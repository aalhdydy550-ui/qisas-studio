#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات اقتراح إعادة البناء (lib.dna.build_rebuild_proposal)
— الجولة 8، v0.1.35.

تعمل بـ `python3 -m unittest discover -s tests -v`.
التقرير الحقيقي من الديمو (videos/demo-20261122-130448.mp4)
بكشف قطع حقيقي (ffmpeg) وكثافة من ملفات ASS الحقيقية في
demo/؛ فحص الصمت بدالة مزيفة (بلا check كامل).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import dna

DEMO_VIDEO = os.path.expanduser(
    "~/workspace/videos/demo-20261122-130448.mp4")
DEMO_DIR = os.path.expanduser("~/workspace/studio/demo")
STORY_PATH = os.path.join(DEMO_DIR, "story.txt")
GOOD_HOOK = "ليه الراجل ظلم أخوه؟ الحقيقة انكشفت فجأة!"


def _fake_check_ok(video):
    return {"passed": True, "checks": [
        {"name": "الصمت عند الفواصل", "ok": True,
         "detail": "لا صمت ≥1 ثانية في منتصف الفيديو"}]}


def _demo_story():
    with open(STORY_PATH, encoding="utf-8") as f:
        return f.read()


class TestRebuildProposalRealDemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(DEMO_VIDEO):
            raise unittest.SkipTest("الديمو غير موجود: %s" % DEMO_VIDEO)
        cls.story = _demo_story()
        cls.report = dna.analyze_dna(
            DEMO_VIDEO, title="الديمو", hook=GOOD_HOOK,
            subs_dir=DEMO_DIR, slug="aisha2",
            story_text=cls.story, check_fn=_fake_check_ok)

    def test_proposal_has_hook_template(self):
        text = dna.build_rebuild_proposal(self.report, self.story)
        self.assertIn("قالب الهوك", text)
        self.assertIn("ليه", text)
        # درجة هوك المرجع الحقيقية تظهر في الاقتراح
        self.assertIn("%d/%d" % (self.report["hook"]["total"],
                                 self.report["hook"]["max"]), text)

    def test_proposal_has_pacing_target(self):
        text = dna.build_rebuild_proposal(self.report, self.story)
        self.assertIn("إيقاع اللقطات", text)
        avg = self.report["pacing"]["avg_shot_seconds"]
        self.assertIn("%.1f" % avg, text)

    def test_proposal_has_silence_guidance(self):
        text = dna.build_rebuild_proposal(self.report, self.story)
        self.assertIn("الصمت", text)
        self.assertIn("بلا صمت مزعج", text)

    def test_proposal_has_word_density_target(self):
        text = dna.build_rebuild_proposal(self.report, self.story)
        self.assertIn("كثافة الكلمات", text)
        wpm = self.report["word_density"]["wpm"]
        if wpm is not None:
            self.assertIn("%.0f" % wpm, text)
        else:
            self.assertIn("غير مقاسة", text)

    def test_proposal_has_four_sections(self):
        text = dna.build_rebuild_proposal(self.report, self.story)
        for marker in ("1) قالب الهوك", "2) هدف إيقاع اللقطات",
                       "3) توجيه الصمت", "4) هدف كثافة الكلمات"):
            self.assertIn(marker, text)


class TestRebuildProposalUnmeasured(unittest.TestCase):
    def test_no_pacing_prints_unmeasured_not_number(self):
        report = {
            "video": "/tmp/ref.mp4",
            "duration": 48.0,
            "hook": dna.score_hook(GOOD_HOOK),
            "pacing": {"shot_count": None, "avg_shot_seconds": None,
                       "cuts": [], "duration": 48.0},
            "silence": {"ok": None,
                        "detail": "غير مقاس (لا نتيجة فحص صمت)"},
            "word_density": {"wpm": None, "words": 0, "files": 0,
                             "source": None},
        }
        text = dna.build_rebuild_proposal(report, "قصة قصيرة. العبرة واضحة.")
        self.assertIn("غير مقاس", text)
        self.assertIn("إيقاع المرجع: غير مقاس", text)
        self.assertIn("صمت المرجع: غير مقاس", text)
        self.assertIn("غير مقاسة", text)

    def test_no_hook_no_story(self):
        report = {"video": "/tmp/ref.mp4", "duration": 48.0,
                  "hook": None, "pacing": {},
                  "silence": {}, "word_density": {}}
        text = dna.build_rebuild_proposal(report, "")
        self.assertIn("غير مقاس", text)
        self.assertIn("نص القصة غير متاح", text)

    def test_weak_reference_hook_flagged(self):
        report = {
            "video": "/tmp/ref.mp4",
            "duration": 48.0,
            "hook": dna.score_hook("يا جماعة تعالوا أحكيلكم قصة"),
            "pacing": {"shot_count": 6, "avg_shot_seconds": 8.0,
                       "cuts": [], "duration": 48.0},
            "silence": {"ok": True, "detail": "لا صمت"},
            "word_density": {"wpm": 120.0, "words": 96, "files": 2,
                             "source": "ass"},
        }
        text = dna.build_rebuild_proposal(report, "قصة. العبرة في آخرها.")
        self.assertIn("هوك المرجع نفسه ضعيف", text)
        self.assertIn("8.0", text)
        self.assertIn("120", text)


if __name__ == "__main__":
    unittest.main()
