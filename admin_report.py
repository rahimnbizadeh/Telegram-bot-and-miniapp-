"""
گزارش صبحگاهی ادمین: هر روز ساعت ۰۸:۰۰ تهران یه پیام کوتاه با خلاصه‌ی «دیروز» (به وقت ایران)
برای همه‌ی ادمین‌ها می‌فرسته؛ و /report همین گزارش رو هر وقت خواستی می‌ده.

نکته‌ی مبلغ: «فروش سرویس» از روی قیمت پلنِ سفارش‌های تاییدشده‌ی خرید/تمدید و درصد تخفیفِ ثبت‌شده‌ی
همون سفارش حساب میشه (یعنی تقریبی؛ قیمت‌های خاص نماینده‌ها/تغییر قیمت‌های قدیمی دقیق لحاظ نمیشن).
«شارژ کیف پول» جمع مبلغ شارژهای تاییدشده‌ست.
"""
import logging
import time
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

import database as db
import premium_emoji as pe
import rich_messages as rm
import rich_screens as rs
from config import ADMIN_IDS, get_plan

logger = logging.getLogger(__name__)

_IRAN = timezone(timedelta(hours=3, minutes=30))


def _day_bounds(now: float, days_ago: int):
    """[شروع، پایان) روزِ «days_ago روز قبل» به وقت ایران، به‌صورت timestamp"""
    today = datetime.fromtimestamp(now, _IRAN).replace(hour=0, minute=0, second=0, microsecond=0)
    start = today - timedelta(days=days_ago)
    return int(start.timestamp()), int((start + timedelta(days=1)).timestamp()), start.strftime("%Y-%m-%d")


def _money(orders):
    """(فروش سرویس به تومان، تعداد خرید جدید، تعداد تمدید، جمع شارژ کیف پول، تعداد شارژ)"""
    revenue = new = renew = topup_sum = topup_n = 0
    for o in orders:
        if o["kind"] in ("new", "renew"):
            plan = get_plan(o["plan_id"]) if o["plan_id"] else None
            price = plan["price"] if plan else 0
            revenue += int(price * (100 - (o["discount_percent"] or 0)) / 100)
            if o["kind"] == "new":
                new += 1
            else:
                renew += 1
        elif o["kind"] == "topup":
            topup_sum += o["amount"] or 0
            topup_n += 1
    return revenue, new, renew, topup_sum, topup_n


def _delta(cur: int, prev: int) -> str:
    if prev <= 0:
        return ""
    pct = round((cur - prev) / prev * 100)
    if pct == 0:
        return " (مثل روز قبل)"
    return f" ({'↑' if pct > 0 else '↓'} {abs(pct)}٪ نسبت به روز قبل)"


def _report_values(now: float = None) -> dict:
    now = now if now is not None else time.time()
    s, e, label = _day_bounds(now, 1)
    ps, pe_, _ = _day_bounds(now, 2)
    cur, prev = db.get_report_data(s, e), db.get_report_data(ps, pe_)
    revenue, new, renew, topup_sum, topup_n = _money(cur["orders"])
    return {
        "label": label, "cur": cur, "revenue": revenue, "new": new, "renew": renew,
        "topup_sum": topup_sum, "topup_n": topup_n, "prev_revenue": _money(prev["orders"])[0],
    }


def build_report_rich(now: float = None) -> str:
    """همون گزارش به‌صورت جدول (پیام غنی، فارسی/راست‌به‌چپ)"""
    v = _report_values(now)
    cur = v["cur"]
    rows_money = [
        [rs._lbl(pe.PRICE, "فروش سرویس"), rm.Raw(str(rm.mark(f"{v['revenue']:,} تومان")) + _delta(v['revenue'], v['prev_revenue']))],
        ["خرید جدید / تمدید", f"{v['new']} / {v['renew']}"],
        [rs._lbl(pe.WALLET, "شارژ کیف پول"), f"{v['topup_sum']:,} تومان ({v['topup_n']} تراکنش)"],
        [rs._lbl(pe.ACCOUNT, "کاربر جدید"), str(cur["new_users"])],
        ["تست رایگان", str(cur["trials"])],
        ["پایان‌یافته / حذف‌شده", f"{cur['ended']} / {cur['deleted']}"],
    ]
    rows_now = [
        [rs._lbl(pe.MY_SERVICES, "سرویس پولی فعال"), str(cur["active_paid"])],
        ["نزدیک انقضا (۳ روز)", str(cur["expiring_3d"])],
        ["در مهلت تمدید", str(cur["in_grace"])],
        ["سفارش در انتظار", str(cur["pending_orders"])],
        ["تیکت باز", str(cur["open_tickets"])],
    ]
    return rm.document(
        rm.paragraph(rm.Raw(f"{pe.CLOCK} "), f"گزارش دیروز ({v['label']})"),
        rm.table(rows_money, rtl=True, row_headers=True),
        rm.paragraph("وضعیت الان"),
        rm.table(rows_now, rtl=True, row_headers=True),
    )


def build_report(now: float = None) -> str:
    v = _report_values(now)
    label, cur, revenue, new, renew = v["label"], v["cur"], v["revenue"], v["new"], v["renew"]
    topup_sum, topup_n, prev_revenue = v["topup_sum"], v["topup_n"], v["prev_revenue"]

    lines = [
        f"📈 گزارش دیروز ({label})",
        "",
        f"💰 فروش سرویس: {revenue:,} تومان{_delta(revenue, prev_revenue)}",
        f"   {new} خرید جدید · {renew} تمدید",
        f"👛 شارژ کیف پول: {topup_sum:,} تومان ({topup_n} تراکنش)",
        f"👤 کاربر جدید: {cur['new_users']} · 🎁 تست رایگان: {cur['trials']}",
        "",
        f"🧹 دیروز: {cur['ended']} سرویس پایان‌یافته · {cur['deleted']} سرویس حذف‌شده",
        "",
        "الان:",
        f"🟢 سرویس پولی فعال: {cur['active_paid']}",
        f"⏳ نزدیک انقضا (۳ روز): {cur['expiring_3d']} · در مهلت تمدید: {cur['in_grace']}",
        f"🧾 سفارش در انتظار: {cur['pending_orders']} · 🎫 تیکت باز: {cur['open_tickets']}",
    ]
    return "\n".join(lines)


async def daily_report_job(context: ContextTypes.DEFAULT_TYPE):
    """هر روز اجرا میشه؛ گزارش دیروز رو برای هر ادمین (حداکثر یک‌بار تو روز) می‌فرسته"""
    today = datetime.fromtimestamp(time.time(), _IRAN).strftime("%Y-%m-%d")
    try:
        text = build_report()
    except Exception:
        logger.exception("ساخت گزارش صبحگاهی ناموفق بود")
        return
    try:
        rich_html = build_report_rich() if rm.enabled() else None
    except Exception:
        logger.exception("ساخت گزارش غنی ناموفق بود؛ نسخه‌ی متنی فرستاده میشه")
        rich_html = None
    for admin_id in ADMIN_IDS:
        flag = f"admin_report_{today}"
        if db.has_user_flag(admin_id, flag):
            continue   # امروز برای این ادمین رفته (مثلاً بعد از ری‌استارت)
        try:
            await rm.send_rich_or_classic(context.bot, admin_id, rich_html, text, classic_parse_mode=None, rtl=True)
            db.set_user_flag(admin_id, flag)
        except Exception:
            logger.warning("ارسال گزارش صبحگاهی به ادمین %s ناموفق بود", admin_id)


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        text = build_report()
        rich_html = build_report_rich() if rm.enabled() else None
        await rm.send_rich_or_classic(
            context.bot, update.effective_chat.id, rich_html, text, classic_parse_mode=None, rtl=True
        )
    except Exception:
        logger.exception("ساخت گزارش ناموفق بود")
        await update.message.reply_text("ساخت گزارش ناموفق بود؛ لاگ بات رو ببین.")


def build_handlers():
    return [CommandHandler("report", report_command)]
