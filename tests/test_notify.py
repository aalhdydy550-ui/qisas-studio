#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات انضباط الإشعارات — جولة v0.1.63 (بند 27، عقد ع5).

كلها على مجلدات مؤقتة ومسلِّمات وهمية؛ بلا شبكة.
"""
import os
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import notify


def _deliver_counter():
    """مسلِّم وهمي بعدّاد: يسجّل كل تسليم فعلي."""
    calls = []

    def deliver(key, message, channel):
        calls.append((key, message, channel))
        return True

    return deliver, calls


class TestNotifyOnce(unittest.TestCase):
    def test_first_send_returns_true_second_returns_false(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            deliver, calls = _deliver_counter()
            self.assertTrue(notify.notify_once(
                "cap:daily", "بلغت الحد اليومي", runs_dir=runs_dir,
                deliver=deliver))
            self.assertFalse(notify.notify_once(
                "cap:daily", "بلغت الحد اليومي", runs_dir=runs_dir,
                deliver=deliver))
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], "cap:daily")
            self.assertEqual(calls[0][2], "log")

    def test_different_keys_each_notify_once(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            deliver, calls = _deliver_counter()
            self.assertTrue(notify.notify_once(
                "key-1", "أول", runs_dir=runs_dir, deliver=deliver))
            self.assertTrue(notify.notify_once(
                "key-2", "ثانٍ", runs_dir=runs_dir, deliver=deliver))
            self.assertEqual(len(calls), 2)

    def test_no_duplicate_after_restart(self):
        # المخزن على القرص: «إعادة تشغيل» = استدعاء جديد
        # لنفس الملف — المفتاح ما زال مكررًا.
        with tempfile.TemporaryDirectory() as runs_dir:
            deliver, calls = _deliver_counter()
            notify.notify_once("series-1", "فشل", runs_dir=runs_dir,
                               deliver=deliver)
            self.assertFalse(notify.notify_once(
                "series-1", "فشل مجددًا", runs_dir=runs_dir,
                deliver=deliver))
            self.assertEqual(len(calls), 1)

    def test_failure_series_notifies_once(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            deliver, calls = _deliver_counter()
            key = "routine:morning:failure-series"
            for _ in range(5):
                notify.notify_once(key, "فشلت الجولة",
                                   runs_dir=runs_dir, deliver=deliver)
            self.assertEqual(len(calls), 1)

    def test_failed_delivery_is_not_recorded(self):
        def failing_deliver(key, message, channel):
            return False

        with tempfile.TemporaryDirectory() as runs_dir:
            self.assertFalse(notify.notify_once(
                "k", "رسالة", runs_dir=runs_dir,
                deliver=failing_deliver))
            self.assertFalse(notify.was_notified("k", runs_dir))
            deliver, calls = _deliver_counter()
            self.assertTrue(notify.notify_once(
                "k", "رسالة", runs_dir=runs_dir, deliver=deliver))
            self.assertEqual(len(calls), 1)

    def test_default_delivery_logs_without_deliver(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            self.assertTrue(notify.notify_once(
                "k", "رسالة", runs_dir=runs_dir))
            self.assertTrue(notify.was_notified("k", runs_dir))

    def test_empty_key_or_message_raises(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            with self.assertRaises(notify.NotifyError):
                notify.notify_once("", "رسالة", runs_dir=runs_dir)
            with self.assertRaises(notify.NotifyError):
                notify.notify_once("k", "  ", runs_dir=runs_dir)

    def test_dedup_file_is_0600(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            notify.notify_once("k", "رسالة", runs_dir=runs_dir)
            mode = stat.S_IMODE(os.stat(
                notify.dedup_path(runs_dir)).st_mode)
            self.assertEqual(mode, 0o600)


class TestReset(unittest.TestCase):
    def test_reset_allows_next_series_notification(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            deliver, calls = _deliver_counter()
            notify.notify_once("k", "أول", runs_dir=runs_dir,
                               deliver=deliver)
            self.assertFalse(notify.notify_once(
                "k", "مكرر", runs_dir=runs_dir, deliver=deliver))
            cleared = notify.reset_notify("k", runs_dir)
            self.assertEqual(cleared, 1)
            self.assertFalse(notify.was_notified("k", runs_dir))
            self.assertTrue(notify.notify_once(
                "k", "سلسلة جديدة", runs_dir=runs_dir,
                deliver=deliver))
            self.assertEqual(len(calls), 2)

    def test_reset_sends_no_notification(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            deliver, calls = _deliver_counter()
            notify.notify_once("k", "أول", runs_dir=runs_dir,
                               deliver=deliver)
            notify.reset_notify("k", runs_dir)
            # إعادة الضبط نفسها لم ترسل شيئًا.
            self.assertEqual(len(calls), 1)

    def test_reset_all_clears_everything(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            deliver, calls = _deliver_counter()
            notify.notify_once("a", "1", runs_dir=runs_dir,
                               deliver=deliver)
            notify.notify_once("b", "2", runs_dir=runs_dir,
                               deliver=deliver)
            self.assertEqual(notify.reset_notify(None, runs_dir), 2)
            self.assertEqual(notify.list_notified(runs_dir), {})

    def test_reset_unknown_key_clears_zero(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            self.assertEqual(
                notify.reset_notify("ghost", runs_dir), 0)

    def test_was_notified_and_list(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            self.assertFalse(notify.was_notified("k", runs_dir))
            notify.notify_once("k", "رسالة", channel="log",
                               runs_dir=runs_dir)
            self.assertTrue(notify.was_notified("k", runs_dir))
            listed = notify.list_notified(runs_dir)
            self.assertIn("k", listed)
            self.assertEqual(listed["k"]["channel"], "log")
            self.assertIn("ts", listed["k"])


if __name__ == "__main__":
    unittest.main()
