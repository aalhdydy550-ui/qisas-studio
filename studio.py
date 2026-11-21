#!/usr/bin/env python3
"""studio — خط إنتاج موحّد لفيديوهات القصص.

المعمارية (طبقة تنسيق فقط — لا كود منسوخ من الأدوات الثلاث):
  OmniRoute  (الذكاء: سيناريو/هوك/عناوين عبر نماذج مجانية)
      ↓
  OpenMontage (الإنتاج: بحث، سيناريو، سرد Piper، صور، تركيب)
      ↓
  Concat     (التجميع النهائي القابل للتعديل + التصدير — الافتراضي)
  headless-editor (تجميع بديل عبر `editor.py render` — اختياري)

الأوامر:
  studio.py status
  studio.py doctor [--fix]   # فحص بيئة studio (PASS/FAIL صادق)
  studio.py run --demo       # القصة التجريبية المدمجة (مسار مجاني فقط)
  studio.py publish --video F --title T [--caption C] [--dry-run]
      # نشر فيديو على صفحة فيسبوك (Reel) ويوتيوب (Data API v3)
  studio.py youtube-auth     # تبادل OAuth ليوتيوب لمرة واحدة
  studio.py script   --story NAME [--allow-fallback]
  studio.py produce  --project NAME [--run RUN_ID]
  studio.py assemble --run RUN_ID [--out PATH] [--backend concat|headless|mlt]
      [--size WxH] [--no-watermark] [--cards-dir DIR] — شعار الصفحة تلقائي، وبطاقات
      # الاقتباس الختامية (3×3 ثوانٍ) إن أُعطي مجلدها.
  studio.py quote-cards --ibra TEXT --hikma TEXT --mawiza TEXT
      [--mawiza-source TEXT] --out-dir DIR
      # توليد بطاقات الاقتباس الثلاث (عبرة/حكمة/موعظة) 720×1280.
  studio.py thumbnail --video PATH --hook TEXT [--time SEC] [--out PATH]
  studio.py whisper-ass --audio PATH --out PATH [--model small]
      # كابشنات من faster-whisper (خيار تجريبي — انظر WHISPER-TEST.md)
  studio.py run      --story NAME --project NAME [--out PATH] [--allow-fallback] [--dry-run] [--backend concat|headless|mlt] [--size WxH]
      # المقاس الافتراضي 720×1280 (عمودي)؛ --size 1280x720 للأفقي
      # (الفيديو الطويل الأسبوعي ليوتيوب).
  studio.py long-video --out PATH --title TITLE [--story NAME | --project NAME
      | --run RUN_ID | --chapter-dir DIR | --chapter-text TITLE --text-file FILE
      --cover IMG ...] [--chapters-file FILE] [--music PATH] [--atempo X]
      # فيديو طويل أفقي 1280×720 (8–12 دقيقة) من عدة قصص: مقدمة بهوك
      # + فصل لكل قصة (بطاقة عنوان + محتوى بعبرته) + خاتمة باشتراك واحد.
      # سرد Piper مقسّم، كتابة كلمة-بكلمة، شعار الصفحة تلقائي، وبلا
      # بطاقات اقتباس أبدًا. ينتج أيضًا طوابع الفصول ووصف يوتيوب.
  studio.py long-narration --text TEXT | --text-file FILE --out WAV
      [--gap SEC] [--atempo X]
      # سرد طويل مقسّم بصوت Piper (رجل) — نص طويل إلى WAV واحد
      # بفواصل صمت بين الجمل، مع أزمنة كل جملة.
  studio.py run-queue [--limit N] [--continue-on-error] [--dry-run]
      # دفعة جماعية من ملف الطابور: القصص الجاهزة فقط (مشروع
      # OpenMontage موجود) تُشغَّل بالتتابع؛ بلا مشروع تُتخطى.
  studio.py analyze-ref --url URL
      # تحليل فيديو مرجعي (بيانات + تفريغ + هوك/إيقاع/ختام) — تحليل
      # خاص فقط، بلا إعادة نشر أو توزيع (انظر README).

الخطوات تعمل بالتتابع (الجهاز محدود: 1.5 وحدة CPU و~6 جيجا رام بلا
كارت شاشة). خادم OmniRoute يبقى شغالًا على loopback (127.0.0.1:20128)
لأن أمر `chat` يحتاجه — هو مجرد عميل HTTP للخادم، وبدونه يفشل
بصمت (عيب 2026-11-21، انظر _ensure_omniroute_server).
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import omniroute_client
from lib import openmontage_stage
from lib import concat_mcp
from lib import headless_stage
from lib import autoedit
from lib import moviepy_fx
from lib import capite_captions
from lib import trim
from lib import mlt_stage
from lib import thumbnail
from lib import whisper_captions
from lib import ref_analyzer
from lib import watermark
from lib import long_narration
from lib import long_video
from lib import doctor
from lib import demo
from lib import publish
from lib import queue as queue_lib
from lib import autoweek
from lib import analyze
from lib import help_ar

VERSION = "0.1.21"
STUDIO_DIR = os.path.dirname(os.path.abspath(__file__))
# الموسيقى الخلفية المدمجة (شوبان — ملكية عامة، assets/music/).
DEFAULT_MUSIC = os.path.join(
    STUDIO_DIR, "assets", "music", "calm-piano-chopin-nocturne-20.mp3")
DEFAULTS = {
    "omniroute": {"base_url": "http://localhost:20128",
                  "model": "ddgw/gpt-5.4-mini",
                  "fallback_model": "g4fpol/deepseek",
                  "timeout_seconds": 120,
                  "retries": 1,
                  "retry_delay_seconds": 5},
    "openmontage": {"root": "~/workspace/openmontage",
                    "projects_dir": "~/workspace/openmontage/projects"},
    "concat": {"bin": "~/workspace/concat/squashfs-root/usr/bin/concat",
               "projects_dir": "~/workspace/concat/projects"},
    "headless": {"root": "~/workspace/headless-editor",
                 "editor": "~/workspace/headless-editor/editor.py"},
    "video": {"width": 720, "height": 1280, "fps": 30,
              "codec": "h264", "crf": 20, "image_clip_seconds": 5},
    "paths": {"workspace": "~/workspace",
              "videos_dir": "~/workspace/videos",
              "runs_dir": "~/workspace/studio/runs",
              "queue_file": "~/workspace/goals/goal/hidden_files/"
                            "story-queue-2026-11-20.md"},
    "publish": {"page_id": "",
                "youtube_client_secrets":
                    "~/workspace/studio/client_secrets.json",
                "youtube_token": "~/workspace/studio/youtube-token.json",
                "youtube_privacy": "public",
                "youtube_channel_id": "UCz5VeqN-eolCaCPGTpiWtJw"},
    "long_video": {"default_music": ""},
}


# قصص الطابور التي لها مشروع OpenMontage جاهز، برقمها في ملف
# الطابور: رقم القصة → (slug القصة في studio، اسم مشروع OpenMontage).
# أي قصة خارج هذه الخريطة بلا مشروع مُعدّ فتُتخطى في run-queue
# (لا يُخترع سيناريو من لا شيء). تُحدَّث الخريطة كلما جُهّز مشروع
# جديد لقصة من الطابور.
KNOWN_PROJECTS = {
    4: ("anza", "anza-part1"),  # العنزة المباركة
}


def load_config():
    cfg = json.loads(json.dumps(DEFAULTS))  # نسخة عميقة
    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("config.yaml", "config.yml"):
        path = os.path.join(here, name)
        if not os.path.isfile(path):
            continue
        try:
            import yaml
            with open(path, encoding="utf-8") as f:
                user = yaml.safe_load(f) or {}
            _deep_update(cfg, user)
        except ImportError:
            print("تحذير: PyYAML غير متاح — يُستخدم الإعداد الافتراضي",
                  file=sys.stderr)
        except Exception as e:
            print("تحذير: تعذر قراءة %s (%s) — يُستخدم الافتراضي"
                  % (path, e), file=sys.stderr)
        break
    # تحقق: أي قسم أُبدل بنوع خاطئ (مثلًا نص بدل قاموس) يُعاد للافتراضي
    for section, default in DEFAULTS.items():
        if not isinstance(cfg.get(section), dict):
            print("تحذير: قسم %s في الإعداد بنوع خاطئ — يُستخدم الافتراضي"
                  % section, file=sys.stderr)
            cfg[section] = json.loads(json.dumps(default))
    return cfg


def _deep_update(base, user):
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v


def parse_size(text):
    """فسّر مقاس فيديو بصيغة WxH (مثال: 1280x720) إلى (عرض، ارتفاع).

    يُستخدم مع --size في run/assemble للفيديو الأفقي (الفيديو الطويل
    الأسبوعي). يرفع ValueError برسالة عربية عند أي صيغة غير صالحة.
    """
    if not isinstance(text, str):
        raise ValueError("المقاس يجب أن يكون نصًا بصيغة WxH مثل 1280x720")
    parts = text.strip().lower().split("x")
    if len(parts) != 2:
        raise ValueError("المقاس بصيغة WxH مثل 1280x720 (وصل: %s)" % text)
    try:
        width = int(parts[0])
        height = int(parts[1])
    except ValueError:
        raise ValueError("المقاس بصيغة WxH بأرقام صحيحة (وصل: %s)" % text)
    if width <= 0 or height <= 0:
        raise ValueError("أبعاد المقاس يجب أن تكون موجبة (وصل: %s)" % text)
    return width, height


def expand(p):
    return os.path.expanduser(os.path.expandvars(str(p)))


def validate_run_component(name, what="اسم القصة"):
    r"""تحقق من مكوّن مسار واحد (slug قصة أو معرّف تشغيل) قبل ضمّه إلى مسار.

    يرفض أي قيمة قد تخرج بالمسار من مجلد التشغيل: فواصل مسارات (`/` أو
    `\`)، أو `..`، أو حرف NUL، أو البدء بنقطة. القيم الصالحة مثل:
    anza، aisha-part2، test_1.
    """
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


def run_dir_for(runs_dir, run_id):
    """مسار تشغيل داخل runs_dir مع تحقق دفاعي بعد الـresolve.

    يتحقق أولًا من مكوّن المسار، ثم يتأكد بعد حلّ المسار المطلق أن
    الناتج ما زال داخل runs_dir (دفاع بالعمق ضد `..` والروابط الرمزية).
    """
    validate_run_component(run_id, "معرّف التشغيل")
    base = Path(os.path.realpath(runs_dir))
    target = Path(os.path.realpath(os.path.join(str(base), run_id)))
    if not target.is_relative_to(base):
        raise ValueError("معرّف التشغيل يخرج عن مجلد التشغيل: %s" % run_id)
    return str(target)


def new_run(runs_dir, story):
    validate_run_component(story, "اسم القصة")
    ts = time.strftime("%Y%m%d-%H%M%S")
    run_id = "%s-%s" % (story, ts)
    run_dir = run_dir_for(runs_dir, run_id)
    n = 2
    while os.path.exists(run_dir):  # تشغيلان في نفس الثانية لنفس القصة
        run_id = "%s-%s-%d" % (story, ts, n)
        run_dir = run_dir_for(runs_dir, run_id)
        n += 1
    os.makedirs(run_dir, exist_ok=True)
    return run_id, run_dir


def write_log(run_dir, log):
    with open(os.path.join(run_dir, "run-log.json"), "w",
              encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- status
def cmd_status(cfg):
    ok = True
    print("== OmniRoute (الذكاء) ==")
    base = cfg["omniroute"]["base_url"]
    try:
        req = urllib.request.Request(base.rstrip("/") + "/")
        with urllib.request.urlopen(req, timeout=8) as resp:
            print("  الخادم يعمل على %s (HTTP %s)" % (base, resp.status))
    except Exception as e:
        print("  الخادم لا يرد على %s: %s" % (base, e))
        ok = False
    try:
        out = subprocess.run(["omniroute", "providers", "list"],
                             capture_output=True, text=True, timeout=30)
        import re as _re
        clean = _re.sub(r"\x1b\[[0-9;]*m", "", out.stdout or "")
        rows = [l.strip() for l in clean.splitlines()
                if l.strip() and not l.strip().startswith(("Loaded",
                      "STORAGE", "OmniRoute Providers", "⚠"))]
        print("  المزودون: %s" % ("؛ ".join(rows) if rows
                                   else "لا يوجد مزود مفعّل"))
    except Exception as e:
        print("  تعذر فحص المزودين: %s" % e)
    print("== OpenMontage (الإنتاج) ==")
    root = expand(cfg["openmontage"]["root"])
    print("  %s: %s" % (root, "موجود" if os.path.isdir(root) else "غير موجود"))
    print("== Concat (التجميع) ==")
    b = expand(cfg["concat"]["bin"])
    print("  %s: %s" % (b, "موجود" if os.path.isfile(b) else "غير موجود"))
    print("== headless-editor (تجميع بديل) ==")
    h = expand(cfg["headless"]["editor"])
    print("  %s: %s" % (h, "موجود" if os.path.isfile(h) else "غير موجود"))
    print("== MLT/melt (تجميع بديل — تايم لاين XML) ==")
    print("  %s" % ("متاح" if shutil_which("melt") else "غير متاح — "
                     "sudo apt-get install -y melt"))
    print("== ffmpeg ==")
    print("  %s" % ("متاح" if shutil_which("ffmpeg") else "غير متاح"))
    print("== الذاكرة ==")
    try:
        with open("/proc/meminfo") as f:
            mem = dict(l.split(":") for l in f.read().splitlines())
        free = int(mem["MemAvailable"].split()[0]) // 1024
        print("  المتاح: %s ميجا" % free)
    except Exception:
        pass
    return 0 if ok else 1


# أدوات يتوقع خط الإنتاج وجودها في PATH (روابط /usr/local/bin
# لنسخها في الـhome). إن غاب أحدها أو غاب ملف خدمة systemd، يُشغَّل
# سكربت الاستعادة تلقائيًا — إصلاح ذاتي بعد أي مسح كامل.
_EXPECTED_TOOLS = ("ffmpeg", "melt", "yt-dlp", "omniroute", "ollama",
                   "piper", "zstd")
_SETUP_ENV_SCRIPT = os.path.join(os.path.expanduser("~"), "workspace",
                                  "setup-env.sh")
_UNIT_FILE = "/etc/systemd/system/studio-env-restore.service"
# أدوات الحماية (apt) وقاعدة ClamAV — تُمسح مع كل ريستارت، وحارس البيئة
# ensure-env.sh يعيدها في الخلفية (انظر _ensure_protection_tools).
_PROTECTION_TOOLS = ("lynis", "clamscan", "rkhunter", "chkrootkit",
                     "fail2ban-client", "ufw")
_ENSURE_ENV_SCRIPT = os.path.join(os.path.expanduser("~"), "workspace",
                                  "ensure-env.sh")
_CLAMAV_DB_DIR = "/var/lib/clamav"


def _ensure_environment():
    """أصلح البيئة بنفسك قبل حلّ الأدوات (best-effort، بلا فشل).

    يضيف مجلدي أدوات الـhome إلى PATH أولًا (شل التنفيذ لا يشملهما
    أصلًا)، فإن بقيت أداة متوقعة غائبة أو غاب ملف الخدمة، يشغّل
    setup-env.sh مرة واحدة بمهلة 300 ثانية. وأخيرًا يتأكد أن خادم
    OmniRoute شغال على loopback لأن أمر `chat` يحتاجه (عيب 2026-11-21).
    أي فشل يُسجَّل تحذيرًا فقط ولا يوقف التشغيل. حارس البيئة
    STUDIO_ENV_RESTORED يمنع إعادة تشغيل سكربت الاستعادة في
    الاستدعاءات المتداخلة؛ أما فحص الخادم فرخيص فيُعاد كل مرة.
    """
    import shutil
    home = os.path.expanduser("~")
    for d in (os.path.join(home, ".local", "bin"),
              os.path.join(home, ".npm-global", "bin")):
        if os.path.isdir(d) and d not in os.environ.get("PATH", ""):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    if os.environ.get("STUDIO_ENV_RESTORED") != "1":
        missing = [t for t in _EXPECTED_TOOLS if shutil.which(t) is None]
        unit_missing = not os.path.isfile(_UNIT_FILE)
        if missing or unit_missing:
            script = _SETUP_ENV_SCRIPT
            if not os.path.isfile(script):
                print("تحذير: أدوات غائبة (%s) ولا يوجد سكربت استعادة %s"
                      % (", ".join(missing) or "ملف الخدمة", script))
            else:
                reasons = []
                if missing:
                    reasons.append("أدوات غائبة (%s)" % ", ".join(missing))
                if unit_missing:
                    reasons.append("ملف الخدمة غائب")
                print("تحذير: %s — تشغيل سكربت الاستعادة…"
                      % " و".join(reasons))
                env = dict(os.environ)
                env["STUDIO_ENV_RESTORED"] = "1"
                try:
                    subprocess.run(["/bin/bash", script], env=env, timeout=300,
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, check=False)
                except (OSError, subprocess.TimeoutExpired) as e:
                    print("تحذير: فشلت استعادة البيئة تلقائيًا (%s) — أكمل بدونها"
                          % e)
    _ensure_protection_tools()
    _ensure_omniroute_server()


_OMNIROUTE_URL = "http://127.0.0.1:20128"


def _omniroute_server_up(timeout=2):
    """هل خادم OmniRoute يرد على /api/health؟ (أي حالة دون 500 تعني شغالًا)."""
    try:
        with urllib.request.urlopen(_OMNIROUTE_URL + "/api/health",
                                    timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except Exception:
        return False


def _ensure_omniroute_server():
    """تأكد أن خادم OmniRoute شغال على loopback قبل أي استدعاء ذكاء.

    عيب وُجد في اختبار النظام 2026-11-21: أمر `omniroute chat` ليس
    مستقلًا — هو عميل HTTP للخادم على localhost:20128؛ وإن كان الخادم
    متوقفًا يفشل بصمت (exit 1 بلا أي رسالة خطأ، لأن ApiError يحمل
    exitCode فيُنهي العملية دون طباعة)، فيظن studio أن النماذج
    المجانية معطلة بينما المشكلة أن الخادم متوقف فقط. تحذير فحص
    التحديثات على stderr ضجيج غير قاتل ويُحذف من المخرجات أصلًا.
    الخادم يُشغَّل على 127.0.0.1 فقط (OMNIROUTE_SERVER_HOST) فلا
    ينكشف على الشبكة، ويبقى شغالًا — أمر chat يحتاجه في كل تشغيل.
    best-effort: أي فشل تحذير فقط ولا يوقف التشغيل.
    """
    import shutil
    if _omniroute_server_up():
        return
    if shutil.which("omniroute") is None:
        return
    env = dict(os.environ)
    env["OMNIROUTE_SERVER_HOST"] = "127.0.0.1"
    # إصلاح 2026-11-21 (اختبار اختراق): REQUIRE_API_KEY=true إلزامي —
    # افتراضي حزمة omniroute هو false، وبدونه تقبل /v1/chat/completions
    # طلبات بلا مفتاح. القيمة في ~/.omniroute/.env أيضًا.
    env["REQUIRE_API_KEY"] = "true"
    try:
        subprocess.run(["omniroute", "serve", "--no-open", "--daemon",
                        "--port", "20128"], env=env, timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=False)
    except (OSError, subprocess.TimeoutExpired):
        print("تحذير: تعذّر تشغيل خادم OmniRoute")
        return
    for _ in range(30):
        time.sleep(2)
        if _omniroute_server_up():
            print("خادم OmniRoute شغال على 127.0.0.1:20128")
            return
    print("تحذير: خادم OmniRoute لم يرد بعد تشغيله — قد يفشل توليد السيناريو")


def _ensure_protection_tools():
    """أصلح أدوات الحماية وقاعدة ClamAV في الخلفية إن غابت (best-effort).

    إصلاح دائم 2026-11-21: أدوات الحماية الست وقاعدة ClamAV تُمسح مع كل
    ريستارت VM، ولم يكن أي مسار تلقائي يعيدها (setup-env.sh لا يشملها،
    وخطافا الشل يعيدان ملف الخدمة فقط). هذه الدالة تفحصها في كل تشغيل،
    وإن غاب شيء أطلقت حارس البيئة ensure-env.sh --apt-only منفصلًا في
    الخلفية (مع قفل flock يمنع التكرار) وأكملت التشغيل فورًا — أدوات
    الحماية ليست في مسار النشر الحرج، فلا معنى لحظر النشر دقائق في
    انتظار apt. أي فشل صامت ولا يوقف التشغيل أبدًا.
    """
    import glob
    import shutil
    missing = [t for t in _PROTECTION_TOOLS if shutil.which(t) is None]
    db_missing = (not glob.glob(os.path.join(_CLAMAV_DB_DIR, "*.cvd"))
                  and not glob.glob(os.path.join(_CLAMAV_DB_DIR, "*.cld")))
    if not missing and not db_missing:
        return
    script = _ENSURE_ENV_SCRIPT
    if not os.path.isfile(script):
        return
    try:
        subprocess.Popen(
            ["/bin/bash", script, "--apt-only"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, start_new_session=True,
            close_fds=True)
        print("تحذير: أدوات حماية غائبة (%s)%s — إطلاق إصلاحها في الخلفية"
              % (", ".join(missing) or "لا شيء",
                 " وقاعدة ClamAV غائبة" if db_missing else ""))
    except OSError:
        pass


def shutil_which(cmd):
    import shutil
    return shutil.which(cmd) is not None


# ---------------------------------------------------------------- script
SCRIPT_PROMPT = (
    "اكتب عنوان هوك صادم من 8 كلمات بالعامية المصرية لفيديو قصة قصيرة "
    "بعبرة عن: {story}. ثم سطرًا واحدًا كابشن تشويقي لا يكشف النهاية. "
    "أرجع العنوان في السطر الأول والكابشن في السطر الثاني فقط."
)

STORY_TEXTS = {
    "anza": ("عنزة صغيرة ادّعى شيخ أنها معجزة إلهية في القاهرة سنة 1184، "
             "والناس بتركع لها وتجيب لها فستق ولوز وذهب"),
}

FALLBACK_TITLES = {
    # بديل موثق عند فشل OmniRoute: هوك من سيناريو OpenMontage الجاهز.
    # خاص بقصة العنزة فقط؛ أي قصة أخرى لها بديل عام من وصفها.
    "anza": ("عنزة صغيرة بقت أشهر مخلوق في القاهرة!",
             "سنة 1184… عنزة صغيرة بقت أشهر مخلوق في "
             "القاهرة، والناس كانت بتركع لها!"),
}


def _fallback_script(story):
    """هوك/كابشن بديل عند فشل OmniRoute — خاص بالقصة لا عامًا."""
    if story in FALLBACK_TITLES:
        return FALLBACK_TITLES[story]
    desc = STORY_TEXTS.get(story, story)
    return ("قصة حقيقية بعبرة عن: %s" % desc,
            "قصة قصيرة حقيقية عن %s — والنهاية أغرب مما تتخيل." % desc)


def cmd_script(cfg, story, allow_fallback, run_dir=None):
    cfg_o = cfg["omniroute"]
    prompt = SCRIPT_PROMPT.format(
        story=STORY_TEXTS.get(story, story))
    t0 = time.time()
    try:
        text, via, model = omniroute_client.chat(
            prompt, cfg_o["model"], cfg_o.get("fallback_model"),
            cfg_o["base_url"], max_tokens=200, temperature=0.7,
            retries=int(cfg_o.get("retries", 1)),
            retry_delay=int(cfg_o.get("retry_delay_seconds", 5)))
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        result = {"source": "omniroute", "via": via, "model": model,
                  "title": lines[0] if lines else "",
                  "caption": lines[1] if len(lines) > 1 else "",
                  "raw": text,
                  "seconds": round(time.time() - t0, 1)}
        print("العنوان (عبر %s/%s): %s" % (via, model, result["title"]))
    except omniroute_client.OmniRouteError as e:
        print("فشل استدعاء OmniRoute: %s" % e)
        if not allow_fallback:
            return None, {"source": "omniroute", "status": "failed",
                          "error": str(e),
                          "seconds": round(time.time() - t0, 1)}
        # بديل موثق: هوك من سيناريو OpenMontage الجاهز (خاص بالقصة)
        fb_title, fb_caption = _fallback_script(story)
        result = {"source": "fallback:openmontage-script",
                  "title": fb_title,
                  "caption": fb_caption,
                  "error": str(e),
                  "seconds": round(time.time() - t0, 1)}
        print("استُخدم البديل من سيناريو OpenMontage الجاهز: %s"
              % result["title"])
    if run_dir:
        with open(os.path.join(run_dir, "script-ai.json"), "w",
                  encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    return result, result


# --------------------------------------------------------------- produce
def cmd_produce(cfg, project, run_dir):
    root = expand(cfg["openmontage"]["root"])
    proj_path = openmontage_stage.find_project(root, project)
    manifest = openmontage_stage.stage(
        proj_path, run_dir, cfg["video"]["image_clip_seconds"])
    print("جُهزت %d صورة، سرد %.1f ثانية، %d عبارة كتابة"
          % (len(manifest["images"]), manifest["narration_duration"],
             len(manifest["phrases"])))
    return manifest


# -------------------------------------------------------------- assemble
def cmd_assemble(cfg, run_dir, title, out_path, watermark_on=True,
                 cards_dir=None):
    """تجميع وتصدير، ثم (افتراضيًا) شعار الصفحة أعلى اليمين، ثم
    بطاقات الاقتباس الختامية إن أُعطي مجلدها. البطاقات تحمل الشعار
    أصلًا، فتُلحق بعد الشعار. المدة الكلية المستهدفة 40-60 ثانية:
    المحتوى 31-51 ثانية + 9 ثوانٍ بطاقات.
    """
    manifest_path = os.path.join(run_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise concat_mcp.ConcatError("ملف البيان غير موجود — شغّل "
                                     "produce أولًا: %s" % manifest_path)
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    assets_dir = os.path.join(run_dir, "assets")
    concat_bin = expand(cfg["concat"]["bin"])
    if not os.path.isfile(concat_bin):
        raise concat_mcp.ConcatError("ثنائي Concat غير موجود: %s"
                                     % concat_bin)
    projects_root = expand(cfg["concat"]["projects_dir"])
    project_name = "studio-" + os.path.basename(run_dir.rstrip("/"))
    log_path = os.path.join(run_dir, "concat-mcp.jsonl")
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    out = concat_mcp.assemble(
        concat_bin, projects_root, project_name, assets_dir, manifest,
        title, out_path, cfg["video"], log_path)
    print("صُدّر الفيديو: %s (%.0f ثانية تصدير)"
          % (out, time.time() - t0))
    out = _finish_video(out, watermark_on, cards_dir)
    return out, round(time.time() - t0, 1)


def _finish_video(out_path, watermark_on=True, cards_dir=None):
    """خطوة الإنهاء المشتركة لكل الخلفيات: شعار ثم بطاقات ختامية."""
    out = out_path
    if watermark_on:
        t0 = time.time()
        watermark.apply_watermark(out, out)
        print("أُضيف شعار الصفحة أعلى اليمين (%.0f ثانية)"
              % (time.time() - t0))
    if cards_dir:
        cards = watermark.find_cards(cards_dir)
        t0 = time.time()
        tmp = out + ".cards-tmp.mp4"
        watermark.append_quote_cards(out, cards, tmp)
        os.replace(tmp, out)
        print("أُلحقت %d بطاقات اقتباس ختامية (%.0f ثانية)"
              % (len(cards), time.time() - t0))
    return out


def cmd_assemble_headless(cfg, run_dir, title, out_path,
                          watermark_on=True, cards_dir=None):
    """تجميع عبر نواة headless-editor (خلفية بديلة لـConcat).

    يبني مشروع JSON من البيان ويستدعي `editor.py render`؛ يحفظ
    المشروع في run_dir/headless-project.json. Concat يبقى الافتراضي.
    """
    manifest_path = os.path.join(run_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise headless_stage.HeadlessError(
            "ملف البيان غير موجود — شغّل produce أولًا: %s"
            % manifest_path)
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    assets_dir = os.path.join(run_dir, "assets")
    editor_path = expand(cfg["headless"]["editor"])
    project_path = os.path.join(run_dir, "headless-project.json")
    project = headless_stage.build_project(manifest, title, assets_dir,
                                           cfg["video"])
    with open(project_path, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    result = headless_stage.render_project(editor_path, project_path,
                                           out_path)
    print("صُدّر الفيديو عبر headless-editor: %s (%.0f ثانية ريندر، "
          "%.1f ميجا)" % (result["output"], result["seconds"],
                          result["size_bytes"] / (1024 * 1024)))
    out = _finish_video(result["output"], watermark_on, cards_dir)
    return out, result["seconds"]


def cmd_assemble_mlt(cfg, run_dir, title, out_path,
                     watermark_on=True, cards_dir=None):
    """تجميع عبر MLT/melt (خلفية بديلة لـConcat — تايم لاين XML).

    يبني ملف .mlt من البيان ويستدعي `melt`؛ يحفظ المشروع في
    run_dir/mlt-project.mlt (يُفتح في Kdenlive/Shotcut لاحقًا).
    Concat يبقى الافتراضي.
    """
    manifest_path = os.path.join(run_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise mlt_stage.MltError(
            "ملف البيان غير موجود — شغّل produce أولًا: %s"
            % manifest_path)
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    assets_dir = os.path.join(run_dir, "assets")
    # قص الصور لتملأ الإطار (بلا أشرطة سوداء) — نسخ بمقاس الإطار
    # في run_dir/mlt-images بجانب ملف .mlt.
    fill_dir = os.path.join(run_dir, "mlt-images")
    mlt_stage.prepare_fill_images(
        manifest, assets_dir, fill_dir,
        int(cfg["video"]["width"]), int(cfg["video"]["height"]))
    mlt_path = os.path.join(run_dir, "mlt-project.mlt")
    xml_text = mlt_stage.build_mlt(manifest, title, assets_dir,
                                   cfg["video"], images_dir=fill_dir)
    with open(mlt_path, "w", encoding="utf-8") as f:
        f.write(xml_text)
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    result = mlt_stage.render_mlt(mlt_path, out_path)
    print("صُدّر الفيديو عبر MLT/melt: %s (%.0f ثانية ريندر، %.1f ميجا)"
          % (result["output"], result["seconds"],
             result["size_bytes"] / (1024 * 1024)))
    out = _finish_video(result["output"], watermark_on, cards_dir)
    return out, result["seconds"]


# ------------------------------------------------------------ clean-audio
def cmd_clean_audio(cfg, input_path, output_path, threshold, margin, force):
    """قص صمت الصوت الخام عبر Auto-Editor (خطوة اختيارية).

    للصوت الخام قبل التجميع فقط — أبدًا على السرد النهائي
    (وقفاته مقصودة دراميًا). يطبع تحذيرًا بذلك في كل تشغيل.
    """
    print("تحذير: هذه الخطوة للصوت الخام فقط — لا تستخدمها على السرد "
          "النهائي (وقفاته مقصودة دراميًا والكتابة مبنية عليها).")
    try:
        import subprocess as _sp
        before = _sp.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", input_path],
            capture_output=True, text=True, timeout=30)
        dur_before = float(before.stdout.strip())
    except Exception:
        dur_before = None
    result = autoedit.clean_audio(
        input_path, output_path, threshold=threshold, margin=margin,
        force=force,
        studio_dir=os.path.dirname(os.path.abspath(__file__)))
    try:
        import subprocess as _sp
        after = _sp.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", output_path],
            capture_output=True, text=True, timeout=30)
        dur_after = float(after.stdout.strip())
    except Exception:
        dur_after = None
    if dur_before is not None and dur_after is not None:
        print("نُظّف الصوت: %.2f ث ← %.2f ث (%.1f ثانية عمل)"
              % (dur_before, dur_after, result["seconds"]))
    else:
        print("نُظّف الصوت: %s (%.1f ثانية عمل)"
              % (result["output"], result["seconds"]))
    return result


# ------------------------------------------------------------ fx
def cmd_fx(cfg, image, output, duration, text, audio, zoom_to, fontsize):
    """تركيبة MoviePy اختيارية: Ken Burns + نص عربي متحرك + صوت.

    يعمل فقط من بيئة MoviePy (والا فشل برسالة واضحة).
    """
    result = moviepy_fx.render_fx(
        image, output, duration, text=text, audio_path=audio,
        zoom_to=zoom_to, fontsize=fontsize)
    print("رُكّبت التركيبة: %s (%.1f ثانية عمل، %.1f ميجا)"
          % (result["output"], result["seconds"],
             result["size_bytes"] / 1024 / 1024))
    return result


# ------------------------------------------------------------ karaoke-ass
def cmd_karaoke_ass(cfg, audio, ass_path, model, max_chars):
    """كابشنات كاريوكي (كلمة-بكلمة) من faster-whisper — منطق Capite
    مُعاد تنفيذه (انظر lib/capite_captions.py). خيار تجريبي فقط؛
    راجع النص قبل النشر (small يخطئ في ~22% من الكلمات)."""
    groups, text = capite_captions.karaoke_ass(
        audio, ass_path, model=model, max_chars=max_chars)
    n_words = sum(len(ln) for g in groups for ln in g["lines"])
    print("كُتبت %d كلمة في %d مجموعة في %s"
          % (n_words, len(groups), ass_path))
    print("النص المسموع: %s" % text)
    print("راجع النص قبل النشر — حتى موديل small يخطئ في ~22% من "
          "كلمات سرد Piper (WHISPER-TEST.md).")
    return groups


# ------------------------------------------------------------ trim
def cmd_trim(cfg, input_path, output_path, start, end, duration, exact):
    """قص مقطع بلا إعادة ترميز (ما يعادل LosslessCut تحت الغطاء).

    البداية/النهاية تلتصق بحدود الإطارات (±~0.2 ث)؛ --exact
    يعيد الترميز لقطع دقيق بالإطار.
    """
    result = trim.trim_lossless(input_path, output_path, start=start,
                                end=end, duration=duration, exact=exact)
    got = result["out_duration"]
    print("قُصّ المقطع: %s (المطلوب %.2f ث، الناتج %.2f ث، %.1f ثانية "
          "عمل)%s"
          % (result["output"], result["duration"],
             got if got is not None else -1, result["seconds"],
             " — إعادة ترميز دقيقة" if exact else " — بلا إعادة ترميز"))
    if not exact:
        print("ملحوظة: القص بلا إعادة ترميز يلتصق بحدود الإطارات "
              "(±~0.2 ث)؛ استخدم --exact لقطع دقيق بالإطار.")
    return result


# ------------------------------------------------------------ thumbnail
def cmd_thumbnail(cfg, video_path, hook, out_path, at_seconds=None,
                  width=thumbnail.WIDTH, height=thumbnail.HEIGHT,
                  fontsize=thumbnail.FONTSIZE,
                  margin_v=thumbnail.MARGIN_V, max_chars=20):
    out, at, lines = thumbnail.make_thumbnail(
        video_path, hook, out_path, at_seconds, width=width, height=height,
        fontsize=fontsize, margin_v=margin_v, max_chars=max_chars)
    w, h = thumbnail.probe_image(out)
    print("صورة مصغرة: %s (%dx%d، لقطة عند %.1f ثانية)" % (out, w, h, at))
    print("نص الهوك: %s" % " / ".join(lines))
    return out


# ------------------------------------------------------------------- run
def cmd_run(cfg, story, project, out_path, allow_fallback, dry_run=False,
            backend="concat", watermark_on=True, cards_dir=None):
    runs_dir = expand(cfg["paths"]["runs_dir"])
    if backend not in ("concat", "headless", "mlt"):
        print("خلفية التجميع غير معروفة: %s (المسموح: concat/headless/mlt)"
              % backend)
        return 1
    if dry_run:
        # وضع تجريبي: يطبع ما سيفعله التشغيل دون استدعاء أي طبقة.
        root = expand(cfg["openmontage"]["root"])
        proj = os.path.join(root, "projects", project)
        print("== وضع تجريبي — لن يُستدعى OmniRoute ولا Concat ولا OpenMontage ==")
        print("1) سيناريو: story=%s عبر %s (بديل: %s؛ إعادة محاولة: %s)"
              % (story, cfg["omniroute"]["model"],
                 cfg["omniroute"].get("fallback_model"),
                 cfg["omniroute"].get("retries", 1)))
        print("   البديل عند الفشل: %s"
              % ("مسموح (هوك من السيناريو الجاهز)"
                 if allow_fallback else "غير مسموح — يتوقف عند الفشل"))
        print("2) إنتاج: مشروع OpenMontage %s — %s"
              % (proj, "موجود" if os.path.isdir(proj) else "غير موجود!"))
        print("3) تجميع (%s): تصدير إلى %s — مقاس %dx%d"
              % (backend, out_path,
                 int(cfg["video"]["width"]), int(cfg["video"]["height"])))
        print("4) شعار الصفحة أعلى اليمين: %s"
              % ("نعم (تلقائي)" if watermark_on else "لا (--no-watermark)"))
        print("5) بطاقات اقتباس ختامية (3×3 ثوانٍ): %s"
              % (cards_dir or "لا — مرّر --cards-dir بمجلد البطاقات"))
        if backend == "concat":
            print("   ثنائي Concat: %s — %s"
                  % (expand(cfg["concat"]["bin"]),
                     "موجود" if os.path.isfile(expand(cfg["concat"]["bin"]))
                     else "غير موجود!"))
        elif backend == "headless":
            print("   محرر headless: %s — %s"
                  % (expand(cfg["headless"]["editor"]),
                     "موجود"
                     if os.path.isfile(expand(cfg["headless"]["editor"]))
                     else "غير موجود!"))
        else:
            print("   ثنائي melt: %s"
                  % ("موجود" if shutil_which("melt") else "غير موجود!"))
        print("   مجلد التشغيل: %s/<story>-<وقت>/" % runs_dir)
        return 0
    run_id, run_dir = new_run(runs_dir, story)
    log = {"run": run_id, "story": story, "project": project,
           "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "steps": {},
           "cost_usd": 0.0}
    print("تشغيل: %s" % run_id)
    try:
        # 1) السيناريو عبر OmniRoute (مع بديل موثق عند الفشل)
        result, step = cmd_script(cfg, story, allow_fallback, run_dir)
        log["steps"]["script"] = step
        if result is None:
            raise RuntimeError("توقف خط الإنتاج: فشل توليد السيناريو "
                               "وبلا بديل مسموح")
        title = result["title"]
        # 2) الإنتاج: تجهيز أصول OpenMontage
        t0 = time.time()
        manifest = cmd_produce(cfg, project, run_dir)
        log["steps"]["produce"] = {"status": "ok",
                                   "seconds": round(time.time() - t0, 1),
                                   "images": len(manifest["images"]),
                                   "phrases": len(manifest["phrases"])}
        # 3) التجميع والتصدير (Concat افتراضيًا، أو headless-editor أو MLT)
        #    ثم شعار الصفحة وبطاقات الاقتباس الختامية (داخل assemble).
        t0 = time.time()
        if backend == "headless":
            out, secs = cmd_assemble_headless(
                cfg, run_dir, title, out_path, watermark_on, cards_dir)
        elif backend == "mlt":
            out, secs = cmd_assemble_mlt(
                cfg, run_dir, title, out_path, watermark_on, cards_dir)
        else:
            out, secs = cmd_assemble(cfg, run_dir, title, out_path,
                                     watermark_on, cards_dir)
        log["steps"]["assemble"] = {"status": "ok", "seconds": secs,
                                    "backend": backend, "output": out}
        log["status"] = "done"
        print("اكتمل خط الإنتاج: %s" % out)
    except Exception as e:
        log["status"] = "failed"
        log["error"] = str(e)
        print("فشل خط الإنتاج: %s" % e)
        write_log(run_dir, log)
        return 1
    write_log(run_dir, log)
    return 0


# ---------------------------------------------------------------- doctor
def cmd_doctor(cfg, fix=False):
    """فحص بيئة studio (تقرير PASS/FAIL صادق). --fix ينشئ config.yaml."""
    here = os.path.dirname(os.path.abspath(__file__))
    if fix and doctor.ensure_config(here):
        print("أُنشئ config.yaml من المثال")
    checks = doctor.run_checks(cfg)
    text, errors, warnings = doctor.format_report(checks)
    print(text)
    return 0 if errors == 0 else 1


# ------------------------------------------------------------------- demo
def cmd_demo(cfg, out_path=None, backend="headless"):
    """نفّذ القصة التجريبية المدمجة (مسار مجاني فقط)."""
    if out_path is None:
        out_path = os.path.join(
            expand(cfg["paths"]["videos_dir"]),
            "demo-%s.mp4" % time.strftime("%Y%m%d-%H%M%S"))
    result = demo.run_demo(cfg, expand(out_path), backend=backend)
    print("فيديو التجربة: %s (%.1f ثانية، %d مشاهد، %.1f ميجا، "
          "%.0f ثانية ريندر)"
          % (result["output"], result["duration"],
             len(demo.load_demo()["scenes"]),
             result["size_bytes"] / (1024 * 1024), result["seconds"]))
    print("العنوان: %s" % result["title"])
    print("الهوك: %s" % result["hook"])
    print("العبرة: %s" % result["moral"])
    return result


# ---------------------------------------------------------------- publish
YT_DEFAULT_TAGS = ["قصص وعبر", "قصص واقعية", "قصص مؤثرة", "حكايات"]


def cmd_publish(cfg, video, title, caption, thumbnail=None,
                platforms=("facebook", "youtube"), page_id=None,
                schedule=None, privacy=None, tags=None, dry_run=False):
    """انشر فيديوًا واحدًا على فيسبوك و/أو يوتيوب.

    يرجع 0 فقط إن نُشر على كل المنصات المطلوبة فعلًا؛ وإن نُشر بعضها
    فقط (أو كُتبت حزمة يوتيوب اليدوية بدل الرفع) يرجع 1 مع شرح
    ما بقي. --dry-run يطبع الحمولة الدقيقة دون نشر أي شيء.
    """
    video = expand(video)
    if not os.path.isfile(video):
        print("ملف الفيديو غير موجود: %s" % video)
        return 1
    if schedule and int(schedule) <= int(time.time()):
        print("موعد الجدولة في الماضي — يجب أن يكون في المستقبل")
        return 1
    page_id = page_id or cfg.get("publish", {}).get("page_id") or ""
    privacy = privacy or cfg.get("publish", {}).get("youtube_privacy") \
        or "public"
    tags = tags if tags is not None else list(YT_DEFAULT_TAGS)
    try:
        fb_caption = publish.build_caption(title, caption)
        yt_desc = publish.build_youtube_description(title, caption)
        yt_title = publish.build_youtube_title(title)
    except publish.PublishError as e:
        print("خطأ في بيانات النشر: %s" % e)
        return 1
    thumb = expand(thumbnail) if thumbnail else None
    if thumb and not os.path.isfile(thumb):
        print("ملف الصورة المصغرة غير موجود: %s" % thumb)
        return 1
    if dry_run:
        print("== وضع تجريبي — لن يُنشر شيء ==")
        if "facebook" in platforms:
            try:
                argv = publish.facebook_argv(page_id, video, fb_caption,
                                             schedule)
            except publish.PublishError as e:
                print("فيسبوك: لا يمكن بناء الأمر — %s" % e)
                return 1
            import shlex
            print("-- فيسبوك (Reel على الصفحة %s):" % (page_id or "?"))
            print("   " + " ".join(shlex.quote(a) for a in argv))
            print("   الكابشن (%d حرفًا):" % len(fb_caption))
            print("   " + fb_caption.replace("\n", "\n   "))
        if "youtube" in platforms:
            payload = publish.youtube_payload(
                yt_title, yt_desc, tags, privacy, schedule,
                thumbnail=thumb)
            print("-- يوتيوب (videos.insert):")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    ok = True
    if "facebook" in platforms:
        try:
            res = publish.post_facebook(page_id, video, fb_caption,
                                        schedule)
            print("فيسبوك: %s (post_id=%s)"
                  % ("مجدول" if res["state"] == "scheduled" else "نُشر",
                     res["post_id"]))
        except publish.PublishError as e:
            print("فيسبوك: فشل — %s" % e)
            ok = False
    if "youtube" in platforms:
        token = expand(cfg.get("publish", {}).get("youtube_token") or
                       "~/workspace/studio/youtube-token.json")
        if os.path.isfile(token):
            try:
                res = publish.upload_youtube(
                    video, yt_title, yt_desc, tags, privacy, schedule,
                    thumbnail=thumb, token=token)
                print("يوتيوب: رُفع — %s" % res["url"])
            except publish.PublishError as e:
                print("يوتيوب: فشل — %s" % e)
                ok = False
        else:
            bundle_dir = os.path.join(
                expand(cfg["paths"]["videos_dir"]),
                "publish-%s-youtube"
                % time.strftime("%Y%m%d-%H%M%S"))
            bundle = publish.write_youtube_bundle(
                bundle_dir, video, yt_title, yt_desc, tags, privacy,
                schedule, thumbnail=thumb)
            print("يوتيوب: بلا بيانات اعتماد — لم يُرفع شيء.")
            print("حزمة الرفع اليدوي جاهزة في: %s" % bundle)
            print("اتبع steps.txt داخل الحزمة، أو أكمل "
                  "`studio.py youtube-auth` ثم أعد الأمر.")
            ok = False
    return 0 if ok else 1


def cmd_youtube_auth(cfg, client_secrets=None, token=None):
    """تبادل OAuth ليوتيوب لمرة واحدة (يفتح المتصفح)."""
    venv_python = publish.youtube_venv_python()
    if not venv_python:
        print("بيئة YouTube غير موجودة (.venv-youtube) — شغّل setup.sh أولًا")
        return 1
    secrets = expand(client_secrets or
                     cfg.get("publish", {}).get("youtube_client_secrets")
                     or "~/workspace/studio/client_secrets.json")
    token = expand(token or cfg.get("publish", {}).get("youtube_token")
                   or "~/workspace/studio/youtube-token.json")
    if not os.path.isfile(secrets):
        print("ملف client_secrets غير موجود: %s" % secrets)
        print("أنشئ مشروعًا في Google Cloud Console وفعّل YouTube "
              "Data API v3، ثم حمّل client_secrets.json (انظر README).")
        return 1
    uploader = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "lib", "youtube_upload.py")
    print("سيُفتح المتصفح لتسجيل الدخول بحساب يوتيوب…")
    try:
        proc = subprocess.run(
            [venv_python, uploader, "auth",
             "--client-secrets", secrets, "--token", token],
            timeout=300)
    except subprocess.TimeoutExpired:
        print("انتهت مهلة تبادل OAuth (300 ثانية) — أعد المحاولة "
              "والمتصفح مفتوح")
        return 1
    return proc.returncode


# ---------------------------------------------------------- long-narration
def cmd_long_narration(cfg, text, text_file, out_path, gap, atempo,
                       voice="piper"):
    """سرد طويل مقسّم إلى WAV واحد (Piper رجل افتراضيًا؛ أو gTTS)."""
    if text_file:
        with open(expand(text_file), encoding="utf-8") as f:
            text = f.read()
    result = long_narration.synthesize_long(
        text, expand(out_path), gap=gap, atempo=atempo, voice=voice)
    print("سرد طويل (%s): %s (%.1f ثانية، %d جملة)"
          % (voice, result["output"], result["duration"],
             len(result["chunks"])))
    return result


# -------------------------------------------------------------- long-video
PAGE_URL = "https://www.facebook.com/1048148471706586"
DEFAULT_LONG_OUTRO = "اشترك في القناة عشان قصة الجمعة الجاية توصلك"


def _long_video_known_projects():
    """خريطة slug القصة → اسم مشروع OpenMontage (من KNOWN_PROJECTS)."""
    return {slug: project for _, (slug, project) in KNOWN_PROJECTS.items()}


def _stage_project_chapter(cfg, project_name, work_dir, title=None,
                           moral=""):
    """جهّز مشروع OpenMontage وابنِ منه فصلًا (بيان + أصول)."""
    root = expand(cfg["openmontage"]["root"])
    proj_path = openmontage_stage.find_project(root, project_name)
    chapter_dir = os.path.join(work_dir, "staged", project_name)
    os.makedirs(chapter_dir, exist_ok=True)
    manifest = openmontage_stage.stage(
        proj_path, chapter_dir, cfg["video"]["image_clip_seconds"])
    assets_dir = os.path.join(chapter_dir, "assets")
    return long_video.chapter_from_manifest(manifest, assets_dir,
                                            title=title, moral=moral)


def _run_chapter(cfg, run_id, title=None, moral=""):
    """ابنِ فصلًا من مجلد تشغيل سابق (manifest.json + assets/)."""
    runs_dir = expand(cfg["paths"]["runs_dir"])
    run_dir = run_dir_for(runs_dir, run_id)
    manifest_path = os.path.join(run_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise long_video.LongVideoError(
            "لا يوجد بيان في التشغيل: %s" % run_dir)
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    assets_dir = os.path.join(run_dir, "assets")
    return long_video.chapter_from_manifest(manifest, assets_dir,
                                            title=title, moral=moral)


def _resolve_long_chapter(cfg, entry, work_dir, atempo, index, voice="piper"):
    """حوّل مدخل فصل واحد (من ملف الفصول أو CLI) إلى قاموس فصل."""
    kind = entry.get("type")
    title = entry.get("title")
    moral = entry.get("moral") or ""
    if kind == "story":
        slug = entry["story"]
        known = _long_video_known_projects()
        if slug in known:
            project = known[slug]
        else:
            # جرّب مشروعًا بنفس اسم القصة قبل الفشل
            root = expand(cfg["openmontage"]["root"])
            try:
                openmontage_stage.find_project(root, slug)
            except (openmontage_stage.StageError, ValueError) as e:
                raise long_video.LongVideoError(
                    "لا يوجد مشروع OpenMontage جاهز لقصة %s (%s) — "
                    "جهّز مشروعها أولًا أو استخدم --chapter-dir"
                    % (slug, e))
            project = slug
        return _stage_project_chapter(cfg, project, work_dir,
                                      title=title, moral=moral)
    if kind == "project":
        return _stage_project_chapter(cfg, entry["project"], work_dir,
                                      title=title, moral=moral)
    if kind == "run":
        return _run_chapter(cfg, entry["run"], title=title, moral=moral)
    if kind == "chapter-dir":
        return long_video.load_chapter_dir(
            expand(entry["path"]),
            work_dir=os.path.join(work_dir, "chapters", "ch%d" % index),
            atempo=atempo, title=title, moral=moral or None)
    if kind == "text":
        text = entry.get("text")
        if entry.get("text_file"):
            with open(expand(entry["text_file"]), encoding="utf-8") as f:
                text = f.read()
        if not text or not text.strip():
            raise long_video.LongVideoError(
                "الفصل النصي بلا نص: %s" % (title or "?"))
        images = [expand(p) for p in entry.get("images", [])]
        if entry.get("cover"):
            images = [expand(entry["cover"])] + images
        if not images:
            raise long_video.LongVideoError(
                "الفصل النصي بلا صور (cover أو images): %s" % title)
        wav = os.path.join(work_dir, "narration",
                           "text-chapter-%d.wav" % index)
        os.makedirs(os.path.dirname(wav), exist_ok=True)
        info = long_narration.synthesize_long(text, wav, atempo=atempo,
                                              voice=voice)
        return long_video.chapter_from_text(title, text, info, images,
                                            moral=moral)
    raise long_video.LongVideoError(
        "نوع فصل غير معروف: %s (المسموح: story/project/run/"
        "chapter-dir/text)" % kind)


def _loop_music_to_cover(music, total, run_dir):
    """كرّر ملف موسيقى أقصر من الفيديو حتى يغطي مدته.

    نواة headless ترفض مقطعًا صوتيًا أقصر من مدته المطلوبة،
    فالموسيقى القصيرة تُكرَّر (loop) إلى ملف عمل. يرجع المسار المستخدم.
    """
    dur = long_narration.probe_duration(music)
    if dur >= total:
        return music
    looped = os.path.join(run_dir, "music-loop.wav")
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1",
                        "-i", music, "-t", str(total), looped],
                       capture_output=True, text=True, timeout=300,
                       check=True)
    except subprocess.CalledProcessError as e:
        raise long_video.LongVideoError(
            "فشل تكرار الموسيقى الخلفية: %s" % (e.stderr or "")[-300:])
    print("الموسيقى الخلفية أقصر من الفيديو (%.1f ث < %.1f ث) — كُرّرت"
          % (dur, total))
    return looped


def cmd_long_video(cfg, args):
    """فيديو طويل أفقي 1280×720 من عدة فصول (8–12 دقيقة)."""
    runs_dir = expand(cfg["paths"]["runs_dir"])
    run_id, run_dir = new_run(runs_dir, "long-video")
    log = {"run": run_id, "cmd": "long-video",
           "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "steps": {}}
    print("تشغيل الفيديو الطويل: %s" % run_id)
    try:
        spec = {}
        if args.chapters_file:
            with open(expand(args.chapters_file), encoding="utf-8") as f:
                spec = json.load(f)
            if not isinstance(spec, dict):
                raise long_video.LongVideoError(
                    "ملف الفصول يجب أن يكون كائن JSON")
        # --auto-week: قصص الأسبوع من ملف الطابور بدل التجميع اليدوي.
        if getattr(args, "auto_week", False):
            if (args.story or args.project or args.run_id
                    or args.chapter_dir or args.chapter_text
                    or args.chapters_file):
                raise long_video.LongVideoError(
                    "لا يُجمع --auto-week مع مصادر فصول يدوية "
                    "(--story/--project/--run/--chapter-dir/"
                    "--chapter-text/--chapters-file)")
            since = None
            if getattr(args, "since", None):
                try:
                    since = datetime.date.fromisoformat(args.since)
                except ValueError:
                    raise long_video.LongVideoError(
                        "--since بصيغة YYYY-MM-DD (وصل: %s)" % args.since)
            queue_path = expand(getattr(args, "queue_file", None)
                                or cfg["paths"]["queue_file"])
            try:
                usable, skipped = autoweek.pick_week_stories(
                    queue_path, cfg, KNOWN_PROJECTS, since=since)
            except autoweek.AutoWeekError as e:
                raise long_video.LongVideoError(str(e))
            print("قصص الأسبوع (%d):" % len(usable))
            for u in usable:
                print("  - %s (%s)" % (u["title"],
                      u["date"].strftime("%Y-%m-%d")))
            for s in skipped:
                print("  تُتخطى: %s — %s" % (s["title"], s["reason"]))
            spec = {"chapters": [
                {"type": u["type"],
                 ("story" if u["type"] == "story" else
                  "project" if u["type"] == "project" else "path"):
                     u["source"], "title": u["title"]}
                for u in usable]}
            if not args.title:
                args.title = "قصص الأسبوع | القصة الكاملة"
            if not args.hook:
                args.hook = "قصص الأسبوع كاملة — اسمعهم ورا بعض"
        title = args.title or spec.get("title")
        if not title:
            raise long_video.LongVideoError("عنوان الفيديو الطويل مطلوب")
        hook = args.hook or spec.get("hook") or title
        intro_text = args.intro or spec.get("intro") or hook
        outro_text = args.outro or spec.get("outro") or DEFAULT_LONG_OUTRO
        music = None
        if args.music:
            music = expand(args.music)
        elif spec.get("music"):
            music = expand(spec["music"])
        else:
            # الموسيقى المدمجة افتراضيًا (شوبان — ملكية عامة)؛
            # long_video.default_music في الإعداد يتجاوزها، و"none"
            # تلغيها.
            cfg_music = (cfg.get("long_video") or {}).get("default_music")
            if cfg_music == "none":
                music = None
            elif cfg_music:
                music = expand(cfg_music)
            elif os.path.isfile(DEFAULT_MUSIC):
                music = DEFAULT_MUSIC
                print("الموسيقى الخلفية الافتراضية: %s" % music)
        entries = list(spec.get("chapters", []))
        for slug in args.story:
            entries.append({"type": "story", "story": slug})
        for proj in args.project:
            entries.append({"type": "project", "project": proj})
        for run in args.run_id:
            entries.append({"type": "run", "run": run})
        for d in args.chapter_dir:
            entries.append({"type": "chapter-dir", "path": d})
        if len(args.text_file) != len(args.chapter_text):
            raise long_video.LongVideoError(
                "عدد --text-file (%d) يجب أن يساوي عدد --chapter-text (%d)"
                % (len(args.text_file), len(args.chapter_text)))
        if args.cover and len(args.cover) != len(args.chapter_text):
            raise long_video.LongVideoError(
                "عدد --cover (%d) يجب أن يساوي عدد --chapter-text (%d)"
                % (len(args.cover), len(args.chapter_text)))
        if args.moral and len(args.moral) != len(args.chapter_text):
            raise long_video.LongVideoError(
                "عدد --moral (%d) يجب أن يساوي عدد --chapter-text (%d)"
                % (len(args.moral), len(args.chapter_text)))
        for i, (ct, tf) in enumerate(zip(args.chapter_text,
                                         args.text_file)):
            entry = {"type": "text", "title": ct, "text_file": tf}
            if args.cover:
                entry["cover"] = args.cover[i]
            if args.moral:
                entry["moral"] = args.moral[i]
            entries.append(entry)
        if not entries:
            raise long_video.LongVideoError(
                "لا توجد فصول — مرّر --story أو --project أو --run أو "
                "--chapter-dir أو --chapter-text أو --chapters-file")
        # 1) الفصول
        chapters = []
        for i, entry in enumerate(entries):
            t0 = time.time()
            ch = _resolve_long_chapter(cfg, entry, run_dir, args.atempo, i,
                                       voice=getattr(args, "voice", "piper"))
            chapters.append(ch)
            print("فصل %d: %s (%.1f ثانية، %d عبارة)"
                  % (i + 1, ch["title"], ch["duration"],
                     len(ch.get("phrases", []))))
            log["steps"]["chapter-%d" % (i + 1)] = {
                "status": "ok", "seconds": round(time.time() - t0, 1),
                "title": ch["title"], "duration": ch["duration"]}
        # 2) سرد المقدمة والخاتمة (Piper مقسّم افتراضيًا؛ أو gTTS)
        narr_dir = os.path.join(run_dir, "narration")
        os.makedirs(narr_dir, exist_ok=True)
        voice = getattr(args, "voice", "piper")
        intro_info = long_narration.synthesize_long(
            intro_text, os.path.join(narr_dir, "intro.wav"),
            atempo=args.atempo, voice=voice)
        outro_info = long_narration.synthesize_long(
            outro_text, os.path.join(narr_dir, "outro.wav"),
            atempo=args.atempo, voice=voice)
        # 3) بناء مشروع headless وريندره أفقيًا
        project, meta = long_video.build_project({
            "title": title, "hook": hook,
            "intro": {"text": intro_text,
                      "narration": intro_info["output"],
                      "duration": intro_info["duration"]},
            "outro": {"text": outro_text,
                      "narration": outro_info["output"],
                      "duration": outro_info["duration"]},
            "chapters": chapters, "music": music,
            "width": 1280, "height": 720,
            "fps": int(cfg["video"]["fps"])})
        if music:
            music = _loop_music_to_cover(
                music, meta["total_duration"], run_dir)
            for track in project["tracks"]:
                if track.get("role") == "background":
                    track["src"] = music
        project_path = os.path.join(run_dir, "long-project.json")
        with open(project_path, "w", encoding="utf-8") as f:
            json.dump(project, f, ensure_ascii=False, indent=2)
        out_path = expand(args.out)
        os.makedirs(os.path.dirname(os.path.abspath(out_path)),
                    exist_ok=True)
        t0 = time.time()
        editor_path = expand(cfg["headless"]["editor"])
        result = headless_stage.render_project(editor_path, project_path,
                                               out_path, timeout=1800)
        print("صُدّر الفيديو الطويل عبر headless-editor: %s "
              "(%.0f ثانية ريندر، %.1f ميجا)"
              % (result["output"], result["seconds"],
                 result["size_bytes"] / (1024 * 1024)))
        # 4) الشعار فقط (بلا بطاقات اقتباس أبدًا في الفيديو الطويل)
        out = _finish_video(result["output"], not args.no_watermark, None)
        # 5) طوابع الفصول ووصف يوتيوب
        base, _ = os.path.splitext(out_path)
        ts_path = base + "-timestamps.txt"
        desc_path = base + "-description.txt"
        with open(ts_path, "w", encoding="utf-8") as f:
            f.write(long_video.format_timestamps(meta))
        with open(desc_path, "w", encoding="utf-8") as f:
            f.write(long_video.build_description(meta, hook, outro_text,
                                                 PAGE_URL))
        total = meta["total_duration"]
        if total < long_video.TARGET_MIN_SECONDS or \
                total > long_video.TARGET_MAX_SECONDS:
            print("تنبيه: مدة الفيديو %.1f ثانية خارج الهدف 8–12 دقيقة"
                  % total)
        log["status"] = "done"
        log["output"] = out
        log["duration"] = total
        log["timestamps"] = ts_path
        log["description"] = desc_path
        print("اكتمل الفيديو الطويل: %s (%.1f ثانية، %d فصول)"
              % (out, total, len(chapters)))
        print("طوابع الفصول: %s" % ts_path)
        print("وصف يوتيوب: %s" % desc_path)
    except Exception as e:
        log["status"] = "failed"
        log["error"] = str(e)
        print("فشل الفيديو الطويل: %s" % e)
        write_log(run_dir, log)
        return 1
    write_log(run_dir, log)
    return 0


# ------------------------------------------------------------- run-queue
def parse_queue(path):
    """يقرأ قصص «في الانتظار» من ملف الطابور بالترتيب.

    يجمع الأسطر المرقّمة `N. **العنوان**` الواقعة تحت قسم «في
    الانتظار» أو قسم «دفعة ثانية» فقط — فالقسم «المنشور» فيه ترقيم
    أيضًا لكنه ليس انتظارًا. يرجع قائمة قواميس
    {"number": int, "title": str, "note": str}.
    """
    import re
    stories = []
    waiting = False
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("## "):
                heading = line.strip()
                waiting = ("في الانتظار" in heading
                           or "دفعة ثانية" in heading)
                continue
            if not waiting:
                continue
            m = re.match(r"\s*(\d+)\.\s+\*\*(.+?)\*\*\s*(?:—\s*(.*))?$",
                         line.strip())
            if m:
                stories.append({"number": int(m.group(1)),
                                "title": m.group(2).strip(),
                                "note": (m.group(3) or "").strip()})
    return stories


def check_story_ready(cfg, story):
    """هل للقصة مشروع OpenMontage جاهز؟ يرجع
    (جاهزة؟، slug القصة، اسم المشروع، سبب التخطي)."""
    known = KNOWN_PROJECTS.get(story["number"])
    if known is None:
        # محاولة أخيرة: عنوان «العنزة» بأي رقم (لو أُعيد ترقيم الطابور)
        if "العنزة" in story["title"]:
            known = ("anza", "anza-part1")
        else:
            return (False, None, None,
                    "يحتاج تجهيز مشروع — لا يوجد مشروع OpenMontage "
                    "مطابق لهذه القصة بعد")
    slug, project = known
    proj_path = os.path.join(expand(cfg["openmontage"]["projects_dir"]),
                             project)
    if not os.path.isdir(proj_path):
        return (False, slug, project,
                "يحتاج تجهيز مشروع — مجلد المشروع غير موجود: %s"
                % proj_path)
    return (True, slug, project, "")


def cmd_run_queue(cfg, limit=None, continue_on_error=False, dry_run=False,
                  allow_fallback=False):
    """دفعة جماعية من ملف الطابور: القصص الجاهزة تُشغَّل بالتتابع
    عبر cmd_run نفسه؛ بلا مشروع تُتخطى مع تسجيل السبب. النتائج في
    runs/queue-<تاريخ>.json، وتُلحَق خلاصة بتاريخ اليوم في ملف
    الطابور (للتشغيل الحقيقي فقط)."""
    queue_path = expand(cfg["paths"]["queue_file"])
    if not os.path.isfile(queue_path):
        print("ملف الطابور غير موجود: %s" % queue_path)
        return 1
    try:
        stories = parse_queue(queue_path)
    except OSError as e:
        print("تعذر قراءة ملف الطابور: %s" % e)
        return 1
    if limit is not None:
        stories = stories[:limit]
    if not stories:
        print("لا توجد قصص في الانتظار في ملف الطابور")
        return 0
    print("قصص في الانتظار (أول %d):" % len(stories))
    plan = []
    for s in stories:
        ready, slug, project, reason = check_story_ready(cfg, s)
        plan.append({"number": s["number"], "title": s["title"],
                     "ready": ready, "story": slug, "project": project,
                     "reason": reason})
        print("  %d. %s — %s" % (s["number"], s["title"],
              "جاهزة (مشروع %s)" % project if ready
              else "تُتخطى: %s" % reason))
    if dry_run:
        print("وضع تجريبي — لم يُشغَّل شيء ولم يُكتب أي ملف")
        return 0
    runs_dir = expand(cfg["paths"]["runs_dir"])
    os.makedirs(runs_dir, exist_ok=True)
    date = time.strftime("%Y%m%d")
    out_path = os.path.join(runs_dir, "queue-%s.json" % date)
    n = 2
    while os.path.exists(out_path):
        out_path = os.path.join(runs_dir, "queue-%s-%d.json" % (date, n))
        n += 1
    results = {"date": time.strftime("%Y-%m-%d %H:%M:%S"),
               "limit": limit, "stories": []}
    overall = 0
    for item in plan:
        entry = {"number": item["number"], "title": item["title"],
                 "ready": item["ready"], "project": item["project"]}
        if not item["ready"]:
            entry["status"] = "skipped"
            entry["reason"] = item["reason"]
            results["stories"].append(entry)
            continue
        out_video = os.path.join(expand(cfg["paths"]["videos_dir"]),
                                 "%s-queue.mp4" % item["story"])
        t0 = time.time()
        rc = cmd_run(cfg, item["story"], item["project"], out_video,
                     allow_fallback)
        entry["status"] = "done" if rc == 0 else "failed"
        entry["seconds"] = round(time.time() - t0, 1)
        entry["output"] = out_video if rc == 0 else None
        results["stories"].append(entry)
        if rc != 0:
            overall = 1
            print("فشلت قصة %d (%s)" % (item["number"], item["title"]))
            if not continue_on_error:
                print("توقفت الدفعة — استخدم --continue-on-error "
                      "للمتابعة بعد الفشل")
                break
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("سُجّلت نتائج الدفعة في: %s" % out_path)
    # خلاصة بتاريخ اليوم تُلحق بملف الطابور (سجل زمني مثل باقي أقسامه)
    try:
        with open(queue_path, "a", encoding="utf-8") as f:
            f.write("\n## تحديث run-queue — %s\n\n" % results["date"])
            for e in results["stories"]:
                f.write("- %d. %s — %s%s\n" % (
                    e["number"], e["title"], e["status"],
                    (" (%s)" % e.get("reason", "")) if e["status"]
                    == "skipped" else ""))
    except OSError as e:
        print("تحذير: تعذر إلحاق الخلاصة بملف الطابور: %s" % e)
    return overall


# ------------------------------------------------------------- queue add
def cmd_queue_add(cfg, title, text_file, parts=1, note=None,
                  queue_file=None):
    """أضف قصة إلى ملف الطابور بسطر واحد (يرفض المكرر).

    يرجع 0 عند النجاح، و1 عند أي رفض (عنوان مكرر/نص فارغ/...).
    """
    queue_path = expand(queue_file or cfg["paths"]["queue_file"])
    try:
        with open(expand(text_file), encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print("تعذر قراءة ملف نص القصة: %s" % e)
        return 1
    stories_dir = os.path.join(STUDIO_DIR, "queue")
    try:
        result = queue_lib.add_story(queue_path, title, text, parts=parts,
                                     note=note, stories_dir=stories_dir)
    except queue_lib.QueueError as e:
        print("رفضت الإضافة: %s" % e)
        return 1
    except OSError as e:
        print("فشل الكتابة في ملف الطابور: %s" % e)
        return 1
    print("أُضيفت القصة رقم %d إلى الطابور: %s"
          % (result["number"], result["title"]))
    if result["text_file"]:
        print("نص القصة محفوظ في: %s" % result["text_file"])
    return 0


# ------------------------------------------------------------------ analyze
def cmd_analyze(cfg, page_id=None, channel_id=None):
    """حلّل آخر فيديو منشور بأرقام حقيقية (فيسبوك + يوتيوب).

    يطبع المنصتين جنبًا إلى جنب + 2–3 اقتراحات تحسين مشتقة من
    الأرقام، ويحفظ JSON في runs/analyze-<وقت>.json. أي مصدر لا
    يصل يُطبع «غير معروف» — بلا أرقام مخترعة أبدًا. يرجع 1 فقط
    إن تعذر المصدران معًا.
    """
    page_id = page_id or (cfg.get("publish") or {}).get("page_id")
    channel_id = (channel_id
                  or (cfg.get("publish") or {}).get("youtube_channel_id"))
    fb = None
    fb_note = None
    fb_bin = publish.find_facebook_bin()
    if not fb_bin:
        fb_note = "facebook-cli غير متاح"
    elif not page_id:
        fb_note = "معرّف الصفحة غير مضبوط (publish.page_id)"
    else:
        fb, fb_note = analyze.fb_last_video(fb_bin, page_id)
    yt, yt_note = analyze.yt_latest_video(channel_id)
    print("== آخر فيديو منشور — تحليل الأداء ==")
    print("-- فيسبوك --")
    if fb:
        print("المنشور: %s" % (fb["caption"][:80] or fb["object_id"]))
        print("نُشر: %s" % (fb["published_time"] or "غير معروف"))
        print("المشاهدات: %s — التفاعلات: %s — الإعجابات: %s — "
              "التعليقات: %s — المشاركات: %s"
              % (analyze.format_value(fb["views"]),
                 analyze.format_value(fb["engagements"]),
                 analyze.format_value(fb["reactions"]),
                 analyze.format_value(fb["comments"]),
                 analyze.format_value(fb["shares"])))
        if fb_note:
            print("ملاحظة: %s" % fb_note)
    else:
        print("غير معروف — %s" % (fb_note or "تعذرت القراءة"))
    print("-- يوتيوب --")
    if yt:
        print("الفيديو: %s" % (yt["title"] or yt["video_id"]))
        print("رُفع: %s — المدة: %s ثانية"
              % (yt["upload_date"] or "غير معروف",
                 yt["duration"] if yt["duration"] is not None
                 else "غير معروف"))
        print("المشاهدات: %s — الإعجابات: %s — التعليقات: %s"
              % (analyze.format_value(yt["views"]),
                 analyze.format_value(yt["likes"]),
                 analyze.format_value(yt["comments"])))
    else:
        print("غير معروف — %s" % (yt_note or "تعذرت القراءة"))
    print("-- ما يُحسَّن في الفيديو التالي --")
    for i, tip in enumerate(analyze.suggest(fb, yt), 1):
        print("%d. %s" % (i, tip))
    runs_dir = expand(cfg["paths"]["runs_dir"])
    os.makedirs(runs_dir, exist_ok=True)
    out_path = os.path.join(
        runs_dir, "analyze-%s.json" % time.strftime("%Y%m%d-%H%M%S"))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"date": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "facebook": fb, "facebook_note": fb_note,
                   "youtube": yt, "youtube_note": yt_note,
                   "suggestions": analyze.suggest(fb, yt)},
                  f, ensure_ascii=False, indent=2)
    print("حُفظ التحليل في: %s" % out_path)
    return 0 if (fb is not None or yt is not None) else 1


# ------------------------------------------------------------ analyze-ref
def cmd_analyze_ref(cfg, url, model="small"):
    """تحليل فيديو مرجعي وحفظ JSON في runs/ref-<id>.json.

    تحليل خاص فقط (انظر تنبيه ref_analyzer.COPYRIGHT_NOTICE) —
    بلا إعادة نشر أو توزيع، والصوت المنزّل يُحذف بعد التحليل.
    """
    try:
        result = ref_analyzer.analyze_reference(url, model=model)
    except ref_analyzer.RefError as e:
        print("فشل تحليل الفيديو المرجعي: %s" % e)
        return 1
    runs_dir = expand(cfg["paths"]["runs_dir"])
    os.makedirs(runs_dir, exist_ok=True)
    vid = result["video"].get("id") or "unknown"
    out_path = os.path.join(runs_dir, "ref-%s.json" % vid)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    v = result["video"]
    print("الفيديو: %s" % v.get("title"))
    print("المدة: %s ثانية — المشاهدات: %s — الناشر: %s"
          % (v.get("duration_seconds"), v.get("view_count"),
             v.get("uploader")))
    a = result.get("analysis")
    if a:
        print("الهوك (أول 10 ثوانٍ): %s" % a["hook_first_10s"])
        print("سرعة السرد: %s كلمة/دقيقة (%d كلمة)"
              % (a["words_per_minute"], a["word_count"]))
        print("الختام (آخر 10 ثوانٍ): %s%s"
              % (a["ending_last_10s"],
                 " — فيه سؤال" if a["ending_has_question"] else ""))
    print("حُفظ التحليل في: %s" % out_path)
    return 0


def main():
    ap = argparse.ArgumentParser(prog="studio",
                                 description="خط إنتاج موحد لفيديوهات "
                                             "القصص",
                                 epilog="للمساعدة بالعربية: "
                                        "python3 studio.py help-ar")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="فحص حالة الطبقات الثلاث")
    sub.add_parser("help-ar", help="مساعدة عربية — كل أمر ووظيفته ومثال عليه")
    p = sub.add_parser("doctor", help="فحص بيئة studio (PASS/FAIL صادق)")
    p.add_argument("--fix", action="store_true",
                   help="أنشئ config.yaml من المثال إن غاب")
    p = sub.add_parser("publish", help="نشر فيديو على فيسبوك ويوتيوب")
    p.add_argument("--video", required=True, help="ملف الفيديو mp4")
    p.add_argument("--title", required=True, help="عنوان الفيديو")
    p.add_argument("--caption", default="",
                   help="نص الكابشن (تُضاف الهاشتاجات تلقائيًا)")
    p.add_argument("--thumbnail", help="ملف الصورة المصغرة")
    p.add_argument("--platforms", default="facebook,youtube",
                   help="منصات مفصولة بفاصلة: facebook,youtube "
                        "(الافتراضي: كلاهما)")
    p.add_argument("--page-id", help="معرّف صفحة فيسبوك (أو من config.yaml)")
    p.add_argument("--schedule", type=int,
                   help="موعد النشر Unix (ثوانٍ) — للجدولة بدل النشر الآن")
    p.add_argument("--privacy", choices=["public", "unlisted", "private"],
                   help="خصوصية يوتيوب (الافتراضي من الإعداد: public)")
    p.add_argument("--tags",
                   help="وسوم يوتيوب مفصولة بفاصلة (الافتراضي: وسوم الصفحة)")
    p.add_argument("--dry-run", action="store_true",
                   help="اطبع الحمولة الدقيقة دون نشر أي شيء")
    p = sub.add_parser("youtube-auth",
                       help="تبادل OAuth ليوتيوب لمرة واحدة (يفتح المتصفح)")
    p.add_argument("--client-secrets",
                   help="ملف client_secrets.json (أو من config.yaml)")
    p.add_argument("--token",
                   help="مسار حفظ التوكن (أو من config.yaml)")
    p = sub.add_parser("script", help="توليد هوك/كابشن عبر OmniRoute")
    p.add_argument("--story", required=True)
    p.add_argument("--allow-fallback", action="store_true")
    p = sub.add_parser("produce", help="تجهيز أصول مشروع OpenMontage")
    p.add_argument("--project", required=True)
    p.add_argument("--run", dest="run_id")
    p = sub.add_parser("assemble", help="تجميع وتصدير (Concat افتراضيًا)")
    p.add_argument("--run", dest="run_id", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--backend", default="concat",
                   choices=["concat", "headless", "mlt"],
                   help="خلفية التجميع: concat (افتراضي) أو headless أو mlt")
    p.add_argument("--no-watermark", action="store_true",
                   help="تخطَّ شعار الصفحة (الشعار تلقائي افتراضيًا)")
    p.add_argument("--cards-dir",
                   help="مجلد بطاقات الاقتباس (ibra/hikma/mawiza) "
                        "لإلحاقها ختامية 3×3 ثوانٍ")
    p.add_argument("--size",
                   help="مقاس الفيديو WxH — الافتراضي 720x1280 (عمودي)؛ "
                        "1280x720 للأفقي (الفيديو الطويل الأسبوعي)")
    p = sub.add_parser("clean-audio",
                         help="قص صمت الصوت الخام عبر Auto-Editor "
                              "(أبدًا على السرد النهائي)")
    p.add_argument("--input", required=True, help="ملف الصوت الخام")
    p.add_argument("--out", required=True, help="ملف الصوت النظيف")
    p.add_argument("--threshold", type=float, default=0.02,
                   help="عتبة الصوت للقص (0.02 افتراضيًا)")
    p.add_argument("--margin", type=float, default=0.2,
                   help="هامش حول المقاطع الصاخبة بالثواني (0.2)")
    p.add_argument("--force", action="store_true",
                   help="اسمح بتنظيف ملف سرد نهائي (غير مستحسن)")
    p = sub.add_parser("fx",
                         help="تركيبة MoviePy: Ken Burns + نص عربي متحرك "
                              "(من بيئة .venv-moviepy)")
    p.add_argument("--image", required=True, help="صورة الخلفية")
    p.add_argument("--out", required=True, help="ملف mp4 الناتج")
    p.add_argument("--duration", type=float, default=5.0,
                   help="مدة المقطع بالثواني (5 افتراضيًا)")
    p.add_argument("--text", default=None,
                   help="نص عربي متحرك (اختياري)")
    p.add_argument("--audio", default=None,
                   help="ملف صوت (اختياري)")
    p.add_argument("--zoom-to", type=float, default=1.15,
                   help="التكبير النهائي (1.15 افتراضيًا)")
    p.add_argument("--fontsize", type=int, default=58,
                   help="حجم خط النص (58 افتراضيًا)")
    p = sub.add_parser("karaoke-ass",
                         help="كابشنات كاريوكي كلمة-بكلمة (منطق Capite "
                              "مُعاد تنفيذه — من بيئة .venv-whisper)")
    p.add_argument("--audio", required=True, help="ملف الصوت")
    p.add_argument("--out", required=True, help="ملف ASS الناتج")
    p.add_argument("--model", default="small",
                   help="موديل faster-whisper (small افتراضيًا)")
    p.add_argument("--max-chars", type=int, default=28,
                   help="أقصى حروف في السطر (28 افتراضيًا)")
    p = sub.add_parser("trim",
                         help="قص مقطع بلا إعادة ترميز (تنظيف Veo قبل "
                              "التجميع)")
    p.add_argument("--input", required=True, help="ملف الفيديو")
    p.add_argument("--out", required=True, help="ملف الفيديو المقصوص")
    p.add_argument("--start", type=float, default=0.0,
                   help="زمن البداية بالثواني (0 افتراضيًا)")
    p.add_argument("--end", type=float, default=None,
                   help="زمن النهاية بالثواني")
    p.add_argument("--duration", type=float, default=None,
                   help="مدة القص بالثواني (بديل لـ --end)")
    p.add_argument("--exact", action="store_true",
                   help="قطع دقيق بالإطار بإعادة ترميز (أبطأ)")
    p = sub.add_parser("thumbnail",
                       help="توليد صورة مصغرة 720×1280 (أو 1280×720 مع --long)")
    p.add_argument("--video", help="مسار الفيديو (أو استخدم --run)")
    p.add_argument("--run", dest="run_id",
                   help="معرّف تشغيل سابق — يأخذ الفيديو والهوك منه")
    p.add_argument("--hook", help="نص الهوك الصادم أعلى الصورة")
    p.add_argument("--time", type=float,
                   help="ثانية اللقطة (الافتراضي: 40%% من مدة الفيديو)")
    p.add_argument("--out", help="مسار الصورة (الافتراضي: videos_dir)")
    p.add_argument("--long", action="store_true",
                   help="صورة أفقية 1280×720 للفيديو الطويل")
    p.add_argument("--size",
                   help="مقاس الصورة WxH — يتجاوز --long إن أُعطي")
    p = sub.add_parser("whisper-ass",
                         help="كابشنات ASS من faster-whisper (تجريبي)")
    p.add_argument("--audio", required=True,
                   help="ملف السرد (wav، أو أي صوت عبر ffmpeg)")
    p.add_argument("--out", required=True, help="مسار ملف ASS الناتج")
    p.add_argument("--model", default="small",
                   help="موديل whisper: tiny/base/small (الافتراضي: small)")
    p.add_argument("--max-words", type=int, default=6,
                   help="أقصى كلمات في العبارة (الافتراضي: 6)")
    p.add_argument("--max-gap", type=float, default=0.6,
                   help="فجوة الصمت التي تفصل عبارتين بالثواني (0.6)")
    p.add_argument("--font-size", type=int, default=52,
                   help="حجم الخط في ASS (الافتراضي: 52)")
    p = sub.add_parser("run", help="خط الإنتاج الكامل (أو --demo للتجربة)")
    p.add_argument("--story",
                   help="اسم القصة (غير مطلوب مع --demo)")
    p.add_argument("--project",
                   help="اسم مشروع OpenMontage (غير مطلوب مع --demo)")
    p.add_argument("--out",
                   help="مسار الفيديو الناتج (افتراضي للتجربة: videos_dir)")
    p.add_argument("--demo", action="store_true",
                   help="القصة التجريبية المدمجة — مسار مجاني فقط، "
                        "بلا Veo وبلا مفاتيح")
    p.add_argument("--allow-fallback", action="store_true")
    p.add_argument("--dry-run", action="store_true",
                   help="يطبع الخطوات فقط دون تنفيذ")
    p.add_argument("--backend", default="concat",
                   choices=["concat", "headless", "mlt"],
                   help="خلفية التجميع: concat (افتراضي) أو headless أو mlt")
    p.add_argument("--no-watermark", action="store_true",
                   help="تخطَّ شعار الصفحة (الشعار تلقائي افتراضيًا)")
    p.add_argument("--cards-dir",
                   help="مجلد بطاقات الاقتباس (ibra/hikma/mawiza) "
                        "لإلحاقها ختامية 3×3 ثوانٍ")
    p.add_argument("--size",
                   help="مقاس الفيديو WxH — الافتراضي 720x1280 (عمودي)؛ "
                        "1280x720 للأفقي (الفيديو الطويل الأسبوعي)")
    p = sub.add_parser("long-video",
                       help="فيديو طويل أفقي 1280×720 من عدة قصص (8–12 دقيقة)")
    p.add_argument("--out", required=True,
                   help="مسار الفيديو الطويل الناتج")
    p.add_argument("--title",
                   help="عنوان الفيديو الطويل (أو من ملف الفصول)")
    p.add_argument("--hook",
                   help="هوك المقدمة (الافتراضي: العنوان)")
    p.add_argument("--intro",
                   help="نص سرد المقدمة (الافتراضي: الهوك)")
    p.add_argument("--outro",
                   help="نص سرد الخاتمة (الافتراضي: دعوة اشتراك)")
    p.add_argument("--story", action="append", default=[],
                   help="قصة من الطابور بمشروع OpenMontage جاهز (تُكرَّر)")
    p.add_argument("--project", action="append", default=[],
                   help="اسم مشروع OpenMontage (يُكرَّر)")
    p.add_argument("--run", dest="run_id", action="append", default=[],
                   help="معرّف تشغيل سابق كمصدر فصل (يُكرَّر)")
    p.add_argument("--chapter-dir", action="append", default=[],
                   help="مجلد فصل مُعدّ (يُكرَّر)")
    p.add_argument("--chapter-text", action="append", default=[],
                   help="عنوان فصل نصي (يُكرَّر، مع --text-file)")
    p.add_argument("--text-file", action="append", default=[],
                   help="ملف نص فصل نصي (يُكرَّر، مع --chapter-text)")
    p.add_argument("--cover", action="append", default=[],
                   help="صورة غلاف فصل نصي (تُكرَّر، مع --chapter-text)")
    p.add_argument("--moral", action="append", default=[],
                   help="عبرة فصل نصي (تُكرَّر، مع --chapter-text)")
    p.add_argument("--chapters-file",
                   help="ملف JSON بمواصفات الفصول (يُدمج مع خيارات CLI)")
    p.add_argument("--music",
                   help="ملف موسيقى خلفية (اختياري — تُخفض تلقائيًا)")
    p.add_argument("--auto-week", action="store_true",
                   help="اختر قصص الأسبوع المنشورة من الطابور تلقائيًا "
                        "بدل مصادر فصول يدوية")
    p.add_argument("--since",
                   help="بداية نافذة الأسبوع بصيغة YYYY-MM-DD "
                        "(الافتراضي: قبل 6 أيام) — مع --auto-week")
    p.add_argument("--queue-file",
                   help="ملف طابور بديل (الافتراضي من config.yaml) — "
                        "مع --auto-week")
    p.add_argument("--voice", default="piper", choices=["piper", "gtts"],
                   help="صوت السرد: piper (الراوي الرجل، الافتراضي) "
                        "أو gtts (صوت ثانٍ اختياري)")
    p.add_argument("--atempo", type=float, default=1.0,
                   help="سرعة السرد (1.0 افتراضيًا؛ 1.25 لإيقاع Kwai)")
    p.add_argument("--no-watermark", action="store_true",
                   help="تخطَّ شعار الصفحة (الشعار تلقائي افتراضيًا)")
    p = sub.add_parser("long-narration",
                       help="سرد طويل مقسّم بصوت Piper (رجل) — نص إلى WAV")
    p.add_argument("--text", help="نص السرد (أو استخدم --text-file)")
    p.add_argument("--text-file", help="ملف نص السرد")
    p.add_argument("--out", required=True, help="ملف WAV الناتج")
    p.add_argument("--gap", type=float, default=0.35,
                   help="فاصل الصمت بين الجمل بالثواني (0.35)")
    p.add_argument("--atempo", type=float, default=1.0,
                   help="سرعة السرد (1.0 افتراضيًا؛ 1.25 لإيقاع Kwai)")
    p.add_argument("--voice", default="piper", choices=["piper", "gtts"],
                   help="صوت السرد: piper (الراوي الرجل، الافتراضي) "
                        "أو gtts (صوت ثانٍ اختياري)")
    p = sub.add_parser("quote-cards",
                       help="توليد بطاقات الاقتباس الثلاث 720×1280")
    p.add_argument("--ibra", required=True, help="نص العبرة")
    p.add_argument("--hikma", required=True, help="نص الحكمة")
    p.add_argument("--mawiza", required=True, help="نص الموعظة الدينية")
    p.add_argument("--mawiza-source", default="",
                   help="مصدر الموعظة (مثال: سورة الإسراء: آية 23)")
    p.add_argument("--out-dir", required=True,
                   help="مجلد حفظ البطاقات الثلاث")
    p = sub.add_parser("run-queue",
                         help="دفعة جماعية من ملف الطابور (الجاهز فقط)")
    p.add_argument("--limit", type=int,
                   help="أقصى عدد قصص من بداية الطابور")
    p.add_argument("--continue-on-error", action="store_true",
                   help="أكمل بعد فشل قصة بدل التوقف")
    p.add_argument("--dry-run", action="store_true",
                   help="اطبع القصص وحالتها دون تنفيذ")
    p.add_argument("--allow-fallback", action="store_true",
                   help="اسمح بهوك بديل من السيناريو الجاهز عند فشل "
                        "OmniRoute")
    p = sub.add_parser("analyze-ref",
                         help="تحليل فيديو مرجعي (خاص فقط — بلا إعادة نشر)")
    p.add_argument("--url", required=True,
                   help="رابط فيديو يوتيوب عام")
    p.add_argument("--model", default="small",
                   help="موديل whisper للتفريغ: tiny/base/small "
                        "(الافتراضي: small)")
    p = sub.add_parser("analyze",
                       help="تحليل آخر فيديو منشور بأرقام حقيقية "
                            "(فيسبوك + يوتيوب) واقتراحات تحسين")
    p.add_argument("--page-id",
                   help="معرّف صفحة فيسبوك (أو من config.yaml)")
    p.add_argument("--channel-id",
                   help="معرّف قناة يوتيوب (أو من config.yaml)")
    p = sub.add_parser("queue", help="إدارة طابور القصص")
    qp = p.add_subparsers(dest="queue_cmd", required=True)
    qa = qp.add_parser("add", help="إضافة قصة جديدة إلى الطابور")
    qa.add_argument("--title", required=True, help="عنوان القصة")
    qa.add_argument("--text-file", required=True,
                    help="ملف نص القصة الكامل")
    qa.add_argument("--parts", type=int, default=1,
                    help="عدد الأجزاء (1 = منشور واحد، الافتراضي)")
    qa.add_argument("--note", help="ملاحظة قصيرة تُلحق بمدخل الطابور")
    qa.add_argument("--queue-file",
                    help="ملف طابور بديل (الافتراضي من config.yaml)")
    p = sub.add_parser("client-run",
                       help="تنفيذ طلب فيديو عميل واحد (client-orders)")
    p.add_argument("--order", required=True, help="رقم الطلب")
    sub.add_parser("process-queue",
                   help="تنفيذ كل طلبات العملاء الجديدة (client-orders)")
    args = ap.parse_args()
    cfg = load_config()
    # خيار --size (في run/assemble): يبدّل مقاس الفيديو لهذا التشغيل
    # فقط دون تعديل config.yaml (الافتراضي 720×1280 عمودي).
    size_arg = getattr(args, "size", None)
    if size_arg:
        try:
            width, height = parse_size(size_arg)
        except ValueError as e:
            print("مقاس غير صالح --size: %s" % e)
            return 2
        cfg["video"]["width"] = width
        cfg["video"]["height"] = height
    # تحقق مبكر من slugs/معرّفات التشغيل القادمة من CLI (منع الخروج من
    # runs/) — قبل أي إنشاء مجلدات. التحقق داخل new_run/run_dir_for يبقى
    # كدفاع ثانٍ للمستدعين البرمجيين (run-queue والاختبارات).
    try:
        if args.cmd == "run" and getattr(args, "story", None):
            validate_run_component(args.story, "اسم القصة")
        elif args.cmd == "produce":
            if getattr(args, "run_id", None):
                validate_run_component(args.run_id, "معرّف التشغيل")
            if getattr(args, "project", None):
                validate_run_component(args.project, "اسم المشروع")
        elif args.cmd in ("assemble", "thumbnail"):
            if getattr(args, "run_id", None):
                validate_run_component(args.run_id, "معرّف التشغيل")
        elif args.cmd == "long-video":
            for slug in getattr(args, "story", []) or []:
                validate_run_component(slug, "اسم القصة")
            for proj in getattr(args, "project", []) or []:
                validate_run_component(proj, "اسم المشروع")
            for run in getattr(args, "run_id", []) or []:
                validate_run_component(run, "معرّف التشغيل")
    except ValueError as e:
        print("قيمة غير صالحة: %s" % e)
        return 2
    if args.cmd == "run":
        if args.demo and (args.story or args.project):
            print("--demo لا يُجمع مع --story/--project")
            return 2
        if not args.demo and not (args.story and args.project and args.out):
            print("خط الإنتاج يحتاج --story و--project و--out "
                  "(أو --demo للتجربة)")
            return 2
    # doctor يقرأ الحالة الخام بلا إصلاح (وظيفته الإبلاغ لا الإصلاح).
    if args.cmd != "doctor":
        _ensure_environment()  # إصلاح ذاتي: أعد الأدوات/الخدمة إن غابتا

    if args.cmd == "doctor":
        return cmd_doctor(cfg, fix=args.fix)
    if args.cmd == "status":
        return cmd_status(cfg)
    if args.cmd == "script":
        run_dir = None
        result, _ = cmd_script(cfg, args.story, args.allow_fallback, run_dir)
        return 0 if result else 1
    if args.cmd == "produce":
        runs_dir = expand(cfg["paths"]["runs_dir"])
        if args.run_id:
            run_dir = run_dir_for(runs_dir, args.run_id)
            os.makedirs(run_dir, exist_ok=True)
        else:
            _, run_dir = new_run(runs_dir, args.project)
        try:
            cmd_produce(cfg, args.project, run_dir)
        except openmontage_stage.StageError as e:
            print("فشل التجهيز: %s" % e)
            return 1
        except Exception as e:
            print("فشل التجهيز بخطأ غير متوقع: %s" % e)
            return 1
        print("مجلد التشغيل: %s" % run_dir)
        return 0
    if args.cmd == "assemble":
        runs_dir = expand(cfg["paths"]["runs_dir"])
        run_dir = run_dir_for(runs_dir, args.run_id)
        script_path = os.path.join(run_dir, "script-ai.json")
        if not os.path.isfile(script_path):
            print("لا يوجد تشغيل بهذا المعرّف أو لم يُولَّد سيناريو له: %s"
                  % run_dir)
            return 1
        try:
            with open(script_path, encoding="utf-8") as f:
                title = json.load(f)["title"]
        except (ValueError, KeyError) as e:
            print("ملف السيناريو تالف أو بلا عنوان (%s): %s"
                  % (script_path, e))
            return 1
        if not title:
            print("عنوان السيناريو فارغ في %s — أعد توليد السيناريو أولًا"
                  % script_path)
            return 1
        try:
            if args.backend == "headless":
                cmd_assemble_headless(cfg, run_dir, title, expand(args.out),
                                      not args.no_watermark,
                                      expand(args.cards_dir)
                                      if args.cards_dir else None)
            elif args.backend == "mlt":
                cmd_assemble_mlt(cfg, run_dir, title, expand(args.out),
                                 not args.no_watermark,
                                 expand(args.cards_dir)
                                 if args.cards_dir else None)
            else:
                cmd_assemble(cfg, run_dir, title, expand(args.out),
                             not args.no_watermark,
                             expand(args.cards_dir)
                             if args.cards_dir else None)
        except concat_mcp.ConcatError as e:
            print("فشل التجميع: %s" % e)
            return 1
        except headless_stage.HeadlessError as e:
            print("فشل التجميع عبر headless-editor: %s" % e)
            return 1
        except mlt_stage.MltError as e:
            print("فشل التجميع عبر MLT/melt: %s" % e)
            return 1
        except watermark.WatermarkError as e:
            print("فشل الإنهاء (شعار/بطاقات): %s" % e)
            return 1
        return 0
    if args.cmd == "clean-audio":
        try:
            cmd_clean_audio(cfg, expand(args.input), expand(args.out),
                            args.threshold, args.margin, args.force)
        except autoedit.AutoEditError as e:
            print("فشل تنظيف الصوت: %s" % e)
            return 1
        return 0
    if args.cmd == "fx":
        try:
            cmd_fx(cfg, expand(args.image), expand(args.out),
                   args.duration, args.text, args.audio,
                   args.zoom_to, args.fontsize)
        except moviepy_fx.MoviePyFxError as e:
            print("فشل التركيب: %s" % e)
            return 1
        return 0
    if args.cmd == "karaoke-ass":
        try:
            cmd_karaoke_ass(cfg, expand(args.audio), expand(args.out),
                            args.model, args.max_chars)
        except capite_captions.CapiteError as e:
            print("فشل توليد الكاريوكي: %s" % e)
            return 1
        except whisper_captions.WhisperError as e:
            print("فشل النسخ: %s" % e)
            return 1
        return 0
    if args.cmd == "trim":
        try:
            cmd_trim(cfg, expand(args.input), expand(args.out),
                     args.start, args.end, args.duration, args.exact)
        except trim.TrimError as e:
            print("فشل القص: %s" % e)
            return 1
        return 0
    if args.cmd == "thumbnail":
        runs_dir = expand(cfg["paths"]["runs_dir"])
        video_path, hook = args.video, args.hook
        if args.run_id:
            run_dir = run_dir_for(runs_dir, args.run_id)
            log_path = os.path.join(run_dir, "run-log.json")
            script_path = os.path.join(run_dir, "script-ai.json")
            if not os.path.isdir(run_dir):
                print("لا يوجد تشغيل بهذا المعرّف: %s" % run_dir)
                return 1
            try:
                with open(log_path, encoding="utf-8") as f:
                    video_path = (json.load(f)["steps"]["assemble"]
                                  ["output"])
            except (OSError, ValueError, KeyError) as e:
                print("تعذر قراءة مسار الفيديو من سجل التشغيل (%s)" % e)
                return 1
            if not hook:
                try:
                    with open(script_path, encoding="utf-8") as f:
                        hook = json.load(f)["title"]
                except (OSError, ValueError, KeyError) as e:
                    print("تعذر قراءة الهوك من السيناريو (%s)" % e)
                    return 1
        if not video_path or not hook:
            print("لازم --video و--hook، أو --run لتشغيل سابق")
            return 1
        if not args.out:
            base = os.path.splitext(os.path.basename(video_path))[0]
            suffix = ("-long-thumbnail.jpg" if args.long
                      else "-thumbnail.jpg")
            out_path = os.path.join(expand(cfg["paths"]["videos_dir"]),
                                    base + suffix)
        else:
            out_path = expand(args.out)
        width, height = thumbnail.WIDTH, thumbnail.HEIGHT
        fontsize, margin_v, max_chars = (thumbnail.FONTSIZE,
                                         thumbnail.MARGIN_V, 20)
        if args.long:
            width, height = thumbnail.LONG_WIDTH, thumbnail.LONG_HEIGHT
            fontsize, margin_v, max_chars = (thumbnail.LONG_FONTSIZE,
                                             thumbnail.LONG_MARGIN_V,
                                             thumbnail.LONG_MAX_CHARS)
        if args.size:
            try:
                width, height = parse_size(args.size)
            except ValueError as e:
                print("مقاس غير صالح --size: %s" % e)
                return 2
            if (width, height) == (thumbnail.LONG_WIDTH,
                                   thumbnail.LONG_HEIGHT):
                fontsize, margin_v, max_chars = (thumbnail.LONG_FONTSIZE,
                                                 thumbnail.LONG_MARGIN_V,
                                                 thumbnail.LONG_MAX_CHARS)
        try:
            cmd_thumbnail(cfg, expand(video_path), hook, out_path,
                          args.time, width=width, height=height,
                          fontsize=fontsize, margin_v=margin_v,
                          max_chars=max_chars)
        except thumbnail.ThumbnailError as e:
            print("فشل توليد الصورة المصغرة: %s" % e)
            return 1
        return 0
    if args.cmd == "whisper-ass":
        # خيار تجريبي: يعمل فقط من بيئة faster-whisper
        # (.venv-whisper) — انظر WHISPER-TEST.md. لا يمس خط
        # silencedetect الافتراضي، ولا يُستخدم حين يختلف النص
        # المعروض عن النص المنطوق.
        try:
            phrases, text = whisper_captions.whisper_ass(
                expand(args.audio), expand(args.out), model=args.model,
                max_words=args.max_words, max_gap=args.max_gap,
                font_size=args.font_size)
        except whisper_captions.WhisperError as e:
            print("فشل توليد الكابشنات: %s" % e)
            return 1
        print("كُتب %d عبارة في %s" % (len(phrases), expand(args.out)))
        print("النص المسموع: %s" % text)
        print("راجع النص قبل النشر — حتى موديل small يخطئ في ~22% "
              "من كلمات سرد Piper (WHISPER-TEST.md).")
        return 0
    if args.cmd == "run":
        if args.demo:
            try:
                # التجربة تعمل بخلفية headless دائمًا (المسار المجاني)
                # — لا يُمرَّر افتراضي --backend (concat) هنا.
                cmd_demo(cfg, args.out)
            except demo.DemoError as e:
                print("فشلت التجربة: %s" % e)
                return 1
            except headless_stage.HeadlessError as e:
                print("فشل ريندر التجربة: %s" % e)
                return 1
            except long_narration.LongNarrationError as e:
                print("فشل سرد التجربة: %s" % e)
                return 1
            except watermark.WatermarkError as e:
                print("فشل إنهاء التجربة (شعار): %s" % e)
                return 1
            return 0
        return cmd_run(cfg, args.story, args.project, expand(args.out),
                       args.allow_fallback, args.dry_run, args.backend,
                       not args.no_watermark,
                       expand(args.cards_dir) if args.cards_dir else None)
    if args.cmd == "publish":
        platforms = [pl.strip() for pl in args.platforms.split(",")
                     if pl.strip()]
        bad = [pl for pl in platforms
               if pl not in ("facebook", "youtube")]
        if bad:
            print("منصات غير معروفة: %s (المسموح: facebook,youtube)"
                  % ", ".join(bad))
            return 2
        if not platforms:
            print("حدد منصة واحدة على الأقل في --platforms")
            return 2
        tags = ([t.strip() for t in args.tags.split(",") if t.strip()]
                if args.tags else None)
        return cmd_publish(cfg, args.video, args.title, args.caption,
                           thumbnail=args.thumbnail, platforms=platforms,
                           page_id=args.page_id, schedule=args.schedule,
                           privacy=args.privacy, tags=tags,
                           dry_run=args.dry_run)
    if args.cmd == "youtube-auth":
        return cmd_youtube_auth(cfg, args.client_secrets, args.token)
    if args.cmd == "long-video":
        try:
            return cmd_long_video(cfg, args)
        except long_video.LongVideoError as e:
            print("فشل الفيديو الطويل: %s" % e)
            return 1
        except long_narration.LongNarrationError as e:
            print("فشل سرد الفيديو الطويل: %s" % e)
            return 1
    if args.cmd == "help-ar":
        help_ar.print_help()
        return 0
    if args.cmd == "queue":
        if args.queue_cmd == "add":
            return cmd_queue_add(cfg, args.title, args.text_file,
                                 parts=args.parts, note=args.note,
                                 queue_file=args.queue_file)
        return 2
    if args.cmd == "analyze":
        return cmd_analyze(cfg, page_id=args.page_id,
                           channel_id=args.channel_id)
    if args.cmd == "long-narration":
        try:
            cmd_long_narration(cfg, args.text, args.text_file,
                               args.out, args.gap, args.atempo,
                               voice=args.voice)
        except long_narration.LongNarrationError as e:
            print("فشل السرد الطويل: %s" % e)
            return 1
        except OSError as e:
            print("فشل قراءة ملف النص: %s" % e)
            return 1
        return 0
    if args.cmd == "quote-cards":
        try:
            paths = watermark.generate_quote_cards(
                args.ibra, args.hikma, args.mawiza, args.mawiza_source,
                expand(args.out_dir))
        except watermark.WatermarkError as e:
            print("فشل توليد البطاقات: %s" % e)
            return 1
        for pth in paths:
            print("بطاقة: %s" % pth)
        return 0
    if args.cmd == "run-queue":
        return cmd_run_queue(cfg, limit=args.limit,
                             continue_on_error=args.continue_on_error,
                             dry_run=args.dry_run,
                             allow_fallback=args.allow_fallback)
    if args.cmd == "analyze-ref":
        return cmd_analyze_ref(cfg, args.url, model=args.model)
    if args.cmd == "client-run":
        import client_orders
        return client_orders.cmd_client_run(cfg, args.order)
    if args.cmd == "process-queue":
        import client_orders
        return client_orders.cmd_process_queue(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
