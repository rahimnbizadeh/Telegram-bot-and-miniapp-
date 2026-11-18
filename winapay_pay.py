"""
پرداخت با درگاه ویناپی (WinaPay) برای ربات و مینی‌اپ.

این فایل «تحویل نهایی» رو یه‌جا نگه می‌داره تا هر چهار مسیری که ممکنه پرداخت رو ببینن،
دقیقاً یک خروجی بدن:
  ۱) کال‌بک مرورگر کاربر (/webhook/winapay تو keep_alive.py)
  ۲) job دوره‌ای (پشتیبان؛ اگه کاربر مرورگر رو ببنده و کال‌بک نرسه)
  ۳) دکمه‌ی «پرداخت کردم، بررسی کن» تو ربات
  ۴) وضعیت‌گیری مینی‌اپ (/api/winapay/status)
جلوی تحویل دوباره رو claim_winapay_invoice (آپدیت اتمیک pending → paid) می‌گیره.

نکته‌ی امنیتی: فیلدهای کال‌بک (PaymentStatus/Authority) هیچ‌وقت مستقیم باور نمیشن؛ همیشه با
PaymentVerification و مبلغ ذخیره‌شده‌ی خودمون استعلام میشه.
"""
import logging
import time
from urllib.parse import urlparse

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes

import database as db
import premium_emoji as pe
import winapay_client as winapay
from config import (
    ADMIN_CHAT_ID,
    MINIAPP_URL,
    PUBLIC_BASE_URL,
    WINAPAY_ENABLED,
    WINAPAY_INVOICE_TIMEOUT_MINUTES,
    get_plan,
)
from delivery import send_service_delivery, _plan_with_actual_gb
from i18n import t
from keyboards import rating_keyboard
from panel_client import panel, PanelError

import theme
logger = logging.getLogger(__name__)


def base_url() -> str:
    """
    دامنه‌ی عمومی سرور: اول PUBLIC_BASE_URL؛ اگه خالی بود، از آدرس مینی‌اپ (MINIAPP_URL) فقط
    «پروتکل + دامنه» برداشته میشه (چون مینی‌اپ و آدرس بازگشت روی همون سرور و دامنه‌ان).
    """
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    try:
        u = urlparse(MINIAPP_URL or "")
        if u.scheme in ("http", "https") and u.netloc:
            return f"{u.scheme}://{u.netloc}"
    except ValueError:
        pass
    return ""


def callback_url() -> str:
    """آدرس بازگشت (اجباریِ ویناپی). باید با آدرس ثبت‌شده‌ی درگاه تو پنل ویناپی همخوان باشه."""
    base = base_url()
    return f"{base}/webhook/winapay" if base else ""


def winapay_keyboard(payment_url: str, check_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("پرداخت در ویناپی", url=payment_url, icon_custom_emoji_id=pe.RAW["CARD"], style=theme.NAV)],
        [InlineKeyboardButton("پرداخت کردم، بررسی کن", callback_data=check_callback,
                              icon_custom_emoji_id=pe.RAW["CONFIRM"], style=theme.CTA)],
        [InlineKeyboardButton("انصراف", callback_data="menu:back", icon_custom_emoji_id=pe.RAW["BACK"], style="danger")],
    ])


def describe(kind: str, plan: dict = None) -> str:
    if kind == "topup":
        return "شارژ کیف پول نوردیس"
    if kind == "renew":
        return f"تمدید سرویس نوردیس - {plan['title']}" if plan else "تمدید سرویس نوردیس"
    return f"خرید سرویس نوردیس - {plan['title']}" if plan else "خرید سرویس نوردیس"


async def create_invoice(*, user_id: int, chat_id: int, message_id, kind: str, amount_toman: int,
                         plan_id: str = None, sub_id: int = None, custom_name: str = None,
                         discount_code: str = None, discount_percent: int = None) -> dict:
    """فاکتور رو تو ویناپی می‌سازه و تو دیتابیس ثبت می‌کنه. → {"authority", "payment_url", "order_id"}"""
    if not WINAPAY_ENABLED:
        raise winapay.WinaPayError("این روش پرداخت فعلاً غیرفعاله.")
    plan = get_plan(plan_id) if plan_id else None
    order_id = winapay.make_order_id()
    created = await winapay.create_payment(amount_toman, order_id, callback_url(), describe(kind, plan))
    db.create_winapay_invoice(
        authority=created["authority"], order_id=order_id, user_id=user_id, chat_id=chat_id, message_id=message_id,
        kind=kind, amount=int(amount_toman), plan_id=plan_id, sub_id=sub_id, custom_name=custom_name,
        discount_code=discount_code, discount_percent=discount_percent,
    )
    return {"authority": created["authority"], "payment_url": created["payment_url"], "order_id": order_id}


async def fulfill(bot, inv) -> str:
    """فاکتور پرداخت‌شده (و claim‌شده) رو نهایی می‌کنه: صدور/تمدید سرویس یا شارژ کیف پول."""
    user_id = inv["user_id"]
    kind = inv["kind"]

    if kind == "new":
        plan = get_plan(inv["plan_id"])
        custom_name = inv["custom_name"]
        discount_code = inv["discount_code"]
        discount_percent = inv["discount_percent"]
        try:
            username = panel.generate_username(prefix=custom_name) if custom_name else panel.generate_username()
            result = await panel.create_user(username, plan["days"], plan["gb"], display_name=custom_name)
        except PanelError as e:
            return f"⚠️ پرداخت تایید شد ولی صدور سرویس خطا داد: {e}\nبا پشتیبانی تماس بگیر."
        order_id = db.create_order(
            user_id, inv["plan_id"], None, kind="new", custom_name=custom_name,
            discount_code=discount_code, discount_percent=discount_percent,
        )
        db.set_order_status(order_id, "approved", user_id)
        if discount_code:
            db.record_discount_use(discount_code, user_id)
        expire_at = result.get("expire") or 0
        sub_link = result.get("subscription_url", "")
        new_sub_id = db.create_subscription(
            user_id=user_id, order_id=order_id, plan_id=inv["plan_id"], marzban_username=username,
            plan_title=plan["title"], expire_at=expire_at, sub_link=sub_link,
        )
        db.maybe_reward_referrer(user_id)
        await send_service_delivery(
            bot, user_id, plan, username, sub_link, expire_at=expire_at, sub_id=new_sub_id,
            connection_link=result.get("connection_link", ""),
        )
        await bot.send_message(
            chat_id=user_id,
            text=t("rating_ask_purchase", db.get_user_language(user_id)),
            reply_markup=rating_keyboard("purchase", new_sub_id),
            parse_mode="HTML",
        )
        return "🎉 پرداخت تایید شد و سرویس صادر شد! جزئیات در پیام بعدی."

    if kind == "renew":
        plan = get_plan(inv["plan_id"])
        sub = db.get_subscription(inv["sub_id"])
        try:
            result = await panel.modify_user(sub["marzban_username"], plan["days"], plan["gb"])
        except PanelError as e:
            return f"⚠️ پرداخت تایید شد ولی تمدید خطا داد: {e}\nبا پشتیبانی تماس بگیر."
        order_id = db.create_order(user_id, inv["plan_id"], None, kind="renew", renew_sub_id=inv["sub_id"])
        db.set_order_status(order_id, "approved", user_id)
        expire_at = result.get("expire") or 0
        sub_link = result.get("subscription_url", "")
        db.update_subscription_after_renew(inv["sub_id"], expire_at, plan["title"], inv["plan_id"])
        if sub_link:
            db.update_subscription_link(inv["sub_id"], sub_link)
        await send_service_delivery(
            bot, user_id, _plan_with_actual_gb(plan, result), sub["marzban_username"], sub_link or sub["sub_link"],
            "تمدید", expire_at=expire_at, sub_id=inv["sub_id"],
            connection_link=result.get("connection_link", ""),
        )
        return "🎉 پرداخت تایید شد و سرویس تمدید شد! جزئیات در پیام بعدی."

    # topup
    amount = inv["amount"]
    order_id = db.create_order(user_id, None, None, kind="topup", amount=amount)
    db.set_order_status(order_id, "approved", user_id)
    db.adjust_wallet_balance_logged(user_id, amount, "topup", f"شارژ ویناپی - فاکتور #{order_id}")
    return f"🎉 کیف پول با موفقیت شارژ شد!\nموجودی جدید: {db.get_wallet_balance(user_id):,} تومان"


async def try_finalize(bot, authority: str, *, notify: bool = True) -> dict:
    """
    استعلام از ویناپی + (اگه پرداخت قطعی بود) تحویل. نتیجه:
      {"state": "paid"}            همین الان تایید و تحویل شد
      {"state": "already"}         قبلاً تحویل داده شده بود
      {"state": "pending"}         هنوز پرداخت نشده
      {"state": "expired"}         فاکتور منقضی شده
      {"state": "failed", ...}     ویناپی خطای قطعی داد
      {"state": "error", ...}      خطای ارتباط؛ بعداً دوباره
      {"state": "unknown"}         همچین فاکتوری نداریم
    """
    inv = db.get_winapay_invoice(authority)
    if not inv:
        return {"state": "unknown"}
    base = {"kind": inv["kind"], "ref_id": inv["ref_id"]}
    if inv["status"] == "paid":
        return {**base, "state": "already"}
    if inv["status"] == "expired":
        return {**base, "state": "expired"}

    try:
        res = await winapay.verify_payment(authority, inv["amount"])
    except winapay.WinaPayError as e:
        return {**base, "state": "error", "message": str(e)}

    if not res["paid"]:
        if res["unpaid"]:
            return {**base, "state": "pending"}
        logger.warning("ویناپی verify نامعتبر: authority=%s status=%s", authority, res["status"])
        return {**base, "state": "failed", "status": res["status"], "message": res["message"]}

    if not db.claim_winapay_invoice(authority, res["ref_id"]):
        return {**base, "state": "already"}

    if res["wallet_issue"] and ADMIN_CHAT_ID:
        try:
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=(f"⚠️ ویناپی: پرداخت فاکتور {inv['order_id']} (کاربر {inv['user_id']}، {inv['amount']:,} تومان) "
                      "انجام شده ولی ویناپی خطای -18 (مشکل به‌روزرسانی کیف پول پذیرنده) داده. "
                      "خدمت به کاربر تحویل داده شد؛ لطفاً با پشتیبانی ویناپی هماهنگ کن."),
            )
        except Exception:
            logger.warning("اطلاع به ادمین درباره‌ی -18 ویناپی ناموفق بود")

    try:
        text = await fulfill(bot, inv)
    except Exception as e:
        logger.exception("تحویل فاکتور ویناپی %s ناموفق بود", authority)
        text = f"⚠️ پرداخت تایید شد ولی تحویل با خطا مواجه شد: {e}\nلطفاً با پشتیبانی تماس بگیر."

    if notify:
        try:
            await bot.send_message(chat_id=inv["chat_id"], text=text, parse_mode="HTML")
        except Exception:
            logger.warning("اطلاع‌رسانی پرداخت ویناپی فاکتور %s ناموفق بود", authority)
    return {**base, "state": "paid", "text": text, "ref_id": res["ref_id"]}


# ---------------------------- هندلرهای ربات ----------------------------
async def _start_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, *, kind: str, amount_toman: int,
                         plan_id: str = None, sub_id: int = None, custom_name: str = None,
                         discount_code: str = None, discount_percent: int = None):
    query = update.callback_query
    if not WINAPAY_ENABLED:
        await query.answer("این روش پرداخت فعلا غیرفعاله.", show_alert=True)
        return
    await query.answer("در حال ساخت فاکتور...")
    user = update.effective_user
    try:
        inv = await create_invoice(
            user_id=user.id, chat_id=update.effective_chat.id, message_id=None, kind=kind, amount_toman=amount_toman,
            plan_id=plan_id, sub_id=sub_id, custom_name=custom_name,
            discount_code=discount_code, discount_percent=discount_percent,
        )
    except winapay.WinaPayError as e:
        await query.edit_message_text(f"⚠️ خطا در ساخت فاکتور ویناپی: {e}")
        return
    except Exception as e:
        logger.exception("ساخت فاکتور ویناپی ناموفق بود")
        await query.edit_message_text(f"⚠️ خطا در ثبت فاکتور: {e}\nلطفاً به پشتیبانی بگو.")
        return

    text = "\n".join([
        f"{pe.CARD} فاکتور پرداخت آنلاین (ویناپی)",
        "",
        f"{pe.PRICE} مبلغ قابل پرداخت: <b>{amount_toman:,}</b> تومان",
        "",
        "👇 از دکمه‌ی زیر وارد صفحه‌ی پرداخت ویناپی شو و پرداخت رو انجام بده؛ بعد به ربات برگرد.",
        "✅ نیازی به ارسال رسید نیست؛ بعد از پرداخت، تراکنش به‌صورت خودکار تایید و سرویس/شارژ صادر میشه "
        "(اگه چیزی نیومد، دکمه‌ی «پرداخت کردم، بررسی کن» رو بزن).",
    ])
    msg = await query.edit_message_text(
        text, reply_markup=winapay_keyboard(inv["payment_url"], f"wpcheck:{inv['authority']}"), parse_mode="HTML",
    )
    try:
        with db.get_conn() as conn:
            conn.execute("UPDATE winapay_invoices SET message_id = ? WHERE authority = ?", (msg.message_id, inv["authority"]))
    except Exception:
        logger.warning("ذخیره‌ی message_id فاکتور ویناپی ناموفق بود")


async def handle_winapay_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_id = update.callback_query.data.split(":", 1)[1]
    plan = get_plan(plan_id)
    if not plan:
        await update.callback_query.answer("پلن پیدا نشد.", show_alert=True)
        return
    discount = context.user_data.get("applied_discount")
    discount_active = bool(discount and discount.get("plan_id") == plan_id)
    amount = round(plan["price"] * (100 - discount["percent"]) / 100) if discount_active else plan["price"]
    await _start_invoice(
        update, context, kind="new", amount_toman=amount, plan_id=plan_id,
        custom_name=context.user_data.pop("pending_custom_name", None),
        discount_code=discount["code"] if discount_active else None,
        discount_percent=discount["percent"] if discount_active else None,
    )
    context.user_data.pop("applied_discount", None)


async def handle_winapay_renew(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _, sub_id_str, plan_id = update.callback_query.data.split(":")
    plan = get_plan(plan_id)
    if not plan:
        await update.callback_query.answer("پلن پیدا نشد.", show_alert=True)
        return
    await _start_invoice(update, context, kind="renew", amount_toman=plan["price"], plan_id=plan_id, sub_id=int(sub_id_str))


async def handle_winapay_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount = int(update.callback_query.data.split(":", 1)[1])
    await _start_invoice(update, context, kind="topup", amount_toman=amount)


async def handle_winapay_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("در حال بررسی...")
    authority = query.data.split(":", 1)[1]
    inv = db.get_winapay_invoice(authority)
    if not inv or inv["user_id"] != update.effective_user.id:       # فقط صاحب فاکتور
        await query.answer("فاکتور پیدا نشد.", show_alert=True)
        return
    res = await try_finalize(context.bot, authority, notify=False)
    state = res["state"]
    if state == "paid":
        await query.edit_message_text(res["text"], parse_mode="HTML")
    elif state == "already":
        await query.answer("این فاکتور قبلاً تایید و تحویل داده شده.", show_alert=True)
    elif state == "expired":
        await query.edit_message_text("⌛ این فاکتور منقضی شده. دوباره از منو تلاش کن.")
    elif state == "pending":
        await query.answer("هنوز پرداختی تایید نشده. چند لحظه دیگه دوباره امتحان کن.", show_alert=True)
    elif state == "error":
        await query.answer(f"خطا در بررسی: {res.get('message', '')}", show_alert=True)
    else:
        await query.answer(res.get("message") or "پرداخت تایید نشد.", show_alert=True)


async def check_pending_winapay_job(context: ContextTypes.DEFAULT_TYPE):
    """پشتیبان کال‌بک مرورگر: فاکتورهای پرداخت‌نشده رو استعلام می‌کنه و منقضی‌ها رو می‌بنده."""
    if not WINAPAY_ENABLED:
        return
    now = int(time.time())
    for inv in db.get_pending_winapay_invoices():
        if inv["created_at"] and now - inv["created_at"] > WINAPAY_INVOICE_TIMEOUT_MINUTES * 60:
            # قبل از بستن، آخرین استعلام (شاید دقیقاً همین حالا پرداخت شده)
            res = await try_finalize(context.bot, inv["authority"])
            if res["state"] in ("paid", "already"):
                continue
            db.set_winapay_invoice_status(inv["authority"], "expired")
            try:
                await context.bot.send_message(
                    chat_id=inv["chat_id"],
                    text="⌛ فاکتور پرداخت ویناپی‌ت منقضی شد. اگه هنوز می‌خوای پرداخت کنی، دوباره از منو تلاش کن.",
                )
            except Exception:
                logger.warning("اطلاع‌رسانی انقضای فاکتور ویناپی %s ناموفق بود", inv["authority"])
            continue
        try:
            await try_finalize(context.bot, inv["authority"])
        except Exception:
            logger.exception("بررسی فاکتور ویناپی %s با خطا مواجه شد", inv["authority"])


def build_winapay_handlers():
    from user import heavy_limited      # همون محدودکننده‌ی نرخ درگاه‌های دیگه
    return [
        CallbackQueryHandler(heavy_limited(handle_winapay_new), pattern=r"^winapay:"),
        CallbackQueryHandler(heavy_limited(handle_winapay_renew), pattern=r"^winapayrenew:"),
        CallbackQueryHandler(heavy_limited(handle_winapay_topup), pattern=r"^winapaytopup:"),
        CallbackQueryHandler(heavy_limited(handle_winapay_check), pattern=r"^wpcheck:"),
    ]
