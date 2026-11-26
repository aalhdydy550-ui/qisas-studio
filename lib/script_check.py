#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""بوابة سكريبت نصية قبل الإنتاج — `script-check` (جولة v0.1.58، W4).

من مرحلة «السكريبت» في خطوط توليد الشورتات الكاملة
(MoneyPrinterTurbo/OpenReels): نص مكتمل مُتحقَّق منه قبل أي
إنفاق — الفكرة فقط، بلا نسخ كود إطلاقًا، وتنفيذ جديد من الصفر
بالمكتبة القياسية.

القيمة: الاستوديو يفحص الفيديو الجاهز (`lib/check.py`) ويولّد
الأفكار (`lib/ideas.py`) لكنه لا يفحص نص السكريبت نفسه قبل
الإنفاق؛ فسكريبت ضعيف يُكتشف بعد صرف 6 مقاطع Veo (120 وحدة
من رصيد ~200) + وقت ريندر وسرد. هذه البوابة تمسك الهوك الضعيف
والعبرة الغائبة والسؤال الختامي الغائب وعدد المشاهد الخاطئ
ولغة بوابة المتابعة وذكر الموسيقى ونهايات الأجزاء المحلولة
قبل أي وحدة Veo.

الفحوصات نصية فقط — بلا فيديو وبلا إنفاق وبلا شبكة وبلا LLM
وبلا عشوائية. يعيد استخدام القراءة فقط:
- `lib/dna.py::score_hook` لدرجة الهوك (0–10).
- `lib/ideas.py::valid_hook` لقواعد الهوك (جملة واحدة، لا يبدأ
  برقم أبدًا، ≤140 حرفًا، بلا وسوم ASS) + قاعدة 5–7 مشاهد.
- `lib/caption_check.py::sentence_issue` للغة بوابة المتابعة.

المدخل: سكريبت كامل قاموسًا::

    {"title": ..., "hook": ..., "text": ...,
     "moral": ..., "closing_question": ...,
     "parts": 1,                # عدد صحيح 1–3 أو قائمة أجزاء
     "scenes": [...],           # اختياري: مشاهد معلنة
     "part_endings": [...],     # اختياري: نهاية كل جزء نصًا
     "timed_phrases": [...],    # اختياري: عبارات موقوتة
     "narration_audio": ...,    # اختياري: مسار صوت سرد (wav)
     "narration_wpm": ...,      # اختياري: معدل سرد يمرره المشغّل
     "narration_duration_seconds": ...}  # اختياري: مدة مقاسة

المدة المقدّرة: تُحسب فقط عند توفر صوت سرد أو عبارات موقوتة
أو معدل سرد يمرره المشغّل صراحةً؛ وإلا تبقى «غير مقاسة» — بلا
اختراع أرقام. لا معدل سرد افتراضي مخترع في هذه الوحدة: أي رقم
بلا مصدر يُذكر «غير مقاس».

قاعدة نهايات الأجزاء: عند `parts > 1` يجب أن ينتهي كل جزء
وسيط (كل جزء إلا الأخير) بهوك/سؤال لا بحلّ؛ فالجزء الأخير
وحده هو الذي يحلّ العقدة بالعبرة. نهايات الأجزاء تُؤخذ من
`part_endings` أو من `parts` كقائمة أجزاء أو من مشاهد تحمل
مفتاح `part`؛ وبلا أي منها تكون النهايات «غير مقاسة» فلا
تجتاز البوابة (بوابة لا تمرّر ما لا تستطيع التحقق منه).

رموز الخروج (مثل `seo-check`): 0 سليم، 1 تقرير غير سليم
(بوابة قبل الإنتاج)، 2 مدخل فاسد.

التوصيل كأمر `script-check` في `studio.py` ليس من هذه الوحدة؛
`cmd_script_check(args)` جاهزة للتوصيل بنمط `cmd_*` المتبع.
"""
import argparse
import json
import os
import re
import wave

from lib import caption_check
from lib import dna as dna_lib
from lib import ideas as ideas_lib

# نطاق مدة الشورت بالثواني (صيغة الاستوديو: 40–60 ثانية).
MIN_DURATION_SECONDS = 40
MAX_DURATION_SECONDS = 60
# عدد المشاهد/النبضات لشورت 40–60ث (قواعد `lib/ideas.py`).
MIN_SCENES = 5
MAX_SCENES = 7
# عتبة الهوك: أقل من 6 «ضعيف — يُستبعد» حسب جدول maquina.
HOOK_MIN_SCORE = 6

# كلمات تنهي الجزء بحلّ (عبرة/ختام) مقابل هوك/سؤال.
_PAYOFF_WORDS = ("العبرة", "الدرس", "تعلم", "فهم", "عرف",
                 "ندم", "تاب", "رجع", "حصد", "في النهاية",
                 "أخيرًا", "وهكذا")
# ذكر موسيقى = مخالفة صيغة (الاستوديو بلا موسيقى — الافتراضي
# القائم؛ تغييره يحتاج دليلًا حسب تفويض 2026-11-26 10:09،
# ولا دليل هنا فيُبقي الفحص على الافتراضي).
_MUSIC_MARKERS = ("موسيق", "موسيقا", "معزوفة", "music",
                  "soundtrack")

_QUESTION_WORDS = dna_lib.QUESTION_WORDS
_SUSPENSE_WORDS = dna_lib.SUSPENSE_WORDS

# معرّفات مشاكل ثابتة (نمط `caption_check`): الفئة ←
# (المعرّف، الخطورة).
_ISSUE_META = {
    "hook_weak": ("SC-HOOK-001", "high"),
    "hook_digit": ("SC-HOOK-002", "high"),
    "hook_rules": ("SC-HOOK-003", "high"),
    "moral": ("SC-MORAL-001", "high"),
    "question": ("SC-QUESTION-001", "high"),
    "scenes": ("SC-SCENES-001", "high"),
    "follow_gate": ("SC-FOLLOW-001", "high"),
    "music": ("SC-MUSIC-001", "high"),
    "parts_ending": ("SC-PARTS-001", "high"),
    "parts_unmeasured": ("SC-PARTS-002", "medium"),
    "duration": ("SC-DURATION-001", "medium"),
}


class ScriptCheckError(Exception):
    """مدخل فاسد لبوابة السكريبت (رسالته عربية)."""


def _is_str(value):
    return isinstance(value, str)


def _clean(value):
    return value.strip() if _is_str(value) else ""


def _words(text):
    return (text or "").split()


def _tokens(text):
    return [t for t in re.split(r"[\s،؛:()\"'«»!?؟.\-…/]+",
                                text or "") if t]


def _is_question(text):
    """هل النص سؤال (علامة استفهام أو أداة استفهام)؟"""
    text = text or ""
    if "؟" in text or "?" in text:
        return True
    return any(tok in _QUESTION_WORDS for tok in _tokens(text))


def _has_suspense(text):
    return any(dna_lib._word_in(text, w) for w in _SUSPENSE_WORDS)


def _ending_kind(ending):
    """صنّف نهاية جزء: "hook" (هوك/سؤال) أو "resolution"
    (حلّ/عبرة) أو "plain" (لا هذا ولا ذاك)."""
    ending = (ending or "").strip()
    if not ending:
        return "plain"
    if _is_question(ending) or _has_suspense(ending):
        return "hook"
    if any(w in ending for w in _PAYOFF_WORDS):
        return "resolution"
    return "plain"


def _scene_text(scene):
    """نص مشهد واحد: سلسلة نصية أو قاموس بمفتاح نصي."""
    if _is_str(scene):
        return scene.strip()
    if isinstance(scene, dict):
        for key in ("text", "prompt", "narration"):
            value = scene.get(key)
            if _is_str(value) and value.strip():
                return value.strip()
    return ""


def _count_scenes(script):
    """عدد المشاهد/النبضات + مصدر العد.

    مشاهد معلنة في `scenes` أولًا؛ وإلا جمل نص السكريبت
    (تقسيم `caption_check.split_sentences`) كبديل تقريبي.
    """
    scenes = script.get("scenes")
    if isinstance(scenes, list):
        count = sum(1 for s in scenes if _scene_text(s))
        return count, "مشاهد معلنة"
    sentences = caption_check.split_sentences(script.get("text") or "")
    return len(sentences), "جمل النص"


def _part_endings(script):
    """نهايات الأجزاء نصًا (أو None إن تعذّر اشتقاقها).

    المصادر بالترتيب: `part_endings`، ثم `parts` كقائمة أجزاء،
    ثم مشاهد مجمّعة بمفتاح `part`.
    """
    endings = script.get("part_endings")
    if isinstance(endings, list) and endings:
        return [_clean(e) for e in endings if _is_str(e) and e.strip()]
    parts = script.get("parts")
    if isinstance(parts, list) and parts:
        out = []
        for part in parts:
            if _is_str(part):
                sents = caption_check.split_sentences(part)
                out.append(sents[-1] if sents else part.strip())
            elif isinstance(part, dict):
                ending = part.get("ending")
                if _is_str(ending) and ending.strip():
                    out.append(ending.strip())
                else:
                    text = _clean(part.get("text"))
                    sents = caption_check.split_sentences(text)
                    out.append(sents[-1] if sents else text)
        return [e for e in out if e]
    scenes = script.get("scenes")
    if isinstance(scenes, list) and scenes:
        grouped = {}
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            part_no = scene.get("part")
            text = _scene_text(scene)
            if isinstance(part_no, int) and not isinstance(part_no, bool) \
                    and text:
                grouped.setdefault(part_no, []).append(text)
        if grouped:
            return [grouped[k][-1] for k in sorted(grouped)]
    return None


def _part_count(script):
    """عدد الأجزاء: من `parts` (عدد أو قائمة) — 1 افتراضيًا."""
    parts = script.get("parts")
    if parts is None:
        return 1
    if isinstance(parts, list):
        return len(parts)
    return parts


def _parse_time(value):
    """حوّل زمنًا إلى ثوانٍ: رقم، أو «MM:SS.cc» / «HH:MM:SS.cc»."""
    if isinstance(value, bool):
        raise ScriptCheckError("زمن غير صالح في العبارات الموقوتة: %r"
                               % (value,))
    if isinstance(value, (int, float)):
        return float(value)
    if _is_str(value):
        text = value.strip()
        try:
            return float(text)
        except ValueError:
            pass
        parts = text.split(":")
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            raise ScriptCheckError(
                "زمن غير صالح في العبارات الموقوتة: %s" % value)
        if len(nums) == 2:
            return nums[0] * 60 + nums[1]
        if len(nums) == 3:
            return nums[0] * 3600 + nums[1] * 60 + nums[2]
    raise ScriptCheckError("زمن غير صالح في العبارات الموقوتة: %r"
                           % (value,))


def _phrases_duration(phrases):
    """المدة من عبارات موقوتة: آخر نهاية − أول بداية.

    كل عبارة قاموس بمفاتيح start/end (أو start_seconds /
    end_seconds أو start_ms / end_ms) أو زوج [بداية، نهاية].
    """
    starts = []
    ends = []
    for phrase in phrases:
        if isinstance(phrase, dict):
            start = None
            end = None
            for s_key, e_key, scale in (
                    ("start", "end", 1.0),
                    ("start_seconds", "end_seconds", 1.0),
                    ("start_ms", "end_ms", 0.001)):
                if s_key in phrase and e_key in phrase:
                    start = _parse_time(phrase[s_key]) * scale
                    end = _parse_time(phrase[e_key]) * scale
                    break
            if start is None or end is None:
                raise ScriptCheckError(
                    "عبارة موقوتة بلا بداية/نهاية: %r" % (phrase,))
        elif isinstance(phrase, (list, tuple)) and len(phrase) == 2:
            start = _parse_time(phrase[0])
            end = _parse_time(phrase[1])
        else:
            raise ScriptCheckError(
                "عبارة موقوتة بصيغة غير معروفة: %r" % (phrase,))
        if end <= start:
            raise ScriptCheckError(
                "عبارة موقوتة نهايتها قبل بدايتها: %r" % (phrase,))
        starts.append(start)
        ends.append(end)
    if not starts:
        return None
    return round(max(ends) - min(starts), 2)


def _wav_duration(path):
    """مدة ملف WAV بالثواني عبر المكتبة القياسية فقط."""
    try:
        with wave.open(path, "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            if rate <= 0:
                return None
            return round(frames / rate, 2)
    except (wave.Error, OSError, EOFError):
        return None


def estimate_duration(script, timed_phrases=None, narration_audio=None,
                      narration_wpm=None,
                      narration_duration_seconds=None):
    """قدّر مدة السرد بالثواني.

    يرجع (المدة أو None، المصدر أو None). المصادر بالترتيب:
    عبارات موقوتة، ثم صوت سرد (ملف wav أو مدة مقاسة يمررها
    المشغّل)، ثم معدل سرد يمرره المشغّل مع عدد كلمات النص.
    بلا أي منها: (None, None) — «غير مقاسة»، بلا اختراع أرقام.
    """
    phrases = timed_phrases if timed_phrases is not None \
        else script.get("timed_phrases")
    if phrases is not None:
        if not isinstance(phrases, list):
            raise ScriptCheckError(
                "العبارات الموقوتة يجب أن تكون قائمة")
        if phrases:
            return _phrases_duration(phrases), "timed_phrases"
    audio = narration_audio if narration_audio is not None \
        else script.get("narration_audio")
    duration = narration_duration_seconds \
        if narration_duration_seconds is not None \
        else script.get("narration_duration_seconds")
    if duration is not None:
        if isinstance(duration, bool) \
                or not isinstance(duration, (int, float)) \
                or duration <= 0:
            raise ScriptCheckError(
                "مدة السرد المقاسة يجب أن تكون رقمًا موجبًا")
        return round(float(duration), 2), "narration_audio"
    if audio is not None:
        if not _is_str(audio):
            raise ScriptCheckError("مسار صوت السرد يجب أن يكون نصًا")
        path = os.path.expanduser(audio)
        if not os.path.isfile(path):
            raise ScriptCheckError(
                "ملف صوت السرد غير موجود: %s" % audio)
        if path.lower().endswith(".wav"):
            measured = _wav_duration(path)
            if measured is not None:
                return measured, "narration_audio"
        return None, None
    wpm = narration_wpm if narration_wpm is not None \
        else script.get("narration_wpm")
    if wpm is not None:
        if isinstance(wpm, bool) or not isinstance(wpm, (int, float)) \
                or wpm <= 0:
            raise ScriptCheckError(
                "معدل السرد يجب أن يكون رقمًا موجبًا (كلمة/دقيقة)")
        words = len(_words(script.get("text") or ""))
        if words == 0:
            return None, None
        return round(words / float(wpm) * 60.0, 2), "narration_wpm"
    return None, None


def validate_script(script):
    """تحقق من سلامة بنية المدخل. يرفع ScriptCheckError إن فاسد.

    الفاسد: ليس قاموسًا؛ أو عنوان/هوك/نص غائب أو ليس نصًا أو
    فارغ؛ أو عبرة/سؤال ختامي ليس نصًا إن وُجد؛ أو `parts` ليس
    عددًا صحيحًا 1–3 ولا قائمة أجزاء؛ أو `scenes` ليس قائمة؛
    أو مشهد ليس نصًا ولا قاموسًا نصيًا. أما العبرة الغائبة
    والسؤال الختامي الغائب فليسا مدخلًا فاسدًا بل فحصان
    فاشلان (يظهران في التقرير برمز خروج 1).
    """
    if not isinstance(script, dict):
        raise ScriptCheckError("المدخل يجب أن يكون قاموس سكريبت")
    for field in ("title", "hook", "text"):
        value = script.get(field)
        if not _is_str(value) or not value.strip():
            raise ScriptCheckError(
                "حقل %s غائب أو فارغ — السكريبت يحتاج عنوانًا "
                "وهوكًا ونصًا" % field)
    for field in ("moral", "closing_question"):
        value = script.get(field)
        if value is not None and not _is_str(value):
            raise ScriptCheckError(
                "حقل %s يجب أن يكون نصًا" % field)
    parts = script.get("parts")
    if parts is not None:
        if isinstance(parts, bool):
            raise ScriptCheckError("عدد الأجزاء يجب أن يكون عددًا "
                                   "صحيحًا 1–3 أو قائمة أجزاء")
        if isinstance(parts, int):
            if parts < 1 or parts > 3:
                raise ScriptCheckError(
                    "عدد الأجزاء يجب أن يكون بين 1 و3 (وصل: %s)"
                    % parts)
        elif isinstance(parts, list):
            if not parts:
                raise ScriptCheckError("قائمة الأجزاء فارغة")
            for part in parts:
                if not _is_str(part) and not isinstance(part, dict):
                    raise ScriptCheckError(
                        "كل جزء يجب أن يكون نصًا أو قاموسًا")
        else:
            raise ScriptCheckError(
                "عدد الأجزاء يجب أن يكون عددًا صحيحًا 1–3 أو "
                "قائمة أجزاء")
    scenes = script.get("scenes")
    if scenes is not None:
        if not isinstance(scenes, list):
            raise ScriptCheckError("المشاهد يجب أن تكون قائمة")
        for scene in scenes:
            if not _is_str(scene) and not isinstance(scene, dict):
                raise ScriptCheckError(
                    "كل مشهد يجب أن يكون نصًا أو قاموسًا")
            if isinstance(scene, dict) and not _scene_text(scene):
                raise ScriptCheckError(
                    "مشهد قاموسي بلا نص (text/prompt/narration)")
    endings = script.get("part_endings")
    if endings is not None and not isinstance(endings, list):
        raise ScriptCheckError("نهايات الأجزاء يجب أن تكون قائمة")


def _check(name, ok, detail):
    return {"name": name, "ok": ok, "detail": detail}


def _issue(category, message, fix):
    fid, severity = _ISSUE_META[category]
    return {"id": fid, "severity": severity, "message": message,
            "fix": fix}


def check_script(script, timed_phrases=None, narration_audio=None,
                 narration_wpm=None, narration_duration_seconds=None):
    """افحص سكريبتًا كاملًا قبل الإنتاج.

    يرجع قاموس التقرير: {ok, title, hook_score, scene_count,
    scene_source, estimated_duration_seconds, duration_source,
    checks, issues}. يرفع ScriptCheckError على مدخل فاسد.
    """
    validate_script(script)
    title = _clean(script.get("title"))
    hook = _clean(script.get("hook"))
    text = _clean(script.get("text"))
    moral = _clean(script.get("moral"))
    question = _clean(script.get("closing_question"))
    checks = []
    issues = []

    # 1) الهوك: درجة dna + قواعد ideas.
    try:
        hook_score = dna_lib.score_hook(hook, story_text=text)
    except dna_lib.DnaError as e:
        raise ScriptCheckError(str(e))
    hook_ok = True
    hook_detail = "الهوك %d/%d (%s)" % (
        hook_score["total"], hook_score["max"], hook_score["verdict"])
    if hook and hook[0] in "0123456789٠١٢٣٤٥٦٧٨٩":
        hook_ok = False
        issues.append(_issue(
            "hook_digit",
            "الهوك يبدأ برقم «%s» — الأرقام كلمات لا أرقام في "
            "بداية السطر" % hook[:30],
            "أعد كتابة الرقم كلمة (مثال: «ثلاثة أخطاء…» بدل "
            "«3 أخطاء…») — انظر lib/dna.py::normalize_hook."))
    elif not ideas_lib.valid_hook(hook):
        hook_ok = False
        issues.append(_issue(
            "hook_rules",
            "الهوك يخالف قواعد الأسلوب (أطول من 140 حرفًا أو فيه "
            "وسوم ASS)",
            "اجعله جملة واحدة صادمة ≤140 حرفًا بلا { } أو \\."))
    if hook_score["total"] < HOOK_MIN_SCORE:
        hook_ok = False
        issues.append(_issue(
            "hook_weak",
            "الهوك ضعيف: %d/%d — أقل من 6 (يُستبعد حسب جدول "
            "maquina)" % (hook_score["total"], hook_score["max"]),
            "أعد صياغة الهوك بسؤال + حقيقة محددة + كلمة صراع "
            "في جملة واحدة."))
    checks.append(_check("الهوك", hook_ok, hook_detail))

    # 2) العبرة حاضرة وصريحة.
    if moral:
        in_text = moral in text
        detail = "العبرة حاضرة: «%s»" % moral
        detail += " — وتظهر في النص" if in_text else \
            " — ولا تظهر حرفيًا في النص؛ تأكد أنها تُقال في " \
            "المشهد الأخير"
        checks.append(_check("العبرة", True, detail))
    else:
        checks.append(_check(
            "العبرة", False, "العبرة غائبة — لا عبرة صريحة في السكريبت"))
        issues.append(_issue(
            "moral",
            "العبرة غائبة — السكريبت بلا عبرة صريحة",
            "أضف عبرة واضحة في جملة (مثال: «الظلم مهما طال ليله، "
            "الحق بيظهر») وقلها في المشهد الأخير."))

    # 3) سؤال ختامي محيّر حاضر.
    if question and _is_question(question):
        checks.append(_check(
            "سؤال الختام", True,
            "سؤال الختام حاضر: «%s»" % question))
    elif question:
        checks.append(_check(
            "سؤال الختام", False,
            "سؤال الختام ليس سؤالًا: «%s» — بلا علامة استفهام "
            "ولا أداة استفهام" % question))
        issues.append(_issue(
            "question",
            "سؤال الختام ليس سؤالًا محيّرًا",
            "اختم بسؤال محيّر بعلامة استفهام (مثال: «لو كنت مكانه، "
            "كنت هتعمل إيه؟»)."))
    else:
        checks.append(_check(
            "سؤال الختام", False,
            "سؤال الختام غائب — لا سؤال يغلق السكريبت"))
        issues.append(_issue(
            "question",
            "سؤال الختام غائب",
            "أضف سؤالًا محيّرًا في الختام (مثال: «لو كنت مكانه، "
            "كنت هتعمل إيه؟»)."))

    # 4) عدد المشاهد/النبضات 5–7.
    scene_count, scene_source = _count_scenes(script)
    if MIN_SCENES <= scene_count <= MAX_SCENES:
        checks.append(_check(
            "عدد المشاهد", True,
            "%d مشاهد (%s) — ضمن 5–7" % (scene_count, scene_source)))
    else:
        checks.append(_check(
            "عدد المشاهد", False,
            "%d مشاهد (%s) — خارج 5–7 لشورت 40–60ث"
            % (scene_count, scene_source)))
        issues.append(_issue(
            "scenes",
            "عدد المشاهد %d خارج 5–7 (%s)"
            % (scene_count, scene_source),
            "قسّم السكريبت إلى 5–7 مشاهد/نبضات (مشهد ≈ 8 ثوانٍ) "
            "أو ادمج الزائد."))

    # 5) لغة بوابة متابعة (عبر كل نص السكريبت).
    full_text = "\n".join(
        part for part in (hook, text, moral, question) if part)
    scenes = script.get("scenes")
    if isinstance(scenes, list):
        full_text += "\n" + "\n".join(
            _scene_text(s) for s in scenes if _scene_text(s))
    gate_sentences = []
    for sentence in caption_check.split_sentences(full_text):
        found = caption_check.sentence_issue(sentence)
        if found:
            gate_sentences.append((sentence, found[1]))
    if gate_sentences:
        detail = "؛ ".join("«%s» (%s)" % (s, r)
                           for s, r in gate_sentences)
        checks.append(_check("بوابة المتابعة", False, detail))
        issues.append(_issue(
            "follow_gate",
            "لغة بوابة متابعة في %d جملة: %s"
            % (len(gate_sentences), detail),
            "احذف الشرط؛ والدعوة اللطيفة الوحيدة المسموحة هي "
            "بوقت معلن («الجزء الثاني بكرة 7 مساءً — اعمل متابعة "
            "عشان يوصلك أول ما ينزل») — انظر "
            "lib/caption_check.py::approved_invite."))
    else:
        checks.append(_check(
            "بوابة المتابعة", True, "بلا لغة بوابة متابعة"))

    # 6) لا ذكر موسيقى (الصيغة بلا موسيقى).
    lowered = full_text.lower()
    music_hits = sorted({m for m in _MUSIC_MARKERS if m in lowered})
    if music_hits:
        checks.append(_check(
            "الموسيقى", False,
            "ذُكرت موسيقى في السكريبت: %s"
            % "، ".join(music_hits)))
        issues.append(_issue(
            "music",
            "ذكر موسيقى في السكريبت (%s) — الصيغة بلا موسيقى"
            % "، ".join(music_hits),
            "احذف أي ذكر للموسيقى من السكريبت؛ فالإنتاج بلا "
            "موسيقى إطلاقًا."))
    else:
        checks.append(_check("الموسيقى", True, "بلا ذكر موسيقى"))

    # 7) نهايات الأجزاء (عند parts > 1).
    parts_n = _part_count(script)
    if parts_n <= 1:
        checks.append(_check(
            "نهايات الأجزاء", True, "جزء واحد — لا نهايات وسيطة"))
    else:
        endings = _part_endings(script)
        if endings is None or len(endings) < parts_n:
            checks.append(_check(
                "نهايات الأجزاء", False,
                "نهايات الأجزاء غير مقاسة — زوّد `part_endings` "
                "(نهاية كل جزء) أو `parts` كقائمة أجزاء"))
            issues.append(_issue(
                "parts_unmeasured",
                "نهايات الأجزاء غير مقاسة (%d أجزاء بلا نهايات "
                "معلنة)" % parts_n,
                "مرّر `part_endings` — نهاية نصية لكل جزء — أو "
                "`parts` كقائمة أجزاء بنص كل جزء."))
        else:
            bad = []
            for i, ending in enumerate(endings[:parts_n - 1], 1):
                kind = _ending_kind(ending)
                if kind != "hook":
                    bad.append((i, kind, ending))
            if bad:
                detail = "؛ ".join(
                    "الجزء %d ينتهي بـ%s: «%s»" % (
                        i, "حلّ" if kind == "resolution" else "نهاية "
                        "عادية بلا هوك/سؤال", ending[:60])
                    for i, kind, ending in bad)
                checks.append(_check("نهايات الأجزاء", False, detail))
                issues.append(_issue(
                    "parts_ending",
                    "أجزاء وسيطة تنتهي بحلّ لا بهوك/سؤال: %s" % detail,
                    "اختم كل جزء وسيط بهوك أو سؤال محيّر (مثال: "
                    "«تفتكروا إيه اللي حصل بعدها؟») واترك الحلّ "
                    "للجزء الأخير."))
            else:
                checks.append(_check(
                    "نهايات الأجزاء", True,
                    "كل جزء وسيط ينتهي بهوك/سؤال (%d أجزاء)"
                    % parts_n))

    # 8) المدة المقدّرة (عند توفر مصدر قياس فقط).
    duration, duration_source = estimate_duration(
        script, timed_phrases=timed_phrases,
        narration_audio=narration_audio, narration_wpm=narration_wpm,
        narration_duration_seconds=narration_duration_seconds)
    if duration is None:
        checks.append(_check(
            "المدة المقدّرة", None,
            "غير مقاسة — بلا صوت سرد أو عبارات موقوتة أو معدل "
            "سرد معطى"))
    elif MIN_DURATION_SECONDS <= duration <= MAX_DURATION_SECONDS:
        checks.append(_check(
            "المدة المقدّرة", True,
            "%.1f ثانية (%s) — ضمن 40–60 ثانية"
            % (duration, duration_source)))
    else:
        checks.append(_check(
            "المدة المقدّرة", False,
            "%.1f ثانية (%s) — خارج 40–60 ثانية"
            % (duration, duration_source)))
        issues.append(_issue(
            "duration",
            "المدة المقدّرة %.1f ثانية خارج 40–60 ثانية (%s)"
            % (duration, duration_source),
            "قصّر السكريبت أو طوّله ليقع بين 40 و60 ثانية."))

    ok = all(c["ok"] is not False for c in checks)
    return {
        "ok": ok,
        "title": title,
        "hook_score": hook_score,
        "scene_count": scene_count,
        "scene_source": scene_source,
        "estimated_duration_seconds": duration,
        "duration_source": duration_source,
        "checks": checks,
        "issues": issues,
    }


def format_report(result):
    """نص عربي لتقرير فحص السكريبت."""
    lines = ["== فحص السكريبت قبل الإنتاج ==",
             "العنوان: %s" % (result.get("title") or "؟"),
             "النتيجة: %s" % ("سليم — جاهز للإنتاج"
                             if result.get("ok")
                             else "غير سليم — لا تنتج قبل الإصلاح"),
             ""]
    hook = result.get("hook_score") or {}
    if hook:
        lines.append("الهوك: %s/%s (%s)"
                     % (hook.get("total"), hook.get("max"),
                        hook.get("verdict") or "؟"))
    lines.append("عدد المشاهد: %s (%s)"
                 % (result.get("scene_count"),
                    result.get("scene_source") or "؟"))
    duration = result.get("estimated_duration_seconds")
    if duration is None:
        lines.append("المدة المقدّرة: غير مقاسة (بلا صوت سرد أو "
                     "عبارات موقوتة أو معدل سرد معطى)")
    else:
        lines.append("المدة المقدّرة: %.1f ثانية (%s)"
                     % (duration, result.get("duration_source") or "؟"))
    lines.append("")
    lines.append("-- الفحوصات --")
    for check in result.get("checks", []):
        mark = "✓" if check["ok"] is True else \
            "✗" if check["ok"] is False else "؟"
        lines.append("  [%s] %s: %s"
                     % (mark, check["name"], check["detail"]))
    issues = result.get("issues") or []
    lines.append("")
    lines.append("-- المشاكل (%d) --" % len(issues))
    if not issues:
        lines.append("  بلا مشاكل — السكريبت جاهز للإنتاج.")
    for issue in issues:
        lines.append("  - [%s] %s" % (issue["id"], issue["message"]))
        lines.append("    الإصلاح: %s" % issue["fix"])
    return "\n".join(lines) + "\n"


def load_script_file(path):
    """اقرأ سكريبت JSON من ملف. يرفع ScriptCheckError إن فاسد."""
    try:
        with open(os.path.expanduser(path), encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ScriptCheckError("ملف السكريبت غير موجود: %s" % path)
    except (OSError, ValueError) as e:
        raise ScriptCheckError(
            "تعذّرت قراءة ملف السكريبت %s: %s" % (path, e))
    if not isinstance(data, dict):
        raise ScriptCheckError(
            "ملف السكريبت يجب أن يحوي قاموسًا واحدًا")
    return data


def to_json(result):
    """JSON خالص للتقرير (بلا أي سطر نصي قبله — درس v0.1.56)."""
    return json.dumps(result, ensure_ascii=False, indent=2)


def cmd_script_check(args):
    """أمر `script-check` الجاهز للتوصيل في `studio.py`.

    يتوقع `args`: ‏`script` (مسار ملف JSON)، واختياريًا `json`
    (اطبع JSON خالصًا بدل التقرير العربي)، و`timed_phrases`
    و`narration_audio` و`narration_wpm` و`narration_duration`
    (مسارات/قيم تمرَّر لـ `check_script`). يرجع رمز الخروج:
    0 سليم، 1 تقرير غير سليم، 2 مدخل فاسد.
    """
    as_json = bool(getattr(args, "json", False))
    try:
        script = load_script_file(getattr(args, "script", ""))
        timed_phrases = None
        timed_path = getattr(args, "timed_phrases", None)
        if timed_path:
            with open(os.path.expanduser(timed_path),
                      encoding="utf-8") as f:
                timed_phrases = json.load(f)
        result = check_script(
            script,
            timed_phrases=timed_phrases,
            narration_audio=getattr(args, "narration_audio", None),
            narration_wpm=getattr(args, "narration_wpm", None),
            narration_duration_seconds=getattr(
                args, "narration_duration", None))
    except ScriptCheckError as e:
        if as_json:
            print(json.dumps({"ok": False, "error": str(e)},
                             ensure_ascii=False, indent=2))
        else:
            print("خطأ في المدخل: %s" % e)
        return 2
    except (OSError, ValueError) as e:
        if as_json:
            print(json.dumps({"ok": False, "error": str(e)},
                             ensure_ascii=False, indent=2))
        else:
            print("خطأ في المدخل: %s" % e)
        return 2
    if as_json:
        print(to_json(result))
    else:
        print(format_report(result), end="")
    return 0 if result["ok"] else 1


def main(argv=None):
    """نقطة دخول سطر الأوامر المستقلة (للاختبار والتوصيل)."""
    parser = argparse.ArgumentParser(
        prog="script-check",
        description="بوابة سكريبت نصية قبل الإنتاج "
                    "(0 سليم، 1 غير سليم، 2 مدخل فاسد).")
    parser.add_argument("script", help="ملف سكريبت JSON")
    parser.add_argument("--json", action="store_true",
                        help="اطبع JSON خالصًا بدل التقرير العربي")
    parser.add_argument("--timed-phrases",
                        help="ملف JSON بعبارات موقوتة لتقدير المدة")
    parser.add_argument("--narration-audio",
                        help="ملف صوت سرد (wav) لتقدير المدة")
    parser.add_argument("--narration-wpm", type=float,
                        help="معدل سرد (كلمة/دقيقة) يمرره المشغّل")
    parser.add_argument("--narration-duration", type=float,
                        help="مدة سرد مقاسة بالثواني يمررها المشغّل")
    args = parser.parse_args(argv)
    return cmd_script_check(args)


if __name__ == "__main__":
    raise SystemExit(main())
