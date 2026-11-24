#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""تدرج لوني عبر LUTs ثلاثية الأبعاد — `lut3d` في ffmpeg.

السياق (جولة v0.1.36، خريطة مزايا OpenReel — البند الأول):
محرر OpenReel يدعم LUTs أصلًا، وخط الإنتاج الحالي بلا أي تدرج
لوني — فالخطوة الأولى من الخريطة هي presets جاهزة تُطبَّق على
أي فيديو مُنتَج بفلتر `lut3d` (إعادة ترميز فيديو فقط، والصوت
يُنسخ بلا مساس).

الـpresets ملفات `.cube` نصية حتمية (LUT_3D_SIZE 16) مولَّدة
من مواصفات رقمية في هذا الملف نفسه (انظر `LUT_SPECS`) —
فأي ملف مفقود يُعاد توليده تلقائيًا، ولا نحتاج ملفات ثنائية
من الشبكة. «دافئ» هو هوية الصفحة (ألوان ترابية دافئة ذهبية).

الاستخدام:
  python3 studio.py grade --video out.mp4 --preset warm
  python3 studio.py grade --list-presets
  python3 studio.py assemble --run X --out out.mp4 --grade warm
"""
import os
import subprocess

from lib import check as check_lib

LUT_SIZE = 16
LUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "luts")

# الاسم → الوصف العربي (يُعرض في --help و--list-presets).
PRESETS = {
    "warm": "دافئ ذهبي — هوية الصفحة: أحمر مرتفع وأزرق منخفض قليلًا",
    "vivid": "زاهٍ — تشبّع أعلى للألوان",
    "cinematic": "سينمائي — تباين منحنى S وتشبّع أقل قليلًا",
    "soft": "هادئ — ظلال مرفوعة وتباين مخفَّف",
}

# المواصفة الرقمية لكل preset: scale/lift قبل الكسب، وكسب لكل
# قناة، وتشبّع، وانحناء تباين (0 = بلا منحنى، 1 = smoothstep كامل).
LUT_SPECS = {
    "warm": {"scale": 1.0, "lift": 0.01, "gains": (1.07, 1.00, 0.92),
             "sat": 1.05, "curve": 0.0},
    "vivid": {"scale": 1.0, "lift": 0.0, "gains": (1.0, 1.0, 1.0),
              "sat": 1.30, "curve": 0.0},
    "cinematic": {"scale": 1.0, "lift": 0.0, "gains": (1.03, 1.00, 0.97),
                  "sat": 0.92, "curve": 0.5},
    "soft": {"scale": 0.84, "lift": 0.08, "gains": (1.0, 1.0, 1.0),
             "sat": 0.92, "curve": 0.0},
}


class LutError(Exception):
    """خطأ في التدرج اللوني (رسالته عربية جاهزة للعرض)."""


def lut_path(preset):
    """مسار ملف .cube الخاص بـpreset."""
    return os.path.join(LUT_DIR, preset + ".cube")


def _clamp(x):
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def _grade_point(r, g, b, spec):
    """طبّق مواصفة preset على نقطة لون واحدة (قيم 0..1)."""
    scale = spec["scale"]
    lift = spec["lift"]
    gains = spec["gains"]
    r1 = _clamp(r * scale + lift) * gains[0]
    g1 = _clamp(g * scale + lift) * gains[1]
    b1 = _clamp(b * scale + lift) * gains[2]
    sat = spec["sat"]
    if sat != 1.0:
        gray = 0.299 * r1 + 0.587 * g1 + 0.114 * b1
        r1 = _clamp(gray + (r1 - gray) * sat)
        g1 = _clamp(gray + (g1 - gray) * sat)
        b1 = _clamp(gray + (b1 - gray) * sat)
    curve = spec["curve"]
    if curve:
        r1 = _clamp(r1 + curve * (r1 * r1 * (3 - 2 * r1) - r1))
        g1 = _clamp(g1 + curve * (g1 * g1 * (3 - 2 * g1) - g1))
        b1 = _clamp(b1 + curve * (b1 * b1 * (3 - 2 * b1) - b1))
    return r1, g1, b1


def generate_lut(preset, path=None):
    """ولّد ملف .cube لـpreset (حتمي — نفس البايتات كل مرة).

    يرجع مسار الملف. يرفع LutError عند preset غير معروف.
    """
    if preset not in LUT_SPECS:
        raise LutError("preset غير معروف: %s (المسموح: %s)"
                       % (preset, ", ".join(sorted(PRESETS))))
    path = path or lut_path(preset)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    spec = LUT_SPECS[preset]
    n = LUT_SIZE
    lines = ["# %s — preset %s مولَّد من lib/lut_grade.py (studio v0.1.36)"
             % (os.path.basename(path), preset),
             "LUT_3D_SIZE %d" % n,
             "DOMAIN_MIN 0.0 0.0 0.0",
             "DOMAIN_MAX 1.0 1.0 1.0",
             ""]
    # ترتيب .cube: R الأسرع، ثم G، ثم B.
    for b_i in range(n):
        for g_i in range(n):
            for r_i in range(n):
                r = r_i / (n - 1)
                g = g_i / (n - 1)
                b = b_i / (n - 1)
                r2, g2, b2 = _grade_point(r, g, b, spec)
                lines.append("%.6f %.6f %.6f" % (r2, g2, b2))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def ensure_presets():
    """ولّد أي ملفات .cube مفقودة. يرجع قائمة المسارات المولَّدة."""
    created = []
    for preset in sorted(PRESETS):
        path = lut_path(preset)
        if not os.path.isfile(path):
            created.append(generate_lut(preset, path))
    return created


def list_presets():
    """قائمة الـpresets مع الوصف وحالة الملف."""
    ensure_presets()
    return [{"name": name, "description": PRESETS[name],
             "file": lut_path(name),
             "exists": os.path.isfile(lut_path(name))}
            for name in sorted(PRESETS)]


def _escape_filter_path(path):
    """هرّب مسارًا داخل وسيط فلتر ffmpeg (الشرطة والنقطتان)."""
    return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def default_out_path(video_path, preset):
    """مسار الإخراج الافتراضي: <الاسم>-<preset>.mp4 بجانب الأصلي."""
    root, _ext = os.path.splitext(video_path)
    return "%s-%s.mp4" % (root, preset)


def apply_lut(video_path, preset, out_path=None, crf=20):
    """طبّق preset لونيًا على فيديو. يرجع تقريرًا قاموسيًا.

    {"path", "output", "preset", "lut_file", "duration_before",
     "duration_after", "changed"}
    الفيديو يُعاد ترميزه (libx264 crf 20)، والصوت يُنسخ بلا
    إعادة ترميز. يرفع LutError برسالة عربية عند ملف مفقود أو
    preset غير معروف أو فشل ffmpeg.
    """
    if preset not in PRESETS:
        raise LutError("preset غير معروف: %s (المسموح: %s)"
                       % (preset, ", ".join(sorted(PRESETS))))
    video_path = os.path.abspath(os.path.expanduser(video_path))
    if not os.path.isfile(video_path):
        raise LutError("ملف الفيديو غير موجود: %s" % video_path)
    ensure_presets()
    lut_file = lut_path(preset)
    try:
        info = check_lib.probe(video_path)
    except check_lib.CheckError as e:
        raise LutError(str(e))
    duration = info["duration"]
    out_path = (os.path.abspath(os.path.expanduser(out_path))
                if out_path else default_out_path(video_path, preset))
    if os.path.abspath(out_path) == video_path:
        raise LutError("مسار الإخراج هو نفسه ملف الفيديو — حدد --out مختلفًا")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    tmp_out = out_path + ".tmp.mp4"
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", video_path,
           "-vf", "lut3d=file=%s" % _escape_filter_path(lut_file),
           "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-c:a", "copy", "-movflags", "+faststart",
           "-t", "%.3f" % duration, tmp_out]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=900)
    except FileNotFoundError:
        raise LutError("الأمر غير موجود: ffmpeg")
    except subprocess.TimeoutExpired:
        raise LutError("انتهت المهلة أثناء التدرج اللوني (900 ثانية)")
    if proc.returncode != 0 or not os.path.isfile(tmp_out):
        if os.path.isfile(tmp_out):
            os.remove(tmp_out)
        raise LutError("فشل التدرج اللوني عبر ffmpeg: %s"
                       % (proc.stderr or "").strip()[-300:])
    os.replace(tmp_out, out_path)
    try:
        after_info = check_lib.probe(out_path)
    except check_lib.CheckError as e:
        raise LutError("تعذر قراءة الفيديو المدرَّج: %s" % e)
    return {"path": video_path, "output": out_path, "preset": preset,
            "lut_file": lut_file,
            "duration_before": round(duration, 3),
            "duration_after": round(after_info["duration"], 3),
            "changed": True}


def format_report(result):
    """نص عربي لتقرير التدرج."""
    return (
        "تدرج لوني (%s — %s): %s\n"
        "المدة: %.3f ث ← %.3f ث\n"
        "ملف LUT: %s\n"
        "الناتج: %s\n"
        % (result["preset"], PRESETS[result["preset"]],
           result["path"], result["duration_before"],
           result["duration_after"], result["lut_file"],
           result["output"]))
