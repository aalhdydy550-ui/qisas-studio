#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""تقطيع مشهدي لفيديو طويل إلى أجزاء 40–60 ثانية — جولة v0.1.58 (W2).

الفكرة (من نمط autoclip/clips-studio — الفكرة فقط، بلا نسخ كود):
قصّ الفيديو الطويل على حدود مشاهده نفسها، لا على نوافذ الصمت.

هذا ليس بديلًا عن `lib.shorts_cut` (v0.1.39) بل مكمّل له:
`shorts_cut` يقطع بنوافذ صمت وقد يقطع منتصف مشهد؛ هنا كل جزء
مشاهد كاملة فقط — يبدأ عند حد مشهد وينتهي عند حد مشهد — حتى
تقارن «فيديو كامل مقابل أجزاء» مستقبلًا (بداية/وسط/نهاية مكتملة).

المدخل: حدود المشاهد `[{start, end, title?}]` (من مخطط مشاهد
القصة أو مانيفست الفيديو — مفتاح العنوان `title` أو `scene`)
+ عبارات موقوتة اختيارية (ASS/whisper).

القواعد:
- تجميع مشاهد متتالية في أجزاء 40–60 ثانية؛ جزء أقصر من 40ث
  يُدمج مع التالي إن أمكن (أي دون تجاوز 60ث)، وإلا يُسجَّل
  «غير مكتمل» ولا يُحذف بصمت.
- مشهد واحد أطول من 60ث لا يمكن تقطيعه دون قطع منتصف المشهد،
  فيُسجَّل جزءًا «غير مكتمل» ولا يُقصّ منه شورت خارج الصيغة.
- هوك كل جزء من أول عبارة فيه (كلمات الهوك من
  `shorts_cut.HOOK_WORDS` — بلا تكرار لمنطقها).
- التنفيذ يعيد استخدام `shorts_cut.reframe_vertical` +
  `shorts_cut.shift_phrases` + `whisper_captions.phrases_to_ass`
  — بلا تكرار لمنطقهما. المخرج: شورت عمودي + ملف ASS مزاح لكل
  جزء مكتمل (كابشنات أسفل الشاشة فقط — محاذاة 2، قاعدة
  الصيغة الصارمة).

قدرة فقط: لا تُنتج فيديو تجربة هنا — القصة الطويلة ~3 دقائق
ما زالت بانتظار موافقة المستخدم.
"""
import os

from lib import check as check_lib
from lib.shorts_cut import (
    HOOK_WORDS,
    SHORT_MAX_SECONDS,
    SHORT_MIN_SECONDS,
    TWIST_WORDS,
    reframe_vertical,
    shift_phrases,
)
from lib.whisper_captions import phrases_to_ass

# نفس حدود الشورت في lib.shorts_cut.
PART_MIN_SECONDS = SHORT_MIN_SECONDS
PART_MAX_SECONDS = SHORT_MAX_SECONDS
# سماحية تقريب مدة الفيديو عند مقارنة نهاية آخر مشهد بها.
DURATION_TOLERANCE_SECONDS = 0.5
# سقف مدة الدخل (مثل سقف الفصل في lib.long_video).
MAX_INPUT_SECONDS = 3600.0

# أوزان درجة الجزء (مجموعها 1.0) — انظر score_part.
W_HOOK = 0.50
W_COMPLETE = 0.30
W_FIT = 0.20


class SceneShortsError(Exception):
    """خطأ في التقطيع المشهدي (رسالته عربية جاهزة للعرض)."""


def _scene_title(scene):
    return (scene.get("title") or scene.get("scene") or "").strip()


def _scene_duration(scene):
    return round(float(scene["end"]) - float(scene["start"]), 3)


def validate_scenes(scenes, duration):
    """تحقق من حدود المشاهد ضد مدة الفيديو؛ يرجع نسخة مرتبة.

    يرفع SceneShortsError عند: قائمة فارغة، أو مشهد بلا start/end
    أو نهايته قبل بدايته، أو بداية سالبة، أو تداخل بين مشهدين،
    أو نهاية بعد مدة الفيديو بأكثر من سماحية التقريب.
    نهاية آخر مشهد بعد المدة بقليل تُقصّ على المدة.
    """
    if not scenes:
        raise SceneShortsError("لا حدود مشاهد: مرّر قائمة مشاهد "
                               "غير فارغة [{start, end, title?}]")
    cleaned = []
    for i, scene in enumerate(scenes):
        try:
            start = float(scene["start"])
            end = float(scene["end"])
        except (KeyError, TypeError, ValueError):
            raise SceneShortsError(
                "المشهد %d بلا start/end صالحين: %s" % (i + 1, scene))
        if start < 0:
            raise SceneShortsError(
                "المشهد %d يبدأ قبل الصفر: %.3f" % (i + 1, start))
        if end <= start:
            raise SceneShortsError(
                "المشهد %d نهايته قبل بدايته: %.3f–%.3f"
                % (i + 1, start, end))
        if end > float(duration) + DURATION_TOLERANCE_SECONDS:
            raise SceneShortsError(
                "المشهد %d ينتهي بعد مدة الفيديو (%.1f ث): %.3f"
                % (i + 1, float(duration), end))
        cleaned.append({"start": round(start, 3),
                        "end": round(min(end, float(duration)), 3),
                        "title": _scene_title(scene)})
    cleaned.sort(key=lambda s: s["start"])
    for prev, cur in zip(cleaned, cleaned[1:]):
        if cur["start"] < prev["end"]:
            raise SceneShortsError(
                "مشهدان متداخلان: %.3f–%.3f و%.3f–%.3f"
                % (prev["start"], prev["end"], cur["start"], cur["end"]))
    return cleaned


def find_gaps(scenes, duration):
    """فترات الفيديو غير المغطاة بأي مشهد [(start, end), ...].

    فجوة قبل أول مشهد أو بين مشهدين أو بعد آخر مشهد — أي
    فجوة تُذكر ولا تُحذف بصمت في تقرير المقارنة.
    """
    gaps = []
    cursor = 0.0
    for scene in scenes:
        if scene["start"] - cursor > 0.001:
            gaps.append((round(cursor, 3), round(scene["start"], 3)))
        cursor = max(cursor, scene["end"])
    if float(duration) - cursor > 0.001:
        gaps.append((round(cursor, 3), round(float(duration), 3)))
    return gaps


def _hook_of(phrases, start, end):
    """نص أول عبارة داخل [start, end] (أو "" بلا عبارات)."""
    for p in phrases or []:
        if float(p["end"]) > start and float(p["start"]) < end:
            return (p.get("text") or "").strip()
    return ""


def _has_word(text, words):
    return any(w in (text or "") for w in words)


def score_part(part, phrases=None):
    """درجة جزء (0..1) — حتمية لنفس المدخلات.

    الدرجة = 0.50 × الهوك (1.0 إن احتوت أول عبارة في الجزء كلمة
             هوك من HOOK_WORDS؛ 0.5 إن احتوت أي عبارة كلمة
             انقلاب من TWIST_WORDS؛ 0.0 بلا عبارات أو بلا كلمة)
           + 0.30 × اكتمال الحدود (1.0 دائمًا هنا — الجزء
             مشاهد كاملة يبدأ وينتهي عند حدي مشهد)
           + 0.20 × ملاءمة المدة (1.0 إن كانت 40–60ث؛ وإلا
             نسبة جزئية: المدة÷40 للأقصر، و60÷المدة للأطول).

    يرجع (الدرجة، سبب عربي موجز).
    """
    start, end = part["start"], part["end"]
    length = end - start
    hook = 0.0
    hook_note = ""
    if phrases:
        inside = [p for p in phrases
                  if float(p["end"]) > start and float(p["start"]) < end]
        if inside and _has_word(inside[0].get("text", ""), HOOK_WORDS):
            hook = 1.0
            hook_note = "هوك في البداية"
        elif any(_has_word(p.get("text", ""), TWIST_WORDS)
                 for p in inside):
            hook = 0.5
            hook_note = "انقلاب داخل الجزء"
    complete = 1.0
    if PART_MIN_SECONDS <= length <= PART_MAX_SECONDS:
        fit = 1.0
        fit_note = "مدة ضمن 40–60ث"
    elif length < PART_MIN_SECONDS:
        fit = round(length / PART_MIN_SECONDS, 4)
        fit_note = "أقصر من 40ث"
    else:
        fit = round(PART_MAX_SECONDS / length, 4)
        fit_note = "أطول من 60ث"
    score = round(W_HOOK * hook + W_COMPLETE * complete
                  + W_FIT * fit, 4)
    parts = []
    if hook_note:
        parts.append(hook_note)
    parts.append("حدود مشهدية كاملة")
    parts.append(fit_note)
    return score, " + ".join(parts)


def plan_parts(scenes, duration, phrases=None,
               min_len=PART_MIN_SECONDS, max_len=PART_MAX_SECONDS):
    """جمّع مشاهد متتالية في أجزاء 40–60ث — مشاهد كاملة فقط.

    يرجع {"parts": [...], "gaps": [...], "duration": ...} حيث كل
    جزء: {"index"، "start"، "end"، "duration"، "scenes" (عناوين
    مشاهده)، "hook"، "score"، "reason"، "status" ("مكتمل" أو
    "غير مكتمل")}. جزء أقصر من 40ث يُدمج مع التالي إن أمكن
    (دون تجاوز 60ث)؛ وإن تعذّر يُسجَّل «غير مكتمل» ولا يُحذف.
    مشهد واحد أطول من 60ث جزء «غير مكتمل» بذاته.
    """
    if float(min_len) <= 0 or float(max_len) < float(min_len):
        raise SceneShortsError("حدود مدة الجزء غير صالحة: %s–%s"
                               % (min_len, max_len))
    scenes = validate_scenes(scenes, duration)
    parts = []
    i = 0
    while i < len(scenes):
        if _scene_duration(scenes[i]) > float(max_len):
            # مشهد واحد أطول من الحد — لا يُقطع منتصفه.
            part = {"index": len(parts) + 1,
                    "start": scenes[i]["start"],
                    "end": scenes[i]["end"],
                    "duration": _scene_duration(scenes[i]),
                    "scenes": [_scene_title(scenes[i])],
                    "status": "غير مكتمل"}
            part["hook"] = _hook_of(phrases, part["start"], part["end"])
            part["score"], part["reason"] = score_part(part, phrases)
            part["reason"] += " + مشهد واحد أطول من %.0fث — لا يمكن " \
                "تقسيمه دون قطع منتصف المشهد" % float(max_len)
            parts.append(part)
            i += 1
            continue
        j = i
        total = 0.0
        while (j < len(scenes)
               and total + _scene_duration(scenes[j]) <= float(max_len)):
            total += _scene_duration(scenes[j])
            j += 1
        part = {"index": len(parts) + 1,
                "start": scenes[i]["start"],
                "end": scenes[j - 1]["end"],
                "duration": round(total, 3),
                "scenes": [_scene_title(s) for s in scenes[i:j]],
                "status": ("مكتمل" if total >= float(min_len)
                           else "غير مكتمل")}
        part["hook"] = _hook_of(phrases, part["start"], part["end"])
        part["score"], part["reason"] = score_part(part, phrases)
        if part["status"] == "غير مكتمل":
            part["reason"] += " + أقصر من %.0fث ولا يمكن دمجه مع " \
                "التالي دون تجاوز %.0fث" % (float(min_len),
                                            float(max_len))
        parts.append(part)
        i = j
    return {"parts": parts,
            "gaps": find_gaps(scenes, duration),
            "duration": round(float(duration), 3)}


def cut_scene_shorts(video_path, scenes, out_dir, phrases=None,
                     min_len=PART_MIN_SECONDS,
                     max_len=PART_MAX_SECONDS):
    """قصّ فيديو طويل إلى أجزاء مشهدية عمودية 40–60ث.

    يرجع قائمة قواميس مرتبة زمنيًا، كل منها:
    {"index"، "output" (مسار mp4 أو None للجزء غير المكتمل)،
     "captions" (مسار ASS أو None)، "start"، "end"، "duration"،
     "scenes"، "hook"، "score"، "reason"، "status"}.
    الجزء غير المكتمل لا يُقصّ منه شورت (خارج الصيغة) لكنه
    يبقى في القائمة والتقرير — لا يُحذف بصمت.
    """
    if not os.path.isfile(video_path):
        raise SceneShortsError("ملف الفيديو غير موجود: %s" % video_path)
    try:
        info = check_lib.probe(video_path)
    except check_lib.CheckError as e:
        raise SceneShortsError(str(e))
    duration = info["duration"]
    if duration > MAX_INPUT_SECONDS:
        raise SceneShortsError("مدة الفيديو فوق الحد الأقصى %d ثانية"
                               % int(MAX_INPUT_SECONDS))
    plan = plan_parts(scenes, duration, phrases,
                      min_len=float(min_len), max_len=float(max_len))
    os.makedirs(out_dir, exist_ok=True)
    results = []
    for part in plan["parts"]:
        entry = dict(part)
        entry["output"] = None
        entry["captions"] = None
        if part["status"] != "مكتمل":
            results.append(entry)
            continue
        out_path = os.path.join(
            os.path.abspath(out_dir), "scene-part-%02d.mp4" % part["index"])
        reframe_vertical(video_path, out_path, part["start"],
                         part["duration"])
        entry["output"] = out_path
        if phrases:
            part_phrases = shift_phrases(phrases, part["start"],
                                          part["end"])
            if part_phrases:
                ass_path = os.path.join(
                    os.path.abspath(out_dir),
                    "scene-part-%02d.ass" % part["index"])
                with open(ass_path, "w", encoding="utf-8") as f:
                    f.write(phrases_to_ass(part_phrases))
                entry["captions"] = ass_path
        results.append(entry)
    return results


def format_comparison_report(results, source_path, duration,
                             full_hook=""):
    """تقرير مقارنة عربي: الفيديو الكامل مقابل الأجزاء.

    results: قائمة cut_scene_shorts (أو أجزاء plan_parts).
    full_hook: هوك الفيديو الكامل (أول عبارة فيه عادةً).
    يذكر: مدة الكامل وهوكه، عدد الأجزاء ومددها وهوكاتها
    ودرجاتها، والأجزاء غير المكتملة، والفجوات غير المغطاة.
    """
    lines = ["مقارنة تقطيع مشهدي من: %s" % source_path]
    lines.append("الفيديو الكامل: %.1f ث%s" % (
        float(duration),
        " — الهوك: %s" % full_hook if full_hook else ""))
    if not results:
        lines.append("لا أجزاء: لم تُمرَّر حدود مشاهد صالحة.")
        return "\n".join(lines) + "\n"
    complete = [r for r in results if r.get("status") == "مكتمل"]
    incomplete = [r for r in results if r.get("status") != "مكتمل"]
    lines.append("عدد الأجزاء: %d (%d مكتمل، %d غير مكتمل)"
                 % (len(results), len(complete), len(incomplete)))
    for r in results:
        scenes = " + ".join(s for s in r.get("scenes") or [] if s)
        lines.append("%d) %.1f–%.1f ث (%.1f ث) — %s — درجة %.2f "
                     "(%s)%s%s" % (
                         r["index"], r["start"], r["end"],
                         r["duration"], r["status"], r["score"],
                         r["reason"],
                         " — مشاهد: %s" % scenes if scenes else "",
                         " — الهوك: %s" % r["hook"] if r.get("hook")
                         else ""))
    covered = round(sum(r["duration"] for r in results), 1)
    lines.append("التغطية: %.1f ث من %.1f ث (%.0f%%)"
                 % (covered, float(duration),
                    100.0 * covered / float(duration)
                    if float(duration) > 0 else 0.0))
    return "\n".join(lines) + "\n"
