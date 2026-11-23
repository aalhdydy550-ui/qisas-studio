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


class TestEstimateVariantCost(unittest.TestCase):
    """تقدير تكلفة المتغير (الجولة v0.1.39) — بلا شبكة."""

    def test_fast_six_clips_120_units(self):
        est = ab.estimate_variant_cost(clips=6, engine="fast")
        self.assertEqual(est["veo_units"], 120)
        self.assertEqual(est["units_per_clip"], 20)
        self.assertEqual(est["video_seconds"], 48)
        self.assertEqual(est["render_minutes_estimate"], 1.6)
        self.assertEqual(est["cash_usd"], 0)
        self.assertEqual(est["engine_label"], "Veo 3.1 Fast")

    def test_lite_six_clips_60_units(self):
        est = ab.estimate_variant_cost(clips=6, engine="lite")
        self.assertEqual(est["veo_units"], 60)
        self.assertEqual(est["units_per_clip"], 10)
        self.assertEqual(est["video_seconds"], 48)
        self.assertEqual(est["render_minutes_estimate"], 1.6)
        self.assertEqual(est["cash_usd"], 0)

    def test_zero_clips_edge_case(self):
        """حالة حدّية: متغير بلا مقاطع — صفر رصيد وصفر ريندر."""
        est = ab.estimate_variant_cost(clips=0, engine="lite")
        self.assertEqual(est["veo_units"], 0)
        self.assertEqual(est["video_seconds"], 0)
        self.assertEqual(est["render_minutes_estimate"], 0.0)
        self.assertEqual(est["cash_usd"], 0)
        self.assertIn("بلا مقاطع", est["note"])

    def test_invalid_engine_rejected(self):
        with self.assertRaises(ValueError):
            ab.estimate_variant_cost(clips=6, engine="ultra")

    def test_invalid_clips_rejected(self):
        for bad in (-1, True, "6", 6.5, None):
            with self.assertRaises(ValueError, msg="clips=%r" % (bad,)):
                ab.estimate_variant_cost(clips=bad, engine="fast")

    def test_balance_fits_and_exceeds(self):
        fits = ab.estimate_variant_cost(
            clips=6, engine="fast", balance_units=680)
        self.assertTrue(fits["fits_recorded_balance"])
        short = ab.estimate_variant_cost(
            clips=6, engine="fast", balance_units=100)
        self.assertFalse(short["fits_recorded_balance"])
        self.assertIn("يتجاوز الرصيد", short["balance_note"] or "")

    def test_ledger_average_compared(self):
        entries = [{"clips": 6, "units": 120, "video": "أ"},
                   {"clips": 6, "units": 60, "video": "ب"}]
        est = ab.estimate_variant_cost(
            clips=6, engine="fast", ledger_entries=entries)
        self.assertEqual(est["actual_avg_units_per_clip"], 15.0)
        self.assertIsNone(
            ab.ledger_avg_units_per_clip("/tmp/no-such-studio-xyz"))
        self.assertIsNone(ab.average_units_per_clip([]))
        self.assertIsNone(ab.average_units_per_clip(
            [{"clips": None, "units": 50}]))


class TestEstimateFromUnits(unittest.TestCase):
    """اشتقاق التقدير من cost_per_video الموجود (توسعة المسار
    القديم — لا مسار موازٍ)."""

    def test_fast_120_is_six_clips(self):
        est = ab.estimate_variant_cost_from_units(120, engine="fast")
        self.assertEqual(est["clips"], 6)
        self.assertEqual(est["veo_units"], 120)
        self.assertEqual(est["render_minutes_estimate"], 1.6)

    def test_lite_120_is_twelve_clips(self):
        est = ab.estimate_variant_cost_from_units(120, engine="lite")
        self.assertEqual(est["clips"], 12)
        self.assertEqual(est["video_seconds"], 96)
        self.assertEqual(est["render_minutes_estimate"], 3.2)

    def test_lite_60_is_six_clips(self):
        est = ab.estimate_variant_cost_from_units(60, engine="lite")
        self.assertEqual(est["clips"], 6)
        self.assertEqual(est["veo_units"], 60)

    def test_zero_units_same_video(self):
        est = ab.estimate_variant_cost_from_units(0, engine="fast")
        self.assertEqual(est["clips"], 0)
        self.assertEqual(est["veo_units"], 0)
        self.assertEqual(est["render_minutes_estimate"], 0.0)
        self.assertIn("نفس الفيديو", est["note"])

    def test_non_divisible_units_fractional_clips(self):
        """90 وحدة Fast = 4.5 مقطع — كسري مصرّح به لا مقطع
        كامل مخترع."""
        est = ab.estimate_variant_cost_from_units(90, engine="fast")
        self.assertEqual(est["clips"], 4.5)
        self.assertEqual(est["veo_units"], 90)
        self.assertEqual(est["video_seconds"], 36.0)

    def test_invalid_units_or_engine(self):
        for bad in (-5, True, "120", None):
            with self.assertRaises(ValueError, msg="units=%r" % (bad,)):
                ab.estimate_variant_cost_from_units(bad)
        with self.assertRaises(ValueError):
            ab.estimate_variant_cost_from_units(120, engine="ultra")

    def test_format_variant_cost_line(self):
        est = ab.estimate_variant_cost_from_units(60, engine="lite")
        line = ab.format_variant_cost(est)
        self.assertIn("60 وحدة", line)
        self.assertIn("Veo 3.1 Lite", line)
        self.assertIn("6 مقاطع", line)
        self.assertIn("$0", line)
        self.assertIn("1.6", line)


class TestCreateAbVariantsCost(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.video = os.path.join(self.tmp, "video.mp4")
        with open(self.video, "wb") as f:
            f.write(b"fake-video")

    def test_lite_cost_per_variant_and_totals(self):
        calls = []
        record = ab.create_ab_variants(
            self.video, [WEAK_HOOK, STRONG_HOOK, MID_HOOK], self.tmp,
            title="قصة",
            thumbnail_fn=_fake_thumbnail(calls),
            duration_fn=lambda v: 50.0,
            cost_per_video=120, engine="lite")
        for v in record["variants"]:
            est = v["cost_estimate"]
            self.assertEqual(est["veo_units"], 120)
            self.assertEqual(est["clips"], 12)
            self.assertEqual(est["engine"], "lite")
            self.assertEqual(est["cash_usd"], 0)
            self.assertEqual(est["render_minutes_estimate"], 3.2)
        costs = record["cost_estimates"]
        self.assertEqual(costs["total_units"], 360)
        self.assertEqual(costs["total_render_minutes_estimate"], 9.6)
        self.assertEqual(costs["cash_usd"], 0)
        # المسار القديم باقٍ كما هو (توافق).
        self.assertEqual(record["cost_estimate_units"]["total"], 360)
        self.assertEqual(record["cost_estimate_units"]["variant_a"], 120)

    def test_fast_default_engine(self):
        record = ab.create_ab_variants(
            self.video, [WEAK_HOOK, STRONG_HOOK], self.tmp,
            thumbnail_fn=_fake_thumbnail([]),
            duration_fn=lambda v: 50.0,
            cost_per_video=120)
        self.assertEqual(record["variants"][0]["cost_estimate"]["clips"], 6)
        self.assertEqual(record["variants"][0]["cost_estimate"]["engine"],
                         "fast")

    def test_zero_cost_same_video(self):
        record = ab.create_ab_variants(
            self.video, [WEAK_HOOK, STRONG_HOOK], self.tmp,
            thumbnail_fn=_fake_thumbnail([]),
            duration_fn=lambda v: 50.0)
        for v in record["variants"]:
            self.assertEqual(v["cost_estimate"]["veo_units"], 0)
            self.assertEqual(v["cost_estimate"]["render_minutes_estimate"],
                             0.0)
        self.assertEqual(record["cost_estimates"]["total_units"], 0)

    def test_balance_flag_in_record(self):
        record = ab.create_ab_variants(
            self.video, [WEAK_HOOK, STRONG_HOOK], self.tmp,
            thumbnail_fn=_fake_thumbnail([]),
            duration_fn=lambda v: 50.0,
            cost_per_video=120, engine="fast", balance_units=100)
        self.assertFalse(record["variants"][0]["cost_estimate"]
                         ["fits_recorded_balance"])

    def test_invalid_engine_rejected_before_thumbnails(self):
        calls = []
        with self.assertRaises(ValueError):
            ab.create_ab_variants(
                self.video, [WEAK_HOOK, STRONG_HOOK], self.tmp,
                thumbnail_fn=_fake_thumbnail(calls),
                duration_fn=lambda v: 50.0,
                cost_per_video=120, engine="ultra")
        self.assertEqual(calls, [])

    def test_create_ab_two_variants_cost(self):
        record = ab.create_ab(
            self.video, "هوك أ!", "هوك ب!", self.tmp,
            title="قصة",
            thumbnail_fn=_fake_thumbnail([]),
            duration_fn=lambda v: 50.0,
            cost_per_video=120, engine="lite")
        costs = record["cost_estimates"]
        self.assertEqual(costs["variant_a"]["veo_units"], 120)
        self.assertEqual(costs["variant_b"]["clips"], 12)
        self.assertEqual(costs["total_units"], 240)
        self.assertEqual(costs["total_render_minutes_estimate"], 6.4)
        self.assertEqual(record["cost_estimate_units"]["total"], 240)

    def test_format_comparison_shows_variant_cost(self):
        record = ab.create_ab(
            self.video, "هوك أ!", "هوك ب!", self.tmp,
            title="قصة",
            thumbnail_fn=_fake_thumbnail([]),
            duration_fn=lambda v: 50.0,
            cost_per_video=60, engine="lite")
        out = ab.compare_ab(record, [], [])
        text = ab.format_comparison(record, out)
        self.assertIn("تكلفة كل متغير", text)
        self.assertIn("60 وحدة", text)
        self.assertIn("Veo 3.1 Lite", text)
        self.assertIn("غير منشورة بعد", text)


if __name__ == "__main__":
    unittest.main()
