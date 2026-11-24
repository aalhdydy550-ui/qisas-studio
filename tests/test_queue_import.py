#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات استيراد قصة طويلة إلى الطابور — على طابور مؤقت فقط."""
import datetime
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import queue_import
from lib.queue import QueueError

# جملة عربية قصيرة (~10 كلمات ≈ 4.6 ثوانٍ سردًا).
S = ("في يوم من الأيام خرج رجل فقير من بيته يبحث عن رزق حلال "
     "لأولاده الجياع.")


def _long_text(n_sentences):
    return "\n".join(S for _ in range(n_sentences))


class TestEstimateAndSplit(unittest.TestCase):
    def test_estimate_seconds(self):
        # 130 كلمة ≈ 60 ثانية؛ الجملة ~15 كلمة ≈ 7 ثوانٍ.
        self.assertAlmostEqual(queue_import.estimate_seconds(S),
                               len(S.split()) * 60 / 130, places=2)

    def test_short_text_is_one_part(self):
        parts = queue_import.split_into_parts(_long_text(3))
        self.assertEqual(len(parts), 1)

    def test_long_text_splits_into_40_to_60s_parts(self):
        # 30 جملة ≈ 210 ثوانٍ → ~4 أجزاء.
        parts = queue_import.split_into_parts(_long_text(30))
        self.assertGreaterEqual(len(parts), 3)
        self.assertLessEqual(len(parts), 5)
        for part in parts[:-1]:
            secs = queue_import.estimate_seconds(part)
            self.assertGreaterEqual(secs, 40)
            self.assertLessEqual(secs, 60)

    def test_empty_text_no_parts(self):
        self.assertEqual(queue_import.split_into_parts("   "), [])
        self.assertEqual(queue_import.split_into_parts(""), [])

    def test_suggested_slots_alternate(self):
        slots = queue_import.suggested_slots(
            4, datetime.date(2026, 11, 23))
        self.assertEqual(slots, ["2026-11-23 09:00",
                                 "2026-11-23 19:00",
                                 "2026-11-24 09:00",
                                 "2026-11-24 19:00"])


class TestImportStory(unittest.TestCase):
    def _setup(self, td, n=30):
        queue_path = os.path.join(td, "story-queue.md")
        text_path = os.path.join(td, "story.txt")
        Path(text_path).write_text(_long_text(n), encoding="utf-8")
        stories_dir = os.path.join(td, "queue")
        return queue_path, text_path, stories_dir

    def test_import_adds_numbered_parts_to_temp_queue(self):
        with tempfile.TemporaryDirectory() as td:
            queue_path, text_path, stories_dir = self._setup(td)
            result = queue_import.import_story(
                queue_path, text_path, "قصة تجريبية",
                stories_dir=stories_dir,
                start_date=datetime.date(2026, 11, 23))
            self.assertEqual(result["title"], "قصة تجريبية")
            self.assertGreaterEqual(len(result["parts"]), 3)
            for i, part in enumerate(result["parts"], 1):
                self.assertEqual(part["part"], i)
                self.assertEqual(part["number"], i)
                self.assertIn("2026-11-2", part["suggested_time"])
                self.assertTrue(part["text_file"].endswith(".txt"))
            content = Path(queue_path).read_text(encoding="utf-8")
            self.assertIn("**قصة تجريبية — الجزء 1**", content)
            self.assertIn("**قصة تجريبية — الجزء 2**", content)

    def test_import_single_part_keeps_plain_title(self):
        with tempfile.TemporaryDirectory() as td:
            queue_path, text_path, stories_dir = self._setup(td, n=3)
            result = queue_import.import_story(
                queue_path, text_path, "قصة قصيرة",
                stories_dir=stories_dir)
            self.assertEqual(len(result["parts"]), 1)
            content = Path(queue_path).read_text(encoding="utf-8")
            self.assertIn("**قصة قصيرة**", content)
            self.assertNotIn("الجزء 1", content)

    def test_import_missing_file_and_empty_text(self):
        with tempfile.TemporaryDirectory() as td:
            queue_path = os.path.join(td, "story-queue.md")
            with self.assertRaises(ValueError):
                queue_import.import_story(queue_path,
                                          os.path.join(td, "nope.txt"),
                                          "عنوان")
            empty = os.path.join(td, "empty.txt")
            Path(empty).write_text("   \n", encoding="utf-8")
            with self.assertRaises(ValueError):
                queue_import.import_story(queue_path, empty, "عنوان")

    def test_import_duplicate_title_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            queue_path, text_path, stories_dir = self._setup(td, n=3)
            queue_import.import_story(queue_path, text_path,
                                      "قصة مكررة",
                                      stories_dir=stories_dir)
            with self.assertRaises(QueueError):
                queue_import.import_story(queue_path, text_path,
                                          "قصة مكررة",
                                          stories_dir=stories_dir)


if __name__ == "__main__":
    unittest.main()
