#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""مدقق العنوان + المصغرة كوحدة واحدة — `title-lint` (جولة v0.1.57، W2).

يطبّق قائمة فحص yt-package ككود، من الفكرة فقط (بلا نسخ كود):

- العنوان والمصغرة وحدة واحدة: المصغرة تكرر العنوان سبب فشل
  نصف سطح النقر — فالمصغرة كلمات مختلفة، نفس الوعد.
- القطع: 60 حرفًا حيث يقطع بحث سطح المكتب، و40 في خلاصة
  الموبايل — ويُبلَّغ عن القطعين لأن فشلهما مختلف (قطع سطح
  المكتب يفقد الذيل، وقطع الموبايل قد يفقد الموضوع نفسه).
- نص المصغرة 3 كلمات كحد أقصى — الرابعة لطخة رمادية بحجم
  الخلاصة.
- رقم أو اسم أو تاريخ يغلب أي صفة (عنصر ملموس).
- كلمتان بأحرف كبيرة هما السقف قبل أن يُقرأ العنوان كسبام.

حتمي بلا شبكة وبلا LLM، بالمكتبة القياسية فقط، عربي أولًا.

ملاحظات منهجية موثقة:

- «كلمات المحتوى» هي كلمات العنوان/المصغرة بعد إزالة كلمات
  التوقف النحوية (حروف جر وضمائر وأسماء إشارة وموصولات —
  ``STOP_WORDS``). المقارنة بعد تطبيع بسيط (إزالة التشكيل،
  توحيد أشكال الألف، ``ى`` ← ``ي``، ``ة`` ← ``ه``، وإسقاط
  البادئة ``ال``/``وال``) حتى تطابق «النجار» و«نجار» الكلمة
  نفسها؛ وتُذكر الكلمات المشتركة بصيغتها الأصلية من العنوان.
- «الاسم العلم» يُكتشف إرشاديًا بطريقتين فقط: كلمة تلي
  ``بن``/``ابن``/``بنت``/``أبو``/``أم``، أو كلمة في قائمة
  ``KNOWN_NAMES`` الصغيرة الموثقة أدناه. ليست هذه قائمة أسماء
  شاملة — اسم غير مذكور هنا لا يُكتشف، ويُذكر ذلك في التقرير
  كغياب عنصر ملموس لا كحكم نهائي على العنوان.
- «المكان المحدد» قائمة أماكن صغيرة موثقة (``KNOWN_PLACES``).
- «الغموض»: كل كلمات محتوى العنوان من قائمة ``GENERIC_WORDS``
  الصغيرة الموثقة أدناه، ولا عنصر ملموس (لا اسم ولا رقم ولا
  مكان). كلمة خارج القائمة — مثل «منقشة» أو «رغيف» — تنفي
  الغموض لأنها تحدد الموضوع.
- «الأحرف الكبيرة» تُحسب للكلمات اللاتينية فقط، لأن العربية
  بلا حالة أحرف.
"""
import re

DESKTOP_LIMIT = 60
MOBILE_LIMIT = 40
MAX_THUMB_WORDS = 3
MAX_CAPS_WORDS = 2
MAX_EXCLAMATIONS = 2

# كلمات التوقف النحوية العربية — تُستبعد من مقارنة التكرار
# ومن حساب الغموض (ليست كلمات محتوى).
STOP_WORDS = frozenset({
    "من", "في", "الى", "إلى", "إلي", "على", "عن", "مع", "بعد", "قبل",
    "عند", "بين", "أن", "إن", "ما", "لا", "لم", "لن", "هو", "هي",
    "هذا", "هذه", "ذلك", "تلك", "كان", "كانت", "قد", "لقد", "كل",
    "أي", "الذي", "التي", "الذين", "أو", "ثم", "لكن", "غير", "نحو",
    "حتى", "كما", "لو", "إذا", "اما", "إما", "دون", "ضد", "حيث",
    "لدى", "ذو", "ذات",
})

# كلمات عامة: صيغة القناة وصفات وأدوار عامة بلا تحديد.
# عنوان كل كلمات محتواه من هذه القائمة (وبلا عنصر ملموس)
# عنوان غامض.
GENERIC_WORDS = frozenset({
    # صيغة القناة
    "قصة", "حقيقية", "حقيقيه", "الجزء", "جزء",
    # صفات عامة
    "مؤثرة", "مؤثر", "جميلة", "جميل", "رائعة", "رائع", "عجيبة",
    "عجيب", "غريبة", "غريب", "حزينة", "حزين", "مبكية", "مبكي",
    "مدهشة", "مدهش", "صادمة", "صادم", "جدا", "جدًا", "قوية",
    "قوي", "أجمل", "أفضل", "أعظم", "أمين", "امين", "صادق",
    "مخلص", "كريم", "شجاع", "حكيم", "عادل", "ظالم", "بخيل",
    "طيب",
    # عبرة/درس عام
    "عبرة", "درس", "موعظة", "حكمة", "عظة",
    # أدوار عامة بلا اسم
    "رجل", "امرأة", "امراه", "شاب", "فتاة", "فتاه", "طفل", "طفلة",
    "طفله", "جار", "صديق", "صديقة", "صديقه", "فقير", "غني",
    "تاجر", "نجار", "حداد", "خباز", "صياد", "مزارع", "معلم",
    "طبيب", "ملك", "أمير", "وزير", "شيخ", "عجوز", "أم", "أب",
    "ابن", "بنت", "زوج", "زوجة", "زوجه", "أخ", "أخت",
})

# كلمات عددية عربية (مفردة ومضافة إليها «ال») — عنصر ملموس.
NUMBER_WORDS = frozenset({
    "واحد", "واحدة", "واحده", "اثنان", "اثنين", "اثنتان", "اثنتين",
    "ثلاثة", "ثلاثه", "ثلاث", "أربعة", "أربعه", "أربع",
    "خمسة", "خمسه", "خمس", "ستة", "سته", "ست",
    "سبعة", "سبعه", "سبع", "ثمانية", "ثمانيه", "ثمان",
    "تسعة", "تسعه", "تسع", "عشرة", "عشره", "عشر",
    "عشرون", "ثلاثون", "أربعون", "خمسون", "ستون", "سبعون",
    "ثمانون", "تسعون", "مئة", "مائة", "مائه", "ألف", "ألفان",
    "ألفين", "مليون", "مليار",
    "أول", "الأول", "الاول", "ثاني", "الثاني", "ثالث", "الثالث",
    "رابع", "الرابع", "خامس", "الخامس", "سادس", "السادس",
    "سابع", "السابع", "ثامن", "الثامن", "تاسع", "التاسع",
    "عاشر", "العاشر",
})

# أسماء علم شائعة في قصص القناة — قائمة صغيرة موثقة، ليست شاملة.
KNOWN_NAMES = frozenset({
    "كعب", "مالك", "عائشة", "عائشه", "يوسف", "أحمد", "احمد",
    "محمد", "علي", "عمر", "خالد", "سارة", "ساره", "فاطمة",
    "فاطمه", "مريم", "زينب", "حسن", "حسين", "إبراهيم",
    "ابراهيم", "موسى", "موسي", "عيسى", "عيسي", "داود",
    "سليمان", "بلال", "حمزة", "حمزه", "طلحة", "طلحه",
    "الزبير", "سعد", "سعيد", "عبد", "الله", "عبدالله",
    "الرحمن", "عبدالرحمن", "أبو", "أبوبكر", "بكر", "عثمان",
    "جعفر", "مصعب", "عمار", "ياسر", "سمية", "سميه", "خديجة",
    "خديجه", "آسية", "آسيه", "هاجر", "آدم", "نوح", "إدريس",
    "ادريس", "هود", "صالح", "شعيب", "لوط", "يعقوب", "أيوب",
    "ايوب", "يونس", "زكريا", "يحيى", "يحيي", "إسحاق", "اسحاق",
    "إسماعيل", "اسماعيل", "هارون", "قارون", "فرعون", "هامان",
})

# أماكن محددة شائعة في القصص — قائمة صغيرة موثقة، ليست شاملة.
KNOWN_PLACES = frozenset({
    "مكة", "مكه", "المدينة", "المدينه", "بغداد", "القاهرة",
    "القاهره", "دمشق", "اليمن", "مصر", "الشام", "فلسطين",
    "الأندلس", "الاندلس", "الكوفة", "الكوفه", "البصرة",
    "البصره", "خراسان", "بخارى", "بخاري", "القدس", "غزة",
    "غزه", "حلب", "الموصل", "طرابلس", "تونس", "الجزائر",
    "المغرب", "السودان", "العراق", "الحجاز", "نجد",
})

# بادئات قرابة: الكلمة بعدها اسم علم (مثل «كعب بن مالك»).
_KINSHIP_PREFIXES = frozenset({"بن", "ابن", "بنت", "أبو", "ابو", "أم", "ام"})

_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_TOKEN_RE = re.compile(r"[\w" + _ARABIC_DIGITS + r"]+", re.UNICODE)
_CAPS_WORD_RE = re.compile(r"\b[A-Z]{2,}\b")
_DIGIT_RE = re.compile(r"[0-9" + _ARABIC_DIGITS + r"]+")

_TASHKEEL = re.compile(r"[\u064b-\u0652\u0670\u0640]")


def _normalize(word):
    """تطبيع بسيط للمقارنة: بلا تشكيل، ألف موحدة، ى←ي، ة←ه، بلا «ال»."""
    word = _TASHKEEL.sub("", word)
    word = word.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    word = word.replace("ى", "ي").replace("ة", "ه")
    if word.startswith("وال"):
        word = word[3:]
    elif word.startswith("ال"):
        word = word[2:]
    elif word.startswith("و") and len(word) > 2:
        word = word[1:]
    return word


# نسخ مطبَّعة من القوائم — المقارنة دائمًا بالصيغة المطبَّعة
# (مثلًا «مؤثرة» في القائمة تطابق «مؤثره» بعد التطبيع).
_STOP_NORM = frozenset(_normalize(w) for w in STOP_WORDS)
_GENERIC_NORM = frozenset(_normalize(w) for w in GENERIC_WORDS)
_NUMBER_NORM = frozenset(_normalize(w) for w in NUMBER_WORDS)
_NAMES_NORM = frozenset(_normalize(w) for w in KNOWN_NAMES)
_PLACES_NORM = frozenset(_normalize(w) for w in KNOWN_PLACES)
_KINSHIP_NORM = frozenset(_normalize(w) for w in _KINSHIP_PREFIXES)


def _tokens(text):
    """كلمات النص (حروف وأرقام عربية/لاتينية)، بلا علامات ترقيم.

    يُزال التشكيل أولًا حتى لا يقسّم التنوين كلمة مثل «جدًا».
    """
    return _TOKEN_RE.findall(_TASHKEEL.sub("", text))


def _content_words(text):
    """كلمات المحتوى: الكلمات بعد إزالة كلمات التوقف.

    ترجع قائمة أزواج (الأصلية، المطبَّعة) محافظة على الترتيب.
    الأرقام كلمات محتوى (تكرار رقم الجزء تكرار).
    """
    out = []
    for tok in _tokens(text):
        norm = _normalize(tok)
        if not norm:
            continue
        if norm in _STOP_NORM:
            continue
        out.append((tok, norm))
    return out


def _cut(text, limit):
    """قطع عند حدّ: (يُقطع؟، الظاهر، المخفي)."""
    if len(text) <= limit:
        return False, text, ""
    return True, text[:limit], text[limit:]


def _find_concrete(title):
    """العناصر الملموسة في العنوان: أرقام وكلمات عددية وأسماء وأماكن.

    ترجع قائمة أوصاف عربية مثل «رقم: 1» و«اسم: مالك».
    """
    found = []
    tokens = _tokens(title)
    for tok in tokens:
        if _DIGIT_RE.search(tok):
            found.append("رقم: %s" % tok)
    norms = [_normalize(t) for t in tokens]
    for tok, norm in zip(tokens, norms):
        if norm in _NUMBER_NORM:
            found.append("كلمة عددية: %s" % tok)
    for i, (tok, norm) in enumerate(zip(tokens, norms)):
        if i > 0 and _normalize(tokens[i - 1]) in _KINSHIP_NORM:
            found.append("اسم: %s" % tok)
        elif norm in _NAMES_NORM:
            found.append("اسم: %s" % tok)
        elif norm in _PLACES_NORM:
            found.append("مكان: %s" % tok)
    # إزالة التكرار مع حفظ الترتيب.
    seen = set()
    unique = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _is_vague(title, concrete):
    """غامض؟ كل كلمات المحتوى عامة ولا عنصر ملموس."""
    if concrete:
        return False
    words = _content_words(title)
    if not words:
        return True
    for _tok, norm in words:
        if norm not in _GENERIC_NORM:
            return False
    return True


def lint_title(title, thumb_text=None):
    """افحص عنوانًا ومصغرة كوحدة واحدة.

    ``title``: نص العنوان (فارغ → ``ValueError`` عربي).
    ``thumb_text``: نص المصغرة اختياري (``None`` = بلا مصغرة).

    يرجع تقريرًا قاموسيًا فيه: الطول، وموضعا القطع (60/40)،
    وتكرار المصغرة للعنوان، وعدد كلمات المصغرة، والعنصر
    الملموس، وإشارات السبام، والغموض، وقائمة المشكلات
    وعددها، وعلامة ``ok``.
    """
    if not isinstance(title, str):
        raise TypeError("العنوان يجب أن يكون نصًا.")
    title = title.strip()
    if not title:
        raise ValueError("العنوان فارغ — اكتب عنوانًا قبل الفحص.")
    if thumb_text is not None and not isinstance(thumb_text, str):
        raise TypeError("نص المصغرة يجب أن يكون نصًا أو None.")
    thumb_text = (thumb_text or "").strip()

    length = len(title)
    desktop_trunc, desktop_visible, desktop_hidden = _cut(title, DESKTOP_LIMIT)
    mobile_trunc, mobile_visible, mobile_hidden = _cut(title, MOBILE_LIMIT)

    title_words = _content_words(title)
    title_norms = {norm: tok for tok, norm in title_words}
    overlap = []
    thumb_word_count = 0
    if thumb_text:
        thumb_word_count = len(_tokens(thumb_text))
        for tok, norm in _content_words(thumb_text):
            if norm in title_norms and title_norms[norm] not in overlap:
                overlap.append(title_norms[norm])

    concrete = _find_concrete(title)
    vague = _is_vague(title, concrete)

    caps_words = _CAPS_WORD_RE.findall(title)
    exclamations = title.count("!")
    is_spammy = len(caps_words) > MAX_CAPS_WORDS or exclamations > MAX_EXCLAMATIONS

    issues = []
    if desktop_trunc:
        issues.append({
            "code": "TITLE-CUT-060",
            "severity": "medium",
            "message": ("يُقطع في بحث سطح المكتب عند 60 حرفًا — "
                        "يُفقد الذيل: «%s»" % desktop_hidden),
        })
    if mobile_trunc:
        issues.append({
            "code": "TITLE-CUT-040",
            "severity": "high",
            "message": ("يُقطع في خلاصة الموبايل عند 40 حرفًا — "
                        "قد يُفقد الموضوع: «%s»" % mobile_hidden),
        })
    if overlap:
        issues.append({
            "code": "THUMB-REPEAT",
            "severity": "high",
            "message": ("المصغرة تكرر العنوان — كلمات مشتركة: %s"
                        % "، ".join(overlap)),
        })
    if thumb_text and thumb_word_count > MAX_THUMB_WORDS:
        issues.append({
            "code": "THUMB-WORDS",
            "severity": "medium",
            "message": ("نص المصغرة %d كلمات — فوق الحد (3)؛ "
                        "الرابعة لطخة رمادية بحجم الخلاصة"
                        % thumb_word_count),
        })
    if not concrete:
        issues.append({
            "code": "TITLE-NO-CONCRETE",
            "severity": "low",
            "message": ("لا عنصر ملموس (رقم أو اسم أو مكان) — "
                        "أضف رقمًا أو اسمًا أو تاريخًا يغلب الصفة"),
        })
    if is_spammy:
        detail = []
        if len(caps_words) > MAX_CAPS_WORDS:
            detail.append("كلمات بأحرف كبيرة: %s" % "، ".join(caps_words))
        if exclamations > MAX_EXCLAMATIONS:
            detail.append("علامات تعجب: %d" % exclamations)
        issues.append({
            "code": "TITLE-SPAM",
            "severity": "high",
            "message": "يُقرأ كسبام — " + "؛ ".join(detail),
        })
    if vague:
        issues.append({
            "code": "TITLE-VAGUE",
            "severity": "medium",
            "message": ("عنوان غامض: كلمات عامة فقط بلا اسم أو رقم "
                        "أو مكان محدد"),
        })

    return {
        "title": title,
        "thumb_text": thumb_text or None,
        "length": length,
        "desktop_cut": {
            "limit": DESKTOP_LIMIT,
            "truncated": desktop_trunc,
            "visible": desktop_visible,
            "hidden": desktop_hidden,
        },
        "mobile_cut": {
            "limit": MOBILE_LIMIT,
            "truncated": mobile_trunc,
            "visible": mobile_visible,
            "hidden": mobile_hidden,
        },
        "thumb_overlap": {
            "words": overlap,
            "count": len(overlap),
            "repeats": bool(overlap),
        },
        "thumb_words": thumb_word_count,
        "thumb_too_long": thumb_word_count > MAX_THUMB_WORDS,
        "concrete": {
            "found": concrete,
            "has_concrete": bool(concrete),
            "note": ("العنصر الملموس: %s" % "، ".join(concrete)
                     if concrete else
                     "لا يوجد عنصر ملموس (رقم أو اسم أو مكان محدد)"),
        },
        "spam": {
            "caps_words": caps_words,
            "exclamations": exclamations,
            "is_spammy": is_spammy,
        },
        "vague": vague,
        "issues": issues,
        "issue_count": len(issues),
        "ok": not issues,
    }


def rank_titles(titles, thumb_text=None):
    """رتّب قائمة عناوين بالأقل مشكلات (الأفضل أولًا).

    ترجع قائمة تقارير ``lint_title`` مرتبة بعدد المشكلات
    تصاعديًا؛ التعادل يحفظ ترتيب الإدخال. عنوان فارغ في
    القائمة يرفع ``ValueError`` كما في ``lint_title``.
    """
    reports = [lint_title(t, thumb_text) for t in titles]
    reports.sort(key=lambda r: r["issue_count"])
    return reports


def format_report(report):
    """نص عربي من تقرير ``lint_title``."""
    lines = []
    lines.append("العنوان: %s" % report["title"])
    lines.append("الطول: %d حرفًا" % report["length"])
    for key, label in (("desktop_cut", "بحث سطح المكتب (60)"),
                       ("mobile_cut", "خلاصة الموبايل (40)")):
        cut = report[key]
        if cut["truncated"]:
            lines.append("%s: يُقطع — الظاهر: «%s» | المخفي: «%s»"
                         % (label, cut["visible"], cut["hidden"]))
        else:
            lines.append("%s: لا يُقطع" % label)
    if report["thumb_text"]:
        lines.append("نص المصغرة: «%s» (%d كلمات)"
                     % (report["thumb_text"], report["thumb_words"]))
        overlap = report["thumb_overlap"]["words"]
        if overlap:
            lines.append("المصغرة تكرر العنوان: %s" % "، ".join(overlap))
        else:
            lines.append("المصغرة لا تكرر العنوان")
        if report["thumb_too_long"]:
            lines.append("نص المصغرة فوق الحد (3 كلمات)")
    else:
        lines.append("بلا نص مصغرة")
    lines.append(report["concrete"]["note"])
    if report["spam"]["is_spammy"]:
        lines.append("إشارة سبام: كلمات كبيرة: %s؛ علامات تعجب: %d"
                     % ("، ".join(report["spam"]["caps_words"]) or "لا شيء",
                        report["spam"]["exclamations"]))
    if report["vague"]:
        lines.append("العنوان غامض: كلمات عامة فقط")
    if report["issues"]:
        lines.append("المشكلات (%d):" % report["issue_count"])
        for issue in report["issues"]:
            lines.append("- [%s] %s" % (issue["code"], issue["message"]))
    else:
        lines.append("لا مشكلات — العنوان والمصغرة وحدة واحدة سليمة")
    return "\n".join(lines)
