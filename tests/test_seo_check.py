#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات أمر فحص SEO قبل النشر (lib.seo_check).

تعمل بـ `python3 -m unittest tests.test_seo_check -v`
من `~/workspace/studio`. بلا شبكة وبلا LLM إطلاقًا.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import publish_meta
from lib import seo_check

GOOD_TITLE = "النجار الأمين | قصة حقيقية"
GOOD_DESC = ("قصة حقيقية عن نجار فقير وجد ذهبًا وأعاده لصاحبه.\n"
             "والنهاية أغرب مما تتخيل.")
GOOD_TAGS = ["قصص وعبر", "قصص واقعية", "قصص مؤثرة", "حكايات",
             "النجار الأمين"]
GOOD_STORY = "نجار فقير وجد ذهبًا في باب وأعاده لصاحبه"


def _good(**overrides):
    kwargs = {"title": GOOD_TITLE, "description": GOOD_DESC,
              "tags": list(GOOD_TAGS), "story_text": GOOD_STORY}
    kwargs.update(overrides)
    return seo_check.check_seo(**kwargs)


class TestNormalization(unittest.TestCase):
    def test_alef_variants(self):
        self.assertEqual(seo_check.normalize_arabic("أإآ"), "ااا")

    def test_teh_marbuta_and_alef_maksura(self):
        self.assertEqual(seo_check.normalize_arabic("قصةً حقيقى"),
                         "قصه حقيقي")

    def test_diacritics_and_tatweel_removed(self):
        self.assertEqual(seo_check.normalize_arabic("قُصَّة"),
                         "قصه")
        self.assertEqual(seo_check.normalize_arabic("قــصة"), "قصه")

    def test_words_split(self):
        self.assertEqual(seo_check.words("عائشة الأرملة | الجزء 1"),
                         ["عائشه", "الارمله", "الجزء", "1"])


class TestQueryDerivation(unittest.TestCase):
    def test_three_queries_always(self):
        report = _good()
        self.assertEqual(len(report["queries"]), 3)
        for result in report["queries"]:
            self.assertTrue(result["query"])
            self.assertTrue(result["words"])

    def test_queries_deterministic(self):
        first = _good()["queries"]
        second = _good()["queries"]
        self.assertEqual(first, second)

    def test_first_query_is_title_core(self):
        report = _good()
        self.assertEqual(report["queries"][0]["query"],
                         "النجار الامين")

    def test_second_query_is_real_story_phrasing(self):
        report = _good()
        self.assertEqual(report["queries"][1]["query"],
                         "قصه حقيقيه النجار")

    def test_third_query_uses_story_only_words(self):
        report = _good()
        self.assertEqual(report["queries"][2]["query"],
                         "قصه نجار فقير")

    def test_no_story_text_still_three_queries(self):
        report = _good(story_text=None)
        self.assertEqual(len(report["queries"]), 3)
        self.assertEqual(report["queries"][2]["query"],
                         "قصه النجار الامين")

    def test_one_word_title_falls_back(self):
        report = _good(title="الأمانة", story_text=None,
                       tags=["الأمانة"])
        self.assertEqual(len(report["queries"]), 3)
        self.assertEqual(len(set(r["query"]
                                 for r in report["queries"])), 3)


class TestQueryTest(unittest.TestCase):
    def test_query_in_title_and_description(self):
        report = _good()
        first = report["queries"][0]
        self.assertTrue(first["in_title"])
        self.assertFalse(first["in_description_first_two_lines"])
        self.assertTrue(first["passed"])

    def test_query_missing_everywhere_fails(self):
        # استعلام مشتق من قصة لا يذكرها العنوان ولا الوصف.
        report = _good(story_text="بحار تاه في عاصفة بعيدة")
        third = report["queries"][2]
        self.assertEqual(third["query"], "قصه بحار تاه")
        self.assertFalse(third["passed"])
        self.assertIn("بحار", third["missing_everywhere"])
        self.assertFalse(report["ok"])
        self.assertTrue(any("قصه بحار تاه" in issue
                            for issue in report["issues"]))

    def test_query_in_description_only_is_note_not_failure(self):
        # عنوان بلا «قصة حقيقية»: q2 «قصه حقيقيه النجار» —
        # «قصه/حقيقيه» في الوصف لا العنوان.
        report = _good(title="النجار الأمين")
        second = report["queries"][1]
        self.assertEqual(second["query"], "قصه حقيقيه النجار")
        self.assertFalse(second["in_title"])
        self.assertFalse(second["in_description_first_two_lines"])
        self.assertTrue(second["passed"])
        self.assertTrue(report["ok"])
        self.assertTrue(any("المشكلة في العنوان" in note
                            for note in report["notes"]))

    def test_normalized_matching(self):
        # «الأرملة» في العنوان تطابق «الارمله» في الاستعلام.
        report = _good(title="عائشة الأرملة | قصة حقيقية",
                       description="قصة حقيقية عن أرملة صابرة.\n"
                                   "والنهاية أغرب مما تتخيل.",
                       tags=["عائشة الأرملة"],
                       story_text="أرملة صابرة ظلمتها حماتها")
        self.assertTrue(report["queries"][0]["in_title"])


class TestDescriptionChecks(unittest.TestCase):
    def test_good_description_passes(self):
        report = _good()
        desc = report["description"]
        self.assertTrue(desc["first_two_lines_non_empty"])
        self.assertTrue(desc["carries_promise"])
        self.assertFalse(desc["has_gate"])
        self.assertTrue(desc["length_ok"])
        self.assertEqual(desc["first_two_lines"],
                         GOOD_DESC.split("\n"))

    def test_empty_description_fails(self):
        report = _good(description="")
        self.assertFalse(report["description"]
                         ["first_two_lines_non_empty"])
        self.assertFalse(report["description"]["carries_promise"])
        self.assertFalse(report["ok"])
        self.assertTrue(any("فارغان" in issue
                            for issue in report["issues"]))

    def test_snippet_without_promise_fails(self):
        report = _good(description="شاهد الفيديو.\nتابعونا.")
        self.assertFalse(report["description"]["carries_promise"])
        self.assertFalse(report["ok"])

    def test_promise_word_counts(self):
        # بلا كلمة من العنوان/القصة — لكن فيها كلمة وعد.
        report = _good(description="والنهاية أغرب مما تتخيل.\n"
                                   "شاهد حتى الآخر.",
                       story_text=None)
        self.assertTrue(report["description"]["carries_promise"])

    def test_follow_gate_flagged(self):
        report = _good(description=GOOD_DESC + "\nلو عايز الجزء "
                       "الثاني اعمل متابعة.")
        desc = report["description"]
        self.assertTrue(desc["has_gate"])
        self.assertEqual(len(desc["gate_issues"]), 1)
        self.assertEqual(desc["gate_issues"][0]["category"],
                         "next_part")
        self.assertFalse(report["ok"])
        self.assertTrue(any("بوابة" in issue
                            for issue in report["issues"]))

    def test_approved_story_line_not_a_gate(self):
        from lib import caption_check
        report = _good(description=GOOD_DESC + "\n"
                       + caption_check.APPROVED_STORY_LINE)
        self.assertFalse(report["description"]["has_gate"])

    def test_description_over_400_fails(self):
        long_desc = "قصة حقيقية عن أمانة. " + "كلمة " * 200
        self.assertGreater(len(long_desc),
                           publish_meta.MAX_DESCRIPTION_CHARS)
        report = _good(description=long_desc)
        self.assertFalse(report["description"]["length_ok"])
        self.assertFalse(report["ok"])

    def test_description_exactly_400_passes(self):
        desc = ("قصة حقيقية عن أمانة ردّها صاحبها. "
                + "x" * (400 - len("قصة حقيقية عن أمانة ردّها صاحبها. ")))
        self.assertEqual(len(desc), 400)
        report = _good(description=desc)
        self.assertTrue(report["description"]["length_ok"])


class TestTagsChecks(unittest.TestCase):
    def test_good_tags_pass(self):
        report = _good()
        tags = report["tags"]
        self.assertTrue(tags["count_ok"])
        self.assertTrue(tags["total_chars_ok"])
        self.assertFalse(tags["has_duplicates"])
        self.assertFalse(tags["has_irrelevant"])

    def test_more_than_15_tags_fails(self):
        tags = ["قصص وعبر"] + ["وسم %d" % i for i in range(15)]
        report = _good(tags=tags)
        self.assertEqual(report["tags"]["count"], 16)
        self.assertFalse(report["tags"]["count_ok"])
        self.assertFalse(report["ok"])

    def test_exactly_15_tags_passes(self):
        tags = ["قصص وعبر"] + ["النجار %d" % i for i in range(14)]
        report = _good(tags=tags)
        self.assertTrue(report["tags"]["count_ok"])

    def test_total_over_500_fails(self):
        tags = ["قصص وعبر", "النجار الأمين " + "طويل " * 100]
        self.assertGreater(len(",".join(tags)),
                           publish_meta.YT_TAGS_LIMIT)
        report = _good(tags=tags)
        self.assertFalse(report["tags"]["total_chars_ok"])
        self.assertFalse(report["ok"])

    def test_normalized_duplicate_flagged(self):
        report = _good(tags=["الأرملة", "الارمله", "قصص وعبر"])
        self.assertEqual(report["tags"]["duplicates"], ["الارمله"])
        self.assertFalse(report["ok"])

    def test_irrelevant_tag_flagged(self):
        report = _good(tags=["قصص وعبر", "كرة القدم", "النجار"])
        self.assertEqual(report["tags"]["irrelevant"], ["كرة القدم"])
        self.assertFalse(report["ok"])

    def test_fixed_generic_tags_not_irrelevant(self):
        report = _good(tags=list(publish_meta.FIXED_TAGS))
        self.assertFalse(report["tags"]["has_irrelevant"])

    def test_tags_as_comma_string_accepted(self):
        report = _good(tags="قصص وعبر, النجار الأمين")
        self.assertEqual(report["tags"]["count"], 2)
        self.assertTrue(report["ok"])

    def test_empty_tag_strings_ignored(self):
        report = _good(tags=["قصص وعبر", "", "  "])
        self.assertEqual(report["tags"]["count"], 1)


class TestTitleCheck(unittest.TestCase):
    def test_title_over_100_fails(self):
        title = "قصة " + "طويلة جدًا " * 20
        self.assertGreater(len(title), publish_meta.YT_TITLE_LIMIT)
        report = _good(title=title)
        self.assertFalse(report["title_ok"])
        self.assertFalse(report["ok"])

    def test_title_exactly_100_passes(self):
        title = "ق" * 100
        report = _good(title=title)
        self.assertTrue(report["title_ok"])


class TestInvalidInput(unittest.TestCase):
    def test_empty_title(self):
        with self.assertRaises(ValueError) as ctx:
            _good(title="   ")
        self.assertIn("العنوان فارغ", str(ctx.exception))

    def test_non_string_title(self):
        with self.assertRaises(ValueError) as ctx:
            _good(title=None)
        self.assertIn("العنوان", str(ctx.exception))

    def test_non_string_description(self):
        with self.assertRaises(ValueError) as ctx:
            _good(description=None)
        self.assertIn("الوصف", str(ctx.exception))

    def test_tags_not_list_or_string(self):
        with self.assertRaises(ValueError) as ctx:
            _good(tags=123)
        self.assertIn("الوسوم", str(ctx.exception))

    def test_non_string_tag_item(self):
        with self.assertRaises(ValueError) as ctx:
            _good(tags=["قصص وعبر", 7])
        self.assertIn("وسم", str(ctx.exception))

    def test_non_string_story_text(self):
        with self.assertRaises(ValueError) as ctx:
            _good(story_text=42)
        self.assertIn("القصة", str(ctx.exception))


class TestRealStudioExample(unittest.TestCase):
    def test_aisha_widow_local_fallback_passes(self):
        # المثال الحقيقي من الاستوديو: البديل المحلي من
        # publish_meta لقصة «عائشة الأرملة» جزء 1 من 2.
        meta = publish_meta.generate_publish_meta(
            {"title": "عائشة الأرملة",
             "text": "أرملة ظلمتها حماتها"},
            part=1, parts=2)
        self.assertEqual(meta["source"], "local")
        self.assertEqual(meta["title"], "عائشة الأرملة | الجزء 1 من 2")
        report = seo_check.check_seo(
            meta["title"], meta["description"], meta["tags"],
            story_text="أرملة ظلمتها حماتها")
        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual(report["title"], meta["title"])
        self.assertEqual(report["queries"][0]["query"],
                         "عائشه الارمله")
        self.assertTrue(all(r["passed"] for r in report["queries"]))
        self.assertTrue(report["description"]["carries_promise"])
        self.assertFalse(report["description"]["has_gate"])
        self.assertEqual(report["tags"]["count"], 5)


class TestReportFormats(unittest.TestCase):
    def test_format_report_arabic(self):
        text = seo_check.format_report(_good())
        self.assertIn("تقرير فحص SEO", text)
        self.assertIn("النجار الأمين", text)
        self.assertIn("سليم", text)
        self.assertIn("«النجار الامين»", text)

    def test_format_report_shows_issues(self):
        text = seo_check.format_report(_good(description=""))
        self.assertIn("فارغان", text)
        self.assertIn("فيه ملاحظات", text)

    def test_to_json_dict_round_trips(self):
        report = _good()
        data = seo_check.to_json_dict(report)
        self.assertEqual(data, report)
        json.dumps(data, ensure_ascii=False)

    def test_check_is_deterministic(self):
        self.assertEqual(_good(), _good())


if __name__ == "__main__":
    unittest.main()
