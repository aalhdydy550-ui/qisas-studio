#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات وظيفة الأفاتار (lib/avatar_job.py) — جولة v0.1.38 بند 1+4.

مواصفة التصميم (§1): مخطط LongCat (prompt/cond_image/cond_audio/
audio_type/settings/audio.kind)؛ وقاعدة «الصوت النظيف فقط» (§4)
في check_audio_clean. ملفات WAV الاصطناعية تُولَّد محليًا (wave+
math) بلا ffmpeg؛ وفحص الصمت/المستوى يحتاج ffmpeg في PATH
(يتخطى عند غيابه كما في test_audio_profile.py).
"""
import json
import math
import os
import shutil
import struct
import tempfile
import unittest
from unittest import mock
import wave

from lib import avatar_job

HAS_FFMPEG = shutil.which("ffmpeg") is not None
HAS_FFPROBE = shutil.which("ffprobe") is not None

# PNG صغير 1×1 (صالح كملف صورة للتحقق من الوجود والامتداد).
_PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c63000100000500010d0a2db4000000"
    "0049454e44ae426082")


def _write_wav(path, segments, rate=22050):
    """اكتب wav: segments قائمة (مدة_ثوانٍ، سعة)؛ سعة 0 = صمت."""
    with wave.open(path, "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        for seconds, amp in segments:
            count = int(seconds * rate)
            for i in range(count):
                sample = int(amp * 32767
                             * math.sin(2 * math.pi * 440 * i / rate))
                fh.writeframes(struct.pack("<h", sample))


def _valid_job(image, audio1, **extra):
    job = {"prompt": "A middle-aged Egyptian storyteller, warm.",
           "cond_image": image,
           "cond_audio": {"person1": audio1},
           "audio_type": "para",
           "settings": {"audio_cfg": 4.0, "full_steps": False,
                        "aspect_policy": "native",
                        "profile": "t4x2-int8"},
           "audio": {"kind": "narration"}}
    job.update(extra)
    return job


@unittest.skipUnless(HAS_FFPROBE, "ffprobe غير موجود")
class TestValidateJob(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="avatar-job-")
        self.image = os.path.join(self.tmp, "storyteller.png")
        with open(self.image, "wb") as fh:
            fh.write(_PNG_1X1)
        self.audio1 = os.path.join(self.tmp, "scene1.wav")
        _write_wav(self.audio1, [(2.0, 0.5)])
        self.audio2 = os.path.join(self.tmp, "scene2.wav")
        _write_wav(self.audio2, [(2.0, 0.5)])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_valid_single_person_passes(self):
        job = avatar_job.validate_job(
            _valid_job(self.image, self.audio1))
        self.assertEqual(job["audio_type"], "para")
        self.assertEqual(job["audio"]["kind"], "narration")
        self.assertEqual(job["settings"]["audio_cfg"], 4.0)
        self.assertEqual(job["settings"]["profile"], "t4x2-int8")
        self.assertAlmostEqual(job["durations"]["person1"], 2.0, 1)

    def test_missing_image_fails(self):
        with self.assertRaises(avatar_job.AvatarJobError):
            avatar_job.validate_job(
                _valid_job(os.path.join(self.tmp, "nope.png"),
                           self.audio1))

    def test_bad_image_extension_fails(self):
        bad = os.path.join(self.tmp, "storyteller.txt")
        with open(bad, "w") as fh:
            fh.write("x")
        with self.assertRaises(avatar_job.AvatarJobError):
            avatar_job.validate_job(_valid_job(bad, self.audio1))

    def test_two_persons_without_audio_type_fails(self):
        job = _valid_job(self.image, self.audio1)
        job["cond_audio"]["person2"] = self.audio2
        del job["audio_type"]
        with self.assertRaises(avatar_job.AvatarJobError):
            avatar_job.validate_job(job)

    def test_audio_over_300s_rejected(self):
        job = _valid_job(self.image, self.audio1)
        with mock.patch.object(avatar_job, "_audio_duration",
                               return_value=301.0):
            with self.assertRaises(avatar_job.AvatarJobError):
                avatar_job.validate_job(job)

    def test_para_different_durations_fails_add_passes(self):
        audio_long = os.path.join(self.tmp, "long.wav")
        _write_wav(audio_long, [(2.5, 0.5)])
        job = _valid_job(self.image, self.audio1)
        job["cond_audio"]["person2"] = audio_long
        job["audio_type"] = "para"
        with self.assertRaises(avatar_job.AvatarJobError):
            avatar_job.validate_job(job)
        job["audio_type"] = "add"
        out = avatar_job.validate_job(job)
        self.assertEqual(out["audio_type"], "add")

    def test_settings_out_of_range_fails(self):
        job = _valid_job(self.image, self.audio1)
        job["settings"] = {"audio_cfg": 2.9}
        with self.assertRaises(avatar_job.AvatarJobError):
            avatar_job.validate_job(job)

    def test_mixed_audio_kind_rejected(self):
        job = _valid_job(self.image, self.audio1)
        job["audio"] = {"kind": "mixed"}
        with self.assertRaises(avatar_job.AvatarJobError):
            avatar_job.validate_job(job)

    def test_empty_prompt_fails(self):
        job = _valid_job(self.image, self.audio1, prompt="  ")
        with self.assertRaises(avatar_job.AvatarJobError):
            avatar_job.validate_job(job)

    def test_audio_duration_missing_file(self):
        with self.assertRaises(avatar_job.AvatarJobError):
            avatar_job._audio_duration(os.path.join(self.tmp, "no.wav"))

    def test_audio_duration_real_file(self):
        self.assertAlmostEqual(
            avatar_job._audio_duration(self.audio1), 2.0, 1)

    def test_load_and_save_roundtrip(self):
        path = os.path.join(self.tmp, "job.json")
        avatar_job.save_job(_valid_job(self.image, self.audio1), path)
        loaded = avatar_job.load_job(path)
        self.assertEqual(loaded["cond_image"], self.image)
        self.assertEqual(loaded["cond_audio"]["person1"], self.audio1)
        self.assertEqual(loaded["settings"]["audio_cfg"], 4.0)

    def test_load_missing_file_fails(self):
        with self.assertRaises(avatar_job.AvatarJobError):
            avatar_job.load_job(os.path.join(self.tmp, "no.json"))

    def test_load_bad_json_fails(self):
        path = os.path.join(self.tmp, "bad.json")
        with open(path, "w") as fh:
            fh.write("{not json")
        with self.assertRaises(avatar_job.AvatarJobError):
            avatar_job.load_job(path)

    def test_job_template_complete(self):
        tpl = avatar_job.job_template()
        self.assertIn("prompt", tpl)
        self.assertIn("cond_image", tpl)
        self.assertIn("person1", tpl["cond_audio"])
        self.assertEqual(tpl["settings"]["profile"], "t4x2-int8")
        self.assertEqual(tpl["audio"]["kind"], "narration")
        tpl2 = avatar_job.job_template(scene_type="dialogue")
        self.assertNotEqual(tpl["prompt"], tpl2["prompt"])


@unittest.skipUnless(HAS_FFMPEG and HAS_FFPROBE,
                     "ffmpeg/ffprobe غير موجود")
class TestCheckAudioClean(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="avatar-clean-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _wav(self, name, segments):
        path = os.path.join(self.tmp, name)
        _write_wav(path, segments)
        return path

    def test_mixed_continuous_20s_rejected(self):
        path = self._wav("mixed.wav", [(20.0, 0.5)])
        result = avatar_job.check_audio_clean(path)
        self.assertFalse(result["ok"])
        self.assertEqual(result["silence_ratio"], 0.0)
        self.assertGreater(result["mean_db"], -30.0)

    def test_narration_with_pauses_20s_passes(self):
        path = self._wav("narration.wav",
                         [(8.0, 0.5), (2.0, 0.0),
                          (8.0, 0.5), (2.0, 0.0)])
        result = avatar_job.check_audio_clean(path)
        self.assertTrue(result["ok"])
        self.assertGreater(result["silence_ratio"], 0.1)

    def test_short_8s_no_silence_passes(self):
        path = self._wav("short.wav", [(8.0, 0.5)])
        result = avatar_job.check_audio_clean(path)
        self.assertTrue(result["ok"])
        self.assertLess(result["duration_seconds"], 15.0)

    def test_missing_file_fails(self):
        with self.assertRaises(avatar_job.AvatarJobError):
            avatar_job.check_audio_clean(
                os.path.join(self.tmp, "no.wav"))


if __name__ == "__main__":
    unittest.main()
