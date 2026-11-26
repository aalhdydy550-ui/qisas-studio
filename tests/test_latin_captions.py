#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات مسار الكابشن اللاتيني LTR (EN-06).

تعمل بـ `env -u PYTHONNOUSERSITE python3 -m unittest tests.test_latin_captions -v`
من جذر الشجرة. تتحقق من: تقسيم الكلمات بلا كسر داخل
الاختصارات والأرقام وعلامات الترقيم؛ وملف ASS باتجاه LTR
صريح وبلا أي منطق RTL؛ وموضع الكابشن أسفل الصورة فقط
(على قيم ASS الفعلية، مطابقة لشريط الكابشن العربي)؛
والتزامن عبارة بعبارة؛ وخط Noto Sans العريض موثق الترخيص.
"""
import hashlib
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import capite_captions, latin_captions, whisper_captions

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from fontTools.ttLib import TTFont
except ImportError:  # pragma: no cover
    TTFont = None

_RTL_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF"
    r"\uFE70-\uFEFF\u200F\u202B\u202C\u202D\u202E]")


def _words(text, start=0.0, step=0.5, dur=0.4):
    """كلمات بتوقيتات متتابعة من نص (لاختبارات التزامن)."""
    out = []
    t = start
    for w in latin_captions.split_latin_words(text):
        out.append({"w": w, "start": round(t, 2),
                    "end": round(t + dur, 2)})
        t += step
    return out


def _dialogues(ass_text):
    """أسطر Dialogue من نص ASS: (start, end, text)."""
    out = []
    for line in ass_text.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line[len("Dialogue:"):].split(",", 9)
        out.append((parts[1], parts[2], parts[9]))
    return out


def _ass_time_to_seconds(token):
    h, m, s = token.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _style_fields(ass_text):
    """حقول سطر Style في الترويسة كقاموس بالاسم."""
    names = ["Name", "Fontname", "Fontsize", "PrimaryColour",
             "SecondaryColour", "OutlineColour", "BackColour", "Bold",
             "Italic", "Underline", "StrikeOut", "ScaleX", "ScaleY",
             "Spacing", "Angle", "BorderStyle", "Outline", "Shadow",
             "Alignment", "MarginL", "MarginR", "MarginV", "Encoding"]
    for line in ass_text.splitlines():
        if line.startswith("Style:"):
            values = line[len("Style:"):].split(",")
            return dict(zip(names, values))
    return {}


class TestSplitLatinWords(unittest.TestCase):
    def test_title_abbreviations_not_split(self):
        self.assertEqual(
            latin_captions.split_latin_words("Mr. Smith met Dr. Jones"),
            ["Mr.", "Smith", "met", "Dr.", "Jones"])

    def test_money_amount_not_split(self):
        self.assertEqual(
            latin_captions.split_latin_words("He paid $20,000 in cash"),
            ["He", "paid", "$20,000", "in", "cash"])

    def test_money_with_trailing_sentence_period(self):
        self.assertEqual(
            latin_captions.split_latin_words("He paid $20,000."),
            ["He", "paid", "$20,000."])

    def test_initialism_not_split(self):
        self.assertEqual(
            latin_captions.split_latin_words("He flew to the U.S. today"),
            ["He", "flew", "to", "the", "U.S.", "today"])
        self.assertEqual(
            latin_captions.split_latin_words("from the U.S.A. office"),
            ["from", "the", "U.S.A.", "office"])

    def test_contraction_not_split(self):
        self.assertEqual(
            latin_captions.split_latin_words("I don't know why"),
            ["I", "don't", "know", "why"])
        self.assertEqual(
            latin_captions.split_latin_words("It's a test, isn't it?"),
            ["It's", "a", "test,", "isn't", "it?"])

    def test_all_five_cases_in_one_sentence(self):
        text = "Mr. Lee told Dr. Ray: I don't owe $20,000 in the U.S."
        self.assertEqual(
            latin_captions.split_latin_words(text),
            ["Mr.", "Lee", "told", "Dr.", "Ray:", "I", "don't", "owe",
             "$20,000", "in", "the", "U.S."])

    def test_plain_sentence_and_numbers(self):
        self.assertEqual(
            latin_captions.split_latin_words("He ran 3.5 miles in 50% rain"),
            ["He", "ran", "3.5", "miles", "in", "50%", "rain"])

    def test_hyphenated_word_kept_whole(self):
        self.assertEqual(
            latin_captions.split_latin_words("a well-known story"),
            ["a", "well-known", "story"])

    def test_empty_and_whitespace_only(self):
        self.assertEqual(latin_captions.split_latin_words(""), [])
        self.assertEqual(latin_captions.split_latin_words("   \n  "), [])
        self.assertEqual(latin_captions.split_latin_words(None), [])

    def test_no_character_is_lost(self):
        text = "Mr. X paid $20,000 — don't ask!"
        joined = " ".join(latin_captions.split_latin_words(text))
        for token in ("Mr.", "$20,000", "don't"):
            self.assertIn(token, joined)


class TestGroupLatinWordsIntoLines(unittest.TestCase):
    def test_groups_respect_max_chars_and_lines(self):
        words = _words("one two three four five six seven eight nine ten "
                       "eleven twelve thirteen fourteen fifteen sixteen")
        groups = latin_captions.group_latin_words_into_lines(
            words, max_chars=20, max_lines=2)
        self.assertGreater(len(groups), 1)
        for g in groups:
            self.assertLessEqual(len(g["lines"]), 2)
            for line in g["lines"]:
                self.assertLessEqual(
                    len(" ".join(w["w"] for w in line)), 20)

    def test_group_span_covers_its_words(self):
        words = _words("a short phrase here", start=1.0)
        groups = latin_captions.group_latin_words_into_lines(words)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["start"], 1.0)
        self.assertEqual(groups[0]["end"], words[-1]["end"])
        flat = [w["w"] for line in groups[0]["lines"] for w in line]
        self.assertEqual(flat, ["a", "short", "phrase", "here"])

    def test_word_key_alias_accepted(self):
        words = [{"word": "hello", "start": 0.0, "end": 0.5},
                 {"word": "world", "start": 0.6, "end": 1.0}]
        groups = latin_captions.group_latin_words_into_lines(words)
        self.assertEqual(groups[0]["lines"][0][0]["w"], "hello")

    def test_arabic_word_rejected(self):
        words = [{"w": "hello", "start": 0.0, "end": 0.5},
                 {"w": "قصة", "start": 0.6, "end": 1.0}]
        with self.assertRaises(latin_captions.LatinCaptionError):
            latin_captions.group_latin_words_into_lines(words)


class TestWordsToLatinAss(unittest.TestCase):
    def test_header_declares_ltr_explicitly(self):
        ass_text, _ = latin_captions.words_to_latin_ass(
            _words("hello world"))
        self.assertIn("LTR", ass_text)
        self.assertIn("Direction: LTR", ass_text)
        self.assertIn("Noto Sans", ass_text)

    def test_ass_has_no_rtl_logic_anywhere(self):
        ass_text, _ = latin_captions.words_to_latin_ass(
            _words("Mr. Smith paid $20,000 in the U.S."))
        self.assertIsNone(_RTL_RE.search(ass_text),
                          "محارف RTL في ملف ASS اللاتيني")
        self.assertNotIn("Noto Naskh Arabic", ass_text)
        self.assertNotIn("{\\c", ass_text)
        self.assertNotIn("{\\r", ass_text)
        self.assertNotIn("arabic", ass_text.lower())

    def test_position_is_bottom_only(self):
        ass_text, _ = latin_captions.words_to_latin_ass(
            _words("hello world"))
        style = _style_fields(ass_text)
        # Alignment 2 = أسفل الوسط — لا وسط (8) ولا أعلى (6/7/9).
        self.assertEqual(style["Alignment"], "2")
        self.assertEqual(style["MarginV"], "64")
        self.assertEqual(style["MarginL"], "40")
        self.assertEqual(style["MarginR"], "40")

    def test_position_matches_arabic_caption_bar(self):
        latin_text, _ = latin_captions.words_to_latin_ass(
            _words("hello world"))
        arabic_text = whisper_captions.ass_header()
        latin_style = _style_fields(latin_text)
        arabic_style = _style_fields(arabic_text)
        for key in ("Alignment", "MarginL", "MarginR", "MarginV",
                    "Fontsize", "Bold"):
            self.assertEqual(latin_style[key], arabic_style[key],
                             "اختلاف في %s بين شريطي الكابشن" % key)
        self.assertIn("PlayResX: 720", latin_text)
        self.assertIn("PlayResY: 1280", latin_text)
        # الخط وحده هو المختلف — العربي يبقى كما هو.
        self.assertNotEqual(latin_style["Fontname"],
                            arabic_style["Fontname"])
        self.assertEqual(latin_style["Fontname"], "Noto Sans")

    def test_one_dialogue_event_per_word(self):
        words = _words("one two three four")
        ass_text, _ = latin_captions.words_to_latin_ass(words)
        self.assertEqual(len(_dialogues(ass_text)), len(words))

    def test_phrase_by_phrase_sync_preserved(self):
        words = _words("one two three four five six", start=2.0,
                       step=0.5, dur=0.4)
        ass_text, groups = latin_captions.words_to_latin_ass(
            words, max_chars=12, max_lines=2)
        dialogues = _dialogues(ass_text)
        # أول حدث يبدأ مع أول كلمة، وآخر حدث ينتهي مع نهاية العبارة.
        self.assertAlmostEqual(
            _ass_time_to_seconds(dialogues[0][0]), words[0]["start"],
            places=2)
        self.assertAlmostEqual(
            _ass_time_to_seconds(dialogues[-1][1]), groups[-1]["end"],
            places=2)
        # كل حدث ينتهي عند بداية الكلمة التالية ناقص 0.01 إن كانت
        # في المجموعة نفسها، أو عند نهاية مجموعته إن كانت آخر
        # كلمة فيها.
        flat = []
        for g in groups:
            for line in g["lines"]:
                for w in line:
                    flat.append((w, g))
        self.assertEqual(len(dialogues), len(flat))
        for i, (start, end, _text) in enumerate(dialogues):
            s = _ass_time_to_seconds(start)
            e = _ass_time_to_seconds(end)
            self.assertGreater(e, s, "حدث بلا مدة: %s" % (start,))
            self.assertAlmostEqual(s, flat[i][0]["start"], places=2)
            if i + 1 < len(flat) and flat[i + 1][1] is flat[i][1]:
                self.assertAlmostEqual(
                    e, flat[i + 1][0]["start"] - 0.01, places=2)
            else:
                self.assertAlmostEqual(e, flat[i][1]["end"], places=2)

    def test_dialogue_text_is_the_full_phrase(self):
        words = _words("honest man keeps his word")
        ass_text, _ = latin_captions.words_to_latin_ass(words)
        for _start, _end, text in _dialogues(ass_text):
            self.assertEqual(text, "honest man keeps his word")

    def test_multiline_group_joins_with_ass_break(self):
        words = _words("alpha beta gamma delta epsilon zeta eta theta",
                       step=0.5, dur=0.4)
        ass_text, groups = latin_captions.words_to_latin_ass(
            words, max_chars=12, max_lines=2)
        self.assertGreater(len(groups), 0)
        multi = [g for g in groups if len(g["lines"]) > 1]
        self.assertTrue(multi, "لا مجموعة متعددة الأسطر للفحص")
        self.assertIn("\\N", ass_text)

    def test_empty_words_raise(self):
        with self.assertRaises(latin_captions.LatinCaptionError):
            latin_captions.words_to_latin_ass([])

    def test_arabic_input_raise(self):
        words = [{"w": "hello", "start": 0.0, "end": 0.5},
                 {"w": "قصة", "start": 0.6, "end": 1.0}]
        with self.assertRaises(latin_captions.LatinCaptionError):
            latin_captions.words_to_latin_ass(words)

    def test_ass_text_escapes_special_chars(self):
        words = [{"w": "a{b}c", "start": 0.0, "end": 0.5}]
        ass_text, _ = latin_captions.words_to_latin_ass(words)
        self.assertIn("a\\{b\\}c", ass_text)


class TestLatinFont(unittest.TestCase):
    def test_latin_font_is_family_name_not_path(self):
        self.assertEqual(latin_captions.LATIN_FONT, "Noto Sans")
        self.assertNotIn("/", latin_captions.LATIN_FONT)
        self.assertNotIn("subset", latin_captions.LATIN_FONT)

    def test_latin_font_license_documented(self):
        self.assertIn("SIL Open Font License",
                      latin_captions.LATIN_FONT_LICENSE)
        self.assertIn("1.1", latin_captions.LATIN_FONT_LICENSE)
        self.assertIn("google/fonts", latin_captions.LATIN_FONT_SOURCE)
        self.assertIn("notosans", latin_captions.LATIN_FONT_SOURCE)

    def test_tree_font_file_exists_and_matches_fingerprint(self):
        self.assertTrue(os.path.isfile(latin_captions.LATIN_FONT_FILE),
                        "خط الشجرة مفقود: %s"
                        % latin_captions.LATIN_FONT_FILE)
        with open(latin_captions.LATIN_FONT_FILE, "rb") as f:
            data = f.read()
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         latin_captions.LATIN_FONT_SHA256)
        self.assertGreater(len(data), 50000)
        self.assertLess(len(data), 200000)

    def test_system_font_exists_for_ass_resolution(self):
        self.assertTrue(
            os.path.isfile(latin_captions.LATIN_FONT_SYSTEM_FILE),
            "خط النظام الذي يحلّ إليه ASS مفقود")

    @unittest.skipUnless(TTFont is not None, "fontTools غير مثبّت")
    def test_tree_font_identity(self):
        font = TTFont(latin_captions.LATIN_FONT_FILE)
        try:
            self.assertEqual(font["name"].getDebugName(1), "Noto Sans")
            self.assertEqual(font["name"].getDebugName(2), "Bold")
            self.assertTrue(
                font["name"].getDebugName(5).startswith("Version 2.015"),
                font["name"].getDebugName(5))
            self.assertIn("SIL Open Font License",
                          font["name"].getDebugName(13))
            # مقسّم فرعيًا فعلًا: أقل glyphs من الأصل الكامل.
            self.assertLess(font["maxp"].numGlyphs, 1000)
            self.assertGreater(font["maxp"].numGlyphs, 500)
            cmap = font.getBestCmap()
            for cp in (0x41, 0x61, 0x30, 0x24, 0x2C, 0x2E, 0x27,
                       0x2019, 0x2014, 0x20AC):
                self.assertIn(cp, cmap, "U+%04X مفقود من المجموعة" % cp)
            # حرف عربي لم يُطلب غير موجود — التقسيم فعلي.
            self.assertNotIn(0x627, cmap)
        finally:
            font.close()

    def test_arabic_path_untouched(self):
        # الخط العربي يبقى كما هو بلا أي تغيير في مساره.
        self.assertEqual(capite_captions.ASS_FONT_FAMILY,
                         "Noto Naskh Arabic")
        self.assertEqual(latin_captions.LATIN_FONT, "Noto Sans")


if __name__ == "__main__":
    unittest.main()
