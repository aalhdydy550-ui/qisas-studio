#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""محلّل صفحة/فيديو على طريقة Page Analyzer في GuinRank — جولة v0.1.61 (W5).

الفكرة (من طريقة «Page Analyzer» في GuinRank فقط، بلا نسخ كود —
GuinRank أداة تجارية مغلقة بلا مستودع وبلا API): المشغّل يزوّد
بيانات صفحة/فيديو جاهزة (عنوان + وصف + وسوم + مدة + رابط +
كلمة مستهدفة اختيارية)، والوحدة تحلّلها ككل بدرجة 0–100
واقتراحات مرتبة بالأولوية — بلا شبكة وبلا LLM وبلا عشوائية.

الفحوصات العشرة (المجموع 100، والأوزان موثّقة هنا لا في
مكان آخر):
 1. طول العنوان 30–70 حرفًا — 5 نقاط.
 2. الكلمة المستهدفة في العنوان — 15 نقطة.
 3. الكلمة المستهدفة في أول 120 حرفًا من الوصف — 10 نقاط.
 4. طول الوصف 150–400 حرفًا — 10 نقاط.
 5. عدد الوسوم 5–15 — 10 نقاط.
 6. صلة الوسوم بالعنوان/الكلمة — 15 نقطة: نسبة الوسوم التي
    تشارك كلمة (بعد التطبيع والتجذير الخفيف) مع العنوان أو
    الكلمة المستهدفة، مضروبة في 15.
 7. هوك في أول سطر من الوصف — 10 نقاط: سؤال (؟ أو ?) أو
    إحدى كلمات الهوك «قصة/اسمع/تخيل».
 8. دعوة لطيفة في الوصف — 10 نقاط: وجود «الجزء الثاني» أو
    «اشترك» أو «تابعنا» (أو «تابعونا»)؛ لطيفة لا بوابة
    متابعة — الوحدة تكتفي برصد الوجود، ولا تقترح أبدًا
    صيغة بوابة متابعة.
 9. المدة في نطاق الشورت 40–60 ثانية إن أُعطيت — 10 نقاط؛
    وإن غابت فهي «غير مقاس» وصفر نقاط مع ذكرها صراحة —
    لا تُخترع مدة.
10. رابط موجود بصيغة سليمة (http(s):// + مضيف فيه نقطة) —
    5 نقاط.

الدرجة + التقدير: ممتاز ≥85، جيد 70–84، يحتاج تحسين
50–69، ضعيف <50.

الكلمة المستهدفة اختيارية: إن غابت فحصا الكلمة (2 و3)
«غير مقاس» وصفر نقاط، مع اقتراح واحد لكل فحص يطلب
تحديدها — لا يُفترض أي كلمة من العنوان.

المطابقة على مستوى الكلمة بعد تطبيع عربي (أ/إ/آ←ا، ة←ه،
ى←ي، إزالة التشكيل والتطويل) وتجذير خفيف لبوادئ الكلمة
(«لل/ال/و/ب/ف» — فـ«للصلاة» و«الصلاة» و«بالصلاة» كلمة
واحدة عند المطابقة). النصوص المعروضة في النتيجة تبقى كما
زوّدها المشغّل بلا تطبيع.

التكامل مع ``lib/seo_check.py`` و``lib/title_lint.py``
(بلا استيراد منهما إطلاقًا): هما فحصا ما قبل النشر — أول
سطرين من الوصف وحدود الوسوم/العنوان؛ أما هذه الوحدة
فتحلّل الصفحة ككل بعد تجهيزها (عنوان + وصف كامل + وسوم +
مدة + رابط) بدرجة واحدة واقتراحات مرتبة بالأولوية. من
يُشغَّل أولًا: فحصا ما قبل النشر عند التجهيز، ثم هذا
المحلّل كمراجعة شاملة قبل النشر أو بعده.

قواعد الوحدة:
- دوال خالصة على بيانات يزوّدها المشغّل — لا قراءة ملفات
  ولا كتابة ملفات ولا شبكة.
- مدخلات فاسدة (عنوان فارغ، وسوم ليست قائمة، مدة سالبة،
  وصف/رابط/كلمة غير نص) → ``ValueError`` عربي.
- الاقتراحات مرتبة: الأولوية (عالٍ ثم متوسط ثم منخفض)،
  ثم الوزن تنازليًا، ثم ترتيب الفحص — حتمي بلا عشوائية.
"""
import json
import math
import re

__all__ = [
    "analyze_page",
    "grade_score",
    "load_page_json",
    "to_json",
    "format_report",
]

# حدود الفحوصات.
TITLE_MIN = 30
TITLE_MAX = 70
DESC_MIN = 150
DESC_MAX = 400
DESC_KEYWORD_CHARS = 120
TAGS_MIN = 5
TAGS_MAX = 15
SHORT_MIN = 40
SHORT_MAX = 60

# أوزان الفحوصات (المجموع 100).
W_TITLE_LEN = 5
W_KEYWORD_TITLE = 15
W_KEYWORD_DESC = 10
W_DESC_LEN = 10
W_TAGS_COUNT = 10
W_TAGS_RELEVANCE = 15
W_HOOK = 10
W_CTA = 10
W_DURATION = 10
W_URL = 5

# التقديرات.
GRADE_EXCELLENT = "ممتاز"
GRADE_GOOD = "جيد"
GRADE_NEEDS_WORK = "يحتاج تحسين"
GRADE_WEAK = "ضعيف"

# الحالات.
STATUS_PASS = "ناجح"
STATUS_FAIL = "فاشل"
STATUS_UNMEASURED = "غير مقاس"

# الأولويات.
PRIORITY_HIGH = "عالٍ"
PRIORITY_MEDIUM = "متوسط"
PRIORITY_LOW = "منخفض"

# أسماء الفحوصات (مستقرة — تظهر في الاقتراحات والتقارير).
CHECK_TITLE_LEN = "طول العنوان"
CHECK_KEYWORD_TITLE = "الكلمة المستهدفة في العنوان"
CHECK_KEYWORD_DESC = "الكلمة المستهدفة في بداية الوصف"
CHECK_DESC_LEN = "طول الوصف"
CHECK_TAGS_COUNT = "عدد الوسوم"
CHECK_TAGS_RELEVANCE = "صلة الوسوم"
CHECK_HOOK = "هوك أول سطر"
CHECK_CTA = "دعوة لطيفة"
CHECK_DURATION = "مدة الشورت"
CHECK_URL = "الرابط"

# كلمات الهوك (بعد التطبيع: «قصة» ← «قصه»).
_HOOK_WORDS = ("قصه", "اسمع", "تخيل")
# عبارات الدعوة اللطيفة (بعد التطبيع).
_CTA_PHRASES = ("الجزء الثاني", "اشترك", "تابعنا", "تابعونا")

_URL_RE = re.compile(r"^https?://[^\s/]+\.[^\s/]{2,}([/?#][^\s]*)?$")

# تطبيع عربي للمطابقة (مثل lib/trend_scout.py + إزالة التطويل).
_DIACRITICS_RE = re.compile(r"[\u064b-\u0652\u0670\u0640]")
_NORMALIZE_TABLE = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي",
})
_WORD_RE = re.compile(r"[\w]+", re.UNICODE)
# بوادئ تُجرَّد عند مطابقة الكلمات (فقط إن بقيت الكلمة ≥3 أحرف).
_PREFIXES = ("لل", "ال", "و", "ب", "ف")


def _normalize(text):
    """تطبيع نص عربي للمطابقة فقط (لا يغيّر النص المعروض)."""
    text = _DIACRITICS_RE.sub("", text)
    return text.translate(_NORMALIZE_TABLE)


def _stem_token(token):
    """جرّد بوادئ الكلمة («لل/ال/و/ب/ف») للمطابقة."""
    while len(token) > 3:
        stripped = False
        for prefix in _PREFIXES:
            if token.startswith(prefix) and len(token) - len(prefix) >= 3:
                token = token[len(prefix):]
                stripped = True
                break
        if not stripped:
            break
    return token


def _tokens(text):
    """كلمات نص مطبّعة ومجذّرة (مجموعة بلا تكرار)."""
    return {_stem_token(word) for word in _WORD_RE.findall(_normalize(text))}


def _keyword_tokens(keyword):
    """كلمات الكلمة المستهدفة مطبّعة ومجذّرة (قائمة)."""
    return [_stem_token(word)
            for word in _WORD_RE.findall(_normalize(keyword))]


def _keyword_in(text, keyword):
    """هل كل كلمات الكلمة المستهدفة حاضرة في النص؟"""
    words = _keyword_tokens(keyword)
    if not words:
        return False
    target = _tokens(text)
    return all(word in target for word in words)


def _check_number(value, name):
    """تحقّق أن القيمة عدد حقيقي منتهٍ غير سالب (بلا bool) أو None."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"«{name}» يجب أن تكون رقمًا — وصلت قيمة غير رقمية.")
    if not math.isfinite(value):
        raise ValueError(f"«{name}» يجب أن تكون رقمًا منتهيًا.")
    if value < 0:
        raise ValueError(f"«{name}» سالبة — المدة لا تكون سالبة.")
    return value


def _clean_page(page):
    """تحقّق من صفحة وأعدها منظّفة؛ وإلا ``ValueError`` عربي."""
    if isinstance(page, str):
        page = load_page_json(page)
    if not isinstance(page, dict):
        raise ValueError("الصفحة يجب أن تكون قاموسًا فيه title على الأقل.")
    title = page.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("عنوان الصفحة فارغ أو غير نص — أعطِ عنوانًا نصيًا.")
    description = page.get("description", "")
    if description is None:
        description = ""
    if not isinstance(description, str):
        raise ValueError("وصف الصفحة (description) يجب أن يكون نصًا.")
    tags = page.get("tags", [])
    if tags is None:
        tags = []
    if not isinstance(tags, (list, tuple)):
        raise ValueError("وسوم الصفحة (tags) يجب أن تكون قائمة.")
    cleaned_tags = []
    for tag in tags:
        if not isinstance(tag, str):
            raise ValueError("كل وسم يجب أن يكون نصًا.")
        tag = tag.strip()
        if tag:
            cleaned_tags.append(tag)
    url = page.get("url", "")
    if url is None:
        url = ""
    if not isinstance(url, str):
        raise ValueError("رابط الصفحة (url) يجب أن يكون نصًا.")
    keyword = page.get("keyword", "")
    if keyword is None:
        keyword = ""
    if not isinstance(keyword, str):
        raise ValueError("الكلمة المستهدفة (keyword) يجب أن تكون نصًا.")
    return {
        "title": title.strip(),
        "description": description.strip(),
        "tags": cleaned_tags,
        "url": url.strip(),
        "duration": _check_number(page.get("duration"), "المدة"),
        "keyword": keyword.strip(),
    }


def grade_score(score):
    """تقدير عربي لدرجة 0–100."""
    if score >= 85:
        return GRADE_EXCELLENT
    if score >= 70:
        return GRADE_GOOD
    if score >= 50:
        return GRADE_NEEDS_WORK
    return GRADE_WEAK


_PRIORITY_RANK = {
    PRIORITY_HIGH: 0,
    PRIORITY_MEDIUM: 1,
    PRIORITY_LOW: 2,
}


def _suggestion(check, issue, suggestion, priority, weight, order):
    """اقتراح واحد مع مفتاح ترتيبه الداخلي (يُحذف قبل الإخراج)."""
    return {
        "check": check,
        "issue": issue,
        "suggestion": suggestion,
        "priority": priority,
        "_weight": weight,
        "_order": order,
    }


def analyze_page(page):
    """حلّل صفحة/فيديو وأعطِ درجة واقتراحات مرتبة.

    ``page``: قاموس {title, description, tags: [...], url?,
    duration?, keyword?} أو نص JSON له — العنوان إلزامي،
    والباقي اختياري (الوصف والوسوم والرابط والكلمة والمدة).

    ترجع قاموسًا: الحقول المزوّدة منظّفة + ``score`` (0–100)
    + ``grade`` (ممتاز/جيد/يحتاج تحسين/ضعيف) + ``checks``
    (الفحوصات العشرة: الاسم والوزن والنقاط والحالة والتفصيل)
    + ``suggestions`` (مرتبة: الأولوية ثم الوزن ثم ترتيب
    الفحص) + ``keyword_measured`` و``duration_measured``.

    مدخلات فاسدة → ``ValueError`` عربي.
    """
    cleaned = _clean_page(page)
    title = cleaned["title"]
    description = cleaned["description"]
    tags = cleaned["tags"]
    url = cleaned["url"]
    duration = cleaned["duration"]
    keyword = cleaned["keyword"]
    has_keyword = bool(keyword)

    checks = []
    suggestions = []

    def _add(check, weight, score, status, detail):
        checks.append({
            "check": check,
            "weight": weight,
            "score": score,
            "status": status,
            "detail": detail,
        })
        return score

    # 1. طول العنوان 30–70 حرفًا — 5.
    title_len = len(title)
    if TITLE_MIN <= title_len <= TITLE_MAX:
        total = _add(CHECK_TITLE_LEN, W_TITLE_LEN, W_TITLE_LEN,
                     STATUS_PASS,
                     f"طول العنوان {title_len} حرفًا (النطاق {TITLE_MIN}–{TITLE_MAX}).")
    else:
        total = _add(CHECK_TITLE_LEN, W_TITLE_LEN, 0, STATUS_FAIL,
                     f"طول العنوان {title_len} حرفًا (النطاق {TITLE_MIN}–{TITLE_MAX}).")
        if title_len < TITLE_MIN:
            issue = f"العنوان قصير ({title_len} حرفًا — أقل من {TITLE_MIN})."
            advice = "أطِل العنوان إلى 30 حرفًا على الأقل بإضافة الكلمة المستهدفة أو تفصيل جذاب."
        else:
            issue = f"العنوان طويل ({title_len} حرفًا — أكثر من {TITLE_MAX})."
            advice = "اختصر العنوان إلى 70 حرفًا على الأكثر مع إبقاء الكلمة المستهدفة."
        suggestions.append(_suggestion(CHECK_TITLE_LEN, issue, advice,
                                       PRIORITY_MEDIUM, W_TITLE_LEN, 1))

    # 2. الكلمة المستهدفة في العنوان — 15.
    if not has_keyword:
        total += _add(CHECK_KEYWORD_TITLE, W_KEYWORD_TITLE, 0,
                      STATUS_UNMEASURED,
                      "غير مقاس — بلا كلمة مستهدفة.")
        suggestions.append(_suggestion(
            CHECK_KEYWORD_TITLE, "بلا كلمة مستهدفة.",
            "حدّد كلمة مستهدفة واحدة للصفحة وضمّنها في العنوان.",
            PRIORITY_HIGH, W_KEYWORD_TITLE, 2))
    elif _keyword_in(title, keyword):
        total += _add(CHECK_KEYWORD_TITLE, W_KEYWORD_TITLE, W_KEYWORD_TITLE,
                      STATUS_PASS, f"الكلمة «{keyword}» حاضرة في العنوان.")
    else:
        total += _add(CHECK_KEYWORD_TITLE, W_KEYWORD_TITLE, 0, STATUS_FAIL,
                      f"الكلمة «{keyword}» غائبة عن العنوان.")
        suggestions.append(_suggestion(
            CHECK_KEYWORD_TITLE, f"الكلمة «{keyword}» غائبة عن العنوان.",
            f"أدخل الكلمة «{keyword}» في العنوان كما هي.",
            PRIORITY_HIGH, W_KEYWORD_TITLE, 2))

    # 3. الكلمة المستهدفة في أول 120 حرفًا من الوصف — 10.
    head = description[:DESC_KEYWORD_CHARS]
    if not has_keyword:
        total += _add(CHECK_KEYWORD_DESC, W_KEYWORD_DESC, 0,
                      STATUS_UNMEASURED,
                      "غير مقاس — بلا كلمة مستهدفة.")
        suggestions.append(_suggestion(
            CHECK_KEYWORD_DESC, "بلا كلمة مستهدفة.",
            "بعد تحديد الكلمة المستهدفة، ضمّنها في أول 120 حرفًا من الوصف.",
            PRIORITY_HIGH, W_KEYWORD_DESC, 3))
    elif _keyword_in(head, keyword):
        total += _add(CHECK_KEYWORD_DESC, W_KEYWORD_DESC, W_KEYWORD_DESC,
                      STATUS_PASS,
                      f"الكلمة «{keyword}» حاضرة في أول {DESC_KEYWORD_CHARS} حرفًا من الوصف.")
    else:
        total += _add(CHECK_KEYWORD_DESC, W_KEYWORD_DESC, 0, STATUS_FAIL,
                      f"الكلمة «{keyword}» غائبة عن أول {DESC_KEYWORD_CHARS} حرفًا من الوصف.")
        suggestions.append(_suggestion(
            CHECK_KEYWORD_DESC,
            f"الكلمة «{keyword}» غائبة عن أول {DESC_KEYWORD_CHARS} حرفًا من الوصف.",
            f"ابدأ الوصف بجملة فيها الكلمة «{keyword}».",
            PRIORITY_HIGH, W_KEYWORD_DESC, 3))

    # 4. طول الوصف 150–400 حرفًا — 10.
    desc_len = len(description)
    if DESC_MIN <= desc_len <= DESC_MAX:
        total += _add(CHECK_DESC_LEN, W_DESC_LEN, W_DESC_LEN, STATUS_PASS,
                      f"طول الوصف {desc_len} حرفًا (النطاق {DESC_MIN}–{DESC_MAX}).")
    else:
        total += _add(CHECK_DESC_LEN, W_DESC_LEN, 0, STATUS_FAIL,
                      f"طول الوصف {desc_len} حرفًا (النطاق {DESC_MIN}–{DESC_MAX}).")
        if desc_len < DESC_MIN:
            issue = f"الوصف قصير ({desc_len} حرفًا — أقل من {DESC_MIN})."
            advice = "وسّع الوصف إلى 150 حرفًا على الأقل بملخص القصة ودعوة لطيفة."
        else:
            issue = f"الوصف طويل ({desc_len} حرفًا — أكثر من {DESC_MAX})."
            advice = "اختصر الوصف إلى 400 حرف على الأكثر مع إبقاء الهوك والدعوة."
        suggestions.append(_suggestion(CHECK_DESC_LEN, issue, advice,
                                       PRIORITY_MEDIUM, W_DESC_LEN, 4))

    # 5. عدد الوسوم 5–15 — 10.
    tags_count = len(tags)
    if TAGS_MIN <= tags_count <= TAGS_MAX:
        total += _add(CHECK_TAGS_COUNT, W_TAGS_COUNT, W_TAGS_COUNT,
                      STATUS_PASS,
                      f"عدد الوسوم {tags_count} (النطاق {TAGS_MIN}–{TAGS_MAX}).")
    else:
        total += _add(CHECK_TAGS_COUNT, W_TAGS_COUNT, 0, STATUS_FAIL,
                      f"عدد الوسوم {tags_count} (النطاق {TAGS_MIN}–{TAGS_MAX}).")
        if tags_count < TAGS_MIN:
            issue = f"وسوم قليلة ({tags_count} — أقل من {TAGS_MIN})."
            advice = "أضف وسومًا حتى 5 على الأقل من كلمات العنوان والكلمة المستهدفة."
        else:
            issue = f"وسوم كثيرة ({tags_count} — أكثر من {TAGS_MAX})."
            advice = "احذف الوسوم الأبعد صلة حتى 15 وسمًا على الأكثر."
        suggestions.append(_suggestion(CHECK_TAGS_COUNT, issue, advice,
                                       PRIORITY_MEDIUM, W_TAGS_COUNT, 5))

    # 6. صلة الوسوم بالعنوان/الكلمة — 15 (نسبة × 15).
    title_words = _tokens(title)
    if has_keyword:
        title_words |= set(_keyword_tokens(keyword))
    if tags:
        relevant = sum(1 for tag in tags if _tokens(tag) & title_words)
        ratio = relevant / len(tags)
        rel_score = round(W_TAGS_RELEVANCE * ratio, 1)
        if ratio == 1.0:
            total += _add(CHECK_TAGS_RELEVANCE, W_TAGS_RELEVANCE, rel_score,
                          STATUS_PASS,
                          f"كل الوسوم ({relevant}/{len(tags)}) صلتها بالعنوان/الكلمة.")
        else:
            total += _add(CHECK_TAGS_RELEVANCE, W_TAGS_RELEVANCE, rel_score,
                          STATUS_FAIL,
                          f"وسوم صلتها بالعنوان/الكلمة {relevant}/{len(tags)} فقط.")
            suggestions.append(_suggestion(
                CHECK_TAGS_RELEVANCE,
                f"وسوم صلتها بالعنوان/الكلمة {relevant}/{len(tags)} فقط.",
                "استبدل الوسوم البعيدة بوسوم من كلمات العنوان أو الكلمة المستهدفة.",
                PRIORITY_HIGH if ratio == 0 else PRIORITY_MEDIUM,
                W_TAGS_RELEVANCE, 6))
    else:
        total += _add(CHECK_TAGS_RELEVANCE, W_TAGS_RELEVANCE, 0, STATUS_FAIL,
                      "بلا وسوم — لا صلة تُقاس.")
        suggestions.append(_suggestion(
            CHECK_TAGS_RELEVANCE, "بلا وسوم — لا صلة تُقاس.",
            "أضف وسومًا من كلمات العنوان والكلمة المستهدفة.",
            PRIORITY_HIGH, W_TAGS_RELEVANCE, 6))

    # 7. هوك في أول سطر من الوصف — 10.
    first_line = description.splitlines()[0].strip() if description else ""
    first_norm = _normalize(first_line)
    has_hook = ("؟" in first_line or "?" in first_line
                or any(word in first_norm for word in _HOOK_WORDS))
    if has_hook:
        total += _add(CHECK_HOOK, W_HOOK, W_HOOK, STATUS_PASS,
                      "أول سطر فيه هوك (سؤال أو كلمة هوك).")
    else:
        total += _add(CHECK_HOOK, W_HOOK, 0, STATUS_FAIL,
                      "أول سطر بلا هوك (لا سؤال ولا كلمة هوك).")
        suggestions.append(_suggestion(
            CHECK_HOOK, "أول سطر بلا هوك.",
            "ابدأ الوصف بسؤال أو بـ«تخيل/اسمع/قصة» لجذب القارئ من أول سطر.",
            PRIORITY_HIGH, W_HOOK, 7))

    # 8. دعوة لطيفة في الوصف — 10.
    desc_norm = _normalize(description)
    found_cta = next((phrase for phrase in _CTA_PHRASES
                      if phrase in desc_norm), None)
    if found_cta:
        total += _add(CHECK_CTA, W_CTA, W_CTA, STATUS_PASS,
                      f"دعوة لطيفة حاضرة («{found_cta}»).")
    else:
        total += _add(CHECK_CTA, W_CTA, 0, STATUS_FAIL,
                      "بلا دعوة لطيفة في الوصف.")
        suggestions.append(_suggestion(
            CHECK_CTA, "بلا دعوة لطيفة في الوصف.",
            "أضف دعوة لطيفة واحدة («انتظر الجزء الثاني» أو «اشترك» أو «تابعنا») — بلا بوابة متابعة.",
            PRIORITY_LOW, W_CTA, 8))

    # 9. المدة في نطاق الشورت 40–60ث إن أُعطيت — 10.
    if duration is None:
        total += _add(CHECK_DURATION, W_DURATION, 0, STATUS_UNMEASURED,
                      "غير مقاس — بلا مدة.")
        suggestions.append(_suggestion(
            CHECK_DURATION, "بلا مدة — نطاق الشورت غير مقاس.",
            "أضف مدة الفيديو بالثواني ليُقاس نطاق الشورت (40–60 ثانية).",
            PRIORITY_LOW, W_DURATION, 9))
    elif SHORT_MIN <= duration <= SHORT_MAX:
        total += _add(CHECK_DURATION, W_DURATION, W_DURATION, STATUS_PASS,
                      f"المدة {duration:g} ثانية (نطاق الشورت {SHORT_MIN}–{SHORT_MAX}).")
    else:
        total += _add(CHECK_DURATION, W_DURATION, 0, STATUS_FAIL,
                      f"المدة {duration:g} ثانية (نطاق الشورت {SHORT_MIN}–{SHORT_MAX}).")
        suggestions.append(_suggestion(
            CHECK_DURATION,
            f"المدة {duration:g} ثانية — خارج نطاق الشورت ({SHORT_MIN}–{SHORT_MAX}).",
            "اجعل مدة الفيديو بين 40 و60 ثانية.",
            PRIORITY_MEDIUM, W_DURATION, 9))

    # 10. رابط موجود بصيغة سليمة — 5.
    if not url:
        total += _add(CHECK_URL, W_URL, 0, STATUS_FAIL,
                      "بلا رابط.")
        suggestions.append(_suggestion(
            CHECK_URL, "بلا رابط.",
            "أضف رابط الصفحة/الفيديو بصيغة سليمة (https://...).",
            PRIORITY_LOW, W_URL, 10))
    elif _URL_RE.match(url):
        total += _add(CHECK_URL, W_URL, W_URL, STATUS_PASS,
                      "رابط موجود بصيغة سليمة.")
    else:
        total += _add(CHECK_URL, W_URL, 0, STATUS_FAIL,
                      "الرابط بصيغة غير سليمة.")
        suggestions.append(_suggestion(
            CHECK_URL, "الرابط بصيغة غير سليمة.",
            "صحّح الرابط إلى صيغة سليمة (https:// + اسم مضيف).",
            PRIORITY_MEDIUM, W_URL, 10))

    score = round(total, 1)
    suggestions.sort(key=lambda s: (_PRIORITY_RANK[s["priority"]],
                                    -s["_weight"], s["_order"]))
    for item in suggestions:
        del item["_weight"]
        del item["_order"]

    return {
        "title": title,
        "description": description,
        "tags": tags,
        "url": url,
        "duration": duration,
        "keyword": keyword,
        "score": score,
        "grade": grade_score(score),
        "checks": checks,
        "suggestions": suggestions,
        "keyword_measured": has_keyword,
        "duration_measured": duration is not None,
    }


def load_page_json(text):
    """اقرأ مدخل JSON نصيًا إلى صفحة منظّفة.

    يرفع ``ValueError`` عربيًا عند JSON تالف أو مدخل ليس
    قاموسًا أو صفحة فاسدة — بلا أي كتابة.
    """
    if not isinstance(text, str):
        raise ValueError("مدخل JSON يجب أن يكون نصًا.")
    try:
        data = json.loads(text)
    except ValueError:
        raise ValueError("مدخل JSON تالف — أعطِ صفحة JSON صالحة.")
    if not isinstance(data, dict):
        raise ValueError("مدخل الصفحة يجب أن يكون قاموسًا.")
    return _clean_page(data)


def to_json(result):
    """سلسل نتيجة ``analyze_page`` إلى JSON عربي (بلا ASCII هارب)."""
    if not isinstance(result, dict):
        raise ValueError("نتيجة المحلّل يجب أن تكون قاموسًا من analyze_page.")
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def format_report(result):
    """نسّق نتيجة ``analyze_page`` تقريرًا عربيًا.

    يحوي الدرجة والتقدير والفحوصات العشرة والاقتراحات
    مرتبة بالأولوية، وسطرًا يذكّر أن «غير مقاس» تعني غياب
    البيانات لا فشل المحتوى، وسطر التكامل مع فحصي ما قبل
    النشر.
    """
    if not isinstance(result, dict):
        raise ValueError("نتيجة المحلّل يجب أن تكون قاموسًا من analyze_page.")
    for key in ("title", "score", "grade", "checks", "suggestions"):
        if key not in result:
            raise ValueError(f"نتيجة المحلّل ناقصة — ينقصها «{key}».")
    checks = result["checks"]
    suggestions = result["suggestions"]
    mark = {STATUS_PASS: "✓", STATUS_FAIL: "✗",
            STATUS_UNMEASURED: "؟"}
    lines = ["محلّل الصفحة — تقرير Page Analyzer",
             "=================================",
             f"العنوان: «{result['title']}»",
             f"الدرجة: {result['score']}/100 — التقدير: {result['grade']}"]
    if result.get("keyword"):
        lines.append(f"الكلمة المستهدفة: «{result['keyword']}»")
    if result.get("duration") is not None:
        lines.append(f"المدة: {result['duration']:g} ثانية")
    lines.append("")
    lines.append("الفحوصات:")
    for entry in checks:
        lines.append(f"{mark.get(entry['status'], '؟')} {entry['check']}: "
                     f"{entry['score']}/{entry['weight']} "
                     f"[{entry['status']}] — {entry['detail']}")
    lines.append("")
    lines.append(f"الاقتراحات مرتبة بالأولوية ({len(suggestions)}):")
    if not suggestions:
        lines.append("لا اقتراحات — الصفحة ممتازة في كل الفحوصات.")
    for i, item in enumerate(suggestions, 1):
        lines.append(f"{i}. [{item['priority']}] {item['check']}: {item['issue']}")
        lines.append(f"   ← {item['suggestion']}")
    lines.append("")
    lines.append("ملاحظة: «غير مقاس» تعني غياب البيانات (كلمة أو مدة "
                 "لم تُزوَّد)، لا فشل المحتوى — زوّدها ليُقاس الفحص.")
    lines.append("تكامل: هذا تحليل شامل للصفحة ككل؛ أما فحصا ما قبل "
                 "النشر (seo_check وtitle_lint) فيفحصان أول سطرين من "
                 "الوصف وحدود الوسوم/العنوان عند التجهيز.")
    return "\n".join(lines)
