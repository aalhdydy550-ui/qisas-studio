#!/usr/bin/env python3
"""تجهيز أصول مشروع OpenMontage موجود لاستخدامها في studio.

لا يعيد تشغيل خط إنتاج OpenMontage كاملًا (بطيء ومكلف)؛ بل يتحقق من
مشروع موجود وينسخ أصوله الجاهزة (صور + سرد + كتابة) إلى مجلد تشغيل
studio. إن لم يوجد المشروع أو نقصت أصوله، يفشل برسالة واضحة.
"""
import json
import os
import shutil


class StageError(Exception):
    pass


def _validate_project_name(name):
    """تحقق من اسم مشروع واحد قبل ضمّه إلى مسار projects/.

    نفس منطق studio.validate_run_component (منسوخ هنا لأن استيراد
    studio من هذه الوحدة يخلق استيرادًا دائريًا: studio يستورد
    openmontage_stage). يرفض فواصل المسارات (`/` أو `\`)، أو `..`،
    أو حرف NUL، أو البدء بنقطة — بنفس رسائل ValueError العربية.
    """
    what = "اسم المشروع"
    if not isinstance(name, str) or not name:
        raise ValueError("%s غير صالح: قيمة فارغة" % what)
    if "\x00" in name:
        raise ValueError("%s غير صالح: يحوي حرف NUL" % what)
    if name.startswith("."):
        raise ValueError("%s غير صالح: يبدأ بنقطة" % what)
    if "/" in name or "\\" in name:
        raise ValueError("%s غير صالح: يحوي فاصل مسار" % what)
    if ".." in name:
        raise ValueError("%s غير صالح: يحوي '..'" % what)
    return name


def find_project(openmontage_root, name):
    _validate_project_name(name)
    path = os.path.join(os.path.expanduser(openmontage_root),
                        "projects", name)
    if not os.path.isdir(path):
        raise StageError("مشروع OpenMontage غير موجود: %s" % path)
    return path


def _natural_key(name):
    """مفتاح فرز طبيعي: scene2 قبل scene10 (الفرز الأبجدي يضعهما بالعكس)."""
    import re
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]


def load_script(project_path):
    """يرجع (نص الهوك، نص السيناريو الكامل)."""
    p = os.path.join(project_path, "artifacts", "script.json")
    if not os.path.isfile(p):
        raise StageError("ملف السيناريو غير موجود: %s" % p)
    try:
        with open(p, encoding="utf-8") as f:
            script = json.load(f)
    except (ValueError, OSError) as e:
        raise StageError("ملف السيناريو تالف أو لا يُقرأ (%s): %s" % (p, e))
    if not isinstance(script, dict):
        raise StageError("بنية ملف السيناريو غير متوقعة: %s" % p)
    sections = script.get("sections", [])
    hook = ""
    full = []
    for s in sections:
        text = (s.get("text") or "").strip()
        if text:
            full.append(text)
        if s.get("label") == "Hook" and text:
            hook = text
    if not hook and full:
        hook = full[0]
    return hook, "\n".join(full)


def build_phrases(captions_path):
    """يحوّل كلمات captions.json (مع pageBreakAfter) إلى عبارات زمنية."""
    try:
        with open(captions_path, encoding="utf-8") as f:
            words = json.load(f)
    except (ValueError, OSError) as e:
        raise StageError("ملف الكتابة تالف أو لا يُقرأ (%s): %s"
                         % (captions_path, e))
    if not isinstance(words, list):
        raise StageError("بنية ملف الكتابة غير متوقعة (ليست قائمة): %s"
                         % captions_path)
    for w in words:
        if (not isinstance(w, dict)
                or not all(k in w for k in ("word", "startMs", "endMs"))):
            raise StageError("كلمة ناقصة الحقول في ملف الكتابة: %s"
                             % captions_path)
    phrases, cur = [], []
    for w in words:
        cur.append(w)
        if w.get("pageBreakAfter"):
            phrases.append(cur)
            cur = []
    if cur:
        phrases.append(cur)
    out = []
    for p in phrases:
        out.append({
            "start": p[0]["startMs"] / 1000.0,
            "end": p[-1]["endMs"] / 1000.0,
            "text": " ".join(w["word"] for w in p),
        })
    return out


def stage(project_path, run_dir, image_clip_seconds=5):
    """ينسخ الأصول إلى run_dir/assets ويرجع قاموس البيان (manifest)."""
    artifacts = os.path.join(project_path, "artifacts")
    img_src = os.path.join(project_path, "assets", "images")
    aud_src = os.path.join(project_path, "assets", "audio")
    if not os.path.isdir(img_src):
        raise StageError("مجلد الصور غير موجود: %s" % img_src)
    images = sorted((f for f in os.listdir(img_src)
                     if f.lower().endswith((".jpg", ".jpeg", ".png"))),
                    key=_natural_key)
    if not images:
        raise StageError("لا توجد صور في: %s" % img_src)
    narration = None
    for cand in ("narration-full.wav", "narration-concat.wav"):
        p = os.path.join(aud_src, cand)
        if os.path.isfile(p):
            narration = p
            break
    if narration is None:
        raise StageError("ملف السرد الكامل غير موجود في: %s" % aud_src)
    captions_path = os.path.join(artifacts, "captions.json")
    if not os.path.isfile(captions_path):
        raise StageError("ملف الكتابة غير موجود: %s" % captions_path)

    assets_dir = os.path.join(run_dir, "assets")
    img_dst = os.path.join(assets_dir, "images")
    aud_dst = os.path.join(assets_dir, "audio")
    os.makedirs(img_dst, exist_ok=True)
    os.makedirs(aud_dst, exist_ok=True)
    # إصلاح اختبار اختراق 2026-11-22 (M1): copy2 كان يتبع الروابط
    # الرمزية فينسخ ملفًا خارج المشروع إلى الأصول — كل مصدر
    # يُحلّ داخل مجلد مصدره أولًا ويُرفض الهارب.
    from lib.paths import resolve_inside

    def _copy_inside(src_dir, src, dst):
        try:
            real = resolve_inside(src_dir, src, "ملف أصل المشروع")
        except ValueError as e:
            raise StageError(str(e))
        shutil.copy2(real, dst)

    for name in images:
        _copy_inside(img_src, os.path.join(img_src, name),
                     os.path.join(img_dst, name))
    _copy_inside(aud_src, narration,
                 os.path.join(aud_dst, "narration-full.wav"))
    _copy_inside(artifacts, captions_path,
                 os.path.join(assets_dir, "captions.json"))
    script_src = os.path.join(artifacts, "script.json")
    if os.path.isfile(script_src):
        _copy_inside(artifacts, script_src,
                     os.path.join(assets_dir, "script.json"))

    # القراءة أيضًا من المسار المحلول فقط (لا من رابط هارب).
    try:
        captions_path = resolve_inside(artifacts, captions_path,
                                       "ملف الكتابة")
    except ValueError as e:
        raise StageError(str(e))
    hook, full_text = load_script(project_path)
    phrases = build_phrases(captions_path)

    # مدة السرد من ffprobe (إن توفر) لتوزيع الصور؛ وإلا من آخر عبارة.
    duration = phrases[-1]["end"] if phrases else 0.0
    try:
        import subprocess
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", narration],
            capture_output=True, text=True, timeout=30)
        duration = float(out.stdout.strip())
    except Exception:
        pass

    # تسلسل الصور: كل صورة 5 ثوانٍ، وتكرار من البداية حتى تغطية مدة السرد
    # (بالتقريب لا بالسقف، حتى لا يمتد الفيديو ثواني صامتة بعد السرد).
    import math
    n_clips = max(1, round(duration / image_clip_seconds))
    sequence = [images[i % len(images)] for i in range(n_clips)]

    manifest = {
        "project": os.path.basename(project_path.rstrip("/")),
        "hook": hook,
        "full_text": full_text,
        "images": images,
        "sequence": sequence,
        "image_clip_seconds": image_clip_seconds,
        "narration": "assets/audio/narration-full.wav",
        "narration_duration": duration,
        "phrases": phrases,
        "assets_dir": assets_dir,
    }
    with open(os.path.join(run_dir, "manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest
