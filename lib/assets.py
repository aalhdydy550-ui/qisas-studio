#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""توصيل أصول صوتية/بصرية إلى فيديوهات الاستوديو.

الأصول (مؤثرات SFX وتراكبات فيلم) تعيش خارج شجرة
الاستوديو في مجلد أصول — افتراضيًا
``~/workspace/studio-work/drive-assets/adapted/`` — ولا يُنسخ أي
ملف صوتي إلى المستودع إطلاقًا. مصدر الأصول وتراخيصها
موثقة في ``ADAPTED-AR.md`` داخل مجلد الأصول نفسه: المؤثرات
من Mixkit (Mixkit Free License — استخدام تجاري بلا
إسناد، ومنع إعادة التوزيع كما هي أو التسجيل في Content ID)،
وصوت الصرّاف من Freesound برخصة CC0 (ملك عام)، والتراكبان
مولّدان محليًا بـffmpeg من الصفر.

السلوك العام (fail-open):
  * مجلد أصول غائب أو ملف أصل غائب → تحذير مطبوع ويُرجع الفيديو
    نفسه بلا أي إعادة ترميز (لا فشل)، فخط النشر لا يتوقف على أصل.
  * فيديو مدخل غير موجود → ``AssetsError`` (خطأ حقيقي).
  * كل عملية ناجحة: ملف مؤقت + ``os.replace``، ومهلة تشغيل
    900 ثانية — نفس نمط ``lib/fix_audio.py``.

المزج الصوتي على نمط ``lib/fix_audio.py`` حرفيًا: المؤثرات
تُؤخَّر بـ``adelay`` إلى مواضعها ثم تُخلط بـ``amix`` مع صوت
الفيديو (``normalize=0`` حتى لا ينخفض مستوى السرد الأصلي) ثم
``alimiter=limit=0.95`` لمنع القصّ، ثم ``atrim`` على مدة
الفيديو و``asetpts=PTS-STARTPTS``؛ والفيديو يُنسخ بلا إعادة
ترميز (``-c:v copy``) والصوت ``aac 192k``.

قاعدة المنتج: نص الشاشة أسفل الصورة فقط ولا يُغطَّى أبدًا —
التراكب يطال المنطقة فوق شريط الكابشن فقط، وأسفل الشريط
يُركَّب كما هو بلا أي فلتر (انظر ``CAPTION_BAND_PX``)؛
ومخرجات التراكب تُرمَّز ``libx264 crf 20`` كما في
``lib/watermark.py`` — فالفيديو الداخل للخطوة فقدي أصلًا
(تصدير Concat ثم شعار crf 20)، وبلا فقدان (``crf 0``)
يضخّم الملف ~5× بلا جودة إضافية (شورت 60ث بالحبيبات
≈ 460 ميجا). التحقق من الشريط بتفاوت لا مساواة حرفية
(متوسط الفرق < 2 لكل قناة + بقاء الشريط أبيض) — وهو
الفحص الصحيح لخط فقدي.
"""
import json
import os
import subprocess

from lib import paths as paths_lib

ASSETS_DIR_ENV = "QISAS_ASSETS_DIR"
DEFAULT_ASSETS_DIR = "~/workspace/studio-work/drive-assets/adapted/"

BURN_OPACITY = 0.85
GRAIN_OPACITY = 0.12

# اشتقاق شريط الكابشن المحمي (من lib/whisper_captions.py:44-63):
# PlayResX 720 / PlayResY 1280، محاذاة 2 (أسفل الوسط)،
# MarginV=60، خط 52. أسفل ~200 بكسل = 60 هامش سفلي +
# سطران × 52 (سطران كحد أقصى للعبارة) + ظل/حدود ≈ 194 → 200
# بهامش أمان صغير. أي تراكب يجب ألا يمس هذه المنطقة أبدًا.
CAPTION_BAND_PX = 200

SFX = {"whoosh": "sfx/whoosh-air-woosh.mp3",
       "whoosh-long": "sfx/whoosh-cinematic-transition.mp3",
       "impact": "sfx/impact-big-cinematic.mp3",
       "pop": "sfx/pop-message-alert.mp3",
       "page": "sfx/paper-page-turn.mp3",
       "shutter": "sfx/shutter-camera-click.mp3",
       "coins": "sfx/money-clinking-coins.mp3",
       "cash-register": "sfx/cash-register.mp3",
       "cash-register-short": "sfx/cash-register-short.mp3"}
OVERLAYS = {"burn": "overlays/overlay-film-burn-720x1280.mp4",
            "grain": "overlays/overlay-film-grain-720x1280.mp4"}

# kind → قاموس مفاتيحه. التراكب فيديو لا صوت لكنه أصل بنفس
# آلية الحل، فيُعامل kind ثانيًا هنا.
_CATALOGS = {"sfx": SFX, "overlay": OVERLAYS}
# التراكب → وضع مزج ffmpeg (screen للحرق، overlay للحبيبات).
_OVERLAY_MODES = {"burn": "screen", "grain": "overlay"}

# مهلة تشغيل ffmpeg — نفس نمط lib/fix_audio.py.
_RUN_TIMEOUT = 900


class AssetsError(Exception):
    """خطأ في توصيل الأصول (رسالته عربية جاهزة للعرض)."""


def _warn(msg):
    """تحذير عربي إلى stdout — الغياب fail-open لا فشل."""
    print("تحذير: %s" % msg)


def _run(cmd, timeout=_RUN_TIMEOUT):
    """شغّل أمرًا — نفس نمط lib/fix_audio.py (مهلة 900 ثانية)."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except FileNotFoundError:
        raise AssetsError("الأمر غير موجود: %s" % cmd[0])
    except subprocess.TimeoutExpired:
        raise AssetsError("انتهت المهلة أثناء: %s" % " ".join(cmd[:3]))
    return proc


def _probe(video):
    """اقرأ مدة الفيديو وأبعاده ووجود صوت عبر ffprobe.

    يرجع {"duration", "width", "height", "fps", "has_audio"}.
    يرفع AssetsError عند ملف تالف أو تعذر القراءة.
    """
    cmd = ["ffprobe", "-v", "error", "-show_format", "-show_streams",
           "-of", "json", video]
    proc = _run(cmd)
    if proc.returncode != 0:
        raise AssetsError("تعذر قراءة الفيديو عبر ffprobe: %s"
                          % (proc.stderr or "").strip()[-200:])
    try:
        data = json.loads(proc.stdout)
    except ValueError:
        raise AssetsError("تعذر تحليل ناتج ffprobe للفيديو: %s"
                          % video)
    try:
        duration = float(data["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        raise AssetsError("تعذر قراءة مدة الفيديو: %s" % video)
    width = height = 0
    fps = 30.0
    has_audio = False
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and not width:
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
            rate = str(stream.get("avg_frame_rate") or "30/1")
            try:
                num, den = (int(x) for x in rate.split("/", 1))
                if den:
                    fps = num / den
            except ValueError:
                fps = 30.0
        elif stream.get("codec_type") == "audio":
            has_audio = True
    if not width or not height:
        raise AssetsError("الفيديو بلا مسار فيديو صالح: %s" % video)
    return {"duration": duration, "width": width, "height": height,
            "fps": fps, "has_audio": has_audio}


def _check_video(video):
    """تحقق من وجود الفيديو واقرأ خصائصه. يرجع (مسار، خصائص)."""
    path = paths_lib.realpath(video)
    if not os.path.isfile(path):
        raise AssetsError("ملف الفيديو غير موجود: %s" % path)
    return path, _probe(path)


def _prepare_out(video, out):
    """جهّز مسار الإخراج: مطلق، مختلف عن المدخل، ومجلده موجود."""
    out_path = paths_lib.realpath(out)
    if out_path == video:
        raise AssetsError(
            "مسار الإخراج هو نفسه ملف الفيديو — حدد --out مختلفًا")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    return out_path


def _finish(cmd, tmp_out, out_path, action):
    """نفّذ أمر ffmpeg ثم انقل المؤقت إلى الإخراج ذريًا."""
    proc = _run(cmd)
    if proc.returncode != 0 or not os.path.isfile(tmp_out):
        if os.path.isfile(tmp_out):
            os.remove(tmp_out)
        raise AssetsError("فشل %s عبر ffmpeg: %s"
                          % (action,
                             (proc.stderr or "").strip()[-300:]))
    os.replace(tmp_out, out_path)
    return out_path


# ------------------------------------------------------------------
# حل مجلد الأصول وملفاتها
# ------------------------------------------------------------------

def resolve_assets_dir(explicit=None) -> str | None:
    """مجلد الأصول: صريح > بيئة QISAS_ASSETS_DIR > الافتراضي.

    يرجع المسار الحقيقي لأول مرشح موجود كمجلد، أو None عند
    غياب المجلد (fail-open — المتصل يطبع تحذيرًا ويتخطى).
    مسار صريح/بيئة غائب لا يسقط إلى الافتراضي: من حدّد مجلدًا
    لا يُستبدل به مجلد آخر بصمت.
    """
    if explicit:
        candidate = paths_lib.realpath(explicit)
    else:
        env = os.environ.get(ASSETS_DIR_ENV, "").strip()
        if env:
            candidate = paths_lib.realpath(env)
        else:
            candidate = paths_lib.realpath(DEFAULT_ASSETS_DIR)
    if os.path.isdir(candidate):
        return candidate
    return None


def asset_path(kind, name, assets_dir=None) -> str | None:
    """مسار أصل من الكتالوج، أو None عند غياب المجلد/الملف.

    kind في {"sfx", "overlay"}؛ وname مفتاح من قاموس
    ذلك النوع. يرفع AssetsError عند kind/name غير صالح.
    الغياب (مجلد أو ملف) يُطبع تحذيرًا ويرجع None — لا استثناء.
    """
    if kind not in _CATALOGS:
        raise AssetsError("نوع الأصل غير صالح: %s (المقبول: %s)"
                          % (kind, "/".join(sorted(_CATALOGS))))
    catalog = _CATALOGS[kind]
    if name not in catalog:
        raise AssetsError("اسم الأصل غير صالح لنوع %s: %s "
                          "(المقبول: %s)"
                          % (kind, name, "/".join(sorted(catalog))))
    directory = resolve_assets_dir(assets_dir)
    if directory is None:
        _warn("مجلد الأصول غير موجود — تُخطّى %s (%s)"
              % (kind, name))
        return None
    path = os.path.join(directory, catalog[name])
    if not os.path.isfile(path):
        _warn("ملف الأصل غير موجود — يُتخطى: %s" % path)
        return None
    return path


def _resolve_sfx(name, assets_dir):
    """مفتاح من SFX أو مسار ملف مؤثر → مسار أو None.

    مفتاح/مسار غائب: تحذير وNone (fail-open) — فمؤثر واحد
    غائب لا يُسقط باقي المؤثرات ولا الفيديو كله.
    """
    if name in SFX:
        return asset_path("sfx", name, assets_dir)
    path = paths_lib.realpath(name)
    if os.path.isfile(path):
        return path
    _warn("ملف المؤثر غير موجود — يُتخطى: %s" % name)
    return None


# ------------------------------------------------------------------
# المؤثرات الصوتية
# ------------------------------------------------------------------

def add_sfx(video, events, out, assets_dir=None) -> str:
    """امزج مؤثرات صوتية في مواضع زمنية. يرجع مسار الإخراج.

    events: قائمة (name, at_seconds)؛ وname مفتاح من SFX أو
    مسار ملف. كل مؤثر يُؤخَّر بـadelay إلى موضعه ويُخلط بـamix
    (normalize=0) مع صوت الفيديو ثم alimiter عند 0.95.
    الفيديو يُنسخ بلا إعادة ترميز والصوت aac 192k.
    مؤثر غائب يُتخطى بتحذير؛ والكل غائب (أو لا أحداث) →
    الفيديو نفسه بلا إعادة ترميز.
    """
    video, info = _check_video(video)
    out_path = _prepare_out(video, out)
    duration = info["duration"]
    ready = []      # (name, path, at_seconds)
    skipped = []
    for name, at in (events or []):
        path = _resolve_sfx(name, assets_dir)
        if path is None:
            skipped.append(str(name))
            continue
        at = max(0.0, float(at))
        if at >= duration:
            _warn("موضع المؤثر %s (‏%.2f ث) بعد نهاية الفيديو "
                  "(‏%.2f ث) — يُتخطى" % (name, at, duration))
            skipped.append(str(name))
            continue
        ready.append((str(name), path, at))
    if not ready:
        print("تُخطّيت كل المؤثرات — الفيديو كما هو: %s" % video)
        return video

    filters = []
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", video]
    for i, (_name, path, at) in enumerate(ready):
        cmd += ["-i", path]
        delay_ms = int(round(at * 1000))
        filters.append("[%d:a]adelay=%d:all=1,apad[s%d]"
                       % (i + 1, delay_ms, i))
    mix_inputs = []
    if info["has_audio"]:
        mix_inputs.append("0:a:0")
    mix_inputs.extend("s%d" % i for i in range(len(ready)))
    filters.append(
        "%samix=inputs=%d:duration=longest:normalize=0:"
        "dropout_transition=0,alimiter=limit=0.95:level=false,"
        "atrim=0:%.3f,asetpts=PTS-STARTPTS[mixed]"
        % ("".join("[%s]" % m for m in mix_inputs),
           len(mix_inputs), duration))
    tmp_out = out_path + ".tmp.mp4"
    cmd += ["-filter_complex", ";".join(filters),
            "-map", "0:v:0", "-map", "[mixed]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-t", "%.3f" % duration, "-movflags", "+faststart",
            tmp_out]
    _finish(cmd, tmp_out, out_path, "مزج المؤثرات")
    print("طُبّقت المؤثرات: %s على %s"
          % ("، ".join("%s عند %.2f ث" % (n, a)
                       for n, _p, a in ready), out_path))
    if skipped:
        print("مؤثرات تُخطّيت: %s" % "، ".join(skipped))
    return out_path


# ------------------------------------------------------------------
# التراكبات
# ------------------------------------------------------------------

def _overlay_chain(vlabel, ov_input, ov_index, mode, opacity,
                   width, height, fps, duration, protect_bottom_px):
    """فلاتر تراكب واحد فوق الفيديو مع حماية شريط الكابشن.

    يقصّ أعلى الفيديو (فوق الشريط) ويمزجه مع أعلى التراكب
    بـblend، ثم يركّب أسفل الفيديو الأصلي تحته بلا أي تغيير —
    فأسفل protect_bottom_px بكسلًا يبقى مطابقًا للبكسل.
    يرجع (فلاتر، تسمية الإخراج).
    """
    top_h = height - protect_bottom_px
    out_label = "ov%d" % ov_index
    ov_label = "ovsrc%d" % ov_index
    filters = [
        # جهّز التراكب: نفس أبعاد الفيديو ومعدل إطاراته ومدته.
        "[%s]scale=%d:%d,fps=fps=%.3f,trim=0:%.3f,"
        "setpts=PTS-STARTPTS[%s]"
        % (ov_input, width, height, fps, duration, ov_label),
        # اقسم الفيديو الحالي: أعلى للمزج، وأسفل يُحفظ كما هو.
        "[%s]split=2[vsp%d_a][vsp%d_b]"
        % (vlabel, ov_index, ov_index),
        "[vsp%d_a]crop=w=iw:h=%d:y=0,format=yuv420p[vtop%d]"
        % (ov_index, top_h, ov_index),
        "[vsp%d_b]crop=w=iw:h=%d:y=%d,format=yuv420p[vbot%d]"
        % (ov_index, protect_bottom_px, top_h, ov_index),
        "[%s]crop=w=iw:h=%d:y=0,format=yuv420p[ovtop%d]"
        % (ov_label, top_h, ov_index),
        # المزج ثم إعادة التركيب فوق الأسفل المحمي.
        "[vtop%d][ovtop%d]blend=all_mode=%s:all_opacity=%.2f"
        "[vblend%d]"
        % (ov_index, ov_index, mode, opacity, ov_index),
        "[vblend%d][vbot%d]vstack,format=yuv420p[%s]"
        % (ov_index, ov_index, out_label),
    ]
    return filters, out_label


def apply_overlay(video, overlay, out, opacity=None,
                  protect_bottom_px=CAPTION_BAND_PX,
                  assets_dir=None) -> str:
    """ركّب تراكب فيلم فوق الفيديو مع حماية شريط الكابشن.

    overlay: مفتاح من OVERLAYS. burn → مزج screen (‏0.85)،
    وgrain → مزج overlay (‏0.12)؛ وopacity صريح يغلبهما.
    المزج يطال المنطقة فوق شريط الكابشن فقط؛ وأسفل الشريط
    (protect_bottom_px بكسلًا، 200 افتراضيًا) يُركَّب كما هو
    بلا أي فلتر، ويُرمَّز الفيديو libx264 crf 20 كما في
    lib/watermark.py (الترميز الفقدي قد يحرّك بكسلات الشريط
    درجة أو درجتين بضجيج الترميز — والتحقق بتفاوت لا مساواة
    حرفية). والصوت يُنسخ.
    غياب التراكب → الفيديو نفسه بلا إعادة ترميز + تحذير.
    """
    video, info = _check_video(video)
    out_path = _prepare_out(video, out)
    if overlay not in OVERLAYS:
        raise AssetsError("اسم التراكب غير صالح: %s (المقبول: %s)"
                          % (overlay, "/".join(sorted(OVERLAYS))))
    ov_path = asset_path("overlay", overlay, assets_dir)
    if ov_path is None:
        print("تُخطّي التراكب — الفيديو كما هو: %s" % video)
        return video
    if opacity is None:
        opacity = BURN_OPACITY if overlay == "burn" else GRAIN_OPACITY
    protect = int(protect_bottom_px)
    if protect < 0:
        protect = 0
    if protect >= info["height"]:
        _warn("شريط الحماية (%d بكسل) يغطي الفيديو كله — "
              "يُتخطى التراكب: %s" % (protect, overlay))
        return video
    mode = _OVERLAY_MODES[overlay]
    filters, out_label = _overlay_chain(
        "0:v", "1:v", 0, mode, float(opacity), info["width"],
        info["height"], info["fps"], info["duration"], protect)
    tmp_out = out_path + ".tmp.mp4"
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", video,
           "-stream_loop", "-1", "-i", ov_path,
           "-filter_complex", ";".join(filters),
           "-map", "[%s]" % out_label,
           "-c:v", "libx264", "-crf", "20",
           "-t", "%.3f" % info["duration"],
           "-movflags", "+faststart"]
    if info["has_audio"]:
        cmd += ["-map", "0:a:0", "-c:a", "copy"]
    cmd += [tmp_out]
    _finish(cmd, tmp_out, out_path, "تركيب التراكب")
    print("طُبّق التراكب: %s (وضع %s، شفافية %.2f، حماية أسفل "
          "%d بكسل) على %s"
          % (overlay, mode, float(opacity), protect, out_path))
    return out_path


# ------------------------------------------------------------------
# تمريرة واحدة جامعة
# ------------------------------------------------------------------

def apply_assets(video, out, sfx=(), overlays=(),
                 assets_dir=None) -> str:
    """طبّق مؤثرات وتراكبات في تمريرة ffmpeg واحدة.

    sfx: قائمة (name, at_seconds)؛ وoverlays: قائمة مفاتيح
    من OVERLAYS. يطبع ما طُبّق وما تُخطّى. لا شيء مطلوب أو
    كل الأصول غائبة → يرجع الفيديو نفسه بلا إعادة ترميز.
    """
    video, info = _check_video(video)
    out_path = _prepare_out(video, out)
    duration = info["duration"]
    applied = []
    skipped = []

    ready_sfx = []
    for name, at in (sfx or []):
        path = _resolve_sfx(name, assets_dir)
        if path is None:
            skipped.append("مؤثر %s" % name)
            continue
        at = max(0.0, float(at))
        if at >= duration:
            _warn("موضع المؤثر %s (‏%.2f ث) بعد نهاية الفيديو — "
                  "يُتخطى" % (name, at))
            skipped.append("مؤثر %s" % name)
            continue
        ready_sfx.append((str(name), path, at))
    for name, _p, at in ready_sfx:
        applied.append("مؤثر %s عند %.2f ث" % (name, at))

    ready_overlays = []
    for name in (overlays or []):
        if name not in OVERLAYS:
            _warn("اسم التراكب غير صالح — يُتخطى: %s" % name)
            skipped.append("تراكب %s" % name)
            continue
        path = asset_path("overlay", name, assets_dir)
        if path is None:
            skipped.append("تراكب %s" % name)
            continue
        ready_overlays.append((name, path))
    for name, _p in ready_overlays:
        applied.append("تراكب %s" % name)

    if not ready_sfx and not ready_overlays:
        print("لا أصول مطبقة — الفيديو كما هو: %s" % video)
        if skipped:
            print("أصول تُخطّيت: %s" % "، ".join(skipped))
        return video

    # --- المدخلات: 0 الفيديو، ثم المؤثرات، ثم التراكبات ---
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", video]
    input_index = 1
    sfx_inputs = []
    for _name, path, _at in ready_sfx:
        cmd += ["-i", path]
        sfx_inputs.append(input_index)
        input_index += 1
    ov_inputs = []
    for _name, path in ready_overlays:
        cmd += ["-stream_loop", "-1", "-i", path]
        ov_inputs.append(input_index)
        input_index += 1

    filters = []
    # --- الصوت: مؤثرات + صوت الفيديو في amix واحد ---
    audio_label = None
    if ready_sfx:
        for i, (_name, _path, at) in enumerate(ready_sfx):
            delay_ms = int(round(at * 1000))
            filters.append("[%d:a]adelay=%d:all=1,apad[s%d]"
                           % (sfx_inputs[i], delay_ms, i))
        mix_inputs = []
        if info["has_audio"]:
            mix_inputs.append("0:a:0")
        mix_inputs.extend("s%d" % i for i in range(len(ready_sfx)))
        filters.append(
            "%samix=inputs=%d:duration=longest:normalize=0:"
            "dropout_transition=0,alimiter=limit=0.95:level=false,"
            "atrim=0:%.3f,asetpts=PTS-STARTPTS[aout]"
            % ("".join("[%s]" % m for m in mix_inputs),
               len(mix_inputs), duration))
        audio_label = "aout"

    # --- الفيديو: تراكب فوق تراكب، كل واحد يحمي شريط الكابشن ---
    video_label = "0:v"
    protect = int(CAPTION_BAND_PX)
    if ready_overlays and protect < info["height"]:
        for i, (name, _path) in enumerate(ready_overlays):
            mode = _OVERLAY_MODES[name]
            opacity = BURN_OPACITY if name == "burn" else GRAIN_OPACITY
            chain, video_label = _overlay_chain(
                video_label, "%d:v" % ov_inputs[i], i, mode, opacity,
                info["width"], info["height"], info["fps"], duration,
                protect)
            filters.extend(chain)
    elif ready_overlays:
        _warn("شريط الحماية (%d بكسل) يغطي الفيديو كله — "
              "تُتخطى التراكبات" % protect)
        ready_overlays = []
        applied = [a for a in applied
                   if not a.startswith("تراكب")]
        if not ready_sfx:
            print("لا أصول مطبقة — الفيديو كما هو: %s" % video)
            if skipped:
                print("أصول تُخطّيت: %s" % "، ".join(skipped))
            return video

    tmp_out = out_path + ".tmp.mp4"
    cmd += ["-filter_complex", ";".join(filters)] if filters else []
    if video_label == "0:v":
        cmd += ["-map", "0:v:0", "-c:v", "copy"]
    else:
        # تراكب مطبق: ترميز libx264 crf 20 كما في
        # lib/watermark.py (بلا فقدان يضخّم الملف بلا جودة
        # إضافية — الفيديو الداخل فقدي أصلًا).
        cmd += ["-map", "[%s]" % video_label,
                "-c:v", "libx264", "-crf", "20"]
    if audio_label is not None:
        cmd += ["-map", "[%s]" % audio_label,
                "-c:a", "aac", "-b:a", "192k"]
    elif info["has_audio"]:
        cmd += ["-map", "0:a:0", "-c:a", "copy"]
    cmd += ["-t", "%.3f" % duration, "-movflags", "+faststart",
            tmp_out]
    _finish(cmd, tmp_out, out_path, "تطبيق الأصول")
    print("طُبّق: %s" % "، ".join(applied))
    if skipped:
        print("تُخطّى: %s" % "، ".join(skipped))
    print("الناتج: %s" % out_path)
    return out_path


__all__ = ["ASSETS_DIR_ENV", "DEFAULT_ASSETS_DIR",
           "BURN_OPACITY", "GRAIN_OPACITY",
           "CAPTION_BAND_PX", "SFX", "OVERLAYS",
           "AssetsError", "resolve_assets_dir", "asset_path",
           "add_sfx", "apply_overlay", "apply_assets"]
