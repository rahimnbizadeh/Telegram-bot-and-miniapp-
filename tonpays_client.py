"""
کلاینت اتصال به TonPays - درگاه پرداخت با فاکتور هاست‌شده (کارت‌به‌کارت خودکار).
مستندات رسمی (OpenAPI کامل): https://tonpays.online/openapi.json
رابط Swagger: https://tonpays.online/docs

خلاصه‌ی مستندات:
- Base URL: https://tonpays.online
- احراز هویت: هدر X-API-Key با مقدار API Key (از منوی بات TonPays، گزینه‌ی
  «مستندات API» گرفته میشه).
- POST /api/v1/invoices/create
    ورودی: amount (تومان)، order_id (رشته، حداکثر ۲۰ کاراکتر، باید بین
    سفارش‌های همین مرچنت یکتا باشه)، callback_url (اختیاری).
    خروجی: invoice_id, order_id, request_amount, final_amount, status,
    invoice_url (صفحه‌ی پرداخت هاست‌شده که کاربر رو بهش می‌فرستیم)،
    و به‌صورت اختیاری payment_url/card_number/card_name (فقط اگه برای
    همین API Key فعال باشن).
- GET /api/v1/invoices/check/{invoice_id}  (یا POST /api/v1/invoices/check)
    خروجی: invoice_id, order_id, request_amount, final_amount, status, paid (bool)

⚠️ نکته‌ی امنیتی مهم درباره‌ی وب‌هوک:
مستندات میگن TonPays یه JSON با فیلد paid:true/false مستقیم به callback_url
POST می‌کنه، ولی برخلاف AutoSMS (که X-Signature/HMAC داره)، هیچ امضایی برای
این وب‌هوک تعریف نشده. یعنی تئوریاً هرکسی که invoice_id/order_id رو حدس
بزنه یا ببینه می‌تونه یه POST جعلی به وب‌هوک ما بفرسته و ادعای «پرداخت شد»
کنه. برای همین در کل این پروژه، هیچ‌جا مستقیم به فیلد paid توی بدنه‌ی
وب‌هوک اعتماد نمی‌کنیم؛ وب‌هوک فقط یه «زنگ اطلاع» برای بررسی فوریه - همون
لحظه با همین تابع check_invoice() و کلید API خودمون دوباره از سرور TonPays
استعلام می‌گیریم و فقط بر اساس اون پاسخِ احرازهویت‌شده سرویس رو نهایی
می‌کنیم. (job دوره‌ای هم که هر چند دقیقه پندینگ‌ها رو چک می‌کنه، همین کارو
مستقل از وب‌هوک انجام میده - پس حتی بدون وب‌هوک هم تحویل گیر نمی‌مونه.)
"""
import secrets
import time

import httpx

from config import TONPAYS_API_KEY

BASE_URL = "https://tonpays.online"

INVALID_KEY_MSG = (
    "کلید API درگاه TonPays نامعتبره. از منوی بات TonPays (گزینه‌ی «مستندات API») "
    "یه کلید تازه بگیر و مقدار TONPAYS_API_KEY رو توی تنظیمات/.env جایگزین کن."
)

_TERMINAL_FAIL_STATUSES = {"expired", "rejected", "cancelled", "canceled", "failed"}


class TonPaysError(Exception):
    pass


def _headers():
    return {"X-API-Key": TONPAYS_API_KEY, "Content-Type": "application/json"}


def make_order_id() -> str:
    """
    شناسه‌ی سفارش یکتا برای همین مرچنت - طبق مستندات حداکثر ۲۰ کاراکتر.
    بر پایه‌ی زمان به‌میلی‌ثانیه (تبدیل‌شده به مبنای ۳۶ برای کوتاهی) + چهار
    کاراکتر رندوم؛ نیازی نیست چیزی ازش decode بشه، فقط باید کوتاه و یکتا بمونه.
    """
    n = int(time.time() * 1000)
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    ts36 = ""
    while n:
        n, r = divmod(n, 36)
        ts36 = digits[r] + ts36
    return f"n{ts36}{secrets.token_hex(2)}"[:20]


def _raise_for_status(resp: httpx.Response, context: str):
    if resp.status_code in (401, 403):
        raise TonPaysError(INVALID_KEY_MSG)
    if resp.status_code == 422:
        raise TonPaysError(f"داده‌ی ارسالی به TonPays نامعتبر بود: {resp.text[:300]}")
    if resp.status_code >= 400:
        raise TonPaysError(f"{context} ناموفق بود ({resp.status_code}): {resp.text[:300]}")


async def create_invoice(amount_toman: int, order_id: str, callback_url: str = None) -> dict:
    """
    یه فاکتور جدید می‌سازه و دیکشنری خام پاسخ TonPays رو برمی‌گردونه:
    invoice_id, order_id, request_amount, final_amount, status, invoice_url,
    و در صورت وجود: payment_url, card_number, card_name
    """
    body = {"amount": int(amount_toman), "order_id": str(order_id)[:20]}
    if callback_url:
        body["callback_url"] = callback_url

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(f"{BASE_URL}/api/v1/invoices/create", json=body, headers=_headers())
    except httpx.HTTPError as e:
        raise TonPaysError(f"اتصال به درگاه TonPays ناموفق بود: {e}")

    _raise_for_status(resp, "ساخت فاکتور TonPays")

    try:
        data = resp.json()
    except ValueError:
        raise TonPaysError(f"پاسخ نامعتبر از TonPays دریافت شد: {resp.text[:300]}")

    if not data.get("invoice_url"):
        raise TonPaysError(f"پاسخ TonPays بدون لینک پرداخت بود (این متن رو برای اصلاح کد بفرست): {resp.text[:300]}")

    return data


async def check_invoice(invoice_id: str) -> dict:
    """
    وضعیت فعلی فاکتور رو مستقیم و با کلید API خودمون از سرور TonPays می‌گیره.
    این تابع تنها منبع قابل‌اعتماد برای تشخیص «پرداخت‌شده» است - نه بدنه‌ی وب‌هوک.
    خروجی خام TonPays: invoice_id, order_id, request_amount, final_amount, status, paid (bool)
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{BASE_URL}/api/v1/invoices/check/{invoice_id}", headers=_headers())
    except httpx.HTTPError as e:
        raise TonPaysError(f"اتصال به درگاه TonPays ناموفق بود: {e}")

    _raise_for_status(resp, "بررسی وضعیت فاکتور TonPays")

    try:
        return resp.json()
    except ValueError:
        raise TonPaysError(f"پاسخ نامعتبر از TonPays دریافت شد: {resp.text[:300]}")


def is_terminal_failure(status: str) -> bool:
    """وضعیت‌هایی که یعنی فاکتور دیگه هیچ‌وقت پرداخت نمیشه (منقضی/رد/لغوشده)"""
    return str(status or "").lower() in _TERMINAL_FAIL_STATUSES
