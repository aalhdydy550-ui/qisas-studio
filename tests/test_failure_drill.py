#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات وحدة التدريب على الأعطال — جولة v0.1.60.

كل الاختبارات تعمل داخل مجلدات مؤقتة فقط، ولا تقرأ أي ملف
خارج شجرة المستودع إلا ``tmp``.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import failure_drill
from lib.failure_drill import DrillError, list_drills, run_all_drills, run_drill


def _count_files(root):
    """عدّ كل الملفات (والروابط) تحت root بشكل متكرر."""
    total = 0
    for _dirpath, _dirnames, filenames in os.walk(root):
        total += len(filenames)
    return total


class TestListDrills(unittest.TestCase):
    def test_lists_at_least_three(self):
        drills = list_drills()
        self.assertGreaterEqual(len(drills), 3)
        ids = {d["id"] for d in drills}
        self.assertIn("missing-melt", ids)
        self.assertIn("broken-piper-link", ids)
        self.assertIn("pillow-old", ids)

    def test_entries_have_id_and_title(self):
        for entry in list_drills():
            self.assertIsInstance(entry["id"], str)
            self.assertTrue(entry["id"])
            self.assertIsInstance(entry["title"], str)
            self.assertTrue(entry["title"])


class TestEachDrillPasses(unittest.TestCase):
    def test_missing_melt_passes_in_tmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_drill("missing-melt", workdir=tmp)
            self.assertEqual(result["id"], "missing-melt")
            self.assertTrue(result["detected"])
            self.assertEqual(result["status"], "pass")
            self.assertIsInstance(result["title"], str)
            self.assertTrue(result["title"])
            self.assertIsInstance(result["simulated"], str)
            self.assertTrue(result["simulated"])
            self.assertIsInstance(result["detail"], str)
            self.assertTrue(result["detail"])

    def test_broken_piper_link_passes_in_tmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_drill("broken-piper-link", workdir=tmp)
            self.assertEqual(result["id"], "broken-piper-link")
            self.assertTrue(result["detected"])
            self.assertEqual(result["status"], "pass")

    def test_pillow_old_passes_in_tmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_drill("pillow-old", workdir=tmp)
            self.assertEqual(result["id"], "pillow-old")
            self.assertTrue(result["detected"])
            self.assertEqual(result["status"], "pass")


class TestUnknownDrill(unittest.TestCase):
    def test_unknown_id_raises_drill_error(self):
        with self.assertRaises(DrillError) as ctx:
            run_drill("no-such-drill")
        self.assertIn("غير معروف", str(ctx.exception))

    def test_unknown_id_does_not_crash_run_all(self):
        # run_all_drills يشغّل الأعطال المعروفة فقط.
        result = run_all_drills()
        self.assertGreaterEqual(result["summary"]["total"], 3)


class TestRunAllDrills(unittest.TestCase):
    def test_summary_ok_when_all_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_all_drills(workdir=tmp)
        summary = result["summary"]
        self.assertGreaterEqual(summary["total"], 3)
        self.assertEqual(summary["passed"], summary["total"])
        self.assertEqual(summary["failed"], 0)
        self.assertTrue(summary["ok"])
        self.assertEqual(len(result["drills"]), summary["total"])
        for drill in result["drills"]:
            self.assertEqual(drill["status"], "pass")

    def test_run_all_without_workdir(self):
        result = run_all_drills()
        self.assertTrue(result["summary"]["ok"])


class TestSafety(unittest.TestCase):
    def test_environ_and_home_unchanged(self):
        env_before = dict(os.environ)
        home_before = os.environ.get("HOME")
        path_before = os.environ.get("PATH")
        with tempfile.TemporaryDirectory() as tmp:
            run_all_drills(workdir=tmp)
            run_drill("missing-melt", workdir=tmp)
            run_drill("broken-piper-link", workdir=tmp)
            run_drill("pillow-old", workdir=tmp)
        run_all_drills()
        self.assertEqual(dict(os.environ), env_before)
        self.assertEqual(os.environ.get("HOME"), home_before)
        self.assertEqual(os.environ.get("PATH"), path_before)

    def test_no_files_created_outside_workdir(self):
        with tempfile.TemporaryDirectory() as parent:
            workdir = os.path.join(parent, "work")
            os.makedirs(workdir)
            before = _count_files(parent)
            run_all_drills(workdir=workdir)
            run_drill("missing-melt", workdir=workdir)
            after = _count_files(parent)
            # كل الملفات المنشأة داخل workdir فقط؛ ولا ملف
            # جديد خارجها (العدد هنا داخل parent كله، وأي
            # ملف خارج workdir كان سيظهر في العدّ).
            self.assertGreaterEqual(after, before)
            # لا شيء خارج workdir إطلاقًا:
            outside = [p for p in os.listdir(parent) if p != "work"]
            self.assertEqual(outside, [])

    def test_no_files_created_outside_temp_workdir(self):
        # run_all_drills بلا workdir: مجلداته المؤقتة تُنظَّف،
        # فلا يبقى أي أثر في مجلد tmp النظامي.
        tmp_root = tempfile.gettempdir()
        before = {e for e in os.listdir(tmp_root)
                  if e.startswith("failure-drill-")}
        run_all_drills()
        run_drill("missing-melt")
        run_drill("broken-piper-link")
        run_drill("pillow-old")
        after = {e for e in os.listdir(tmp_root)
                 if e.startswith("failure-drill-")}
        self.assertEqual(after, before)

    def test_temp_workdir_cleaned_by_default(self):
        tmp_root = tempfile.gettempdir()
        before = {e for e in os.listdir(tmp_root)
                  if e.startswith("failure-drill-")}
        run_drill("missing-melt")
        run_drill("broken-piper-link")
        run_drill("pillow-old")
        after = {e for e in os.listdir(tmp_root)
                 if e.startswith("failure-drill-")}
        self.assertEqual(after, before)

    def test_caller_workdir_is_never_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_drill("missing-melt", workdir=tmp)
            run_all_drills(workdir=tmp)
            self.assertTrue(os.path.isdir(tmp))


if __name__ == "__main__":
    unittest.main()
