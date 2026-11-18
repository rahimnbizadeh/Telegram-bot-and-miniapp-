"""
کلاینت اتصال به پنل سنایی (Sanaei / 3x-ui) - نسخه‌ی جدید API (/panel/api/clients/*) با API Token.
"""
from __future__ import annotations

import time
import random
import string
import json
import re
import uuid as uuid_module
import urllib.parse

import httpx

from config import (
    SANAEI_URL,
    SANAEI_INBOUND_ID,
    SANAEI_USERNAME_PREFIX,
    SANAEI_SUB_BASE_URL,
    SANAEI_SUB_PATH,
    SANAEI_CONNECT_HOST,
    VLESS_REMARK_PREFIX,
    SANAEI_API_TOKEN,
    DEMO_MODE,
)


class SanaeiError(Exception):
    pass


_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# پیشوندهایی که یوزرنیمشون «سیستمی»ـه و همیشه با پسوند رندوم ساخته میشه.
# هر پیشوند دیگه‌ای یعنی «اسم دلخواهِ خودِ کاربر» و همون اسم، بدون پسوند رندوم، یوزرنیم میشه.
_SYSTEM_PREFIXES = {SANAEI_USERNAME_PREFIX, "trial"}
# قالب مجازِ اسم دلخواه (سمت سرور هم چک میشه، چون مینی‌اپ ممکنه مستقیم فراخوانی بشه)
_CUSTOM_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,19}$")


def _rand(k: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=k))


def _extract_client_uuid(client: dict):
    """
    بعضی نسخه‌های پنل، تو فیلد "id" به‌جای UUID واقعی VLESS، شناسه‌ی ردیف
    داخلی کلاینت تو دیتابیس خودشون (یه عدد ساده مثل 13) رو برمی‌گردونن که
    اصلاً به‌کار ساخت لینک کانفیگ نمیاد. این تابع چندتا اسم فیلد محتمل رو
    امتحان می‌کنه و فقط وقتی مقدار واقعاً فرمت UUID داشت قبولش می‌کنه -
    وگرنه None برمی‌گردونه تا caller به‌جای ساختن یه لینک خراب، ساکت بمونه.
    """
    for key in ("uuid", "clientId", "client_id", "id"):
        val = client.get(key)
        if isinstance(val, str) and _UUID_RE.match(val):
            return val
    return None


class SanaeiClient:
    def __init__(self):
        pass

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {SANAEI_API_TOKEN}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {}) or {}
        headers.update(self._headers())
        async with httpx.AsyncClient(timeout=20, verify=False) as client:
            resp = await client.request(method, f"{SANAEI_URL}{path}", headers=headers, **kwargs)
        return resp

    @staticmethod
    def _safe_json(resp: httpx.Response) -> dict:
        try:
            return resp.json()
        except Exception:
            raise SanaeiError(
                f"پاسخ غیرمنتظره/خالی از پنل سنایی دریافت شد (status {resp.status_code}): "
                f"{resp.text[:300]!r}"
            )

    @staticmethod
    def generate_username(prefix: str = SANAEI_USERNAME_PREFIX, bare: bool = False) -> str:
        """
        - پیش‌فرض یا prefix="trial": یوزرنیم سیستمی با پسوند رندوم (مثل noordis_ab12cd34).
        - bare=True: فقط ۸ حرف رندوم، بدون هیچ برندی (برای سرویس‌های نمایندگی).
        - هر prefix دیگه = «اسم دلخواه کاربر»: همون اسم دقیقاً (بدون پسوند رندوم).
          فقط اگه قبلاً روی سرویس دیگه‌ای ثبت شده باشه (مثلاً وسط پرداخت دیگری گرفته شده)،
          برای جلوگیری از تداخل تو پنل یه پسوند کوتاه می‌گیره؛ اگه هم قالبش نامعتبر باشه
          (درخواست دستکاری‌شده) به یوزرنیم سیستمی برمی‌گرده.
        """
        if bare:
            return _rand()
        if prefix in _SYSTEM_PREFIXES:
            return f"{prefix}_{_rand()}"
        name = (prefix or "").strip().lower()
        if not _CUSTOM_NAME_RE.match(name):
            return f"{SANAEI_USERNAME_PREFIX}_{_rand()}"
        try:
            import database as _db
            if _db.username_taken(name):
                return f"{name}_{_rand(4)}"
        except Exception:
            pass
        return name

    @staticmethod
    def _remark(username: str, display_name: str = None, remark_prefix: str = None) -> str:
        """اسم نمایشی کانفیگ (بعد از #). سرویس‌های نمایندگی پیشوند اختصاصی خودشون رو دارن (ذخیره‌شده روی سرویس)."""
        if remark_prefix is None:
            try:
                import database as _db
                remark_prefix = _db.get_remark_prefix_by_username(username)
            except Exception:
                remark_prefix = None
        return f"{remark_prefix or VLESS_REMARK_PREFIX}-{display_name or username}"

    @staticmethod
    def _build_subscription_url(sub_id: str) -> str:
        if not SANAEI_SUB_BASE_URL or not sub_id:
            return ""
        base = SANAEI_SUB_BASE_URL.rstrip("/")
        path = SANAEI_SUB_PATH.strip("/")
        return f"{base}/{path}/{sub_id}"

    async def _get_client_info(self, email: str) -> dict:
        resp = await self._request("GET", f"/panel/api/clients/get/{email}")
        if resp.status_code != 200:
            raise SanaeiError(f"دریافت اطلاعات کاربر ناموفق بود ({resp.status_code}): {resp.text}")
        result = self._safe_json(resp)
        if not result.get("success", True):
            raise SanaeiError(f"دریافت اطلاعات کاربر ناموفق بود: {result.get('msg')}")
        obj = result.get("obj") or {}
        return obj.get("client") or obj

    async def _get_inbound_info(self) -> dict:
        """
        تنظیمات اینباند (پروتکل، پورت، streamSettings) رو می‌خونه - برای
        ساخت لینک کانفیگ خام (vless://...) لازمه. اگه این endpoint رو این
        نسخه از پنل نداشته باشه، خطا میده و caller باید graceful هندلش کنه
        (یعنی فقط بدون لینک کانفیگ خام ادامه بده، سرویس رو خراب نکنه).
        """
        resp = await self._request("GET", f"/panel/api/inbounds/get/{SANAEI_INBOUND_ID}")
        if resp.status_code != 200:
            raise SanaeiError(f"دریافت اطلاعات اینباند ناموفق بود ({resp.status_code}): {resp.text}")
        result = self._safe_json(resp)
        if not result.get("success", True):
            raise SanaeiError(f"دریافت اطلاعات اینباند ناموفق بود: {result.get('msg')}")
        return result.get("obj") or {}

    @staticmethod
    def _connect_host() -> str:
        if SANAEI_CONNECT_HOST:
            return SANAEI_CONNECT_HOST
        # fallback: هاست همون SANAEI_URL (فقط وقتی پنل ادمین و سرور اینباند یکی‌ان)
        return SANAEI_URL.split("://", 1)[-1].split(":")[0].split("/")[0]

    def _build_connection_link(self, client: dict, inbound: dict, remark: str) -> str:
        """لینک کانفیگ خام (vless://... یا vmess://...) رو از روی تنظیمات واقعی اینباند می‌سازه"""
        client_id = _extract_client_uuid(client)
        if not client_id:
            return ""

        protocol = (inbound.get("protocol") or "vless").lower()
        port = inbound.get("port")
        host = self._connect_host()

        stream_raw = inbound.get("streamSettings") or "{}"
        try:
            stream = json.loads(stream_raw) if isinstance(stream_raw, str) else (stream_raw or {})
        except (TypeError, ValueError):
            stream = {}

        network = stream.get("network", "tcp")
        security = stream.get("security", "none")
        params = {"type": network, "security": security}

        if network == "ws":
            ws = stream.get("wsSettings") or {}
            params["path"] = ws.get("path", "/")
            ws_host = (ws.get("headers") or {}).get("Host") or ws.get("host")
            if ws_host:
                params["host"] = ws_host
        elif network == "grpc":
            grpc = stream.get("grpcSettings") or {}
            if grpc.get("serviceName"):
                params["serviceName"] = grpc["serviceName"]

        if security == "reality":
            reality = stream.get("realitySettings") or {}
            reality_inner = reality.get("settings") or {}

            server_names = reality.get("serverNames") or []
            sni = server_names[0] if server_names else (reality.get("dest", "").split(":")[0])
            if sni:
                params["sni"] = sni

            fp = reality_inner.get("fingerprint")
            if fp:
                params["fp"] = fp

            pbk = reality_inner.get("publicKey")
            if pbk:
                params["pbk"] = pbk

            short_ids = reality.get("shortIds") or []
            # اولین shortId غیرخالی رو انتخاب می‌کنیم (این‌ها یه استخر مشترکن، نه اختصاصی هر کلاینت)
            sid = next((s for s in short_ids if s), "") if short_ids else ""
            params["sid"] = sid

            spx = reality_inner.get("spiderX")
            if spx:
                params["spx"] = spx
        elif security == "tls":
            tls = stream.get("tlsSettings") or {}
            tls_inner = tls.get("settings") or {}
            server_names = tls.get("serverName") or (tls.get("serverNames") or [None])[0]
            if server_names:
                params["sni"] = server_names
            fp = tls_inner.get("fingerprint")
            if fp:
                params["fp"] = fp
            alpn = tls.get("alpn")
            if alpn:
                params["alpn"] = ",".join(alpn) if isinstance(alpn, list) else alpn

        if protocol == "vless":
            params.setdefault("encryption", "none")

        query = urllib.parse.urlencode(params)
        tag = urllib.parse.quote(remark)
        return f"{protocol}://{client_id}@{host}:{port}?{query}#{tag}"

    async def _build_links(self, username: str, sub_id: str, display_name: str = None, remark_prefix: str = None) -> dict:
        """
        هم لینک اشتراک (sub) هم لینک کانفیگ خام (vless://...) رو برمی‌گردونه.
        اگه به هر دلیلی گرفتن اطلاعات اینباند/کلاینت ناموفق بود، فقط لینک
        کانفیگ خام خالی می‌مونه (سرویس خراب نمیشه، لینک ساب هنوز کار می‌کنه).

        display_name: اسم دلخواهی که کاربر موقع خرید انتخاب کرده (بدون
        پسوند رندوم که فقط برای یکتا بودن تو پنل لازمه). اگه داده بشه، تو
        remark به‌جای username کامل (که شامل پسوند رندومه) ازش استفاده
        میشه - وگرنه اسم تو لینک vless سه‌تیکه و شلوغ میشه (پیشوند برند +
        اسم دلخواه + پسوند رندوم).
        """
        subscription_url = self._build_subscription_url(sub_id)
        connection_link = ""
        try:
            client = await self._get_client_info(username)
            inbound = await self._get_inbound_info()
            remark = self._remark(username, display_name, remark_prefix)
            connection_link = self._build_connection_link(client, inbound, remark=remark)
        except Exception:
            pass
        return {"subscription_url": subscription_url, "connection_link": connection_link}

    async def create_user(self, username: str, days: int, gb: float, display_name: str = None, remark_prefix: str = None) -> dict:
        expire_seconds = 0
        if days and days > 0:
            expire_seconds = int(time.time()) + days * 86400
        expire_ms = expire_seconds * 1000 if expire_seconds else 0

        if DEMO_MODE:
            return {
                "username": username,
                "expire": expire_seconds,
                "subscription_url": f"https://demo.noordis.test/sub/{username}",
                "connection_link": f"vless://demo-uuid@demo.noordis.test:443?type=ws&security=none#{username}",
            }

        data_limit_bytes = int(round(gb * 1024 ** 3)) if gb and gb > 0 else 0

        body = {
            "client": {
                "email": username,
                "totalGB": data_limit_bytes,
                "expiryTime": expire_ms,
                "tgId": 0,
                "limitIp": 0,
                "enable": True,
            },
            "inboundIds": [SANAEI_INBOUND_ID],
        }

        resp = await self._request("POST", "/panel/api/clients/add", json=body)
        if resp.status_code != 200:
            raise SanaeiError(f"ساخت کاربر ناموفق بود ({resp.status_code}): {resp.text}")
        result = self._safe_json(resp)
        if not result.get("success", True):
            raise SanaeiError(f"ساخت کاربر ناموفق بود: {result.get('msg')}")

        info = await self._get_client_info(username)
        sub_id = info.get("subId") or username
        links = await self._build_links(username, sub_id, display_name=display_name, remark_prefix=remark_prefix)

        return {
            "username": username,
            "expire": expire_seconds,
            **links,
        }

    async def modify_user(self, username: str, days: int, gb: float, reset_usage: bool = True) -> dict:
        expire_seconds = 0
        if days and days > 0:
            expire_seconds = int(time.time()) + days * 86400
        expire_ms = expire_seconds * 1000 if expire_seconds else 0

        if DEMO_MODE:
            return {
                "username": username,
                "expire": expire_seconds,
                "subscription_url": f"https://demo.noordis.test/sub/{username}",
                "connection_link": f"vless://demo-uuid@demo.noordis.test:443?type=ws&security=none#{username}",
            }

        data_limit_bytes = int(round(gb * 1024 ** 3)) if gb and gb > 0 else 0

        try:
            existing = await self._get_client_info(username)
        except SanaeiError:
            # کلاینت با این یوزرنیم روی پنل فعلی پیدا نشد (مثلاً دستی پاک شده
            # یا مربوط به یه پنل/دوره‌ی قبلیه). به‌جای شکست کامل تمدید و از
            # دست رفتن سرویس کاربر، همینجا از نو با همون یوزرنیم می‌سازیمش.
            add_body = {
                "client": {
                    "email": username,
                    "totalGB": data_limit_bytes,
                    "expiryTime": expire_ms,
                    "tgId": 0,
                    "limitIp": 0,
                    "enable": True,
                },
                "inboundIds": [SANAEI_INBOUND_ID],
            }
            resp = await self._request("POST", "/panel/api/clients/add", json=add_body)
            if resp.status_code != 200:
                raise SanaeiError(
                    f"کاربر روی پنل پیدا نشد و ساخت مجددش هم ناموفق بود ({resp.status_code}): {resp.text}"
                )
            result = self._safe_json(resp)
            if not result.get("success", True):
                raise SanaeiError(f"کاربر روی پنل پیدا نشد و ساخت مجددش هم ناموفق بود: {result.get('msg')}")
        else:
            # نکته‌ی مهم تمدید: اگه کاربر حجم باقی‌مونده از سرویس قبلیش داشته
            # باشه، اون رو دور نمی‌ریزیم - به سقف پلن جدید اضافه‌ش می‌کنیم.
            # مثلاً ۵ گیگ باقی‌مونده + تمدید با پلن ۱۰ گیگ = ۱۵ گیگ نهایی؛
            # روزها همچنان کامل از نو حساب میشه (طبق رفتار قبلی، عوض نشده).
            old_total = int(existing.get("totalGB", 0) or 0)
            if old_total > 0 and data_limit_bytes > 0:
                used_bytes = 0
                try:
                    traffic_resp = await self._request("GET", f"/panel/api/clients/traffic/{username}")
                    if traffic_resp.status_code == 200:
                        traffic = self._safe_json(traffic_resp)
                        obj = traffic.get("obj") or {}
                        if isinstance(obj, list) and obj:
                            obj = obj[0]
                        used_bytes = int(obj.get("up", 0)) + int(obj.get("down", 0))
                except Exception:
                    used_bytes = 0
                remaining_bytes = max(0, old_total - used_bytes)
                data_limit_bytes += remaining_bytes
            # اگه old_total == 0 یعنی قبلاً نامحدود بوده - «باقی‌مونده»ی
            # نامحدود معنی نداره که به یه سقف مشخص اضافه بشه، پس همون سقف
            # پلن جدید (data_limit_bytes) دست‌نخورده می‌مونه.

            body = {
                "email": username,
                "totalGB": data_limit_bytes,
                "expiryTime": expire_ms,
                "tgId": existing.get("tgId", 0),
                "limitIp": existing.get("limitIp", 0),
                "enable": True,
            }

            resp = await self._request("POST", f"/panel/api/clients/update/{username}", json=body)
            if resp.status_code != 200:
                raise SanaeiError(f"تمدید کاربر ناموفق بود ({resp.status_code}): {resp.text}")
            result = self._safe_json(resp)
            if not result.get("success", True):
                raise SanaeiError(f"تمدید کاربر ناموفق بود: {result.get('msg')}")

        if reset_usage:
            try:
                await self._request("POST", f"/panel/api/clients/resetTraffic/{username}")
            except Exception:
                pass

        info = await self._get_client_info(username)
        sub_id = info.get("subId") or username
        links = await self._build_links(username, sub_id)

        return {
            "username": username,
            "expire": expire_seconds,
            "total_gb": round(data_limit_bytes / (1024 ** 3), 2) if data_limit_bytes > 0 else 0,
            **links,
        }

    async def get_user(self, username: str, include_config: bool = True) -> dict:
        if DEMO_MODE:
            return {
                "username": username,
                "used_traffic": 0,
                "data_limit": 0,
                "links": [],
                "subscription_url": f"https://demo.noordis.test/sub/{username}",
                "connection_link": f"vless://demo-uuid@demo.noordis.test:443?type=ws&security=none#{username}"
                if include_config else "",
                "status": "active",
            }

        info = await self._get_client_info(username)
        sub_id = info.get("subId") or username
        enabled = info.get("enable", True)

        used_traffic = 0
        data_limit = int(info.get("totalGB", 0) or 0)
        try:
            resp = await self._request("GET", f"/panel/api/clients/traffic/{username}")
            if resp.status_code == 200:
                traffic = self._safe_json(resp)
                obj = traffic.get("obj") or {}
                if isinstance(obj, list) and obj:
                    obj = obj[0]
                used_traffic = int(obj.get("up", 0)) + int(obj.get("down", 0))
        except Exception:
            pass

        connection_link = ""
        if include_config:
            try:
                inbound = await self._get_inbound_info()
                connection_link = self._build_connection_link(info, inbound, remark=self._remark(username))
            except Exception:
                pass

        return {
            "username": username,
            "used_traffic": used_traffic,
            "data_limit": data_limit,
            "links": [],
            "subscription_url": self._build_subscription_url(sub_id),
            "connection_link": connection_link,
            "status": "active" if enabled else "disabled",
        }

    async def revoke_subscription(self, username: str) -> dict:
        """
        فقط UUID کلاینت رو عوض می‌کنه تا لینک قبلی باطل بشه و لینک جدید کار
        کنه - کلاینت اصلاً حذف نمیشه (برخلاف قبل که DELETE+ADD می‌کرد و چون
        رکورد کاملاً تازه می‌ساخت، آمار مصرف پنل هم صفر می‌شد - یه باگ جدی
        که باعث می‌شد کاربر با زدن این دکمه صاحب حجم مجانی جدید بشه).
        چون اینجا فقط یه فیلد از همون رکورد قبلی آپدیت میشه، مصرف قبلی و
        همه‌چیز دیگه (تاریخ انقضا، سقف حجم) دقیقاً دست‌نخورده می‌مونه.
        """
        if DEMO_MODE:
            new_token = "".join(random.choices("abcdef0123456789", k=8))
            return {
                "subscription_url": f"https://demo.noordis.test/sub/{username}-{new_token}",
                "connection_link": f"vless://demo-uuid@demo.noordis.test:443?type=ws&security=none#{username}",
            }

        existing = await self._get_client_info(username)
        new_uuid = str(uuid_module.uuid4())

        body = {
            "email": username,
            "id": new_uuid,
            "totalGB": existing.get("totalGB", 0),
            "expiryTime": existing.get("expiryTime", 0),
            "tgId": existing.get("tgId", 0),
            "limitIp": existing.get("limitIp", 0),
            "enable": existing.get("enable", True),
        }
        resp = await self._request("POST", f"/panel/api/clients/update/{username}", json=body)
        if resp.status_code != 200:
            raise SanaeiError(f"بازتولید لینک ناموفق بود ({resp.status_code}): {resp.text}")
        result = self._safe_json(resp)
        if not result.get("success", True):
            raise SanaeiError(f"بازتولید لینک ناموفق بود: {result.get('msg')}")

        info = await self._get_client_info(username)
        sub_id = info.get("subId") or username
        links = await self._build_links(username, sub_id)

        return links

    async def set_status(self, username: str, status: str) -> dict:
        if DEMO_MODE:
            return {"username": username, "status": status}

        existing = await self._get_client_info(username)
        body = {
            "email": username,
            "totalGB": existing.get("totalGB", 0),
            "expiryTime": existing.get("expiryTime", 0),
            "tgId": existing.get("tgId", 0),
            "limitIp": existing.get("limitIp", 0),
            "enable": status == "active",
        }
        resp = await self._request("POST", f"/panel/api/clients/update/{username}", json=body)
        if resp.status_code != 200:
            raise SanaeiError(f"تغییر وضعیت ناموفق بود ({resp.status_code}): {resp.text}")
        return {"username": username, "status": status}

    async def remove_user(self, username: str):
        if DEMO_MODE:
            return
        resp = await self._request("POST", f"/panel/api/clients/del/{username}")
        if resp.status_code != 200:
            raise SanaeiError(f"حذف کاربر ناموفق بود ({resp.status_code}): {resp.text}")

    async def get_online_status(self, username: str) -> bool:
        if DEMO_MODE:
            return True
        resp = await self._request("POST", "/panel/api/clients/onlines", json={})
        if resp.status_code != 200:
            raise SanaeiError(f"بررسی وضعیت اتصال ناموفق بود ({resp.status_code}): {resp.text}")
        result = self._safe_json(resp)
        online_list = result.get("obj") or []
        return username in online_list


sanaei = SanaeiClient()
