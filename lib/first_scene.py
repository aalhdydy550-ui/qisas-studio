#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""عيّنة المشهد الأول في وضع dry-run — جولة v0.1.37 (مقترح tinker رقم 7).

بعد طباعة الخطة في `batch --dry-run` و`daily --dry-run`، تُطبع
عيّنة المشهد الأول: نص الكابشن الأول كما سيظهر على الشاشة +
أول جملة سرد منطوقة + مدة المقطع الخام + سرعة atempo — ليمسك
أخطاء الصياغة قبل أي إنفاق Veo.

انحراف موثق عن صيغة التقرير: «مدة المقطع الخام (ffprobe)»
لا تنطبق حرفيًا على مشاريع OpenMontage — مشاهدها صور لا
مقاطع فيديو (ffprobe يعطي ~0.04ث للصورة، رقم مضلل). الرقم
المعروض هو مدة عرض الصورة من الإعدادات (image_clip_seconds)،
موسومًا صراحةً «صورة» لا فيديو.
"""
import os
import re

from lib import openmontage_stage


def _first_sentence(text):
    """أول جملة غير فارغة في نص السرد."""
    for piece in re.split(r"[.!؟\n]+", text or ""):
        piece = piece.strip()
        if piece:
            return piece
    return ""


def first_scene_sample(cfg, project_name):
    """عيّنة المشهد الأول لمشروع OpenMontage جاهز.

    يرجع قاموسًا {hook, first_caption, first_sentence,
    clip_file, clip_seconds, clip_kind, atempo}، أو None إن
    كان المشروع غير موجود أو ناقصًا (لا استثناءات — العيّنة
    تجميلية ولا تفشل الخطة أبدًا).
    """
    cfg = cfg or {}
    root = ((cfg.get("openmontage") or {}).get("root")
            or "~/workspace/openmontage")
    try:
        project_path = openmontage_stage.find_project(root, project_name)
        hook, full_text = openmontage_stage.load_script(project_path)
        phrases = openmontage_stage.build_phrases(
            os.path.join(project_path, "artifacts", "captions.json"))
    except (ValueError, openmontage_stage.StageError):
        return None
    if not phrases:
        return None
    images_dir = os.path.join(project_path, "assets", "images")
    images = []
    if os.path.isdir(images_dir):
        images = sorted(
            f for f in os.listdir(images_dir)
            if f.lower().endswith((".jpg", ".jpeg", ".png")))
    clip_seconds = ((cfg.get("video") or {}).get("image_clip_seconds")
                    or 5)
    try:
        clip_seconds = float(clip_seconds)
    except (TypeError, ValueError):
        clip_seconds = 5
    atempo = ((cfg.get("narration") or {}).get("atempo") or 1.0)
    try:
        atempo = float(atempo)
    except (TypeError, ValueError):
        atempo = 1.0
    return {
        "project": project_name,
        "hook": hook,
        "first_caption": phrases[0]["text"],
        "first_sentence": _first_sentence(full_text),
        "clip_file": images[0] if images else None,
        "clip_seconds": clip_seconds,
        "clip_kind": "image",
        "atempo": atempo,
    }


def format_sample(sample):
    """نص عربي للعيّنة (للطباعة بعد الخطة في dry-run)."""
    lines = ["-- عيّنة المشهد الأول (قبل أي إنفاق) --",
             "الكابشن الأول كما سيظهر: «%s»"
             % sample["first_caption"],
             "أول جملة سرد منطوقة: «%s»"
             % sample["first_sentence"]]
    if sample.get("clip_file"):
        lines.append("المقطع الخام: صورة %s (تُعرض %.0f ثوانٍ)"
                     % (sample["clip_file"], sample["clip_seconds"]))
    else:
        lines.append("المقطع الخام: بلا صور في المشروع")
    lines.append("سرعة السرد atempo: %s" % (sample["atempo"],))
    return "\n".join(lines)
