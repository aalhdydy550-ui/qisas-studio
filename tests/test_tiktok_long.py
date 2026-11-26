#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات النسخة الطويلة اليومية لـ TikTok — خطة الـ30 يومًا.

يغطي: عنوان النسخة (full/two)، فحص المدخل القصير (ملف مفقود،
صيغة غير mp4، مدة خارج 40–60، أبعاد غير عمودية، بلا صوت)،
رفض المجموع الخارج عن 65–110 قبل أي ترميز، أمر ffmpeg
(مرشح concat + إعادة ترميز libx264/aac)، فشل ffmpeg،
كابشن النسخة (الوسوم الأربعة)، وكاتب الحزمة (الملفات الأربعة)،
ودمج حقيقي end-to-end بفيديوهين مولّدين بـ ffmpeg (يتخطى
إن غاب ffmpeg/ffprobe).

بلا أي شبكة — كل الشبكة محاكاة تفشل عند استدعائها.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import check as check_lib
from lib import tiktok_long as tl

EXPECTED_HASHTAGS = ["#قصص", "#قصص_حقيقية", "#قصص_واقعية",
                     "#قصة_وعبرة"]
HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _mp4(tmpdir, name="video.mp4", size=1024):
    path = os.path.join(tmpdir, name)
    with open(path, "wb") as f:
        f.write(b"\x00" * size)
    return path


def _probe(duration=45.0, width=720, height=1280, has_audio=True):
    return {"duration": duration, "width": width, "height": height,
            "has_audio": has_audio}


class TestLongTitle(unittest.TestCase):
    def test_full_title(self):
        self.assertEqual(tl.long_title("الأصمعي والأعرابي", "full"),
                         "القصة كاملة: الأصمعي والأعرابي")

    def test_two_title(self):
        self.assertEqual(tl.long_title("أي وصف", "two"),
                         "قصتان مؤثرتان")

    def test_bad_kind(self):
        with self.assertRaises(tl.TikTokLongError):
            tl.long_title("قصة", "three")

    def test_full_needs_title(self):
        with self.assertRaises(tl.TikTokLongError):
            tl.long_title("   ", "full")


class TestProbeShort(unittest.TestCase):
    def test_missing_file(self):
        with self.assertRaises(tl.TikTokLongError):
            tl.probe_short("/tmp/does-not-exist-xyz.mp4")

    def test_non_mp4(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _mp4(tmp, "video.mov")
            with self.assertRaises(tl.TikTokLongError):
                tl.probe_short(path)

    def test_duration_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _mp4(tmp)
            for bad in (39.9, 60.1):
                with mock.patch.object(check_lib, "probe",
                                       return_value=_probe(duration=bad)):
                    with self.assertRaises(tl.TikTokLongError):
                        tl.probe_short(path)
            with mock.patch.object(check_lib, "probe",
                                   return_value=_probe(duration=60.0)):
                self.assertEqual(tl.probe_short(path)["duration"], 60.0)

    def test_non_vertical_dims(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _mp4(tmp)
            with mock.patch.object(check_lib, "probe",
                                   return_value=_probe(width=1280,
                                                       height=720)):
                with self.assertRaises(tl.TikTokLongError):
                    tl.probe_short(path)

    def test_no_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _mp4(tmp)
            with mock.patch.object(check_lib, "probe",
                                   return_value=_probe(has_audio=False)):
                with self.assertRaises(tl.TikTokLongError):
                    tl.probe_short(path)

    def test_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _mp4(tmp)
            with mock.patch.object(check_lib, "probe",
                                   return_value=_probe(duration=47.5)):
                info = tl.probe_short(path)
                self.assertEqual(info["duration"], 47.5)
                self.assertEqual((info["width"], info["height"]),
                                 (720, 1280))
                self.assertTrue(info["has_audio"])


class TestMergeLongVersion(unittest.TestCase):
    def _probes(self, durations):
        """side_effect لـ check.probe: مدخلان ثم الناتج."""
        calls = {"n": 0}

        def _fake(path):
            calls["n"] += 1
            if calls["n"] <= 2:
                return _probe(duration=durations[calls["n"] - 1])
            return _probe(duration=sum(durations))

        return _fake

    def test_total_out_of_range_rejects_before_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = _mp4(tmp, "a.mp4")
            b = _mp4(tmp, "b.mp4")
            out = os.path.join(tmp, "long.mp4")
            with mock.patch.object(check_lib, "probe",
                                   side_effect=self._probes([56.9, 55.0])), \
                    mock.patch.object(tl.subprocess, "run") as run:
                with self.assertRaises(tl.TikTokLongError):
                    tl.merge_long_version(a, b, out)
                run.assert_not_called()

    def test_total_below_min_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = _mp4(tmp, "a.mp4")
            b = _mp4(tmp, "b.mp4")
            out = os.path.join(tmp, "long.mp4")
            with mock.patch.object(check_lib, "probe",
                                   side_effect=self._probes([40.0, 20.0])):
                # 20 ثانية ترفضها probe_short أصلًا — فالمجموع
                # لا يصل للفحص؛ المهم أن الخطأ عربي واضح.
                with self.assertRaises(tl.TikTokLongError):
                    tl.merge_long_version(a, b, out)

    def test_ffmpeg_command_and_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = _mp4(tmp, "a.mp4")
            b = _mp4(tmp, "b.mp4")
            out = os.path.join(tmp, "long.mp4")
            ok = mock.Mock(returncode=0, stdout="", stderr="")
            with mock.patch.object(check_lib, "probe",
                                   side_effect=self._probes([47.5, 47.5])), \
                    mock.patch.object(tl.subprocess, "run",
                                      return_value=ok) as run:
                with mock.patch.object(os.path, "getsize",
                                       return_value=12345):
                    info = tl.merge_long_version(a, b, out)
            self.assertEqual(info["duration"], 95.0)
            self.assertEqual((info["width"], info["height"]),
                             (720, 1280))
            cmd = run.call_args[0][0]
            self.assertEqual(cmd[0], "ffmpeg")
            self.assertIn("-filter_complex", cmd)
            filt = cmd[cmd.index("-filter_complex") + 1]
            self.assertIn("concat=n=2:v=1:a=1", filt)
            self.assertIn("fps=30", filt)
            self.assertIn("aresample=48000", filt)
            self.assertIn("libx264", cmd)
            self.assertIn("aac", cmd)
            self.assertEqual(cmd[-1], os.path.abspath(out))

    def test_ffmpeg_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = _mp4(tmp, "a.mp4")
            b = _mp4(tmp, "b.mp4")
            out = os.path.join(tmp, "long.mp4")
            bad = mock.Mock(returncode=1, stdout="",
                            stderr="ffmpeg: خطأ تجريبي")
            with mock.patch.object(check_lib, "probe",
                                   side_effect=self._probes([47.5, 47.5])), \
                    mock.patch.object(tl.subprocess, "run",
                                      return_value=bad):
                with self.assertRaises(tl.TikTokLongError) as ctx:
                    tl.merge_long_version(a, b, out)
                self.assertIn("خطأ تجريبي", str(ctx.exception))


class TestNormalizePartTags(unittest.TestCase):
    def test_string_and_list(self):
        self.assertEqual(
            tl.normalize_part_tags("#الجزء_الأول #الجزء_الثاني"),
            ["#الجزء_الأول", "#الجزء_الثاني"])
        self.assertEqual(
            tl.normalize_part_tags(["الجزء_الأول", "#الجزء_الأول",
                                    "  ", "#الجزء_الثاني"]),
            ["#الجزء_الأول", "#الجزء_الثاني"])

    def test_empty(self):
        self.assertEqual(tl.normalize_part_tags(None), [])
        self.assertEqual(tl.normalize_part_tags(""), [])


class TestBuildLongCaption(unittest.TestCase):
    def test_full_caption_hashtags_and_title(self):
        text = tl.build_long_caption("الأصمعي والأعرابي",
                                     "نص القصة.", moral="رزقك مكتوب.",
                                     kind="full")
        lines = text.splitlines()
        self.assertEqual(lines[0], "القصة كاملة: الأصمعي والأعرابي")
        self.assertEqual(lines[-1], " ".join(EXPECTED_HASHTAGS))
        self.assertIn("العبرة: رزقك مكتوب.", text)

    def test_two_caption(self):
        text = tl.build_long_caption("زوج من القصص", "نص القصتين.",
                                     kind="two")
        self.assertTrue(text.startswith("قصتان مؤثرتان"))

    def test_part_tags_line_before_hashtags(self):
        # وسوم الأجزاء سطر مستقل قبل الوسوم الأربعة، والوسوم
        # الأربعة (وفيها #قصص — أكبر كلمة بحث) تبقى السطر الأخير.
        text = tl.build_long_caption(
            "الأصمعي والأعرابي", "نص القصة.", kind="full",
            part_tags="#الجزء_الأول #الجزء_الثاني")
        lines = text.splitlines()
        self.assertIn("#الجزء_الأول #الجزء_الثاني", lines)
        self.assertEqual(lines[-1], " ".join(EXPECTED_HASHTAGS))
        self.assertIn("#قصص", lines[-1])
        self.assertLess(lines.index("#الجزء_الأول #الجزء_الثاني"),
                        lines.index(" ".join(EXPECTED_HASHTAGS)))

    def test_no_part_tags_no_extra_line(self):
        text = tl.build_long_caption("قصة", "نص.", kind="full")
        self.assertNotIn("الجزء_", text)


class TestWriteLongBundle(unittest.TestCase):
    def test_bundle_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = _mp4(tmp, "a.mp4")
            b = _mp4(tmp, "b.mp4")
            merged = _mp4(tmp, "merged.mp4", size=2048)
            fake_merged = {"video": merged, "duration": 95.0,
                           "width": 720, "height": 1280,
                           "has_audio": True, "size": 2048,
                           "sources": [
                               {"video": a, "duration": 47.5},
                               {"video": b, "duration": 47.5}]}
            bundle = os.path.join(tmp, "bundle")
            # المحاكاة تكتب ملفًا مدمجًا وهميًا في مسار الناتج
            # (كما يفعل الدمج الحقيقي) ثم ترجع معلوماته.
            def _fake_merge(a_path, b_path, out_path, **kwargs):
                with open(out_path, "wb") as f:
                    f.write(b"\x00" * 2048)
                return fake_merged

            with mock.patch.object(tl, "merge_long_version",
                                   side_effect=_fake_merge):
                result = tl.write_long_bundle(
                    bundle, a, b, "الأصمعي والأعرابي", "نص القصة.",
                    moral="رزقك مكتوب.", kind="full",
                    part_tags="#الجزء_الأول #الجزء_الثاني")
            for name in ("metadata.json", "caption.txt", "steps.txt",
                         "long.json"):
                self.assertTrue(
                    os.path.isfile(os.path.join(bundle, name)), name)
            with open(os.path.join(bundle, "long.json"),
                      encoding="utf-8") as f:
                long_info = json.load(f)
            self.assertEqual(long_info["kind"], "full")
            self.assertEqual(long_info["duration"], 95.0)
            self.assertEqual(long_info["part_tags"],
                             ["#الجزء_الأول", "#الجزء_الثاني"])
            self.assertEqual(len(long_info["sources"]), 2)
            with open(os.path.join(bundle, "caption.txt"),
                      encoding="utf-8") as f:
                caption = f.read()
            self.assertIn("القصة كاملة: الأصمعي والأعرابي", caption)
            self.assertIn("#الجزء_الأول #الجزء_الثاني", caption)
            self.assertTrue(
                caption.rstrip().endswith(" ".join(EXPECTED_HASHTAGS)))
            self.assertEqual(result["video_info"]["duration"], 95.0)


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg/ffprobe غير متاحين")
class TestRealMergeEndToEnd(unittest.TestCase):
    def _make_clip(self, path, seconds=2.0, rate=30, freq=440):
        cmd = ["ffmpeg", "-y",
               "-f", "lavfi", "-i",
               "testsrc=size=720x1280:rate=%d:duration=%.1f"
               % (rate, seconds),
               "-f", "lavfi", "-i",
               "sine=frequency=%d:duration=%.1f" % (freq, seconds),
               "-c:v", "libx264", "-preset", "veryfast",
               "-c:a", "aac", "-shortest", path]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr[-500:])

    def test_real_merge_mixed_fps(self):
        # مقطع 30 إطارًا (Veo) + مقطع 24 إطارًا (OpenMontage):
        # الدمج الحقيقي يطبّع الاثنين إلى 30 إطارًا.
        with tempfile.TemporaryDirectory() as tmp:
            a = os.path.join(tmp, "a.mp4")
            b = os.path.join(tmp, "b.mp4")
            self._make_clip(a, seconds=2.0, rate=30, freq=440)
            self._make_clip(b, seconds=2.0, rate=24, freq=660)
            out = os.path.join(tmp, "long.mp4")
            info = tl.merge_long_version(a, b, out,
                                         min_seconds=3.5,
                                         max_seconds=4.5,
                                         short_min_seconds=0,
                                         short_max_seconds=1000)
            self.assertAlmostEqual(info["duration"], 4.0, delta=2.0)
            self.assertEqual((info["width"], info["height"]),
                             (720, 1280))
            self.assertTrue(info["has_audio"])
            self.assertGreater(info["size"], 0)


if __name__ == "__main__":
    unittest.main()
