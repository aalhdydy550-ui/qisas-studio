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

# سقوف القوائم مصدرها الوحيد lib.team_file (مالك البند 31)؛
# إعادة التصدير هنا تبقي job_registry.ROSTER_MAX_BOTS صالحة.
from lib.team_file import OTHERS_MIN_BOTS, ROSTER_MAX_BOTS

CAIRO = ZoneInfo("Africa/Cairo")

REGISTRY_FILENAME = "jobs.jsonl"
SCHEMA_VERSION = 1

JOB_KINDS = ("run", "batch", "assemble", "schedule")
JOB_STATUSES = ("running", "done", "failed", "skipped", "reused",
                "cancelled")

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
                 input_fingerprint=None, job_id=None, source=None,
                 parent_id=None):
    """سجّل مهمة جديدة بحالة running؛ ارجع سجل المهمة.

    kind: run أو batch أو assemble. story: معرّف القصة
    (رقم الطابور أو slug)؛ title: عنوانها للبحث والعرض.
    input_fingerprint: بصمة مدخلات الريندر (انظر
    lib/render_cache.py) — بلا بصمة إن لم تُحسب بعد.
    source: تسمية مصدر اختيارية بصيغة ع11
    `[From <who> · <what> · <authority>]`؛ parent_id: معرّف
    المهمة الأب إن كانت هذه المهمة مفوَّضة منها (للمقاطعة
    الشجرية — انظر interrupt_job).
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
        "source": source or "",
        "parent_id": parent_id,
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
               error=None, reused=None, input_fingerprint=None,
               source=None):
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
            if source is not None:
                target["source"] = str(source)
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
              kind=None, limit=None, source=None):
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
    if source is not None:
        jobs = [j for j in jobs if j.get("source") == source]
    jobs.sort(key=lambda j: j.get("started_at") or "")
    # عكس القائمة بعد فرز مستقر (لا sorted(reverse=True): فهو
    # يُبقي المتساوين في ترتيب الملف — الأقدم أولًا — بينما
    # مهام في الثانية نفسها يجب أن تظهر الأحدث تسجيلًا أولًا).
    jobs.reverse()
    if limit is not None:
        jobs = jobs[:limit]
    return jobs


# ============================================================
# آلة حالات التسليم + سجل الوقوعات + قواعد الرئيس
# (جولة v0.1.63 — البنود 6 و10 و12 و19 و21 و28؛ العقدان ع4 و ع11)
#
# التسليم (handoff/delivery) سجل مستقل عن مهمة التشغيل
# (jobs.jsonl): له حالة واحدة صريحة من آلة الحالات، وحقل
# مصدر إلزامي بصيغة ع11، وعدّاد تنفيذات (runs) يزيد مع كل
# دخول إلى running، وعلامة بلاغ (flagged).
# ============================================================

DELIVERY_FILENAME = "deliveries.jsonl"

# آلة حالات التسليم (ع4): source → queued → running → waiting
# → resume → completed/failed/cancelled. أي انتقال خارج
# الجدول أدناه مرفوض — بلا انتقالات صامتة.
DELIVERY_STATES = ("source", "queued", "running", "waiting",
                   "resume", "completed", "failed", "cancelled")
DELIVERY_TERMINAL_STATES = ("completed", "failed", "cancelled")
DELIVERY_TRANSITIONS = {
    "source": ("queued", "cancelled"),
    "queued": ("running", "cancelled"),
    "running": ("waiting", "completed", "failed", "cancelled"),
    "waiting": ("resume", "failed", "cancelled"),
    "resume": ("running", "completed", "failed", "cancelled"),
    "completed": (),
    "failed": (),
    "cancelled": (),
}

# حالات وقوعات الروتينات (ع4، بند 6) وكلمات السبب الثابتة.
ROUTINE_STATES = ("ran", "failed", "missed", "skipped",
                  "queued", "running")
ROUTINE_REASONS = ("previous_active", "cap_reached", "no_new_data",
                   "check_failed", "missed_window", "busy_wait",
                   "completed", "failed", "manual_skip")
ROUTINE_LEDGER_FILENAME = "routines.ledger.jsonl"

# سقوف القوائم (ع4/ع17، البندان 12 و31) — معرّفة في
# lib.team_file ومستوردة في أعلى الملف (مصدر واحد).

# حالات الانتظار (بند 19/21 — ما يرجعه wait_for_conversation)
# وحالات المهمة التي تُشتق منها.
WAIT_OUTCOMES = ("settled", "needs-user", "failed", "stalled",
                 "timed-out")
WAIT_JOB_STATES = ("completed", "idle", "needs-input", "failed",
                   "stalled", "timed-out")
_WAIT_OUTCOME_BY_JOB_STATE = {
    "completed": "settled",
    "idle": "settled",
    "needs-input": "needs-user",
    "failed": "failed",
    "stalled": "stalled",
    "timed-out": "timed-out",
}

# حالات إيقاف العمال (بند 28): pause يجمّد قابلًا للاستئناف،
# وstop نهائي لا يُستأنف.
WORKER_STATES = ("active", "paused", "stopped")
WORKERS_FILENAME = "workers.json"


def format_source(who, what, authority):
    """ابنِ تسمية مصدر بصيغة ع11.

    `[From <who> · <what> · <authority>]` — توضع على كل نص
    وارد من عامل آخر أو webhook أو بريد.
    """
    return "[From %s · %s · %s]" % (who, what, authority)


def is_valid_source_label(source):
    """هل التسمية بصيغة ع11 (تبدأ بـ [From وتحمل فاصلَي ·)؟"""
    if not isinstance(source, str) or not source.strip():
        return False
    text = source.strip()
    return (text.startswith("[From ") and text.endswith("]")
            and text.count("·") >= 2)


def _delivery_path(runs_dir):
    """مسار ملف سجل التسليمات (runs/deliveries.jsonl)."""
    base = os.path.abspath(os.path.expanduser(runs_dir))
    return os.path.join(base, DELIVERY_FILENAME)


def _locked_file(path):
    """سياق قفل ملف حصري لملف معيّن (نمط _locked نفسه).

    يرجع ملف القفل المفتوح — يُغلق ويُحرَّر عند الخروج.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock_path = path + ".lock"
    lock_f = open(lock_path, "a+", encoding="utf-8")
    fcntl.flock(lock_f, fcntl.LOCK_EX)
    return lock_f


def _read_deliveries_locked(path):
    """اقرأ كل التسليمات السليمة (يُستدعى والقفل ممسوك)."""
    deliveries = []
    if not os.path.isfile(path):
        return deliveries
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return deliveries
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and record.get("id"):
            deliveries.append(record)
    return deliveries


def _write_deliveries_locked(path, deliveries):
    """اكتب كل التسليمات ذريًا (يُستدعى والقفل ممسوك)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path),
                               prefix=".deliveries-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for record in deliveries:
                fh.write(json.dumps(record, ensure_ascii=False,
                                    default=str) + "\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _new_delivery_id():
    """معرّف تسليم فريد: handoff-YYYYMMDD-HHMMSS-xxxxxxxx."""
    return "handoff-%s-%s" % (time.strftime("%Y%m%d-%H%M%S"),
                              uuid.uuid4().hex[:8])


def register_delivery(runs_dir, source, kind=None, title=None,
                      parent_id=None, delivery_id=None):
    """سجّل تسليمًا جديدًا بحالة source؛ ارجع سجله.

    source: تسمية مصدر إلزامية بصيغة ع11 — تسليم بلا مصدر
    مرفوض (بند 10: المنسّق يرفض أي طلب موافقة بلا تسمية
    مصدر صحيحة). kind/title: وصف اختياري للتسليم.
    parent_id: معرّف التسليم الأب إن كان هذا التسليم مفوَّضًا
    منه (للمقاطعة الشجرية).
    """
    if not is_valid_source_label(source):
        raise JobRegistryError(
            "تسمية المصدر غير صالحة — يلزم صيغة ع11: "
            "[From <who> · <what> · <authority>]")
    now = now_cairo_iso()
    record = {
        "schema_version": SCHEMA_VERSION,
        "id": delivery_id or _new_delivery_id(),
        "source": source,
        "state": "source",
        "kind": kind or "",
        "title": title or "",
        "runs": 0,
        "flagged": False,
        "parent_id": parent_id,
        "wait_outcome": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    with _REGISTRY_THREAD_LOCK:
        path = _delivery_path(runs_dir)
        lock_f = _locked_file(path)
        try:
            deliveries = _read_deliveries_locked(path)
            if any(d.get("id") == record["id"] for d in deliveries):
                raise JobRegistryError(
                    "معرّف تسليم مكرر: %s" % record["id"])
            deliveries.append(record)
            _write_deliveries_locked(path, deliveries)
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            lock_f.close()
    return record


def transition_delivery(runs_dir, delivery_id, new_state,
                        error=None):
    """انقل تسليمًا إلى حالة جديدة؛ ارجع سجله أو None إن غاب.

    الانتقال غير المسموح في DELIVERY_TRANSITIONS مرفوض
    بـJobRegistryError (بلا انتقال صامت). الدخول إلى running
    يزيد عدّاد التنفيذات runs. error يُقصّ إلى 2000 حرف.
    """
    if new_state not in DELIVERY_STATES:
        raise JobRegistryError(
            "حالة التسليم غير صالحة: %s (المسموح: %s)"
            % (new_state, "/".join(DELIVERY_STATES)))
    with _REGISTRY_THREAD_LOCK:
        path = _delivery_path(runs_dir)
        lock_f = _locked_file(path)
        try:
            deliveries = _read_deliveries_locked(path)
            target = None
            for record in deliveries:
                if record.get("id") == delivery_id:
                    target = record
                    break
            if target is None:
                return None
            current = target.get("state") or "source"
            if new_state not in DELIVERY_TRANSITIONS.get(current, ()):
                raise JobRegistryError(
                    "انتقال تسليم غير مسموح: %s → %s"
                    % (current, new_state))
            if new_state == "running":
                target["runs"] = int(target.get("runs") or 0) + 1
            target["state"] = new_state
            target["updated_at"] = now_cairo_iso()
            if error is not None:
                target["error"] = str(error)[:2000]
            _write_deliveries_locked(path, deliveries)
            return dict(target)
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            lock_f.close()


def get_delivery(runs_dir, delivery_id):
    """اجلب تسليمًا بالمعرّف؛ None إن غاب."""
    path = _delivery_path(runs_dir)
    for record in _read_deliveries_locked(path):
        if record.get("id") == delivery_id:
            return record
    return None


def list_deliveries(runs_dir, state=None, source=None,
                    flagged=None, limit=None):
    """قائمة التسليمات (الأحدث أولًا).

    state: فلترة بالحالة؛ source: فلترة بتسمية المصدر (مطابقة
    تامة)؛ flagged: فلترة بالعلامة؛ limit: أقصى عدد.
    """
    if state is not None and state not in DELIVERY_STATES:
        raise JobRegistryError(
            "حالة التسليم غير صالحة: %s (المسموح: %s)"
            % (state, "/".join(DELIVERY_STATES)))
    path = _delivery_path(runs_dir)
    deliveries = _read_deliveries_locked(path)
    if state is not None:
        deliveries = [d for d in deliveries
                      if d.get("state") == state]
    if source is not None:
        deliveries = [d for d in deliveries
                      if d.get("source") == source]
    if flagged is not None:
        deliveries = [d for d in deliveries
                      if bool(d.get("flagged")) is bool(flagged)]
    deliveries.sort(key=lambda d: d.get("created_at") or "")
    deliveries.reverse()
    if limit is not None:
        deliveries = deliveries[:limit]
    return deliveries


def flag_delivery(runs_dir, delivery_id, flagged=True):
    """ضع علامة بلاغ على تسليم (أو أزلها)؛ ارجع سجله أو None."""
    with _REGISTRY_THREAD_LOCK:
        path = _delivery_path(runs_dir)
        lock_f = _locked_file(path)
        try:
            deliveries = _read_deliveries_locked(path)
            target = None
            for record in deliveries:
                if record.get("id") == delivery_id:
                    target = record
                    break
            if target is None:
                return None
            target["flagged"] = bool(flagged)
            target["updated_at"] = now_cairo_iso()
            _write_deliveries_locked(path, deliveries)
            return dict(target)
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            lock_f.close()


def set_delivery_wait_outcome(runs_dir, delivery_id, outcome):
    """سجّل نتيجة انتظار تسليم؛ ارجع سجله أو None إن غاب.

    outcome إحدى حالات الانتظار الخمس (بند 21) — قيمة غيرها
    مرفوضة.
    """
    if outcome not in WAIT_OUTCOMES:
        raise JobRegistryError(
            "نتيجة الانتظار غير صالحة: %s (المسموح: %s)"
            % (outcome, "/".join(WAIT_OUTCOMES)))
    with _REGISTRY_THREAD_LOCK:
        path = _delivery_path(runs_dir)
        lock_f = _locked_file(path)
        try:
            deliveries = _read_deliveries_locked(path)
            target = None
            for record in deliveries:
                if record.get("id") == delivery_id:
                    target = record
                    break
            if target is None:
                return None
            target["wait_outcome"] = outcome
            target["updated_at"] = now_cairo_iso()
            _write_deliveries_locked(path, deliveries)
            return dict(target)
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            lock_f.close()


def wait_outcome_for_state(job_state):
    """حوّل حالة مهمة إلى نتيجة انتظار (بند 19).

    completed/idle → settled، وneeds-input → needs-user،
    والباقي بنفس الاسم. حالة مجهولة مرفوضة.
    """
    if job_state not in _WAIT_OUTCOME_BY_JOB_STATE:
        raise JobRegistryError(
            "حالة مهمة غير صالحة للانتظار: %s (المسموح: %s)"
            % (job_state, "/".join(WAIT_JOB_STATES)))
    return _WAIT_OUTCOME_BY_JOB_STATE[job_state]


def format_deliveries(deliveries):
    """نص عربي لقائمة تسليمات (لعرض `handoffs list`)."""
    if not deliveries:
        return "لا تسليمات مسجلة بعد"
    lines = []
    for record in deliveries:
        created = str(record.get("created_at") or "؟")[:16].replace(
            "T", " ")
        line = "%s — %s — %s — تنفيذات %s" % (
            created, record.get("title") or record.get("kind") or "؟",
            record.get("state") or "؟",
            record.get("runs") or 0)
        if record.get("id"):
            line += " — %s" % record["id"]
        if record.get("flagged"):
            line += " (مُبلَّغ عنه)"
        if record.get("wait_outcome"):
            line += " — انتظار: %s" % record["wait_outcome"]
        lines.append(line)
    return "\n".join(lines)


# --- سجل وقوعات الروتينات (بند 6) ---

def routine_ledger_path(runs_dir):
    """مسار سجل وقوعات الروتينات (runs/routines.ledger.jsonl)."""
    base = os.path.abspath(os.path.expanduser(runs_dir))
    return os.path.join(base, ROUTINE_LEDGER_FILENAME)


def append_routine_ledger(runs_dir, routine, state, reason,
                          job_id=None, count=1):
    """ألحق سطر وقوع واحد بسجل الروتينات؛ ارجع السطر.

    السطر معرّفات وأوقات وعدّادات فقط — أبدًا مطالبات أو
    مخرجات (ع4). state إحدى حالات الوقوعات الست، وreason
    إحدى كلمات السبب الثابتة — غيرهما مرفوض.
    """
    if state not in ROUTINE_STATES:
        raise JobRegistryError(
            "حالة وقوع غير صالحة: %s (المسموح: %s)"
            % (state, "/".join(ROUTINE_STATES)))
    if reason not in ROUTINE_REASONS:
        raise JobRegistryError(
            "كلمة سبب غير صالحة: %s (المسموح: %s)"
            % (reason, "/".join(ROUTINE_REASONS)))
    entry = {
        "ts": now_cairo_iso(),
        "routine": routine,
        "state": state,
        "reason": reason,
        "job_id": job_id,
        "count": int(count),
    }
    with _REGISTRY_THREAD_LOCK:
        path = routine_ledger_path(runs_dir)
        lock_f = _locked_file(path)
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            lock_f.close()
    return entry


def read_routine_ledger(runs_dir, routine=None, state=None,
                        limit=200):
    """اقرأ سجل الوقوعات (الأحدث أولًا، بحد 200 سطرًا).

    سطر تالف يُتخطى ولا يُسقط السجل.
    """
    path = routine_ledger_path(runs_dir)
    entries = []
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.readlines()
        except OSError:
            lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict) and entry.get("routine"):
                entries.append(entry)
    if routine is not None:
        entries = [e for e in entries if e.get("routine") == routine]
    if state is not None:
        entries = [e for e in entries if e.get("state") == state]
    entries.reverse()
    if limit is not None:
        entries = entries[:limit]
    return entries


# --- سقوف القوائم وتوجيه الطلب الجماعي (البندان 12 و31) ---

def enforce_roster_size(total_bots):
    """ارفض قائمة فوق سقف 40 عاملًا؛ ارجع العدد إن كان مسموحًا."""
    if int(total_bots) > ROSTER_MAX_BOTS:
        raise JobRegistryError(
            "قائمة العمال فوق السقف: %s (الأقصى %s)"
            % (total_bots, ROSTER_MAX_BOTS))
    return int(total_bots)


def roster_size_ok(total_bots):
    """هل عدد العمال ضمن السقف (≤40)؟"""
    return int(total_bots) <= ROSTER_MAX_BOTS


def others_count_ok(others_count):
    """هل عدد غير الرئيس يبلغ الحد الأدنى (≥8)؟"""
    return int(others_count) >= OTHERS_MIN_BOTS


def route_group_message(target, chief="chief"):
    """وجّه طلبًا جماعيًا: `@everyone` يذهب للمنسّق وحده.

    أي هدف آخر يرجع كما هو — بلا مروحة جماعية تُغرق العمال.
    """
    if target in ("@everyone", "everyone"):
        return chief
    return target


# --- المقاطعة (بند 19): مهمة + شجرتها ---

def _descendant_ids(records, id_key, parent_key, root_id):
    """كل الأحفاد (مباشرون وغير مباشرين) لجذر عبر parent_id."""
    children = {}
    for record in records:
        parent = record.get(parent_key)
        if parent:
            children.setdefault(parent, []).append(record.get(id_key))
    found = []
    stack = list(children.get(root_id, []))
    while stack:
        current = stack.pop()
        found.append(current)
        stack.extend(children.get(current, []))
    return found


def interrupt_delivery(runs_dir, delivery_id):
    """قاطع تسليمًا وشجرته المفوَّضة: كل غير منتهٍ → cancelled.

    التسليمات المنتهية أصلًا (completed/failed/cancelled) لا
    تُمسّ. يرجع قائمة السجلات التي تغيّرت (الجذر أولًا).
    """
    with _REGISTRY_THREAD_LOCK:
        path = _delivery_path(runs_dir)
        lock_f = _locked_file(path)
        try:
            deliveries = _read_deliveries_locked(path)
            by_id = {d.get("id"): d for d in deliveries}
            if delivery_id not in by_id:
                return []
            targets = [delivery_id] + _descendant_ids(
                deliveries, "id", "parent_id", delivery_id)
            changed = []
            for target_id in targets:
                record = by_id.get(target_id)
                if record is None:
                    continue
                if record.get("state") in DELIVERY_TERMINAL_STATES:
                    continue
                record["state"] = "cancelled"
                record["updated_at"] = now_cairo_iso()
                changed.append(dict(record))
            if changed:
                _write_deliveries_locked(path, deliveries)
            return changed
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            lock_f.close()


def interrupt_job(runs_dir, job_id):
    """قاطع مهمة تشغيل وشجرتها: كل غير منتهية → cancelled.

    المهمة المنتهية (done/failed/skipped/reused/cancelled) لا
    تُمسّ. الانتهاء يختم finished_at. يرجع قائمة السجلات
    التي تغيّرت (الجذر أولًا).
    """
    _TERMINAL = ("done", "failed", "skipped", "reused", "cancelled")
    with _REGISTRY_THREAD_LOCK:
        path, lock_f = _locked(runs_dir)
        try:
            jobs = _read_all_locked(path)
            by_id = {j.get("job_id"): j for j in jobs}
            if job_id not in by_id:
                return []
            targets = [job_id] + _descendant_ids(
                jobs, "job_id", "parent_id", job_id)
            changed = []
            for target_id in targets:
                record = by_id.get(target_id)
                if record is None:
                    continue
                if record.get("status") in _TERMINAL:
                    continue
                if (record.get("status") == "running"
                        and not record.get("finished_at")):
                    record["finished_at"] = now_cairo_iso()
                record["status"] = "cancelled"
                changed.append(dict(record))
            if changed:
                _write_all_locked(path, jobs)
            return changed
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            lock_f.close()


# --- إيقاف العمال (بند 28): pause قابل للاستئناف، stop نهائي ---

def _workers_path(runs_dir):
    """مسار ملف حالات العمال (runs/workers.json)."""
    base = os.path.abspath(os.path.expanduser(runs_dir))
    return os.path.join(base, WORKERS_FILENAME)


def _read_workers_locked(path):
    """اقرأ حالات العمال (يُستدعى والقفل ممسوك)."""
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_workers_locked(path, workers):
    """اكتب حالات العمال ذريًا (يُستدعى والقفل ممسوك)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path),
                               prefix=".workers-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(workers, fh, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def set_worker_state(runs_dir, worker, state):
    """اضبط حالة عامل؛ ارجع {"worker"، "state"}.

    paused: مجمّد قابل للاستئناف؛ stopped: منتهٍ نهائيًا —
    أي انتقال من stopped مرفوض (لا استئناف بعد stop).
    """
    if state not in WORKER_STATES:
        raise JobRegistryError(
            "حالة العامل غير صالحة: %s (المسموح: %s)"
            % (state, "/".join(WORKER_STATES)))
    with _REGISTRY_THREAD_LOCK:
        path = _workers_path(runs_dir)
        lock_f = _locked_file(path)
        try:
            workers = _read_workers_locked(path)
            current = workers.get(worker, "active")
            if current == "stopped" and state != "stopped":
                raise JobRegistryError(
                    "العامل %s موقوف نهائيًا (stop) — لا يُستأنف"
                    % worker)
            workers[worker] = state
            _write_workers_locked(path, workers)
            return {"worker": worker, "state": state}
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            lock_f.close()


def pause_worker(runs_dir, worker):
    """جمّد عاملًا (قابل للاستئناف بـresume_worker)."""
    return set_worker_state(runs_dir, worker, "paused")


def resume_worker(runs_dir, worker):
    """استأنف عاملًا مجمّدًا (pause فقط — لا استئناف بعد stop)."""
    return set_worker_state(runs_dir, worker, "active")


def stop_worker(runs_dir, worker):
    """أنهِ عاملًا نهائيًا (stop — لا يُستأنف بعده)."""
    return set_worker_state(runs_dir, worker, "stopped")


def get_worker_state(runs_dir, worker):
    """حالة عامل؛ "active" إن لم يُسجَّل له شيء بعد."""
    path = _workers_path(runs_dir)
    workers = _read_workers_locked(path)
    state = workers.get(worker, "active")
    return state if state in WORKER_STATES else "active"


def list_workers(runs_dir):
    """كل حالات العمال المسجلة {worker: state}."""
    return _read_workers_locked(_workers_path(runs_dir))


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
