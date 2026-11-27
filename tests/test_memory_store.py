#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات مخزن الذاكرة بميزانية — جولة v0.1.63 (بند 14، عقد ع13).

معزولة: مجلدات مؤقتة فقط، بلا شبكة، بلا قراءة خارج الشجرة.
"""
import os
import stat
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import memory_store
from lib.memory_store import MemoryStore


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class TestLoadBudget(unittest.TestCase):
    def test_500_lines_loads_200_only(self):
        with tempfile.TemporaryDirectory() as td:
            _write(os.path.join(td, "MEMORY.md"),
                   "".join("سطر %d\n" % i for i in range(500)))
            store = MemoryStore(td)
            loaded = store.load_memory()
            self.assertEqual(len(loaded.splitlines()), 200)
            self.assertIn("سطر 0", loaded)
            self.assertNotIn("سطر 200", loaded)

    def test_24kb_cap(self):
        with tempfile.TemporaryDirectory() as td:
            _write(os.path.join(td, "MEMORY.md"),
                   "x" * 30000 + "\nسطر أخير\n")
            store = MemoryStore(td)
            loaded = store.load_memory()
            self.assertLessEqual(len(loaded.encode("utf-8")), 24 * 1024)
            self.assertNotIn("سطر أخير", loaded)

    def test_missing_file_loads_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(MemoryStore(td).load_memory(), "")


class TestRedact(unittest.TestCase):
    def test_api_key_redacted_with_length(self):
        value = "abc123XYZ"
        text = "api_key = %s" % value
        redacted = memory_store.redact_credentials(text)
        self.assertNotIn(value, redacted)
        self.assertIn("«redacted %d chars»" % len(value), redacted)

    def test_bearer_redacted(self):
        value = "tok-987"
        redacted = memory_store.redact_credentials("Bearer %s" % value)
        self.assertNotIn(value, redacted)
        self.assertIn("«redacted %d chars»" % len(value), redacted)

    def test_clean_text_unchanged(self):
        text = "قصة النجار الأمين — الجزء الأول"
        self.assertEqual(memory_store.redact_credentials(text), text)

    def test_add_note_redacts_before_disk(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(td)
            store.add_note("queue", "api_key = abc123XYZ")
            with open(store.topic_path("queue"), encoding="utf-8") as fh:
                on_disk = fh.read()
            self.assertNotIn("abc123XYZ", on_disk)
            self.assertIn("«redacted 9 chars»", on_disk)


class TestExpiry(unittest.TestCase):
    def test_past_until_is_expired(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        self.assertTrue(
            memory_store.is_expired("ملاحظة · until %s" % past))

    def test_future_until_not_expired(self):
        future = (date.today() + timedelta(days=30)).isoformat()
        self.assertFalse(
            memory_store.is_expired("ملاحظة · until %s" % future))

    def test_no_marker_never_expires(self):
        self.assertFalse(memory_store.is_expired("ملاحظة بلا علامة"))

    def test_recall_skips_expired(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(td)
            past = (date.today() - timedelta(days=1)).isoformat()
            store.add_note("topics", "قصة قديمة · until %s" % past)
            store.add_note("topics", "قصة جديدة عن النجار")
            result = store.recall("قصة")
            joined = "\n".join(result["notes"] + result["snippets"])
            self.assertNotIn("قديمة", joined)
            self.assertIn("جديدة", joined)


class TestEntryCap(unittest.TestCase):
    def test_over_1000_chars_rejected(self):
        with self.assertRaises(ValueError):
            memory_store.check_entry("x" * 1001)

    def test_1000_chars_accepted(self):
        self.assertEqual(memory_store.check_entry("x" * 1000), "x" * 1000)

    def test_over_20_lines_rejected(self):
        with self.assertRaises(ValueError):
            memory_store.check_entry("\n".join("س" for _ in range(21)))

    def test_20_lines_accepted(self):
        text = "\n".join("س" for _ in range(20))
        self.assertEqual(memory_store.check_entry(text), text)


class TestArchiveBeforeRewrite(unittest.TestCase):
    def test_rewrite_archives_first(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(td)
            _write(store.memory_path(), "الذاكرة القديمة\n")
            store.rewrite_memory("الذاكرة الجديدة\n")
            with open(store.archive_path(), encoding="utf-8") as fh:
                self.assertIn("الذاكرة القديمة", fh.read())
            with open(store.memory_path(), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), "الذاكرة الجديدة\n")

    def test_rewrite_is_atomic_0600(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(td)
            store.rewrite_memory("ذاكرة\n")
            mode = stat.S_IMODE(os.stat(store.memory_path()).st_mode)
            self.assertEqual(mode, 0o600)


class TestRecallLimits(unittest.TestCase):
    def test_recall_caps_notes_snippets_and_chars(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(td)
            body = "\n\n".join(
                "مقطع %d عن القصة" % i for i in range(30))
            _write(store.memory_path(), body)
            result = store.recall("القصة")
            self.assertLessEqual(len(result["notes"]), 4)
            self.assertLessEqual(len(result["snippets"]), 4)
            self.assertLessEqual(result["chars"], 6000)
            self.assertEqual(
                result["chars"],
                sum(len(t) for t in result["notes"] + result["snippets"]))


class TestIndexAndFiles(unittest.TestCase):
    def test_index_capped_40_topics_2000_chars(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(td)
            for i in range(50):
                store.add_note("topic%02d" % i, "ملاحظة")
            index = store.build_index()
            self.assertLessEqual(len(index.splitlines()), 40)
            self.assertLessEqual(len(index), 2000)

    def test_log_and_thread_files(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(td)
            day = date(2026, 11, 27)
            log = store.add_log_entry("سجل اليوم", day=day)
            self.assertTrue(log.endswith(os.path.join("log", "2026-11-27.md")))
            thread = store.add_thread_note("run-1", "ملاحظة خيط")
            self.assertTrue(thread.endswith(
                os.path.join("threads", "run-1.md")))
            self.assertTrue(os.path.exists(log))
            self.assertTrue(os.path.exists(thread))

    def test_unsafe_topic_name_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            store = MemoryStore(td)
            with self.assertRaises(ValueError):
                store.add_note("///", "ملاحظة")


if __name__ == "__main__":
    unittest.main()
