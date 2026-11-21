#!/usr/bin/env python3
"""تحليل فيديو مرجعي (هندسة عكسية: هوك/إيقاع/ختام) — تحليل خاص فقط.

الخطوات: بيانات الفيديو عبر `yt-dlp --dump-json`، ثم تنزيل الصوت
فقط، ثم تفريغه بـ faster-whisper (من بيئة `.venv-whisper` — إما
داخل العملية نفسها لو شُغّل الأمر منها، أو عبر استدعاء بايثون
البيئة كعملية فرعية)، ثم تحليل تلقائي: نص أول 10 ثوانٍ (الهوك)،
سرعة السرد (كلمة/دقيقة)، وجود سؤال ختامي.

تنبيه حقوق وشروط منصات — اقرأ قبل الاستخدام:
  هذا التحليل للاستخدام الخاص فقط (فهم أسلوب فيديو منافس)، وليس
  لإعادة نشر المحتوى أو توزيعه أو نسخه. شروط استخدام يوتيوب تمنع
  تنزيل الفيديوهات؛ لذلك يُنزَّل الصوت إلى مجلد مؤقت ويُحذف فور
  انتهاء التحليل، ولا يُحفظ أي صوت أو فيديو ولا يُشارك. استخدم
  الأمر على فيديوهات عامة متاحة فقط، واحترم حقوق صانعيها.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile

from lib import whisper_captions


class RefError(Exception):
    pass


COPYRIGHT_NOTICE = (
    "تنبيه حقوق: هذا التحليل للاستخدام الخاص فقط — لفهم أسلوب الفيديو "
    "(هوك/إيقاع/ختام) وليس لإعادة نشر المحتوى أو توزيعه أو نسخه. "
    "شروط استخدام يوتيوب تمنع تنزيل الفيديوهات؛ الصوت المنزّل يُحذف "
    "فور انتهاء التحليل ولا يُحفظ ولا يُشارك."
)

YTDLP = "yt-dlp"
# بايثون بيئة faster-whisper الخاصة بالمشروع (انظر WHISPER-TEST.md)
VENV_PYTHON = os.path.expanduser(
    "~/workspace/studio/.venv-whisper/bin/python")

YOUTUBE_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?[^#]*v=|shorts/|embed/|live/)|"
    r"youtu\.be/)([A-Za-z0-9_-]{6,})")


def video_id_from_url(url):
    """يستخرج معرّف فيديو يوتيوب من الرابط، أو None لو ليس يوتيوب."""
    m = YOUTUBE_RE.search(url or "")
    return m.group(1) if m else None


def _run(cmd, timeout):
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except FileNotFoundError:
        raise RefError("أمر %s غير موجود في PATH — ثبّته أولًا"
                       % cmd[0])
    except subprocess.TimeoutExpired:
        raise RefError("انتهت المهلة أثناء تشغيل: %s" % " ".join(cmd))


def fetch_metadata(url, timeout=120):
    """بيانات الفيديو عبر yt-dlp بلا تنزيل. يرجع قاموسًا مختصرًا."""
    if shutil.which(YTDLP) is None:
        raise RefError("أمر yt-dlp غير مثبّت — ثبّته بـ "
                       "`pip install yt-dlp`")
    r = _run([YTDLP, "--dump-json", "--no-download", "--no-warnings",
              url], timeout)
    if r.returncode != 0 or not r.stdout.strip():
        raise RefError("تعذر جلب بيانات الفيديو: %s"
                       % (r.stderr.strip() or r.stdout.strip())[:400])
    try:
        data = json.loads(r.stdout)
    except ValueError as e:
        raise RefError("رد yt-dlp ليس JSON صالحًا: %s" % e)
    vid = video_id_from_url(url)
    return {
        "id": data.get("id") or vid,
        "url": url,
        "title": data.get("title") or "",
        "uploader": data.get("uploader") or data.get("channel") or "",
        "duration_seconds": data.get("duration"),
        "view_count": data.get("view_count"),
        "like_count": data.get("like_count"),
        "upload_date": data.get("upload_date") or "",
    }


def download_audio(url, tmpdir, timeout=300):
    """ينزّل الصوت فقط (wav) إلى tmpdir. يرجع مسار ملف الصوت."""
    out_tmpl = os.path.join(tmpdir, "audio.%(ext)s")
    r = _run([YTDLP, "-x", "--audio-format", "wav",
              "--audio-quality", "0",
              "-o", out_tmpl, "--no-warnings", url], timeout)
    if r.returncode != 0:
        raise RefError("تعذر تنزيل صوت الفيديو: %s"
                       % (r.stderr.strip() or r.stdout.strip())[:400])
    for name in os.listdir(tmpdir):
        if name.startswith("audio.") and name.endswith(".wav"):
            return os.path.join(tmpdir, name)
    raise RefError("اكتمل التنزيل لكن لم يُعثر على ملف wav في %s"
                   % tmpdir)


def transcribe_via_venv(audio_path, model="small", timeout=600):
    """تفريغ عبر بايثون بيئة .venv-whisper كعملية فرعية.

    يُستخدم حين يعمل studio من بايثون النظام (بلا faster-whisper).
    يرجع (كلمات، نص كامل) بنفس صيغة whisper_captions.
    """
    if not os.path.isfile(VENV_PYTHON):
        raise RefError("بيئة faster-whisper غير موجودة: %s — راجع "
                       "WHISPER-TEST.md" % VENV_PYTHON)
    code = (
        "import json, sys; sys.path.insert(0, %r); "
        "from lib import whisper_captions; "
        "words, text = whisper_captions.transcribe_words("
        "sys.argv[1], model=sys.argv[2]); "
        "print(json.dumps({'words': words, 'text': text}, "
        "ensure_ascii=False))"
        % os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    r = _run([VENV_PYTHON, "-c", code, audio_path, model], timeout)
    if r.returncode != 0:
        raise RefError("فشل التفريغ عبر .venv-whisper: %s"
                       % (r.stderr.strip() or r.stdout.strip())[:400])
    try:
        data = json.loads(r.stdout)
    except ValueError as e:
        raise RefError("رد التفريغ ليس JSON صالحًا: %s" % e)
    return data["words"], data["text"]


def transcribe_audio(audio_path, model="small"):
    """تفريغ صوت: داخل العملية إن توفر faster-whisper، وإلا عبر
    بيئة .venv-whisper. يرفع RefError لو تعذّر الاثنان."""
    try:
        return whisper_captions.transcribe_words(audio_path, model=model)
    except whisper_captions.WhisperError:
        return transcribe_via_venv(audio_path, model=model)


def analyze_words(words, duration_seconds):
    """تحليل تلقائي من كلمات whisper الموقّتة.

    يرجع: نص الهوك (أول 10 ثوانٍ)، عدد الكلمات، سرعة السرد
    (كلمة/دقيقة)، نص الختام (آخر 10 ثوانٍ)، وهل فيه سؤال.
    """
    texts = [(w.get("w") or w.get("word") or "").strip()
             for w in words]
    texts = [t for t in texts if t]
    hook = " ".join(w.get("w") or w.get("word") or ""
                    for w in words
                    if float(w["start"]) < 10).strip()
    tail_start = max(0.0, (duration_seconds or 0) - 10)
    ending = " ".join(w.get("w") or w.get("word") or ""
                      for w in words
                      if float(w["start"]) >= tail_start).strip()
    minutes = (duration_seconds or 0) / 60.0
    wpm = round(len(texts) / minutes, 1) if minutes > 0 else None
    return {
        "word_count": len(texts),
        "words_per_minute": wpm,
        "hook_first_10s": hook,
        "ending_last_10s": ending,
        "ending_has_question": ("؟" in ending or "?" in ending),
        "transcript": " ".join(texts),
    }


def analyze_reference(url, model="small", keep_audio=False):
    """التحليل الكامل: بيانات + صوت + تفريغ + مقاييس.

    يرجع قاموس النتيجة (يُحفظ JSON في runs/ref-<id>.json).
    الصوت المنزّل يُحذف دائمًا بعد التحليل إلا مع keep_audio
    (للتشخيص فقط — لا يُستخدم في التشغيل العادي).
    """
    print(COPYRIGHT_NOTICE)
    meta = fetch_metadata(url)
    result = {"notice": COPYRIGHT_NOTICE, "video": meta,
              "transcription": None, "analysis": None}
    tmpdir = tempfile.mkdtemp(prefix="studio-ref-")
    try:
        audio = download_audio(url, tmpdir)
        try:
            words, text = transcribe_audio(audio, model=model)
        except RefError as e:
            result["transcription"] = {"status": "skipped",
                                       "reason": str(e)}
            print("تخطّي التفريغ: %s" % e)
            return result
        result["transcription"] = {"status": "ok", "model": model,
                                   "text": text}
        result["analysis"] = analyze_words(
            words, meta.get("duration_seconds"))
        return result
    finally:
        if not keep_audio:
            shutil.rmtree(tmpdir, ignore_errors=True)
