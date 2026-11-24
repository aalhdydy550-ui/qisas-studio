#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات أمر الحماية — جولة الحماية المرحلة 2 (بلا رفع نسخة).

- فجوات .gitignore الثلاث: الأنماط العريضة موجودة في الملف
  الحقيقي، والحارس يطلبها، وغيابها يُكتشف (انحدار).
- فحص النسخة الاحتياطية: جديدة/قديمة/غائبة/تالفة.
- الفحوصات السريعة (doctor): شجرة نظيفة تمر، وسرّ يفشل.
- تدهور الأدوات الخارجية: غياب أدوات ~/workspace/protection/
  يرجع «غير متاح» ولا يفشل الأمر.
- ربط doctor: فحص «حماية المشروع (protect)» موجود وأخضر.
"""
import os
import sys
import tempfile
import time
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import doctor, protect, secret_guard

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BROAD_PATTERNS = ("*.env*", "*token*", "id_rsa*")


def _gitignore_with_required():
    return "\n".join(secret_guard.REQUIRED_GITIGNORE) + "\n"


def _make_backup(backup_dir, name="backup-20261122-120000-ab12cd34.zip",
                 age_hours=1.0, corrupt=False):
    path = os.path.join(backup_dir, name)
    if corrupt:
        with open(path, "wb") as fh:
            fh.write(b"not a zip file at all")
    else:
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("manifest.txt", "test")
    mtime = time.time() - age_hours * 3600
    os.utime(path, (mtime, mtime))
    return path


def _make_tree(files, with_backup=True, backup_age_hours=1.0):
    """شجرة مؤقتة: .gitignore كامل + ملفات + backups/ (ترجع المسار)."""
    td = tempfile.mkdtemp()
    with open(os.path.join(td, ".gitignore"), "w",
              encoding="utf-8") as fh:
        fh.write(_gitignore_with_required())
    for name, content in files.items():
        path = os.path.join(td, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
    if with_backup:
        bdir = os.path.join(td, "backups")
        os.makedirs(bdir)
        _make_backup(bdir, age_hours=backup_age_hours)
    return td


class TestGitignoreGaps(unittest.TestCase):
    def test_broad_patterns_present_in_real_gitignore(self):
        """الأنماط العريضة الثلاث موجودة فعلًا في .gitignore."""
        with open(os.path.join(STUDIO_ROOT, ".gitignore"),
                  encoding="utf-8") as fh:
            content = fh.read()
        for pattern in BROAD_PATTERNS:
            self.assertIn(pattern, content, pattern)

    def test_guard_requires_broad_patterns(self):
        """الحارس يطلب الأنماط العريضة والشجرة الحقيقية تغطيها."""
        for pattern in BROAD_PATTERNS:
            self.assertIn(pattern, secret_guard.REQUIRED_GITIGNORE)
        self.assertEqual(secret_guard.check_gitignore(STUDIO_ROOT), [])

    def test_missing_broad_pattern_is_detected(self):
        """انحدار: إن عادت الفجوة (حُذف نمط) يكشفها الحارس."""
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, ".gitignore"), "w",
                      encoding="utf-8") as fh:
                fh.write(".env\n*.key\n*.token\n")  # بلا الأنماط العريضة
            missing = secret_guard.check_gitignore(td)
            for pattern in BROAD_PATTERNS:
                self.assertIn(pattern, missing)


class TestBackupCheck(unittest.TestCase):
    def test_fresh_backup_passes(self):
        td = _make_tree({}, backup_age_hours=1.0)
        result = protect.check_backup(td)
        self.assertTrue(result["ok"])

    def test_no_backup_dir_warns(self):
        with tempfile.TemporaryDirectory() as td:
            result = protect.check_backup(td)
            self.assertFalse(result["ok"])
            self.assertEqual(result["level"], "warn")

    def test_empty_backup_dir_fails(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "backups"))
            result = protect.check_backup(td)
            self.assertFalse(result["ok"])
            self.assertEqual(result["level"], "error")

    def test_old_backup_warns(self):
        td = _make_tree({}, backup_age_hours=72.0)
        result = protect.check_backup(td)
        self.assertFalse(result["ok"])
        self.assertEqual(result["level"], "warn")

    def test_corrupt_backup_fails(self):
        with tempfile.TemporaryDirectory() as td:
            bdir = os.path.join(td, "backups")
            os.makedirs(bdir)
            _make_backup(bdir, corrupt=True)
            result = protect.check_backup(td)
            self.assertFalse(result["ok"])
            self.assertEqual(result["level"], "error")

    def test_ignores_non_backup_files(self):
        with tempfile.TemporaryDirectory() as td:
            bdir = os.path.join(td, "backups")
            os.makedirs(bdir)
            with open(os.path.join(bdir, "notes.txt"), "w") as fh:
                fh.write("not a backup")
            result = protect.check_backup(td)
            self.assertFalse(result["ok"])
            self.assertEqual(result["level"], "error")


class TestFastChecks(unittest.TestCase):
    def test_clean_tree_passes(self):
        td = _make_tree({"hello.py": "print('hello')\n"})
        for result in protect.run_fast_checks(td):
            self.assertTrue(result["ok"], result)

    def test_secret_in_tree_fails(self):
        # القيمة الاصطناعية تُبنى بالتجميع حتى لا تظهر حرفيًا
        # في هذا الملف نفسه فيصطادها حارس الشجرة الحقيقية.
        fake = "sk_" + "live_" + "0123456789abcdef"
        td = _make_tree({"leak.py": 'api_key = "%s"\n' % fake})
        results = protect.run_fast_checks(td)
        secrets = [r for r in results if "أسرار" in r["name"]][0]
        self.assertFalse(secrets["ok"])
        self.assertEqual(secrets["level"], "error")
        # التقرير لا يحمل قيمة السر أبدًا.
        self.assertNotIn("sk_live", secrets["detail"])

    def test_gitignore_gap_fails_fast_checks(self):
        td = _make_tree({"hello.py": "print('hello')\n"})
        with open(os.path.join(td, ".gitignore"), "w",
                  encoding="utf-8") as fh:
            fh.write(".env\n")
        results = protect.run_fast_checks(td)
        secrets = [r for r in results if "أسرار" in r["name"]][0]
        self.assertFalse(secrets["ok"])
        self.assertIn("*.env*", secrets["detail"])


class TestToolDegradation(unittest.TestCase):
    def test_missing_protection_tools_are_unavailable(self):
        """غياب أدوات ~/workspace/protection/ = «غير متاح» لا فشل."""
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(protect, "PROTECTION_DIR", td), \
                    mock.patch.object(protect, "INTEGRITY_PY",
                                      os.path.join(td, "integrity.py")), \
                    mock.patch.object(protect, "PERM_AUDIT_PY",
                                      os.path.join(td, "perm-audit.py")):
                self.assertIsNone(protect.check_integrity()["ok"])
                self.assertIsNone(protect.check_permissions()["ok"])

    def test_run_all_never_raises_without_tools(self):
        """غياب الأدوات الخارجية = «غير متاح» لا فشل — مع شجرة
        نظيفة (gitignore + نسخة احتياطية) حتى لا يتداخل فشلها."""
        td = _make_tree({})
        with tempfile.TemporaryDirectory() as empty:
            with mock.patch.object(protect, "PROTECTION_DIR", empty), \
                    mock.patch.object(protect, "INTEGRITY_PY",
                                      os.path.join(empty, "integrity.py")), \
                    mock.patch.object(protect, "PERM_AUDIT_PY",
                                      os.path.join(empty, "perm-audit.py")):
                results = protect.run_all(td)
                self.assertEqual(len(results), 4)
                text, errors, _warnings = protect.format_report(results)
                self.assertEqual(errors, 0)
                self.assertIn("غير متاح", text)

    def test_format_report_counts(self):
        results = [
            {"name": "أ", "ok": True, "level": "ok",
             "detail": "سليم", "fix": ""},
            {"name": "ب", "ok": False, "level": "error",
             "detail": "خطأ", "fix": "أصلحه"},
            {"name": "ج", "ok": False, "level": "warn",
             "detail": "تحذير", "fix": ""},
            {"name": "د", "ok": None, "level": "warn",
             "detail": "غائب", "fix": ""},
        ]
        text, errors, warnings = protect.format_report(results)
        self.assertEqual(errors, 1)
        self.assertEqual(warnings, 1)
        self.assertIn("[PASS] أ", text)
        self.assertIn("[FAIL] ب", text)
        self.assertIn("[WARN] ج", text)
        self.assertIn("[غير متاح] د", text)


def _has_fresh_backup():
    """نسخة احتياطية حديثة (≤ يومين) في الشجرة الحقيقية؟

    جولة v0.1.41 (إصلاح CI) — السبب الجذري: _protect_check
    يجمع check_secrets + check_backup، وbackups/ في .gitignore
    فنسخة CI العارية بلا أي نسخة احتياطية أصلًا → check_backup
    خطأ → الفحص كله not ok. الاختبار يفحص شجرة آلة مهيأة،
    لا نسخة CI عارية.
    """
    try:
        return protect.check_backup()["ok"] is True
    except Exception:
        return False


class TestDoctorProtectCheck(unittest.TestCase):
    @unittest.skipUnless(
        _has_fresh_backup(),
        "لا نسخة احتياطية حديثة في الشجرة — بيئة CI "
        "(backups/ في .gitignore)")
    def test_protect_check_is_green_on_real_tree(self):
        """الشجرة الحقيقية: أسرار نظيفة + .gitignore مغطى +
        نسخة احتياطية حديثة → الفحص أخضر."""
        result = doctor._protect_check()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["name"], "حماية المشروع (protect)")

    @unittest.skipUnless(
        _has_fresh_backup(),
        "لا نسخة احتياطية حديثة في الشجرة — بيئة CI "
        "(backups/ في .gitignore)")
    def test_protect_check_present_in_run_checks(self):
        """الفحص موجود ضمن قائمة doctor الكاملة."""
        fake_cfg = {
            "paths": {
                "videos_dir": "~/workspace/videos",
                "runs_dir": "~/workspace/studio/runs",
                "openmontage_root": "~/workspace/openmontage",
                "concat_bin": "~/workspace/studio/bin/concat.AppImage",
                "ensure_env": "~/workspace/ensure-env.sh",
                "youtube_venv": "~/workspace/studio/.venv-youtube",
                "backup_dir": "~/workspace/studio/backups",
            },
            "openmontage": {"enabled": True},
            "concat": {"enabled": True},
        }
        resp = mock.MagicMock()
        resp.status = 200
        resp.__enter__ = mock.MagicMock(return_value=resp)
        resp.__exit__ = mock.MagicMock(return_value=False)
        run_mock = mock.MagicMock()
        run_mock.stdout = "Noto Naskh Arabic"
        with mock.patch("lib.doctor.urllib.request.urlopen",
                        return_value=resp), \
                mock.patch("lib.doctor.subprocess.run",
                           return_value=run_mock):
            checks = doctor.run_checks(fake_cfg)
        names = [c["name"] for c in checks]
        self.assertIn("حماية المشروع (protect)", names)
        self.assertEqual(len(checks), 27)
        protect_check = [c for c in checks
                         if c["name"] == "حماية المشروع (protect)"][0]
        self.assertTrue(protect_check["ok"], protect_check)


if __name__ == "__main__":
    unittest.main()
