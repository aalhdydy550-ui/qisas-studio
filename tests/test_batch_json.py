#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات دفعات JSON ووضع no-spend (lib.batch) — الجولة v0.1.39
(أ2-2 وأ2-3).

كل الكتابة في مجلدات مؤقتة — بلا أي إنفاق Veo وبلا شبكة:
الإنتاج غير موجود أصلًا في توقيع validate_batch (فلا يمكن
استدعاؤه)، والرصيد يُقرأ من الإعداد فقط ولا يُخصم.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import batch

VALID_JSON = {
    "name": "دفعة الصباح",
    "source": "veo",
    "default_engine": "lite",
    "tasks": [
        {"title": "العنزة المباركة", "parts": 2, "clips": 6},
        {"title": "عجائب الصدقة", "parts": 1, "engine": "fast"},
    ],
}


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


def _ready(entry):
    return (True, "slug-%d" % entry["number"],
            "proj-%d" % entry["number"], "")


def _write_json(tmpdir, data, name="batch.json"):
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, ensure_ascii=False)
    return path


class TestParseJsonBatch(unittest.TestCase):
    def test_valid_dict_defaults(self):
        parsed = batch.parse_json_batch(
            {"tasks": [{"title": "قصة تجريبية"}]})
        self.assertEqual(parsed["source"], "openmontage")
        task = parsed["tasks"][0]
        self.assertEqual(task["parts"], 1)
        self.assertEqual(task["engine"], "fast")
        self.assertEqual(task["clips"], 6)
        self.assertEqual(task["total_clips"], 6)
        self.assertEqual(task["note"], "")

    def test_bare_list_accepted(self):
        parsed = batch.parse_json_batch(
            [{"title": "قصة تجريبية", "engine": "lite"}])
        self.assertEqual(parsed["tasks"][0]["engine"], "lite")
        self.assertEqual(parsed["tasks"][0]["total_clips"], 6)

    def test_story_alias_and_notes_alias(self):
        parsed = batch.parse_json_batch(
            {"tasks": [{"story": "قصة تجريبية", "notes": "ملاحظة"}]})
        self.assertEqual(parsed["tasks"][0]["title"], "قصة تجريبية")
        self.assertEqual(parsed["tasks"][0]["note"], "ملاحظة")

    def test_missing_title_rejected_arabic(self):
        with self.assertRaises(batch.BatchError) as cm:
            batch.parse_json_batch({"tasks": [{"parts": 1}]})
        self.assertIn("بلا عنوان", str(cm.exception))
        self.assertIn("title", str(cm.exception))

    def test_empty_title_rejected(self):
        with self.assertRaises(batch.BatchError) as cm:
            batch.parse_json_batch({"tasks": [{"title": "   "}]})
        self.assertIn("بلا عنوان", str(cm.exception))

    def test_invalid_engine_rejected_arabic(self):
        with self.assertRaises(batch.BatchError) as cm:
            batch.parse_json_batch(
                {"tasks": [{"title": "قصة", "engine": "ultra"}]})
        self.assertIn("محرك", str(cm.exception))
        self.assertIn("ultra", str(cm.exception))

    def test_invalid_source_rejected(self):
        with self.assertRaises(batch.BatchError) as cm:
            batch.parse_json_batch(
                {"source": "tiktok",
                 "tasks": [{"title": "قصة"}]})
        self.assertIn("المصدر غير صالح", str(cm.exception))

    def test_parts_out_of_range_rejected(self):
        for parts in (0, 3):
            with self.assertRaises(batch.BatchError) as cm:
                batch.parse_json_batch(
                    {"tasks": [{"title": "قصة", "parts": parts}]})
            self.assertIn("parts", str(cm.exception))

    def test_clips_out_of_range_rejected(self):
        for clips in (0, 13):
            with self.assertRaises(batch.BatchError) as cm:
                batch.parse_json_batch(
                    {"tasks": [{"title": "قصة", "clips": clips}]})
            self.assertIn("clips", str(cm.exception))

    def test_unknown_task_field_rejected(self):
        with self.assertRaises(batch.BatchError) as cm:
            batch.parse_json_batch(
                {"tasks": [{"title": "قصة", "gflow": True}]})
        self.assertIn("غير معروف", str(cm.exception))

    def test_unknown_top_field_rejected(self):
        with self.assertRaises(batch.BatchError) as cm:
            batch.parse_json_batch(
                {"tasks": [{"title": "قصة"}], "client": "x"})
        self.assertIn("غير معروف", str(cm.exception))

    def test_duplicate_titles_rejected(self):
        with self.assertRaises(batch.BatchError) as cm:
            batch.parse_json_batch(
                {"tasks": [{"title": "قصة"}, {"title": "قصة"}]})
        self.assertIn("مكرر", str(cm.exception))

    def test_empty_tasks_rejected(self):
        with self.assertRaises(batch.BatchError) as cm:
            batch.parse_json_batch({"tasks": []})
        self.assertIn("بلا مهام", str(cm.exception))

    def test_non_dict_task_rejected(self):
        with self.assertRaises(batch.BatchError) as cm:
            batch.parse_json_batch({"tasks": ["قصة"]})
        self.assertIn("قاموسًا", str(cm.exception))

    def test_non_object_rejected(self):
        with self.assertRaises(batch.BatchError) as cm:
            batch.parse_json_batch("قصة")
        self.assertIn("قاموسًا", str(cm.exception))


class TestLoadJsonBatch(unittest.TestCase):
    def test_load_valid_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, VALID_JSON)
            parsed = batch.load_json_batch(path)
            self.assertEqual(len(parsed["tasks"]), 2)
            self.assertEqual(parsed["name"], "دفعة الصباح")

    def test_load_missing_file(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(batch.BatchError) as cm:
                batch.load_json_batch(os.path.join(td, "nope.json"))
            self.assertIn("غير موجود", str(cm.exception))

    def test_load_malformed_json_rejected_arabic(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, "{ليس json صالحًا")
            with self.assertRaises(batch.BatchError) as cm:
                batch.load_json_batch(path)
            self.assertIn("ليس JSON صالحًا", str(cm.exception))


class TestPlanBatchFromJson(unittest.TestCase):
    def test_plan_fast_vs_lite_units(self):
        """6 مقاطع = 120 وحدة Fast / 60 وحدة Lite (تسعيرة ab)."""
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            plan = batch.plan_batch_from_json(
                cfg, data={"source": "veo", "tasks": [
                    {"title": "قصة سريعة", "engine": "fast"},
                    {"title": "قصة خفيفة", "engine": "lite"},
                ]}, ready_fn=_ready)
            self.assertEqual(
                plan["stories"][0]["estimated_units"], 120)
            self.assertEqual(
                plan["stories"][1]["estimated_units"], 60)
            self.assertEqual(plan["total_expected_units"], 180)
            self.assertTrue(plan["from_json"])
            self.assertTrue(all(s["from_json"]
                                for s in plan["stories"]))

    def test_plan_two_parts_doubles_clips(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            plan = batch.plan_batch_from_json(
                cfg, data={"source": "veo", "tasks": [
                    {"title": "قصة جزأين", "parts": 2,
                     "engine": "lite"},
                ]}, ready_fn=_ready)
            self.assertEqual(plan["stories"][0]["total_clips"], 12)
            self.assertEqual(
                plan["stories"][0]["estimated_units"], 120)

    def test_plan_from_file_and_source_override(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            path = _write_json(td, VALID_JSON)
            plan = batch.plan_batch_from_json(
                cfg, json_path=path, source="openmontage",
                ready_fn=_ready)
            self.assertEqual(plan["source"], "openmontage")
            self.assertEqual(plan["total_expected_units"], 0)
            self.assertEqual(plan["json_name"], "دفعة الصباح")
            # رغم التجاوز: المحرك والأجزاء من الملف محفوظان.
            self.assertEqual(plan["stories"][0]["parts"], 2)
            self.assertEqual(plan["stories"][0]["engine"], "lite")

    def test_plan_veo_total_exceeds_balance_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td, balance=150)
            with self.assertRaises(batch.BatchError) as cm:
                batch.plan_batch_from_json(
                    cfg, data={"source": "veo", "tasks": [
                        {"title": "أولى", "engine": "fast"},
                        {"title": "ثانية", "engine": "fast"},
                    ]}, ready_fn=_ready)
            self.assertIn("240", str(cm.exception))
            self.assertIn("150", str(cm.exception))

    def test_plan_veo_cap_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td, cap=100)
            with self.assertRaises(batch.BatchError) as cm:
                batch.plan_batch_from_json(
                    cfg, data={"source": "veo", "tasks": [
                        {"title": "قصة", "engine": "fast"},
                    ]}, ready_fn=_ready)
            self.assertIn("يتجاوز سقف", str(cm.exception))

    def test_plan_needs_neither_path_nor_data(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(batch.BatchError):
                batch.plan_batch_from_json(_cfg(td))

    def test_format_plan_shows_json_details(self):
        with tempfile.TemporaryDirectory() as td:
            plan = batch.plan_batch_from_json(
                _cfg(td), data={"source": "veo", "tasks": [
                    {"title": "قصة", "engine": "lite"},
                ]}, ready_fn=_ready)
            text = batch.format_plan(plan)
            self.assertIn("Lite", text)
            self.assertIn("60 وحدة", text)


class TestValidateBatchNoSpend(unittest.TestCase):
    def _probe_ok(self, video):
        return {"duration": 50.0, "width": 720, "height": 1280,
                "has_audio": True}

    def test_no_spend_never_calls_produce_and_deducts_nothing(self):
        """validate_batch بلا produce_fn في توقيعها أصلًا؛ وأي
        دالة إنتاج تُمرَّر خطأً لا تُستدعى — والرصيد لا يتغير."""
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            plan = batch.plan_batch_from_json(
                cfg, data={"source": "veo", "tasks": [
                    {"title": "قصة", "engine": "fast"},
                ]}, ready_fn=_ready)
            produce_fn = mock.Mock(return_value=0)
            report = batch.validate_batch(cfg, plan)
            produce_fn.assert_not_called()
            self.assertEqual(cfg["veo"]["balance_units"], 680)
            # فيديو Veo غير جاهز: مانع needs-flow، والتقرير
            # يسمّيه أول خطأ مانع.
            self.assertFalse(report["ok"])
            self.assertEqual(report["total_expected_units"], 120)
            self.assertEqual(report["balance_units"], 680)
            self.assertTrue(report["balance_sufficient"])
            self.assertIn("Flow", report["first_blocking_error"])
            self.assertIn("no-spend", batch.format_no_spend_report(
                report))

    def test_no_spend_openmontage_ok(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            plan = batch.plan_batch_from_json(
                cfg, data={"tasks": [
                    {"title": "قصة", "engine": "lite"},
                ]}, ready_fn=_ready)
            report = batch.validate_batch(cfg, plan)
            self.assertTrue(report["ok"])
            self.assertEqual(report["total_expected_units"], 0)
            self.assertIsNone(report["first_blocking_error"])
            text = batch.format_no_spend_report(report)
            self.assertIn("0 وحدة", text)
            self.assertIn("جاهزة", text)

    def test_no_spend_reports_reused_from_cache(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            runs_dir = cfg["paths"]["runs_dir"]

            def produce_fn(c, slug, project, out_path):
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "wb") as fh:
                    fh.write(b"fake-video")
                return 0

            def check_fn(video):
                return {"passed": True, "checks": []}

            def thumb_fn(video, hook, out):
                return out

            plan = batch.plan_batch_from_json(
                cfg, data={"tasks": [{"title": "قصة"}]},
                ready_fn=_ready)
            batch.execute_batch(cfg, plan, produce_fn, check_fn,
                                thumb_fn, runs_dir,
                                probe_fn=self._probe_ok)
            plan2 = batch.plan_batch_from_json(
                cfg, data={"tasks": [{"title": "قصة"}]},
                ready_fn=_ready)
            report = batch.validate_batch(
                cfg, plan2, runs_dir=runs_dir,
                probe_fn=self._probe_ok)
            self.assertTrue(report["ok"])
            self.assertEqual(report["reused_count"], 1)
            self.assertEqual(report["reused_titles"], ["قصة"])
            self.assertEqual(report["tasks"][0]["status"], "reused")

    def test_no_spend_veo_reuse_needs_no_balance(self):
        """مهمة Veo معاد استخدامها من الكاش: 0 وحدة مطلوبة —
        فالرصيد الناقص لا يمنعها."""
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td, balance=680)
            runs_dir = cfg["paths"]["runs_dir"]
            videos_dir = cfg["paths"]["videos_dir"]
            os.makedirs(videos_dir, exist_ok=True)
            with open(os.path.join(videos_dir, "slug-1-batch.mp4"),
                      "wb") as fh:
                fh.write(b"fake-video")

            def produce_fn(c, slug, project, out_path):
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "wb") as fh:
                    fh.write(b"fake-video")
                return 0

            def check_fn(video):
                return {"passed": True, "checks": []}

            def thumb_fn(video, hook, out):
                return out

            # الإنتاج الأول (Veo Lite) يملأ الكاش ببصمة المصدر
            # نفسه؛ ثم ينفد الرصيد بعد التخطيط.
            plan = batch.plan_batch_from_json(
                cfg, data={"source": "veo", "tasks": [
                    {"title": "قصة", "engine": "lite"},
                ]}, ready_fn=_ready)
            batch.execute_batch(cfg, plan, produce_fn, check_fn,
                                thumb_fn, runs_dir,
                                probe_fn=self._probe_ok)
            plan2 = batch.plan_batch_from_json(
                cfg, data={"source": "veo", "tasks": [
                    {"title": "قصة", "engine": "lite"},
                ]}, ready_fn=_ready)
            cfg["veo"]["balance_units"] = 0
            report = batch.validate_batch(
                cfg, plan2, runs_dir=runs_dir,
                probe_fn=self._probe_ok)
            self.assertEqual(report["reused_count"], 1)
            self.assertEqual(report["total_expected_units"], 0)
            self.assertTrue(report["ok"])

    def test_no_spend_low_balance_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td, balance=100)
            videos_dir = cfg["paths"]["videos_dir"]
            os.makedirs(videos_dir, exist_ok=True)
            with open(os.path.join(videos_dir, "slug-1-batch.mp4"),
                      "wb") as fh:
                fh.write(b"fake-video")
            plan = batch.plan_batch_from_json(
                cfg, data={"tasks": [{"title": "قصة"}]},
                ready_fn=_ready)
            plan["source"] = "veo"
            plan["stories"][0]["engine"] = "fast"
            plan["stories"][0]["total_clips"] = 6
            report = batch.validate_batch(cfg, plan)
            self.assertFalse(report["ok"])
            self.assertFalse(report["balance_sufficient"])
            self.assertIn("يتجاوز الرصيد",
                          report["first_blocking_error"])

    def test_no_spend_skipped_story_reported(self):
        def _not_ready(entry):
            return (False, None, None, "يحتاج تجهيز مشروع")

        with tempfile.TemporaryDirectory() as td:
            plan = batch.plan_batch_from_json(
                _cfg(td), data={"tasks": [{"title": "قصة"}]},
                ready_fn=_not_ready)
            report = batch.validate_batch(_cfg(td), plan)
            self.assertFalse(report["ok"])
            self.assertEqual(report["tasks"][0]["status"], "skipped")
            self.assertIn("يحتاج تجهيز مشروع",
                          report["first_blocking_error"])


if __name__ == "__main__":
    unittest.main()
