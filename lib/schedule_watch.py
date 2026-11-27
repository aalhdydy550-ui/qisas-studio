#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""مراقبة المنشور المجدول — `studio.py schedule --watch`.

يغلق ثغرة كروني النشر (qisas-morning-publish /
qisas-evening-publish): الكرونان يتخطّيان كل شيء عندما تكون
الخانة مجدولة/منشورة أصلًا، فلا يحدث التعليق الأول أبدًا على
المنشورات المجدولة مسبقًا. هذا الملف منطق نقي بدوال قابلة
للحقن — لا يستورد facebook_cli ولا يعمل أي شبكة بنفسه:
القراءة والنشر الحقيقيان يأتيان كدالتين محقونتين (read_fn /
comment_fn) يبنيهما المنسّق في studio.py من
`publish.find_facebook_bin` وأنماط lib/publish.py.

صيغة التعليق الأول المعتمدة (العبرة + سؤال محيّر + موعد
الجزء التالي) تُعاد هنا باستخدام الدعوة اللطيفة المعتمدة
`caption_check.approved_invite` — بلا صياغة مخالفة:
الدعوة «الجزء الثاني بكرة 7 مساءً — اعمل متابعة عشان يوصلك
أول ما ينزل» لأن الجزء سينشر في وقته سواء تابع القارئ أم لا.

قواعد صادقة: لا يُخترع أي رقم أو حالة — أي حالة لا تُعرف
تُطبع «غير معروفة»؛ والتعليق الفاشل يُعاد مرة واحدة فقط.

دلالات المهام المجدولة (جولة v0.1.41 — بند 3 من استخراج
AlphaCLI، REPORT-AR.md §4.1): كل occurrence تُسجَّل في سجل
المهام **قبل** بدئها (حقل started_at يُكتب قبل أي قراءة أو
تعليق) — فإعادة تشغيل الـVM بعد البدء تُتخطى لا تُكرر؛ وبعد
توقف تُلحق occurrence متأخرة واحدة فقط ثم يستأنف الفاصل
الأصلي؛ والإيقاف/الإلغاء للمستقبل فقط.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import fcntl
import json
import os
import threading

from lib import caption_check

CAIRO = ZoneInfo("Africa/Cairo")

SLOTS = ("morning", "evening")
# موعد الخانة القانوني بتوقيت القاهرة — هوية الـoccurrence:
# خانة واحدة لكل موعد في اليوم (صباحًا 09:00 / مساءً 19:00).
SLOT_TIMES = {"morning": "09:00", "evening": "19:00"}
UNKNOWN = "غير معروفة"


def occurrence_key(post_id, slot, due):
    """مفتاح occurrence حتمي: خانة + منشور + موعدها القانوني."""
    return "schedule-watch:%s:%s:%s" % (slot, post_id, due)


def default_due(slot):
    """موعد الخانة القانوني اليوم بتوقيت القاهرة."""
    now = datetime.now(tz=CAIRO)
    return "%sT%s" % (now.date().isoformat(), SLOT_TIMES[slot])


def catch_up_plan(missed_due, next_due=None):
    """خطة اللحاق بعد توقف: occurrence متأخرة واحدة فقط تلحق،
    والباقي يُتخطى، والفاصل الأصلي يستأنف بلا إزاحة
    (next_due يمر كما هو — لا يُعاد حسابه من وقت اللحاق).

    missed_due: قائمة مواعيد متأخرة مرتبة (الأقدم أولًا).
    ترجع {run, skipped, next_due}.
    """
    missed = list(missed_due or [])
    return {"run": missed[0] if missed else None,
            "skipped": missed[1:],
            "next_due": next_due}


def cancel_future(occurrences, cutoff):
    """إيقاف/إلغاء للمستقبل فقط: ما موعده قبل cutoff يبقى كما
    هو (بدأ أو اكتمل فلا يُمس)، وما موعده cutoff أو بعده
    يُلغى. ترجع {kept, cancelled}."""
    kept, cancelled = [], []
    for occ in (occurrences or []):
        due = str((occ or {}).get("due") or "")
        if due >= str(cutoff):
            cancelled.append(occ)
        else:
            kept.append(occ)
    return {"kept": kept, "cancelled": cancelled}


# ─── سجل وقوعات الروتينات وقواعد موثوقيتها (جولة v0.1.63) ───
# البنود 6 (جزء السجل) و20 و38 و27 — عقدا ع4 وع5 من خطة
# الجولة. كل وقوع روتين يترك سطرًا واحدًا في
# runs/routines.ledger.jsonl: {"ts", "routine", "state",
# "reason", "job_id", "count"} — معرّفات وأوقات وعدّادات
# فقط، أبدًا مطالبات أو مخرجات.
ROUTINE_STATES = ("ran", "failed", "missed", "skipped",
                  "queued", "running")
ROUTINE_REASONS = ("previous_active", "cap_reached",
                   "no_new_data", "check_failed", "missed_window",
                   "busy_wait", "completed", "failed",
                   "manual_skip")
LEDGER_FILENAME = "routines.ledger.jsonl"
AI_TURNS_FILENAME = "routine-ai-turns.jsonl"

# خنق جولات الذكاء: 24 جولة كحد أقصى في أي 24 ساعة.
AI_TURNS_MAX_PER_24H = 24
AI_TURNS_WINDOW_SECONDS = 24 * 3600
# نافذة اللحاق بالفائت: الأحدث خلال 12 ساعة يعمل متأخرًا.
CATCH_UP_WINDOW_SECONDS = 12 * 3600
# تأخير الإقلاع: أول الفحوص تنتظر دقيقتين بعد البدء.
BOOT_DELAY_SECONDS = 120

# قفل خيوط داخل العملية (يكمل قفل الملف بين العمليات).
_LEDGER_THREAD_LOCK = threading.Lock()


def now_cairo_iso():
    """الآن بتوقيت القاهرة بصيغة ISO."""
    return datetime.now(tz=CAIRO).isoformat(timespec="seconds")


def _parse_when(value):
    """نص ISO أو datetime ← datetime بتوقيت القاهرة، أو None.

    نص ساذج (بلا منطقة) يُفترض القاهرة؛ وقيمة غير قابلة
    للتحليل ترجع None — بلا اختراع وقت.
    """
    if isinstance(value, datetime):
        when = value
    elif isinstance(value, str) and value.strip():
        try:
            when = datetime.fromisoformat(value.strip())
        except ValueError:
            return None
    else:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=CAIRO)
    return when.astimezone(CAIRO)


def _coerce_now(now):
    """وحّد now (datetime/نص ISO/بلا قيمة) إلى datetime القاهرة."""
    parsed = _parse_when(now) if now is not None else None
    return parsed or datetime.now(tz=CAIRO)


def ledger_path(runs_dir):
    """مسار سجل الوقوعات (runs/routines.ledger.jsonl)."""
    base = os.path.abspath(os.path.expanduser(runs_dir))
    return os.path.join(base, LEDGER_FILENAME)


def append_ledger(runs_dir, routine, state, reason, job_id=None,
                  count=1, ts=None):
    """ألحق سطر وقوع واحد بالسجل؛ ارجع السطر.

    state إحدى حالات ع4 الست؛ وreason إحدى كلمات السبب
    الثابتة التسع — أي قيمة خارجها ترفع ValueError (لا
    سطر بسبب حر). reason=None مسموح لسطر بدءٍ (running)
    بلا نتيجة بعد — النتيجة سطر لاحق بسببه الثابت.
    count عدّاد الوقوعات المنهارة في هذا السطر (1 للوقوع
    الواحد، وN لصف Missed المنهار).
    """
    routine = (routine or "").strip() \
        if isinstance(routine, str) else ""
    if not routine:
        raise ValueError("اسم الروتين مفقود — مرّر routine غير فارغ")
    if state not in ROUTINE_STATES:
        raise ValueError(
            "حالة وقوع غير صالحة: %s (المسموح: %s)"
            % (state, "/".join(ROUTINE_STATES)))
    if reason is not None and reason not in ROUTINE_REASONS:
        raise ValueError(
            "سبب وقوع غير صالح: %s (المسموح: %s)"
            % (reason, "/".join(ROUTINE_REASONS)))
    count = int(count)
    if count < 0:
        raise ValueError("عدّاد الوقوعات لا يكون سالبًا")
    line = {"ts": ts or now_cairo_iso(),
            "routine": routine,
            "state": state,
            "reason": reason,
            "job_id": job_id,
            "count": count}
    path = ledger_path(runs_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock_path = path + ".lock"
    with _LEDGER_THREAD_LOCK:
        lock_f = open(lock_path, "a+", encoding="utf-8")
        try:
            fcntl.flock(lock_f, fcntl.LOCK_EX)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            lock_f.close()
    return dict(line)


def read_ledger(runs_dir, routine=None, state=None, limit=None):
    """اقرأ سطور السجل (الأقدم أولًا)؛ سطر تالف يُتخطى.

    فلترة اختيارية بالروتين والحالة؛ وlimit يرجع آخر N
    سطور فقط (بلا حد إن غاب).
    """
    path = ledger_path(runs_dir)
    lines = []
    if not os.path.isfile(path):
        return lines
    try:
        with open(path, encoding="utf-8") as fh:
            raw_lines = fh.readlines()
    except OSError:
        return lines
    for raw in raw_lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            record = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(record, dict) or not record.get("routine"):
            continue
        if routine is not None and record.get("routine") != routine:
            continue
        if state is not None and record.get("state") != state:
            continue
        lines.append(record)
    if limit is not None:
        lines = lines[-int(limit):]
    return lines


def latest_ledger_entry(runs_dir, routine):
    """آخر سطر لروتين؛ None إن لم يكن له أي وقوع."""
    entries = read_ledger(runs_dir, routine=routine)
    return entries[-1] if entries else None


def is_previous_active(runs_dir, routine):
    """هل الجولة السابقة ما زالت نشطة؟

    نشطة = آخر سطر للروتين حالته "running" (بلا ختم
    لاحق). "queued" وحدها ليست جولة نشطة — انتظار بلا
    تنفيذ لا يمنع وقوعًا جديدًا.
    """
    latest = latest_ledger_entry(runs_dir, routine)
    return latest is not None and latest.get("state") == "running"


def skip_if_previous_active(runs_dir, routine, job_id=None):
    """فحص ما قبل البدء: السابقة نشطة؟ ← تخطَّ.

    إن كانت نشطة: سطر سجل skipped/previous_active واحد،
    و{"skipped": True, "reason": "previous_active"} — بلا
    طابور غير محدود أبدًا. وإن لم تكن: {"skipped": False}
    بلا أي سطر.
    """
    if is_previous_active(runs_dir, routine):
        line = append_ledger(runs_dir, routine, "skipped",
                             "previous_active", job_id=job_id)
        return {"skipped": True, "reason": "previous_active",
                "ledger": line}
    return {"skipped": False, "reason": None, "ledger": None}


def record_missed_collapsed(runs_dir, routine, missed,
                            job_id=None):
    """انهِ الفائت القديم في صف Missed واحد (count = عدده).

    missed: قائمة مواعيد/معرّفات فائتة؛ وقائمة فارغة ترجع
    None بلا أي سطر. السطر: missed/missed_window.
    """
    missed = list(missed or [])
    if not missed:
        return None
    return append_ledger(runs_dir, routine, "missed",
                         "missed_window", job_id=job_id,
                         count=len(missed))


def record_no_new_data(runs_dir, routine, checked_at=None,
                       job_id=None):
    """سجّل جولة فحوص بلا جديد: skipped/no_new_data.

    checked_at (إن أُعطي) هو طابع السطر — «لا جديد → لا
    دور ولا جولة، فقط checked at».
    """
    return append_ledger(runs_dir, routine, "skipped",
                         "no_new_data", job_id=job_id,
                         ts=checked_at)


def record_check_failed(runs_dir, routine, job_id=None):
    """سجّل فحصًا فاشلًا/مشوّهًا: failed/check_failed.

    الفشل ليس «لا جديد» أبدًا — له سطره الخاص وسببه
    الخاص، ويُبقي المؤشر للتراجع (انظر backoff_delay).
    """
    return append_ledger(runs_dir, routine, "failed",
                         "check_failed", job_id=job_id)


def record_cap_reached(runs_dir, routine, job_id=None):
    """سجّل وقوعًا تُخطّي لبلوغ خنق جولات الذكاء:
    skipped/cap_reached."""
    return append_ledger(runs_dir, routine, "skipped",
                         "cap_reached", job_id=job_id)


def plan_catch_up_12h(missed_due, now=None):
    """خطة اللحاق بالفائت (نافذة 12 ساعة).

    missed_due: قائمة مواعيد فائتة (نص ISO أو datetime).
    الأحدث خلال 12 ساعة يعمل متأخرًا (run + run_late)؛
    والأقدم ينهار في missed_collapsed (يُسجَّل صف Missed
    واحد عبر record_missed_collapsed)؛ وموعد مستقبلي
    (لم يفُت بعد) يظهر في future ولا يُعدّ فائتًا. موعد
    غير قابل للتحليل يرفع ValueError بدل تخمين.
    ترجع {"run", "run_late", "missed_collapsed",
          "missed_count", "skipped", "future"} — والمواعيد
    نصوص ISO بتوقيت القاهرة.
    """
    moment = _coerce_now(now)
    parsed = []
    for due in (missed_due or []):
        when = _parse_when(due)
        if when is None:
            raise ValueError("موعد فائت غير صالح: %s" % (due,))
        parsed.append(when)
    parsed.sort()
    recent, older, future = [], [], []
    for when in parsed:
        if when > moment:
            future.append(when)
        elif (moment - when).total_seconds() \
                <= CATCH_UP_WINDOW_SECONDS:
            recent.append(when)
        else:
            older.append(when)
    run = recent[-1] if recent else None
    iso = lambda when: when.isoformat(timespec="seconds")
    return {"run": iso(run) if run is not None else None,
            "run_late": run is not None,
            "missed_collapsed": [iso(w) for w in older],
            "missed_count": len(older),
            "skipped": [iso(w) for w in recent[:-1]],
            "future": [iso(w) for w in future]}


def apply_catch_up(runs_dir, routine, missed_due, now=None,
                   job_id=None):
    """خطط للحاق وسجّل الفائت القديم في صف Missed واحد.

    ترجع خطة plan_catch_up_12h نفسها + مفتاح "ledger"
    (سطر Missed المنهار أو None إن لم يكن فائت قديم).
    """
    plan = plan_catch_up_12h(missed_due, now=now)
    line = record_missed_collapsed(
        runs_dir, routine, plan["missed_collapsed"],
        job_id=job_id)
    plan["ledger"] = line
    return plan


def run_pre_model_checks(checks, now=None):
    """فحوص ما قبل النموذج: كود عادي، بلا دور نموذج.

    checks: قاموس {اسم: دالة بلا وسيطات} أو قائمة أزواج
    (اسم، دالة). كل دالة ترجع: True/False (جديد؟)، أو
    قاموس {"has_new": bool, "detail": ...}، أو None
    (= لا جديد). استثناء أو قيمة مشوّهة (قاموس بلا
    has_new منطقي، أو أي نوع آخر) ← فحص فاشل: ليس
    «لا جديد» أبدًا — has_new_data تبقى كما وجدتها
    الفحوص السليمة، وfailed=True، والخطأ في results.
    ترجع {"has_new_data", "checked_at", "failed",
          "results": {اسم: {"has_new", "detail", "error"}},
          "errors": [رسائل الفشل]} — ولا تستدعي أي نموذج.
    """
    if isinstance(checks, dict):
        items = list(checks.items())
    else:
        items = list(checks or [])
    results, errors = {}, []
    has_new = False
    failed = False
    for name, fn in items:
        name = str(name)
        entry = {"has_new": False, "detail": None, "error": None}
        try:
            value = fn()
        except Exception as e:  # noqa: BLE001 — فشل الفحص
            # يُسجَّل ويُبلَّغ، لا يُرمى ولا يُقرأ «لا جديد».
            entry["error"] = "فشل فحص %s: %s" % (name, e)
            errors.append(entry["error"])
            failed = True
            results[name] = entry
            continue
        if value is None:
            pass
        elif isinstance(value, bool):
            entry["has_new"] = value
        elif isinstance(value, dict) \
                and isinstance(value.get("has_new"), bool):
            entry["has_new"] = bool(value["has_new"])
            detail = value.get("detail")
            if detail is not None:
                entry["detail"] = str(detail)[:500]
        else:
            entry["error"] = (
                "فحص %s أرجع قراءة مشوّهة (%s) — ليست «لا "
                "جديد»: تُبقي المؤشر وتتراجع" % (name, type(value).__name__))
            errors.append(entry["error"])
            failed = True
            results[name] = entry
            continue
        if entry["has_new"]:
            has_new = True
        results[name] = entry
    return {"has_new_data": has_new,
            "checked_at": _coerce_now(now).isoformat(
                timespec="seconds"),
            "failed": failed,
            "results": results,
            "errors": errors}


def should_run_model(check_result):
    """هل يبدأ دور نموذج بعد الفحوص؟ جديد سليم فقط.

    جديد + بلا فشل ← True. بلا جديد ← False (فقط
    «checked at»). فشل/قراءة مشوّهة ← False (تُبقي
    المؤشر وتتراجع — ليست «لا جديد»).
    """
    result = check_result or {}
    return bool(result.get("has_new_data")) \
        and not bool(result.get("failed"))


def is_no_new_data(check_result):
    """هل الفحوص سليمة وبلا جديد؟ (فقط «checked at»)."""
    result = check_result or {}
    return (not bool(result.get("failed"))
            and not bool(result.get("has_new_data")))


def backoff_delay(failure_index, jitter=True, rng=None):
    """فاصل التراجع بعد جولة فاشلة (استيراد كسول).

    15 دقيقة ثم مضاعفة حتى سقف 4 ساعات مع jitter —
    التسلسل نفسه في lib/retry_policy.py
    (routine_backoff_delay)؛ وبلا jitter يرجع القيمة
    الدقيقة (للتخطيط والاختبار).
    """
    from lib import retry_policy as retry_policy_mod
    return retry_policy_mod.routine_backoff_delay(
        failure_index, jitter=jitter, rng=rng)


def ai_turns_in_window(timestamps, now=None,
                       window_seconds=AI_TURNS_WINDOW_SECONDS):
    """عدد جولات الذكاء في النافذة (افتراضيًا آخر 24 ساعة).

    timestamps: قائمة نصوص ISO أو datetime. قيمة تالفة
    تُتخطى (لا تُحسب جولة لم تحدث يقينًا).
    """
    moment = _coerce_now(now)
    count = 0
    for stamp in (timestamps or []):
        when = _parse_when(stamp)
        if when is None:
            continue
        delta = (moment - when).total_seconds()
        if 0 <= delta <= window_seconds:
            count += 1
    return count


def ai_turns_allowed(timestamps, now=None,
                     limit=AI_TURNS_MAX_PER_24H):
    """هل يسمح الخنق بجولة ذكاء جديدة؟ 24 كحد أقصى/24 ساعة."""
    return ai_turns_in_window(timestamps, now=now) < int(limit)


def _ai_turns_path(runs_dir):
    base = os.path.abspath(os.path.expanduser(runs_dir))
    return os.path.join(base, AI_TURNS_FILENAME)


def record_ai_turn(runs_dir, routine, now=None):
    """سجّل جولة ذكاء منفَّذة (سطر في routine-ai-turns.jsonl).

    يرجع السطر {"ts", "routine"}. لا يفحص الخنق — الفحص
    في check_ai_cap قبل البدء.
    """
    routine = (routine or "").strip() \
        if isinstance(routine, str) else ""
    if not routine:
        raise ValueError("اسم الروتين مفقود — مرّر routine غير فارغ")
    record = {"ts": _coerce_now(now).isoformat(timespec="seconds"),
              "routine": routine}
    path = _ai_turns_path(runs_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _LEDGER_THREAD_LOCK:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return dict(record)


def ai_turns_allowed_in_runs(runs_dir, routine=None, now=None,
                             limit=AI_TURNS_MAX_PER_24H):
    """هل يسمح الخنق بجولة ذكاء جديدة (من ملف الحالة)؟

    routine معيّن ← العدّ لذلك الروتين فقط؛ وبلا روتين
    ← العدّ العام لكل الروتينات. ترجع
    {"allowed": bool, "used": int, "limit": int}.
    """
    path = _ai_turns_path(runs_dir)
    stamps = []
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.readlines()
        except OSError:
            lines = []
        for raw in lines:
            try:
                record = json.loads(raw.strip())
            except ValueError:
                continue
            if not isinstance(record, dict) or not record.get("ts"):
                continue
            if routine is not None \
                    and record.get("routine") != routine:
                continue
            stamps.append(record["ts"])
    used = ai_turns_in_window(stamps, now=now)
    return {"allowed": used < int(limit),
            "used": used, "limit": int(limit)}


def check_ai_cap(runs_dir, routine, now=None,
                 limit=AI_TURNS_MAX_PER_24H):
    """افحص الخنق قبل بدء جولة ذكاء جديدة.

    مسموح ← {"allowed": True, "used", "limit"} بلا سطر.
    مبلوغ ← سطر سجل skipped/cap_reached واحد +
    {"allowed": False, "reason": "cap_reached", ...}؛
    والعناصر تنتظر إعادة الضبط (لا جولة فائتة صامتة).
    """
    verdict = ai_turns_allowed_in_runs(
        runs_dir, routine=routine, now=now, limit=limit)
    if verdict["allowed"]:
        return verdict
    line = record_cap_reached(runs_dir, routine)
    verdict["reason"] = "cap_reached"
    verdict["ledger"] = line
    return verdict


def boot_delay_remaining(started_at, now=None,
                         delay_seconds=BOOT_DELAY_SECONDS):
    """ثوانٍ متبقية من تأخير الإقلاع (0 إن انقضى).

    started_at: وقت بدء العملية (datetime أو نص ISO).
    أول الفحوص تنتظر دقيقتين بعد البدء؛ وقيمة غير قابلة
    للتحليل تعني: لا انتظار موثوق ← 0 (لا حظر بلا دليل).
    """
    started = _parse_when(started_at)
    if started is None:
        return 0
    moment = _coerce_now(now)
    remaining = delay_seconds - (moment - started).total_seconds()
    return max(int(remaining), 0)


def should_wait_for_boot(started_at, now=None,
                         delay_seconds=BOOT_DELAY_SECONDS):
    """هل ما زلنا داخل دقيقتي تأخير الإقلاع؟"""
    return boot_delay_remaining(started_at, now=now,
                                delay_seconds=delay_seconds) > 0


def busy_wait_decision(is_busy):
    """قرار انتظار عامل مشغول: ينتظر، بلا إشعار، ولا يفشل أبدًا.

    is_busy=True ← {"wait": True, "notify": False,
    "fail": False, "reason": "busy_wait"}؛ وFalse ←
    {"wait": False, "notify": False, "fail": False,
    "reason": None}. الانشغال ليس فشلًا ولا سبب إشعار.
    """
    busy = bool(is_busy)
    return {"wait": busy, "notify": False, "fail": False,
            "reason": "busy_wait" if busy else None}


def note_busy_wait(runs_dir, routine, job_id=None):
    """سجّل انتظار عامل مشغول: queued/busy_wait + القرار.

    ترجع قرار busy_wait_decision(True) نفسه + مفتاح
    "ledger" (سطر الانتظار). بلا إشعار إطلاقًا.
    """
    line = append_ledger(runs_dir, routine, "queued",
                         "busy_wait", job_id=job_id)
    decision = busy_wait_decision(True)
    decision["ledger"] = line
    return decision


class ScheduleWatchError(Exception):
    """خطأ في مراقبة المنشور المجدول (رسالته عربية)."""


def build_first_comment(story):
    """نص أول تعليق: العبرة + السؤال المحيّر + الدعوة اللطيفة
    بموعد الجزء التالي.

    story قاموس {moral, question, next_part_time} — موعد الجزء
    التالي اختياري (الافتراضي «بكرة 7 مساءً» من
    caption_check.DEFAULT_NEXT_PART_TIME). غياب moral أو
    question يرفع ValueError صريحًا بدل نص مخترع.
    """
    story = story or {}
    moral = (story.get("moral") or "").strip()
    question = (story.get("question") or "").strip()
    if not moral:
        raise ValueError(
            "العبرة مفقودة — لا يمكن بناء أول تعليق بلا عبرة")
    if not question:
        raise ValueError(
            "السؤال المحيّر مفقود — لا يمكن بناء أول تعليق بلا سؤال")
    next_part_time = ((story.get("next_part_time") or "").strip()
                      or caption_check.DEFAULT_NEXT_PART_TIME)
    lines = ["«%s»" % moral,
             question,
             caption_check.approved_invite(next_part_time)]
    return "\n".join(lines)


def status_from_watch(result):
    """حوّل نتيجة watch_slot إلى حالة نشر موحّدة (أ2-8).

    ok=True ← المنشور نُشر وعُلّق عليه ← "published"؛
    reason=not_published ← لم يُنشر بعد ← "pending"؛
    وأي فشل (error) ← "failed"؛ وdry-run أو نتيجة بلا ok
    تُقرأ "pending" (لم يحدث نشر بعد).
    """
    result = result or {}
    if result.get("ok") is True:
        return "published"
    if result.get("reason") == "not_published":
        return "pending"
    if result.get("error"):
        return "failed"
    return "pending"


def apply_watch_result(statuses, number, result,
                       platform="facebook"):
    """طبّق نتيجة watch_slot على حالات نشر عنصر (أ2-8).

    statuses خريطة {رقم: {منصة: حالة}}؛ وwatch_slot يراقب
    فيسبوك افتراضيًا (أول تعليق على منشور الصفحة) لذا
    platform الافتراضية "facebook". يرجع حالات العنصر
    المطبّعة كاملة بعد التحديث (دالة نقية — لا تكتب ملفًا).
    """
    from lib import queue as queue_lib
    return queue_lib.update_platform_status(
        statuses, number, platform, status_from_watch(result))


def _read_state(result):
    """استخرج حالة المنشور من نتيجة read_fn.

    تقبل نص حالة مباشرًا («published»/«scheduled»/…) أو
    قاموسًا فيه مفتاح «state». أي قيمة مفقودة أو غير نصية
    تُرجع «غير معروفة» — بلا اختراع حالة.
    """
    if isinstance(result, dict):
        state = result.get("state")
    else:
        state = result
    if isinstance(state, str) and state.strip():
        return state.strip()
    return UNKNOWN


def _execute_watch(post_id, story, read_fn, comment_fn, slot, text):
    """جسم التنفيذ الفعلي (قراءة + تعليق) — بلا سجل مهام.
    يُستدعى من watch_slot بعد التسجيل المسبق للبدء.
    """
    try:
        state = _read_state(read_fn(post_id))
    except Exception as e:  # noqa: BLE001 — تُترجم لرسالة عربية
        return {"ok": False, "post_id": str(post_id), "slot": slot,
                "dry_run": False,
                "error": "تعذّرت قراءة حالة المنشور %s: %s"
                         % (post_id, e)}
    if state != "published":
        return {"ok": False, "post_id": str(post_id), "slot": slot,
                "dry_run": False, "state": state,
                "reason": "not_published",
                "message": "المنشور لم يُنشر بعد (الحالة: %s) — "
                           "لا تعليق الآن، وستُعاد المراقبة في "
                           "التشغيل التالي" % state}
    last_error = None
    for attempt in (1, 2):
        try:
            result = comment_fn(post_id, text)
            comment_id = UNKNOWN
            if isinstance(result, dict):
                comment_id = (result.get("comment_id")
                              or result.get("id") or UNKNOWN)
            return {"ok": True, "post_id": str(post_id), "slot": slot,
                    "dry_run": False, "state": "published",
                    "comment": text, "comment_id": comment_id,
                    "attempts": attempt}
        except Exception as e:  # noqa: BLE001 — إعادة واحدة فقط
            last_error = e
    return {"ok": False, "post_id": str(post_id), "slot": slot,
            "dry_run": False, "state": "published",
            "error": "فشل نشر أول تعليق على المنشور %s بعد "
                     "محاولتين: %s" % (post_id, last_error)}


def watch_slot(post_id, story, read_fn, comment_fn, execute=False,
               slot="morning", runs_dir=None, due=None, routine=None):
    """راقب خانة مجدولة وعلّق أول تعليق عند نشرها.

    - dry-run (الافتراضي): لا يستدعي read_fn ولا comment_fn
      إطلاقًا؛ يرجع قاموس خطة {post_id, slot, would_check,
      would_post, dry_run} — ولا يسجّل شيئًا في سجل المهام.
    - execute=True: يستدعي read_fn(post_id)؛ إن رجع
      «published» استدعِ comment_fn(post_id, text)؛ عند فشل
      النشر أعد المحاولة مرة واحدة فقط ثم ارجع {ok: False,
      error: <رسالة عربية واضحة>}؛ وإن لم يكن المنشور منشورًا
      بعد (scheduled أو غيره) فلا تعليق وارجع {ok: False,
      reason: "not_published"} مع رسالة عربية.
    - runs_dir (اختياري، مع execute فقط): دلالات المهام
      المجدولة — تُسجَّل الـoccurrence في سجل المهام (نوع
      schedule) **قبل** أي قراءة أو تعليق؛ فإن وُجدت مسجلة
      أصلًا (ريستارت بعد البدء) تُتخطى بلا أي استدعاء
      ({reason: "already_started", skipped: True})؛ وبعد
      التنفيذ تُختم done (نُشر أو لم يُنشر بعد — الخانة
      فُحصت) أو failed عند خطأ. due هو موعد الخانة القانوني
      (الافتراضي: موعد الخانة اليوم بتوقيت القاهرة)؛ خانة
      الغد occurrence مختلفة فتُشغَّل من جديد.
    - routine (اختياري، مع runs_dir وexecute فقط): اسم
      روتين في سجل الوقوعات — إن كانت جولته السابقة ما
      زالت نشطة (آخر سطر running) يُتخطى الوقوع بسطر
      سجل skipped/previous_active بلا أي استدعاء.

    read_fn(post_id) -> نص حالة أو قاموس فيه «state».
    comment_fn(post_id, text) -> أي نتيجة (قاموس فيه
    comment_id/comment_url عند توفرهما) أو يرفع استثناءً عند
    الفشل. لا إعادة محاولة أكثر من مرة أبدًا.
    """
    post_id = (post_id or "").strip() if isinstance(post_id, str) \
        else post_id
    if not post_id:
        raise ValueError("معرّف المنشور مفقود — مرّر --post-id")
    if slot not in SLOTS:
        raise ValueError("الموعد غير صالح: %s (المسموح: morning/evening)"
                         % slot)
    text = build_first_comment(story)
    if not execute:
        return {"post_id": str(post_id), "slot": slot,
                "would_check": True, "would_post": text,
                "dry_run": True}
    if runs_dir is not None and routine:
        # فحص ما قبل البدء (بند 6): جولة سابقة ما زالت
        # نشطة ← تُتخطى بسطر سجل previous_active، بلا أي
        # استدعاء لـ read_fn ولا comment_fn وبلا طابور.
        skip = skip_if_previous_active(runs_dir, routine)
        if skip["skipped"]:
            return {"ok": False, "post_id": str(post_id),
                    "slot": slot, "dry_run": False,
                    "reason": "previous_active", "skipped": True,
                    "message": "جولة سابقة للروتين %s ما زالت "
                               "نشطة — يُتخطى هذا الوقوع "
                               "(سطر سجل previous_active)"
                               % routine}
    job = None
    job_registry = None
    if runs_dir is not None:
        from lib import job_registry as job_registry_mod
        job_registry = job_registry_mod
        due_value = due or default_due(slot)
        key = occurrence_key(str(post_id), slot, due_value)
        existing = job_registry.list_jobs(
            runs_dir, story=key, kind="schedule")
        if existing:
            return {"ok": False, "post_id": str(post_id),
                    "slot": slot, "dry_run": False,
                    "reason": "already_started", "skipped": True,
                    "message": "هذه الخانة (%s) سُجّلت بدايتها "
                               "من قبل — تُتخطى ولا تُكرر "
                               "(ريستارت بعد البدء)" % key}
        try:
            job = job_registry.register_job(
                runs_dir, "schedule", story=key,
                title="مراقبة منشور %s (%s)" % (post_id, slot))
        except Exception as e:  # noqa: BLE001 — فشل مغلق: بلا
            # تسجيل مسبق لا ضمان ضد التكرار، فلا تنفيذ إطلاقًا.
            return {"ok": False, "post_id": str(post_id),
                    "slot": slot, "dry_run": False,
                    "error": "تعذّر تسجيل بداية الخانة %s قبل "
                             "التنفيذ — أُلغي التشغيل منعًا "
                             "للتكرار: %s" % (key, e)}
    res = _execute_watch(post_id, story, read_fn, comment_fn, slot,
                         text)
    if job is not None:
        try:
            status = ("done" if (res.get("ok")
                                 or res.get("reason") == "not_published")
                      else "failed")
            job_registry.update_job(
                runs_dir, job["job_id"], status=status,
                error=res.get("error"))
        except Exception:  # noqa: BLE001 — ختم السجل لا يغيّر
            # نتيجة التنفيذ نفسها.
            pass
    return res
