#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""ربط نواة headless-editor بـstudio كخلفية تجميع بديلة لـConcat.

يبني مشروع JSON من بيان studio (manifest) ويستدعي
`editor.py render` في مجلد headless-editor. لا يعدّل كود النواة
— يستخدم CLI الخاص بها فقط (`render`).

الخريطة (نفس ما يفعله تجميع Concat):
- صور manifest["sequence"] مقاطع 5 ثوانٍ بقص صلب (بلا انتقالات،
  حتى تطابق مدة الفيديو مدة السرد بالتقريب كما في Concat).
- السرد `narration-full.wav` مسارًا صوتيًا بمستوى 1.0 من الثانية 0.
- العنوان (الهوك) نصًا أسفل الشاشة فوق العبارات أول 4 ثوانٍ
  (موضع "above" — قاعدة دائمة 2026-11-22: لا نص أعلى أبدًا).
- عبارات manifest["phrases"] نصوصًا أسفل الشاشة بأوقاتها
  (مثل captions_add).

Concat يبقى الافتراضي؛ هذه الخلفية اختيارية عبر
`assemble --backend headless` أو `run --backend headless`.
"""
import json
import os
import subprocess
import sys
import time


class HeadlessError(Exception):
    """خطأ في بناء مشروع headless أو الريندر (رسالته عربية)."""


HOOK_DURATION_SECONDS = 4.0
HOOK_FONTSIZE = 58
CAPTION_FONTSIZE = 44


def build_project(manifest, title, assets_dir, video_cfg):
    """ابنِ قاموس مشروع headless-editor من بيان studio.

    دوال نقية (بلا ملفات وبلا شبكة) — قابلة للاختبار مباشرة.
    """
    clip_seconds = float(manifest.get(
        "image_clip_seconds",
        video_cfg.get("image_clip_seconds", 5)))
    width = int(video_cfg["width"])
    height = int(video_cfg["height"])
    fps = int(video_cfg["fps"])
    tracks = []
    start = 0.0
    from lib.paths import resolve_inside, safe_component
    images_dir = os.path.join(assets_dir, "images")
    for name in manifest["sequence"]:
        # إصلاح اختبار اختراق 2026-11-21: اسم من البيان بلا تحقق
        # كان يشير إلى ملف خارج مجلد الأصول (../../../../etc/passwd).
        safe_component(name, "اسم الصورة")
        src = resolve_inside(images_dir, os.path.join(images_dir, name),
                             "صورة الفصل")
        tracks.append({
            "type": "image",
            "src": src,
            "start": round(start, 3),
            "duration": clip_seconds,
            "transition_in": "none",
        })
        start += clip_seconds
    narration = os.path.join(assets_dir, "audio", "narration-full.wav")
    duration = float(manifest.get("narration_duration") or 0.0)
    if duration > 0 and tracks and start < duration:
        # مدّد آخر صورة حتى تغطي السرد كاملًا (وإلا قُصّ ذيل السرد
        # وآخر عبارة، كما في Concat الذي يطابق مدة الفيديو للسرد).
        # الفرق دائمًا أقل من مدة مقطع واحد لأن عدد المقاطع
        # = تقريب(مدة السرد / مدة المقطع).
        tracks[-1]["duration"] = round(
            tracks[-1]["duration"] + (duration - start), 3)
    if duration > 0:
        tracks.append({
            "type": "audio",
            "src": narration,
            "start": 0,
            "duration": round(duration, 3),
            "volume": 1.0,
        })
    if title:
        tracks.append({
            "type": "text",
            "text": title,
            "start": 0,
            "end": HOOK_DURATION_SECONDS,
            # "above" = أسفل الشاشة فوق الكابشن (قاعدة دائمة
            # 2026-11-22: لا نص أعلى الشاشة أبدًا).
            "position": "above",
            "fontsize": HOOK_FONTSIZE,
        })
    for p in manifest.get("phrases", []):
        tracks.append({
            "type": "text",
            "text": p["text"],
            "start": float(p["start"]),
            "end": float(p["end"]),
            "position": "bottom",
            "fontsize": CAPTION_FONTSIZE,
        })
    return {
        "name": manifest.get("project", "studio"),
        "width": width,
        "height": height,
        "fps": fps,
        "tracks": tracks,
    }


def render_project(editor_path, project_path, out_path, timeout=900):
    """شغّل `editor.py render` على مشروع JSON. يرجع قاموس النتيجة.

    يرفع HeadlessError برسالة عربية عند أي فشل (ثنائي مفقود،
    مهلة، خروج غير صفري، بلا ملف خرج).
    """
    if not os.path.isfile(editor_path):
        raise HeadlessError("ملف محرر headless غير موجود: %s"
                            % editor_path)
    cmd = [sys.executable, editor_path, "render", project_path,
           "-o", out_path]
    t0 = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=timeout)
    except subprocess.TimeoutExpired:
        raise HeadlessError("انتهت مهلة ريندر headless (%d ثانية) — "
                            "أعد المحاولة والجهاز فاضٍ" % timeout)
    except OSError as e:
        raise HeadlessError("تعذر تشغيل محرر headless: %s" % e)
    if result.returncode != 0:
        tail = ((result.stderr or "") + (result.stdout or ""))[-1200:]
        raise HeadlessError("فشل ريندر headless (رمز الخروج %d):\n%s"
                            % (result.returncode, tail))
    if not os.path.isfile(out_path):
        raise HeadlessError("انتهى ريندر headless دون إنشاء ملف الخرج: %s"
                            % out_path)
    return {"output": out_path,
            "seconds": round(time.time() - t0, 1),
            "size_bytes": os.path.getsize(out_path)}
