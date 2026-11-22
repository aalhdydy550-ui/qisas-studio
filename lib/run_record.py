#!/usr/bin/env python3
"""سجل تشغيل — جولة v0.1.37 (مقترح tinker رقم 10).

كل تشغيل إنتاج (run/daily/batch/long-video/demo/client-run)
يكتب `runs/run-<وقت>-<أمر>.json` بإعداداته المحلولة فعليًا
(الصوت، السرعة، الموديل، الخلفية، التدرج، الرصيد...) قبل
التنفيذ، ويُحدَّث عند الانتهاء بالحالة والمخرجات والخطأ.
الهدف: عند فشل تشغيل، يُعرف بالضبط بأي إعدادات جرى — بلا
تخمين من `config.yaml` وحدها.
"""
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

CAIRO = ZoneInfo("Africa/Cairo")


def now_cairo_iso():
    """الآن بتوقيت القاهرة بصيغة ISO."""
    return datetime.now(tz=CAIRO).isoformat(timespec="seconds")


def _iso(value):
    """حوّل قيمة إلى صيغة JSON آمنة: datetime ← ISO، وغيره كما هو."""
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return value


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


def print_settings(settings):
    """اطبع الإعدادات المحلولة سطرًا سطرًا (للتشغيل التفاعلي)."""
    print("الإعدادات المحلولة:")
    for key in ("voice", "atempo", "llm_model", "llm_fallback_model",
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
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2, default=str)
    return record
