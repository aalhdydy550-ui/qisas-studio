#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
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

from lib import queue_check
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


# مواقع ثابتة في الـhome تنجو من إعادة تشغيل الـVM (روابط
# /usr/local/bin تُمسح معها، فيبلّغ doctor عن أداة موجودة أصلًا
# كغائبة). تُفحص فقط إن غاب الأمر عن PATH، وdoctor لا يصلح شيئًا.
_WHICH_FALLBACKS = {
    "piper": ("~/.local/bin/piper",),
    "yt-dlp": ("~/.local/bin/yt-dlp",),
    "omniroute": ("~/.npm-global/bin/omniroute", "/usr/bin/omniroute"),
}


def _check(cmd, name, level="error"):
    path = _which(cmd)
    if path:
        return {"name": name, "ok": True, "level": level,
                "detail": path, "fix": ""}
    for cand in _WHICH_FALLBACKS.get(cmd, ()):
        cand = os.path.expanduser(cand)
        if os.path.isfile(cand):
            return {"name": name, "ok": True, "level": level,
                    "detail": cand, "fix": ""}
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


# بند 8 من استخراج AlphaCLI (جولة v0.1.41): التحقق من PATH في
# shell جديدة — إطلاق shell دخول نظيفة (بيئة فارغة إلا HOME،
# وPATH أدنى) وسؤالها أين تجد الثنائيات، فيثبت أن تعديل PATH
# يعمل بدل افتراضه (كما في install.sh الخاص بـAlphaCLI).
_CLEAN_SHELL_BINARIES = ("piper", "ffmpeg", "omniroute")
_CLEAN_SHELL_MIN_PATH = "/usr/bin:/bin"


def _expected_binary_path(cmd):
    """الموضع المتوقع لثنائي كما يراه doctor الآن (PATH ثم
    بدائل الـhome الثابتة) — نفس منطق `_check`."""
    path = _which(cmd)
    if path:
        return path
    for cand in _WHICH_FALLBACKS.get(cmd, ()):
        cand = os.path.expanduser(cand)
        if os.path.isfile(cand):
            return cand
    return None


def _run_clean_shell(script, timeout=15):
    """شغّل سكربتًا في shell دخول نظيفة: بيئة فارغة إلا HOME
    وPATH أدنى (/usr/bin:/bin) — فتقرأ ملفات بدء التشغيل
    (~/.profile) وتعيد بناء PATH كما تراه طرفية جديدة.
    يرجع (stdout, "") أو (None, سبب الفشل)."""
    shell = shutil.which("bash") or shutil.which("sh")
    if not shell:
        return None, "لا توجد shell (bash/sh) لتشغيل الفحص"
    env = {"HOME": os.path.expanduser("~"),
           "PATH": _CLEAN_SHELL_MIN_PATH}
    try:
        proc = subprocess.run([shell, "-lc", script],
                              capture_output=True, text=True,
                              timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, "تعذر تشغيل الـshell النظيفة (%s)" % e
    return proc.stdout or "", ""


def _clean_shell_path_check(runner=None, timeout=15):
    """فحص PATH في shell جديدة (بند 8 — AlphaCLI).

    يمرّ إن وجدت الـshell النظيفة كلًا من piper وffmpeg
    وomniroute في مواضعه المتوقعة (بعد حل الروابط الرمزية —
    فـ /usr/local/bin/piper و~/.local/bin/piper الثنائي نفسه).
    تحذير لا خطأ عند غياب ثنائي أو فوز ثنائي آخر بالاسم،
    مع رسالة عربية تقول ماذا يفعل المستخدم.
    `runner` للحقن في الاختبارات: دالة (script, timeout)
    ترجع (stdout, error) كما يرجع `_run_clean_shell`."""
    name = "PATH في shell جديدة (piper/ffmpeg/omniroute)"
    run = runner or _run_clean_shell
    script = ("for b in piper ffmpeg omniroute; do "
              "echo \"$b=$(command -v \"$b\" || echo __MISSING__)\"; done")
    try:
        stdout, error = run(script, timeout)
    except Exception as e:
        stdout, error = None, str(e)
    if stdout is None:
        return {"name": name, "ok": False, "level": "warn",
                "detail": error or "تعذر تشغيل الـshell النظيفة",
                "fix": "تأكد من وجود bash وأن ملفات بدء التشغيل "
                       "(~/.profile) سليمة، ثم أعد doctor"}
    found = {}
    for line in (stdout or "").splitlines():
        if "=" in line:
            cmd, path = line.split("=", 1)
            found[cmd.strip()] = path.strip()
    problems = []
    good = []
    for cmd in _CLEAN_SHELL_BINARIES:
        expected = _expected_binary_path(cmd)
        got = found.get(cmd)
        if expected is None:
            problems.append(
                "%s غير مثبّت أصلًا (لا في PATH ولا في بدائل الـhome) — "
                "ثبّته أولًا: %s" % (cmd, INSTALL_HINTS.get(cmd, "")))
        elif not got or got == "__MISSING__":
            problems.append(
                "%s موجود في %s لكن الـshell الجديدة لا تجده — أضف "
                "مجلده إلى PATH" % (cmd, expected))
        elif os.path.realpath(got) != os.path.realpath(expected):
            problems.append(
                "ثنائي آخر يفوز باسم %s في الـshell الجديدة: %s بدل "
                "%s — أزل الثنائي الآخر من PATH أو أعد ترتيب PATH"
                % (cmd, got, expected))
        else:
            good.append("%s=%s" % (cmd, got))
    if not problems:
        return {"name": name, "ok": True, "level": "warn",
                "detail": "؛ ".join(good), "fix": ""}
    fix = ("أضف مجلدات الأدوات إلى PATH في ~/.bashrc و~/.profile: "
           "export PATH=\"$HOME/.local/bin:$HOME/.npm-global/bin:"
           "$PATH\" — ثم افتح طرفية جديدة وأعد "
           "`python3 studio.py doctor`")
    return {"name": name, "ok": False, "level": "warn",
            "detail": "؛ ".join(problems), "fix": fix}


def _protect_check(cfg=None):
    """حماية المشروع — مسح أسرار + .gitignore + نسخة احتياطية
    (المجموعة السريعة من `protect`، بلا عمليات خارجية).
    الفحص الكامل (سلامة + صلاحيات) بأمر `protect`."""
    from lib import protect as protect_lib
    results = protect_lib.run_fast_checks()
    fails = [r for r in results
             if r["ok"] is False and r["level"] == "error"]
    warns = [r for r in results if r["ok"] is False]
    detail = "؛ ".join(r["detail"] for r in results)
    if fails:
        return {"name": "حماية المشروع (protect)", "ok": False,
                "level": "error", "detail": detail[:300],
                "fix": "شغّل `python3 studio.py protect` للتفاصيل"}
    if warns:
        return {"name": "حماية المشروع (protect)", "ok": False,
                "level": "warn", "detail": detail[:300],
                "fix": "شغّل `python3 studio.py protect` للتفاصيل"}
    return {"name": "حماية المشروع (protect)", "ok": True,
            "level": "ok", "detail": detail[:300], "fix": ""}


def _queue_check(cfg=None):
    """بنية ملف الطابور (جولة v0.1.37) — خطأ إن معطوب،
    تحذير إن غاب الملف (تثبيت جديد بلا طابور بعد)."""
    queue_file = None
    if cfg:
        queue_file = (cfg.get("paths") or {}).get("queue_file")
    if not queue_file:
        queue_file = ("~/workspace/goals/goal/hidden_files/"
                      "story-queue-2026-11-20.md")
    path = os.path.expanduser(queue_file)
    if not os.path.isfile(path):
        return {"name": "بنية الطابور",
                "ok": False,
                "level": "warn",
                "detail": "ملف الطابور غير موجود بعد: %s" % path,
                "fix": "أنشئه بـ `queue add` أو انسخ ملف طابور موجود"}
    ok, issues = queue_check.validate_queue_file(path)
    if ok:
        return {"name": "بنية الطابور",
                "ok": True,
                "level": "ok",
                "detail": "الطابور سليم (لا أرقام/عناوين/مواعيد مكررة)"}
    return {"name": "بنية الطابور",
            "ok": False,
            "level": "error",
            "detail": "; ".join(issues[:3]),
            "fix": "شغّل: python3 studio.py queue validate"}


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
        _file_check(p["logo_badge"], "شارة شعار «قصص وعبر»",
                    fix="تأكد من وجود الشارة في assets/"
                        "qisas-logo-badge.png"),
        _file_check(p["config"], "ملف config.yaml", level="warn",
                    fix="cp config.example.yaml config.yaml"),
        _writable_dir_check(p["videos_dir"], "مجلد الفيديو (قابل للكتابة)"),
        _writable_dir_check(p["runs_dir"], "مجلد التشغيل (قابل للكتابة)"),
        _check("omniroute", "OmniRoute (بوابة الذكاء)", level="warn"),
        _clean_shell_path_check(),
        _omniroute_server_check(),
        _dir_check(p["openmontage_root"], "OpenMontage (خط الإنتاج)",
                   level="warn",
                   fix="استنسخ https://github.com/OpenMontageInc/OpenMontage"),
        _file_check(p["concat_bin"], "Concat (التجميع الافتراضي)",
                    level="warn",
                    fix="استنسخ Concat واستخرج AppImage"),
        _file_check(p["ensure_env"], "حارس البيئة ensure-env.sh",
                    level="warn",
                    fix="استنسخ سكربت ensure-env.sh أو تجاهل الفحص "
                        "إن لم تستخدمه"),
        _file_check(p["youtube_venv"], "بيئة YouTube ‏(.venv-youtube)",
                    level="warn",
                    fix="شغّل setup.sh لإنشائها (أو تجاهلها إن لم تنشر "
                        "على يوتيوب عبر API)"),
        _queue_check(cfg),
        _protect_check(cfg),
    ]
    return checks


# مساعد Gemini الآمن (مفتاح بديل عبر الـconnector).
GEMINI_HELPER = os.path.expanduser(
    "~/workspace/custom-connectors/custom.gemini/bin/gemini.py")


def _gemini_live_check(timeout=30):
    """فحص حي خفيف لـ Gemini: list-models عبر المساعد الآمن.

    تحذير فقط عند الفشل (Gemini ساق بديلة لا أساسية)؛ ومهلة
    30ث حتى لا يعلّق doctor.
    """
    name = "Gemini (مساعد آمن — ساق بديلة)"
    if not os.path.isfile(GEMINI_HELPER):
        return {"name": name, "ok": False, "level": "warn",
                "detail": "غير موجود: %s" % GEMINI_HELPER,
                "fix": "أعد ربط Gemini عبر الـconnector"}
    try:
        proc = subprocess.run(
            [sys.executable, GEMINI_HELPER, "list-models"],
            capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return {"name": name, "ok": False, "level": "warn",
                "detail": "تعذر الاتصال (مهلة %dث)" % timeout,
                "fix": "تحقق من الشبكة وأعد المحاولة"}
    if proc.returncode == 0 and "models" in (proc.stdout or ""):
        return {"name": name, "ok": True, "level": "warn",
                "detail": "يعمل (list-models ناجح)", "fix": ""}
    return {"name": name, "ok": False, "level": "warn",
            "detail": "فشل list-models: %s"
                      % ((proc.stderr or proc.stdout or "")
                         .strip()[:200] or "بلا تفاصيل"),
            "fix": "تحقق من ربط Gemini وأعد المحاولة"}


def run_llm_checks(cfg=None):
    """فحوصات سلسلة LLM فقط (لـ `doctor --llm`): بوابة
    OmniRoute (CLI + خادم) ومساعد Gemini (ملف + حي) وGroq
    (ركن ثانٍ — مفتاح/اتصال) وOllama المحلي (ساق أخيرة —
    تحذير فقط).
    قسم منفصل بعدّاده الخاص — لا تغيّر عدد فحوصات doctor
    الأساسية (27 بعد إضافة فحص PATH في shell جديدة، بند 8)."""
    return [
        _check("omniroute", "OmniRoute CLI (بوابة الذكاء)",
               level="warn"),
        _omniroute_server_check(),
        _file_check(GEMINI_HELPER,
                    "مساعد Gemini الآمن (ملف)", level="warn",
                    fix="أعد ربط Gemini عبر الـconnector"),
        _gemini_live_check(),
        _groq_check(),
        _ollama_check(cfg),
    ]


def _groq_check():
    """فحص خفيف لركن Groq الثاني (جولة v0.1.40 — يحل محل
    g4fpol): المفتاح في بيئة العملية فقط؛ غيابه تحذير لا
    خطأ (الركن يُتخطى عند فشل المصادقة بلا كسر للسلسلة).
    بلا شبكة وبلا قراءة أي قيمة سرية — الوجود فقط."""
    name = "Groq الرسمي المجاني (ركن ثانٍ — gpt-oss-120b)"
    if os.environ.get("GROQ_API_KEY", "").strip():
        return {"name": name, "ok": True, "level": "warn",
                "detail": "المفتاح مضبوط في البيئة", "fix": ""}
    return {"name": name, "ok": False, "level": "warn",
            "detail": "المفتاح GROQ_API_KEY غير مضبوط في البيئة — "
                      "الركن يُتخطى حتى إضافة اتصال المزود في "
                      "OmniRoute بالمفتاح",
            "fix": "أضف اتصال Groq في OmniRoute بمفتاح مجاني "
                   "(راجع free-keys/omniroute-combos.json)"}


def _ollama_check(cfg=None, timeout=5):
    """فحص خفيف لتوفر Ollama المحلي (ساق أخيرة في السلسلة).

    تحذير فقط عند الغياب (Ollama احتياطي دون اتصال لا أساسي)؛
    ومهلة 5ث حتى لا يعلّق doctor. بلا توليد وبلا إنفاق.
    """
    name = "Ollama المحلي (ساق أخيرة)"
    try:
        from lib import omniroute_client as _orc
        cfg_o = ((cfg or {}).get("omniroute") or {}
                 if isinstance(cfg, dict) else {})
        st = _orc.ollama_status(
            cfg_o.get("ollama_base_url"), cfg_o.get("ollama_model"),
            timeout=timeout)
    except Exception as e:
        return {"name": name, "ok": False, "level": "warn",
                "detail": "تعذر الفحص: %s" % e,
                "fix": "ollama serve"}
    if st.get("available"):
        return {"name": name, "ok": True, "level": "warn",
                "detail": "متاح — الموديل %s" % st.get("model"),
                "fix": ""}
    return {"name": name, "ok": False, "level": "warn",
            "detail": st.get("detail")
                      or "غير متاح — ثبّت Ollama وشغّل ollama serve "
                         "ثم ollama pull qwen2.5:7b",
            "fix": "ollama serve"}


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

# ------------------------------------------------------------------
# مخرجات JSON + فحوص مضيف + وضع --fix (جولة v0.1.63، عقدا ع2 وع20)
#
# - `--json` يرجع `{"ok", "problems", "warnings", "checks":
#   [{"id", "status", "message", "fix"}]}`؛ وخروج 7 عند أي FAIL
#   (فحص بمستوى error فاشل)؛ وكل فحص FAIL يحمل `fix` غير فارغ
#   (يُملأ بإصلاح افتراضي إن غاب من الفحص نفسه).
# - `--fix` يصلح ما يمكن (config.yaml من المثال + إنشاء
#   مجلدي الفيديو والتشغيل) ثم يعيد الفحص.
# - فحوص المضيف (شبكة، مساحة قرص، أدوات خارجية melt/piper)
#   بنفس صيغة سطور الفحوصات الأساسية — قسم مستقل لا يغيّر
#   عدد الفحوصات الأساسية (27 في run_checks + فحص الترخيص
#   = 28 في `studio.py doctor`).
# ------------------------------------------------------------------

# رمز خروج doctor عند أي FAIL (ع20 — وهو رمز ع1 رقم 7).
DOCTOR_FAIL_EXIT = 7

# إصلاح افتراضي يُملأ به أي فحص FAIL بلا `fix` في مصدره.
_DEFAULT_FIX = "أصلح السبب ثم أعد `python3 studio.py doctor`"

# عنوان فحص الشبكة (طلب خفيف بمهلة قصيرة — تحذير فقط).
_HOST_NETWORK_URL = "https://pypi.org"

# مجلدات قابلة للإصلاح عبر --fix: الاسم ← مفتاح cfg.paths.
_FIXABLE_DIRS = {
    "مجلد الفيديو (قابل للكتابة)": "videos_dir",
    "مجلد التشغيل (قابل للكتابة)": "runs_dir",
}


def _check_id(name, index, used):
    """معرّف ثابت للفحص من اسمه (slug): حروف/أرقام فقط،
    والباقي `-`؛ وإن فرغ الاسم أو تكرر المعرّف يُستخدم
    `check-NN` مع لاحقة تمييز."""
    slug = "".join(ch if ch.isalnum() else "-"
                   for ch in (name or "").lower())
    slug = "-".join(part for part in slug.split("-") if part)
    if not slug:
        slug = "check-%02d" % (index + 1)
    base, n = slug, 2
    while slug in used:
        slug = "%s-%d" % (base, n)
        n += 1
    used.add(slug)
    return slug


def _status_of(check):
    """حالة JSON للفحص: pass إن ناجح، وfail إن فاشل بمستوى
    error، وwarn إن فاشل بمستوى warn (أو أي مستوى آخر)."""
    if check.get("ok"):
        return "pass"
    if check.get("level") == "error":
        return "fail"
    return "warn"


def to_json_report(checks):
    """حوّل قائمة فحوصات (صيغة run_checks) إلى تقرير JSON
    بالشكل المتفق عليه: `{"ok", "problems", "warnings",
    "checks": [{"id", "status", "message", "fix"}]}`.

    `ok` صحيحة إن لم يكن أي FAIL (تحذيرات فقط لا تُسقطها)؛
    و`problems` عدد FAIL و`warnings` عدد التحذيرات.
    دالة نقية — لا تقرأ القرص ولا الشبكة.
    """
    entries = []
    problems = warnings = 0
    used = set()
    for i, check in enumerate(checks or []):
        status = _status_of(check)
        if status == "fail":
            problems += 1
        elif status == "warn":
            warnings += 1
        fix = (check.get("fix") or "").strip()
        if status != "pass" and not fix:
            fix = _DEFAULT_FIX
        entries.append({
            "id": _check_id(check.get("name", ""), i, used),
            "status": status,
            "message": "%s — %s" % (check.get("name", ""),
                                    check.get("detail", "")),
            "fix": fix,
        })
    return {"ok": problems == 0,
            "problems": problems,
            "warnings": warnings,
            "checks": entries}


def json_exit_code(checks):
    """رمز خروج doctor لقائمة فحوصات: 0 إن لم يكن أي FAIL،
    و7 (DOCTOR_FAIL_EXIT) عند أي FAIL."""
    return 0 if to_json_report(checks)["ok"] else DOCTOR_FAIL_EXIT


def _network_check(urlopen=None, timeout=5):
    """فحص الشبكة: طلب خفيف إلى pypi.org بمهلة قصيرة.

    تحذير فقط عند الفشل (الشبكة ليست أساسية للتجربة
    المحلية). `urlopen` للحقن في الاختبارات.
    """
    name = "الشبكة (اتصال إنترنت)"
    opener = urlopen or urllib.request.urlopen
    try:
        with opener(_HOST_NETWORK_URL, timeout=timeout) as resp:
            ok = 200 <= resp.status < 500
    except Exception:
        ok = False
    return {"name": name, "ok": ok, "level": "warn",
            "detail": "يعمل" if ok else "غير متاح (مهلة %dث)" % timeout,
            "fix": "" if ok else "تحقق من اتصال الشبكة ثم أعد "
                                 "`python3 studio.py doctor`"}


def _disk_space_check(path=None, min_free_gb=1.0):
    """فحص مساحة القرص: مساحة حرة ≥ `min_free_gb` في `path`
    (الافتراضي مجلد الاستوديو). تحذير فقط عند الضيق."""
    path = os.path.expanduser(str(path or STUDIO_DIR))
    try:
        usage = shutil.disk_usage(path)
    except OSError as e:
        return {"name": "مساحة القرص", "ok": False, "level": "warn",
                "detail": "تعذر قراءة مساحة القرص في %s (%s)"
                          % (path, e),
                "fix": "تأكد من وجود المسار %s ثم أعد الفحص" % path}
    free_gb = usage.free / (1024 ** 3)
    ok = free_gb >= min_free_gb
    return {"name": "مساحة القرص", "ok": ok, "level": "warn",
            "detail": "مساحة حرة %.1f غيغابايت في %s"
                      % (free_gb, path),
            "fix": "" if ok else "حرّر مساحة على القرص (احذف مخرجات "
                                 "قديمة من runs/ أو videos/)"}


def run_host_checks(cfg=None, disk_path=None, min_free_gb=1.0,
                    urlopen=None, network_timeout=5):
    """فحوص المضيف فقط (قسم مستقل بصيغة السطور نفسها):
    شبكة، مساحة قرص، وأدوات خارجية melt/piper.

    `disk_path` و`urlopen` و`network_timeout` للحقن في
    الاختبارات (بلا شبكة حقيقية وبلا قرص حقيقي).
    """
    cfg = cfg or {}
    disk = disk_path
    if disk is None:
        disk = (cfg.get("paths") or {}).get("videos_dir")
    return [
        _network_check(urlopen=urlopen, timeout=network_timeout),
        _disk_space_check(path=disk, min_free_gb=min_free_gb),
        _check("melt", "أداة المضيف melt/MLT", level="warn"),
        _check("piper", "أداة المضيف Piper", level="warn"),
    ]


def run_all_checks(cfg=None, **host_kwargs):
    """كل الفحوصات: الأساسية (27) + المضيف. عدد الأساسية
    لا يتغيّر — فحوص المضيف قسم إضافي بعدها."""
    return run_checks(cfg) + run_host_checks(cfg, **host_kwargs)


def run_json_report(cfg=None, include_host=True, **host_kwargs):
    """شغّل الفحوصات وارجع (تقرير JSON، رمز الخروج).

    رمز الخروج 0 إن لم يكن أي FAIL، و7 عند أي FAIL.
    `include_host=False` يرجع الأساسية فقط.
    """
    checks = (run_all_checks(cfg, **host_kwargs) if include_host
              else run_checks(cfg))
    report = to_json_report(checks)
    return report, 0 if report["ok"] else DOCTOR_FAIL_EXIT


def apply_fixes(checks, cfg=None, studio_dir=None, recheck=None):
    """صلّح ما يمكن من الفحوصات الفاشلة ثم أعد الفحص.

    القابل للإصلاح هنا: إنشاء config.yaml من المثال
    (`ensure_config`)، وإنشاء مجلدي الفيديو والتشغيل.
    الباقي يُترك في `unfixed` مع سببه في الفحص نفسه.
    يرجع `{"fixed": [أسماء], "unfixed": [أسماء],
    "checks": [الفحوصات بعد إعادة الفحص]}`.
    `recheck` للحقن في الاختبارات (الافتراضي `run_checks`).
    """
    cfg = cfg or {}
    fixed = []
    unfixed = []
    for check in checks or []:
        if check.get("ok"):
            continue
        name = check.get("name", "")
        done = False
        if "config.yaml" in name:
            done = ensure_config(studio_dir)
        elif name in _FIXABLE_DIRS:
            key = _FIXABLE_DIRS[name]
            path = (cfg.get("paths") or {}).get(key)
            if not path:
                path = DEFAULT_PATHS.get(
                    "videos_dir" if key == "videos_dir" else "runs_dir")
            try:
                os.makedirs(os.path.expanduser(str(path)),
                            exist_ok=True)
                done = True
            except OSError:
                done = False
        (fixed if done else unfixed).append(name)
    runner = recheck or (lambda: run_checks(cfg))
    return {"fixed": fixed, "unfixed": unfixed,
            "checks": runner()}
