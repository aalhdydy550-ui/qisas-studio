#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""قياس السلطة الموضوعية لمكتبة القصص — جولة v0.1.61 (W7).

الفكرة (من طريقة «Topical Authority» في GuinRank فقط، بلا نسخ كود):
المشغّل يزوّد قائمة قصص {title, topic?}، والوحدة تقيس عمق
تغطية المكتبة لمواضيع القصص وتكشف الفجوات — بلا شبكة وبلا
LLM وبلا عشوائية. دوال خالصة على بيانات يزوّدها المشغّل.

الخريطة الافتراضية لمجال القصص (12 موضوعًا، بالترتيب):
1. توبة — توبه، تايب، تائب، استغفار، رجع الي الله
2. أمانة — امانه، امين
3. صدقة — صدقه، تصدق، متصدق
4. بر الوالدين — بر الوالدين، الوالدين، والديه، والدته، والده،
   بر امه، بر ابيه
5. صبر — صبر، صابر، صبرت
6. ظلم وعوض — ظلم، مظلوم، ظالم، عوض
7. كرم — كرم، كريم، جود، جواد
8. صلاة — صلاه، يصلي، صلي، مسجد، الفجر
9. غدر وخيانة — غدر، غدار، خيانه، خائن، خاين
10. ندم — ندم، ندمان
11. رحمة — رحمه، رحيم، تراحم
12. عدل — عدل، عادل، انصف، انصاف

(الكلمات أعلاه بصيغتها المطبّعة: أ/إ/آ←ا، ة←ه، ى←ي، بلا
تشكيل وبلا تطويل — وهي الصيغة التي تُطابَق بها العناوين.)

قواعد الوحدة:
- التصنيف: إن أُعطي topic يُستخدم كما هو بعد التطبيع؛ فإن
  ظهر اسم موضوع من الخريطة داخل الموضوع المعطى (مثل
  «الصدقة» ← صدقة) عُدّ تحت ذلك الموضوع، وإن لم يطابق أي
  موضوع من الخريطة بقي موضوعًا مستقلًا باسمه ولا يدخل
  حساب التغطية. وإن غاب topic صُنّف العنوان بمطابقة
  كلمات الخريطة — أول مطابقة تفوز حسب ترتيب الخريطة
  أعلاه. وعنوان بلا أي مطابقة → موضوع «أخرى».
- «أخرى» لا تدخل حساب التغطية إطلاقًا، بل تُذكر منفصلة
  بعددها وعناوينها.
- درجة العمق لكل موضوع (من عدد قصصه): 0→0، 1→30، 2→55،
  3→75، 4–5→90، 6 فأكثر→100.
- التغطية = المواضيع ذات قصة واحدة على الأقل / إجمالي
  مواضيع الخريطة. السلطة الكلية 0–100 = 0.5 × متوسط
  العمق + 0.5 × التغطية × 100.
- الأحكام: قوية 70 فأكثر، متوسطة 40–69، ضعيفة أقل من 40.
- الفجوات: المواضيع ذات 0–1 قصة مرتبة كفرص محتوى (الصفر
  أولًا ثم الواحد، وبترتيب الخريطة داخل كل مجموعة) مع
  اقتراح «قصة جديدة في موضوع X».
- مكتبة فارغة → ``ValueError`` عربي. كل مدخل فاسد
  (قصة بلا عنوان، topic غير نص، خريطة مخصصة فارغة أو
  فاسدة) → ``ValueError`` عربي.
"""
import json
import re

__all__ = [
    "DEFAULT_TOPIC_MAP",
    "TOPIC_OTHER",
    "VERDICT_STRONG",
    "VERDICT_MEDIUM",
    "VERDICT_WEAK",
    "classify_title",
    "depth_score",
    "topical_authority",
    "format_report",
    "to_json",
    "load_library_json",
]

# موضوع العناوين بلا أي مطابقة — يُذكر منفصلًا ولا يدخل التغطية.
TOPIC_OTHER = "أخرى"

# الأحكام (قيم الإخراج — عربية).
VERDICT_STRONG = "قوية"
VERDICT_MEDIUM = "متوسطة"
VERDICT_WEAK = "ضعيفة"

# حدّا الحكمين.
STRONG_MIN = 70.0
MEDIUM_MIN = 40.0

# أوزان السلطة الكلية (المجموع 100).
DEPTH_WEIGHT = 0.5
COVERAGE_WEIGHT = 0.5

# الخريطة الافتراضية لمجال القصص — الترتيب هو ترتيب أول
# مطابقة تفوز في التصنيف التلقائي.
DEFAULT_TOPIC_MAP = {
    "توبة": ("توبه", "تايب", "تائب", "استغفار", "رجع الي الله"),
    "أمانة": ("امانه", "امين"),
    "صدقة": ("صدقه", "تصدق", "متصدق"),
    "بر الوالدين": ("بر الوالدين", "الوالدين", "والديه", "والدته",
                    "والده", "بر امه", "بر ابيه"),
    "صبر": ("صبر", "صابر", "صبرت"),
    "ظلم وعوض": ("ظلم", "مظلوم", "ظالم", "عوض"),
    "كرم": ("كرم", "كريم", "جود", "جواد"),
    "صلاة": ("صلاه", "يصلي", "صلي", "مسجد", "الفجر"),
    "غدر وخيانة": ("غدر", "غدار", "خيانه", "خائن", "خاين"),
    "ندم": ("ندم", "ندمان"),
    "رحمة": ("رحمه", "رحيم", "تراحم"),
    "عدل": ("عدل", "عادل", "انصف", "انصاف"),
}

# سطر يُطبع في كل تقرير.
DISCLAIMER = "تصنيف بالكلمات فقط — ليس ادعاءً بموضوع القصة الحقيقي."

# تطبيع حروف عربية قبل المطابقة (ة↔ه، أ/إ/آ↔ا، ى↔ي) + إزالة
# التشكيل والتطويل — مثل lib/trend_scout.py مع إضافة التطويل.
_DIACRITICS_RE = re.compile(r"[\u064b-\u0652\u0670]")
_TATWEEL_RE = re.compile(r"\u0640")
_NORMALIZE_TABLE = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي",
})


def _normalize(text):
    """تطبيع نص عربي للمطابقة فقط (لا يغيّر النص المعروض)."""
    text = _DIACRITICS_RE.sub("", text)
    text = _TATWEEL_RE.sub("", text)
    return text.translate(_NORMALIZE_TABLE)


def _normalized_map(topic_map):
    """تحقّق من خريطة مواضيع وأعدها: (الاسم، كلمات مطبّعة).

    يرفع ``ValueError`` عربيًا إن كانت الخريطة ليست قاموسًا
    أو فارغة أو فيها موضوع بلا اسم أو بلا كلمات أو كلمة
    فارغة أو اسما موضوعين يتطابقان بعد التطبيع.
    """
    if not isinstance(topic_map, dict):
        raise ValueError("خريطة المواضيع (topic_map) يجب أن تكون قاموسًا "
                         "موضوعًا ← كلمات مطابقة.")
    if len(topic_map) == 0:
        raise ValueError("خريطة المواضيع فارغة — أعطِ موضوعًا واحدًا "
                         "على الأقل أو اتركها غائبة للخريطة الافتراضية.")
    seen = {}
    normalized = []
    for topic, words in topic_map.items():
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("اسم موضوع في الخريطة فارغ أو غير نص — "
                             "كل موضوع يحتاج اسمًا نصيًا غير فارغ.")
        if not isinstance(words, (list, tuple)) or len(words) == 0:
            raise ValueError(f"موضوع «{topic.strip()}» بلا كلمات مطابقة — "
                             "أعطِ كلمة واحدة على الأقل.")
        clean_words = []
        for word in words:
            if not isinstance(word, str) or not word.strip():
                raise ValueError(f"كلمة مطابقة فارغة أو غير نص في موضوع "
                                 f"«{topic.strip()}».")
            clean_words.append(_normalize(word.strip()))
        key = _normalize(topic.strip())
        if key in seen:
            raise ValueError(f"موضوعان في الخريطة يتطابقان بعد التطبيع: "
                             f"«{seen[key]}» و«{topic.strip()}».")
        if key == _normalize(TOPIC_OTHER):
            raise ValueError("لا تسمِّ موضوعًا في الخريطة «أخرى» — "
                             "«أخرى» محجوزة للعناوين بلا أي مطابقة.")
        seen[key] = topic.strip()
        normalized.append((topic.strip(), clean_words))
    return normalized


def _resolve_topic(topic, normalized):
    """طابق موضوعًا معطى بموضوع من الخريطة أو أبقه مستقلًا.

    يرجع (اسم الموضوع المعروض، هل هو من الخريطة). المطابقة
    عندما يظهر اسم موضوع الخريطة المطبّع داخل الموضوع
    المعطى المطبّع (فتطابق «الصدقة» موضوع «صدقة»).
    """
    given = _normalize(topic.strip())
    for name, _words in normalized:
        if _normalize(name) in given:
            return name, True
    return topic.strip(), False


def classify_title(title, topic_map=None):
    """صنّف عنوان قصة في موضوع من الخريطة بالكلمات فقط.

    أول مطابقة تفوز حسب ترتيب الخريطة؛ وعنوان بلا أي
    مطابقة → «أخرى». يرفع ``ValueError`` عربيًا إن كان
    العنوان فارغًا أو غير نص أو كانت الخريطة فاسدة.
    """
    if not isinstance(title, str) or not title.strip():
        raise ValueError("عنوان القصة فارغ أو غير نص — أعطِ عنوانًا نصيًا.")
    normalized = _normalized_map(
        DEFAULT_TOPIC_MAP if topic_map is None else topic_map)
    text = _normalize(title.strip())
    for name, words in normalized:
        if any(word in text for word in words):
            return name
    return TOPIC_OTHER


def depth_score(count):
    """درجة عمق موضوع من عدد قصصه: 0→0، 1→30، 2→55، 3→75،
    4–5→90، 6 فأكثر→100.

    يرفع ``ValueError`` عربيًا إن لم يكن العدد صحيحًا غير سالب.
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("عدد القصص يجب أن يكون عددًا صحيحًا غير سالب.")
    if count == 0:
        return 0
    if count == 1:
        return 30
    if count == 2:
        return 55
    if count == 3:
        return 75
    if count <= 5:
        return 90
    return 100


def _clean_story(story):
    """تحقّق من قصة واحدة وأعدها منظّفة؛ وإلا ``ValueError`` عربي."""
    if not isinstance(story, dict):
        raise ValueError("كل قصة يجب أن تكون قاموسًا فيه title.")
    title = story.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("قصة بلا عنوان — كل قصة تحتاج title نصيًا غير فارغ.")
    topic = story.get("topic")
    if topic is None:
        topic = ""
    if not isinstance(topic, str):
        raise ValueError("موضوع القصة (topic) يجب أن يكون نصًا.")
    return {"title": title.strip(), "topic": topic.strip() or None}


def load_library_json(text):
    """اقرأ مدخل JSON نصيًا إلى قائمة قصص منظّفة.

    يرفع ``ValueError`` عربيًا عند JSON تالف أو مدخل ليس
    قائمة أو مكتبة فارغة أو قصة فاسدة — بلا أي كتابة.
    """
    if not isinstance(text, str):
        raise ValueError("مدخل JSON يجب أن يكون نصًا.")
    try:
        data = json.loads(text)
    except ValueError:
        raise ValueError("مدخل JSON تالف — أعطِ قائمة قصص JSON صالحة.")
    if not isinstance(data, list):
        raise ValueError("مدخل المكتبة يجب أن يكون قائمة قصص.")
    if len(data) == 0:
        raise ValueError("مكتبة القصص فارغة — أعطِ قصة واحدة على الأقل.")
    return [_clean_story(story) for story in data]


def topical_authority(library, topic_map=None):
    """قس سلطة مكتبة قصص الموضوعية على خريطة مواضيع.

    ``library``: قائمة قواميس {title, topic?} يزوّدها
    المشغّل (أو نص JSON يُقرأ بـ ``load_library_json``).
    ``topic_map``: قاموس اختياري موضوع ← كلمات مطابقة؛
    وإن غاب استُخدمت الخريطة الافتراضية الموثّقة في
    مقدّمة الوحدة (12 موضوعًا لمجال القصص).

    ترجع قاموسًا: ``total`` (عدد القصص)، و``topics`` (كل
    موضوع من الخريطة بالترتيب: الاسم والعدد ودرجة العمق)،
    و``other_count`` و``other_titles`` («أخرى» منفصلة عن
    التغطية)، و``extra_topics`` (مواضيع صريحة خارج
    الخريطة بعددها وعمقها — منفصلة عن التغطية أيضًا)،
    و``covered_topics`` و``total_topics`` و``coverage``
    (نسبة 0–1) و``coverage_pct`` و``average_depth`` و
    ``authority`` (0–100) و``verdict`` (قوية/متوسطة/
    ضعيفة)، و``gaps`` (المواضيع ذات 0–1 قصة: الصفر أولًا
    ثم الواحد، مع اقتراح «قصة جديدة في موضوع X»)،
    و``stories`` (كل قصة: العنوان والموضوع المصنّف).

    مكتبة فارغة أو مدخل فاسد → ``ValueError`` عربي.
    """
    if isinstance(library, str):
        library = load_library_json(library)
    if not isinstance(library, (list, tuple)):
        raise ValueError("مكتبة القصص يجب أن تكون قائمة قصص.")
    if len(library) == 0:
        raise ValueError("مكتبة القصص فارغة — أعطِ قصة واحدة على الأقل.")
    cleaned = [_clean_story(story) for story in library]
    normalized = _normalized_map(
        DEFAULT_TOPIC_MAP if topic_map is None else topic_map)

    counts = {name: 0 for name, _words in normalized}
    extra_counts = {}
    other_titles = []
    stories = []
    for story in cleaned:
        if story["topic"] is not None:
            name, in_map = _resolve_topic(story["topic"], normalized)
            if in_map:
                counts[name] += 1
            elif _normalize(name) == _normalize(TOPIC_OTHER):
                other_titles.append(story["title"])
            else:
                extra_counts[name] = extra_counts.get(name, 0) + 1
        else:
            name = classify_title(story["title"], topic_map)
            if name == TOPIC_OTHER:
                other_titles.append(story["title"])
            else:
                counts[name] += 1
        stories.append({"title": story["title"], "topic": name})

    topics = [{"topic": name, "count": counts[name],
               "depth": depth_score(counts[name])}
              for name, _words in normalized]
    extra_topics = [{"topic": name, "count": count,
                     "depth": depth_score(count)}
                    for name, count in extra_counts.items()]
    covered = sum(1 for entry in topics if entry["count"] >= 1)
    total_topics = len(topics)
    coverage = covered / total_topics
    average_depth = sum(entry["depth"] for entry in topics) / total_topics
    authority = round(DEPTH_WEIGHT * average_depth
                      + COVERAGE_WEIGHT * coverage * 100, 1)
    if authority >= STRONG_MIN:
        verdict = VERDICT_STRONG
    elif authority >= MEDIUM_MIN:
        verdict = VERDICT_MEDIUM
    else:
        verdict = VERDICT_WEAK

    gaps = [{"topic": entry["topic"], "count": entry["count"],
             "suggestion": f"قصة جديدة في موضوع {entry['topic']}"}
            for entry in topics if entry["count"] <= 1]
    # الصفر أولًا ثم الواحد — وبترتيب الخريطة داخل كل مجموعة
    # (الترتيب مستقر لأن topics أصلًا بترتيب الخريطة).
    gaps.sort(key=lambda entry: entry["count"])

    return {
        "total": len(cleaned),
        "topics": topics,
        "other_count": len(other_titles),
        "other_titles": other_titles,
        "extra_topics": extra_topics,
        "covered_topics": covered,
        "total_topics": total_topics,
        "coverage": round(coverage, 4),
        "coverage_pct": round(coverage * 100, 1),
        "average_depth": round(average_depth, 1),
        "authority": authority,
        "verdict": verdict,
        "gaps": gaps,
        "stories": stories,
    }


def to_json(result):
    """سلسل نتيجة ``topical_authority`` إلى JSON عربي (بلا ASCII هارب)."""
    if not isinstance(result, dict):
        raise ValueError("نتيجة السلطة الموضوعية يجب أن تكون قاموسًا "
                         "من topical_authority.")
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def format_report(result):
    """نسّق نتيجة ``topical_authority`` تقريرًا عربيًا.

    يحوي دائمًا السلطة والحكم والتغطية وجدول المواضيع
    والفجوات باقتراحاتها و«أخرى» منفصلة، وسطر «تصنيف
    بالكلمات فقط — ليس ادعاءً بموضوع القصة الحقيقي».
    """
    if not isinstance(result, dict):
        raise ValueError("نتيجة السلطة الموضوعية يجب أن تكون قاموسًا "
                         "من topical_authority.")
    for key in ("total", "topics", "other_count", "other_titles",
                "extra_topics", "covered_topics", "total_topics",
                "coverage_pct", "average_depth", "authority",
                "verdict", "gaps", "stories"):
        if key not in result:
            raise ValueError(f"نتيجة السلطة الموضوعية ناقصة — ينقصها «{key}».")
    lines = ["السلطة الموضوعية لمكتبة القصص",
             "==========================="]
    lines.append(f"عدد القصص: {result['total']}")
    lines.append(f"السلطة الكلية: {result['authority']:.1f}/100 "
                 f"— الحكم: {result['verdict']}")
    lines.append(f"التغطية: {result['covered_topics']}/"
                 f"{result['total_topics']} موضوعًا "
                 f"({result['coverage_pct']:.1f}%)")
    lines.append(f"متوسط العمق: {result['average_depth']:.1f}/100")
    lines.append("")
    lines.append("المواضيع:")
    for entry in result["topics"]:
        lines.append(f"- {entry['topic']}: {entry['count']} قصص — "
                     f"العمق {entry['depth']}/100")
    if result["extra_topics"]:
        lines.append("")
        lines.append("مواضيع صريحة خارج الخريطة "
                     "(لا تدخل التغطية):")
        for entry in result["extra_topics"]:
            lines.append(f"- {entry['topic']}: {entry['count']} قصص — "
                         f"العمق {entry['depth']}/100")
    lines.append("")
    lines.append(f"«أخرى» (بلا أي مطابقة — خارج التغطية): "
                 f"{result['other_count']} قصص")
    for title in result["other_titles"]:
        lines.append(f"- «{title}»")
    lines.append("")
    lines.append(f"فجوات — فرص محتوى ({len(result['gaps'])}):")
    if not result["gaps"]:
        lines.append("لا فجوات — كل المواضيع فيها قصتان على الأقل.")
    for gap in result["gaps"]:
        lines.append(f"- {gap['topic']} ({gap['count']} قصص): "
                     f"{gap['suggestion']}")
    lines.append("")
    lines.append(DISCLAIMER)
    return "\n".join(lines)
