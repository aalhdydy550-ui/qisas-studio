#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات مولّد الكلمات المفتاحية العربية — جولة v0.1.61 (W3).

كل البيانات هنا تركيبية لأغراض الاختبار فقط، ما عدا قوالب
مجال القصص الموثّقة في ``lib/keyword_generate.py``.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import keyword_generate
from lib.keyword_generate import (
    PREFIXES,
    SOURCE_CORPUS,
    SOURCE_EXPANSION,
    SOURCE_LONG_TAIL,
    SOURCE_PREFIX,
    SOURCE_SUFFIX,
    VOLUME_UNMEASURED,
    format_report,
    generate_keywords,
    load_corpus_json,
    normalize_keyword,
    to_json,
)


def _words(result):
    """قائمة صيغ العرض من نتيجة المولّد."""
    return [entry["keyword"] for entry in result["keywords"]]


class TestHappyPathNoCorpus(unittest.TestCase):
    """مسار سعيد بلا corpus: القوالب الخمسة عشر فقط."""

    def test_no_corpus_default_limit(self):
        """بذرة «الصدقة» بلا corpus: 15 مرشحًا كلها «غير مقاس»."""
        result = generate_keywords("الصدقة")
        self.assertEqual(result["seed"], "الصدقة")
        self.assertEqual(result["total"], 15)
        self.assertEqual(result["measured"], 0)
        self.assertEqual(result["unmeasured"], 15)
        self.assertEqual(result["limit"], 20)
        self.assertTrue(all(entry["volume"] is None
                            for entry in result["keywords"]))
        self.assertTrue(all(entry["volume_status"] == VOLUME_UNMEASURED
                            for entry in result["keywords"]))

    def test_prefixes_present(self):
        """البادئات الخمس كلها حاضرة بمصدر «بادئة»."""
        result = generate_keywords("الصدقة")
        words = _words(result)
        for prefix in PREFIXES:
            self.assertIn(prefix + "الصدقة", words)
        sources = {e["keyword"]: e["source"] for e in result["keywords"]}
        self.assertEqual(sources["قصص قبل النوم الصدقة"], SOURCE_PREFIX)

    def test_suffixes_present(self):
        """اللواحق السبع كلها حاضرة بمصدر «لاحقة»."""
        result = generate_keywords("الصدقة")
        words = _words(result)
        for suffix in (" حقيقية", " مؤثرة", " قصيرة", " للاطفال",
                       " وعبرة", " من الواقع", " كاملة"):
            self.assertIn("الصدقة" + suffix, words)
        sources = {e["keyword"]: e["source"] for e in result["keywords"]}
        self.assertEqual(sources["الصدقة وعبرة"], SOURCE_SUFFIX)

    def test_long_tail_present_and_part_one_rejected(self):
        """الذيل الطويل القصصي حاضر، و«الجزء الاول» مرفوض تمامًا."""
        result = generate_keywords("الصدقة")
        words = _words(result)
        for tail in (" ملخص", " بالعربي", " مكتوبة"):
            self.assertIn("الصدقة" + tail, words)
        sources = {e["keyword"]: e["source"] for e in result["keywords"]}
        self.assertEqual(sources["الصدقة ملخص"], SOURCE_LONG_TAIL)
        self.assertFalse(any("الجزء" in word for word in words))
        self.assertFalse(any("الاول" in word for word in words))

    def test_seed_never_in_results(self):
        """البذرة نفسها لا تظهر في النتائج."""
        result = generate_keywords("الصدقة")
        self.assertNotIn("الصدقة", _words(result))
        self.assertNotIn("الصدقة", [e["keyword"] for e in result["keywords"]])

    def test_limit_truncates_in_generation_order(self):
        """limit=5: أول خمسة بترتيب التوليد (البادئات أولًا)."""
        result = generate_keywords("الصدقة", limit=5)
        self.assertEqual(_words(result), [
            "قصص الصدقة",
            "قصة الصدقة",
            "حكاية الصدقة",
            "قصص واقعية الصدقة",
            "قصص قبل النوم الصدقة",
        ])

    def test_seed_stripped(self):
        """بذرة بفراغات: تُجرَّد والكلمات نظيفة."""
        result = generate_keywords("  الصدقة  ")
        self.assertEqual(result["seed"], "الصدقة")
        self.assertIn("قصص الصدقة", _words(result))
        self.assertTrue(all(word == word.strip()
                            for word in _words(result)))

    def test_deterministic(self):
        """نفس المدخل مرتين: نفس النتيجة تمامًا."""
        first = generate_keywords("التوبة", corpus=[
            {"keyword": "قصص التوبة", "volume": 9000},
            {"keyword": "قصص واقعية", "volume": 8000},
        ])
        second = generate_keywords("التوبة", corpus=[
            {"keyword": "قصص التوبة", "volume": 9000},
            {"keyword": "قصص واقعية", "volume": 8000},
        ])
        self.assertEqual(first, second)


class TestWithCorpus(unittest.TestCase):
    """مسار سعيد مع corpus: وراثة الحجم والتوسيع والترتيب."""

    def test_corpus_volume_inherited_and_sorted(self):
        """حجم corpus يُورَّث للصيغة المولّدة المطابقة ويُرتَّب تنازليًا."""
        corpus = [
            {"keyword": "قصص الصدقة", "volume": 100},
            {"keyword": "الصدقة مؤثرة", "volume": 900},
            {"keyword": "قصص واقعية الصدقة", "volume": 500},
        ]
        result = generate_keywords("الصدقة", corpus=corpus)
        words = _words(result)
        self.assertEqual(words[0], "الصدقة مؤثرة")
        self.assertEqual(words[1], "قصص واقعية الصدقة")
        self.assertEqual(words[2], "قصص الصدقة")
        volumes = [e["volume"] for e in result["keywords"][:3]]
        self.assertEqual(volumes, [900, 500, 100])
        self.assertEqual(result["measured"], 3)

    def test_measured_before_unmeasured(self):
        """الحجم المعروف قبل «غير مقاس»؛ وغير المقاس بترتيب التوليد."""
        corpus = [{"keyword": "الصدقة مكتوبة", "volume": 50}]
        result = generate_keywords("الصدقة", corpus=corpus)
        words = _words(result)
        self.assertEqual(words[0], "الصدقة مكتوبة")
        self.assertEqual(result["keywords"][0]["volume"], 50)
        self.assertEqual(words[1], "قصص الصدقة")
        self.assertEqual(result["keywords"][1]["volume_status"],
                         VOLUME_UNMEASURED)
        self.assertEqual(words[2], "قصة الصدقة")

    def test_volume_tie_keeps_generation_order(self):
        """حجمان متساويان: ترتيب التوليد يحسم (الفرز مستقر)."""
        corpus = [
            {"keyword": "قصة الصدقة", "volume": 200},
            {"keyword": "قصص الصدقة", "volume": 200},
        ]
        result = generate_keywords("الصدقة", corpus=corpus)
        self.assertEqual(_words(result)[:2],
                         ["قصص الصدقة", "قصة الصدقة"])

    def test_corpus_keyword_included_verbatim(self):
        """كلمة corpus لا يولّدها قالب تظهر كما هي بمصدرها وحجمها."""
        corpus = [{"keyword": "فضل الصدقة على الفقير", "volume": 1234}]
        result = generate_keywords("الصدقة", corpus=corpus)
        entry = [e for e in result["keywords"]
                 if e["keyword"] == "فضل الصدقة على الفقير"]
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry[0]["volume"], 1234)
        self.assertEqual(entry[0]["source"], SOURCE_CORPUS)

    def test_corpus_expansion_shared_words(self):
        """كلمة تظهر في كلمتي corpus: «البذرة + الكلمة» تُولَّد."""
        corpus = [
            {"keyword": "قصص أطفال قبل النوم", "volume": 700},
            {"keyword": "حكايات أطفال مؤثرة", "volume": 600},
        ]
        result = generate_keywords("الصدقة", corpus=corpus)
        entry = [e for e in result["keywords"]
                 if e["keyword"] == "الصدقة أطفال"]
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry[0]["source"], SOURCE_EXPANSION)
        self.assertIsNone(entry[0]["volume"])

    def test_seed_excluded_even_from_corpus(self):
        """البذرة واردة في الـcorpus: لا تظهر في النتائج."""
        corpus = [
            {"keyword": "الصدقة", "volume": 99999},
            {"keyword": "قصص الصدقة", "volume": 100},
        ]
        result = generate_keywords("الصدقة", corpus=corpus)
        self.assertNotIn("الصدقة", _words(result))
        self.assertEqual(result["measured"], 1)

    def test_corpus_json_string_accepted(self):
        """الـcorpus كنص JSON يُقبل مثل القائمة."""
        text = json.dumps([{"keyword": "قصص الصدقة", "volume": 42}],
                          ensure_ascii=False)
        result = generate_keywords("الصدقة", corpus=text)
        self.assertEqual(result["keywords"][0]["keyword"], "قصص الصدقة")
        self.assertEqual(result["keywords"][0]["volume"], 42)


class TestDedupNormalization(unittest.TestCase):
    """إزالة التكرار بالتطبيع — صيغة العرض الأولى تفوز."""

    def test_dedup_tashkeel(self):
        """«قصص» و«قِصَص» بالتشكيل: مرشح واحد بصيغة العرض الأولى."""
        corpus = [{"keyword": "قِصَص الصَّدقة", "volume": 300}]
        result = generate_keywords("الصدقة", corpus=corpus)
        matches = [e for e in result["keywords"]
                   if normalize_keyword(e["keyword"]) == "قصص الصدقه"]
        self.assertEqual(len(matches), 1)
        # صيغة العرض الأولى (قالب البادئة) تفوز، والحجم يُورَّث.
        self.assertEqual(matches[0]["keyword"], "قصص الصدقة")
        self.assertEqual(matches[0]["volume"], 300)

    def test_dedup_ta_marbuta_and_alef(self):
        """ة←ه وآ←ا: «قصص الصدقه» و«قصص الصدقة» مرشح واحد."""
        corpus = [{"keyword": "قصص الصدقه", "volume": 300},
                  {"keyword": "قصص الصدقة", "volume": 400}]
        result = generate_keywords("الصدقة", corpus=corpus)
        matches = [e for e in result["keywords"]
                   if normalize_keyword(e["keyword"]) == "قصص الصدقه"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["keyword"], "قصص الصدقة")
        self.assertEqual(matches[0]["volume"], 300)

    def test_dedup_tatweel(self):
        """التطويل يُزال: «قصـص الصدقة» تطابق «قصص الصدقة»."""
        self.assertEqual(normalize_keyword("قصـص الصدقة"), "قصص الصدقه")
        corpus = [{"keyword": "قصـص الصدقة", "volume": 77}]
        result = generate_keywords("الصدقة", corpus=corpus)
        matches = [e for e in result["keywords"]
                   if normalize_keyword(e["keyword"]) == "قصص الصدقه"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["volume"], 77)

    def test_dedup_long_tail_suffix_duplicate(self):
        """« كاملة» لاحقة وذيل: تظهر مرة واحدة بمصدر اللاحقة."""
        result = generate_keywords("الصدقة")
        matches = [e for e in result["keywords"]
                   if e["keyword"] == "الصدقة كاملة"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["source"], SOURCE_SUFFIX)


class TestValidation(unittest.TestCase):
    """مدخلات فاسدة → ValueError عربي."""

    def test_empty_seed_raises(self):
        for bad in ("", "   ", None, 123, ["الصدقة"]):
            with self.assertRaises(ValueError, msg=repr(bad)):
                generate_keywords(bad)

    def test_limit_too_big_raises(self):
        with self.assertRaises(ValueError):
            generate_keywords("الصدقة", limit=101)

    def test_limit_invalid_raises(self):
        for bad in (0, -1, 1.5, "20", True, None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                generate_keywords("الصدقة", limit=bad)

    def test_limit_100_ok(self):
        """حد 100 مسموح: 100 كلمة من corpus كبير بلا قصّ زائد."""
        corpus = [{"keyword": f"كلمة تجريبية {i}", "volume": i}
                  for i in range(120)]
        result = generate_keywords("الصدقة", corpus=corpus, limit=100)
        self.assertEqual(result["total"], 100)
        self.assertEqual(result["limit"], 100)
        # الأعلى حجمًا أولًا: 119 ثم 118.
        self.assertEqual(result["keywords"][0]["volume"], 119)
        self.assertEqual(result["keywords"][1]["volume"], 118)

    def test_corpus_bad_entry_raises(self):
        with self.assertRaises(ValueError):
            generate_keywords("الصدقة", corpus=["ليست قاموسًا"])
        with self.assertRaises(ValueError):
            generate_keywords("الصدقة", corpus=[{"volume": 5}])
        with self.assertRaises(ValueError):
            generate_keywords("الصدقة", corpus=[{"keyword": "   "}])
        with self.assertRaises(ValueError):
            generate_keywords("الصدقة",
                              corpus=[{"keyword": "ك", "volume": -5}])
        with self.assertRaises(ValueError):
            generate_keywords("الصدقة",
                              corpus=[{"keyword": "ك", "volume": True}])
        with self.assertRaises(ValueError):
            generate_keywords("الصدقة",
                              corpus=[{"keyword": "ك", "volume": "كثير"}])

    def test_corpus_wrong_type_raises(self):
        with self.assertRaises(ValueError):
            generate_keywords("الصدقة", corpus=123)


class TestJsonAndReport(unittest.TestCase):
    """المدخل JSON والمخرج JSON والتقرير العربي."""

    def test_load_corpus_json_valid(self):
        text = json.dumps([{"keyword": "قصص الصدقة", "volume": 42},
                           {"keyword": "قصة الصدقة"}],
                          ensure_ascii=False)
        corpus = load_corpus_json(text)
        self.assertEqual(len(corpus), 2)
        self.assertEqual(corpus[0]["volume"], 42)
        self.assertIsNone(corpus[1]["volume"])

    def test_load_corpus_json_broken(self):
        with self.assertRaises(ValueError):
            load_corpus_json("{ليس json")
        with self.assertRaises(ValueError):
            load_corpus_json(json.dumps({"keyword": "ليست قائمة"}))
        with self.assertRaises(ValueError):
            load_corpus_json(
                json.dumps([{"keyword": "ك", "volume": -1}]))

    def test_load_corpus_json_empty_list_allowed(self):
        self.assertEqual(load_corpus_json("[]"), [])

    def test_to_json_round_trip(self):
        result = generate_keywords("الصدقة", corpus=[
            {"keyword": "قصص الصدقة", "volume": 9000}])
        text = to_json(result)
        self.assertTrue(text.endswith("\n"))
        # عربي بلا ASCII هارب.
        self.assertIn("الصدقة", text)
        self.assertNotIn("\\u", text)
        payload = json.loads(text)
        self.assertEqual(payload, result)
        self.assertEqual(payload["keywords"][0]["volume"], 9000)

    def test_to_json_rejects_non_dict(self):
        with self.assertRaises(ValueError):
            to_json(["ليست نتيجة"])

    def test_format_report_contents(self):
        result = generate_keywords("الصدقة", corpus=[
            {"keyword": "قصص الصدقة", "volume": 9000}])
        report = format_report(result)
        self.assertIn("الصدقة", report)
        self.assertIn("قصص الصدقة", report)
        self.assertIn("حجم 9000", report)
        self.assertIn("غير مقاس", report)
        self.assertIn("لا أحجام مخترعة", report)
        self.assertIn("البذرة نفسها ليست ضمن النتائج", report)

    def test_format_report_rejects_bad_result(self):
        with self.assertRaises(ValueError):
            format_report({"keywords": []})
        with self.assertRaises(ValueError):
            format_report("ليست نتيجة")

    def test_module_exports(self):
        self.assertIn("generate_keywords", keyword_generate.__all__)
        self.assertIn("to_json", keyword_generate.__all__)
        self.assertIn("format_report", keyword_generate.__all__)
        self.assertIn("load_corpus_json", keyword_generate.__all__)


class TestDegenerateGuard(unittest.TestCase):
    """حارس التكرار اللفظي (عيب وجده الفحص الحي للمنسّق):
    بذرة «قصص» كانت تولّد «قصص قصص»."""

    def test_category_seed_skips_all_prefixes(self):
        """بذرة «قصص»: بلا أي بادئة، و10 مرشحين (لواحق وذيول)."""
        result = generate_keywords("قصص")
        words = _words(result)
        sources = {e["keyword"]: e["source"]
                   for e in result["keywords"]}
        self.assertEqual(result["total"], 10)
        self.assertNotIn(SOURCE_PREFIX, sources.values())
        self.assertIn("قصص حقيقية", words)
        for word in words:
            tokens = normalize_keyword(word).split()
            self.assertEqual(len(tokens), len(set(tokens)), word)

    def test_singular_category_seed(self):
        """بذرة «قصة»: بلا «قصة قصص»، و«قصة حقيقية» حاضرة."""
        result = generate_keywords("قصة")
        words = _words(result)
        self.assertNotIn("قصة قصص", words)
        self.assertIn("قصة حقيقية", words)
        sources = {e["keyword"]: e["source"]
                   for e in result["keywords"]}
        self.assertNotIn(SOURCE_PREFIX, sources.values())

    def test_suffix_repeat_skipped(self):
        """بذرة «قصص حقيقية»: اللاحقة المكررة تُسقط."""
        result = generate_keywords("قصص حقيقية")
        words = _words(result)
        self.assertNotIn("قصص حقيقية حقيقية", words)
        self.assertIn("قصص حقيقية مؤثرة", words)

    def test_topic_seed_prefixes_unchanged(self):
        """بذرة موضوع («توبة») بلا كلمة فئة: البادئات تعمل."""
        result = generate_keywords("توبة")
        self.assertIn("قصص توبة", _words(result))


if __name__ == "__main__":
    unittest.main()
