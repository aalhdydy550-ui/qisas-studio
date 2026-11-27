#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""check-back: «عُد بعد N دقيقة» — جولة v0.1.63 (بند 7).

مهام لمرة واحدة يطلبها عامل أو منسّق، محفوظة في ملف حالة
`runs/check-backs.json` (0600، كتابة ذرية تحت قفل ملف —
نمط lib/job_registry.py). الحدود: 10 لكل تشغيل/محادثة
و50 لكل عامل (المعلَّقة فقط تُحسب)؛ والحادي عشر مرفوض
بخطأ صريح لا يُسجَّل بصمت. check-back فائت يعمل مرة
واحدة متأخرًا ثم يُستهلك (`consume_due`) فلا يتكرر أبدًا.

الحالات: pending (معلَّق) / consumed (نُفِّذ مرة واحدة)
 / cancelled (أُلغي). لا حذف فعلي من الملف — الإلغاء
والاستهلاك حالتان تُحفظان للتدقيق.
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

STATE_FILENAME = "check-backs.json"
SCHEMA_VERSION = 1

# الحدود: 10 لكل تشغيل/محادثة، 50 لكل عامل (معلَّقة فقط).
MAX_PER_RUN = 10
MAX_PER_WORKER = 50

CHECK_BACK_STATUSES = ("pending", "consumed", "cancelled")

# قفل خيوط داخل العملية (يكمل قفل الملف بين العمليات).
_CHECK_BACK_THREAD_LOCK = threading.Lock()


class CheckBackError(Exception):
    """خطأ في check-back (رسالته عربية)."""


def now_cairo_iso():
    """الآن بتوقيت القاهرة بصيغة ISO."""
    return datetime.now(tz=CAIRO).isoformat(timespec="seconds")


def state_path(runs_dir):
    """مسار ملف الحالة (runs/check-backs.json)."""
    base = os.path.abspath(os.path.expanduser(runs_dir))
    return os.path.join(base, STATE_FILENAME)


def _new_check_id():
    """معرّف check-back فريد: cb-YYYYMMDD-HHMMSS-xxxxxxxx."""
    return "cb-%s-%s" % (time.strftime("%Y%m%d-%H%M%S"),
                         uuid.uuid4().hex[:8])


def _coerce_due(due):
    """وحّد موعد الاستحقاق إلى ISO بتوقيت القاهرة.

    يقبل datetime (ساذج يُفترض القاهرة) أو نص ISO. قيمة
    غير قابلة للتحليل ترفع CheckBackError صريحًا.
    """
    if isinstance(due, datetime):
        when = due if due.tzinfo is not None \
            else due.replace(tzinfo=CAIRO)
        return when.astimezone(CAIRO).isoformat(timespec="seconds")
    if isinstance(due, str) and due.strip():
        try:
            when = datetime.fromisoformat(due.strip())
        except ValueError:
            raise CheckBackError(
                "موعد check-back غير صالح: %s (مرّر ISO أو datetime)"
                % due)
        if when.tzinfo is None:
            when = when.replace(tzinfo=CAIRO)
        return when.astimezone(CAIRO).isoformat(timespec="seconds")
    raise CheckBackError(
        "موعد check-back مفقود — مرّر due بصيغة ISO أو datetime")


def _parse_due_iso(due_iso):
    """نص ISO ← datetime بتوقيت القاهرة (أو None إن تالف)."""
    try:
        when = datetime.fromisoformat(str(due_iso))
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=CAIRO)
    return when.astimezone(CAIRO)


def _read_locked(path):
    """اقرأ كل السجلات السليمة (يُستدعى والقفل ممسوك).

    ملف غائب أو JSON تالف ← حالة فارغة؛ وسجل بلا معرّف
    يُتخطى بصمت — بلا إسقاط للملف كله.
    """
    if not os.path.isfile(path):
        return {"schema_version": SCHEMA_VERSION, "check_backs": []}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {"schema_version": SCHEMA_VERSION, "check_backs": []}
    if not isinstance(data, dict) or not isinstance(
            data.get("check_backs"), list):
        return {"schema_version": SCHEMA_VERSION, "check_backs": []}
    records = [r for r in data["check_backs"]
               if isinstance(r, dict) and r.get("id")]
    return {"schema_version": SCHEMA_VERSION,
            "check_backs": records}


def _write_locked(path, state):
    """اكتب الحالة ذريًا بصلاحية 0600 (يُستدعى والقفل ممسوك)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path),
                               prefix=".check-backs-",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _locked(runs_dir):
    """سياق قفل ملف حصري يغطي القراءة والتعديل والكتابة."""
    path = state_path(runs_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock_path = path + ".lock"
    lock_f = open(lock_path, "a+", encoding="utf-8")
    fcntl.flock(lock_f, fcntl.LOCK_EX)
    return path, lock_f


def _pending_counts(records):
    """عدّادا المعلَّقة: لكل run_id ولكل worker."""
    by_run, by_worker = {}, {}
    for rec in records:
        if rec.get("status") != "pending":
            continue
        run_id = rec.get("run_id")
        worker = rec.get("worker")
        by_run[run_id] = by_run.get(run_id, 0) + 1
        by_worker[worker] = by_worker.get(worker, 0) + 1
    return by_run, by_worker


def add_check_back(runs_dir, run_id, worker, due, note=None,
                   now=None):
    """أضف check-back معلَّقًا؛ ارجع سجله.

    run_id: معرّف التشغيل/المحادثة؛ worker: اسم العامل؛
    due: موعد الاستحقاق (datetime أو نص ISO)؛ note: ملاحظة
    قصيرة اختيارية (تُقصّ إلى 500 حرف — معرّفات وأوقات
    فقط، أبدًا مطالبات أو مخرجات). تجاوز حد 10 لكل تشغيل
    أو 50 لكل عامل يرفع CheckBackError ولا يسجّل شيئًا.
    """
    run_id = (run_id or "").strip() \
        if isinstance(run_id, str) else ""
    worker = (worker or "").strip() \
        if isinstance(worker, str) else ""
    if not run_id:
        raise CheckBackError(
            "معرّف التشغيل مفقود — مرّر run_id غير فارغ")
    if not worker:
        raise CheckBackError(
            "اسم العامل مفقود — مرّر worker غير فارغ")
    due_iso = _coerce_due(due)
    note = (note or "").strip() if isinstance(note, str) else ""
    record = {
        "id": _new_check_id(),
        "run_id": run_id,
        "worker": worker,
        "due": due_iso,
        "note": note[:500],
        "status": "pending",
        "created_at": now or now_cairo_iso(),
        "consumed_at": None,
        "cancelled_at": None,
    }
    with _CHECK_BACK_THREAD_LOCK:
        path, lock_f = _locked(runs_dir)
        try:
            state = _read_locked(path)
            records = state["check_backs"]
            by_run, by_worker = _pending_counts(records)
            if by_run.get(run_id, 0) >= MAX_PER_RUN:
                raise CheckBackError(
                    "بلغ check-back حدّه لهذا التشغيل (%d لكل "
                    "تشغيل/محادثة) — ألغِ واحدًا معلَّقًا قبل "
                    "إضافة جديد" % MAX_PER_RUN)
            if by_worker.get(worker, 0) >= MAX_PER_WORKER:
                raise CheckBackError(
                    "بلغ check-back حدّه لهذا العامل (%d لكل "
                    "عامل) — ألغِ واحدًا معلَّقًا قبل إضافة "
                    "جديد" % MAX_PER_WORKER)
            records.append(record)
            _write_locked(path, state)
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            lock_f.close()
    return dict(record)


def list_check_backs(runs_dir, run_id=None, worker=None,
                     status=None):
    """قائمة check-backs (الأقدم استحقاقًا أولًا).

    فلترة اختيارية بـ run_id وworker وstatus (إحدى الحالات
    الثلاث)؛ وstatus غير صالح يرفع CheckBackError.
    """
    if status is not None and status not in CHECK_BACK_STATUSES:
        raise CheckBackError(
            "حالة check-back غير صالحة: %s (المسموح: %s)"
            % (status, "/".join(CHECK_BACK_STATUSES)))
    state = _read_locked(state_path(runs_dir))
    records = [dict(r) for r in state["check_backs"]]
    if run_id is not None:
        records = [r for r in records
                   if r.get("run_id") == run_id]
    if worker is not None:
        records = [r for r in records
                   if r.get("worker") == worker]
    if status is not None:
        records = [r for r in records
                   if r.get("status") == status]
    records.sort(key=lambda r: (r.get("due") or "",
                                r.get("created_at") or ""))
    return records


def get_check_back(runs_dir, check_id):
    """اجلب check-back بالمعرّف؛ None إن غاب."""
    for rec in list_check_backs(runs_dir):
        if rec.get("id") == check_id:
            return rec
    return None


def count_pending(runs_dir, run_id=None, worker=None):
    """عدد المعلَّقة (كلها، أو لتشغيل/عامل محدد)."""
    return len(list_check_backs(runs_dir, run_id=run_id,
                                worker=worker, status="pending"))


def cancel_check_back(runs_dir, check_id, now=None):
    """ألغِ check-back معلَّقًا؛ ارجع سجله أو None إن غاب.

    إلغاء مستهلك/ملغًى أصلًا يرجع سجله كما هو بلا تغيير.
    """
    with _CHECK_BACK_THREAD_LOCK:
        path, lock_f = _locked(runs_dir)
        try:
            state = _read_locked(path)
            target = None
            for rec in state["check_backs"]:
                if rec.get("id") == check_id:
                    target = rec
                    break
            if target is None:
                return None
            if target.get("status") == "pending":
                target["status"] = "cancelled"
                target["cancelled_at"] = now or now_cairo_iso()
                _write_locked(path, state)
            return dict(target)
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            lock_f.close()


def consume_check_back(runs_dir, check_id, now=None):
    """استهلك check-back معلَّقًا (نُفِّذ مرة واحدة).

    يرجع سجله أو None إن غاب؛ واستهلاك مستهلك/ملغًى يرجع
    سجله كما هو بلا تغيير (لا تنفيذ ثانٍ أبدًا).
    """
    with _CHECK_BACK_THREAD_LOCK:
        path, lock_f = _locked(runs_dir)
        try:
            state = _read_locked(path)
            target = None
            for rec in state["check_backs"]:
                if rec.get("id") == check_id:
                    target = rec
                    break
            if target is None:
                return None
            if target.get("status") == "pending":
                target["status"] = "consumed"
                target["consumed_at"] = now or now_cairo_iso()
                _write_locked(path, state)
            return dict(target)
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            lock_f.close()


def due_check_backs(runs_dir, now=None):
    """المعلَّقة التي حلّ موعدها (due ≤ الآن)، الأقدم أولًا."""
    if now is None:
        moment = datetime.now(tz=CAIRO)
    elif isinstance(now, datetime):
        moment = now if now.tzinfo is not None \
            else now.replace(tzinfo=CAIRO)
    else:
        moment = _parse_due_iso(now) or datetime.now(tz=CAIRO)
    due_list = []
    for rec in list_check_backs(runs_dir, status="pending"):
        when = _parse_due_iso(rec.get("due"))
        if when is not None and when <= moment:
            due_list.append(rec)
    return due_list


def consume_due(runs_dir, now=None):
    """استهلك كل الفائتة مرة واحدة متأخرة؛ ارجع قائمتها.

    كل سجل يُستهلك هنا لا يعود مستحقًا في استدعاء لاحق —
    الفائت يعمل مرة واحدة ثم يُستهلك.
    """
    due_list = due_check_backs(runs_dir, now=now)
    consumed = []
    for rec in due_list:
        done = consume_check_back(runs_dir, rec["id"], now=now)
        if done is not None:
            consumed.append(done)
    return consumed
