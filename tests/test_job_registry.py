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


if __name__ == "__main__":
    unittest.main()
