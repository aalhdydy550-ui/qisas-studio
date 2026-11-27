#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""قارئ سجلات محدود (سطح الفحص/التحكم — جولة v0.1.63، البندان 19 و21).

قراءة سجل (حد 200 رسالة) وبحث سجل (حد 100 نتيجة) فوق ملفات
JSONL/ndjson أو سجلات نصية عادية، مع تقطيع: أي مخرج أطول من
1000 حرف يصل بأوله 1000 حرف مع `"clipped": true`.

- `read_log(path, limit=200)`: آخر `limit` سطرًا بترتيب الملف.
- `search_log(path, query, limit=100)`: أول `limit` مطابقة
  (مطابقة جزئية بلا حساسية لحالة الأحرف) بترتيب الملف.
- أحداث مهمة: `runs/events/<job_id>.ndjson` — إلحاق حدث
  (`append_job_event`) وقراءته (`read_job_events`) وعلامة
  الاستئناف (`events_resumed`): أول سطر يقول إن كان
  `"resumed": false` فأعد قراءة الحالة (بند 21).

القواعد:
- ملف غائب يُرفع LogReaderError (لا قائمة صامتة) إلا أحداث
  مهمة غائبة فتُرجع [] — فالمهمة بلا أحداث بعد حالة مشروعة.
- سطر JSON تالف يُتخطى ولا يُسقط القراءة.
- بلا شبكة وبلا قراءة خارج المسار الممرَّر.
"""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

CAIRO = ZoneInfo("Africa/Cairo")

# حدود القراءة (بند 19): 200 رسالة للقراءة، 100 نتيجة للبحث.
READ_LIMIT = 200
SEARCH_LIMIT = 100
# حد التقطيع (بند 21): مخرجات أطول من 1000 حرف تُقصّ.
CLIP_LIMIT = 1000

EVENTS_DIRNAME = "events"


class LogReaderError(Exception):
    """خطأ في قراءة سجل (رسالته عربية)."""


def now_cairo_iso():
    """الآن بتوقيت القاهرة بصيغة ISO."""
    return datetime.now(tz=CAIRO).isoformat(timespec="seconds")


def clip_text(text, limit=CLIP_LIMIT):
    """قصّ نصًا عند الحد؛ ارجع (النص، هل قُصّ؟).

    نص أقصر من الحد أو مساوٍ له يرجع كما هو مع False.
    """
    text = str(text)
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def clip_value(value, limit=CLIP_LIMIT):
    """قصّ كل نص طويل داخل قيمة (قاموس/قائمة/نص) بعمق.

    أي نص يُقصّ يضيف `"clipped": true` على مستوى القاموس
    الحاوي له. القيم غير النصية ترجع كما هي.
    """
    if isinstance(value, str):
        clipped_text, was_clipped = clip_text(value, limit)
        return clipped_text, was_clipped
    if isinstance(value, dict):
        out = {}
        clipped_any = False
        for key, item in value.items():
            new_item, was_clipped = clip_value(item, limit)
            out[key] = new_item
            clipped_any = clipped_any or was_clipped
        if clipped_any:
            out["clipped"] = True
        return out, clipped_any
    if isinstance(value, (list, tuple)):
        out = []
        clipped_any = False
        for item in value:
            new_item, was_clipped = clip_value(item, limit)
            out.append(new_item)
            clipped_any = clipped_any or was_clipped
        return out, clipped_any
    return value, False


def _is_jsonl_path(path):
    """هل الملف JSONL/ndjson (سطور JSON) أم سجلًا نصيًا عاديًا؟"""
    return str(path).lower().endswith((".jsonl", ".ndjson"))


def _parse_line(line, lineno, json_only=False):
    """سطر واحد إلى مدخل: JSON كقاموس، وإلا سطر نصي.

    سطر فارغ يرجع None دائمًا. في ملف JSONL سطر JSON تالف
    يُتخطى (None) ولا يُسقط القراءة؛ وفي ملف نصي أي سطر
    يرجع {"line": رقم السطر، "text": نصه}.
    """
    line = line.strip()
    if not line:
        return None
    try:
        record = json.loads(line)
    except ValueError:
        if json_only:
            return None
        return {"line": lineno, "text": line}
    if isinstance(record, dict):
        clipped, _was = clip_value(record)
        return clipped
    if json_only:
        return None
    return {"line": lineno, "text": line}


def _read_lines(path):
    """اقرأ كل سطور ملف؛ ارفع LogReaderError إن غاب الملف."""
    if not os.path.isfile(path):
        raise LogReaderError("ملف السجل غير موجود: %s" % path)
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.readlines()
    except OSError as e:
        raise LogReaderError("تعذّرت قراءة ملف السجل %s: %s"
                             % (path, e))


def _check_limit(limit, default):
    """تحقق من حد قراءة/بحث؛ ارجع الحد الفعلي."""
    if limit is None:
        return default
    if not isinstance(limit, int) or isinstance(limit, bool) \
            or limit < 1:
        raise LogReaderError(
            "حد القراءة غير صالح: %r (يلزم عدد صحيح ≥ 1)" % (limit,))
    return limit


def read_log(path, limit=READ_LIMIT):
    """اقرأ سجلًا: آخر `limit` مدخلًا (افتراضي 200) بترتيب الملف.

    ملف JSONL/ndjson يعطي قاموسًا لكل سطر؛ وملف نصي يعطي
    {"line": رقم السطر، "text": نصه}. حد فوق 200 يُقصّ إلى 200
    (بند 19 — لا قراءة بلا سقف).
    """
    limit = min(_check_limit(limit, READ_LIMIT), READ_LIMIT)
    json_only = _is_jsonl_path(path)
    entries = []
    for lineno, line in enumerate(_read_lines(path), start=1):
        entry = _parse_line(line, lineno, json_only=json_only)
        if entry is not None:
            entries.append(entry)
    return entries[-limit:] if len(entries) > limit else entries


def search_log(path, query, limit=SEARCH_LIMIT):
    """ابحث في سجل: أول `limit` مطابقة (افتراضي 100).

    المطابقة جزئية بلا حساسية لحالة الأحرف على نص المدخل
    (JSON مُسطَّحًا أو نص السطر). بترتيب الملف.
    """
    limit = min(_check_limit(limit, SEARCH_LIMIT), SEARCH_LIMIT)
    needle = str(query or "").casefold()
    if not needle:
        raise LogReaderError("عبارة البحث فارغة")
    json_only = _is_jsonl_path(path)
    matches = []
    for lineno, line in enumerate(_read_lines(path), start=1):
        entry = _parse_line(line, lineno, json_only=json_only)
        if entry is None:
            continue
        haystack = (json.dumps(entry, ensure_ascii=False)
                    if isinstance(entry, dict) else str(entry))
        if needle in haystack.casefold():
            matches.append(entry)
            if len(matches) >= limit:
                break
    return matches


# --- أحداث مهمة (بند 21): runs/events/<job_id>.ndjson ---

def events_path(runs_dir, job_id):
    """مسار ملف أحداث مهمة."""
    base = os.path.abspath(os.path.expanduser(runs_dir))
    return os.path.join(base, EVENTS_DIRNAME, "%s.ndjson" % job_id)


def append_job_event(runs_dir, job_id, event):
    """ألحق حدثًا واحدًا بملف أحداث مهمة؛ ارجع الحدث المكتوب.

    event قاموس (يلزم "kind")؛ يُضاف "ts" إن غاب. أي مخرج
    أطول من 1000 حرف يُقصّ مع "clipped": true عند الكتابة.
    """
    if not isinstance(event, dict) or not event.get("kind"):
        raise LogReaderError(
            "الحدث يلزم قاموسًا فيه kind (مثل started/completed)")
    record, _was = clip_value(dict(event))
    record.setdefault("ts", now_cairo_iso())
    record.setdefault("job_id", job_id)
    path = events_path(runs_dir, job_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_job_events(runs_dir, job_id, limit=READ_LIMIT):
    """اقرأ أحداث مهمة: آخر `limit` حدثًا (افتراضي 200).

    مهمة بلا ملف أحداث ترجع [] — بلا رفع.
    """
    limit = min(_check_limit(limit, READ_LIMIT), READ_LIMIT)
    path = events_path(runs_dir, job_id)
    if not os.path.isfile(path):
        return []
    entries = []
    for lineno, line in enumerate(_read_lines(path), start=1):
        entry = _parse_line(line, lineno, json_only=True)
        if entry is not None:
            entries.append(entry)
    return entries[-limit:] if len(entries) > limit else entries


def events_resumed(events):
    """علامة الاستئناف من أول حدث: True/False أو None إن غابت.

    `"resumed": false` في أول سطر تعني: أعد قراءة الحالة
    كاملة — فالارتباط لم يُستأنف من حيث انقطع (بند 21).
    """
    if not events:
        return None
    first = events[0]
    if isinstance(first, dict) and "resumed" in first:
        return bool(first["resumed"])
    return None


def events_settled(events):
    """هل استقرت المهمة؟ True إن حمل آخر حدث حالة نهائية.

    الحالات النهائية: completed/failed/cancelled، أو نتيجة
    انتظار (settled/needs-user/failed/stalled/timed-out).
    """
    if not events:
        return False
    last = events[-1]
    if not isinstance(last, dict):
        return False
    state = last.get("state") or last.get("kind")
    if state in ("completed", "failed", "cancelled"):
        return True
    return last.get("wait_outcome") in (
        "settled", "needs-user", "failed", "stalled", "timed-out")
