#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات سجل التشغيلات — على مجلد runs/ مؤقت فقط."""
import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import runlog


def _run_log(story, started, steps, status=None):
    d = {"run": story + "-20261122-070000", "story": story,
         "project": story + "-part1", "started": started,
         "steps": steps}
    if status is not None:
        d["status"] = status
    return d


class TestCollectRuns(unittest.TestCase):
    def _setup(self, td):
        runs = Path(td) / "runs"
        (runs / "anza-20261122-070000").mkdir(parents=True)
        (runs / "anza-20261122-070000" / "run-log.json").write_text(
            json.dumps(_run_log("anza", "2026-11-22T07:00:00",
                                {"script": {"status": "ok"},
                                 "render": {"status": "ok"}}),
                       ensure_ascii=False), encoding="utf-8")
        (runs / "hamati-20261121-190000").mkdir(parents=True)
        (runs / "hamati-20261121-190000" / "run-log.json").write_text(
            json.dumps(_run_log("hamati", "2026-11-21T19:00:00",
                                {"script": {"status": "failed",
                                            "error": "تعذر الاتصال"}}),
                       ensure_ascii=False), encoding="utf-8")
        (runs / "analyze-20261122-080000.json").write_text(
            json.dumps({"date": "2026-11-22 08:00:00",
                        "facebook": {"caption": "نجار فقير",
                                     "views": 694},
                        "youtube": {"views": 254}},
                       ensure_ascii=False), encoding="utf-8")
        (runs / "analyze-bad.json").write_text("{not json",
                                               encoding="utf-8")
        return runs

    def test_collects_runs_and_analyses_newest_first(self):
        with tempfile.TemporaryDirectory() as td:
            runs = self._setup(td)
            entries = runlog.collect_runs(str(runs), today_only=False)
            self.assertEqual(len(entries), 3)
            self.assertEqual(entries[0]["kind"], "تحليل")
            self.assertEqual(entries[0]["status"], "ناجح")
            self.assertIn("694", entries[0]["detail"])
            self.assertIn("254", entries[0]["detail"])
            ok = [e for e in entries if e["title"] == "anza"][0]
            self.assertEqual(ok["status"], "ناجح")
            failed = [e for e in entries if e["title"] == "hamati"][0]
            self.assertEqual(failed["status"], "فشل")
            self.assertIn("script", failed["detail"])
            self.assertIn("تعذر الاتصال", failed["detail"])

    def test_today_only_filters(self):
        with tempfile.TemporaryDirectory() as td:
            runs = self._setup(td)
            entries = runlog.collect_runs(
                str(runs), today_only=True,
                today=datetime.date(2026, 11, 22))
            self.assertEqual(len(entries), 2)
            self.assertTrue(all(e["date_key"] == "2026-11-22"
                                for e in entries))

    def test_empty_runs_dir(self):
        with tempfile.TemporaryDirectory() as td:
            runs = Path(td) / "runs"
            runs.mkdir()
            self.assertEqual(runlog.collect_runs(str(runs)), [])
            self.assertIn("لا تشغيلات",
                          runlog.format_runs([]))

    def test_format_runs_arabic(self):
        with tempfile.TemporaryDirectory() as td:
            runs = self._setup(td)
            text = runlog.format_runs(
                runlog.collect_runs(str(runs), today_only=False))
            self.assertIn("إنتاج «anza» — ناجح", text)
            self.assertIn("إنتاج «hamati» — فشل", text)
            self.assertIn("تحليل", text)


if __name__ == "__main__":
    unittest.main()
