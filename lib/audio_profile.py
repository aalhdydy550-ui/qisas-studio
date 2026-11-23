#!/usr/bin/env python3
"""ملف أداء الصوت — جولة v0.1.38 (بند 2).

يقيس منحنى طاقة السرد ثانية بثانية (astats)، وخريطة الصمت،
ويشتق «الكلمات المؤكَّدة» من العبارات الممرَّرة (ASS): عبارة
ذروة طاقتها ≥ 6dB فوق وسيط المنحنى تُعلَّم مؤكَّدة. بلا ASR —
فالكلمات المؤكَّدة الحقيقية (بلا عبارات ممرَّرة) مستحيلة،
والقائمة عندها فارغة (انحراف موثّق عن نص التقرير).

ملاحظة حسابية (موثّقة): متوسط الديسيبل مباشرةً خاطئ —
تُجمَّع الإطارات بمتوسط الطاقة الخطية (10^(dB/10)) ثم
تُحوَّل النتيجة إلى ديسيبل (10*log10).
"""
import json
import math
import os
import re
import statistics
import subprocess

from lib import check as check_lib

# عتبة «المؤكَّد»: ذروة العبارة فوق الوسيط بهذا القدر (dB).
EMPHASIS_DB_ABOVE_MEDIAN = 6.0


class AudioProfileError(Exception):
    """خطأ ملف أداء صوت — رسالة عربية."""


def _audio_duration(path):
    """مدة ملف صوتي (ثوانٍ) عبر ffprobe — أو خطأ عربي."""
    if not os.path.isfile(path):
        raise AudioProfileError("ملف الصوت غير موجود: %s" % path)
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-of", "json",
             path],
            capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        raise AudioProfileError("الأمر غير موجود: ffprobe")
    except subprocess.TimeoutExpired:
        raise AudioProfileError("انتهت المهلة أثناء قراءة: %s" % path)
    if proc.returncode != 0:
        raise AudioProfileError(
            "تعذرت قراءة الصوت عبر ffprobe: %s"
            % (proc.stderr or "").strip()[-200:])
    try:
        duration = float(json.loads(proc.stdout or "{}")
                         .get("format", {}).get("duration") or 0)
    except (ValueError, TypeError):
        duration = 0.0
    if duration <= 0:
        raise AudioProfileError("مدة الصوت غير مقروءة في: %s" % path)
    return duration


def _frame_rms(path):
    """(زمن الإطار، RMS dB أو None للصمت) لكل إطار صوتي.

    عبر astats (metadata=1:reset=1) + ametadata يطبع
    lavfi.astats.Overall.RMS_level مع pts_time لكل إطار.
    """
    if not os.path.isfile(path):
        raise AudioProfileError("ملف الصوت غير موجود: %s" % path)
    cmd = ["ffmpeg", "-v", "info", "-i", path, "-af",
           "astats=metadata=1:reset=1,"
           "ametadata=print:key=lavfi.astats.Overall.RMS_level",
           "-f", "null", "-"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=600)
    except FileNotFoundError:
        raise AudioProfileError("الأمر غير موجود: ffmpeg")
    except subprocess.TimeoutExpired:
        raise AudioProfileError("انتهت المهلة أثناء تحليل: %s" % path)
    if proc.returncode != 0:
        raise AudioProfileError(
            "تعذّر تحليل الصوت عبر ffmpeg: %s"
            % (proc.stderr or "").strip()[-300:])
    frames = []
    current_time = None
    frame_re = re.compile(r"pts_time:([0-9.]+)")
    rms_re = re.compile(
        r"lavfi\.astats\.Overall\.RMS_level=(-inf|-?[0-9.]+)")
    for line in (proc.stderr or "").splitlines():
        m = frame_re.search(line)
        if m:
            current_time = float(m.group(1))
            continue
        m = rms_re.search(line)
        if m and current_time is not None:
            value = m.group(1)
            frames.append((current_time,
                           None if value == "-inf" else float(value)))
            current_time = None
    if not frames:
        raise AudioProfileError(
            "تعذّر قياس طاقة الصوت (بلا إطارات astats): %s" % path)
    return frames


def energy_curve(audio_path, bucket_seconds=1.0):
    """منحنى الطاقة: [{"second": i, "rms_db": float|None}] لكل سلة.

    تُجمَّع إطارات astats في سلال ثوانٍ بمتوسط الطاقة الخطية
    (10^(dB/10)) مثقَّلًا بتداخل كل إطار مع السلة — فإطار
    يعبر حدود سلة لا يُحسب كاملًا في سلة واحدة — ثم تُحوَّل
    النتيجة لديسيبل؛ وسلة طاقتها صفر (صمت رقمي) ← None.
    """
    if bucket_seconds <= 0:
        raise AudioProfileError(
            "مدة السلة يجب أن تكون موجبة (القيمة: %s)"
            % (bucket_seconds,))
    duration = _audio_duration(audio_path)
    frames = _frame_rms(audio_path)
    count = int(math.ceil(duration / bucket_seconds))
    # مدة كل إطار = الفرق مع الإطار التالي (والأخير حتى نهاية الملف).
    durations = []
    for i, (t, _db) in enumerate(frames):
        if i + 1 < len(frames):
            durations.append(max(0.0, frames[i + 1][0] - t))
        else:
            durations.append(max(0.0, duration - t) or 0.1)
    energy = [0.0] * count
    cover = [0.0] * count
    for (t, db), dur in zip(frames, durations):
        if dur <= 0:
            continue
        value = 0.0 if db is None else 10.0 ** (db / 10.0)
        start, end = t, t + dur
        first = max(0, int(start // bucket_seconds))
        last = min(count - 1,
                   int((end - 1e-9) // bucket_seconds))
        for i in range(first, last + 1):
            lo = max(start, i * bucket_seconds)
            hi = min(end, (i + 1) * bucket_seconds)
            if hi > lo:
                energy[i] += value * (hi - lo)
                cover[i] += hi - lo
    curve = []
    for i in range(count):
        if cover[i] <= 0 or energy[i] <= 0:
            curve.append({"second": i, "rms_db": None})
        else:
            curve.append({"second": i,
                          "rms_db": round(
                              10.0 * math.log10(energy[i] / cover[i]),
                              1)})
    return curve


def silence_map(audio_path):
    """خريطة الصمت: قائمة (بداية، نهاية، مدة) لصمت ≥ 0.5ث."""
    if not os.path.isfile(audio_path):
        raise AudioProfileError(
            "ملف الصوت غير موجود: %s" % audio_path)
    try:
        return check_lib.detect_silences(audio_path, min_seconds=0.5)
    except check_lib.CheckError as e:
        raise AudioProfileError(str(e))


def build_profile(audio_path, phrases=None):
    """ابنِ ملف أداء كاملًا لملف صوت.

    phrases: عبارات [{"text", "start", "end"}] (من ASS) — كل
    عبارة ذروتها ≥ 6dB فوق الوسيط تُعلَّم «مؤكَّدة»؛ وبلا
    عبارات تكون القائمة فارغة.
    يرجع {"audio", "duration_seconds", "energy_curve",
    "silences", "silence_ratio", "mean_db", "max_db",
    "emphasized": [{"text", "peak_db"}]}.
    """
    audio_path = os.path.abspath(os.path.expanduser(audio_path))
    duration = _audio_duration(audio_path)
    curve = energy_curve(audio_path)
    silences = silence_map(audio_path)
    mean_db, max_db = check_lib.audio_levels(audio_path)
    if mean_db is None or max_db is None:
        raise AudioProfileError(
            "لا يوجد مسار صوتي مقروء في: %s" % audio_path)
    silence_total = 0.0
    for start, end, dur in silences:
        if dur is not None:
            silence_total += dur
        elif end is not None:
            silence_total += max(0.0, end - start)
        else:
            silence_total += max(0.0, duration - start)
    values = [b["rms_db"] for b in curve if b["rms_db"] is not None]
    median_db = statistics.median(values) if values else None
    emphasized = []
    for phrase in (phrases or []):
        try:
            text = (phrase.get("text") or "").strip()
            start = float(phrase.get("start"))
            end = float(phrase.get("end"))
        except (AttributeError, TypeError, ValueError):
            continue
        if not text or end <= start or median_db is None:
            continue
        peak = None
        for bucket in curve:
            b0 = bucket["second"]
            b1 = b0 + 1.0
            if bucket["rms_db"] is None:
                continue
            if b1 > start and b0 < end:
                peak = (bucket["rms_db"] if peak is None
                        else max(peak, bucket["rms_db"]))
        if peak is not None and peak >= median_db + EMPHASIS_DB_ABOVE_MEDIAN:
            emphasized.append({"text": text, "peak_db": peak})
    return {"audio": audio_path,
            "duration_seconds": round(duration, 2),
            "energy_curve": curve,
            "silences": [[round(s, 2),
                          round(e, 2) if e is not None else None,
                          round(d, 2) if d is not None else None]
                         for s, e, d in silences],
            "silence_ratio": round(silence_total / duration, 3)
                             if duration else 0.0,
            "mean_db": mean_db,
            "max_db": max_db,
            "emphasized": emphasized}


def save_profile(profile, path):
    """اكتب ملف أداء JSON؛ ارجع المسار."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, ensure_ascii=False, indent=2)
    return path


def load_profile(path):
    """اقرأ ملف أداء JSON؛ ارجع القاموس."""
    if not os.path.isfile(path):
        raise AudioProfileError("ملف الأداء غير موجود: %s" % path)
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except ValueError as e:
        raise AudioProfileError(
            "ملف الأداء ليس JSON صالحًا: %s (%s)" % (path, e))
