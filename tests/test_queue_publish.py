#!/usr/bin/env python3
"""اختبارات قائمة انتظار النشر الموحّدة — جولة v0.1.39 (أ2-8).

حالة نشر لكل منصة (facebook/youtube/tiktok/instagram) في
ملف جانبي JSON بجانب ملف الطابور — صيغة أسطر الطابور لا
تُمسّ، والعنصر القديم بلا حالات يُقرأ pending لكل المنصات.
كل الاختبارات على ملفات مؤقتة — لا تُمس ملف الطابور الحقيقي.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import queue as queue_lib
from lib.queue import QueueError

SAMPLE_QUEUE = """# طابور قصص — تجريبي للاختبار فقط

## في الانتظار

1. **قصة قديمة** — بلا ملاحظات
2. **قصة أخرى** — جزآن

## المنشور

1. **النجار الأمين** — نُشر 2026-11-20 09:00
"""


class TestLegacyEntriesDefaultPending(unittest.TestCase):
    def test_old_entry_reads_pending_everywhere(self):
        entries = queue_lib.parse_waiting_entries(SAMPLE_QUEUE)
        self.assertEqual(len(entries), 2)
        for entry in entries:
            self.assertEqual(entry["publish"],
                             {"facebook": "pending",
                              "youtube": "pending",
                              "tiktok": "pending",
                              "instagram": "pending"})

    def test_default_publish_statuses(self):
        self.assertEqual(queue_lib.default_publish_statuses(),
                         {"facebook": "pending",
                          "youtube": "pending",
                          "tiktok": "pending",
                          "instagram": "pending"})

    def test_normalize_partial_fills_pending(self):
        self.assertEqual(
            queue_lib.normalize_publish_statuses(
                {"facebook": "published"}),
            {"facebook": "published",
             "youtube": "pending",
             "tiktok": "pending",
             "instagram": "pending"})
        self.assertEqual(queue_lib.normalize_publish_statuses(None),
                         queue_lib.default_publish_statuses())
        self.assertEqual(queue_lib.normalize_publish_statuses({}),
                         queue_lib.default_publish_statuses())

    def test_normalize_unknown_platform_or_status_rejected(self):
        with self.assertRaises(QueueError):
            queue_lib.normalize_publish_statuses(
                {"myspace": "published"})
        with self.assertRaises(QueueError):
            queue_lib.normalize_publish_statuses(
                {"facebook": "uploaded"})
        with self.assertRaises(QueueError):
            queue_lib.normalize_publish_statuses("published")


class TestInMemoryStatusUpdates(unittest.TestCase):
    def test_update_and_retrieve(self):
        statuses = {}
        entry = queue_lib.update_platform_status(
            statuses, 1, "facebook", "published")
        self.assertEqual(entry["facebook"], "published")
        self.assertEqual(entry["youtube"], "pending")
        self.assertEqual(
            queue_lib.get_platform_status(statuses, 1, "facebook"),
            "published")
        self.assertEqual(
            queue_lib.get_platform_status(statuses, 1, "youtube"),
            "pending")
        # عنصر بلا أي سجل يُقرأ pending.
        self.assertEqual(
            queue_lib.get_platform_status(statuses, 99, "tiktok"),
            "pending")

    def test_update_second_platform_keeps_first(self):
        statuses = {}
        queue_lib.update_platform_status(statuses, 2, "youtube",
                                         "failed")
        entry = queue_lib.update_platform_status(statuses, 2, "tiktok",
                                                 "skipped")
        self.assertEqual(entry["youtube"], "failed")
        self.assertEqual(entry["tiktok"], "skipped")
        self.assertEqual(entry["facebook"], "pending")

    def test_update_invalid_platform_or_status_rejected(self):
        with self.assertRaises(QueueError):
            queue_lib.update_platform_status({}, 1, "myspace",
                                             "published")
        with self.assertRaises(QueueError):
            queue_lib.update_platform_status({}, 1, "facebook",
                                             "uploaded")
        with self.assertRaises(QueueError):
            queue_lib.get_platform_status({}, 1, "myspace")
        with self.assertRaises(QueueError):
            queue_lib.update_platform_status({}, "x", "facebook",
                                             "published")


class TestPendingAndSummary(unittest.TestCase):
    def _entries(self):
        statuses = {
            1: {"facebook": "published", "youtube": "pending",
                "tiktok": "failed", "instagram": "pending"},
            2: {"facebook": "pending", "youtube": "published",
                "tiktok": "pending", "instagram": "skipped"},
        }
        return queue_lib.parse_waiting_entries(SAMPLE_QUEUE, statuses)

    def test_pending_for_platform(self):
        entries = self._entries()
        fb = queue_lib.pending_for_platform(entries, "facebook")
        self.assertEqual([e["number"] for e in fb], [2])
        self.assertEqual(fb[0]["title"], "قصة أخرى")
        yt = queue_lib.pending_for_platform(entries, "youtube")
        self.assertEqual([e["number"] for e in yt], [1])
        ig = queue_lib.pending_for_platform(entries, "instagram")
        self.assertEqual([e["number"] for e in ig], [1])

    def test_pending_for_platform_invalid_rejected(self):
        with self.assertRaises(QueueError):
            queue_lib.pending_for_platform(self._entries(), "myspace")

    def test_publish_summary_counts(self):
        summary = queue_lib.publish_summary(self._entries())
        self.assertEqual(summary["entries"], 2)
        self.assertEqual(summary["facebook"],
                         {"pending": 1, "published": 1, "failed": 0,
                          "skipped": 0, "total": 2})
        self.assertEqual(summary["youtube"],
                         {"pending": 1, "published": 1, "failed": 0,
                          "skipped": 0, "total": 2})
        self.assertEqual(summary["tiktok"],
                         {"pending": 1, "published": 0, "failed": 1,
                          "skipped": 0, "total": 2})
        self.assertEqual(summary["instagram"],
                         {"pending": 1, "published": 0, "failed": 0,
                          "skipped": 1, "total": 2})

    def test_publish_summary_empty(self):
        summary = queue_lib.publish_summary([])
        self.assertEqual(summary["entries"], 0)
        for platform in queue_lib.PUBLISH_PLATFORMS:
            self.assertEqual(summary[platform]["total"], 0)
            self.assertEqual(summary[platform]["pending"], 0)

    def test_summary_legacy_entries_all_pending(self):
        entries = queue_lib.parse_waiting_entries(SAMPLE_QUEUE)
        summary = queue_lib.publish_summary(entries)
        for platform in queue_lib.PUBLISH_PLATFORMS:
            self.assertEqual(summary[platform]["pending"], 2)
            self.assertEqual(summary[platform]["published"], 0)


class TestSidecarPersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.qpath = os.path.join(self.tmp.name, "queue.md")
        with open(self.qpath, "w", encoding="utf-8") as f:
            f.write(SAMPLE_QUEUE)

    def tearDown(self):
        self.tmp.cleanup()

    def test_set_and_load_roundtrip(self):
        entry = queue_lib.set_platform_status(self.qpath, 1,
                                              "facebook", "published")
        self.assertEqual(entry["facebook"], "published")
        self.assertEqual(entry["youtube"], "pending")
        loaded = queue_lib.load_publish_statuses(self.qpath)
        self.assertEqual(loaded[1]["facebook"], "published")
        self.assertEqual(loaded[1]["youtube"], "pending")
        # الملف الجانبي JSON صالح وبجانب ملف الطابور.
        sidecar = queue_lib.publish_statuses_path(self.qpath)
        self.assertTrue(os.path.isfile(sidecar))
        with open(sidecar, encoding="utf-8") as f:
            raw = json.load(f)
        self.assertEqual(raw["1"]["facebook"], "published")

    def test_queue_file_untouched_by_status_updates(self):
        with open(self.qpath, encoding="utf-8") as f:
            before = f.read()
        queue_lib.set_platform_status(self.qpath, 1, "youtube",
                                      "failed")
        with open(self.qpath, encoding="utf-8") as f:
            after = f.read()
        self.assertEqual(before, after)

    def test_entries_with_publish_reads_sidecar(self):
        queue_lib.set_platform_status(self.qpath, 2, "tiktok",
                                      "skipped")
        with open(self.qpath, encoding="utf-8") as f:
            entries = queue_lib.entries_with_publish(
                f.read(), self.qpath)
        self.assertEqual(entries[1]["publish"]["tiktok"], "skipped")
        self.assertEqual(entries[0]["publish"]["tiktok"], "pending")

    def test_missing_sidecar_means_all_pending(self):
        self.assertEqual(queue_lib.load_publish_statuses(self.qpath),
                         {})
        with open(self.qpath, encoding="utf-8") as f:
            entries = queue_lib.entries_with_publish(
                f.read(), self.qpath)
        for entry in entries:
            self.assertEqual(entry["publish"],
                             queue_lib.default_publish_statuses())

    def test_corrupt_sidecar_reads_as_pending(self):
        sidecar = queue_lib.publish_statuses_path(self.qpath)
        with open(sidecar, "w", encoding="utf-8") as f:
            f.write("{ليس json صالحًا")
        self.assertEqual(queue_lib.load_publish_statuses(self.qpath),
                         {})
        with open(sidecar, "w", encoding="utf-8") as f:
            json.dump({"1": {"facebook": "uploaded"},
                       "2": {"tiktok": "skipped"}},
                      f, ensure_ascii=False)
        loaded = queue_lib.load_publish_statuses(self.qpath)
        # المدخل التالف يُتخطى، والسليم يُقرأ.
        self.assertNotIn(1, loaded)
        self.assertEqual(loaded[2]["tiktok"], "skipped")

    def test_set_invalid_rejected_and_writes_nothing(self):
        with self.assertRaises(QueueError):
            queue_lib.set_platform_status(self.qpath, 1, "facebook",
                                          "uploaded")
        self.assertFalse(os.path.isfile(
            queue_lib.publish_statuses_path(self.qpath)))

    def test_save_load_roundtrip_with_string_keys(self):
        queue_lib.save_publish_statuses(
            self.qpath, {"1": {"instagram": "published"}})
        loaded = queue_lib.load_publish_statuses(self.qpath)
        self.assertEqual(loaded[1]["instagram"], "published")


if __name__ == "__main__":
    unittest.main()
