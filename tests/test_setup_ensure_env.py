#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات إدارة البيئات — lib.ensure_env (حزمة v0.1.41).

بلا شبكة وبلا مساس بالبيئة الحية: كل الاختبارات في مجلدات
مؤقتة، وأداة وهمية بحزم فارغة تختبر إنشاء البيئة فعليًا
(``python3 -m venv`` محلي فقط).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import ensure_env


class TestRegistry(unittest.TestCase):
    def test_five_tools_registered(self):
        self.assertEqual(set(ensure_env.TOOLS),
                         {"gtts", "youtube", "autoeditor",
                          "whisper", "moviepy"})

    def test_light_tools_share_one_group(self):
        light = [n for n, s in ensure_env.TOOLS.items()
                 if not s["heavy"]]
        self.assertEqual(sorted(light),
                         ["autoeditor", "gtts", "youtube"])
        for n in light:
            self.assertEqual(ensure_env.TOOLS[n]["group"], "tools")

    def test_heavy_tools_are_lazy_and_unshared(self):
        for n in ("whisper", "moviepy"):
            spec = ensure_env.TOOLS[n]
            self.assertTrue(spec["heavy"])
            self.assertIsNone(spec["group"])

    def test_legacy_names_unique(self):
        legacies = [s["legacy"] for s in ensure_env.TOOLS.values()]
        self.assertEqual(len(legacies), len(set(legacies)))

    def test_every_tool_has_packages_and_import(self):
        for n, spec in ensure_env.TOOLS.items():
            self.assertTrue(spec["packages"], n)
            self.assertTrue(spec["import"], n)


class TestResolve(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _fake_venv(self, name, with_python=True):
        d = os.path.join(self.root, name, "bin")
        os.makedirs(d, exist_ok=True)
        if with_python:
            p = os.path.join(d, "python")
            with open(p, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\nexit 0\n")
            os.chmod(p, 0o755)
        return d

    def test_missing_tool_resolves_to_none(self):
        python, where = ensure_env.resolve_python(self.root, "gtts")
        self.assertIsNone(python)
        self.assertIsNone(where)

    def test_legacy_venv_preferred(self):
        self._fake_venv(".venv-gtts")
        self._fake_venv(".venv-youtube")
        python, where = ensure_env.resolve_python(self.root, "gtts")
        self.assertEqual(where, "legacy")
        self.assertIn(".venv-gtts", python)

    def test_shared_venv_used_when_legacy_absent(self):
        # gtts بلا بيئة قديمة → تُحل إلى المشتركة (.venv-youtube).
        self._fake_venv(".venv-youtube")
        python, where = ensure_env.resolve_python(self.root, "gtts")
        self.assertEqual(where, "shared")
        self.assertIn(".venv-youtube", python)

    def test_youtube_legacy_is_the_shared_home(self):
        # يوتيوب: بيئتها القديمة هي المشتركة نفسها.
        self._fake_venv(".venv-youtube")
        python, where = ensure_env.resolve_python(self.root, "youtube")
        self.assertEqual(where, "legacy")
        self.assertIn(".venv-youtube", python)

    def test_heavy_tool_never_resolves_to_shared(self):
        self._fake_venv(".venv-youtube")
        python, where = ensure_env.resolve_python(self.root, "whisper")
        self.assertIsNone(python)
        self.assertIsNone(where)

    def test_target_dirs(self):
        self.assertTrue(ensure_env.target_venv_dir(
            self.root, "gtts").endswith(".venv-youtube"))
        self.assertTrue(ensure_env.target_venv_dir(
            self.root, "whisper").endswith(".venv-whisper"))


class TestLinkAliases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, ".venv-youtube", "bin"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_links_created_for_missing_legacy(self):
        # المشتركة نفسها (.venv-youtube) تُتخطى؛ الرابطان الآخران فقط.
        results = ensure_env.link_legacy_aliases(root=self.root)
        by_name = {n: a for n, a, _d in results}
        self.assertEqual(by_name, {"gtts": "linked",
                                   "youtube": "kept",
                                   "autoeditor": "linked"})
        for legacy in (".venv-gtts", ".venv-autoeditor"):
            self.assertTrue(os.path.islink(
                os.path.join(self.root, legacy)))
            self.assertEqual(os.readlink(
                os.path.join(self.root, legacy)), ".venv-youtube")
        self.assertFalse(os.path.islink(
            os.path.join(self.root, ".venv-youtube")))

    def test_real_legacy_venv_is_kept(self):
        os.makedirs(os.path.join(self.root, ".venv-gtts", "bin"))
        results = ensure_env.link_legacy_aliases(root=self.root)
        by_name = {n: a for n, a, _d in results}
        self.assertEqual(by_name["gtts"], "kept")
        self.assertFalse(os.path.islink(
            os.path.join(self.root, ".venv-gtts")))

    def test_dry_run_creates_nothing(self):
        results = ensure_env.link_legacy_aliases(root=self.root,
                                                 dry_run=True)
        by_name = {n: a for n, a, _d in results}
        self.assertEqual(by_name, {"gtts": "would-link",
                                   "youtube": "kept",
                                   "autoeditor": "would-link"})
        self.assertFalse(os.path.lexists(
            os.path.join(self.root, ".venv-gtts")))


class TestDistIntegrity(unittest.TestCase):
    """تثبيت مقطوع (بيانات وصفية تالفة) لا يُحسب جاهزًا."""

    def test_pkg_name_strips_specifiers(self):
        self.assertEqual(ensure_env._pkg_name("auto-editor==29.3.1"),
                         "auto-editor")
        self.assertEqual(ensure_env._pkg_name("gtts"), "gtts")
        self.assertEqual(ensure_env._pkg_name("moviepy>=2.0"), "moviepy")

    def test_disk_free_mb(self):
        self.assertGreaterEqual(
            ensure_env.disk_free_mb(tempfile.gettempdir()), 0)
        self.assertEqual(ensure_env.disk_free_mb(
            "/nonexistent-path-xyz"), -1)

    def test_broken_dist_info_is_not_ready(self):
        with tempfile.TemporaryDirectory() as root:
            venv = os.path.join(root, ".venv-brokentest")
            subprocess.run([sys.executable, "-m", "venv", venv],
                           check=True, timeout=120)
            site = subprocess.run(
                [os.path.join(venv, "bin", "python"), "-c",
                 "import sysconfig; print(sysconfig.get_path('purelib'))"],
                capture_output=True, text=True, check=True,
                timeout=60).stdout.strip()
            broken = os.path.join(site, "brokentest-1.0.dist-info")
            os.makedirs(broken)
            with open(os.path.join(broken, "METADATA"), "w",
                      encoding="utf-8") as f:
                f.write("garbage without a Name field\n")
            orig = dict(ensure_env.TOOLS)
            ensure_env.TOOLS["brokentest"] = {
                "legacy": ".venv-brokentest",
                "group": None,
                "packages": ["brokentest"],
                "import": "json",
                "heavy": True,
                "desc": "أداة اختبار ببيانات تالفة",
            }
            try:
                # الاستيراد وحده ينجح (json) — لكن البيانات تالفة.
                self.assertTrue(ensure_env._import_ok(
                    os.path.join(venv, "bin", "python"), "json"))
                self.assertFalse(ensure_env._dist_ok(
                    os.path.join(venv, "bin", "python"),
                    ["brokentest"]))
                st = ensure_env.status(root, "brokentest")
                self.assertFalse(st["ready"])
            finally:
                ensure_env.TOOLS.clear()
                ensure_env.TOOLS.update(orig)


class TestEnsureDryRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_unknown_tool(self):
        ok, msg = ensure_env.ensure("nope", root=self.root)
        self.assertFalse(ok)
        self.assertIn("غير معروفة", msg)

    def test_dry_run_creates_nothing(self):
        ok, msg = ensure_env.ensure("whisper", root=self.root,
                                    dry_run=True)
        self.assertTrue(ok)
        self.assertIn("WOULD", msg)
        self.assertFalse(os.path.exists(
            os.path.join(self.root, ".venv-whisper")))

    def test_broken_legacy_heavy_venv_is_not_deleted(self):
        os.makedirs(os.path.join(self.root, ".venv-whisper", "bin"))
        ok, msg = ensure_env.ensure("whisper", root=self.root)
        self.assertFalse(ok)
        self.assertIn("احذفه يدويًا", msg)
        self.assertTrue(os.path.isdir(
            os.path.join(self.root, ".venv-whisper")))


class TestEnsureRealWithFakeTool(unittest.TestCase):
    """إنشاء بيئة حقيقي بلا شبكة: أداة وهمية بلا حزم واستيراد stdlib."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self._orig = dict(ensure_env.TOOLS)
        ensure_env.TOOLS["tinytest"] = {
            "legacy": ".venv-tinytest",
            "group": None,
            "packages": [],
            "import": "json",
            "heavy": True,
            "desc": "أداة اختبار وهمية",
        }

    def tearDown(self):
        ensure_env.TOOLS.clear()
        ensure_env.TOOLS.update(self._orig)
        self.tmp.cleanup()

    def test_ensure_creates_venv_and_verifies_import(self):
        ok, msg = ensure_env.ensure("tinytest", root=self.root)
        self.assertTrue(ok, msg)
        venv = os.path.join(self.root, ".venv-tinytest")
        self.assertTrue(os.path.isfile(
            os.path.join(venv, "bin", "python")))
        st = ensure_env.status(self.root, "tinytest")
        self.assertTrue(st["ready"])
        self.assertEqual(st["where"], "legacy")

    def test_ensure_second_time_is_noop(self):
        ensure_env.ensure("tinytest", root=self.root)
        ok, msg = ensure_env.ensure("tinytest", root=self.root)
        self.assertTrue(ok)
        self.assertIn("جاهز", msg)


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, *args):
        cmd = [sys.executable, "-m", "lib.ensure_env",
               "--root", self.root] + list(args)
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            cwd=os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))))

    def test_check_empty_root_fails(self):
        r = self._run("check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("[MISS] gtts", r.stdout)
        self.assertIn("[LAZY] whisper", r.stdout)

    def test_check_json(self):
        r = self._run("check", "--json")
        self.assertEqual(r.returncode, 1)
        data = json.loads(r.stdout)
        self.assertEqual(set(data), set(ensure_env.TOOLS))
        self.assertFalse(data["whisper"]["ready"])

    def test_install_dry_run_shared_creates_nothing(self):
        r = self._run("install", "--shared", "--dry-run")
        self.assertEqual(r.returncode, 0)
        self.assertIn("WOULD", r.stdout)
        self.assertFalse(os.path.exists(
            os.path.join(self.root, ".venv-youtube")))

    def test_install_unknown_tool_exit_2(self):
        r = self._run("install", "nope")
        self.assertEqual(r.returncode, 2)

    def test_no_command_exit_2(self):
        r = self._run()
        self.assertEqual(r.returncode, 2)

    def test_help_exit_0(self):
        r = self._run("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("install --shared", r.stdout)


if __name__ == "__main__":
    unittest.main()
