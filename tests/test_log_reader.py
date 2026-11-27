#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات قارئ السجلات المحدود (lib.log_reader) — جولة v0.1.63
(البندان 19 و21).

تعمل بـ `python3 -m unittest discover -s tests -v`.
كل الكتابة في مجلدات مؤقتة — بلا شبكة وبلا ملفات خارج الشجرة.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import log_reader


def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


class TestClipText(unittest.TestCase):
    def test_short_text_not_clipped(self):
        text, clipped = log_reader.clip_text("قصير")
        self.assertEqual(text, "قصير")
        self.assertFalse(clipped)

    def test_long_text_clipped_at_1000(self):
        text, clipped = log_reader.clip_text("x" * 1500)
        self.assertEqual(len(text), 1000)
        self.assertTrue(clipped)

    def test_exactly_1000_not_clipped(self):
        text, clipped = log_reader.clip_text("x" * 1000)
        self.assertEqual(len(text), 1000)
        self.assertFalse(clipped)

    def test_clip_value_marks_dict(self):
        value, clipped = log_reader.clip_value(
            {"output": "y" * 1200, "kind": "step"})
        self.assertTrue(clipped)
        self.assertTrue(value["clipped"])
        self.assertEqual(len(value["output"]), 1000)
        self.assertEqual(value["kind"], "step")


class TestReadLog(unittest.TestCase):
    def test_reads_jsonl_entries(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "a.ndjson")
            _write_jsonl(path, [{"n": 1, "msg": "أ"},
                                {"n": 2, "msg": "ب"}])
            entries = log_reader.read_log(path)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0]["msg"], "أ")

    def test_read_limit_200_returns_last_200(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "a.ndjson")
            _write_jsonl(path, [{"n": i} for i in range(250)])
            entries = log_reader.read_log(path)
            self.assertEqual(len(entries), 200)
            self.assertEqual(entries[0]["n"], 50)
            self.assertEqual(entries[-1]["n"], 249)
            # حد صريح أصغر يُحترم.
            self.assertEqual(len(log_reader.read_log(path, limit=5)),
                             5)

    def test_read_limit_capped_at_200(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "a.ndjson")
            _write_jsonl(path, [{"n": i} for i in range(250)])
            self.assertEqual(
                len(log_reader.read_log(path, limit=500)), 200)

    def test_read_plain_text_lines(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "a.log")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("سطر أول\nسطر ثانٍ\n")
            entries = log_reader.read_log(path)
            self.assertEqual(entries[0], {"line": 1, "text": "سطر أول"})

    def test_corrupt_line_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "a.ndjson")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write('{"n": 1}\n{تالف\n{"n": 2}\n\n')
            entries = log_reader.read_log(path)
            self.assertEqual([e["n"] for e in entries], [1, 2])

    def test_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(log_reader.LogReaderError):
                log_reader.read_log(os.path.join(td, "غائب.ndjson"))

    def test_invalid_limit_raises(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "a.ndjson")
            _write_jsonl(path, [{"n": 1}])
            for bad in (0, -3, "كثير"):
                with self.assertRaises(log_reader.LogReaderError):
                    log_reader.read_log(path, limit=bad)


class TestSearchLog(unittest.TestCase):
    def _path(self, td):
        path = os.path.join(td, "a.ndjson")
        _write_jsonl(path, [{"n": i, "msg": "قصة العنزة" if i % 2 == 0
                             else "خبر آخر"} for i in range(10)])
        return path

    def test_search_finds_matches(self):
        with tempfile.TemporaryDirectory() as td:
            matches = log_reader.search_log(self._path(td), "العنزة")
            self.assertEqual(len(matches), 5)
            self.assertTrue(all("العنزة" in m["msg"]
                                for m in matches))

    def test_search_case_insensitive(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "a.ndjson")
            _write_jsonl(path, [{"msg": "Hello World"}])
            self.assertEqual(
                len(log_reader.search_log(path, "hello")), 1)

    def test_search_limit_100(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "a.ndjson")
            _write_jsonl(path, [{"n": i, "msg": "مطابق"}
                                for i in range(150)])
            self.assertEqual(
                len(log_reader.search_log(path, "مطابق")), 100)
            self.assertEqual(
                len(log_reader.search_log(path, "مطابق", limit=3)), 3)

    def test_search_empty_query_raises(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(log_reader.LogReaderError):
                log_reader.search_log(self._path(td), "")

    def test_search_long_output_clipped(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "a.ndjson")
            _write_jsonl(path, [{"msg": "z" * 1500}])
            matches = log_reader.search_log(path, "zzz")
            self.assertEqual(len(matches[0]["msg"]), 1000)
            self.assertTrue(matches[0]["clipped"])


class TestJobEvents(unittest.TestCase):
    def test_append_and_read_events(self):
        with tempfile.TemporaryDirectory() as td:
            log_reader.append_job_event(
                td, "job-1", {"kind": "started", "msg": "بدأ"})
            log_reader.append_job_event(
                td, "job-1", {"kind": "completed", "state": "completed"})
            events = log_reader.read_job_events(td, "job-1")
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["kind"], "started")
            self.assertIn("ts", events[0])
            self.assertEqual(events[0]["job_id"], "job-1")
            self.assertTrue(os.path.isfile(
                os.path.join(td, "events", "job-1.ndjson")))

    def test_missing_job_events_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(log_reader.read_job_events(td, "job-x"),
                             [])

    def test_event_without_kind_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(log_reader.LogReaderError):
                log_reader.append_job_event(td, "job-1", {"msg": "x"})

    def test_long_event_output_clipped_at_write(self):
        with tempfile.TemporaryDirectory() as td:
            event = log_reader.append_job_event(
                td, "job-1", {"kind": "step", "output": "q" * 1500})
            self.assertEqual(len(event["output"]), 1000)
            self.assertTrue(event["clipped"])
            stored = log_reader.read_job_events(td, "job-1")
            self.assertEqual(len(stored[0]["output"]), 1000)
            self.assertTrue(stored[0]["clipped"])

    def test_events_limit_200(self):
        with tempfile.TemporaryDirectory() as td:
            for i in range(210):
                log_reader.append_job_event(
                    td, "job-1", {"kind": "step", "n": i})
            events = log_reader.read_job_events(td, "job-1")
            self.assertEqual(len(events), 200)
            self.assertEqual(events[0]["n"], 10)

    def test_resumed_flag(self):
        with tempfile.TemporaryDirectory() as td:
            log_reader.append_job_event(
                td, "job-1", {"kind": "reconnected", "resumed": False})
            events = log_reader.read_job_events(td, "job-1")
            self.assertFalse(log_reader.events_resumed(events))
            self.assertIsNone(log_reader.events_resumed([]))
            self.assertIsNone(log_reader.events_resumed(
                [{"kind": "started"}]))

    def test_events_settled(self):
        with tempfile.TemporaryDirectory() as td:
            log_reader.append_job_event(
                td, "job-1", {"kind": "started"})
            self.assertFalse(log_reader.events_settled(
                log_reader.read_job_events(td, "job-1")))
            log_reader.append_job_event(
                td, "job-1", {"kind": "done", "state": "completed"})
            self.assertTrue(log_reader.events_settled(
                log_reader.read_job_events(td, "job-1")))
            log_reader.append_job_event(
                td, "job-2", {"kind": "wait",
                              "wait_outcome": "timed-out"})
            self.assertTrue(log_reader.events_settled(
                log_reader.read_job_events(td, "job-2")))


if __name__ == "__main__":
    unittest.main()
