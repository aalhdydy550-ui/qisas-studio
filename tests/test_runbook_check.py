#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات دفاتر التشغيل المقروءة آليًا (lib.runbook_check).

تعمل بـ `python3 -m unittest tests.test_runbook_check -v` من مجلد
studio. الدفاتر الاصطناعية تُبنى في مجلد مؤقت (tmp) فقط؛
والدفتران المشحونان يُقرآن من داخل الشجرة (lib/runbooks/).
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import runbook_check
from lib.runbook_check import RunbookError, check_runbook, list_runbooks, load_runbook

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNBOOKS_DIR = os.path.join(REPO_ROOT, "lib", "runbooks")


def _step(step_id, check, title="خطوة"):
    return {"id": step_id, "title": title, "check": check,
            "fix_hint": "أصلحها يدويًا."}


def _runbook(steps, runbook_id="test"):
    return {"id": runbook_id, "title": "دفتر اختبار",
            "for": "اختبار", "steps": steps}


class TestSyntheticRunbook(unittest.TestCase):
    def test_pass_fail_skip_mix(self):
        with tempfile.TemporaryDirectory() as tmp:
            present = os.path.join(tmp, "present.txt")
            with open(present, "w", encoding="utf-8") as handle:
                handle.write("x")
            runbook = _runbook([
                _step("ok-file", {"type": "file_exists", "path": "{root}/present.txt"}),
                _step("missing-file", {"type": "file_exists", "path": "{root}/absent.txt"}),
                _step("unknown", {"type": "no-such-check"}),
            ])
            result = check_runbook(runbook, root=tmp)
            by_id = {s["id"]: s for s in result["steps"]}
            self.assertEqual(by_id["ok-file"]["status"], "pass")
            self.assertEqual(by_id["missing-file"]["status"], "fail")
            self.assertEqual(by_id["unknown"]["status"], "skip")
            self.assertIn("غير معروف", by_id["unknown"]["detail"])
            self.assertEqual(result["summary"], {
                "total": 3, "passed": 1, "failed": 1, "skipped": 1, "ok": False,
            })
            self.assertEqual(result["id"], "test")

    def test_ok_true_when_no_failures(self):
        runbook = _runbook([
            _step("a", {"type": "python_import", "module": "json"}),
            _step("b", {"type": "mystery"}),
        ])
        result = check_runbook(runbook)
        self.assertTrue(result["summary"]["ok"])
        self.assertEqual(result["summary"]["skipped"], 1)

    def test_unknown_check_type_skips(self):
        result = check_runbook(_runbook([
            _step("x", {"type": "teleport"}),
        ]))
        self.assertEqual(result["steps"][0]["status"], "skip")

    def test_root_substitution(self):
        with tempfile.TemporaryDirectory() as tmp:
            sub = os.path.join(tmp, "sub")
            os.makedirs(sub)
            with open(os.path.join(sub, "file.txt"), "w", encoding="utf-8") as handle:
                handle.write("x")
            runbook = _runbook([
                _step("nested", {"type": "file_exists",
                                 "path": "{root}/sub/file.txt"}),
            ])
            self.assertEqual(
                check_runbook(runbook, root=tmp)["steps"][0]["status"], "pass")
            # جذر آخر لا يحوي الملف → فشل، أي أن {root} استُبدل فعلًا.
            with tempfile.TemporaryDirectory() as other:
                self.assertEqual(
                    check_runbook(runbook, root=other)["steps"][0]["status"],
                    "fail")

    def test_tool_check(self):
        runbook = _runbook([
            _step("py", {"type": "tool", "tool": sys.executable.split(os.sep)[-1]
                         if os.sep in sys.executable else "python3",
                         "args": ["--version"]}),
            _step("ghost", {"type": "tool", "tool": "definitely-not-a-tool-xyz"}),
        ])
        result = check_runbook(runbook)
        by_id = {s["id"]: s for s in result["steps"]}
        self.assertEqual(by_id["py"]["status"], "pass")
        self.assertEqual(by_id["ghost"]["status"], "fail")

    def test_symlink_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "target.txt")
            with open(target, "w", encoding="utf-8") as handle:
                handle.write("x")
            good = os.path.join(tmp, "good-link")
            os.symlink(target, good)
            broken = os.path.join(tmp, "broken-link")
            os.symlink(os.path.join(tmp, "nope.txt"), broken)
            runbook = _runbook([
                _step("good", {"type": "symlink_target", "path": good,
                               "must_exist": True}),
                _step("broken", {"type": "symlink_target", "path": broken,
                                 "must_exist": True}),
                _step("notlink", {"type": "symlink_target", "path": target,
                                  "must_exist": True}),
            ])
            result = check_runbook(runbook, root=tmp)
            by_id = {s["id"]: s for s in result["steps"]}
            self.assertEqual(by_id["good"]["status"], "pass")
            self.assertEqual(by_id["broken"]["status"], "fail")
            self.assertEqual(by_id["notlink"]["status"], "fail")

    def test_python_import(self):
        runbook = _runbook([
            _step("ok", {"type": "python_import", "module": "json"}),
            _step("bad", {"type": "python_import", "module": "no_such_module_xyz"}),
        ])
        result = check_runbook(runbook)
        by_id = {s["id"]: s for s in result["steps"]}
        self.assertEqual(by_id["ok"]["status"], "pass")
        self.assertEqual(by_id["bad"]["status"], "fail")

    def test_json_field_equals_and_not_equals(self):
        with tempfile.TemporaryDirectory() as tmp:
            status_path = os.path.join(tmp, "status.json")
            with open(status_path, "w", encoding="utf-8") as handle:
                json.dump({"status": "pending", "last_result": "ok"}, handle)
            runbook = _runbook([
                _step("eq-ok", {"type": "json_field", "path": "{root}/status.json",
                                "field": "status", "equals": "pending"}),
                _step("eq-bad", {"type": "json_field", "path": "{root}/status.json",
                                 "field": "status", "equals": "published"}),
                _step("ne-ok", {"type": "json_field", "path": "{root}/status.json",
                                "field": "status", "not_equals": "published"}),
                _step("ne-bad", {"type": "json_field", "path": "{root}/status.json",
                                 "field": "last_result", "not_equals": "ok"}),
                _step("missing-field", {"type": "json_field",
                                        "path": "{root}/status.json",
                                        "field": "nope", "equals": "x"}),
                _step("missing-file", {"type": "json_field",
                                       "path": "{root}/gone.json",
                                       "field": "status", "equals": "x"}),
            ])
            result = check_runbook(runbook, root=tmp)
            by_id = {s["id"]: s for s in result["steps"]}
            self.assertEqual(by_id["eq-ok"]["status"], "pass")
            self.assertEqual(by_id["eq-bad"]["status"], "fail")
            self.assertEqual(by_id["ne-ok"]["status"], "pass")
            self.assertEqual(by_id["ne-bad"]["status"], "fail")
            self.assertEqual(by_id["missing-field"]["status"], "fail")
            self.assertEqual(by_id["missing-file"]["status"], "fail")

    def test_video_duration_with_mocked_ffprobe(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = os.path.join(tmp, "final.mp4")
            with open(video, "wb") as handle:
                handle.write(b"fake")
            runbook = _runbook([
                _step("dur", {"type": "video_duration", "path": "{root}/final.mp4",
                              "min": 40, "max": 60}),
            ])

            def fake_run_ok(*args, **kwargs):
                return mock.Mock(returncode=0, stdout=b"50.0\n")

            def fake_run_short(*args, **kwargs):
                return mock.Mock(returncode=0, stdout=b"30.0\n")

            with mock.patch.object(runbook_check.subprocess, "run", fake_run_ok):
                self.assertEqual(
                    check_runbook(runbook, root=tmp)["steps"][0]["status"], "pass")
            with mock.patch.object(runbook_check.subprocess, "run", fake_run_short):
                self.assertEqual(
                    check_runbook(runbook, root=tmp)["steps"][0]["status"], "fail")
            # بلا ffprobe → skip موثّق.
            with mock.patch.object(runbook_check.shutil, "which", return_value=None):
                step = check_runbook(runbook, root=tmp)["steps"][0]
                self.assertEqual(step["status"], "skip")
                self.assertIn("ffprobe", step["detail"])


class TestLoadRunbook(unittest.TestCase):
    def _write_tmp(self, tmp, name, content):
        path = os.path.join(tmp, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def test_corrupt_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_tmp(tmp, "bad.json", "{not json")
            with self.assertRaises(RunbookError) as ctx:
                load_runbook(path)
            self.assertIn("تالف", str(ctx.exception))

    def test_missing_file_raises(self):
        with self.assertRaises(RunbookError):
            load_runbook("/tmp/definitely-no-such-runbook-xyz.json")

    def test_missing_fields_raise(self):
        cases = [
            {"title": "x", "for": "y", "steps": [_step("a", {"type": "tool"})]},
            {"id": "x", "for": "y", "steps": [_step("a", {"type": "tool"})]},
            {"id": "x", "title": "t", "steps": [_step("a", {"type": "tool"})]},
            {"id": "x", "title": "t", "for": "y", "steps": []},
            {"id": "x", "title": "t", "for": "y"},
            {"id": "x", "title": "t", "for": "y",
             "steps": [{"id": "a", "title": "t"}]},
            {"id": "x", "title": "t", "for": "y",
             "steps": [_step("a", {"type": "tool"}),
                       _step("a", {"type": "tool"})]},
            ["not", "a", "dict"],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            for i, data in enumerate(cases):
                path = self._write_tmp(tmp, "case%d.json" % i, json.dumps(data))
                with self.assertRaises(RunbookError, msg="case %d" % i):
                    load_runbook(path)

    def test_valid_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_tmp(tmp, "ok.json", json.dumps(_runbook([
                _step("a", {"type": "python_import", "module": "json"}),
            ])))
            loaded = load_runbook(path)
            self.assertEqual(loaded["id"], "test")
            self.assertEqual(len(loaded["steps"]), 1)


class TestShippedRunbooks(unittest.TestCase):
    def test_both_load_and_have_unique_ids(self):
        for name in ("env_restore.json", "publish_failure.json"):
            path = os.path.join(RUNBOOKS_DIR, name)
            runbook = load_runbook(path)
            self.assertGreaterEqual(len(runbook["steps"]), 5, name)
            ids = [s["id"] for s in runbook["steps"]]
            self.assertEqual(len(ids), len(set(ids)), name)
            for step in runbook["steps"]:
                self.assertIn("type", step["check"])
                self.assertTrue(step["fix_hint"].strip())

    def test_list_runbooks(self):
        ids = list_runbooks(RUNBOOKS_DIR)
        self.assertEqual(ids, ["env-restore", "publish-failure"])

    def test_list_runbooks_missing_dir(self):
        with self.assertRaises(RunbookError):
            list_runbooks("/tmp/definitely-no-such-dir-xyz")

    def test_publish_failure_end_to_end_with_mocked_ffprobe(self):
        runbook = load_runbook(os.path.join(RUNBOOKS_DIR, "publish_failure.json"))
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("final.mp4", "caption.txt"):
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as handle:
                    handle.write("x")
            with open(os.path.join(tmp, "publish-status.json"),
                      "w", encoding="utf-8") as handle:
                json.dump({"status": "pending"}, handle)
            with open(os.path.join(tmp, "publish-log.json"),
                      "w", encoding="utf-8") as handle:
                json.dump({"last_result": "ok"}, handle)

            def fake_run(*args, **kwargs):
                return mock.Mock(returncode=0, stdout=b"50.0\n")

            with mock.patch.object(runbook_check.subprocess, "run", fake_run):
                result = check_runbook(runbook, root=tmp)
            self.assertTrue(result["summary"]["ok"], result)
            self.assertEqual(result["summary"]["passed"], 5)


if __name__ == "__main__":
    unittest.main()
