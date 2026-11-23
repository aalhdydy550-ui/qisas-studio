#!/usr/bin/env python3
"""سرد طويل مقسّم بصوت Piper (الراوي الرجل) — نص طويل إلى WAV واحد.

Piper يقرأ نصًا كاملًا دفعة واحدة، فالنصوص الطويلة (دقائق) تُقسَّم
إلى جمل، وتُركَّب كل جملة على حدة، ثم تُدمج بفواصل صمت قصيرة بين
الجمل (وقفات درامية، مثل أسلوب المشروع). كل جملة يعرف زمن بدايتها
ونهايتها بدقة بعد الدمج، فتُبنى عليها الكتابة المتزامنة مع الكلام.

الصوت ثابت دائمًا: الراوي الرجل ar_JO-kareem-medium
(الموديل ~/workspace/tts-models/ar_JO-kareem-medium.onnx،
الثنائي ~/.local/bin/piper). لا يُستخدم أي صوت آخر هنا —
إلا بصوت ثانٍ اختياري (voice="gtts") عبر lib/gtts_voice.py،
أو (voice="supertonic-M1") عبر lib/supertonic_voice.py —
ولا يبدّل الافتراضي أبدًا (Piper دائمًا).
"""
import os
import re
import shutil
import subprocess
import tempfile

from . import gtts_voice
from . import supertonic_voice

PIPER_BIN = os.path.expanduser("~/.local/bin/piper")
PIPER_MODEL = os.path.expanduser(
    "~/workspace/tts-models/ar_JO-kareem-medium.onnx")

# أقصى حروف في مقطع Piper واحد قبل تقسيم الجملة الطويلة.
MAX_CHUNK_CHARS = 300
# فاصل الصمت بين الجمل بالثواني (وقفة درامية عند الفواصل).
DEFAULT_GAP_SECONDS = 0.35


class LongNarrationError(Exception):
    """خطأ في توليد السرد الطويل (رسالته عربية)."""


def _run(cmd, what, timeout=300):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except FileNotFoundError:
        raise LongNarrationError(
            "%s: الأمر غير موجود: %s" % (what, cmd[0]))
    except subprocess.TimeoutExpired:
        raise LongNarrationError(
            "%s: انتهت المهلة (%d ثانية)" % (what, timeout))
    if proc.returncode != 0:
        raise LongNarrationError(
            "%s فشل (رمز الخروج %d): %s"
            % (what, proc.returncode,
               (proc.stderr or proc.stdout or "").strip()[-500:]))
    return proc


def probe_duration(path):
    """مدة ملف صوتي بالثواني عبر ffprobe."""
    # إصلاح اختبار اختراق 2026-11-22 (L2): مسار نسبي يبدأ
    # بشرطة كان يُفسَّر كخيار من ffprobe — المسار المطلق كما في
    # check.py.
    path = os.path.abspath(os.path.expanduser(path))
    out = _run(["ffprobe", "-v", "error", "-show_entries",
                "format=duration", "-of",
                "default=noprint_wrappers=1:nokey=1", path],
               "قراءة مدة الصوت")
    try:
        return float(out.stdout.strip())
    except ValueError:
        raise LongNarrationError("تعذر قراءة مدة الصوت: %s" % path)


def split_sentences(text):
    """قسّم نصًا عربيًا إلى جمل عند (. ! ؟ …) أو سطر جديد.

    علامة الترقيم تبقى ملتصقة بجملتها. الجمل الفارغة تُحذف.
    """
    if not text:
        return []
    parts = re.split(r"(?<=[.!؟…])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def split_chunks(text, max_chars=MAX_CHUNK_CHARS):
    """قسّم نصًا طويلًا إلى مقاطع Piper (جملة لكل مقطع غالبًا).

    الجملة الأطول من max_chars تُقسَّم عند «،» أو «؛» أو « - »،
    وإن بقيت طويلة تُقسَّم عند حدود الكلمات. لا يُقطع نص في
    منتصف كلمة أبدًا.
    """
    chunks = []
    for sentence in split_sentences(text):
        if len(sentence) <= max_chars:
            chunks.append(sentence)
            continue
        # جرّب التقسيم عند الفواصل الداخلية أولًا
        pieces = re.split(r"(?<=[،؛])\s+", sentence)
        for piece in pieces:
            if len(piece) <= max_chars:
                chunks.append(piece)
                continue
            # تقسيم قسري عند حدود الكلمات
            words = piece.split()
            cur = ""
            for w in words:
                trial = (cur + " " + w).strip()
                if len(trial) <= max_chars or not cur:
                    cur = trial
                else:
                    chunks.append(cur)
                    cur = w
            if cur:
                chunks.append(cur)
    return chunks


def _resample_to_22050_mono(wav_path):
    """وحّد معدل عينة ملف WAV إلى 22050 هرتز أحادي (معدل Piper).

    مخرج Supertonic 44100 هرتز؛ و`concatenate_with_gaps` يأخذ
    المعدل من أول مقطع، فاختلاف المعدلات بين المقاطع يكسر
    التجميع — لذلك يُوحَّد كل مقطع Supertonic قبل الدمج.
    """
    tmp = wav_path + ".22050.wav"
    _run(["ffmpeg", "-y", "-v", "error", "-i", wav_path,
          "-ar", "22050", "-ac", "1", tmp],
         "توحيد معدل عينة الصوت")
    os.replace(tmp, wav_path)
    return wav_path


def synthesize_chunk(text, out_wav, piper_bin=PIPER_BIN,
                     model=PIPER_MODEL, timeout=120, voice="piper"):
    """ركّب مقطعًا واحدًا بـPiper (أو gTTS أو Supertonic M1).

    يرفع LongNarrationError عند الفشل. الصوت الافتراضي Piper
    (الراوي الرجل) — gTTS وsupertonic-M1 صوتان اختياريان فقط.
    مخرج Supertonic يُوحَّد إلى 22050 هرتز أحادي قبل إرجاعه
    (معدل Piper) ليتسق الدمج اللاحق.
    """
    if voice == "gtts":
        try:
            return gtts_voice.synthesize_gtts_chunk(text, out_wav)
        except gtts_voice.GttsError as e:
            raise LongNarrationError(str(e))
    if voice == "supertonic-M1":
        try:
            supertonic_voice.synthesize(text, out_path=out_wav)
        except supertonic_voice.SupertonicError as e:
            raise LongNarrationError(str(e))
        except ValueError as e:
            raise LongNarrationError(str(e))
        return _resample_to_22050_mono(out_wav)
    if voice != "piper":
        raise LongNarrationError(
            "صوت غير معروف: %s (المسموح: piper أو gtts أو "
            "supertonic-M1)" % voice)
    if not os.path.isfile(piper_bin):
        raise LongNarrationError("ثنائي Piper غير موجود: %s" % piper_bin)
    if not os.path.isfile(model):
        raise LongNarrationError("موديل الصوت غير موجود: %s" % model)
    if not text or not text.strip():
        raise LongNarrationError("نص المقطع فارغ")
    try:
        proc = subprocess.run(
            [piper_bin, "--model", model, "--output_file", out_wav],
            input=text, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise LongNarrationError("ثنائي Piper غير موجود: %s" % piper_bin)
    except subprocess.TimeoutExpired:
        raise LongNarrationError(
            "انتهت مهلة تركيب المقطع (%d ثانية): %s"
            % (timeout, text[:40]))
    if proc.returncode != 0:
        raise LongNarrationError(
            "فشل Piper (رمز الخروج %d): %s"
            % (proc.returncode,
               (proc.stderr or proc.stdout or "").strip()[-400:]))
    if not os.path.isfile(out_wav):
        raise LongNarrationError(
            "انتهى Piper دون إنشاء ملف الصوت: %s" % out_wav)
    return out_wav


def apply_atempo(wav_path, factor, work_dir):
    """طبّق سرعة atempo على ملف WAV (1.0 = بلا تغيير)."""
    if abs(factor - 1.0) < 1e-6:
        return wav_path
    if not 0.5 <= factor <= 2.0:
        raise LongNarrationError(
            "معامل السرعة atempo يجب أن يكون بين 0.5 و2.0 (وصل: %s)"
            % factor)
    out = os.path.join(work_dir, os.path.basename(wav_path) + ".atempo.wav")
    _run(["ffmpeg", "-y", "-v", "error", "-i", wav_path,
          "-filter:a", "atempo=%.3f" % factor, out],
         "تطبيق سرعة السرد")
    return out


def concatenate_with_gaps(wav_paths, out_wav, gap=DEFAULT_GAP_SECONDS):
    """ادمج ملفات WAV بفواصل صمت بينها. يرجع مدة الناتج بالثواني."""
    if not wav_paths:
        raise LongNarrationError("لا توجد مقاطع صوتية للدمج")
    if len(wav_paths) == 1:
        shutil.copy2(wav_paths[0], out_wav)
        return probe_duration(out_wav)
    # معدل العينة من أول مقطع (Piper: 22050 هرتز أحادي) لصمت مطابق.
    info = _run(["ffprobe", "-v", "error", "-show_entries",
                 "stream=sample_rate,channels", "-of",
                 "default=noprint_wrappers=1", wav_paths[0]],
                "قراءة خصائص الصوت")
    props = dict(line.split("=", 1) for line in info.stdout.strip().splitlines()
                 if "=" in line)
    rate = props.get("sample_rate", "22050")
    channels = int(props.get("channels", "1"))
    layout = "mono" if channels == 1 else "stereo"
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for p in wav_paths:
        cmd += ["-i", p]
    n_sil = len(wav_paths) - 1
    for _ in range(n_sil):
        cmd += ["-f", "lavfi", "-t", str(gap),
                "-i", "anullsrc=r=%s:cl=%s" % (rate, layout)]
    # ترتيب المدخلات: مقطع0، صمت0، مقطع1، صمت1، مقطع2...
    labels = []
    for i in range(len(wav_paths)):
        labels.append("[%d:a]" % i)
        if i < n_sil:
            labels.append("[%d:a]" % (len(wav_paths) + i))
    filt = "%sconcat=n=%d:v=0:a=1[out]" % ("".join(labels),
                                           len(labels))
    cmd += ["-filter_complex", filt, "-map", "[out]", out_wav]
    _run(cmd, "دمج مقاطع السرد", timeout=600)
    return probe_duration(out_wav)


def synthesize_long(text, out_wav, gap=DEFAULT_GAP_SECONDS, atempo=1.0,
                    piper_bin=PIPER_BIN, model=PIPER_MODEL,
                    work_dir=None, voice="piper"):
    """ركّب نصًا طويلًا إلى WAV واحد بفواصل صمت بين الجمل.

    voice: "piper" (الافتراضي — الراوي الرجل) أو "gtts" أو
    "supertonic-M1" (صوت ثانٍ اختياري). مع supertonic-M1 يُتجاهل
    `atempo` عمدًا: سرعته المدمجة 1.05 أصلًا بإيقاع مقاس
    (~113 كلمة/دقيقة — يعادل Piper عند atempo ‏1.25)، فتمرير
    atempo فوقه كان سيسرّعه بلا قياس. يرجع {"output": مسار WAV، "duration": المدة بالثواني،
    "chunks": [{"text": نص الجملة، "start": بداية النطق،
    "end": نهايته}]} — أزمنة الجمل بدقة بعد الدمج والسرعة.
    """
    if voice not in ("piper", "gtts", "supertonic-M1"):
        raise LongNarrationError(
            "صوت غير معروف: %s (المسموح: piper أو gtts أو "
            "supertonic-M1)" % voice)
    if not text or not text.strip():
        raise LongNarrationError("نص السرد فارغ")
    if gap < 0 or gap > 2.0:
        raise LongNarrationError(
            "فاصل الصمت يجب أن يكون بين 0 و2 ثانية (وصل: %s)" % gap)
    chunks = split_chunks(text)
    if not chunks:
        raise LongNarrationError("نص السرد فارغ بعد التقسيم")
    # مع supertonic-M1 يُتجاهل atempo (سرعته المدمجة 1.05 أصلًا
    # بإيقاع مقاس يعادل Piper عند 1.25 — تمريره فوقها بلا قياس).
    effective_atempo = 1.0 if voice == "supertonic-M1" else atempo
    out_dir = os.path.dirname(os.path.abspath(out_wav))
    os.makedirs(out_dir, exist_ok=True)
    tmp = work_dir or tempfile.mkdtemp(prefix="long-narr-")
    os.makedirs(tmp, exist_ok=True)
    chunk_infos = []
    try:
        wav_paths = []
        for i, chunk_text in enumerate(chunks):
            raw = os.path.join(tmp, "chunk%03d.wav" % i)
            synthesize_chunk(chunk_text, raw, piper_bin, model,
                             voice=voice)
            wav = apply_atempo(raw, effective_atempo, tmp)
            wav_paths.append(wav)
        total = concatenate_with_gaps(wav_paths, out_wav, gap=gap)
        # أزمنة الجمل: تراكمية من مدد المقاطع بعد السرعة + الفواصل
        cursor = 0.0
        for i, chunk_text in enumerate(chunks):
            dur = probe_duration(wav_paths[i])
            chunk_infos.append({"text": chunk_text,
                                "start": round(cursor, 3),
                                "end": round(cursor + dur, 3)})
            cursor += dur + gap
        total = round(total, 3)
    finally:
        if work_dir is None:
            shutil.rmtree(tmp, ignore_errors=True)
    return {"output": out_wav, "duration": total, "chunks": chunk_infos}
