#!/usr/bin/env python3
"""اختبارات احتفاظ النسخ الاحتياطية — الجولة 6 (2026-11-22).

تغطي prune_old_backups وmake_backup(keep=...):
- الاحتفاظ يبقي 7 ويحذف الأقدم؛
- مجلد فيه أقل من 7 → بلا حذف؛
- أحدث نسخة محمية دائمًا (حتى مع keep=0)؛
- ملفات غير نسخ لا تُمسّ؛
- keep مخصص يعمل.

كل الكتابة في مجلدات مؤقتة — لا تُمس نسخ
~/workspace/studio/backups/ الحقيقية أبدًا.
"""
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import update_backup


def _fake_backup(out_dir, day, hour=12):
    """نسخة وهمية باسم/تاريخ متسلسل (mtime مضبوط صراحةً)."""
    name = "backup-202611%02d-%02d0000-1-aaaa0000.zip" % (day, hour)
    path = os.path.join(out_dir, name)
    with open(path, "wb") as f:
        f.write(b"fake-backup-%d" % day)
    # mtime متسلسل: اليوم الأكبر = الأحدث.
    ts = 1763000000 + day * 86400 + hour * 3600
    os.utime(path, (ts, ts))
    return name


class TestPruneOldBackups(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "backups")
        os.makedirs(self.out)

    def _names(self):
        return sorted(os.listdir(self.out))

    def test_keeps_seven_deletes_oldest_three(self):
        made = [_fake_backup(self.out, d) for d in range(1, 11)]
        deleted = update_backup.prune_old_backups(self.out)
        self.assertEqual(len(deleted), 3)
        self.assertEqual(sorted(os.path.basename(p) for p in deleted),
                         sorted(made[:3]))
        self.assertEqual(self._names(), sorted(made[3:]))

    def test_fewer_than_seven_no_delete(self):
        made = [_fake_backup(self.out, d) for d in range(1, 4)]
        deleted = update_backup.prune_old_backups(self.out)
        self.assertEqual(deleted, [])
        self.assertEqual(self._names(), sorted(made))

    def test_exactly_seven_no_delete(self):
        made = [_fake_backup(self.out, d) for d in range(1, 8)]
        self.assertEqual(update_backup.prune_old_backups(self.out),
                         [])
        self.assertEqual(self._names(), sorted(made))

    def test_newest_always_protected(self):
        made = [_fake_backup(self.out, d) for d in range(1, 6)]
        deleted = update_backup.prune_old_backups(self.out, keep=1)
        self.assertEqual(len(deleted), 4)
        self.assertEqual(self._names(), [made[-1]])

    def test_keep_zero_or_negative_keeps_newest(self):
        made = [_fake_backup(self.out, d) for d in range(1, 6)]
        # keep=0 يُثبَّت إلى 1: تُحذف 4 وتبقى الأحدث فقط.
        deleted = update_backup.prune_old_backups(self.out, keep=0)
        self.assertEqual(len(deleted), 4)
        self.assertEqual(self._names(), [made[-1]])
        # keep سالب على ملف واحد: بلا حذف.
        self.assertEqual(
            update_backup.prune_old_backups(self.out, keep=-3), [])
        self.assertEqual(self._names(), [made[-1]])

    def test_non_backup_files_untouched(self):
        made = [_fake_backup(self.out, d) for d in range(1, 11)]
        others = ["notes.txt", "random.zip", "other.zip",
                  "pre-update-20261110-120000-1-bbbb0000.zip",
                  ".backup.lock", "backup-20261110-120000.zip.bak"]
        for name in others:
            with open(os.path.join(self.out, name), "wb") as f:
                f.write(b"keep-me")
        deleted = update_backup.prune_old_backups(self.out)
        self.assertEqual(len(deleted), 3)
        for name in others:
            self.assertIn(name, self._names(), name)
            with open(os.path.join(self.out, name), "rb") as f:
                self.assertEqual(f.read(), b"keep-me")
        self.assertEqual(
            [n for n in self._names() if n.startswith("backup-")
             and n.endswith(".zip")],
            sorted(made[3:]))

    def test_custom_keep(self):
        made = [_fake_backup(self.out, d) for d in range(1, 11)]
        deleted = update_backup.prune_old_backups(self.out, keep=3)
        self.assertEqual(len(deleted), 7)
        self.assertEqual(self._names(), sorted(made[7:]))

    def test_symlinked_backup_not_deleted(self):
        target = os.path.join(self.tmp, "target.zip")
        with open(target, "wb") as f:
            f.write(b"target-content")
        link = os.path.join(self.out, "backup-20261101-120000.zip")
        os.symlink(target, link)
        for d in range(2, 10):
            _fake_backup(self.out, d)
        deleted = update_backup.prune_old_backups(self.out, keep=7)
        self.assertNotIn(link, deleted)
        self.assertTrue(os.path.islink(link))
        with open(target, "rb") as f:
            self.assertEqual(f.read(), b"target-content")

    def test_missing_dir_returns_empty(self):
        self.assertEqual(
            update_backup.prune_old_backups(
                os.path.join(self.tmp, "no-such-dir")), [])


class TestMakeBackupRetention(unittest.TestCase):
    """make_backup الحقيقي على نسخة مؤقتة من مجلد استوديو."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.studio = os.path.join(self.tmp, "studio")
        os.makedirs(os.path.join(self.studio, "client-orders"))
        os.makedirs(os.path.join(self.studio, "runs"))
        with open(os.path.join(self.studio, "config.yaml"),
                  "w", encoding="utf-8") as f:
            f.write("publish:\n  page_id: '1'\n")
        self.queue = os.path.join(self.tmp, "queue.md")
        with open(self.queue, "w", encoding="utf-8") as f:
            f.write("# طابور\n")
        with open(os.path.join(self.studio, "client-orders",
                               "orders.jsonl"), "w",
                  encoding="utf-8") as f:
            f.write('{"order": 1}\n')
        self.cfg = {"paths": {"queue_file": self.queue}}
        self.out = os.path.join(self.studio, "backups")
        os.makedirs(self.out)

    def test_make_backup_creates_zip_and_prunes_to_seven(self):
        old = [_fake_backup(self.out, d) for d in range(1, 9)]
        zip_path, included, _missing = update_backup.make_backup(
            self.studio, self.cfg)
        self.assertTrue(os.path.isfile(zip_path))
        self.assertIn("config.yaml", included)
        with zipfile.ZipFile(zip_path) as zf:
            self.assertIn("manifest.txt", zf.namelist())
            self.assertIn("config.yaml", zf.namelist())
        names = sorted(n for n in os.listdir(self.out)
                       if n.startswith("backup-")
                       and n.endswith(".zip"))
        self.assertEqual(len(names), 7)
        # الأقدم (اليوم 1) حُذفت، والجديدة (الأحدث) موجودة.
        self.assertNotIn(old[0], names)
        self.assertIn(os.path.basename(zip_path), names)

    def test_make_backup_custom_keep(self):
        for d in range(1, 6):
            _fake_backup(self.out, d)
        zip_path, _inc, _miss = update_backup.make_backup(
            self.studio, self.cfg, keep=3)
        names = sorted(n for n in os.listdir(self.out)
                       if n.startswith("backup-")
                       and n.endswith(".zip"))
        self.assertEqual(len(names), 3)
        self.assertIn(os.path.basename(zip_path), names)


if __name__ == "__main__":
    unittest.main()
