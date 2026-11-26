#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""أمر فحص SEO قبل النشر — `lib/seo_check.py` (الجولة v0.1.57، W1).

يطبّق قائمة فحص yt-seo ككود — من الفكرة فقط، بلا نسخ كود
من أي مشروع. بايثون بالمكتبة القياسية فقط، حتمي بلا شبكة
وبلا LLM وبلا عشوائية. لا شيء يُنشر من هنا — فحص وتقرير فقط.

القواعد:
- أول سطرين من الوصف هما ما يُقرأ (مقتطف البحث): يجب أن
  يكونا غير فارغين وأن يحملا الوعد (يذكران موضوع الفيديو
  أو كلمة وعد)، وبلا بوابة متابعة/تعليق — يُعاد استخدام
  `lib.caption_check.sentence_issue` — والطول ≤ 400 حرف
  (حد `lib.publish_meta.MAX_DESCRIPTION_CHARS`).
- الوسوم إشارة ضعيفة — للتوضيح فقط: ≤ 15 وسمًا، والمجموع
  ≤ 500 حرف (حد `lib.publish_meta.YT_TAGS_LIMIT`)، وبلا
  تكرار، وبلا حشو غير ذي صلة (كلمات الوسم تقارَن بكلمات
  العنوان/القصة، ما عدا الوسوم العامة الثابتة للصفحة).
- العنوان ≤ 100 حرف (حد `lib.publish_meta.YT_TITLE_LIMIT`).
- اختبار الاستعلام: 3 استعلامات بحث مشتقة حتميًا من كلمات
  العنوان/القصة، ويُتحقَّق أن كلمات كل استعلام موجودة في
  العنوان أو أول سطرين من الوصف؛ وإن غابت عن العنوان
  فالمشكلة في العنوان لا الوصف.
- التطبيع العربي للمطابقة: أ/إ/آ ← ا، ة ← ه، ى ← ي، مع
  إزالة التشكيل والتطويل.

`check_seo(title, description, tags, story_text=None)` ترجع
تقريرًا قاموسيًا؛ و`format_report(report)` نص عربي؛ و
`to_json_dict(report)` نسخة جاهزة لـ JSON. "ok" صحيحة
عندما لا توجد مخالفات صلبة؛ و"notes" ملاحظات إرشادية
(مثل غياب استعلام عن العنوان مع وجوده في الوصف) لا
تمنع النشر.
"""
import json
import re

from lib import caption_check
from lib import publish_meta

TITLE_LIMIT = publish_meta.YT_TITLE_LIMIT
TAGS_LIMIT = publish_meta.YT_TAGS_LIMIT
DESCRIPTION_LIMIT = publish_meta.MAX_DESCRIPTION_CHARS
MAX_TAGS = 15

_ARABIC_NORM = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا",
                               "ة": "ه", "ى": "ي"})
_DIACRITICS_RE = re.compile(r"[\u064b-\u0652\u0670\u0640]")
_WORD_RE = re.compile(r"[\w\u0600-\u06ff]+")

# كلمات وظيفية لا تصلح نواة استعلام بحث.
_STOPWORDS = frozenset([
    "الجزء", "جزء", "من", "في", "على", "الى", "عن", "ما", "لا",
    "او", "ثم", "بعد", "قبل", "مع", "بين", "هذا", "هذه", "ذلك",
    "تلك", "كان", "كانت", "هو", "هي", "ان", "انه", "انها", "قصه",
    "حقيقيه", "قصص", "و", "يا", "ل", "ب", "ك",
])

# كلمات وعد (إرشادية): وجود إحداها في أول سطرين يعني أن
# المقتطف يعِد القارئ بشيء — لا أنها تضمن النقر.
_PROMISE_WORDS = frozenset([
    "النهايه", "اغرب", "مفاجاه", "سر", "هتعرف", "هتشوف", "شوف",
    "اسمع", "ظلم", "عوض", "توبه", "امانه", "صبر", "خيانه",
    "غدر", "ندم", "فرج", "عجيب", "مدهش",
])

# استعلامات عامة احتياطية — تُستخدم فقط إن لم تكفِ كلمات
# العنوان/القصة لاشتقاق 3 استعلامات مميزة.
_FALLBACK_QUERIES = ("قصص وعبر", "قصص موثره")


def normalize_arabic(text):
    """طبّع نصًا عربيًا للمطابقة: أ/إ/آ ← ا، ة ← ه، ى ← ي،
    بلا تشكيل ولا تطويل."""
    text = (text or "").translate(_ARABIC_NORM)
    return _DIACRITICS_RE.sub("", text)


def words(text):
    """كلمات نص مطبّعة (عربية/لاتينية/أرقام)، بالترتيب."""
    return _WORD_RE.findall(normalize_arabic(text or "").lower())


def _content_words(text):
    """كلمات المحتوى: بلا كلمات وظيفية وبلا أرقام وبلا
    كلمات من حرف واحد — بالترتيب وبلا تكرار."""
    seen = []
    for word in words(text):
        if len(word) < 2 or word in _STOPWORDS or word.isdigit():
            continue
        if word not in seen:
            seen.append(word)
    return seen


def _clean_tag(tag):
    """نظّف وسمًا واحدًا للمقارنة: بلا #، و_ ← مسافة."""
    return re.sub(r"\s+", " ", (tag or "").lstrip("#")
                  .replace("_", " ").strip())


def _generic_tags():
    """الوسوم العامة الثابتة للصفحة — مطبّعة."""
    return {normalize_arabic(_clean_tag(t))
            for t in publish_meta.FIXED_TAGS}


def _validate(title, description, tags, story_text):
    """تحقق من المدخلات؛ ValueError عربي عند الفاسد."""
    if not isinstance(title, str):
        raise ValueError("العنوان يجب أن يكون نصًا")
    if not title.strip():
        raise ValueError("العنوان فارغ — أدخل عنوانًا غير فارغ")
    if not isinstance(description, str):
        raise ValueError("الوصف يجب أن يكون نصًا")
    if isinstance(tags, str):
        tags = [t for t in (tags.split(",") if tags else [])]
    elif isinstance(tags, (list, tuple)):
        tags = list(tags)
    else:
        raise ValueError(
            "الوسوم يجب أن تكون قائمة أو نصًا مفصولًا بفواصل")
    for tag in tags:
        if not isinstance(tag, str):
            raise ValueError("كل وسم يجب أن يكون نصًا")
    if story_text is not None and not isinstance(story_text, str):
        raise ValueError("نص القصة يجب أن يكون نصًا")
    return title.strip(), description, [_clean_tag(t) for t in tags
                                        if _clean_tag(t)], story_text


def _derive_queries(title, story_text):
    """اشتق 3 استعلامات بحث حتميًا من كلمات العنوان/القصة.

    1. نواة العنوان (أول 3 كلمات محتوى).
    2. «قصه حقيقيه» + أول كلمة من العنوان.
    3. «قصه» + أول كلمتين من القصة ليستا في العنوان،
       وإلا «قصه» + أول كلمتين من العنوان.
    الاستعلامات مطبّعة (للمطابقة)، ومميزة، و3 دائمًا.
    """
    title_words = _content_words(title)
    story_words = _content_words(story_text)
    story_only = [w for w in story_words if w not in title_words]
    queries = []
    first = " ".join(title_words[:3]) or "قصه حقيقيه"
    queries.append(first)
    queries.append(" ".join(["قصه", "حقيقيه"] + title_words[:1]))
    if story_only:
        queries.append(" ".join(["قصه"] + story_only[:2]))
    else:
        queries.append(" ".join(["قصه"] + title_words[:2])
                       or "قصص وعبر")
    out = []
    for query in queries:
        if query and query not in out:
            out.append(query)
    for fallback in _FALLBACK_QUERIES:
        if len(out) >= 3:
            break
        if fallback not in out:
            out.append(fallback)
    return out[:3]


def _test_queries(queries, title, first_two_lines):
    """اختبر كل استعلام: كلماته في العنوان؟ في أول سطرين؟

    النجاح = كل كلمة موجودة في العنوان أو أول سطرين معًا؛
    والغياب عن العنوان وحده يُسجَّل — فالمشكلة عندها في
    العنوان لا الوصف.
    """
    title_set = set(words(title))
    desc_set = set(words("\n".join(first_two_lines)))
    results = []
    for query in queries:
        qwords = words(query)
        missing_title = [w for w in qwords if w not in title_set]
        missing_desc = [w for w in qwords if w not in desc_set]
        missing_all = [w for w in qwords
                       if w not in title_set and w not in desc_set]
        results.append({
            "query": query,
            "words": qwords,
            "in_title": not missing_title,
            "in_description_first_two_lines": not missing_desc,
            "missing_in_title": missing_title,
            "missing_in_description": missing_desc,
            "missing_everywhere": missing_all,
            "passed": not missing_all,
        })
    return results


def _check_description(description, title_words, story_words):
    """افحص الوصف: أول سطرين + الوعد + البوابة + الطول."""
    lines = [ln.strip() for ln in (description or "").splitlines()
             if ln.strip()]
    first_two = lines[:2]
    first_two_words = set(words("\n".join(first_two)))
    topical = bool(first_two_words
                   & (set(title_words) | set(story_words)))
    promise = bool(first_two_words & _PROMISE_WORDS)
    carries_promise = bool(first_two) and (topical or promise)
    gate_issues = []
    for sentence in caption_check.split_sentences(description):
        found = caption_check.sentence_issue(sentence)
        if found is not None:
            category, reason = found
            gate_issues.append({"sentence": sentence,
                                "reason": reason,
                                "category": category})
    length = len(description or "")
    return {
        "first_two_lines": first_two,
        "first_two_lines_non_empty": bool(first_two),
        "carries_promise": carries_promise,
        "gate_issues": gate_issues,
        "has_gate": bool(gate_issues),
        "length": length,
        "length_limit": DESCRIPTION_LIMIT,
        "length_ok": length <= DESCRIPTION_LIMIT,
    }


def _check_tags(tags, title_words, story_words):
    """افحص الوسوم: العدد + المجموع + التكرار + الصلة."""
    generic = _generic_tags()
    topic = set(title_words) | set(story_words)
    normalized = [normalize_arabic(t) for t in tags]
    seen, duplicates = set(), []
    for tag in normalized:
        if tag in seen and tag not in duplicates:
            duplicates.append(tag)
        seen.add(tag)
    irrelevant = []
    for tag in tags:
        norm = normalize_arabic(tag)
        if norm in generic:
            continue
        if not (set(words(tag)) & topic):
            irrelevant.append(tag)
    total = len(",".join(tags))
    return {
        "tags": list(tags),
        "count": len(tags),
        "count_limit": MAX_TAGS,
        "count_ok": len(tags) <= MAX_TAGS,
        "total_chars": total,
        "total_chars_limit": TAGS_LIMIT,
        "total_chars_ok": total <= TAGS_LIMIT,
        "duplicates": duplicates,
        "has_duplicates": bool(duplicates),
        "irrelevant": irrelevant,
        "has_irrelevant": bool(irrelevant),
    }


def check_seo(title, description, tags, story_text=None):
    """افحص عنوانًا ووصفًا ووسومًا قبل النشر (فحص فقط).

    title نص غير فارغ؛ description نص (قد يكون فارغًا —
    يُسجَّل كفشل فحص لا خطأ إدخال)؛ tags قائمة نصوص أو
    نص مفصول بفواصل؛ story_text نص اختياري لاشتقاق
    الاستعلامات وفحص الصلة. يرجع تقريرًا قاموسيًا فيه
    "ok" و"issues" (رسائل عربية) وفحوص العنوان والوصف
    والوسوم والاستعلامات الثلاثة.
    """
    title, description, tags, story_text = _validate(
        title, description, tags, story_text)
    title_words = _content_words(title)
    story_words = _content_words(story_text)
    first_two = [ln.strip() for ln in description.splitlines()
                 if ln.strip()][:2]
    queries = _derive_queries(title, story_text)
    query_results = _test_queries(queries, title, first_two)
    desc = _check_description(description, title_words, story_words)
    tag_report = _check_tags(tags, title_words, story_words)
    title_length = len(title)
    title_ok = title_length <= TITLE_LIMIT

    issues = []
    notes = []
    if not title_ok:
        issues.append("العنوان أطول من %d حرفًا (%d حرفًا)"
                      % (TITLE_LIMIT, title_length))
    if not desc["first_two_lines_non_empty"]:
        issues.append("أول سطرين من الوصف فارغان — المقتطف "
                      "الذي يراه الباحث فارغ")
    elif not desc["carries_promise"]:
        issues.append("أول سطرين من الوصف لا يحملان وعدًا واضحًا "
                      "— لا يذكران موضوع الفيديو ولا ما يعطيه")
    for gate in desc["gate_issues"]:
        issues.append("الوصف يحوي جملة بوابة: «%s» (%s)"
                      % (gate["sentence"], gate["reason"]))
    if not desc["length_ok"]:
        issues.append("الوصف أطول من %d حرفًا (%d حرفًا)"
                      % (DESCRIPTION_LIMIT, desc["length"]))
    if not tag_report["count_ok"]:
        issues.append("الوسوم أكثر من %d (%d وسمًا)"
                      % (MAX_TAGS, tag_report["count"]))
    if not tag_report["total_chars_ok"]:
        issues.append("مجموع الوسوم أطول من %d حرفًا (%d حرفًا)"
                      % (TAGS_LIMIT, tag_report["total_chars"]))
    for dup in tag_report["duplicates"]:
        issues.append("وسم مكرر: «%s»" % dup)
    for tag in tag_report["irrelevant"]:
        issues.append("وسم غير ذي صلة بالعنوان/القصة: «%s»" % tag)
    for result in query_results:
        if not result["passed"]:
            issues.append("الاستعلام «%s» لا يفوز به الفيديو — "
                          "كلمة غير موجودة في العنوان ولا أول "
                          "سطرين: %s"
                          % (result["query"],
                             "، ".join(result["missing_everywhere"])))
        elif not result["in_title"]:
            # تشخيص فقط لا فشل: الاستعلام يُفاز به عبر الوصف،
            # لكن غيابه عن العنوان يعني أن الإصلاح — إن أُريد
            # تقوية — في العنوان لا الوصف.
            notes.append("الاستعلام «%s» غائب عن العنوان "
                         "(موجود في الوصف فقط) — المشكلة في "
                         "العنوان لا الوصف" % result["query"])

    return {
        "title": title,
        "title_length": title_length,
        "title_limit": TITLE_LIMIT,
        "title_ok": title_ok,
        "description": desc,
        "tags": tag_report,
        "queries": query_results,
        "ok": not issues,
        "issues": issues,
        "notes": notes,
    }


def to_json_dict(report):
    """نسخة من التقرير جاهزة لـ JSON (قابلة للتسلسل)."""
    return json.loads(json.dumps(report, ensure_ascii=False))


def format_report(report):
    """نص عربي يلخّص تقرير فحص SEO."""
    lines = ["تقرير فحص SEO — «%s»" % report["title"]]
    lines.append("النتيجة: %s"
                 % ("سليم — جاهز للنشر من ناحية SEO"
                    if report["ok"] else "فيه ملاحظات"))
    title_mark = "✓" if report["title_ok"] else "✗"
    lines.append("العنوان: %d / %d حرفًا %s"
                 % (report["title_length"], report["title_limit"],
                    title_mark))
    lines.append("الاستعلامات المستهدفة:")
    for i, result in enumerate(report["queries"], 1):
        mark = "✓" if result["passed"] else "✗"
        in_title = "في العنوان ✓" if result["in_title"] \
            else "غائب عن العنوان ✗"
        in_desc = "في أول سطرين ✓" \
            if result["in_description_first_two_lines"] \
            else "غائب عن أول سطرين ✗"
        lines.append("  %d. «%s» %s — %s، %s"
                     % (i, result["query"], mark, in_title, in_desc))
    desc = report["description"]
    lines.append("الوصف (أول سطرين):")
    if desc["first_two_lines"]:
        for line in desc["first_two_lines"]:
            lines.append("  «%s»" % line)
    else:
        lines.append("  (فارغ)")
    lines.append("  يحمل الوعد: %s — الطول: %d / %d حرفًا %s"
                 % ("نعم" if desc["carries_promise"] else "لا",
                    desc["length"], desc["length_limit"],
                    "✓" if desc["length_ok"] else "✗"))
    if desc["has_gate"]:
        lines.append("  بوابة متابعة/تعليق: موجودة ✗")
    tag_report = report["tags"]
    lines.append("الوسوم: %d وسمًا (الحد %d)، %d / %d حرفًا %s"
                 % (tag_report["count"], tag_report["count_limit"],
                    tag_report["total_chars"],
                    tag_report["total_chars_limit"],
                    "✓" if tag_report["total_chars_ok"] else "✗"))
    if report["issues"]:
        lines.append("الملاحظات:")
        for issue in report["issues"]:
            lines.append("  - %s" % issue)
    if report.get("notes"):
        lines.append("ملاحظات إرشادية (لا تمنع النشر):")
        for note in report["notes"]:
            lines.append("  - %s" % note)
    return "\n".join(lines)
