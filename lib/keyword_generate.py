#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""مولّد كلمات مفتاحية عربية من بذرة — جولة v0.1.61 (W3).

الفكرة (من نمط «Keyword Generator» في GuinRank فقط، بلا نسخ
كود — GuinRank أداة تجارية مغلقة بلا مستودع وبلا API):
المشغّل يزوّد بذرة (موضوع قصة) وقائمة corpus اختيارية
{keyword, volume?} من كلمات ذات صلة (مثل كلمات vidIQ ذات
الصلة)، والوحدة تولّد مرشحين حتميًا بقوالب عربية من مجال
القصص — بلا شبكة وبلا LLM وبلا عشوائية.

قوالب التوليد (بالترتيب، وكلها موثّقة هنا):
1. بادئات: «قصص »، «قصة »، «حكاية »، «قصص واقعية »،
   «قصص قبل النوم » + البذرة — وتُتخطى كلها إن كانت في
   البذرة كلمة فئة (قصص/قصة/حكاية/حكايات)، فالبادئة زائدة
   حينها (البذرة «قصص» تولّد لواحق وذيولًا فقط).
2. لواحق: البذرة + « حقيقية»، « مؤثرة»، « قصيرة»،
   « للاطفال»، « وعبرة»، « من الواقع»، « كاملة».
3. ذيل طويل (قصصي فقط): البذرة + « كاملة»، « ملخص»،
   « بالعربي»، « مكتوبة». و« كاملة» مكررة مع اللواحق عمدًا
   فيبقيها إزالة التكرار بصيغتها الأولى.
4. توسيع بالكلمات المشتركة: كلمة تظهر (بعد التطبيع) في
   كلمتين مختلفتين على الأقل من الـcorpus، ما عدا كلمات
   البذرة نفسها والكلمات العامة «قصص/قصة/حكاية» (تغطيها
   البادئات)، تولّد «البذرة + الكلمة» فقط — العكس («الكلمة
   + البذرة») مرفوض لأنه ينتج صيغًا غير طبيعية في العربية.
5. كلمات الـcorpus نفسها كما هي (بعد إزالة التكرار) —
   فكلمة ذات صلة مزوّدة مرشح قائم بذاته.

المرفوض صراحة: ذيل « الجزء الاول» لا يُولَّد أبدًا —
الذيول قصصية فقط (القائمة أعلاه).

قواعد عامة:
- البذرة نفسها لا تظهر في النتائج إطلاقًا (هي المدخل) —
  حتى لو وردت في الـcorpus.
- لا مرشح مولّد مكرر لفظيًا: أي كلمة مطبّعة تظهر مرتين
  في المرشح (مثل «قصص قصص» أو «قصص واقعية واقعية»)
  تُسقطه؛ والبادئات لا تُطبَّق أصلًا على بذرة فيها كلمة
  فئة (قصص/قصة/حكاية/حكايات) — فالبادئة مهمتها إضافة
  كلمة الفئة، وهي موجودة في البذرة أصلًا. كلمات الـcorpus
  نفسها مستثناة من الحارسين (بيانات مشغّل تُعرض كما هي).
- إزالة تكرار بالصيغة المطبّعة (أ/إ/آ←ا، ة←ه، ى←ي، إزالة
  التشكيل والتطويل) مع الاحتفاظ بصيغة العرض الأولى.
- الحجم يُورَّث فقط من الـcorpus عند تطابق الصيغة المطبّعة
  بين المرشح المولّد وكلمة corpus — ولا يُخترع حجم أبدًا.
  بلا حجم معروف يظهر المرشح «غير مقاس».
- الترتيب: الحجم المعروف تنازليًا أولًا (والتعادل بترتيب
  التوليد)؛ ثم «غير مقاس» بترتيب التوليد؛ ثم يُقصّ عند
  limit (الافتراضي 20، والأقصى 100).
- دوال خالصة على بيانات يزوّدها المشغّل: لا تقرأ ملفات
  ولا تكتب ملفات؛ ومدخلات فاسدة → ``ValueError`` عربي.
"""
import json
import re

__all__ = [
    "generate_keywords",
    "format_report",
    "to_json",
    "load_corpus_json",
    "normalize_keyword",
]

# قوالب التوليد — قيم الإخراج (عربية)، بالترتيب الموثّق أعلاه.
PREFIXES = (
    "قصص ",
    "قصة ",
    "حكاية ",
    "قصص واقعية ",
    "قصص قبل النوم ",
)
SUFFIXES = (
    " حقيقية",
    " مؤثرة",
    " قصيرة",
    " للاطفال",
    " وعبرة",
    " من الواقع",
    " كاملة",
)
# ذيول قصصية فقط — « الجزء الاول» مرفوض ولا يظهر هنا.
LONG_TAILS = (
    " كاملة",
    " ملخص",
    " بالعربي",
    " مكتوبة",
)

# مصادر المرشحين (قيم الإخراج — عربية).
SOURCE_PREFIX = "بادئة"
SOURCE_SUFFIX = "لاحقة"
SOURCE_LONG_TAIL = "ذيل طويل"
SOURCE_EXPANSION = "توسيع بالكلمات المشتركة"
SOURCE_CORPUS = "من الـcorpus"

# حالات الحجم (قيم الإخراج — عربية).
VOLUME_MEASURED = "مقاس"
VOLUME_UNMEASURED = "غير مقاس"

DEFAULT_LIMIT = 20
MAX_LIMIT = 100

# كلمات عامة لا تُستخدم في التوسيع بالكلمات المشتركة —
# البادئات تغطيها، وعكسها مع البذرة غير طبيعي.
_GENERIC_WORDS = frozenset({"قصص", "قصه", "حكايه"})

# كلمات الفئة (قصص/قصة/حكاية/حكايات): البادئة مهمتها
# إضافتها، فتُتخطى البادئات كلها إن كانت في البذرة أصلًا.
_CATEGORY_WORDS = _GENERIC_WORDS | {"حكايات"}

# سطر يُطبع في كل تقرير.
NO_INVENTED_VOLUMES = ("لا أحجام مخترعة: أي كلمة بلا حجم "
                       "من الـcorpus تظهر «غير مقاس».")

# تطبيع عربي قبل المطابقة وإزالة التكرار (مثل trend_scout،
# مع إزالة التطويل أيضًا): أ/إ/آ←ا، ة←ه، ى←ي، إزالة التشكيل
# (U+064B–U+0652 وU+0670) والتطويل (U+0640).
_DIACRITICS_RE = re.compile(r"[\u064b-\u0652\u0670\u0640]")
_NORMALIZE_TABLE = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي",
})
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_keyword(text):
    """طبّع كلمة مفتاحية عربية للمطابقة وإزالة التكرار فقط.

    لا يغيّر النص المعروض؛ يرفع ``ValueError`` عربيًا إن
    كان المدخل فارغًا أو غير نص.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("الكلمة المفتاحية فارغة أو غير نص — أعطِ نصًا.")
    text = _DIACRITICS_RE.sub("", text.strip())
    text = text.translate(_NORMALIZE_TABLE)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _check_limit(limit):
    """تحقّق أن limit عدد صحيح بين 1 و100 (بلا bool)."""
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("«limit» يجب أن يكون عددًا صحيحًا — وصلت قيمة غير صحيحة.")
    if limit < 1:
        raise ValueError("«limit» يجب أن يكون 1 على الأقل.")
    if limit > MAX_LIMIT:
        raise ValueError(f"«limit» الأقصى {MAX_LIMIT} — وصل {limit}.")
    return limit


def _check_volume(value, name):
    """تحقّق أن الحجم عدد حقيقي منتهٍ غير سالب (بلا bool) أو None."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"«{name}» يجب أن يكون رقمًا — وصلت قيمة غير رقمية.")
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"«{name}» يجب أن يكون رقمًا منتهيًا.")
    if value < 0:
        raise ValueError(f"«{name}» سالب — الحجم لا يكون سالبًا.")
    return value


def _clean_corpus_entry(entry):
    """تحقّق من كلمة corpus واحدة وأعدها منظّفة؛ وإلا ``ValueError`` عربي."""
    if not isinstance(entry, dict):
        raise ValueError("كل كلمة corpus يجب أن تكون قاموسًا فيه keyword.")
    keyword = entry.get("keyword")
    if not isinstance(keyword, str) or not keyword.strip():
        raise ValueError("كلمة corpus بلا keyword — كل كلمة تحتاج keyword نصيًا غير فارغ.")
    return {
        "keyword": keyword.strip(),
        "volume": _check_volume(entry.get("volume"), "الحجم (volume)"),
    }


def load_corpus_json(text):
    """اقرأ مدخل corpus JSON نصيًا إلى قائمة كلمات منظّفة.

    يرفع ``ValueError`` عربيًا عند JSON تالف أو مدخل ليس
    قائمة أو كلمة فاسدة — بلا أي كتابة. القائمة الفارغة
    مسموحة (الـcorpus اختياري).
    """
    if not isinstance(text, str):
        raise ValueError("مدخل JSON يجب أن يكون نصًا.")
    try:
        data = json.loads(text)
    except ValueError:
        raise ValueError("مدخل JSON تالف — أعطِ قائمة corpus JSON صالحة.")
    if not isinstance(data, list):
        raise ValueError("مدخل الـcorpus يجب أن يكون قائمة كلمات.")
    return [_clean_corpus_entry(entry) for entry in data]


def _is_degenerate(key):
    """مرشح مولّد مكرر لفظيًا؟ أي كلمة مطبّعة تظهر مرتين
    في المرشح (مثل «قصص قصص» أو «قصص واقعية واقعية»).

    يطبَّق على المولّد فقط لا على كلمات الـcorpus (بيانات
    مشغّل تُعرض كما هي).
    """
    tokens = key.split()
    return len(tokens) != len(set(tokens))


def _shared_words(corpus, seed_words):
    """كلمات الـcorpus المشتركة بترتيب أول ظهور.

    الكلمة مشتركة إن ظهرت (بعد التطبيع) في كلمتين مختلفتين
    على الأقل من الـcorpus، ما عدا كلمات البذرة والكلمات
    العامة «قصص/قصة/حكاية». ترجع صيغ العرض الأولى (لا
    المطبّعة) بترتيب أول ظهور.
    """
    counts = {}
    display = {}
    order = []
    for entry in corpus:
        seen_here = set()
        for word in entry["keyword"].split():
            key = normalize_keyword(word)
            if not key or key in seed_words or key in _GENERIC_WORDS:
                continue
            if key not in seen_here:
                seen_here.add(key)
                if key not in counts:
                    counts[key] = 0
                    display[key] = word
                    order.append(key)
                counts[key] += 1
    return [display[key] for key in order if counts[key] >= 2]


def generate_keywords(seed, corpus=None, limit=20):
    """ولّد كلمات مفتاحية عربية من بذرة (وcorpus اختياري).

    ``seed``: موضوع القصة نصًا غير فارغ — لا يظهر في النتائج.
    ``corpus``: قائمة قواميس {keyword, volume?} يزوّدها
    المشغّل (مثل كلمات vidIQ ذات الصلة)، أو نص JSON لها،
    أو None. ``limit``: عدد النتائج المطلوبة (1–100،
    الافتراضي 20).

    ترجع قاموسًا: ``seed`` (البذرة مجرّدة)، و``keywords``
    (قائمة {keyword, volume, volume_status, source} مرتبة:
    الحجم المعروف تنازليًا أولًا ثم «غير مقاس» بترتيب
    التوليد، مقصوصة عند limit)، و``total``، و``measured``،
    و``unmeasured``، و``limit``.

    مدخلات فاسدة (بذرة فارغة، limit خارج 1–100، كلمة
    corpus بلا keyword أو بحجم سالب/غير رقمي) →
    ``ValueError`` عربي.
    """
    if not isinstance(seed, str) or not seed.strip():
        raise ValueError("البذرة فارغة أو غير نص — أعطِ موضوع قصة نصيًا.")
    limit = _check_limit(limit)
    seed = seed.strip()
    if corpus is None:
        corpus = []
    elif isinstance(corpus, str):
        corpus = load_corpus_json(corpus)
    if not isinstance(corpus, (list, tuple)):
        raise ValueError("مدخل الـcorpus يجب أن يكون قائمة كلمات أو None.")
    cleaned = [_clean_corpus_entry(entry) for entry in corpus]

    seed_key = normalize_keyword(seed)
    seed_words = set(normalize_keyword(seed).split())

    # خريطة الحجم من الـcorpus بالصيغة المطبّعة: أول حجم
    # معروف يفوز، ولا يُخترع حجم لما ليس فيها.
    volumes = {}
    for entry in cleaned:
        key = normalize_keyword(entry["keyword"])
        if key not in volumes:
            volumes[key] = entry["volume"]
        elif volumes[key] is None and entry["volume"] is not None:
            volumes[key] = entry["volume"]

    # توليد حتمي بالترتيب الموثّق في مقدّمة الوحدة.
    # البادئات تُتخطى كلها إن كانت في البذرة كلمة فئة
    # (قصص/قصة/حكاية/حكايات) — مهمتها إضافة كلمة الفئة
    # وهي موجودة في البذرة أصلًا.
    generated = []  # (صيغة العرض، المصدر)
    seed_has_category = bool(seed_words & _CATEGORY_WORDS)
    if not seed_has_category:
        for prefix in PREFIXES:
            generated.append((prefix + seed, SOURCE_PREFIX))
    for suffix in SUFFIXES:
        generated.append((seed + suffix, SOURCE_SUFFIX))
    for tail in LONG_TAILS:
        generated.append((seed + tail, SOURCE_LONG_TAIL))
    for word in _shared_words(cleaned, seed_words):
        generated.append((seed + " " + word, SOURCE_EXPANSION))
    for entry in cleaned:
        generated.append((entry["keyword"], SOURCE_CORPUS))

    # إزالة تكرار بالصيغة المطبّعة مع الاحتفاظ بصيغة العرض
    # الأولى؛ والبذرة نفسها لا تظهر أبدًا؛ والمرشح المولّد
    # المكرر لفظيًا (أي كلمة مرتين) يُسقط.
    seen = set()
    candidates = []
    for display, source in generated:
        key = normalize_keyword(display)
        if key == seed_key:
            continue
        if key in seen:
            continue
        if source != SOURCE_CORPUS and _is_degenerate(key):
            continue
        seen.add(key)
        volume = volumes.get(key)
        candidates.append({
            "keyword": display,
            "volume": volume,
            "volume_status": (VOLUME_MEASURED if volume is not None
                              else VOLUME_UNMEASURED),
            "source": source,
        })

    # الحجم المعروف تنازليًا أولًا (والتعادل بترتيب التوليد
    # — الفرز مستقر)، ثم «غير مقاس» بترتيب التوليد.
    measured = sorted(
        [c for c in candidates if c["volume"] is not None],
        key=lambda c: -c["volume"])
    unmeasured = [c for c in candidates if c["volume"] is None]
    keywords = (measured + unmeasured)[:limit]

    return {
        "seed": seed,
        "keywords": keywords,
        "total": len(keywords),
        "measured": len([c for c in keywords if c["volume"] is not None]),
        "unmeasured": len([c for c in keywords if c["volume"] is None]),
        "limit": limit,
    }


def to_json(result):
    """سلسل نتيجة ``generate_keywords`` إلى JSON عربي (بلا ASCII هارب)."""
    if not isinstance(result, dict):
        raise ValueError("نتيجة المولّد يجب أن تكون قاموسًا من generate_keywords.")
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def format_report(result):
    """نسّق نتيجة ``generate_keywords`` تقريرًا عربيًا.

    يحوي دائمًا سطر «لا أحجام مخترعة»، وسطر أن البذرة
    نفسها ليست ضمن النتائج.
    """
    if not isinstance(result, dict):
        raise ValueError("نتيجة المولّد يجب أن تكون قاموسًا من generate_keywords.")
    for key in ("seed", "keywords", "total", "measured", "unmeasured"):
        if key not in result:
            raise ValueError(f"نتيجة المولّد ناقصة — ينقصها «{key}».")
    keywords = result["keywords"]
    lines = ["مولّد الكلمات المفتاحية — قائمة مقترحة",
             "=====================================",
             f"البذرة: «{result['seed']}»",
             f"العدد: {result['total']} كلمة "
             f"({result['measured']} مقاسة، {result['unmeasured']} غير مقاسة)"]
    if not keywords:
        lines.append("لا كلمات — لم يُولَّد أي مرشح.")
    for i, entry in enumerate(keywords, 1):
        volume = entry["volume"]
        volume_text = f"حجم {volume}" if volume is not None else VOLUME_UNMEASURED
        lines.append(f"{i}. «{entry['keyword']}» — {volume_text} "
                     f"[{entry['source']}]")
    lines.append("")
    lines.append("البذرة نفسها ليست ضمن النتائج — هي المدخل.")
    lines.append(NO_INVENTED_VOLUMES)
    return "\n".join(lines)
