#!/usr/bin/env python3
"""اختبارات إصلاح فجوات الصمت التلقائي (lib.fix_audio).

تعمل بـ `python3 -m unittest tests.test_fix_audio -v` من مجلد studio.
تولّد مقاطع اختبار صغيرة بـffmpeg (بلا Veo وبلا شبكة):
سليم بلا فجوات، وفجوة صمت 2 ثانية وسط السرد، وبلا صوت أصلًا،
ونغمة مشهد 880 هرتز للتحقق من مزج صوت المشاهد.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import check as check_lib
from lib import fix_audio as fix_lib


def _ffmpeg(*args):
    cmd = ["ffmpeg", "-y", "-v", "error"] + list(args)
    subprocess.run(cmd, check=True, timeout=300)


def _make_video(out, duration=10, audio=True, mute_between=None):
    """ولّد مقطع اختبار: خلفية لونية + نغمة sine (أو بلا صوت)."""
    args = ["-f", "lavfi", "-i",
            "color=c=0x2a2a2a:s=720x1280:r=30:d=%s" % duration]
    if audio:
        args += ["-f", "lavfi", "-i",
                 "sine=frequency=440:sample_rate=48000:duration=%s"
                 % duration]
    if audio and mute_between:
        args += ["-af", "volume=0:enable='between(t,%s,%s)'"
                 % mute_between]
    args += ["-t", str(duration), "-c:v", "libx264", "-preset",
             "veryfast", "-crf", "28", "-pix_fmt", "yuv420p"]
    if audio:
        args += ["-c:a", "aac"]
    args.append(out)
    _ffmpeg(*args)


def _band_level(path, freq, seconds=5):
    """متوسط مستوى الصوت (ديسيبل) في نطاق ضيق حول تردد معين.

    يرجع None إن كان النطاق صامتًا تمامًا (-inf).
    """
    proc = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", path, "-t", str(seconds),
         "-af", "bandpass=f=%d:width_type=h:width=2,volumedetect"
         % freq, "-f", "null", "-"],
        capture_output=True, text=True, timeout=300)
    mean = re.search(r"mean_volume: (-?[0-9.]+|-inf) dB",
                     proc.stderr or "")
    if not mean or mean.group(1) == "-inf":
        return None
    return float(mean.group(1))


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "ffmpeg/ffprobe غير متاحين")
class TestFixAudio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.mkdtemp(prefix="fix-audio-test-")
        cls.clean = os.path.join(cls.td, "clean.mp4")
        _make_video(cls.clean, duration=10)
        cls.gap = os.path.join(cls.td, "gap.mp4")
        _make_video(cls.gap, duration=10, mute_between=(4, 6))
        cls.no_audio = os.path.join(cls.td, "no-audio.mp4")
        _make_video(cls.no_audio, duration=10, audio=False)
        cls.scene_tone = os.path.join(cls.td, "scene-tone.wav")
        _ffmpeg("-f", "lavfi", "-i",
                "sine=frequency=880:sample_rate=48000:duration=5",
                "-c:a", "pcm_s16le", cls.scene_tone)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.td, ignore_errors=True)

    def test_clean_video_returned_unchanged(self):
        result = fix_lib.fix_silence_gaps(self.clean)
        self.assertFalse(result["fixed"])
        self.assertEqual(result["output"], os.path.abspath(self.clean))
        self.assertEqual(result["gaps_before"], [])
        self.assertTrue(result["silence_check_before"])
        # لم يُنشأ أي ملف -fixed بجانب الأصلي.
        self.assertFalse(os.path.isfile(
            fix_lib.default_out_path(self.clean)))

    def test_gap_video_fixed_and_silence_passes(self):
        out = os.path.join(self.td, "gap-fixed-test.mp4")
        result = fix_lib.fix_silence_gaps(self.gap, out_path=out)
        self.assertTrue(result["fixed"])
        self.assertEqual(len(result["gaps_before"]), 1)
        start, end, dur = result["gaps_before"][0]
        self.assertAlmostEqual(start, 4.0, delta=0.6)
        self.assertAlmostEqual(end, 6.0, delta=0.6)
        self.assertGreaterEqual(dur, 1.0)
        self.assertEqual(result["gaps_after"], [])
        self.assertTrue(result["silence_check_after"])
        # فحص check.py نفسه ينجح على الناتج.
        silences = check_lib.detect_silences(out)
        ok, _detail = check_lib.eval_silences(
            silences, result["duration_after"], long_mode=False)
        self.assertTrue(ok)

    def test_duration_unchanged(self):
        out = os.path.join(self.td, "gap-dur.mp4")
        result = fix_lib.fix_silence_gaps(self.gap, out_path=out)
        self.assertLess(abs(result["duration_after"]
                            - result["duration_before"]), 0.05)
        before = check_lib.probe(self.gap)["duration"]
        after = check_lib.probe(out)["duration"]
        self.assertLess(abs(after - before), 0.05)

    def test_missing_video_raises_arabic(self):
        with self.assertRaises(fix_lib.FixAudioError) as cm:
            fix_lib.fix_silence_gaps(os.path.join(self.td, "nope.mp4"))
        self.assertIn("غير موجود", str(cm.exception))

    def test_missing_scene_audio_raises_arabic(self):
        with self.assertRaises(fix_lib.FixAudioError) as cm:
            fix_lib.fix_silence_gaps(
                self.gap,
                scene_audio_paths=[os.path.join(self.td, "nope.wav")])
        self.assertIn("غير موجود", str(cm.exception))

    def test_out_path_same_as_input_raises(self):
        with self.assertRaises(fix_lib.FixAudioError):
            fix_lib.fix_silence_gaps(self.gap, out_path=self.gap)

    def test_scene_audio_mixed_at_target(self):
        out = os.path.join(self.td, "gap-scene.mp4")
        result = fix_lib.fix_silence_gaps(
            self.gap, scene_audio_paths=[self.scene_tone], out_path=out)
        self.assertTrue(result["fixed"])
        self.assertEqual(len(result["scene_audio"]), 1)
        self.assertEqual(result["scene_audio"][0]["path"],
                         os.path.abspath(self.scene_tone))
        # نغمة المشهد 880 هرتز حاضرة في المزيج عند ~-28 ديسيبل.
        level = _band_level(out, 880)
        self.assertIsNotNone(level)
        self.assertGreater(level, -40.0)
        self.assertLess(level, -15.0)
        # وبلا صوت مشاهد يكاد النطاق نفسه يكون صامتًا.
        plain = os.path.join(self.td, "gap-plain.mp4")
        fix_lib.fix_silence_gaps(self.gap, out_path=plain)
        plain_level = _band_level(plain, 880)
        self.assertTrue(plain_level is None or plain_level < -60.0)

    def test_no_audio_video_gets_audio_track(self):
        out = os.path.join(self.td, "no-audio-fixed.mp4")
        result = fix_lib.fix_silence_gaps(self.no_audio, out_path=out)
        self.assertTrue(result["fixed"])
        self.assertTrue(check_lib.probe(out)["has_audio"])
        self.assertEqual(result["gaps_after"], [])
        self.assertTrue(result["silence_check_after"])

    def test_default_out_path_naming(self):
        self.assertTrue(
            fix_lib.default_out_path("/tmp/x/video.mp4").endswith(
                "video-fixed.mp4"))

    def test_middle_gaps_ignore_edges(self):
        # صمت البداية والنهاية لا يُحتسبان؛ ووسطي ≥1 ثانية يُحتسب.
        self.assertEqual(fix_lib.middle_gaps([(0.0, 1.5, 1.5)], 10), [])
        self.assertEqual(fix_lib.middle_gaps([(8.5, 10.0, 1.5)], 10), [])
        self.assertEqual(len(fix_lib.middle_gaps(
            [(4.0, 6.0, 2.0)], 10)), 1)
        self.assertEqual(fix_lib.middle_gaps([(4.0, 4.5, 0.5)], 10), [])


if __name__ == "__main__":
    unittest.main()
