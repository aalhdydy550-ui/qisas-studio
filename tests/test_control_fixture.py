#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات تركيبة التحكم المعزولة (lib.control_fixture) — بند 17، جولة v0.1.63.

زوج موجب/سالب لكل سلوك: التركيبة تستخدم مجلدًا مؤقتًا لا
الحقيقي؛ ورفض أمر تعديل بلا هدف صريح؛ وأن خريطة السلوك
تطابق الأفعال التي يقودها الحزام (أو موسومة كقيد صراحة).

معزولة: `tempfile` فقط، بلا شبكة، بلا ملفات خارج الشجرة.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import control_fixture as cf


class TestFreePort(unittest.TestCase):
    def test_free_port_is_usable_local_port(self):
        port = cf.free_port()
        self.assertIsInstance(port, int)
        self.assertGreater(port, 0)
        self.assertLessEqual(port, 65535)


class TestChildEnv(unittest.TestCase):
    def test_only_fake_claude_vars_pass_through(self):
        env = cf.child_env({
            "FAKE_CLAUDE_MODE": "echo",
            "FAKE_CLAUDE_RESPONSES": "hi",
            "HOME": "/home/real-user",
            "GEMINI_API_KEY": "sk-real-key",
            "QISAS_STUDIO_DATA_DIR": "/home/real-user/studio",
            "PATH": "/usr/bin",
        })
        self.assertEqual(env, {
            "FAKE_CLAUDE_MODE": "echo",
            "FAKE_CLAUDE_RESPONSES": "hi",
        })

    def test_real_home_and_keys_never_pass(self):
        env = cf.child_env({"HOME": "/home/real-user"})
        self.assertNotIn("HOME", env)


class TestControlFixture(unittest.TestCase):
    def test_fixture_uses_temp_dirs_not_real_ones(self):
        real_home = os.path.expanduser("~")
        with cf.ControlFixture() as fx:
            self.assertNotEqual(fx.data_dir, real_home)
            self.assertNotEqual(fx.home_dir, real_home)
            self.assertTrue(fx.data_dir.startswith(tempfile.gettempdir()))
            self.assertTrue(fx.home_dir.startswith(tempfile.gettempdir()))
            self.assertTrue(os.path.isdir(fx.data_dir))
            self.assertTrue(os.path.isdir(fx.home_dir))
            self.assertNotEqual(fx.data_dir, fx.home_dir)
            self.assertTrue(fx.url.startswith("http://127.0.0.1:"))
            self.assertEqual(fx.engine, cf.FAKE_ENGINE_NAME)
            self.assertNotEqual(fx.port, fx.control_port)

    def test_child_environment_is_isolated(self):
        base = {"FAKE_CLAUDE_MODE": "echo", "HOME": "/home/real-user",
                "SECRET_KEY": "sk-real"}
        with cf.ControlFixture(base_env=base) as fx:
            env = fx.child_environment()
            self.assertEqual(env["HOME"], fx.home_dir)
            self.assertEqual(env["QISAS_STUDIO_DATA_DIR"], fx.data_dir)
            self.assertEqual(env["FAKE_CLAUDE_MODE"], "echo")
            self.assertNotIn("SECRET_KEY", env)

    def test_configure_fake_engine_writes_recipe_inside_fixture(self):
        with cf.ControlFixture() as fx:
            path = fx.configure_fake_engine(
                mode="scripted", responses=["hello"],
                tool_calls=["read-log"])
            self.assertTrue(path.startswith(fx.data_dir))
            import json
            with open(path, encoding="utf-8") as handle:
                recipe = json.load(handle)
            self.assertEqual(recipe["engine"], "fake")
            self.assertEqual(recipe["mode"], "scripted")
            self.assertEqual(recipe["responses"], ["hello"])

    def test_start_and_cleanup(self):
        tmp_root = None
        with cf.ControlFixture() as fx:
            tmp_root = fx._tmp
            pid = fx.start()
            self.assertIsInstance(pid, int)
            self.assertGreater(pid, 0)
            self.assertEqual(fx.pid, pid)
            self.assertTrue(os.path.isdir(tmp_root))
        self.assertIsNone(fx.pid)
        self.assertFalse(os.path.exists(tmp_root))

    def test_target_points_at_fixture(self):
        with cf.ControlFixture() as fx:
            target = fx.target()
            self.assertEqual(target.data_dir, fx.data_dir)
            self.assertEqual(target.port, fx.port)


class TestRequireExplicitTarget(unittest.TestCase):
    def test_mutating_verbs_refuse_silent_target(self):
        for verb in ("publish", "delete", "send", "stop", "approve",
                     "interrupt-job", "switch-model"):
            with self.subTest(verb=verb):
                with self.assertRaises(cf.ControlError):
                    cf.require_explicit_target(verb, None)

    def test_read_verbs_allow_no_target(self):
        for verb in ("inspect", "jobs", "read-log", "status", "list"):
            with self.subTest(verb=verb):
                self.assertIsNone(cf.require_explicit_target(verb, None))

    def test_unknown_verb_rejected(self):
        with self.assertRaises(cf.ControlError):
            cf.require_explicit_target("explode", None)


class TestRunControl(unittest.TestCase):
    def test_mutating_without_target_or_fixture_refused(self):
        with self.assertRaises(cf.ControlError):
            cf.run_control("publish")

    def test_mutating_with_fixture_target_runs_handler(self):
        calls = []

        def handler(verb, target):
            calls.append((verb, target))
            return {"ok": True, "verb": verb}

        with cf.ControlFixture() as fx:
            result = cf.run_control("publish", handler=handler, fixture=fx)
        self.assertEqual(result, {"ok": True, "verb": "publish"})
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1].data_dir, fx.data_dir)

    def test_read_without_handler_returns_summary(self):
        result = cf.run_control("inspect")
        self.assertTrue(result["ok"])
        self.assertEqual(result["verb"], "inspect")
        self.assertIsNone(result["target"])

    def test_same_handler_drives_published_action(self):
        # سطح التحكم يشغّل الفعل المنشور نفسه: نفس المعالج
        # يُستدعى بالفعل والهدف نفسيهما.
        seen = {}

        def handler(verb, target):
            seen["verb"] = verb
            seen["target"] = target
            return {"ok": True}

        with cf.ControlFixture() as fx:
            target = fx.target(label="explicit")
            cf.run_control("send-work", target=target, handler=handler)
        self.assertEqual(seen["verb"], "send-work")
        self.assertEqual(seen["target"].label, "explicit")

    def test_explicit_target_beats_fixture(self):
        with cf.ControlFixture() as fx:
            other = cf.ControlTarget(fx.data_dir, label="other")
            result = cf.run_control(
                "stop", target=other,
                handler=lambda verb, t: {"label": t.label}, fixture=fx)
        self.assertEqual(result["label"], "other")


class TestBehaviorMap(unittest.TestCase):
    def test_every_entry_is_harness_driven_or_has_constraint(self):
        for entry in cf.behavior_map_entries():
            with self.subTest(entry=entry["id"]):
                self.assertTrue(entry["id"])
                self.assertTrue(entry["description"])
                self.assertTrue(entry["harness"] or entry["constraint"],
                                "مدخل بلا حزام ولا قيد: %s" % entry["id"])

    def test_map_matches_control_map_md(self):
        md_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "CONTROL-MAP.md")
        with open(md_path, encoding="utf-8") as handle:
            md = handle.read()
        for entry in cf.behavior_map_entries():
            with self.subTest(entry=entry["id"]):
                self.assertIn("`%s`" % entry["id"], md)
                if not entry["harness"]:
                    self.assertIn(entry["constraint"], md)

    def test_viewer_only_behavior_is_explicit_constraint(self):
        entries = {e["id"]: e for e in cf.behavior_map_entries()}
        viewer = entries["viewer-only-behavior"]
        self.assertFalse(viewer["harness"])
        self.assertIn("لا يثبته الحزام", viewer["constraint"])


if __name__ == "__main__":
    unittest.main()
