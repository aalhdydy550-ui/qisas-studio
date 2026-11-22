#!/usr/bin/env python3
"""اختبارات فحص الجودة قبل النشر (lib.check).

تعمل بـ `python3 -m unittest discover -s tests -v`.
تولّد مقاطع اختبار صغيرة بـffmpeg (بلا Veo وبلا شبكة):
سليم 45 ثانية، وصمت مُصطنع وسط السرد، وبلا صوت، ومقاس
خاطئ، وبلا شعار، وقصير، وصمت ختامي يُستثنى من فحص الصمت.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import check as check_lib

GOLD_BOX = "drawbox=x=600:y=20:w=100:h=100:color=0xE0AF5C:t=fill"


def _ffmpeg(*args):
    cmd = ["ffmpeg", "-y", "-v", "error"] + list(args)
    subprocess.run(cmd, check=True, timeout=300)


def _make_video(out, duration=10, size="720x1280", audio=True,
                audio_duration=None, mute_between=None, gold=False):
    """ولّد مقطع اختبار: خلفية لونية + نغمة sine (أو بلا صوت)."""
    args = ["-f", "lavfi", "-i",
            "color=c=0x2a2a2a:s=%s:r=30:d=%s" % (size, duration)]
    if audio:
        ad = audio_duration or duration
        args += ["-f", "lavfi", "-i",
                 "sine=frequency=440:sample_rate=48000:duration=%s" % ad]
    vf = []
    if gold:
        vf.append(GOLD_BOX)
    if vf:
        args += ["-vf", ",".join(vf)]
    if audio and mute_between:
        args += ["-af", "volume=0:enable='between(t,%s,%s)'"
                 % mute_between]
    args += ["-t", str(duration), "-c:v", "libx264", "-preset",
             "veryfast", "-crf", "28", "-pix_fmt", "yuv420p"]
    if audio:
        args += ["-c:a", "aac"]
    args.append(out)
    _ffmpeg(*args)


def _check_by_name(result, name):
    for c in result["checks"]:
        if c["name"] == name:
            return c
    raise AssertionError("فحص %s غائب من التقرير" % name)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "ffmpeg/ffprobe غير متاحين")
class TestCheckFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.mkdtemp(prefix="check-test-")
        cls.good = os.path.join(cls.td, "good.mp4")
        _make_video(cls.good, duration=45, gold=True)
        cls.silent_gap = os.path.join(cls.td, "silent-gap.mp4")
        _make_video(cls.silent_gap, duration=10, gold=True,
                    mute_between=(4, 6))
        cls.no_audio = os.path.join(cls.td, "no-audio.mp4")
        _make_video(cls.no_audio, duration=10, gold=True, audio=False)
        cls.wrong_size = os.path.join(cls.td, "wrong-size.mp4")
        _make_video(cls.wrong_size, duration=10, size="640x360",
                    gold=True)
        cls.no_logo = os.path.join(cls.td, "no-logo.mp4")
        _make_video(cls.no_logo, duration=10, gold=False)
        cls.short = os.path.join(cls.td, "short.mp4")
        _make_video(cls.short, duration=30, gold=True)
        cls.trailing = os.path.join(cls.td, "trailing.mp4")
        _make_video(cls.trailing, duration=12, gold=True,
                    audio_duration=10.5)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.td, ignore_errors=True)

    def test_good_video_passes_all(self):
        result = check_lib.run_checks(self.good)
        self.assertTrue(result["passed"], check_lib.format_report(result))

    def test_dash_leading_filename(self):
        # اختبار انحدار (اختراق 2026-11-22): ملف اسمه يبدأ
        # بشرطة كان يُفسَّر كخيار من ffprobe فيفشل الفحص.
        dash = os.path.join(self.td, "-dash.mp4")
        shutil.copy(self.good, dash)
        old_cwd = os.getcwd()
        try:
            os.chdir(self.td)
            result = check_lib.run_checks("-dash.mp4")
        finally:
            os.chdir(old_cwd)
        self.assertTrue(result["passed"], check_lib.format_report(result))
        self.assertEqual(result["duration"], 45)
        self.assertEqual((result["width"], result["height"]),
                         (720, 1280))
        for c in result["checks"]:
            self.assertTrue(c["ok"], c)

    def test_artificial_silence_fails_silence_check(self):
        result = check_lib.run_checks(self.silent_gap)
        self.assertFalse(result["passed"])
        c = _check_by_name(result, "الصمت عند الفواصل")
        self.assertFalse(c["ok"])
        # الصمت المُصطنع 4–6 ثوانٍ يظهر في التفصيل.
        self.assertIn("4", c["detail"])

    def test_no_audio_fails_audio_check(self):
        result = check_lib.run_checks(self.no_audio)
        self.assertFalse(result["passed"])
        c = _check_by_name(result, "الصوت")
        self.assertFalse(c["ok"])
        self.assertIn("لا يوجد مسار صوتي", c["detail"])

    def test_wrong_size_fails_size_check(self):
        result = check_lib.run_checks(self.wrong_size)
        c = _check_by_name(result, "المقاس")
        self.assertFalse(c["ok"])
        self.assertIn("640x360", c["detail"])

    def test_no_logo_fails_logo_check(self):
        result = check_lib.run_checks(self.no_logo)
        c = _check_by_name(result, "شعار الصفحة")
        self.assertFalse(c["ok"])

    def test_short_video_fails_duration_only(self):
        result = check_lib.run_checks(self.short)
        c = _check_by_name(result, "المدة")
        self.assertFalse(c["ok"])
        self.assertIn("30", c["detail"])
        # باقي الفحوصات تنجح — القصر وحده سبب الفشل.
        for other in result["checks"]:
            if other["name"] != "المدة":
                self.assertTrue(other["ok"], other)

    def test_trailing_silence_is_ignored(self):
        # صوت ينتهي قبل نهاية الفيديو بـ1.5 ثانية (خاتمة) — لا يُحتسب.
        result = check_lib.run_checks(self.trailing)
        c = _check_by_name(result, "الصمت عند الفواصل")
        self.assertTrue(c["ok"], c)

    def test_missing_file_raises(self):
        with self.assertRaises(check_lib.CheckError):
            check_lib.run_checks(os.path.join(self.td, "nope.mp4"))

    def test_report_format_arabic_pass_fail(self):
        result = check_lib.run_checks(self.good)
        text = check_lib.format_report(result)
        self.assertIn("[PASS]", text)
        self.assertIn("جاهز للنشر", text)
        bad = check_lib.run_checks(self.no_logo)
        self.assertIn("[FAIL]", check_lib.format_report(bad))


class TestCheckRules(unittest.TestCase):
    def test_duration_ranges(self):
        self.assertTrue(check_lib.eval_duration(45, False)[0])
        self.assertTrue(check_lib.eval_duration(40, False)[0])
        self.assertTrue(check_lib.eval_duration(60, False)[0])
        self.assertFalse(check_lib.eval_duration(39.9, False)[0])
        self.assertFalse(check_lib.eval_duration(60.1, False)[0])
        self.assertTrue(check_lib.eval_duration(600, True)[0])
        self.assertFalse(check_lib.eval_duration(300, True)[0])
        self.assertFalse(check_lib.eval_duration(721, True)[0])

    def test_silence_rules(self):
        # صمت وسط الفيديو يفشل؛ وصمت البداية والنهاية لا يُحتسبان.
        ok, _ = check_lib.eval_silences([(22.0, 23.5, 1.5)], 47.0, False)
        self.assertFalse(ok)
        ok, _ = check_lib.eval_silences([(0.0, 1.5, 1.5)], 47.0, False)
        self.assertTrue(ok)
        ok, _ = check_lib.eval_silences([(45.5, 47.0, 1.5)], 47.0, False)
        self.assertTrue(ok)
        ok, _ = check_lib.eval_silences([], 47.0, False)
        self.assertTrue(ok)
        # الطويل: صمت 3 ثوانٍ (بطاقة عنوان) يمر؛ و5 ثوانٍ يفشل.
        ok, _ = check_lib.eval_silences([(100.0, 103.0, 3.0)], 600, True)
        self.assertTrue(ok)
        ok, _ = check_lib.eval_silences([(100.0, 105.0, 5.0)], 600, True)
        self.assertFalse(ok)

    def test_audio_rules(self):
        self.assertFalse(check_lib.eval_audio(False, None, None)[0])
        self.assertFalse(check_lib.eval_audio(True, None, None)[0])
        self.assertFalse(check_lib.eval_audio(True, -50.0, -30.0)[0])
        self.assertTrue(check_lib.eval_audio(True, -21.0, -2.9)[0])

    def test_size_rules(self):
        self.assertTrue(check_lib.eval_size(720, 1280, False)[0])
        self.assertFalse(check_lib.eval_size(1280, 720, False)[0])
        self.assertTrue(check_lib.eval_size(1280, 720, True)[0])
        self.assertFalse(check_lib.eval_size(720, 1280, True)[0])

    def test_logo_rules(self):
        self.assertTrue(check_lib.eval_logo(
            [("3.0ث", 5000), ("20.0ث", 4000)])[0])
        self.assertFalse(check_lib.eval_logo(
            [("3.0ث", 0), ("20.0ث", 6000)])[0])
        self.assertFalse(check_lib.eval_logo(
            [("3.0ث", 100), ("20.0ث", 200)])[0])


class TestSampleVideo(unittest.TestCase):
    """عيّنة سلوكية في check — جولة v0.1.37 (مقترح tinker رقم 6)."""

    def test_sample_creates_frames_and_preview(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            _make_video(video, duration=12)
            out_dir = os.path.join(td, "samples", "v")
            sample = check_lib.sample_video(video, out_dir)
            self.assertEqual(len(sample["frames"]), 3)
            for frame in sample["frames"]:
                self.assertTrue(os.path.isfile(frame), frame)
                self.assertGreater(os.path.getsize(frame), 0)
            self.assertTrue(os.path.isfile(sample["preview"]))
            # المعاينة 3 ثوانٍ فعلًا.
            info = check_lib.probe(sample["preview"])
            self.assertAlmostEqual(info["duration"], 3.0, delta=0.5)

    def test_sample_missing_video_raises(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(check_lib.CheckError):
                check_lib.sample_video(os.path.join(td, "nope.mp4"),
                                       os.path.join(td, "out"))



if __name__ == "__main__":
    unittest.main()
