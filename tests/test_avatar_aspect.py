#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
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
from lib.avatar_aspect import AvatarAspectError, ReframeError
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


class TestReframeCrop(unittest.TestCase):
    """هندسة إعادة التأطير — جولة v0.1.39 (أ2-7)، بلا ffmpeg."""

    def test_landscape_center_crop(self):
        crop = aspect_lib.reframe_crop(1280, 720)
        # نسبة الهدف 9:16 من ارتفاع 720 → عرض قصّ 404 (زوجي)
        # وموضع مركزي 438.
        self.assertEqual(crop["width"], 404)
        self.assertEqual(crop["height"], 720)
        self.assertEqual(crop["x"], 438)
        self.assertEqual(crop["y"], 0)
        self.assertEqual(crop["out_width"], 720)
        self.assertEqual(crop["out_height"], 1280)
        self.assertTrue(crop["needs_reframe"])

    def test_focus_moves_crop_window(self):
        center = aspect_lib.reframe_crop(1280, 720, focus_x=0.5)
        left = aspect_lib.reframe_crop(1280, 720, focus_x=0.1)
        right = aspect_lib.reframe_crop(1280, 720, focus_x=0.9)
        self.assertEqual(left["x"], 0)
        self.assertEqual(right["x"], 876)
        self.assertLess(left["x"], center["x"])
        self.assertLess(center["x"], right["x"])
        # نفس أبعاد النافذة مهما تحركت نقطة التركيز.
        for c in (left, center, right):
            self.assertEqual((c["width"], c["height"]), (404, 720))

    def test_focus_edges_clamp_inside_frame(self):
        self.assertEqual(aspect_lib.reframe_crop(1280, 720,
                                                 focus_x=0.0)["x"], 0)
        self.assertEqual(aspect_lib.reframe_crop(1280, 720,
                                                 focus_x=1.0)["x"], 876)

    def test_focus_invalid_rejected(self):
        for bad in (-0.1, 1.5, "يسار", None, True):
            with self.assertRaises(ReframeError, msg=repr(bad)):
                aspect_lib.reframe_crop(1280, 720, focus_x=bad)

    def test_safety_margin_keeps_crop_off_edges(self):
        center = aspect_lib.reframe_crop(1280, 720, safety_margin=100)
        self.assertEqual(center["x"], 438)
        right = aspect_lib.reframe_crop(1280, 720, focus_x=0.9,
                                        safety_margin=100)
        # الحد الأقصى يتراجع بمقدار الهامش: 1280-100-404.
        self.assertEqual(right["x"], 776)
        left = aspect_lib.reframe_crop(1280, 720, focus_x=0.0,
                                       safety_margin=100)
        self.assertEqual(left["x"], 100)

    def test_safety_margin_too_big_rejected(self):
        with self.assertRaises(ReframeError):
            aspect_lib.reframe_crop(1280, 720, safety_margin=500)
        with self.assertRaises(ReframeError):
            aspect_lib.reframe_crop(1280, 720, safety_margin=-1)

    def test_vertical_passes_through_unchanged(self):
        crop = aspect_lib.reframe_crop(720, 1280)
        self.assertFalse(crop["needs_reframe"])
        self.assertEqual((crop["x"], crop["y"],
                          crop["width"], crop["height"]),
                         (0, 0, 720, 1280))
        self.assertEqual((crop["out_width"], crop["out_height"]),
                         (720, 1280))

    def test_vertical_other_size_passes_through(self):
        crop = aspect_lib.reframe_crop(1080, 1920)
        self.assertFalse(crop["needs_reframe"])
        self.assertEqual((crop["out_width"], crop["out_height"]),
                         (1080, 1920))

    def test_square_crops_width(self):
        crop = aspect_lib.reframe_crop(720, 720)
        self.assertTrue(crop["needs_reframe"])
        self.assertEqual((crop["width"], crop["height"]), (404, 720))
        self.assertEqual((crop["out_width"], crop["out_height"]),
                         (720, 1280))

    def test_bad_dimensions_rejected(self):
        for w, h in ((0, 720), (1280, 0), (-1280, 720), ("1280", 720)):
            with self.assertRaises(ReframeError, msg=repr((w, h))):
                aspect_lib.reframe_crop(w, h)

    def test_build_command_landscape_crops_and_scales(self):
        crop = aspect_lib.reframe_crop(1280, 720)
        cmd = aspect_lib.build_reframe_command("in.mp4", "out.mp4",
                                               crop)
        joined = " ".join(cmd)
        self.assertIn("crop=404:720:438:0", joined)
        self.assertIn("scale=720:1280", joined)
        self.assertIn("libx264", joined)

    def test_build_command_vertical_copies_without_reencode(self):
        crop = aspect_lib.reframe_crop(720, 1280)
        cmd = aspect_lib.build_reframe_command("in.mp4", "out.mp4",
                                               crop)
        self.assertIn("-c", cmd)
        self.assertIn("copy", cmd)
        self.assertFalse(any("crop=" in a for a in cmd))


@unittest.skipUnless(shutil.which("ffmpeg") is not None,
                     "ffmpeg غير موجود")
class TestReframeVideo(unittest.TestCase):
    """إعادة تأطير فعلية بمقاطع مولّدة — جولة v0.1.39 (أ2-7)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="reframe-")
        self.video_h = os.path.join(self.tmp, "h.mp4")
        self.video_v = os.path.join(self.tmp, "v.mp4")
        for out, size in ((self.video_h, "1280x720"),
                          (self.video_v, "720x1280")):
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f",
                            "lavfi", "-i",
                            "color=c=0x336699:s=%s:d=1" % size,
                            "-f", "lavfi", "-i",
                            "sine=frequency=440:d=1",
                            "-shortest", "-c:v", "libx264",
                            "-c:a", "aac", out],
                           check=True, timeout=60)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_landscape_reframes_to_exactly_720x1280(self):
        out = os.path.join(self.tmp, "v-out.mp4")
        res = aspect_lib.reframe_video(self.video_h, out)
        self.assertTrue(res["reframed"])
        self.assertEqual((res["out_width"], res["out_height"]),
                         (720, 1280))
        self.assertEqual(aspect_lib.probe_dimensions(out),
                         {"width": 720, "height": 1280})

    def test_focus_right_changes_output_pixels(self):
        # مصدر بنمط testsrc المتباين أفقيًا: قصّ يسار وقصّ يمين
        # يجب أن يعطيا إطارين مختلفين فعلًا (لا مجرد حساب).
        src = os.path.join(self.tmp, "pattern.mp4")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f",
                        "lavfi", "-i",
                        "testsrc=s=1280x720:d=1",
                        "-f", "lavfi", "-i",
                        "sine=frequency=440:d=1",
                        "-shortest", "-c:v", "libx264",
                        "-c:a", "aac", src],
                       check=True, timeout=60)
        frames = []
        for focus, name in ((0.1, "left.mp4"), (0.9, "right.mp4")):
            out = os.path.join(self.tmp, name)
            aspect_lib.reframe_video(src, out, focus_x=focus)
            self.assertEqual(aspect_lib.probe_dimensions(out),
                             {"width": 720, "height": 1280})
            frame = os.path.join(self.tmp, name + ".png")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", out,
                            "-frames:v", "1", frame],
                           check=True, timeout=60)
            with open(frame, "rb") as f:
                frames.append(f.read())
        self.assertNotEqual(frames[0], frames[1])
        left = aspect_lib.reframe_crop(1280, 720, focus_x=0.1)
        right = aspect_lib.reframe_crop(1280, 720, focus_x=0.9)
        self.assertNotEqual(left["x"], right["x"])

    def test_vertical_passes_through_without_reencode(self):
        out = os.path.join(self.tmp, "v-copy.mp4")
        res = aspect_lib.reframe_video(self.video_v, out)
        self.assertFalse(res["reframed"])
        self.assertEqual((res["out_width"], res["out_height"]),
                         (720, 1280))
        self.assertEqual(aspect_lib.probe_dimensions(out),
                         {"width": 720, "height": 1280})

    def test_missing_file_raises(self):
        with self.assertRaises(ReframeError):
            aspect_lib.reframe_video(os.path.join(self.tmp, "no.mp4"),
                                     os.path.join(self.tmp, "o.mp4"))
        with self.assertRaises(ReframeError):
            aspect_lib.probe_dimensions(
                os.path.join(self.tmp, "no.mp4"))


if __name__ == "__main__":
    unittest.main()
