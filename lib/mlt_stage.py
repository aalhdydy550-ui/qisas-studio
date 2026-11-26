#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""خلفية تجميع بديلة عبر MLT/melt — تايم لاين XML حقيقي.

يبني ملف `.mlt` من بيان studio (نفس مدخلات headless_stage):
صور التسلسل مقاطع 5 ثوانٍ، السرد مسارًا صوتيًا، الهوك نصًا أسفل
الشاشة فوق العبارات أول 4 ثوانٍ، والعبارات نصوصًا أسفل الشاشة — ثم يريندر
عبر `melt` (إطار الوسائط الذي تقوم عليه Kdenlive وShotcut).

النصوص عبر مرشح `dynamictext` (pango — يشكّل العربية).
الصور عبر منتج `qimage` مع `ttl` بالإطارات. الصوت عبر منتج
`avformat` على مسار ثانٍ مع انتقال `mix`.

نفس ملف `.mlt` يُفتح في Kdenlive/Shotcut على جهاز حقيقي
للتعديل اليدوي لاحقًا — ميزة لا توفرها خلفية headless.
Concat يبقى الافتراضي؛ هذه الخلفية اختيارية عبر
`assemble --backend mlt` أو `run --backend mlt`.
"""
import os
import signal
import subprocess
import time
import xml.etree.ElementTree as ET
from math import gcd


class MltError(Exception):
    """خطأ في بناء مشروع MLT أو الريندر (رسالته عربية)."""


HOOK_DURATION_SECONDS = 4.0
HOOK_FONTSIZE = 58
CAPTION_FONTSIZE = 44
# قاعدة دائمة 2026-11-22: كل نصوص الشاشة أسفل فقط، ولا نص أعلى
# أبدًا. صندوق الهوك يجلس فوق صندوق العبارات مباشرة (عبارات:
# y=height-230 وارتفاع 170): y=height-420 وارتفاع 150 يترك فجوة
# ~40px بين سطر الهوك الأخير وأول سطر عبارة (هوك سطران ~144px).
# (أُلغي LOGO_RESERVE_PX مع نقل الهوك للأسفل — كان يحجز منطقة
# الشارة أعلى اليمين للهوك حين كان أعلى الشاشة.)
# qimage (Qt) للصور وdynamictext (Qt) للنصوص — كلاهما يحتاج
# جلسة X11، فيُشغَّل melt تحت `xvfb-run -a` (Xvfb مثبّت على
# الـVM). البديل pixbuf لا ينفع هنا: حزمة gdk-pixbuf في هذه
# الصورة بلا loader لـJPEG/PNG أصلًا (اتحقق 2026-11-21).
IMAGE_SERVICE = "qimage"

# هندسة التوسيط (جولة v0.1.62 — عيبا MLT من إنتاج v2 الحي):
# مرشح dynamictext في MLT 7.22 يتجاهل halign تمامًا (اتحقق
# بالريندر: halign ‏0/1/2 تعطي الإخراج نفسه بايتيًا — نص
# ملتصق بالحافة اليسرى x≈26 — عربيًا وإنجليزيًا)، ويتجاهل
# valign كذلك (صندوقا ارتفاع 150 و170 يعطيان إخراجًا متماثلًا
# بايتيًا؛ والنص مثبَّت أعلى الصندوق بإزاحة ثابتة). والتوسيط
# الوحيد الذي يعمل هو التوسيط بالهندسة: قياس عرض النص المرئي
# بـPIL بالخط نفسه الذي يستخدمه المرشح ثم وضع الصندوق
# متمركزًا حوله. وصندوق ارتفاعه = حجم الخط يقصّ النص
# (58 يقصّ سطر «مليون مرة» إلى شريط علوي فقط n=130 بكسلًا
# ساطعًا مقابل n=1005 كاملة) — الارتفاع 150 (كمرشح الهوك
# الافتراضي في الملف نفسه) يمنع القصّ، و170 لا يضيف شيئًا
# (إخراج متماثل بايتيًا مع 150) فلا يُستخدم.
# قياس PIL يبالغ قليلًا في العرض دائمًا (~2–6%: «مليون مرة»
# ‏214 بـPIL مقابل 201 مرسومة) فهو هامش أمان مدمج: ما قال
# PIL إنه يتسع على سطر واحد يتسع فعلًا عند pango.
TEXT_FONT_FILE = ("/usr/share/fonts/truetype/noto/"
                  "NotoNaskhArabic-Bold.ttf")
TEXT_PAD = 20
HOOK_TITLE_BOX_HEIGHT = 150


def _measure_text_width(text, fontsize,
                        font_file=TEXT_FONT_FILE):
    """عرض النص المرئي بالبكسل بخط المرشح نفسه (Noto Naskh
    Arabic ‏Bold — نفس family/weight في _text_filter)، أو
    None عند تعذّر القياس (ملف خط مفقود / خطأ PIL) — فيرجع
    المتصل للهندسة القديمة (fail-open، لا يكسر الإنتاج أبدًا)."""
    try:
        from PIL import ImageFont
        font = ImageFont.truetype(font_file, int(fontsize))
        return float(font.getlength(text or ""))
    except Exception:
        return None


def _centered_geometry(text, fontsize, width, pad=TEXT_PAD):
    """هندسة (x, box_width) متمركزة أفقيًا للنص: الصندوق بعرض
    النص + حاشيتين (pad كما في _text_filter)، متمركز في
    الإطار. إن ضاق النص عن العرض (أو تعذّر قياسه) ترجع
    الهندسة القديمة (0, width) — العبارات الأوسع من العرض
    الآمن حتى وهي متمركزة مشكلة طول محتوى لا عيب هندسة."""
    text_w = _measure_text_width(text, fontsize)
    if text_w is None:
        return 0, int(width)
    box_w = int(round(text_w)) + 2 * pad
    if box_w > int(width):
        return 0, int(width)
    return (int(width) - box_w) // 2, box_w


def format_timecode(seconds):
    """ثوانٍ عشرية → زمن MLT مثل 00:00:04.500."""
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    m = (total_s // 60) % 60
    h = total_s // 3600
    return "%02d:%02d:%02d.%03d" % (h, m, s, ms)


def _prop(parent, name, value):
    el = ET.SubElement(parent, "property", {"name": name})
    el.text = str(value)
    return el


def _image_producer(root, pid, path, ttl_frames, start_tc, end_tc):
    prod = ET.SubElement(root, "producer",
                         {"id": pid, "in": start_tc, "out": end_tc})
    _prop(prod, "resource", path)
    _prop(prod, "mlt_service", IMAGE_SERVICE)
    _prop(prod, "ttl", ttl_frames)
    return prod


def _text_filter(parent, fid, text, start_tc, end_tc, fontsize, y,
                 height, width, x=0):
    filt = ET.SubElement(parent, "filter", {"id": fid})
    _prop(filt, "argument", text)
    # geometry بأربع قيم فقط (x y w h) — قيمة خامسة للشفافية
    # ("100%") تُعطّل المرشح كاملًا في MLT 7.22 فلا يظهر نص.
    # اتحقق 2026-11-21.
    _prop(filt, "geometry", "%d %d %d %d" % (x, y, width, height))
    _prop(filt, "family", "Noto Naskh Arabic")
    _prop(filt, "size", fontsize)
    _prop(filt, "weight", 700)
    _prop(filt, "fgcolour", "#ffffffff")
    _prop(filt, "bgcolour", "#00000000")
    _prop(filt, "olcolour", "#ff000000")
    _prop(filt, "outline", 2)
    _prop(filt, "pad", 20)
    _prop(filt, "halign", 1)
    _prop(filt, "valign", 1)
    _prop(filt, "mlt_service", "dynamictext")
    _prop(filt, "in", start_tc)
    _prop(filt, "out", end_tc)
    return filt


def prepare_fill_images(manifest, assets_dir, out_dir, width, height):
    """قص صور التسلسل لتملأ الإطار (scale-to-cover + قص الوسط).

    منتج qimage يلائم الصورة داخل الإطار بلا قص فيترك أشرطة سوداء
    (letterbox) — ومرشح affine (بصيغه الثلاث: geometry مباشرة،
    وtransition.*، وانتقال affine فوق مسار خلفية) لا يغيّر ذلك في
    MLT 7.22 لأن الصورة تُلائم قبل أن يراها المرشح/الانتقال
    (اتحقق عمليًا 2026-11-21 على ثلاث صيغ — بلا أي أثر). الحل:
    قص نسخ بمقاس الإطار مسبقًا بـffmpeg والإشارة إليها في ملف
    .mlt. النسخ في out_dir (بجانب ملف .mlt) فيبقى المشروع قابلًا
    للفتح في Kdenlive. يرجع قاموس {اسم الصورة: مسار النسخة}.
    """
    import shutil
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise MltError("أمر ffmpeg غير موجود — لا يمكن قص صور MLT")
    seq = list(manifest.get("sequence") or [])
    if not seq:
        raise MltError("لا صور في البيان — لا شيء يُقصّ لـMLT")
    os.makedirs(out_dir, exist_ok=True)
    out_paths = {}
    from lib.paths import resolve_inside, safe_component
    images_dir = os.path.join(assets_dir, "images")
    for name in seq:
        # إصلاح اختبار اختراق 2026-11-21: اسم من البيان بلا تحقق
        # كان يكتب خارج مجلد القصّ (../../escape-target.jpg).
        try:
            safe_component(name, "اسم الصورة")
            src = resolve_inside(images_dir,
                                 os.path.join(images_dir, name),
                                 "صورة MLT")
            dst = resolve_inside(out_dir, os.path.join(out_dir, name),
                                 "نسخة صورة MLT")
        except ValueError as e:
            raise MltError(str(e))
        if not os.path.isfile(src):
            raise MltError("صورة MLT غير موجودة: %s" % src)
        vf = ("scale=%d:%d:force_original_aspect_ratio=increase,"
              "crop=%d:%d" % (width, height, width, height))
        cmd = [ffmpeg, "-y", "-v", "error", "-i", src,
               "-vf", vf]
        if name.lower().endswith((".jpg", ".jpeg")):
            cmd += ["-q:v", "2"]
        cmd += [dst]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=120)
        except subprocess.TimeoutExpired:
            raise MltError("انتهت مهلة قص الصورة: %s" % name)
        if r.returncode != 0 or not os.path.isfile(dst):
            raise MltError("تعذر قص الصورة %s: %s"
                           % (name, (r.stderr or "").strip()[:300]))
        out_paths[name] = dst
    return out_paths


def build_mlt(manifest, title, assets_dir, video_cfg, images_dir=None,
              as_hook_title=False):
    """ابنِ نص XML لمشروع MLT من بيان studio (دالة نقية).

    images_dir (اختياري): مجلد فيه نسخ الصور بمقاس الإطار
    (من prepare_fill_images) — تُستخدم مساراته بدل
    assets_dir/images، فيملأ الإطار بلا أشرطة سوداء.
    as_hook_title: عند التفعيل يُحرق العنوان مرة واحدة بهندسة
    `hook_title_spec` (النطاق الأوسط، 0–3ث، مرشح dynamictext
    لكل سطر) بدل عنوان الأسفل 4ث — حرق واحد بلا تضاعف؛
    والافتراضي (False) بلا أي تغيير (عنوان أسفل واحد 0–4ث).
    """
    clip_seconds = float(manifest.get(
        "image_clip_seconds",
        video_cfg.get("image_clip_seconds", 5)))
    width = int(video_cfg["width"])
    height = int(video_cfg["height"])
    fps = int(video_cfg["fps"])
    duration = float(manifest.get("narration_duration") or 0.0)
    seq = list(manifest["sequence"])
    total = clip_seconds * len(seq)
    if duration > 0 and total < duration:
        total = duration
    if total <= 0:
        raise MltError("لا مدة لمشروع MLT — البيان بلا تسلسل ولا سرد")

    root = ET.Element("mlt", {"LC_NUMERIC": "C", "version": "7.0",
                              "title": manifest.get("project", "studio"),
                              "producer": "main_bin"})
    # نسبة العرض تُحسب من الأبعاد نفسها (كانت 9/16 مثبتة — خطأ
    # للأفقي 1280×720 الذي يحتاج 16/9). إصلاح 2026-11-21.
    _g = gcd(width, height)
    profile = ET.SubElement(root, "profile", {
        "width": str(width), "height": str(height),
        "display_aspect_num": str(width // _g),
        "display_aspect_den": str(height // _g),
        "sample_aspect_num": "1", "sample_aspect_den": "1",
        "frame_rate_num": str(fps), "frame_rate_den": "1",
        "colorspace": "709"})
    # ترتيب العناصر إلزامي: محلل XML في melt يحل المراجع بترتيب
    # المستند — مرجع أمامي (قائمة قبل منتجها) يُسقَط بصمت فيترك
    # التايم لاين فارغًا (ريندر 0.04ث). لذا: المنتجات أولًا، ثم
    # القوائم، ثم التراكتور، ثم main_bin أخيرًا. اتحقق 2026-11-21.
    clip_durs = []
    for i, name in enumerate(seq):
        start = i * clip_seconds
        dur = clip_seconds
        if i == len(seq) - 1 and duration > 0 and start + dur < duration:
            dur = duration - start
        clip_durs.append(dur)
        clip_end_tc = format_timecode(dur - 1.0 / fps)
        img_path = (os.path.join(images_dir, name) if images_dir
                    else os.path.join(assets_dir, "images", name))
        _image_producer(
            root, "img%d" % i, img_path,
            int(round(dur * fps)),
            format_timecode(0), clip_end_tc)
    # السرد
    if duration > 0:
        narration = os.path.join(assets_dir, "audio", "narration-full.wav")
        prod = ET.SubElement(root, "producer",
                             {"id": "narration",
                              "in": format_timecode(0),
                              "out": format_timecode(duration - 1.0 / fps)})
        _prop(prod, "resource", narration)
        _prop(prod, "mlt_service", "avformat")
    # قائمة الصور — ملحوظة: in/out كل إدخال على زمن المنتج نفسه
    # (0 ← مدة المقطع)، لا زمنًا تراكميًا على التايم لاين.
    playlist = ET.SubElement(root, "playlist", {"id": "playlist0"})
    for i, name in enumerate(seq):
        clip_end_tc = format_timecode(clip_durs[i] - 1.0 / fps)
        ET.SubElement(playlist, "entry", {
            "producer": "img%d" % i,
            "in": format_timecode(0),
            "out": clip_end_tc})
    # التايم لاين
    tractor = ET.SubElement(root, "tractor",
                            {"id": "timeline",
                             "title": manifest.get("project", "studio")})
    ET.SubElement(tractor, "track", {"producer": "playlist0"})
    if duration > 0:
        ET.SubElement(tractor, "track",
                      {"producer": "narration", "hide": "video"})
        trans = ET.SubElement(tractor, "transition",
                              {"id": "transition0"})
        _prop(trans, "a_track", 0)
        _prop(trans, "b_track", 1)
        _prop(trans, "mlt_service", "mix")
        _prop(trans, "always_active", 1)
        _prop(trans, "sum", 1)
    # النصوص (هوك + عبارات) — الهوك أسفل الشاشة فوق العبارات
    # مباشرة (قاعدة دائمة 2026-11-22: لا نص أعلى الشاشة أبدًا):
    # صندوقه بعرض الإطار كاملًا (أقل سطورًا) وحافته السفلى فوق
    # صندوق العبارات بفجوة ~40px.
    if title:
        if as_hook_title:
            # حرق واحد بهندسة عنوان الهوك (إصلاح التضاعف —
            # 2026-11-26): سطر لكل سطر من المواصفة، في النطاق
            # الأوسط، 0–3ث — بلا عنوان أسفل إضافي.
            from lib import hook_title as hook_title_lib
            try:
                spec = hook_title_lib.hook_title_spec(
                    title, width, height)
            except hook_title_lib.HookTitleError as e:
                raise MltError(str(e))
            for i, (line, y) in enumerate(zip(spec["lines"],
                                              spec["line_y"])):
                # عيب (أ) 2026-11-26: ارتفاع الصندوق = حجم الخط
                # (58) يقصّ النص؛ وhalign يُتجاهل في MLT 7.22
                # فيلتصق السطر باليسار — فالارتفاع 150 والتوسيط
                # بالهندسة معًا (انظر _centered_geometry).
                hx, hw = _centered_geometry(line, spec["fontsize"],
                                            width)
                _text_filter(
                    tractor, "filter-hook%d" % i, line,
                    format_timecode(spec["start"]),
                    format_timecode(spec["end"] - 1.0 / fps),
                    spec["fontsize"], y, HOOK_TITLE_BOX_HEIGHT, hw, hx)
        else:
            # الهوك الافتراضي: مرشح واحد بالعنوان كاملًا — هو
            # أيضًا ملتصق باليسار (هامشا عنوان «قصتك ممكن
            # تتشاف مليون مرة» 26 يسارًا مقابل 63 يمينًا في
            # ريندر داكن) فيُمركز بالهندسة حين يتسع على سطر
            # واحد، ويرجع للهندسة القديمة حين يلتف (طول محتوى).
            hx, hw = _centered_geometry(title, HOOK_FONTSIZE, width)
            _text_filter(tractor, "filter-hook", title,
                         format_timecode(0),
                         format_timecode(HOOK_DURATION_SECONDS - 1.0 / fps),
                         HOOK_FONTSIZE, height - 420, 150, hw, hx)
    for i, p in enumerate(manifest.get("phrases", [])):
        # عيب (ب) 2026-11-26: العبارات تتجاهل halign فتلتصق
        # باليسار (x≈22 < هامش 36) — توسيط بالهندسة، والرجوع
        # للهندسة القديمة حين يتعذّر القياس أو يضيق النص.
        px, pw = _centered_geometry(p["text"], CAPTION_FONTSIZE,
                                     width)
        _text_filter(tractor, "filter-phrase%d" % i, p["text"],
                     format_timecode(float(p["start"])),
                     format_timecode(float(p["end"]) - 1.0 / fps),
                     CAPTION_FONTSIZE, height - 230, 170, pw, px)
    # قائمة main_bin أخيرًا: نقطة دخول melt إلى التراكتور.
    main_bin = ET.SubElement(root, "playlist", {"id": "main_bin"})
    ET.SubElement(main_bin, "entry", {
        "producer": "timeline",
        "in": format_timecode(0),
        "out": format_timecode(total - 1.0 / fps)})
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def find_melt():
    """ابحث عن ثنائي melt على PATH."""
    import shutil
    path = shutil.which("melt")
    if path:
        return path
    raise MltError(
        "ثنائي melt غير موجود — ثبّته عبر apt:\n"
        "  sudo apt-get install -y melt")


def render_mlt(mlt_path, out_path, timeout=900):
    """ريندر ملف .mlt عبر melt إلى mp4. يرجع قاموس النتيجة.

    يُشغَّل melt تحت `xvfb-run -a` لأن منتجات Qt (qimage
    للصور وdynamictext للنصوص) ترفض العمل بلا جلسة X11
    («The MLT Qt module requires a X11 environment») وتترك
    الإطارات شفافة.
    """
    if not os.path.isfile(mlt_path):
        raise MltError("ملف مشروع MLT غير موجود: %s" % mlt_path)
    melt = find_melt()
    import shutil
    xvfb = shutil.which("xvfb-run")
    cmd = []
    if xvfb:
        cmd += [xvfb, "-a"]
    cmd += [melt, mlt_path, "-consumer",
            "avformat:%s" % out_path,
            "vcodec=libx264", "preset=veryfast", "crf=20",
            "acodec=aac"]
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    # Popen في جلسة عمليات خاصة: عند انتهاء المهلة يجب قتل
    # مجموعة العمليات كلها — subprocess.run يقتل xvfb-run فقط
    # ويترك melt يتيمًا يريندر للأبد (شوهد حيًا 2026-11-22
    # بعد مهلة 900ث، بلا ملف خرج، ويستهلك 120% CPU).
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                start_new_session=True)
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        raise MltError("انتهت مهلة ريندر melt (%d ثانية) — أعد المحاولة "
                       "والجهاز فاضٍ" % timeout)
    except OSError as e:
        raise MltError("تعذر تشغيل melt: %s" % e)
    if proc.returncode != 0:
        tail = ((stderr or "") + (stdout or ""))[-1200:]
        raise MltError("فشل ريندر melt (رمز الخروج %d):\n%s"
                       % (proc.returncode, tail))
    if not os.path.isfile(out_path):
        raise MltError("انتهى ريندر melt دون إنشاء ملف الخرج: %s"
                       % out_path)
    return {"output": out_path,
            "seconds": round(time.time() - t0, 1),
            "size_bytes": os.path.getsize(out_path)}
