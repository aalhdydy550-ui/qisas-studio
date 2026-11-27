#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات الحارس (lib.sentinel) — بند 16، جولة v0.1.63.

زوج موجب/سالب لكل سلوك: تجميع خطأين برقمين مختلفين في
قضية واحدة؛ والمخرجات الخام لا تُخزَّن أبدًا؛ ورفض `--out`
داخل البيانات أو git؛ ولا-عمل عند لا-تغيير؛ وتحديث `count`
و`lastAt` في موضعهما عند إعادة الفحص؛ وSQLite قراءة فقط
بـ`mode=ro`.

معزولة: `tempfile` فقط، بلا شبكة، بلا ملفات خارج الشجرة.
"""
import json
import os
import sqlite3
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import sentinel as sn


def _write_jobs(path, records):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


class TestNormalizeError(unittest.TestCase):
    def test_paths_numbers_uuids_urls_emails_quoted_replaced(self):
        text = ("failed at /home/user/studio/runs/x.log layer 12 "
                "uuid 123e4567-e89b-12d3-a456-426614174000 "
                "see https://example.com/a?b=1 mail a@b.com "
                "value 'secret-thing' end")
        out = sn.normalize_error(text)
        self.assertNotIn("/home/user", out)
        self.assertNotIn("123e4567", out)
        self.assertNotIn("example.com", out)
        self.assertNotIn("a@b.com", out)
        self.assertNotIn("secret-thing", out)
        self.assertNotIn("12", out)
        self.assertIn("<path>", out)
        self.assertIn("<n>", out)
        self.assertIn("<uuid>", out)
        self.assertIn("<url>", out)
        self.assertIn("<email>", out)
        self.assertIn("<value>", out)

    def test_empty_and_whitespace(self):
        self.assertEqual(sn.normalize_error(""), "")
        self.assertEqual(sn.normalize_error("  a   b  "), "a b")


class TestSigStability(unittest.TestCase):
    def test_two_errors_differing_only_by_number_share_sig(self):
        sig1 = sn.make_sig("mlt", sn.normalize_error("no layer 12"))
        sig2 = sn.make_sig("mlt", sn.normalize_error("no layer 104"))
        self.assertEqual(sig1, sig2)

    def test_different_tool_or_message_differs(self):
        base = sn.make_sig("mlt", sn.normalize_error("no layer 12"))
        other_tool = sn.make_sig("ffmpeg", sn.normalize_error("no layer 12"))
        other_msg = sn.make_sig("mlt", sn.normalize_error("disk full"))
        self.assertNotEqual(base, other_tool)
        self.assertNotEqual(base, other_msg)

    def test_sig_prefix_and_length(self):
        sig = sn.make_sig("mlt", sn.normalize_error("boom"))
        self.assertTrue(sig.startswith("tool_error:"))
        self.assertEqual(len(sig.split(":", 1)[1]), 16)


class TestClassifyAndCoarseSig(unittest.TestCase):
    def test_timeout_ignores_exit_code(self):
        sig1 = sn.make_sig("sh", "timed out after 5s", exit_code=124,
                           coarse=True)
        sig2 = sn.make_sig("sh", "timed out after 9s", exit_code=1,
                           coarse=True)
        self.assertEqual(sig1, sig2)
        self.assertEqual(sn.classify_error("Timed out waiting"), "timed out")

    def test_command_not_found_category(self):
        self.assertEqual(
            sn.classify_error("bash: frobnicate: command not found"),
            "command not found")

    def test_coarse_sig_differs_by_category(self):
        a = sn.make_sig("sh", "no such file or directory", exit_code=1,
                        coarse=True)
        b = sn.make_sig("sh", "permission denied", exit_code=1, coarse=True)
        self.assertNotEqual(a, b)

    def test_unknown_when_nothing_matches(self):
        self.assertEqual(sn.classify_error("weird thing"), "unknown")


class TestTitle(unittest.TestCase):
    def test_title_capped_at_160(self):
        title = sn.make_title("tool", "x" * 500)
        self.assertLessEqual(len(title), sn.TITLE_MAX_LEN)

    def test_title_single_line(self):
        title = sn.make_title("tool", "line one\nline two")
        self.assertNotIn("\n", title)


class TestValidateOutDir(unittest.TestCase):
    def test_rejects_out_inside_data_dir(self):
        with tempfile.TemporaryDirectory() as td:
            data = os.path.join(td, "data")
            os.makedirs(data)
            with self.assertRaises(sn.SentinelError):
                sn.validate_out_dir(os.path.join(data, "out"), data)
            with self.assertRaises(sn.SentinelError):
                sn.validate_out_dir(data, data)

    def test_rejects_out_inside_git_repo(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, ".git"))
            with self.assertRaises(sn.SentinelError):
                sn.validate_out_dir(os.path.join(td, "out"), "/tmp/elsewhere")

    def test_accepts_outside_both(self):
        with tempfile.TemporaryDirectory() as td:
            data = os.path.join(td, "data")
            out = os.path.join(td, "out")
            os.makedirs(data)
            self.assertEqual(sn.validate_out_dir(out, data),
                             os.path.abspath(out))


class TestScanJobsFile(unittest.TestCase):
    def test_failed_jobs_grouped_and_raw_never_stored(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "jobs.jsonl")
            secret = "sk-test-SECRET-VALUE-12345"
            _write_jobs(path, [
                {"job_id": "j1", "kind": "assemble", "status": "failed",
                 "error": "no layer 12 at /home/me/x key %s" % secret,
                 "started_at": "2026-11-27T10:00:00+02:00",
                 "finished_at": "2026-11-27T10:01:00+02:00"},
                {"job_id": "j2", "kind": "assemble", "status": "failed",
                 "error": "no layer 104 at /home/me/y key %s" % secret,
                 "started_at": "2026-11-27T10:02:00+02:00",
                 "finished_at": "2026-11-27T10:03:00+02:00"},
                {"job_id": "j3", "kind": "run", "status": "completed",
                 "error": None},
            ])
            issues, read_ids = sn.scan_jobs_file(path)
            self.assertEqual(len(issues), 2)
            self.assertEqual(issues[0]["sig"], issues[1]["sig"])
            self.assertEqual(read_ids, {"j1", "j2", "j3"})
            blob = json.dumps(issues, ensure_ascii=False)
            self.assertNotIn(secret, blob)
            self.assertNotIn("/home/me", blob)
            self.assertIn("evidenceRef", issues[0])
            self.assertEqual(issues[0]["evidenceRef"]["source"], "jobs")
            self.assertEqual(issues[0]["evidenceRef"]["id"], "j1")

    def test_seen_ids_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "jobs.jsonl")
            _write_jobs(path, [
                {"job_id": "j1", "kind": "run", "status": "failed",
                 "error": "boom"},
            ])
            issues, _ = sn.scan_jobs_file(path, seen_ids={"j1"})
            self.assertEqual(issues, [])

    def test_missing_file_returns_empty(self):
        issues, read_ids = sn.scan_jobs_file("/tmp/no-such-jobs.jsonl")
        self.assertEqual(issues, [])
        self.assertEqual(read_ids, set())

    def test_malformed_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "jobs.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("not json\n")
                handle.write(json.dumps(
                    {"job_id": "j1", "kind": "run", "status": "failed",
                     "error": "boom"}) + "\n")
            issues, _ = sn.scan_jobs_file(path)
            self.assertEqual(len(issues), 1)


class TestScanLogFile(unittest.TestCase):
    def test_offset_resume_reads_only_new_lines(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "run.log")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("ok line\nERROR failure 7\n")
            issues1, offset, ids1 = sn.scan_log_file(path, offset=0)
            self.assertEqual(len(issues1), 1)
            with open(path, "a", encoding="utf-8") as handle:
                handle.write("ok again\nERROR failure 9\n")
            issues2, new_offset, _ = sn.scan_log_file(
                path, offset=offset, seen_ids=ids1)
            self.assertEqual(len(issues2), 1)
            self.assertGreater(new_offset, offset)
            # نفس الخطأ برقم مختلف → نفس التوقيع (تطبيع الأرقام).
            self.assertEqual(issues1[0]["sig"], issues2[0]["sig"])


class TestReadSqliteRo(unittest.TestCase):
    def test_reads_live_db_and_missing_raises(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "live.db")
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE t (a TEXT)")
            conn.execute("INSERT INTO t VALUES ('x')")
            conn.commit()
            conn.close()
            rows = sn.read_sqlite_ro(path, "SELECT a FROM t")
            self.assertEqual(rows, [("x",)])
            with self.assertRaises(sn.SentinelError):
                sn.read_sqlite_ro(os.path.join(td, "absent.db"),
                                  "SELECT 1")


class TestRunSentinel(unittest.TestCase):
    def _make_data(self, td):
        data = os.path.join(td, "data")
        _write_jobs(os.path.join(data, "runs", "jobs.jsonl"), [
            {"job_id": "j1", "kind": "assemble", "status": "failed",
             "error": "render failed layer 3",
             "started_at": "2026-11-27T10:00:00+02:00",
             "finished_at": "2026-11-27T10:01:00+02:00"},
        ])
        return data

    def test_full_run_writes_issues_and_state_with_modes(self):
        with tempfile.TemporaryDirectory() as td:
            data = self._make_data(td)
            out = os.path.join(td, "sentinel-out")
            code, summary = sn.run_sentinel(data, out)
            self.assertEqual(code, 0)
            self.assertTrue(summary["changed"])
            self.assertEqual(summary["new_issues"], 1)
            self.assertEqual(summary["total_issues"], 1)
            self.assertEqual(stat.S_IMODE(os.stat(out).st_mode), 0o700)
            issues_path = os.path.join(out, sn.ISSUES_FILENAME)
            state_path = os.path.join(out, sn.STATE_FILENAME)
            self.assertEqual(stat.S_IMODE(os.stat(issues_path).st_mode),
                             0o600)
            self.assertEqual(stat.S_IMODE(os.stat(state_path).st_mode),
                             0o600)
            with open(issues_path, encoding="utf-8") as handle:
                record = json.loads(handle.readline())
            self.assertNotIn("layer 3", record["title"].replace("<n>", ""))
            self.assertIn("sig", record)
            self.assertEqual(record["count"], 1)

    def test_no_change_does_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            data = self._make_data(td)
            out = os.path.join(td, "sentinel-out")
            sn.run_sentinel(data, out)
            issues_path = os.path.join(out, sn.ISSUES_FILENAME)
            with open(issues_path, "rb") as handle:
                before = handle.read()
            code, summary = sn.run_sentinel(data, out)
            self.assertEqual(code, 0)
            self.assertFalse(summary["changed"])
            self.assertEqual(summary["new_issues"], 0)
            self.assertEqual(summary["total_issues"], 1)
            with open(issues_path, "rb") as handle:
                self.assertEqual(handle.read(), before)

    def test_rerun_updates_count_and_last_at_in_place(self):
        with tempfile.TemporaryDirectory() as td:
            data = self._make_data(td)
            out = os.path.join(td, "sentinel-out")
            sn.run_sentinel(data, out)
            jobs_path = os.path.join(data, "runs", "jobs.jsonl")
            _write_jobs(jobs_path, [
                {"job_id": "j1", "kind": "assemble", "status": "failed",
                 "error": "render failed layer 3",
                 "started_at": "2026-11-27T10:00:00+02:00",
                 "finished_at": "2026-11-27T10:01:00+02:00"},
                {"job_id": "j2", "kind": "assemble", "status": "failed",
                 "error": "render failed layer 8",
                 "started_at": "2026-11-27T11:00:00+02:00",
                 "finished_at": "2026-11-27T11:05:00+02:00"},
            ])
            code, summary = sn.run_sentinel(data, out)
            self.assertEqual(code, 0)
            self.assertEqual(summary["total_issues"], 1)
            with open(os.path.join(out, sn.ISSUES_FILENAME),
                      encoding="utf-8") as handle:
                lines = handle.readlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["count"], 2)
            self.assertEqual(record["lastAt"], "2026-11-27T11:05:00+02:00")
            self.assertEqual(record["evidenceRef"]["id"], "j2")

    def test_out_inside_data_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            data = self._make_data(td)
            with self.assertRaises(sn.SentinelError):
                sn.run_sentinel(data, os.path.join(data, "sentinel"))

    def test_missing_sources_still_succeeds(self):
        with tempfile.TemporaryDirectory() as td:
            data = os.path.join(td, "empty-data")
            os.makedirs(data)
            code, summary = sn.run_sentinel(data, os.path.join(td, "out"))
            self.assertEqual(code, 0)
            self.assertEqual(summary["total_issues"], 0)


if __name__ == "__main__":
    unittest.main()
