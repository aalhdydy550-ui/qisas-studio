#!/usr/bin/env python3
"""اختبارات توصيل أوامر الجولة 9 (v0.1.35) — مستوى CLI.

تتحقق أن التوصيل في studio.py يعمل فعليًا لكل فكرة:
`check --captions`، و`script` مع publish_meta، و`ab --variants`،
و`analyze --dna --reference`، و`schedule --watch` (تجريبي).
بلا نشر حقيقي وبلا لمس المنشورات المجدولة أو الطابور الحقيقي
أو بيانات العملاء؛ والشبكة محاكاة حيث يلزم (OmniRoute).
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.expanduser("~/workspace/videos/demo-20261122-130448.mp4")
NAJJAR = os.path.expanduser("~/workspace/videos/najjar-full-fixed.mp4")
SUBS_DIR = os.path.expanduser("~/workspace/videos/subs")
MORAL = "الظلم مهما طال ليله، الحق بيظهر."
QUESTION = "لو كنت مكانه، كنت عملت إيه؟"


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "studio.py"] + list(args), cwd=STUDIO_DIR,
        capture_output=True, text=True, timeout=300)


class TestCheckCaptionsWiring(unittest.TestCase):
    def test_check_captions_real_subs_pass(self):
        proc = _run_cli("check", "--video", DEMO, "--captions", SUBS_DIR)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("تدقيق تشكيل الكابشن", proc.stdout)
        self.assertIn("لا مشاكل تشكيل", proc.stdout)

    def test_check_captions_broken_fails(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(SUBS_DIR, "najjar-scene1.ass")
            with open(src, encoding="utf-8") as f:
                text = f.read()
            broken = text.replace("عم حسن", "عم حس�ن", 1)
            self.assertIn("�", broken)
            dst = os.path.join(td, "broken.ass")
            with open(dst, "w", encoding="utf-8") as f:
                f.write(broken)
            proc = _run_cli("check", "--video", DEMO, "--captions", td)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("replacement_char", proc.stdout)


class TestScriptMetaWiring(unittest.TestCase):
    def _cfg(self):
        return {"omniroute": {"model": "x", "fallback_model": None,
                              "base_url": "http://127.0.0.1:1",
                              "retries": 0, "retry_delay_seconds": 0}}

    def test_script_llm_meta_saved(self):
        with tempfile.TemporaryDirectory() as td:
            chat = mock.Mock(side_effect=[
                ("عنوان تجريبي\nكابشن تجريبي", "ddgw", "m"),
                ("وصف من جملتين عن القصة.\n#قصص_وعبر #قصص_واقعية",
                 "ddgw", "m"),
            ])
            with mock.patch.object(studio.omniroute_client, "chat", chat):
                result, _ = studio.cmd_script(
                    self._cfg(), "anza", True, run_dir=td)
            meta = result.get("publish_meta")
            self.assertIsNotNone(meta)
            self.assertEqual(meta["source"], "omniroute")
            self.assertIn("وصف من جملتين", meta["description"])
            self.assertIn("#قصص_وعبر", meta["hashtags"])
            with open(os.path.join(td, "script-ai.json"),
                      encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(saved["publish_meta"], meta)

    def test_script_fallback_meta_local(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(
                    studio.omniroute_client, "chat",
                    side_effect=studio.omniroute_client.OmniRouteError(
                        "بلا شبكة")):
                result, _ = studio.cmd_script(
                    self._cfg(), "anza", True, run_dir=td)
            meta = result.get("publish_meta")
            self.assertIsNotNone(meta)
            self.assertEqual(meta["source"], "local")
            self.assertTrue(meta["description"].endswith(
                "وهنحكيها باسمك أو بدون اسم."))
            self.assertIn("#قصص_وعبر", meta["hashtags"])


class TestAbVariantsWiring(unittest.TestCase):
    def test_ab_variants_ranked_with_winner(self):
        with tempfile.TemporaryDirectory() as td:
            hooks_text = (
                "رجل فقير لقى صرة دهب جوّا باب قديم — والنهاية صادمة\n"
                "ليه النجار الفقير رفض ياخد الدهب؟\n"
                "صرة دهب في باب قديم غيّرت حياة نجار فقير")
            chat = mock.Mock(
                return_value=(hooks_text, "ddgw", "m"))
            cfg = {"paths": {"runs_dir": td},
                   "omniroute": {"model": "x", "fallback_model": None,
                                 "base_url": "http://127.0.0.1:1",
                                 "retries": 0, "retry_delay_seconds": 0}}
            with mock.patch.object(studio.omniroute_client, "chat", chat):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = studio._cmd_ab_variants(
                        cfg, DEMO, None, None, "demo", td, 20, 3)
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("الفائز (أعلى درجة DNA)", out)
            records = []
            for root, _dirs, files in os.walk(td):
                for f in files:
                    if f.startswith("ab-") and f.endswith(".json"):
                        records.append(os.path.join(root, f))
            self.assertEqual(len(records), 1)
            with open(records[0], encoding="utf-8") as f:
                record = json.load(f)
            scores = [v["dna_score"] for v in record["variants"]]
            self.assertEqual(scores, sorted(scores, reverse=True))
            self.assertEqual(record["best"],
                             record["variants"][0]["hook"])
            self.assertIn("hook_a", record)
            self.assertIn("hook_b", record)
            self.assertEqual(
                record["cost_estimate_units"]["total"], 60)

    def test_ab_variants_two_cli_uses_legacy_path(self):
        with tempfile.TemporaryDirectory() as td:
            proc = _run_cli("ab", "--video", DEMO,
                            "--hook-a", "رجل فقير لقى صرة دهب جوّا باب قديم",
                            "--hook-b", "ليه النجار رفض ياخد الدهب؟",
                            "--variants", "2", "--out-dir", td)
            self.assertEqual(proc.returncode, 0,
                             proc.stdout + proc.stderr)
            self.assertIn("نسخة أ", proc.stdout)


class TestAnalyzeReferenceWiring(unittest.TestCase):
    def test_dna_reference_proposal_printed(self):
        with tempfile.TemporaryDirectory() as td:
            story_path = os.path.join(td, "story.txt")
            with open(story_path, "w", encoding="utf-8") as f:
                f.write("قصة نجار فقير لقى صرة دهب جوّا باب قديم، "
                        "ورفض ياخدها ورجعها لصاحبها، فعوّضه الله "
                        "أضعافًا. العبرة: الأمانة طريق الغنى الحقيقي.")
            cfg = {"publish": {}, "paths": {"runs_dir": td}}
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = studio.cmd_analyze_dna(
                    cfg, video=DEMO, reference=NAJJAR,
                    new_story_path=story_path)
            self.assertEqual(rc, 0)
            self.assertIn("== اقتراح إعادة بناء ==", buf.getvalue())
            # انحدار: ملف القصة الجديدة يُقرأ فعلًا (لا «غير مقاس») —
            # «العبرة» في آخر ثلث النص فمعيار العائد محقق.
            self.assertIn("معيار العائد محقق", buf.getvalue())

    def test_payoff_keyword_harvest(self):
        # انحدار: «من زرع الخير حصده» عبرة ختام حقيقية — كلمة
        # «حصد» تُحتسب في معيار العائد (score_hook والاقتراح).
        res = studio.dna_lib.score_hook(
            "ليه النجار رفض ياخد الدهب؟",
            story_text="باع بقرته ووزع البذور. جاء المطر فأنبتت "
                       "الأرض ضعف ما أنبتت. فقال جيرانه: "
                       "من زرع الخير حصده.")
        self.assertEqual(res["breakdown"]["payoff"], 1)

    def test_dna_reference_missing_new_story_file(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = {"publish": {}, "paths": {"runs_dir": td}}
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = studio.cmd_analyze_dna(
                    cfg, video=DEMO, reference=NAJJAR,
                    new_story_path=os.path.join(td, "nope.txt"))
            self.assertEqual(rc, 1)
            self.assertIn("تعذرت قراءة ملف نص القصة الجديدة",
                          buf.getvalue())


class TestScheduleWatchWiring(unittest.TestCase):
    def test_schedule_watch_dry_run_cli(self):
        proc = _run_cli(
            "schedule", "--watch", "--post-id", "122132235897269645",
            "--story", "anza", "--slot", "morning",
            "--moral", MORAL, "--question", QUESTION)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("وضع تجريبي", proc.stdout)
        self.assertIn(MORAL, proc.stdout)
        self.assertIn(QUESTION, proc.stdout)


if __name__ == "__main__":
    unittest.main()
