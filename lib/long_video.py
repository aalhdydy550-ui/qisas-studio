#!/usr/bin/env python3
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
import os
import re

from . import long_narration

TITLE_CARD_SECONDS = 3.0
IMAGE_CLIP_SECONDS = 5.0
MIN_CARD_SECONDS = 3.0
HOOK_FONTSIZE = 64
TITLE_FONTSIZE = 64
OUTRO_FONTSIZE = 56
CAPTION_FONTSIZE = 44
TARGET_MIN_SECONDS = 480.0
TARGET_MAX_SECONDS = 720.0
SCENE_GAP_SECONDS = 0.35


class LongVideoError(Exception):
    """خطأ في بناء الفيديو الطويل (رسالته عربية)."""


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
    narration = os.path.join(assets_dir, "audio", "narration-full.wav")
    if not os.path.isfile(narration):
        raise LongVideoError(
            "ملف السرد الكامل غير موجود: %s" % narration)
    duration = float(manifest.get("narration_duration") or 0.0)
    if duration <= 0:
        raise LongVideoError("مدة السرد في البيان صفر أو غائبة")
    from lib.paths import resolve_inside, safe_component
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
    captions_path = os.path.join(assets_dir, "captions.json")
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
    if title is None:
        title = _read_text_file(os.path.join(path, "title.txt"),
                                "عنوان الفصل")
    if not title:
        raise LongVideoError("عنوان الفصل فارغ في: %s" % path)
    if moral is None:
        moral = ""
        moral_path = os.path.join(path, "moral.txt")
        if os.path.isfile(moral_path):
            moral = _read_text_file(moral_path, "عبرة الفصل")
    scene_wavs = _list_media(path, (".wav",))
    scene_wavs = [p for p in scene_wavs
                  if re.search(r"scene\d+", os.path.basename(p),
                               re.IGNORECASE)]
    work = work_dir or os.path.join(path, ".long-video")
    os.makedirs(work, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_",
                  os.path.basename(os.path.abspath(path)))
    narration = os.path.join(path, "narration.wav")
    phrases = []
    if os.path.isfile(narration):
        if atempo != 1.0:
            narration = long_narration.apply_atempo(narration, atempo, work)
        duration = long_narration.probe_duration(narration)
        ass_path = os.path.join(path, "phrases.ass")
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
            ass_path = os.path.join(path, base + ".ass")
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
    images = _list_media(os.path.join(path, "images"), (".jpg", ".jpeg", ".png"))
    if not images:
        cover = os.path.join(path, "cover.jpg")
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


def _content_images(images, duration):
    """وزّع صور الفصل على مدة السرد (5 ثوانٍ للصورة، الأخيرة تُمدَّد)."""
    import math
    n = max(1, int(round(duration / IMAGE_CLIP_SECONDS)))
    clips = []
    for i in range(n):
        if i < n - 1:
            clips.append((images[i % len(images)], IMAGE_CLIP_SECONDS))
        else:
            clips.append((images[i % len(images)],
                          round(duration - IMAGE_CLIP_SECONDS * (n - 1), 3)))
    return clips


def build_project(spec):
    """ابنِ مشروع headless-editor كاملًا للفيديو الطويل.

    spec: {"title", "hook", "intro": {"text","narration","duration"},
    "outro": {...}, "chapters": [فصل], "music": مسار|None,
    "width": 1280, "height": 720, "fps": 30}.
    يرجع (مشروع JSON، meta) — وmeta فيه توقيتات الفصول للطوابع والوصف.
    """
    chapters = spec.get("chapters") or []
    if not chapters:
        raise LongVideoError("الفيديو الطويل يحتاج فصلًا واحدًا على الأقل")
    width = int(spec.get("width", 1280))
    height = int(spec.get("height", 720))
    fps = int(spec.get("fps", 30))
    intro = spec.get("intro") or {}
    outro = spec.get("outro") or {}
    for label, part in (("المقدمة", intro), ("الخاتمة", outro)):
        if not part.get("narration") or not os.path.isfile(part["narration"]):
            raise LongVideoError("سرد %s غير موجود" % label)
        if float(part.get("duration") or 0) <= 0:
            raise LongVideoError("مدة سرد %s صفر" % label)
    for ch in chapters:
        if not ch.get("title"):
            raise LongVideoError("فصل بلا عنوان")
        if not ch.get("narration") or not os.path.isfile(ch["narration"]):
            raise LongVideoError(
                "سرد الفصل غير موجود: %s" % ch.get("title"))
        if float(ch.get("duration") or 0) <= 0:
            raise LongVideoError("مدة الفصل صفر: %s" % ch.get("title"))
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
    tracks.append({"type": "image", "src": intro_img, "start": 0.0,
                   "duration": round(intro_dur, 3), "transition_in": "none",
                   "ken_burns": "in"})
    tracks.append({"type": "audio", "src": intro["narration"], "start": 0.0,
                   "duration": round(float(intro["duration"]), 3),
                   "volume": 1.0})
    tracks.append({"type": "text", "text": spec.get("hook") or spec["title"],
                   "start": 0.0, "end": round(intro_dur, 3),
                   "position": "top", "fontsize": HOOK_FONTSIZE})
    intro_meta = {"start": 0.0, "end": round(intro_dur, 3)}
    cursor = intro_dur

    for idx, ch in enumerate(chapters):
        ch_start = cursor
        title_img = ch["images"][0]
        tracks.append({"type": "image", "src": title_img,
                       "start": round(cursor, 3),
                       "duration": TITLE_CARD_SECONDS,
                       "transition_in": "none", "ken_burns": "in"})
        tracks.append({"type": "text", "text": ch["title"],
                       "start": round(cursor, 3),
                       "end": round(cursor + TITLE_CARD_SECONDS, 3),
                       "position": "middle", "fontsize": TITLE_FONTSIZE})
        cursor += TITLE_CARD_SECONDS
        content_start = cursor
        dur = float(ch["duration"])
        kb = "in"
        for img, clip_dur in _content_images(ch["images"], dur):
            tracks.append({"type": "image", "src": img,
                           "start": round(cursor, 3),
                           "duration": round(clip_dur, 3),
                           "transition_in": "none", "ken_burns": kb})
            kb = "out" if kb == "in" else "in"
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
        meta_chapters.append({
            "index": idx + 1, "title": ch["title"],
            "moral": ch.get("moral") or "",
            "start": round(ch_start, 3), "end": round(cursor, 3),
            "content_start": round(content_start, 3)})

    outro_dur = max(float(outro["duration"]), MIN_CARD_SECONDS)
    outro_img = chapters[-1]["images"][-1]
    outro_start = cursor
    tracks.append({"type": "image", "src": outro_img,
                   "start": round(cursor, 3),
                   "duration": round(outro_dur, 3),
                   "transition_in": "none", "ken_burns": "out"})
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
    meta = {"title": spec.get("title", ""), "total_duration": total,
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
