#!/usr/bin/env python3
"""اختبارات الجولة 8 (v0.1.33) — أمر version، وترويسة help-ar،
والفرق بين run-queue وbatch، ومساعدة publish، ورسالة التجريبي
في daily.

بلا شبكة وبلا نشر — اختبار `publish --help` و`--version`
عبر استدعاء studio.py كعملية فرعية (قراءة فقط).
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import help_ar

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestVersionCommand(unittest.TestCase):
    def test_version_prints_current_version(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = studio.cmd_version()
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("0.1.33", out)
        self.assertIn("studio", out)

    def test_remote_status_from_sync_log(self):
        with tempfile.TemporaryDirectory() as td:
            log = os.path.join(td, "sync.json")
            entries = [
                {"owner": "aalhdydy550-ui", "repo": "qisas-studio",
                 "branch": "main",
                 "commit_sha": "9990257a3f5f736994f50e167f8e354eb00f2fa5",
                 "paths": ["studio.py"]},
                {"owner": "aalhdydy550-ui", "repo": "qisas-studio",
                 "branch": "main",
                 "commit_sha": "aaaaaaaabbbbbbbbccccccccddddddddeeeeeeee",
                 "paths": ["README.md"]},
            ]
            with open(log, "w", encoding="utf-8") as f:
                json.dump(entries, f)
            line = studio.remote_status_line(sync_log=log)
        self.assertIn("qisas-studio", line)
        self.assertIn("aaaaaaaa", line)
        self.assertIn("2 إدخالًا", line)

    def test_remote_status_skips_fake_test_entries(self):
        # إدخال وهمي dddd… في نهاية السجل (من تشغيل الاختبارات)
        # يُتخطى — المرجع آخر إدخال حقيقي.
        with tempfile.TemporaryDirectory() as td:
            log = os.path.join(td, "sync.json")
            entries = [
                {"owner": "aalhdydy550-ui", "repo": "qisas-studio",
                 "branch": "main",
                 "commit_sha": "9990257a3f5f736994f50e167f8e354eb00f2fa5",
                 "paths": ["studio.py"]},
                {"owner": "aalhdydy550-ui", "repo": "qisas-studio",
                 "branch": "main", "commit_sha": "d" * 40,
                 "paths": ["studio.py"]},
            ]
            with open(log, "w", encoding="utf-8") as f:
                json.dump(entries, f)
            line = studio.remote_status_line(sync_log=log)
        self.assertIn("9990257a", line)
        self.assertNotIn("dddddddd", line)
        self.assertIn("1 إدخالًا", line)

    def test_remote_status_unknown_without_log(self):
        line = studio.remote_status_line(
            sync_log="/tmp/no-such-sync-log-xyz.json")
        self.assertIn("غير معروفة", line)

    def test_cli_version_subcommand(self):
        proc = subprocess.run(
            [sys.executable, "studio.py", "version"],
            cwd=STUDIO_DIR, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("0.1.33", proc.stdout)

    def test_cli_double_dash_version(self):
        proc = subprocess.run(
            [sys.executable, "studio.py", "--version"],
            cwd=STUDIO_DIR, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("0.1.33", proc.stdout)


class TestHelpArRound8(unittest.TestCase):
    def test_quick_start_header(self):
        text = help_ar.help_text()
        self.assertIn("بداية سريعة", text)
        self.assertIn("python3 studio.py init", text)
        self.assertIn("python3 studio.py run --demo", text)
        self.assertIn("python3 studio.py daily --dry-run", text)
        self.assertIn("لا ينفّذ شيئًا", text)
        self.assertIn("افتراضيًا وضع تجريبي", text)

    def test_run_queue_vs_batch_documented(self):
        text = help_ar.help_text()
        # batch هو المسار الحالي، وrun-queue إرثي للتوافق.
        self.assertIn("المسار الحالي", text)
        self.assertIn("إرثي", text)
        batch_desc = [d for n, d, _ in help_ar.COMMANDS
                      if n == "batch"][0]
        self.assertIn("المسار الحالي", batch_desc)
        rq_desc = [d for n, d, _ in help_ar.COMMANDS
                   if n == "run-queue"][0]
        self.assertIn("إرثي", rq_desc)
        self.assertIn("batch", rq_desc)

    def test_publish_help_lists_all_platforms(self):
        proc = subprocess.run(
            [sys.executable, "studio.py", "publish", "--help"],
            cwd=STUDIO_DIR, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        # argparse يلف الأسطر الطويلة ويُقسّم الكلمات بشرطة — أعد
        # وصل الكلمات المقسومة قبل الفحص.
        import re
        flat = " ".join(re.sub(r"-\n\s*", "", proc.stdout).split())
        for name in ("facebook", "youtube", "tiktok", "instagram"):
            self.assertIn(name, flat,
                          "المنصة %s غائبة من publish --help" % name)
        self.assertIn("tiktok-auth", flat)
        self.assertIn("instagram-auth", flat)

    def test_daily_dry_run_message_is_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            queue = os.path.join(td, "queue.md")
            with open(queue, "w", encoding="utf-8") as f:
                f.write("# طابور قصص\n\n## في الانتظار\n\n"
                        "4. **العنزة المباركة** — تحتاج جزأين\n")
            cfg = {
                "paths": {
                    "queue_file": queue,
                    "videos_dir": os.path.join(td, "videos"),
                    "runs_dir": os.path.join(td, "runs"),
                },
                "openmontage": {"projects_dir": os.path.join(
                    td, "projects")},
                "publish": {"page_id": "1048148471706586"},
                "veo": {"balance_units": 50,
                        "renews": "2026-12-13",
                        "daily_cost_min": 100,
                        "daily_cost_max": 140},
            }
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = studio.cmd_daily(cfg, slot="morning",
                                      execute=False,
                                      queue_file=queue)
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("لم يُنفَّذ شيء", out)
            self.assertIn("--execute", out)


if __name__ == "__main__":
    unittest.main()
