#!/usr/bin/env python3
"""اختبارات نسب العرض — جولة v0.1.38 (بند 3).

عمودي فقط وبأبعاد قابلة للقسمة على 8؛ والمربع والأفقي
وغير القابل للقسمة على 8 تُرفض؛ والملفان الرسميان
موجودان والمثبت بصريًا هو 720x1092 فقط.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import avatar_aspect as aspect_lib
from lib import check as check_lib
from lib.avatar_aspect import AvatarAspectError
from lib.check import CheckError


class TestValidateAspect(unittest.TestCase):
    def test_vertical_ok(self):
        self.assertEqual(
            aspect_lib.validate_aspect(720, 1280),
            {"width": 720, "height": 1280})

    def test_pilot_portrait_is_not_an_output_aspect(self):
        # 720×1092 حجم بورتريه مدخل لا يقبل القسمة على 8
        # (1092÷8 = 136.5) — يُرفض كأبعاد مخرج.
        with self.assertRaises(AvatarAspectError):
            aspect_lib.validate_aspect(720, 1092)

    def test_square_rejected(self):
        with self.assertRaises(AvatarAspectError) as ctx:
            aspect_lib.validate_aspect(720, 720)
        self.assertIn("عمودي", str(ctx.exception))

    def test_horizontal_rejected(self):
        with self.assertRaises(AvatarAspectError):
            aspect_lib.validate_aspect(1280, 720)

    def test_not_divisible_by_8_rejected(self):
        with self.assertRaises(AvatarAspectError) as ctx:
            aspect_lib.validate_aspect(720, 1091)
        self.assertIn("8", str(ctx.exception))
        with self.assertRaises(AvatarAspectError):
            aspect_lib.validate_aspect(719, 1280)


class TestParseAspect(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(aspect_lib.parse_aspect("720x1280"),
                         {"width": 720, "height": 1280})

    def test_parse_bad(self):
        for bad in ("720", "720x", "x1280", "abcxdef", "720:1280",
                    "1280x720"):
            with self.assertRaises(AvatarAspectError, msg=bad):
                aspect_lib.parse_aspect(bad)


class TestOfficialProfiles(unittest.TestCase):
    def test_official_are_landscape_only(self):
        # الملفان الرسميان في السكربت أفقيان (480×832 و768×1280).
        self.assertEqual(aspect_lib.official_profile("480p"),
                         {"width": 480, "height": 832})
        self.assertEqual(aspect_lib.official_profile("720p"),
                         {"width": 768, "height": 1280})

    def test_pilot_portrait_verified(self):
        portrait = aspect_lib.pilot_portrait()
        self.assertEqual(portrait["width"], 720)
        self.assertEqual(portrait["height"], 1092)
        self.assertTrue(portrait["verified"])

    def test_unknown_profile(self):
        with self.assertRaises(AvatarAspectError):
            aspect_lib.official_profile("720x1280")


class TestAspectForJob(unittest.TestCase):
    def test_default(self):
        self.assertEqual(aspect_lib.aspect_for_job({}),
                         {"width": 720, "height": 1280})
        self.assertEqual(aspect_lib.aspect_for_job(None),
                         {"width": 720, "height": 1280})

    def test_from_settings(self):
        self.assertEqual(
            aspect_lib.aspect_for_job(
                {"settings": {"aspect": "720x1280"}}),
            {"width": 720, "height": 1280})
        self.assertEqual(
            aspect_lib.aspect_for_job(
                {"settings": {"aspect": {"width": 720,
                                         "height": 1280}}}),
            {"width": 720, "height": 1280})

    def test_invalid_in_job_rejected(self):
        with self.assertRaises(AvatarAspectError):
            aspect_lib.aspect_for_job(
                { "settings": {"aspect": "1280x720"}})


@unittest.skipUnless(shutil.which("ffmpeg") is not None,
                     "ffmpeg غير موجود")
class TestCheckAvatarAspect(unittest.TestCase):
    """قاعدة الأبعاد في lib/check.py (تصميم §7)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="avatar-aspect-")
        self.video_v = os.path.join(self.tmp, "v.mp4")
        self.video_h = os.path.join(self.tmp, "h.mp4")
        self.image_v = os.path.join(self.tmp, "portrait.png")
        self.image_wide = os.path.join(self.tmp, "wide.png")
        for out, size in ((self.video_v, "720x1280"),
                          (self.video_h, "1280x720")):
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f",
                            "lavfi", "-i",
                            "color=c=0x336699:s=%s:d=1" % size,
                            "-frames:v", "1", out],
                           check=True, timeout=60)
        for out, size in ((self.image_v, "720x1280"),
                          (self.image_wide, "720x960")):
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f",
                            "lavfi", "-i",
                            "color=c=0x336699:s=%s:d=1" % size,
                            "-frames:v", "1", out],
                           check=True, timeout=60)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_native_matching_ratios_ok(self):
        result = check_lib.check_avatar_aspect(
            self.video_v, self.image_v, policy="native")
        self.assertEqual(result["level"], "ok")

    def test_native_different_ratios_warn(self):
        result = check_lib.check_avatar_aspect(
            self.video_v, self.image_wide, policy="native")
        self.assertEqual(result["level"], "warn")

    def test_crop_vertical_ok(self):
        result = check_lib.check_avatar_aspect(
            self.video_v, self.image_wide, policy="crop")
        self.assertEqual(result["level"], "ok")

    def test_crop_horizontal_warn(self):
        result = check_lib.check_avatar_aspect(
            self.video_h, self.image_v, policy="crop")
        self.assertEqual(result["level"], "warn")

    def test_pad_always_warn(self):
        result = check_lib.check_avatar_aspect(
            self.video_v, self.image_v, policy="pad")
        self.assertEqual(result["level"], "warn")

    def test_rotate_horizontal_warn_vertical_ok(self):
        self.assertEqual(check_lib.check_avatar_aspect(
            self.video_h, self.image_v, policy="rotate")["level"],
            "warn")
        self.assertEqual(check_lib.check_avatar_aspect(
            self.video_v, self.image_v, policy="rotate")["level"],
            "ok")

    def test_missing_image_raises(self):
        with self.assertRaises(CheckError):
            check_lib.check_avatar_aspect(
                self.video_v, os.path.join(self.tmp, "no.png"))

    def test_unknown_policy_raises(self):
        with self.assertRaises(CheckError):
            check_lib.check_avatar_aspect(
                self.video_v, self.image_v, policy="weird")


if __name__ == "__main__":
    unittest.main()
