#!/usr/bin/env python3
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


class AvatarAspectError(Exception):
    """خطأ نسبة عرض — رسالة عربية."""


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
