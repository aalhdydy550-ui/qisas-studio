#!/usr/bin/env python3
"""اختبارات الدفعات الجماعية (lib.batch) — الجولة 7.

تعمل بـ `python3 -m unittest discover -s tests -v`.
كل الكتابة في مجلدات مؤقتة — لا يُمس الطابور الحقيقي ولا
أي منشور، وبلا أي إنفاق Veo (الإنتاج والفحص والمصغرة كلها
دوال مزيفة محقونة).
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import batch

QUEUE_TEXT = """# طابور قصص

## في الانتظار

4. **العنزة المباركة** — تحتاج جزأين
5. **عجائب الصدقة** — منشور واحد
"""


def _cfg(tmpdir, balance=680, cap=None):
    queue = os.path.join(tmpdir, "queue.md")
    with open(queue, "w", encoding="utf-8") as f:
        f.write(QUEUE_TEXT)
    veo = {"balance_units": balance, "renews": "2026-12-13"}
    if cap is not None:
        veo["cap_units"] = cap
    return {
        "paths": {
            "queue_file": queue,
            "videos_dir": os.path.join(tmpdir, "videos"),
            "runs_dir": os.path.join(tmpdir, "runs"),
        },
        "publish": {"page_id": "1048148471706586"},
        "veo": veo,
    }


def _ready(entry):
    if entry["number"] == 4:
        return (True, "anza", "anza-part1", "")
    return (False, None, None, "يحتاج تجهيز مشروع")


class TestPlanBatch(unittest.TestCase):
    def test_plan_openmontage(self):
        with tempfile.TemporaryDirectory() as td:
            plan = batch.plan_batch(_cfg(td), 2, source="openmontage",
                                    ready_fn=_ready)
            self.assertEqual(plan["source"], "openmontage")
            self.assertEqual(len(plan["stories"]), 2)
            self.assertTrue(plan["stories"][0]["ready"])
            self.assertEqual(plan["stories"][0]["slug"], "anza")
            self.assertFalse(plan["stories"][1]["ready"])
            self.assertEqual(plan["expected_units_per_video"], 0)

    def test_plan_count_limit(self):
        with tempfile.TemporaryDirectory() as td:
            plan = batch.plan_batch(_cfg(td), 1, source="openmontage",
                                    ready_fn=_ready)
            self.assertEqual(len(plan["stories"]), 1)
            self.assertEqual(plan["stories"][0]["number"], 4)

    def test_plan_invalid_count(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(batch.BatchError):
                batch.plan_batch(_cfg(td), 0, source="openmontage",
                                 ready_fn=_ready)

    def test_plan_invalid_source(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(batch.BatchError):
                batch.plan_batch(_cfg(td), 1, source="tiktok",
                                 ready_fn=_ready)

    def test_plan_veo_low_balance(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(batch.BatchError) as cm:
                batch.plan_batch(_cfg(td, balance=100), 1,
                                 source="veo", ready_fn=_ready)
            self.assertIn("أقل من 120", str(cm.exception))

    def test_plan_veo_cap_refused(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(batch.BatchError) as cm:
                batch.plan_batch(_cfg(td, cap=100), 1,
                                 source="veo", ready_fn=_ready)
            self.assertIn("يتجاوز سقف", str(cm.exception))

    def test_plan_veo_cap_ok(self):
        with tempfile.TemporaryDirectory() as td:
            plan = batch.plan_batch(_cfg(td, cap=200), 1,
                                    source="veo", ready_fn=_ready)
            self.assertEqual(plan["expected_units_per_video"], 120)
            self.assertEqual(plan["total_expected_units"], 120)
            self.assertIsNotNone(plan["stories"][0]["scene_plan"])

    def test_plan_veo_balance_total_not_single(self):
        """انحدار: رصيد 150 كان يقبل دفعة قصتين (إجمالي 240)
        لأن الفحص كان على فيديو واحد (120) فقط — فتُخطط دفعة
        لا يمكن توليدها."""
        def _ready_both(entry):
            return (True, "slug-%d" % entry["number"],
                    "proj-%d" % entry["number"], "")

        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(batch.BatchError) as cm:
                batch.plan_batch(_cfg(td, balance=150), 2,
                                 source="veo", ready_fn=_ready_both)
            self.assertIn("240", str(cm.exception))
            self.assertIn("150", str(cm.exception))

    def test_plan_veo_balance_total_ok(self):
        def _ready_both(entry):
            return (True, "slug-%d" % entry["number"],
                    "proj-%d" % entry["number"], "")

        with tempfile.TemporaryDirectory() as td:
            plan = batch.plan_batch(_cfg(td, balance=240), 2,
                                    source="veo", ready_fn=_ready_both)
            self.assertEqual(plan["total_expected_units"], 240)

    def test_format_plan_shows_actual_count(self):
        """انحدار: طلب 5 قصص مع قصتين في الانتظار كان يعرض
        «خطة الدفعة — 5 قصص» مع سطرين فقط."""
        with tempfile.TemporaryDirectory() as td:
            plan = batch.plan_batch(_cfg(td), 5, source="openmontage",
                                    ready_fn=_ready)
            self.assertEqual(plan["count"], 2)
            text = batch.format_plan(plan)
            self.assertIn("2 قصص", text)
            self.assertNotIn("5 قصص", text)

    def test_format_plan(self):
        with tempfile.TemporaryDirectory() as td:
            plan = batch.plan_batch(_cfg(td), 2, source="openmontage",
                                    ready_fn=_ready)
            text = batch.format_plan(plan)
            self.assertIn("العنزة المباركة", text)
            self.assertIn("عجائب الصدقة", text)
            self.assertIn("جاهزة", text)
            self.assertIn("تُتخطى", text)


class TestExecuteBatch(unittest.TestCase):
    def _fns(self, produce_rc=0, check_passed=True):
        def produce_fn(cfg, slug, project, out_path):
            return produce_rc

        def check_fn(video):
            return {"passed": check_passed, "checks": []}

        def thumbnail_fn(video, hook, out):
            return out

        return produce_fn, check_fn, thumbnail_fn

    def test_execute_openmontage(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            plan = batch.plan_batch(cfg, 2, source="openmontage",
                                    ready_fn=_ready)
            produce_fn, check_fn, thumb_fn = self._fns()
            rc, result = batch.execute_batch(
                cfg, plan, produce_fn, check_fn, thumb_fn,
                cfg["paths"]["runs_dir"])
            self.assertEqual(rc, 0)
            self.assertEqual(result["stories"][0]["status"], "done")
            self.assertEqual(result["stories"][0]["output"],
                             plan["stories"][0]["video"])
            self.assertEqual(result["stories"][1]["status"], "skipped")
            files = os.listdir(cfg["paths"]["runs_dir"])
            self.assertTrue(any(f.startswith("batch-") for f in files))

    def test_execute_produce_fails_stops(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            plan = batch.plan_batch(cfg, 1, source="openmontage",
                                    ready_fn=_ready)
            produce_fn, check_fn, thumb_fn = self._fns(produce_rc=1)
            rc, result = batch.execute_batch(
                cfg, plan, produce_fn, check_fn, thumb_fn,
                cfg["paths"]["runs_dir"])
            self.assertEqual(rc, 1)
            self.assertEqual(result["stories"][0]["status"], "failed")

    def test_execute_veo_needs_flow(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            plan = batch.plan_batch(cfg, 1, source="veo",
                                    ready_fn=_ready)
            produce_fn, check_fn, thumb_fn = self._fns()
            rc, result = batch.execute_batch(
                cfg, plan, produce_fn, check_fn, thumb_fn,
                cfg["paths"]["runs_dir"])
            self.assertEqual(rc, 0)
            self.assertEqual(result["stories"][0]["status"],
                             "needs-flow")
            self.assertIsNotNone(
                result["stories"][0]["scene_plan"])


if __name__ == "__main__":
    unittest.main()
