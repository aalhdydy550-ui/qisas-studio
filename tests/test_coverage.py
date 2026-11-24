#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات تأكيدات التغطية والحدود الآمنة — جولة v0.1.37
(مقترح tinker رقم 3).

تختبر القواعد على بيانات اصطناعية، وعلى فيديو حقيقي
مولَّد بـffmpeg (نغمة + صمت مصطنع) مع بيان اصطناعي.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import coverage as coverage_lib
from lib import manifest as manifest_lib


def _make_video(out, duration=10, mute_between=None):
    args = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
            "color=c=0x2a2a2a:s=720x1280:r=30:d=%s" % duration,
            "-f", "lavfi", "-i",
            "sine=frequency=440:sample_rate=48000:duration=%s" % duration]
    if mute_between:
        args += ["-af", "volume=0:enable='between(t,%s,%s)'"
                 % mute_between]
    args += ["-t", str(duration), "-c:v", "libx264", "-preset",
             "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
             "-c:a", "aac", out]
    subprocess.run(args, check=True, timeout=300)


def _manifest(scenes, narration_duration):
    return {"schema_version": 1, "video": {"file": "t.mp4"},
            "title": "t", "hook": "h", "created_at": "2026-11-22",
            "source": "studio",
            "scenes": [{"scene": i + 1, "start": s, "end": e,
                        "text": "عبارة %d" % (i + 1)}
                       for i, (s, e) in enumerate(scenes)],
            "narration": {"duration_seconds": narration_duration}}


class TestSceneCoverage(unittest.TestCase):
    def test_tiling_passes(self):
        ok, _detail, skipped = coverage_lib.check_scene_coverage(
            _manifest([(0.0, 5.0), (5.3, 10.0)], 10.0))
        self.assertTrue(ok)
        self.assertFalse(skipped)

    def test_head_gap_fails(self):
        ok, detail, _ = coverage_lib.check_scene_coverage(
            _manifest([(1.0, 5.0), (5.3, 10.0)], 10.0))
        self.assertFalse(ok)
        self.assertIn("رأس مفقود", detail)

    def test_tail_gap_fails(self):
        ok, detail, _ = coverage_lib.check_scene_coverage(
            _manifest([(0.0, 5.0), (5.3, 8.0)], 10.0))
        self.assertFalse(ok)
        self.assertIn("قبل نهاية السرد", detail)

    def test_big_gap_fails(self):
        ok, detail, _ = coverage_lib.check_scene_coverage(
            _manifest([(0.0, 4.0), (5.0, 10.0)], 10.0))
        self.assertFalse(ok)
        self.assertIn("فجوة", detail)

    def test_overlap_fails(self):
        ok, detail, _ = coverage_lib.check_scene_coverage(
            _manifest([(0.0, 5.5), (5.0, 10.0)], 10.0))
        self.assertFalse(ok)
        self.assertIn("تداخل", detail)

    def test_no_scenes_skipped(self):
        _ok, _detail, skipped = coverage_lib.check_scene_coverage(
            _manifest([], 10.0))
        self.assertTrue(skipped)

    @unittest.skipUnless(
        os.path.isfile(os.path.expanduser(
            "~/workspace/studio/runs/anza-20261122-150031/manifest.json")),
        "بيان إنتاج العنزة غائب — بيئة CI")
    def test_real_anza_manifest_passes(self):
        # قاعدة التبليط تمر على بيان إنتاج حقيقي (العنزة ج1):
        # فجوات التنفس 0.3ث مسموحة، والذيل 0.14ث مسموح.
        import json
        path = os.path.expanduser(
            "~/workspace/studio/runs/anza-20261122-150031/manifest.json")
        with open(path, encoding="utf-8") as fh:
            produce = json.load(fh)
        man = {"scenes": [
            {"scene": i + 1, "start": p["start"], "end": p["end"],
             "text": p["text"]}
            for i, p in enumerate(produce["phrases"])],
            "narration": {"duration_seconds":
                          produce["narration_duration"]}}
        ok, detail, skipped = coverage_lib.check_scene_coverage(man)
        self.assertFalse(skipped)
        self.assertTrue(ok, detail)


class TestBoundariesAndPhraseAudio(unittest.TestCase):
    SILENCES = [(4.8, 5.2, 0.4)]

    def test_boundary_inside_silence_passes(self):
        ok, _d, _s = coverage_lib.check_scene_boundaries(
            _manifest([(0.0, 5.0), (5.0, 10.0)], 10.0), self.SILENCES)
        self.assertTrue(ok)

    def test_boundary_mid_speech_fails(self):
        ok, detail, _ = coverage_lib.check_scene_boundaries(
            _manifest([(0.0, 7.0), (7.0, 10.0)], 10.0), self.SILENCES)
        self.assertFalse(ok)
        self.assertIn("7.00", detail)

    def test_boundary_80ms_tolerance(self):
        # حد على بعد 0.05ث من الصمت يمر؛ وعلى بعد 0.2ث يفشل.
        ok, _d, _s = coverage_lib.check_scene_boundaries(
            _manifest([(0.0, 4.75), (4.75, 10.0)], 10.0), self.SILENCES)
        self.assertTrue(ok)
        ok, _d, _s = coverage_lib.check_scene_boundaries(
            _manifest([(0.0, 4.5), (4.5, 10.0)], 10.0), self.SILENCES)
        self.assertFalse(ok)

    def test_no_silences_skips_boundaries(self):
        _ok, _d, skipped = coverage_lib.check_scene_boundaries(
            _manifest([(0.0, 5.0), (5.0, 10.0)], 10.0), [])
        self.assertTrue(skipped)

    def test_boundary_between_words_with_word_times_passes(self):
        # إيجاب كاذب سابق (العنزة ج1، حد 48.93ث): حد بين كلمتين
        # بلا صمت ≥0.3ث قربه كان يفشل بقاعدة الصمت؛ وبتوقيتات
        # الكلمات يمر — الحد على حدود الكلمة لا داخلها.
        man = _manifest([(0.0, 5.0), (5.0, 10.0)], 10.0)
        man["phrases"] = [
            {"start": 0.0, "end": 5.0, "text": "عبارة أولى",
             "words": [{"w": "أول", "start": 0.0, "end": 2.0},
                       {"w": "ثان", "start": 2.0, "end": 5.0}]},
            {"start": 5.0, "end": 10.0, "text": "عبارة ثانية",
             "words": [{"w": "ثالث", "start": 5.0, "end": 7.0},
                       {"w": "رابع", "start": 7.0, "end": 10.0}]},
        ]
        ok, detail, skipped = coverage_lib.check_scene_boundaries(
            man, self.SILENCES)
        self.assertTrue(ok, detail)
        self.assertFalse(skipped)

    def test_boundary_inside_word_with_word_times_fails(self):
        # حد يقع داخل كلمة (5.0ث داخل 4.0–6.0ث) يفشل حتى مع
        # توقيتات الكلمات — هذه هي القاعدة حرفيًا.
        man = _manifest([(0.0, 5.0), (5.0, 10.0)], 10.0)
        man["phrases"] = [
            {"start": 0.0, "end": 5.0, "text": "عبارة أولى",
             "words": [{"w": "كلمة", "start": 4.0, "end": 6.0}]},
            {"start": 5.0, "end": 10.0, "text": "عبارة ثانية",
             "words": [{"w": "أخرى", "start": 6.0, "end": 10.0}]},
        ]
        ok, detail, _ = coverage_lib.check_scene_boundaries(
            man, self.SILENCES)
        self.assertFalse(ok)
        self.assertIn("5.00", detail)

    @unittest.skipUnless(
        os.path.isfile(os.path.expanduser(
            "~/workspace/studio/runs/anza-20261122-150031/manifest.json")),
        "بيان إنتاج العنزة غائب — بيئة CI")
    def test_real_anza_boundary_with_words_passes(self):
        # حالة العنزة ج1 الحقيقية: حد 48.926ث نهاية عبارة =
        # نهاية كلمة «إيه؟» وبداية «الجزء» — بين كلمتين لا
        # داخل كلمة — فيمر رغم غياب صمت قريب.
        import json
        base = os.path.expanduser(
            "~/workspace/studio/runs/anza-20261122-150031")
        with open(os.path.join(base, "manifest.json"),
                  encoding="utf-8") as fh:
            produce = json.load(fh)
        with open(os.path.join(base, "assets/captions.json"),
                  encoding="utf-8") as fh:
            caps = json.load(fh)
        words = [{"w": w["word"], "start": w["startMs"] / 1000.0,
                  "end": w["endMs"] / 1000.0} for w in caps]
        man = {"scenes": [
            {"scene": i + 1, "start": p["start"], "end": p["end"],
             "text": p["text"]}
            for i, p in enumerate(produce["phrases"])],
            "phrases": [
            {"start": p["start"], "end": p["end"], "text": p["text"],
             "words": [w for w in words
                       if w["start"] >= p["start"] - 0.001
                       and w["end"] <= p["end"] + 0.001]}
            for p in produce["phrases"]],
            "narration": {"duration_seconds":
                          produce["narration_duration"]}}
        ok, detail, skipped = coverage_lib.check_scene_boundaries(
            man, self.SILENCES)
        self.assertFalse(skipped)
        self.assertTrue(ok, detail)

    def test_phrase_fully_silent_fails(self):
        ok, detail, _ = coverage_lib.check_phrase_audio(
            _manifest([(0.0, 2.0), (4.9, 5.1), (6.0, 10.0)], 10.0),
            self.SILENCES)
        self.assertFalse(ok)
        self.assertIn("4.90", detail)

    def test_phrase_with_audio_passes(self):
        ok, _d, _s = coverage_lib.check_phrase_audio(
            _manifest([(0.0, 5.0), (5.0, 10.0)], 10.0), self.SILENCES)
        self.assertTrue(ok)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "ffmpeg/ffprobe غير متاحين")
class TestCoverageEndToEnd(unittest.TestCase):
    def test_video_with_silence_gap_passes(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            _make_video(video, duration=10, mute_between=(4.8, 5.2))
            man = manifest_lib.build_manifest(
                video, title="t", hook="h", source="studio",
                scenes=[{"scene": 1, "start": 0.0, "end": 5.0,
                         "text": "أولًا"},
                        {"scene": 2, "start": 5.0, "end": 10.0,
                         "text": "ثانيًا"}],
                narration={"duration_seconds": 10.0})
            checks = coverage_lib.extra_checks(video, man)
            by_name = {c["name"]: c for c in checks}
            self.assertTrue(by_name["تغطية المشاهد"]["ok"],
                            by_name["تغطية المشاهد"]["detail"])
            self.assertTrue(by_name["حدود المشاهد الآمنة"]["ok"],
                            by_name["حدود المشاهد الآمنة"]["detail"])
            self.assertTrue(by_name["صوت العبارات"]["ok"],
                            by_name["صوت العبارات"]["detail"])

    def test_silent_phrase_fails_end_to_end(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            _make_video(video, duration=10, mute_between=(2.0, 3.0))
            man = manifest_lib.build_manifest(
                video, title="t", hook="h", source="studio",
                scenes=[{"scene": 1, "start": 0.0, "end": 2.0,
                         "text": "أولًا"},
                        {"scene": 2, "start": 2.1, "end": 2.9,
                         "text": "صامتة"},
                        {"scene": 3, "start": 3.0, "end": 10.0,
                         "text": "ثالثًا"}],
                narration={"duration_seconds": 10.0})
            checks = coverage_lib.extra_checks(video, man)
            by_name = {c["name"]: c for c in checks}
            self.assertFalse(by_name["صوت العبارات"]["ok"])


if __name__ == "__main__":
    unittest.main()
