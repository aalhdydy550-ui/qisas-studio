#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات سجل تكاليف Veo — على مجلد مؤقت فقط."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import cost_ledger


class TestRecord(unittest.TestCase):
    def test_record_writes_jsonl_entry(self):
        with tempfile.TemporaryDirectory() as td:
            entry = cost_ledger.record(td, 120, "عائشة ج2", clips=6,
                                       when="2026-11-22 02:18")
            self.assertEqual(entry["units"], 120)
            self.assertEqual(entry["video"], "عائشة ج2")
            self.assertEqual(entry["clips"], 6)
            self.assertEqual(entry["date"], "2026-11-22 02:18")
            lines = cost_ledger.history(td)
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["units"], 120)

    def test_record_appends_and_history_preserves_order(self):
        with tempfile.TemporaryDirectory() as td:
            cost_ledger.record(td, 120, "أ", clips=6)
            cost_ledger.record(td, 100, "ب", clips=5)
            entries = cost_ledger.history(td)
            self.assertEqual([e["video"] for e in entries], ["أ", "ب"])
            t = cost_ledger.totals(entries)
            self.assertEqual(t, {"entries": 2, "units": 220,
                                 "clips": 11})

    def test_record_requires_video_and_positive_units(self):
        with tempfile.TemporaryDirectory() as td:
            for bad in (0, -5, "abc"):
                with self.assertRaises(ValueError):
                    cost_ledger.record(td, bad, "أ")
            with self.assertRaises(ValueError):
                cost_ledger.record(td, 120, "   ")
            with self.assertRaises(ValueError):
                cost_ledger.record(td, 120, "أ", clips=0)

    def test_history_empty_without_file(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(cost_ledger.history(td), [])
            self.assertIn("لا قيود", cost_ledger.format_history([]))

    def test_corrupt_lines_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            cost_ledger.record(td, 120, "أ")
            path = cost_ledger.ledger_path(td)
            with open(path, "a", encoding="utf-8") as f:
                f.write("not json{\n")
            cost_ledger.record(td, 100, "ب")
            entries = cost_ledger.history(td)
            self.assertEqual([e["video"] for e in entries], ["أ", "ب"])

    def test_format_history_shows_totals(self):
        with tempfile.TemporaryDirectory() as td:
            cost_ledger.record(td, 120, "أ", clips=6)
            cost_ledger.record(td, 100, "ب", clips=5)
            text = cost_ledger.format_history(cost_ledger.history(td))
            self.assertIn("220 وحدة", text)
            self.assertIn("11 مقطعًا", text)


if __name__ == "__main__":
    unittest.main()
