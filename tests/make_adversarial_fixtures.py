#!/usr/bin/env python3
"""مولّد المُثبِّتات العدائية (v0.1.37 — البند 4 من تقرير tinker).

يولّد 5 مُثبِّتات تحقن عمدًا عيوب الخط المعروفة، بلا ملفات ثنائية
ملتزمة (الصوت WAV يُولَّد برمجيًا هنا؛ والفيديو الطويل يُولَّد
في الاختبار عبر ffmpeg lavfi، لا يُلتزم).

الاستخدام:
    python3 tests/make_adversarial_fixtures.py [OUT_DIR]
الافتراضي: tests/fixtures/adversarial/ (بجانب هذا الملف).

المُثبِّتات:
  (أ) hook-numeral.json — قصة هوكها يبدأ برقم («3 أخطاء…»).
  (ب) follow-gate-caption.txt — كابشن فيه جملة follow-gate.
  (ج) no-silence.wav + no-silence-captions.json — مشهد سردي
      بلا فاصل صمت (نغمة متصلة 3ث) مع كلمات موقَّتة.
  (د) long-story.json — قصة مدتها المخططة 61.5ث (>60ث).
  (هـ) broken-caption.ass — كابشن فيه U+FFFD وحروف
      Presentation Forms مفككة.
"""
import json
import math
import os
import sys
import wave

# (أ) هوك يبدأ برقم — القاعدة الدائمة: الهوك لا يبدأ برقم أبدًا.
HOOK_NUMERAL = {
    "title": "ثلاثة أخطاء تدمر البيوت",
    "hook": "3 أخطاء تدمر البيوت من غير ما تحس!",
    "story": ("رجل طيب دخل بيته فوجد زوجته تبكي. سألها: مالك؟ "
              "قالت: أخطاء صغيرة كل يوم هدمت البيت. "
              "العبرة: البيت لا يهدمه خطأ واحد، بل تكرار الصغير."),
}

# (ب) كابشن فيه جملة follow-gate (الجزء التالي مشروط بالمتابعة).
FOLLOW_GATE_CAPTION = (
    "3 أخطاء تدمر البيوت من غير ما تحس!\n"
    "رجل طيب دخل بيته فوجد زوجته تبكي.\n"
    "لو عايز الجزء الثاني اعمل متابعة للصفحة.\n"
    "#قصص_وعبر #قصص_واقعية #قصص_مؤثرة #حكايات\n"
)

# (د) قصة مدتها المخططة فوق الحد (60ث).
LONG_STORY = {
    "title": "قصة طويلة بلا تقسيم",
    "planned_duration": 61.5,
    "parts": 1,
    "note": "مدة مخططة 61.5 ثانية — خارج نطاق 40–60 ثانية.",
}

# (هـ) سطرا Dialogue: الأول فيه U+FFFD، والثاني حروف
# Arabic Presentation Forms (U+FE80–U+FEFF) مفككة.
BROKEN_ASS = (
    "[Script Info]\n"
    "Title: adversarial broken caption\n"
    "ScriptType: v4.00+\n"
    "\n"
    "[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
    "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
    "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
    "Alignment, MarginL, MarginR, MarginV, Encoding\n"
    "Style: Default,Noto Naskh Arabic,52,&H00FFFFFF,&H000000FF,"
    "&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,0,2,40,40,60,1\n"
    "\n"
    "[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
    "Effect, Text\n"
    "Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,"
    "سنة 1184\uFFFD عنزة صغيرة بقت أشهر مخلوق في القاهرة\n"
    "Dialogue: 0,0:00:02.00,0:00:04.00,Default,,0,0,0,,"
    "\uFEB3\uFEF3\uFE8D\uFEDF\n"
)


def _write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _write_text(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _write_no_silence_wav(path, seconds=3.0, freq=440.0,
                          sample_rate=16000, amplitude=0.3):
    """نغمة جيبية متصلة بلا أي فاصل صمت (سرد بلا توقف)."""
    frames = int(seconds * sample_rate)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        for i in range(frames):
            value = int(amplitude * 32767
                        * math.sin(2.0 * math.pi * freq * i / sample_rate))
            w.writeframesraw(value.to_bytes(2, "little", signed=True))


def _no_silence_captions():
    """كلمات موقَّتة للمشهد بلا صمت: عبارتان بحد بين كلمتين."""
    words = []
    text = ["سنة", "1184", "عنزة", "صغيرة", "بقت", "أشهر",
            "مخلوق", "في", "القاهرة"]
    step_ms = 300
    for i, word in enumerate(text):
        words.append({"word": word,
                      "startMs": i * step_ms,
                      "endMs": (i + 1) * step_ms,
                      "pageBreakAfter": i == 4})
    return words


def build_all(out_dir):
    """ولّد كل المُثبِّتات في out_dir. يرجع قاموس المسارات."""
    os.makedirs(out_dir, exist_ok=True)
    paths = {}
    paths["hook_numeral"] = os.path.join(out_dir, "hook-numeral.json")
    _write_json(paths["hook_numeral"], HOOK_NUMERAL)
    paths["follow_gate"] = os.path.join(
        out_dir, "follow-gate-caption.txt")
    _write_text(paths["follow_gate"], FOLLOW_GATE_CAPTION)
    paths["no_silence_wav"] = os.path.join(out_dir, "no-silence.wav")
    _write_no_silence_wav(paths["no_silence_wav"])
    paths["no_silence_captions"] = os.path.join(
        out_dir, "no-silence-captions.json")
    _write_json(paths["no_silence_captions"], _no_silence_captions())
    paths["long_story"] = os.path.join(out_dir, "long-story.json")
    _write_json(paths["long_story"], LONG_STORY)
    paths["broken_caption"] = os.path.join(
        out_dir, "broken-caption.ass")
    _write_text(paths["broken_caption"], BROKEN_ASS)
    return paths


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    default = os.path.join(here, "fixtures", "adversarial")
    target = sys.argv[1] if len(sys.argv) > 1 else default
    made = build_all(target)
    for name, path in sorted(made.items()):
        print("%s: %s" % (name, path))
