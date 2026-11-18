"""
رهگیر عمومی پیام‌های بات: وقتی «پیام غنی» روشنه، هر پیام متنیِ HTML که بات به یه کاربر می‌فرسته (یا
ویرایش می‌کنه) اول به پیام غنی (rich_convert) تبدیل و با sendRichMessage / editMessageText فرستاده
میشه؛ اگه تلگرام رد کنه همون پیام کلاسیک می‌ره. اینطوری همه‌ی بخش‌های بات (هشدارها، رسیدها،
پیام‌های خرید و ...) بدون دست‌زدن به تک‌تک‌شون ظاهر یکدست و مرتب می‌گیرن.

با install() یک‌بار روی کلاس telegram.Bot نصب میشه (ExtBot هم از همین عبور می‌کنه). صفحه‌های طراحی‌شده‌ی
دستی (rich_screens) مستقیم با rich_messages می‌فرستن و از این رهگیر رد نمیشن.
پیام‌هایی که رهگیر بهشون دست نمیزنه: گروه/کانال، پیام‌های با entities/ریپلای/ترد/بیزینس، و هر چیزی که parse_mode=HTML نباشه.
"""
import logging
import types

import rich_messages as rm
from rich_convert import classic_to_rich

logger = logging.getLogger(__name__)
_SKIP_KW = ("entities", "reply_parameters", "reply_to_message_id", "message_thread_id", "business_connection_id", "link_preview_options")
_logged = set()


def _is_default(x) -> bool:
    return x.__class__.__name__ == "DefaultValue"


def _clean(x):
    return None if _is_default(x) else x


def _is_html(parse_mode) -> bool:
    return isinstance(_clean(parse_mode), str) and str(_clean(parse_mode)).upper().endswith("HTML")


def _private(chat_id) -> bool:
    try:
        return int(chat_id) > 0
    except (TypeError, ValueError):
        return False


def _eligible(kwargs, text) -> bool:
    if not (rm.enabled() and not rm.suppressed()):
        return False
    if not isinstance(text, str) or not _is_html(kwargs.get("parse_mode")):
        return False
    return not any(_clean(kwargs.get(k)) for k in _SKIP_KW)


def _log_once(description):
    if description not in _logged:
        _logged.add(description)
        logger.warning("پیام غنی رد شد (%s)؛ پیام کلاسیک فرستاده میشه", description)


def _to_message(bot, result, chat_id):
    try:
        from telegram import Message

        msg = Message.de_json(result, bot)
        if msg is not None:
            return msg
    except Exception:
        pass
    mid = result.get("message_id") if isinstance(result, dict) else None
    return types.SimpleNamespace(message_id=mid, chat_id=chat_id, chat=types.SimpleNamespace(id=chat_id))


async def rich_send(bot, args, kwargs):
    chat_id = args[0] if len(args) > 0 else kwargs.get("chat_id")
    text = args[1] if len(args) > 1 else kwargs.get("text")
    if not _private(chat_id) or not _eligible(kwargs, text):
        return None
    html = classic_to_rich(text, rtl=rm.text_is_rtl(text))
    if not html:
        return None
    ok, info, result = await rm.send_rich_raw(
        int(chat_id), html=html, reply_markup=_clean(kwargs.get("reply_markup")), rtl=rm.text_is_rtl(text)
    )
    if not ok:
        _log_once(info)
        return None
    return _to_message(bot, result, int(chat_id))


async def rich_edit(bot, args, kwargs):
    text = args[0] if len(args) > 0 else kwargs.get("text")
    chat_id = args[1] if len(args) > 1 else kwargs.get("chat_id")
    message_id = args[2] if len(args) > 2 else kwargs.get("message_id")
    if kwargs.get("inline_message_id") or not chat_id or not message_id or not _private(chat_id) or not _eligible(kwargs, text):
        return None
    html = classic_to_rich(text, rtl=rm.text_is_rtl(text))
    if not html:
        return None
    ok, info, result = await rm.edit_rich_raw(
        int(chat_id), int(message_id), html=html, reply_markup=_clean(kwargs.get("reply_markup")), rtl=rm.text_is_rtl(text)
    )
    if not ok:
        _log_once(info)
        return None
    return _to_message(bot, result, int(chat_id)) if isinstance(result, dict) else True


def install(bot_cls=None):
    """رهگیر رو روی telegram.Bot نصب می‌کنه (فقط یک‌بار)"""
    if bot_cls is None:
        import telegram

        bot_cls = telegram.Bot
    if getattr(bot_cls, "_rich_installed", False):
        return False
    orig_send, orig_edit = bot_cls.send_message, bot_cls.edit_message_text

    async def send_message(self, *args, **kwargs):
        try:
            res = await rich_send(self, args, kwargs)
        except Exception:
            logger.exception("رهگیر پیام غنی (ارسال) خطا داد؛ پیام کلاسیک فرستاده میشه")
            res = None
        return res if res is not None else await orig_send(self, *args, **kwargs)

    async def edit_message_text(self, *args, **kwargs):
        try:
            res = await rich_edit(self, args, kwargs)
        except Exception:
            logger.exception("رهگیر پیام غنی (ویرایش) خطا داد؛ ویرایش کلاسیک انجام میشه")
            res = None
        return res if res is not None else await orig_edit(self, *args, **kwargs)

    bot_cls.send_message = send_message
    bot_cls.edit_message_text = edit_message_text
    bot_cls._rich_installed = True
    bot_cls._rich_originals = (orig_send, orig_edit)
    return True
