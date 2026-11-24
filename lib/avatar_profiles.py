#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""ملفات تعريف العتاد للأفاتار الناطق — جولة v0.1.38 (بند 5).

ثلاثة ملفات من تقرير LongCat (§5.أ): t4x2-int8 (الافتراضي —
العتاد المتاح في الاختبار التجريبي على Kaggle)، وa100-bf16،
وrtx4090-int8. كل ملف يولّد أعلام CLI لسكربت الاستدلال
الأصلي، و`validate_flags` يرفض `--use_fp8` مع `--use_int8`
معًا (مطابقًا `parser.error` في السكربت الأصلي).

السرعات المتوقعة تقديرات من التقرير نفسه (يُقاس الفعلي
في الاختبار) — لا أرقام مخترعة.
"""
from lib import avatar_settings as settings_lib

PROFILES = {
    "t4x2-int8": {
        "gpus": 2,
        "use_int8": True,
        "context_parallel_size": 2,
        "resolution": "480p",
        "expected_vram_gb": 15,
        "expected_speed": "تقدير — يُقاس في الاختبار",
    },
    "a100-bf16": {
        "gpus": 1,
        "use_int8": False,
        "context_parallel_size": 1,
        "resolution": "720p",
        "expected_vram_gb": 40,
        "expected_speed": "تقدير — يُقاس في الاختبار",
    },
    "rtx4090-int8": {
        "gpus": 1,
        "use_int8": True,
        "context_parallel_size": 1,
        "resolution": "720p",
        "expected_vram_gb": 24,
        "expected_speed": "~16ث حساب/ث فيديو (رقم واحد منشور)",
    },
}


class AvatarProfilesError(Exception):
    """خطأ ملف تعريف عتاد — رسالة عربية."""


def list_profiles():
    """أسماء ملفات التعريف المعروفة (مرتبة)."""
    return sorted(PROFILES)


def get_profile(name):
    """قاموس ملف التعريف (نسخة) أو خطأ عربي إن مجهول."""
    if not isinstance(name, str) or name not in PROFILES:
        raise AvatarProfilesError(
            "ملف تعريف العتاد غير معروف: %s (الصالح: %s)"
            % (name, "، ".join(list_profiles())))
    return dict(PROFILES[name])


def profile_flags(name):
    """أعلام CLI لسكربت الاستدلال من ملف التعريف."""
    profile = get_profile(name)
    flags = ["--nproc_per_node=%d" % profile["gpus"],
             "--context_parallel_size=%d"
             % profile["context_parallel_size"]]
    if profile["use_int8"]:
        flags.append("--use_int8")
    flags += ["--resolution", profile["resolution"]]
    return flags


def validate_flags(flags):
    """تحقق من أعلام CLI: --use_fp8 مع --use_int8 مرفوضان معًا.

    يرجع قائمة الأعلام كما هي (نسخة) أو يرفع خطأً عربيًا.
    """
    flags = list(flags or [])
    if "--use_fp8" in flags and "--use_int8" in flags:
        raise AvatarProfilesError(
            "لا يمكن الجمع بين --use_fp8 و--use_int8 في استدعاء واحد")
    return flags


def profile_for_job(job):
    """ملف تعريف وظيفة: من settings.profile أو الافتراضي t4x2-int8.

    الوظيفة قاموس (أو بلا settings)؛ والاسم المجهول يُرفض.
    """
    name = settings_lib.PROFILE_DEFAULT
    if isinstance(job, dict):
        settings = job.get("settings") or {}
        if isinstance(settings, dict) and settings.get("profile"):
            name = settings["profile"]
    return get_profile(name)
