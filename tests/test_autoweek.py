#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات اختيار قصص الأسبوع `long-video --auto-week` (lib.autoweek).

تعمل بـ `python3 -m unittest discover -s tests -v`.
كل الاختبارات على ملفات طابور مؤقتة — بلا شبكة وبلا ريندر.
"""
import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import autoweek

KNOWN = {4: ("anza", "anza-part1")}


def write_queue(path, body):
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)


class TestPickWeekStories(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.qpath = os.path.join(self.tmp.name, "queue.md")
        # مجلدات فصول مؤقتة لكل قصة في الاختبارات، حتى تُحل مصادرها.
        self.runs = os.path.join(self.tmp.name, "runs")
        for slug in ("najjar", "hizaa", "manqasha"):
            os.makedirs(os.path.join(self.runs, "x", "chapters", slug))
        self.cfg = {"paths": {
            "runs_dir": self.runs,
            "projects_dir": os.path.join(self.tmp.name, "projects")},
            "openmontage": {
                "projects_dir": os.path.join(self.tmp.name, "projects")}}

    def tearDown(self):
        self.tmp.cleanup()

    def _pick(self, body, since=None, today=None):
        write_queue(self.qpath, body)
        return autoweek.pick_week_stories(
            self.qpath, self.cfg, KNOWN, since=since, today=today)

    def test_picks_dated_stories_in_window(self):
        body = """## المنشور

1. **النجار الأمين** — نُشر 2026-11-20 09:00
2. **حذاء أبي** — نُشر 2026-11-21 19:00

## المجدول

- **منقشة الرغيف** — مجدول 2026-11-22 09:00
"""
        usable, skipped = self._pick(
            body, today=datetime.date(2026, 11, 22))
        self.assertEqual([u["title"] for u in usable],
                         ["النجار الأمين", "حذاء أبي", "منقشة الرغيف"])
        self.assertEqual(usable[0]["type"], "chapter-dir")

    def test_old_and_future_excluded(self):
        body = """## المنشور

1. **قصة قديمة جدًا** — نُشر 2026-11-10 09:00
1. **النجار الأمين** — نُشر 2026-11-20 09:00

## المجدول

- **قصة المستقبل** — مجدول 2026-11-30 09:00
"""
        # قصة واحدة صالحة فقط → خطأ يسمّي الجاهزة.
        with self.assertRaises(autoweek.AutoWeekError) as ctx:
            self._pick(body, today=datetime.date(2026, 11, 22))
        self.assertIn("النجار الأمين", str(ctx.exception))
        self.assertNotIn("قصة قديمة", str(ctx.exception))
        self.assertNotIn("قصة المستقبل", str(ctx.exception))

    def test_waiting_entries_not_picked(self):
        body = """## في الانتظار

1. **قصة لم تُنشر بعد** — تنتظر دورها

## المنشور

1. **النجار الأمين** — نُشر 2026-11-20 09:00
2. **حذاء أبي** — نُشر 2026-11-21 19:00
"""
        usable, skipped = self._pick(
            body, today=datetime.date(2026, 11, 22))
        self.assertEqual([u["title"] for u in usable],
                         ["النجار الأمين", "حذاء أبي"])

    def test_known_project_resolved(self):
        body = """## المنشور

1. **النجار الأمين** — نُشر 2026-11-20 09:00
2. **العنزة المباركة** — نُشر 2026-11-21 19:00
"""
        usable, skipped = self._pick(
            body, today=datetime.date(2026, 11, 22))
        self.assertEqual(usable[1]["type"], "story")
        self.assertEqual(usable[1]["source"], "anza")

    def test_fewer_than_two_raises(self):
        body = """## المنشور

1. **النجار الأمين** — نُشر 2026-11-20 09:00
"""
        with self.assertRaises(autoweek.AutoWeekError) as ctx:
            self._pick(body, today=datetime.date(2026, 11, 22))
        self.assertIn("النجار الأمين", str(ctx.exception))

    def test_empty_queue_raises(self):
        with self.assertRaises(autoweek.AutoWeekError):
            self._pick("", today=datetime.date(2026, 11, 22))

    def test_missing_queue_file_raises(self):
        with self.assertRaises(autoweek.AutoWeekError):
            autoweek.pick_week_stories(
                os.path.join(self.tmp.name, "nope.md"), self.cfg,
                KNOWN, today=datetime.date(2026, 11, 22))

    def test_duplicate_titles_deduplicated(self):
        body = """## المنشور

1. **النجار الأمين** — نُشر 2026-11-20 09:00
2. **حذاء أبي** — نُشر 2026-11-21 19:00

## المجدول

- **النجار الأمين** — مجدول 2026-11-21 09:00
"""
        usable, skipped = self._pick(
            body, today=datetime.date(2026, 11, 22))
        self.assertEqual([u["title"] for u in usable],
                         ["النجار الأمين", "حذاء أبي"])
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["title"], "النجار الأمين")


class TestResolveChapterSource(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runs = os.path.join(self.tmp.name, "runs")
        os.makedirs(os.path.join(self.runs, "x", "chapters", "hamati"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_known_project(self):
        cfg = {"paths": {"projects_dir": os.path.join(self.tmp.name,
                                                      "projects")},
               "openmontage": {"projects_dir": os.path.join(
                   self.tmp.name, "projects")}}
        got = autoweek.resolve_chapter_source(cfg, "العنزة المباركة", KNOWN)
        self.assertEqual(got, ("story", "anza"))

    def test_chapter_dir(self):
        cfg = {"paths": {"projects_dir": os.path.join(self.tmp.name,
                                                      "projects"),
                         "runs_dir": self.runs},
               "openmontage": {"projects_dir": os.path.join(
                   self.tmp.name, "projects")}}
        got = autoweek.resolve_chapter_source(cfg, "حماتي", KNOWN)
        self.assertEqual(got[0], "chapter-dir")
        self.assertTrue(got[1].endswith("chapters/hamati"))

    def test_unknown_story(self):
        cfg = {"paths": {"projects_dir": os.path.join(self.tmp.name,
                                                      "projects"),
                         "runs_dir": self.runs},
               "openmontage": {"projects_dir": os.path.join(
                   self.tmp.name, "projects")}}
        kind, reason = autoweek.resolve_chapter_source(
            cfg, "قصة لا مصدر لها", KNOWN)
        self.assertIsNone(kind)
        self.assertTrue(reason)


if __name__ == "__main__":
    unittest.main()
