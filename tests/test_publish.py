#!/usr/bin/env python3
"""اختبارات النشر — بلا نشر حقيقي وبلا شبكة.

facebook-cli ويوتيوب API يُستبدلان بمحاكاة (mock)؛ والتحقق من
النشر الحقيقي يتم عبر --dry-run فقط (انظر README).
"""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import publish


class TestCaption(unittest.TestCase):
    def test_adds_hashtags_and_invite_line(self):
        text = publish.build_caption("عنوان القصة", "كابشن تشويقي.")
        self.assertIn("عنوان القصة", text)
        self.assertIn("كابشن تشويقي.", text)
        for tag in publish.HASHTAGS:
            self.assertIn(tag, text)
        self.assertIn("ابعتها في رسائل الصفحة", text)
        self.assertLessEqual(len(text), publish.FB_CAPTION_LIMIT)

    def test_too_long_caption_raises(self):
        with self.assertRaises(publish.PublishError):
            publish.build_caption("t", "x" * 2000)

    def test_youtube_description_and_title_limits(self):
        desc = publish.build_youtube_description("عنوان", "كابشن",
                                                 moral="عبرة")
        self.assertIn("العبرة: عبرة", desc)
        self.assertIn(publish.PAGE_URL, desc)
        with self.assertRaises(publish.PublishError):
            publish.build_youtube_title("x" * 101)
        with self.assertRaises(publish.PublishError):
            publish.build_youtube_title("")


class TestFacebookCommand(unittest.TestCase):
    def test_argv_is_reel_with_single_mp4(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            Path(video).write_bytes(b"fake")
            argv = publish.facebook_argv(
                "1048148471706586", video, "كابشن",
                facebook_bin="/usr/bin/facebook-cli")
            self.assertEqual(argv[:4],
                             ["/usr/bin/facebook-cli", "pages", "posts",
                              "create"])
            self.assertIn("--page-id", argv)
            self.assertIn("1048148471706586", argv)
            self.assertIn("--privacy", argv)
            self.assertIn("PUBLIC", argv)
            self.assertIn(video, argv)
            self.assertIn("--media-caption", argv)
            self.assertNotIn("--scheduled-publish-time", argv)

    def test_schedule_adds_publish_time(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            Path(video).write_bytes(b"fake")
            argv = publish.facebook_argv(
                "1", video, "كابشن", schedule=1795366800,
                facebook_bin="facebook-cli")
            self.assertIn("--scheduled-publish-time", argv)
            self.assertIn("1795366800", argv)

    def test_missing_video_raises(self):
        with self.assertRaises(publish.PublishError):
            publish.facebook_argv("1", "/nope/v.mp4", "كابشن",
                                  facebook_bin="facebook-cli")

    def test_post_confirms_published_state(self):
        proc = mock.MagicMock()
        proc.returncode = 0
        proc.stdout = json.dumps({"state": "published",
                                  "post_id": "122"})
        with mock.patch("lib.publish.subprocess.run",
                        return_value=proc), \
             mock.patch("lib.publish.find_facebook_bin",
                        return_value="facebook-cli"), \
             mock.patch("lib.publish.os.path.isfile", return_value=True):
            res = publish.post_facebook("1", "/tmp/v.mp4", "كابشن")
        self.assertEqual(res, {"post_id": "122", "state": "published"})

    def test_post_rejects_non_published_state(self):
        proc = mock.MagicMock()
        proc.returncode = 0
        proc.stdout = json.dumps({"state": "failed"})
        with mock.patch("lib.publish.subprocess.run",
                        return_value=proc), \
             mock.patch("lib.publish.find_facebook_bin",
                        return_value="facebook-cli"), \
             mock.patch("lib.publish.os.path.isfile", return_value=True):
            with self.assertRaises(publish.PublishError):
                publish.post_facebook("1", "/tmp/v.mp4", "كابشن")


class TestYoutubePayload(unittest.TestCase):
    def test_payload_shape_and_tag_limit(self):
        payload = publish.youtube_payload(
            "عنوان", "وصف", ["قصص", "عبر"], privacy="public")
        self.assertEqual(payload["method"], "youtube.videos.insert")
        self.assertEqual(payload["body"]["snippet"]["title"], "عنوان")
        self.assertEqual(payload["body"]["status"]["privacyStatus"],
                         "public")
        self.assertEqual(payload["body"]["snippet"]["categoryId"], "24")
        with self.assertRaises(publish.PublishError):
            publish.youtube_payload("عنوان", "وصف", ["x" * 600])

    def test_bundle_writes_metadata_description_steps(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            Path(video).write_bytes(b"fake")
            bundle = publish.write_youtube_bundle(
                os.path.join(td, "bundle"), video, "عنوان", "وصف",
                ["قصص"])
            self.assertTrue(os.path.isfile(
                os.path.join(bundle, "metadata.json")))
            self.assertTrue(os.path.isfile(
                os.path.join(bundle, "description.txt")))
            steps = Path(bundle, "steps.txt").read_text(encoding="utf-8")
            self.assertIn("studio.youtube.com", steps)
            meta = json.loads(Path(bundle, "metadata.json")
                              .read_text(encoding="utf-8"))
            self.assertEqual(meta["body"]["snippet"]["title"], "عنوان")
            self.assertEqual(meta["video"], os.path.abspath(video))

    def test_upload_without_token_raises(self):
        with mock.patch("lib.publish.youtube_venv_python",
                        return_value="/x/.venv-youtube/bin/python"):
            with self.assertRaises(publish.PublishError):
                publish.upload_youtube("/tmp/v.mp4", "عنوان", "وصف", [],
                                       token="/nope/token.json")


class TestCmdPublishDryRun(unittest.TestCase):
    def test_dry_run_prints_payloads_and_posts_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            Path(video).write_bytes(b"fake")
            cfg = {"publish": {"page_id": "1048148471706586",
                               "youtube_token": os.path.join(td, "t.json"),
                               "youtube_privacy": "public"},
                   "paths": {"videos_dir": td}}
            with mock.patch("lib.publish.find_facebook_bin",
                            return_value="facebook-cli"):
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    # فيديو وهمي (بايتات عشوائية) — فحص الجودة
                    # المسبق يُتجاوز هنا؛ بوابته تُختبر وحدها أدناه.
                    rc = studio.cmd_publish(
                        cfg, video, "عنوان التجربة", "كابشن تجريبي",
                        platforms=("facebook", "youtube"), dry_run=True,
                        skip_check=True)
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("وضع تجريبي", out)
            self.assertIn("facebook-cli", out)
            self.assertIn("youtube.videos.insert", out)
            self.assertIn("عنوان التجربة", out)

    def test_real_run_without_youtube_token_writes_bundle(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            Path(video).write_bytes(b"fake")
            cfg = {"publish": {"page_id": "1048148471706586",
                               "youtube_token": os.path.join(td, "t.json"),
                               "youtube_privacy": "public"},
                   "paths": {"videos_dir": td}}
            proc = mock.MagicMock()
            proc.returncode = 0
            proc.stdout = json.dumps({"state": "published",
                                      "post_id": "122"})
            with mock.patch("lib.publish.subprocess.run",
                            return_value=proc):
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    # فيديو وهمي — فحص الجودة يُتجاوز؛ المقصود هنا
                    # مسار حزمة يوتيوب اليدوية عند غياب التوكن.
                    rc = studio.cmd_publish(
                        cfg, video, "عنوان", "كابشن",
                        platforms=("facebook", "youtube"),
                        skip_check=True)
            # فيسبوك نُشر لكن يوتيوب بلا توكن → حزمة يدوية + رجوع 1
            self.assertEqual(rc, 1)
            out = buf.getvalue()
            self.assertIn("فيسبوك: نُشر", out)
            self.assertIn("حزمة الرفع اليدوي", out)
            bundles = [d for d in os.listdir(td)
                       if d.startswith("publish-") and d.endswith("-youtube")]
            self.assertEqual(len(bundles), 1)


class TestPublishQualityGate(unittest.TestCase):
    """بوابة فحص الجودة المسبق في cmd_publish (فحص مُحاكى).

    فيديو وهمي + فحص مُحاكى: الفشل يمنع النشر، والنجاح يمرّره،
    و--skip-check يتجاوز البوابة دون استدعاء الفحص أصلًا.
    """

    def _cfg(self, td):
        return {"publish": {"page_id": "1048148471706586",
                            "youtube_token": os.path.join(td, "t.json"),
                            "youtube_privacy": "public"},
                "paths": {"videos_dir": td}}

    def _result(self, passed):
        return {"path": "/tmp/v.mp4", "long": False, "duration": 45.0,
                "width": 720, "height": 1280,
                "checks": [{"name": "المدة", "ok": passed,
                            "detail": "المدة 45.0 ثانية"}],
                "passed": passed}

    def test_failed_check_blocks_publish(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            Path(video).write_bytes(b"fake")
            with mock.patch("studio.check_lib.run_checks",
                            return_value=self._result(False)), \
                 mock.patch("lib.publish.post_facebook",
                            side_effect=AssertionError(
                                "لا نشر بعد فشل الفحص")):
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    rc = studio.cmd_publish(
                        self._cfg(td), video, "عنوان", "كابشن",
                        platforms=("facebook",), dry_run=True)
            self.assertEqual(rc, 1)
            self.assertIn("فشل فحص الجودة", buf.getvalue())

    def test_passed_check_allows_dry_run(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            Path(video).write_bytes(b"fake")
            with mock.patch("studio.check_lib.run_checks",
                            return_value=self._result(True)), \
                 mock.patch("lib.publish.find_facebook_bin",
                            return_value="facebook-cli"):
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    rc = studio.cmd_publish(
                        self._cfg(td), video, "عنوان", "كابشن",
                        platforms=("facebook",), dry_run=True)
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("وضع تجريبي", out)
            self.assertIn("[PASS]", out)

    def test_skip_check_never_calls_the_gate(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            Path(video).write_bytes(b"fake")
            with mock.patch("studio.check_lib.run_checks",
                            side_effect=AssertionError(
                                "البوابة استُدعيت رغم --skip-check")), \
                 mock.patch("lib.publish.find_facebook_bin",
                            return_value="facebook-cli"):
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    rc = studio.cmd_publish(
                        self._cfg(td), video, "عنوان", "كابشن",
                        platforms=("facebook",), dry_run=True,
                        skip_check=True)
            self.assertEqual(rc, 0)
            self.assertNotIn("فحص جودة", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
