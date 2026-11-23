#!/usr/bin/env python3
"""اختبارات إعدادات الأفاتار المشتركة — جولة v0.1.38 (بنود 3 و6 و7).

معامل التوجيه 3–5، و8 خطوات افتراضيًا، وسياسة العمودي،
ودمج الإعدادات (افتراضيات ← config ← تجاوزات وظيفة).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import avatar_settings as settings_lib
from lib.avatar_settings import AvatarSettingsError


class TestAudioCfg(unittest.TestCase):
    def test_default_is_4(self):
        self.assertEqual(settings_lib.AUDIO_CFG_DEFAULT, 4.0)
        self.assertEqual(
            settings_lib.resolve_avatar_settings()["audio_cfg"], 4.0)

    def test_bounds_pass(self):
        self.assertEqual(settings_lib.validate_audio_cfg(3.0), 3.0)
        self.assertEqual(settings_lib.validate_audio_cfg(5.0), 5.0)
        self.assertEqual(settings_lib.validate_audio_cfg(4), 4.0)
        self.assertEqual(settings_lib.validate_audio_cfg("4.5"), 4.5)

    def test_out_of_range_rejected_arabic(self):
        for bad in (2.9, 5.1, 0, 10, None, True, "عالٍ"):
            with self.assertRaises(AvatarSettingsError) as ctx:
                settings_lib.validate_audio_cfg(bad)
            self.assertIn("بين 3 و5", str(ctx.exception))

    def test_override_respected(self):
        settings = settings_lib.resolve_avatar_settings(
            overrides={"audio_cfg": 3.5})
        self.assertEqual(settings["audio_cfg"], 3.5)

    def test_config_then_override(self):
        settings = settings_lib.resolve_avatar_settings(
            config={"avatar": {"audio_cfg": 3.0}},
            overrides={"audio_cfg": 5.0})
        self.assertEqual(settings["audio_cfg"], 5.0)
        settings = settings_lib.resolve_avatar_settings(
            config={"avatar": {"audio_cfg": 3.0}})
        self.assertEqual(settings["audio_cfg"], 3.0)


class TestSteps(unittest.TestCase):
    def test_default_8(self):
        self.assertEqual(settings_lib.STEPS_DEFAULT, 8)
        self.assertEqual(settings_lib.resolve_steps(), 8)
        self.assertEqual(settings_lib.resolve_steps(False), 8)

    def test_full_50(self):
        self.assertEqual(settings_lib.STEPS_FULL, 50)
        self.assertEqual(settings_lib.resolve_steps(True), 50)

    def test_steps_key_in_settings(self):
        settings = settings_lib.resolve_avatar_settings(
            overrides={"steps": 50})
        self.assertTrue(settings["full_steps"])
        settings = settings_lib.resolve_avatar_settings(
            overrides={"steps": 8})
        self.assertFalse(settings["full_steps"])
        with self.assertRaises(AvatarSettingsError) as ctx:
            settings_lib.resolve_avatar_settings(
                overrides={"steps": 20})
        self.assertIn("8 أو 50", str(ctx.exception))

    def test_manifest_exception_only_on_full(self):
        extra = settings_lib.avatar_manifest_extra()
        self.assertEqual(extra["avatar"]["steps"], 8)
        self.assertNotIn("steps_exception", extra["avatar"])
        extra = settings_lib.avatar_manifest_extra(
            {"full_steps": True})
        self.assertEqual(extra["avatar"]["steps"], 50)
        self.assertTrue(extra["avatar"]["steps_exception"])


class TestAspectPolicy(unittest.TestCase):
    def test_default_native(self):
        self.assertEqual(
            settings_lib.resolve_avatar_settings()["aspect_policy"],
            "native")

    def test_known_policies_pass(self):
        for policy in ("native", "crop", "rotate"):
            self.assertEqual(
                settings_lib.validate_aspect_policy(policy), policy)

    def test_pad_rejected_strict(self):
        with self.assertRaises(AvatarSettingsError) as ctx:
            settings_lib.validate_aspect_policy("pad")
        self.assertIn("الأشرطة الجانبية", str(ctx.exception))

    def test_pad_accepted_non_strict(self):
        self.assertEqual(
            settings_lib.validate_aspect_policy("pad", strict=False),
            "pad")

    def test_unknown_rejected(self):
        with self.assertRaises(AvatarSettingsError):
            settings_lib.validate_aspect_policy("stretch")


class TestResolve(unittest.TestCase):
    def test_unknown_keys_ignored(self):
        settings = settings_lib.resolve_avatar_settings(
            overrides={"audio_cfg": 4.0, "mystery_key": 123,
                       "another": "x"})
        self.assertEqual(set(settings),
                         {"audio_cfg", "full_steps", "aspect_policy",
                          "profile"})

    def test_profile_default_and_override(self):
        self.assertEqual(
            settings_lib.resolve_avatar_settings()["profile"],
            "t4x2-int8")
        settings = settings_lib.resolve_avatar_settings(
            overrides={"profile": "a100-bf16"})
        self.assertEqual(settings["profile"], "a100-bf16")

    def test_manifest_extra_fields(self):
        extra = settings_lib.avatar_manifest_extra(
            {"audio_cfg": 3.5, "aspect_policy": "crop"},
            prompt="A calm storyteller.", scene_type="narration",
            profile="rtx4090-int8")
        avatar = extra["avatar"]
        self.assertEqual(avatar["audio_cfg"], 3.5)
        self.assertEqual(avatar["aspect_policy"], "crop")
        self.assertEqual(avatar["profile"], "rtx4090-int8")
        self.assertEqual(avatar["performance_prompt"],
                         "A calm storyteller.")
        self.assertEqual(avatar["scene_type"], "narration")


if __name__ == "__main__":
    unittest.main()
