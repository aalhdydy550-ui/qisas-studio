#!/usr/bin/env python3
"""ربط الوضع التلقائي لـOpenReel بـstudio كخلفية تجميع بديلة ثالثة.

يبني مشروع `openreel-auto` v1 JSON من بيان studio (manifest)
ويستدعي `render.py` في مجلد openreel-auto. لا ينسخ كود
render.py — يستخدم CLI الخاص به فقط (`--project`/`--out`)،
ولا يعدّل كود OpenReel الأصلي إطلاقًا.

الخريطة (نفس ما يفعله تجميع Concat):
- صور manifest["sequence"] مقاطع صورة ثابتة (kind=image) بمدة
  image_clip_seconds لكلٍّ منها (المدة صريحة — render.py
  يشترطها للصور لأن ffprobe يقرأ للصورة ~0.04ث).
- السرد `narration-full.wav` مسارًا صوتيًا بمستوى 1.0 من الثانية 0.
- العنوان (الهوك) نصًا أسفل الشاشة فوق العبارات أول 4 ثوانٍ
  (قاعدة دائمة 2026-11-22: لا نص أعلى الشاشة أبدًا — الهوك
  يُثبَّت بإحداثيات صريحة فوق نطاق الكابشن لا بموضع "top").
- عبارات manifest["phrases"] نصوصًا أسفل الشاشة بأوقاتها
  (مثل captions_add).

الشعار لا يُضاف هنا — خطوة الإنهاء `_finish_video` في
studio.py تضيفه بعد الريندر (فلا شعار مزدوج).

الريندر أبطأ من الزمن الحقيقي (~3× بلا GPU) — فيديو 50ث
يحتاج ~3 دقائق؛ المهلة الافتراضية 1200 ثانية.

Concat يبقى الافتراضي؛ هذه الخلفية اختيارية عبر
`assemble --backend openreel` أو `run --backend openreel`.
"""
import json
import os
import subprocess
import sys
import time


class OpenReelError(Exception):
    """خطأ في بناء مشروع OpenReel أو الريندر (رسالته عربية)."""


HOOK_DURATION_SECONDS = 4.0
HOOK_FONTSIZE = 58
CAPTION_FONTSIZE = 44
# قاعدة دائمة 2026-11-22: كل نصوص الشاشة أسفل فقط، ولا نص أعلى
# أبدًا. الهوك يُثبَّت بإحداثيات صريحة (x/y) فوق نطاق الكابشن:
# حافته السفلى على هذا البعد من أسفل الإطار؛ الكابشن (نمط bottom
# في render.py، MarginV=70) قمته نحو 110px فوق حافته السفلى،
# فالفجوة بين الهوك (سطران ~150px) والكابشن ~100px ولا تداخل.
HOOK_BOTTOM_OFFSET_PX = 280


def build_project(manifest, title, assets_dir, video_cfg):
    """ابنِ قاموس مشروع openreel-auto v1 من بيان studio.

    دوال نقية (بلا ملفات وبلا شبكة) — قابلة للاختبار مباشرة.
    """
    clip_seconds = float(manifest.get(
        "image_clip_seconds",
        video_cfg.get("image_clip_seconds", 5)))
    width = int(video_cfg["width"])
    height = int(video_cfg["height"])
    fps = int(video_cfg["fps"])
    from lib.paths import resolve_inside, safe_component
    images_dir = os.path.join(assets_dir, "images")
    clips = []
    start = 0.0
    for name in manifest["sequence"]:
        # نفس حارس headless_stage: اسم من البيان بلا تحقق كان
        # يشير إلى ملف خارج مجلد الأصول.
        safe_component(name, "اسم الصورة")
        src = resolve_inside(images_dir, os.path.join(images_dir, name),
                             "صورة الفصل")
        clips.append({
            "file": src,
            "kind": "image",
            "duration": clip_seconds,
        })
        start += clip_seconds
    narration = os.path.join(assets_dir, "audio", "narration-full.wav")
    duration = float(manifest.get("narration_duration") or 0.0)
    if duration > 0 and clips and start < duration:
        # مدّد آخر صورة حتى تغطي السرد كاملًا (وإلا قُصّ ذيل السرد
        # وآخر عبارة، كما في Concat الذي يطابق مدة الفيديو للسرد).
        clips[-1]["duration"] = round(
            clips[-1]["duration"] + (duration - start), 3)
    project = {
        "format": "openreel-auto",
        "version": 1,
        "name": manifest.get("project", "studio"),
        "settings": {"width": width, "height": height,
                     "frameRate": fps, "sampleRate": 48000},
        "clips": clips,
        "texts": [],
        "narration": {"file": narration, "volume": 1.0},
    }
    if title:
        # الهوك أسفل الشاشة فوق العبارات (لا "top" أبدًا — قاعدة
        # دائمة 2026-11-22): موضع bottom + إحداثيات صريحة يمررها
        # render.py إلى وسم \pos في ASS؛ (x,y) هنا نقطة الارتكاز
        # (أسفل-وسط) لأن محاذاة bottom هي 2.
        project["texts"].append({
            "text": title,
            "start": 0,
            "end": HOOK_DURATION_SECONDS,
            "size": HOOK_FONTSIZE,
            "color": "#FFFFFF",
            "position": "bottom",
            "x": width // 2,
            "y": height - HOOK_BOTTOM_OFFSET_PX,
        })
    for p in manifest.get("phrases", []):
        project["texts"].append({
            "text": p["text"],
            "start": float(p["start"]),
            "end": float(p["end"]),
            "size": CAPTION_FONTSIZE,
            "color": "#FFFFFF",
            "position": "bottom",
        })
    return project


def render_project(render_path, project_path, out_path, timeout=1200):
    """شغّل `render.py --project ... --out ...` على مشروع JSON.

    يرجع قاموس النتيجة {"output", "seconds", "size_bytes",
    "duration"} — يرفع OpenReelError برسالة عربية عند أي فشل
    (ثنائي مفقود، مهلة، خروج غير صفري، بلا ملف خرج، أو خرج
    JSON غير صالح).
    """
    if not os.path.isfile(render_path):
        raise OpenReelError("ملف ريندر OpenReel غير موجود: %s"
                            % render_path)
    cmd = [sys.executable, render_path, "--project", project_path,
           "--out", out_path]
    t0 = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=timeout)
    except subprocess.TimeoutExpired:
        raise OpenReelError("انتهت مهلة ريندر OpenReel (%d ثانية) — "
                            "أعد المحاولة والجهاز فاضٍ" % timeout)
    except OSError as e:
        raise OpenReelError("تعذر تشغيل ريندر OpenReel: %s" % e)
    if result.returncode != 0:
        tail = ((result.stderr or "") + (result.stdout or ""))[-1200:]
        raise OpenReelError("فشل ريندر OpenReel (رمز الخروج %d):\n%s"
                            % (result.returncode, tail))
    if not os.path.isfile(out_path):
        raise OpenReelError("انتهى ريندر OpenReel دون إنشاء ملف الخرج: %s"
                            % out_path)
    summary = None
    for line in (result.stdout or "").strip().splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            summary = json.loads(line)
        except ValueError:
            continue
    duration = (summary or {}).get("duration")
    return {"output": out_path,
            "seconds": round(time.time() - t0, 1),
            "size_bytes": os.path.getsize(out_path),
            "duration": duration}
