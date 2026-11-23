#!/usr/bin/env python3
"""اختبارات فحص ما قبل النشر على يوتيوب (الجولة 8 — v0.1.33).

`publish --preflight`: صلاحية التوكن أولًا (بلا شبكة)، ثم إنشاء
جلسة رفع قابلة للاستئناف بلا إرسال أي بايت من الفيديو وبلا نشر.
كل الشبكة محاكاة (http_post محقون) — بلا أي اتصال حقيقي وبلا
نشر حقيقي وبلا لمس للتوكن الحقيقي.
"""
import io
import json
import os
import ssl
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import publish
from lib import youtube_upload

# جولة v0.1.41 (إصلاح CI): بيئة .venv-youtube موجودة محليًا
# فقط ولا تُرفع إلى GitHub (في .gitignore) — ففحص ما قبل النشر
# يرفع PublishError «بيئة YouTube غير موجودة» في CI قبل أي
# منطق. عند غيابها تتخطى فئة الغلاف نظيفًا (نمط test_ci_skips).
_HAS_YOUTUBE_VENV = publish.youtube_venv_python() is not None


def _token_file(td, refresh=True, scopes=True):
    data = {"refresh_token": "1//fake-refresh"} if refresh else {}
    if scopes:
        data["scopes"] = [
            "https://www.googleapis.com/auth/youtube.upload"]
    path = os.path.join(td, "token.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


class FakeResponse:
    def __init__(self, status_code=200, location=None):
        self.status_code = status_code
        self.headers = {}
        if location:
            self.headers["Location"] = location


class TestTokenFileStatus(unittest.TestCase):
    def test_missing_token(self):
        status, detail = youtube_upload.token_file_status(
            "/tmp/no-such-token-xyz.json")
        self.assertEqual(status, "missing")
        self.assertIn("غير موجود", detail)

    def test_corrupt_token(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "token.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{not json")
            status, _ = youtube_upload.token_file_status(path)
            self.assertEqual(status, "invalid")

    def test_token_without_refresh_token_is_invalid(self):
        with tempfile.TemporaryDirectory() as td:
            path = _token_file(td, refresh=False)
            status, detail = youtube_upload.token_file_status(path)
            self.assertEqual(status, "invalid")
            self.assertIn("refresh_token", detail)

    def test_valid_token_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = _token_file(td)
            status, _ = youtube_upload.token_file_status(path)
            self.assertEqual(status, "ok")


class TestRunPreflight(unittest.TestCase):
    def setUp(self):
        self._orig_load = youtube_upload.load_credentials
        youtube_upload.load_credentials = lambda p: object()

    def tearDown(self):
        youtube_upload.load_credentials = self._orig_load

    def test_success_creates_session_without_video_bytes(self):
        calls = []

        def fake_post(url, headers=None, data=None):
            calls.append({"url": url, "headers": headers, "data": data})
            return FakeResponse(
                200, "https://www.googleapis.com/upload/session/abc")

        with tempfile.TemporaryDirectory() as td:
            token = _token_file(td)
            result = youtube_upload.run_preflight(
                token, "العنوان", "الوصف", ["قصص"], 123456,
                http_post=fake_post)
        self.assertTrue(result["ok"])
        self.assertEqual(result["video_size"], 123456)
        self.assertEqual(len(calls), 1)
        call = calls[0]
        # جلسة resumable فقط — لا مقاطع فيديو في الطلب.
        self.assertIn("uploadType=resumable", call["url"])
        self.assertEqual(call["headers"]["X-Upload-Content-Length"],
                         "123456")
        body = json.loads(call["data"])
        self.assertEqual(body["snippet"]["title"], "العنوان")
        self.assertNotIn("video/mp4; charset", call["data"])

    def test_ssl_failure_prints_manual_message(self):
        def failing_post(url, headers=None, data=None):
            raise ssl.SSLError(
                "[SSL: WRONG_VERSION_NUMBER] wrong version number")

        with tempfile.TemporaryDirectory() as td:
            token = _token_file(td)
            with self.assertRaises(youtube_upload.PreflightError) as cm:
                youtube_upload.run_preflight(
                    token, "العنوان", "الوصف", [], 100,
                    http_post=failing_post)
        msg = str(cm.exception)
        self.assertIn("WRONG_VERSION_NUMBER", msg)
        self.assertIn("YouTube Studio", msg)
        self.assertIn("يدوي", msg)

    def test_invalid_token_reports_before_any_network(self):
        def must_not_run(url, headers=None, data=None):
            raise AssertionError("لا يجب أن تُجرى أي محاولة شبكة")

        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(youtube_upload.PreflightError) as cm:
                youtube_upload.run_preflight(
                    os.path.join(td, "missing.json"), "العنوان",
                    "الوصف", [], 100, http_post=must_not_run)
        self.assertIn("توكن يوتيوب", str(cm.exception))
        self.assertIn("youtube-reauth", str(cm.exception))

    def test_api_rejection_is_preflight_error(self):
        def fake_post(url, headers=None, data=None):
            return FakeResponse(403)

        with tempfile.TemporaryDirectory() as td:
            token = _token_file(td)
            with self.assertRaises(youtube_upload.PreflightError) as cm:
                youtube_upload.run_preflight(
                    token, "العنوان", "الوصف", [], 100,
                    http_post=fake_post)
        self.assertIn("403", str(cm.exception))


@unittest.skipUnless(
    _HAS_YOUTUBE_VENV,
    "بيئة .venv-youtube غائبة (لا تُرفع إلى GitHub) — بيئة CI")
class TestPublishPreflightWrapper(unittest.TestCase):
    def test_runner_success_returns_report(self):
        def runner(argv):
            self.assertIn("preflight", argv)
            self.assertIn("--video-size", argv)
            # «-I» إلزامي: بدونه يظلّل lib/queue.py وحدة stdlib
            # queue فينكسر urllib3 قبل أي شبكة.
            self.assertIn("-I", argv)
            return 0, ("فحص ما قبل النشر على يوتيوب: المسار يعمل "
                       "من الـVM — أُنشئت جلسة رفع."), ""

        result = publish.youtube_preflight(
            __file__, "العنوان", "الوصف", ["قصص"], 100,
            runner=runner)
        self.assertTrue(result["ok"])
        self.assertIn("المسار يعمل", result["report"])

    def test_runner_ssl_failure_passes_arabic_message(self):
        def runner(argv):
            return 1, "", ("فحص ما قبل النشر على يوتيوب: فشل — "
                           "SSL: WRONG_VERSION_NUMBER — ارفع الفيديو "
                           "يدويًا من YouTube Studio")

        with self.assertRaises(publish.PublishError) as cm:
            publish.youtube_preflight(
                __file__, "العنوان", "الوصف", [], 100, runner=runner)
        self.assertIn("YouTube Studio", str(cm.exception))

    def test_missing_token_file_raises_before_runner(self):
        def must_not_run(argv):
            raise AssertionError("لا يجب استدعاء الرافع بلا توكن")

        with self.assertRaises(publish.PublishError) as cm:
            publish.youtube_preflight(
                "/tmp/no-such-token-xyz.json", "العنوان", "الوصف",
                [], 100, runner=must_not_run)
        self.assertIn("توكن يوتيوب", str(cm.exception))


class TestPreflightCli(unittest.TestCase):
    def test_main_preflight_invalid_token_exit_nonzero(self):
        # مسار التوكن الصريح بلا شبكة: main يخرج بكود غير صفري.
        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as td:
            with redirect_stdout(buf):
                rc = youtube_upload.main([
                    "preflight", "--token",
                    os.path.join(td, "missing.json"),
                    "--title", "العنوان", "--video-size", "100"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
