#!/usr/bin/env python3
"""اختبارات فحص البيئة (doctor) — بلا شبكة وبلا أدوات حقيقية.

كل ما يحتاج نظامًا يُستبدل بمحاكاة (mock): which، وملفات مؤقتة،
وخادم OmniRoute الوهمي.
"""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import doctor


def _fake_response(status=200):
    resp = mock.MagicMock()
    resp.status = status
    resp.__enter__ = mock.MagicMock(return_value=resp)
    resp.__exit__ = mock.MagicMock(return_value=False)
    return resp


class TestRunChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        # ملفات وهمية لكل ما يفحصه doctor
        (self.root / "model.onnx").write_text("x")
        (self.root / "editor.py").write_text("x")
        (self.root / "badge.png").write_text("x")
        (self.root / "config.yaml").write_text("x")
        (self.root / "openmontage").mkdir()
        (self.root / "concat-bin").write_text("x")
        (self.root / "ensure-env.sh").write_text("x")
        (self.root / "yt-python").write_text("x")
        self.cfg = {
            "openmontage": {"root": str(self.root / "openmontage")},
            "concat": {"bin": str(self.root / "concat-bin")},
            "headless": {"editor": str(self.root / "editor.py")},
            "paths": {"videos_dir": str(self.root / "videos"),
                      "runs_dir": str(self.root / "runs")},
        }

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, which_map=None, fallbacks=None):
        which_map = which_map or {}
        real_which = doctor.shutil.which

        def fake_which(cmd):
            if cmd in which_map:
                return which_map[cmd]
            return real_which(cmd)

        fb = doctor._WHICH_FALLBACKS if fallbacks is None else fallbacks
        with mock.patch("lib.doctor.shutil.which", side_effect=fake_which), \
             mock.patch("lib.doctor._WHICH_FALLBACKS", fb), \
             mock.patch("lib.doctor.urllib.request.urlopen",
                        return_value=_fake_response(200)), \
             mock.patch("lib.doctor.long_narration.PIPER_MODEL",
                        str(self.root / "model.onnx")), \
             mock.patch("lib.doctor.DEFAULT_PATHS", {
                 **doctor.DEFAULT_PATHS,
                 "logo_badge": str(self.root / "badge.png"),
                 "config": str(self.root / "config.yaml"),
                 "ensure_env": str(self.root / "ensure-env.sh"),
                 "youtube_venv": str(self.root / "yt-python"),
             }), \
             mock.patch("lib.doctor.subprocess.run") as run_mock:
            run_mock.return_value = mock.MagicMock(stdout="Noto Naskh Arabic")
            return doctor.run_checks(self.cfg)

    def test_all_core_checks_pass(self):
        checks = self._run()
        by_name = {c["name"]: c for c in checks}
        self.assertTrue(by_name["ffmpeg (أساسي للريندر)"]["ok"])
        self.assertTrue(by_name["موديل صوت Piper "
                                "(ar_JO-kareem-medium)"]["ok"])
        self.assertTrue(by_name["محرر headless-editor "
                                "(خلفية التجربة)"]["ok"])
        self.assertTrue(by_name["شارة شعار «قصص وعبر»"]["ok"])
        text, errors, warnings = doctor.format_report(checks)
        self.assertEqual(errors, 0)
        self.assertIn("النظام جاهز", text)

    def test_missing_piper_model_is_error(self):
        (self.root / "model.onnx").unlink()
        checks = self._run()
        bad = [c for c in checks
               if "موديل صوت Piper" in c["name"]][0]
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["level"], "error")
        _, errors, _ = doctor.format_report(checks)
        self.assertGreater(errors, 0)

    def test_missing_optional_tool_is_warning_only(self):
        checks = self._run(which_map={"yt-dlp": None},
                           fallbacks={})
        bad = [c for c in checks if "yt-dlp" in c["name"]][0]
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["level"], "warn")

    def test_home_fallback_counts_when_path_link_missing(self):
        # بعد إعادة تشغيل الـVM تُمسح روابط /usr/local/bin فيغيب piper
        # عن PATH رغم وجود ثنائيه في ~/.local/bin — يجب أن يجده doctor.
        fake_piper = self.root / "piper"
        fake_piper.write_text("x")
        checks = self._run(which_map={"piper": None},
                           fallbacks={"piper": (str(fake_piper),)})
        good = [c for c in checks if c["name"].startswith("Piper (")][0]
        self.assertTrue(good["ok"])
        self.assertEqual(good["detail"], str(fake_piper))

    def test_no_path_no_fallback_is_failure(self):
        checks = self._run(which_map={"piper": None}, fallbacks={})
        bad = [c for c in checks if c["name"].startswith("Piper (")][0]
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["level"], "error")

    def test_format_report_never_claims_success_on_failure(self):
        checks = [{"name": "x", "ok": False, "level": "error",
                   "detail": "غائب", "fix": ""}]
        text, errors, _ = doctor.format_report(checks)
        self.assertEqual(errors, 1)
        self.assertNotIn("كل الفحوصات سليمة", text)
        self.assertIn("خطأ أساسي", text)


class TestEnsureConfig(unittest.TestCase):
    def test_creates_from_example_once(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "config.example.yaml").write_text("a: 1\n")
            self.assertTrue(doctor.ensure_config(d))
            self.assertTrue(os.path.isfile(os.path.join(d, "config.yaml")))
            # إعادة التشغيل آمنة: لا يعيد الكتابة
            self.assertFalse(doctor.ensure_config(d))

    def test_no_example_no_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(doctor.ensure_config(d))


class TestCmdDoctor(unittest.TestCase):
    def test_returns_zero_when_no_errors(self):
        fake = [{"name": "x", "ok": True, "level": "error",
                 "detail": "ok", "fix": ""}]
        with mock.patch("lib.doctor.run_checks", return_value=fake):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                self.assertEqual(studio.cmd_doctor({}), 0)

    def test_returns_one_on_error(self):
        fake = [{"name": "x", "ok": False, "level": "error",
                 "detail": "غائب", "fix": ""}]
        with mock.patch("lib.doctor.run_checks", return_value=fake):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                self.assertEqual(studio.cmd_doctor({}), 1)


if __name__ == "__main__":
    unittest.main()
