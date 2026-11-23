#!/usr/bin/env python3
"""اختبارات قوالب بنية القصة (lib.story_templates) + ربطها
بخطة المشاهد (lib.scene_plan) — الجولة v0.1.39.

تعمل بـ `python3 -m unittest discover -s tests -v`.
بلا شبكة وبلا رصيد Veo: فحص السقف في build_scene_plan
يستخدم الرصيد المسجَّل في الإعداد فقط.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import scene_plan
from lib import story_templates


def _cfg(balance=680, cap=None):
    veo = {"balance_units": balance, "renews": "2026-12-13"}
    if cap is not None:
        veo["cap_units"] = cap
    return {"veo": veo}


class TestListAndGet(unittest.TestCase):
    def test_three_templates(self):
        names = [n for n, _ in story_templates.list_templates()]
        self.assertEqual(names, ["relatives_injustice", "parents",
                                 "honesty_charity"])

    def test_labels_arabic(self):
        labels = dict(story_templates.list_templates())
        self.assertEqual(labels["relatives_injustice"],
                         "ظلم الأقارب والحماة")
        self.assertEqual(labels["parents"], "برّ/عقوق الوالدين")
        self.assertEqual(labels["honesty_charity"], "أمانة/صدقة")

    def test_unknown_template(self):
        with self.assertRaises(ValueError) as cm:
            story_templates.get_template("nope")
        self.assertIn("غير معروف", str(cm.exception))
        self.assertIn("relatives_injustice", str(cm.exception))

    def test_get_returns_copy(self):
        tpl = story_templates.get_template("parents")
        tpl["beats"]["hook"] = "معدَّل"
        fresh = story_templates.get_template("parents")
        self.assertNotEqual(fresh["beats"]["hook"], "معدَّل")


class TestBuildOutline(unittest.TestCase):
    def test_default_six_scenes_beats(self):
        out = story_templates.build_scene_outline(
            "relatives_injustice", "عائشة الأرملة", "عائشة الأرملة",
            "ظلمتها حماتها وطردتها من بيتها")
        self.assertEqual(out["clips"], 6)
        self.assertEqual(out["total_duration_seconds"], 48)
        self.assertEqual([s["beat"] for s in out["scenes"]],
                         ["hook", "escalation", "escalation",
                          "twist", "twist", "moral"])
        self.assertEqual(out["scenes"][0]["duration_seconds"], 8)
        self.assertIn("عائشة الأرملة", out["hook"])
        self.assertIn("ظلمتها حماتها", out["hook"])
        self.assertIn("العبرة:", out["scenes"][-1]["prompt"])
        self.assertIn("الظلم مهما طال", out["moral"])
        self.assertTrue(out["closing_question"].endswith("؟"))

    def test_four_clips_one_beat_each(self):
        out = story_templates.build_scene_outline(
            "parents", "الابن البعيد", "أحمد",
            "ترك أهله وسافر عشر سنين", clips=4)
        self.assertEqual([s["beat"] for s in out["scenes"]],
                         ["hook", "escalation", "twist", "moral"])

    def test_custom_moral_used(self):
        out = story_templates.build_scene_outline(
            "honesty_charity", "النجار الأمين", "نجار فقير",
            "وجد ذهبًا في باب قديم", moral="من ترك شيئًا لله عوّضه.",
            clips=4)
        self.assertEqual(out["moral"], "من ترك شيئًا لله عوّضه.")
        self.assertIn("من ترك شيئًا لله عوّضه.",
                      out["scenes"][-1]["prompt"])

    def test_default_moral_per_template(self):
        for name in ("relatives_injustice", "parents",
                     "honesty_charity"):
            out = story_templates.build_scene_outline(
                name, "عنوان", "بطل", "موقف", clips=1)
            self.assertTrue(out["moral"])

    def test_empty_inputs_rejected(self):
        for kwargs in ({"title": "  "}, {"hero": ""},
                       {"situation": "  "}):
            base = {"template": "parents", "title": "عنوان",
                    "hero": "بطل", "situation": "موقف"}
            base.update(kwargs)
            with self.assertRaises(ValueError):
                story_templates.build_scene_outline(**base)

    def test_invalid_clips(self):
        for clips in (0, 13, True, "6"):
            with self.assertRaises(ValueError):
                story_templates.build_scene_outline(
                    "parents", "عنوان", "بطل", "موقف", clips=clips)

    def test_render_story_text(self):
        out = story_templates.build_scene_outline(
            "honesty_charity", "النجار الأمين", "نجار فقير",
            "وجد ذهبًا في باب قديم", clips=4)
        text = story_templates.render_story_text(out)
        self.assertIn("نجار فقير", text)
        self.assertIn("لو لقيت مبلغ كبير", text)
        self.assertEqual(len(text.splitlines()), 5)

    def test_render_empty_outline_rejected(self):
        with self.assertRaises(ValueError):
            story_templates.render_story_text({})

    def test_format_outline(self):
        out = story_templates.build_scene_outline(
            "parents", "الابن البعيد", "أحمد",
            "ترك أهله وسافر عشر سنين", clips=4)
        text = story_templates.format_outline(out)
        self.assertIn("الابن البعيد", text)
        self.assertIn("32", text)
        self.assertIn("هوك", text)
        self.assertIn("عبرة", text)


class TestScenePlanWiring(unittest.TestCase):
    def test_template_replaces_draft(self):
        plan = scene_plan.build_scene_plan(
            _cfg(), {"number": 99, "title": "عائشة الأرملة"},
            template="relatives_injustice",
            template_hero="عائشة الأرملة",
            template_situation="ظلمتها حماتها وطردتها من بيتها")
        self.assertFalse(plan["draft_prompts"])
        self.assertEqual(plan["template"], "relatives_injustice")
        self.assertEqual(plan["template_beats"],
                         ["hook", "escalation", "escalation",
                          "twist", "twist", "moral"])
        self.assertEqual(plan["total_units"], 120)
        self.assertIn("ظلمتها حماتها", plan["scenes"][0]["prompt"])
        self.assertIn("قالب", scene_plan.format_plan(plan))

    def test_from_template_helper(self):
        plan = scene_plan.build_scene_plan_from_template(
            _cfg(), "honesty_charity", "النجار الأمين",
            "نجار فقير", "وجد ذهبًا في باب قديم", clips=4)
        self.assertEqual(len(plan["scenes"]), 4)
        self.assertEqual(plan["total_units"], 80)
        self.assertEqual(plan["template"], "honesty_charity")
        self.assertFalse(plan["draft_prompts"])

    def test_template_cap_still_enforced(self):
        with self.assertRaises(scene_plan.CapError):
            scene_plan.build_scene_plan_from_template(
                _cfg(cap=60), "parents", "الابن البعيد", "أحمد",
                "ترك أهله وسافر عشر سنين")

    def test_unknown_template_raises(self):
        with self.assertRaises(ValueError):
            scene_plan.build_scene_plan(
                _cfg(), {"title": "عنوان"},
                template="nope")

    def test_no_template_still_draft(self):
        plan = scene_plan.build_scene_plan(
            _cfg(), {"title": "قصة بلا نص"})
        self.assertTrue(plan["draft_prompts"])
        self.assertNotIn("template", plan)


if __name__ == "__main__":
    unittest.main()
