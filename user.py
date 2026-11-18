import asyncio
import contextlib
import datetime
from zoneinfo import ZoneInfo
import logging
import re
import time
from functools import wraps

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ApplicationHandlerStop,
    filters,
)

import database as db
import security as sec
from i18n import t, DEFAULT_LANG, SUPPORTED_LANGS
from config import (
    get_plan,
    DURATION_LABELS,
    DURATION_MONTHS,
    PRICE_PER_GB_TOMAN,
    PREMIUM_LOCATION_NAME,
    get_plans_for_duration,
    CARD_NUMBER,
    CARD_HOLDER,
    ADMIN_CHAT_ID,
    ADMIN_IDS,
    BRAND_NAME_FA,
    BRAND_NAME_EN,
    SUPPORT_USERNAME,
    SUPPORT_LINK,
    FREE_TRIAL_DAYS,
    FREE_TRIAL_GB,
    FREE_TRIAL_MB,
    REFERRAL_BONUS_TOMAN,
    REFERRAL_SIGNUP_BONUS_TOMAN,
    PLATFORM_GUIDES,
    FORCE_JOIN_CHANNEL,
    REQUIRED_CHANNEL_USERNAME,
    REQUIRED_CHANNEL_LINK,
    DEMO_MODE,
    SERVICES_PAGE_SIZE,
    FAQ_ITEMS,
    TICKET_AUTO_CLOSE_DAYS,
    CRYPTO_PAYMENT_ENABLED,
    CRYPTO_CURRENCIES,
    CRYPTO_CURRENCY_LABELS,
    CRYPTO_INVOICE_TIMEOUT_MINUTES,
    DATA_WARNING_THRESHOLD_PERCENT,
    EXPIRY_WARNING_DAYS_BEFORE,
    FINAL_WARNING_HOURS,
    WINBACK_ENABLED,
    WINBACK_PERCENT,
    WINBACK_HOURS,
    LOYALTY_TIERS,
    RESELLER_MIN_TOPUP_TOMAN,
    RESELLER_PRICE_PER_GB_TOMAN,
    RESELLER_REMARK_PREFIX,
    PLANS,
    AUTOSMS_ENABLED,
    AUTOSMS_INVOICE_TTL_MINUTES,
    AUTOSMS_MIN_AMOUNT_TOMAN,
    AUTOSMS_MAX_AMOUNT_TOMAN,
    TONPAYS_ENABLED,
    TONPAYS_INVOICE_TIMEOUT_MINUTES,
    PUBLIC_BASE_URL,
    MINIAPP_URL,
    BOT_ACTION_LIMIT,
    BOT_ACTION_WINDOW_SECONDS,
    BOT_HEAVY_ACTION_LIMIT,
    BOT_HEAVY_ACTION_WINDOW_SECONDS,
)
from panel_client import panel, PanelError
import xrocket_client as xrocket
import autosms_client as autosms
import tonpays_client as tonpays
import premium_emoji as pe
from delivery import send_service_delivery, _plan_with_actual_gb
import smart_plans
import rich_messages as rm
import rich_screens as rs
import jalali
from keyboards import (
    weekly_summary_keyboard,
    main_menu_keyboard,
    main_reply_keyboard,
    language_keyboard,
    duration_keyboard,
    gb_tier_keyboard,
    location_keyboard,
    trial_location_keyboard,
    trial_used_keyboard,
    all_plans_keyboard,
    confirm_payment_keyboard,
    card_payment_details_keyboard,
    autosms_payment_keyboard,
    tonpays_payment_keyboard,
    custom_name_choice_keyboard,
    admin_decision_keyboard,
    my_services_keyboard,
    renew_gb_tier_keyboard,
    renew_duration_keyboard,
    renew_location_keyboard,
    renew_all_plans_keyboard,
    confirm_renew_payment_keyboard,
    back_to_menu_keyboard,
    enter_app_keyboard,
    get_referral_link,
    referral_keyboard,
    account_keyboard,
    crypto_payment_keyboard,
    crypto_currency_keyboard,
    CRYPTO_CURRENCY_ICON,
    wallet_menu_keyboard,
    data_warning_keyboard,
    expired_notice_keyboard,
    confirm_topup_payment_keyboard,
    payment_method_keyboard,
    join_channel_keyboard,
    platform_keyboard,
    platform_guide_keyboard,
    services_table_keyboard,
    service_detail_keyboard,
    service_delete_confirm_keyboard,
    service_note_keyboard,
    wallet_transfer_confirm_keyboard,
    support_menu_keyboard,
    faq_back_keyboard,
    ticket_created_keyboard,
    ticket_answer_keyboard,
    ticket_closed_keyboard,
    ticket_list_keyboard,
    ticket_detail_keyboard,
    admin_ticket_keyboard,
    leaderboard_back_keyboard,
    onboarding_keyboard,
    rating_keyboard,
    reseller_hub_keyboard,
    reseller_catalog_keyboard,
    reseller_confirm_keyboard,
    reseller_name_choice_keyboard,
    reseller_duration_keyboard,
    reseller_volume_keyboard,
    admin_reseller_request_keyboard,
    loyalty_hub_keyboard,
)

WAITING_RECEIPT = 1
WAITING_TOPUP_AMOUNT = 2
WAITING_TOPUP_RECEIPT = 3
WAITING_SERVICE_SEARCH = 4
WAITING_SERVICE_NOTE = 5
WAITING_SERVICE_TRANSFER = 6
WAITING_WALLET_TRANSFER_TARGET = 7
WAITING_WALLET_TRANSFER_AMOUNT = 8
WAITING_TICKET_MESSAGE = 9
WAITING_TICKET_REPLY_USER = 10
WAITING_CUSTOM_NAME = 11
WAITING_DISCOUNT_CODE = 12
WAITING_RESELLER_REASON = 13
WAITING_RESELLER_NAME = 14

logger = logging.getLogger(__name__)


# ==================== ضدِ اسپم/فلاد داخل خودِ چت بات ====================
# جدا و مستقل از محدودیت‌های مینی‌اپ/وب‌هوک (keep_alive.py) - این‌جا هر
# «اکشن» یعنی یه پیام یا کلیک دکمه‌ی داخل خودِ چت بات.

async def global_flood_gate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    این handler با group=-1 قبل از همه‌ی handlerهای دیگه اجرا میشه (تو bot.py
    ثبت شده) - یه سقف کلی و سبک روی «هر اکشنی» از طرف هر کاربر تلگرام
    می‌ذاره تا جلوی اسپم‌کلیک/فلاد عمومی رو بگیره. ادمین‌ها معاف‌ان (کارهای
    مدیریتی مثل تایید سفارش‌ها/پیام‌همگانی نباید بهش بخوره).
    """
    user = update.effective_user
    if not user or user.id in ADMIN_IDS:
        return
    ok, retry_after = sec.allow(f"tgflood:{user.id}", BOT_ACTION_LIMIT, BOT_ACTION_WINDOW_SECONDS)
    if ok:
        return
    # بی‌سروصدا - فقط یه هشدار کوتاه، بدون اسپم بیشتر (پیام متنی جدید نمی‌فرستیم)
    try:
        if update.callback_query:
            await update.callback_query.answer("یکم آروم‌تر! چند ثانیه صبر کن 🙏", show_alert=False)
    except Exception:
        pass
    raise ApplicationHandlerStop


def heavy_limited(fn):
    """
    دکوراتور برای اکشن‌های «گرون» - اون‌هایی که با پنل VPN یا درگاه پرداخت
    بیرونی حرف می‌زنن یا مستقیم پول/موجودی جابه‌جا می‌کنن (ساخت/تمدید سرویس،
    ساخت فاکتور، بررسی وضعیت فاکتور، انتقال کیف‌پول، تلاش برای کد تخفیف).
    سقفش جداگونه و به‌مراتب سخت‌گیرانه‌تر از سقف کلی global_flood_gate ـه.
    """
    @wraps(fn)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if user and user.id not in ADMIN_IDS:
            ok, retry_after = sec.allow(f"tgheavy:{user.id}", BOT_HEAVY_ACTION_LIMIT, BOT_HEAVY_ACTION_WINDOW_SECONDS)
            if not ok:
                wait_txt = f"{int(retry_after) + 1} ثانیه‌ی دیگه"
                msg = f"⏳ برای جلوگیری از فشار زیاد، لطفاً {wait_txt} صبر کن و دوباره امتحان کن."
                try:
                    if update.callback_query:
                        await update.callback_query.answer(msg, show_alert=True)
                    elif update.effective_message:
                        await update.effective_message.reply_text(msg)
                except Exception:
                    pass
                return None
        return await fn(update, context, *args, **kwargs)
    return wrapper


def _extract_image_file_id(message):
    """رسید ممکنه به‌صورت عکس عادی یا فایل تصویری ارسال شده باشه؛ هر دو رو پشتیبانی می‌کنیم"""
    if message.photo:
        return message.photo[-1].file_id
    if message.document and (message.document.mime_type or "").startswith("image/"):
        return message.document.file_id
    return None


def _last_visit_text(user_id: int, lang) -> str:
    """«آخرین ورود» (نشست قبلی) به شمسی؛ برای اولین بازدید متن خوش‌آمد"""
    prev = db.touch_last_seen(user_id)
    return jalali.format_jalali_datetime(prev) if prev else t("panel_first_visit", lang)


async def _try_rich(update: Update, rich_html, markup, lang) -> bool:
    """
    نسخه‌ی غنی (جدول) یه صفحه رو می‌فرسته یا (از دکمه‌ی inline) پیام فعلی رو باهاش ویرایش می‌کنه.
    True یعنی انجام شد. هر خطایی (خاموش بودن، رد تلگرام، پیام عکس‌دار) False برمی‌گردونه و
    فراخوان با همون پیام کلاسیک ادامه میده؛ یعنی کاربر هیچ‌وقت بی‌پاسخ نمی‌مونه.
    """
    if not (rich_html and rm.enabled()):
        return False
    rtl = rm.is_rtl(lang)
    chat_id = update.effective_chat.id
    if update.callback_query:
        msg = update.callback_query.message
        if not getattr(msg, "photo", None):
            ok, _ = await rm.edit_rich(chat_id, msg.message_id, html=rich_html, reply_markup=markup, rtl=rtl)
            if ok:
                return True
        ok, _ = await rm.send_rich(chat_id, html=rich_html, reply_markup=markup, rtl=rtl)
        return ok
    ok, _ = await rm.send_rich(chat_id, html=rich_html, reply_markup=markup, rtl=rtl)
    return ok


async def _reply_or_edit(update: Update, text: str, rich=None, lang=None, **kwargs):
    """
    پیام رو یا ادیت می‌کنه (وقتی از یه دکمه‌ی inline اومده) یا به‌عنوان پیام
    تازه می‌فرسته (وقتی از منوی ثابت پایین صفحه/یه پیام متنی اومده). این‌جوری
    توابع مشترک منو هم از دکمه‌های inline هم از منوی ثابت قابل‌استفاده‌ان،
    بدون تکرار منطق.

    نکته‌ی مهم: اگه پیام اصلی متنی نباشه (مثلاً عکس/ویدیوی یه پست همگانی با
    دکمه)، edit_message_text از تلگرام خطا می‌گیره چون نمیشه کپشن یه
    عکس/ویدیو رو با این متد ویرایش کرد. برای همین وقتی edit شکست بخوره،
    به‌جای این‌که کاربر هیچی نبینه (دکمه انگار کار نمی‌کنه)، یه پیام تازه
    می‌فرستیم.
    """
    # rich = نسخه‌ی غنی (جدول) همین صفحه؛ اگه روشن باشه و تلگرام قبول کنه، به‌جای متن کلاسیک میره
    if await _try_rich(update, rich, kwargs.get("reply_markup"), lang):
        return
    with (rm.suppress() if rich else contextlib.nullcontext()):   # رد شده؛ رهگیر دوباره امتحانش نکنه
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(text, **kwargs)
            except Exception:
                await update.effective_chat.send_message(text, **kwargs)
        else:
            await update.message.reply_text(text, **kwargs)


async def check_and_prompt_join(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str = None) -> bool:
    """
    بررسی می‌کنه که کاربر عضو کانال اجباری هست یا نه.
    اگه عضو بود یا این قابلیت خاموش بود: True برمی‌گردونه (اجازه‌ی ادامه).
    اگه عضو نبود: پیام عضویت رو نشون میده و False برمی‌گردونه (باید متوقف بشه).
    """
    if not FORCE_JOIN_CHANNEL:
        return True

    user = update.effective_user
    if user.id in ADMIN_IDS:
        return True

    if lang is None:
        lang = db.get_user_language(user.id)

    try:
        member = await context.bot.get_chat_member(
            chat_id=REQUIRED_CHANNEL_USERNAME, user_id=user.id
        )
        if member.status in ("member", "administrator", "creator"):
            return True
    except Exception:
        logger.exception(
            "خطا در بررسی عضویت کاربر %s در کانال %s (شاید ربات ادمین کانال نیست)",
            user.id,
            REQUIRED_CHANNEL_USERNAME,
        )
        # اگه بررسی عضویت به هر دلیلی ممکن نبود، کاربر رو بلاک نمی‌کنیم
        return True

    text = (
        f"{pe.LOCK} {t('join_channel_prompt', lang, brand=BRAND_NAME_FA)}\n\n"
        f"{REQUIRED_CHANNEL_LINK}\n\n"
        f"{t('join_channel_instruction', lang)}"
    )
    kb = join_channel_keyboard(lang)

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await update.effective_chat.send_message(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")

    return False


async def handle_checkjoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    lang = db.get_user_language(user.id)
    ok = await check_and_prompt_join(update, context, lang)
    if not ok:
        await query.answer(t("not_joined_alert", lang), show_alert=True)
        return

    await query.answer(t("joined_confirmed", lang))
    await query.edit_message_text(f"{pe.CONFIRM} {t('joined_confirmed', lang)}", parse_mode="HTML")
    await query.message.reply_text(
        f"{pe.WAVE} " + t("welcome_short", lang, name=pe.esc(user.first_name or ""), brand=BRAND_NAME_FA),
        reply_markup=main_reply_keyboard(lang),
        parse_mode="HTML",
    )


def _extract_referrer(args) -> int:
    """از /start ref_123456 آیدی معرف رو استخراج می‌کنه، اگه نبود None"""
    if not args:
        return None
    payload = args[0]
    if payload.startswith("ref_"):
        try:
            return int(payload.split("_", 1)[1])
        except ValueError:
            return None
    return None


def _build_welcome_text(user) -> str:
    return (
        f"{pe.WAVE} سلام {pe.esc(user.first_name or '')}!\n"
        f"اگه سرعت و کیفیت برات مهمه، جای درستی اومدی.\n\n"
        f"{pe.ROCKET} {BRAND_NAME_FA} سرویسی ارائه می‌ده که هر بار بدون نگرانی"
        f" بهش وصل شی؛ سریع، پایدار و قابل اعتماد.\n\n"
        f"{pe.DIAMOND} ویژگی‌های سرویس‌های ما:\n"
        f"{pe.GAME_CONTROLLER} مناسب گیمینگ\n"
        f"{pe.MAP} آی‌پی ثابت اختصاصی\n"
        f"{pe.WHEEL} سرعت بالا و پینگ پایین\n"
        f"{pe.CHAT} پشتیبانی ۲۴/۷\n\n"
        f"از منوی زیر شروع کن {pe.DOWN_ARROW}"
    )


async def _send_main_menu_message(send_func, user, lang):
    """پیام منوی اصلی + خط وضعیت سریع (موجودی/تعداد سرویس)؛ مشترک بین start، انتخاب زبان و پایان آنبوردینگ"""
    status_line = t(
        "quick_status_line", lang,
        wallet_icon=pe.WALLET, services_icon=pe.MY_SERVICES,
        balance=db.get_wallet_balance(user.id), count=len(db.get_user_subscriptions(user.id)),
    )
    markup = main_reply_keyboard(lang)
    if rm.enabled():
        # نسخه‌ی غنی: جدول موجودی / سرویس فعال / شناسه (مثل پنل‌های جدول‌دار)
        ok, _ = await rm.send_rich(
            user.id,
            html=rs.main_menu(lang, user.first_name, BRAND_NAME_FA, db.get_wallet_balance(user.id),
                              len(db.get_user_subscriptions(user.id)), user.id, _last_visit_text(user.id, lang)),
            reply_markup=markup, rtl=rm.is_rtl(lang),
        )
        if ok:
            return
    await send_func(
        f"{pe.WAVE} " + t("welcome_short", lang, name=pe.esc(user.first_name or ""), brand=BRAND_NAME_FA)
        + "\n\n" + status_line,
        reply_markup=markup,
        parse_mode="HTML",
    )


ONBOARDING_STEP_KEYS = ["onboarding_step1", "onboarding_step2", "onboarding_step3"]
ONBOARDING_STEP_ICONS = [pe.ROCKET, pe.TRIAL, pe.TWO_PEOPLE]


async def onboarding_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کاروسل خوش‌آمدگویی ۳ مرحله‌ای؛ فقط یک‌بار، بلافاصله بعد از انتخاب زبون توسط کاربر جدید"""
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    lang = db.get_user_language(user.id)
    step = query.data.split(":", 1)[1]

    if step == "done":
        await _send_main_menu_message(query.message.reply_text, user, lang)
        return

    step_index = int(step) - 1  # step=2 یعنی متن دومه (اولی مستقیم بعد از انتخاب زبون فرستاده میشه)
    is_last = step_index == len(ONBOARDING_STEP_KEYS) - 1
    next_step = "done" if is_last else str(step_index + 2)

    await query.edit_message_text(
        f"{ONBOARDING_STEP_ICONS[step_index]} " + t(ONBOARDING_STEP_KEYS[step_index], lang, brand=BRAND_NAME_FA),
        reply_markup=onboarding_keyboard(next_step),
        parse_mode="HTML",
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    existing = db.get_user(user.id)
    is_new_user = existing is None

    referred_by = None
    if not existing:
        referred_by = _extract_referrer(context.args)
        if referred_by == user.id:
            referred_by = None  # کسی نمیتونه معرف خودش باشه

    db.upsert_user(user.id, user.username or "", user.first_name or "", referred_by=referred_by)

    if referred_by and not existing:
        db.adjust_wallet_balance_logged(
            referred_by,
            REFERRAL_SIGNUP_BONUS_TOMAN,
            "referral_signup",
            f"هدیه‌ی عضویت زیرمجموعه {user.id}",
        )
        try:
            await context.bot.send_message(
                chat_id=referred_by,
                text=(
                    f"{pe.CHARGE} یک نفر با لینک دعوت تو عضو شد!\n"
                    f"{REFERRAL_SIGNUP_BONUS_TOMAN:,} تومان به کیف پولت اضافه شد."
                ),
                parse_mode="HTML",
            )
        except Exception:
            logger.warning("اطلاع‌رسانی هدیه عضویت به معرف %s ناموفق بود", referred_by)

    if is_new_user:
        # کاربر تازه: قبل هر چیز دیگه‌ای (حتی چک عضویت کانال)، انتخاب زبان
        await update.message.reply_text(
            t("choose_language", DEFAULT_LANG), reply_markup=language_keyboard()
        )
        return

    lang = db.get_user_language(user.id)

    if not await check_and_prompt_join(update, context, lang):
        return

    await _send_main_menu_message(update.message.reply_text, user, lang)


async def handle_setlang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بعد از انتخاب زبون (اولین بار که کاربر وارد بات میشه)"""
    query = update.callback_query
    await query.answer()

    lang = query.data.split(":", 1)[1]
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG

    user = update.effective_user
    db.set_user_language(user.id, lang)

    await query.edit_message_text(t("language_set", lang))

    if not await check_and_prompt_join(update, context, lang):
        return

    # کاروسل خوش‌آمدگویی ۳ مرحله‌ای، فقط همین یک‌بار برای کاربر تازه
    await query.message.reply_text(
        f"{ONBOARDING_STEP_ICONS[0]} " + t(ONBOARDING_STEP_KEYS[0], lang, brand=BRAND_NAME_FA),
        reply_markup=onboarding_keyboard("2"),
        parse_mode="HTML",
    )


async def menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = db.get_user_language(update.effective_user.id)

    if not await check_and_prompt_join(update, context, lang):
        return

    action = query.data.split(":", 1)[1]

    if action == "buy":
        await _reply_or_edit(
            update, _location_prompt_text(lang), reply_markup=location_keyboard(), parse_mode="HTML"
        )
    elif action == "back":
        status_line = t(
            "quick_status_line", lang,
            wallet_icon=pe.WALLET, services_icon=pe.MY_SERVICES,
            balance=db.get_wallet_balance(update.effective_user.id),
            count=len(db.get_user_subscriptions(update.effective_user.id)),
        )
        u = update.effective_user
        await _reply_or_edit(
            update, f"{pe.CHECK2} {t('back_to_menu', lang)}\n\n{status_line}", parse_mode="HTML",
            rich=(rs.main_menu(lang, u.first_name, BRAND_NAME_FA, db.get_wallet_balance(u.id),
                               len(db.get_user_subscriptions(u.id)), u.id, _last_visit_text(u.id, lang), back=True)
                  if rm.enabled() else None),
            lang=lang,
        )
    elif action == "myservices":
        await show_my_services(update, context)
    elif action == "trial":
        await handle_trial(update, context)
    elif action == "wallet":
        await show_wallet(update, context)
    elif action == "account":
        await show_account(update, context)
    elif action == "referral":
        await show_referral(update, context)
    elif action == "apps":
        await show_apps(update, context)
    elif action == "support":
        await show_support_menu(update, context)
    elif action == "reseller":
        await show_reseller_hub(update, context)
    elif action == "loyalty":
        await show_loyalty_hub(update, context)
    elif action == "backmenu":
        await _send_main_menu_message(update.callback_query.message.reply_text, update.effective_user, lang)


def _build_reply_menu_actions() -> dict:
    """
    از هر ۳ زبان، یه نسخه‌ی معکوس می‌سازه: «متن دکمه (به هر زبانی) -> اکشن»،
    چون کاربر ممکنه با هرکدوم از زبون‌ها روی دکمه‌ی پایین صفحه بزنه.
    """
    keys = {
        "enterapp": "menu_enter_app",
        "buy": "menu_buy",
        "myservices": "menu_myservices",
        "trial": "menu_trial",
        "wallet": "menu_wallet",
        "account": "menu_account",
        "apps": "menu_apps",
        "referral": "menu_referral",
        "support": "menu_support",
        "reseller": "menu_reseller",
        "loyalty": "menu_loyalty",
        "backmenu": "menu_back_to_main",
    }
    actions = {}
    for action, i18n_key in keys.items():
        for lang in SUPPORTED_LANGS:
            actions[t(i18n_key, lang)] = action
    # چندتا دکمه رو تو خودِ ReplyKeyboard (keyboards.py) با متن سفارشی/متفاوت
    # از کلید مشترک i18n نشون می‌دیم (چون همون کلید جای دیگه‌ای هم استفاده
    # میشه و نمی‌خوایم اونجا رو هم عوض کنه) - برای همین این متن‌های دقیق رو
    # هم صریحاً به همون اکشن وصل می‌کنیم، وگرنه دکمه بی‌صدا از کار میفته.
    actions["کیف پول من"] = "wallet"
    actions["پشتیبانی آنی"] = "support"
    actions["خرید سرویس"] = "buy"
    # اسم قدیمیِ دکمه (قبل از تغییر به «ورود به مینی اپ»): کیبورد پایین صفحه‌ی بعضی کاربرا تا
    # دفعه‌ی بعد که منو براشون ارسال بشه هنوز همین متن رو داره؛ نباید بی‌صدا از کار بیفته.
    actions["ورود به برنامه"] = "enterapp"
    # اسم قدیمیِ «دعوت دوستان» (قبلاً «زیرمجموعه‌گیری» بود)؛ همون دلیلِ بالا
    actions["زیرمجموعه‌گیری"] = "referral"
    return actions


REPLY_MENU_ACTIONS = _build_reply_menu_actions()


async def reply_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌های منوی ثابت پایین صفحه (ReplyKeyboard) رو به همون منطق دکمه‌های inline وصل می‌کنه"""
    action = REPLY_MENU_ACTIONS.get((update.message.text or "").strip())
    if not action:
        return

    lang = db.get_user_language(update.effective_user.id)

    if not await check_and_prompt_join(update, context, lang):
        return

    if action == "enterapp":
        if not MINIAPP_URL:
            await update.message.reply_text("مینی‌اپ فعلاً تنظیم نشده.")
            return
        await update.message.reply_text(
            "برای ورود به مینی اپ، دکمه‌ی زیر رو بزن:",
            reply_markup=enter_app_keyboard(),
        )
        return
    if action == "buy":
        await _reply_or_edit(update, _location_prompt_text(lang), reply_markup=location_keyboard(), parse_mode="HTML")
    elif action == "myservices":
        await show_my_services(update, context)
    elif action == "trial":
        await handle_trial(update, context)
    elif action == "wallet":
        await show_wallet(update, context)
    elif action == "account":
        await show_account(update, context)
    elif action == "apps":
        await show_apps(update, context)
    elif action == "referral":
        await show_referral(update, context)
    elif action == "support":
        await show_support_menu(update, context)
    elif action == "reseller":
        await show_reseller_hub(update, context)
    elif action == "loyalty":
        await show_loyalty_hub(update, context)
    elif action == "backmenu":
        await _send_main_menu_message(update.message.reply_text, update.effective_user, lang)


# ---------------- سرویس‌های من / تمدید ----------------
from service_stats import (
    fetch_live_stats as _fetch_live_stats,
    remaining_days as _remaining_days,
    grace_seconds as _grace_seconds,
    grace_deadline as _grace_deadline,
    grace_left_seconds as _grace_left_seconds,
)


def _fmt_left(seconds) -> str:
    """مدت باقی‌مانده رو به‌صورت «2 روز و 10 ساعت» برمی‌گردونه"""
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours = rem // 3600
    if days and hours:
        return f"{days} روز و {hours} ساعت"
    if days:
        return f"{days} روز"
    if hours:
        return f"{hours} ساعت"
    return "کمتر از یک ساعت"


def _fmt_left_short(seconds) -> str:
    """نسخه‌ی کوتاه برای دکمه‌ها: «2 روز» یا «5 ساعت»"""
    seconds = max(0, int(seconds))
    days = seconds // 86400
    if days:
        return f"{days} روز"
    return f"{max(1, seconds // 3600)} ساعت"


async def _build_service_rows(subs):
    """برای هر سرویس، آمار زنده رو می‌گیره و یک دیکشنری آماده برای مرتب‌سازی/نمایش برمی‌گردونه"""
    result = []
    for s in subs:
        stats = await _fetch_live_stats(s, include_config=False)
        result.append(
            {
                "sub_id": s["sub_id"],
                "plan_title": s["plan_title"],
                "username": s["marzban_username"] or "",
                "remaining_days": _remaining_days(s),
                "grace_left": _grace_left_seconds(s),
                "remaining_gb": stats["remaining_gb"],
                "sub_link": s["sub_link"],
            }
        )
    return result


def _sort_rows(rows, sort_key: str):
    if sort_key == "volume":
        # نامحدودها (None) آخر لیست؛ بقیه از کم به زیاد (فوری‌ترین‌ها اول)
        return sorted(rows, key=lambda r: (r["remaining_gb"] is None, r["remaining_gb"] if r["remaining_gb"] is not None else 0))
    if sort_key == "name":
        return sorted(rows, key=lambda r: r["plan_title"] or "")
    # پیش‌فرض: زمان - نامحدودها آخر، بقیه از کم به زیاد
    return sorted(rows, key=lambda r: (r["remaining_days"] is None, r["remaining_days"] if r["remaining_days"] is not None else 0))


def _row_labels(r) -> dict:
    name_label = r["username"] or r["plan_title"]
    if len(name_label) > 14:
        name_label = name_label[:13] + "…"

    if r["remaining_gb"] is None:
        volume_label = "نامحدود"
    else:
        volume_label = f"{r['remaining_gb']:g}GB"

    if r.get("grace_left") is not None:
        # سرویس پایان‌یافته (در مهلت تمدید): به‌جای «۰ روز»، زمان مونده تا حذف رو نشون بده
        days_label = f"⏳ {_fmt_left_short(r['grace_left'])}"
    elif r["remaining_days"] is None:
        days_label = "نامحدود"
    else:
        days_label = f"{r['remaining_days']} روز"

    return {
        "sub_id": r["sub_id"],
        "name_label": name_label,
        "volume_label": volume_label,
        "days_label": days_label,
    }


async def render_services_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: int = 1,
    sort_key: str = "days",
    search: str = None,
):
    user_id = update.effective_user.id
    lang = db.get_user_language(user_id)
    subs = db.get_user_subscriptions(user_id)

    if not subs:
        await _reply_or_edit(
            update,
            t("my_services_empty", lang),
        )
        return

    if search:
        needle = search.strip().lower()
        subs = [
            s for s in subs
            if needle in (s["plan_title"] or "").lower() or needle in (s["marzban_username"] or "").lower()
        ]
        if not subs:
            await _reply_or_edit(
                update,
                f"{pe.APPS} چیزی برای «{pe.esc(search)}» پیدا نشد.",
                reply_markup=services_table_keyboard([], 1, 1, sort_key, search_active=True),
                parse_mode="HTML",
            )
            return

    rows = await _build_service_rows(subs)
    rows = _sort_rows(rows, sort_key)

    total_pages = max(1, (len(rows) + SERVICES_PAGE_SIZE - 1) // SERVICES_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * SERVICES_PAGE_SIZE
    page_rows = rows[start:start + SERVICES_PAGE_SIZE]
    labels = [_row_labels(r) for r in page_rows]

    header = f"{pe.MY_SERVICES} {t('my_services_title', lang)}"
    if search:
        header += f"\n🔍 {pe.esc(search)}"
    text = f"{header}\n\n{t('my_services_hint', lang)}"

    await _reply_or_edit(
        update,
        text,
        reply_markup=services_table_keyboard(labels, page, total_pages, sort_key, search_active=bool(search)),
        parse_mode="HTML",
    )


async def show_my_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await render_services_list(update, context, page=1, sort_key="days")


async def handle_services_sort(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sort_key = query.data.split(":", 1)[1]
    await render_services_list(update, context, page=1, sort_key=sort_key)


async def handle_services_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, page_str, sort_key = query.data.split(":")
    await render_services_list(update, context, page=int(page_str), sort_key=sort_key)


async def handle_service_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, sub_id_str, page_str, sort_key = query.data.split(":")
    await _render_service_detail(update, context, int(sub_id_str), int(page_str), sort_key)


async def handle_autorenew_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, sub_id_str, page_str, sort_key, new_value = query.data.split(":")
    sub_id = int(sub_id_str)
    sub = db.get_subscription(sub_id)
    if not sub or sub["user_id"] != update.effective_user.id:
        await query.answer("سرویس پیدا نشد.", show_alert=True)
        return
    db.set_auto_renew(sub_id, bool(int(new_value)))
    await query.answer(
        "تمدید خودکار روشن شد؛ به‌محض نزدیک شدن انقضا، خودکار از کیف پولت کسر میشه."
        if int(new_value) else "تمدید خودکار خاموش شد."
    )
    await _render_service_detail(update, context, sub_id, int(page_str), sort_key)


async def _render_service_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, sub_id: int, page: int, sort_key: str):
    query = update.callback_query
    sub = db.get_subscription(sub_id)
    if not sub or sub["user_id"] != update.effective_user.id:
        await query.answer("سرویس پیدا نشد.", show_alert=True)
        return

    stats = await _fetch_live_stats(sub)
    remaining_days = _remaining_days(sub)

    lines = [f"{pe.MY_SERVICES} {pe.esc(sub['plan_title'])}\n"]
    grace_left = _grace_left_seconds(sub)
    if grace_left is not None:
        reason_txt = "اتمام حجم" if sub["ended_reason"] == "data" else "پایان مدت"
        lines.append(f"{pe.REJECT} وضعیت: پایان‌یافته ({reason_txt})")
        lines.append(
            f"{pe.HOURGLASS2} مهلت تمدید: {_fmt_left(grace_left)} تا حذف قطعی\n"
            "با تمدید، همین لینک و کانفیگ قبلی دوباره فعال میشه."
        )
    elif remaining_days is None:
        lines.append(f"{pe.REMAINING} انقضا: بدون انقضا")
    else:
        expire_str = datetime.datetime.fromtimestamp(sub["expire_at"]).strftime("%Y-%m-%d")
        lines.append(f"{pe.REMAINING} انقضا: {expire_str} ({remaining_days} روز مانده)")

    if stats["remaining_gb"] is None:
        lines.append(f"{pe.UNLIMITED} حجم: نامحدود")
    else:
        lines.append(f"{pe.UNLIMITED} حجم باقی‌مانده: {stats['remaining_gb']:g} گیگ")

    lines.append(f"\n{pe.CONNECTION} کانفیگ اتصال:")
    if stats["connection_link"]:
        lines.append(f"<code>{pe.esc(stats['connection_link'])}</code>")
    else:
        lines.append("در حال حاضر در دسترس نیست؛ از دکمه‌ی «دریافت کانفیگ‌ها» امتحان کن.")
    lines.append(f"\n{pe.LINK} لینک سابسکریپشن:\n<code>{pe.esc(stats['subscription_url'])}</code>")

    volume_label = "نامحدود" if stats["remaining_gb"] is None else f"{stats['remaining_gb']:g}GB"
    if grace_left is not None:
        days_label = f"⏳ {_fmt_left_short(grace_left)}"
    else:
        days_label = "نامحدود" if remaining_days is None else f"{remaining_days} روز"

    detail_text = "\n".join(lines)
    detail_markup = service_detail_keyboard(
        sub_id, page, sort_key, volume_label, days_label, stats["subscription_url"],
        auto_renew=bool(sub["auto_renew"]), show_auto_renew=remaining_days is not None,
    )
    # نسخه‌ی غنی (جدول)؛ اگه خاموش باشه یا تلگرام رد کنه، همون پیام کلاسیک پایین میره
    if rm.enabled():
        status_rows = []
        if grace_left is not None:
            reason_txt = "اتمام حجم" if sub["ended_reason"] == "data" else "پایان مدت"
            status_rows.append((pe.REJECT, "وضعیت", f"پایان‌یافته ({reason_txt})"))
            status_rows.append((pe.HOURGLASS2, "مهلت تمدید", rm.mark(f"{_fmt_left(grace_left)} تا حذف قطعی")))
            status_rows.append((pe.CONFIRM, "با تمدید", "همین لینک و کانفیگ قبلی دوباره فعال میشه"))
        elif remaining_days is None:
            status_rows.append((pe.CALENDAR, "انقضا", "بدون انقضا"))
        else:
            expire_str = datetime.datetime.fromtimestamp(sub["expire_at"]).strftime("%Y-%m-%d")
            status_rows.append((pe.CALENDAR, "انقضا", rm.Raw(f"{expire_str} " + str(rm.mark(f"{remaining_days} روز مانده")))))
        if stats["remaining_gb"] is None:
            status_rows.append((pe.UNLIMITED, "حجم", "نامحدود"))
        else:
            status_rows.append((pe.REMAINING, "حجم باقی‌مانده", rm.mark(f"{stats['remaining_gb']:g} گیگ")))
        rich_html = rs.service_detail(sub["plan_title"], status_rows, stats["connection_link"], stats["subscription_url"])
        if await _try_rich(update, rich_html, detail_markup, "fa"):
            return
    # اگه این دکمه از زیر پیام QR (که یه پیام عکسه، نه متن) زده شده باشه،
    # نمیشه با edit_message_text ویرایشش کرد؛ باید یه پیام متنی جدید فرستاد
    if query.message.photo:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=detail_text,
            reply_markup=detail_markup,
            parse_mode="HTML",
        )
    else:
        await query.edit_message_text(detail_text, reply_markup=detail_markup, parse_mode="HTML")


async def handle_svc_getsub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.split(":")[1])
    sub = db.get_subscription(sub_id)
    if not sub or sub["user_id"] != update.effective_user.id:
        await query.answer("سرویس پیدا نشد.", show_alert=True)
        return

    connection_link = ""
    try:
        info = await panel.get_user(sub["marzban_username"])
        connection_link = info.get("connection_link") or ""
    except PanelError:
        pass

    lines = []
    if connection_link:
        lines.append(f"{pe.CONNECTION} کانفیگ اتصال:\n<code>{pe.esc(connection_link)}</code>\n")
    lines.append(f"{pe.LINK} لینک سابسکریپشن:\n<code>{pe.esc(sub['sub_link'])}</code>")

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="\n".join(lines),
        parse_mode="HTML",
    )


async def handle_svc_getconfigs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("در حال دریافت کانفیگ...")
    _, sub_id_str, page_str, sort_key = query.data.split(":")
    sub_id = int(sub_id_str)
    sub = db.get_subscription(sub_id)
    if not sub or sub["user_id"] != update.effective_user.id:
        await query.answer("سرویس پیدا نشد.", show_alert=True)
        return

    try:
        info = await panel.get_user(sub["marzban_username"])
    except PanelError as e:
        await query.answer(f"خطا در دریافت کانفیگ: {e}", show_alert=True)
        return

    connection_link = info.get("connection_link") or ""
    if not connection_link:
        text = f"{pe.LIST} کانفیگ جداگانه‌ای در دسترس نیست؛ از لینک سابسکریپشن استفاده کن."
    else:
        text = f"{pe.LIST} کانفیگ این سرویس:\n<code>{pe.esc(connection_link)}</code>"

    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode="HTML")


async def handle_svc_refreshlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("در حال بازتولید لینک...")
    _, sub_id_str, page_str, sort_key = query.data.split(":")
    sub_id = int(sub_id_str)
    sub = db.get_subscription(sub_id)
    if not sub or sub["user_id"] != update.effective_user.id:
        await query.answer("سرویس پیدا نشد.", show_alert=True)
        return

    try:
        result = await panel.revoke_subscription(sub["marzban_username"])
    except PanelError as e:
        await query.answer(f"خطا: {e}", show_alert=True)
        return

    new_link = result.get("subscription_url", sub["sub_link"])
    db.update_subscription_link(sub_id, new_link)

    lines = [f"{pe.CONNECTION} لینک‌های قبلی باطل شدن.\n"]
    connection_link = result.get("connection_link") or ""
    if connection_link:
        lines.append(f"{pe.CONNECTION} کانفیگ اتصال جدید:\n<code>{pe.esc(connection_link)}</code>\n")
    lines.append(f"{pe.LINK} لینک سابسکریپشن جدید:\n<code>{pe.esc(new_link)}</code>")

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="\n".join(lines),
        parse_mode="HTML",
    )


async def handle_svc_check_online(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("در حال بررسی وضعیت اتصال...")
    _, sub_id_str, page_str, sort_key = query.data.split(":")
    sub_id = int(sub_id_str)
    sub = db.get_subscription(sub_id)
    if not sub or sub["user_id"] != update.effective_user.id:
        await query.answer("سرویس پیدا نشد.", show_alert=True)
        return

    try:
        is_online = await panel.get_online_status(sub["marzban_username"])
    except PanelError as e:
        await query.answer(f"خطا: {e}", show_alert=True)
        return

    if is_online:
        await query.answer("🟢 سرویس همین الان به سرور وصله.", show_alert=True)
    else:
        await query.answer("🔴 همین الان هیچ اتصالی فعالی از این سرویس دیده نمیشه.", show_alert=True)


async def handle_svc_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, sub_id_str, page_str, sort_key = query.data.split(":")
    sub_id = int(sub_id_str)
    sub = db.get_subscription(sub_id)
    if not sub or sub["user_id"] != update.effective_user.id:
        await query.answer("سرویس پیدا نشد.", show_alert=True)
        return

    note_text = sub["note"] or "هنوز یادداشتی ثبت نشده."
    await query.edit_message_text(
        rs.hdr(pe.LIST, "یادداشت سرویس", [("سرویس", pe.esc(sub["plan_title"]))]) + f"\n\n{rs._RLM}{pe.esc(note_text)}",
        reply_markup=service_note_keyboard(sub_id, int(page_str), sort_key),
        parse_mode="HTML",
    )


async def ask_service_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    _, sub_id_str, page_str, sort_key = query.data.split(":")
    context.user_data["note_ctx"] = {
        "sub_id": int(sub_id_str), "page": int(page_str), "sort_key": sort_key
    }
    await query.edit_message_text(
        rs.hdr("✏️", "یادداشت سرویس", hint="متن یادداشتت رو بفرست."),
        reply_markup=back_to_menu_keyboard(),
    )
    return WAITING_SERVICE_NOTE


async def receive_service_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ctx = context.user_data.get("note_ctx")
    if not ctx:
        await update.message.reply_text("یه مشکلی پیش اومد، از /start دوباره شروع کن.")
        return ConversationHandler.END

    sub = db.get_subscription(ctx["sub_id"])
    if not sub or sub["user_id"] != update.effective_user.id:
        await update.message.reply_text("سرویس پیدا نشد.")
        return ConversationHandler.END

    db.set_subscription_note(ctx["sub_id"], update.message.text.strip())
    await update.message.reply_text(f"{pe.CONFIRM} یادداشت ذخیره شد.", parse_mode="HTML")
    context.user_data.pop("note_ctx", None)
    return ConversationHandler.END


async def handle_svc_transfer_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    _, sub_id_str, page_str, sort_key = query.data.split(":")
    context.user_data["transfer_ctx"] = {
        "sub_id": int(sub_id_str), "page": int(page_str), "sort_key": sort_key
    }
    await query.edit_message_text(
        f"{pe.TRANSFER} آیدی عددی کاربری که می‌خوای این سرویس بهش منتقل بشه رو بفرست.\n"
        "(اون کاربر باید قبلا حداقل یک بار به ربات /start زده باشه.)",
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard(),
    )
    return WAITING_SERVICE_TRANSFER


async def receive_service_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ctx = context.user_data.get("transfer_ctx")
    if not ctx:
        await update.message.reply_text("یه مشکلی پیش اومد، از /start دوباره شروع کن.")
        return ConversationHandler.END

    back_kb = back_to_menu_keyboard()
    raw = update.message.text.strip()
    if not raw.isdigit():
        await update.message.reply_text("لطفا فقط آیدی عددی معتبر بفرست.", reply_markup=back_kb)
        return WAITING_SERVICE_TRANSFER

    target_id = int(raw)
    user = update.effective_user

    if target_id == user.id:
        await update.message.reply_text("نمی‌تونی سرویس رو به خودت منتقل کنی.", reply_markup=back_kb)
        return WAITING_SERVICE_TRANSFER

    target_user = db.get_user(target_id)
    if not target_user:
        await update.message.reply_text(
            "این آیدی هنوز به ربات پیام نداده. اول باید اون کاربر /start رو بزنه، بعد دوباره امتحان کن.",
            reply_markup=back_kb,
        )
        return WAITING_SERVICE_TRANSFER

    sub = db.get_subscription(ctx["sub_id"])
    if not sub or sub["user_id"] != user.id:
        await update.message.reply_text("سرویس پیدا نشد.")
        context.user_data.pop("transfer_ctx", None)
        return ConversationHandler.END

    db.transfer_subscription(ctx["sub_id"], target_id)

    await update.message.reply_text(
        f"{pe.CONFIRM} سرویس «{sub['plan_title']}» به آیدی {target_id} منتقل شد.",
        parse_mode="HTML",
    )
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"{pe.CONFIRM} یک سرویس («{sub['plan_title']}») به حساب تو منتقل شد! از «سرویس‌های من» ببینش.",
            parse_mode="HTML",
        )
    except Exception:
        logger.warning("اطلاع‌رسانی انتقال سرویس به کاربر %s ناموفق بود", target_id)

    context.user_data.pop("transfer_ctx", None)
    return ConversationHandler.END


async def handle_svc_delete_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, sub_id_str, page_str, sort_key = query.data.split(":")
    sub_id = int(sub_id_str)
    sub = db.get_subscription(sub_id)
    if not sub or sub["user_id"] != update.effective_user.id:
        await query.answer("سرویس پیدا نشد.", show_alert=True)
        return

    await query.edit_message_text(
        rs.hdr(pe.TRASH, "حذف سرویس", [("سرویس", pe.esc(sub["plan_title"]))],
               "آیا مطمئنی می‌خوای این سرویس رو کامل حذف کنی؟ این کار غیرقابل بازگشته."),
        reply_markup=service_delete_confirm_keyboard(sub_id, int(page_str), sort_key),
        parse_mode="HTML",
    )


async def handle_svc_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("در حال حذف...")
    _, sub_id_str, page_str, sort_key = query.data.split(":")
    sub_id = int(sub_id_str)
    sub = db.get_subscription(sub_id)
    if not sub or sub["user_id"] != update.effective_user.id:
        await query.answer("سرویس پیدا نشد.", show_alert=True)
        return

    try:
        await panel.remove_user(sub["marzban_username"])
    except PanelError as e:
        await query.answer(f"خطا در حذف از پنل: {e}", show_alert=True)
        return

    db.delete_subscription(sub_id)
    await render_services_list(update, context, page=int(page_str), sort_key=sort_key)


async def handle_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


async def ask_service_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        rs.hdr("🔍", "جستجوی سرویس", hint="اسم پلن یا یوزرنیم سرویس رو بفرست تا جستجو کنم."),
        reply_markup=back_to_menu_keyboard(),
    )
    return WAITING_SERVICE_SEARCH


async def receive_service_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    search_term = update.message.text.strip()

    user_id = update.effective_user.id
    subs = db.get_user_subscriptions(user_id)
    needle = search_term.lower()
    filtered = [
        s for s in subs
        if needle in (s["plan_title"] or "").lower() or needle in (s["marzban_username"] or "").lower()
    ]

    if not filtered:
        await update.message.reply_text(
            f"چیزی برای «{search_term}» پیدا نشد."
        )
        return ConversationHandler.END

    rows = await _build_service_rows(filtered)
    rows = _sort_rows(rows, "days")
    total_pages = max(1, (len(rows) + SERVICES_PAGE_SIZE - 1) // SERVICES_PAGE_SIZE)
    page_rows = rows[:SERVICES_PAGE_SIZE]
    labels = [_row_labels(r) for r in page_rows]

    text = f"{pe.MY_SERVICES} سرویس‌های من\n🔍 نتایج جستجو برای: {pe.esc(search_term)}"
    await update.message.reply_text(
        text,
        reply_markup=services_table_keyboard(labels, 1, total_pages, "days", search_active=True),
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def clear_service_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await render_services_list(update, context, page=1, sort_key="days")


async def _recommendation_for_sub(sub):
    """
    پیشنهاد پلن بر اساس مصرف واقعیِ این سرویس (smart_plans)؛ None اگه داده‌ی کافی نیست.
    هر خطایی (پنل، دیتابیس) فقط باعث میشه پیشنهاد نیاد؛ هیچ‌وقت جلوی تمدید رو نمی‌گیره.
    """
    if not sub:
        return None
    try:
        import usage_history

        stats = await _fetch_live_stats(sub, include_config=False)
        week = usage_history.get_week(sub["sub_id"])
        return smart_plans.build_recommendation(
            sub["plan_id"], stats["remaining_gb"], _remaining_days(sub), week["avg_gb"], week["tracked_days"]
        )
    except Exception:
        logger.warning("محاسبه‌ی پیشنهاد پلن برای سرویس #%s ناموفق بود", sub["sub_id"] if sub else None)
        return None


def _recommendation_text(rec) -> str:
    avg = f"{rec['avg_gb']:g}"
    if rec["sufficient"]:
        line = f"با مصرف روزی حدود {avg} گیگ، حجم این پلن برای کل دوره‌ش کافیه."
    else:
        line = (
            f"مصرفت (روزی حدود {avg} گیگ) بالاست و این بزرگ‌ترین پلن محدوده؛ "
            "اگه باز هم کم اومد، با پشتیبانی صحبت کن."
        )
    return f"{pe.STAR} پیشنهاد برای مصرف تو: {pe.esc(rec['title'])}\n{line}"


async def choose_renew_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not await check_and_prompt_join(update, context):
        return

    sub_id = int(query.data.split(":", 1)[1])
    await query.edit_message_text(
        "لوکیشن موردنظرت رو انتخاب کن:",
        reply_markup=renew_location_keyboard(sub_id),
    )


async def handle_renew_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not await check_and_prompt_join(update, context):
        return

    _, sub_id_str, months_str = query.data.split(":")
    sub_id, months = int(sub_id_str), int(months_str)
    lang = db.get_user_language(update.effective_user.id)
    st = _duration_stats(months)
    if not st:
        await query.edit_message_text(
            f"{_renew_title(lang, 1)}\n\n{_duration_overview_text(lang)}",
            reply_markup=renew_duration_keyboard(sub_id),
            parse_mode="HTML",
        )
        return
    rec = await _recommendation_for_sub(db.get_subscription(sub_id))
    text = f"{_renew_title(lang, 2)}\n\n{_volume_step_text(months, st, lang)}"
    if rec:
        text += "\n\n" + _recommendation_text(rec)
    await query.edit_message_text(
        text,
        reply_markup=renew_gb_tier_keyboard(sub_id, months, recommended_id=rec["plan_id"] if rec else None),
        parse_mode="HTML",
    )


async def handle_renew_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not await check_and_prompt_join(update, context):
        return

    _, sub_id_str, _location = query.data.split(":")
    sub_id = int(sub_id_str)
    lang = db.get_user_language(update.effective_user.id)
    rec = await _recommendation_for_sub(db.get_subscription(sub_id))
    text = (
        f"{_renew_title(lang, 1)}\n\n"
        f"{_duration_overview_text(lang)}\n\n"
        f"{t('renew_keep_note', lang)}"
    )
    if rec:
        text += "\n\n" + _recommendation_text(rec)
    await query.edit_message_text(
        text,
        reply_markup=renew_duration_keyboard(sub_id),
        parse_mode="HTML",
    )


async def choose_renew_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = db.get_user_language(update.effective_user.id)

    if not await check_and_prompt_join(update, context, lang):
        return

    _, sub_id, plan_id = query.data.split(":")
    plan = get_plan(plan_id)
    if not plan:
        await query.edit_message_text(t("plan_not_found", lang))
        return

    unlimited_tag = f" {pe.UNLIMITED}" if plan.get("is_unlimited") else ""
    text = (
        f"{_renew_title(lang, 3)}\n"
        f"{pe.CONNECTION} {t('renew_summary_intro', lang)}\n"
        f"{t('plan_selected_summary', lang, emoji=plan['emoji_tag'], title=plan['title'], unlimited=unlimited_tag)}\n"
        f"{_plan_detail_lines(plan, lang)}"
        f"{pe.PRICE} {t('plan_price_label', lang, price=plan['price'])}\n\n"
        f"{t('choose_payment_method_prompt', lang)}"
    )
    wallet_balance = db.get_wallet_balance(update.effective_user.id)
    await query.edit_message_text(
        text,
        reply_markup=confirm_renew_payment_keyboard(int(sub_id), plan_id, wallet_balance),
        parse_mode="HTML",
    )


async def show_card_payment_details_renew(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """صفحه‌ی دوم: نمایش شماره کارت + دکمه‌های کپی، برای تمدید سرویس"""
    query = update.callback_query
    await query.answer()

    if not await check_and_prompt_join(update, context):
        return

    _, sub_id, plan_id = query.data.split(":")
    lang = db.get_user_language(update.effective_user.id)
    plan = get_plan(plan_id)
    if not plan:
        await query.edit_message_text(t("plan_not_found", lang))
        return

    text = (
        rs.hdr(pe.CARD, "پرداخت کارت به کارت", [(pe.MY_SERVICES, "تمدید", pe.esc(plan["title"]))]) + "\n\n"
        f"{pe.PRICE} مبلغ (کامل و بدون تغییر واریز کن): <b>{plan["price"] * 10:,}</b> ریال (معادل {plan["price"]:,} تومان)\n\n"
        f"{pe.CARD} {t('payment_instructions', lang, card_number=CARD_NUMBER, card_holder=CARD_HOLDER)}"
    )
    markup = card_payment_details_keyboard(
        kind="renew", plan_id=plan_id, amount=plan["price"], card_number=CARD_NUMBER, sub_id=int(sub_id)
    )
    await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")


async def back_to_renew_payment_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, sub_id, plan_id = query.data.split(":")
    lang = db.get_user_language(update.effective_user.id)
    plan = get_plan(plan_id)
    if not plan:
        await query.edit_message_text(t("plan_not_found", lang))
        return

    unlimited_tag = f" {pe.UNLIMITED}" if plan.get("is_unlimited") else ""
    text = (
        f"{_renew_title(lang, 3)}\n"
        f"{pe.CONNECTION} {t('renew_summary_intro', lang)}\n"
        f"{t('plan_selected_summary', lang, emoji=plan['emoji_tag'], title=plan['title'], unlimited=unlimited_tag)}\n"
        f"{_plan_detail_lines(plan, lang)}"
        f"{pe.PRICE} {t('plan_price_label', lang, price=plan['price'])}\n\n"
        f"{t('choose_payment_method_prompt', lang)}"
    )
    wallet_balance = db.get_wallet_balance(update.effective_user.id)
    await query.edit_message_text(
        text,
        reply_markup=confirm_renew_payment_keyboard(int(sub_id), plan_id, wallet_balance),
        parse_mode="HTML",
    )


# ---------------- تست رایگان ----------------
# مسیر: دکمه‌ی «تست رایگان» ← انتخاب لوکیشن (برای وقتی که چند لوکیشن/سرویس داشته باشیم) ← ساخت تست.
# اگه کاربر قبلاً تست گرفته، فقط یه پیام کامل با دکمه‌ی «خرید سرویس» زیرش میاد.
def _trial_location_text(lang) -> str:
    rows = t("trial_location_rows", lang, i1=pe.CALENDAR, i2=pe.REMAINING, days=FREE_TRIAL_DAYS, mb=FREE_TRIAL_MB)
    return (
        f"{pe.TRIAL} {pe.esc(t('menu_trial', lang))}\n"
        f"{pe.STAR} {t('trial_location_intro', lang)}\n"
        f"{rows}\n\n"
        f"{t('trial_location_prompt', lang)}"
    )


async def _trial_already_used(update: Update, lang):
    await _reply_or_edit(
        update,
        f"{pe.TRIAL} {t('trial_already_used', lang)}",
        reply_markup=trial_used_keyboard(lang),
        parse_mode="HTML",
    )


async def handle_trial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ورودی تست رایگان (دکمه‌ی منو): اگه قبلاً تست گرفته پیام + دکمه‌ی خرید، وگرنه انتخاب لوکیشن"""
    user_id = update.effective_user.id
    lang = db.get_user_language(user_id)

    if db.has_used_trial(user_id):
        await _trial_already_used(update, lang)
        return

    await _reply_or_edit(
        update, _trial_location_text(lang), reply_markup=trial_location_keyboard(), parse_mode="HTML"
    )


async def handle_trial_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بعد از انتخاب لوکیشن، تست ساخته میشه"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = db.get_user_language(user_id)

    if not await check_and_prompt_join(update, context, lang):
        return

    # ثبت اتمیک: چند کلیک/درخواست همزمان نمی‌تونن چند تست بسازن
    if not db.claim_trial(user_id):
        await _trial_already_used(update, lang)
        return

    await _reply_or_edit(update, f"{pe.TRIAL} {t('trial_creating', lang)}", parse_mode="HTML")

    try:
        username = panel.generate_username(prefix="trial")
        result = await panel.create_user(username, FREE_TRIAL_DAYS, FREE_TRIAL_GB)
    except PanelError as e:
        db.release_trial(user_id)   # ساخت تست انجام نشد؛ حقِ تست برمی‌گرده
        await update.effective_message.reply_text(
            f"{pe.REJECT} {t('trial_error', lang, error=pe.esc(e))}",
            parse_mode="HTML",
        )
        return
    except Exception:
        db.release_trial(user_id)
        raise
    expire_at = result.get("expire") or 0
    sub_link = result.get("subscription_url", "")
    plan_title = f"تست رایگان ({FREE_TRIAL_DAYS} روزه)"

    new_sub_id = db.create_subscription(
        user_id=user_id,
        order_id=None,
        plan_id="trial",
        marzban_username=username,
        plan_title=plan_title,
        expire_at=expire_at,
        sub_link=sub_link,
    )

    await update.effective_message.reply_text(
        f"{pe.CONFIRM} {t('trial_success', lang)} {pe.DOWN_ARROW}",
        parse_mode="HTML",
    )

    trial_plan = {
        "title": plan_title,
        "emoji": pe.TRIAL,
        "gb": FREE_TRIAL_GB,
        "is_unlimited": False,
        "volume_label": f"{FREE_TRIAL_MB} مگابایت",
        "days": FREE_TRIAL_DAYS,
    }
    await send_service_delivery(
        context.bot, user_id, trial_plan, username, sub_link,
        expire_at=expire_at, sub_id=new_sub_id, connection_link=result.get("connection_link", ""),
    )


# ---------------- کیف پول ----------------
async def show_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = db.get_user_language(user_id)
    balance = db.get_wallet_balance(user_id)

    text = (
        f"{pe.WALLET} {t('wallet_title', lang)}\n\n"
        f"{t('wallet_balance', lang, balance=balance)}\n\n"
        f"{t('wallet_topup_hint', lang, n1=pe.NUM[1], n2=pe.NUM[2])}"
    )
    await _reply_or_edit(
        update, text, reply_markup=wallet_menu_keyboard(), parse_mode="HTML",
        rich=(rs.wallet(lang, balance) if rm.enabled() else None), lang=lang,
    )


async def show_wallet_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = db.get_user_language(user_id)
    txs = db.get_wallet_transactions(user_id, limit=15)
    balance = db.get_wallet_balance(user_id)

    if not txs:
        await query.edit_message_text(
            rs.hdr(pe.WALLET, "تراکنش‌های کیف پول", [("موجودی فعلی", f"{balance:,} تومان")], "هنوز هیچ تراکنشی ثبت نشده."),
            reply_markup=wallet_menu_keyboard(), parse_mode="HTML",
        )
        return

    rlm = rs._RLM
    lines = [rs.hdr(pe.WALLET, "تراکنش‌های کیف پول", [("موجودی فعلی", f"{balance:,} تومان")]), ""]
    for tx in txs:
        sign = "+" if tx["amount"] >= 0 else "-"
        date_str = rs._jdate(tx["created_at"])
        lines.append(f"{rlm}{sign}{abs(tx['amount']):,} تومان — {pe.esc(rs.tx_label(tx['tx_type']))}\n{rlm}{date_str}\n")
    await _reply_or_edit(
        update, "\n".join(lines), reply_markup=wallet_menu_keyboard(), parse_mode="HTML",
        rich=(rs.wallet_transactions(txs, balance) if (lang == "fa" and rm.enabled()) else None), lang=lang,
    )


async def ask_wallet_transfer_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{pe.TRANSFER} آیدی عددی کاربری که می‌خوای بهش موجودی منتقل کنی رو بفرست.\n"
        "(اون کاربر باید قبلا حداقل یک بار به ربات /start زده باشه.)",
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard(),
    )
    return WAITING_WALLET_TRANSFER_TARGET


async def receive_wallet_transfer_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    if not raw.isdigit():
        await update.message.reply_text("لطفا فقط آیدی عددی معتبر بفرست.", reply_markup=back_to_menu_keyboard())
        return WAITING_WALLET_TRANSFER_TARGET

    target_id = int(raw)
    user = update.effective_user

    if target_id == user.id:
        await update.message.reply_text("نمی‌تونی به خودت انتقال بدی.", reply_markup=back_to_menu_keyboard())
        return WAITING_WALLET_TRANSFER_TARGET

    if not db.get_user(target_id):
        await update.message.reply_text(
            "این آیدی هنوز به ربات پیام نداده. اول باید اون کاربر /start رو بزنه، بعد دوباره امتحان کن.",
            reply_markup=back_to_menu_keyboard(),
        )
        return WAITING_WALLET_TRANSFER_TARGET

    context.user_data["wallet_transfer_target"] = target_id
    balance = db.get_wallet_balance(user.id)
    await update.message.reply_text(
        f"موجودی فعلی تو: {balance:,} تومان\nچقدر می‌خوای به {target_id} منتقل کنی؟ (فقط عدد)",
        reply_markup=back_to_menu_keyboard(),
    )
    return WAITING_WALLET_TRANSFER_AMOUNT


async def receive_wallet_transfer_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip().replace(",", "").replace("،", "")
    if not raw.isdigit() or int(raw) <= 0:
        await update.message.reply_text("لطفا فقط عدد معتبر بفرست.", reply_markup=back_to_menu_keyboard())
        return WAITING_WALLET_TRANSFER_AMOUNT

    amount = int(raw)
    user = update.effective_user
    balance = db.get_wallet_balance(user.id)

    if amount > balance:
        await update.message.reply_text(
            f"موجودی کافی نیست. موجودی فعلی: {balance:,} تومان. یه مبلغ کمتر بفرست.",
            reply_markup=back_to_menu_keyboard(),
        )
        return WAITING_WALLET_TRANSFER_AMOUNT

    target_id = context.user_data.get("wallet_transfer_target")
    await update.message.reply_text(
        f"مطمئنی می‌خوای {amount:,} تومان به آیدی {target_id} منتقل کنی؟",
        reply_markup=wallet_transfer_confirm_keyboard(target_id, amount),
    )
    return ConversationHandler.END


async def confirm_wallet_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("در حال انتقال...")
    _, target_id_str, amount_str = query.data.split(":")
    target_id = int(target_id_str)
    amount = int(amount_str)
    user = update.effective_user

    ok = db.transfer_wallet_balance(user.id, target_id, amount)
    if not ok:
        await query.edit_message_text(
            "موجودی کافی نیست یا خطایی پیش اومد.", reply_markup=wallet_menu_keyboard()
        )
        return

    await query.edit_message_text(
        f"{pe.CONFIRM} مبلغ {amount:,} تومان به آیدی {target_id} منتقل شد.\n"
        f"موجودی جدید تو: {db.get_wallet_balance(user.id):,} تومان",
        reply_markup=wallet_menu_keyboard(),
        parse_mode="HTML",
    )
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"{pe.PRICE} مبلغ {amount:,} تومان به کیف پولت واریز شد (انتقال از کاربر دیگر).",
            parse_mode="HTML",
        )
    except Exception:
        logger.warning("اطلاع‌رسانی انتقال موجودی به کاربر %s ناموفق بود", target_id)
    context.user_data.pop("wallet_transfer_target", None)


# ---------------- حساب کاربری ----------------
async def show_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = db.get_user_language(user.id)
    user_row = db.get_user(user.id)
    subs_count = len(db.get_user_subscriptions(user.id))
    balance = db.get_wallet_balance(user.id)

    joined_str = "-"
    if user_row and user_row["joined_at"]:
        joined_str = datetime.datetime.fromtimestamp(user_row["joined_at"]).strftime("%Y-%m-%d")

    spent = db.get_lifetime_spent(user.id)
    tier = db.get_loyalty_tier_for_amount(spent)
    tier_lines = [f"\n{t('account_loyalty_title', lang, icon=pe.CUP)}"]
    if tier:
        tier_lines.append(t("account_loyalty_current", lang, emoji=_tier_medal(tier), name=tier["name"]))
    else:
        tier_lines.append(t("account_loyalty_none", lang))
    tier_lines.append(t("loyalty_account_pointer", lang, menu_label=t("menu_loyalty", lang)))

    text = (
        f"{pe.ACCOUNT} {t('account_title', lang)}\n\n"
        f"{t('account_name', lang)}: {pe.esc(user.first_name or '-')}\n"
        f"{t('account_username', lang)}: @{pe.esc(user.username or t('account_none', lang))}\n"
        f"{t('account_id', lang)}: {user.id}\n\n"
        f"{pe.MY_SERVICES} {t('account_services_count', lang)}: {subs_count}\n\n"
        f"{pe.PRICE} {t('account_balance', lang)}: {balance:,}\n\n"
        f"{pe.CALENDAR} {t('account_joined_at', lang)}: {joined_str}\n"
        + "\n".join(tier_lines)
    )
    rich_html = None
    if rm.enabled():
        tier_text = (
            t("account_loyalty_current", lang, emoji=_tier_medal(tier), name=tier["name"]) if tier
            else t("account_loyalty_none", lang)
        )
        rich_html = rs.account(
            lang, user, subs_count, balance, joined_str, tier_text,
            t("loyalty_account_pointer", lang, menu_label=t("menu_loyalty", lang)),
        )
    await _reply_or_edit(update, text, reply_markup=account_keyboard(), parse_mode="HTML", rich=rich_html, lang=lang)


# ---------------- زیرمجموعه‌گیری ----------------
async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = db.get_user_language(user_id)
    link = get_referral_link(user_id)
    referrals_count = db.count_referrals(user_id)

    referral_orders = db.get_referral_orders(user_id)
    purchases_count = len(referral_orders)
    total_amount = 0
    for o in referral_orders:
        plan = get_plan(o["plan_id"])
        if plan:
            total_amount += plan["price"]

    text = (
        f"{pe.REFERRAL} {t('referral_title', lang)}\n\n"
        f"{t('referral_intro', lang)}\n\n"
        f"{pe.CHARGE} {t('referral_signup_bonus', lang, amount=REFERRAL_SIGNUP_BONUS_TOMAN)}\n"
        f"{pe.PRICE} {t('referral_purchase_bonus', lang, amount=REFERRAL_BONUS_TOMAN)}\n\n"
        f"{t('referral_stats_title', lang)}:\n"
        f"{pe.TWO_PEOPLE} {t('referral_count', lang)}: {referrals_count}\n"
        f"{pe.CART} {t('referral_purchases_count', lang)}: {purchases_count}\n"
        f"{t('referral_total_amount', lang)}: {total_amount:,}\n\n"
        f"{pe.LINK} {t('referral_link_label', lang)}:\n"
        f"<code>{pe.esc(link)}</code>\n\n"
        f"{t('referral_cta', lang)}"
    )
    rich_html = None
    if rm.enabled():
        rich_html = rs.referral(
            lang, referrals_count, purchases_count, total_amount, link,
            REFERRAL_SIGNUP_BONUS_TOMAN, REFERRAL_BONUS_TOMAN,
        )
    await _reply_or_edit(update, text, reply_markup=referral_keyboard(link), parse_mode="HTML", rich=rich_html, lang=lang)


async def show_referral_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = db.get_user_language(user_id)

    rows = db.get_referral_leaderboard_this_month(limit=10)

    if not rows:
        text = f"{t('leaderboard_title', lang, icon=pe.CUP)}\n\n{t('leaderboard_empty', lang, icon=pe.ROCKET)}"
    else:
        lines = [t("leaderboard_title", lang, icon=pe.CUP), ""]
        for i, row in enumerate(rows):
            u = db.get_user(row["user_id"])
            name = pe.esc(u["first_name"]) if u and u["first_name"] else "کاربر"
            medal = f"{i + 1}."
            lines.append("\u200e" + t("leaderboard_row", lang, medal=medal, name=f"<b>{name}</b>", count=row["c"]))
        text = "\n".join(lines)
        if not any(row["user_id"] == user_id for row in rows):
            my_count = db.get_referral_count_this_month(user_id)
            if my_count:
                text += t("leaderboard_your_rank", lang, icon=pe.LOCATION, count=my_count)

    await _reply_or_edit(update, text, reply_markup=leaderboard_back_keyboard(), parse_mode="HTML")


async def handle_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ثبت نظرسنجی رضایت (⭐۱ تا ⭐۵) بعد از خرید یا بستن تیکت"""
    query = update.callback_query
    _, ctx_name, target_id, score = query.data.split(":", 3)
    score = int(score)
    user_id = update.effective_user.id
    lang = db.get_user_language(user_id)

    db.add_rating(user_id, ctx_name, target_id, score)
    await query.answer()
    await query.edit_message_text(t("rating_thanks", lang, stars=pe.STAR * score), parse_mode="HTML")

    if score <= 2:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(
                    f"⚠️ یه نظر {score} ستاره ثبت شد (نوع: {ctx_name}, شناسه: {target_id})"
                    f" از کاربر {user_id}. شاید ارزش پیگیری داشته باشه."
                ),
            )
        except Exception:
            pass


# ---------------- نمایندگی (Reseller) ----------------
def _reseller_hub_text_fa(reseller: bool, eligible: bool, balance: int) -> str:
    rlm = rs._RLM
    if reseller:
        return "\n".join([
            f"{pe.RESELLER} {rlm}نمایندگی فروش\n",
            f"{rlm}تو نماینده‌ی تاییدشده‌ای و سرویس‌ها رو با قیمت عمده می‌خری.\n",
            f"{pe.PRICE} {rlm}قیمت نمایندگی هر گیگ: {RESELLER_PRICE_PER_GB_TOMAN:,} تومان (قیمت عادی: {PRICE_PER_GB_TOMAN:,} تومان)",
            f"{pe.WALLET} {rlm}موجودی کیف پول: {balance:,} تومان\n",
            f"{rlm}چطور خرید کنم؟",
            f"{pe.NUM[1]} {rlm}لوکیشن، مدت و حجم رو انتخاب کن",
            f"{pe.NUM[2]} {rlm}برای سرویس اسم دلخواه بذار یا رندوم باشه",
            f"{pe.NUM[3]} {rlm}از موجودی کیف پولت بخر؛ اگه موجودی کم بود، همون مقدار کمبود رو با درگاه پرداخت شارژ کن و ادامه بده",
            f"{pe.NUM[4]} {rlm}لینک اشتراک رو به مشتریت بده؛ سرویس با همون اسمی که انتخاب کردی نمایش داده میشه",
        ])
    lines = [
        f"{pe.RESELLER} {rlm}نمایندگی فروش\n",
        f"{rlm}با نمایندگی، سرویس‌ها رو با قیمت عمده می‌خری و به مشتری‌های خودت می‌فروشی.\n",
        f"{pe.CHARGE} {rlm}شرط درخواست: موجودی کیف پولت همین الان باید حداقل {RESELLER_MIN_TOPUP_TOMAN:,} تومان باشه "
        f"(موجودیِ همین لحظه حساب میشه، نه مجموع شارژها و تراکنش‌های قبلی).",
        f"{pe.WALLET} {rlm}موجودی فعلی: {balance:,} تومان",
    ]
    if eligible:
        lines.append(f"\n{pe.CONFIRM} {rlm}موجودیت کافیه؛ می‌تونی درخواستت رو برای ادمین بفرستی.")
    else:
        lines.append(f"\n{rlm}برای درخواست، {RESELLER_MIN_TOPUP_TOMAN - balance:,} تومان دیگه به کیف پولت اضافه کن.")
    return "\n".join(lines)


async def show_reseller_hub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = db.get_user_language(user_id)
    reseller = db.is_reseller(user_id)
    balance = db.get_wallet_balance(user_id)   # موجودیِ همین لحظه (نه مجموع شارژهای قبلی)
    eligible = balance >= RESELLER_MIN_TOPUP_TOMAN

    if lang == "fa":
        text = _reseller_hub_text_fa(reseller, eligible, balance)
        rich = rs.reseller_hub(reseller, eligible, balance, RESELLER_MIN_TOPUP_TOMAN) if rm.enabled() else None
    else:
        lines = [t("reseller_title", lang, icon=pe.RESELLER), ""]
        if reseller:
            lines.append(t("reseller_active_intro", lang, price=RESELLER_PRICE_PER_GB_TOMAN))
        elif eligible:
            lines.append(t("reseller_eligible_intro", lang, threshold=RESELLER_MIN_TOPUP_TOMAN))
        else:
            lines.append(t("reseller_not_eligible_intro", lang))
            lines.append("")
            lines.append(t("reseller_progress", lang, icon=pe.CHARGE, current=balance, threshold=RESELLER_MIN_TOPUP_TOMAN))
        text, rich = "\n".join(lines), None

    await _reply_or_edit(
        update, text, reply_markup=reseller_hub_keyboard(reseller, eligible, lang), parse_mode="HTML",
        rich=rich, lang=lang,
    )


async def reseller_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action = query.data.split(":", 1)[1]

    if action == "hub":
        await query.answer()
        await show_reseller_hub(update, context)
    elif action == "catalog":
        await query.answer()
        await show_reseller_catalog(update, context)
    elif action == "dur":
        await query.answer()
        await show_reseller_durations(update, context)
    elif action.startswith("vol:"):
        await query.answer()
        try:
            months = int(action.split(":", 1)[1])
        except ValueError:
            return
        await show_reseller_volumes(update, context, months)
    elif action == "reqplain":
        await handle_reseller_request_plain(update, context)


async def show_reseller_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مرحله‌ی ۱ از ۳ خرید نمایندگی: انتخاب لوکیشن"""
    user_id = update.effective_user.id
    lang = db.get_user_language(user_id)
    if not db.is_reseller(user_id):
        # دفاعی: این دکمه فقط وقتی is_reseller=True هست نشون داده میشه، پس
        # این یعنی درخواست دستکاری‌شده یا وضعیت تازه عوض شده؛ query از قبل
        # توسط reseller_router جواب داده شده، دوباره answer() نمی‌زنیم.
        await show_reseller_hub(update, context)
        return
    balance = db.get_wallet_balance(user_id)
    text = rs.hdr(
        pe.RESELLER, "خرید با قیمت نمایندگی",
        [(pe.MY_SERVICES, "مرحله", "۱ از ۳ (لوکیشن)"), (pe.WALLET, "موجودی کیف پول", f"{balance:,} تومان")],
        "لوکیشن موردنظرت رو انتخاب کن؛ بعدش مدت و حجم رو انتخاب می‌کنی. قیمت‌ها قیمت نمایندگی‌ان.",
    )
    await _reply_or_edit(update, text, reply_markup=reseller_catalog_keyboard(), parse_mode="HTML")


async def show_reseller_durations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مرحله‌ی ۲ از ۳: انتخاب مدت"""
    user_id = update.effective_user.id
    if not db.is_reseller(user_id):
        await show_reseller_hub(update, context)
        return
    balance = db.get_wallet_balance(user_id)
    text = rs.hdr(
        pe.RESELLER, "خرید با قیمت نمایندگی",
        [(pe.MY_SERVICES, "مرحله", "۲ از ۳ (مدت)"), (pe.LOCATION, "لوکیشن", pe.esc(PREMIUM_LOCATION_NAME)),
         (pe.WALLET, "موجودی کیف پول", f"{balance:,} تومان")],
        "مدت اشتراک رو انتخاب کن؛ قیمت روی هر دکمه، ارزون‌ترین پلنِ همون مدت با قیمت نمایندگیه.",
    )
    await _reply_or_edit(update, text, reply_markup=reseller_duration_keyboard(), parse_mode="HTML")


async def show_reseller_volumes(update: Update, context: ContextTypes.DEFAULT_TYPE, months: int):
    """مرحله‌ی ۳ از ۳: انتخاب حجم"""
    user_id = update.effective_user.id
    if not db.is_reseller(user_id):
        await show_reseller_hub(update, context)
        return
    if not get_plans_for_duration(months):
        await show_reseller_durations(update, context)
        return
    balance = db.get_wallet_balance(user_id)
    text = rs.hdr(
        pe.RESELLER, "خرید با قیمت نمایندگی",
        [(pe.MY_SERVICES, "مرحله", "۳ از ۳ (حجم)"), (pe.LOCATION, "لوکیشن", pe.esc(PREMIUM_LOCATION_NAME)),
         (pe.CALENDAR, "مدت", DURATION_LABELS[months]), (pe.WALLET, "موجودی کیف پول", f"{balance:,} تومان")],
        "حجم رو انتخاب کن. اگه موجودیت کم باشه، توی مرحله‌ی بعد می‌تونی مبلغ کمبود رو با درگاه پرداخت شارژ کنی.",
    )
    await _reply_or_edit(update, text, reply_markup=reseller_volume_keyboard(months), parse_mode="HTML")


async def _check_reseller_request_eligibility(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """قبل از هر مسیر ارسال درخواست چک می‌کنه: واجد شرایط باشه و درخواست باز نداشته باشه"""
    query = update.callback_query
    user_id = update.effective_user.id
    lang = db.get_user_language(user_id)
    balance = db.get_wallet_balance(user_id)   # موجودیِ همین لحظه، نه مجموع شارژهای قبلی
    if balance < RESELLER_MIN_TOPUP_TOMAN:
        await query.answer(t("reseller_not_eligible_alert", lang, threshold=RESELLER_MIN_TOPUP_TOMAN), show_alert=True)
        return False
    if db.get_pending_reseller_request(user_id):
        await query.answer(t("reseller_request_pending", lang), show_alert=True)
        return False
    return True


async def ask_reseller_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not await _check_reseller_request_eligibility(update, context):
        return ConversationHandler.END
    lang = db.get_user_language(update.effective_user.id)
    await query.answer()
    await query.edit_message_text(
        t("reseller_request_ask_reason", lang),
        reply_markup=back_to_menu_keyboard(),
    )
    return WAITING_RESELLER_REASON


async def receive_reseller_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = db.get_user_language(user.id)
    message = (update.message.text or "").strip()
    request_id = db.create_reseller_request(user.id, message)
    await _notify_admin_reseller_request(context, request_id, user, message)
    await update.message.reply_text(t("reseller_request_sent", lang, icon=pe.RESELLER), parse_mode="HTML")
    return ConversationHandler.END


async def handle_reseller_request_plain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_reseller_request_eligibility(update, context):
        return
    query = update.callback_query
    user = update.effective_user
    lang = db.get_user_language(user.id)
    await query.answer()
    request_id = db.create_reseller_request(user.id, "")
    await _notify_admin_reseller_request(context, request_id, user, "")
    await query.edit_message_text(t("reseller_request_sent", lang, icon=pe.RESELLER), parse_mode="HTML")


async def _notify_admin_reseller_request(context: ContextTypes.DEFAULT_TYPE, request_id: int, user, message: str):
    caption = (
        f"{pe.RESELLER} درخواست نمایندگی جدید #{request_id}\n"
        "این کاربر درخواست نمایندگی فروش داده؛ بعد از تایید، قیمت نمایندگی برای او فعال میشه و می‌تونه از موجودی کیف پولش سرویس بخره.\n"
        f"کاربر: {pe.esc(user.first_name or '')} (@{pe.esc(user.username or 'بدون‌یوزرنیم')})\n"
        f"آیدی عددی: {user.id}\n"
        f"موجودی فعلی کیف پول: {db.get_wallet_balance(user.id):,} تومان\n"
        f"مجموع شارژ: {db.get_lifetime_topup(user.id):,} تومان\n\n"
        + (f"توضیح: {pe.esc(message)}" if message else "بدون توضیح")
    )
    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID, text=caption,
            reply_markup=admin_reseller_request_keyboard(request_id), parse_mode="HTML",
        )
    except Exception:
        logger.warning("ارسال درخواست نمایندگی #%s به ادمین ناموفق بود", request_id)


async def handle_reseller_buy_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    if not db.is_reseller(user_id):
        await query.answer("این بخش فقط برای نماینده‌های تاییدشده‌ست.", show_alert=True)
        return

    plan_id = query.data.split(":", 1)[1]
    plan = get_plan(plan_id)
    if not plan:
        await query.answer("پلن پیدا نشد.", show_alert=True)
        return
    await query.answer()

    # اول اسم سرویس (دلخواه یا رندوم)، بعد صفحه‌ی تایید خرید
    context.user_data.pop("reseller_name", None)
    text = rs.hdr(
        pe.RESELLER, "اسم سرویس",
        [(pe.MY_SERVICES, "پلن", pe.esc(plan["title"])), (pe.PRICE, "قیمت نمایندگی", f"{plan['reseller_price']:,} تومان")],
        "می‌خوای برای این سرویس اسم دلخواه بذاری یا رندوم باشه؟ این اسم تو کانفیگ مشتری‌ات نمایش داده میشه.",
    )
    await query.edit_message_text(text, reply_markup=reseller_name_choice_keyboard(plan_id), parse_mode="HTML")


async def _send_reseller_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_id: str):
    """صفحه‌ی تایید خرید نمایندگی (بعد از انتخاب اسم)؛ موجودی لحظه‌ای چک میشه و اگه کم بود، شارژ مبلغ کمبود با درگاه پیشنهاد میشه"""
    user_id = update.effective_user.id
    plan = get_plan(plan_id)
    if not plan:
        await _reply_or_edit(update, "پلن پیدا نشد.", reply_markup=reseller_catalog_keyboard())
        return

    pending = context.user_data.get("reseller_name") or {}
    name = pending.get("name") if pending.get("plan_id") == plan_id else None
    name_value = f"<code>{pe.esc(name)}</code>" if name else "رندوم"
    price = plan["reseller_price"]
    balance = db.get_wallet_balance(user_id)
    shortfall = max(0, price - balance)
    facts = [
        (pe.MY_SERVICES, "پلن", pe.esc(plan["title"])),
        (pe.MY_SERVICES, "اسم سرویس", name_value),
        (pe.PRICE, "قیمت نمایندگی", f"{price:,} تومان"),
        (pe.WALLET, "موجودی فعلی", f"{balance:,} تومان"),
    ]
    if shortfall:
        facts.append(("❗️", "کمبود موجودی", f"{shortfall:,} تومان"))
        hint = "با دکمه‌ی زیر همین مقدار رو با درگاه پرداخت شارژ کن؛ بعد از تایید پرداخت، از منوی «نمایندگی» همین پلن رو بخر."
    else:
        hint = "با تایید، سرویس با قیمت نمایندگی از موجودی کیف پولت خریداری میشه و همون لحظه ساخته و برات ارسال میشه."
    text = rs.hdr(pe.RESELLER, "تایید خرید نمایندگی", facts, hint)
    await _reply_or_edit(update, text, reply_markup=reseller_confirm_keyboard(plan_id, shortfall), parse_mode="HTML")


async def handle_reseller_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شارژ دقیقِ مبلغ کمبود با همون درگاه‌های شارژ کیف پول (کارت، درگاه‌ها، کریپتو)"""
    query = update.callback_query
    user_id = update.effective_user.id
    if not db.is_reseller(user_id):
        await query.answer("این بخش فقط برای نماینده‌های تاییدشده‌ست.", show_alert=True)
        return
    plan_id = query.data.split(":", 1)[1]
    plan = get_plan(plan_id)
    if not plan:
        await query.answer("پلن پیدا نشد.", show_alert=True)
        return
    shortfall = plan["reseller_price"] - db.get_wallet_balance(user_id)   # موجودیِ همین لحظه
    if shortfall <= 0:
        await query.answer("موجودیت کافیه!")
        await _send_reseller_confirm(update, context, plan_id)
        return

    await query.answer()
    context.user_data["topup_amount"] = shortfall
    lang = db.get_user_language(user_id)
    text = rs.hdr(
        pe.WALLET, "شارژ مبلغ کمبود",
        [(pe.CONFIRM, "مبلغ", f"{shortfall:,} تومان"), (pe.RESELLER, "برای خرید", pe.esc(plan["title"]))],
        "روش پرداخت رو انتخاب کن؛ بعد از تایید پرداخت، از منوی «نمایندگی» همین پلن رو بخر.",
    )
    await query.edit_message_text(text, reply_markup=payment_method_keyboard(shortfall), parse_mode="HTML")


async def handle_reseller_name_random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not db.is_reseller(update.effective_user.id):
        await query.answer("این بخش فقط برای نماینده‌های تاییدشده‌ست.", show_alert=True)
        return
    await query.answer()
    plan_id = query.data.split(":", 1)[1]
    context.user_data["reseller_name"] = {"plan_id": plan_id, "name": None}
    await _send_reseller_confirm(update, context, plan_id)


async def ask_reseller_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not db.is_reseller(update.effective_user.id):
        await query.answer("این بخش فقط برای نماینده‌های تاییدشده‌ست.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    plan_id = query.data.split(":", 1)[1]
    context.user_data["reseller_name_ctx"] = {"plan_id": plan_id}
    await query.edit_message_text(
        rs.hdr(pe.MY_SERVICES, "اسم دلخواه سرویس",
               hint="اسمی که می‌خوای رو بفرست؛ فقط حروف انگلیسی، عدد و _ ، بدون فاصله، بین ۳ تا ۲۰ کاراکتر و با حرف شروع بشه.")
        + "\n" + rs._RLM + "مثال <code>shop_vip1</code>",
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard(),
    )
    return WAITING_RESELLER_NAME


async def receive_reseller_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ctx = context.user_data.get("reseller_name_ctx")
    if not ctx:
        await update.message.reply_text("یه مشکلی پیش اومد، از /start دوباره شروع کن.")
        return ConversationHandler.END

    cleaned = _sanitize_custom_name(update.message.text or "")
    if not cleaned:
        await update.message.reply_text(
            f"{pe.REJECT} اسم نامعتبره. فقط حروف انگلیسی، عدد و _ مجازه، بین ۳ تا ۲۰ کاراکتر "
            "و باید با حرف شروع بشه. دوباره بفرست.",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
        return WAITING_RESELLER_NAME
    if db.username_taken(cleaned):
        await update.message.reply_text(
            f"{pe.REJECT} این اسم قبلاً برای یه سرویس دیگه گرفته شده؛ یه اسم دیگه بفرست.",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
        return WAITING_RESELLER_NAME

    plan_id = ctx["plan_id"]
    context.user_data["reseller_name"] = {"plan_id": plan_id, "name": cleaned}
    context.user_data.pop("reseller_name_ctx", None)
    await _send_reseller_confirm(update, context, plan_id)
    return ConversationHandler.END


async def handle_reseller_purchase_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user

    if not db.is_reseller(user.id):
        await query.answer("این بخش فقط برای نماینده‌های تاییدشده‌ست.", show_alert=True)
        return

    plan_id = query.data.split(":", 1)[1]
    plan = get_plan(plan_id)
    if not plan:
        await query.answer("پلن پیدا نشد.", show_alert=True)
        return

    price = plan["reseller_price"]
    balance = db.get_wallet_balance(user.id)
    if balance < price:
        await query.answer(f"موجودی کافی نیست؛ {price - balance:,} تومان کم داری.", show_alert=True)
        await _send_reseller_confirm(update, context, plan_id)   # دکمه‌ی شارژ مبلغ کمبود با درگاه
        return

    # کسر اتمیک قبل از ساخت سرویس: چند درخواست همزمان نمی‌تونن یک موجودی رو چندبار خرج کنن
    if not db.try_debit_wallet(user.id, price, "reseller_purchase", f"خرید نمایندگی {plan['title']}"):
        await query.answer("موجودی کافی نیست.", show_alert=True)
        await _send_reseller_confirm(update, context, plan_id)
        return

    await query.answer("در حال صدور سرویس...")

    pending = context.user_data.get("reseller_name") or {}
    custom_name = pending.get("name") if pending.get("plan_id") == plan_id else None

    try:
        # اسم دلخواه = همون اسم (بدون پسوند)؛ رندوم = فقط ۸ حرف رندوم؛ هیچ‌کدوم اسم برند ما رو ندارن
        username = panel.generate_username(prefix=custom_name) if custom_name else panel.generate_username(bare=True)
        result = await panel.create_user(
            username, plan["days"], plan["gb"], display_name=custom_name, remark_prefix=RESELLER_REMARK_PREFIX,
        )
    except PanelError as e:
        _refund_wallet_purchase(user.id, price, "برگشت مبلغ: خطا در صدور سرویس نمایندگی")
        await query.edit_message_text(
            f"{pe.REJECT} در صدور سرویس مشکلی پیش اومد:\n{pe.esc(e)}\nمبلغی از کیف پولت کم نشد.",
            parse_mode="HTML",
        )
        return
    except Exception:
        _refund_wallet_purchase(user.id, price, "برگشت مبلغ: خطای غیرمنتظره")
        raise
    context.user_data.pop("reseller_name", None)

    order_id = db.create_order(user.id, plan_id, None, kind="new", custom_name=custom_name)
    db.set_order_status(order_id, "approved", user.id)

    expire_at = result.get("expire") or 0
    sub_link = result.get("subscription_url", "")
    new_sub_id = db.create_subscription(
        user_id=user.id, order_id=order_id, plan_id=plan_id, marzban_username=username,
        plan_title=plan["title"], expire_at=expire_at, sub_link=sub_link,
        remark_prefix=RESELLER_REMARK_PREFIX,
    )
    db.maybe_reward_referrer(user.id)

    await query.edit_message_text(
        f"{pe.CONFIRM} خرید نمایندگی با موفقیت انجام شد!\n"
        f"{pe.DOWN} موجودی باقیمانده: {db.get_wallet_balance(user.id):,} تومان",
        parse_mode="HTML",
    )
    await send_service_delivery(
        context.bot, user.id, plan, username, sub_link, expire_at=expire_at, sub_id=new_sub_id,
        connection_link=result.get("connection_link", ""),
    )
    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=(
                f"{pe.RESELLER} خرید نمایندگی (نیازی به تایید نیست)\n"
                "این خرید از موجودی کیف پول نماینده پرداخت شد و سرویس همین الان به‌صورت خودکار برای او ساخته و ارسال شد.\n"
                f"کاربر: {pe.esc(user.first_name or '')} (@{pe.esc(user.username or 'بدون‌یوزرنیم')})\n"
                f"پلن: {plan['emoji_tag']} {plan['title']}\n"
                f"مبلغ: {price:,} تومان"
            ),
            parse_mode="HTML",
        )
    except Exception:
        pass


def _loyalty_progress_bar(current: int, target: int, length: int = 10) -> str:
    if not target:
        return ""
    filled = max(0, min(length, int(length * current / target)))
    return "▰" * filled + "▱" * (length - filled)


_LOYALTY_TIER_INDEX = {tr["name"]: i for i, tr in enumerate(LOYALTY_TIERS)}


def _tier_medal(tier: dict) -> str:
    """ایموجی پرمیوم مخصوص سطح باشگاه، بر اساس جایگاهش تو نردبان (سطح ۱ تا ۴)"""
    idx = _LOYALTY_TIER_INDEX.get(tier["name"])
    if idx is not None and idx < len(pe.LOYALTY_TIER_MEDALS):
        return pe.LOYALTY_TIER_MEDALS[idx]
    return tier["emoji"]


async def show_loyalty_hub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = db.get_user_language(user_id)
    spent = db.get_lifetime_spent(user_id)
    tier = db.get_loyalty_tier_for_amount(spent)
    next_tier = next((tr for tr in LOYALTY_TIERS if tr["min_spent"] > spent), None)

    lines = [t("loyalty_hub_title", lang, icon=pe.CUP, brand=BRAND_NAME_FA), ""]

    # ---------- نردبان سطح‌ها ----------
    lines.append(t("loyalty_ladder_title", lang))
    for tr in LOYALTY_TIERS:
        mark = "○"
        current_marker = t("loyalty_current_marker", lang) if tier and tr["name"] == tier["name"] else ""
        tier_emoji = _tier_medal(tr)
        lines.append(
            t(
                "loyalty_tier_row", lang, mark=mark, emoji=tier_emoji, name=tr["name"],
                threshold=tr["min_spent"], bonus=tr["monthly_bonus"], current_marker=current_marker,
            )
        )

    # ---------- پیشرفت تا سطح بعدی ----------
    lines.append("")
    if next_tier:
        lines.append(_loyalty_progress_bar(spent, next_tier["min_spent"]))
        next_tier_emoji = _tier_medal(next_tier)
        lines.append(
            t("account_loyalty_progress", lang, emoji=next_tier_emoji, name=next_tier["name"],
              remaining=next_tier["min_spent"] - spent)
        )
    elif tier:
        lines.append(_loyalty_progress_bar(1, 1))
        lines.append(t("account_loyalty_maxed", lang))
    else:
        lines.append(t("account_loyalty_none", lang))

    # ---------- لیدربرد برترین اعضا ----------
    lines.append("")
    lines.append(t("loyalty_leaderboard_title", lang, icon=pe.CUP))
    top = db.get_top_spenders(limit=10)
    if not top:
        lines.append(t("loyalty_leaderboard_empty", lang))
    else:
        in_top = False
        for i, (uid, total) in enumerate(top):
            u = db.get_user(uid)
            name = pe.esc(u["first_name"]) if u and u["first_name"] else "کاربر"
            rank_num = f"{i + 1}."
            u_tier = db.get_loyalty_tier_for_amount(total)
            badge = _tier_medal(u_tier) if u_tier else ""
            lines.append(f"\u200e{rank_num} <b>{name}</b> {badge}")
            if uid == user_id:
                in_top = True

        if not in_top:
            rank = db.get_spender_rank(user_id)
            if rank:
                lines.append(t("loyalty_your_rank", lang, icon=pe.LOCATION, rank=rank))
            else:
                lines.append(t("loyalty_no_rank_yet", lang))

    text = "\n".join(lines)
    await _reply_or_edit(update, text, reply_markup=loyalty_hub_keyboard(), parse_mode="HTML")


# ---------------- آموزش اپلیکیشن‌ها ----------------
async def show_apps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = db.get_user_language(update.effective_user.id)
    text = f"{pe.APPS} {t('apps_title', lang)}\n\n{t('apps_choose_device', lang)}"
    await _reply_or_edit(update, text, reply_markup=platform_keyboard(), parse_mode="HTML")


async def show_platform_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not await check_and_prompt_join(update, context):
        return

    platform_key = query.data.split(":", 1)[1]
    guide = PLATFORM_GUIDES.get(platform_key)
    if not guide:
        await query.edit_message_text("این پلتفرم پیدا نشد.", reply_markup=platform_keyboard())
        return

    lang = db.get_user_language(update.effective_user.id)
    await _reply_or_edit(
        update,
        _platform_guide_classic(guide),
        reply_markup=platform_guide_keyboard(guide),
        parse_mode="HTML",
        rich=(rs.platform_guide(guide) if rm.enabled() else None),
        lang=lang,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


def _platform_guide_classic(guide: dict) -> str:
    """نسخه‌ی کلاسیک (وقتی پیام غنی خاموشه یا تلگرام رد کنه). اسم فایل‌ها تو <code> تا لینک نشن؛ هر خط با RLM شروع میشه."""
    rlm = rs._RLM
    lines = [
        f"{pe.APPS} راهنمای اتصال - {pe.esc(guide['label'])}\n",
        f"{pe.LINK} {rlm}اپ پیشنهادی: <b>{pe.esc(guide['app_name'])}</b> ({pe.esc(guide['note'])})",
    ]
    if guide.get("req"):
        lines.append(f"{rlm}سازگاری: {pe.esc(guide['req'])}")
    if guide.get("files"):
        lines.append(f"\n📦 {rlm}کدوم فایل رو بگیرم؟")
        lines.extend(f"• {rlm}{pe.esc(cond)}: <code>{pe.esc(name)}</code>" for cond, name in guide["files"])
    if guide.get("files_note"):
        lines.append(f"{rlm}{rs.guide_html(guide['files_note'])}")
    lines.append(f"\n🧭 {rlm}مراحل")
    for i, step in enumerate(guide["steps"], start=1):
        lines.append(f"{pe.NUM.get(i, str(i) + '.')} {rlm}{rs.guide_html(step)}")
    for title, text, code in guide.get("faq") or []:
        lines.append(f"\n💡 {rlm}<b>{pe.esc(title)}</b>\n{rlm}{rs.guide_html(text)}")
        if code:
            lines.append(f"<pre>{pe.esc(code)}</pre>")
    return "\n".join(lines)


# ---------------- پشتیبانی و تیکت ----------------
_TICKET_MAX_LEN = 2000   # هم‌اندازه‌ی مینی‌اپ؛ پیام ادمین هم از سقف ۴۰۹۶ کاراکتر تلگرام رد نمیشه


def _support_menu_classic(lang: str, answered: int) -> str:
    if lang != "fa":
        return f"{pe.SUPPORT} {t('support_title', lang)}\n\n{t('support_choose_option', lang)}"
    rlm = rs._RLM
    lines = [
        f"{pe.SUPPORT} {rlm}پشتیبانی\n",
        f"{pe.QUESTION} {rlm}سوالات متداول: جواب سریع مشکلات رایج؛ اول اینجا رو ببین",
        f"{pe.CHAT} {rlm}ثبت تیکت: سوالت رو بفرست؛ جواب همین‌جا برات میاد",
        f"{pe.FOLDERS} {rlm}تیکت‌های من: پیگیری گفتگوها و وضعیت هر تیکت",
        f"{pe.SUPPORT} {rlm}پشتیبانی تلگرام: گفتگوی مستقیم با پشتیبان",
    ]
    if answered:
        lines.append(f"\n🟢 {rlm}{answered} تیکتت جواب گرفته؛ از «تیکت‌های من» ببینش.")
    if TICKET_AUTO_CLOSE_DAYS > 0:
        lines.append(
            f"\n{rlm}تیکتی که جواب بگیره و {TICKET_AUTO_CLOSE_DAYS:g} روز پیام جدیدی نداشته باشه، خودکار بسته میشه."
        )
    return "\n".join(lines)


async def show_support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = db.get_user_language(user_id)
    answered = db.count_user_answered_tickets(user_id)
    await _reply_or_edit(
        update,
        _support_menu_classic(lang, answered),
        reply_markup=support_menu_keyboard(answered),
        parse_mode="HTML",
        rich=(rs.support_menu(answered, TICKET_AUTO_CLOSE_DAYS) if (lang == "fa" and rm.enabled()) else None),
        lang=lang,
    )


async def show_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rlm = rs._RLM
    lines = [f"{pe.QUESTION} {rlm}سوالات متداول\n"]
    for item in FAQ_ITEMS:
        lines.append(f"◈ {rlm}<b>{pe.esc(item['q'])}</b>\n{rlm}{pe.esc(item['a'])}\n")
    await _reply_or_edit(
        update,
        "\n".join(lines),
        reply_markup=faq_back_keyboard(),
        parse_mode="HTML",
        rich=(rs.faq(FAQ_ITEMS) if rm.enabled() else None),
        lang="fa",
    )


async def ask_ticket_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        rs.hdr(
            pe.CHAT, "ثبت تیکت جدید",
            hint="سوال یا مشکلت رو کامل بنویس و بفرست. هرچی دقیق‌تر بنویسی (اسم سرویس، اپ، متن خطا) سریع‌تر جواب می‌گیری؛ "
                 "رمز یا اطلاعات کارتت رو نفرست.",
        ),
        reply_markup=back_to_menu_keyboard(),
        parse_mode="HTML",
    )
    return WAITING_TICKET_MESSAGE


async def _notify_admin_new_ticket(context, ticket_id: int, user, message_text: str, is_reply: bool = False):
    title = f"💬 پیام جدید در تیکت #{ticket_id}" if is_reply else f"🎫 تیکت جدید #{ticket_id}"
    caption = (
        f"{title}\n"
        f"کاربر: {user.first_name or ''} (@{user.username or 'بدون‌یوزرنیم'})\n"
        f"آیدی عددی: {user.id}\n\n"
        f"{message_text}"
    )
    try:
        admin_msg = await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID, text=caption, reply_markup=admin_ticket_keyboard(ticket_id)
        )
        db.set_ticket_admin_message(ticket_id, admin_msg.message_id)
    except Exception:
        logger.exception("اطلاع‌رسانی تیکت #%s به ادمین ناموفق بود", ticket_id)


async def receive_ticket_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    message_text = update.message.text.strip()
    if len(message_text) > _TICKET_MAX_LEN:
        await update.message.reply_text(
            f"{pe.REJECT} متن تیکت خیلی بلنده (حداکثر {_TICKET_MAX_LEN} کاراکتر). کوتاه‌ترش کن و دوباره بفرست.",
            parse_mode="HTML",
        )
        return WAITING_TICKET_MESSAGE
    ticket_id = db.create_ticket(user.id, message_text)

    await update.message.reply_text(
        f"{pe.CONFIRM} تیکت #{ticket_id} ثبت شد.\n"
        "جواب پشتیبانی همین‌جا برات ارسال میشه؛ وضعیتش رو هم هر وقت خواستی از «تیکت‌های من» ببین.",
        parse_mode="HTML",
        reply_markup=ticket_created_keyboard(ticket_id),
    )
    await _notify_admin_new_ticket(context, ticket_id, user, message_text)
    return ConversationHandler.END


async def show_ticket_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    lang = db.get_user_language(user_id)
    tickets = db.get_user_tickets(user_id)

    if not tickets:
        await query.edit_message_text(
            "هنوز هیچ تیکتی ثبت نکردی. هر وقت سوال یا مشکلی داشتی، «ثبت تیکت جدید» رو بزن.",
            reply_markup=support_menu_keyboard(),
        )
        return

    rlm = rs._RLM
    classic = (
        f"{pe.FOLDERS} {rlm}تیکت‌های من\n\n"
        f"🟡 {rlm}در انتظار پاسخ  |  🟢 {rlm}پاسخ داده شد  |  ⚪️ {rlm}بسته شده\n\n"
        f"{rlm}برای دیدن گفتگو و ارسال پیام جدید، روی هر تیکت بزن."
    )
    if TICKET_AUTO_CLOSE_DAYS > 0:
        classic += f"\n{rlm}تیکتی که جواب بگیره و {TICKET_AUTO_CLOSE_DAYS:g} روز پیام جدیدی نداشته باشه، خودکار بسته میشه."
    await _reply_or_edit(
        update,
        classic,
        reply_markup=ticket_list_keyboard(tickets),
        parse_mode="HTML",
        rich=(rs.ticket_list(tickets, TICKET_AUTO_CLOSE_DAYS) if (lang == "fa" and rm.enabled()) else None),
        lang=lang,
    )


def _ticket_detail_classic(ticket, messages) -> str:
    rlm = rs._RLM
    status_emoji = {"open": "🟡", "answered": "🟢", "closed": "⚪️"}
    status_label = {"open": "در انتظار پاسخ", "answered": "پاسخ داده شد", "closed": "بسته شده"}
    lines = [
        f"🎫 {rlm}تیکت #{ticket['ticket_id']}",
        f"{status_emoji.get(ticket['status'], '⚪️')} {rlm}وضعیت: {status_label.get(ticket['status'], '')}\n",
    ]
    shown = messages[-8:]
    if len(messages) > len(shown):
        lines.append(f"{rlm}({len(messages) - len(shown)} پیام قدیمی‌تر نمایش داده نمیشه)\n")
    for m in shown:
        sender_label = f"{pe.ACCOUNT} تو" if m["sender"] == "user" else f"{pe.SUPPORT} پشتیبانی"
        date_str = rs._jdate(m["created_at"])
        text = (m["text"] or "")
        text = text[:700] + ("…" if len(text) > 700 else "")
        lines.append(f"<b>{sender_label}</b> · {date_str}\n{rlm}{pe.esc(text)}\n")
    if ticket["status"] == "closed":
        lines.append(f"{rlm}این تیکت بسته شده؛ اگه هنوز مشکلی داری، یه تیکت جدید ثبت کن.")
    return "\n".join(lines)


async def show_ticket_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass   # وقتی از handle_ticket_close_user صدا زده میشه، قبلاً جواب داده شده
    ticket_id = int(query.data.split(":", 1)[1])
    ticket = db.get_ticket(ticket_id)
    if not ticket or ticket["user_id"] != update.effective_user.id:
        await query.answer("تیکت پیدا نشد.", show_alert=True)
        return

    lang = db.get_user_language(update.effective_user.id)
    messages = db.get_ticket_messages(ticket_id)
    is_open = ticket["status"] != "closed"
    await _reply_or_edit(
        update,
        _ticket_detail_classic(ticket, messages),
        reply_markup=ticket_detail_keyboard(ticket_id, is_open),
        parse_mode="HTML",
        rich=(rs.ticket_detail(ticket, messages, TICKET_AUTO_CLOSE_DAYS) if (lang == "fa" and rm.enabled()) else None),
        lang=lang,
    )


async def handle_ticket_close_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کاربر خودش تیکتش رو می‌بنده («مشکلم حل شد»)"""
    query = update.callback_query
    ticket_id = int(query.data.split(":", 1)[1])
    ticket = db.get_ticket(ticket_id)
    if not ticket or ticket["user_id"] != update.effective_user.id:
        await query.answer("تیکت پیدا نشد.", show_alert=True)
        return
    if ticket["status"] == "closed":
        await query.answer("این تیکت قبلاً بسته شده.", show_alert=True)
        return

    db.set_ticket_status(ticket_id, "closed")
    await query.answer("تیکت بسته شد.")
    # دکمه‌های پیام ادمین رو برمی‌داریم تا تیکتِ بسته‌شده بی‌جهت باز به نظر نیاد
    if ticket["admin_message_id"]:
        try:
            await context.bot.edit_message_reply_markup(ADMIN_CHAT_ID, ticket["admin_message_id"], reply_markup=None)
        except Exception:
            pass
    await show_ticket_detail(update, context)


async def auto_close_stale_tickets_job(context: ContextTypes.DEFAULT_TYPE):
    """
    تیکتی که پشتیبانی جوابش رو داده و کاربر بعدش TICKET_AUTO_CLOSE_DAYS روز چیزی ننوشته خودکار بسته میشه.
    تیکت‌های بی‌جواب (open) هیچ‌وقت خودکار بسته نمیشن؛ اونا باید جواب بگیرن.
    """
    days = TICKET_AUTO_CLOSE_DAYS
    if not days or days <= 0:
        return
    cutoff = int(time.time() - days * 86400)
    for tk in db.get_tickets_to_auto_close(cutoff):
        try:
            if not db.close_ticket_if_stale(tk["ticket_id"], cutoff):
                continue   # تو همین فاصله یکی (کاربر/ادمین) پیام داده؛ دست نمی‌زنیم
            if tk["admin_message_id"]:
                try:
                    await context.bot.edit_message_reply_markup(ADMIN_CHAT_ID, tk["admin_message_id"], reply_markup=None)
                except Exception:
                    pass
            if (tk["updated_at"] or 0) < time.time() - 30 * 86400:
                continue   # تیکت‌های خیلی قدیمی (بیش از ۳۰ روز) بی‌صدا بسته میشن تا کاربر با پیام کهنه اذیت نشه
            await context.bot.send_message(
                chat_id=tk["user_id"],
                text=(
                    f"{pe.LOCK} تیکت #{tk['ticket_id']} بعد از {days:g} روز بدون پیام جدید خودکار بسته شد.\n"
                    "اگه هنوز مشکلت حل نشده، یه تیکت جدید ثبت کن؛ ما اینجاییم."
                ),
                parse_mode="HTML",
                reply_markup=ticket_closed_keyboard(),
            )
        except Exception:
            logger.exception("بستن خودکار تیکت #%s ناموفق بود", tk["ticket_id"])
        await asyncio.sleep(0.05)


async def ask_ticket_reply_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ticket_id = int(query.data.split(":", 1)[1])
    ticket = db.get_ticket(ticket_id)
    if not ticket or ticket["user_id"] != update.effective_user.id:
        await query.answer("تیکت پیدا نشد.", show_alert=True)
        return ConversationHandler.END
    if ticket["status"] == "closed":
        await query.answer("این تیکت بسته شده؛ برای ادامه یه تیکت جدید ثبت کن.", show_alert=True)
        return ConversationHandler.END

    context.user_data["reply_ticket_id"] = ticket_id
    await query.edit_message_text(
        rs.hdr(pe.CHAT, f"پیام جدید به تیکت #{ticket_id}", hint="پیامت رو بفرست."),
        reply_markup=back_to_menu_keyboard(),
        parse_mode="HTML",
    )
    return WAITING_TICKET_REPLY_USER


async def receive_ticket_reply_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ticket_id = context.user_data.get("reply_ticket_id")
    if not ticket_id:
        await update.message.reply_text("یه مشکلی پیش اومد، از /start دوباره شروع کن.")
        return ConversationHandler.END

    ticket = db.get_ticket(ticket_id)
    if not ticket or ticket["user_id"] != update.effective_user.id:
        await update.message.reply_text("تیکت پیدا نشد.")
        return ConversationHandler.END
    if ticket["status"] == "closed":
        await update.message.reply_text("این تیکت بسته شده؛ برای ادامه یه تیکت جدید ثبت کن.")
        context.user_data.pop("reply_ticket_id", None)
        return ConversationHandler.END

    message_text = update.message.text.strip()
    if len(message_text) > _TICKET_MAX_LEN:
        await update.message.reply_text(
            f"{pe.REJECT} پیام خیلی بلنده (حداکثر {_TICKET_MAX_LEN} کاراکتر). کوتاه‌ترش کن و دوباره بفرست.",
            parse_mode="HTML",
        )
        return WAITING_TICKET_REPLY_USER
    db.add_ticket_message(ticket_id, "user", message_text)
    db.set_ticket_status(ticket_id, "open")

    await update.message.reply_text(
        f"{pe.CONFIRM} پیامت به تیکت #{ticket_id} اضافه شد.",
        parse_mode="HTML",
        reply_markup=ticket_created_keyboard(ticket_id),
    )
    await _notify_admin_new_ticket(context, ticket_id, update.effective_user, message_text, is_reply=True)
    context.user_data.pop("reply_ticket_id", None)
    return ConversationHandler.END


# ---------------- خرید پلن جدید ----------------
# ---------------- متن‌های توضیحی مراحل خرید/تمدید (لوکیشن ← مدت ← حجم) ----------------
# همه‌ی عددها (روز، حجم، قیمت) از روی PLANS در config.py ساخته میشن، پس اگه پلنی اضافه/کم بشه
# متن‌ها خودکار درست می‌مونن. ایموجی‌ها فقط پریمیومِ اختصاصی (pe.PLAN_TAG) هستن.
def _buy_title(lang, n: int, total: int = 4) -> str:
    """خط اول صفحه‌های خرید: «خرید سرویس · مرحله n از ۴» (لوکیشن ← مدت ← حجم ← اسم)؛ بقیه‌ی صفحه همون ساختار قبلیه"""
    return f"{pe.GEM} {t('buy_step_title', lang, n=n, total=total)}"


def _renew_title(lang, n: int, total: int = 3) -> str:
    """خط اول صفحه‌های تمدید: «تمدید سرویس · مرحله n از ۳» (مدت ← حجم ← پرداخت)"""
    return f"{pe.CHARGE} {t('renew_step_title', lang, n=n, total=total)}"


def _location_prompt_text(lang) -> str:
    """صفحه‌ی انتخاب لوکیشن: اسم + چند خط توضیح درباره‌ی سرور + راهنما"""
    points = t(
        "location_premium_points", lang,
        i1=pe.ROCKET, i2=pe.CONNECTION, i3=pe.FIXED_IP, i4=pe.GAME_CONTROLLER,
    )
    return (
        f"{_buy_title(lang, 1)}\n{_location_tag(lang)}\n{pe.STAR} {t('location_premium_intro', lang)}\n"
        f"{points}\n\n{t('menu_location_prompt', lang)}"
    )


def _location_tag(lang) -> str:
    return f"{pe.PLAN_TAG['LOCATION']} {pe.esc(t('location_germany_header', lang))}"


def _duration_label(months: int, lang) -> str:
    if lang == "fa" and months in DURATION_LABELS:
        return DURATION_LABELS[months]   # «۱ ماهه» با ارقام فارسی، یکی با متن دکمه‌ها
    return t("duration_label", lang, n=months)


def _duration_stats(months: int):
    plans = [p for p in PLANS if p.get("duration_months") == months and not p.get("is_unlimited")]
    if not plans:
        return None
    return {
        "days": plans[0]["days"],
        "min_gb": min(p["gb"] for p in plans),
        "max_gb": max(p["gb"] for p in plans),
        "min_price": min(p["price"] for p in plans),
    }


def _duration_overview_text(lang, step: int = None) -> str:
    """صفحه‌ی انتخاب مدت: عنوان لوکیشن، راهنما، یه خط توضیح برای هر مدت و یادآوری قیمت یکسانِ هر گیگ"""
    lines = [_buy_title(lang, step)] if step else []
    lines += [_location_tag(lang), f"{pe.STAR} {t('location_premium_tagline', lang)}", t("plan_duration_prompt", lang)]
    for months in DURATION_MONTHS:
        st = _duration_stats(months)
        if not st:
            continue
        lines.append(
            f"• {pe.PLAN_TAG.get(f'DUR_{months}', '')} "
            + t("plan_duration_line", lang, label=_duration_label(months, lang), **st)
        )
    lines.append("")
    lines.append(t("plan_price_same_note", lang, price_per_gb=PRICE_PER_GB_TOMAN))
    return "\n".join(lines)


def _volume_step_text(months: int, st: dict, lang, step: int = None) -> str:
    """صفحه‌ی انتخاب حجم داخل یه مدت"""
    return (
        (f"{_buy_title(lang, step)}\n" if step else "")
        + f"{_location_tag(lang)} | {pe.PLAN_TAG.get(f'DUR_{months}', '')} {_duration_label(months, lang)}\n"
        f"{pe.PRICE} {t('plan_volume_hint', lang, price_per_gb=PRICE_PER_GB_TOMAN)}\n"
        + t("plan_volume_rows", lang, i1=pe.CALENDAR, i2=pe.REMAINING, i3=pe.PRICE, **st)
        + f"\n\n{t('plan_volume_prompt', lang)}"
    )


def _plan_detail_lines(plan, lang) -> str:
    """دو خط «اعتبار» و «حجم پلن» که زیر خلاصه‌ی پلنِ انتخابی میاد (با آیکون پریمیوم؛ رو پیام غنی جدول میشن)"""
    return (
        f"{pe.CALENDAR} {t('plan_days_label', lang, days=plan['days'])}\n"
        f"{pe.REMAINING} {t('plan_volume_label', lang, gb=plan['gb'])}\n"
    )


async def handle_plan_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not await check_and_prompt_join(update, context):
        return

    lang = db.get_user_language(update.effective_user.id)
    months = int(query.data.split(":", 1)[1])
    st = _duration_stats(months)
    if not st:
        await query.edit_message_text(
            _duration_overview_text(lang, step=2), reply_markup=duration_keyboard(), parse_mode="HTML"
        )
        return
    await query.edit_message_text(
        _volume_step_text(months, st, lang, step=3), reply_markup=gb_tier_keyboard(months), parse_mode="HTML"
    )


async def handle_location_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = db.get_user_language(update.effective_user.id)

    if not await check_and_prompt_join(update, context, lang):
        return

    # بعد از لوکیشن، اول مدت (۱/۲/۳ ماهه) انتخاب میشه و بعدش حجم؛ برگشت از لیست حجم‌ها هم به همین صفحه میاد
    await query.edit_message_text(
        _duration_overview_text(lang, step=2),
        reply_markup=duration_keyboard(),
        parse_mode="HTML",
    )


async def choose_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = db.get_user_language(update.effective_user.id)

    if not await check_and_prompt_join(update, context, lang):
        return

    plan_id = query.data.split(":", 1)[1]
    plan = get_plan(plan_id)
    if not plan:
        await query.edit_message_text(t("plan_not_found", lang), reply_markup=location_keyboard())
        return

    unlimited_tag = f" {pe.UNLIMITED}" if plan.get("is_unlimited") else ""
    text = (
        f"{_buy_title(lang, 4)}\n"
        f"{t('purchase_summary_intro', lang)}\n"
        f"{pe.CONFIRM} {t('plan_selected_summary', lang, emoji=plan['emoji_tag'], title=plan['title'], unlimited=unlimited_tag)}\n"
        f"{_plan_detail_lines(plan, lang)}"
        f"{pe.PRICE} {t('plan_price_label', lang, price=plan['price'])}\n\n"
        f"{t('custom_name_question', lang)}"
    )
    await query.edit_message_text(text, reply_markup=custom_name_choice_keyboard(plan_id), parse_mode="HTML")


def _sanitize_custom_name(raw: str) -> str | None:
    """
    فقط حروف انگلیسی، عدد و آندرلاین مجازه (چون این اسم بخشی از یوزرنیم/شناسه‌ی
    کلاینت روی پنل میشه). بین ۳ تا ۲۰ کاراکتر، باید با حرف شروع بشه.
    اگه نامعتبر بود None برمی‌گردونه.
    """
    cleaned = raw.strip().lower().replace(" ", "_")
    cleaned = re.sub(r"[^a-z0-9_]", "", cleaned)
    if not (3 <= len(cleaned) <= 20):
        return None
    if not cleaned[0].isalpha():
        return None
    return cleaned


async def _send_payment_step(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_id: str):
    """صفحه‌ی نمایش قیمت/شماره‌کارت/روش‌های پرداخت رو نشون میده (بعد از انتخاب اسم)"""
    lang = db.get_user_language(update.effective_user.id)
    plan = get_plan(plan_id)
    if not plan:
        text = t("plan_not_found", lang)
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=location_keyboard())
        else:
            await update.message.reply_text(text, reply_markup=location_keyboard())
        return

    discount = context.user_data.get("applied_discount")
    discount_active = bool(discount and discount.get("plan_id") == plan_id)
    final_price = plan["price"]
    discount_line = ""
    if discount_active:
        final_price = round(plan["price"] * (100 - discount["percent"]) / 100)
        discount_line = (
            f"\n{pe.CONFIRM} کد «{discount['code']}» اعمال شد ({discount['percent']}٪ تخفیف)\n"
            f"{pe.PRICE} قیمت نهایی: {final_price:,} تومان\n"
        )

    unlimited_tag = f" {pe.UNLIMITED}" if plan.get("is_unlimited") else ""
    text = (
        f"{pe.GEM} {t('buy_pay_title', lang)}\n"
        f"{t('purchase_summary_intro', lang)}\n"
        f"{pe.CONFIRM} {t('plan_selected_summary', lang, emoji=plan['emoji_tag'], title=plan['title'], unlimited=unlimited_tag)}\n"
        f"{_plan_detail_lines(plan, lang)}"
        f"{pe.PRICE} {t('plan_price_label', lang, price=plan['price'])}\n"
        f"{discount_line}\n"
        f"{t('choose_payment_method_prompt', lang)}"
    )
    wallet_balance = db.get_wallet_balance(update.effective_user.id)
    markup = confirm_payment_keyboard(plan_id, wallet_balance, final_price=final_price, discount_applied=discount_active)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode="HTML")


async def show_card_payment_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """صفحه‌ی دوم: نمایش شماره کارت + دکمه‌های کپی، برای خرید سرویس جدید"""
    query = update.callback_query
    await query.answer()

    if not await check_and_prompt_join(update, context):
        return

    plan_id = query.data.split(":", 1)[1]
    lang = db.get_user_language(update.effective_user.id)
    plan = get_plan(plan_id)
    if not plan:
        await query.edit_message_text(t("plan_not_found", lang))
        return

    discount = context.user_data.get("applied_discount")
    discount_active = bool(discount and discount.get("plan_id") == plan_id)
    final_price = plan["price"]
    if discount_active:
        final_price = round(plan["price"] * (100 - discount["percent"]) / 100)

    text = (
        rs.hdr(pe.CARD, "پرداخت کارت به کارت", [(pe.MY_SERVICES, "پلن", pe.esc(plan["title"]))]) + "\n\n"
        f"{pe.PRICE} مبلغ (کامل و بدون تغییر واریز کن): <b>{final_price * 10:,}</b> ریال (معادل {final_price:,} تومان)\n\n"
        f"{pe.CARD} {t('payment_instructions', lang, card_number=CARD_NUMBER, card_holder=CARD_HOLDER)}"
    )
    markup = card_payment_details_keyboard(
        kind="new", plan_id=plan_id, amount=final_price, card_number=CARD_NUMBER
    )
    await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")


async def back_to_payment_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = query.data.split(":", 1)[1]
    await _send_payment_step(update, context, plan_id)


async def ask_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    plan_id = query.data.split(":", 1)[1]
    context.user_data["discount_ctx"] = {"plan_id": plan_id}
    await query.edit_message_text(
        rs.hdr(pe.PRICE, "کد تخفیف", hint="کد تخفیفت رو بفرست."),
        reply_markup=back_to_menu_keyboard(),
        parse_mode="HTML",
    )
    return WAITING_DISCOUNT_CODE


async def receive_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ctx = context.user_data.get("discount_ctx")
    if not ctx:
        await update.message.reply_text("این عملیات دیگه معتبر نیست؛ دوباره از منو شروع کن.")
        return ConversationHandler.END

    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        ok, retry_after = sec.allow(f"tgheavy:{user_id}", BOT_HEAVY_ACTION_LIMIT, BOT_HEAVY_ACTION_WINDOW_SECONDS)
        if not ok:
            await update.message.reply_text(
                f"⏳ برای جلوگیری از حدس زدن پشت‌سرهم کد تخفیف، {int(retry_after) + 1} ثانیه‌ی دیگه صبر کن.",
                reply_markup=back_to_menu_keyboard(),
            )
            return WAITING_DISCOUNT_CODE

    code = update.message.text.strip().upper()
    user_id = update.effective_user.id
    ok, err, row = db.validate_discount_code(code, user_id)

    if not ok:
        error_texts = {
            "not_found": "این کد پیدا نشد. دوباره امتحان کن.",
            "inactive": "این کد دیگه فعال نیست.",
            "expired": "این کد منقضی شده.",
            "max_uses": "ظرفیت استفاده از این کد تموم شده.",
            "already_used": "تو قبلاً از این کد استفاده کردی.",
        }
        await update.message.reply_text(
            f"{pe.REJECT} {error_texts.get(err, 'این کد معتبر نیست.')}",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard() if err in ("not_found",) else None,
        )
        if err in ("not_found",):
            return WAITING_DISCOUNT_CODE
        # برای بقیه‌ی خطاها (منقضی/غیرفعال/تمام‌شده/استفاده‌شده) برگرد به صفحه‌ی پرداخت بدون کد
        await _send_payment_step(update, context, ctx["plan_id"])
        context.user_data.pop("discount_ctx", None)
        return ConversationHandler.END

    context.user_data["applied_discount"] = {
        "code": row["code"], "percent": row["percent"], "plan_id": ctx["plan_id"]
    }
    context.user_data.pop("discount_ctx", None)
    await _send_payment_step(update, context, ctx["plan_id"])
    return ConversationHandler.END


async def discount_code_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("discount_ctx", None)
    await update.message.reply_text("لغو شد.")
    return ConversationHandler.END


async def handle_discount_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("کد تخفیف حذف شد.")
    plan_id = query.data.split(":", 1)[1]
    context.user_data.pop("applied_discount", None)
    await _send_payment_step(update, context, plan_id)


async def handle_name_random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plan_id = query.data.split(":", 1)[1]
    context.user_data["pending_custom_name"] = None
    await _send_payment_step(update, context, plan_id)


async def ask_custom_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    plan_id = query.data.split(":", 1)[1]
    context.user_data["custom_name_ctx"] = {"plan_id": plan_id}
    await query.edit_message_text(
        rs.hdr(pe.MY_SERVICES, "اسم دلخواه سرویس",
               hint="اسمی که می‌خوای رو بفرست؛ فقط حروف انگلیسی، عدد و _ ، بدون فاصله، بین ۳ تا ۲۰ کاراکتر و با حرف شروع بشه.")
        + "\n" + rs._RLM + "مثال <code>alireza_vpn</code>",
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard(),
    )
    return WAITING_CUSTOM_NAME


async def receive_custom_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ctx = context.user_data.get("custom_name_ctx")
    if not ctx:
        await update.message.reply_text("یه مشکلی پیش اومد، از /start دوباره شروع کن.")
        return ConversationHandler.END

    cleaned = _sanitize_custom_name(update.message.text or "")
    if not cleaned:
        await update.message.reply_text(
            f"{pe.REJECT} اسم نامعتبره. فقط حروف انگلیسی، عدد و _ مجازه، بین ۳ تا ۲۰ کاراکتر "
            "و باید با حرف شروع بشه. دوباره بفرست.",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
        return WAITING_CUSTOM_NAME

    if db.username_taken(cleaned):
        await update.message.reply_text(
            f"{pe.REJECT} این اسم قبلاً برای یه سرویس دیگه گرفته شده؛ یه اسم دیگه بفرست.",
            parse_mode="HTML",
            reply_markup=back_to_menu_keyboard(),
        )
        return WAITING_CUSTOM_NAME

    plan_id = ctx["plan_id"]
    context.user_data["pending_custom_name"] = cleaned
    context.user_data.pop("custom_name_ctx", None)
    await _send_payment_step(update, context, plan_id)
    return ConversationHandler.END


# ---------------- شارژ کیف پول ----------------
async def ask_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not await check_and_prompt_join(update, context):
        return ConversationHandler.END

    await query.edit_message_text(
        rs.hdr(pe.CARD, "شارژ کیف پول", [("موجودی فعلی", f"{db.get_wallet_balance(update.effective_user.id):,} تومان")],
               "چند تومان می‌خوای شارژ کنی؟ فقط عدد بفرست (مثلا 100000)."),
        parse_mode="HTML",
        reply_markup=back_to_menu_keyboard(),
    )
    return WAITING_TOPUP_AMOUNT


async def receive_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip().replace(",", "").replace("،", "").replace(" ", "")
    if not raw.isdigit() or int(raw) <= 0:
        await update.message.reply_text(
            "❗️ لطفا فقط عدد معتبر بفرست (مثلا: 100000).",
            reply_markup=back_to_menu_keyboard(),
        )
        return WAITING_TOPUP_AMOUNT

    amount = int(raw)
    context.user_data["topup_amount"] = amount

    lang = db.get_user_language(update.effective_user.id)
    text = rs.hdr(
        pe.WALLET, "شارژ کیف پول",
        [(pe.CONFIRM, "مبلغ", f"{amount:,} تومان"), (pe.WALLET, "موجودی فعلی", f"{db.get_wallet_balance(update.effective_user.id):,} تومان")],
        "روش پرداخت رو انتخاب کن.\n✅ با درگاه «کارت به کارت تون پی» و «ویناپی»، شارژ کیف پولت خودکار تایید میشه.",
    )

    await update.message.reply_text(
        text, reply_markup=payment_method_keyboard(amount), parse_mode="HTML"
    )
    return ConversationHandler.END


async def handle_topup_card_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = db.get_user_language(update.effective_user.id)
    amount = int(query.data.split(":", 1)[1])
    context.user_data["topup_amount"] = amount

    text = (
        rs.hdr(pe.CARD, "شارژ کیف پول - کارت به کارت") + "\n\n"
        f"{pe.CONFIRM} {t('topup_amount_label', lang, amount=amount)}\n"
        f"{pe.PRICE} مبلغ (کامل و بدون تغییر واریز کن): <b>{amount * 10:,}</b> ریال\n\n"
        f"{pe.CARD} {t('topup_card_instructions', lang, card_number=CARD_NUMBER, card_holder=CARD_HOLDER)}"
    )
    await query.edit_message_text(
        text,
        reply_markup=card_payment_details_keyboard(
            kind="topup", plan_id="", amount=amount, card_number=CARD_NUMBER
        ),
        parse_mode="HTML",
    )


async def prompt_topup_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = db.get_user_language(update.effective_user.id)
    await query.edit_message_text(t("send_receipt_prompt", lang), reply_markup=back_to_menu_keyboard())
    return WAITING_TOPUP_RECEIPT


async def receive_topup_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    amount = context.user_data.get("topup_amount")
    if not amount:
        await update.message.reply_text("یه مشکلی پیش اومد، لطفا از /start دوباره شروع کن.")
        return ConversationHandler.END

    file_id = _extract_image_file_id(update.message)
    if not file_id:
        await update.message.reply_text(
            "لطفا فقط عکس رسید رو ارسال کن (به‌صورت عکس یا فایل تصویری، نه متن).",
            reply_markup=back_to_menu_keyboard(),
        )
        return WAITING_TOPUP_RECEIPT

    user = update.effective_user

    try:
        order_id = db.create_order(user.id, None, file_id, kind="topup", amount=amount)
    except Exception:
        logger.exception("ثبت سفارش شارژ کیف پول در دیتابیس ناموفق بود (کاربر %s)", user.id)
        await update.message.reply_text(
            f"{pe.REJECT} یه خطای فنی در ثبت درخواست پیش اومد.\n"
            "این معمولا یعنی دیتابیس نیاز به ریست داره (فایل bot_database.db رو پاک کن و ربات رو ری‌استارت کن).\n"
            "لطفا با پشتیبانی هم هماهنگ کن.",
            parse_mode="HTML",
        )
        context.user_data.pop("topup_amount", None)
        return ConversationHandler.END

    await update.message.reply_text(
        f"{pe.CONFIRM} رسید شارژ کیف پول دریافت شد و برای بررسی ارسال شد.\n"
        "به محض تایید، مبلغ به کیف پولت اضافه میشه و بهت خبر می‌دم.",
        parse_mode="HTML",
    )
    context.user_data.pop("topup_amount", None)

    caption = (
        f"💳 درخواست شارژ کیف پول\n"
        f"سفارش: #{order_id}\n"
        f"کاربر: {user.first_name or ''} (@{user.username or 'بدون‌یوزرنیم'})\n"
        f"آیدی عددی: {user.id}\n"
        f"مبلغ: {amount:,} تومان"
    )

    try:
        admin_msg = await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=file_id,
            caption=caption,
            reply_markup=admin_decision_keyboard(order_id),
        )
        db.set_order_admin_message(order_id, admin_msg.message_id)
    except Exception:
        logger.exception("ارسال رسید شارژ #%s به ادمین (ADMIN_CHAT_ID=%s) ناموفق بود", order_id, ADMIN_CHAT_ID)
        await update.message.reply_text(
            f"{pe.REJECT} درخواست #{order_id} ثبت شد ولی اطلاع‌رسانی به ادمین با خطا مواجه شد.\n"
            "این معمولا یعنی اکانت ادمین هنوز یک بار /start به ربات نزده.\n"
            "لطفا با پشتیبانی هماهنگ کن تا پیگیری بشه.",
            parse_mode="HTML",
        )

    return ConversationHandler.END


# ---------------- پرداخت مستقیم از کیف پول ----------------
async def pay_new_with_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not await check_and_prompt_join(update, context):
        return

    plan_id = query.data.split(":", 1)[1]
    plan = get_plan(plan_id)
    user = update.effective_user

    if not plan:
        await query.answer("پلن پیدا نشد.", show_alert=True)
        return

    discount = context.user_data.get("applied_discount")
    discount_active = bool(discount and discount.get("plan_id") == plan_id)
    final_price = round(plan["price"] * (100 - discount["percent"]) / 100) if discount_active else plan["price"]

    balance = db.get_wallet_balance(user.id)
    if balance < final_price:
        await query.answer(
            f"موجودی کافی نیست. موجودی فعلی: {balance:,} تومان؛ یا کیف پولت رو شارژ کن یا از روش‌های دیگه پرداخت کن.",
            show_alert=True,
        )
        return

    # کسر اتمیک قبل از ساخت سرویس: چند درخواست همزمان نمی‌تونن یک موجودی رو چندبار خرج کنن
    if not db.try_debit_wallet(user.id, final_price, "purchase", f"خرید {plan['title']}"):
        await query.answer(
            "موجودی کافی نیست؛ یا کیف پولت رو شارژ کن یا از روش‌های دیگه پرداخت کن.", show_alert=True
        )
        return
    if discount_active:
        used_ok, _err = db.consume_discount_use(discount["code"], user.id)
        if not used_ok:
            _refund_wallet_purchase(user.id, final_price, "برگشت مبلغ: کد تخفیف معتبر نبود")
            context.user_data.pop("applied_discount", None)
            await query.answer("کد تخفیف دیگه معتبر نیست؛ صفحه رو دوباره باز کن.", show_alert=True)
            return
    refund_code = discount["code"] if discount_active else None

    await query.answer("در حال صدور سرویس...")
    custom_name = context.user_data.pop("pending_custom_name", None)

    try:
        username = panel.generate_username(prefix=custom_name) if custom_name else panel.generate_username()
        result = await panel.create_user(username, plan["days"], plan["gb"], display_name=custom_name)
    except PanelError as e:
        _refund_wallet_purchase(user.id, final_price, "برگشت مبلغ: خطا در صدور سرویس", refund_code)
        await query.edit_message_text(
            f"{pe.REJECT} در صدور سرویس مشکلی پیش اومد:\n{pe.esc(e)}\nمبلغی از کیف پولت کم نشد.",
            parse_mode="HTML",
        )
        return
    except Exception:
        _refund_wallet_purchase(user.id, final_price, "برگشت مبلغ: خطای غیرمنتظره", refund_code)
        raise

    order_id = db.create_order(
        user.id, plan_id, None, kind="new", custom_name=custom_name,
        discount_code=discount["code"] if discount_active else None,
        discount_percent=discount["percent"] if discount_active else None,
    )
    db.set_order_status(order_id, "approved", user.id)
    if discount_active:
        context.user_data.pop("applied_discount", None)

    expire_at = result.get("expire") or 0
    sub_link = result.get("subscription_url", "")

    new_sub_id = db.create_subscription(
        user_id=user.id,
        order_id=order_id,
        plan_id=plan_id,
        marzban_username=username,
        plan_title=plan["title"],
        expire_at=expire_at,
        sub_link=sub_link,
    )
    db.maybe_reward_referrer(user.id)

    await query.edit_message_text(
        f"🎉 پرداخت با موفقیت از کیف پول انجام شد!\n"
        f"{pe.DOWN} موجودی باقیمانده: {db.get_wallet_balance(user.id):,} تومان",
        parse_mode="HTML",
    )
    await send_service_delivery(
        context.bot, user.id, plan, username, sub_link, expire_at=expire_at, sub_id=new_sub_id,
        connection_link=result.get("connection_link", ""),
    )
    await context.bot.send_message(
        chat_id=user.id,
        text=t("rating_ask_purchase", db.get_user_language(user.id)),
        reply_markup=rating_keyboard("purchase", new_sub_id),
        parse_mode="HTML",
    )

    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=(
            f"🔔 خرید با کیف پول (نیازی به تایید نیست)\n"
            f"کاربر: {user.first_name or ''} (@{user.username or 'بدون‌یوزرنیم'})\n"
            f"پلن: {plan['title']}\n"
            f"مبلغ: {final_price:,} تومان"
            + (f" (کد {discount['code']}، {discount['percent']}٪ تخفیف)" if discount_active else "")
        ),
    )


async def pay_renew_with_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if not await check_and_prompt_join(update, context):
        return

    _, sub_id_str, plan_id = query.data.split(":")
    sub_id = int(sub_id_str)
    plan = get_plan(plan_id)
    user = update.effective_user

    if not plan:
        await query.answer("پلن پیدا نشد.", show_alert=True)
        return

    balance = db.get_wallet_balance(user.id)
    if balance < plan["price"]:
        await query.answer(
            f"موجودی کافی نیست. موجودی فعلی: {balance:,} تومان؛ یا کیف پولت رو شارژ کن یا از روش‌های دیگه پرداخت کن.",
            show_alert=True,
        )
        return

    sub = db.get_subscription(sub_id)
    if not sub or sub["user_id"] != user.id:
        await query.answer("سرویس پیدا نشد.", show_alert=True)
        return

    # کسر اتمیک قبل از تمدید (جلوی خرج همزمان یک موجودی)
    if not db.try_debit_wallet(user.id, plan["price"], "purchase", f"تمدید {plan['title']}"):
        await query.answer("موجودی کافی نیست؛ یا کیف پولت رو شارژ کن یا از روش‌های دیگه پرداخت کن.", show_alert=True)
        return

    await query.answer("در حال تمدید سرویس...")

    try:
        result = await panel.modify_user(sub["marzban_username"], plan["days"], plan["gb"])
    except PanelError as e:
        _refund_wallet_purchase(user.id, plan["price"], "برگشت مبلغ: خطا در تمدید سرویس")
        await query.edit_message_text(
            f"{pe.REJECT} در تمدید سرویس مشکلی پیش اومد:\n{pe.esc(e)}\nمبلغی از کیف پولت کم نشد.",
            parse_mode="HTML",
        )
        return
    except Exception:
        _refund_wallet_purchase(user.id, plan["price"], "برگشت مبلغ: خطای غیرمنتظره")
        raise

    order_id = db.create_order(user.id, plan_id, None, kind="renew", renew_sub_id=sub_id)
    db.set_order_status(order_id, "approved", user.id)

    expire_at = result.get("expire") or 0
    db.update_subscription_after_renew(sub_id, expire_at, plan["title"], plan_id)

    total_gb = result.get("total_gb")
    volume_line = f"{pe.REMAINING} حجم کل بعد از تمدید: {total_gb:g} گیگابایت\n" if total_gb else ""
    await query.edit_message_text(
        f"🎉 سرویس با موفقیت تمدید شد (پرداخت از کیف پول)!\n\n"
        f"پلن جدید: {plan['emoji_tag']} {plan['title']}\n"
        f"{volume_line}"
        f"{pe.CONNECTION} لینک اتصال (بدون تغییر):\n{pe.esc(sub['sub_link'])}\n\n"
        f"{pe.DOWN} موجودی باقیمانده: {db.get_wallet_balance(user.id):,} تومان",
        parse_mode="HTML",
    )

    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=(
            f"🔔 تمدید با کیف پول (نیازی به تایید نیست)\n"
            f"کاربر: {user.first_name or ''} (@{user.username or 'بدون‌یوزرنیم'})\n"
            f"پلن: {plan['title']}\n"
            f"مبلغ: {plan['price']:,} تومان"
        ),
    )


# ---------------- پرداخت کریپتو (xRocket) ----------------
async def handle_cryptopay_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not CRYPTO_PAYMENT_ENABLED:
        await query.answer("این روش پرداخت فعلا غیرفعاله.", show_alert=True)
        return
    await query.answer()
    plan_id = query.data.split(":", 1)[1]
    plan = get_plan(plan_id)
    if not plan:
        await query.answer("پلن پیدا نشد.", show_alert=True)
        return
    discount = context.user_data.get("applied_discount")
    discount_active = bool(discount and discount.get("plan_id") == plan_id)
    price = round(plan["price"] * (100 - discount["percent"]) / 100) if discount_active else plan["price"]
    await query.edit_message_text(
        f"{pe.DIAMOND} انتخاب ارز پرداخت - xRocket\n\n{pe.PRICE} مبلغ: {price:,} تومان\n\n"
        "با کدام ارز می‌خواهید پرداخت کنید؟",
        reply_markup=crypto_currency_keyboard("new", plan_id),
        parse_mode="HTML",
    )


async def handle_cryptopay_renew(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not CRYPTO_PAYMENT_ENABLED:
        await query.answer("این روش پرداخت فعلا غیرفعاله.", show_alert=True)
        return
    await query.answer()
    _, sub_id_str, plan_id = query.data.split(":")
    plan = get_plan(plan_id)
    if not plan:
        await query.answer("پلن پیدا نشد.", show_alert=True)
        return
    await query.edit_message_text(
        f"{pe.DIAMOND} انتخاب ارز پرداخت - xRocket\n\n{pe.PRICE} مبلغ: {plan['price']:,} تومان\n\n"
        "با کدام ارز می‌خواهید پرداخت کنید؟",
        reply_markup=crypto_currency_keyboard("renew", f"{sub_id_str}:{plan_id}"),
        parse_mode="HTML",
    )


async def handle_cryptopay_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not CRYPTO_PAYMENT_ENABLED:
        await query.answer("این روش پرداخت فعلا غیرفعاله.", show_alert=True)
        return
    await query.answer()
    amount = query.data.split(":", 1)[1]
    await query.edit_message_text(
        f"{pe.DIAMOND} انتخاب ارز پرداخت - xRocket\n\n{pe.PRICE} مبلغ: {int(amount):,} تومان\n\n"
        "با کدام ارز می‌خواهید پرداخت کنید؟",
        reply_markup=crypto_currency_keyboard("topup", amount),
        parse_mode="HTML",
    )


async def handle_crypto_currency_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("در حال ساخت فاکتور...")
    parts = query.data.split(":")
    kind = parts[1]
    currency = parts[-1]
    user = update.effective_user

    if kind == "new":
        plan_id = parts[2]
        plan = get_plan(plan_id)
        discount = context.user_data.get("applied_discount")
        discount_active = bool(discount and discount.get("plan_id") == plan_id)
        amount_toman = round(plan["price"] * (100 - discount["percent"]) / 100) if discount_active else plan["price"]
        description = f"خرید {plan['title']}"
        extra = {
            "plan_id": plan_id,
            "custom_name": context.user_data.pop("pending_custom_name", None),
            "discount_code": discount["code"] if discount_active else None,
            "discount_percent": discount["percent"] if discount_active else None,
        }
        context.user_data.pop("applied_discount", None)
    elif kind == "renew":
        sub_id, plan_id = int(parts[2]), parts[3]
        plan = get_plan(plan_id)
        amount_toman = plan["price"]
        description = f"تمدید {plan['title']}"
        extra = {"plan_id": plan_id, "sub_id": sub_id}
    else:  # topup
        amount_toman = int(parts[2])
        description = "شارژ کیف پول"
        extra = {}

    try:
        invoice = await xrocket.create_invoice(amount_toman, currency, description)
    except xrocket.XRocketError as e:
        await query.edit_message_text(f"⚠️ خطا در ساخت فاکتور: {e}")
        return

    coin_icon_key = CRYPTO_CURRENCY_ICON.get(currency, "GEM")
    msg = await query.edit_message_text(
        f"{pe.DIAMOND} فاکتور پرداخت xRocket\n\n"
        f"{pe.PRICE} مبلغ: {amount_toman:,} تومان\n"
        f"{pe.RAW.get(coin_icon_key, '🪙')} معادل: {invoice['amount_crypto']:g} {CRYPTO_CURRENCY_LABELS.get(currency, currency)}\n\n"
        f"از دکمه‌ی زیر در ربات xRocket پرداخت را انجام دهید.\n"
        f"{pe.HOURGLASS2} تا {CRYPTO_INVOICE_TIMEOUT_MINUTES} دقیقه پرداخت به‌صورت خودکار بررسی می‌شود؛ "
        f"در غیر این‌صورت دکمه‌ی «بررسی پرداخت» را بزنید.",
        reply_markup=crypto_payment_keyboard(invoice["pay_url"], f"cryptocheck:{invoice['invoice_id']}"),
        parse_mode="HTML",
    )

    db.create_crypto_invoice(
        invoice_id=invoice["invoice_id"],
        user_id=user.id,
        chat_id=update.effective_chat.id,
        message_id=msg.message_id,
        kind=kind,
        amount_toman=amount_toman,
        currency=currency,
        amount_crypto=invoice["amount_crypto"],
        plan_id=extra.get("plan_id"),
        sub_id=extra.get("sub_id"),
        custom_name=extra.get("custom_name"),
        discount_code=extra.get("discount_code"),
        discount_percent=extra.get("discount_percent"),
    )


async def _claim_and_fulfill(key, claim, release, inner, context, inv) -> str:
    """
    تحویل «دقیقاً یک‌بار» برای فاکتورهای پرداخت: قبل از هر کاری فاکتور به‌صورت اتمیک pending → paid میشه و فقط
    کسی که برنده شد خدمت رو تحویل میده؛ وب‌هوک، جاب دوره‌ای و دکمه‌ی «بررسی» نمی‌تونن همزمان دوبار تحویل بدن.
    اگه تحویل به‌خاطر خطا (پنل و ...) انجام نشد، فاکتور برمی‌گرده به pending تا دوباره تلاش بشه.
    """
    if not claim(key):
        return "✅ این پرداخت قبلاً تایید و تحویل داده شده."
    try:
        text = await inner(context, inv)
    except Exception:
        release(key)
        raise
    if isinstance(text, str) and text.startswith("⚠️"):
        release(key)
    return text


async def _fulfill_crypto_invoice(context, inv) -> str:
    return await _claim_and_fulfill(
        inv["invoice_id"], db.claim_crypto_invoice, db.release_crypto_invoice, _fulfill_crypto_invoice_inner, context, inv
    )


async def _fulfill_tonpays_invoice(context, inv) -> str:
    return await _claim_and_fulfill(
        inv["invoice_id"], db.claim_tonpays_invoice, db.release_tonpays_invoice, _fulfill_tonpays_invoice_inner, context, inv
    )


async def _fulfill_autosms_invoice(context, inv) -> str:
    return await _claim_and_fulfill(
        inv["authority"], db.claim_autosms_invoice, db.release_autosms_invoice, _fulfill_autosms_invoice_inner, context, inv
    )


def _refund_wallet_purchase(user_id: int, amount: int, description: str, discount_code: str = None):
    """برگشت مبلغی که قبل از صدور سرویس کسر شده بود (و مصرف کد تخفیف)، وقتی صدور سرویس خطا بده"""
    db.adjust_wallet_balance_logged(user_id, amount, "refund", description)
    if discount_code:
        db.release_discount_use(discount_code, user_id)


async def _fulfill_crypto_invoice_inner(context: ContextTypes.DEFAULT_TYPE, inv) -> str:
    """
    فاکتور پرداخت‌شده رو نهایی می‌کنه (صدور/تمدید سرویس یا شارژ کیف پول).
    خروجی: متن پیام نهایی برای نمایش/ارسال به کاربر.
    """
    user_id = inv["user_id"]
    kind = inv["kind"]

    if kind == "new":
        plan = get_plan(inv["plan_id"])
        custom_name = inv["custom_name"] if "custom_name" in inv.keys() else None
        discount_code = inv["discount_code"] if "discount_code" in inv.keys() else None
        discount_percent = inv["discount_percent"] if "discount_percent" in inv.keys() else None
        try:
            username = panel.generate_username(prefix=custom_name) if custom_name else panel.generate_username()
            result = await panel.create_user(username, plan["days"], plan["gb"], display_name=custom_name)
        except PanelError as e:
            return f"⚠️ پرداخت تایید شد ولی صدور سرویس خطا داد: {e}\nبا پشتیبانی تماس بگیر."
        order_id = db.create_order(
            user_id, inv["plan_id"], None, kind="new", custom_name=custom_name,
            discount_code=discount_code, discount_percent=discount_percent,
        )
        db.set_order_status(order_id, "approved", user_id)
        if discount_code:
            db.record_discount_use(discount_code, user_id)
        expire_at = result.get("expire") or 0
        sub_link = result.get("subscription_url", "")
        new_sub_id = db.create_subscription(
            user_id=user_id, order_id=order_id, plan_id=inv["plan_id"], marzban_username=username,
            plan_title=plan["title"], expire_at=expire_at, sub_link=sub_link,
        )
        db.maybe_reward_referrer(user_id)
        await send_service_delivery(
            context.bot, user_id, plan, username, sub_link, expire_at=expire_at, sub_id=new_sub_id,
            connection_link=result.get("connection_link", ""),
        )
        await context.bot.send_message(
            chat_id=user_id,
            text=t("rating_ask_purchase", db.get_user_language(user_id)),
            reply_markup=rating_keyboard("purchase", new_sub_id),
            parse_mode="HTML",
        )
        text = "🎉 پرداخت تایید شد و سرویس صادر شد! جزئیات در پیام بعدی."

    elif kind == "renew":
        plan = get_plan(inv["plan_id"])
        sub = db.get_subscription(inv["sub_id"])
        try:
            result = await panel.modify_user(sub["marzban_username"], plan["days"], plan["gb"])
        except PanelError as e:
            return f"⚠️ پرداخت تایید شد ولی تمدید خطا داد: {e}\nبا پشتیبانی تماس بگیر."
        order_id = db.create_order(user_id, inv["plan_id"], None, kind="renew", renew_sub_id=inv["sub_id"])
        db.set_order_status(order_id, "approved", user_id)
        expire_at = result.get("expire") or 0
        sub_link = result.get("subscription_url", "")
        db.update_subscription_after_renew(inv["sub_id"], expire_at, plan["title"], inv["plan_id"])
        if sub_link:
            db.update_subscription_link(inv["sub_id"], sub_link)
        await send_service_delivery(
            context.bot, user_id, _plan_with_actual_gb(plan, result), sub["marzban_username"], sub_link or sub["sub_link"],
            "تمدید", expire_at=expire_at, sub_id=inv["sub_id"],
            connection_link=result.get("connection_link", ""),
        )
        text = "🎉 پرداخت تایید شد و سرویس تمدید شد! جزئیات در پیام بعدی."

    else:  # topup
        amount = inv["amount_toman"]
        order_id = db.create_order(user_id, None, None, kind="topup", amount=amount)
        db.set_order_status(order_id, "approved", user_id)
        db.adjust_wallet_balance_logged(user_id, amount, "topup", f"شارژ کریپتو - فاکتور #{order_id}")
        text = f"🎉 کیف پول با موفقیت شارژ شد!\nموجودی جدید: {db.get_wallet_balance(user_id):,} تومان"

    db.set_crypto_invoice_status(inv["invoice_id"], "paid")
    return text


async def handle_crypto_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("در حال بررسی...")
    invoice_id = query.data.split(":", 1)[1]

    inv = db.get_crypto_invoice(invoice_id)
    if not inv:
        await query.answer("فاکتور پیدا نشد.", show_alert=True)
        return
    if inv["status"] == "paid":
        await query.answer("این فاکتور قبلا تایید شده.", show_alert=True)
        return
    if inv["status"] == "expired":
        await query.edit_message_text("⌛ این فاکتور منقضی شده. دوباره از منو تلاش کن.")
        return

    try:
        status = await xrocket.check_invoice(invoice_id)
    except xrocket.XRocketError as e:
        await query.answer(f"خطا در بررسی: {e}", show_alert=True)
        return

    if status == "pending":
        await query.answer("هنوز پرداختی ثبت نشده. چند لحظه دیگه دوباره امتحان کن.", show_alert=True)
        return
    if status == "expired":
        db.set_crypto_invoice_status(invoice_id, "expired")
        await query.edit_message_text("⌛ این فاکتور منقضی شده. دوباره از منو تلاش کن.")
        return

    text = await _fulfill_crypto_invoice(context, inv)
    await query.edit_message_text(text, parse_mode="HTML")


# ==================== پرداخت TonPays (فاکتور هاست‌شده) ====================
# کاملاً مستقل از AutoSMS/کریپتو/کارت‌به‌کارت دستی.

def _tonpays_callback_url() -> str:
    """اگه PUBLIC_BASE_URL تنظیم نشده باشه، وب‌هوک آنی کار نمی‌کنه ولی job دوره‌ای
    (check_pending_tonpays_job) همچنان به‌درستی و مستقل فاکتورها رو نهایی می‌کنه."""
    if not PUBLIC_BASE_URL:
        return None
    return f"{PUBLIC_BASE_URL}/webhook/tonpays"


async def _start_tonpays_invoice(
    update: Update, context: ContextTypes.DEFAULT_TYPE, *, kind: str, amount_toman: int,
    plan_id: str = None, sub_id: int = None, custom_name: str = None,
    discount_code: str = None, discount_percent: int = None,
):
    query = update.callback_query
    if not TONPAYS_ENABLED:
        await query.answer("این روش پرداخت فعلا غیرفعاله.", show_alert=True)
        return

    await query.answer("در حال ساخت فاکتور...")
    user = update.effective_user
    order_id = tonpays.make_order_id()

    try:
        invoice = await tonpays.create_invoice(amount_toman, order_id, callback_url=_tonpays_callback_url())
    except tonpays.TonPaysError as e:
        await query.edit_message_text(f"⚠️ خطا در ساخت فاکتور: {e}")
        return

    try:
        invoice_id = invoice["invoice_id"]
        final_amount = invoice.get("final_amount") or amount_toman
        request_amount = invoice.get("request_amount") or amount_toman

        lines = [
            f"{pe.TOP} فاکتور کارت به کارت تون پی",
            "",
            f"{pe.PRICE} مبلغ قابل پرداخت: <b>{final_amount:,}</b> تومان",
            "💡 <i>درگاه TonPays\u200f ۱۰٪ از هر تراکنش کارمزد می‌گیره؛ برای همینه که مبلغ کمی بیشتر از قیمت پلنه‌ست.</i>",
        ]
        if invoice.get("card_number"):
            lines.append(f"{pe.CARD} شماره کارت: <code>{pe.esc(invoice['card_number'])}</code>")
        if invoice.get("card_name"):
            lines.append(f"👤 به نام: {pe.esc(invoice['card_name'])}")
        lines += [
            "",
            f"👇 از دکمه‌ی زیر وارد صفحه‌ی پرداخت TonPays\u200f شو و پرداخت رو انجام بده؛ "
            "بعدش دکمه‌ی «پرداخت کردم، بررسی کن» رو بزن.",
            "✅ نیازی به ارسال رسید نیست؛ بعد از پرداخت، تراکنش به‌صورت خودکار تایید و سرویس/شارژ صادر میشه.",
        ]
        text = "\n".join(lines)

        msg = await query.edit_message_text(
            text,
            reply_markup=tonpays_payment_keyboard(invoice["invoice_url"], f"tpcheck:{invoice_id}"),
            parse_mode="HTML",
        )

        db.create_tonpays_invoice(
            invoice_id=invoice_id, order_id=order_id, user_id=user.id, chat_id=update.effective_chat.id,
            message_id=msg.message_id, kind=kind, request_amount=request_amount, final_amount=final_amount,
            plan_id=plan_id, sub_id=sub_id, custom_name=custom_name,
            discount_code=discount_code, discount_percent=discount_percent,
        )
    except Exception as e:
        logger.exception("ساخت فاکتور TonPays برای kind=%s ناموفق بود: %s", kind, e)
        try:
            await query.edit_message_text(
                f"⚠️ فاکتور تو درگاه ساخته شد ولی توی ثبتش تو ربات خطا افتاد: {e}\n"
                "لطفاً این پیام رو برای پشتیبانی بفرست تا دستی بررسی بشه."
            )
        except Exception:
            pass


async def handle_tonpays_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_id = update.callback_query.data.split(":", 1)[1]
    plan = get_plan(plan_id)
    if not plan:
        await update.callback_query.answer("پلن پیدا نشد.", show_alert=True)
        return
    discount = context.user_data.get("applied_discount")
    discount_active = bool(discount and discount.get("plan_id") == plan_id)
    amount = round(plan["price"] * (100 - discount["percent"]) / 100) if discount_active else plan["price"]
    await _start_tonpays_invoice(
        update, context, kind="new", amount_toman=amount,
        plan_id=plan_id, custom_name=context.user_data.pop("pending_custom_name", None),
        discount_code=discount["code"] if discount_active else None,
        discount_percent=discount["percent"] if discount_active else None,
    )
    context.user_data.pop("applied_discount", None)


async def handle_tonpays_renew(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _, sub_id_str, plan_id = update.callback_query.data.split(":")
    plan = get_plan(plan_id)
    if not plan:
        await update.callback_query.answer("پلن پیدا نشد.", show_alert=True)
        return
    await _start_tonpays_invoice(
        update, context, kind="renew", amount_toman=plan["price"],
        plan_id=plan_id, sub_id=int(sub_id_str),
    )


async def handle_tonpays_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount = int(update.callback_query.data.split(":", 1)[1])
    await _start_tonpays_invoice(update, context, kind="topup", amount_toman=amount)


async def _fulfill_tonpays_invoice_inner(context, inv) -> str:
    """فاکتور پرداخت‌شده رو نهایی می‌کنه (صدور/تمدید سرویس یا شارژ کیف‌پول)"""
    user_id = inv["user_id"]
    kind = inv["kind"]
    db.set_tonpays_invoice_status(inv["invoice_id"], "paid")

    if kind == "new":
        plan = get_plan(inv["plan_id"])
        custom_name = inv["custom_name"] if "custom_name" in inv.keys() else None
        discount_code = inv["discount_code"] if "discount_code" in inv.keys() else None
        discount_percent = inv["discount_percent"] if "discount_percent" in inv.keys() else None
        try:
            username = panel.generate_username(prefix=custom_name) if custom_name else panel.generate_username()
            result = await panel.create_user(username, plan["days"], plan["gb"], display_name=custom_name)
        except PanelError as e:
            return f"⚠️ پرداخت تایید شد ولی صدور سرویس خطا داد: {e}\nبا پشتیبانی تماس بگیر."
        order_id = db.create_order(
            user_id, inv["plan_id"], None, kind="new", custom_name=custom_name,
            discount_code=discount_code, discount_percent=discount_percent,
        )
        db.set_order_status(order_id, "approved", user_id)
        if discount_code:
            db.record_discount_use(discount_code, user_id)
        expire_at = result.get("expire") or 0
        sub_link = result.get("subscription_url", "")
        new_sub_id = db.create_subscription(
            user_id=user_id, order_id=order_id, plan_id=inv["plan_id"], marzban_username=username,
            plan_title=plan["title"], expire_at=expire_at, sub_link=sub_link,
        )
        db.maybe_reward_referrer(user_id)
        await send_service_delivery(
            context.bot, user_id, plan, username, sub_link, expire_at=expire_at, sub_id=new_sub_id,
            connection_link=result.get("connection_link", ""),
        )
        await context.bot.send_message(
            chat_id=user_id,
            text=t("rating_ask_purchase", db.get_user_language(user_id)),
            reply_markup=rating_keyboard("purchase", new_sub_id),
            parse_mode="HTML",
        )
        text = "🎉 پرداخت تایید شد و سرویس صادر شد! جزئیات در پیام بعدی."

    elif kind == "renew":
        plan = get_plan(inv["plan_id"])
        sub = db.get_subscription(inv["sub_id"])
        try:
            result = await panel.modify_user(sub["marzban_username"], plan["days"], plan["gb"])
        except PanelError as e:
            return f"⚠️ پرداخت تایید شد ولی تمدید خطا داد: {e}\nبا پشتیبانی تماس بگیر."
        order_id = db.create_order(user_id, inv["plan_id"], None, kind="renew", renew_sub_id=inv["sub_id"])
        db.set_order_status(order_id, "approved", user_id)
        expire_at = result.get("expire") or 0
        sub_link = result.get("subscription_url", "")
        db.update_subscription_after_renew(inv["sub_id"], expire_at, plan["title"], inv["plan_id"])
        if sub_link:
            db.update_subscription_link(inv["sub_id"], sub_link)
        await send_service_delivery(
            context.bot, user_id, _plan_with_actual_gb(plan, result), sub["marzban_username"], sub_link or sub["sub_link"],
            "تمدید", expire_at=expire_at, sub_id=inv["sub_id"],
            connection_link=result.get("connection_link", ""),
        )
        text = "🎉 پرداخت تایید شد و سرویس تمدید شد! جزئیات در پیام بعدی."

    else:  # topup
        amount = inv["final_amount"] if "final_amount" in inv.keys() else inv["request_amount"]
        order_id = db.create_order(user_id, None, None, kind="topup", amount=amount)
        db.set_order_status(order_id, "approved", user_id)
        db.adjust_wallet_balance_logged(user_id, amount, "topup", f"شارژ TonPays - فاکتور #{order_id}")
        text = f"🎉 کیف پول با موفقیت شارژ شد!\nموجودی جدید: {db.get_wallet_balance(user_id):,} تومان"

    return text


async def handle_tonpays_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("در حال بررسی...")
    invoice_id = query.data.split(":", 1)[1]

    inv = db.get_tonpays_invoice(invoice_id)
    if not inv:
        await query.answer("فاکتور پیدا نشد.", show_alert=True)
        return
    if inv["status"] == "paid":
        await query.answer("این فاکتور قبلاً تایید و تحویل داده شده.", show_alert=True)
        return
    if inv["status"] == "expired":
        await query.edit_message_text("⌛ این فاکتور منقضی شده. دوباره از منو تلاش کن.")
        return

    try:
        result = await tonpays.check_invoice(invoice_id)
    except tonpays.TonPaysError as e:
        await query.answer(f"خطا در بررسی: {e}", show_alert=True)
        return

    if tonpays.is_terminal_failure(result.get("status")):
        db.set_tonpays_invoice_status(invoice_id, "expired")
        await query.edit_message_text("⌛ این فاکتور منقضی/لغو شده. دوباره از منو تلاش کن.")
        return

    if not result.get("paid"):
        await query.answer("هنوز پرداختی تایید نشده. چند لحظه دیگه دوباره امتحان کن.", show_alert=True)
        return

    # paid=True و از سرور TonPays با کلید API خودمون استعلام شده - قابل‌اعتماده
    fresh = db.get_tonpays_invoice(invoice_id)
    if fresh["status"] == "paid":
        await query.answer("این فاکتور قبلاً تایید و تحویل داده شده.", show_alert=True)
        return
    text = await _fulfill_tonpays_invoice(context, fresh)
    await query.edit_message_text(text, parse_mode="HTML")


async def check_pending_tonpays_job(context: ContextTypes.DEFAULT_TYPE):
    """هر چند ثانیه یک‌بار اجرا میشه؛ فاکتورهای پرداخت‌نشده‌ی TonPays رو با کلید
    API خودمون از سرور TonPays استعلام می‌گیره (پشتیبان وب‌هوک - حتی اگه وب‌هوک
    نرسه یا PUBLIC_BASE_URL تنظیم نشده باشه، تحویل همینجا نهایی میشه)"""
    pending = db.get_pending_tonpays_invoices()
    now = int(time.time())

    for inv in pending:
        if inv["created_at"] and now - inv["created_at"] > TONPAYS_INVOICE_TIMEOUT_MINUTES * 60:
            db.set_tonpays_invoice_status(inv["invoice_id"], "expired")
            try:
                await context.bot.send_message(
                    chat_id=inv["chat_id"],
                    text="⌛ فاکتور پرداخت TonPays\u200f‌ت منقضی شد. اگه هنوز می‌خوای پرداخت کنی، دوباره از منو تلاش کن.",
                )
            except Exception:
                logger.warning("اطلاع‌رسانی انقضای فاکتور TonPays #%s ناموفق بود", inv["invoice_id"])
            continue

        try:
            result = await tonpays.check_invoice(inv["invoice_id"])
        except tonpays.TonPaysError:
            continue

        if tonpays.is_terminal_failure(result.get("status")):
            db.set_tonpays_invoice_status(inv["invoice_id"], "expired")
            continue

        if result.get("paid"):
            fresh = db.get_tonpays_invoice(inv["invoice_id"])
            if fresh["status"] == "paid":
                continue
            text = await _fulfill_tonpays_invoice(context, fresh)
            try:
                await context.bot.send_message(chat_id=inv["chat_id"], text=text, parse_mode="HTML")
            except Exception:
                logger.warning("اطلاع‌رسانی پرداخت TonPays فاکتور #%s ناموفق بود", inv["invoice_id"])


# ==================== پرداخت خودکار کارت‌به‌کارت (AutoSMS) ====================
# کاملاً مستقل از کارت‌به‌کارت دستی (pay:/renewpay:/topupcard:) و از کریپتوئه.

def _autosms_amount_error(amount_toman: int) -> str:
    if amount_toman < AUTOSMS_MIN_AMOUNT_TOMAN:
        return f"⚠️ حداقل مبلغ پرداخت خودکار {AUTOSMS_MIN_AMOUNT_TOMAN:,} تومانه."
    if amount_toman > AUTOSMS_MAX_AMOUNT_TOMAN:
        return f"⚠️ حداکثر مبلغ پرداخت خودکار {AUTOSMS_MAX_AMOUNT_TOMAN:,} تومانه."
    return ""


async def _start_autosms_invoice(
    update: Update, context: ContextTypes.DEFAULT_TYPE, *, kind: str, amount_toman: int,
    description: str, plan_id: str = None, sub_id: int = None, custom_name: str = None,
    discount_code: str = None, discount_percent: int = None,
):
    query = update.callback_query
    if not AUTOSMS_ENABLED:
        await query.answer("این روش پرداخت فعلا غیرفعاله.", show_alert=True)
        return

    err = _autosms_amount_error(amount_toman)
    if err:
        await query.answer(err, show_alert=True)
        return

    await query.answer("در حال ساخت فاکتور...")
    user = update.effective_user
    order_id = autosms.make_order_id(kind, user.id)

    try:
        inv_data = await autosms.create_payment(
            amount_toman, order_id, description, ttl_minutes=AUTOSMS_INVOICE_TTL_MINUTES
        )
    except autosms.AutoSMSError as e:
        await query.edit_message_text(f"⚠️ خطا در ساخت فاکتور: {e}")
        return

    try:
        authority = inv_data["authority"]
        pay_amount = inv_data["pay_amount_toman"]
        pay_amount_rial = inv_data.get("pay_amount_rial", pay_amount * 10)
        card_number = inv_data["card_number"]
        card_holder = inv_data["card_holder"]
        expires_ts = inv_data.get("expires_at", 0)
        if expires_ts:
            expires_at_dt = datetime.datetime.fromtimestamp(
                expires_ts, tz=ZoneInfo("Asia/Tehran")
            ).strftime("%H:%M - %Y/%m/%d")
        else:
            expires_at_dt = ""

        text = (
            f"{pe.LIGHTNING} پرداخت خودکار کارت‌به‌کارت\n\n"
            f"{pe.PRICE} مبلغ دقیق (این مبلغ رو حتماً کامل و بدون تغییر واریز کن): "
            f"<b>{pay_amount_rial:,}</b> ریال (معادل {pay_amount:,} تومان)\n"
            f"{pe.CARD} شماره کارت: <code>{card_number}</code>\n"
            f"👤 به نام: {pe.esc(card_holder)}\n"
            f"{pe.HOURGLASS2} مهلت پرداخت تا: {pe.esc(expires_at_dt)}\n\n"
            "بلافاصله بعد از واریز، تاییدش خودکاره و نیازی به ارسال رسید نیست؛ "
            "چند لحظه صبر کن یا دکمه‌ی «بررسی پرداخت» رو بزن.\n\n"
            "⚠️ دکمه‌ی «ارسال رسید پرداخت» رو فقط و فقط در صورتی بزن که "
            "بعد از گذشت یک ساعت از واریز، تراکنشت هنوز به‌صورت خودکار تایید نشده باشه."
        )
        msg = await query.edit_message_text(
            text,
            reply_markup=autosms_payment_keyboard(authority, card_number, pay_amount_rial, kind=kind),
            parse_mode="HTML",
        )

        db.create_autosms_invoice(
            authority=authority, order_id=order_id, user_id=user.id, chat_id=update.effective_chat.id,
            message_id=msg.message_id, kind=kind, base_amount_toman=amount_toman, pay_amount_toman=pay_amount,
            card_number=card_number, card_holder=card_holder, expires_at=inv_data.get("expires_at", 0),
            plan_id=plan_id, sub_id=sub_id, custom_name=custom_name,
            discount_code=discount_code, discount_percent=discount_percent,
        )
    except Exception as e:
        logger.exception("ساخت فاکتور AutoSMS برای kind=%s ناموفق بود: %s", kind, e)
        try:
            await query.edit_message_text(
                f"⚠️ فاکتور تو درگاه ساخته شد ولی توی ثبتش تو ربات خطا افتاد: {e}\n"
                "لطفاً این پیام رو برای پشتیبانی بفرست تا دستی بررسی بشه."
            )
        except Exception:
            pass


async def handle_autosms_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_id = update.callback_query.data.split(":", 1)[1]
    plan = get_plan(plan_id)
    if not plan:
        await update.callback_query.answer("پلن پیدا نشد.", show_alert=True)
        return
    discount = context.user_data.get("applied_discount")
    discount_active = bool(discount and discount.get("plan_id") == plan_id)
    amount = round(plan["price"] * (100 - discount["percent"]) / 100) if discount_active else plan["price"]
    await _start_autosms_invoice(
        update, context, kind="new", amount_toman=amount, description=f"خرید {plan['title']}",
        plan_id=plan_id, custom_name=context.user_data.pop("pending_custom_name", None),
        discount_code=discount["code"] if discount_active else None,
        discount_percent=discount["percent"] if discount_active else None,
    )
    context.user_data.pop("applied_discount", None)


async def handle_autosms_renew(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _, sub_id_str, plan_id = update.callback_query.data.split(":")
    plan = get_plan(plan_id)
    if not plan:
        await update.callback_query.answer("پلن پیدا نشد.", show_alert=True)
        return
    await _start_autosms_invoice(
        update, context, kind="renew", amount_toman=plan["price"], description=f"تمدید {plan['title']}",
        plan_id=plan_id, sub_id=int(sub_id_str),
    )


async def handle_autosms_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount = int(update.callback_query.data.split(":", 1)[1])
    await _start_autosms_invoice(
        update, context, kind="topup", amount_toman=amount, description="شارژ کیف پول",
    )


async def _fulfill_autosms_invoice_inner(context, inv) -> str:
    """فاکتور پرداخت‌شده رو نهایی می‌کنه؛ خروجی متن پیام نهایی برای کاربره"""
    user_id = inv["user_id"]
    kind = inv["kind"]
    db.set_autosms_invoice_status(inv["authority"], "paid")

    if kind == "new":
        plan = get_plan(inv["plan_id"])
        custom_name = inv["custom_name"] if "custom_name" in inv.keys() else None
        discount_code = inv["discount_code"] if "discount_code" in inv.keys() else None
        discount_percent = inv["discount_percent"] if "discount_percent" in inv.keys() else None
        try:
            username = panel.generate_username(prefix=custom_name) if custom_name else panel.generate_username()
            result = await panel.create_user(username, plan["days"], plan["gb"], display_name=custom_name)
        except PanelError as e:
            return f"⚠️ پرداخت تایید شد ولی صدور سرویس خطا داد: {e}\nبا پشتیبانی تماس بگیر."
        order_id = db.create_order(
            user_id, inv["plan_id"], None, kind="new", custom_name=custom_name,
            discount_code=discount_code, discount_percent=discount_percent,
        )
        db.set_order_status(order_id, "approved", user_id)
        if discount_code:
            db.record_discount_use(discount_code, user_id)
        expire_at = result.get("expire") or 0
        sub_link = result.get("subscription_url", "")
        new_sub_id = db.create_subscription(
            user_id=user_id, order_id=order_id, plan_id=inv["plan_id"], marzban_username=username,
            plan_title=plan["title"], expire_at=expire_at, sub_link=sub_link,
        )
        db.maybe_reward_referrer(user_id)
        await send_service_delivery(
            context.bot, user_id, plan, username, sub_link, expire_at=expire_at, sub_id=new_sub_id,
            connection_link=result.get("connection_link", ""),
        )
        await context.bot.send_message(
            chat_id=user_id,
            text=t("rating_ask_purchase", db.get_user_language(user_id)),
            reply_markup=rating_keyboard("purchase", new_sub_id),
            parse_mode="HTML",
        )
        text = "🎉 پرداخت تایید شد و سرویس صادر شد! جزئیات در پیام بعدی."

    elif kind == "renew":
        plan = get_plan(inv["plan_id"])
        sub = db.get_subscription(inv["sub_id"])
        try:
            result = await panel.modify_user(sub["marzban_username"], plan["days"], plan["gb"])
        except PanelError as e:
            return f"⚠️ پرداخت تایید شد ولی تمدید خطا داد: {e}\nبا پشتیبانی تماس بگیر."
        order_id = db.create_order(user_id, inv["plan_id"], None, kind="renew", renew_sub_id=inv["sub_id"])
        db.set_order_status(order_id, "approved", user_id)
        expire_at = result.get("expire") or 0
        sub_link = result.get("subscription_url", "")
        db.update_subscription_after_renew(inv["sub_id"], expire_at, plan["title"], inv["plan_id"])
        if sub_link:
            db.update_subscription_link(inv["sub_id"], sub_link)
        await send_service_delivery(
            context.bot, user_id, _plan_with_actual_gb(plan, result), sub["marzban_username"], sub_link or sub["sub_link"],
            "تمدید", expire_at=expire_at, sub_id=inv["sub_id"],
            connection_link=result.get("connection_link", ""),
        )
        text = "🎉 پرداخت تایید شد و سرویس تمدید شد! جزئیات در پیام بعدی."

    else:  # topup
        amount = inv["base_amount_toman"]
        order_id = db.create_order(user_id, None, None, kind="topup", amount=amount)
        db.set_order_status(order_id, "approved", user_id)
        db.adjust_wallet_balance_logged(user_id, amount, "topup", f"شارژ خودکار - فاکتور #{order_id}")
        text = f"🎉 کیف پول با موفقیت شارژ شد!\nموجودی جدید: {db.get_wallet_balance(user_id):,} تومان"

    return text


async def handle_autosms_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("در حال بررسی...")
    authority = query.data.split(":", 1)[1]

    inv = db.get_autosms_invoice(authority)
    if not inv:
        await query.answer("فاکتور پیدا نشد.", show_alert=True)
        return
    if inv["status"] == "paid":
        await query.answer("این فاکتور قبلاً تایید و تحویل داده شده.", show_alert=True)
        return
    if inv["status"] == "expired":
        await query.edit_message_text("⌛ این فاکتور منقضی شده. دوباره از منو تلاش کن.")
        return
    if inv["status"] == "manual_review":
        await query.answer("رسیدت الان دست ادمینه برای بررسی؛ لطفا صبر کن.", show_alert=True)
        return

    try:
        status = await autosms.check_status(authority, known_status="pending")
    except autosms.AutoSMSError as e:
        await query.answer(f"خطا در بررسی: {e}", show_alert=True)
        return

    if status == "pending":
        await query.answer("هنوز پرداختی تشخیص داده نشده. چند لحظه دیگه دوباره امتحان کن.", show_alert=True)
        return
    if status == "expired":
        db.set_autosms_invoice_status(authority, "expired")
        await query.edit_message_text("⌛ این فاکتور منقضی شده. دوباره از منو تلاش کن.")
        return

    # paid
    if inv["status"] != "paid":
        text = await _fulfill_autosms_invoice(context, inv)
        await query.edit_message_text(text, parse_mode="HTML")


async def handle_autosms_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    authority = query.data.split(":", 1)[1]
    inv = db.get_autosms_invoice(authority)
    if inv and inv["status"] == "pending":
        db.set_autosms_invoice_status(authority, "expired")
    await query.edit_message_text("پرداخت لغو شد. هر وقت خواستی دوباره از منو تلاش کن.")


async def check_pending_autosms_job(context: ContextTypes.DEFAULT_TYPE):
    """هر چند دقیقه یک‌بار اجرا میشه؛ فاکتورهای پرداخت‌نشده‌ی خودکار رو بررسی می‌کنه
    (پشتیبان وب‌هوک - حتی اگه وب‌هوک نرسه یا تنظیم نشده باشه، همین جا نهایی می‌شن)"""
    pending = db.get_pending_autosms_invoices()
    now = int(time.time())

    for inv in pending:
        if inv["expires_at"] and now > inv["expires_at"]:
            db.set_autosms_invoice_status(inv["authority"], "expired")
            try:
                await context.bot.send_message(
                    chat_id=inv["chat_id"],
                    text="⌛ فاکتور پرداخت خودکارت منقضی شد. اگه هنوز می‌خوای پرداخت کنی، دوباره از منو تلاش کن.",
                )
            except Exception:
                logger.warning("اطلاع‌رسانی انقضای فاکتور AutoSMS #%s ناموفق بود", inv["authority"])
            continue

        try:
            status = await autosms.check_status(inv["authority"], known_status="pending")
        except autosms.AutoSMSError:
            continue

        if status == "paid":
            fresh = db.get_autosms_invoice(inv["authority"])
            if fresh["status"] == "paid":
                continue
            text = await _fulfill_autosms_invoice(context, fresh)
            try:
                await context.bot.send_message(chat_id=inv["chat_id"], text=text, parse_mode="HTML")
            except Exception:
                logger.warning("اطلاع‌رسانی پرداخت خودکار فاکتور AutoSMS #%s ناموفق بود", inv["authority"])
        elif status == "expired":
            db.set_autosms_invoice_status(inv["authority"], "expired")


async def ask_for_receipt_autosms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """دکمه‌ی پشتیبان «ارسال رسید» روی فاکتور خودکار (خرید/تمدید) - برای وقتی
    بعد از یک ساعت هنوز خودکار تایید نشده"""
    query = update.callback_query
    await query.answer()
    authority = query.data.split(":", 1)[1]
    inv = db.get_autosms_invoice(authority)
    if not inv:
        await query.edit_message_text("فاکتور پیدا نشد.")
        return ConversationHandler.END
    if inv["status"] == "paid":
        await query.edit_message_text("این پرداخت قبلاً خودکار تایید و تحویل داده شده.")
        return ConversationHandler.END

    context.user_data["receipt_ctx"] = {
        "kind": inv["kind"],
        "plan_id": inv["plan_id"],
        "sub_id": inv["sub_id"] if "sub_id" in inv.keys() else None,
        "custom_name": inv["custom_name"] if "custom_name" in inv.keys() else None,
        "discount_code": inv["discount_code"] if "discount_code" in inv.keys() else None,
        "discount_percent": inv["discount_percent"] if "discount_percent" in inv.keys() else None,
    }
    if inv["status"] == "pending":
        db.set_autosms_invoice_status(authority, "manual_review")
    await query.edit_message_text(
        rs.hdr("📸", "ارسال رسید پرداخت", hint="لطفا الان عکس رسید پرداخت رو ارسال کن."),
        reply_markup=back_to_menu_keyboard(),
    )
    return WAITING_RECEIPT


async def ask_for_receipt_autosms_topup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """همون بالایی ولی برای فاکتورهای شارژ کیف پول"""
    query = update.callback_query
    await query.answer()
    authority = query.data.split(":", 1)[1]
    inv = db.get_autosms_invoice(authority)
    if not inv:
        await query.edit_message_text("فاکتور پیدا نشد.")
        return ConversationHandler.END
    if inv["status"] == "paid":
        await query.edit_message_text("این پرداخت قبلاً خودکار تایید و تحویل داده شده.")
        return ConversationHandler.END

    context.user_data["topup_amount"] = inv["base_amount_toman"]
    if inv["status"] == "pending":
        db.set_autosms_invoice_status(authority, "manual_review")
    await query.edit_message_text(
        rs.hdr("📸", "ارسال رسید پرداخت", hint="لطفا الان عکس رسید پرداخت رو ارسال کن."),
        reply_markup=back_to_menu_keyboard(),
    )
    return WAITING_TOPUP_RECEIPT


async def check_data_limits_job(context: ContextTypes.DEFAULT_TYPE):
    """
    هر ۲۰ ثانیه اجرا میشه (فاصله کوتاه شده چون فاصله‌ی قبلی -۲ دقیقه- زمان
    زیادی به کاربر می‌داد که رو یه اتصال سریع چندین برابر سقفش مصرف کنه).
    دو کار می‌کنه:
    ۱. وقتی مصرف به DATA_WARNING_THRESHOLD_PERCENT درصد سقف رسید، یه‌بار
       (نه هر بار) هشدار با دکمه‌ی تمدید/خرید می‌فرسته.
    ۲. وقتی مصرف کامل به سقف رسید، سرویس رو غیرفعال می‌کنه و به کاربر
       اطلاع می‌ده.
    """
    subs = db.get_all_active_subscriptions()
    for sub in subs:
        username = sub["marzban_username"]
        if not username:
            continue
        if sub["ended_at"]:
            continue  # از قبل وارد مهلت تمدید شده؛ مراقبتش با check_expired_subscriptions_job ـه
        try:
            info = await panel.get_user(username, include_config=False)
        except PanelError:
            continue

        if info.get("status") != "active":
            # از قبل غیرفعاله (چه دستی چه قبلاً به همین دلیل قطع شده). اگه به‌خاطر
            # اتمام حجم بوده (قبل از اضافه‌شدن مهلت تمدید) هنوز مهلتش شروع نشده؛
            # از همین الان وارد مهلت میشه تا تا ابد تو لیست نمونه.
            if sub["plan_id"] != "trial":
                dead_limit = info.get("data_limit") or 0
                dead_used = info.get("used_traffic") or 0
                if dead_limit and dead_used >= dead_limit:
                    await _enter_grace(context, sub, "data")
            continue

        limit = info.get("data_limit") or 0
        used = info.get("used_traffic") or 0
        if not limit:
            continue

        if used >= limit:
            try:
                await panel.set_status(username, "disabled")
            except PanelError:
                logger.warning("غیرفعال‌کردن سرویس #%s به‌خاطر اتمام حجم ناموفق بود", sub["sub_id"])
                continue
            if sub["plan_id"] == "trial":
                # تست رایگان مهلت نداره؛ مثل قبل فقط غیرفعال میشه (سر موعد حذف میشه)
                try:
                    await context.bot.send_message(
                        chat_id=sub["user_id"],
                        text=(
                            f"{pe.REJECT} سرویس «{sub['plan_title']}» شما به‌خاطر اتمام حجم غیرفعال شد.\n"
                            "برای ادامه‌ی استفاده، از «سرویس‌های من» تمدیدش کن."
                        ),
                        reply_markup=data_warning_keyboard(sub["sub_id"]),
                        parse_mode="HTML",
                    )
                except Exception:
                    logger.warning("اطلاع‌رسانی اتمام حجم سرویس #%s به کاربر %s ناموفق بود", sub["sub_id"], sub["user_id"])
            else:
                await _enter_grace(context, sub, "data")
            continue

        # هشدار نزدیک‌شدن به سقف (فقط یه‌بار در هر دوره‌ی سرویس)
        if not sub["data_warning_sent"] and used >= limit * (DATA_WARNING_THRESHOLD_PERCENT / 100):
            db.mark_data_warning_sent(sub["sub_id"])
            remaining_mb = max(0, round((limit - used) / (1024 ** 2)))
            try:
                await context.bot.send_message(
                    chat_id=sub["user_id"],
                    text=(
                        f"{pe.HOURGLASS2} یادآوری اتمام حجم\n\n"
                        f"حجم سرویس «{sub['plan_title']}» شما رو به اتمامه (فقط حدود {remaining_mb} مگابایت باقی مونده).\n"
                        "نسبت به تمدید سرویس خود اقدام کنید."
                    ),
                    reply_markup=data_warning_keyboard(sub["sub_id"]),
                    parse_mode="HTML",
                )
            except Exception:
                logger.warning("اطلاع‌رسانی هشدار حجم سرویس #%s به کاربر %s ناموفق بود", sub["sub_id"], sub["user_id"])


async def _try_auto_renew(context: ContextTypes.DEFAULT_TYPE, sub) -> bool:
    """
    برای سرویس‌هایی که «تمدید خودکار» روشنه، درست لحظه‌ی انقضا (توسط
    check_expired_subscriptions_job) تلاش می‌کنه بی‌صدا از کیف پول کسر و
    تمدید کنه. اگه موفق شد True برمی‌گردونه (یعنی کار حذف لازم نیست).
    """
    plan = get_plan(sub["plan_id"])
    if not plan:
        return False

    balance = db.get_wallet_balance(sub["user_id"])
    if balance < plan["price"]:
        db.set_auto_renew(sub["sub_id"], False)
        try:
            await context.bot.send_message(
                chat_id=sub["user_id"],
                text=(
                    f"{pe.REJECT} تمدید خودکار سرویس «{sub['plan_title']}» به‌خاطر کمبود موجودی کیف پول انجام نشد.\n"
                    f"موجودی فعلی: {balance:,} تومان | مبلغ لازم: {plan['price']:,} تومان\n\n"
                    "سرویس منقضی شد؛ کیف پولت رو شارژ کن و به‌صورت دستی تمدید کن."
                ),
                reply_markup=expired_notice_keyboard(),
                parse_mode="HTML",
            )
        except Exception:
            logger.warning("اطلاع‌رسانی شکست تمدید خودکار #%s ناموفق بود", sub["sub_id"])
        return False

    # کسر اتمیک قبل از تمدید (اگه همزمان کاربر خودش موجودی رو خرج کرده باشه، تمدید انجام نمیشه)
    if not db.try_debit_wallet(sub["user_id"], plan["price"], "renewal", f"تمدید خودکار {plan['title']}"):
        return False

    try:
        result = await panel.modify_user(sub["marzban_username"], plan["days"], plan["gb"])
    except PanelError:
        _refund_wallet_purchase(sub["user_id"], plan["price"], "برگشت مبلغ: تمدید خودکار انجام نشد")
        logger.warning("تمدید خودکار سرویس #%s با خطای پنل مواجه شد", sub["sub_id"])
        return False
    except Exception:
        _refund_wallet_purchase(sub["user_id"], plan["price"], "برگشت مبلغ: خطای غیرمنتظره در تمدید خودکار")
        raise
    new_expire = result.get("expire") or 0
    new_sub_link = result.get("subscription_url", "")
    db.update_subscription_after_renew(sub["sub_id"], new_expire, plan["title"], plan["id"])
    if new_sub_link:
        db.update_subscription_link(sub["sub_id"], new_sub_link)

    order_id = db.create_order(sub["user_id"], plan["id"], None, kind="renew", renew_sub_id=sub["sub_id"])
    db.set_order_status(order_id, "approved", sub["user_id"])

    try:
        await send_service_delivery(
            context.bot, sub["user_id"], _plan_with_actual_gb(plan, result), sub["marzban_username"],
            new_sub_link or sub["sub_link"], "تمدید خودکار", expire_at=new_expire,
            sub_id=sub["sub_id"], connection_link=result.get("connection_link", ""),
        )
    except Exception:
        logger.warning("اطلاع‌رسانی تمدید خودکار #%s به کاربر ناموفق بود", sub["sub_id"])

    return True


_REMOVE_STRIKES = {}          # {sub_id: چندبار پشت‌سرهم «حذف از پنل ناموفق + کلاینت روی پنل نبود»}
_ORPHAN_STRIKES_NEEDED = 3    # بعد از این‌قدر بار (هر بار ~۵ دقیقه) کلاینت رو «یتیم» حساب می‌کنیم


async def _remove_from_panel(sub_id: int, username: str) -> bool:
    """
    کلاینت رو از پنل حذف می‌کنه. True یعنی «دیگه روی پنل نیست» (حذف شد، یا از قبل
    نبود) و میشه ردیف دیتابیس رو هم پاک کرد. False یعنی هنوز نشده؛ دفعه‌ی بعد
    دوباره تلاش میشه.

    قبلاً اگه کلاینت دستی از پنل پاک شده بود، حذف همیشه خطا می‌داد و سرویس برای
    همیشه تو دیتابیس/مینی‌اپ می‌موند. حالا اگه حذف خطا بده و کلاینت رو هم نشه
    از پنل خوند، بعد از چند تلاش پشت‌سرهم «یتیم» حسابش می‌کنیم. (اگه کلاینت
    هنوز روی پنل هست، یعنی خطای واقعیه و هیچ‌وقت یتیم حساب نمیشه.)
    """
    try:
        await panel.remove_user(username)
        _REMOVE_STRIKES.pop(sub_id, None)
        return True
    except PanelError:
        pass

    try:
        await panel.get_user(username, include_config=False)
    except PanelError:
        strikes = _REMOVE_STRIKES.get(sub_id, 0) + 1
        if strikes >= _ORPHAN_STRIKES_NEEDED:
            _REMOVE_STRIKES.pop(sub_id, None)
            logger.warning("کلاینت سرویس #%s روی پنل پیدا نمیشه؛ یتیم حساب شد و فقط از دیتابیس حذف میشه", sub_id)
            return True
        _REMOVE_STRIKES[sub_id] = strikes
        return False

    _REMOVE_STRIKES.pop(sub_id, None)
    logger.warning("حذف سرویس #%s از پنل ناموفق بود (کلاینت هنوز روی پنل هست)؛ دفعه‌ی بعد دوباره تلاش میشه", sub_id)
    return False


async def _enter_grace(context: ContextTypes.DEFAULT_TYPE, sub, reason: str):
    """
    سرویس تموم شده (reason='time' اتمام زمان، 'data' اتمام حجم) و به‌جای حذف فوری،
    وارد «مهلت تمدید» میشه: ساعت مهلت از همین لحظه شروع میشه و به کاربر خبر داده میشه.
    """
    now = int(time.time())
    total = _grace_seconds(reason)
    # اگه کل مهلت کوتاه‌تر از پنجره‌ی هشدار نهایی باشه، پیام اول خودش هشدار نهاییه
    already_final = total <= FINAL_WARNING_HOURS * 3600
    if not db.mark_subscription_ended(sub["sub_id"], reason, now, final_warning_sent=already_final):
        return  # قبلاً وارد مهلت شده؛ ساعتش ریست نمیشه
    db.log_lifecycle(f"ended_{reason}", sub["user_id"], sub["sub_id"])   # برای گزارش صبحگاهی ادمین

    title = pe.esc(sub["plan_title"] or "")
    if reason == "data":
        head = f"{pe.REJECT} حجم سرویس «{title}» تموم شد و سرویس غیرفعال شد."
    else:
        head = f"{pe.REJECT} مدت سرویس «{title}» به پایان رسید."
    try:
        await rm.send_rich_or_classic(
            context.bot, sub["user_id"],
            rs.service_ended(sub["plan_title"] or "", reason, _fmt_left(total)) if rm.enabled() else None,
            (
                f"{head}\n\n"
                f"{pe.HOURGLASS2} تا {_fmt_left(total)} فرصت داری تمدیدش کنی؛ با تمدید، همین لینک و کانفیگ "
                "قبلی دوباره فعال میشه و لازم نیست چیزی رو دوباره تنظیم کنی.\n\n"
                "بعد از این مهلت، سرویس برای همیشه حذف میشه."
            ),
            reply_markup=data_warning_keyboard(sub["sub_id"]),
        )
    except Exception:
        logger.warning("اطلاع‌رسانی پایان سرویس #%s به کاربر %s ناموفق بود", sub["sub_id"], sub["user_id"])


async def _delete_ended_subscription(context: ContextTypes.DEFAULT_TYPE, sub, winback: bool):
    """
    حذف قطعی: از پنل، دیتابیس (و در نتیجه بات و مینی‌اپ) + پیام به کاربر.
    winback=True (سرویس پولی که مهلتش تموم شد) یه کد تخفیف شخصی هم تو پیام میاد.
    """
    sub_id = sub["sub_id"]
    # درست قبل از حذف دوباره از دیتابیس می‌خونیم؛ اگه تو این فاصله تمدید شده باشه، دست نمی‌زنیم
    fresh = db.get_subscription(sub_id)
    if not fresh:
        return
    if winback:
        if not fresh["ended_at"]:
            return
    elif fresh["expire_at"] and fresh["expire_at"] > int(time.time()):
        return

    if not await _remove_from_panel(sub_id, fresh["marzban_username"]):
        return

    plan_title = fresh["plan_title"] or ""
    user_id = fresh["user_id"]
    db.delete_subscription(sub_id)
    db.log_lifecycle("deleted" if winback else "deleted_trial", user_id, sub_id)   # برای گزارش صبحگاهی ادمین

    code = None
    if winback and WINBACK_ENABLED and WINBACK_PERCENT > 0:
        try:
            code = db.create_winback_code(WINBACK_PERCENT, WINBACK_HOURS)
        except Exception:
            logger.exception("ساخت کد تخفیف بازگشت برای کاربر %s ناموفق بود", user_id)

    text = (
        f"{pe.REJECT} سرویس «{pe.esc(plan_title)}» به‌دلیل تمدید نکردن حذف شد.\n"
        "لطفا یک اشتراک جدید تهیه کنید."
    )
    if code:
        text += (
            f"\n\n🎁 یه هدیه برای برگشتنت: {WINBACK_PERCENT}٪ تخفیف مخصوص خودت روی خرید سرویس جدید\n"
            f"<code>{code}</code>\n"
            f"فقط {WINBACK_HOURS} ساعت اعتبار داره و یک‌بارمصرفه؛ موقع خرید واردش کن."
        )
    try:
        await rm.send_rich_or_classic(
            context.bot, user_id,
            rs.service_deleted(plan_title, code, WINBACK_PERCENT, WINBACK_HOURS) if rm.enabled() else None,
            text, reply_markup=expired_notice_keyboard(),
        )
    except Exception:
        logger.warning("اطلاع‌رسانی حذف سرویس #%s به کاربر %s ناموفق بود", sub_id, user_id)


async def _process_grace_period(context: ContextTypes.DEFAULT_TYPE, sub, now: int):
    """سرویسی که تو مهلت تمدیده: یا وقت حذفشه، یا وقت هشدار نهایی، یا هنوز صبر می‌کنیم"""
    deadline = _grace_deadline(sub)
    if deadline is None:
        return
    if now >= deadline:
        await _delete_ended_subscription(context, sub, winback=True)
        return

    left = deadline - now
    if not sub["final_warning_sent"] and left <= FINAL_WARNING_HOURS * 3600:
        db.mark_final_warning_sent(sub["sub_id"])
        try:
            await rm.send_rich_or_classic(
                context.bot, sub["user_id"],
                rs.final_warning(sub["plan_title"] or "", _fmt_left(left)) if rm.enabled() else None,
                (
                    f"{pe.HOURGLASS2} هشدار نهایی\n\n"
                    f"سرویس «{pe.esc(sub['plan_title'] or '')}» حدود {_fmt_left(left)} دیگه برای همیشه حذف میشه.\n"
                    "هنوز می‌تونی با تمدیدش (همون لینک قبلی) نگهش داری."
                ),
                reply_markup=data_warning_keyboard(sub["sub_id"]),
            )
        except Exception:
            logger.warning("اطلاع‌رسانی هشدار نهایی سرویس #%s به کاربر %s ناموفق بود", sub["sub_id"], sub["user_id"])


async def _lifecycle_step(context: ContextTypes.DEFAULT_TYPE, sub, now: int):
    username = sub["marzban_username"]
    if not username:
        return

    # ۱) سرویسی که قبلاً وارد مهلت تمدید شده
    if sub["ended_at"]:
        await _process_grace_period(context, sub, now)
        return

    expire_at = sub["expire_at"]
    if not expire_at:
        return  # بدون تاریخ انقضا (مثلاً بعضی تنظیمات خاص) - نادیده می‌گیریم

    # ۲) همین الان تموم شده
    if expire_at <= now:
        if sub["auto_renew"]:
            renewed = await _try_auto_renew(context, sub)
            if renewed:
                return  # سرویس با موفقیت تمدید خودکار شد
        if sub["plan_id"] == "trial":
            # تست رایگان مهلت نداره؛ مثل قبل سر موعد حذف میشه (بدون کد تخفیف)
            await _delete_ended_subscription(context, sub, winback=False)
        else:
            await _enter_grace(context, sub, "time")
        return

    # ۳) هشدار نزدیک‌شدن به پایان اعتبار (یه‌بار)
    seconds_left = expire_at - now
    if not sub["expiry_warning_sent"] and seconds_left <= EXPIRY_WARNING_DAYS_BEFORE * 86400:
        db.mark_expiry_warning_sent(sub["sub_id"])
        days_left = max(1, round(seconds_left / 86400))
        try:
            await rm.send_rich_or_classic(
                context.bot, sub["user_id"],
                rs.expiry_reminder(sub["plan_title"] or "", days_left) if rm.enabled() else None,
                (
                    f"{pe.HOURGLASS2} یادآوری تمدید اشتراک\n\n"
                    f"تنها {days_left} روز از اعتبار اشتراک «{sub['plan_title']}» شما باقی مانده است!\n\n"
                    "برای ادامه سرویس، هم‌اکنون نسبت به تمدید اشتراک اقدام کنید."
                ),
                reply_markup=data_warning_keyboard(sub["sub_id"]),
            )
        except Exception:
            logger.warning("اطلاع‌رسانی هشدار انقضای سرویس #%s به کاربر %s ناموفق بود", sub["sub_id"], sub["user_id"])


async def check_expired_subscriptions_job(context: ContextTypes.DEFAULT_TYPE):
    """
    هر چند دقیقه اجرا میشه و چرخه‌ی عمر سرویس بعد از پایان رو مدیریت می‌کنه:
    ۱. یه روز قبل از پایان اعتبار، یه هشدار با دکمه‌ی تمدید می‌فرسته (یه‌بار).
    ۲. لحظه‌ی انقضا، اگه «تمدید خودکار» روشن بود، تلاش می‌کنه بی‌صدا از کیف پول
       کسر و تمدید کنه (_try_auto_renew).
    ۳. اگه تمدید نشد، سرویس فوراً حذف نمیشه: وارد «مهلت تمدید» میشه (GRACE_DAYS_TIME
       روز؛ برای اتمام حجم GRACE_DAYS_DATA روز که تو check_data_limits_job شروع میشه).
       تو این مهلت هنوز با همون لینک قابل تمدیده.
    ۴. FINAL_WARNING_HOURS ساعت مونده به حذف، هشدار نهایی میاد.
    ۵. بعد از مهلت، کلاینت از پنل، ردیف از دیتابیس (یعنی از بات و مینی‌اپ) حذف میشه و
       یه کد تخفیف شخصی برای برگشتن کاربر میاد.
    (سرویس تست رایگان مهلت نداره و مثل قبل سر موعد حذف میشه.)
    """
    subs = db.get_all_active_subscriptions()
    now = int(time.time())

    for sub in subs:
        # خطای یه سرویس نباید کل بررسی بقیه‌ی سرویس‌ها رو متوقف کنه
        try:
            await _lifecycle_step(context, sub, now)
        except Exception:
            logger.exception("بررسی چرخه‌ی عمر سرویس #%s با خطا مواجه شد", sub["sub_id"])


async def _build_weekly_summary(user_id: int):
    """
    متن خلاصه‌ی هفتگی کاربر + آیدی سرویسی که تمدید فوری می‌خواد (یا None).
    خروجی None یعنی چیزی برای گفتن نیست. فقط سرویس‌های پولیِ فعال حساب میشن.
    """
    import usage_history

    gb = 1024 ** 3
    subs = [
        s for s in db.get_user_subscriptions(user_id)
        if not s["ended_at"] and s["plan_id"] != "trial"
    ]
    if not subs:
        return None
    rows = _sort_rows(await _build_service_rows(subs), "days")
    by_id = {s["sub_id"]: s for s in subs}

    lines = [f"{pe.MY_SERVICES} خلاصه‌ی هفتگی سرویس‌هات"]
    rich_services = []   # همون اطلاعات برای نسخه‌ی غنی (جدول)
    urgent_sub_id = None
    shown = rows[:3]
    for r in shown:
        sub = by_id[r["sub_id"]]
        name = pe.esc(r["username"] or r["plan_title"] or "")
        try:
            week = usage_history.get_week(r["sub_id"])
        except Exception:
            week = {"days": [], "avg_gb": 0, "tracked_days": 0}
        week_gb = sum(d["bytes"] for d in week["days"] if d["bytes"] is not None) / gb

        svc = {
            "name": r["username"] or r["plan_title"] or "",
            "week_gb": week_gb if week["tracked_days"] >= 1 else None,
            "remaining_gb": r["remaining_gb"],
            "remaining_days": r["remaining_days"],
            "notes": [],
        }
        rich_services.append(svc)
        block = [f"\n🔹 {name}"]
        if week["tracked_days"] >= 1:
            block.append(f"مصرف ۷ روز اخیر: {week_gb:.1f} گیگ")
        if r["remaining_gb"] is not None:
            block.append(f"حجم باقی‌مانده: {r['remaining_gb']:g} گیگ")
        if r["remaining_days"] is not None:
            block.append(f"زمان باقی‌مانده: {r['remaining_days']} روز")

        rec = smart_plans.build_recommendation(
            sub["plan_id"], r["remaining_gb"], r["remaining_days"], week["avg_gb"], week["tracked_days"]
        )
        if rec and rec["runs_out_early"] and rec["days_to_depleted"] is not None:
            block.append(
                f"⚠️ با این مصرف حجمت حدود {max(1, round(rec['days_to_depleted']))} روز دیگه تموم میشه."
            )
            block.append(_recommendation_text(rec))
            svc["notes"].append(f"⚠️ با این مصرف حجمت حدود {max(1, round(rec['days_to_depleted']))} روز دیگه تموم میشه.")
            svc["notes"] += [rm.Raw(ln) for ln in _recommendation_text(rec).split("\n")]
            if urgent_sub_id is None:
                urgent_sub_id = r["sub_id"]
        elif rec:
            block.append("✅ با این مصرف، حجمت تا آخر دوره کافیه.")
            svc["notes"].append("✅ با این مصرف، حجمت تا آخر دوره کافیه.")
        elif r["remaining_days"] is not None and r["remaining_days"] <= 3 and urgent_sub_id is None:
            urgent_sub_id = r["sub_id"]
            block.append("⏳ اعتبار سرویس رو به پایانه؛ بهتره تمدیدش کنی.")
            svc["notes"].append("⏳ اعتبار سرویس رو به پایانه؛ بهتره تمدیدش کنی.")
        lines.append("\n".join(block))

    if len(rows) > len(shown):
        lines.append(f"\nو {len(rows) - len(shown)} سرویس دیگه هم داری ({pe.MY_SERVICES} سرویس‌های من).")
    footer = (
        rm.Raw(f"و {len(rows) - len(shown)} سرویس دیگه هم داری ({pe.MY_SERVICES} سرویس‌های من).")
        if len(rows) > len(shown) else None
    )
    return "\n".join(lines), urgent_sub_id, rs.weekly_summary("fa", rich_services, footer)


async def weekly_summary_job(context: ContextTypes.DEFAULT_TYPE):
    """
    هر روز اجرا میشه ولی فقط «جمعه به وقت ایران» واقعاً پیام می‌فرسته: خلاصه‌ی مصرف هفته،
    باقی‌مانده و (در صورت نیاز) پیشنهاد پلن، برای کاربرای دارای سرویس پولی که خاموشش نکردن.
    """
    now_ir = datetime.datetime.now(ZoneInfo("Asia/Tehran"))
    if now_ir.weekday() != 4:      # دوشنبه=۰ ... جمعه=۴
        return
    today = now_ir.strftime("%Y-%m-%d")

    for uid in db.get_weekly_summary_users(today):
        try:
            built = await _build_weekly_summary(uid)
            if not built:
                continue
            text, urgent_sub_id, rich_html = built
            await rm.send_rich_or_classic(
                context.bot, uid, rich_html, text,
                reply_markup=weekly_summary_keyboard(urgent_sub_id), rtl=True,
            )
            db.mark_weekly_summary_sent(uid, today)
        except Exception:
            logger.warning("ارسال خلاصه‌ی هفتگی به کاربر %s ناموفق بود", uid)
        await asyncio.sleep(0.05)   # زیر محدودیت فلود تلگرام بمونیم


async def handle_weekly_summary_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دکمه‌ی خاموش/روشن‌کردن خلاصه‌ی هفتگی زیر خود پیام"""
    query = update.callback_query
    enabled = query.data.split(":", 1)[1] == "on"
    db.set_weekly_summary(update.effective_user.id, enabled)
    if enabled:
        await query.answer("خلاصه‌ی هفتگی دوباره روشن شد.")
        button = InlineKeyboardButton("🔕 خاموش کردن خلاصه‌ی هفتگی", callback_data="wsum:off")
    else:
        await query.answer("خلاصه‌ی هفتگی خاموش شد؛ دیگه برات نمی‌فرستیم.", show_alert=True)
        button = InlineKeyboardButton("🔔 روشن کردن خلاصه‌ی هفتگی", callback_data="wsum:on")
    try:
        await query.edit_message_reply_markup(InlineKeyboardMarkup([[button]]))
    except Exception:
        pass


async def monthly_loyalty_bonus_job(context: ContextTypes.DEFAULT_TYPE):
    """
    هر روز اجرا میشه ولی فقط روز اول هر ماه واقعاً کاری می‌کنه (این‌جوری
    اگه بات دقیقاً همون لحظه خاموش بود، روز بعد که بالا اومد رد نمیشه).
    به هر کاربری که مجموع خریدش به یکی از سطح‌های باشگاه مشتریان رسیده،
    پاداش ماهانه‌ی همون سطح رو (فقط یه‌بار در ماه) به کیف پولش اضافه می‌کنه.
    """
    now = datetime.datetime.now()
    if now.day != 1:
        return
    month_key = now.strftime("%Y-%m")

    totals = db.get_all_lifetime_spent()
    for user_id, spent in totals.items():
        tier = db.get_loyalty_tier_for_amount(spent)
        if not tier:
            continue
        user_row = db.get_user(user_id)
        if not user_row or user_row["loyalty_bonus_month"] == month_key:
            continue

        db.adjust_wallet_balance_logged(
            user_id, tier["monthly_bonus"], "loyalty_bonus",
            f"پاداش ماهانه‌ی باشگاه مشتریان (سطح {tier['name']})",
        )
        db.mark_loyalty_bonus_given(user_id, month_key)
        try:
            lang = db.get_user_language(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=t(
                    "loyalty_bonus_message", lang,
                    pe_charge=pe.CHARGE, emoji=_tier_medal(tier),
                    name=tier["name"], amount=tier["monthly_bonus"],
                ),
                parse_mode="HTML",
            )
        except Exception:
            logger.warning("اطلاع‌رسانی پاداش باشگاه مشتریان به کاربر %s ناموفق بود", user_id)


async def check_pending_crypto_job(context: ContextTypes.DEFAULT_TYPE):
    """هر چند دقیقه یک‌بار اجرا میشه؛ فاکتورهای پرداخت‌نشده رو خودکار بررسی می‌کنه"""
    pending = db.get_pending_crypto_invoices()
    now = int(time.time())

    for inv in pending:
        age_minutes = (now - inv["created_at"]) / 60
        if age_minutes > CRYPTO_INVOICE_TIMEOUT_MINUTES:
            db.set_crypto_invoice_status(inv["invoice_id"], "expired")
            try:
                await context.bot.send_message(
                    chat_id=inv["chat_id"],
                    text="⌛ فاکتور پرداخت کریپتوت منقضی شد. اگه هنوز می‌خوای پرداخت کنی، دوباره از منو تلاش کن.",
                )
            except Exception:
                logger.warning("اطلاع‌رسانی انقضای فاکتور #%s ناموفق بود", inv["invoice_id"])
            continue

        try:
            status = await xrocket.check_invoice(inv["invoice_id"])
        except xrocket.XRocketError:
            continue

        if status == "paid":
            text = await _fulfill_crypto_invoice(context, inv)
            try:
                await context.bot.send_message(chat_id=inv["chat_id"], text=text, parse_mode="HTML")
            except Exception:
                logger.warning("اطلاع‌رسانی پرداخت خودکار فاکتور #%s ناموفق بود", inv["invoice_id"])
        elif status == "expired":
            db.set_crypto_invoice_status(inv["invoice_id"], "expired")


# ---------------- ورودی مکالمه‌ی ارسال رسید (خرید جدید و تمدید) ----------------
async def ask_for_receipt_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not await check_and_prompt_join(update, context):
        return ConversationHandler.END

    plan_id = query.data.split(":", 1)[1]
    discount = context.user_data.get("applied_discount")
    discount_active = bool(discount and discount.get("plan_id") == plan_id)
    context.user_data["receipt_ctx"] = {
        "kind": "new",
        "plan_id": plan_id,
        "custom_name": context.user_data.pop("pending_custom_name", None),
        "discount_code": discount["code"] if discount_active else None,
        "discount_percent": discount["percent"] if discount_active else None,
    }
    await query.edit_message_text(
        rs.hdr("📸", "ارسال رسید پرداخت", hint="لطفا الان عکس رسید پرداخت رو ارسال کن."),
        reply_markup=back_to_menu_keyboard(),
    )
    return WAITING_RECEIPT


async def ask_for_receipt_renew(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if not await check_and_prompt_join(update, context):
        return ConversationHandler.END

    _, sub_id, plan_id = query.data.split(":")
    context.user_data["receipt_ctx"] = {
        "kind": "renew",
        "plan_id": plan_id,
        "sub_id": int(sub_id),
    }
    await query.edit_message_text(
        rs.hdr("📸", "ارسال رسید پرداخت", hint="لطفا الان عکس رسید پرداخت رو ارسال کن."),
        reply_markup=back_to_menu_keyboard(),
    )
    return WAITING_RECEIPT


async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ctx = context.user_data.get("receipt_ctx")
    plan = get_plan(ctx["plan_id"]) if ctx else None

    if not ctx or not plan:
        await update.message.reply_text(
            "یه مشکلی پیش اومد، لطفا از /start دوباره شروع کن."
        )
        return ConversationHandler.END

    file_id = _extract_image_file_id(update.message)
    if not file_id:
        await update.message.reply_text(
            "لطفا فقط عکس رسید رو ارسال کن (به‌صورت عکس یا فایل تصویری، نه متن).",
            reply_markup=back_to_menu_keyboard(),
        )
        return WAITING_RECEIPT

    user = update.effective_user
    kind = ctx["kind"]
    renew_sub_id = ctx.get("sub_id") if kind == "renew" else None

    try:
        order_id = db.create_order(
            user.id, ctx["plan_id"], file_id, kind=kind, renew_sub_id=renew_sub_id,
            custom_name=ctx.get("custom_name"),
            discount_code=ctx.get("discount_code"),
            discount_percent=ctx.get("discount_percent"),
        )
    except Exception:
        logger.exception("ثبت سفارش در دیتابیس ناموفق بود (کاربر %s)", user.id)
        await update.message.reply_text(
            f"{pe.REJECT} یه خطای فنی در ثبت سفارش پیش اومد.\n"
            "این معمولا یعنی دیتابیس نیاز به ریست داره (فایل bot_database.db رو پاک کن و ربات رو ری‌استارت کن).\n"
            "لطفا با پشتیبانی هم هماهنگ کن.",
            parse_mode="HTML",
        )
        context.user_data.pop("receipt_ctx", None)
        return ConversationHandler.END

    # اول به کاربر تاییدیه می‌دیم، مستقل از اینکه اطلاع‌رسانی به ادمین موفق باشه یا نه
    await update.message.reply_text(
        f"{pe.CONFIRM} رسید شما دریافت شد و برای بررسی ارسال شد.\n"
        "به محض تایید، اطلاعات سرویس برات ارسال میشه.\n"
        "معمولا این کار چند دقیقه تا چند ساعت زمان می‌بره.",
        parse_mode="HTML",
    )
    context.user_data.pop("receipt_ctx", None)
    context.user_data.pop("applied_discount", None)

    final_price = plan["price"]
    discount_line = ""
    if ctx.get("discount_code"):
        final_price = round(plan["price"] * (100 - ctx["discount_percent"]) / 100)
        discount_line = f"\nکد تخفیف: {ctx['discount_code']} ({ctx['discount_percent']}٪)"

    kind_label = "🔄 تمدید سرویس" if kind == "renew" else "🧾 سفارش جدید"
    caption = (
        f"{kind_label}\n"
        f"سفارش: #{order_id}\n"
        f"کاربر: {user.first_name or ''} (@{user.username or 'بدون‌یوزرنیم'})\n"
        f"آیدی عددی: {user.id}\n"
        f"پلن: {plan['title']}\n"
        f"مبلغ: {final_price:,} تومان"
        f"{discount_line}"
    )

    try:
        admin_msg = await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=file_id,
            caption=caption,
            reply_markup=admin_decision_keyboard(order_id),
        )
        db.set_order_admin_message(order_id, admin_msg.message_id)
    except Exception:
        logger.exception("ارسال رسید سفارش #%s به ادمین (ADMIN_CHAT_ID=%s) ناموفق بود", order_id, ADMIN_CHAT_ID)
        await update.message.reply_text(
            f"{pe.REJECT} سفارش #{order_id} ثبت شد ولی اطلاع‌رسانی به ادمین با خطا مواجه شد.\n"
            "این معمولا یعنی اکانت ادمین هنوز یک بار /start به ربات نزده.\n"
            "لطفا با پشتیبانی هماهنگ کن تا سفارشت رو دستی پیگیری کنه.",
            parse_mode="HTML",
        )

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("receipt_ctx", None)
    context.user_data.pop("custom_name_ctx", None)
    context.user_data.pop("pending_custom_name", None)
    await update.message.reply_text("عملیات لغو شد.")
    return ConversationHandler.END


async def cancel_via_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """وقتی وسط یه مکالمه (مثل شارژ کیف پول) کاربر دکمه‌ی بازگشت به منو رو بزنه"""
    context.user_data.pop("receipt_ctx", None)
    context.user_data.pop("topup_amount", None)
    context.user_data.pop("custom_name_ctx", None)
    context.user_data.pop("pending_custom_name", None)
    context.user_data.pop("reseller_name_ctx", None)
    context.user_data.pop("reseller_name", None)
    await menu_router(update, context)
    return ConversationHandler.END


def build_handlers():
    receipt_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_for_receipt_new, pattern=r"^paysend:"),
            CallbackQueryHandler(ask_for_receipt_renew, pattern=r"^renewpaysend:"),
            CallbackQueryHandler(ask_for_receipt_autosms, pattern=r"^atsend:"),
        ],
        states={
            WAITING_RECEIPT: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_receipt),
                MessageHandler(filters.ALL & ~filters.COMMAND, receive_receipt),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_via_menu, pattern=r"^menu:"),
        ],
        per_message=False,
    )

    topup_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_topup_amount, pattern=r"^wallettopup:start$"),
            CallbackQueryHandler(ask_for_receipt_autosms_topup, pattern=r"^attsend:"),
            CallbackQueryHandler(prompt_topup_receipt, pattern=r"^topupsend:"),
        ],
        states={
            WAITING_TOPUP_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_topup_amount)
            ],
            WAITING_TOPUP_RECEIPT: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_topup_receipt),
                MessageHandler(filters.ALL & ~filters.COMMAND, receive_topup_receipt),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_via_menu, pattern=r"^menu:"),
        ],
        per_message=False,
    )

    service_search_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_service_search, pattern=r"^svcsearch:start$"),
        ],
        states={
            WAITING_SERVICE_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_service_search)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_via_menu, pattern=r"^menu:"),
        ],
        per_message=False,
    )

    service_note_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_service_note, pattern=r"^svcnoteedit:"),
        ],
        states={
            WAITING_SERVICE_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_service_note)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_via_menu, pattern=r"^menu:"),
        ],
        per_message=False,
    )

    custom_name_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_custom_name, pattern=r"^namecustom:"),
        ],
        states={
            WAITING_CUSTOM_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_name)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_via_menu, pattern=r"^menu:"),
        ],
        per_message=False,
    )

    discount_code_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_discount_code, pattern=r"^discountask:"),
        ],
        states={
            WAITING_DISCOUNT_CODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_discount_code)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", discount_code_cancel),
            CallbackQueryHandler(cancel_via_menu, pattern=r"^menu:"),
        ],
        per_message=False,
    )

    service_transfer_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(handle_svc_transfer_start, pattern=r"^svctransfer:"),
        ],
        states={
            WAITING_SERVICE_TRANSFER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_service_transfer)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_via_menu, pattern=r"^menu:"),
        ],
        per_message=False,
    )

    wallet_transfer_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_wallet_transfer_target, pattern=r"^wallettransfer:start$"),
        ],
        states={
            WAITING_WALLET_TRANSFER_TARGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_wallet_transfer_target)
            ],
            WAITING_WALLET_TRANSFER_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_wallet_transfer_amount)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_via_menu, pattern=r"^menu:"),
        ],
        per_message=False,
    )

    ticket_new_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_ticket_new, pattern=r"^ticket:new$"),
        ],
        states={
            WAITING_TICKET_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticket_message)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_via_menu, pattern=r"^menu:"),
        ],
        per_message=False,
    )

    ticket_reply_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_ticket_reply_user, pattern=r"^ticketreply_user:"),
        ],
        states={
            WAITING_TICKET_REPLY_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ticket_reply_user)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_via_menu, pattern=r"^menu:"),
        ],
        per_message=False,
    )

    reseller_name_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_reseller_name, pattern=r"^rnamecustom:"),
        ],
        states={
            WAITING_RESELLER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_reseller_name)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_via_menu, pattern=r"^menu:"),
        ],
        per_message=False,
    )

    reseller_reason_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(ask_reseller_reason, pattern=r"^reseller:reqreason$"),
        ],
        states={
            WAITING_RESELLER_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_reseller_reason)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel_via_menu, pattern=r"^menu:"),
        ],
        per_message=False,
    )

    return [
        CommandHandler("start", start),
        CallbackQueryHandler(handle_checkjoin, pattern=r"^checkjoin$"),
        CallbackQueryHandler(handle_setlang, pattern=r"^setlang:"),
        CallbackQueryHandler(onboarding_router, pattern=r"^onboarding:"),
        CallbackQueryHandler(show_referral_leaderboard, pattern=r"^referral:"),
        CallbackQueryHandler(handle_rating, pattern=r"^rate:"),
        receipt_conv,
        topup_conv,
        service_search_conv,
        service_note_conv,
        custom_name_conv,
        discount_code_conv,
        CallbackQueryHandler(handle_discount_remove, pattern=r"^discountremove:"),
        service_transfer_conv,
        wallet_transfer_conv,
        ticket_new_conv,
        ticket_reply_conv,
        reseller_reason_conv,
        reseller_name_conv,
        CallbackQueryHandler(handle_reseller_name_random, pattern=r"^rnamerandom:"),
        CallbackQueryHandler(handle_reseller_topup, pattern=r"^rtopup:"),
        CallbackQueryHandler(reseller_router, pattern=r"^reseller:"),
        CallbackQueryHandler(handle_reseller_buy_select, pattern=r"^resellerbuy:"),
        CallbackQueryHandler(handle_reseller_purchase_confirm, pattern=r"^resellerconfirm:"),
        CallbackQueryHandler(show_wallet_transactions, pattern=r"^wallettx:show$"),
        CallbackQueryHandler(heavy_limited(confirm_wallet_transfer), pattern=r"^wallettransferconfirm:"),
        CallbackQueryHandler(show_faq, pattern=r"^faq:show$"),
        CallbackQueryHandler(show_ticket_list, pattern=r"^ticket:list$"),
        CallbackQueryHandler(show_ticket_detail, pattern=r"^ticketview:"),
        CallbackQueryHandler(handle_ticket_close_user, pattern=r"^ticketuserclose:"),
        CallbackQueryHandler(choose_plan, pattern=r"^plan:"),
        CallbackQueryHandler(handle_name_random, pattern=r"^namerandom:"),
        CallbackQueryHandler(handle_plan_duration, pattern=r"^plandur:"),
        CallbackQueryHandler(handle_location_chosen, pattern=r"^location:"),
        CallbackQueryHandler(handle_trial_location, pattern=r"^triallocation:"),
        CallbackQueryHandler(choose_renew_sub, pattern=r"^renew:"),
        CallbackQueryHandler(handle_weekly_summary_toggle, pattern=r"^wsum:"),
        CallbackQueryHandler(handle_renew_duration, pattern=r"^renewdur:"),
        CallbackQueryHandler(handle_renew_location, pattern=r"^renewlocation:"),
        CallbackQueryHandler(choose_renew_plan, pattern=r"^renewplan:"),
        CallbackQueryHandler(heavy_limited(pay_new_with_wallet), pattern=r"^walletpay:"),
        CallbackQueryHandler(heavy_limited(pay_renew_with_wallet), pattern=r"^walletrenewpay:"),
        CallbackQueryHandler(show_card_payment_details, pattern=r"^pay:"),
        CallbackQueryHandler(show_card_payment_details_renew, pattern=r"^renewpay:"),
        CallbackQueryHandler(back_to_payment_step, pattern=r"^paycardback:"),
        CallbackQueryHandler(back_to_renew_payment_step, pattern=r"^paycardbackrenew:"),
        CallbackQueryHandler(heavy_limited(handle_autosms_new), pattern=r"^autosms:"),
        CallbackQueryHandler(heavy_limited(handle_autosms_renew), pattern=r"^autosmsrenew:"),
        CallbackQueryHandler(heavy_limited(handle_autosms_topup), pattern=r"^autosmstopup:"),
        CallbackQueryHandler(heavy_limited(handle_autosms_check), pattern=r"^atcheck:"),
        CallbackQueryHandler(handle_autosms_cancel, pattern=r"^atcancel:"),
        CallbackQueryHandler(heavy_limited(handle_tonpays_new), pattern=r"^tonpays:"),
        CallbackQueryHandler(heavy_limited(handle_tonpays_renew), pattern=r"^tonpaysrenew:"),
        CallbackQueryHandler(heavy_limited(handle_tonpays_topup), pattern=r"^tonpaystopup:"),
        CallbackQueryHandler(heavy_limited(handle_tonpays_check), pattern=r"^tpcheck:"),
        CallbackQueryHandler(handle_cryptopay_new, pattern=r"^cryptopay:"),
        CallbackQueryHandler(handle_cryptopay_renew, pattern=r"^cryptopayrenew:"),
        CallbackQueryHandler(handle_cryptopay_topup, pattern=r"^cryptopaytopup:"),
        CallbackQueryHandler(handle_topup_card_selected, pattern=r"^topupcard:"),
        CallbackQueryHandler(heavy_limited(handle_crypto_currency_chosen), pattern=r"^cryptocur:"),
        CallbackQueryHandler(heavy_limited(handle_crypto_check), pattern=r"^cryptocheck:"),
        CallbackQueryHandler(show_platform_guide, pattern=r"^platform:"),
        CallbackQueryHandler(handle_services_sort, pattern=r"^svcsort:"),
        CallbackQueryHandler(handle_services_page, pattern=r"^svcpage:"),
        CallbackQueryHandler(handle_service_detail, pattern=r"^svcdetail:"),
        CallbackQueryHandler(handle_autorenew_toggle, pattern=r"^autorenew:"),
        CallbackQueryHandler(clear_service_search, pattern=r"^svcsearch:clear$"),
        CallbackQueryHandler(handle_svc_getsub, pattern=r"^svcgetsub:"),
        CallbackQueryHandler(handle_svc_getconfigs, pattern=r"^svcgetconfigs:"),
        CallbackQueryHandler(handle_svc_refreshlink, pattern=r"^svcrefreshlink:"),
        CallbackQueryHandler(handle_svc_check_online, pattern=r"^svccheckonline:"),
        CallbackQueryHandler(handle_svc_note, pattern=r"^svcnote:"),
        CallbackQueryHandler(handle_svc_delete_ask, pattern=r"^svcdeleteask:"),
        CallbackQueryHandler(handle_svc_delete, pattern=r"^svcdelete:"),
        CallbackQueryHandler(handle_noop, pattern=r"^noop$"),
        CallbackQueryHandler(menu_router, pattern=r"^menu:"),
        MessageHandler(
            filters.TEXT & filters.Regex("^(" + "|".join(re.escape(k) for k in REPLY_MENU_ACTIONS) + ")$"),
            reply_menu_router,
        ),
    ]
