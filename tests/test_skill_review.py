#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات مراجعة المهارات المتعلمة + مكتبة مهارات — جولة v0.1.63 (بند 25).

معزولة: مجلدات مؤقتة فقط، بلا شبكة. مزايا ``lib.features``
تُحقن كوحدة وهمية في ``sys.modules`` لأن ملف W3 قد لا يكون
موجودًا بعد — والوحدة الحقيقية تتبع العقد نفسه (ع7).
"""
import json
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import skill_review


class FakeFeatures:
    """مزايا وهمية بنفس واجهة ع7: ``get(name, default)``."""

    def __init__(self, values):
        self.values = dict(values)

    def get(self, name, default=None):
        return self.values.get(name, default)


def _install_features(values):
    module = types.ModuleType("lib.features")
    module.get = FakeFeatures(values).get
    module.set = lambda name, value: None
    sys.modules["lib.features"] = module
    # ``from lib import features`` يرجع سمة الحزمة بعد أول استيراد،
    # فيجب تحديثها مع كل تثبيت وهمي جديد.
    import lib
    setattr(lib, "features", module)
    return module


class FeaturesMixin(unittest.TestCase):
    def setUp(self):
        self._saved = sys.modules.get("lib.features")
        import lib
        self._saved_attr = getattr(lib, "features", None)

    def tearDown(self):
        import lib
        if self._saved is None:
            sys.modules.pop("lib.features", None)
        else:
            sys.modules["lib.features"] = self._saved
        if self._saved_attr is None:
            if hasattr(lib, "features"):
                delattr(lib, "features")
        else:
            setattr(lib, "features", self._saved_attr)

    def install(self, values):
        return _install_features(values)


class TestReviewSteps(FeaturesMixin):
    def test_bounds_3_to_100(self):
        self.assertEqual(skill_review.validate_steps(3), 3)
        self.assertEqual(skill_review.validate_steps(100), 100)
        with self.assertRaises(ValueError):
            skill_review.validate_steps(2)
        with self.assertRaises(ValueError):
            skill_review.validate_steps(101)
        with self.assertRaises(ValueError):
            skill_review.validate_steps("10")
        with self.assertRaises(ValueError):
            skill_review.validate_steps(True)

    def test_review_after_exactly_n_steps(self):
        self.install({"skillReview": True, "skillReviewSteps": 5})
        self.assertTrue(skill_review.should_review(5))
        self.assertTrue(skill_review.should_review(10))
        self.assertFalse(skill_review.should_review(4))
        self.assertFalse(skill_review.should_review(6))
        self.assertFalse(skill_review.should_review(0))

    def test_review_disabled_by_default(self):
        self.install({})
        self.assertFalse(skill_review.review_enabled())
        self.assertFalse(skill_review.should_review(10))

    def test_invalid_steps_fall_back_to_default(self):
        self.install({"skillReview": True, "skillReviewSteps": 500})
        self.assertEqual(skill_review.review_steps(), 10)
        self.assertTrue(skill_review.should_review(10))

    def test_no_features_module_means_disabled(self):
        sys.modules.pop("lib.features", None)
        import lib
        if hasattr(lib, "features"):
            delattr(lib, "features")
        self.assertFalse(skill_review.review_enabled())
        self.assertEqual(skill_review.review_steps(), 10)
        self.assertEqual(skill_review.share_mode(), "off")


class TestShareModes(FeaturesMixin):
    def test_three_modes(self):
        for mode in ("off", "ask", "auto"):
            self.install({"shareLearnedSkills": mode})
            self.assertEqual(skill_review.share_mode(), mode)

    def test_unknown_mode_falls_back_to_off(self):
        self.install({"shareLearnedSkills": "always"})
        self.assertEqual(skill_review.share_mode(), "off")


class TestOptOut(unittest.TestCase):
    def test_missing_file_means_no_exclusion(self):
        with tempfile.TemporaryDirectory() as td:
            names, warning = skill_review.load_opt_out(
                os.path.join(td, "library-opt-out.json"))
            self.assertEqual(names, set())
            self.assertIsNone(warning)

    def test_valid_list(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "library-opt-out.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(["fix-mlt", "hook-title"], fh)
            names, warning = skill_review.load_opt_out(path)
            self.assertEqual(names, {"fix-mlt", "hook-title"})
            self.assertIsNone(warning)

    def test_unreadable_file_keeps_everything_with_warning(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "library-opt-out.json")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{ليس json")
            names, warning = skill_review.load_opt_out(path)
            self.assertEqual(names, set())
            self.assertIsNotNone(warning)
            self.assertIn("يحتفظ العامل بكل شيء", warning)

    def test_non_list_keeps_everything_with_warning(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "library-opt-out.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"skill": True}, fh)
            names, warning = skill_review.load_opt_out(path)
            self.assertEqual(names, set())
            self.assertIsNotNone(warning)


class TestReviewFlow(FeaturesMixin):
    def _steps(self):
        return [{"tool": "render"}, {"tool": "render"},
                {"tool": "caption"}, {"tool": "render"},
                {"tool": "publish"}]

    def test_auto_shares_repeated_tool_as_skill(self):
        self.install({"skillReview": True, "skillReviewSteps": 5,
                      "shareLearnedSkills": "auto"})
        with tempfile.TemporaryDirectory() as td:
            result = skill_review.review_after_steps(
                5, self._steps(), library_dir=td)
            self.assertTrue(result["due"])
            self.assertEqual(result["candidates"], ["render"])
            self.assertEqual(len(result["shared"]), 1)
            self.assertEqual(skill_review.list_library(td), ["render"])

    def test_ask_mode_pends_instead_of_writing(self):
        self.install({"skillReview": True, "skillReviewSteps": 5,
                      "shareLearnedSkills": "ask"})
        with tempfile.TemporaryDirectory() as td:
            result = skill_review.review_after_steps(
                5, self._steps(), library_dir=td)
            self.assertEqual(len(result["pending"]), 1)
            self.assertEqual(result["shared"], [])
            self.assertEqual(skill_review.list_library(td), [])

    def test_off_mode_shares_nothing(self):
        self.install({"skillReview": True, "skillReviewSteps": 5,
                      "shareLearnedSkills": "off"})
        with tempfile.TemporaryDirectory() as td:
            result = skill_review.review_after_steps(
                5, self._steps(), library_dir=td)
            self.assertEqual(result["shared"], [])
            self.assertEqual(result["pending"], [])

    def test_opted_out_tool_excluded(self):
        self.install({"skillReview": True, "skillReviewSteps": 5,
                      "shareLearnedSkills": "auto"})
        with tempfile.TemporaryDirectory() as td:
            worker = os.path.join(td, "worker")
            os.makedirs(worker)
            with open(os.path.join(worker, "library-opt-out.json"),
                      "w", encoding="utf-8") as fh:
                json.dump(["render"], fh)
            library = os.path.join(td, "library")
            result = skill_review.review_after_steps(
                5, self._steps(), library_dir=library, worker_dir=worker)
            self.assertEqual(result["candidates"], [])
            self.assertEqual(result["shared"], [])

    def test_not_due_returns_no_candidates(self):
        self.install({"skillReview": True, "skillReviewSteps": 5,
                      "shareLearnedSkills": "auto"})
        with tempfile.TemporaryDirectory() as td:
            result = skill_review.review_after_steps(
                4, self._steps(), library_dir=td)
            self.assertFalse(result["due"])
            self.assertEqual(result["candidates"], [])

    def test_write_skill_rejects_empty_body(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                skill_review.write_skill(td, "x", "   ")


if __name__ == "__main__":
    unittest.main()
