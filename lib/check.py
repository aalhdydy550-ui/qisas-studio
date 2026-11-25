#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
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
  6. النص والمنطقة الآمنة (`qa_safe_area`): على إطارات فعلية
     (25% و50% و75% من المدة، أو منتصفات عبارات ASS عند
     وجود ملف ASS بجانب الفيديو): لا نص في الثلث العلوي،
     والنص الظاهر داخل هوامش 5% من كل جهة ولا يلامس حافة
     الإطار، والشعار (إن وُجد) داخل موضعه أعلى اليمين ولا
     يغطي نصًا. الكشف البكسلي إرشادي — انظر docstring في
     `qa_safe_area` للحدود.

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

# --- فحص النص والمنطقة الآمنة (qa_safe_area — جولة v0.1.39) ---
QA_NAME = "النص والمنطقة الآمنة"
QA_SAFE_MARGIN = 0.05      # هوامش المنطقة الآمنة من كل جهة
QA_TOP_FRACTION = 1.0 / 3.0  # الثلث العلوي — بلا نص أبدًا
QA_LOGO_CORNER = 160       # صندوق زاوية الشعار أعلى اليمين
QA_MIN_BAND_HEIGHT = 10    # شريط نصي أقصر من هذا خط أفقي في المشهد
QA_MAX_BAND_HEIGHT = 70    # وأطول من هذا منطقة مشهد مزدحمة
QA_MIN_BAND_DENSITY = 0.08  # متوسط كثافة الحواف داخل الشريط
QA_MIN_BAND_WIDTH = 0.35   # الشريط النصي يمتد على ≥35% من العرض
QA_MIN_BRIGHT_FRACTION = 0.02  # نص ساطع (حشوة بيضاء) داخل الشريط
QA_EDGE_THRESHOLD = 40     # عتبة تدرج البكسل لحافة
QA_ROW_DENSITY = 0.05      # عتبة كثافة الصف لبدء شريط
QA_BRIGHT_THRESHOLD = 230  # بكسل «ساطع» (حشوة حرف أبيض)
QA_LOGO_MIN_SIZE = 30      # شارة أصغر من هذا ليست شارة
QA_LOGO_MAX_SIZE = 150     # وأكبر من هذا ذهبي مشهد منتشر
QA_LOGO_MIN_DENSITY = 0.5  # كثافة الذهب داخل صندوق الشارة
QA_EDGE_TOLERANCE_PX = 2   # لمس الحافة = مقصوص


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
    # Pillow 13: get_flattened_data() على صورة RGB تُرجع ثلاثية
    # لكل بكسل (نفس شكل getdata() — «مسطّحة» تعني الصفوف
    # متتابعة لا القنوات)؛ فهي بديل حرفي هنا، والمنطق الذهبي
    # أدناه لم يتغيّر. (تحقّق تجريبيًا على Pillow 13.0.0.)
    for r, g, b in region.get_flattened_data():
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


# ------------------------------------------------------------------
# فحص النص والمنطقة الآمنة (qa_safe_area — جولة v0.1.39، مقترح
# من `raea check` + OpenCut: القسم 4.6 والقسم 6 بند 5).
#
# طبقتان:
#  (أ) تحليل ملف ASS المرافق (إن وُجد بجانب الفيديو بنفس الاسم
#      أو مُرّر صراحةً): محاذاة كل عبارة (Alignment: 7/8/9
#      علوية = فشل — القاعدة الصارمة: كل الكتابة أسفل فقط)
#      وهوامشها الفعالة (MarginL/MarginR/MarginV من العبارة
#      أو من النمط) مقابل هوامش 5%.
#  (ب) كشف بكسل على إطارات فعلية (PIL + numpy): شريط نصي هو
#      run متصل من الصفوف (10–70 بكسل ارتفاعًا) بكثافة حواف
#      ≥0.08 وعرض ≥35% من العرض وبكسلات ساطعة ≥2% — ثم
#      يُفحص موضعه (ثلث علوي؟) وامتداده الساطع (مقصوص عند
#      الحافة؟ خارج هوامش 5%؟).
#
# حدود موثقة (قيس على فيديو عائشة ج2 الحقيقي 47.6ث + fixtures
# مولّدة محليًا):
#  - الكاشف مضبوط على نمط الخط: نص أبيض ساطع بحواف داكنة
#    (ASS الافتراضي). نص داكن على خلفية فاتحة قد لا يُكتشف.
#  - الامتداد الأفقي يُقاس من البكسلات الساطعة (حشوة الحروف)
#    لا من الحواف — حواف المشهد خلف الكابشن تلوّث امتداد
#    الحواف (في عائشة ج2: امتداد الحواف x=4–715 لكابشن
#    هوامشه 40 بكسلًا؛ الامتداد الساطع x=193–528 سليم).
#  - زاوية الشعار مُستثناة من الكشف (الشارة الذهبية حوافها
#    كثيفة)، وحدود الأشرطة السوداء العلوية/السفلية من Veo
#    (~6 بكسلات) تُستثنى بارتفاع الشريط الأدنى.
#  - قاعدة «الذهبي» تطابق ألوان مشاهد Veo نفسها (غروب/رمل:
#    آلاف البكسلات الذهبية في كل بلاطة) فلا يُمسح الإطار
#    كاملًا بحثًا عن شعار — فحص الشعار يقتصر على صندوق
#    الزاوية، ولا يُعدّ ذهبيًا شارةً إلا إن كان متماسكًا
#    (صندوق 30–150 بكسلًا وكثافة ≥0.5)؛ وذهبي مشهد منتشر
#    في الزاوية يُتخطى لا يُفشل.
#  - بلا ملف ASS وبلا numpy: الفحص البكسلي يُتخطى ويُفحص
#    الشعار فقط (أو يُذكر التخطي في التفصيل).
# ------------------------------------------------------------------


def _parse_ass_time(text):
    """حوّل وقت ASS (h:mm:ss.cs) إلى ثوانٍ، أو None."""
    try:
        parts = (text or "").strip().split(":")
        h = float(parts[0])
        m = float(parts[1])
        s = float(parts[2])
        return h * 3600.0 + m * 60.0 + s
    except (IndexError, ValueError):
        return None


def parse_ass_positions(ass_path):
    """اقرأ مواضع العبارات من ملف ASS.

    يرجع {"dialogues": [{start, end, style, alignment,
    margin_l, margin_r, margin_v, text, line_no}]} — الهوامش
    فعالة (عبارة أو نمط). يرفع CheckError إن غاب الملف؛
    وأسطر تالفة تُتخطى بصمت.
    """
    from lib import ass_shaping as shaping_lib

    path = os.path.abspath(os.path.expanduser(ass_path))
    if not os.path.isfile(path):
        raise CheckError("ملف ASS غير موجود: %s" % path)
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    section = None
    style_fmt = []
    event_fmt = []
    styles = {}
    dialogues = []
    for line_no, raw in enumerate(lines, 1):
        line = raw.strip()
        if line.startswith("["):
            section = line
            continue
        if section == "[V4+ Styles]" and line.startswith("Format:"):
            style_fmt = [c.strip() for c in
                         line[len("Format:"):].split(",")]
        elif section == "[V4+ Styles]" and line.startswith("Style:"):
            vals = [v.strip() for v in
                    line[len("Style:"):].split(",")]

            def _idx(name, default=None):
                try:
                    i = style_fmt.index(name)
                except ValueError:
                    return default
                return vals[i] if i < len(vals) else default

            name = _idx("Name", "")
            try:
                styles[name] = {
                    "alignment": int(_idx("Alignment", "2")),
                    "margin_l": int(_idx("MarginL", "0")),
                    "margin_r": int(_idx("MarginR", "0")),
                    "margin_v": int(_idx("MarginV", "0"))}
            except ValueError:
                continue
        elif section == "[Events]" and line.startswith("Format:"):
            event_fmt = [c.strip() for c in
                         line[len("Format:"):].split(",")]
        elif section == "[Events]" and line.startswith("Dialogue:"):
            rest = line[len("Dialogue:"):]
            parts = rest.split(",", 9)
            if len(parts) < 10:
                continue

            def _efield(name):
                try:
                    i = event_fmt.index(name)
                except ValueError:
                    return ""
                return parts[i].strip() if i < len(parts) else ""

            start = _parse_ass_time(_efield("Start"))
            end = _parse_ass_time(_efield("End"))
            if start is None or end is None or end <= start:
                continue
            style = styles.get(_efield("Style"), {
                "alignment": 2, "margin_l": 0, "margin_r": 0,
                "margin_v": 0})
            try:
                m_l = int(_efield("MarginL") or 0)
                m_r = int(_efield("MarginR") or 0)
                m_v = int(_efield("MarginV") or 0)
            except ValueError:
                continue
            text = shaping_lib.strip_ass_tags(parts[9]).strip()
            if not text:
                continue
            dialogues.append({
                "start": start, "end": end,
                "style": _efield("Style"),
                "alignment": style["alignment"],
                "margin_l": m_l or style["margin_l"],
                "margin_r": m_r or style["margin_r"],
                "margin_v": m_v or style["margin_v"],
                "text": text, "line_no": line_no})
    return {"dialogues": dialogues}


def eval_ass_positions(dialogues, width, height):
    """قيّم مواضع عبارات ASS: (ناجح؟، تفصيل عربي).

    محاذاة علوية (7/8/9) = فشل؛ ولسفلية (1/2/3): MarginV
    أقل من 5% من الارتفاع أو أكبر من ثلثي الارتفاع = فشل،
    وMarginL/MarginR أقل من 5% من العرض = فشل. وسطية
    (4/5/6) تُفحص هوامشها الجانبية فقط — موضعها العمودي
    يفحصه الكشف البكسلي على الإطار الفعلي.
    """
    margin_x = QA_SAFE_MARGIN * width
    margin_y = QA_SAFE_MARGIN * height
    problems = []
    for d in dialogues:
        tag = "سطر %d (%.1fث) «%s»" % (
            d["line_no"], d["start"], d["text"][:25])
        if d["alignment"] in (7, 8, 9):
            problems.append("%s: محاذاة علوية (Alignment %d) — "
                            "الكتابة أسفل فقط"
                            % (tag, d["alignment"]))
            continue
        if d["alignment"] in (1, 2, 3):
            if d["margin_v"] < margin_y:
                problems.append(
                    "%s: MarginV ‏%d بكسل — أقرب من هامش 5%% "
                    "(%.0f بكسل) للحافة السفلى"
                    % (tag, d["margin_v"], margin_y))
            elif d["margin_v"] > height * 2.0 / 3.0:
                problems.append(
                    "%s: MarginV ‏%d بكسل — يدفع النص إلى الثلث "
                    "العلوي" % (tag, d["margin_v"]))
        if d["margin_l"] < margin_x or d["margin_r"] < margin_x:
            problems.append(
                "%s: هوامش جانبية %d/%d بكسل — خارج المنطقة الآمنة "
                "(هامش 5%% = %.0f بكسل)" % (tag, d["margin_l"],
                                            d["margin_r"], margin_x))
    if problems:
        return False, "مواضع ASS: " + "؛ ".join(problems)
    return True, "مواضع ASS سليمة: %d عبارة داخل المنطقة الآمنة" % (
        len(dialogues))


def detect_text_bands(image_path):
    """اكتشف أشرطة نصية في صورة إطار (PIL + numpy).

    يرجع قائمة {"y0", "y1", "xmin", "xmax", "bxmin", "bxmax"}
    — bxmin/bxmax امتداد البكسلات الساطعة (حشوة الحروف)،
    وxmin/xmax امتداد الحواف. زاوية الشعار أعلى اليمين
    مُستثناة. يرفع CheckError إن غابت PIL أو numpy.
    """
    try:
        from PIL import Image
    except ImportError:
        raise CheckError("مكتبة PIL غير متاحة — لا يمكن فحص النص")
    try:
        import numpy as np
    except ImportError:
        raise CheckError("مكتبة numpy غير متاحة — لا يمكن الكشف "
                         "البكسلي عن النص")
    im = Image.open(image_path).convert("L")
    a = np.asarray(im, dtype=np.float32)
    height, width = a.shape
    gx = np.zeros_like(a)
    gy = np.zeros_like(a)
    gx[:, 1:] = np.abs(np.diff(a, axis=1))
    gy[1:, :] = np.abs(np.diff(a, axis=0))
    edge = (gx > QA_EDGE_THRESHOLD) | (gy > QA_EDGE_THRESHOLD)
    edge[:QA_LOGO_CORNER, width - QA_LOGO_CORNER:] = False
    row = edge.mean(axis=1)
    smooth = np.convolve(row, np.ones(5) / 5.0, mode="same")
    bright = a > QA_BRIGHT_THRESHOLD
    bands = []
    y = 0
    while y < height:
        if smooth[y] > QA_ROW_DENSITY:
            y0 = y
            while y < height and smooth[y] > QA_ROW_DENSITY:
                y += 1
            y1 = y - 1
            band_h = y1 - y0 + 1
            density = float(row[y0:y1 + 1].mean())
            if not (QA_MIN_BAND_HEIGHT <= band_h <= QA_MAX_BAND_HEIGHT
                    and density >= QA_MIN_BAND_DENSITY):
                continue
            sub = edge[y0:y1 + 1, :]
            col = sub.mean(axis=0)
            xs = np.where(col > 0.02)[0]
            bright_frac = float(bright[y0:y1 + 1, :].mean())
            if not len(xs) or bright_frac < QA_MIN_BRIGHT_FRACTION:
                continue
            if (xs[-1] - xs[0]) / width < QA_MIN_BAND_WIDTH:
                continue
            bcol = bright[y0:y1 + 1, :].mean(axis=0)
            bxs = np.where(bcol > 0.01)[0]
            if not len(bxs):
                continue
            bands.append({"y0": y0, "y1": y1,
                          "xmin": int(xs[0]), "xmax": int(xs[-1]),
                          "bxmin": int(bxs[0]),
                          "bxmax": int(bxs[-1])})
        else:
            y += 1
    return bands


def gold_badge_box(image_path, width):
    """صندوق شارة ذهبية متماسكة في زاوية الشعار، أو None.

    ذهبي منتشر (مشهد غروب/رمل يملأ الزاوية) يُرجع None —
    ليس شارة. شارة حقيقية: صندوق 30–150 بكسلًا لكل ضلع
    وكثافة ذهب ≥0.5 داخله.
    """
    try:
        from PIL import Image
    except ImportError:
        raise CheckError("مكتبة PIL غير متاحة — لا يمكن فحص الشعار")
    try:
        import numpy as np
    except ImportError:
        raise CheckError("مكتبة numpy غير متاحة — لا يمكن فحص الشعار")
    im = Image.open(image_path).convert("RGB")
    a = np.asarray(im, dtype=np.int16)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    gold = ((r >= 150) & (g >= 90) & (b <= 130)
            & ((r - b) >= 40))
    corner = gold[:QA_LOGO_CORNER, width - QA_LOGO_CORNER:]
    count = int(corner.sum())
    if count < LOGO_MIN_GOLD_PIXELS:
        return None
    ys, xs = np.where(corner)
    x0 = int(xs.min()) + width - QA_LOGO_CORNER
    x1 = int(xs.max()) + width - QA_LOGO_CORNER
    y0, y1 = int(ys.min()), int(ys.max())
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    density = count / float(bw * bh)
    if not (QA_LOGO_MIN_SIZE <= bw <= QA_LOGO_MAX_SIZE
            and QA_LOGO_MIN_SIZE <= bh <= QA_LOGO_MAX_SIZE
            and density >= QA_LOGO_MIN_DENSITY):
        return None
    return {"x0": x0, "x1": x1, "y0": y0, "y1": y1, "pixels": count}


def eval_qa_bands(bands, badge_box, width, height):
    """قيّم أشرطة نصية مكتشفة + صندوق شارة: (ناجح؟، [مشاكل]).

    نص في الثلث العلوي = فشل؛ وامتداد ساطع يلامس حافة
    الإطار = مقصوص؛ وامتداد ساطع خارج هوامش 5% أو شريط
    يلامس الحافة السفلى = خارج المنطقة الآمنة؛ وشارة تلامس
    حافة الإطار = مقصوصة؛ وتداخل شريط مع الشارة = تغطية.
    """
    margin_x = QA_SAFE_MARGIN * width
    margin_y = QA_SAFE_MARGIN * height
    top_limit = height * QA_TOP_FRACTION
    problems = []
    for band in bands:
        center = (band["y0"] + band["y1"]) / 2.0
        tag = "شريط نصي y=%d–%d" % (band["y0"], band["y1"])
        if center < top_limit:
            problems.append("%s: نص في الثلث العلوي (وسطه %.0f "
                            "بكسل من %d)" % (tag, center, height))
        if (band["bxmin"] <= QA_EDGE_TOLERANCE_PX
                or band["bxmax"] >= width - 1 - QA_EDGE_TOLERANCE_PX):
            problems.append("%s: نص مقصوص عند الحافة "
                            "(x=%d–%d من %d)"
                            % (tag, band["bxmin"], band["bxmax"],
                               width))
        elif (band["bxmin"] < margin_x
                or band["bxmax"] > width - margin_x):
            problems.append("%s: نص خارج المنطقة الآمنة "
                            "(x=%d–%d، الهامش %.0f بكسل)"
                            % (tag, band["bxmin"], band["bxmax"],
                               margin_x))
        if band["y1"] > height - margin_y:
            problems.append("%s: نص يلامس الحافة السفلى "
                            "(y1=%d من %d)"
                            % (tag, band["y1"], height))
        if badge_box and not (
                band["xmax"] < badge_box["x0"]
                or band["xmin"] > badge_box["x1"]
                or band["y1"] < badge_box["y0"]
                or band["y0"] > badge_box["y1"]):
            problems.append("%s: الشعار يغطي نصًا (تداخل مع "
                            "صندوق الشارة)" % tag)
    if badge_box:
        if (badge_box["x1"] >= width - 1 - QA_EDGE_TOLERANCE_PX
                or badge_box["y0"] <= QA_EDGE_TOLERANCE_PX):
            problems.append("الشعار مقصوص عند حافة الإطار "
                            "(x=%d–%d، y=%d–%d)"
                            % (badge_box["x0"], badge_box["x1"],
                               badge_box["y0"], badge_box["y1"]))
    return (not problems), problems


def _qa_frame_times(duration, dialogues):
    """أزمنة إطارات QA: منتصفات عبارات ASS القريبة من
    25%/50%/75% من المدة، أو الكسور نفسها بلا ASS."""
    times = []
    mids = sorted((d["start"] + d["end"]) / 2.0 for d in dialogues
                  if d["end"] > d["start"])
    for frac in (0.25, 0.5, 0.75):
        target = duration * frac
        if mids:
            best = min(mids, key=lambda m: abs(m - target))
            if abs(best - target) <= duration * 0.2:
                target = best
        times.append(round(target, 2))
    seen = set()
    out = []
    for t in times:
        key = round(t, 1)
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out or [round(duration * 0.5, 2)]


def _discover_ass(video_path):
    """ملف ASS بجانب الفيديو بنفس الاسم، أو None."""
    cand = os.path.splitext(video_path)[0] + ".ass"
    return cand if os.path.isfile(cand) else None


def qa_safe_area(video_path, duration, width, height, ass_path=None):
    """فحص النص والمنطقة الآمنة على إطارات فعلية: (ناجح؟، تفصيل).

    يجمع تحليل ASS المرافق (محاذاة وهوامش العبارات) والكشف
    البكسلي على 3 إطارات (منتصفات عبارات أو 25%/50%/75%)
    وفحص موضع الشعار. بلا ASS يُفحص الشعار والإطارات فقط.
    انظر docstring أعلى هذا القسم للحدود الموثقة.
    """
    problems = []
    notes = []
    dialogues = []
    ass_file = ass_path or _discover_ass(video_path)
    if ass_file:
        try:
            dialogues = parse_ass_positions(ass_file)["dialogues"]
            ok, detail = eval_ass_positions(dialogues, width, height)
            if not ok:
                problems.append(detail)
            notes.append("ASS: %d عبارة" % len(dialogues))
        except CheckError as e:
            notes.append("ASS بجانب الفيديو تعذر تحليله — فحص "
                         "بكسل فقط (%s)" % e)
        except (OSError, UnicodeDecodeError) as e:
            notes.append("ASS بجانب الفيديو تعذر تحليله — فحص "
                         "بكسل فقط (%s)" % e)
    try:
        with tempfile.TemporaryDirectory() as td:
            badge = None
            checked_frames = 0
            for i, t in enumerate(_qa_frame_times(duration,
                                                  dialogues)):
                frame = os.path.join(td, "qa-%d.png" % i)
                extract_frame(video_path, t, frame)
                checked_frames += 1
                bands = detect_text_bands(frame)
                if badge is None:
                    badge = gold_badge_box(frame, width)
                ok, band_problems = eval_qa_bands(
                    bands, badge, width, height)
                for p in band_problems:
                    problems.append("إطار %.1fث: %s" % (t, p))
            if badge is None:
                notes.append("بلا شارة متماسكة في الزاوية — "
                             "فحص موضع الشعار متخطى")
            else:
                notes.append("الشارة في موضعها أعلى اليمين")
    except CheckError as e:
        notes.append("الكشف البكسلي متخطى (%s)" % e)
    if problems:
        return False, "؛ ".join(problems)
    summary = "%d إطارات: لا نص في الثلث العلوي، والنص الظاهر " \
              "داخل المنطقة الآمنة (هوامش 5%%)" % checked_frames
    if notes:
        summary += " — " + "؛ ".join(notes)
    return True, summary


def run_checks(path, long_mode=False, ass_path=None):
    """شغّل كل فحوصات الجودة على فيديو. يرجع تقريرًا قاموسيًا.

    {"path", "long", "duration", "width", "height",
     "checks": [{"name", "ok", "detail"}], "passed": bool}
    long_mode يُستنتج تلقائيًا من المقاس الأفقي إن لم يُمرَّر.
    ass_path ملف ASS اختياري لفحص مواضع العبارات؛ وبلاه
    يُكتشف ملف بجانب الفيديو بنفس الاسم تلقائيًا.
    الفحوصات الأساسية 6 (المدة، الصمت، الصوت، المقاس،
    الشعار، النص والمنطقة الآمنة).
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

    ok, detail = qa_safe_area(path, duration, width, height,
                              ass_path=ass_path)
    checks.append({"name": QA_NAME, "ok": ok, "detail": detail})

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
