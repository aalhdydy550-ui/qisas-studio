#!/usr/bin/env python3
"""اختبارات توسيع A/B (lib.ab: suggest_hooks_n / score_hooks /
create_ab_variants) — الجولة 8، v0.1.35.

تعمل بـ `python3 -m unittest discover -s tests -v`.
اختبار create_ab_variants على الديمو الحقيقي
(videos/demo-20261122-130448.mp4) بمصغرات حقيقية (ffmpeg)؛
باقي الاختبارات بدوال مزيفة بلا شبكة.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import ab

DEMO_VIDEO = os.path.expanduser(
    "~/workspace/videos/demo-20261122-130448.mp4")

STRONG_HOOK = "ليه الراجل ظلم أخوه؟ الحقيقة انكشفت فجأة!"
MID_HOOK = "الراجل باع ضميره والنهاية هتصدمك"
WEAK_HOOK = "يا جماعة تعالوا أحكيلكم قصة راجل طيب"


def _fake_thumbnail(calls):
    def fn(video, hook, out, at_seconds=None):
        calls.append((hook, at_seconds))
        with open(out, "wb") as f:
            f.write(b"fake-thumb")
        return out, at_seconds, [hook]
    return fn


class TestSuggestHooksN(unittest.TestCase):
    def test_five_llm_hooks_returns_three_distinct_valid(self):
        def fake_chat(prompt):
            self.assertIn("3", prompt)
            return ("هوك أول صادم!\n"
                    "هوك ثانٍ مختلف!\n"
                    "هوك ثالث جديد!\n"
                    "هوك رابع إضافي!\n"
                    "هوك خامس أخير!\n")
        hooks, src = ab.suggest_hooks_n("قصة جديدة", chat_fn=fake_chat)
        self.assertEqual(len(hooks), 3)
        self.assertEqual(len(set(hooks)), 3)
        self.assertEqual(src, "omniroute")
        for h in hooks:
            self.assertTrue(h)
            self.assertLessEqual(len(h), 140)

    def test_llm_returns_fewer_than_n_fills_local(self):
        def fake_chat(prompt):
            return "هوك أول صادم!\n"
        hooks, src = ab.suggest_hooks_n("قصة جديدة", chat_fn=fake_chat)
        self.assertEqual(len(hooks), 3)
        self.assertEqual(len(set(hooks)), 3)
        self.assertEqual(hooks[0], "هوك أول صادم!")
        self.assertIn("قصة جديدة", hooks[1])
        self.assertEqual(src, "mixed")

    def test_llm_failure_local_fallback_three_distinct(self):
        def boom(prompt):
            raise RuntimeError("بلا شبكة")
        hooks, src = ab.suggest_hooks_n("قصة جديدة", chat_fn=boom)
        self.assertEqual(len(hooks), 3)
        self.assertEqual(len(set(hooks)), 3)
        self.assertEqual(hooks[0], "قصة جديدة")
        self.assertEqual(src, "local")
        for h in hooks:
            self.assertTrue(h)
            self.assertLessEqual(len(h), 140)

    def test_no_chat_fn_local_fallback(self):
        hooks, src = ab.suggest_hooks_n("قصة", chat_fn=None, n=2)
        self.assertEqual(len(hooks), 2)
        self.assertNotEqual(hooks[0], hooks[1])
        self.assertEqual(src, "local")

    def test_invalid_n_rejected(self):
        with self.assertRaises(ValueError):
            ab.suggest_hooks_n("قصة", chat_fn=None, n=0)


class TestScoreHooks(unittest.TestCase):
    def test_scores_use_dna_table(self):
        scores = ab.score_hooks([STRONG_HOOK, WEAK_HOOK])
        self.assertEqual(len(scores), 2)
        self.assertGreater(scores[0]["total"], scores[1]["total"])
        self.assertEqual(scores[0]["total"], 6)
        self.assertEqual(scores[0]["max"], 9)  # بلا نص قصة: العائد غير مقاس
        self.assertIn("breakdown", scores[0])

    def test_score_with_story_text_measures_payoff(self):
        story = ("كان فيه راجل ظالم. سرق مال أخوه. أنكر الوصية. "
                 "هرب من القرية. العبرة أن الظلم لا يدوم.")
        scores = ab.score_hooks([STRONG_HOOK], story_text=story)
        self.assertEqual(scores[0]["max"], 10)
        self.assertEqual(scores[0]["breakdown"]["payoff"], 1)


class TestCreateAbVariants(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.video = os.path.join(self.tmp, "video.mp4")
        with open(self.video, "wb") as f:
            f.write(b"fake-video")

    def test_fake_thumbnails_sorted_by_dna_score(self):
        calls = []
        record = ab.create_ab_variants(
            self.video, [WEAK_HOOK, STRONG_HOOK, MID_HOOK], self.tmp,
            title="قصة",
            thumbnail_fn=_fake_thumbnail(calls),
            duration_fn=lambda v: 50.0,
            cost_per_video=20)
        variants = record["variants"]
        self.assertEqual(len(variants), 3)
        scores = [v["dna_score"] for v in variants]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(record["best"], variants[0]["hook"])
        self.assertEqual(record["best"], STRONG_HOOK)
        self.assertEqual(record["hook_a"], WEAK_HOOK)
        self.assertEqual(record["hook_b"], STRONG_HOOK)
        self.assertTrue(os.path.isfile(record["record_path"]))
        for v in variants:
            self.assertTrue(os.path.isfile(v["thumb"]))
            self.assertEqual(v["cost"], 20)
        cost = record["cost_estimate_units"]
        self.assertEqual(cost["total"], 60)
        self.assertEqual(cost["variant_a"], 20)
        self.assertEqual(cost["variant_b"], 20)
        with open(record["record_path"], encoding="utf-8") as f:
            saved = json.load(f)
        self.assertEqual(saved["best"], STRONG_HOOK)
        self.assertEqual(len(saved["variants"]), 3)

    def test_duplicate_hooks_rejected(self):
        with self.assertRaises(ValueError):
            ab.create_ab_variants(
                self.video, [STRONG_HOOK, STRONG_HOOK], self.tmp,
                thumbnail_fn=_fake_thumbnail([]),
                duration_fn=lambda v: 50.0)

    def test_fewer_than_two_hooks_rejected(self):
        with self.assertRaises(ValueError):
            ab.create_ab_variants(
                self.video, [STRONG_HOOK], self.tmp,
                thumbnail_fn=_fake_thumbnail([]),
                duration_fn=lambda v: 50.0)

    def test_two_variants_match_create_ab_fractions(self):
        calls = []
        ab.create_ab_variants(
            self.video, [STRONG_HOOK, MID_HOOK], self.tmp,
            thumbnail_fn=_fake_thumbnail(calls),
            duration_fn=lambda v: 50.0)
        self.assertEqual(calls[0][1], 17.5)
        self.assertEqual(calls[1][1], 32.5)

    def test_real_demo_video(self):
        if not os.path.isfile(DEMO_VIDEO):
            raise unittest.SkipTest("الديمو غير موجود: %s" % DEMO_VIDEO)
        record = ab.create_ab_variants(
            DEMO_VIDEO, [WEAK_HOOK, STRONG_HOOK, MID_HOOK], self.tmp,
            title="الديمو", cost_per_video=20)
        variants = record["variants"]
        self.assertEqual(len(variants), 3)
        scores = [v["dna_score"] for v in variants]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(record["best"], variants[0]["hook"])
        self.assertEqual(record["best"], STRONG_HOOK)
        self.assertEqual(record["hook_a"], WEAK_HOOK)
        self.assertEqual(record["hook_b"], STRONG_HOOK)
        self.assertEqual(record["cost_estimate_units"]["total"], 60)
        for v in variants:
            self.assertTrue(os.path.isfile(v["thumb"]))
            self.assertGreater(os.path.getsize(v["thumb"]), 0)


if __name__ == "__main__":
    unittest.main()
