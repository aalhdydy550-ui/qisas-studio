#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""نسب العرض وملفات التعريف المحظورة للأفاتار — جولة v0.1.38 (بند 3).

القاعدة: المخرج عمودي فقط (العرض < الارتفاع) وبأبعاد قابلة
للقسمة على 8 (محاذاة VAE)؛ وأي نسبة مربعة أو أفقية أو أبعاد
غير قابلة للقسمة على 8 تُرفض بخطأ عربي. الافتراضي 720×1280
(هدف الخط اليومي).

تصحيح موثّق لوثيقة التصميم (§3): 720×1092 ليس ملف تعريف
مخرج رسميًا — هو حجم الصورة المرجعية (البورتريه) في دفتر
الاختبار التجريبي على Kaggle (‏`longcat-pilot.ipynb`: ‏
«expect 720x1092»)، وهو لا يقبل القسمة على 8 (1092÷8 =
136.5) فلا يصح كأبعاد مخرج. ملفا المخرج الرسميان الوحيدان
في سكربت LongCat هما 480p ‏(480×832) و720p ‏(768×1280)
وكلاهما أفقي؛ والعمودي 720×1280 (هدفنا) غير مؤكد بعد
حسب تقرير LongCat — يُثبت بصريًا في الاختبار قبل الاعتماد.
"""
# الأبعاد الافتراضية للخط: 9:16 عمودي.
DEFAULT_WIDTH = 720
DEFAULT_HEIGHT = 1280

# ملفا المخرج الرسميان في سكربت LongCat (أفقيان فقط).
OFFICIAL_PROFILES = {
    "480p": {"width": 480, "height": 832},
    "720p": {"width": 768, "height": 1280},
}

# حجم الصورة المرجعية (البورتريه) المثبت في الاختبار التجريبي
# على Kaggle — صورة مدخل لا أبعاد مخرج.
PILOT_PORTRAIT = {"width": 720, "height": 1092, "verified": True}

# القاسم المطلوب لأبعاد المخرج (محاذاة VAE).
ASPECT_DIVISOR = 8


import json
import os
import shutil
import subprocess
import time


class AvatarAspectError(Exception):
    """خطأ نسبة عرض — رسالة عربية."""


class ReframeError(Exception):
    """خطأ إعادة تأطير — رسالة عربية."""


def validate_aspect(width, height):
    """تحقق من أبعاد مخرج: عمودي فقط وقابلة للقسمة على 8.

    يرجع {"width", "height"} أو يرفع خطأً عربيًا.
    """
    if not isinstance(width, int) or not isinstance(height, int):
        raise AvatarAspectError(
            "الأبعاد يجب أن تكون أعدادًا صحيحة (القيم: %s×%s)"
            % (width, height))
    if width <= 0 or height <= 0:
        raise AvatarAspectError(
            "الأبعاد يجب أن تكون موجبة (القيم: %s×%s)"
            % (width, height))
    if width >= height:
        raise AvatarAspectError(
            "الأفاتار عمودي فقط — العرض (%d) يجب أن يكون أصغر "
            "من الارتفاع (%d)" % (width, height))
    if width % ASPECT_DIVISOR or height % ASPECT_DIVISOR:
        raise AvatarAspectError(
            "الأبعاد يجب أن تقبل القسمة على %d (القيم: %s×%s)"
            % (ASPECT_DIVISOR, width, height))
    return {"width": width, "height": height}


def default_aspect():
    """الأبعاد الافتراضية: 720×1280."""
    return {"width": DEFAULT_WIDTH, "height": DEFAULT_HEIGHT}


def parse_aspect(text):
    """حلّل نص نسبة مثل «720x1280» إلى أبعاد متحقق منها."""
    if not isinstance(text, str) or "x" not in text:
        raise AvatarAspectError(
            "نسبة العرض يجب أن تكون مثل 720x1280 (القيمة: %s)"
            % (text,))
    parts = text.strip().lower().split("x")
    if len(parts) != 2:
        raise AvatarAspectError(
            "نسبة العرض يجب أن تكون مثل 720x1280 (القيمة: %s)"
            % (text,))
    try:
        width, height = int(parts[0]), int(parts[1])
    except ValueError:
        raise AvatarAspectError(
            "نسبة العرض يجب أن تكون مثل 720x1280 (القيمة: %s)"
            % (text,))
    return validate_aspect(width, height)


def official_profile(name):
    """ملف مخرج رسمي بالاسم («480p» أو «720p» — أفقيان).

    يرجع {"width", "height"} أو خطأً عربيًا.
    """
    if not isinstance(name, str) or name not in OFFICIAL_PROFILES:
        raise AvatarAspectError(
            "ملف تعريف LongCat غير معروف: %s (الصالح: %s)"
            % (name, "، ".join(sorted(OFFICIAL_PROFILES))))
    return dict(OFFICIAL_PROFILES[name])


def pilot_portrait():
    """حجم الصورة المرجعية المثبت في الاختبار (720×1092).

    صورة مدخل لا أبعاد مخرج — لا تمر من validate_aspect.
    """
    return dict(PILOT_PORTRAIT)


def aspect_for_job(job):
    """أبعاد وظيفة: من settings.aspect (أو aspect_ratio) أو الافتراضي.

    الوظيفة قاموس (أو بلا settings)؛ والقيمة المجهولة/غير
    الصالحة تُرفض بخطأ عربي.
    """
    if not isinstance(job, dict):
        return default_aspect()
    settings = job.get("settings") or {}
    if not isinstance(settings, dict):
        return default_aspect()
    value = settings.get("aspect") or settings.get("aspect_ratio")
    if value is None:
        return default_aspect()
    if isinstance(value, dict):
        return validate_aspect(value.get("width"), value.get("height"))
    if isinstance(value, str):
        return parse_aspect(value)
    raise AvatarAspectError(
        "نسبة العرض غير صالحة (القيمة: %s)" % (value,))


# --- إعادة تأطير تلقائية للعمودي — جولة v0.1.39 (أ2-7) ---
# من ميزات Concat المحلية (المقارنة §4.5): مقطع أفقي (16:9)
# يُقصّ بذكاء إلى 9:16 عمودي 720×1280 — قصّ لا تمديد، فلا
# تشويه أبدًا. التركيز مركزي افتراضيًا، مع نقطة تركيز
# اختيارية (focus_x: ‏0 = أقصى اليسار، 1 = أقصى اليمين)
# وهامش أمان يمنع القصّ من ملامسة الحواف. المدخل العمودي
# أصلًا يمرّ بلا تغيير (بلا قصّ وبلا إعادة ترميز).
#
# ملاحظة الأبعاد الزوجية: قصّ ffmpeg على yuv420p يتطلب
# أبعادًا ومواضع قصّ زوجية — لذا تُقرَّب الأبعاد والمواضع
# إلى أقرب عدد زوجي أصغر (floor) قبل بناء الأمر.

# أبعاد هدف إعادة التأطير (هدف الخط اليومي).
REFRAME_WIDTH = 720
REFRAME_HEIGHT = 1280


def _even_floor(n):
    """أقرب عدد صحيح زوجي أصغر أو يساوِ n."""
    return int(n) & ~1


def _validate_focus(focus_x):
    """تحقق من نقطة التركيز: عدد بين 0 و1."""
    if isinstance(focus_x, bool) or not isinstance(focus_x, (int, float)):
        raise ReframeError(
            "نقطة التركيز يجب أن تكون عددًا بين 0 و1 (القيمة: %s)"
            % (focus_x,))
    focus_x = float(focus_x)
    if focus_x < 0 or focus_x > 1:
        raise ReframeError(
            "نقطة التركيز يجب أن تكون بين 0 (يسار) و1 (يمين) "
            "(القيمة: %s)" % (focus_x,))
    return focus_x


def _validate_safety_margin(safety_margin, src_width, crop_width):
    """تحقق من هامش الأمان: عدد صحيح غير سالب يترك مجالًا للقصّ."""
    if isinstance(safety_margin, bool) or not isinstance(
            safety_margin, int):
        raise ReframeError(
            "هامش الأمان يجب أن يكون عددًا صحيحًا غير سالب "
            "(القيمة: %s)" % (safety_margin,))
    if safety_margin < 0:
        raise ReframeError(
            "هامش الأمان لا يمكن أن يكون سالبًا (القيمة: %d)"
            % safety_margin)
    if 2 * safety_margin + crop_width > src_width:
        raise ReframeError(
            "هامش الأمان (%d) كبير جدًا على عرض %d مع قصّ %d — "
            "لا يبقى مجال لنافذة القصّ"
            % (safety_margin, src_width, crop_width))
    return safety_margin


def reframe_crop(src_width, src_height, focus_x=0.5, safety_margin=0,
                 target_width=REFRAME_WIDTH,
                 target_height=REFRAME_HEIGHT):
    """احسب نافذة قصّ ذكية من مقطع أفقي إلى عمودي (دالة نقية).

    يرجع قاموسًا فيه نافذة القصّ {x, y, width, height} وأبعاد
    الخرج {out_width, out_height} وعلامة needs_reframe
    (False للمدخل العمودي أصلًا — يمرّ بلا تغيير) ونقطة
    التركيز الفعلية. يرفع ReframeError عند أبعاد غير صالحة
    أو تركيز/هامش خارج النطاق.
    """
    if isinstance(src_width, bool) or isinstance(src_height, bool) \
            or not isinstance(src_width, int) \
            or not isinstance(src_height, int):
        raise ReframeError(
            "أبعاد المصدر يجب أن تكون أعدادًا صحيحة (القيم: %s×%s)"
            % (src_width, src_height))
    if src_width <= 0 or src_height <= 0:
        raise ReframeError(
            "أبعاد المصدر يجب أن تكون موجبة (القيم: %s×%s)"
            % (src_width, src_height))
    if not isinstance(target_width, int) \
            or not isinstance(target_height, int) \
            or target_width <= 0 or target_height <= 0:
        raise ReframeError(
            "أبعاد الهدف يجب أن تكون أعدادًا صحيحة موجبة "
            "(القيم: %s×%s)" % (target_width, target_height))
    focus_x = _validate_focus(focus_x)
    # عمودي أصلًا: يمرّ بلا تغيير — نافذة القصّ هي الإطار كاملًا
    # وأبعاد الخرج هي أبعاد المصدر نفسها (بلا تحجيم ولا تشويه).
    if src_width < src_height:
        return {"x": 0, "y": 0, "width": src_width,
                "height": src_height,
                "out_width": src_width, "out_height": src_height,
                "focus_x": focus_x, "safety_margin": 0,
                "needs_reframe": False,
                "source_width": src_width,
                "source_height": src_height}
    # أفقي أو مربع: قصّ العرض إلى نسبة الهدف مع الحفاظ على
    # الارتفاع كاملًا (قصّ لا تمديد).
    crop_height = _even_floor(src_height)
    crop_width = _even_floor(crop_height * target_width
                             / target_height)
    if crop_width <= 0 or crop_width > src_width:
        raise ReframeError(
            "لا يمكن قصّ %dx%d إلى نسبة %dx%d"
            % (src_width, src_height, target_width, target_height))
    safety_margin = _validate_safety_margin(safety_margin, src_width,
                                            crop_width)
    # قصّ yuv420p يتطلب موضعًا زوجيًا — يُرفع الهامش الفردي
    # إلى الزوجي التالي للتثبيت (القيمة الممرَّرة تُحفظ كما هي
    # في القاموس المرجَع).
    margin = safety_margin + (safety_margin % 2)
    center = focus_x * src_width
    x = int(round(center - crop_width / 2.0))
    x = max(margin, min(x, src_width - margin - crop_width))
    x = _even_floor(x)
    return {"x": x, "y": 0, "width": crop_width,
            "height": crop_height,
            "out_width": target_width, "out_height": target_height,
            "focus_x": focus_x, "safety_margin": safety_margin,
            "needs_reframe": True,
            "source_width": src_width, "source_height": src_height}


def probe_dimensions(path):
    """اقرأ أبعاد ملف فيديو عبر ffprobe.

    يرجع {"width", "height"}. يرفع ReframeError عند ملف
    مفقود أو غير فيديو أو تعذر قراءته.
    """
    if not os.path.isfile(path):
        raise ReframeError("ملف الفيديو غير موجود: %s" % path)
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "json", path],
            capture_output=True, text=True, timeout=30)
    except OSError as e:
        raise ReframeError("تعذر تشغيل ffprobe: %s" % e)
    except subprocess.TimeoutExpired:
        raise ReframeError("انتهت مهلة قراءة أبعاد الفيديو: %s" % path)
    if r.returncode != 0:
        raise ReframeError(
            "تعذر قراءة أبعاد الفيديو %s: %s"
            % (path, (r.stderr or "").strip()[-300:]))
    try:
        data = json.loads(r.stdout or "{}")
        stream = (data.get("streams") or [{}])[0]
        width, height = int(stream["width"]), int(stream["height"])
    except (ValueError, KeyError, IndexError, TypeError):
        raise ReframeError(
            "مخرجات ffprobe بلا أبعاد فيديو صالحة: %s" % path)
    if width <= 0 or height <= 0:
        raise ReframeError(
            "أبعاد فيديو غير صالحة في %s: %dx%d" % (path, width, height))
    return {"width": width, "height": height}


def build_reframe_command(input_path, output_path, crop):
    """ابنِ أمر ffmpeg لإعادة التأطير (دالة نقية — للاختبار).

    crop قاموس من reframe_crop. المدخل العمودي أصلًا
    (needs_reframe=False) يُنسخ بايتاته بلا إعادة ترميز
    (-c copy)؛ والأفقي يُقصّ ويُحجَّم إلى أبعاد الهدف
    (crop + scale، فيديو libx264 crf 20، والصوت يُنسخ كما هو).
    """
    if not crop.get("needs_reframe"):
        return ["ffmpeg", "-y", "-v", "error", "-i", input_path,
                "-c", "copy", output_path]
    filt = ("crop=%d:%d:%d:%d,scale=%d:%d:flags=lanczos"
            % (crop["width"], crop["height"], crop["x"], crop["y"],
               crop["out_width"], crop["out_height"]))
    return ["ffmpeg", "-y", "-v", "error", "-i", input_path,
            "-vf", filt, "-c:v", "libx264", "-crf", "20",
            "-preset", "veryfast", "-c:a", "copy", output_path]


def reframe_video(input_path, output_path, focus_x=0.5,
                  safety_margin=0, target_width=REFRAME_WIDTH,
                  target_height=REFRAME_HEIGHT, timeout=300):
    """أعد تأطير مقطع أفقي إلى عمودي 720×1280 (أو الهدف الممرَّر).

    المدخل العمودي أصلًا يمرّ بلا تغيير (نسخ بايتات). يرجع
    قاموس النتيجة {output, source_*, crop, reframed,
    out_width, out_height, size_bytes, seconds}. يرفع
    ReframeError عند ملف مفقود أو أبعاد غير صالحة أو فشل
    ffmpeg أو أبعاد خرج غير مطابقة للمتوقع.
    """
    dims = probe_dimensions(input_path)
    crop = reframe_crop(dims["width"], dims["height"],
                        focus_x=focus_x, safety_margin=safety_margin,
                        target_width=target_width,
                        target_height=target_height)
    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    cmd = build_reframe_command(input_path, output_path, crop)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ReframeError(
            "انتهت مهلة إعادة التأطير (%d ثانية)" % timeout)
    except OSError as e:
        raise ReframeError("تعذر تشغيل ffmpeg: %s" % e)
    if r.returncode != 0:
        raise ReframeError("فشل ffmpeg (رمز الخروج %d):\n%s"
                           % (r.returncode, (r.stderr or "")[-800:]))
    if not os.path.isfile(output_path):
        raise ReframeError(
            "انتهى ffmpeg دون إنشاء ملف الخرج: %s" % output_path)
    out_dims = probe_dimensions(output_path)
    if (out_dims["width"] != crop["out_width"]
            or out_dims["height"] != crop["out_height"]):
        raise ReframeError(
            "أبعاد الخرج غير مطابقة (%dx%d بدل %dx%d)"
            % (out_dims["width"], out_dims["height"],
               crop["out_width"], crop["out_height"]))
    return {"output": output_path,
            "source_width": dims["width"],
            "source_height": dims["height"],
            "crop": crop,
            "reframed": bool(crop["needs_reframe"]),
            "out_width": out_dims["width"],
            "out_height": out_dims["height"],
            "seconds": round(time.time() - t0, 1),
            "size_bytes": os.path.getsize(output_path)}
