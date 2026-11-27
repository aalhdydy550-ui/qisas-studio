#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""حزمة تصدير تشخيصية (بند 29، جولة v0.1.63).

أمر `studio.py export --job ID --out DIR` (يربطه عامل آخر)
يكتب حزمة واحدة قابلة للمشاركة لتشخيص فشل بدل نسخ ملفات
يدويًا: `manifest.json` + `job.json` + نصوص (≤2,000 رسالة
لكلٍّ)، وكل الأسرار منزوعة قبل الكتابة.

قواعد ثابتة:
- التنقيح عبر `redact_deep` من `lib.cli_output` (ع2) —
  باستيراد كسول داخل الدالة؛ وإن لم توجد الوحدة بعد
  (عامل آخر يبنيها بالتوازي) يرجع التنقيح إلى
  `lib.id_mask.redact_secrets` تكراريًا.
- الحدود: `--max-files 200` و`--max-bytes 500MB` (تُفحص
  قبل أي كتابة — لا حزمة جزئية).
- مجلد إخراج غير فارغ مرفوض إلا مع `--force`، و`--force`
  يحذف فقط ما يسرده `manifest.json` الموجود — أي ملف
  آخر في المجلد يُترك كما هو. وبلا `manifest.json` موجود
  يبقى الرفض حتى مع `--force` (لا شيء آمن لحذفه).
- كل الملفات المكتوبة 0600؛ والطوابع الزمنية Africa/Cairo.
"""
import hashlib
import json
import os

__all__ = [
    "ExportError", "MAX_FILES_DEFAULT", "MAX_BYTES_DEFAULT",
    "MAX_MESSAGES_PER_TEXT", "MANIFEST_FILENAME", "JOB_FILENAME",
    "redact_for_export", "read_manifest", "force_clean",
    "export_job",
]

# ─── الثوابت ───
MAX_FILES_DEFAULT = 200
MAX_BYTES_DEFAULT = 500 * 1024 * 1024  # 500MB
MAX_MESSAGES_PER_TEXT = 2000
MANIFEST_FILENAME = "manifest.json"
JOB_FILENAME = "job.json"
FILE_MODE = 0o600


class ExportError(Exception):
    """خطأ التصدير (حدّ مُتجاوَز، مجلد مرفوض، مصدر غائب...)."""


def _redact_fallback(obj):
    """تنقيح تكراري احتياطي عبر `lib.id_mask.redact_secrets`."""
    from lib.id_mask import redact_secrets
    if isinstance(obj, str):
        return redact_secrets(obj)
    if isinstance(obj, dict):
        return {key: _redact_fallback(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_redact_fallback(item) for item in obj]
    return obj


def redact_for_export(obj):
    """نقّح كائنًا للتصدير: `redact_deep` من `lib.cli_output` (ع2).

    استيراد كسول داخل الدالة لتجنّب الدورات؛ وعند غياب
    الوحدة (ما زالت تُبنى في هذه الجولة) يُستخدم التنقيح
    الاحتياطي من `lib.id_mask`. لا سرّ يغادر الآلة أبدًا.
    """
    try:
        from lib.cli_output import redact_deep
    except ImportError:
        return _redact_fallback(obj)
    return redact_deep(obj)


def _now_cairo_iso():
    """طابع زمني ISO بمنطقة Africa/Cairo (ع19)."""
    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Africa/Cairo")
    except Exception:
        from datetime import timezone, timedelta
        tz = timezone(timedelta(hours=2))
    return datetime.now(tz).isoformat(timespec="seconds")


def read_manifest(out_dir):
    """اقرأ `manifest.json` من مجلد؛ None إن غاب أو مشوّه."""
    path = os.path.join(out_dir, MANIFEST_FILENAME)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        if isinstance(manifest, dict) and isinstance(
                manifest.get("files"), list):
            return manifest
    except (ValueError, OSError):
        return None
    return None


def force_clean(out_dir):
    """احذف فقط ما يسرده `manifest.json` الموجود في المجلد.

    يرجع قائمة أسماء الملفات المحذوفة. أي ملف غير مسرود
    يُترك. يرفع `ExportError` إن لم يوجد manifest صالح.
    """
    manifest = read_manifest(out_dir)
    if manifest is None:
        raise ExportError(
            "لا يوجد %s صالح في %s — لا شيء آمن لحذفه"
            % (MANIFEST_FILENAME, out_dir))
    deleted = []
    for entry in manifest["files"]:
        name = entry.get("name") if isinstance(entry, dict) else None
        if not name or os.sep in name or name in (".", ".."):
            continue
        path = os.path.join(out_dir, name)
        if os.path.isfile(path):
            os.unlink(path)
            deleted.append(name)
    return deleted


def _check_out_dir(out_dir, force):
    """تحقق من مجلد الإخراج؛ ونظّفه مع --force أو ارفضه.

    مجلد غير فارغ مرفوض إلا مع `--force`؛ و`--force` يحذف
    فقط ما يسرده `manifest.json` (انظر `force_clean`).
    """
    if not os.path.isdir(out_dir):
        return
    entries = [name for name in os.listdir(out_dir)
               if not name.startswith(".")]
    if not entries:
        return
    if not force:
        raise ExportError(
            "مجلد الإخراج غير فارغ: %s — استخدم --force لمسح حزمة "
            "سابقة (يُحذف فقط ما يسرده %s)"
            % (out_dir, MANIFEST_FILENAME))
    force_clean(out_dir)
    remaining = [name for name in os.listdir(out_dir)
                 if not name.startswith(".") and name != MANIFEST_FILENAME]
    if remaining:
        raise ExportError(
            "مجلد الإخراج ما زال يحوي ملفات غير مسرودة في %s "
            "(%s) — امسحها يدويًا أو اختر مجلدًا آخر"
            % (MANIFEST_FILENAME, ", ".join(sorted(remaining))))


def _load_text_lines(source):
    """اقرأ مصدر نص: مسار ملف أو قائمة سطور؛ ارجع سطورًا منقحة.

    المصدر dict بـ`path` (ملف يُقرأ) أو `lines` (سطور
    جاهزة) أو `text` (نص واحد). يُقصّ إلى
    `MAX_MESSAGES_PER_TEXT` سطرًا (2,000 رسالة كحد أقصى).
    """
    if isinstance(source, dict) and "path" in source:
        path = source["path"]
        if not os.path.isfile(path):
            raise ExportError("ملف المصدر غير موجود: %s" % path)
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    elif isinstance(source, dict) and "lines" in source:
        lines = list(source["lines"])
    elif isinstance(source, dict) and "text" in source:
        lines = str(source["text"]).splitlines()
    else:
        raise ExportError("مصدر نص غير صالح: %r" % (source,))
    clipped = len(lines) > MAX_MESSAGES_PER_TEXT
    return [str(line) for line in lines[:MAX_MESSAGES_PER_TEXT]], clipped


def export_job(job, out_dir, sources=None, max_files=MAX_FILES_DEFAULT,
               max_bytes=MAX_BYTES_DEFAULT, force=False):
    """صدّر حزمة تشخيصية لمهمة إلى مجلد؛ ارجع الـmanifest.

    `job`: سجل المهمة (dict من `lib.job_registry`) — يُكتب
    منقحًا في `job.json`. `sources`: قائمة مصادر نص
    (dicts كما في `_load_text_lines`) تُكتب ملفًا لكلٍّ
    باسمها (`name`؛ افتراضيًا `log-N.txt`). `max_files` /
    `max_bytes`: حدّا الحزمة (200 / 500MB افتراضيًا).

    الحدود تُفحص قبل أي كتابة؛ وتجاوزها يرفع `ExportError`
    بلا ملف مكتوب. المجلد يُنشأ عند الحاجة.
    """
    if not isinstance(job, dict) or not job.get("job_id"):
        raise ExportError("سجل مهمة غير صالح: يحتاج `job_id`")
    if max_files is not None and max_files < 2:
        raise ExportError("حدّ الملفات صغير جدًا: %s" % max_files)
    if max_bytes is not None and max_bytes <= 0:
        raise ExportError("حدّ البايتات غير صالح: %s" % max_bytes)

    _check_out_dir(out_dir, force)
    os.makedirs(out_dir, exist_ok=True)

    # ─── بناء المحتوى المنقح كاملًا في الذاكرة أولًا ───
    planned = {}  # name -> bytes
    job_bytes = json.dumps(
        redact_for_export(job), ensure_ascii=False, indent=2
    ).encode("utf-8") + b"\n"
    planned[JOB_FILENAME] = job_bytes

    text_files = []
    for index, source in enumerate(sources or []):
        name = source.get("name") if isinstance(source, dict) else None
        name = name or "log-%d.txt" % (index + 1)
        if os.sep in name or name in (".", "..", MANIFEST_FILENAME,
                                      JOB_FILENAME):
            raise ExportError("اسم ملف مصدر غير صالح: %s" % name)
        lines, clipped = _load_text_lines(source)
        redacted_lines = [redact_for_export(line) for line in lines]
        if clipped:
            redacted_lines.append(
                "[... قُصّ عند %d رسالة]" % MAX_MESSAGES_PER_TEXT)
        text_files.append((name, "\n".join(redacted_lines) + "\n"))
    for name, text in text_files:
        if name in planned:
            raise ExportError("اسم ملف مكرر في الحزمة: %s" % name)
        planned[name] = text.encode("utf-8")

    # ─── فحص الحدود قبل الكتابة ───
    total_files = len(planned) + 1  # + manifest.json نفسه
    if max_files is not None and total_files > max_files:
        raise ExportError(
            "تجاوز حدّ الملفات: %d ملفًا (الحد %d)"
            % (total_files, max_files))
    total_bytes = sum(len(data) for data in planned.values())
    if max_bytes is not None and total_bytes > max_bytes:
        raise ExportError(
            "تجاوز حدّ البايتات: %d بايت (الحد %d)"
            % (total_bytes, max_bytes))

    # ─── الكتابة ───
    files_meta = []
    for name in sorted(planned):
        data = planned[name]
        path = os.path.join(out_dir, name)
        with open(path, "wb") as handle:
            handle.write(data)
        os.chmod(path, FILE_MODE)
        files_meta.append({
            "name": name,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    manifest = {
        "schema_version": 1,
        "job_id": job["job_id"],
        "exported_at": _now_cairo_iso(),
        "timezone": "Africa/Cairo",
        "limits": {"max_files": max_files, "max_bytes": max_bytes,
                   "max_messages_per_text": MAX_MESSAGES_PER_TEXT},
        "files": files_meta,
        "total_files": len(files_meta) + 1,
        # مجموع بايتات الملفات المسرودة (بلا manifest.json نفسه).
        "total_bytes": total_bytes,
    }
    manifest_path = os.path.join(out_dir, MANIFEST_FILENAME)
    with open(manifest_path, "wb") as handle:
        handle.write(json.dumps(
            manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    os.chmod(manifest_path, FILE_MODE)
    return manifest
