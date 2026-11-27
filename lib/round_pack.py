#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""صيغة «حزمة جولة» — جولة v0.1.63 (بند 11، عقد ع15).

ملف `.md` واحد لكل جولة: واجهة YAML أمامية + جسم مقروء يحمل
التغييرات والملفات والاختبارات، مع تنظيف أي قيمة بشكل السرّ
وعدّها. الحزمة لا تحمل أبدًا: بيانات اعتماد أو محادثات أو
أذونات أو ذاكرة أو وصول تنفيذ.

الحدود (ع15):
- نص فقط، ≤30 ملفًا، ≤128KB لكل ملف، ≤512KB إجمالًا، ≤6 مجلدات عمقًا.
- بلا ملفات مخفية ولا `node_modules` ولا `__pycache__` ولا venv
  ولا ثنائيات ولا ملفات بأسماء مفاتيح.
- حدود الاستيراد: 1MB للملف، 4MB/300 ملف.
- نسخة `.previous` عند الاستبدال؛ وروتينات الحزمة تصل متوقفة.
"""
import hashlib
import os
import re

__all__ = [
    "PackError",
    "MAX_FILES",
    "MAX_FILE_BYTES",
    "MAX_TOTAL_BYTES",
    "MAX_DEPTH",
    "IMPORT_MAX_FILE_BYTES",
    "IMPORT_MAX_TOTAL_BYTES",
    "IMPORT_MAX_FILES",
    "count_secrets",
    "scrub_text",
    "validate_pack_files",
    "export_pack",
    "import_pack",
    "review_pack",
    "parse_pack",
]

MAX_FILES = 30
MAX_FILE_BYTES = 128 * 1024
MAX_TOTAL_BYTES = 512 * 1024
MAX_DEPTH = 6
IMPORT_MAX_FILE_BYTES = 1024 * 1024
IMPORT_MAX_TOTAL_BYTES = 4 * 1024 * 1024
IMPORT_MAX_FILES = 300

# مقاطع مسار مرفوضة أبدًا في الحزمة: أسرار أو محادثات أو أذونات
# أو ذاكرة أو وصول تنفيذ — الحزمة لا تحمل أيًا منها.
_FORBIDDEN_SEGMENTS = (
    ".env",
    "credentials",
    "secrets",
    "memory",
    "conversations",
    "permissions",
    "tokens",
    "private",
)
_FORBIDDEN_DIR_NAMES = (
    "node_modules",
    "__pycache__",
    "venv",
    ".venv",
    ".git",
    "site-packages",
)
_KEY_NAME_RES = (
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"password|passwd", re.IGNORECASE),
    re.compile(r"private[_-]?key", re.IGNORECASE),
    re.compile(r"access[_-]?token", re.IGNORECASE),
)
# أنماط قيم شبيهة بالأسرار داخل النصوص (تُستبدل وتُعَدّ).
_SECRET_RES = (
    re.compile(r"Bearer\s+\S+"),
    re.compile(
        r"(?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{8,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
)

_REDACTED = "[REDACTED]"


class PackError(Exception):
    """خطأ في حزمة جولة (رسالته عربية)."""


def count_secrets(text):
    """عدد القيم شبيهة بالأسرار في نص (بلا تعديل)."""
    if not text:
        return 0
    return sum(len(pattern.findall(text)) for pattern in _SECRET_RES)


def scrub_text(text):
    """يستبدل القيم شبيهة بالأسرار ويعيد (النص النظيف، العدد).

    الاستبدال نهائي لا عكسي: القيمة الأصلية لا تعود.
    """
    if not text:
        return "", 0
    total = 0
    cleaned = text
    for pattern in _SECRET_RES:
        cleaned, n = pattern.subn(_REDACTED, cleaned)
        total += n
    return cleaned, total


def _is_binary(data):
    """نصي أم ثنائي؟ بايت NUL أو فشل فك UTF-8 يعني ثنائيًا."""
    if b"\x00" in data:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def _check_rel_path(rel_path):
    """أخطاء مسار نسبي واحد (فارغة إن كان مقبولًا)."""
    errors = []
    parts = rel_path.replace("\\", "/").split("/")
    if rel_path.startswith("/") or ".." in parts:
        errors.append("مسار خارج الحزمة: %s" % rel_path)
        return errors
    if any(part.startswith(".") for part in parts):
        errors.append("ملف مخفي مرفوض: %s" % rel_path)
    if len(parts) > MAX_DEPTH:
        errors.append(
            "عمق %d يتجاوز الحد %d: %s" % (len(parts), MAX_DEPTH, rel_path)
        )
    lowered = [part.lower() for part in parts]
    if any(name in lowered for name in _FORBIDDEN_DIR_NAMES):
        errors.append("مجلد مرفوض في المسار: %s" % rel_path)
    if any(seg in lowered for seg in _FORBIDDEN_SEGMENTS):
        errors.append("مسار محظور في الحزمة (أسرار/ذاكرة/أذونات): %s" % rel_path)
    name = parts[-1].lower()
    if any(pattern.search(name) for pattern in _KEY_NAME_RES):
        errors.append("اسم ملف بشكل مفتاح مرفوض: %s" % rel_path)
    return errors


def validate_pack_files(pack_dir, rel_paths):
    """يتحقق من قائمة ملفات قبل التصدير ويعيد قائمة أخطاء.

    يفحص الحدود (العدد والحجم الإجمالي وحجم كل ملف والعمق)
    والمسارات المرفوضة والمحتوى الثنائي. قائمة فارغة تعني القبول.
    """
    errors = []
    if len(rel_paths) > MAX_FILES:
        errors.append(
            "عدد الملفات %d يتجاوز الحد %d" % (len(rel_paths), MAX_FILES)
        )
    total = 0
    for rel_path in rel_paths:
        errors.extend(_check_rel_path(rel_path))
        full = os.path.join(pack_dir, rel_path)
        if not os.path.isfile(full):
            errors.append("ملف غير موجود: %s" % rel_path)
            continue
        size = os.path.getsize(full)
        total += size
        if size > MAX_FILE_BYTES:
            errors.append(
                "ملف %s حجمه %d بايت يتجاوز الحد %d"
                % (rel_path, size, MAX_FILE_BYTES)
            )
        try:
            with open(full, "rb") as fh:
                head = fh.read(8192)
        except OSError as exc:
            errors.append("تعذر قراءة %s: %s" % (rel_path, exc))
            continue
        if _is_binary(head):
            errors.append("ملف ثنائي مرفوض: %s" % rel_path)
    if total > MAX_TOTAL_BYTES:
        errors.append(
            "الحجم الإجمالي %d بايت يتجاوز الحد %d"
            % (total, MAX_TOTAL_BYTES)
        )
    return errors


def _fence_for(text):
    """سياج كود أطول من أي سياج داخل النص (حتى لا ينكسر التحليل)."""
    longest = 0
    for match in re.finditer(r"`+", text):
        longest = max(longest, len(match.group(0)))
    return "`" * max(3, longest + 1)


def _front_matter(meta):
    """واجهة YAML أمامية — الاستيراد كسول حتى لا تُفرض yaml عند القراءة."""
    import yaml

    return yaml.safe_dump(
        meta, allow_unicode=True, sort_keys=False, default_flow_style=False
    )


def export_pack(pack_dir, rel_paths, *, name, version, changes,
                tests, out_path, routines_stopped=True):
    """يصدّر حزمة جولة إلى ملف `.md` واحد ويعيد ملخصًا.

    `changes` و`tests` قوائم نصية (سطور الجسم المقروء). الأسرار
    في أي محتوى تُستبدل وتُعَدّ في الواجهة الأمامية. روتينات
    الحزمة تُسجَّل متوقفة دائمًا (لا روتين نشط يسافر في حزمة).
    """
    errors = validate_pack_files(pack_dir, rel_paths)
    if errors:
        raise PackError("الحزمة مرفوضة: " + "؛ ".join(errors))
    if not name or not str(name).strip():
        raise PackError("اسم الحزمة مطلوب.")
    files = []
    total_bytes = 0
    secrets_scrubbed = 0
    for rel_path in rel_paths:
        full = os.path.join(pack_dir, rel_path)
        with open(full, encoding="utf-8") as fh:
            content = fh.read()
        cleaned, n = scrub_text(content)
        secrets_scrubbed += n
        size = len(cleaned.encode("utf-8"))
        total_bytes += size
        files.append({"path": rel_path.replace("\\", "/"), "content": cleaned})
    meta = {
        "pack": str(name).strip(),
        "version": str(version),
        "files": len(files),
        "total_bytes": total_bytes,
        "secrets_scrubbed": secrets_scrubbed,
        "routines_stopped": bool(routines_stopped),
    }
    lines = ["---", _front_matter(meta).rstrip(), "---", ""]
    lines.append("# حزمة جولة: %s" % meta["pack"])
    lines.append("")
    lines.append("## التغييرات")
    lines.append("")
    for change in changes or []:
        cleaned_change, n = scrub_text(str(change))
        secrets_scrubbed += n
        lines.append("- %s" % cleaned_change)
    if not changes:
        lines.append("- (لا تغييرات موثقة)")
    lines.append("")
    lines.append("## الاختبارات")
    lines.append("")
    for test in tests or []:
        cleaned_test, n = scrub_text(str(test))
        secrets_scrubbed += n
        lines.append("- %s" % cleaned_test)
    if not tests:
        lines.append("- (لا اختبارات موثقة)")
    lines.append("")
    lines.append("## الملفات")
    lines.append("")
    for entry in files:
        fence = _fence_for(entry["content"])
        lines.append("### `%s`" % entry["path"])
        lines.append("")
        lines.append(fence)
        lines.append(entry["content"])
        lines.append(fence)
        lines.append("")
    # العدد النهائي يشمل ما في الجسم أيضًا.
    meta["secrets_scrubbed"] = secrets_scrubbed
    lines[1] = _front_matter(meta).rstrip()
    text = "\n".join(lines)
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return {
        "path": os.path.abspath(out_path),
        "pack": meta["pack"],
        "version": meta["version"],
        "files": len(files),
        "total_bytes": total_bytes,
        "secrets_scrubbed": secrets_scrubbed,
    }


def parse_pack(pack_path):
    """يحلّل ملف حزمة ويعيد (الواجهة الأمامية، قائمة الملفات، الجسم).

    قائمة الملفات عناصرها `{"path": ..., "content": ...}`.
    """
    try:
        with open(pack_path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise PackError("تعذر قراءة الحزمة: %s" % exc)
    if not text.startswith("---\n"):
        raise PackError("الحزمة بلا واجهة YAML أمامية.")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise PackError("واجهة YAML الأمامية غير مغلقة.")
    import yaml

    try:
        meta = yaml.safe_load(text[4:end]) or {}
    except Exception as exc:  # yaml.YAMLError وأشباهها
        raise PackError("واجهة YAML غير صالحة: %s" % exc)
    if not isinstance(meta, dict):
        raise PackError("واجهة YAML يجب أن تكون قاموسًا.")
    body = text[end + 5:]
    files = []
    pattern = re.compile(
        r"^### `([^`]+)`\s*\n\s*\n(`+)\n(.*?)\n\2\s*$",
        re.MULTILINE | re.DOTALL,
    )
    for match in pattern.finditer(body):
        files.append({"path": match.group(1), "content": match.group(3)})
    return meta, files, body


def review_pack(pack_path):
    """شاشة مراجعة قبل الإنشاء/الاستيراد: تحقق بلا كتابة.

    يعيد قاموسًا فيه `ok` و`errors` و`warnings` وملخصًا بشريًا
    (`summary_lines`) وعدد الأسرار المتبقية (يجب أن يكون صفرًا).
    """
    errors = []
    warnings = []
    try:
        meta, files, _body = parse_pack(pack_path)
    except PackError as exc:
        return {
            "ok": False,
            "errors": [str(exc)],
            "warnings": [],
            "summary_lines": ["الحزمة مرفوضة: %s" % exc],
            "secrets_remaining": 0,
        }
    if not meta.get("pack"):
        errors.append("الواجهة بلا اسم حزمة.")
    if len(files) > MAX_FILES:
        errors.append("عدد الملفات %d يتجاوز الحد %d" % (len(files), MAX_FILES))
    if len(files) > IMPORT_MAX_FILES:
        errors.append(
            "عدد الملفات %d يتجاوز حد الاستيراد %d"
            % (len(files), IMPORT_MAX_FILES)
        )
    total = 0
    secrets_remaining = 0
    for entry in files:
        errors.extend(_check_rel_path(entry["path"]))
        size = len(entry["content"].encode("utf-8"))
        total += size
        if size > IMPORT_MAX_FILE_BYTES:
            errors.append(
                "ملف %s حجمه %d بايت يتجاوز حد الاستيراد %d"
                % (entry["path"], size, IMPORT_MAX_FILE_BYTES)
            )
        secrets_remaining += count_secrets(entry["content"])
    if total > IMPORT_MAX_TOTAL_BYTES:
        errors.append(
            "الحجم الإجمالي %d بايت يتجاوز حد الاستيراد %d"
            % (total, IMPORT_MAX_TOTAL_BYTES)
        )
    if secrets_remaining:
        errors.append(
            "الحزمة تحمل %d قيمة بشكل سرّ — الأسرار لا تسافر أبدًا"
            % secrets_remaining
        )
    if meta.get("secrets_scrubbed"):
        warnings.append(
            "نُظّفت %d قيمة بشكل سرّ عند التصدير" % meta["secrets_scrubbed"]
        )
    if not meta.get("routines_stopped", True):
        warnings.append("روتينات الحزمة غير موسومة متوقفة.")
    lines = [
        "حزمة: %s (الإصدار %s)" % (meta.get("pack"), meta.get("version")),
        "الملفات: %d — الحجم: %d بايت" % (len(files), total),
        "أسرار نُظّفت عند التصدير: %s" % meta.get("secrets_scrubbed", 0),
        "الروتينات متوقفة: %s" % ("نعم" if meta.get("routines_stopped", True) else "لا"),
    ]
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary_lines": lines,
        "secrets_remaining": secrets_remaining,
        "meta": meta,
        "files": [entry["path"] for entry in files],
        "total_bytes": total,
    }


def import_pack(pack_path, dest_dir, *, allow_overwrite=False):
    """يستورد حزمة بعد مراجعتها ويعيد ملخصًا.

    ملف موجود يُستبدل تُحفظ نسخته أولًا بامتداد `.previous`.
    بلا `allow_overwrite` يُرفض الاستبدال. أي خطأ مراجعة يرفض
    الاستيراد كله قبل كتابة أي ملف.
    """
    review = review_pack(pack_path)
    if not review["ok"]:
        raise PackError("الاستيراد مرفوض: " + "؛ ".join(review["errors"]))
    _meta, files, _body = parse_pack(pack_path)
    dest_dir = os.path.abspath(dest_dir)
    written = []
    backed_up = []
    for entry in files:
        rel_path = entry["path"]
        target = os.path.join(dest_dir, rel_path)
        if os.path.isfile(target):
            if not allow_overwrite:
                raise PackError(
                    "ملف موجود وبلا إذن استبدال: %s" % rel_path
                )
            previous = target + ".previous"
            with open(target, "rb") as src:
                data = src.read()
            with open(previous, "wb") as dst:
                dst.write(data)
            backed_up.append(rel_path + ".previous")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(entry["content"])
        written.append(rel_path)
    return {
        "pack": review["meta"].get("pack"),
        "version": review["meta"].get("version"),
        "files": written,
        "backed_up": backed_up,
        "total_bytes": review["total_bytes"],
        "secrets_scrubbed": review["meta"].get("secrets_scrubbed", 0),
    }


def pack_sha256(pack_path):
    """بصمة ملف الحزمة (للمراجعة والمقارنة)."""
    digest = hashlib.sha256()
    with open(pack_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
