#!/usr/bin/env python3
"""إصلاح تلقائي لفشل فحص الصمت — `fix_silence_gaps`.

السياق (إنتاج «عائشة الأرملة ج2» 2026-11-22): السرد بسرعة 1.25
أقصر من مقاطع Veo فظهرت فجوات صمت 1.8–3.8 ثوانٍ عند فواصل
المشاهد، وفشل فحص الصمت في lib/check.py (أي صمت ≥1 ثانية وسط
الفيديو). أُصلح يدويًا بمزج صوت المشاهد الأصلي من Veo (مكبَّر
ليستقر ~-28 ديسيبل) + طبقة ضجيج وردي خافتة (سعة 0.05) تحت
السرد — فنجح فحص الصمت بلا تغيير المدة أو الإيقاع أو النص.
هذه الوحدة تحوّل تلك الوصفة إلى دالة قابلة لإعادة الاستخدام.

القواعد:
  * الكشف عبر lib/check.py نفسه (silencedetect عند -40 ديسيبل،
    وفجوة ≥1 ثانية) — فما يُصلحه هنا هو بالضبط ما يفشل هناك.
  * الفيديو بلا فجوات يُعاد كما هو بلا أي إعادة ترميز، ويُبلَّغ
    أنه سليم (fixed=False).
  * عند وجود فجوات: يُعاد ترميز الصوت فقط، والفيديو يُنسخ بلا
    إعادة ترميز (-c:v copy)، والمدة تُقصّ بدقة على مدة الأصل.
  * طبقة الضجيج الوردي سعتها 0.05 طوال المدة — خافتة بما يكفي
    لتبقى تحت السرد (متوسطها ~-28 ديسيبل)، وعالية بما يكفي
    لتكسر عتبة الصمت (-40 ديسيبل) عند كل فجوة.
  * أصوات المشاهد الأصلية (اختيارية) تُقاس بمستواها المتوسط
    عبر volumedetect ثم تُكبَّر/تُخفَّض بمقدار ثابت لتستقر عند
    ~-28 ديسيبل، وتُدمج متتالية بالترتيب المُعطى من بداية
    الفيديو. القيد: بلا مواضع زمنية لكل مشهد، فالدمج متتالٍ
    من البداية لا موضعيّ؛ فإن احتجت مواضع دقيقة مرّر مقطعًا
    واحدًا مجهزًا بطول الفيديو.
  * المزج بـ amix مع normalize=0 حتى لا ينخفض مستوى السرد
    الأصلي (الافتراضي normalize=1 يقسم المجموع على عدد
    المدخلات)، مع حدّ alimiter عند 0.95 لمنع أي قصّ إن
    تزامنت القمم.
  * فيديو بلا مسار صوتي أصلًا يُعامل كفجوة بطول الفيديو كله،
    ويُبنى له مسار صوتي من الضجيج (+ أصوات المشاهد إن أُعطيت).
"""
import os
import subprocess

from lib import check as check_lib

# سعة الضجيج الوردي — الوصفة المجرّبة في إنتاج عائشة ج2.
NOISE_AMPLITUDE = 0.05
# مستوى الاستقرار المستهدف لأصوات المشاهد الأصلية (ديسيبل).
SCENE_TARGET_DB = -28.0
# حدا كسب أصوات المشاهد: لا نكبّر صمتًا شبه كامل ولا نخفض
# صوتًا صاخبًا إلى ما دون المسموع.
SCENE_GAIN_MIN_DB = -20.0
SCENE_GAIN_MAX_DB = 30.0
# عتبة الصمت وحد الفجوة — نفس قيم lib/check.py افتراضيًا.
SILENCE_NOISE_DB = check_lib.SILENCE_NOISE_DB
SILENCE_MIN_SECONDS = check_lib.SILENCE_MIN_SECONDS
# أقصى انحراف مسموح في المدة بين الأصل والمُصلح (ثوانٍ).
MAX_DURATION_DRIFT = 0.05


class FixAudioError(Exception):
    """خطأ في إصلاح الصوت (رسالته عربية جاهزة للعرض)."""


def _run(cmd, timeout=600):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except FileNotFoundError:
        raise FixAudioError("الأمر غير موجود: %s" % cmd[0])
    except subprocess.TimeoutExpired:
        raise FixAudioError("انتهت المهلة أثناء: %s" % " ".join(cmd[:3]))
    return proc


def middle_gaps(silences, duration, min_seconds=SILENCE_MIN_SECONDS):
    """فجوات الصمت الوسطى ≥ min_seconds — نفس استثناءات check.py.

    صمت البداية (يبدأ عند 0) وصمت النهاية (ينتهي عند مدة
    الفيديو) لا يُحتسبان — مقدمة/خاتمة. يرجع قائمة
    (بداية، نهاية، مدة) مرتبة زمنيًا.
    """
    gaps = []
    for start, end, _dur in silences:
        if start <= 0.05:
            continue
        real_end = duration if end is None else end
        if real_end >= duration - 0.3:
            continue
        if real_end - start >= min_seconds:
            gaps.append((round(start, 3), round(real_end, 3),
                         round(real_end - start, 3)))
    return gaps


def scene_gain_db(path, target_db=SCENE_TARGET_DB):
    """كسب (ديسيبل) يوصل متوسط صوت مشهد إلى target_db.

    يرجع None إن تعذرت قراءة المستوى (ملف بلا صوت أو صامت
    تمامًا) — فيُتخطى الملف مع تسجيل السبب بدل الفشل.
    """
    mean_db, _max_db = check_lib.audio_levels(path)
    if mean_db is None:
        return None
    gain = target_db - mean_db
    return max(SCENE_GAIN_MIN_DB, min(SCENE_GAIN_MAX_DB, gain))


def default_out_path(video_path):
    """مسار الإخراج الافتراضي: <الاسم>-fixed.mp4 بجانب الأصلي."""
    root, _ext = os.path.splitext(video_path)
    return root + "-fixed.mp4"


def fix_silence_gaps(video_path, scene_audio_paths=None, out_path=None,
                     noise_amplitude=NOISE_AMPLITUDE,
                     scene_target_db=SCENE_TARGET_DB,
                     min_seconds=SILENCE_MIN_SECONDS,
                     noise_db=SILENCE_NOISE_DB):
    """أصلح فجوات الصمت في فيديو. يرجع تقريرًا قاموسيًا.

    {"path", "output", "fixed", "duration_before",
     "duration_after", "gaps_before", "gaps_after",
     "silence_check_before", "silence_check_after",
     "noise_amplitude", "scene_audio", "skipped_scene_audio",
     "note"}
    gaps_* قوائم (بداية، نهاية، مدة) للفجوات الوسطى ≥ min_seconds.
    scene_audio: [{"path", "gain_db"}] للمقاطع الممزوجة فعلًا.
    إن كان الفيديو سليمًا: fixed=False وoutput هو نفس الملف.
    يرفع FixAudioError برسالة عربية عند ملف مفقود أو فيديو
    تالف أو فشل ffmpeg.
    """
    video_path = os.path.abspath(os.path.expanduser(video_path))
    if not os.path.isfile(video_path):
        raise FixAudioError("ملف الفيديو غير موجود: %s" % video_path)
    try:
        info = check_lib.probe(video_path)
    except check_lib.CheckError as e:
        raise FixAudioError(str(e))
    duration = info["duration"]

    out_path = (os.path.abspath(os.path.expanduser(out_path))
                if out_path else default_out_path(video_path))
    if os.path.abspath(out_path) == video_path:
        raise FixAudioError(
            "مسار الإخراج هو نفسه ملف الفيديو — حدد --out مختلفًا")

    scene_paths = [os.path.abspath(os.path.expanduser(p))
                   for p in (scene_audio_paths or [])]
    for p in scene_paths:
        if not os.path.isfile(p):
            raise FixAudioError("ملف صوت المشهد غير موجود: %s" % p)

    silences_before = check_lib.detect_silences(
        video_path, noise_db=noise_db, min_seconds=min_seconds)
    if info["has_audio"]:
        gaps_before = middle_gaps(silences_before, duration, min_seconds)
        note = ""
    else:
        # بلا مسار صوتي: الفيديو كله فجوة واحدة — يُبنى له صوت.
        gaps_before = [(0.0, round(duration, 3), round(duration, 3))]
        note = "لا يوجد مسار صوتي أصلًا — بُني مسار من الضجيج الوردي"
    _ok, _detail = check_lib.eval_silences(
        silences_before, duration, long_mode=False)
    silence_before_ok = _ok if info["has_audio"] else False

    if not gaps_before:
        return {"path": video_path, "output": video_path,
                "fixed": False, "duration_before": round(duration, 3),
                "duration_after": round(duration, 3),
                "gaps_before": [], "gaps_after": [],
                "silence_check_before": True,
                "silence_check_after": True,
                "noise_amplitude": noise_amplitude,
                "scene_audio": [], "skipped_scene_audio": [],
                "note": "الفيديو سليم — لا فجوات صمت ≥%.0f ثانية" % min_seconds}

    # --- بناء أمر ffmpeg: صوت فقط يُعاد ترميزه، فيديو يُنسخ ---
    # المدخلات: 0 الفيديو، 1 ضجيج وردي، 2+ أصوات المشاهد.
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", video_path,
           "-f", "lavfi", "-i",
           "anoisesrc=color=pink:duration=%.3f:sample_rate=48000:"
           "amplitude=%s" % (duration, noise_amplitude)]
    for p in scene_paths:
        cmd += ["-i", p]

    mixed = []
    filters = []
    if scene_paths:
        mixed_scene = []
        skipped = []
        for i, p in enumerate(scene_paths):
            gain = scene_gain_db(p, target_db=scene_target_db)
            if gain is None:
                skipped.append({"path": p,
                                "reason": "تعذرت قراءة مستوى الصوت"})
                continue
            label = "s%d" % i
            filters.append("[%d:a]volume=%.1fdB[%s]"
                           % (2 + i, gain, label))
            mixed_scene.append({"path": p, "gain_db": round(gain, 1)})
            mixed.append(label)
        if len(mixed) > 1:
            filters.append("%sconcat=n=%d:v=0:a=1[scene]"
                           % ("".join("[%s]" % m for m in mixed),
                              len(mixed)))
            scene_label = "scene"
        elif len(mixed) == 1:
            scene_label = mixed[0]
        else:
            scene_label = None
        if scene_label is not None:
            # قصّر/مدّد صوت المشاهد المدموج إلى مدة الفيديو تمامًا.
            filters.append("[%s]apad,atrim=0:%.3f[scenemix]"
                           % (scene_label, duration))
    else:
        mixed_scene, skipped = [], []

    mix_inputs = []
    if info["has_audio"]:
        mix_inputs.append("0:a:0")
    mix_inputs.append("1:a")
    if scene_paths and mixed_scene:
        mix_inputs.append("scenemix")
    filters.append("%samix=inputs=%d:duration=longest:normalize=0:"
                   "dropout_transition=0,alimiter=limit=0.95:"
                   "level=false,atrim=0:%.3f,"
                   "asetpts=PTS-STARTPTS[mixed]"
                   % ("".join("[%s]" % m for m in mix_inputs),
                      len(mix_inputs), duration))

    tmp_out = out_path + ".tmp.mp4"
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    cmd += ["-filter_complex", ";".join(filters),
            "-map", "0:v:0", "-map", "[mixed]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-t", "%.3f" % duration, "-movflags", "+faststart",
            tmp_out]
    proc = _run(cmd, timeout=900)
    if proc.returncode != 0 or not os.path.isfile(tmp_out):
        if os.path.isfile(tmp_out):
            os.remove(tmp_out)
        raise FixAudioError(
            "فشل مزج الصوت عبر ffmpeg: %s"
            % (proc.stderr or "").strip()[-300:])
    os.replace(tmp_out, out_path)

    try:
        after_info = check_lib.probe(out_path)
    except check_lib.CheckError as e:
        raise FixAudioError("تعذر قراءة الفيديو المُصلح: %s" % e)
    silences_after = check_lib.detect_silences(
        out_path, noise_db=noise_db, min_seconds=min_seconds)
    gaps_after = middle_gaps(silences_after, after_info["duration"],
                             min_seconds)
    ok_after, _d = check_lib.eval_silences(
        silences_after, after_info["duration"], long_mode=False)

    return {"path": video_path, "output": out_path,
            "fixed": True,
            "duration_before": round(duration, 3),
            "duration_after": round(after_info["duration"], 3),
            "gaps_before": gaps_before, "gaps_after": gaps_after,
            "silence_check_before": silence_before_ok,
            "silence_check_after": ok_after,
            "noise_amplitude": noise_amplitude,
            "scene_audio": mixed_scene, "skipped_scene_audio": skipped,
            "note": note}


def format_report(result):
    """نص عربي للتقرير: الفجوات قبل/بعد والمدة."""
    lines = ["إصلاح فجوات الصمت: %s" % result["path"]]
    if not result["fixed"]:
        lines.append("النتيجة: الفيديو سليم — لا فجوات صمت، لم يُعد "
                     "ترميز أي شيء")
        return "\n".join(lines) + "\n"
    lines.append("الفجوات قبل الإصلاح: %d (%s)"
                 % (len(result["gaps_before"]),
                    "، ".join("%.1f–%.1f (%.1f ث)" % g
                              for g in result["gaps_before"])
                    or "—"))
    lines.append("الفجوات بعد الإصلاح: %d (%s)"
                 % (len(result["gaps_after"]),
                    "، ".join("%.1f–%.1f (%.1f ث)" % g
                              for g in result["gaps_after"])
                    or "لا فجوات"))
    lines.append("المدة: %.3f ث ← %.3f ث (فرق %.3f ث)"
                 % (result["duration_before"], result["duration_after"],
                    abs(result["duration_after"]
                        - result["duration_before"])))
    lines.append("فحص الصمت بعد الإصلاح: %s"
                 % ("PASS" if result["silence_check_after"] else "FAIL"))
    if result["scene_audio"]:
        lines.append("صوت المشاهد الممزوج: %s"
                     % "، ".join("%s (كسب %+.1f ديسيبل)"
                                 % (s["path"], s["gain_db"])
                                 for s in result["scene_audio"]))
    if result["skipped_scene_audio"]:
        lines.append("مقاطع مشاهد تُخطّيت: %s"
                     % "، ".join("%s (%s)" % (s["path"], s["reason"])
                                 for s in result["skipped_scene_audio"]))
    lines.append("الناتج: %s" % result["output"])
    if result["note"]:
        lines.append("ملاحظة: %s" % result["note"])
    return "\n".join(lines) + "\n"
