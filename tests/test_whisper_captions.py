#!/usr/bin/env python3
"""اختبارات استيراد SRT إلى ASS (lib.whisper_captions — v0.1.36).

تعمل بـ `python3 -m unittest tests.test_whisper_captions -v` من
مجلد studio. بلا faster-whisper وبلا شبكة — تختبر التحليل
والتحويل فقط.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import whisper_captions as wc

SRT_SAMPLE = """1
00:00:00,500 --> 00:00:04,200
عائشة الأرملة باعت كل ما تملك

2
00:00:05,000 --> 00:00:09,750
وفي ليلة ظلماء
طرق بابها رجل غريب

3
00:00:10,000 --> 00:00:12,500
النهاية أغرب مما تتخيل
"""


class TestParseSrt(unittest.TestCase):
    def test_three_entries(self):
        phrases, skipped = wc.parse_srt(SRT_SAMPLE)
        self.assertEqual(len(phrases), 3)
        self.assertEqual(skipped, 0)
        self.assertAlmostEqual(phrases[0]["start"], 0.5)
        self.assertAlmostEqual(phrases[0]["end"], 4.2)
        self.assertEqual(phrases[0]["text"],
                         "عائشة الأرملة باعت كل ما تملك")
        # سطور النص المتعددة تُدمج بمسافة في عبارة واحدة
        self.assertEqual(phrases[1]["text"],
                         "وفي ليلة ظلماء طرق بابها رجل غريب")

    def test_crlf_and_dot_separator(self):
        text = ("1\r\n00:00:01.000 --> 00:00:02.500\r\nنص أول\r\n\r\n"
                "2\r\n00:00:03,000 --> 00:00:04,000\r\nنص ثانٍ\r\n")
        phrases, skipped = wc.parse_srt(text)
        self.assertEqual(len(phrases), 2)
        self.assertEqual(skipped, 0)
        self.assertAlmostEqual(phrases[0]["start"], 1.0)
        self.assertAlmostEqual(phrases[0]["end"], 2.5)

    def test_malformed_blocks_skipped(self):
        text = ("1\n00:00:01,000 --> 00:00:02,000\nصالحة\n\n"
                "بلا زمن هنا\n\n"
                "3\n99:99:99,999 --> 00:00:02,000\nزمن تالف\n\n"
                "4\n00:00:05,000 --> 00:00:04,000\nنهاية قبل البداية\n\n")
        phrases, skipped = wc.parse_srt(text)
        self.assertEqual(len(phrases), 1)
        self.assertEqual(phrases[0]["text"], "صالحة")
        self.assertEqual(skipped, 3)

    def test_empty_text(self):
        phrases, skipped = wc.parse_srt("")
        self.assertEqual(phrases, [])
        self.assertEqual(skipped, 0)


class TestSrtToAss(unittest.TestCase):
    def test_writes_ass_with_studio_style(self):
        tmp = tempfile.mkdtemp(prefix="srt-test-")
        srt_path = os.path.join(tmp, "in.srt")
        ass_path = os.path.join(tmp, "out.ass")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(SRT_SAMPLE)
        phrases, skipped = wc.srt_to_ass(srt_path, ass_path)
        self.assertEqual(len(phrases), 3)
        self.assertEqual(skipped, 0)
        with open(ass_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Noto Naskh Arabic", content)
        self.assertIn("PlayResX: 720", content)
        self.assertIn("PlayResY: 1280", content)
        self.assertIn("0:00:00.50", content)
        self.assertIn("0:00:04.20", content)
        self.assertIn("عائشة الأرملة باعت كل ما تملك", content)
        self.assertNotIn("\ufffd", content)

    def test_missing_file(self):
        with self.assertRaises(wc.WhisperError):
            wc.srt_to_ass("/tmp/no-such.srt", "/tmp/out.ass")

    def test_no_valid_entries(self):
        tmp = tempfile.mkdtemp(prefix="srt-test-")
        srt_path = os.path.join(tmp, "empty.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("بلا أي كتلة زمنية\n")
        with self.assertRaises(wc.WhisperError):
            wc.srt_to_ass(srt_path, os.path.join(tmp, "out.ass"))


if __name__ == "__main__":
    unittest.main()
