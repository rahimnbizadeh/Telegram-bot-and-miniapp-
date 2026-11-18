"""
یادآوری هوشمند اتمام حجم (پیش‌بینی بر اساس مصرف واقعی).

چرا: هشدار قدیمی فقط وقتی میاد که مصرف به درصد ثابتی از سقف برسه (مثلاً ۹۰٪). ولی کسی که روزی ۵ گیگ
مصرف می‌کنه ممکنه با ۶۰٪ مصرف هم تا دو روز دیگه تموم کنه. این جاب با تاریخچه‌ی مصرف روزانه
(usage_history) سرعت واقعی مصرف رو حساب می‌کنه و اگه حجم قبل از انقضای سرویس و تا چند روز آینده تموم میشه،
یه پیام با دکمه‌ی تمدید می‌فرسته.

نکته‌ها:
- ماژول مستقله: جدول خودش (smart_alerts) رو می‌سازه و فقط تو bot.py (جاب) صدا زده میشه.
- با SMART_ALERTS_ENABLED=false خاموش میشه؛ SMART_ALERT_DAYS (پیش‌فرض ۳) = چند روز جلوتر رو پیش‌بینی کنه.
- برای هر دوره‌ی سرویس (هر بار تمدید = دوره‌ی جدید) فقط یک‌بار پیام میده.
- اگه هشدار قدیمی حجم قبلاً فرستاده شده باشه، دوباره مزاحم نمیشه. تست رایگان رو شامل نمیشه.
- بین ساعت ۲۳ تا ۸ صبح (به وقت ایران) پیام نمی‌فرسته؛ دور بعدی (۳ ساعت بعد) دوباره بررسی میشه.
"""
import html
import logging
import os
import time
from typing import Optional
from datetime import datetime, timedelta, timezone

import database as db
import premium_emoji as pe
import usage_history
from keyboards import data_warning_keyboard
from panel_client import panel, PanelError

logger = logging.getLogger(__name__)

ENABLED = os.getenv("SMART_ALERTS_ENABLED", "true").lower() in ("1", "true", "yes")
LOOKAHEAD_DAYS = float(os.getenv("SMART_ALERT_DAYS", "3"))
MIN_KNOWN_DAYS = 2                      # حداقل چند روز کامل داده برای اعتماد به میانگین
MIN_DAILY_BYTES = 100 * 1024 ** 2       # زیر ۱۰۰ مگابایت در روز، پیش‌بینی بی‌معنیه
QUIET_FROM, QUIET_TO = 23, 8            # ساعت سکوت (وقت ایران)
GB = 1024 ** 3
_IRAN = timezone(timedelta(hours=3, minutes=30))
_table_ready = False


def _ensure_table():
    global _table_ready
    if _table_ready:
        return
    with db.get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS smart_alerts (
                sub_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                period TEXT NOT NULL,
                sent_at INTEGER NOT NULL,
                PRIMARY KEY (sub_id, kind, period)
            )
            """
        )
    _table_ready = True


def _already_sent(sub_id: int, kind: str, period: str) -> bool:
    _ensure_table()
    with db.get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM smart_alerts WHERE sub_id = ? AND kind = ? AND period = ?", (sub_id, kind, period)
        ).fetchone() is not None


def _mark_sent(sub_id: int, kind: str, period: str):
    _ensure_table()
    with db.get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO smart_alerts (sub_id, kind, period, sent_at) VALUES (?, ?, ?, ?)",
            (sub_id, kind, period, int(time.time())),
        )


def avg_daily_bytes(sub_id: int, now: Optional[float] = None) -> Optional[float]:
    """میانگین مصرف روزهای کامل اخیر (حداکثر ۳ روز آخر، بدون امروز که ناقصه). اگه داده کم باشه None."""
    week = usage_history.get_week(sub_id, now)
    days = [d["bytes"] for d in week["days"][:-1] if d["bytes"] is not None][-3:]
    if len(days) < MIN_KNOWN_DAYS:
        return None
    return sum(days) / len(days)


def forecast(sub, limit: int, used: int, now: Optional[float] = None) -> Optional[dict]:
    """
    اگه با روند فعلی حجم تا LOOKAHEAD_DAYS روز آینده و قبل از انقضا تموم بشه، اطلاعات پیش‌بینی رو برمی‌گردونه.
    در غیر این صورت None.
    """
    now = now if now is not None else time.time()
    if not limit or used >= limit:
        return None
    avg = avg_daily_bytes(sub["sub_id"], now)
    if avg is None or avg < MIN_DAILY_BYTES:
        return None
    days_data = (limit - used) / avg
    if days_data > LOOKAHEAD_DAYS:
        return None
    expire_at = sub["expire_at"] or 0
    days_time = (expire_at - now) / 86400 if expire_at else float("inf")
    if days_time <= days_data + 0.25:       # قبل از تموم‌شدن حجم، مدت سرویس تموم میشه؛ هشدار انقضا پوشش میده
        return None
    return {"days": days_data, "avg_gb": avg / GB}


def _is_quiet_hour(now: Optional[float] = None) -> bool:
    h = datetime.fromtimestamp(now if now is not None else time.time(), _IRAN).hour
    return h >= QUIET_FROM or h < QUIET_TO


def _days_text(days: float) -> str:
    return "کمتر از یک روز" if days < 1 else f"حدود {max(1, round(days))} روز"


def build_message(sub, fc: dict) -> str:
    title = html.escape(str(sub["plan_title"] or ""))
    return (
        f"{pe.HOURGLASS2} پیش‌بینی مصرف\n\n"
        f"با روند مصرف این چند روزت (حدود {fc['avg_gb']:.1f} گیگ در روز)، حجم سرویس «{title}» "
        f"{_days_text(fc['days'])} دیگه تموم میشه؛ قبل از اینکه مدتش تموم بشه.\n"
        "برای اینکه وسط کار قطع نشی، از همین حالا تمدیدش کن."
    )


async def smart_forecast_job(context):
    if _is_quiet_hour():
        return
    sent = 0
    for sub in db.get_all_active_subscriptions():
        try:
            if not sub["marzban_username"] or sub["ended_at"] or sub["plan_id"] == "trial" or sub["data_warning_sent"]:
                continue
            period = str(sub["expire_at"] or 0)
            if _already_sent(sub["sub_id"], "forecast", period):
                continue
            try:
                info = await panel.get_user(sub["marzban_username"], include_config=False)
            except PanelError:
                continue
            if info.get("status") != "active":
                continue
            fc = forecast(sub, info.get("data_limit") or 0, info.get("used_traffic") or 0)
            if not fc:
                continue
            _mark_sent(sub["sub_id"], "forecast", period)       # اول ثبت می‌کنیم: حتی اگه ارسال خطا بده، تکرار نشه
            try:
                await context.bot.send_message(
                    chat_id=sub["user_id"],
                    text=build_message(sub, fc),
                    reply_markup=data_warning_keyboard(sub["sub_id"]),
                    parse_mode="HTML",
                )
                sent += 1
            except Exception:
                logger.warning("ارسال پیش‌بینی مصرف سرویس #%s به کاربر %s ناموفق بود", sub["sub_id"], sub["user_id"])
        except Exception:
            logger.exception("بررسی پیش‌بینی مصرف سرویس #%s خطا داد", sub["sub_id"])
    if sent:
        logger.info("یادآوری هوشمند: %s پیام پیش‌بینی مصرف فرستاده شد.", sent)
