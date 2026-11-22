#!/usr/bin/env python3
"""توقع رصيد Veo — `studio.py balance`.

يقرأ الرصيد المسجَّل في الإعداد (قسم `veo`: الرصيد الحالي
بالوحدات، وتاريخ التجديد، وتكلفة الفيديو اليومي) فيحسب: كم
يوم يكفي + تاريخ النفاد المتوقع + توصية (التحول لـ OpenMontage).

صراحة مهمة: الرصيد مسجَّل في الإعداد وليس حيًا من أي API —
لا يوجد واجهة رسمية لرصيد Flow/Veo؛ فحدّث `veo.balance_units`
في config.yaml يدويًا بعد كل توليد في Flow (أو مرّر
`--balance` في الأمر).
"""
import datetime

DEFAULT_BALANCE = 750
DEFAULT_RENEWS = "2026-12-13"
DEFAULT_COST_MIN = 100
DEFAULT_COST_MAX = 140
# سقوف عقلانية تمنع انهيار الحساب (timedelta ينفجر فوق ~2.7 مليون
# سنة): رصيد فوق 100 مليون وحدة أو تكلفة فوق مليون وحدة للفيديو
# ليست قيمًا حقيقية — تُرفض برسالة واضحة بدل تتبع استثناء.
MAX_BALANCE = 100_000_000
MAX_COST = 1_000_000


def _as_int(value, name):
    """حوّل قيمة عددية إلى int صحيح (يقبل int أو float صحيحًا
    أو نصًا رقميًا كما قد يأتي من config.yaml مقتبسًا).
    يرفع ValueError برسالة عربية عند أي قيمة غير عددية."""
    if isinstance(value, bool):
        raise ValueError("%s غير صالح: %s" % (name, value))
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.lstrip("-").isdigit():
            return int(text)
    raise ValueError("%s غير صالح: %s" % (name, value))


def forecast(balance_units, renews, cost_min, cost_max,
             today=None):
    """احسب التوقع. today: تاريخ date (الافتراضي: اليوم).
    يرجع قاموسًا بالأيام (أسوأ/متوسط/أفضل حالة) وتواريخ
    النفاد والتوصية."""
    balance_units = _as_int(balance_units, "الرصيد")
    cost_min = _as_int(cost_min, "أقل تكلفة")
    cost_max = _as_int(cost_max, "أعلى تكلفة")
    if balance_units is None or balance_units < 0:
        raise ValueError("الرصيد غير صالح: %s" % balance_units)
    if balance_units > MAX_BALANCE:
        raise ValueError("الرصيد غير صالح (فوق الحد %d): %s"
                         % (MAX_BALANCE, balance_units))
    if cost_min <= 0 or cost_max < cost_min:
        raise ValueError("تكلفة الفيديو اليومي غير صالحة: %s–%s"
                         % (cost_min, cost_max))
    if cost_max > MAX_COST:
        raise ValueError("تكلفة الفيديو اليومي غير صالحة (فوق الحد %d): %s"
                         % (MAX_COST, cost_max))
    try:
        renews_date = datetime.date.fromisoformat(renews)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("تاريخ التجديد غير صالح (YYYY-MM-DD): %s"
                         % renews)
    today = today or datetime.date.today()
    avg_cost = (cost_min + cost_max) / 2.0
    days_avg = balance_units / avg_cost
    days_worst = balance_units / cost_max
    days_best = balance_units / cost_min
    depletion_avg = today + datetime.timedelta(days=int(days_avg))
    depletion_worst = today + datetime.timedelta(days=int(days_worst))
    depletion_best = today + datetime.timedelta(days=int(days_best))
    days_to_renew = (renews_date - today).days
    if depletion_avg < renews_date:
        recommendation = (
            "الرصيد سيكفي حتى %s تقريبًا؛ بعدها الفيديوهان "
            "OpenMontage بلا رصيد حتى التجديد في %s."
            % (depletion_avg.isoformat(), renews_date.isoformat()))
    else:
        recommendation = (
            "الرصيد يكفي حتى موعد التجديد في %s — لا حاجة "
            "لتغيير خطة النشر." % renews_date.isoformat())
    return {
        "balance_units": balance_units,
        "renews": renews_date.isoformat(),
        "cost_min": cost_min,
        "cost_max": cost_max,
        "cost_avg": round(avg_cost, 1),
        "today": today.isoformat(),
        "days_avg": round(days_avg, 1),
        "days_worst": round(days_worst, 1),
        "days_best": round(days_best, 1),
        "depletion_avg": depletion_avg.isoformat(),
        "depletion_worst": depletion_worst.isoformat(),
        "depletion_best": depletion_best.isoformat(),
        "days_to_renew": days_to_renew,
        "recommendation": recommendation,
        "recorded_not_live": True,
    }


def format_forecast(result):
    """نص عربي للتوقع مع التنبيه الصريح أنه مسجَّل لا حي."""
    lines = [
        "== توقع رصيد Veo ==",
        "الرصيد المسجَّل: %d وحدة (يتجدد في %s — بعد %d يومًا)"
        % (result["balance_units"], result["renews"],
           result["days_to_renew"]),
        "تكلفة فيديو Veo اليومي: %d–%d وحدة (متوسط %.0f)"
        % (result["cost_min"], result["cost_max"],
           result["cost_avg"]),
        "يكفي: %.1f يومًا في المتوسط (أسوأ حالة %.1f، أفضل "
        "حالة %.1f)" % (result["days_avg"], result["days_worst"],
                        result["days_best"]),
        "تاريخ النفاد المتوقع: %s (أسوأ حالة %s، أفضل حالة %s)"
        % (result["depletion_avg"], result["depletion_worst"],
           result["depletion_best"]),
        "التوصية: %s" % result["recommendation"],
        "",
        "تنبيه: هذا الرصيد مسجَّل في الإعداد وليس حيًا من API — "
        "حدّث veo.balance_units في config.yaml بعد كل توليد "
        "في Flow.",
    ]
    return "\n".join(lines) + "\n"
