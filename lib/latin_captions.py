#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
r"""كابشنات لاتينية LTR — مسار إنجليزي منفصل (EN-06).

واجهة موازية لواجهة ``lib.capite_captions`` (تقسيم كلمات ← تجميع
في أسطر ← ملف ASS بحدث لكل كلمة)، لكن **بلا أي منطق RTL وبلا
تشكيل عربي**: لا عكس اتجاه، لا حروف عربية، لا وسوم تلوين
مقسّمة ({\c}...{\r}) — النص سليم حرفيًا دائمًا.

الموضع: **أسفل الصورة فقط** — نفس شريط الكابشن العربي حرفيًا:
محاذاة ASS رقم 2 (أسفل الوسط)، MarginL/MarginR ‏40، MarginV ‏64،
PlayRes ‏720×1280، وحجم الخط الافتراضي 52 — مطابقة لقيم
``lib.whisper_captions.ass_header`` التي يستخدمها المسار العربي.
لا موضع وسط ولا أعلى أبدًا.

الخط (LATIN_FONT):
- العائلة في ASS: ``Noto Sans`` — تُحلّ عبر fontconfig وقت
  الحرق (libass) إلى خط النظام الكامل
  ``/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf`` — نفس
  قيد ASS الموثّق في ``docs/fonts.md`` للخط العربي: خط الشجرة
  المُقسَّم فرعيًا لا يُثبَّت في fontconfig عمدًا حتى لا يحجب
  خط النظام الكامل.
- الملف في الشجرة: ``assets/fonts/NotoSans-Bold-subset.ttf``
  (Bold ثابت، v2.015، ‏65,252 بايت، 758 glyph) — للاستخدام
  حيث يُمرَّر مسار ملف صريح.
- المصدر: مستودع ``google/fonts`` الرسمي —
  ``ofl/notosans/NotoSans[wdth,wght].ttf`` (خط متغير،
  2,049,096 بايت، SHA-256 ‏bfb7bb69…؛ فُحص 2026-11-26).
  الرابط المباشر في ثابت ``LATIN_FONT_SOURCE``.
- الترخيص: **SIL Open Font License, Version 1.1 (OFL)** —
  مصرّح به في ``METADATA.pb`` في المصدر نفسه
  (``license: "OFL"``، المصمم Google)، ونصه في
  ``ofl/notosans/OFL.txt``، ومدوّن داخل الخط نفسه
  (nameID 13). حر للاستخدام والتوزيع والتضمين مع الاستوديو.
- كيف وُلّد الملف المُقسَّم (قابل لإعادة الإنتاج): تثبيت الوزن
  wght=700 بمكتبة fontTools ‏4.46.0 (``varLib.instancer``)
  مع تصحيح جدول الأسماء (العائلة «Noto Sans»، والفرعية
  «Bold»، وbit الغامق في ``OS/2.fsSelection`` و``head.macStyle``)
  وحذف جداول التغيّر (fvar/avar/gvar/HVAR/MVAR/VVAR)، ثم
  تقسيم فرعي بمجموعة حروف لاتينية (الأساسية U+0020–U+007E،
  وLatin-1 ‏U+00A0–U+00FF، وLatin Extended-A ‏U+0100–U+017F،
  وعلامات الترقيم العامة U+2000–U+206F، ورموز العملات
  U+20A0–U+20BF). النتيجة: 2,049,096 ← 65,252 بايت.
  بصمة الملف المُقسَّم في ثابت ``LATIN_FONT_SHA256``.

التقسيم (``split_latin_words``): تقسيم على الكلمات بلا تقسيم
داخل الاختصارات والأرقام وعلامات الترقيم الملتصقة — ``Mr.``
و``Dr.`` و``$20,000`` و``U.S.`` و``don't`` تبقى كلمة واحدة.

التزامن: حدث ASS واحد لكل كلمة — يبدأ مع الكلمة وينتهي عند
بداية الكلمة التالية (ناقص 10 مللي ثانية)، أو عند نهاية
العبارة لآخر كلمة فيها — فالتزامن عبارة بعبارة محفوظ كما في
المسار العربي.
"""
import os
import re

# ---------------------------------------------------------------- ثوابت
# اسم عائلة الخط في كابشنات ASS — يُحلّ عبر fontconfig وقت الحرق
# (libass)، لا عبر مسار ملف؛ انظر قيد الخط في توثيق الوحدة.
LATIN_FONT = "Noto Sans"

_STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LATIN_FONT_FILE = os.path.join(
    _STUDIO_ROOT, "assets", "fonts", "NotoSans-Bold-subset.ttf")
LATIN_FONT_SYSTEM_FILE = (
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf")
LATIN_FONT_LICENSE = "SIL Open Font License, Version 1.1 (OFL)"
LATIN_FONT_SOURCE = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/notosans/"
    "NotoSans%5Bwdth%2Cwght%5D.ttf")
LATIN_FONT_VERSION = "2.015"
LATIN_FONT_SHA256 = (
    "67d38264b1a57ed33c3a50da4fbb37477086bf5b3c13c4121ca6bf2b04d7d7ed")

# موضع الكابشن — نفس شريط الكابشن العربي حرفيًا (أسفل الصورة فقط).
CAPTION_ALIGNMENT = 2   # أسفل الوسط في ASS (1=أسفل يسار، 3=أسفل يمين)
CAPTION_MARGIN_L = 40
CAPTION_MARGIN_R = 40
CAPTION_MARGIN_V = 64   # ارتفاع الشريط عن أسفل الشاشة (64 = حد المنطقة الآمنة 5% عند ارتفاع 1280)
CAPTION_PLAYRES_X = 720
CAPTION_PLAYRES_Y = 1280
CAPTION_FONT_SIZE = 52

# حد عرض السطر اللاتيني (EN-08: ~42 حرفًا للاتينية في 9:16).
MAX_LINE_CHARS = 42
MAX_LINES = 2


class LatinCaptionError(Exception):
    """خطأ في توليد الكابشنات اللاتينية (رسالته عربية جاهزة للعرض)."""


# حروف عربية + محارف تحكم RTL — ممنوعة في هذا المسار كله.
_RTL_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF"
    r"\uFE70-\uFEFF\u200F\u202B\u202C\u202D\u202E]")

# التقسيم على الكلمات — ترتيب البدائل مقصود (الأخص أولًا):
# 1. مال/أرقام بفواصل عشرية وآلاف: $20,000 / 20,000 / 3.5 / 50%
#    (الفاصلة داخل الرقم لا تقسّم؛ وعلامة الترقيم الملتصقة
#    بعده — فاصلة أو نقطة نهاية جملة — تبقى معه).
# 2. اختصارات الحروف الأولى: U.S. / U.S.A. / e.g. (مع ما يلتصق بها).
# 3. كلمة (مع اختصار فاصلة عليا داخلي: don't / it's)، وقد
#    تُربط بشرطة (well-known)، وقد تنتهي بنقطة اختصار أو
#    نهاية جملة (Mr. / Dr. / end.)، وعلامات الترقيم الملتصقة
#    بها (، ؟ ! :) تبقى معها — كما في المسار العربي.
# 4. أي سلسلة غير فراغية أخرى (علامات ترقيم مستقلة كالشرطات
#    والاقتباسات) — فلا يضيع أي محرف من النص.
_TOKEN_RE = re.compile(r"""
    \$?\d[\d,]*(?:\.\d+)?%?[.,;:!?]*   # $20,000 / 20,000 / 3.5 / 50%
  | (?:[A-Za-z]\.){2,}[.,;:!?]*        # U.S. / U.S.A. / e.g.
  | [A-Za-z]+(?:'[A-Za-z]+)*(?:-[A-Za-z]+(?:'[A-Za-z]+)*)*\.?[.,;:!?]*
                                       # don't / well-known / Mr. / end.
  | [^\s]+                             # any other non-space run
""", re.VERBOSE)


def escape_ass_text(text):
    """هرب محارف ASS الخاصة في نص كلمة."""
    return (text.replace("\\", "\\\\")
                .replace("{", "\\{")
                .replace("}", "\\}")
                .replace("\n", " "))


def split_latin_words(text):
    """قسّم نصًا إنجليزيًا إلى كلمات (قائمة سلاسل).

    لا تقسيم داخل: ``Mr.`` و``Dr.`` و``$20,000`` و``U.S.``
    و``don't`` — ولا داخل أي اختصار/رقم/انكماش مماثل.
    نص فارغ أو بلا كلمات يرجع قائمة فارغة.
    """
    if not text:
        return []
    return _TOKEN_RE.findall(text)


def group_latin_words_into_lines(words, max_chars=MAX_LINE_CHARS,
                                 max_lines=MAX_LINES):
    """يجمّع كلمات (قواميس w/start/end) في مجموعات من سطرين كحد أقصى.

    كل مجموعة: {"start": ..., "end": ..., "lines": [[كلمات...], ...]}.
    كلمة جديدة تنتقل للسطر التالي إن تجاوزت ميزانية الحروف،
    ومجموعة جديدة إن امتلأ السطران. موازٍ لـ
    ``capite_captions.group_words_into_lines`` بلا قاعدة اليتيم
    العربية (لا كلمات وظيفية عربية هنا أصلًا).
    """
    groups = []
    cur_lines = [[]]
    cur_chars = [0]
    cur_start = None
    cur_end = None

    def flush():
        nonlocal cur_lines, cur_chars, cur_start, cur_end
        if cur_lines and any(cur_lines):
            groups.append({"start": cur_start, "end": cur_end,
                           "lines": [list(ln) for ln in cur_lines]})
        cur_lines = [[]]
        cur_chars = [0]
        cur_start = None
        cur_end = None

    for w in words:
        word = (w.get("w") or w.get("word") or "").strip()
        if not word:
            continue
        if _RTL_RE.search(word):
            raise LatinCaptionError(
                "كلمة غير لاتينية في المسار اللاتيني: %r" % word)
        start = float(w["start"])
        end = float(w["end"])
        if cur_start is None:
            cur_start = start
            cur_lines = [[{"w": word, "start": start, "end": end}]]
            cur_chars = [len(word)]
            cur_end = end
            continue
        idx = len(cur_lines) - 1
        chars = cur_chars[idx] + (1 if cur_lines[idx] else 0) + len(word)
        if chars <= max_chars:
            cur_lines[idx].append({"w": word, "start": start, "end": end})
            cur_chars[idx] = chars
            cur_end = end
        elif idx + 1 < max_lines:
            cur_lines.append([{"w": word, "start": start, "end": end}])
            cur_chars.append(len(word))
            cur_end = end
        else:
            flush()
            cur_start = start
            cur_lines = [[{"w": word, "start": start, "end": end}]]
            cur_chars = [len(word)]
            cur_end = end
    flush()
    return groups


def latin_ass_header(font_size=CAPTION_FONT_SIZE):
    """ترويسة ASS لاتينية: اتجاه LTR صريح، وخط Noto Sans،
    وموضع أسفل الصورة فقط — نفس قيم شريط الكابشن العربي."""
    return (
        "[Script Info]\n"
        "; Latin captions — LTR only (explicit: no RTL logic in this path)\n"
        "; Direction: LTR\n"
        "; Language: en\n"
        "ScriptType: v4.00+\n"
        "PlayResX: %d\n"
        "PlayResY: %d\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,%s,%d,&H00FFFFFF,&H000000FF,"
        "&H80000000,&H80000000,1,0,0,0,100,100,0,0,1,3,0,%d,%d,%d,%d,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n" % (CAPTION_PLAYRES_X, CAPTION_PLAYRES_Y,
                            LATIN_FONT, font_size, CAPTION_ALIGNMENT,
                            CAPTION_MARGIN_L, CAPTION_MARGIN_R,
                            CAPTION_MARGIN_V)
    )


def _format_ass_time(seconds):
    """ثوانٍ عشرية → زمن ASS مثل 0:00:01.50 (يُقص لأقرب 10 مللي ثانية)."""
    if seconds < 0:
        seconds = 0.0
    total_cs = int(round(seconds * 100))
    cs = total_cs % 100
    total_s = total_cs // 100
    s = total_s % 60
    m = (total_s // 60) % 60
    h = total_s // 3600
    return "%d:%02d:%02d.%02d" % (h, m, s, cs)


def words_to_latin_ass(words, font_size=CAPTION_FONT_SIZE,
                       max_chars=MAX_LINE_CHARS, max_lines=MAX_LINES):
    """كلمات بتوقيتها → (نص ملف ASS كامل، مجموعات).

    حدث ASS واحد لكل كلمة بنص العبارة الكامل سليمًا بلا أي
    وسوم: يبدأ مع الكلمة وينتهي عند بداية الكلمة التالية
    (ناقص 10 مللي ثانية)، أو عند نهاية العبارة لآخر كلمة فيها.
    يرفع LatinCaptionError عند غياب الكلمات أو وجود محتوى
    غير لاتيني (عربي أو محارف تحكم RTL).
    """
    groups = group_latin_words_into_lines(words, max_chars=max_chars,
                                          max_lines=max_lines)
    if not groups:
        raise LatinCaptionError("لا كلمات لتوليد الكابشنات منها")
    lines = [latin_ass_header(font_size)]
    for g in groups:
        flat = []  # (كلمة، سطر)
        for li, line in enumerate(g["lines"]):
            for w in line:
                flat.append((w, li))
        for idx, (w, _li) in enumerate(flat):
            start = w["start"]
            if idx + 1 < len(flat):
                end = flat[idx + 1][0]["start"] - 0.01
            else:
                end = g["end"]
            if end <= start:
                end = start + 0.10
            text_parts = []
            for line in g["lines"]:
                text_parts.append(" ".join(
                    escape_ass_text(x["w"]) for x in line))
            text = "\\N".join(text_parts)
            lines.append("Dialogue: 0,%s,%s,Default,,0,0,0,,%s" % (
                _format_ass_time(start),
                _format_ass_time(end), text))
    return "\n".join(lines) + "\n", groups
