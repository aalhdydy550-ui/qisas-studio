#!/usr/bin/env python3
"""سجل التشغيلات — `studio.py logs` (قراءة فقط من runs/).

يجمع نوعين: مجلدات الإنتاج `<slug>-<ts>/run-log.json` (حالته من
خطواته: أي خطوة فاشلة تعني فشل التشغيل كله، مع أول خطأ) وملفات
`analyze-*.json` (تحليل أداء آخر فيديو). ملف JSON تالف يُتخطى
ولا يُسقط القائمة كلها. الترتيب الأحدث أولًا، واليوم افتراضيًا.
"""
import datetime
import glob
import json
import os

_OK_STATUSES = ("ok", "passed", "done", "success")

# حالات سجلات التشغيل run-*.json (جولة v0.1.41 — بند 6):
# crashed هي حالة التشغيل المنقطع (ريستارت VM) القابل للاستئناف.
_RECORD_STATUSES = {"running": "جارٍ", "crashed": "تعطّل",
                    "done": "ناجح", "failed": "فشل"}


def _parse_run_record(path):
    """سجل تشغيل run-*.json: حالته + آخر نقطة تفتيش إن تعطّل."""
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if not isinstance(d, dict):
        return None
    status = _RECORD_STATUSES.get(d.get("status"), d.get("status") or "؟")
    settings = d.get("settings") or {}
    title = (settings.get("story") or d.get("command")
             or d.get("run_id") or "؟")
    detail = ""
    checkpoint = d.get("checkpoint") or {}
    if d.get("status") == "crashed" and checkpoint.get("step"):
        detail = ("آخر نقطة: %s — استأنف بـ run --resume %s"
                  % (checkpoint["step"], d.get("run_id") or "؟"))
    elif d.get("error"):
        detail = str(d.get("error"))[:120]
    started = d.get("started_at") or ""
    return {"date": (started[:16].replace("T", " ") if started else "؟"),
            "date_key": started[:10] if started else "",
            "kind": "تشغيل",
            "title": title,
            "status": status, "detail": detail,
            "run_id": d.get("run_id") or ""}


def _status_from_steps(steps):
    if not isinstance(steps, dict) or not steps:
        return None
    for s in steps.values():
        if isinstance(s, dict) and s.get("status") not in _OK_STATUSES:
            return "فشل"
    return "ناجح"


def _first_error(steps):
    for name, s in (steps or {}).items():
        if isinstance(s, dict) and s.get("status") not in _OK_STATUSES:
            err = (s.get("error") or "").strip().splitlines()
            return name, (err[0][:120] if err else "")
    return None, None


def _parse_run_log(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if not isinstance(d, dict):
        return None
    started = d.get("started") or ""
    status = d.get("status")
    if isinstance(status, str):
        status = {"ok": "ناجح", "failed": "فشل",
                  "error": "فشل"}.get(status.lower(), status)
    else:
        status = None
    if status is None:
        status = _status_from_steps(d.get("steps")) or "؟"
    step, err = _first_error(d.get("steps"))
    detail = ""
    if status == "فشل":
        if step:
            detail = "خطوة %s: %s" % (step, err)
        elif d.get("error"):
            detail = str(d.get("error"))[:120]
    elif d.get("cost_usd") is not None:
        detail = "تكلفة $%s" % d.get("cost_usd")
    return {"date": (started[:16].replace("T", " ") if started else "؟"),
            "date_key": started[:10] if started else "",
            "kind": "إنتاج",
            "title": d.get("story") or d.get("run") or "؟",
            "status": status, "detail": detail}


def _parse_analyze(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if not isinstance(d, dict):
        return None
    date = d.get("date") or ""
    fb = d.get("facebook") or {}
    yt = d.get("youtube") or {}
    parts = []
    if isinstance(fb, dict) and fb.get("views") is not None:
        parts.append("فيسبوك %s مشاهدة" % fb["views"])
    if isinstance(yt, dict) and yt.get("views") is not None:
        parts.append("يوتيوب %s مشاهدة" % yt["views"])
    caption = (fb.get("caption") or "")[:40] if isinstance(fb, dict) else ""
    return {"date": date[:16] if date else "؟",
            "date_key": date[:10] if date else "",
            "kind": "تحليل",
            "title": caption or "آخر فيديو",
            "status": "ناجح" if (fb or yt) else "؟",
            "detail": " / ".join(parts)}


def collect_runs(runs_dir, today_only=False, limit=20, today=None):
    """اجمع التشغيلات (الأحدث أولًا). today_only يقصرها على اليوم."""
    entries = []
    for path in glob.glob(os.path.join(runs_dir, "*", "run-log.json")):
        try:
            e = _parse_run_log(path)
        except (ValueError, OSError):
            continue
        if e:
            entries.append(e)
    for path in glob.glob(os.path.join(runs_dir, "run-*.json")):
        try:
            e = _parse_run_record(path)
        except (ValueError, OSError):
            continue
        if e:
            entries.append(e)
    for path in glob.glob(os.path.join(runs_dir, "analyze-*.json")):
        try:
            e = _parse_analyze(path)
        except (ValueError, OSError):
            continue
        if e:
            entries.append(e)
    entries.sort(key=lambda e: e["date"], reverse=True)
    if today_only:
        day = (today or datetime.date.today()).isoformat()
        entries = [e for e in entries if e["date_key"] == day]
    return entries[:limit] if limit else entries


def format_runs(entries):
    """نص عربي لقائمة التشغيلات."""
    if not entries:
        return ("لا تشغيلات مسجلة في runs/ لهذا اليوم — "
                "جرّب `studio.py logs --all` لعرض كل الأيام")
    lines = []
    for e in entries:
        line = "%s — %s «%s» — %s" % (e["date"], e["kind"],
                                      e["title"], e["status"])
        if e["detail"]:
            line += " (%s)" % e["detail"]
        lines.append(line)
    return "\n".join(lines)
