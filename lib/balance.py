#!/usr/bin/env python3
"""توقع رصيد Veo — `studio.py balance`.

يقرأ الرصيد المسجَّل في الإعداد (قسم `veo`: الرصيد الحالي
بالوحدات، وتاريخ التجديد، وتكلفة الفيديو اليومي) فيحسب: كم
يوم يكفي + تاريخ النفاد المتوقع + توصية (التحول لـ OpenMontage).

صراحة مهمة: الرصيد مسجَّل في الإعداد وليس حيًا من أي API —
لا يوجد واجهة رسمية لرصيد Flow/Veo؛ فحدّث `veo.balance_units`
في config.yaml يدويًا بعد كل توليد في Flow (أو مرّر
`--balance` في الأمر).

عمر الرقم (الجولة 6): كل تحديث للرصيد يسجَّل معه
`veo.updated_at` بصيغة ISO مع المنطقة الزمنية، ويُعرض عمر
الرقم دائمًا بجانب القيمة. رصيد بلا `updated_at` (إعداد قديم)
يُعامل كـ«غير معروف العمر» لا كخطأ؛ ورصيد أقدم من 24 ساعة
يُعتبر قديمًا ويُحذَّر منه — فقد يكون تغيّر بعد آخر توليد.
"""
import datetime

DEFAULT_BALANCE = 750
DEFAULT_RENEWS = "2026-12-13"
DEFAULT_COST_MIN = 100
DEFAULT_COST_MAX = 140
# رصيد أقدم من هذا يُعتبر قديمًا (الجولة 6): آخر توليد في Flow
# قد يكون غيّره، فلا يُعتمد عليه بلا تحديث.
VEO_STALE_HOURS = 24
UNKNOWN_AGE_LABEL = "غير معروف العمر"
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


def _arabic_count(n, one, two, few, many):
    """صيغة عربية للعدد: 1/2/3–10/11+ (مثال: ساعة/ساعتين/
    ساعات/ساعة)."""
    if n == 1:
        return one
    if n == 2:
        return two
    if 3 <= n <= 10:
        return "%d %s" % (n, few)
    return "%d %s" % (n, many)


def now_iso(now=None):
    """الآن بصيغة ISO مع المنطقة الزمنية (للتسجيل في config)."""
    if now is None:
        now = datetime.datetime.now().astimezone()
    elif now.tzinfo is None:
        now = now.astimezone()
    return now.isoformat()


def parse_updated_at(value):
    """حوّل قيمة `veo.updated_at` إلى datetime واعٍ بالمنطقة،
    أو None إن غابت أو كانت غير صالحة (إعداد قديم — «غير
    معروف العمر» لا خطأ). يقبل نص ISO أو datetime جاهزًا —
    PyYAML قد يحوّل الطابع غير المقتبس في config.yaml إلى
    datetime عند القراءة."""
    if isinstance(value, datetime.datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.datetime.fromisoformat(value.strip())
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        # بلا منطقة زمنية: اعتبرها توقيتًا محليًا.
        parsed = parsed.astimezone()
    return parsed


def balance_age(updated_at, now=None):
    """عمر الرصيد: يرجع (التسمية العربية، الساعات float أو None،
    قديم؟). بلا تاريخ صالح: («غير معروف العمر»، None، False)."""
    parsed = parse_updated_at(updated_at)
    if parsed is None:
        return UNKNOWN_AGE_LABEL, None, False
    if now is None:
        now = datetime.datetime.now().astimezone()
    elif now.tzinfo is None:
        now = now.astimezone()
    seconds = (now - parsed).total_seconds()
    if seconds < 0:
        return "الآن", 0.0, False
    hours = seconds / 3600.0
    if hours < 1:
        label = "منذ أقل من ساعة"
    elif hours < 24:
        label = "منذ " + _arabic_count(
            int(hours), "ساعة واحدة", "ساعتين", "ساعات", "ساعة")
    else:
        days = int(hours // 24)
        label = "منذ " + _arabic_count(
            days, "يوم واحد", "يومين", "أيام", "يومًا")
    return label, hours, hours > VEO_STALE_HOURS


def age_label(updated_at, now=None):
    """تسمية عمر الرصيد فقط (اختصار لـ balance_age)."""
    label, _, _ = balance_age(updated_at, now=now)
    return label


def is_balance_stale(updated_at, now=None,
                     stale_hours=VEO_STALE_HOURS):
    """هل الرصيد قديم (أقدم من stale_hours)؟ بلا تاريخ صالح:
    False — «غير معروف» ليس «قديمًا»."""
    parsed = parse_updated_at(updated_at)
    if parsed is None:
        return False
    if now is None:
        now = datetime.datetime.now().astimezone()
    elif now.tzinfo is None:
        now = now.astimezone()
    return (now - parsed).total_seconds() > stale_hours * 3600


def record_balance_update(veo, balance_units=None, now=None):
    """سجّل تحديثًا للرصيد: يرجع نسخة جديدة من قسم veo فيها
    `updated_at` (ISO مع المنطقة الزمنية)، و`balance_units`
    الجديد إن مُرّر. لا يعدّل القاموس الأصلي."""
    updated = dict(veo or {})
    if balance_units is not None:
        updated["balance_units"] = _as_int(balance_units, "الرصيد")
    updated["updated_at"] = now_iso(now)
    return updated


def forecast(balance_units, renews, cost_min, cost_max,
             today=None, updated_at=None, now=None):
    """احسب التوقع. today: تاريخ date (الافتراضي: اليوم).
    updated_at: وقت آخر تحديث للرصيد (ISO) — يُحمل في النتيجة
    مع تسمية عمره وعلامة القدم؛ وnow: لحظة «الآن» لحساب العمر
    (للاختبار؛ الافتراضي: الآن). يرجع قاموسًا بالأيام
    (أسوأ/متوسط/أفضل حالة) وتواريخ النفاد والتوصية."""
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
    age_text, age_hours, stale = balance_age(updated_at, now=now)
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
        "updated_at": updated_at,
        "age_label": age_text,
        "age_hours": age_hours,
        "stale": stale,
    }


def format_forecast(result):
    """نص عربي للتوقع مع التنبيه الصريح أنه مسجَّل لا حي، وعمر
    الرقم دائمًا بجانب القيمة (الجولة 6)."""
    age_text = result.get("age_label")
    if age_text is None:
        age_text, _, _ = balance_age(result.get("updated_at"))
    lines = [
        "== توقع رصيد Veo ==",
        "الرصيد المسجَّل: %d وحدة (يتجدد في %s — بعد %d يومًا)"
        % (result["balance_units"], result["renews"],
           result["days_to_renew"]),
        "عمر الرقم: %s" % age_text,
    ]
    if result.get("stale"):
        lines.append(
            "تحذير: الرصيد قديم (أكثر من 24 ساعة بلا تحديث) — "
            "قد يكون تغيّر بعد آخر توليد في Flow؛ حدّث "
            "veo.balance_units في config.yaml قبل الاعتماد عليه.")
    lines += [
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
