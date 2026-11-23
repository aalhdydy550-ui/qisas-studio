#!/usr/bin/env python3
"""اختبارات صوت Supertonic M1 (lib.supertonic_voice).

تعمل بـ `python3 -m unittest discover -s tests -v`.
الاختبار الحقيقي (test_real_synthesis) يركّب جملة عربية قصيرة
فعلًا بالنموذج المحلي — ويُتخطى تلقائيًا إن غاب النموذج أو
مفسّر الحزمة، بدل فشل كاذب. لا ينزّل النموذج أبدًا.
"""
import os
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import supertonic_voice


class TestNormalizeText(unittest.TestCase):
    def test_semicolon_to_comma(self):
        self.assertEqual(
            supertonic_voice.normalize_text("قال؛ ثم سكت؛ ومضى"),
            "قال، ثم سكت، ومضى")

    def test_semicolon_at_edges(self):
        self.assertEqual(
            supertonic_voice.normalize_text("؛في البداية كان؛"),
            "،في البداية كان،")

    def test_only_semicolons(self):
        self.assertEqual(supertonic_voice.normalize_text("؛؛؛"), "،،،")

    def test_no_semicolon_unchanged(self):
        text = "قال، ثم سكت. ومضى إلى السوق!"
        self.assertEqual(supertonic_voice.normalize_text(text), text)

    def test_empty_and_none(self):
        self.assertEqual(supertonic_voice.normalize_text(""), "")
        self.assertEqual(supertonic_voice.normalize_text(None), "")


class TestNumbersToWords(unittest.TestCase):
    def test_three(self):
        self.assertEqual(supertonic_voice.numbers_to_words("3"), "ثلاثة")

    def test_zero_and_one_two(self):
        self.assertEqual(supertonic_voice.numbers_to_words("0"), "صفر")
        self.assertEqual(supertonic_voice.numbers_to_words("1"), "واحد")
        self.assertEqual(supertonic_voice.numbers_to_words("2"), "اثنان")

    def test_year_2026(self):
        # الصيغة الموثقة في مهمة الدمج.
        self.assertEqual(supertonic_voice.numbers_to_words("2026"),
                         "ألفان وستة وعشرون")

    def test_year_1999(self):
        self.assertEqual(supertonic_voice.numbers_to_words("1999"),
                         "ألف وتسعمئة وتسعة وتسعون")

    def test_tens_and_compounds(self):
        self.assertEqual(supertonic_voice.numbers_to_words("10"), "عشرة")
        self.assertEqual(supertonic_voice.numbers_to_words("12"),
                         "اثنا عشر")
        self.assertEqual(supertonic_voice.numbers_to_words("21"),
                         "واحد وعشرون")
        self.assertEqual(supertonic_voice.numbers_to_words("99"),
                         "تسعة وتسعون")

    def test_hundreds_and_thousands(self):
        self.assertEqual(supertonic_voice.numbers_to_words("100"), "مئة")
        self.assertEqual(supertonic_voice.numbers_to_words("200"), "مئتان")
        self.assertEqual(supertonic_voice.numbers_to_words("101"),
                         "مئة وواحد")
        self.assertEqual(supertonic_voice.numbers_to_words("1000"), "ألف")
        self.assertEqual(supertonic_voice.numbers_to_words("2000"), "ألفان")
        self.assertEqual(supertonic_voice.numbers_to_words("3000"),
                         "ثلاثة آلاف")
        self.assertEqual(supertonic_voice.numbers_to_words("11000"),
                         "أحد عشر ألفًا")
        self.assertEqual(supertonic_voice.numbers_to_words("1500"),
                         "ألف وخمسمئة")

    def test_eastern_digits(self):
        self.assertEqual(supertonic_voice.numbers_to_words("٣"), "ثلاثة")
        self.assertEqual(supertonic_voice.numbers_to_words("٢٠٢٦"),
                         "ألفان وستة وعشرون")
        self.assertEqual(supertonic_voice.numbers_to_words("١٢"),
                         "اثنا عشر")

    def test_inside_sentence(self):
        self.assertEqual(
            supertonic_voice.numbers_to_words(
                "عاش 3 إخوة في سنة 2026"),
            "عاش ثلاثة إخوة في سنة ألفان وستة وعشرون")

    def test_no_digits_unchanged(self):
        text = "لا أرقام هنا"
        self.assertEqual(supertonic_voice.numbers_to_words(text), text)

    def test_too_large_left_as_digits(self):
        # أكبر من 999999 يُترك رقمًا (حد موثّق في docstring).
        self.assertEqual(supertonic_voice.numbers_to_words("1000000"),
                         "1000000")

    def test_prepare_text_combines_both(self):
        self.assertEqual(
            supertonic_voice.prepare_text("قال؛ كان له 3 أبناء"),
            "قال، كان له ثلاثة أبناء")


class TestVoiceSelection(unittest.TestCase):
    def test_available_voices(self):
        self.assertEqual(supertonic_voice.available_voices(), ["M1"])

    def test_disclosure_line(self):
        self.assertEqual(supertonic_voice.DISCLOSURE_LINE,
                         "صوت مولّد بالذكاء الاصطناعي")

    def test_m2_rejected_with_clear_message(self):
        with self.assertRaises(ValueError) as ctx:
            supertonic_voice.synthesize("نص", voice="M2",
                                        out_path="/tmp/x.wav")
        self.assertIn("M2", str(ctx.exception))
        self.assertIn("غير مدمج", str(ctx.exception))

    def test_unknown_voice_rejected(self):
        for voice in ("gtts", "piper", "M3", "F1", ""):
            with self.assertRaises(ValueError) as ctx:
                supertonic_voice.synthesize("نص", voice=voice,
                                            out_path="/tmp/x.wav")
            self.assertIn("غير مدعوم", str(ctx.exception))

    def test_empty_text_rejected(self):
        with self.assertRaises(supertonic_voice.SupertonicError):
            supertonic_voice.synthesize("   ", out_path="/tmp/x.wav")

    def test_missing_model_clear_error(self):
        # مجلد نموذج فارغ: خطأ عربي واضح بلا أي تنزيل.
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(supertonic_voice.SupertonicError) as ctx:
                supertonic_voice.synthesize(
                    "نص قصير", out_path=os.path.join(tmp, "o.wav"),
                    model_dir=tmp)
            self.assertIn("غير موجود", str(ctx.exception))

    def test_model_available_locally(self):
        # النموذج المُتحقَّق في ~/.cache/supertonic3 موجود فعلًا.
        self.assertTrue(supertonic_voice.model_available())
        self.assertEqual(supertonic_voice.missing_model_files(), [])


class TestRealSynthesis(unittest.TestCase):
    def test_real_synthesis(self):
        """تركيب حقيقي قصير بـM1: نص عربي → WAV صالح 44100 هرتز.

        يُتخطى إن غاب النموذج أو مفسّر حزمة supertonic.
        زمن التوليف الموثّق ~الزمن الحقيقي (45–60 ثانية لمقطع
        ~65 ثانية)؛ فجملة قصيرة هنا تستغرق ثواني معدودة بعد
        تحميل النموذج.
        """
        if not supertonic_voice.model_available():
            self.skipTest("نموذج Supertonic-3 غير موجود محليًا")
        if supertonic_voice.find_supertonic_python() is None:
            self.skipTest("لا مفسّر بايثون فيه حزمة supertonic")
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "m1.wav")
            result = supertonic_voice.synthesize(
                "كان يا ما كان؛ في قديم الزمان 3 إخوة",
                out_path=out, timeout=600)
            self.assertEqual(result, os.path.abspath(out))
            self.assertTrue(os.path.getsize(out) > 1000)
            with wave.open(out, "rb") as w:
                self.assertEqual(w.getframerate(), 44100)
                self.assertEqual(w.getnchannels(), 1)
                self.assertGreater(w.getnframes(), 22050)  # > 0.5 ثانية


if __name__ == "__main__":
    unittest.main()
