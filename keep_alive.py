"""
سرور کوچک Flask با سه‌تا وظیفه:
۱. Keep-Alive: وقتی روی Replit اجراست، UptimeRobot هر چند دقیقه بهش سر
   می‌زنه تا Replit ربات رو نخوابونه (مسیر "/").
۲. میزبانی فایل‌های Mini App بات (پوشه‌ی miniapp/) زیر مسیر "/app".
۳. یه API سبک ("/api/...") که دقیقاً از همون database.py و config.py
   خود ربات می‌خونه - یعنی موجودی، سرویس‌ها، پلن‌ها و سطح باشگاه مشتریان
   داخل Mini App همیشه دقیقاً همون چیزیه که داخل خود ربات می‌بینی.

روی VPS واقعی هم می‌تونی همینو نگه داری (فقط برای API/Mini App لازمه)،
فقط دیگه لازم نیست UptimeRobot روش تنظیم کنی.
"""
import asyncio
import base64
import hashlib
import html as _html
import hmac
import json
import os
import re
import time
from threading import Thread, Lock
from urllib.parse import parse_qsl, quote

import httpx
from flask import Flask, jsonify, request, send_from_directory

import database as db
from config import (
    BOT_TOKEN, BOT_USERNAME, PLANS, PREMIUM_LOCATION_NAME, PRICE_PER_GB_TOMAN, DATA_WARNING_THRESHOLD_PERCENT, LOYALTY_TIERS,
    get_plan, MINIAPP_PORT, FREE_TRIAL_DAYS, FREE_TRIAL_GB, FREE_TRIAL_MB, SUPPORT_LINK, ADMIN_CHAT_ID,
    RESELLER_MIN_TOPUP_TOMAN, RESELLER_PRICE_PER_GB_TOMAN, RESELLER_REMARK_PREFIX, PLATFORM_GUIDES,
    CARD_NUMBER, CARD_HOLDER, PANEL_TYPE, FAQ_ITEMS,
    FORCE_JOIN_CHANNEL, REQUIRED_CHANNEL_USERNAME, REQUIRED_CHANNEL_LINK, ADMIN_IDS,
    TRUST_PROXY_HEADERS, API_RATE_LIMIT_PER_MIN, POST_RATE_LIMIT_PER_MIN,
    WEBHOOK_RATE_LIMIT_PER_MIN, MAX_REQUEST_BODY_BYTES,
)
from panel_client import panel, PanelError
from i18n import t as i18n_t, SUPPORTED_LANGS, LANG_LABELS
import security as sec
import premium_hook as _ph   # تبدیل خودکار ایموجی معمولی به پریمیوم برای پیام‌هایی که Flask مستقیم می‌فرسته

MINIAPP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "miniapp")

app = Flask("")
# جلوی بدنه‌ی غول‌پیکر (حمله‌ی ساده‌ی مصرف پهنای‌باند/حافظه با آپلود فایل‌های خیلی بزرگ)
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BODY_BYTES


@app.errorhandler(413)
def _too_large(e):
    return jsonify({"error": "payload_too_large", "message": "حجم درخواست بیش از حد مجازه."}), 413


def _client_ip() -> str:
    """
    IP واقعی کاربر. فقط وقتی TRUST_PROXY_HEADERS روشن باشه (یعنی مطمئنیم این
    سرور پشت Cloudflare/nginx‌ـه) به هدرهای CF-Connecting-IP/X-Forwarded-For
    اعتماد می‌کنیم؛ وگرنه این هدرها رو نادیده می‌گیریم چون بدون پروکسی واسط،
    هرکسی می‌تونه با ارسال یه هدر جعلی محدودیت نرخ رو کاملاً دور بزنه.
    """
    if TRUST_PROXY_HEADERS:
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip.strip()
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _post_identity_key() -> str:
    """
    برای درخواست‌های POST، تا حد امکان بر اساس خودِ کاربر تلگرام (از init_data
    معتبر) شناسایی می‌کنیم نه فقط IP - چون چند کاربر واقعی می‌تونن پشت یه IP
    مشترک (مثلاً یه اپراتور موبایل با CGNAT) باشن و نباید همدیگه رو مسدود کنن.
    اگه init_data معتبر پیدا نشه (مثلاً درخواست ناشناس/جعلی)، میفته رو IP.
    """
    init_data = None
    if request.is_json:
        body = request.get_json(silent=True) or {}
        init_data = body.get("init_data")
    if not init_data:
        init_data = request.form.get("init_data")
    if init_data:
        user = _validate_init_data(init_data)
        if user and "id" in user:
            return f"user:{user['id']}"
    return f"ip:{_client_ip()}"


def _rate_limited_response(retry_after: float):
    resp = jsonify({
        "error": "rate_limited",
        "message": "درخواست‌های زیادی فرستادی؛ چند لحظه صبر کن و دوباره امتحان کن.",
        "retry_after": retry_after,
    })
    resp.status_code = 429
    resp.headers["Retry-After"] = str(int(retry_after) + 1)
    return resp


@app.before_request
def _security_gate():
    """
    دروازه‌ی امنیتی سراسری - قبل از رسیدن به هر route ی دیگه اجرا میشه.
    سه لایه:
    ۱. فایل‌های استاتیک مینی‌اپ (/app و /) کاملاً معافن - فقط HTML/CSS/JS
       ثابتن، خطری ندارن و مرورگر معمولاً چندتاشون رو موازی می‌خواد.
    ۲. وب‌هوک‌های درگاه پرداخت (/webhook/*) - این آدرس‌ها فقط باید از سمت
       سرور خودِ درگاه صدا زده بشن؛ سقف پایین و مستقل.
    ۳. بقیه‌ی /api/* - سقف کلی به‌ازای IP + سقف جداگونه و سخت‌گیرانه‌تر برای
       POSTها (که گرون‌ترن: ساخت سفارش/فاکتور، آپلود رسید، انتقال کیف‌پول)
       بر اساس شناسه‌ی کاربر تلگرام وقتی قابل‌تشخیص باشه.
    """
    path = request.path
    if path == "/" or path.startswith("/app"):
        return None

    if path.startswith("/webhook/"):
        ok, retry_after = sec.allow(f"webhook:{_client_ip()}", WEBHOOK_RATE_LIMIT_PER_MIN, 60)
        if not ok:
            return _rate_limited_response(retry_after)
        return None

    ip_key = f"ip:{_client_ip()}"
    ok, retry_after = sec.allow(ip_key, API_RATE_LIMIT_PER_MIN, 60)
    if not ok:
        return _rate_limited_response(retry_after)

    if request.method == "POST":
        user_key = _post_identity_key()
        ok, retry_after = sec.allow(user_key, POST_RATE_LIMIT_PER_MIN, 60)
        if not ok:
            return _rate_limited_response(retry_after)

    return None


@app.route("/")
def home():
    return "ربات نوردیس روشنه و در حال کار کردنه ✅"


@app.route("/app")
@app.route("/app/")
def miniapp_index():
    """
    no-store اجباریه چون تلگرام (خصوصاً WebView اندروید) فایل‌های Mini App
    رو خیلی تهاجمی کش می‌کنه؛ بدون این هدر، بعد از هر آپدیت ممکنه کاربر
    همچنان نسخه‌ی قدیمی/باگ‌دار رو ببینه حتی اگه فایل روی سرور درست شده باشه.
    """
    resp = send_from_directory(MINIAPP_DIR, "index.html")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# ---------------- اتصال با یک کلیک ----------------
# تلگرام لینک‌های با پروتکل اختصاصی (v2rayng:// و ...) رو مستقیم از مینی‌اپ باز نمیکنه؛
# پس مینی‌اپ این صفحه‌ی https رو تو مرورگر گوشی باز میکنه و این صفحه کاربر رو به برنامه می‌فرسته.
_GO_CLIENTS = {
    "v2rayng": ("v2rayNG", lambda u, n: f"v2rayng://install-sub?url={quote(u, safe='')}&name={quote(n, safe='')}"),
    "hiddify": ("Hiddify", lambda u, n: f"hiddify://import/{u}#{quote(n, safe='')}"),
    "happ": ("Happ", lambda u, n: f"happ://add/{u}"),
    "streisand": ("Streisand", lambda u, n: f"streisand://import/{u}#{quote(n, safe='')}"),
    "v2box": ("V2Box", lambda u, n: f"v2box://install-sub?url={quote(u, safe='')}&name={quote(n, safe='')}"),
    "shadowrocket": ("Shadowrocket", lambda u, n: "shadowrocket://add/sub://" + base64.b64encode(u.encode()).decode() + f"?remark={quote(n, safe='')}"),
}
_GO_URL_RE = re.compile(r"^https?://[^\s<>\"']{4,1800}$")


@app.route("/app/go")
def miniapp_go():
    client = request.args.get("c", "")
    url = (request.args.get("u", "") or "").strip()
    name = re.sub(r"[\x00-\x1f]", "", (request.args.get("n", "") or "Noordis"))[:40].strip() or "Noordis"
    if client not in _GO_CLIENTS or not _GO_URL_RE.match(url):
        return "bad request", 400
    label, build = _GO_CLIENTS[client]
    deeplink = build(url, name)
    e_label, e_link = _html.escape(label), _html.escape(deeplink, quote=True)
    js_link = json.dumps(deeplink).replace("</", "<\\/")
    js_url = json.dumps(url).replace("</", "<\\/")
    page = f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Noordis VPN</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;background:#0A1436;color:#F3F5FF;
font-family:system-ui,-apple-system,"Segoe UI",Tahoma,sans-serif;line-height:1.8}}
.c{{width:100%;max-width:380px;text-align:center}}h1{{font-size:20px;margin:0 0 6px}}p{{margin:0 0 18px;color:rgba(243,245,255,.7);font-size:14px}}
a.b,button{{display:block;width:100%;padding:14px;border:0;border-radius:14px;font:inherit;font-weight:700;font-size:15px;text-decoration:none;cursor:pointer;margin-bottom:10px}}
a.b{{background:linear-gradient(135deg,#7B5FFF,#4A8BFF);color:#fff}}button{{background:rgba(255,255,255,.08);color:#F3F5FF;border:1px solid rgba(226,232,255,.18)}}
small{{display:block;color:rgba(243,245,255,.5);font-size:12.5px;margin-top:6px}}
</style></head><body><div class="c">
<h1>در حال باز کردن {e_label}…</h1>
<p>اگه برنامه خودکار باز نشد، دکمه‌ی زیر رو بزن.</p>
<a class="b" id="go" href="{e_link}">باز کردن {e_label}</a>
<button type="button" id="cp">کپی لینک سرویس</button>
<small>اگه چیزی باز نشد، احتمالاً برنامه نصب نیست یا نسخه‌اش قدیمیه. اول نصب یا آپدیتش کن و دوباره امتحان کن.</small>
</div>
<script>
var L={js_link},U={js_url};
setTimeout(function(){{location.href=L}},250);
document.getElementById("cp").onclick=function(){{var b=this;
function ok(){{b.textContent="کپی شد ✓"}}
if(navigator.clipboard&&navigator.clipboard.writeText){{navigator.clipboard.writeText(U).then(ok,fb)}}else fb();
function fb(){{var t=document.createElement("textarea");t.value=U;document.body.appendChild(t);t.select();try{{document.execCommand("copy");ok()}}catch(e){{}}t.remove()}}}};
</script></body></html>"""
    resp = app.response_class(page, mimetype="text/html")
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/app/<path:filename>")
def miniapp_assets(filename):
    resp = send_from_directory(MINIAPP_DIR, filename)
    if filename.lower().endswith((".woff2", ".woff")):
        # فونت‌ها عوض نمیشن؛ برخلاف index.html، بذار یه‌بار دانلود بشن و بعد از کش گوشی بیان
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


# ---------------- احراز هویت Mini App ----------------
def _validate_init_data(init_data: str, max_age_seconds: int = 86400):
    """
    اعتبارسنجی رسمی initData تلگرام (طبق مستندات Telegram Web Apps)، تا
    مطمئن بشیم کاربر واقعاً همونیه که ادعا می‌کنه و کسی نمی‌تونه با ساختن
    یه initData جعلی، اطلاعات کیف‌پول/سرویس‌های یکی دیگه رو ببینه.
    """
    if not init_data or not BOT_TOKEN:
        return None
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    auth_date = int(parsed.get("auth_date", 0) or 0)
    if max_age_seconds and (time.time() - auth_date) > max_age_seconds:
        return None

    try:
        return json.loads(parsed.get("user", "{}"))
    except (ValueError, TypeError):
        return None


def _get_authed_user_id():
    init_data = request.args.get("init_data") or request.headers.get("X-Telegram-Init-Data", "")
    user = _validate_init_data(init_data)
    if not user or "id" not in user:
        return None
    return int(user["id"])


def _get_authed_user():
    """کل اطلاعات کاربر از initData معتبر تلگرام (id، first_name، username، ...) یا None"""
    init_data = request.args.get("init_data") or request.headers.get("X-Telegram-Init-Data", "")
    user = _validate_init_data(init_data)
    if not user or "id" not in user:
        return None
    return user


def _get_authed_body_user_id(body: dict):
    """مثل _get_authed_user_id ولی برای POSTهایی که init_data رو توی JSON body می‌فرستن، نه query string"""
    init_data = (body or {}).get("init_data", "")
    user = _validate_init_data(init_data)
    if not user or "id" not in user:
        return None
    return int(user["id"])


def _tg_send_message(chat_id, text: str, reply_markup: dict = None):
    """
    ارسال پیام مستقیم به تلگرام از طریق HTTP خام (نه python-telegram-bot)،
    چون Flask توی یه ترد جدا از حلقه‌ی asyncio خود بات اجراست و نمی‌تونه
    مستقیم به Application وصل بشه. این یه درخواست کاملاً مستقل و امنه.
    """
    if not BOT_TOKEN:
        return
    payload = {"chat_id": chat_id, "text": _ph.premium_html(text), "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(_ph.fix_markup_dict(reply_markup))
    try:
        with httpx.Client(timeout=10) as client:
            client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload)
    except Exception:
        pass


def _tg_send_message_id(chat_id, text: str, reply_markup: dict = None):
    """
    مثل _tg_send_message ولی بدون parse_mode (متن خام کاربر داخل پیامه) و message_id
    پیام ارسال‌شده رو برمی‌گردونه (یا None). خود بات هم پیام تیکت ادمین رو بدون
    parse_mode می‌فرسته.
    """
    if not BOT_TOKEN:
        return None
    payload = {"chat_id": chat_id, "text": text}
    if _ph.has_premium(text):
        # متن خام (شامل نوشته‌ی کاربر) escape میشه و بعد ایموجی‌ها پریمیوم میشن؛ ظاهر متن همون می‌مونه
        payload = {"chat_id": chat_id, "text": _ph.premium_plain(text), "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = _ph.fix_markup_dict(reply_markup)
    try:
        with httpx.Client(timeout=10) as client:
            data = client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload).json()
        if data.get("ok"):
            return data["result"]["message_id"]
    except Exception:
        pass
    return None


# ---------------- پیام‌های چت به زبان کاربر (همون زبانی که تو تنظیمات مینی‌اپ/بات انتخاب کرده) ----------------
_LOCATIONS = {"آلمان": ("Germany", "Германия")}


def _plural(n: int, lang: str, en: tuple, ru: tuple) -> str:
    if lang == "ru":
        a, b = n % 10, n % 100
        if a == 1 and b != 11:
            return ru[0]
        if 2 <= a <= 4 and not 12 <= b <= 14:
            return ru[1]
        return ru[2]
    return en[0] if n == 1 else en[1]


def _localize_plan_title(title, lang: str):
    """عنوان‌های استاندارد پلن («۱ ماهه - ۱۰ گیگ | لوکیشن آلمان»، «تست رایگان (1 روزه)») به زبان کاربر؛ بقیه دست‌نخورده"""
    if lang == "fa" or not title:
        return title
    d = lambda x: int(str(x).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")))
    t = str(title).strip()
    m = re.match(r"^([۰-۹0-9]+) ماهه - ([۰-۹0-9]+) گیگ(?: \| (?:لوکیشن (.+)|پریمیوم (.+)))?$", t)
    if m:
        months, gb, loc, prem = d(m.group(1)), d(m.group(2)), m.group(3), m.group(4)
        unit = _plural(months, lang, ("month", "months"), ("месяц", "месяца", "месяцев"))
        gb_unit = "GB" if lang == "en" else "ГБ"
        out = f"{months} {unit} - {gb} {gb_unit}"
        i = 0 if lang == "en" else 1
        if prem:     # عنوان جدید: «پریمیوم آلمان»
            place = _LOCATIONS.get(prem, (prem, prem))[i]
            out += " | " + (f"Premium {place}" if lang == "en" else f"Премиум {place}")
        elif loc:    # عنوان قدیمی سرویس‌های قبلی: «لوکیشن آلمان»
            out += " | " + _LOCATIONS.get(loc, (loc, loc))[i]
        return out
    m = re.match(r"^تست رایگان \(([۰-۹0-9]+) روزه\)$", t)
    if m:
        days = d(m.group(1))
        unit = _plural(days, lang, ("day", "days"), ("день", "дня", "дней"))
        return f"Free trial ({days} {unit})" if lang == "en" else f"Бесплатный тест ({days} {unit})"
    return t


_MSGS = {
    "trial_issued": {
        "fa": "✅ سرویس تست رایگانت از داخل Mini App صادر شد!\n\nپلن: {plan}\nلینک سابسکریپشن:\n<code>{link}</code>",
        "en": "✅ Your free trial service was issued from the Mini App!\n\nPlan: {plan}\nSubscription link:\n<code>{link}</code>",
        "ru": "✅ Ваш бесплатный тест выдан из Mini App!\n\nТариф: {plan}\nСсылка на подписку:\n<code>{link}</code>",
    },
    "bought": {
        "fa": "✅ خرید از Mini App با موفقیت انجام شد!\n\nپلن: {plan}\nمبلغ: {amount} تومان\nلینک سابسکریپشن:\n<code>{link}</code>",
        "en": "✅ Purchase from the Mini App completed!\n\nPlan: {plan}\nAmount: {amount} Toman\nSubscription link:\n<code>{link}</code>",
        "ru": "✅ Покупка из Mini App выполнена!\n\nТариф: {plan}\nСумма: {amount} томан\nСсылка на подписку:\n<code>{link}</code>",
    },
    "reseller_bought": {
        "fa": "✅ خرید نمایندگی از Mini App با موفقیت انجام شد!\n\nپلن: {plan}\nمبلغ: {amount} تومان\nلینک سابسکریپشن:\n<code>{link}</code>",
        "en": "✅ Reseller purchase from the Mini App completed!\n\nPlan: {plan}\nAmount: {amount} Toman\nSubscription link:\n<code>{link}</code>",
        "ru": "✅ Партнёрская покупка из Mini App выполнена!\n\nТариф: {plan}\nСумма: {amount} томан\nСсылка на подписку:\n<code>{link}</code>",
    },
    "receipt_new": {
        "fa": "✅ رسید شما دریافت شد و برای بررسی ارسال شد.\nبه محض تایید، اطلاعات سرویس برات ارسال میشه.",
        "en": "✅ Your receipt was received and sent for review.\nOnce approved, your service details will be sent to you.",
        "ru": "✅ Ваш чек получен и отправлен на проверку.\nПосле подтверждения данные услуги будут отправлены вам.",
    },
    "receipt_renew": {
        "fa": "✅ رسید شما دریافت شد و برای بررسی ارسال شد.\nبه محض تایید، سرویست تمدید میشه.",
        "en": "✅ Your receipt was received and sent for review.\nOnce approved, your service will be renewed.",
        "ru": "✅ Ваш чек получен и отправлен на проверку.\nПосле подтверждения услуга будет продлена.",
    },
    "receipt_topup": {
        "fa": "✅ رسید شارژ کیف پول دریافت شد و برای بررسی ارسال شد.\nبه محض تایید، مبلغ به کیف پولت اضافه میشه.",
        "en": "✅ Your wallet top-up receipt was received and sent for review.\nOnce approved, the amount will be added to your wallet.",
        "ru": "✅ Чек о пополнении кошелька получен и отправлен на проверку.\nПосле подтверждения сумма будет зачислена на ваш кошелёк.",
    },
    "service_received": {
        "fa": "✅ یک سرویس («{plan}») به حساب تو منتقل شد! از «سرویس‌های من» ببینش.",
        "en": "✅ A service (“{plan}”) was transferred to your account! See it in “My services”.",
        "ru": "✅ Услуга («{plan}») передана на ваш аккаунт! Посмотрите её в разделе «Мои услуги».",
    },
    "renewed": {
        "fa": "🎉 سرویس با موفقیت تمدید شد (پرداخت از کیف پول، Mini App)!\n\nپلن جدید: {plan}\nمبلغ: {amount} تومان",
        "en": "🎉 Your service was renewed (paid from wallet, Mini App)!\n\nNew plan: {plan}\nAmount: {amount} Toman",
        "ru": "🎉 Услуга продлена (оплата с кошелька, Mini App)!\n\nНовый тариф: {plan}\nСумма: {amount} томан",
    },
    "ticket_created": {
        "fa": "✅ تیکت #{id} ثبت شد. به محض پاسخ پشتیبانی بهت خبر می‌دم.",
        "en": "✅ Ticket #{id} created. I'll let you know as soon as support replies.",
        "ru": "✅ Тикет #{id} создан. Сообщу, как только поддержка ответит.",
    },
    "ticket_reply": {
        "fa": "✅ پیامت به تیکت #{id} اضافه شد.",
        "en": "✅ Your message was added to ticket #{id}.",
        "ru": "✅ Ваше сообщение добавлено в тикет #{id}.",
    },
    "wallet_received": {
        "fa": "💰 مبلغ {amount} تومان به کیف پولت واریز شد (انتقال از کاربر دیگر).",
        "en": "💰 {amount} Toman was added to your wallet (transfer from another user).",
        "ru": "💰 {amount} томан зачислено на ваш кошелёк (перевод от другого пользователя).",
    },
}


def _umsg(user_id: int, key: str, **kw) -> str:
    lang = db.get_user_language(user_id)
    if lang not in ("fa", "en", "ru"):
        lang = "fa"
    if "plan" in kw:
        kw["plan"] = _localize_plan_title(kw["plan"], lang)
    return _MSGS[key][lang].format(**kw)


# ---------------- کمکی‌های «سرویس‌های من» ----------------
def _force_join_ok(user_id: int) -> bool:
    """
    مثل check_and_prompt_join خود بات: ادمین‌ها معاف‌اند و اگه بررسی عضویت ممکن نبود (مثلاً بات ادمین کانال
    نیست) کاربر رو بلاک نمی‌کنیم. قبلاً مینی‌اپ این شرط رو اصلاً چک نمی‌کرد.
    """
    if not FORCE_JOIN_CHANNEL or user_id in ADMIN_IDS or not BOT_TOKEN:
        return True
    try:
        with httpx.Client(timeout=8) as client:
            r = client.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember",
                params={"chat_id": REQUIRED_CHANNEL_USERNAME, "user_id": user_id},
            )
        data = r.json()
        if data.get("ok"):
            return (data.get("result") or {}).get("status") in ("member", "administrator", "creator")
    except Exception:
        pass
    return True


_wallet_lock = Lock()  # جلوی دوبار کسر شدن پول وقتی کاربر دکمه‌ی تمدید رو پشت‌سرهم می‌زنه


def _owned_sub(user_id: int, sub_id: int):
    """سرویس رو فقط وقتی برمی‌گردونه که واقعاً مال همین کاربر باشه"""
    sub = db.get_subscription(sub_id)
    if not sub or sub["user_id"] != user_id:
        return None
    return sub


def _drop_services_cache(*user_ids):
    for uid in user_ids:
        _services_cache.pop(uid, None)


def _service_fields(s, stats) -> dict:
    """
    فیلدهای مشترک هر سرویس (هم برای لیست و هم برای صفحه‌ی جزئیات)؛ دقیقاً
    همون منطقی که قبلاً داخل api_services بود، فقط یه‌جا جمع شده.
    """
    from service_stats import remaining_days, grace_left_seconds

    plan = get_plan(s["plan_id"])
    total_gb = plan["gb"] if plan else None
    if total_gb is None and s["plan_id"] == "trial":
        # سرویس تست رایگان توی PLANS تعریف نشده؛ سقفش همون FREE_TRIAL_GB خود بات‌ـه
        total_gb = FREE_TRIAL_GB
    remaining_days_val = remaining_days(s)
    remaining_gb = stats["remaining_gb"]
    # بعد از تمدید، سقف واقعیِ پنل = حجم پلن + باقی‌ماندهٔ قبلی (نه عدد خام پلن)؛
    # وگرنه مینی‌اپ چیزی مثل «۱۵ گیگ از ۱۰ گیگ» نشون میده.
    real_total = stats.get("real_limit_gb")
    if real_total:
        total_gb = real_total
    if total_gb and remaining_gb is not None and remaining_gb > total_gb:
        total_gb = remaining_gb

    if remaining_gb is None:
        status = "unlimited"
    elif remaining_gb <= 0:
        status = "depleted"
    elif total_gb and (remaining_gb / total_gb * 100) <= (100 - DATA_WARNING_THRESHOLD_PERCENT):
        status = "warn"
    else:
        status = "active"
    # «منقضی» فقط وقتی که زمان واقعاً تموم شده؛ remaining_days رو به روز رُند می‌کنیم و
    # سرویسی که کمتر از ۲۴ ساعت مونده بهش هم ۰ روز نشون میده ولی هنوز فعاله
    if s["expire_at"] and s["expire_at"] <= int(time.time()):
        status = "expired"
    # سرویس پایان‌یافته (در مهلت تمدید): وضعیتش طبق دلیل پایان مشخصه، حتی اگه
    # پنل به‌خاطر غیرفعال‌بودن عدد حجم درستی برنگردونه
    grace_left = grace_left_seconds(s)
    if grace_left is not None and status not in ("expired", "depleted"):
        status = "depleted" if s["ended_reason"] == "data" else "expired"

    return {
        "sub_id": s["sub_id"],
        "username": s["marzban_username"] or "",
        "plan_title": s["plan_title"],
        "remaining_days": remaining_days_val,
        # ثانیه‌های مونده تا پایان اعتبار (None = بدون انقضا)؛ برای نمایش «ساعت/دقیقه» وقتی کمتر از یک روز مونده
        "expires_in": (max(0, int(s["expire_at"]) - int(time.time())) if s["expire_at"] else None),
        "remaining_gb": remaining_gb,
        "total_gb": total_gb,
        "status": status,
        # برای هشدار «موجودی برای تمدید خودکار کافی نیست» تو مینی‌اپ
        "auto_renew": bool(s["auto_renew"]) and bool(s["expire_at"]) and plan is not None,
        "renew_price": plan["price"] if plan else None,
        # مهلت تمدید: ثانیه‌های مونده تا حذف قطعی (None = سرویس هنوز پایان نیافته)
        "grace_left": grace_left,
        "ended_reason": (s["ended_reason"] or None) if grace_left is not None else None,
    }


# ---------------- API ----------------
@app.route("/api/profile")
def api_profile():
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    user_row = db.get_user(user_id)
    balance = db.get_wallet_balance(user_id)
    subs_count = len(db.get_user_subscriptions(user_id))
    spent = db.get_lifetime_spent(user_id)
    tier = db.get_loyalty_tier_for_amount(spent)
    next_tier = next((t for t in LOYALTY_TIERS if t["min_spent"] > spent), None)

    # آخرین پاداش ماهانه‌ی باشگاه مشتریان (همون که جاب ماهانه‌ی بات به کیف پول اضافه می‌کنه)؛
    # مینی‌اپ ازش برای انیمیشن «سکه‌ی پاداش» موقع اولین ورود بعد از دریافتش استفاده می‌کنه
    with db.get_conn() as conn:
        bonus = conn.execute(
            "SELECT amount, created_at FROM wallet_transactions WHERE user_id = ? AND tx_type = 'loyalty_bonus' "
            "ORDER BY created_at DESC, tx_id DESC LIMIT 1",
            (user_id,),
        ).fetchone()

    return jsonify({
        "user_id": user_id,
        "first_name": (user_row["first_name"] if user_row else "") or "",
        "last_bonus": {"amount": bonus["amount"], "at": bonus["created_at"]} if bonus else None,
        "balance": balance,
        "services_count": subs_count,
        "joined_at": user_row["joined_at"] if user_row else None,
        "is_reseller": bool(user_row and user_row["is_reseller"]),
        "language": db.get_user_language(user_id),
        "spent": spent,
        "tier": {"name": tier["name"], "emoji": tier["emoji"]} if tier else None,
        "next_tier": (
            {
                "name": next_tier["name"], "emoji": next_tier["emoji"],
                "remaining": next_tier["min_spent"] - spent, "threshold": next_tier["min_spent"],
            }
            if next_tier else None
        ),
    })


_services_cache = {}  # {user_id: (timestamp, data)} - جلوی درخواست تکراری به پنل رو می‌گیره
_SERVICES_CACHE_TTL = 20  # ثانیه - همون فاصله‌ی جاب چک حجم خود بات


@app.route("/api/services")
def api_services():
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    cached = _services_cache.get(user_id)
    if cached and (time.time() - cached[0]) < _SERVICES_CACHE_TTL:
        return jsonify({"services": cached[1]})

    # سبک و بدون وابستگی به پکیج telegram - برای همین از user.py مستقیم
    # ایمپورت نمی‌کنیم، بلکه از همون ماژول مشترک service_stats.py که
    # خود user.py هم داره ازش استفاده می‌کنه.
    from service_stats import fetch_live_stats, remaining_days

    subs = db.get_user_subscriptions(user_id)

    async def build():
        # همه‌ی درخواست‌های پنل (یکی به‌ازای هر سرویس) رو هم‌زمان می‌فرستیم
        # نه پشت‌سرهم، وگرنه یکی با ۲۰ تا سرویس باید چند ثانیه صبر کنه.
        stats_list = await asyncio.gather(*[fetch_live_stats(s, include_config=False) for s in subs])
        result = []
        for s, stats in zip(subs, stats_list):
            result.append(_service_fields(s, stats))
        return result

    services = asyncio.run(build())
    _services_cache[user_id] = (time.time(), services)
    return jsonify({"services": services})


@app.route("/api/shop")
def api_shop():
    plans = [
        {
            "id": p["id"], "title": p["title"], "gb": p["gb"], "days": p["days"],
            "price": p["price"], "duration_months": p["duration_months"],
        }
        for p in PLANS
    ]
    return jsonify({
        "plans": plans,
        "location": PREMIUM_LOCATION_NAME, "price_per_gb": PRICE_PER_GB_TOMAN,
        "trial_days": FREE_TRIAL_DAYS, "trial_mb": FREE_TRIAL_MB,
    })


@app.route("/api/apps")
def api_apps():
    """راهنمای اتصال هر پلتفرم - محتوای عمومی، نیازی به احراز هویت نداره"""
    return jsonify({"guides": PLATFORM_GUIDES, "support_link": SUPPORT_LINK})


@app.route("/api/payment-info")
def api_payment_info():
    """شماره کارت/صاحب کارت + وضعیت روش‌های پرداخت - دقیقاً هماهنگ با خود بات"""
    from config import AUTOSMS_ENABLED, MANUAL_CARD_PAYMENT_ENABLED, CRYPTO_PAYMENT_ENABLED, TONPAYS_ENABLED, WINAPAY_ENABLED
    return jsonify({
        "card_number": CARD_NUMBER, "card_holder": CARD_HOLDER,
        "autosms_enabled": AUTOSMS_ENABLED,
        "manual_card_enabled": MANUAL_CARD_PAYMENT_ENABLED,
        "crypto_enabled": CRYPTO_PAYMENT_ENABLED,
        "tonpays_enabled": TONPAYS_ENABLED,
        "winapay_enabled": WINAPAY_ENABLED,
    })


@app.route("/api/referral")
def api_referral():
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    total_count = db.count_referrals(user_id)
    month_count = db.get_referral_count_this_month(user_id)

    top = db.get_referral_leaderboard_this_month(limit=10)
    leaderboard = []
    my_rank = None
    for i, row in enumerate(top):
        u = db.get_user(row["user_id"])
        leaderboard.append({
            "rank": i + 1,
            "name": (u["first_name"] if u else None) or "کاربر",
            "count": row["c"],
            "is_me": row["user_id"] == user_id,
        })
        if row["user_id"] == user_id:
            my_rank = i + 1

    return jsonify({
        "link": link,
        "total_count": total_count,
        "month_count": month_count,
        "leaderboard": leaderboard,
        "my_rank": my_rank,
    })


@app.route("/api/reseller")
def api_reseller():
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    is_res = db.is_reseller(user_id)
    balance = db.get_wallet_balance(user_id)   # شرط درخواست نمایندگی: موجودیِ همین لحظه (نه مجموع شارژهای قبلی)
    pending = db.get_pending_reseller_request(user_id)

    catalog = [
        {
            "id": p["id"], "title": p["title"], "gb": p["gb"], "days": p["days"],
            "months": p.get("duration_months"), "price": p["reseller_price"],
        }
        for p in PLANS
    ] if is_res else []

    return jsonify({
        "is_reseller": is_res,
        "balance": balance,
        "lifetime_topup": balance,   # نام قدیمی برای سازگاری؛ حالا همون موجودی لحظه‌ایه
        "threshold": RESELLER_MIN_TOPUP_TOMAN,
        "eligible": balance >= RESELLER_MIN_TOPUP_TOMAN,
        "has_pending_request": bool(pending),
        "catalog": catalog,
        "location": PREMIUM_LOCATION_NAME,
        "price_per_gb": RESELLER_PRICE_PER_GB_TOMAN,
        "retail_per_gb": PRICE_PER_GB_TOMAN,
    })


@app.route("/api/wallet")
def api_wallet():
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    balance = db.get_wallet_balance(user_id)
    rows = db.get_wallet_transactions(user_id, limit=15)
    tx = [
        {
            "amount": r["amount"], "tx_type": r["tx_type"],
            "description": r["description"], "created_at": r["created_at"],
        }
        for r in rows
    ]
    return jsonify({"balance": balance, "transactions": tx, "support_link": SUPPORT_LINK})


@app.route("/api/trial", methods=["POST"])
def api_trial():
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    # مثل بات: تست روی یه لوکیشن گرفته میشه (فعلاً فقط «germany»)؛ لوکیشن جدید فقط باید به این لیست اضافه بشه
    if (body.get("location") or "germany") not in ("germany",):
        return jsonify({"error": "bad_location"}), 400

    if db.has_used_trial(user_id):
        return jsonify({"error": "already_used"}), 400

    if not _force_join_ok(user_id):
        return jsonify({"error": "join_required", "link": REQUIRED_CHANNEL_LINK}), 403

    # ثبت اتمیک: درخواست‌های همزمان نمی‌تونن چند تست بسازن
    if not db.claim_trial(user_id):
        return jsonify({"error": "already_used"}), 400

    try:
        username = panel.generate_username(prefix="trial")
        result = asyncio.run(panel.create_user(username, FREE_TRIAL_DAYS, FREE_TRIAL_GB))
    except PanelError as e:
        db.release_trial(user_id)
        return jsonify({"error": "panel_error", "message": str(e)}), 502
    except Exception:
        db.release_trial(user_id)
        raise

    expire_at = result.get("expire") or 0
    sub_link = result.get("subscription_url", "")
    plan_title = f"تست رایگان ({FREE_TRIAL_DAYS} روزه)"
    new_sub_id = db.create_subscription(
        user_id=user_id, order_id=None, plan_id="trial", marzban_username=username,
        plan_title=plan_title, expire_at=expire_at, sub_link=sub_link,
    )
    _tg_send_message(user_id, _umsg(user_id, "trial_issued", plan=plan_title, link=sub_link))
    return jsonify({"success": True, "sub_id": new_sub_id, "plan_title": plan_title, "sub_link": sub_link})


@app.route("/api/buy", methods=["POST"])
def api_buy():
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    plan = get_plan(body.get("plan_id", ""))
    if not plan:
        return jsonify({"error": "plan_not_found"}), 404

    custom_name = (body.get("custom_name") or "").strip() or None
    discount_code = (body.get("discount_code") or "").strip().upper() or None
    discount_percent = None
    if discount_code:
        ok, err, row = db.validate_discount_code(discount_code, user_id)
        if ok:
            discount_percent = row["percent"]
        else:
            discount_code = None

    price = plan["price"]
    if discount_percent:
        price = round(plan["price"] * (100 - discount_percent) / 100)

    if not _force_join_ok(user_id):
        return jsonify({"error": "join_required", "link": REQUIRED_CHANNEL_LINK}), 403

    balance = db.get_wallet_balance(user_id)
    if balance < price:
        return jsonify({"error": "insufficient_balance", "balance": balance, "price": price}), 402

    # کسر اتمیک قبل از ساخت سرویس: درخواست‌های همزمان نمی‌تونن یک موجودی رو چندبار خرج کنن
    if not db.try_debit_wallet(user_id, price, "purchase", f"خرید {plan['title']} (Mini App)"):
        return jsonify({"error": "insufficient_balance", "balance": db.get_wallet_balance(user_id), "price": price}), 402
    if discount_code:
        used_ok, _err = db.consume_discount_use(discount_code, user_id)
        if not used_ok:
            db.adjust_wallet_balance_logged(user_id, price, "refund", "برگشت مبلغ: کد تخفیف معتبر نبود")
            return jsonify({"error": "discount_invalid"}), 400

    def _refund():
        db.adjust_wallet_balance_logged(user_id, price, "refund", "برگشت مبلغ: خطا در صدور سرویس (Mini App)")
        if discount_code:
            db.release_discount_use(discount_code, user_id)

    try:
        username = panel.generate_username(prefix=custom_name) if custom_name else panel.generate_username()
        result = asyncio.run(panel.create_user(username, plan["days"], plan["gb"], display_name=custom_name))
    except PanelError as e:
        _refund()
        return jsonify({"error": "panel_error", "message": str(e)}), 502
    except Exception:
        _refund()
        raise

    order_id = db.create_order(
        user_id, plan["id"], None, kind="new",
        custom_name=custom_name, discount_code=discount_code, discount_percent=discount_percent,
    )
    db.set_order_status(order_id, "approved", user_id)
    expire_at = result.get("expire") or 0
    sub_link = result.get("subscription_url", "")
    new_sub_id = db.create_subscription(
        user_id=user_id, order_id=order_id, plan_id=plan["id"], marzban_username=username,
        plan_title=plan["title"], expire_at=expire_at, sub_link=sub_link,
    )
    db.maybe_reward_referrer(user_id)

    _tg_send_message(user_id, _umsg(user_id, "bought", plan=plan["title"], amount=f"{price:,}", link=sub_link))
    try:
        _tg_send_message(
            ADMIN_CHAT_ID,
            f"🔔 خرید با کیف پول از Mini App (نیازی به تایید نیست)\nپلن: {plan['title']}\nمبلغ: {price:,} تومان\nکاربر: {user_id}",
        )
    except Exception:
        pass

    return jsonify({
        "success": True, "sub_id": new_sub_id, "plan_title": plan["title"],
        "sub_link": sub_link, "balance": db.get_wallet_balance(user_id),
    })


_CUSTOM_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,19}$")


@app.route("/api/name/check")
def api_name_check():
    """چک اسم دلخواه سرویس (قالب + آزاد بودن) قبل از رفتن به مرحله‌ی پرداخت"""
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    name = (request.args.get("name") or "").strip().lower()
    if not _CUSTOM_NAME_RE.match(name):
        return jsonify({"ok": False, "error": "bad_name"})
    if db.username_taken(name):
        return jsonify({"ok": False, "error": "name_taken"})
    return jsonify({"ok": True, "name": name})


@app.route("/api/reseller/buy", methods=["POST"])
def api_reseller_buy():
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    if not db.is_reseller(user_id):
        return jsonify({"error": "not_reseller"}), 403

    plan = get_plan(body.get("plan_id", ""))
    if not plan:
        return jsonify({"error": "plan_not_found"}), 404

    custom_name = (body.get("custom_name") or "").strip().lower() or None
    if custom_name:
        if not _CUSTOM_NAME_RE.match(custom_name):
            return jsonify({"error": "bad_name"}), 400
        if db.username_taken(custom_name):
            return jsonify({"error": "name_taken"}), 409

    price = plan["reseller_price"]
    balance = db.get_wallet_balance(user_id)
    if balance < price:
        return jsonify({"error": "insufficient_balance", "balance": balance, "price": price}), 402

    # کسر اتمیک قبل از ساخت سرویس (جلوی خرید همزمان با یک موجودی)
    if not db.try_debit_wallet(user_id, price, "reseller_purchase", f"خرید نمایندگی {plan['title']} (Mini App)"):
        return jsonify({"error": "insufficient_balance", "balance": db.get_wallet_balance(user_id), "price": price}), 402

    try:
        # اسم دلخواه = همون اسم (بدون پسوند)؛ رندوم = فقط ۸ حرف رندوم؛ هیچ‌کدوم اسم برند ما رو ندارن
        username = panel.generate_username(prefix=custom_name) if custom_name else panel.generate_username(bare=True)
        result = asyncio.run(panel.create_user(
            username, plan["days"], plan["gb"], display_name=custom_name, remark_prefix=RESELLER_REMARK_PREFIX,
        ))
    except PanelError as e:
        db.adjust_wallet_balance_logged(user_id, price, "refund", "برگشت مبلغ: خطا در صدور سرویس نمایندگی (Mini App)")
        return jsonify({"error": "panel_error", "message": str(e)}), 502
    except Exception:
        db.adjust_wallet_balance_logged(user_id, price, "refund", "برگشت مبلغ: خطای غیرمنتظره (Mini App)")
        raise

    order_id = db.create_order(user_id, plan["id"], None, kind="new", custom_name=custom_name)
    db.set_order_status(order_id, "approved", user_id)
    expire_at = result.get("expire") or 0
    sub_link = result.get("subscription_url", "")
    new_sub_id = db.create_subscription(
        user_id=user_id, order_id=order_id, plan_id=plan["id"], marzban_username=username,
        plan_title=plan["title"], expire_at=expire_at, sub_link=sub_link,
        remark_prefix=RESELLER_REMARK_PREFIX,
    )
    db.maybe_reward_referrer(user_id)

    _tg_send_message(user_id, _umsg(user_id, "reseller_bought", plan=plan["title"], amount=f"{price:,}", link=sub_link))
    return jsonify({
        "success": True, "sub_id": new_sub_id, "plan_title": plan["title"],
        "sub_link": sub_link, "balance": db.get_wallet_balance(user_id),
    })


@app.route("/api/reseller/request", methods=["POST"])
def api_reseller_request():
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    balance = db.get_wallet_balance(user_id)   # موجودیِ همین لحظه
    if balance < RESELLER_MIN_TOPUP_TOMAN:
        return jsonify({"error": "not_eligible", "threshold": RESELLER_MIN_TOPUP_TOMAN, "topup": balance, "balance": balance}), 403
    if db.get_pending_reseller_request(user_id):
        return jsonify({"error": "pending_exists"}), 409

    message = (body.get("message") or "").strip()
    request_id = db.create_reseller_request(user_id, message)

    user_row = db.get_user(user_id)
    caption = (
        f"🤝 درخواست نمایندگی جدید #{request_id}\n"
        f"کاربر: {(user_row['first_name'] if user_row else '') or ''}\n"
        f"آیدی عددی: {user_id}\n"
        f"مجموع شارژ: {topup:,} تومان\n\n"
        + (f"توضیح: {message}" if message else "بدون توضیح (از Mini App)")
    )
    _tg_send_message(ADMIN_CHAT_ID, caption, reply_markup={
        "inline_keyboard": [[
            {"text": "تایید نمایندگی", "callback_data": f"resellerapprove:{request_id}"},
            {"text": "رد درخواست", "callback_data": f"resellerreject:{request_id}"},
        ]]
    })
    return jsonify({"success": True})


@app.route("/api/discount/check")
def api_discount_check():
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    code = (request.args.get("code") or "").strip().upper()
    plan_id = request.args.get("plan_id", "")
    if not code or not get_plan(plan_id):
        return jsonify({"ok": False, "error": "not_found"})

    ok, err, row = db.validate_discount_code(code, user_id)
    if not ok:
        return jsonify({"ok": False, "error": err})
    return jsonify({"ok": True, "code": row["code"], "percent": row["percent"]})


def _tg_send_photo(chat_id, file_bytes, filename, caption, reply_markup=None):
    """
    آپلود مستقیم عکس به تلگرام (نه از طریق python-telegram-bot). خروجی
    file_id همون چیزیه که بقیه‌ی سیستم (admin.py) برای رسیدها استفاده می‌کنه،
    پس بعد از این تماس، رسید Mini App دقیقاً مثل رسید ارسالی داخل چت رفتار می‌کنه.
    """
    data = {"chat_id": str(chat_id), "caption": _ph.premium_html(caption), "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(_ph.fix_markup_dict(reply_markup))
    files = {"photo": (filename, file_bytes)}
    with httpx.Client(timeout=30) as client:
        resp = client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", data=data, files=files)
    result = resp.json()
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "sendPhoto failed"))
    msg = result["result"]
    photo_sizes = msg.get("photo") or []
    file_id = photo_sizes[-1]["file_id"] if photo_sizes else None
    return msg["message_id"], file_id


@app.route("/api/receipt-upload", methods=["POST"])
def api_receipt_upload():
    init_data = request.form.get("init_data", "")
    user = _validate_init_data(init_data)
    if not user or "id" not in user:
        return jsonify({"error": "unauthorized"}), 401
    user_id = int(user["id"])

    photo = request.files.get("photo")
    plan_id = request.form.get("plan_id", "")
    custom_name = (request.form.get("custom_name") or "").strip() or None
    discount_code = (request.form.get("discount_code") or "").strip().upper() or None

    plan = get_plan(plan_id)
    if not plan:
        return jsonify({"error": "plan_not_found"}), 404
    if not photo:
        return jsonify({"error": "no_photo"}), 400

    # تمدید: مثل خود بات، اسم دلخواه و کد تخفیف نداره و سفارش به سرویس بسته میشه
    is_renew = request.form.get("kind") == "renew"
    renew_sub_id = None
    if is_renew:
        try:
            renew_sub_id = int(request.form.get("sub_id", 0))
        except (TypeError, ValueError):
            renew_sub_id = 0
        if not _owned_sub(user_id, renew_sub_id):
            return jsonify({"error": "sub_not_found"}), 404
        custom_name = None
        discount_code = None

    discount_percent = None
    if discount_code:
        ok, err, row = db.validate_discount_code(discount_code, user_id)
        if ok:
            discount_percent = row["percent"]
        else:
            discount_code = None

    final_price = plan["price"]
    if discount_percent:
        final_price = round(plan["price"] * (100 - discount_percent) / 100)

    order_id = db.create_order(
        user_id, plan_id, "pending-upload", kind="renew" if is_renew else "new", renew_sub_id=renew_sub_id,
        custom_name=custom_name, discount_code=discount_code, discount_percent=discount_percent,
    )

    discount_line = f"\nکد تخفیف: {discount_code} ({discount_percent}٪)" if discount_code else ""
    caption = (
        f"{'🔄 تمدید سرویس' if is_renew else '🧾 سفارش جدید'} (از Mini App)\n"
        f"سفارش: #{order_id}\n"
        f"کاربر: {(user.get('first_name') or '')} (@{user.get('username') or 'بدون‌یوزرنیم'})\n"
        f"آیدی عددی: {user_id}\n"
        f"پلن: {plan['emoji_tag']} {plan['title']}\n"
        f"مبلغ: {final_price:,} تومان"
        f"{discount_line}"
    )
    try:
        admin_msg_id, file_id = _tg_send_photo(
            ADMIN_CHAT_ID, photo.read(), photo.filename or "receipt.jpg", caption,
            reply_markup={"inline_keyboard": [[
                {"text": "تایید ✅", "callback_data": f"approve:{order_id}"},
                {"text": "رد ❌", "callback_data": f"reject:{order_id}"},
            ]]},
        )
        db.set_order_admin_message(order_id, admin_msg_id)
        if file_id:
            with db.get_conn() as conn:
                conn.execute("UPDATE orders SET receipt_file_id = ? WHERE order_id = ?", (file_id, order_id))
    except Exception:
        return jsonify({"error": "admin_notify_failed", "order_id": order_id}), 502

    _tg_send_message(user_id, _umsg(user_id, "receipt_renew" if is_renew else "receipt_new"))
    return jsonify({"success": True, "order_id": order_id})


@app.route("/api/crypto/invoice", methods=["POST"])
def api_crypto_invoice():
    from config import CRYPTO_PAYMENT_ENABLED, CRYPTO_INVOICE_TIMEOUT_MINUTES, CRYPTO_CURRENCY_LABELS
    import xrocket_client as xrocket

    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    if not CRYPTO_PAYMENT_ENABLED:
        return jsonify({"error": "crypto_disabled"}), 400

    kind = body.get("kind", "new")
    currency = body.get("currency", "")
    plan = None
    custom_name = None
    discount_code = None
    discount_percent = None
    renew_sub_id = None

    if kind == "renew":
        plan = get_plan(body.get("plan_id", ""))
        if not plan:
            return jsonify({"error": "plan_not_found"}), 404
        try:
            renew_sub_id = int(body.get("sub_id", 0))
        except (TypeError, ValueError):
            renew_sub_id = 0
        if not _owned_sub(user_id, renew_sub_id):
            return jsonify({"error": "sub_not_found"}), 404
        amount_toman = plan["price"]
        description = f"تمدید {plan['title']} (Mini App)"
    elif kind == "topup":
        try:
            amount_toman = int(body.get("amount", 0))
        except (TypeError, ValueError):
            amount_toman = 0
        if amount_toman <= 0:
            return jsonify({"error": "invalid_amount"}), 400
        description = "شارژ کیف پول (Mini App)"
    else:
        plan = get_plan(body.get("plan_id", ""))
        if not plan:
            return jsonify({"error": "plan_not_found"}), 404
        custom_name = (body.get("custom_name") or "").strip() or None
        discount_code = (body.get("discount_code") or "").strip().upper() or None
        if discount_code:
            ok, err, row = db.validate_discount_code(discount_code, user_id)
            discount_percent = row["percent"] if ok else None
            if not ok:
                discount_code = None
        amount_toman = plan["price"]
        if discount_percent:
            amount_toman = round(plan["price"] * (100 - discount_percent) / 100)
        description = f"خرید {plan['title']} (Mini App)"

    try:
        invoice = asyncio.run(xrocket.create_invoice(amount_toman, currency, description))
    except xrocket.XRocketError as e:
        return jsonify({"error": "xrocket_error", "message": str(e)}), 502

    db.create_crypto_invoice(
        invoice_id=invoice["invoice_id"], user_id=user_id, chat_id=user_id, message_id=0,
        kind=kind, amount_toman=amount_toman, currency=currency, amount_crypto=invoice["amount_crypto"],
        plan_id=plan["id"] if plan else None, sub_id=renew_sub_id,
        custom_name=custom_name, discount_code=discount_code, discount_percent=discount_percent,
    )
    return jsonify({
        "invoice_id": invoice["invoice_id"], "pay_url": invoice["pay_url"],
        "amount_crypto": invoice["amount_crypto"], "amount_toman": amount_toman,
        "currency_label": CRYPTO_CURRENCY_LABELS.get(currency, currency),
        "timeout_minutes": CRYPTO_INVOICE_TIMEOUT_MINUTES,
    })


@app.route("/api/wallet/topup-receipt", methods=["POST"])
def api_wallet_topup_receipt():
    init_data = request.form.get("init_data", "")
    user = _validate_init_data(init_data)
    if not user or "id" not in user:
        return jsonify({"error": "unauthorized"}), 401
    user_id = int(user["id"])

    photo = request.files.get("photo")
    try:
        amount = int(request.form.get("amount", 0))
    except (TypeError, ValueError):
        amount = 0
    if amount <= 0:
        return jsonify({"error": "invalid_amount"}), 400
    if not photo:
        return jsonify({"error": "no_photo"}), 400

    order_id = db.create_order(user_id, None, "pending-upload", kind="topup", amount=amount)

    caption = (
        f"💳 درخواست شارژ کیف پول (از Mini App)\n"
        f"سفارش: #{order_id}\n"
        f"کاربر: {(user.get('first_name') or '')} (@{user.get('username') or 'بدون‌یوزرنیم'})\n"
        f"آیدی عددی: {user_id}\n"
        f"مبلغ: {amount:,} تومان"
    )
    try:
        admin_msg_id, file_id = _tg_send_photo(
            ADMIN_CHAT_ID, photo.read(), photo.filename or "receipt.jpg", caption,
            reply_markup={"inline_keyboard": [[
                {"text": "تایید ✅", "callback_data": f"approve:{order_id}"},
                {"text": "رد ❌", "callback_data": f"reject:{order_id}"},
            ]]},
        )
        db.set_order_admin_message(order_id, admin_msg_id)
        if file_id:
            with db.get_conn() as conn:
                conn.execute("UPDATE orders SET receipt_file_id = ? WHERE order_id = ?", (file_id, order_id))
    except Exception:
        return jsonify({"error": "admin_notify_failed", "order_id": order_id}), 502

    _tg_send_message(user_id, _umsg(user_id, "receipt_topup"))
    return jsonify({"success": True, "order_id": order_id})


@app.route("/api/crypto/status")
def api_crypto_status():
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    invoice_id = request.args.get("invoice_id", "")
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM crypto_invoices WHERE invoice_id = ? AND user_id = ?", (invoice_id, user_id)
        ).fetchone()
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"status": row["status"]})


@app.route("/api/autosms/invoice", methods=["POST"])
def api_autosms_invoice():
    from config import AUTOSMS_ENABLED, AUTOSMS_INVOICE_TTL_MINUTES
    import autosms_client as autosms
    import datetime
    from zoneinfo import ZoneInfo

    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    if not AUTOSMS_ENABLED:
        return jsonify({"error": "autosms_disabled"}), 400

    kind = body.get("kind", "new")
    plan = None
    custom_name = None
    discount_code = None
    discount_percent = None
    renew_sub_id = None

    if kind == "renew":
        plan = get_plan(body.get("plan_id", ""))
        if not plan:
            return jsonify({"error": "plan_not_found"}), 404
        try:
            renew_sub_id = int(body.get("sub_id", 0))
        except (TypeError, ValueError):
            renew_sub_id = 0
        if not _owned_sub(user_id, renew_sub_id):
            return jsonify({"error": "sub_not_found"}), 404
        amount_toman = plan["price"]
        description = f"تمدید {plan['title']} (Mini App)"
    elif kind == "topup":
        try:
            amount_toman = int(body.get("amount", 0))
        except (TypeError, ValueError):
            amount_toman = 0
        if amount_toman <= 0:
            return jsonify({"error": "invalid_amount"}), 400
        description = "شارژ کیف پول (Mini App)"
    else:
        plan = get_plan(body.get("plan_id", ""))
        if not plan:
            return jsonify({"error": "plan_not_found"}), 404
        custom_name = (body.get("custom_name") or "").strip() or None
        discount_code = (body.get("discount_code") or "").strip().upper() or None
        if discount_code:
            ok, err, row = db.validate_discount_code(discount_code, user_id)
            discount_percent = row["percent"] if ok else None
            if not ok:
                discount_code = None
        amount_toman = plan["price"]
        if discount_percent:
            amount_toman = round(plan["price"] * (100 - discount_percent) / 100)
        description = f"خرید {plan['title']} (Mini App)"

    order_id = autosms.make_order_id(kind, user_id)
    try:
        inv_data = asyncio.run(
            autosms.create_payment(amount_toman, order_id, description, ttl_minutes=AUTOSMS_INVOICE_TTL_MINUTES)
        )
    except autosms.AutoSMSError as e:
        return jsonify({"error": "autosms_error", "message": str(e)}), 502

    authority = inv_data["authority"]
    pay_amount = inv_data["pay_amount_toman"]
    pay_amount_rial = inv_data.get("pay_amount_rial", pay_amount * 10)
    expires_ts = inv_data.get("expires_at", 0)
    expires_at_fa = ""
    if expires_ts:
        expires_at_fa = datetime.datetime.fromtimestamp(
            expires_ts, tz=ZoneInfo("Asia/Tehran")
        ).strftime("%H:%M - %Y/%m/%d")

    # چت‌آیدی همون یوزرآیدیه؛ برای پیوی با بات همیشه یکسانه - دقیقاً مثل کریپتو
    db.create_autosms_invoice(
        authority=authority, order_id=order_id, user_id=user_id, chat_id=user_id, message_id=0,
        kind=kind, base_amount_toman=amount_toman, pay_amount_toman=pay_amount,
        card_number=inv_data["card_number"], card_holder=inv_data["card_holder"],
        expires_at=expires_ts, plan_id=plan["id"] if plan else None, sub_id=renew_sub_id, custom_name=custom_name,
        discount_code=discount_code, discount_percent=discount_percent,
    )

    return jsonify({
        "authority": authority,
        "pay_amount_toman": pay_amount,
        "pay_amount_rial": pay_amount_rial,
        "card_number": inv_data["card_number"],
        "card_holder": inv_data["card_holder"],
        "expires_at_fa": expires_at_fa,
        "ttl_minutes": AUTOSMS_INVOICE_TTL_MINUTES,
    })


@app.route("/api/autosms/status")
def api_autosms_status():
    """
    فقط وضعیتِ ذخیره‌شده تو دیتابیس رو می‌خونه (همون چیزی که job دوره‌ای/وب‌هوکِ
    بات به‌روزش می‌کنه) - دقیقاً هم‌الگو با /api/crypto/status. تحویل واقعی
    (صدور سرویس/شارژ کیف‌پول) همیشه سمت بات انجام می‌شه و نتیجه‌ش تو همون چت
    براش پیام میاد.
    """
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    authority = request.args.get("authority", "")
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM autosms_invoices WHERE authority = ? AND user_id = ?", (authority, user_id)
        ).fetchone()
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"status": row["status"]})


@app.route("/api/tonpays/invoice", methods=["POST"])
def api_tonpays_invoice():
    from config import TONPAYS_ENABLED, TONPAYS_INVOICE_TIMEOUT_MINUTES, PUBLIC_BASE_URL
    import tonpays_client as tonpays

    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    if not TONPAYS_ENABLED:
        return jsonify({"error": "tonpays_disabled"}), 400

    kind = body.get("kind", "new")
    plan = None
    custom_name = None
    discount_code = None
    discount_percent = None
    renew_sub_id = None

    if kind == "renew":
        plan = get_plan(body.get("plan_id", ""))
        if not plan:
            return jsonify({"error": "plan_not_found"}), 404
        try:
            renew_sub_id = int(body.get("sub_id", 0))
        except (TypeError, ValueError):
            renew_sub_id = 0
        if not _owned_sub(user_id, renew_sub_id):
            return jsonify({"error": "sub_not_found"}), 404
        amount_toman = plan["price"]
    elif kind == "topup":
        try:
            amount_toman = int(body.get("amount", 0))
        except (TypeError, ValueError):
            amount_toman = 0
        if amount_toman <= 0:
            return jsonify({"error": "invalid_amount"}), 400
    else:
        plan = get_plan(body.get("plan_id", ""))
        if not plan:
            return jsonify({"error": "plan_not_found"}), 404
        custom_name = (body.get("custom_name") or "").strip() or None
        discount_code = (body.get("discount_code") or "").strip().upper() or None
        if discount_code:
            ok, err, row = db.validate_discount_code(discount_code, user_id)
            discount_percent = row["percent"] if ok else None
            if not ok:
                discount_code = None
        amount_toman = plan["price"]
        if discount_percent:
            amount_toman = round(plan["price"] * (100 - discount_percent) / 100)

    order_id = tonpays.make_order_id()
    callback_url = f"{PUBLIC_BASE_URL}/webhook/tonpays" if PUBLIC_BASE_URL else None
    try:
        invoice = asyncio.run(tonpays.create_invoice(amount_toman, order_id, callback_url=callback_url))
    except tonpays.TonPaysError as e:
        return jsonify({"error": "tonpays_error", "message": str(e)}), 502

    invoice_id = invoice["invoice_id"]
    final_amount = invoice.get("final_amount") or amount_toman
    request_amount = invoice.get("request_amount") or amount_toman

    # چت‌آیدی همون یوزرآیدیه؛ برای پیوی با بات همیشه یکسانه - دقیقاً مثل کریپتو/AutoSMS
    db.create_tonpays_invoice(
        invoice_id=invoice_id, order_id=order_id, user_id=user_id, chat_id=user_id, message_id=0,
        kind=kind, request_amount=request_amount, final_amount=final_amount,
        plan_id=plan["id"] if plan else None, sub_id=renew_sub_id, custom_name=custom_name,
        discount_code=discount_code, discount_percent=discount_percent,
    )

    return jsonify({
        "invoice_id": invoice_id,
        "invoice_url": invoice["invoice_url"],
        "payment_url": invoice.get("payment_url"),
        "card_number": invoice.get("card_number"),
        "card_name": invoice.get("card_name"),
        "final_amount": final_amount,
        "timeout_minutes": TONPAYS_INVOICE_TIMEOUT_MINUTES,
    })


@app.route("/api/tonpays/status")
def api_tonpays_status():
    """
    فقط وضعیتِ ذخیره‌شده تو دیتابیس رو می‌خونه (همون چیزی که job دوره‌ای/وب‌هوکِ
    بات به‌روزش می‌کنه) - دقیقاً هم‌الگو با /api/crypto/status و /api/autosms/status.
    تحویل واقعی (صدور سرویس/شارژ کیف‌پول) همیشه سمت بات انجام می‌شه و نتیجه‌ش
    تو همون چت براش پیام میاد.
    """
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    invoice_id = request.args.get("invoice_id", "")
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM tonpays_invoices WHERE invoice_id = ? AND user_id = ?", (invoice_id, user_id)
        ).fetchone()
    if not row:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"status": row["status"]})


# ---------------- درگاه ویناپی (WinaPay) ----------------
def _winapay_finalize(authority: str) -> dict:
    """استعلام از ویناپی + تحویل (اگه پرداخت قطعی بود). منطق مشترک تو winapay_pay.try_finalize"""
    from config import BOT_TOKEN
    from telegram import Bot
    import winapay_pay

    async def _run():
        async with Bot(BOT_TOKEN) as bot:
            return await winapay_pay.try_finalize(bot, authority)

    return asyncio.run(_run())


@app.route("/api/winapay/invoice", methods=["POST"])
def api_winapay_invoice():
    from config import WINAPAY_ENABLED, WINAPAY_INVOICE_TIMEOUT_MINUTES
    import winapay_client as winapay
    import winapay_pay

    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    if not WINAPAY_ENABLED:
        return jsonify({"error": "winapay_disabled"}), 400

    kind = body.get("kind", "new")
    plan = None
    custom_name = None
    discount_code = None
    discount_percent = None
    renew_sub_id = None

    if kind == "renew":
        plan = get_plan(body.get("plan_id", ""))
        if not plan:
            return jsonify({"error": "plan_not_found"}), 404
        try:
            renew_sub_id = int(body.get("sub_id", 0))
        except (TypeError, ValueError):
            renew_sub_id = 0
        if not _owned_sub(user_id, renew_sub_id):
            return jsonify({"error": "sub_not_found"}), 404
        amount_toman = plan["price"]
    elif kind == "topup":
        try:
            amount_toman = int(body.get("amount", 0))
        except (TypeError, ValueError):
            amount_toman = 0
        if amount_toman <= 0:
            return jsonify({"error": "invalid_amount"}), 400
    else:
        kind = "new"
        plan = get_plan(body.get("plan_id", ""))
        if not plan:
            return jsonify({"error": "plan_not_found"}), 404
        custom_name = (body.get("custom_name") or "").strip() or None
        discount_code = (body.get("discount_code") or "").strip().upper() or None
        if discount_code:
            ok, err, row = db.validate_discount_code(discount_code, user_id)
            discount_percent = row["percent"] if ok else None
            if not ok:
                discount_code = None
        amount_toman = plan["price"]
        if discount_percent:
            amount_toman = round(plan["price"] * (100 - discount_percent) / 100)

    try:
        invoice = asyncio.run(winapay_pay.create_invoice(
            user_id=user_id, chat_id=user_id, message_id=0, kind=kind, amount_toman=amount_toman,
            plan_id=plan["id"] if plan else None, sub_id=renew_sub_id, custom_name=custom_name,
            discount_code=discount_code, discount_percent=discount_percent,
        ))
    except winapay.WinaPayError as e:
        return jsonify({"error": "winapay_error", "message": str(e)}), 502

    return jsonify({
        "authority": invoice["authority"],
        "payment_url": invoice["payment_url"],
        "amount": amount_toman,
        "timeout_minutes": WINAPAY_INVOICE_TIMEOUT_MINUTES,
    })


_WINAPAY_LAST_CHECK = {}   # authority -> آخرین زمان استعلام (جلوگیری از فشار روی ویناپی موقع پولینگ مینی‌اپ)


@app.route("/api/winapay/status")
def api_winapay_status():
    """
    وضعیت فاکتور برای مینی‌اپ. اگه هنوز pending باشه، حداکثر هر ۳ ثانیه یه بار از خودِ ویناپی
    استعلام میکنه (و در صورت پرداخت، همون‌جا تحویل میده). نتیجه‌ی تحویل تو چت بات هم پیام میشه.
    """
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    authority = request.args.get("authority", "")
    inv = db.get_winapay_invoice(authority) if authority else None
    if not inv or inv["user_id"] != user_id:
        return jsonify({"error": "not_found"}), 404
    if inv["status"] == "pending":
        now = time.time()
        if now - _WINAPAY_LAST_CHECK.get(authority, 0) >= 3:
            _WINAPAY_LAST_CHECK[authority] = now
            try:
                _winapay_finalize(authority)
            except Exception:
                pass          # job دوره‌ای بات پشتیبانه
            inv = db.get_winapay_invoice(authority)
    return jsonify({"status": inv["status"]})


def _winapay_page(ok: bool, title: str, text: str, ref_id: str = "") -> str:
    from config import BOT_USERNAME
    color = "#3FD2C0" if ok else "#FF8A80"
    mark = "✓" if ok else "!"
    ref = f'<p class="r">شماره پیگیری: <b dir="ltr">{_html.escape(str(ref_id))}</b></p>' if ref_id else ""
    link = f"https://t.me/{BOT_USERNAME}" if BOT_USERNAME else "https://t.me"
    return f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Noordis VPN</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;background:#0A1436;color:#F3F5FF;
font-family:system-ui,-apple-system,"Segoe UI",Tahoma,sans-serif;line-height:1.9}}
.c{{width:100%;max-width:380px;text-align:center}}
.i{{width:72px;height:72px;margin:0 auto 14px;border-radius:50%;display:grid;place-items:center;font-size:36px;font-weight:800;color:#0E1A45;background:{color}}}
h1{{font-size:20px;margin:0 0 6px}}p{{margin:0 0 14px;color:rgba(243,245,255,.75);font-size:14px}}.r b{{color:#F3F5FF}}
a.b{{display:block;padding:14px;border-radius:14px;font-weight:700;font-size:15px;text-decoration:none;color:#fff;background:linear-gradient(135deg,#7B5FFF,#4A8BFF)}}
</style></head><body><div class="c">
<div class="i">{mark}</div><h1>{_html.escape(title)}</h1><p>{_html.escape(text)}</p>{ref}
<a class="b" href="{_html.escape(link, quote=True)}">بازگشت به تلگرام</a>
</div></body></html>"""


@app.route("/webhook/winapay", methods=["GET", "POST"])
def webhook_winapay():
    """
    آدرس بازگشت ویناپی: بعد از پرداخت، مرورگر کاربر با POST (Authority, PaymentStatus, InvoiceID)
    اینجا میاد. این فیلدها از مرورگر کاربرن و قابل‌جعل‌ان؛ پس فقط برای پیدا کردن فاکتور استفاده میشن و
    هر تحویلی فقط با استعلام مستقیم PaymentVerification (و مبلغ ذخیره‌شده‌ی خودمون) انجام میشه.
    """
    authority = (request.values.get("Authority") or "").strip()
    pay_status = (request.values.get("PaymentStatus") or "").strip().upper()
    inv = db.get_winapay_invoice(authority) if authority else None
    if not inv:
        return _winapay_page(False, "فاکتور پیدا نشد", "این لینک معتبر نیست یا منقضی شده. به ربات برگرد و دوباره تلاش کن."), 404
    if pay_status != "OK":
        return _winapay_page(False, "پرداخت انجام نشد", "پرداخت لغو شد یا ناموفق بود. اگه مبلغی از حسابت کم شده، تا چند دقیقه دیگه به‌صورت خودکار تایید میشه یا برگشت داده میشه.")
    try:
        res = _winapay_finalize(authority)
    except Exception:
        res = {"state": "error"}
    state = res.get("state")
    if state in ("paid", "already"):
        done = "کیف پول شارژ شد" if inv["kind"] == "topup" else "سرویس برات آماده شد"
        return _winapay_page(True, "پرداخت موفق بود", f"{done}. جزئیات رو تو چت ربات برات فرستادیم.", res.get("ref_id") or "")
    if state == "expired":
        return _winapay_page(False, "فاکتور منقضی شده", "این فاکتور منقضی شده. به ربات برگرد و دوباره تلاش کن.")
    return _winapay_page(True, "پرداخت ثبت شد", "تایید نهایی چند لحظه طول می‌کشه. به ربات برگرد؛ به‌محض تایید، سرویس/شارژ برات ارسال میشه.")


# ---------------- جزئیات و مدیریت سرویس (همون قابلیت‌های «سرویس‌های من» خود بات) ----------------
def _sub_or_error(user_id: int, sub_id: int):
    sub = _owned_sub(user_id, sub_id)
    if not sub:
        return None, (jsonify({"error": "not_found"}), 404)
    return sub, None


@app.route("/api/service/<int:sub_id>")
def api_service_detail(sub_id):
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    sub, err = _sub_or_error(user_id, sub_id)
    if err:
        return err

    from service_stats import fetch_live_stats

    stats = asyncio.run(fetch_live_stats(sub))
    data = _service_fields(sub, stats)
    data.update({
        "plan_id": sub["plan_id"],
        "expire_at": sub["expire_at"] or 0,
        "subscription_url": stats["subscription_url"] or sub["sub_link"],
        "connection_link": stats["connection_link"] or "",
        "auto_renew": bool(sub["auto_renew"]),
        # مثل بات: تمدید خودکار فقط وقتی معنی داره که سرویس تاریخ انقضا داشته باشه؛
        # و چون تمدید خودکار با قیمت پلن حساب میشه، پلنِ تعریف‌نشده (مثل تست رایگان) نمی‌تونه
        "can_auto_renew": bool(sub["expire_at"]) and get_plan(sub["plan_id"]) is not None,
        "note": sub["note"] or "",
        "can_check_online": PANEL_TYPE == "sanaei",
        "created_at": sub["created_at"] or 0,
        # پیشنهاد پلن بر اساس مصرف واقعی (None = داده‌ی کافی نیست یا سرویس تموم‌شده)
        "recommendation": _plan_recommendation(sub, stats, data),
    })
    return jsonify(data)


def _plan_recommendation(sub, stats, data):
    """
    همون منطق بات (smart_plans)؛ خطا فقط باعث میشه پیشنهاد نیاد و هیچ‌وقت جلوی
    باز شدن صفحه‌ی سرویس رو نمی‌گیره.
    """
    try:
        import logging
        import usage_history
        import smart_plans

        week = usage_history.get_week(sub["sub_id"])
        return smart_plans.build_recommendation(
            sub["plan_id"], data.get("remaining_gb"), data.get("remaining_days"),
            week["avg_gb"], week["tracked_days"],
        )
    except Exception:
        import logging

        logging.getLogger(__name__).warning("محاسبه‌ی پیشنهاد پلن برای سرویس #%s ناموفق بود", sub["sub_id"])
        return None


@app.route("/api/service/<int:sub_id>/qr")
def api_service_qr(sub_id):
    """همون QR ای که بات موقع تحویل سرویس می‌فرسته (لینک اشتراک؛ اگه نبود کانفیگ اتصال)"""
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    sub, err = _sub_or_error(user_id, sub_id)
    if err:
        return err

    link = sub["sub_link"]
    if not link:
        from service_stats import fetch_live_stats
        link = asyncio.run(fetch_live_stats(sub))["connection_link"]
    if not link:
        return jsonify({"error": "no_link"}), 404

    import io
    import qrcode

    buf = io.BytesIO()
    qrcode.make(link).save(buf, format="PNG")
    resp = app.response_class(buf.getvalue(), mimetype="image/png")
    resp.headers["Cache-Control"] = "private, no-store"
    return resp


@app.route("/api/service/<int:sub_id>/autorenew", methods=["POST"])
def api_service_autorenew(sub_id):
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    sub, err = _sub_or_error(user_id, sub_id)
    if err:
        return err

    enabled = bool(body.get("enabled"))
    if enabled:
        if not sub["expire_at"]:
            return jsonify({"error": "no_expiry"}), 400
        if not get_plan(sub["plan_id"]):
            return jsonify({"error": "no_plan"}), 400
    db.set_auto_renew(sub_id, enabled)
    return jsonify({"success": True, "auto_renew": enabled})


@app.route("/api/service/<int:sub_id>/note", methods=["POST"])
def api_service_note(sub_id):
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    sub, err = _sub_or_error(user_id, sub_id)
    if err:
        return err

    note = str(body.get("note") or "").strip()[:500]
    db.set_subscription_note(sub_id, note)
    return jsonify({"success": True, "note": note})


@app.route("/api/service/<int:sub_id>/refresh-link", methods=["POST"])
def api_service_refresh_link(sub_id):
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    sub, err = _sub_or_error(user_id, sub_id)
    if err:
        return err

    try:
        result = asyncio.run(panel.revoke_subscription(sub["marzban_username"]))
    except PanelError as e:
        return jsonify({"error": "panel_error", "message": str(e)}), 502

    new_link = result.get("subscription_url", sub["sub_link"])
    db.update_subscription_link(sub_id, new_link)
    _drop_services_cache(user_id)
    return jsonify({
        "success": True, "subscription_url": new_link,
        "connection_link": result.get("connection_link") or "",
    })


@app.route("/api/service/<int:sub_id>/online")
def api_service_online(sub_id):
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    sub, err = _sub_or_error(user_id, sub_id)
    if err:
        return err
    if PANEL_TYPE != "sanaei":
        # مثل بات: این قابلیت فقط روی پنل سنایی واقعیه
        return jsonify({"error": "not_supported"}), 400

    try:
        online = asyncio.run(panel.get_online_status(sub["marzban_username"]))
    except PanelError as e:
        return jsonify({"error": "panel_error", "message": str(e)}), 502
    return jsonify({"online": bool(online)})


_CARD_LAST = {}   # آخرین ارسال کارت دعوت هر کاربر (جلوگیری از اسپم)
_CARD_TEXT = {
    "fa": "کارت دعوت نوردیس\nاین تصویر رو فوروارد کن یا ذخیره‌اش کن و برای دوستات بفرست.\n{link}",
    "en": "Noordis invite card\nForward this image or save it and send it to your friends.\n{link}",
    "ru": "Пригласительная карточка Noordis\nПерешлите это изображение или сохраните его и отправьте друзьям.\n{link}",
}


@app.route("/api/referral/card", methods=["POST"])
def api_referral_card():
    """کارت دعوتِ ساخته‌شده تو مینی‌اپ رو به‌صورت عکس تو چت خود کاربر با بات میفرسته.
    (وب‌ویوی تلگرام اشتراک‌گذاری/دانلود فایل رو درست پشتیبانی نمیکنه؛ ولی تو چت میشه فوروارد یا ذخیره‌اش کرد.)"""
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    now = time.time()
    if now - _CARD_LAST.get(user_id, 0) < 15:
        return jsonify({"error": "لطفاً چند ثانیه صبر کن و دوباره امتحان کن."}), 429
    raw = str(body.get("image", ""))
    if len(raw) > 4_500_000:
        return jsonify({"error": "bad image"}), 400
    if raw.startswith("data:image/jpeg;base64,"):
        prefix, magic, ext = "data:image/jpeg;base64,", b"\xff\xd8\xff", "jpg"
    elif raw.startswith("data:image/png;base64,"):
        prefix, magic, ext = "data:image/png;base64,", b"\x89PNG\r\n\x1a\n", "png"
    else:
        return jsonify({"error": "bad image"}), 400
    try:
        data = base64.b64decode(raw[len(prefix):], validate=True)
    except Exception:
        return jsonify({"error": "bad image"}), 400
    if not data.startswith(magic) or len(data) > 3_000_000:
        return jsonify({"error": "bad image"}), 400
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    lang = db.get_user_language(user_id)
    caption = _html.escape(_CARD_TEXT.get(lang, _CARD_TEXT["fa"]).format(link=link), quote=False)
    _CARD_LAST[user_id] = now
    try:
        _tg_send_photo(user_id, data, f"noordis-invite.{ext}", caption)
    except Exception:
        _CARD_LAST.pop(user_id, None)
        return jsonify({"error": "ارسال کارت ممکن نشد. اول یه بار ربات رو استارت کن و دوباره امتحان کن."}), 502
    return jsonify({"ok": True})


# ---------------- اشتراک کارت دعوت تو استوری تلگرام ----------------
# shareToStory تلگرام فقط «آدرس عمومیِ» تصویر رو می‌گیره (نه فایل)؛ پس کارت رو چند دقیقه روی سرور
# نگه می‌داریم و یه لینک غیرقابل‌حدس بهش می‌دیم. فایل بعد از ۳۰ دقیقه پاک میشه.
_STORY_TTL = 1800
_STORY_LAST = {}   # آخرین ساخت استوری هر کاربر (جلوگیری از اسپم)
_STORY_NAME_RE = re.compile(r"^[a-f0-9]{32}\.(png|jpg)$")


def _story_dir() -> str:
    import tempfile

    d = os.path.join(tempfile.gettempdir(), "noordis_story")
    os.makedirs(d, exist_ok=True)
    return d


def _public_base():
    """آدرس عمومی سرور برای ساخت لینک استوری؛ None اگه هیچ‌کدوم از PUBLIC_BASE_URL/MINIAPP_URL تنظیم نباشه"""
    from urllib.parse import urlsplit
    from config import PUBLIC_BASE_URL, MINIAPP_URL

    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    if MINIAPP_URL:
        u = urlsplit(MINIAPP_URL)
        if u.scheme and u.netloc:
            return f"{u.scheme}://{u.netloc}"
    return None


def _cleanup_story_dir():
    d, now = _story_dir(), time.time()
    for name in os.listdir(d):
        path = os.path.join(d, name)
        try:
            if now - os.path.getmtime(path) > _STORY_TTL:
                os.remove(path)
        except OSError:
            pass


@app.route("/api/referral/story", methods=["POST"])
def api_referral_story():
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    base = _public_base()
    if not base:
        return jsonify({"error": "story_unavailable"}), 503
    now = time.time()
    if now - _STORY_LAST.get(user_id, 0) < 8:
        return jsonify({"error": "لطفاً چند ثانیه صبر کن و دوباره امتحان کن."}), 429

    raw = str(body.get("image", ""))
    if len(raw) > 4_500_000:
        return jsonify({"error": "bad image"}), 400
    if raw.startswith("data:image/jpeg;base64,"):
        prefix, magic, ext = "data:image/jpeg;base64,", b"\xff\xd8\xff", "jpg"
    elif raw.startswith("data:image/png;base64,"):
        prefix, magic, ext = "data:image/png;base64,", b"\x89PNG\r\n\x1a\n", "png"
    else:
        return jsonify({"error": "bad image"}), 400
    try:
        data = base64.b64decode(raw[len(prefix):], validate=True)
    except Exception:
        return jsonify({"error": "bad image"}), 400
    if not data.startswith(magic) or len(data) > 3_000_000:
        return jsonify({"error": "bad image"}), 400

    import secrets

    _cleanup_story_dir()
    name = f"{secrets.token_hex(16)}.{ext}"
    with open(os.path.join(_story_dir(), name), "wb") as f:
        f.write(data)
    _STORY_LAST[user_id] = now
    return jsonify({
        "url": f"{base}/story/{name}",
        "link": f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}",
    })


@app.route("/story/<name>")
def story_media(name):
    """عکس موقتِ کارت دعوت برای سرورهای تلگرام (فقط اسم‌های ۳۲‌حرفیِ تصادفی)"""
    if not _STORY_NAME_RE.match(name):
        return jsonify({"error": "not_found"}), 404
    path = os.path.join(_story_dir(), name)
    if not os.path.isfile(path) or time.time() - os.path.getmtime(path) > _STORY_TTL:
        return jsonify({"error": "not_found"}), 404
    resp = send_from_directory(_story_dir(), name)
    resp.headers["Cache-Control"] = "public, max-age=600"
    return resp


# ---------------- افزودن مینی‌اپ به صفحه‌ی اصلی گوشی ----------------
@app.route("/api/homescreen/added", methods=["POST"])
def api_homescreen_added():
    """کلاینت وقتی تلگرام رویداد homeScreenAdded رو داد صدا می‌زنه؛ فقط یه مهر دستاورد ثبت میشه"""
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    db.set_user_flag(user_id, "home_screen")
    return jsonify({"ok": True})


@app.route("/api/service/<int:sub_id>/usage")
def api_service_usage(sub_id):
    """مصرف روزانه‌ی ۷ روز اخیر (برای نمودار و پیش‌بینی اتمام حجم)"""
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    sub, err = _sub_or_error(user_id, sub_id)
    if err:
        return err
    import usage_history
    try:
        return jsonify(usage_history.get_week(sub_id))
    except Exception:
        return jsonify({"days": [], "avg_gb": 0, "tracked_days": 0})


@app.route("/api/service/<int:sub_id>/transfer", methods=["POST"])
def api_service_transfer(sub_id):
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    sub, err = _sub_or_error(user_id, sub_id)
    if err:
        return err

    raw = str(body.get("target_id", "")).strip()
    if not raw.isdigit():
        return jsonify({"error": "invalid_id"}), 400
    target_id = int(raw)
    if target_id == user_id:
        return jsonify({"error": "self_transfer"}), 400
    if not db.get_user(target_id):
        # مثل بات: اون کاربر باید قبلاً حداقل یه‌بار به بات /start زده باشه
        return jsonify({"error": "target_not_found"}), 404

    db.transfer_subscription(sub_id, target_id)
    _drop_services_cache(user_id, target_id)
    _tg_send_message(target_id, _umsg(target_id, "service_received", plan=sub["plan_title"]))
    return jsonify({"success": True})


@app.route("/api/service/<int:sub_id>/delete", methods=["POST"])
def api_service_delete(sub_id):
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    sub, err = _sub_or_error(user_id, sub_id)
    if err:
        return err

    if sub["marzban_username"]:
        try:
            asyncio.run(panel.remove_user(sub["marzban_username"]))
        except PanelError as e:
            return jsonify({"error": "panel_error", "message": str(e)}), 502

    db.delete_subscription(sub_id)
    _drop_services_cache(user_id)
    return jsonify({"success": True})


@app.route("/api/service/<int:sub_id>/renew", methods=["POST"])
def api_service_renew(sub_id):
    """تمدید با کیف پول - همون منطق pay_renew_with_wallet خود بات (بدون کد تخفیف، مثل بات)"""
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    sub, err = _sub_or_error(user_id, sub_id)
    if err:
        return err

    plan = get_plan(body.get("plan_id", ""))
    if not plan:
        return jsonify({"error": "plan_not_found"}), 404

    with _wallet_lock:
        balance = db.get_wallet_balance(user_id)
        if balance < plan["price"]:
            return jsonify({"error": "insufficient_balance", "balance": balance, "price": plan["price"]}), 402

        # کسر اتمیک قبل از تمدید (قفل فقط بین درخواست‌های مینی‌اپه؛ بات هم از همین موجودی خرج می‌کنه)
        if not db.try_debit_wallet(user_id, plan["price"], "purchase", f"تمدید {plan['title']} (Mini App)"):
            return jsonify({"error": "insufficient_balance", "balance": db.get_wallet_balance(user_id), "price": plan["price"]}), 402

        try:
            result = asyncio.run(panel.modify_user(sub["marzban_username"], plan["days"], plan["gb"]))
        except PanelError as e:
            db.adjust_wallet_balance_logged(user_id, plan["price"], "refund", "برگشت مبلغ: خطا در تمدید (Mini App)")
            return jsonify({"error": "panel_error", "message": str(e)}), 502
        except Exception:
            db.adjust_wallet_balance_logged(user_id, plan["price"], "refund", "برگشت مبلغ: خطای غیرمنتظره (Mini App)")
            raise

        order_id = db.create_order(user_id, plan["id"], None, kind="renew", renew_sub_id=sub_id)
        db.set_order_status(order_id, "approved", user_id)
        expire_at = result.get("expire") or 0
        db.update_subscription_after_renew(sub_id, expire_at, plan["title"], plan["id"])
        sub_link = result.get("subscription_url", "")
        if sub_link:
            db.update_subscription_link(sub_id, sub_link)

    _drop_services_cache(user_id)
    _tg_send_message(user_id, _umsg(user_id, "renewed", plan=plan["title"], amount=f"{plan['price']:,}"))
    try:
        _tg_send_message(
            ADMIN_CHAT_ID,
            f"🔔 تمدید با کیف پول از Mini App (نیازی به تایید نیست)\nپلن: {plan['title']}\n"
            f"مبلغ: {plan['price']:,} تومان\nکاربر: {user_id}",
        )
    except Exception:
        pass
    return jsonify({
        "success": True, "plan_title": plan["title"], "expire_at": expire_at, "total_gb": result.get("total_gb"),
        "subscription_url": sub_link or sub["sub_link"], "balance": db.get_wallet_balance(user_id),
    })


# ---------------- پشتیبانی: سوالات متداول و تیکت (همون منطق بات) ----------------
_TICKET_MAX_LEN = 2000


def _notify_admin_ticket(ticket_id: int, user_id: int, text: str, is_reply: bool = False):
    """همون پیامی که خود بات برای ادمین می‌فرسته (با دکمه‌های «پاسخ بده / بستن تیکت» خود بات)"""
    u = db.get_user(user_id)
    first_name = (u["first_name"] if u and u["first_name"] else "")
    username = (u["username"] if u and u["username"] else "بدون‌یوزرنیم")
    title = f"💬 پیام جدید در تیکت #{ticket_id}" if is_reply else f"🎫 تیکت جدید #{ticket_id}"
    caption = (
        f"{title}\n"
        f"کاربر: {first_name} (@{username})\n"
        f"آیدی عددی: {user_id}\n\n"
        f"{text}"
    )
    msg_id = _tg_send_message_id(
        ADMIN_CHAT_ID, caption,
        reply_markup={"inline_keyboard": [[
            {"text": "پاسخ بده", "callback_data": f"ticketreply_admin:{ticket_id}"},
            {"text": "بستن تیکت", "callback_data": f"ticketclose:{ticket_id}"},
        ]]},
    )
    if msg_id:
        db.set_ticket_admin_message(ticket_id, msg_id)


def _clean_ticket_text(body: dict):
    text = str((body or {}).get("text") or "").strip()
    if not text:
        return None, (jsonify({"error": "empty"}), 400)
    if len(text) > _TICKET_MAX_LEN:
        return None, (jsonify({"error": "too_long", "max": _TICKET_MAX_LEN}), 400)
    return text, None


def _owned_ticket(user_id: int, ticket_id: int):
    t = db.get_ticket(ticket_id)
    if not t or t["user_id"] != user_id:
        return None
    return t


@app.route("/api/support")
def api_support():
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"faq": FAQ_ITEMS, "support_link": SUPPORT_LINK})


@app.route("/api/tickets")
def api_tickets():
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"tickets": [
        {
            "ticket_id": t["ticket_id"], "subject": (t["subject"] or "")[:160], "status": t["status"],
            "created_at": t["created_at"], "updated_at": t["updated_at"],
        }
        for t in db.get_user_tickets(user_id)
    ]})


@app.route("/api/tickets/<int:ticket_id>")
def api_ticket_detail(ticket_id):
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    t = _owned_ticket(user_id, ticket_id)
    if not t:
        return jsonify({"error": "not_found"}), 404
    return jsonify({
        "ticket_id": t["ticket_id"], "status": t["status"],
        "created_at": t["created_at"], "updated_at": t["updated_at"],
        "messages": [
            {"sender": m["sender"], "text": m["text"], "created_at": m["created_at"]}
            for m in db.get_ticket_messages(ticket_id)
        ],
    })


@app.route("/api/tickets", methods=["POST"])
def api_ticket_create():
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    text, err = _clean_ticket_text(body)
    if err:
        return err

    # دوبار کلیک: اگه همین متن همین الان (کمتر از ۲۰ ثانیه پیش) ثبت شده، تیکت دومی نمی‌سازیم
    latest = db.get_user_tickets(user_id, limit=1)
    if latest and latest[0]["subject"] == text and time.time() - (latest[0]["created_at"] or 0) < 20:
        return jsonify({"success": True, "ticket_id": latest[0]["ticket_id"], "duplicate": True})

    ticket_id = db.create_ticket(user_id, text)
    _tg_send_message(user_id, _umsg(user_id, "ticket_created", id=ticket_id))
    _notify_admin_ticket(ticket_id, user_id, text)
    return jsonify({"success": True, "ticket_id": ticket_id})


@app.route("/api/tickets/<int:ticket_id>/reply", methods=["POST"])
def api_ticket_reply(ticket_id):
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    t = _owned_ticket(user_id, ticket_id)
    if not t:
        return jsonify({"error": "not_found"}), 404
    if t["status"] == "closed":
        return jsonify({"error": "closed"}), 400
    text, err = _clean_ticket_text(body)
    if err:
        return err

    msgs = db.get_ticket_messages(ticket_id)
    if msgs and msgs[-1]["sender"] == "user" and msgs[-1]["text"] == text and time.time() - (msgs[-1]["created_at"] or 0) < 20:
        return jsonify({"success": True, "duplicate": True})

    db.add_ticket_message(ticket_id, "user", text)
    db.set_ticket_status(ticket_id, "open")
    _tg_send_message(user_id, _umsg(user_id, "ticket_reply", id=ticket_id))
    _notify_admin_ticket(ticket_id, user_id, text, is_reply=True)
    return jsonify({"success": True})


# ---------------- انتقال موجودی کیف پول به کاربر دیگر (همون مراحل بات) ----------------
def _wallet_transfer_target(user_id: int, raw):
    """مثل بات: فقط عدد، نه به خودت، و اون کاربر باید قبلاً به بات /start زده باشه"""
    raw = str(raw if raw is not None else "").strip()
    if not raw.isdigit():
        return None, (jsonify({"error": "invalid_id"}), 400)
    target_id = int(raw)
    if target_id == user_id:
        return None, (jsonify({"error": "self_transfer"}), 400)
    if not db.get_user(target_id):
        return None, (jsonify({"error": "target_not_found"}), 404)
    return target_id, None


@app.route("/api/wallet/transfer/check", methods=["POST"])
def api_wallet_transfer_check():
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    target_id, err = _wallet_transfer_target(user_id, body.get("target_id"))
    if err:
        return err
    return jsonify({"ok": True, "target_id": target_id, "balance": db.get_wallet_balance(user_id)})


@app.route("/api/wallet/transfer", methods=["POST"])
def api_wallet_transfer():
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    target_id, err = _wallet_transfer_target(user_id, body.get("target_id"))
    if err:
        return err

    raw = str(body.get("amount", "")).strip().replace(",", "").replace("،", "")
    if not raw.isdigit() or int(raw) <= 0:
        return jsonify({"error": "invalid_amount"}), 400
    amount = int(raw)

    balance = db.get_wallet_balance(user_id)
    if amount > balance or not db.transfer_wallet_balance(user_id, target_id, amount):
        return jsonify({"error": "insufficient_balance", "balance": db.get_wallet_balance(user_id)}), 402

    _tg_send_message(target_id, _umsg(target_id, "wallet_received", amount=f"{amount:,}"))
    return jsonify({"success": True, "amount": amount, "balance": db.get_wallet_balance(user_id)})


# ---------------- پاداش روزانه (زنجیره‌ی روزها) ----------------
@app.route("/api/checkin")
def api_checkin_state():
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    import daily_checkin

    return jsonify(daily_checkin.get_state(user_id))


@app.route("/api/checkin", methods=["POST"])
def api_checkin_claim():
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    import daily_checkin

    result = daily_checkin.claim(user_id)
    if result.get("enabled") is False:
        return jsonify({"error": "disabled"}), 404
    return jsonify(result)


# ---------------- باشگاه مشتریان (همون داده‌ها و منطق show_loyalty_hub بات) ----------------
_loyalty_cache = {"ts": 0, "totals": {}}
_LOYALTY_CACHE_TTL = 30  # ثانیه؛ مجموع خرید همه‌ی کاربرا رو هر بار از اول حساب نمی‌کنیم


def _lifetime_totals() -> dict:
    now = time.time()
    if now - _loyalty_cache["ts"] > _LOYALTY_CACHE_TTL:
        _loyalty_cache["totals"] = db.get_all_lifetime_spent()
        _loyalty_cache["ts"] = now
    return _loyalty_cache["totals"]


@app.route("/api/loyalty")
def api_loyalty():
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    totals = _lifetime_totals()
    spent = db.get_lifetime_spent(user_id)   # مقدار تازه‌ی خود کاربر (کش فقط برای رتبه‌بندی همه‌ست)
    tier = db.get_loyalty_tier_for_amount(spent)
    tier_index = next((i for i, t in enumerate(LOYALTY_TIERS) if tier and t["name"] == tier["name"]), None)
    next_tier = next((t for t in LOYALTY_TIERS if t["min_spent"] > spent), None)

    top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:10]
    leaderboard = []
    for i, (uid, total) in enumerate(top):
        u = db.get_user(uid)
        u_tier = db.get_loyalty_tier_for_amount(total)
        leaderboard.append({
            "rank": i + 1,
            "name": (u["first_name"] if u and u["first_name"] else "کاربر"),
            "tier_index": next((k for k, t in enumerate(LOYALTY_TIERS) if u_tier and t["name"] == u_tier["name"]), None),
            "is_me": uid == user_id,
        })
    in_top = any(e["is_me"] for e in leaderboard)
    my_total = totals.get(user_id, 0)
    my_rank = (1 + sum(1 for v in totals.values() if v > my_total)) if my_total > 0 else None

    return jsonify({
        "tiers": [
            {"index": i, "name": t["name"], "emoji": t["emoji"], "min_spent": t["min_spent"], "monthly_bonus": t["monthly_bonus"]}
            for i, t in enumerate(LOYALTY_TIERS)
        ],
        "spent": spent,
        "tier_index": tier_index,
        "next_tier": (
            {"index": LOYALTY_TIERS.index(next_tier), "name": next_tier["name"], "emoji": next_tier["emoji"],
             "min_spent": next_tier["min_spent"], "remaining": next_tier["min_spent"] - spent}
            if next_tier else None
        ),
        "maxed": bool(tier and not next_tier),
        "monthly_bonus": tier["monthly_bonus"] if tier else 0,
        "leaderboard": leaderboard,
        "in_top": in_top,
        "my_rank": my_rank,
    })


# ---------------- تنظیمات حساب و زبان (همون فیلد users.language که بات ازش استفاده می‌کنه) ----------------
def _main_reply_keyboard_json(lang: str):
    """
    همون کیبورد ثابت پایین صفحه‌ی خود بات (keyboards.main_reply_keyboard) به زبان انتخابی؛
    اگه به هر دلیلی ساخته نشد، فقط پیام بدون کیبورد فرستاده میشه.
    """
    try:
        from keyboards import main_reply_keyboard
        return main_reply_keyboard(lang).to_dict()
    except Exception:
        return None


@app.route("/api/settings")
def api_settings():
    tg_user = _get_authed_user()
    if not tg_user:
        return jsonify({"error": "unauthorized"}), 401
    user_id = int(tg_user["id"])
    row = db.get_user(user_id)
    return jsonify({
        "user_id": user_id,
        "first_name": tg_user.get("first_name") or (row["first_name"] if row and row["first_name"] else ""),
        "username": tg_user.get("username") or (row["username"] if row and row["username"] else ""),
        "joined_at": row["joined_at"] if row else None,
        "language": db.get_user_language(user_id),
        "languages": [
            {"code": c, "label": LANG_LABELS[c], "name": LANG_LABELS[c].split(" ", 1)[-1]}
            for c in SUPPORTED_LANGS
        ],
    })


@app.route("/api/settings/language", methods=["POST"])
def api_settings_language():
    body = request.get_json(silent=True) or {}
    user_id = _get_authed_body_user_id(body)
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401
    lang = str(body.get("language") or "").strip()
    if lang not in SUPPORTED_LANGS:
        return jsonify({"error": "invalid_language"}), 400

    changed = db.get_user_language(user_id) != lang
    db.set_user_language(user_id, lang)
    if changed:
        # مثل بات: پیام تاییدِ خود بات (i18n) + کیبورد ثابت پایین صفحه به زبان جدید
        _tg_send_message(user_id, i18n_t("language_set", lang), reply_markup=_main_reply_keyboard_json(lang))
    return jsonify({"success": True, "language": lang, "changed": changed})


# ---------------- مهرهای گذرنامه (نشان‌های افتخاری؛ فقط از روی داده‌های موجود محاسبه میشن و به هیچ قانون مالی‌ای دست نمی‌زنن) ----------------
@app.route("/api/stamps")
def api_stamps():
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    with db.get_conn() as conn:
        counts = {
            r["kind"]: r["c"]
            for r in conn.execute(
                "SELECT kind, COUNT(*) AS c FROM orders WHERE user_id = ? AND status = 'approved' GROUP BY kind",
                (user_id,),
            ).fetchall()
        }
    user_row = db.get_user(user_id)
    joined_at = (user_row["joined_at"] if user_row else None) or 0
    age_days = (time.time() - joined_at) / 86400 if joined_at else 0
    spent = db.get_lifetime_spent(user_id)
    referrals = db.count_referrals(user_id)

    checkin_row = db.get_checkin_row(user_id)
    stamps = [
        {"id": "trial", "earned": db.has_used_trial(user_id)},
        {"id": "first_topup", "earned": db.get_lifetime_topup(user_id) > 0},
        {"id": "first_buy", "earned": counts.get("new", 0) >= 1},
        {"id": "first_renew", "earned": counts.get("renew", 0) >= 1},
        {"id": "first_referral", "earned": referrals >= 1},
        {"id": "referrals_5", "earned": referrals >= 5},
    ]
    for i, t in enumerate(LOYALTY_TIERS):
        stamps.append({"id": f"tier_{i}", "earned": spent >= t["min_spent"], "name": t["name"]})
    stamps += [
        {"id": "month_1", "earned": age_days >= 30},
        {"id": "year_1", "earned": age_days >= 365},
        {"id": "home_screen", "earned": db.has_user_flag(user_id, "home_screen")},
        {"id": "streak_7", "earned": bool(checkin_row and checkin_row["best"] >= 7)},
    ]
    return jsonify({"stamps": stamps, "earned": sum(1 for x in stamps if x["earned"]), "total": len(stamps)})


# ---------------- بنرهای اعلان (از داخل بات با /newbanner و /banners مدیریت میشن) ----------------
@app.route("/api/banners")
def api_banners():
    user_id = _get_authed_user_id()
    if not user_id:
        return jsonify({"error": "unauthorized"}), 401

    def variant(title, body):
        return {"title": title, "body": body or ""} if title else None

    out = []
    now = int(time.time())
    for b in db.get_active_banners():
        item = {
            "id": b["banner_id"], "theme": b["theme"], "action": b["action"], "url": b["url"],
            "fa": variant(b["title_fa"], b["body_fa"]),
            "en": variant(b["title_en"], b["body_en"]),
            "ru": variant(b["title_ru"], b["body_ru"]),
        }
        # کمپین تخفیف: کد + شمارنده‌ی معکوس (ثانیه‌های مونده؛ نه ساعت دیوار، تا اختلاف ساعت گوشی مهم نباشه)
        if b["kind"] == "campaign" and b["code"] and b["expires_at"]:
            dc = db.get_discount_code(b["code"])
            if (dc and dc["active"] and (dc["max_uses"] is None or dc["used_count"] < dc["max_uses"])
                    and not db.has_user_used_discount(dc["code"], user_id)):   # کسی که کد رو مصرف کرده، بنر ساده می‌بینه
                item["code"] = dc["code"]
                item["percent"] = dc["percent"]
                item["ends_in"] = max(0, int(b["expires_at"]) - now)
        out.append(item)
    return jsonify({"banners": out})


@app.route("/webhook/autosms", methods=["POST"])
def webhook_autosms():
    """
    وب‌هوک آنی AutoSMS - همون لحظه‌ای که پیامک بانکی تشخیص داده بشه صدا زده می‌شه.
    این کاملاً «مکمل»ه: حتی اگه این هیچ‌وقت نرسه (PUBLIC_BASE_URL تنظیم نشده، یا
    خود سرویس بیرونی نتونه به سرور ما وصل بشه)، job دوره‌ای داخل بات هم همین
    فاکتورها رو هر ۴۵ ثانیه بررسی و نهایی می‌کنه - پس تحویل خدمت هیچ‌وقت گیر
    نمی‌مونه، این فقط سرعتش رو از چند ثانیه به لحظه‌ای می‌رسونه.
    """
    import autosms_client

    raw = request.get_data()
    sig = request.headers.get("X-Signature", "")
    if not autosms_client.verify_webhook_signature(raw, sig):
        return jsonify({"ok": False, "error": "bad_signature"}), 403

    payload = request.get_json(silent=True) or {}
    if payload.get("status") != "paid":
        return jsonify({"ok": True})

    authority = payload.get("authority", "")
    inv = db.get_autosms_invoice(authority)
    if not inv or inv["status"] != "pending":
        return jsonify({"ok": True})  # قبلاً تحویل داده شده یا فاکتور ناشناسه

    from config import BOT_TOKEN
    from telegram import Bot
    from user import _fulfill_autosms_invoice

    async def _deliver():
        async with Bot(BOT_TOKEN) as bot:
            class _Ctx:
                pass
            ctx = _Ctx()
            ctx.bot = bot
            text = await _fulfill_autosms_invoice(ctx, inv)
            try:
                await bot.send_message(chat_id=inv["chat_id"], text=text, parse_mode="HTML")
            except Exception:
                pass

    try:
        asyncio.run(_deliver())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True})


@app.route("/webhook/tonpays", methods=["POST"])
def webhook_tonpays():
    """
    وب‌هوک TonPays - وقتی فاکتور تایید/رد/منقضی میشه صدا زده میشه.
    برخلاف AutoSMS، این وب‌هوک هیچ امضایی نداره (نه HMAC، نه هیچ هدر دیگه‌ای)
    پس هیچ‌وقت مستقیم به فیلد paid تو بدنه‌ش اعتماد نمی‌کنیم - فقط به‌عنوان
    محرک یه استعلام فوری از خودِ TonPays (با کلید API خودمون) استفاده میشه،
    و فقط بر اساس همون پاسخ معتبر سرویس نهایی میشه. این کاملاً «مکمل»ه: حتی
    اگه این هیچ‌وقت نرسه، job دوره‌ای داخل بات هم همین فاکتورها رو هر ۴۵ ثانیه
    بررسی و نهایی می‌کنه - پس تحویل خدمت هیچ‌وقت گیر نمی‌مونه.
    """
    import tonpays_client as tonpays

    payload = request.get_json(silent=True) or {}
    invoice_id = payload.get("invoice_id", "")
    if not invoice_id:
        return jsonify({"ok": True})

    inv = db.get_tonpays_invoice(invoice_id)
    if not inv or inv["status"] != "pending":
        return jsonify({"ok": True})  # قبلاً تحویل داده شده یا فاکتور ناشناسه

    from config import BOT_TOKEN
    from telegram import Bot
    from user import _fulfill_tonpays_invoice

    async def _deliver():
        try:
            result = await tonpays.check_invoice(invoice_id)
        except tonpays.TonPaysError:
            return  # job دوره‌ای بعداً دوباره امتحان می‌کنه

        if tonpays.is_terminal_failure(result.get("status")):
            db.set_tonpays_invoice_status(invoice_id, "expired")
            return
        if not result.get("paid"):
            return

        fresh = db.get_tonpays_invoice(invoice_id)
        if not fresh or fresh["status"] != "pending":
            return

        async with Bot(BOT_TOKEN) as bot:
            class _Ctx:
                pass
            ctx = _Ctx()
            ctx.bot = bot
            text = await _fulfill_tonpays_invoice(ctx, fresh)
            try:
                await bot.send_message(chat_id=fresh["chat_id"], text=text, parse_mode="HTML")
            except Exception:
                pass

    try:
        asyncio.run(_deliver())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True})


def run():
    # threaded=True: بدون این، Flask فقط یه درخواست رو در آن واحد جواب
    # می‌ده و بقیه صف می‌کشن؛ برای Mini App که چند کاربر هم‌زمان بازش
    # می‌کنن، این تنظیم لازمه.
    app.run(host="0.0.0.0", port=MINIAPP_PORT, threaded=True)


def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
