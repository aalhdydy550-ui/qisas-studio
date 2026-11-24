#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات برومبت الأداء المنظَّم — جولة v0.1.38 (بند 8).

الخانات الأربع حاضرة؛ وخانة فارغة تُرفض؛ وأنواع المشاهد
الثلاثة تختلف في سطر الإيماءة؛ والشخصية الافتراضية تُستخدم
عند الغياب.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import avatar_prompt as prompt_lib
from lib.avatar_prompt import AvatarPromptError


class TestBuildPrompt(unittest.TestCase):
    def test_four_slots_present(self):
        prompt = prompt_lib.build_performance_prompt(
            persona="A young teacher", expression="cheerful",
            gesture="nods often", camera="slow push-in")
        for slot in ("Persona: A young teacher",
                     "Expression: cheerful",
                     "Gesture: nods often",
                     "Camera: slow push-in"):
            self.assertIn(slot, prompt)

    def test_empty_slot_rejected_arabic(self):
        for kwargs in ({"persona": ""}, {"expression": "  "},
                       {"gesture": ""}, {"camera": ""}):
            with self.assertRaises(AvatarPromptError) as ctx:
                prompt_lib.build_performance_prompt(**kwargs)
            self.assertIn("فارغة", str(ctx.exception))

    def test_default_persona_used(self):
        prompt = prompt_lib.build_performance_prompt()
        self.assertIn("Persona: %s" % prompt_lib.DEFAULT_PERSONA,
                      prompt)
        self.assertIn("Camera: %s" % prompt_lib.DEFAULT_CAMERA,
                      prompt)

    def test_scene_types_differ_in_gesture(self):
        prompts = {t: prompt_lib.build_performance_prompt(
            scene_type=t) for t in prompt_lib.SCENE_TYPES}
        gestures = [p.split("Gesture: ")[1].split(". Camera:")[0]
                    for p in prompts.values()]
        self.assertEqual(len(set(gestures)), 3)

    def test_unknown_scene_type_rejected(self):
        with self.assertRaises(AvatarPromptError) as ctx:
            prompt_lib.build_performance_prompt(scene_type="dance")
        self.assertIn("غير معروف", str(ctx.exception))


class TestPromptFromScene(unittest.TestCase):
    def test_scene_dict(self):
        prompt = prompt_lib.prompt_from_scene(
            {"type": "dialogue", "persona": "A merchant"})
        self.assertIn("Persona: A merchant", prompt)
        self.assertIn("turns head slightly", prompt)

    def test_scene_type_defaults_to_narration(self):
        prompt = prompt_lib.prompt_from_scene({})
        self.assertIn("subtle head movements", prompt)

    def test_non_dict_rejected(self):
        with self.assertRaises(AvatarPromptError):
            prompt_lib.prompt_from_scene("narration")


class TestPromptToManifest(unittest.TestCase):
    def test_manifest_fields(self):
        out = prompt_lib.prompt_to_manifest("Persona: X.", "dialogue")
        self.assertEqual(out, {"performance_prompt": "Persona: X.",
                               "scene_type": "dialogue"})

    def test_empty_prompt_rejected(self):
        with self.assertRaises(AvatarPromptError):
            prompt_lib.prompt_to_manifest("  ")


if __name__ == "__main__":
    unittest.main()
