#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات سجل التشغيل البنيوي (lib.run_log) — جولة تطبيق الأنماط (W5b).

تعمل بـ `env -u PYTHONNOUSERSITE python3 -m unittest
tests.test_run_log -v` من ~/workspace/studio/. بلا شبكة وبلا
كتابة خارج مجلد مؤقت: كل اختبار يكتب في TemporaryDirectory
أو يمنع الكتابة أصلًا (write=False). ساعة وهمية قابلة للحقن
تثبت توقيت المراحل حتميًا.
"""
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import run_log


class _FakeClock:
    """ساعة وهمية: monotonic يتقدم بخطوات ثابتة، والآن ثابت."""

    def __init__(self):
        self.mono = 1000.0
        self.now = datetime(2026, 11, 26, 1, 0, 0, tzinfo=timezone.utc)

    def monotonic(self):
        return self.mono

    def advance(self, seconds):
        self.mono += seconds

    def now_fn(self):
        return self.now


def _make_log(command="run", clock=None, **kwargs):
    clock = clock or _FakeClock()
    kwargs.setdefault("write", False)
    return run_log.RunLog(command, time_fn=clock.monotonic,
                          now_fn=clock.now_fn, **kwargs)


class TestCorrelationId(unittest.TestCase):
    def test_generated_id_is_32_hex_chars(self):
        log = _make_log()
        self.assertRegex(log.correlation_id, r"^[0-9a-f]{32}$")

    def test_ids_are_unique(self):
        ids = {_make_log().correlation_id for _ in range(50)}
        self.assertEqual(len(ids), 50)

    def test_explicit_id_is_kept(self):
        log = _make_log(correlation_id="a" * 32)
        self.assertEqual(log.correlation_id, "a" * 32)

    def test_id_appears_in_dict_and_summary(self):
        log = _make_log(correlation_id="b" * 32)
        log.start()
        log.finish()
        self.assertEqual(log.to_dict()["correlation_id"], "b" * 32)
        self.assertIn("bbbbbbbb", log.format_summary())

    def test_new_correlation_id_helper(self):
        self.assertRegex(run_log.new_correlation_id(), r"^[0-9a-f]{32}$")


class TestStageTiming(unittest.TestCase):
    def test_stage_records_start_end_and_duration(self):
        clock = _FakeClock()
        log = _make_log(clock=clock)
        log.start()
        log.start_stage("script")
        clock.advance(2.5)
        log.end_stage("script")
        clock.advance(1.0)
        log.finish()
        stages = log.to_dict()["stages"]
        self.assertEqual(len(stages), 1)
        stage = stages[0]
        self.assertEqual(stage["name"], "script")
        self.assertEqual(stage["status"], "ok")
        self.assertEqual(stage["duration_seconds"], 2.5)
        self.assertEqual(stage["started_at"], "2026-11-26T01:00:00+00:00")
        self.assertEqual(stage["ended_at"], "2026-11-26T01:00:00+00:00")
        self.assertEqual(log.duration_seconds, 3.5)

    def test_stage_context_manager_ok(self):
        clock = _FakeClock()
        log = _make_log(clock=clock)
        with log:
            with log.stage("produce"):
                clock.advance(4.0)
        stage = log.to_dict()["stages"][0]
        self.assertEqual(stage["status"], "ok")
        self.assertEqual(stage["duration_seconds"], 4.0)
        self.assertEqual(log.status, "ok")

    def test_stage_context_manager_records_failure_and_reraises(self):
        log = _make_log()
        with self.assertRaises(ValueError):
            with log:
                with log.stage("assemble"):
                    raise ValueError("التصدير لم يكتمل")
        self.assertEqual(log.status, "failed")
        self.assertEqual(log.failed_stages(), ["assemble"])
        self.assertEqual(log.error_count, 1)
        self.assertEqual(log.first_error["category"],
                         "concat_export_failed")
        self.assertEqual(log.first_error["code"], "STUDIO-CONCAT-001")

    def test_end_stage_wrong_name_raises(self):
        log = _make_log()
        log.start_stage("script")
        with self.assertRaises(RuntimeError):
            log.end_stage("produce")

    def test_nested_stage_raises(self):
        log = _make_log()
        log.start_stage("script")
        with self.assertRaises(RuntimeError):
            log.start_stage("produce")


class TestCentralErrorHandler(unittest.TestCase):
    def test_record_error_classifies_with_code_and_runbook(self):
        log = _make_log()
        log.start()
        entry = log.record_error("ffmpeg: command not found")
        self.assertEqual(entry["category"], "ffmpeg_not_found")
        self.assertEqual(entry["code"], "STUDIO-FFMPEG-001")
        self.assertEqual(entry["runbook"],
                         "docs/ERRORS-RUNBOOK.md#studio-ffmpeg-001")
        self.assertEqual(log.error_count, 1)
        self.assertTrue(log.has_errors)

    def test_record_error_keeps_stage(self):
        log = _make_log()
        log.start_stage("publish")
        entry = log.record_error("quotaExceeded", stage="publish")
        self.assertEqual(entry["stage"], "publish")
        self.assertEqual(entry["category"], "youtube_quota")
        log.end_stage("publish", error=RuntimeError("quotaExceeded"))
        # الخطأ الثاني من إغلاق المرحلة يُجمَّع أيضًا ولا يُستبدل الأول.
        self.assertEqual(log.error_count, 2)
        self.assertEqual(log.first_error["category"], "youtube_quota")

    def test_multiple_errors_all_collected_in_order(self):
        log = _make_log()
        log.record_error("ffmpeg: command not found")
        log.record_error("No such file or directory: '/tmp/x.mp4'")
        log.record_error("Something completely unexpected")
        self.assertEqual(log.error_count, 3)
        codes = [e["code"] for e in log.errors]
        self.assertEqual(codes, ["STUDIO-FFMPEG-001",
                                 "STUDIO-FILE-001",
                                 "STUDIO-UNKNOWN-001"])
        self.assertEqual(log.first_error["code"], "STUDIO-FFMPEG-001")

    def test_finish_failed_when_errors_exist(self):
        log = _make_log()
        log.start()
        log.record_error("ffmpeg: command not found")
        log.finish()
        self.assertEqual(log.status, "failed")

    def test_finish_ok_when_no_errors(self):
        log = _make_log()
        with log:
            with log.stage("check"):
                pass
        self.assertEqual(log.status, "ok")
        self.assertEqual(log.error_count, 0)
        self.assertIsNone(log.first_error)

    def test_record_error_never_raises(self):
        log = _make_log()
        for weird in (None, "", 0, [], {}, object()):
            entry = log.record_error(weird)
            self.assertIn("code", entry)
        self.assertEqual(log.error_count, 6)

    def test_context_manager_exception_is_recorded_and_reraised(self):
        log = _make_log()
        with self.assertRaises(RuntimeError):
            with log:
                raise RuntimeError("Conversion failed!")
        self.assertEqual(log.status, "failed")
        self.assertEqual(log.first_error["category"],
                         "ffmpeg_encode_failed")

    def test_explicit_finish_status_wins(self):
        log = _make_log()
        log.start()
        log.finish(status="skipped")
        self.assertEqual(log.status, "skipped")

    def test_outputs_recorded(self):
        log = _make_log()
        log.finish(output={"video": "/tmp/out.mp4"})
        self.assertEqual(log.to_dict()["outputs"],
                         {"video": "/tmp/out.mp4"})


class TestJsonFile(unittest.TestCase):
    def test_finish_writes_one_valid_json_file(self):
        clock = _FakeClock()
        with tempfile.TemporaryDirectory() as tmp:
            log = run_log.RunLog(
                "run", correlation_id="c" * 32, out_dir=tmp,
                time_fn=clock.monotonic, now_fn=clock.now_fn)
            with log:
                with log.stage("script"):
                    clock.advance(1.5)
            expected = os.path.join(tmp, "run-log-" + "c" * 32 + ".json")
            self.assertEqual(log.log_path, expected)
            self.assertTrue(os.path.isfile(expected))
            with open(expected, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["schema_version"], 1)
            self.assertEqual(data["correlation_id"], "c" * 32)
            self.assertEqual(data["command"], "run")
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["error_count"], 0)
            self.assertEqual(data["stages"][0]["duration_seconds"], 1.5)
            # لا مفاتيح داخلية (تبدأ بـ _) تتسرب إلى JSON.
            self.assertNotIn("_mono_start", data["stages"][0])

    def test_write_failure_does_not_raise(self):
        # out_dir ملف لا مجلد — الكتابة مستحيلة، والسجل لا يكسر الأمر.
        with tempfile.NamedTemporaryFile() as tmpfile:
            log = run_log.RunLog("run", out_dir=tmpfile.name,
                                 write=True)
            log.start()
            log.finish()
            self.assertIsNotNone(log.write_error)
            self.assertIsNone(log.log_path)
            self.assertEqual(log.status, "ok")

    def test_start_run_helper(self):
        log = run_log.start_run("check", write=False)
        self.assertIsNotNone(log.started_at)
        log.finish()
        self.assertEqual(log.status, "ok")

    def test_summary_mentions_first_error_code(self):
        log = _make_log()
        log.start()
        log.record_error("ffmpeg: command not found")
        log.finish()
        summary = log.format_summary()
        self.assertIn("STUDIO-FFMPEG-001", summary)
        self.assertIn("docs/ERRORS-RUNBOOK.md#studio-ffmpeg-001", summary)
        self.assertIn("فشل", summary)


if __name__ == "__main__":
    unittest.main()
