#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""وحدة التدريب على الأعطال (failure drill) — جولة v0.1.60.

النمط مأخوذ من مشروع OpenSRE (Tracer-Cloud/opensre، الفرع main،
الالتزام d3d0af888005dd6ed29cb5a5ec7223c6150b1fdf، رخصة Apache-2.0):
بيئة حوادث اصطناعية للتدريب والتقييم — تُحاكي عطلًا وتتحقق من أن
الكشف يعمل. التنفيذ هنا من الصفر بالمكتبة القياسية فقط، من فهم
النمط، بلا نسخ كود أو نصوص من المشروع إطلاقًا.

ضمانات السلامة (ملزمة):
- التدريب يحاكي العطل داخل مجلد عمل مؤقت فقط (``workdir`` يُمرَّر
  أو مجلد ``tempfile`` يُنشأ تلقائيًا) — لا يحذف ولا يعدّل ولا
  ينشئ أي ملف خارج مجلد العمل هذا.
- لا يغيّر ``os.environ`` للمتصل إطلاقًا: أي تعديل بيئة يكون
  داخل نسخة ``dict`` تُمرَّر لدالة الكشف فقط.
- لا يمسّ ``HOME`` الحقيقي ولا ``PATH`` الحقيقي.
- كل drill ينظّف مجلد عمله المؤقت بعد انتهائه إلا إن طُلب
  الاحتفاظ به صراحة (``keep=True``). مجلد ``workdir`` يمرّره
  المتصل يبقى ملكًا للمتصل ولا يُحذف أبدًا.
"""
import os
import shutil
import tempfile

__all__ = ["DrillError", "list_drills", "run_drill", "run_all_drills"]

#: الحد الأدنى المقبول لإصدار Pillow في الاستوديو.
_MIN_PILLOW_VERSION = (13, 0, 0)


class DrillError(Exception):
    """خطأ في التدريب على الأعطال (رسالته عربية)."""


def _parse_version(text):
    """حلّل سلسلة إصدار مثل ``"10.2.0"`` إلى صف أعداد صحيحة.

    دالة مقارنة إصدارات خالصة — لا تقرأ أي حزمة حقيقية.
    الأجزاء غير الرقمية تُتجاهل بعد أرقامها البادئة.
    """
    parts = []
    for chunk in str(text).split("."):
        digits = ""
        for char in chunk:
            if char.isdigit():
                digits += char
            else:
                break
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def _drill_missing_melt(workdir):
    """حاكِ غياب melt: مجلد bin فارغ وPATH بلا melt."""
    bin_dir = os.path.join(workdir, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    # نسخة dict فقط — لا مساس بـ os.environ للمتصل.
    env = {"PATH": bin_dir}
    found = shutil.which("melt", path=env["PATH"])
    detected = found is None
    if detected:
        detail = "لم يُعثر على melt في PATH المؤقت — الكشف عمل كما هو متوقع."
    else:
        detail = "عُثر على melt في PATH المؤقت رغم أن مجلد bin فارغ."
    return detected, detail


def _drill_broken_piper_link(workdir):
    """حاكِ رابط piper مكسورًا: رابط رمزي dangling داخل workdir."""
    link = os.path.join(workdir, "piper")
    target = os.path.join(workdir, "piper-target-missing")
    if os.path.lexists(link):
        os.unlink(link)
    os.symlink(target, link)
    detected = os.path.lexists(link) and not os.path.exists(link)
    if detected:
        detail = "الرابط piper موجود لكن هدفه مفقود — الكشف عمل كما هو متوقع."
    else:
        detail = "لم يُكشف كسر الرابط piper كما هو متوقع."
    return detected, detail


def _drill_pillow_old(workdir):
    """حاكِ Pillow قديمة: حلّل "10.2.0" وقارنها بالحد الأدنى 13."""
    version_text = "10.2.0"
    version = _parse_version(version_text)
    detected = version < _MIN_PILLOW_VERSION
    if detected:
        detail = "الإصدار %s أقدم من الحد الأدنى 13 — الكشف عمل كما هو متوقع." % version_text
    else:
        detail = "لم يُكشف قِدم الإصدار %s كما هو متوقع." % version_text
    return detected, detail


#: الأعطال المدمجة: id -> (title, simulated, drill function).
_DRILLS = {
    "missing-melt": (
        "غياب melt",
        "أُنشئ مجلد bin مؤقت فارغ وPATH بلا melt، ثم فُحص وجود melt.",
        _drill_missing_melt,
    ),
    "broken-piper-link": (
        "رابط piper مكسور",
        "أُنشئ رابط رمزي dangling باسم piper داخل مجلد العمل المؤقت.",
        _drill_broken_piper_link,
    ),
    "pillow-old": (
        "إصدار Pillow قديم",
        "حُلّلت سلسلة الإصدار الاصطناعية 10.2.0 وقُورنت بالحد الأدنى 13.",
        _drill_pillow_old,
    ),
}


def list_drills():
    """اسرد الأعطال المتاحة: ``[{"id", "title"}]``."""
    return [{"id": drill_id, "title": title}
            for drill_id, (title, _sim, _fn) in _DRILLS.items()]


def run_drill(drill_id, workdir=None, keep=False):
    """درّب على عطل معروف وأعد نتيجة التدريب.

    ``workdir`` مجلد عمل يُمرَّر (يبقى ملكًا للمتصل ولا يُحذف)،
    أو ``None`` فيُنشأ مجلد مؤقت ويُنظَّف بعد الانتهاء إلا إن
    طُلب الاحتفاظ به صراحة (``keep=True``).

    يعيد ``{"id", "title", "simulated", "detected", "status",
    "detail"}`` حيث ``status`` إما ``"pass"`` أو ``"fail"``.
    ``drill_id`` مجهول يرفع ``DrillError`` برسالة عربية.
    """
    try:
        title, simulated, func = _DRILLS[drill_id]
    except KeyError:
        known = ", ".join(sorted(_DRILLS))
        raise DrillError(
            "تدريب غير معروف: %s — الأعطال المتاحة: %s" % (drill_id, known)
        )
    owned = workdir is None
    if owned:
        workdir = tempfile.mkdtemp(prefix="failure-drill-")
    try:
        detected, detail = func(workdir)
    finally:
        if owned and not keep:
            shutil.rmtree(workdir, ignore_errors=True)
    return {
        "id": drill_id,
        "title": title,
        "simulated": simulated,
        "detected": bool(detected),
        "status": "pass" if detected else "fail",
        "detail": detail,
    }


def run_all_drills(workdir=None, keep=False):
    """شغّل كل الأعطال المدمجة وأعد النتائج مع ملخص.

    إن مُرّر ``workdir`` يُعطى كل drill مجلدًا فرعيًا خاصًا به
    داخله؛ وإن كان ``None`` أنشأ كل drill مجلده المؤقت الخاص.
    """
    results = []
    for drill_id in _DRILLS:
        subdir = None
        if workdir is not None:
            subdir = os.path.join(workdir, drill_id)
            os.makedirs(subdir, exist_ok=True)
        results.append(run_drill(drill_id, workdir=subdir, keep=keep))
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = len(results) - passed
    return {
        "drills": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "ok": failed == 0,
        },
    }
