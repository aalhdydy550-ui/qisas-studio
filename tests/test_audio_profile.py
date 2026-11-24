#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات ملف أداء الصوت — جولة v0.1.38 (بند 2).

wav اصطناعي (نغمة 440Hz ‏3ث + صمت 1ث + نغمة 2ث): 6 سلال
طاقة، وسلة الصمت منخفضة جدًا، وخريطة الصمت تجد الفجوة،
وعبارة في الجزء الصاخب مؤكَّدة وفي الصامت لا؛ وملف مفقود
يرفع AudioProfileError؛ وحفظ/تحميل ذهابًا وإيابًا.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import audio_profile as profile_lib
from lib.audio_profile import AudioProfileError


def _make_wav(path):
    """نغمة صاخبة 2ث + نغمة هادئة (-12dB) ‏1ث + صمت 1ث
    + نغمة هادئة 2ث = 6 ثوانٍ (ffmpeg lavfi)."""
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
           "-f", "lavfi",
           "-i", "sine=frequency=440:duration=1,volume=0.25",
           "-f", "lavfi", "-i",
           "anullsrc=channel_layout=mono:sample_rate=48000:duration=1",
           "-f", "lavfi",
           "-i", "sine=frequency=440:duration=2,volume=0.25",
           "-filter_complex",
           "[0:a][1:a][2:a][3:a]concat=n=4:v=0:a=1",
           path]
    subprocess.run(cmd, check=True, timeout=60)


@unittest.skipUnless(shutil.which("ffmpeg"),
                     "ffmpeg غائب — بيئة CI")
class TestEnergyCurve(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.wav = os.path.join(cls.tmp.name, "tone.wav")
        _make_wav(cls.wav)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_six_buckets(self):
        curve = profile_lib.energy_curve(self.wav)
        self.assertEqual(len(curve), 6)
        self.assertEqual([b["second"] for b in curve], list(range(6)))

    def test_silence_bucket_much_lower(self):
        curve = profile_lib.energy_curve(self.wav)
        loud = curve[0]["rms_db"]
        quiet = curve[3]["rms_db"]
        self.assertIsNotNone(loud)
        self.assertIsNotNone(quiet)  # إطاران يعبران الحدود يرفعانها قليلًا
        self.assertLess(loud, -10.0)
        self.assertGreater(loud, -40.0)
        self.assertLess(quiet, loud - 10.0)  # ≥ 10dB أهدأ

    def test_missing_file_raises_arabic(self):
        with self.assertRaises(AudioProfileError) as ctx:
            profile_lib.energy_curve("/tmp/no-such-audio-xyz.wav")
        self.assertIn("غير موجود", str(ctx.exception))


@unittest.skipUnless(shutil.which("ffmpeg"),
                     "ffmpeg غائب — بيئة CI")
class TestSilenceMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.wav = os.path.join(cls.tmp.name, "tone.wav")
        _make_wav(cls.wav)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_finds_gap(self):
        silences = profile_lib.silence_map(self.wav)
        self.assertEqual(len(silences), 1)
        start, end, dur = silences[0]
        self.assertAlmostEqual(start, 3.0, delta=0.3)
        self.assertAlmostEqual(dur, 1.0, delta=0.3)


@unittest.skipUnless(shutil.which("ffmpeg"),
                     "ffmpeg غائب — بيئة CI")
class TestBuildProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.wav = os.path.join(cls.tmp.name, "tone.wav")
        _make_wav(cls.wav)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_profile_shape(self):
        prof = profile_lib.build_profile(self.wav)
        self.assertEqual(prof["audio"], os.path.abspath(self.wav))
        self.assertAlmostEqual(prof["duration_seconds"], 6.0, delta=0.2)
        self.assertEqual(len(prof["energy_curve"]), 6)
        self.assertEqual(len(prof["silences"]), 1)
        self.assertAlmostEqual(prof["silence_ratio"], 1.0 / 6.0,
                               delta=0.05)
        self.assertIsNotNone(prof["mean_db"])
        self.assertIsNotNone(prof["max_db"])
        self.assertEqual(prof["emphasized"], [])  # بلا عبارات

    def test_emphasized_phrase(self):
        phrases = [
            {"text": "عبارة صاخبة", "start": 0.0, "end": 2.0},
            {"text": "عبارة صامتة", "start": 3.0, "end": 4.0},
        ]
        prof = profile_lib.build_profile(self.wav, phrases=phrases)
        texts = [e["text"] for e in prof["emphasized"]]
        self.assertIn("عبارة صاخبة", texts)
        self.assertNotIn("عبارة صامتة", texts)

    def test_save_load_roundtrip(self):
        prof = profile_lib.build_profile(self.wav)
        path = os.path.join(self.tmp.name, "profile.json")
        self.assertEqual(profile_lib.save_profile(prof, path), path)
        loaded = profile_lib.load_profile(path)
        self.assertEqual(loaded["duration_seconds"],
                         prof["duration_seconds"])
        self.assertEqual(loaded["emphasized"], prof["emphasized"])

    def test_load_missing_raises(self):
        with self.assertRaises(AudioProfileError):
            profile_lib.load_profile("/tmp/no-such-profile-xyz.json")


if __name__ == "__main__":
    unittest.main()
