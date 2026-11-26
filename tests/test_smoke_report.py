#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات مولّد تقرير الدخان + عقد APIs — جولة الأنماط (W3).

بلا أي اتصال شبكي وبلا مفاتيح: تختبر صفحة HTML
(الهروب + الصفوف + العدّادات) وكاتب JUnit اليدوي
(XML صالح + failure/skipped) وشكل العقد (كل مدخل
كامل، واختيار دخان واحد لكل مزود) وCLI المولّد.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import api_contract
from lib import smoke_report

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sample_results():
    return [
        smoke_report.result("gemini", "gemini-3.1-flash-lite",
                            "POST /v1beta/models/...:generateContent",
                            "ok", 1234, ""),
        smoke_report.result("instagram", "-",
                            "GET /v21.0/me?fields=id",
                            "failed", 234, "HTTP 401: توكن منتهٍ"),
        smoke_report.result("tiktok", "-",
                            "GET /v2/user/info/",
                            "skipped", None,
                            "لا توكن TikTok محفوظ"),
    ]


class TestRenderHtml(unittest.TestCase):
    def test_rows_status_elapsed_error(self):
        page = smoke_report.render_html(_sample_results())
        self.assertIn("gemini", page)
        self.assertIn("1234", page)
        self.assertIn("ناجح", page)
        self.assertIn("فاشل", page)
        self.assertIn("متخطَّى", page)
        self.assertIn("HTTP 401", page)
        self.assertIn("لا توكن TikTok محفوظ", page)
        # العدّادات: الإجمالي 3 (ناجح 1، فاشل 1، متخطَّى 1)
        self.assertIn("الإجمالي: 3", page)

    def test_escapes_html_in_error(self):
        bad = smoke_report.result("x", "y", "GET /z", "failed", 1,
                                  "<script>alert(1)</script>")
        page = smoke_report.render_html([bad])
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_empty_results_renders(self):
        page = smoke_report.render_html([])
        self.assertIn("الإجمالي: 0", page)
        self.assertIn("لا نتائج", page)

    def test_unknown_status_rejected(self):
        with self.assertRaises(ValueError):
            smoke_report.result("x", "y", "GET /z", "weird", 1, "")


class TestRenderJunit(unittest.TestCase):
    def test_valid_xml_counts(self):
        text = smoke_report.render_junit(_sample_results())
        root = ET.fromstring(text)
        suite = root.find("testsuite")
        self.assertIsNotNone(suite)
        self.assertEqual(suite.get("tests"), "3")
        self.assertEqual(suite.get("failures"), "1")
        self.assertEqual(suite.get("skipped"), "1")
        cases = suite.findall("testcase")
        self.assertEqual(len(cases), 3)
        self.assertIsNotNone(cases[1].find("failure"))
        self.assertIsNotNone(cases[2].find("skipped"))
        self.assertIsNone(cases[0].find("failure"))
        self.assertIsNone(cases[0].find("skipped"))

    def test_escapes_special_chars(self):
        bad = smoke_report.result("x&y", "m", "GET /z?a=1&b=2",
                                  "failed", 5, 'خطأ "مقتبس" & <وسم>')
        text = smoke_report.render_junit([bad])
        root = ET.fromstring(text)  # يرفع إن كان XML تالفًا
        case = root.find("testsuite").find("testcase")
        self.assertIn("x&y", case.get("name"))

    def test_empty_results_valid(self):
        root = ET.fromstring(smoke_report.render_junit([]))
        self.assertEqual(root.find("testsuite").get("tests"), "0")


class TestSkippedResults(unittest.TestCase):
    def test_one_skipped_per_smoke_entry(self):
        results = smoke_report.skipped_results("سبب اختبار")
        picks = api_contract.smoke_entries()
        self.assertEqual(len(results), len(picks))
        self.assertGreater(len(results), 0)
        for item, entry in zip(results, picks):
            self.assertEqual(item["status"], "skipped")
            self.assertEqual(item["provider"], entry["provider"])
            self.assertEqual(item["model"], entry["model"])
            self.assertEqual(item["error"], "سبب اختبار")
            self.assertIsNone(item["elapsed_ms"])

    def test_summarize(self):
        counts = smoke_report.summarize(_sample_results())
        self.assertEqual(counts, {"ok": 1, "failed": 1,
                                  "skipped": 1, "total": 3})


class TestWriteReportAndCli(unittest.TestCase):
    def test_write_report_files_match_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            html_path = os.path.join(tmp, "r.html")
            junit_path = os.path.join(tmp, "r.xml")
            written = smoke_report.write_report(
                _sample_results(), html_path, junit_path)
            self.assertEqual(written, [html_path, junit_path])
            with open(html_path, encoding="utf-8") as fh:
                self.assertEqual(
                    fh.read(),
                    smoke_report.render_html(_sample_results()))
            with open(junit_path, encoding="utf-8") as fh:
                ET.fromstring(fh.read())

    def test_cli_writes_skipped_report_without_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env.pop("STUDIO_LIVE_SMOKE", None)
            html_path = os.path.join(tmp, "smoke-report.html")
            junit_path = os.path.join(tmp, "smoke-report-junit.xml")
            proc = subprocess.run(
                [sys.executable, "-m", "lib.smoke_report",
                 "--html", html_path, "--junit", junit_path],
                cwd=STUDIO_DIR, capture_output=True, text=True,
                env=env, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            with open(html_path, encoding="utf-8") as fh:
                page = fh.read()
            self.assertIn("متخطَّى", page)
            with open(junit_path, encoding="utf-8") as fh:
                root = ET.fromstring(fh.read())
            suite = root.find("testsuite")
            self.assertEqual(suite.get("tests"),
                             str(len(api_contract.smoke_entries())))
            self.assertEqual(suite.get("skipped"), suite.get("tests"))

    def test_cli_loads_results_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = os.path.join(tmp, "results.json")
            with open(data_path, "w", encoding="utf-8") as fh:
                json.dump(_sample_results(), fh, ensure_ascii=False)
            html_path = os.path.join(tmp, "out.html")
            junit_path = os.path.join(tmp, "out.xml")
            proc = subprocess.run(
                [sys.executable, "-m", "lib.smoke_report",
                 "--html", html_path, "--junit", junit_path,
                 "--results-json", data_path],
                cwd=STUDIO_DIR, capture_output=True, text=True,
                timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            with open(html_path, encoding="utf-8") as fh:
                self.assertIn("ناجح", fh.read())
            with open(junit_path, encoding="utf-8") as fh:
                suite = ET.fromstring(fh.read()).find("testsuite")
            self.assertEqual(suite.get("failures"), "1")

    def test_collect_results_missing_json_falls_back_to_skipped(self):
        results = smoke_report.collect_results(
            "/tmp/no-such-smoke-results-xyz.json")
        self.assertTrue(all(r["status"] == "skipped"
                            for r in results))
        self.assertEqual(len(results),
                         len(api_contract.smoke_entries()))


class TestApiContractShape(unittest.TestCase):
    def test_every_entry_complete(self):
        self.assertGreater(len(api_contract.API_CONTRACT), 0)
        for entry in api_contract.API_CONTRACT:
            for key in api_contract.REQUIRED_KEYS:
                self.assertIn(key, entry, entry)
            self.assertIn(entry["method"], ("GET", "POST"))
            self.assertEqual(entry["expected_status"], 200)
            self.assertTrue(entry["path"].startswith("/"))
            self.assertIsInstance(entry["required_fields"], list)
            self.assertGreater(len(entry["required_fields"]), 0)
            self.assertIsInstance(entry["time_budget_ms"], int)
            self.assertGreater(entry["time_budget_ms"], 0)
            self.assertIsInstance(entry["smoke"], bool)

    def test_one_smoke_pick_per_provider(self):
        picks = api_contract.smoke_entries()
        providers = [p["provider"] for p in picks]
        self.assertEqual(len(providers), len(set(providers)),
                         "اختيار دخان مكرر لمزود: %s" % providers)
        self.assertEqual(set(providers),
                         set(api_contract.providers()))
        # كل مزود له مدخل smoke واحد على الأقل في العقد
        for provider in api_contract.providers():
            flagged = [e for e in
                       api_contract.entries_for_provider(provider)
                       if e["smoke"]]
            self.assertEqual(len(flagged), 1, provider)

    def test_has_nested_field(self):
        data = {"data": {"user": {"open_id": "x"}}}
        self.assertTrue(api_contract.has_nested_field(
            data, "data.user.open_id"))
        self.assertFalse(api_contract.has_nested_field(
            data, "data.user.missing"))
        self.assertFalse(api_contract.has_nested_field(
            data, "data.user.open_id.deep"))
        self.assertFalse(api_contract.has_nested_field(
            {"data": None}, "data.user"))

    def test_no_publish_or_write_entry(self):
        """العقد قراءة فقط: لا مدخل نشر/كتابة إطلاقًا."""
        text = json.dumps(api_contract.API_CONTRACT,
                          ensure_ascii=False).lower()
        for banned in ("media_publish", "/v2/post/publish/",
                       "upload_url", "file_upload"):
            self.assertNotIn(banned, text, banned)


if __name__ == "__main__":
    unittest.main()
