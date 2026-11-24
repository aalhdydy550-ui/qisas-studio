#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""قص بلا إعادة ترميز — خطوة تنظيف اختيارية لمقاطع Veo قبل التجميع.

ما يعادل LosslessCut تحت الغطاء (LosslessCut نفسه واجهة فوق
ffmpeg: «fueled by the awesome FFmpeg which does all the grunt
work»): نسخ بايتات `-c copy` بلا فك ترميز ولا إعادة ترميز —
سريع (مقطع 8 ثوانٍ في ~0.1 ث) وبلا فقدان جودة.

لماذا بلا تطبيق LosslessCut نفسه؟ الـCLI الرسمي (انظر
LOSSLESSCUT-TEST.md) لا يقص بلا واجهة — يفتح التطبيق الرسومي
ويُؤتمت عبر `--keyboard-action` أو HTTP API على نسخة شغّالة،
وهذا غير ممكن على VM بلا شاشة. العملية نفسها هي `ffmpeg -c copy`
وهذا ما ينفذه هذا الموديول مباشرة.

قيود صادقة (اتحققت عمليًا على مقطع حماتي):
- البداية والنهاية تلتصقان بحدود الإطارات (±~0.2 ث): قص 2.0–6.0
  أعطى 4.21 ث بدل 4.0، وقص 0–6.0 أعطى 6.08 ث.
- الإطار الأول مطابق بكسلًا لإطار المصدر عند نفس الزمن (فرق 0.0)
  — بلا إعادة ترميز فعلًا.
- لقطع دقيق بالإطار استخدم `--exact` (يعيد الترميز libx264
  crf 20 — أبطأ وبفقد طفيف).
"""
import os
import subprocess
import time


class TrimError(Exception):
    """خطأ في القص (رسالته عربية جاهزة للعرض)."""


def probe_duration(path):
    """مدة ملف وسائط بالثواني عبر ffprobe (None إن تعذر)."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:
        return None


def build_command(input_path, output_path, start, duration, exact=False):
    """ابنِ أمر ffmpeg للقص (دالة نقية — للاختبار)."""
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if exact:
        # بحث دقيق بعد الدخل + إعادة ترميز
        cmd += ["-i", input_path, "-ss", "%s" % start,
                "-t", "%s" % duration,
                "-c:v", "libx264", "-crf", "20",
                "-c:a", "aac"]
    else:
        # بحث سريع قبل الدخل + نسخ بايتات
        # ملحوظة: بلا -avoid_negative_ts — مع بحث الدخل يبقي المقاطع
        # من الـkeyframe ويطيل الناتج (اتحقق: 6.13ث بدل 4.21ث)
        cmd += ["-ss", "%s" % start, "-i", input_path,
                "-t", "%s" % duration, "-c", "copy"]
    cmd += [output_path]
    return cmd


def trim_lossless(input_path, output_path, start=0.0, end=None,
                  duration=None, exact=False, timeout=300):
    """قص مقطع: من start حتى end (أو لمدة duration).

    يرجع قاموس النتيجة. يرفع TrimError عند: ملف مفقود، زمن غير
    صالح، أو فشل ffmpeg.
    """
    if not os.path.isfile(input_path):
        raise TrimError("ملف الفيديو غير موجود: %s" % input_path)
    start = float(start)
    if start < 0:
        raise TrimError("زمن البداية لا يمكن أن يكون سالبًا: %s" % start)
    if end is not None and duration is not None:
        raise TrimError("حدّد end أو duration — ليس كليهما")
    if end is not None:
        duration = float(end) - start
    if duration is None:
        raise TrimError("حدّد end أو duration للقص")
    duration = float(duration)
    if duration <= 0:
        raise TrimError("مدة القص يجب أن تكون موجبة: %s" % duration)
    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    cmd = build_command(input_path, output_path, start, duration, exact)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        raise TrimError("انتهت مهلة القص (%d ثانية)" % timeout)
    except OSError as e:
        raise TrimError("تعذر تشغيل ffmpeg: %s" % e)
    if r.returncode != 0:
        raise TrimError("فشل ffmpeg (رمز الخروج %d):\n%s"
                        % (r.returncode, (r.stderr or "")[-800:]))
    if not os.path.isfile(output_path):
        raise TrimError("انتهى ffmpeg دون إنشاء ملف الخرج: %s" % output_path)
    return {"output": output_path,
            "start": start,
            "duration": duration,
            "exact": exact,
            "seconds": round(time.time() - t0, 1),
            "size_bytes": os.path.getsize(output_path),
            "out_duration": probe_duration(output_path)}
