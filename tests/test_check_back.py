#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات check-back — جولة v0.1.63 (بند 7).

كلها على مجلدات مؤقتة؛ بلا شبكة وبلا ملفات خارج الشجرة.
"""
import os
import stat
import tempfile
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import check_back

_CAIRO = ZoneInfo("Africa/Cairo")


def _due_in(minutes):
    return datetime.now(tz=_CAIRO) + timedelta(minutes=minutes)


class TestAddAndList(unittest.TestCase):
    def test_add_returns_pending_record(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            rec = check_back.add_check_back(
                runs_dir, "run-1", "worker-a", _due_in(5),
                note="تذكير")
            self.assertTrue(rec["id"].startswith("cb-"))
            self.assertEqual(rec["run_id"], "run-1")
            self.assertEqual(rec["worker"], "worker-a")
            self.assertEqual(rec["status"], "pending")
            self.assertEqual(rec["note"], "تذكير")
            self.assertIsNone(rec["consumed_at"])
            listed = check_back.list_check_backs(runs_dir)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["id"], rec["id"])

    def test_add_accepts_iso_string_due(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            rec = check_back.add_check_back(
                runs_dir, "run-1", "worker-a", "2026-11-27T12:00:00")
            self.assertIn("2026-11-27T12:00:00", rec["due"])

    def test_add_validates_inputs(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            with self.assertRaises(check_back.CheckBackError):
                check_back.add_check_back(
                    runs_dir, "", "worker-a", _due_in(5))
            with self.assertRaises(check_back.CheckBackError):
                check_back.add_check_back(
                    runs_dir, "run-1", "", _due_in(5))
            with self.assertRaises(check_back.CheckBackError):
                check_back.add_check_back(
                    runs_dir, "run-1", "worker-a", "not-a-date")
            with self.assertRaises(check_back.CheckBackError):
                check_back.add_check_back(
                    runs_dir, "run-1", "worker-a", None)

    def test_state_file_is_0600(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            check_back.add_check_back(
                runs_dir, "run-1", "worker-a", _due_in(5))
            mode = stat.S_IMODE(os.stat(
                check_back.state_path(runs_dir)).st_mode)
            self.assertEqual(mode, 0o600)

    def test_list_filters_by_run_worker_status(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            first = check_back.add_check_back(
                runs_dir, "run-1", "worker-a", _due_in(5))
            check_back.add_check_back(
                runs_dir, "run-2", "worker-a", _due_in(6))
            check_back.add_check_back(
                runs_dir, "run-1", "worker-b", _due_in(7))
            check_back.cancel_check_back(runs_dir, first["id"])
            self.assertEqual(
                len(check_back.list_check_backs(
                    runs_dir, run_id="run-1")), 2)
            self.assertEqual(
                len(check_back.list_check_backs(
                    runs_dir, worker="worker-a")), 2)
            self.assertEqual(
                len(check_back.list_check_backs(
                    runs_dir, status="cancelled")), 1)
            self.assertEqual(
                len(check_back.list_check_backs(
                    runs_dir, status="pending")), 2)
            with self.assertRaises(check_back.CheckBackError):
                check_back.list_check_backs(runs_dir, status="done")

    def test_note_truncated_to_500_chars(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            rec = check_back.add_check_back(
                runs_dir, "run-1", "worker-a", _due_in(5),
                note="x" * 600)
            self.assertEqual(len(rec["note"]), 500)


class TestLimits(unittest.TestCase):
    def test_eleventh_per_run_is_rejected(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            for _ in range(check_back.MAX_PER_RUN):
                check_back.add_check_back(
                    runs_dir, "run-1", "worker-a", _due_in(5))
            self.assertEqual(check_back.MAX_PER_RUN, 10)
            with self.assertRaises(check_back.CheckBackError):
                check_back.add_check_back(
                    runs_dir, "run-1", "worker-a", _due_in(5))
            self.assertEqual(
                check_back.count_pending(runs_dir, run_id="run-1"),
                10)

    def test_cancelled_does_not_count_toward_limit(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            ids = [check_back.add_check_back(
                runs_dir, "run-1", "worker-a", _due_in(5))["id"]
                for _ in range(10)]
            check_back.cancel_check_back(runs_dir, ids[0])
            rec = check_back.add_check_back(
                runs_dir, "run-1", "worker-a", _due_in(5))
            self.assertEqual(rec["status"], "pending")
            self.assertEqual(
                check_back.count_pending(runs_dir, run_id="run-1"),
                10)

    def test_fifty_first_per_worker_rejected(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            for i in range(check_back.MAX_PER_WORKER):
                check_back.add_check_back(
                    runs_dir, "run-%d" % (i // 10 + 1), "worker-a",
                    _due_in(5))
            self.assertEqual(check_back.MAX_PER_WORKER, 50)
            with self.assertRaises(check_back.CheckBackError):
                check_back.add_check_back(
                    runs_dir, "run-99", "worker-a", _due_in(5))
            self.assertEqual(
                check_back.count_pending(runs_dir, worker="worker-a"),
                50)


class TestDueAndConsume(unittest.TestCase):
    def test_overdue_runs_once_then_consumed(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            rec = check_back.add_check_back(
                runs_dir, "run-1", "worker-a", _due_in(-5))
            due = check_back.due_check_backs(runs_dir)
            self.assertEqual(len(due), 1)
            consumed = check_back.consume_due(runs_dir)
            self.assertEqual(len(consumed), 1)
            self.assertEqual(consumed[0]["status"], "consumed")
            self.assertIsNotNone(consumed[0]["consumed_at"])
            self.assertEqual(check_back.due_check_backs(runs_dir), [])
            self.assertEqual(check_back.consume_due(runs_dir), [])

    def test_not_yet_due_is_not_listed(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            check_back.add_check_back(
                runs_dir, "run-1", "worker-a", _due_in(60))
            self.assertEqual(check_back.due_check_backs(runs_dir), [])

    def test_consume_twice_is_impossible(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            rec = check_back.add_check_back(
                runs_dir, "run-1", "worker-a", _due_in(-1))
            first = check_back.consume_check_back(runs_dir, rec["id"])
            second = check_back.consume_check_back(
                runs_dir, rec["id"])
            self.assertEqual(first["status"], "consumed")
            self.assertEqual(second["status"], "consumed")
            self.assertEqual(first["consumed_at"],
                             second["consumed_at"])

    def test_due_sorted_oldest_first(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            late = check_back.add_check_back(
                runs_dir, "run-1", "worker-a", _due_in(-1))
            early = check_back.add_check_back(
                runs_dir, "run-1", "worker-a", _due_in(-30))
            due = check_back.due_check_backs(runs_dir)
            self.assertEqual([r["id"] for r in due],
                             [early["id"], late["id"]])


class TestCancel(unittest.TestCase):
    def test_cancel_marks_cancelled_and_keeps_record(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            rec = check_back.add_check_back(
                runs_dir, "run-1", "worker-a", _due_in(5))
            done = check_back.cancel_check_back(runs_dir, rec["id"])
            self.assertEqual(done["status"], "cancelled")
            self.assertIsNotNone(done["cancelled_at"])
            self.assertIsNotNone(
                check_back.get_check_back(runs_dir, rec["id"]))
            self.assertEqual(
                check_back.count_pending(runs_dir), 0)

    def test_cancel_unknown_returns_none(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            self.assertIsNone(
                check_back.cancel_check_back(runs_dir, "cb-nope"))
            self.assertIsNone(
                check_back.consume_check_back(runs_dir, "cb-nope"))
            self.assertIsNone(
                check_back.get_check_back(runs_dir, "cb-nope"))

    def test_cancelled_is_not_due(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            rec = check_back.add_check_back(
                runs_dir, "run-1", "worker-a", _due_in(-5))
            check_back.cancel_check_back(runs_dir, rec["id"])
            self.assertEqual(check_back.due_check_backs(runs_dir), [])
            self.assertEqual(check_back.consume_due(runs_dir), [])


if __name__ == "__main__":
    unittest.main()
