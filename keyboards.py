from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    CopyTextButton,
    WebAppInfo,
)

from config import (
    PLANS,
    BOT_USERNAME,
    SUPPORT_LINK,
    PANEL_TYPE,
    get_plan,
    get_plans_for_duration,
    DURATION_MONTHS,
    DURATION_LABELS,
    PREMIUM_LOCATION_NAME,
    REQUIRED_CHANNEL_LINK,
    CRYPTO_PAYMENT_ENABLED,
    CRYPTO_CURRENCIES,
    CRYPTO_CURRENCY_LABELS,
    CRYPTO_CURRENCY_STYLES,
    AUTOSMS_ENABLED,
    MANUAL_CARD_PAYMENT_ENABLED,
    TONPAYS_ENABLED,
    WINAPAY_ENABLED,
    MINIAPP_URL,
    MAIN_MENU_MINIAPP_BUTTON,
    LOYALTY_CLUB_MENU_BUTTON_ENABLED,
)

CRYPTO_CURRENCY_ICON = {
    "TONCOIN": "GEM",
    "USDT": "VERIFIED",
    "TRX": "LIGHTNING",
}
import premium_emoji as pe
import theme
from i18n import t, DEFAULT_LANG, SUPPORTED_LANGS, LANG_LABELS

# آیکون مخصوص هر رده‌ی پلن: الماس پریمیوم اختصاصیِ هر مدت (۱/۲/۳ ماهه)
def get_plan_icon(plan) -> str:
    if plan.get("is_unlimited"):
        return pe.RAW["CUP"]  # جام/تاج برای پلن ویژه، به‌جای بستنی (VIP) که تناسب بصری نداشت
    months = plan.get("duration_months")
    return pe.PLAN_RAW.get(f"GEM_{months}") or pe.RAW.get({6: "CUP"}.get(months, ""))


# رنگ دکمه‌ی مدت/پلن از تم فعال میاد (theme.py): تم پیش‌فرض آبیِ یکدسته؛ تم classic همون «چراغ‌راهنمای» قبلی
def get_duration_style(months) -> str:
    return theme.duration_style(months)


def get_plan_style(plan) -> str:
    """رنگ دکمه‌ی پلن: پلن نامحدود (ویژه) تو تم classic سبز بود؛ بقیه از رنگ مدت"""
    if plan.get("is_unlimited"):
        return theme.PICK
    return get_duration_style(plan.get("duration_months"))


def _plan_button_label(plan, with_duration: bool = False) -> str:
    """متن فشرده‌ی دکمه‌ی یک پلن: «حجم · قیمت». مدت تو متن همون صفحه هست و تکرارش دکمه رو دوخطی می‌کرد.
    فقط لیست‌های «همه‌ی پلن‌ها» (با مدت‌های مختلف) with_duration=True می‌گیرن: «حجم | مدت | قیمت».
    (ایموجی فقط از طریق icon_custom_emoji_id پرمیوم نمایش داده میشه)"""
    if with_duration:
        return " | ".join([f"{plan['gb']} گیگ", DURATION_LABELS[plan["duration_months"]], f"{plan['price']:,} تومان"])
    return f"{plan['gb']} گیگ · {plan['price']:,}"


def _pair_rows(buttons: list) -> list:
    """
    دکمه‌ها رو دوتا‌دوتا کنار هم می‌چینه (دو ستون) و ترتیب فارسی (راست‌به‌چپ) رو رعایت می‌کنه:
    کوچک‌ترین حجم سمت راستِ ردیفِ اول، بعدی سمت چپش، و همین‌طور ردیف‌های بعدی.
    (تو کیبورد inline تلگرام اولین دکمه‌ی هر ردیف سمت چپه، برای همین هر جفت برعکس چیده میشه.)
    اگه تعداد فرد بود آخری تنها و تمام‌عرض میمونه.
    """
    return [buttons[i:i + 2][::-1] for i in range(0, len(buttons), 2)]


def _duration_button_label(months: int) -> str:
    """متن دکمه‌ی مدت: «۱ ماهه | از ۴۰,۰۰۰ تومان» (ارزون‌ترین پلنِ همون مدت)"""
    plans = [p for p in get_plans_for_duration(months) if not p.get("is_unlimited")]
    if not plans:
        return DURATION_LABELS[months]
    return f"{DURATION_LABELS[months]} | از {min(p['price'] for p in plans):,} تومان"


def join_channel_keyboard(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(t("join_channel_button", lang), url=REQUIRED_CHANNEL_LINK, icon_custom_emoji_id=pe.RAW["LINK"], style=theme.NAV)],
        [
            InlineKeyboardButton(
                t("joined_check_button", lang),
                callback_data="checkjoin",
                icon_custom_emoji_id=pe.RAW["CONFIRM"],
                style=theme.CTA,
            )
        ],
    ]
    return InlineKeyboardMarkup(rows)


def language_keyboard() -> InlineKeyboardMarkup:
    """صفحه‌ی اول - انتخاب زبان (فارسی / انگلیسی / روسی)"""
    rows = [[InlineKeyboardButton(LANG_LABELS[code], callback_data=f"setlang:{code}")] for code in SUPPORTED_LANGS]
    return InlineKeyboardMarkup(rows)


def main_menu_keyboard(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                t("menu_buy", lang),
                callback_data="menu:buy",
                icon_custom_emoji_id=pe.RAW["MENU_BUY"],
                style=theme.CTA,
            ),
            InlineKeyboardButton(
                t("menu_myservices", lang),
                callback_data="menu:myservices",
                icon_custom_emoji_id=pe.RAW["MENU_SERVICES"],
                style=theme.PICK,
            ),
        ],
        [
            InlineKeyboardButton(
                t("menu_trial", lang),
                callback_data="menu:trial",
                icon_custom_emoji_id=pe.RAW["MENU_TRIAL"],
                style="danger",
            )
        ],
        [
            InlineKeyboardButton(
                t("menu_wallet", lang),
                callback_data="menu:wallet",
                icon_custom_emoji_id=pe.RAW["MENU_WALLET"],
                style=theme.NAV,
            ),
            InlineKeyboardButton(
                t("menu_account", lang),
                callback_data="menu:account",
                icon_custom_emoji_id=pe.RAW["MENU_ACCOUNT"],
                style=theme.NAV,
            ),
        ],
        [
            InlineKeyboardButton(
                t("menu_apps", lang),
                callback_data="menu:apps",
                icon_custom_emoji_id=pe.RAW["MENU_APPS"],
                style=theme.NAV,
            )
        ],
        [
            InlineKeyboardButton(
                t("menu_referral", lang),
                callback_data="menu:referral",
                icon_custom_emoji_id=pe.RAW["MENU_REFERRAL"],
            ),
            InlineKeyboardButton(
                t("menu_support", lang),
                callback_data="menu:support",
                icon_custom_emoji_id=pe.RAW["MENU_SUPPORT"],
            ),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def main_reply_keyboard(lang: str = DEFAULT_LANG) -> ReplyKeyboardMarkup:
    """
    منوی ثابت پایین صفحه - از Bot API 9.4 به بعد، دکمه‌های ReplyKeyboard هم
    مثل دکمه‌های inline از style (رنگ) و icon_custom_emoji_id (ایموجی
    پرمیوم) پشتیبانی می‌کنن. دکمه‌ی «ورود به برنامه» عمداً web_app نداره -
    فقط متنش رو می‌فرسته و reply_menu_router (تو user.py) با یه دکمه‌ی
    inline (enter_app_keyboard) جوابش میده، چون طبق مستندات تلگرام
    initData برای Mini App بازشده از دکمه‌ی ReplyKeyboard همیشه خالیه.
    چیدمان (همه آبی). توجه: تو ReplyKeyboard اولین دکمه‌ی هر ردیف سمت چپه، پس ردیف‌های سه‌تایی
    «از راست» اینجوری خونده میشن:
      ردیف ۱: «خرید سرویس» (تمام‌عرض)
      ردیف ۲: «سرویس‌های من» | «آموزش اتصال» | «کیف پول من»
      ردیف ۳: «تست رایگان» (تمام‌عرض)
      ردیف ۴: «پشتیبانی آنی» | «دعوت دوستان» | «حساب کاربری»
      ردیف ۵: «نمایندگی فروش» (تمام‌عرض)
    «ورود به مینی‌اپ» فعلاً خاموشه (MAIN_MENU_MINIAPP_BUTTON)؛ اگه روشن بشه، بالای همه‌ی ردیف‌ها میاد.
    «باشگاه مشتریان» فعلاً از منو مخفیه (LOYALTY_CLUB_MENU_BUTTON_ENABLED) -
    اگه فعال بشه، به‌صورت یه ردیف تمام‌عرض درست بالای «نمایندگی فروش» اضافه میشه.
    نکته: نمایش icon_custom_emoji_id مشروط به این‌ه که بات یوزرنیم اضافه از
    Fragment خریده باشه یا صاحب بات Premium داشته باشه؛ در غیر این صورت
    تلگرام خودش fallback امن (بدون آیکون) رو نشون میده، چیزی خراب نمیشه.
    """
    def btn(text: str, emoji_key: str) -> KeyboardButton:
        return KeyboardButton(text, icon_custom_emoji_id=pe.RAW[emoji_key], style=theme.NAV)

    rows = []
    if MINIAPP_URL and MAIN_MENU_MINIAPP_BUTTON:
        rows.append([btn(t("menu_enter_app", lang), "MENU_ENTER_APP")])
    rows += [
        [btn("خرید سرویس" if lang == "fa" else t("menu_buy", lang), "MENU_BUY")],
        [
            btn("کیف پول من", "MENU_WALLET"),               # چپ
            btn(t("menu_apps", lang), "MENU_APPS"),         # وسط
            btn(t("menu_myservices", lang), "MENU_SERVICES"),  # راست
        ],
        [btn(t("menu_trial", lang), "MENU_TRIAL")],
        [
            btn(t("menu_account", lang), "MENU_ACCOUNT"),   # چپ
            btn(t("menu_referral", lang), "MENU_REFERRAL"),  # وسط
            btn("پشتیبانی آنی", "MENU_SUPPORT"),            # راست
        ],
    ]
    if LOYALTY_CLUB_MENU_BUTTON_ENABLED:
        rows.append([btn(t("menu_loyalty", lang), "CUP")])
    rows.append([btn(t("menu_reseller", lang), "MENU_RESELLER")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)


def trial_location_keyboard() -> InlineKeyboardMarkup:
    """مرحله‌ی اول تست رایگان: انتخاب لوکیشن (فعلاً فقط یکی هست؛ هر لوکیشن جدید فقط یه دکمه‌ی دیگه اینجا می‌خواد)"""
    rows = [
        [
            InlineKeyboardButton(
                PREMIUM_LOCATION_NAME,
                callback_data="triallocation:germany",
                icon_custom_emoji_id=pe.PLAN_RAW["LOCATION"],
                style=theme.PICK,
            )
        ],
        [InlineKeyboardButton("بازگشت", callback_data="menu:back", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")],
    ]
    return InlineKeyboardMarkup(rows)


def trial_used_keyboard(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    """وقتی کاربر قبلاً تست گرفته: فقط دکمه‌ی خرید سرویس (و بازگشت) زیر همون پیام"""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t("menu_buy", lang),
                    callback_data="menu:buy",
                    icon_custom_emoji_id=pe.RAW["MENU_BUY"],
                    style=theme.CTA,
                )
            ],
            [InlineKeyboardButton("بازگشت", callback_data="menu:back", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")],
        ]
    )


def duration_keyboard() -> InlineKeyboardMarkup:
    """مرحله‌ی دوم خرید (بعد از انتخاب لوکیشن): انتخاب مدت اشتراک.
    ۱ ماهه آبی، ۲ ماهه سبز، ۳ ماهه قرمز؛ هر کدوم ایموجی پریمیوم عددِ خودش رو داره."""
    rows = []
    for months in DURATION_MONTHS:
        rows.append(
            [
                InlineKeyboardButton(
                    _duration_button_label(months),
                    callback_data=f"plandur:{months}",
                    icon_custom_emoji_id=pe.PLAN_RAW.get(f"DUR_{months}") or pe.RAW["CALENDAR"],
                    style=get_duration_style(months),
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton("بازگشت", callback_data="menu:buy", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")]
    )
    return InlineKeyboardMarkup(rows)


def location_keyboard() -> InlineKeyboardMarkup:
    """مرحله‌ی اول خرید: فقط یک لوکیشن فعلاً هست («پریمیوم آلمان»)، پس یک دکمه نشون میدیم
    و بعدش مرحله‌ی انتخاب مدت (۱/۲/۳ ماهه) میاد."""
    rows = [
        [
            InlineKeyboardButton(
                PREMIUM_LOCATION_NAME,
                callback_data="location:germany",
                icon_custom_emoji_id=pe.PLAN_RAW["LOCATION"],
                style=theme.PICK,
            )
        ],
        [InlineKeyboardButton("بازگشت", callback_data="menu:back", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")],
    ]
    return InlineKeyboardMarkup(rows)


def all_plans_keyboard() -> InlineKeyboardMarkup:
    """همه‌ی پلن‌های فروش (فارغ از مدت) رو یکجا، زیر همون لوکیشن نشون میده."""
    rows = []
    for plan in PLANS:
        rows.append(
            [
                InlineKeyboardButton(
                    _plan_button_label(plan, with_duration=True),
                    callback_data=f"plan:{plan['id']}",
                    icon_custom_emoji_id=get_plan_icon(plan),
                    style=get_plan_style(plan),
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton("بازگشت", callback_data="menu:buy", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")]
    )
    return InlineKeyboardMarkup(rows)


def gb_tier_keyboard(months: int) -> InlineKeyboardMarkup:
    """مرحله‌ی دوم خرید: انتخاب حجم (یا نامحدود) داخل همون مدت"""
    rows = []
    plans = get_plans_for_duration(months)
    metered = [p for p in plans if not p["is_unlimited"]]
    unlimited = [p for p in plans if p["is_unlimited"]]

    rows.extend(_pair_rows([
        InlineKeyboardButton(
            _plan_button_label(plan),
            callback_data=f"plan:{plan['id']}",
            icon_custom_emoji_id=get_plan_icon(plan),
            style=get_plan_style(plan),
        )
        for plan in metered
    ]))
    for plan in unlimited:
        rows.append(
            [
                InlineKeyboardButton(
                    f"نامحدود (تا {plan['gb']} گیگ) · {plan['price']:,}",
                    callback_data=f"plan:{plan['id']}",
                    icon_custom_emoji_id=get_plan_icon(plan),
                    style=theme.PICK,
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton("بازگشت", callback_data="location:germany", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")]
    )
    return InlineKeyboardMarkup(rows)


def custom_name_choice_keyboard(plan_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "اسم دلخواه",
                    callback_data=f"namecustom:{plan_id}",
                    icon_custom_emoji_id=pe.RAW["NOTES"],
                    style=theme.NAV,
                )
            ],
            [
                InlineKeyboardButton(
                    "اسم رندوم",
                    callback_data=f"namerandom:{plan_id}",
                    icon_custom_emoji_id=pe.RAW["GAME_CONTROLLER"],
                    style=theme.PICK,
                )
            ],
            [InlineKeyboardButton("بازگشت", callback_data="menu:buy", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")],
        ]
    )


# ---------------- دکمه‌های درگاه‌های پرداخت (خرید، تمدید، شارژ کیف پول) ----------------
# ترتیب ثابت و مرتب برای همه‌ی صفحه‌های پرداخت:
#   کارت به کارت (عادی) ← کیف پول (همیشه؛ حتی با موجودی کم، که موقع زدن پیام «موجودی کافی نیست» میاد) ←
#   کارت به کارت خودکار ← پرداخت آنلاین (TonPays) ← درگاه ویناپی ← کریپتو.
# هر درگاه ایموجی پریمیوم مخصوص خودش رو داره. رنگ: درگاه‌ها «انتخاب»ن (PICK: تو تم پیش‌فرض آبی)،
# و فقط دکمه‌ی «پرداخت از کیف پول» وقتی موجودی کافیه اقدام نهایی/سریع‌ترین راهه (CTA: تک دکمه‌ی سبز صفحه).
_GATEWAY_ICON = {
    "card": pe.EXTRA_RAW["pk3_credit_card"],   # کارت به کارت عادی
    "wallet": pe.RAW["WALLET"],                # کیف پول
    "autosms": pe.RAW["LIGHTNING"],            # کارت به کارت خودکار (آنی)
    "tonpays": pe.EXTRA_RAW["card_2"],             # کارت به کارت تون پی
    "winapay": pe.EXTRA_RAW["pk3_phone_arrow_1"],  # درگاه ویناپی
    "crypto": pe.EXTRA_RAW["crypto_globe"],        # کریپتو
}


def _gateway_button(text: str, callback_data: str, key: str, cta: bool = False) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text, callback_data=callback_data, icon_custom_emoji_id=_GATEWAY_ICON[key],
        style=theme.CTA if cta else theme.PICK,
    )


def _gateway_rows(cb: dict, wallet_label: str = None, crypto_label: str = "ارز دیجیتال", wallet_cta: bool = False) -> list:
    """
    cb = {کلید درگاه: callback_data}؛ کلیدها: card, wallet, autosms, tonpays, winapay, crypto
    چینش (تا همه‌ی درگاه‌ها یه‌جا و بدون اسکرول دیده بشن):
      ردیف ۱: کارت به کارت (تمام‌عرض، اول همه)
      بعدش: درگاه‌های آنلاین دوتا‌دوتا (ویناپی | کارت به کارت تون پی ← کارت آنی | ارز دیجیتال)
      آخر: پرداخت از کیف پول (تمام‌عرض، همیشه هست)
    اگه درگاهی غیرفعال باشه، بقیه خودکار جا باز می‌کنن.
    """
    rows = []
    if MANUAL_CARD_PAYMENT_ENABLED and cb.get("card"):
        rows.append([_gateway_button("کارت به کارت", cb["card"], "card")])

    pair = []
    # ویناپی اول (سمت چپ) و کارت به کارت تون پی بعدش (سمت راست)
    if WINAPAY_ENABLED and cb.get("winapay"):
        pair.append(_gateway_button("درگاه ویناپی", cb["winapay"], "winapay"))
    if TONPAYS_ENABLED and cb.get("tonpays"):
        pair.append(_gateway_button("کارت به کارت تون پی", cb["tonpays"], "tonpays"))
    if AUTOSMS_ENABLED and cb.get("autosms"):
        pair.append(_gateway_button("کارت به کارت آنی", cb["autosms"], "autosms"))
    if CRYPTO_PAYMENT_ENABLED and cb.get("crypto"):
        pair.append(_gateway_button(crypto_label, cb["crypto"], "crypto"))
    for i in range(0, len(pair), 2):
        rows.append(pair[i:i + 2])

    if cb.get("wallet"):
        rows.append([_gateway_button(wallet_label, cb["wallet"], "wallet", cta=wallet_cta)])
    return rows


def confirm_payment_keyboard(
    plan_id: str, wallet_balance: int = 0, final_price: int = None, discount_applied: bool = False
) -> InlineKeyboardMarkup:
    plan = get_plan(plan_id)
    price = final_price if final_price is not None else (plan["price"] if plan else 0)
    wallet_label = f"پرداخت از کیف پول (موجودی: {wallet_balance:,})"
    rows = _gateway_rows(
        {
            "card": f"pay:{plan_id}",
            "wallet": f"walletpay:{plan_id}",
            "autosms": f"autosms:{plan_id}",
            "tonpays": f"tonpays:{plan_id}",
            "winapay": f"winapay:{plan_id}",
            "crypto": f"cryptopay:{plan_id}",
        },
        wallet_label=wallet_label,
        wallet_cta=wallet_balance >= price,   # موجودی کافیه: پرداخت فوری از کیف پول = تک دکمه‌ی سبز
    )
    # کد تخفیف و پشتیبانی کنار هم، یه ردیف
    if discount_applied:
        discount_btn = InlineKeyboardButton(
            "حذف کد تخفیف", callback_data=f"discountremove:{plan_id}",
            icon_custom_emoji_id=pe.RAW["REJECT"], style="danger",
        )
    else:
        discount_btn = InlineKeyboardButton(
            "کد تخفیف دارم", callback_data=f"discountask:{plan_id}",
            icon_custom_emoji_id=pe.EXTRA_RAW["gift_2"], style=theme.NAV,
        )
    rows.append(
        [discount_btn, InlineKeyboardButton("پشتیبانی", url=SUPPORT_LINK, icon_custom_emoji_id=pe.RAW["SUPPORT"])]
    )
    rows.append(
        [InlineKeyboardButton("بازگشت", callback_data="menu:buy", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")]
    )
    return InlineKeyboardMarkup(rows)


def renew_location_keyboard(sub_id: int) -> InlineKeyboardMarkup:
    """مرحله‌ی اول تمدید: فقط یک لوکیشن، یک دکمه"""
    rows = [
        [
            InlineKeyboardButton(
                PREMIUM_LOCATION_NAME,
                callback_data=f"renewlocation:{sub_id}:germany",
                icon_custom_emoji_id=pe.PLAN_RAW["LOCATION"],
                style=theme.PICK,
            )
        ],
        [
            InlineKeyboardButton(
                "بازگشت",
                callback_data="menu:myservices",
                icon_custom_emoji_id=pe.RAW["BACK"],
                style="danger",
            )
        ],
    ]
    return InlineKeyboardMarkup(rows)


def renew_duration_keyboard(sub_id: int) -> InlineKeyboardMarkup:
    """مرحله‌ی دوم تمدید (بعد از لوکیشن): انتخاب مدت؛ ۱ ماهه آبی، ۲ ماهه سبز، ۳ ماهه قرمز"""
    rows = []
    for months in DURATION_MONTHS:
        rows.append(
            [
                InlineKeyboardButton(
                    _duration_button_label(months),
                    callback_data=f"renewdur:{sub_id}:{months}",
                    icon_custom_emoji_id=pe.PLAN_RAW.get(f"DUR_{months}") or pe.RAW["CALENDAR"],
                    style=get_duration_style(months),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "بازگشت",
                callback_data=f"renew:{sub_id}",
                icon_custom_emoji_id=pe.RAW["BACK"],
                style="danger",
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def renew_all_plans_keyboard(sub_id: int, recommended_id: str = None) -> InlineKeyboardMarkup:
    """همه‌ی پلن‌های تمدید (فارغ از مدت) رو یکجا، زیر همون لوکیشن نشون میده."""
    rows = []
    for plan in PLANS:
        rows.append(
            [
                InlineKeyboardButton(
                    ("★ " if plan["id"] == recommended_id else "") + _plan_button_label(plan, with_duration=True),
                    callback_data=f"renewplan:{sub_id}:{plan['id']}",
                    icon_custom_emoji_id=get_plan_icon(plan),
                    style=get_plan_style(plan),
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "بازگشت",
                callback_data=f"renew:{sub_id}",
                icon_custom_emoji_id=pe.RAW["BACK"],
                style="danger",
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def renew_gb_tier_keyboard(sub_id: int, months: int, recommended_id: str = None) -> InlineKeyboardMarkup:
    """مرحله‌ی دوم تمدید: انتخاب حجم (یا نامحدود) داخل همون مدت"""
    rows = []
    plans = get_plans_for_duration(months)
    metered = [p for p in plans if not p["is_unlimited"]]
    unlimited = [p for p in plans if p["is_unlimited"]]

    rows.extend(_pair_rows([
        InlineKeyboardButton(
            ("★ " if plan["id"] == recommended_id else "") + _plan_button_label(plan),
            callback_data=f"renewplan:{sub_id}:{plan['id']}",
            icon_custom_emoji_id=get_plan_icon(plan),
            style=get_plan_style(plan),
        )
        for plan in metered
    ]))
    for plan in unlimited:
        rows.append(
            [
                InlineKeyboardButton(
                    f"نامحدود (تا {plan['gb']} گیگ) · {plan['price']:,}",
                    callback_data=f"renewplan:{sub_id}:{plan['id']}",
                    icon_custom_emoji_id=get_plan_icon(plan),
                    style=theme.PICK,
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "بازگشت",
                callback_data=f"renewlocation:{sub_id}:germany",
                icon_custom_emoji_id=pe.RAW["BACK"],
                style="danger",
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def confirm_renew_payment_keyboard(sub_id: int, plan_id: str, wallet_balance: int = 0) -> InlineKeyboardMarkup:
    plan = get_plan(plan_id)
    wallet_label = f"پرداخت از کیف پول (موجودی: {wallet_balance:,})"
    rows = _gateway_rows(
        {
            "card": f"renewpay:{sub_id}:{plan_id}",
            "wallet": f"walletrenewpay:{sub_id}:{plan_id}",
            "autosms": f"autosmsrenew:{sub_id}:{plan_id}",
            "tonpays": f"tonpaysrenew:{sub_id}:{plan_id}",
            "winapay": f"winapayrenew:{sub_id}:{plan_id}",
            "crypto": f"cryptopayrenew:{sub_id}:{plan_id}",
        },
        wallet_label=wallet_label,
        wallet_cta=bool(plan) and wallet_balance >= plan["price"],
    )
    rows.append(
        [
            InlineKeyboardButton(
                "سوال دارم؟ پشتیبانی", url=SUPPORT_LINK, icon_custom_emoji_id=pe.RAW["SUPPORT"]
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                "بازگشت",
                callback_data="menu:myservices",
                icon_custom_emoji_id=pe.RAW["BACK"],
                style="danger",
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def card_payment_details_keyboard(
    kind: str, plan_id: str, amount: int, card_number: str, sub_id: int = None
) -> InlineKeyboardMarkup:
    """صفحه‌ی دوم پرداخت کارت‌به‌کارت (خرید/تمدید/شارژ کیف پول): دکمه‌های کپی شماره کارت/مبلغ + ارسال رسید"""
    if kind == "renew":
        send_cb = f"renewpaysend:{sub_id}:{plan_id}"
        back_cb = f"paycardbackrenew:{sub_id}:{plan_id}"
    elif kind == "topup":
        send_cb = f"topupsend:{amount}"
        back_cb = "menu:wallet"
    else:
        send_cb = f"paysend:{plan_id}"
        back_cb = f"paycardback:{plan_id}"
    rows = [
        [
            InlineKeyboardButton(
                "کپی مبلغ (ریال)",
                copy_text=CopyTextButton(text=str(amount * 10)),  # اپ بانک‌ها ریالیه، مثل درگاه خودکار
                icon_custom_emoji_id=pe.RAW["PRICE"],
                style=theme.NAV,
            ),
            InlineKeyboardButton(
                "کپی شماره کارت",
                copy_text=CopyTextButton(text=card_number),
                icon_custom_emoji_id=pe.RAW["CARD"],
                style=theme.NAV,
            ),
        ],
        [
            InlineKeyboardButton(
                "ارسال رسید پرداخت",
                callback_data=send_cb,
                icon_custom_emoji_id=pe.RAW["CONFIRM"],
                style=theme.CTA,
            )
        ],
        [
            InlineKeyboardButton(
                "سوال دارم؟ پشتیبانی", url=SUPPORT_LINK, icon_custom_emoji_id=pe.RAW["SUPPORT"]
            )
        ],
        [
            InlineKeyboardButton(
                "بازگشت", callback_data=back_cb, icon_custom_emoji_id=pe.RAW["BACK"], style="danger"
            )
        ],
    ]
    return InlineKeyboardMarkup(rows)


def autosms_payment_keyboard(
    authority: str, card_number: str, amount_rial: int, kind: str = "new"
) -> InlineKeyboardMarkup:
    """صفحه‌ی فاکتور پرداخت خودکار: کپی مبلغ (به ریال - چون اپ بانک‌ها ریالیه)/کارت + بررسی آنی + ارسال رسید (پشتیبان) + پشتیبانی + انصراف"""
    send_cb = f"attsend:{authority}" if kind == "topup" else f"atsend:{authority}"
    rows = [
        [
            InlineKeyboardButton(
                "کپی مبلغ (ریال)",
                copy_text=CopyTextButton(text=str(amount_rial)),
                icon_custom_emoji_id=pe.RAW["PRICE"],
                style=theme.NAV,
            ),
            InlineKeyboardButton(
                "کپی شماره کارت",
                copy_text=CopyTextButton(text=card_number),
                icon_custom_emoji_id=pe.RAW["CARD"],
                style=theme.NAV,
            ),
        ],
        [
            InlineKeyboardButton(
                "بررسی پرداخت", callback_data=f"atcheck:{authority}",
                icon_custom_emoji_id=pe.RAW["LIGHTNING"], style=theme.CTA,
            )
        ],
        [
            InlineKeyboardButton(
                "ارسال رسید پرداخت (در صورت عدم تایید)", callback_data=send_cb,
                icon_custom_emoji_id=pe.RAW["CONFIRM"],
            )
        ],
        [
            InlineKeyboardButton(
                "سوال دارم؟ پشتیبانی", url=SUPPORT_LINK, icon_custom_emoji_id=pe.RAW["SUPPORT"]
            )
        ],
        [
            InlineKeyboardButton(
                "انصراف", callback_data=f"atcancel:{authority}",
                icon_custom_emoji_id=pe.RAW["BACK"], style="danger",
            )
        ],
    ]
    return InlineKeyboardMarkup(rows)


def my_services_keyboard(subs) -> InlineKeyboardMarkup:
    rows = []
    for s in subs:
        rows.append(
            [
                InlineKeyboardButton(
                    f"تمدید «{s['plan_title']}»",
                    callback_data=f"renew:{s['sub_id']}",
                    icon_custom_emoji_id=pe.RAW["CHARGE"],
                    style=theme.PICK,
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton("بازگشت", callback_data="menu:back", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")]
    )
    return InlineKeyboardMarkup(rows)


def weekly_summary_keyboard(urgent_sub_id: int = None) -> InlineKeyboardMarkup:
    """دکمه‌های پیام خلاصه‌ی هفتگی: (اگه سرویسی عجله‌ای داره) تمدیدش + سرویس‌های من + خاموش‌کردن خلاصه"""
    rows = []
    if urgent_sub_id is not None:
        rows.append(
            [
                InlineKeyboardButton(
                    "تمدید سرویس",
                    callback_data=f"renew:{urgent_sub_id}",
                    icon_custom_emoji_id=pe.RAW["CHARGE"],
                    style=theme.CTA,
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "سرویس‌های من",
                callback_data="menu:myservices",
                icon_custom_emoji_id=pe.RAW["MY_SERVICES"],
                style=theme.NAV,
            )
        ]
    )
    rows.append([InlineKeyboardButton("🔕 خاموش کردن خلاصه‌ی هفتگی", callback_data="wsum:off")])
    return InlineKeyboardMarkup(rows)


def data_warning_keyboard(sub_id: int) -> InlineKeyboardMarkup:
    """پیام هشدار نزدیک‌شدن به سقف حجم - دو دکمه‌ی رنگی: تمدید همین سرویس / خرید سرویس جدید"""
    rows = [
        [
            InlineKeyboardButton(
                "تمدید همین سرویس",
                callback_data=f"renew:{sub_id}",
                icon_custom_emoji_id=pe.RAW["CHARGE"],
                style=theme.CTA,
            ),
            InlineKeyboardButton(
                "خرید سرویس جدید",
                callback_data="menu:buy",
                icon_custom_emoji_id=pe.RAW["CART"],
                style=theme.NAV,
            ),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def expired_notice_keyboard() -> InlineKeyboardMarkup:
    """پیام حذف سرویس بعد از اتمام زمان - فقط دکمه‌ی خرید (سرویس قبلی دیگه وجود نداره که تمدید بشه)"""
    rows = [
        [
            InlineKeyboardButton(
                "خرید سرویس جدید",
                callback_data="menu:buy",
                icon_custom_emoji_id=pe.RAW["CART"],
                style=theme.PICK,
            )
        ],
    ]
    return InlineKeyboardMarkup(rows)


def data_warning_keyboard(sub_id: int) -> InlineKeyboardMarkup:
    """پیام هشدار نزدیک‌شدن به سقف حجم - دو دکمه‌ی رنگی مطابق درخواست"""
    rows = [
        [
            InlineKeyboardButton(
                "تمدید همین سرویس",
                callback_data=f"renew:{sub_id}",
                icon_custom_emoji_id=pe.RAW["CHARGE"],
                style=theme.CTA,
            ),
            InlineKeyboardButton(
                "خرید سرویس جدید",
                callback_data="menu:buy",
                icon_custom_emoji_id=pe.RAW["CART"],
                style=theme.NAV,
            ),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def expired_notice_keyboard() -> InlineKeyboardMarkup:
    """پیام حذف سرویس بعد از پایان مدت و عدم تمدید"""
    rows = [
        [
            InlineKeyboardButton(
                "خرید سرویس جدید",
                callback_data="menu:buy",
                icon_custom_emoji_id=pe.RAW["CART"],
                style=theme.PICK,
            )
        ],
    ]
    return InlineKeyboardMarkup(rows)


def wallet_menu_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                "شارژ کیف پول",
                callback_data="wallettopup:start",
                icon_custom_emoji_id=pe.RAW["CHARGE"],
                style=theme.CTA,
            ),
            InlineKeyboardButton(
                "انتقال موجودی",
                callback_data="wallettransfer:start",
                icon_custom_emoji_id=pe.RAW["TRANSFER"],
                style=theme.NAV,
            ),
        ],
        [InlineKeyboardButton("تراکنش‌های من", callback_data="wallettx:show", icon_custom_emoji_id=pe.RAW["CLOCK"], style=theme.PICK)],
        [InlineKeyboardButton("بازگشت", callback_data="menu:back", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")],
    ]
    return InlineKeyboardMarkup(rows)


def wallet_transfer_confirm_keyboard(target_id: int, amount: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                "بله، انتقال بده",
                callback_data=f"wallettransferconfirm:{target_id}:{amount}",
                icon_custom_emoji_id=pe.RAW["CONFIRM"],
                style=theme.CTA,
            )
        ],
        [
            InlineKeyboardButton(
                "انصراف", callback_data="menu:wallet", icon_custom_emoji_id=pe.RAW["BACK"], style="danger"
            )
        ],
    ]
    return InlineKeyboardMarkup(rows)


def payment_method_keyboard(amount: int) -> InlineKeyboardMarkup:
    rows = _gateway_rows(
        {
            "card": f"topupcard:{amount}",
            "autosms": f"autosmstopup:{amount}",
            "tonpays": f"tonpaystopup:{amount}",
            "winapay": f"winapaytopup:{amount}",
            "crypto": f"cryptopaytopup:{amount}",
        },
        crypto_label="ارز دیجیتال",
    )
    rows.append(
        [
            InlineKeyboardButton(
                "سوال دارم؟ پشتیبانی", url=SUPPORT_LINK, icon_custom_emoji_id=pe.RAW["SUPPORT"]
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                "انصراف", callback_data="menu:wallet", icon_custom_emoji_id=pe.RAW["BACK"], style="danger"
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def confirm_topup_payment_keyboard(amount: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                "ارسال رسید پرداخت",
                callback_data=f"topupsend:{amount}",
                icon_custom_emoji_id=pe.RAW["CARD"],
                style=theme.NAV,
            )
        ],
    ]
    rows.append(
        [
            InlineKeyboardButton(
                "سوال دارم؟ پشتیبانی", url=SUPPORT_LINK, icon_custom_emoji_id=pe.RAW["SUPPORT"]
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                "انصراف",
                callback_data="menu:wallet",
                icon_custom_emoji_id=pe.RAW["BACK"],
                style="danger",
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def crypto_currency_keyboard(kind: str, payload: str) -> InlineKeyboardMarkup:
    """kind: new/renew/topup - payload: بقیه‌ی پارامترهای لازم با : جدا شده (plan_id یا sub_id:plan_id یا amount)"""
    rows = []
    for cur in CRYPTO_CURRENCIES:
        label = CRYPTO_CURRENCY_LABELS.get(cur, cur)
        icon_key = CRYPTO_CURRENCY_ICON.get(cur)
        rows.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"cryptocur:{kind}:{payload}:{cur}",
                    icon_custom_emoji_id=pe.RAW.get(icon_key) if icon_key else None,
                    style=CRYPTO_CURRENCY_STYLES.get(cur),
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton("بازگشت", callback_data="menu:back", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")]
    )
    return InlineKeyboardMarkup(rows)


def crypto_payment_keyboard(pay_url: str, check_callback: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("💎 پرداخت در xRocket", url=pay_url, style=theme.NAV)],
        [InlineKeyboardButton("✅ پرداخت کردم، بررسی کن", callback_data=check_callback, style=theme.CTA)],
        [InlineKeyboardButton("انصراف", callback_data="menu:back", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")],
    ]
    return InlineKeyboardMarkup(rows)


def tonpays_payment_keyboard(invoice_url: str, check_callback: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("💳 پرداخت در TonPays", url=invoice_url, style=theme.NAV)],
        [InlineKeyboardButton("✅ پرداخت کردم، بررسی کن", callback_data=check_callback, style=theme.CTA)],
        [InlineKeyboardButton("انصراف", callback_data="menu:back", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")],
    ]
    return InlineKeyboardMarkup(rows)


def enter_app_keyboard() -> InlineKeyboardMarkup:
    """
    دکمه‌ی «ورود به برنامه» به‌شکل inline (نه دکمه‌ی ثابت پایین صفحه).
    دلیل فنی: طبق مستندات رسمی تلگرام، وقتی یه Mini App از یه دکمه‌ی
    ReplyKeyboard (KeyboardButton.web_app) باز میشه، initData همیشه خالیه -
    یعنی سمت مینی‌اپ هیچ‌وقت نمی‌فهمه کاربر کیه و نمی‌تونه بهش اعتماد کنه.
    اینکه لینک t.me/.../start رو بدیم هم مشکل رو حل نمی‌کنه چون
    ReplyKeyboardButton اصلاً فیلدی برای باز کردن یه URL خام نداره (فقط
    web_app، که همون مشکل initData رو داره). فقط دکمه‌ی inline (همینجا) یا
    دکمه‌ی منوی ثابت کنار پیام (که تو bot.py با MenuButtonWebApp تنظیم شده)
    initData معتبر می‌دن؛ برای همین دکمه‌ی ثابت «ورود به برنامه» فقط متنشو
    می‌فرسته و اینجا (reply_menu_router) با همین دکمه‌ی inline جواب میدیم.
    """
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("ورود به مینی اپ", web_app=WebAppInfo(url=MINIAPP_URL), icon_custom_emoji_id=pe.RAW["MENU_ENTER_APP"], style=theme.NAV)]]
    )


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "بازگشت به منو",
                    callback_data="menu:back",
                    icon_custom_emoji_id=pe.RAW["MENU"],
                    style="danger",
                )
            ]
        ]
    )


def referral_keyboard(referral_link: str) -> InlineKeyboardMarkup:
    share_url = (
        "https://t.me/share/url?url="
        + referral_link
        + "&text="
        + "دعوت کن، هدیه بگیر، رشد کن! 🚀"
    )
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "اشتراک‌گذاری لینک دعوت", url=share_url, icon_custom_emoji_id=pe.RAW["LINK"]
                )
            ],
            [
                InlineKeyboardButton(
                    "🏆 لیدربرد رفرال این ماه",
                    callback_data="referral:leaderboard",
                    style=theme.NAV,
                )
            ],
            [
                InlineKeyboardButton(
                    "بازگشت",
                    callback_data="menu:back",
                    icon_custom_emoji_id=pe.RAW["BACK"],
                    style="danger",
                )
            ],
        ]
    )


def leaderboard_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "بازگشت",
                    callback_data="menu:referral",
                    icon_custom_emoji_id=pe.RAW["BACK"],
                    style="danger",
                )
            ]
        ]
    )


def onboarding_keyboard(next_step: str) -> InlineKeyboardMarkup:
    label = "بزن بریم" if next_step == "done" else "بعدی"
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=f"onboarding:{next_step}", icon_custom_emoji_id=pe.RAW["ROCKET"], style=theme.NAV)]]
    )


def rating_keyboard(context: str, target_id) -> InlineKeyboardMarkup:
    """دکمه‌های ⭐۱ تا ⭐۵ (با آیکون پرمیوم ستاره) برای نظرسنجی رضایت"""
    row = [
        InlineKeyboardButton(str(n), callback_data=f"rate:{context}:{target_id}:{n}", icon_custom_emoji_id=pe.RAW["STAR"])
        for n in range(1, 6)
    ]
    return InlineKeyboardMarkup([row])


def reseller_hub_keyboard(is_reseller: bool, eligible: bool, lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    rows = []
    if is_reseller:
        rows.append(
            [
                InlineKeyboardButton(
                    t("reseller_catalog_button", lang),
                    callback_data="reseller:catalog",
                    icon_custom_emoji_id=pe.RAW["CART"],
                    style=theme.CTA,
                )
            ]
        )
    elif eligible:
        rows.append(
            [
                InlineKeyboardButton(
                    t("reseller_request_with_reason_btn", lang),
                    callback_data="reseller:reqreason",
                    icon_custom_emoji_id=pe.RAW["CHAT"],
                    style=theme.NAV,
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    t("reseller_request_plain_btn", lang),
                    callback_data="reseller:reqplain",
                    icon_custom_emoji_id=pe.RAW["MEGAPHONE"],
                    style=theme.NAV,
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "شارژ کیف پول",
                callback_data="wallettopup:start",
                icon_custom_emoji_id=pe.RAW["WALLET"],
                style=theme.NAV,
            )
        ]
    )
    rows.append(
        [InlineKeyboardButton("بازگشت", callback_data="menu:back", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")]
    )
    return InlineKeyboardMarkup(rows)


def reseller_catalog_keyboard() -> InlineKeyboardMarkup:
    """مرحله‌ی اول خرید نمایندگی: انتخاب لوکیشن (مثل خرید عادی؛ فعلاً یک لوکیشن)"""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    PREMIUM_LOCATION_NAME,
                    callback_data="reseller:dur",
                    icon_custom_emoji_id=pe.PLAN_RAW["LOCATION"],
                    style=theme.PICK,
                )
            ],
            [InlineKeyboardButton("بازگشت", callback_data="reseller:hub", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")],
        ]
    )


def reseller_duration_keyboard() -> InlineKeyboardMarkup:
    """مرحله‌ی دوم: انتخاب مدت (با قیمت نمایندگیِ ارزون‌ترین پلنِ همون مدت)"""
    rows = []
    for months in DURATION_MONTHS:
        plans = [p for p in get_plans_for_duration(months) if not p.get("is_unlimited")] or get_plans_for_duration(months)
        label = DURATION_LABELS[months]
        if plans:
            label += f" | از {min(p['reseller_price'] for p in plans):,} تومان"
        rows.append(
            [
                InlineKeyboardButton(
                    label,
                    callback_data=f"reseller:vol:{months}",
                    icon_custom_emoji_id=pe.PLAN_RAW.get(f"DUR_{months}") or pe.RAW["CALENDAR"],
                    style=get_duration_style(months),
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton("بازگشت", callback_data="reseller:catalog", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")]
    )
    return InlineKeyboardMarkup(rows)


def reseller_volume_keyboard(months: int) -> InlineKeyboardMarkup:
    """مرحله‌ی سوم: انتخاب حجم داخل همون مدت (قیمت‌ها قیمت نمایندگی‌ان)"""
    rows = []
    plans = get_plans_for_duration(months)
    for plan in [p for p in plans if not p["is_unlimited"]] + [p for p in plans if p["is_unlimited"]]:
        gb_text = f"نامحدود (تا {plan['gb']} گیگ)" if plan["is_unlimited"] else f"{plan['gb']} گیگ"
        rows.append(
            [
                InlineKeyboardButton(
                    f"{gb_text} | {DURATION_LABELS[plan['duration_months']]} | {plan['reseller_price']:,} تومان",
                    callback_data=f"resellerbuy:{plan['id']}",
                    icon_custom_emoji_id=get_plan_icon(plan),
                    style=get_plan_style(plan),
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton("بازگشت", callback_data="reseller:dur", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")]
    )
    return InlineKeyboardMarkup(rows)


def reseller_name_choice_keyboard(plan_id: str) -> InlineKeyboardMarkup:
    """انتخاب اسم سرویس در خرید نمایندگی: اسم دلخواه یا رندوم"""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "اسم دلخواه",
                    callback_data=f"rnamecustom:{plan_id}",
                    icon_custom_emoji_id=pe.RAW["NOTES"],
                    style=theme.NAV,
                )
            ],
            [
                InlineKeyboardButton(
                    "اسم رندوم",
                    callback_data=f"rnamerandom:{plan_id}",
                    icon_custom_emoji_id=pe.RAW["GAME_CONTROLLER"],
                    style=theme.PICK,
                )
            ],
            [InlineKeyboardButton("بازگشت", callback_data="reseller:catalog", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")],
        ]
    )


def reseller_confirm_keyboard(plan_id: str, shortfall: int = 0) -> InlineKeyboardMarkup:
    rows = []
    if shortfall > 0:
        rows.append(
            [
                InlineKeyboardButton(
                    f"شارژ {shortfall:,} تومان با درگاه پرداخت",
                    callback_data=f"rtopup:{plan_id}",
                    icon_custom_emoji_id=pe.RAW["WALLET"],
                    style=theme.CTA,
                )
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    "تایید و خرید از کیف پول",
                    callback_data=f"resellerconfirm:{plan_id}",
                    icon_custom_emoji_id=pe.RAW["CONFIRM"],
                    style=theme.CTA,
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton("انصراف", callback_data="reseller:catalog", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")]
    )
    return InlineKeyboardMarkup(rows)


def loyalty_hub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "بازگشت",
                    callback_data="menu:back",
                    icon_custom_emoji_id=pe.RAW["BACK"],
                    style="danger",
                )
            ]
        ]
    )


def admin_reseller_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "تایید نمایندگی",
                    callback_data=f"resellerapprove:{request_id}",
                    icon_custom_emoji_id=pe.RAW["CONFIRM"],
                    style=theme.CTA,
                ),
                InlineKeyboardButton(
                    "رد درخواست",
                    callback_data=f"resellerreject:{request_id}",
                    icon_custom_emoji_id=pe.RAW["REJECT"],
                    style="danger",
                ),
            ]
        ]
    )


def admin_decision_keyboard(order_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                "تایید و صدور سرویس",
                callback_data=f"approve:{order_id}",
                icon_custom_emoji_id=pe.RAW["CONFIRM"],
                style=theme.CTA,
            ),
            InlineKeyboardButton(
                "رد کردن",
                callback_data=f"reject:{order_id}",
                icon_custom_emoji_id=pe.RAW["REJECT"],
                style="danger",
            ),
        ]
    ]
    return InlineKeyboardMarkup(rows)


def platform_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                "اندروید", callback_data="platform:android", icon_custom_emoji_id=pe.RAW["ANDROID"]
            ),
            InlineKeyboardButton(
                "iOS / آیپد", callback_data="platform:ios", icon_custom_emoji_id=pe.RAW["APPLE"]
            ),
        ],
        [
            InlineKeyboardButton(
                "ویندوز", callback_data="platform:windows", icon_custom_emoji_id=pe.RAW["WINDOWS"]
            ),
            InlineKeyboardButton(
                "مک", callback_data="platform:mac", icon_custom_emoji_id=pe.RAW["APPLE"]
            ),
        ],
        [
            InlineKeyboardButton(
                "لینوکس", callback_data="platform:linux", icon_custom_emoji_id=pe.RAW["LINUX"]
            )
        ],
        [
            InlineKeyboardButton(
                "بازگشت", callback_data="menu:back", icon_custom_emoji_id=pe.RAW["BACK"], style="danger"
            )
        ],
    ]
    return InlineKeyboardMarkup(rows)


def platform_guide_keyboard(guide: dict = None) -> InlineKeyboardMarkup:
    rows = []
    if guide and guide.get("link"):
        rows.append(
            [
                InlineKeyboardButton(
                    guide.get("download_label") or "صفحه‌ی دانلود",
                    url=guide["link"],
                    icon_custom_emoji_id=pe.RAW["LINK"],
                    style=theme.CTA,
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    "لینک اشتراک من (سرویس‌های من)",
                    callback_data="menu:myservices",
                    icon_custom_emoji_id=pe.RAW["MENU_SERVICES"],
                    style=theme.PICK,
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "بازگشت به لیست دستگاه‌ها",
                callback_data="menu:apps",
                icon_custom_emoji_id=pe.RAW["BACK"],
                style="danger",
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def services_table_keyboard(rows, page: int, total_pages: int, sort_key: str, search_active: bool) -> InlineKeyboardMarkup:
    """
    rows: لیستی از دیکشنری‌ها با کلیدهای sub_id, name_label, volume_label, days_label
    رنگ‌ها: مرتب‌سازیِ فعال = سبز | سرستون جدول = آبی (نمایشی) | بازگشت = قرمز | بقیه بی‌رنگ
    """
    def sort_btn(label, key, icon):
        return InlineKeyboardButton(
            label, callback_data=f"svcsort:{key}", icon_custom_emoji_id=icon,
            style=theme.PICK if sort_key == key else None,
        )

    kb_rows = [
        [
            sort_btn("زمان", "days", pe.RAW["CLOCK"]),
            sort_btn("حجم", "volume", pe.RAW["REMAINING"]),
            sort_btn("نام سرویس", "name", pe.RAW["MY_SERVICES"]),
        ],
        [
            InlineKeyboardButton(
                "جستجو در سرویس‌ها", callback_data="svcsearch:start",
                icon_custom_emoji_id=pe.EXTRA_RAW["pk3_magnifier_left"],
            )
        ],
    ]

    if search_active:
        kb_rows.append(
            [
                InlineKeyboardButton(
                    "پاک کردن جستجو", callback_data="svcsearch:clear",
                    icon_custom_emoji_id=pe.RAW["REJECT"], style="danger",
                )
            ]
        )

    kb_rows.append(
        [
            InlineKeyboardButton("نام سرویس", callback_data="noop", style=theme.NAV),
            InlineKeyboardButton("حجم مانده", callback_data="noop", style=theme.NAV),
            InlineKeyboardButton("زمان مانده", callback_data="noop", style=theme.NAV),
        ]
    )

    for r in rows:
        target = f"svcdetail:{r['sub_id']}:{page}:{sort_key}"
        kb_rows.append(
            [
                InlineKeyboardButton(r["name_label"], callback_data=target),
                InlineKeyboardButton(r["volume_label"], callback_data=target),
                InlineKeyboardButton(r["days_label"], callback_data=target),
            ]
        )

    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(
                InlineKeyboardButton(
                    "قبلی", callback_data=f"svcpage:{page-1}:{sort_key}",
                    icon_custom_emoji_id=pe.EXTRA_RAW["pk3_play_reverse"],
                )
            )
        nav_row.append(InlineKeyboardButton(f"{page} / {total_pages}", callback_data="noop"))
        if page < total_pages:
            nav_row.append(
                InlineKeyboardButton(
                    "بعدی", callback_data=f"svcpage:{page+1}:{sort_key}",
                    icon_custom_emoji_id=pe.EXTRA_RAW["pk3_play_1"],
                )
            )
        kb_rows.append(nav_row)

    kb_rows.append(
        [InlineKeyboardButton("بازگشت", callback_data="menu:back", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")]
    )
    return InlineKeyboardMarkup(kb_rows)

def service_detail_keyboard(
    sub_id: int,
    page: int,
    sort_key: str,
    volume_label: str,
    days_label: str,
    sub_link: str,
    auto_renew: bool = False,
    show_auto_renew: bool = True,
) -> InlineKeyboardMarkup:
    """
    صفحه‌ی جزئیات سرویس. منطق رنگ‌ها (توی کل بات یکسانه):
      سبز = اقدام اصلی (تمدید، تمدید خودکارِ روشن)  |  آبی = ابزارهای سرویس  |  قرمز = حذف و بازگشت
      چیپ‌های حجم و زمان فقط نمایشی‌ان و بی‌رنگ.
    چینش: آمار ← تمدید ← لینک‌ها ← ابزارها ← یادداشت/انتقال ← تمدید خودکار ← حذف/بازگشت (همه دوتا‌دوتا، بدون شلوغی)
    """
    def cb(action):
        return f"{action}:{sub_id}:{page}:{sort_key}"

    rows = [
        # آمار (نمایشی)
        [
            InlineKeyboardButton(volume_label, callback_data="noop", icon_custom_emoji_id=pe.RAW["REMAINING"]),
            InlineKeyboardButton(days_label, callback_data="noop", icon_custom_emoji_id=pe.RAW["CLOCK"]),
        ],
        # اقدام اصلی
        [
            InlineKeyboardButton(
                "تمدید سرویس", callback_data=f"renew:{sub_id}",
                icon_custom_emoji_id=pe.RAW["CHARGE"], style=theme.CTA,
            )
        ],
        # لینک‌ها
        [
            InlineKeyboardButton(
                "دریافت اشتراک", callback_data=cb("svcgetsub"),
                icon_custom_emoji_id=pe.RAW["LINK"], style=theme.NAV,
            ),
            InlineKeyboardButton(
                "وضعیت و راهنما", url=sub_link,
                icon_custom_emoji_id=pe.RAW["EYES"], style=theme.NAV,
            ),
        ],
    ]

    # ابزارها: دکمه‌ی مخصوص نوع پنل + بروزرسانی لینک
    # (کانفیگ‌های تکی فقط رو مرزبان واقعیه و بررسی آنلاین/آفلاین فقط رو سنایی؛ پس هر پنل فقط دکمه‌ی خودش رو می‌بینه)
    tools = []
    if PANEL_TYPE == "marzban":
        tools.append(
            InlineKeyboardButton(
                "دریافت کانفیگ‌ها", callback_data=cb("svcgetconfigs"),
                icon_custom_emoji_id=pe.RAW["LIST"], style=theme.NAV,
            )
        )
    if PANEL_TYPE == "sanaei":
        tools.append(
            InlineKeyboardButton(
                "بررسی اتصال", callback_data=cb("svccheckonline"),
                icon_custom_emoji_id=pe.RAW["CONNECTION"], style=theme.NAV,
            )
        )
    tools.append(
        InlineKeyboardButton(
            "بروزرسانی لینک", callback_data=cb("svcrefreshlink"),
            icon_custom_emoji_id=pe.EXTRA_RAW["pk3_gear_1"], style=theme.NAV,
        )
    )
    rows.append(tools)

    rows.append(
        [
            InlineKeyboardButton(
                "یادداشت سرویس", callback_data=cb("svcnote"),
                icon_custom_emoji_id=pe.RAW["NOTES"], style=theme.NAV,
            ),
            InlineKeyboardButton(
                "انتقال سرویس", callback_data=cb("svctransfer"),
                icon_custom_emoji_id=pe.RAW["TRANSFER"], style=theme.NAV,
            ),
        ]
    )

    if show_auto_renew:
        rows.append(
            [
                InlineKeyboardButton(
                    f"تمدید خودکار: {'روشن' if auto_renew else 'خاموش'}",
                    callback_data=f"autorenew:{sub_id}:{page}:{sort_key}:{0 if auto_renew else 1}",
                    icon_custom_emoji_id=pe.RAW["CONFIRM"] if auto_renew else pe.RAW["REJECT"],
                    style=theme.PICK if auto_renew else None,
                )
            ]
        )

    # ناحیه‌ی خطر و بازگشت
    rows.append(
        [
            InlineKeyboardButton(
                "حذف اکانت", callback_data=cb("svcdeleteask"),
                icon_custom_emoji_id=pe.RAW["TRASH"], style="danger",
            ),
            InlineKeyboardButton(
                "بازگشت به لیست", callback_data=f"svcpage:{page}:{sort_key}",
                icon_custom_emoji_id=pe.RAW["BACK"], style="danger",
            ),
        ]
    )
    return InlineKeyboardMarkup(rows)

def service_delete_confirm_keyboard(sub_id: int, page: int, sort_key: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                "بله، کامل حذف کن",
                callback_data=f"svcdelete:{sub_id}:{page}:{sort_key}",
                icon_custom_emoji_id=pe.RAW["TRASH"],
                style="danger",
            )
        ],
        [
            InlineKeyboardButton(
                "انصراف",
                callback_data=f"svcdetail:{sub_id}:{page}:{sort_key}",
                icon_custom_emoji_id=pe.RAW["BACK"],
                style="danger",
            )
        ],
    ]
    return InlineKeyboardMarkup(rows)


def service_note_keyboard(sub_id: int, page: int, sort_key: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                "✏️ ثبت/ویرایش یادداشت",
                callback_data=f"svcnoteedit:{sub_id}:{page}:{sort_key}",
                style=theme.PICK,
            )
        ],
        [
            InlineKeyboardButton(
                "بازگشت",
                callback_data=f"svcdetail:{sub_id}:{page}:{sort_key}",
                icon_custom_emoji_id=pe.RAW["BACK"],
                style="danger",
            )
        ],
    ]
    return InlineKeyboardMarkup(rows)


def support_menu_keyboard(answered_count: int = 0) -> InlineKeyboardMarkup:
    my_tickets = "تیکت‌های من" + (f" ({answered_count} پاسخ جدید)" if answered_count else "")
    rows = [
        [
            InlineKeyboardButton("سوالات متداول", callback_data="faq:show", icon_custom_emoji_id=pe.RAW["QUESTION"]),
            InlineKeyboardButton(
                "ثبت تیکت جدید", callback_data="ticket:new", icon_custom_emoji_id=pe.RAW["CHAT"], style=theme.CTA
            ),
        ],
        [
            InlineKeyboardButton(my_tickets, callback_data="ticket:list", icon_custom_emoji_id=pe.RAW["FOLDERS"], style=theme.NAV),
            InlineKeyboardButton(
                "پشتیبانی تلگرام", url=SUPPORT_LINK, icon_custom_emoji_id=pe.RAW["SUPPORT"], style=theme.NAV
            ),
        ],
        [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data="menu:back", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")],
    ]
    return InlineKeyboardMarkup(rows)


def faq_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("ثبت تیکت جدید", callback_data="ticket:new", icon_custom_emoji_id=pe.RAW["CHAT"], style=theme.CTA)],
            [InlineKeyboardButton("بازگشت", callback_data="menu:support", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")],
        ]
    )


_TICKET_STATUS_LABEL = {"open": "در انتظار پاسخ", "answered": "پاسخ داده شد", "closed": "بسته شده"}


def ticket_list_keyboard(tickets) -> InlineKeyboardMarkup:
    status_emoji = {"open": "🟡", "answered": "🟢", "closed": "⚪️"}
    rows = []
    for t in tickets:
        subject = (t["subject"] or "").replace("\n", " ")
        label = (
            f"{status_emoji.get(t['status'], '⚪️')} #{t['ticket_id']} · "
            f"{_TICKET_STATUS_LABEL.get(t['status'], '')} · {subject[:18]}"
        )
        rows.append([InlineKeyboardButton(label, callback_data=f"ticketview:{t['ticket_id']}")])
    rows.append(
        [InlineKeyboardButton("ثبت تیکت جدید", callback_data="ticket:new", icon_custom_emoji_id=pe.RAW["CHAT"], style=theme.CTA)]
    )
    rows.append(
        [InlineKeyboardButton("بازگشت", callback_data="menu:support", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")]
    )
    return InlineKeyboardMarkup(rows)


def ticket_detail_keyboard(ticket_id: int, is_open: bool) -> InlineKeyboardMarkup:
    rows = []
    if is_open:
        rows.append(
            [InlineKeyboardButton("✉️ ارسال پیام جدید", callback_data=f"ticketreply_user:{ticket_id}", style=theme.CTA)]
        )
        rows.append(
            [InlineKeyboardButton("✅ مشکلم حل شد، تیکت رو ببند", callback_data=f"ticketuserclose:{ticket_id}", style=theme.NAV)]
        )
    else:
        rows.append(
            [InlineKeyboardButton("ثبت تیکت جدید", callback_data="ticket:new", icon_custom_emoji_id=pe.RAW["CHAT"], style=theme.CTA)]
        )
    rows.append(
        [InlineKeyboardButton("بازگشت به لیست", callback_data="ticket:list", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")]
    )
    return InlineKeyboardMarkup(rows)


def ticket_created_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    """زیر پیام «تیکت ثبت شد»"""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("مشاهده‌ی تیکت", callback_data=f"ticketview:{ticket_id}", icon_custom_emoji_id=pe.RAW["FOLDERS"], style=theme.NAV)],
            [InlineKeyboardButton("بازگشت به پشتیبانی", callback_data="menu:support", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")],
        ]
    )


def ticket_answer_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    """زیر پیام «پاسخ پشتیبانی» که برای کاربر میره؛ پیام خودش (متن پاسخ) دست‌نخورده می‌مونه"""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("مشاهده و پاسخ", callback_data=f"ticketview:{ticket_id}", icon_custom_emoji_id=pe.RAW["CHAT"], style=theme.CTA)]]
    )


def ticket_closed_keyboard() -> InlineKeyboardMarkup:
    """زیر پیام «تیکت بسته شد»"""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("ثبت تیکت جدید", callback_data="ticket:new", icon_custom_emoji_id=pe.RAW["CHAT"], style=theme.CTA)],
            [InlineKeyboardButton("تیکت‌های من", callback_data="ticket:list", icon_custom_emoji_id=pe.RAW["FOLDERS"], style=theme.NAV)],
        ]
    )


def admin_ticket_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                "پاسخ بده", callback_data=f"ticketreply_admin:{ticket_id}",
                icon_custom_emoji_id=pe.RAW["CHAT"], style=theme.CTA
            ),
            InlineKeyboardButton(
                "بستن تیکت", callback_data=f"ticketclose:{ticket_id}",
                icon_custom_emoji_id=pe.RAW["LOCK"], style="danger"
            ),
        ]
    ]
    return InlineKeyboardMarkup(rows)


def account_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                "افزایش موجودی",
                callback_data="wallettopup:start",
                icon_custom_emoji_id=pe.RAW["CHARGE"],
                style=theme.CTA,
            ),
            InlineKeyboardButton(
                "انتقال موجودی",
                callback_data="wallettransfer:start",
                icon_custom_emoji_id=pe.RAW["TRANSFER"],
                style=theme.NAV,
            ),
        ],
        [InlineKeyboardButton("تراکنش‌های من", callback_data="wallettx:show", icon_custom_emoji_id=pe.RAW["CLOCK"], style=theme.PICK)],
        [InlineKeyboardButton("بازگشت", callback_data="menu:back", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")],
    ]
    return InlineKeyboardMarkup(rows)


def get_referral_link(user_id: int) -> str:
    return f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
