#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات منظّف HTML ← Markdown (lib.html_to_md) — جولة الأنماط (W6).

تعمل بـ `python3 -m unittest tests.test_html_to_md -v` من
~/workspace/studio/. بلا شبكة: كل اختبار يمرّر HTML محاكى.
زوج موجب/سالب لكل قاعدة تحويل.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import html_to_md


class TestDropTags(unittest.TestCase):
    def test_script_dropped(self):
        out = html_to_md.html_to_markdown(
            "<p>Keep</p><script>var x = 1; alert('gone');</script>")
        self.assertIn("Keep", out)
        self.assertNotIn("alert", out)
        self.assertNotIn("var x", out)

    def test_script_content_not_leaked_via_nesting(self):
        out = html_to_md.html_to_markdown(
            "<div><script><p>hidden</p></script></div><p>shown</p>")
        self.assertNotIn("hidden", out)
        self.assertIn("shown", out)

    def test_style_dropped(self):
        out = html_to_md.html_to_markdown(
            "<style>p { color: red; }</style><p>Text</p>")
        self.assertIn("Text", out)
        self.assertNotIn("color", out)

    def test_nav_header_footer_dropped(self):
        html = ("<header>Site name</header><nav>Home About</nav>"
                "<p>Body</p><footer>Copyright 2026</footer>")
        out = html_to_md.html_to_markdown(html)
        self.assertIn("Body", out)
        self.assertNotIn("Site name", out)
        self.assertNotIn("Home About", out)
        self.assertNotIn("Copyright", out)

    def test_nested_drop_tags(self):
        out = html_to_md.html_to_markdown(
            "<nav><ul><li>Menu</li></ul></nav><p>Real</p>")
        self.assertIn("Real", out)
        self.assertNotIn("Menu", out)

    def test_plain_text_kept(self):
        # سالب الإسقاط: نص عادي بلا وسوم مسقَطة يبقى كاملًا.
        out = html_to_md.html_to_markdown("<p>Just text here</p>")
        self.assertEqual(out.strip(), "Just text here")


class TestHeadingsAndParagraphs(unittest.TestCase):
    def test_h1_h2_h3(self):
        html = "<h1>Title</h1><h2>Section</h2><h3>Sub</h3><p>Body</p>"
        out = html_to_md.html_to_markdown(html)
        self.assertIn("# Title", out)
        self.assertIn("## Section", out)
        self.assertIn("### Sub", out)
        self.assertIn("Body", out)

    def test_heading_level_capped_at_3(self):
        # h4 فأعمق تُحوَّل كـ h3 كحد أقصى (النطاق h1–h3).
        out = html_to_md.html_to_markdown("<h4>Deep</h4>")
        self.assertIn("### Deep", out)
        self.assertNotIn("#### Deep", out)

    def test_paragraphs_separated(self):
        out = html_to_md.html_to_markdown("<p>One</p><p>Two</p>")
        self.assertIn("One\n\nTwo", out)

    def test_empty_input(self):
        self.assertEqual(html_to_md.html_to_markdown(""), "")
        self.assertEqual(html_to_md.html_to_markdown("   "), "")


class TestLinksAndLists(unittest.TestCase):
    def test_link_to_markdown(self):
        out = html_to_md.html_to_markdown(
            '<p>See <a href="https://example.com/docs">the docs</a>.</p>')
        self.assertIn("[the docs](https://example.com/docs)", out)

    def test_relative_link_resolved_with_base_url(self):
        out = html_to_md.html_to_markdown(
            '<p><a href="/guide">Guide</a></p>',
            base_url="https://example.com/docs/page")
        self.assertIn("[Guide](https://example.com/guide)", out)

    def test_link_without_href_keeps_text(self):
        out = html_to_md.html_to_markdown("<p><a>plain</a></p>")
        self.assertIn("plain", out)
        self.assertNotIn("[plain]", out)

    def test_unordered_list(self):
        out = html_to_md.html_to_markdown(
            "<ul><li>First</li><li>Second</li></ul>")
        self.assertIn("- First", out)
        self.assertIn("- Second", out)

    def test_ordered_list(self):
        out = html_to_md.html_to_markdown(
            "<ol><li>One</li><li>Two</li></ol>")
        self.assertIn("1. One", out)
        self.assertIn("1. Two", out)

    def test_nested_list_indented(self):
        out = html_to_md.html_to_markdown(
            "<ul><li>Outer<ul><li>Inner</li></ul></li></ul>")
        self.assertIn("- Outer", out)
        self.assertIn("  - Inner", out)


class TestInlineAndCap(unittest.TestCase):
    def test_strong_em_code(self):
        out = html_to_md.html_to_markdown(
            "<p><strong>bold</strong> and <em>italic</em> and "
            "<code>code</code></p>")
        self.assertIn("**bold**", out)
        self.assertIn("*italic*", out)
        self.assertIn("`code`", out)

    def test_max_chars_truncates_with_marker(self):
        long_html = "<p>" + "word " * 5000 + "</p>"
        out = html_to_md.html_to_markdown(long_html, max_chars=100)
        self.assertLessEqual(len(out), 200)
        self.assertIn("مُقتطع", out)

    def test_max_chars_not_reached_keeps_full(self):
        out = html_to_md.html_to_markdown("<p>Short</p>", max_chars=1000)
        self.assertIn("Short", out)
        self.assertNotIn("مُقتطع", out)

    def test_non_string_rejected(self):
        with self.assertRaises(TypeError):
            html_to_md.html_to_markdown(None)

    def test_bad_max_chars_rejected(self):
        with self.assertRaises(ValueError):
            html_to_md.html_to_markdown("<p>x</p>", max_chars=0)

    def test_estimate_tokens(self):
        self.assertEqual(html_to_md.estimate_tokens(""), 0)
        self.assertEqual(html_to_md.estimate_tokens("abcd"), 1)
        self.assertEqual(html_to_md.estimate_tokens("a" * 400), 100)


if __name__ == "__main__":
    unittest.main()
