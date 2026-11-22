#!/usr/bin/env python3
"""اختبارات تحقق بنية الطابور — جولة v0.1.37 (مقترح tinker رقم 8).

تختبر القواعد على نصوص اصطناعية، وتتحقق أن الطابور
الحقيقي سليم (قاعدة ذهبية: أي تعديل في القواعد يجب أن
يبقي الطابور الحقيقي أخضر).
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import queue_check

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL_QUEUE = os.path.expanduser(
    "~/workspace/goals/goal/hidden_files/story-queue-2026-11-20.md")

CLEAN = """## المنشور
- **قصة منشورة** — نُشر 2026-11-20 09:00 EET

## المجدول
- **قصة ألف** — مجدول 2026-11-22 19:00 EET (Unix 1795366800)

## المخطط له (ليس مجدولاً بعد)
- **قصة باء** — الموعد الحر التالي: الأحد 2026-11-23 19:00 EET (Unix 1795453200)

## في الانتظار (بالترتيب)
1. **قصة جيم** — ملاحظة
2. **قصة دال**
"""


class TestQueueCheckRules(unittest.TestCase):
    def test_clean_queue_passes(self):
        self.assertEqual(queue_check.validate_queue_text(CLEAN), [])

    def test_malformed_waiting_line(self):
        text = CLEAN + "3. قصة بلا تنسيق\n"
        issues = queue_check.validate_queue_text(text)
        self.assertTrue(any("مشوّه" in i for i in issues), issues)

    def test_duplicate_waiting_number(self):
        text = CLEAN.replace("2. **قصة دال**",
                             "2. **قصة دال**\n1. **قصة هاء**")
        issues = queue_check.validate_queue_text(text)
        self.assertTrue(any("رقم انتظار مكرر" in i for i in issues),
                        issues)

    def test_duplicate_waiting_title(self):
        text = CLEAN.replace("2. **قصة دال**",
                             "2. **قصة جيم** — نسخة ثانية")
        issues = queue_check.validate_queue_text(text)
        self.assertTrue(any("عنوان مكرر" in i for i in issues), issues)

    def test_duplicate_slot_unix(self):
        text = CLEAN.replace("Unix 1795453200", "Unix 1795366800")
        issues = queue_check.validate_queue_text(text)
        self.assertTrue(any("موعد مكرر" in i for i in issues), issues)

    def test_missing_video_in_slot(self):
        text = CLEAN.replace(
            "- **قصة ألف** — مجدول 2026-11-22 19:00 EET (Unix 1795366800)",
            "- **قصة ألف** — مجدول 2026-11-22 19:00 EET (Unix 1795366800) "
            "بالفيديو ~/workspace/videos/no-such-video-xyz.mp4")
        issues = queue_check.validate_queue_text(text)
        self.assertTrue(any("غير موجود" in i for i in issues), issues)

    def test_same_unix_in_update_note_is_not_a_slot(self):
        # تكرار Unix في سرد التحديثات (نص حر) ليس خانتين —
        # القاعدة تفحص سطور الخانات فقط.
        text = CLEAN + ("\n## تحديث\n- نجحت الجدولة للموعد "
                        "(Unix 1795366800).\n")
        self.assertEqual(queue_check.validate_queue_text(text), [])

    def test_validate_file_missing(self):
        ok, issues = queue_check.validate_queue_file(
            "/tmp/no-such-queue-xyz.md")
        self.assertFalse(ok)
        self.assertTrue(issues)

    def test_validate_file_roundtrip(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md",
                                         encoding="utf-8",
                                         delete=False) as fh:
            fh.write(CLEAN)
            path = fh.name
        try:
            ok, issues = queue_check.validate_queue_file(path)
            self.assertTrue(ok, issues)
        finally:
            os.unlink(path)


class TestRealQueue(unittest.TestCase):
    def test_real_queue_is_clean(self):
        if not os.path.isfile(REAL_QUEUE):
            self.skipTest("ملف الطابور الحقيقي غائب في هذه البيئة")
        ok, issues = queue_check.validate_queue_file(REAL_QUEUE)
        self.assertTrue(ok, "مشكلات في الطابور الحقيقي: %s" % issues)


if __name__ == "__main__":
    unittest.main()
