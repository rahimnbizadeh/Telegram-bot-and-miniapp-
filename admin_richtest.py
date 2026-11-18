"""
/richtest (فقط ادمین): چند نمونه «پیام غنی» تلگرام می‌فرسته و جواب تلگرام رو برای هر نمونه جدا
گزارش می‌کنه (✅ یا ❌ با متن خطا). قبل از اینکه پیام غنی رو به بخش‌های بات وصل کنیم، با این دستور
مطمئن میشیم تلگرامِ همین بات جدول، بخش جمع‌شونده، دکمه و ایموجی پریمیوم رو قبول می‌کنه.
"""
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler

import rich_messages as rm
from config import ADMIN_IDS, RICH_MESSAGES_ENABLED

logger = logging.getLogger(__name__)


def _samples():
    # ایموجی پریمیوم (همون شناسه‌ی «کیف پول» منوی اصلی) داخل سلول جدول
    import premium_emoji as pe

    wallet_cell = rm.Raw(f'<tg-emoji emoji-id="{pe.RAW["MENU_WALLET"]}">👛</tg-emoji> موجودی کیف پول')
    rows = [["موجودی کیف پول", "5,000 تومان"], ["سرویس‌های فعال", "2 سرویس"], ["شناسه کاربری", "5328325197"]]
    table_html = rm.document(rm.heading("پنل مدیریت سرویس‌ها", 2), rm.table(rows, bordered=True, rtl=True))
    table_ltr_html = rm.document(rm.heading("پنل مدیریت سرویس‌ها (برای مقایسه)", 2), rm.table(rows, bordered=True, rtl=False))
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("پشتیبانی", callback_data="menu:support")]])
    return [
        ("جدول (HTML) با راست‌به‌چپ", dict(html=table_html)),
        ("همون جدول بدون راست‌به‌چپ (مقایسه)", dict(html=table_ltr_html, rtl=False)),
        ("جدول (Markdown)", dict(markdown="## پنل\n\n| عنوان | مقدار |\n|---|---|\n| موجودی | 5,000 تومان |\n| سرویس فعال | 2 |")),
        ("بخش جمع‌شونده + لیست", dict(html=rm.document(
            rm.heading("آموزش اتصال", 2),
            rm.details("اندروید", rm.bullet_list(["برنامه رو نصب کن", "لینک اشتراک رو وارد کن"])),
        ))),
        ("ایموجی پریمیوم داخل جدول", dict(html=rm.table([[wallet_cell, "5,000 تومان"]], bordered=True))),
        ("دکمه‌ی معمولی زیر پیام غنی", dict(html=rm.table([["تست دکمه", "زیر همین پیام"]]), reply_markup=keyboard)),
    ]


async def richtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    chat_id = update.effective_chat.id
    await update.message.reply_text("⏳ در حال فرستادن ۶ نمونه‌ی پیام غنی... هر کدوم جدا نتیجه می‌ده.")
    lines = []
    for name, kwargs in _samples():
        ok, info = await rm.send_rich(chat_id, **kwargs)
        lines.append(f"{'✅' if ok else '❌'} {name}" + ("" if ok else f"\n    {info}"))
    state = "روشن" if RICH_MESSAGES_ENABLED else "خاموش (RICH_MESSAGES_ENABLED=false)"
    await update.message.reply_text(
        "نتیجه‌ی تست پیام غنی:\n\n" + "\n".join(lines)
        + f"\n\nوضعیت فعلی استفاده‌ی بات از پیام غنی: {state}\n"
        "اگه همه ✅ بود، می‌تونی بعد از دیدن ظاهر پیام‌ها روی گوشیت بگی تا به بخش‌ها وصلش کنم."
    )


def build_handlers():
    return [CommandHandler("richtest", richtest_command)]
