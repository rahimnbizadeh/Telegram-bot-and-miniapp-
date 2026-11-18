"""
تنظیمات اصلی ربات نوردیس (Noordis)
همه‌ی مقادیر حساس (توکن، رمزها و ...) از فایل .env خونده می‌شن.
یک فایل .env.example نمونه در کنار پروژه هست؛ کپی کن به .env و پر کن.
"""
import os
from dotenv import load_dotenv

import premium_emoji as _pe   # فقط برای تگ ایموجی پلن‌ها (premium_emoji به config وابسته نیست، پس چرخه‌ی import نداریم)

load_dotenv()

# ---------- برندینگ ----------
BRAND_NAME_FA = os.getenv("BRAND_NAME_FA", "نوردیس")
BRAND_NAME_EN = os.getenv("BRAND_NAME_EN", "Noordis")

# پیشوند اسمی که تو لینک vless (بعد از #) و به‌عنوان remark نمایش داده میشه.
# فقط جنبه‌ی نمایشی داره - هیچ‌جای دیگه‌ی بات (لینک ساب، دیتابیس، API پنل)
# ازش استفاده نمی‌کنه، پس امن می‌تونه هر چیزی (با ایموجی/فاصله) باشه.
VLESS_REMARK_PREFIX = os.getenv("VLESS_REMARK_PREFIX", "Noordis 💎")
# پیشوند اسم کانفیگ برای سرویس‌هایی که از بخش «نمایندگی» خریداری میشن (به‌جای VLESS_REMARK_PREFIX).
# اسم برند خودت هیچ‌جای این سرویس‌ها نمیاد؛ اسمی که نماینده انتخاب می‌کنه بعد از همین پیشوند میاد.
# فقط جنبه‌ی نمایشی داره و با ایموجی/فاصله هم مشکلی نداره. مثال: VIP 💎
RESELLER_REMARK_PREFIX = os.getenv("RESELLER_REMARK_PREFIX", "VIP 💎")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "Noordis_Support")
SUPPORT_LINK = os.getenv("SUPPORT_LINK", "https://t.me/noordis_support")

# ---------- تنظیمات ربات تلگرام ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "NoordisVpnBot")
# آدرس عمومی و HTTPS جایی که Mini App (پوشه‌ی miniapp/) در دسترسه.
# روی Replit معمولا چیزی شبیه این میشه: https://<repl-name>.<username>.repl.co/app
# تا وقتی این مقدار خالیه، دکمه‌ی منوی Mini App اصلا برای بات ثبت نمیشه.
MINIAPP_URL = os.getenv("MINIAPP_URL", "")
# دکمه‌ی «ورود به مینی‌اپ» توی منوی ثابت پایین صفحه (فعلاً خاموش؛ برای روشن‌کردن: MAIN_MENU_MINIAPP_BUTTON=true)
MAIN_MENU_MINIAPP_BUTTON = os.getenv("MAIN_MENU_MINIAPP_BUTTON", "false").lower() in ("1", "true", "yes")

# تم رنگی دکمه‌ها (فایل theme.py): semantic = آبی برای ناوبری + سبز فقط برای اقدام نهایی هر صفحه (پیش‌فرض)،
# blue = همه آبی، classic = رنگ‌بندی قبلی (سبزِ بیشتر). «بازگشت/لغو» تو همه‌ی تم‌ها قرمز می‌مونه.
BUTTON_THEME = os.getenv("BUTTON_THEME", "semantic").strip().lower()
# پورت داخلی سرور Flask که Mini App/API روش سرو میشه (nginx بهش proxy میزنه).
# پیش‌فرض 8081 چون رو سرور فعلی، پنل ثنایی/X-UI پورت 8080 رو گرفته بود؛
# اگه یه روز این پورت هم اشغال شد، فقط همینو توی .env عوض کن، لازم نیست کد رو دست بزنی.
MINIAPP_PORT = int(os.getenv("MINIAPP_PORT", "8081"))

# آیدی عددی ادمین‌ها (میتونی چندتا بذاری، با کاما جدا کن)
# آیدی عددی خودت رو از ربات‌هایی مثل @userinfobot میتونی بگیری
ADMIN_IDS = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]

# آیدی عددی چتی که رسیدهای پرداخت برای تایید به اونجا فوروارد میشه
# میتونه خود ادمین باشه یا یک گروه/کانال خصوصی
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

# ---------- اطلاعات کارت برای پرداخت ----------
CARD_NUMBER = os.getenv("CARD_NUMBER", "6219-8614-0484-9167")
CARD_HOLDER = os.getenv("CARD_HOLDER", "رحیم نبی زاده")

# ---------- حالت آزمایشی (بدون نیاز به پنل واقعی Marzban) ----------
# وقتی True باشه، ربات به‌جای اتصال واقعی به پنل، داده‌ی فرضی برمی‌گردونه
# تا بتونی کل روند خرید/تایید/تست‌رایگان رو امتحان کنی. وقتی VPS و پنل واقعی
# رو راه انداختی، این مقدار رو در Secrets/​.env روی False بذار.
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in ("1", "true", "yes")

# ---------- انتخاب نوع پنل ----------
# marzban یا sanaei - با همین یک سوییچ کل ربات بین دو پنل جابه‌جا میشه
PANEL_TYPE = os.getenv("PANEL_TYPE", "marzban").lower()

# ---------- تنظیمات پنل Marzban ----------
MARZBAN_URL = os.getenv("MARZBAN_URL", "https://your-panel-domain.com").rstrip("/")
MARZBAN_USERNAME = os.getenv("MARZBAN_USERNAME", "")
MARZBAN_PASSWORD = os.getenv("MARZBAN_PASSWORD", "")

# پروتکل‌هایی که موقع ساخت یوزر جدید فعال میشن
# مقدار خالی {} یعنی از تنظیمات پیش‌فرض inbound همون پروتکل تو پنل استفاده بشه
MARZBAN_PROTOCOLS = ["vless", "vmess"]

# پیشوند یوزرنیم‌ها روی پنل، برای تشخیص راحت‌تر مشتری‌های نوردیس
MARZBAN_USERNAME_PREFIX = "noordis"

# ---------- تنظیمات پنل سنایی (Sanaei / 3x-ui) ----------
# فقط وقتی لازمن که PANEL_TYPE=sanaei باشه
SANAEI_URL = os.getenv("SANAEI_URL", "https://your-sanaei-panel.com:2053").rstrip("/")
# روش اول (پیشنهادی): توکن API. از پنل برو Settings -> Security -> API Token
# و یه توکن بساز، بعد بذارش تو SANAEI_API_TOKEN. وقتی این مقدار پر باشه، بات
# اصلا نیازی به یوزرنیم/پسورد نداره و لاگین سشن هم انجام نمیده.
SANAEI_API_TOKEN = os.getenv("SANAEI_API_TOKEN", "")
# روش دوم (فقط اگه توکن نداری): یوزرنیم/پسورد پنل - روش قدیمی‌تر و مبتنی بر
# سشن/کوکیه. نسخه‌های جدید 3x-ui این روش رو هم پشتیبانی می‌کنن، ولی اگه
# ورود دو مرحله‌ای (2FA) روی اکانت پنلت فعاله، این روش کار نمی‌کنه و حتما
# باید از SANAEI_API_TOKEN استفاده کنی.
SANAEI_USERNAME = os.getenv("SANAEI_USERNAME", "")
SANAEI_PASSWORD = os.getenv("SANAEI_PASSWORD", "")
# آیدی عددی inbound-ای که کاربرای جدید توش ساخته میشن (از پنل ببین چنده)
SANAEI_INBOUND_ID = int(os.getenv("SANAEI_INBOUND_ID", "1"))
SANAEI_USERNAME_PREFIX = "noordis"
# آدرس سرویس ساب‌اسکریپشن پنل (از تنظیمات Subscription خود پنل سنایی بردار)
SANAEI_SUB_BASE_URL = os.getenv("SANAEI_SUB_BASE_URL", "")
SANAEI_SUB_PATH = os.getenv("SANAEI_SUB_PATH", "sub")

# آدرس/دامنه‌ای که کلاینت‌ها واقعاً برای اتصال (نه پنل ادمین) بهش وصل میشن.
# چون تو گذشته دیده شده IP/دامنه‌ی پنل ادمین با IP واقعی سروری که اینباند
# روش گوش میده فرق داره، این مقدار جداست. اگه خالی بمونه، از هاست همون
# SANAEI_URL استفاده میشه (فقط برای حالتی که هردو یکی‌ان).
SANAEI_CONNECT_HOST = os.getenv("SANAEI_CONNECT_HOST", "")

# ---------- پایگاه داده ----------
DB_PATH = os.getenv("DB_PATH", "bot_database.db")

# ---------- عضویت اجباری در کانال ----------
# اگه True باشه، کاربر قبل از استفاده از امکانات ربات باید عضو کانال زیر بشه
FORCE_JOIN_CHANNEL = os.getenv("FORCE_JOIN_CHANNEL", "true").lower() in ("1", "true", "yes")

# یوزرنیم کانال با @ (برای بررسی عضویت از طریق API لازمه)
REQUIRED_CHANNEL_USERNAME = os.getenv("REQUIRED_CHANNEL_USERNAME", "@NoordisVpn")

# لینک کانال (برای نمایش به کاربر و دکمه‌ی عضویت)
REQUIRED_CHANNEL_LINK = os.getenv("REQUIRED_CHANNEL_LINK", "https://t.me/NoordisVpn")

# ---------- تنظیمات نمایش لیست سرویس‌ها ----------
SERVICES_PAGE_SIZE = int(os.getenv("SERVICES_PAGE_SIZE", "5"))

# ---------- تیکت‌ها ----------
# تیکتی که پشتیبانی جوابش رو داده و کاربر بعدش چیزی ننوشته، بعد از این تعداد روز خودکار بسته میشه (۰ = خاموش)
TICKET_AUTO_CLOSE_DAYS = float(os.getenv("TICKET_AUTO_CLOSE_DAYS", "3"))

# ---------- سوالات متداول ----------
# عددها (تست رایگان، مهلت تمدید، بستن خودکار تیکت) از همون تنظیمات اصلی خونده میشن
_FAQ_TRIAL_MB = int(os.getenv("FREE_TRIAL_MB", "100"))
_FAQ_TRIAL_DAYS = int(os.getenv("FREE_TRIAL_DAYS", "1"))
_FAQ_GRACE_TIME = float(os.getenv("GRACE_DAYS_TIME", "3"))
_FAQ_GRACE_DATA = float(os.getenv("GRACE_DAYS_DATA", "7"))

FAQ_ITEMS = [
    {
        "q": "چطور سرویس بخرم؟",
        "a": "از منوی «خرید سرویس»، لوکیشن، مدت و حجم موردنظرت رو انتخاب کن و پرداخت رو انجام بده "
             "(کارت‌به‌کارت یا کیف پول). بعد از تایید پرداخت، سرویس ساخته و برات ارسال میشه.",
    },
    {
        "q": "تست رایگان چیه و چطور می‌گیرمش؟",
        "a": f"هر کاربر یک‌بار می‌تونه برای امتحان سرعت و کیفیت، تست رایگان ({_FAQ_TRIAL_MB} مگابایت، "
             f"{_FAQ_TRIAL_DAYS} روزه) بگیره. از منوی اصلی روی «تست رایگان» بزن.",
    },
    {
        "q": "بعد از خرید چطور وصل بشم؟",
        "a": "از منوی «آموزش اتصال» دستگاهت رو انتخاب کن تا اپ مناسب و مراحل نصب رو ببینی. "
             "لینک اشتراکت رو هم از «سرویس‌های من» برداشت کن.",
    },
    {
        "q": "سرویسم وصل نمیشه، چی کار کنم؟",
        "a": "اول از «سرویس‌های من» مطمئن شو حجم یا زمان سرویس تموم نشده. بعد ساعت و تاریخ دستگاهت رو روی حالت "
             "خودکار بذار، اشتراک رو توی اپ آپدیت کن و یه سرور دیگه از لیست رو امتحان کن. "
             "اگه باز هم حل نشد، از بخش پشتیبانی تیکت ثبت کن.",
    },
    {
        "q": "چطور سرویسم رو تمدید کنم؟",
        "a": "از «سرویس‌های من» سرویس رو باز کن و «تمدید» رو بزن. لینک و کانفیگ قبلی همون می‌مونه و فقط لازمه "
             "اشتراک رو توی اپ یک‌بار آپدیت کنی. تمدید خودکار از کیف پول هم از همون صفحه قابل روشن‌کردنه.",
    },
    {
        "q": "اگه تمدید نکنم چی میشه؟",
        "a": f"سرویس غیرفعال میشه، ولی مهلت داری: تا {_FAQ_GRACE_TIME:g} روز بعد از اتمام زمان و تا "
             f"{_FAQ_GRACE_DATA:g} روز بعد از اتمام حجم می‌تونی تمدیدش کنی. بعد از این مهلت، سرویس برای همیشه حذف میشه.",
    },
    {
        "q": "کیف پول چطور شارژ میشه؟",
        "a": "از «کیف پول من» روی «افزایش موجودی» بزن و مبلغ رو انتخاب کن. موجودی کیف پول برای خرید و تمدید "
             "سرویس استفاده میشه.",
    },
    {
        "q": "تیکت‌ها چطور کار می‌کنن؟",
        "a": "تیکتت رو ثبت کن؛ جواب پشتیبانی همین‌جا برات ارسال میشه و وضعیتش رو از «تیکت‌های من» می‌بینی."
             + (f" اگه جواب بدیم و {TICKET_AUTO_CLOSE_DAYS:g} روز پیام جدیدی ننویسی، تیکت خودکار بسته میشه؛ "
                "هر وقت مشکلی بود، یه تیکت جدید ثبت کن." if TICKET_AUTO_CLOSE_DAYS > 0 else ""),
    },
    {
        "q": "تضمین پایداری خدمات به چه صورت است؟",
        "a": f"زیرساخت‌های {os.getenv('BRAND_NAME_FA', 'نوردیس')} بر پایه‌ی ثبات و تداوم بنا شدن. "
             "اصالت ما، بزرگ‌ترین تضمین برای امنیت و استمرار دسترسی شماست.",
    },
    {
        "q": "امنیت و حریم خصوصی چطور تامین میشه؟",
        "a": "خط قرمز ما، حفاظت از هویت و داده‌های کاربرانه؛ با استانداردهایی فراتر از انتظار.",
    },
    {
        "q": "کیفیت نهایی سرویس چطوره؟",
        "a": "ما تنها یک ارائه‌دهنده نیستیم؛ مرجع کیفیت در این حوزه هستیم و مدام روی سرعت و پایداری کار می‌کنیم.",
    },
]

# ---------- پرداخت کریپتو (xRocket) ----------
# روشن/خاموش کردن دکمه‌ی مستقل «کارت به کارت» (تایید دستی توسط ادمین) تو منوهای
# خرید/تمدید/شارژ کیف پول. این کاملاً جدا از دکمه‌ی «ارسال رسید پرداخت» داخل
# فاکتور AutoSMS ـه (که برای وقتیه که بعد از یک ساعت هنوز خودکار تایید نشده) -
# خاموش کردن این یکی، اون قابلیت پشتیبان رو خاموش نمی‌کنه.
MANUAL_CARD_PAYMENT_ENABLED = os.getenv("MANUAL_CARD_PAYMENT_ENABLED", "true").lower() in ("1", "true", "yes")

CRYPTO_PAYMENT_ENABLED = os.getenv("CRYPTO_PAYMENT_ENABLED", "false").lower() in ("1", "true", "yes")
XROCKET_API_KEY = os.getenv("XROCKET_API_KEY", "")
# سوییچ جداگانه از DEMO_MODE کلی؛ یعنی می‌تونی کریپتو رو با کلید واقعی تست کنی
# حتی وقتی هنوز مرزبان (DEMO_MODE اصلی) روی حالت آزمایشی مونده
XROCKET_DEMO_MODE = os.getenv("XROCKET_DEMO_MODE", "true").lower() in ("1", "true", "yes")

# ارزهایی که برای انتخاب کاربر نمایش داده میشه + نرخ تبدیل هر کدوم به تومان
# این نرخ‌ها رو باید خودت دستی و مرتب آپدیت کنی، نرخ لحظه‌ای واقعی نیستن
CRYPTO_CURRENCIES = ["TONCOIN", "USDT", "TRX"]
# اسمی که به کاربر نشون داده میشه (جدا از کد واقعی که به API فرستاده میشه)
CRYPTO_CURRENCY_LABELS = {
    "TONCOIN": "GRAM",
    "USDT": "USDT",
    "TRX": "TRX",
}
CRYPTO_CURRENCY_STYLES = {
    "TONCOIN": "primary",
    "USDT": "success",
    "TRX": "danger",
}
CRYPTO_RATES_TOMAN = {
    "TONCOIN": int(os.getenv("TOMAN_PER_TONCOIN", "280000")),
    "USDT": int(os.getenv("TOMAN_PER_USDT", "70000")),
    "TRX": int(os.getenv("TOMAN_PER_TRX", "9000")),
}
# بعد از چند دقیقه، فاکتور پرداخت‌نشده منقضی در نظر گرفته بشه
CRYPTO_INVOICE_TIMEOUT_MINUTES = int(os.getenv("CRYPTO_INVOICE_TIMEOUT_MINUTES", "60"))

# ---------- پرداخت خودکار کارت‌به‌کارت (AutoSMS - تشخیص خودکار پیامک بانکی) ----------
# این کاملاً جدا از کارت‌به‌کارت دستیه (همون CARD_NUMBER/CARD_HOLDER که با آپلود
# رسید و تایید ادمین کار می‌کنه) - اون دست‌نخورده باقی می‌مونه.
AUTOSMS_ENABLED = os.getenv("AUTOSMS_ENABLED", "false").lower() in ("1", "true", "yes")
AUTOSMS_API_KEY = os.getenv("AUTOSMS_API_KEY", "")
# از پنل AutoSMS قابل مشاهده‌ست؛ برای تایید امضای وب‌هوک لازمه
AUTOSMS_WEBHOOK_SECRET = os.getenv("AUTOSMS_WEBHOOK_SECRET", "")
# آدرس عمومی خودِ همین سرور (همونی که MINIAPP_URL هم ازش می‌سازی)، بدون مسیر
# اضافه - مثلا https://your-app.onrender.com - برای ساخت callback_url وب‌هوک.
# اگه خالی بمونه، وب‌هوک آنی کار نمی‌کنه ولی بررسی خودکار/دستی پرداخت (polling)
# همچنان به‌درستی کار می‌کنه.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
AUTOSMS_INVOICE_TTL_MINUTES = int(os.getenv("AUTOSMS_INVOICE_TTL_MINUTES", "60"))
AUTOSMS_MIN_AMOUNT_TOMAN = 10_000
AUTOSMS_MAX_AMOUNT_TOMAN = 50_000_000

# ---------- پرداخت TonPays (فاکتور هاست‌شده - کارت‌به‌کارت خودکار) ----------
# کاملاً مستقل از AutoSMS/کریپتو/کارت‌به‌کارت دستی؛ خاموش‌کردن این‌ها روی هم اثر نمی‌ذاره.
# دکمه‌ی «باشگاه مشتریان» فعلاً از منوی اصلی مخفیه (تصمیم مدیر، نه حذف کامل
# قابلیت) - جاش تو منو با «نمایندگی فروش» پر شده. کل قابلیت باشگاه مشتریان
# (صفحه، امتیازات، جدول رتبه‌بندی) دست‌نخورده باقی مونده؛ هر وقت خواستی
# برگرده تو منو، همینو true کن.
LOYALTY_CLUB_MENU_BUTTON_ENABLED = os.getenv("LOYALTY_CLUB_MENU_BUTTON_ENABLED", "false").lower() in ("1", "true", "yes")

TONPAYS_ENABLED = os.getenv("TONPAYS_ENABLED", "false").lower() in ("1", "true", "yes")
# از منوی بات TonPays، گزینه‌ی «مستندات API» قابل دریافته
TONPAYS_API_KEY = os.getenv("TONPAYS_API_KEY", "")
# بعد از این‌همه دقیقه، فاکتور پرداخت‌نشده منقضی در نظر گرفته میشه (فقط برای
# نمایش/جاب دوره‌ای؛ خود TonPays هم ممکنه مستقل زودتر منقضیش کنه)
TONPAYS_INVOICE_TIMEOUT_MINUTES = int(os.getenv("TONPAYS_INVOICE_TIMEOUT_MINUTES", "60"))

# ---------- پرداخت ویناپی (WinaPay) - درگاه واسط با مرچنت‌آیدی ----------
# مستندات: https://winapay.io/public/document
# کاملاً مستقل از بقیه‌ی درگاه‌ها. مرچنت‌آیدی رو از «درگاه‌های من» تو پنل ویناپی بردار.
# حتماً آدرس PUBLIC_BASE_URL (دامنه‌ی سرور) باید با آدرس ثبت‌شده برای درگاه تو پنل ویناپی
# یکی باشه، وگرنه ویناپی خطای -10 میده. اگه ویناپی IP سرور رو هم محدود کرده، IP سرور رو
# تو پنل‌شون ثبت کن (خطای -9).
WINAPAY_MERCHANT_ID = os.getenv("WINAPAY_MERCHANT_ID", "").strip()
WINAPAY_ENABLED = bool(WINAPAY_MERCHANT_ID) and os.getenv("WINAPAY_ENABLED", "true").lower() in ("1", "true", "yes")
# بعد از این‌همه دقیقه، فاکتور پرداخت‌نشده منقضی در نظر گرفته میشه
WINAPAY_INVOICE_TIMEOUT_MINUTES = int(os.getenv("WINAPAY_INVOICE_TIMEOUT_MINUTES", "30"))

# ---------- امنیت / محدودسازی نرخ درخواست (ضدِ اسپم و DoS) ----------
# اگه Mini App/وب‌هوک‌ها پشت Cloudflare یا یه ریورس‌پروکسی (nginx و مثل اون)
# هستن، این رو true کن تا IP واقعی کاربر از هدر CF-Connecting-IP یا
# X-Forwarded-For خونده بشه؛ وگرنه (دسترسی مستقیم بدون پروکسی به این سرور)
# حتماً false نگه‌دار، چون هرکسی می‌تونه این هدرها رو جعل کنه و محدودیت رو دور بزنه.
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "false").lower() in ("1", "true", "yes")
# سقف کلی درخواست هر IP در دقیقه، روی کل API مینی‌اپ (لایه‌ی اول - جلوی فلاد عمومی)
API_RATE_LIMIT_PER_MIN = int(os.getenv("API_RATE_LIMIT_PER_MIN", "90"))
# سقف درخواست‌های POST (ساخت سفارش/فاکتور، آپلود رسید، انتقال کیف‌پول و...) -
# این‌ها گرون‌ترن، برای همین سقفشون جداگونه و سخت‌گیرانه‌تره؛ تا حد امکان بر
# اساس خودِ کاربر تلگرام سنجیده میشه نه IP (چون چند کاربر می‌تونن پشت یه IP باشن)
POST_RATE_LIMIT_PER_MIN = int(os.getenv("POST_RATE_LIMIT_PER_MIN", "20"))
# سقف درخواست به وب‌هوک‌های درگاه‌های پرداخت در دقیقه - این آدرس‌ها فقط باید
# از سمت سرور خودِ درگاه (AutoSMS/TonPays) صدا زده بشن، نه کاربر عادی
WEBHOOK_RATE_LIMIT_PER_MIN = int(os.getenv("WEBHOOK_RATE_LIMIT_PER_MIN", "60"))
# حداکثر حجم مجاز بدنه‌ی هر درخواست به مینی‌اپ (بایت) - جلوی حمله‌ی «بدنه‌ی غول‌پیکر»
MAX_REQUEST_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(10 * 1024 * 1024)))  # 10 مگابایت

# سقف تعداد «اکشن» (پیام/دکمه) هر کاربر تلگرام در بات، در این‌همه ثانیه -
# جلوی اسپم‌کلیک/فلاد از داخل خودِ چت بات (جدا و مستقل از محدودیت‌های بالا که فقط مینی‌اپ/وب‌هوک رو پوشش میدن)
BOT_ACTION_LIMIT = int(os.getenv("BOT_ACTION_LIMIT", "15"))
BOT_ACTION_WINDOW_SECONDS = int(os.getenv("BOT_ACTION_WINDOW_SECONDS", "10"))
# سقف سخت‌گیرانه‌تر و جداگونه برای اکشن‌های «گرون» که با پنل VPN یا درگاه پرداخت
# بیرونی حرف می‌زنن (ساخت/تمدید سرویس، ساخت فاکتور، انتقال کیف‌پول، کد تخفیف)
BOT_HEAVY_ACTION_LIMIT = int(os.getenv("BOT_HEAVY_ACTION_LIMIT", "6"))
BOT_HEAVY_ACTION_WINDOW_SECONDS = int(os.getenv("BOT_HEAVY_ACTION_WINDOW_SECONDS", "60"))

# ---------- تست رایگان ----------
FREE_TRIAL_DAYS = int(os.getenv("FREE_TRIAL_DAYS", "1"))
# حجم تست رایگان بر حسب مگابایت (برای نمایش به کاربر)
FREE_TRIAL_MB = int(os.getenv("FREE_TRIAL_MB", "100"))
# همون حجم، تبدیل‌شده به گیگابایت (اعشاری) چون توابع پنل gb می‌گیرن
FREE_TRIAL_GB = FREE_TRIAL_MB / 1024

# ---------- هشدار اتمام حجم/انقضا ----------
# وقتی مصرف به این درصد از سقف حجم رسید، یه پیام هشدار (با دکمه‌ی تمدید)
# یه‌بار برای کاربر فرستاده میشه - قبل از این‌که کامل تموم بشه و قطع بشه
DATA_WARNING_THRESHOLD_PERCENT = int(os.getenv("DATA_WARNING_THRESHOLD_PERCENT", "80"))
# وقتی این‌قدر روز به پایان اعتبار سرویس مونده، یه پیام هشدار (با دکمه‌ی
# تمدید) یه‌بار برای کاربر فرستاده میشه
EXPIRY_WARNING_DAYS_BEFORE = int(os.getenv("EXPIRY_WARNING_DAYS_BEFORE", "1"))

# ---------- چرخه‌ی عمر سرویس بعد از پایان (مهلت تمدید) ----------
# وقتی سرویسی تموم میشه (زمان یا حجم) و تمدید نمیشه، فوراً حذف نمیشه؛ یه مهلت
# داره که توش با همون لینک و کانفیگ قبلی قابل تمدیده. بعد از مهلت، کامل حذف میشه.
# (سرویس‌های «تست رایگان» مهلت ندارن و مثل قبل سر موعد حذف میشن.)
GRACE_DAYS_TIME = float(os.getenv("GRACE_DAYS_TIME", "3"))    # پایان به‌خاطر اتمام زمان
GRACE_DAYS_DATA = float(os.getenv("GRACE_DAYS_DATA", "7"))    # پایان به‌خاطر اتمام حجم
# این‌قدر ساعت مونده به حذف، یه «هشدار نهایی» (یه‌بار) فرستاده میشه
FINAL_WARNING_HOURS = float(os.getenv("FINAL_WARNING_HOURS", "24"))
# کد تخفیف شخصی و یک‌بارمصرفی که لحظه‌ی حذف سرویس برای کاربر ساخته میشه (برای برگشتنش)
WINBACK_ENABLED = os.getenv("WINBACK_ENABLED", "true").lower() in ("1", "true", "yes")
WINBACK_PERCENT = int(os.getenv("WINBACK_PERCENT", "15"))
WINBACK_HOURS = int(os.getenv("WINBACK_HOURS", "48"))

# خلاصه‌ی هفتگی مصرف (هر جمعه ~۱۱ صبح به وقت ایران برای کاربرای دارای سرویس پولی)
WEEKLY_SUMMARY_ENABLED = os.getenv("WEEKLY_SUMMARY_ENABLED", "true").lower() in ("1", "true", "yes")

# گزارش صبحگاهی برای ادمین‌ها (هر روز ساعت ۰۸:۰۰ تهران؛ خلاصه‌ی دیروز) - دستی هم با /report
ADMIN_REPORT_ENABLED = os.getenv("ADMIN_REPORT_ENABLED", "true").lower() in ("1", "true", "yes")

# «پیام غنی» تلگرام (جدول، بخش جمع‌شونده و ...؛ Bot API 10.1+). تا وقتی با /richtest روی بات خودت تایید نشده، خاموش بمونه.
RICH_MESSAGES_ENABLED = os.getenv("RICH_MESSAGES_ENABLED", "false").lower() in ("1", "true", "yes")

# ---------- پاداش روزانه‌ی مینی‌اپ (زنجیره‌ی روزهای پشت‌سرهم) ----------
# هر روز (به وقت ایران) کاربر یه‌بار «دریافت امروز» رو می‌زنه و زنجیره‌ش یکی زیاد میشه؛ اگه یه روز رو
# جا بندازه از اول شروع میشه. جایزه‌ی مایل‌استون‌ها «کد تخفیف شخصی، یک‌بارمصرف» ـه (نه اعتبار کیف پول،
# چون کیف پول قابل انتقال بین کاربراست و با ساخت چند حساب سوءاستفاده‌پذیر میشد).
DAILY_CHECKIN_ENABLED = os.getenv("DAILY_CHECKIN_ENABLED", "true").lower() in ("1", "true", "yes")
STREAK_MILESTONES = [(3, 3), (7, 5), (14, 8), (30, 10)]    # (روز پشت‌سرهم، درصد تخفیف)؛ بعد از ۳۰، هر ۳۰ روز یه‌بار تکرار میشه
STREAK_CODE_HOURS = int(os.getenv("STREAK_CODE_HOURS", "168"))                    # اعتبار کد جایزه (پیش‌فرض ۷ روز)
STREAK_REWARD_COOLDOWN_DAYS = int(os.getenv("STREAK_REWARD_COOLDOWN_DAYS", "14"))  # حداقل فاصله‌ی گرفتن «همون» جایزه‌ی مایل‌استون برای بار دوم (جلوی شکستن و دوباره شروع‌کردن برای جایزه‌گرفتن)

# ---------- زیرمجموعه‌گیری (رفرال) ----------
# مبلغی که به کیف پول کاربر معرف اضافه میشه، وقتی زیرمجموعه‌اش اولین خریدش رو انجام بده
REFERRAL_BONUS_TOMAN = int(os.getenv("REFERRAL_BONUS_TOMAN", "20000"))

# مبلغی که فوراً (فقط با عضو شدن زیرمجموعه، حتی بدون خرید) به کیف پول معرف اضافه میشه
REFERRAL_SIGNUP_BONUS_TOMAN = int(os.getenv("REFERRAL_SIGNUP_BONUS_TOMAN", "5000"))

# ---------- باشگاه مشتریان (سطح‌بندی بر اساس مجموع خرید کل‌عمر) ----------
# هر کاربر بر اساس مجموع مبلغ خریدهای تاییدشده‌ش (خرید+تمدید) وارد بالاترین
# سطحی میشه که به min_spent‌ـش رسیده باشه. اولین روز هر ماه، مبلغ
# monthly_bonus همون سطح خودکار به کیف پولش شارژ میشه.
# این عددها پیش‌فرض پیشنهادی‌ان؛ هر موقع خواستی می‌تونی از طریق Secrets/.env
# بدون تغییر کد تنظیمشون کنی، یا این لیست رو مستقیم دستی ویرایش کنی.
LOYALTY_TIERS = [
    {"name": "برنزی", "emoji": "🥉", "min_spent": 1_000_000, "monthly_bonus": 5_000},
    {"name": "نقره‌ای", "emoji": "🥈", "min_spent": 3_000_000, "monthly_bonus": 15_000},
    {"name": "طلایی", "emoji": "🥇", "min_spent": 6_000_000, "monthly_bonus": 30_000},
    {"name": "الماسی", "emoji": "💎", "min_spent": 10_000_000, "monthly_bonus": 50_000},
]

# ---------- نمایندگی (Reseller) ----------
# کاربری که مجموعاً این مبلغ رو به کیف پولش شارژ کرده باشه (نه لزوماً خرج
# کرده باشه)، واجد شرایط درخواست نمایندگیه. تایید نهایی همیشه با ادمینه.
RESELLER_MIN_TOPUP_TOMAN = int(os.getenv("RESELLER_MIN_TOPUP_TOMAN", "5000000"))
# قیمت هر گیگ برای نماینده‌های تاییدشده (به‌جای قیمت عادی هر پلن)
RESELLER_PRICE_PER_GB_TOMAN = int(os.getenv("RESELLER_PRICE_PER_GB_TOMAN", "5000"))

# ---------- پلن‌های فروش ----------
# هر پلن، حجم + مدت + قیمت هر گیگ مخصوص به خودش رو داره (دیگه یک قیمت واحد
# برای کل ربات نیست). لوکیشن هم اختیاریه؛ فقط جایی که مقدار داشته باشه
# تو عنوان پلن نمایش داده میشه.
PREMIUM_LOCATION_NAME = "پریمیوم آلمان"   # اسم نمایشیِ تنها لوکیشن فعلی (بات و مینی‌اپ و عنوان پلن‌ها)

# قیمت هر گیگ برای همه‌ی پلن‌ها یکسانه؛ هر مدت (۱/۲/۳ ماهه) نردبان حجم مخصوص خودش رو داره.
# نکته: id هر پلن از مدت و حجم ساخته میشه (مثلاً 1m_10gb)؛ پلن‌های قبلی (1m_5gb ،1m_10gb ،2m_20gb ،
# 2m_30gb ،3m_50gb) باید همین‌جا بمونن چون سرویس‌های فعال و تمدید خودکارشون بهشون وصله.
_PRICE_PER_GB = 8000
PRICE_PER_GB_TOMAN = _PRICE_PER_GB   # برای متن‌های توضیحیِ بات و مینی‌اپ (قیمت هر گیگ)
_LADDER = {
    1: (5, 10, 15, 20, 30, 50),
    2: (10, 20, 30, 50, 75, 100),
    3: (20, 30, 50, 100, 150, 200),   # پلن ۱۰ گیگِ سه‌ماهه حذف شده
}
PLAN_DEFS = [
    {"months": months, "gb": gb, "price_per_gb": _PRICE_PER_GB, "location": "آلمان"}
    for months, sizes in _LADDER.items()
    for gb in sizes
]

# مدت‌های قابل‌فروش (ماه) و معادل روزشون - این‌ها بر اساس PLAN_DEFS بالا
# به‌صورت خودکار محاسبه میشن، نیازی به دستکاری دستی نیست
DURATION_MONTHS = sorted({d["months"] for d in PLAN_DEFS})
DURATION_DAYS = {1: 30, 2: 60, 3: 90, 6: 180}
DURATION_LABELS = {1: "۱ ماهه", 2: "۲ ماهه", 3: "۳ ماهه", 6: "۶ ماهه"}
# ایموجی معمولی توی هیچ‌جای پلن‌ها استفاده نمیشه؛ هر مدت الماس پریمیوم خودش رو داره
# (تگ داخل متن: plan["emoji_tag"]، آیدی روی دکمه: keyboards.get_plan_icon) و رنگ دکمه‌ی خودش:
# ۱ ماهه آبی، ۲ ماهه سبز، ۳ ماهه قرمز (keyboards.get_plan_style).


def _round_price(price: float) -> int:
    """رند کردن قیمت به نزدیک‌ترین ۱۰۰۰ تومان برای زیبایی عدد"""
    return int(round(price / 1000.0)) * 1000


def _build_plans():
    plans = []
    for d in PLAN_DEFS:
        months = d["months"]
        gb = d["gb"]
        location = d.get("location")
        price = _round_price(gb * d["price_per_gb"])

        title = f"{DURATION_LABELS[months]} - {gb} گیگ"
        if location:
            title += f" | {PREMIUM_LOCATION_NAME}"

        plans.append(
            {
                "id": f"{months}m_{gb}gb",
                "emoji": "",   # ایموجی معمولی نداریم؛ برای داخل متن HTML از emoji_tag استفاده کن
                "emoji_tag": _pe.PLAN_TAG.get(f"GEM_{months}", ""),
                "title": title,
                "days": DURATION_DAYS[months],
                "gb": gb,
                "price": price,
                "reseller_price": _round_price(gb * RESELLER_PRICE_PER_GB_TOMAN),
                "duration_months": months,
                "location": location,
                "is_unlimited": False,
            }
        )

    return plans


PLANS = _build_plans()


def get_plan(plan_id: str):
    for p in PLANS:
        if p["id"] == plan_id:
            return p
    return None


def get_plans_for_duration(months: int):
    return [p for p in PLANS if p.get("duration_months") == months]



# ---------- راهنمای اتصال به تفکیک سیستم‌عامل (برای بخش آموزش) ----------
def _L(text: str) -> str:
    """
    عبارت انگلیسیِ «ایزوله» (LRI..PDI) تا وسط جمله‌ی فارسی جاش عوض نشه (مثل «Subscription group setting»).
    موقع نمایش (بات/مینی‌اپ) همین عبارت‌ها خودکار پررنگ میشن.
    """
    return f"\u2066{text}\u2069"


_FAQ_COMMON = [
    (
        "اگه وصل نشد چی کار کنم؟",
        f"ساعت و تاریخ دستگاهت باید درست و روی حالت خودکار باشه. اشتراک رو یک‌بار آپدیت کن ({_L('Update subscription')}) "
        "و اگه باز هم وصل نشد، یه سرور دیگه از لیست رو امتحان کن.",
        None,
    ),
    (
        "بعد از تمدید چی کار کنم؟",
        "لینک و تنظیماتت عوض نمیشه؛ فقط اشتراک رو توی اپ یک‌بار آپدیت کن.",
        None,
    ),
]

_LINK_STEP = "لینک اشتراک سرویست رو از «سرویس‌های من» همین بات کپی کن."

# راهنمای اتصال به تفکیک سیستم‌عامل (برای بخش آموزش بات و مینی‌اپ).
# link: اندروید/دسکتاپ = صفحه‌ی آخرین نسخه‌ی پایدار روی GitHub (releases/latest)، iOS = App Store.
# files: [(شرط، اسم فایل)] از راهنمای رسمی فایل‌های خود پروژه‌ها (بدون شماره‌ی نسخه تا کهنه نشه).
# faq: [(عنوان، متن، کد اختیاری)] که تو بات به‌صورت بخش جمع‌شونده نمایش داده میشه.
PLATFORM_GUIDES = {
    "android": {
        "label": "اندروید",
        "app_name": "v2rayNG",
        "note": "رایگان و متن‌باز",
        "req": None,
        "link": "https://github.com/2dust/v2rayNG/releases/latest",
        "download_label": "دانلود v2rayNG (GitHub)",
        "files": [
            ("بیشتر گوشی‌ها", "v2rayNG_…_arm64-v8a.apk"),
            ("مطمئن نیستی یا نصب نشد", "v2rayNG_…_universal.apk"),
        ],
        "files_note": "فایل‌هایی که fdroid توی اسمشون دارن لازم نیست.",
        "steps": [
            f"روی دکمه‌ی دانلود بزن، فایل مناسب (جدول بالا) رو از بخش {_L('Assets')} بگیر و نصبش کن.",
            _LINK_STEP,
            f"تو {_L('v2rayNG')} منوی ☰ رو باز کن، {_L('Subscription group setting')} رو بزن، با + یه اشتراک بساز، "
            f"لینک رو توی فیلد {_L('URL')} پیست کن و ✓ رو بزن.",
            f"برگرد به صفحه‌ی اصلی و از منوی ⋮ گزینه‌ی {_L('Update subscription')} رو بزن.",
            "یه سرور انتخاب کن و دکمه‌ی ▶ رو بزن؛ اگه اندروید اجازه‌ی VPN خواست، تایید کن.",
        ],
        "faq": [
            (
                "اندروید اجازه‌ی نصب نمیده؟",
                "اندروید برای نصب فایل APK اجازه‌ی «نصب از این منبع» می‌خواد؛ همون رو فعال کن و نصب رو دوباره بزن.",
                None,
            ),
        ] + _FAQ_COMMON,
    },
    "ios": {
        "label": "آیفون / آیپد",
        "app_name": "Streisand",
        "note": "رایگان",
        "req": "iOS 14 و بالاتر",
        "link": "https://apps.apple.com/app/streisand/id6450534064",
        "download_label": "دانلود Streisand (App Store)",
        "files": [],
        "files_note": "برای آیفون فایل جداگانه‌ای نیست؛ اپ مستقیم از App Store نصب میشه.",
        "steps": [
            f"روی دکمه‌ی دانلود بزن و {_L('Streisand')} رو از App Store نصب کن.",
            _LINK_STEP,
            f"تو {_L('Streisand')} روی + بزن، گزینه‌ی افزودن اشتراک ({_L('Subscription')}) رو انتخاب کن و لینک رو پیست کن.",
            "یه سرور انتخاب کن، دکمه‌ی اتصال رو بزن و وقتی iOS اجازه‌ی افزودن VPN خواست، تایید کن.",
        ],
        "faq": list(_FAQ_COMMON),
    },
    "windows": {
        "label": "ویندوز",
        "app_name": "v2rayN",
        "note": "رایگان و متن‌باز",
        "req": "ویندوز ۱۰ و بالاتر",
        "link": "https://github.com/2dust/v2rayN/releases/latest",
        "download_label": "دانلود v2rayN (GitHub)",
        "files": [
            ("ویندوز معمولی (۶۴ بیتی)", "v2rayN-windows-64.zip"),
            ("ویندوز روی پردازنده‌ی ARM", "v2rayN-windows-arm64.zip"),
        ],
        "files_note": "نسخه‌ی desktop لازم نیست.",
        "steps": [
            f"روی دکمه‌ی دانلود بزن، فایل مناسب (جدول بالا) رو از بخش {_L('Assets')} بگیر و کامل Extract کن.",
            f"فایل {_L('v2rayN.exe')} رو اجرا کن.",
            _LINK_STEP,
            f"از منوی {_L('Subscription group')} گزینه‌ی {_L('Subscription group setting')} رو بزن، با {_L('Add')} یه اشتراک بساز "
            f"و لینک رو توی {_L('URL')} پیست کن.",
            f"دوباره از منوی {_L('Subscription group')} یکی از گزینه‌های {_L('Update subscription')} رو بزن.",
            f"یه سرور رو انتخاب کن (دابل‌کلیک)، بعد روی آیکون کنار ساعت راست‌کلیک کن و از {_L('System proxy')} "
            f"گزینه‌ی {_L('Set system proxy')} رو بزن.",
        ],
        "faq": [
            (
                "ویندوز هشدار امنیتی داد؟",
                f"روی {_L('More info')} و بعد {_L('Run anyway')} بزن. برنامه‌ی متن‌بازه و ما لینک رسمی GitHub رو گذاشتیم.",
                None,
            ),
        ] + _FAQ_COMMON,
    },
    "mac": {
        "label": "مک",
        "app_name": "v2rayN",
        "note": "رایگان و متن‌باز",
        "req": "macOS 12 و بالاتر",
        "link": "https://github.com/2dust/v2rayN/releases/latest",
        "download_label": "دانلود v2rayN (GitHub)",
        "files": [
            ("مک M1 و جدیدتر (اپل سیلیکون)", "v2rayN-macos-arm64.dmg"),
            ("مک اینتل", "v2rayN-macos-64.dmg"),
        ],
        "files_note": f"نوع پردازنده‌ات رو از منوی Apple بالا-چپ و {_L('About This Mac')} ببین.",
        "steps": [
            f"روی دکمه‌ی دانلود بزن، فایل مناسب (جدول بالا) رو از بخش {_L('Assets')} بگیر، باز کن و v2rayN رو بکش توی {_L('Applications')}.",
            f"{_L('v2rayN')} رو اجرا کن؛ اگه گفت «damaged»، راه‌حلش پایین توی «سوال‌های رایج» هست.",
            _LINK_STEP,
            f"از منوی {_L('Subscription group')} گزینه‌ی {_L('Subscription group setting')} رو بزن، با {_L('Add')} یه اشتراک بساز "
            f"و لینک رو توی {_L('URL')} پیست کن.",
            f"دوباره از منوی {_L('Subscription group')} یکی از گزینه‌های {_L('Update subscription')} رو بزن.",
            f"یه سرور انتخاب کن، بعد از آیکون v2rayN بالای صفحه، {_L('System proxy')} و سپس {_L('Set system proxy')} رو بزن.",
        ],
        "faq": [
            (
                "پیام «damaged» اومد؟",
                "چون اپ امضای اپل نداره این پیام میاد و خرابی نیست. Terminal رو باز کن، این دستور رو بزن و دوباره اپ رو باز کن:",
                "xattr -cr /Applications/v2rayN.app",
            ),
        ] + _FAQ_COMMON,
    },
    "linux": {
        "label": "لینوکس",
        "app_name": "v2rayN",
        "note": "رایگان و متن‌باز",
        "req": "Debian 12+ ، Ubuntu 22.04+ ، Fedora 36+",
        "link": "https://github.com/2dust/v2rayN/releases/latest",
        "download_label": "دانلود v2rayN (GitHub)",
        "files": [
            ("Debian / Ubuntu", "v2rayN-linux-64.deb"),
            ("Fedora / RedHat", "فایل rpm (اسمش rhel داره)"),
            ("بدون نصب (همه‌ی توزیع‌ها)", "v2rayN-linux-64.zip"),
        ],
        "files_note": "برای پردازنده‌ی ARM به‌جای 64 از نسخه‌ی arm64 استفاده کن.",
        "steps": [
            f"روی دکمه‌ی دانلود بزن، فایل مناسب توزیعت (جدول بالا) رو از بخش {_L('Assets')} بگیر و طبق «نصب با ترمینال» نصب کن.",
            _LINK_STEP,
            f"از منوی {_L('Subscription group')} گزینه‌ی {_L('Subscription group setting')} رو بزن، با {_L('Add')} یه اشتراک بساز "
            f"و لینک رو توی {_L('URL')} پیست کن.",
            f"دوباره از منوی {_L('Subscription group')} یکی از گزینه‌های {_L('Update subscription')} رو بزن.",
            "یه سرور رو انتخاب کن تا فعال بشه.",
            f"اگه دسکتاپت پروکسی رو خودکار قبول نمی‌کنه، پروکسی سیستم رو روی آدرس {_L('127.0.0.1')} و پورتی که v2rayN نشون میده بذار.",
        ],
        "faq": [
            (
                "نصب با ترمینال",
                "دستور اول برای deb، دوم برای rpm و سومی برای نسخه‌ی zip (بعد از Extract) هست:",
                "sudo apt install -y ./v2rayN-linux-64.deb\nsudo dnf install -y ./<rpm-file>\nchmod +x v2rayN && ./v2rayN",
            ),
        ] + _FAQ_COMMON,
    },
}
