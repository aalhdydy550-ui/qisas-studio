#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""عنوان هوك كبير مكتوب في أول 3 ثوانٍ (جولة v0.1.58 — W6).

الدليل (قرار 10:09): تحليل ترند TikTok 2026-11-26 — كل فيديوهات
القصص المتصدرة تبدأ بالهوك عنوانًا مكتوبًا كبيرًا + صورة قبل
الصوت، بينما هوك الاستوديو حاليًا منطوق فقط — فالمشاهد الصامت
لا يرى أي هوك في أول 3 ثوانٍ. هذا هو التغيير الوحيد المدعوم
بالدليل في الجولة: عنصر جديد مستقل (نص هوك القصة نفسه، بلا
اختراع نص) بخط كبير عالي التباين من الثانية 0 إلى الثانية 3
فقط، في النطاق الأوسط من الإطار.

حدود التغيير (من ثوابت الاستوديو القائمة، لا أرقام مخترعة):
- أبدًا في الثلث العلوي: `lib.check.QA_TOP_FRACTION` (1/3).
- أبدًا متداخلًا مع منطقة الكابشنات أسفل الصورة: الكابشنات
  محاذاة سفلية (Alignment 2) بهامش `MarginV` وحجم خط من نمط
  `lib.whisper_captions.ass_header` (يُقرأ منهما مباشرة)،
  وبحد أقصى سطرين للعبارة (نمط الاستوديو: `wrap_hook` يقصّر
  على سطرين، و`capite_captions` يجمّع سطرين كحد أقصى).
- أسلوب النص من نمط العناوين القائم (`lib.thumbnail`: خط
  Noto Naskh Arabic عريض، حجم 58، أبيض بحواف سوداء).
- الكابشنات المتزامنة لا تتحرك (أسفل فقط)، وحظر الثلث العلوي
  لا يُمسّ، ولا موسيقى، ولا صوت بديل.

الهروب (حقائق مثبّتة تجريبيًا على ffmpeg 8.1.2 في هذا الجهاز):
- `:` داخل نص drawtext يقسّم الخيارات حتى داخل علامات
  الاقتباس المفردة — لا بد من `\\:` في سلسلة الفلتر.
- `%` ASCII في drawtext يخضع لتوسيع `%{...}`، وهروب `\\%`
  يفشل حين يحيط بالنص العربي نص RTL آخر (إعادة ترتيب fribidi
  تفصل `%` عن `\\` قبل التوسيع فيُسقط النص كاملًا بلا خطأ
  صريح — «Stray %» فقط). لذلك يُطبَّع `%` إلى `٪` (U+066A،
  علامة النسبة العربية القياسية في الطباعة العربية، وموجودة
  في خط Noto Naskh Arabic Bold) قبل الحرق — والنص الأصلي
  يُحفظ في المواصفة (`text`) والمنطَّق في (`render_text`).
- `'` ASCII يستحيل تمثيلها داخل `text='...'` إطلاقًا: علامة
  الاقتباس المفردة تقلب حالة الاقتباس دائمًا في محلّل مخطط
  فلاتر ffmpeg هذا، ولا يهربها أي عدد من الشرطات المائلة
  (`\\'` و`\\\\'` و`\\\\\\'` كلها تكسر التحليل، ونمط
  الإغلاق-وإعادة-الفتح `'a'\\''b'` يبتلع بقية الفلتر) —
  لذلك تُطبَّع إلى علامتي الاقتباس العربيتين «» (موجودتان في
  الخط، وهما الصيغة الصحيحة للاقتباس في النص العربي أصلًا):
  الأولى « والثانية » بالتناوب.
- `expansion=none` لا يمنع تحذير «Stray %» فلا يُستخدم بديلًا
  عن التطبيع؛ وخط Noto Naskh Arabic Bold بلا لاتيني أصلًا
  وبلا U+2019 (’)، فلا يُستخدم `’` كبديل للفاصلة — بل «».

التكامل في مسار بناء الشورت ليس من هذه الوحدة — للمنسق في
الربط (انظر مواصفة الربط في تقرير إكمال الجولة): الدوال هنا
جاهزة للتوصيل (`hook_title_spec` + `build_drawtext_filter`
+ `apply_hook_title`)، وتُدمج كفلتر إضافي بعد إعادة التأطير
العمودي وقبل حرق الكابشنات (أو كخطوة مستقلة على الشورت
الجاهز — الترتيب لا يغيّر النتيجة لأن العنوان في النطاق
الأوسط والكابشنات أسفل الصورة).
"""
import json
import os
import re
import subprocess
import unicodedata

from lib import check as check_lib
from lib import manifest as manifest_lib
from lib import thumbnail as thumbnail_lib
from lib import whisper_captions as captions_lib

HOOK_TITLE_START = 0.0
HOOK_TITLE_END = 3.0
# أسلوب النص من نمط العناوين القائم (lib.thumbnail — Hook).
TITLE_FONT = thumbnail_lib.FONT
TITLE_FONT_SIZE = thumbnail_lib.FONTSIZE
TITLE_FONT_FILE = ("/usr/share/fonts/truetype/noto/"
                   "NotoNaskhArabic-Bold.ttf")
TITLE_FONT_COLOR = "white"
TITLE_BORDER_COLOR = "black"
TITLE_BORDER_WIDTH = 2
TITLE_MAX_LINES = 2
# أقصى سطور لعبارة كابشن واحدة (نمط الاستوديو — سطران).
CAPTION_MAX_LINES = 2
# نسبة عرض حرف عربي ~0.58 من حجم الخط (docstring في
# lib.capite_captions) — تُستخدم لحساب حروف السطر من العرض.
_ARABIC_CHAR_WIDTH_RATIO = 0.58
# علامة النسبة العربية (U+066A) — بديل `%` ASCII في النص
# العربي (انظر docstring أعلى الملف).
_ARABIC_PERCENT = "\u066a"
# علامتا الاقتباس العربيتان — بديل `'` ASCII (انظر docstring
# أعلى الملف): الأولى « والثانية » بالتناوب.
_ARABIC_QUOTE_OPEN = "\u00ab"
_ARABIC_QUOTE_CLOSE = "\u00bb"


class HookTitleError(Exception):
    """خطأ في عنوان الهوك (رسالته عربية جاهزة للعرض)."""


def _caption_style():
    """اقرأ نمط الكابشن القائم من `whisper_captions.ass_header`.

    يرجع {"font_size", "margin_v", "alignment"} من سطر
    `Style: Default` — لا أرقام مكتوبة هنا: أي تغيير في نمط
    الكابشنات ينعكس تلقائيًا على هندسة العنوان.
    """
    header = captions_lib.ass_header()
    fmt = []
    style_vals = None
    for line in header.splitlines():
        line = line.strip()
        if line.startswith("Format:") and "Fontname" in line:
            fmt = [c.strip() for c in line[len("Format:"):].split(",")]
        elif line.startswith("Style: Default,"):
            style_vals = [v.strip() for v in
                          line[len("Style:"):].split(",")]
    if not fmt or not style_vals:
        raise HookTitleError("تعذّرت قراءة نمط الكابشن من "
                             "lib.whisper_captions.ass_header")
    try:
        return {"font_size": int(style_vals[fmt.index("Fontsize")]),
                "margin_v": int(style_vals[fmt.index("MarginV")]),
                "alignment": int(style_vals[fmt.index("Alignment")])}
    except (ValueError, IndexError):
        raise HookTitleError("نمط الكابشن في "
                             "lib.whisper_captions.ass_header غير صالح")


def normalize_hook_text(text):
    """طبّع نص الهوك للعرض: `%` ASCII ← `٪` عربية، و`'`
    ASCII ← علامتا اقتباس عربيتان «» بالتناوب (الأولى «
    والثانية »).

    علامة النسبة العربية هي الصيغة القياسية في النص العربي،
    و`%` ASCII تُسقط النص كاملًا في drawtext حين يحيط بها
    نص RTL (انظر docstring أعلى الملف)؛ و`'` ASCII يستحيل
    تمثيلها داخل `text='...'` إطلاقًا في ffmpeg هذا الجهاز
    (علامة الاقتباس تقلب حالة الاقتباس دائمًا) — و«» هما
    صيغة الاقتباس العربية الصحيحة أصلًا، وموجودتان في الخط.
    النص الأصلي لا يُفقد — يُحفظ في مواصفة `hook_title_spec`
    تحت `text`.
    """
    out = []
    quote_open = True
    for ch in (text or ""):
        if ch == "%":
            out.append(_ARABIC_PERCENT)
        elif ch == "'":
            out.append(_ARABIC_QUOTE_OPEN if quote_open
                       else _ARABIC_QUOTE_CLOSE)
            quote_open = not quote_open
        else:
            out.append(ch)
    return "".join(out)


def escape_drawtext_text(text):
    """هرب نص داخل قيمة `text='...'` في فلتر ffmpeg drawtext.

    مرحلتان (الترتيب مهم):
    1. هروب مستوى drawtext نفسه: `\\` ← `\\\\`، و`%` ← `\\%`
       (حرفي في التوسيع) — وإلا فصّل النص أو أُسقط (تحذير
       «Stray %» يلغي النص كاملًا بصمت).
    2. هروب مستوى مخطط الفلاتر (داخل علامات الاقتباس
       المفردة): `\\` ← `\\\\`، و`:` ← `\\:` (`:` تقسّم
       الخيارات حتى داخل الاقتباسات في ffmpeg هذا الجهاز —
       مثبّت تجريبيًا).
    `,` داخل الاقتباسات محمية فتُترك كما هي.
    قيدان موثّقان (انظر docstring أعلى الملف): `\\%` من
    المرحلة 1 لا يصمد حين يحيط بالنص العربي نص RTL آخر
    (إعادة ترتيب fribidi) — لذلك يطبّع `hook_title_spec`
    كل `%` إلى `٪` قبل الوصول هنا؛ و`'` ASCII لا يهربها أي
    عدد من الشرطات المائلة إطلاقًا (تقلب حالة الاقتباس
    دائمًا) — فأي `'` تصل هنا تُستبدل بـ `»` كملاذ أخير،
    والتطبيع الصحيح لها هو `normalize_hook_text` («» بالتناوب).
    """
    # 1. مستوى drawtext.
    text = text.replace("\\", "\\\\").replace("%", "\\%")
    # 2. مستوى مخطط الفلاتر.
    text = (text.replace("\\", "\\\\").replace(":", "\\:")
                .replace("'", _ARABIC_QUOTE_CLOSE))
    return text


# --- حارس التضاعف (إصلاح تضاعف عنوان الهوك على فيديوهات
# Concat — 2026-11-26): فيديو Concat يحمل أصلًا عنوانًا محروقًا
# أول ثوانٍ (title_add في lib.concat_mcp: 0–4ث، مركز y≈794 في
# 1280 — داخل النطاق الأوسط لعنوان الهوك)، فحرق العنوان نفسه
# مرة ثانية ينتج عنوانين متداخلين مشوّهين في الشريط نفسه.
# الحارس يقرأ حقل `title` فقط من البيان الجانبي
# `<الفيديو>.manifest.json` (المعيار الذي يكتبه كل تجميع —
# lib.manifest.manifest_path_for)؛ حقل `hook` هو الهوك المنطوق
# لا المحروق فلا يحرّك الحارس وحده. بلا بيان أو بيان تالف:
# fail-open موثّق (لا رفض أعمى).
_ARABIC_DIACRITICS = "".join(chr(c) for c in range(0x064B, 0x0653))
# الهمزة فوق/تحت (0654/0655) تظهر بعد NFKD من أشكال الألف
# المهموزة — تُجرد مع التشكيل حتى لا تفسد المقارنة.
_ARABIC_DIACRITICS += "\u0670\u0640\u0654\u0655"
_ALEF_VARIANTS = {"\u0622": "\u0627", "\u0623": "\u0627",
                  "\u0625": "\u0627", "\u0671": "\u0627",
                  "\u0629": "\u0647", "\u0649": "\u064a",
                  "\u0624": "\u0648", "\u0626": "\u064a"}


def _normalize_title_words(text):
    """طبّع عنوانًا للمقارنة: تجريد التشكيل والتطويل، وتوحيد
    أشكال الألف والتاء المربوطة والألف المقصورة والهمزات،
    وإسقاط الترقيم، وتقسيم كلمات. كلمة واحدة مشتركة لا تكفي
    وحدها — انظر `titles_overlap`."""
    if not text:
        return []
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text
                   if ch not in _ARABIC_DIACRITICS)
    text = "".join(_ALEF_VARIANTS.get(ch, ch) for ch in text)
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return [w.lower() for w in text.split() if w]


def _is_subsequence(short, long_words):
    """هل كلمات `short` متتابعة (بالترتيب، لا يشترط التصاقها)
    داخل `long_words`؟"""
    it = iter(long_words)
    return all(any(w == word for word in it) for w in short)


def titles_overlap(a, b):
    """هل العنوانان متداخلان (تطابق أو احتواء)؟

    التطبيع يجعل الترقيم والتشكيل وأشكال الألف لا تخفي
    التطابق؛ والاحتواء يحتاج كلمتين على الأقل من العنوان
    الأقصر متتابعتين بالترتيب داخل الأطول — فكلمة واحدة
    مشتركة (مثل «الفجر») ليست عنوانًا مضاعفًا."""
    words_a = _normalize_title_words(a)
    words_b = _normalize_title_words(b)
    if not words_a or not words_b:
        return False
    if words_a == words_b:
        return True
    short, long_words = (words_a, words_b) if len(words_a) <= len(words_b) \
        else (words_b, words_a)
    if len(short) < 2:
        return False
    return _is_subsequence(short, long_words)


def detect_burned_title(video_path, title):
    """أعلن البيان الجانبي عنوانًا محروقًا يتداخل مع `title`؟

    يرجع نص العنوان المحروق كما هو في البيان، أو None: بلا
    بيان، أو بيان تالف/ليس قاموسًا، أو حقل `title` فارغ، أو
    عنوان لا يتداخل، أو فيديو مفقود. لا يقرأ حقل `hook` —
    فهو الهوك المنطوق لا المحروق."""
    if not video_path or not title:
        return None
    try:
        path = manifest_lib.manifest_path_for(video_path)
    except (OSError, ValueError):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            manifest = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(manifest, dict):
        return None
    burned = manifest.get("title")
    if not burned or not isinstance(burned, str):
        return None
    if titles_overlap(burned, title):
        return burned
    return None


def _max_chars_per_line(width, fontsize=TITLE_FONT_SIZE):
    """حروف السطر من العرض الآمن: عرض الإطار ناقص هامشي 5%
    (`lib.check.QA_SAFE_MARGIN`) مقسومًا على عرض الحرف العربي
    (~0.58 × حجم الخط — `lib.capite_captions`)."""
    usable = width * (1.0 - 2.0 * check_lib.QA_SAFE_MARGIN)
    char_w = _ARABIC_CHAR_WIDTH_RATIO * fontsize
    return max(1, int(usable // char_w))


def hook_title_spec(title, width=720, height=1280):
    """احسب مواصفة عنوان الهوك (قاموس JSON خالص، حتمي).

    {"text" (الأصلي)، "render_text" (المطبَّع للعرض)، "lines"
    (≤ سطرين — `thumbnail.wrap_hook`)، "width"/"height"،
    "font"/"fontfile"/"fontsize"/"fontcolor"/"bordercolor"/
    "borderw" (نمط العناوين القائم)، "start"=0.0، "end"=3.0،
    "top_limit" (نهاية الثلث العلوي المحظور)،
    "caption_zone_top" (أعلى منطقة الكابشنات أسفل الصورة)،
    "y0"/"y1" (أعلى/أسفل كتلة العنوان)، "line_y" (y كل سطر)،
    "max_chars_per_line"}.
    كتلة العنوان متمركزة عموديًا في النطاق الأوسط
    [top_limit, caption_zone_top] — أبدًا في الثلث العلوي،
    وأبدًا متداخلة مع منطقة الكابشنات. يرفع HookTitleError
    عند عنوان فارغ أو أبعاد غير صالحة أو إطار أضيق من أن
    يتسع للكتلة في النطاق الأوسط.
    """
    if not title or not title.strip():
        raise HookTitleError("نص الهوك فارغ — عنوان الهوك من نص "
                             "السكريبت نفسه، بلا اختراع نص")
    try:
        width = int(width)
        height = int(height)
    except (TypeError, ValueError):
        raise HookTitleError("أبعاد الفيديو غير صالحة: %s×%s"
                             % (width, height))
    if width <= 0 or height <= 0:
        raise HookTitleError("أبعاد الفيديو غير صالحة: %dx%d"
                             % (width, height))
    caption = _caption_style()
    if caption["alignment"] != 2:
        raise HookTitleError("نمط الكابشنات لم يعد سفليًا "
                             "(Alignment %d) — هندسة النطاق الأوسط "
                             "مبنية على كابشنات أسفل الصورة فقط"
                             % caption["alignment"])
    render_text = normalize_hook_text(title.strip())
    max_chars = _max_chars_per_line(width)
    lines = thumbnail_lib.wrap_hook(render_text, max_chars=max_chars)
    lines = [ln for ln in lines if ln]
    if not lines:
        raise HookTitleError("نص الهوك فارغ بعد التطبيع")
    top_limit = height * check_lib.QA_TOP_FRACTION
    caption_zone_top = (height - caption["margin_v"]
                        - CAPTION_MAX_LINES * caption["font_size"])
    block_h = len(lines) * TITLE_FONT_SIZE
    y0 = int(round((top_limit + caption_zone_top - block_h) / 2.0))
    y1 = y0 + block_h
    spec = {"text": title.strip(),
            "render_text": render_text,
            "lines": lines,
            "width": width, "height": height,
            "font": TITLE_FONT, "fontfile": TITLE_FONT_FILE,
            "fontsize": TITLE_FONT_SIZE,
            "fontcolor": TITLE_FONT_COLOR,
            "bordercolor": TITLE_BORDER_COLOR,
            "borderw": TITLE_BORDER_WIDTH,
            "start": HOOK_TITLE_START, "end": HOOK_TITLE_END,
            "top_limit": round(top_limit, 2),
            "caption_zone_top": caption_zone_top,
            "y0": y0, "y1": y1,
            "line_y": [y0 + i * TITLE_FONT_SIZE
                       for i in range(len(lines))],
            "max_chars_per_line": max_chars}
    problems = validate_spec(spec)
    if problems:
        raise HookTitleError("؛ ".join(problems))
    return spec


def validate_spec(spec):
    """تحقق من مواصفة عنوان: يرجع قائمة مشاكل عربية (فارغة =
    سليمة). يفحص الهندسة (النطاق الأوسط فقط)، والتوقيت
    (0–3 ثوانٍ بالظبط)، والسطور (≤ سطرين وكل سطر ضمن الحد)."""
    problems = []
    top = spec.get("top_limit")
    cap_top = spec.get("caption_zone_top")
    y0 = spec.get("y0")
    y1 = spec.get("y1")
    if top is None or cap_top is None or y0 is None or y1 is None:
        return ["المواصفة بلا هندسة (top_limit/caption_zone_top/"
                "y0/y1)"]
    if y0 < top:
        problems.append("عنوان الهوك يبدأ عند y=%d — داخل الثلث "
                        "العلوي المحظور (حده %.0f)" % (y0, top))
    if y1 > cap_top:
        problems.append("عنوان الهوك ينتهي عند y=%d — متداخل مع "
                        "منطقة الكابشنات (تبدأ عند %d)"
                        % (y1, cap_top))
    if y1 <= y0:
        problems.append("كتلة العنوان بلا ارتفاع (y0=%d، y1=%d)"
                        % (y0, y1))
    if spec.get("start") != HOOK_TITLE_START:
        problems.append("بداية العنوان %.1f — يجب أن تكون %.1f"
                        % (spec.get("start"), HOOK_TITLE_START))
    if spec.get("end") != HOOK_TITLE_END:
        problems.append("نهاية العنوان %.1f — يجب أن تكون %.1f"
                        % (spec.get("end"), HOOK_TITLE_END))
    lines = spec.get("lines") or []
    if not lines:
        problems.append("العنوان بلا سطور")
    if len(lines) > TITLE_MAX_LINES:
        problems.append("العنوان %d سطور — الحد %d"
                        % (len(lines), TITLE_MAX_LINES))
    max_chars = spec.get("max_chars_per_line")
    if max_chars:
        for ln in lines:
            if len(ln) > max_chars:
                problems.append("سطر «%s» أطول من الحد (%d حرفًا)"
                                % (ln[:20], max_chars))
    if "%" in (spec.get("render_text") or ""):
        problems.append("النص المعروض يحوي `%` ASCII — يجب "
                        "تطبيعه إلى `٪` قبل الحرق")
    if "'" in (spec.get("render_text") or ""):
        problems.append("النص المعروض يحوي `'` ASCII — يجب "
                        "تطبيعه إلى «» قبل الحرق")
    return problems


def build_drawtext_filter(spec):
    """ابنِ فلتر ffmpeg drawtext من المواصفة: مرشح drawtext
    واحد لكل سطر (بلا `\\n` — موضع كل سطر محسوب صراحة)،
    متمركز أفقيًا `x=(w-text_w)/2`، ومقيّد زمنيًا
    `enable='between(t,0,3)'` — العنوان ظاهر في أول 3 ثوانٍ
    فقط. النص يُهرب بـ `escape_drawtext_text`."""
    problems = validate_spec(spec)
    if problems:
        raise HookTitleError("مواصفة عنوان غير صالحة: %s"
                             % "؛ ".join(problems))
    parts = []
    for line, y in zip(spec["lines"], spec["line_y"]):
        parts.append(
            "drawtext=text='%s':fontfile=%s:fontsize=%d:"
            "fontcolor=%s:borderw=%d:bordercolor=%s:"
            "x=(w-text_w)/2:y=%d:enable='between(t,%.1f,%.1f)'"
            % (escape_drawtext_text(line), spec["fontfile"],
               spec["fontsize"], spec["fontcolor"], spec["borderw"],
               spec["bordercolor"], y, spec["start"], spec["end"]))
    return ",".join(parts)


def apply_hook_title(video_path, title, out_path, timeout=600,
                     force=False):
    """طبّق عنوان الهوك على فيديو: حرق العنوان في أول 3 ثوانٍ
    فقط وإعادة ترميز على نمط `shorts_cut.reframe_vertical`
    (libx264 veryfast crf 20 + yuv420p + aac إن وُجد صوت).
    يرجع مسار الخرج. يرفع HookTitleError عند ملف مفقود أو
    عنوان فارغ أو فشل ffmpeg — والمدة والأبعاد والصوت
    تُحفظ كما هي (العنوان إضافة بصرية فقط).

    الحارس (قبل المواصفة، بعد فحص الفيديو): إن أعلن البيان
    الجانبي عنوانًا محروقًا يتداخل مع المطلوب يرفض برسالة
    عربية تسمّي العنوان المحروق وتذكّر بـ`--force` في الـCLI
    (أو `force=True` في بايثون) — و`--force` يطبّق عند الطلب
    الصريح. الترتيب مقصود: رفض التضاعف يفوز
    على رفض طول الهوك (تقصير الهوك لا ينفع حين العنوان محروق
    أصلًا). الرفض لا يمسّ ملف خرج موجود أصلًا."""
    if not os.path.isfile(video_path):
        raise HookTitleError("ملف الفيديو غير موجود: %s" % video_path)
    # مسار مطلق: ملف اسمه يبدأ بشرطة كان يُفسَّر كخيار من
    # ffmpeg (نفس إصلاح lib.check).
    video_path = os.path.abspath(os.path.expanduser(video_path))
    try:
        info = check_lib.probe(video_path)
    except check_lib.CheckError as e:
        raise HookTitleError(str(e))
    if not force:
        burned = detect_burned_title(video_path, title)
        if burned:
            raise HookTitleError(
                "الفيديو يحمل عنوانًا محروقًا أصلًا: «%s» — يتداخل "
                "مع عنوان الهوك المطلوب «%s»؛ لن يُحرق العنوان مرة "
                "ثانية حتى لا يتضاعف في الشريط نفسه. مرّر "
                "--force للتطبيق رغم التضاعف."
                % (burned, (title or "").strip()))
    spec = hook_title_spec(title, info["width"], info["height"])
    if not os.path.isfile(spec["fontfile"]):
        raise HookTitleError("ملف خط العناوين غير موجود: %s"
                             % spec["fontfile"])
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    filt = build_drawtext_filter(spec)
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", video_path,
           "-vf", filt, "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "20", "-pix_fmt", "yuv420p"]
    if info["has_audio"]:
        cmd += ["-c:a", "aac"]
    cmd.append(out_path)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        raise HookTitleError("انتهت مهلة حرق عنوان الهوك (%d ثانية)"
                             % timeout)
    except OSError as e:
        raise HookTitleError("تعذر تشغيل ffmpeg: %s" % e)
    if proc.returncode != 0:
        raise HookTitleError("فشل ffmpeg في حرق عنوان الهوك "
                             "(رمز %d):\n%s"
                             % (proc.returncode,
                                (proc.stderr or "")[-800:]))
    if not os.path.isfile(out_path):
        raise HookTitleError("انتهى ffmpeg دون إنشاء الفيديو: %s"
                             % out_path)
    return out_path
