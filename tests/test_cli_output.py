#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات عقد CLI الموحّد (جولة v0.1.63، بند 2 — عقدا ع1 وع2).

بلا شبكة وبلا ملفات خارج الشجرة: المخرجات تُلتقط من
StringIO، والأسرار المستخدمة قيم وهمية بصيغ صحيحة.
"""
import contextlib
import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import cli_output
from lib.cli_output import Output


class TestExitCodes(unittest.TestCase):
    def test_codes_match_contract_o1(self):
        self.assertEqual(cli_output.EXIT_OK, 0)
        self.assertEqual(cli_output.EXIT_FAILURE, 1)
        self.assertEqual(cli_output.EXIT_BAD_CLI, 2)
        self.assertEqual(cli_output.EXIT_NEEDS_HUMAN, 3)
        self.assertEqual(cli_output.EXIT_LOGIN_TIMEOUT, 4)
        self.assertEqual(cli_output.EXIT_FORBIDDEN, 5)
        self.assertEqual(cli_output.EXIT_BUSY, 6)
        self.assertEqual(cli_output.EXIT_NOT_FOUND, 7)
        self.assertEqual(cli_output.EXIT_DATA_ERROR, 8)
        self.assertEqual(cli_output.EXIT_INTERRUPTED, 130)

    def test_error_returns_each_code(self):
        for code in (0, 1, 2, 3, 4, 5, 6, 7, 8, 130):
            out = Output(json_mode=False)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(out.error("x", code=code), code)


class TestShortIdOneLine(unittest.TestCase):
    def test_short_id_truncates_long(self):
        self.assertEqual(cli_output.short_id("abcdefghij123"),
                         "abcdefgh…")
        self.assertEqual(cli_output.short_id("abcdefgh"), "abcdefgh")
        self.assertEqual(cli_output.short_id("abc"), "abc")
        self.assertEqual(cli_output.short_id(""), "")

    def test_one_line_flattens(self):
        self.assertEqual(cli_output.one_line("a\nb  \n  c"), "a b c")
        self.assertEqual(cli_output.one_line("  x  "), "x")
        self.assertEqual(cli_output.one_line(""), "")

    def test_one_line_cuts_at_120_by_default(self):
        long_text = "x" * 200
        cut = cli_output.one_line(long_text)
        self.assertEqual(len(cut), 121)
        self.assertTrue(cut.endswith("…"))
        self.assertEqual(cli_output.one_line("y" * 120), "y" * 120)
        self.assertEqual(cli_output.one_line("z" * 130, limit=10),
                         "z" * 10 + "…")


class TestRedactDeep(unittest.TestCase):
    def test_redacts_provider_keys(self):
        secret = "AIza" + "A" * 35
        value = cli_output.redact_deep({"key": secret})
        self.assertNotIn(secret, json.dumps(value))
        self.assertIn("[REDACTED]", value["key"])

    def test_redacts_groq_openrouter_bearer_assignment(self):
        obj = {"a": "gsk_" + "B" * 48,
               "b": "sk-or-v1-" + "c" * 64,
               "c": "Bearer " + "a" * 22,
               "d": "api_key=" + "AbCdEfGh12345678"}
        redacted = cli_output.redact_deep(obj)
        dumped = json.dumps(redacted)
        for key in ("a", "b", "c", "d"):
            self.assertNotIn(obj[key], dumped, key)
        self.assertIn("[REDACTED]", dumped)

    def test_masks_email_and_phone_and_long_id(self):
        obj = {"mail": "user@example.com",
               "phone": "01512345678",
               "page": "صفحة 1048148471706586"}
        redacted = cli_output.redact_deep(obj)
        self.assertNotIn("user@example.com",
                         json.dumps(redacted))
        self.assertNotIn("01512345678", json.dumps(redacted))
        self.assertNotIn("1048148471706586", json.dumps(redacted))

    def test_recursive_and_non_mutating(self):
        original = {"n": [1, "sk-" + "D" * 48, ("x", None)],
                    "keep": 42, "flag": True, "none": None}
        redacted = cli_output.redact_deep(original)
        # الأصل لم يُعدَّل
        self.assertEqual(original["n"][1], "sk-" + "D" * 48)
        self.assertIsInstance(redacted["n"][2], tuple)
        self.assertEqual(redacted["keep"], 42)
        self.assertIs(redacted["flag"], True)
        self.assertIsNone(redacted["none"])
        self.assertNotIn("D" * 48, json.dumps(redacted))

    def test_plain_text_passes_through(self):
        self.assertEqual(cli_output.redact_deep("نص عادي"), "نص عادي")
        self.assertEqual(cli_output.redact_deep(7), 7)


class TestOutputJsonMode(unittest.TestCase):
    def test_result_is_single_json_document(self):
        out = Output(json_mode=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out.result({"job": "abc123", "count": 3},
                       human_lines=["مهمة abc123: 3"])
        text = buf.getvalue()
        self.assertEqual(text.count("\n"), 1)
        doc = json.loads(text)
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["job"], "abc123")
        self.assertEqual(doc["count"], 3)

    def test_result_redacts_secret_inside_json(self):
        secret = "ghp_" + "e" * 36
        out = Output(json_mode=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out.result({"token": secret})
        self.assertNotIn(secret, buf.getvalue())
        self.assertIn("[REDACTED]", buf.getvalue())

    def test_error_json_shape_and_code(self):
        out = Output(json_mode=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = out.error("تعذر الوصول", hint="أعد المحاولة",
                             code=4)
        self.assertEqual(code, 4)
        doc = json.loads(buf.getvalue())
        self.assertEqual(doc, {"ok": False, "error": "تعذر الوصول",
                               "hint": "أعد المحاولة", "exitCode": 4})

    def test_error_json_even_without_hint(self):
        out = Output(json_mode=True)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out.error("فشل", code=1)
        doc = json.loads(buf.getvalue())
        self.assertEqual(doc["hint"], "")
        self.assertEqual(doc["exitCode"], 1)

    def test_progress_goes_to_stderr_as_json_line(self):
        out = Output(json_mode=True)
        err = io.StringIO()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), \
                contextlib.redirect_stderr(err):
            out.progress({"step": "render", "pct": 50})
        self.assertEqual(stdout.getvalue(), "")
        doc = json.loads(err.getvalue())
        self.assertEqual(doc, {"step": "render", "pct": 50})

    def test_progress_redacts_secrets(self):
        secret = "AIza" + "F" * 35
        out = Output(json_mode=True)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            out.progress({"note": secret})
        self.assertNotIn(secret, err.getvalue())


class TestOutputHumanMode(unittest.TestCase):
    def test_result_prints_human_lines(self):
        out = Output(json_mode=False)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out.result({"job": "x"}, human_lines=["سطر أول", "سطر ثانٍ"])
        self.assertEqual(buf.getvalue(), "سطر أول\nسطر ثانٍ\n")

    def test_error_prints_to_stderr_with_hint(self):
        out = Output(json_mode=False)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = out.error("تعذر الوصول", hint="أعد المحاولة",
                             code=5)
        self.assertEqual(code, 5)
        self.assertIn("error: تعذر الوصول", err.getvalue())
        self.assertIn("hint: أعد المحاولة", err.getvalue())

    def test_error_without_hint_prints_no_hint_line(self):
        out = Output(json_mode=False)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            out.error("فشل")
        self.assertNotIn("hint:", err.getvalue())

    def test_quiet_drops_progress_only(self):
        out = Output(json_mode=False, quiet=True)
        err = io.StringIO()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), \
                contextlib.redirect_stderr(err):
            out.progress({"step": "x"})
            out.result({"a": 1}, human_lines=["نتيجة"])
        self.assertEqual(err.getvalue(), "")
        self.assertIn("نتيجة", stdout.getvalue())

    def test_non_quiet_progress_is_json_on_stderr(self):
        out = Output(json_mode=False, quiet=False)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            out.progress("جارٍ العمل")
        doc = json.loads(err.getvalue())
        self.assertEqual(doc["message"], "جارٍ العمل")


if __name__ == "__main__":
    unittest.main()
