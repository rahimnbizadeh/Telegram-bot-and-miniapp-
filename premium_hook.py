"""
تبدیل خودکار «تمام» ایموجی‌های معمولیِ بات به ایموجی پریمیوم.

چرا این فایل: قبلاً فقط جاهایی که دستی با pe.XXX نوشته شده بودن پریمیوم بودن و هر ایموجی معمولی که
تو متن/کپشن/دکمه‌ای مونده بود، معمولی نمایش داده میشد. این ماژول یک‌بار روی telegram.Bot نصب میشه و
قبل از ارسال/ویرایش هر پیام:
  - متن/کپشن HTML: هر ایموجی معمولیِ دارای معادل پریمیوم (بانک premium_emoji) با <tg-emoji> عوض میشه.
  - متن/کپشن ساده (بدون parse_mode): اگه ایموجیِ قابل‌تبدیل داشته باشه، متن escape میشه و با
    parse_mode=HTML فرستاده میشه (ظاهر متن دقیقاً همونه، فقط ایموجی‌ها پریمیوم میشن).
  - دکمه‌های شیشه‌ای که ایموجی تو متنشون هست و icon_custom_emoji_id ندارن: ایموجی از متن برداشته و
    به‌صورت آیکون پریمیوم دکمه گذاشته میشه (نیازمند پریمیوم بودن مالک بات؛ مثل بقیه‌ی دکمه‌ها).
پیام‌هایی که entities دارن، parse_mode مارک‌داون دارن، یا ایموجی‌شون معادل پریمیوم نداره (مثل پرچم‌ها)
دست‌نخورده می‌مونن. هر خطایی داخل این ماژول فقط لاگ میشه و پیام همون‌طور که بود فرستاده میشه.

برای مسیرهایی که از python-telegram-bot رد نمیشن (Flask مینی‌اپ، پیام غنی) از premium_html /
premium_plain / fix_markup_dict همین فایل مستقیم استفاده میشه.
"""
import functools
import html as _html
import inspect
import logging

import premium_emoji as pe

logger = logging.getLogger(__name__)

# متد -> (اسم پارامتر متن/کپشن, اسم پارامتر entities)
_SPECS = {
    "send_message": ("text", "entities"),
    "edit_message_text": ("text", "entities"),
    "send_photo": ("caption", "caption_entities"),
    "send_document": ("caption", "caption_entities"),
    "send_video": ("caption", "caption_entities"),
    "send_animation": ("caption", "caption_entities"),
    "send_audio": ("caption", "caption_entities"),
    "send_voice": ("caption", "caption_entities"),
    "edit_message_caption": ("caption", "caption_entities"),
    "edit_message_reply_markup": (None, None),
}


def _is_default(x) -> bool:
    return x.__class__.__name__ == "DefaultValue"


def _clean(x):
    return None if _is_default(x) else x


def _is_html(parse_mode) -> bool:
    v = _clean(parse_mode)
    return v is not None and str(v).upper().endswith("HTML")


def has_premium(text) -> bool:
    """آیا تو این متن ایموجی معمولی‌ای هست که معادل پریمیوم داره؟"""
    if not isinstance(text, str) or not text:
        return False
    return any(pe.CHAR_IDS.get(pe._norm_emoji(m.group(0))) for m in pe._EMOJI_RE.finditer(text))


def premium_html(text):
    """متن HTML تلگرام -> همون متن با ایموجی‌های پریمیوم"""
    if not isinstance(text, str) or not text:
        return text
    return pe.premiumize_html(text)


def premium_plain(text):
    """متن ساده -> HTML امن (escape شده) با ایموجی‌های پریمیوم؛ حتماً با parse_mode=HTML فرستاده بشه"""
    return pe.premiumize_html(_html.escape(text, quote=False))


def fix_markup_dict(markup):
    """
    کیبورد شیشه‌ای به‌شکل dict خام (inline_keyboard): دکمه‌هایی که ایموجیِ قابل‌تبدیل تو متنشون دارن و
    آیکون ندارن، آیکون پریمیوم می‌گیرن. روی کپی کار می‌کنه؛ اگه تغییری لازم نباشه همون ورودی برمی‌گرده.
    """
    if not isinstance(markup, dict):
        return markup
    rows = markup.get("inline_keyboard")
    if not rows:
        return markup
    changed = False
    new_rows = []
    for row in rows:
        new_row = []
        for b in row:
            if (
                isinstance(b, dict)
                and not b.get("icon_custom_emoji_id")
                and isinstance(b.get("text"), str)
                and has_premium(b["text"])
            ):
                icon, clean = pe.button_icon(b["text"])
                if icon:
                    b = dict(b, text=clean, icon_custom_emoji_id=icon)
                    changed = True
            new_row.append(b)
        new_rows.append(new_row)
    if not changed:
        return markup
    out = dict(markup)
    out["inline_keyboard"] = new_rows
    return out


def fix_markup(markup):
    """مثل fix_markup_dict ولی برای شیء InlineKeyboardMarkup کتابخونه"""
    try:
        from telegram import InlineKeyboardMarkup
    except ImportError:
        return markup
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup
    need = any(
        getattr(b, "icon_custom_emoji_id", None) is None and has_premium(getattr(b, "text", ""))
        for row in markup.inline_keyboard
        for b in row
    )
    if not need:
        return markup
    fixed = fix_markup_dict(markup.to_dict())
    return InlineKeyboardMarkup.de_json(fixed, None) or markup


def _prepare(sig, bot, args, kwargs, spec):
    """آرگومان‌های اصلاح‌شده (BoundArguments) یا None اگه چیزی عوض نشد"""
    ba = sig.bind(bot, *args, **kwargs)
    a = ba.arguments
    text_name, ent_name = spec
    changed = False

    if text_name:
        text = a.get(text_name)
        if isinstance(text, str) and text and not _clean(a.get(ent_name)):
            pm = _clean(a.get("parse_mode"))
            if pm is None:
                if has_premium(text):
                    a[text_name] = premium_plain(text)
                    a["parse_mode"] = "HTML"
                    changed = True
            elif _is_html(pm):
                new = premium_html(text)
                if new != text:
                    a[text_name] = new
                    changed = True

    markup = a.get("reply_markup")
    if markup is not None:
        fixed = fix_markup(markup)
        if fixed is not markup:
            a["reply_markup"] = fixed
            changed = True

    return ba if changed else None


def _wrap(orig, spec):
    try:
        sig = inspect.signature(orig)
    except (TypeError, ValueError):
        return None

    @functools.wraps(orig)
    async def wrapper(self, *args, **kwargs):
        ba = None
        try:
            ba = _prepare(sig, self, args, kwargs, spec)
        except Exception:
            logger.exception("تبدیل خودکار ایموجی پریمیوم خطا داد؛ پیام همون‌طور که بود فرستاده میشه")
        if ba is not None:
            return await orig(*ba.args, **ba.kwargs)
        return await orig(self, *args, **kwargs)

    return wrapper


def install(bot_cls=None):
    """روی telegram.Bot نصب میشه (فقط یک‌بار). ExtBot هم از همین متدها عبور می‌کنه."""
    if bot_cls is None:
        import telegram

        bot_cls = telegram.Bot
    if getattr(bot_cls, "_premium_hook_installed", False):
        return False
    for name, spec in _SPECS.items():
        orig = getattr(bot_cls, name, None)
        if orig is None:
            continue
        wrapped = _wrap(orig, spec)
        if wrapped is not None:
            setattr(bot_cls, name, wrapped)
    bot_cls._premium_hook_installed = True
    return True
