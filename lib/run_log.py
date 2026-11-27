#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""سجل تشغيل بنيوي واحد لكل تشغيل — جولة تطبيق الأنماط (W5b).

مستوحى من نمط المراقبة في Next.js (§3-5/§3-6 من مسح next.js):
`instrumentation.ts` (تهيئة مرة واحدة عند الإقلاع) و`onRequestError`
(خطاف خطأ مركزي واحد) ومجلد `errors/` (رموز أخطاء موثّقة بروابط).
الترجمة إلى Python من الصفر بالمكتبة القياسية فقط — بلا نسخ كود،
وبلا OpenTelemetry ولا أي اعتماد جديد.

كل تشغيل (أمر `studio.py` واحد) ينشئ `RunLog` واحدًا:

  - معرّف ارتباط (correlation id) واحد يربط كل مراحل التشغيل
    وأخطائه — يظهر في السجل وفي أي رسالة فشل.
  - توقيت كل مرحلة (بداية/نهاية/مدة بالثواني).
  - معالج أخطاء مركزي واحد (`record_error`) يجمع أخطاء المراحل
    بدل `try/except` متناثرة بلا سياق — كل خطأ يُصنَّف عبر
    `lib.errors.explain_error` فيحمل فئته ورمزها الثابت ورابط
    قسم runbook.
  - عند الانتهاء يُكتب ملف JSON واحد
    `runs/run-log-<correlation-id>.json` (أو في `out_dir` الذي
    يمرّره المتصل).

الاستخدام (التوصيل في `studio.py` يطبقه المنسق — انظر تقرير
`~/workspace/studio-work/patterns-round/work/w5b-runlog.md`):

    log = RunLog("run")
    with log:                       # أو: log.start() ... log.finish()
        with log.stage("script"):
            ...                     # أي استثناء يُسجَّل ويُعاد رفعه
        with log.stage("assemble"):
            ...
    # عند الخروج يُكتب ملف JSON تلقائيًا؛ والاستثناء (إن وُجد)
    # يُسجَّل في السجل ثم يُعاد رفعه — لا يُبتلَع أبدًا.

القواعد:
- السجل إضافة لا تعديل سلوك: لا يغيّر نتيجة أي أمر ولا يخفي
  أي خطأ؛ وإن تعذّرت كتابة ملف السجل نفسه لا يرفع استثناءً
  (يُحفظ السبب في `write_error`).
- متميز عن `lib/runlog.py` (قارئ سجلات لأمر `logs`) وعن
  `lib/run_record.py` (سجل إعدادات التشغيل ونقاط التفتيش):
  هذا سجل بنيوي للمراحل والأخطاء بمعرّف ارتباط واحد.
"""
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

from lib import errors as _errors

SCHEMA_VERSION = 1

# مجلد السجلات الافتراضي — بجانب الشجرة كما في lib/run_record.py.
_DEFAULT_OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runs")

# حالات المراحل والتشغيل.
STATUS_OK = "ok"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"


def new_correlation_id():
    """معرّف ارتباط جديد: 32 حرفًا سداسيًا (uuid4) — فريد لكل تشغيل."""
    return uuid.uuid4().hex


def _now_iso(now_fn):
    """الآن بصيغة ISO-8601 (UTC) عبر دالة الوقت المحقونة (للاختبارات)."""
    value = now_fn()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat(timespec="seconds")
    return str(value)


class RunLog:
    """سجل تشغيل واحد: مراحل موقوتة + أخطاء مجمّعة + ملف JSON واحد.

    `command`: اسم الأمر (مثل "run" أو "publish") — يظهر في السجل.
    `correlation_id`: معرّف ارتباط؛ يُولَّد تلقائيًا إن لم يُمرَّر.
    `out_dir`: مجلد كتابة ملف JSON؛ None تعني مجلد `runs/` في الشجرة.
    `time_fn`: دالة أحادية (monotonic) لقياس المدد — للحقن في الاختبارات.
    `now_fn`: دالة ترجع `datetime` للطوابع الزمنية — للحقن في الاختبارات.
    `write`: False يمنع كتابة أي ملف (سجل في الذاكرة فقط).
    """

    def __init__(self, command, correlation_id=None, out_dir=None,
                 time_fn=None, now_fn=None, write=True):
        self.command = command
        self.correlation_id = correlation_id or new_correlation_id()
        self.out_dir = out_dir if out_dir is not None else _DEFAULT_OUT_DIR
        self._time_fn = time_fn or time.monotonic
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self._write = write
        self.started_at = None
        self.ended_at = None
        self._started_mono = None
        self.duration_seconds = None
        self.status = None
        self.stages = []
        self.errors = []
        self.outputs = {}
        self.write_error = None
        self.log_path = None
        self._open_stage = None
        self._finished = False
        # آخر استثناء سجّلته مرحلة عند إغلاقها — حتى لا يسجّله
        # `__exit__` مرة ثانية (تجميع بلا تكرار).
        self._last_stage_error = None

    # --- دورة الحياة ---

    def start(self):
        """ابدأ التشغيل (يُستدعى مرة واحدة؛ و`__enter__` يستدعيه)."""
        if self.started_at is not None:
            return self
        self.started_at = _now_iso(self._now_fn)
        self._started_mono = self._time_fn()
        return self

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        if exc is not None:
            # سجّل الخطأ في المرحلة المفتوحة (إن وُجدت) ثم في التشغيل،
            # وأغلق المرحلة كفاشلة — ثم أعد رفع الاستثناء (لا ابتلاع).
            # إن سجّلت المرحلة الاستثناء نفسه أصلًا (عبر stage())
            # فلا يُسجَّل مرة ثانية.
            if self._open_stage is not None:
                self._close_stage(self._open_stage, STATUS_FAILED,
                                  error=exc)
            if exc is not self._last_stage_error:
                self.record_error(exc)
            self.finish(STATUS_FAILED)
        else:
            self.finish()
        return False

    # --- المراحل ---

    def start_stage(self, name):
        """افتح مرحلة موقوتة بالاسم. مرحلة واحدة مفتوحة في المرة."""
        if self.started_at is None:
            self.start()
        if self._open_stage is not None:
            raise RuntimeError(
                "مرحلة مفتوحة أصلًا: %s — أغلقها قبل فتح %s"
                % (self._open_stage["name"], name))
        stage = {"name": name, "status": None,
                 "started_at": _now_iso(self._now_fn),
                 "ended_at": None, "duration_seconds": None,
                 "detail": "", "error": None}
        stage["_mono_start"] = self._time_fn()
        self.stages.append(stage)
        self._open_stage = stage
        return stage

    def end_stage(self, name, status=STATUS_OK, detail="", error=None):
        """أغلق مرحلة مفتوحة بالاسم مع حالتها النهائية."""
        stage = self._open_stage
        if stage is None or stage["name"] != name:
            raise RuntimeError(
                "لا توجد مرحلة مفتوحة باسم %s" % name)
        if error is not None:
            status = STATUS_FAILED
        self._close_stage(stage, status, detail=detail, error=error)
        return stage

    def _close_stage(self, stage, status, detail="", error=None):
        stage["status"] = status
        stage["ended_at"] = _now_iso(self._now_fn)
        stage["duration_seconds"] = round(
            self._time_fn() - stage.pop("_mono_start"), 3)
        if detail:
            stage["detail"] = detail
        if error is not None:
            self._last_stage_error = error
            stage["error"] = self.record_error(
                error, stage=stage["name"])
        self._open_stage = None

    def stage(self, name):
        """سياق مرحلة: `with log.stage("script"): ...`.

        الاستثناء داخل المرحلة يُسجَّل في السجل المركزي (برمزه
        ورابط runbook) وتُغلق المرحلة كفاشلة، ثم يُعاد رفعه.
        """
        return _StageContext(self, name)

    # --- معالج الأخطاء المركزي ---

    def record_error(self, exc_or_text, stage=None, context=None):
        """سجّل خطأً واحدًا مركزيًا وارجع قاموسه المفسَّر.

        يصنّف الخطأ عبر `lib.errors.explain_error` فيحمل: الفئة
        العربية، والرمز الثابت (مثل STUDIO-FFMPEG-001)، ورابط قسم
        runbook، والنص الأصلي مقصوصًا. لا يرفع استثناءً أبدًا.
        """
        try:
            explained = _errors.explain_error(exc_or_text, context)
        except Exception:
            explained = {"category": "unknown",
                         "title": "خطأ غير معروف",
                         "code": _errors.error_code("unknown"),
                         "runbook": _errors.runbook_link("unknown"),
                         "original": ""}
        entry = {
            "code": explained.get("code")
                    or _errors.error_code(explained.get("category",
                                                        "unknown")),
            "runbook": explained.get("runbook")
                       or _errors.runbook_link(
                           explained.get("category", "unknown")),
            "category": explained.get("category", "unknown"),
            "title": explained.get("title", ""),
            "stage": stage or (self._open_stage["name"]
                               if self._open_stage else None),
            "at": _now_iso(self._now_fn),
            "original": _errors.clip_output(
                explained.get("original") or ""),
        }
        self.errors.append(entry)
        return entry

    # --- الإنهاء والكتابة ---

    @property
    def has_errors(self):
        return bool(self.errors)

    @property
    def error_count(self):
        return len(self.errors)

    @property
    def first_error(self):
        return self.errors[0] if self.errors else None

    def failed_stages(self):
        """أسماء المراحل الفاشلة بالترتيب."""
        return [s["name"] for s in self.stages
                if s.get("status") == STATUS_FAILED]

    def finish(self, status=None, output=None):
        """أنهِ التشغيل واكتب ملف JSON (مرة واحدة فقط).

        الحالة تُستنتج تلقائيًا: failed إن وُجد خطأ مسجَّل أو
        مرحلة فاشلة، وإلا ok — ما لم تُمرَّر حالة صريحة.
        `output`: مخرجات التشغيل (مثل مسار الفيديو) تُحفظ في السجل.
        """
        if self._finished:
            return self
        self._finished = True
        if self._open_stage is not None:
            self._close_stage(self._open_stage, STATUS_FAILED)
        if self.started_at is None:
            self.start()
        self.ended_at = _now_iso(self._now_fn)
        self.duration_seconds = round(
            self._time_fn() - self._started_mono, 3)
        if output is not None:
            if isinstance(output, dict):
                self.outputs.update(output)
            else:
                self.outputs["result"] = output
        if status is None:
            status = (STATUS_FAILED if (self.errors
                                        or self.failed_stages())
                      else STATUS_OK)
        self.status = status
        if self._write:
            self._write_file()
        return self

    def _write_file(self):
        try:
            os.makedirs(self.out_dir, exist_ok=True)
            path = os.path.join(
                self.out_dir,
                "run-log-%s.json" % self.correlation_id)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(tmp, path)
            self.log_path = path
        except OSError as e:
            self.write_error = str(e)

    def to_dict(self):
        """السجل كاملًا كقاموس JSON-آمن."""
        stages = []
        for s in self.stages:
            stages.append({k: v for k, v in s.items()
                           if not k.startswith("_")})
        return {
            "schema_version": SCHEMA_VERSION,
            "correlation_id": self.correlation_id,
            "command": self.command,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "stages": stages,
            "errors": list(self.errors),
            "error_count": len(self.errors),
            "outputs": dict(self.outputs),
            "log_path": self.log_path,
            "write_error": self.write_error,
        }

    def format_summary(self):
        """سطر عربي واحد يلخّص التشغيل (للطرفية/سجلات cron)."""
        status = {"ok": "ناجح", "failed": "فشل",
                  "skipped": "تخطّى"}.get(self.status or "", self.status)
        parts = ["تشغيل %s (%s): %s" % (self.command,
                                        self.correlation_id[:8], status)]
        if self.duration_seconds is not None:
            parts.append("المدة %.1fث" % self.duration_seconds)
        failed = self.failed_stages()
        if failed:
            parts.append("مراحل فاشلة: %s" % "، ".join(failed))
        if self.first_error:
            parts.append("أول خطأ: %s (%s) — %s"
                         % (self.first_error["code"],
                            self.first_error["title"],
                            self.first_error["runbook"]))
        return " — ".join(parts)


class _StageContext:
    """سياق `with log.stage(name)` — داخلي لـ RunLog."""

    def __init__(self, log, name):
        self._log = log
        self._name = name

    def __enter__(self):
        return self._log.start_stage(self._name)

    def __exit__(self, exc_type, exc, tb):
        if exc is not None:
            self._log.end_stage(self._name, error=exc)
        else:
            self._log.end_stage(self._name)
        return False


def start_run(command, **kwargs):
    """اختصار: أنشئ RunLog وابدأه فورًا."""
    return RunLog(command, **kwargs).start()


# ============================================================
# قراءة محدودة + احتفاظ (جولة v0.1.63 — بند 30)
#
# حدود الصفحات: 200 رسالة للقراءة، 100 نتيجة للبحث — فلا
# تُقرأ سجلات ضخمة كاملة في الذاكرة. والاحتفاظ: سجلات
# القرار/الموافقة الأقدم من 180 يومًا تُحذف.
# ============================================================

READ_LIMIT = 200
SEARCH_LIMIT = 100
RETENTION_DAYS = 180
CLIP_LIMIT = 1000


def clip_text(text, limit=CLIP_LIMIT):
    """قصّ نصًا عند الحد؛ ارجع (النص، هل قُصّ؟)."""
    text = str(text)
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def _check_limit(limit, default, cap):
    """تحقق من حد؛ ارجع الحد الفعلي مقصوصًا عند السقف."""
    if limit is None:
        return default
    if not isinstance(limit, int) or isinstance(limit, bool) \
            or limit < 1:
        raise ValueError("حد القراءة غير صالح: %r" % (limit,))
    return min(limit, cap)


def _load_run_log_file(path):
    """اقرأ ملف run-log-*.json واحدًا؛ None إن تالف أو غير قاموس."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _run_log_summary(data):
    """ملخص سجل تشغيل: معرّفات وحالة ومدد فقط — بلا نصوص طويلة."""
    first = data.get("errors") or []
    first_error = first[0] if first else None
    summary = {
        "correlation_id": data.get("correlation_id") or "",
        "command": data.get("command") or "",
        "status": data.get("status") or "",
        "started_at": data.get("started_at") or "",
        "duration_seconds": data.get("duration_seconds"),
        "error_count": len(first),
    }
    if isinstance(first_error, dict):
        original, clipped = clip_text(
            str(first_error.get("original") or ""))
        summary["first_error"] = {
            "code": first_error.get("code") or "",
            "title": first_error.get("title") or "",
            "original": original,
            "clipped": clipped,
        }
    return summary


def list_run_logs(out_dir=None, limit=READ_LIMIT):
    """اقرأ ملخصات سجلات التشغيل (الأحدث أولًا، بحد 200).

    ملف JSON تالف يُتخطى ولا يُسقط القائمة.
    """
    limit = _check_limit(limit, READ_LIMIT, READ_LIMIT)
    out_dir = out_dir if out_dir is not None else _DEFAULT_OUT_DIR
    summaries = []
    if not os.path.isdir(out_dir):
        return summaries
    for name in sorted(os.listdir(out_dir)):
        if not (name.startswith("run-log-")
                and name.endswith(".json")):
            continue
        data = _load_run_log_file(os.path.join(out_dir, name))
        if data is not None:
            summaries.append(_run_log_summary(data))
    summaries.sort(key=lambda s: s.get("started_at") or "",
                   reverse=True)
    return summaries[:limit]


def search_run_logs(out_dir=None, query="", limit=SEARCH_LIMIT):
    """ابحث في سجلات التشغيل: أول 100 مطابقة (الأحدث أولًا).

    المطابقة جزئية بلا حساسية لحالة الأحرف على الأمر ومعرّف
    الارتباط ورمز/عنوان أول خطأ.
    """
    limit = _check_limit(limit, SEARCH_LIMIT, SEARCH_LIMIT)
    needle = str(query or "").casefold()
    if not needle:
        raise ValueError("عبارة البحث فارغة")
    matches = []
    for summary in list_run_logs(out_dir, limit=READ_LIMIT):
        haystack = " ".join([
            str(summary.get("command") or ""),
            str(summary.get("correlation_id") or ""),
            str(summary.get("status") or ""),
            str((summary.get("first_error") or {}).get("code") or ""),
            str((summary.get("first_error") or {}).get("title") or ""),
        ]).casefold()
        if needle in haystack:
            matches.append(summary)
            if len(matches) >= limit:
                break
    return matches


def _parse_ts(value):
    """فسّر طابعًا زمنيًا (ISO أو epoch) إلى datetime واعٍ؛ None إن تعذّر."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(
                text[:-1] + "+00:00" if text.endswith("Z")
                else text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def _prune_ndjson_file(path, cutoff):
    """احذف من ملف JSONL السطور الأقدم من cutoff؛ ارجع (محذوف، باقٍ).

    سطر بلا طابع زمني مفسَّر يُبقى (لا نحذف ما لا نستطيع
    تأريخه). ملف يفرغ تمامًا يُحذف ويرجع محذوفًا في القائمة
    عبر القيمة الثانية الخاصة: (n, -1) تعني حُذف الملف.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return 0, 0
    kept = []
    deleted = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except ValueError:
            kept.append(line)
            continue
        ts = None
        if isinstance(record, dict):
            for key in ("ts", "at", "time", "timestamp",
                        "created_at"):
                ts = _parse_ts(record.get(key))
                if ts is not None:
                    break
        if ts is not None and ts < cutoff:
            deleted += 1
        else:
            kept.append(line)
    if not kept:
        try:
            os.unlink(path)
        except OSError:
            pass
        return deleted, -1
    if deleted:
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.writelines(kept)
            os.replace(tmp, path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            return 0, len(kept)
    return deleted, len(kept)


def prune_old_logs(out_dir=None, days=RETENTION_DAYS, now=None):
    """احذف ملفات run-log-*.json الأقدم من `days` يومًا.

    القدم بزمن التعديل (أو started_at داخل الملف إن فُسّر).
    يرجع قائمة مسارات المحذوفة.
    """
    out_dir = out_dir if out_dir is not None else _DEFAULT_OUT_DIR
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    cutoff = moment - timedelta(days=days)
    deleted = []
    if not os.path.isdir(out_dir):
        return deleted
    for name in sorted(os.listdir(out_dir)):
        if not (name.startswith("run-log-")
                and name.endswith(".json")):
            continue
        path = os.path.join(out_dir, name)
        try:
            mtime = datetime.fromtimestamp(os.stat(path).st_mtime,
                                           tz=timezone.utc)
        except OSError:
            continue
        stamp = mtime
        data = _load_run_log_file(path)
        if data is not None:
            parsed = _parse_ts(data.get("started_at"))
            if parsed is not None:
                stamp = parsed
        if stamp < cutoff:
            try:
                os.unlink(path)
                deleted.append(path)
            except OSError:
                continue
    return deleted


def prune_decision_logs(runs_dir, days=RETENTION_DAYS, now=None):
    """احذف سجلات القرار/الموافقة الأقدم من `days` يومًا (180).

    يغطي `runs/decider-log/*.ndjson` (سجلات الموجّه — ع8)
    و`runs/approval-decisions.jsonl` (سجل قرارات الموافقة —
    ع3): السطور القديمة تُحذف سطرًا سطرًا بطابعها الزمني،
    والملف الذي يفرغ يُحذف. يرجع {"deleted": [ملفات حُذفت]،
    "pruned": {مسار: سطور محذوفة}، "kept": سطور باقية}.
    """
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    cutoff = moment - timedelta(days=days)
    result = {"deleted": [], "pruned": {}, "kept": 0}
    targets = []
    decider_dir = os.path.join(runs_dir, "decider-log")
    if os.path.isdir(decider_dir):
        for name in sorted(os.listdir(decider_dir)):
            if name.endswith(".ndjson"):
                targets.append(os.path.join(decider_dir, name))
    approval = os.path.join(runs_dir, "approval-decisions.jsonl")
    if os.path.isfile(approval):
        targets.append(approval)
    for path in targets:
        deleted, kept = _prune_ndjson_file(path, cutoff)
        if kept == -1:
            result["deleted"].append(path)
        else:
            result["kept"] += kept
        if deleted:
            result["pruned"][path] = deleted
    return result
