"""
ارسال «پیام غنی» تلگرام (Rich Messages، از Bot API 10.1): جدول واقعی، تیتر، لیست و بخش‌های
جمع‌شونده به‌جای متن ساده.

چرا مستقیم به API میزنیم: کتابخونه‌ی python-telegram-bot هنوز متد sendRichMessage رو نداره، پس
با httpx همین درخواست رو خودمون می‌فرستیم (بدون وابستگی به نسخه‌ی کتابخونه).

پایه‌ی امن: send_rich_or_classic هر وقت پیام غنی خاموش باشه (RICH_MESSAGES_ENABLED) یا تلگرام
ارسالش رو رد کنه، همون پیام «کلاسیک» قبلی رو می‌فرسته؛ یعنی هیچ‌وقت پیام گم نمیشه.

نکته: ساختار دقیق تگ‌ها (مثل <table>/<details>) رو نمیشه بدون تلگرام واقعی تایید کرد؛ برای همین
ادمین با /richtest چند نمونه می‌فرسته و جواب تلگرام رو می‌بینه، قبل از اینکه به جایی وصلش کنیم.
"""
import contextlib
import contextvars
import html as _html
import logging
import re

import httpx


from config import BOT_TOKEN, RICH_MESSAGES_ENABLED
import premium_hook as _ph   # تبدیل خودکار ایموجی معمولی به پریمیوم (متن + آیکون دکمه‌ها)

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"


class Raw(str):
    """HTML آماده (مثلاً تگ ایموجی پریمیوم) که نباید escape بشه"""


def esc(value) -> str:
    return value if isinstance(value, Raw) else _html.escape(str(value), quote=False)


RTL_LANGS = {"fa"}


def is_rtl(lang) -> bool:
    """زبان‌های راست‌به‌چپ بات (فعلاً فقط فارسی)"""
    return lang in RTL_LANGS


def enabled() -> bool:
    return bool(RICH_MESSAGES_ENABLED)


_SUPPRESS = contextvars.ContextVar("rich_suppress", default=False)


@contextlib.contextmanager
def suppress():
    """داخل این بلاک رهگیر عمومی پیام غنی کار نمی‌کنه (برای وقتی که نسخه‌ی غنی همین پیام تازه رد شده و پیام کلاسیک میره)"""
    token = _SUPPRESS.set(True)
    try:
        yield
    finally:
        _SUPPRESS.reset(token)


def suppressed() -> bool:
    return _SUPPRESS.get()


_RTL_CHARS = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")


def text_is_rtl(text: str) -> bool:
    """متنی که حتی یه حرف فارسی/عربی داره، راست‌به‌چپ نمایش داده میشه"""
    return bool(_RTL_CHARS.search(text or ""))


# ---------------- سازنده‌های ساده‌ی HTML ----------------
def heading(text, level: int = 2) -> Raw:
    level = min(max(int(level), 1), 4)
    return Raw(f"<h{level}>{esc(text)}</h{level}>")


def paragraph(*parts) -> Raw:
    """پاراگراف؛ هر بخش اگه Raw نباشه escape میشه (پس میشه متن و تگ ایموجی رو قاطی داد)"""
    return Raw("<p>" + "".join(esc(p) for p in parts) + "</p>")


def divider() -> Raw:
    return Raw("<hr/>")


def bullet_list(items) -> Raw:
    return Raw("<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>")


def details(summary, body_html) -> Raw:
    """بخش جمع‌شونده؛ body_html باید HTML آماده باشه (مثلاً خروجی paragraph/bullet_list)"""
    return Raw(f"<details><summary>{esc(summary)}</summary>{body_html}</details>")


def table(rows, header=None, bordered: bool = True, striped: bool = False, compact: bool = False, rtl: bool = True,
          caption=None, row_headers: bool = False) -> Raw:
    """
    جدول. rows = لیستی از ردیف‌ها (هر ردیف لیستی از سلول‌ها)؛ header = ردیف عنوان (اختیاری).
    متن سلول‌ها escape میشه مگر اینکه Raw باشه.
    rtl=True (پیش‌فرض، برای فارسی): سلول‌ها راست‌چین‌ان؛ تلگرام هم با is_rtl ستون اول رو سمت راست می‌ذاره.
    row_headers=True: سلول اول هر ردیف «سلول عنوان» (<th>) میشه؛ تلگرام اون ستون رو با رنگ جدا (روشن‌تر)
      نشون میده، یعنی ستون برچسب‌ها سیاهِ یکدست نیست و از ستون مقدارها متمایزه.
    caption: عنوان بالای جدول (<caption>).
    """
    attrs = "".join(
        f" {name}" for name, on in (("bordered", bordered), ("striped", striped), ("compact", compact)) if on
    )
    cell = f' align="{"right" if rtl else "left"}" valign="middle"'
    out = [f"<table{attrs}>"]
    if caption:
        out.append(f"<caption>{esc(caption)}</caption>")
    if header:
        out.append("<tr>" + "".join(f"<th{cell}>{esc(c)}</th>" for c in header) + "</tr>")
    for row in rows:
        cells = []
        for idx, c in enumerate(row):
            # ردیفِ تک‌سلولی باید <td> باشه؛ تلگرام عرض <th> رو حدود ۵۵٪ جدول می‌گیره و بقیه‌ی کادر خالی می‌مونه
            tag = "th" if (row_headers and idx == 0 and len(row) > 1) else "td"
            cells.append(f"<{tag}{cell}>{esc(c)}</{tag}>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</table>")
    return Raw("".join(out))


def mark(text) -> Raw:
    """هایلایت (<mark>) برای مقدارهای مهم مثل موجودی؛ تلگرام با پس‌زمینه‌ی رنگی نشونش میده"""
    return Raw(f"<mark>{esc(text)}</mark>")


def bold(text) -> Raw:
    return Raw(f"<b>{esc(text)}</b>")


def code(text) -> Raw:
    return Raw(f"<code>{esc(text)}</code>")


def callout(*parts, credit=None) -> Raw:
    """کادر نقل‌قولی (<blockquote>) برای هشدار/نکته؛ parts: متن‌ها و Raw ها پشت‌سرهم"""
    body = "".join(esc(p) for p in parts)
    cite = f"<cite>{esc(credit)}</cite>" if credit else ""
    return Raw(f"<blockquote>{body}{cite}</blockquote>")


def aside(*parts, credit=None) -> Raw:
    """نقل‌قول وسط‌چین (<aside>) برای تاکید روی یه جمله (مثلاً کد تخفیف)"""
    body = "".join(esc(p) for p in parts)
    cite = f"<cite>{esc(credit)}</cite>" if credit else ""
    return Raw(f"<aside>{body}{cite}</aside>")


def footer(text) -> Raw:
    return Raw(f"<footer>{esc(text)}</footer>")


def document(*blocks) -> str:
    """چند بلوک رو پشت‌سرهم به یه HTML واحد تبدیل می‌کنه"""
    return "".join(str(b) for b in blocks)


# ---------------- ارسال ----------------
def _rich_body(html, markdown, rtl, skip_entity_detection) -> dict:
    if (html is None) == (markdown is None):
        raise ValueError("دقیقاً یکی از html یا markdown باید داده بشه")
    rich = {"html": _ph.premium_html(html)} if html is not None else {"markdown": markdown}
    if rtl:
        rich["is_rtl"] = True   # فارسی: جهت کل پیام راست‌به‌چپ (ترتیب ستون‌های جدول و ...)
    if skip_entity_detection:
        rich["skip_entity_detection"] = True   # شناسه‌ها و مبلغ‌ها اتولینک (شماره تلفن/کارت) نشن
    return rich


def _markup_dict(reply_markup):
    d = reply_markup.to_dict() if hasattr(reply_markup, "to_dict") else reply_markup
    return _ph.fix_markup_dict(d)


async def edit_rich(chat_id, message_id, *, html=None, markdown=None, reply_markup=None, rtl=True,
                    skip_entity_detection=True, timeout=20):
    """
    پیام موجود رو با محتوای غنی ویرایش می‌کنه (editMessageText با rich_message).
    خروجی: (True, None) یا (False, «توضیح خطا»)؛ هیچ‌وقت exception نمیده.
    """
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "rich_message": _rich_body(html, markdown, rtl, skip_entity_detection),
    }
    if reply_markup is not None:
        payload["reply_markup"] = _markup_dict(reply_markup)
    ok, info, _ = await _post("editMessageText", payload, timeout)
    return ok, info


async def edit_rich_raw(chat_id, message_id, *, html=None, reply_markup=None, rtl=True, skip_entity_detection=True, timeout=20):
    """مثل edit_rich ولی جواب خام تلگرام (Message دیکشنری یا True) رو هم برمی‌گردونه: (ok, info, result)"""
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "rich_message": _rich_body(html, None, rtl, skip_entity_detection),
    }
    if reply_markup is not None:
        payload["reply_markup"] = _markup_dict(reply_markup)
    return await _post("editMessageText", payload, timeout)


async def send_rich(chat_id, *, html=None, markdown=None, reply_markup=None, rtl=True, skip_entity_detection=True, timeout=20):
    """
    پیام غنی می‌فرسته. خروجی: (True, message_id) یا (False, «توضیح خطا»). هیچ‌وقت exception نمیده.
    دقیقاً یکی از html یا markdown باید داده بشه (قانون خود تلگرام).
    """
    payload = {"chat_id": chat_id, "rich_message": _rich_body(html, markdown, rtl, skip_entity_detection)}
    if reply_markup is not None:
        payload["reply_markup"] = _markup_dict(reply_markup)
    ok, info, _ = await _post("sendRichMessage", payload, timeout)
    return ok, info


async def send_rich_raw(chat_id, *, html=None, reply_markup=None, rtl=True, skip_entity_detection=True, timeout=20, extra=None):
    """مثل send_rich ولی جواب خام تلگرام (دیکشنری Message) رو هم برمی‌گردونه: (ok, info, result)"""
    payload = {"chat_id": chat_id, "rich_message": _rich_body(html, None, rtl, skip_entity_detection)}
    if reply_markup is not None:
        payload["reply_markup"] = _markup_dict(reply_markup)
    if extra:
        payload.update(extra)
    return await _post("sendRichMessage", payload, timeout)


async def _post(method, payload, timeout):
    url = _API.format(token=BOT_TOKEN, method=method)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
        data = resp.json()
    except Exception as e:  # شبکه، JSON خراب و ...
        return False, f"{type(e).__name__}: {e}", None
    if data.get("ok"):
        result = data.get("result")
        return True, (result.get("message_id") if isinstance(result, dict) else None), result
    return False, data.get("description") or f"HTTP {getattr(resp, 'status_code', '?')}", None


async def send_rich_or_classic(bot, chat_id, rich_html, classic_text, *, reply_markup=None, classic_parse_mode="HTML", rtl=True):
    """
    اگه پیام غنی روشن باشه و تلگرام قبولش کنه، همونو می‌فرسته؛ وگرنه پیام کلاسیک (classic_text).
    خروجی: True اگه پیام غنی رفت، False اگه کلاسیک رفت.
    """
    if RICH_MESSAGES_ENABLED and rich_html:
        ok, info = await send_rich(chat_id, html=rich_html, reply_markup=reply_markup, rtl=rtl)
        if ok:
            return True
        logger.warning("ارسال پیام غنی به %s ناموفق بود (%s)؛ پیام کلاسیک فرستاده میشه", chat_id, info)
    with suppress():   # رهگیر عمومی دوباره همین پیام رو غنی نکنه (تازه رد شده)
        await bot.send_message(chat_id, classic_text, reply_markup=reply_markup, parse_mode=classic_parse_mode)
    return False
