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
  studio.py batch --count N [--source veo|openmontage] [--execute]
      # دفعة جماعية (الجولة 7): القصص التالية من الطابور في تشغيل
      # واحد — إنتاج + فحص + مصغرة + سجل؛ افتراضيًا وضع تجريبي.
  studio.py scene-plan --story N [--clips 6]
      # خطة مشاهد Veo مكتوبة قبل أي إنفاق (موجهات + وحدات) مع
      # فحص السقف — الجولة 7.
  studio.py tiktok-auth [--token TOKEN] / instagram-auth [--token TOKEN]
      # خطوات ربط TikTok/Instagram يدويًا + حفظ التوكن (600).
  studio.py analyze --dna --video F [--title T] [--hook H]
      # تحليل DNA الفيروسي (الجولة 7): درجة الهوك 0–10 + الإيقاع
      # + الصمت + كثافة الكلمات + حكم مربوط بالأرقام الحقيقية.
  studio.py analyze-ref --url URL
      # تحليل فيديو مرجعي (بيانات + تفريغ + هوك/إيقاع/ختام) — تحليل
      # خاص فقط، بلا إعادة نشر أو توزيع (انظر README).
  studio.py ideas [--count N] [--theme THEME] [--add N]
      # مولّد أفكار قصص بأسلوب الصفحة (النموذج أولًا، والبنك
      # المحلي بديلًا) مع منع تكرار أي عنوان في الطابور.
  studio.py daily [--slot morning|evening] [--execute]
      # أمر اليوم الواحد: إنتاج + فحص + مصغرة + نشر المنصتين +
      # نص أول تعليق. افتراضيًا --dry-run (خطة بلا تنفيذ).
  studio.py ab --video F [--hook-a A --hook-b B]
      # اختبار A/B: هوكان ومصغرتان + سجل الزوج في runs/ab-*.
  studio.py ab-results [--ab-file FILE]
      # قارن مشاهدات النسختين (فيسبوك + يوتيوب).
  studio.py update [--dry-run]
      # جلب آخر إصدار من GitHub وتطبيق الملفات المتغيرة
      # (مع نسخة احتياطية؛ والملفات المحمية لا تُمسّ).
  studio.py backup [--out-dir DIR]
      # نسخة احتياطية zip: الإعداد + الطابور + الطلبات + السجلات.
  studio.py balance [--balance N] [--renew DATE]
      # توقع رصيد Veo بالأيام — من الرصيد المسجَّل (ليس حيًا).

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
from lib import check as check_lib
from lib import fix_audio as fix_audio_lib
from lib import init_wizard
from lib import ideas
from lib import daily
from lib import ab as ab_lib
from lib import update_backup
from lib import balance as balance_lib
from lib import batch as batch_lib
from lib import dna as dna_lib
from lib import scene_plan as scene_plan_lib
from lib import social_publish as social_lib


def _print_translated(prefix, exc, context):
    """اطبع خطأً مترجمًا للعربية؛ وإن لم تُعرف فئته اطبع الأصل."""
    from lib import errors as errors_lib
    text = str(exc)
    if "ماذا حدث:" in text:
        print("%s: %s" % (prefix, text))  # مترجم أصلًا في lib/ — لا تكرر
        return
    explained = errors_lib.explain_error(exc, context)
    if explained["category"] == "unknown":
        print("%s: %s" % (prefix, text))
    else:
        print(errors_lib.format_error(explained))

VERSION = "0.1.32"
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
    "schedule": {"morning": "09:00", "evening": "19:00"},
    "narration": {"voice": "piper"},
    # رصيد Veo مسجَّل يدويًا (ليس حيًا من API — لا واجهة رسمية
    # لرصيد Flow): يُحدَّث بعد كل توليد في Flow. 750 وحدة
    # تتجدد 13 ديسمبر؛ فيديو Veo اليومي 100–140 وحدة.
    "veo": {"balance_units": 750, "renews": "2026-12-13",
            "daily_cost_min": 100, "daily_cost_max": 140},
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
    from lib.paths import check_size
    return check_size(width, height, "المقاس")


def expand(p):
    return os.path.expanduser(os.path.expandvars(str(p)))


def validate_run_component(name, what="اسم القصة"):
    r"""تحقق من مكوّن مسار واحد (slug قصة أو معرّف تشغيل) قبل ضمّه إلى مسار.

    يرفض أي قيمة قد تخرج بالمسار من مجلد التشغيل: فواصل مسارات (`/` أو
    `\`)، أو `..`، أو حرف NUL، أو البدء بنقطة أو بشرطة (حقن أعلام).
    القيم الصالحة مثل: anza، aisha-part2، test_1.
    """
    from lib.paths import safe_component
    return safe_component(name, what)


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
    # إصلاح اختبار اختراق 2026-11-22 (L14): الفحص ثم الإنشاء
    # (exists + makedirs exist_ok=True) كان سباقًا نظريًا —
    # تشغيلان متوازيان في نفس الثانية قد يأخذا نفس المجلد.
    # الآن إنشاء ذري: makedirs(..., exist_ok=False) والتعارض
    # (FileExistsError) يعيد المحاولة بلاحقة رقمية.
    n = 2
    for _attempt in range(10000):
        try:
            os.makedirs(run_dir, exist_ok=False)
            return run_id, run_dir
        except FileExistsError:
            run_id = "%s-%s-%d" % (story, ts, n)
            run_dir = run_dir_for(runs_dir, run_id)
            n += 1
    raise OSError("تعذّر إنشاء مجلد تشغيل فريد بعد 10000 محاولة: %s"
                  % story)


def write_log(run_dir, log):
    with open(os.path.join(run_dir, "run-log.json"), "w",
              encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- status
def _omniroute_bind_address(port=20128):
    """عنوان ربط خادم OmniRoute من /proc/net/tcp.

    يقرأ المنفذ 20128 ويعيد عنوان الاستماع الفعلي؛ تحذير صريح
    إن لم يكن loopback (اختبار اختراق 2026-11-21: الخادم كان
    يربط 0.0.0.0 لأن المتغير الصحيح HOSTNAME لا
    OMNIROUTE_SERVER_HOST).
    """
    try:
        with open("/proc/net/tcp", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 4:
                    continue
                try:
                    local = parts[1]
                    addr, p = local.rsplit(":", 1)
                    port_no = int(p, 16)
                except ValueError:
                    continue
                if port_no != port or parts[3] != "0A":
                    continue
                ip = ".".join(str(int(addr[i:i + 2], 16))
                              for i in (6, 4, 2, 0))
                if ip == "127.0.0.1":
                    return "127.0.0.1 فقط (loopback — آمن)"
                return "%s — تحذير: ليس loopback!" % ip
    except OSError:
        pass
    return "غير معروف (الخادم متوقف أو بلا /proc/net/tcp)"


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
    print("  الربط: %s" % _omniroute_bind_address())
    try:
        out = subprocess.run(["omniroute", "providers", "list"],
                             capture_output=True, text=True, timeout=30)
        import re as _re
        clean = _re.sub(r"\x1b\[[0-9;]*m", "", out.stdout or "")
        rows = [l.strip() for l in clean.splitlines()
                if l.strip() and not l.strip().startswith(("Loaded", "📋",
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
# (fc-list: أُضيف 2026-11-22 — fontconfig حزمة apt تُمسح مع الريستارت
# وكان فحص الخطوط بلا تغطية إصلاح.)
_EXPECTED_TOOLS = ("ffmpeg", "melt", "yt-dlp", "omniroute", "ollama",
                   "piper", "zstd", "fc-list")
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


def _script_safe_to_run(script):
    """هل سكربت الاستعادة آمن للتشغيل التلقائي؟

    سكربتات الاستعادة تُنفَّذ تلقائيًا بصلاحيات المستخدم، فأي عبث
    بها يتحول إلى تنفيذ كود. ارفض التشغيل إن لم يكن السكربت ملفًا
    عاديًا مملوكًا للمستخدم (أو root) أو كان قابلًا للكتابة من
    الجميع. (إصلاح اختبار اختراق 2026-11-21.)
    """
    try:
        st = os.stat(script)
    except OSError:
        return False
    import stat as _stat
    if not _stat.S_ISREG(st.st_mode):
        return False
    if st.st_uid not in (os.getuid(), 0):
        return False
    if st.st_mode & 0o002:
        return False
    return True


def _log_auto_script(script, reason):
    """سجّل كل تشغيل تلقائي لسكربت استعادة (بدل إخفائه في DEVNULL)."""
    try:
        log = os.path.join(os.path.expanduser("~"), "workspace", "studio",
                           "runs", "ensure-env-runs.log")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write("%s تشغيل تلقائي: %s (%s)\n"
                    % (time.strftime("%Y-%m-%dT%H:%M:%S"), script, reason))
    except OSError:
        pass


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
        # مكتبتا بايثون النظاميتان (PyYAML/Pillow) — حزمتا apt قد تُمسحان
        # مع الريستارت ولا يغطيهما `command -v`؛ فحص الاستيراد يطلق
        # الاستعادة نفسها (setup-env.sh يعيد تثبيتهما في الخطوة 8).
        # إصلاح 2026-11-22 (حل مشكلة التثبيت بعد إعادة التشغيل).
        import importlib.util as _ilu
        py_missing = [m for m in ("yaml", "PIL")
                      if _ilu.find_spec(m) is None]
        if py_missing:
            missing = missing + ["python:%s" % m for m in py_missing]
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
                if not _script_safe_to_run(script):
                    print("تحذير: سكربت الاستعادة غير آمن للتشغيل "
                          "التلقائي (مالك/صلاحيات) — يُتخطى: %s" % script)
                else:
                    _log_auto_script(script, " و".join(reasons))
                    env = dict(os.environ)
                    env["STUDIO_ENV_RESTORED"] = "1"
                    try:
                        subprocess.run(["/bin/bash", script], env=env,
                                       timeout=300,
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL,
                                       check=False)
                    except (OSError,
                            subprocess.TimeoutExpired) as e:
                        print("تحذير: فشلت استعادة البيئة تلقائيًا (%s) — "
                              "أكمل بدونها" % e)
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
    خادم OmniRoute شغال على 127.0.0.1 فقط (HOSTNAME) فلا
    ينكشف على الشبكة، ويبقى شغالًا — أمر chat يحتاجه في كل تشغيل.
    تنبيه (اختبار اختراق 2026-11-21): الخادم يقرأ `HOSTNAME`
    لا `OMNIROUTE_SERVER_HOST` (server.js: `HOSTNAME || '0.0.0.0'`)،
    فالمتغير القديم وحده كان يترك الخادم على كل الواجهات.
    best-effort: أي فشل تحذير فقط ولا يوقف التشغيل.
    """
    import shutil
    if _omniroute_server_up():
        return
    if shutil.which("omniroute") is None:
        return
    env = dict(os.environ)
    env["HOSTNAME"] = "127.0.0.1"
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
    if not _script_safe_to_run(script):
        print("تحذير: سكربت حارس البيئة غير آمن للتشغيل التلقائي "
              "(مالك/صلاحيات) — يُتخطى: %s" % script)
        return
    _log_auto_script(script, "أدوات حماية غائبة")
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
    # إصلاح تلقائي لفجوات الصمت (الجولة 6 بند 3): إن فشل فحص
    # الصمت فقط، امزج ضجيجًا ورديًا خافتًا وأعد الفحص؛ أي فشل
    # آخر (مدة/مقاس/شعار) يُترك كما هو. الفشل هنا لا يفشل
    # التجميع — يُطبع تحذير ويُترك الفيديو الأصلي.
    try:
        result = check_lib.run_checks(out)
        silence = next(c for c in result["checks"]
                       if c["name"] == "الصمت عند الفواصل")
        if not silence["ok"]:
            fixed = fix_audio_lib.fix_silence_gaps(
                out, min_seconds=4.0 if result["long"] else 1.0)
            print(fix_audio_lib.format_report(fixed))
            out = fixed["output"]
    except Exception as e:
        print("تعذر الإصلاح التلقائي للصمت (%s) — يُترك الفيديو "
              "كما هو" % e)
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
        _print_translated("فشل خط الإنتاج", e, "run")
        write_log(run_dir, log)
        return 1
    write_log(run_dir, log)
    return 0


# ---------------------------------------------------------------- doctor
def cmd_check(cfg, video, long_mode=False, as_json=False):
    """فحص جودة فيديو قبل النشر (تقرير عربي PASS/FAIL).

    يرجع 0 إن نجحت كل الفحوصات، و1 عند أي فشل (أو تعذر القراءة).
    """
    try:
        result = check_lib.run_checks(expand(video), long_mode=long_mode)
    except check_lib.CheckError as e:
        _print_translated("تعذر فحص الفيديو", e, "check")
        return 1
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(check_lib.format_report(result))
    return 0 if result["passed"] else 1


def cmd_fix_audio(cfg, video, scene_audio=None, out_path=None):
    """إصلاح فجوات الصمت في فيديو (ضجيج وردي + صوت المشاهد).

    يرجع 0 إن نجح الإصلاح أو كان الفيديو سليمًا أصلًا، و1 عند
    أي فشل (ملف مفقود أو تعذر المزج).
    """
    try:
        result = fix_audio_lib.fix_silence_gaps(
            expand(video), scene_audio_paths=scene_audio,
            out_path=expand(out_path) if out_path else None)
    except fix_audio_lib.FixAudioError as e:
        print("فشل إصلاح الصوت: %s" % e)
        return 1
    print(fix_audio_lib.format_report(result))
    return 0


def cmd_init(cfg, args):
    """معالج الإعداد التفاعلي — يكتب config.yaml.

    بلا أعلام: يسأل المستخدم بالعربية. مع أي علم: يعمل بلا
    تفاعل بالقيم الممررة + الافتراضيات للباقي.
    """
    config_path = expand(args.config) if args.config else os.path.join(
        STUDIO_DIR, "config.yaml")
    flags = {}
    for key, attr in (("page_id", "page_id"),
                      ("channel_id", "channel_id"),
                      ("voice", "voice"),
                      ("morning", "morning"),
                      ("evening", "evening"),
                      ("queue_file", "queue_file"),
                      ("page_name", "page_name"),
                      ("logo_file", "logo_file"),
                      ("payment_number", "payment_number")):
        value = getattr(args, attr, None)
        if value is not None:
            flags[key] = value
    if not flags:
        flags = None
    return init_wizard.run_wizard(cfg, config_path, flags=flags,
                                  force=args.force,
                                  check_only=args.check_only)


def cmd_doctor(cfg, fix=False, accounts_flag=False):
    """فحص بيئة studio (تقرير PASS/FAIL صادق). --fix ينشئ config.yaml.

    --accounts يضيف قسمًا منفصلًا بعدّاده الخاص لفحوصات الحسابات
    (فيسبوك/يوتيوب/Veo — قراءة فقط).
    """
    here = os.path.dirname(os.path.abspath(__file__))
    if fix and doctor.ensure_config(here):
        print("أُنشئ config.yaml من المثال")
    checks = doctor.run_checks(cfg)
    text, errors, warnings = doctor.format_report(checks)
    print(text)
    if accounts_flag:
        from lib import accounts as accounts_lib
        acc = accounts_lib.run_account_checks(cfg)
        acc_text, acc_errors, acc_warnings = doctor.format_report(acc)
        print("== فحوصات الحسابات (%d) ==" % len(acc))
        print(acc_text)
        errors += acc_errors
        warnings += acc_warnings
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
                schedule=None, privacy=None, tags=None, dry_run=False,
                skip_check=False, skip_caption_check=False):
    """انشر فيديوًا واحدًا على فيسبوك و/أو يوتيوب.

    يرجع 0 فقط إن نُشر على كل المنصات المطلوبة فعلًا؛ وإن نُشر بعضها
    فقط (أو كُتبت حزمة يوتيوب اليدوية بدل الرفع) يرجع 1 مع شرح
    ما بقي. --dry-run يطبع الحمولة الدقيقة دون نشر أي شيء.
    فحص امتثال الكابشن مسبق افتراضيًا (يرفض أي بوابة متابعة/
    تعليق)؛ و--skip-caption-check للتجاوز الصريح فقط.
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
    fb_caption = yt_desc = yt_title = None
    try:
        if "facebook" in platforms:
            fb_caption = publish.build_caption(title, caption)
        if "youtube" in platforms:
            yt_desc = publish.build_youtube_description(title, caption)
            yt_title = publish.build_youtube_title(title)
    except publish.PublishError as e:
        print("خطأ في بيانات النشر: %s" % e)
        return 1
    thumb = expand(thumbnail) if thumbnail else None
    if thumb and not os.path.isfile(thumb):
        print("ملف الصورة المصغرة غير موجود: %s" % thumb)
        return 1
    # فحص امتثال الكابشن مسبق افتراضيًا: أي جملة تجعل الجزء التالي
    # مشروطًا بالمتابعة أو التعليق ترفض النشر كله قبل أي فحص فيديو
    # أو طباعة حمولة. --skip-caption-check للتجاوز الصريح فقط.
    # الكابشن النهائي يُعرض دائمًا قبل النشر (تجريبي وحقيقي).
    from lib import caption_check
    if "facebook" in platforms and not skip_caption_check:
        cap_result = caption_check.check_caption(fb_caption)
        print("الكابشن النهائي (%d حرفًا):" % len(fb_caption))
        print("   " + fb_caption.replace("\n", "\n   "))
        if not cap_result["ok"]:
            print("الكابشن مرفوض — جمل مشروطة بالمتابعة/التعليق:")
            for issue in cap_result["issues"]:
                print("  - «%s» (%s)"
                      % (issue["sentence"], issue["reason"]))
            if cap_result["fixed"]:
                print("الكابشن المقترح:")
                print("   " + cap_result["fixed"].replace("\n", "\n   "))
            else:
                print("الجملة المحظورة في الهوك نفسه — أعد كتابة "
                      "الكابشن كاملًا.")
            print("أعد النشر بالكابشن المصحح، أو استخدم "
                  "--skip-caption-check للتجاوز على مسؤوليتك")
            return 1
    elif "facebook" in platforms:
        print("الكابشن النهائي (%d حرفًا) — فحص الامتثال متخطَّى "
              "(--skip-caption-check):" % len(fb_caption))
        print("   " + fb_caption.replace("\n", "\n   "))
    # فحص جودة مسبق افتراضي قبل أي نشر (أو معاينة): فيديو فاشل
    # لا يُنشر ولا تُطبع حمولته. --skip-check للتجاوز الصريح فقط.
    if not skip_check:
        try:
            result = check_lib.run_checks(video)
        except check_lib.CheckError as e:
            _print_translated("تعذر فحص الجودة قبل النشر", e, "check")
            print("أصلح الفيديو أو استخدم --skip-check للتجاوز")
            return 1
        print(check_lib.format_report(result))
        if not result["passed"]:
            print("فشل فحص الجودة قبل النشر — أصلح الملاحظات أعلاه "
                  "أو استخدم --skip-check للتجاوز على مسؤوليتك")
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
            if schedule:
                print("   موعد النشر المجدول: %s"
                      % publish.format_schedule(schedule))
            print("   الكابشن (%d حرفًا):" % len(fb_caption))
            print("   " + fb_caption.replace("\n", "\n   "))
        if "youtube" in platforms:
            payload = publish.youtube_payload(
                yt_title, yt_desc, tags, privacy, schedule,
                thumbnail=thumb)
            print("-- يوتيوب (videos.insert):")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        if "tiktok" in platforms:
            try:
                payload = social_lib.tiktok_init_payload(
                    video, title, caption)
            except social_lib.SocialPublishError as e:
                print("تيك توك: لا يمكن بناء الحمولة — %s" % e)
                return 1
            print("-- تيك توك (Content Posting API — video/init):")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            print("   تنبيه: الرفع الحقيقي غير مختبَر حيًا — لا حساب "
                  "TikTok مربوط بعد.")
        if "instagram" in platforms:
            ig_user_id = (cfg.get("publish") or {}).get(
                "instagram_user_id")
            try:
                payload = social_lib.instagram_reel_payload(
                    video, title, caption, ig_user_id)
            except social_lib.SocialPublishError as e:
                print("إنستغرام: لا يمكن بناء الحمولة — %s" % e)
                return 1
            print("-- إنستغرام (Graph API — Reels، رفع قابل "
                  "للاستئناف):")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            print("   تنبيه: الرفع الحقيقي غير مختبَر حيًا — لا حساب "
                  "Instagram مربوط بعد.")
        return 0
    ok = True
    if "facebook" in platforms:
        try:
            res = publish.post_facebook(page_id, video, fb_caption,
                                        schedule)
            print("فيسبوك: %s (post_id=%s)"
                  % ("مجدول" if res["state"] == "scheduled" else "نُشر",
                     res["post_id"]))
            if schedule:
                print("   موعد النشر المجدول: %s"
                      % publish.format_schedule(schedule))
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
                if schedule:
                    print("   موعد النشر المجدول: %s"
                          % publish.format_schedule(schedule))
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
    if "tiktok" in platforms:
        token = social_lib.load_token("tiktok")
        if token:
            try:
                res = social_lib.upload_tiktok(video, title, caption,
                                               token)
                print("تيك توك: رُفع — publish_id=%s"
                      % res["publish_id"])
                print("   تحقق من ظهور الفيديو على الحساب — أول رفع "
                      "حقيقي عبر API غير مختبَر حيًا بعد.")
            except social_lib.SocialPublishError as e:
                print("تيك توك: فشل — %s" % e)
                ok = False
        else:
            bundle_dir = os.path.join(
                expand(cfg["paths"]["videos_dir"]),
                "publish-%s-tiktok" % time.strftime("%Y%m%d-%H%M%S"))
            try:
                payload = social_lib.tiktok_init_payload(
                    video, title, caption)
            except social_lib.SocialPublishError as e:
                print("تيك توك: لا يمكن بناء الحمولة — %s" % e)
                return 1
            bundle = social_lib.write_social_bundle(
                bundle_dir, "tiktok", video, title, caption, payload)
            print("تيك توك: بلا توكن — لم يُرفع شيء.")
            print("حزمة الرفع اليدوي جاهزة في: %s" % bundle)
            print(social_lib.setup_steps("tiktok"))
            ok = False
    if "instagram" in platforms:
        ig_user_id = (cfg.get("publish") or {}).get("instagram_user_id")
        token = social_lib.load_token("instagram")
        if token and ig_user_id:
            try:
                res = social_lib.upload_instagram(
                    video, title, caption, ig_user_id, token)
                print("إنستغرام: رُفع — media_id=%s"
                      % res["media_id"])
                print("   تحقق من ظهور الريل على الحساب — أول رفع "
                      "حقيقي عبر API غير مختبَر حيًا بعد.")
            except social_lib.SocialPublishError as e:
                print("إنستغرام: فشل — %s" % e)
                ok = False
        else:
            bundle_dir = os.path.join(
                expand(cfg["paths"]["videos_dir"]),
                "publish-%s-instagram" % time.strftime("%Y%m%d-%H%M%S"))
            try:
                payload = social_lib.instagram_reel_payload(
                    video, title, caption, ig_user_id)
            except social_lib.SocialPublishError as e:
                print("إنستغرام: لا يمكن بناء الحمولة — %s" % e)
                return 1
            bundle = social_lib.write_social_bundle(
                bundle_dir, "instagram", video, title, caption, payload,
                ig_user_id=ig_user_id)
            print("إنستغرام: بلا توكن أو معرّف حساب — لم يُرفع شيء.")
            print("حزمة الرفع اليدوي جاهزة في: %s" % bundle)
            print(social_lib.setup_steps("instagram"))
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


def cmd_youtube_reauth(cfg, client_secrets=None, token=None):
    """إعادة الموافقة على يوتيوب — نفس تبادل OAuth في
    `youtube-auth`، بأمر موجَّه يطبع الرابط والخطوات.

    لا ينشر التطبيق Production ولا يغيّر مشروع Google Cloud —
    يعيد الموافقة فقط على نفس التطبيق في وضع الاختبار (7 أيام).
    """
    print("إعادة الموافقة على يوتيوب:")
    print("1. سيُفتح المتصفح لتسجيل الدخول بحساب يوتيوب.")
    print("2. وافق على نطاق الرفع (youtube.upload).")
    print("3. التوكن الجديد صالح 7 أيام (وضع الاختبار) — أعد "
          "الموافقة قبل انتهائها بيومين.")
    print("ملاحظة: نشر التطبيق Production خيار منفصل — انظر README "
          "(قسم «توكن يوتيوب: وضع الاختبار») قبل أن تقرره.")
    return cmd_youtube_auth(cfg, client_secrets=client_secrets,
                            token=token)


# ---------------------------------------------------------- long-narration
def _default_voice(cfg):
    """صوت السرد الافتراضي: من الإعداد (narration.voice — يضبطه
    معالج `init`)، وإلا piper (الراوي الرجل). قيمة غير معروفة
    في الإعداد تُعامل كـ piper."""
    voice = (cfg.get("narration") or {}).get("voice") or "piper"
    return voice if voice in ("piper", "gtts") else "piper"


def cmd_long_narration(cfg, text, text_file, out_path, gap, atempo,
                       voice="piper"):
    """سرد طويل مقسّم إلى WAV واحد (Piper رجل افتراضيًا؛ أو gTTS)."""
    if text_file:
        # إصلاح اختبار اختراق 2026-11-21: ملف نص قادم من ملف فصول
        # JSON كان يقرأ أي ملف على القرص — احصره في مساحة العمل.
        from lib.paths import resolve_inside_workspace
        text_file = resolve_inside_workspace(text_file, "ملف نص السرد")
        with open(text_file, encoding="utf-8") as f:
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


def _validate_chapters_spec(spec):
    """تحقق من بنية ملف الفصول (L5): كائن، و«chapters» قائمة،
    وكل مدخل كائن فيه «type» من الأنواع المعروفة، والحقول
    المطلوبة لكل نوع موجودة نصًا غير فارغ. يرفع LongVideoError."""
    chapters = spec.get("chapters", [])
    if not isinstance(chapters, list):
        raise long_video.LongVideoError(
            "حقل «chapters» في ملف الفصول يجب أن يكون قائمة")
    required = {"story": "story", "project": "project", "run": "run",
                "chapter-dir": "path", "text": "text"}
    for i, entry in enumerate(chapters):
        if not isinstance(entry, dict):
            raise long_video.LongVideoError(
                "الفصل %d في ملف الفصول ليس كائنًا" % (i + 1))
        kind = entry.get("type")
        if kind not in required:
            raise long_video.LongVideoError(
                "الفصل %d نوعه غير معروف: %s (المسموح: "
                "story/project/run/chapter-dir/text)"
                % (i + 1, kind))
        field = required[kind]
        value = entry.get(field)
        if kind == "text":
            value = value or entry.get("text_file")
        if not isinstance(value, str) or not value.strip():
            raise long_video.LongVideoError(
                "الفصل %d من نوع %s ينقصه الحقل «%s»"
                % (i + 1, kind, field))
        for key in ("title", "moral"):
            if key in entry and not isinstance(entry[key], str):
                raise long_video.LongVideoError(
                    "الفصل %d حقل «%s» يجب أن يكون نصًا" % (i + 1, key))
    for key in ("title", "hook", "intro", "outro", "music"):
        if key in spec and not isinstance(spec[key], str):
            raise long_video.LongVideoError(
                "حقل «%s» في ملف الفصول يجب أن يكون نصًا" % key)


def _resolve_long_chapter(cfg, entry, work_dir, atempo, index, voice="piper"):
    """حوّل مدخل فصل واحد (من ملف الفصول أو CLI) إلى قاموس فصل."""
    if not isinstance(entry, dict):
        raise long_video.LongVideoError("مدخل فصل ليس كائنًا: %r" % (entry,))
    kind = entry.get("type")
    title = entry.get("title")
    moral = entry.get("moral") or ""
    if kind == "story":
        slug = entry.get("story")
        if not isinstance(slug, str) or not slug.strip():
            raise long_video.LongVideoError(
                "فصل story بلا حقل «story»")
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
        proj = entry.get("project")
        if not isinstance(proj, str) or not proj.strip():
            raise long_video.LongVideoError(
                "فصل project بلا حقل «project»")
        return _stage_project_chapter(cfg, proj, work_dir,
                                      title=title, moral=moral)
    if kind == "run":
        run = entry.get("run")
        if not isinstance(run, str) or not run.strip():
            raise long_video.LongVideoError("فصل run بلا حقل «run»")
        return _run_chapter(cfg, run, title=title, moral=moral)
    if kind == "chapter-dir":
        # إصلاح اختبار اختراق 2026-11-21: مجلد فصل خارج مساحة العمل
        # كان يُقرأ وتُكتب فيه ملفات عمل (.long-video) — احصره.
        from lib.paths import resolve_inside_workspace
        if not isinstance(entry.get("path"), str) \
                or not entry.get("path", "").strip():
            raise long_video.LongVideoError(
                "فصل chapter-dir بلا حقل «path»")
        try:
            chapter_path = resolve_inside_workspace(entry["path"],
                                                    "مجلد الفصل")
        except ValueError as e:
            raise long_video.LongVideoError(str(e))
        return long_video.load_chapter_dir(
            chapter_path,
            work_dir=os.path.join(work_dir, "chapters", "ch%d" % index),
            atempo=atempo, title=title, moral=moral or None)
    if kind == "text":
        from lib.paths import resolve_inside_workspace
        text = entry.get("text")
        if not isinstance(text, (str, type(None))):
            raise long_video.LongVideoError(
                "الفصل النصي حقل «text» يجب أن يكون نصًا")
        if entry.get("text_file"):
            if not isinstance(entry.get("text_file"), str):
                raise long_video.LongVideoError(
                    "الفصل النصي حقل «text_file» يجب أن يكون نصًا")
            try:
                text_path = resolve_inside_workspace(entry["text_file"],
                                                     "ملف نص الفصل")
            except ValueError as e:
                raise long_video.LongVideoError(str(e))
            try:
                with open(text_path, encoding="utf-8") as f:
                    text = f.read()
            except OSError as e:
                raise long_video.LongVideoError(
                    "تعذّرت قراءة ملف نص الفصل: %s" % e)
        if not text or not text.strip():
            raise long_video.LongVideoError(
                "الفصل النصي بلا نص: %s" % (title or "?"))
        raw_images = entry.get("images", [])
        if not isinstance(raw_images, list) or any(
                not isinstance(p, str) for p in raw_images):
            raise long_video.LongVideoError(
                "الفصل النصي حقل «images» يجب أن يكون قائمة نصوص")
        try:
            images = [resolve_inside_workspace(p, "صورة الفصل")
                      for p in raw_images]
            if entry.get("cover"):
                images = [resolve_inside_workspace(entry["cover"],
                                                   "غلاف الفصل")] + images
        except ValueError as e:
            raise long_video.LongVideoError(str(e))
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
    # صوت السرد: --voice الصريح أولًا، وإلا الافتراضي من الإعداد.
    voice = getattr(args, "voice", None) or _default_voice(cfg)
    print("تشغيل الفيديو الطويل: %s" % run_id)
    try:
        spec = {}
        if args.chapters_file:
            # إصلاح اختبار اختراق 2026-11-22 (L5): ملف فصول
            # مشوَّه كان يتعطل برسائل خام (JSONDecodeError/KeyError/
            # AttributeError) — يُتحقق من البنية كلها هنا ويرفع
            # LongVideoError برسالة عربية قبل أي معالجة.
            try:
                with open(expand(args.chapters_file),
                          encoding="utf-8") as f:
                    spec = json.load(f)
            except (ValueError, OSError) as e:
                raise long_video.LongVideoError(
                    "ملف الفصول غير صالح (%s): %s"
                    % (args.chapters_file, e))
            if not isinstance(spec, dict):
                raise long_video.LongVideoError(
                    "ملف الفصول يجب أن يكون كائن JSON")
            _validate_chapters_spec(spec)
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
        if music:
            # إصلاح اختبار اختراق 2026-11-21: ملف موسيقى من ملف
            # فصول JSON كان يُقرأ من أي مسار — احصره في مساحة العمل.
            from lib.paths import resolve_inside_workspace
            try:
                music = resolve_inside_workspace(music, "ملف الموسيقى")
            except ValueError as e:
                raise long_video.LongVideoError(str(e))
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
                                       voice=voice)
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


def cmd_queue_import(cfg, text_file, title, queue_file=None, start=None):
    """استورد قصة طويلة من ملف نصي إلى الطابور — مقسَّمة لأجزاء
    ~40–60 ثانية سردًا، كل جزء بموعد مقترح (9:00/19:00 بالتناوب).

    يرجع 0 عند النجاح، و1 عند أي رفض (ملف مفقود/نص فارغ/عنوان
    مكرر)، و2 عند تاريخ بداية غير صالح.
    """
    from lib import queue_import as queue_import_lib
    from lib.paths import resolve_inside_workspace
    queue_path = expand(queue_file or cfg["paths"]["queue_file"])
    try:
        text_path = resolve_inside_workspace(text_file, "ملف نص القصة")
    except ValueError as e:
        print("ملف قصة غير صالح: %s" % e)
        return 1
    start_date = None
    if start:
        try:
            start_date = datetime.date.fromisoformat(start)
        except ValueError:
            print("تاريخ بداية غير صالح (YYYY-MM-DD): %s" % start)
            return 2
    stories_dir = os.path.join(STUDIO_DIR, "queue")
    try:
        result = queue_import_lib.import_story(
            queue_path, text_path, title, stories_dir=stories_dir,
            start_date=start_date)
    except (ValueError, queue_lib.QueueError) as e:
        print("فشل الاستيراد: %s" % e)
        return 1
    except OSError as e:
        print("فشل الكتابة في ملف الطابور: %s" % e)
        return 1
    print("استُوردت «%s» — %d أجزاء:" % (result["title"],
                                          len(result["parts"])))
    for part in result["parts"]:
        print("  الجزء %d — الطابور #%d — ~%s ثانية — مقترح %s"
              % (part["part"], part["number"], part["seconds"],
                 part["suggested_time"]))
    return 0


# ------------------------------------------------------------------ analyze
def cmd_analyze(cfg, page_id=None, channel_id=None, dna=False,
                video=None, hook=None, subs_dir=None, story_text=None,
                slug=None):
    """حلّل آخر فيديو منشور بأرقام حقيقية (فيسبوك + يوتيوب).

    يطبع المنصتين جنبًا إلى جنب + 2–3 اقتراحات تحسين مشتقة من
    الأرقام، ويحفظ JSON في runs/analyze-<وقت>.json. أي مصدر لا
    يصل يُطبع «غير معروف» — بلا أرقام مخترعة أبدًا. يرجع 1 فقط
    إن تعذر المصدران معًا.

    مع --dna: تحليل DNA الفيروسي لفيديو واحد (--video) — درجة
    الهوك 0–10 + الإيقاع + الصمت + كثافة الكلمات + حكم مربوط
    بأرقام المنصتين لنفس الفيديو (بمطابقة العنوان).
    """
    if dna:
        return cmd_analyze_dna(cfg, video=video, hook=hook,
                               subs_dir=subs_dir, story_text=story_text,
                               page_id=page_id, channel_id=channel_id,
                               slug=slug)
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


# ------------------------------------------------------- analyze --dna
def cmd_analyze_dna(cfg, video=None, hook=None, subs_dir=None,
                    story_text=None, page_id=None, channel_id=None,
                    slug=None):
    """تحليل DNA الفيروسي لفيديو واحد (الجولة 7)."""
    if not video:
        print("تحليل DNA يحتاج --video <ملف mp4>")
        return 2
    page_id = page_id or (cfg.get("publish") or {}).get("page_id")
    channel_id = (channel_id
                  or (cfg.get("publish") or {}).get("youtube_channel_id"))
    title = os.path.splitext(os.path.basename(expand(video)))[0]
    story = None
    if story_text:
        try:
            with open(expand(story_text), encoding="utf-8") as f:
                story = f.read()
        except OSError as e:
            print("تعذرت قراءة ملف نص القصة: %s" % e)
            return 1
    # أرقام المنصتين لنفس الفيديو (بمطابقة العنوان/الهوك) — أي
    # مصدر لا يصل يُطبع «غير معروف» في التقرير.
    fb = yt = None
    needle = (hook or "").strip() or title
    fb_bin = publish.find_facebook_bin()
    if page_id and fb_bin:
        entries, _note = ab_lib.fetch_fb_posts(fb_bin, page_id)
        match = ab_lib.match_variant(entries, needle, "caption")
        if match is not None:
            fb = match
    if channel_id:
        yt_entries, _note = ab_lib.fetch_yt_uploads(channel_id)
        match = ab_lib.match_variant(yt_entries, needle, "title")
        if match is not None:
            yt = match
    try:
        report = dna_lib.analyze_dna(
            expand(video), title=title, hook=hook or None,
            subs_dir=subs_dir, story_text=story, fb=fb, yt=yt,
            slug=slug)
    except dna_lib.DnaError as e:
        print("فشل تحليل DNA: %s" % e)
        return 1
    except check_lib.CheckError as e:
        print("فشل تحليل DNA: %s" % e)
        return 1
    print(dna_lib.format_report(report))
    runs_dir = expand(cfg["paths"]["runs_dir"])
    out_path = dna_lib.save_report(report, runs_dir)
    print("حُفظ تقرير DNA في: %s" % out_path)
    return 0


# ------------------------------------------------------------------ ideas
def cmd_ideas(cfg, count=5, theme=None, add=None, queue_file=None):
    """ولّد أفكار قصص بأسلوب الصفحة (النموذج أولًا، والبنك
    المحلي بديلًا)، مع منع تكرار أي عنوان في الطابور.
    --add N يضيف الفكرة رقم N إلى الطابور عبر queue add."""
    queue_path = expand(queue_file or cfg["paths"]["queue_file"])
    cfg_o = cfg["omniroute"]

    def chat_fn(prompt):
        text, _via, _model = omniroute_client.chat(
            prompt, cfg_o["model"], cfg_o.get("fallback_model"),
            cfg_o["base_url"], max_tokens=800, temperature=0.8,
            retries=int(cfg_o.get("retries", 1)),
            retry_delay=int(cfg_o.get("retry_delay_seconds", 5)))
        return text

    ideas_list, notes = ideas.generate_ideas(
        queue_path, count=count, theme=theme, chat_fn=chat_fn)
    print(ideas.format_ideas(ideas_list))
    for note in notes:
        print("ملاحظة: %s" % note)
    if not ideas_list:
        print("لم تُولَّد أي فكرة — جرّب موضوعًا آخر")
        return 1
    if add is not None:
        if add < 1 or add > len(ideas_list):
            print("رقم الفكرة غير صالح: %d (المتاح 1–%d)"
                  % (add, len(ideas_list)))
            return 2
        idea = ideas_list[add - 1]
        stories_dir = os.path.join(STUDIO_DIR, "queue")
        try:
            result = ideas.add_idea(queue_path, idea, stories_dir)
        except queue_lib.QueueError as e:
            print("رفضت الإضافة: %s" % e)
            return 1
        print("أُضيفت الفكرة رقم %d إلى الطابور: %s"
              % (result["number"], result["title"]))
        print("مسودة النص في: %s" % result["text_file"])
    return 0


# ------------------------------------------------------------------ daily
def cmd_daily(cfg, slot="morning", execute=False, video=None,
              moral="", question="", queue_file=None,
              auto_approve=False):
    """أمر اليوم الواحد: خطة (dry-run افتراضيًا) أو تنفيذ
    كامل مع --execute (إنتاج + فحص + مصغرة + نشر + نص
    أول تعليق). الجولة 7: مسار Veo يحفظ خطة المشاهد ويطلب
    الموافقة على الإنفاق تفاعليًا — إلا مع --auto-approve
    أو في تشغيل غير تفاعلي (كرون)."""
    if queue_file:
        cfg = json.loads(json.dumps(cfg))
        cfg["paths"]["queue_file"] = queue_file
    try:
        plan = daily.plan_daily(
            cfg, slot, video=video, moral=moral, question=question,
            ready_fn=lambda s: check_story_ready(cfg, s))
    except daily.DailyError as e:
        print("تعذر التخطيط لليوم: %s" % e)
        return 1
    except publish.PublishError as e:
        print("خطأ في بيانات النشر: %s" % e)
        return 1
    if not execute:
        print(daily.format_plan(plan))
        print("== وضع تجريبي — لم يُنفَّذ شيء "
              "(أضف --execute للتنفيذ) ==")
        return 0

    def produce_fn(c, slug, project, out_path):
        return cmd_run(c, slug, project, out_path, False)

    def check_fn(v):
        return check_lib.run_checks(v)

    def thumbnail_fn(v, hook, out):
        path, _sec, _lines = thumbnail.make_thumbnail(v, hook, out)
        return path

    def publish_fn(c, v, t, cap, thumb):
        return cmd_publish(c, v, t, cap, thumbnail=thumb,
                           skip_check=True)

    try:
        rc, _result = daily.execute_daily(
            cfg, plan, produce_fn, check_fn, thumbnail_fn, publish_fn,
            expand(cfg["paths"]["runs_dir"]), auto_approve=auto_approve)
    except check_lib.CheckError as e:
        print("تعذر فحص الجودة: %s" % e)
        return 1
    return rc


# ------------------------------------------------------------------ batch
def cmd_batch(cfg, count=1, source="openmontage", execute=False,
              continue_on_error=False, queue_file=None):
    """دفعة جماعية (الجولة 7): القصص التالية من الطابور في
    تشغيل واحد — إنتاج + فحص + مصغرة + سجل. افتراضيًا وضع
    تجريبي (يطبع الخطة بلا تنفيذ)؛ والتنفيذ فقط مع --execute."""
    if queue_file:
        cfg = json.loads(json.dumps(cfg))
        cfg["paths"]["queue_file"] = queue_file
    try:
        plan = batch_lib.plan_batch(
            cfg, count, source=source,
            ready_fn=lambda s: check_story_ready(cfg, s))
    except batch_lib.BatchError as e:
        print("تعذرت خطة الدفعة: %s" % e)
        return 1
    if not execute:
        print(batch_lib.format_plan(plan))
        print("== وضع تجريبي — لم يُنفَّذ شيء "
              "(أضف --execute للتنفيذ) ==")
        return 0

    def produce_fn(c, slug, project, out_path):
        return cmd_run(c, slug, project, out_path, False)

    def check_fn(v):
        return check_lib.run_checks(v)

    def thumbnail_fn(v, hook, out):
        path, _sec, _lines = thumbnail.make_thumbnail(v, hook, out)
        return path

    try:
        rc, _result = batch_lib.execute_batch(
            cfg, plan, produce_fn, check_fn, thumbnail_fn,
            expand(cfg["paths"]["runs_dir"]),
            continue_on_error=continue_on_error)
    except check_lib.CheckError as e:
        print("تعذر فحص الجودة: %s" % e)
        return 1
    return rc


# ------------------------------------------------------------- scene-plan
def cmd_scene_plan(cfg, story=None, clips=6, queue_file=None):
    """خطة مشاهد Veo مكتوبة لقصة من الطابور (الجولة 7) — تُطبع
    وتُحفظ قبل أي إنفاق، مع فحص السقف. story: رقم القصة في
    الطابور أو جزء من عنوانها."""
    if story is None:
        print("حدد القصة: --story <رقم في الطابور أو جزء من العنوان>")
        return 2
    queue_path = expand(queue_file or cfg["paths"]["queue_file"])
    if not os.path.isfile(queue_path):
        print("ملف الطابور غير موجود: %s" % queue_path)
        return 1
    try:
        stories = parse_queue(queue_path)
    except OSError as e:
        print("تعذر قراءة ملف الطابور: %s" % e)
        return 1
    target = None
    if str(story).strip().isdigit():
        for s in stories:
            if s["number"] == int(str(story).strip()):
                target = s
                break
    else:
        needle = str(story).strip()
        for s in stories:
            if needle in s["title"]:
                target = s
                break
    if target is None:
        print("لا توجد قصة مطابقة في الانتظار: %s" % story)
        return 1
    try:
        plan = scene_plan_lib.build_scene_plan(cfg, target, clips=clips)
    except scene_plan_lib.CapError as e:
        print("رفضت خطة المشاهد: %s" % e)
        return 1
    except ValueError as e:
        print("خطة مشاهد غير صالحة: %s" % e)
        return 2
    print(scene_plan_lib.format_plan(plan))
    out_path = scene_plan_lib.save_plan(
        plan, expand(cfg["paths"]["runs_dir"]))
    print("حُفظت الخطة في: %s" % out_path)
    return 0


# ------------------------------------------- tiktok-auth / instagram-auth
def cmd_social_auth(cfg, platform, token=None):
    """خطوات ربط TikTok/Instagram يدويًا + حفظ التوكن (600).

    بلا --token: يطبع الخطوات فقط. مع --token: يحفظه ولا يعرضه.
    """
    if token:
        try:
            path = social_lib.save_token(platform, token)
        except social_lib.SocialPublishError as e:
            print("فشل حفظ التوكن: %s" % e)
            return 1
        print("حُفظ توكن %s في: %s (صلاحية 600 — لم يُعرض)"
              % (platform, path))
        print("أعد النشر الآن: python3 studio.py publish --video "
              "<ملف> --title \"...\" --platforms %s" % platform)
        return 0
    print(social_lib.setup_steps(platform))
    return 0


# ---------------------------------------------------------------------- ab
def cmd_ab(cfg, video, hook_a=None, hook_b=None, title=None,
           out_dir=None, cost_per_video=0):
    """اختبار A/B: هوكان ومصغرتان لفيديو واحد + سجل الزوج.

    cost_per_video: تقدير وحدات Veo لإنتاج كل بديل من جديد
    (الافتراضي 0 — نفس الفيديو، هوك+مصغرة فقط؛ وتوليد جديد
    كامل = 120 وحدة)."""
    runs_dir = expand(out_dir or cfg["paths"]["runs_dir"])
    if not hook_a or not hook_b:
        cfg_o = cfg["omniroute"]

        def chat_fn(prompt):
            text, _via, _model = omniroute_client.chat(
                prompt, cfg_o["model"], cfg_o.get("fallback_model"),
                cfg_o["base_url"], max_tokens=200, temperature=0.8,
                retries=int(cfg_o.get("retries", 1)),
                retry_delay=int(cfg_o.get("retry_delay_seconds", 5)))
            return text

        sug_a, sug_b, src = ab_lib.suggest_hooks(
            title or os.path.basename(video), chat_fn)
        hook_a = hook_a or sug_a
        hook_b = hook_b or sug_b
        print("الهوكان المقترحان (%s)" % src)
    try:
        record = ab_lib.create_ab(expand(video), hook_a, hook_b,
                                  runs_dir, title=title,
                                  cost_per_video=cost_per_video)
    except (ValueError, thumbnail.ThumbnailError) as e:
        print("فشل اختبار A/B: %s" % e)
        return 1
    print("نسخة أ — الهوك: %s" % record["hook_a"])
    print("  المصغرة: %s" % record["thumb_a"])
    print("نسخة ب — الهوك: %s" % record["hook_b"])
    print("  المصغرة: %s" % record["thumb_b"])
    cost = record.get("cost_estimate_units") or {}
    if cost:
        print("تقدير التكلفة (وحدات Veo): أ %s — ب %s — المجموع %s"
              % (cost.get("variant_a"), cost.get("variant_b"),
                 cost.get("total")))
    print("سُجّل الزوج في: %s" % record["record_path"])
    print(ab_lib.AB_NOTE)
    print("انشر كل نسخة بعنوانها (هوكها) ثم قارن بـ:")
    print("  python3 studio.py ab-results --ab-file %s"
          % record["record_path"])
    return 0


def cmd_ab_results(cfg, ab_file=None):
    """قارن مشاهدات نسختي اختبار A/B (فيسبوك + يوتيوب)."""
    runs_dir = expand(cfg["paths"]["runs_dir"])
    if ab_file:
        path = expand(ab_file)
    else:
        candidates = sorted(
            Path(runs_dir).glob("ab-*/ab-*.json"))
        path = str(candidates[-1]) if candidates else None
    if not path or not os.path.isfile(path):
        print("لا يوجد سجل اختبار A/B — أنشئ واحدًا أولًا "
              "بـ studio.py ab")
        return 1
    with open(path, encoding="utf-8") as f:
        record = json.load(f)
    record["record_path"] = path
    page_id = (cfg.get("publish") or {}).get("page_id")
    channel_id = (cfg.get("publish") or {}).get("youtube_channel_id")
    fb_bin = publish.find_facebook_bin()
    if not page_id:
        fb_entries, fb_note = [], "معرّف الصفحة غير مضبوط"
    elif not fb_bin:
        fb_entries, fb_note = [], "facebook-cli غير متاح"
    else:
        fb_entries, fb_note = ab_lib.fetch_fb_posts(fb_bin, page_id)
    yt_entries, yt_note = ab_lib.fetch_yt_uploads(channel_id)
    if fb_note:
        print("فيسبوك: %s" % fb_note)
    if yt_note:
        print("يوتيوب: %s" % yt_note)
    comparison = ab_lib.compare_ab(record, fb_entries, yt_entries)
    print(ab_lib.format_comparison(record, comparison))
    return 0


# ------------------------------------------------------- update + backup
def cmd_update(cfg, dry_run=False,
               repo="aalhdydy550-ui/qisas-studio", branch="main"):
    """جلب آخر إصدار من GitHub وتطبيق الملفات المتغيرة فقط،
    مع نسخة احتياطية أولًا؛ والملفات المحمية لا تُمسّ أبدًا."""
    try:
        tree = update_backup.fetch_tree(repo, branch)
    except update_backup.UpdateError as e:
        print("فشل جلب الشجرة البعيدة: %s" % e)
        return 1
    changes = update_backup.plan_update(STUDIO_DIR, tree)
    if not changes:
        print("المشروع محدَّث بالفعل — لا ملفات متغيرة")
        return 0
    print("ملفات ستتغير (%d):" % len(changes))
    for change in changes:
        print("  %s %s" % ("+" if change["action"] == "add" else "~",
                           change["path"]))
    if dry_run:
        print("وضع تجريبي — لم يُكتب شيء")
        return 0

    def fetch_fn(path):
        return update_backup.fetch_file_raw(repo, branch, path)

    def backup_fn(paths):
        zip_path, _inc, _miss = update_backup.make_backup(
            STUDIO_DIR, cfg)
        print("نسخة احتياطية قبل التحديث: %s" % zip_path)
        # إصلاح اختبار اختراق 2026-11-22 (M5): نسخة ثانية من
        # الملفات المتغيرة نفسها (ومنها الكود) للتراجع منها
        # بأمر `restore --file <zip>`.
        pre_path, pre_inc = update_backup.make_pre_update_backup(
            STUDIO_DIR, paths)
        if pre_path:
            print("نسخة الملفات المتغيرة قبل التحديث: %s (%d ملفًا)"
                  % (pre_path, len(pre_inc)))

    try:
        # إصلاح اختبار اختراق 2026-11-22 (H1): تُمرَّر بصمات
        # الشجرة فيُتحقق من كل محتوى منزَّل قبل أي كتابة.
        written = update_backup.apply_update(
            STUDIO_DIR, changes, fetch_fn, backup_fn, tree=tree)
    except update_backup.UpdateError as e:
        print("فشل التحديث: %s" % e)
        return 1
    print("طُبّق %d ملفًا" % len(written))
    print("أعد تشغيل الاختبارات: "
          "python3 -m unittest discover -s tests")
    return 0


def cmd_restore(cfg, backup_file):
    """استعد ملفات من نسخة «قبل التحديث» (zip).

    التراجع الصريح من تحديث فاسد (إصلاح اختبار اختراق
    2026-11-22، M5): `studio.py restore --file
    backups/pre-update-....zip`. ملف النسخة يجب أن يكون داخل
    مجلد المشروع، والملفات المحمية لا تُستعاد أبدًا.
    """
    try:
        from lib.paths import resolve_inside
        path = resolve_inside(STUDIO_DIR, expand(backup_file),
                              "ملف النسخة الاحتياطية")
    except ValueError as e:
        print("ملف نسخة غير صالح: %s" % e)
        return 1
    try:
        restored = update_backup.restore_backup(path, STUDIO_DIR)
    except update_backup.UpdateError as e:
        print("فشلت الاستعادة: %s" % e)
        return 1
    print("استُعيد %d ملفًا من %s" % (len(restored), path))
    for name in restored:
        print("  %s" % name)
    print("أعد تشغيل الاختبارات: "
          "python3 -m unittest discover -s tests")
    return 0


def cmd_restore_backup(cfg, backup_file, dry_run=False, yes=False):
    """استرجع الإعداد والطابور وطلبات العملاء من نسخة `backup` (zip).

    أمان إلزامي: (1) كل مدخل يُفحص قبل أي كتابة — لا أسرار أبدًا
    (توكن يوتيوب/client_secrets/.env/مفاتيح تُرفض وتُلغي العملية
    كلها)؛ (2) نسخة احتياطية من الحالة الحالية تُؤخذ أولًا
    تلقائيًا، وإن تعذّرت أُلغيت الاستعادة؛ (3) تأكيد صريح قبل
    الكتابة فوق الملفات ما لم يُمرَّر --yes. --dry-run يعرض
    الخطة فقط بلا كتابة وبلا نسخة أمان.
    """
    try:
        from lib.paths import resolve_inside
        path = resolve_inside(STUDIO_DIR, expand(backup_file),
                              "ملف النسخة الاحتياطية")
    except ValueError as e:
        print("ملف نسخة غير صالح: %s" % e)
        return 1
    try:
        plan = update_backup.plan_user_restore(path, STUDIO_DIR)
    except update_backup.UpdateError as e:
        print("فشلت الاستعادة: %s" % e)
        return 1
    print("ستُستعاد %d ملفًا من %s:" % (len(plan["restorable"]), path))
    for name in plan["restorable"]:
        print("  %s" % name)
    if plan["skipped"]:
        print("تُتخطى (%d): %s" % (len(plan["skipped"]),
                                    ", ".join(plan["skipped"])))
    if dry_run:
        print("وضع تجريبي — لم يُكتب شيء، ولم تُؤخذ نسخة احتياطية")
        return 0
    if not yes:
        answer = input("ستُكتب فوق الملفات الحالية. اكتب «نعم» "
                       "للتأكيد: ").strip().lower()
        if answer not in ("نعم", "yes", "y"):
            print("أُلغيت الاستعادة — لم يتغير شيء")
            return 1
    try:
        safety, _inc, _miss = update_backup.make_backup(STUDIO_DIR, cfg)
    except update_backup.UpdateError as e:
        print("تعذّرت نسخة الأمان من الحالة الحالية — أُلغيت "
              "الاستعادة: %s" % e)
        return 1
    print("نسخة أمان من الحالة الحالية: %s" % safety)
    try:
        restored = update_backup.apply_user_restore(
            path, STUDIO_DIR, plan)
    except (update_backup.UpdateError, OSError) as e:
        print("فشلت الاستعادة أثناء الكتابة: %s" % e)
        print("الحالة السابقة محفوظة في: %s" % safety)
        return 1
    print("استُعيد %d ملفًا:" % len(restored))
    for name in restored:
        print("  %s" % name)
    print("نسخة الأمان: %s" % safety)
    return 0


def cmd_backup(cfg, out_dir=None, keep=None):
    """نسخة احتياطية zip: الإعداد + الطابور + طلبات العملاء +
    سجلات التشغيل."""
    try:
        zip_path, included, missing = update_backup.make_backup(
            STUDIO_DIR, cfg,
            out_dir=expand(out_dir) if out_dir else None,
            keep=(keep if keep is not None
                  else update_backup.BACKUP_KEEP))
    except update_backup.UpdateError as e:
        print("فشل النسخ الاحتياطي: %s" % e)
        return 1
    print("نسخة احتياطية: %s (%d ملفًا)"
          % (zip_path, len(included)))
    for name in included:
        print("  %s" % name)
    if missing:
        print("مفقود (لم يُضمَّن): %s" % ", ".join(missing))
    return 0


# ----------------------------------------------------------------- balance
def _save_veo_balance(balance_units, stamp):
    """احفظ رصيد Veo + وقت تحديثه في config.yaml بتعديل نصي.

    تعديل نصي (لا إعادة كتابة YAML) حتى تبقى تعليقات الملف.
    يرجع True عند النجاح.
    """
    import re
    config_path = os.path.join(STUDIO_DIR, "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        text = f.read()
    bal_line = "  balance_units: %d" % balance_units
    stamp_line = "  updated_at: %s" % stamp
    m = re.search(r"(?m)^veo:\n((?:  .*\n)*)", text)
    if not m or not m.group(1):
        if m:
            text = text[:m.end()] + bal_line + "\n" + stamp_line + "\n" \
                + text[m.end():]
        else:
            text = text.rstrip("\n") + "\n\nveo:\n" + bal_line + \
                "\n" + stamp_line + "\n"
    else:
        section = m.group(1)
        section = re.sub(r"(?m)^  balance_units:.*$",
                         bal_line, section)
        if "balance_units:" not in section:
            section = bal_line + "\n" + section
        section = re.sub(r"(?m)^  updated_at:.*$",
                         stamp_line, section)
        if "updated_at:" not in section:
            section += stamp_line + "\n"
        text = text[:m.start(1)] + section + text[m.end(1):]
    tmp = config_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, config_path)
    return True


def cmd_balance(cfg, balance=None, renew=None, cost_min=None,
                cost_max=None, record=None, video=None, clips=None,
                history_flag=False, cap=None, config_path=None):
    """توقع رصيد Veo بالأيام — من الرصيد المسجَّل في الإعداد
    (ليس حيًا من API).

    --record N --video NAME يسجّل إنفاقًا فعليًا بعد توليد في
    Flow في runs/cost-ledger.jsonl؛ و--history يعرض السجل.
    --cap N يضبط سقف الإنفاق لكل توليد Veo (فيديو واحد) في
    config.yaml؛ و--cap 0 يلغي السقف.
    """
    if cap is not None:
        if isinstance(cap, bool) or not isinstance(cap, int) \
                or cap < 0:
            print("سقف غير صالح: %s (المسموح: عدد صحيح ≥ 0 — و0 "
                  "يلغي السقف)" % (cap,))
            return 2
        path = config_path or os.path.join(STUDIO_DIR, "config.yaml")
        try:
            if cap == 0:
                balance_lib.remove_veo_key("cap_units", path)
                print("أُلغي سقف الإنفاق (بلا سقف الآن).")
            else:
                balance_lib.save_veo_value("cap_units", cap, path)
                print("حُفظ سقف الإنفاق (%d وحدة لكل توليد Veo) في "
                      "config.yaml." % cap)
        except (ValueError, OSError) as e:
            print("فشل حفظ السقف: %s" % e)
            return 1
        veo = dict(cfg.get("veo") or {})
        if cap == 0:
            veo.pop("cap_units", None)
        else:
            veo["cap_units"] = cap
        cfg = dict(cfg)
        cfg["veo"] = veo
    if record is not None:
        from lib import cost_ledger
        try:
            entry = cost_ledger.record(STUDIO_DIR, record, video,
                                       clips=clips)
        except ValueError as e:
            print("سجل التكاليف: %s" % e)
            return 2
        print("سُجّل إنفاق %d وحدة — %s (%s)"
              % (entry["units"], entry["video"], entry["date"]))
        return 0
    if history_flag:
        from lib import cost_ledger
        print(cost_ledger.format_history(
            cost_ledger.history(STUDIO_DIR)))
        return 0
    veo = cfg.get("veo") or {}
    bal = (balance if balance is not None
           else veo.get("balance_units", balance_lib.DEFAULT_BALANCE))
    ren = renew or veo.get("renews", balance_lib.DEFAULT_RENEWS)
    cmin = (cost_min if cost_min is not None
            else veo.get("daily_cost_min", balance_lib.DEFAULT_COST_MIN))
    cmax = (cost_max if cost_max is not None
            else veo.get("daily_cost_max", balance_lib.DEFAULT_COST_MAX))
    if balance is not None:
        # الجولة 6: احفظ الرصيد الجديد + وقت تحديثه في config.yaml.
        stamp = balance_lib.now_iso()
        _save_veo_balance(balance, stamp)
        veo = dict(veo)
        veo["balance_units"] = balance
        veo["updated_at"] = stamp
        print("حُفظ الرصيد الجديد (%d وحدة) في config.yaml مع وقت "
              "التحديث." % balance)
    try:
        result = balance_lib.forecast(bal, ren, cmin, cmax,
                                      updated_at=veo.get("updated_at"),
                                      cap_units=veo.get("cap_units"))
    except (ValueError, TypeError) as e:
        print("قيم غير صالحة: %s" % e)
        return 2
    print(balance_lib.format_forecast(result))
    return 0


def cmd_preview(cfg, video, caption=None, first_comment=None,
                out_dir=None, title=None):
    """صفحة معاينة HTML لفيديو قبل النشر (إطارات + صوت + فحص
    جودة + كابشن + أول تعليق). يرجع 0 عند النجاح."""
    from lib import preview as preview_lib
    try:
        out, result = preview_lib.build_preview(
            video, caption=caption, first_comment=first_comment,
            out_dir=expand(out_dir) if out_dir else None, title=title)
    except check_lib.CheckError as e:
        print("تعذرت المعاينة: %s" % e)
        return 1
    print("صفحة المعاينة: %s" % out)
    print(check_lib.format_report(result))
    return 0


def cmd_logs(cfg, today=True, limit=20):
    """آخر التشغيلات من runs/ ونتائجها بالعربي (اليوم افتراضيًا)."""
    from lib import runlog as runlog_lib
    runs_dir = expand(cfg["paths"]["runs_dir"])
    entries = runlog_lib.collect_runs(runs_dir, today_only=today,
                                      limit=limit)
    print(runlog_lib.format_runs(entries))
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
    p.add_argument("--accounts", action="store_true",
                   help="أضف فحوصات الحسابات: فيسبوك/يوتيوب/Veo "
                        "(قراءة فقط)")
    p = sub.add_parser("check", help="فحص جودة فيديو قبل النشر (PASS/FAIL)")
    p.add_argument("--video", required=True, help="ملف الفيديو mp4")
    p.add_argument("--long", action="store_true",
                   help="فيديو طويل أفقي 1280×720 (8–12 دقيقة)")
    p.add_argument("--json", action="store_true",
                   help="اطبع التقرير JSON بدل النص العربي")
    p = sub.add_parser("fix-audio",
                       help="إصلاح فجوات الصمت في فيديو (ضجيج وردي + "
                            "صوت المشاهد الأصلي)")
    p.add_argument("--video", required=True, help="ملف الفيديو mp4")
    p.add_argument("--scene-audio", action="append", default=[],
                   help="ملف صوت مشهد أصلي (يُكرَّر، تُدمج بالترتيب)")
    p.add_argument("--out", help="ملف الفيديو الناتج (الافتراضي: "
                                 "<الاسم>-fixed.mp4 بجانب الأصلي)")
    p = sub.add_parser("init", help="معالج إعداد تفاعلي — يكتب config.yaml")
    p.add_argument("--page-id", help="معرّف صفحة فيسبوك")
    p.add_argument("--channel-id", help="معرّف قناة يوتيوب")
    p.add_argument("--voice", choices=["piper", "gtts"],
                   help="صوت الراوي: piper (الرجل، الافتراضي) أو gtts")
    p.add_argument("--morning", help="موعد النشر الصباحي HH:MM")
    p.add_argument("--evening", help="موعد النشر المسائي HH:MM")
    p.add_argument("--queue-file", help="ملف طابور القصص")
    p.add_argument("--config",
                   help="مسار config.yaml (الافتراضي: مجلد studio)")
    p.add_argument("--force", action="store_true",
                   help="اكتب فوق config.yaml موجود بلا سؤال")
    p.add_argument("--page-name", help="اسم الصفحة (يُحفظ في identity.page_name)")
    p.add_argument("--logo-file", help="ملف الشعار PNG (يُنسخ إلى assets/qisas-logo-badge.png)")
    p.add_argument("--payment-number", help="رقم الدفع فودافون كاش (11 رقمًا يبدأ بـ 01)")
    p.add_argument("--check-only", action="store_true",
                   help="تحقق من الربط فقط بلا كتابة أي ملف")
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
    p.add_argument("--schedule",
                   help="موعد النشر المجدول بصيغة YYYY-MM-DD HH:MM "
                        "بتوقيت Africa/Cairo (مثال: 2026-11-23 19:00)؛ "
                        "أو Unix (ثوانٍ) للتوافق مع القديم — للجدولة "
                        "بدل النشر الآن")
    p.add_argument("--privacy", choices=["public", "unlisted", "private"],
                   help="خصوصية يوتيوب (الافتراضي من الإعداد: public)")
    p.add_argument("--tags",
                   help="وسوم يوتيوب مفصولة بفاصلة (الافتراضي: وسوم الصفحة)")
    p.add_argument("--dry-run", action="store_true",
                   help="اطبع الحمولة الدقيقة دون نشر أي شيء")
    p.add_argument("--skip-check", action="store_true",
                   help="تجاوز فحص الجودة المسبق (غير مستحسن)")
    p.add_argument("--skip-caption-check", action="store_true",
                   help="تجاوز فحص امتثال الكابشن (غير مستحسن — "
                        "بوابة المتابعة/التعليق ممنوعة)")
    p = sub.add_parser("youtube-auth",
                       help="تبادل OAuth ليوتيوب لمرة واحدة (يفتح المتصفح)")
    p.add_argument("--client-secrets",
                   help="ملف client_secrets.json (أو من config.yaml)")
    p.add_argument("--token",
                   help="مسار حفظ التوكن (أو من config.yaml)")
    p = sub.add_parser("youtube-reauth",
                       help="إعادة الموافقة على يوتيوب (التوكن في وضع "
                            "الاختبار ينتهي بعد 7 أيام)")
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
    p.add_argument("--voice", default=None, choices=["piper", "gtts"],
                   help="صوت السرد: piper (الراوي الرجل) أو gtts "
                        "(صوت ثانٍ اختياري) — الافتراضي من الإعداد "
                        "(narration.voice)")
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
    p.add_argument("--voice", default=None, choices=["piper", "gtts"],
                   help="صوت السرد: piper (الراوي الرجل) أو gtts "
                        "(صوت ثانٍ اختياري) — الافتراضي من الإعداد "
                        "(narration.voice)")
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
    p.add_argument("--dna", action="store_true",
                   help="تحليل DNA الفيروسي لفيديو واحد (مع --video)")
    p.add_argument("--video",
                   help="ملف الفيديو لتحليل DNA (مع --dna)")
    p.add_argument("--hook",
                   help="نص الهوك لدرجة DNA (مع --dna؛ الافتراضي: "
                        "اسم الفيديو)")
    p.add_argument("--subs-dir",
                   help="مجلد ملفات ASS لكثافة الكلمات (مع --dna)")
    p.add_argument("--slug",
                   help="بادئة ملفات ASS لكثافة الكلمات (مع --dna؛ "
                        "الافتراضي: تُشتق من اسم الفيديو)")
    p.add_argument("--story-text",
                   help="ملف نص القصة لمعيار العائد (مع --dna)")
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
    qi = qp.add_parser("import",
                       help="استيراد قصة طويلة من ملف نصي — تقسيم "
                            "لأجزاء 40–60 ثانية سردًا")
    qi.add_argument("--file", required=True, help="ملف نص القصة")
    qi.add_argument("--title", required=True, help="عنوان القصة")
    qi.add_argument("--queue-file",
                    help="ملف طابور بديل (الافتراضي من config.yaml)")
    qi.add_argument("--start",
                    help="تاريخ بداية المواعيد المقترحة (YYYY-MM-DD — "
                         "الافتراضي: اليوم)")
    p = sub.add_parser("client-run",
                       help="تنفيذ طلب فيديو عميل واحد (client-orders)")
    p.add_argument("--order", required=True, help="رقم الطلب")
    sub.add_parser("process-queue",
                   help="تنفيذ كل طلبات العملاء الجديدة (client-orders)")
    p = sub.add_parser("orders",
                       help="إدارة طلبات العملاء (تأكيد دفع/عرض)")
    op = p.add_subparsers(dest="orders_cmd", required=True)
    oc = op.add_parser("confirm",
                       help="تأكيد دفع طلب بعد التحقق من التحويل يدويًا")
    oc.add_argument("order_id", help="رقم الطلب (مثال QS-123456)")
    oc.add_argument("--by", default="owner",
                    help="من أكّد الدفع (افتراضي owner)")
    ol = op.add_parser("list",
                       help="عرض الطلبات (اختياريًا بحالة معينة)")
    ol.add_argument("--status", default=None,
                    help="تصفية بحالة (مثال awaiting_payment)")
    ot = op.add_parser("trial",
                       help="حالة التجربة المجانية لعميل (كم فيديو "
                            "مجاني بقي له)")
    ot.add_argument("whatsapp", help="رقم واتساب العميل")
    p = sub.add_parser("ideas", help="مولّد أفكار قصص بأسلوب الصفحة")
    p.add_argument("--count", type=int, default=5,
                   help="عدد الأفكار (افتراضي 5)")
    p.add_argument("--theme", default=None,
                   help="موضوع واحد من بنك المواضيع")
    p.add_argument("--add", type=int, default=None,
                   help="أضف الفكرة بهذا الرقم إلى الطابور")
    p.add_argument("--queue-file", default=None,
                   help="ملف طابور بديل (للاختبار)")
    p = sub.add_parser("daily",
                       help="أمر اليوم الواحد: إنتاج + فحص + مصغرة "
                            "+ نشر + أول تعليق")
    p.add_argument("--slot", choices=["morning", "evening"],
                   default="morning",
                   help="موعد اليوم (افتراضي الصباح)")
    p.add_argument("--execute", action="store_true",
                   help="تنفيذ حقيقي (بدونه: وضع تجريبي فقط)")
    p.add_argument("--dry-run", action="store_true",
                   help="وضع تجريبي صريح (هو الافتراضي)")
    p.add_argument("--video", default=None,
                   help="فيديو جاهز (مثلًا من Flow) بدل الإنتاج")
    p.add_argument("--moral", default="",
                   help="العبرة لنص أول تعليق والكابشن")
    p.add_argument("--question", default="",
                   help="سؤال المعضلة لنص أول تعليق")
    p.add_argument("--queue-file", default=None,
                   help="ملف طابور بديل (للاختبار)")
    p.add_argument("--auto-approve", action="store_true",
                   help="موافقة تلقائية على إنفاق Veo بخطة المشاهد "
                        "(بلا توقف تفاعلي)")
    p = sub.add_parser("batch",
                       help="دفعة جماعية: القصص التالية من الطابور "
                            "في تشغيل واحد (إنتاج + فحص + مصغرة)")
    p.add_argument("--count", type=int, default=1,
                   help="عدد القصص من بداية الطابور (افتراضي 1)")
    p.add_argument("--source", choices=["veo", "openmontage"],
                   default="openmontage",
                   help="مصدر الإنتاج (افتراضي openmontage)")
    p.add_argument("--execute", action="store_true",
                   help="تنفيذ حقيقي (بدونه: وضع تجريبي فقط)")
    p.add_argument("--continue-on-error", action="store_true",
                   help="أكمل بعد فشل قصة بدل التوقف")
    p.add_argument("--queue-file", default=None,
                   help="ملف طابور بديل (للاختبار)")
    p = sub.add_parser("scene-plan",
                       help="خطة مشاهد Veo مكتوبة لقصة من الطابور "
                            "قبل أي إنفاق (مع فحص السقف)")
    p.add_argument("--story", required=True,
                   help="رقم القصة في الطابور أو جزء من عنوانها")
    p.add_argument("--clips", type=int, default=6,
                   help="عدد المقاطع (افتراضي 6 — كل مقطع 20 وحدة)")
    p.add_argument("--queue-file", default=None,
                   help="ملف طابور بديل (للاختبار)")
    p = sub.add_parser("tiktok-auth",
                       help="خطوات ربط TikTok يدويًا + حفظ التوكن")
    p.add_argument("--token", default=None,
                   help="توكن TikTok (يُحفظ بصلاحية 600 ولا يُعرض)")
    p = sub.add_parser("instagram-auth",
                       help="خطوات ربط Instagram يدويًا + حفظ التوكن")
    p.add_argument("--token", default=None,
                   help="توكن Instagram (يُحفظ بصلاحية 600 ولا يُعرض)")
    p = sub.add_parser("ab", help="اختبار A/B: هوكان ومصغرتان "
                                  "لفيديو واحد")
    p.add_argument("--video", required=True,
                   help="ملف الفيديو")
    p.add_argument("--hook-a", default=None, help="هوك النسخة أ")
    p.add_argument("--hook-b", default=None, help="هوك النسخة ب")
    p.add_argument("--title", default=None, help="عنوان الفيديو")
    p.add_argument("--out-dir", default=None,
                   help="مجلد السجلات (افتراضي runs/)")
    p.add_argument("--cost-per-video", type=int, default=0,
                   help="تقدير وحدات Veo لإنتاج كل بديل من جديد "
                        "(افتراضي 0 — نفس الفيديو بلا توليد جديد؛ "
                        "وتوليد جديد كامل = 120)")
    p = sub.add_parser("ab-results",
                       help="قارن مشاهدات نسختي اختبار A/B")
    p.add_argument("--ab-file", default=None,
                   help="ملف سجل ab-*.json (افتراضي: الأحدث)")
    p = sub.add_parser("update",
                       help="جلب آخر إصدار من GitHub وتطبيقه "
                            "(مع نسخة احتياطية)")
    p.add_argument("--dry-run", action="store_true",
                   help="اعرض ما سيتغير بلا كتابة")
    p.add_argument("--repo", default="aalhdydy550-ui/qisas-studio",
                   help="المستودع (افتراضي aalhdydy550-ui/qisas-studio)")
    p.add_argument("--branch", default="main",
                   help="الفرع (افتراضي main)")
    p = sub.add_parser("restore",
                       help="استعادة الإعداد والطابور وطلبات العملاء "
                            "من نسخة backup (أو تراجع من تحديث فاسد)")
    p.add_argument("--backup",
                   help="ملف zip النسخة (من `studio.py backup`) — "
                        "يسترجع الإعداد والطابور وطلبات العملاء فقط")
    p.add_argument("--file",
                   help="ملف zip نسخة «قبل التحديث» (تراجع من "
                        "تحديث فاسد — لا يسترجع ملفات محمية)")
    p.add_argument("--dry-run", action="store_true",
                   help="اعرض خطة الاستعادة دون كتابة (مع --backup)")
    p.add_argument("--yes", action="store_true",
                   help="تجاوز سؤال التأكيد (غير تفاعلي)")
    p = sub.add_parser("backup",
                       help="نسخة احتياطية zip للإعداد والطابور "
                            "والطلبات والسجلات")
    p.add_argument("--out-dir", default=None,
                   help="مجلد النسخ (افتراضي backups/)")
    p.add_argument("--keep", type=int, default=None,
                   help="عدد النسخ المحتفَظ بها (افتراضي 7)")
    p = sub.add_parser("preview",
                       help="صفحة معاينة HTML لفيديو قبل النشر "
                            "(إطارات + صوت + فحص جودة + كابشن)")
    p.add_argument("--video", required=True, help="ملف الفيديو mp4")
    p.add_argument("--caption", help="نص الكابشن")
    p.add_argument("--first-comment", help="نص أول تعليق")
    p.add_argument("--out-dir",
                   help="مجلد حفظ الصفحة (افتراضي: بجانب الفيديو)")
    p.add_argument("--title", help="عنوان الصفحة (افتراضي: اسم الفيديو)")
    p = sub.add_parser("logs",
                       help="آخر التشغيلات من runs/ ونتائجها بالعربي")
    p.add_argument("--today", action="store_true",
                   help="اليوم فقط (الافتراضي)")
    p.add_argument("--all", dest="all_logs", action="store_true",
                   help="كل الأيام بدل اليوم فقط")
    p.add_argument("--limit", type=int, default=20,
                   help="أقصى عدد تشغيلات (افتراضي 20)")
    p = sub.add_parser("balance",
                       help="توقع رصيد Veo بالأيام (مسجَّل لا حي)")
    p.add_argument("--balance", type=int, default=None,
                   help="رصيد حالي بديل (وحدة)")
    p.add_argument("--renew", default=None,
                   help="تاريخ تجديد بديل (YYYY-MM-DD)")
    p.add_argument("--cost-min", type=int, default=None,
                   help="أقل تكلفة فيديو يومي (وحدة)")
    p.add_argument("--cost-max", type=int, default=None,
                   help="أعلى تكلفة فيديو يومي (وحدة)")
    p.add_argument("--record", type=int, default=None,
                   help="سجّل إنفاقًا فعليًا بعد توليد في Flow (وحدة) "
                        "— مع --video")
    p.add_argument("--video", default=None,
                   help="اسم الفيديو للإنفاق المسجَّل (مع --record)")
    p.add_argument("--clips", type=int, default=None,
                   help="عدد مقاطع التوليد (مع --record)")
    p.add_argument("--history", action="store_true",
                   help="اعرض سجل التكاليف المسجَّلة")
    p.add_argument("--cap", type=int, default=None,
                   help="سقف الإنفاق: حد أقصى لوحدات Veo لكل توليد "
                        "(فيديو واحد) — يُحفظ في config.yaml؛ و0 "
                        "يلغي السقف")
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
        return cmd_doctor(cfg, fix=args.fix, accounts_flag=args.accounts)
    if args.cmd == "check":
        return cmd_check(cfg, args.video, long_mode=args.long,
                         as_json=args.json)
    if args.cmd == "fix-audio":
        return cmd_fix_audio(cfg, args.video,
                             scene_audio=args.scene_audio or None,
                             out_path=args.out)
    if args.cmd == "init":
        return cmd_init(cfg, args)
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
            _print_translated("فشل التجميع", e, "assemble")
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
               if pl not in ("facebook", "youtube", "tiktok",
                             "instagram")]
        if bad:
            print("منصات غير معروفة: %s (المسموح: facebook,youtube,"
                  "tiktok,instagram)" % ", ".join(bad))
            return 2
        if not platforms:
            print("حدد منصة واحدة على الأقل في --platforms")
            return 2
        tags = ([t.strip() for t in args.tags.split(",") if t.strip()]
                if args.tags else None)
        schedule = None
        if args.schedule:
            try:
                schedule = publish.parse_schedule(args.schedule)
            except publish.PublishError as e:
                print("خطأ في موعد الجدولة: %s" % e)
                return 2
        return cmd_publish(cfg, args.video, args.title, args.caption,
                           thumbnail=args.thumbnail, platforms=platforms,
                           page_id=args.page_id, schedule=schedule,
                           privacy=args.privacy, tags=tags,
                           dry_run=args.dry_run,
                           skip_check=args.skip_check,
                           skip_caption_check=args.skip_caption_check)
    if args.cmd == "youtube-auth":
        return cmd_youtube_auth(cfg, args.client_secrets, args.token)
    if args.cmd == "youtube-reauth":
        return cmd_youtube_reauth(cfg, args.client_secrets, args.token)
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
        if args.queue_cmd == "import":
            return cmd_queue_import(cfg, args.file, args.title,
                                    queue_file=args.queue_file,
                                    start=args.start)
        return 2
    if args.cmd == "analyze":
        return cmd_analyze(cfg, page_id=args.page_id,
                           channel_id=args.channel_id, dna=args.dna,
                           video=args.video, hook=args.hook,
                           subs_dir=args.subs_dir,
                           story_text=args.story_text,
                           slug=args.slug)
    if args.cmd == "long-narration":
        try:
            cmd_long_narration(cfg, args.text, args.text_file,
                               args.out, args.gap, args.atempo,
                               voice=args.voice or _default_voice(cfg))
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
    if args.cmd == "orders":
        import client_orders
        if args.orders_cmd == "confirm":
            return client_orders.cmd_confirm_payment(cfg, args.order_id,
                                                     confirmed_by=args.by)
        if args.orders_cmd == "list":
            return client_orders.cmd_list_orders(status=args.status)
        if args.orders_cmd == "trial":
            return client_orders.cmd_trial_status(args.whatsapp)
    if args.cmd == "ideas":
        return cmd_ideas(cfg, count=args.count, theme=args.theme,
                         add=args.add, queue_file=args.queue_file)
    if args.cmd == "daily":
        return cmd_daily(cfg, slot=args.slot,
                         execute=args.execute and not args.dry_run,
                         video=args.video, moral=args.moral,
                         question=args.question,
                         queue_file=args.queue_file,
                         auto_approve=args.auto_approve)
    if args.cmd == "batch":
        return cmd_batch(cfg, count=args.count, source=args.source,
                         execute=args.execute,
                         continue_on_error=args.continue_on_error,
                         queue_file=args.queue_file)
    if args.cmd == "scene-plan":
        return cmd_scene_plan(cfg, story=args.story,
                              clips=args.clips,
                              queue_file=args.queue_file)
    if args.cmd == "tiktok-auth":
        return cmd_social_auth(cfg, "tiktok", token=args.token)
    if args.cmd == "instagram-auth":
        return cmd_social_auth(cfg, "instagram", token=args.token)
    if args.cmd == "ab":
        return cmd_ab(cfg, args.video, args.hook_a, args.hook_b,
                      args.title, args.out_dir,
                      cost_per_video=args.cost_per_video)
    if args.cmd == "ab-results":
        return cmd_ab_results(cfg, args.ab_file)
    if args.cmd == "update":
        return cmd_update(cfg, dry_run=args.dry_run, repo=args.repo,
                          branch=args.branch)
    if args.cmd == "restore":
        if args.backup and args.file:
            print("حدد إما --backup أو --file، لا كليهما")
            return 1
        if args.backup:
            return cmd_restore_backup(cfg, args.backup,
                                      dry_run=args.dry_run, yes=args.yes)
        if args.file:
            return cmd_restore(cfg, args.file)
        print("حدد ملف النسخة: --backup <ملف.zip> أو --file <ملف.zip>")
        return 1
    if args.cmd == "backup":
        return cmd_backup(cfg, args.out_dir, keep=args.keep)
    if args.cmd == "preview":
        return cmd_preview(cfg, args.video, caption=args.caption,
                           first_comment=args.first_comment,
                           out_dir=args.out_dir, title=args.title)
    if args.cmd == "logs":
        return cmd_logs(cfg, today=not args.all_logs,
                        limit=args.limit)
    if args.cmd == "balance":
        return cmd_balance(cfg, balance=args.balance, renew=args.renew,
                           cost_min=args.cost_min,
                           cost_max=args.cost_max,
                           record=args.record, video=args.video,
                           clips=args.clips,
                           history_flag=args.history,
                           cap=args.cap)
    return 0


if __name__ == "__main__":
    sys.exit(main())
