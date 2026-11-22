#!/usr/bin/env python3
"""القصة التجريبية المدمجة — `studio.py run --demo`.

قصة قصيرة أصلية (3 مشاهد) تُرنَّد إلى فيديو عمودي حقيقي 720×1280
عبر المسار المجاني فقط: سرد Piper (رجل) + صور خلفية مولّدة محليًا
+ كتابة متزامنة + شعار الصفحة. بلا Veo، بلا مفاتيح API، بلا شبكة.

الصور خلفيات متدرجة دافئة مولّدة بـ Pillow (بلا نص عربي فيها —
النص العربي يظهر كمسارات نص في المحرر، فيشكّله libass صحيحًا).
أزمنة العبارات من أزمنة جمل Piper نفسها (long_narration)، فالكتابة
متزامنة مع الكلام عبارة بعبارة كما في خط الإنتاج الحقيقي.
"""
import json
import os
import random
import time

from lib import headless_stage
from lib import long_narration
from lib import watermark

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_DIR = os.path.join(STUDIO_DIR, "demo")
STORY_FILE = os.path.join(DEMO_DIR, "story.txt")
META_FILE = os.path.join(DEMO_DIR, "meta.json")

GAP_SECONDS = 0.35
HOOK_DURATION_SECONDS = 4.0
CAPTION_FONTSIZE = 44
HOOK_FONTSIZE = 58

# خلفيات دافئة لكل مشهد: (لون أعلى، لون أسفل) — ذهبي/ترابي/أخضر.
SCENE_COLORS = {
    "gold": ((58, 32, 8), (198, 143, 58)),
    "earth": ((46, 26, 14), (148, 98, 54)),
    "green": ((14, 42, 26), (76, 132, 84)),
}
DEFAULT_COLORS = ((40, 26, 12), (150, 105, 55))


class DemoError(Exception):
    """خطأ في بناء التجربة أو ريندرها (رسالته عربية)."""


def load_demo(studio_dir=None):
    """اقرأ القصة والبيانات الوصفية. يرجع {title, hook, moral, scenes}."""
    base = os.path.join(studio_dir or STUDIO_DIR, "demo")
    story_path = os.path.join(base, "story.txt")
    meta_path = os.path.join(base, "meta.json")
    if not os.path.isfile(story_path):
        raise DemoError("ملف القصة التجريبية غير موجود: %s" % story_path)
    with open(story_path, encoding="utf-8") as f:
        text = f.read()
    scenes = [s.strip() for s in text.strip().split("\n\n") if s.strip()]
    if not scenes:
        raise DemoError("القصة التجريبية فارغة")
    meta = {}
    if os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    hues = [s.get("hue", "gold") for s in meta.get("scenes", [])]
    while len(hues) < len(scenes):
        hues.append("gold")
    return {
        "title": meta.get("title", "القصة التجريبية"),
        "hook": meta.get("hook", ""),
        "moral": meta.get("moral", ""),
        "scenes": scenes,
        "hues": hues[:len(scenes)],
        "ken_burns": [s.get("ken_burns", "in")
                       for s in meta.get("scenes", [])][:len(scenes)],
    }


def make_scene_image(path, width, height, hue="gold", seed=7):
    """ولّد خلفية متدرجة دافئة 720×1280 (بلا نص).

    تدرج عمودي + توهجين دائريين ناعمين + حبيبات خفيفة، حتى لا تبدو
    الصورة مسطحة تحت الكتابة. Pillow فقط — بلا شبكة وبلا خطوط.
    """
    from PIL import Image, ImageDraw, ImageFilter
    top, bottom = SCENE_COLORS.get(hue, DEFAULT_COLORS)
    img = Image.new("RGB", (width, height))
    px = img.load()
    for y in range(height):
        t = y / max(height - 1, 1)
        px_line = tuple(int(top[i] + (bottom[i] - top[i]) * t)
                        for i in range(3))
        for x in range(width):
            px[x, y] = px_line
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    rnd = random.Random(seed)
    for _ in range(3):
        cx = rnd.randint(width // 4, 3 * width // 4)
        cy = rnd.randint(height // 5, 4 * height // 5)
        r = rnd.randint(180, 320)
        warm = (255, 205, 120, 26)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=warm)
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    # حبيبات خفيفة لكسر التدرج
    noise = Image.effect_noise((width, height), 14).convert("L")
    img = Image.blend(img, Image.merge("RGB", (noise, noise, noise)), 0.05)
    img.save(path, "JPEG", quality=88)
    return path


def build_demo_project(cfg, work_dir):
    """ابنِ مشروع headless-editor للتجربة + السرد.

    يرجع (project, info) حيث info فيه مسار السرد والمدة والعبارات.
    السرد يُركَّب مشهدًا مشهدًا (أزمنة دقيقة لكل مشهد ولكل جملة).
    """
    demo = load_demo()
    width = int(cfg["video"]["width"])
    height = int(cfg["video"]["height"])
    fps = int(cfg["video"]["fps"])
    assets_dir = os.path.join(work_dir, "assets")
    images_dir = os.path.join(assets_dir, "images")
    audio_dir = os.path.join(assets_dir, "audio")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)

    tracks = []
    all_chunks = []
    scene_wavs = []
    cursor = 0.0
    for i, scene_text in enumerate(demo["scenes"]):
        scene_wav = os.path.join(audio_dir, "scene%d.wav" % (i + 1))
        result = long_narration.synthesize_long(
            scene_text, scene_wav, gap=GAP_SECONDS)
        scene_wavs.append(scene_wav)
        img_name = "scene%d.jpg" % (i + 1)
        img_path = os.path.join(images_dir, img_name)
        make_scene_image(img_path, width, height,
                         demo["hues"][i], seed=7 + i)
        dur = result["duration"]
        kb = demo["ken_burns"][i] if i < len(demo["ken_burns"]) else "in"
        tracks.append({
            "type": "image",
            "src": img_path,
            "start": round(cursor, 3),
            "duration": round(dur + GAP_SECONDS, 3),
            "transition_in": "none",
            "ken_burns": kb,
        })
        for ch in result["chunks"]:
            all_chunks.append({
                "text": ch["text"],
                "start": round(cursor + ch["start"], 3),
                "end": round(cursor + ch["end"], 3),
            })
        cursor += dur + GAP_SECONDS
    total = round(cursor - GAP_SECONDS, 3)  # بلا فاصل بعد المشهد الأخير
    tracks[-1]["duration"] = round(
        tracks[-1]["duration"] - GAP_SECONDS, 3)

    narration_path = os.path.join(audio_dir, "narration-full.wav")
    long_narration.concatenate_with_gaps(scene_wavs, narration_path,
                                         gap=GAP_SECONDS)
    tracks.append({
        "type": "audio",
        "src": narration_path,
        "start": 0,
        "duration": total,
        "volume": 1.0,
    })
    if demo["hook"]:
        tracks.append({
            "type": "text",
            "text": demo["hook"],
            "start": 0,
            "end": HOOK_DURATION_SECONDS,
            # "above" = أسفل الشاشة فوق الكابشن (قاعدة دائمة
            # 2026-11-22: لا نص أعلى الشاشة أبدًا).
            "position": "above",
            "fontsize": HOOK_FONTSIZE,
        })
    for ch in all_chunks:
        tracks.append({
            "type": "text",
            "text": ch["text"],
            "start": ch["start"],
            "end": ch["end"],
            "position": "bottom",
            "fontsize": CAPTION_FONTSIZE,
        })
    project = {
        "name": "demo",
        "width": width,
        "height": height,
        "fps": fps,
        "tracks": tracks,
    }
    info = {
        "title": demo["title"],
        "hook": demo["hook"],
        "moral": demo["moral"],
        "narration": narration_path,
        "duration": total,
        "chunks": all_chunks,
        "scenes": len(demo["scenes"]),
    }
    return project, info


def run_demo(cfg, out_path, studio_dir=None, runs_dir=None,
             backend="headless"):
    """نفّذ التجربة كاملة: بناء + ريندر + شعار. يرجع معلومات الناتج."""
    if backend != "headless":
        raise DemoError("التجربة تعمل بخلفية headless فقط (وصل: %s)"
                        % backend)
    studio_dir = studio_dir or STUDIO_DIR
    runs_dir = runs_dir or os.path.expanduser(
        cfg["paths"]["runs_dir"])
    run_id = "demo-%s" % time.strftime("%Y%m%d-%H%M%S")
    work_dir = os.path.join(runs_dir, run_id)
    os.makedirs(work_dir, exist_ok=True)
    project, info = build_demo_project(cfg, work_dir)
    project_path = os.path.join(work_dir, "demo-project.json")
    with open(project_path, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)
    editor_path = os.path.expanduser(cfg["headless"]["editor"])
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    result = headless_stage.render_project(editor_path, project_path,
                                           out_path)
    watermark.apply_watermark(out_path, out_path)
    log = {"run": run_id, "story": "demo", "title": info["title"],
           "duration": info["duration"], "scenes": info["scenes"],
           "chunks": len(info["chunks"]), "output": out_path,
           "seconds": result["seconds"]}
    with open(os.path.join(work_dir, "demo.json"), "w",
              encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    return {"output": out_path, "duration": info["duration"],
            "run_dir": work_dir, "run_id": run_id,
            "seconds": result["seconds"],
            "size_bytes": os.path.getsize(out_path),
            "title": info["title"], "hook": info["hook"],
            "moral": info["moral"]}
