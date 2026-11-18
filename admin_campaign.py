"""
کمپین تخفیف زمان‌دار (فقط ادمین):

  /campaign     ← متن بنر + درصد تخفیف + مدت رو انتخاب می‌کنی. یه کد تخفیف همگانی (هر کاربر یه‌بار)
                  ساخته میشه و یه بنر طلایی با «شمارنده‌ی معکوس» بالای مینی‌اپ میاد. کاربر روی بنر
                  بزنه، کد موقع خرید خودکار اعمال میشه. (اختیاری: یه پیام هم برای همه‌ی کاربرا می‌ره.)
  /campaignend  ← کمپین رو زودتر تموم می‌کنه: بنر جمع میشه و کدش از کار می‌افته.

بعد از رسیدن مدت، بنر خودش از مینی‌اپ میره و کد هم منقضی میشه (انقضای کد = انقضای بنر).
"""
import asyncio
import html
import logging
import time

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

import database as db
from admin_banners import parse_banner_text, TITLE_MAX, BODY_MAX
from config import ADMIN_IDS

import theme
logger = logging.getLogger(__name__)

(WAITING_CAMP_TEXT, WAITING_CAMP_PERCENT, WAITING_CAMP_HOURS, WAITING_CAMP_CONFIRM) = range(50, 54)

CAMPAIGN_KIND = "campaign"
PERCENT_CHOICES = [10, 15, 20, 25, 30]
HOUR_CHOICES = [6, 12, 24, 48, 72]
AUDIENCE = "all"


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _buy_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("خرید سرویس", callback_data="menu:buy", style=theme.CTA)]]
    )


def _campaign_message(title: str, body, code: str, percent: int, hours: int) -> str:
    text = f"🎁 {html.escape(title)}"
    if body:
        text += f"\n\n{html.escape(body)}"
    text += (
        f"\n\nکد تخفیف {percent}٪: <code>{code}</code>\n"
        f"فقط تا {hours} ساعت دیگه معتبره و هر نفر یک‌بار می‌تونه ازش استفاده کنه؛ موقع خرید واردش کن."
    )
    return text


# ---------------- /campaign ----------------
async def campaign_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data["camp_draft"] = {}
    await update.message.reply_text(
        "🎁 کمپین تخفیف زمان‌دار\n\n"
        "متن بنر رو بفرست.\n"
        f"خط اول = عنوان (حداکثر {TITLE_MAX} کاراکتر)، خط دوم (اختیاری) = توضیح (حداکثر {BODY_MAX} کاراکتر).\n\n"
        "مثال:\nجشنواره‌ی آخر هفته\nروی همه‌ی پلن‌ها تخفیف ویژه\n\n"
        "برای لغو: /cancel"
    )
    return WAITING_CAMP_TEXT


async def receive_campaign_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = context.user_data.get("camp_draft")
    if draft is None:
        await update.message.reply_text("این عملیات دیگه معتبر نیست؛ دوباره /campaign رو بزن.")
        return ConversationHandler.END
    parsed = parse_banner_text(update.message.text)
    if isinstance(parsed, str):
        await update.message.reply_text(parsed)
        return WAITING_CAMP_TEXT
    draft["fa"] = parsed
    buttons = [InlineKeyboardButton(f"{p}٪", callback_data=f"camp:p:{p}") for p in PERCENT_CHOICES]
    await update.message.reply_text(
        "درصد تخفیف چند باشه؟",
        reply_markup=InlineKeyboardMarkup([buttons[:3], buttons[3:]]),
    )
    return WAITING_CAMP_PERCENT


async def handle_campaign_percent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get("camp_draft")
    if not draft or "fa" not in draft:
        await query.edit_message_text("این عملیات دیگه معتبر نیست؛ دوباره /campaign رو بزن.")
        return ConversationHandler.END
    try:
        percent = int(query.data.rsplit(":", 1)[1])
    except ValueError:
        percent = 0
    if percent not in PERCENT_CHOICES:
        await query.answer("درصد نامعتبره.", show_alert=True)
        return WAITING_CAMP_PERCENT
    draft["percent"] = percent
    buttons = [InlineKeyboardButton(f"{h} ساعت", callback_data=f"camp:h:{h}") for h in HOUR_CHOICES]
    await query.edit_message_text(
        "کمپین چند ساعت فعال باشه؟ (بعد از این مدت بنر خودش جمع میشه و کد منقضی میشه)",
        reply_markup=InlineKeyboardMarkup([buttons[:3], buttons[3:]]),
    )
    return WAITING_CAMP_HOURS


async def handle_campaign_hours(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get("camp_draft")
    if not draft or "percent" not in draft:
        await query.edit_message_text("این عملیات دیگه معتبر نیست؛ دوباره /campaign رو بزن.")
        return ConversationHandler.END
    try:
        hours = int(query.data.rsplit(":", 1)[1])
    except ValueError:
        hours = 0
    if hours not in HOUR_CHOICES:
        await query.answer("مدت نامعتبره.", show_alert=True)
        return WAITING_CAMP_HOURS
    draft["hours"] = hours

    count = len(db.get_audience_user_ids(AUDIENCE))
    title, body = draft["fa"]
    await query.edit_message_text(
        "پیش‌نمایش:\n\n"
        f"بنر: {title}" + (f"\n{body}" if body else "") + "\n"
        f"تخفیف: {draft['percent']}٪ · مدت: {hours} ساعت\n"
        "یک کد همگانی ساخته میشه (هر کاربر فقط یک‌بار می‌تونه ازش استفاده کنه).",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🖼 فقط بنر مینی‌اپ", callback_data="camp:go:banner", style=theme.NAV)],
                [InlineKeyboardButton(f"📣 بنر + پیام برای همه ({count} کاربر)", callback_data="camp:go:both", style=theme.CTA)],
                [InlineKeyboardButton("❌ لغو", callback_data="camp:go:no", style="danger")],
            ]
        ),
    )
    return WAITING_CAMP_CONFIRM


async def handle_campaign_go(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    mode = query.data.rsplit(":", 1)[1]
    draft = context.user_data.pop("camp_draft", None)

    if mode == "no" or not draft or not all(k in draft for k in ("fa", "percent", "hours")):
        await query.edit_message_text("لغو شد؛ چیزی ساخته یا ارسال نشد.")
        return ConversationHandler.END

    title, body = draft["fa"]
    percent, hours = draft["percent"], draft["hours"]
    try:
        # کد همگانی (max_uses=None)؛ «هر کاربر یک‌بار» رو خودِ validate_discount_code تضمین می‌کنه
        code = db.create_winback_code(percent, hours, prefix="SALE", max_uses=None)
    except Exception:
        logger.exception("ساخت کد کمپین ناموفق بود")
        await query.edit_message_text("ساخت کد تخفیف ناموفق بود؛ دوباره امتحان کن.")
        return ConversationHandler.END

    banner_id = db.create_banner(
        (title, body),
        theme="gold",
        action="shop",
        expires_at=int(time.time()) + hours * 3600,
        kind=CAMPAIGN_KIND,
        code=code,
    )

    if mode == "banner":
        await query.edit_message_text(
            f"✅ کمپین ساخته شد.\nکد: {code} ({percent}٪، {hours} ساعت)\nبنر #{banner_id} تو مینی‌اپ فعاله."
        )
        return ConversationHandler.END

    await query.edit_message_text(
        f"✅ کمپین ساخته شد (کد: {code}).\n⏳ در حال ارسال پیام... ممکنه چند دقیقه طول بکشه."
    )
    text = _campaign_message(title, body, code, percent, hours)
    sent, failed = 0, 0
    for uid in db.get_audience_user_ids(AUDIENCE):
        try:
            await context.bot.send_message(uid, text, reply_markup=_buy_keyboard(), parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)   # زیر محدودیت فلود تلگرام بمونیم
    await context.bot.send_message(
        update.effective_chat.id,
        f"✅ ارسال تموم شد.\nموفق: {sent}\nناموفق (بلاک/حذف حساب و...): {failed}\n\n"
        "برای تموم‌کردن زودتر کمپین: /campaignend",
    )
    return ConversationHandler.END


async def campaign_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("camp_draft", None)
    await update.message.reply_text("لغو شد.")
    return ConversationHandler.END


# ---------------- /campaignend ----------------
async def campaignend_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    active = db.count_active_banners_by_kind(CAMPAIGN_KIND)
    if active == 0:
        await update.message.reply_text("الان هیچ کمپین فعالی نداریم.")
        return
    await update.message.reply_text(
        f"{active} کمپین فعاله. تمومش کنم؟ (بنر جمع میشه و کد تخفیفش از کار می‌افته)",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ آره، تمومش کن", callback_data="campend:yes", style="danger")],
                [InlineKeyboardButton("لغو", callback_data="campend:no")],
            ]
        ),
    )


async def handle_campaignend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update.effective_user.id):
        return
    if query.data.split(":", 1)[1] != "yes":
        await query.edit_message_text("لغو شد.")
        return
    ended = db.end_campaigns()
    await query.edit_message_text(f"✅ {ended} کمپین تموم شد؛ بنر جمع و کد تخفیفش غیرفعال شد.")


def build_handlers():
    text = filters.TEXT & ~filters.COMMAND
    conv = ConversationHandler(
        entry_points=[CommandHandler("campaign", campaign_start)],
        states={
            WAITING_CAMP_TEXT: [MessageHandler(text, receive_campaign_text)],
            WAITING_CAMP_PERCENT: [CallbackQueryHandler(handle_campaign_percent, pattern=r"^camp:p:")],
            WAITING_CAMP_HOURS: [CallbackQueryHandler(handle_campaign_hours, pattern=r"^camp:h:")],
            WAITING_CAMP_CONFIRM: [CallbackQueryHandler(handle_campaign_go, pattern=r"^camp:go:")],
        },
        fallbacks=[CommandHandler("cancel", campaign_cancel)],
        per_message=False,
    )
    return [
        conv,
        CommandHandler("campaignend", campaignend_start),
        CallbackQueryHandler(handle_campaignend, pattern=r"^campend:"),
    ]
