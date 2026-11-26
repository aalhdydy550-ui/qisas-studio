#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""كلمات اليوم الطازجة — Today's Fresh Keywords في GuinRank — جولة v0.1.61 (W6).

الفكرة (من طريقة «Today's Fresh Keywords» في GuinRank فقط، بلا
نسخ كود — GuinRank أداة تجارية مغلقة بلا مستودع وبلا API):
المشغّل يزوّد قائمة كلمات مفتاحية حديثة (من بحث الترند أو
vidIQ) مع نموها وحجمها وتاريخ قياسها، والوحدة ترتّبها
بحداثتها ونموها — بلا شبكة وبلا LLM وبلا عشوائية.

قواعد الوحدة:
- المدخل قائمة قواميس {keyword, growth_pct?, volume?,
  date: "YYYY-MM-DD", source?} — يزوّدها المشغّل جاهزة.
  قراءة فقط: بلا شبكة وبلا جلب.
- الحداثة: مدخل أقدم من ``days`` قبل ``today`` → مستبعد
  ويُدرج في ``stale`` مع سببه (عمره بالأيام). مدخل بتاريخ
  اليوم أو أحدث منه يُعامل كعمر صفر (طازج). تاريخ فاسد
  (صيغة غير «YYYY-MM-DD» أو يوم مستحيل) → ``ValueError``
  عربي. ``today`` تاريخ «YYYY-MM-DD» أو كائن ``date`` —
  افتراضيًا ``date.today()``.
- النمو المجهول (``growth_pct`` غائب) → «غير مقاس» ويُرتَّب
  بعد المقاس عند تساوي الدرجة (لا يُخترع نمو): يساهم
  بصفر في الدرجة ويُعلَّم في السبب.
- الدرجة 0–100 من إشارتين مقاستين فقط:
  1. النمو حتى 70 نقطة: ``70 × min(max(growth_pct, 0) / 200, 1)``
     — مقياسًا على 200% (نمو 200% فأكثر يأخذ 70 كاملة،
     والنمو السالب يُعامل كصفر).
  2. إشارة الحجم حتى 30 نقطة بمقياس لوغاريتمي:
     ``30 × min(log10(volume + 1) / log10(1_000_001), 1)``
     — حجم مليون فأكثر يأخذ 30 كاملة، والحجم المجهول
     صفر ومُعلَّم «غير مقاس».
- «رائج اليوم»: كل كلمة طازجة بنمو ``>= 50%`` تُعلَّم
  ``trending_today=True`` (وسم «رائج اليوم») — قياس لا
  اقتراح.
- الترتيب حتمي: الدرجة تنازليًا، ثم المقاس قبل غير المقاس،
  ثم النمو تنازليًا، ثم الكلمة أبجديًا.
- الرعب مستبعد من خطنا — لا يُقترح أبدًا: أي كلمة فيها
  لفظ رعب/غموض (رعب، مرعب، غامض، غموض، جن، عفريت،
  مقبرة، شبح، مسكون...) تُوسم «مستبعد» وتُدرج في
  ``excluded`` ولا تدخل ``suggestions``.
- كلمة فارغة أو قائمة فارغة → ``ValueError`` عربي.

مرجع (بيانات الاستوديو المقاسة — أمثلة لا بيانات حية):
«قصص واقعية» نمو +92.6%، و«قصص غموض» نمو +84.8% —
و«قصص غموض» نفسها مستبعدة من الاقتراحات رغم نموها
(الغموض/الرعب خارج الخط بانتظار قرار المستخدم).
"""
import json
import math
import re
from datetime import date, datetime

__all__ = [
    "is_horror_keyword",
    "fresh_keywords",
    "format_report",
    "to_json",
    "load_trends_json",
]

# حالات الكلمة.
STATUS_CANDIDATE = "مرشح"
STATUS_EXCLUDED = "مستبعد"

# وسم النمو العالي.
TRENDING_LABEL = "رائج اليوم"
TRENDING_THRESHOLD = 50.0

# مراجع الدرجة الموثقة في مقدّمة الوحدة.
GROWTH_CAP_PCT = 200.0
GROWTH_WEIGHT = 70.0
VOLUME_WEIGHT = 30.0
VOLUME_REF = 1_000_000

# أمثلة مقاسة من بيانات الاستوديو — لا بيانات حية.
REFERENCE_EXAMPLES = [
    {"keyword": "قصص واقعية", "growth_pct": 92.6},
    {"keyword": "قصص غموض", "growth_pct": 84.8,
     "status": STATUS_EXCLUDED},
]

# تطبيع حروف عربية قبل المطابقة (ة↔ه، أ/إ/آ↔ا، ى↔ي) + إزالة التشكيل.
_DIACRITICS_RE = re.compile(r"[\u064b-\u0652\u0670]")
_NORMALIZE_TABLE = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي",
})

# ألفاظ الرعب/الغموض (بعد التطبيع). «جن» مطابقة تامة فقط
# حتى لا يلتقط «جنة» أو «جنون».
_HORROR_WORDS = (
    "رعب", "مرعب", "غامض", "غموض", "عفريت", "مقبره",
    "شبح", "اشباح", "مسكون", "سحر", "لعنه",
)
_HORROR_EXACT_ONLY = ("جن",)


def _normalize(text):
    """تطبيع نص عربي للمطابقة فقط (لا يغيّر النص المعروض)."""
    text = _DIACRITICS_RE.sub("", text)
    return text.translate(_NORMALIZE_TABLE)


def _tokens(text):
    """قسّم نصًا مطبّعًا إلى كلمات بلا بادئة «ال» وبلا ترقيم."""
    words = []
    for raw in re.split(r"\s+", text):
        word = raw.strip("،؛:.!?\"'«»()[]-")
        if word.startswith("ال") and len(word) > 2:
            word = word[2:]
        if word:
            words.append(word)
    return words


def is_horror_keyword(keyword):
    """هل الكلمة رعب/غموض (مستبعدة من الخط)؟ مطابقة كلمات فقط.

    يرفع ``ValueError`` عربيًا إن كانت الكلمة فارغة أو غير نص.
    """
    if not isinstance(keyword, str) or not keyword.strip():
        raise ValueError("الكلمة المفتاحية فارغة أو غير نص — أعطِ كلمة نصية.")
    tokens = _tokens(_normalize(keyword.strip()))
    for token in tokens:
        if token in _HORROR_EXACT_ONLY:
            return True
        if any(token == word or token.startswith(word)
               for word in _HORROR_WORDS):
            return True
    return False


def _parse_date(value, name):
    """فسّر تاريخ «YYYY-MM-DD» أو كائن date — وإلا ValueError عربي."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError(f"تاريخ {name} يجب أن يكون «YYYY-MM-DD» أو تاريخًا.")
    text = value.strip()
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(
            f"تاريخ {name} فاسد: «{value}» — أعطِ تاريخًا بصيغة «YYYY-MM-DD».")
    if parsed.isoformat() != text:
        raise ValueError(
            f"تاريخ {name} فاسد: «{value}» — أعطِ تاريخًا بصيغة «YYYY-MM-DD».")
    return parsed


def _check_number(value, name, allow_negative=False):
    """تحقّق أن القيمة عدد حقيقي منتهٍ (بلا bool) أو None."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"«{name}» يجب أن تكون رقمًا — وصلت قيمة غير رقمية.")
    if not math.isfinite(value):
        raise ValueError(f"«{name}» يجب أن تكون رقمًا منتهيًا.")
    if not allow_negative and value < 0:
        raise ValueError(f"«{name}» سالبة — العدّادات لا تكون سالبة.")
    return value


def _check_positive_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"«{name}» يجب أن تكون عددًا صحيحًا موجبًا.")
    return value


def _clean_trend(trend):
    """تحقّق من مدخل ترند واحد وأعده منظّفًا؛ وإلا ValueError عربي."""
    if not isinstance(trend, dict):
        raise ValueError("كل مدخل ترند يجب أن يكون قاموسًا فيه keyword وdate.")
    keyword = trend.get("keyword")
    if not isinstance(keyword, str) or not keyword.strip():
        raise ValueError("مدخل بلا كلمة مفتاحية — كل مدخل يحتاج keyword نصيًا غير فارغ.")
    if "date" not in trend or trend.get("date") is None:
        raise ValueError(f"مدخل «{keyword.strip()}» بلا تاريخ — كل مدخل يحتاج date بصيغة «YYYY-MM-DD».")
    entry_date = _parse_date(trend.get("date"), f"مدخل «{keyword.strip()}»")
    source = trend.get("source", "")
    if source is None:
        source = ""
    if not isinstance(source, str):
        raise ValueError("مصدر المدخل (source) يجب أن يكون نصًا.")
    return {
        "keyword": keyword.strip(),
        "growth_pct": _check_number(trend.get("growth_pct"), "النمو",
                                    allow_negative=True),
        "volume": _check_number(trend.get("volume"), "الحجم"),
        "date": entry_date,
        "source": source.strip(),
    }


def _score(growth_pct, volume):
    """درجة 0–100: النمو حتى 70 (مقياسًا على 200%) + الحجم حتى 30 (لوغاريتمي)."""
    total = 0.0
    if growth_pct is not None:
        total += GROWTH_WEIGHT * min(max(growth_pct, 0.0) / GROWTH_CAP_PCT, 1.0)
    if volume is not None:
        total += VOLUME_WEIGHT * min(
            math.log10(volume + 1) / math.log10(VOLUME_REF + 1), 1.0)
    return round(total, 1)


def _growth_text(growth_pct):
    """نسّق النمو كـ «+92.6%» — أو «غير مقاس» إن كان مجهولًا."""
    if growth_pct is None:
        return "غير مقاس"
    sign = "+" if growth_pct >= 0 else ""
    return f"{sign}{growth_pct:.1f}%"


def _reason(growth_pct, volume):
    """سبب عربي بالقياسات — «غير مقاس» لأي إشارة بلا مصدر."""
    growth_text = _growth_text(growth_pct)
    if volume is None:
        volume_text = "غير مقاس"
    elif volume == int(volume):
        volume_text = f"{int(volume):,}"
    else:
        volume_text = f"{volume:,}"
    return f"نمو {growth_text}؛ حجم {volume_text}"


def load_trends_json(text):
    """اقرأ مدخل JSON نصيًا إلى قائمة مدخلات ترند منظّفة.

    يرفع ``ValueError`` عربيًا عند JSON تالف أو مدخل ليس
    قائمة أو قائمة فارغة أو مدخل فاسد — بلا أي كتابة.
    """
    if not isinstance(text, str):
        raise ValueError("مدخل JSON يجب أن يكون نصًا.")
    try:
        data = json.loads(text)
    except ValueError:
        raise ValueError("مدخل JSON تالف — أعطِ قائمة مدخلات ترند JSON صالحة.")
    if not isinstance(data, list):
        raise ValueError("مدخل الترند يجب أن يكون قائمة مدخلات.")
    if len(data) == 0:
        raise ValueError("قائمة الترند فارغة — أعطِ مدخلًا واحدًا على الأقل.")
    return [_clean_trend(trend) for trend in data]


def fresh_keywords(trends, days=7, today=None):
    """رتّب كلمات مفتاحية طازجة بنموها وحجمها (طريقة Today's Fresh Keywords).

    ``trends``: قائمة قواميس {keyword, growth_pct?, volume?,
    date: "YYYY-MM-DD", source?} أو نص JSON لها. ``days``:
    نافذة الحداثة بالأيام. ``today``: تاريخ «YYYY-MM-DD»
    أو كائن ``date`` — افتراضيًا ``date.today()``.

    ترجع قاموسًا: ``keywords`` (كل الطازجة مرتبة: الكلمة
    والنمو ونصه والحجم والدرجة ووسم «رائج اليوم» والحالة
    والتاريخ والمصدر والسبب)، و``suggestions`` (الطازجة غير
    المستبعدة بنفس الترتيب)، و``stale`` (القديمة مع سبب
    الاستبعاد وعمرها بالأيام)، و``excluded`` (كلمات الرعب/
    الغموض المستبعدة)، و``total`` و``fresh_count`` و``today``
    و``days`` و``reference`` (المراجع المقاسة).

    مدخلات فاسدة (قائمة فارغة، كلمة فارغة، تاريخ فاسد،
    رقم سالب/غير رقمي) → ``ValueError`` عربي.
    """
    days = _check_positive_int(days, "days")
    if today is None:
        today_date = date.today()
    else:
        today_date = _parse_date(today, "today")
    if isinstance(trends, str):
        trends = load_trends_json(trends)
    if not isinstance(trends, (list, tuple)):
        raise ValueError("مدخل الترند يجب أن يكون قائمة مدخلات.")
    if len(trends) == 0:
        raise ValueError("قائمة الترند فارغة — أعطِ مدخلًا واحدًا على الأقل.")
    cleaned = [_clean_trend(trend) for trend in trends]

    keywords = []
    stale = []
    for entry in cleaned:
        age = (today_date - entry["date"]).days
        if age < 0:
            age = 0
        if age > days:
            stale.append({
                "keyword": entry["keyword"],
                "date": entry["date"].isoformat(),
                "age_days": age,
                "growth_pct": entry["growth_pct"],
                "volume": entry["volume"],
                "source": entry["source"],
                "reason": (f"أقدم من {days} أيام — تاريخه "
                           f"{entry['date'].isoformat()} (عمره {age} أيام)"),
            })
            continue
        horror = is_horror_keyword(entry["keyword"])
        status = STATUS_EXCLUDED if horror else STATUS_CANDIDATE
        growth_pct = entry["growth_pct"]
        trending = growth_pct is not None and growth_pct >= TRENDING_THRESHOLD
        keywords.append({
            "keyword": entry["keyword"],
            "growth_pct": growth_pct,
            "growth_text": _growth_text(growth_pct),
            "volume": entry["volume"],
            "score": _score(growth_pct, entry["volume"]),
            "trending_today": trending,
            "label": TRENDING_LABEL if trending else "",
            "status": status,
            "date": entry["date"].isoformat(),
            "age_days": age,
            "source": entry["source"],
            "reason": _reason(growth_pct, entry["volume"]),
        })
    # الدرجة تنازليًا، ثم المقاس قبل غير المقاس، ثم النمو
    # تنازليًا، ثم الكلمة أبجديًا — حتمي بلا عشوائية.
    keywords.sort(key=lambda e: (
        -e["score"],
        e["growth_pct"] is None,
        -(e["growth_pct"] if e["growth_pct"] is not None else 0.0),
        e["keyword"],
    ))

    return {
        "keywords": keywords,
        "suggestions": [e for e in keywords
                        if e["status"] != STATUS_EXCLUDED],
        "stale": stale,
        "excluded": [e["keyword"] for e in keywords
                     if e["status"] == STATUS_EXCLUDED],
        "total": len(keywords),
        "fresh_count": len(keywords),
        "today": today_date.isoformat(),
        "days": days,
        "reference": {
            "examples": REFERENCE_EXAMPLES,
            "growth_cap_pct": GROWTH_CAP_PCT,
            "volume_ref": VOLUME_REF,
            "source": "بيانات الاستوديو المقاسة — أمثلة لا بيانات حية",
        },
    }


def to_json(result):
    """سلسل نتيجة ``fresh_keywords`` إلى JSON عربي (بلا ASCII هارب)."""
    if not isinstance(result, dict):
        raise ValueError("نتيجة الكلمات الطازجة يجب أن تكون قاموسًا من fresh_keywords.")
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def format_report(result):
    """نسّق نتيجة ``fresh_keywords`` تقريرًا عربيًا.

    يحوي دائمًا سطر «النمو المجهول يظهر «غير مقاس» — لا
    أرقام مخترعة»، وتنبيهًا أن الرعب/الغموض مستبعد ولا
    يُقترح أبدًا.
    """
    if not isinstance(result, dict):
        raise ValueError("نتيجة الكلمات الطازجة يجب أن تكون قاموسًا من fresh_keywords.")
    for key in ("keywords", "suggestions", "stale", "excluded",
                "total", "today", "days"):
        if key not in result:
            raise ValueError(f"نتيجة الكلمات الطازجة ناقصة — ينقصها «{key}».")
    keywords = result["keywords"]
    suggestions = result["suggestions"]
    stale = result["stale"]
    lines = ["كلمات اليوم الطازجة — Today's Fresh Keywords",
             "==========================================",
             f"اليوم: {result['today']} | نافذة الحداثة: {result['days']} أيام | "
             f"طازجة: {result['total']}"]
    if not keywords:
        lines.append("لا كلمات طازجة — كل المدخلات قديمة أو القائمة فارغة.")
    for i, entry in enumerate(keywords, 1):
        label = f" | {TRENDING_LABEL}" if entry["trending_today"] else ""
        lines.append(f"{i}. «{entry['keyword']}» — الدرجة: {entry['score']:.1f}/100"
                     f" | الحالة: {entry['status']}{label}")
        lines.append(f"   {entry['reason']} | التاريخ: {entry['date']}"
                     f" (عمره {entry['age_days']} أيام)")
        if entry["source"]:
            lines.append(f"   المصدر: {entry['source']}")
    lines.append("")
    lines.append(f"مقترحة للطابور ({len(suggestions)}):")
    if not suggestions:
        lines.append("لا اقتراحات — كل الكلمات الطازجة مستبعدة أو قديمة.")
    for i, entry in enumerate(suggestions, 1):
        label = f" [{TRENDING_LABEL}]" if entry["trending_today"] else ""
        lines.append(f"{i}. «{entry['keyword']}»{label} — {entry['score']:.1f}/100"
                     f" ({entry['reason']})")
    if result["excluded"]:
        lines.append("")
        lines.append("مستبعدة (رعب/غموض — خارج الخط بانتظار قرار "
                     "المستخدم، لا تُقترح أبدًا):")
        for keyword in result["excluded"]:
            lines.append(f"- «{keyword}»")
    if stale:
        lines.append("")
        lines.append(f"قديمة — خارج نافذة {result['days']} أيام ({len(stale)}):")
        for entry in stale:
            lines.append(f"- «{entry['keyword']}» — {entry['reason']}")
    lines.append("")
    lines.append("النمو المجهول يظهر «غير مقاس» — لا أرقام مخترعة.")
    lines.append("الرعب/الغموض مستبعد من خطنا — لا يُقترح أبدًا.")
    return "\n".join(lines)
