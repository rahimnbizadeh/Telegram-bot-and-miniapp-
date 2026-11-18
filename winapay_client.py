"""
کلاینت درگاه پرداخت ویناپی (WinaPay) - https://winapay.io/public/document

جریان کار (شبیه زرین‌پال):
۱. create_payment: درخواست PaymentRequest → Authority (۳۲ کاراکتر) + لینک پرداخت.
۲. کاربر تو مرورگر پرداخت می‌کنه و ویناپی کاربر رو با POST (PaymentStatus=OK/NOK و
   Authority) به CallbackURL ما برمی‌گردونه.
۳. verify_payment: درخواست PaymentVerification (با همون Amount فاکتور). فقط پاسخ همین
   استعلام معتبره؛ فیلدهای کال‌بک مرورگر قابل‌جعل‌ان و هیچ‌وقت مستقیم باور نمیشن.

پاسخ‌ها JSON و درخواست‌ها فرم‌انکد (application/x-www-form-urlencoded) هستن.
"""
import logging
import secrets
import time

import httpx

from config import WINAPAY_MERCHANT_ID

logger = logging.getLogger(__name__)

BASE_URL = "https://winapay.io/webservice/rest"
START_PAY_URL = "https://winapay.io/startPay/"
TIMEOUT_SECONDS = 30


class WinaPayError(Exception):
    pass


# شرح کدها از https://winapay.io/public/response
STATUS_MESSAGES = {
    100: "عملیات موفقیت‌آمیز بود.",
    101: "پرداخت موفق بوده و قبلاً تایید شده.",
    102: "اتصال به وب‌سرویس ویناپی انجام نشد.",
    -1: "درخواست باید از طریق وب‌سرویس ارسال بشه.",
    -2: "مرچنت‌آیدی ارسال نشده.",
    -3: "مبلغ ارسال نشده.",
    -4: "آدرس بازگشت (CallbackURL) ارسال نشده.",
    -5: "حداقل مبلغ قابل پرداخت در ویناپی ۱۰۰ تومانه.",
    -6: "مرچنت‌آیدی تو ویناپی پیدا نشد.",
    -7: "مرچنت‌آیدی تو ویناپی فعال نیست.",
    -8: "اکانت ویناپی تجاری نیست و امکان استفاده از وب‌سرویس نداره.",
    -9: "IP سرور برای ویناپی معتبر نیست (IP سرور رو تو پنل ویناپی ثبت کن).",
    -10: "آدرس بازگشت با آدرس ثبت‌شده‌ی درگاه تو ویناپی یکی نیست.",
    -11: "ساخت تراکنش تو ویناپی با خطا مواجه شد.",
    -12: "شناسه‌ی تراکنش (Authority) معتبر نیست.",
    -13: "شناسه‌ی تراکنش (Authority) ارسال نشده.",
    -14: "اطلاعات تراکنش پیدا نشد.",
    -15: "تراکنش هنوز پرداخت نشده.",
    -16: "مبلغ ارسالی با مبلغ تراکنش یکی نیست.",
    -17: "این تراکنش برای مرچنت‌آیدی شما ثبت نشده.",
    -18: "پرداخت انجام شده ولی به‌روزرسانی کیف پول پذیرنده تو ویناپی مشکل داشته.",
    -19: "وضعیت تراکنش نامشخصه.",
    -20: "شماره کارت ارسال‌شده معتبر نیست.",
    -21: "شماره کارت پرداخت‌کننده با کارت مجاز مطابقت نداره.",
}


def explain(status) -> str:
    try:
        code = int(status)
    except (TypeError, ValueError):
        return "پاسخ نامعتبر از ویناپی."
    return STATUS_MESSAGES.get(code, f"خطای ناشناخته از ویناپی (کد {code}).")


def make_order_id() -> str:
    """InvoiceID یکتا که به ویناپی میدیم و بعد از پرداخت هم به‌ما برمی‌گرده"""
    return f"W{int(time.time())}{secrets.token_hex(3).upper()}"


def _to_int(v, default=None):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


async def _post(endpoint: str, data: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.post(f"{BASE_URL}/{endpoint}", data=data)
    except httpx.HTTPError as e:
        raise WinaPayError(f"اتصال به ویناپی برقرار نشد: {e}") from e
    try:
        payload = resp.json()
    except ValueError as e:
        raise WinaPayError(f"پاسخ نامعتبر از ویناپی (HTTP {resp.status_code}).") from e
    if not isinstance(payload, dict):
        raise WinaPayError("پاسخ نامعتبر از ویناپی.")
    return payload


async def create_payment(amount_toman: int, order_id: str, callback_url: str, description: str = "") -> dict:
    """→ {"authority": ..., "payment_url": ...}"""
    if not WINAPAY_MERCHANT_ID:
        raise WinaPayError("درگاه ویناپی تنظیم نشده (WINAPAY_MERCHANT_ID خالیه).")
    if not callback_url:
        raise WinaPayError("آدرس عمومی سرور (PUBLIC_BASE_URL) تنظیم نشده؛ ویناپی بدون آدرس بازگشت کار نمی‌کنه.")
    amount = int(amount_toman)
    if amount < 100:
        raise WinaPayError(explain(-5))

    data = {
        "MerchantID": WINAPAY_MERCHANT_ID,
        "Amount": str(amount),
        "InvoiceID": order_id,
        "CallbackURL": callback_url,
    }
    if description:
        data["Description"] = description[:200]
    payload = await _post("PaymentRequest", data)

    status = _to_int(payload.get("Status"))
    authority = str(payload.get("Authority") or "").strip()
    if status != 100 or not authority:
        logger.warning("ویناپی PaymentRequest ناموفق: status=%s", status)
        raise WinaPayError(explain(status))

    url = str(payload.get("PaymentUrl") or "").strip()
    if not url.startswith("https://"):
        url = START_PAY_URL + authority
    return {"authority": authority, "payment_url": url}


async def verify_payment(authority: str, amount_toman: int) -> dict:
    """
    استعلام نهایی. خروجی:
      paid: True اگه پرداخت قطعی شده (۱۰۰ = تازه تایید شد، ۱۰۱ = قبلاً تایید شده، -۱۸ = پرداخت
            انجام شده ولی کیف پول پذیرنده‌ی ویناپی مشکل داشته؛ پول کاربر کم شده پس تحویل میدیم)
      wallet_issue: True فقط برای -۱۸ (باید به ادمین خبر داده بشه)
      unpaid: True اگه هنوز پرداخت نشده (-۱۵)
      status / ref_id / amount / message
    """
    if not WINAPAY_MERCHANT_ID:
        raise WinaPayError("درگاه ویناپی تنظیم نشده (WINAPAY_MERCHANT_ID خالیه).")
    payload = await _post("PaymentVerification", {
        "MerchantID": WINAPAY_MERCHANT_ID,
        "Authority": authority,
        "Amount": str(int(amount_toman)),
    })
    status = _to_int(payload.get("Status"))
    paid = status in (100, 101, -18)
    paid_amount = _to_int(payload.get("Amount"))
    # دفاع دوم: اگه ویناپی مبلغ پرداخت‌شده رو برگردونده و با فاکتور فرق داره، تحویل نمیدیم
    if paid and paid_amount is not None and paid_amount != int(amount_toman):
        logger.error("ویناپی: مبلغ پرداخت‌شده (%s) با مبلغ فاکتور (%s) فرق داره - authority=%s",
                     paid_amount, amount_toman, authority)
        paid = False
    return {
        "status": status,
        "paid": paid,
        "wallet_issue": status == -18,
        "unpaid": status == -15,
        "ref_id": payload.get("RefID"),
        "amount": paid_amount,
        "message": explain(status),
    }
