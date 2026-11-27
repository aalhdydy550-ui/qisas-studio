#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""الحارس (Sentinel) — فاحص صحة يقرأ فقط ويجمّع الأعطال (بند 16، جولة v0.1.63).

فاحص دوري اختياري يقرأ `runs/jobs.jsonl` وسجلات التشغيل **قراءة
فقط** (SQLite بـ`mode=ro` أبدًا `immutable`)، ويجمّع الفشل في
قضايا بتوقيعات مستقرة، ويكتب `issues.jsonl` و`state.json` في
مجلده الخاص خارج مجلد البيانات.

قواعد الخصوصية (ع14):
- التوقيع `sig` = تجزئة (اسم الأداة + الخطأ **المُطبَّع** بعد
  استبدال مسارات/أرقام/UUIDs/URLs/بريد/قيم مقتبسة) — فيصير
  «no layer 12» و«no layer 104» قضية واحدة.
- العنوان سطر مُطبَّع ≤160 حرفًا؛ والمخرجات الخام **لا تُخزَّن
  أبدًا** في أي قضية.
- المجلد 0700 وملفاته 0600؛ ويرفض `--out` داخل مجلد البيانات
  أو داخل مستودع git.
- حين لا يتغير أي ملف مصدر منذ التشغيل الأخير، لا يقرأ أي صف
  ولا يعمل شيئًا، ويخرج 0 مع ملخص.

أمر صدفة فاشل يُجمَّع بخشونة أكبر: برمز خروجه وفئة خطأ
(`timed out`، `command not found`، `syntax error`،
`no such file`، `permission denied`…) لا بما طبعه؛ والمهلة
تتجاهل رمز الخروج.
"""
import hashlib
import json
import os
import re
import sqlite3
import stat

__all__ = [
    "SentinelError", "TITLE_MAX_LEN", "WINDOW_SECONDS",
    "DEFAULT_STATE_DIRNAME", "ISSUES_FILENAME", "STATE_FILENAME",
    "normalize_error", "classify_error", "make_sig", "make_title",
    "validate_out_dir", "read_sqlite_ro", "scan_jobs_file",
    "scan_log_file", "run_sentinel",
]

# ─── الثوابت ───
TITLE_MAX_LEN = 160
WINDOW_SECONDS = 1800  # نافذة إعادة القراءة: آخر 30 دقيقة.
DEFAULT_STATE_DIRNAME = "qisas-studio-sentinel"
ISSUES_FILENAME = "issues.jsonl"
STATE_FILENAME = "state.json"
STATE_DIR_MODE = 0o700
STATE_FILE_MODE = 0o600

# فئات خشونة أمر الصدفة الفاشل (تُستخدم بدل نص الخطأ في التوقيع).
COMMAND_ERROR_CATEGORIES = (
    ("timed out", ("timed out", "timeout", "timed-out", "مهلة")),
    ("command not found", ("command not found", "not found", "no such command")),
    ("syntax error", ("syntax error", "invalid syntax")),
    ("no such file", ("no such file", "no such file or directory", "file not found")),
    ("permission denied", ("permission denied", "operation not permitted")),
    ("connection failed", ("connection refused", "connection failed", "network is unreachable")),
)

_SEVERITY_BY_CATEGORY = {
    "timed out": "high",
    "permission denied": "high",
    "connection failed": "high",
}

# أنماط التطبيع: تُستبدل قبل التجزئة فتستقر التوقيعات.
_PATH_RE = re.compile(r"(?:/[A-Za-z0-9._~+%-]+)+/?")
_WIN_PATH_RE = re.compile(r"[A-Za-z]:\\(?:[^\\s\"']+\\)*[^\\s\"']*")
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"")
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_WS_RE = re.compile(r"\s+")


class SentinelError(Exception):
    """خطأ الحارس (إخراج مرفوض، مصدر غير مقروء...)."""


def normalize_error(text):
    """طبّع نص خطأ قبل التجزئة: استبدل كل قيمة متغيرة بعلامة.

    الأسرار أولًا (عبر `lib.id_mask.redact_secrets`)، ثم
    مسارات → `<path>`، أرقام → `<n>`، UUIDs → `<uuid>`،
    URLs → `<url>`، بريد → `<email>`، قيم مقتبسة → `<value>`،
    ومسافات متعددة → مسافة واحدة، مع قصّ الفراغات.
    """
    if not text:
        return ""
    # الأسرار أولًا (استيراد كسول): قيمة سرّ عارية لا تُخزَّن
    # في عنوان ولا تدخل في توقيع أبدًا.
    try:
        from lib.id_mask import redact_secrets
        out = redact_secrets(str(text))
    except ImportError:
        out = str(text)
    out = _URL_RE.sub("<url>", out)
    out = _EMAIL_RE.sub("<email>", out)
    out = _WIN_PATH_RE.sub("<path>", out)
    out = _PATH_RE.sub("<path>", out)
    out = _UUID_RE.sub("<uuid>", out)
    out = _QUOTED_RE.sub("<value>", out)
    out = _NUMBER_RE.sub("<n>", out)
    out = _WS_RE.sub(" ", out).strip()
    return out


def classify_error(text, exit_code=None):
    """صنّف خطأ في فئة خشونة (لأوامر الصدفة خاصة).

    المهلة تتجاهل رمز الخروج: أي خطأ يحمل «timed out» فئته
    `timed out` مهما كان رمز الخروج. بلا تطابق يرجع `unknown`.
    """
    lowered = (text or "").lower()
    for category, markers in COMMAND_ERROR_CATEGORIES:
        if any(marker in lowered for marker in markers):
            return category
    if exit_code is not None and exit_code != 0:
        return "exit_%d" % exit_code
    return "unknown"


def make_sig(tool, normalized_error, exit_code=None, coarse=False):
    """اصنع توقيع قضية مستقرًا: `tool_error:<sha256[:16]>`.

    `coarse=True` (أمر صدفة): التجزئة على (الأداة + فئة الخطأ
    + رمز الخروج) لا على نص الخطأ. والمهلة تتجاهل رمز الخروج.
    """
    tool = tool or "unknown"
    if coarse:
        category = classify_error(normalized_error, exit_code)
        code_part = "" if category == "timed out" else str(exit_code or 0)
        material = "%s|%s|%s" % (tool, category, code_part)
        prefix = "command_error"
    else:
        material = "%s|%s" % (tool, normalized_error or "")
        prefix = "tool_error"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
    return "%s:%s" % (prefix, digest)


def make_title(tool, normalized_error):
    """عنوان قضية: سطر مُطبَّع واحد ≤160 حرفًا، بلا محتوى خام."""
    base = "%s: %s" % (tool or "unknown", normalized_error or "خطأ غير معروف")
    base = _WS_RE.sub(" ", base).strip()
    if len(base) > TITLE_MAX_LEN:
        base = base[:TITLE_MAX_LEN - 1].rstrip() + "…"
    return base


def _is_within(child, parent):
    child = os.path.realpath(child)
    parent = os.path.realpath(parent)
    return child == parent or child.startswith(parent + os.sep)


def _inside_git_repo(path):
    """True إن كان المسار داخل مستودع git (صعودًا حتى الجذر)."""
    current = os.path.realpath(path)
    while True:
        if os.path.isdir(os.path.join(current, ".git")):
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


def validate_out_dir(out_dir, data_dir):
    """ارفض مجلد إخراج داخل مجلد البيانات أو داخل مستودع git.

    يرجع المسار المطلق بعد التحقق؛ ويرفع `SentinelError` عند
    الرفض (رسالة عربية تشرح السبب).
    """
    out_abs = os.path.abspath(out_dir)
    if data_dir:
        data_abs = os.path.abspath(data_dir)
        if _is_within(out_abs, data_abs):
            raise SentinelError(
                "مجلد الإخراج داخل مجلد البيانات مرفوض: %s (البيانات: %s)"
                % (out_abs, data_abs))
    if _inside_git_repo(out_abs):
        raise SentinelError(
            "مجلد الإخراج داخل مستودع git مرفوض: %s" % out_abs)
    return out_abs


def read_sqlite_ro(path, query, params=()):
    """اقرأ SQLite قراءة فقط (`mode=ro` أبدًا `immutable`).

    `mode=ro` يرى ملف `-wal` وأحدث الصفوف؛ و`immutable` كان
    سيتجاهلها. الاستعلام قصير والمقبض يُغلق فورًا. يرجع قائمة
    صفوف (tuples). يرفع `SentinelError` عند غياب الملف.
    """
    if not os.path.isfile(path):
        raise SentinelError("ملف قاعدة البيانات غير موجود: %s" % path)
    uri = "file:%s?mode=ro" % os.path.abspath(path).replace("?", "%3F")
    conn = sqlite3.connect(uri, uri=True, timeout=5.0)
    try:
        cur = conn.execute(query, params)
        return cur.fetchall()
    finally:
        conn.close()


def _issue_from_failure(tool, error_text, origin, source_id,
                        first_at, last_at, exit_code=None, coarse=False,
                        extra=None):
    """ابنِ سجل قضية من فشل واحد (بلا أي محتوى خام)."""
    normalized = normalize_error(error_text)
    sig = make_sig(tool, normalized, exit_code=exit_code, coarse=coarse)
    category = classify_error(normalized, exit_code)
    severity = _SEVERITY_BY_CATEGORY.get(category, "medium")
    issue = {
        "sig": sig,
        "kind": "command_error" if coarse else "tool_error",
        "title": make_title(tool, normalized),
        "origin": origin,
        "severity": severity,
        "tool": tool,
        "botId": None,
        "threadId": None,
        "turnId": None,
        "firstAt": first_at,
        "lastAt": last_at,
        "count": 1,
        "wastedTurns": 1,
        "evidenceRef": {"source": origin, "id": str(source_id)},
    }
    if extra:
        for key in ("botId", "threadId", "turnId"):
            if key in extra and extra[key] is not None:
                issue[key] = str(extra[key])
    return issue


def scan_jobs_file(path, seen_ids=None):
    """افحص `runs/jobs.jsonl` قراءة فقط؛ اجمع المهام الفاشلة.

    كل سطر فاشل (`status` في failed/cancelled مع `error`، أو
    `error` غير فارغ) يصير قضية. `seen_ids`: مجموعة معرّفات
    سُجّلت سابقًا — تُتخطى (العدّ يبقى في القضية القائمة عبر
    `count`). يرجع (قضايا جديدة، معرّفات مقروءة).
    """
    issues = []
    read_ids = set()
    if not os.path.isfile(path):
        return issues, read_ids
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            job_id = str(record.get("job_id") or record.get("id") or "")
            if not job_id:
                continue
            read_ids.add(job_id)
            error = record.get("error")
            status = record.get("status")
            if not error and status not in ("failed", "cancelled"):
                continue
            if seen_ids is not None and job_id in seen_ids:
                continue
            tool = record.get("kind") or record.get("tool") or "job"
            first_at = record.get("finished_at") or record.get("started_at")
            issues.append(_issue_from_failure(
                tool, error or "فشل بلا رسالة خطأ", "jobs",
                job_id, first_at, first_at,
                extra={"threadId": record.get("story")}))
    return issues, read_ids


# سطر سجل يُعدّ خطأً إن احتوى أحد هذه الماركات (case-insensitive).
_LOG_ERROR_MARKERS = ("error", "failed", "failure", "traceback", "خطأ", "فشل")


def scan_log_file(path, offset=0, seen_ids=None):
    """افحص ملف سجل نصي من إزاحة بايت؛ اجمع سطور الأخطاء.

    تُقرأ السطور من `offset` فقط؛ وكل سطر خطأ يُجمَّع قضية
    بتوقيعه. يرجع (قضايا جديدة، الإزاحة الجديدة بالبايت،
    معرّفات مقروءة). الإزاحة تُصفَّر من المتصل حين يصغر الملف
    أو يتغير inode (انظر `run_sentinel`).
    """
    issues = []
    read_ids = set()
    if not os.path.isfile(path):
        return issues, offset, read_ids
    with open(path, "rb") as handle:
        handle.seek(offset)
        data = handle.read()
    new_offset = offset + len(data)
    text = data.decode("utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        if not any(marker in lowered for marker in _LOG_ERROR_MARKERS):
            continue
        message_id = "%s:%d:%s" % (
            os.path.basename(path), lineno,
            hashlib.sha256(line.encode("utf-8")).hexdigest()[:8])
        read_ids.add(message_id)
        if seen_ids is not None and message_id in seen_ids:
            continue
        tool = "log"
        issues.append(_issue_from_failure(
            tool, line, "log", message_id, None, None))
    return issues, new_offset, read_ids


def _load_state(out_dir):
    """اقرأ `state.json` (إزاحات + معرّفات معدّودة) أو state فارغ."""
    path = os.path.join(out_dir, STATE_FILENAME)
    if not os.path.isfile(path):
        return {"sources": {}, "seen_ids": []}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            state = json.load(handle)
        if not isinstance(state, dict):
            return {"sources": {}, "seen_ids": []}
        state.setdefault("sources", {})
        state.setdefault("seen_ids", [])
        return state
    except (ValueError, OSError):
        return {"sources": {}, "seen_ids": []}


def _atomic_write_json(path, payload):
    """اكتب JSON ذريًا بصلاحيات 0600."""
    tmp = "%s.tmp.%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.chmod(tmp, STATE_FILE_MODE)
    os.replace(tmp, path)


def _load_issues(out_dir):
    """اقرأ `issues.jsonl` كقاموس sig → قضية."""
    path = os.path.join(out_dir, ISSUES_FILENAME)
    issues = {}
    if not os.path.isfile(path):
        return issues
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict) and record.get("sig"):
                issues[record["sig"]] = record
    return issues


def _write_issues(out_dir, issues):
    """اكتب كل القضايا إلى `issues.jsonl` ذريًا بصلاحيات 0600."""
    path = os.path.join(out_dir, ISSUES_FILENAME)
    tmp = "%s.tmp.%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as handle:
        for sig in sorted(issues):
            handle.write(json.dumps(issues[sig], ensure_ascii=False) + "\n")
    os.chmod(tmp, STATE_FILE_MODE)
    os.replace(tmp, path)


def _source_fingerprint(path):
    """بصمة ملف مصدر: (inode, الحجم، زمن التعديل) أو None إن غاب."""
    try:
        info = os.stat(path)
    except OSError:
        return None
    return [info.st_ino, info.st_size, int(info.st_mtime)]


def run_sentinel(data_dir, out_dir=None, json_mode=False, once=True):
    """شغّل فحصًا واحدًا (دالة الدخول التي يلفّها أمر `studio.py sentinel`).

    `data_dir`: مجلد البيانات المقروء (يحوي `runs/jobs.jsonl`
    وسجلات التشغيل). `out_dir`: مجلد الكتابة (افتراضيًا
    `~/.local/state/qisas-studio-sentinel/`)؛ يُرفض إن كان
    داخل البيانات أو git. `once`: محجوز للتشغيل الدوري
    المستقبلي — الفحص الواحد هو السلوك الحالي دائمًا.

    يرجع (رمز خروج ع1 = 0 دائمًا عند النجاح، ملخص dict)؛
    والملخص يحمل `changed` و`new_issues` و`total_issues`
    و`scanned` و`out_dir`. حين لا يتغير أي ملف مصدر لا يُقرأ
    أي صف (`changed=False`).
    """
    data_dir = os.path.abspath(data_dir)
    if out_dir is None:
        out_dir = os.path.join(
            os.path.expanduser("~"), ".local", "state",
            DEFAULT_STATE_DIRNAME)
    out_dir = validate_out_dir(out_dir, data_dir)

    os.makedirs(out_dir, exist_ok=True)
    os.chmod(out_dir, STATE_DIR_MODE)

    jobs_path = os.path.join(data_dir, "runs", "jobs.jsonl")
    log_paths = []
    runs_dir = os.path.join(data_dir, "runs")
    if os.path.isdir(runs_dir):
        for name in sorted(os.listdir(runs_dir)):
            if name.endswith(".log"):
                log_paths.append(os.path.join(runs_dir, name))

    state = _load_state(out_dir)
    sources = state.get("sources", {})
    seen_ids = set(state.get("seen_ids", []))

    # بصمات المصادر الحالية؛ وتغيّر أي مصدر يشغّل الفحص.
    fingerprints = {}
    for path in [jobs_path] + log_paths:
        fingerprints[path] = _source_fingerprint(path)
    changed = False
    for path, fingerprint in fingerprints.items():
        old = sources.get(path)
        old_fp = old.get("fingerprint") if isinstance(old, dict) else old
        if fingerprint is None:
            if old_fp is not None:
                changed = True
            continue
        if old_fp != fingerprint:
            changed = True
    # مصدر اختفى كليًا (كان في الحالة وغاب الآن) يُعدّ تغييرًا.
    for path in sources:
        if path not in fingerprints:
            changed = True

    summary = {
        "changed": changed,
        "new_issues": 0,
        "total_issues": 0,
        "scanned": {"jobs": 0, "log_lines": 0, "log_files": len(log_paths)},
        "out_dir": out_dir,
        "json": bool(json_mode),
        "once": bool(once),
    }
    if not changed:
        existing = _load_issues(out_dir)
        summary["total_issues"] = len(existing)
        return 0, summary

    new_issues, read_ids = scan_jobs_file(jobs_path, seen_ids=seen_ids)
    summary["scanned"]["jobs"] = len(read_ids)
    seen_ids |= read_ids

    all_new = list(new_issues)
    for log_path in log_paths:
        source_state = sources.get(log_path) or {}
        offset = source_state.get("offset", 0)
        # الإزاحة تُصفَّر حين يصغر الملف أو يتغير inode.
        fingerprint = fingerprints.get(log_path)
        old_fingerprint = source_state.get("fingerprint")
        if fingerprint and old_fingerprint:
            if fingerprint[0] != old_fingerprint[0] or fingerprint[1] < old_fingerprint[1]:
                offset = 0
        log_issues, new_offset, log_ids = scan_log_file(
            log_path, offset=offset, seen_ids=seen_ids)
        all_new.extend(log_issues)
        seen_ids |= log_ids
        summary["scanned"]["log_lines"] += len(log_ids)
        sources[log_path] = {"offset": new_offset, "fingerprint": fingerprint}

    issues = _load_issues(out_dir)
    for issue in all_new:
        sig = issue["sig"]
        if sig in issues:
            existing = issues[sig]
            existing["count"] = existing.get("count", 1) + 1
            existing["wastedTurns"] = existing.get("wastedTurns", 1) + 1
            if issue.get("lastAt"):
                existing["lastAt"] = issue["lastAt"]
            existing["evidenceRef"] = issue["evidenceRef"]
        else:
            issues[sig] = issue
    if all_new:
        _write_issues(out_dir, issues)

    sources[jobs_path] = {"fingerprint": fingerprints.get(jobs_path)}
    state["sources"] = sources
    state["seen_ids"] = sorted(seen_ids)
    _atomic_write_json(os.path.join(out_dir, STATE_FILENAME), state)

    summary["new_issues"] = len(all_new)
    summary["total_issues"] = len(issues)
    return 0, summary
