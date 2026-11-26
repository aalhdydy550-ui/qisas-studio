#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات بروفايلات الإعداد — جولة تطبيق الأنماط (W4).

ترتيب الأولوية (افتراضي ← نظام ← مستخدم ← مشروع ← بروفايل
← CLI)؛ والتشخيص ومصدر كل قيمة؛ ورفض مسار خارج مساحة العمل؛
وبروفايل غير موجود ← خطأ عربي واضح؛ وأدوات MCP المدمرة على
prompt دائمًا؛ ورفض الوصول الكامل والأسرار المضمّنة.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import profiles as profiles_lib

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MISSING = os.path.join(tempfile.gettempdir(), "studio-profiles-missing.toml")


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _base_kwargs(**over):
    kwargs = {"studio_root": STUDIO_ROOT, "system_path": MISSING,
              "user_path": MISSING, "project_path": MISSING}
    kwargs.update(over)
    return kwargs


class TestDefaults(unittest.TestCase):
    def test_no_files_gives_safest_defaults(self):
        resolved = profiles_lib.resolve(**_base_kwargs())
        settings = resolved["settings"]
        self.assertEqual(settings["sandbox"], "read-only")
        self.assertEqual(settings["approval"], "untrusted")
        self.assertEqual(settings["network"], "closed")
        self.assertEqual(settings["effort"], "medium")
        self.assertFalse(settings["allow_publish"])
        self.assertFalse(settings["allow_delete"])
        self.assertEqual(resolved["profile"], None)
        self.assertEqual(resolved["profiles"], [])

    def test_default_sources_are_default(self):
        resolved = profiles_lib.resolve(**_base_kwargs())
        for _key, _value, source in profiles_lib.diagnose(resolved):
            self.assertEqual(source, "افتراضي")


class TestPriority(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.system = os.path.join(self.tmp.name, "system.toml")
        self.user = os.path.join(self.tmp.name, "user.toml")
        self.project = os.path.join(self.tmp.name, "project.toml")
        _write(self.system, '[settings]\neffort = "low"\n'
                            'timeout_seconds = 100\n')
        _write(self.user, '[settings]\neffort = "medium"\n')
        _write(self.project, '[settings]\neffort = "high"\n'
                             '[profiles.fast]\neffort = "low"\n'
                             'sandbox = "workspace-write"\n')

    def tearDown(self):
        self.tmp.cleanup()

    def _resolve(self, **over):
        kwargs = {"system_path": self.system, "user_path": self.user,
                  "project_path": self.project, "studio_root": STUDIO_ROOT}
        kwargs.update(over)
        return profiles_lib.resolve(**kwargs)

    def test_project_beats_user_beats_system(self):
        resolved = self._resolve()
        self.assertEqual(resolved["settings"]["effort"], "high")
        self.assertEqual(resolved["sources"]["effort"], "مشروع")
        # timeout جاء من النظام وحده فبقي مصدره نظامًا.
        self.assertEqual(resolved["settings"]["timeout_seconds"], 100)
        self.assertEqual(resolved["sources"]["timeout_seconds"], "نظام")

    def test_user_beats_system_without_project(self):
        resolved = self._resolve(project_path=MISSING)
        self.assertEqual(resolved["settings"]["effort"], "medium")
        self.assertEqual(resolved["sources"]["effort"], "مستخدم")

    def test_profile_beats_project(self):
        resolved = self._resolve(profile="fast")
        self.assertEqual(resolved["settings"]["effort"], "low")
        self.assertEqual(resolved["sources"]["effort"], "بروفايل:fast")
        self.assertEqual(resolved["settings"]["sandbox"], "workspace-write")

    def test_cli_beats_profile(self):
        resolved = self._resolve(profile="fast",
                                 cli_overrides=["effort=high"])
        self.assertEqual(resolved["settings"]["effort"], "high")
        self.assertEqual(resolved["sources"]["effort"], "سطر الأوامر")

    def test_cli_bool_and_int_coercion(self):
        resolved = self._resolve(
            cli_overrides=["allow_publish=true", "max_steps=5"])
        self.assertIs(resolved["settings"]["allow_publish"], True)
        self.assertEqual(resolved["settings"]["max_steps"], 5)

    def test_cli_bad_format_is_arabic_error(self):
        with self.assertRaisesRegex(profiles_lib.ProfileError,
                                    "بلا «=»"):
            self._resolve(cli_overrides=["effort"])

    def test_cli_unknown_key_is_arabic_error(self):
        with self.assertRaisesRegex(profiles_lib.ProfileError,
                                    "غير معروف"):
            self._resolve(cli_overrides=["nope=1"])


class TestShippedProfiles(unittest.TestCase):
    def _resolve(self, **over):
        kwargs = {"studio_root": STUDIO_ROOT, "system_path": MISSING,
                  "user_path": MISSING,
                  "project_path": os.path.join(STUDIO_ROOT,
                                               "profiles.toml")}
        kwargs.update(over)
        return profiles_lib.resolve(**kwargs)

    def test_three_profiles_listed(self):
        self.assertEqual(self._resolve()["profiles"],
                         ["publish", "render", "review"])

    def test_render_is_safe_no_publish(self):
        settings = self._resolve(profile="render")["settings"]
        self.assertEqual(settings["sandbox"], "workspace-write")
        self.assertEqual(settings["approval"], "on-request")
        self.assertEqual(settings["network"], "closed")
        self.assertFalse(settings["allow_publish"])
        self.assertEqual(settings["network_domains"], [])

    def test_publish_allows_publish_only_on_declared_domains(self):
        settings = self._resolve(profile="publish")["settings"]
        self.assertTrue(settings["allow_publish"])
        self.assertEqual(settings["network"], "publish-only")
        self.assertIn("graph.facebook.com",
                      settings["network_domains"])
        self.assertIn("uploads.youtube.com",
                      settings["network_domains"])

    def test_review_is_read_only_high_effort(self):
        settings = self._resolve(profile="review")["settings"]
        self.assertEqual(settings["sandbox"], "read-only")
        self.assertEqual(settings["approval"], "untrusted")
        self.assertEqual(settings["effort"], "high")
        self.assertEqual(settings["network"], "closed")
        self.assertFalse(settings["allow_publish"])

    def test_unknown_profile_is_clear_arabic_error(self):
        with self.assertRaisesRegex(profiles_lib.ProfileError,
                                    "البروفايل «nope» غير موجود"):
            self._resolve(profile="nope")
        try:
            self._resolve(profile="nope")
        except profiles_lib.ProfileError as e:
            self.assertIn("render", str(e))
            self.assertIn("publish", str(e))
            self.assertIn("review", str(e))


class TestDiagnosis(unittest.TestCase):
    def test_diagnosis_lists_every_key_with_source(self):
        resolved = profiles_lib.resolve(**_base_kwargs())
        rows = profiles_lib.diagnose(resolved)
        keys = [key for key, _v, _s in rows]
        self.assertIn("sandbox", keys)
        self.assertIn("effort", keys)
        self.assertIn("mcp.concat.default_tools_approval_mode", keys)
        self.assertEqual(keys, sorted(keys))
        text = profiles_lib.format_diagnosis(resolved)
        self.assertIn("sandbox = read-only (المصدر: افتراضي)", text)
        self.assertIn("البروفايل: بلا بروفايل", text)

    def test_diagnosis_shows_profile_name(self):
        resolved = profiles_lib.resolve(
            studio_root=STUDIO_ROOT, system_path=MISSING,
            user_path=MISSING,
            project_path=os.path.join(STUDIO_ROOT, "profiles.toml"),
            profile="review")
        text = profiles_lib.format_diagnosis(resolved)
        self.assertIn("البروفايل: review", text)
        self.assertIn("sandbox = read-only (المصدر: بروفايل:review)",
                      text)


class TestWorkspacePaths(unittest.TestCase):
    def test_path_inside_roots_passes(self):
        with tempfile.TemporaryDirectory() as root:
            inside = os.path.join(root, "sub", "out.mp4")
            self.assertEqual(
                profiles_lib.check_workspace_path(inside, roots=[root]),
                os.path.realpath(inside))

    def test_dotdot_escape_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            outside = os.path.join(root, "..", "escape.mp4")
            with self.assertRaisesRegex(
                    profiles_lib.ProfileError, "خارج مساحة العمل"):
                profiles_lib.check_workspace_path(outside, roots=[root])

    def test_absolute_outside_path_rejected(self):
        with self.assertRaisesRegex(profiles_lib.ProfileError,
                                    "خارج مساحة العمل"):
            profiles_lib.check_workspace_path("/etc/passwd")

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            target_dir = tempfile.mkdtemp()
            link = os.path.join(root, "link")
            try:
                os.symlink(target_dir, link)
            except OSError:
                self.skipTest("لا روابط رمزية في هذه البيئة")
            with self.assertRaisesRegex(
                    profiles_lib.ProfileError, "خارج مساحة العمل"):
                profiles_lib.check_workspace_path(
                    os.path.join(link, "x.mp4"), roots=[root])


class TestMcpApproval(unittest.TestCase):
    def test_destructive_always_prompt_even_when_allow(self):
        resolved = profiles_lib.resolve(**_base_kwargs())
        settings = resolved["settings"]
        settings["mcp"]["concat"]["default_tools_approval_mode"] = "allow"
        self.assertEqual(
            profiles_lib.mcp_approval_for(settings, "concat", "publish"),
            "prompt")
        self.assertEqual(
            profiles_lib.mcp_approval_for(settings, "concat", "read"),
            "allow")

    def test_unknown_server_fails_closed_to_prompt(self):
        resolved = profiles_lib.resolve(**_base_kwargs())
        self.assertEqual(
            profiles_lib.mcp_approval_for(resolved["settings"],
                                          "no-such-server", "read"),
            "prompt")

    def test_disabled_tool_denied(self):
        resolved = profiles_lib.resolve(**_base_kwargs())
        settings = resolved["settings"]
        # "read" ليست مدمرة، فيسري عليها المنع لا قاعدة prompt.
        settings["mcp"]["concat"]["disabled_tools"] = ["read"]
        settings["mcp"]["concat"]["default_tools_approval_mode"] = "allow"
        self.assertEqual(
            profiles_lib.mcp_approval_for(settings, "concat", "read"),
            "deny")


class TestRejections(unittest.TestCase):
    def test_full_access_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml",
                                         delete=False) as f:
            f.write('[settings]\nsandbox = "full"\n')
            path = f.name
        try:
            with self.assertRaisesRegex(profiles_lib.ProfileError,
                                        "مرفوضة"):
                profiles_lib.resolve(**_base_kwargs(project_path=path))
        finally:
            os.unlink(path)

    def test_embedded_secret_key_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml",
                                         delete=False) as f:
            f.write('[settings]\napi_key = "xxx"\n')
            path = f.name
        try:
            with self.assertRaisesRegex(profiles_lib.ProfileError,
                                        "باسم سرّ"):
                profiles_lib.resolve(**_base_kwargs(project_path=path))
        finally:
            os.unlink(path)

    def test_corrupt_toml_is_arabic_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml",
                                         delete=False) as f:
            f.write('[settings\nbroken = =\n')
            path = f.name
        try:
            with self.assertRaisesRegex(profiles_lib.ProfileError,
                                        "تالف أو غير مقروء"):
                profiles_lib.resolve(**_base_kwargs(project_path=path))
        finally:
            os.unlink(path)

    def test_unknown_setting_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml",
                                         delete=False) as f:
            f.write('[settings]\nnope = 1\n')
            path = f.name
        try:
            with self.assertRaisesRegex(profiles_lib.ProfileError,
                                        "غير معروف"):
                profiles_lib.resolve(**_base_kwargs(project_path=path))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
