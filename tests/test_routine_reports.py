#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات تقارير الروتينات — جولة v0.1.63 (بند 20).

دوال نقية؛ بلا ملفات وبلا شبكة.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import routine_reports
from lib.routine_reports import RoutineReportError


class TestNothingNew(unittest.TestCase):
    def test_nothing_new_constant_is_quiet_only(self):
        self.assertEqual(routine_reports.NOTHING_NEW, {"quiet": True})

    def test_nothing_new_parses_to_quiet(self):
        report = routine_reports.parse_routine_report(
            {"quiet": True})
        self.assertTrue(report["quiet"])
        self.assertEqual(report["items"], [])
        self.assertIsNone(report["checked_at"])

    def test_nothing_new_carries_checked_at(self):
        report = routine_reports.nothing_new(
            checked_at="2026-11-27T11:00:00+02:00")
        self.assertEqual(report,
                         {"quiet": True,
                          "checked_at": "2026-11-27T11:00:00+02:00"})
        parsed = routine_reports.parse_routine_report(report)
        self.assertTrue(parsed["quiet"])

    def test_quiet_is_never_published(self):
        self.assertFalse(
            routine_reports.should_publish({"quiet": True}))
        self.assertFalse(
            routine_reports.should_publish(
                routine_reports.nothing_new()))
        self.assertTrue(
            routine_reports.is_quiet({"quiet": True}))
        self.assertTrue(
            routine_reports.is_quiet(
                routine_reports.format_nothing_new()))

    def test_json_string_quiet_parses(self):
        report = routine_reports.parse_routine_report(
            '{"quiet": true}')
        self.assertTrue(report["quiet"])


class TestPublishable(unittest.TestCase):
    def test_items_report_is_publishable(self):
        report = routine_reports.parse_routine_report(
            {"quiet": False,
             "items": [{"title": "بريد جديد"}]})
        self.assertFalse(report["quiet"])
        self.assertEqual(len(report["items"]), 1)
        self.assertTrue(routine_reports.should_publish(
            {"quiet": False, "items": ["بريد جديد"]}))

    def test_items_without_quiet_flag_is_publishable(self):
        report = routine_reports.parse_routine_report(
            {"items": ["عنصر"]})
        self.assertFalse(report["quiet"])
        self.assertTrue(routine_reports.should_publish(
            {"items": ["عنصر"]}))


class TestMalformed(unittest.TestCase):
    def test_none_answer_fails(self):
        with self.assertRaises(RoutineReportError):
            routine_reports.parse_routine_report(None)

    def test_empty_string_fails(self):
        with self.assertRaises(RoutineReportError):
            routine_reports.parse_routine_report("   ")

    def test_non_json_string_fails(self):
        with self.assertRaises(RoutineReportError):
            routine_reports.parse_routine_report("ليس JSON")

    def test_non_object_fails(self):
        with self.assertRaises(RoutineReportError):
            routine_reports.parse_routine_report(["quiet"])
        with self.assertRaises(RoutineReportError):
            routine_reports.parse_routine_report(42)

    def test_unknown_field_fails(self):
        with self.assertRaises(RoutineReportError):
            routine_reports.parse_routine_report(
                {"quiet": True, "publish": True})

    def test_quiet_with_items_is_contradiction(self):
        with self.assertRaises(RoutineReportError):
            routine_reports.parse_routine_report(
                {"quiet": True, "items": ["عنصر"]})

    def test_empty_answer_is_neither_quiet_nor_report(self):
        with self.assertRaises(RoutineReportError):
            routine_reports.parse_routine_report({})
        with self.assertRaises(RoutineReportError):
            routine_reports.parse_routine_report({"items": []})
        with self.assertRaises(RoutineReportError):
            routine_reports.parse_routine_report({"quiet": False})

    def test_wrong_types_fail(self):
        with self.assertRaises(RoutineReportError):
            routine_reports.parse_routine_report({"quiet": "yes"})
        with self.assertRaises(RoutineReportError):
            routine_reports.parse_routine_report({"items": "عنصر"})
        with self.assertRaises(RoutineReportError):
            routine_reports.parse_routine_report(
                {"items": [123]})
        with self.assertRaises(RoutineReportError):
            routine_reports.parse_routine_report(
                {"quiet": True, "checked_at": 123})

    def test_malformed_never_publishes_and_is_not_quiet(self):
        self.assertFalse(routine_reports.should_publish(None))
        self.assertFalse(routine_reports.should_publish(
            {"quiet": True, "items": ["x"]}))
        self.assertFalse(routine_reports.is_quiet(None))
        self.assertFalse(routine_reports.is_quiet(
            {"quiet": True, "items": ["x"]}))

    def test_validate_returns_flag_not_exception(self):
        ok, error = routine_reports.validate_routine_report(
            {"quiet": True})
        self.assertTrue(ok)
        self.assertIsNone(error)
        ok, error = routine_reports.validate_routine_report(None)
        self.assertFalse(ok)
        self.assertTrue(error)


if __name__ == "__main__":
    unittest.main()
