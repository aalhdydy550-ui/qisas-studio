#!/usr/bin/env python3
"""كابشنات من faster-whisper — خيار تجريبي (opt-in)، وليس الافتراضي.

السياق (WHISPER-TEST.md): اختُبر faster-whisper على سرد «حماتي»
(Piper Kareem) بموديلات tiny/base/small. النتيجة:
- التوقيت: توقيت الكلمات من small أدق من حدود silencedetect
  (متوسط خطأ حدود العبارات في ASS الحالي ~0.24 ثانية).
- النص: حتى small يخطئ في ~22% من الكلمات (WER) على سرد Piper
  السريع بالعامية، والمشهد 4 يصل إلى 44% — لا يصلح نصًا للنشر
  دون مراجعة بشرية.
- الأهم: النص المعروض على الشاشة في هذا المشروع **ليس** النص
  المنطوق أصلًا (صياغة فصحى موجزة مقابل سرد عامي بضمير المتكلم)،
  فلا يمكن ربط كلمات whisper بعبارات ASS تلقائيًا.

لذلك يبقى خط silencedetect هو الافتراضي للكتابة المتزامنة، وهذا
الموديول خيار إضافي فقط للحالات التي يكون فيها النص المعروض
**مطابقًا** للنص المنطوق (أو كأداة تحقق من مطابقة السرد للنص)،
حيث يولّد ملف ASS مباشرة من word timestamps.

الاستخدام (من بيئة faster-whisper — انظر WHISPER-TEST.md):
  ~/workspace/studio/.venv-whisper/bin/python studio.py whisper-ass \\
      --audio ~/workspace/videos/narration-male/hamati-scene1.wav \\
      --out /tmp/scene1-whisper.ass --model small

مكتبة قياسية فقط عند الاستيراد؛ faster-whisper يُستورد بتأجيل
داخل transcribe_words() حتى يعمل باقي studio بدونه.
"""
import array
import os
import re
import subprocess
import tempfile
import wave


class WhisperError(Exception):
    pass


# نفس نمط ملفات subs/ الحالية (Noto Naskh Arabic، محاذاة 2 — أسفل الوسط).
def ass_header(font_size=52):
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 720\n"
        "PlayResY: 1280\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Noto Naskh Arabic,%d,&H00FFFFFF,&H000000FF,"
        "&H80000000,&H80000000,1,0,0,0,100,100,0,0,1,3,0,2,40,40,60,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n" % font_size
    )


def format_ass_time(seconds):
    """ثوانٍ عشرية → زمن ASS مثل 0:00:01.50 (يُقص لأقرب 10 مللي ثانية)."""
    if seconds < 0:
        seconds = 0.0
    total_cs = int(round(seconds * 100))
    cs = total_cs % 100
    total_s = total_cs // 100
    s = total_s % 60
    m = (total_s // 60) % 60
    h = total_s // 3600
    return "%d:%02d:%02d.%02d" % (h, m, s, cs)


def group_words_into_phrases(words, max_words=6, max_gap=0.6,
                             max_duration=4.0):
    """يجمّع كلمات whisper (قواميس w/start/end) في عبارات زمنية.

    عبارة جديدة عند: فجوة صمت > max_gap بين كلمتين، أو بلوغ
    max_words كلمات، أو تجاوز مدة العبارة max_duration ثانية.
    """
    phrases = []
    cur = []
    for w in words:
        word = (w.get("w") or w.get("word") or "").strip()
        if not word:
            continue
        start = float(w["start"])
        end = float(w["end"])
        if cur:
            gap = start - cur[-1]["end"]
            span = end - cur[0]["start"]
            if gap > max_gap or len(cur) >= max_words or span > max_duration:
                phrases.append(_finish_phrase(cur))
                cur = []
        cur.append({"w": word, "start": start, "end": end})
    if cur:
        phrases.append(_finish_phrase(cur))
    return phrases


def _finish_phrase(words):
    return {"start": words[0]["start"], "end": words[-1]["end"],
            "text": " ".join(w["w"] for w in words),
            # توقيتات الكلمات تُحفظ للبيان — فحص حدود المشاهد
            # (lib/coverage.py) يحكم بها حرفيًا: حد داخل كلمة
            # → FAIL، وحد بين كلمتين سليم حتى بلا صمت.
            "words": [{"w": w["w"], "start": w["start"],
                       "end": w["end"]} for w in words]}


def phrases_to_ass(phrases, font_size=52):
    """عبارات زمنية → نص ملف ASS كامل بنفس نمط subs/."""
    # إصلاح اختبار اختراق 2026-11-21: العبارات كانت تُدرج خامًا
    # فيستطيع نصها حقن وسوم ASS — نفس هروب capite_captions.
    from lib.capite_captions import escape_ass_text
    lines = [ass_header(font_size)]
    for p in phrases:
        lines.append("Dialogue: 0,%s,%s,Default,,0,0,0,,%s" % (
            format_ass_time(p["start"]), format_ass_time(p["end"]),
            escape_ass_text(p["text"])))
    return "\n".join(lines) + "\n"


def load_wav_16k(path):
    """يفك ترميز wav إلى قائمة float أحادي 16kHz (stdlib فقط — بلا `av`).

    ملحوظة: إصدار `av` الذي يثبّته faster-whisper 1.2.1 افتراضيًا
    (19.x) غير متوافق معه (TypeError: metadata_errors)؛ فك الترميز
    هنا يتجنب المشكلة تمامًا لملفات wav، وملفات mp3/m4a تُحوَّل
    أولًا عبر ffmpeg في ensure_wav().
    """
    with wave.open(path, "rb") as w:
        nch, sw, sr, n = (w.getnchannels(), w.getsampwidth(),
                          w.getframerate(), w.getnframes())
        raw = w.readframes(n)
    typecode = {1: "b", 2: "h", 4: "i"}[sw]
    peak = float({1: 128, 2: 32768, 4: 2 ** 31}[sw])
    samples = array.array(typecode)
    samples.frombytes(raw)
    if nch > 1:
        mono = [sum(samples[i * nch:(i + 1) * nch]) / (nch * peak)
                for i in range(n)]
    else:
        mono = [s / peak for s in samples]
    if sr == 16000:
        return mono
    out_len = int(len(mono) * 16000 / sr)
    out = []
    for i in range(out_len):
        pos = i * (len(mono) - 1) / max(out_len - 1, 1)
        j = int(pos)
        frac = pos - j
        nxt = mono[j + 1] if j + 1 < len(mono) else mono[j]
        out.append(mono[j] * (1 - frac) + nxt * frac)
    return out


def ensure_wav(audio_path, tmpdir=None):
    """يرجع مسار wav جاهزًا: الملف نفسه لو كان wav، وإلا تحويل
    مؤقت عبر ffmpeg (16kHz أحادي)."""
    if audio_path.lower().endswith(".wav"):
        return audio_path, None
    tmpdir = tmpdir or tempfile.mkdtemp(prefix="whisper-ass-")
    out = os.path.join(tmpdir, "audio.wav")
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", audio_path,
                        "-ac", "1", "-ar", "16000", out],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.isfile(out):
        raise WhisperError("تعذر تحويل الصوت عبر ffmpeg: %s"
                           % (r.stderr.strip() or audio_path))
    return out, tmpdir


def transcribe_words(audio_path, model="small", language="ar",
                     device="cpu", compute_type="int8"):
    """يشغّل faster-whisper ويرجع (كلمات، نص كامل).

    الكلمات قواميس {"w": ..., "start": ..., "end": ...} بالثواني.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise WhisperError(
            "faster-whisper غير مثبّت في بيئة Python الحالية — شغّل "
            "الأمر من بيئة المشروع: "
            "~/workspace/studio/.venv-whisper/bin/python studio.py "
            "whisper-ass ... (التثبيت موثق في WHISPER-TEST.md)")
    if not os.path.isfile(audio_path):
        raise WhisperError("ملف الصوت غير موجود: %s" % audio_path)
    wav_path, _tmpdir = ensure_wav(audio_path)
    import numpy as np
    audio = np.asarray(load_wav_16k(wav_path), dtype=np.float32)
    fw = WhisperModel(model, device=device, compute_type=compute_type)
    segments, _info = fw.transcribe(audio, language=language,
                                    word_timestamps=True)
    words = []
    texts = []
    for seg in segments:
        texts.append(seg.text.strip())
        for w in seg.words:
            words.append({"w": w.word.strip(), "start": round(w.start, 2),
                          "end": round(w.end, 2)})
    return words, " ".join(t for t in texts if t)


def whisper_ass(audio_path, ass_path, model="small", max_words=6,
                max_gap=0.6, max_duration=4.0, font_size=52):
    """من ملف صوت إلى ملف ASS؛ يرجع (عبارات، نص مسموع كامل)."""
    words, text = transcribe_words(audio_path, model=model)
    phrases = group_words_into_phrases(words, max_words=max_words,
                                       max_gap=max_gap,
                                       max_duration=max_duration)
    if not phrases:
        raise WhisperError("لم يسمع whisper أي كلام في: %s" % audio_path)
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(phrases_to_ass(phrases, font_size=font_size))
    return phrases, text


# ---------------------------------------------------------------- SRT
_SRT_TIME_RE = re.compile(r"^(\d+):(\d{2}):(\d{2})[,.](\d{3})$")
_SRT_RANGE_RE = re.compile(r"^\s*(\S+)\s+-->\s+(\S+)")


def _srt_time(token):
    """زمن SRT مثل 00:01:23,450 → ثوانٍ عشرية."""
    m = _SRT_TIME_RE.match(token.strip())
    if not m:
        raise WhisperError("زمن SRT غير صالح: %s" % token)
    h, mnt, s, ms = (int(x) for x in m.groups())
    return h * 3600 + mnt * 60 + s + ms / 1000.0


def parse_srt(text):
    """نص SRT → (عبارات، عدد الكتل المتخطاة).

    الكتلة: رقم تسلسلي اختياري، ثم سطر النطاق
    `HH:MM:SS,mmm --> HH:MM:SS,mmm`، ثم سطور النص (تُدمج
    بمسافة في عبارة واحدة — نفس نمط عبارات subs/).
    الكتل الفارغة أو ذات الزمن التالف أو النهاية قبل البداية
    تُتخطى وتُحتسب، لا تُفشل التحويل كله.
    """
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip())
    phrases = []
    skipped = 0
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        if lines[0].isdigit():
            lines = lines[1:]
        if not lines:
            skipped += 1
            continue
        m = _SRT_RANGE_RE.match(lines[0])
        if not m:
            skipped += 1
            continue
        try:
            start = _srt_time(m.group(1))
            end = _srt_time(m.group(2))
        except WhisperError:
            skipped += 1
            continue
        phrase_text = " ".join(lines[1:]).strip()
        if not phrase_text or end <= start:
            skipped += 1
            continue
        phrases.append({"start": start, "end": end, "text": phrase_text})
    return phrases, skipped


def srt_to_ass(srt_path, ass_path, font_size=52):
    """حوّل ملف SRT إلى ASS بنفس نمط ملفات subs/ الحالية.

    يرجع (عبارات، عدد الكتل المتخطاة). يرفع WhisperError عند
    ملف مفقود أو بلا أي عبارة صالحة.
    """
    if not os.path.isfile(srt_path):
        raise WhisperError("ملف SRT غير موجود: %s" % srt_path)
    with open(srt_path, encoding="utf-8-sig") as f:
        text = f.read()
    phrases, skipped = parse_srt(text)
    if not phrases:
        raise WhisperError("لا عبارات صالحة في ملف SRT: %s" % srt_path)
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(phrases_to_ass(phrases, font_size=font_size))
    return phrases, skipped
