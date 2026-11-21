#!/usr/bin/env python3
"""فحص بيئة studio (doctor) — تقرير PASS/FAIL صادق بلا ادعاء.

يُستخدم من `studio.py doctor` ومن `setup.sh`. كل فحص يرجع قاموسًا:
  {"name": ..., "ok": bool, "level": "error"|"warn",
   "detail": ..., "fix": ...}

- level "error": أساسي (التجربة `run --demo` والنشر لا يعملان بدونه).
- level "warn": اختياري أو لخط الإنتاج الكامل فقط (يُكمل بدونه).
- لا يصلح شيئًا بنفسه إلا عبر `ensure_config` (إنشاء config.yaml
  من المثال) وإنشاء مجلدي الفيديو والتشغيل — وكلاهما صريح من
  `--fix` فقط. لا يدّعي نجاح فحص فشل أبدًا.
"""
import os
import shutil
import subprocess
import sys
import urllib.request

from lib import long_narration

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# مسارات افتراضية مطابقة لـ studio.DEFAULTS (تُتجاوز بـ cfg).
DEFAULT_PATHS = {
    "openmontage_root": "~/workspace/openmontage",
    "concat_bin": "~/workspace/concat/squashfs-root/usr/bin/concat",
    "headless_editor": "~/workspace/headless-editor/editor.py",
    "videos_dir": "~/workspace/videos",
    "runs_dir": "~/workspace/studio/runs",
    "ensure_env": "~/workspace/ensure-env.sh",
    "logo_badge": os.path.join(STUDIO_DIR, "assets", "qisas-logo-badge.png"),
    "config_example": os.path.join(STUDIO_DIR, "config.example.yaml"),
    "config": os.path.join(STUDIO_DIR, "config.yaml"),
    "youtube_venv": os.path.join(STUDIO_DIR, ".venv-youtube",
                                 "bin", "python"),
}

INSTALL_HINTS = {
    "ffmpeg": "sudo apt-get install -y ffmpeg",
    "ffprobe": "sudo apt-get install -y ffmpeg",
    "git": "sudo apt-get install -y git",
    "node": "sudo apt-get install -y nodejs",
    "npm": "sudo apt-get install -y npm",
    "melt": "sudo apt-get install -y melt",
    "yt-dlp": "pip install --user yt-dlp",
    "piper": "ثبّت Piper في ~/.local/bin/piper (انظر README)",
    "omniroute": "npm install -g omniroute (ثم omniroute serve --daemon)",
}


def _which(cmd):
    return shutil.which(cmd)


def _check(cmd, name, level="error"):
    path = _which(cmd)
    if path:
        return {"name": name, "ok": True, "level": level,
                "detail": path, "fix": ""}
    return {"name": name, "ok": False, "level": level,
            "detail": "غير موجود في PATH",
            "fix": INSTALL_HINTS.get(cmd, "")}


def _file_check(path, name, level="error", fix=""):
    path = os.path.expanduser(str(path))
    if os.path.isfile(path):
        return {"name": name, "ok": True, "level": level,
                "detail": path, "fix": ""}
    return {"name": name, "ok": False, "level": level,
            "detail": "غير موجود: %s" % path, "fix": fix}


def _dir_check(path, name, level="warn", fix=""):
    path = os.path.expanduser(str(path))
    if os.path.isdir(path):
        return {"name": name, "ok": True, "level": level,
                "detail": path, "fix": ""}
    return {"name": name, "ok": False, "level": level,
            "detail": "غير موجود: %s" % path, "fix": fix}


def _python_check():
    v = sys.version_info
    ok = (v.major, v.minor) >= (3, 9)
    return {"name": "Python ‏3.9+", "ok": ok, "level": "error",
            "detail": "Python %d.%d.%d" % (v.major, v.minor, v.micro),
            "fix": "" if ok else "ثبّت Python 3.9 أو أحدث"}


def _lib_check(module, name, level="error", fix=""):
    try:
        __import__(module)
        return {"name": name, "ok": True, "level": level,
                "detail": "مثبّت", "fix": ""}
    except ImportError:
        return {"name": name, "ok": False, "level": level,
                "detail": "غير مثبّت", "fix": fix}


def _font_check():
    try:
        out = subprocess.run(["fc-list"], capture_output=True, text=True,
                             timeout=15)
        if "Noto Naskh" in (out.stdout or ""):
            return {"name": "خط Noto Naskh Arabic", "ok": True,
                    "level": "error", "detail": "موجود", "fix": ""}
        return {"name": "خط Noto Naskh Arabic", "ok": False,
                "level": "error", "detail": "غير موجود",
                "fix": "sudo apt-get install -y fonts-noto-core"}
    except (OSError, subprocess.TimeoutExpired):
        return {"name": "خط Noto Naskh Arabic", "ok": False,
                "level": "warn", "detail": "تعذر فحص الخطوط (fc-list)",
                "fix": "sudo apt-get install -y fontconfig"}


def _omniroute_server_check():
    try:
        with urllib.request.urlopen("http://127.0.0.1:20128/api/health",
                                    timeout=2) as resp:
            ok = 200 <= resp.status < 500
    except Exception:
        ok = False
    return {"name": "خادم OmniRoute ‏(127.0.0.1:20128)", "ok": ok,
            "level": "warn",
            "detail": "يعمل" if ok else "متوقف (يُشغَّل تلقائيًا عند الحاجة)",
            "fix": "omniroute serve --no-open --daemon --port 20128"}


def _writable_dir_check(path, name):
    path = os.path.expanduser(str(path))
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".doctor-write-test")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return {"name": name, "ok": True, "level": "error",
                "detail": path, "fix": ""}
    except OSError as e:
        return {"name": name, "ok": False, "level": "error",
                "detail": "غير قابل للكتابة: %s (%s)" % (path, e),
                "fix": "أصلح صلاحيات المجلد"}


def run_checks(cfg=None):
    """شغّل كل الفحوصات. يرجع قائمة قواميس (بالترتيب الظاهر للمستخدم)."""
    cfg = cfg or {}
    p = dict(DEFAULT_PATHS)
    if cfg.get("openmontage", {}).get("root"):
        p["openmontage_root"] = cfg["openmontage"]["root"]
    if cfg.get("concat", {}).get("bin"):
        p["concat_bin"] = cfg["concat"]["bin"]
    if cfg.get("headless", {}).get("editor"):
        p["headless_editor"] = cfg["headless"]["editor"]
    if cfg.get("paths", {}).get("videos_dir"):
        p["videos_dir"] = cfg["paths"]["videos_dir"]
    if cfg.get("paths", {}).get("runs_dir"):
        p["runs_dir"] = cfg["paths"]["runs_dir"]

    checks = [
        _python_check(),
        _check("ffmpeg", "ffmpeg (أساسي للريندر)"),
        _check("ffprobe", "ffprobe (قراءة مدد الفيديو)"),
        _check("git", "git", level="warn"),
        _check("node", "node (لـ OpenMontage)", level="warn"),
        _check("npm", "npm (لتثبيت OmniRoute)", level="warn"),
        _check("melt", "melt/MLT (خلفية تجميع بديلة)", level="warn"),
        _check("yt-dlp", "yt-dlp (لتحليل المراجع)", level="warn"),
        _check("piper", "Piper (ثنائي السرد)"),
        _file_check(long_narration.PIPER_MODEL, "موديل صوت Piper "
                    "(ar_JO-kareem-medium)",
                    fix="نزّل الموديل إلى ~/workspace/tts-models/"),
        _file_check(p["headless_editor"], "محرر headless-editor "
                    "(خلفية التجربة)",
                    fix="استنسخ ~/workspace/headless-editor/"),
        _lib_check("yaml", "PyYAML (قراءة config.yaml)",
                   fix="pip install --user pyyaml"),
        _lib_check("PIL", "Pillow (خلفيات التجربة)",
                   fix="pip install --user pillow"),
        _font_check(),
        _file_check(p["logo_badge"], "شارة شعار «قصص وعبر»"),
        _file_check(p["config"], "ملف config.yaml", level="warn",
                    fix="cp config.example.yaml config.yaml"),
        _writable_dir_check(p["videos_dir"], "مجلد الفيديو (قابل للكتابة)"),
        _writable_dir_check(p["runs_dir"], "مجلد التشغيل (قابل للكتابة)"),
        _check("omniroute", "OmniRoute (بوابة الذكاء)", level="warn"),
        _omniroute_server_check(),
        _dir_check(p["openmontage_root"], "OpenMontage (خط الإنتاج)",
                   level="warn",
                   fix="استنسخ https://github.com/OpenMontageInc/OpenMontage"),
        _file_check(p["concat_bin"], "Concat (التجميع الافتراضي)",
                    level="warn",
                    fix="استنسخ Concat واستخرج AppImage"),
        _file_check(p["ensure_env"], "حارس البيئة ensure-env.sh",
                    level="warn"),
        _file_check(p["youtube_venv"], "بيئة YouTube ‏(.venv-youtube)",
                    level="warn",
                    fix="شغّل setup.sh لإنشائها (أو تجاهلها إن لم تنشر "
                        "على يوتيوب عبر API)"),
    ]
    return checks


def ensure_config(studio_dir=None):
    """أنشئ config.yaml من المثال إن غاب. يرجع True إن أُنشئ."""
    studio_dir = studio_dir or STUDIO_DIR
    src = os.path.join(studio_dir, "config.example.yaml")
    dst = os.path.join(studio_dir, "config.yaml")
    if os.path.isfile(dst) or not os.path.isfile(src):
        return False
    import shutil as _shutil
    _shutil.copyfile(src, dst)
    return True


def format_report(checks):
    """نص التقرير + (عدد الأخطاء، عدد التحذيرات)."""
    lines = []
    errors = warnings = 0
    for c in checks:
        if c["ok"]:
            lines.append("[PASS] %s — %s" % (c["name"], c["detail"]))
        elif c["level"] == "error":
            errors += 1
            line = "[FAIL] %s — %s" % (c["name"], c["detail"])
            if c.get("fix"):
                line += "  ← %s" % c["fix"]
            lines.append(line)
        else:
            warnings += 1
            line = "[WARN] %s — %s" % (c["name"], c["detail"])
            if c.get("fix"):
                line += "  ← %s" % c["fix"]
            lines.append(line)
    if errors:
        lines.append("النتيجة: %d خطأ أساسي، %d تحذير — أصلح الأخطاء "
                     "قبل تشغيل التجربة" % (errors, warnings))
    elif warnings:
        lines.append("النتيجة: كل الفحوصات الأساسية سليمة، %d تحذير "
                     "(اختياري) — التجربة جاهزة" % warnings)
    else:
        lines.append("النتيجة: كل الفحوصات سليمة — النظام جاهز")
    return "\n".join(lines), errors, warnings
