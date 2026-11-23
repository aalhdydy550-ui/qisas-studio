#!/usr/bin/env python3
"""فحص جودة قبل النشر — `studio.py check --video FILE`.

يفحص فيديوًا جاهزًا قبل رفعه ويطبع تقريرًا عربيًا PASS/FAIL
لكل فحص، ويرجع كود خروج غير صفري عند أي فشل:

  1. المدة: 40–60 ثانية للعمودي، أو 8–12 دقيقة للأفقي الطويل.
  2. الصمت عند فواصل المشاهد: أي صمت شبه كامل ≥1 ثانية في
     منتصف الفيديو يُبلَّغ (فكرة من تجربة ViralForge 2026-11-21:
     مقاطع Veo تترك ~ثانيتين صمت عند كل فاصل مشهد). صمت البداية
     والنهاية (مقدمة/خاتمة) لا يُحتسب.
  3. الصوت: وجود مسار صوتي ومستوى معقول (أقصى ≥ -25 ديسيبل،
     ومتوسط ≥ -40 ديسيبل).
  4. المقاس: 720×1280 عمودي (أو 1280×720 للطويل).
  5. الشعار: شارة «قصص وعبر» الذهبية أعلى اليمين — تُفحص
     بكسلات المنطقة العلوية اليمنى في إطارين (بداية ومنتصف)؛
     الشارة ثابتة في كل الإطارات فلا بد أن تظهر في الإطارين
     معًا (مشهد ذهبي عابر في إطار واحد لا يكفي).

يُستخدم أيضًا كفحص مسبق افتراضي في `studio.py publish`
(مع --skip-check للتجاوز).
"""
import json
import os
import re
import subprocess
import tempfile

from lib import errors as errors_lib

SILENCE_NOISE_DB = -40
SILENCE_MIN_SECONDS = 1.0
# الفيديو الطويل: بطاقات عناوين الفصول حتى 3 ثوانٍ، فلا يُرفض
# إلا صمت أطول من 4 ثوانٍ.
LONG_SILENCE_FAIL_SECONDS = 4.0
VERTICAL_DURATION = (40.0, 60.0)
LONG_DURATION = (480.0, 720.0)
VERTICAL_SIZE = (720, 1280)
LONG_SIZE = (1280, 720)
MAX_VOLUME_MIN_DB = -25.0
MEAN_VOLUME_MIN_DB = -40.0
# الشارة 110 بكسل + هامش 20 أعلى اليمين؛ نفحص منطقة أوسع قليلًا
# (140×140) تحسبًا لاختلاف بسيط في الموضع.
LOGO_REGION = 140
LOGO_MIN_GOLD_PIXELS = 300


class CheckError(Exception):
    """خطأ في فحص الفيديو (رسالته عربية)."""


def _run(cmd, timeout=300):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except FileNotFoundError:
        raise CheckError("الأمر غير موجود: %s" % cmd[0])
    except subprocess.TimeoutExpired:
        raise CheckError("انتهت المهلة أثناء: %s" % " ".join(cmd[:3]))
    return proc


def probe(path):
    """اقرأ مدة الفيديو وأبعاده ومساراته عبر ffprobe.

    يرجع {"duration", "width", "height", "has_audio"}. يرفع
    CheckError إن لم يكن الملف فيديو صالحًا.
    """
    if not os.path.isfile(path):
        raise CheckError("ملف الفيديو غير موجود: %s" % path)
    proc = _run(["ffprobe", "-v", "error", "-show_format",
                 "-show_streams", "-of", "json", path], timeout=30)
    if proc.returncode != 0:
        raw = (proc.stderr or "").strip()[-300:]
        msg = "تعذر قراءة الفيديو عبر ffprobe: %s" % raw
        if raw:
            # stderr الخام من ffprobe إنجليزي غالبًا — ألحق
            # ترجمته العربية (lib.errors) دون حذف الأصل.
            msg += "\n" + errors_lib.explain_error_text(raw, "ffmpeg")
        raise CheckError(msg)
    try:
        data = json.loads(proc.stdout or "{}")
    except ValueError:
        raise CheckError("مخرجات ffprobe ليست JSON صالحًا")
    fmt = data.get("format") or {}
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"),
                 None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"),
                 None)
    if video is None:
        raise CheckError("لا يوجد مسار فيديو في الملف: %s" % path)
    try:
        duration = float(fmt.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0:
        raise CheckError("مدة الفيديو غير مقروءة في: %s" % path)
    return {"duration": duration,
            "width": int(video.get("width") or 0),
            "height": int(video.get("height") or 0),
            "has_audio": audio is not None}


def _probe_image_size(path):
    """أبعاد صورة عبر ffprobe (ffprobe يقرأ الصور).

    يرجع (العرض، الارتفاع). يرفع CheckError عند غياب الملف
    أو تعذر قراءته.
    """
    if not os.path.isfile(path):
        raise CheckError("صورة الأفاتار غير موجودة: %s" % path)
    proc = _run(["ffprobe", "-v", "error", "-show_streams",
                 "-of", "json", path], timeout=30)
    if proc.returncode != 0:
        raise CheckError("تعذرت قراءة الصورة عبر ffprobe: %s" % path)
    try:
        data = json.loads(proc.stdout or "{}")
    except ValueError:
        raise CheckError("مخرجات ffprobe ليست JSON صالحًا")
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"),
                 None)
    if video is None or not video.get("width"):
        raise CheckError("تعذرت قراءة أبعاد الصورة: %s" % path)
    return int(video.get("width")), int(video.get("height"))


# سياسات نسبة أبعاد الأفاتار (نفس مجموعة avatar_settings).
AVATAR_ASPECT_POLICIES = ("native", "crop", "pad", "rotate")
# حد فرق النسبة في سياسة native.
_AVATAR_ASPECT_TOLERANCE = 0.02


def check_avatar_aspect(video_path, image_path, policy="native"):
    """قارن نسبة أبعاد الفيديو بنسبة صورة الأفاتار (جولة v0.1.38 §7).

    يرجع {"level": "ok"|"warn", "detail": str}:
    - native: تحذير إن |نسبة الفيديو − نسبة الصورة| > 0.02.
    - crop: سليم إن كان الفيديو 720×1280 وإلا تحذير.
    - pad: تحذير دائم (سياسة مرفوضة للخط).
    - rotate: تحذير إن كان الفيديو أفقيًا.
    كل النتائج تحذيرات — لا فشل أبدًا. صورة مفقودة →
    CheckError.
    """
    if policy not in AVATAR_ASPECT_POLICIES:
        raise CheckError("سياسة أبعاد غير معروفة: %s" % (policy,))
    info = probe(video_path)
    width, height = info["width"], info["height"]
    img_w, img_h = _probe_image_size(image_path)
    video_ratio = width / height if height else 0.0
    image_ratio = img_w / img_h if img_h else 0.0
    if policy == "pad":
        return {"level": "warn",
                "detail": "سياسة pad مرفوضة للخط — الأشرطة "
                          "الجانبية تشبه أشرطة Veo السوداء"}
    if policy == "crop":
        if (width, height) == VERTICAL_SIZE:
            return {"level": "ok",
                    "detail": "الفيديو 720×1280 — سليم لسياسة crop"}
        return {"level": "warn",
                "detail": "الفيديو %d×%d وليس 720×1280 — "
                          "سياسة crop" % (width, height)}
    if policy == "rotate":
        if width > height:
            return {"level": "warn",
                    "detail": "الفيديو أفقي (%d×%d) — سياسة rotate"
                              % (width, height)}
        return {"level": "ok",
                "detail": "الفيديو عمودي — سليم لسياسة rotate"}
    # native
    if abs(video_ratio - image_ratio) > _AVATAR_ASPECT_TOLERANCE:
        return {"level": "warn",
                "detail": "نسبة الفيديو (%.4f) تختلف عن نسبة "
                          "الصورة (%.4f) — السياسة native"
                          % (video_ratio, image_ratio)}
    return {"level": "ok",
            "detail": "نسبة الفيديو (%.4f) تطابق نسبة الصورة "
                      "(%.4f)" % (video_ratio, image_ratio)}


def detect_silences(path, noise_db=SILENCE_NOISE_DB,
                    min_seconds=SILENCE_MIN_SECONDS):
    """كشف فترات الصمت عبر ffmpeg silencedetect.

    يرجع قائمة (بداية، نهاية، مدة) لكل صمت ≥ min_seconds عند
    عتبة noise_db. صمت بلا نهاية مسجلة يُغلق عند مدة الفيديو.
    """
    proc = _run(["ffmpeg", "-v", "info", "-i", path, "-af",
                 "silencedetect=noise=%ddB:d=%s" % (noise_db, min_seconds),
                 "-f", "null", "-"], timeout=600)
    out = proc.stderr or ""
    starts = [float(m) for m in
              re.findall(r"silence_start: ([0-9.]+)", out)]
    ends = [(float(a), float(b)) for a, b in
            re.findall(r"silence_end: ([0-9.]+) \| silence_duration: "
                       r"([0-9.]+)", out)]
    silences = []
    for i, start in enumerate(starts):
        if i < len(ends):
            end, dur = ends[i]
        else:
            end, dur = None, None
        silences.append((start, end, dur))
    return silences


def audio_levels(path):
    """مستوى الصوت عبر volumedetect: (متوسط، أقصى) بالديسيبل.

    يرجع (None, None) إن تعذرت القراءة (بلا صوت أصلًا).
    """
    proc = _run(["ffmpeg", "-v", "info", "-i", path, "-af",
                 "volumedetect", "-f", "null", "-"], timeout=600)
    out = proc.stderr or ""
    mean = re.search(r"mean_volume: (-?[0-9.]+|-inf) dB", out)
    maxv = re.search(r"max_volume: (-?[0-9.]+|-inf) dB", out)
    if not mean or not maxv:
        return None, None

    def _db(text):
        return None if text == "-inf" else float(text)

    return _db(mean.group(1)), _db(maxv.group(1))


def extract_frame(path, seconds, out_path):
    """استخرج إطارًا واحدًا عند ثانية معينة كصورة PNG."""
    proc = _run(["ffmpeg", "-v", "error", "-ss", str(seconds),
                 "-i", path, "-frames:v", "1", "-y", out_path],
                timeout=60)
    if proc.returncode != 0 or not os.path.isfile(out_path):
        raise CheckError("تعذر استخراج إطار عند %.1f ثانية" % seconds)


def sample_video(path, out_dir):
    """عيّنة سلوكية من فيديو (جولة v0.1.37 — مقترح tinker رقم 6).

    يستخرج 3 لقطات (25% و50% و75% من المدة) + معاينة 3 ثوانٍ
    تبدأ عند 25% من المدة، في `out_dir` (المقصود:
    runs/samples/<اسم الفيديو>/). يرجع قاموسًا بالمسارات.
    يرفع CheckError عند أي فشل — المتصل يقرر إن كان تحذيرًا.
    """
    path = os.path.abspath(os.path.expanduser(path))
    info = probe(path)
    duration = info["duration"]
    os.makedirs(out_dir, exist_ok=True)
    frames = []
    for frac, name in ((0.25, "frame-25.jpg"), (0.5, "frame-50.jpg"),
                       (0.75, "frame-75.jpg")):
        out_path = os.path.join(out_dir, name)
        extract_frame(path, round(duration * frac, 2), out_path)
        frames.append(out_path)
    preview_path = os.path.join(out_dir, "preview-3s.mp4")
    start = round(duration * 0.25, 2)
    proc = _run(["ffmpeg", "-y", "-v", "error", "-ss", str(start),
                 "-i", path, "-t", "3", "-c:v", "libx264", "-preset",
                 "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", preview_path], timeout=300)
    if proc.returncode != 0 or not os.path.isfile(preview_path):
        raise CheckError("تعذرت معاينة 3 ثوانٍ من: %s" % path)
    return {"frames": frames, "preview": preview_path,
            "duration": round(duration, 1)}


def count_gold_pixels(image_path, width):
    """عدد البكسلات الذهبية في المنطقة العلوية اليمنى من صورة.

    الذهبي هنا لون الشارة (متوسط RGB ‏224/175/92): أحمر مرتفع،
    وأخضر متوسط، وأزرق منخفض، والأحمر أعلى من الأزرق بفارق واضح.
    """
    try:
        from PIL import Image
    except ImportError:
        raise CheckError("مكتبة PIL غير متاحة — لا يمكن فحص الشعار")
    im = Image.open(image_path).convert("RGB")
    region = im.crop((width - LOGO_REGION, 0, width, LOGO_REGION))
    gold = 0
    for r, g, b in region.getdata():
        if r >= 150 and g >= 90 and b <= 130 and r - b >= 40:
            gold += 1
    return gold


def eval_duration(duration, long_mode):
    """قيّم المدة: (ناجح؟، تفصيل عربي)."""
    low, high = LONG_DURATION if long_mode else VERTICAL_DURATION
    if low <= duration <= high:
        return True, "المدة %.1f ثانية (ضمن %s)" % (
            duration, "8–12 دقيقة" if long_mode else "40–60 ثانية")
    return False, "المدة %.1f ثانية — خارج النطاق %s" % (
        duration, "8–12 دقيقة" if long_mode else "40–60 ثانية")


def eval_silences(silences, duration, long_mode):
    """قيّم الصمت: (ناجح؟، تفصيل عربي).

    صمت البداية (يبدأ عند 0) وصمت النهاية (ينتهي عند مدة الفيديو)
    لا يُحتسبان — مقدمة/خاتمة. العمودي يفشل عند أي صمت ≥1 ثانية؛
    والطويل يفشل فقط عند صمت ≥4 ثوانٍ (بطاقات العناوين).
    """
    fail_at = (LONG_SILENCE_FAIL_SECONDS if long_mode
               else SILENCE_MIN_SECONDS)
    middle = []
    for start, end, _dur in silences:
        if start <= 0.05:
            continue
        if end is not None and end >= duration - 0.3:
            continue
        middle.append((start, end if end is not None else duration))
    if not middle:
        return True, "لا صمت ≥%.0f ثانية في منتصف الفيديو" % fail_at
    desc = "، ".join("%.1f–%.1f (%.1f ث)" % (s, e, e - s)
                     for s, e in middle)
    bad = [m for m in middle if m[1] - m[0] >= fail_at]
    if bad:
        return False, "صمت في المنتصف: %s" % desc
    return True, "صمت قصير فقط (دون حد الفشل): %s" % desc


def eval_audio(has_audio, mean_db, max_db):
    """قيّم الصوت: (ناجح؟، تفصيل عربي)."""
    if not has_audio:
        return False, "لا يوجد مسار صوتي في الفيديو"
    if mean_db is None or max_db is None:
        return False, "تعذرت قراءة مستوى الصوت"
    detail = "متوسط %.1f ديسيبل، أقصى %.1f ديسيبل" % (mean_db, max_db)
    if max_db < MAX_VOLUME_MIN_DB:
        return False, "الصوت خافت جدًا (%s)" % detail
    if mean_db < MEAN_VOLUME_MIN_DB:
        return False, "متوسط الصوت منخفض جدًا (%s)" % detail
    return True, "مستوى الصوت معقول (%s)" % detail


def eval_size(width, height, long_mode):
    """قيّم المقاس: (ناجح؟، تفصيل عربي)."""
    want = LONG_SIZE if long_mode else VERTICAL_SIZE
    if (width, height) == want:
        return True, "المقاس %dx%d صحيح" % (width, height)
    return False, "المقاس %dx%d — المتوقع %dx%d" % (
        width, height, want[0], want[1])


def eval_logo(gold_counts):
    """قيّم الشعار من عدّادات الذهب في الإطارات: (ناجح؟، تفصيل)."""
    detail = "؛ ".join("إطار %s: %d بكسل ذهبي" % (t, n)
                       for t, n in gold_counts)
    if all(n >= LOGO_MIN_GOLD_PIXELS for _, n in gold_counts):
        return True, "الشارة ظاهرة أعلى اليمين (%s)" % detail
    return False, "الشارة غير ظاهرة أعلى اليمين (%s)" % detail


def run_checks(path, long_mode=False):
    """شغّل كل فحوصات الجودة على فيديو. يرجع تقريرًا قاموسيًا.

    {"path", "long", "duration", "width", "height",
     "checks": [{"name", "ok", "detail"}], "passed": bool}
    long_mode يُستنتج تلقائيًا من المقاس الأفقي إن لم يُمرَّر.
    """
    # مسار مطلق: ملف اسمه يبدأ بشرطة (-test.mp4) كان يُفسَّر
    # كخيار من ffprobe/ffmpeg فيفشل الفحص (اختراق 2026-11-22).
    path = os.path.abspath(os.path.expanduser(path))
    info = probe(path)
    duration = info["duration"]
    width, height = info["width"], info["height"]
    if not long_mode and width > height:
        long_mode = True
    checks = []

    ok, detail = eval_duration(duration, long_mode)
    checks.append({"name": "المدة", "ok": ok, "detail": detail})

    silences = detect_silences(path)
    ok, detail = eval_silences(silences, duration, long_mode)
    checks.append({"name": "الصمت عند الفواصل", "ok": ok,
                   "detail": detail})

    mean_db, max_db = (None, None)
    if info["has_audio"]:
        mean_db, max_db = audio_levels(path)
    ok, detail = eval_audio(info["has_audio"], mean_db, max_db)
    checks.append({"name": "الصوت", "ok": ok, "detail": detail})

    ok, detail = eval_size(width, height, long_mode)
    checks.append({"name": "المقاس", "ok": ok, "detail": detail})

    with tempfile.TemporaryDirectory() as td:
        gold_counts = []
        for t in (min(3.0, duration * 0.25), duration * 0.5):
            frame = os.path.join(td, "frame-%.1f.png" % t)
            extract_frame(path, t, frame)
            gold_counts.append(("%.1fث" % t,
                                count_gold_pixels(frame, width)))
    ok, detail = eval_logo(gold_counts)
    checks.append({"name": "شعار الصفحة", "ok": ok, "detail": detail})

    return {"path": os.path.abspath(path),
            "long": long_mode,
            "duration": round(duration, 1),
            "width": width,
            "height": height,
            "checks": checks,
            "passed": all(c["ok"] for c in checks)}


def format_report(result):
    """نص عربي للتقرير: PASS/FAIL لكل فحص + خلاصة."""
    lines = ["فحص جودة: %s" % result["path"],
             "المدة %.1f ثانية — %dx%d%s" % (
                 result["duration"], result["width"], result["height"],
                 " (طويل)" if result["long"] else ""),
             ""]
    for c in result["checks"]:
        mark = "PASS" if c["ok"] else "FAIL"
        lines.append("[%s] %s — %s" % (mark, c["name"], c["detail"]))
    lines.append("")
    failed = [c["name"] for c in result["checks"] if not c["ok"]]
    if not failed:
        lines.append("النتيجة: كل الفحوصات ناجحة — الفيديو جاهز للنشر")
    else:
        lines.append("النتيجة: فشل في %s" % "، ".join(failed))
    return "\n".join(lines) + "\n"
