#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""معالج الإعداد — `studio.py init`: إعداد أول مرة بالعربية.

يسأل عن: معرّف صفحة فيسبوك، ومعرّف قناة يوتيوب، وصوت
الراوي (Piper رجل افتراضيًا)، وموعدي النشر اليومي، وملف
طابور القصص — ويكتبها في config.yaml. يعرض أيضًا ملف
الكرونات المقترحة (نشر يومي + فيديو طويل أسبوعي) دون
تثبيتها صامتًا: التثبيت قرار المستخدم وحده.

الجولة 6 — ينهي الربط فعلًا، خطوة بخطوة:
- بعد كتابة الإعداد يتحقق من كل حساب: فيسبوك (قراءة آخر
  المنشورات عبر facebook-cli — نفس فحص `doctor --accounts`)،
  ويوتيوب (توكن OAuth وسريانه)، وثنائي Piper وموديل صوته،
  وخط Noto Naskh Arabic، وشارة الشعار. كل عنصر ناقص يُعرض
  كخطوة واحدة واضحة بالعربي مع الأمر أو الرابط الجاهز.
- يسأل عن الهوية والدفع: اسم الصفحة، وملف الشعار (يُتحقق
  أنه PNG صالح ثم يُنسخ إلى assets/qisas-logo-badge.png)،
  ورقم الدفع (فودافون كاش) — وتُكتب في config.yaml تحت
  قسمي `identity` و`payment`. وإن كان الرقم الجديد مختلفًا
  عن الرقم المكتوب في README.md وREADME_EN.md حدّثهما به.
- `--check-only`: تحقق فقط من الربط بلا كتابة أي ملف.

يعمل بلا تفاعل عبر الأعلام (--page-id وغيرها) لزوم
الاختبارات؛ ولا يكتب فوق config.yaml موجود إلا بعد تأكيد
صريح (--force أو إجابة y في الوضع التفاعلي). لا يلمس
المنشورات المجدولة ولا الطابور ولا بيانات العملاء أبدًا.
"""
import copy
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
EGYPT_MOBILE_RE = re.compile(r"^(?:01[0-9]{9}|\+201[0-9]{9})$")
DEFAULT_MORNING = "09:00"
DEFAULT_EVENING = "19:00"
DEFAULT_VOICE = "piper"
VOICES = ("piper", "gtts")

# رقم الدفع القديم المكتوب في README.md وREADME_EN.md — يُستبدل
# بالرقم الجديد فقط حين يُدخله المستخدم صراحةً (لا يُخترع رقم).
OLD_PAYMENT_NUMBER = "01023468196"
LOGO_BADGE_REL = os.path.join("assets", "qisas-logo-badge.png")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

CONFIG_HEADER = (
    "# إعدادات studio — كُتبت عبر `studio.py init`.\n"
    "# لا تضع أي مفاتيح أو بيانات اعتماد هنا أبدًا.\n"
    "# مفتاح بوابة OmniRoute يمرَّر عبر متغير البيئة "
    "OMNIROUTE_API_KEY فقط.\n\n")


class InitError(Exception):
    """خطأ في معالج الإعداد (رسالته عربية)."""


def validate_time(text, what="الوقت"):
    """تحقق من صيغة HH:MM (24 ساعة). يرجع النص كما هو أو يرفع."""
    text = (text or "").strip()
    if not TIME_RE.match(text):
        raise InitError("%s بصيغة HH:MM (مثال 09:00) — وصل: %s"
                        % (what, text or "فارغ"))
    return text


def validate_page_id(text):
    """معرّف صفحة فيسبوك: أرقام فقط (أو فارغ = يُضبط لاحقًا)."""
    text = (text or "").strip()
    if text and not text.isdigit():
        raise InitError("معرّف الصفحة أرقام فقط (وصل: %s)" % text)
    return text


def validate_voice(text):
    """صوت الراوي: piper (الرجل، الافتراضي) أو gtts (اختياري)."""
    text = (text or "").strip().lower()
    if text not in VOICES:
        raise InitError("الصوت piper أو gtts فقط (وصل: %s)" % text)
    return text


def validate_page_name(text):
    """اسم الصفحة: نص حر حتى 100 حرف (أو فارغ = يُضبط لاحقًا)."""
    text = (text or "").strip()
    if len(text) > 100:
        raise InitError("اسم الصفحة حتى 100 حرف (وصل %d حرفًا)"
                        % len(text))
    return text


def validate_payment_number(text):
    """رقم الدفع (فودافون كاش): مصري 11 رقمًا يبدأ بـ 01، أو
    بالصيغة الدولية +20. تُزال المسافات والشرطات، ويُرجع
    الصيغة المحلية 01XXXXXXXXX (أو فارغ = يُضبط لاحقًا)."""
    text = (text or "").strip().replace(" ", "").replace("-", "")
    if not text:
        return ""
    if not EGYPT_MOBILE_RE.match(text):
        raise InitError(
            "رقم الدفع مصري 11 رقمًا يبدأ بـ 01 (مثال 01023468196) "
            "— وصل: %s" % text)
    if text.startswith("+20"):
        text = "0" + text[3:]
    return text


def validate_logo_png(path):
    """تحقق أن الملف PNG صالح: التوقيع السحري + قطعة IHDR
    بأبعاد موجبة. يرجع (العرض، الارتفاع) أو يرفع InitError."""
    path = os.path.expanduser(str(path or ""))
    if not path or not os.path.isfile(path):
        raise InitError("ملف الشعار غير موجود: %s" % (path or "فارغ"))
    try:
        with open(path, "rb") as f:
            head = f.read(33)
    except OSError as e:
        raise InitError("تعذرت قراءة ملف الشعار (%s)" % e)
    if len(head) < 33 or head[:8] != PNG_MAGIC:
        raise InitError("ملف الشعار ليس PNG صالحًا (التوقيع غير "
                        "مطابق) — أرسل صورة PNG: %s" % path)
    if head[12:16] != b"IHDR":
        raise InitError("ملف الشعار PNG تالف (بلا قطعة IHDR): %s"
                        % path)
    width, height = struct.unpack(">II", head[16:24])
    if not (0 < width <= 8192 and 0 < height <= 8192):
        raise InitError("أبعاد الشعار غير صالحة (%d×%d)" %
                        (width, height))
    return width, height


def install_logo(src_path, studio_dir):
    """انسخ ملف شعار PNG صالح إلى assets/qisas-logo-badge.png
    داخل مجلد studio (كتابة ذرية). يرجع مسار الوجهة."""
    width, height = validate_logo_png(src_path)
    dest = os.path.join(studio_dir, LOGO_BADGE_REL)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    dir_name = os.path.dirname(dest)
    fd, tmp = tempfile.mkstemp(dir=dir_name, prefix=".logo-",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as out:
            with open(os.path.expanduser(src_path), "rb") as src:
                shutil.copyfileobj(src, out)
        os.replace(tmp, dest)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return dest, width, height


def apply_answers(cfg, answers):
    """طبّق إجابات المعالج على نسخة من الإعداد. يرجع الإعداد الجديد."""
    cfg = copy.deepcopy(cfg)
    if answers.get("page_id") is not None:
        cfg.setdefault("publish", {})["page_id"] = \
            validate_page_id(answers["page_id"])
    if answers.get("channel_id") is not None:
        cfg.setdefault("publish", {})["youtube_channel_id"] = \
            (answers["channel_id"] or "").strip()
    if answers.get("queue_file") is not None:
        cfg.setdefault("paths", {})["queue_file"] = \
            (answers["queue_file"] or "").strip()
    if answers.get("morning") is not None:
        cfg.setdefault("schedule", {})["morning"] = \
            validate_time(answers["morning"], "موعد النشر الصباحي")
    if answers.get("evening") is not None:
        cfg.setdefault("schedule", {})["evening"] = \
            validate_time(answers["evening"], "موعد النشر المسائي")
    if answers.get("voice") is not None:
        cfg.setdefault("narration", {})["voice"] = \
            validate_voice(answers["voice"])
    # الجولة 6 — الهوية والدفع (فارغ = أبقِ الحالي).
    if answers.get("page_name"):
        cfg.setdefault("identity", {})["page_name"] = \
            validate_page_name(answers["page_name"])
    if answers.get("payment_number"):
        cfg.setdefault("payment", {})["method"] = "vodafone_cash"
        cfg["payment"]["vodafone_cash"] = \
            validate_payment_number(answers["payment_number"])
    return cfg


def _write_atomic(path, text):
    """اكتب نصًا في ملف ذريًا (ملف مؤقت بنفس المجلد ثم
    os.replace) — فانقطاع منتصف الكتابة لا يترك config.yaml
    نصف مكتوب (اختراق 2026-11-22: الكتابة كانت مباشرة)."""
    dir_name = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=dir_name, prefix=".init-",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_config(path, cfg):
    """اكتب config.yaml (YAML + ترويسة توضيحية)."""
    try:
        import yaml
    except ImportError:
        raise InitError("PyYAML غير متاح — لا يمكن كتابة config.yaml")
    text = yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False,
                          default_flow_style=False)
    _write_atomic(path, CONFIG_HEADER + text)
    return path


def update_readme_payment_number(studio_dir, new_number,
                                 print_fn=print):
    """حدّث رقم الدفع في README.md وREADME_EN.md داخل مجلد studio.

    يستبدل الرقم القديم بالجديد فقط إن وُجد وكان مختلفًا؛
    ويعيد قائمة الملفات المحدَّثة. بلا رقم جديد أو بلا ملفات
    تحمل الرقم القديم لا يكتب شيئًا.
    """
    new_number = validate_payment_number(new_number or "")
    if not new_number or new_number == OLD_PAYMENT_NUMBER:
        return []
    updated = []
    for name in ("README.md", "README_EN.md"):
        path = os.path.join(studio_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        if OLD_PAYMENT_NUMBER not in text:
            continue
        _write_atomic(path, text.replace(OLD_PAYMENT_NUMBER,
                                         new_number))
        updated.append(path)
        print_fn("حُدّث رقم الدفع في %s" % name)
    return updated


def suggested_crons_text(cfg):
    """نص الكرونات المقترحة (أوامر/ملفات — لم تُثبَّت).

    النشر اليومي مرتان (صباحًا ومساءً) والفيديو الطويل أسبوعيًا
    يوم الجمعة — نفس مواعيد صفحة «قصص وعبر».
    """
    morning = (cfg.get("schedule") or {}).get("morning",
                                              DEFAULT_MORNING)
    evening = (cfg.get("schedule") or {}).get("evening",
                                              DEFAULT_EVENING)
    queue = (cfg.get("paths") or {}).get("queue_file", "")
    videos = (cfg.get("paths") or {}).get("videos_dir",
                                          "~/workspace/videos")
    mh, mm = morning.split(":")
    eh, em = evening.split(":")
    lines = [
        "# كرونات مقترحة — لم تُثبَّت تلقائيًا.",
        "# ثبّتها بنفسك حين تقرر (عبر أدوات الجدولة أو من التيرمينال).",
        "# كل كرون: المعرّف، والموعد، والمهمة.",
        "",
        "## 1) النشر الصباحي — يوميًا %s (بتوقيت القاهرة)" % morning,
        "المعرّف: qisas-morning-publish",
        "الموعد: %s:%s يوميًا" % (mh, mm),
        "المهمة: إنتاج فيديو الصباح من القصة التالية في الطابور",
        "  (%s) عبر خط OpenMontage بلا رصيد، ثم فحصه" % queue,
        "  (`studio.py check --video <الملف>`) ونشره على فيسبوك",
        "  ويوتيوب (`studio.py publish --video <الملف> --title <العنوان>`).",
        "",
        "## 2) النشر المسائي — يوميًا %s (بتوقيت القاهرة)" % evening,
        "المعرّف: qisas-evening-publish",
        "الموعد: %s:%s يوميًا" % (eh, em),
        "المهمة: مثل الصباحي — القصة التالية في الطابور، إنتاج",
        "  OpenMontage بلا رصيد، ثم فحص ونشر.",
        "",
        "## 3) الفيديو الطويل الأسبوعي — الجمعة 20:03",
        "المعرّف: qisas-weekly-long-video",
        "الموعد: الجمعة 20:03 أسبوعيًا",
        "المهمة: فيديو طويل أفقي 1280×720 (8–12 دقيقة) من قصص",
        "  الأسبوع المنشورة، بلا رصيد Veo أبدًا:",
        "  `python3 studio.py long-video --auto-week "
        "--out %s/long-weekly.mp4`" % videos,
        "  ثم نشره على يوتيوب فقط.",
        "",
        "## قواعد ثابتة في كل الكرونات",
        "- قبل أي نشر: حلّل أداء الفيديو السابق وحسّن التالي عليه.",
        "- كل فيديو 40–60 ثانية؛ والشعار أعلى اليمين تلقائيًا.",
        "- بطاقات الاقتباس صور مستقلة — لا تُلْحق بأي فيديو أبدًا.",
        "",
    ]
    return "\n".join(lines)


def write_suggested_crons(path, cfg):
    """اكتب ملف الكرونات المقترحة بجانب config.yaml."""
    _write_atomic(path, suggested_crons_text(cfg))
    return path


# ------------------------------------------------------- فحوصات الربط

def _short_fb_runner(cmd, **kw):
    """مشغّل facebook-cli بمهلة 30 ثانية (بدل 120 في analyze)
    حتى لا يعلّق المعالج على شبكة بطيئة."""
    kw.pop("timeout", None)
    return subprocess.run(cmd, capture_output=True, text=True,
                          timeout=30, **kw)


def facebook_connect_url(fb_bin, runner=None):
    """رابط ربط فيسبوك (أفضل جهد): شغّل `facebook-cli
    connect-url` واستخرج connect_url من مخرجاته. يرجع الرابط
    أو None إن تعذر — وعندها تُطبع الخطوة كأمر يدوي."""
    run = runner or (lambda cmd, **kw: subprocess.run(
        cmd, capture_output=True, text=True, timeout=30, **kw))
    try:
        proc = run([fb_bin, "connect-url"])
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout or "")
    except ValueError:
        return None
    url = (data or {}).get("connect_url") or ""
    return url.strip() or None


def check_link_steps(cfg, fb_runner=None):
    """تحقق من كل حساب خطوة بخطوة. يرجع قائمة قواميس مثل
    doctor: {key, name, ok, level, detail, fix} — قراءة فقط،
    لا يكتب شيئًا ولا ينشر شيئًا.

    fb_runner: دالة تشغيل قابلة للحقن في الاختبارات (بدل
    subprocess الحقيقي لفيسبوك).
    """
    from lib import accounts as accounts_lib
    from lib import doctor as doctor_lib
    from lib import long_narration
    from lib import publish as publish_lib

    steps = []
    # 1) فيسبوك — نفس فحص doctor --accounts (قراءة المنشورات).
    fb = accounts_lib.check_facebook_page(
        cfg, runner=fb_runner or _short_fb_runner)
    fb = dict(fb)
    fb["key"] = "facebook"
    if not fb["ok"] and "facebook-cli غير متاح" in fb["detail"]:
        fb["fix"] = ("ثبّت facebook-cli ثم شغّل "
                     "`facebook-cli connect-url` وافتح الرابط")
    elif not fb["ok"] and "معرّف الصفحة مفقود" in fb["detail"]:
        fb["fix"] = ("اضبط معرّف الصفحة في المعالج (--page-id) ثم "
                     "أعد `studio.py init --check-only`")
    elif not fb["ok"]:
        fb_bin = publish_lib.find_facebook_bin()
        url = (facebook_connect_url(fb_bin, runner=fb_runner)
               if fb_bin else None)
        if url:
            fb["fix"] = ("افتح رابط الربط ووافق في Meta Accounts "
                         "Center ثم أعد الفحص: %s" % url)
        else:
            fb["fix"] = ("شغّل `facebook-cli connect-url` وافتح "
                         "الرابط الظاهر ووافق في Meta Accounts "
                         "Center، ثم أعد الفحص")
    steps.append(fb)

    # 2) يوتيوب — توكن OAuth وسريانه (قراءة ملف فقط).
    yt = accounts_lib.check_youtube_token(cfg)
    yt = dict(yt)
    yt["key"] = "youtube"
    if not yt["ok"] and "لا يوجد توكن" in yt["detail"]:
        secrets = os.path.expanduser(
            (cfg.get("publish") or {}).get("youtube_client_secrets")
            or "~/workspace/studio/client_secrets.json")
        if os.path.isfile(secrets):
            yt["fix"] = ("خطوة واحدة: شغّل "
                         "`python3 studio.py youtube-auth` — سيُفتح "
                         "المتصفح؛ سجّل دخولك بحساب يوتيوب ووافق على "
                         "نطاق الرفع، وسيُحفظ التوكن تلقائيًا")
        else:
            yt["fix"] = ("خطوة واحدة: أنشئ مشروعًا في Google Cloud "
                         "Console وفعّل YouTube Data API v3، وحمّل "
                         "client_secrets.json إلى %s ثم شغّل "
                         "`python3 studio.py youtube-auth`" % secrets)
    steps.append(yt)

    # 3) ثنائي Piper.
    piper_bin = shutil.which("piper") or os.path.expanduser(
        "~/.local/bin/piper")
    if piper_bin and os.path.isfile(piper_bin):
        steps.append({"key": "piper_bin", "name": "Piper (ثنائي السرد)",
                      "ok": True, "level": "error",
                      "detail": piper_bin, "fix": ""})
    else:
        steps.append({"key": "piper_bin", "name": "Piper (ثنائي السرد)",
                      "ok": False, "level": "error",
                      "detail": "غير موجود",
                      "fix": "ثبّت Piper في ~/.local/bin/piper "
                             "(انظر README)"})

    # 4) موديل صوت Piper.
    model = os.path.expanduser(long_narration.PIPER_MODEL)
    if os.path.isfile(model):
        steps.append({"key": "piper_model",
                      "name": "موديل صوت Piper (ar_JO-kareem-medium)",
                      "ok": True, "level": "error", "detail": model,
                      "fix": ""})
    else:
        steps.append({"key": "piper_model",
                      "name": "موديل صوت Piper (ar_JO-kareem-medium)",
                      "ok": False, "level": "error",
                      "detail": "غير موجود: %s" % model,
                      "fix": "نزّل موديل ar_JO-kareem-medium "
                             "(onnx + onnx.json) من مستودع أصوات "
                             "Piper (rhasspy/piper-voices) إلى "
                             "~/workspace/tts-models/"})

    # 5) خط Noto Naskh Arabic (فحص doctor نفسه).
    font = dict(doctor_lib._font_check())
    font["key"] = "font"
    steps.append(font)

    # 6) شارة الشعار.
    logo = dict(doctor_lib._file_check(
        doctor_lib.DEFAULT_PATHS["logo_badge"],
        "شارة شعار «قصص وعبر»", level="warn",
        fix="أعد `studio.py init --logo-file <ملف PNG>`"))
    logo["key"] = "logo"
    steps.append(logo)
    return steps


def format_link_steps(steps):
    """نص عربي لنتائج فحوصات الربط + الخطوات اليدوية الباقية."""
    lines = ["== الربط — خطوة بخطوة =="]
    missing = 0
    for s in steps:
        if s["ok"]:
            lines.append("[PASS] %s — %s" % (s["name"], s["detail"]))
        else:
            missing += 1
            line = "[FAIL] %s — %s" % (s["name"], s["detail"])
            if s.get("fix"):
                line += "  ← %s" % s["fix"]
            lines.append(line)
    if missing:
        lines.append("بقي %d %s يدوية أعلاه — كل واحدة خطوة واحدة "
                     "بأمرها أو رابطها الجاهز." %
                     (missing, "خطوة" if missing == 1 else "خطوات"))
    else:
        lines.append("النتيجة: كل حسابات الربط سليمة — لا خطوات باقية.")
    return "\n".join(lines)


# ------------------------------------------------------- الأسئلة التفاعلية

def prompt_answers(current, input_fn=input, print_fn=print):
    """اسأل المستخدم أسئلة الإعداد بالعربية (تفاعلي).

    current: الإعداد الحالي (للقيم الافتراضية المعروضة).
    يرجع قاموس إجابات — فارغ يعني «أبقِ الحالي».
    """
    publish = current.get("publish") or {}
    paths = current.get("paths") or {}
    schedule = current.get("schedule") or {}
    narration = current.get("narration") or {}

    def ask(question, default):
        shown = default if default else "فارغ"
        raw = input_fn("%s [%s]: " % (question, shown)).strip()
        return raw if raw else default

    print_fn("معالج إعداد studio — أجب أو اترك فارغًا للقيمة الحالية.")
    answers = {}
    answers["page_id"] = ask("معرّف صفحة فيسبوك",
                             str(publish.get("page_id") or ""))
    answers["channel_id"] = ask(
        "معرّف قناة يوتيوب",
        str(publish.get("youtube_channel_id") or ""))
    answers["voice"] = ask("صوت الراوي (piper رجل / gtts ثانٍ)",
                           str(narration.get("voice") or DEFAULT_VOICE))
    answers["morning"] = ask("موعد النشر الصباحي (HH:MM)",
                             str(schedule.get("morning")
                                 or DEFAULT_MORNING))
    answers["evening"] = ask("موعد النشر المسائي (HH:MM)",
                             str(schedule.get("evening")
                                 or DEFAULT_EVENING))
    answers["queue_file"] = ask("ملف طابور القصص",
                                str(paths.get("queue_file") or ""))
    return answers


def prompt_identity(current, input_fn=input, print_fn=print):
    """اسأل عن الهوية والدفع (تفاعلي) — تُستدعى بعد أسئلة
    الإعداد الأساسية وبعد تأكيد الكتابة فوق ملف موجود، حتى
    لا يزيح أي سؤال إجابة التأكيد. فارغ = أبقِ الحالي.
    يتحمّل انتهاء الإدخال (StopIteration/EOFError) كإجابة فارغة.
    """
    identity = current.get("identity") or {}
    payment = current.get("payment") or {}

    def ask(question, default):
        shown = default if default else "فارغ"
        try:
            raw = input_fn("%s [%s]: " % (question, shown)).strip()
        except (StopIteration, EOFError):
            return default
        return raw if raw else default

    print_fn("الهوية والدفع — أجب أو اترك فارغًا للقيمة الحالية.")
    answers = {}
    answers["page_name"] = ask("اسم الصفحة",
                               str(identity.get("page_name") or ""))
    answers["logo_file"] = ask(
        "ملف الشعار PNG (يُنسخ إلى assets/qisas-logo-badge.png)",
        "")
    answers["payment_number"] = ask(
        "رقم الدفع (فودافون كاش — 11 رقمًا يبدأ بـ 01)",
        str(payment.get("vodafone_cash") or ""))
    return answers


def run_wizard(cfg, config_path, flags=None, force=False,
               input_fn=input, print_fn=print, check_only=False,
               fb_runner=None):
    """نفّذ المعالج كاملًا. يرجع 0 عند النجاح و1 عند الرفض/الخطأ.

    flags: إجابات من الأعلام (بلا تفاعل)؛ وإن كانت None يُسأل
    المستخدم تفاعليًا. force: اكتب فوق ملف موجود بلا سؤال.
    check_only: تحقق من الربط فقط واطبع النتيجة بلا كتابة
    أي ملف (علم --check-only). fb_runner: مشغّل facebook-cli
    قابل للحقن في الاختبارات.
    """
    if check_only:
        steps = check_link_steps(cfg, fb_runner=fb_runner)
        print_fn(format_link_steps(steps))
        return 0 if all(s["ok"] for s in steps) else 1
    interactive = flags is None
    flags = flags or {}
    exists = os.path.isfile(config_path)
    if exists and not force and not interactive:
        print_fn("ملف الإعداد موجود أصلًا: %s" % config_path)
        print_fn("استخدم --force للكتابة فوقه، أو احذفه أولًا.")
        return 1
    if interactive:
        answers = prompt_answers(cfg, input_fn=input_fn,
                                 print_fn=print_fn)
    else:
        answers = dict(flags)
    if exists and not force:
        try:
            ok = input_fn("ملف الإعداد موجود — اكتب فوقه؟ (y/N): "
                          ).strip().lower()
        except (StopIteration, EOFError):
            ok = ""
        if ok not in ("y", "yes", "نعم"):
            print_fn("أُلغي — لم يُكتب أي ملف.")
            return 1
    if interactive:
        answers.update(prompt_identity(cfg, input_fn=input_fn,
                                       print_fn=print_fn))
    studio_dir = os.path.dirname(os.path.abspath(config_path))
    try:
        new_cfg = apply_answers(cfg, answers)
        logo_src = (answers.get("logo_file") or "").strip()
        if logo_src:
            dest, width, height = install_logo(logo_src, studio_dir)
            new_cfg.setdefault("identity", {})["logo_file"] = \
                LOGO_BADGE_REL
            print_fn("نُسخ الشعار (%d×%d) إلى %s"
                     % (width, height, dest))
        write_config(config_path, new_cfg)
    except (InitError, OSError) as e:
        print_fn("فشل الإعداد: %s" % e)
        return 1
    if answers.get("payment_number"):
        try:
            update_readme_payment_number(
                studio_dir, answers["payment_number"],
                print_fn=print_fn)
        except (InitError, OSError) as e:
            print_fn("تحذير: تعذر تحديث رقم الدفع في README (%s)" % e)
    crons_path = os.path.join(studio_dir, "suggested-crons.md")
    try:
        write_suggested_crons(crons_path, new_cfg)
    except OSError as e:
        print_fn("تحذير: تعذرت كتابة الكرونات المقترحة (%s)" % e)
    print_fn("كُتب ملف الإعداد: %s" % config_path)
    print_fn("كُتبت الكرونات المقترحة (لم تُثبَّت): %s" % crons_path)
    print_fn("الصفحة: %s — القناة: %s — الصوت: %s"
             % (new_cfg.get("publish", {}).get("page_id") or "فارغ",
                new_cfg.get("publish", {}).get("youtube_channel_id")
                or "فارغ",
                new_cfg.get("narration", {}).get("voice")
                or DEFAULT_VOICE))
    identity = new_cfg.get("identity") or {}
    payment = new_cfg.get("payment") or {}
    if identity.get("page_name") or payment.get("vodafone_cash"):
        print_fn("الهوية: %s — الدفع (فودافون كاش): %s"
                 % (identity.get("page_name") or "فارغ",
                    payment.get("vodafone_cash") or "فارغ"))
    print_fn("النشر اليومي: %s و%s — راجع suggested-crons.md "
             "للتثبيت حين تقرر."
             % (new_cfg.get("schedule", {}).get("morning"),
                new_cfg.get("schedule", {}).get("evening")))
    # الربط خطوة بخطوة — بعد الكتابة، لا قبلها: يتحقق من
    # الحسابات بالأرقام الجديدة ويطبع ما بقي يدويًا.
    steps = check_link_steps(new_cfg, fb_runner=fb_runner)
    print_fn(format_link_steps(steps))
    return 0
