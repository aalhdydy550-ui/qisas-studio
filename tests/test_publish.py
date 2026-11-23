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
from lib import manifest as manifest_lib
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
            # بوابة بيان المصدر (v0.1.37): فيديو جديد بلا بيان يُرفض
            # في النشر الحقيقي — والمسار المختبر هنا (حزمة يوتيوب
            # اليدوية) يفترض فيديو منتجًا من الاستوديو فله بيان.
            manifest_lib.write_manifest(video, {
                "schema_version": manifest_lib.SCHEMA_VERSION,
                "video": {"file": video,
                          "sha256": manifest_lib.sha256_file(video)},
                "title": "عنوان التجربة",
                "hook": "هوك التجربة",
                "created_at": manifest_lib.now_cairo_iso(),
                "source": "test",
            })
            cfg = {"publish": {"page_id": "1048148471706586",
                               "youtube_token": os.path.join(td, "t.json"),
                               "youtube_privacy": "public"},
                   "paths": {"videos_dir": td}}
            proc = mock.MagicMock()
            proc.returncode = 0
            proc.stdout = json.dumps({"state": "published",
                                      "post_id": "122"})
            # (انحدار CI #255): post_facebook يبني الأمر عبر
            # find_facebook_bin — بلا هذه المحاكاة يفشل الاختبار
            # في CI حيث facebook-cli غير مثبّت أصلًا، بينما يمر
            # محليًا بفضل المسار المطلق /opt/hatch/bin/facebook-cli
            # الموجود على الـVM فقط.
            with mock.patch("lib.publish.subprocess.run",
                            return_value=proc), \
                 mock.patch("lib.publish.find_facebook_bin",
                            return_value="facebook-cli"):
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


class TestCaptionComplianceGate(unittest.TestCase):
    """بوابة امتثال الكابشن في cmd_publish (فحص مُحاكى للجودة).

    كابشن محظور يرفض النشر قبل أي حمولة؛ والدعوة اللطيفة
    وسطر «ابعت قصتك» يمرّان؛ و--skip-caption-check يتجاوز
    البوابة صراحةً.
    """

    GATE = ("لو عايز الجزء الثاني اعمل متابعة واكتب في التعليقات: "
            "الجزء الثاني")
    GENTLE = ("الجزء الثاني بكرة 7 مساءً — اعمل متابعة عشان يوصلك "
              "أول ما ينزل")

    def _cfg(self, td):
        return {"publish": {"page_id": "1048148471706586",
                            "youtube_token": os.path.join(td, "t.json"),
                            "youtube_privacy": "public"},
                "paths": {"videos_dir": td}}

    def _run(self, td, video, title, caption, **kw):
        with mock.patch("lib.publish.find_facebook_bin",
                        return_value="facebook-cli"), \
             mock.patch("lib.publish.post_facebook",
                        side_effect=AssertionError(
                            "لا نشر بعد رفض الكابشن")):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                rc = studio.cmd_publish(
                    self._cfg(td), video, title, caption,
                    platforms=("facebook",), dry_run=True,
                    skip_check=True, **kw)
        return rc, buf.getvalue()

    def test_banned_caption_blocks_publish(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            Path(video).write_bytes(b"fake")
            rc, out = self._run(td, video, "عنوان", self.GATE)
            self.assertEqual(rc, 1)
            self.assertIn("مرفوض", out)
            self.assertIn("الكابشن المقترح", out)
            self.assertIn("بكرة 7 مساء", out)
            self.assertNotIn("وضع تجريبي", out)

    def test_skip_caption_check_allows_banned(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            Path(video).write_bytes(b"fake")
            rc, out = self._run(td, video, "عنوان", self.GATE,
                                skip_caption_check=True)
            self.assertEqual(rc, 0)
            self.assertIn("وضع تجريبي", out)
            self.assertIn("متخطَّى", out)

    def test_gentle_invite_passes_and_caption_shown(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            Path(video).write_bytes(b"fake")
            rc, out = self._run(td, video, "عنوان", self.GENTLE)
            self.assertEqual(rc, 0)
            self.assertIn("الكابشن النهائي", out)
            self.assertIn("بكرة 7 مساء", out)
            self.assertNotIn("مرفوض", out)

    def test_gate_in_title_needs_full_rewrite(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            Path(video).write_bytes(b"fake")
            rc, out = self._run(td, video, self.GATE, "كابشن عادي")
            self.assertEqual(rc, 1)
            self.assertIn("أعد كتابة", out)


class TestPublishNoFacebookBinRegression(unittest.TestCase):
    """انحدار CI #255: اختبارات النشر الثلاثة تمرّ بلا facebook-cli.

    السبب الجذري: cmd_publish يبني أمر فيسبوك عبر
    lib.publish.find_facebook_bin()، وفي CI (ubuntu-latest)
    لا facebook-cli في PATH ولا /opt/hatch/bin — ففشلت
    الاختبارات الثلاثة هناك بينما تمرّ محليًا بفضل المسار
    المطلق الموجود على الـVM فقط (ومحاكاة find_facebook_bin
    في الاختبارات نفسها هي الإصلاح). هذا الاختبار يثبت
    الإصلاح بتشغيل الاختبارات الثلاثة في عملية فرعية ببيئة
    عارية (HOME فارغ، PATH بلا شيء إلا python وffmpeg كما
    في CI) مع إفراغ FACEBOOK_BIN_CANDIDATES لمحاكاة غياب
    الثنائي تمامًا — والنجاح = 3 اختبارات ناجحة بلا تخطٍّ.
    """

    def test_publish_tests_pass_without_facebook_bin(self):
        import shutil
        studio_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        test_ids = [
            "tests.test_publish.TestCmdPublishDryRun."
            "test_real_run_without_youtube_token_writes_bundle",
            "tests.test_wiring_0139.TestPublishGenerateMetaWiring."
            "test_generate_meta_dry_run_with_mock_llm",
            "tests.test_wiring_0139.TestPublishGenerateMetaWiring."
            "test_generate_meta_explicit_caption_wins",
        ]
        driver = (
            "import sys\n"
            "sys.path.insert(0, %r)\n"
            "import lib.publish\n"
            "lib.publish.FACEBOOK_BIN_CANDIDATES = ()\n"
            "import unittest\n"
            "suite = unittest.TestLoader().loadTestsFromNames(%r)\n"
            "result = unittest.TextTestRunner(verbosity=2).run(suite)\n"
            "sys.exit(0 if result.wasSuccessful() else 1)\n"
            % (studio_dir, test_ids))
        home = tempfile.mkdtemp(prefix="ci-home-")
        bindir = tempfile.mkdtemp(prefix="ci-bin-")
        os.symlink(sys.executable, os.path.join(bindir, "python3"))
        os.symlink(sys.executable, os.path.join(bindir, "python"))
        for tool in ("ffmpeg", "ffprobe"):
            path = shutil.which(tool)
            if path:
                os.symlink(path, os.path.join(bindir, tool))
        env = {"HOME": home, "PATH": bindir}
        with tempfile.NamedTemporaryFile(
                "w", suffix=".py", delete=False,
                encoding="utf-8") as f:
            f.write(driver)
            driver_path = f.name
        try:
            proc = subprocess.run(
                [sys.executable, driver_path],
                cwd=studio_dir, capture_output=True, text=True,
                env=env, timeout=300)
        finally:
            os.unlink(driver_path)
        out = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, out[-3000:])
        self.assertIn("Ran 3 tests", out, out[-3000:])
        self.assertIn("OK", out, out[-3000:])
        self.assertNotIn("skipped", out.lower(), out[-3000:])


if __name__ == "__main__":
    unittest.main()
