"""
ایموجی‌های پرمیوم متحرک (Premium Custom Emoji) تلگرام.

دو جور کاربرد داره:
1. داخل متن پیام (message text) با تگ HTML <tg-emoji> - نیازمند parse_mode="HTML"
2. روی دکمه‌های شیشه‌ای (Inline Keyboard) با پارامتر icon_custom_emoji_id -
   این قابلیت از نسخه‌ی Bot API 9.4 و کتابخانه‌ی python-telegram-bot>=22.7 اضافه شده.

⚠️ شرط استفاده روی دکمه‌ها: طبق مستندات تلگرام، این فقط زمانی کار می‌کنه که
مالک ربات اشتراک تلگرام پرمیوم فعال داشته باشه.

⚠️ نکته‌ی امنیتی: تگ‌های HTML (بخش ۱) فقط باید کنار متنی استفاده بشن که
مستقیم از کاربر نیومده باشه (یا با تابع esc() پاک‌سازی شده باشه).
"""
import html

# ---------------------------------------------------------------------------
# دسته‌ی اول - همیشه در حال استفاده در سراسر ربات
# ---------------------------------------------------------------------------
_DATA = {
    "CARD": ("5447453226498552490", "💳"),        # پرداخت / شماره کارت
    "SUPPORT": ("5447510826304959724", "💬"),      # پشتیبانی
    "PRICE": ("5444860552310457690", "💰"),        # قیمت
    "CONFIRM": ("5444987348334965906", "✅"),      # تایید
    "REJECT": ("5445092669522996408", "❌"),       # رد یا هشدار
    "CONNECTION": ("5445326466067754897", "🌐"),   # اتصال
    "REMAINING": ("4904626998745237074", "🔋"),    # مقدار باقی‌مانده اشتراک
    "LOCATION": ("5104989658350093220", "📍"),     # لوکیشن
    "LINK": ("4916086774649848789", "🔗"),         # لینک
    "UNLIMITED": ("5116512467194741904", "👾"),    # بی‌نهایت / نامحدود
    "UP": ("5445307250384075361", "🔼"),           # بالا (افزایش)
    "DOWN": ("5445358884480916784", "🔽"),         # پایین (کاهش)
    "TRIAL": ("5445104308884370368", "🖥"),        # تست رایگان
    "WALLET": ("5444960062407732826", "👛"),       # کیف پول
    "MY_SERVICES": ("5444924349754667822", "💼"),  # سرویس‌های من
    "ACCOUNT": ("5445372439397691719", "🫂"),      # حساب کاربری
    "REFERRAL": ("5447311106030726740", "👨‍🦰"),      # زیرمجموعه‌گیری
    "APPS": ("5447611706496808621", "⚙️"),         # دانلود و آموزش اپلیکیشن‌ها
    # --- دسته‌ی دوم (بچ جدید) - فقط اونایی که جای مشخصی تو ربات پیدا کردن ---
    "BACK": ("5447434637880098257", "🚪"),         # بازگشت / انصراف
    "MENU": ("5445362436418859744", "↩️"),         # بازگشت به منوی اصلی
    "CHARGE": ("5447579253723918909", "💲"),       # شارژ کیف پول / تمدید سرویس
    "VIP": ("5990181503227663726", "🍦"),          # پلن VIP / نامحدود سه‌ماهه
    "CUP": ("5841517790166519917", "🏆"),          # پلن رده‌ی طلایی
    "STAR": ("5444939047132755535", "⭐️"),         # پلن رده‌ی نقره‌ای
    "FIRE": ("5384404296299196920", "🔥"),         # پلن پرطرفدار / ورودی
    "TWO_PEOPLE": ("5447311106030726740", "👨‍🦰"),   # تعداد زیرمجموعه‌ها
    "LOCK": ("5258476306152038031", "🔒"),         # قفل بودن دسترسی (عضویت اجباری)
    "CALENDAR": ("5258105663359294787", "🗓"),     # تاریخ انقضا
    "CART": ("5445146945024720188", "🛒"),         # خرید سرویس جدید
    "ENTER_APP": ("5445408306669582934", "▶️"),     # ورود به برنامه (باز کردن مینی‌اپ)
    "ANDROID": ("5841282245570074279", "🤖"),      # پلتفرم اندروید
    "WINDOWS": ("5841343066601951177", "🔥"),      # پلتفرم ویندوز
    "APPLE": ("5841300864253301504", "🍎"),        # پلتفرم مک/iOS
    "LINUX": ("5929096876321149063", "🖥"),         # پلتفرم لینوکس
    "FIRE_HOT": ("5336964037462737821", "🔥"),      # آتش خفن - هوک شروع پیام
    "ROCKET": ("5474253392928862097", "🚀"),        # موشک زیبا - سرعت/کیفیت
    "DIAMOND": ("5447507587899605348", "💎"),       # الماس زیبا - کیفیت پرمیوم
    "GAME_SERVICE": ("5278561828085977005", "🎮"),  # معرفی سرویس‌ها
    "GAME_CONTROLLER": ("5231316384671099257", "🎮"),  # ویژگی گیمینگ
    "CHECK2": ("5447242579827523388", "✔️"),        # چک‌مارک لیست ویژگی‌ها
    "MEGAPHONE": ("5339041401474662078", "📣"),     # اطلاعیه
    "CHAT": ("5447510826304959724", "💬"),          # پشتیبانی/گفتگو
    "FIXED_IP": ("5458811795793799381", "📍"),      # آی‌پی ثابت
    "DOWN_ARROW": ("5444961234933806330", "⬇️"),    # منوی پایین
    "WHEEL": ("5377521684221815300", "🛞"),         # سرعت بالا و پینگ پایین
    "WAVE": ("5325707675504222689", "👋"),          # سلام (به‌جای تیک)
    "MAP": ("5940396943866859681", "🗺"),           # آی‌پی ثابت (جایگزین جدید)
    "LIST": ("5444961234933806330", "⬇️"),          # دریافت کانفیگ‌ها (آیکون جدا از NOTES)
    "TRANSFER": ("5445365692004071819", "↪️"),      # انتقال سرویس به کاربر دیگر
    "TRASH": ("5445005936953424165", "🗑"),         # حذف کامل اکانت
    "GEM": ("5359719332542718652", "💎"),           # ارز GRAM
    "VERIFIED": ("5956111576367895555", "💸"),      # ارز USDT
    "LIGHTNING": ("5445388803223091254", "⚡️"),      # ارز TRX
    "QUESTION": ("5348551425435646741", "❓"),      # سوالات متداول
    "FOLDERS": ("5447282724886839705", "📂"),       # تیکت‌های من
    "CLOCK": ("5445350406215465190", "⏰"),         # تراکنش‌های من / تاریخچه
    "TOP": ("5348276504579031076", "🔝"),           # بروزرسانی و دریافت لینک جدید
    "HOURGLASS2": ("5278626308429991847", "⌛"),    # فعال‌سازی موقت سرویس
    "EYES": ("5220070652756635426", "👀"),          # وضعیت و راهنمای سرویس
    "NOTES": ("5444889156792646660", "📝"),          # یادداشت سرویس
    "DELETE": ("5445184667722477677", "🗑"),         # حذف کامل اکانت
    "RESELLER": ("5447420365703773550", "💼"),       # نمایندگی/همکاری (دست‌دادن)
    "BACK_TO_MENU": ("5445362436418859744", "↩️"),   # دکمه‌ی بزرگ بازگشت به منوی اصلی
    "TIER_MEDAL_1": ("5280735858926822987", "🥇"),   # سطح ۱ باشگاه مشتریان (برنزی)
    "TIER_MEDAL_2": ("5283195573812340110", "🥈"),   # سطح ۲ باشگاه مشتریان (نقره‌ای)
    "TIER_MEDAL_3": ("5282750778409233531", "🥉"),   # سطح ۳ باشگاه مشتریان (طلایی)
    "TIER_MEDAL_4": ("5444931419270839381", "🏅"),   # سطح ۴ باشگاه مشتریان (الماسی)
    # --- ایموجی‌های اختصاصیِ «منوی اصلی بات» (هم منوی inline هم منوی ثابت پایین صفحه) ---
    # جدا از کلیدهای بالا نگه داشته شدن تا جاهای دیگه‌ی بات (پیام‌ها، لیست‌ها) همون ایموجی‌های قبلی رو داشته باشن.
    "MENU_BUY": ("5445146945024720188", "🛒"),        # خرید سرویس
    "MENU_SERVICES": ("5444924349754667822", "💼"),   # سرویس‌های من
    "MENU_TRIAL": ("5445104308884370368", "🖥"),      # تست رایگان
    "MENU_ENTER_APP": ("5445408306669582934", "▶️"),  # ورود به مینی‌اپ
    "MENU_WALLET": ("5444960062407732826", "👛"),     # کیف پول
    "MENU_SUPPORT": ("5447510826304959724", "💬"),    # پشتیبانی
    "MENU_APPS": ("5447611706496808621", "⚙️"),       # آموزش اتصال
    "MENU_REFERRAL": ("5447311106030726740", "👨‍🦰"),   # زیرمجموعه‌گیری
    "MENU_ACCOUNT": ("5445372439397691719", "🫂"),    # حساب کاربری
    "MENU_RESELLER": ("5447420365703773550", "💼"),   # نمایندگی فروش
}

_NUM_DATA = {
    1: ("5141109049114232089", "1️⃣"),
    2: ("5140871649091912628", "2️⃣"),
    3: ("5141399818400170896", "3️⃣"),
    4: ("5138822752123225428", "4️⃣"),
    5: ("5141062672057369534", "5️⃣"),
    6: ("5139005588881015916", "6️⃣"),
    7: ("5140999557512954818", "7️⃣"),
    8: ("5141013683660391172", "8️⃣"),
    9: ("5141137309999039199", "9️⃣"),
}

# ---------------------------------------------------------------------------
# بانک کامل ایموجی‌های بچ دوم که فرستادی - اینجا فقط ذخیره‌ست، هنوز جایی وصل
# نشدن چون تو این ربات فروش VPN جای منطقی‌ای براشون پیدا نکردم (نهنگ، اسب،
# بستنی، زنگ تلفن، تقویم و ...). اگه بعدا بخش جدیدی به ربات اضافه شد که یکی
# از این‌ها بهش می‌خوره، از همینجا برمی‌دارم؛ نیازی نیست دوباره بفرستیشون.
# ---------------------------------------------------------------------------
EXTRA_RAW = {
    "diamond_1": "5843829032327582377",
    "play_store": "5843899937942671820",
    "settings": "5956053070323389566",
    "white_heart": "5384566663242854099",
    "trash_delete": "5258130763148172425",
    "screenshot_camera": "5258205968025525531",
    "game_controller": "5258508428212445001",
    "pin": "5258461531464539536",
    "hundred": "5222241728659988366",
    "exclaim": "5220197908342648622",
    "white_flag": "5397730656400714154",
    "hourglass": "5258113901106580375",
    "phone_call": "5453965363286925977",
    "blue_1": "5348427408254975270",
    "whale": "5350375974787630168",
    "star_pretty": "5348203150832583752",
    "horse_running": "5350287773339238562",
    "blue_2": "5348418874154957864",
    "punch_reject": "5348514879558926674",
    "warning": "5348402067947929537",
    "radio_button": "5987583288531751809",
    "anger": "5987841089648726931",
    "cheetah_running": "5990151760579139563",
    "sun": "5989945202716971999",
    "snow": "5987974070426146302",
    "battery_full": "5988017011509171250",
    "wave_hand": "5987570781586985273",
    "fire_extra": "5940568167033082016",
    "eyes_2": "5337185975602787411",
    "warning_2": "5420303617234062155",
    "warning_3": "5339526393476694676",
    "plus": "5400084109500366328",
    "cross_2": "5339200899380165703",
    "gear_2": "5278652945817158489",
    "upload": "5451800102769288376",
    "gift_2": "5384456888173739712",
    "card_2": "5449857261428045701",
    "shopping_bag": "5339230049323203551",
    "links": "5841171023096976223",
    "star_alt": "5841646175328932342",
    "unlimited_alt": "5348421451135336104",
    "crypto_globe": "6039709013090768335",   # 🌐 دکمه‌ی درگاه کریپتو
}


def _tag(emoji_id: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

# ---------------------------------------------------------------------------
# بانک ایموجی «بچ سوم» (۱۰۰ ایموجی پریمیوم): اسم‌ها با pk3_ شروع میشن و جلوی هر اسم ایموجی پایه‌ش نوشته شده.
# هرکدوم که تو بات استفاده شده، تو _DATA بالا هم با همون شناسه اومده؛ بقیه برای استفاده‌ی بعدی اینجا نگه داشته شدن.
# برای استفاده تو متن: bank_tag("pk3_...")  |  برای دکمه: EXTRA_RAW["pk3_..."]
# (۴۷ ایموجی آخرِ لیستی که فرستاده بودی شناسه نداشتن و فقط خود ایموجی بودن؛ بدون شناسه نمیشه پریمیومشون کرد.)
# ---------------------------------------------------------------------------
_BANK3 = [
    ("pk3_square_button", "5445385947069838800", "🔲"),
    ("pk3_phone_arrow_1", "5445059250382469069", "📲"),
    ("pk3_phone_arrow_2", "5445033158456145975", "📲"),
    ("pk3_globe_1", "5447602197439218445", "🌐"),
    ("pk3_arrow_left_1", "5447506720316225765", "⬅️"),
    ("pk3_arrow_right_1", "5445350109862720603", "➡️"),
    ("pk3_arrow_left_2", "5447389832781264371", "⬅️"),
    ("pk3_arrow_right_2", "5447181973544008180", "➡️"),
    ("pk3_folder_open", "5447282724886839705", "📂"),
    ("pk3_door", "5447434637880098257", "🚪"),
    ("pk3_arrow_down", "5444961234933806330", "⬇️"),
    ("pk3_folder_1", "5447389837076231920", "📁"),
    ("pk3_check_heavy_1", "5447242579827523388", "✔️"),
    ("pk3_check_green", "5444987348334965906", "✅"),
    ("pk3_check_box_1", "5445210909972655435", "☑️"),
    ("pk3_check_box_2", "5445163158526261598", "☑️"),
    ("pk3_plus", "5447224884562263112", "➕"),
    ("pk3_medal", "5444931419270839381", "🏅"),
    ("pk3_minus", "5447155993286832278", "➖"),
    ("pk3_play_1", "5444883062234053429", "▶️"),
    ("pk3_speech_1", "5445140257760639304", "💬"),
    ("pk3_check_heavy_2", "5445189224682779974", "✔️"),
    ("pk3_prohibited_1", "5447647474984449520", "🚫"),
    ("pk3_bolt", "5445388803223091254", "⚡️"),
    ("pk3_thumbs_up", "5447153029759397673", "👍"),
    ("pk3_thumbs_down", "5447128406711891434", "👎"),
    ("pk3_heart_1", "5444887644964159628", "❤️"),
    ("pk3_heart_2", "5444862970377040012", "❤️"),
    ("pk3_heart_broken", "5445053099989303899", "💔"),
    ("pk3_warning_1", "5447381715293074599", "⚠️"),
    ("pk3_warning_2", "5447592907424955482", "⚠️"),
    ("pk3_picture_1", "5447588260270341594", "🖼"),
    ("pk3_memo", "5444889156792646660", "📝"),
    ("pk3_headphones", "5445276884965291212", "🎧"),
    ("pk3_abc_caps", "5445137435967126342", "🔠"),
    ("pk3_arrows_lr", "5447554042265891906", "↔️"),
    ("pk3_arrows_ud", "5445088739627924307", "↕️"),
    ("pk3_arrow_hook", "5445365692004071819", "↪️"),
    ("pk3_trash_1", "5445005936953424165", "🗑"),
    ("pk3_trash_2", "5445184667722477677", "🗑"),
    ("pk3_triangle_down_1", "5445358884480916784", "🔽"),
    ("pk3_triangle_up", "5445307250384075361", "🔼"),
    ("pk3_triangle_down_2", "5447198504873129855", "🔽"),
    ("pk3_coin", "5447629406057034342", "🪙"),
    ("pk3_on_arrow", "5445279663809130789", "🔛"),
    ("pk3_phone_off", "5445349654596189741", "📴"),
    ("pk3_technologist", "5445224894386172410", "👩‍💻"),
    ("pk3_hug_people_1", "5445372439397691719", "🫂"),
    ("pk3_hug_people_2", "5445174334031166029", "🫂"),
    ("pk3_cross", "5445092669522996408", "❌"),
    ("pk3_money_bag", "5444860552310457690", "💰"),
    ("pk3_dollar", "5447579253723918909", "💲"),
    ("pk3_purse_1", "5444903695256941915", "👛"),
    ("pk3_purse_2", "5444960062407732826", "👛"),
    ("pk3_writing", "5445128296276718145", "✍️"),
    ("pk3_artist", "5447226864542190055", "👨‍🎨"),
    ("pk3_magnifier_left", "5444989577422993015", "🔍"),
    ("pk3_prohibited_2", "5447385112612208213", "🚫"),
    ("pk3_speech_2", "5445371412900508977", "💬"),
    ("pk3_speech_3", "5447510826304959724", "💬"),
    ("pk3_folder_2", "5444908424015934570", "📁"),
    ("pk3_picture_2", "5447637214307579793", "🖼"),
    ("pk3_star", "5444939047132755535", "⭐️"),
    ("pk3_globe_2", "5445326466067754897", "🌐"),
    ("pk3_play_2", "5445408306669582934", "▶️"),
    ("pk3_play_reverse", "5447651546613449378", "◀️"),
    ("pk3_arrow_right_3", "5445364025556759279", "➡️"),
    ("pk3_arrow_return", "5445362436418859744", "↩️"),
    ("pk3_arrow_up", "5444988177263654261", "⬆️"),
    ("pk3_folder_3", "5444965220663458467", "📁"),
    ("pk3_magnifier_right_1", "5445255929819854310", "🔎"),
    ("pk3_registered", "5445373981290952548", "®️"),
    ("pk3_gear_1", "5444869180899752137", "⚙️"),
    ("pk3_gear_2", "5445347129155419150", "⚙️"),
    ("pk3_video_camera", "5445344161333015312", "📹"),
    ("pk3_phone_arrow_3", "5445386127458465652", "📲"),
    ("pk3_desktop_1", "5447607759421863856", "🖥"),
    ("pk3_clipboard", "5445260044398524944", "📋"),
    ("pk3_bookmark_tabs", "5445203741672243391", "📑"),
    ("pk3_notebook", "5444854925903295394", "📔"),
    ("pk3_desktop_2", "5447190164046639079", "🖥"),
    ("pk3_desktop_3", "5447609176761071706", "🖥"),
    ("pk3_desktop_4", "5447180161067808631", "🖥"),
    ("pk3_desktop_5", "5444901350204798672", "🖥"),
    ("pk3_mic", "5447321534211323909", "🎙"),
    ("pk3_speaker", "5445030469806618301", "🔊"),
    ("pk3_cart_1", "5447319442562251569", "🛒"),
    ("pk3_cart_2", "5445146945024720188", "🛒"),
    ("pk3_cart_3", "5447253390260207116", "🛒"),
    ("pk3_shopping_bags", "5447387942995655277", "🛍"),
    ("pk3_credit_card", "5447453226498552490", "💳"),
    ("pk3_black_circle", "5447429226221303478", "⚫️"),
    ("pk3_alarm_clock", "5445350406215465190", "⏰"),
    ("pk3_globe_3", "5445027583588593750", "🌐"),
    ("pk3_magnifier_right_2", "5445023138297447592", "🔎"),
    ("pk3_desktop_6", "5445104308884370368", "🖥"),
    ("pk3_key", "5445373775132522312", "🔑"),
    ("pk3_briefcase_1", "5447395373289079503", "💼"),
    ("pk3_briefcase_2", "5445219272273990067", "💼"),
    ("pk3_briefcase_3", "5444924349754667822", "💼"),
]

EXTRA_RAW.update({name: emoji_id for name, emoji_id, _ in _BANK3})
EXTRA_FALLBACK = {name: fallback for name, _, fallback in _BANK3}   # ایموجی پایه‌ی هر اسم (برای تگ داخل متن)
EXTRA_FALLBACK["crypto_globe"] = "🌐"


def bank_tag(name: str) -> str:
    """تگ <tg-emoji> برای یه ایموجی بانک (داخل متن، نیازمند parse_mode=\"HTML\")"""
    return _tag(EXTRA_RAW[name], EXTRA_FALLBACK.get(name, "⭐"))



# ---- برای استفاده داخل متن پیام (نیازمند parse_mode="HTML") ----
CARD = _tag(*_DATA["CARD"])
SUPPORT = _tag(*_DATA["SUPPORT"])
PRICE = _tag(*_DATA["PRICE"])
CONFIRM = _tag(*_DATA["CONFIRM"])
REJECT = _tag(*_DATA["REJECT"])
CONNECTION = _tag(*_DATA["CONNECTION"])
REMAINING = _tag(*_DATA["REMAINING"])
LOCATION = _tag(*_DATA["LOCATION"])
LINK = _tag(*_DATA["LINK"])
UNLIMITED = _tag(*_DATA["UNLIMITED"])
UP = _tag(*_DATA["UP"])
DOWN = _tag(*_DATA["DOWN"])
TRIAL = _tag(*_DATA["TRIAL"])
WALLET = _tag(*_DATA["WALLET"])
MY_SERVICES = _tag(*_DATA["MY_SERVICES"])
ACCOUNT = _tag(*_DATA["ACCOUNT"])
REFERRAL = _tag(*_DATA["REFERRAL"])
APPS = _tag(*_DATA["APPS"])
BACK = _tag(*_DATA["BACK"])
MENU = _tag(*_DATA["MENU"])
CHARGE = _tag(*_DATA["CHARGE"])
VIP = _tag(*_DATA["VIP"])
CUP = _tag(*_DATA["CUP"])
STAR = _tag(*_DATA["STAR"])
FIRE = _tag(*_DATA["FIRE"])
TWO_PEOPLE = _tag(*_DATA["TWO_PEOPLE"])
LOCK = _tag(*_DATA["LOCK"])
CALENDAR = _tag(*_DATA["CALENDAR"])
CART = _tag(*_DATA["CART"])
FIRE_HOT = _tag(*_DATA["FIRE_HOT"])
ROCKET = _tag(*_DATA["ROCKET"])
DIAMOND = _tag(*_DATA["DIAMOND"])
GAME_SERVICE = _tag(*_DATA["GAME_SERVICE"])
GAME_CONTROLLER = _tag(*_DATA["GAME_CONTROLLER"])
CHECK2 = _tag(*_DATA["CHECK2"])
MEGAPHONE = _tag(*_DATA["MEGAPHONE"])
CHAT = _tag(*_DATA["CHAT"])
FIXED_IP = _tag(*_DATA["FIXED_IP"])
DOWN_ARROW = _tag(*_DATA["DOWN_ARROW"])
WHEEL = _tag(*_DATA["WHEEL"])
WAVE = _tag(*_DATA["WAVE"])
MAP = _tag(*_DATA["MAP"])
LIST = _tag(*_DATA["LIST"])
TRANSFER = _tag(*_DATA["TRANSFER"])
TRASH = _tag(*_DATA["TRASH"])
GEM = _tag(*_DATA["GEM"])
VERIFIED = _tag(*_DATA["VERIFIED"])
LIGHTNING = _tag(*_DATA["LIGHTNING"])
QUESTION = _tag(*_DATA["QUESTION"])
FOLDERS = _tag(*_DATA["FOLDERS"])
CLOCK = _tag(*_DATA["CLOCK"])
TOP = _tag(*_DATA["TOP"])
HOURGLASS2 = _tag(*_DATA["HOURGLASS2"])
EYES = _tag(*_DATA["EYES"])
RESELLER = _tag(*_DATA["RESELLER"])
BACK_TO_MENU = _tag(*_DATA["BACK_TO_MENU"])
TIER_MEDAL_1 = _tag(*_DATA["TIER_MEDAL_1"])
TIER_MEDAL_2 = _tag(*_DATA["TIER_MEDAL_2"])
TIER_MEDAL_3 = _tag(*_DATA["TIER_MEDAL_3"])
TIER_MEDAL_4 = _tag(*_DATA["TIER_MEDAL_4"])

NUM = {n: _tag(*v) for n, v in _NUM_DATA.items()}

# ---- برای استفاده روی دکمه‌ها (پارامتر icon_custom_emoji_id) - فقط آیدی خام ----
RAW = {key: value[0] for key, value in _DATA.items()}
RAW_NUM = {n: v[0] for n, v in _NUM_DATA.items()}

# ---------------------------------------------------------------------------
# ایموجی‌های اختصاصیِ «پلن‌ها، مدت‌ها و لوکیشن» (خرید و تمدید)
# عمداً داخل _DATA نیستن تا به نگاشت خودکارِ کاراکتر←ایموجی (CHAR_IDS) اضافه نشن
# و ایموجی جاهای دیگه‌ی بات (منوها، عددها، الماس‌های عمومی) تغییر نکنن.
#   - PLAN_RAW[...]  : آیدی خام برای icon_custom_emoji_id روی دکمه‌ها
#   - PLAN_TAG[...]  : تگ <tg-emoji> برای داخل متن پیام (parse_mode="HTML")
# ---------------------------------------------------------------------------
_PLAN_DATA = {
    "LOCATION": ("5368654333397199941", "\U0001F680"),   # موشک: لوکیشن «پریمیوم آلمان»
    "DUR_1": ("5814684939035088799", "1\ufe0f\u20e3"),     # دکمه‌ی مدت ۱ ماهه
    "DUR_2": ("5816683846879417049", "2\ufe0f\u20e3"),     # دکمه‌ی مدت ۲ ماهه
    "DUR_3": ("5816422472349651007", "3\ufe0f\u20e3"),     # دکمه‌ی مدت ۳ ماهه
    "GEM_1": ("5427168083074628963", "\U0001F48E"),       # الماس همه‌ی پلن‌های ۱ ماهه
    "GEM_2": ("5380111356227770863", "\U0001F48E"),       # الماس همه‌ی پلن‌های ۲ ماهه
    "GEM_3": ("5296773795091094130", "\U0001F48E"),       # الماس همه‌ی پلن‌های ۳ ماهه
}
PLAN_RAW = {key: value[0] for key, value in _PLAN_DATA.items()}
PLAN_TAG = {key: _tag(*value) for key, value in _PLAN_DATA.items()}

# نگاشت سطح‌های باشگاه مشتریان به ایموجی پرمیوم، به ترتیب نردبان (سطح ۱ تا ۴).
LOYALTY_TIER_MEDALS = [TIER_MEDAL_1, TIER_MEDAL_2, TIER_MEDAL_3, TIER_MEDAL_4]


def esc(text) -> str:
    """قبل از قرار دادن هر متن خام (اسم کاربر، لینک و ...) کنار تگ‌های HTML، این رو صداش بزن"""
    return html.escape(str(text), quote=False)


# ===========================================================================
# جایگزینی خودکار ایموجی‌های معمولی با ایموجی پریمیوم (برای کل بات)
# ===========================================================================
# هر ایموجی معمولی که جایی از بات (متن پیام، کپشن، دکمه‌های شیشه‌ای) نوشته شده باشه، موقع ارسال
# خودکار با معادل پریمیومش از همین بانک عوض میشه (rich_messages.install_rich_hooks این کار رو
# انجام میده). اول ایموجی‌هایی که خودِ بانک برای اون کاراکتر داره؛ بعد جفت‌های «مرتبط» پایین.
import re as _re

_RELATED = {
    # کاراکتر                 -> اسم ایموجی در بانک (EXTRA_RAW) یا کلید _DATA
    "🎉": "gift_2", "🎊": "gift_2", "🥳": "gift_2",
    "👇": "pk3_arrow_down", "👆": "pk3_arrow_up",
    "⏳": "hourglass", "⌛": "HOURGLASS2",
    "📸": "screenshot_camera", "📷": "screenshot_camera",
    "🟢": "pk3_check_green", "🟡": "pk3_warning_1", "🔴": "pk3_cross", "🔵": "blue_1", "🟣": "blue_2",
    "⚪": "radio_button",
    "🎫": "pk3_bookmark_tabs", "🎟": "pk3_bookmark_tabs",
    "🔄": "pk3_arrows_lr", "🔃": "pk3_arrows_lr",
    "✏": "pk3_writing", "🖊": "pk3_writing",
    "🔔": "pk3_alarm_clock", "🔕": "pk3_phone_off",
    "👤": "ACCOUNT", "👥": "TWO_PEOPLE",
    "🧾": "pk3_clipboard", "📊": "pk3_clipboard",
    "📢": "MEGAPHONE",
    "🙁": "pk3_heart_broken", "😔": "pk3_heart_broken", "😢": "pk3_heart_broken",
    "🙏": "pk3_heart_1", "😍": "pk3_heart_1", "💙": "pk3_heart_1", "💜": "pk3_heart_2",
    "⏸": "pk3_square_button",
    "♾": "UNLIMITED",
    "📈": "UP", "📉": "DOWN",
    "🧹": "TRASH",
    "🕓": "CLOCK", "🕐": "CLOCK", "🕒": "CLOCK",
    "🎲": "game_controller",
    "🤝": "pk3_hug_people_2",
    "📒": "pk3_notebook", "📓": "pk3_notebook",
    "💡": "pk3_bolt",
    "❗": "exclaim", "❕": "exclaim", "‼": "exclaim",
    "🔹": "blue_1", "🔸": "blue_2",
    "🚀": "ROCKET",
    "✉": "pk3_speech_2", "📩": "pk3_speech_2", "📨": "pk3_speech_2",
    "⛔": "pk3_prohibited_2",
    "✨": "star_pretty", "🌟": "star_pretty", "💫": "star_pretty",
    "🔐": "LOCK", "🔓": "LOCK",
    "💵": "PRICE", "💸": "PRICE",
    "🗓": "CALENDAR", "📅": "CALENDAR", "📆": "CALENDAR",
    "🔙": "BACK", "🔗": "LINK",
    "🎁": "gift_2", "📦": "shopping_bag", "🧭": "pk3_globe_2",
}


def _norm_emoji(ch: str) -> str:
    return ch.replace("\ufe0f", "")


def _resolve_id(name: str):
    if name in _DATA:
        return _DATA[name][0]
    return EXTRA_RAW.get(name)


def _build_char_map() -> dict:
    mapping = {}
    for emoji_id, fallback in _DATA.values():          # اول: ایموجی‌های اصلی بات
        mapping.setdefault(_norm_emoji(fallback), emoji_id)
    for _name, emoji_id, fallback in _BANK3:            # بعد: بانک بچ سوم
        mapping.setdefault(_norm_emoji(fallback), emoji_id)
    for num, (emoji_id, fallback) in _NUM_DATA.items():  # عددها (1️⃣ ...)
        mapping.setdefault(_norm_emoji(fallback), emoji_id)
    for char, name in _RELATED.items():                 # آخر: جفت‌های مرتبط (فقط برای کاراکترهای بدون معادل)
        emoji_id = _resolve_id(name)
        if emoji_id:
            mapping.setdefault(_norm_emoji(char), emoji_id)
    return mapping


CHAR_IDS = _build_char_map()

_E_BASE = (
    "[\U0001F000-\U0001FAFF\u2190-\u21FF\u2300-\u23FF\u25A0-\u25FF\u2600-\u27BF\u2B00-\u2BFF"
    "\u00A9\u00AE\u203C\u2049\u2122\u2139\u3030\u303D\u3297\u3299]"
)
_EMOJI_RE = _re.compile(
    r"[0-9#*]\ufe0f?\u20e3"
    + "|" + _E_BASE + "[\U0001F3FB-\U0001F3FF]?\ufe0f?(?:\u200d" + _E_BASE + "\ufe0f?)*"
)
# بخش‌هایی که ایموجی داخلشون دست نمی‌خوره: تگ‌های tg-emoji، کد، و خودِ تگ‌ها
_SKIP_RE = _re.compile(
    r"(<tg-emoji\b[^>]*>.*?</tg-emoji>|<(?:code|pre)\b[^>]*>.*?</(?:code|pre)>|<[^>]+>)",
    _re.DOTALL | _re.IGNORECASE,
)


def premiumize_html(markup: str) -> str:
    """هر ایموجی معمولیِ داخل متن HTML تلگرام (که معادل پریمیوم داره) رو با تگ tg-emoji عوض می‌کنه"""
    if not markup:
        return markup

    def repl(m):
        emoji_id = CHAR_IDS.get(_norm_emoji(m.group(0)))
        return _tag(emoji_id, m.group(0)) if emoji_id else m.group(0)

    parts = _SKIP_RE.split(markup)
    for i in range(0, len(parts), 2):  # ایندکس‌های زوج = متن عادی؛ فرد = تگ/کد
        parts[i] = _EMOJI_RE.sub(repl, parts[i])
    return "".join(parts)


def button_icon(text: str):
    """
    برای متن دکمه‌ی شیشه‌ای: (آیدی ایموجی پریمیوم برای icon_custom_emoji_id یا None, متن بدون ایموجی).
    ایموجی‌های بدون معادل (مثل پرچم) دست‌نخورده می‌مونن.
    """
    found = []

    def repl(m):
        emoji_id = CHAR_IDS.get(_norm_emoji(m.group(0)))
        if emoji_id is None:
            return m.group(0)
        found.append(emoji_id)
        return ""

    cleaned = _EMOJI_RE.sub(repl, text or "")
    cleaned = _re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    if not found or not cleaned:
        return None, text
    return found[0], cleaned


# آیکونِ پیش‌فرضِ «برچسب» ردیف‌های جدول (وقتی خودِ برچسب ایموجی نداره): (regex روی متن برچسب, اسم ایموجی)
# ترتیب مهمه: اولین الگوی منطبق برنده‌ست (مثلاً «شماره کارت» باید قبل از «شماره/شناسه» بیاد).
_LABEL_ICONS = [
    (r"نام کاربری|یوزرنیم|username|user name|имя пользователя", "pk3_technologist"),
    (r"شماره کارت|کارت|card|карт", "CARD"),
    (r"روش|درگاه|method|gateway|способ|шлюз", "pk3_credit_card"),
    (r"آیدی|شناسه|شماره|\bid\b|\bکد\b|\bcode\b|\bкод\b|номер", "pk3_key"),
    (r"موجودی|کیف|balance|wallet|остаток|баланс|кошел", "WALLET"),
    (r"زیرمجموعه|دعوت|رفرال|معرف|referral|invite|реферал|приглаш", "TWO_PEOPLE"),
    (r"حجم|ترافیک|مصرف|volume|traffic|usage|data|объ[её]м|трафик|расход", "REMAINING"),
    (r"تخفیف|discount|скидк", "FIRE"),
    (r"پاداش|هدیه|بونوس|bonus|gift|бонус|подар", "gift_2"),
    (r"مبلغ|قیمت|هزینه|پرداخت|مجموع|معادل|درآمد|شارژ|price|amount|cost|total|paid|цена|сумма|оплат", "PRICE"),
    (r"پلن|بسته|plan|тариф", "GEM"),
    (r"سرویس|اشتراک|service|subscription|услуг", "MY_SERVICES"),
    (r"سرعت|speed|скорост", "ROCKET"),
    (r"آیپی|\bip\b|\bайпи\b|ip-адрес", "FIXED_IP"),
    (r"اتصال|connection|соединен", "CONNECTION"),
    (r"کاربرد|مناسب|use case|best for|подходит", "GAME_CONTROLLER"),
    (r"مهلت|مانده|باقی|remaining|left|осталось|остаток дн", "HOURGLASS2"),
    (r"زمان|ساعت|آخرین|time|last|время|послед", "CLOCK"),
    (r"اعتبار|انقضا|تاریخ|مدت|روز|عضویت|valid|expir|date|duration|days|joined|срок|дата|дн", "CALENDAR"),
    (r"وضعیت|status|state|статус", "CONNECTION"),
    (r"لوکیشن|موقعیت|سرور|کشور|location|server|country|локац|сервер|страна", "LOCATION"),
    (r"لینک|آدرس|link|url|address|ссылк|адрес", "LINK"),
    (r"سطح|رتبه|باشگاه|level|tier|rank|уров", "CUP"),
    (r"نماینده|فروش|reseller|продав|реселлер", "RESELLER"),
    (r"پشتیبان|support|поддерж", "SUPPORT"),
    (r"تیکت|ticket|тикет", "pk3_bookmark_tabs"),
    (r"توضیح|پیام|یادداشت|دلیل|متن|note|message|description|reason|заметк|сообщен|причин", "NOTES"),
    (r"تعداد|آمار|گزارش|count|number|stats|кол-во|количеств|статист", "pk3_clipboard"),
    (r"ارز|کریپتو|coin|currency|usdt|trx|валют", "pk3_coin"),
    (r"نسخه|برنامه|اپ|version|app|приложен|версия", "APPS"),
    (r"نوع|type|тип", "pk3_folder_1"),
    (r"نام|اسم|name|имя|название", "ACCOUNT"),
]
_LABEL_ICONS_COMPILED = [(_re.compile(p, _re.IGNORECASE), name) for p, name in _LABEL_ICONS]
LABEL_DEFAULT_ICON = "star_pretty"   # وقتی هیچ الگویی نخورد، ردیف باز هم ایموجی داشته باشه


def _tag_by_name(name: str) -> str:
    emoji_id = _resolve_id(name)
    if not emoji_id:
        return ""
    fallback = _DATA[name][1] if name in _DATA else EXTRA_FALLBACK.get(name, "⭐")
    return _tag(emoji_id, fallback)


def label_icon_tag(label_visible: str) -> str:
    """تگ ایموجی پریمیوم مناسب برای یه برچسب (مثلاً «موجودی» -> کیف پول)؛ رشته‌ی خالی اگه چیزی مناسب نبود"""
    text = (label_visible or "").strip()
    for pattern, name in _LABEL_ICONS_COMPILED:
        if pattern.search(text):
            tag = _tag_by_name(name)
            if tag:
                return tag
    return ""


def label_emoji(label_visible: str) -> str:
    """مثل label_icon_tag ولی همیشه یه ایموجی پریمیوم برمی‌گردونه (اگه الگویی نخورد، ایموجی پیش‌فرض)"""
    return label_icon_tag(label_visible) or _tag_by_name(LABEL_DEFAULT_ICON)
