"""ساخت و ارسال پیام تحویل سرویس (متن + QR کد لینک اشتراک + دکمه‌های اقدام)"""
import io
import datetime
import qrcode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import theme
import premium_emoji as pe


def _plan_with_actual_gb(plan: dict, result: dict) -> dict:
    """
    برای تمدید: مقدار gb تو دیکشنری پلن، عدد خامِ همون پلنه (مثلاً ۱۰ گیگ)،
    ولی چون الان حجم باقی‌مونده‌ی سرویس قبلی هم به سقف جدید اضافه میشه
    (تو sanaei_client/marzban_client)، حجم واقعی نهایی ممکنه بیشتر باشه.
    این تابع یه کپی از پلن با gb درست‌شده برمی‌گردونه تا پیام تحویل به
    کاربر (send_service_delivery) عدد واقعی رو نشون بده، نه رقم خام پلن.
    """
    total_gb = result.get("total_gb")
    if not total_gb:
        return plan
    display_plan = dict(plan)
    display_plan["gb"] = total_gb
    display_plan.pop("volume_label", None)  # برچسب حجم ثابت قدیمی دیگه دقیق نیست
    return display_plan


def build_delivery_text(
    plan: dict,
    username: str,
    sub_link: str,
    expire_at: int = 0,
    action_label: str = "خریداری",
    connection_link: str = "",
) -> str:
    if plan.get("volume_label"):
        volume = plan["volume_label"]
    elif plan.get("is_unlimited"):
        volume = f"نامحدود (تا {plan['gb']} گیگ)"
    else:
        volume = f"{plan['gb']} گیگابایت"
    if expire_at:
        expire_str = datetime.datetime.fromtimestamp(expire_at).strftime("%Y-%m-%d")
        expiry_line = f"{pe.CALENDAR} تاریخ انقضا: {expire_str} ({plan['days']} روز)"
    else:
        expiry_line = f"{pe.CALENDAR} مدت زمان: {plan['days']} روز"

    lines = [
        f"{pe.CONFIRM} سرویس شما {action_label} شد!\n",
        f"{pe.MY_SERVICES} نام سرویس: {pe.esc(username)}",
        f"{plan.get('emoji_tag') or plan.get('emoji', '')} پلن: {pe.esc(plan['title'])}",
        f"{pe.REMAINING} حجم: {volume}",
        expiry_line,
    ]
    if connection_link:
        lines.append(f"\n{pe.CONNECTION} کانفیگ اتصال:\n<code>{pe.esc(connection_link)}</code>")
    if sub_link:
        lines.append(f"\n{pe.LINK} لینک سابسکریپشن:\n<code>{pe.esc(sub_link)}</code>")
    elif not connection_link:
        lines.append(
            f"\n{pe.REJECT} لینک سابسکریپشن هنوز آماده نشده؛ از دکمه‌ی «بروزرسانی و "
            "دریافت لینک جدید» تو «سرویس‌های من» یا دستور /myservices امتحان کن."
        )
    return "\n".join(lines)


def build_delivery_keyboard(sub_id: int | None) -> InlineKeyboardMarkup | None:
    rows = []
    if sub_id:
        rows.append(
            [
                InlineKeyboardButton(
                    "مشاهده و مدیریت سرویس",
                    callback_data=f"svcdetail:{sub_id}:1:days",
                    icon_custom_emoji_id=pe.RAW["MY_SERVICES"],
                    style=theme.CTA,
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "راهنمای اتصال و دانلود اپلیکیشن‌ها",
                callback_data="menu:apps",
                icon_custom_emoji_id=pe.RAW["APPS"],
                style=theme.NAV,
            )
        ]
    )
    return InlineKeyboardMarkup(rows) if rows else None


def make_qr_bytes(link: str) -> io.BytesIO:
    img = qrcode.make(link)
    buf = io.BytesIO()
    buf.name = "qr.png"
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


async def send_service_delivery(
    bot,
    chat_id: int,
    plan: dict,
    username: str,
    sub_link: str,
    action_label: str = "خریداری",
    expire_at: int = 0,
    sub_id: int | None = None,
    connection_link: str = "",
):
    text = build_delivery_text(plan, username, sub_link, expire_at, action_label, connection_link)
    keyboard = build_delivery_keyboard(sub_id)
    qr_source = sub_link or connection_link
    if qr_source:
        qr = make_qr_bytes(qr_source)
        await bot.send_photo(chat_id=chat_id, photo=qr, caption=text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=keyboard)
