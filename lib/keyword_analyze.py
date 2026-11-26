#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""محلّل كلمات مفتاحية يقدّر صعوبة استهداف كلمة — جولة v0.1.61 (W1).

الفكرة (من طريقة «Keyword Analyzer» في GuinRank فقط، بلا نسخ كود):
المشغّل يزوّد مقاييس كلمة جاهزة (من أداة بحث كلمات أو فحص
يدوي)، والوحدة تحسب صعوبة 0–100 وتصنّفها وتحكم: استهداف أم
منافسة بحذر أم تجنّب — بلا شبكة وبلا LLM وبلا عشوائية.

الصيغة الموثّقة (كل مكوّن 0–100، والصعوبة تُقرَّب لعشرة واحدة):
    قوة SERP = (مطابقات العنوان في أول 10 نتائج / عدد النتائج
                المعتبرة من أول 10) × متوسط السلطة
    الصعوبة = 0.60 × المنافسة + 0.40 × قوة SERP
- «النتائج المعتبرة» هي أول 10 نتائج فقط؛ نتائج بعد العاشرة
  تُتجاهل. ومتوسط السلطة من قيم السلطة المزوّدة فقط في تلك
  النتائج العشر.
- إن غابت المنافسة → الصعوبة «غير مقاس» (None) مع السبب؛
  لا تُخترع منافسة ولا تُستنتج من غيرها.
- إن غاب SERP (لا مفتاح أو None أو قائمة فارغة) أو غابت
  السلطة عن كل نتائجه → جزء SERP صفر، والصعوبة من المنافسة
  وحدها، ويُعلَّم الجزء «غير مقاس» في السبب — لا أرقام مخترعة.

التصنيفات:
- الصعوبة: <30 «سهلة»، 30–59 «متوسطة»، ≥60 «صعبة»،
  وبلا منافسة «غير مقاس».
- المنافسة: <35 «منخفضة»، 35–64 «متوسطة»، ≥65 «عالية»،
  وبلا منافسة «غير مقاس».

الحكم (يُفحص التجنّب أولًا):
- «تجنب الآن»: الصعوبة ≥65 أو المنافسة ≥80.
- «استهدف»: الصعوبة <40.
- «نافس بحذر»: الصعوبة 40–64.
- «غير محدد»: الصعوبة غير مقاسة والمنافسة <80 (لا حكم بلا
  صعوبة ولا منافسة عالية).

مرجع المعايرة — بيانات الاستوديو المقاسة 2026-11-26 من
vidIQ (أمثلة مدخلات لا بيانات حية):
- «قصص»: حجم ~483,574 ومنافسة 59.
- «قصص واقعية»: حجم 39,618 ونمو +92.6% ومنافسة 40.
- «قصص اطفال»: حجم 75,888 ومنافسة 32.
هذه الأرقام أمثلة معايرة فقط؛ الوحدة لا تجلب أي بيانات
ولا تعرف أي حجم أو منافسة إلا ما يزوّده المشغّل.

قواعد الوحدة:
- المدخل قاموس metrics {volume?, competition?, growth_pct?,
  serp?} يزوّده المشغّل جاهزًا. قراءة فقط: بلا شبكة وبلا جلب.
- دوال خالصة على بيانات يزوّدها المشغّل: لا تقرأ ملفات
  بنفسها ولا تكتب ملفات.
- مدخلات فاسدة (كلمة فارغة، منافسة خارج 0–100، حجم سالب،
  سلطة خارج 0–100، JSON تالف) → ``ValueError`` عربي.
- كل تقرير يطبع سطر: «لا أرقام مخترعة: أي قيمة بلا مصدر
  تظهر «غير مقاس»».
"""
import json
import math

__all__ = [
    "analyze_keyword",
    "analyze_keywords",
    "format_report",
    "to_json",
    "load_keywords_json",
    "load_keyword_json",
]

# تصنيفات الصعوبة (قيم الإخراج — عربية).
DIFFICULTY_EASY = "سهلة"
DIFFICULTY_MEDIUM = "متوسطة"
DIFFICULTY_HARD = "صعبة"
UNMEASURED = "غير مقاس"

# تصنيفات المنافسة (قيم الإخراج — عربية).
COMPETITION_LOW = "منخفضة"
COMPETITION_MEDIUM = "متوسطة"
COMPETITION_HIGH = "عالية"

# الأحكام (قيم الإخراج — عربية).
VERDICT_TARGET = "استهدف"
VERDICT_CAREFUL = "نافس بحذر"
VERDICT_AVOID = "تجنب الآن"
VERDICT_UNKNOWN = "غير محدد"

# أوزان الصعوبة (المجموع 1.0).
COMPETITION_WEIGHT = 0.60
SERP_WEIGHT = 0.40

# حدّا تصنيف الصعوبة.
EASY_MAX = 30.0
HARD_MIN = 60.0

# حدّا تصنيف المنافسة.
COMPETITION_LOW_MAX = 35.0
COMPETITION_HIGH_MIN = 65.0

# حدّا الحكم.
TARGET_MAX = 40.0
AVOID_DIFFICULTY_MIN = 65.0
AVOID_COMPETITION_MIN = 80.0

# عدد نتائج SERP المعتبرة في الحساب.
SERP_TOP_N = 10

# سطر يُطبع في كل تقرير.
NO_INVENTED_NUMBERS = ("لا أرقام مخترعة: أي قيمة بلا مصدر "
                       "تظهر «غير مقاس».")

# مرجع المعايرة — بيانات الاستوديو المقاسة 2026-11-26 من
# vidIQ. أمثلة مدخلات لا بيانات حية: الوحدة لا تجلب شيئًا.
CALIBRATION_SOURCE = "بيانات vidIQ المقاسة 2026-11-26 — أمثلة معايرة لا بيانات حية"
CALIBRATION_EXAMPLES = (
    {"keyword": "قصص", "volume": 483574, "competition": 59},
    {"keyword": "قصص واقعية", "volume": 39618, "growth_pct": 92.6,
     "competition": 40},
    {"keyword": "قصص اطفال", "volume": 75888, "competition": 32},
)


def _check_number(value, name, minimum=None, maximum=None):
    """تحقّق أن القيمة عدد حقيقي منتهٍ (بلا bool) أو None."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"«{name}» يجب أن تكون رقمًا — وصلت قيمة غير رقمية.")
    if not math.isfinite(value):
        raise ValueError(f"«{name}» يجب أن تكون رقمًا منتهيًا.")
    if minimum is not None and value < minimum:
        raise ValueError(f"«{name}» أقل من الحد الأدنى {minimum} — قيمة غير صالحة.")
    if maximum is not None and value > maximum:
        raise ValueError(f"«{name}» أعلى من الحد الأقصى {maximum} — قيمة غير صالحة.")
    return value


def _check_volume(value):
    """الحجم الشهري: عدد غير سالب أو None."""
    value = _check_number(value, "الحجم", minimum=0)
    if value is None:
        return None
    return value


def _check_competition(value):
    """المنافسة: عدد 0–100 أو None."""
    return _check_number(value, "المنافسة", minimum=0, maximum=100)


def _clean_serp_entry(entry):
    """تحقّق من نتيجة SERP واحدة وأعدها منظّفة."""
    if not isinstance(entry, dict):
        raise ValueError("كل نتيجة SERP يجب أن تكون قاموسًا فيه domain.")
    domain = entry.get("domain")
    if not isinstance(domain, str) or not domain.strip():
        raise ValueError("نتيجة SERP بلا نطاق — كل نتيجة تحتاج domain نصيًا غير فارغ.")
    title_match = entry.get("title_match", False)
    if not isinstance(title_match, bool):
        raise ValueError("مطابقة العنوان (title_match) يجب أن تكون true أو false.")
    authority = _check_number(entry.get("authority"), "السلطة",
                              minimum=0, maximum=100)
    return {
        "domain": domain.strip(),
        "title_match": title_match,
        "authority": authority,
    }


def _clean_serp(serp):
    """نظّف قائمة SERP — أو None إن غابت (None أو غير موجودة)."""
    if serp is None:
        return None
    if not isinstance(serp, list):
        raise ValueError("نتائج SERP يجب أن تكون قائمة.")
    return [_clean_serp_entry(entry) for entry in serp]


def _clean_metrics(metrics):
    """تحقّق من قاموس metrics وأعده منظّفًا (None ← قاموس فارغ)."""
    if metrics is None:
        metrics = {}
    if not isinstance(metrics, dict):
        raise ValueError("مقاييس الكلمة (metrics) يجب أن تكون قاموسًا.")
    return {
        "volume": _check_volume(metrics.get("volume")),
        "competition": _check_competition(metrics.get("competition")),
        "growth_pct": _check_number(metrics.get("growth_pct"), "النمو"),
        "serp": _clean_serp(metrics.get("serp")),
    }


def _serp_strength(serp):
    """قوة SERP ‏0–100 من أول 10 نتائج — أو None إن لم تُقَس.

    نسبة مطابقة العنوان × متوسط السلطة المزوّدة. None إن
    غاب SERP أو كان فارغًا أو غابت السلطة عن كل نتائجه.
    ترجع (القوة، عدد المطابقات، عدد النتائج المعتبرة،
    متوسط السلطة).
    """
    if not serp:
        return None, 0, 0, None
    top = serp[:SERP_TOP_N]
    matches = sum(1 for entry in top if entry["title_match"])
    authorities = [entry["authority"] for entry in top
                   if entry["authority"] is not None]
    if not authorities:
        return None, matches, len(top), None
    avg_authority = sum(authorities) / len(authorities)
    strength = (matches / len(top)) * avg_authority
    return round(strength, 1), matches, len(top), round(avg_authority, 1)


def _difficulty_label(difficulty):
    """صنّف الصعوبة — «غير مقاس» إن كانت None."""
    if difficulty is None:
        return UNMEASURED
    if difficulty < EASY_MAX:
        return DIFFICULTY_EASY
    if difficulty < HARD_MIN:
        return DIFFICULTY_MEDIUM
    return DIFFICULTY_HARD


def _competition_label(competition):
    """صنّف المنافسة — «غير مقاس» إن كانت None."""
    if competition is None:
        return UNMEASURED
    if competition < COMPETITION_LOW_MAX:
        return COMPETITION_LOW
    if competition < COMPETITION_HIGH_MIN:
        return COMPETITION_MEDIUM
    return COMPETITION_HIGH


def _verdict(difficulty, competition):
    """احكم على الكلمة من الصعوبة والمنافسة (التجنّب أولًا)."""
    if competition is not None and competition >= AVOID_COMPETITION_MIN:
        return VERDICT_AVOID
    if difficulty is None:
        return VERDICT_UNKNOWN
    if difficulty >= AVOID_DIFFICULTY_MIN:
        return VERDICT_AVOID
    if difficulty < TARGET_MAX:
        return VERDICT_TARGET
    return VERDICT_CAREFUL


def _format_number(value):
    """نسّق عددًا بفواصل آلاف — أو «غير مقاس» إن كان None."""
    if value is None:
        return UNMEASURED
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,}"


def _reason(keyword_result):
    """سبب عربي يذكر الأرقام — و«غير مقاس» لأي قيمة بلا مصدر."""
    parts = []
    volume = keyword_result["volume"]
    if volume is None:
        parts.append("الحجم غير مقاس")
    else:
        parts.append(f"الحجم {_format_number(volume)} بحث/شهر")
    competition = keyword_result["competition"]
    if competition is None:
        parts.append("المنافسة غير مقاسة")
    else:
        parts.append(f"المنافسة {competition}/100 "
                     f"({keyword_result['competition_label']})")
    growth = keyword_result["growth_pct"]
    if growth is not None:
        parts.append(f"النمو {growth:+.1f}%")
    if keyword_result["serp_strength"] is None:
        parts.append("قوة SERP غير مقاسة (لا نتائج بسلطة مزوّدة)")
    else:
        parts.append(f"قوة SERP {keyword_result['serp_strength']}/100 "
                     f"({keyword_result['title_match_count']} من "
                     f"{keyword_result['serp_count']} عناوين مطابقة؛ "
                     f"متوسط السلطة {keyword_result['avg_authority']})")
    difficulty = keyword_result["difficulty"]
    if difficulty is None:
        parts.append("الصعوبة غير مقاسة — المنافسة غائبة")
    else:
        parts.append(f"الصعوبة {difficulty}/100 "
                     f"({keyword_result['difficulty_label']})")
    parts.append(f"الحكم: {keyword_result['verdict']}")
    return "؛ ".join(parts)


def analyze_keyword(keyword, metrics=None):
    """حلّل كلمة مفتاحية واحدة وقدّر صعوبة استهدافها.

    ``keyword``: نص غير فارغ. ``metrics``: قاموس {volume?,
    competition? (0–100), growth_pct?, serp?} — كل الحقول
    اختيارية، وserp قائمة {domain, title_match: bool,
    authority? (0–100)} يزوّدها المشغّل.

    الصعوبة = 0.60 × المنافسة + 0.40 × قوة SERP (انظر مقدّمة
    الوحدة). بلا منافسة → الصعوبة None («غير مقاس»)؛ وبلا
    SERP أو بلا سلطة فيه → جزء SERP صفر ومُعلَّم غير مقاس.

    ترجع قاموسًا فيه keyword وvolume وcompetition و
    competition_label وgrowth_pct وserp_strength و
    title_match_count وserp_count وavg_authority و
    serp_measured وdifficulty وdifficulty_label وverdict و
    reason. مدخلات فاسدة → ``ValueError`` عربي.
    """
    if not isinstance(keyword, str) or not keyword.strip():
        raise ValueError("الكلمة المفتاحية فارغة أو غير نص — أعطِ كلمة نصية.")
    clean = _clean_metrics(metrics)
    competition = clean["competition"]
    strength, matches, count, avg_authority = _serp_strength(clean["serp"])
    serp_measured = strength is not None
    serp_part = strength if serp_measured else 0.0
    if competition is None:
        difficulty = None
    else:
        difficulty = round(COMPETITION_WEIGHT * competition
                           + SERP_WEIGHT * serp_part, 1)
    result = {
        "keyword": keyword.strip(),
        "volume": clean["volume"],
        "competition": competition,
        "competition_label": _competition_label(competition),
        "growth_pct": clean["growth_pct"],
        "serp_strength": strength,
        "title_match_count": matches,
        "serp_count": count,
        "avg_authority": avg_authority,
        "serp_measured": serp_measured,
        "difficulty": difficulty,
        "difficulty_label": _difficulty_label(difficulty),
        "verdict": _verdict(difficulty, competition),
    }
    result["reason"] = _reason(result)
    return result


def _clean_batch_entry(entry):
    """تحقّق من إدخال دفعي {keyword, metrics?} وأعده منظّفًا."""
    if not isinstance(entry, dict):
        raise ValueError("كل إدخال دفعي يجب أن يكون قاموسًا فيه keyword.")
    keyword = entry.get("keyword")
    if not isinstance(keyword, str) or not keyword.strip():
        raise ValueError("إدخال دفعي بلا كلمة — كل إدخال يحتاج keyword نصيًا غير فارغ.")
    metrics = entry.get("metrics")
    if metrics is not None and not isinstance(metrics, dict):
        raise ValueError("مقاييس الكلمة (metrics) يجب أن تكون قاموسًا.")
    return {"keyword": keyword.strip(), "metrics": metrics or {}}


def _sort_key(result):
    """مفتاح ترتيب الدفعية: الصعوبة تصاعديًا ثم الحجم تنازليًا.

    غير المقاسة أخيرًا؛ وبلا حجم بعد ذوات الحجم؛ ثم الكلمة
    لكسر التعادل حتميًا.
    """
    difficulty = result["difficulty"]
    volume = result["volume"]
    return (
        1 if difficulty is None else 0,
        difficulty if difficulty is not None else 0.0,
        1 if volume is None else 0,
        -(volume if volume is not None else 0),
        result["keyword"],
    )


def analyze_keywords(keywords):
    """حلّل كلمات دفعيًا ورتّبها بالصعوبة تصاعديًا ثم الحجم تنازليًا.

    ``keywords``: قائمة قواميس {keyword, metrics?} أو نص
    JSON بنفس الصيغة (يُقرأ عبر ``load_keywords_json``).
    القائمة الفارغة ترجع [] — لا خطأ. غير المقاسة (بلا
    منافسة) في آخر الترتيب. مدخلات فاسدة → ``ValueError``
    عربي.
    """
    if isinstance(keywords, str):
        keywords = load_keywords_json(keywords)
    if not isinstance(keywords, (list, tuple)):
        raise ValueError("مدخل الدفعية يجب أن يكون قائمة كلمات.")
    results = [analyze_keyword(entry["keyword"], entry["metrics"])
               for entry in (_clean_batch_entry(e) for e in keywords)]
    results.sort(key=_sort_key)
    return results


def load_keywords_json(text):
    """اقرأ مدخل JSON نصيًا إلى قائمة إدخالات دفعية منظّفة.

    يرفع ``ValueError`` عربيًا عند JSON تالف أو مدخل ليس
    قائمة أو إدخال فاسد — بلا أي كتابة.
    """
    if not isinstance(text, str):
        raise ValueError("مدخل JSON يجب أن يكون نصًا.")
    try:
        data = json.loads(text)
    except ValueError:
        raise ValueError("مدخل JSON تالف — أعطِ قائمة كلمات JSON صالحة.")
    if not isinstance(data, list):
        raise ValueError("مدخل الكلمات يجب أن يكون قائمة.")
    return [_clean_batch_entry(entry) for entry in data]


def load_keyword_json(text):
    """اقرأ مدخل JSON نصيًا إلى إدخال كلمة واحدة منظّف.

    المدخل قاموس {keyword, metrics?} — يرفع ``ValueError``
    عربيًا عند JSON تالف أو مدخل ليس قاموسًا أو كلمة فاسدة.
    """
    if not isinstance(text, str):
        raise ValueError("مدخل JSON يجب أن يكون نصًا.")
    try:
        data = json.loads(text)
    except ValueError:
        raise ValueError("مدخل JSON تالف — أعطِ قاموس كلمة JSON صالحًا.")
    if not isinstance(data, dict):
        raise ValueError("مدخل الكلمة يجب أن يكون قاموسًا فيه keyword.")
    return _clean_batch_entry(data)


def to_json(result):
    """سلسل نتيجة ``analyze_keyword`` أو ``analyze_keywords`` إلى JSON عربي."""
    if not isinstance(result, (dict, list)):
        raise ValueError("نتيجة المحلّل يجب أن تكون قاموسًا أو قائمة من analyze_keyword.")
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def _report_entry_lines(result):
    """سطران أو ثلاثة لكل نتيجة في التقرير."""
    lines = [f"«{result['keyword']}» — الصعوبة: "
             + (f"{result['difficulty']}/100 "
                f"({result['difficulty_label']})"
                if result["difficulty"] is not None
                else "غير مقاسة")
             + f" | الحكم: {result['verdict']}"]
    volume = result["volume"]
    lines.append("   الحجم: "
                 + (f"{_format_number(volume)} بحث/شهر"
                    if volume is not None else UNMEASURED)
                 + f" | المنافسة: "
                 + (f"{result['competition']}/100 "
                    f"({result['competition_label']})"
                    if result["competition"] is not None
                    else UNMEASURED))
    if result["growth_pct"] is not None:
        lines.append(f"   النمو: {result['growth_pct']:+.1f}%")
    lines.append(f"   {result['reason']}")
    return lines


def format_report(result):
    """نسّق نتيجة المحلّل تقريرًا عربيًا.

    يقبل نتيجة مفردة (قاموس من ``analyze_keyword``) أو
    دفعية (قائمة من ``analyze_keywords`` أو قاموس فيه
    مفتاح ``results``). يحوي دائمًا سطر «لا أرقام مخترعة».
    """
    if isinstance(result, dict) and "results" in result:
        results = result["results"]
        if not isinstance(results, list):
            raise ValueError("نتيجة المحلّل ناقصة — «results» يجب أن تكون قائمة.")
        title = "محلّل الكلمات المفتاحية — تقرير دفعي"
    elif isinstance(result, list):
        results = result
        title = "محلّل الكلمات المفتاحية — تقرير دفعي"
    elif isinstance(result, dict) and "keyword" in result:
        results = [result]
        title = "محلّل الكلمات المفتاحية — تقرير كلمة"
    else:
        raise ValueError("نتيجة المحلّل يجب أن تكون قاموسًا من analyze_keyword "
                         "أو قائمة من analyze_keywords.")
    for entry in results:
        for key in ("keyword", "difficulty", "verdict", "reason"):
            if key not in entry:
                raise ValueError(f"نتيجة المحلّل ناقصة — ينقصها «{key}».")
    lines = [title, "=" * len(title)]
    if not results:
        lines.append("لا كلمات — القائمة فارغة.")
    for i, entry in enumerate(results, 1):
        if len(results) > 1:
            entry_lines = _report_entry_lines(entry)
            entry_lines[0] = f"{i}. {entry_lines[0]}"
            lines.extend(entry_lines)
        else:
            lines.extend(_report_entry_lines(entry))
    lines.append("")
    lines.append(NO_INVENTED_NUMBERS)
    return "\n".join(lines)
