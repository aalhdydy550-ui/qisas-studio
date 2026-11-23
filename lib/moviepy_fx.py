#!/usr/bin/env python3
"""مساعد تركيب اختياري عبر MoviePy — للتأثيرات التي تؤلم فلاتر ffmpeg.

- Ken Burns (تكبير بطيء) على صورة ثابتة: يُنفَّذ بدالة إطار يدوية
  (قص نافذة مركزية تتقلص مع الزمن + تكبير LANCZOS) لأن `resized`
  الزمني في MoviePy لا يتعاون مع `cropped` المركزي.
- نص عربي متحرك: TextClip في MoviePy 2 لا يشكّل العربية إطلاقًا —
  يستدعي `multiline_text` بلا `direction`، فتظهر الحروف منفصلة
  بترتيب خاطئ (اتحقق بصريًا 2026-11-21). وإعادة التشكيل المسبق
  عبر `arabic-reshaper` لا تنفع أيضًا لأن raqm في Pillow يعيد
  تطبيق bidi فيفكّها. الحل الصحيح: رسم النص مباشرة بـPillow مع
  `direction="rtl", language="ar"` (raqm يشكّل ويرتّب بنفسه) على
  صورة شفافة، ثم تمريرها كـImageClip — وهذا ما يفعله
  `animated_text_clip` هنا. الخط الأسهل يبقى ASS عبر headless-editor؛
  هذا المساعد للحالات التي تحتاج حركة نص/صورة لا يوفرها ASS.

يعمل فقط من بيئة MoviePy الخاصة بالمشروع
(`.venv-moviepy/bin/python studio.py fx ...`) — نظام python3
لا يحوي moviepy. الدوال النقية (حساب التكبير والنافذة) بلا
اعتماديات وقابلة للاختبار من أي بايثون.
"""
import os

from lib import ensure_env


class MoviePyFxError(Exception):
    """خطأ في مساعد MoviePy (رسالته عربية جاهزة للعرض)."""


ARABIC_FONT = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"
DEFAULT_SIZE = (720, 1280)


def zoom_at(t, duration, zoom_to=1.15):
    """معامل التكبير في اللحظة t: من 1.0 إلى zoom_to خطيًا."""
    if duration <= 0:
        raise MoviePyFxError("مدة المقطع يجب أن تكون موجبة: %s" % duration)
    if zoom_to < 1.0:
        raise MoviePyFxError("التكبير النهائي لا يقل عن 1.0: %s" % zoom_to)
    frac = max(0.0, min(1.0, t / duration))
    return 1.0 + (zoom_to - 1.0) * frac


def crop_window(base_w, base_h, zoom, out_w=720, out_h=1280):
    """نافذة القص المركزية (x0, y0, ww, wh) في صورة الغلاف.

    النافذة بنسبة أبعاد الخرج، وتصغر مع التكبير (فيعطي إحساس
    التقريب)، وتبقى دائمًا داخل حدود الصورة.
    """
    aspect = out_w / out_h
    wh = base_h / zoom
    ww = wh * aspect
    if ww > base_w:
        ww = float(base_w)
        wh = ww / aspect
    ww = min(ww, base_w)
    wh = min(wh, base_h)
    x0 = int((base_w - ww) / 2)
    y0 = int((base_h - wh) / 2)
    return x0, y0, int(ww), int(wh)


def render_arabic_text_image(text, fontsize=58, font_path=ARABIC_FONT,
                             color=(255, 255, 255, 255),
                             stroke_color=(0, 0, 0, 255), stroke_width=2,
                             max_width=660):
    """ارسم نصًا عربيًا على صورة شفافة (PIL Image RGBA).

    يستخدم `direction="rtl", language="ar"` فيرسم raqm النص
    مشكولًا ومرتبًا بنفسه — لا إعادة تشكيل مسبق (تفكّها raqm).
    إن تجاوز النص العرض الأقصى صغّر الخط حتى يدخل فيه.
    يرجع صورة PIL؛ يرفع MoviePyFxError عند خط فارغ أو خط مفقود.
    """
    if not text or not text.strip():
        raise MoviePyFxError("نص فارغ — لا يمكن رسم صورة نص")
    if not os.path.isfile(font_path):
        raise MoviePyFxError("ملف الخط غير موجود: %s" % font_path)
    from PIL import Image, ImageDraw, ImageFont
    size = fontsize
    while size > 12:
        font = ImageFont.truetype(font_path, size)
        probe = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        draw = ImageDraw.Draw(probe)
        bbox = draw.textbbox((0, 0), text, font=font, direction="rtl",
                             language="ar", stroke_width=stroke_width)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            break
        size -= 4
    pad = stroke_width + 8
    img = Image.new("RGBA", (w + 2 * pad, (bbox[3] - bbox[1]) + 2 * pad),
                    (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((pad - bbox[0], pad - bbox[1]), text, font=font,
              fill=color, direction="rtl", language="ar",
              stroke_width=stroke_width, stroke_fill=stroke_color)
    return img


def _require_moviepy():
    try:
        from moviepy import (AudioFileClip, CompositeVideoClip, ImageClip,
                             VideoClip)
    except ImportError:
        # تثبيت كسول (جولة v0.1.41): جهّز البيئة عند أول حاجة
        # لها — فتنجح المحاولة التالية من البيئة نفسها.
        ensure_env.ensure("moviepy")
        raise MoviePyFxError(
            "moviepy غير مثبّت في بايثون الحالي — شغّل الأمر من بيئة "
            "MoviePy:\n  ~/workspace/studio/.venv-moviepy/bin/python "
            "studio.py fx ...")
    return AudioFileClip, CompositeVideoClip, ImageClip, VideoClip


def ken_burns_clip(image_path, duration, zoom_to=1.15,
                   size=DEFAULT_SIZE):
    """مقطع Ken Burns من صورة: تكبير بطيء 1.0 ← zoom_to."""
    if not os.path.isfile(image_path):
        raise MoviePyFxError("الصورة غير موجودة: %s" % image_path)
    if duration <= 0:
        raise MoviePyFxError("مدة المقطع يجب أن تكون موجبة: %s" % duration)
    if zoom_to < 1.0:
        raise MoviePyFxError("التكبير النهائي لا يقل عن 1.0: %s" % zoom_to)
    _AudioFileClip, _Composite, _TextClip, VideoClip = _require_moviepy()
    from PIL import Image
    import numpy as np
    out_w, out_h = size
    pil = Image.open(image_path).convert("RGB")
    iw, ih = pil.size
    s0 = max(out_w / iw, out_h / ih)
    base = pil.resize((int(iw * s0), int(ih * s0)), Image.LANCZOS)
    bw, bh = base.size

    def frame(t):
        x0, y0, ww, wh = crop_window(bw, bh, zoom_at(t, duration, zoom_to),
                                     out_w, out_h)
        crop = base.crop((x0, y0, x0 + ww, y0 + wh))
        return np.array(crop.resize((out_w, out_h), Image.LANCZOS))

    return VideoClip(frame, duration=duration).with_fps(30)


def animated_text_clip(text, duration, fontsize=58, position="bottom",
                       font_path=ARABIC_FONT, fade=0.5):
    """مقطع نص عربي متحرك (ظهور/اختفاء تدريجي) — أسفل الشاشة دائمًا.

    قاعدة دائمة 2026-11-22: لا نص أعلى الشاشة أبدًا — أي موضع
    غير "bottom" (ومنها "top" القديم) يُعاد توجيهه إلى الأسفل
    (y=0.78) بدل رفضه، حتى لا يكسر متصلًا قديمًا بصمت.

    النص يُرسم بـPillow (direction=rtl) ثم يُمرَّر كـImageClip —
    لا TextClip (لا يشكّل العربية).
    """
    _AudioFileClip, _Composite, ImageClip, _VideoClip = _require_moviepy()
    import numpy as np
    img = render_arabic_text_image(text, fontsize=fontsize,
                                   font_path=font_path)
    clip = ImageClip(np.array(img), transparent=True)
    y = 0.78  # أسفل الشاشة دائمًا (انظر القاعدة أعلاه)
    clip = clip.with_position(("center", y), relative=True)
    clip = clip.with_duration(duration)
    try:
        from moviepy.video.fx import FadeIn, FadeOut
        clip = clip.with_effects([FadeIn(fade), FadeOut(fade)])
    except Exception:
        pass
    return clip


def build_fx(image_path, duration, text=None, audio_path=None,
             zoom_to=1.15, fontsize=58, size=DEFAULT_SIZE):
    """ابنِ تركيبة MoviePy: Ken Burns + نص متحرك + صوت (اختياريان)."""
    _AudioFileClip, CompositeVideoClip, _ImageClip, _VideoClip = \
        _require_moviepy()
    clips = [ken_burns_clip(image_path, duration, zoom_to, size)]
    if text:
        clips.append(animated_text_clip(text, duration,
                                        fontsize=fontsize))
    comp = CompositeVideoClip(clips, size=size).with_fps(30)
    if audio_path:
        if not os.path.isfile(audio_path):
            raise MoviePyFxError("ملف الصوت غير موجود: %s" % audio_path)
        audio = _AudioFileClip(audio_path)
        if audio.duration > duration:
            audio = audio.subclipped(0, duration)
        comp = comp.with_audio(audio)
    return comp


def render_fx(image_path, output_path, duration, text=None, audio_path=None,
              zoom_to=1.15, fontsize=58, size=DEFAULT_SIZE, timeout=900):
    """ريندر تركيبة MoviePy إلى mp4. يرجع قاموس النتيجة."""
    import time
    comp = build_fx(image_path, duration, text, audio_path,
                    zoom_to, fontsize, size)
    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    try:
        comp.write_videofile(output_path, codec="libx264",
                             audio_codec="aac", preset="ultrafast",
                             threads=2, logger=None)
    except Exception as e:
        raise MoviePyFxError("فشل ريندر MoviePy: %s" % e)
    finally:
        try:
            comp.close()
        except Exception:
            pass
    if not os.path.isfile(output_path):
        raise MoviePyFxError("انتهى الريندر دون إنشاء ملف الخرج: %s"
                             % output_path)
    return {"output": output_path,
            "seconds": round(time.time() - t0, 1),
            "size_bytes": os.path.getsize(output_path)}
