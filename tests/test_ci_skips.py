#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات انحدار لتخطي CI — جولة v0.1.38 (إصلاح CI).

كل اختبار معتمد على بيئة المستخدم (فيديو ديمو، كابشنات،
مشروع العنزة، Piper، ffmpeg) يجب أن يتخطى نظيفًا (skipped)
لا أن يفشل عند غياب البيئة. تُتحقق هنا بتشغيل الاختبار
المستهدف في عملية فرعية بـHOME فارغة وPATH بلا ffmpeg،
والنجاح = ظهور «skipped» في المخرجات بلا FAIL/ERROR.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_test_in_bare_env(test_id, with_ffmpeg=True,
                          without_venvs=False):
    """شغّل اختبارًا واحدًا في عملية فرعية: HOME فارغ، وPATH
    بلا ffmpeg إلا إن طُلب. يرجع (returncode, stdout+stderr).
    without_venvs: شغّل من نسخة مصغّرة من الشجرة (lib/ +
    tests/ + setup.sh) بلا أي .venv-* — تحاكي checkout نظيفًا
    في CI حيث بيئات الأدوات المحلية غائبة أصلًا."""
    home = tempfile.mkdtemp(prefix="ci-home-")
    env = {"HOME": home, "PATH": ""}
    bindir = tempfile.mkdtemp(prefix="ci-bin-")
    python_link = os.path.join(bindir, "python3")
    os.symlink(sys.executable, python_link)
    os.symlink(sys.executable, os.path.join(bindir, "python"))
    if with_ffmpeg:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            os.symlink(ffmpeg, os.path.join(bindir, "ffmpeg"))
        ffprobe = shutil.which("ffprobe")
        if ffprobe:
            os.symlink(ffprobe, os.path.join(bindir, "ffprobe"))
    env["PATH"] = bindir
    cwd = STUDIO_DIR
    if without_venvs:
        cwd = tempfile.mkdtemp(prefix="ci-tree-")
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
        for sub in ("lib", "tests"):
            shutil.copytree(os.path.join(STUDIO_DIR, sub),
                            os.path.join(cwd, sub), ignore=ignore)
        shutil.copy2(os.path.join(STUDIO_DIR, "setup.sh"),
                     os.path.join(cwd, "setup.sh"))
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", test_id, "-v"],
        cwd=cwd, capture_output=True, text=True,
        env=env, timeout=300)
    return proc.returncode, proc.stdout + proc.stderr


class TestCiSkips(unittest.TestCase):
    def _assert_skipped(self, test_id, with_ffmpeg=True,
                        without_venvs=False):
        rc, out = _run_test_in_bare_env(test_id, with_ffmpeg,
                                        without_venvs)
        self.assertEqual(rc, 0, out[-2000:])
        self.assertIn("skipped", out.lower(), out[-2000:])
        self.assertNotIn("FAILED", out)

    def test_demo_tests_skip_without_demo_video(self):
        self._assert_skipped(
            "tests.test_round9_wiring."
            "TestAbVariantsWiring.test_ab_variants_ranked_with_winner")

    def test_captions_tests_skip_without_subs(self):
        self._assert_skipped(
            "tests.test_round9_wiring."
            "TestCheckCaptionsWiring.test_check_captions_real_subs_pass")

    def test_real_ass_tests_skip_without_subs(self):
        self._assert_skipped(
            "tests.test_ass_shaping."
            "TestRealCaptions.test_real_aisha2_and_najjar_pass")

    def test_real_coverage_tests_skip_without_anza_run(self):
        self._assert_skipped(
            "tests.test_coverage."
            "TestSceneCoverage.test_real_anza_manifest_passes")

    def test_first_scene_tests_skip_without_anza_project(self):
        self._assert_skipped(
            "tests.test_first_scene."
            "TestFirstSceneSample.test_daily_dry_run_prints_sample")

    def test_piper_tests_skip_without_piper(self):
        self._assert_skipped(
            "tests.test_long_narration."
            "TestSynthesizeLong.test_two_sentences_with_gap")

    def test_audio_profile_tests_skip_without_ffmpeg(self):
        self._assert_skipped(
            "tests.test_audio_profile."
            "TestEnergyCurve.test_six_buckets",
            with_ffmpeg=False)

    def test_avatar_job_tests_skip_without_ffmpeg(self):
        self._assert_skipped(
            "tests.test_avatar_job."
            "TestValidateJob.test_valid_single_person_passes",
            with_ffmpeg=False)

    def test_template_json_parseable_in_bare_env(self):
        """انحدار: تحذير حارس بدء التشغيل (أدوات غائبة) يذهب
        إلى stderr لا stdout — فمخرج `avatar-job --template`
        يبقى JSON نقيًا قابلًا للقراءة الآلية في بيئة متدهورة
        (عيب كشفته المحاكاة العارية: كان التحذير يسبق JSON
        في stdout فيكسر json.loads)."""
        import json
        home = tempfile.mkdtemp(prefix="ci-home-")
        bindir = tempfile.mkdtemp(prefix="ci-bin-")
        os.symlink(sys.executable, os.path.join(bindir, "python3"))
        os.symlink(sys.executable, os.path.join(bindir, "python"))
        env = {"HOME": home, "PATH": bindir}
        proc = subprocess.run(
            [sys.executable, "studio.py", "avatar-job", "--template"],
            cwd=STUDIO_DIR, capture_output=True, text=True,
            env=env, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr[-1000:])
        tpl = json.loads(proc.stdout)
        self.assertIn("prompt", tpl)
        self.assertIn("person1", tpl["cond_audio"])
        self.assertIn("أدوات غائبة", proc.stderr)

    def test_eval_snapshot_skips_without_eval_videos(self):
        self._assert_skipped(
            "tests.test_eval_set_manifest."
            "TestEvalSet.test_snapshot_cli_matches_baseline")

    def test_status_english_skips_without_local_tools(self):
        """انحدار جولة v0.1.42 (إصلاح CI #255): `status` الإنجليزي
        يتخطى في بيئة عارية — كلمة «exists» لا تطبعها إلا مسارات
        أدوات الاستوديو المحلية (OpenMontage/Concat/headless)
        الغائبة في CI، والخادم وحده لا يحدد النتيجة (الاختبار
        يمر محليًا والخادم متوقف)."""
        self._assert_skipped(
            "tests.test_i18n.TestCmdWiring.test_status_english")

    def test_verify_cli_skips_without_gtts_venv(self):
        """انحدار جولة v0.1.42 (إصلاح CI #255): تحقق `verify`
        من gtts يتخطى في checkout نظيف بلا .venv-* — بيئة gtts
        محلية فقط، و`verify` يفشل فيها بـ«بلا بيئة» لا بخلل
        في الكود."""
        self._assert_skipped(
            "tests.test_setup_alpha_patterns.TestSha256Verify."
            "test_verify_cli_exit_codes",
            without_venvs=True)

    def test_status_arabic_skips_without_local_tools(self):
        """انحدار جولة v0.1.42: الشقيق العربي لـtest_status_english
        يتخطى في بيئة عارية — تأكيده «موجود» صُحّح ليطابق
        سطر «المسار: موجود» لا السلسلة الجزئية داخل
        «غير موجود» (كان يمرّ صوريًا في CI)."""
        self._assert_skipped(
            "tests.test_i18n.TestCmdWiring.test_status_arabic_default")


class TestCiWorkflow(unittest.TestCase):
    def test_ci_installs_ffmpeg(self):
        """انحدار: سير العمل يثبّت ffmpeg (سبب ~50 فشلًا سابقًا)."""
        path = os.path.join(STUDIO_DIR, ".github", "workflows",
                            "ci.yml")
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn("apt-get install -y ffmpeg", content)
        self.assertIn("python -m unittest discover -s tests", content)

    def test_ci_installs_arabic_font_and_node24_actions(self):
        """انحدار جولة v0.1.41 (إصلاح CI #247): سير العمل يثبّت
        خط Noto Naskh Arabic، ويستخدم checkout v5 وsetup-python
        v6 (أول نسختين على Node 24 — v4/v5 كانتا على Node 20)."""
        path = os.path.join(STUDIO_DIR, ".github", "workflows",
                            "ci.yml")
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn("fonts-noto-core", content)
        self.assertIn("actions/checkout@v5", content)
        self.assertIn("actions/setup-python@v6", content)
        self.assertNotIn("actions/checkout@v4", content)
        self.assertNotIn("actions/setup-python@v5", content)

    def test_setup_scripts_live_in_repo_and_parse(self):
        """انحدار جولة v0.1.41: سكربتا الإعداد داخل شجرة
        المستودع (لا في ~/workspace/ خارجها) ويمرّان bash -n —
        غيابهما عن نسخة CI أسقط اختبار AGPL و~13 اختبار
        test_ensure_env في #247."""
        import subprocess
        for name in ("setup-env.sh", "ensure-env.sh"):
            path = os.path.join(STUDIO_DIR, name)
            self.assertTrue(os.path.isfile(path),
                            "سكربت الإعداد مفقود من المستودع: %s" % path)
            r = subprocess.run(["/bin/bash", "-n", path],
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, "%s: %s" % (path, r.stderr))


if __name__ == "__main__":
    unittest.main()
