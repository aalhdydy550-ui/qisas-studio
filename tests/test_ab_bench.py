#!/usr/bin/env python3
"""اختبارات منهجية bench المتداخلة (lib.ab.bench_interleaved)
— الجولة v0.1.40، حزمة 1ب (استخراج fast-anything بند 2).

تعمل بـ `python3 -m unittest tests.test_ab_bench -v`.
دالتان وهميتان (نوم قصير + مخرجات حتمية) — بلا شبكة وبلا
ffmpeg وبلا فيسبوك/يوتيوب.
"""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import ab


def _slow_fn(text):
    def fn():
        time.sleep(0.03)
        return text
    return fn


def _fast_fn(text):
    def fn():
        time.sleep(0.005)
        return text
    return fn


class TestBenchInterleaved(unittest.TestCase):
    def test_matching_outputs(self):
        result = ab.bench_interleaved(
            _fast_fn("سطر أول\nسطر ثانٍ"),
            _slow_fn("سطر أول\nسطر ثانٍ"), runs=3)
        self.assertEqual(result["runs"], 3)
        for side in ("a", "b"):
            self.assertEqual(len(result[side]["times"]), 3)
            self.assertGreater(result[side]["median"], 0)
            self.assertGreaterEqual(result[side]["mean"], 0)
            self.assertGreaterEqual(result[side]["stddev"], 0)
        self.assertEqual(result["a"]["output"], "سطر أول\nسطر ثانٍ")
        self.assertEqual(result["b"]["output"], "سطر أول\nسطر ثانٍ")
        self.assertTrue(result["outputs_equal"])
        self.assertIsNone(result["first_diff"])
        # السريعة (أ) وسيطها أقل — الفائز أ والتسريع > 1.
        self.assertEqual(result["winner"], "a")
        self.assertGreater(result["speedup"], 1.0)

    def test_different_outputs_first_diff(self):
        result = ab.bench_interleaved(
            _fast_fn("سطر أول\nسطر ثانٍ\nسطر ثالث"),
            _fast_fn("سطر أول\nسطر مختلف\nسطر ثالث"), runs=2)
        self.assertFalse(result["outputs_equal"])
        diff = result["first_diff"]
        self.assertIsNotNone(diff)
        self.assertEqual(diff["index"], 1)
        self.assertEqual(diff["a"], "سطر ثانٍ")
        self.assertEqual(diff["b"], "سطر مختلف")

    def test_different_outputs_shorter_side(self):
        result = ab.bench_interleaved(
            _fast_fn("سطر أول\nسطر ثانٍ"),
            _fast_fn("سطر أول\nسطر ثانٍ\nسطر ثالث"), runs=1)
        self.assertFalse(result["outputs_equal"])
        diff = result["first_diff"]
        self.assertEqual(diff["index"], 2)
        self.assertIsNone(diff["a"])
        self.assertEqual(diff["b"], "سطر ثالث")

    def test_interleaved_order(self):
        # الترتيب المتداخل: أ، ب، أ، ب... — لا كل أ ثم كل ب.
        order = []

        def fn_a():
            order.append("a")
            return "x"

        def fn_b():
            order.append("b")
            return "x"

        ab.bench_interleaved(fn_a, fn_b, runs=4)
        self.assertEqual(order, ["a", "b"] * 4)

    def test_runs_one(self):
        result = ab.bench_interleaved(
            _fast_fn("ناتج"), _fast_fn("ناتج"), runs=1)
        self.assertEqual(result["runs"], 1)
        self.assertEqual(len(result["a"]["times"]), 1)
        self.assertEqual(len(result["b"]["times"]), 1)
        # تشغيلة واحدة: بلا انحراف، والوسيط = المتوسط = الزمن.
        self.assertEqual(result["a"]["stddev"], 0.0)
        self.assertEqual(result["a"]["median"], result["a"]["mean"])
        self.assertEqual(result["a"]["median"],
                         result["a"]["times"][0])
        self.assertTrue(result["outputs_equal"])
        self.assertIsNone(result["first_diff"])

    def test_tie_when_same_speed(self):
        # زمن مثبَّت بمحاكاة perf_counter: الجانبان بنفس الأزمنة
        # تمامًا — فالوسيطان متساويان والفائز تعادل والتسريع 1.
        import itertools
        from unittest import mock
        ticks = itertools.count(start=0, step=1)
        with mock.patch("time.perf_counter",
                        side_effect=lambda: next(ticks) * 0.001):
            result = ab.bench_interleaved(
                lambda: "نفس الناتج", lambda: "نفس الناتج", runs=3)
        self.assertTrue(result["outputs_equal"])
        self.assertEqual(result["winner"], "tie")
        self.assertEqual(result["speedup"], 1.0)

    def test_invalid_runs_raise(self):
        for bad in (0, -1, 2.5, "3", True, None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                ab.bench_interleaved(lambda: 1, lambda: 1, runs=bad)

    def test_non_callable_raises(self):
        with self.assertRaises(ValueError):
            ab.bench_interleaved("ليست دالة", lambda: 1)
        with self.assertRaises(ValueError):
            ab.bench_interleaved(lambda: 1, 42)

    def test_non_text_outputs_compared_by_equality(self):
        result = ab.bench_interleaved(lambda: [1, 2], lambda: [1, 3],
                                      runs=1)
        self.assertFalse(result["outputs_equal"])
        # مخرجات غير نصية: بلا أول اختلاف سطري.
        self.assertIsNone(result["first_diff"])


class TestFormatBench(unittest.TestCase):
    def test_matching_outputs_summary(self):
        result = ab.bench_interleaved(
            _fast_fn("سطر أول\nسطر ثانٍ"),
            _slow_fn("سطر أول\nسطر ثانٍ"), runs=2)
        text = ab.format_bench(result)
        self.assertIn("الوسيط", text)
        self.assertIn("الانحراف المعياري", text)
        self.assertIn("متطابقة", text)
        self.assertIn("الفائز: نسخة أ", text)
        self.assertIn("أسرع", text)

    def test_different_outputs_summary(self):
        result = ab.bench_interleaved(
            _fast_fn("سطر أول\nسطر ثانٍ"),
            _fast_fn("سطر أول\nسطر مختلف"), runs=1)
        text = ab.format_bench(result)
        self.assertIn("مختلفة", text)
        self.assertIn("أول اختلاف في السطر 2", text)
        self.assertIn("سطر ثانٍ", text)
        self.assertIn("سطر مختلف", text)

    def test_tie_summary(self):
        result = {"runs": 2,
                  "a": {"median": 0.01, "mean": 0.01, "stddev": 0.0},
                  "b": {"median": 0.01, "mean": 0.01, "stddev": 0.0},
                  "outputs_equal": True, "first_diff": None,
                  "winner": "tie", "speedup": 1.0}
        self.assertIn("تعادل", ab.format_bench(result))


if __name__ == "__main__":
    unittest.main()
