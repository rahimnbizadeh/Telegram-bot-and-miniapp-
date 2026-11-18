"""
لایه‌ی پایگاه داده - SQLite
برای مقیاس کوچک تا متوسط (چند صد تا چند هزار کاربر) SQLite کاملا کافیه.
اگر بعدا حجم بالا رفت، میشه به PostgreSQL مهاجرت کرد بدون تغییر زیاد در بقیه‌ی کد.
"""
import sqlite3
import threading
import time
import datetime
from contextlib import contextmanager

from config import DB_PATH, REFERRAL_BONUS_TOMAN, LOYALTY_TIERS, get_plan

_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_conn():
    with _lock:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _column_exists(conn, table, column) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def _rebuild_orders_table_if_needed(conn):
    """
    نسخه‌ی خیلی اول این پروژه، ستون plan_id رو 'اجباری' (NOT NULL) تعریف کرده بود.
    از وقتی قابلیت «شارژ کیف پول» اضافه شد، این ستون باید بتونه خالی هم باشه.
    این تابع اگه چنین دیتابیس قدیمی‌ای رو تشخیص بده، بدون از دست رفتن سفارش‌های
    قبلی، جدول رو به ساختار جدید مهاجرت می‌ده.
    """
    rows = conn.execute("PRAGMA table_info(orders)").fetchall()
    plan_id_info = next((r for r in rows if r["name"] == "plan_id"), None)
    if not plan_id_info or plan_id_info["notnull"] == 0:
        return  # از قبل درسته یا جدول هنوز ساخته نشده

    existing_cols = [r["name"] for r in rows]

    conn.execute("ALTER TABLE orders RENAME TO orders_old_migration")
    conn.execute(
        """
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_id TEXT,
            kind TEXT NOT NULL DEFAULT 'new',
            renew_sub_id INTEGER,
            amount INTEGER,
            status TEXT NOT NULL DEFAULT 'pending',
            receipt_file_id TEXT,
            admin_message_id INTEGER,
            created_at INTEGER,
            decided_at INTEGER,
            decided_by INTEGER
        )
        """
    )

    new_cols = [
        "order_id", "user_id", "plan_id", "kind", "renew_sub_id", "amount",
        "status", "receipt_file_id", "admin_message_id", "created_at",
        "decided_at", "decided_by",
    ]
    copyable = [c for c in new_cols if c in existing_cols]
    cols_sql = ", ".join(copyable)
    conn.execute(f"INSERT INTO orders ({cols_sql}) SELECT {cols_sql} FROM orders_old_migration")
    conn.execute("DROP TABLE orders_old_migration")


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                joined_at INTEGER,
                wallet_balance INTEGER NOT NULL DEFAULT 0,
                referred_by INTEGER,
                referral_bonus_given INTEGER NOT NULL DEFAULT 0,
                trial_used INTEGER NOT NULL DEFAULT 0,
                language TEXT NOT NULL DEFAULT 'fa'
            );

            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan_id TEXT,
                kind TEXT NOT NULL DEFAULT 'new',   -- 'new' / 'renew' / 'topup'
                renew_sub_id INTEGER,
                amount INTEGER,                     -- فقط برای kind='topup': مبلغ شارژ به تومان
                discount_code TEXT,                  -- کد تخفیف اعمال‌شده (اگه بوده)
                discount_percent INTEGER,            -- درصد تخفیف در لحظه‌ی ثبت سفارش (تاریخی، حتی اگه کد بعداً عوض/حذف بشه)
                status TEXT NOT NULL DEFAULT 'pending', -- pending / approved / rejected
                receipt_file_id TEXT,
                admin_message_id INTEGER,
                created_at INTEGER,
                decided_at INTEGER,
                decided_by INTEGER
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                sub_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                order_id INTEGER,
                plan_id TEXT,
                marzban_username TEXT,
                plan_title TEXT,
                expire_at INTEGER,
                sub_link TEXT,
                note TEXT,
                created_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS wallet_transactions (
                tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,       -- مثبت = واریز، منفی = برداشت
                tx_type TEXT NOT NULL,         -- topup / purchase / referral_bonus / transfer_in / transfer_out
                description TEXT,
                created_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject TEXT,
                status TEXT NOT NULL DEFAULT 'open',   -- open / answered / closed
                admin_message_id INTEGER,
                created_at INTEGER,
                updated_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS ticket_messages (
                msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                sender TEXT NOT NULL,   -- 'user' یا 'admin'
                text TEXT,
                created_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS crypto_invoices (
                invoice_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                message_id INTEGER,
                kind TEXT NOT NULL,        -- new / renew / topup
                plan_id TEXT,
                sub_id INTEGER,
                amount_toman INTEGER,
                discount_code TEXT,
                discount_percent INTEGER,
                currency TEXT,
                amount_crypto REAL,
                status TEXT NOT NULL DEFAULT 'pending',   -- pending / paid / expired
                created_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS autosms_invoices (
                authority TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                message_id INTEGER,
                kind TEXT NOT NULL,        -- new / renew / topup
                plan_id TEXT,
                sub_id INTEGER,
                custom_name TEXT,
                discount_code TEXT,
                discount_percent INTEGER,
                base_amount_toman INTEGER,
                pay_amount_toman INTEGER,
                card_number TEXT,
                card_holder TEXT,
                status TEXT NOT NULL DEFAULT 'pending',   -- pending / paid / expired
                created_at INTEGER,
                expires_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS tonpays_invoices (
                invoice_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                message_id INTEGER,
                kind TEXT NOT NULL,        -- new / renew / topup
                plan_id TEXT,
                sub_id INTEGER,
                custom_name TEXT,
                discount_code TEXT,
                discount_percent INTEGER,
                request_amount INTEGER,
                final_amount INTEGER,
                status TEXT NOT NULL DEFAULT 'pending',   -- pending / paid / expired
                created_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS winapay_invoices (
                authority TEXT PRIMARY KEY,   -- شناسه‌ی ۳۲ کاراکتری ویناپی
                order_id TEXT NOT NULL,       -- InvoiceID که ما فرستادیم
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                message_id INTEGER,
                kind TEXT NOT NULL,           -- new / renew / topup
                plan_id TEXT,
                sub_id INTEGER,
                custom_name TEXT,
                discount_code TEXT,
                discount_percent INTEGER,
                amount INTEGER NOT NULL,      -- تومان؛ دقیقاً همونی که تو Verify هم باید بفرستیم
                status TEXT NOT NULL DEFAULT 'pending',   -- pending / paid / expired
                ref_id TEXT,
                created_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS discount_codes (
                code TEXT PRIMARY KEY,
                percent INTEGER NOT NULL,
                max_uses INTEGER,              -- NULL = نامحدود
                used_count INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                expires_at INTEGER,            -- NULL = بدون انقضا
                created_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS banners (
                banner_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title_fa TEXT NOT NULL,
                body_fa TEXT,
                title_en TEXT,
                body_en TEXT,
                title_ru TEXT,
                body_ru TEXT,
                theme TEXT NOT NULL DEFAULT 'gold',   -- gold / blue / green / violet / red
                action TEXT,                          -- NULL / shop / trial / wallet / loyalty / referral / support / apps / url
                url TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                expires_at INTEGER,                   -- NULL = بدون انقضا
                created_at INTEGER,
                kind TEXT,                            -- NULL = بنر معمولی؛ 'outage' = اطلاعیه‌ی اختلال؛ 'campaign' = کمپین تخفیف
                code TEXT                             -- کد تخفیف کمپین (فقط برای kind='campaign')
            );

            CREATE TABLE IF NOT EXISTS discount_code_uses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                used_at INTEGER,
                UNIQUE(code, user_id)
            );

            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject TEXT,
                status TEXT NOT NULL DEFAULT 'open',  -- open / answered / closed
                admin_message_id INTEGER,
                created_at INTEGER,
                updated_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS ticket_messages (
                msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                sender TEXT NOT NULL,   -- user / admin
                text TEXT,
                created_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS wallet_transactions (
                tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tx_type TEXT NOT NULL,   -- topup / purchase / renewal / referral_bonus / transfer_sent / transfer_received / admin_adjust
                amount INTEGER NOT NULL, -- مثبت = واریز، منفی = برداشت
                description TEXT,
                created_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS ratings (
                rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                context TEXT NOT NULL,    -- 'purchase' یا 'ticket'
                target_id INTEGER,        -- sub_id یا ticket_id مربوطه
                score INTEGER NOT NULL,   -- ۱ تا ۵
                created_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS reseller_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT,             -- توضیح کاربر؛ می‌تونه خالی باشه
                status TEXT NOT NULL DEFAULT 'pending',  -- pending / approved / rejected
                created_at INTEGER,
                decided_at INTEGER
            );
            """
        )

        # اگه از نسخه‌ی خیلی قدیمی این پروژه مهاجرت می‌کنیم، جدول orders رو اصلاح کن
        _rebuild_orders_table_if_needed(conn)

        # مهاجرت نرم برای دیتابیس‌های قدیمی‌تر که از قبل ساخته شدن
        if not _column_exists(conn, "subscriptions", "plan_id"):
            conn.execute("ALTER TABLE subscriptions ADD COLUMN plan_id TEXT")
        if not _column_exists(conn, "users", "language"):
            conn.execute("ALTER TABLE users ADD COLUMN language TEXT NOT NULL DEFAULT 'fa'")
        if not _column_exists(conn, "users", "referred_by"):
            conn.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
        if not _column_exists(conn, "users", "referral_bonus_given"):
            conn.execute("ALTER TABLE users ADD COLUMN referral_bonus_given INTEGER NOT NULL DEFAULT 0")
        if not _column_exists(conn, "users", "wallet_balance"):
            conn.execute("ALTER TABLE users ADD COLUMN wallet_balance INTEGER NOT NULL DEFAULT 0")
        if not _column_exists(conn, "users", "trial_used"):
            conn.execute("ALTER TABLE users ADD COLUMN trial_used INTEGER NOT NULL DEFAULT 0")
        if not _column_exists(conn, "orders", "kind"):
            conn.execute("ALTER TABLE orders ADD COLUMN kind TEXT NOT NULL DEFAULT 'new'")
        if not _column_exists(conn, "orders", "renew_sub_id"):
            conn.execute("ALTER TABLE orders ADD COLUMN renew_sub_id INTEGER")
        if not _column_exists(conn, "orders", "amount"):
            conn.execute("ALTER TABLE orders ADD COLUMN amount INTEGER")
        if not _column_exists(conn, "subscriptions", "note"):
            conn.execute("ALTER TABLE subscriptions ADD COLUMN note TEXT")
        if not _column_exists(conn, "subscriptions", "remark_prefix"):
            # پیشوند اسم کانفیگِ اختصاصیِ این سرویس (مثلاً سرویس‌های نمایندگی)؛ خالی = پیشوند پیش‌فرض برند
            conn.execute("ALTER TABLE subscriptions ADD COLUMN remark_prefix TEXT")
        if not _column_exists(conn, "subscriptions", "data_warning_sent"):
            conn.execute("ALTER TABLE subscriptions ADD COLUMN data_warning_sent INTEGER NOT NULL DEFAULT 0")
        if not _column_exists(conn, "subscriptions", "expiry_warning_sent"):
            conn.execute("ALTER TABLE subscriptions ADD COLUMN expiry_warning_sent INTEGER NOT NULL DEFAULT 0")
        if not _column_exists(conn, "orders", "custom_name"):
            conn.execute("ALTER TABLE orders ADD COLUMN custom_name TEXT")
        if not _column_exists(conn, "crypto_invoices", "custom_name"):
            conn.execute("ALTER TABLE crypto_invoices ADD COLUMN custom_name TEXT")
        if not _column_exists(conn, "orders", "discount_code"):
            conn.execute("ALTER TABLE orders ADD COLUMN discount_code TEXT")
        if not _column_exists(conn, "orders", "discount_percent"):
            conn.execute("ALTER TABLE orders ADD COLUMN discount_percent INTEGER")
        if not _column_exists(conn, "crypto_invoices", "discount_code"):
            conn.execute("ALTER TABLE crypto_invoices ADD COLUMN discount_code TEXT")
        if not _column_exists(conn, "crypto_invoices", "discount_percent"):
            conn.execute("ALTER TABLE crypto_invoices ADD COLUMN discount_percent INTEGER")
        if not _column_exists(conn, "subscriptions", "auto_renew"):
            conn.execute("ALTER TABLE subscriptions ADD COLUMN auto_renew INTEGER NOT NULL DEFAULT 0")
        if not _column_exists(conn, "users", "loyalty_bonus_month"):
            conn.execute("ALTER TABLE users ADD COLUMN loyalty_bonus_month TEXT")
        if not _column_exists(conn, "users", "is_reseller"):
            conn.execute("ALTER TABLE users ADD COLUMN is_reseller INTEGER NOT NULL DEFAULT 0")
        # خلاصه‌ی هفتگی: کاربر می‌تونه خاموشش کنه؛ تاریخ آخرین ارسال جلوی دوبار ارسال تو یه روز رو می‌گیره
        if not _column_exists(conn, "users", "weekly_summary"):
            conn.execute("ALTER TABLE users ADD COLUMN weekly_summary INTEGER NOT NULL DEFAULT 1")
        if not _column_exists(conn, "users", "weekly_summary_last"):
            conn.execute("ALTER TABLE users ADD COLUMN weekly_summary_last TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_checkins (
                user_id INTEGER PRIMARY KEY,
                last_day TEXT,                 -- آخرین روزی (به وقت ایران) که پاداش روزانه گرفته
                streak INTEGER NOT NULL DEFAULT 0,
                best INTEGER NOT NULL DEFAULT 0,
                total INTEGER NOT NULL DEFAULT 0,
                last_code TEXT,                -- آخرین کد جایزه (تا کاربر از دستش نده)
                last_code_percent INTEGER,
                last_code_expires INTEGER
            )
            """
        )
        # هر مایل‌استون برای هر کاربر آخرین بار کِی جایزه داده شده؛ برای cooldown «همون جایزه‌ی تکراری»
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_checkin_rewards (
                user_id INTEGER NOT NULL,
                milestone_days INTEGER NOT NULL,
                granted_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, milestone_days)
            )
            """
        )
        # «آخرین ورود» پنل منوی اصلی: last_seen = آخرین فعالیت، prev_seen = شروع‌نشستِ قبلی (فاصله > ۳۰ دقیقه = نشست جدید)
        if not _column_exists(conn, "users", "last_seen"):
            conn.execute("ALTER TABLE users ADD COLUMN last_seen INTEGER")
        if not _column_exists(conn, "users", "prev_seen"):
            conn.execute("ALTER TABLE users ADD COLUMN prev_seen INTEGER")
        # لاگ رویدادهای چرخه‌ی عمر سرویس (پایان‌یافتن/حذف خودکار) برای گزارش صبحگاهی ادمین
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lifecycle_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT NOT NULL,     -- ended_time / ended_data / deleted / deleted_trial
                user_id INTEGER,
                sub_id INTEGER,
                at INTEGER NOT NULL
            )
            """
        )
        # پرچم‌های ساده‌ی کاربر (مثلاً «سرویس رو به صفحه‌ی گوشی اضافه کرده») برای مهرهای گذرنامه
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_flags (
                user_id INTEGER NOT NULL,
                flag TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, flag)
            )
            """
        )
        if not _column_exists(conn, "banners", "kind"):
            conn.execute("ALTER TABLE banners ADD COLUMN kind TEXT")
        if not _column_exists(conn, "banners", "code"):
            conn.execute("ALTER TABLE banners ADD COLUMN code TEXT")
        # چرخه‌ی عمر بعد از پایان سرویس (مهلت تمدید قبل از حذف)
        if not _column_exists(conn, "subscriptions", "ended_at"):
            conn.execute("ALTER TABLE subscriptions ADD COLUMN ended_at INTEGER")
        if not _column_exists(conn, "subscriptions", "ended_reason"):
            conn.execute("ALTER TABLE subscriptions ADD COLUMN ended_reason TEXT")
        if not _column_exists(conn, "subscriptions", "final_warning_sent"):
            conn.execute("ALTER TABLE subscriptions ADD COLUMN final_warning_sent INTEGER NOT NULL DEFAULT 0")


# ---------------- کاربران ----------------
def upsert_user(user_id: int, username: str, first_name: str, referred_by: int = None):
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE users SET username = ?, first_name = ? WHERE user_id = ?",
                (username, first_name, user_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO users (user_id, username, first_name, joined_at, referred_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, username, first_name, int(time.time()), referred_by),
            )


def get_user(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()


def get_user_language(user_id: int) -> str:
    row = get_user(user_id)
    if row and row["language"]:
        return row["language"]
    return "fa"


def set_user_language(user_id: int, language: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET language = ? WHERE user_id = ?", (language, user_id)
        )


def count_users() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
        return row["c"]


def get_all_user_ids() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT user_id FROM users").fetchall()
        return [r["user_id"] for r in rows]


def has_used_trial(user_id: int) -> bool:
    user = get_user(user_id)
    return bool(user and user["trial_used"])


def claim_trial(user_id: int) -> bool:
    """ثبت اتمیک «تست رایگان گرفته شد»؛ فقط یکی از چند درخواست همزمان برنده میشه"""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE users SET trial_used = 1 WHERE user_id = ? AND trial_used = 0", (user_id,)
        )
        return cur.rowcount == 1


def release_trial(user_id: int):
    """اگه ساخت تست به‌خاطر خطا انجام نشد، حقِ تست برمی‌گرده"""
    with get_conn() as conn:
        conn.execute("UPDATE users SET trial_used = 0 WHERE user_id = ?", (user_id,))


def mark_trial_used(user_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET trial_used = 1 WHERE user_id = ?", (user_id,)
        )


def reset_all_trials() -> int:
    """trial_used همه‌ی کاربرا رو صفر می‌کنه تا بتونن دوباره تست رایگان بگیرن. تعداد کاربرای تحت‌تاثیر رو برمی‌گردونه."""
    with get_conn() as conn:
        cur = conn.execute("UPDATE users SET trial_used = 0 WHERE trial_used = 1")
        return cur.rowcount


def get_wallet_balance(user_id: int) -> int:
    user = get_user(user_id)
    return user["wallet_balance"] if user else 0


def adjust_wallet_balance(user_id: int, amount: int):
    """amount میتونه مثبت (شارژ) یا منفی (کسر) باشه"""
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET wallet_balance = wallet_balance + ? WHERE user_id = ?",
            (amount, user_id),
        )


def log_wallet_transaction(user_id: int, amount: int, tx_type: str, description: str = ""):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO wallet_transactions (user_id, amount, tx_type, description, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, amount, tx_type, description, int(time.time())),
        )


def try_debit_wallet(user_id: int, amount: int, tx_type: str, description: str = "") -> bool:
    """
    کسر اتمیک از کیف پول: فقط اگه موجودیِ همون لحظه کافی باشه کم میشه (شرط تو خودِ UPDATE).
    جلوی خرج‌کردن چندباره‌ی یک موجودی با درخواست‌های همزمان رو می‌گیره و موجودی هیچ‌وقت منفی نمیشه.
    اگه کسر موفق بود تراکنش هم ثبت میشه و True برمی‌گرده؛ وگرنه هیچ تغییری نمیده و False.
    """
    if amount <= 0:
        return True
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE users SET wallet_balance = wallet_balance - ? WHERE user_id = ? AND wallet_balance >= ?",
            (amount, user_id, amount),
        )
        if cur.rowcount != 1:
            return False
        conn.execute(
            "INSERT INTO wallet_transactions (user_id, amount, tx_type, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, -amount, tx_type, description, int(time.time())),
        )
        return True


def adjust_wallet_balance_logged(user_id: int, amount: int, tx_type: str, description: str = ""):
    """کسر/افزایش موجودی + ثبت تراکنش در یک عملیات"""
    adjust_wallet_balance(user_id, amount)
    log_wallet_transaction(user_id, amount, tx_type, description)


def get_wallet_transactions(user_id: int, limit: int = 15):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM wallet_transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()


def transfer_wallet_balance(from_user_id: int, to_user_id: int, amount: int) -> bool:
    """
    مبلغ رو از کیف پول یک کاربر به کاربر دیگه منتقل می‌کنه.
    اگه موجودی کافی نباشه، False برمی‌گردونه و هیچ تغییری اعمال نمیشه.
    """
    if amount <= 0:
        return False
    with get_conn() as conn:
        # کسر اتمیک با شرط موجودی تو خودِ UPDATE (چک جدا از کسر، با انتقال‌های همزمان می‌تونست موجودی رو منفی کنه)
        cur = conn.execute(
            "UPDATE users SET wallet_balance = wallet_balance - ? WHERE user_id = ? AND wallet_balance >= ?",
            (amount, from_user_id, amount),
        )
        if cur.rowcount != 1:
            return False
        conn.execute(
            "UPDATE users SET wallet_balance = wallet_balance + ? WHERE user_id = ?",
            (amount, to_user_id),
        )
        now = int(time.time())
        conn.execute(
            "INSERT INTO wallet_transactions (user_id, amount, tx_type, description, created_at) VALUES (?, ?, 'transfer_out', ?, ?)",
            (from_user_id, -amount, f"انتقال به {to_user_id}", now),
        )
        conn.execute(
            "INSERT INTO wallet_transactions (user_id, amount, tx_type, description, created_at) VALUES (?, ?, 'transfer_in', ?, ?)",
            (to_user_id, amount, f"دریافتی از {from_user_id}", now),
        )
        return True


def add_rating(user_id: int, context: str, target_id, score: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ratings (user_id, context, target_id, score, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, context, target_id, score, int(time.time())),
        )


def count_referrals(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE referred_by = ?", (user_id,)
        ).fetchone()
        return row["c"]


def get_referral_leaderboard_this_month(limit: int = 10):
    """
    نفرات برتر دعوت‌کننده در ماه میلادی جاری، بر اساس تعداد کاربرهایی که با
    لینکشون عضو شدن (users.joined_at این ماه بوده و referred_by همینه).
    """
    now = datetime.datetime.now()
    month_start = int(datetime.datetime(now.year, now.month, 1).timestamp())
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT referred_by AS user_id, COUNT(*) AS c
            FROM users
            WHERE referred_by IS NOT NULL AND joined_at >= ?
            GROUP BY referred_by
            ORDER BY c DESC
            LIMIT ?
            """,
            (month_start, limit),
        ).fetchall()


def get_referral_count_this_month(user_id: int) -> int:
    now = datetime.datetime.now()
    month_start = int(datetime.datetime(now.year, now.month, 1).timestamp())
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE referred_by = ? AND joined_at >= ?",
            (user_id, month_start),
        ).fetchone()
        return row["c"]


def get_lifetime_spent(user_id: int) -> int:
    """
    مجموع مبلغ خریدهای تاییدشده‌ی این کاربر (خرید جدید + تمدید)، بر اساس
    قیمت فعلی پلن (مثل آمار رفرال، تخفیف لحظه‌ای سفارش لحاظ نمیشه) - برای
    باشگاه مشتریان.
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT plan_id FROM orders WHERE user_id = ? AND status = 'approved' AND kind IN ('new', 'renew')",
            (user_id,),
        ).fetchall()
    total = 0
    for row in rows:
        plan = get_plan(row["plan_id"])
        if plan:
            total += plan["price"]
    return total


def get_loyalty_tier_for_amount(spent: int):
    """بالاترین سطح باشگاه مشتریانی که این مبلغ خرید بهش می‌رسه؛ اگه به هیچی نرسه None"""
    tier = None
    for t in LOYALTY_TIERS:
        if spent >= t["min_spent"]:
            tier = t
    return tier


def get_all_lifetime_spent() -> dict:
    """{user_id: مجموع خرید} برای همه‌ی کاربرها با حداقل یک خرید تاییدشده - برای جاب ماهانه‌ی باشگاه مشتریان"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT user_id, plan_id FROM orders WHERE status = 'approved' AND kind IN ('new', 'renew')"
        ).fetchall()
    totals = {}
    for row in rows:
        plan = get_plan(row["plan_id"])
        if not plan:
            continue
        totals[row["user_id"]] = totals.get(row["user_id"], 0) + plan["price"]
    return totals


def get_top_spenders(limit: int = 10):
    """[(user_id, مجموع خرید), ...] به ترتیب نزولی - برای لیدربرد باشگاه مشتریان"""
    totals = get_all_lifetime_spent()
    return sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:limit]


def get_spender_rank(user_id: int):
    """رتبه‌ی ۱-پایه‌ی این کاربر بین همه‌ی خریدارها؛ اگه هنوز خریدی نداشته None"""
    totals = get_all_lifetime_spent()
    my_total = totals.get(user_id, 0)
    if my_total <= 0:
        return None
    return 1 + sum(1 for v in totals.values() if v > my_total)


def mark_loyalty_bonus_given(user_id: int, month_key: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET loyalty_bonus_month = ? WHERE user_id = ?", (month_key, user_id))


def get_lifetime_topup(user_id: int) -> int:
    """مجموع همه‌ی شارژهای موفق کیف پول (نه مبلغ خرج‌شده) - برای احراز شرایط نمایندگی"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS c FROM wallet_transactions WHERE user_id = ? AND tx_type = 'topup'",
            (user_id,),
        ).fetchone()
        return row["c"]


def is_reseller(user_id: int) -> bool:
    user = get_user(user_id)
    return bool(user and user["is_reseller"])


def set_reseller(user_id: int, enabled: bool):
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_reseller = ? WHERE user_id = ?", (1 if enabled else 0, user_id))


def get_pending_reseller_request(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM reseller_requests WHERE user_id = ? AND status = 'pending' ORDER BY request_id DESC LIMIT 1",
            (user_id,),
        ).fetchone()


def create_reseller_request(user_id: int, message: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO reseller_requests (user_id, message, status, created_at) VALUES (?, ?, 'pending', ?)",
            (user_id, message, int(time.time())),
        )
        return cur.lastrowid


def get_reseller_request(request_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM reseller_requests WHERE request_id = ?", (request_id,)
        ).fetchone()


def set_reseller_request_status(request_id: int, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE reseller_requests SET status = ?, decided_at = ? WHERE request_id = ?",
            (status, int(time.time()), request_id),
        )


def get_referral_orders(referrer_id: int):
    """سفارش‌های تاییدشده‌ی (خرید/تمدید) همه‌ی زیرمجموعه‌های این کاربر"""
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT o.plan_id, o.kind
            FROM orders o
            JOIN users u ON u.user_id = o.user_id
            WHERE u.referred_by = ? AND o.status = 'approved' AND o.kind IN ('new', 'renew')
            """,
            (referrer_id,),
        ).fetchall()


def maybe_reward_referrer(user_id: int):
    """
    وقتی کاربری اولین خریدش رو تایید کرد، اگه معرف داشته و هنوز پاداش
    بهش داده نشده، مبلغ REFERRAL_BONUS_TOMAN رو به کیف پول معرف اضافه می‌کنه.
    """
    user = get_user(user_id)
    if not user or not user["referred_by"]:
        return
    # علامت‌گذاری اتمیک «پاداش داده شد» قبل از پرداخت؛ دو خرید همزمان نمی‌تونن پاداش رو دوبار بدن
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE users SET referral_bonus_given = 1 WHERE user_id = ? AND referral_bonus_given = 0", (user_id,)
        )
        if cur.rowcount != 1:
            return
    adjust_wallet_balance_logged(
        user["referred_by"], REFERRAL_BONUS_TOMAN, "referral_bonus", f"پاداش معرفی کاربر {user_id}"
    )


# ---------------- سفارش‌ها ----------------
def create_order(
    user_id: int,
    plan_id: str,
    receipt_file_id: str,
    kind: str = "new",
    renew_sub_id: int = None,
    amount: int = None,
    custom_name: str = None,
    discount_code: str = None,
    discount_percent: int = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO orders
                (user_id, plan_id, kind, renew_sub_id, amount, status, receipt_file_id,
                 custom_name, discount_code, discount_percent, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
            """,
            (
                user_id, plan_id, kind, renew_sub_id, amount, receipt_file_id, custom_name,
                discount_code, discount_percent, int(time.time()),
            ),
        )
        return cur.lastrowid


def set_order_admin_message(order_id: int, message_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET admin_message_id = ? WHERE order_id = ?",
            (message_id, order_id),
        )


def get_order(order_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()


def set_order_status(order_id: int, status: str, decided_by: int):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE orders SET status = ?, decided_at = ?, decided_by = ?
            WHERE order_id = ?
            """,
            (status, int(time.time()), decided_by, order_id),
        )


def claim_order_approval(order_id: int, decided_by: int) -> bool:
    """pending → approved اتمیک؛ دوبار زدن دکمه‌ی «تایید» (یا دو ادمین) نمی‌تونه دوبار شارژ/تحویل بده"""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE orders SET status = 'approved', decided_at = ?, decided_by = ? WHERE order_id = ? AND status = 'pending'",
            (int(time.time()), decided_by, order_id),
        )
        return cur.rowcount == 1


def release_order_approval(order_id: int):
    """اگه تایید به‌خاطر خطا کامل نشد، سفارش برمی‌گرده به pending تا ادمین دوباره تایید کنه"""
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET status = 'pending', decided_at = NULL, decided_by = NULL "
            "WHERE order_id = ? AND status = 'approved'",
            (order_id,),
        )


def count_pending_orders() -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM orders WHERE status = 'pending'"
        ).fetchone()
        return row["c"]


def count_orders_today() -> int:
    since = int(time.time()) - 24 * 3600
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM orders WHERE created_at >= ?", (since,)
        ).fetchone()
        return row["c"]


def has_approved_order_before(user_id: int) -> bool:
    """آیا این کاربر قبلا حداقل یک خرید تاییدشده داشته؟ (برای پاداش رفرال یک‌باره)"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM orders WHERE user_id = ? AND status = 'approved'",
            (user_id,),
        ).fetchone()
        return row["c"] > 0


# ---------------- سرویس‌ها (ساب‌اسکریپشن) ----------------
def create_subscription(
    user_id: int,
    order_id: int,
    plan_id: str,
    marzban_username: str,
    plan_title: str,
    expire_at: int,
    sub_link: str,
    remark_prefix: str = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO subscriptions
                (user_id, order_id, plan_id, marzban_username, plan_title, expire_at, sub_link, created_at, remark_prefix)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, order_id, plan_id, marzban_username, plan_title, expire_at, sub_link, int(time.time()), remark_prefix),
        )
        return cur.lastrowid


def get_user_subscriptions(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()


def get_all_active_subscriptions():
    """
    همه‌ی سرویس‌هایی که یه یوزرنیم واقعی رو پنل دارن (چه تست رایگان چه
    پولی) - برای جاب دوره‌ای چک حجم مصرفی استفاده میشه.
    """
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM subscriptions WHERE marzban_username IS NOT NULL AND marzban_username != ''"
        ).fetchall()


def get_subscription(sub_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM subscriptions WHERE sub_id = ?", (sub_id,)
        ).fetchone()


def username_taken(name: str) -> bool:
    """آیا این اسم (یوزرنیم پنل) قبلاً روی یه سرویس ثبت شده؟ (بدون حساسیت به حروف بزرگ/کوچک)"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM subscriptions WHERE LOWER(marzban_username) = LOWER(?) LIMIT 1", (name,)
        ).fetchone()
        return row is not None


def get_remark_prefix_by_username(username: str):
    """پیشوند اسم کانفیگِ اختصاصیِ سرویسی که این یوزرنیم رو داره (یا None = پیشوند پیش‌فرض برند)"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT remark_prefix FROM subscriptions WHERE marzban_username = ? LIMIT 1", (username,)
        ).fetchone()
        return (row["remark_prefix"] or None) if row else None


def set_auto_renew(sub_id: int, enabled: bool):
    with get_conn() as conn:
        conn.execute(
            "UPDATE subscriptions SET auto_renew = ? WHERE sub_id = ?", (1 if enabled else 0, sub_id)
        )


def update_subscription_after_renew(sub_id: int, new_expire_at: int, new_plan_title: str, new_plan_id: str):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE subscriptions
            SET expire_at = ?, plan_title = ?, plan_id = ?, data_warning_sent = 0, expiry_warning_sent = 0,
                ended_at = NULL, ended_reason = NULL, final_warning_sent = 0
            WHERE sub_id = ?
            """,
            (new_expire_at, new_plan_title, new_plan_id, sub_id),
        )


def set_subscription_note(sub_id: int, note: str):
    with get_conn() as conn:
        conn.execute("UPDATE subscriptions SET note = ? WHERE sub_id = ?", (note, sub_id))


def update_subscription_link(sub_id: int, new_link: str):
    with get_conn() as conn:
        conn.execute("UPDATE subscriptions SET sub_link = ? WHERE sub_id = ?", (new_link, sub_id))


def transfer_subscription(sub_id: int, new_user_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE subscriptions SET user_id = ? WHERE sub_id = ?", (new_user_id, sub_id))


def delete_subscription(sub_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM subscriptions WHERE sub_id = ?", (sub_id,))


def mark_data_warning_sent(sub_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE subscriptions SET data_warning_sent = 1 WHERE sub_id = ?", (sub_id,))


def mark_expiry_warning_sent(sub_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE subscriptions SET expiry_warning_sent = 1 WHERE sub_id = ?", (sub_id,))


def mark_subscription_ended(sub_id: int, reason: str, ended_at: int, final_warning_sent: bool = False):
    """
    سرویس وارد «مهلت تمدید» میشه (reason = 'time' یا 'data'). فقط اگه قبلاً
    پایان‌یافته علامت نخورده باشه اثر داره (جلوی ریست‌شدن ساعت مهلت رو می‌گیره).
    خروجی True یعنی همین الان علامت خورد.
    """
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE subscriptions
            SET ended_at = ?, ended_reason = ?, final_warning_sent = ?
            WHERE sub_id = ? AND ended_at IS NULL
            """,
            (ended_at, reason, 1 if final_warning_sent else 0, sub_id),
        )
        return cur.rowcount > 0


def touch_last_seen(user_id: int, session_gap: int = 1800):
    """
    فعالیت کاربر رو ثبت می‌کنه و «آخرین ورودِ قبلی» (ثانیه) رو برمی‌گردونه (None = اولین بازدید).
    اگه از آخرین فعالیت بیشتر از session_gap ثانیه گذشته باشه، نشست جدیده و نشست قبلی میشه prev_seen؛
    وگرنه prev_seen عوض نمیشه (تا با هر بار «برگشت به منو» «آخرین ورود» چند ثانیه‌ی پیش نشون داده نشه).
    """
    now = int(time.time())
    with get_conn() as conn:
        row = conn.execute("SELECT last_seen, prev_seen FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return None
        last, prev = row["last_seen"], row["prev_seen"]
        if last is None or now - last > session_gap:
            prev = last
            conn.execute("UPDATE users SET prev_seen = ?, last_seen = ? WHERE user_id = ?", (prev, now, user_id))
        else:
            conn.execute("UPDATE users SET last_seen = ? WHERE user_id = ?", (now, user_id))
        return prev


def get_weekly_summary_users(today: str) -> list:
    """
    کاربرایی که امروز (today = 'YYYY-MM-DD') باید خلاصه‌ی هفتگی بگیرن: خلاصه‌شون خاموش نشده،
    امروز براشون فرستاده نشده، و حداقل یه سرویس پولیِ فعال (نه تست، نه پایان‌یافته) دارن.
    """
    now = int(time.time())
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT u.user_id FROM users u JOIN subscriptions s ON s.user_id = u.user_id
            WHERE u.weekly_summary = 1
              AND (u.weekly_summary_last IS NULL OR u.weekly_summary_last != ?)
              AND s.ended_at IS NULL AND s.plan_id != 'trial'
              AND (s.expire_at IS NULL OR s.expire_at = 0 OR s.expire_at > ?)
            """,
            (today, now),
        ).fetchall()
        return [r["user_id"] for r in rows]


def log_lifecycle(event: str, user_id: int, sub_id: int):
    """ثبت یه رویداد چرخه‌ی عمر؛ هیچ‌وقت خطا نمیده (گزارش‌گیری نباید جلوی کار اصلی رو بگیره)"""
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO lifecycle_log (event, user_id, sub_id, at) VALUES (?, ?, ?, ?)",
                (event, user_id, sub_id, int(time.time())),
            )
    except Exception:
        pass


def get_report_data(start: int, end: int) -> dict:
    """
    اعداد گزارش ادمین برای بازه‌ی [start, end) (timestamp) + چند عدد «لحظه‌ای» (الان).
    محاسبه‌ی مبلغ (به تومان) سمت admin_report.py انجام میشه چون قیمت پلن‌ها تو config ـه.
    """
    now = int(time.time())
    with get_conn() as conn:
        orders = conn.execute(
            """
            SELECT kind, plan_id, discount_percent, amount FROM orders
            WHERE status = 'approved' AND COALESCE(decided_at, created_at) >= ? AND COALESCE(decided_at, created_at) < ?
            """,
            (start, end),
        ).fetchall()
        one = lambda sql, args=(): conn.execute(sql, args).fetchone()[0]
        return {
            "orders": [dict(r) for r in orders],
            "new_users": one("SELECT COUNT(*) FROM users WHERE joined_at >= ? AND joined_at < ?", (start, end)),
            "trials": one(
                "SELECT COUNT(*) FROM subscriptions WHERE plan_id = 'trial' AND created_at >= ? AND created_at < ?",
                (start, end),
            ),
            "ended": one(
                "SELECT COUNT(*) FROM lifecycle_log WHERE event IN ('ended_time', 'ended_data') AND at >= ? AND at < ?",
                (start, end),
            ),
            "deleted": one(
                "SELECT COUNT(*) FROM lifecycle_log WHERE event = 'deleted' AND at >= ? AND at < ?", (start, end)
            ),
            # لحظه‌ای
            "pending_orders": one("SELECT COUNT(*) FROM orders WHERE status = 'pending'"),
            "open_tickets": one("SELECT COUNT(*) FROM tickets WHERE status = 'open'"),
            "expiring_3d": one(
                "SELECT COUNT(*) FROM subscriptions WHERE ended_at IS NULL AND plan_id != 'trial' AND expire_at > ? AND expire_at <= ?",
                (now, now + 3 * 86400),
            ),
            "in_grace": one("SELECT COUNT(*) FROM subscriptions WHERE ended_at IS NOT NULL"),
            "active_paid": one(
                "SELECT COUNT(*) FROM subscriptions WHERE ended_at IS NULL AND plan_id != 'trial' "
                "AND (expire_at IS NULL OR expire_at = 0 OR expire_at > ?)",
                (now,),
            ),
        }


def mark_weekly_summary_sent(user_id: int, today: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET weekly_summary_last = ? WHERE user_id = ?", (today, user_id))


def set_weekly_summary(user_id: int, enabled: bool):
    with get_conn() as conn:
        conn.execute("UPDATE users SET weekly_summary = ? WHERE user_id = ?", (1 if enabled else 0, user_id))


# ---------------- پاداش روزانه (زنجیره‌ی روزها) ----------------
def has_paid_purchase(user_id: int) -> bool:
    """آیا کاربر حداقل یه خرید/تمدید تاییدشده داره؟ (شرط گرفتن جایزه‌ی مایل‌استون)"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM orders WHERE user_id = ? AND kind IN ('new', 'renew') AND status = 'approved'",
            (user_id,),
        ).fetchone()
        return row["c"] > 0


def set_user_flag(user_id: int, flag: str):
    """پرچم رو (یک‌بار) ثبت می‌کنه؛ تکراری بودنش مشکلی نداره"""
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_flags (user_id, flag, created_at) VALUES (?, ?, ?)",
            (user_id, flag, int(time.time())),
        )


def has_user_flag(user_id: int, flag: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM user_flags WHERE user_id = ? AND flag = ?", (user_id, flag)
        ).fetchone()
        return row is not None


def get_checkin_row(user_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM daily_checkins WHERE user_id = ?", (user_id,)).fetchone()


def claim_checkin(user_id: int, today: str, yesterday: str, now_ts: int, percent_for, cooldown_seconds: int,
                  reward_allowed: bool) -> dict:
    """
    ثبت اتمیکِ «دریافت امروز». خروجی:
      already       True یعنی امروز قبلاً گرفته (هیچ چیز عوض نشد)
      streak/best/total   وضعیت بعد از ثبت
      milestone     {"days","percent"} اگه امروز به یه مایل‌استون رسید، وگرنه None
      granted       True اگه جایزه‌ی این مایل‌استون واقعاً باید داده بشه (مجازه و cooldown گذشته)
      locked        اگه مایل‌استون رسید ولی جایزه داده نمیشه: 'no_purchase' یا 'cooldown'
      prev_reward_at   برای برگردوندن اگه ساخت کد شکست خورد
    percent_for(streak) درصد تخفیف مایل‌استون اون روز رو برمی‌گردونه (یا None).
    cooldown برای «هر مایل‌استون جدا»ست: رسیدن به روز ۷ بعد از جایزه‌ی روز ۳ مشکلی نداره، ولی گرفتنِ
    دوباره‌ی همون جایزه‌ی روز ۳ (با شکستن و دوباره شروع‌کردن زنجیره) باید cooldown رو صبر کنه.
    """
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM daily_checkins WHERE user_id = ?", (user_id,)).fetchone()
        if row and row["last_day"] == today:
            return {"already": True, "streak": row["streak"], "best": row["best"], "total": row["total"],
                    "milestone": None, "granted": False, "locked": None, "prev_reward_at": None}

        streak = (row["streak"] + 1) if (row and row["last_day"] == yesterday) else 1
        best = max(row["best"] if row else 0, streak)
        total = (row["total"] if row else 0) + 1
        prev_reward_at = None

        milestone, granted, locked = None, False, None
        percent = percent_for(streak)
        if percent:
            milestone = {"days": streak, "percent": percent}
            prev = conn.execute(
                "SELECT granted_at FROM daily_checkin_rewards WHERE user_id = ? AND milestone_days = ?",
                (user_id, streak),
            ).fetchone()
            prev_reward_at = prev["granted_at"] if prev else None
            if not reward_allowed:
                locked = "no_purchase"
            elif prev_reward_at is not None and now_ts - prev_reward_at < cooldown_seconds:
                locked = "cooldown"
            else:
                granted = True
                conn.execute(
                    """
                    INSERT INTO daily_checkin_rewards (user_id, milestone_days, granted_at) VALUES (?, ?, ?)
                    ON CONFLICT(user_id, milestone_days) DO UPDATE SET granted_at = excluded.granted_at
                    """,
                    (user_id, streak, now_ts),
                )

        if row:
            conn.execute(
                "UPDATE daily_checkins SET last_day = ?, streak = ?, best = ?, total = ? WHERE user_id = ?",
                (today, streak, best, total, user_id),
            )
        else:
            conn.execute(
                "INSERT INTO daily_checkins (user_id, last_day, streak, best, total) VALUES (?, ?, ?, ?, ?)",
                (user_id, today, streak, best, total),
            )
        return {"already": False, "streak": streak, "best": best, "total": total, "milestone": milestone,
                "granted": granted, "locked": locked, "prev_reward_at": prev_reward_at}


def save_checkin_code(user_id: int, code: str, percent: int, expires_at: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE daily_checkins SET last_code = ?, last_code_percent = ?, last_code_expires = ? WHERE user_id = ?",
            (code, percent, expires_at, user_id),
        )


def restore_checkin_reward(user_id: int, milestone_days: int, prev_reward_at):
    """اگه ساخت کد جایزه شکست خورد، cooldown اون مایل‌استون رو برمی‌گردونیم تا کاربر بی‌جایزه نسوزه"""
    with get_conn() as conn:
        if prev_reward_at is None:
            conn.execute(
                "DELETE FROM daily_checkin_rewards WHERE user_id = ? AND milestone_days = ?",
                (user_id, milestone_days),
            )
        else:
            conn.execute(
                "UPDATE daily_checkin_rewards SET granted_at = ? WHERE user_id = ? AND milestone_days = ?",
                (prev_reward_at, user_id, milestone_days),
            )


def mark_final_warning_sent(sub_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE subscriptions SET final_warning_sent = 1 WHERE sub_id = ?", (sub_id,))


def create_winback_code(percent: int, hours: int, prefix: str = "BACK", max_uses=1) -> str:
    """
    یه کد تخفیف شخصی، یک‌بارمصرف و کوتاه‌مدت می‌سازه (برای کاربری که سرویسش حذف شده)
    و خود کد رو برمی‌گردونه. از حروف/عددهای گیج‌کننده (O/0/I/1) استفاده نمیشه.
    """
    import secrets

    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    expires_at = int(time.time()) + int(hours) * 3600
    for _ in range(10):
        code = prefix + "".join(secrets.choice(alphabet) for _ in range(6))
        try:
            create_discount_code(code, percent, max_uses=max_uses, expires_at=expires_at)
            return code
        except sqlite3.IntegrityError:
            continue  # تصادفاً تکراری شد؛ یکی دیگه
    raise RuntimeError("ساخت کد تخفیف ناموفق بود")


# ---------------- تیکت‌های پشتیبانی ----------------
def create_ticket(user_id: int, subject: str) -> int:
    now = int(time.time())
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO tickets (user_id, subject, status, created_at, updated_at)
            VALUES (?, ?, 'open', ?, ?)
            """,
            (user_id, subject, now, now),
        )
        ticket_id = cur.lastrowid
        conn.execute(
            "INSERT INTO ticket_messages (ticket_id, sender, text, created_at) VALUES (?, 'user', ?, ?)",
            (ticket_id, subject, now),
        )
        return ticket_id


def add_ticket_message(ticket_id: int, sender: str, text: str):
    now = int(time.time())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ticket_messages (ticket_id, sender, text, created_at) VALUES (?, ?, ?, ?)",
            (ticket_id, sender, text, now),
        )
        conn.execute("UPDATE tickets SET updated_at = ? WHERE ticket_id = ?", (now, ticket_id))


def set_ticket_status(ticket_id: int, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE tickets SET status = ?, updated_at = ? WHERE ticket_id = ?",
            (status, int(time.time()), ticket_id),
        )


def get_tickets_to_auto_close(cutoff_ts: int, limit: int = 100):
    """تیکت‌هایی که آخرین پیامشون جواب پشتیبانیه (answered) و از اون موقع تا cutoff پیام جدیدی نیومده"""
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM tickets WHERE status = 'answered' AND updated_at < ? ORDER BY updated_at ASC LIMIT ?",
            (cutoff_ts, limit),
        ).fetchall()


def close_ticket_if_stale(ticket_id: int, cutoff_ts: int) -> bool:
    """بستن اتمیک: فقط اگه هنوز answered باشه و پیام جدیدی نیومده باشه (جلوی تداخل با پاسخ همزمان کاربر/ادمین)"""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE tickets SET status = 'closed', updated_at = ? WHERE ticket_id = ? AND status = 'answered' AND updated_at < ?",
            (int(time.time()), ticket_id, cutoff_ts),
        )
        return cur.rowcount > 0


def count_user_answered_tickets(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM tickets WHERE user_id = ? AND status = 'answered'", (user_id,)
        ).fetchone()
        return int(row["n"]) if row else 0


def set_ticket_admin_message(ticket_id: int, message_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE tickets SET admin_message_id = ? WHERE ticket_id = ?", (message_id, ticket_id)
        )


def get_ticket(ticket_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()


def get_user_tickets(user_id: int, limit: int = 20):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM tickets WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()


def get_ticket_messages(ticket_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY created_at ASC",
            (ticket_id,),
        ).fetchall()


def count_open_tickets() -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM tickets WHERE status IN ('open', 'answered')"
        ).fetchone()
        return row["c"]


# ---------------- فاکتورهای پرداخت کریپتو (xRocket) ----------------
def create_crypto_invoice(
    invoice_id: str,
    user_id: int,
    chat_id: int,
    message_id: int,
    kind: str,
    amount_toman: int,
    currency: str,
    amount_crypto: float,
    plan_id: str = None,
    sub_id: int = None,
    custom_name: str = None,
    discount_code: str = None,
    discount_percent: int = None,
):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO crypto_invoices
                (invoice_id, user_id, chat_id, message_id, kind, plan_id, sub_id,
                 amount_toman, currency, amount_crypto, custom_name, discount_code, discount_percent, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                invoice_id, user_id, chat_id, message_id, kind, plan_id, sub_id,
                amount_toman, currency, amount_crypto, custom_name, discount_code, discount_percent,
                int(time.time()),
            ),
        )


def get_crypto_invoice(invoice_id: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM crypto_invoices WHERE invoice_id = ?", (invoice_id,)
        ).fetchone()


def set_crypto_invoice_status(invoice_id: str, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE crypto_invoices SET status = ? WHERE invoice_id = ?", (status, invoice_id)
        )


def claim_crypto_invoice(invoice_id: str) -> bool:
    """pending → paid اتمیک؛ فقط یکی از (وب‌هوک/جاب/دکمه‌ی بررسی) حق تحویل رو می‌گیره"""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE crypto_invoices SET status = 'paid' WHERE invoice_id = ? AND status = 'pending'", (invoice_id,)
        )
        return cur.rowcount == 1


def release_crypto_invoice(invoice_id: str):
    """اگه تحویل با خطا مواجه شد، فاکتور برمی‌گرده به pending تا جاب دوباره تلاش کنه"""
    with get_conn() as conn:
        conn.execute(
            "UPDATE crypto_invoices SET status = 'pending' WHERE invoice_id = ? AND status = 'paid'", (invoice_id,)
        )


def get_pending_crypto_invoices():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM crypto_invoices WHERE status = 'pending'"
        ).fetchall()


# ---------------- فاکتورهای پرداخت خودکار کارت‌به‌کارت (AutoSMS) ----------------
def create_autosms_invoice(
    authority: str,
    order_id: str,
    user_id: int,
    chat_id: int,
    message_id: int,
    kind: str,
    base_amount_toman: int,
    pay_amount_toman: int,
    card_number: str,
    card_holder: str,
    expires_at: int,
    plan_id: str = None,
    sub_id: int = None,
    custom_name: str = None,
    discount_code: str = None,
    discount_percent: int = None,
):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO autosms_invoices
                (authority, order_id, user_id, chat_id, message_id, kind, plan_id, sub_id,
                 custom_name, discount_code, discount_percent, base_amount_toman,
                 pay_amount_toman, card_number, card_holder, status, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                authority, order_id, user_id, chat_id, message_id, kind, plan_id, sub_id,
                custom_name, discount_code, discount_percent, base_amount_toman,
                pay_amount_toman, card_number, card_holder, int(time.time()), expires_at,
            ),
        )


def get_autosms_invoice(authority: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM autosms_invoices WHERE authority = ?", (authority,)
        ).fetchone()


def set_autosms_invoice_status(authority: str, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE autosms_invoices SET status = ? WHERE authority = ?", (status, authority)
        )


def claim_autosms_invoice(authority: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE autosms_invoices SET status = 'paid' WHERE authority = ? AND status = 'pending'", (authority,)
        )
        return cur.rowcount == 1


def release_autosms_invoice(authority: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE autosms_invoices SET status = 'pending' WHERE authority = ? AND status = 'paid'", (authority,)
        )


def get_pending_autosms_invoices():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM autosms_invoices WHERE status = 'pending'"
        ).fetchall()


# ---------------- فاکتورهای درگاه TonPays ----------------
def create_tonpays_invoice(
    invoice_id: str,
    order_id: str,
    user_id: int,
    chat_id: int,
    message_id: int,
    kind: str,
    request_amount: int,
    final_amount: int,
    plan_id: str = None,
    sub_id: int = None,
    custom_name: str = None,
    discount_code: str = None,
    discount_percent: int = None,
):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO tonpays_invoices
                (invoice_id, order_id, user_id, chat_id, message_id, kind, plan_id, sub_id,
                 custom_name, discount_code, discount_percent, request_amount, final_amount, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                invoice_id, order_id, user_id, chat_id, message_id, kind, plan_id, sub_id,
                custom_name, discount_code, discount_percent, request_amount, final_amount,
                int(time.time()),
            ),
        )


def get_tonpays_invoice(invoice_id: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM tonpays_invoices WHERE invoice_id = ?", (invoice_id,)
        ).fetchone()


def set_tonpays_invoice_status(invoice_id: str, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE tonpays_invoices SET status = ? WHERE invoice_id = ?", (status, invoice_id)
        )


def claim_tonpays_invoice(invoice_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE tonpays_invoices SET status = 'paid' WHERE invoice_id = ? AND status = 'pending'", (invoice_id,)
        )
        return cur.rowcount == 1


def release_tonpays_invoice(invoice_id: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE tonpays_invoices SET status = 'pending' WHERE invoice_id = ? AND status = 'paid'", (invoice_id,)
        )


def get_pending_tonpays_invoices():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM tonpays_invoices WHERE status = 'pending'"
        ).fetchall()


# ---------------- فاکتورهای درگاه ویناپی (WinaPay) ----------------
def create_winapay_invoice(
    authority: str,
    order_id: str,
    user_id: int,
    chat_id: int,
    message_id: int,
    kind: str,
    amount: int,
    plan_id: str = None,
    sub_id: int = None,
    custom_name: str = None,
    discount_code: str = None,
    discount_percent: int = None,
):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO winapay_invoices
                (authority, order_id, user_id, chat_id, message_id, kind, plan_id, sub_id,
                 custom_name, discount_code, discount_percent, amount, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                authority, order_id, user_id, chat_id, message_id, kind, plan_id, sub_id,
                custom_name, discount_code, discount_percent, amount, int(time.time()),
            ),
        )


def get_winapay_invoice(authority: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM winapay_invoices WHERE authority = ?", (authority,)
        ).fetchone()


def claim_winapay_invoice(authority: str, ref_id: str = None) -> bool:
    """pending → paid به‌صورت اتمیک. فقط یکی از (کال‌بک مرورگر / job دوره‌ای / دکمه‌ی بررسی /
    API مینی‌اپ) برنده میشه و حق تحویل خدمت رو می‌گیره؛ جلوی تحویل دوباره رو می‌گیره."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE winapay_invoices SET status = 'paid', ref_id = ? WHERE authority = ? AND status = 'pending'",
            (str(ref_id) if ref_id is not None else None, authority),
        )
        return cur.rowcount == 1


def set_winapay_invoice_status(authority: str, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE winapay_invoices SET status = ? WHERE authority = ? AND status = 'pending'", (status, authority)
        )


def get_pending_winapay_invoices():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM winapay_invoices WHERE status = 'pending'"
        ).fetchall()


# ---------------- کد تخفیف ----------------
def create_discount_code(code: str, percent: int, max_uses: int = None, expires_at: int = None):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO discount_codes (code, percent, max_uses, used_count, active, expires_at, created_at)
            VALUES (?, ?, ?, 0, 1, ?, ?)
            """,
            (code.upper(), percent, max_uses, expires_at, int(time.time())),
        )


def get_discount_code(code: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM discount_codes WHERE code = ?", (code.upper(),)
        ).fetchone()


def list_discount_codes():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM discount_codes ORDER BY created_at DESC"
        ).fetchall()


def set_discount_code_active(code: str, active: bool):
    with get_conn() as conn:
        conn.execute(
            "UPDATE discount_codes SET active = ? WHERE code = ?", (1 if active else 0, code.upper())
        )


def has_user_used_discount(code: str, user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM discount_code_uses WHERE code = ? AND user_id = ?", (code.upper(), user_id)
        ).fetchone()
        return row is not None


def record_discount_use(code: str, user_id: int) -> bool:
    """
    استفاده‌ی این کاربر از کد رو ثبت می‌کنه و شمارنده‌ی کلی رو فقط وقتی یکی زیاد می‌کنه که این
    ثبت واقعاً جدید باشه (قبلاً با درخواست‌های تکراری شمارنده الکی بالا می‌رفت). True = ثبتِ جدید.
    """
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO discount_code_uses (code, user_id, used_at) VALUES (?, ?, ?)",
            (code.upper(), user_id, int(time.time())),
        )
        if cur.rowcount != 1:
            return False
        conn.execute(
            "UPDATE discount_codes SET used_count = used_count + 1 WHERE code = ?", (code.upper(),)
        )
        return True


def consume_discount_use(code: str, user_id: int):
    """
    اعتبارسنجی + مصرف کد تخفیف به‌صورت اتمیک (ظرفیت کل و یک‌بار-برای-هر-کاربر).
    خروجی: (ok, error_key) با error_key از: not_found / inactive / expired / max_uses / already_used
    """
    code = code.upper()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM discount_codes WHERE code = ?", (code,)).fetchone()
        if not row:
            return False, "not_found"
        if not row["active"]:
            return False, "inactive"
        if row["expires_at"] and row["expires_at"] < int(time.time()):
            return False, "expired"
        cur = conn.execute(
            "INSERT OR IGNORE INTO discount_code_uses (code, user_id, used_at) VALUES (?, ?, ?)",
            (code, user_id, int(time.time())),
        )
        if cur.rowcount != 1:
            return False, "already_used"
        cur2 = conn.execute(
            "UPDATE discount_codes SET used_count = used_count + 1 "
            "WHERE code = ? AND (max_uses IS NULL OR used_count < max_uses)",
            (code,),
        )
        if cur2.rowcount != 1:
            conn.execute("DELETE FROM discount_code_uses WHERE code = ? AND user_id = ?", (code, user_id))
            return False, "max_uses"
        return True, None


def release_discount_use(code: str, user_id: int):
    """برگشت مصرف کد (وقتی بعد از مصرف، صدور سرویس خطا داد)"""
    code = code.upper()
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM discount_code_uses WHERE code = ? AND user_id = ?", (code, user_id))
        if cur.rowcount:
            conn.execute(
                "UPDATE discount_codes SET used_count = MAX(0, used_count - 1) WHERE code = ?", (code,)
            )


def validate_discount_code(code: str, user_id: int):
    """
    کد رو کامل بررسی می‌کنه: وجود داشتن، فعال بودن، منقضی نشدن، ظرفیت تمام‌نشده،
    و این‌که همین کاربر قبلاً ازش استفاده نکرده باشه.
    خروجی: (ok: bool, error_key: str|None, row: sqlite3.Row|None)
    error_key یکی از این‌هاست: not_found / inactive / expired / max_uses / already_used
    """
    row = get_discount_code(code)
    if not row:
        return False, "not_found", None
    if not row["active"]:
        return False, "inactive", row
    if row["expires_at"] and row["expires_at"] < int(time.time()):
        return False, "expired", row
    if row["max_uses"] is not None and row["used_count"] >= row["max_uses"]:
        return False, "max_uses", row
    if has_user_used_discount(code, user_id):
        return False, "already_used", row
    return True, None, row


# ---------------- بنرهای اعلان مینی‌اپ (مدیریت از داخل بات با /newbanner و /banners) ----------------
def create_banner(fa, en=None, ru=None, theme: str = "gold", action: str = None,
                  url: str = None, expires_at: int = None, kind: str = None, code: str = None) -> int:
    """fa / en / ru هرکدوم یه tuple به شکل (عنوان، توضیح) هستن؛ en و ru اختیاری‌ان"""
    en = en or (None, None)
    ru = ru or (None, None)
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO banners (title_fa, body_fa, title_en, body_en, title_ru, body_ru,
                                 theme, action, url, active, expires_at, created_at, kind, code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (fa[0], fa[1], en[0], en[1], ru[0], ru[1], theme, action, url, expires_at, int(time.time()), kind, code),
        )
        return cur.lastrowid


def list_banners():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM banners ORDER BY created_at DESC, banner_id DESC").fetchall()


def get_banner(banner_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM banners WHERE banner_id = ?", (banner_id,)).fetchone()


def get_active_banners(limit: int = 8):
    """بنرهای فعال و منقضی‌نشده؛ تازه‌ترین اول"""
    now = int(time.time())
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT * FROM banners
            WHERE active = 1 AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY created_at DESC, banner_id DESC LIMIT ?
            """,
            (now, limit),
        ).fetchall()


def set_banner_active(banner_id: int, active: bool):
    with get_conn() as conn:
        conn.execute("UPDATE banners SET active = ? WHERE banner_id = ?", (1 if active else 0, banner_id))


def end_campaigns() -> int:
    """
    همه‌ی کمپین‌های فعال رو تموم می‌کنه: بنرشون غیرفعال میشه و کد تخفیفشون هم از کار می‌افته
    (کسی که کد رو ذخیره کرده بود دیگه نمی‌تونه ازش استفاده کنه). تعداد کمپین‌های تمام‌شده رو برمی‌گردونه.
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT banner_id, code FROM banners WHERE kind = 'campaign' AND active = 1"
        ).fetchall()
        for r in rows:
            conn.execute("UPDATE banners SET active = 0 WHERE banner_id = ?", (r["banner_id"],))
            if r["code"]:
                conn.execute("UPDATE discount_codes SET active = 0 WHERE code = ?", (r["code"].upper(),))
        return len(rows)


def count_active_banners_by_kind(kind: str) -> int:
    """تعداد بنرهای فعال و منقضی‌نشده از یه نوع (مثلاً 'outage')"""
    now = int(time.time())
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM banners WHERE kind = ? AND active = 1 AND (expires_at IS NULL OR expires_at > ?)",
            (kind, now),
        ).fetchone()
        return row["c"]


def deactivate_banners_by_kind(kind: str) -> int:
    """همه‌ی بنرهای فعال یه نوع رو غیرفعال می‌کنه؛ تعداد بنرهای غیرفعال‌شده رو برمی‌گردونه"""
    with get_conn() as conn:
        cur = conn.execute("UPDATE banners SET active = 0 WHERE kind = ? AND active = 1", (kind,))
        return cur.rowcount


# ---------------- مخاطب‌های اطلاعیه (برای /post و /outage) ----------------
AUDIENCE_ORDER = ["all", "active", "expiring", "ended", "no_purchase"]


def get_audience_user_ids(audience: str) -> list:
    """
    لیست آیدی کاربران یه گروه مخاطب:
      all         همه‌ی کاربران بات
      active      کاربرایی که حداقل یه سرویس فعال (پایان‌نیافته) دارن
      expiring    سرویس فعالی دارن که تا ۳ روز دیگه تموم میشه
      ended       سرویسی دارن که تموم شده و تو مهلت تمدیده
      no_purchase هنوز هیچ خرید/تمدید تاییدشده‌ای ندارن (فقط عضو یا تست‌گیرنده)
    فقط کاربرایی که تو جدول users هستن (یعنی بات رو استارت زدن) برمی‌گردن.
    """
    now = int(time.time())
    with get_conn() as conn:
        if audience == "all":
            rows = conn.execute("SELECT user_id FROM users").fetchall()
        elif audience == "active":
            rows = conn.execute(
                """
                SELECT DISTINCT u.user_id FROM users u JOIN subscriptions s ON s.user_id = u.user_id
                WHERE s.ended_at IS NULL AND (s.expire_at IS NULL OR s.expire_at = 0 OR s.expire_at > ?)
                """,
                (now,),
            ).fetchall()
        elif audience == "expiring":
            rows = conn.execute(
                """
                SELECT DISTINCT u.user_id FROM users u JOIN subscriptions s ON s.user_id = u.user_id
                WHERE s.ended_at IS NULL AND s.expire_at > ? AND s.expire_at <= ?
                """,
                (now, now + 3 * 86400),
            ).fetchall()
        elif audience == "ended":
            rows = conn.execute(
                """
                SELECT DISTINCT u.user_id FROM users u JOIN subscriptions s ON s.user_id = u.user_id
                WHERE s.ended_at IS NOT NULL
                """
            ).fetchall()
        elif audience == "no_purchase":
            rows = conn.execute(
                """
                SELECT u.user_id FROM users u
                WHERE NOT EXISTS (
                    SELECT 1 FROM orders o
                    WHERE o.user_id = u.user_id AND o.kind IN ('new', 'renew') AND o.status = 'approved'
                )
                """
            ).fetchall()
        else:
            raise ValueError(f"مخاطب نامعتبر: {audience}")
        return [r["user_id"] for r in rows]


def delete_banner(banner_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM banners WHERE banner_id = ?", (banner_id,))
