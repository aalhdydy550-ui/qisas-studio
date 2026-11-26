#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات توصيل أوامر SRE في جولة v0.1.60:
reliability-report / failure-classify / incident-probe /
id-mask / runbook-check / failure-drill.

تعمل بـ `python3 -m unittest tests.test_sre_wiring_0160 -v` من
`~/workspace/studio`. بلا شبكة وبلا LLM إطلاقًا — كل المدخلات
ملفات مؤقتة تُبنى هنا.
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio

SIX_COMMANDS = ("reliability-report", "failure-classify",
                "incident-probe", "id-mask", "runbook-check",
                "failure-drill")

EMAIL = "ayman_201511@yahoo.com"

GOOD_RUNS = [
    {"id": "run-1", "kind": "test-suite",
     "started_at": "2026-11-26T10:00:00Z", "duration_s": 120,
     "status": "ok"},
    {"id": "run-2", "kind": "test-suite",
     "started_at": "2026-11-26T11:00:00Z", "duration_s": 130,
     "status": "failed",
     "failure_text": "ModuleNotFoundError: No module named 'piper'",
     "failure_class": "environment"},
    {"id": "run-3", "kind": "publish",
     "started_at": "2026-11-26T12:00:00Z", "duration_s": 45,
     "status": "ok"},
]

GOOD_CONTEXT = {
    "title": "فشل المجموعة بعد ريستارت",
    "failure_text": "ModuleNotFoundError: No module named 'piper' — "
                    "راسل %s" % EMAIL,
    "failure_class": "environment",
    "last_test_failure": "test_check failed",
    "recent_changes": ["أصلحنا lib/check.py"],
    "env_state": {"melt": True, "piper": False, "notes": []},
    "cron_logs": [],
}

FAILING_RUNBOOK = {
    "id": "synthetic-fail",
    "title": "دفتر اصطناعي فيه خطوة فاشلة",
    "for": "اختبار توصيل runbook-check",
    "steps": [
        {"id": "missing-file",
         "title": "ملف غير موجود عمدًا",
         "check": {"type": "file_exists",
                   "path": "{root}/no-such-file-0160.txt"},
         "fix_hint": "لا شيء — الخطوة مقصود فشلها في الاختبار."},
        {"id": "existing-file",
         "title": "ملف موجود",
         "check": {"type": "file_exists",
                   "path": "{root}/present-0160.txt"},
         "fix_hint": "لا شيء — هذه الخطوة تنجح."},
    ],
}


def _capture(fn, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*args, **kwargs)
    return rc, buf.getvalue()


def _write(td, name, text):
    path = os.path.join(td, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def _write_json(td, name, payload):
    return _write(td, name, json.dumps(payload, ensure_ascii=False))


class TestReliabilityReportCmd(unittest.TestCase):
    def test_json_pure(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, "runs.json", GOOD_RUNS)
            rc, out = _capture(studio.cmd_reliability_report, {}, path,
                               as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(parsed["total_runs"], 3)
            self.assertEqual(parsed["failed"], 1)

    def test_window_days(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, "runs.json", GOOD_RUNS)
            rc, out = _capture(studio.cmd_reliability_report, {}, path,
                               window_days=7, as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(parsed["window"]["days"], 7)

    def test_missing_file_returns_2(self):
        rc, _out = _capture(studio.cmd_reliability_report, {},
                            "/tmp/لا-يوجد-سجلات-0160.json", as_json=True)
        self.assertEqual(rc, 2)

    def test_corrupt_json_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "runs.json", "{ليس json")
            rc, _out = _capture(studio.cmd_reliability_report, {}, path,
                                as_json=True)
            self.assertEqual(rc, 2)

    def test_not_a_list_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, "runs.json", {"id": "run-1"})
            rc, _out = _capture(studio.cmd_reliability_report, {}, path,
                                as_json=True)
            self.assertEqual(rc, 2)


class TestFailureClassifyCmd(unittest.TestCase):
    def test_text_json_pure(self):
        rc, out = _capture(
            studio.cmd_failure_classify, {},
            text="ModuleNotFoundError: No module named 'piper'",
            as_json=True)
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["class"], "environment")
        self.assertIn("module_not_found_piper", parsed["signals"])

    def test_file_input(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "fail.txt", "HTTP 429 rate limit from GitHub")
            rc, out = _capture(studio.cmd_failure_classify, {}, file=path,
                               as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(parsed["class"], "external")

    def test_neither_input_returns_2(self):
        rc, _out = _capture(studio.cmd_failure_classify, {}, as_json=True)
        self.assertEqual(rc, 2)

    def test_both_inputs_returns_2(self):
        rc, _out = _capture(studio.cmd_failure_classify, {},
                            text="x", file="/tmp/x.txt", as_json=True)
        self.assertEqual(rc, 2)

    def test_missing_file_returns_2(self):
        rc, _out = _capture(studio.cmd_failure_classify, {},
                            file="/tmp/لا-يوجد-فشل-0160.txt", as_json=True)
        self.assertEqual(rc, 2)


class TestIncidentProbeCmd(unittest.TestCase):
    def test_json_pure(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, "incident.json", GOOD_CONTEXT)
            rc, out = _capture(studio.cmd_incident_probe, {}, path,
                               as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(parsed["likely_root_cause"]["class"],
                             "environment")
            self.assertEqual(len(parsed["hypotheses"]), 3)

    def test_mask_hides_email(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, "incident.json", GOOD_CONTEXT)
            rc, out = _capture(studio.cmd_incident_probe, {}, path,
                               mask=True, as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertNotIn(EMAIL, out)
            self.assertIn("[EMAIL:1]", out)
            self.assertEqual(parsed["likely_root_cause"]["class"],
                             "environment")

    def test_mask_mapping_out_only_in_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, "incident.json", GOOD_CONTEXT)
            mapping_path = os.path.join(td, "mapping.json")
            rc, out = _capture(studio.cmd_incident_probe, {}, path,
                               mask=True, mapping_out=mapping_path,
                               as_json=True)
            self.assertEqual(rc, 0)
            self.assertNotIn(EMAIL, out)
            with open(mapping_path, encoding="utf-8") as f:
                mapping = json.load(f)
            self.assertEqual(mapping.get("EMAIL:1"), EMAIL)

    def test_missing_file_returns_2(self):
        rc, _out = _capture(studio.cmd_incident_probe, {},
                            "/tmp/لا-يوجد-حادثة-0160.json", as_json=True)
        self.assertEqual(rc, 2)

    def test_corrupt_json_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "incident.json", "{ليس json")
            rc, _out = _capture(studio.cmd_incident_probe, {}, path,
                                as_json=True)
            self.assertEqual(rc, 2)

    def test_not_a_dict_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, "incident.json", ["not", "a", "dict"])
            rc, _out = _capture(studio.cmd_incident_probe, {}, path,
                                as_json=True)
            self.assertEqual(rc, 2)


class TestIdMaskCmd(unittest.TestCase):
    def test_mask_text_json_pure(self):
        text = "راسل %s أو اتصل على 01023468196" % EMAIL
        rc, out = _capture(studio.cmd_id_mask, {}, text=text, as_json=True)
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["masked"],
                         "راسل [EMAIL:1] أو اتصل على [PHONE:1]")
        self.assertNotIn(EMAIL, out)

    def test_round_trip_via_mapping_out(self):
        text = "راسل %s" % EMAIL
        with tempfile.TemporaryDirectory() as td:
            mapping_path = os.path.join(td, "mapping.json")
            rc, out = _capture(studio.cmd_id_mask, {}, text=text,
                               mapping_out=mapping_path, as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(parsed["masked"], "راسل [EMAIL:1]")
            self.assertNotIn(EMAIL, out)
            with open(mapping_path, encoding="utf-8") as f:
                mapping = json.load(f)
            self.assertEqual(mapping.get("EMAIL:1"), EMAIL)
            rc, out = _capture(studio.cmd_id_mask, {}, text="راسل [EMAIL:1]",
                               unmask=True, mapping_file=mapping_path,
                               as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(parsed["unmasked"], text)

    def test_file_input(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "note.txt", "الحساب %s" % EMAIL)
            rc, out = _capture(studio.cmd_id_mask, {}, file=path,
                               as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(parsed["masked"], "الحساب [EMAIL:1]")

    def test_redact_has_no_mapping(self):
        text = "api_key=secret123 ولا بريد %s" % EMAIL
        rc, out = _capture(studio.cmd_id_mask, {}, text=text, redact=True,
                           as_json=True)
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertIn("[REDACTED]", parsed["redacted"])
        self.assertNotIn("secret123", out)
        self.assertNotIn("mapping", parsed)

    def test_neither_input_returns_2(self):
        rc, _out = _capture(studio.cmd_id_mask, {}, as_json=True)
        self.assertEqual(rc, 2)

    def test_unmask_without_mapping_returns_2(self):
        rc, _out = _capture(studio.cmd_id_mask, {}, text="راسل [EMAIL:1]",
                            unmask=True, as_json=True)
        self.assertEqual(rc, 2)

    def test_missing_file_returns_2(self):
        rc, _out = _capture(studio.cmd_id_mask, {},
                            file="/tmp/لا-يوجد-نص-0160.txt", as_json=True)
        self.assertEqual(rc, 2)


class TestRunbookCheckCmd(unittest.TestCase):
    def test_failing_synthetic_runbook_returns_1(self):
        with tempfile.TemporaryDirectory() as td:
            _write(td, "present-0160.txt", "موجود")
            path = _write_json(td, "runbook.json", FAILING_RUNBOOK)
            rc, out = _capture(studio.cmd_runbook_check, {},
                               runbook_file=path, root=td, as_json=True)
            self.assertEqual(rc, 1)
            parsed = json.loads(out)
            self.assertEqual(parsed["summary"]["failed"], 1)
            self.assertEqual(parsed["summary"]["passed"], 1)
            self.assertFalse(parsed["summary"]["ok"])

    def test_passing_synthetic_runbook_returns_0(self):
        passing = dict(FAILING_RUNBOOK)
        passing["steps"] = [FAILING_RUNBOOK["steps"][1]]
        with tempfile.TemporaryDirectory() as td:
            _write(td, "present-0160.txt", "موجود")
            path = _write_json(td, "runbook.json", passing)
            rc, out = _capture(studio.cmd_runbook_check, {},
                               runbook_file=path, root=td, as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertTrue(parsed["summary"]["ok"])

    def test_builtin_runbook_json_pure(self):
        rc, out = _capture(studio.cmd_runbook_check, {},
                           runbook="env-restore", as_json=True)
        # الرمز يعتمد على حالة البيئة الحية (0 أو 1)، لكن
        # المخرج JSON خالص دائمًا وله ملخص.
        self.assertIn(rc, (0, 1))
        parsed = json.loads(out)
        self.assertEqual(parsed["id"], "env-restore")
        self.assertIn("summary", parsed)

    def test_neither_source_returns_2(self):
        rc, _out = _capture(studio.cmd_runbook_check, {}, as_json=True)
        self.assertEqual(rc, 2)

    def test_both_sources_returns_2(self):
        rc, _out = _capture(studio.cmd_runbook_check, {},
                            runbook="env-restore",
                            runbook_file="/tmp/x.json", as_json=True)
        self.assertEqual(rc, 2)

    def test_unknown_builtin_returns_2(self):
        rc, _out = _capture(studio.cmd_runbook_check, {},
                            runbook="no-such-runbook", as_json=True)
        self.assertEqual(rc, 2)

    def test_missing_file_returns_2(self):
        rc, _out = _capture(studio.cmd_runbook_check, {},
                            runbook_file="/tmp/لا-يوجد-دفتر-0160.json",
                            as_json=True)
        self.assertEqual(rc, 2)

    def test_corrupt_file_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "runbook.json", "{ليس json")
            rc, _out = _capture(studio.cmd_runbook_check, {},
                                runbook_file=path, as_json=True)
            self.assertEqual(rc, 2)


class TestFailureDrillCmd(unittest.TestCase):
    def test_all_json_pure(self):
        rc, out = _capture(studio.cmd_failure_drill, {}, as_json=True)
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["summary"]["total"], 3)
        self.assertEqual(parsed["summary"]["passed"], 3)
        self.assertTrue(parsed["summary"]["ok"])

    def test_single_drill(self):
        rc, out = _capture(studio.cmd_failure_drill, {}, drill="pillow-old",
                           as_json=True)
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["id"], "pillow-old")
        self.assertEqual(parsed["status"], "pass")

    def test_unknown_drill_returns_2(self):
        rc, _out = _capture(studio.cmd_failure_drill, {},
                            drill="no-such-drill", as_json=True)
        self.assertEqual(rc, 2)

    def test_drill_and_all_returns_2(self):
        rc, _out = _capture(studio.cmd_failure_drill, {},
                            drill="pillow-old", all_drills=True,
                            as_json=True)
        self.assertEqual(rc, 2)

    def test_workdir_kept(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = os.path.join(td, "work")
            rc, out = _capture(studio.cmd_failure_drill, {},
                               drill="broken-piper-link", workdir=workdir,
                               keep=True, as_json=True)
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isdir(workdir))
            self.assertTrue(os.path.islink(os.path.join(workdir, "piper")))


class TestSreDispatch0160(unittest.TestCase):
    def test_help_lists_six_commands(self):
        studio_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        proc = subprocess.run(
            [sys.executable, "studio.py", "--help"],
            cwd=studio_dir, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0)
        for cmd in SIX_COMMANDS:
            self.assertIn(cmd, proc.stdout)

    def test_help_ar_lists_six_commands(self):
        argv = ["studio.py", "help-ar"]
        with mock.patch.object(sys, "argv", argv):
            rc, out = _capture(studio.main)
        self.assertEqual(rc, 0)
        for cmd in SIX_COMMANDS:
            self.assertIn(cmd, out)

    def test_dispatch_failure_classify(self):
        argv = ["studio.py", "failure-classify",
                "--text", "ModuleNotFoundError: No module named 'piper'",
                "--json"]
        with mock.patch.object(sys, "argv", argv):
            rc, out = _capture(studio.main)
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["class"], "environment")

    def test_dispatch_failure_drill_unknown_returns_2(self):
        argv = ["studio.py", "failure-drill", "--drill", "no-such-drill",
                "--json"]
        with mock.patch.object(sys, "argv", argv):
            rc, _out = _capture(studio.main)
        self.assertEqual(rc, 2)

    def test_dispatch_reliability_report(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, "runs.json", GOOD_RUNS)
            argv = ["studio.py", "reliability-report",
                    "--runs-json", path, "--json"]
            with mock.patch.object(sys, "argv", argv):
                rc, out = _capture(studio.main)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(parsed["total_runs"], 3)

    def test_dispatch_id_mask_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            mapping_path = os.path.join(td, "mapping.json")
            argv = ["studio.py", "id-mask", "--text", "راسل %s" % EMAIL,
                    "--mapping-out", mapping_path, "--json"]
            with mock.patch.object(sys, "argv", argv):
                rc, out = _capture(studio.main)
            self.assertEqual(rc, 0)
            self.assertNotIn(EMAIL, out)
            argv = ["studio.py", "id-mask", "--unmask",
                    "--mapping", mapping_path,
                    "--text", "راسل [EMAIL:1]", "--json"]
            with mock.patch.object(sys, "argv", argv):
                rc, out = _capture(studio.main)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(parsed["unmasked"], "راسل %s" % EMAIL)

    def test_dispatch_runbook_check_failing_returns_1(self):
        with tempfile.TemporaryDirectory() as td:
            _write(td, "present-0160.txt", "موجود")
            path = _write_json(td, "runbook.json", FAILING_RUNBOOK)
            argv = ["studio.py", "runbook-check", "--runbook-file", path,
                    "--root", td, "--json"]
            with mock.patch.object(sys, "argv", argv):
                rc, out = _capture(studio.main)
            self.assertEqual(rc, 1)
            parsed = json.loads(out)
            self.assertFalse(parsed["summary"]["ok"])

    def test_dispatch_incident_probe_masked(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, "incident.json", GOOD_CONTEXT)
            argv = ["studio.py", "incident-probe", "--context-json", path,
                    "--mask", "--json"]
            with mock.patch.object(sys, "argv", argv):
                rc, out = _capture(studio.main)
            self.assertEqual(rc, 0)
            self.assertNotIn(EMAIL, out)
            self.assertIn("[EMAIL:1]", out)


if __name__ == "__main__":
    unittest.main()
