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
import json
import math
import os
import re

from . import long_narration
from .paths import resolve_inside

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
    (الافتراضي "clips")}.
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
    motion = spec.get("motion", "clips")
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
            "outro": {"start": round(outro_start, 3), "end": total}}
    return project, meta


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
