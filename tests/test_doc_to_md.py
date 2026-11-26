#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات استخراج/تحويل المستندات إلى Markdown (lib.doc_to_md)
— جولة الأنماط (W6).

تعمل بـ `python3 -m unittest tests.test_doc_to_md -v` من
~/workspace/studio/. بلا شبكة وبلا ملفات: كل اختبار يمرّر صفحات
نصية محاكاة. زوج موجب/سالب لكل قاعدة تحويل، وفصل الاستخراج
عن التحويل مُختبَر صراحة (extract_blocks لا تنتج Markdown).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import doc_to_md


class TestExtractBlocks(unittest.TestCase):
    def test_text_and_heading_classified(self):
        blocks = doc_to_md.extract_blocks(["# Title\n\nBody text"])
        self.assertEqual(blocks[0]["type"], "heading")
        self.assertEqual(blocks[0]["level"], 1)
        self.assertEqual(blocks[0]["text"], "Title")
        self.assertEqual(blocks[1]["type"], "text")
        self.assertEqual(blocks[1]["page"], 1)

    def test_extract_produces_no_markdown(self):
        # فصل المراحل: الاستخراج الخام لا ينتج أي صياغة Markdown
        # (لا # ولا | ولا فواصل جدول).
        blocks = doc_to_md.extract_blocks(
            ["# Head\n\n| A | B |\n| 1 | 2 |"])
        for block in blocks:
            self.assertNotIn("|", block.get("text", ""))
            if block["type"] == "table":
                self.assertIn("rows", block)
                self.assertEqual(block["rows"][0], ["A", "B"])

    def test_empty_page_preserved_as_block(self):
        blocks = doc_to_md.extract_blocks(["Page one", "", "Page three"])
        empty = [b for b in blocks if b["type"] == "empty"]
        self.assertEqual(len(empty), 1)
        self.assertEqual(empty[0]["page"], 2)

    def test_table_rows_grouped(self):
        blocks = doc_to_md.extract_blocks(
            ["| Name | Age |\n| Ali | 30 |\n| Sara | 25 |"])
        tables = [b for b in blocks if b["type"] == "table"]
        self.assertEqual(len(tables), 1)
        self.assertEqual(len(tables[0]["rows"]), 3)

    def test_non_list_rejected(self):
        with self.assertRaises(TypeError):
            doc_to_md.extract_blocks("single string, not a list")

    def test_non_string_page_rejected(self):
        with self.assertRaises(TypeError):
            doc_to_md.extract_blocks(["ok", 42])

    def test_from_text_splits_on_form_feed(self):
        blocks = doc_to_md.extract_blocks_from_text("One\f\fThree")
        pages = {b["page"] for b in blocks}
        self.assertEqual(pages, {1, 2, 3})
        self.assertEqual(
            [b for b in blocks if b["type"] == "empty"][0]["page"], 2)


class TestBlocksToMarkdown(unittest.TestCase):
    def test_heading_and_text(self):
        blocks = doc_to_md.extract_blocks(["## Head\n\nSome text"])
        out = doc_to_md.blocks_to_markdown(blocks)
        self.assertIn("## Head", out)
        self.assertIn("Some text", out)

    def test_table_rendered(self):
        blocks = doc_to_md.extract_blocks(["| A | B |\n| 1 | 2 |"])
        out = doc_to_md.blocks_to_markdown(blocks)
        self.assertIn("| A | B |", out)
        self.assertIn("| --- | --- |", out)
        self.assertIn("| 1 | 2 |", out)

    def test_cross_page_table_merged(self):
        # جدول يعبر صفحتين يُدمج في جدول واحد بلا ترويسة ثانية.
        blocks = doc_to_md.extract_blocks([
            "| Name | Age |\n| Ali | 30 |",
            "| Name | Age |\n| Sara | 25 |",
        ])
        out = doc_to_md.blocks_to_markdown(blocks)
        self.assertEqual(out.count("| Name | Age |"), 1)
        self.assertEqual(out.count("| --- | --- |"), 1)
        self.assertIn("| Ali | 30 |", out)
        self.assertIn("| Sara | 25 |", out)

    def test_cross_page_table_different_header_not_merged_as_header(self):
        # جدولان متتاليان بترويستين مختلفتين: صفوف الثانية تُلحق
        # كصفوف بيانات (لا تُحذف لأنها ليست ترويسة مكررة).
        blocks = doc_to_md.extract_blocks([
            "| A | B |\n| 1 | 2 |",
            "| C | D |\n| 3 | 4 |",
        ])
        out = doc_to_md.blocks_to_markdown(blocks)
        self.assertIn("| C | D |", out)
        self.assertIn("| 3 | 4 |", out)

    def test_repeated_header_row_inside_table_dropped(self):
        blocks = [{"type": "table", "page": 1,
                   "rows": [["A", "B"], ["1", "2"], ["A", "B"],
                            ["3", "4"]]}]
        out = doc_to_md.blocks_to_markdown(blocks)
        self.assertEqual(out.count("| A | B |"), 1)
        self.assertIn("| 3 | 4 |", out)

    def test_tables_separated_by_text_not_merged(self):
        blocks = doc_to_md.extract_blocks([
            "| A | B |\n| 1 | 2 |\n\nMiddle\n\n| A | B |\n| 3 | 4 |",
        ])
        out = doc_to_md.blocks_to_markdown(blocks)
        self.assertEqual(out.count("| --- | --- |"), 2)
        self.assertIn("Middle", out)

    def test_empty_page_kept_with_number(self):
        blocks = doc_to_md.extract_blocks(["One", "", "Three"])
        out = doc_to_md.blocks_to_markdown(blocks)
        self.assertIn("<!-- صفحة 2 فارغة -->", out)
        self.assertIn("One", out)
        self.assertIn("Three", out)

    def test_no_empty_page_marker_when_none_empty(self):
        blocks = doc_to_md.extract_blocks(["One", "Two"])
        out = doc_to_md.blocks_to_markdown(blocks)
        self.assertNotIn("فارغة", out)

    def test_invalid_block_rejected(self):
        with self.assertRaises(ValueError):
            doc_to_md.blocks_to_markdown([{"type": "mystery", "page": 1}])
        with self.assertRaises(TypeError):
            doc_to_md.blocks_to_markdown("not a list")


class TestCompetitorSchema(unittest.TestCase):
    def _valid(self):
        return {"title": "قصة الأمانة", "date": "2026-11-25",
                "story_type": "moral", "views": 12345,
                "topic": "الأمانة"}

    def test_valid_record_accepted(self):
        result = doc_to_md.validate_competitor_post(self._valid())
        self.assertEqual(result["views"], 12345)
        self.assertEqual(result["story_type"], "moral")

    def test_valid_json_string_accepted(self):
        import json
        result = doc_to_md.validate_competitor_post(
            json.dumps(self._valid(), ensure_ascii=False))
        self.assertEqual(result["title"], "قصة الأمانة")

    def test_missing_field_rejected_not_guessed(self):
        for missing in ("title", "date", "story_type", "views", "topic"):
            record = self._valid()
            del record[missing]
            with self.assertRaises(ValueError, msg=missing):
                doc_to_md.validate_competitor_post(record)

    def test_bad_date_rejected(self):
        record = self._valid()
        record["date"] = "25/11/2026"
        with self.assertRaises(ValueError):
            doc_to_md.validate_competitor_post(record)

    def test_unknown_story_type_rejected(self):
        record = self._valid()
        record["story_type"] = "sci-fi"
        with self.assertRaises(ValueError):
            doc_to_md.validate_competitor_post(record)

    def test_negative_or_bool_views_rejected(self):
        for bad in (-1, True, "1000", 12.5):
            record = self._valid()
            record["views"] = bad
            with self.assertRaises(ValueError, msg=repr(bad)):
                doc_to_md.validate_competitor_post(record)

    def test_zero_views_allowed(self):
        record = self._valid()
        record["views"] = 0
        self.assertEqual(
            doc_to_md.validate_competitor_post(record)["views"], 0)

    def test_non_object_rejected(self):
        with self.assertRaises(ValueError):
            doc_to_md.validate_competitor_post([1, 2, 3])
        with self.assertRaises(ValueError):
            doc_to_md.validate_competitor_post("{bad json")

    def test_schema_constant_documents_required_fields(self):
        schema = doc_to_md.COMPETITOR_POST_SCHEMA
        self.assertEqual(sorted(schema["required"]),
                         ["date", "story_type", "title", "topic", "views"])


if __name__ == "__main__":
    unittest.main()
