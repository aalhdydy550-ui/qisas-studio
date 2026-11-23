#!/usr/bin/env python3
"""اختبارات ملفات تعريف العتاد — جولة v0.1.38 (بند 5).

الملفات الثلاثة تولّد أعلامًا صالحة؛ وfp8+int8 يُرفضان؛
وملف مجهول يُرفض؛ و--use_int8 في ملفي INT8 فقط؛ والدقة
480p/720p فقط.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import avatar_profiles as profiles_lib
from lib.avatar_profiles import AvatarProfilesError


class TestProfiles(unittest.TestCase):
    def test_three_profiles_listed(self):
        self.assertEqual(profiles_lib.list_profiles(),
                         ["a100-bf16", "rtx4090-int8", "t4x2-int8"])

    def test_flags_valid_for_all(self):
        for name in profiles_lib.list_profiles():
            flags = profiles_lib.profile_flags(name)
            # الأعلام المولَّدة تمر من التحقق نفسه
            self.assertEqual(profiles_lib.validate_flags(flags), flags)
            self.assertIn("--resolution", flags)
            res = flags[flags.index("--resolution") + 1]
            self.assertIn(res, ("480p", "720p"))

    def test_int8_only_in_int8_profiles(self):
        self.assertIn("--use_int8",
                      profiles_lib.profile_flags("t4x2-int8"))
        self.assertIn("--use_int8",
                      profiles_lib.profile_flags("rtx4090-int8"))
        self.assertNotIn("--use_int8",
                         profiles_lib.profile_flags("a100-bf16"))

    def test_t4x2_uses_two_gpus(self):
        flags = profiles_lib.profile_flags("t4x2-int8")
        self.assertIn("--nproc_per_node=2", flags)
        self.assertIn("--context_parallel_size=2", flags)
        self.assertIn("480p", flags)

    def test_unknown_profile_rejected_arabic(self):
        with self.assertRaises(AvatarProfilesError) as ctx:
            profiles_lib.get_profile("h100-fp8")
        self.assertIn("غير معروف", str(ctx.exception))
        with self.assertRaises(AvatarProfilesError):
            profiles_lib.profile_flags("h100-fp8")

    def test_fp8_and_int8_rejected(self):
        with self.assertRaises(AvatarProfilesError) as ctx:
            profiles_lib.validate_flags(
                ["--use_fp8", "--use_int8", "--resolution", "480p"])
        self.assertIn("--use_fp8", str(ctx.exception))

    def test_profile_for_job(self):
        self.assertEqual(
            profiles_lib.profile_for_job({})["resolution"], "480p")
        self.assertEqual(
            profiles_lib.profile_for_job(
                {"settings": {"profile": "a100-bf16"}})["resolution"],
            "720p")
        with self.assertRaises(AvatarProfilesError):
            profiles_lib.profile_for_job(
                {"settings": {"profile": "nope"}})


if __name__ == "__main__":
    unittest.main()
