#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات وصفات الخطوات المتكررة (lib.recipes) — جولة v0.1.63، بند 37.

تعمل بـ `python3 -m unittest tests.test_recipes -v` من مجلد studio.
بلا ملفات خارجية وبلا شبكة — الوصفات في مجلد مؤقت، والأوامر
المنفَّذة أوامر نظام آمنة قصيرة (echo / python3 -c).
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import recipes

STEPS = [
    {"name": "خطوة أولى", "command": ["echo", "واحد"]},
    {"name": "خطوة ثانية", "command": ["echo", "اثنان"], "note": "ملاحظة"},
]


class TestSaveLoadList(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "recipes")

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_then_load_same_steps(self):
        path = recipes.save_recipe(
            self.dir, "my-recipe", "وصف تجريبي", STEPS
        )
        self.assertTrue(os.path.isfile(path))
        loaded = recipes.load_recipe(self.dir, "my-recipe")
        self.assertEqual(loaded["name"], "my-recipe")
        self.assertEqual(loaded["description"], "وصف تجريبي")
        self.assertEqual(len(loaded["steps"]), 2)
        self.assertEqual(loaded["steps"][0]["command"], ["echo", "واحد"])
        self.assertEqual(loaded["steps"][1]["note"], "ملاحظة")

    def test_list_recipes(self):
        recipes.save_recipe(self.dir, "one", "", STEPS)
        recipes.save_recipe(self.dir, "two", "وصف", STEPS[:1])
        listed = recipes.list_recipes(self.dir)
        self.assertEqual([r["slug"] for r in listed], ["one", "two"])
        self.assertEqual(listed[1]["steps"], 1)

    def test_list_empty_dir(self):
        self.assertEqual(recipes.list_recipes(self.dir), [])

    def test_duplicate_without_overwrite_refused(self):
        recipes.save_recipe(self.dir, "dup", "", STEPS)
        with self.assertRaises(recipes.RecipeError):
            recipes.save_recipe(self.dir, "dup", "", STEPS)

    def test_overwrite_allowed(self):
        recipes.save_recipe(self.dir, "dup", "", STEPS)
        recipes.save_recipe(self.dir, "dup", "جديد", STEPS[:1], overwrite=True)
        self.assertEqual(len(recipes.load_recipe(self.dir, "dup")["steps"]), 1)

    def test_load_missing_raises(self):
        with self.assertRaises(recipes.RecipeError):
            recipes.load_recipe(self.dir, "ghost")

    def test_remove_recipe(self):
        recipes.save_recipe(self.dir, "gone", "", STEPS)
        self.assertTrue(recipes.remove_recipe(self.dir, "gone"))
        self.assertFalse(recipes.remove_recipe(self.dir, "gone"))

    def test_empty_steps_refused(self):
        with self.assertRaises(recipes.RecipeError):
            recipes.save_recipe(self.dir, "empty", "", [])

    def test_too_many_steps_refused(self):
        steps = [{"name": "s%d" % i, "command": ["echo", "x"]}
                 for i in range(recipes.MAX_STEPS + 1)]
        with self.assertRaises(recipes.RecipeError):
            recipes.save_recipe(self.dir, "many", "", steps)

    def test_example_recipe_in_tree_loads(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        example_dir = os.path.join(root, "recipes")
        loaded = recipes.load_recipe(example_dir, "site-ad-assembly")
        self.assertEqual(loaded["name"], "site-ad-assembly")
        self.assertGreaterEqual(len(loaded["steps"]), 1)
        for step in loaded["steps"]:
            self.assertTrue(step["command"])


class TestNoSecrets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "recipes")

    def tearDown(self):
        self.tmp.cleanup()

    def test_secret_in_command_refused(self):
        steps = [{"name": "x", "command": ["echo", "sk-abcdefgh12345678"]}]
        with self.assertRaises(recipes.RecipeError):
            recipes.save_recipe(self.dir, "bad", "", steps)

    def test_secret_in_description_refused(self):
        with self.assertRaises(recipes.RecipeError):
            recipes.save_recipe(
                self.dir, "bad", "api_key=topsecretvalue", STEPS
            )

    def test_secret_in_name_refused(self):
        with self.assertRaises(recipes.RecipeError):
            recipes.save_recipe(
                self.dir, "api_key=topsecretvalue", "", STEPS
            )


class TestRunRecipe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "recipes")

    def tearDown(self):
        self.tmp.cleanup()

    def test_run_returns_same_result_each_time(self):
        recipes.save_recipe(self.dir, "run-me", "", STEPS)
        first = recipes.run_recipe(self.dir, "run-me")
        second = recipes.run_recipe(self.dir, "run-me")
        self.assertTrue(first["ok"])
        self.assertEqual(
            [s["stdout"].strip() for s in first["steps"]],
            ["واحد", "اثنان"],
        )
        self.assertEqual(first["steps"], second["steps"])

    def test_dry_run_executes_nothing(self):
        recipes.save_recipe(self.dir, "dry", "", STEPS)
        report = recipes.run_recipe(self.dir, "dry", dry_run=True)
        self.assertTrue(report["ok"])
        self.assertTrue(
            all(s["returncode"] is None for s in report["steps"])
        )

    def test_failure_stops_at_failed_step(self):
        steps = [
            {"name": "ناجحة", "command": ["echo", "ok"]},
            {"name": "فاشلة",
             "command": ["python3", "-c", "import sys; sys.exit(3)"]},
            {"name": "لا تصل", "command": ["echo", "nope"]},
        ]
        recipes.save_recipe(self.dir, "fail", "", steps)
        report = recipes.run_recipe(self.dir, "fail")
        self.assertFalse(report["ok"])
        self.assertEqual(report["failed_step"], "فاشلة")
        self.assertEqual(report["steps"][2]["returncode"], None)

    def test_missing_command_reports_127(self):
        steps = [{"name": "مفقود", "command": ["no-such-cmd-xyz", "x"]}]
        recipes.save_recipe(self.dir, "missing", "", steps)
        report = recipes.run_recipe(self.dir, "missing")
        self.assertFalse(report["ok"])
        self.assertEqual(report["steps"][0]["returncode"], 127)

    def test_run_writes_into_workdir(self):
        steps = [{"name": "اكتب", "command": ["python3", "-c",
                  "open('out.txt', 'w').write('done')"]}]
        recipes.save_recipe(self.dir, "write", "", steps)
        work = os.path.join(self.tmp.name, "work")
        os.makedirs(work)
        report = recipes.run_recipe(self.dir, "write", workdir=work)
        self.assertTrue(report["ok"])
        with open(os.path.join(work, "out.txt"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "done")


if __name__ == "__main__":
    unittest.main()
