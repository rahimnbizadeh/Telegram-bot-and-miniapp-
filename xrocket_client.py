"""
کلاینت اتصال به xRocket Pay برای پرداخت کریپتو - نسخه‌ی مستقیم HTTP.

مبتنی بر:
- آدرس پایه‌ی رسمی: https://pay.xrocket.tg/  (تایید‌شده از مستندات چند SDK رسمی/غیررسمی)
- روش ساخت فاکتور: POST به مسیر اندپوینت اینویس با فیلدهای amount, currency,
  description (دقیقاً مطابق پارامترهای SDK رسمی TypeScript این سرویس)
- هدر احراز هویت: Rocket-Pay-Key

⚠️ در سطح مسیر دقیق endpoint (که این ربات فرض می‌کنه /tg-invoices هست) و اسم
دقیق فیلدهای پاسخ (لینک پرداخت، وضعیت)، به مستندات Swagger رسمی (پشت
robots.txt) دسترسی مستقیم نداشتم. **بعد از اولین تست واقعی، اگه خطا داد،
پیام خطای کامل (که شامل پاسخ خام سرور میشه) رو برام بفرست تا مسیر یا اسم
فیلد رو در همین یک فایل اصلاح کنم.**
"""
import time

import httpx

from config import XROCKET_API_KEY, XROCKET_DEMO_MODE, CRYPTO_RATES_TOMAN

BASE_URL = "https://pay.xrocket.tg"


class XRocketError(Exception):
    pass


def _headers():
    return {"Rocket-Pay-Key": XROCKET_API_KEY, "Content-Type": "application/json"}


def toman_to_crypto(amount_toman: int, currency: str) -> float:
    rate = CRYPTO_RATES_TOMAN.get(currency)
    if not rate or rate <= 0:
        raise XRocketError(f"نرخ تبدیل برای ارز {currency} تنظیم نشده.")
    amount = round(amount_toman / rate, 6)
    return max(amount, 0.000001)  # جلوگیری از فاکتور صفر


def _unwrap(payload: dict) -> dict:
    """بعضی پاسخ‌ها زیر کلید data میان، بعضی مستقیم؛ هر دو حالت رو پشتیبانی می‌کنیم"""
    if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], dict):
        return payload["data"]
    return payload


async def create_invoice(amount_toman: int, currency: str, description: str) -> dict:
    """
    یک فاکتور پرداخت کریپتو برای ارز مشخص‌شده می‌سازه.
    خروجی: {"invoice_id": ..., "pay_url": ..., "amount_crypto": ..., "currency": ...}
    """
    amount_crypto = toman_to_crypto(amount_toman, currency)

    if XROCKET_DEMO_MODE:
        return {
            "invoice_id": f"demo-{int(time.time())}",
            "pay_url": "https://t.me/xrocket?start=demo-invoice",
            "amount_crypto": amount_crypto,
            "currency": currency,
        }

    body = {
        "amount": amount_crypto,
        "currency": currency,
        "description": description[:1024],
        "numPayments": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(f"{BASE_URL}/tg-invoices", json=body, headers=_headers())
    except httpx.HTTPError as e:
        raise XRocketError(f"اتصال به xRocket ناموفق بود: {e}")

    if resp.status_code not in (200, 201):
        raise XRocketError(f"ساخت فاکتور ناموفق بود ({resp.status_code}): {resp.text}")

    data = _unwrap(resp.json())
    pay_url = data.get("link") or data.get("payUrl") or data.get("pay_url")
    invoice_id = data.get("id") or data.get("invoiceId")

    if not pay_url or not invoice_id:
        raise XRocketError(
            f"پاسخ غیرمنتظره از xRocket دریافت شد (این متن رو برای اصلاح کد بفرست): {resp.text}"
        )

    return {
        "invoice_id": invoice_id,
        "pay_url": pay_url,
        "amount_crypto": amount_crypto,
        "currency": currency,
    }


async def check_invoice(invoice_id: str) -> str:
    """
    وضعیت فاکتور رو برمی‌گردونه: 'paid' / 'pending' / 'expired' / 'unknown'
    """
    if XROCKET_DEMO_MODE:
        return "paid"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{BASE_URL}/tg-invoices/{invoice_id}", headers=_headers())
    except httpx.HTTPError as e:
        raise XRocketError(f"اتصال به xRocket ناموفق بود: {e}")

    if resp.status_code != 200:
        raise XRocketError(f"بررسی وضعیت فاکتور ناموفق بود ({resp.status_code}): {resp.text}")

    data = _unwrap(resp.json())
    status = str(data.get("status") or data.get("paymentStatus") or "unknown").lower()

    if status in ("paid", "completed", "success", "active_paid"):
        return "paid"
    if status in ("expired", "cancelled", "canceled"):
        return "expired"
    return "pending"
