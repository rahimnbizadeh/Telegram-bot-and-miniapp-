import logging
import os
import datetime
import time

from telegram import MenuButtonWebApp, WebAppInfo, Update
from telegram.ext import Application, TypeHandler

import rich_intercept

from config import BOT_TOKEN, DEMO_MODE, CRYPTO_PAYMENT_ENABLED, AUTOSMS_ENABLED, TONPAYS_ENABLED, MINIAPP_URL, MINIAPP_PORT
import database as db
import user as user_handlers
import admin as admin_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def _post_init(app: Application):
    """
    بعد از بالا اومدن بات و قبل از شروع polling اجرا میشه. دکمه‌ی منوی
    کنار پیام (همون چیزی که توی بات‌های دیگه Mini App رو باز می‌کنه) رو
    به Mini App خودمون وصل می‌کنه.
    """
    if not MINIAPP_URL:
        logger.info(
            "MINIAPP_URL توی Secrets/.env خالیه؛ دکمه‌ی منوی Mini App ثبت نشد. "
            "بعد از این‌که آدرس عمومی Replit/سرورت رو گرفتی، MINIAPP_URL رو ست کن و دوباره بات رو اجرا کن."
        )
        return
    # تلگرام خودش (جدا از کش HTTP معمولی) صفحه‌ی اصلی Mini App رو بر اساس
    # همین URL کش می‌کنه؛ برای این‌که بعد از هر آپدیت کاربرها مطمئن نسخه‌ی
    # تازه رو ببینن (نه نسخه‌ی کش‌شده‌ی قدیمی)، هر بار که بات بالا میاد یه
    # پارامتر ورژن جدید (بر اساس زمان) به آخر URL اضافه می‌کنیم تا از نظر
    # تلگرام یه آدرس کاملاً «تازه» به‌حساب بیاد.
    versioned_url = f"{MINIAPP_URL}{'&' if '?' in MINIAPP_URL else '?'}v={int(time.time())}"
    try:
        await app.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="منو", web_app=WebAppInfo(url=versioned_url))
        )
        logger.info("دکمه‌ی منوی Mini App تنظیم شد: %s", versioned_url)
    except Exception:
        logger.exception("تنظیم دکمه‌ی منوی Mini App ناموفق بود.")


def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "BOT_TOKEN تنظیم نشده. فایل .env رو بساز (یا در Replit، Secrets رو پر کن) و توکن ربات رو داخلش بذار."
        )

    # این سرور Flask دو تا کاربرد داره: ۱) روی Replit، برای Keep-Alive
    # (KEEP_ALIVE=true) ۲) روی هر جایی (از جمله VPS)، برای میزبانی
    # Mini App و APIهاش - وقتی MINIAPP_URL ست شده باشه، یعنی حتماً بهش
    # نیاز داری، پس خودش رو خودکار روشن می‌کنیم.
    if os.getenv("KEEP_ALIVE", "false").lower() in ("1", "true", "yes") or MINIAPP_URL:
        from keep_alive import keep_alive

        keep_alive()
        logger.info("سرور Flask (Keep-Alive / Mini App) روی پورت %s بالا اومد.", MINIAPP_PORT)

    db.init_db()

    if DEMO_MODE:
        logger.warning(
            "⚠️ ربات در حالت DEMO_MODE اجرا میشه؛ به پنل واقعی Marzban وصل نمیشه و داده‌ی فرضی برمی‌گردونه."
        )

    # ایموجی معمولی -> پریمیوم برای همه‌ی پیام‌ها/کپشن‌ها/دکمه‌ها. حتماً قبل از rich_intercept نصب بشه
    # تا رهگیر پیام غنی بیرونی‌ترین لایه بمونه (پیام‌های ساده بدون parse_mode هم غنی نشن).
    import premium_hook

    premium_hook.install()
    # رهگیر پیام غنی: وقتی RICH_MESSAGES_ENABLED=true باشه، پیام‌های HTML بات به پیام غنی (جدول و ...) تبدیل میشن
    rich_intercept.install()
    app = Application.builder().token(BOT_TOKEN).post_init(_post_init).build()

    # دروازه‌ی ضدِ اسپم/فلاد - باید قبل از همه‌ی handlerهای دیگه (group=0) اجرا
    # بشه، برای همین group=-1 (زودتر از پیش‌فرض). Update رو از Update واقعی می‌گیره.
    app.add_handler(TypeHandler(Update, user_handlers.global_flood_gate), group=-1)

    for handler in user_handlers.build_handlers():
        app.add_handler(handler)

    for handler in admin_handlers.build_handlers():
        app.add_handler(handler)

    # پیگیری تست رایگان (پیام «وصل نشدی؟» بعد از چند دقیقه) - ماژول مستقل
    from trial_followup import build_trial_followup_handlers

    for handler in build_trial_followup_handlers():
        app.add_handler(handler)

    # درگاه پرداخت ویناپی (WinaPay) - ماژول مستقل
    from winapay_pay import build_winapay_handlers

    for handler in build_winapay_handlers():
        app.add_handler(handler)

    if app.job_queue is None:
        logger.warning(
            "⚠️ JobQueue در دسترس نیست (پکیج python-telegram-bot[job-queue] نصب نشده)؛ "
            "بررسی خودکار اتمام حجم/انقضای سرویس‌ها و فاکتورهای کریپتو غیرفعاله."
        )
    else:
        from user import check_data_limits_job, check_expired_subscriptions_job, monthly_loyalty_bonus_job, weekly_summary_job

        # فاصله از ۲ دقیقه به ۲۰ ثانیه کوتاه شد؛ چون فاصله‌ی قبلی به کاربر
        # رو یه اتصال سریع اجازه می‌داد چند برابر سقفش مصرف کنه قبل از قطع.
        app.job_queue.run_repeating(check_data_limits_job, interval=20, first=15)
        logger.info("بررسی خودکار اتمام حجم سرویس‌ها هر ۲۰ ثانیه فعال شد.")

        app.job_queue.run_repeating(check_expired_subscriptions_job, interval=300, first=30)

        # تیکت‌های جواب‌داده‌شده‌ای که کاربر بعدش چیزی ننوشته (TICKET_AUTO_CLOSE_DAYS روز) خودکار بسته میشن
        from user import auto_close_stale_tickets_job

        app.job_queue.run_repeating(auto_close_stale_tickets_job, interval=3600, first=120)
        logger.info("بستن خودکار تیکت‌های جواب‌داده‌شده هر ساعت بررسی میشه.")
        logger.info("بررسی خودکار انقضا/حذف سرویس‌ها (و تمدید خودکار) هر ۵ دقیقه فعال شد.")

        # هر روز چک میشه، ولی خودش فقط روز اول ماه واقعاً پاداش می‌ده
        app.job_queue.run_daily(monthly_loyalty_bonus_job, time=datetime.time(hour=2, minute=0))
        logger.info("پاداش ماهانه‌ی باشگاه مشتریان فعال شد (روز اول هر ماه، ساعت ۰۲:۰۰).")

        # هر روز اجرا میشه، ولی خودش فقط جمعه (به وقت ایران) پیام می‌فرسته. ۰۷:۳۰ UTC = ۱۱:۰۰ تهران
        from config import WEEKLY_SUMMARY_ENABLED

        if WEEKLY_SUMMARY_ENABLED:
            app.job_queue.run_daily(
                weekly_summary_job, time=datetime.time(hour=7, minute=30, tzinfo=datetime.timezone.utc)
            )
            logger.info("خلاصه‌ی هفتگی مصرف فعال شد (جمعه‌ها ساعت ۱۱:۰۰ تهران).")

        # گزارش صبحگاهی ادمین: هر روز ۰۸:۰۰ تهران (= ۰۴:۳۰ UTC) خلاصه‌ی دیروز
        from config import ADMIN_REPORT_ENABLED

        if ADMIN_REPORT_ENABLED:
            from admin_report import daily_report_job

            app.job_queue.run_daily(
                daily_report_job, time=datetime.time(hour=4, minute=30, tzinfo=datetime.timezone.utc)
            )
            logger.info("گزارش صبحگاهی ادمین فعال شد (هر روز ساعت ۰۸:۰۰ تهران).")

        from trial_followup import trial_followup_job, ENABLED as TRIAL_FOLLOWUP_ENABLED, DELAY_MINUTES

        if TRIAL_FOLLOWUP_ENABLED:
            app.job_queue.run_repeating(trial_followup_job, interval=60, first=45)
            logger.info("پیگیری خودکار تست رایگان (اگه وصل نشد) بعد از %s دقیقه فعال شد.", DELAY_MINUTES)

        from usage_history import usage_history_job, ENABLED as USAGE_HISTORY_ENABLED

        if USAGE_HISTORY_ENABLED:
            app.job_queue.run_repeating(usage_history_job, interval=1800, first=90)
            logger.info("ثبت تاریخچه‌ی مصرف روزانه‌ی سرویس‌ها (برای نمودار مینی‌اپ) فعال شد.")

        from smart_alerts import smart_forecast_job, ENABLED as SMART_ALERTS_ENABLED

        if SMART_ALERTS_ENABLED:
            app.job_queue.run_repeating(smart_forecast_job, interval=10800, first=300)
            logger.info("یادآوری هوشمند اتمام حجم (پیش‌بینی بر اساس مصرف واقعی) فعال شد.")

    if CRYPTO_PAYMENT_ENABLED:
        if app.job_queue is None:
            pass
        else:
            from user import check_pending_crypto_job

            app.job_queue.run_repeating(check_pending_crypto_job, interval=90, first=20)
            logger.info("بررسی خودکار فاکتورهای کریپتو هر ۹۰ ثانیه فعال شد.")

    if AUTOSMS_ENABLED:
        if app.job_queue is None:
            pass
        else:
            from user import check_pending_autosms_job

            app.job_queue.run_repeating(check_pending_autosms_job, interval=45, first=15)
            logger.info("بررسی خودکار فاکتورهای پرداخت خودکار (AutoSMS) هر ۴۵ ثانیه فعال شد.")

    if TONPAYS_ENABLED:
        if app.job_queue is None:
            pass
        else:
            from user import check_pending_tonpays_job

            app.job_queue.run_repeating(check_pending_tonpays_job, interval=45, first=15)
            logger.info("بررسی خودکار فاکتورهای TonPays هر ۴۵ ثانیه فعال شد.")

    from config import WINAPAY_ENABLED
    from winapay_pay import check_pending_winapay_job

    if WINAPAY_ENABLED and app.job_queue is not None:
        app.job_queue.run_repeating(check_pending_winapay_job, interval=45, first=20)
        logger.info("بررسی خودکار فاکتورهای ویناپی هر ۴۵ ثانیه فعال شد.")

    logger.info("ربات در حال اجراست...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
