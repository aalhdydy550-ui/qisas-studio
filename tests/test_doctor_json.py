#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات `doctor --json` + فحوص المضيف + `--fix`
(جولة v0.1.63، بند 3 — عقد ع20).

بلا شبكة حقيقية (urlopen محقون) وبلا ملفات خارج الشجرة
(tempfile + محاكاة which والمسارات) — والفحوصات الـ28
الأساسية تُتحقق أنها ما زالت 27 في run_checks + فحص
الترخيص، وخضراء في بيئة محاكاة كاملة.
"""
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import doctor


def _fake_response(status=200):
    resp = mock.MagicMock()
    resp.status = status
    resp.__enter__ = mock.MagicMock(return_value=resp)
    resp.__exit__ = mock.MagicMock(return_value=False)
    return resp


class _CoreHarness:
    """بيئة محاكاة كاملة لـ run_checks (كما في test_doctor.py):
    كل أداة حاضرة افتراضيًا ما لم يُصرَّح بغيابها."""

    def __init__(self, test):
        self.test = test
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
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

    def cleanup(self):
        self.tmp.cleanup()

    def run(self, which_map=None, fallbacks=None, paths=None):
        defaults = {cmd: "/usr/bin/%s" % cmd for cmd in
                    ("ffmpeg", "ffprobe", "git", "node", "npm", "melt",
                     "yt-dlp", "piper", "omniroute")}
        defaults.update(which_map or {})
        which_map = defaults
        real_which = doctor.shutil.which

        def fake_which(cmd):
            if cmd in which_map:
                return which_map[cmd]
            return real_which(cmd)

        fb = doctor._WHICH_FALLBACKS if fallbacks is None else fallbacks
        default_paths = {
            **doctor.DEFAULT_PATHS,
            "logo_badge": str(self.root / "badge.png"),
            "config": str(self.root / "config.yaml"),
            "ensure_env": str(self.root / "ensure-env.sh"),
            "youtube_venv": str(self.root / "yt-python"),
        }
        if paths:
            default_paths.update(paths)
        with mock.patch("lib.doctor.shutil.which",
                        side_effect=fake_which), \
             mock.patch("lib.doctor._WHICH_FALLBACKS", fb), \
             mock.patch("lib.doctor._protect_check",
                        return_value={
                            "name": "حماية المشروع (protect)",
                            "ok": True, "level": "ok",
                            "detail": "سليم", "fix": ""}), \
             mock.patch("lib.doctor.urllib.request.urlopen",
                        return_value=_fake_response(200)), \
             mock.patch("lib.doctor.long_narration.PIPER_MODEL",
                        str(self.root / "model.onnx")), \
             mock.patch("lib.doctor.DEFAULT_PATHS", default_paths), \
             mock.patch("lib.doctor.subprocess.run") as run_mock:
            run_mock.return_value = mock.MagicMock(
                stdout="Noto Naskh Arabic")
            return doctor.run_checks(self.cfg)


class TestJsonReportShape(unittest.TestCase):
    def test_report_keys_and_entry_keys(self):
        checks = [
            {"name": "أ", "ok": True, "level": "error",
             "detail": "سليم", "fix": ""},
            {"name": "ب", "ok": False, "level": "error",
             "detail": "غائب", "fix": "ثبّته"},
            {"name": "ج", "ok": False, "level": "warn",
             "detail": "اختياري", "fix": "تجاهله"},
        ]
        report = doctor.to_json_report(checks)
        self.assertEqual(set(report), {"ok", "problems",
                                       "warnings", "checks"})
        self.assertFalse(report["ok"])
        self.assertEqual(report["problems"], 1)
        self.assertEqual(report["warnings"], 1)
        self.assertEqual(len(report["checks"]), 3)
        for entry in report["checks"]:
            self.assertEqual(set(entry),
                             {"id", "status", "message", "fix"})
        by_status = {e["status"] for e in report["checks"]}
        self.assertEqual(by_status, {"pass", "fail", "warn"})
        fail = [e for e in report["checks"]
                if e["status"] == "fail"][0]
        self.assertIn("ب", fail["message"])
        self.assertEqual(fail["fix"], "ثبّته")

    def test_ids_unique_even_for_duplicate_names(self):
        checks = [{"name": "نفس الاسم", "ok": True, "level": "error",
                   "detail": "x", "fix": ""} for _ in range(3)]
        ids = [e["id"] for e in doctor.to_json_report(checks)["checks"]]
        self.assertEqual(len(set(ids)), 3)

    def test_empty_checks_is_ok(self):
        report = doctor.to_json_report([])
        self.assertEqual(report, {"ok": True, "problems": 0,
                                  "warnings": 0, "checks": []})


class TestJsonExitCode(unittest.TestCase):
    def test_zero_when_all_pass(self):
        checks = [{"name": "أ", "ok": True, "level": "error",
                   "detail": "ok", "fix": ""}]
        self.assertEqual(doctor.json_exit_code(checks), 0)

    def test_zero_when_only_warnings(self):
        checks = [{"name": "أ", "ok": False, "level": "warn",
                   "detail": "اختياري", "fix": "تجاهله"}]
        self.assertEqual(doctor.json_exit_code(checks), 0)
        self.assertTrue(doctor.to_json_report(checks)["ok"])

    def test_seven_on_single_fail(self):
        checks = [{"name": "أ", "ok": True, "level": "error",
                   "detail": "ok", "fix": ""},
                  {"name": "ب", "ok": False, "level": "error",
                   "detail": "غائب", "fix": "ثبّته"}]
        self.assertEqual(doctor.json_exit_code(checks), 7)
        self.assertEqual(doctor.DOCTOR_FAIL_EXIT, 7)

    def test_fail_without_fix_gets_default_fix(self):
        checks = [{"name": "أ", "ok": False, "level": "error",
                   "detail": "غائب", "fix": ""}]
        entry = doctor.to_json_report(checks)["checks"][0]
        self.assertEqual(entry["status"], "fail")
        self.assertTrue(entry["fix"])

    def test_warn_without_fix_gets_default_fix(self):
        checks = [{"name": "أ", "ok": False, "level": "warn",
                   "detail": "غائب"}]
        entry = doctor.to_json_report(checks)["checks"][0]
        self.assertEqual(entry["status"], "warn")
        self.assertTrue(entry["fix"])


class TestCoreChecksStillGreen(unittest.TestCase):
    def setUp(self):
        self.h = _CoreHarness(self)

    def tearDown(self):
        self.h.cleanup()

    def test_run_checks_still_27(self):
        checks = self.h.run()
        self.assertEqual(len(checks), 27)

    def test_all_pass_report_is_ok(self):
        checks = self.h.run()
        report = doctor.to_json_report(checks)
        self.assertTrue(report["ok"])
        self.assertEqual(report["problems"], 0)
        self.assertEqual(doctor.json_exit_code(checks), 0)
        _, errors, _ = doctor.format_report(checks)
        self.assertEqual(errors, 0)

    def test_every_real_failure_carries_nonempty_fix(self):
        # غيّب أدوات وملفات: كل FAIL الناتج يجب أن يحمل fix.
        (self.h.root / "badge.png").unlink()
        (self.h.root / "ensure-env.sh").unlink()
        checks = self.h.run(
            which_map={"ffmpeg": None, "piper": None, "melt": None},
            fallbacks={},
            paths={"logo_badge": str(self.h.root / "badge-missing.png"),
                   "ensure_env": str(self.h.root / "ensure-missing.sh")})
        report = doctor.to_json_report(checks)
        self.assertFalse(report["ok"])
        self.assertEqual(doctor.json_exit_code(checks), 7)
        for entry in report["checks"]:
            if entry["status"] == "fail":
                self.assertTrue(entry["fix"],
                                "فحص FAIL بلا fix: %s" % entry)


class TestHostChecks(unittest.TestCase):
    def test_shape_and_count(self):
        with mock.patch("lib.doctor.shutil.which",
                        return_value="/usr/bin/x"):
            checks = doctor.run_host_checks(
                urlopen=lambda *a, **k: _fake_response(200),
                min_free_gb=0)
        self.assertEqual(len(checks), 4)
        for check in checks:
            self.assertEqual(set(check),
                             {"name", "ok", "level", "detail", "fix"})
        names = " ".join(c["name"] for c in checks)
        self.assertIn("الشبكة", names)
        self.assertIn("مساحة القرص", names)
        self.assertIn("melt", names)
        self.assertIn("Piper", names)

    def test_network_ok_when_reachable(self):
        checks = doctor.run_host_checks(
            urlopen=lambda *a, **k: _fake_response(200),
            min_free_gb=0)
        net = [c for c in checks if "الشبكة" in c["name"]][0]
        self.assertTrue(net["ok"])
        self.assertEqual(net["level"], "warn")

    def test_network_failure_is_warn_not_error(self):
        def boom(*args, **kwargs):
            raise OSError("لا شبكة")

        checks = doctor.run_host_checks(urlopen=boom, min_free_gb=0)
        net = [c for c in checks if "الشبكة" in c["name"]][0]
        self.assertFalse(net["ok"])
        self.assertEqual(net["level"], "warn")
        self.assertTrue(net["fix"])
        # تحذير وحده لا يُسقط تقرير JSON ولا يرفع الخروج إلى 7
        report = doctor.to_json_report(checks)
        self.assertEqual(report["warnings"], 1)

    def test_disk_space_threshold(self):
        with tempfile.TemporaryDirectory() as d:
            ok_checks = doctor.run_host_checks(
                disk_path=d, min_free_gb=0,
                urlopen=lambda *a, **k: _fake_response(200))
            disk = [c for c in ok_checks
                    if "مساحة القرص" in c["name"]][0]
            self.assertTrue(disk["ok"])
            bad_checks = doctor.run_host_checks(
                disk_path=d, min_free_gb=10 ** 9,
                urlopen=lambda *a, **k: _fake_response(200))
            disk = [c for c in bad_checks
                    if "مساحة القرص" in c["name"]][0]
            self.assertFalse(disk["ok"])
            self.assertTrue(disk["fix"])

    def test_disk_missing_path_is_warn_with_fix(self):
        checks = doctor.run_host_checks(
            disk_path="/nonexistent-path-xyz",
            urlopen=lambda *a, **k: _fake_response(200))
        disk = [c for c in checks if "مساحة القرص" in c["name"]][0]
        self.assertFalse(disk["ok"])
        self.assertEqual(disk["level"], "warn")
        self.assertTrue(disk["fix"])

    def test_host_tools_follow_which(self):
        def fake_which(cmd):
            return "/usr/bin/melt" if cmd == "melt" else None

        with mock.patch("lib.doctor.shutil.which",
                        side_effect=fake_which), \
             mock.patch("lib.doctor._WHICH_FALLBACKS", {}):
            checks = doctor.run_host_checks(
                urlopen=lambda *a, **k: _fake_response(200),
                min_free_gb=0)
        melt = [c for c in checks if "melt" in c["name"]][0]
        piper = [c for c in checks if "Piper" in c["name"]][0]
        self.assertTrue(melt["ok"])
        self.assertFalse(piper["ok"])


class TestRunJsonReport(unittest.TestCase):
    def test_combines_core_and_host(self):
        core = [{"name": "أ", "ok": True, "level": "error",
                 "detail": "ok", "fix": ""}]
        with mock.patch("lib.doctor.run_checks",
                        return_value=core), \
             mock.patch("lib.doctor.shutil.which",
                        return_value="/usr/bin/x"):
            report, code = doctor.run_json_report(
                urlopen=lambda *a, **k: _fake_response(200),
                min_free_gb=0)
        self.assertEqual(len(report["checks"]), 1 + 4)
        self.assertTrue(report["ok"])
        self.assertEqual(code, 0)

    def test_core_only_without_host(self):
        core = [{"name": "أ", "ok": False, "level": "error",
                 "detail": "غائب", "fix": "ثبّته"}]
        with mock.patch("lib.doctor.run_checks",
                        return_value=core):
            report, code = doctor.run_json_report(include_host=False)
        self.assertEqual(len(report["checks"]), 1)
        self.assertEqual(code, 7)


class TestApplyFixes(unittest.TestCase):
    def test_fixes_config_yaml_and_rechecks(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "config.example.yaml").write_text("a: 1\n")
            checks = [{"name": "ملف config.yaml", "ok": False,
                       "level": "warn", "detail": "غير موجود",
                       "fix": "cp config.example.yaml config.yaml"}]
            fixed_check = [{"name": "ملف config.yaml", "ok": True,
                            "level": "warn", "detail": "موجود",
                            "fix": ""}]
            out = doctor.apply_fixes(
                checks, studio_dir=d,
                recheck=lambda: fixed_check)
            self.assertEqual(out["fixed"], ["ملف config.yaml"])
            self.assertEqual(out["unfixed"], [])
            self.assertTrue(out["checks"][0]["ok"])
            self.assertTrue(os.path.isfile(
                os.path.join(d, "config.yaml")))

    def test_fixes_writable_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            videos = os.path.join(d, "videos")
            runs = os.path.join(d, "runs")
            cfg = {"paths": {"videos_dir": videos,
                             "runs_dir": runs}}
            checks = [{"name": "مجلد الفيديو (قابل للكتابة)",
                       "ok": False, "level": "error",
                       "detail": "غير موجود: %s" % videos, "fix": "x"}]
            out = doctor.apply_fixes(
                checks, cfg=cfg, recheck=lambda: [])
            self.assertEqual(out["fixed"],
                             ["مجلد الفيديو (قابل للكتابة)"])
            self.assertTrue(os.path.isdir(videos))

    def test_unfixable_check_stays_unfixed(self):
        checks = [{"name": "موديل صوت Piper (ar_JO-kareem-medium)",
                   "ok": False, "level": "error",
                   "detail": "غير موجود", "fix": "نزّل الموديل"}]
        out = doctor.apply_fixes(checks, recheck=lambda: checks)
        self.assertEqual(out["fixed"], [])
        self.assertEqual(out["unfixed"],
                         ["موديل صوت Piper (ar_JO-kareem-medium)"])
        self.assertEqual(out["checks"], checks)

    def test_passing_checks_are_untouched(self):
        checks = [{"name": "أ", "ok": True, "level": "error",
                   "detail": "ok", "fix": ""}]
        out = doctor.apply_fixes(checks, recheck=lambda: checks)
        self.assertEqual(out["fixed"], [])
        self.assertEqual(out["unfixed"], [])


if __name__ == "__main__":
    unittest.main()
