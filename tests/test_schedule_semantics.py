#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات دلالات المهام المجدولة (جولة v0.1.41 — بند 3 من
استخراج AlphaCLI، REPORT-AR.md §4.1).

- كل occurrence تُسجَّل قبل بدئها (started_at في سجل المهام
  قبل أي قراءة/تعليق) — ريستارت بعد البدء = تخطٍّ لا تكرار.
- بعد التوقف: occurrence متأخرة واحدة فقط تلحق، ثم يستأنف
  الفاصل الأصلي؛ والإيقاف/الإلغاء للمستقبل فقط.
- كلها على دوال وهمية وسجل مهام مؤقت في /tmp — ممنوع تمامًا
  لمس المنشورات المجدولة الحقيقية أو الطابور الحقيقي.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import job_registry, schedule_watch


STORY = {"moral": "الظلم مهما طال ليله، الحق بيظهر.",
         "question": "لو كنت مكانه، كنت عملت إيه؟",
         "next_part_time": "بكرة 7 مساءً"}
POST_ID = "122132235897269645"
DUE = "2026-11-23T09:00"


def _fakes(state="published", fail_times=0):
    """دالتان وهميتان بعدّادات استدعاء."""
    calls = {"read": 0, "comment": 0, "texts": []}
    failures_left = [fail_times]

    def read_fn(post_id):
        calls["read"] += 1
        return state

    def comment_fn(post_id, text):
        calls["comment"] += 1
        calls["texts"].append(text)
        if failures_left[0] > 0:
            failures_left[0] -= 1
            raise RuntimeError("رفض فيسبوك التعليق (وهمي)")
        return {"comment_id": "2056409585228722"}

    return read_fn, comment_fn, calls


class TestRecordBeforeStart(unittest.TestCase):
    def test_restart_after_start_is_skipped_not_repeated(self):
        """(أ) ريستارت بعد البدء = تخطٍّ لا تكرار."""
        with tempfile.TemporaryDirectory() as td:
            read_fn, comment_fn, calls = _fakes()
            first = schedule_watch.watch_slot(
                POST_ID, STORY, read_fn, comment_fn, execute=True,
                runs_dir=td, due=DUE)
            self.assertTrue(first["ok"])
            self.assertEqual(calls["comment"], 1)
            # التشغيل الثاني لنفس الـoccurrence (ريستارت):
            read_fn2, comment_fn2, calls2 = _fakes()
            second = schedule_watch.watch_slot(
                POST_ID, STORY, read_fn2, comment_fn2, execute=True,
                runs_dir=td, due=DUE)
            self.assertFalse(second["ok"])
            self.assertEqual(second["reason"], "already_started")
            self.assertTrue(second["skipped"])
            self.assertEqual(calls2["read"], 0)
            self.assertEqual(calls2["comment"], 0)
            # سجل واحد فقط في السجل، بحالة done وstarted_at.
            jobs = job_registry.list_jobs(td, kind="schedule")
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["status"], "done")
            self.assertTrue(jobs[0]["started_at"])
            self.assertIn("schedule-watch:morning:%s:%s"
                          % (POST_ID, DUE), jobs[0]["story"])

    def test_started_at_recorded_before_any_call(self):
        """started_at يُكتب قبل القراءة/التعليق: read_fn ترى
        السجل موجودًا أصلًا أثناء تنفيذها."""
        with tempfile.TemporaryDirectory() as td:
            seen = []

            def read_fn(post_id):
                seen.append(job_registry.list_jobs(
                    td, kind="schedule"))
                return "published"

            _, comment_fn, _ = _fakes()
            res = schedule_watch.watch_slot(
                POST_ID, STORY, read_fn, comment_fn, execute=True,
                runs_dir=td, due=DUE)
            self.assertTrue(res["ok"])
            self.assertEqual(len(seen), 1)
            self.assertEqual(len(seen[0]), 1)
            self.assertEqual(seen[0][0]["status"], "running")
            self.assertTrue(seen[0][0]["started_at"])

    def test_failed_occurrence_also_skips_restart(self):
        """occurrence فشلت (تعليق فشل مرتين) ثم ريستارت =
        تخطٍّ — التسجيل المسبق يغطي الفشل أيضًا."""
        with tempfile.TemporaryDirectory() as td:
            read_fn, comment_fn, calls = _fakes(fail_times=10)
            first = schedule_watch.watch_slot(
                POST_ID, STORY, read_fn, comment_fn, execute=True,
                runs_dir=td, due=DUE)
            self.assertFalse(first["ok"])
            self.assertEqual(calls["comment"], 2)
            jobs = job_registry.list_jobs(td, kind="schedule")
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["status"], "failed")
            read_fn2, comment_fn2, calls2 = _fakes()
            second = schedule_watch.watch_slot(
                POST_ID, STORY, read_fn2, comment_fn2, execute=True,
                runs_dir=td, due=DUE)
            self.assertEqual(second["reason"], "already_started")
            self.assertEqual(calls2["comment"], 0)

    def test_not_published_tick_is_done_and_next_slot_runs(self):
        """خانة فُحصت ولم يُنشر منشورها تُختم done؛ وموعد
        آخر (occurrence مختلفة) يُشغَّل من جديد."""
        with tempfile.TemporaryDirectory() as td:
            read_fn, comment_fn, calls = _fakes(state="scheduled")
            first = schedule_watch.watch_slot(
                POST_ID, STORY, read_fn, comment_fn, execute=True,
                runs_dir=td, due=DUE)
            self.assertEqual(first["reason"], "not_published")
            self.assertEqual(calls["comment"], 0)
            jobs = job_registry.list_jobs(td, kind="schedule")
            self.assertEqual(jobs[0]["status"], "done")
            read_fn2, comment_fn2, calls2 = _fakes()
            second = schedule_watch.watch_slot(
                POST_ID, STORY, read_fn2, comment_fn2, execute=True,
                runs_dir=td, due="2026-11-23T19:00", slot="evening")
            self.assertTrue(second["ok"])
            self.assertEqual(calls2["comment"], 1)
            self.assertEqual(
                len(job_registry.list_jobs(td, kind="schedule")), 2)

    def test_dry_run_records_nothing(self):
        """الوضع التجريبي لا يسجّل في سجل المهام إطلاقًا."""
        with tempfile.TemporaryDirectory() as td:
            read_fn, comment_fn, _ = _fakes()
            plan = schedule_watch.watch_slot(
                POST_ID, STORY, read_fn, comment_fn,
                runs_dir=td, due=DUE)
            self.assertTrue(plan["dry_run"])
            self.assertEqual(
                job_registry.list_jobs(td, kind="schedule"), [])
            self.assertFalse(
                os.path.isfile(job_registry.registry_path(td)))

    def test_without_runs_dir_behaviour_unchanged(self):
        """بلا runs_dir: لا سجل ولا تخطٍّ — السلوك القديم."""
        read_fn, comment_fn, calls = _fakes()
        res = schedule_watch.watch_slot(
            POST_ID, STORY, read_fn, comment_fn, execute=True)
        self.assertTrue(res["ok"])
        self.assertEqual(calls["comment"], 1)
        res2 = schedule_watch.watch_slot(
            POST_ID, STORY, read_fn, comment_fn, execute=True)
        self.assertTrue(res2["ok"])
        self.assertEqual(calls["comment"], 2)


class TestCatchUp(unittest.TestCase):
    def test_only_one_missed_occurrence_catches_up(self):
        """(ب) occurrence واحدة تلحق بعد التوقف لا كل المتأخرات."""
        plan = schedule_watch.catch_up_plan(
            ["2026-11-21T09:00", "2026-11-22T09:00",
             "2026-11-23T09:00"],
            next_due="2026-11-24T09:00")
        self.assertEqual(plan["run"], "2026-11-21T09:00")
        self.assertEqual(plan["skipped"],
                         ["2026-11-22T09:00", "2026-11-23T09:00"])
        # الفاصل الأصلي يستأنف بلا إزاحة من وقت اللحاق.
        self.assertEqual(plan["next_due"], "2026-11-24T09:00")

    def test_no_missed_means_no_catch_up(self):
        plan = schedule_watch.catch_up_plan(
            [], next_due="2026-11-24T09:00")
        self.assertIsNone(plan["run"])
        self.assertEqual(plan["skipped"], [])
        self.assertEqual(plan["next_due"], "2026-11-24T09:00")

    def test_single_missed_runs_it(self):
        plan = schedule_watch.catch_up_plan(
            ["2026-11-23T09:00"], next_due="2026-11-24T09:00")
        self.assertEqual(plan["run"], "2026-11-23T09:00")
        self.assertEqual(plan["skipped"], [])


class TestCancelFuture(unittest.TestCase):
    def test_cancel_is_future_only(self):
        """الإيقاف/الإلغاء للمستقبل فقط: الماضي يبقى."""
        occs = [{"due": "2026-11-21T09:00"},
                {"due": "2026-11-23T09:00"},
                {"due": "2026-11-24T09:00"}]
        res = schedule_watch.cancel_future(occs, "2026-11-23T09:00")
        self.assertEqual(res["kept"], [{"due": "2026-11-21T09:00"}])
        self.assertEqual(res["cancelled"],
                         [{"due": "2026-11-23T09:00"},
                          {"due": "2026-11-24T09:00"}])

    def test_cancel_before_all_keeps_nothing(self):
        occs = [{"due": "2026-11-23T09:00"}]
        res = schedule_watch.cancel_future(occs, "2026-11-20T09:00")
        self.assertEqual(res["kept"], [])
        self.assertEqual(len(res["cancelled"]), 1)


class TestOccurrenceKey(unittest.TestCase):
    def test_key_is_deterministic_and_slot_scoped(self):
        key = schedule_watch.occurrence_key(POST_ID, "morning", DUE)
        self.assertEqual(
            key, "schedule-watch:morning:%s:%s" % (POST_ID, DUE))
        self.assertNotEqual(
            key, schedule_watch.occurrence_key(POST_ID, "evening",
                                               DUE))

    def test_default_due_uses_slot_time(self):
        self.assertTrue(
            schedule_watch.default_due("morning").endswith("T09:00"))
        self.assertTrue(
            schedule_watch.default_due("evening").endswith("T19:00"))


if __name__ == "__main__":
    unittest.main()
