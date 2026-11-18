"""
تبدیل خودکارِ پیام «کلاسیک» (HTML ساده‌ی تلگرام با \\n) به پیام غنی: بیشتر پیام‌های بات (رسیدها،
هشدارها، پیام‌های خرید و ...) رو بدون دست‌زدن به تک‌تک‌شون به شکل مرتب (تیتر، جدول «برچسب: مقدار»،
لیست) نمایش میده. صفحه‌های مهم (منو، کیف پول، سرویس، ...) جداگانه و دستی طراحی شدن (rich_screens).

قوانین (خروجی HTML غنیِ معتبر یا None اگه متن مناسب تبدیل نیست):
- هر خط = یه پاراگراف (تو HTML غنی \\n فاصله حساب میشه، خط جدید نیست). خط خالی حذف میشه.
- ۲ خط یا بیشتر پشت‌سرهم به شکل «برچسب: مقدار» → جدول (ستون برچسب سلول عنوان؛ مقدارهای پولی هایلایت).
- خط‌هایی که با • یا - شروع میشن → لیست.
- خط اولِ کوتاهِ بدون «:» (وقتی بعدش محتوا هست) → تیتر.
- بلوک‌های <pre> و <blockquote> دست‌نخورده می‌مونن؛ تگ‌های درون‌خطی (b, i, u, s, code, a, tg-emoji, ...) هم همین‌طور.
"""
import re

import premium_emoji as _pe

_BLOCK_RE = re.compile(r"(<pre\b.*?</pre>|<blockquote\b.*?</blockquote>)", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_BULLET_RE = re.compile(r"^\s*(?:[•▪▫◾◽\-–*])\s+(.*\S)\s*$")
_EMOJI_TAG = r"(?:<tg-emoji\b[^>]*>.*?</tg-emoji>)"
# برچسب: (اختیاری یه ایموجی/تگ‌ایموجی اول) + متن کوتاه بدون تگ + «:»؛ بعدش مقدار
_ROW_RE = re.compile(
    r"^\s*(?P<label>(?:" + _EMOJI_TAG + r"\s*|[^\w\s<:]{1,4}\s*)?[^:<>\n]{1,32}?)\s*[:：]\s*(?P<value>\S.*)$"
)
_MONEY_HINT = ("تومان", "Toman", "TRX", "USDT", "$", "ریال")


def _plain(s: str) -> str:
    return _TAG_RE.sub("", s).strip()


def _row(line: str):
    """اگه خط «برچسب: مقدار» بود، (برچسب، مقدار) برمی‌گردونه"""
    m = _ROW_RE.match(line)
    if not m:
        return None
    label, value = m.group("label").strip(), m.group("value").strip()
    plain_label = _plain(label)
    if not plain_label or re.match(r"^(https?|tg|ftp|mailto|tel)$", plain_label, re.I) or value.startswith("//"):
        return None
    if len(plain_label.split()) > 5:
        return None
    return label, value


def _is_money(value: str) -> bool:
    p = _plain(value)
    return any(h in p for h in _MONEY_HINT) and bool(re.search(r"\d", p))


# اولِ برچسب ایموجی داره؟ (تگ tg-emoji یا یه کاراکتر ایموجی)
_HAS_EMOJI_RE = re.compile(r"^\s*(?:<tg-emoji\b|[\u2190-\u2BFF\u2600-\u27BF\U0001F000-\U0001FAFF])")


def _with_label_emoji(label: str) -> str:
    """ایموجی معمولیِ برچسب رو پریمیوم می‌کنه و اگه برچسب ایموجی نداشت، یکی مناسبِ خودش از بانک می‌ذاره"""
    label = _pe.premiumize_html(label)
    if _HAS_EMOJI_RE.match(label):
        return label
    return f"{_pe.label_emoji(_plain(label))} {label}"


def _flush_rows(rows, out):
    if len(rows) >= 2:
        trs = []
        for label, value in rows:
            label = _with_label_emoji(label)
            val = f"<mark>{value}</mark>" if _is_money(value) and "<" not in value else value
            trs.append(
                f'<tr><th align="{{a}}" valign="middle">{label}</th><td align="{{a}}" valign="middle">{val}</td></tr>'
            )
        out.append(("table", "".join(trs)))
    else:
        for label, value in rows:
            out.append(("p", f"{label}: {value}"))
    rows.clear()


def classic_to_rich(text: str, rtl: bool = True):
    """متن کلاسیک (HTML تلگرام) → HTML غنی؛ None یعنی چیزی برای نمایش نبود"""
    if not text or not text.strip():
        return None
    out = []   # (نوع، محتوا)
    for part in _BLOCK_RE.split(text):
        if not part.strip():
            continue
        if _BLOCK_RE.fullmatch(part.strip()):
            block = part.strip()
            block = re.sub(r"<blockquote\b[^>]*>", "<blockquote>", block, flags=re.I)
            out.append(("raw", block))
            continue
        rows, bullets = [], []
        for raw_line in part.split("\n"):
            line = raw_line.strip()
            if not line:
                _flush_rows(rows, out)
                if bullets:
                    out.append(("ul", bullets[:])); bullets.clear()
                continue
            b = _BULLET_RE.match(line)
            if b:
                _flush_rows(rows, out)
                bullets.append(b.group(1))
                continue
            if bullets:
                out.append(("ul", bullets[:])); bullets.clear()
            r = _row(line)
            if r:
                rows.append(r)
                continue
            _flush_rows(rows, out)
            out.append(("p", line))
        _flush_rows(rows, out)
        if bullets:
            out.append(("ul", bullets[:])); bullets.clear()
    if not out:
        return None

    # خط اولِ کوتاهِ بدون «:» (وقتی بعدش محتوا هست) → تیتر
    if len(out) > 1 and out[0][0] == "p":
        first = out[0][1]
        plain = _plain(first)
        if 0 < len(plain) <= 48 and ":" not in plain and "：" not in plain and not plain.endswith(("؟", "?", "!", ".", "،")):
            out[0] = ("h", first)

    align = "right" if rtl else "left"
    html = []
    for kind, content in out:
        if kind == "p":
            html.append(f"<p>{content}</p>")
        elif kind == "h":
            html.append(f"<h3>{content}</h3>")
        elif kind == "ul":
            html.append("<ul>" + "".join(f"<li>{i}</li>" for i in content) + "</ul>")
        elif kind == "table":
            # compact: حاشیه‌ی داخلی سلول‌ها نصف میشه و مقدارهای بلند (تاریخ و ...) تو ستونِ مقدار جا میشن
            html.append("<table bordered compact>" + content.replace("{a}", align) + "</table>")
        else:
            html.append(content)
    return "".join(html)
