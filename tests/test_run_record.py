#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات سجل التشغيل — جولة v0.1.37 (مقترح tinker رقم 10)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import run_record


class TestResolveSettings(unittest.TestCase):
    def test_defaults_from_empty_config(self):
        settings = run_record.resolve_settings({})
        self.assertEqual(settings["voice"], "piper")
        self.assertEqual(settings["atempo"], 1.0)
        self.assertEqual(settings["backend"], "concat")
        self.assertEqual(settings["duration_min_seconds"], 40)
        self.assertEqual(settings["duration_max_seconds"], 60)
        self.assertIsNone(settings["veo_balance_units"])

    def test_real_config_values_win(self):
        cfg = {
            "narration": {"voice": "gtts", "atempo": 1.25},
            "omniroute": {"model": "ddgw/gpt-5.4-mini",
                          "fallback_model": "ddgw/llama-3.3-70b"},
            "video": {"width": 720, "height": 1280,
                      "duration_min_seconds": 45,
                      "duration_max_seconds": 55},
            "veo": {"balance_units": 680,
                    "updated_at": "2026-11-22T14:50:00+02:00"},
        }
        settings = run_record.resolve_settings(
            cfg, {"backend": "openreel", "grade": "warm",
                  "watermark": False, "story": "anza",
                  "project": "anza-part1"})
        self.assertEqual(settings["voice"], "gtts")
        self.assertEqual(settings["atempo"], 1.25)
        self.assertEqual(settings["llm_model"], "ddgw/gpt-5.4-mini")
        self.assertEqual(settings["backend"], "openreel")
        self.assertEqual(settings["llm_chain"],
                         ["ddgw/gpt-5.4-mini", "ddgw/llama-3.3-70b",
                          "gemini-3.1-flash-lite",
                          "gemini-3-flash-preview", "qwen2.5:7b"])
        self.assertEqual(settings["grade"], "warm")
        self.assertFalse(settings["watermark"])
        self.assertEqual(settings["video_size"], "720x1280")
        self.assertEqual(settings["veo_balance_units"], 680)
        self.assertEqual(settings["story"], "anza")

    def test_datetime_updated_at_serializes(self):
        # عيب وُجد حيًا في `run --demo` أثناء التحقق النهائي:
        # PyYAML يقرأ `veo.updated_at` من config.yaml كـdatetime
        # (لا نص) فكان `json.dump` في begin_record يتعطل بـ
        # TypeError ويُسقط كل تشغيل إنتاج قبل أن يبدأ.
        from datetime import datetime
        from zoneinfo import ZoneInfo
        cfg = {"veo": {"balance_units": 680,
                       "updated_at": datetime(
                           2026, 11, 22, 14, 50, 47,
                           tzinfo=ZoneInfo("Africa/Cairo"))}}
        settings = run_record.resolve_settings(cfg)
        self.assertIsInstance(settings["veo_balance_updated_at"], str)
        self.assertIn("2026-11-22T14:50:47",
                      settings["veo_balance_updated_at"])
        with tempfile.TemporaryDirectory() as td:
            path, _ = run_record.begin_record(td, "demo", settings)
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
            self.assertEqual(
                record["settings"]["veo_balance_updated_at"],
                "2026-11-22T14:50:47+02:00")


class TestRecordLifecycle(unittest.TestCase):
    def test_begin_and_finish_done(self):
        with tempfile.TemporaryDirectory() as td:
            settings = run_record.resolve_settings(
                {}, {"story": "demo"})
            path, run_id = run_record.begin_record(td, "demo", settings)
            self.assertTrue(os.path.isfile(path))
            self.assertTrue(path.endswith(".json"))
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
            self.assertEqual(record["status"], "running")
            self.assertEqual(record["command"], "demo")
            self.assertEqual(record["settings"]["voice"], "piper")
            # الطابع الزمني بتوقيت القاهرة (+02/+03 حسب التوقيت الصيفي).
            self.assertTrue(record["started_at"].endswith(("+02:00", "+03:00")),
                            record["started_at"])
            finished = run_record.finish_record(
                path, "done", outputs=["/tmp/demo.mp4"])
            self.assertEqual(finished["status"], "done")
            self.assertEqual(finished["outputs"], ["/tmp/demo.mp4"])
            self.assertIn("finished_at", finished)
            self.assertIsInstance(finished["duration_seconds"], float)

    def test_finish_failed_keeps_error(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = run_record.begin_record(
                td, "run", run_record.resolve_settings({}))
            finished = run_record.finish_record(
                path, "failed", error=RuntimeError("فشل تجريبي"))
            self.assertEqual(finished["status"], "failed")
            self.assertIn("فشل تجريبي", finished["error"])

    def test_two_records_same_second_get_unique_names(self):
        with tempfile.TemporaryDirectory() as td:
            settings = run_record.resolve_settings({})
            p1, _ = run_record.begin_record(td, "run", settings)
            p2, _ = run_record.begin_record(td, "run", settings)
            self.assertNotEqual(p1, p2)

    def test_print_settings_lists_resolved_values(self):
        import io
        from contextlib import redirect_stdout
        settings = run_record.resolve_settings(
            {"narration": {"voice": "piper"}},
            {"backend": "concat"})
        buf = io.StringIO()
        with redirect_stdout(buf):
            run_record.print_settings(settings)
        text = buf.getvalue()
        self.assertIn("voice: piper", text)
        self.assertIn("backend: concat", text)


if __name__ == "__main__":
    unittest.main()
