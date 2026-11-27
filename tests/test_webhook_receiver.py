#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات مستقبل webhooks المحلي (lib.webhook_receiver) — جولة v0.1.63، بند 36.

تعمل بـ `python3 -m unittest tests.test_webhook_receiver -v` من مجلد studio.
بلا شبكة خارجية: الخادم الحي يُربط على 127.0.0.1 بمنفذ مؤقت،
وراية التفعيل تُرقَّع في الاختبارات الحية لأن `lib/features.py`
لعامل آخر في الجولة ولم تصل الشجرة بعد.
"""
import json
import os
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import webhook_receiver


def _post(url, body, token=None):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token is not None:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class TestDisabledByDefault(unittest.TestCase):
    def test_is_enabled_false_without_features(self):
        # بلا lib/features.py في الشجرة بعد: الفشل مغلق (مطفأ).
        self.assertFalse(webhook_receiver.is_enabled())

    def test_serve_refuses_when_disabled(self):
        with self.assertRaises(webhook_receiver.WebhookDisabledError) as ctx:
            webhook_receiver.serve(port=0)
        self.assertIn("webhookReceiver", str(ctx.exception))

    def test_enable_hint_names_the_flag(self):
        self.assertIn("webhookReceiver", webhook_receiver.enable_hint())


class TestToken(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "token.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_issue_token_shown_once_and_not_stored(self):
        token = webhook_receiver.issue_token(self.path)
        self.assertTrue(token)
        with open(self.path, encoding="utf-8") as fh:
            stored = fh.read()
        self.assertNotIn(token, stored)
        self.assertIn("token_sha256", stored)
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)

    def test_verify_token(self):
        token = webhook_receiver.issue_token(self.path)
        self.assertTrue(webhook_receiver.verify_token(self.path, token))
        self.assertFalse(webhook_receiver.verify_token(self.path, token + "x"))
        self.assertFalse(webhook_receiver.verify_token(self.path, ""))

    def test_reissue_invalidates_old_token(self):
        old = webhook_receiver.issue_token(self.path)
        new = webhook_receiver.issue_token(self.path)
        self.assertNotEqual(old, new)
        self.assertFalse(webhook_receiver.verify_token(self.path, old))
        self.assertTrue(webhook_receiver.verify_token(self.path, new))

    def test_verify_missing_file_false(self):
        self.assertFalse(webhook_receiver.verify_token(self.path, "x"))


class TestLiveServer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.token_path = os.path.join(self.tmp.name, "token.json")
        self.token = webhook_receiver.issue_token(self.token_path)
        self.received = []
        patcher = mock.patch.object(
            webhook_receiver, "is_enabled", return_value=True
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.receiver = webhook_receiver.WebhookReceiver(
            port=0, token_path=self.token_path,
            on_event=lambda record: self.received.append(record),
        )
        host, port = self.receiver.start()
        self.url = "http://%s:%d/webhook" % (host, port)

    def tearDown(self):
        self.receiver.stop()
        self.tmp.cleanup()

    def test_binds_loopback_only(self):
        self.assertEqual(self.receiver.host, "127.0.0.1")

    def test_reject_without_bearer(self):
        status, body = _post(self.url, {"event": "upload.done"})
        self.assertEqual(status, 401)
        self.assertFalse(body["ok"])
        self.assertEqual(self.received, [])

    def test_reject_wrong_bearer(self):
        status, _body = _post(self.url, {"event": "upload.done"},
                              token="wrong-token")
        self.assertEqual(status, 401)
        self.assertEqual(self.received, [])

    def test_accept_valid_event_and_convert_to_job(self):
        status, body = _post(self.url, {"event": "upload.done", "id": "42"},
                             token=self.token)
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertTrue(body["job_id"].startswith("hook-"))
        self.assertEqual(len(self.received), 1)
        self.assertEqual(self.received[0]["event"], "upload.done")
        self.assertEqual(self.received[0]["job_id"], body["job_id"])
        self.assertEqual(self.received[0]["timezone"], "Africa/Cairo")

    def test_reject_event_without_kind(self):
        status, body = _post(self.url, {"noid": 1}, token=self.token)
        self.assertEqual(status, 400)
        self.assertEqual(self.received, [])

    def test_reject_invalid_json(self):
        req = urllib.request.Request(self.url, data=b"{not json",
                                     method="POST")
        req.add_header("Authorization", "Bearer " + self.token)
        try:
            urllib.request.urlopen(req, timeout=5)
            self.fail("كان يجب أن يرفض JSON باطلًا")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)

    def test_unknown_path_404(self):
        status, _body = _post(self.url.replace("/webhook", "/nope"),
                              {"event": "x"}, token=self.token)
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
