#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""مُحسِّن المحتوى (Content Optimizer) — جولة v0.1.61 (W2).

الفكرة (من طريقة Content Optimizer في GuinRank فقط، بلا نسخ كود —
GuinRank أداة تجارية مغلقة بلا مستودع وبلا API):
المشغّل يزوّد عنوانًا ووصفًا ونصًا وكلمة مفتاحية وقائمة عبارات
موصى بها (عبارات تستخدمها نتائج أول 20 في GuinRank — عندنا: من
بحث المشغّل)، والوحدة تقيّم المحتوى بدرجة 0–100 وتحدد حكمه
وتوصياته — بلا شبكة وبلا LLM وبلا عشوائية.

أوزان الدرجة (المجموع 100):
1. الكلمة المفتاحية في العنوان: 15 نقطة.
2. الكلمة المفتاحية في أول 120 حرفًا من الوصف: 10 نقاط.
3. كثافة الكلمة المفتاحية في النص: 20 نقطة كاملة داخل نطاق
   0.5%–2.5%، وصفر خارج النطاق البعيد، وجزئي قرب النطاق
   (تدرّج خطي: من صفر عند كثافة صفر إلى 20 عند 0.5%، ومن 20
   عند 2.5% إلى صفر عند 5%، وصفر فوق 5%).
4. تغطية العبارات الموصى بها الموجودة في النص: 30 نقطة
   تناسبيًا (الموجودة / الكل × 30)؛ وإن غابت العبارات الموصى
   بها فالمكوّن صفر ويُذكر «غير مقاس» — لا تُخترع تغطية.
5. طول النص: 10 نقاط عند 300 كلمة فأكثر، و5 نقاط عند
   150–299 كلمة، وصفر دون ذلك.
6. البنية: 10 نقاط عند وجود علامة عبرة («العبرة») أو سؤال
   ختامي (ينتهي النص بعلامة استفهام «؟» أو «?»).
7. طول العنوان بين 30 و70 حرفًا: 5 نقاط.

كثافة الكلمة = تكرار الكلمة المطبّعة / عدد كلمات النص.

**النطاق الصحي 55–75 — نقطة جوهرية في طريقة GuinRank:**
الدرجة العالية ليست هدفًا. الحكم «صحي» داخل النطاق 55–75
فقط؛ وأقل من 55 «يحتاج تحسين» مع قائمة العبارات الغائبة
(5 كحد أقصى، الغائب فقط)؛ وأكثر من 75 «مبالغ فيه — خطر
حشو» مع تحذير صريح «لا ترفع الدرجة أكثر — النطاق الصحي
55–75» وبلا أي توصيات إضافة كلمات (قائمة التوصيات عندها
تحوي اقتراحات حذف/تخفيف فقط). كل تقرير يطبع سطر النطاق
الصحي دائمًا.

قواعد الوحدة:
- دوال خالصة على بيانات يزوّدها المشغّل: لا قراءة ملفات
  ولا كتابة ملفات ولا شبكة ولا LLM ولا عشوائية.
- تطبيع عربي للمطابقة (أ/إ/آ←ا، ة←ه، ى←ي، إزالة التشكيل
  والتطويل) مثل ``lib/trend_scout.py``؛ والمطابقة بالاحتواء
  النصي بعد التطبيع (تشمل البادئات المتصلة مثل «والصلاة»)،
  أما عدّ الكلمة للكثافة فيحسب الكلمة الكاملة وحدها.
- مدخل فارغ (عنوان أو نص أو كلمة فارغة) → ``ValueError``
  عربي. العبارات الموصى بها قائمة قواميس {phrase,
  used_by_top: 0–20}؛ و``used_by_top`` يرتّب العبارات
  الغائبة فقط (الأكثر استخدامًا أولًا) ولا يغيّر النقاط.
"""
import json
import re

__all__ = [
    "optimize_content",
    "to_json",
    "format_report",
]

# أوزان الدرجة (المجموع 100).
W_TITLE_KEYWORD = 15
W_DESCRIPTION_KEYWORD = 10
W_DENSITY = 20
W_PHRASE_COVERAGE = 30
W_BODY_LENGTH = 10
W_STRUCTURE = 10
W_TITLE_LENGTH = 5

# **النطاق الصحي 55–75 — نقطة جوهرية في طريقة GuinRank.**
# الدرجة العالية ليست هدفًا: فوق 75 حشو، وتحت 55 نقص.
HEALTHY_LOW = 55
HEALTHY_HIGH = 75

# نطاق كثافة الكلمة المفتاحية الصحي، ونقطة تلاشي التدرّج فوقه.
DENSITY_LOW = 0.005
DENSITY_HIGH = 0.025
DENSITY_ZERO_ABOVE = 0.05

# حدود مكوّني الطول.
BODY_LONG_WORDS = 300
BODY_MEDIUM_WORDS = 150
TITLE_MIN_LEN = 30
TITLE_MAX_LEN = 70
DESCRIPTION_HEAD_CHARS = 120
MAX_MISSING_PHRASES = 5

# الأحكام.
VERDICT_HEALTHY = "صحي"
VERDICT_LOW = "يحتاج تحسين"
VERDICT_HIGH = "مبالغ فيه — خطر حشو"

# التحذير الصريح عند تجاوز النطاق الصحي — يُطبع ولا تُضاف
# معه أي توصية إضافة كلمات أبدًا.
WARNING_OVERSTUFFED = ("لا ترفع الدرجة أكثر — النطاق الصحي "
                       f"{HEALTHY_LOW}–{HEALTHY_HIGH}")
HEALTHY_RANGE_LINE = (f"النطاق الصحي للدرجة: {HEALTHY_LOW}–{HEALTHY_HIGH}"
                      " — فوقه خطر حشو، وتحته يحتاج تحسين.")
MORAL_MARKER = "العبره"

# تطبيع حروف عربية قبل المطابقة (ة↔ه، أ/إ/آ↔ا، ى↔ي) + إزالة
# التشكيل والتطويل — مثل lib/trend_scout.py مع إضافة التطويل.
_DIACRITICS_RE = re.compile(r"[\u064b-\u0652\u0670\u0640]")
_NORMALIZE_TABLE = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي",
})
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _normalize(text):
    """تطبيع نص عربي للمطابقة فقط (لا يغيّر النص المعروض)."""
    text = _DIACRITICS_RE.sub("", text)
    return text.translate(_NORMALIZE_TABLE)


def _tokens(text):
    """كلمات النص المطبّع (بلا علامات ترقيم)."""
    return _TOKEN_RE.findall(_normalize(text))


def _contains(needle_norm, haystack_norm):
    """احتواء نصي بعد التطبيع (يشمل البادئات المتصلة)."""
    return needle_norm != "" and needle_norm in haystack_norm


def _count_keyword(keyword_norm, body_norm, tokens):
    """تكرار الكلمة المفتاحية المطبّعة في النص.

    كلمة واحدة: عدّ الكلمة الكاملة وحدها. عبارة من كلمات:
    عدّ التكرارات غير المتداخلة بحدود الكلمات.
    """
    if " " in keyword_norm:
        pattern = (r"(?<!\w)" + re.escape(keyword_norm) + r"(?!\w)")
        return len(re.findall(pattern, body_norm))
    return tokens.count(keyword_norm)


def _check_text(value, name):
    """تحقّق أن القيمة نص غير فارغ بعد التجريد؛ وإلا ValueError عربي."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"«{name}» فارغ أو غير نص — أعطِ {name} نصًا غير فارغ.")
    return value.strip()


def _clean_phrases(recommended_phrases):
    """تحقّق من العبارات الموصى بها وأعدها منظّفة.

    كل عنصر قاموس {phrase, used_by_top?}؛ و``used_by_top``
    اختياري (افتراضي 0) ويجب أن يكون عددًا صحيحًا 0–20.
    ``None`` تعني بلا عبارات موصى بها.
    """
    if recommended_phrases is None:
        return []
    if not isinstance(recommended_phrases, (list, tuple)):
        raise ValueError("العبارات الموصى بها يجب أن تكون قائمة قواميس.")
    cleaned = []
    for item in recommended_phrases:
        if not isinstance(item, dict):
            raise ValueError("كل عبارة موصى بها يجب أن تكون قاموسًا "
                             "فيه phrase.")
        phrase = item.get("phrase")
        if not isinstance(phrase, str) or not phrase.strip():
            raise ValueError("عبارة موصى بها فارغة أو غير نص — كل عبارة "
                             "تحتاج phrase نصيًا غير فارغ.")
        used_by_top = item.get("used_by_top", 0)
        if (isinstance(used_by_top, bool)
                or not isinstance(used_by_top, int)
                or used_by_top < 0 or used_by_top > 20):
            raise ValueError("«used_by_top» يجب أن يكون عددًا صحيحًا "
                             "بين 0 و20.")
        cleaned.append({"phrase": phrase.strip(),
                        "used_by_top": used_by_top})
    return cleaned


def _density_points(density):
    """نقاط الكثافة (0–20): كاملة داخل 0.5%–2.5%، وجزئية قرب النطاق.

    تدرّج خطي تحت النطاق (صفر عند كثافة صفر إلى 20 عند 0.5%)
    وفوقه (20 عند 2.5% إلى صفر عند 5%)، وصفر خارج ذلك.
    """
    if density <= 0:
        return 0.0
    if DENSITY_LOW <= density <= DENSITY_HIGH:
        return float(W_DENSITY)
    if density < DENSITY_LOW:
        return round(W_DENSITY * density / DENSITY_LOW, 1)
    if density <= DENSITY_ZERO_ABOVE:
        return round(W_DENSITY * (DENSITY_ZERO_ABOVE - density)
                     / (DENSITY_ZERO_ABOVE - DENSITY_HIGH), 1)
    return 0.0


def _length_points(word_count):
    """نقاط طول النص: 10 عند 300+ كلمة، و5 عند 150–299، وصفر دونها."""
    if word_count >= BODY_LONG_WORDS:
        return W_BODY_LENGTH
    if word_count >= BODY_MEDIUM_WORDS:
        return W_BODY_LENGTH // 2
    return 0


def optimize_content(title, description, body, keyword,
                     recommended_phrases=None):
    """قيّم محتوى (عنوان + وصف + نص) ضد كلمة مفتاحية.

    ``title`` و``body`` و``keyword`` نصوص إلزامية غير فارغة؛
    و``description`` نص (أو None بلا وصف)؛ و``recommended_phrases``
    قائمة قواميس {phrase, used_by_top: 0–20} يزوّدها المشغّل
    (عبارات تستخدمها نتائج أول 20 في GuinRank — عندنا: من
    بحث المشغّل)، أو None بلا عبارات.

    ترجع قاموسًا: ``score`` (0–100) و``verdict`` («صحي» داخل
    **النطاق الصحي 55–75**، و«يحتاج تحسين» تحته، و«مبالغ فيه —
    خطر حشو» فوقه) و``warning`` (التحذير الصريح فوق 75 فقط)
    و``components`` (نقاط كل مكوّن وتفاصيله) و``found_phrases``
    و``missing_phrases`` (الغائب فقط، 5 كحد أقصى، الأكثر
    استخدامًا أولًا) و``recommendations`` (فارغة عند «صحي»؛
    وعند >75 اقتراحات حذف/تخفيف فقط — بلا أي إضافة كلمات).

    مدخلات فاسدة (عنوان/نص/كلمة فارغة أو غير نص، وصف غير
    نص، عبارة فاسدة أو used_by_top خارج 0–20) → ``ValueError``
    عربي.
    """
    title = _check_text(title, "العنوان")
    body = _check_text(body, "النص")
    keyword = _check_text(keyword, "الكلمة المفتاحية")
    if description is None:
        description = ""
    if not isinstance(description, str):
        raise ValueError("الوصف يجب أن يكون نصًا — أعطِ وصفًا نصيًا أو اتركه فارغًا.")
    description = description.strip()
    phrases = _clean_phrases(recommended_phrases)

    title_norm = _normalize(title)
    keyword_norm = _normalize(keyword)
    body_norm = _normalize(body)
    tokens = _tokens(body)
    word_count = len(tokens)

    # 1. الكلمة في العنوان (15).
    title_has_keyword = _contains(keyword_norm, title_norm)
    title_points = W_TITLE_KEYWORD if title_has_keyword else 0

    # 2. الكلمة في أول 120 حرفًا من الوصف (10).
    desc_head_norm = _normalize(description[:DESCRIPTION_HEAD_CHARS])
    desc_has_keyword = _contains(keyword_norm, desc_head_norm)
    desc_points = W_DESCRIPTION_KEYWORD if desc_has_keyword else 0

    # 3. كثافة الكلمة في النص (20).
    occurrences = _count_keyword(keyword_norm, body_norm, tokens)
    density = (occurrences / word_count) if word_count else 0.0
    density_points = _density_points(density)

    # 4. تغطية العبارات الموصى بها (30 تناسبيًا).
    found_phrases = []
    missing = []
    for item in phrases:
        phrase_norm = _normalize(item["phrase"])
        if _contains(phrase_norm, body_norm):
            found_phrases.append(item["phrase"])
        else:
            missing.append(item)
    if phrases:
        coverage = len(found_phrases) / len(phrases)
        coverage_points = round(W_PHRASE_COVERAGE * coverage, 1)
        coverage_note = None
    else:
        coverage = None
        coverage_points = 0.0
        coverage_note = "غير مقاس — بلا عبارات موصى بها"
    # الغائب فقط، 5 كحد أقصى، الأكثر استخدامًا أولًا.
    missing.sort(key=lambda item: -item["used_by_top"])
    missing_phrases = [item["phrase"]
                       for item in missing[:MAX_MISSING_PHRASES]]

    # 5. طول النص (10/5/0).
    length_points = _length_points(word_count)

    # 6. البنية: علامة عبرة أو سؤال ختامي (10).
    has_moral = _contains(MORAL_MARKER, body_norm)
    has_closing_question = body.rstrip().endswith(("؟", "?"))
    structure_points = W_STRUCTURE if (has_moral
                                       or has_closing_question) else 0

    # 7. طول العنوان 30–70 حرفًا (5).
    title_len = len(title)
    title_len_points = (W_TITLE_LENGTH
                        if TITLE_MIN_LEN <= title_len <= TITLE_MAX_LEN
                        else 0)

    score = round(title_points + desc_points + density_points
                  + coverage_points + length_points + structure_points
                  + title_len_points, 1)

    if score < HEALTHY_LOW:
        verdict = VERDICT_LOW
        warning = None
    elif score > HEALTHY_HIGH:
        verdict = VERDICT_HIGH
        warning = WARNING_OVERSTUFFED
    else:
        verdict = VERDICT_HEALTHY
        warning = None

    # التوصيات: تحت 55 إضافات وتحسينات؛ وفوق 75 حذف/تخفيف
    # فقط — بلا أي توصية إضافة كلمات؛ وصحي بلا توصيات.
    if verdict == VERDICT_HIGH:
        recommendations = [
            "خفّف تكرار الكلمة المفتاحية في النص بدل زيادتها.",
            "احذف بعض العبارات المكررة من النص بدل إضافة عبارات جديدة.",
        ]
    elif verdict == VERDICT_LOW:
        recommendations = [
            f"أضف العبارة «{phrase}» إلى النص."
            for phrase in missing_phrases
        ]
        if not title_has_keyword:
            recommendations.append("أضف الكلمة المفتاحية إلى العنوان.")
        if not desc_has_keyword:
            recommendations.append("أضف الكلمة المفتاحية إلى أول 120 حرفًا "
                                   "من الوصف.")
        if density_points == 0:
            recommendations.append("اضبط كثافة الكلمة في النص ضمن "
                                   "0.5%–2.5%.")
        elif density_points < W_DENSITY:
            recommendations.append("قرّب كثافة الكلمة في النص من نطاق "
                                   "0.5%–2.5%.")
        if length_points == 0:
            recommendations.append("أطِل النص إلى 150 كلمة على الأقل.")
        if structure_points == 0:
            recommendations.append("أضف علامة «العبرة» أو سؤالًا ختاميًا "
                                   "إلى النص.")
        if title_len_points == 0:
            recommendations.append("اضبط طول العنوان بين 30 و70 حرفًا.")
    else:
        recommendations = []

    return {
        "title": title,
        "keyword": keyword,
        "score": score,
        "verdict": verdict,
        "warning": warning,
        "healthy_range": [HEALTHY_LOW, HEALTHY_HIGH],
        "components": {
            "keyword_in_title": {
                "points": title_points, "max": W_TITLE_KEYWORD,
                "present": title_has_keyword,
            },
            "keyword_in_description_start": {
                "points": desc_points, "max": W_DESCRIPTION_KEYWORD,
                "present": desc_has_keyword,
            },
            "keyword_density": {
                "points": density_points, "max": W_DENSITY,
                "density": round(density, 4),
                "density_pct": round(density * 100, 2),
                "occurrences": occurrences,
                "word_count": word_count,
                "in_range": DENSITY_LOW <= density <= DENSITY_HIGH,
            },
            "phrase_coverage": {
                "points": coverage_points, "max": W_PHRASE_COVERAGE,
                "found": len(found_phrases), "total": len(phrases),
                "coverage": (round(coverage, 4)
                             if coverage is not None else None),
                "note": coverage_note,
            },
            "body_length": {
                "points": length_points, "max": W_BODY_LENGTH,
                "word_count": word_count,
            },
            "structure": {
                "points": structure_points, "max": W_STRUCTURE,
                "has_moral_marker": has_moral,
                "has_closing_question": has_closing_question,
            },
            "title_length": {
                "points": title_len_points, "max": W_TITLE_LENGTH,
                "length": title_len,
            },
        },
        "found_phrases": found_phrases,
        "missing_phrases": missing_phrases,
        "recommendations": recommendations,
    }


def to_json(result):
    """سلسل نتيجة ``optimize_content`` إلى JSON عربي (بلا ASCII هارب)."""
    if not isinstance(result, dict):
        raise ValueError("نتيجة المحسِّن يجب أن تكون قاموسًا من optimize_content.")
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def format_report(result):
    """نسّق نتيجة ``optimize_content`` تقريرًا عربيًا.

    يطبع دائمًا سطر النطاق الصحي 55–75؛ وعند >75 يطبع
    التحذير الصريح «لا ترفع الدرجة أكثر» بلا أي توصية إضافة؛
    وعند <55 يسرد العبارات الغائبة (5 كحد أقصى).
    """
    if not isinstance(result, dict):
        raise ValueError("نتيجة المحسِّن يجب أن تكون قاموسًا من optimize_content.")
    for key in ("score", "verdict", "warning", "healthy_range",
                "components", "missing_phrases", "recommendations"):
        if key not in result:
            raise ValueError(f"نتيجة المحسِّن ناقصة — ينقصها «{key}».")
    components = result["components"]
    for name in ("keyword_in_title", "keyword_in_description_start",
                 "keyword_density", "phrase_coverage", "body_length",
                 "structure", "title_length"):
        if name not in components:
            raise ValueError(f"نتيجة المحسِّن ناقصة — ينقصها مكوّن «{name}».")
    lines = ["مُحسِّن المحتوى (Content Optimizer) — تقرير تحسين",
             "=============================================",
             f"الكلمة المفتاحية: «{result.get('keyword', '')}»",
             f"الدرجة: {result['score']:.1f}/100 — الحكم: {result['verdict']}",
             HEALTHY_RANGE_LINE]
    if result["warning"]:
        lines.append(f"تحذير: {result['warning']}")
    density = components["keyword_density"]
    coverage = components["phrase_coverage"]
    lines.append("")
    lines.append("تفصيل الدرجة:")
    lines.append(f"- الكلمة في العنوان: "
                 f"{components['keyword_in_title']['points']}/"
                 f"{components['keyword_in_title']['max']}")
    lines.append(f"- الكلمة في أول 120 حرفًا من الوصف: "
                 f"{components['keyword_in_description_start']['points']}/"
                 f"{components['keyword_in_description_start']['max']}")
    lines.append(f"- كثافة الكلمة في النص: {density['points']}/"
                 f"{density['max']} (الكثافة {density['density_pct']}% — "
                 f"{density['occurrences']} تكرار / {density['word_count']} "
                 f"كلمة)")
    coverage_text = ("غير مقاس — بلا عبارات موصى بها"
                     if coverage["total"] == 0
                     else f"{coverage['found']} من {coverage['total']}")
    lines.append(f"- تغطية العبارات الموصى بها: {coverage['points']}/"
                 f"{coverage['max']} ({coverage_text})")
    lines.append(f"- طول النص: {components['body_length']['points']}/"
                 f"{components['body_length']['max']} "
                 f"({components['body_length']['word_count']} كلمة)")
    lines.append(f"- البنية (عبرة أو سؤال ختامي): "
                 f"{components['structure']['points']}/"
                 f"{components['structure']['max']}")
    lines.append(f"- طول العنوان: {components['title_length']['points']}/"
                 f"{components['title_length']['max']} "
                 f"({components['title_length']['length']} حرفًا)")
    if result["verdict"] == VERDICT_LOW and result["missing_phrases"]:
        lines.append("")
        lines.append("العبارات الموصى بها الغائبة "
                     f"({len(result['missing_phrases'])} — 5 كحد أقصى):")
        for phrase in result["missing_phrases"]:
            lines.append(f"- «{phrase}»")
    if result["recommendations"]:
        lines.append("")
        lines.append("التوصيات:")
        for recommendation in result["recommendations"]:
            lines.append(f"- {recommendation}")
    elif result["verdict"] == VERDICT_HEALTHY:
        lines.append("")
        lines.append("لا توصيات — المحتوى ضمن النطاق الصحي.")
    lines.append("")
    lines.append("تذكير: الدرجة العالية ليست هدفًا — "
                 f"النطاق الصحي {HEALTHY_LOW}–{HEALTHY_HIGH} فقط.")
    return "\n".join(lines)
