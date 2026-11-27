#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات مراقبة المنشور المجدول — كلها على دوال وهمية.

ممنوع تمامًا لمس المنشورات المجدولة الحقيقية أو نشر تعليق
حقيقي: read_fn وcomment_fn هنا عدّادات محلية فقط.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import caption_check
from lib import schedule_watch


STORY = {"moral": "الظلم مهما طال ليله، الحق بيظهر.",
         "question": "لو كنت مكانه، كنت عملت إيه؟",
         "next_part_time": "بكرة 7 مساءً"}
POST_ID = "122132235897269645"


def _fakes(state="published", fail_times=0):
    """دالتان وهميتان بعدّادات استدعاء.

    read_fn ترجع الحالة المطلوبة؛ وcomment_fn تفشل
    fail_times مرات ثم تنجح بقاموس إيصال.
    """
    calls = {"read": 0, "comment": 0, "texts": []}
    failures_left = [fail_times]

    def read_fn(post_id):
        calls["read"] += 1
        calls["read_post_id"] = post_id
        return state

    def comment_fn(post_id, text):
        calls["comment"] += 1
        calls["texts"].append(text)
        if failures_left[0] > 0:
            failures_left[0] -= 1
            raise RuntimeError("رفض فيسبوك التعليق (وهمي)")
        return {"comment_id": "2056409585228722",
                "comment_url": "https://www.facebook.com/xxx"}

    return read_fn, comment_fn, calls


class TestDryRun(unittest.TestCase):
    def test_dry_run_calls_nothing_and_returns_plan(self):
        read_fn, comment_fn, calls = _fakes()
        plan = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                         comment_fn)
        self.assertEqual(calls["read"], 0)
        self.assertEqual(calls["comment"], 0)
        self.assertEqual(plan["post_id"], POST_ID)
        self.assertEqual(plan["slot"], "morning")
        self.assertTrue(plan["would_check"])
        self.assertTrue(plan["dry_run"])
        self.assertIn(STORY["moral"], plan["would_post"])
        self.assertIn(STORY["question"], plan["would_post"])
        self.assertIn("بكرة 7 مساءً", plan["would_post"])

    def test_dry_run_evening_slot(self):
        read_fn, comment_fn, calls = _fakes()
        plan = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                         comment_fn, slot="evening")
        self.assertEqual(plan["slot"], "evening")
        self.assertEqual(calls["read"], 0)
        self.assertEqual(calls["comment"], 0)


class TestExecute(unittest.TestCase):
    def test_execute_published_comments_once_with_exact_text(self):
        read_fn, comment_fn, calls = _fakes(state="published")
        expected = schedule_watch.build_first_comment(STORY)
        res = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                        comment_fn, execute=True)
        self.assertTrue(res["ok"])
        self.assertEqual(calls["read"], 1)
        self.assertEqual(calls["comment"], 1)
        self.assertEqual(calls["texts"][0], expected)
        self.assertEqual(calls["read_post_id"], POST_ID)
        self.assertEqual(res["comment_id"], "2056409585228722")

    def test_execute_published_dict_state(self):
        def read_fn(post_id):
            return {"state": "published", "post_id": post_id}
        _, comment_fn, calls = _fakes()
        res = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                        comment_fn, execute=True)
        self.assertTrue(res["ok"])
        self.assertEqual(calls["comment"], 1)

    def test_execute_scheduled_posts_no_comment(self):
        read_fn, comment_fn, calls = _fakes(state="scheduled")
        res = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                        comment_fn, execute=True)
        self.assertFalse(res["ok"])
        self.assertEqual(res["reason"], "not_published")
        self.assertIn("لم يُنشر بعد", res["message"])
        self.assertEqual(calls["read"], 1)
        self.assertEqual(calls["comment"], 0)

    def test_execute_unknown_state_posts_no_comment(self):
        read_fn, comment_fn, calls = _fakes(state=None)
        res = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                        comment_fn, execute=True)
        self.assertFalse(res["ok"])
        self.assertEqual(res["reason"], "not_published")
        self.assertEqual(res["state"], "غير معروفة")
        self.assertEqual(calls["comment"], 0)

    def test_execute_comment_fails_once_then_succeeds(self):
        read_fn, comment_fn, calls = _fakes(state="published",
                                            fail_times=1)
        res = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                        comment_fn, execute=True)
        self.assertTrue(res["ok"])
        self.assertEqual(calls["comment"], 2)
        self.assertEqual(res["attempts"], 2)

    def test_execute_comment_fails_twice_retries_only_once(self):
        read_fn, comment_fn, calls = _fakes(state="published",
                                            fail_times=2)
        res = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                        comment_fn, execute=True)
        self.assertFalse(res["ok"])
        self.assertEqual(calls["comment"], 2)
        self.assertIn("فشل نشر أول تعليق", res["error"])
        self.assertIn("محاولتين", res["error"])

    def test_execute_comment_fails_many_times_still_two_attempts(self):
        read_fn, comment_fn, calls = _fakes(state="published",
                                            fail_times=10)
        res = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                        comment_fn, execute=True)
        self.assertFalse(res["ok"])
        self.assertEqual(calls["comment"], 2)

    def test_execute_read_failure_returns_arabic_error(self):
        def read_fn(post_id):
            raise RuntimeError("انقطع الاتصال (وهمي)")
        _, comment_fn, calls = _fakes()
        res = schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                        comment_fn, execute=True)
        self.assertFalse(res["ok"])
        self.assertIn("تعذّرت قراءة حالة المنشور", res["error"])
        self.assertEqual(calls["comment"], 0)


class TestBuildFirstComment(unittest.TestCase):
    def test_contains_moral_question_and_next_part_time(self):
        text = schedule_watch.build_first_comment(STORY)
        self.assertIn("«الظلم مهما طال ليله، الحق بيظهر.»", text)
        self.assertIn("لو كنت مكانه، كنت عملت إيه؟", text)
        self.assertIn("بكرة 7 مساءً", text)
        self.assertIn("اعمل متابعة عشان يوصلك أول ما ينزل", text)

    def test_every_sentence_passes_caption_check(self):
        text = schedule_watch.build_first_comment(STORY)
        for sentence in caption_check.split_sentences(text):
            self.assertIsNone(caption_check.sentence_issue(sentence),
                              "جملة مرفوضة: %s" % sentence)

    def test_default_next_part_time_when_missing(self):
        story = {"moral": STORY["moral"],
                 "question": STORY["question"]}
        text = schedule_watch.build_first_comment(story)
        self.assertIn(caption_check.DEFAULT_NEXT_PART_TIME, text)
        for sentence in caption_check.split_sentences(text):
            self.assertIsNone(caption_check.sentence_issue(sentence))

    def test_missing_moral_raises_value_error(self):
        with self.assertRaises(ValueError):
            schedule_watch.build_first_comment(
                {"question": STORY["question"]})

    def test_missing_question_raises_value_error(self):
        with self.assertRaises(ValueError):
            schedule_watch.build_first_comment(
                {"moral": STORY["moral"]})

    def test_uses_approved_invite_not_a_rewording(self):
        text = schedule_watch.build_first_comment(STORY)
        self.assertIn(
            caption_check.approved_invite("بكرة 7 مساءً"), text)


class TestValidation(unittest.TestCase):
    def test_missing_post_id_raises(self):
        read_fn, comment_fn, _ = _fakes()
        with self.assertRaises(ValueError):
            schedule_watch.watch_slot("", STORY, read_fn, comment_fn)

    def test_bad_slot_raises(self):
        read_fn, comment_fn, _ = _fakes()
        with self.assertRaises(ValueError):
            schedule_watch.watch_slot(POST_ID, STORY, read_fn,
                                      comment_fn, slot="noon")


class TestWatchResultToPublishStatus(unittest.TestCase):
    """ترجمة نتيجة watch_slot إلى حالة نشر موحّدة (أ2-8)."""

    def test_published_ok_maps_to_published(self):
        self.assertEqual(
            schedule_watch.status_from_watch({"ok": True}),
            "published")

    def test_not_published_maps_to_pending(self):
        self.assertEqual(
            schedule_watch.status_from_watch(
                {"ok": False, "reason": "not_published"}),
            "pending")

    def test_error_maps_to_failed(self):
        self.assertEqual(
            schedule_watch.status_from_watch(
                {"ok": False, "error": "فشل نشر أول تعليق"}),
            "failed")

    def test_dry_run_and_empty_map_to_pending(self):
        self.assertEqual(schedule_watch.status_from_watch(
            {"dry_run": True}), "pending")
        self.assertEqual(schedule_watch.status_from_watch({}),
                         "pending")
        self.assertEqual(schedule_watch.status_from_watch(None),
                         "pending")

    def test_apply_watch_result_updates_facebook_by_default(self):
        statuses = {}
        entry = schedule_watch.apply_watch_result(
            statuses, 3, {"ok": True})
        self.assertEqual(entry["facebook"], "published")
        self.assertEqual(entry["youtube"], "pending")
        entry = schedule_watch.apply_watch_result(
            statuses, 3, {"ok": False, "error": "فشل"})
        self.assertEqual(entry["facebook"], "failed")

    def test_apply_watch_result_not_published_keeps_pending(self):
        entry = schedule_watch.apply_watch_result(
            {}, 5, {"ok": False, "reason": "not_published"})
        self.assertEqual(entry["facebook"], "pending")


if __name__ == "__main__":
    unittest.main()


# ─── اختبارات جولة v0.1.63 (W6): سجل الروتينات + اللحاق +
# فحوص ما قبل النموذج + التراجع + الخنق + الإقلاع + المشغول ───
import random
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from lib import retry_policy

_CAIRO = ZoneInfo("Africa/Cairo")


def _now_iso():
    return datetime.now(tz=_CAIRO).isoformat(timespec="seconds")


def _hours_ago_iso(hours):
    moment = datetime.now(tz=_CAIRO) - timedelta(hours=hours)
    return moment.isoformat(timespec="seconds")


class TestRoutineLedger(unittest.TestCase):
    def test_append_and_read_roundtrip_exact_schema(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            line = schedule_watch.append_ledger(
                runs_dir, "morning-brief", "ran", "completed",
                job_id="job-1")
            self.assertEqual(set(line),
                             {"ts", "routine", "state", "reason",
                              "job_id", "count"})
            self.assertEqual(line["routine"], "morning-brief")
            self.assertEqual(line["state"], "ran")
            self.assertEqual(line["reason"], "completed")
            self.assertEqual(line["count"], 1)
            rows = schedule_watch.read_ledger(runs_dir)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0], line)

    def test_ledger_has_only_ids_times_counts_never_prompts(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            schedule_watch.append_ledger(
                runs_dir, "r1", "skipped", "no_new_data")
            with open(schedule_watch.ledger_path(runs_dir),
                      encoding="utf-8") as fh:
                text = fh.read()
            for forbidden in ("prompt", "مطالبة", "output", "مخرجات"):
                self.assertNotIn(forbidden, text)

    def test_invalid_state_and_reason_raise(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            with self.assertRaises(ValueError):
                schedule_watch.append_ledger(
                    runs_dir, "r1", "done", "completed")
            with self.assertRaises(ValueError):
                schedule_watch.append_ledger(
                    runs_dir, "r1", "ran", "because-busy")
            with self.assertRaises(ValueError):
                schedule_watch.append_ledger(
                    runs_dir, "", "ran", "completed")

    def test_all_six_states_and_nine_reasons_accepted(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            for state in schedule_watch.ROUTINE_STATES:
                schedule_watch.append_ledger(
                    runs_dir, "r1", state, "completed"
                    if state == "ran" else "manual_skip"
                    if state == "skipped" else None
                    if state in ("running", "queued") else "failed")
            self.assertEqual(
                len(schedule_watch.read_ledger(runs_dir)), 6)

    def test_corrupt_line_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            schedule_watch.append_ledger(
                runs_dir, "r1", "ran", "completed")
            with open(schedule_watch.ledger_path(runs_dir), "a",
                      encoding="utf-8") as fh:
                fh.write("{not json\n\n")
            schedule_watch.append_ledger(
                runs_dir, "r1", "failed", "failed")
            rows = schedule_watch.read_ledger(runs_dir)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["state"], "ran")
            self.assertEqual(rows[1]["state"], "failed")

    def test_read_ledger_filters_and_limit(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            schedule_watch.append_ledger(
                runs_dir, "a", "ran", "completed")
            schedule_watch.append_ledger(
                runs_dir, "b", "failed", "failed")
            schedule_watch.append_ledger(
                runs_dir, "a", "missed", "missed_window")
            self.assertEqual(
                len(schedule_watch.read_ledger(runs_dir, routine="a")),
                2)
            self.assertEqual(
                len(schedule_watch.read_ledger(
                    runs_dir, state="failed")), 1)
            self.assertEqual(
                len(schedule_watch.read_ledger(runs_dir, limit=1)), 1)
            self.assertEqual(
                schedule_watch.read_ledger(runs_dir, limit=1)[0]
                ["state"], "missed")


class TestPreviousActive(unittest.TestCase):
    def test_running_previous_is_active_and_skipped(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            self.assertFalse(
                schedule_watch.is_previous_active(runs_dir, "r1"))
            schedule_watch.append_ledger(
                runs_dir, "r1", "running", None)
            self.assertTrue(
                schedule_watch.is_previous_active(runs_dir, "r1"))
            verdict = schedule_watch.skip_if_previous_active(
                runs_dir, "r1", job_id="job-9")
            self.assertTrue(verdict["skipped"])
            self.assertEqual(verdict["reason"], "previous_active")
            rows = schedule_watch.read_ledger(runs_dir, routine="r1")
            self.assertEqual(rows[-1]["state"], "skipped")
            self.assertEqual(rows[-1]["reason"], "previous_active")

    def test_completed_previous_is_not_active(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            schedule_watch.append_ledger(
                runs_dir, "r1", "running", None)
            schedule_watch.append_ledger(
                runs_dir, "r1", "ran", "completed")
            self.assertFalse(
                schedule_watch.is_previous_active(runs_dir, "r1"))
            verdict = schedule_watch.skip_if_previous_active(
                runs_dir, "r1")
            self.assertFalse(verdict["skipped"])
            self.assertIsNone(verdict["ledger"])
            self.assertEqual(
                len(schedule_watch.read_ledger(runs_dir)), 2)

    def test_queued_alone_is_not_a_running_turn(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            schedule_watch.append_ledger(
                runs_dir, "r1", "queued", "busy_wait")
            self.assertFalse(
                schedule_watch.is_previous_active(runs_dir, "r1"))

    def test_watch_slot_skips_when_previous_active(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            schedule_watch.append_ledger(
                runs_dir, "watch-routine", "running", None)
            read_fn, comment_fn, calls = _fakes(state="published")
            res = schedule_watch.watch_slot(
                POST_ID, STORY, read_fn, comment_fn, execute=True,
                runs_dir=runs_dir, routine="watch-routine")
            self.assertFalse(res["ok"])
            self.assertEqual(res["reason"], "previous_active")
            self.assertTrue(res["skipped"])
            self.assertEqual(calls["read"], 0)
            self.assertEqual(calls["comment"], 0)

    def test_watch_slot_runs_when_previous_completed(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            schedule_watch.append_ledger(
                runs_dir, "watch-routine", "running", None)
            schedule_watch.append_ledger(
                runs_dir, "watch-routine", "ran", "completed")
            read_fn, comment_fn, calls = _fakes(state="published")
            res = schedule_watch.watch_slot(
                POST_ID, STORY, read_fn, comment_fn, execute=True,
                runs_dir=runs_dir, routine="watch-routine")
            self.assertTrue(res["ok"])
            self.assertEqual(calls["comment"], 1)


class TestCatchUp12h(unittest.TestCase):
    def test_newest_within_12h_runs_late(self):
        now = datetime.now(tz=_CAIRO)
        missed = [_hours_ago_iso(2), _hours_ago_iso(5)]
        plan = schedule_watch.plan_catch_up_12h(missed, now=now)
        self.assertTrue(plan["run_late"])
        self.assertEqual(plan["run"], max(missed))
        self.assertEqual(plan["missed_count"], 0)
        self.assertEqual(plan["missed_collapsed"], [])

    def test_older_than_12h_collapses_into_one_missed(self):
        now = datetime.now(tz=_CAIRO)
        missed = [_hours_ago_iso(2), _hours_ago_iso(20),
                  _hours_ago_iso(30)]
        plan = schedule_watch.plan_catch_up_12h(missed, now=now)
        self.assertEqual(plan["run"], _hours_ago_iso(2))
        self.assertEqual(plan["missed_count"], 2)
        self.assertEqual(len(plan["missed_collapsed"]), 2)
        self.assertEqual(plan["skipped"], [])

    def test_all_older_than_12h_no_run(self):
        now = datetime.now(tz=_CAIRO)
        missed = [_hours_ago_iso(13), _hours_ago_iso(26)]
        plan = schedule_watch.plan_catch_up_12h(missed, now=now)
        self.assertIsNone(plan["run"])
        self.assertFalse(plan["run_late"])
        self.assertEqual(plan["missed_count"], 2)

    def test_future_due_is_not_missed(self):
        now = datetime.now(tz=_CAIRO)
        future = (now + timedelta(hours=1)).isoformat(
            timespec="seconds")
        plan = schedule_watch.plan_catch_up_12h([future], now=now)
        self.assertIsNone(plan["run"])
        self.assertEqual(plan["missed_count"], 0)
        self.assertEqual(plan["future"], [future])

    def test_invalid_due_raises(self):
        with self.assertRaises(ValueError):
            schedule_watch.plan_catch_up_12h(["not-a-date"])

    def test_apply_catch_up_writes_single_missed_row(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            now = datetime.now(tz=_CAIRO)
            missed = [_hours_ago_iso(2), _hours_ago_iso(20),
                      _hours_ago_iso(30)]
            plan = schedule_watch.apply_catch_up(
                runs_dir, "r1", missed, now=now)
            self.assertEqual(plan["missed_count"], 2)
            rows = schedule_watch.read_ledger(
                runs_dir, routine="r1", state="missed")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["reason"], "missed_window")
            self.assertEqual(rows[0]["count"], 2)

    def test_record_missed_collapsed_empty_writes_nothing(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            self.assertIsNone(
                schedule_watch.record_missed_collapsed(
                    runs_dir, "r1", []))
            self.assertEqual(
                schedule_watch.read_ledger(runs_dir), [])


class TestPreModelChecks(unittest.TestCase):
    def test_no_new_data_means_no_model_turn(self):
        result = schedule_watch.run_pre_model_checks(
            {"calendar": lambda: False, "mail": lambda: None})
        self.assertFalse(result["has_new_data"])
        self.assertFalse(result["failed"])
        self.assertFalse(schedule_watch.should_run_model(result))
        self.assertTrue(schedule_watch.is_no_new_data(result))
        self.assertIn("checked_at", result)

    def test_new_data_means_model_turn(self):
        result = schedule_watch.run_pre_model_checks(
            {"calendar": lambda: {"has_new": True,
                                  "detail": "اجتماع جديد"},
             "mail": lambda: False})
        self.assertTrue(result["has_new_data"])
        self.assertTrue(schedule_watch.should_run_model(result))
        self.assertFalse(schedule_watch.is_no_new_data(result))

    def test_failing_check_is_not_no_new_data(self):
        def boom():
            raise RuntimeError("انقطع التقويم (وهمي)")

        result = schedule_watch.run_pre_model_checks(
            {"calendar": boom, "mail": lambda: False})
        self.assertTrue(result["failed"])
        self.assertFalse(schedule_watch.should_run_model(result))
        self.assertFalse(schedule_watch.is_no_new_data(result))
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("calendar", result["results"])
        self.assertIsNotNone(
            result["results"]["calendar"]["error"])

    def test_malformed_check_reading_is_not_no_new_data(self):
        result = schedule_watch.run_pre_model_checks(
            {"weird": lambda: "yes-maybe"})
        self.assertTrue(result["failed"])
        self.assertFalse(schedule_watch.should_run_model(result))
        self.assertFalse(schedule_watch.is_no_new_data(result))

    def test_no_new_data_ledger_row(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            line = schedule_watch.record_no_new_data(
                runs_dir, "r1", checked_at=_now_iso())
            self.assertEqual(line["state"], "skipped")
            self.assertEqual(line["reason"], "no_new_data")

    def test_check_failed_ledger_row(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            line = schedule_watch.record_check_failed(runs_dir, "r1")
            self.assertEqual(line["state"], "failed")
            self.assertEqual(line["reason"], "check_failed")


class TestRoutineBackoff(unittest.TestCase):
    def test_sequence_doubles_to_four_hour_cap(self):
        self.assertEqual(
            retry_policy.routine_backoff_sequence(7),
            [900, 1800, 3600, 7200, 14400, 14400, 14400])

    def test_sequence_empty_for_zero(self):
        self.assertEqual(
            retry_policy.routine_backoff_sequence(0), [])

    def test_delay_without_jitter_is_exact(self):
        self.assertEqual(
            schedule_watch.backoff_delay(0, jitter=False), 900)
        self.assertEqual(
            schedule_watch.backoff_delay(1, jitter=False), 1800)
        self.assertEqual(
            schedule_watch.backoff_delay(4, jitter=False), 14400)
        self.assertEqual(
            schedule_watch.backoff_delay(99, jitter=False), 14400)

    def test_delay_with_jitter_stays_within_bounds(self):
        rng = random.Random(7)
        for index, cap in ((0, 900), (2, 3600), (9, 14400)):
            delay = schedule_watch.backoff_delay(
                index, jitter=True, rng=rng)
            self.assertGreaterEqual(delay, 0)
            self.assertLessEqual(delay, cap)


class TestAiTurnCap(unittest.TestCase):
    def test_pure_count_allows_23_blocks_24(self):
        now = datetime.now(tz=_CAIRO)
        stamps = [(now - timedelta(hours=i)).isoformat()
                  for i in range(23)]
        self.assertTrue(schedule_watch.ai_turns_allowed(stamps, now=now))
        stamps.append((now - timedelta(minutes=1)).isoformat())
        self.assertFalse(
            schedule_watch.ai_turns_allowed(stamps, now=now))
        self.assertEqual(
            schedule_watch.ai_turns_in_window(stamps, now=now), 24)

    def test_old_turns_fall_out_of_window(self):
        now = datetime.now(tz=_CAIRO)
        stamps = [(now - timedelta(hours=25)).isoformat()]
        self.assertEqual(
            schedule_watch.ai_turns_in_window(stamps, now=now), 0)
        self.assertTrue(schedule_watch.ai_turns_allowed(stamps, now=now))

    def test_file_backed_cap_blocks_25th_and_logs_row(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            now = datetime.now(tz=_CAIRO)
            for i in range(24):
                schedule_watch.record_ai_turn(
                    runs_dir, "r1",
                    now=now - timedelta(minutes=i))
            verdict = schedule_watch.check_ai_cap(
                runs_dir, "r1", now=now)
            self.assertFalse(verdict["allowed"])
            self.assertEqual(verdict["reason"], "cap_reached")
            self.assertEqual(verdict["used"], 24)
            rows = schedule_watch.read_ledger(
                runs_dir, routine="r1", state="skipped")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["reason"], "cap_reached")

    def test_file_backed_cap_allows_under_limit(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            now = datetime.now(tz=_CAIRO)
            for i in range(3):
                schedule_watch.record_ai_turn(
                    runs_dir, "r1",
                    now=now - timedelta(minutes=i))
            verdict = schedule_watch.check_ai_cap(
                runs_dir, "r1", now=now)
            self.assertTrue(verdict["allowed"])
            self.assertEqual(verdict["used"], 3)
            self.assertEqual(schedule_watch.read_ledger(runs_dir), [])

    def test_cap_counts_per_routine_when_named(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            now = datetime.now(tz=_CAIRO)
            for i in range(24):
                schedule_watch.record_ai_turn(
                    runs_dir, "other",
                    now=now - timedelta(minutes=i))
            verdict = schedule_watch.check_ai_cap(
                runs_dir, "r1", now=now)
            self.assertTrue(verdict["allowed"])
            self.assertEqual(verdict["used"], 0)


class TestBootDelay(unittest.TestCase):
    def test_just_started_waits_about_two_minutes(self):
        now = datetime.now(tz=_CAIRO)
        started = now - timedelta(seconds=30)
        remaining = schedule_watch.boot_delay_remaining(
            started, now=now)
        self.assertGreaterEqual(remaining, 85)
        self.assertLessEqual(remaining, 95)
        self.assertTrue(schedule_watch.should_wait_for_boot(
            started, now=now))

    def test_started_three_minutes_ago_waits_nothing(self):
        now = datetime.now(tz=_CAIRO)
        started = now - timedelta(minutes=3)
        self.assertEqual(
            schedule_watch.boot_delay_remaining(started, now=now), 0)
        self.assertFalse(schedule_watch.should_wait_for_boot(
            started, now=now))

    def test_unparseable_start_means_no_block(self):
        self.assertEqual(
            schedule_watch.boot_delay_remaining("not-a-date"), 0)


class TestBusyWait(unittest.TestCase):
    def test_busy_waits_without_notify_and_never_fails(self):
        decision = schedule_watch.busy_wait_decision(True)
        self.assertTrue(decision["wait"])
        self.assertFalse(decision["notify"])
        self.assertFalse(decision["fail"])
        self.assertEqual(decision["reason"], "busy_wait")

    def test_free_worker_does_not_wait(self):
        decision = schedule_watch.busy_wait_decision(False)
        self.assertFalse(decision["wait"])
        self.assertFalse(decision["fail"])
        self.assertIsNone(decision["reason"])

    def test_note_busy_wait_writes_queued_row(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            decision = schedule_watch.note_busy_wait(runs_dir, "r1")
            self.assertTrue(decision["wait"])
            self.assertFalse(decision["notify"])
            rows = schedule_watch.read_ledger(runs_dir, routine="r1")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["state"], "queued")
            self.assertEqual(rows[0]["reason"], "busy_wait")
