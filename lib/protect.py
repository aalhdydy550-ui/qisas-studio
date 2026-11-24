#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""أمر الحماية — جولة الحماية المرحلة 2 (بلا رفع نسخة).

يجمع في تقرير عربي واحد أربعة فحوصات قراءة فقط (لا حذف ولا
حجر صحي ولا تعديل لأي ملف):
1. سلامة الملفات — `integrity.py verify` من ~/workspace/protection/
2. صلاحيات الملفات — `perm-audit.py` من المجلد نفسه
3. مسح الأسرار — `lib/secret_guard.py` داخل الشجرة + تحقق .gitignore
4. آخر نسخة احتياطية — أحدث backup-*.zip في studio/backups/
   (موجودة + zip صالح + حديثة)

كل فحص يرجع قاموسًا بنفس شكل فحوصات doctor:
  {"name", "ok": True|False|None, "level": "error"|"warn",
   "detail", "fix"}
- ok=None تعني «غير متاح»: أداة خارجية غائبة (قد تُمسح أدوات
  ~/workspace/protection/ مع إعادة تشغيل VM أو تغيب في بيئة CI)
  — تُطبع ولا تُحتسب خطأً ولا تُفشل الأمر.
- level "warn": مشكلة غير حرجة (نسخة احتياطية قديمة مثلًا).

`run_fast_checks()` للاستخدام في doctor: الأسرار + النسخة
الاحتياطية فقط (بلا عمليات خارجية) فيبقى doctor سريعًا
ويعمل حتى بغياب أدوات الحماية الخارجية.
"""
import os
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone

from lib import secret_guard

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTECTION_DIR = os.path.join(os.path.expanduser("~"),
                              "workspace", "protection")
INTEGRITY_PY = os.path.join(PROTECTION_DIR, "integrity.py")
PERM_AUDIT_PY = os.path.join(PROTECTION_DIR, "perm-audit.py")
BASELINE_JSON = os.path.join(PROTECTION_DIR, "baseline.json")

BACKUP_DIR_NAME = "backups"
BACKUP_PREFIX = "backup-"
# نسخة أحدث من يومين = سليمة؛ أقدم = تحذير (الكرون اليومي 03:51).
BACKUP_MAX_AGE_DAYS = 2

# ------------------------------------------------------------------
# بوابة مخاطر كارثية مطلقة (جولة v0.1.41 — بند 4 من استخراج
# AlphaCLI، REPORT-AR.md §4.1، مقتبسة من
# src/alphacode_command_risk/gate.rs):
# طبقة Deny دائمة بلا مبرر يفتحها لمسارات التدمير الكارثية
# (rm -rf ~ و/etc وعقد الأجهزة)، وAllow لما عداها مع مطالبات
# إذن للخطِر. اعتراف صريح من المصدر نفسه ننقله كما هو:
# «هذا دفاع بالعمق لا sandbox» — البوابة تمنع الكارثي فقط،
# ولا تعزل التنفيذ ولا تحل محل نسخة احتياطية أو مراجعة.
# ------------------------------------------------------------------

class ProtectDeniedError(Exception):
    """رفض حذف مطلق من بوابة المخاطر الكارثية (رسالته عربية)."""


# جذور نظام يُرفض حذف أي شيء داخلها ("/" مطابق تمامًا فقط —
# فهي جذر كل شيء؛ أما الباقي فيُرفض الجذر نفسه وما تحته).
_CATASTROPHIC_TREES = ("/bin", "/boot", "/dev", "/etc", "/proc",
                       "/sbin", "/sys", "/usr")

# الطابور الحقيقي (المسار الافتراضي في config — يمرَّر المسار
# الفعلي عبر extra_protected عند اختلافه).
DEFAULT_PROTECTED_QUEUE = os.path.join(
    os.path.expanduser("~"), "workspace", "goals", "goal",
    "hidden_files", "story-queue-2026-11-20.md")


def _is_within(path, root):
    """True إن كان path هو root نفسه أو تحته (بعد الـresolve)."""
    path = os.path.realpath(path)
    root = os.path.realpath(root)
    return path == root or path.startswith(root + os.sep)


def deny_catastrophic(path, studio_dir=None, extra_protected=()):
    """True = يُرفض حذف هذا المسار رفضًا مطلقًا بلا استثناء.

    يُرفض: مسار فارغ/غير نصي (بلا معنى آمن)؛ المجلد الرئيسي
    ~ نفسه؛ ‎~/.ssh وما تحته؛ ‎/ وما تحته من جذور نظام
    (/etc و/dev — عقد الأجهزة — و/bin و/sbin و/usr و/boot
    و/proc و/sys)؛ وجذر الاستوديو نفسه؛ والمسارات المحمية
    في الاستوديو (مجلد الطابور queue/، ومجلد النسخ الاحتياطية
    backups/ وما تحته، وclient-orders/orders.jsonl ونسخته
    ‎.bad، وسجل المهام runs/jobs.jsonl، والطابور الحقيقي
    الافتراضي)؛ وأي مسار إضافي في extra_protected (ملف
    يُطابَق تمامًا، ومجلد يُطابَق هو وما تحته).

    الروابط الرمزية تُحلّ قبل الحكم (realpath) فلا يتجاوزها
    رابط يشير إلى مسار محمي. أي مسار آخر = False (مسموح،
    مع مطالبات الإذن المعتادة للخطِر خارج هذه الدالة).
    """
    if not isinstance(path, str) or not path.strip():
        return True
    target = os.path.realpath(os.path.expanduser(path.strip()))
    home = os.path.realpath(os.path.expanduser("~"))
    if target == home:
        return True
    if _is_within(target, os.path.join(home, ".ssh")):
        return True
    if target == os.sep:
        return True
    for root in _CATASTROPHIC_TREES:
        if _is_within(target, root):
            return True
    root = studio_dir or STUDIO_DIR
    studio = os.path.realpath(root)
    if target == studio:
        return True
    dir_trees = (os.path.join(studio, "queue"),
                 os.path.join(studio, "backups"))
    for tree in dir_trees:
        if _is_within(target, tree):
            return True
    exact_files = (
        os.path.join(studio, "client-orders", "orders.jsonl"),
        os.path.join(studio, "client-orders", "orders.jsonl.bad"),
        os.path.join(studio, "runs", "jobs.jsonl"),
        os.path.realpath(DEFAULT_PROTECTED_QUEUE),
    )
    if target in {os.path.realpath(p) for p in exact_files}:
        return True
    for extra in (extra_protected or ()):
        if isinstance(extra, str) and extra.strip():
            extra_path = os.path.realpath(
                os.path.expanduser(extra.strip()))
            if target == extra_path or (
                    os.path.isdir(extra_path)
                    and _is_within(target, extra_path)):
                return True
    return False


def safe_delete(path, studio_dir=None, extra_protected=()):
    """احذف ملفًا بعد بوابة المخاطر؛ ارجع True عند الحذف.

    يرفع ProtectDeniedError على أي مسار ترفضه
    deny_catastrophic، وFileNotFoundError على مسار غائب،
    وIsADirectoryError على مجلد (استخدم safe_rmtree له).
    """
    if deny_catastrophic(path, studio_dir=studio_dir,
                         extra_protected=extra_protected):
        raise ProtectDeniedError(
            "رفض مطلق: حذف المسار المحمي %s مرفوض دائمًا — "
            "بوابة المخاطر الكارثية (دفاع بالعمق لا sandbox)"
            % path)
    if not os.path.lexists(path):
        raise FileNotFoundError("الملف غير موجود: %s" % path)
    if os.path.isdir(path) and not os.path.islink(path):
        raise IsADirectoryError(
            "المسار مجلد لا ملف — استخدم safe_rmtree: %s" % path)
    os.remove(path)
    return True


def safe_rmtree(path, studio_dir=None, extra_protected=()):
    """احذف مجلدًا وشجرته بعد بوابة المخاطر؛ ارجع True.

    نفس الرفض المطلق في deny_catastrophic؛ ويرفض أيضًا
    حذف ملف عادي (استخدم safe_delete له).
    """
    if deny_catastrophic(path, studio_dir=studio_dir,
                         extra_protected=extra_protected):
        raise ProtectDeniedError(
            "رفض مطلق: حذف المسار المحمي %s مرفوض دائمًا — "
            "بوابة المخاطر الكارثية (دفاع بالعمق لا sandbox)"
            % path)
    if not os.path.lexists(path):
        raise FileNotFoundError("المجلد غير موجود: %s" % path)
    if os.path.islink(path) or not os.path.isdir(path):
        raise NotADirectoryError(
            "المسار ليس مجلدًا — استخدم safe_delete: %s" % path)
    shutil.rmtree(path)
    return True


_TOOL_TIMEOUT = 120


def _run_tool(script, args):
    """شغّل أداة حماية خارجية؛ ارجع (كود الخروج int أو None،
    stdout). None تعني: الأداة غائبة أو تعذّر تشغيلها أو انتهت
    المهلة أو خرجها غير رقمي (محاكاة في الاختبارات)."""
    if not os.path.isfile(script):
        return None, ""
    try:
        proc = subprocess.run(
            [sys.executable, script] + list(args),
            capture_output=True, text=True, timeout=_TOOL_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    rc = proc.returncode
    if not isinstance(rc, int):
        return None, ""
    return rc, proc.stdout or ""


def _counts_line(text):
    """استخرج سطر الخلاصة «معدَّلة X | محذوفة Y | جديدة Z» من
    خرج integrity verify (أو None)."""
    m = re.search(r"معدَّلة\s+(\d+)\s*\|\s*محذوفة\s+(\d+)"
                  r"\s*\|\s*جديدة\s+(\d+)", text)
    if not m:
        return None
    return "معدَّلة %s | محذوفة %s | جديدة %s" % m.groups()


def _sample_paths(text, limit=3):
    """أول مسارات «  - <مسار>» في خرج verify (للتقرير المختصر)."""
    paths = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- ") and line[2:].startswith("/"):
            paths.append(line[2:])
            if len(paths) >= limit:
                break
    return paths


def check_integrity(studio_dir=None):
    """سلامة الملفات مقابل أساس baseline.json."""
    name = "سلامة الملفات (integrity)"
    if not os.path.isfile(INTEGRITY_PY):
        return {"name": name, "ok": None, "level": "warn",
                "detail": "أداة السلامة غير موجودة: %s" % INTEGRITY_PY,
                "fix": "أعد بناء أدوات الحماية (انظر protection/README.md)"}
    if not os.path.isfile(BASELINE_JSON):
        return {"name": name, "ok": None, "level": "warn",
                "detail": "لا يوجد أساس بصمات: %s" % BASELINE_JSON,
                "fix": "ابنِ الأساس بـ `python3 integrity.py init`"}
    rc, out = _run_tool(INTEGRITY_PY, ["verify"])
    if rc is None:
        return {"name": name, "ok": None, "level": "warn",
                "detail": "تعذّر تشغيل مدقق السلامة (مهلة أو خطأ)",
                "fix": "شغّل `python3 integrity.py verify` يدويًا"}
    if rc == 0:
        return {"name": name, "ok": True, "level": "ok",
                "detail": "سليم — لا اختلافات عن الأساس",
                "fix": ""}
    if rc == 2:
        return {"name": name, "ok": False, "level": "error",
                "detail": "خطأ في الأساس (تالف أو غير مقروء) — أعد بناءه",
                "fix": "أعد بناء الأساس بـ `python3 integrity.py update`"}
    counts = _counts_line(out) or "يوجد اختلاف عن الأساس"
    detail = counts
    sample = _sample_paths(out)
    if sample:
        detail += " — مثال: " + "، ".join(sample)
    return {"name": name, "ok": False, "level": "error",
            "detail": detail,
            "fix": "راجع `python3 integrity.py verify` للقوائم "
                   "الكاملة، أو `update` بعد تغيير مقصود"}


def check_permissions():
    """صلاحيات الملفات (كتابة للجميع / أسرار بغير 600 /
    تغطية .gitignore)."""
    name = "صلاحيات الملفات (perm-audit)"
    if not os.path.isfile(PERM_AUDIT_PY):
        return {"name": name, "ok": None, "level": "warn",
                "detail": "أداة تدقيق الصلاحيات غير موجودة: %s"
                          % PERM_AUDIT_PY,
                "fix": "أعد بناء أدوات الحماية (انظر protection/README.md)"}
    rc, out = _run_tool(PERM_AUDIT_PY, [])
    if rc is None:
        return {"name": name, "ok": None, "level": "warn",
                "detail": "تعذّر تشغيل تدقيق الصلاحيات (مهلة أو خطأ)",
                "fix": "شغّل `python3 perm-audit.py` يدويًا"}
    if rc == 0:
        return {"name": name, "ok": True, "level": "ok",
                "detail": "سليم — لا كتابة للجميع ولا أسرار بصلاحية خاطئة",
                "fix": ""}
    problems = [line.strip() for line in out.splitlines()
                if re.match(r"\s*\d+\.\s+\[", line)][:3]
    detail = ("؛ ".join(problems) if problems
              else "توجد مشاكل صلاحيات — راجع perm-audit.py")
    return {"name": name, "ok": False, "level": "error",
            "detail": detail,
            "fix": "شغّل `python3 perm-audit.py` للتفاصيل الكاملة"}


def check_secrets(studio_dir=None):
    """مسح أسرار الشجرة + تحقق تغطية .gitignore (بلا قيم في التقرير
    أبدًا — الملف والسطر ونوع النمط فقط)."""
    root = studio_dir or STUDIO_DIR
    name = "مسح الأسرار (secret_guard)"
    missing = secret_guard.check_gitignore(root)
    if missing:
        return {"name": name, "ok": False, "level": "error",
                "detail": "فجوات في .gitignore: %s" % "، ".join(missing),
                "fix": "أضف الأنماط الناقصة إلى .gitignore"}
    findings = secret_guard.scan_tree(root)
    if findings:
        shown = ["%s:%d (%s)" % (f["file"], f["line"], f["pattern"])
                 for f in findings[:3]]
        detail = "%d إصابة — مثال: %s" % (len(findings),
                                          "، ".join(shown))
        return {"name": name, "ok": False, "level": "error",
                "detail": detail,
                "fix": "أزل السر من الملف أو أضفه إلى .gitignore "
                       "إن كان ملف أسرار حقيقيًا"}
    return {"name": name, "ok": True, "level": "ok",
            "detail": "نظيف — 0 إصابة، و.gitignore يغطي ملفات الأسرار",
            "fix": ""}


def check_backup(studio_dir=None):
    """آخر نسخة احتياطية: موجودة + zip صالح + حديثة (≤ يومين)."""
    root = studio_dir or STUDIO_DIR
    name = "آخر نسخة احتياطية"
    backup_dir = os.path.join(root, BACKUP_DIR_NAME)
    if not os.path.isdir(backup_dir):
        return {"name": name, "ok": False, "level": "warn",
                "detail": "لا يوجد مجلد نسخ احتياطية بعد: %s" % backup_dir,
                "fix": "شغّل `python3 studio.py backup`"}
    candidates = []
    for fname in os.listdir(backup_dir):
        if fname.startswith(BACKUP_PREFIX) and fname.endswith(".zip"):
            path = os.path.join(backup_dir, fname)
            if os.path.isfile(path):
                candidates.append(path)
    if not candidates:
        return {"name": name, "ok": False, "level": "error",
                "detail": "لا توجد أي نسخة احتياطية في %s" % backup_dir,
                "fix": "شغّل `python3 studio.py backup`"}
    latest = max(candidates, key=os.path.getmtime)
    if not zipfile.is_zipfile(latest):
        return {"name": name, "ok": False, "level": "error",
                "detail": "أحدث نسخة تالفة (ليست zip صالحًا): %s" % latest,
                "fix": "احذفها وشغّل `python3 studio.py backup`"}
    try:
        with zipfile.ZipFile(latest) as zf:
            if zf.testzip() is not None:
                return {"name": name, "ok": False, "level": "error",
                        "detail": "أحدث نسخة تالفة (ملف داخلي معطوب): %s"
                                 % latest,
                        "fix": "احذفها وشغّل `python3 studio.py backup`"}
    except zipfile.BadZipFile:
        return {"name": name, "ok": False, "level": "error",
                "detail": "أحدث نسخة تالفة (لا تُفتح): %s" % latest,
                "fix": "احذفها وشغّل `python3 studio.py backup`"}
    age_days = ((datetime.now(timezone.utc).timestamp()
                 - os.path.getmtime(latest)) / 86400.0)
    if age_days <= BACKUP_MAX_AGE_DAYS:
        return {"name": name, "ok": True, "level": "ok",
                "detail": "أحدث نسخة %s (عمرها %.1f ساعة)"
                          % (os.path.basename(latest), age_days * 24),
                "fix": ""}
    return {"name": name, "ok": False, "level": "warn",
            "detail": "أحدث نسخة قديمة (عمرها %.1f يوم): %s"
                      % (age_days, os.path.basename(latest)),
            "fix": "شغّل `python3 studio.py backup` أو تحقق من كرون "
                   "النسخ اليومي"}


def run_all(studio_dir=None):
    """كل فحوصات الحماية الأربعة بالترتيب."""
    return [check_integrity(studio_dir),
            check_permissions(),
            check_secrets(studio_dir),
            check_backup(studio_dir)]


def run_fast_checks(studio_dir=None):
    """المجموعة السريعة بلا عمليات خارجية (لـ doctor):
    الأسرار + النسخة الاحتياطية."""
    return [check_secrets(studio_dir),
            check_backup(studio_dir)]


def format_report(results):
    """نص التقرير العربي + (عدد الأخطاء، عدد التحذيرات)."""
    lines = []
    errors = warnings = 0
    for c in results:
        if c["ok"] is True:
            lines.append("[PASS] %s — %s" % (c["name"], c["detail"]))
        elif c["ok"] is None:
            lines.append("[غير متاح] %s — %s" % (c["name"], c["detail"]))
        elif c["level"] == "error":
            errors += 1
            line = "[FAIL] %s — %s" % (c["name"], c["detail"])
            if c.get("fix"):
                line += "  ← %s" % c["fix"]
            lines.append(line)
        else:
            warnings += 1
            line = "[WARN] %s — %s" % (c["name"], c["detail"])
            if c.get("fix"):
                line += "  ← %s" % c["fix"]
            lines.append(line)
    if errors:
        lines.append("النتيجة: %d خطأ أساسي، %d تحذير — أصلح الأخطاء "
                     "قبل أي رفع" % (errors, warnings))
    elif warnings:
        lines.append("النتيجة: لا أخطاء أساسية، %d تحذير — راجعها "
                     "عند أول فرصة" % warnings)
    else:
        lines.append("النتيجة: كل فحوصات الحماية سليمة")
    return "\n".join(lines), errors, warnings
