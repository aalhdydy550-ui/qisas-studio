#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات تقرير الموثوقية — جولة v0.1.60.

بيانات اصطناعية فقط وtmp — بلا قراءة أي ملف خارج شجرة
المستودع وبلا شبكة. تغطي: حساب المعدلات، التصنيف حسب
النوع والفئة، رياضيات الزمن الأحمر (فترتان منها واحدة
مفتوحة لنهاية النافذة)، MTTR/MTBF، السجل التالف، المدخل
الفارغ، وترتيب زمني غير مرتب في المدخل.
"""
import json
import os
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import reliability_report
from lib.reliability_report import build_reliability_report


def _run(run_id, kind, started_at, status, failure_class=None,
         duration_s=60):
    record = {"id": run_id, "kind": kind, "started_at": started_at,
              "duration_s": duration_s, "status": status}
    if failure_class is not None:
        record["failure_class"] = failure_class
    return record


def _iso(text):
    """حلّل ISO-8601 (مع Z) إلى datetime واعٍ للمقارنة."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


class TestRatesAndClassification(unittest.TestCase):
    def test_rates_by_kind_and_by_class(self):
        runs = [
            _run("t1", "test-suite", "2026-11-01T00:00:00Z", "ok"),
            _run("t2", "test-suite", "2026-11-01T01:00:00Z",
                 "failed", "code"),
            _run("t3", "test-suite", "2026-11-01T02:00:00Z", "ok"),
            _run("c1", "cron", "2026-11-01T03:00:00Z",
                 "failed", "environment"),
            _run("c2", "cron", "2026-11-01T04:00:00Z", "failed"),
            _run("p1", "publish", "2026-11-01T05:00:00Z", "ok"),
        ]
        report = build_reliability_report(runs)
        self.assertEqual(report["total_runs"], 6)
        self.assertEqual(report["ok"], 3)
        self.assertEqual(report["failed"], 3)
        self.assertEqual(report["failure_rate"], 0.5)
        self.assertEqual(report["window"]["days"], 30)
        self.assertEqual(_iso(report["window"]["end"]),
                         _iso("2026-11-01T05:00:00Z"))
        self.assertEqual(_iso(report["window"]["start"]),
                         _iso("2026-10-02T05:00:00Z"))

        by_kind = report["by_kind"]
        self.assertEqual(by_kind["test-suite"],
                         {"total": 3, "ok": 2, "failed": 1,
                          "failure_rate": 0.3333})
        self.assertEqual(by_kind["cron"],
                         {"total": 2, "ok": 0, "failed": 2,
                          "failure_rate": 1.0})
        self.assertEqual(by_kind["publish"],
                         {"total": 1, "ok": 1, "failed": 0,
                          "failure_rate": 0.0})
        self.assertEqual(by_kind["build"],
                         {"total": 0, "ok": 0, "failed": 0,
                          "failure_rate": 0.0})

        self.assertEqual(report["by_class"],
                         {"environment": 1, "code": 1,
                          "external": 0, "unknown": 0,
                          "unclassified": 1})
        self.assertEqual(report["skipped"], 0)

    def test_failure_class_unknown_counts_as_unknown(self):
        runs = [
            _run("a", "build", "2026-11-01T00:00:00Z",
                 "failed", "unknown"),
            _run("b", "build", "2026-11-01T01:00:00Z",
                 "failed", "external"),
            _run("c", "build", "2026-11-01T02:00:00Z",
                 "failed", "weird-class"),
        ]
        report = build_reliability_report(runs)
        self.assertEqual(report["by_class"]["unknown"], 1)
        self.assertEqual(report["by_class"]["external"], 1)
        # فئة غير معروفة تُعامل كبلا تصنيف
        self.assertEqual(report["by_class"]["unclassified"], 1)

    def test_ok_run_failure_class_ignored(self):
        runs = [
            _run("a", "cron", "2026-11-01T00:00:00Z",
                 "ok", "code"),
        ]
        report = build_reliability_report(runs)
        self.assertEqual(report["by_class"],
                         {"environment": 0, "code": 0,
                          "external": 0, "unknown": 0,
                          "unclassified": 0})


class TestRedTimeMttrMtbf(unittest.TestCase):
    def test_two_red_periods_one_open_to_window_end(self):
        runs = [
            _run("b0", "build", "2026-11-01T10:00:00Z", "ok"),
            _run("b1", "build", "2026-11-01T11:00:00Z",
                 "failed", "code"),
            _run("b2", "build", "2026-11-01T11:30:00Z",
                 "failed", "code"),
            _run("b3", "build", "2026-11-01T13:00:00Z", "ok"),
            _run("b4", "build", "2026-11-01T14:00:00Z", "ok"),
            _run("b5", "build", "2026-11-01T15:00:00Z",
                 "failed", "environment"),
            # تشغيل لاحق من نوع آخر يحدد نهاية النافذة 16:00
            _run("c1", "cron", "2026-11-01T16:00:00Z", "ok"),
        ]
        report = build_reliability_report(runs)
        # الفترة 1: 11:00 → 13:00 = 7200ث (فشلان متتاليان
        # فترة واحدة)؛ الفترة 2 مفتوحة: 15:00 → 16:00 = 3600ث
        self.assertEqual(report["red_time"],
                         {"total_red_s": 10800.0,
                          "longest_red_s": 7200.0,
                          "red_periods": 2})
        # MTTR من الفترة المغلقة وحدها
        self.assertEqual(report["mttr_s"], 7200.0)
        # MTBF: فشل 11:00 و11:30 و15:00 → فجوتان 1800 و12600
        self.assertEqual(report["mtbf_s"], 7200.0)
        self.assertTrue(any("مفتوحة" in note
                            for note in report["notes"]))

    def test_red_period_per_kind_not_mixed(self):
        # فشل cron لا يفتح فترة حمراء لـbuild والعكس
        runs = [
            _run("c1", "cron", "2026-11-01T00:00:00Z",
                 "failed", "code"),
            _run("b1", "build", "2026-11-01T01:00:00Z", "ok"),
            _run("c2", "cron", "2026-11-01T02:00:00Z", "ok"),
        ]
        report = build_reliability_report(runs)
        # فترة cron وحدها: 00:00 → 02:00 = 7200ث
        self.assertEqual(report["red_time"]["total_red_s"], 7200.0)
        self.assertEqual(report["red_time"]["red_periods"], 1)
        self.assertEqual(report["mttr_s"], 7200.0)

    def test_no_failures_null_mtbf_mttr_zero_red(self):
        runs = [
            _run("a", "cron", "2026-11-01T00:00:00Z", "ok"),
            _run("b", "cron", "2026-11-01T01:00:00Z", "ok"),
        ]
        report = build_reliability_report(runs)
        self.assertIsNone(report["mtbf_s"])
        self.assertIsNone(report["mttr_s"])
        self.assertEqual(report["red_time"],
                         {"total_red_s": 0.0, "longest_red_s": 0.0,
                          "red_periods": 0})
        self.assertEqual(report["failure_rate"], 0.0)

    def test_single_failure_no_mtbf_no_mttr(self):
        runs = [
            _run("a", "cron", "2026-11-01T00:00:00Z",
                 "failed", "code"),
            _run("b", "cron", "2026-11-01T02:00:00Z", "ok"),
        ]
        report = build_reliability_report(runs)
        self.assertIsNone(report["mtbf_s"])
        # فترة واحدة مغلقة: الاسترداد بعد ساعتين
        self.assertEqual(report["mttr_s"], 7200.0)
        self.assertEqual(report["red_time"]["red_periods"], 1)


class TestCorruptAndEmpty(unittest.TestCase):
    def test_corrupt_records_skipped_never_raises(self):
        runs = [
            _run("good", "cron", "2026-11-01T00:00:00Z", "ok"),
            {"kind": "cron", "started_at": "2026-11-01T01:00:00Z",
             "status": "ok"},  # بلا id
            {"id": "", "kind": "cron",
             "started_at": "2026-11-01T01:00:00Z",
             "status": "ok"},  # id فارغ
            {"id": "bad-time", "kind": "cron",
             "started_at": "not-a-date", "status": "ok"},
            {"id": "no-time", "kind": "cron", "status": "ok"},
            {"id": "bad-status", "kind": "cron",
             "started_at": "2026-11-01T01:00:00Z",
             "status": "weird"},
            "not-a-dict",
            None,
        ]
        report = build_reliability_report(runs)
        self.assertEqual(report["skipped"], 7)
        self.assertEqual(report["total_runs"], 1)
        self.assertEqual(report["ok"], 1)
        self.assertEqual(report["failed"], 0)
        self.assertTrue(report["notes"])

    def test_empty_input_zero_report(self):
        report = build_reliability_report([])
        self.assertEqual(report["total_runs"], 0)
        self.assertEqual(report["ok"], 0)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["failure_rate"], 0.0)
        self.assertIsNone(report["mtbf_s"])
        self.assertIsNone(report["mttr_s"])
        self.assertEqual(report["skipped"], 0)
        self.assertEqual(report["red_time"],
                         {"total_red_s": 0.0, "longest_red_s": 0.0,
                          "red_periods": 0})
        self.assertEqual(report["window"],
                         {"days": 30, "start": None, "end": None})
        for kind in ("test-suite", "cron", "publish", "build"):
            self.assertEqual(report["by_kind"][kind],
                             {"total": 0, "ok": 0, "failed": 0,
                              "failure_rate": 0.0})
        self.assertEqual(report["by_class"],
                         {"environment": 0, "code": 0,
                          "external": 0, "unknown": 0,
                          "unclassified": 0})
        self.assertTrue(report["notes"])

    def test_custom_window_days(self):
        runs = [
            _run("a", "cron", "2026-11-10T12:00:00Z", "ok"),
        ]
        report = build_reliability_report(runs, window_days=7)
        self.assertEqual(report["window"]["days"], 7)
        self.assertEqual(_iso(report["window"]["start"]),
                         _iso("2026-11-03T12:00:00Z"))


class TestUnsortedInputAndShape(unittest.TestCase):
    def test_unsorted_input_same_report(self):
        ordered = [
            _run("b0", "build", "2026-11-01T10:00:00Z", "ok"),
            _run("b1", "build", "2026-11-01T11:00:00Z",
                 "failed", "code"),
            _run("b2", "build", "2026-11-01T11:30:00Z",
                 "failed", "code"),
            _run("b3", "build", "2026-11-01T13:00:00Z", "ok"),
            _run("b5", "build", "2026-11-01T15:00:00Z",
                 "failed", "environment"),
            _run("c1", "cron", "2026-11-01T16:00:00Z", "ok"),
        ]
        shuffled = [ordered[4], ordered[0], ordered[5],
                    ordered[2], ordered[1], ordered[3]]
        self.assertEqual(build_reliability_report(shuffled),
                         build_reliability_report(ordered))

    def test_json_keys_ascii_and_serializable(self):
        runs = [
            _run("a", "cron", "2026-11-01T00:00:00Z",
                 "failed", "code"),
            _run("b", "cron", "2026-11-01T01:00:00Z", "ok"),
        ]
        report = build_reliability_report(runs)
        text = json.dumps(report, ensure_ascii=False)
        parsed = json.loads(text)
        self.assertEqual(parsed, report)

        def _check_keys(obj):
            if isinstance(obj, dict):
                for key in obj:
                    self.assertTrue(key.isascii(), key)
                    _check_keys(obj[key])
            elif isinstance(obj, list):
                for item in obj:
                    _check_keys(item)

        _check_keys(report)

    def test_unknown_kind_grouped_and_noted(self):
        runs = [
            _run("a", "smoke", "2026-11-01T00:00:00Z", "ok"),
        ]
        report = build_reliability_report(runs)
        self.assertEqual(report["by_kind"]["unknown"]["total"], 1)
        self.assertEqual(report["total_runs"], 1)
        self.assertTrue(any("غير معروف" in note
                            for note in report["notes"]))

    def test_naive_datetime_treated_as_utc(self):
        runs = [
            _run("a", "cron", "2026-11-01T00:00:00", "ok"),
            _run("b", "cron", "2026-11-01T01:00:00Z", "ok"),
        ]
        report = build_reliability_report(runs)
        self.assertEqual(report["total_runs"], 2)
        self.assertEqual(_iso(report["window"]["end"]),
                         _iso("2026-11-01T01:00:00Z"))


if __name__ == "__main__":
    unittest.main()
