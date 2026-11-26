#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""مقاطع حركة مولّدة للفيديو الطويل — تخطيط مقاطع Wan/LTX من مانيفست.

يقرأ مانيفست الحركة (JSON أو CSV) ويحوّل كل مقطع مخطط إلى مقاطع
فيديو فعلية (توليد a أولًا ثم بداية التوليد b لباقي المدة — لأن
التوليدين مستقلان من نفس الإطار الأول وليسا استمرارًا)، مع رجوع
لتجميد آخر إطار أو صورة ثابتة عند غياب الملفات. لا يرفع استثناءً
عند غياب المقاطع أبدًا — الرجوع للصورة الثابتة مع تحذير هو السلوك.
"""
import csv
import json
import math
import os
import re
import subprocess

DEFAULT_GENERATION_SECONDS = 5.04
IMAGE_CLIP_SECONDS = 5.0
MAX_DURATION_SECONDS = 3600.0


class MotionError(Exception):
    """خطأ في مانيفست الحركة أو تخطيط مقاطعه (رسالته عربية)."""


def _natural_key(name):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", str(name))]


def _check_duration(value, what):
    """ارفض مدة غير رقمية أو غير منتهية أو ≤0 أو فوق السقف."""
    if isinstance(value, bool):
        raise MotionError("مدة %s غير صالحة: %s" % (what, value))
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise MotionError("مدة %s غير صالحة: %s" % (what, value))
    if not math.isfinite(value) or value <= 0:
        raise MotionError("مدة %s غير صالحة: %s" % (what, value))
    if value > MAX_DURATION_SECONDS:
        raise MotionError(
            "مدة %s فوق الحد الأقصى %d ثانية (وصلت %.1f)"
            % (what, int(MAX_DURATION_SECONDS), value))
    return value


def _take_from_gen_id(gen_id):
    """اشتقّ حرف التوليد (a/b) من معرّفه، وإلا ''."""
    m = re.search(r"-([A-Za-z])$", str(gen_id))
    return m.group(1) if m else ""


def _coverage_note_text():
    return ("توليدات مستقلة من نفس الإطار الأول — يُستخدم التوليد a "
            "أولًا ثم بداية التوليد b لباقي المدة، أو يُجمَّد آخر إطار "
            "في a عند غياب b")


def load_motion_manifest(path):
    """اقرأ مانيفست حركة (.json أو .csv) → قاموس موحّد.

    يرجع {"generation_seconds": float,
           "clips": {clip_id: {"generations": [gen_id...],
                               "duration_needed_s": float|None,
                               "coverage_note": str}},
           "generations": {gen_id: {"clip_id", "output_name", "scene",
                                    "slice", "take", "first_frame"}}}.
    """
    if not path or not isinstance(path, str):
        raise MotionError("مسار مانيفست الحركة غير صالح: %r" % (path,))
    if not os.path.isfile(path):
        raise MotionError("ملف مانيفست الحركة غير موجود: %s" % path)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        return _load_json_manifest(path)
    if ext == ".csv":
        return _load_csv_manifest(path)
    raise MotionError(
        "امتداد مانيفست الحركة غير مدعوم: %s (المسموح: .json أو .csv)"
        % ext)


def _load_json_manifest(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError) as e:
        raise MotionError("ملف مانيفست الحركة غير صالح (%s): %s"
                          % (path, e))
    if not isinstance(data, dict):
        raise MotionError("مانيفست الحركة يجب أن يكون كائن JSON: %s" % path)
    gen_seconds = data.get("generation_seconds") or DEFAULT_GENERATION_SECONDS
    try:
        gen_seconds = float(gen_seconds)
    except (TypeError, ValueError):
        raise MotionError("مدة التوليد في المانيفست غير صالحة: %r"
                          % (gen_seconds,))
    if not math.isfinite(gen_seconds) or gen_seconds <= 0:
        raise MotionError("مدة التوليد في المانيفست غير صالحة: %r"
                          % (gen_seconds,))
    raw_clips = data.get("clips")
    if not isinstance(raw_clips, list) or not raw_clips:
        raise MotionError("مانيفست الحركة بلا مقاطع: %s" % path)
    raw_gens = data.get("generations_list")
    generations = {}
    if isinstance(raw_gens, list):
        for g in raw_gens:
            if not isinstance(g, dict):
                continue
            gen_id = g.get("gen_id")
            if not gen_id:
                continue
            generations[str(gen_id)] = {
                "clip_id": g.get("clip_id"),
                "output_name": g.get("output_name"),
                "scene": g.get("scene") or "",
                "slice": g.get("slice") or "",
                "take": g.get("take") or _take_from_gen_id(gen_id),
                "first_frame": g.get("first_frame") or "",
            }
    clips = {}
    for c in raw_clips:
        if not isinstance(c, dict) or not c.get("clip_id"):
            continue
        clip_id = str(c["clip_id"])
        gens = [str(g) for g in (c.get("generations") or [])]
        if not gens:
            raise MotionError(
                "المقطع %s في المانيفست بلا توليدات" % clip_id)
        for gen_id in gens:
            if gen_id not in generations:
                # توليد مذكور في المقطع بلا صف في generations_list:
                # ابنِ صفه من المعرّف نفسه.
                generations[gen_id] = {
                    "clip_id": clip_id,
                    "output_name": "%s.mp4" % gen_id,
                    "scene": "",
                    "slice": c.get("slice") or "",
                    "take": _take_from_gen_id(gen_id),
                    "first_frame": "",
                }
        dur = c.get("duration_needed_s")
        if dur is not None:
            try:
                dur = float(dur)
            except (TypeError, ValueError):
                raise MotionError(
                    "مدة المقطع %s في المانيفست غير صالحة: %r"
                    % (clip_id, dur))
        clips[clip_id] = {
            "generations": gens,
            "duration_needed_s": dur,
            "coverage_note": c.get("coverage_note") or "",
        }
    if not clips:
        raise MotionError("مانيفست الحركة بلا مقاطع صالحة: %s" % path)
    for gen_id, g in generations.items():
        if not g.get("output_name"):
            raise MotionError(
                "التوليد %s في المانيفست بلا اسم ملف (output_name)"
                % gen_id)
    return {"generation_seconds": gen_seconds, "clips": clips,
            "generations": generations}


def _load_csv_manifest(path):
    try:
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
    except (ValueError, OSError) as e:
        raise MotionError("ملف مانيفست الحركة غير صالح (%s): %s"
                          % (path, e))
    if not rows:
        raise MotionError("مانيفست الحركة بلا صفوف: %s" % path)
    gen_seconds = DEFAULT_GENERATION_SECONDS
    clips = {}
    generations = {}
    for row in rows:
        gen_id = (row.get("gen_id") or "").strip()
        clip_id = (row.get("clip_id") or "").strip()
        output_name = (row.get("output_name") or "").strip()
        if not gen_id or not clip_id:
            continue
        if not output_name:
            raise MotionError(
                "التوليد %s في المانيفست بلا اسم ملف (output_name)"
                % gen_id)
        try:
            row_gen_seconds = float(row.get("generation_seconds")
                                    or DEFAULT_GENERATION_SECONDS)
        except ValueError:
            raise MotionError(
                "مدة التوليد في المانيفست غير صالحة: %r"
                % (row.get("generation_seconds"),))
        if math.isfinite(row_gen_seconds) and row_gen_seconds > 0:
            gen_seconds = row_gen_seconds
        dur = row.get("duration_needed_s")
        try:
            dur = float(dur) if dur not in (None, "") else None
        except ValueError:
            raise MotionError(
                "مدة المقطع %s في المانيفست غير صالحة: %r"
                % (clip_id, dur))
        generations[gen_id] = {
            "clip_id": clip_id,
            "output_name": output_name,
            "scene": (row.get("scene") or "").strip(),
            "slice": (row.get("slice") or "").strip(),
            "take": (row.get("take") or "").strip()
                    or _take_from_gen_id(gen_id),
            "first_frame": (row.get("first_frame") or "").strip(),
        }
        entry = clips.setdefault(clip_id, {
            "generations": [], "duration_needed_s": dur,
            "coverage_note": _coverage_note_text()})
        if gen_id not in entry["generations"]:
            entry["generations"].append(gen_id)
        if entry["duration_needed_s"] is None and dur is not None:
            entry["duration_needed_s"] = dur
    if not clips:
        raise MotionError("مانيفست الحركة بلا مقاطع صالحة: %s" % path)
    for clip_id, c in clips.items():
        if not c["generations"]:
            raise MotionError(
                "المقطع %s في المانيفست بلا توليدات" % clip_id)
    return {"generation_seconds": gen_seconds, "clips": clips,
            "generations": generations}


def _gen_path(manifest, motion_dir, gen_id):
    gen = manifest["generations"].get(gen_id)
    if gen is None:
        raise MotionError("التوليد %s غير موجود في المانيفست" % gen_id)
    output_name = gen.get("output_name")
    if not output_name:
        raise MotionError(
            "التوليد %s في المانيفست بلا اسم ملف (output_name)" % gen_id)
    return os.path.abspath(os.path.join(motion_dir, output_name))


def plan_clip_segments(clip_id, duration_needed, manifest, motion_dir,
                       generation_seconds=None):
    """خطط مقاطع فيديو لمقطع واحد يغطي duration_needed ثانية.

    يرجع {"segments": [...], "warnings": [...]} — مقطع video فيه
    kind/src/in/out، ومقطع freeze فيه kind/src/duration.
    """
    needed = _check_duration(duration_needed,
                             "المقطع %s" % clip_id)
    clips = (manifest or {}).get("clips") or {}
    if clip_id not in clips:
        raise MotionError(
            "المقطع %s غير موجود في مانيفست الحركة" % clip_id)
    gen_seconds = generation_seconds
    if gen_seconds is None:
        gen_seconds = (manifest or {}).get("generation_seconds") \
            or DEFAULT_GENERATION_SECONDS
    try:
        gen_seconds = float(gen_seconds)
    except (TypeError, ValueError):
        raise MotionError("مدة التوليد غير صالحة: %r" % (gen_seconds,))
    if not math.isfinite(gen_seconds) or gen_seconds <= 0:
        raise MotionError("مدة التوليد غير صالحة: %r" % (gen_seconds,))
    gens = clips[clip_id].get("generations") or []
    if not gens:
        raise MotionError("المقطع %s في المانيفست بلا توليدات" % clip_id)
    a_path = _gen_path(manifest, motion_dir, gens[0])
    if not os.path.isfile(a_path):
        raise MotionError(
            "ملف التوليد الأول للمقطع %s غير موجود: %s" % (clip_id, a_path))
    segments = []
    warnings = []
    dur_a = min(needed, gen_seconds)
    segments.append({"kind": "video", "src": a_path,
                     "in": 0.0, "out": round(dur_a, 3)})
    remaining = round(needed - dur_a, 3)
    if remaining > 0:
        b_path = None
        if len(gens) > 1:
            b_path = _gen_path(manifest, motion_dir, gens[1])
            if not os.path.isfile(b_path):
                b_path = None
        if b_path is not None and remaining <= gen_seconds:
            # معالجة القفزة الموثقة: التوليد b مستقل من نفس الإطار
            # الأول، فيُستخدم من بدايته لباقي المدة.
            segments.append({"kind": "video", "src": b_path,
                             "in": 0.0, "out": round(remaining, 3)})
            remaining = 0.0
        elif b_path is not None:
            # الباقي أطول من توليد واحد: خذ b كاملًا ثم جمّد.
            segments.append({"kind": "video", "src": b_path,
                             "in": 0.0, "out": round(gen_seconds, 3)})
            remaining = round(remaining - gen_seconds, 3)
            segments.append({"kind": "freeze", "src": a_path,
                             "duration": remaining})
            warnings.append(
                "المقطع %s: المدة المطلوبة أطول من توليدين "
                "(%.2f ث) — باقي المدة (%.2f ث) سيُجمَّد من آخر "
                "إطار في التوليد a" % (clip_id, needed, remaining))
            remaining = 0.0
        else:
            segments.append({"kind": "freeze", "src": a_path,
                             "duration": remaining})
            warnings.append(
                "المقطع %s: التوليد الثاني (b) غير متوفر — باقي "
                "المدة (%.2f ث) سيُجمَّد من آخر إطار في التوليد a"
                % (clip_id, remaining))
            remaining = 0.0
    return {"segments": segments, "warnings": warnings}


def extract_last_frame(video_path, out_path):
    """استخرج آخر إطار من فيديو عبر ffmpeg إلى صورة jpg."""
    if not os.path.isfile(video_path):
        raise MotionError("ملف الفيديو غير موجود: %s" % video_path)
    parent = os.path.dirname(os.path.abspath(out_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    # مدة الفيديو بـffprobe ثم قفز قرب النهاية (أدق من -sseof وحده).
    ss = None
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, timeout=60)
        if probe.returncode == 0:
            dur = float(probe.stdout.strip())
            if math.isfinite(dur) and dur > 0:
                ss = max(0.0, dur - 0.05)
    except (ValueError, OSError, subprocess.SubprocessError):
        ss = None
    if ss is None:
        cmd = ["ffmpeg", "-y", "-v", "error", "-sseof", "-0.1",
               "-i", video_path, "-frames:v", "1", out_path]
    else:
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % ss,
               "-i", video_path, "-frames:v", "1", out_path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        raise MotionError("فشل استخراج آخر إطار من %s: %s"
                          % (video_path, e))
    if proc.returncode != 0 or not os.path.isfile(out_path):
        raise MotionError(
            "فشل استخراج آخر إطار من %s: %s"
            % (video_path, (proc.stderr or "").strip()[-300:]))
    return out_path


def resolve_next_first_frame(prev_clip_id, manifest, motion_dir,
                             out_path=None, duration_needed=None):
    """استخرج الإطار الذي يبدأ منه المقطع التالي: آخر إطار يُعرض من
    المقطع السابق (قاعدة التمديد بالإطار الأخير).

    يخطط المقطع السابق عبر plan_clip_segments ثم يستخرج آخر إطار
    من آخر مقطع فيه (التوليد b إن عُرض، وإلا a؛ ومقطع freeze
    مصدره a أصلًا) — فهذا الإطار هو first_frame الذي يجب أن يبدأ
    منه توليد المقطع التالي: يُمرَّر كمدخل image-to-video لتوليد
    Wan خارج هذه الشجرة، ثم يُسجَّل في المانيفست. هذه الدالة
    تنتج البذرة فقط — لا تولّد المقاطع ولا تغيّر التخطيط القائم.

    duration_needed: مدة المقطع السابق؛ الافتراضي مدته المسجلة
    في المانيفست (duration_needed_s) أو مدة التوليد.
    out_path الافتراضي: <motion_dir>/<prev_clip_id>-last-frame.jpg.
    يرجع مسار الصورة المستخرجة. يرفع MotionError إن غاب المقطع
    أو ملف توليده الأول أو فشل الاستخراج.
    """
    clips = (manifest or {}).get("clips") or {}
    if prev_clip_id not in clips:
        raise MotionError(
            "المقطع %s غير موجود في مانيفست الحركة" % prev_clip_id)
    need = duration_needed
    if need is None:
        need = clips[prev_clip_id].get("duration_needed_s")
    if need is None:
        need = (manifest or {}).get("generation_seconds") \
            or DEFAULT_GENERATION_SECONDS
    planned = plan_clip_segments(prev_clip_id, need, manifest,
                                 motion_dir)
    segments = planned.get("segments") or []
    if not segments:
        raise MotionError(
            "المقطع %s بلا مقاطع مخططة" % prev_clip_id)
    src = segments[-1].get("src")
    if not src:
        raise MotionError(
            "المقطع %s بلا مصدر لآخر مقطع" % prev_clip_id)
    if out_path is None:
        out_path = os.path.join(
            motion_dir, "%s-last-frame.jpg" % prev_clip_id)
    return extract_last_frame(src, out_path)


def check_first_frame_chain(manifest, clip_ids):
    """افحص سلسلة first_frame لمقاطع تُعرض متتابعة (ترتيب clip_ids
    هو ترتيب العرض) مقابل قاعدة التمديد بالإطار الأخير.

    القاعدة تقتضي أن يبدأ كل مقطع من آخر إطار للمقطع السابق —
    وفي المانيفست يعني ذلك:
    - كل توليد يصرّح بـ first_frame غير فارغ (وإلا فالسلسلة
      غير موثقة)؛
    - توليدا المقطع الواحد (a/b) يتشاركان first_frame نفسه
      (يبدآن من الإطار الأول نفسه — القفزة الموثقة)؛
    - مقطعان متتابعان لا يتشاركان first_frame نفسه (وإلا فالتالي
      يعيد البدء من نفس الصورة الثابتة بدل آخر إطار لسابقه).

    يرجع قائمة تحذيرات (عربية) — فارغة إن كانت السلسلة نظيفة.
    فحص بيانات فقط: لا يقرأ ملفات ولا يرفع استثناءً؛ والمقطع
    غير الموجود في المانيفست تحذير. لا يغيّر سلوك التخطيط —
    أداة تدقيق لجولة التوليد، لا فحص يُفرض عند العرض (انظر
    docs/motion.md).
    """
    warnings = []
    clips = (manifest or {}).get("clips") or {}
    generations = (manifest or {}).get("generations") or {}
    prev_clip_id = None
    prev_first = None
    for clip_id in (clip_ids or []):
        clip_id = str(clip_id)
        info = clips.get(clip_id)
        if info is None:
            warnings.append(
                "المقطع %s غير موجود في المانيفست — لا يمكن فحص "
                "سلسلة first_frame له" % clip_id)
            prev_clip_id = None
            prev_first = None
            continue
        firsts = []
        for gen_id in (info.get("generations") or []):
            gen = generations.get(gen_id) or {}
            first = (gen.get("first_frame") or "").strip() \
                if isinstance(gen, dict) else ""
            firsts.append(first)
        if not firsts:
            warnings.append(
                "المقطع %s بلا توليدات في المانيفست" % clip_id)
            prev_clip_id = None
            prev_first = None
            continue
        if any(not f for f in firsts):
            warnings.append(
                "المقطع %s: توليد بلا first_frame مصرّح — سلسلة "
                "التمديد بالإطار الأخير غير موثقة له" % clip_id)
        distinct = sorted({f for f in firsts if f})
        if len(distinct) > 1:
            warnings.append(
                "المقطع %s: توليداته تبدأ من إطارات أولى مختلفة "
                "(%s) — يجب أن تتشارك first_frame نفسه"
                % (clip_id, "، ".join(distinct)))
        current = distinct[0] if len(distinct) == 1 else None
        if (current is not None and prev_first is not None
                and current == prev_first):
            warnings.append(
                "المقطع %s يبدأ من نفس الإطار الأول للمقطع السابق "
                "%s (%s) — لم يُطبَّق التمديد بالإطار الأخير"
                % (clip_id, prev_clip_id, current))
        prev_clip_id = clip_id
        prev_first = current
    return warnings


def _still_segments(images, duration, clip_seconds=IMAGE_CLIP_SECONDS):
    """وزّع صور الفصل على المدة (clip_seconds للصورة، الأخيرة تُمدَّد).

    clip_seconds هو مقدار الصورة في وضع الحركة (2.5ث في youtube-long
    و5ث في clips) — يتبع الوضع بدل الثابت 5ث دائمًا (إصلاح فجوة
    الصورة المتجمدة 2026-11-24: باقي الفصل بعد المقاطع والرجوع
    بلا مقاطع يُقسَّمان إلى صور متناوبة بهذا المقدار).
    """
    clip_seconds = _check_duration(clip_seconds, "مقدار الصورة")
    n = max(1, int(round(duration / clip_seconds)))
    segments = []
    for i in range(n):
        if i < n - 1:
            segments.append({"kind": "image", "src": images[i % len(images)],
                             "duration": clip_seconds})
        else:
            segments.append({
                "kind": "image", "src": images[i % len(images)],
                "duration": round(
                    duration - clip_seconds * (n - 1), 3)})
    return segments


def _segment_duration(seg):
    if seg["kind"] == "video":
        return round(float(seg["out"]) - float(seg["in"]), 3)
    return round(float(seg["duration"]), 3)


def resolve_chapter_motion(chapter, manifest, motion_dir, chapter_index,
                           clip_seconds=None):
    """حلّ مقاطع الحركة لفصل كامل يغطي مدته.

    clip_seconds: مقدار الصورة الاحتياطية في وضع الحركة (2.5ث في
    youtube-long و5ث في clips — الافتراضي 5ث). باقي مدة الفصل بعد
    المقاطع يُقسَّم إلى صور متناوبة بهذا المقدار بدل صورة واحدة
    متجمدة (إصلاح فجوة 2026-11-24: الفصل 2 في الألغاز كان 6.855ث
    فيديو ثم 53.421ث صورة واحدة)، والرجوع بلا مقاطع يستخدم
    المقدار نفسه.

    يرجع {"segments": [...], "mode": "clips"|"still", "warnings": [...]}.
    لا يرفع استثناءً عند غياب المقاطع — يرجع لصورة ثابتة مع تحذير.
    الاستثناء فقط لمدخلات فاسدة (مدة غير صالحة، فصل بلا صور).
    """
    if not isinstance(chapter, dict):
        raise MotionError("الفصل ليس كائنًا")
    duration = _check_duration(chapter.get("duration"),
                               "الفصل %s" % (chapter.get("title") or "?"))
    if clip_seconds is None:
        clip_seconds = IMAGE_CLIP_SECONDS
    else:
        clip_seconds = _check_duration(clip_seconds, "مقدار الصورة")
    images = chapter.get("images") or []
    if not images:
        raise MotionError("الفصل بلا صور: %s"
                          % (chapter.get("title") or "?"))
    title = chapter.get("title") or ("الفصل %d" % chapter_index)
    clips = (manifest or {}).get("clips") or {}
    generations = (manifest or {}).get("generations") or {}
    explicit = chapter.get("motion_clips")
    if isinstance(explicit, list) and explicit:
        clip_ids = [str(c) for c in explicit]
    else:
        # مطابقة تلقائية: مقاطع توليداتها تحمل scene == "chapter N".
        scene = "chapter %d" % chapter_index
        found = set()
        for gen in generations.values():
            if isinstance(gen, dict) and (gen.get("scene") or "") == scene:
                if gen.get("clip_id"):
                    found.add(str(gen["clip_id"]))
        clip_ids = sorted(found, key=_natural_key)
    if not clip_ids:
        return {"segments": _still_segments(images, duration, clip_seconds),
                "mode": "still",
                "warnings": ["لا يوجد مقطع حركة للفصل %s — صورة ثابتة "
                             "بلا Ken Burns" % title]}
    segments = []
    warnings = []
    covered = 0.0
    for clip_id in clip_ids:
        remaining = round(duration - covered, 3)
        if remaining <= 0:
            break
        info = clips.get(clip_id)
        if info is None:
            warnings.append(
                "المقطع %s غير موجود في المانيفست — تُخطى للفصل %s"
                % (clip_id, title))
            continue
        need = info.get("duration_needed_s")
        try:
            need = float(need) if need is not None else remaining
        except (TypeError, ValueError):
            need = remaining
        need = min(need, remaining)
        if need <= 0:
            continue
        try:
            planned = plan_clip_segments(clip_id, need, manifest,
                                         motion_dir)
        except MotionError as e:
            warnings.append(
                "المقطع %s غير قابل للاستخدام للفصل %s (%s)"
                % (clip_id, title, e))
            continue
        for seg in planned["segments"]:
            segments.append(seg)
            covered = round(covered + _segment_duration(seg), 3)
        warnings.extend(planned["warnings"])
    remaining = round(duration - covered, 3)
    if remaining > 0:
        # إصلاح فجوة الصورة المتجمدة (2026-11-24): باقي المدة يُقسَّم
        # إلى صور متناوبة بمقدار الوضع (2.5ث في youtube-long و5ث في
        # clips) بدل صورة واحدة بطول الباقي كله.
        segments.extend(_still_segments(images, remaining, clip_seconds))
        warnings.append(
            "مقاطع الحركة غطّت %.2f ث من %.2f ث للفصل %s — باقي المدة "
            "(%.2f ث) صور ثابتة متناوبة كل %.1f ث بلا Ken Burns"
            % (covered, duration, title, remaining, clip_seconds))
    has_video = any(s.get("kind") == "video" for s in segments)
    return {"segments": segments,
            "mode": "clips" if has_video else "still",
            "warnings": warnings}
