"""
کلاینت ساده برای اتصال به API پنل Marzban
مستندات API پنل معمولا در آدرس زیر در دسترسه (بعد از بالا آوردن پنل):
    https://YOUR-PANEL-DOMAIN/docs

نکته مهم: بسته به نسخه‌ی Marzban که نصب کردی، ممکنه بعضی فیلدها
(مثل ساختار دقیق proxies) کمی فرق کنه. حتما یک بار با یک درخواست
تستی (مثلا از همون صفحه‌ی /docs) خروجی واقعی رو چک کن.
"""
import time
import random
import string

import httpx

from config import (
    MARZBAN_URL,
    MARZBAN_USERNAME,
    MARZBAN_PASSWORD,
    MARZBAN_PROTOCOLS,
    MARZBAN_USERNAME_PREFIX,
    DEMO_MODE,
)


class MarzbanError(Exception):
    pass


class MarzbanClient:
    def __init__(self):
        self._token = None
        self._token_fetched_at = 0
        self._token_ttl = 60 * 50  # هر ۵۰ دقیقه توکن رو تازه می‌کنیم

    async def _get_token(self) -> str:
        now = time.time()
        if self._token and (now - self._token_fetched_at) < self._token_ttl:
            return self._token

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{MARZBAN_URL}/api/admin/token",
                data={
                    "username": MARZBAN_USERNAME,
                    "password": MARZBAN_PASSWORD,
                },
            )
        if resp.status_code != 200:
            raise MarzbanError(
                f"لاگین به پنل مرزبان ناموفق بود ({resp.status_code}): {resp.text}"
            )
        data = resp.json()
        self._token = data["access_token"]
        self._token_fetched_at = now
        return self._token

    async def _auth_headers(self):
        token = await self._get_token()
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def generate_username(prefix: str = MARZBAN_USERNAME_PREFIX) -> str:
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"{prefix}_{suffix}"

    async def create_user(self, username: str, days: int, gb: float) -> dict:
        """
        یک یوزر جدید در پنل مرزبان می‌سازه.
        days=0 یعنی بدون انقضا / gb=0 یعنی حجم نامحدود
        خروجی دیکشنری خام پاسخ پنله (شامل subscription_url)
        """
        expire = 0
        if days and days > 0:
            expire = int(time.time()) + days * 86400

        if DEMO_MODE:
            return {
                "username": username,
                "expire": expire,
                "subscription_url": f"https://demo.noordis.test/sub/{username}",
            }

        headers = await self._auth_headers()

        data_limit = 0
        if gb and gb > 0:
            data_limit = int(round(gb * 1024 ** 3))

        proxies = {p: {} for p in MARZBAN_PROTOCOLS}

        body = {
            "username": username,
            "proxies": proxies,
            "expire": expire,
            "data_limit": data_limit,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
        }

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{MARZBAN_URL}/api/user", json=body, headers=headers
            )

        if resp.status_code not in (200, 201):
            raise MarzbanError(
                f"ساخت یوزر در پنل ناموفق بود ({resp.status_code}): {resp.text}"
            )

        result = resp.json()

        sub_url = result.get("subscription_url", "")
        if sub_url and sub_url.startswith("/"):
            sub_url = f"{MARZBAN_URL}{sub_url}"
        result["subscription_url"] = sub_url

        return result

    async def modify_user(self, username: str, days: int, gb: float, reset_usage: bool = True) -> dict:
        """
        برای تمدید سرویس یک کاربر موجود استفاده می‌شه: تاریخ انقضا و حجم رو
        بر اساس پلن جدید تنظیم می‌کنه و در صورت نیاز مصرف قبلی رو صفر می‌کنه.

        نکته‌ی مهم: اگه کاربر حجم باقی‌مونده از سرویس قبلیش داشته باشه، اون
        رو دور نمی‌ریزیم - به سقف پلن جدید اضافه‌ش می‌کنیم (مثلاً ۵ گیگ
        باقی‌مونده + تمدید با پلن ۱۰ گیگ = ۱۵ گیگ نهایی). روزها همچنان کامل
        از نو حساب میشه (رفتار قبلی، عوض نشده).
        """
        expire = 0
        if days and days > 0:
            expire = int(time.time()) + days * 86400

        if DEMO_MODE:
            return {
                "username": username,
                "expire": expire,
                "subscription_url": f"https://demo.noordis.test/sub/{username}",
            }

        headers = await self._auth_headers()

        data_limit = 0
        if gb and gb > 0:
            data_limit = int(round(gb * 1024 ** 3))

        if data_limit > 0:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    existing_resp = await client.get(f"{MARZBAN_URL}/api/user/{username}", headers=headers)
                if existing_resp.status_code == 200:
                    existing = existing_resp.json()
                    old_limit = int(existing.get("data_limit") or 0)
                    if old_limit > 0:
                        used = int(existing.get("used_traffic") or 0)
                        remaining = max(0, old_limit - used)
                        data_limit += remaining
                    # اگه old_limit == 0 یعنی قبلاً نامحدود بوده - «باقی‌مونده»ی
                    # نامحدود معنی نداره که به یه سقف مشخص اضافه بشه.
            except Exception:
                pass  # اگه استعلام وضعیت فعلی ناموفق بود، حداقل تمدید با سقف پلن جدید (بدون افزودن باقی‌مونده) انجام میشه

        body = {
            "expire": expire,
            "data_limit": data_limit,
            "status": "active",
        }

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.put(
                f"{MARZBAN_URL}/api/user/{username}", json=body, headers=headers
            )

        if resp.status_code != 200:
            raise MarzbanError(
                f"تمدید سرویس ناموفق بود ({resp.status_code}): {resp.text}"
            )

        if reset_usage:
            async with httpx.AsyncClient(timeout=20) as client:
                reset_resp = await client.post(
                    f"{MARZBAN_URL}/api/user/{username}/reset", headers=headers
                )
            # اگه پنل این اندپوینت رو نداشته باشه (نسخه‌های خیلی قدیمی)، فقط از تمدید تاریخ/حجم صرف‌نظر نمی‌کنیم
            if reset_resp.status_code not in (200, 204):
                pass

        result = resp.json()
        sub_url = result.get("subscription_url", "")
        if sub_url and sub_url.startswith("/"):
            sub_url = f"{MARZBAN_URL}{sub_url}"
        result["subscription_url"] = sub_url
        result["expire"] = expire
        result["total_gb"] = round(data_limit / (1024 ** 3), 2) if data_limit > 0 else 0
        return result

    async def get_user(self, username: str, include_config: bool = True) -> dict:
        # نکته: include_config اینجا تاثیری نداره چون API مرزبان همیشه لینک‌ها
        # رو تو همون یه درخواست برمی‌گردونه (درخواست جداگانه‌ای برای اینباند
        # لازم نیست) - این پارامتر فقط برای هم‌شکل‌بودن با sanaei_client.py هست.
        if DEMO_MODE:
            return {
                "username": username,
                "used_traffic": 0,
                "data_limit": 0,
                "links": [
                    f"vless://demo-uuid@demo.noordis.test:443?type=tcp&security=tls#{username}-1",
                    f"vmess://eyJkZW1vIjogdHJ1ZX0=#{username}-2",
                ],
                "subscription_url": f"https://demo.noordis.test/sub/{username}",
                "status": "active",
            }
        headers = await self._auth_headers()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{MARZBAN_URL}/api/user/{username}", headers=headers)
        if resp.status_code != 200:
            raise MarzbanError(f"دریافت اطلاعات یوزر ناموفق بود: {resp.text}")
        return resp.json()

    async def revoke_subscription(self, username: str) -> dict:
        """
        لینک ساب‌اسکریپشن رو باطل و یک لینک جدید تولید می‌کنه (برای وقتی لینک لو رفته
        یا کاربر می‌خواد یه لینک تازه بگیره). در پنل مرزبان معمولا اندپوینت
        POST /api/user/{username}/revoke_sub همین کار رو انجام می‌ده.
        """
        if DEMO_MODE:
            import random as _r
            token = "".join(_r.choices("abcdef0123456789", k=8))
            return {"subscription_url": f"https://demo.noordis.test/sub/{username}-{token}"}

        headers = await self._auth_headers()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{MARZBAN_URL}/api/user/{username}/revoke_sub", headers=headers
            )
        if resp.status_code != 200:
            raise MarzbanError(f"بازتولید لینک ناموفق بود: {resp.text}")
        result = resp.json()
        sub_url = result.get("subscription_url", "")
        if sub_url and sub_url.startswith("/"):
            sub_url = f"{MARZBAN_URL}{sub_url}"
        result["subscription_url"] = sub_url
        return result

    async def set_status(self, username: str, status: str) -> dict:
        """status مثلا: active / disabled"""
        if DEMO_MODE:
            return {"username": username, "status": status}

        headers = await self._auth_headers()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.put(
                f"{MARZBAN_URL}/api/user/{username}", json={"status": status}, headers=headers
            )
        if resp.status_code != 200:
            raise MarzbanError(f"تغییر وضعیت ناموفق بود: {resp.text}")
        return resp.json()

    async def remove_user(self, username: str):
        if DEMO_MODE:
            return
        headers = await self._auth_headers()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.delete(f"{MARZBAN_URL}/api/user/{username}", headers=headers)
        if resp.status_code not in (200, 204):
            raise MarzbanError(f"حذف یوزر ناموفق بود: {resp.text}")

    async def get_online_status(self, username: str) -> bool:
        """
        این قابلیت فعلا فقط برای پنل سنایی پیاده شده (endpoint اختصاصی
        onlines). دکمه‌ی مربوطه تو کیبورد فقط وقتی PANEL_TYPE=sanaei باشه
        نشون داده میشه، پس این تابع عملا نباید صدا زده بشه؛ فقط برای
        سازگاری قرارداد بین دو کلاینت اینجا گذاشته شده.
        """
        raise MarzbanError("بررسی وضعیت آنلاین فعلا فقط برای پنل سنایی پشتیبانی میشه.")


marzban = MarzbanClient()
