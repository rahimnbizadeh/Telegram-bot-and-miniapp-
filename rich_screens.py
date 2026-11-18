"""
نسخه‌ی «پیام غنی» صفحه‌های اطلاعاتی و اعلان‌های بات؛ هر تابع فقط HTML غنی می‌سازه. ارسال/ویرایش و
برگشت به پیام کلاسیک (وقتی پیام غنی خاموشه یا تلگرام رد کنه) تو user.py (_reply_or_edit / _try_rich)
و rich_messages.send_rich_or_classic انجام میشه.

اصول طراحی:
- ستون برچسب‌ها «سلول عنوان» (<th>) و با ایموجی پریمیوم مخصوص خودش؛ ستون مقدارها <td>. تلگرام ستون
  عنوان رو با رنگ جدا نشون میده، پس جدول سیاهِ یکدست نیست.
- مقدارهای مهم (موجودی، زمان مهلت و ...) با <mark> هایلایت میشن.
- هشدار و توضیح تو کادر نقل‌قول (<blockquote>)؛ مقدارهای طولانی (کانفیگ) تو بخش جمع‌شونده تا پیام جمع‌وجور باشه.
- راست‌به‌چپ: فارسی با is_rtl و سلول‌های راست‌چین؛ انگلیسی/روسی چپ‌به‌راست.
"""
import re

import jalali
from config import PRICE_PER_GB_TOMAN, RESELLER_PRICE_PER_GB_TOMAN
import premium_emoji as pe
import rich_messages as rm
from i18n import t
from rich_messages import Raw, esc, table, paragraph, document, mark, callout


def _lbl(icon, text) -> Raw:
    """برچسب ردیف: ایموجی پریمیوم (تگ آماده) + متن (escape میشه).
    اگه ایموجی داده نشده باشه، یکی مناسبِ خودِ برچسب از بانک انتخاب میشه تا هیچ ردیفی بدون ایموجی نمونه."""
    icon = icon or pe.label_emoji(str(text))
    return Raw(f"{icon} {esc(text)}")


def _toman(lang, n) -> str:
    return t("panel_toman", lang, n=f"{n:,}")


def _h(icon, text, level=3) -> Raw:
    """تیتر با ایموجی پریمیوم اول.
    سطح‌های یکدست تو کل بات: عنوان هر صفحه = h3 (مثل مبدل خودکار rich_convert)، عنوان بخش‌های داخلی = h4."""
    return Raw(f"<h{level}>{icon} {esc(text)}</h{level}>" if icon else f"<h{level}>{esc(text)}</h{level}>")


def _tbl(rows, rtl=True, **kw) -> Raw:
    kw.setdefault("compact", True)   # همه‌ی جدول‌های برچسب|مقدار فشرده‌ان تا مقدارها (تاریخ و ...) تو ستونشون جا بشن
    return table(rows, rtl=rtl, row_headers=True, **kw)


# ======================= صفحه‌های اصلی =======================
def main_menu(lang, first_name, brand, balance, services_count, user_id, last_visit_text=None, back=False) -> str:
    """پنل منوی اصلی: خوش‌آمد + جدول موجودی / سرویس فعال / شناسه / آخرین ورود + راهنمای منو"""
    title = t("back_to_menu", lang) if back else t("welcome_short", lang, name=first_name or "", brand=brand)
    icon = pe.CHECK2 if back else pe.WAVE
    rtl = rm.is_rtl(lang)
    rows = [
        [_lbl(pe.WALLET, t("panel_balance_short", lang)), mark(_toman(lang, balance))],
        [_lbl(pe.MY_SERVICES, t("panel_active_services", lang)), str(services_count)],
        [_lbl(pe.ACCOUNT, t("panel_user_id", lang)), str(user_id)],
    ]
    if last_visit_text:
        rows.append([_lbl(pe.CLOCK, t("panel_last_visit", lang)), last_visit_text])
    return document(
        paragraph(Raw(f"{icon} "), title),
        paragraph(Raw(f"{pe.STAR} "), t("panel_intro", lang)),
        _tbl(rows, rtl, compact=True),   # compact: حاشیه‌ی داخلی سلول‌ها نصف میشه و تاریخ+ساعت تو ستون مقدار جا میشه
        paragraph(Raw(f"{pe.DOWN_ARROW} "), t("panel_choose", lang)),
    )


def wallet(lang, balance) -> str:
    hint_lines = [ln for ln in t("wallet_topup_hint", lang, n1=pe.NUM[1], n2=pe.NUM[2]).split("\n") if ln.strip()]
    return document(
        _h(pe.WALLET, t("wallet_title", lang)),
        paragraph(Raw(f"{pe.CHARGE} "), t("wallet_intro", lang)),
        _tbl([[_lbl(pe.WALLET, t("panel_balance_short", lang)), mark(_toman(lang, balance))]], rm.is_rtl(lang)),
        *[Raw(f"<p>{ln}</p>") for ln in hint_lines],   # راهنما ایموجی پریمیوم (تگ آماده) داره
    )


def account(lang, user, subs_count, balance, joined_str, tier_text, pointer_text) -> str:
    rows = [
        [_lbl(pe.ACCOUNT, t("account_name", lang)), user.first_name or "-"],
        [_lbl(None, t("account_username", lang)), "@" + (user.username or t("account_none", lang))],
        [_lbl(None, t("account_id", lang)), str(user.id)],
        [_lbl(pe.MY_SERVICES, t("account_services_count", lang)), str(subs_count)],
        [_lbl(pe.WALLET, t("account_balance", lang)), mark(f"{balance:,}")],
        [_lbl(pe.CALENDAR, t("account_joined_at", lang)), joined_str],
        [Raw(t("account_loyalty_title", lang, icon=pe.CUP).strip()), Raw(tier_text)],
    ]
    return document(_h(pe.ACCOUNT, t("account_title", lang)), _tbl(rows, rm.is_rtl(lang)), Raw(f"<p>{pointer_text}</p>"))


def referral(lang, referrals_count, purchases_count, total_amount, link, signup_bonus, purchase_bonus) -> str:
    rtl = rm.is_rtl(lang)
    return document(
        _h(pe.REFERRAL, t("referral_title", lang)),
        paragraph(t("referral_intro", lang)),
        # ردیف‌های تک‌سلولی باید <td> باشن (نه <th>)؛ تلگرام عرض سلولِ <th> رو حدود ۵۵٪ جدول می‌گیره و بقیه خالی می‌مونه
        table(
            [
                [_lbl(pe.CHARGE, t("referral_signup_bonus", lang, amount=signup_bonus))],
                [_lbl(pe.PRICE, t("referral_purchase_bonus", lang, amount=purchase_bonus))],
            ],
            rtl=rtl, compact=True,
        ),
        paragraph(t("referral_stats_title", lang)),
        _tbl(
            [
                [_lbl(pe.TWO_PEOPLE, t("referral_count", lang)), mark(str(referrals_count))],
                [_lbl(pe.CART, t("referral_purchases_count", lang)), str(purchases_count)],
                [_lbl(pe.PRICE, t("referral_total_amount", lang)), mark(f"{total_amount:,}")],
            ],
            rtl,
        ),
        paragraph(Raw(f"{pe.LINK} "), t("referral_link_label", lang)),
        Raw(f"<p><code>{esc(link)}</code></p>"),
        callout(t("referral_cta", lang)),
    )


def service_detail(plan_title, status_rows, config_link, sub_link) -> str:
    """
    جزئیات سرویس (فارسی). status_rows = [(تگ ایموجی، برچسب، مقدار), ...] (مقدار Raw/mark هم میشه).
    لینک سابسکریپشن همیشه پیداست؛ کانفیگ تو بخش جمع‌شونده تا پیام جمع‌وجور بمونه.
    """
    parts = [
        _h(pe.MY_SERVICES, plan_title),
        paragraph(Raw(f"{pe.CONNECTION} "), "مشخصات و وضعیت این سرویس رو پایین می‌بینی؛ برای اتصال از لینک سابسکریپشن یا کانفیگ استفاده کن و برای تمدید و مدیریت سرویس از دکمه‌های زیر پیام کمک بگیر."),
        _tbl([[_lbl(ic, lbl), val] for ic, lbl, val in status_rows]),
        paragraph(Raw(f"{pe.LINK} "), "لینک سابسکریپشن (با یه لمس کپی میشه):"),
        Raw(f"<p><code>{esc(sub_link)}</code></p>"),
    ]
    if config_link:
        parts.append(rm.details("کانفیگ اتصال", Raw(f"<p><code>{esc(config_link)}</code></p>")))
    else:
        parts.append(callout("کانفیگ اتصال فعلاً در دسترس نیست؛ از دکمه‌ی «دریافت کانفیگ‌ها» امتحان کن."))
    return document(*parts)


def weekly_summary(lang, services, footer=None) -> str:
    """
    خلاصه‌ی هفتگی: برای هر سرویس یه جدول کوچک. services = لیست دیکشنری:
      name, week_gb (None=نامشخص), remaining_gb (None=نامحدود), remaining_days (None=بدون انقضا),
      notes (لیست جمله‌ها؛ Raw = تگ ایموجی/HTML آماده، str = escape میشه)
    """
    out = [_h(pe.MY_SERVICES, "خلاصه‌ی هفتگی سرویس‌هات"), paragraph(Raw(f"{pe.REMAINING} "), t("weekly_intro", lang))]
    for s in services:
        rows = []
        if s.get("week_gb") is not None:
            rows.append(["مصرف ۷ روز اخیر", f"{s['week_gb']:.1f} گیگ"])
        if s.get("remaining_gb") is not None:
            rows.append(["حجم باقی‌مانده", mark(f"{s['remaining_gb']:g} گیگ")])
        if s.get("remaining_days") is not None:
            rows.append(["زمان باقی‌مانده", mark(f"{s['remaining_days']} روز")])
        out.append(_h(pe.CONNECTION, s["name"], 4))
        if rows:
            out.append(_tbl([[_lbl(None, a), b] for a, b in rows], compact=True))
        notes = s.get("notes", [])
        if notes:
            out.append(callout(*[x for n in notes for x in (n, Raw(" "))]))
    if footer:
        out.append(paragraph(footer))
    return document(*out)


# ======================= اعلان‌های چرخه‌ی سرویس =======================
def service_ended(plan_title, reason, grace_text) -> str:
    what = "حجم سرویس تموم شد" if reason == "data" else "مدت سرویس به پایان رسید"
    return document(
        _h(pe.REJECT, what),
        _tbl([
            [_lbl(pe.MY_SERVICES, "سرویس"), plan_title],
            [_lbl(None, "وضعیت"), "غیرفعال"],
            [_lbl(pe.HOURGLASS2, "مهلت تمدید"), mark(grace_text)],
        ]),
        callout("با تمدید، همین لینک و کانفیگ قبلی دوباره فعال میشه و لازم نیست چیزی رو دوباره تنظیم کنی. "
                "بعد از این مهلت، سرویس برای همیشه حذف میشه."),
    )


def final_warning(plan_title, left_text) -> str:
    return document(
        _h(pe.HOURGLASS2, "هشدار نهایی"),
        _tbl([
            [_lbl(pe.MY_SERVICES, "سرویس"), plan_title],
            [_lbl(pe.CLOCK, "مونده تا حذف"), mark(left_text)],
        ]),
        callout("هنوز می‌تونی با تمدیدش (همون لینک قبلی) نگهش داری."),
    )


def service_deleted(plan_title, code=None, percent=None, hours=None) -> str:
    parts = [
        _h(pe.REJECT, "سرویس حذف شد"),
        _tbl([[_lbl(pe.MY_SERVICES, "سرویس"), plan_title], [_lbl(None, "دلیل"), "تمدید نشد"]]),
        paragraph("لطفا یک اشتراک جدید تهیه کنید."),
    ]
    if code:
        parts += [
            paragraph(Raw("🎁 "), f"یه هدیه برای برگشتنت: {percent}٪ تخفیف مخصوص خودت روی خرید سرویس جدید"),
            rm.aside(Raw(f"<code>{esc(code)}</code>")),
            _tbl([[_lbl(None, "تخفیف"), mark(f"{percent}٪")], [_lbl(pe.CLOCK, "اعتبار"), f"{hours} ساعت"],
                  [_lbl(None, "نوع"), "یک‌بارمصرف"]], compact=True),
            callout("موقع خرید سرویس جدید همین کد رو وارد کن."),
        ]
    return document(*parts)


def expiry_reminder(plan_title, days_left) -> str:
    return document(
        _h(pe.HOURGLASS2, "یادآوری تمدید اشتراک"),
        _tbl([
            [_lbl(pe.MY_SERVICES, "سرویس"), plan_title],
            [_lbl(pe.CLOCK, "اعتبار باقی‌مانده"), mark(f"{days_left} روز")],
        ]),
        callout("برای ادامه‌ی سرویس، هم‌اکنون نسبت به تمدید اشتراک اقدام کنید."),
    )


# ======================= آموزش اتصال =======================
_RLM = "\u200f"   # علامت راست‌به‌چپ؛ اولِ هر خط فارسی میذاریمش تا اگه خط با کلمه‌ی انگلیسی شروع شد، چپ‌چین/به‌هم‌ریخته نشه
_LTR_RUN = re.compile("\u2066([^\u2069]*)\u2069")   # عبارت‌های انگلیسی ایزوله‌شده با config._L


def guide_html(text) -> Raw:
    """متن راهنما: escape میشه و عبارت‌های انگلیسیِ ایزوله (منوها، اسم فایل‌ها و ...) پررنگ میشن"""
    return Raw(_LTR_RUN.sub(lambda m: f"<b>\u2066{m.group(1)}\u2069</b>", esc(text)))


def platform_guide(guide) -> str:
    """
    راهنمای اتصال یک پلتفرم، کوتاه و تمیز: مشخصات اپ تو جدول، «کدوم فایل» تو جدول، مراحل کوتاه،
    و نکته‌ها/مشکل‌های رایج تو بخش‌های جمع‌شونده. لینک دانلود و دکمه‌ها از reply_markup میان.
    """
    parts = [
        _h(pe.APPS, f"راهنمای اتصال — {guide['label']}", 3),
        _tbl(
            [
                [_lbl(pe.LINK, "اپ پیشنهادی"), Raw(f"<b>{esc(guide['app_name'])}</b>")],
            ]
            + ([[_lbl(None, "سازگاری"), guide["req"]]] if guide.get("req") else [])
            + [[_lbl(None, "هزینه"), guide["note"]]],
            True,
        ),
    ]

    files = guide.get("files") or []
    if files:
        parts.append(_h(None, "📦 کدوم فایل رو بگیرم؟", 4))
        parts.append(table([[cond, Raw(f"<code>{esc(name)}</code>")] for cond, name in files], rtl=True, compact=True))
    if guide.get("files_note"):
        parts.append(Raw(f"<p>{_RLM}{guide_html(guide['files_note'])}</p>"))

    parts.append(_h(None, "🧭 مراحل", 4))
    for i, step in enumerate(guide["steps"], start=1):
        parts.append(Raw(f"<p>{pe.NUM.get(i, str(i) + '.')} {_RLM}{guide_html(step)}</p>"))

    faq = guide.get("faq") or []
    if faq:
        parts.append(_h(None, "💡 سوال‌های رایج", 4))
        for title, text, code in faq:
            body = f"<p>{_RLM}{guide_html(text)}</p>"
            if code:
                body += f"<pre>{esc(code)}</pre>"
            parts.append(rm.details(title, Raw(body)))

    parts.append(rm.footer("مشکلی بود؟ از «پشتیبانی» توی منوی اصلی بپرس."))
    return document(*parts)


# ======================= پشتیبانی و تیکت =======================
_T_STATUS = {
    "open": ("🟡", "در انتظار پاسخ"),
    "answered": ("🟢", "پاسخ داده شد"),
    "closed": ("⚪️", "بسته شده"),
}


def _auto_close_note(auto_days) -> str:
    return (
        f"تیکتی که جواب بگیره و {auto_days:g} روز پیام جدیدی نداشته باشه، خودکار بسته میشه."
        if auto_days and auto_days > 0 else ""
    )


def _jdate(ts) -> str:
    try:
        return jalali.format_jalali_datetime(ts) if ts else "—"
    except Exception:
        return "—"


def support_menu(answered: int, auto_days) -> str:
    """منوی پشتیبانی: هر راه ارتباطی با یک جمله توضیح + چک‌لیست قبل از ثبت تیکت"""
    rows = [
        [_lbl(pe.QUESTION, "سوالات متداول"), "جواب سریع مشکلات رایج؛ اول اینجا رو ببین"],
        [_lbl(pe.CHAT, "ثبت تیکت"), "سوالت رو برای پشتیبانی بفرست؛ جواب همین‌جا برات میاد"],
        [_lbl(pe.FOLDERS, "تیکت‌های من"), "پیگیری گفتگوها و وضعیت هر تیکت"],
        [_lbl(pe.SUPPORT, "پشتیبانی تلگرام"), "گفتگوی مستقیم با پشتیبان"],
    ]
    parts = [
        _h(pe.SUPPORT, "پشتیبانی", 3),
        paragraph(Raw(f"{pe.STAR} "), "چطور کمکت کنیم؟ یکی از گزینه‌های زیر رو انتخاب کن:"),
        _tbl(rows, True),
    ]
    if answered:
        parts.append(callout(f"🟢 {answered} تیکتت جواب گرفته؛ از «تیکت‌های من» ببینش."))
    parts.append(
        rm.details(
            "قبل از ثبت تیکت، اینا رو چک کن",
            rm.bullet_list([
                "حجم و زمان سرویس رو از «سرویس‌های من» ببین.",
                "ساعت و تاریخ دستگاهت رو روی حالت خودکار بذار.",
                "اشتراک رو توی اپ آپدیت کن و یه سرور دیگه از لیست امتحان کن.",
                "توی تیکتت اسم سرویس، اپی که استفاده می‌کنی و متن خطا (اگه هست) رو بنویس.",
            ]),
        )
    )
    note = _auto_close_note(auto_days)
    if note:
        parts.append(rm.footer(note))
    return document(*parts)


def faq(items) -> str:
    """سوالات متداول: هر سوال یک بخش جمع‌شونده"""
    parts = [
        _h(pe.QUESTION, "سوالات متداول", 3),
        paragraph(Raw(f"{pe.STAR} "), "روی هر سوال بزن تا جوابش باز بشه:"),
    ]
    for item in items:
        parts.append(rm.details(item["q"], paragraph(item["a"])))
    parts.append(rm.footer("جوابت رو پیدا نکردی؟ یه تیکت ثبت کن."))
    return document(*parts)


def ticket_list(tickets, auto_days) -> str:
    counts = {"open": 0, "answered": 0, "closed": 0}
    for tk in tickets:
        counts[tk["status"]] = counts.get(tk["status"], 0) + 1
    rows = [
        [Raw(f"{_T_STATUS[k][0]} {esc(_T_STATUS[k][1])}"), str(counts[k])]
        for k in ("open", "answered", "closed") if counts.get(k)
    ]
    parts = [
        _h(pe.FOLDERS, "تیکت‌های من", 3),
        _tbl(rows, True),
        paragraph(Raw(f"{pe.STAR} "), "برای دیدن گفتگو و ارسال پیام جدید، روی هر تیکت بزن:"),
    ]
    note = _auto_close_note(auto_days)
    if note:
        parts.append(rm.footer(note))
    return document(*parts)


def ticket_detail(ticket, messages, auto_days) -> str:
    emoji, label = _T_STATUS.get(ticket["status"], _T_STATUS["closed"])
    rows = [
        [_lbl(pe.FOLDERS, "تیکت"), f"#{ticket['ticket_id']}"],
        [_lbl(pe.CLOCK, "وضعیت"), Raw(f"{emoji} {esc(label)}")],
        [_lbl(pe.CALENDAR, "ثبت"), _jdate(ticket["created_at"])],
        [_lbl(pe.CLOCK, "آخرین بروزرسانی"), _jdate(ticket["updated_at"])],
    ]
    parts = [_h(pe.SUPPORT, f"تیکت #{ticket['ticket_id']}", 3), _tbl(rows, True)]

    shown = messages[-8:]
    if len(messages) > len(shown):
        parts.append(callout(f"{len(messages) - len(shown)} پیام قدیمی‌تر نمایش داده نمیشه."))
    for m in shown:
        who = "👤 تو" if m["sender"] == "user" else "🎧 پشتیبانی"
        parts.append(rm.divider())
        parts.append(Raw(f"<p><b>{who}</b> · {esc(_jdate(m['created_at']))}</p>"))
        body = (m["text"] or "")[:900] + ("…" if len(m["text"] or "") > 900 else "")
        for line in [ln for ln in body.split("\n") if ln.strip()] or ["—"]:
            parts.append(paragraph(line))

    if ticket["status"] == "closed":
        parts.append(callout("این تیکت بسته شده. اگه هنوز مشکلی داری، یه تیکت جدید ثبت کن."))
    elif ticket["status"] == "answered":
        note = _auto_close_note(auto_days)
        if note:
            parts.append(rm.footer(note))
    return document(*parts)


# ======================= نمایندگی =======================
def reseller_hub(is_reseller: bool, eligible: bool, balance: int, threshold: int) -> str:
    """هاب نمایندگی: قیمت‌ها و موجودی تو جدول، مراحل خرید و توضیح شرط تو بخش‌های جمع‌شونده"""
    parts = [_h(pe.RESELLER, "نمایندگی فروش", 3)]
    if is_reseller:
        parts.append(paragraph(Raw(f"{pe.CONFIRM} "), "تو نماینده‌ی تاییدشده‌ای و سرویس‌ها رو با قیمت عمده می‌خری."))
        parts.append(_tbl([
            [_lbl(pe.RESELLER, "قیمت نمایندگی هر گیگ"), mark(f"{RESELLER_PRICE_PER_GB_TOMAN:,} تومان")],
            [_lbl(pe.PRICE, "قیمت عادی هر گیگ"), f"{PRICE_PER_GB_TOMAN:,} تومان"],
            [_lbl(pe.WALLET, "موجودی کیف پول"), mark(f"{balance:,} تومان")],
        ], True))
        parts.append(rm.details(
            "چطور خرید کنم؟",
            rm.bullet_list([
                "لوکیشن، مدت و حجم رو انتخاب کن.",
                "برای سرویس اسم دلخواه بذار یا رندوم باشه.",
                "از موجودی کیف پولت بخر؛ اگه موجودی کم بود، همون مقدار کمبود رو با درگاه پرداخت شارژ کن و ادامه بده.",
                "لینک اشتراک رو به مشتریت بده؛ سرویس با همون اسمی که انتخاب کردی نمایش داده میشه.",
            ]),
        ))
    else:
        parts.append(paragraph(Raw(f"{pe.STAR} "), "با نمایندگی، سرویس‌ها رو با قیمت عمده می‌خری و به مشتری‌های خودت می‌فروشی."))
        status = Raw(f"{pe.CONFIRM} واجد شرایطی") if eligible else f"{max(0, threshold - balance):,} تومان دیگه لازمه"
        parts.append(_tbl([
            [_lbl(pe.CHARGE, "شرط درخواست"), f"موجودی کیف پول حداقل {threshold:,} تومان"],
            [_lbl(pe.WALLET, "موجودی فعلی"), mark(f"{balance:,} تومان")],
            [_lbl(None, "وضعیت"), status],
        ], True))
        parts.append(callout("موجودیِ همین لحظه حساب میشه، نه مجموع شارژها و تراکنش‌های قبلی."))
        parts.append(rm.details(
            "نماینده بشم چی می‌گیرم؟",
            rm.bullet_list([
                f"قیمت عمده: هر گیگ {RESELLER_PRICE_PER_GB_TOMAN:,} تومان (قیمت عادی: {PRICE_PER_GB_TOMAN:,} تومان).",
                "انتخاب اسم دلخواه برای هر سرویس.",
                "اگه موجودی کم باشه، با درگاه پرداخت مبلغ کمبود رو شارژ می‌کنی و می‌خری.",
            ]),
        ))
    return document(*parts)


# ======================= سربرگ یکدست =======================
def hdr(icon, title: str, facts=(), hint: str = None) -> str:
    """
    سربرگ یکدستِ همه‌ی صفحه‌های بات (متن کلاسیک). ساختار ثابت:
      خط اول: تیتر کوتاه با ایموجی  |  بعدش خط‌های «برچسب: مقدار» (مشخصات)  |  آخرش یه خط راهنما (بدون «:»)
    وقتی پیام غنی روشنه، مبدل خودکار (rich_convert) همین ساختار رو به «تیتر + جدول مشخصات + یادداشت» تبدیل
    می‌کنه؛ وقتی خاموشه همین متن راست‌چین به‌صورت کلاسیک نمایش داده میشه. هر صفحه‌ای که این تابع رو
    استفاده کنه، تو هر دو حالت ظاهر یکسان داره.
    facts = [(label, value)] یا [(ایموجی، label, value)]؛ hint نباید «:» داشته باشه (جدول حساب نشه).
    """
    lines = [f"{icon} {_RLM}{title}"]
    for f in facts:
        ic, label, value = f if len(f) == 3 else (None, f[0], f[1])
        lines.append((f"{ic} " if ic else "") + f"{_RLM}{label}: {value}")
    if hint:
        lines.append(f"\n{_RLM}{hint}")
    return "\n".join(lines)


_TX_LABELS = {
    "topup": "شارژ کیف پول",
    "purchase": "خرید/تمدید سرویس",
    "renewal": "تمدید خودکار",
    "referral_bonus": "پاداش زیرمجموعه‌گیری",
    "referral_signup": "پاداش عضو جدید",
    "transfer_in": "دریافت از کاربر دیگر",
    "transfer_out": "انتقال به کاربر دیگر",
    "reseller_purchase": "خرید نمایندگی",
    "loyalty_bonus": "پاداش باشگاه مشتریان",
    "refund": "برگشت مبلغ",
}


def tx_label(tx_type: str) -> str:
    return _TX_LABELS.get(tx_type, tx_type)


def wallet_transactions(txs, balance: int) -> str:
    """تراکنش‌های اخیر کیف پول: سربرگ + جدول (تاریخ | شرح | مبلغ)؛ مبلغ‌های واریزی هایلایت"""
    rows = []
    for tx in txs:
        amount = tx["amount"]
        shown = f"{'+' if amount >= 0 else '-'}{abs(amount):,}"
        rows.append([
            _jdate(tx["created_at"]),
            tx_label(tx["tx_type"]),
            mark(shown) if amount >= 0 else shown,
        ])
    parts = [
        _h(pe.WALLET, "تراکنش‌های کیف پول", 3),
        _tbl([[_lbl(pe.WALLET, "موجودی فعلی"), mark(f"{balance:,} تومان")]], True),
        table(rows, header=["تاریخ", "شرح", "مبلغ (تومان)"], rtl=True, compact=True),
        rm.footer("فقط ۱۵ تراکنش آخر نمایش داده میشه."),
    ]
    return document(*parts)
