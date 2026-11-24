#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
r"""كابشنات كاريوكي (كلمة-بكلمة) — منطق مستعار من Capite ومُعاد تنفيذه هنا.

لماذا إعادة تنفيذ؟ كود Capite نفسه (https://github.com/muneebkhan08/Capite)
لم يُشغَّل ولم يُثبَّت في هذا المشروع — نسخته المستنسخة لم تجتز فحص
مخاطر التنفيذ، فيلزم موافقة صريحة من المستخدم لتشغيله. ما فُعل هنا:
قراءة منطقه (قراءة نصية فقط) وإعادة تنفيذ الحد الأدنى منه بأدواتنا
الموثوقة أصلًا (faster-whisper + ffmpeg + libass).

المنطق المستعار (من قراءة backend/subtitles.py وsubtitle_utils.py):
- توقيت كل كلمة من faster-whisper → تجميع في أسطر بميزانية حروف
  (للعربية: نسبة عرض حرف ~0.58 وخط أصغر نسبيًا)، سطران كحد أقصى
  لكل مجموعة، ثم مجموعة جديدة.
- حدث ASS واحد لكل كلمة: يبدأ مع الكلمة وينتهي عند بداية الكلمة
  التالية (ناقص 10 مللي ثانية)، ونصه السطر الكامل مع تمييز الكلمة
  النشطة بلون مختلف.
- للعربية (RTL): لا يُستخدم وسم الكاريوكي {\\kf} — libass لا
  يمسحه باتجاه صحيح في RTL؛ التمييز بتغيير اللون فقط ({\c...}).
  هذا فرع RTL الصريح في كود Capite نفسه.
- لا التفاف تلقائي يعتمد عليه: الأسطر محسوبة مسبقًا بميزانية
  الحروف، والخط Noto Naskh Arabic (نفس خط الكتابة الحالي).

قيود معروفة (من WHISPER-TEST.md): نص whisper نفسه يخطئ في
~22% من الكلمات (small) على سرد Piper — راجع النص قبل النشر.
والنص المعروض أصلًا في هذا المشروع صياغة فصحى مختلفة عن المنطوق،
فالكاريوكي يصلح فقط حين يكون النص المعروض مطابقًا للمنطوق.
الاستخدام (من بيئة faster-whisper):
  ~/workspace/studio/.venv-whisper/bin/python studio.py karaoke-ass \\
      --audio ~/workspace/videos/narration-male/hamati-scene1.wav \\
      --out /tmp/scene1-karaoke.ass --model small
"""
import os

from lib import whisper_captions

HIGHLIGHT_COLOR = "&H0000FFFF"  # أصفر (ASS: &H00BBGGRR)


class CapiteError(Exception):
    """خطأ في توليد كابشنات الكاريوكي (رسالته عربية جاهزة للعرض)."""


def escape_ass_text(text):
    """هرب محارف ASS الخاصة في نص كلمة."""
    return (text.replace("\\", "\\\\")
                .replace("{", "\\{")
                .replace("}", "\\}")
                .replace("\n", " "))


def group_words_into_lines(words, max_chars=28, max_lines=2):
    """يجمّع كلمات (قواميس w/start/end) في مجموعات من سطرين كحد أقصى.

    كل مجموعة: {"start": ..., "end": ..., "lines": [[كلمات...], ...]}.
    كلمة جديدة تنتقل للسطر التالي إن تجاوزت ميزانية الحروف،
    ومجموعة جديدة إن امتلأ السطران.
    """
    groups = []
    cur_lines = [[]]
    cur_chars = [0]
    cur_start = None
    cur_end = None

    def flush():
        nonlocal cur_lines, cur_chars, cur_start, cur_end
        if cur_lines and any(cur_lines):
            groups.append({"start": cur_start, "end": cur_end,
                           "lines": [list(ln) for ln in cur_lines]})
        cur_lines = [[]]
        cur_chars = [0]
        cur_start = None
        cur_end = None

    for w in words:
        word = (w.get("w") or w.get("word") or "").strip()
        if not word:
            continue
        start = float(w["start"])
        end = float(w["end"])
        if cur_start is None:
            cur_start = start
            cur_lines = [[{"w": word, "start": start, "end": end}]]
            cur_chars = [len(word)]
            cur_end = end
            continue
        idx = len(cur_lines) - 1
        chars = cur_chars[idx] + (1 if cur_lines[idx] else 0) + len(word)
        if chars <= max_chars:
            cur_lines[idx].append({"w": word, "start": start, "end": end})
            cur_chars[idx] = chars
            cur_end = end
        elif idx + 1 < max_lines:
            cur_lines.append([{"w": word, "start": start, "end": end}])
            cur_chars.append(len(word))
            cur_end = end
        else:
            flush()
            cur_start = start
            cur_lines = [[{"w": word, "start": start, "end": end}]]
            cur_chars = [len(word)]
            cur_end = end
    flush()
    return groups


def _line_text(line, active_idx, highlight=HIGHLIGHT_COLOR):
    """سطر كامل مع تمييز الكلمة النشطة (بلون) — بلا {\\kf} (RTL)."""
    parts = []
    for i, w in enumerate(line):
        text = escape_ass_text(w["w"])
        if i == active_idx:
            parts.append("{\\c%s}%s{\\r}" % (highlight, text))
        else:
            parts.append(text)
    return " ".join(parts)


def words_to_karaoke_ass(words, font_size=52, max_chars=28, max_lines=2,
                         highlight=HIGHLIGHT_COLOR):
    """كلمات بتوقيتها → نص ملف ASS كامل (حدث لكل كلمة)."""
    groups = group_words_into_lines(words, max_chars=max_chars,
                                    max_lines=max_lines)
    if not groups:
        raise CapiteError("لا كلمات لتوليد الكابشنات منها")
    lines = [whisper_captions.ass_header(font_size)]
    for g in groups:
        flat = []  # (كلمة، سطر)
        for li, line in enumerate(g["lines"]):
            for w in line:
                flat.append((w, li))
        for idx, (w, _li) in enumerate(flat):
            start = w["start"]
            if idx + 1 < len(flat):
                end = flat[idx + 1][0]["start"] - 0.01
            else:
                end = g["end"]
            if end <= start:
                end = start + 0.10
            text_parts = []
            for li, line in enumerate(g["lines"]):
                active = None
                for j, ww in enumerate(line):
                    if ww is w:
                        active = j
                text_parts.append(_line_text(line, active, highlight))
            text = "\\N".join(text_parts)
            lines.append("Dialogue: 0,%s,%s,Default,,0,0,0,,%s" % (
                whisper_captions.format_ass_time(start),
                whisper_captions.format_ass_time(end), text))
    return "\n".join(lines) + "\n", groups


def karaoke_ass(audio_path, ass_path, model="small", max_chars=28,
                max_lines=2, font_size=52):
    """من ملف صوت إلى ملف ASS كاريوكي؛ يرجع (مجموعات، نص مسموع)."""
    words, text = whisper_captions.transcribe_words(audio_path, model=model)
    if not words:
        raise CapiteError("لم يسمع whisper أي كلام في: %s" % audio_path)
    ass_text, groups = words_to_karaoke_ass(
        words, font_size=font_size, max_chars=max_chars,
        max_lines=max_lines)
    out_dir = os.path.dirname(os.path.abspath(ass_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_text)
    return groups, text
