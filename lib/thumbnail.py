#!/usr/bin/env python3
"""توليد صورة مصغرة عمودية 720×1280 لأي فيديو.

نفس أسلوب المشروع المعتمد (aisha-part1-thumbnail.jpg و
hamati-thumbnail.jpg): أقوى لقطة من الفيديو (إطار يُستخرج بـ ffmpeg،
افتراضيًا عند 40% من المدة) + نص الهوك الصادم أعلى الصورة بخط عربي
عريض (Noto Naskh Arabic Bold عبر ملف ASS وفلتر subtitles).
"""
import json
import os
import subprocess
import tempfile

WIDTH = 720
HEIGHT = 1280
FONT = "Noto Naskh Arabic"
FONTSIZE = 58
MARGIN_V = 110

# مقاس أفقي للفيديو الطويل (1280×720): خط أكبر وهامش أصغر، وسطور
# هوك أطول (الصورة أعرض).
LONG_WIDTH = 1280
LONG_HEIGHT = 720
LONG_FONTSIZE = 64
LONG_MARGIN_V = 80
LONG_MAX_CHARS = 28


class ThumbnailError(Exception):
    pass


def _run(cmd, what):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=120)
    except FileNotFoundError:
        raise ThumbnailError("ffmpeg غير متاح: %s" % what)
    if proc.returncode != 0:
        raise ThumbnailError("%s فشل: %s" % (what, proc.stderr.strip()[:400]))
    return proc.stdout


def video_duration(video_path):
    # مسار مطلق: ملف اسمه يبدأ بشرطة (-test.mp4) كان يُفسَّر
    # كخيار من ffprobe فيفشل الفحص (اختراق 2026-11-22).
    video_path = os.path.abspath(os.path.expanduser(video_path))
    out = _run(["ffprobe", "-v", "error", "-show_entries",
                "format=duration", "-of",
                "default=noprint_wrappers=1:nokey=1", video_path],
               "قراءة مدة الفيديو")
    try:
        return float(out.strip())
    except ValueError:
        raise ThumbnailError("تعذر قراءة مدة الفيديو: %s" % video_path)


def wrap_hook(text, max_chars=20):
    """يقسم نص الهوك إلى سطرين متوازنين (كلمة كاملة في كل سطر)."""
    words = text.split()
    if not words:
        return [""]
    if sum(len(w) for w in words) + len(words) - 1 <= max_chars:
        return [" ".join(words)]
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if len(trial) <= max_chars or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    # أكثر من سطرين: ادمج الزائد في السطر الثاني
    if len(lines) > 2:
        lines = [lines[0], " ".join(lines[1:])]
    return lines


def write_ass(hook, ass_path, width=WIDTH, height=HEIGHT,
              fontsize=FONTSIZE, margin_v=MARGIN_V, max_chars=20):
    """يكتب ملف ASS بنص الهوك أعلى الصورة (محاذاة 8 — أعلى الوسط)."""
    # إصلاح اختبار اختراق 2026-11-21: الهوك كان يُدرج خامًا في سطر
    # Dialogue فيستطيع نصه حقن وسوم ASS ({\\fs200} و{\\pos...}).
    from lib.capite_captions import escape_ass_text
    lines = [escape_ass_text(ln)
             for ln in wrap_hook(hook, max_chars=max_chars)]
    text = "\\N".join(lines)
    ass = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hook,{font},{size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,8,40,40,{mv},1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:05.00,Hook,,0,0,0,,{text}
""".format(w=width, h=height, font=FONT, size=fontsize, mv=margin_v,
           text=text)
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass)
    return lines


def _escape_filter_path(p):
    """هرب مسار داخل قيمة فلتر ffmpeg (نفس هروب نواة headless)."""
    return (p.replace("\\", "\\\\").replace(":", "\\:")
             .replace("'", "\\'"))


def make_thumbnail(video_path, hook, out_path, at_seconds=None,
                   width=WIDTH, height=HEIGHT, fontsize=FONTSIZE,
                   margin_v=MARGIN_V, max_chars=20):
    """يولّد الصورة المصغرة. يرجع (مسار الخرج، ثانية اللقطة، سطور الهوك).

    المقاس الافتراضي 720×1280 (عمودي)؛ للأفقي مرّر
    width=1280, height=720 (أو استخدم make_long_thumbnail).
    """
    if not os.path.isfile(video_path):
        raise ThumbnailError("ملف الفيديو غير موجود: %s" % video_path)
    # مسار مطلق لنفس سبب video_duration (ملف يبدأ بشرطة).
    video_path = os.path.abspath(os.path.expanduser(video_path))
    if not hook or not hook.strip():
        raise ThumbnailError("نص الهوك فارغ")
    duration = video_duration(video_path)
    if at_seconds is None:
        at_seconds = round(duration * 0.4, 1)  # لقطة منتصف الفيديو تقريبًا
    at_seconds = max(0.0, min(float(at_seconds), max(0.0, duration - 0.1)))
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    # مجلد مؤقت فريد لكل استدعاء — الاسم الثابت .thumb-tmp كان
    # يتصادم بين استدعاءين متوازيين لنفس المجلد فيفسد أحدهما
    # الآخر (أُثبت حيًا: 6 متوازية نجح منها 3 فقط).
    tmpdir = tempfile.mkdtemp(prefix=".thumb-", dir=out_dir)
    frame = os.path.join(tmpdir, "frame.png")
    ass_path = os.path.join(tmpdir, "hook.ass")
    try:
        _run(["ffmpeg", "-y", "-v", "error", "-ss", str(at_seconds),
              "-i", video_path, "-frames:v", "1",
              "-vf", "scale=%d:%d:force_original_aspect_ratio=increase,"
                     "crop=%d:%d" % (width, height, width, height),
              frame], "استخراج إطار الفيديو")
        lines = write_ass(hook.strip(), ass_path, width=width,
                          height=height, fontsize=fontsize,
                          margin_v=margin_v, max_chars=max_chars)
        # اقتباس مسار ASS بعلامات مفردة: فاصلة في المسار كانت
        # تُقسَّم كفلترين فيفشل الحرق (أُثبت حيًا بمسار فيه فاصلة).
        _run(["ffmpeg", "-y", "-v", "error", "-i", frame,
              "-vf", "subtitles='%s'" % _escape_filter_path(ass_path),
              "-frames:v", "1", out_path], "حرق نص الهوك على الصورة")
    finally:
        for p in (frame, ass_path):
            try:
                os.remove(p)
            except OSError:
                pass
        try:
            os.rmdir(tmpdir)
        except OSError:
            pass
    if not os.path.isfile(out_path):
        raise ThumbnailError("لم يُنشأ ملف الصورة المصغرة: %s" % out_path)
    return out_path, at_seconds, lines


def make_long_thumbnail(video_path, hook, out_path, at_seconds=None):
    """صورة مصغرة أفقية 1280×720 للفيديو الطويل (نفس الأسلوب الذهبي)."""
    return make_thumbnail(video_path, hook, out_path, at_seconds,
                          width=LONG_WIDTH, height=LONG_HEIGHT,
                          fontsize=LONG_FONTSIZE, margin_v=LONG_MARGIN_V,
                          max_chars=LONG_MAX_CHARS)


def probe_image(path):
    """يرجع (العرض، الارتفاع) لملف صورة عبر ffprobe."""
    path = os.path.abspath(os.path.expanduser(path))
    out = _run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "json", path],
               "فحص أبعاد الصورة")
    info = json.loads(out)
    s = info["streams"][0]
    return int(s["width"]), int(s["height"])
