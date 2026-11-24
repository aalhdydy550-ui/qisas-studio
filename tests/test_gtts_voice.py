#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات الصوت الثاني الاختياري gTTS (lib.gtts_voice).

تعمل بـ `python3 -m unittest discover -s tests -v`.
الاختبار الحقيقي (test_real_gtts_synthesis) يحتاج شبكة إلى
translate.google.com ويُتخطى تلقائيًا إن تعذر الوصول.
باقي الاختبارات بلا شبكة.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import gtts_voice


class TestGttsVenv(unittest.TestCase):
    def test_venv_python_path(self):
        # مسار مفسّر بيئة gTTS ثابت ومعروف — لا يُرفع استثناء
        # سواء وُجدت البيئة أم لا.
        py = gtts_voice.GTTS_VENV_PYTHON
        self.assertTrue(py.endswith(".venv-gtts/bin/python"))

    def test_convert_mp3_to_wav_missing_file(self):
        tmp = tempfile.TemporaryDirectory()
        out = os.path.join(tmp.name, "x.wav")
        with self.assertRaises(gtts_voice.GttsError):
            gtts_voice.convert_mp3_to_wav(
                os.path.join(tmp.name, "nope.mp3"), out)
        tmp.cleanup()


class TestGttsReal(unittest.TestCase):
    def test_real_gtts_synthesis(self):
        """تركيب حقيقي: نص عربي قصير → WAV صالح.

        يُتخطى إن غابت بيئة gTTS أو تعذرت الشبكة.
        """
        from lib import long_narration
        if not os.path.isfile(gtts_voice.GTTS_VENV_PYTHON):
            self.skipTest("بيئة gTTS (.venv-gtts) غير موجودة")
        tmp = tempfile.TemporaryDirectory()
        out = os.path.join(tmp.name, "gtts-test.wav")
        try:
            gtts_voice.synthesize_gtts_chunk("السلام عليكم ورحمة الله", out)
        except gtts_voice.GttsError as e:
            self.skipTest("تعذّر gTTS من هذا الجهاز: %s" % e)
        self.assertTrue(os.path.isfile(out))
        self.assertGreater(os.path.getsize(out), 5000)
        dur = long_narration.probe_duration(out)
        self.assertGreater(dur, 0.5)
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
