#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""تدقيق تشكيل الكابشن العربي في ملفات ASS.

يفحص كل سطر Dialogue بعد تجريد وسوم ASS:

- غياب U+FFFD (حرف الاستبدال — ملف تالف أو ترميز مكسور).
- غياب حروف Arabic Presentation Forms ‏(U+FE80–U+FEFF) — النص
  يجب أن يكون بترتيب منطقي ويشكّله العارض (libass)، لا حروفًا
  مشكّلة مسبقًا.
- السطر لا يبدأ برقم أو حرف لاتيني عندما يحتوي عربيًا (خلل
  bidi — الهوك لا يبدأ برقم أبدًا).
- النص المرئي غير فارغ بعد تجريد الوسوم.
- التفاف: سطر أطول من 70 حرفًا، أو كلمة واحدة أطول من 25 حرفًا،
  يُعلَّم كمشكلة التفاف محتملة (مع ذكر الحد في الرسالة).
- كلمة وظيفية عربية يتيمة في نهاية سطر مرئي ليس الأخير
  (kind ‏wrap_orphan_function_word) — تُفحص الأسطر المرئية
  المقسومة على ‎\\N بعد تجريد الوسوم، كل سطر عدا الأخير.
- تقسيم تلوين في سطر عربي (‏{\\c}...{\\r}) ‏(kind
  ‏rtl_highlight_split) — يُفحص على نص Dialogue الخام
  (مع الوسوم)، لأن تجريد الوسوم يخفي التقسيم الذي يقلب
  libass ترتيب مقاطعه عند العرض؛ والإنجليزي LTR لا يُعلَّم.

ثنائية اللغة (الجولة v0.1.41): `detect_text_lang` يصنّف
السطر ar/en/mixed/other بعدّ الحروف العربية مقابل اللاتينية؛
و`classify_line` يرجع التصنيف مع العدّين وما إذا كانت قاعدة
bidi تنطبق. القاعدة: الإنجليزي الخالص LTR سليم دائمًا
(بلا فحص bidi)؛ والمختلط تُطبَّق عليه bidi فقط إن غلب
العربي (حروف عربية أكثر من اللاتينية)؛ والمختلط الغالب
لاتينيًا يمر بلا عَلَم — فبدء سطر إنجليزي بكلمة إنجليزية
ليس خللًا. فحص حروف Presentation Forms يبقى على كل سطر
(الإنجليزي لا يحويها أصلًا)؛ والتفاف واحد للغتين.

لا يفحص هذا الملف امتثال كابشن فيسبوك (engagement bait) —
ذلك في `lib/caption_check.py` — ولا يعدّله.
"""
import os
import re

MAX_LINE_CHARS = 70
MAX_WORD_CHARS = 25

_REPLACEMENT_CHAR = "\ufffd"
_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
_TAG_RE = re.compile(r"\{[^}]*\}")
_COLOUR_TAG_RE = re.compile(r"\{\\c[^}]*\}")
_RESET_TAG_RE = re.compile(r"\{\\r[^}]*\}")
_LATIN_RE = re.compile(r"[A-Za-z]")
_DIGITS = set("0123456789٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹")

# كلمات وظيفية عربية (21 كلمة) لا تُترك يتيمة في نهاية
# سطر مرئي ليس الأخير — من خطة قاعدة اليتيم.
_FUNCTION_WORDS = frozenset([
    "في", "من", "على", "إلى", "عن", "مع", "أو", "ثم", "أن", "إن",
    "لا", "ما", "كل", "هل", "بل", "قد", "لم", "لن", "بين", "حتى",
    "منذ", "لدى",
])
_ORPHAN_PUNCT = "،؛؟.!"


def strip_ass_tags(text):
    """أزل وسوم ASS ‏({\\...}) وحوّل فواصل الأسطر إلى مسافات."""
    text = _TAG_RE.sub("", text or "")
    text = text.replace("\\N", " ").replace("\\n", " ").replace("\\h", " ")
    return text


def _strip_tags_keep_breaks(text):
    """أزل وسوم ASS مع الإبقاء على فواصل الأسطر ‎\\N (و‎\\n)
    فواصل — لفحص الأسطر المرئية قبل تسطيحها."""
    text = _TAG_RE.sub("", text or "")
    text = text.replace("\\h", " ")
    return text


def _visual_lines(text):
    """الأسطر المرئية لنص Dialogue: تجريد الوسوم مع الإبقاء
    على ‎\\N فاصلًا، ثم التقسيم عليه."""
    return re.split(r"\\[Nn]", _strip_tags_keep_breaks(text))


def _count_letters(text):
    """(عدد الحروف العربية، عدد الحروف اللاتينية) في نص."""
    arabic = sum(1 for c in text if _ARABIC_RE.match(c))
    latin = sum(1 for c in text if _LATIN_RE.match(c))
    return arabic, latin


def detect_text_lang(text):
    """صنّف نصًا بعد تجريد وسوم ASS: "ar" (عربي خالص) أو
    "en" (إنجليزي خالص) أو "mixed" (اللغتان معًا) أو
    "other" (بلا حروف من اللغتين — أرقام/رموز فقط)."""
    visible = strip_ass_tags(text).strip()
    arabic, latin = _count_letters(visible)
    if arabic and latin:
        return "mixed"
    if arabic:
        return "ar"
    if latin:
        return "en"
    return "other"


def classify_line(text):
    """تصنيف سطر للتشكيل: {"lang", "arabic_chars",
    "latin_chars", "bidi_applies"} — وقاعدة bidi تنطبق
    فقط على العربي والمختلط الغالب عربيًا (فالإنجليزي
    الخالص LTR سليم، والمختلط الغالب لاتينيًا يبدأ
    بكلمة إنجليزية بلا خلل)."""
    visible = strip_ass_tags(text).strip()
    arabic, latin = _count_letters(visible)
    lang = detect_text_lang(text)
    return {"lang": lang,
            "arabic_chars": arabic,
            "latin_chars": latin,
            "bidi_applies": bool(arabic) and arabic > latin}


def _dialogue_text(line):
    """نص سطر Dialogue (الحقل العاشر بعد 9 فواصل)، أو None."""
    if not line.startswith("Dialogue:"):
        return None
    rest = line[len("Dialogue:"):]
    parts = rest.split(",", 9)
    if len(parts) < 10:
        return None
    return parts[9]


def _check_line(text, file_name, line_no):
    """مشاكل سطر واحد بعد تجريد الوسوم."""
    issues = []
    visible = strip_ass_tags(text).strip()
    if not visible:
        issues.append({
            "file": file_name, "line_no": line_no,
            "kind": "empty_text",
            "detail": "سطر Dialogue بلا نص مرئي بعد تجريد وسوم ASS",
        })
        return issues
    if _REPLACEMENT_CHAR in visible:
        issues.append({
            "file": file_name, "line_no": line_no,
            "kind": "replacement_char",
            "detail": "السطر يحتوي حرف الاستبدال U+FFFD "
                      "(ملف تالف أو ترميز مكسور)",
        })
    bad = [c for c in visible if "\ufe80" <= c <= "\ufeff"]
    if bad:
        issues.append({
            "file": file_name, "line_no": line_no,
            "kind": "presentation_form",
            "detail": "السطر يحتوي %d حرفًا من Arabic Presentation "
                      "Forms (U+FE80–U+FEFF) مثل %r — النص يجب أن "
                      "يكون بترتيب منطقي ويشكّله العارض"
                      % (len(bad), bad[0]),
        })
    if classify_line(visible)["bidi_applies"]:
        first = visible[0]
        if first in _DIGITS or _LATIN_RE.match(first):
            issues.append({
                "file": file_name, "line_no": line_no,
                "kind": "bidi_start",
                "detail": "سطر عربي يبدأ بـ %r (رقم أو حرف لاتيني) — "
                          "خلل bidi؛ الهوك لا يبدأ برقم أبدًا" % first,
            })
    if len(visible) > MAX_LINE_CHARS:
        issues.append({
            "file": file_name, "line_no": line_no,
            "kind": "wrap_long_line",
            "detail": "السطر %d حرفًا — أطول من حد الالتفاف %d حرفًا"
                      % (len(visible), MAX_LINE_CHARS),
        })
    for word in visible.split():
        if len(word) > MAX_WORD_CHARS:
            issues.append({
                "file": file_name, "line_no": line_no,
                "kind": "wrap_long_word",
                "detail": "كلمة %r طولها %d حرفًا — أطول من حد "
                          "الكلمة %d حرفًا" % (word, len(word),
                                              MAX_WORD_CHARS),
            })
            break
    # قاعدة اليتيم: كلمة وظيفية في نهاية سطر مرئي ليس الأخير.
    # تُفحص الأسطر المرئية (التقسيم على ‎\N) لا النص المسطّح،
    # وكل سطر بقاعدة bidi_applies الخاصة به.
    visual = _visual_lines(text)
    for visual_line in visual[:-1]:
        stripped = visual_line.strip()
        if not stripped:
            continue
        if not classify_line(stripped)["bidi_applies"]:
            continue
        words = stripped.split()
        orphan = words[-1].strip(_ORPHAN_PUNCT)
        if orphan in _FUNCTION_WORDS:
            issues.append({
                "file": file_name, "line_no": line_no,
                "kind": "wrap_orphan_function_word",
                "detail": "سطر مرئي ينتهي بالكلمة الوظيفية %r — "
                          "يتيمة في نهاية السطر (انقلها إلى السطر "
                          "التالي مع ما بعدها)" % orphan,
            })
    # تقسيم التلوين: ‎{\c}...{\r} في سطر عربي يقلب libass
    # ترتيب مقاطعه عند العرض. يُفحص النص الخام (مع الوسوم)
    # لأن تجريدها يخفي التقسيم؛ والإنجليزي LTR سليم فلا يُعلَّم.
    if (_COLOUR_TAG_RE.search(text or "")
            and _RESET_TAG_RE.search(text or "")
            and classify_line(visible)["bidi_applies"]):
        issues.append({
            "file": file_name, "line_no": line_no,
            "kind": "rtl_highlight_split",
            "detail": "سطر عربي يحوي تقسيم تلوين (‎{\\c}...{\\r}) — "
                      "libass يقلب ترتيب مقاطع السطر عند العرض",
        })
    return issues


def audit_ass_file(path):
    """دقّق ملف ASS واحد.

    يرجع {"ok", "files_checked", "lines_checked", "issues"} —
    issues قائمة {"file", "line_no", "kind", "detail"}.
    """
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(path):
        raise FileNotFoundError("ملف ASS غير موجود: %s" % path)
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError as e:
        return {"ok": False, "files_checked": 1, "lines_checked": 0,
                "issues": [{"file": os.path.basename(path),
                            "line_no": 0, "kind": "unreadable",
                            "detail": "تعذر قراءة الملف كـ UTF-8: %s"
                                      % e}]}
    issues = []
    checked = 0
    for line_no, line in enumerate(lines, 1):
        text = _dialogue_text(line.rstrip("\n"))
        if text is None:
            continue
        checked += 1
        issues.extend(_check_line(text, os.path.basename(path),
                                  line_no))
    return {"ok": not issues, "files_checked": 1,
            "lines_checked": checked, "issues": issues}


def audit_ass_dir(dir_path):
    """دقّق كل ملفات ‎.ass في مجلد (مرتبة بالاسم)."""
    dir_path = os.path.abspath(os.path.expanduser(dir_path))
    if not os.path.isdir(dir_path):
        raise FileNotFoundError("المجلد غير موجود: %s" % dir_path)
    files = sorted(f for f in os.listdir(dir_path)
                   if f.lower().endswith(".ass"))
    issues = []
    checked = 0
    for name in files:
        res = audit_ass_file(os.path.join(dir_path, name))
        checked += res["lines_checked"]
        issues.extend(res["issues"])
    return {"ok": not issues, "files_checked": len(files),
            "lines_checked": checked, "issues": issues}


def format_report(result):
    """تقرير عربي موجز لنتيجة التدقيق."""
    lines = ["== تدقيق تشكيل الكابشن ==",
             "ملفات: %d — أسطر Dialogue: %d — مشاكل: %d"
             % (result["files_checked"], result["lines_checked"],
                len(result["issues"]))]
    for issue in result["issues"]:
        lines.append("%s:%d [%s] %s"
                     % (issue["file"], issue["line_no"],
                        issue["kind"], issue["detail"]))
    if result["ok"]:
        lines.append("النتيجة: سليم — لا مشاكل تشكيل.")
    return "\n".join(lines) + "\n"
