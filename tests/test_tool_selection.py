#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات اختيار الأدوات Allow/Exclude (lib.tool_selection) —
جولة v0.1.63، بند 15 (ع6).

تعمل بـ `env -u PYTHONNOUSERSITE python3 -m unittest
tests.test_tool_selection`. خالصة بلا قرص وبلا شبكة.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import tool_selection
from lib.tool_selection import ToolSelectionError


AVAILABLE = [
    "native:read",
    "native:write",
    "native:publish",
    "mcp:mail:read_notes",
    "mcp:mail:send",
]


class TestAllowEmpty(unittest.TestCase):
    def test_empty_allow_denies_everything(self):
        for tool in AVAILABLE:
            self.assertFalse(
                tool_selection.allowed(tool, [], [], available=AVAILABLE)
            )
        self.assertEqual(
            tool_selection.select_tools([], [], AVAILABLE), []
        )

    def test_none_allow_is_empty(self):
        self.assertFalse(
            tool_selection.allowed("native:read", None, None, available=AVAILABLE)
        )


class TestDenyWins(unittest.TestCase):
    def test_deny_beats_allow_exact(self):
        self.assertFalse(
            tool_selection.allowed(
                "native:read",
                ["native:read"],
                ["native:read"],
                available=AVAILABLE,
            )
        )

    def test_deny_wildcard_beats_allow_exact(self):
        self.assertFalse(
            tool_selection.allowed(
                "native:read",
                ["native:*"],
                ["native:*"],
                available=AVAILABLE,
            )
        )
        self.assertTrue(
            tool_selection.allowed(
                "mcp:mail:read_notes",
                ["mcp:mail:*"],
                ["native:*"],
                available=AVAILABLE,
            )
        )


class TestSelectors(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(
            tool_selection.allowed(
                "mcp:mail:read_notes",
                ["mcp:mail:read_notes"],
                [],
                available=AVAILABLE,
            )
        )
        self.assertFalse(
            tool_selection.allowed(
                "mcp:mail:send",
                ["mcp:mail:read_notes"],
                [],
                available=AVAILABLE,
            )
        )

    def test_full_segment_wildcard(self):
        self.assertTrue(
            tool_selection.matches_selector("native:*", "native:read")
        )
        self.assertTrue(
            tool_selection.matches_selector("mcp:mail:*", "mcp:mail:send")
        )
        self.assertFalse(
            tool_selection.matches_selector("mcp:mail:*", "native:read")
        )
        self.assertFalse(
            tool_selection.matches_selector("native:*", "native")
        )

    def test_partial_wildcard_is_invalid(self):
        self.assertFalse(
            tool_selection.is_valid_selector("native:read*")
        )
        self.assertFalse(tool_selection.is_valid_selector("native:*read"))
        self.assertFalse(tool_selection.is_valid_selector("*"))
        with self.assertRaises(ToolSelectionError):
            tool_selection.validate_selectors(["native:read*"], "allow")
        with self.assertRaises(ToolSelectionError):
            tool_selection.allowed(
                "native:read", ["native:read*"], [], available=AVAILABLE
            )

    def test_case_sensitive_names(self):
        self.assertFalse(
            tool_selection.allowed(
                "native:read", ["Native:Read"], [], available=AVAILABLE
            )
        )

    def test_invalid_selector_matches_nothing(self):
        self.assertFalse(
            tool_selection.matches_selector("native:read*", "native:read")
        )


class TestUnavailableName(unittest.TestCase):
    def test_correct_but_unavailable_selects_nothing(self):
        # اسم صحيح غير متاح لا يعود إلى كل الأدوات.
        self.assertFalse(
            tool_selection.allowed(
                "native:secret", ["native:secret"], [], available=AVAILABLE
            )
        )
        self.assertEqual(
            tool_selection.select_tools(
                ["native:secret"], [], AVAILABLE
            ),
            [],
        )

    def test_select_tools_returns_only_available_allowed(self):
        chosen = tool_selection.select_tools(
            ["native:*", "mcp:mail:read_notes"], ["native:publish"], AVAILABLE
        )
        self.assertEqual(
            chosen,
            ["mcp:mail:read_notes", "native:read", "native:write"],
        )


class TestLimits(unittest.TestCase):
    def test_256_selectors_max(self):
        many = ["native:tool%d" % i for i in range(256)]
        self.assertEqual(len(tool_selection.validate_selectors(many, "allow")), 256)
        with self.assertRaises(ToolSelectionError):
            tool_selection.validate_selectors(many + ["native:extra"], "allow")

    def test_1024_chars_per_selector(self):
        long_ok = "native:" + "a" * 1017  # 1024 حرفًا بالضبط
        self.assertEqual(len(long_ok), 1024)
        self.assertEqual(
            tool_selection.validate_selectors([long_ok], "allow"), [long_ok]
        )
        with self.assertRaises(ToolSelectionError):
            tool_selection.validate_selectors(
                ["native:" + "a" * 1018], "allow"
            )

    def test_non_list_and_non_string_rejected(self):
        with self.assertRaises(ToolSelectionError):
            tool_selection.validate_selectors("native:read", "allow")
        with self.assertRaises(ToolSelectionError):
            tool_selection.validate_selectors([42], "allow")


class TestFailedSaveGrantsNothing(unittest.TestCase):
    def test_invalid_selection_raises_instead_of_granting(self):
        # اختيار مشوّه يوقف الدور بخطأ إعداد — لا يمنح أدوات أبدًا.
        with self.assertRaises(ToolSelectionError):
            tool_selection.select_tools(
                ["native:read*"], [], AVAILABLE
            )
        with self.assertRaises(ToolSelectionError):
            tool_selection.select_tools(
                ["native:read"], ["mcp:**"], AVAILABLE
            )


if __name__ == "__main__":
    unittest.main()
