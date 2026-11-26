#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""دفاتر تشغيل (runbooks) مقروءة آليًا: فحوصات قراءة فقط بلا أي إصلاح.

المصدر (النمط فقط، بلا نسخ): مشروع OpenSRE — مستودع Tracer-Cloud/opensre، الفرع main، الالتزام d3d0af888005dd6ed29cb5a5ec7223c6150b1fdf (2026-11-26)، رخصة Apache-2.0.

الدفتر ملف JSON بالصيغة::

    {"id": str, "title": str, "for": str,
     "steps": [{"id": str, "title": str,
                "check": {"type": ..., ...},
                "fix_hint": str}]}

أنواع الفحص المدعومة (كلها قراءة فقط):
- ``tool``: ‏{"tool": "melt", "args": ["-version"]} — الأداة موجودة
  في PATH (‏shutil.which‏)، وإن وُجدت ``args`` تُشغَّل ويُقبل
  خروج 0 فقط.
- ``file_exists``: ‏{"path": "..."} — الملف موجود. يدعم العنصر
  النائب ``{root}`` في بداية المسار.
- ``symlink_target``: ‏{"path": "...", "must_exist": true} —
  الرابط الرمزي موجود وهدفه موجود (عند ``must_exist``).
- ``python_import``: ‏{"module": "PIL"} — الوحدة قابلة للاستيراد
  (تُفحص بـ ‏importlib.util.find_spec‏ بلا تنفيذ كودها).
- ``json_field``: ‏{"path": "...", "field": "status",
  "equals": "ok"} — يقرأ JSON ويقارن حقلًا؛ ويقبل أيضًا
  ``"not_equals"`` (يمرّ عندما تختلف القيمة) لأن بعض الفحوصات
  صيغتها نفي (مثل «الحالة ليست published»). يمكن الجمع بينهما،
  ويُقبل مسار حقل منقّط (مثل ``"publish.facebook"``) للحقول
  المتداخلة. واحد منهما على الأقل لازم.
- ``video_duration``: ‏{"path": "...", "min": 40, "max": 60} —
  مدة الفيديو بالثواني ضمن النطاق، تُقاس بـ ``ffprobe``؛ وإن
  لم يتوفر ``ffprobe`` تُتخطى الخطوة (skip) مع توثيق السبب.

نوع فحص غير معروف ← الخطوة ``skip`` مع السبب، لا فشل.

استبدال ``{root}`` يتم في ``check_runbook`` فقط (لا في
``load_runbook``)، وعند بداية المسار فقط. الوحدة لا تكتب أي
ملف أبدًا، ولا تُصلح شيئًا — الفحص فقط، و``fix_hint`` في كل
خطوة يشرح الإصلاح يدويًا بالعربية.
"""

import importlib.util
import json
import os
import shutil
import subprocess

__all__ = ["RunbookError", "load_runbook", "list_runbooks", "check_runbook"]


class RunbookError(Exception):
    """خطأ في دفتر التشغيل (رسالته عربية)."""


# ---------------------------------------------------------------------------
# التحميل والتحقق من البنية
# ---------------------------------------------------------------------------

def _fail(message):
    raise RunbookError(message)


def _validate_runbook(data, source="<دفتر>"):
    """يتحقق من بنية دفتر محمّل، ويرفع RunbookError برسالة عربية."""
    if not isinstance(data, dict):
        _fail("الدفتر في %s ليس كائن JSON صالحًا: المتوقع قاموس." % source)
    for field in ("id", "title", "for"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            _fail("الدفتر في %s ناقص: الحقل «%s» مفقود أو فارغ." % (source, field))
    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        _fail("الدفتر «%s» ناقص: الحقل «steps» مفقود أو فارغ." % data.get("id", source))
    seen = set()
    for index, step in enumerate(steps):
        where = "الخطوة رقم %d في الدفتر «%s»" % (index + 1, data["id"])
        if not isinstance(step, dict):
            _fail("%s ليست كائنًا صالحًا." % where)
        for field in ("id", "title", "check", "fix_hint"):
            if field not in step:
                _fail("%s ناقصة: الحقل «%s» مفقود." % (where, field))
        if not isinstance(step["id"], str) or not step["id"].strip():
            _fail("%s ناقصة: معرّف الخطوة «id» مفقود أو فارغ." % where)
        if step["id"] in seen:
            _fail("الدفتر «%s» فيه معرّف خطوة مكرر: «%s»." % (data["id"], step["id"]))
        seen.add(step["id"])
        if not isinstance(step["title"], str) or not step["title"].strip():
            _fail("%s ناقصة: الحقل «title» مفقود أو فارغ." % where)
        if not isinstance(step["fix_hint"], str) or not step["fix_hint"].strip():
            _fail("%s ناقصة: الحقل «fix_hint» مفقود أو فارغ." % where)
        check = step["check"]
        if not isinstance(check, dict):
            _fail("%s ناقصة: الحقل «check» ليس كائنًا." % where)
        if not isinstance(check.get("type"), str) or not check["type"].strip():
            _fail("%s ناقصة: نوع الفحص «type» مفقود أو فارغ." % where)
    return data


def load_runbook(path):
    """يحمّل دفتر تشغيل من ملف JSON ويتحقق من بنيته.

    يرفع ``RunbookError`` برسالة عربية عند JSON تالف أو بنية
    ناقصة أو ملف مفقود.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        _fail("ملف الدفتر غير موجود: %s" % path)
    except json.JSONDecodeError as exc:
        _fail("ملف الدفتر %s فيه JSON تالف: %s" % (path, exc))
    except OSError as exc:
        _fail("تعذّرت قراءة ملف الدفتر %s: %s" % (path, exc))
    return _validate_runbook(data, source=str(path))


def list_runbooks(directory):
    """يرجع معرّفات دفاتر التشغيل (ملفات ‎*.json) في مجلد، مرتبة.

    يرفع ``RunbookError`` إن كان المجلد مفقودًا أو احتوى ملفًا
    تالفًا أو ناقص البنية.
    """
    if not os.path.isdir(directory):
        _fail("مجلد الدفاتر غير موجود: %s" % directory)
    ids = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        runbook = load_runbook(os.path.join(directory, name))
        ids.append(runbook["id"])
    return ids


# ---------------------------------------------------------------------------
# تنفيذ الفحوصات (قراءة فقط)
# ---------------------------------------------------------------------------

def _resolve(path, root):
    """يستبدل العنصر النائب ``{root}`` في بداية المسار فقط."""
    if isinstance(path, str) and path.startswith("{root}"):
        return root + path[len("{root}"):]
    return path


def _get_field(data, field):
    """يقرأ حقلًا (يدعم المسار المنقّط للحقول المتداخلة)."""
    current = data
    for part in str(field).split("."):
        if not isinstance(current, dict) or part not in current:
            return None, False
        current = current[part]
    return current, True


def _check_tool(check):
    tool = check.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        return "skip", "تعريف الفحص ناقص: يلزم حقل «tool»."
    if shutil.which(tool) is None:
        return "fail", "الأداة «%s» غير موجودة في PATH." % tool
    args = check.get("args") or []
    if not args:
        return "pass", "الأداة «%s» موجودة في PATH." % tool
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        return "skip", "تعريف الفحص ناقص: حقل «args» يجب أن يكون قائمة نصوص."
    try:
        result = subprocess.run(
            [tool] + args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "fail", "الأداة «%s» لم ترد خلال 30 ثانية." % tool
    except OSError as exc:
        return "fail", "تعذّر تشغيل الأداة «%s»: %s" % (tool, exc)
    if result.returncode == 0:
        return "pass", "الأداة «%s» تعمل (خرج 0)." % tool
    return "fail", "الأداة «%s» خرجت برمز %d." % (tool, result.returncode)


def _check_file_exists(check, root):
    path = check.get("path")
    if not isinstance(path, str) or not path.strip():
        return "skip", "تعريف الفحص ناقص: يلزم حقل «path»."
    resolved = _resolve(path, root)
    if os.path.isfile(resolved):
        return "pass", "الملف موجود: %s" % resolved
    return "fail", "الملف غير موجود: %s" % resolved


def _check_symlink_target(check, root):
    path = check.get("path")
    if not isinstance(path, str) or not path.strip():
        return "skip", "تعريف الفحص ناقص: يلزم حقل «path»."
    resolved = _resolve(path, root)
    if not os.path.islink(resolved):
        return "fail", "المسار ليس رابطًا رمزيًا: %s" % resolved
    if check.get("must_exist", False) and not os.path.exists(resolved):
        return "fail", "الرابط موجود لكن هدفه مفقود: %s" % resolved
    target = os.readlink(resolved)
    return "pass", "الرابط سليم ويشير إلى: %s" % target


def _check_python_import(check):
    module = check.get("module")
    if not isinstance(module, str) or not module.strip():
        return "skip", "تعريف الفحص ناقص: يلزم حقل «module»."
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError, AttributeError) as exc:
        return "fail", "الوحدة «%s» غير قابلة للاستيراد: %s" % (module, exc)
    if spec is None:
        return "fail", "الوحدة «%s» غير قابلة للاستيراد." % module
    return "pass", "الوحدة «%s» قابلة للاستيراد." % module


def _check_json_field(check, root):
    path = check.get("path")
    field = check.get("field")
    if not isinstance(path, str) or not path.strip():
        return "skip", "تعريف الفحص ناقص: يلزم حقل «path»."
    if not isinstance(field, str) or not field.strip():
        return "skip", "تعريف الفحص ناقص: يلزم حقل «field»."
    if "equals" not in check and "not_equals" not in check:
        return "skip", "تعريف الفحص ناقص: يلزم «equals» أو «not_equals»."
    resolved = _resolve(path, root)
    try:
        with open(resolved, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return "fail", "ملف الحالة غير موجود: %s" % resolved
    except json.JSONDecodeError as exc:
        return "fail", "ملف الحالة %s فيه JSON تالف: %s" % (resolved, exc)
    except OSError as exc:
        return "fail", "تعذّرت قراءة ملف الحالة %s: %s" % (resolved, exc)
    value, found = _get_field(data, field)
    if not found:
        return "fail", "الحقل «%s» غير موجود في %s." % (field, resolved)
    if "equals" in check and value != check["equals"]:
        return "fail", "الحقل «%s» قيمته «%s» لا «%s»." % (field, value, check["equals"])
    if "not_equals" in check and value == check["not_equals"]:
        return "fail", "الحقل «%s» قيمته «%s» وهي القيمة الممنوعة." % (field, value)
    return "pass", "الحقل «%s» قيمته «%s» كما هو متوقع." % (field, value)


def _check_video_duration(check, root):
    path = check.get("path")
    if not isinstance(path, str) or not path.strip():
        return "skip", "تعريف الفحص ناقص: يلزم حقل «path»."
    resolved = _resolve(path, root)
    if not os.path.isfile(resolved):
        return "fail", "ملف الفيديو غير موجود: %s" % resolved
    if shutil.which("ffprobe") is None:
        return "skip", "ffprobe غير متوفر — لا يمكن قياس مدة الفيديو."
    minimum = check.get("min")
    maximum = check.get("max")
    if minimum is None and maximum is None:
        return "skip", "تعريف الفحص ناقص: يلزم «min» أو «max»."
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", resolved],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return "fail", "ffprobe لم يرد خلال 30 ثانية."
    except OSError as exc:
        return "fail", "تعذّر تشغيل ffprobe: %s" % exc
    if result.returncode != 0:
        return "fail", "ffprobe فشل في قراءة المدة من %s." % resolved
    try:
        duration = float(result.stdout.decode("utf-8", "replace").strip())
    except ValueError:
        return "fail", "ffprobe أعاد مدة غير رقمية للملف %s." % resolved
    if minimum is not None and duration < minimum:
        return "fail", "مدة الفيديو %.1f ثانية أقل من الحد الأدنى %s ثانية." % (duration, minimum)
    if maximum is not None and duration > maximum:
        return "fail", "مدة الفيديو %.1f ثانية أكثر من الحد الأقصى %s ثانية." % (duration, maximum)
    return "pass", "مدة الفيديو %.1f ثانية ضمن النطاق المطلوب." % duration


_CHECKERS = {
    "tool": lambda check, root: _check_tool(check),
    "file_exists": _check_file_exists,
    "symlink_target": _check_symlink_target,
    "python_import": lambda check, root: _check_python_import(check),
    "json_field": _check_json_field,
    "video_duration": _check_video_duration,
}


def check_runbook(runbook, root="."):
    """ينفّذ فحوصات دفتر (قراءة فقط) ويرجع النتيجة والملخص.

    ``root`` هو الجذر الذي يستبدل العنصر النائب ``{root}`` في
    بداية المسارات. ``ok`` صحيح عندما لا توجد خطوة فاشلة
    (الخطوات المتخطاة لا تُسقطه).
    """
    _validate_runbook(runbook)
    root = os.path.abspath(root)
    results = []
    passed = failed = skipped = 0
    for step in runbook["steps"]:
        check = step["check"]
        checker = _CHECKERS.get(check["type"])
        if checker is None:
            status, detail = (
                "skip",
                "نوع الفحص «%s» غير معروف — تم تخطي الخطوة." % check["type"],
            )
        else:
            try:
                status, detail = checker(check, root)
            except Exception as exc:  # pragma: no cover - حارس أخير
                status, detail = "fail", "خطأ غير متوقع أثناء الفحص: %s" % exc
        if status == "pass":
            passed += 1
        elif status == "fail":
            failed += 1
        else:
            skipped += 1
        results.append({
            "id": step["id"],
            "title": step["title"],
            "status": status,
            "detail": detail,
        })
    total = len(results)
    return {
        "id": runbook["id"],
        "title": runbook["title"],
        "steps": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "ok": failed == 0,
        },
    }
