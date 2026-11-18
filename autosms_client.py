"""
کلاینت اتصال به AutoSMS - درگاه کارت‌به‌کارت با تایید خودکار (تشخیص پیامک بانکی).
مستندات رسمی: https://rialbotapi.shop/autosms/docs.php

نکات مهم مستندات:
- همه‌ی مبالغ AutoSMS بر خلاف بعضی درگاه‌های دیگه «تومان»ـه، نه ریال.
- pay_amount_toman یه پسوند یکتا داره (چند رقم متفاوت با amount درخواستی) که
  برای تشخیص خودکار پیامک لازمه - همیشه دقیقاً همین عدد باید به کاربر نشون
  داده بشه، نه amount اصلی.
- هر authority فقط یک‌بار توسط verify-payment جواب موفق می‌ده (جلوگیری از
  تحویل دوبار).

نکته‌ی عملیاتی: سرور rialbotapi.shop گاهی زیر بار یا قطعی موقت، به‌جای JSON
یه صفحه‌ی خطای Cloudflare (502/503/504/522 و...) برمی‌گردونه. برای همین هر
درخواست یک‌بار با کمی تاخیر retry می‌شه، و اگه بازم شکست بخوره، پیام روشنی
مبنی بر «درگاه موقتاً در دسترس نیست» به‌جای یه خطای گنگ نشون داده می‌شه.
"""
import asyncio
import hashlib
import hmac
import time

import httpx

from config import AUTOSMS_API_KEY, AUTOSMS_WEBHOOK_SECRET, PUBLIC_BASE_URL

BASE_URL = "https://rialbotapi.shop/autosms"

ERROR_MESSAGES = {
    "insufficient_balance": "موجودی درگاه پرداخت کافی نیست؛ لطفاً بعداً امتحان کن یا از روش دیگه‌ای استفاده کن.",
    "not_activated": "درگاه پرداخت خودکار هنوز فعال نشده.",
    "no_card_available": "فعلاً کارتی برای پرداخت خودکار در دسترس نیست؛ لطفاً روش دیگه‌ای رو امتحان کن.",
}

GATEWAY_DOWN_MSG = (
    "درگاه پرداخت خودکار موقتاً در دسترس نیست (خطای سرور {code}). "
    "چند لحظه دیگه دوباره امتحان کن یا از روش دیگه‌ای استفاده کن."
)


class AutoSMSError(Exception):
    pass


def _headers():
    return {"Authorization": f"Bearer {AUTOSMS_API_KEY}", "Content-Type": "application/json"}


def _callback_url() -> str:
    base = PUBLIC_BASE_URL or "https://example.com"
    return f"{base}/webhook/autosms"


def _parse_json(resp):
    if resp.status_code >= 500:
        raise AutoSMSError(GATEWAY_DOWN_MSG.format(code=resp.status_code))
    try:
        return resp.json()
    except ValueError:
        raise AutoSMSError(f"پاسخ نامعتبر از درگاه دریافت شد ({resp.status_code}): {resp.text[:300]}")


async def _request(method: str, url: str, *, retries: int = 1, retry_delay: float = 1.5, **kwargs):
    """یه درخواست با یک‌بار retry روی خطاهای موقتی شبکه/سرور (>=500 یا timeout)"""
    last_exc = None
    timeout = kwargs.pop("timeout", 20)
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(method, url, **kwargs)
            if resp.status_code >= 500 and attempt < retries:
                await asyncio.sleep(retry_delay)
                continue
            return resp
        except httpx.HTTPError as e:
            last_exc = e
            if attempt < retries:
                await asyncio.sleep(retry_delay)
                continue
    raise AutoSMSError(f"اتصال به درگاه پرداخت خودکار ناموفق بود: {last_exc}")


async def create_payment(amount_toman: int, order_id: str, description: str = "", ttl_minutes: int = 60) -> dict:
    """
    یه فاکتور جدید می‌سازه.
    خروجی موفق شامل: authority, pay_amount_toman, base_amount_toman,
    card_number, card_holder, expires_at, expires_at_datetime, ttl_minutes
    """
    body = {
        "amount": amount_toman,
        "order_id": order_id[:64],
        "callback_url": _callback_url(),
        "description": (description or "")[:255],
        "ttl_minutes": ttl_minutes,
    }
    resp = await _request(
        "POST", f"{BASE_URL}/api/v1/create-payment.php", json=body, headers=_headers(), timeout=20
    )
    data = _parse_json(resp)
    if not data.get("success"):
        code = data.get("code")
        raise AutoSMSError(ERROR_MESSAGES.get(code, data.get("error") or "خطای نامشخص از درگاه پرداخت."))
    return data


async def verify_payment(authority: str) -> dict:
    """تایید نهایی و یک‌بارمصرف - فقط وقتی بخوایم مطمئن قطعی بشیم که تحویل بدیم"""
    resp = await _request(
        "POST", f"{BASE_URL}/api/v1/verify-payment.php", json={"authority": authority}, headers=_headers(),
        timeout=20,
    )
    return _parse_json(resp)


async def check_status(authority: str, known_status: str = "pending") -> str:
    """
    Long-polling وضعیت (تا ~۱۸ ثانیه باز می‌مونه). خروجی: pending / paid / expired
    نیاز به توکن نداره.
    """
    resp = await _request(
        "GET", f"{BASE_URL}/status.php", params={"authority": authority, "known_status": known_status},
        timeout=25,
    )
    data = _parse_json(resp)
    return data.get("status", "pending")


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """امضای X-Signature وب‌هوک رو با webhook_secret تایید می‌کنه (HMAC-SHA256)"""
    if not AUTOSMS_WEBHOOK_SECRET or not signature:
        return False
    expected = hmac.new(AUTOSMS_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def make_order_id(kind: str, user_id: int) -> str:
    return f"noordis-{kind}-{user_id}-{int(time.time() * 1000)}"
