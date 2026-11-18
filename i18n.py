"""
ماژول چندزبانه (فارسی / انگلیسی / روسی).

طرز استفاده:
    from i18n import t
    text = t("welcome", lang, name="Ali")

- t(key, lang, **kwargs) رشته‌ی مربوط به اون کلید و زبان رو برمی‌گردونه.
  اگه ترجمه‌ی اون زبان موجود نبود، به فارسی (پیش‌فرض) fallback می‌کنه تا
  هیچ‌وقت پیام خالی/خراب نشون داده نشه.
- kwargs برای جای‌گذاری تو رشته‌ها با .format() استفاده میشه (مثل
  "{name}" تو دیکشنری‌های زیر).

نکته‌ی مهم درباره‌ی ایموجی‌های پرمیوم (premium_emoji.py):
    اون‌ها بخشی از UI (آیکون تصویری) هستن، نه متن قابل‌ترجمه؛ مستقل از
    زبان همیشه ثابت می‌مونن و همینجا وارد این فایل نمیشن - تو خودِ
    فراخوانی t() یا مستقیم تو f-string کنارش گذاشته میشن (دقیقاً مثل قبل).

وضعیت پوشش فعلی:
    این فایل هسته‌ی اصلی ناوبری (خوش‌آمدگویی، انتخاب زبان، منوی اصلی
    inline و پایین صفحه، عضویت اجباری، بازگشت به منو، تست رایگان، سرآیند
    کیف‌پول/حساب‌کاربری/زیرمجموعه‌گیری/آموزش/پشتیبانی، حالت خالی
    سرویس‌ها) رو کامل به هر ۳ زبان پوشش می‌ده. بخش‌های عمیق‌تر (فرم‌های
    پرداخت، جزئیات تیکت، پنل ادمین) هنوز فقط فارسی‌ان و باید در قدم بعد
    تدریجی اضافه بشن - کلید جدید اضافه‌کردن به TRANSLATIONS زیر و صدا
    زدن t() به‌جای رشته‌ی خام، برای هرکدوم کافیه.
"""

DEFAULT_LANG = "fa"
SUPPORTED_LANGS = ("fa", "en", "ru")

LANG_LABELS = {
    "fa": "🇮🇷 فارسی",
    "en": "🇬🇧 English",
    "ru": "🇷🇺 Русский",
}

TRANSLATIONS = {
    "choose_language": {
        "fa": "لطفا زبان مورد نظرت رو انتخاب کن:",
        "en": "Please choose your preferred language:",
        "ru": "Пожалуйста, выберите язык:",
    },
    "language_set": {
        "fa": "✅ زبان روی فارسی تنظیم شد.",
        "en": "✅ Language set to English.",
        "ru": "✅ Язык установлен на русский.",
    },
    "welcome_short": {
        "fa": "سلام {name}! به {brand} خوش اومدی.",
        "en": "Hi {name}! Welcome to {brand}.",
        "ru": "Привет, {name}! Добро пожаловать в {brand}.",
    },
    "onboarding_step1": {
        "fa": "به {brand} خوش اومدی!\n\nاینجا می‌تونی VPN پرسرعت، پایدار و بدون قطعی برای اندروید، ویندوز و اپل بگیری.",
        "en": "Welcome to {brand}!\n\nHere you can get fast, stable VPN service for Android, Windows, and Apple devices.",
        "ru": "Добро пожаловать в {brand}!\n\nЗдесь вы можете получить быстрый и стабильный VPN для Android, Windows и Apple.",
    },
    "onboarding_step2": {
        "fa": "قبل از خرید، یه تست رایگان داری!\n\nاز منوی اصلی گزینه‌ی «تست رایگان» رو بزن و بدون هیچ هزینه‌ای امتحانش کن.",
        "en": "Before buying, you get a free trial!\n\nTap \"Free Trial\" from the main menu and try it out at no cost.",
        "ru": "Перед покупкой у вас есть бесплатный пробный период!\n\nНажмите «Бесплатный тест» в главном меню и попробуйте бесплатно.",
    },
    "onboarding_step3": {
        "fa": "با دعوت دوستات پول دربیار!\n\nاز بخش «دعوت دوستان» لینک اختصاصیت رو بگیر؛ هم با عضویت دوستت هدیه می‌گیری هم درصدی از هر خریدش.",
        "en": "Earn money by inviting friends!\n\nGet your link from the \"Referral\" section — earn a bonus when they join, plus a share of their purchases.",
        "ru": "Зарабатывайте, приглашая друзей!\n\nПолучите свою ссылку в разделе «Рефералы» — бонус за вступление друга и процент с его покупок.",
    },
    "join_channel_prompt": {
        "fa": "برای استفاده از امکانات ربات {brand}، اول باید عضو کانال ما بشی:",
        "en": "To use {brand} bot features, you first need to join our channel:",
        "ru": "Чтобы пользоваться функциями бота {brand}, сначала вступите в наш канал:",
    },
    "join_channel_instruction": {
        "fa": "بعد از عضویت، روی دکمه‌ی «عضو شدم، بررسی کن» بزن.",
        "en": "After joining, tap the \"I joined, check now\" button.",
        "ru": "После вступления нажмите «Я подписался, проверить».",
    },
    "join_channel_button": {
        "fa": "📢 عضویت در کانال",
        "en": "📢 Join Channel",
        "ru": "📢 Вступить в канал",
    },
    "joined_check_button": {
        "fa": "عضو شدم، بررسی کن",
        "en": "I joined, check now",
        "ru": "Я подписался, проверить",
    },
    "not_joined_alert": {
        "fa": "هنوز عضو کانال نشدی 🙁",
        "en": "You haven't joined the channel yet 🙁",
        "ru": "Вы ещё не вступили в канал 🙁",
    },
    "joined_confirmed": {
        "fa": "✅ عضویت تایید شد.",
        "en": "✅ Membership confirmed.",
        "ru": "✅ Подписка подтверждена.",
    },
    # برچسب ردیف‌های جدولِ «پیام غنی» (پنل منوی اصلی و ...)
    "panel_balance": {"fa": "موجودی کیف پول", "en": "Wallet balance", "ru": "Баланс кошелька"},
    "panel_active_services": {"fa": "سرویس‌های فعال", "en": "Active services", "ru": "Активные услуги"},
    "panel_user_id": {"fa": "شناسه کاربری", "en": "User ID", "ru": "ID пользователя"},
    "panel_toman": {"fa": "{n} تومان", "en": "{n} Toman", "ru": "{n} томан"},
    "panel_balance_short": {"fa": "موجودی", "en": "Balance", "ru": "Баланс"},
    "panel_last_visit": {"fa": "آخرین ورود", "en": "Last visit", "ru": "Последний визит"},
    "panel_first_visit": {"fa": "اولین بازدید شماست 👋", "en": "This is your first visit 👋", "ru": "Это ваш первый визит 👋"},
    "panel_choose": {"fa": "یکی از گزینه‌های منو را انتخاب کنید", "en": "Choose an option from the menu", "ru": "Выберите пункт меню"},
    "back_to_menu": {
        "fa": "به منوی اصلی بازگشتید.",
        "en": "You're back at the main menu.",
        "ru": "Вы вернулись в главное меню.",
    },
    "quick_status_line": {
        "fa": "{wallet_icon} موجودی: {balance:,} تومان   |   {services_icon} سرویس فعال: {count}",
        "en": "{wallet_icon} Balance: {balance:,} Toman   |   {services_icon} Active services: {count}",
        "ru": "{wallet_icon} Баланс: {balance:,} томан   |   {services_icon} Активных услуг: {count}",
    },
    # --- دکمه‌های منوی اصلی (هم inline هم پایین صفحه) ---
    "menu_buy": {"fa": "خرید سرویس جدید", "en": "Buy New Service", "ru": "Купить новую услугу"},
    "menu_enter_app": {"fa": "ورود به مینی اپ", "en": "Open the Mini App", "ru": "Открыть мини-приложение"},
    "menu_myservices": {"fa": "سرویس‌های من", "en": "My Services", "ru": "Мои услуги"},
    "menu_trial": {"fa": "تست رایگان", "en": "Free Trial", "ru": "Бесплатный тест"},
    "menu_wallet": {"fa": "کیف پول", "en": "Wallet", "ru": "Кошелёк"},
    "menu_account": {"fa": "حساب کاربری", "en": "Account", "ru": "Аккаунт"},
    "menu_apps": {"fa": "آموزش اتصال", "en": "Guides & Apps", "ru": "Гайды и приложения"},
    "menu_referral": {"fa": "دعوت دوستان", "en": "Invite Friends", "ru": "Пригласить друзей"},
    "menu_support": {"fa": "پشتیبانی", "en": "Support", "ru": "Поддержка"},
    "menu_reseller": {"fa": "نمایندگی فروش", "en": "Reseller", "ru": "Партнёрство"},
    "menu_loyalty": {"fa": "باشگاه مشتریان", "en": "Loyalty Club", "ru": "Клуб лояльности"},
    "menu_back_to_main": {"fa": "بازگشت به منو اصلی", "en": "Back to Main Menu", "ru": "Назад в главное меню"},
    "loyalty_hub_title": {
        "fa": "{icon} باشگاه مشتریان {brand}",
        "en": "{icon} {brand} Loyalty Club",
        "ru": "{icon} Клуб лояльности {brand}",
    },
    "loyalty_ladder_title": {"fa": "سطح‌های باشگاه:", "en": "Club Tiers:", "ru": "Уровни клуба:"},
    "loyalty_tier_row": {
        "fa": "{mark} {emoji} {name} — {threshold:,} تومان خرید ({bonus:,} تومان/ماه){current_marker}",
        "en": "{mark} {emoji} {name} — {threshold:,} Toman spent ({bonus:,} Toman/month){current_marker}",
        "ru": "{mark} {emoji} {name} — {threshold:,} томан покупок ({bonus:,} томан/мес){current_marker}",
    },
    "loyalty_current_marker": {"fa": "  ← سطح شما", "en": "  ← your tier", "ru": "  ← ваш уровень"},
    "loyalty_leaderboard_title": {
        "fa": "{icon} برترین اعضای باشگاه (تا رتبه ۱۰)",
        "en": "{icon} Top Club Members (Top 10)",
        "ru": "{icon} Лучшие участники клуба (топ-10)",
    },
    "loyalty_leaderboard_empty": {
        "fa": "هنوز کسی به هیچ سطحی نرسیده. اولین نفر باش!",
        "en": "No one has reached a tier yet. Be the first!",
        "ru": "Пока никто не достиг уровня. Будьте первым!",
    },
    "loyalty_your_rank": {
        "fa": "\n{icon} رتبه‌ی تو در باشگاه: #{rank}",
        "en": "\n{icon} Your club rank: #{rank}",
        "ru": "\n{icon} Ваш ранг в клубе: #{rank}",
    },
    "loyalty_no_rank_yet": {
        "fa": "\nهنوز خریدی ثبت نکردی؛ با اولین خرید وارد رتبه‌بندی میشی.",
        "en": "\nYou haven't made a purchase yet; you'll enter the ranking with your first one.",
        "ru": "\nВы ещё не совершали покупок; вы попадёте в рейтинг после первой покупки.",
    },
    "loyalty_account_pointer": {
        "fa": "برای جزئیات کامل و رتبه‌بندی، از منوی اصلی «{menu_label}» رو بزن",
        "en": "For full details and the leaderboard, tap \"{menu_label}\" from the main menu",
        "ru": "Подробности и рейтинг — в разделе «{menu_label}» в главном меню",
    },
    "reseller_title": {"fa": "{icon} نمایندگی فروش", "en": "{icon} Reseller Program", "ru": "{icon} Партнёрская программа"},
    "reseller_active_intro": {
        "fa": "تو نماینده‌ی تاییدشده‌ی ما هستی! می‌تونی کانفیگ‌ها رو با قیمت ویژه‌ی نمایندگی (هر گیگ {price:,} تومان) بخری.",
        "en": "You're one of our approved resellers! You can buy configs at the special reseller rate ({price:,} Toman per GB).",
        "ru": "Вы наш подтверждённый партнёр! Вы можете покупать конфиги по специальной партнёрской цене ({price:,} томан за ГБ).",
    },
    "reseller_catalog_button": {"fa": "خرید با قیمت نمایندگی", "en": "Buy at Reseller Price", "ru": "Купить по партнёрской цене"},
    "reseller_eligible_intro": {
        "fa": "تبریک! موجودی کیف پولت همین الان از {threshold:,} تومان بیشتره و واجد شرایط درخواست نمایندگی هستی.\nمی‌تونی درخواستت رو برای بررسی برای ادمین بفرستی:",
        "en": "Congrats! Your wallet balance right now is over {threshold:,} Toman, so you're eligible to request reseller status.\nYou can send your request to the admin for review:",
        "ru": "Поздравляем! Баланс вашего кошелька прямо сейчас превышает {threshold:,} томан — вы можете подать заявку на партнёрство.\nОтправьте заявку администратору на рассмотрение:",
    },
    "reseller_not_eligible_intro": {
        "fa": "با داشتن موجودی کافی توی کیف پول می‌تونی نماینده‌ی فروش ما بشی و کانفیگ‌ها رو با قیمت عمده بخری.",
        "en": "With enough balance in your wallet, you can become one of our resellers and buy configs at wholesale pricing.",
        "ru": "При достаточном балансе кошелька вы можете стать нашим партнёром и покупать конфиги по оптовой цене.",
    },
    "reseller_progress": {
        "fa": "{icon} موجودی فعلی: {current:,} از {threshold:,} تومان لازم",
        "en": "{icon} Current balance: {current:,} of {threshold:,} Toman required",
        "ru": "{icon} Текущий баланс: {current:,} из {threshold:,} томан",
    },
    "reseller_request_with_reason_btn": {"fa": "ارسال درخواست (با توضیح)", "en": "Send Request (with a note)", "ru": "Отправить заявку (с комментарием)"},
    "reseller_request_plain_btn": {"fa": "فقط ارسال درخواست", "en": "Just Send a Request", "ru": "Просто отправить заявку"},
    "reseller_request_ask_reason": {
        "fa": "چرا می‌خوای نماینده بشی؟ توضیحت رو بنویس و بفرست (یا /cancel برای انصراف).",
        "en": "Why do you want to become a reseller? Type your reason and send it (or /cancel to cancel).",
        "ru": "Почему вы хотите стать партнёром? Напишите причину (или /cancel для отмены).",
    },
    "reseller_request_sent": {
        "fa": "{icon} درخواست نمایندگیت برای ادمین ارسال شد. به‌زودی نتیجه رو بهت اطلاع می‌دیم.",
        "en": "{icon} Your reseller request was sent to the admin. We'll let you know the result soon.",
        "ru": "{icon} Ваша заявка на партнёрство отправлена администратору. Скоро сообщим результат.",
    },
    "reseller_request_pending": {
        "fa": "یه درخواست نمایندگی باز از قبل داری؛ منتظر بررسی ادمین بمون.",
        "en": "You already have an open reseller request; please wait for the admin to review it.",
        "ru": "У вас уже есть открытая заявка на партнёрство; дождитесь решения администратора.",
    },
    "reseller_not_eligible_alert": {
        "fa": "موجودی کیف پولت هنوز به {threshold:,} تومان نرسیده.",
        "en": "Your wallet balance hasn't reached {threshold:,} Toman yet.",
        "ru": "Баланс вашего кошелька ещё не достиг {threshold:,} томан.",
    },
    "reseller_approved_message": {
        "fa": "{icon} تبریک! درخواست نمایندگیت تایید شد.\n\nحالا از منوی «نمایندگی» می‌تونی کانفیگ‌ها رو با قیمت هر گیگ {price:,} تومان بخری.",
        "en": "{icon} Congratulations! Your reseller request was approved.\n\nYou can now buy configs from the \"Reseller\" menu at {price:,} Toman per GB.",
        "ru": "{icon} Поздравляем! Ваша заявка на партнёрство одобрена.\n\nТеперь вы можете покупать конфиги в разделе «Партнёрство» по {price:,} томан за ГБ.",
    },
    "reseller_rejected_message": {
        "fa": "درخواست نمایندگیت فعلاً تایید نشد. اگه سوالی داری با پشتیبانی در ارتباط باش.",
        "en": "Your reseller request wasn't approved at this time. Contact support if you have questions.",
        "ru": "Ваша заявка на партнёрство пока не одобрена. Если есть вопросы, обратитесь в поддержку.",
    },
    "menu_location_prompt": {
        "fa": "لوکیشن موردنظرت رو انتخاب کن:",
        "en": "Choose your preferred location:",
        "ru": "Выберите нужную локацию:",
    },
    # --- تست رایگان ---
    "trial_already_used": {
        "fa": "تو قبلاً از تست رایگان استفاده کردی؛ هر کاربر فقط یک‌بار می‌تونه تست بگیره.\nبرای ادامه باید یکی از پلن‌ها رو تهیه کنی و سرویس جدید بگیری. دکمه‌ی خرید سرویس همین پایینه.",
        "en": "You've already used your free trial; each user can only take one.\nTo continue, you need to buy a plan and get a new service. The Buy Service button is right below.",
        "ru": "Вы уже использовали бесплатный тест; каждый пользователь может получить его только один раз.\nЧтобы продолжить, нужно приобрести тариф и получить новую услугу. Кнопка покупки — прямо ниже.",
    },
    "trial_location_intro": {
        "fa": "با تست رایگان می‌تونی قبل از خرید، سرعت و کیفیت سرویس رو خودت امتحان کنی؛ هر کاربر فقط یک‌بار می‌تونه تست بگیره.",
        "en": "With the free trial you can test the speed and quality of the service yourself before buying; each user can take one trial only.",
        "ru": "Бесплатный тест позволяет самому проверить скорость и качество услуги перед покупкой; каждый пользователь может получить его только один раз.",
    },
    "trial_location_rows": {
        "fa": "{i1} اعتبار: {days} روز\n{i2} حجم: {mb} مگابایت",
        "en": "{i1} Validity: {days} day(s)\n{i2} Volume: {mb} MB",
        "ru": "{i1} Срок: {days} дн.\n{i2} Объём: {mb} МБ",
    },
    "trial_location_prompt": {
        "fa": "لوکیشنی که می‌خوای ازش تست بگیری رو انتخاب کن:",
        "en": "Choose the location you want to test:",
        "ru": "Выберите локацию, которую хотите протестировать:",
    },
    "trial_creating": {
        "fa": "در حال ساخت سرویس تست رایگان...",
        "en": "Creating your free trial service...",
        "ru": "Создаём бесплатную тестовую услугу...",
    },
    "trial_error": {
        "fa": "متاسفانه در ساخت تست رایگان مشکلی پیش اومد:\n{error}\nلطفا کمی بعد دوباره تلاش کن یا با پشتیبانی تماس بگیر.",
        "en": "Sorry, something went wrong creating your trial:\n{error}\nPlease try again shortly or contact support.",
        "ru": "К сожалению, при создании теста произошла ошибка:\n{error}\nПопробуйте позже или обратитесь в поддержку.",
    },
    "trial_success": {
        "fa": "سرویس تست رایگان‌ت ساخته شد! جزئیات در پیام بعدی",
        "en": "Your free trial service is ready! Details in the next message",
        "ru": "Ваша бесплатная тестовая услуга готова! Подробности в следующем сообщении",
    },
    # --- کیف پول ---
    "wallet_title": {"fa": "کیف پول شما", "en": "Your Wallet", "ru": "Ваш кошелёк"},
    "wallet_balance": {
        "fa": "موجودی فعلی: {balance:,} تومان",
        "en": "Current balance: {balance:,} Toman",
        "ru": "Текущий баланс: {balance:,} томан",
    },
    "wallet_topup_hint": {
        "fa": "موجودی کیف پول از دو راه شارژ میشه:\n{n1} واریز مستقیم و ارسال رسید (دکمه‌ی زیر)\n{n2} پاداش دعوت از دوستان",
        "en": "You can top up your wallet in two ways:\n{n1} Direct deposit + receipt (button below)\n{n2} Referral rewards (invite friends)",
        "ru": "Пополнить кошелёк можно двумя способами:\n{n1} Прямой перевод + чек (кнопка ниже)\n{n2} Реферальные бонусы (приглашайте друзей)",
    },
    # --- حساب کاربری ---
    "account_title": {"fa": "پروفایل کاربری", "en": "User Profile", "ru": "Профиль пользователя"},
    "account_name": {"fa": "نام", "en": "Name", "ru": "Имя"},
    "account_username": {"fa": "نام کاربری", "en": "Username", "ru": "Имя пользователя"},
    "account_id": {"fa": "آیدی", "en": "ID", "ru": "ID"},
    "account_services_count": {"fa": "تعداد سرویس", "en": "Services count", "ru": "Количество услуг"},
    "account_balance": {"fa": "موجودی", "en": "Balance", "ru": "Баланс"},
    "account_joined_at": {"fa": "تاریخ ورود به بات", "en": "Joined on", "ru": "Дата регистрации"},
    "account_loyalty_title": {"fa": "{icon} باشگاه مشتریان", "en": "{icon} Loyalty Club", "ru": "{icon} Клуб лояльности"},
    "account_loyalty_current": {
        "fa": "سطح فعلی: {emoji} {name}",
        "en": "Current tier: {emoji} {name}",
        "ru": "Текущий уровень: {emoji} {name}",
    },
    "account_loyalty_none": {
        "fa": "هنوز به سطح اول باشگاه مشتریان نرسیدی",
        "en": "You haven't reached the first loyalty tier yet",
        "ru": "Вы ещё не достигли первого уровня клуба лояльности",
    },
    "account_loyalty_progress": {
        "fa": "تا سطح بعدی ({emoji} {name})، {remaining:,} تومان دیگه خرید کن",
        "en": "{remaining:,} Toman more in purchases to reach the next tier ({emoji} {name})",
        "ru": "Ещё {remaining:,} томан покупок до следующего уровня ({emoji} {name})",
    },
    "account_loyalty_bonus_note": {
        "fa": "پاداش ماهانه‌ی این سطح: {amount:,} تومان (اول هر ماه به کیف پولت اضافه میشه)",
        "en": "Monthly bonus for this tier: {amount:,} Toman (added to your wallet on the 1st of each month)",
        "ru": "Ежемесячный бонус этого уровня: {amount:,} томан (начисляется 1-го числа каждого месяца)",
    },
    "account_loyalty_maxed": {
        "fa": "به بالاترین سطح باشگاه مشتریان رسیدی!",
        "en": "You've reached the highest loyalty tier!",
        "ru": "Вы достигли высшего уровня клуба лояльности!",
    },
    "loyalty_bonus_message": {
        "fa": "{pe_charge} پاداش ماهانه‌ی باشگاه مشتریان\n\nچون عضو سطح {emoji} {name} هستی، {amount:,} تومان به کیف پولت اضافه شد. ممنون که همراه مایی.",
        "en": "{pe_charge} Monthly Loyalty Club Bonus\n\nAs a {emoji} {name} tier member, {amount:,} Toman was added to your wallet. Thanks for staying with us.",
        "ru": "{pe_charge} Ежемесячный бонус клуба лояльности\n\nКак участник уровня {emoji} {name}, вам начислено {amount:,} томан. Спасибо, что вы с нами.",
    },
    "account_none": {"fa": "ندارد", "en": "none", "ru": "нет"},
    # --- زیرمجموعه‌گیری ---
    "referral_title": {"fa": "دعوت دوستان", "en": "Referral & Invite Friends", "ru": "Реферальная программа"},
    "referral_intro": {
        "fa": "با دعوت دوستان از طریق لینک اختصاصی، بدون پرداخت حتی ۱ ریال کیف پولت شارژ میشه و از خدمات ربات استفاده می‌کنی!",
        "en": "Invite friends with your personal link and charge your wallet without paying a single Toman!",
        "ru": "Приглашайте друзей по своей ссылке и пополняйте кошелёк без единого рубля из своего кармана!",
    },
    "referral_signup_bonus": {
        "fa": "هدیه عضویت: به ازای هر ۱ زیرمجموعه، {amount:,} تومان",
        "en": "Signup bonus: {amount:,} Toman per referral",
        "ru": "Бонус за регистрацию: {amount:,} томан за реферала",
    },
    "referral_purchase_bonus": {
        "fa": "پاداش خرید: به ازای اولین خرید هر زیرمجموعه، {amount:,} تومان",
        "en": "Purchase bonus: {amount:,} Toman on each referral's first purchase",
        "ru": "Бонус за покупку: {amount:,} томан за первую покупку реферала",
    },
    "referral_stats_title": {"fa": "آمار شما", "en": "Your Stats", "ru": "Ваша статистика"},
    "referral_count": {"fa": "زیرمجموعه‌ها", "en": "Referrals", "ru": "Рефералы"},
    "referral_purchases_count": {"fa": "خریدهای زیرمجموعه", "en": "Referral purchases", "ru": "Покупки рефералов"},
    "referral_total_amount": {"fa": "مجموع خرید زیرمجموعه", "en": "Total referral purchases", "ru": "Общая сумма покупок рефералов"},
    "referral_link_label": {"fa": "لینک دعوت شما", "en": "Your invite link", "ru": "Ваша реферальная ссылка"},
    "referral_cta": {
        "fa": "دعوت کن، هدیه بگیر، رشد کن!",
        "en": "Invite, earn, grow!",
        "ru": "Приглашай, получай, расти!",
    },
    "leaderboard_title": {
        "fa": "{icon} لیدربرد رفرال این ماه",
        "en": "{icon} This Month's Referral Leaderboard",
        "ru": "{icon} Лидерборд рефералов за этот месяц",
    },
    "leaderboard_empty": {
        "fa": "این ماه هنوز کسی از طریق لینک دعوت عضو نشده. اولین نفر باش! {icon}",
        "en": "No one has joined via a referral link this month yet. Be the first! {icon}",
        "ru": "В этом месяце пока никто не присоединился по реферальной ссылке. Будь первым! {icon}",
    },
    "leaderboard_row": {
        "fa": "{medal} {name} — {count} دعوت",
        "en": "{medal} {name} — {count} invites",
        "ru": "{medal} {name} — {count} приглашений",
    },
    "leaderboard_your_rank": {
        "fa": "\n{icon} جایگاه تو این ماه: {count} دعوت",
        "en": "\n{icon} Your standing this month: {count} invites",
        "ru": "\n{icon} Ваш результат в этом месяце: {count} приглашений",
    },
    "rating_ask_purchase": {
        "fa": "چقدر از خرید و تحویل سرویس راضی بودی؟",
        "en": "How satisfied were you with your purchase and delivery?",
        "ru": "Насколько вы довольны покупкой и доставкой услуги?",
    },
    "rating_ask_ticket": {
        "fa": "چقدر از پاسخ پشتیبانی راضی بودی؟",
        "en": "How satisfied were you with the support response?",
        "ru": "Насколько вы довольны ответом поддержки?",
    },
    "rating_thanks": {
        "fa": "{stars}\nممنون از نظرت.",
        "en": "{stars}\nThanks for your feedback.",
        "ru": "{stars}\nСпасибо за ваш отзыв.",
    },
    # --- آموزش اپلیکیشن‌ها ---
    "apps_title": {"fa": "آموزش اتصال", "en": "Connection Guide", "ru": "Инструкция по подключению"},
    "apps_choose_device": {
        "fa": "دستگاهت رو انتخاب کن تا راهنمای قدم‌به‌قدم مخصوص همون سیستم‌عامل رو ببینی:",
        "en": "Choose your device to see the step-by-step guide for that platform:",
        "ru": "Выберите устройство, чтобы увидеть пошаговую инструкцию для вашей платформы:",
    },
    # --- پشتیبانی ---
    "support_title": {"fa": "پشتیبانی", "en": "Support", "ru": "Поддержка"},
    "support_choose_option": {
        "fa": "از گزینه‌های زیر انتخاب کن:",
        "en": "Choose one of the options below:",
        "ru": "Выберите один из вариантов ниже:",
    },
    # --- سرویس‌های من ---
    "my_services_empty": {
        "fa": "هنوز هیچ سرویس فعالی نداری.\nاز منوی خرید سرویس، اولین پلنت رو بگیر 👇",
        "en": "You don't have any active service yet.\nGet your first plan from the buy menu 👇",
        "ru": "У вас пока нет активных услуг.\nВыберите первый тариф в меню покупки 👇",
    },
    "my_services_title": {"fa": "سرویس‌های من", "en": "My Services", "ru": "Мои услуги"},
    "my_services_hint": {
        "fa": "روی هر سرویس بزن تا لینک اتصال و گزینه‌ی تمدید رو ببینی.",
        "en": "Tap any service to see its connection link and renewal options.",
        "ru": "Нажмите на услугу, чтобы увидеть ссылку подключения и варианты продления.",
    },
    # --- خرید سرویس ---
    "location_germany_header": {
        "fa": "پریمیوم آلمان",
        "en": "Premium Germany",
        "ru": "Премиум Германия",
    },
    "location_premium_intro": {
        "fa": "سرویس پریمیوم آلمان با سرعت بالا و آیپی ثابت، مناسب گیم، وب‌گردی و استفاده‌ی روزمره است. مشخصات سرویس:",
        "en": "Premium Germany combines high speed with a fixed IP and suits gaming, browsing and everyday use. Specifications:",
        "ru": "Премиум Германия сочетает высокую скорость и постоянный IP и подходит для игр, сёрфинга и повседневного использования. Характеристики:",
    },
    "location_premium_points": {
        "fa": "{i1} سرعت: بسیار بالا\n{i2} اتصال: تانل‌شده\n{i3} آیپی: ثابت\n{i4} کاربرد: گیم، وب‌گردی و استفاده‌ی روزمره",
        "en": "{i1} Speed: Very high\n{i2} Connection: Tunneled\n{i3} IP: Fixed\n{i4} Use: Gaming, browsing and everyday use",
        "ru": "{i1} Скорость: очень высокая\n{i2} Соединение: туннелированное\n{i3} IP: постоянный\n{i4} Применение: игры, сёрфинг и повседневное использование",
    },
    "location_premium_tagline": {
        "fa": "سرویس پریمیوم آلمان با سرعت بالا و آیپی ثابت؛ مناسب گیم، وب‌گردی و استفاده‌ی روزمره.",
        "en": "Premium Germany: high speed and a fixed IP, suited to gaming, browsing and everyday use.",
        "ru": "Премиум Германия: высокая скорость и постоянный IP, подходит для игр, сёрфинга и повседневного использования.",
    },
    # ---- جمله‌های توضیحیِ بالای جدول‌ها: هم راهنمای واقعی صفحه‌ان، هم حباب پیام رو پهن می‌کنن تا جدول جا بشه ----
    "panel_intro": {
        "fa": "از اینجا می‌تونی سرویس بخری، سرویس‌هات رو تمدید و مدیریت کنی، کیف پولت رو شارژ کنی و به پشتیبانی پیام بدی.",
        "en": "From here you can buy a service, renew and manage your services, top up your wallet and message support.",
        "ru": "Здесь вы можете купить услугу, продлить и настроить свои услуги, пополнить кошелёк и написать в поддержку.",
    },
    "wallet_intro": {
        "fa": "موجودی کیف پولت رو اینجا می‌بینی؛ برای خرید و تمدید سرویس می‌تونی مستقیم از همین موجودی پرداخت کنی.",
        "en": "Your wallet balance is shown here; you can pay for new services and renewals directly from it.",
        "ru": "Здесь отображается баланс вашего кошелька; им можно напрямую оплачивать покупку и продление услуг.",
    },
    "weekly_intro": {
        "fa": "این گزارش خلاصه‌ی مصرف ۷ روز اخیر و حجم و زمان باقی‌مانده‌ی هر سرویس توئه؛ جزئیات بیشتر رو توی «سرویس‌های من» ببین.",
        "en": "This is a summary of your last 7 days of usage and the remaining data and time of each service; see more details in My Services.",
        "ru": "Это сводка расхода за последние 7 дней и остатка трафика и времени по каждой услуге; подробности смотрите в разделе «Мои услуги».",
    },
    "purchase_summary_intro": {
        "fa": "خلاصه‌ی پلن انتخابی‌ات رو پایین می‌بینی؛ قبل از پرداخت یه بار مدت، حجم و قیمت رو چک کن و بعد روش پرداخت رو انتخاب کن.",
        "en": "The plan you selected is shown below; check the duration, volume and price once more, then choose a payment method.",
        "ru": "Выбранный тариф показан ниже: проверьте срок, объём и цену, а затем выберите способ оплаты.",
    },
    "renew_summary_intro": {
        "fa": "پلن تمدید و قیمتش رو پایین می‌بینی؛ بعد از پرداخت، تمدید روی همین سرویس اعمال میشه و لینک و کانفیگ قبلی‌ت بدون تغییر می‌مونه.",
        "en": "The renewal plan and its price are shown below; after payment the renewal is applied to this same service and your link and config stay the same.",
        "ru": "Тариф продления и его цена показаны ниже; после оплаты продление применяется к этой же услуге, а ссылка и конфиг остаются прежними.",
    },
    "topup_methods_intro": {
        "fa": "مبلغ شارژ ثبت شد؛ یکی از روش‌های پرداخت زیر رو انتخاب کن تا بعد از پرداخت و تایید، موجودی کیف پولت بالا بره.",
        "en": "Your top-up amount is set; choose one of the payment methods below and your wallet balance will increase after payment and confirmation.",
        "ru": "Сумма пополнения указана; выберите один из способов оплаты ниже, и после оплаты и подтверждения баланс кошелька пополнится.",
    },
    "duration_label": {
        "fa": "{n} ماهه",
        "en": "{n}-month",
        "ru": "{n} мес",
    },
    "plan_duration_prompt": {
        "fa": "مدت سرویس رو انتخاب کن:",
        "en": "Choose your plan duration:",
        "ru": "Выберите срок действия:",
    },
    "plan_duration_line": {
        "fa": "{label}: {days} روز اعتبار، حجم از {min_gb} تا {max_gb} گیگ، از {min_price:,} تومان",
        "en": "{label}: {days} days, {min_gb} to {max_gb} GB, from {min_price:,} Toman",
        "ru": "{label}: {days} дн., от {min_gb} до {max_gb} ГБ, от {min_price:,} томан",
    },
    "plan_price_same_note": {
        "fa": "قیمت هر گیگ توی همه‌ی پلن‌ها یکسانه ({price_per_gb:,} تومان)، پس فقط مدت و حجم رو بر اساس نیازت انتخاب کن.",
        "en": "Every plan costs the same per GB ({price_per_gb:,} Toman), so just pick the duration and volume that fit your needs.",
        "ru": "Цена за ГБ одинакова во всех тарифах ({price_per_gb:,} томан), поэтому выбирайте срок и объём под свои нужды.",
    },
    "plan_volume_prompt": {
        "fa": "حجم موردنظرت رو انتخاب کن:",
        "en": "Choose your data volume:",
        "ru": "Выберите объём трафика:",
    },
    "plan_volume_hint": {
        "fa": "حجم‌های موجود برای این پلن رو توی دکمه‌های پایین می‌بینی؛ قیمت هر گیگ توی همه‌ی پلن‌ها یکسانه ({price_per_gb:,} تومان)، پس فقط حجم مناسب خودت رو انتخاب کن.",
        "en": "You can see the available volumes for this plan in the buttons below; every plan costs the same per GB ({price_per_gb:,} Toman), so just pick the volume that suits you.",
        "ru": "Доступные объёмы для этого тарифа указаны на кнопках ниже; цена за ГБ одинакова во всех тарифах ({price_per_gb:,} томан), поэтому просто выберите подходящий объём.",
    },
    "plan_volume_rows": {
        "fa": "{i1} اعتبار: {days} روز\n{i2} حجم: از {min_gb} تا {max_gb} گیگ\n{i3} شروع قیمت: از {min_price:,} تومان",
        "en": "{i1} Validity: {days} days\n{i2} Volume: {min_gb} to {max_gb} GB\n{i3} Prices from: {min_price:,} Toman",
        "ru": "{i1} Срок: {days} дн.\n{i2} Объём: от {min_gb} до {max_gb} ГБ\n{i3} Цена от: {min_price:,} томан",
    },
    "renew_keep_note": {
        "fa": "با تمدید، مدت سرویس از امروز دوباره از اول شروع میشه و مصرف قبلی صفر میشه. حجم باقی‌مانده‌ی فعلی هم دور ریخته نمیشه و به حجم پلن جدید اضافه میشه.",
        "en": "When you renew, the service period restarts from today and previous usage resets to zero. Any remaining data is not lost; it is added to the new plan's volume.",
        "ru": "При продлении срок услуги начинается заново с сегодняшнего дня, а прежний расход обнуляется. Оставшийся трафик не сгорает и добавляется к объёму нового тарифа.",
    },
    "plan_days_label": {
        "fa": "اعتبار: {days} روز",
        "en": "Validity: {days} days",
        "ru": "Срок действия: {days} дн.",
    },
    "plan_volume_label": {
        "fa": "حجم پلن: {gb} گیگ",
        "en": "Plan volume: {gb} GB",
        "ru": "Объём тарифа: {gb} ГБ",
    },
    "plan_recommended_tag": {
        "fa": "پیشنهادی",
        "en": "Recommended",
        "ru": "Рекомендуем",
    },
    "choose_plan_prompt": {
        "fa": "پلن موردنظرت رو انتخاب کن:",
        "en": "Choose your desired plan:",
        "ru": "Выберите нужный тариф:",
    },
    "plan_not_found": {
        "fa": "پلن پیدا نشد، دوباره تلاش کن.",
        "en": "Plan not found, please try again.",
        "ru": "Тариф не найден, попробуйте снова.",
    },
    "plan_selected_summary": {
        "fa": "پلن انتخابی: {emoji} {title}{unlimited}",
        "en": "Selected plan: {emoji} {title}{unlimited}",
        "ru": "Выбранный тариф: {emoji} {title}{unlimited}",
    },
    "plan_price_label": {
        "fa": "قیمت: {price:,} تومان",
        "en": "Price: {price:,} Toman",
        "ru": "Цена: {price:,} томан",
    },
    "custom_name_question": {
        "fa": "می‌خوای برای این سرویس یه اسم دلخواه انتخاب کنی یا رندوم باشه؟",
        "en": "Would you like to choose a custom name for this service, or use a random one?",
        "ru": "Хотите задать собственное имя для этой услуги или оставить случайное?",
    },
    "choose_payment_method_prompt": {
        "fa": "روش پرداختت رو از پایین انتخاب کن 👇\n✅ با درگاه «کارت به کارت تون پی» و «ویناپی»، سفارشت خودکار تایید میشه.",
        "en": "Choose your payment method below 👇\n✅ Orders paid via TonPays card-to-card or WinaPay are confirmed automatically.",
        "ru": "Выберите способ оплаты ниже 👇\n✅ Заказы, оплаченные через «Карта на карту TonPays» или WinaPay, подтверждаются автоматически.",
    },
    "payment_instructions": {
        "fa": "لطفا مبلغ رو به کارت زیر واریز کن:\nشماره کارت: {card_number}\nبه نام: {card_holder}\n\nیا اگه کیف پولت موجودی کافی داره، مستقیم از همونجا پرداخت کن.\nبعد از واریز کارت‌به‌کارت هم، روی «ارسال رسید پرداخت» بزن.",
        "en": "Please transfer the amount to the card below:\nCard number: {card_number}\nHolder: {card_holder}\n\nOr if your wallet has enough balance, pay directly from there.\nAfter a card transfer, tap \"Send payment receipt\".",
        "ru": "Пожалуйста, переведите сумму на карту ниже:\nНомер карты: {card_number}\nВладелец: {card_holder}\n\nИли, если на кошельке достаточно средств, оплатите прямо оттуда.\nПосле перевода на карту нажмите «Отправить чек об оплате».",
    },
    "renew_service_header": {
        "fa": "تمدید سرویس",
        "en": "Renew Service",
        "ru": "Продление услуги",
    },
    "topup_amount_label": {
        "fa": "مبلغ: {amount:,} تومان",
        "en": "Amount: {amount:,} Toman",
        "ru": "Сумма: {amount:,} томан",
    },
    "topup_card_instructions": {
        "fa": "لطفا مبلغ رو به کارت زیر واریز کن:\nشماره کارت: {card_number}\nبه نام: {card_holder}\n\nسپس عکس رسید پرداخت رو همینجا بفرست.",
        "en": "Please transfer the amount to the card below:\nCard number: {card_number}\nHolder: {card_holder}\n\nThen send the payment receipt photo here.",
        "ru": "Пожалуйста, переведите сумму на карту ниже:\nНомер карты: {card_number}\nВладелец: {card_holder}\n\nЗатем отправьте сюда фото чека.",
    },
    "send_receipt_prompt": {
        "fa": "📸 لطفا الان عکس رسید پرداخت رو ارسال کن.",
        "en": "📸 Please send the payment receipt photo now.",
        "ru": "📸 Пожалуйста, отправьте сейчас фото чека об оплате.",
    },
    "buy_step_title": {
        "fa": "خرید سرویس · مرحله {n} از {total}",
        "en": "Buy a service · Step {n} of {total}",
        "ru": "Покупка · шаг {n} из {total}",
    },
    "buy_pay_title": {
        "fa": "تایید و پرداخت",
        "en": "Review & pay",
        "ru": "Проверка и оплата",
    },
    "renew_step_title": {
        "fa": "تمدید سرویس · مرحله {n} از {total}",
        "en": "Renew service · Step {n} of {total}",
        "ru": "Продление · шаг {n} из {total}",
    },
}


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    entry = TRANSLATIONS.get(key)
    if not entry:
        return key  # کلید تعریف‌نشده - به‌جای کرش، خودِ کلید رو نشون بده تا فوراً حین تست معلوم بشه
    text = entry.get(lang) or entry.get(DEFAULT_LANG, "")
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
