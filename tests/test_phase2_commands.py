#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات أوامر المرحلة 2 (preview/logs/balance/queue import/
الصوت الافتراضي) — بلا نشر وبلا لمس للطابور الحقيقي."""
import datetime
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import cost_ledger

SENTENCE = ("في يوم من الأيام خرج رجل فقير من بيته يبحث عن رزق حلال "
            "لأولاده الجياع.")


def _capture(fn, *args, **kwargs):
    buf = io.StringIO()
    with mock.patch("sys.stdout", buf):
        rc = fn(*args, **kwargs)
    return rc, buf.getvalue()


class TestBalanceLedgerCmd(unittest.TestCase):
    def test_record_and_history(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(studio, "STUDIO_DIR", td):
                rc, out = _capture(studio.cmd_balance, {},
                                   record=120, video="عائشة ج2",
                                   clips=6)
                self.assertEqual(rc, 0)
                self.assertIn("120 وحدة", out)
                rc, out = _capture(studio.cmd_balance, {}, record=100,
                                   video="العنزة ج1", clips=5)
                self.assertEqual(rc, 0)
                rc, out = _capture(studio.cmd_balance, {},
                                   history_flag=True)
                self.assertEqual(rc, 0)
                self.assertIn("220 وحدة", out)
                self.assertEqual(len(cost_ledger.history(td)), 2)

    def test_record_without_video_fails(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(studio, "STUDIO_DIR", td):
                rc, _out = _capture(studio.cmd_balance, {}, record=120)
            self.assertEqual(rc, 2)
            self.assertEqual(cost_ledger.history(td), [])

    def test_history_empty(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(studio, "STUDIO_DIR", td):
                rc, out = _capture(studio.cmd_balance, {},
                                   history_flag=True)
            self.assertEqual(rc, 0)
            self.assertIn("لا قيود", out)

    def test_forecast_still_works(self):
        cfg = {"veo": {"balance_units": 680, "renews": "2026-12-13",
                       "daily_cost_min": 100, "daily_cost_max": 140}}
        rc, out = _capture(studio.cmd_balance, cfg)
        self.assertEqual(rc, 0)
        self.assertIn("680", out)


class TestDefaultVoice(unittest.TestCase):
    def test_voice_from_config(self):
        self.assertEqual(studio._default_voice({}), "piper")
        self.assertEqual(
            studio._default_voice({"narration": {"voice": "gtts"}}),
            "gtts")
        self.assertEqual(
            studio._default_voice({"narration": {"voice": "bogus"}}),
            "piper")
        self.assertEqual(
            studio._default_voice({"narration": {}}), "piper")

    def test_long_narration_dispatch_uses_config_voice(self):
        """التوزيع يمرّر صوت الإعداد عند غياب --voice."""
        cfg = studio.load_config()
        expected = studio._default_voice(cfg)
        fake = {"output": "/tmp/x.wav", "duration": 1.0, "chunks": [1]}
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "n.wav")
            argv = ["studio.py", "long-narration", "--text", "نص",
                    "--out", out]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch("lib.long_narration.synthesize_long",
                            return_value=fake) as synth:
                rc = studio.main()
            self.assertEqual(rc, 0)
            self.assertEqual(synth.call_args.kwargs.get("voice")
                             or synth.call_args[1].get("voice"),
                             expected)


def _make_video(path, seconds=5):
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=black:s=720x1280:d=%d" % seconds,
                    "-f", "lavfi", "-i",
                    "sine=frequency=440:d=%d" % seconds,
                    "-shortest", "-c:v", "libx264", "-c:a", "aac",
                    "-y", path], check=True, timeout=120)


class TestPreviewCmd(unittest.TestCase):
    def test_preview_command_writes_page(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            _make_video(video)
            rc, out = _capture(studio.cmd_preview, {}, video,
                               caption="كابشن <b>تجريبي</b>",
                               first_comment="تعليق أول",
                               out_dir=td, title="قصة")
            self.assertEqual(rc, 0)
            page_path = os.path.join(td, "قصة-preview.html")
            self.assertTrue(os.path.isfile(page_path))
            page = open(page_path, encoding="utf-8").read()
            self.assertIn("&lt;b&gt;تجريبي&lt;/b&gt;", page)
            self.assertIn("تعليق أول", page)
            self.assertIn("صفحة المعاينة", out)

    def test_preview_missing_video_fails(self):
        rc, out = _capture(studio.cmd_preview, {}, "/tmp/nope.mp4")
        self.assertEqual(rc, 1)
        self.assertIn("تعذرت المعاينة", out)


class TestLogsCmd(unittest.TestCase):
    def _setup(self, td):
        # التواريخ نسبية لليوم الحقيقي: كان الاختبار مثبّتًا على
        # 2026-11-22 ففشل في أي يوم آخر (اليوم = anza، أمس = hamati).
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        runs = Path(td) / "runs"
        anza_day = today.strftime("%Y%m%d")
        (runs / ("anza-%s-070000" % anza_day)).mkdir(parents=True)
        (runs / ("anza-%s-070000" % anza_day) / "run-log.json").write_text(
            json.dumps({"run": "anza-%s-070000" % anza_day, "story": "anza",
                        "started": "%sT07:00:00" % today.isoformat(),
                        "steps": {"render": {"status": "ok"}}},
                       ensure_ascii=False), encoding="utf-8")
        hamati_day = yesterday.strftime("%Y%m%d")
        (runs / ("hamati-%s-190000" % hamati_day)).mkdir(parents=True)
        (runs / ("hamati-%s-190000" % hamati_day) / "run-log.json").write_text(
            json.dumps({"run": "hamati-%s-190000" % hamati_day,
                        "story": "hamati",
                        "started": "%sT19:00:00" % yesterday.isoformat(),
                        "steps": {"script": {"status": "failed",
                                             "error": "خطأ تجريبي"}}},
                       ensure_ascii=False), encoding="utf-8")
        return str(runs)

    def test_logs_today_only_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            runs = self._setup(td)
            cfg = {"paths": {"runs_dir": runs}}
            rc, out = _capture(studio.cmd_logs, cfg, today=True)
            self.assertEqual(rc, 0)
            self.assertIn("anza", out)
            self.assertNotIn("hamati", out)

    def test_logs_all_days(self):
        with tempfile.TemporaryDirectory() as td:
            runs = self._setup(td)
            cfg = {"paths": {"runs_dir": runs}}
            rc, out = _capture(studio.cmd_logs, cfg, today=False)
            self.assertEqual(rc, 0)
            self.assertIn("anza", out)
            self.assertIn("hamati", out)
            self.assertIn("فشل", out)


class TestQueueImportCmd(unittest.TestCase):
    def _setup(self, td):
        # ملف النص يجب أن يكون داخل ~/workspace (قيد الأمان).
        # المجلد الأب قد لا يوجد (CI: بلا ~/workspace) فيُنشأ أولًا.
        os.makedirs(os.path.expanduser("~/workspace"), exist_ok=True)
        ws_tmp = tempfile.mkdtemp(prefix=".test-qi-",
                                  dir=os.path.expanduser("~/workspace"))
        self.addCleanup(shutil.rmtree, ws_tmp, True)
        text_path = os.path.join(ws_tmp, "story.txt")
        Path(text_path).write_text(
            "\n".join(SENTENCE for _ in range(30)), encoding="utf-8")
        queue_path = os.path.join(td, "story-queue.md")
        return queue_path, text_path

    def test_import_command_adds_parts(self):
        with tempfile.TemporaryDirectory() as td:
            queue_path, text_path = self._setup(td)
            cfg = {"paths": {"queue_file": queue_path}}
            with mock.patch.object(studio, "STUDIO_DIR", td):
                rc, out = _capture(studio.cmd_queue_import, cfg,
                                   text_path, "قصة تجريبية",
                                   start="2026-11-23")
            self.assertEqual(rc, 0)
            self.assertIn("أجزاء", out)
            content = Path(queue_path).read_text(encoding="utf-8")
            self.assertIn("**قصة تجريبية — الجزء 1**", content)
            self.assertIn("2026-11-23 09:00", content)

    def test_import_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            queue_path, text_path = self._setup(td)
            cfg = {"paths": {"queue_file": queue_path}}
            with mock.patch.object(studio, "STUDIO_DIR", td):
                rc, _o = _capture(studio.cmd_queue_import, cfg,
                                  text_path, "قصة مكررة")
                self.assertEqual(rc, 0)
                rc, _o = _capture(studio.cmd_queue_import, cfg,
                                  text_path, "قصة مكررة")
            self.assertEqual(rc, 1)

    def test_import_bad_start_date(self):
        with tempfile.TemporaryDirectory() as td:
            queue_path, text_path = self._setup(td)
            cfg = {"paths": {"queue_file": queue_path}}
            rc, _o = _capture(studio.cmd_queue_import, cfg, text_path,
                              "عنوان", start="not-a-date")
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
