#!/usr/bin/env python3
"""اختبارات استعادة نسخة مستخدم — على مجلدات مؤقتة فقط.

لا لمس للطابور الحقيقي ولا لبيانات العملاء الحقيقية ولا لنسخ
الاختراق الاحتياطية. كل الاختبارات على جذر studio مؤقت.
"""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import update_backup

GOOD_CONFIG = b"publish:\n  page_id: '1048148471706586'\n"
GOOD_QUEUE = "# الطابور\n\n## 1. قصة تجريبية\n".encode("utf-8")


def _make_root(td):
    root = Path(td)
    (root / "config.yaml").write_bytes(GOOD_CONFIG)
    (root / "story-queue.md").write_bytes(GOOD_QUEUE)
    (root / "client-orders" / "orders").mkdir(parents=True)
    (root / "client-orders" / "orders.jsonl").write_text(
        '{"order_id": "QS-1"}\n', encoding="utf-8")
    (root / "client-orders" / "orders" / "QS-1.txt").write_text(
        "طلب تجريبي", encoding="utf-8")
    (root / "runs").mkdir()
    (root / "runs" / "analyze-x.json").write_text("{}", encoding="utf-8")
    return root


def _make_zip(path, entries):
    """entries: {arcname: bytes} أو {arcname: (bytes, external_attr)}."""
    with zipfile.ZipFile(path, "w") as zf:
        for name, value in entries.items():
            if isinstance(value, tuple):
                data, attr = value
                info = zipfile.ZipInfo(name)
                info.external_attr = attr
                zf.writestr(info, data)
            else:
                zf.writestr(name, value)
    return path


def _good_entries():
    return {"config.yaml": GOOD_CONFIG,
            "story-queue.md": GOOD_QUEUE,
            "client-orders/orders.jsonl": b'{"order_id": "QS-1"}\n',
            "client-orders/orders/QS-1.txt": "طلب تجريبي".encode("utf-8"),
            "runs/analyze-x.json": b"{}",
            "manifest.txt": b"manifest\n"}


class TestPlanUserRestore(unittest.TestCase):
    def test_valid_backup_plans_state_files_only(self):
        with tempfile.TemporaryDirectory() as td:
            _make_root(td)
            z = _make_zip(os.path.join(td, "b.zip"), _good_entries())
            plan = update_backup.plan_user_restore(z, td)
        self.assertEqual(set(plan["restorable"]),
                         {"config.yaml", "story-queue.md",
                          "client-orders/orders.jsonl",
                          "client-orders/orders/QS-1.txt"})
        self.assertIn("runs/analyze-x.json", plan["skipped"])
        self.assertGreater(plan["total_bytes"], 0)

    def test_secret_entry_aborts_restore(self):
        entries = _good_entries()
        entries["youtube-token.json"] = b'{"refresh_token": "x"}'
        with tempfile.TemporaryDirectory() as td:
            z = _make_zip(os.path.join(td, "b.zip"), entries)
            with self.assertRaises(update_backup.UpdateError) as ctx:
                update_backup.plan_user_restore(z, td)
        self.assertIn("لا تُستعاد", str(ctx.exception))

    def test_client_secrets_entry_aborts_restore(self):
        entries = _good_entries()
        entries["client_secrets.json"] = b"{}"
        with tempfile.TemporaryDirectory() as td:
            z = _make_zip(os.path.join(td, "b.zip"), entries)
            with self.assertRaises(update_backup.UpdateError):
                update_backup.plan_user_restore(z, td)

    def test_traversal_entry_aborts_restore(self):
        entries = _good_entries()
        entries["../evil.txt"] = b"evil"
        with tempfile.TemporaryDirectory() as td:
            z = _make_zip(os.path.join(td, "b.zip"), entries)
            with self.assertRaises(update_backup.UpdateError):
                update_backup.plan_user_restore(z, td)

    def test_absolute_entry_aborts_restore(self):
        entries = _good_entries()
        entries["/etc/passwd"] = b"root"
        with tempfile.TemporaryDirectory() as td:
            z = _make_zip(os.path.join(td, "b.zip"), entries)
            with self.assertRaises(update_backup.UpdateError):
                update_backup.plan_user_restore(z, td)

    def test_symlink_entry_aborts_restore(self):
        entries = _good_entries()
        entries["config.yaml"] = (GOOD_CONFIG, 0o120777 << 16)
        with tempfile.TemporaryDirectory() as td:
            z = _make_zip(os.path.join(td, "b.zip"), entries)
            with self.assertRaises(update_backup.UpdateError):
                update_backup.plan_user_restore(z, td)

    def test_invalid_config_yaml_aborts_restore(self):
        entries = _good_entries()
        entries["config.yaml"] = b"publish: [unclosed\n"
        with tempfile.TemporaryDirectory() as td:
            z = _make_zip(os.path.join(td, "b.zip"), entries)
            with self.assertRaises(update_backup.UpdateError):
                update_backup.plan_user_restore(z, td)

    def test_empty_backup_aborts_restore(self):
        with tempfile.TemporaryDirectory() as td:
            z = _make_zip(os.path.join(td, "b.zip"),
                          {"manifest.txt": b"manifest\n"})
            with self.assertRaises(update_backup.UpdateError):
                update_backup.plan_user_restore(z, td)

    def test_missing_zip_aborts_restore(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(update_backup.UpdateError):
                update_backup.plan_user_restore(
                    os.path.join(td, "nope.zip"), td)


class TestApplyUserRestore(unittest.TestCase):
    def test_apply_restores_exact_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = _make_root(td)
            z = _make_zip(os.path.join(td, "b.zip"), _good_entries())
            plan = update_backup.plan_user_restore(z, td)
            # غيّر الملفات الحالية ثم استرجع
            (root / "config.yaml").write_text("publish: {}\n",
                                              encoding="utf-8")
            (root / "story-queue.md").write_text("فارغ\n",
                                                 encoding="utf-8")
            restored = update_backup.apply_user_restore(z, td, plan)
            self.assertEqual(set(restored), set(plan["restorable"]))
            self.assertEqual((root / "config.yaml").read_bytes(),
                             GOOD_CONFIG)
            self.assertEqual((root / "story-queue.md").read_bytes(),
                             GOOD_QUEUE)
            # ملف لم يكن في النسخة لم يُمسّ
            self.assertEqual((root / "runs" / "analyze-x.json")
                             .read_text(encoding="utf-8"), "{}")


class TestCmdRestoreBackup(unittest.TestCase):
    def _setup(self, td):
        root = _make_root(td)
        z = _make_zip(os.path.join(td, "b.zip"), _good_entries())
        # غيّر الحالة الحالية (هي ما سيُستعاد فوقه)
        (root / "config.yaml").write_text("publish: {}\n",
                                          encoding="utf-8")
        return root, z

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            root, z = self._setup(td)
            with mock.patch.object(studio, "STUDIO_DIR", td):
                rc = studio.cmd_restore_backup({}, z, dry_run=True)
            self.assertEqual(rc, 0)
            self.assertEqual((root / "config.yaml").read_text(
                encoding="utf-8"), "publish: {}\n")
            self.assertFalse((root / "backups").exists())

    def test_yes_restores_and_takes_safety_backup(self):
        with tempfile.TemporaryDirectory() as td:
            root, z = self._setup(td)
            with mock.patch.object(studio, "STUDIO_DIR", td):
                rc = studio.cmd_restore_backup({}, z, yes=True)
            self.assertEqual(rc, 0)
            self.assertEqual((root / "config.yaml").read_bytes(),
                             GOOD_CONFIG)
            backups = list((root / "backups").glob("backup-*.zip"))
            self.assertEqual(len(backups), 1)
            # نسخة الأمان تحفظ الحالة السابقة (قبل الاسترجاع)
            with zipfile.ZipFile(backups[0]) as zf:
                self.assertEqual(zf.read("config.yaml"),
                                 b"publish: {}\n")

    def test_declined_prompt_changes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            root, z = self._setup(td)
            with mock.patch.object(studio, "STUDIO_DIR", td), \
                 mock.patch("builtins.input", return_value="لا"):
                rc = studio.cmd_restore_backup({}, z)
            self.assertEqual(rc, 1)
            self.assertEqual((root / "config.yaml").read_text(
                encoding="utf-8"), "publish: {}\n")
            self.assertFalse((root / "backups").exists())

    def test_confirmed_prompt_restores(self):
        with tempfile.TemporaryDirectory() as td:
            root, z = self._setup(td)
            with mock.patch.object(studio, "STUDIO_DIR", td), \
                 mock.patch("builtins.input", return_value="نعم"):
                rc = studio.cmd_restore_backup({}, z)
            self.assertEqual(rc, 0)
            self.assertEqual((root / "config.yaml").read_bytes(),
                             GOOD_CONFIG)

    def test_secret_backup_refused_by_command(self):
        with tempfile.TemporaryDirectory() as td:
            root, z = self._setup(td)
            entries = _good_entries()
            entries["youtube-token.json"] = b'{"refresh_token": "x"}'
            bad = _make_zip(os.path.join(td, "bad.zip"), entries)
            with mock.patch.object(studio, "STUDIO_DIR", td):
                rc = studio.cmd_restore_backup({}, bad, yes=True)
            self.assertEqual(rc, 1)
            self.assertEqual((root / "config.yaml").read_text(
                encoding="utf-8"), "publish: {}\n")
            self.assertFalse((root / "backups").exists())


if __name__ == "__main__":
    unittest.main()
