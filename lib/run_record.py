#!/usr/bin/env python3
"""سجل تشغيل — جولة v0.1.37 (مقترح tinker رقم 10).

كل تشغيل إنتاج (run/daily/batch/long-video/demo/client-run)
يكتب `runs/run-<وقت>-<أمر>.json` بإعداداته المحلولة فعليًا
(الصوت، السرعة، الموديل، الخلفية، التدرج، الرصيد...) قبل
التنفيذ، ويُحدَّث عند الانتهاء بالحالة والمخرجات والخطأ.
الهدف: عند فشل تشغيل، يُعرف بالضبط بأي إعدادات جرى — بلا
تخمين من `config.yaml` وحدها.

جولة v0.1.41 (بند 6 من استخراج AlphaCLI — جلسات قابلة
للاستئناف بعد الانهيار): كل سجل يحمل أيضًا حقل `checkpoint`
(آخر خطوة مكتملة + مدخلاتها ومخرجاتها) وحالة `crashed`
للتشغيلات المنقطعة (ريستارت VM يقطع الريندر). منطق الاستئناف
نفسه في `lib/run_resume.py`؛ وهنا فقط تخزين السجل ونقاط
التفتيش وكشف المنقطع.
"""
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

CAIRO = ZoneInfo("Africa/Cairo")

# خطوات خط الإنتاج بالترتيب (كما في cmd_run) — نقطة التفتيش
# هي آخر خطوة *مكتملة*؛ فـassemble بلا نقطة خاصة بها لأن
# إعادة تشغيلها من manifest.json آمنة (تكتب فوق نفس المخرج).
PIPELINE_STEPS = ("script", "produce", "assemble")


def now_cairo_iso():
    """الآن بتوقيت القاهرة بصيغة ISO."""
    return datetime.now(tz=CAIRO).isoformat(timespec="seconds")


def _iso(value):
    """حوّل قيمة إلى صيغة JSON آمنة: datetime ← ISO، وغيره كما هو."""
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return value


def current_boot_id():
    """معرّف إقلاع النظام الحالي (يتغير مع كل ريستارت VM) أو None."""
    try:
        with open("/proc/sys/kernel/random/boot_id", encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def is_process_alive(pid):
    """هل عملية بهذا الـPID ما زالت حية؟"""
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _atomic_write_json(path, record):
    """اكتب سجل JSON ذريًا (ملف مؤقت + os.replace) فلا يفسد
    السجل إن انقطع التشغيل وسط الكتابة — وهذا جوهر الاستئناف:
    نقطة التفتيش نفسها يجب أن تنجو من الانهيار الذي توثّقه."""
    tmp = "%s.tmp-%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, path)


def load_record(path):
    """اقرأ سجل تشغيل؛ None إن غاب الملف أو تلف JSON."""
    try:
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def resolve_settings(cfg, extra=None):
    """اجمع الإعدادات المحلولة فعليًا لهذا التشغيل.

    كل قيمة تُقرأ من config مع قيمتها الافتراضية في الكود —
    فالسجل يوثق ما جرى فعلًا لا ما في الملف وحده.
    ملاحظة: `veo.updated_at` يصل من PyYAML كـdatetime (لا نص)
    فيُحوَّل إلى ISO هنا — وإلا يتعطل `json.dump` في
    `begin_record` ويفشل كل تشغيل إنتاج (عُثر عليه حيًا في
    `run --demo` أثناء التحقق النهائي لـv0.1.37).
    """
    extra = extra or {}
    narration = (cfg.get("narration") or {}) if isinstance(cfg, dict) else {}
    video = (cfg.get("video") or {}) if isinstance(cfg, dict) else {}
    omniroute = (cfg.get("omniroute") or {}) if isinstance(cfg, dict) else {}
    veo = (cfg.get("veo") or {}) if isinstance(cfg, dict) else {}
    settings = {
        "voice": narration.get("voice", "piper"),
        "atempo": narration.get("atempo", 1.0),
        "llm_model": omniroute.get("model"),
        "llm_fallback_model": omniroute.get("fallback_model"),
        "llm_chain": [p.get("model") for p in
                      _chain_providers(omniroute)],
        "backend": extra.get("backend", "concat"),
        "grade": extra.get("grade"),
        "watermark": extra.get("watermark", True),
        "video_size": "%sx%s" % (video.get("width"), video.get("height")),
        "duration_min_seconds": video.get("duration_min_seconds", 40),
        "duration_max_seconds": video.get("duration_max_seconds", 60),
        "veo_balance_units": veo.get("balance_units"),
        "veo_balance_updated_at": _iso(veo.get("updated_at")),
        "story": extra.get("story"),
        "project": extra.get("project"),
    }
    return settings


def _chain_providers(omniroute):
    """سلسلة المزودين من قسم omniroute (بلا استيراد دائري —
    منطق providers_from_config مكرر هنا عمدًا بصيغة خفيفة)."""
    try:
        from lib import omniroute_client as _client
        return _client.providers_from_config(omniroute or {})
    except Exception:
        providers = []
        for key in ("model", "fallback_model"):
            value = (omniroute or {}).get(key)
            if value and value not in providers:
                providers.append({"kind": "omniroute",
                                  "model": value})
        return providers


def print_settings(settings):
    """اطبع الإعدادات المحلولة سطرًا سطرًا (للتشغيل التفاعلي)."""
    print("الإعدادات المحلولة:")
    for key in ("voice", "atempo", "llm_model", "llm_fallback_model",
                "llm_chain",
                "backend", "grade", "watermark", "video_size",
                "duration_min_seconds", "duration_max_seconds",
                "veo_balance_units"):
        value = settings.get(key)
        if value is not None:
            print("  %s: %s" % (key, value))


def begin_record(runs_dir, command, settings, run_id=None):
    """أنشئ سجل تشغيل بحالة running؛ ارجع (مسار الملف، run_id)."""
    os.makedirs(runs_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = "run-%s-%s" % (stamp, command)
    path = os.path.join(runs_dir, base + ".json")
    n = 2
    while os.path.exists(path):
        path = os.path.join(runs_dir, "%s-%d.json" % (base, n))
        n += 1
    record = {
        "run_id": run_id or base,
        "command": command,
        "status": "running",
        "started_at": now_cairo_iso(),
        "settings": settings,
        "outputs": [],
        "error": None,
        # جولة v0.1.41 (بند 6): نقطة تفتيش الاستئناف + ما يثبت
        # الانقطاع — pid وboot_id يكشفان تشغيلًا مات مع ريستارت VM.
        "checkpoint": None,
        "pid": os.getpid(),
        "boot_id": current_boot_id(),
    }
    with open(path, "w", encoding="utf-8") as fh:
        # default=str شبكة أمان أخيرة: أي قيمة غير JSON-able مستقبلًا
        # تُسلسل كنص بدل أن تُسقط تشغيل إنتاج كاملًا.
        json.dump(record, fh, ensure_ascii=False, indent=2, default=str)
    return path, record["run_id"]


def finish_record(path, status, outputs=None, error=None):
    """حدّث سجل تشغيل بالحالة النهائية (done/failed)."""
    try:
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
    except (OSError, ValueError):
        record = {"run_id": os.path.basename(path)}
    record["status"] = status
    record["finished_at"] = now_cairo_iso()
    try:
        started = datetime.fromisoformat(record.get("started_at", ""))
        record["duration_seconds"] = round(
            (datetime.now(tz=CAIRO) - started).total_seconds(), 1)
    except ValueError:
        record["duration_seconds"] = None
    if outputs:
        record["outputs"] = list(outputs)
    if error is not None:
        record["error"] = str(error)[:2000]
    _atomic_write_json(path, record)
    return record


def save_checkpoint(path, step, inputs=None, outputs=None, note=None):
    """احفظ نقطة تفتيش: آخر خطوة مكتملة + مدخلاتها ومخرجاتها.

    تُكتب ذريًا فتنجو من الانهيار نفسه. step يجب أن يكون من
    PIPELINE_STEPS. ترجع قاموس نقطة التفتيش المحفوظة.
    """
    if step not in PIPELINE_STEPS:
        raise ValueError("خطوة غير معروفة: %s (المتاح: %s)"
                         % (step, ", ".join(PIPELINE_STEPS)))
    record = load_record(path)
    if record is None:
        raise FileNotFoundError(
            "سجل التشغيل غير موجود أو تالف: %s" % path)
    idx = PIPELINE_STEPS.index(step)
    checkpoint = {
        "step": step,
        "completed": list(PIPELINE_STEPS[:idx + 1]),
        "inputs": dict(inputs or {}),
        "outputs": dict(outputs or {}),
        "note": note,
        "saved_at": now_cairo_iso(),
    }
    record["checkpoint"] = checkpoint
    record["updated_at"] = checkpoint["saved_at"]
    _atomic_write_json(path, record)
    return checkpoint


def mark_crashed(path, error=None):
    """علّم سجل تشغيل منقطع بحالة crashed (بلا مسح نقطة التفتيش).

    تُعلَّم فقط السجلات التي ما زالت running — حالة نهائية
    (done/failed/crashed) لا تُعاد كتابتها. ترجع السجل المحدَّث
    أو None إن غاب الملف أو تلف.
    """
    record = load_record(path)
    if record is None:
        return None
    if record.get("status") != "running":
        return record
    record["status"] = "crashed"
    record["finished_at"] = now_cairo_iso()
    if error is not None:
        record["error"] = str(error)[:2000]
    _atomic_write_json(path, record)
    return record


def reopen_record(path):
    """أعد فتح سجل منقطع للاستئناف: running + resumed_at + عدّاد.

    ترجع السجل المحدَّث؛ FileNotFoundError إن غاب الملف أو تلف.
    """
    record = load_record(path)
    if record is None:
        raise FileNotFoundError(
            "سجل التشغيل غير موجود أو تالف: %s" % path)
    record["status"] = "running"
    record["resumed_at"] = now_cairo_iso()
    record["resume_count"] = int(record.get("resume_count") or 0) + 1
    record["finished_at"] = None
    record["error"] = None
    _atomic_write_json(path, record)
    return record


def detect_crashed(runs_dir, force=False):
    """اكتشف التشغيلات المنقطعة وعلّمها crashed.

    سجل ما زال running مع أن عمليته مستحيلة الحياة يُعلَّم:
    boot_id مختلف عن الحالي = ريستارت VM، أو PID ميت.
    بلا force: سجل بلا boot_id ولا PID (قديم، قبل v0.1.41)
    يُترك كما هو لعدم ثبوت انقطاعه؛ مع force=True كل running
    يُعلَّم crashed (استخدام يدوي صريح فقط).
    ترجع قائمة (مسار، سجل) للتي عُلّمت.
    """
    crashed = []
    try:
        names = os.listdir(runs_dir)
    except OSError:
        return crashed
    boot = current_boot_id()
    for name in sorted(names):
        if not (name.startswith("run-") and name.endswith(".json")):
            continue
        path = os.path.join(runs_dir, name)
        record = load_record(path)
        if record is None or record.get("status") != "running":
            continue
        record_boot = record.get("boot_id")
        record_pid = record.get("pid")
        if force:
            reason = "force"
        elif record_boot and boot and record_boot != boot:
            reason = "boot-changed"
        elif record_pid and not is_process_alive(record_pid):
            reason = "process-gone"
        else:
            continue
        updated = mark_crashed(
            path, "انقطع التشغيل (%s) قبل اكتماله" % reason)
        if updated is not None:
            crashed.append((path, updated))
    return crashed
