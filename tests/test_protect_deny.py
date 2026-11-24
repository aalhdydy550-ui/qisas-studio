#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات بوابة المخاطر الكارثية المطلقة (جولة v0.1.41 —
بند 4 من استخراج AlphaCLI، REPORT-AR.md §4.1).

- طبقة Deny دائمة بلا مبرر يفتحها لمسارات التدمير الكارثية
  (rm -rf ~ و/etc وعقد الأجهزة)؛ وAllow لما عداها.
- قائمة رفض مطلقة للمسارات المحمية (الطابور الحقيقي،
  orders.jsonl، النسخ الاحتياطية) لا يتجاوزها أي أمر.
- كل الاختبارات على بيانات مؤقتة في /tmp ومسارات نظام
  تُفحص بالحكم فقط (لا حذف حقيقي لأي مسار نظام)؛ والطابور
  الحقيقي وorders.jsonl يُفحصان بـdeny_catastrophic فقط
  (لا حذف ولا لمس).
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import protect

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fake_studio():
    """شجرة استوديو مؤقتة بهيكل المسارات المحمية."""
    td = tempfile.mkdtemp()
    for sub in ("queue", "backups", "client-orders", "runs"):
        os.makedirs(os.path.join(td, sub))
    with open(os.path.join(td, "client-orders", "orders.jsonl"),
              "w", encoding="utf-8") as fh:
        fh.write("{}\n")
    with open(os.path.join(td, "client-orders", "orders.jsonl.bad"),
              "w", encoding="utf-8") as fh:
        fh.write("bad\n")
    with open(os.path.join(td, "runs", "jobs.jsonl"),
              "w", encoding="utf-8") as fh:
        fh.write("{}\n")
    with open(os.path.join(td, "backups", "backup-x.zip"),
              "w", encoding="utf-8") as fh:
        fh.write("zip\n")
    return td


class TestDenyCatastrophicSystem(unittest.TestCase):
    def test_home_dir_denied(self):
        self.assertTrue(protect.deny_catastrophic("~"))
        self.assertTrue(protect.deny_catastrophic(
            os.path.expanduser("~")))

    def test_etc_denied(self):
        self.assertTrue(protect.deny_catastrophic("/etc"))
        self.assertTrue(protect.deny_catastrophic("/etc/passwd"))
        self.assertTrue(protect.deny_catastrophic("/etc/ssh/sshd_config"))

    def test_root_denied(self):
        self.assertTrue(protect.deny_catastrophic("/"))

    def test_device_nodes_denied(self):
        self.assertTrue(protect.deny_catastrophic("/dev"))
        self.assertTrue(protect.deny_catastrophic("/dev/null"))
        self.assertTrue(protect.deny_catastrophic("/dev/sda"))

    def test_ssh_dir_denied(self):
        self.assertTrue(protect.deny_catastrophic("~/.ssh"))
        self.assertTrue(protect.deny_catastrophic("~/.ssh/id_ed25519"))

    def test_other_system_roots_denied(self):
        for path in ("/bin", "/bin/sh", "/sbin", "/usr", "/usr/bin",
                     "/boot", "/proc", "/proc/self", "/sys"):
            self.assertTrue(protect.deny_catastrophic(path), path)

    def test_empty_or_missing_path_denied(self):
        self.assertTrue(protect.deny_catastrophic(""))
        self.assertTrue(protect.deny_catastrophic("   "))
        self.assertTrue(protect.deny_catastrophic(None))
        self.assertTrue(protect.deny_catastrophic(123))

    def test_symlink_to_protected_target_denied(self):
        """رابط رمزي يشير إلى /etc يُرفض (الحكم بعد الـresolve)."""
        with tempfile.TemporaryDirectory() as td:
            link = os.path.join(td, "evil-link")
            os.symlink("/etc", link)
            self.assertTrue(protect.deny_catastrophic(link))


class TestDenyProtectedStudioPaths(unittest.TestCase):
    def test_real_queue_file_denied(self):
        """رفض حذف الطابور الحقيقي (المسار الافتراضي)."""
        self.assertTrue(protect.deny_catastrophic(
            protect.DEFAULT_PROTECTED_QUEUE))

    def test_orders_jsonl_denied(self):
        td = _fake_studio()
        self.assertTrue(protect.deny_catastrophic(
            os.path.join(td, "client-orders", "orders.jsonl"),
            studio_dir=td))
        self.assertTrue(protect.deny_catastrophic(
            os.path.join(td, "client-orders", "orders.jsonl.bad"),
            studio_dir=td))

    def test_backups_denied(self):
        td = _fake_studio()
        self.assertTrue(protect.deny_catastrophic(
            os.path.join(td, "backups"), studio_dir=td))
        self.assertTrue(protect.deny_catastrophic(
            os.path.join(td, "backups", "backup-x.zip"),
            studio_dir=td))

    def test_queue_dir_denied(self):
        td = _fake_studio()
        self.assertTrue(protect.deny_catastrophic(
            os.path.join(td, "queue"), studio_dir=td))
        self.assertTrue(protect.deny_catastrophic(
            os.path.join(td, "queue", "anything.md"), studio_dir=td))

    def test_job_registry_denied(self):
        td = _fake_studio()
        self.assertTrue(protect.deny_catastrophic(
            os.path.join(td, "runs", "jobs.jsonl"), studio_dir=td))

    def test_studio_root_itself_denied(self):
        td = _fake_studio()
        self.assertTrue(protect.deny_catastrophic(td, studio_dir=td))

    def test_extra_protected_paths_denied(self):
        with tempfile.TemporaryDirectory() as td:
            keep = os.path.join(td, "keep.txt")
            with open(keep, "w") as fh:
                fh.write("keep\n")
            self.assertTrue(protect.deny_catastrophic(
                keep, extra_protected=[keep]))

    def test_real_studio_protected_paths_denied(self):
        """على الشجرة الحقيقية: الطابور الافتراضي والنسخ
        الاحتياطية وorders.jsonl — حكم فقط، بلا حذف."""
        self.assertTrue(protect.deny_catastrophic(
            protect.DEFAULT_PROTECTED_QUEUE,
            studio_dir=STUDIO_ROOT))
        self.assertTrue(protect.deny_catastrophic(
            os.path.join(STUDIO_ROOT, "backups"),
            studio_dir=STUDIO_ROOT))
        self.assertTrue(protect.deny_catastrophic(
            os.path.join(STUDIO_ROOT, "client-orders",
                         "orders.jsonl"),
            studio_dir=STUDIO_ROOT))


class TestAllow(unittest.TestCase):
    def test_temp_file_allowed(self):
        """سماح بحذف ملف مؤقت في /tmp."""
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "temp.txt")
            with open(path, "w") as fh:
                fh.write("temp\n")
            self.assertFalse(protect.deny_catastrophic(path))

    def test_temp_file_under_home_allowed(self):
        """ملف عادي مباشرة تحت ~ (لا داخل .ssh) مسموح."""
        home = os.path.expanduser("~")
        self.assertFalse(protect.deny_catastrophic(
            os.path.join(home, "some-temp-file.txt")))

    def test_unprotected_studio_file_allowed(self):
        td = _fake_studio()
        self.assertFalse(protect.deny_catastrophic(
            os.path.join(td, "runs", "run-log.json"),
            studio_dir=td))


class TestSafeDelete(unittest.TestCase):
    def test_safe_delete_removes_temp_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "temp.txt")
            with open(path, "w") as fh:
                fh.write("temp\n")
            self.assertTrue(protect.safe_delete(path))
            self.assertFalse(os.path.exists(path))

    def test_safe_delete_refuses_queue(self):
        """رفض حذف الطابور: الاستثناء وسلامة الملف."""
        td = _fake_studio()
        queue_file = os.path.join(td, "queue", "q.md")
        with open(queue_file, "w") as fh:
            fh.write("queue\n")
        with self.assertRaises(protect.ProtectDeniedError):
            protect.safe_delete(queue_file, studio_dir=td)
        self.assertTrue(os.path.isfile(queue_file))

    def test_safe_delete_refuses_system_path(self):
        with self.assertRaises(protect.ProtectDeniedError):
            protect.safe_delete("/etc/passwd")

    def test_safe_delete_missing_file_raises(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                protect.safe_delete(os.path.join(td, "nope.txt"))

    def test_safe_delete_refuses_directory(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(IsADirectoryError):
                protect.safe_delete(td)

    def test_safe_rmtree_removes_temp_dir(self):
        with tempfile.TemporaryDirectory() as parent:
            target = os.path.join(parent, "work")
            os.makedirs(target)
            with open(os.path.join(target, "f.txt"), "w") as fh:
                fh.write("x\n")
            self.assertTrue(protect.safe_rmtree(target))
            self.assertFalse(os.path.exists(target))

    def test_safe_rmtree_refuses_backups(self):
        td = _fake_studio()
        with self.assertRaises(protect.ProtectDeniedError):
            protect.safe_rmtree(os.path.join(td, "backups"),
                                studio_dir=td)
        self.assertTrue(os.path.isdir(os.path.join(td, "backups")))

    def test_safe_rmtree_refuses_home(self):
        with self.assertRaises(protect.ProtectDeniedError):
            protect.safe_rmtree(os.path.expanduser("~"))


if __name__ == "__main__":
    unittest.main()
