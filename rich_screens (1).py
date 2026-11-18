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
import premium_emoji as pe
import rich_messages as rm
from i18n import t
from rich_messages import Raw, esc, table, paragraph, document, mark, callout


def _lbl(icon, text) -> Raw:
    """برچسب ردیف: ایموجی پریمیوم (تگ آماده) + متن (escape میشه)"""
    return Raw(f"{icon} {esc(text)}" if icon else esc(text))


def _toman(lang, n) -> str:
    return t("panel_toman", lang, n=f"{n:,}")


def _h(icon, text, level=3) -> Raw:
    """تیتر با ایموجی پریمیوم اول"""
    return Raw(f"<h{level}>{icon} {esc(text)}</h{level}>" if icon else f"<h{level}>{esc(text)}</h{level}>")


def _tbl(rows, rtl=True, **kw) -> Raw:
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
        paragraph(t("panel_intro", lang)),
        _tbl(rows, rtl),
        paragraph(Raw(f"{pe.DOWN_ARROW} "), t("panel_choose", lang)),
    )


def wallet(lang, balance) -> str:
    hint_lines = [ln for ln in t("wallet_topup_hint", lang, n1=pe.NUM[1], n2=pe.NUM[2]).split("\n") if ln.strip()]
    return document(
        _h(pe.WALLET, t("wallet_title", lang)),
        paragraph(t("wallet_intro", lang)),
        _tbl([[_lbl(pe.PRICE, t("panel_balance_short", lang)), mark(_toman(lang, balance))]], rm.is_rtl(lang)),
        *[Raw(f"<p>{ln}</p>") for ln in hint_lines],   # راهنما ایموجی پریمیوم (تگ آماده) داره
    )


def account(lang, user, subs_count, balance, joined_str, tier_text, pointer_text) -> str:
    rows = [
        [_lbl(pe.ACCOUNT, t("account_name", lang)), user.first_name or "-"],
        [_lbl(None, t("account_username", lang)), "@" + (user.username or t("account_none", lang))],
        [_lbl(None, t("account_id", lang)), str(user.id)],
        [_lbl(pe.MY_SERVICES, t("account_services_count", lang)), str(subs_count)],
        [_lbl(pe.PRICE, t("account_balance", lang)), mark(f"{balance:,}")],
        [_lbl(pe.CALENDAR, t("account_joined_at", lang)), joined_str],
        [Raw(t("account_loyalty_title", lang, icon=pe.CUP).strip()), Raw(tier_text)],
    ]
    return document(_h(pe.ACCOUNT, t("account_title", lang)), _tbl(rows, rm.is_rtl(lang)), Raw(f"<p>{pointer_text}</p>"))


def referral(lang, referrals_count, purchases_count, total_amount, link, signup_bonus, purchase_bonus) -> str:
    rtl = rm.is_rtl(lang)
    return document(
        _h(pe.REFERRAL, t("referral_title", lang)),
        paragraph(t("referral_intro", lang)),
        _tbl(
            [
                [_lbl(pe.CHARGE, t("referral_signup_bonus", lang, amount=signup_bonus))],
                [_lbl(pe.PRICE, t("referral_purchase_bonus", lang, amount=purchase_bonus))],
            ],
            rtl, compact=True,
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
        paragraph("مشخصات و وضعیت این سرویس رو پایین می‌بینی؛ برای اتصال از لینک سابسکریپشن یا کانفیگ استفاده کن و برای تمدید و مدیریت سرویس از دکمه‌های زیر پیام کمک بگیر."),
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
    out = [_h(pe.MY_SERVICES, "خلاصه‌ی هفتگی سرویس‌هات"), paragraph(t("weekly_intro", lang))]
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
