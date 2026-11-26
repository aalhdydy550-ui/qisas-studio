#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""الفيديو الطويل — تجميع عدة قصص في فيديو أفقي واحد 1280×720.

البنية: بطاقة مقدمة بهوك + فصل لكل قصة (بطاقة عنوان 3 ثوانٍ ثم
محتوى القصة بسردها وكتابتها) + بطاقة خاتمة بدعوة اشتراك واحدة.
الريندر عبر نواة headless-editor (مشروع JSON → ffmpeg) — لا يُعاد
اختراع الريندر هنا. الشعار يُحرق بعد الريندر (مثل run/assemble)،
وبطاقات الاقتباس لا تُلْحق أبدًا بالفيديو الطويل (هي للشورتس).

مصادر الفصول:
- مشروع OpenMontage جاهز (بيان + سرد كامل + كتابة بكلمات موقوتة).
- مجلد تشغيل سابق (manifest.json + assets/).
- مجلد فصل مُعدّ (title.txt + narration.wav/scene*.wav +
  phrases.ass/scene*.ass + images/ أو cover.jpg).
- فصل نصي (عنوان + نص + صورة غلاف؛ السرد يُركَّب بـlong-narration).

الكتابة على الشاشة: كلمة-بكلمة (word_highlight) بتوقيتات حقيقية من
captions.json لمشاريع OpenMontage، وبتوقيتات مقدَّرة بتقسيم متساوٍ
داخل كل عبارة لباقي المصادر (السرد ثابت الإيقاع تقريبًا).
"""
import copy
import json
import math
import os
import re
import shutil
import tempfile

from . import headless_stage
from . import long_narration
from . import motion_clips
from .paths import resolve_inside
from .stage_cache import hash_file

TITLE_CARD_SECONDS = 3.0
IMAGE_CLIP_SECONDS = 5.0
# إيقاع يوتيوب الطويل (v0.1.45): القنوات المقاسة تغيّر الصورة كل
# 1–3 ثوانٍ (الراوي 2.0ث، حكايا الليل 3.4ث) — فالوضع youtube-long
# يستخدم 2.5 ثانية للصورة الاحتياطية بدل 5، مع قطع مباشر وبلا
# Ken Burns أبدًا. انظر ~/workspace/flow-eval/youtube-motion/REPORT-AR.md
YOUTUBE_LONG_IMAGE_SECONDS = 2.5
MIN_CARD_SECONDS = 3.0
HOOK_FONTSIZE = 64
TITLE_FONTSIZE = 64
OUTRO_FONTSIZE = 56
CAPTION_FONTSIZE = 44
TARGET_MIN_SECONDS = 480.0
TARGET_MAX_SECONDS = 720.0
SCENE_GAP_SECONDS = 0.35
# إصلاح اختبار اختراق 2026-11-22 (M4): مدة فصل غير مسقوفة
# (1e7 ث) كانت تولّد 2,000,009 مقاطع و811MB مشروع — سقف مطلق
# 3600 ثانية للفصل/السرد، و720 للمدة المستهدفة.
MAX_CHAPTER_SECONDS = 3600.0
MAX_TARGET_SECONDS = 720.0


class LongVideoError(Exception):
    """خطأ في بناء الفيديو الطويل (رسالته عربية)."""


def _check_duration(duration, what):
    """ارفض مدة غير رقمية أو غير منتهية أو فوق السقف المطلق."""
    try:
        duration = float(duration)
    except (TypeError, ValueError):
        raise LongVideoError("مدة %s غير صالحة: %s" % (what, duration))
    if not math.isfinite(duration) or duration <= 0:
        raise LongVideoError("مدة %s غير صالحة: %s" % (what, duration))
    if duration > MAX_CHAPTER_SECONDS:
        raise LongVideoError(
            "مدة %s فوق الحد الأقصى %d ثانية (وصلت %.1f)"
            % (what, int(MAX_CHAPTER_SECONDS), duration))
    return duration


def _resolve_in(base, path, what):
    """حلّ مسار داخل base وارفض الهارب عبر رابط رمزي (M1)."""
    try:
        return resolve_inside(base, path, what)
    except ValueError as e:
        raise LongVideoError(str(e))


def mmss(seconds):
    """حوّل ثوانٍ إلى MM:SS (أو H:MM:SS إن تجاوزت الساعة)."""
    total = max(0, int(round(float(seconds))))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return "%d:%02d:%02d" % (h, m, s)
    return "%02d:%02d" % (m, s)


def estimate_word_times(text, start, end):
    """وزّع كلمات عبارة بتساوٍ على [start, end] (توقيت تقديري).

    يُستخدم حين لا توجد توقيتات كلمات حقيقية (captions.json).
    """
    words = (text or "").split()
    if not words:
        return []
    start = float(start)
    end = float(end)
    if end <= start:
        end = start + 0.1
    if len(words) == 1:
        return [{"w": words[0], "start": round(start, 3),
                 "end": round(end, 3)}]
    step = (end - start) / len(words)
    out = []
    for i, w in enumerate(words):
        out.append({"w": w,
                    "start": round(start + i * step, 3),
                    "end": round(start + (i + 1) * step, 3)})
    return out


def _ass_time_to_seconds(text):
    """حوّل زمن ASS (h:mm:ss.cc) إلى ثوانٍ."""
    m = re.match(r"(\d+):(\d\d):(\d\d)\.(\d\d)", text.strip())
    if not m:
        raise LongVideoError("زمن ASS غير صالح: %s" % text)
    h, minute, sec, cs = (int(x) for x in m.groups())
    return h * 3600 + minute * 60 + sec + cs / 100.0


def parse_ass(path):
    """اقرأ عبارات ملف ASS (أسطر Dialogue) → [{start, end, text}]."""
    if not os.path.isfile(path):
        raise LongVideoError("ملف ASS غير موجود: %s" % path)
    phrases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.startswith("Dialogue:"):
                continue
            body = line[len("Dialogue:"):].strip()
            fields = body.split(",", 9)
            if len(fields) < 10:
                continue
            try:
                start = _ass_time_to_seconds(fields[1])
                end = _ass_time_to_seconds(fields[2])
            except LongVideoError:
                continue
            text = re.sub(r"\{[^}]*\}", "", fields[9])
            text = text.replace("\\N", " ").strip()
            if text and end > start:
                phrases.append({"start": start, "end": end, "text": text})
    return phrases


def _natural_key(name):
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]


def _list_media(directory, extensions):
    if not os.path.isdir(directory):
        return []
    return sorted((os.path.join(directory, f) for f in os.listdir(directory)
                   if f.lower().endswith(extensions)),
                  key=lambda p: _natural_key(os.path.basename(p)))


def _read_text_file(path, what):
    if not os.path.isfile(path):
        raise LongVideoError("ملف %s غير موجود: %s" % (what, path))
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def _words_by_phrase(captions_path):
    """جمّع كلمات captions.json إلى عبارات (مثل build_phrases).

    يرجع قائمة عبارات، كل عبارة قائمة كلمات {w, start, end} بالثواني.
    """
    try:
        with open(captions_path, encoding="utf-8") as f:
            words = json.load(f)
    except (ValueError, OSError) as e:
        raise LongVideoError("ملف الكتابة تالف أو لا يُقرأ (%s): %s"
                             % (captions_path, e))
    if not isinstance(words, list):
        raise LongVideoError(
            "بنية ملف الكتابة غير متوقعة (ليست قائمة): %s" % captions_path)
    phrases, cur = [], []
    for w in words:
        if not isinstance(w, dict) or not all(
                k in w for k in ("word", "startMs", "endMs")):
            raise LongVideoError(
                "كلمة ناقصة الحقول في ملف الكتابة: %s" % captions_path)
        cur.append({"w": w["word"],
                    "start": round(w["startMs"] / 1000.0, 3),
                    "end": round(w["endMs"] / 1000.0, 3)})
        if w.get("pageBreakAfter"):
            phrases.append(cur)
            cur = []
    if cur:
        phrases.append(cur)
    return phrases


def chapter_from_manifest(manifest, assets_dir, title=None, moral=""):
    """ابنِ فصلًا من بيان studio (manifest) وأصوله المُجهَّزة.

    الكتابة بمستوى الكلمة من assets/captions.json (توقيتات حقيقية)
    إن وُجد، وإلا عبارات فقط.
    """
    narration = _resolve_in(
        assets_dir, os.path.join(assets_dir, "audio", "narration-full.wav"),
        "ملف السرد الكامل")
    if not os.path.isfile(narration):
        raise LongVideoError(
            "ملف السرد الكامل غير موجود: %s" % narration)
    duration = _check_duration(manifest.get("narration_duration") or 0.0,
                               "السرد في البيان")
    from lib.paths import safe_component
    images_dir = os.path.join(assets_dir, "images")
    images = []
    for name in manifest.get("sequence", []):
        # إصلاح اختبار اختراق 2026-11-21: اسم من البيان بلا تحقق
        # كان يشير إلى ملف خارج مجلد الأصول.
        try:
            safe_component(name, "اسم الصورة")
            images.append(resolve_inside(
                images_dir, os.path.join(images_dir, name),
                "صورة الفصل"))
        except ValueError as e:
            raise LongVideoError(str(e))
    if not images:
        raise LongVideoError("تسلسل الصور في البيان فارغ")
    missing = [p for p in images if not os.path.isfile(p)]
    if missing:
        raise LongVideoError("صور مفقودة في أصول الفصل: %s" % missing[0])
    word_groups = None
    captions_path = _resolve_in(
        assets_dir, os.path.join(assets_dir, "captions.json"),
        "ملف الكتابة")
    if os.path.isfile(captions_path):
        word_groups = _words_by_phrase(captions_path)
    phrases = []
    for i, p in enumerate(manifest.get("phrases", [])):
        phrase = {"start": float(p["start"]), "end": float(p["end"]),
                  "text": p["text"], "words": None}
        if word_groups and i < len(word_groups):
            phrase["words"] = word_groups[i]
        if not phrase["words"]:
            phrase["words"] = estimate_word_times(
                phrase["text"], phrase["start"], phrase["end"])
        phrases.append(phrase)
    return {
        "title": title or manifest.get("hook")
                 or manifest.get("project", "قصة"),
        "moral": moral or "",
        "narration": narration,
        "duration": duration,
        "images": images,
        "phrases": phrases,
    }


def load_chapter_dir(path, work_dir=None, atempo=1.0, title=None,
                     moral=None):
    """ابنِ فصلًا من مجلد فصل مُعدّ.

    التخطيط:
      title.txt            (مطلوب) عنوان الفصل — سطر واحد
      moral.txt            (اختياري) عبرة الفصل
      narration.wav        (أو scene*.wav) — السرد
      phrases.ass          (أو scene*.ass) — عبارات السرد
      images/              (أو cover.jpg) — صور الفصل
    مشاهد scene*.wav تُدمج بفواصل صمت، وعبارات scene*.ass تُزاح
    زمنيًا لتطابق الدمج. atempo تُطبَّق على السرد إن لم تكن 1.0.
    title/moral الممرَّران يتجاوزان ملفي title.txt/moral.txt.
    """
    if not os.path.isdir(path):
        raise LongVideoError("مجلد الفصل غير موجود: %s" % path)
    # إصلاح اختبار اختراق 2026-11-22 (M1): كل ملف في مجلد الفصل
    # يُحلّ بـresolve_inside — رابط رمزي يشير خارج المجلد يُرفض
    # بدل اتباعه (سرد/عبارات/صور/غلاف).
    if title is None:
        title = _read_text_file(_resolve_in(
            path, os.path.join(path, "title.txt"), "عنوان الفصل"),
            "عنوان الفصل")
    if not title:
        raise LongVideoError("عنوان الفصل فارغ في: %s" % path)
    if moral is None:
        moral = ""
        moral_path = _resolve_in(
            path, os.path.join(path, "moral.txt"), "عبرة الفصل")
        if os.path.isfile(moral_path):
            moral = _read_text_file(moral_path, "عبرة الفصل")
    scene_wavs = _list_media(path, (".wav",))
    scene_wavs = [_resolve_in(path, p, "ملف سرد المشهد")
                  for p in scene_wavs
                  if re.search(r"scene\d+", os.path.basename(p),
                               re.IGNORECASE)]
    work = work_dir or os.path.join(path, ".long-video")
    os.makedirs(work, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_",
                  os.path.basename(os.path.abspath(path)))
    narration = _resolve_in(path, os.path.join(path, "narration.wav"),
                            "ملف السرد")
    phrases = []
    if os.path.isfile(narration):
        if atempo != 1.0:
            narration = long_narration.apply_atempo(narration, atempo, work)
        duration = long_narration.probe_duration(narration)
        ass_path = _resolve_in(path, os.path.join(path, "phrases.ass"),
                               "ملف العبارات")
        if os.path.isfile(ass_path):
            phrases = parse_ass(ass_path)
    elif scene_wavs:
        merged = os.path.join(work, "%s-narration.wav" % slug)
        # طبّق السرعة على كل مشهد قبل الدمج (مثل إنتاج عائشة ج2)
        timed = []
        for wav in scene_wavs:
            w = long_narration.apply_atempo(wav, atempo, work) \
                if atempo != 1.0 else wav
            timed.append(w)
        duration = long_narration.concatenate_with_gaps(
            timed, merged, gap=SCENE_GAP_SECONDS)
        narration = merged
        cursor = 0.0
        for wav, timed_wav in zip(scene_wavs, timed):
            dur = long_narration.probe_duration(timed_wav)
            base = os.path.splitext(os.path.basename(wav))[0]
            ass_path = _resolve_in(
                path, os.path.join(path, base + ".ass"), "ملف العبارات")
            if os.path.isfile(ass_path):
                for p in parse_ass(ass_path):
                    phrases.append({
                        "start": round(cursor + p["start"], 3),
                        "end": round(cursor + p["end"], 3),
                        "text": p["text"]})
            cursor += dur + SCENE_GAP_SECONDS
    else:
        raise LongVideoError(
            "مجلد الفصل بلا سرد (narration.wav أو scene*.wav): %s" % path)
    duration = _check_duration(duration, "فصل %s" % path)
    images = [_resolve_in(path, p, "صورة الفصل") for p in
              _list_media(os.path.join(path, "images"),
                          (".jpg", ".jpeg", ".png"))]
    if not images:
        cover = _resolve_in(path, os.path.join(path, "cover.jpg"),
                            "غلاف الفصل")
        if os.path.isfile(cover):
            images = [cover]
    if not images:
        raise LongVideoError(
            "مجلد الفصل بلا صور (images/ أو cover.jpg): %s" % path)
    for p in phrases:
        p["words"] = estimate_word_times(p["text"], p["start"], p["end"])
    return {"title": title, "moral": moral, "narration": narration,
            "duration": duration, "images": images, "phrases": phrases}


def chapter_from_text(title, text, narration_info, images, moral=""):
    """ابنِ فصلًا نصيًا من سرد مركَّب (long-narration) وصور.

    narration_info: نتيجة synthesize_long (output/duration/chunks).
    العبارات هي جمل السرد بتوقيتاتها الدقيقة، والكلمات مقدَّرة
    بتقسيم متساوٍ داخل كل جملة.
    """
    if not images:
        raise LongVideoError("الفصل النصي بلا صور: %s" % title)
    _check_duration(narration_info["duration"], "الفصل النصي %s" % title)
    phrases = []
    for c in narration_info["chunks"]:
        phrases.append({
            "start": float(c["start"]), "end": float(c["end"]),
            "text": c["text"],
            "words": estimate_word_times(c["text"], c["start"],
                                         c["end"])})
    return {"title": title, "moral": moral or "",
            "narration": narration_info["output"],
            "duration": float(narration_info["duration"]),
            "images": list(images), "phrases": phrases}


def _content_images(images, duration, clip_seconds=IMAGE_CLIP_SECONDS):
    """وزّع صور الفصل على مدة السرد (clip_seconds للصورة، الأخيرة تُمدَّد)."""
    import math
    n = max(1, int(round(duration / clip_seconds)))
    clips = []
    for i in range(n):
        if i < n - 1:
            clips.append((images[i % len(images)], clip_seconds))
        else:
            clips.append((images[i % len(images)],
                          round(duration - clip_seconds * (n - 1), 3)))
    return clips


MOTION_MODES = ("clips", "still", "kenburns", "youtube-long")

# المسار السريع بلا GPU (الموجة الأولى، الطلب 1): العروض الجديدة
# تستخدم Ken Burns افتراضيًا؛ و"clips" خيار صريح يتطلب حصة GPU
# ووقت توليد (Wan/LTX) — يُفعَّل لاحقًا عبر improve_motion.
FAST_MOTION_DEFAULT = "kenburns"

# رسالة المسار السريع — نص حرفي من خطة الموجة الأولى (الطلب 1):
# تُطبع عند إنتاج المسودة السريعة وتُحفظ في تقريرها.
FAST_DRAFT_GPU_NOTE = ("الفيديو السريع جاهز الآن؛ الحركة المولّدة تحتاج "
                       "حصة GPU ووقتًا — أعد التشغيل بـ`--motion clips` لاحقًا")


def _segment_duration(seg):
    """مدة مقطع motion محلول (فيديو: out-in، صورة: duration)."""
    if seg.get("kind") == "video":
        return round(float(seg["out"]) - float(seg["in"]), 3)
    return round(float(seg["duration"]), 3)


def _check_motion_segments(ch, duration):
    """تحقق من motion_segments فصل: فيديو/صورة فقط، وتملأ المدة."""
    segs = ch.get("motion_segments")
    if not isinstance(segs, list) or not segs:
        raise LongVideoError(
            "motion_segments الفصل %s يجب أن تكون قائمة غير فارغة"
            % ch.get("title"))
    total = 0.0
    for seg in segs:
        if not isinstance(seg, dict):
            raise LongVideoError(
                "مقطع حركة في الفصل %s ليس كائنًا" % ch.get("title"))
        kind = seg.get("kind")
        if kind == "freeze":
            raise LongVideoError(
                "مقطع freeze في الفصل %s يجب حلّه قبل build_project "
                "(استخرج آخر إطار أولًا)" % ch.get("title"))
        if kind not in ("video", "image"):
            raise LongVideoError(
                "نوع مقطع حركة غير معروف في الفصل %s: %s"
                % (ch.get("title"), kind))
        if not seg.get("src") or not os.path.isfile(seg["src"]):
            raise LongVideoError(
                "ملف مقطع حركة غير موجود في الفصل %s: %s"
                % (ch.get("title"), seg.get("src")))
        if kind == "video":
            try:
                seg_in = float(seg["in"])
                seg_out = float(seg["out"])
            except (KeyError, TypeError, ValueError):
                raise LongVideoError(
                    "مقطع فيديو في الفصل %s بلا in/out صالحين"
                    % ch.get("title"))
            if seg_out <= seg_in:
                raise LongVideoError(
                    "مقطع فيديو في الفصل %s: out يجب أن تكون بعد in"
                    % ch.get("title"))
        total = round(total + _segment_duration(seg), 3)
    if abs(total - duration) > 0.01:
        raise LongVideoError(
            "مدة motion_segments الفصل %s (%.3f ث) لا تملأ مدة الفصل "
            "(%.3f ث)" % (ch.get("title"), total, duration))
    return segs


def build_project(spec):
    """ابنِ مشروع headless-editor كاملًا للفيديو الطويل.

    spec: {"title", "hook", "intro": {"text","narration","duration"},
    "outro": {...}, "chapters": [فصل], "music": مسار|None,
    "width": 1280, "height": 720, "fps": 30,
    "motion": "clips"|"still"|"kenburns"|"youtube-long"
    (الافتراضي FAST_MOTION_DEFAULT = "kenburns" — المسار السريع بلا
    GPU أولًا؛ و"clips" خيار صريح كما كان)}.
    "youtube-long" مثل "clips" تمامًا في حلّ مقاطع الحركة من
    المانيفست، لكن الصور الاحتياطية تُوزَّع 2.5 ثانية للصورة بدل
    5 (إيقاع القطع السريع في قصص يوتيوب الطويلة) وبلا Ken Burns.
    الفصول قد تحمل "motion_segments" (مقاطع محلولة مسبقًا من النوعين
    video/image فقط — لا freeze) و"motion_report" (mode/warnings).
    يرجع (مشروع JSON، meta) — وmeta فيه توقيتات الفصول للطوابع والوصف.
    """
    chapters = spec.get("chapters") or []
    if not chapters:
        raise LongVideoError("الفيديو الطويل يحتاج فصلًا واحدًا على الأقل")
    motion = spec.get("motion", FAST_MOTION_DEFAULT)
    if motion not in MOTION_MODES:
        raise LongVideoError(
            "وضع الحركة غير معروف: %s "
            "(المسموح: clips/still/kenburns/youtube-long)"
            % motion)
    width = int(spec.get("width", 1280))
    height = int(spec.get("height", 720))
    fps = int(spec.get("fps", 30))
    intro = spec.get("intro") or {}
    outro = spec.get("outro") or {}
    for label, part in (("المقدمة", intro), ("الخاتمة", outro)):
        if not part.get("narration") or not os.path.isfile(part["narration"]):
            raise LongVideoError("سرد %s غير موجود" % label)
        # إصلاح اختبار اختراق 2026-11-22 (M4): مدة غير مسقوفة
        # هنا أيضًا قبل توليد أي مقاطع.
        _check_duration(part.get("duration") or 0, "سرد %s" % label)
    for ch in chapters:
        if not ch.get("title"):
            raise LongVideoError("فصل بلا عنوان")
        if not ch.get("narration") or not os.path.isfile(ch["narration"]):
            raise LongVideoError(
                "سرد الفصل غير موجود: %s" % ch.get("title"))
        _check_duration(ch.get("duration") or 0,
                        "الفصل %s" % ch.get("title"))
        if not ch.get("images"):
            raise LongVideoError("الفصل بلا صور: %s" % ch.get("title"))
        missing = [p for p in ch["images"] if not os.path.isfile(p)]
        if missing:
            raise LongVideoError("صورة مفقودة في فصل %s: %s"
                                 % (ch.get("title"), missing[0]))
    music = spec.get("music")
    if music and not os.path.isfile(music):
        raise LongVideoError("ملف الموسيقى الخلفية غير موجود: %s" % music)

    tracks = []
    # بطاقات العناوين المحروقة (إصلاح التضاعف — 2026-11-26):
    # تسجيل فقط، بلا تغيير في أي مسار ريندر — لتكون العناوين
    # مقروءة آليًا عند التوصيل (مقدمة + كل فصل + خاتمة).
    title_cards = []
    meta_chapters = []
    cursor = 0.0
    intro_dur = max(float(intro["duration"]), MIN_CARD_SECONDS)
    intro_img = chapters[0]["images"][0]
    intro_track = {"type": "image", "src": intro_img, "start": 0.0,
                   "duration": round(intro_dur, 3),
                   "transition_in": "none"}
    if motion == "kenburns":
        intro_track["ken_burns"] = "in"
    tracks.append(intro_track)
    tracks.append({"type": "audio", "src": intro["narration"], "start": 0.0,
                   "duration": round(float(intro["duration"]), 3),
                   "volume": 1.0})
    tracks.append({"type": "text", "text": spec.get("hook") or spec["title"],
                   "start": 0.0, "end": round(intro_dur, 3),
                   # "above" = أسفل الشاشة فوق الكابشن (قاعدة دائمة
                   # 2026-11-22: لا نص أعلى الشاشة أبدًا).
                   "position": "above", "fontsize": HOOK_FONTSIZE})
    title_cards.append({"text": spec.get("hook") or spec["title"],
                        "start": 0.0, "end": round(intro_dur, 3),
                        "position": "above"})
    intro_meta = {"start": 0.0, "end": round(intro_dur, 3)}
    cursor = intro_dur

    for idx, ch in enumerate(chapters):
        ch_start = cursor
        title_img = ch["images"][0]
        title_track = {"type": "image", "src": title_img,
                       "start": round(cursor, 3),
                       "duration": TITLE_CARD_SECONDS,
                       "transition_in": "none"}
        if motion == "kenburns":
            title_track["ken_burns"] = "in"
        tracks.append(title_track)
        tracks.append({"type": "text", "text": ch["title"],
                       "start": round(cursor, 3),
                       "end": round(cursor + TITLE_CARD_SECONDS, 3),
                       "position": "middle", "fontsize": TITLE_FONTSIZE})
        title_cards.append({"text": ch["title"],
                            "start": round(cursor, 3),
                            "end": round(cursor + TITLE_CARD_SECONDS, 3),
                            "position": "middle"})
        cursor += TITLE_CARD_SECONDS
        content_start = cursor
        dur = float(ch["duration"])
        if ch.get("motion_segments"):
            for seg in _check_motion_segments(ch, dur):
                seg_dur = _segment_duration(seg)
                if seg["kind"] == "video":
                    tracks.append({
                        "type": "video", "src": seg["src"],
                        "start": round(cursor, 3),
                        "duration": round(seg_dur, 3),
                        "in": round(float(seg["in"]), 3),
                        "out": round(float(seg["out"]), 3),
                        "volume": 0, "transition_in": "none"})
                else:
                    tracks.append({
                        "type": "image", "src": seg["src"],
                        "start": round(cursor, 3),
                        "duration": round(seg_dur, 3),
                        "transition_in": "none"})
                cursor += seg_dur
        else:
            kb = "in"
            clip_seconds = (YOUTUBE_LONG_IMAGE_SECONDS
                            if motion == "youtube-long"
                            else IMAGE_CLIP_SECONDS)
            for img, clip_dur in _content_images(ch["images"], dur,
                                                 clip_seconds):
                track = {"type": "image", "src": img,
                         "start": round(cursor, 3),
                         "duration": round(clip_dur, 3),
                         "transition_in": "none"}
                if motion == "kenburns":
                    track["ken_burns"] = kb
                    kb = "out" if kb == "in" else "in"
                tracks.append(track)
                cursor += clip_dur
        tracks.append({"type": "audio", "src": ch["narration"],
                       "start": round(content_start, 3),
                       "duration": round(dur, 3), "volume": 1.0})
        for p in ch.get("phrases", []):
            track = {"type": "text", "text": p["text"],
                     "start": round(content_start + float(p["start"]), 3),
                     "end": round(content_start + float(p["end"]), 3),
                     "position": "bottom", "fontsize": CAPTION_FONTSIZE}
            if p.get("words"):
                track["word_highlight"] = True
                track["words"] = [
                    {"w": w["w"],
                     "start": round(content_start + float(w["start"]), 3),
                     "end": round(content_start + float(w["end"]), 3)}
                    for w in p["words"]]
            tracks.append(track)
        report = ch.get("motion_report")
        if isinstance(report, dict) and "mode" in report:
            ch_motion = {"mode": report.get("mode") or motion,
                         "warnings": list(report.get("warnings") or [])}
        else:
            ch_motion = {"mode": motion, "warnings": []}
        meta_chapters.append({
            "index": idx + 1, "title": ch["title"],
            "moral": ch.get("moral") or "",
            "start": round(ch_start, 3), "end": round(cursor, 3),
            "content_start": round(content_start, 3),
            "motion": ch_motion})

    outro_dur = max(float(outro["duration"]), MIN_CARD_SECONDS)
    outro_img = chapters[-1]["images"][-1]
    outro_start = cursor
    outro_track = {"type": "image", "src": outro_img,
                   "start": round(cursor, 3),
                   "duration": round(outro_dur, 3),
                   "transition_in": "none"}
    if motion == "kenburns":
        outro_track["ken_burns"] = "out"
    tracks.append(outro_track)
    tracks.append({"type": "audio", "src": outro["narration"],
                   "start": round(cursor, 3),
                   "duration": round(float(outro["duration"]), 3),
                   "volume": 1.0})
    tracks.append({"type": "text", "text": outro["text"],
                   "start": round(cursor, 3),
                   "end": round(cursor + outro_dur, 3),
                   "position": "middle", "fontsize": OUTRO_FONTSIZE})
    title_cards.append({"text": outro["text"],
                        "start": round(cursor, 3),
                        "end": round(cursor + outro_dur, 3),
                        "position": "middle"})
    cursor += outro_dur
    total = round(cursor, 3)
    if music:
        tracks.append({"type": "audio", "src": music, "start": 0.0,
                       "duration": total, "role": "background",
                       "volume": 0.3})
    project = {"name": spec.get("title", "long-video"), "width": width,
               "height": height, "fps": fps, "tracks": tracks}
    motion_warnings = []
    for mc in meta_chapters:
        motion_warnings.extend(mc["motion"]["warnings"])
    meta = {"title": spec.get("title", ""), "total_duration": total,
            "motion": motion, "motion_warnings": motion_warnings,
            "intro": intro_meta,
            "chapters": meta_chapters,
            "title_cards": title_cards,
            "outro": {"start": round(outro_start, 3), "end": total}}
    return project, meta


DEFAULT_HEADLESS_EDITOR = os.path.expanduser(
    "~/workspace/headless-editor/editor.py")


def _file_hash_or_path(path):
    """بصمة محتوى ملف لمفتاح تخزين، أو مساره المطلق عند تعذّر القراءة.

    الرجوع للمسار fail-open لمفتاح التخزين فقط — لا يؤثر في
    المخرج أبدًا (أسوأ ما يحدث إصابة/غياب إضافي في التخزين).
    """
    if not path:
        return None
    try:
        return hash_file(path)
    except OSError:
        return os.path.abspath(os.path.expanduser(path))


def _fast_draft_cache_inputs(spec, project):
    """مدخلات تخزين المسودة السريعة — مبنية على المحتوى لا المسارات.

    فصل يتغيّر نصه أو سردُه أو أي صورة فيه يغيّر المفتاح،
    فيُعاد ريندره؛ وما لم يتغيّر شيء يُعاد استخدام الفيديو.
    """
    chapters = []
    for ch in spec.get("chapters") or []:
        chapters.append({
            "title": ch.get("title"),
            "duration": ch.get("duration"),
            "images": [_file_hash_or_path(p)
                       for p in ch.get("images") or []],
            "narration": _file_hash_or_path(ch.get("narration")),
            "phrases": [(p.get("text"), p.get("start"), p.get("end"))
                        for p in ch.get("phrases") or []],
        })
    intro = spec.get("intro") or {}
    outro = spec.get("outro") or {}
    return {
        "kind": "fast-draft",
        "motion": FAST_MOTION_DEFAULT,
        "title": spec.get("title"),
        "hook": spec.get("hook"),
        "width": project.get("width"),
        "height": project.get("height"),
        "fps": project.get("fps"),
        "intro": {"text": intro.get("text"),
                  "narration": _file_hash_or_path(
                      intro.get("narration"))},
        "outro": {"text": outro.get("text"),
                  "narration": _file_hash_or_path(
                      outro.get("narration"))},
        "chapters": chapters,
    }


def _synthesize_fast_part(text, out_wav, work_dir, voice):
    """ركّب نص مقدمة/خاتمة/فصل بـPiper (الراوي الرجل افتراضيًا).

    يرجع نتيجة synthesize_long (output/duration/chunks).
    """
    return long_narration.synthesize_long(
        text, out_wav, work_dir=work_dir, voice=voice)


def build_fast_draft(spec, out_path, cache=None, editor_path=None,
                     work_dir=None, timeout=900, voice="piper"):
    """ابنِ مسودة سريعة بلا GPU من spec بشكل build_project.

    المسودة: سرد Piper (الراوي الرجل — إما جاهزًا في spec أو
    يُركَّب هنا من فصل نصي {"title","text","images"}) + صور ثابتة
    بحركة Ken Burns + كتابة متزامنة عبارة بعبارة أسفل الصورة فقط
    (نفس build_project — لا مسار كتابة جديد هنا). بلا موسيقى أبدًا:
    أي "music" في spec تُسقَط وتُوثَّق في التقرير.

    out_path: إن انتهى بـ.json كُتب ملف المشروع فقط بلا ريندر؛
    وإلا رُندر فيديو MP4 عبر headless-editor وكُتب مشروع JSON
    بجانبه (<الاسم>-project.json). spec الممرَّرة لا تُعدَّل
    (نسخة عميقة داخلية)، وmotion تُفرَض kenburns دائمًا.

    cache: StageCache اختياري — إصابة فيديو مطابقة تعيد استخدام
    الفيديو المخزّن بلا إعادة ريندر (record في مكانه).

    يرجع {"output": مسار المخرج، "duration": مدة الفيديو،
    "report": {"motion": "kenburns", "note": FAST_DRAFT_GPU_NOTE،
    "cache_hit": bool، "music_dropped": bool، "warnings": [...],
    "voice": voice، "format": "video"|"project-json"،
    "project_json": مسار مشروع JSON، "work_dir": مجلد العمل}}.
    تطبع FAST_DRAFT_GPU_NOTE عند كل إنتاج.
    """
    if not isinstance(spec, dict):
        raise LongVideoError("مواصفات المسودة السريعة يجب أن تكون كائنًا")
    if not out_path:
        raise LongVideoError("مسار مخرج المسودة السريعة مطلوب")
    out_path = os.path.abspath(os.path.expanduser(out_path))
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if work_dir:
        work = os.path.abspath(os.path.expanduser(work_dir))
        os.makedirs(work, exist_ok=True)
    else:
        # مجلد مؤقت يُحفَظ (لا يُحذف): سرد الفصول النصية المُركَّب
        # هنا قد يشير إليه مشروع JSON المكتوب بجانب المخرج.
        work = tempfile.mkdtemp(prefix="fast-draft-")
    fast = copy.deepcopy(spec)
    # 1) فصول نصية: ركّب سردها بـPiper وابنِ الفصل (إعادة استخدام
    # chapter_from_text — لا منطق سرد جديد هنا).
    for i, ch in enumerate(fast.get("chapters") or []):
        if not isinstance(ch, dict):
            continue
        narr = ch.get("narration")
        if narr and os.path.isfile(narr):
            continue
        text = ch.get("text")
        images = ch.get("images") or []
        if not text or not images:
            continue
        info = _synthesize_fast_part(
            text, os.path.join(work, "chapter-%d.wav" % (i + 1)),
            work, voice)
        fast["chapters"][i] = chapter_from_text(
            ch.get("title") or "فصل %d" % (i + 1), text, info,
            images, moral=ch.get("moral") or "")
    # 2) مقدمة/خاتمة نصيتان بلا سرد: ركّبهما بالطريقة نفسها.
    for label, fname in (("intro", "intro.wav"), ("outro", "outro.wav")):
        part = fast.get(label) or {}
        if not isinstance(part, dict):
            continue
        narr = part.get("narration")
        if narr and os.path.isfile(narr):
            continue
        text = part.get("text")
        if not text:
            continue
        info = _synthesize_fast_part(
            text, os.path.join(work, fname), work, voice)
        fast[label] = {"text": text, "narration": info["output"],
                       "duration": info["duration"]}
    # 3) المسار السريع: Ken Burns دائمًا، وبلا موسيقى أبدًا.
    fast["motion"] = FAST_MOTION_DEFAULT
    music_dropped = bool(fast.get("music"))
    fast["music"] = None
    project, meta = build_project(fast)
    duration = meta["total_duration"]
    is_json = out_path.lower().endswith(".json")
    if is_json:
        project_json = out_path
    else:
        base, _ = os.path.splitext(out_path)
        project_json = base + "-project.json"
    with open(project_json, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)
    report = {
        "motion": FAST_MOTION_DEFAULT,
        "note": FAST_DRAFT_GPU_NOTE,
        "cache_hit": False,
        "music_dropped": music_dropped,
        "warnings": list(meta.get("motion_warnings") or []),
        "voice": voice,
        "format": "project-json" if is_json else "video",
        "project_json": project_json,
        "work_dir": work,
        "chapters": len(fast.get("chapters") or []),
        "total_duration": duration,
    }
    if not is_json:
        cache_inputs = None
        if cache is not None:
            cache_inputs = _fast_draft_cache_inputs(fast, project)
            try:
                hit = cache.lookup("video", cache_inputs)
            except Exception:
                hit = None
            if hit and os.path.isfile(hit):
                if hit != out_path:
                    shutil.copyfile(hit, out_path)
                # إصابة والتخزين في مكانه (record): المخرج نفسه
                # هو النسخة المخزّنة — لا نسخ ولا إعادة ريندر.
                report["cache_hit"] = True
                report["reused"] = ["video"]
                print(FAST_DRAFT_GPU_NOTE)
                return {"output": out_path, "duration": duration,
                        "report": report}
        editor = editor_path or DEFAULT_HEADLESS_EDITOR
        try:
            headless_stage.render_project(editor, project_json,
                                          out_path, timeout=timeout)
        except headless_stage.HeadlessError as e:
            raise LongVideoError(str(e))
        if cache is not None and cache_inputs is not None:
            try:
                cache.record("video", cache_inputs, out_path)
            except Exception:
                # فشل التسجيل في التخزين لا يفشل مسودة سليمة.
                pass
    print(FAST_DRAFT_GPU_NOTE)
    return {"output": out_path, "duration": duration, "report": report}


def improve_motion(spec, motion_manifest, motion_dir, cache=None,
                   freeze_dir=None, work_dir=None, clip_seconds=None):
    """بدّل صور المسودة السريعة بمقاطع مولّدة (ترقية الحركة).

    يأخذ spec بشكل build_project (يفضَّل ناتج build_fast_draft —
    لكن أي spec صالح يعمل) + مانيفست حركة (مسار ملف أو قاموس
    محمّل) + مجلد المقاطع المولّدة، فيحلّ لكل فصل مقاطعه عبر
    motion_clips.resolve_chapter_motion، ويحوّل مقاطع freeze إلى
    صور (آخر إطار) — مع إعادة استخدام المنتجات غير المتغيرة عبر
    StageCache: إطار مجمّد مولَّد من قبل يُعاد استخدامه بلا إعادة
    استخراج، والفيديو المولَّد نفسه لا يُعاد توليده أبدًا (هذه
    الدالة لا تولّد مقاطع — التوليد GPU خارجها).

    freeze_dir: مجلد الإطارات المجمّدة الجديدة (بلا cache)؛
    وبلا freeze_dir/work_dir يُنشأ مجلد مؤقت يُحفَظ ويُوثَّق
    مساره في التقرير. spec الممرَّرة لا تُعدَّل.

    يرجع {"spec": spec الجديدة (motion="clips" + motion_segments
    وmotion_report لكل فصل)، "motion": "clips"،
    "reused": [تسميات المنتجات المعاد استخدامها]،
    "generated": [تسميات المنتجات المولَّدة حديثًا]،
    "warnings": [...]، "report": {...}} — وتُتحقق مقاطع كل فصل
    بنفس تحققات build_project (عبر _check_motion_segments).
    """
    if not isinstance(spec, dict):
        raise LongVideoError("مواصفات تحسين الحركة يجب أن تكون كائنًا")
    if isinstance(motion_manifest, dict):
        manifest = motion_manifest
    else:
        try:
            manifest = motion_clips.load_motion_manifest(motion_manifest)
        except motion_clips.MotionError as e:
            raise LongVideoError(str(e))
    if not motion_dir or not os.path.isdir(motion_dir):
        raise LongVideoError(
            "مجلد المقاطع المولّدة غير موجود: %s" % motion_dir)
    if clip_seconds is None:
        clip_seconds = motion_clips.IMAGE_CLIP_SECONDS
    if freeze_dir:
        freeze_dir = os.path.abspath(os.path.expanduser(freeze_dir))
        os.makedirs(freeze_dir, exist_ok=True)
    elif work_dir:
        freeze_dir = os.path.join(
            os.path.abspath(os.path.expanduser(work_dir)),
            "motion-freezes")
        os.makedirs(freeze_dir, exist_ok=True)
    else:
        freeze_dir = tempfile.mkdtemp(prefix="motion-freezes-")
    new_spec = copy.deepcopy(spec)
    chapters = new_spec.get("chapters") or []
    if not chapters:
        raise LongVideoError("تحسين الحركة يحتاج فصلًا واحدًا على الأقل")
    reused, generated, warnings = [], [], []
    chapter_reports = []
    for i, ch in enumerate(chapters):
        if not isinstance(ch, dict):
            raise LongVideoError("فصل ليس كائنًا في الموضع %d" % (i + 1))
        if not ch.get("duration"):
            raise LongVideoError(
                "الفصل %s بلا مدة صالحة" % (ch.get("title") or i + 1))
        try:
            resolved = motion_clips.resolve_chapter_motion(
                ch, manifest, motion_dir, i + 1,
                clip_seconds=clip_seconds)
        except motion_clips.MotionError as e:
            raise LongVideoError(str(e))
        ch_warnings = list(resolved.get("warnings") or [])
        segments = []
        for j, seg in enumerate(resolved.get("segments") or []):
            if seg.get("kind") != "freeze":
                segments.append(seg)
                continue
            label = "chapter-%d-freeze-%d" % (i + 1, j)
            src = seg["src"]
            inputs = {"kind": "freeze-frame",
                      "video": os.path.abspath(src),
                      "video_hash": _file_hash_or_path(src)}
            cached = None
            if cache is not None:
                try:
                    cached = cache.lookup("scenes", inputs)
                except Exception:
                    cached = None
            if cached and os.path.isfile(cached):
                segments.append({"kind": "image", "src": cached,
                                 "duration": seg["duration"]})
                reused.append(label)
                continue
            out_jpg = os.path.join(
                freeze_dir, "ch%d-%d.jpg" % (i + 1, j))
            try:
                motion_clips.extract_last_frame(src, out_jpg)
            except motion_clips.MotionError as e:
                ch_warnings.append(
                    "تعذّر تجميد آخر إطار للمقطع في الفصل %s (%s) — "
                    "صورة ثابتة بدلًا منه"
                    % (ch.get("title") or (i + 1), e))
                segments.append({"kind": "image",
                                 "src": (ch.get("images") or [None])[0],
                                 "duration": seg["duration"]})
                continue
            if cache is not None:
                try:
                    stored = cache.store("scenes", inputs, out_jpg)
                except Exception:
                    stored = out_jpg
            else:
                stored = out_jpg
            segments.append({"kind": "image", "src": stored,
                             "duration": seg["duration"]})
            generated.append(label)
        ch["motion_segments"] = segments
        ch["motion_report"] = {"mode": resolved.get("mode") or "clips",
                               "warnings": ch_warnings}
        # نفس تحققات build_project حرفيًا (مدة المقاطع = مدة الفصل).
        _check_motion_segments(ch, float(ch["duration"]))
        warnings.extend(ch_warnings)
        chapter_reports.append({
            "title": ch.get("title") or "",
            "mode": resolved.get("mode"),
            "segments": len(segments),
            "warnings": ch_warnings,
        })
    new_spec["motion"] = "clips"
    report = {"motion": "clips", "reused": list(reused),
              "generated": list(generated),
              "warnings": list(warnings),
              "freeze_dir": freeze_dir,
              "chapters": chapter_reports}
    return {"spec": new_spec, "motion": "clips",
            "reused": reused, "generated": generated,
            "warnings": warnings, "report": report}


def format_timestamps(meta):
    """طوابع فصول يوتيوب (MM:SS) من meta بناء المشروع."""
    lines = ["%s المقدمة" % mmss(meta["intro"]["start"])]
    for ch in meta["chapters"]:
        lines.append("%s الفصل %d: %s"
                     % (mmss(ch["start"]), ch["index"], ch["title"]))
    lines.append("%s الخاتمة" % mmss(meta["outro"]["start"]))
    return "\n".join(lines) + "\n"


def build_description(meta, hook, subscribe_line, page_url):
    """نص وصف يوتيوب: هوك + فصول بتوقيتاتها وعبرها + اشتراك + روابط."""
    parts = [hook, ""]
    parts.append("فصول الفيديو:")
    for ch in meta["chapters"]:
        line = "%s — %s" % (mmss(ch["start"]), ch["title"])
        if ch.get("moral"):
            line += " (العبرة: %s)" % ch["moral"]
        parts.append(line)
    parts.append("")
    parts.append(subscribe_line)
    if page_url:
        parts.append(page_url)
    parts.append("")
    parts.append("#قصص_وعبر #قصص_واقعية #حكايات")
    return "\n".join(parts) + "\n"
