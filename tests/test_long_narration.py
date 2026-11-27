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
import wave
from unittest import mock

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

    def test_english_punctuation(self):
        text = ("He found a wallet. He returned it! "
                "Did anyone believe him? Yes, they did.")
        got = long_narration.split_sentences(text)
        self.assertEqual(len(got), 4)
        self.assertTrue(got[0].endswith("."))
        self.assertTrue(got[1].endswith("!"))
        self.assertTrue(got[2].endswith("?"))

    def test_english_abbreviations_do_not_split(self):
        text = "Mr. Smith met Dr. Jones yesterday. He stayed home."
        got = long_narration.split_sentences(text)
        self.assertEqual(len(got), 2)
        self.assertTrue(got[0].endswith("yesterday."))
        self.assertIn("Mr. Smith", got[0])
        self.assertIn("Dr. Jones", got[0])

    def test_english_abbrev_eg_ie(self):
        text = ("He likes fruits, e.g. apples, and vegetables, "
                "i.e. carrots. He eats well.")
        got = long_narration.split_sentences(text)
        self.assertEqual(len(got), 2)

    def test_english_acronym_mid_sentence(self):
        text = "He lives in the U.S. now. He works there."
        got = long_narration.split_sentences(text)
        self.assertEqual(len(got), 2)
        self.assertTrue(got[0].endswith("now."))

    def test_english_quote_after_period(self):
        text = 'He whispered "Stop." Then he left.'
        got = long_narration.split_sentences(text)
        self.assertEqual(len(got), 2)
        self.assertTrue(got[0].endswith('."'))

    def test_english_numbers_not_split(self):
        text = "He won $20,000. He kept 3.5 dollars."
        got = long_narration.split_sentences(text)
        self.assertEqual(len(got), 2)
        self.assertIn("$20,000", got[0])
        self.assertIn("3.5", got[1])

    def test_english_ellipsis(self):
        got = long_narration.split_sentences("Wait... Then he left.")
        self.assertEqual(len(got), 2)
        self.assertTrue(got[0].endswith("..."))


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

    def test_long_english_sentence_splits_at_commas(self):
        long_s = ", ".join(["word"] * 80) + "."
        got = long_narration.split_chunks(long_s, max_chars=100)
        self.assertGreater(len(got), 1)
        for c in got:
            self.assertLessEqual(len(c), 100)

    def test_english_chunks_keep_all_words(self):
        text = ("A poor man found a wallet. He returned it to its "
                "owner. Everyone was surprised.")
        got = long_narration.split_chunks(text)
        self.assertEqual(" ".join(got).split(), text.split())

    def test_english_decimal_survives_chunking(self):
        text = "He won $20,000 in one night. He kept it."
        got = long_narration.split_chunks(text, max_chars=30)
        self.assertIn("$20,000", " ".join(got))
        for c in got:
            self.assertLessEqual(len(c), 30)


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


def _fake_synthesize_chunk(record, chunk_seconds=0.5):
    """بديل synthesize_chunk: يسجّل الموديل واللغة ويكتب WAV
    صامتًا صالحًا — بلا Piper حي وبلا ffmpeg."""
    def _fake(text, out_wav, piper_bin=None, model=None, timeout=120,
              voice="piper", lang="ar"):
        record.append({"text": text, "model": model, "voice": voice,
                       "lang": lang})
        with wave.open(out_wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(22050)
            w.writeframes(b"\x00\x00" * int(22050 * chunk_seconds))
        return out_wav
    return _fake


def _fake_concat(wav_paths, out_wav, gap=0.35):
    """بديل concatenate_with_gaps: ينسخ أول مقطع ويرجع مدة ثابتة."""
    shutil.copy2(wav_paths[0], out_wav)
    return 1.0


class TestSynthesizeLongLang(unittest.TestCase):
    """اختيار الموديل من lang — بلا توليد صوتي ثقيل."""

    def _run_mocked(self, text, **kwargs):
        record = []
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out.wav")
            with mock.patch.object(
                    long_narration, "synthesize_chunk",
                    _fake_synthesize_chunk(record)), \
                mock.patch.object(
                    long_narration, "concatenate_with_gaps",
                    _fake_concat), \
                mock.patch.object(
                    long_narration, "probe_duration",
                    lambda p: 0.5):
                result = long_narration.synthesize_long(
                    text, out, **kwargs)
            return record, result

    def test_lang_en_selects_ryan_model(self):
        record, result = self._run_mocked(
            "Hello world. This is a test.", lang="en")
        self.assertEqual(len(record), 2)
        for call in record:
            self.assertTrue(
                call["model"].endswith("en_US-ryan-medium.onnx"),
                call["model"])
            self.assertEqual(call["lang"], "en")
        self.assertEqual(len(result["chunks"]), 2)

    def test_default_is_arabic_kareem(self):
        record, _ = self._run_mocked("قصة قصيرة. جملة ثانية.")
        self.assertEqual(len(record), 2)
        for call in record:
            self.assertTrue(
                call["model"].endswith("ar_JO-kareem-medium.onnx"),
                call["model"])
            self.assertEqual(call["lang"], "ar")

    def test_unknown_lang_falls_back_to_arabic(self):
        record, _ = self._run_mocked("Hello world.", lang="xx")
        self.assertEqual(len(record), 1)
        self.assertTrue(
            record[0]["model"].endswith("ar_JO-kareem-medium.onnx"),
            record[0]["model"])

    def test_explicit_model_overrides_lang(self):
        record, _ = self._run_mocked(
            "Hello world.", lang="en", model="/tmp/custom-voice.onnx")
        self.assertEqual(record[0]["model"], "/tmp/custom-voice.onnx")

    def test_synthesize_chunk_resolves_model_from_lang(self):
        # حسم الموديل على مستوى المقطع: اعترض subprocess.run
        # وسجّل أمر Piper — بلا تشغيل Piper حيًا.
        calls = []

        def _fake_run(cmd, **kwargs):
            calls.append(cmd)
            out = cmd[cmd.index("--output_file") + 1]
            with wave.open(out, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(22050)
                w.writeframes(b"\x00\x00" * 100)
            proc = mock.Mock()
            proc.returncode = 0
            proc.stderr = ""
            proc.stdout = ""
            return proc

        # الموديل المحسوم من lang يعيش خارج شجرة المستودع
        # (~/workspace/tts-models) وغائب على عدّاء CI — احجب
        # فحص وجوده وحده، وفوّض باقي الفحوصات للدالة الحقيقية
        # (ثنائي Piper وملف الإخراج الناتج يُفحصان فعلًا).
        model_path = long_narration.i18n.resolve_voice_model(
            lang="en")[1]
        _real_isfile = os.path.isfile

        def _isfile(path):
            if path == model_path:
                return True
            return _real_isfile(path)

        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "c.wav")
            with mock.patch.object(long_narration.subprocess, "run",
                                   _fake_run), \
                    mock.patch.object(os.path, "isfile",
                                      side_effect=_isfile):
                got = long_narration.synthesize_chunk(
                    "Hello world.", out, piper_bin=sys.executable,
                    lang="en")
            self.assertEqual(got, out)
            self.assertEqual(len(calls), 1)
            model_arg = calls[0][calls[0].index("--model") + 1]
            self.assertTrue(
                model_arg.endswith("en_US-ryan-medium.onnx"), model_arg)

    def test_synthesize_chunk_missing_explicit_model_raises(self):
        # حارس وجود ملف الموديل: موديل صريح غير موجود يرفع
        # LongNarrationError — بلا تشغيل Piper حيًا. يغلب
        # الموديل الصريح lang حتى مع lang="en".
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "no-such-model.onnx")
            with self.assertRaises(
                    long_narration.LongNarrationError) as cm:
                long_narration.synthesize_chunk(
                    "Hello world.", os.path.join(tmp, "c.wav"),
                    piper_bin=sys.executable, model=missing,
                    lang="en")
            self.assertIn(missing, str(cm.exception))

    @unittest.skipUnless(
        _PIPER_OK and os.path.isfile(os.path.expanduser(
            "~/workspace/tts-models/en_US-ryan-medium.onnx")),
        "Piper أو موديل ryan الإنجليزي غائب")
    def test_live_english_sentence(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "en.wav")
            result = long_narration.synthesize_long(
                "Hello, this is a test of the English narrator.",
                out, gap=0.0, lang="en")
            self.assertTrue(os.path.isfile(out))
            self.assertEqual(len(result["chunks"]), 1)
            self.assertGreater(result["duration"], 0)


if __name__ == "__main__":
    unittest.main()
