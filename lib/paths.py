#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""مسارات آمنة مشتركة — احتواء الملفات داخل مجلدات مسموحة.

كل وحدة lib تستورد من هنا (بلا اعتماديات على studio لتفادي
الاستيراد الدائري). القاعدة: أي اسم أو مسار قادم من ملف بيانات
(بيان manifest، ملف فصول JSON، طابور، طلب عميل) يجب أن يبقى
داخل المجلد المسموح له؛ أما المسارات التي يكتبها المشغّل نفسه
في سطر الأوامر فهي مقصودة، لكن مدخلات ملفات البيانات تُحصَر
دائمًا داخل مساحة العمل أو مجلد التشغيل.
"""
import os

WORKSPACE_ROOT = os.path.realpath(os.path.expanduser("~/workspace"))

MAX_VIDEO_WIDTH = 3840
MAX_VIDEO_HEIGHT = 2160


def realpath(p):
    return os.path.realpath(os.path.expanduser(os.path.expandvars(str(p))))


def inside(base, path):
    """هل المسار (بعد حل الروابط الرمزية) داخل base؟"""
    b = os.path.realpath(str(base))
    t = os.path.realpath(str(path))
    return t == b or t.startswith(b + os.sep)


def resolve_inside(base, path, what="المسار"):
    """حلّ المسار وارفضه إن خرج من base. يرجع المسار الحقيقي."""
    t = realpath(path)
    if not inside(base, t):
        raise ValueError("%s خارج المجلد المسموح (%s): %s"
                         % (what, base, path))
    return t


def resolve_inside_workspace(path, what="المسار"):
    """حلّ المسار وارفضه إن خرج من مساحة العمل ~/workspace."""
    return resolve_inside(WORKSPACE_ROOT, path, what)


def safe_component(name, what="اسم المكوّن"):
    """تحقق من مكوّن مسار واحد (اسم ملف بلا مجلدات).

    يرفض: فارغًا، NUL، البدء بنقطة أو بشرطة (حقن أعلام)، فواصل
    مسارات، و'..'. القيم الصالحة مثل: scene1.jpg، anza-part1.
    """
    if not isinstance(name, str) or not name:
        raise ValueError("%s غير صالح: قيمة فارغة" % what)
    if "\x00" in name:
        raise ValueError("%s غير صالح: يحوي حرف NUL" % what)
    if name.startswith((".", "-")):
        raise ValueError("%s غير صالح: يبدأ بنقطة أو شرطة" % what)
    if "/" in name or "\\" in name:
        raise ValueError("%s غير صالح: يحوي فاصل مسار" % what)
    if ".." in name:
        raise ValueError("%s غير صالح: يحوي '..'" % what)
    return name


def check_size(width, height, what="المقاس"):
    """ارفض أبعادًا غير موجبة أو فوق 4K (استنفاد ذاكرة في الريندر)."""
    if width <= 0 or height <= 0:
        raise ValueError("%s يجب أن تكون أبعاده موجبة (وصل: %dx%d)"
                         % (what, width, height))
    if width > MAX_VIDEO_WIDTH or height > MAX_VIDEO_HEIGHT:
        raise ValueError("%s فوق الحد الأقصى %dx%d (وصل: %dx%d)"
                         % (what, MAX_VIDEO_WIDTH, MAX_VIDEO_HEIGHT,
                            width, height))
    return width, height
