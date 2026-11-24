#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""إعدادات الأفاتار الناطق المشتركة — جولة v0.1.38 (مقترحات LongCat).

وحدة منطق خالص (stdlib فقط) تجمع الافتراضيات والتحقق
المشترك للبنود 3 و6 و7 — بدل تكرار الأرقام في كل وحدة:

- معامل التوجيه الصوتي audio_cfg: 3–5، والافتراضي 4.0
  (ملاحظة من تقرير LongCat: `s_audio=4` قد يسبب احمرار
  الشفاه في النسخة غير المقطرة — النطاق 3–5 هو النطاق
  الصالح في الاستدلال المقطّر).
- خطوات الاستدلال: المقطّر 8 افتراضيًا، والكامل 50.
- سياسة نسبة الأبعاد: native/crop/pad/rotate، والافتراضي
  native. "pad" مرفوضة في الوضع الصارم لأن الأشرطة
  الجانبية تشبه أشرطة Veo السوداء — هوية الخط ترفضها.

لا قسم `avatar:` في الإعدادات بعدُ يُقبل — `resolve_avatar_settings`
تقرأه إن وُجد وتتجاهل المفاتيح المجهولة (موثّق).
"""
# البند 3: معامل التوجيه الصوتي (تقرير LongCat §5.أ — النطاق 3–5).
AUDIO_CFG_DEFAULT = 4.0
AUDIO_CFG_MIN = 3.0
AUDIO_CFG_MAX = 5.0

# البند 6: الاستدلال المقطّر 8 خطوات افتراضيًا؛ والكامل 50.
STEPS_DEFAULT = 8
STEPS_FULL = 50

# البند 7: سياسات نسبة الأبعاد (الافتراضي native — النسبة تتبع الصورة).
ASPECT_POLICIES = ("native", "crop", "pad", "rotate")
ASPECT_POLICY_DEFAULT = "native"

# ملفات تعريف العتاد المعروفة (أسماء فقط — التحقق الكامل
# في lib/avatar_profiles.py حتى لا تدور الاستيرادات).
PROFILE_DEFAULT = "t4x2-int8"


class AvatarSettingsError(Exception):
    """خطأ إعداد أفاتار — رسالة عربية."""


def validate_audio_cfg(value):
    """تحقق من معامل التوجيه الصوتي؛ ارجع float أو ارفع خطأً عربيًا."""
    if isinstance(value, bool) or value is None:
        raise AvatarSettingsError(
            "معامل التوجيه الصوتي يجب أن يكون بين 3 و5 "
            "(القيمة: %s)" % (value,))
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise AvatarSettingsError(
            "معامل التوجيه الصوتي يجب أن يكون بين 3 و5 "
            "(القيمة: %s)" % (value,))
    if number != number or number in (float("inf"), float("-inf")):
        raise AvatarSettingsError(
            "معامل التوجيه الصوتي يجب أن يكون بين 3 و5 "
            "(القيمة: %s)" % (value,))
    if number < AUDIO_CFG_MIN or number > AUDIO_CFG_MAX:
        raise AvatarSettingsError(
            "معامل التوجيه الصوتي يجب أن يكون بين 3 و5 "
            "(القيمة: %s)" % (value,))
    return number


def validate_aspect_policy(policy, strict=True):
    """تحقق من سياسة نسبة الأبعاد؛ ارجعها أو ارفع خطأً عربيًا.

    الوضع الصارم (افتراضي تحقق الوظيفة) يرفض "pad" —
    الأشرطة الجانبية مرفوضة لخط «قصص وعبر». الوضع غير
    الصارم يقبلها لاستخدامات أخرى خارج الخط.
    """
    policy = (policy or "").strip() if isinstance(policy, str) else policy
    if policy not in ASPECT_POLICIES:
        raise AvatarSettingsError(
            "سياسة نسبة الأبعاد غير معروفة: %s "
            "(الصالح: %s)" % (policy, "، ".join(ASPECT_POLICIES)))
    if strict and policy == "pad":
        raise AvatarSettingsError(
            "الأشرطة الجانبية مرفوضة لخط «قصص وعبر» — "
            "تشبه أشرطة Veo السوداء")
    return policy


def resolve_steps(full_steps=False):
    """عدد خطوات الاستدلال: 8 مقطّرة افتراضيًا، و50 كاملة."""
    return STEPS_FULL if full_steps else STEPS_DEFAULT


def resolve_avatar_settings(config=None, overrides=None):
    """ادمج إعدادات الأفاتار: افتراضيات ← قسم `avatar:` من
    config.yaml ← تجاوزات وظيفة (`settings`).

    يرجع {"audio_cfg", "full_steps", "aspect_policy", "profile"}.
    المفاتيح المجهولة في الإعداد تُتجاهل (موثّق). اسم الملف
    يُتحقق منه نوعًا فقط هنا؛ والتحقق من وجوده في
    lib/avatar_profiles.py.
    """
    settings = {
        "audio_cfg": AUDIO_CFG_DEFAULT,
        "full_steps": False,
        "aspect_policy": ASPECT_POLICY_DEFAULT,
        "profile": PROFILE_DEFAULT,
    }
    cfg_avatar = {}
    if isinstance(config, dict):
        cfg_avatar = config.get("avatar") or {}
    if not isinstance(cfg_avatar, dict):
        cfg_avatar = {}
    for source in (cfg_avatar, overrides or {}):
        if not isinstance(source, dict):
            continue
        if "audio_cfg" in source:
            settings["audio_cfg"] = validate_audio_cfg(
                source["audio_cfg"])
        if "full_steps" in source:
            settings["full_steps"] = bool(source["full_steps"])
        if "steps" in source:
            # "steps: 8" في الإعداد توثيق وتجاوز — القيمة
            # الوحيدة الصالحة غير الافتراضي هي المسار الكامل.
            try:
                steps = int(source["steps"])
            except (TypeError, ValueError):
                raise AvatarSettingsError(
                    "عدد خطوات الاستدلال يجب أن يكون 8 أو 50 "
                    "(القيمة: %s)" % (source["steps"],))
            if steps == STEPS_FULL:
                settings["full_steps"] = True
            elif steps == STEPS_DEFAULT:
                settings["full_steps"] = False
            else:
                raise AvatarSettingsError(
                    "عدد خطوات الاستدلال يجب أن يكون 8 أو 50 "
                    "(القيمة: %s)" % (steps,))
        if "aspect_policy" in source:
            settings["aspect_policy"] = validate_aspect_policy(
                source["aspect_policy"])
        if "profile" in source:
            profile = source["profile"]
            if not isinstance(profile, str) or not profile.strip():
                raise AvatarSettingsError(
                    "ملف تعريف العتاد يجب أن يكون اسمًا غير فارغ "
                    "(القيمة: %s)" % (profile,))
            settings["profile"] = profile.strip()
    return settings


def avatar_manifest_extra(overrides=None, *, prompt=None,
                          scene_type=None, profile=None):
    """ابنِ حقل `extra["avatar"]` للبيان من إعدادات محلولة.

    يسجّل audio_cfg وsteps وaspect_policy وprofile، و
    `steps_exception: true` فقط عند المسار الكامل (50 خطوة).
    لا حقل جديد في مخطط البيان (SCHEMA_VERSION يبقى 1).
    """
    settings = resolve_avatar_settings(overrides=overrides)
    if profile is not None:
        if not isinstance(profile, str) or not profile.strip():
            raise AvatarSettingsError(
                "ملف تعريف العتاد يجب أن يكون اسمًا غير فارغ "
                "(القيمة: %s)" % (profile,))
        settings["profile"] = profile.strip()
    steps = resolve_steps(settings["full_steps"])
    avatar = {
        "audio_cfg": settings["audio_cfg"],
        "steps": steps,
        "aspect_policy": settings["aspect_policy"],
        "profile": settings["profile"],
    }
    if settings["full_steps"]:
        avatar["steps_exception"] = True
    if prompt:
        avatar["performance_prompt"] = prompt
    if scene_type:
        avatar["scene_type"] = scene_type
    return {"avatar": avatar}
