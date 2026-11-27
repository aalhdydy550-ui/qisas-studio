#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""انضباط الإشعارات — جولة v0.1.63 (بند 27، عقد ع5).

إشعار واحد لكل مفتاح في كل سلسلة فشل / لكل حد وفترة عند
البلوغ؛ ولا إشعار عند إعادة الضبط؛ ولا إشعار مكرر بعد
إعادة تشغيل. إزالة التكرار في ملف حالة
`runs/notify-dedup.json` (0600، كتابة ذرية تحت قفل ملف —
نمط lib/job_registry.py).

الدالة المركزية `notify_once(key, message, channel="log")`
ترجع True إن أُرسل فعلًا وFalse إن كُرر. التسليم نفسه
قابل للحقن (وسيط `deliver`) فيُختبر بلا مخرجات حقيقية؛
والتسليم الافتراضي سطر في سجل logging (قناة "log") —
بلا شبكة وبلا إرسال خارجي في هذه الوحدة: قنوات الإرسال
الخارجية (إن وُجدت لاحقًا) تُمرَّر كدالة deliver من
المستدعي، لا تُبنى هنا.

إعادة الضبط لا تُشعر أبدًا: `reset_notify` يمسح المفتاح
من مخزن إزالة التكرار بصمت فيُسمح بإشعار جديد لاحقًا
للسلسلة التالية.
"""
import fcntl
import json
import logging
import os
import tempfile
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

CAIRO = ZoneInfo("Africa/Cairo")

DEDUP_FILENAME = "notify-dedup.json"
SCHEMA_VERSION = 1

_LOG = logging.getLogger("studio.notify")

# قفل خيوط داخل العملية (يكمل قفل الملف بين العمليات).
_NOTIFY_THREAD_LOCK = threading.Lock()


class NotifyError(Exception):
    """خطأ في الإشعارات (رسالته عربية)."""


def now_cairo_iso():
    """الآن بتوقيت القاهرة بصيغة ISO."""
    return datetime.now(tz=CAIRO).isoformat(timespec="seconds")


def default_runs_dir():
    """مجلد runs الافتراضي: runs/ بجانب مجلد lib هذا."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "runs")


def dedup_path(runs_dir):
    """مسار ملف إزالة التكرار (runs/notify-dedup.json)."""
    base = os.path.abspath(os.path.expanduser(
        runs_dir or default_runs_dir()))
    return os.path.join(base, DEDUP_FILENAME)


def _default_deliver(key, message, channel):
    """التسليم الافتراضي: سطر سجل فقط (قناة "log").

    يرجع True دائمًا (أُرسل). أي قناة أخرى بلا مسلِّم
    محقون تُسجَّل بالطريقة نفسها — لا إرسال خارجي هنا.
    """
    _LOG.info("[%s] %s: %s", channel, key, message)
    return True


def _read_locked(path):
    """اقرأ مخزن إزالة التكرار (يُستدعى والقفل ممسوك).

    ملف غائب أو JSON تالف ← مخزن فارغ (لا يُسقط الإشعار
    الحالي)؛ وسطر بلا مخزن سليم يُعامل كمخزن فارغ.
    """
    if not os.path.isfile(path):
        return {"schema_version": SCHEMA_VERSION, "keys": {}}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {"schema_version": SCHEMA_VERSION, "keys": {}}
    if not isinstance(data, dict) or not isinstance(
            data.get("keys"), dict):
        return {"schema_version": SCHEMA_VERSION, "keys": {}}
    return {"schema_version": SCHEMA_VERSION,
            "keys": dict(data["keys"])}


def _write_locked(path, store):
    """اكتب المخزن ذريًا بصلاحية 0600 (يُستدعى والقفل ممسوك)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path),
                               prefix=".notify-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(store, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _locked(runs_dir):
    """سياق قفل ملف حصري يغطي القراءة والتعديل والكتابة."""
    path = dedup_path(runs_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock_path = path + ".lock"
    lock_f = open(lock_path, "a+", encoding="utf-8")
    fcntl.flock(lock_f, fcntl.LOCK_EX)
    return path, lock_f


def notify_once(key, message, channel="log", runs_dir=None,
                deliver=None):
    """أرسل إشعارًا مرة واحدة لكل مفتاح؛ ارجع True إن أُرسل.

    key: مفتاح إزالة التكرار (مثل "usage-cap:dailyUsd"
    أو "routine:<name>:failure-series") — نص غير فارغ.
    message: نص الإشعار (غير فارغ). channel: قناة التسليم
    (الافتراضي "log"). deliver: دالة اختيارية
    deliver(key, message, channel) -> bool؛ إن رجعت False
    يُعامل الإشعار كغير مرسَل ولا يُسجَّل في المخزن.
    مفتاح سبق إرساله ← False بلا أي تسليم (لا تكرار حتى
    بعد إعادة تشغيل — المخزن على القرص).
    """
    key = (key or "").strip() if isinstance(key, str) else ""
    if not key:
        raise NotifyError("مفتاح الإشعار مفقود — مرّر key غير فارغ")
    message = (message or "").strip() \
        if isinstance(message, str) else ""
    if not message:
        raise NotifyError("نص الإشعار مفقود — مرّر message غير فارغ")
    channel = (channel or "log").strip() \
        if isinstance(channel, str) else "log"
    send = deliver or _default_deliver
    with _NOTIFY_THREAD_LOCK:
        path, lock_f = _locked(runs_dir)
        try:
            store = _read_locked(path)
            if key in store["keys"]:
                return False
            sent = send(key, message, channel)
            if sent is False:
                return False
            store["keys"][key] = {"ts": now_cairo_iso(),
                                  "channel": channel}
            _write_locked(path, store)
            return True
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            lock_f.close()


def was_notified(key, runs_dir=None):
    """هل أُرسل إشعار بهذا المفتاح من قبل؟ (قراءة فقط)."""
    key = (key or "").strip() if isinstance(key, str) else ""
    if not key:
        return False
    store = _read_locked(dedup_path(runs_dir))
    return key in store["keys"]


def list_notified(runs_dir=None):
    """نسخة من مخزن إزالة التكرار {key: {ts, channel}}."""
    store = _read_locked(dedup_path(runs_dir))
    return dict(store["keys"])


def reset_notify(key=None, runs_dir=None):
    """امسح مفتاحًا (أو كل المفاتيح إن غاب) من المخزن — بصمت.

    إعادة الضبط لا تُشعر أبدًا: المسح هنا لا يرسل أي
    إشعار، بل يسمح فقط بإشعار جديد لاحقًا للسلسلة
    التالية. يرجع عدد المفاتيح الممسوحة.
    """
    with _NOTIFY_THREAD_LOCK:
        path, lock_f = _locked(runs_dir)
        try:
            store = _read_locked(path)
            if key is None:
                cleared = len(store["keys"])
                store["keys"] = {}
            else:
                key = str(key).strip()
                cleared = 1 if key in store["keys"] else 0
                store["keys"].pop(key, None)
            _write_locked(path, store)
            return cleared
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)
            lock_f.close()


# اسم بديل أوضح للمستدعين: مسح إزالة التكرار.
clear_dedup = reset_notify
