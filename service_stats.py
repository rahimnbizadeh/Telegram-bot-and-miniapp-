"""
دو تابع مشترک برای محاسبه‌ی آمار سرویس (حجم باقی‌مانده/روز باقی‌مانده) که هم
خود ربات (user.py) و هم Flask API مینی‌اپ (keep_alive.py) بهشون نیاز دارن.

عمداً یه فایل کاملاً مستقل و سبکه (فقط به panel_client و config وابسته‌ست،
نه به telegram/python-telegram-bot) تا Flask بتونه بدون بار اضافه‌ی import
کل ماژول user.py، دقیقاً همون منطق محاسبه‌ی خود ربات رو صدا بزنه - یعنی
عددی که داخل Mini App می‌بینی، تضمینی همونیه که داخل خود بات می‌بینی.
"""
import datetime

from config import DEMO_MODE, get_plan, GRACE_DAYS_TIME, GRACE_DAYS_DATA
from panel_client import panel, PanelError


async def fetch_live_stats(sub, include_config: bool = True) -> dict:
    """
    حجم مصرف‌شده/باقی‌مانده + لینک کانفیگ خام زنده‌ی هر سرویس رو برمی‌گردونه.
    include_config=False فقط تو حالتی استفاده میشه که واقعاً کانفیگ لازم
    نیست (مثلاً رندر لیست خلاصه‌ی سرویس‌ها) تا یه درخواست اضافه به پنل
    (گرفتن اطلاعات اینباند) به‌ازای هر سرویس زده نشه.
    در DEMO_MODE چون به پنل واقعی وصل نیستیم، عددی پایدار و شبه‌تصادفی
    (بر اساس یوزرنیم) نمایش می‌دیم که هر بار یکسان بمونه.
    """
    plan = get_plan(sub["plan_id"]) if sub["plan_id"] else None
    limit_gb = plan["gb"] if plan else 0

    if DEMO_MODE:
        seed = sum(ord(c) for c in (sub["marzban_username"] or str(sub["sub_id"])))
        if limit_gb and limit_gb > 0:
            used_gb = round(limit_gb * ((seed % 70 + 5) / 100), 2)
            remaining_gb = round(max(limit_gb - used_gb, 0), 2)
        else:
            remaining_gb = None
        return {
            "remaining_gb": remaining_gb,
            "limit_gb": limit_gb,
            "real_limit_gb": None,
            "connection_link": "",
            "subscription_url": sub["sub_link"],
        }

    try:
        info = await panel.get_user(sub["marzban_username"], include_config=include_config)
    except PanelError:
        return {
            "remaining_gb": None,
            "limit_gb": limit_gb,
            "real_limit_gb": None,
            "connection_link": "",
            "subscription_url": sub["sub_link"],
        }

    used_bytes = info.get("used_traffic") or 0
    limit_bytes = info.get("data_limit") or 0
    real_limit_gb = None
    if limit_bytes and limit_bytes > 0:
        limit_gb_real = limit_bytes / (1024 ** 3)
        used_gb = used_bytes / (1024 ** 3)
        remaining_gb = round(max(limit_gb_real - used_gb, 0), 2)
        # سقف واقعی روی پنل (بعد از تمدید = حجم پلن + باقی‌ماندهٔ قبلی)؛ نه عدد خامِ پلن
        real_limit_gb = round(limit_gb_real, 2)
    else:
        remaining_gb = None
    return {
        "remaining_gb": remaining_gb,
        "limit_gb": limit_gb,
        "real_limit_gb": real_limit_gb,
        "connection_link": info.get("connection_link") or "",
        "subscription_url": info.get("subscription_url") or sub["sub_link"],
    }


def remaining_days(sub):
    if not sub["expire_at"]:
        return None
    return max(0, (sub["expire_at"] - int(datetime.datetime.now().timestamp())) // 86400)


def grace_seconds(reason) -> int:
    """طول مهلت تمدید برای هر نوع پایان: 'data' (اتمام حجم) یا 'time' (اتمام زمان)"""
    days = GRACE_DAYS_DATA if reason == "data" else GRACE_DAYS_TIME
    return int(days * 86400)


def grace_deadline(sub):
    """
    زمان حذف قطعی یه سرویس «پایان‌یافته» (timestamp)؛ برای سرویس‌ای که هنوز
    پایان‌یافته علامت نخورده None برمی‌گردونه. هم بات و هم Flask ازش استفاده می‌کنن.
    """
    if not sub["ended_at"]:
        return None
    return int(sub["ended_at"]) + grace_seconds(sub["ended_reason"])


def grace_left_seconds(sub):
    """چند ثانیه تا حذف مونده (حداقل ۰)؛ اگه سرویس پایان‌یافته نیست None"""
    deadline = grace_deadline(sub)
    if deadline is None:
        return None
    return max(0, deadline - int(datetime.datetime.now().timestamp()))

