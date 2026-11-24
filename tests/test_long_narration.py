#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات السرد الطويل المقسّم (lib.long_narration) — Piper (رجل).

تعمل بـ `python3 -m unittest discover -s tests -v`.
اختبار التركيب الحقيقي يستخدم Piper المحلي (بلا شبكة) على جملتين
قصيرتين فقط.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import long_narration

# Piper ثنائي خارجي لا يثبته CI — الاختبارات الحية تتخطى عند غيابه.
_PIPER_OK = bool(
    shutil.which("piper")
    or os.path.isfile(os.path.expanduser("~/.local/bin/piper")))


class TestSplitSentences(unittest.TestCase):
    def test_arabic_punctuation(self):
        text = "هذه قصة قصيرة. هل سمعتها من قبل؟ إنها عجيبة! تابع معنا…"
        got = long_narration.split_sentences(text)
        self.assertEqual(len(got), 4)
        self.assertTrue(got[0].endswith("."))
        self.assertTrue(got[1].endswith("؟"))

    def test_newlines_split(self):
        got = long_narration.split_sentences("سطر أول\nسطر ثانٍ")
        self.assertEqual(got, ["سطر أول", "سطر ثانٍ"])

    def test_empty(self):
        self.assertEqual(long_narration.split_sentences(""), [])
        self.assertEqual(long_narration.split_sentences("   "), [])


class TestSplitChunks(unittest.TestCase):
    def test_short_text_is_one_chunk(self):
        got = long_narration.split_chunks("قصة قصيرة عن الصدق.")
        self.assertEqual(got, ["قصة قصيرة عن الصدق."])

    def test_long_sentence_splits_at_commas(self):
        long_s = "، ".join(["كلمة"] * 80) + "."
        got = long_narration.split_chunks(long_s, max_chars=100)
        self.assertGreater(len(got), 1)
        for c in got:
            self.assertLessEqual(len(c), 100)

    def test_no_word_is_cut(self):
        text = " ".join(["الكلمةالطويلة"] * 40) + "."
        got = long_narration.split_chunks(text, max_chars=50)
        joined = " ".join(got)
        self.assertEqual(joined.split(), text.split())

    def test_chunks_keep_all_words(self):
        text = "أول جملة قصيرة. ثاني جملة أطول قليلًا من الأولى. ثالثة."
        got = long_narration.split_chunks(text)
        self.assertEqual(" ".join(got).split(), text.split())


class TestSynthesizeLong(unittest.TestCase):
    @unittest.skipUnless(_PIPER_OK, "Piper غائب — بيئة CI")
    def test_two_sentences_with_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "long.wav")
            text = "السلام عليكم ورحمة الله. هذه قصة قصيرة."
            result = long_narration.synthesize_long(text, out, gap=0.5)
            self.assertTrue(os.path.isfile(out))
            self.assertEqual(len(result["chunks"]), 2)
            self.assertGreater(result["duration"], 0)
            c0, c1 = result["chunks"]
            self.assertEqual(c0["start"], 0.0)
            # بداية الجملة الثانية = مدة الأولى + الفاصل
            self.assertAlmostEqual(c1["start"], c0["end"] + 0.5, places=1)
            self.assertAlmostEqual(c1["end"], result["duration"], places=1)
            self.assertGreater(long_narration.probe_duration(out), 0)

    @unittest.skipUnless(_PIPER_OK, "Piper غائب — بيئة CI")
    def test_atempo_shortens(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = "السلام عليكم ورحمة الله وبركاته."
            normal = long_narration.synthesize_long(
                text, os.path.join(tmp, "n.wav"), gap=0.0)
            fast = long_narration.synthesize_long(
                text, os.path.join(tmp, "f.wav"), gap=0.0, atempo=1.25)
            self.assertLess(fast["duration"], normal["duration"])
            self.assertAlmostEqual(
                fast["duration"], normal["duration"] / 1.25, delta=0.3)

    def test_empty_text_raises(self):
        with self.assertRaises(long_narration.LongNarrationError):
            long_narration.synthesize_long("   ", "/tmp/nope.wav")

    def test_missing_piper_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(long_narration.LongNarrationError):
                long_narration.synthesize_long(
                    "نص قصير.", os.path.join(tmp, "x.wav"),
                    piper_bin="/nonexistent/piper")

    def test_bad_atempo_raises(self):
        with self.assertRaises(long_narration.LongNarrationError):
            long_narration.synthesize_long(
                "نص قصير.", "/tmp/nope.wav", atempo=3.0)


if __name__ == "__main__":
    unittest.main()
