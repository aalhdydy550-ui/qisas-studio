#!/usr/bin/env python3
"""client-orders — تنفيذ طلبات فيديو العملاء لنظام studio.

طلب العميل (من صفحة الطلب) → توسيع الوصف إلى سيناريو كامل عبر
OmniRoute → سرد Piper (كريم، رجل) → صور Wikimedia Commons →
مشروع OpenMontage → خط إنتاج studio (run) → فيديو + صورة مصغرة →
تحديث حالة الطلب.

الأوامر:
  client_orders.py client-run --order CO-...   # طلب واحد من orders.jsonl
  client_orders.py process-queue               # كل الطلبات الجديدة

لا يمس طابور القصص ولا كرونات النشر ولا منشورات فيسبوك. لا يستخدم
Veo (الإنتاج OpenMontage فقط). لا يخترع أسعارًا.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import studio  # noqa: E402  (studio.py في نفس المجلد)

ORDERS_DIR = os.path.join(os.path.expanduser("~"), "workspace", "studio",
                          "client-orders")
ORDERS_FILE = os.path.join(ORDERS_DIR, "orders.jsonl")
OUT_ROOT = os.path.join(os.path.expanduser("~"), "workspace", "videos",
                        "client-orders")
PIPER_BIN = os.path.join(os.path.expanduser("~"), ".local", "bin", "piper")
PIPER_MODEL = os.path.join(os.path.expanduser("~"), "workspace",
                           "tts-models", "ar_JO-kareem-medium.onnx")
ATEMPO = 1.25          # سرعة السرد (إيقاع Kwai ~109 كلمة/دقيقة)
SILENCE_GAP = 0.3      # ثواني صمت بين المشاهد
SECONDS_PER_WORD = 0.56  # تقدير مدة الكلمة بعد atempo (كريم ~0.7 ث طبيعي)
DURATION_TARGETS = {"30-40": 35, "40-60": 50, "60-90": 75}
WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "qisas-studio-client-orders/0.1 (contact: studio local)"}


class ClientOrderError(Exception):
    pass


def _safe_slug(order_id):
    """معرّف آمن لمسارات الملفات من رقم الطلب (قد يأتي من الصفحة بأي صيغة)."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", str(order_id or "")).strip("-")
    if not safe:
        raise ClientOrderError("رقم طلب فارغ أو بلا حروف صالحة: %s"
                               % order_id)
    return safe


def _normalize_size(size):
    """مقاس الطلب إلى (عرض، ارتفاع): يقبل vertical/horizontal أو WxH."""
    s = str(size or "").strip().lower()
    if s in ("vertical", "720x1280", "720*1280"):
        return 720, 1280
    if s in ("horizontal", "1280x720", "1280*720"):
        return 1280, 720
    m = re.match(r"^(\d+)\s*x\s*(\d+)$", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 720, 1280


# ---------------------------------------------------------------- orders
def load_orders():
    orders = []
    if not os.path.isfile(ORDERS_FILE):
        return orders
    with open(ORDERS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                orders.append(json.loads(line))
    return orders


def save_orders(orders):
    os.makedirs(ORDERS_DIR, exist_ok=True)
    tmp = ORDERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for o in orders:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    os.replace(tmp, ORDERS_FILE)


def get_order(order_id):
    for o in load_orders():
        if o.get("id") == order_id:
            return o
    return None


def update_order(order_id, **fields):
    orders = load_orders()
    found = False
    for o in orders:
        if o.get("id") == order_id:
            o.update(fields)
            o["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            found = True
    if not found:
        raise ClientOrderError("الطلب غير موجود في %s: %s"
                               % (ORDERS_FILE, order_id))
    save_orders(orders)


def append_order(order):
    orders = load_orders()
    if any(o.get("id") == order.get("id") for o in orders):
        raise ClientOrderError("طلب بنفس الرقم موجود بالفعل: %s"
                               % order.get("id"))
    orders.append(order)
    save_orders(orders)


# ------------------------------------------------------- story expansion
EXPAND_PROMPT = (
    "أنت كاتب قصص قصيرة مؤثرة بالعامية المصرية لقناة «قصص وعبر». "
    "اكتب قصة قصيرة كاملة بعبرة عن الموضوع التالي: {description}\n"
    "القصة لفيديو قصير مدته المستهدفة {target_seconds} ثانية، والسرد "
    "بصوت راوٍ رجل. أرجع JSON فقط بهذا الشكل بالضبط (بدون أي نص آخر):\n"
    '{{"hook": "عنوان هوك صادم من 8 كلمات بالعامية المصرية", '
    '"scenes": [{{"text": "نص السرد بالعامية المصرية", '
    '"image_keywords": ["english", "keywords"]}}], '
    '"moral": "العبرة في جملة واحدة"}}.\n'
    "الشروط: 5-6 مشاهد؛ مجموع كلمات نصوص المشاهد حوالي {target_words} "
    "كلمة؛ المشهد الأول هو الهوك الصادم نفسه (ابدأ فورًا بلا مقدمة)؛ "
    "المشهد الأخير ينتهي بالعبرة؛ كل مشهد له كلمتان أو ثلاث كلمات "
    "مفتاحية بالإنجليزية تصف صورته؛ النص كله بالعامية المصرية. "
    "إن كان الوصف قصة كاملة أصلًا فاحتفظ بأحداثها."
)


def _parse_story_json(text):
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ClientOrderError("تعذر قراءة سيناريو JSON من رد الذكاء")
    try:
        data = json.loads(text[start:end + 1])
    except ValueError as e:
        raise ClientOrderError("سيناريو JSON تالف: %s" % e)
    if not isinstance(data, dict) or not (data.get("hook") or "").strip():
        raise ClientOrderError("السيناريو بلا هوك")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not 3 <= len(scenes) <= 8:
        raise ClientOrderError("السيناريو يحتاج 3-8 مشاهد (وصل %s)"
                               % (len(scenes) if isinstance(scenes, list)
                                  else "بلا مشاهد"))
    for i, s in enumerate(scenes):
        if not isinstance(s, dict) or not (s.get("text") or "").strip():
            raise ClientOrderError("المشهد %d بلا نص سرد" % (i + 1))
        kws = s.get("image_keywords") or []
        s["image_keywords"] = [str(k).strip() for k in kws if str(k).strip()]
    if not (data.get("moral") or "").strip():
        raise ClientOrderError("السيناريو بلا عبرة")
    return data


def expand_story(cfg, description, target_seconds):
    """وصف العميل → سيناريو كامل (هوك + مشاهد + عبرة) عبر OmniRoute."""
    target_words = max(30, int(target_seconds / SECONDS_PER_WORD))
    prompt = EXPAND_PROMPT.format(description=description,
                                  target_seconds=target_seconds,
                                  target_words=target_words)
    cfg_o = cfg["omniroute"]
    last_err = None
    for attempt in (1, 2):
        try:
            text, via, model = studio.omniroute_client.chat(
                prompt, cfg_o["model"], cfg_o.get("fallback_model"),
                cfg_o["base_url"], max_tokens=1500, temperature=0.7,
                retries=int(cfg_o.get("retries", 1)),
                retry_delay=int(cfg_o.get("retry_delay_seconds", 5)))
            story = _parse_story_json(text)
            print("وُسّع الوصف إلى سيناريو (%d مشاهد، عبر %s/%s)"
                  % (len(story["scenes"]), via, model))
            return story
        except Exception as e:
            last_err = e
            print("فشل توسيع القصة (محاولة %d): %s" % (attempt, e))
            prompt = (prompt + "\nتنبيه: أرجع JSON صالحًا فقط، بلا أي "
                      "نص خارجه.")
    raise ClientOrderError("تعذر توسيع وصف العميل إلى سيناريو: %s"
                           % last_err)


# ------------------------------------------------------------ narration
def _run(cmd, timeout=300):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise ClientOrderError("فشل أمر (%s): %s"
                               % (" ".join(cmd[:3]),
                                  (r.stderr or "").strip()[-300:]))
    return r


def _ffprobe_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise ClientOrderError("تعذر قراءة مدة الصوت: %s" % path)
    return float(r.stdout.strip())


def _wav_rate(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, timeout=30)
    return int(r.stdout.strip()) if r.returncode == 0 else 22050


def narrate_scenes(story, audio_dir):
    """سرد Piper لكل مشهد + تسريع atempo + دمج بصمت 0.3 ث.

    يرجع (مسار narration-full.wav، مدته، قائمة مقاطع المشاهد
    [(start, end)] بالثواني).
    """
    os.makedirs(audio_dir, exist_ok=True)
    if not os.path.isfile(PIPER_BIN):
        raise ClientOrderError("ثنائي Piper غير موجود: %s" % PIPER_BIN)
    if not os.path.isfile(PIPER_MODEL):
        raise ClientOrderError("موديل Piper غير موجود: %s" % PIPER_MODEL)
    fast_paths = []
    for i, scene in enumerate(story["scenes"], 1):
        raw = os.path.join(audio_dir, "scene%d.wav" % i)
        r = subprocess.run(
            [PIPER_BIN, "-m", PIPER_MODEL, "-f", raw],
            input=scene["text"], capture_output=True, text=True,
            timeout=300)
        if r.returncode != 0 or not os.path.isfile(raw):
            raise ClientOrderError("فشل سرد المشهد %d عبر Piper: %s"
                                   % (i, (r.stderr or "").strip()[-300:]))
        fast = os.path.join(audio_dir, "scene%d-fast.wav" % i)
        _run(["ffmpeg", "-y", "-v", "error", "-i", raw,
              "-filter:a", "atempo=%.2f" % ATEMPO, fast])
        fast_paths.append(fast)
        print("سُرد المشهد %d (%.1f ث بعد التسريع)"
              % (i, _ffprobe_duration(fast)))
    rate = _wav_rate(fast_paths[0])
    silence = os.path.join(audio_dir, "silence03.wav")
    _run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
          "-t", str(SILENCE_GAP), "-i",
          "anullsrc=r=%d:cl=mono" % rate, silence])
    list_path = os.path.join(audio_dir, "concat-list.txt")
    spans = []
    cursor = 0.0
    with open(list_path, "w", encoding="utf-8") as f:
        for j, p in enumerate(fast_paths):
            dur = _ffprobe_duration(p)
            spans.append((round(cursor, 3), round(cursor + dur, 3)))
            f.write("file '%s'\n" % p)
            cursor += dur
            if j < len(fast_paths) - 1:
                f.write("file '%s'\n" % silence)
                cursor += SILENCE_GAP
    full = os.path.join(audio_dir, "narration-full.wav")
    _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
          "-i", list_path, "-c", "copy", full])
    total = _ffprobe_duration(full)
    print("السرد الكامل: %.1f ثانية" % total)
    return full, total, spans


# -------------------------------------------------------------- captions
def build_captions(story, spans):
    """كلمات + توقيتات من نص السيناريو المعروف ومقاطع المشاهد.

    حدود العبارات دقيقة بالبناء (أول/آخر كلمة في المشهد)، وتوزيع
    الكلمات داخل المشهد بالتناسب مع طولها — فالنص المعروض مطابق
    تمامًا للنص المنطوق (قاعدة المشروع).
    """
    words = []
    transcript = []
    for scene, (start, end) in zip(story["scenes"], spans):
        text = scene["text"]
        parts = text.split()
        if not parts:
            continue
        total_chars = sum(len(w) for w in parts)
        span = max(end - start, 0.1)
        cursor = start
        for k, w in enumerate(parts):
            w_dur = span * max(len(w), 1) / max(total_chars, 1)
            w_start = cursor
            w_end = end if k == len(parts) - 1 else cursor + w_dur
            entry = {"word": w,
                     "startMs": int(round(w_start * 1000)),
                     "endMs": int(round(w_end * 1000))}
            if k == len(parts) - 1:
                entry["pageBreakAfter"] = True
            words.append(entry)
            transcript.append({"word": w, "start": round(w_start, 3),
                               "end": round(w_end, 3),
                               "start_ms": entry["startMs"],
                               "end_ms": entry["endMs"]})
            cursor = w_end
    return words, transcript


# ---------------------------------------------------------------- images
def _wikimedia_search(query, limit=6):
    params = {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": query, "gsrnamespace": "6", "gsrlimit": str(limit),
        "prop": "imageinfo", "iiprop": "url|size|mime",
        "iiurlwidth": "1280",
    }
    url = WIKIMEDIA_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    pages = (data.get("query") or {}).get("pages") or {}
    out = []
    for p in pages.values():
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime") != "image/jpeg":
            continue
        if (info.get("width") or 0) < 800:
            continue
        out.append({
            "url": info.get("thumburl") or info.get("url"),
            "original_url": info.get("descriptionurl") or info.get("url"),
            "width": info.get("width"),
        })
    return [o for o in out if o["url"]]


def _wikimedia_download(url, dest):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    if len(data) < 5000:
        raise ClientOrderError("صورة صغيرة جدًا من Wikimedia: %s" % url)
    with open(dest, "wb") as f:
        f.write(data)
    return dest


def fetch_scene_image(keywords, topic, dest, scene_no):
    """صورة من Wikimedia Commons بكلمات المشهد، مع بدائل متدرجة."""
    queries = []
    if keywords:
        queries.append(" ".join(keywords[:3]))
        queries.extend(keywords[:3])
    if topic:
        queries.append(topic)
    queries.append("Egypt")
    seen = set()
    for q in queries:
        if not q or q in seen:
            continue
        seen.add(q)
        try:
            results = _wikimedia_search(q)
        except Exception as e:
            print("تعذر بحث Wikimedia عن «%s»: %s" % (q, e))
            continue
        for res in results:
            try:
                _wikimedia_download(res["url"], dest)
                print("صورة المشهد %d من Wikimedia («%s»): %s"
                      % (scene_no, q, res["original_url"]))
                return res["original_url"]
            except Exception as e:
                print("فشل تنزيل صورة المشهد %d: %s" % (scene_no, e))
                continue
    raise ClientOrderError("تعذّر إيجاد صورة للمشهد %d (كلمات: %s)"
                           % (scene_no, ", ".join(keywords or [])))


# ------------------------------------------------------- project build
def build_project(order, story, narration_full, spans, images_dir):
    """يكتب مشروع OpenMontage كاملًا من السيناريو والأصول."""
    proj_name = "client-" + _safe_slug(order["id"])
    root = os.path.join(os.path.expanduser("~"), "workspace",
                        "openmontage", "projects", proj_name)
    artifacts = os.path.join(root, "artifacts")
    assets_img = os.path.join(root, "assets", "images")
    assets_aud = os.path.join(root, "assets", "audio")
    os.makedirs(artifacts, exist_ok=True)
    os.makedirs(assets_img, exist_ok=True)
    os.makedirs(assets_aud, exist_ok=True)

    sections = []
    for i, (scene, (start, end)) in enumerate(
            zip(story["scenes"], spans), 1):
        sections.append({
            "id": "s%d" % i,
            "label": "Hook" if i == 1 else "Scene %d" % i,
            "text": scene["text"],
            "start_seconds": round(start, 3),
            "end_seconds": round(end, 3),
        })
    script = {
        "metadata": {
            "dialect": "Egyptian Arabic (العامية المصرية)",
            "narrator": "male, Piper ar_JO-kareem-medium",
            "client_order": order["id"],
        },
        "sections": sections,
    }
    with open(os.path.join(artifacts, "script.json"), "w",
              encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    words, transcript = build_captions(story, spans)
    with open(os.path.join(artifacts, "captions.json"), "w",
              encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False)
    with open(os.path.join(artifacts, "narration_transcript.json"), "w",
              encoding="utf-8") as f:
        json.dump({"word_timestamps": transcript}, f, ensure_ascii=False,
                  indent=2)

    scenes_plan = []
    manifest_assets = []
    for i, (scene, (start, end)) in enumerate(
            zip(story["scenes"], spans), 1):
        img_name = "scene%d.jpg" % i
        img_src = os.path.join(images_dir, img_name)
        if not os.path.isfile(img_src):
            raise ClientOrderError("صورة المشهد %d غير موجودة: %s"
                                   % (i, img_src))
        import shutil
        shutil.copy2(img_src, os.path.join(assets_img, img_name))
        scenes_plan.append({
            "id": "scene-%02d" % i,
            "type": "broll",
            "description": scene["text"][:80],
            "start_seconds": round(start, 3),
            "end_seconds": round(end, 3),
            "script_section_id": "s%d" % i,
            "required_assets": ["img-scene%d" % i],
            "texture_keywords": scene.get("image_keywords") or [],
        })
        manifest_assets.append({
            "id": "img-scene%d" % i,
            "type": "image",
            "path": os.path.join(assets_img, img_name),
            "source_tool": "wikimedia_stock",
            "scene_id": "scene-%02d" % i,
            "license": "Wikimedia Commons — see original_url",
            "original_url": scene.get("image_url") or "",
        })
    with open(os.path.join(artifacts, "scene_plan.json"), "w",
              encoding="utf-8") as f:
        json.dump({"version": "1.0",
                   "style_playbook": "flat-motion-graphics",
                   "scenes": scenes_plan}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(artifacts, "asset_manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump({"version": "1.0", "assets": manifest_assets}, f,
                  ensure_ascii=False, indent=2)
    import shutil as _sh
    _sh.copy2(narration_full,
              os.path.join(assets_aud, "narration-full.wav"))
    with open(os.path.join(root, "project.json"), "w",
              encoding="utf-8") as f:
        json.dump({
            "version": "1.0",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "project_id": proj_name,
            "title": story["hook"],
            "pipeline_type": "animated-explainer",
            "client_order": order["id"],
        }, f, ensure_ascii=False, indent=2)
    print("بُني مشروع OpenMontage: %s (%d مشاهد)"
          % (proj_name, len(story["scenes"])))
    return proj_name


# ------------------------------------------------------------- run order
def cmd_client_run(cfg, order_id):
    """نفّذ طلب عميل واحد كاملًا: سيناريو → سرد → صور → فيديو."""
    order = get_order(order_id)
    if order is None:
        print("الطلب غير موجود: %s" % order_id)
        return 1
    if order.get("status") == "done":
        print("الطلب مكتمل بالفعل: %s → %s"
              % (order_id, order.get("video_path") or ""))
        return 0
    slug = "client-" + _safe_slug(order_id)
    try:
        studio.validate_run_component(slug, "اسم طلب العميل")
    except ValueError as e:
        print("رقم طلب غير صالح: %s" % e)
        return 2
    update_order(order_id, status="processing")
    order_dir = os.path.join(OUT_ROOT, _safe_slug(order_id))
    os.makedirs(order_dir, exist_ok=True)
    try:
        target = DURATION_TARGETS.get(order.get("duration") or "40-60", 50)
        story = expand_story(cfg, order["description"], target)
        audio_dir = os.path.join(order_dir, "audio")
        narration_full, total, spans = narrate_scenes(story, audio_dir)
        print("مدة السرد %.1f ثانية (المستهدف %d)" % (total, target))
        images_dir = os.path.join(order_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        topic = " ".join((order["description"] or "").split()[:4])
        for i, scene in enumerate(story["scenes"], 1):
            dest = os.path.join(images_dir, "scene%d.jpg" % i)
            url = fetch_scene_image(scene.get("image_keywords") or [],
                                    topic, dest, i)
            scene["image_url"] = url
        proj_name = build_project(order, story, narration_full, spans,
                                  images_dir)
        # مقاس الطلب لهذا التشغيل فقط (مثل --size في run)
        width, height = _normalize_size(order.get("size"))
        cfg["video"]["width"] = width
        cfg["video"]["height"] = height
        runs_dir = studio.expand(cfg["paths"]["runs_dir"])
        run_id, run_dir = studio.new_run(runs_dir, slug)
        print("تشغيل: %s" % run_id)
        manifest = studio.cmd_produce(cfg, proj_name, run_dir)
        print("جُهزت %d صورة، سرد %.1f ثانية، %d عبارة كتابة"
              % (len(manifest["images"]), manifest["narration_duration"],
                 len(manifest["phrases"])))
        out_video = os.path.join(order_dir, "video.mp4")
        logo = order.get("logo") or "page"
        watermark_on = (logo == "page")
        out, _secs = studio.cmd_assemble(cfg, run_dir, story["hook"],
                                         out_video, watermark_on)
        if logo in ("client", "custom"):
            logo_path = order.get("logo_path")
            if logo_path and os.path.isfile(logo_path):
                studio.watermark.apply_watermark(out, out, badge=logo_path)
                print("أُضيف شعار العميل أعلى اليمين")
            else:
                print("تحذير: شعار العميل غير متوفر — الفيديو بلا شعار")
        thumb_path = os.path.join(order_dir, "thumbnail.jpg")
        studio.cmd_thumbnail(cfg, out, story["hook"], thumb_path)
        duration = studio.watermark.probe_duration(out)
        update_order(order_id, status="done", video_path=out,
                     thumbnail_path=thumb_path,
                     duration_seconds=round(duration, 2),
                     hook=story["hook"], moral=story["moral"])
        print("اكتمل طلب العميل %s: %s (%.1f ثانية)"
              % (order_id, out, duration))
        return 0
    except Exception as e:
        update_order(order_id, status="failed",
                     error=str(e)[:500])
        print("فشل طلب العميل %s: %s" % (order_id, e))
        return 1


def cmd_process_queue(cfg):
    """نفّذ كل الطلبات الجديدة في الطابور بالتتابع."""
    orders = load_orders()
    new = [o for o in orders if o.get("status") == "new"]
    if not new:
        print("لا توجد طلبات جديدة")
        return 0
    print("طلبات جديدة: %d" % len(new))
    failed = 0
    for o in new:
        rc = cmd_client_run(cfg, o["id"])
        if rc != 0:
            failed += 1
    print("اكتملت الدفعة: %d نجحت، %d فشلت"
          % (len(new) - failed, failed))
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(prog="client_orders",
                                 description="تنفيذ طلبات فيديو العملاء")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("client-run", help="تنفيذ طلب عميل واحد")
    p.add_argument("--order", required=True, help="رقم الطلب")
    sub.add_parser("process-queue", help="تنفيذ كل الطلبات الجديدة")
    args = ap.parse_args()
    cfg = studio.load_config()
    studio._ensure_environment()
    if args.cmd == "client-run":
        return cmd_client_run(cfg, args.order)
    if args.cmd == "process-queue":
        return cmd_process_queue(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
