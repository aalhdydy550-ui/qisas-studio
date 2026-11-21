#!/usr/bin/env python3
"""اختبارات أمر الطابور `queue add` (lib.queue).

تعمل بـ `python3 -m unittest discover -s tests -v`.
كل الاختبارات على ملف طابور مؤقت — لا تُمس ملف الطابور الحقيقي
أبدًا.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import queue as queue_lib


SAMPLE_QUEUE = """# طابور قصص — تجريبي للاختبار فقط

## في الانتظار

1. **قصة قديمة** — بلا ملاحظات
2. **قصة أخرى** — جزآن

## المنشور

1. **النجار الأمين** — نُشر 2026-11-20 09:00
"""


class TestQueueParse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.qpath = os.path.join(self.tmp.name, "queue.md")
        with open(self.qpath, "w", encoding="utf-8") as f:
            f.write(SAMPLE_QUEUE)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_waiting_entries(self):
        with open(self.qpath, encoding="utf-8") as f:
            entries = queue_lib.parse_waiting_entries(f.read())
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["number"], 1)
        self.assertEqual(entries[0]["title"], "قصة قديمة")
        self.assertEqual(entries[1]["number"], 2)
        self.assertEqual(entries[1]["title"], "قصة أخرى")

    def test_parse_dated_entries(self):
        from lib import autoweek
        dated = autoweek.parse_dated_stories(self.qpath)
        self.assertEqual(len(dated), 1)
        self.assertEqual(dated[0]["title"], "النجار الأمين")
        self.assertEqual(dated[0]["date"].strftime("%Y-%m-%d %H:%M"),
                         "2026-11-20 09:00")


class TestQueueAdd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.qpath = os.path.join(self.tmp.name, "queue.md")
        with open(self.qpath, "w", encoding="utf-8") as f:
            f.write(SAMPLE_QUEUE)
        self.stories_dir = os.path.join(self.tmp.name, "queue")

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_appends_and_numbers(self):
        result = queue_lib.add_story(
            self.qpath, "قصة جديدة", "كان يا ما كان…",
            stories_dir=self.stories_dir)
        self.assertEqual(result["number"], 3)
        self.assertEqual(result["title"], "قصة جديدة")
        with open(self.qpath, encoding="utf-8") as f:
            lines = f.read()
        self.assertIn("3. **قصة جديدة**", lines)
        # النص الكامل محفوظ في ملف منفصل تحت مجلد الطابور.
        self.assertTrue(result["text_file"].endswith(".txt"))
        with open(result["text_file"], encoding="utf-8") as f:
            self.assertIn("كان يا ما كان", f.read())

    def test_add_with_parts_and_note(self):
        result = queue_lib.add_story(
            self.qpath, "قصة جزآن", "نص طويل…", parts=2,
            note="تُقسم على جزأين", stories_dir=self.stories_dir)
        self.assertEqual(result["number"], 3)
        with open(self.qpath, encoding="utf-8") as f:
            lines = f.read()
        self.assertIn("3. **قصة جزآن** — يحتاج 2 أجزاء — تُقسم على جزأين",
                      lines)

    def test_add_duplicate_refused(self):
        with self.assertRaises(queue_lib.QueueError):
            queue_lib.add_story(self.qpath, "قصة قديمة", "نص آخر",
                                stories_dir=self.stories_dir)
        with self.assertRaises(queue_lib.QueueError):
            queue_lib.add_story(self.qpath, "قصة  قديمة", "نص آخر",
                                stories_dir=self.stories_dir)

    def test_add_empty_text_refused(self):
        with self.assertRaises(queue_lib.QueueError):
            queue_lib.add_story(self.qpath, "قصة بلا نص", "   ",
                                stories_dir=self.stories_dir)

    def test_add_empty_title_refused(self):
        with self.assertRaises(queue_lib.QueueError):
            queue_lib.add_story(self.qpath, "   ", "نص",
                                stories_dir=self.stories_dir)

    def test_add_empty_queue_file(self):
        empty = os.path.join(self.tmp.name, "empty.md")
        result = queue_lib.add_story(empty, "أول قصة", "نص أول",
                                     stories_dir=self.stories_dir)
        self.assertEqual(result["number"], 1)
        with open(empty, encoding="utf-8") as f:
            self.assertIn("1. **أول قصة**", f.read())

    def test_add_twice_numbers_increment(self):
        queue_lib.add_story(self.qpath, "قصة ثالثة", "نص",
                            stories_dir=self.stories_dir)
        result = queue_lib.add_story(self.qpath, "قصة رابعة", "نص",
                                     stories_dir=self.stories_dir)
        self.assertEqual(result["number"], 4)


if __name__ == "__main__":
    unittest.main()
