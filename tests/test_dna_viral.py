#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات تقرير Viral DNA المنظّم (lib.dna) — الجولة v0.1.39.

تعمل بـ `python3 -m unittest discover -s tests -v`.
كل المقاييس حتمية من مدخلات مصطنعة (تقارير يدوية + فيديو
لونين بـffmpeg) — بلا أي فيديو حقيقي وبلا أي اتصال.
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
WEAK_HOOK = "يا جماعة تعالوا أحكيلكم قصة راجل طيب"
STORY_TWIST_MORAL = ("كان فيه راجل ظالم. سرق مال أخوه. أنكر الوصية. "
                     "فجأة انكشفت الحقيقة. العبرة أن الظلم لا يدوم.")
STORY_PLAIN = "كان فيه راجل طيب. ساعد جيرانه. عاش في سلام."


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


def _report(hook=None, cuts=None, silence_ok=True, wpm=120.0):
    return {
        "video": "/tmp/video.mp4",
        "duration": 48.0,
        "hook": hook,
        "pacing": cuts or {"shot_count": 6,
                           "cuts": [8.0, 16.0, 24.0, 32.0, 40.0],
                           "avg_shot_seconds": 8.0, "duration": 48.0},
        "silence": {"ok": silence_ok,
                    "detail": "لا صمت" if silence_ok else "صمت 1.5ث"},
        "word_density": {"wpm": wpm, "words": 96, "files": 2,
                         "source": "ass"},
        "verdict": ["حكم تجريبي"],
    }


class TestHookType(unittest.TestCase):
    def test_strong_question_conflict(self):
        t = dna.hook_type(dna.score_hook(STRONG_HOOK,
                                         story_text=STORY_TWIST_MORAL))
        self.assertEqual(t["kind"], "question_conflict")
        self.assertEqual(t["strength"], "قوي")
        self.assertEqual(t["score"], 9)

    def test_weak_hook(self):
        t = dna.hook_type(dna.score_hook(WEAK_HOOK))
        self.assertEqual(t["kind"], "weak")
        self.assertEqual(t["strength"], "ضعيف")

    def test_fact_hook(self):
        t = dna.hook_type(dna.score_hook("الراجل سرق 3 مرات من أخوه"))
        self.assertEqual(t["kind"], "fact")

    def test_suspense_hook(self):
        t = dna.hook_type(dna.score_hook("فجأة انكشفت الحقيقة"))
        self.assertEqual(t["kind"], "suspense")

    def test_none_hook(self):
        self.assertIsNone(dna.hook_type(None))


class TestShotStructure(unittest.TestCase):
    def test_two_equal_shots(self):
        s = dna.analyze_shot_structure(
            {"cuts": [3.0], "duration": 6.0, "shot_count": 2})
        self.assertEqual(s["shots_seconds"], [3.0, 3.0])
        self.assertEqual(s["median_shot_seconds"], 3.0)
        self.assertEqual(s["distribution"],
                         {"short": 2, "medium": 0, "long": 0})

    def test_mixed_distribution(self):
        s = dna.analyze_shot_structure(
            {"cuts": [2.0, 10.0], "duration": 18.0, "shot_count": 3})
        self.assertEqual(s["shots_seconds"], [2.0, 8.0, 8.0])
        self.assertEqual(s["median_shot_seconds"], 8.0)
        self.assertEqual(s["distribution"],
                         {"short": 1, "medium": 2, "long": 0})

    def test_single_long_shot(self):
        s = dna.analyze_shot_structure(
            {"cuts": [], "duration": 48.0, "shot_count": 1})
        self.assertEqual(s["shots_seconds"], [48.0])
        self.assertEqual(s["distribution"],
                         {"short": 0, "medium": 0, "long": 1})
        self.assertEqual(s["median_shot_seconds"], 48.0)

    def test_unmeasured(self):
        s = dna.analyze_shot_structure({})
        self.assertEqual(s["shots_seconds"], [])
        self.assertIsNone(s["median_shot_seconds"])
        self.assertEqual(s["distribution"],
                         {"short": 0, "medium": 0, "long": 0})


class TestPacing(unittest.TestCase):
    def test_fast_balanced_slow(self):
        self.assertEqual(
            dna.analyze_pacing(
                {"cuts": [3.0], "duration": 6.0})["verdict"], "سريع")
        self.assertEqual(
            dna.analyze_pacing(
                {"cuts": [8.0], "duration": 16.0})["verdict"], "متوازن")
        self.assertEqual(
            dna.analyze_pacing(
                {"cuts": [12.0], "duration": 24.0})["verdict"], "بطيء")

    def test_median_not_mean(self):
        """لقطة واحدة طويلة لا تجرّ الوسيط: [2, 2, 30] وسيطها 2
        (سريع) رغم أن متوسطها 11.3."""
        p = dna.analyze_pacing(
            {"cuts": [2.0, 4.0], "duration": 34.0})
        self.assertEqual(p["median_shot_seconds"], 2.0)
        self.assertEqual(p["verdict"], "سريع")

    def test_variance_labels(self):
        even = dna.analyze_pacing({"cuts": [8.0], "duration": 16.0})
        self.assertEqual(even["stdev_shot_seconds"], 0.0)
        self.assertEqual(even["variance_label"], "منتظم")
        wild = dna.analyze_pacing({"cuts": [1.0], "duration": 16.0})
        self.assertEqual(wild["variance_label"], "متباين جدًا")
        self.assertGreater(wild["stdev_shot_seconds"], 4)

    def test_unmeasured(self):
        p = dna.analyze_pacing({})
        self.assertIsNone(p["median_shot_seconds"])
        self.assertEqual(p["verdict"], "غير مقاس")


class TestEmotionalArc(unittest.TestCase):
    def test_twist_and_moral(self):
        arc = dna.analyze_emotional_arc(
            dna.score_hook(STRONG_HOOK, story_text=STORY_TWIST_MORAL),
            STORY_TWIST_MORAL)
        self.assertTrue(arc["twist"])
        self.assertTrue(arc["moral"])
        self.assertEqual(arc["shape"], "تصاعد + انقلاب + عبرة")

    def test_plain_story_no_twist_no_moral(self):
        arc = dna.analyze_emotional_arc(None, STORY_PLAIN)
        self.assertFalse(arc["twist"])
        self.assertFalse(arc["moral"])
        self.assertEqual(arc["shape"], "بلا انقلاب ولا عبرة واضحة في النص")

    def test_no_story_unmeasured(self):
        # بلا نص قصة: العائد غير مقاس فالمجموع 8/9 = «جيد».
        arc = dna.analyze_emotional_arc(
            dna.score_hook(STRONG_HOOK), None)
        self.assertIsNone(arc["twist"])
        self.assertIsNone(arc["moral"])
        self.assertIn("غير مقاس", arc["shape"])
        self.assertIn("جيد", arc["opening"])

    def test_no_hook_opening_unmeasured(self):
        arc = dna.analyze_emotional_arc(None, None)
        self.assertIn("غير مقاس", arc["opening"])


class TestBuildViralDnaReport(unittest.TestCase):
    def test_structure_keys(self):
        viral = dna.build_viral_dna_report(
            _report(hook=dna.score_hook(STRONG_HOOK)),
            story_text=STORY_TWIST_MORAL)
        for key in ("hook", "hook_score", "shot_structure", "pacing",
                    "emotional_arc", "weaknesses"):
            self.assertIn(key, viral)
        self.assertEqual(viral["hook"]["kind"], "question_conflict")
        self.assertEqual(viral["shot_structure"]["shot_count"], 6)
        self.assertEqual(viral["pacing"]["median_shot_seconds"], 8.0)
        self.assertEqual(viral["emotional_arc"]["shape"],
                         "تصاعد + انقلاب + عبرة")

    def test_weaknesses_all_bad(self):
        viral = dna.build_viral_dna_report(_report(
            hook=dna.score_hook(WEAK_HOOK),
            silence_ok=False, wpm=80.0))
        areas = [w["area"] for w in viral["weaknesses"]]
        self.assertIn("الهوك", areas)
        self.assertIn("العائد داخل المقطع", areas)  # بلا نص قصة
        self.assertIn("الصمت", areas)
        self.assertIn("كثافة السرد", areas)
        for w in viral["weaknesses"]:
            self.assertTrue(w["detail"])
            self.assertTrue(w["action"])
            self.assertNotIn("None", w["detail"])

    def test_weaknesses_single_long_shot(self):
        viral = dna.build_viral_dna_report(_report(
            hook=dna.score_hook(STRONG_HOOK, story_text=STORY_TWIST_MORAL),
            cuts={"shot_count": 1, "cuts": [], "avg_shot_seconds": 48.0,
                  "duration": 48.0},
            wpm=120.0), story_text=STORY_TWIST_MORAL)
        areas = [w["area"] for w in viral["weaknesses"]]
        self.assertIn("بنية اللقطات", areas)

    def test_no_hook_weakness(self):
        viral = dna.build_viral_dna_report(_report(hook=None))
        areas = [w["area"] for w in viral["weaknesses"]]
        self.assertIn("الهوك", areas)

    def test_unmeasured_density_weakness(self):
        report = _report(hook=dna.score_hook(
            STRONG_HOOK, story_text=STORY_TWIST_MORAL))
        report["word_density"] = {"wpm": None, "words": 0, "files": 0,
                                  "source": None}
        viral = dna.build_viral_dna_report(
            report, story_text=STORY_TWIST_MORAL)
        areas = [w["area"] for w in viral["weaknesses"]]
        self.assertIn("كثافة السرد", areas)


class TestFormatViralDnaReport(unittest.TestCase):
    def test_all_sections_present(self):
        viral = dna.build_viral_dna_report(
            _report(hook=dna.score_hook(STRONG_HOOK)),
            story_text=STORY_TWIST_MORAL)
        text = dna.format_viral_dna_report(viral)
        for marker in ("تقرير Viral DNA المنظّم", "الهوك:",
                       "بنية اللقطات:", "الإيقاع:",
                       "المنحنى العاطفي:", "نقاط الضعف"):
            self.assertIn(marker, text)
        self.assertNotIn("None", text)

    def test_empty_viral_unmeasured_not_none(self):
        text = dna.format_viral_dna_report({})
        self.assertIn("غير مقاس", text)
        self.assertNotIn("None", text)


class TestAnalyzeDnaIntegration(unittest.TestCase):
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

    def _fake_check(self, video):
        return {"passed": True, "checks": [
            {"name": "الصمت عند الفواصل", "ok": True,
             "detail": "لا صمت ≥1 ثانية في منتصف الفيديو"}]}

    def test_report_has_viral_dna(self):
        report = dna.analyze_dna(
            self.video, title="اختبار", hook=STRONG_HOOK,
            story_text=STORY_TWIST_MORAL,
            check_fn=self._fake_check)
        viral = report["viral_dna"]
        self.assertEqual(viral["hook"]["kind"], "question_conflict")
        self.assertEqual(viral["shot_structure"]["shot_count"], 2)
        self.assertEqual(viral["pacing"]["median_shot_seconds"], 3.0)
        self.assertEqual(viral["emotional_arc"]["shape"],
                         "تصاعد + انقلاب + عبرة")

    def test_format_report_has_structured_section(self):
        report = dna.analyze_dna(
            self.video, title="اختبار", hook=STRONG_HOOK,
            story_text=STORY_TWIST_MORAL,
            check_fn=self._fake_check)
        text = dna.format_report(report)
        # السطور القديمة باقية (توافق) + القسم المنظّم الجديد.
        self.assertIn("9/10", text)
        self.assertIn("الإيقاع", text)
        self.assertIn("تقرير Viral DNA المنظّم", text)
        self.assertIn("بنية اللقطات", text)
        self.assertIn("المنحنى العاطفي", text)
        self.assertIn("نقاط الضعف", text)
        self.assertNotIn("None", text)

    def test_format_old_report_without_viral_dna(self):
        """توافق رجعي: تقرير محفوظ قديم بلا viral_dna يُطبع
        بالقسم المنظّم دون استثناء."""
        old = _report(hook=dna.score_hook(STRONG_HOOK))
        text = dna.format_report(old)
        self.assertIn("تقرير Viral DNA المنظّم", text)
        self.assertNotIn("None", text)


if __name__ == "__main__":
    unittest.main()
