#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات مثبّت setup.sh (حزمة v0.1.41).

تعمل على نسخة من السكربت + lib/ensure_env.py في مجلد مؤقت —
بلا أي مساس بالشجرة الحية أو بالبيئات الحقيقية. الوضعان
الآمنان فقط (--dry-run و--check)؛ التثبيت الحقيقي يُختبر
يدويًا في sandbox (انظر docs/SETUP.md).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP_SH = os.path.join(STUDIO_ROOT, "setup.sh")


def _stage_copy(tmp):
    """انسخ setup.sh + lib/ensure_env.py (+ __init__) إلى tmp."""
    shutil.copy2(SETUP_SH, os.path.join(tmp, "setup.sh"))
    lib = os.path.join(tmp, "lib")
    os.makedirs(lib)
    for name in ("__init__.py", "ensure_env.py"):
        shutil.copy2(os.path.join(STUDIO_ROOT, "lib", name),
                     os.path.join(lib, name))
    return os.path.join(tmp, "setup.sh")


class TestSetupScriptSafeModes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.script = _stage_copy(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, *args, extra_env=None):
        env = dict(os.environ)
        env["STUDIO_SETUP_NO_APT"] = "1"
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            ["bash", self.script] + list(args),
            capture_output=True, text=True, timeout=180,
            cwd=self.tmp.name, env=env)

    def test_syntax_ok(self):
        r = subprocess.run(["bash", "-n", self.script],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_help_exit_0(self):
        r = self._run("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("--dry-run", r.stdout)
        self.assertIn("--check", r.stdout)
        self.assertIn("--with", r.stdout)

    def test_dry_run_exit_0_and_creates_nothing(self):
        r = self._run("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[DRY-RUN]", r.stdout)
        self.assertIn("[1/7]", r.stdout)
        self.assertIn("[7/7]", r.stdout)
        self.assertFalse(os.path.exists(
            os.path.join(self.tmp.name, ".venv-youtube")))
        self.assertFalse(os.path.exists(
            os.path.join(self.tmp.name, ".venv-whisper")))
        self.assertFalse(os.path.exists(
            os.path.join(self.tmp.name, "config.yaml")))

    def test_dry_run_with_heavy_mentions_it(self):
        r = self._run("--dry-run", "--with", "whisper")
        self.assertEqual(r.returncode, 0)
        self.assertIn("whisper", r.stdout)

    def test_check_reports_missing_and_creates_nothing(self):
        r = self._run("--check")
        # بيئة خفيفة غائبة في المجلد المؤقت → فحص فاشل (1)، بلا تثبيت.
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("[MISS] gtts", r.stdout)
        self.assertIn("[LAZY] whisper", r.stdout)
        self.assertFalse(os.path.exists(
            os.path.join(self.tmp.name, ".venv-youtube")))
        self.assertFalse(os.path.exists(
            os.path.join(self.tmp.name, "config.yaml")))

    def test_check_is_idempotent_and_readonly(self):
        # --check مرتين يعطي نفس المخرجات ولا يغيّر المجلد إطلاقًا.
        before = sorted(os.listdir(self.tmp.name))
        r1 = self._run("--check")
        mid = sorted(os.listdir(self.tmp.name))
        r2 = self._run("--check")
        self.assertEqual(r1.returncode, r2.returncode)
        self.assertEqual(r1.stdout, r2.stdout)
        self.assertEqual(before, mid)
        self.assertEqual(mid, sorted(os.listdir(self.tmp.name)))

    def test_unknown_flag_exit_2(self):
        r = self._run("--bogus")
        self.assertEqual(r.returncode, 2)

    def test_with_bad_value_exit_2_without_side_effects(self):
        r = self._run("--dry-run", "--with", "bogus-tool")
        self.assertEqual(r.returncode, 2)
        self.assertFalse(os.path.exists(
            os.path.join(self.tmp.name, ".venv-youtube")))


class TestSetupScriptCompliance(unittest.TestCase):
    def test_no_forbidden_component_words(self):
        """حارس الامتثال: setup.sh بلا أي ذكر للمكوّنين الخارجيين."""
        with open(SETUP_SH, encoding="utf-8") as f:
            text = f.read().lower()
        for word in ("openmontage", "concat"):
            self.assertNotIn(word, text,
                             "setup.sh يذكر %s — ممنوع في سكربتات "
                             "الإعداد" % word)

    def test_documents_lazy_heavy_by_default(self):
        with open(SETUP_SH, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("--dry-run", text)
        self.assertIn("--check", text)
        self.assertIn(".venv-youtube", text)
        self.assertIn("lib.ensure_env", text)


if __name__ == "__main__":
    unittest.main()
