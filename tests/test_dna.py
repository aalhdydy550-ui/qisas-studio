#!/usr/bin/env python3
"""اختبارات تحليل DNA الفيروسي (lib.dna) — الجولة 7.

تعمل بـ `python3 -m unittest discover -s tests -v`.
درجة الهوك حتمية من إشارات نصية موثقة؛ وكشف القطع على
فيديو اصطناعي من لونين (ffmpeg)؛ وكثافة الكلمات من ملفات
ASS مصطنعة — بلا أي فيديو حقيقي وبلا أي اتصال.
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import dna

STRONG_HOOK = ("ليه الراجل ظلم أخوه 3 مرات؟ مستحيل يفلت — الحقيقة "
               "انكشفت فجأة!")
STORY_TEXT = ("كان فيه راجل ظالم. سرق مال أخوه. أنكر الوصية. "
              "هرب من القرية. العبرة أن الظلم لا يدوم.")
GOOD_HOOK = "ليه الراجل ظلم أخوه؟ الحقيقة انكشفت فجأة!"
WEAK_HOOK = "يا جماعة تعالوا أحكيلكم قصة راجل طيب"


def _make_two_color_video(path):
    """فيديو 6 ثوانٍ: 3ث أحمر ثم 3ث أزرق (قطع واحد عند 3ث)."""
    cmd = ["ffmpeg", "-v", "error",
           "-f", "lavfi", "-i", "color=c=red:s=320x568:d=3",
           "-f", "lavfi", "-i", "color=c=blue:s=320x568:d=3",
           "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0",
           "-y", path]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=120)
    if proc.returncode != 0 or not os.path.isfile(path):
        raise RuntimeError("تعذر بناء الفيديو الاصطناعي: %s"
                           % (proc.stderr or "")[-200:])


def _ass_file(path, start, end, words):
    with open(path, "w", encoding="utf-8") as f:
        f.write("[Script Info]\n[Events]\n")
        f.write("Dialogue: 0,%s,%s,Default,,0,0,0,,%s\n"
                % (start, end, " ".join(["كلمة"] * words)))


class TestScoreHook(unittest.TestCase):
    def test_strong_hook_9(self):
        result = dna.score_hook(STRONG_HOOK, story_text=STORY_TEXT)
        self.assertEqual(result["total"], 9)
        self.assertEqual(result["max"], 10)
        self.assertEqual(result["breakdown"]["curiosity_gap"], 3)
        self.assertEqual(result["breakdown"]["specific_fact"], 1)
        self.assertEqual(result["breakdown"]["conflict"], 2)
        self.assertEqual(result["breakdown"]["direct_entry"], 1)
        self.assertEqual(result["breakdown"]["payoff"], 1)
        self.assertEqual(result["breakdown"]["self_contained"], 1)
        self.assertIn("قوي", result["verdict"])

    def test_good_hook_6_payoff_unmeasured(self):
        result = dna.score_hook(GOOD_HOOK)
        self.assertEqual(result["total"], 6)
        self.assertEqual(result["max"], 9)
        self.assertIsNone(result["breakdown"]["payoff"])
        self.assertIn("جيد", result["verdict"])

    def test_weak_hook_1(self):
        result = dna.score_hook(WEAK_HOOK)
        self.assertEqual(result["total"], 1)
        self.assertIn("ضعيف", result["verdict"])

    def test_empty_hook_error(self):
        with self.assertRaises(dna.DnaError):
            dna.score_hook("   ")

    def test_substring_false_positives(self):
        """انحدار: المطابقة الجزئية كانت تعطي فجوة فضول 3/3
        لهوك بلا أي فجوة — «ليه» داخل «عليه»، و«سر» داخل
        «سريع»، و«مين» داخل «يمين»."""
        result = dna.score_hook("عليه سريع يمين")
        self.assertEqual(result["breakdown"]["curiosity_gap"], 0)
        self.assertEqual(result["total"], 2)
        self.assertIn("ضعيف", result["verdict"])

    def test_conjugated_suspense_matches(self):
        """صيغ مصرّفة تطابق: «انكشفت» = انكشف + ت، و«لكنه» =
        لكن + ه، و«والحقيقة» = و + الحقيقة."""
        result = dna.score_hook("انكشفت الحقيقة فجأة")
        self.assertEqual(result["breakdown"]["curiosity_gap"], 1)
        result2 = dna.score_hook("لكنه ظلم أخوه والحقيقة واضحة")
        self.assertEqual(result2["breakdown"]["conflict"], 1)

    def test_payoff_needs_story_text(self):
        result = dna.score_hook(STRONG_HOOK)
        self.assertIsNone(result["breakdown"]["payoff"])
        self.assertEqual(result["max"], 9)


class TestBuildVerdictSlowPace(unittest.TestCase):
    """انحدار: فرع «بطيء» (متوسط لقطة > 8ث — حالة فيديوهات Veo
    الحقيقية) كان يعطّل build_verdict بـ TypeError."""

    def test_slow_pace_formats(self):
        cuts = {"shot_count": 6, "cuts": [8.0, 16.0, 24.0, 32.0, 40.0],
                "avg_shot_seconds": 8.0, "duration": 48.0}
        # متوسط 8.0 بالضبط = فرع «متوازن»؛ جرّب 9.5 للفرع البطيء.
        cuts["avg_shot_seconds"] = 9.5
        verdict = dna.build_verdict(None, cuts, True,
                                    {"wpm": None, "words": 0},
                                    None, None)
        text = "\n".join(verdict)
        self.assertIn("بطيء", text)
        self.assertIn("9.5", text)
        self.assertIn("6 لقطة", text)
    def test_aisha_part2_maps_to_aisha2_files(self):
        self.assertEqual(
            dna._slug_for_video("/tmp/aisha-part2-main.mp4"), "aisha2")

    def test_aisha_part1_maps_to_aisha1_files(self):
        self.assertEqual(
            dna._slug_for_video("/tmp/aisha-part1-full.mp4"), "aisha1")

    def test_aisha2_attached_digit(self):
        """انحدار: aisha2-full.mp4 (الرقم ملتصق بالحروف بلا
        part) كان يرجع None فتبقى الكثافة «غير مقاسة»."""
        self.assertEqual(
            dna._slug_for_video("/tmp/aisha2-full.mp4"), "aisha2")

    def test_najjar_and_hamati(self):
        self.assertEqual(
            dna._slug_for_video("/tmp/najjar-full.mp4"), "najjar")
        self.assertEqual(
            dna._slug_for_video("/tmp/hamati-full.mp4"), "hamati")

    def test_anza(self):
        self.assertEqual(
            dna._slug_for_video(
                "/tmp/openmontage-anza-part1-fixed.mp4"), "anza")

    def test_unknown_returns_none(self):
        self.assertIsNone(
            dna._slug_for_video("/tmp/demo-20261122-102913.mp4"))


class TestAnalyzeDnaSlug(unittest.TestCase):
    """انحدار: كثافة كلمات عائشة ج2 تُقاس من aisha2-scene*.ass
    رغم أن اسم الفيديو aisha-part2-main.mp4."""

    def test_aisha_density_measured(self):
        with tempfile.TemporaryDirectory() as td:
            subs = os.path.join(td, "subs")
            os.makedirs(subs)
            _ass_file(os.path.join(subs, "aisha2-scene1.ass"),
                      "0:00:01.00", "0:00:05.00", 10)
            video = os.path.join(td, "aisha-part2-main.mp4")
            _make_two_color_video(video)
            report = dna.analyze_dna(
                video, title="عائشة ج2",
                hook="الكاتب باع ضميره… بس الرسالة وصلت لصاحبتها!",
                subs_dir=subs,
                check_fn=lambda v: {"passed": True, "checks": [
                    {"name": "الصمت عند الفواصل", "ok": True,
                     "detail": "لا صمت"}]})
            self.assertEqual(report["word_density"]["words"], 10)
            self.assertEqual(report["word_density"]["files"], 1)
            self.assertIsNotNone(report["word_density"]["wpm"])


class TestWordDensity(unittest.TestCase):
    def test_density_from_ass(self):
        with tempfile.TemporaryDirectory() as td:
            _ass_file(os.path.join(td, "aisha2-scene1.ass"),
                      "0:00:01.00", "0:00:05.00", 10)
            _ass_file(os.path.join(td, "aisha2-scene2.ass"),
                      "0:00:06.00", "0:00:10.00", 10)
            result = dna.word_density(
                os.path.join(td, "aisha-part2-main.mp4"),
                subs_dir=td, slug="aisha2")
            self.assertEqual(result["words"], 20)
            self.assertEqual(result["files"], 2)
            # ملفان × 4 ثوانٍ لكل منهما = 8 ثوانٍ؛ 20 كلمة = 150
            # كلمة/دقيقة (الزمن مجموع أزمنة الملفات لا الفرق بين
            # أول بداية وآخر نهاية — خطوط زمنية محلية لكل مشهد).
            self.assertAlmostEqual(result["wpm"], 150.0, places=1)

    def test_density_no_ass(self):
        with tempfile.TemporaryDirectory() as td:
            result = dna.word_density(
                os.path.join(td, "video.mp4"), subs_dir=td)
            self.assertIsNone(result["wpm"])
            self.assertEqual(result["words"], 0)


class TestDetectCuts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.video = os.path.join(cls.tmp.name, "two-color.mp4")
        try:
            _make_two_color_video(cls.video)
        except RuntimeError as e:
            cls.tmp.cleanup()
            raise unittest.SkipTest(str(e))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_two_shots(self):
        result = dna.detect_cuts(self.video)
        self.assertEqual(result["shot_count"], 2)
        self.assertEqual(len(result["cuts"]), 1)
        self.assertAlmostEqual(result["cuts"][0], 3.0, delta=0.2)
        self.assertAlmostEqual(result["avg_shot_seconds"], 3.0,
                               delta=0.2)

    def test_missing_video(self):
        with self.assertRaises(dna.DnaError):
            dna.detect_cuts("/tmp/no-such-video-xyz.mp4")


class TestAnalyzeDna(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.video = os.path.join(cls.tmp.name, "two-color.mp4")
        try:
            _make_two_color_video(cls.video)
        except RuntimeError as e:
            cls.tmp.cleanup()
            raise unittest.SkipTest(str(e))
        cls.subs = os.path.join(cls.tmp.name, "subs")
        os.makedirs(cls.subs)
        _ass_file(os.path.join(cls.subs, "aisha2-scene1.ass"),
                  "0:00:01.00", "0:00:05.00", 10)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _fake_check(self, video):
        return {"passed": True, "checks": [
            {"name": "الصمت عند الفواصل", "ok": True,
             "detail": "لا صمت ≥1 ثانية في منتصف الفيديو"}]}

    def test_report_keys(self):
        report = dna.analyze_dna(
            self.video, title="اختبار", hook=GOOD_HOOK,
            subs_dir=self.subs, check_fn=self._fake_check)
        self.assertEqual(report["hook"]["total"], 6)
        self.assertEqual(report["pacing"]["shot_count"], 2)
        self.assertTrue(report["silence"]["ok"])
        self.assertEqual(report["word_density"]["words"], 10)
        self.assertTrue(report["verdict"])

    def test_format_report(self):
        report = dna.analyze_dna(
            self.video, title="اختبار", hook=GOOD_HOOK,
            subs_dir=self.subs, check_fn=self._fake_check)
        text = dna.format_report(report)
        self.assertIn("تحليل DNA", text)
        self.assertIn("6/9", text)
        self.assertIn("الإيقاع", text)

    def test_silence_unmeasured_not_none(self):
        """انحدار: فحص بلا نتيجة «الصمت عند الفواصل» كان
        يطبع None حرفيًا في التقرير."""
        report = dna.analyze_dna(
            self.video, title="اختبار", hook=GOOD_HOOK,
            subs_dir=self.subs,
            check_fn=lambda v: {"passed": True, "checks": []})
        self.assertIsNone(report["silence"]["ok"])
        self.assertIn("غير مقاس", report["silence"]["detail"])
        text = dna.format_report(report)
        self.assertNotIn("None", text)
        self.assertIn("غير مقاس", text)

    def test_save_report(self):
        runs = os.path.join(self.tmp.name, "runs")
        report = dna.analyze_dna(
            self.video, title="اختبار", hook=GOOD_HOOK,
            subs_dir=self.subs, check_fn=self._fake_check)
        path = dna.save_report(report, runs)
        self.assertTrue(os.path.isfile(path))
        self.assertTrue(path.endswith(".json"))


if __name__ == "__main__":
    unittest.main()
