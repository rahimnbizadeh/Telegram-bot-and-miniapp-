"""
پاداش روزانه‌ی مینی‌اپ: هر روز (به وقت ایران) یه‌بار «دریافت امروز»؛ زنجیره‌ی روزهای پشت‌سرهم
تو مایل‌استون‌های config.STREAK_MILESTONES جایزه‌ی «کد تخفیف شخصی یک‌بارمصرف» میده.

قوانین ضدسوءاستفاده:
- جایزه فقط برای کاربری که حداقل یه خرید/تمدید تاییدشده داره (اعتبار کیف پول داده نمیشه چون قابل انتقاله).
- گرفتنِ دوباره‌ی «همون» جایزه (با شکستن و دوباره شروع‌کردن زنجیره) باید STREAK_REWARD_COOLDOWN_DAYS روز صبر کنه.
- روز با ساعت ایران (UTC+3:30) حساب میشه و ثبت سمت سرور انجام میشه، نه کلاینت.

ماژول مستقل از تلگرام/Flask ـه؛ فقط keep_alive.py صداش می‌زنه.
"""
import logging
import time
from datetime import datetime, timedelta, timezone

import database as db
from config import (
    DAILY_CHECKIN_ENABLED,
    STREAK_MILESTONES,
    STREAK_CODE_HOURS,
    STREAK_REWARD_COOLDOWN_DAYS,
)

logger = logging.getLogger(__name__)

_IRAN = timezone(timedelta(hours=3, minutes=30))
_MILESTONE_MAP = dict(STREAK_MILESTONES)
_LAST_DAYS, _LAST_PERCENT = max(STREAK_MILESTONES)[0], max(STREAK_MILESTONES)[1]


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, _IRAN).strftime("%Y-%m-%d")


def _today_yesterday(now: float):
    return _day(now), _day(now - 86400)


def milestone_percent(streak: int):
    """درصد جایزه‌ی این روزِ زنجیره (یا None). بعد از آخرین مایل‌استون، هر _LAST_DAYS روز تکرار میشه."""
    if streak in _MILESTONE_MAP:
        return _MILESTONE_MAP[streak]
    if streak > _LAST_DAYS and streak % _LAST_DAYS == 0:
        return _LAST_PERCENT
    return None


def next_milestone(streak: int):
    """نزدیک‌ترین مایل‌استون بعد از زنجیره‌ی فعلی: {"days","percent"}"""
    for days, percent in sorted(STREAK_MILESTONES):
        if days > streak:
            return {"days": days, "percent": percent}
    days = (streak // _LAST_DAYS + 1) * _LAST_DAYS
    return {"days": days, "percent": _LAST_PERCENT}


def _active_code(row, now: float):
    """کد جایزه‌ی هنوز معتبر و مصرف‌نشده‌ی کاربر (تا از دستش نده)، وگرنه None"""
    if not row or not row["last_code"] or not row["last_code_expires"] or row["last_code_expires"] <= now:
        return None
    code = db.get_discount_code(row["last_code"])
    if not code or not code["active"]:
        return None
    if code["max_uses"] is not None and code["used_count"] >= code["max_uses"]:
        return None
    return {"code": row["last_code"], "percent": row["last_code_percent"], "expires_at": row["last_code_expires"]}


def get_state(user_id: int, now: float = None) -> dict:
    now = now if now is not None else time.time()
    if not DAILY_CHECKIN_ENABLED:
        return {"enabled": False}
    today, yesterday = _today_yesterday(now)
    row = db.get_checkin_row(user_id)
    claimed_today = bool(row and row["last_day"] == today)
    alive = bool(row and row["last_day"] in (today, yesterday))
    streak = row["streak"] if alive else 0          # زنجیره‌ی شکسته‌شده = ۰
    return {
        "enabled": True,
        "streak": streak,
        "best": row["best"] if row else 0,
        "total": row["total"] if row else 0,
        "claimed_today": claimed_today,
        "next": next_milestone(streak),
        "eligible": db.has_paid_purchase(user_id),
        "code": _active_code(row, now),
        "milestones": [{"days": d, "percent": p} for d, p in sorted(STREAK_MILESTONES)],
    }


def claim(user_id: int, now: float = None) -> dict:
    """
    «دریافت امروز». خروجی = get_state(...) + :
      already     امروز قبلاً گرفته بود
      milestone   اگه امروز به مایل‌استون رسید {"days","percent"}
      locked      اگه مایل‌استون رسید ولی جایزه داده نشد: 'no_purchase' | 'cooldown'
    و اگه جایزه داده شد، کدش تو state["code"] هست.
    """
    now = now if now is not None else time.time()
    if not DAILY_CHECKIN_ENABLED:
        return {"enabled": False}
    today, yesterday = _today_yesterday(now)
    res = db.claim_checkin(
        user_id, today, yesterday, int(now), milestone_percent,
        STREAK_REWARD_COOLDOWN_DAYS * 86400, db.has_paid_purchase(user_id),
    )

    if res["granted"]:
        try:
            percent = res["milestone"]["percent"]
            code = db.create_winback_code(percent, STREAK_CODE_HOURS, prefix="STRK")
            db.save_checkin_code(user_id, code, percent, int(now) + STREAK_CODE_HOURS * 3600)
        except Exception:
            logger.exception("ساخت کد جایزه‌ی زنجیره برای کاربر %s ناموفق بود", user_id)
            db.restore_checkin_reward(user_id, res["milestone"]["days"], res["prev_reward_at"])   # cooldown نسوزه
            res["granted"] = False

    state = get_state(user_id, now)
    state.update({"already": res["already"], "milestone": res["milestone"], "locked": res["locked"]})
    return state
