"""
پیگیری تست رایگان: اگه کاربر بعد از چند دقیقه هنوز به سرویس تستش وصل نشده بود،
بات خودش بهش پیام میده و راهنمایی/پشتیبانی پیشنهاد میکنه.

جریان کار:
۱. هر ۶۰ ثانیه یه جاب (trial_followup_job) اجرا میشه و تست‌های رایگانی رو پیدا میکنه
   که بیشتر از TRIAL_FOLLOWUP_MINUTES دقیقه از ساختشون گذشته (و کمتر از یک ساعت
   بعد از اون، تا بعد از خاموشی/ری‌استارت بات یهو پیام‌های کهنه نره).
۲. مصرف ترافیک سرویس از پنل خونده میشه. اگه مصرف از حداقل (TRIAL_FOLLOWUP_MIN_KB)
   بیشتر باشه یعنی کاربر وصل شده و هیچ پیامی نمیره.
۳. اگه وصل نشده بود، یه پیام با دو دکمه میره: «متصل شدم» (سبز) و «متصل نشدم» (قرمز).
   - «متصل شدم»: فقط دکمه‌ها برمی‌دارن؛ همین.
   - «متصل نشدم»: یه پیام دوم با دکمه‌ی پشتیبانی تلگرام (آبی) میاد.

این فایل کاملاً مستقله: هیچ فایل دیگه‌ای از ربات رو تغییر نمیده (جدول خودش رو هم
خودش می‌سازه). فقط تو bot.py ثبت میشه. با TRIAL_FOLLOWUP_ENABLED=false خاموش میشه.

نکته: تست‌های رایگان چه از داخل بات و چه از Mini App ساخته بشن، چون هر دو توی
جدول subscriptions با plan_id='trial' ثبت میشن، هر دو پوشش داده میشن.
"""
import logging
import os
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes

import database as db
import premium_emoji as pe
from config import SUPPORT_LINK
from panel_client import panel, PanelError

import theme
logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


ENABLED = os.getenv("TRIAL_FOLLOWUP_ENABLED", "true").lower() in ("1", "true", "yes")
DELAY_MINUTES = max(1, _env_int("TRIAL_FOLLOWUP_MINUTES", 10))
# زیر این مقدار مصرف، یعنی کاربر فقط لینک رو باز کرده و واقعاً وصل نشده
MIN_USED_BYTES = max(0, _env_int("TRIAL_FOLLOWUP_MIN_KB", 100)) * 1024
# بعد از این مدت از زمان مقرر، دیگه پیام نمی‌فرستیم (مثلاً بات چند ساعت خاموش بوده)
LATE_WINDOW_MINUTES = 60

# ---------------------------------------------------------------------------
# متن‌ها (فارسی / انگلیسی / روسی). ایموجی‌ها همه پرمیوم هستن و با parse_mode=HTML میان.
# ---------------------------------------------------------------------------
_TEXT = {
    "ask": {
        "fa": (
            f"{pe.TRIAL} <b>تست رایگانت چطور پیش رفت؟</b>\n\n"
            "متوجه شدیم هنوز به سرویس تستت وصل نشدی. می‌دونیم وقتی از همون اول چیزی کار نمی‌کنه "
            "چقدر رو اعصابه، ولی قبل از اینکه بگی «به درد نمی‌خوره»، یه فرصت بده بررسیش کنیم.\n\n"
            f"{pe.CONNECTION} معمولاً دلیلش یه چیز ساده‌ست؛ مثلاً آپدیت‌نبودن برنامه‌ی کلاینت یا "
            "اشتباه وارد شدن لینک، و با چند دقیقه راهنمایی درست میشه.\n\n"
            f"{pe.SUPPORT} اگه وصل نشدی، پشتیبانی همین‌جاست؛ بهمون پیام بده تا قدم‌به‌قدم درستش کنیم.\n\n"
            f"الان وضعیتت چیه؟ {pe.DOWN_ARROW}"
        ),
        "en": (
            f"{pe.TRIAL} <b>How did your free trial go?</b>\n\n"
            "We noticed you haven't connected to your trial service yet. We know how annoying it is "
            "when something doesn't work from the very start, but before you decide it's not for you, "
            "give us a chance to look into it.\n\n"
            f"{pe.CONNECTION} Usually the cause is something simple, like an outdated client app or a "
            "mistyped link, and a few minutes of guidance fixes it.\n\n"
            f"{pe.SUPPORT} If you couldn't connect, support is right here. Message us and we'll fix it "
            "together, step by step.\n\n"
            f"So, how are things now? {pe.DOWN_ARROW}"
        ),
        "ru": (
            f"{pe.TRIAL} <b>Как прошёл ваш бесплатный тест?</b>\n\n"
            "Мы заметили, что вы ещё не подключились к тестовой услуге. Понимаем, как это раздражает, "
            "когда что-то не работает с самого начала, но прежде чем решить, что это не для вас, "
            "дайте нам шанс всё проверить.\n\n"
            f"{pe.CONNECTION} Обычно причина простая: устаревшее приложение или неверно введённая "
            "ссылка, и пара минут помощи решают проблему.\n\n"
            f"{pe.SUPPORT} Если подключиться не удалось, поддержка рядом. Напишите нам, и мы всё "
            "исправим шаг за шагом.\n\n"
            f"Как у вас сейчас дела? {pe.DOWN_ARROW}"
        ),
    },
    "btn_ok": {"fa": "متصل شدم", "en": "I'm connected", "ru": "Я подключился"},
    "btn_no": {"fa": "متصل نشدم", "en": "I couldn't connect", "ru": "Не удалось подключиться"},
    "ok_toast": {
        "fa": "عالیه، لذت ببر!",
        "en": "Great, enjoy!",
        "ru": "Отлично, приятного использования!",
    },
    "help": {
        "fa": (
            f"{pe.SUPPORT} <b>نگران نباش، درستش می‌کنیم</b>\n\n"
            "متأسفیم که وصل نشدی. لطفاً با پشتیبانی در ارتباط باش تا بررسی کنیم؛ کافیه بگی با چه "
            "دستگاهی (اندروید، آیفون، ویندوز و...) و با کدوم برنامه امتحان کردی تا سریع‌تر وصلت کنیم.\n\n"
            f"{pe.CHAT} روی دکمه‌ی زیر بزن تا مستقیم وارد گفتگو با پشتیبانی بشی."
        ),
        "en": (
            f"{pe.SUPPORT} <b>Don't worry, we'll sort it out</b>\n\n"
            "Sorry you couldn't connect. Please get in touch with support so we can look into it; just "
            "tell them which device (Android, iPhone, Windows, etc.) and which app you tried, and "
            "we'll get you connected faster.\n\n"
            f"{pe.CHAT} Tap the button below to chat with support directly."
        ),
        "ru": (
            f"{pe.SUPPORT} <b>Не переживайте, мы всё решим</b>\n\n"
            "Жаль, что не удалось подключиться. Пожалуйста, свяжитесь с поддержкой, чтобы мы всё "
            "проверили; просто напишите, с какого устройства (Android, iPhone, Windows и т.д.) и "
            "через какое приложение вы пробовали, и мы подключим вас быстрее.\n\n"
            f"{pe.CHAT} Нажмите кнопку ниже, чтобы написать в поддержку."
        ),
    },
    "btn_support": {"fa": "ارتباط با پشتیبانی", "en": "Contact support", "ru": "Связаться с поддержкой"},
}


def _tr(key: str, lang: str) -> str:
    entry = _TEXT[key]
    return entry.get(lang) or entry["fa"]


# ---------------------------------------------------------------------------
# دیتابیس: یه جدول کوچیک برای اینکه به هر تست فقط یک‌بار پیام بدیم
# ---------------------------------------------------------------------------
_table_ready = False


def _ensure_table():
    global _table_ready
    if _table_ready:
        return
    with db.get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trial_followups (
                sub_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL,       -- sent / connected / not_connected / connected_auto / skipped / send_failed
                updated_at INTEGER
            )
            """
        )
    _table_ready = True


def _find_candidates(now: int):
    _ensure_table()
    newest = now - DELAY_MINUTES * 60
    oldest = now - (DELAY_MINUTES + LATE_WINDOW_MINUTES) * 60
    with db.get_conn() as conn:
        return conn.execute(
            """
            SELECT s.* FROM subscriptions s
            LEFT JOIN trial_followups f ON f.sub_id = s.sub_id
            WHERE s.plan_id = 'trial'
              AND s.created_at IS NOT NULL
              AND s.created_at <= ? AND s.created_at >= ?
              AND f.sub_id IS NULL
            """,
            (newest, oldest),
        ).fetchall()


def _claim(sub_id: int, user_id: int, status: str) -> bool:
    """اولین نفری که ردیف رو بسازه برنده‌ست؛ از ارسال دوباره‌ی پیام جلوگیری می‌کنه."""
    _ensure_table()
    with db.get_conn() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO trial_followups (sub_id, user_id, status, updated_at) VALUES (?, ?, ?, ?)",
            (sub_id, user_id, status, int(time.time())),
        )
        return cur.rowcount == 1


def _set_status(sub_id: int, status: str):
    _ensure_table()
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE trial_followups SET status = ?, updated_at = ? WHERE sub_id = ?",
            (status, int(time.time()), sub_id),
        )


def _get_status(sub_id: int):
    _ensure_table()
    with db.get_conn() as conn:
        row = conn.execute("SELECT status FROM trial_followups WHERE sub_id = ?", (sub_id,)).fetchone()
    return row["status"] if row else None


# ---------------------------------------------------------------------------
# کیبوردها (رنگ دکمه‌ها مطابق بقیه‌ی بات: سبز = تایید، قرمز = مشکل، آبی = پشتیبانی)
# ---------------------------------------------------------------------------
def _ask_keyboard(sub_id: int, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _tr("btn_ok", lang),
                    callback_data=f"trialfu:ok:{sub_id}",
                    icon_custom_emoji_id=pe.RAW["CONFIRM"],
                    style=theme.CTA,
                ),
                InlineKeyboardButton(
                    _tr("btn_no", lang),
                    callback_data=f"trialfu:no:{sub_id}",
                    icon_custom_emoji_id=pe.RAW["REJECT"],
                    style="danger",
                ),
            ]
        ]
    )


def _support_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _tr("btn_support", lang),
                    url=SUPPORT_LINK,
                    icon_custom_emoji_id=pe.RAW["SUPPORT"],
                    style=theme.NAV,
                )
            ]
        ]
    )


# ---------------------------------------------------------------------------
# جاب دوره‌ای
# ---------------------------------------------------------------------------
async def _process(context: ContextTypes.DEFAULT_TYPE, sub):
    sub_id = sub["sub_id"]
    user_id = sub["user_id"]
    username = sub["marzban_username"]
    if not username:
        _claim(sub_id, user_id, "skipped")
        return

    try:
        info = await panel.get_user(username, include_config=False)
    except PanelError:
        # مشکل موقت پنل (یا سرویس از پنل حذف شده)؛ دقیقه‌ی بعد دوباره امتحان میشه
        return

    if (info.get("used_traffic") or 0) >= MIN_USED_BYTES:
        _claim(sub_id, user_id, "connected_auto")   # وصل شده، پیامی لازم نیست
        return
    if info.get("status") not in (None, "active"):
        _claim(sub_id, user_id, "skipped")          # غیرفعال/منقضی شده
        return

    if not _claim(sub_id, user_id, "sent"):
        return
    lang = db.get_user_language(user_id)
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=_tr("ask", lang),
            reply_markup=_ask_keyboard(sub_id, lang),
            parse_mode="HTML",
        )
    except Exception:
        _set_status(sub_id, "send_failed")          # مثلاً کاربر بات رو بلاک کرده
        logger.warning("ارسال پیام پیگیری تست رایگان به کاربر %s ناموفق بود", user_id)


async def trial_followup_job(context: ContextTypes.DEFAULT_TYPE):
    if not ENABLED:
        return
    try:
        candidates = _find_candidates(int(time.time()))
    except Exception:
        logger.exception("خواندن لیست تست‌های رایگان برای پیگیری ناموفق بود")
        return
    for sub in candidates:
        try:
            await _process(context, sub)
        except Exception:
            logger.exception("پیگیری تست رایگان #%s با خطا مواجه شد", sub["sub_id"])


# ---------------------------------------------------------------------------
# دکمه‌ها
# ---------------------------------------------------------------------------
async def _strip_keyboard(query):
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass


async def handle_trial_followup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = (query.data or "").split(":")           # trialfu:ok:<sub_id>  یا  trialfu:no:<sub_id>
    if len(parts) != 3 or parts[1] not in ("ok", "no"):
        await query.answer()
        return
    try:
        sub_id = int(parts[2])
    except ValueError:
        await query.answer()
        return

    user_id = update.effective_user.id
    sub = db.get_subscription(sub_id)
    if not sub or sub["user_id"] != user_id:        # فقط صاحب سرویس
        await query.answer()
        return

    lang = db.get_user_language(user_id)
    if _get_status(sub_id) != "sent":               # قبلاً جواب داده؛ دوباره‌کاری نکن
        await query.answer()
        await _strip_keyboard(query)
        return

    if parts[1] == "ok":
        _set_status(sub_id, "connected")
        await query.answer(_tr("ok_toast", lang))
        await _strip_keyboard(query)
        return

    _set_status(sub_id, "not_connected")
    await query.answer()
    await _strip_keyboard(query)
    await context.bot.send_message(
        chat_id=user_id,
        text=_tr("help", lang),
        reply_markup=_support_keyboard(lang),
        parse_mode="HTML",
    )


def build_trial_followup_handlers():
    return [CallbackQueryHandler(handle_trial_followup, pattern=r"^trialfu:")]
