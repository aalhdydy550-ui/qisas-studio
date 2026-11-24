#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات توصيل أوامر الجولة 0.1.36 — مستوى CLI.

تتحقق أن التوصيل في studio.py يعمل فعليًا: `assemble`/`run`
بخلفية openreel و`--grade`، وأمر `grade`، وأمر `srt-ass`،
وعلما `fix-audio` الجديدان. بلا نشر حقيقي وبلا لمس المنشورات
المجدولة أو الطابور الحقيقي أو بيانات العملاء.
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "studio.py"] + list(args), cwd=STUDIO_DIR,
        capture_output=True, text=True, timeout=600)


def _make_video(out, duration=3):
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "color=c=0x404040:s=720x1280:r=30:d=%s" % duration,
         "-f", "lavfi", "-i",
         "sine=frequency=440:sample_rate=48000:duration=%s" % duration,
         "-t", str(duration), "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "28", "-pix_fmt", "yuv420p", "-c:a", "aac", out],
        check=True, timeout=120)


class TestBackendHelp(unittest.TestCase):
    def test_assemble_help_lists_openreel_and_grade(self):
        proc = _run_cli("assemble", "--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("openreel", proc.stdout)
        self.assertIn("--grade", proc.stdout)

    def test_run_help_lists_openreel_and_grade(self):
        proc = _run_cli("run", "--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("openreel", proc.stdout)
        self.assertIn("--grade", proc.stdout)

    def test_run_dry_run_openreel(self):
        proc = _run_cli("run", "--story", "anza", "--project",
                        "anza-part1", "--out", "/tmp/dry-openreel.mp4",
                        "--dry-run", "--backend", "openreel",
                        "--grade", "warm")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("openreel", proc.stdout)
        self.assertIn("render.py", proc.stdout)
        self.assertIn("warm", proc.stdout)

    def test_run_dry_run_bad_backend_rejected(self):
        proc = _run_cli("run", "--story", "anza", "--project",
                        "anza-part1", "--out", "/tmp/dry-x.mp4",
                        "--dry-run", "--backend", "nope")
        self.assertEqual(proc.returncode, 2)


class TestGradeCli(unittest.TestCase):
    def test_list_presets(self):
        proc = _run_cli("grade", "--video", "/tmp/x.mp4",
                        "--list-presets")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for name in ("warm", "vivid", "cinematic", "soft"):
            self.assertIn(name, proc.stdout)

    def test_list_presets_without_video(self):
        # عيب v0.1.36: `grade --list-presets` وحده كان يفشل لأن
        # --video مطلوب في argparse — صار اختياريًا معه.
        proc = _run_cli("grade", "--list-presets")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for name in ("warm", "vivid", "cinematic", "soft"):
            self.assertIn(name, proc.stdout)

    def test_grade_without_video_or_preset_rejected(self):
        proc = _run_cli("grade")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--video", proc.stdout + proc.stderr)

    def test_grade_real_short_video(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "in.mp4")
            _make_video(video)
            out = os.path.join(td, "graded.mp4")
            proc = _run_cli("grade", "--video", video, "--preset",
                            "warm", "--out", out)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(os.path.isfile(out))
            self.assertIn("تدرج لوني", proc.stdout)

    def test_grade_missing_video_fails(self):
        proc = _run_cli("grade", "--video", "/tmp/no-such.mp4",
                        "--preset", "warm")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("غير موجود", proc.stdout + proc.stderr)

    def test_grade_no_preset_rejected(self):
        proc = _run_cli("grade", "--video", "/tmp/x.mp4")
        self.assertEqual(proc.returncode, 2)


class TestSrtAssCli(unittest.TestCase):
    def test_srt_ass_real(self):
        with tempfile.TemporaryDirectory() as td:
            srt = os.path.join(td, "in.srt")
            ass = os.path.join(td, "out.ass")
            with open(srt, "w", encoding="utf-8") as f:
                f.write("1\n00:00:00,500 --> 00:00:04,200\n"
                        "عبارة تجريبية\n")
            proc = _run_cli("srt-ass", "--srt", srt, "--out", ass)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertTrue(os.path.isfile(ass))
            with open(ass, encoding="utf-8") as f:
                self.assertIn("عبارة تجريبية", f.read())

    def test_srt_ass_missing_fails(self):
        proc = _run_cli("srt-ass", "--srt", "/tmp/no-such.srt",
                        "--out", "/tmp/out.ass")
        self.assertEqual(proc.returncode, 1)


class TestFixAudioFlags(unittest.TestCase):
    def test_fix_audio_help_lists_new_flags(self):
        proc = _run_cli("fix-audio", "--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--denoise", proc.stdout)
        self.assertIn("--loudnorm", proc.stdout)

    def test_fix_audio_denoise_and_loudnorm(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "in.mp4")
            _make_video(video, duration=6)
            proc = _run_cli("fix-audio", "--video", video,
                            "--denoise", "--loudnorm")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("إزالة ضجيج", proc.stdout)
            self.assertIn("تطبيع جهارة", proc.stdout)


# ------------------------------------------------------------- daily

DAILY_QUEUE_TEXT = """# طابور قصص

## في الانتظار

4. **العنزة المباركة** — تحتاج جزأين
5. **عجائب الصدقة** — منشور واحد
"""


def _daily_cfg(tmpdir):
    queue = os.path.join(tmpdir, "queue.md")
    with open(queue, "w", encoding="utf-8") as f:
        f.write(DAILY_QUEUE_TEXT)
    return {
        "paths": {
            "queue_file": queue,
            "videos_dir": os.path.join(tmpdir, "videos"),
            "runs_dir": os.path.join(tmpdir, "runs"),
        },
        "publish": {"page_id": "1048148471706586",
                    "youtube_channel_id": "UCz5VeqN-eolCaCPGTpiWtJw"},
        "veo": {"balance_units": 750, "renews": "2026-12-13",
                "daily_cost_min": 100, "daily_cost_max": 140},
        "openmontage": {"projects_dir": "~/workspace/openmontage/projects"},
    }


class TestDailyOpenreelWiring(unittest.TestCase):
    """توصيل --backend openreel من daily إلى cmd_run."""

    def test_daily_help_lists_backend(self):
        """daily --help يعرض --backend و--grade."""
        proc = _run_cli("daily", "--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--backend", proc.stdout)
        self.assertIn("openreel", proc.stdout)
        self.assertIn("--grade", proc.stdout)

    def test_daily_dry_run_accepts_openreel(self):
        """daily --dry-run --backend openreel يقبل العلم ويطبع الخطة بلا تنفيذ."""
        with tempfile.TemporaryDirectory() as tmp:
            queue = os.path.join(tmp, "queue.md")
            with open(queue, "w", encoding="utf-8") as f:
                f.write(DAILY_QUEUE_TEXT)
            proc = _run_cli("daily", "--slot", "evening",
                            "--dry-run", "--backend", "openreel",
                            "--queue-file", queue)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("وضع تجريبي", proc.stdout)

    def test_batch_queue_file_dry_run(self):
        """انحدار: batch --queue-file لا يتعطل على datetime في config
        (كان json.dumps(cfg) يرفع TypeError قبل الإصلاح)."""
        with tempfile.TemporaryDirectory() as tmp:
            queue = os.path.join(tmp, "queue.md")
            with open(queue, "w", encoding="utf-8") as f:
                f.write(DAILY_QUEUE_TEXT)
            proc = _run_cli("batch", "--count", "1", "--source",
                            "openmontage", "--queue-file", queue)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("وضع تجريبي", proc.stdout)

    def test_daily_execute_threads_backend_to_run(self):
        """daily --execute يمرّر backend/grade إلى cmd_run عبر produce_fn."""
        import studio as studio_mod
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _daily_cfg(tmp)
            calls = []

            def fake_run(c, slug, project, out_path, allow_fallback,
                         **kw):
                calls.append((slug, project, kw))
                return 0

            def fake_execute(c, plan, produce_fn, *rest, **kw):
                produce_fn(c, "anza", "anza-part1",
                           os.path.join(tmp, "out.mp4"))
                return 0, {}

            with mock.patch.object(studio_mod, "cmd_run", fake_run), \
                    mock.patch.object(studio_mod.daily, "execute_daily",
                                      fake_execute):
                rc = studio_mod.cmd_daily(
                    cfg, slot="evening", execute=True,
                    queue_file=cfg["paths"]["queue_file"],
                    backend="openreel", grade="warm")
            self.assertEqual(rc, 0)
            self.assertEqual(len(calls), 1)
            slug, project, kw = calls[0]
            self.assertEqual(slug, "anza")
            self.assertEqual(project, "anza-part1")
            self.assertEqual(kw.get("backend"), "openreel")
            self.assertEqual(kw.get("grade"), "warm")


if __name__ == "__main__":
    unittest.main()
