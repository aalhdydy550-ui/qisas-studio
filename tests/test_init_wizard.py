#!/usr/bin/env python3
"""اختبارات معالج الإعداد (lib.init_wizard).

تعمل بـ `python3 -m unittest discover -s tests -v`.
كل الكتابة في مجلدات مؤقتة — لا يُمس config.yaml الحقيقي
ولا ملف الطابور الحقيقي أبدًا.
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import init_wizard

BASE_CFG = {
    "publish": {"page_id": "", "youtube_channel_id": ""},
    "paths": {"queue_file": "~/workspace/queue.md",
              "videos_dir": "~/workspace/videos"},
    "schedule": {"morning": "09:00", "evening": "19:00"},
    "narration": {"voice": "piper"},
}


def _read_yaml(path):
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestValidation(unittest.TestCase):
    def test_valid_times(self):
        self.assertEqual(init_wizard.validate_time("09:00"), "09:00")
        self.assertEqual(init_wizard.validate_time("19:30"), "19:30")
        self.assertEqual(init_wizard.validate_time("00:00"), "00:00")

    def test_invalid_times(self):
        for bad in ("25:00", "9:00", "09:60", "صباحًا", "", "09-00"):
            with self.assertRaises(init_wizard.InitError, msg=bad):
                init_wizard.validate_time(bad)

    def test_page_id(self):
        self.assertEqual(init_wizard.validate_page_id("1048148471706586"),
                         "1048148471706586")
        self.assertEqual(init_wizard.validate_page_id(""), "")
        with self.assertRaises(init_wizard.InitError):
            init_wizard.validate_page_id("abc123")

    def test_voice(self):
        self.assertEqual(init_wizard.validate_voice("piper"), "piper")
        self.assertEqual(init_wizard.validate_voice("GTTS"), "gtts")
        with self.assertRaises(init_wizard.InitError):
            init_wizard.validate_voice("female")


class TestApplyAnswers(unittest.TestCase):
    def test_applies_all_fields(self):
        cfg = init_wizard.apply_answers(BASE_CFG, {
            "page_id": "123", "channel_id": "UCxxxx",
            "queue_file": "/tmp/q.md", "morning": "08:30",
            "evening": "20:00", "voice": "gtts"})
        self.assertEqual(cfg["publish"]["page_id"], "123")
        self.assertEqual(cfg["publish"]["youtube_channel_id"], "UCxxxx")
        self.assertEqual(cfg["paths"]["queue_file"], "/tmp/q.md")
        self.assertEqual(cfg["schedule"]["morning"], "08:30")
        self.assertEqual(cfg["schedule"]["evening"], "20:00")
        self.assertEqual(cfg["narration"]["voice"], "gtts")

    def test_partial_answers_keep_rest(self):
        cfg = init_wizard.apply_answers(BASE_CFG, {"page_id": "999"})
        self.assertEqual(cfg["publish"]["page_id"], "999")
        self.assertEqual(cfg["schedule"]["morning"], "09:00")
        self.assertEqual(cfg["narration"]["voice"], "piper")

    def test_invalid_answer_raises(self):
        with self.assertRaises(init_wizard.InitError):
            init_wizard.apply_answers(BASE_CFG, {"morning": "99:99"})


class TestRunWizard(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="init-test-")
        self.cfg_path = os.path.join(self.td, "config.yaml")
        self.noop = lambda *a: None

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_writes_config_and_crons_non_interactive(self):
        rc = init_wizard.run_wizard(
            BASE_CFG, self.cfg_path,
            flags={"page_id": "123", "channel_id": "UCx",
                   "morning": "08:00", "evening": "18:00",
                   "voice": "piper",
                   "queue_file": os.path.join(self.td, "q.md")},
            print_fn=self.noop)
        self.assertEqual(rc, 0)
        cfg = _read_yaml(self.cfg_path)
        self.assertEqual(cfg["publish"]["page_id"], "123")
        self.assertEqual(cfg["publish"]["youtube_channel_id"], "UCx")
        self.assertEqual(cfg["schedule"]["morning"], "08:00")
        self.assertEqual(cfg["narration"]["voice"], "piper")
        crons = os.path.join(self.td, "suggested-crons.md")
        self.assertTrue(os.path.isfile(crons))
        text = Path(crons).read_text(encoding="utf-8")
        self.assertIn("08:00", text)
        self.assertIn("18:00", text)
        self.assertIn("long-video --auto-week", text)
        self.assertIn("لم تُثبَّت", text)

    def test_refuses_overwrite_without_force(self):
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write("قديم\n")
        rc = init_wizard.run_wizard(
            BASE_CFG, self.cfg_path, flags={"page_id": "123"},
            print_fn=self.noop)
        self.assertEqual(rc, 1)
        self.assertEqual(
            Path(self.cfg_path).read_text(encoding="utf-8"), "قديم\n")

    def test_force_overwrites(self):
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write("قديم\n")
        rc = init_wizard.run_wizard(
            BASE_CFG, self.cfg_path, flags={"page_id": "123"},
            force=True, print_fn=self.noop)
        self.assertEqual(rc, 0)
        cfg = _read_yaml(self.cfg_path)
        self.assertEqual(cfg["publish"]["page_id"], "123")

    def test_interactive_flow_writes_answers(self):
        answers = iter(["555", "UCy", "piper", "07:30", "21:00",
                        os.path.join(self.td, "q.md")])

        def fake_input(prompt=""):
            return next(answers)

        rc = init_wizard.run_wizard(
            BASE_CFG, self.cfg_path, flags=None,
            input_fn=fake_input, print_fn=self.noop)
        self.assertEqual(rc, 0)
        cfg = _read_yaml(self.cfg_path)
        self.assertEqual(cfg["publish"]["page_id"], "555")
        self.assertEqual(cfg["schedule"]["morning"], "07:30")
        self.assertEqual(cfg["schedule"]["evening"], "21:00")

    def test_interactive_overwrite_decline_keeps_file(self):
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write("قديم\n")
        answers = iter(["555", "UCy", "piper", "07:30", "21:00",
                        os.path.join(self.td, "q.md"), "n"])

        def fake_input(prompt=""):
            return next(answers)

        rc = init_wizard.run_wizard(
            BASE_CFG, self.cfg_path, flags=None,
            input_fn=fake_input, print_fn=self.noop)
        self.assertEqual(rc, 1)
        self.assertEqual(
            Path(self.cfg_path).read_text(encoding="utf-8"), "قديم\n")

    def test_interactive_overwrite_confirm_replaces(self):
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write("قديم\n")
        answers = iter(["555", "UCy", "piper", "07:30", "21:00",
                        os.path.join(self.td, "q.md"), "y"])

        def fake_input(prompt=""):
            return next(answers)

        rc = init_wizard.run_wizard(
            BASE_CFG, self.cfg_path, flags=None,
            input_fn=fake_input, print_fn=self.noop)
        self.assertEqual(rc, 0)
        cfg = _read_yaml(self.cfg_path)
        self.assertEqual(cfg["publish"]["page_id"], "555")


if __name__ == "__main__":
    unittest.main()
