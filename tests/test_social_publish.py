#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات نشر TikTok/Instagram (lib.social_publish) — الجولة 7.

تعمل بـ `python3 -m unittest discover -s tests -v`.
بلا أي اتصال شبكي وبلا أي رفع حقيقي — تختبر بناء الحمولات
(--dry-run) وحفظ التوكنات والخطوات اليدوية فقط.
"""
import json
import os
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import social_publish as sp


def _mp4(tmpdir, size=1024):
    path = os.path.join(tmpdir, "video.mp4")
    with open(path, "wb") as f:
        f.write(b"\x00" * size)
    return path


class TestTiktokPayload(unittest.TestCase):
    def test_init_payload_shape(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td, size=25 * 1024 * 1024)
            payload = sp.tiktok_init_payload(
                video, "عنوان القصة", "كابشن قصير")
            self.assertEqual(payload["method"], "POST")
            self.assertTrue(payload["url"].endswith(
                "/v2/post/publish/video/init/"))
            body = payload["body"]
            self.assertEqual(body["post_info"]["privacy_level"],
                             "PUBLIC_TO_EVERYONE")
            self.assertIn("عنوان القصة", body["post_info"]["title"])
            self.assertEqual(body["source_info"]["source"], "FILE_UPLOAD")
            self.assertEqual(body["source_info"]["video_size"],
                             25 * 1024 * 1024)
            self.assertEqual(body["source_info"]["chunk_size"],
                             10 * 1024 * 1024)
            self.assertEqual(body["source_info"]["total_chunk_count"], 3)

    def test_title_too_long(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.tiktok_init_payload(video, "x" * 2201, "")
            self.assertIn("2200", str(cm.exception))

    def test_missing_video(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(sp.SocialPublishError):
                sp.tiktok_init_payload(
                    os.path.join(td, "nope.mp4"), "عنوان", "")

    def test_non_mp4_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "video.mov")
            with open(path, "wb") as f:
                f.write(b"\x00" * 10)
            with self.assertRaises(sp.SocialPublishError):
                sp.tiktok_init_payload(path, "عنوان", "")


class TestInstagramPayload(unittest.TestCase):
    def test_reel_payload_steps(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            payload = sp.instagram_reel_payload(
                video, "عنوان القصة", "كابشن", "123456789")
            steps = payload["steps"]
            # التدفق الصحيح حسب توثيق Meta: إنشاء (id فقط) ثم
            # POST إلى rupload برأسي offset/file_size ثم انتظار
            # FINISHED ثم النشر — لا upload_url ولا PUT ولا
            # Content-Range (كان الكود يوثّق التدفق الخاطئ).
            self.assertEqual(len(steps), 4)
            self.assertEqual(steps[0]["method"], "POST")
            self.assertIn("/123456789/media", steps[0]["url"])
            self.assertEqual(steps[0]["body"]["media_type"], "REELS")
            self.assertEqual(steps[0]["body"]["upload_type"],
                             "resumable")
            self.assertIn("بلا upload_url", steps[0]["returns"])
            self.assertEqual(steps[1]["method"], "POST")
            self.assertIn("rupload.facebook.com/ig-api-upload",
                          steps[1]["url"])
            self.assertIn("offset", steps[1]["headers"])
            self.assertIn("file_size", steps[1]["headers"])
            self.assertEqual(steps[2]["method"], "GET")
            self.assertIn("status_code", steps[2]["url"])
            self.assertEqual(steps[3]["method"], "POST")
            self.assertIn("/media_publish", steps[3]["url"])
            self.assertIn("لا يقبل رفع ملف محلي مباشر",
                          payload["note"])

    def test_missing_ig_user_id_placeholder(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            payload = sp.instagram_reel_payload(video, "عنوان", "", None)
            self.assertIn("معرّف حساب Instagram",
                          payload["ig_user_id"])


class TestTokens(unittest.TestCase):
    def test_save_load_roundtrip_600(self):
        with tempfile.TemporaryDirectory() as td:
            path = sp.save_token("tiktok", "test-token-abcdef", td)
            self.assertTrue(os.path.isfile(path))
            mode = stat.S_IMODE(os.stat(path).st_mode)
            self.assertEqual(mode, 0o600)
            self.assertEqual(sp.load_token("tiktok", td),
                             "test-token-abcdef")
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["platform"], "tiktok")

    def test_save_short_token_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(sp.SocialPublishError):
                sp.save_token("instagram", "short", td)

    def test_save_unknown_platform(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(sp.SocialPublishError):
                sp.save_token("facebook", "a-valid-token-value", td)

    def test_load_missing_token_none(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(sp.load_token("instagram", td))


class TestSetupSteps(unittest.TestCase):
    def test_tiktok_steps(self):
        steps = sp.setup_steps("tiktok")
        self.assertIn("developers.tiktok.com", steps)
        self.assertIn("Content Posting API", steps)
        self.assertIn("video.upload", steps)
        self.assertIn("tiktok-auth --token", steps)

    def test_instagram_steps(self):
        steps = sp.setup_steps("instagram")
        self.assertIn("instagram_basic", steps)
        self.assertIn("instagram_content_publish", steps)
        self.assertIn("Business", steps)
        self.assertIn("instagram-auth --token", steps)

    def test_unknown_platform(self):
        with self.assertRaises(sp.SocialPublishError):
            sp.setup_steps("youtube")


class TestSocialBundle(unittest.TestCase):
    def test_write_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            payload = sp.tiktok_init_payload(video, "عنوان", "كابشن")
            out = os.path.join(td, "bundle")
            result = sp.write_social_bundle(
                out, "tiktok", video, "عنوان", "كابشن", payload)
            self.assertTrue(os.path.isfile(
                os.path.join(result, "metadata.json")))
            self.assertTrue(os.path.isfile(
                os.path.join(result, "steps.txt")))
            with open(os.path.join(result, "metadata.json"),
                      encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["platform"], "tiktok")


class TestUploadInstagram(unittest.TestCase):
    """انحدار: الرفع الحقيقي كان يطلب upload_url من رد إنشاء
    الحاوية (Meta يرجع id فقط) فيرفض كل رد صحيح، ويرفع
    المقاطع PUT مع Content-Range بلا توكن (الصحيح POST إلى
    rupload برأسي offset/file_size وتخويل OAuth)، وينشر قبل
    جاهزية الحاوية."""

    def _fake_http(self, calls):
        def fake(method, url, body=None, token=None, headers=None,
                 timeout=300, **kw):
            calls.append((method, url, body, token))
            if method == "POST" and url.endswith("/media"):
                return {"id": "17841400000000000"}
            if method == "GET" and "status_code" in url:
                return {"status_code": "FINISHED"}
            if method == "POST" and url.endswith("/media_publish"):
                return {"id": "18000000000000000"}
            raise AssertionError("طلب غير متوقع: %s %s"
                                 % (method, url))
        return fake

    def test_full_flow_uses_rupload_and_waits(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td, size=1024)
            calls = []
            uploads = []
            real_http = sp._http_json
            real_rupload = sp._http_post_bytes_rupload
            real_dur = sp._check_duration
            sp._http_json = self._fake_http(calls)
            sp._http_post_bytes_rupload = lambda url, chunk, off, \
                total, token, timeout=600: uploads.append(
                    (url, off, total, token))
            sp._check_duration = lambda *a: None
            try:
                res = sp.upload_instagram(
                    video, "عنوان", "كابشن", "123456789",
                    "test-token-abcdef")
            finally:
                sp._http_json = real_http
                sp._http_post_bytes_rupload = real_rupload
                sp._check_duration = real_dur
            self.assertEqual(res["media_id"], "18000000000000000")
            self.assertEqual(res["creation_id"], "17841400000000000")
            # مقطع واحد إلى rupload بالتوكن وoffset 0.
            self.assertEqual(len(uploads), 1)
            url, off, total, token = uploads[0]
            self.assertIn("rupload.facebook.com/ig-api-upload/v21.0/"
                          "17841400000000000", url)
            self.assertEqual(off, 0)
            self.assertEqual(total, 1024)
            self.assertEqual(token, "test-token-abcdef")
            # انتظار الحالة قبل النشر: GET ثم media_publish آخرًا.
            methods = [(m, u) for (m, u, _b, _t) in calls]
            self.assertEqual(methods[0][0], "POST")
            self.assertTrue(any(m == "GET" and "status_code" in u
                                for (m, u) in methods))
            self.assertTrue(methods[-1][1].endswith("/media_publish"))

    def test_create_without_id_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            real_http = sp._http_json
            real_dur = sp._check_duration
            sp._http_json = lambda *a, **k: {}
            sp._check_duration = lambda *a: None
            try:
                with self.assertRaises(sp.SocialPublishError) as cm:
                    sp.upload_instagram(video, "عنوان", "كابشن",
                                        "123456789",
                                        "test-token-abcdef")
            finally:
                sp._http_json = real_http
                sp._check_duration = real_dur
            self.assertIn("بلا id", str(cm.exception))


class TestWaitIgContainer(unittest.TestCase):
    def test_error_status_raises(self):
        real_http = sp._http_json
        sp._http_json = lambda *a, **k: {"status_code": "ERROR"}
        try:
            with self.assertRaises(sp.SocialPublishError):
                sp._wait_ig_container_ready(
                    "17841400000000000", "test-token-abcdef",
                    timeout=0, poll_seconds=0)
        finally:
            sp._http_json = real_http

    def test_timeout_raises(self):
        real_http = sp._http_json
        sp._http_json = lambda *a, **k: {"status_code": "IN_PROGRESS"}
        try:
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp._wait_ig_container_ready(
                    "17841400000000000", "test-token-abcdef",
                    timeout=0, poll_seconds=0)
            self.assertIn("مهلة", str(cm.exception))
        finally:
            sp._http_json = real_http


class TestUploadTiktokStatus(unittest.TestCase):
    """انحدار: فحص الحالة FAILED كان يُرجع بنجاح ويطبع «رُفع»."""

    def _run(self, status_data):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td, size=1024)
            calls = []
            real_http = sp._http_json
            real_put = sp._http_put_bytes
            real_dur = sp._check_duration

            def fake(method, url, body=None, token=None,
                     headers=None, timeout=300, **kw):
                calls.append((method, url))
                if url.endswith("/video/init/"):
                    return {"data": {"publish_id": "pid-1",
                                     "upload_url":
                                     "https://example.invalid/up"}}
                if url.endswith("/status/fetch/"):
                    return {"data": status_data}
                raise AssertionError("طلب غير متوقع: %s" % url)
            sp._http_json = fake
            sp._http_put_bytes = lambda *a, **k: None
            sp._check_duration = lambda *a: None
            try:
                return sp.upload_tiktok(video, "عنوان", "كابشن",
                                        "test-token-abcdef")
            finally:
                sp._http_json = real_http
                sp._http_put_bytes = real_put
                sp._check_duration = real_dur

    def test_failed_status_raises(self):
        with self.assertRaises(sp.SocialPublishError) as cm:
            self._run({"status": "FAILED",
                       "fail_reason": "video_too_long"})
        self.assertIn("pid-1", str(cm.exception))

    def test_complete_returns_public_url(self):
        res = self._run({"status": "PUBLISH_COMPLETE",
                         "public_url": "https://tiktok.example/v/1"})
        self.assertEqual(res["publish_id"], "pid-1")
        self.assertEqual(res["status"], "PUBLISH_COMPLETE")
        self.assertEqual(res["public_url"],
                         "https://tiktok.example/v/1")


class TestCheckDuration(unittest.TestCase):
    def test_instagram_over_90s_rejected(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with mock.patch("lib.check.probe",
                            return_value={"duration": 120.0}):
                with self.assertRaises(sp.SocialPublishError) as cm:
                    sp._check_duration(
                        video, sp.IG_REEL_MAX_DURATION, "Instagram")
            self.assertIn("90", str(cm.exception))

    def test_short_video_passes(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with mock.patch("lib.check.probe",
                            return_value={"duration": 30.0}):
                sp._check_duration(
                    video, sp.IG_REEL_MAX_DURATION, "Instagram")


if __name__ == "__main__":
    unittest.main()
