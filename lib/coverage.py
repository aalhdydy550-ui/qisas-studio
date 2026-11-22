#!/usr/bin/env python3
"""تأكيدات تغطية وحدود آمنة — جولة v0.1.37 (مقترح tinker رقم 3).

تعمل على بيان مصدر الفيديو (scenes بتوقيتات + مدة السرد)
وفترات الصمت المكتشفة من الصوت. تُستدعى من `check` فقط
عند وجود بيان فيه مشاهد موقَّتة؛ بلا بيان تُتخطى بصمت.

انحراف موثق عن صيغة التقرير الحرفية: «مجموع مدد المشاهد =
مدة الفيديو ±0.15ث» لا ينطبق حرفيًا على خط الإنتاج الحقيقي
(قيس على العنزة ج1: مجموع العبارات 54.246ث مقابل فيديو
56.96ث — فرق 2.7ث): العبارات تترك فجوات تنفس مقصودة
0.3ث بينها، والريندر يضيف حشو ~1ث، والبطاقات الختامية
9ث خارج السرد. القاعدة المنفذة تحفظ قصد الفحص — المشاهد
تبلّط السرد كاملًا بلا فجوة ولا تداخل — بسماحيات يقيسها
خط الإنتاج فعلًا: رأس ≤0.15ث، ذيل ≤0.5ث، فجوة بين
مشهدين ≤0.5ث، بلا تداخل.

تصحيح 2026-11-22 لقاعدة الحدود: الصيغة الأولى كانت تقارب
«حد داخل كلمة» بـ«حد ليس في صمت ≥0.3ث أو قربه» — فأعطت
إيجابًا كاذبًا على فيديو حقيقي (العنزة ج1: حد 48.93ث بين
كلمتي «إيه؟» و«الجزء» — بين كلمتين لا داخل كلمة — لكن
بلا صمت ≥0.3ث قربه لأن السرد متصل). القاعدة الآن حرفية:
إن حمل البيان توقيتات كلمات (عبارات `phrases` بـ`words`)
فالفشل فقط لحد يقع داخل كلمة (بسماحية 80ms من طرفيها)؛
وقاعدة الصمت بديل فقط عند غياب توقيتات الكلمات.
"""
from lib import check as check_lib

BOUNDARY_TOLERANCE = 0.08   # 80ms — حد مشهد داخل كلمة منطوقة
COVERAGE_HEAD_MAX = 0.15    # أول مشهد يبدأ بعد 0.15ث = رأس مفقود
COVERAGE_TAIL_MAX = 0.5     # آخر مشهد ينتهي قبل نهاية السرد بـ0.5ث
COVERAGE_GAP_MAX = 0.5      # فجوة بين مشهدين أكبر من 0.5ث = محتوى مفقود


def _timed_scenes(manifest):
    """مشاهد البيان ذات التوقيتات الرقمية، مرتبة بالبداية."""
    scenes = []
    for s in (manifest or {}).get("scenes") or []:
        try:
            start = float(s["start"])
            end = float(s["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if end > start:
            scenes.append({"start": start, "end": end,
                           "text": (s.get("text") or "")[:40]})
    scenes.sort(key=lambda x: x["start"])
    return scenes


def check_scene_coverage(manifest):
    """هل المشاهد تبلّط السرد كاملًا؟ يرجع (ok, detail, skipped).

    skipped=True إن بلا مشاهد موقَّتة أو بلا مدة سرد في البيان.
    """
    scenes = _timed_scenes(manifest)
    narration = ((manifest or {}).get("narration") or {}).get(
        "duration_seconds")
    if not scenes or narration is None:
        return (True, "بلا مشاهد موقَّتة أو مدة سرد في البيان — "
                "يُتخطى", True)
    try:
        narration = float(narration)
    except (TypeError, ValueError):
        return (True, "مدة سرد غير رقمية في البيان — يُتخطى", True)
    problems = []
    if scenes[0]["start"] > COVERAGE_HEAD_MAX:
        problems.append("أول مشهد يبدأ عند %.2fث (رأس مفقود)"
                        % scenes[0]["start"])
    tail = narration - scenes[-1]["end"]
    if tail > COVERAGE_TAIL_MAX:
        problems.append("آخر مشهد ينتهي عند %.2fث قبل نهاية السرد "
                        "(%.2fث) بفارق %.2fث"
                        % (scenes[-1]["end"], narration, tail))
    elif tail < -COVERAGE_TAIL_MAX:
        problems.append("آخر مشهد يتجاوز مدة السرد بـ %.2fث"
                        % (-tail))
    for prev, cur in zip(scenes, scenes[1:]):
        gap = cur["start"] - prev["end"]
        if gap > COVERAGE_GAP_MAX:
            problems.append("فجوة %.2fث بين مشهدين (%.2fث–%.2fث)"
                            % (gap, prev["end"], cur["start"]))
        elif gap < -BOUNDARY_TOLERANCE:
            problems.append("تداخل %.2fث بين مشهدين (%.2fث–%.2fث)"
                            % (-gap, prev["end"], cur["start"]))
    total = sum(s["end"] - s["start"] for s in scenes)
    detail = ("%d مشهدًا، مجموع المدد %.2fث، السرد %.2fث"
              % (len(scenes), total, narration))
    if problems:
        return (False, detail + " — " + "؛ ".join(problems), False)
    return (True, detail + " — التبليط سليم", False)


def _near_silence(moment, silences, tolerance=BOUNDARY_TOLERANCE):
    """هل اللحظة داخل صمت أو على بعد ≤tolerance من حدوده؟"""
    for start, end, _dur in silences:
        if end is None:
            end = start
        if start - tolerance <= moment <= end + tolerance:
            return True
    return False


def _word_spans(manifest):
    """كل توقيتات الكلمات من عبارات/مشاهد البيان (إن وُجدت).

    عبارات `phrases` تحمل `words` (من `build_phrases` في
    openmontage_stage أو `group_words_into_phrases` في
    whisper_captions أو فصول الفيديو الطويل) — قواميس
    {w/start/end} بالثواني. بلا كلمات يرجع [] فيُستخدم
    بديل الصمت.
    """
    spans = []
    for section in ((manifest or {}).get("phrases") or [],
                    (manifest or {}).get("scenes") or []):
        for item in section:
            for w in (item.get("words") or []):
                try:
                    start = float(w["start"])
                    end = float(w["end"])
                except (KeyError, TypeError, ValueError):
                    continue
                if end > start:
                    spans.append((start, end))
    return spans


def check_scene_boundaries(manifest, silences):
    """حدود المشاهد آمنة؟ حد نهاية عبارة يقع داخل كلمة منطوقة
    (بسماحية 80ms من طرفي الكلمة) → FAIL؛ حد على حدود كلمة
    (بين كلمتين) سليم حتى بلا صمت قابل للقياس.

    توقيتات الكلمات هي المرجع عند وجودها في البيان؛ وبلا
    كلمات يُستخدم بديل الصمت (حد في صمت ≥0.3ث أو على بعد
    ≤80ms من حدوده)؛ وبلا كلمات وبلا صمت مكتشف أصلًا (سرد
    متصل بلا توقف) يُتخطى — لا يمكن الحكم بلا بيانات.
    """
    scenes = _timed_scenes(manifest)
    if len(scenes) < 2:
        return (True, "مشهد واحد أو بلا مشاهد — لا حدود تُفحص", True)
    words = _word_spans(manifest)
    if words:
        bad = []
        for prev, cur in zip(scenes, scenes[1:]):
            boundary = prev["end"]
            for start, end in words:
                if (start + BOUNDARY_TOLERANCE < boundary
                        < end - BOUNDARY_TOLERANCE):
                    bad.append("%.2fث (داخل كلمة %.2fث–%.2fث)"
                               % (boundary, start, end))
                    break
        if bad:
            return (False,
                    "حدود مشاهد داخل كلمات منطوقة: %s"
                    % "، ".join(bad), False)
        return (True, "كل حدود المشاهد (%d) بين كلمات "
                "(لا حد داخل كلمة)" % (len(scenes) - 1), False)
    if not silences:
        return (True, "لا فواصل صمت مكتشفة في الصوت (سرد متصل) — "
                "يُتخطى", True)
    bad = []
    for prev, cur in zip(scenes, scenes[1:]):
        boundary = prev["end"]
        if not _near_silence(boundary, silences):
            bad.append("%.2fث" % boundary)
    if bad:
        return (False,
                "حدود مشاهد داخل كلام منطوق (بلا صمت قريب): %s"
                % "، ".join(bad), False)
    return (True, "كل حدود المشاهد (%d) في صمت أو قربه (≤80ms)"
            % (len(scenes) - 1), False)


def check_phrase_audio(manifest, silences):
    """هل لكل عبارة صوت؟ عبارة واقعة بالكامل داخل صمت = بلا صوت.

    بلا فواصل صمت مكتشفة تُتخطى (كل العبارات لها صوت حتمًا).
    """
    scenes = _timed_scenes(manifest)
    if not scenes:
        return (True, "بلا عبارات موقَّتة — يُتخطى", True)
    if not silences:
        return (True, "لا فواصل صمت — كل العبارات لها صوت", True)
    silent = []
    for s in scenes:
        for start, end, _dur in silences:
            if end is None:
                continue
            if start <= s["start"] and s["end"] <= end:
                silent.append("%.2fث–%.2fث «%s»"
                              % (s["start"], s["end"], s["text"]))
                break
    if silent:
        return (False,
                "عبارات بلا صوت (داخل صمت): %s" % "؛ ".join(silent),
                False)
    return (True, "كل العبارات (%d) لها صوت" % len(scenes), False)


def extra_checks(video_path, manifest):
    """كل تأكيدات التغطية/الحدود لفيديو له بيان.

    يرجع قائمة فحوصات بصيغة check_lib نفسها
    ({name, ok, detail}) — المُتخطى يُسجَّل ok مع ذكر السبب.
    """
    checks = []
    ok, detail, _sk = check_scene_coverage(manifest)
    checks.append({"name": "تغطية المشاهد", "ok": ok, "detail": detail})
    scenes = _timed_scenes(manifest)
    if len(scenes) >= 2:
        silences = check_lib.detect_silences(video_path, min_seconds=0.3)
        ok, detail, _sk = check_scene_boundaries(manifest, silences)
        checks.append({"name": "حدود المشاهد الآمنة", "ok": ok,
                       "detail": detail})
        ok, detail, _sk = check_phrase_audio(manifest, silences)
        checks.append({"name": "صوت العبارات", "ok": ok, "detail": detail})
    return checks
