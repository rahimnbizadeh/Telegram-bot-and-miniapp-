"""
پیشنهاد هوشمند پلن بر اساس «مصرف واقعی» کاربر.

نکته‌ی مهم: قیمت همه‌ی پلن‌ها گیگی یکسانه، پس این ماژول هیچ‌وقت ادعای «ارزون‌تره» نمی‌کنه؛
فقط می‌گه کدوم پلن «با مصرف تو جور درمیاد» (حجمش تا آخر دوره کافیه) تا کاربر وسط دوره
بی‌حجم نمونه و پلن بی‌دلیل کوچیک/بزرگ نخره.

ماژول کاملاً مستقل و بدون وابستگی به تلگرام/پنل/دیتابیسه (فقط config) تا هم بات و هم
Flask مینی‌اپ دقیقاً یه منطق رو صدا بزنن و راحت تست بشه.
"""
from config import PLANS, get_plan

HEADROOM = 1.15          # ۱۵٪ حاشیه‌ی اطمینان روی مصرف میانگین
MIN_TRACKED_DAYS = 3     # با کمتر از این‌قدر روز داده، پیشنهاد نمیدیم (حدس‌زدن بی‌پایه نمی‌کنیم)
MIN_AVG_GB = 0.02        # مصرف تقریباً صفر (کمتر از ~۲۰ مگ در روز) پیشنهادی نمیخواد


def recommend_plan(avg_gb_per_day: float, prefer_months=None, plans=None):
    """
    پلنِ محدودِ (غیرنامحدود) مناسب مصرف رو برمی‌گردونه: حجمش تا آخر دورهٔ خودش
    (days × مصرف روزانه × حاشیه) کافی باشه. بین پلن‌های کافی، اونی که قیمت هر روزش
    کمتره (و بعد ارزون‌تر) انتخاب میشه؛ اگه prefer_months داده بشه و پلن کافی هم‌مدت
    وجود داشته باشه، اول بین همون‌ها. اگه هیچ پلنی کافی نباشه، بزرگ‌ترین پلن (از نظر
    حجم در ماه) با sufficient=False برمی‌گرده.
    خروجی: (plan, sufficient) یا (None, False) اگه پلنی نیست.
    """
    plans = [p for p in (plans if plans is not None else PLANS) if not p.get("is_unlimited")]
    if not plans:
        return None, False

    def fits(p):
        return p["gb"] >= avg_gb_per_day * p["days"] * HEADROOM

    sufficient = [p for p in plans if fits(p)]
    if sufficient:
        pool = sufficient
        if prefer_months is not None:
            same = [p for p in sufficient if p.get("duration_months") == prefer_months]
            if same:
                pool = same
        best = min(pool, key=lambda p: (p["price"] / max(1, p["days"]), p["price"]))
        return best, True

    biggest = max(plans, key=lambda p: p["gb"] / max(1, p["days"]))
    return biggest, False


def usage_outlook(avg_gb_per_day: float, remaining_gb, remaining_days):
    """
    با مصرف فعلی حجم کی تموم میشه؟
    خروجی: {"days_to_depleted": float|None, "runs_out_early": bool}
    runs_out_early یعنی حجم قبل از پایان مدت سرویس تموم میشه. برای حجم/زمان نامحدود None.
    """
    if remaining_gb is None or avg_gb_per_day is None or avg_gb_per_day < MIN_AVG_GB:
        return {"days_to_depleted": None, "runs_out_early": False}
    days_to_depleted = remaining_gb / avg_gb_per_day
    early = remaining_days is not None and remaining_days > 0 and days_to_depleted < remaining_days
    return {"days_to_depleted": days_to_depleted, "runs_out_early": bool(early)}


def build_recommendation(current_plan_id, remaining_gb, remaining_days, avg_gb_per_day, tracked_days):
    """
    خروجی نهایی برای بات و مینی‌اپ (یا None اگه داده‌ی کافی نیست):
      plan_id, title, gb, price, avg_gb, sufficient, runs_out_early, days_to_depleted
    """
    if tracked_days is None or tracked_days < MIN_TRACKED_DAYS:
        return None
    if avg_gb_per_day is None or avg_gb_per_day < MIN_AVG_GB:
        return None

    current = get_plan(current_plan_id) if current_plan_id else None
    prefer = current.get("duration_months") if current else None
    plan, sufficient = recommend_plan(avg_gb_per_day, prefer_months=prefer)
    if plan is None:
        return None

    outlook = usage_outlook(avg_gb_per_day, remaining_gb, remaining_days)
    return {
        "plan_id": plan["id"],
        "title": plan["title"],
        "gb": plan["gb"],
        "price": plan["price"],
        "avg_gb": round(float(avg_gb_per_day), 2),
        "sufficient": sufficient,
        "runs_out_early": outlook["runs_out_early"],
        "days_to_depleted": (round(outlook["days_to_depleted"], 1) if outlook["days_to_depleted"] is not None else None),
    }
