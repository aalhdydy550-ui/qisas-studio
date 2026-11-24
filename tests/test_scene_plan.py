#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات خطة المشاهد وسقف Veo (lib.scene_plan) — الجولة 7.

تعمل بـ `python3 -m unittest discover -s tests -v`.
كل الكتابة في مجلدات مؤقتة — لا يُمس config.yaml الحقيقي
ولا أي رصيد Veo فعلي.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import scene_plan

TEXT_8 = ("كان فيه راجل ظالم. سرق مال أخوه. أنكر الوصية. "
          "هرب من القرية. رجعت الرسالة لصاحبتها. انكشف الحق. "
          "اعتذر للناس. وعاش بعدها راضيًا.")


def _cfg(tmpdir, balance=680, cap=None):
    veo = {"balance_units": balance, "renews": "2026-12-13"}
    if cap is not None:
        veo["cap_units"] = cap
    return {
        "paths": {
            "queue_file": os.path.join(tmpdir, "queue.md"),
            "videos_dir": os.path.join(tmpdir, "videos"),
            "runs_dir": os.path.join(tmpdir, "runs"),
        },
        "veo": veo,
    }


class TestBuildScenePlan(unittest.TestCase):
    def _story(self, note="تحتاج جزأين (النص: queue/4-test.txt)"):
        return {"number": 4, "title": "العنزة المباركة", "note": note}

    def test_from_text_file(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            text_path = os.path.join(td, "4-test.txt")
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(TEXT_8)
            real = scene_plan.story_text_path
            scene_plan.story_text_path = lambda c, s: text_path
            try:
                plan = scene_plan.build_scene_plan(cfg, self._story())
            finally:
                scene_plan.story_text_path = real
            self.assertEqual(len(plan["scenes"]), 6)
            self.assertEqual(plan["total_units"], 120)
            self.assertFalse(plan["draft_prompts"])
            self.assertIn("كان فيه راجل ظالم",
                          plan["scenes"][0]["prompt"])

    def test_story_text_path_anchored(self):
        """انحدار: «queue/...» كان يُحلّ مقابل CWD — فمن أي
        مجلد غير studio لا يُوجد الملف أبدًا وتسقط الخطة بصمت
        إلى موجِّهات مسودة."""
        import os
        from lib import paths as paths_lib
        with tempfile.TemporaryDirectory() as td:
            fake_studio = os.path.join(td, "studio")
            queue_dir = os.path.join(fake_studio, "queue")
            os.makedirs(queue_dir)
            text_path = os.path.join(queue_dir, "4-test.txt")
            with open(text_path, "w", encoding="utf-8") as f:
                f.write(TEXT_8)
            elsewhere = os.path.join(td, "elsewhere")
            os.makedirs(elsewhere)
            old_cwd = os.getcwd()
            old_root = paths_lib.WORKSPACE_ROOT
            # الحصر داخل مساحة العمل باقٍ — رقّع جذرها إلى
            # المجلد المؤقت لهذا الاختبار فقط.
            paths_lib.WORKSPACE_ROOT = td
            os.chdir(elsewhere)
            try:
                found = scene_plan.story_text_path(
                    _cfg(td), self._story(),
                    studio_dir=fake_studio)
            finally:
                os.chdir(old_cwd)
                paths_lib.WORKSPACE_ROOT = old_root
            self.assertEqual(found, text_path)

    def test_story_text_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            story = {"number": 4, "title": "العنزة المباركة",
                     "note": "النص: queue/../../etc/passwd"}
            self.assertIsNone(
                scene_plan.story_text_path(_cfg(td), story,
                                           studio_dir=td))

    def test_draft_when_no_text(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            plan = scene_plan.build_scene_plan(cfg, self._story())
            self.assertTrue(plan["draft_prompts"])
            self.assertEqual(len(plan["scenes"]), 6)
            self.assertIn("العنزة المباركة",
                          plan["scenes"][0]["prompt"])

    def test_fewer_clips(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            plan = scene_plan.build_scene_plan(cfg, self._story(),
                                               clips=3)
            self.assertEqual(len(plan["scenes"]), 3)
            self.assertEqual(plan["total_units"], 60)

    def test_invalid_clips(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            with self.assertRaises(ValueError):
                scene_plan.build_scene_plan(cfg, self._story(), clips=0)
            with self.assertRaises(ValueError):
                scene_plan.build_scene_plan(cfg, self._story(), clips=13)

    def test_cap_refused(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td, cap=100)
            with self.assertRaises(scene_plan.CapError) as cm:
                scene_plan.build_scene_plan(cfg, self._story())
            self.assertIn("يتجاوز سقف", str(cm.exception))

    def test_cap_exact_passes(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td, cap=120)
            plan = scene_plan.build_scene_plan(cfg, self._story())
            self.assertEqual(plan["total_units"], 120)

    def test_balance_refused(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td, balance=100)
            with self.assertRaises(scene_plan.CapError) as cm:
                scene_plan.build_scene_plan(cfg, self._story())
            self.assertIn("الرصيد", str(cm.exception))

    def test_save_and_format(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            plan = scene_plan.build_scene_plan(cfg, self._story())
            path = scene_plan.save_plan(plan, cfg["paths"]["runs_dir"])
            self.assertTrue(os.path.isfile(path))
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["total_units"], 120)
            text = scene_plan.format_plan(plan)
            self.assertIn("العنزة المباركة", text)
            self.assertIn("120 وحدة", text)


class TestRequestApproval(unittest.TestCase):
    PLAN = {"total_units": 120, "scenes": []}

    def test_auto_approve(self):
        self.assertTrue(scene_plan.request_approval(
            self.PLAN, auto_approve=True, is_tty=True,
            input_fn=lambda prompt: "لا"))

    def test_non_tty_proceeds(self):
        self.assertTrue(scene_plan.request_approval(
            self.PLAN, auto_approve=False, is_tty=False,
            input_fn=lambda prompt: "لا"))

    def test_tty_yes(self):
        self.assertTrue(scene_plan.request_approval(
            self.PLAN, auto_approve=False, is_tty=True,
            input_fn=lambda prompt: "نعم"))

    def test_tty_no(self):
        self.assertFalse(scene_plan.request_approval(
            self.PLAN, auto_approve=False, is_tty=True,
            input_fn=lambda prompt: "لا"))


if __name__ == "__main__":
    unittest.main()
