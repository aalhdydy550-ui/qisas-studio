#!/usr/bin/env python3
"""استيراد قصة طويلة من ملف نصي إلى الطابور — `queue import`.

يقرأ نصًا طويلًا، يقدّر مدة سرده (سرعة السرد ~130 كلمة/دقيقة)،
ويقسّمه لأجزاء على حدود الجمل (كل جزء 40–60 ثانية تقديرًا)،
ويضيف كل جزء عبر queue.add_story بعنوان «العنوان — الجزء N»
وملاحظة فيها رقم الجزء والمدة التقديرية والموعد المقترح
(9:00 صباحًا و7:00 مساءً بالتناوب من تاريخ بداية يُعطى أو اليوم).
"""
import datetime
import os
import re

from lib import queue as queue_lib

WORDS_PER_MINUTE = 130
TARGET_SECONDS = 50
MIN_SECONDS = 40
MAX_SECONDS = 60


def estimate_seconds(text):
    """قدّر مدة سرد نص بالثواني (130 كلمة/دقيقة)."""
    words = len((text or "").split())
    return words * 60.0 / WORDS_PER_MINUTE


def split_sentences(text):
    """قسّم نصًا إلى جمل على [.؟!] والأسطر، مع إبقاء علامة الترقيم."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        for piece in re.split(r"(?<=[.!؟])\s+", line):
            piece = piece.strip()
            if piece:
                out.append(piece)
    return out


def split_into_parts(text, target_seconds=TARGET_SECONDS):
    """قسّم نصًا لأجزاء سردية على حدود الجمل.

    كل جزء ~40–60 ثانية تقديرًا (جملة واحدة طويلة جدًا تبقى
    جزءًا وحدها). جزء أخير أقصر من 20 ثانية يُدمج مع سابقه
    إن بقي المجموع ضمن الحد. يرجع قائمة نصوص الأجزاء.
    """
    sentences = split_sentences(text)
    if not sentences:
        return []
    parts, current, cur_secs = [], [], 0.0
    for s in sentences:
        secs = estimate_seconds(s)
        if (current and cur_secs + secs > MAX_SECONDS
                and cur_secs >= MIN_SECONDS):
            parts.append(" ".join(current))
            current, cur_secs = [], 0.0
        current.append(s)
        cur_secs += secs
    if current:
        parts.append(" ".join(current))
    if len(parts) > 1:
        last_secs = estimate_seconds(parts[-1])
        if last_secs < 20:
            prev_secs = estimate_seconds(parts[-2])
            if prev_secs + last_secs <= MAX_SECONDS + 10:
                parts[-2] = parts[-2] + " " + parts[-1]
                parts.pop()
    return parts


def suggested_slots(n_parts, start_date=None):
    """مواعيد مقترحة: 9:00 و19:00 بالتناوب من تاريخ البداية."""
    start = start_date or datetime.date.today()
    slots = []
    for i in range(n_parts):
        day = start + datetime.timedelta(days=i // 2)
        hour = "09:00" if i % 2 == 0 else "19:00"
        slots.append("%s %s" % (day.isoformat(), hour))
    return slots


def import_story(queue_path, text_path, title, stories_dir=None,
                 start_date=None, target_seconds=TARGET_SECONDS):
    """استورد قصة من ملف نصي إلى الطابور. يرجع {"title", "parts"}.

    كل جزء: {"part", "number", "seconds", "suggested_time",
    "text_file"}. يرفع ValueError عند ملف مفقود أو نص فارغ أو
    عنوان فارغ، وQueueError عند عنوان مكرر.
    """
    title = (title or "").strip()
    if not title:
        raise ValueError("عنوان القصة فارغ")
    if not os.path.isfile(text_path):
        raise ValueError("ملف القصة غير موجود: %s" % text_path)
    with open(text_path, encoding="utf-8") as f:
        text = f.read()
    if not text.strip():
        raise ValueError("ملف القصة فارغ: %s" % text_path)
    parts = split_into_parts(text, target_seconds)
    if not parts:
        raise ValueError("لم تُستخرج أي جملة من الملف: %s" % text_path)
    slots = suggested_slots(len(parts), start_date)
    out_parts = []
    for i, part_text in enumerate(parts, 1):
        part_title = ("%s — الجزء %d" % (title, i)
                      if len(parts) > 1 else title)
        note = ("جزء %d من %d — ~%d ثانية سرد — مقترح %s"
                % (i, len(parts),
                   round(estimate_seconds(part_text)), slots[i - 1]))
        added = queue_lib.add_story(queue_path, part_title, part_text,
                                    parts=len(parts), note=note,
                                    stories_dir=stories_dir)
        out_parts.append({"part": i, "number": added["number"],
                          "seconds": round(estimate_seconds(part_text), 1),
                          "suggested_time": slots[i - 1],
                          "text_file": added.get("text_file")})
    return {"title": title, "parts": out_parts}
