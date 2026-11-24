#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""صوت ثانٍ اختياري — gTTS (Google Text-to-Speech، مجاني بلا مفتاح).

الراوي الافتراضي يبقى Piper Kareem (رجل) دائمًا — هذا صوت ثانٍ
فقط عبر `--voice gtts` في `long-narration` و`long-video` (سرد
المقدمة/الخاتمة والفصول النصية؛ فصول مشاريع OpenMontage تستخدم
سردها المُجهَّز أصلًا).

التنفيذ: gTTS مثبّت في بيئة studio الخاصة `.venv-gtts`
(أُنشئت بـ `python3 -m venv .venv-gtts && pip install gtts` —
راجع setup.sh)؛ يُستدعى بمفسّر تلك البيئة ثم يُحوَّل mp3 إلى
WAV ‏22050 هرتز أحادي عبر ffmpeg ليتطابق مع مخرجات Piper.
يعمل من هذه الشبكة فعلًا (اتحقق 2026-11-21: عينة عربية 7.3 ثوانٍ
بمستوى صوت حقيقي). إن حجبته الشبكة لاحقًا، يفشل برسالة واضحة
ولا يمسّ الراوي الافتراضي.
"""
import os
import subprocess
import tempfile

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GTTS_VENV_PYTHON = os.path.join(STUDIO_DIR, ".venv-gtts", "bin", "python")


class GttsError(Exception):
    """خطأ في توليد الصوت بـgTTS (رسالته عربية)."""


def _run(cmd, what, timeout=180):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except FileNotFoundError:
        raise GttsError("%s: الأمر غير موجود: %s" % (what, cmd[0]))
    except subprocess.TimeoutExpired:
        raise GttsError("%s: انتهت المهلة (%d ثانية)" % (what, timeout))
    if proc.returncode != 0:
        raise GttsError("%s فشل (رمز الخروج %d): %s"
                        % (what, proc.returncode,
                           (proc.stderr or proc.stdout or "").strip()[-400:]))
    return proc


def convert_mp3_to_wav(mp3_path, wav_path):
    """حوّل mp3 إلى WAV ‏22050 هرتز أحادي (مثل مخرجات Piper)."""
    if not os.path.isfile(mp3_path):
        raise GttsError("ملف mp3 غير موجود: %s" % mp3_path)
    _run(["ffmpeg", "-y", "-v", "error", "-i", mp3_path,
          "-ar", "22050", "-ac", "1", wav_path], "تحويل mp3 إلى WAV")
    if not os.path.isfile(wav_path) or os.path.getsize(wav_path) == 0:
        raise GttsError("انتهى التحويل دون إنشاء WAV: %s" % wav_path)
    return wav_path


def synthesize_gtts_chunk(text, out_wav, lang="ar",
                          venv_python=GTTS_VENV_PYTHON, timeout=120):
    """ركّب مقطعًا واحدًا بـgTTS إلى WAV. يرفع GttsError عند الفشل."""
    if not text or not text.strip():
        raise GttsError("نص المقطع فارغ")
    if not os.path.isfile(venv_python):
        raise GttsError(
            "بيئة gTTS غير موجودة (%s) — أنشئها بـ:\n"
            "  python3 -m venv .venv-gtts && "
            ".venv-gtts/bin/pip install gtts\n"
            "أو شغّل setup.sh" % venv_python)
    tmp = tempfile.mkdtemp(prefix="gtts-")
    try:
        text_path = os.path.join(tmp, "text.txt")
        mp3_path = os.path.join(tmp, "chunk.mp3")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(text.strip())
        script = ("from gtts import gTTS\n"
                  "import sys\n"
                  "gTTS(text=open(sys.argv[1], encoding='utf-8').read(),"
                  " lang='ar').save(sys.argv[2])\n")
        _run([venv_python, "-c", script, text_path, mp3_path],
             "توليد الصوت بـgTTS", timeout=timeout)
        convert_mp3_to_wav(mp3_path, out_wav)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    return out_wav
