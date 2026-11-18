"""
اطلاعیه‌ی اختلال (فقط ادمین):

  /outage     ← اعلام اختلال: متن رو می‌نویسی، مدت نمایش بنر رو انتخاب می‌کنی، و با یه تایید
                 هم پیام برای کاربرای دارای سرویس فعال می‌ره، هم یه بنر قرمز بالای مینی‌اپ
                 میاد که بعد از مدت انتخاب‌شده خودش جمع میشه.
  /outageend  ← پایان اختلال: بنر جمع میشه و (اختیاری) پیام «اختلال برطرف شد» می‌ره.

بنر اختلال با نوع (kind) 'outage' ذخیره میشه تا /outageend فقط همین‌ها رو جمع کنه و به
بنرهای تبلیغاتی دست نزنه.
"""
import asyncio
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

WAITING_OUTAGE_TEXT, WAITING_OUTAGE_HOURS, WAITING_OUTAGE_CONFIRM = range(40, 43)

OUTAGE_KIND = "outage"
HOUR_CHOICES = [2, 6, 12, 24]
AUDIENCE = "active"   # پیام اختلال فقط برای کسایی میره که سرویس فعال دارن


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("پشتیبانی", callback_data="menu:support", style=theme.NAV)]]
    )


def _outage_message(title: str, body) -> str:
    return f"⚠️ {title}" + (f"\n\n{body}" if body else "")


async def _send_to_users(bot, user_ids, text: str, reply_markup=None):
    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text, reply_markup=reply_markup)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # زیر محدودیت فلود تلگرام بمونیم
    return sent, failed


# ---------------- /outage ----------------
async def outage_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data["outage_draft"] = {}
    await update.message.reply_text(
        "⚠️ اعلام اختلال\n\n"
        "متن اطلاعیه رو بفرست. همین متن هم برای کاربرا پیام میشه، هم بنر بالای مینی‌اپ.\n"
        f"خط اول = عنوان (حداکثر {TITLE_MAX} کاراکتر)، خط دوم (اختیاری) = توضیح (حداکثر {BODY_MAX} کاراکتر).\n\n"
        "مثال:\nاختلال موقت روی بعضی اپراتورها\nدر حال رفع هستیم؛ تا اون موقع یه سرور دیگه رو امتحان کن.\n\n"
        "برای لغو: /cancel"
    )
    return WAITING_OUTAGE_TEXT


async def receive_outage_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = context.user_data.get("outage_draft")
    if draft is None:
        await update.message.reply_text("این عملیات دیگه معتبر نیست؛ دوباره /outage رو بزن.")
        return ConversationHandler.END
    parsed = parse_banner_text(update.message.text)
    if isinstance(parsed, str):
        await update.message.reply_text(parsed)
        return WAITING_OUTAGE_TEXT
    draft["fa"] = parsed

    buttons = [
        InlineKeyboardButton(f"{h} ساعت", callback_data=f"outage:h:{h}") for h in HOUR_CHOICES
    ]
    await update.message.reply_text(
        "بنر چند ساعت تو مینی‌اپ بمونه؟ (بعد از این مدت خودش جمع میشه؛ هر وقت اختلال برطرف شد با /outageend زودتر هم می‌تونی جمعش کنی)",
        reply_markup=InlineKeyboardMarkup([buttons[:2], buttons[2:]]),
    )
    return WAITING_OUTAGE_HOURS


async def handle_outage_hours(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get("outage_draft")
    if not draft or "fa" not in draft:
        await query.edit_message_text("این عملیات دیگه معتبر نیست؛ دوباره /outage رو بزن.")
        return ConversationHandler.END
    try:
        hours = int(query.data.rsplit(":", 1)[1])
    except ValueError:
        hours = 0
    if hours not in HOUR_CHOICES:
        await query.answer("مدت نامعتبره.", show_alert=True)
        return WAITING_OUTAGE_HOURS
    draft["hours"] = hours

    count = len(db.get_audience_user_ids(AUDIENCE))
    title, body = draft["fa"]
    await query.edit_message_text(
        "پیش‌نمایش پیام:\n\n"
        f"{_outage_message(title, body)}\n\n"
        f"بنر قرمز مینی‌اپ: {hours} ساعت\n"
        f"پیام برای {count} کاربر دارای سرویس فعال ارسال میشه.",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(f"📣 ارسال پیام + بنر ({count} کاربر)", callback_data="outage:go:both", style=theme.CTA)],
                [InlineKeyboardButton("🖼 فقط بنر (بدون پیام)", callback_data="outage:go:banner", style=theme.NAV)],
                [InlineKeyboardButton("❌ لغو", callback_data="outage:go:no", style="danger")],
            ]
        ),
    )
    return WAITING_OUTAGE_CONFIRM


async def handle_outage_go(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    mode = query.data.rsplit(":", 1)[1]
    draft = context.user_data.pop("outage_draft", None)

    if mode == "no" or not draft or "fa" not in draft or "hours" not in draft:
        await query.edit_message_text("لغو شد؛ چیزی ارسال یا ساخته نشد.")
        return ConversationHandler.END

    title, body = draft["fa"]
    banner_id = db.create_banner(
        (title, body),
        theme="red",
        action="support",
        expires_at=int(time.time()) + draft["hours"] * 3600,
        kind=OUTAGE_KIND,
    )

    if mode == "banner":
        await query.edit_message_text(f"✅ بنر اختلال ساخته شد (#{banner_id}) و {draft['hours']} ساعت تو مینی‌اپ می‌مونه.")
        return ConversationHandler.END

    await query.edit_message_text(
        f"✅ بنر اختلال ساخته شد (#{banner_id}).\n⏳ در حال ارسال پیام... ممکنه چند دقیقه طول بکشه."
    )
    user_ids = db.get_audience_user_ids(AUDIENCE)
    sent, failed = await _send_to_users(context.bot, user_ids, _outage_message(title, body), _support_keyboard())
    await context.bot.send_message(
        update.effective_chat.id,
        f"✅ ارسال تموم شد.\nموفق: {sent}\nناموفق (بلاک/حذف حساب و...): {failed}\n\n"
        "وقتی اختلال برطرف شد، /outageend رو بزن.",
    )
    return ConversationHandler.END


async def outage_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("outage_draft", None)
    await update.message.reply_text("لغو شد.")
    return ConversationHandler.END


# ---------------- /outageend ----------------
async def outageend_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    active = db.count_active_banners_by_kind(OUTAGE_KIND)
    if active == 0:
        await update.message.reply_text("الان هیچ بنر اختلال فعالی نداریم.")
        return
    count = len(db.get_audience_user_ids(AUDIENCE))
    await update.message.reply_text(
        f"{active} بنر اختلال فعاله. جمعش کنم؟",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(f"✅ جمع کردن + پیام «برطرف شد» ({count} کاربر)", callback_data="outageend:notify", style=theme.CTA)],
                [InlineKeyboardButton("🖼 فقط جمع کردن بنر", callback_data="outageend:quiet", style=theme.NAV)],
                [InlineKeyboardButton("❌ لغو", callback_data="outageend:no", style="danger")],
            ]
        ),
    )


async def handle_outageend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer()
        return
    await query.answer()
    mode = query.data.split(":", 1)[1]
    if mode == "no":
        await query.edit_message_text("لغو شد.")
        return

    ended = db.deactivate_banners_by_kind(OUTAGE_KIND)
    if mode == "quiet":
        await query.edit_message_text(f"✅ {ended} بنر اختلال جمع شد.")
        return

    await query.edit_message_text(f"✅ {ended} بنر اختلال جمع شد.\n⏳ در حال ارسال پیام «برطرف شد»...")
    user_ids = db.get_audience_user_ids(AUDIENCE)
    sent, failed = await _send_to_users(
        context.bot,
        user_ids,
        "✅ اختلال برطرف شد.\nاگه هنوز مشکلی داری، از بخش «پشتیبانی» بهمون بگو.",
        _support_keyboard(),
    )
    await context.bot.send_message(
        update.effective_chat.id, f"✅ ارسال تموم شد.\nموفق: {sent}\nناموفق: {failed}"
    )


def build_handlers():
    text = filters.TEXT & ~filters.COMMAND
    conv = ConversationHandler(
        entry_points=[CommandHandler("outage", outage_start)],
        states={
            WAITING_OUTAGE_TEXT: [MessageHandler(text, receive_outage_text)],
            WAITING_OUTAGE_HOURS: [CallbackQueryHandler(handle_outage_hours, pattern=r"^outage:h:")],
            WAITING_OUTAGE_CONFIRM: [CallbackQueryHandler(handle_outage_go, pattern=r"^outage:go:")],
        },
        fallbacks=[CommandHandler("cancel", outage_cancel)],
        per_message=False,
    )
    return [
        conv,
        CommandHandler("outageend", outageend_start),
        CallbackQueryHandler(handle_outageend, pattern=r"^outageend:"),
    ]
