#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات سجل المهام الدائم (lib.job_registry) — الجولة v0.1.39.

تعمل بـ `python3 -m unittest discover -s tests -v`.
كل الكتابة في مجلدات مؤقتة — لا يُمس سجل runs/ الحقيقي.
بلا أي شبكة.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import job_registry


class TestRegisterAndGet(unittest.TestCase):
    def test_register_returns_running_job(self):
        with tempfile.TemporaryDirectory() as td:
            job = job_registry.register_job(
                td, "batch", story="4", title="العنزة المباركة")
            self.assertTrue(job["job_id"].startswith("job-"))
            self.assertEqual(job["kind"], "batch")
            self.assertEqual(job["story"], "4")
            self.assertEqual(job["title"], "العنزة المباركة")
            self.assertEqual(job["status"], "running")
            self.assertIsNotNone(job["started_at"])
            self.assertIsNone(job["finished_at"])
            self.assertEqual(job["outputs"], [])
            self.assertFalse(job["reused"])
            self.assertTrue(os.path.isfile(
                os.path.join(td, "jobs.jsonl")))

    def test_get_job_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            job = job_registry.register_job(
                td, "run", story="anza", title="العنزة")
            found = job_registry.get_job(td, job["job_id"])
            self.assertIsNotNone(found)
            self.assertEqual(found["title"], "العنزة")
            self.assertIsNone(job_registry.get_job(td, "job-لا-يوجد"))

    def test_register_invalid_kind_raises(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.register_job(td, "publish", title="x")

    def test_register_duplicate_id_raises(self):
        with tempfile.TemporaryDirectory() as td:
            job_registry.register_job(td, "run", title="أ",
                                      job_id="job-ثابت-1")
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.register_job(td, "run", title="ب",
                                          job_id="job-ثابت-1")

    def test_register_with_fingerprint(self):
        with tempfile.TemporaryDirectory() as td:
            job = job_registry.register_job(
                td, "assemble", title="عائشة",
                input_fingerprint="abc123")
            self.assertEqual(job["input_fingerprint"], "abc123")


class TestUpdateJob(unittest.TestCase):
    def test_update_to_done_stamps_finished(self):
        with tempfile.TemporaryDirectory() as td:
            job = job_registry.register_job(td, "batch", title="أ")
            updated = job_registry.update_job(
                td, job["job_id"], status="done",
                outputs=["/tmp/x.mp4"])
            self.assertEqual(updated["status"], "done")
            self.assertIsNotNone(updated["finished_at"])
            self.assertEqual(updated["outputs"], ["/tmp/x.mp4"])
            # التحديث دائم عبر القراءة من القرص.
            self.assertEqual(
                job_registry.get_job(td, job["job_id"])["status"],
                "done")

    def test_update_to_reused(self):
        with tempfile.TemporaryDirectory() as td:
            job = job_registry.register_job(td, "batch", title="أ")
            updated = job_registry.update_job(
                td, job["job_id"], status="reused", reused=True,
                outputs=["/tmp/x.mp4"])
            self.assertEqual(updated["status"], "reused")
            self.assertTrue(updated["reused"])

    def test_update_failed_with_error(self):
        with tempfile.TemporaryDirectory() as td:
            job = job_registry.register_job(td, "run", title="أ")
            updated = job_registry.update_job(
                td, job["job_id"], status="failed",
                error="فشل الإنتاج")
            self.assertEqual(updated["status"], "failed")
            self.assertEqual(updated["error"], "فشل الإنتاج")

    def test_update_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(job_registry.update_job(
                td, "job-غائب", status="done"))

    def test_update_invalid_status_raises(self):
        with tempfile.TemporaryDirectory() as td:
            job = job_registry.register_job(td, "run", title="أ")
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.update_job(td, job["job_id"],
                                        status="نائم")


class TestListJobs(unittest.TestCase):
    def _seed(self, td):
        a = job_registry.register_job(td, "batch", story="4",
                                      title="العنزة المباركة")
        b = job_registry.register_job(td, "run", story="5",
                                      title="عجائب الصدقة")
        c = job_registry.register_job(td, "batch", story="6",
                                      title="العنزة الصغيرة")
        job_registry.update_job(td, a["job_id"], status="done",
                                outputs=["/tmp/a.mp4"])
        job_registry.update_job(td, b["job_id"], status="failed",
                                error="خطأ")
        return a, b, c

    def test_list_all_newest_first(self):
        with tempfile.TemporaryDirectory() as td:
            a, _b, c = self._seed(td)
            jobs = job_registry.list_jobs(td)
            self.assertEqual(len(jobs), 3)
            # الأحدث أولًا: آخر مسجَّل أولًا.
            self.assertEqual(jobs[0]["job_id"], c["job_id"])
            self.assertEqual(jobs[-1]["job_id"], a["job_id"])

    def test_list_by_status(self):
        with tempfile.TemporaryDirectory() as td:
            self._seed(td)
            self.assertEqual(
                len(job_registry.list_jobs(td, status="done")), 1)
            self.assertEqual(
                len(job_registry.list_jobs(td, status="failed")), 1)
            self.assertEqual(
                len(job_registry.list_jobs(td, status="running")), 1)

    def test_list_by_kind(self):
        with tempfile.TemporaryDirectory() as td:
            self._seed(td)
            self.assertEqual(
                len(job_registry.list_jobs(td, kind="batch")), 2)
            self.assertEqual(
                len(job_registry.list_jobs(td, kind="assemble")), 0)

    def test_list_by_story_substring(self):
        with tempfile.TemporaryDirectory() as td:
            self._seed(td)
            jobs = job_registry.list_jobs(td, story="العنزة")
            self.assertEqual(len(jobs), 2)
            jobs = job_registry.list_jobs(td, story="5")
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["title"], "عجائب الصدقة")

    def test_list_by_date(self):
        with tempfile.TemporaryDirectory() as td:
            a, _b, _c = self._seed(td)
            today = a["started_at"][:10]
            self.assertEqual(
                len(job_registry.list_jobs(td, date=today)), 3)
            self.assertEqual(
                len(job_registry.list_jobs(td, date="2000-01-01")), 0)

    def test_list_limit(self):
        with tempfile.TemporaryDirectory() as td:
            self._seed(td)
            self.assertEqual(len(job_registry.list_jobs(td, limit=2)), 2)

    def test_list_invalid_status_raises(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.list_jobs(td, status="نائم")

    def test_corrupt_line_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            job = job_registry.register_job(td, "run", title="أ")
            path = os.path.join(td, "jobs.jsonl")
            with open(path, "a", encoding="utf-8") as fh:
                fh.write("{سطر تالف بلا json\n")
                fh.write("\n")
            jobs = job_registry.list_jobs(td)
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["job_id"], job["job_id"])
            # والتسجيل بعد السطر التالف ما زال يعمل.
            job2 = job_registry.register_job(td, "run", title="ب")
            self.assertEqual(len(job_registry.list_jobs(td)), 2)
            self.assertEqual(job_registry.list_jobs(td)[0]["job_id"],
                             job2["job_id"])


class TestFormatJobs(unittest.TestCase):
    def test_format_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIn("لا مهام",
                          job_registry.format_jobs([]))

    def test_format_shows_reused(self):
        with tempfile.TemporaryDirectory() as td:
            job = job_registry.register_job(td, "batch",
                                            title="العنزة")
            job_registry.update_job(td, job["job_id"],
                                    status="reused", reused=True,
                                    outputs=["/tmp/a.mp4"])
            text = job_registry.format_jobs(
                job_registry.list_jobs(td))
            self.assertIn("العنزة", text)
            self.assertIn("reused", text)
            self.assertIn("أُعيد استخدامه", text)


# ============================================================
# جولة v0.1.63 — البنود 6 و10 و12 و19 و21 و28
# ============================================================

SRC = "[From worker-a · تسليم قصة · direct]"


class TestDeliveryStateMachine(unittest.TestCase):
    def _new(self, td):
        return job_registry.register_delivery(td, SRC, kind="story",
                                              title="العنزة")

    def test_register_starts_at_source_with_counter_zero(self):
        with tempfile.TemporaryDirectory() as td:
            d = self._new(td)
            self.assertTrue(d["id"].startswith("handoff-"))
            self.assertEqual(d["state"], "source")
            self.assertEqual(d["runs"], 0)
            self.assertFalse(d["flagged"])
            self.assertEqual(d["source"], SRC)
            self.assertIsNotNone(d["created_at"])
            self.assertIsNotNone(d["updated_at"])

    def test_full_happy_path_chain(self):
        with tempfile.TemporaryDirectory() as td:
            d = self._new(td)
            for state in ("queued", "running", "waiting", "resume",
                          "running", "completed"):
                d = job_registry.transition_delivery(td, d["id"], state)
                self.assertEqual(d["state"], state)
            # دخل running مرتين → عدّاد التنفيذات 2.
            self.assertEqual(d["runs"], 2)

    def test_invalid_transitions_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            d = self._new(td)
            # source → completed مباشرة مرفوض.
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.transition_delivery(td, d["id"],
                                                 "completed")
            # source → running مرفوض (يلزم queued أولًا).
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.transition_delivery(td, d["id"], "running")
            job_registry.transition_delivery(td, d["id"], "queued")
            job_registry.transition_delivery(td, d["id"], "running")
            # running → resume مرفوض (resume بعد waiting فقط).
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.transition_delivery(td, d["id"], "resume")
            job_registry.transition_delivery(td, d["id"], "completed")
            # حالة نهائية لا تتحرك أبدًا.
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.transition_delivery(td, d["id"], "queued")

    def test_invalid_state_name_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            d = self._new(td)
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.transition_delivery(td, d["id"], "نائم")

    def test_transition_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(job_registry.transition_delivery(
                td, "handoff-غائب", "queued"))

    def test_duplicate_delivery_id_raises(self):
        with tempfile.TemporaryDirectory() as td:
            job_registry.register_delivery(td, SRC, delivery_id="h-1")
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.register_delivery(td, SRC,
                                               delivery_id="h-1")

    def test_corrupt_line_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            d = self._new(td)
            path = os.path.join(td, "deliveries.jsonl")
            with open(path, "a", encoding="utf-8") as fh:
                fh.write("{سطر تالف\n")
            self.assertEqual(len(job_registry.list_deliveries(td)), 1)
            self.assertEqual(job_registry.get_delivery(td, d["id"])
                             ["state"], "source")


class TestDeliverySourceAndFlag(unittest.TestCase):
    def test_delivery_without_source_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            for bad in ("", None, "نص بلا تسمية", "[From x]"):
                with self.assertRaises(job_registry.JobRegistryError,
                                       msg=repr(bad)):
                    job_registry.register_delivery(td, bad)

    def test_format_source_builds_contract_label(self):
        label = job_registry.format_source("worker-a", "تسليم قصة",
                                           "direct")
        self.assertEqual(label, SRC)
        self.assertTrue(job_registry.is_valid_source_label(label))
        self.assertFalse(job_registry.is_valid_source_label(""))

    def test_flag_and_list_filters(self):
        with tempfile.TemporaryDirectory() as td:
            a = job_registry.register_delivery(td, SRC, title="أ")
            b = job_registry.register_delivery(td, SRC, title="ب")
            flagged = job_registry.flag_delivery(td, a["id"])
            self.assertTrue(flagged["flagged"])
            self.assertEqual(
                [d["id"] for d in job_registry.list_deliveries(
                    td, flagged=True)], [a["id"]])
            self.assertEqual(
                len(job_registry.list_deliveries(td, flagged=False)),
                1)
            job_registry.flag_delivery(td, a["id"], flagged=False)
            self.assertEqual(
                len(job_registry.list_deliveries(td, flagged=True)),
                0)
            self.assertIsNone(job_registry.flag_delivery(
                td, "handoff-غائب"))
            text = job_registry.format_deliveries(
                job_registry.list_deliveries(td))
            self.assertIn("أ", text)
            self.assertIn("source", text)
            self.assertIn("تنفيذات 0", text)

    def test_list_by_state_and_source(self):
        with tempfile.TemporaryDirectory() as td:
            a = job_registry.register_delivery(td, SRC, title="أ")
            job_registry.register_delivery(td, SRC, title="ب")
            job_registry.transition_delivery(td, a["id"], "queued")
            self.assertEqual(
                len(job_registry.list_deliveries(td, state="queued")),
                1)
            self.assertEqual(
                len(job_registry.list_deliveries(td, state="source")),
                1)
            self.assertEqual(
                len(job_registry.list_deliveries(td, source=SRC)), 2)
            self.assertEqual(
                len(job_registry.list_deliveries(
                    td, source="[From x · y · z]")), 0)
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.list_deliveries(td, state="نائم")

    def test_job_source_field_stored(self):
        with tempfile.TemporaryDirectory() as td:
            job = job_registry.register_job(td, "run", title="أ",
                                            source=SRC)
            self.assertEqual(job["source"], SRC)
            updated = job_registry.update_job(
                td, job["job_id"], source="[From b · x · y]")
            self.assertEqual(updated["source"], "[From b · x · y]")
            self.assertEqual(
                len(job_registry.list_jobs(
                    td, source="[From b · x · y]")), 1)


class TestRoutineLedger(unittest.TestCase):
    def test_append_and_read(self):
        with tempfile.TemporaryDirectory() as td:
            entry = job_registry.append_routine_ledger(
                td, "daily-09", "ran", "completed", job_id="job-1",
                count=3)
            self.assertEqual(entry["routine"], "daily-09")
            self.assertEqual(entry["state"], "ran")
            self.assertEqual(entry["reason"], "completed")
            self.assertEqual(entry["count"], 3)
            self.assertTrue(os.path.isfile(
                os.path.join(td, "routines.ledger.jsonl")))
            rows = job_registry.read_routine_ledger(td)
            self.assertEqual(len(rows), 1)
            # السطر معرّفات وأوقات وعدّادات فقط — بلا مطالبات.
            self.assertEqual(set(rows[0]),
                             {"ts", "routine", "state", "reason",
                              "job_id", "count"})

    def test_all_states_and_reasons_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            for state in job_registry.ROUTINE_STATES:
                job_registry.append_routine_ledger(
                    td, "r", state, "completed")
            for reason in job_registry.ROUTINE_REASONS:
                job_registry.append_routine_ledger(
                    td, "r", "ran", reason)
            self.assertEqual(
                len(job_registry.read_routine_ledger(td)),
                len(job_registry.ROUTINE_STATES)
                + len(job_registry.ROUTINE_REASONS))

    def test_invalid_state_or_reason_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.append_routine_ledger(
                    td, "r", "done", "completed")
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.append_routine_ledger(
                    td, "r", "ran", "لأنني أريد")

    def test_read_filters_and_limit(self):
        with tempfile.TemporaryDirectory() as td:
            job_registry.append_routine_ledger(
                td, "a", "ran", "completed")
            job_registry.append_routine_ledger(
                td, "a", "missed", "missed_window")
            job_registry.append_routine_ledger(
                td, "b", "skipped", "previous_active")
            self.assertEqual(
                len(job_registry.read_routine_ledger(td, routine="a")),
                2)
            self.assertEqual(
                len(job_registry.read_routine_ledger(td, state="ran")),
                1)
            rows = job_registry.read_routine_ledger(td, limit=2)
            self.assertEqual(len(rows), 2)
            # الأحدث أولًا.
            self.assertEqual(rows[0]["routine"], "b")

    def test_corrupt_line_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            job_registry.append_routine_ledger(
                td, "a", "ran", "completed")
            path = os.path.join(td, "routines.ledger.jsonl")
            with open(path, "a", encoding="utf-8") as fh:
                fh.write("{تالف\n")
            self.assertEqual(
                len(job_registry.read_routine_ledger(td)), 1)


class TestRosterCaps(unittest.TestCase):
    def test_enforce_max_40(self):
        self.assertEqual(job_registry.enforce_roster_size(40), 40)
        self.assertEqual(job_registry.enforce_roster_size(3), 3)
        with self.assertRaises(job_registry.JobRegistryError):
            job_registry.enforce_roster_size(41)
        self.assertTrue(job_registry.roster_size_ok(40))
        self.assertFalse(job_registry.roster_size_ok(41))

    def test_others_min_8(self):
        self.assertTrue(job_registry.others_count_ok(8))
        self.assertFalse(job_registry.others_count_ok(7))

    def test_group_message_goes_to_chief_only(self):
        self.assertEqual(
            job_registry.route_group_message("@everyone"), "chief")
        self.assertEqual(
            job_registry.route_group_message("everyone"), "chief")
        self.assertEqual(
            job_registry.route_group_message("worker-a"), "worker-a")


class TestWaitOutcomes(unittest.TestCase):
    def test_mapping_all_job_states(self):
        expected = {
            "completed": "settled", "idle": "settled",
            "needs-input": "needs-user", "failed": "failed",
            "stalled": "stalled", "timed-out": "timed-out",
        }
        for state, outcome in expected.items():
            self.assertEqual(
                job_registry.wait_outcome_for_state(state), outcome)

    def test_unknown_job_state_rejected(self):
        with self.assertRaises(job_registry.JobRegistryError):
            job_registry.wait_outcome_for_state("running")

    def test_set_wait_outcome(self):
        with tempfile.TemporaryDirectory() as td:
            d = job_registry.register_delivery(td, SRC, title="أ")
            updated = job_registry.set_delivery_wait_outcome(
                td, d["id"], "needs-user")
            self.assertEqual(updated["wait_outcome"], "needs-user")
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.set_delivery_wait_outcome(
                    td, d["id"], "waiting")
            self.assertIsNone(job_registry.set_delivery_wait_outcome(
                td, "handoff-غائب", "settled"))


class TestInterrupt(unittest.TestCase):
    def test_interrupt_delivery_tree(self):
        with tempfile.TemporaryDirectory() as td:
            root = job_registry.register_delivery(td, SRC, title="جذر")
            child = job_registry.register_delivery(
                td, SRC, title="ابن", parent_id=root["id"])
            grand = job_registry.register_delivery(
                td, SRC, title="حفيد", parent_id=child["id"])
            done = job_registry.register_delivery(
                td, SRC, title="منتهٍ", parent_id=root["id"])
            for d in (done,):
                job_registry.transition_delivery(td, d["id"], "queued")
                job_registry.transition_delivery(td, d["id"], "running")
                job_registry.transition_delivery(td, d["id"],
                                                 "completed")
            job_registry.transition_delivery(td, root["id"], "queued")
            job_registry.transition_delivery(td, root["id"], "running")
            changed = job_registry.interrupt_delivery(td, root["id"])
            self.assertEqual(
                {c["id"] for c in changed},
                {root["id"], child["id"], grand["id"]})
            self.assertTrue(all(c["state"] == "cancelled"
                                for c in changed))
            # المنتهي أصلًا لم يُمسّ.
            self.assertEqual(job_registry.get_delivery(
                td, done["id"])["state"], "completed")

    def test_interrupt_missing_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(job_registry.interrupt_delivery(
                td, "handoff-غائب"), [])

    def test_interrupt_job_tree_stamps_finished(self):
        with tempfile.TemporaryDirectory() as td:
            root = job_registry.register_job(td, "run", title="جذر")
            child = job_registry.register_job(
                td, "run", title="ابن", parent_id=root["job_id"])
            done = job_registry.register_job(td, "run", title="منتهٍ",
                                             parent_id=root["job_id"])
            job_registry.update_job(td, done["job_id"], status="done")
            changed = job_registry.interrupt_job(td, root["job_id"])
            self.assertEqual(
                {c["job_id"] for c in changed},
                {root["job_id"], child["job_id"]})
            self.assertTrue(all(c["status"] == "cancelled"
                                for c in changed))
            self.assertIsNotNone(changed[0]["finished_at"])
            self.assertEqual(job_registry.get_job(
                td, done["job_id"])["status"], "done")

    def test_interrupt_job_missing_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(job_registry.interrupt_job(
                td, "job-غائب"), [])


class TestWorkerStates(unittest.TestCase):
    def test_pause_resume_cycle(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                job_registry.get_worker_state(td, "w1"), "active")
            job_registry.pause_worker(td, "w1")
            self.assertEqual(
                job_registry.get_worker_state(td, "w1"), "paused")
            job_registry.resume_worker(td, "w1")
            self.assertEqual(
                job_registry.get_worker_state(td, "w1"), "active")

    def test_stop_is_terminal(self):
        with tempfile.TemporaryDirectory() as td:
            job_registry.pause_worker(td, "w1")
            job_registry.stop_worker(td, "w1")
            self.assertEqual(
                job_registry.get_worker_state(td, "w1"), "stopped")
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.resume_worker(td, "w1")
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.pause_worker(td, "w1")

    def test_invalid_worker_state_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(job_registry.JobRegistryError):
                job_registry.set_worker_state(td, "w1", "نائم")

    def test_list_workers(self):
        with tempfile.TemporaryDirectory() as td:
            job_registry.pause_worker(td, "w1")
            job_registry.stop_worker(td, "w2")
            workers = job_registry.list_workers(td)
            self.assertEqual(workers, {"w1": "paused",
                                       "w2": "stopped"})


if __name__ == "__main__":
    unittest.main()
