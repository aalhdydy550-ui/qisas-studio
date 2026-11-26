#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات بوابة السكريبت `lib/script_check.py` (جولة v0.1.58، W4)."""
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from lib import script_check
from lib.script_check import ScriptCheckError


def valid_script():
    """سكريبت سليم كامل: هوك قوي، عبرة، سؤال ختامي، 6 مشاهد."""
    return {
        "title": "أخي سرق ميراثي",
        "hook": "ليه أخي سرق ميراثي؟ انكشف السر بعد عشر سنين!",
        "text": (
            "أخي وقّعني على ورقة وأنا مش عارفة إنها تنازل عن الميراث. "
            "صبرت ثلاث سنين والناس كلها شايفة وساكتة. "
            "وفي يوم لقيت الورقة الأصلية في درج قديم. "
            "الورقة أثبتت إن التوقيع مزوّر. "
            "رجّع أخي كل حاجة واعتذر قدام العيلة كلها. "
            "العبرة: الظلم مهما طال ليله، الحق بيظهر في الآخر."),
        "moral": "الظلم مهما طال ليله، الحق بيظهر.",
        "closing_question": "لو كنت مكانه، كنت هتعمل إيه؟",
        "parts": 1,
        "scenes": [
            "أخي وقّعني على ورقة تنازل عن الميراث.",
            "صبرت ثلاث سنين والناس شايفة وساكتة.",
            "لقيت الورقة الأصلية في درج قديم.",
            "الورقة أثبتت إن التوقيع مزوّر.",
            "رجّع أخي كل حاجة واعتذر.",
            "العبرة: الظلم مهما طال ليله، الحق بيظهر.",
        ],
    }


def timed_50s():
    """عبارات موقوتة تمتد 50 ثانية (ضمن 40–60)."""
    return [{"start": 0.0, "end": 25.0},
            {"start": 25.0, "end": 50.0}]


def check_named(result, name):
    for check in result["checks"]:
        if check["name"] == name:
            return check
    raise AssertionError("لا فحص باسم %s" % name)


def issue_ids(result):
    return [i["id"] for i in result["issues"]]


class TestValidScript(unittest.TestCase):
    def test_valid_script_passes(self):
        result = script_check.check_script(valid_script())
        self.assertTrue(result["ok"])
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["scene_count"], 6)
        self.assertEqual(result["scene_source"], "مشاهد معلنة")
        self.assertGreaterEqual(result["hook_score"]["total"], 6)
        self.assertIsNone(result["estimated_duration_seconds"])
        self.assertIsNone(result["duration_source"])
        duration = check_named(result, "المدة المقدّرة")
        self.assertIsNone(duration["ok"])
        self.assertIn("غير مقاسة", duration["detail"])

    def test_valid_script_with_timed_phrases_50s(self):
        result = script_check.check_script(
            valid_script(), timed_phrases=timed_50s())
        self.assertTrue(result["ok"])
        self.assertEqual(result["estimated_duration_seconds"], 50.0)
        self.assertEqual(result["duration_source"], "timed_phrases")
        self.assertTrue(check_named(result, "المدة المقدّرة")["ok"])

    def test_scene_count_from_text_when_no_scenes(self):
        script = valid_script()
        del script["scenes"]
        result = script_check.check_script(script)
        self.assertTrue(result["ok"])
        self.assertEqual(result["scene_count"], 6)
        self.assertEqual(result["scene_source"], "جمل النص")

    def test_duration_from_caller_wpm(self):
        script = valid_script()
        words = len(script["text"].split())
        # معدل يجعل المدة 50 ثانية بالضبط: كلمة/دقيقة = كلمات × 60 / 50.
        wpm = words * 60.0 / 50.0
        result = script_check.check_script(script, narration_wpm=wpm)
        self.assertTrue(result["ok"])
        self.assertAlmostEqual(result["estimated_duration_seconds"],
                               50.0, places=1)
        self.assertEqual(result["duration_source"], "narration_wpm")

    def test_duration_out_of_range_fails(self):
        result = script_check.check_script(
            valid_script(),
            timed_phrases=[{"start": 0.0, "end": 75.0}])
        self.assertFalse(result["ok"])
        self.assertFalse(check_named(result, "المدة المقدّرة")["ok"])
        self.assertEqual(result["estimated_duration_seconds"], 75.0)
        self.assertIn("SC-DURATION-001", issue_ids(result))


class TestHook(unittest.TestCase):
    def test_weak_hook_fails(self):
        script = valid_script()
        script["hook"] = "كان يا ما كان في رجل طيب."
        result = script_check.check_script(script)
        self.assertFalse(result["ok"])
        hook = check_named(result, "الهوك")
        self.assertFalse(hook["ok"])
        self.assertLess(result["hook_score"]["total"], 6)
        self.assertIn("SC-HOOK-001", issue_ids(result))

    def test_hook_starting_with_digit_fails(self):
        script = valid_script()
        script["hook"] = "3 أخطاء دمّرت بيته وقلبت حياته!"
        result = script_check.check_script(script)
        self.assertFalse(result["ok"])
        self.assertFalse(check_named(result, "الهوك")["ok"])
        self.assertIn("SC-HOOK-002", issue_ids(result))

    def test_hook_too_long_fails(self):
        script = valid_script()
        script["hook"] = ("ليه أخي سرق ميراثي وانكشف السر بعد عشر "
                          "سنين طويلة من الصبر والظلم والدموع "
                          "والانتظار والخوف والندم والرجوع للحق "
                          "والاعتذار أمام العائلة كلها يا جماعة؟")
        self.assertGreater(len(script["hook"]), 140)
        result = script_check.check_script(script)
        self.assertFalse(result["ok"])
        self.assertIn("SC-HOOK-003", issue_ids(result))


class TestMoralAndQuestion(unittest.TestCase):
    def test_missing_moral_fails(self):
        script = valid_script()
        script["moral"] = ""
        result = script_check.check_script(script)
        self.assertFalse(result["ok"])
        self.assertFalse(check_named(result, "العبرة")["ok"])
        self.assertIn("SC-MORAL-001", issue_ids(result))

    def test_missing_moral_key_fails(self):
        script = valid_script()
        del script["moral"]
        result = script_check.check_script(script)
        self.assertFalse(result["ok"])
        self.assertIn("SC-MORAL-001", issue_ids(result))

    def test_missing_closing_question_fails(self):
        script = valid_script()
        script["closing_question"] = ""
        result = script_check.check_script(script)
        self.assertFalse(result["ok"])
        self.assertFalse(check_named(result, "سؤال الختام")["ok"])
        self.assertIn("SC-QUESTION-001", issue_ids(result))

    def test_closing_statement_not_question_fails(self):
        script = valid_script()
        script["closing_question"] = "هذه كانت قصتنا اليوم."
        result = script_check.check_script(script)
        self.assertFalse(result["ok"])
        self.assertIn("SC-QUESTION-001", issue_ids(result))


class TestScenes(unittest.TestCase):
    def test_too_few_scenes_fails(self):
        script = valid_script()
        script["scenes"] = script["scenes"][:3]
        result = script_check.check_script(script)
        self.assertFalse(result["ok"])
        scene = check_named(result, "عدد المشاهد")
        self.assertFalse(scene["ok"])
        self.assertEqual(result["scene_count"], 3)
        self.assertIn("SC-SCENES-001", issue_ids(result))

    def test_too_many_scenes_fails(self):
        script = valid_script()
        script["scenes"] = script["scenes"] + [
            "مشهد زائد أول.", "مشهد زائد ثانٍ."]
        result = script_check.check_script(script)
        self.assertFalse(result["ok"])
        self.assertEqual(result["scene_count"], 8)
        self.assertIn("SC-SCENES-001", issue_ids(result))


class TestFollowGateAndMusic(unittest.TestCase):
    def test_follow_gate_fails(self):
        script = valid_script()
        script["text"] = (
            "أخي وقّعني على ورقة تنازل عن الميراث. "
            "لو عايز الجزء الثاني اعمل متابعة. "
            "صبرت ثلاث سنين والناس كلها شايفة وساكتة. "
            "وفي يوم لقيت الورقة الأصلية في درج قديم. "
            "الورقة أثبتت إن التوقيع مزوّر. "
            "العبرة: الظلم مهما طال ليله، الحق بيظهر في الآخر.")
        result = script_check.check_script(script)
        self.assertFalse(result["ok"])
        self.assertFalse(check_named(result, "بوابة المتابعة")["ok"])
        self.assertIn("SC-FOLLOW-001", issue_ids(result))

    def test_approved_gentle_invite_passes(self):
        script = valid_script()
        script["text"] = valid_script()["text"] + (
            " الجزء الثاني بكرة 7 مساءً — اعمل متابعة عشان "
            "يوصلك أول ما ينزل.")
        result = script_check.check_script(script)
        self.assertTrue(check_named(result, "بوابة المتابعة")["ok"])
        self.assertTrue(result["ok"])

    def test_music_mention_fails(self):
        script = valid_script()
        script["text"] = valid_script()["text"] + (
            " وتُعزف موسيقى تصويرية حزينة في الخلفية.")
        result = script_check.check_script(script)
        self.assertFalse(result["ok"])
        self.assertFalse(check_named(result, "الموسيقى")["ok"])
        self.assertIn("SC-MUSIC-001", issue_ids(result))


class TestParts(unittest.TestCase):
    def test_middle_part_ending_with_resolution_fails(self):
        script = valid_script()
        script["parts"] = 2
        script["part_endings"] = [
            "وفي النهاية تاب أخي وعرف خطأه، والعبرة أن الظلم لا يدوم.",
            "رجّع أخي كل حاجة واعتذر قدام العيلة كلها.",
        ]
        result = script_check.check_script(script)
        self.assertFalse(result["ok"])
        self.assertFalse(check_named(result, "نهايات الأجزاء")["ok"])
        self.assertIn("SC-PARTS-001", issue_ids(result))

    def test_middle_part_ending_with_hook_passes(self):
        script = valid_script()
        script["parts"] = [
            {"text": "أخي وقّعني على ورقة تنازل. تفتكروا إيه اللي "
                     "حصل بعدها؟"},
            {"text": "رجّع أخي كل حاجة واعتذر. العبرة: الظلم لا يدوم."},
        ]
        result = script_check.check_script(script)
        self.assertTrue(check_named(result, "نهايات الأجزاء")["ok"])
        self.assertTrue(result["ok"])

    def test_parts_without_endings_is_unmeasured_and_fails(self):
        script = valid_script()
        script["parts"] = 2
        result = script_check.check_script(script)
        self.assertFalse(result["ok"])
        self.assertFalse(check_named(result, "نهايات الأجزاء")["ok"])
        self.assertIn("SC-PARTS-002", issue_ids(result))

    def test_single_part_needs_no_endings(self):
        result = script_check.check_script(valid_script())
        self.assertTrue(check_named(result, "نهايات الأجزاء")["ok"])


class TestInvalidInput(unittest.TestCase):
    def test_non_dict_raises(self):
        with self.assertRaises(ScriptCheckError):
            script_check.check_script("not a dict")

    def test_empty_script_raises(self):
        with self.assertRaises(ScriptCheckError):
            script_check.check_script({})

    def test_missing_hook_raises(self):
        script = valid_script()
        del script["hook"]
        with self.assertRaises(ScriptCheckError):
            script_check.check_script(script)

    def test_empty_text_raises(self):
        script = valid_script()
        script["text"] = "   "
        with self.assertRaises(ScriptCheckError):
            script_check.check_script(script)

    def test_parts_wrong_type_raises(self):
        script = valid_script()
        script["parts"] = "two"
        with self.assertRaises(ScriptCheckError):
            script_check.check_script(script)

    def test_parts_zero_raises(self):
        script = valid_script()
        script["parts"] = 0
        with self.assertRaises(ScriptCheckError):
            script_check.check_script(script)

    def test_scenes_wrong_type_raises(self):
        script = valid_script()
        script["scenes"] = "not a list"
        with self.assertRaises(ScriptCheckError):
            script_check.check_script(script)

    def test_bad_timed_phrase_raises(self):
        with self.assertRaises(ScriptCheckError):
            script_check.check_script(
                valid_script(),
                timed_phrases=[{"start": 10.0, "end": 5.0}])

    def test_missing_narration_audio_raises(self):
        with self.assertRaises(ScriptCheckError):
            script_check.check_script(
                valid_script(), narration_audio="/tmp/no-such-file.wav")

    def test_load_bad_json_file_raises(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False,
                encoding="utf-8") as f:
            f.write("{not json")
            path = f.name
        try:
            with self.assertRaises(ScriptCheckError):
                script_check.load_script_file(path)
        finally:
            os.unlink(path)

    def test_load_non_dict_json_raises(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False,
                encoding="utf-8") as f:
            json.dump([1, 2, 3], f)
            path = f.name
        try:
            with self.assertRaises(ScriptCheckError):
                script_check.load_script_file(path)
        finally:
            os.unlink(path)


class TestReportAndCli(unittest.TestCase):
    def _write_script(self, script):
        tmp = tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(script, tmp, ensure_ascii=False)
        tmp.close()
        self.addCleanup(os.unlink, tmp.name)
        return tmp.name

    def test_format_report_arabic(self):
        result = script_check.check_script(valid_script())
        report = script_check.format_report(result)
        self.assertIn("فحص السكريبت", report)
        self.assertIn("سليم", report)
        self.assertIn("أخي سرق ميراثي", report)
        bad = script_check.check_script(
            {**valid_script(), "moral": ""})
        self.assertIn("غير سليم", script_check.format_report(bad))
        self.assertIn("SC-MORAL-001", script_check.format_report(bad))

    def test_to_json_is_pure_json(self):
        result = script_check.check_script(valid_script())
        parsed = json.loads(script_check.to_json(result))
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["title"], "أخي سرق ميراثي")

    def test_cmd_returns_0_for_valid(self):
        path = self._write_script(valid_script())
        args = Namespace(script=path, json=False,
                         timed_phrases=None, narration_audio=None,
                         narration_wpm=None, narration_duration=None)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = script_check.cmd_script_check(args)
        self.assertEqual(code, 0)
        self.assertIn("سليم", buf.getvalue())

    def test_cmd_returns_1_for_bad_report(self):
        path = self._write_script({**valid_script(), "moral": ""})
        args = Namespace(script=path, json=False,
                         timed_phrases=None, narration_audio=None,
                         narration_wpm=None, narration_duration=None)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = script_check.cmd_script_check(args)
        self.assertEqual(code, 1)

    def test_cmd_returns_2_for_invalid_input(self):
        args = Namespace(script="/tmp/no-such-script.json", json=False,
                         timed_phrases=None, narration_audio=None,
                         narration_wpm=None, narration_duration=None)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = script_check.cmd_script_check(args)
        self.assertEqual(code, 2)

    def test_main_json_output_is_pure_json(self):
        path = self._write_script(valid_script())
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = script_check.main([path, "--json"])
        self.assertEqual(code, 0)
        parsed = json.loads(buf.getvalue())
        self.assertTrue(parsed["ok"])

    def test_main_exit_1_for_bad_report(self):
        path = self._write_script({**valid_script(), "moral": ""})
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = script_check.main([path])
        self.assertEqual(code, 1)

    def test_main_exit_2_for_missing_file(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = script_check.main(["/tmp/no-such-script.json"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
