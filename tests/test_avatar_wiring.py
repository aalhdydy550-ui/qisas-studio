#!/usr/bin/env python3
"""اختبارات توصيل الأفاتار في studio.py — جولة v0.1.38.

أمر avatar-job (--validate/--template/--list-profiles) + علما
check --avatar-image/--aspect-policy + علم
analyze --dna --audio-profile + مداخل help_ar. كلها عبر
الـCLI الفعلي (subprocess) على ملفات مؤقتة مولَّدة محليًا.
"""
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

STUDIO = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "studio.py")
HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, STUDIO, *args],
        capture_output=True, text=True, timeout=300)


def _write_wav(path, seconds=1.0, rate=22050):
    with wave.open(path, "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        count = int(seconds * rate)
        for i in range(count):
            sample = int(0.5 * 32767
                         * math.sin(2 * math.pi * 440 * i / rate))
            fh.writeframes(struct.pack("<h", sample))


def _make_media(tmp, video_size="720x1280", image_size="720x1280"):
    video = os.path.join(tmp, "clip.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=0x336699:s=%s:d=2" % video_size,
                    video], check=True, timeout=60)
    image = os.path.join(tmp, "portrait.png")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=0x336699:s=%s:d=1" % image_size,
                    "-frames:v", "1", image],
                   check=True, timeout=60)
    return video, image


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg غير موجود")
class TestAvatarJobCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="avatar-wiring-")
        self.video, self.image = _make_media(self.tmp)
        self.audio = os.path.join(self.tmp, "scene1.wav")
        _write_wav(self.audio, seconds=2.0)
        self.job_path = os.path.join(self.tmp, "job.json")
        job = {"prompt": "A middle-aged Egyptian storyteller.",
               "cond_image": self.image,
               "cond_audio": {"person1": self.audio},
               "audio_type": "para",
               "settings": {"audio_cfg": 4.0, "full_steps": False,
                            "aspect_policy": "native",
                            "profile": "t4x2-int8"},
               "audio": {"kind": "narration"}}
        with open(self.job_path, "w") as fh:
            json.dump(job, fh)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_template_prints_valid_job(self):
        proc = _run_cli("avatar-job", "--template")
        self.assertEqual(proc.returncode, 0)
        tpl = json.loads(proc.stdout)
        self.assertIn("prompt", tpl)
        self.assertIn("person1", tpl["cond_audio"])
        self.assertEqual(tpl["settings"]["profile"], "t4x2-int8")

    def test_template_scene_types_differ(self):
        a = _run_cli("avatar-job", "--template",
                     "--scene-type", "narration")
        b = _run_cli("avatar-job", "--template",
                     "--scene-type", "dialogue")
        self.assertNotEqual(json.loads(a.stdout)["prompt"],
                            json.loads(b.stdout)["prompt"])

    def test_list_profiles_shows_three(self):
        proc = _run_cli("avatar-job", "--list-profiles")
        self.assertEqual(proc.returncode, 0)
        for name in ("t4x2-int8", "a100-bf16", "rtx4090-int8"):
            self.assertIn(name, proc.stdout)
        self.assertIn("--use_int8", proc.stdout)

    def test_validate_valid_job_rc0(self):
        proc = _run_cli("avatar-job", "--validate", self.job_path)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("وظيفة الأفاتار سليمة", proc.stdout)
        self.assertIn("--nproc_per_node=2", proc.stdout)

    def test_validate_profile_override(self):
        proc = _run_cli("avatar-job", "--validate", self.job_path,
                        "--profile", "a100-bf16")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("الملف: a100-bf16", proc.stdout)
        self.assertNotIn("--use_int8", proc.stdout)

    def test_validate_invalid_job_rc1(self):
        bad = os.path.join(self.tmp, "bad.json")
        with open(bad, "w") as fh:
            json.dump({"prompt": "x"}, fh)
        proc = _run_cli("avatar-job", "--validate", bad)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("غير سليمة", proc.stdout)

    def test_no_flag_rc2(self):
        proc = _run_cli("avatar-job")
        self.assertEqual(proc.returncode, 2)


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg غير موجود")
class TestCheckAvatarImageCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="avatar-check-")
        self.video, self.image = _make_media(self.tmp)
        self.wide = os.path.join(self.tmp, "wide.png")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                        "-i", "color=c=0x336699:s=720x960:d=1",
                        "-frames:v", "1", self.wide],
                       check=True, timeout=60)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_matching_ratios_no_warning(self):
        proc = _run_cli("check", "--video", self.video,
                        "--avatar-image", self.image)
        self.assertNotIn("نسبة أبعاد الأفاتار", proc.stdout)

    def test_mismatched_ratios_warns(self):
        proc = _run_cli("check", "--video", self.video,
                        "--avatar-image", self.wide)
        self.assertIn("تحذير — نسبة أبعاد الأفاتار", proc.stdout)

    def test_missing_image_warns_not_crash(self):
        proc = _run_cli("check", "--video", self.video,
                        "--avatar-image",
                        os.path.join(self.tmp, "no.png"))
        self.assertIn("تحذير — نسبة أبعاد الأفاتار", proc.stdout)

    def test_exit_code_unaffected(self):
        base = _run_cli("check", "--video", self.video)
        with_flag = _run_cli("check", "--video", self.video,
                             "--avatar-image", self.wide)
        self.assertEqual(base.returncode, with_flag.returncode)


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg غير موجود")
class TestAnalyzeAudioProfileCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="avatar-dna-")
        self.video, _image = _make_media(self.tmp)
        self.audio = os.path.join(self.tmp, "narration.wav")
        _write_wav(self.audio, seconds=2.0)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _saved_report(self, stdout):
        match = re.search(r"حُفظ تقرير DNA في: (\S+)", stdout)
        self.assertIsNotNone(match, stdout[-500:])
        with open(match.group(1), encoding="utf-8") as fh:
            return json.load(fh)

    def test_audio_profile_section_and_saved(self):
        proc = _run_cli("analyze", "--dna", "--video", self.video,
                        "--audio-profile", self.audio)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("-- أداء الصوت --", proc.stdout)
        report = self._saved_report(proc.stdout)
        self.assertIn("audio_profile", report)
        self.assertAlmostEqual(
            report["audio_profile"]["duration_seconds"], 2.0, 1)

    def test_missing_audio_file_warns_dna_still_passes(self):
        proc = _run_cli("analyze", "--dna", "--video", self.video,
                        "--audio-profile",
                        os.path.join(self.tmp, "no.wav"))
        self.assertEqual(proc.returncode, 0)
        self.assertIn("تحذير: تعذر بناء ملف أداء الصوت",
                      proc.stdout)
        self.assertIn("حُفظ تقرير DNA في:", proc.stdout)

    def test_without_dna_notice_and_ignored(self):
        proc = _run_cli("analyze", "--audio-profile", self.audio)
        self.assertIn("يعمل مع --dna فقط", proc.stdout)


class TestAvatarHelpAr(unittest.TestCase):
    def test_entries(self):
        from lib import help_ar
        names = [name for name, _d, _e in help_ar.COMMANDS]
        self.assertIn("avatar-job", names)
        desc = dict((n, d) for n, d, _e in help_ar.COMMANDS)
        self.assertIn("--avatar-image", desc["check"])
        self.assertIn("--audio-profile", desc["analyze"])
        self.assertIn("سلسلة بدائل", desc["script"])
        self.assertIn("--validate", desc["avatar-job"])


if __name__ == "__main__":
    unittest.main()
