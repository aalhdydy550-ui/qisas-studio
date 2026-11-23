#!/usr/bin/env python3
"""استئناف تشغيل منقطع — جولة v0.1.41 (بند 6 من استخراج AlphaCLI).

ريندر/تجميع طويل يُستأنف من آخر نقطة تفتيش بعد ريستارت VM
بدل البدء من الصفر: النصوص محفوظة على القرص (script-ai.json
وmanifest.json في مجلد التشغيل) + حالة `crashed` في سجل
التشغيل (`runs/run-*.json`).

عقد الربط في `cmd_run` (يقوم به المنسّق عند التوصيل — هذا
الملف لا يعدّل studio.py ولا يستورده):
  1) عند بدء أي تشغيل: `run_record.detect_crashed(runs_dir)`
     لتعليم المنقطع من التشغيلات السابقة.
  2) بعد كل خطوة مكتملة في cmd_run:
     `run_record.save_checkpoint(_record_path, "script", inputs={...},
     outputs={"title": result["title"], "script_file": "script-ai.json"})`
     ثم بعد produce بنفس النمط مع
     `outputs={"manifest_file": "manifest.json", "images": n,
     "phrases": n}`.
     مدخلات نقطة التفتيش يجب أن تضم: story وproject وbackend
     وout_path وwatermark وgrade وcards_dir وlang وallow_fallback
     وrun_dir (مجلد التشغيل نفسه).
     خطوة assemble بلا نقطة تفتيش خاصة بها: إعادة تشغيلها من
     manifest.json آمنة لأنها تكتب فوق نفس المخرج.
  3) مع `run --resume <run_id>`:
     `path, plan = prepare_resume(runs_dir, run_id)`
     ثم تُتخطى كل خطوة `should_skip(step, plan)` صحيح لها،
     والعنوان يُستعاد بـ `load_script_result(plan["run_dir"])`
     ، ويُستأنف من `plan["next_step"]` بنفس run_dir.
     عند اكتمال الاستئناف يُنهى السجل نفسه بـ
     `run_record.finish_record(path, "done", ...)` — لا سجل جديد.
"""
import glob
import json
import os

from lib import run_record

PIPELINE_STEPS = run_record.PIPELINE_STEPS

# الحالات القابلة للاستئناف: منقطع (crashed) أو فاشل بخطأ
# موثق (failed) مع نقطة تفتيش — إعادة الخطوة الفاشلة نفسها
# بعد إصلاح سببها. done حالة نهائية لا تُستأنف.
RESUMABLE_STATUSES = ("crashed", "failed")


class ResumeError(Exception):
    """لا يمكن استئناف هذا التشغيل (بلا نقطة تفتيش، أو مكتمل،
    أو ملفات خطواته المكتملة غائبة من القرص)."""


def find_record(runs_dir, run_id):
    """ابحث عن ملف سجل تشغيل بـrun_id؛ ارجع المسار أو None."""
    for path in sorted(glob.glob(os.path.join(runs_dir, "run-*.json"))):
        record = run_record.load_record(path)
        if record and record.get("run_id") == run_id:
            return path
    return None


def completed_steps(checkpoint):
    """الخطوات المكتملة حسب نقطة تفتيش (بالترتيب) أو [] بلا نقطة."""
    if not isinstance(checkpoint, dict):
        return []
    step = checkpoint.get("step")
    if step not in PIPELINE_STEPS:
        return []
    return list(PIPELINE_STEPS[:PIPELINE_STEPS.index(step) + 1])


def next_step_after(checkpoint):
    """الخطوة التالية بعد نقطة تفتيش، أو None إن اكتملت كلها."""
    done = completed_steps(checkpoint)
    for step in PIPELINE_STEPS:
        if step not in done:
            return step
    return None


def should_skip(step, plan):
    """هل تُتخطى هذه الخطوة عند الاستئناف (اكتملت قبل الانقطاع)؟"""
    return step in (plan.get("completed_steps") or [])


def resume_plan(record, record_path=None):
    """ابنِ خطة استئناف من سجل تشغيل؛ ResumeError إن تعذّر.

    الخطة: الخطوات المكتملة، والخطوة التالية، ومدخلات إعادة
    الدخول (قصة/مشروع/خلفية/مخرج/شعار/درجة/بطاقات/لغة/بديل)،
    ومجلد التشغيل، وعدد مرات الاستئناف السابقة.
    """
    if not isinstance(record, dict):
        raise ResumeError("لا يوجد سجل تشغيل")
    run_id = record.get("run_id")
    status = record.get("status")
    if status == "done":
        raise ResumeError("التشغيل %s مكتمل أصلًا — لا حاجة للاستئناف"
                          % run_id)
    if status not in RESUMABLE_STATUSES:
        raise ResumeError("التشغيل %s بحالة %s — الاستئناف من "
                          "crashed/failed فقط" % (run_id, status))
    checkpoint = record.get("checkpoint") or {}
    step = checkpoint.get("step")
    if step not in PIPELINE_STEPS:
        raise ResumeError("التشغيل %s بلا نقطة تفتيش محفوظة — "
                          "ابدأ تشغيلًا جديدًا" % run_id)
    nxt = next_step_after(checkpoint)
    if nxt is None:
        raise ResumeError("كل خطوات التشغيل %s مكتملة — تحقق من "
                          "المخرج وأنهِ السجل" % run_id)
    inputs = dict(checkpoint.get("inputs") or {})
    settings = dict(record.get("settings") or {})
    run_dir = inputs.get("run_dir")
    if not run_dir and record_path and run_id:
        run_dir = os.path.join(os.path.dirname(record_path), run_id)
    return {
        "run_id": run_id,
        "command": record.get("command"),
        "status": status,
        "completed_steps": completed_steps(checkpoint),
        "next_step": nxt,
        "checkpoint": checkpoint,
        "settings": settings,
        "run_dir": run_dir,
        "resume_args": {
            "story": inputs.get("story") or settings.get("story"),
            "project": inputs.get("project") or settings.get("project"),
            "backend": inputs.get("backend")
                       or settings.get("backend", "concat"),
            "out_path": inputs.get("out_path"),
            "watermark": inputs.get("watermark",
                                    settings.get("watermark", True)),
            "grade": inputs.get("grade", settings.get("grade")),
            "cards_dir": inputs.get("cards_dir"),
            "lang": inputs.get("lang", "ar"),
            "allow_fallback": inputs.get("allow_fallback", True),
        },
        "resume_count": int(record.get("resume_count") or 0),
    }


def load_script_result(run_dir):
    """اقرأ نتيجة السيناريو المحفوظة (script-ai.json).

    ترجع القاموس (وفيه العنوان)؛ ResumeError إن غاب الملف
    أو تلف أو بلا عنوان.
    """
    path = os.path.join(run_dir, "script-ai.json")
    try:
        with open(path, encoding="utf-8") as fh:
            result = json.load(fh)
    except OSError:
        raise ResumeError("ملف السيناريو غائب — لا يمكن الاستئناف: %s"
                          % path)
    except ValueError:
        raise ResumeError("ملف السيناريو تالف — لا يمكن الاستئناف: %s"
                          % path)
    if not isinstance(result, dict) or not (result.get("title") or "").strip():
        raise ResumeError("ملف السيناريو بلا عنوان — لا يمكن "
                          "الاستئناف: %s" % path)
    return result


def verify_resume_inputs(plan):
    """تحقق من وجود ملفات الخطوات المكتملة على القرص.

    ترجع (صحيح، []) أو (خطأ، [أسباب النقص]).
    """
    missing = []
    run_dir = plan.get("run_dir")
    if not run_dir or not os.path.isdir(run_dir):
        return False, ["مجلد التشغيل غائب: %s" % run_dir]
    completed = plan.get("completed_steps") or []
    if "script" in completed:
        try:
            load_script_result(run_dir)
        except ResumeError as e:
            missing.append(str(e))
    if "produce" in completed:
        manifest = os.path.join(run_dir, "manifest.json")
        if not os.path.isfile(manifest):
            missing.append("بيان الإنتاج غائب — لا يمكن الاستئناف: %s"
                           % manifest)
    return (not missing), missing


def prepare_resume(runs_dir, run_id_or_path):
    """جهّز استئناف تشغيل: ابحث عن سجله، وابنِ خطته، وأعده running.

    ترجع (مسار السجل، الخطة). ترفع ResumeError إن تعذّر
    (بلا سجل، أو مكتمل، أو بلا نقطة تفتيش، أو ملفات ناقصة).
    لا تعيد أي خطوة مكتملة — الخطة نفسها هي ما يمنع ذلك
    عند الربط في cmd_run (should_skip).
    """
    if os.path.isfile(run_id_or_path):
        path = run_id_or_path
    else:
        path = find_record(runs_dir, run_id_or_path)
        if path is None:
            raise ResumeError("لا يوجد سجل تشغيل بالمعرّف: %s"
                              % run_id_or_path)
    record = run_record.load_record(path)
    if record is None:
        raise ResumeError("سجل التشغيل تالف: %s" % path)
    plan = resume_plan(record, record_path=path)
    ok, missing = verify_resume_inputs(plan)
    if not ok:
        raise ResumeError("تعذّر الاستئناف: " + "؛ ".join(missing))
    run_record.reopen_record(path)
    return path, plan


def list_resumable(runs_dir):
    """قائمة التشغيلات القابلة للاستئناف (الأحدث أولًا) مع خططها.

    لا تعلّم المنقطع بنفسها — على المتصل استدعاء
    `run_record.detect_crashed(runs_dir)` أولًا بعد ريستارت.
    """
    out = []
    for path in sorted(glob.glob(os.path.join(runs_dir, "run-*.json"))):
        record = run_record.load_record(path)
        if record is None or record.get("status") not in RESUMABLE_STATUSES:
            continue
        try:
            plan = resume_plan(record, record_path=path)
        except ResumeError:
            continue
        out.append((record.get("started_at") or "", path,
                    {"path": path, "run_id": plan["run_id"],
                     "status": plan["status"],
                     "completed_steps": plan["completed_steps"],
                     "next_step": plan["next_step"],
                     "started_at": record.get("started_at")}))
    # الأحدث أولًا حسب بدء التشغيل (اسم الملف وحده لا يكفي —
    # سجلات تُنشأ في نفس الثانية تأخذ لاحقة رقمية).
    out.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item for _, _, item in out]


def simulate_crash(record_path, step=None, inputs=None, outputs=None,
                   error="محاكاة انهيار: توقف مفاجئ وسط التنفيذ"):
    """حاكِ انهيارًا: احفظ نقطة تفتيش (إن أُعطيت خطوة) ثم علّم crashed.

    للاختبار والتدريب فقط — تحاكي ريستارت VM يقطع التشغيل
    بعد اكتمال `step`. ترجع السجل بعد التعليم.
    """
    if step is not None:
        run_record.save_checkpoint(record_path, step,
                                   inputs=inputs, outputs=outputs,
                                   note="محاكاة انهيار")
    return run_record.mark_crashed(record_path, error=error)
