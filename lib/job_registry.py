#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""سجل مهام دائم — جولة v0.1.39 (مقترح MoneyPrinterTurbo:
دفعات + history — المقارنة القسم 4.1 بند 1 والقسم 6 بند 4).

ملف `runs/jobs.jsonl` (سطر JSON لكل مهمة) يسجّل كل مهمة
تشغيل (نوعها run/batch/assemble، القصة/العنوان، الحالة،
بدأت/انتهت، المخرجات، بصمة المدخلات). يكمل سجل runlog
الحالي ولا يكسره: runlog يقرأ `runs/*/run-log.json` وملفات
`analyze-*.json` كما هو، وهذا السجل ملف مستقل بجانبها.

- الكتابة ذرية (ملف مؤقت + os.replace) وتحت قفل ملف حصري
  (نمط lib/queue.py) فلا تفقد إضافتان متوازيتان إحداهما.
- سطر تالف يُتخطى عند القراءة ولا يُسقط السجل كله.
- الحالات: running / done / failed / skipped / reused
  (reused = أُعيد استخدام مخرج سابق بنفس البصمة بلا إعادة
  ريندر — انظر lib/render_cache.py).
"""
import fcntl
import json
import os
import tempfile
import threading
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

CAIRO = ZoneInfo("Africa/Cairo")

REGISTRY_FILENAME = "jobs.jsonl"
SCHEMA_VERSION = 1

JOB_KINDS = ("run", "batch", "assemble", "schedule")
JOB_STATUSES = ("running", "done", "failed", "skipped", "reused")

# قفل خيوط داخل العملية (يكمل قفل الملف بين العمليات).
_REGISTRY_THREAD_LOCK = threading.Lock()


class JobRegistryError(Exception):
    """خطأ في سجل المهام (رسالته عربية)."""


def now_cairo_iso():
    """الآن بتوقيت القاهرة بصيغة ISO."""
    return datetime.now(tz=CAIRO).isoformat(timespec="seconds")


def registry_path(runs_dir):
    """مسار ملف السجل (runs/jobs.jsonl)."""
    base = os.path.abspath(os.path.expanduser(runs_dir))
    return os.path.join(base, REGISTRY_FILENAME)


def _new_job_id():
    """معرّف مهمة فريد: job-YYYYMMDD-HHMMSS-xxxxxxxx."""
    return "job-%s-%s" % (time.strftime("%Y%m%d-%H%M%S"),
                          uuid.uuid4().hex[:8])


def _read_all_locked(path):
    """اقرأ كل السجلات السليمة (يُستدعى والقفل ممسوك).

    سطر فارغ أو JSON تالف يُتخطى بصمت — بلا إسقاط للسجل.
    """
    jobs = []
    if not os.path.isfile(path):
        return jobs
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return jobs
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and record.get("job_id"):
            jobs.append(record)
    return jobs


def _write_all_locked(path, jobs):
    """اكتب كل السجلات ذريًا (يُستدعى والقفل ممسوك)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path),
                               prefix=".jobs-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for job in jobs:
                fh.write(json.dumps(job, ensure_ascii=False,
                                    default=str) + "\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _locked(runs_dir):
    """سياق قفل ملف حصري يغطي القراءة والتعديل والكتابة.

    يرجع (مسار السجل، ملف القفل المفتوح) — يُغلق ويُحرَّر
    القفل عند الخروج. نمط lib/queue.py نفسه.
    """
    path = registry_path(runs_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock_path = path + ".lock"
    lock_f = open(lock_path, "a+", encoding="utf-8")
    fcntl.flock(lock_f, fcntl.LOCK_EX)
    return path, lock_f


def register_job(runs_dir, kind, story=None, title=None,
                 input_fingerprint=None, job_id=None):
    """سجّل مهمة جديدة بحالة running؛ ارجع سجل المهمة.

    kind: run أو batch أو assemble. story: معرّف القصة
    (رقم الطابور أو slug)؛ title: عنوانها للبحث والعرض.
    input_fingerprint: بصمة مدخلات الريندر (انظر
    lib/render_cache.py) — بلا بصمة إن لم تُحسب بعد.
    """
    if kind not in JOB_KINDS:
        raise JobRegistryError(
            "نوع المهمة غير صالح: %s (المسموح: %s)"
            % (kind, "/".join(JOB_KINDS)))
    record = {
        "schema_version": SCHEMA_VERSION,
        "job_id": job_id or _new_job_id(),
        "kind": kind,
        "story": story,
        "title": title or "",
        "status": "running",
        "started_at": now_cairo_iso(),
        "finished_at": None,
        "outputs": [],
        "input_fingerprint": input_fingerprint,
        "reused": False,
        "error": None,
    }
    with _REGISTRY_THREAD_LOCK:
        path, lock_f = _locked(runs_dir)
        try:
            jobs = _read_all_locked(path)
            if any(j.get("job_id") == record["job_id"]
                   for j in jobs):
                raise JobRegistryError(
                    "معرّف مهمة مكرر: %s" % record["job_id"])
            jobs.append(record)
            _write_all_locked(path, jobs)
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            lock_f.close()
    return record


def update_job(runs_dir, job_id, status=None, outputs=None,
               error=None, reused=None, input_fingerprint=None):
    """حدّث حالة مهمة؛ ارجع سجلها المحدَّث أو None إن غابت.

    status: إحدى الحالات الخمس؛ outputs: قائمة مسارات
    المخرجات (تستبدل القائمة السابقة)؛ error: نص الخطأ
    (يُقصّ إلى 2000 حرف)؛ reused: True تعني أُعيد استخدام
    مخرج سابق. الانتهاء يختم finished_at تلقائيًا عند أول
    انتقال من running إلى حالة نهائية.
    """
    if status is not None and status not in JOB_STATUSES:
        raise JobRegistryError(
            "حالة المهمة غير صالحة: %s (المسموح: %s)"
            % (status, "/".join(JOB_STATUSES)))
    with _REGISTRY_THREAD_LOCK:
        path, lock_f = _locked(runs_dir)
        try:
            jobs = _read_all_locked(path)
            target = None
            for job in jobs:
                if job.get("job_id") == job_id:
                    target = job
                    break
            if target is None:
                return None
            if status is not None:
                if (target.get("status") == "running"
                        and status != "running"
                        and not target.get("finished_at")):
                    target["finished_at"] = now_cairo_iso()
                target["status"] = status
            if outputs is not None:
                target["outputs"] = list(outputs)
            if error is not None:
                target["error"] = str(error)[:2000]
            if reused is not None:
                target["reused"] = bool(reused)
            if input_fingerprint is not None:
                target["input_fingerprint"] = input_fingerprint
            _write_all_locked(path, jobs)
            return dict(target)
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            lock_f.close()


def get_job(runs_dir, job_id):
    """اجلب مهمة بالمعرّف؛ None إن غابت."""
    path = registry_path(runs_dir)
    jobs = _read_all_locked(path)
    for job in jobs:
        if job.get("job_id") == job_id:
            return job
    return None


def list_jobs(runs_dir, status=None, story=None, date=None,
              kind=None, limit=None):
    """قائمة المهام (الأحدث أولًا).

    status: فلترة بالحالة؛ kind: فلترة بالنوع؛ story: فلترة
    بالقصة — يطابق رقم/عنوان القصة (مطابقة جزئية على حقلي
    story وtitle)؛ date: فلترة بتاريخ البدء YYYY-MM-DD؛
    limit: أقصى عدد (بلا حد إن غاب).
    """
    if status is not None and status not in JOB_STATUSES:
        raise JobRegistryError(
            "حالة المهمة غير صالحة: %s (المسموح: %s)"
            % (status, "/".join(JOB_STATUSES)))
    if kind is not None and kind not in JOB_KINDS:
        raise JobRegistryError(
            "نوع المهمة غير صالح: %s (المسموح: %s)"
            % (kind, "/".join(JOB_KINDS)))
    path = registry_path(runs_dir)
    jobs = _read_all_locked(path)
    if status is not None:
        jobs = [j for j in jobs if j.get("status") == status]
    if kind is not None:
        jobs = [j for j in jobs if j.get("kind") == kind]
    if story is not None:
        needle = str(story).strip()
        jobs = [j for j in jobs
                if needle in str(j.get("story") or "")
                or needle in str(j.get("title") or "")]
    if date is not None:
        jobs = [j for j in jobs
                if str(j.get("started_at") or "")[:10] == date]
    jobs.sort(key=lambda j: j.get("started_at") or "")
    # عكس القائمة بعد فرز مستقر (لا sorted(reverse=True): فهو
    # يُبقي المتساوين في ترتيب الملف — الأقدم أولًا — بينما
    # مهام في الثانية نفسها يجب أن تظهر الأحدث تسجيلًا أولًا).
    jobs.reverse()
    if limit is not None:
        jobs = jobs[:limit]
    return jobs


def format_jobs(jobs):
    """نص عربي لقائمة مهام (لعرض `jobs list` مستقبلًا)."""
    if not jobs:
        return "لا مهام مسجلة بعد — شغّل دفعة أو إنتاجًا أولًا"
    lines = []
    for job in jobs:
        started = str(job.get("started_at") or "؟")[:16].replace("T", " ")
        line = "%s — %s «%s» — %s" % (
            started, job.get("kind") or "؟",
            job.get("title") or job.get("story") or "؟",
            job.get("status") or "؟")
        if job.get("job_id"):
            # المعرّف في السطر نفسه — بدونه لا يعمل `jobs show`.
            line += " — %s" % job["job_id"]
        if job.get("reused"):
            line += " (أُعيد استخدامه)"
        outputs = job.get("outputs") or []
        if outputs:
            line += " — %s" % outputs[0]
        if job.get("error"):
            line += " (%s)" % str(job["error"])[:120]
        lines.append(line)
    return "\n".join(lines)
