#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات التدرج اللوني LUT (lib.lut_grade).

تعمل بـ `python3 -m unittest tests.test_lut_grade -v` من مجلد studio.
تولّد فيديو اختبار صغيرًا بـffmpeg (بلا Veo وبلا شبكة) وتطبّق
الـpresets الأربعة، وتتحقق أن الخرج موجود ومدته مطابقة وأن
preset «هادئ» يرفع فعلًا متوسط السطوع (رفع الظلال).
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import check as check_lib
from lib import lut_grade as lut_lib


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error"] + list(args),
                   check=True, timeout=300)


def _make_video(out, duration=3, color="0x404040"):
    _ffmpeg("-f", "lavfi", "-i",
            "color=c=%s:s=720x1280:r=30:d=%s" % (color, duration),
            "-f", "lavfi", "-i",
            "sine=frequency=440:sample_rate=48000:duration=%s" % duration,
            "-t", str(duration), "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "28", "-pix_fmt", "yuv420p", "-c:a", "aac", out)


def _yavg(path):
    """متوسط سطوع Y للإطار الأول عبر signalstats + metadata=print."""
    proc = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", path, "-vf",
         "signalstats,metadata=print:key=lavfi.signalstats.YAVG",
         "-frames:v", "1", "-f", "null", "-"],
        capture_output=True, text=True, timeout=120)
    m = re.search(r"lavfi\.signalstats\.YAVG=([0-9.]+)",
                  proc.stderr or "")
    return float(m.group(1)) if m else None


class TestPresets(unittest.TestCase):
    def test_list_presets_four(self):
        presets = lut_lib.list_presets()
        self.assertEqual([p["name"] for p in presets],
                         ["cinematic", "soft", "vivid", "warm"])
        for p in presets:
            self.assertTrue(p["exists"])
            self.assertTrue(p["description"])

    def test_generate_deterministic(self):
        tmp = tempfile.mkdtemp(prefix="lut-test-")
        p1 = lut_lib.generate_lut(
            "warm", os.path.join(tmp, "a.cube"))
        p2 = lut_lib.generate_lut(
            "warm", os.path.join(tmp, "b.cube"))
        with open(p1, "rb") as f:
            b1 = f.read()
        with open(p2, "rb") as f:
            b2 = f.read()
        # نفس البايتات عدا سطر التعليق (فيه اسم الملف)
        body1 = b"\n".join(b1.split(b"\n")[1:])
        body2 = b"\n".join(b2.split(b"\n")[1:])
        self.assertEqual(body1, body2)
        self.assertIn(b"LUT_3D_SIZE 16", b1)
        # 4096 نقطة شبكة + 5 أسطر ترويسة
        self.assertEqual(len(b1.decode("utf-8").splitlines()), 4101)

    def test_unknown_preset(self):
        with self.assertRaises(lut_lib.LutError):
            lut_lib.generate_lut("nope")
        with self.assertRaises(lut_lib.LutError):
            lut_lib.apply_lut("/tmp/x.mp4", "nope")


class TestApplyLut(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lut-test-")
        self.video = os.path.join(self.tmp, "in.mp4")
        _make_video(self.video)

    def test_apply_all_presets(self):
        for preset in ("warm", "vivid", "cinematic", "soft"):
            out = os.path.join(self.tmp, "%s.mp4" % preset)
            result = lut_lib.apply_lut(self.video, preset, out)
            self.assertTrue(os.path.isfile(out))
            self.assertEqual(result["preset"], preset)
            self.assertAlmostEqual(result["duration_before"], 3.0,
                                   delta=0.1)
            self.assertAlmostEqual(result["duration_after"], 3.0,
                                   delta=0.1)
            info = check_lib.probe(out)
            self.assertEqual((info["width"], info["height"]),
                             (720, 1280))
            self.assertTrue(info["has_audio"])

    def test_soft_lifts_brightness(self):
        """preset «هادئ» يرفع الظلال — فيديو رمادي داكن يسطع فعلًا."""
        before = _yavg(self.video)
        out = os.path.join(self.tmp, "soft.mp4")
        lut_lib.apply_lut(self.video, "soft", out)
        after = _yavg(out)
        self.assertIsNotNone(before)
        self.assertIsNotNone(after)
        self.assertGreater(after, before + 5,
                           "سطوع soft (%s) لم يرتفع عن الأصل (%s)"
                           % (after, before))

    def test_missing_video(self):
        with self.assertRaises(lut_lib.LutError):
            lut_lib.apply_lut(os.path.join(self.tmp, "no.mp4"), "warm")

    def test_same_path_rejected(self):
        with self.assertRaises(lut_lib.LutError):
            lut_lib.apply_lut(self.video, "warm", self.video)


if __name__ == "__main__":
    unittest.main()
