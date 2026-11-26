#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات فحص الجودة قبل النشر (lib.check).

تعمل بـ `python3 -m unittest discover -s tests -v`.
تولّد مقاطع اختبار صغيرة بـffmpeg (بلا Veo وبلا شبكة):
سليم 45 ثانية، وصمت مُصطنع وسط السرد، وبلا صوت، ومقاس
خاطئ، وبلا شعار، وقصير، وصمت ختامي يُستثنى من فحص الصمت.
وفحص النص والمنطقة الآمنة (qa_safe_area — جولة v0.1.39):
نص أسفل سليم ينجح، ونص أعلى يفشل، ونص مقصوص عند الحافة
يفشل، وفيديو بلا ASS يفحص الإطارات والشعار فقط.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import check as check_lib
from lib import caption_check

GOLD_BOX = "drawbox=x=600:y=20:w=100:h=100:color=0xE0AF5C:t=fill"
DRAWTEXT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _drawtext(text, x, y):
    """مرشح drawtext لنص أبيض بحواف داكنة (نمط كابشن الخط)."""
    return ("drawtext=text='%s':fontfile=%s:fontsize=46:"
            "fontcolor=white:borderw=2:bordercolor=black:x=%s:y=%s"
            % (text, DRAWTEXT_FONT, x, y))


def _ffmpeg(*args):
    cmd = ["ffmpeg", "-y", "-v", "error"] + list(args)
    subprocess.run(cmd, check=True, timeout=300)


def _make_video(out, duration=10, size="720x1280", audio=True,
                audio_duration=None, mute_between=None, gold=False,
                drawtext=None):
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
    if drawtext:
        vf.append(drawtext)
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


ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Naskh Arabic,46,&H00FFFFFF,&H000000FF,&H80000000,&H80000000,1,0,0,0,100,100,0,0,1,2.5,0,%d,%d,%d,%d,1
Style: Keyword,Noto Naskh Arabic,110,&H00FFFFFF,&H000000FF,&H80000000,&H80000000,-1,0,0,0,100,100,0,0,1,3.5,0,5,40,40,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _write_ass(path, alignment=2, margin_l=40, margin_r=40,
               margin_v=70, dialogues=None):
    """اكتب ملف ASS صغير بنمط Default واحد + عبارات."""
    if dialogues is None:
        dialogues = [("0:00:01.00", "0:00:03.00", "Default",
                      "عبارة أولى أسفل"),
                     ("0:00:03.00", "0:00:05.00", "Keyword",
                      "الوصية!")]
    lines = [ASS_HEAD % (alignment, margin_l, margin_r, margin_v)]
    for start, end, style, text in dialogues:
        lines.append("Dialogue: 0,%s,%s,%s,,0,0,0,,%s"
                     % (start, end, style, text))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


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



class TestQaSafeAreaBands(unittest.TestCase):
    """كشف أشرطة النص البكسلي على إطارات مولّدة بـPIL (بلا ffmpeg)."""

    def _frame(self, draw_fn):
        from PIL import Image, ImageDraw, ImageFont
        font = ImageFont.truetype(DRAWTEXT_FONT, 46)
        img = Image.new("RGB", (720, 1280), (42, 42, 42))
        draw_fn(ImageDraw.Draw(img), font)
        path = os.path.join(self.td, "frame-%s.png" % id(draw_fn))
        img.save(path)
        return path

    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="qa-bands-")

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_blank_frame_has_no_bands(self):
        path = self._frame(lambda d, f: None)
        self.assertEqual(check_lib.detect_text_bands(path), [])

    def test_bottom_text_band_detected_and_safe(self):
        path = self._frame(
            lambda d, f: d.text((360, 1100), "Hello world test",
                                font=f, fill=(255, 255, 255),
                                anchor="ma"))
        bands = check_lib.detect_text_bands(path)
        self.assertEqual(len(bands), 1)
        ok, problems = check_lib.eval_qa_bands(bands, None, 720, 1280)
        self.assertTrue(ok, problems)

    def test_top_text_band_flagged(self):
        path = self._frame(
            lambda d, f: d.text((360, 100), "Hello world test",
                                font=f, fill=(255, 255, 255),
                                anchor="ma"))
        bands = check_lib.detect_text_bands(path)
        self.assertEqual(len(bands), 1)
        ok, problems = check_lib.eval_qa_bands(bands, None, 720, 1280)
        self.assertFalse(ok)
        self.assertIn("الثلث العلوي", "؛ ".join(problems))

    def test_clipped_text_band_flagged(self):
        path = self._frame(
            lambda d, f: d.text((-30, 1100),
                                "Hello world test clipped",
                                font=f, fill=(255, 255, 255)))
        bands = check_lib.detect_text_bands(path)
        self.assertEqual(len(bands), 1)
        ok, problems = check_lib.eval_qa_bands(bands, None, 720, 1280)
        self.assertFalse(ok)
        self.assertIn("مقصوص", "؛ ".join(problems))

    def test_gold_logo_box_is_not_a_text_band(self):
        path = self._frame(
            lambda d, f: d.rectangle([600, 20, 700, 120],
                                     fill=(224, 175, 92)))
        self.assertEqual(check_lib.detect_text_bands(path), [])
        badge = check_lib.gold_badge_box(path, 720)
        self.assertIsNotNone(badge)
        self.assertEqual((badge["x0"], badge["x1"],
                          badge["y0"], badge["y1"]),
                         (600, 700, 20, 120))
        ok, problems = check_lib.eval_qa_bands([], badge, 720, 1280)
        self.assertTrue(ok, problems)

    def test_badge_covering_text_is_flagged(self):
        band = {"y0": 20, "y1": 50, "xmin": 580, "xmax": 700,
                "bxmin": 590, "bxmax": 690}
        badge = {"x0": 600, "x1": 700, "y0": 20, "y1": 120,
                 "pixels": 10000}
        ok, problems = check_lib.eval_qa_bands([band], badge, 720,
                                               1280)
        self.assertFalse(ok)
        self.assertIn("يغطي نصًا", "؛ ".join(problems))

    def test_eval_qa_bands_rules(self):
        safe = {"y0": 1100, "y1": 1130, "xmin": 150, "xmax": 570,
                "bxmin": 160, "bxmax": 560}
        ok, _ = check_lib.eval_qa_bands([safe], None, 720, 1280)
        self.assertTrue(ok)
        top = dict(safe, y0=100, y1=130)
        ok, problems = check_lib.eval_qa_bands([top], None, 720, 1280)
        self.assertFalse(ok)
        self.assertIn("الثلث العلوي", "؛ ".join(problems))
        clipped = dict(safe, bxmin=0)
        ok, problems = check_lib.eval_qa_bands([clipped], None, 720,
                                               1280)
        self.assertFalse(ok)
        self.assertIn("مقصوص", "؛ ".join(problems))
        outside = dict(safe, bxmin=10)
        ok, problems = check_lib.eval_qa_bands([outside], None, 720,
                                               1280)
        self.assertFalse(ok)
        self.assertIn("المنطقة الآمنة", "؛ ".join(problems))
        low = dict(safe, y1=1250)
        ok, problems = check_lib.eval_qa_bands([low], None, 720, 1280)
        self.assertFalse(ok)
        self.assertIn("السفلى", "؛ ".join(problems))


class TestQaAssPositions(unittest.TestCase):
    """تحليل مواضع عبارات ASS (بلا ffmpeg)."""

    def test_bottom_style_passes(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_ass(os.path.join(td, "bottom.ass"))
            parsed = check_lib.parse_ass_positions(path)
            self.assertEqual(len(parsed["dialogues"]), 2)
            # Keyword بمحاذاة وسطية (5) يمر — موضعه العمودي
            # يفحصه الكشف البكسلي لا ASS.
            ok, detail = check_lib.eval_ass_positions(
                parsed["dialogues"], 720, 1280)
            self.assertTrue(ok, detail)

    def test_top_alignment_fails(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_ass(os.path.join(td, "top.ass"),
                              alignment=8,
                              dialogues=[("0:00:01.00", "0:00:03.00",
                                          "Default", "عبارة علوية")])
            parsed = check_lib.parse_ass_positions(path)
            ok, detail = check_lib.eval_ass_positions(
                parsed["dialogues"], 720, 1280)
            self.assertFalse(ok)
            self.assertIn("علوية", detail)

    def test_narrow_side_margins_fail(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_ass(os.path.join(td, "narrow.ass"),
                              margin_l=5,
                              dialogues=[("0:00:01.00", "0:00:03.00",
                                          "Default",
                                          "عبارة بهامش ضيق")])
            parsed = check_lib.parse_ass_positions(path)
            ok, detail = check_lib.eval_ass_positions(
                parsed["dialogues"], 720, 1280)
            self.assertFalse(ok)
            self.assertIn("المنطقة الآمنة", detail)

    def test_low_margin_v_fails(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_ass(os.path.join(td, "lowv.ass"),
                              margin_v=10,
                              dialogues=[("0:00:01.00", "0:00:03.00",
                                          "Default", "عبارة لاصقة")])
            parsed = check_lib.parse_ass_positions(path)
            ok, detail = check_lib.eval_ass_positions(
                parsed["dialogues"], 720, 1280)
            self.assertFalse(ok)
            self.assertIn("السفلى", detail)

    def test_missing_ass_raises(self):
        with self.assertRaises(check_lib.CheckError):
            check_lib.parse_ass_positions("/tmp/no-such-file.ass")

    def test_qa_frame_times_use_dialogue_midpoints(self):
        dialogues = [{"start": 9.0, "end": 13.0},
                     {"start": 20.0, "end": 24.0},
                     {"start": 38.0, "end": 42.0}]
        times = check_lib._qa_frame_times(45.0, dialogues)
        self.assertEqual(times, [11.0, 22.0, 40.0])
        self.assertEqual(check_lib._qa_frame_times(45.0, []),
                         [11.25, 22.5, 33.75])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "ffmpeg/ffprobe غير متاحين")
class TestQaSafeAreaVideo(unittest.TestCase):
    """فحص qa_safe_area نهايةً على فيديوهات مولّدة بـffmpeg."""

    @classmethod
    def setUpClass(cls):
        # يعيد استخدام fixtures فئة TestCheckFixtures (تُبنى
        # أولًا بالترتيب الأبجدي للفئات) — وإن غابت يُعاد بناؤها.
        cls.td = tempfile.mkdtemp(prefix="qa-video-")
        cls.bottom_text = os.path.join(cls.td, "bottom-text.mp4")
        _make_video(cls.bottom_text, duration=45, gold=True,
                    drawtext=_drawtext("BOTTOM CAPTION TEXT",
                                       "(w-text_w)/2", 1100))
        cls.top_text = os.path.join(cls.td, "top-text.mp4")
        _make_video(cls.top_text, duration=10, gold=True,
                    drawtext=_drawtext("TOP CAPTION TEXT",
                                       "(w-text_w)/2", 100))
        cls.clipped_text = os.path.join(cls.td, "clipped-text.mp4")
        _make_video(cls.clipped_text, duration=10, gold=True,
                    drawtext=_drawtext("CLIPPED CAPTION TEXT HERE",
                                       -30, 1100))
        cls.good = os.path.join(cls.td, "good.mp4")
        _make_video(cls.good, duration=45, gold=True)
        cls.ass_bottom = _write_ass(
            os.path.join(cls.td, "bottom.ass"))
        cls.ass_top = _write_ass(
            os.path.join(cls.td, "top.ass"), alignment=8,
            dialogues=[("0:00:01.00", "0:00:03.00", "Default",
                        "عبارة علوية")])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.td, ignore_errors=True)

    def test_six_quality_checks(self):
        result = check_lib.run_checks(self.good)
        self.assertEqual(len(result["checks"]), 6)
        names = [c["name"] for c in result["checks"]]
        self.assertIn(check_lib.QA_NAME, names)

    def test_bottom_text_video_passes_all(self):
        result = check_lib.run_checks(self.bottom_text)
        self.assertTrue(result["passed"],
                        check_lib.format_report(result))
        c = _check_by_name(result, check_lib.QA_NAME)
        self.assertTrue(c["ok"], c)
        self.assertIn("المنطقة الآمنة", c["detail"])

    def test_top_text_video_fails_qa(self):
        result = check_lib.run_checks(self.top_text)
        c = _check_by_name(result, check_lib.QA_NAME)
        self.assertFalse(c["ok"], c)
        self.assertIn("الثلث العلوي", c["detail"])

    def test_clipped_text_video_fails_qa(self):
        result = check_lib.run_checks(self.clipped_text)
        c = _check_by_name(result, check_lib.QA_NAME)
        self.assertFalse(c["ok"], c)
        self.assertIn("مقصوص", c["detail"])

    def test_video_without_ass_checks_frames_only(self):
        # بلا ملف ASS: الفحص البكسلي + الشعار فقط — فيديو سليم
        # بلا نص ينجح، وفيديو بنص أعلى يفشل بلا ASS أصلًا.
        result = check_lib.run_checks(self.good)
        c = _check_by_name(result, check_lib.QA_NAME)
        self.assertTrue(c["ok"], c)
        bad = check_lib.run_checks(self.top_text)
        self.assertFalse(_check_by_name(bad, check_lib.QA_NAME)["ok"])

    def test_video_with_bottom_ass_passes(self):
        result = check_lib.run_checks(self.bottom_text,
                                      ass_path=self.ass_bottom)
        c = _check_by_name(result, check_lib.QA_NAME)
        self.assertTrue(c["ok"], c)
        self.assertIn("ASS", c["detail"])

    def test_video_with_top_ass_fails(self):
        # ASS علوية تفشل الفحص حتى بلا نص أعلى في الإطارات.
        result = check_lib.run_checks(self.good,
                                      ass_path=self.ass_top)
        c = _check_by_name(result, check_lib.QA_NAME)
        self.assertFalse(c["ok"], c)
        self.assertIn("علوية", c["detail"])


class TestResultTemplate(unittest.TestCase):
    """قالب «معرّف + خطورة + رسالة إصلاح» (جولة الأنماط W8).

    بلا ffmpeg: يختبر التغليف مباشرة عبر _check_result
    وformat_report وcheck_caption — لا منطق QA هنا.
    """

    EXPECTED_CHECK_NAMES = (
        "المدة", "الصمت عند الفواصل", "الصوت", "المقاس",
        "شعار الصفحة", check_lib.QA_NAME)

    def test_all_six_checks_have_unique_ids(self):
        self.assertEqual(set(check_lib._CHECK_META),
                         set(self.EXPECTED_CHECK_NAMES))
        ids = [meta[0] for meta in check_lib._CHECK_META.values()]
        self.assertEqual(len(ids), len(set(ids)))
        for fid in ids:
            self.assertTrue(fid.startswith("CHK-"), fid)

    def test_check_result_failed_is_high_with_fix(self):
        for name in self.EXPECTED_CHECK_NAMES:
            res = check_lib._check_result(name, False, "تفصيل")
            self.assertEqual(res["name"], name)
            self.assertFalse(res["ok"])
            self.assertEqual(res["detail"], "تفصيل")
            self.assertTrue(res["id"].startswith("CHK-"), res)
            self.assertEqual(res["severity"], "high")
            self.assertTrue(res["fix"], res)

    def test_check_result_passed_is_info(self):
        for name in self.EXPECTED_CHECK_NAMES:
            res = check_lib._check_result(name, True, "تفصيل")
            self.assertTrue(res["ok"])
            self.assertEqual(res["severity"], "info")
            self.assertTrue(res["fix"], res)

    def test_format_report_shows_fix_for_failures_only(self):
        failed = check_lib._check_result("المقاس", False,
                                         "المقاس 640x360")
        passed = check_lib._check_result("الصوت", True, "سليم")
        result = {"path": "/tmp/v.mp4", "long": False, "duration": 45.0,
                  "width": 640, "height": 360,
                  "checks": [failed, passed], "passed": False}
        text = check_lib.format_report(result)
        self.assertIn("[FAIL] المقاس", text)
        self.assertIn("الإصلاح:", text)
        self.assertIn("720×1280", text)
        self.assertIn("[PASS] الصوت", text)
        # سطر الإصلاح يظهر مرة واحدة — للفاشل فقط.
        self.assertEqual(text.count("الإصلاح:"), 1)

    def test_caption_issue_carries_template(self):
        gate = ("عنوان القصة\nلو عايز الجزء الثاني اعمل متابعة "
                "واكتب في التعليقات: الجزء الثاني")
        res = caption_check.check_caption(gate)
        self.assertFalse(res["ok"])
        issue = res["issues"][0]
        self.assertEqual(issue["category"], "next_part")
        self.assertEqual(issue["id"], "CAP-NEXT-001")
        self.assertEqual(issue["severity"], "high")
        self.assertIn("الدعوة اللطيفة", issue["fix"])
        # الحقول القديمة باقية دون تغيير.
        self.assertIn("sentence", issue)
        self.assertIn("reason", issue)
        self.assertIn("in_hook", issue)
        self.assertFalse(issue["in_hook"])

    def test_caption_issue_in_hook_fix_is_rewrite(self):
        gate = ("لو عايز الجزء الثاني اعمل متابعة واكتب في "
                "التعليقات: الجزء الثاني")
        res = caption_check.check_caption(gate)
        issue = res["issues"][0]
        self.assertTrue(issue["in_hook"])
        self.assertIn("أعد كتابة الكابشن كاملًا", issue["fix"])

    def test_caption_story_issue_template(self):
        res = caption_check.check_caption(
            "عنوان القصة\nابعت قصتك في التعليقات عشان نحكيها")
        issue = res["issues"][0]
        self.assertEqual(issue["category"], "story")
        self.assertEqual(issue["id"], "CAP-STORY-001")
        self.assertEqual(issue["severity"], "high")
        self.assertIn("رسائل الصفحة", issue["fix"])


if __name__ == "__main__":
    unittest.main()
