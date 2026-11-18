"""
مدیریت بنرهای اعلان مینی‌اپ از داخل بات (فقط ادمین):

  /newbanner  ← ساخت بنر جدید: متن فارسی، انگلیسی و روسی، رنگ، دکمه‌ی اقدام و مدت نمایش
  /banners    ← لیست بنرها با دکمه‌ی فعال/غیرفعال و حذف

بنرهای فعال بالای صفحه‌ی اصلی مینی‌اپ (به‌صورت اسلایدر خودکار) نشون داده میشن.
"""
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
from config import ADMIN_IDS

(
    WAITING_BANNER_FA,
    WAITING_BANNER_EN,
    WAITING_BANNER_RU,
    WAITING_BANNER_THEME,
    WAITING_BANNER_ACTION,
    WAITING_BANNER_URL,
    WAITING_BANNER_DAYS,
) = range(30, 37)

TITLE_MAX = 60
BODY_MAX = 120

THEMES = [("gold", "🟡 طلایی"), ("blue", "🔵 آبی"), ("green", "🟢 سبز"), ("violet", "🟣 بنفش"), ("red", "🔴 قرمز")]
THEME_LABEL = dict(THEMES)
ACTIONS = [
    ("none", "بدون دکمه"), ("shop", "خرید سرویس"), ("trial", "تست رایگان"), ("wallet", "کیف پول"),
    ("loyalty", "باشگاه مشتریان"), ("referral", "دعوت دوستان"), ("support", "پشتیبانی"),
    ("apps", "آموزش اتصال"), ("url", "لینک بیرونی"),
]
ACTION_LABEL = dict(ACTIONS)

_FORMAT_HELP = (
    f"قالب: خط اول = عنوان (حداکثر {TITLE_MAX} کاراکتر)\n"
    f"خط دوم (اختیاری) = توضیح کوتاه (حداکثر {BODY_MAX} کاراکتر)"
)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def parse_banner_text(text: str):
    """(عنوان، توضیح) یا یه پیام خطا (str)"""
    lines = [ln.strip() for ln in (text or "").strip().split("\n") if ln.strip()]
    if not lines:
        return "متن خالیه. دوباره بفرست:"
    title, body = lines[0], " ".join(lines[1:]) if len(lines) > 1 else None
    if len(title) > TITLE_MAX:
        return f"عنوان از {TITLE_MAX} کاراکتر بلندتره ({len(title)}). کوتاه‌ترش کن و دوباره بفرست:"
    if body and len(body) > BODY_MAX:
        return f"توضیح از {BODY_MAX} کاراکتر بلندتره ({len(body)}). کوتاه‌ترش کن و دوباره بفرست:"
    return title, body


def _kb(rows):
    return InlineKeyboardMarkup(rows)


def _chunk(buttons, n):
    return [buttons[i:i + n] for i in range(0, len(buttons), n)]


async def _reply(update: Update, text: str, reply_markup=None):
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)


# ---------------- ساخت بنر ----------------
async def newbanner_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data["banner_draft"] = {}
    await update.message.reply_text(
        "🖼 ساخت بنر جدید برای مینی‌اپ\n\n"
        "اول متن «فارسی» بنر رو بفرست.\n" + _FORMAT_HELP + "\n\nبرای لغو: /cancel"
    )
    return WAITING_BANNER_FA


async def _need_draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get("banner_draft")
    if draft is None:
        await _reply(update, "این عملیات دیگه معتبر نیست؛ دوباره /newbanner رو بزن.")
    return draft


async def receive_banner_fa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = await _need_draft(update, context)
    if draft is None:
        return ConversationHandler.END
    parsed = parse_banner_text(update.message.text)
    if isinstance(parsed, str):
        await update.message.reply_text(parsed)
        return WAITING_BANNER_FA
    draft["fa"] = parsed
    await update.message.reply_text(
        "همین متن رو حالا به «انگلیسی» بفرست (با همون قالب).\n"
        "اگه ترجمه‌ش رو نداری، رد کن تا کاربرای انگلیسی هم متن فارسی رو ببینن.",
        reply_markup=_kb([[InlineKeyboardButton("رد کردن", callback_data="banner:skip_en")]]),
    )
    return WAITING_BANNER_EN


async def receive_banner_en(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = await _need_draft(update, context)
    if draft is None:
        return ConversationHandler.END
    if update.callback_query:
        await update.callback_query.answer()
        draft["en"] = None
    else:
        text = update.message.text.strip()
        if text in ("رد", "skip", "-"):
            draft["en"] = None
        else:
            parsed = parse_banner_text(text)
            if isinstance(parsed, str):
                await update.message.reply_text(parsed)
                return WAITING_BANNER_EN
            draft["en"] = parsed
    await _reply(
        update,
        "حالا متن «روسی» رو بفرست (یا رد کن).",
        _kb([[InlineKeyboardButton("رد کردن", callback_data="banner:skip_ru")]]),
    )
    return WAITING_BANNER_RU


async def receive_banner_ru(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = await _need_draft(update, context)
    if draft is None:
        return ConversationHandler.END
    if update.callback_query:
        await update.callback_query.answer()
        draft["ru"] = None
    else:
        text = update.message.text.strip()
        if text in ("رد", "skip", "-"):
            draft["ru"] = None
        else:
            parsed = parse_banner_text(text)
            if isinstance(parsed, str):
                await update.message.reply_text(parsed)
                return WAITING_BANNER_RU
            draft["ru"] = parsed
    rows = _chunk([InlineKeyboardButton(label, callback_data=f"banner:theme:{key}") for key, label in THEMES], 3)
    await _reply(update, "رنگ بنر رو انتخاب کن:", _kb(rows))
    return WAITING_BANNER_THEME


async def handle_banner_theme(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    draft = await _need_draft(update, context)
    if draft is None:
        return ConversationHandler.END
    draft["theme"] = query.data.split(":")[2]
    rows = _chunk([InlineKeyboardButton(label, callback_data=f"banner:act:{key}") for key, label in ACTIONS], 2)
    await query.edit_message_text(
        "دکمه‌ی اقدام بنر چی باشه؟ (کاربر با زدنش به همون بخش مینی‌اپ میره)", reply_markup=_kb(rows)
    )
    return WAITING_BANNER_ACTION


async def handle_banner_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    draft = await _need_draft(update, context)
    if draft is None:
        return ConversationHandler.END
    action = query.data.split(":")[2]
    draft["action"] = None if action == "none" else action
    if action == "url":
        await query.edit_message_text("آدرس لینک رو بفرست (باید با https:// شروع بشه):")
        return WAITING_BANNER_URL
    return await _ask_days(update)


async def receive_banner_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = await _need_draft(update, context)
    if draft is None:
        return ConversationHandler.END
    url = update.message.text.strip()
    if not url.lower().startswith("https://") or " " in url or len(url) > 500:
        await update.message.reply_text("آدرس معتبر نیست؛ باید با https:// شروع بشه و فاصله نداشته باشه. دوباره بفرست:")
        return WAITING_BANNER_URL
    draft["url"] = url
    return await _ask_days(update)


async def _ask_days(update: Update) -> int:
    await _reply(
        update,
        "چند روز نمایش داده بشه؟ (یه عدد بین ۱ تا ۳۶۵ بفرست)\nیا اگه انقضا نمی‌خوای، دکمه‌ی زیر رو بزن.",
        _kb([[InlineKeyboardButton("♾ بدون انقضا", callback_data="banner:days:none")]]),
    )
    return WAITING_BANNER_DAYS


async def receive_banner_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = await _need_draft(update, context)
    if draft is None:
        return ConversationHandler.END
    if update.callback_query:
        await update.callback_query.answer()
        draft["days"] = None
    else:
        text = update.message.text.strip()
        if not text.isdigit() or not (1 <= int(text) <= 365):
            await update.message.reply_text("باید یه عدد بین ۱ تا ۳۶۵ باشه. دوباره بفرست:")
            return WAITING_BANNER_DAYS
        draft["days"] = int(text)
    return await _finalize(update, context)


async def _finalize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    draft = context.user_data.pop("banner_draft")
    expires_at = int(time.time()) + draft["days"] * 86400 if draft.get("days") else None
    banner_id = db.create_banner(
        draft["fa"], draft.get("en"), draft.get("ru"), theme=draft["theme"],
        action=draft.get("action"), url=draft.get("url"), expires_at=expires_at,
    )
    await _reply(
        update,
        f"✅ بنر #{banner_id} ساخته شد و به‌زودی بالای صفحه‌ی اصلی مینی‌اپ نشون داده میشه.\n\n"
        + _summary(db.get_banner(banner_id))
        + "\n\nمدیریت: /banners",
    )
    return ConversationHandler.END


async def newbanner_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("banner_draft", None)
    await update.message.reply_text("لغو شد.")
    return ConversationHandler.END


# ---------------- لیست و مدیریت ----------------
def _summary(b) -> str:
    now = int(time.time())
    if b["expires_at"] and b["expires_at"] <= now:
        status = "⌛ منقضی‌شده"
    else:
        status = "✅ فعال" if b["active"] else "⏸ غیرفعال"
    if b["expires_at"] and b["expires_at"] > now:
        left = max(1, round((b["expires_at"] - now) / 86400))
        expiry = f"{left} روز دیگه"
    else:
        expiry = "بدون انقضا" if not b["expires_at"] else "-"
    langs = " ".join(
        f"{code} {'✓' if b[f'title_{key}'] else '✗'}" for code, key in (("FA", "fa"), ("EN", "en"), ("RU", "ru"))
    )
    action = ACTION_LABEL.get(b["action"] or "none", b["action"])
    if b["action"] == "url" and b["url"]:
        action += f" ({b['url']})"
    lines = [
        f"🖼 بنر #{b['banner_id']} | {THEME_LABEL.get(b['theme'], b['theme'])} | {status}",
        f"عنوان: {b['title_fa']}",
    ]
    if b["body_fa"]:
        lines.append(f"توضیح: {b['body_fa']}")
    lines += [f"دکمه: {action}", f"انقضا: {expiry}", f"زبان‌ها: {langs}"]
    return "\n".join(lines)


async def banners_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    banners = db.list_banners()
    if not banners:
        await update.message.reply_text("هنوز هیچ بنری نساختی. با /newbanner یکی بساز.")
        return
    for b in banners:
        toggle = "⏸ غیرفعال کن" if b["active"] else "▶️ فعال کن"
        await update.message.reply_text(
            _summary(b),
            reply_markup=_kb([[
                InlineKeyboardButton(toggle, callback_data=f"bannertoggle:{b['banner_id']}"),
                InlineKeyboardButton("🗑 حذف", callback_data=f"bannerdel:{b['banner_id']}"),
            ]]),
        )


async def handle_banner_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("فقط ادمین می‌تونه این کار رو انجام بده.", show_alert=True)
        return
    await query.answer()
    banner_id = int(query.data.split(":")[1])
    b = db.get_banner(banner_id)
    if not b:
        await query.edit_message_text("این بنر دیگه وجود نداره.")
        return
    db.set_banner_active(banner_id, not b["active"])
    b = db.get_banner(banner_id)
    toggle = "⏸ غیرفعال کن" if b["active"] else "▶️ فعال کن"
    await query.edit_message_text(
        _summary(b),
        reply_markup=_kb([[
            InlineKeyboardButton(toggle, callback_data=f"bannertoggle:{banner_id}"),
            InlineKeyboardButton("🗑 حذف", callback_data=f"bannerdel:{banner_id}"),
        ]]),
    )


async def handle_banner_delete_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("فقط ادمین می‌تونه این کار رو انجام بده.", show_alert=True)
        return
    await query.answer()
    banner_id = int(query.data.split(":")[1])
    b = db.get_banner(banner_id)
    if not b:
        await query.edit_message_text("این بنر دیگه وجود نداره.")
        return
    await query.edit_message_text(
        f"مطمئنی می‌خوای بنر #{banner_id} («{b['title_fa']}») رو کامل حذف کنی؟",
        reply_markup=_kb([[
            InlineKeyboardButton("بله، حذف کن", callback_data=f"bannerdelok:{banner_id}"),
            InlineKeyboardButton("انصراف", callback_data=f"bannertoggle:{banner_id}"),
        ]]),
    )


async def handle_banner_delete_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update.effective_user.id):
        await query.answer("فقط ادمین می‌تونه این کار رو انجام بده.", show_alert=True)
        return
    await query.answer()
    banner_id = int(query.data.split(":")[1])
    db.delete_banner(banner_id)
    await query.edit_message_text(f"🗑 بنر #{banner_id} حذف شد.")


def build_handlers():
    text = filters.TEXT & ~filters.COMMAND
    conv = ConversationHandler(
        entry_points=[CommandHandler("newbanner", newbanner_start)],
        states={
            WAITING_BANNER_FA: [MessageHandler(text, receive_banner_fa)],
            WAITING_BANNER_EN: [
                CallbackQueryHandler(receive_banner_en, pattern=r"^banner:skip_en$"),
                MessageHandler(text, receive_banner_en),
            ],
            WAITING_BANNER_RU: [
                CallbackQueryHandler(receive_banner_ru, pattern=r"^banner:skip_ru$"),
                MessageHandler(text, receive_banner_ru),
            ],
            WAITING_BANNER_THEME: [CallbackQueryHandler(handle_banner_theme, pattern=r"^banner:theme:")],
            WAITING_BANNER_ACTION: [CallbackQueryHandler(handle_banner_action, pattern=r"^banner:act:")],
            WAITING_BANNER_URL: [MessageHandler(text, receive_banner_url)],
            WAITING_BANNER_DAYS: [
                CallbackQueryHandler(receive_banner_days, pattern=r"^banner:days:none$"),
                MessageHandler(text, receive_banner_days),
            ],
        },
        fallbacks=[CommandHandler("cancel", newbanner_cancel)],
        per_message=False,
    )
    return [
        conv,
        CommandHandler("banners", banners_list),
        CallbackQueryHandler(handle_banner_toggle, pattern=r"^bannertoggle:"),
        CallbackQueryHandler(handle_banner_delete_ask, pattern=r"^bannerdel:"),
        CallbackQueryHandler(handle_banner_delete_ok, pattern=r"^bannerdelok:"),
    ]
