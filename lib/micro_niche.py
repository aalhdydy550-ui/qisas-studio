#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""باحث التخصصات الدقيقة (Micro Niche Finder) — جولة v0.1.61 (W4).

الفكرة (من طريقة Micro Niche Finder في GuinRank فقط، بلا نسخ كود):
المشغّل يزوّد قائمة تخصصات مقترحة لقصصنا، كل تخصص فيه كلمات
بحث مع حجم طلب ومنافسة (من بحثه هو — أدوات الكلمات أو تقديره)،
ويزوّد اختياريًا مكتبة قصصنا (عناوين ومواضيع)، والوحدة ترتّب
التخصصات بدرجة فرصة حتمية — بلا شبكة وبلا LLM وبلا عشوائية.

قواعد الوحدة:
- المدخل قائمة قواميس {name, keywords: [{keyword, volume?,
  competition?}]} — يزوّدها المشغّل جاهزة. والمكتبة اختيارية:
  قائمة قواميس {title, topic?}. قراءة فقط: بلا شبكة وبلا جلب
  وبلا قراءة ملفات — دوال خالصة على بيانات يزوّدها المشغّل.
- لكل تخصص: متوسط المنافسة من القيم المعروفة فقط، وإجمالي
  الحجم ومتوسطه من القيم المعروفة فقط، والتغطية = نسبة كلمات
  التخصص الموجودة أصلًا في عناوين/مواضيع المكتبة (مطابقة نص
  جزئي بعد التطبيع العربي).
- درجة الفرصة 0–100 من ثلاث إشارات فقط:
  1. المنافسة المنخفضة — حتى 40 نقطة:
     ``40 × (1 − متوسط المنافسة / 100)``؛ منافسة 0 تعطي
     40 كاملة، ومنافسة 100 تعطي صفرًا. بلا منافسة معروفة
     تساهم بصفر وتُذكر «غير مقاس».
  2. إشارة الحجم — حتى 30 نقطة:
     ``30 × min(متوسط الحجم / 5000, 1)``؛ متوسط حجم 5000
     فأكثر يشبع الإشارة (30 نقطة)، وأقل منه تناسبيًا.
     بلا حجم معروف تساهم بصفر وتُذكر «غير مقاس» — **وحجم
     مجهول تمامًا لا يعني «بلا طلب» أبدًا**.
  3. فجوة التغطية — حتى 30 نقطة:
     ``30 × (1 − التغطية)``؛ تخصص بلا أي كلمة مغطاة يأخذ
     30 كاملة، والمغطى بالكامل يأخذ صفرًا.
- الأحكام (بهذا الترتيب، أول حكم ينطبق يفوز):
  1. «بلا طلب»: كل أحجام كلمات التخصص معروفة والإجمالي
     أقل من 500.
  2. «مزدحم»: متوسط المنافسة ≥ 65، أو الدرجة < 40 مع منافسة
     عالية (متوسط منافسة ≥ 50).
  3. «فرصة»: الدرجة ≥ 60.
  4. «ممكن»: ما بقي — الدرجة 40–59، أو درجة < 40 مع منافسة
     غير عالية وطلب غير منعدم (تُذكر ضعف الدرجة في السبب).
- الترتيب بالدرجة تنازليًا ثم الاسم — حتمي بلا عشوائية.
- التطبيع العربي للمطابقة فقط (لا يغيّر النص المعروض):
  أ/إ/آ←ا، ة←ه، ى←ي، وإزالة التشكيل والتطويل. المطابقة
  جزئية في الاتجاهين: الكلمة المطبّعة داخل عنوان/موضوع
  مطبّع، أو عنوان/موضوع مطبّع قصير (حرفان فأكثر) داخل
  الكلمة المطبّعة.
- مدخل فاسد (قائمة فارغة، تخصص بلا اسم، منافسة خارج
  0–100، حجم سالب) → ``ValueError`` عربي.
"""
import json
import math
import re

__all__ = [
    "VERDICT_OPPORTUNITY",
    "VERDICT_POSSIBLE",
    "VERDICT_CROWDED",
    "VERDICT_NO_DEMAND",
    "find_micro_niches",
    "format_report",
    "to_json",
    "load_niches_json",
]

# الأحكام (قيم الإخراج — عربية).
VERDICT_OPPORTUNITY = "فرصة"
VERDICT_POSSIBLE = "ممكن"
VERDICT_CROWDED = "مزدحم"
VERDICT_NO_DEMAND = "بلا طلب"

# حالة القياس (قيم الإخراج — عربية).
MEASURED = "مقاس"
UNMEASURED = "غير مقاس"

# أوزان الدرجة (المجموع 100).
COMPETITION_WEIGHT = 40.0
VOLUME_WEIGHT = 30.0
GAP_WEIGHT = 30.0

# مرجع إشارة الحجم: متوسط حجم يشبع الإشارة.
VOLUME_REFERENCE = 5000
# حد «بلا طلب»: إجمالي حجم أقل من هذا وكل الأحجام معروفة.
NO_DEMAND_TOTAL_BELOW = 500
# حد «مزدحم» بالمنافسة وحدها.
CROWDED_COMPETITION_AT_LEAST = 65
# حد «منافسة عالية» في شرط الدرجة المنخفضة.
HIGH_COMPETITION_AT_LEAST = 50

# سطور تُطبع في كل تقرير.
NO_DEMAND_WARNING = ("الحجم غير المقاس يظهر «غير مقاس» "
                     "ولا يعني «بلا طلب» أبدًا.")
METHOD_NOTE = ("الطريقة: منافسة منخفضة 40 + إشارة حجم 30 + "
               "فجوة تغطية 30 — من بيانات المشغّل فقط، بلا شبكة "
               "وبلا تقديرات.")

# تطبيع حروف عربية قبل المطابقة (ة↔ه، أ/إ/آ↔ا، ى↔ي) +
# إزالة التشكيل والتطويل.
_DIACRITICS_RE = re.compile(r"[\u0640\u064b-\u0652\u0670]")
_NORMALIZE_TABLE = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي",
})


def _normalize(text):
    """تطبيع نص عربي للمطابقة فقط (لا يغيّر النص المعروض)."""
    text = _DIACRITICS_RE.sub("", text)
    return text.translate(_NORMALIZE_TABLE)


def _check_number(value, name, minimum=None, maximum=None):
    """تحقّق أن القيمة عدد حقيقي منتهٍ (بلا bool) أو None."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"«{name}» يجب أن تكون رقمًا — وصلت قيمة غير رقمية.")
    if not math.isfinite(value):
        raise ValueError(f"«{name}» يجب أن تكون رقمًا منتهيًا.")
    if minimum is not None and value < minimum:
        raise ValueError(f"«{name}» سالبة — القيمة لا تكون سالبة.")
    if maximum is not None and value > maximum:
        raise ValueError(f"«{name}» خارج النطاق — يجب أن تكون بين "
                         f"{minimum} و{maximum}.")
    return value


def _check_volume(value, keyword):
    """تحقّق من حجم كلمة: عدد غير سالب أو None (غير مقاس)."""
    return _check_number(value, f"حجم «{keyword}»", minimum=0)


def _check_competition(value, keyword):
    """تحقّق من منافسة كلمة: عدد بين 0 و100 أو None (غير مقاس)."""
    return _check_number(value, f"منافسة «{keyword}»",
                         minimum=0, maximum=100)


def _clean_keyword(entry, niche_name):
    """تحقّق من كلمة بحث واحدة وأعدها منظّفة؛ وإلا ``ValueError`` عربي."""
    if not isinstance(entry, dict):
        raise ValueError(f"كل كلمة في تخصص «{niche_name}» يجب أن تكون "
                         "قاموسًا فيه keyword.")
    keyword = entry.get("keyword")
    if not isinstance(keyword, str) or not keyword.strip():
        raise ValueError(f"كلمة فارغة في تخصص «{niche_name}» — كل كلمة "
                         "تحتاج keyword نصيًا غير فارغ.")
    keyword = keyword.strip()
    return {
        "keyword": keyword,
        "volume": _check_volume(entry.get("volume"), keyword),
        "competition": _check_competition(entry.get("competition"), keyword),
    }


def _clean_niche(niche):
    """تحقّق من تخصص واحد وأعده منظّفًا؛ وإلا ``ValueError`` عربي."""
    if not isinstance(niche, dict):
        raise ValueError("كل تخصص يجب أن يكون قاموسًا فيه name وkeywords.")
    name = niche.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("تخصص بلا اسم — كل تخصص يحتاج name نصيًا غير فارغ.")
    keywords = niche.get("keywords", [])
    if keywords is None:
        keywords = []
    if not isinstance(keywords, list):
        raise ValueError(f"كلمات تخصص «{name.strip()}» يجب أن تكون قائمة.")
    return {
        "name": name.strip(),
        "keywords": [_clean_keyword(entry, name.strip())
                     for entry in keywords],
    }


def _clean_library_entry(entry):
    """تحقّق من عنصر مكتبة واحد وأعده منظّفًا؛ وإلا ``ValueError`` عربي."""
    if not isinstance(entry, dict):
        raise ValueError("كل عنصر في المكتبة يجب أن يكون قاموسًا فيه title.")
    title = entry.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("عنصر مكتبة بلا عنوان — كل عنصر يحتاج "
                         "title نصيًا غير فارغ.")
    topic = entry.get("topic", "")
    if topic is None:
        topic = ""
    if not isinstance(topic, str):
        raise ValueError("موضوع عنصر المكتبة (topic) يجب أن يكون نصًا.")
    return {"title": title.strip(), "topic": topic.strip()}


def _clean_library(library):
    """تحقّق من المكتبة كلها؛ None تعني مكتبة فارغة."""
    if library is None:
        return []
    if isinstance(library, str):
        try:
            library = json.loads(library)
        except ValueError:
            raise ValueError("مدخل JSON للمكتبة تالف — أعطِ قائمة "
                             "عناصر JSON صالحة.")
    if not isinstance(library, (list, tuple)):
        raise ValueError("المكتبة يجب أن تكون قائمة عناصر {title, topic?}.")
    return [_clean_library_entry(entry) for entry in library]


def _coverage(keywords, library_texts):
    """نسبة كلمات مغطاة في نصوص المكتبة المطبّعة (0.0–1.0).

    الكلمة مغطاة إن ظهرت مطبّعة داخل نص مكتبة مطبّع، أو ظهر
    نص مكتبة مطبّع قصير (حرفان فأكثر) داخلها. بلا كلمات
    تكون التغطية صفرًا والفجوة كاملة.
    """
    if not keywords:
        return 0, 0.0
    covered = 0
    for entry in keywords:
        normalized = _normalize(entry["keyword"])
        if not normalized:
            continue
        for text in library_texts:
            if not text:
                continue
            if normalized in text:
                covered += 1
                break
            if len(text) >= 2 and text in normalized:
                covered += 1
                break
    return covered, round(covered / len(keywords), 4)


def _verdict(score, avg_competition, all_volumes_known, total_volume):
    """حكم التخصص — أول حكم ينطبق يفوز (موثّق في مقدّمة الوحدة)."""
    if all_volumes_known and total_volume < NO_DEMAND_TOTAL_BELOW:
        return VERDICT_NO_DEMAND
    if avg_competition is not None and (
            avg_competition >= CROWDED_COMPETITION_AT_LEAST
            or (score < 40 and avg_competition >= HIGH_COMPETITION_AT_LEAST)):
        return VERDICT_CROWDED
    if score >= 60:
        return VERDICT_OPPORTUNITY
    return VERDICT_POSSIBLE


def _reason(avg_competition, volume_status, total_volume, avg_volume,
            covered, keyword_count, coverage, score):
    """سبب عربي بالقياسات — «غير مقاس» لأي إشارة بلا مصدر."""
    if avg_competition is None:
        comp_text = f"المنافسة {UNMEASURED}"
    else:
        comp_text = f"منافسة متوسطة {avg_competition:.1f}"
    if volume_status == UNMEASURED:
        vol_text = f"الحجم {UNMEASURED} — لا يعني «بلا طلب»"
    else:
        vol_text = (f"حجم إجمالي {total_volume} ومتوسط {avg_volume:.1f}")
    cover_text = (f"تغطية المكتبة {coverage * 100:.1f}% "
                  f"({covered} من {keyword_count})؛ "
                  f"فجوة {(1 - coverage) * 100:.1f}%")
    text = f"{comp_text}؛ {vol_text}؛ {cover_text}"
    if score < 40:
        text += "؛ الدرجة دون 40 — إشارة ضعيفة"
    return text


def _score(avg_competition, avg_volume, coverage):
    """درجة الفرصة 0–100 ومكوّناتها (غير المقاس = صفر)."""
    comp_points = 0.0
    if avg_competition is not None:
        comp_points = COMPETITION_WEIGHT * (1 - avg_competition / 100)
    vol_points = 0.0
    if avg_volume is not None:
        vol_points = VOLUME_WEIGHT * min(avg_volume / VOLUME_REFERENCE, 1.0)
    gap_points = GAP_WEIGHT * (1 - coverage)
    total = round(comp_points + vol_points + gap_points, 1)
    return total, {
        "competition": round(comp_points, 1),
        "volume": round(vol_points, 1),
        "gap": round(gap_points, 1),
    }


def load_niches_json(text):
    """اقرأ مدخل JSON نصيًا إلى (تخصصات، مكتبة) منظّفين.

    يقبل قائمة تخصصات، أو قاموسًا فيه «niches» ومكتبة
    اختيارية «library». يرفع ``ValueError`` عربيًا عند JSON
    تالف أو مدخل ليس قائمة/قاموسًا أو تخصص فاسد — بلا أي
    كتابة.
    """
    if not isinstance(text, str):
        raise ValueError("مدخل JSON يجب أن يكون نصًا.")
    try:
        data = json.loads(text)
    except ValueError:
        raise ValueError("مدخل JSON تالف — أعطِ تخصصات JSON صالحة.")
    library = []
    if isinstance(data, dict):
        if "niches" not in data:
            raise ValueError("مدخل JSON قاموسًا بلا «niches» — أعطِ قائمة "
                             "تخصصات أو قاموسًا فيه «niches».")
        niches = data["niches"]
        if "library" in data and data["library"] is not None:
            library = data["library"]
    elif isinstance(data, list):
        niches = data
    else:
        raise ValueError("مدخل التخصصات يجب أن يكون قائمة تخصصات أو "
                         "قاموسًا فيه «niches».")
    if not isinstance(niches, list) or len(niches) == 0:
        raise ValueError("قائمة التخصصات فارغة — أعطِ تخصصًا واحدًا "
                         "على الأقل.")
    return ([_clean_niche(niche) for niche in niches],
            _clean_library(library))


def find_micro_niches(niches, library=None):
    """رتّب تخصصات دقيقة بدرجة فرصة واحكم عليها.

    ``niches``: قائمة قواميس {name, keywords: [{keyword,
    volume?, competition?}]} (الحجم والمنافسة اختياريان؛
    والاسم والكلمة إلزاميان)، أو نص JSON يقبله
    ``load_niches_json``. ``library``: قائمة قواميس
    {title, topic?} (مكتبة قصصنا) — اختيارية.

    ترجع قاموسًا: ``niches`` (كل التخصصات مرتبة بالدرجة
    تنازليًا ثم الاسم: الاسم وعدد الكلمات وعدد المقاس منها
    ومتوسط المنافسة وإجمالي/متوسط الحجم وحالة قياس الحجم
    والتغطية والكلمات المغطاة والفجوة والدرجة ومكوّناتها
    والحكم والسبب)، و``total``، و``library_size``،
    و``reference`` (الأوزان والمراجع والعتبات).

    مدخلات فاسدة (قائمة فارغة، تخصص بلا اسم، منافسة خارج
    0–100، حجم سالب) → ``ValueError`` عربي.
    """
    if isinstance(niches, str):
        parsed_niches, parsed_library = load_niches_json(niches)
        niches = parsed_niches
        if library is None:
            library = parsed_library
    if not isinstance(niches, (list, tuple)):
        raise ValueError("مدخل التخصصات يجب أن يكون قائمة تخصصات.")
    if len(niches) == 0:
        raise ValueError("قائمة التخصصات فارغة — أعطِ تخصصًا واحدًا "
                         "على الأقل.")
    cleaned_niches = [_clean_niche(niche) for niche in niches]
    cleaned_library = _clean_library(library)
    library_texts = []
    for entry in cleaned_library:
        for field in (entry["title"], entry["topic"]):
            normalized = _normalize(field)
            if normalized:
                library_texts.append(normalized)

    results = []
    for niche in cleaned_niches:
        keywords = niche["keywords"]
        competitions = [entry["competition"] for entry in keywords
                        if entry["competition"] is not None]
        volumes = [entry["volume"] for entry in keywords
                   if entry["volume"] is not None]
        avg_competition = (round(sum(competitions) / len(competitions), 1)
                           if competitions else None)
        if volumes:
            total_volume = sum(volumes)
            avg_volume = round(sum(volumes) / len(volumes), 1)
            volume_status = MEASURED
        else:
            total_volume = None
            avg_volume = None
            volume_status = UNMEASURED
        covered, coverage = _coverage(keywords, library_texts)
        score, components = _score(avg_competition, avg_volume, coverage)
        all_volumes_known = len(volumes) == len(keywords) and len(keywords) > 0
        verdict = _verdict(score, avg_competition, all_volumes_known,
                           total_volume if total_volume is not None else 0)
        results.append({
            "name": niche["name"],
            "keyword_count": len(keywords),
            "keywords_with_volume": len(volumes),
            "keywords_with_competition": len(competitions),
            "avg_competition": avg_competition,
            "total_volume": total_volume,
            "avg_volume": avg_volume,
            "volume_status": volume_status,
            "coverage": coverage,
            "covered_keywords": covered,
            "gap": round(1 - coverage, 4),
            "score": score,
            "components": components,
            "verdict": verdict,
            "reason": _reason(avg_competition, volume_status, total_volume,
                              avg_volume, covered, len(keywords), coverage,
                              score),
        })
    # الدرجة تنازليًا، ثم الاسم — حتمي بلا عشوائية.
    results.sort(key=lambda e: (-e["score"], e["name"]))

    return {
        "niches": results,
        "total": len(results),
        "library_size": len(cleaned_library),
        "reference": {
            "competition_weight": COMPETITION_WEIGHT,
            "volume_weight": VOLUME_WEIGHT,
            "gap_weight": GAP_WEIGHT,
            "volume_reference": VOLUME_REFERENCE,
            "no_demand_total_below": NO_DEMAND_TOTAL_BELOW,
            "crowded_competition_at_least": CROWDED_COMPETITION_AT_LEAST,
            "high_competition_at_least": HIGH_COMPETITION_AT_LEAST,
            "source": "طريقة Micro Niche Finder — بيانات يزوّدها "
                      "المشغّل فقط، بلا شبكة",
        },
    }


def to_json(result):
    """سلسل نتيجة ``find_micro_niches`` إلى JSON عربي (بلا ASCII هارب)."""
    if not isinstance(result, dict):
        raise ValueError("نتيجة الباحث يجب أن تكون قاموسًا من "
                         "find_micro_niches.")
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def format_report(result):
    """نسّق نتيجة ``find_micro_niches`` تقريرًا عربيًا.

    يحوي دائمًا سطر الطريقة، وسطر «الحجم غير المقاس ...
    لا يعني بلا طلب»، وتعريف الأحكام.
    """
    if not isinstance(result, dict):
        raise ValueError("نتيجة الباحث يجب أن تكون قاموسًا من "
                         "find_micro_niches.")
    for key in ("niches", "total", "library_size"):
        if key not in result:
            raise ValueError(f"نتيجة الباحث ناقصة — ينقصها «{key}».")
    niches = result["niches"]
    lines = ["باحث التخصصات الدقيقة — فرص لقصصنا",
             "==================================",
             f"التخصصات: {result['total']} | عناصر المكتبة: "
             f"{result['library_size']}"]
    if not niches:
        lines.append("لا تخصصات — القائمة فارغة.")
    for i, entry in enumerate(niches, 1):
        lines.append(f"{i}. «{entry['name']}» — {entry['verdict']} — "
                     f"الدرجة: {entry['score']:.1f}/100")
        comp = (f"{entry['avg_competition']:.1f}"
                if entry["avg_competition"] is not None else UNMEASURED)
        if entry["volume_status"] == UNMEASURED:
            vol = UNMEASURED
        else:
            vol = (f"إجمالي {entry['total_volume']} ومتوسط "
                   f"{entry['avg_volume']:.1f}")
        lines.append(f"   المنافسة: {comp} | الحجم: {vol} | "
                     f"التغطية: {entry['coverage'] * 100:.1f}% "
                     f"({entry['covered_keywords']} من "
                     f"{entry['keyword_count']})")
        lines.append(f"   {entry['reason']}")
    lines.append("")
    lines.append(METHOD_NOTE)
    lines.append(NO_DEMAND_WARNING)
    lines.append("الأحكام: فرصة ≥60؛ ممكن 40–59؛ مزدحم عند منافسة "
                 "≥65 أو درجة <40 مع منافسة عالية (≥50)؛ بلا طلب "
                 "عند طلب إجمالي <500 وكل الأحجام معروفة.")
    return "\n".join(lines)
