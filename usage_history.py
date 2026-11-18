"""
تاریخچه‌ی مصرف روزانه‌ی سرویس‌ها (برای نمودار «مصرف ۷ روز اخیر» و «پیش‌بینی اتمام حجم» تو Mini App).

ایده: پنل فقط «مجموع مصرف تا الان» رو میده، نه مصرف هر روز. پس هر ۳۰ دقیقه مصرف
تجمعی هر سرویس رو ذخیره می‌کنیم و مصرف هر روز از تفاضل آخرین عدد امروز و آخرین عدد
دیروز حساب میشه. (شروع هر روز و پایان هر روز به وقت ایران حساب میشه.)

نکته‌ها:
- ماژول کاملاً مستقله: جدول خودش رو می‌سازه و فقط تو bot.py (جاب) و keep_alive.py (API) صدا زده میشه.
- با USAGE_HISTORY_ENABLED=false خاموش میشه (نمودار خالی میمونه).
- داده از لحظه‌ی فعال‌شدن شروع میشه؛ روزهای قبلش «نامشخص» (None) برگردونده میشن.
- اگه مصرف بعد از تمدید صفر بشه (عدد تجمعی کم بشه)، همون روز از اول حساب میشه.
"""
import asyncio
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import database as db
from panel_client import panel, PanelError

logger = logging.getLogger(__name__)

ENABLED = os.getenv("USAGE_HISTORY_ENABLED", "true").lower() in ("1", "true", "yes")
KEEP_DAYS = 45
CONCURRENCY = 4
GB = 1024 ** 3
_IRAN = timezone(timedelta(hours=3, minutes=30))

_table_ready = False
_last_prune_day = None


def _day_of(ts: float) -> str:
    return datetime.fromtimestamp(ts, _IRAN).strftime("%Y-%m-%d")


def _ensure_table():
    global _table_ready
    if _table_ready:
        return
    with db.get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_daily (
                sub_id INTEGER NOT NULL,
                day TEXT NOT NULL,
                start_bytes INTEGER NOT NULL,
                end_bytes INTEGER NOT NULL,
                PRIMARY KEY (sub_id, day)
            )
            """
        )
    _table_ready = True


def record(sub_id: int, used_bytes: int, now: float = None):
    """مصرف تجمعی فعلی رو برای امروز ذخیره میکنه (اولین عدد روز = شروع، آخرین = پایان)."""
    _ensure_table()
    day = _day_of(now if now is not None else time.time())
    used_bytes = max(0, int(used_bytes or 0))
    with db.get_conn() as conn:
        conn.execute(
            """
            INSERT INTO usage_daily (sub_id, day, start_bytes, end_bytes) VALUES (?, ?, ?, ?)
            ON CONFLICT(sub_id, day) DO UPDATE SET end_bytes = excluded.end_bytes
            """,
            (sub_id, day, used_bytes, used_bytes),
        )


def get_week(sub_id: int, now: float = None) -> dict:
    """
    ۷ روز آخر (قدیمی‌ترین ← امروز). هر روز: {"day": "YYYY-MM-DD", "bytes": عدد یا None}
    + avg_gb (میانگین روزهای دارای داده) و tracked_days (تعداد روزهای دارای داده).
    """
    _ensure_table()
    now = now if now is not None else time.time()
    days = [_day_of(now - i * 86400) for i in range(7, -1, -1)]   # ۸ روز: یکی اضافه برای مبنای روز اول
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT day, start_bytes, end_bytes FROM usage_daily WHERE sub_id = ? AND day >= ? AND day <= ?",
            (sub_id, days[0], days[-1]),
        ).fetchall()
    by_day = {r["day"]: (r["start_bytes"], r["end_bytes"]) for r in rows}

    out = []
    for i in range(1, len(days)):
        d = days[i]
        cur = by_day.get(d)
        if cur is None:
            out.append({"day": d, "bytes": None})
            continue
        prev = by_day.get(days[i - 1])
        base = prev[1] if prev is not None else cur[0]
        delta = cur[1] - base
        if delta < 0:                       # تمدید/ریست مصرف: از اول همون روز
            delta = max(0, cur[1] - cur[0])
        out.append({"day": d, "bytes": int(delta)})

    known = [x["bytes"] for x in out if x["bytes"] is not None]
    avg_gb = (sum(known) / len(known) / GB) if known else 0.0
    return {"days": out, "avg_gb": round(avg_gb, 4), "tracked_days": len(known)}


def _prune_once_a_day():
    global _last_prune_day
    today = _day_of(time.time())
    if _last_prune_day == today:
        return
    cutoff = _day_of(time.time() - KEEP_DAYS * 86400)
    with db.get_conn() as conn:
        conn.execute("DELETE FROM usage_daily WHERE day < ?", (cutoff,))
    _last_prune_day = today


async def _snapshot_one(sem, sub):
    async with sem:
        try:
            info = await panel.get_user(sub["marzban_username"], include_config=False)
        except PanelError:
            return                        # مشکل موقت پنل / سرویس حذف‌شده؛ دور بعد
        except Exception:
            logger.exception("ثبت مصرف سرویس #%s ناموفق بود", sub["sub_id"])
            return
        used = info.get("used_traffic")
        if used is None:
            return
        try:
            record(sub["sub_id"], used)
        except Exception:
            logger.exception("ذخیره‌ی مصرف سرویس #%s ناموفق بود", sub["sub_id"])


async def usage_history_job(context):
    if not ENABLED:
        return
    try:
        _ensure_table()
        _prune_once_a_day()
        subs = db.get_all_active_subscriptions()
    except Exception:
        logger.exception("خواندن لیست سرویس‌ها برای ثبت مصرف ناموفق بود")
        return
    sem = asyncio.Semaphore(CONCURRENCY)
    await asyncio.gather(*[_snapshot_one(sem, s) for s in subs])
