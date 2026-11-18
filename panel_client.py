"""
لایه‌ی انتزاعی انتخاب پنل.

کل ربات (handlers) فقط از همین فایل استفاده می‌کنه، نه مستقیم از
marzban_client یا sanaei_client. با تغییر PANEL_TYPE توی Secrets/.env
(marzban یا sanaei)، کل ربات بدون هیچ تغییر دیگه‌ای به پنل دیگه وصل میشه.

اگه در آینده پنل سومی هم اضافه شد، کافیه یک فایل {panel}_client.py با همون
توابع (generate_username, create_user, modify_user, get_user,
revoke_subscription, set_status, remove_user) بسازی و اینجا اضافه‌ش کنی.
"""
from config import PANEL_TYPE

if PANEL_TYPE == "sanaei":
    from sanaei_client import sanaei as panel, SanaeiError as PanelError
elif PANEL_TYPE == "marzban":
    from marzban_client import marzban as panel, MarzbanError as PanelError
else:
    raise ValueError(
        f"PANEL_TYPE نامعتبره: '{PANEL_TYPE}'. مقدارهای مجاز: 'marzban' یا 'sanaei'."
    )
