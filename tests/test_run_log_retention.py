#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات تقطيع القراءة والاحتفاظ 180 يومًا — جولة v0.1.63
(بند 30): lib.run_log وlib.runlog وlib.update_backup.

تعمل بـ `python3 -m unittest discover -s tests -v`.
كل الكتابة في مجلدات مؤقتة — بلا شبكة وبلا ملفات خارج الشجرة.
"""
import datetime
import json
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import run_log, runlog, update_backup

NOW = datetime.datetime(2026, 11, 27, 12, 0, 0,
                        tzinfo=datetime.timezone.utc)
OLD = "2026-04-01T10:00:00+00:00"   # أقدم من 180 يومًا من NOW
NEW = "2026-11-20T10:00:00+00:00"   # أحدث من 180 يومًا من NOW


def _write_run_log_file(out_dir, name, command, started, error=None):
    data = {"schema_version": 1, "correlation_id": name,
            "command": command, "started_at": started,
            "ended_at": started, "duration_seconds": 1.0,
            "status": "failed" if error else "ok",
            "stages": [], "errors": [], "error_count": 0,
            "outputs": {}, "log_path": None, "write_error": None}
    if error:
        data["errors"] = [{"code": "STUDIO-X-001", "title": "خطأ",
                           "original": error, "runbook": "",
                           "category": "x", "stage": None,
                           "at": started}]
        data["error_count"] = 1
    path = os.path.join(out_dir, "run-log-%s.json" % name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    return path


def _set_old_mtime(path):
    old = NOW - datetime.timedelta(days=200)
    stamp = old.timestamp()
    os.utime(path, (stamp, stamp))


class TestRunLogReadLimits(unittest.TestCase):
    def test_list_run_logs_limit_200(self):
        with tempfile.TemporaryDirectory() as td:
            for i in range(5):
                _write_run_log_file(
                    td, "id-%02d" % i, "run",
                    "2026-11-2%dT10:00:00+00:00" % i)
            summaries = run_log.list_run_logs(td)
            self.assertEqual(len(summaries), 5)
            # الأحدث أولًا.
            self.assertEqual(summaries[0]["correlation_id"], "id-04")
            self.assertEqual(len(run_log.list_run_logs(td, limit=2)),
                             2)

    def test_list_run_logs_skips_corrupt(self):
        with tempfile.TemporaryDirectory() as td:
            _write_run_log_file(td, "good", "run",
                                "2026-11-20T10:00:00+00:00")
            with open(os.path.join(td, "run-log-bad.json"), "w",
                      encoding="utf-8") as fh:
                fh.write("{تالف\n")
            self.assertEqual(len(run_log.list_run_logs(td)), 1)

    def test_list_empty_dir(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(run_log.list_run_logs(td), [])

    def test_search_run_logs_limit_100(self):
        with tempfile.TemporaryDirectory() as td:
            for i in range(150):
                _write_run_log_file(
                    td, "id-%03d" % i, "publish",
                    "2026-11-20T10:00:00+00:00")
            matches = run_log.search_run_logs(td, "publish")
            self.assertEqual(len(matches), 100)
            self.assertEqual(
                len(run_log.search_run_logs(td, "publish", limit=3)),
                3)
            self.assertEqual(run_log.search_run_logs(td, "run"), [])

    def test_search_matches_error_code(self):
        with tempfile.TemporaryDirectory() as td:
            _write_run_log_file(td, "bad", "run",
                                "2026-11-20T10:00:00+00:00",
                                error="تعذر الاتصال")
            matches = run_log.search_run_logs(td, "STUDIO-X-001")
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["first_error"]["code"],
                             "STUDIO-X-001")

    def test_first_error_clipped_at_1000(self):
        with tempfile.TemporaryDirectory() as td:
            _write_run_log_file(td, "bad", "run",
                                "2026-11-20T10:00:00+00:00",
                                error="e" * 1500)
            summaries = run_log.list_run_logs(td)
            first = summaries[0]["first_error"]
            self.assertEqual(len(first["original"]), 1000)
            self.assertTrue(first["clipped"])


class TestRunLogPrune(unittest.TestCase):
    def test_prune_old_run_logs_by_mtime(self):
        with tempfile.TemporaryDirectory() as td:
            old_path = _write_run_log_file(
                td, "old", "run", "2026-04-01T10:00:00+00:00")
            _set_old_mtime(old_path)
            new_path = _write_run_log_file(
                td, "new", "run", "2026-11-20T10:00:00+00:00")
            deleted = run_log.prune_old_logs(td, now=NOW)
            self.assertEqual(deleted, [old_path])
            self.assertFalse(os.path.isfile(old_path))
            self.assertTrue(os.path.isfile(new_path))

    def test_prune_keeps_recent(self):
        with tempfile.TemporaryDirectory() as td:
            _write_run_log_file(td, "new", "run",
                                "2026-11-20T10:00:00+00:00")
            self.assertEqual(run_log.prune_old_logs(td, now=NOW), [])

    def test_prune_empty_dir(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(run_log.prune_old_logs(td, now=NOW), [])


class TestPruneDecisionLogs(unittest.TestCase):
    def _setup(self, td):
        runs = os.path.join(td, "runs")
        decider = os.path.join(runs, "decider-log")
        os.makedirs(decider)
        decider_path = os.path.join(decider, "2026-11.ndjson")
        with open(decider_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": OLD, "model": "flash"},
                                ensure_ascii=False) + "\n")
            fh.write(json.dumps({"ts": NEW, "model": "flash"},
                                ensure_ascii=False) + "\n")
            fh.write(json.dumps({"ts": OLD, "model": "lite"},
                                ensure_ascii=False) + "\n")
        approval_path = os.path.join(runs, "approval-decisions.jsonl")
        with open(approval_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": OLD, "action": "publish"},
                                ensure_ascii=False) + "\n")
            fh.write(json.dumps({"ts": NEW, "action": "publish"},
                                ensure_ascii=False) + "\n")
        return runs, decider_path, approval_path

    def test_prunes_old_lines_keeps_recent(self):
        with tempfile.TemporaryDirectory() as td:
            runs, decider_path, approval_path = self._setup(td)
            result = run_log.prune_decision_logs(runs, now=NOW)
            self.assertEqual(result["pruned"][decider_path], 2)
            self.assertEqual(result["pruned"][approval_path], 1)
            self.assertEqual(result["kept"], 2)
            self.assertEqual(result["deleted"], [])
            with open(decider_path, encoding="utf-8") as fh:
                self.assertEqual(len(fh.readlines()), 1)
            with open(approval_path, encoding="utf-8") as fh:
                self.assertEqual(len(fh.readlines()), 1)

    def test_all_old_file_deleted(self):
        with tempfile.TemporaryDirectory() as td:
            runs = os.path.join(td, "runs", "decider-log")
            os.makedirs(runs)
            path = os.path.join(runs, "2026-04.ndjson")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": OLD, "model": "x"},
                                    ensure_ascii=False) + "\n")
            result = run_log.prune_decision_logs(
                os.path.join(td, "runs"), now=NOW)
            self.assertEqual(result["deleted"], [path])
            self.assertFalse(os.path.isfile(path))

    def test_line_without_timestamp_kept(self):
        with tempfile.TemporaryDirectory() as td:
            runs = os.path.join(td, "runs")
            os.makedirs(runs)
            path = os.path.join(runs, "approval-decisions.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"action": "publish"},
                                    ensure_ascii=False) + "\n")
            result = run_log.prune_decision_logs(runs, now=NOW)
            self.assertEqual(result["kept"], 1)
            self.assertTrue(os.path.isfile(path))

    def test_no_decision_logs(self):
        with tempfile.TemporaryDirectory() as td:
            result = run_log.prune_decision_logs(td, now=NOW)
            self.assertEqual(result, {"deleted": [], "pruned": {},
                                      "kept": 0})


class TestRunlogSearchAndPrune(unittest.TestCase):
    def _setup(self, td):
        runs = os.path.join(td, "runs")
        os.makedirs(os.path.join(runs, "anza-20261122-070000"))
        with open(os.path.join(
                runs, "anza-20261122-070000", "run-log.json"),
                "w", encoding="utf-8") as fh:
            json.dump({"run": "anza-20261122-070000", "story": "anza",
                       "started": "2026-11-22T07:00:00",
                       "steps": {"script": {"status": "ok"}}},
                      fh, ensure_ascii=False)
        return runs

    def test_search_runs_finds_by_title(self):
        with tempfile.TemporaryDirectory() as td:
            runs = self._setup(td)
            matches = runlog.search_runs(runs, "anza")
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["title"], "anza")
            self.assertEqual(runlog.search_runs(runs, "غائب"), [])

    def test_search_runs_limit_100(self):
        with tempfile.TemporaryDirectory() as td:
            runs = os.path.join(td, "runs")
            os.makedirs(runs)
            for i in range(120):
                path = os.path.join(runs, "run-%03d.json" % i)
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump({"run_id": "r%d" % i,
                               "command": "run",
                               "started_at": "2026-11-20T10:00:00",
                               "status": "done"},
                              fh, ensure_ascii=False)
            matches = runlog.search_runs(runs, "run")
            self.assertEqual(len(matches), 100)

    def test_search_runs_detail_not_clipped_when_short(self):
        with tempfile.TemporaryDirectory() as td:
            runs = os.path.join(td, "runs")
            os.makedirs(runs)
            path = os.path.join(runs, "run-1.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"run_id": "r1", "command": "run",
                           "started_at": "2026-11-20T10:00:00",
                           "status": "failed",
                           "error": "تعذر الاتصال"},
                          fh, ensure_ascii=False)
            matches = runlog.search_runs(runs, "run")
            self.assertEqual(len(matches), 1)
            self.assertIn("تعذر الاتصال", matches[0]["detail"])
            self.assertFalse(matches[0]["clipped"])

    def test_clip_text_cuts_at_1000(self):
        text, clipped = runlog.clip_text("e" * 1500)
        self.assertEqual(len(text), 1000)
        self.assertTrue(clipped)
        text, clipped = runlog.clip_text("قصير")
        self.assertEqual(text, "قصير")
        self.assertFalse(clipped)

    def test_collect_runs_clamped_at_200(self):
        with tempfile.TemporaryDirectory() as td:
            runs = os.path.join(td, "runs")
            os.makedirs(runs)
            for i in range(205):
                path = os.path.join(runs, "run-%03d.json" % i)
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump({"run_id": "r%d" % i,
                               "command": "run",
                               "started_at": "2026-11-20T10:00:00",
                               "status": "done"},
                              fh, ensure_ascii=False)
            entries = runlog.collect_runs(runs, limit=500)
            self.assertEqual(len(entries), 200)

    def test_prune_old_logs_delegates(self):
        with tempfile.TemporaryDirectory() as td:
            runs = os.path.join(td, "runs", "decider-log")
            os.makedirs(runs)
            path = os.path.join(runs, "2026-04.ndjson")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": OLD, "model": "x"},
                                    ensure_ascii=False) + "\n")
            result = runlog.prune_old_logs(
                os.path.join(td, "runs"), now=NOW)
            self.assertEqual(result["deleted"], [path])
            self.assertFalse(os.path.isfile(path))


class TestBackupExcludesDeciderLogs(unittest.TestCase):
    def test_is_decider_log(self):
        self.assertTrue(update_backup.is_decider_log(
            "runs/decider-log/2026-11.ndjson"))
        self.assertTrue(update_backup.is_decider_log(
            "runs/approval-decisions.jsonl"))
        self.assertTrue(update_backup.is_decider_log(
            "decider-log/2026-11.ndjson"))
        self.assertFalse(update_backup.is_decider_log(
            "runs/jobs.jsonl"))
        self.assertFalse(update_backup.is_decider_log(
            "runs/analyze-20261122.json"))
        self.assertFalse(update_backup.is_decider_log("config.yaml"))

    def test_collect_excludes_decider_logs(self):
        with tempfile.TemporaryDirectory() as td:
            studio = os.path.join(td, "studio")
            runs = os.path.join(studio, "runs")
            decider = os.path.join(runs, "decider-log")
            os.makedirs(decider)
            with open(os.path.join(studio, "config.yaml"), "w",
                      encoding="utf-8") as fh:
                fh.write("x: 1\n")
            with open(os.path.join(runs, "run-1.json"), "w",
                      encoding="utf-8") as fh:
                fh.write("{}\n")
            with open(os.path.join(runs, "analyze-1.json"), "w",
                      encoding="utf-8") as fh:
                fh.write("{}\n")
            with open(os.path.join(decider, "2026-11.ndjson"), "w",
                      encoding="utf-8") as fh:
                fh.write("{}\n")
            with open(os.path.join(decider, "old.json"), "w",
                      encoding="utf-8") as fh:
                fh.write("{}\n")
            with open(os.path.join(runs, "approval-decisions.jsonl"),
                      "w", encoding="utf-8") as fh:
                fh.write("{}\n")
            found, _missing = update_backup.collect_backup_files(
                studio, {"paths": {}})
            arcs = [arc for arc, _path in found]
            self.assertIn("runs/run-1.json", arcs)
            self.assertIn("runs/analyze-1.json", arcs)
            self.assertNotIn("runs/decider-log/2026-11.ndjson", arcs)
            self.assertNotIn("runs/decider-log/old.json", arcs)
            self.assertNotIn("runs/approval-decisions.jsonl", arcs)

    def test_make_backup_zip_has_no_decider_logs(self):
        with tempfile.TemporaryDirectory() as td:
            studio = os.path.join(td, "studio")
            runs = os.path.join(studio, "runs", "decider-log")
            os.makedirs(runs)
            with open(os.path.join(studio, "config.yaml"), "w",
                      encoding="utf-8") as fh:
                fh.write("x: 1\n")
            with open(os.path.join(runs, "2026-11.ndjson"), "w",
                      encoding="utf-8") as fh:
                fh.write("{}\n")
            with open(os.path.join(runs, "old.json"), "w",
                      encoding="utf-8") as fh:
                fh.write("{}\n")
            zip_path, _inc, _missing = update_backup.make_backup(
                studio, {"paths": {}})
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
            self.assertNotIn("runs/decider-log/2026-11.ndjson", names)
            self.assertNotIn("runs/decider-log/old.json", names)
            self.assertIn("config.yaml", names)


if __name__ == "__main__":
    unittest.main()
