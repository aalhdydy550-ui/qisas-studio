#!/usr/bin/env python3
"""معالج الإعداد — `studio.py init`: إعداد أول مرة بالعربية.

يسأل عن: معرّف صفحة فيسبوك، ومعرّف قناة يوتيوب، وصوت
الراوي (Piper رجل افتراضيًا)، وموعدي النشر اليومي، وملف
طابور القصص — ويكتبها في config.yaml. يعرض أيضًا ملف
الكرونات المقترحة (نشر يومي + فيديو طويل أسبوعي) دون
تثبيتها صامتًا: التثبيت قرار المستخدم وحده.

يعمل بلا تفاعل عبر الأعلام (--page-id وغيرها) لزوم
الاختبارات؛ ولا يكتب فوق config.yaml موجود إلا بعد تأكيد
صريح (--force أو إجابة y في الوضع التفاعلي).
"""
import copy
import os
import re
import tempfile

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DEFAULT_MORNING = "09:00"
DEFAULT_EVENING = "19:00"
DEFAULT_VOICE = "piper"
VOICES = ("piper", "gtts")

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


def run_wizard(cfg, config_path, flags=None, force=False,
               input_fn=input, print_fn=print):
    """نفّذ المعالج كاملًا. يرجع 0 عند النجاح و1 عند الرفض/الخطأ.

    flags: إجابات من الأعلام (بلا تفاعل)؛ وإن كانت None يُسأل
    المستخدم تفاعليًا. force: اكتب فوق ملف موجود بلا سؤال.
    """
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
        ok = input_fn("ملف الإعداد موجود — اكتب فوقه؟ (y/N): "
                      ).strip().lower()
        if ok not in ("y", "yes", "نعم"):
            print_fn("أُلغي — لم يُكتب أي ملف.")
            return 1
    try:
        new_cfg = apply_answers(cfg, answers)
        write_config(config_path, new_cfg)
    except (InitError, OSError) as e:
        print_fn("فشل الإعداد: %s" % e)
        return 1
    crons_path = os.path.join(os.path.dirname(
        os.path.abspath(config_path)), "suggested-crons.md")
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
    print_fn("النشر اليومي: %s و%s — راجع suggested-crons.md "
             "للتثبيت حين تقرر."
             % (new_cfg.get("schedule", {}).get("morning"),
                new_cfg.get("schedule", {}).get("evening")))
    return 0
