#!/usr/bin/env python3
"""وظيفة الأفاتار الناطق (LongCat) — جولة v0.1.38 (بند 1).

مخطط الوظيفة (JSON):
{
  "prompt": "A middle-aged Egyptian storyteller, warm and calm...",
  "cond_image": "portraits/storyteller.jpg",
  "cond_audio": {"person1": "narration/scene1.wav",
                 "person2": "narration/scene2.wav"},
  "audio_type": "para",
  "settings": {"audio_cfg": 4.0, "full_steps": false,
               "aspect_policy": "native", "profile": "t4x2-int8"},
  "audio": {"kind": "narration"}
}

قواعد التحقق (validate_job):
- prompt سلسلة غير فارغة.
- cond_image موجود + امتداد صورة (jpg/jpeg/png/webp).
- cond_audio.person1 موجود + مدته ≤ 300ث (دالة _audio_duration
  الخاصة بالوظيفة عبر ffprobe — فـ check_lib.probe يرفض ملفًا
  بلا مسار فيديو).
- person2 يستلزم audio_type؛ وaudio_type ∈ {para, add}؛
  وpara يستلزم |مدة1 − مدة2| ≤ 0.1ث.
- settings تُتحقق عبر avatar_settings.
- audio.kind يجب أن يكون "narration" (طبقة المخطط من البند 4).

قاعدة «الصوت النظيف فقط» (البند 4، طبقة القياس):
check_audio_clean يرفض فقط إذا تحققت الشروط الثلاثة معًا:
المدة ≥ 15ث، ونسبة الصمت صفر تمامًا (لا صمت ≥ 0.5ث عند
-40dB)، ومتوسط المستوى > -30dB (صوت مستمر صاخب). الملفات
القصيرة لا تُقاس أبدًا (سرد Piper بسرعة 1.25 لا يترك صمتًا
قابلًا للقياس في المقاطع القصيرة).
"""
import json
import os
import subprocess

from lib import avatar_prompt as prompt_lib
from lib import avatar_settings as settings_lib
from lib import check as check_lib

# أقصى مدة صوت لشخص واحد (ثوانٍ).
MAX_AUDIO_SECONDS = 300.0
# حدا قاعدة «الصوت النظيف فقط».
CLEAN_MIN_SECONDS = 15.0
CLEAN_MEAN_DB_MAX = -30.0
CLEAN_SILENCE_MIN_SECONDS = 0.5

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
AUDIO_TYPES = ("para", "add")
_PARA_MAX_DIFF_SECONDS = 0.1


class AvatarJobError(Exception):
    """خطأ وظيفة أفاتار — رسالة عربية."""


def _audio_duration(path):
    """مدة ملف صوتي (ثوانٍ) عبر ffprobe -show_format.

    دالة الوظيفة الخاصة (قابلة للترقيع في الاختبارات).
    """
    if not os.path.isfile(path):
        raise AvatarJobError("ملف الصوت غير موجود: %s" % path)
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-of", "json",
             path],
            capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        raise AvatarJobError("الأمر غير موجود: ffprobe")
    except subprocess.TimeoutExpired:
        raise AvatarJobError("انتهت المهلة أثناء قراءة: %s" % path)
    if proc.returncode != 0:
        raise AvatarJobError(
            "تعذرت قراءة الصوت عبر ffprobe: %s"
            % (proc.stderr or "").strip()[-200:])
    try:
        duration = float(json.loads(proc.stdout or "{}")
                         .get("format", {}).get("duration") or 0)
    except (ValueError, TypeError):
        duration = 0.0
    if duration <= 0:
        raise AvatarJobError("مدة الصوت غير مقروءة في: %s" % path)
    return duration


def _resolve_path(value, base_dir, label):
    if not isinstance(value, str) or not value.strip():
        raise AvatarJobError("مسار %s فارغ" % label)
    value = value.strip()
    if base_dir and not os.path.isabs(value):
        value = os.path.join(base_dir, value)
    return os.path.abspath(os.path.expanduser(value))


def validate_job(data, base_dir=None):
    """تحقق من وظيفة أفاتار وأرجع قاموسًا مُطبَّعًا.

    data: قاموس الوظيفة؛ base_dir: مجلد تُحلّ إليه المسارات
    النسبية (افتراضيًا الدليل الحالي). يرفع AvatarJobError
    برسالة عربية عند أي مخالفة.
    """
    if not isinstance(data, dict):
        raise AvatarJobError("الوظيفة يجب أن تكون قاموسًا")
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise AvatarJobError("برومبت الوظيفة فارغ")
    image = _resolve_path(data.get("cond_image"), base_dir, "الصورة")
    if not os.path.isfile(image):
        raise AvatarJobError("صورة الوظيفة غير موجودة: %s" % image)
    if os.path.splitext(image)[1].lower() not in IMAGE_EXTENSIONS:
        raise AvatarJobError(
            "امتداد الصورة غير مدعوم: %s (الصالح: %s)"
            % (image, "، ".join(IMAGE_EXTENSIONS)))
    cond_audio = data.get("cond_audio")
    if not isinstance(cond_audio, dict) or not cond_audio.get("person1"):
        raise AvatarJobError(
            "صوت الوظيفة يجب أن يحوي person1 على الأقل")
    audio1 = _resolve_path(cond_audio.get("person1"), base_dir,
                           "صوت person1")
    if not os.path.isfile(audio1):
        raise AvatarJobError(
            "صوت person1 غير موجود: %s" % audio1)
    duration1 = _audio_duration(audio1)
    if duration1 > MAX_AUDIO_SECONDS:
        raise AvatarJobError(
            "صوت person1 أطول من %d ثانية (المدة: %.1f)"
            % (MAX_AUDIO_SECONDS, duration1))
    audio_type = data.get("audio_type")
    audio2 = None
    duration2 = None
    if cond_audio.get("person2"):
        if not audio_type:
            raise AvatarJobError(
                "شخصان في الوظيفة يستلزمان audio_type "
                "(para أو add)")
        audio2 = _resolve_path(cond_audio.get("person2"), base_dir,
                               "صوت person2")
        if not os.path.isfile(audio2):
            raise AvatarJobError(
                "صوت person2 غير موجود: %s" % audio2)
        duration2 = _audio_duration(audio2)
        if duration2 > MAX_AUDIO_SECONDS:
            raise AvatarJobError(
                "صوت person2 أطول من %d ثانية (المدة: %.1f)"
                % (MAX_AUDIO_SECONDS, duration2))
    if audio_type is None:
        audio_type = "para"
    if audio_type not in AUDIO_TYPES:
        raise AvatarJobError(
            "نوع الصوت غير معروف: %s (الصالح: %s)"
            % (audio_type, "، ".join(AUDIO_TYPES)))
    if audio2 is not None and audio_type == "para":
        if abs(duration1 - duration2) > _PARA_MAX_DIFF_SECONDS:
            raise AvatarJobError(
                "نوع para يستلزم مدتين متطابقتين (±0.1ث): "
                "%.2f مقابل %.2f" % (duration1, duration2))
    audio = data.get("audio") or {}
    if not isinstance(audio, dict):
        raise AvatarJobError("حقل audio يجب أن يكون قاموسًا")
    kind = audio.get("kind", "narration")
    if kind != "narration":
        raise AvatarJobError(
            "نوع الصوت يجب أن يكون narration (القيمة: %s)" % (kind,))
    settings = data.get("settings") or {}
    if not isinstance(settings, dict):
        raise AvatarJobError("إعدادات الوظيفة يجب أن تكون قاموسًا")
    try:
        resolved = settings_lib.resolve_avatar_settings(
            overrides=settings)
    except settings_lib.AvatarSettingsError as e:
        raise AvatarJobError(str(e))
    return {"prompt": prompt.strip(),
            "cond_image": image,
            "cond_audio": {"person1": audio1,
                           **({"person2": audio2}
                              if audio2 else {})},
            "audio_type": audio_type,
            "settings": resolved,
            "audio": {"kind": kind},
            "durations": {"person1": round(duration1, 2),
                          **({"person2": round(duration2, 2)}
                             if duration2 is not None else {})}}


def load_job(path):
    """اقرأ وظيفة من ملف JSON وتحقق منها؛ ارجع القاموس المُطبَّع."""
    if not os.path.isfile(path):
        raise AvatarJobError("ملف الوظيفة غير موجود: %s" % path)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except ValueError as e:
        raise AvatarJobError(
            "ملف الوظيفة ليس JSON صالحًا: %s (%s)" % (path, e))
    base_dir = os.path.dirname(os.path.abspath(path))
    return validate_job(data, base_dir=base_dir)


def save_job(job, path):
    """اكتب وظيفة (مُتحقق منها) JSON؛ ارجع المسار."""
    job = validate_job(job)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(job, fh, ensure_ascii=False, indent=2)
    return path


def job_template(scene_type="narration"):
    """وظيفة مثال كاملة (برومبتها من باني برومبت الأداء).

    المسارات أمثلة يملؤها المستخدم — الوظيفة المثال نفسها
    لا تُتحقق (ملفاتها غير موجودة).
    """
    prompt = prompt_lib.build_performance_prompt(
        scene_type=scene_type)
    return {"prompt": prompt,
            "cond_image": "portraits/storyteller.jpg",
            "cond_audio": {"person1": "narration/scene1.wav"},
            "audio_type": "para",
            "settings": {"audio_cfg": 4.0, "full_steps": False,
                         "aspect_policy": "native",
                         "profile": "t4x2-int8"},
            "audio": {"kind": "narration"}}


def check_audio_clean(audio_path):
    """افحص «نظافة» ملف صوت (قاعدة البند 4).

    يُرفض (ok=False) فقط إذا تحققت الشروط الثلاثة معًا:
    المدة ≥ 15ث، ونسبة الصمت صفر (لا صمت ≥ 0.5ث عند -40dB)،
    ومتوسط المستوى > -30dB. يرجع {"ok", "detail",
    "duration_seconds", "silence_ratio", "mean_db"}.
    """
    if not os.path.isfile(audio_path):
        raise AvatarJobError("ملف الصوت غير موجود: %s" % audio_path)
    duration = _audio_duration(audio_path)
    try:
        silences = check_lib.detect_silences(
            audio_path, min_seconds=CLEAN_SILENCE_MIN_SECONDS)
    except check_lib.CheckError as e:
        raise AvatarJobError(str(e))
    silence_total = 0.0
    for start, end, dur in silences:
        if dur is not None:
            silence_total += dur
        elif end is not None:
            silence_total += max(0.0, end - start)
        else:
            silence_total += max(0.0, duration - start)
    silence_ratio = silence_total / duration if duration else 0.0
    mean_db, _max_db = check_lib.audio_levels(audio_path)
    if mean_db is None:
        raise AvatarJobError(
            "لا يوجد مسار صوتي مقروء في: %s" % audio_path)
    detail = ("المدة %.1fث، نسبة الصمت %.3f، متوسط %.1fdB"
              % (duration, silence_ratio, mean_db))
    if (duration >= CLEAN_MIN_SECONDS and silence_ratio == 0.0
            and mean_db > CLEAN_MEAN_DB_MAX):
        return {"ok": False,
                "detail": "صوت مستمر بلا أي صمت (ممزوج؟) — %s"
                          % detail,
                "duration_seconds": round(duration, 2),
                "silence_ratio": round(silence_ratio, 3),
                "mean_db": mean_db}
    return {"ok": True, "detail": detail,
            "duration_seconds": round(duration, 2),
            "silence_ratio": round(silence_ratio, 3),
            "mean_db": mean_db}
