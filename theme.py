"""
تم رنگی دکمه‌های بات (تنها منبع حقیقت برای رنگ دکمه‌ها).

تلگرام فقط سه رنگ می‌ده: آبی (primary)، سبز (success) و قرمز (danger)؛ بدون style هم دکمه خاکستریه.
هر دکمه یه «نقش» داره و رنگش از روی نقشش و تم فعال (BUTTON_THEME تو .env) تعیین میشه:

  NAV    ناوبری و انتخاب‌ها (منو، لیست‌ها، جزئیات)            همه‌ی تم‌ها: آبی
  CTA    اقدام نهایی/پولیِ هر صفحه (پرداخت، تایید، تمدید ...)    semantic/classic: سبز | blue: آبی
  PICK   انتخاب‌هایی که قبلاً سبز بودن (لوکیشن، پلن، ...)       classic: سبز | semantic/blue: آبی
  BACK / DANGER  بازگشت، انصراف، حذف                          همه‌ی تم‌ها: قرمز

تم‌ها:
  semantic (پیش‌فرض)  آبی برای همه‌چیز + سبز فقط برای یک دکمه‌ی اقدام در هر صفحه تا چشم مستقیم بره روش
  blue                همه‌ی دکمه‌ها آبی (بجز بازگشت/لغو که قرمزه)
  classic             رنگ‌بندی قبلی بات
برای عوض‌کردن: توی .env بنویس BUTTON_THEME=blue (یا semantic / classic) و بات رو ریستارت کن.
"""
from config import BUTTON_THEME as _RAW_THEME

THEME = _RAW_THEME if _RAW_THEME in ("semantic", "blue", "classic") else "semantic"

NAV = "primary"
BACK = "danger"
DANGER = "danger"

if THEME == "blue":
    CTA = "primary"
    PICK = "primary"
elif THEME == "classic":
    CTA = "success"
    PICK = "success"
else:
    CTA = "success"
    PICK = "primary"

# رنگ مدت‌ها تو تم قبلی «چراغ‌راهنما» بود (۱ ماهه آبی، ۲ ماهه سبز، ۳ ماهه قرمز)؛ تو بقیه‌ی تم‌ها همه آبی
_LEGACY_DURATION_STYLE = {1: "primary", 2: "success", 3: "danger", 6: "danger"}


def duration_style(months) -> str:
    if THEME == "classic":
        return _LEGACY_DURATION_STYLE.get(months, "primary")
    return NAV
