"""
هسته‌ی مرکزی محدودسازی نرخ درخواست (Rate Limiting) و ضدِ اسپم/فلاد - هم برای
بات (هر کاربر تلگرام) هم برای مینی‌اپ/وب‌هوک‌ها (بر اساس IP یا کاربر تلگرام).

کاملاً در حافظه‌ست (بدون نیاز به Redis یا هر سرویس بیرونی دیگه) - برای مقیاس
این پروژه (یک پردازش، چند صد تا چند هزار کاربر) کاملاً کافیه و هیچ وابستگی
جدیدی هم لازم نداره. اگه یه روز چندین پردازش/سرور موازیِ همین بات رو
اجرا کردی (مثلاً چندتا worker)، باید این حافظه رو مشترک کنی (مثلاً Redis)،
وگرنه هر پردازش شمارنده‌ی جدای خودشو نگه می‌داره.

منطق: sliding window ساده + «تنبیه تصاعدی». هر شناسه (کلید) یه لیست از
زمان درخواست‌های اخیرشه؛ اگه از سقف مجاز توی پنجره‌ی زمانی رد بشه، بلافاصله
رد نمیشه فقط - برای یه مدت (که با هر تخلف پشت‌سرهم دوبرابر میشه تا سقف ۱۰
دقیقه) کاملاً مسدود میشه. این جلوی یه اسکریپت حمله‌ای که دقیقاً زیر آستانه
درخواست می‌فرسته رو هم می‌گیره؛ کاربر عادی که فقط تند کلیک کرده هم بعد از
چند ثانیه صبر دوباره کارش راه میفته.
"""
import threading
import time
import logging

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_buckets: dict[str, list] = {}       # key -> [timestamps]
_violations: dict[str, tuple] = {}   # key -> (تعداد تخلف پشت‌سرهم, آخرین زمان تخلف)
_blocked_until: dict[str, float] = {}  # key -> تا چه زمانی کاملاً مسدوده

_MAX_TRACKED_KEYS = 20_000  # جلوی رشد بی‌نهایت حافظه؛ فقط برای پاکسازی دوره‌ای
_VIOLATION_FORGET_SECONDS = 3600  # بعد از یک ساعت بدون تخلف جدید، سابقه‌ی تنبیه تصاعدی پاک میشه
_MAX_PENALTY_SECONDS = 600  # سقف مسدودی: ۱۰ دقیقه


def _cleanup_locked(now: float):
    """فقط وقتی تعداد کلیدها زیاد شده صدا زده میشه؛ داده‌های راکد رو پاک می‌کنه"""
    if len(_buckets) <= _MAX_TRACKED_KEYS:
        return
    stale = [k for k, v in _buckets.items() if not v or now - v[-1] > _VIOLATION_FORGET_SECONDS]
    for k in stale:
        _buckets.pop(k, None)
        _violations.pop(k, None)
        _blocked_until.pop(k, None)


def allow(key: str, limit: int, window_seconds: float) -> tuple:
    """
    بررسی می‌کنه که آیا شناسه‌ی «key» اجازه‌ی یه درخواست دیگه رو داره یا نه.
    خروجی: (ok: bool, retry_after_seconds: float)
    - ok=True یعنی مجازه (و این درخواست هم توی شمارش لحاظ شد)
    - ok=False یعنی رد شده؛ retry_after_seconds یعنی چند ثانیه دیگه صبر کنه
    """
    now = time.time()
    with _lock:
        blocked = _blocked_until.get(key, 0)
        if blocked > now:
            return False, round(blocked - now, 1)

        bucket = _buckets.setdefault(key, [])
        cutoff = now - window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)

        if len(bucket) >= limit:
            count, last = _violations.get(key, (0, 0))
            if now - last > _VIOLATION_FORGET_SECONDS:
                count = 0
            count += 1
            penalty = min(window_seconds * (2 ** min(count, 6)), _MAX_PENALTY_SECONDS)
            _blocked_until[key] = now + penalty
            _violations[key] = (count, now)
            _cleanup_locked(now)
            return False, round(penalty, 1)

        bucket.append(now)
        _cleanup_locked(now)
        return True, 0.0


def reset(key: str):
    """پاک کردن کامل سابقه‌ی یه شناسه (مثلاً برای تست دستی یا رفع مسدودی توسط ادمین)"""
    with _lock:
        _buckets.pop(key, None)
        _violations.pop(key, None)
        _blocked_until.pop(key, None)


def violation_streak(key: str) -> int:
    """چندبار پشت‌سرهم این شناسه لیمیت رو رد کرده - برای تصمیم «به ادمین اطلاع بدیم یا نه»"""
    with _lock:
        count, _ = _violations.get(key, (0, 0))
        return count
