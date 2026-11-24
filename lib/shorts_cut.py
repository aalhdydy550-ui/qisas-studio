#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""تقطيع الفيديو الطويل إلى شورتات (نمط OpenShorts) — جولة v0.1.39 (أ2-5).

من فيديو طويل (8–12 دقيقة، أفقي 1280×720 أو عمودي) تُنتج
شورتات مرشحة 40–60 ثانية:

  (أ) اكتشاف المقاطع عبر فواصل الصمت/الكلام — يعيد استخدام
      `lib.check.detect_silences` (ffmpeg silencedetect عند
      -40 ديسيبل، نفس أداة فحص الجودة)؛ وإن مُرّرت عبارات
      موقوتة (ASS/whisper) تُستخدم حدودها أيضًا.
  (ب) تقييم كل مقطع بدرجة موثقة (انظر `score_window`).
  (ج) قصّ أفضل N مقطعًا (افتراضيًا 3) وإعادة تأطيرها إلى
      720×1280 عمودي عبر ffmpeg (scale+crop — نفس نمط
      إعادة التأطير في `lib.avatar_aspect`/`lib.trim`).
  (د) إرجاع قائمة بالمخرجات + تقرير عربي موجز.

الكابشنات: لكل شورت يُولَّد ملف ASS بعباراته مُزاحة إلى زمن
الشورت، بنفس نمط `lib.whisper_captions.phrases_to_ass`
(محاذاة 2 — أسفل الشاشة فقط، قاعدة المشروع الصارمة).
حرق الكابشنات داخل الفيديو نفسه خطوة لاحقة عند الربط
(فلتر subtitles) — الملف جاهز والفيديو بلا كابشنات محروقة
حتى ذلك الحين، والقاعدة (أسفل فقط) غير مكسورة.

TODO موثق — تتبّع الوجه الكامل (نمط OpenShorts):
  إعادة التأطير هنا مركزية (crop وسط الإطار) لا تتبع الوجه.
  تتبّع الوجه يحتاج كاشف وجوه (بلا اعتمادياته في المشروع
  الآن) وسيغيّر نافذة القص لكل ثانية؛ يُضاف كخيار
  `--face-track` لاحقًا إن تقرر، ولا يُنفَّذ نصفه هنا.
"""
import os
import subprocess

from lib import check as check_lib
from lib.avatar_aspect import validate_aspect

# حدود الشورت (نفس نطاق الشورت العمودي في lib.check).
SHORT_MIN_SECONDS = 40.0
SHORT_MAX_SECONDS = 60.0
DEFAULT_COUNT = 3
MAX_COUNT = 10
OUT_WIDTH = 720
OUT_HEIGHT = 1280
# عتبة الصمت وفاصل الدمج — نفس عتبة فحص الجودة (-40 ديسيبل).
SILENCE_NOISE_DB = -40
SILENCE_MIN_SECONDS = 0.5
# فجوة صمت قصيرة داخل جملة واحدة تُدمج ولا تقطع المقطع.
MERGE_GAP_SECONDS = 0.8
# أقصر كلام يُحتسب مقطعًا (أقل من ذلك ضجيج عابر).
MIN_SPEECH_SECONDS = 0.5
# سقف مدة الدخل (مثل سقف الفصل في lib.long_video).
MAX_INPUT_SECONDS = 3600.0

# أوزان الدرجة (مجموعها 1.0) — انظر score_window.
W_DENSITY = 0.50
W_HOOK = 0.30
W_COMPLETE = 0.20

# كلمات هوك/انقلاب في سرد القصص (مطابقة جزئية على نص العبارة).
HOOK_WORDS = ("فجأة", "صدم", "مفاجأة", "اكتشف", "تبين", "انقلب",
              "خان", "ظلم", "غدر", "سر", "مات", "عوض", "انتقم",
              "فإذا", "وإذا", "لكن")
# كلمات الانقلاب وحدها تعطي نصف نقاط الهوك إن لم تكن في البداية.
TWIST_WORDS = ("لكن", "فجأة", "انقلب", "اكتشف", "تبين", "فإذا")


class ShortsCutError(Exception):
    """خطأ في تقطيع الشورتات (رسالته عربية جاهزة للعرض)."""


def _has_word(text, words):
    return any(w in (text or "") for w in words)


def detect_speech_segments(duration, silences):
    """مكمل فترات الصمت داخل [0, duration] → مقاطع كلام.

    فترات صمت بلا نهاية تُغلق عند مدة الفيديو؛ وكلام أقصر من
    MIN_SPEECH_SECONDS يُهمل؛ وفجوات صمت أقصر من
    MERGE_GAP_SECONDS تُدمج (وقفة داخل جملة لا فاصل).
    يرجع [(start, end), ...] مرتبة وحتمية.
    """
    duration = float(duration)
    speech = []
    cursor = 0.0
    for start, end, _dur in sorted(silences):
        start = float(start)
        end = duration if end is None else float(end)
        if start > cursor and start - cursor >= MIN_SPEECH_SECONDS:
            speech.append((round(cursor, 3), round(start, 3)))
        cursor = max(cursor, end)
    if duration - cursor >= MIN_SPEECH_SECONDS:
        speech.append((round(cursor, 3), round(duration, 3)))
    merged = []
    for seg in speech:
        if merged and seg[0] - merged[-1][1] < MERGE_GAP_SECONDS:
            merged[-1] = (merged[-1][0], seg[1])
        else:
            merged.append(seg)
    return merged


def candidate_windows(segments, min_len=SHORT_MIN_SECONDS,
                      max_len=SHORT_MAX_SECONDS):
    """نوافذ مرشحة من مقاطع الكلام: كل نافذة تبدأ عند بداية
    مقطع كلام وتنتهي عند نهاية مقطع كلام، بطول ضمن
    [min_len, max_len].

    مقطع كلام واحد أطول من max_len يُقطع عند max_len (نافذة
    بحد نهاية غير مكتمل — تنعكس في درجتها). يرجع قائمة
    [(start, end, speech_seconds), ...] بلا تكرار.
    """
    windows = []
    seen = set()
    for i, (s_start, _s_end) in enumerate(segments):
        if _s_end - s_start > max_len:
            key = (round(s_start, 3), round(s_start + max_len, 3))
            if key not in seen:
                seen.add(key)
                windows.append((key[0], key[1], round(max_len, 3)))
            continue
        speech = 0.0
        for j in range(i, len(segments)):
            seg_start, seg_end = segments[j]
            end = seg_end
            if end - s_start > max_len:
                break
            speech += seg_end - seg_start
            if end - s_start >= min_len:
                key = (round(s_start, 3), round(end, 3))
                if key not in seen:
                    seen.add(key)
                    windows.append((key[0], key[1], round(speech, 3)))
    return windows


def score_window(window, segments, phrases=None):
    """درجة نافذة (0..1) — حتمية لنفس المدخلات.

    الدرجة = 0.50 × كثافة الكلام (ثواني الكلام ÷ مدة النافذة)
           + 0.30 × الهوك (1.0 إن احتوت أول عبارة في النافذة
             كلمة هوك؛ 0.5 إن احتوت أي عبارة كلمة انقلاب؛
             0.0 بلا عبارات أو بلا كلمة)
           + 0.20 × اكتمال الحدود (1.0 إن بدأت النافذة عند
             بداية مقطع كلام وانتهت عند نهايته؛ 0.5 إن طابقت
             جهة واحدة؛ 0.0 إن قُطعت من منتصف الكلام).

    يرجع (الدرجة، سبب عربي موجز).
    """
    start, end, speech = window
    length = end - start
    density = speech / length if length > 0 else 0.0
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
            hook_note = "انقلاب داخل المقطع"
    starts_ok = any(abs(s - start) < 0.05 for s, _e in segments)
    ends_ok = any(abs(e - end) < 0.05 for _s, e in segments)
    complete = 1.0 if (starts_ok and ends_ok) else (
        0.5 if (starts_ok or ends_ok) else 0.0)
    score = round(W_DENSITY * density + W_HOOK * hook
                  + W_COMPLETE * complete, 4)
    parts = ["كثافة كلام %.2f" % density]
    if hook_note:
        parts.append(hook_note)
    parts.append("حدود %s" % ("كاملة" if complete == 1.0 else
                              "نصف مكتملة" if complete == 0.5
                              else "مقطوعة من منتصف الكلام"))
    return score, " + ".join(parts)


def rank_windows(windows, segments, phrases=None):
    """رتّب النوافذ بالدرجة (الأعلى أولًا، ثم الأقدم عند التعادل)."""
    scored = []
    for w in windows:
        score, reason = score_window(w, segments, phrases)
        scored.append({"start": w[0], "end": w[1],
                       "duration": round(w[1] - w[0], 3),
                       "speech_seconds": w[2], "score": score,
                       "reason": reason})
    scored.sort(key=lambda c: (-c["score"], c["start"]))
    return scored


def reframe_vertical(input_path, output_path, start, duration,
                     timeout=600):
    """قصّ مقطع وأعد تأطيره إلى 720×1280 عمودي.

    scale يملأ الإطار ثم crop مركزي 720×1280 (للأفقي يُقص
    الجانبان؛ والعمودي الجاهز يمر كما هو). إعادة ترميز
    libx264 crf 20 + aac — قص دقيق بالإطار (لا نسخ بايتات
    مثل lib.trim لأن إعادة التأطير تستلزم إعادة الترميز).
    """
    validate_aspect(OUT_WIDTH, OUT_HEIGHT)
    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    vf = ("scale=%d:%d:force_original_aspect_ratio=increase,"
          "crop=%d:%d,setsar=1" % (OUT_WIDTH, OUT_HEIGHT,
                                   OUT_WIDTH, OUT_HEIGHT))
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", input_path,
           "-ss", "%s" % float(start), "-t", "%s" % float(duration),
           "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac",
           output_path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ShortsCutError("انتهت مهلة قص الشورت (%d ثانية)"
                             % timeout)
    except OSError as e:
        raise ShortsCutError("تعذر تشغيل ffmpeg: %s" % e)
    if r.returncode != 0:
        raise ShortsCutError("فشل ffmpeg في قص الشورت (رمز %d):\n%s"
                             % (r.returncode, (r.stderr or "")[-800:]))
    if not os.path.isfile(output_path):
        raise ShortsCutError("انتهى ffmpeg دون إنشاء الشورت: %s"
                             % output_path)
    return output_path


def shift_phrases(phrases, start, end):
    """عبارات داخل [start, end] مُزاحة إلى زمن الشورت ومقصوصة
    على حدوده (لملف ASS الخاص بالشورت)."""
    out = []
    for p in phrases or []:
        p_start, p_end = float(p["start"]), float(p["end"])
        if p_end <= start or p_start >= end:
            continue
        out.append({"start": round(max(p_start, start) - start, 3),
                    "end": round(min(p_end, end) - start, 3),
                    "text": p.get("text", "")})
    return out


def cut_shorts(video_path, out_dir, count=DEFAULT_COUNT, phrases=None,
               min_len=SHORT_MIN_SECONDS, max_len=SHORT_MAX_SECONDS):
    """قطّع فيديو طويل إلى أفضل `count` شورتات عمودية.

    يرجع قائمة قواميس، كل منها:
    {"output", "captions" (مسار ASS أو None)، "start"، "end"،
     "duration"، "score"، "reason"} مرتبة زمنيًا.
    فيديو بلا كلام كافٍ (صامت تمامًا مثلًا) يرجع قائمة فارغة
    — لا شورت يُنتج من صمت.
    """
    if not os.path.isfile(video_path):
        raise ShortsCutError("ملف الفيديو غير موجود: %s" % video_path)
    count = int(count)
    if count < 1 or count > MAX_COUNT:
        raise ShortsCutError("عدد الشورتات يجب أن يكون بين 1 و%d"
                             % MAX_COUNT)
    if float(min_len) <= 0 or float(max_len) < float(min_len):
        raise ShortsCutError("حدود مدة الشورت غير صالحة: %s–%s"
                             % (min_len, max_len))
    try:
        info = check_lib.probe(video_path)
    except check_lib.CheckError as e:
        raise ShortsCutError(str(e))
    duration = info["duration"]
    if duration > MAX_INPUT_SECONDS:
        raise ShortsCutError("مدة الفيديو فوق الحد الأقصى %d ثانية"
                             % int(MAX_INPUT_SECONDS))
    if duration < float(min_len):
        return []
    silences = check_lib.detect_silences(
        video_path, noise_db=SILENCE_NOISE_DB,
        min_seconds=SILENCE_MIN_SECONDS)
    segments = detect_speech_segments(duration, silences)
    windows = candidate_windows(segments, min_len=float(min_len),
                                max_len=float(max_len))
    ranked = rank_windows(windows, segments, phrases)
    # الأفضل أولًا، لكن أخرجها مرتبة زمنيًا بأسماء ثابتة.
    picked = sorted(ranked[:count], key=lambda c: c["start"])
    os.makedirs(out_dir, exist_ok=True)
    results = []
    for i, cand in enumerate(picked, 1):
        out_path = os.path.join(
            os.path.abspath(out_dir), "short-%02d.mp4" % i)
        reframe_vertical(video_path, out_path, cand["start"],
                         cand["duration"])
        ass_path = None
        if phrases:
            short_phrases = shift_phrases(phrases, cand["start"],
                                           cand["end"])
            if short_phrases:
                from lib.whisper_captions import phrases_to_ass
                ass_path = os.path.join(
                    os.path.abspath(out_dir), "short-%02d.ass" % i)
                with open(ass_path, "w", encoding="utf-8") as f:
                    f.write(phrases_to_ass(short_phrases))
        results.append({"output": out_path, "captions": ass_path,
                        "start": cand["start"], "end": cand["end"],
                        "duration": cand["duration"],
                        "score": cand["score"], "reason": cand["reason"]})
    return results


def format_report(results, source_path):
    """تقرير عربي موجز عن الشورتات المقطوعة."""
    lines = ["تقطيع شورتات من: %s" % source_path]
    if not results:
        lines.append("لا شورتات: الفيديو بلا كلام كافٍ لمقطع "
                     "40–60 ثانية (صامت أو مقاطع كلامه قصيرة).")
        return "\n".join(lines) + "\n"
    lines.append("عدد الشورتات: %d" % len(results))
    for i, r in enumerate(results, 1):
        lines.append("%d) %s — %.1f–%.1f ث (%.1f ث) — درجة %.2f "
                     "(%s)%s" % (
                         i, os.path.basename(r["output"]),
                         r["start"], r["end"], r["duration"], r["score"],
                         r["reason"],
                         " + كابشنات ASS" if r["captions"] else ""))
    lines.append("ملاحظة: الكابشنات في ملفات ASS أسفل الشاشة فقط؛ "
                 "حرقها داخل الفيديو خطوة لاحقة عند الربط.")
    return "\n".join(lines) + "\n"
