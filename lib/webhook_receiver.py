#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""مستقبل webhooks محلي — جولة v0.1.63 (بند 36، عقد ع18).

**مُنفَّذ لكن مطفأ افتراضيًا.** البوابة راية `webhookReceiver`
في المزايا (ع7) وافتراضيها `False`؛ وأمر `webhook serve`
يرفض البدء ما لم تكن الراية `True` صراحةً. تشغيل المستمع
نفسه يحتاج قرارًا صريحًا لاحقًا — لا مستمع حي بلا ذلك القرار.

عند التفعيل: الاستماع على `127.0.0.1:8800` فقط (لا واجهة
خارجية أبدًا)، ومصادقة Bearer برمز يُعرض مرة واحدة ويُحفظ
مجزّأً فقط (sha256) في ملف 0600، وحمولة JSON ≤1MB.
"""
import hashlib
import hmac
import json
import os
import secrets
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

__all__ = [
    "WebhookError",
    "WebhookDisabledError",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "MAX_BODY_BYTES",
    "is_enabled",
    "enable_hint",
    "generate_token",
    "issue_token",
    "verify_token",
    "serve",
    "WebhookReceiver",
]

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8800
MAX_BODY_BYTES = 1024 * 1024
FEATURE_NAME = "webhookReceiver"

CAIRO = ZoneInfo("Africa/Cairo")


class WebhookError(Exception):
    """خطأ في مستقبل webhooks (رسالته عربية)."""


class WebhookDisabledError(WebhookError):
    """المستقبل مطفأ — يحتاج تفعيلًا صريحًا أولًا."""


def is_enabled():
    """هل راية `webhookReceiver` مفعّلة صراحةً؟ الافتراضي False.

    الاستيراد كسول لأن `lib/features.py` لعامل آخر في الجولة؛
    وغيابها أو أي عطل يعني: مطفأ (فشل مغلق).
    """
    try:
        from lib.features import get as features_get
    except Exception:
        return False
    try:
        return bool(features_get(FEATURE_NAME, False))
    except Exception:
        return False


def enable_hint():
    """كيف يُفعَّل المستقبل (تُطبع عند الرفض)."""
    return (
        "مستقبل webhooks مطفأ افتراضيًا. للتفعيل الصريح: "
        "studio.py features set webhookReceiver true — "
        "ثم أعد تشغيل webhook serve. التشغيل يحتاج قرارًا صريحًا."
    )


def generate_token():
    """رمز عشوائي جديد (يُعرض مرة واحدة فقط — لا يُحفظ نصًا)."""
    return secrets.token_urlsafe(32)


def _token_sha256(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _atomic_write_json(path, data):
    """كتابة ذرية 0600 لملف JSON."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    tmp = os.path.join(directory, ".webhook-token.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
        fh.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def issue_token(token_path):
    """يصدر رمزًا جديدًا ويعيد نصه **مرة واحدة فقط**.

    الملف يحفظ تجزئة sha256 فقط — النص لا يُكتب على القرص أبدًا.
    إعادة الإصدار تستبدل الرمز القديم (ويُبطل فورًا).
    """
    token = generate_token()
    _atomic_write_json(
        token_path,
        {
            "token_sha256": _token_sha256(token),
            "created": datetime.now(tz=CAIRO).isoformat(timespec="seconds"),
            "timezone": "Africa/Cairo",
        },
    )
    return token


def verify_token(token_path, presented):
    """هل الرمز المقدَّم يطابق المخزّن؟ مقارنة ثابتة الزمن."""
    if not presented or not os.path.isfile(token_path):
        return False
    try:
        with open(token_path, encoding="utf-8") as fh:
            stored = json.load(fh)
    except (OSError, ValueError):
        return False
    expected = stored.get("token_sha256") or ""
    if not expected:
        return False
    return hmac.compare_digest(_token_sha256(presented), expected)


def _check_enabled():
    if not is_enabled():
        raise WebhookDisabledError(enable_hint())


class WebhookReceiver:
    """مستقبل HTTP محلي على 127.0.0.1 فقط.

    `on_event` دالة اختيارية تستقبل قاموس الحدث الصحيح.
    الأحداث الصحيحة تُسجَّل أيضًا في `events` (في الذاكرة).
    """

    def __init__(self, *, host=DEFAULT_HOST, port=DEFAULT_PORT,
                 token_path=None, on_event=None):
        _check_enabled()
        if host != DEFAULT_HOST:
            raise WebhookError(
                "الاستماع مسموح على %s فقط — لا واجهة خارجية."
                % DEFAULT_HOST
            )
        self.host = host
        self.port = port
        self.token_path = token_path
        self.on_event = on_event
        self.events = []
        self._server = None
        self._thread = None

    def _handle_event(self, event):
        """يتحقق من الحدث ويسجّله ويمرّره للمعالج؛ يعيد معرّف مهمة."""
        if not isinstance(event, dict):
            raise WebhookError("جسم الحدث يجب أن يكون JSON object.")
        kind = event.get("event")
        if not kind or not isinstance(kind, str):
            raise WebhookError("الحدث بلا حقل event نصي.")
        job_id = "hook-%s-%s" % (
            datetime.now(tz=CAIRO).strftime("%Y%m%d-%H%M%S"),
            secrets.token_hex(4),
        )
        record = {
            "job_id": job_id,
            "event": kind,
            "received_at": datetime.now(tz=CAIRO).isoformat(timespec="seconds"),
            "timezone": "Africa/Cairo",
            "payload": event,
        }
        self.events.append(record)
        if self.on_event is not None:
            self.on_event(record)
        return job_id

    def _make_handler(self):
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):  # بلا ضجيج على stdout
                pass

            def _send_json(self, status, payload):
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _authorized(self):
                if receiver.token_path is None:
                    return False
                auth = self.headers.get("Authorization") or ""
                if not auth.startswith("Bearer "):
                    return False
                return verify_token(receiver.token_path, auth[7:].strip())

            def do_POST(self):
                if self.path not in ("/webhook", "/hook"):
                    self._send_json(404, {"ok": False, "error": "not_found"})
                    return
                if not self._authorized():
                    self._send_json(
                        401, {"ok": False, "error": "unauthorized"}
                    )
                    return
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    length = 0
                if length <= 0 or length > MAX_BODY_BYTES:
                    self._send_json(
                        413, {"ok": False, "error": "body_too_large"}
                    )
                    return
                raw = self.rfile.read(length)
                try:
                    event = json.loads(raw.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    self._send_json(
                        400, {"ok": False, "error": "invalid_json"}
                    )
                    return
                try:
                    job_id = receiver._handle_event(event)
                except WebhookError as exc:
                    self._send_json(
                        400, {"ok": False, "error": str(exc)}
                    )
                    return
                self._send_json(200, {"ok": True, "job_id": job_id})

            def do_GET(self):
                self._send_json(200, {"ok": True, "service": "webhook"})

        return Handler

    def start(self):
        """يربط 127.0.0.1 ويبدأ الخيط؛ يعيد (host, port) الفعليين."""
        if self._server is not None:
            raise WebhookError("المستقبل يعمل أصلًا.")
        self._server = ThreadingHTTPServer(
            (self.host, self.port), self._make_handler()
        )
        self._server.daemon_threads = True
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread.start()
        return self._server.server_address

    def stop(self):
        """يوقف المستمع وينتظر خيطه."""
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
        self._server = None
        self._thread = None


def serve(*, host=DEFAULT_HOST, port=DEFAULT_PORT, token_path=None,
          on_event=None):
    """يبني مستقبلًا ويشغّله؛ يرفض إن كانت الراية مطفأة.

    يعيد المستقبل الجاري — أوقفه بـ `stop()`. هذه الدالة لا
    تحجب الخيط؛ المتصل يقرر مدة التشغيل.
    """
    receiver = WebhookReceiver(
        host=host, port=port, token_path=token_path, on_event=on_event
    )
    receiver.start()
    return receiver
