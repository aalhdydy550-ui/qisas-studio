#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات التثبيت الكسول — جولة v0.1.41 (بند د).

ensure() تُحاكى دائمًا (بلا أي تثبيت حقيقي): يُختبر أن
الوحدات تستدعيها عند الحاجة، وأن الفشل الأصلي يبقى كما هو.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import moviepy_fx
from lib import ref_analyzer
from lib import whisper_captions


class TestLazyEnsure(unittest.TestCase):
    def test_transcribe_via_venv_ensures_before_missing_error(self):
        with mock.patch("lib.ensure_env.ensure",
                        return_value=(False, "تعذّر")) as ensure:
            with mock.patch.object(ref_analyzer, "VENV_PYTHON",
                                   "/nonexistent/venv/bin/python"):
                with self.assertRaises(ref_analyzer.RefError):
                    ref_analyzer.transcribe_via_venv("/tmp/x.wav")
            ensure.assert_called_once_with("whisper")

    def test_require_moviepy_ensures_on_import_error(self):
        with mock.patch("lib.ensure_env.ensure",
                        return_value=(True, "جاهز")) as ensure:
            with mock.patch.dict(sys.modules, {"moviepy": None}):
                with self.assertRaises(moviepy_fx.MoviePyFxError):
                    moviepy_fx._require_moviepy()
            ensure.assert_called_once_with("moviepy")

    def test_transcribe_words_ensures_on_import_error(self):
        with mock.patch("lib.ensure_env.ensure",
                        return_value=(True, "جاهز")) as ensure:
            with mock.patch.dict(sys.modules, {"faster_whisper": None}):
                with self.assertRaises(whisper_captions.WhisperError):
                    whisper_captions.transcribe_words("/tmp/x.wav")
            ensure.assert_called_once_with("whisper")


if __name__ == "__main__":
    unittest.main()
