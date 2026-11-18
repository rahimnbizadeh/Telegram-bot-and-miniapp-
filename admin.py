import asyncio
import logging
import random
import string

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
from config import ADMIN_IDS, get_plan, RESELLER_PRICE_PER_GB_TOMAN
from panel_client import panel, PanelError
import premium_emoji as pe
from delivery import send_service_delivery, _plan_with_actual_gb
from i18n import t
from keyboards import rating_keyboard, ticket_answer_keyboard, ticket_closed_keyboard
from admin_banners import build_handlers as _banner_handlers
from admin_outage import build_handlers as _outage_handlers
from admin_campaign import build_handlers as _campaign_handlers
from admin_report import build_handlers as _report_handlers

import theme
logger = logging.getLogger(__name__)


def _is_rich_message(msg) -> bool:
    """
    «پیام غنی» تلگرام (Bot API 10.1: جدول، تیتر، لیست و ...) فیلد text نداره و محتواش تو فیلد
    rich_message میاد. نسخه‌ی python-telegram-bot ما این فیلد رو هنوز نمی‌شناسه، پس تو
    message.api_kwargs می‌افته؛ هر دو حالت (اگه کتابخونه بعداً اضافه‌ش کرد) چک میشه.
    """
    if getattr(msg, "rich_message", None):
        return True
    return bool((getattr(msg, "api_kwargs", None) or {}).get("rich_message"))


class _RichMessageFilter(filters.MessageFilter):
    def __init__(self):
        super().__init__(name="RichMessage")

    def filter(self, message) -> bool:
        return _is_rich_message(message)


RICH_MESSAGE = _RichMessageFilter()

WAITING_ADMIN_TICKET_REPLY = 1
WAITING_POST_CONTENT = 10
WAITING_POST_BUTTON_TEXT = 11
WAITING_POST_BUTTON_URL = 12
WAITING_DISCOUNT_CODE_NAME = 20
WAITING_DISCOUNT_PERCENT = 21
WAITING_DISCOUNT_MAX_USES = 22


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    text = (
        "📊 آمار ربات\n\n"
        f"👤 تعداد کل کاربران: {db.count_users()}\n"
        f"🕓 سفارش‌های در انتظار: {db.count_pending_orders()}\n"
        f"🧾 سفارش‌های ۲۴ ساعت اخیر: {db.count_orders_today()}\n"
    )
    await update.message.reply_text(text)


async def admin_resettrials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استفاده: /resettrials - تست رایگان همه‌ی کاربرا رو ریست می‌کنه (با تاییدیه)"""
    if not is_admin(update.effective_user.id):
        return
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ بله، ریست کن", callback_data="resettrials:yes"),
                InlineKeyboardButton("❌ انصراف", callback_data="resettrials:no"),
            ]
        ]
    )
    await update.message.reply_text(
        "⚠️ مطمئنی می‌خوای تست رایگان همه‌ی کاربرا رو ریست کنی؟\n"
        "بعد از این، همه (حتی کسایی که قبلاً گرفته بودن) می‌تونن دوباره تست رایگان بگیرن.",
        reply_markup=kb,
    )


async def handle_resettrials_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("فقط ادمین می‌تونه این کار رو انجام بده.", show_alert=True)
        return

    choice = query.data.split(":", 1)[1]
    await query.answer()

    if choice == "no":
        await query.edit_message_text("لغو شد؛ چیزی تغییر نکرد.")
        return

    count = db.reset_all_trials()
    await query.edit_message_text(f"✅ تست رایگان {count} کاربر ریست شد؛ همه می‌تونن دوباره بگیرن.")


# ==================== ارسال پست همگانی (Broadcast) ====================
async def admin_post_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استفاده: /post - شروع ساخت یه پست/اطلاعیه برای ارسال به همه‌ی کاربرا"""
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data.pop("post_draft", None)
    await update.message.reply_text(
        "📣 محتوای پستی که می‌خوای برای همه بفرستی رو الان ارسال کن.\n"
        "می‌تونی متن ساده، پیام غنی (جدول و ...)، یا عکس/ویدیو همراه با کپشن بفرستی.\n\n"
        "برای لغو: /cancel"
    )
    return WAITING_POST_CONTENT


async def receive_post_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    draft = {}

    if msg.photo:
        draft["kind"] = "photo"
        draft["file_id"] = msg.photo[-1].file_id
        draft["text"] = msg.caption or ""
        draft["entities"] = msg.caption_entities
    elif msg.video:
        draft["kind"] = "video"
        draft["file_id"] = msg.video.file_id
        draft["text"] = msg.caption or ""
        draft["entities"] = msg.caption_entities
    elif msg.text:
        draft["kind"] = "text"
        draft["text"] = msg.text
        draft["entities"] = msg.entities
    elif _is_rich_message(msg):
        # پیام غنی رو بازسازی نمی‌کنیم؛ خودِ پیام ادمین عیناً کپی میشه (copyMessage)
        # تا جدول، ایموجی پریمیوم و ظاهرش دقیقاً همونی بمونه که ادمین فرستاده.
        draft["kind"] = "rich"
        draft["from_chat_id"] = msg.chat_id
        draft["message_id"] = msg.message_id
        draft["text"] = ""
    else:
        await msg.reply_text("این نوع پیام پشتیبانی نمیشه؛ لطفا متن، پیام غنی، عکس یا ویدیو بفرست.")
        return WAITING_POST_CONTENT

    context.user_data["post_draft"] = draft

    await msg.reply_text("دکمه هم می‌خوای زیر این پست باشه؟", reply_markup=_post_button_menu_keyboard(draft))
    return WAITING_POST_CONTENT


async def receive_post_unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """هر نوع پیام دیگه‌ای تو مرحله‌ی محتوای پست (استیکر، فایل، ...): به‌جای سکوت، جواب میدیم."""
    msg = update.message
    keys = ", ".join(sorted((getattr(msg, "api_kwargs", None) or {}).keys())) or "-"
    logger.info("post: unsupported message type from admin; api_kwargs keys=%s", keys)
    await msg.reply_text(
        "این نوع پیام پشتیبانی نمیشه؛ لطفا متن، پیام غنی، عکس یا ویدیو بفرست.\n"
        f"(فیلدهای ناشناخته‌ی پیام: {keys})"
    )
    return WAITING_POST_CONTENT


MAX_POST_BUTTONS = 3

# پیش‌فرض‌های دکمه - دقیقاً همون متن/ایموجی/رنگ منوی اصلی ربات، تا پست هم
# همون حس حرفه‌ای و برندشده رو داشته باشه
POST_BUTTON_PRESETS = {
    "buy": ("خرید سرویس", "CART", "success", "menu:buy"),
    "trial": ("تست رایگان", "TRIAL", "danger", "menu:trial"),
    "myservices": ("سرویس‌های من", "MY_SERVICES", "success", "menu:myservices"),
    "wallet": ("کیف پول", "WALLET", "primary", "menu:wallet"),
    "account": ("حساب کاربری", "ACCOUNT", "primary", "menu:account"),
    "apps": ("آموزش و اپلیکیشن‌ها", "APPS", "primary", "menu:apps"),
    "referral": ("دعوت دوستان", "REFERRAL", None, "menu:referral"),
    "support": ("پشتیبانی", "SUPPORT", None, "menu:support"),
}


def _post_button_menu_keyboard(draft: dict) -> InlineKeyboardMarkup:
    buttons = draft.get("buttons", [])
    rows = []
    row = []
    for key, (text, icon_key, style, _target) in POST_BUTTON_PRESETS.items():
        btn_kwargs = {"callback_data": f"postbtn:{key}"}
        if pe.RAW.get(icon_key):
            btn_kwargs["icon_custom_emoji_id"] = pe.RAW[icon_key]
        if style:
            btn_kwargs["style"] = style
        row.append(InlineKeyboardButton(text, **btn_kwargs))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("🔗 دکمه با متن/لینک دلخواه", callback_data="postbtn:custom", style=theme.NAV)])
    if buttons:
        rows.append(
            [
                InlineKeyboardButton(
                    f"✅ اتمام و پیش‌نمایش ({len(buttons)} دکمه)", callback_data="postbtn:finish", style=theme.CTA
                )
            ]
        )
    else:
        rows.append([InlineKeyboardButton("❌ بدون دکمه", callback_data="postbtn:none", style="danger")])
    return InlineKeyboardMarkup(rows)


async def handle_postbtn_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]

    draft = context.user_data.get("post_draft")
    if not draft:
        await query.edit_message_text("این پست دیگه معتبر نیست؛ دوباره /post رو بزن.")
        return ConversationHandler.END

    draft.setdefault("buttons", [])

    if choice in POST_BUTTON_PRESETS:
        text, icon_key, style, target = POST_BUTTON_PRESETS[choice]
        draft["buttons"].append(
            {"text": text, "type": "callback", "target": target, "icon": icon_key, "style": style}
        )
        if len(draft["buttons"]) >= MAX_POST_BUTTONS:
            return await _show_post_preview(update, context)
        await query.edit_message_text(
            f"✅ دکمه‌ی «{text}» اضافه شد ({len(draft['buttons'])} از {MAX_POST_BUTTONS}).\n"
            "می‌خوای یه دکمه‌ی دیگه هم اضافه کنی؟",
            reply_markup=_post_button_menu_keyboard(draft),
        )
        return WAITING_POST_CONTENT

    if choice == "none":
        draft["buttons"] = []
        await query.edit_message_text("بدون دکمه ارسال میشه.")
        return await _show_post_preview(update, context)

    if choice == "finish":
        return await _show_post_preview(update, context)

    # custom
    await query.edit_message_text("متن دکمه رو بفرست (مثلاً: خرید از اینجا 🛍):")
    return WAITING_POST_BUTTON_TEXT


async def receive_post_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = context.user_data.get("post_draft")
    if not draft:
        await update.message.reply_text("این پست دیگه معتبر نیست؛ دوباره /post رو بزن.")
        return ConversationHandler.END
    context.user_data["pending_button_text"] = update.message.text.strip()
    await update.message.reply_text("حالا لینکی که با زدن دکمه باز بشه رو بفرست (باید با https:// یا http:// یا t.me/ شروع بشه):")
    return WAITING_POST_BUTTON_URL


async def receive_post_button_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = context.user_data.get("post_draft")
    if not draft:
        await update.message.reply_text("این پست دیگه معتبر نیست؛ دوباره /post رو بزن.")
        return ConversationHandler.END

    url = update.message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://") or url.startswith("t.me/") or url.startswith("https://t.me/")):
        await update.message.reply_text("این یه لینک معتبر نیست. باید با http(s):// یا t.me/ شروع بشه. دوباره بفرست:")
        return WAITING_POST_BUTTON_URL
    if url.startswith("t.me/"):
        url = "https://" + url

    text = context.user_data.pop("pending_button_text", "لینک")
    draft.setdefault("buttons", [])
    draft["buttons"].append({"text": text, "type": "url", "target": url, "icon": None, "style": None})

    if len(draft["buttons"]) >= MAX_POST_BUTTONS:
        return await _show_post_preview(update, context)

    await update.message.reply_text(
        f"✅ دکمه‌ی «{text}» اضافه شد ({len(draft['buttons'])} از {MAX_POST_BUTTONS}).\n"
        "می‌خوای یه دکمه‌ی دیگه هم اضافه کنی؟",
        reply_markup=_post_button_menu_keyboard(draft),
    )
    return WAITING_POST_CONTENT


def _build_post_keyboard(draft: dict):
    buttons = draft.get("buttons", [])
    if not buttons:
        return None
    rows = []
    for b in buttons:
        if b["type"] == "url":
            rows.append([InlineKeyboardButton(b["text"], url=b["target"], style=theme.NAV)])
        else:
            btn_kwargs = {"callback_data": b["target"]}
            if b.get("icon") and pe.RAW.get(b["icon"]):
                btn_kwargs["icon_custom_emoji_id"] = pe.RAW[b["icon"]]
            if b.get("style"):
                btn_kwargs["style"] = b["style"]
            rows.append([InlineKeyboardButton(b["text"], **btn_kwargs)])
    return InlineKeyboardMarkup(rows)


# گروه‌های مخاطب اطلاعیه؛ ترتیب نمایش = ترتیب database.AUDIENCE_ORDER
AUDIENCE_LABELS = {
    "all": "همه‌ی کاربران",
    "active": "دارندگان سرویس فعال",
    "expiring": "سرویس نزدیک انقضا (تا ۳ روز)",
    "ended": "سرویس پایان‌یافته (در مهلت تمدید)",
    "no_purchase": "بدون خرید (عضو یا تست‌گیرنده)",
}


def _post_audience_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for key in db.AUDIENCE_ORDER:
        count = len(db.get_audience_user_ids(key))
        if count == 0 and key != "all":
            continue  # گروه خالی دکمه نمی‌خواد
        rows.append(
            [
                InlineKeyboardButton(
                    f"✅ {AUDIENCE_LABELS[key]} ({count})",
                    callback_data=f"postconfirm:{key}",
                    style=theme.CTA if key == "all" else "primary",
                )
            ]
        )
    rows.append([InlineKeyboardButton("❌ لغو", callback_data="postconfirm:no", style="danger")])
    return InlineKeyboardMarkup(rows)


async def _show_post_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = context.user_data["post_draft"]
    kb_preview = _build_post_keyboard(draft)
    confirm_kb = _post_audience_keyboard()
    chat_id = update.effective_chat.id
    caption = draft.get("text", "")
    if draft["kind"] == "photo":
        await context.bot.send_photo(chat_id, draft["file_id"], caption=caption, reply_markup=kb_preview, caption_entities=draft.get("entities"))
    elif draft["kind"] == "video":
        await context.bot.send_video(chat_id, draft["file_id"], caption=caption, reply_markup=kb_preview, caption_entities=draft.get("entities"))
    elif draft["kind"] == "rich":
        await context.bot.copy_message(chat_id, draft["from_chat_id"], draft["message_id"], reply_markup=kb_preview)
    else:
        await context.bot.send_message(chat_id, caption, reply_markup=kb_preview, entities=draft.get("entities"))

    await context.bot.send_message(
        chat_id, "این پیش‌نمایش نهایی پسته. برای کدوم گروه ارسال بشه؟", reply_markup=confirm_kb
    )
    return WAITING_POST_CONTENT


async def handle_postconfirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data.split(":", 1)[1]

    draft = context.user_data.get("post_draft")
    if not draft:
        await query.edit_message_text("این پست دیگه معتبر نیست.")
        return ConversationHandler.END

    if choice == "no":
        context.user_data.pop("post_draft", None)
        await query.edit_message_text("لغو شد؛ چیزی ارسال نشد.")
        return ConversationHandler.END

    audience = "all" if choice == "yes" else choice   # «yes» = دکمه‌ی قدیمی «ارسال به همه»
    if audience not in AUDIENCE_LABELS:
        await query.edit_message_text("گروه مخاطب نامعتبره؛ دوباره /post رو بزن.")
        context.user_data.pop("post_draft", None)
        return ConversationHandler.END

    await query.edit_message_text(
        f"⏳ در حال ارسال برای «{AUDIENCE_LABELS[audience]}»... این ممکنه چند دقیقه طول بکشه."
    )

    user_ids = db.get_audience_user_ids(audience)
    kb = _build_post_keyboard(draft)
    caption = draft.get("text", "")
    sent, failed = 0, 0
    first_error = None

    for uid in user_ids:
        try:
            if draft["kind"] == "photo":
                await context.bot.send_photo(uid, draft["file_id"], caption=caption, reply_markup=kb, caption_entities=draft.get("entities"))
            elif draft["kind"] == "video":
                await context.bot.send_video(uid, draft["file_id"], caption=caption, reply_markup=kb, caption_entities=draft.get("entities"))
            elif draft["kind"] == "rich":
                await context.bot.copy_message(uid, draft["from_chat_id"], draft["message_id"], reply_markup=kb)
            else:
                await context.bot.send_message(uid, caption, reply_markup=kb, entities=draft.get("entities"))
            sent += 1
        except Exception as e:
            failed += 1
            if first_error is None:
                first_error = f"{type(e).__name__}: {e}"
                logger.warning("post broadcast: first failure for %s: %s", uid, first_error)
        await asyncio.sleep(0.05)  # زیر محدودیت فلود تلگرام بمونیم (~۲۰ پیام در ثانیه)

    context.user_data.pop("post_draft", None)
    await context.bot.send_message(
        update.effective_chat.id,
        f"✅ ارسال تموم شد. (مخاطب: {AUDIENCE_LABELS[audience]})\nموفق: {sent}\nناموفق (بلاک/حذف حساب و...): {failed}"
        + (f"\nنمونه‌ی اولین خطا: {first_error}" if first_error else ""),
    )
    return ConversationHandler.END


async def admin_post_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("post_draft", None)
    await update.message.reply_text("لغو شد.")
    return ConversationHandler.END


# ==================== کد تخفیف ====================
async def admin_newcode_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """استفاده: /newcode - شروع ساخت یه کد تخفیف درصدی جدید"""
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data.pop("newcode_draft", None)
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🎲 خودت یه کد تصادفی بساز", callback_data="newcode:random")]]
    )
    await update.message.reply_text(
        "اسم کد تخفیف رو بفرست (مثلاً: SUMMER20) - فقط حروف انگلیسی و عدد.\n"
        "یا از دکمه‌ی زیر بخواه خودم یکی بسازم.\n\n"
        "برای لغو: /cancel",
        reply_markup=kb,
    )
    return WAITING_DISCOUNT_CODE_NAME


async def handle_newcode_random(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
    context.user_data["newcode_draft"] = {"code": code}
    await query.edit_message_text(f"کد ساخته شد: {code}\n\nچند درصد تخفیف بده؟ (فقط عدد بین ۱ تا ۹۹)")
    return WAITING_DISCOUNT_PERCENT


async def receive_newcode_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = update.message.text.strip().upper()
    if not code.isalnum():
        await update.message.reply_text("اسم کد فقط باید حروف انگلیسی و عدد باشه (بدون فاصله/علامت). دوباره بفرست:")
        return WAITING_DISCOUNT_CODE_NAME
    if db.get_discount_code(code):
        await update.message.reply_text("این کد از قبل وجود داره. یه اسم دیگه بفرست:")
        return WAITING_DISCOUNT_CODE_NAME

    context.user_data["newcode_draft"] = {"code": code}
    await update.message.reply_text(f"کد: {code}\n\nچند درصد تخفیف بده؟ (فقط عدد بین ۱ تا ۹۹)")
    return WAITING_DISCOUNT_PERCENT


async def receive_newcode_percent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = context.user_data.get("newcode_draft")
    if not draft:
        await update.message.reply_text("این عملیات دیگه معتبر نیست؛ دوباره /newcode رو بزن.")
        return ConversationHandler.END

    text = update.message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 99):
        await update.message.reply_text("باید یه عدد بین ۱ تا ۹۹ باشه. دوباره بفرست:")
        return WAITING_DISCOUNT_PERCENT

    draft["percent"] = int(text)
    kb = InlineKeyboardMarkup(
        [[InlineKeyboardButton("♾ نامحدود (هر تعداد کاربر)", callback_data="newcode:unlimited")]]
    )
    await update.message.reply_text(
        "این کد حداکثر چندبار قابل‌استفاده باشه؟ (یه عدد بفرست، مثلاً 50)\n"
        "یا اگه محدودیتی نمی‌خوای، از دکمه‌ی زیر استفاده کن.",
        reply_markup=kb,
    )
    return WAITING_DISCOUNT_MAX_USES


async def handle_newcode_unlimited(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    draft = context.user_data.get("newcode_draft")
    if not draft:
        await query.edit_message_text("این عملیات دیگه معتبر نیست؛ دوباره /newcode رو بزن.")
        return ConversationHandler.END
    draft["max_uses"] = None
    return await _finalize_newcode(update, context)


async def receive_newcode_max_uses(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = context.user_data.get("newcode_draft")
    if not draft:
        await update.message.reply_text("این عملیات دیگه معتبر نیست؛ دوباره /newcode رو بزن.")
        return ConversationHandler.END

    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("باید یه عدد مثبت باشه. دوباره بفرست:")
        return WAITING_DISCOUNT_MAX_USES

    draft["max_uses"] = int(text)
    return await _finalize_newcode(update, context)


async def _finalize_newcode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = context.user_data.pop("newcode_draft")
    db.create_discount_code(draft["code"], draft["percent"], max_uses=draft.get("max_uses"))

    uses_label = "نامحدود" if draft.get("max_uses") is None else str(draft["max_uses"])
    text = (
        f"✅ کد تخفیف ساخته شد!\n\n"
        f"کد: {draft['code']}\n"
        f"درصد تخفیف: {draft['percent']}%\n"
        f"سقف استفاده: {uses_label}\n\n"
        "کاربرا موقع خرید، دکمه‌ی «کد تخفیف دارم» رو می‌زنن و این کد رو وارد می‌کنن."
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text)
    else:
        await update.message.reply_text(text)
    return ConversationHandler.END


async def admin_newcode_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("newcode_draft", None)
    await update.message.reply_text("لغو شد.")
    return ConversationHandler.END


async def admin_codes_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استفاده: /codes - لیست همه‌ی کدهای تخفیف با آمار و دکمه‌ی غیرفعال‌کردن"""
    if not is_admin(update.effective_user.id):
        return
    codes = db.list_discount_codes()
    if not codes:
        await update.message.reply_text("هنوز هیچ کد تخفیفی نساختی. با /newcode یکی بساز.")
        return

    for c in codes:
        status = "✅ فعال" if c["active"] else "❌ غیرفعال"
        uses_label = "نامحدود" if c["max_uses"] is None else str(c["max_uses"])
        text = (
            f"🎟 {c['code']}\n"
            f"{c['percent']}% تخفیف | استفاده‌شده: {c['used_count']} از {uses_label}\n"
            f"وضعیت: {status}"
        )
        kb = None
        if c["active"]:
            kb = InlineKeyboardMarkup(
                [[InlineKeyboardButton("غیرفعال کن", callback_data=f"deactivatecode:{c['code']}")]]
            )
        await update.message.reply_text(text, reply_markup=kb)


async def handle_deactivate_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("فقط ادمین می‌تونه این کار رو انجام بده.", show_alert=True)
        return
    await query.answer()
    code = query.data.split(":", 1)[1]
    db.set_discount_code_active(code, False)
    await query.edit_message_text(f"❌ کد {code} غیرفعال شد.")


async def handle_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("فقط ادمین می‌تونه این کار رو انجام بده.", show_alert=True)
        return

    order_id = int(query.data.split(":", 1)[1])
    order = db.get_order(order_id)

    if not order:
        await query.answer("سفارش پیدا نشد.", show_alert=True)
        return
    if order["status"] != "pending":
        await query.answer("این سفارش قبلا بررسی شده.", show_alert=True)
        return

    await query.answer("در حال پردازش...")

    # ---------- شارژ کیف پول ----------
    if order["kind"] == "topup":
        if not db.claim_order_approval(order_id, update.effective_user.id):
            await query.answer("این سفارش قبلا بررسی شده.", show_alert=True)
            return
        db.adjust_wallet_balance_logged(
            order["user_id"], order["amount"], "topup", f"شارژ کیف پول - سفارش #{order_id}"
        )

        await context.bot.send_message(
            chat_id=order["user_id"],
            text=(
                f"🎉 کیف پول شما با موفقیت شارژ شد!\n"
                f"مبلغ: {order['amount']:,} تومان\n"
                f"{pe.UP} موجودی جدید: {db.get_wallet_balance(order['user_id']):,} تومان"
            ),
            parse_mode="HTML",
        )
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n✅ تایید شد توسط ادمین"
        )
        return

    # ---------- خرید جدید / تمدید ----------
    plan = get_plan(order["plan_id"])
    if not plan:
        # پلن این سفارش دیگه تو لیست پلن‌های فعلی نیست (مثلا حذف/تغییر شده)
        await query.edit_message_caption(
            caption=query.message.caption
            + f"\n\n⚠️ پلن این سفارش (`{order['plan_id']}`) دیگه در دسترس نیست؛ نمیشه خودکار تایید کرد."
        )
        await query.answer("پلن این سفارش دیگه معتبر نیست.", show_alert=True)
        return
    is_renewal = order["kind"] == "renew" and order["renew_sub_id"]

    if is_renewal:
        sub = db.get_subscription(order["renew_sub_id"])
        if not sub:
            await query.edit_message_caption(
                caption=query.message.caption
                + "\n\n⚠️ سرویس اصلی این تمدید پیدا نشد (شاید حذف شده)؛ نمیشه خودکار تایید کرد."
            )
            await query.answer("سرویس مرتبط با این تمدید پیدا نشد.", show_alert=True)
            return

    # تایید اتمیک: دوبار زدن دکمه‌ی «تایید» نمی‌تونه دو سرویس بسازه؛ اگه خطا بشه سفارش برمی‌گرده به pending
    if not db.claim_order_approval(order_id, update.effective_user.id):
        await query.answer("این سفارش قبلا بررسی شده.", show_alert=True)
        return

    try:
        if is_renewal:
            result = await panel.modify_user(sub["marzban_username"], plan["days"], plan["gb"])
        else:
            custom_name = order["custom_name"] if "custom_name" in order.keys() else None
            username = panel.generate_username(prefix=custom_name) if custom_name else panel.generate_username()
            result = await panel.create_user(username, plan["days"], plan["gb"], display_name=custom_name)
    except PanelError as e:
        db.release_order_approval(order_id)
        await query.edit_message_caption(
            caption=query.message.caption + f"\n\n⚠️ خطا در پردازش سرویس:\n{e}"
        )
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=f"{pe.REJECT} متاسفانه در پردازش سرویس مشکلی پیش اومد، پشتیبانی به زودی بررسی می‌کنه.",
            parse_mode="HTML",
        )
        return
    except Exception as e:
        # هر خطای غیرمنتظره‌ی دیگه (نه فقط PanelError) رو هم می‌گیریم و نشون
        # می‌دیم، وگرنه دکمه‌ی تایید بی‌هیچ پیام یا واکنشی «هیچ‌کاری نمی‌کنه»
        # و سفارش هم pending می‌مونه بدون این‌که ادمین بفهمه چرا.
        logger.exception("خطای غیرمنتظره در تایید سفارش #%s", order_id)
        db.release_order_approval(order_id)
        await query.edit_message_caption(
            caption=query.message.caption + f"\n\n⚠️ خطای غیرمنتظره در پردازش سرویس:\n{e!r}"
        )
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=f"{pe.REJECT} متاسفانه در پردازش سرویس مشکلی پیش اومد، پشتیبانی به زودی بررسی می‌کنه.",
            parse_mode="HTML",
        )
        return

    expire_at = result.get("expire") or 0
    sub_link = result.get("subscription_url", "")

    db.set_order_status(order_id, "approved", update.effective_user.id)

    if order["discount_code"] if "discount_code" in order.keys() else None:
        db.record_discount_use(order["discount_code"], order["user_id"])

    if is_renewal:
        db.update_subscription_after_renew(
            sub["sub_id"], expire_at, plan["title"], plan["id"]
        )
        if sub_link:
            db.update_subscription_link(sub["sub_id"], sub_link)
        await send_service_delivery(
            context.bot, order["user_id"], _plan_with_actual_gb(plan, result), sub["marzban_username"],
            sub_link or sub["sub_link"], "تمدید", expire_at=expire_at, sub_id=sub["sub_id"],
            connection_link=result.get("connection_link", ""),
        )
    else:
        new_sub_id = db.create_subscription(
            user_id=order["user_id"],
            order_id=order_id,
            plan_id=plan["id"],
            marzban_username=username,
            plan_title=plan["title"],
            expire_at=expire_at,
            sub_link=sub_link,
        )
        await send_service_delivery(
            context.bot, order["user_id"], plan, username, sub_link,
            expire_at=expire_at, sub_id=new_sub_id, connection_link=result.get("connection_link", ""),
        )
        # نظرسنجی رضایت فقط برای خرید جدید (نه هر بار تمدید، که مزاحم میشه)
        buyer_lang = db.get_user_language(order["user_id"])
        await context.bot.send_message(
            chat_id=order["user_id"],
            text=t("rating_ask_purchase", buyer_lang),
            reply_markup=rating_keyboard("purchase", new_sub_id),
            parse_mode="HTML",
        )
        # پاداش زیرمجموعه‌گیری فقط برای اولین خرید تاییدشده‌ی کاربر
        db.maybe_reward_referrer(order["user_id"])

    await query.edit_message_caption(
        caption=query.message.caption + "\n\n✅ تایید شد توسط ادمین"
    )


async def handle_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("فقط ادمین می‌تونه این کار رو انجام بده.", show_alert=True)
        return

    order_id = int(query.data.split(":", 1)[1])
    order = db.get_order(order_id)

    if not order:
        await query.answer("سفارش پیدا نشد.", show_alert=True)
        return
    if order["status"] != "pending":
        await query.answer("این سفارش قبلا بررسی شده.", show_alert=True)
        return

    db.set_order_status(order_id, "rejected", update.effective_user.id)

    await context.bot.send_message(
        chat_id=order["user_id"],
        text=(
            f"{pe.REJECT} متاسفانه رسید پرداخت شما تایید نشد.\n"
            "لطفا از صحت مبلغ و شماره کارت مطمئن شو یا با پشتیبانی تماس بگیر."
        ),
        parse_mode="HTML",
    )

    await query.answer("سفارش رد شد.")
    await query.edit_message_caption(caption=query.message.caption + "\n\n❌ رد شد توسط ادمین")



def _original_text(query, fallback: str) -> str:
    """متن پیام اصلی؛ اگه پیام «غنی» باشه (message.text نداره) متن جایگزین برمی‌گردونه تا ادیت خطا نده"""
    return query.message.text or fallback

async def handle_reseller_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("فقط ادمین می‌تونه این کار رو انجام بده.", show_alert=True)
        return

    request_id = int(query.data.split(":", 1)[1])
    req = db.get_reseller_request(request_id)
    if not req:
        await query.answer("درخواست پیدا نشد.", show_alert=True)
        return
    if req["status"] != "pending":
        await query.answer("این درخواست قبلا بررسی شده.", show_alert=True)
        return

    db.set_reseller(req["user_id"], True)
    db.set_reseller_request_status(request_id, "approved")

    lang = db.get_user_language(req["user_id"])
    try:
        await context.bot.send_message(
            chat_id=req["user_id"],
            text=t("reseller_approved_message", lang, icon=pe.RESELLER, price=RESELLER_PRICE_PER_GB_TOMAN),
            parse_mode="HTML",
        )
    except Exception:
        logger.warning("اطلاع‌رسانی تایید نمایندگی به کاربر %s ناموفق بود", req["user_id"])

    await query.answer("نماینده شد.")
    await query.edit_message_text(_original_text(query, f"درخواست نمایندگی #{request_id}") + "\n\n✅ تایید و به نمایندگی ارتقا یافت")


async def handle_reseller_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("فقط ادمین می‌تونه این کار رو انجام بده.", show_alert=True)
        return

    request_id = int(query.data.split(":", 1)[1])
    req = db.get_reseller_request(request_id)
    if not req:
        await query.answer("درخواست پیدا نشد.", show_alert=True)
        return
    if req["status"] != "pending":
        await query.answer("این درخواست قبلا بررسی شده.", show_alert=True)
        return

    db.set_reseller_request_status(request_id, "rejected")

    lang = db.get_user_language(req["user_id"])
    try:
        await context.bot.send_message(
            chat_id=req["user_id"], text=t("reseller_rejected_message", lang), parse_mode="HTML",
        )
    except Exception:
        logger.warning("اطلاع‌رسانی رد نمایندگی به کاربر %s ناموفق بود", req["user_id"])

    await query.answer("درخواست رد شد.")
    await query.edit_message_text(_original_text(query, f"درخواست نمایندگی #{request_id}") + "\n\n❌ رد شد توسط ادمین")


async def ask_ticket_reply_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("فقط ادمین می‌تونه این کار رو انجام بده.", show_alert=True)
        return ConversationHandler.END

    ticket_id = int(query.data.split(":", 1)[1])
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        await query.answer("تیکت پیدا نشد.", show_alert=True)
        return ConversationHandler.END

    context.user_data["admin_reply_ticket_id"] = ticket_id
    await query.answer()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"✏️ پاسخت رو برای تیکت #{ticket_id} بفرست:",
    )
    return WAITING_ADMIN_TICKET_REPLY


async def receive_ticket_reply_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ticket_id = context.user_data.get("admin_reply_ticket_id")
    if not ticket_id:
        return ConversationHandler.END

    ticket = db.get_ticket(ticket_id)
    if not ticket:
        await update.message.reply_text("تیکت پیدا نشد.")
        return ConversationHandler.END

    reply_text = update.message.text.strip()
    db.add_ticket_message(ticket_id, "admin", reply_text)
    db.set_ticket_status(ticket_id, "answered")

    await context.bot.send_message(
        chat_id=ticket["user_id"],
        text=f"{pe.SUPPORT} پاسخ پشتیبانی به تیکت #{ticket_id}:\n\n{pe.esc(reply_text)}",
        parse_mode="HTML",
        reply_markup=ticket_answer_keyboard(ticket_id),
    )
    await update.message.reply_text(f"✅ پاسخ برای تیکت #{ticket_id} ارسال شد.")
    context.user_data.pop("admin_reply_ticket_id", None)
    return ConversationHandler.END


async def handle_ticket_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("فقط ادمین می‌تونه این کار رو انجام بده.", show_alert=True)
        return

    ticket_id = int(query.data.split(":", 1)[1])
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        await query.answer("تیکت پیدا نشد.", show_alert=True)
        return

    db.set_ticket_status(ticket_id, "closed")
    await query.answer("تیکت بسته شد.")
    # دکمه‌های پیام ادمین رو برمی‌داریم تا تیکتِ بسته‌شده دوباره بسته/جواب داده نشه
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=ticket["user_id"],
        text=f"🔒 تیکت #{ticket_id} توسط پشتیبانی بسته شد.\nاگه هنوز مشکلی داری، یه تیکت جدید ثبت کن.",
        reply_markup=ticket_closed_keyboard(),
    )
    try:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=f"✅ تیکت #{ticket_id} بسته شد."
        )
    except Exception:
        pass


def build_handlers():
    ticket_reply_admin_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_ticket_reply_admin, pattern=r"^ticketreply_admin:"),
        ],
        states={
            WAITING_ADMIN_TICKET_REPLY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticket_reply_admin)
            ],
        },
        fallbacks=[],
        per_message=False,
    )

    post_conv = ConversationHandler(
        entry_points=[CommandHandler("post", admin_post_start)],
        states={
            WAITING_POST_CONTENT: [
                CallbackQueryHandler(handle_postbtn_choice, pattern=r"^postbtn:"),
                CallbackQueryHandler(handle_postconfirm, pattern=r"^postconfirm:"),
                MessageHandler(
                    (filters.TEXT | filters.PHOTO | filters.VIDEO | RICH_MESSAGE) & ~filters.COMMAND,
                    receive_post_content,
                ),
                MessageHandler(filters.ALL & ~filters.COMMAND, receive_post_unsupported),
            ],
            WAITING_POST_BUTTON_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_post_button_text)
            ],
            WAITING_POST_BUTTON_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_post_button_url)
            ],
        },
        fallbacks=[CommandHandler("cancel", admin_post_cancel)],
        per_message=False,
    )

    newcode_conv = ConversationHandler(
        entry_points=[CommandHandler("newcode", admin_newcode_start)],
        states={
            WAITING_DISCOUNT_CODE_NAME: [
                CallbackQueryHandler(handle_newcode_random, pattern=r"^newcode:random$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_newcode_name),
            ],
            WAITING_DISCOUNT_PERCENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_newcode_percent)
            ],
            WAITING_DISCOUNT_MAX_USES: [
                CallbackQueryHandler(handle_newcode_unlimited, pattern=r"^newcode:unlimited$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_newcode_max_uses),
            ],
        },
        fallbacks=[CommandHandler("cancel", admin_newcode_cancel)],
        per_message=False,
    )

    return [
        CommandHandler("stats", admin_stats),
        CommandHandler("resettrials", admin_resettrials),
        CallbackQueryHandler(handle_resettrials_confirm, pattern=r"^resettrials:"),
        post_conv,
        newcode_conv,
        CommandHandler("codes", admin_codes_list),
        CallbackQueryHandler(handle_deactivate_code, pattern=r"^deactivatecode:"),
        CallbackQueryHandler(handle_approve, pattern=r"^approve:"),
        CallbackQueryHandler(handle_reject, pattern=r"^reject:"),
        CallbackQueryHandler(handle_reseller_approve, pattern=r"^resellerapprove:"),
        CallbackQueryHandler(handle_reseller_reject, pattern=r"^resellerreject:"),
        ticket_reply_admin_conv,
        CallbackQueryHandler(handle_ticket_close, pattern=r"^ticketclose:"),
        *_banner_handlers(),
        *_outage_handlers(),
        *_campaign_handlers(),
        *_report_handlers(),
    ]
