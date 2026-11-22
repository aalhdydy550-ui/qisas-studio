#!/usr/bin/env python3
"""اختبارات تدقيق تشكيل الكابشن العربي (lib.ass_shaping).

تعمل بـ `python3 -m unittest discover -s tests -v`.
الكابشنات الحقيقية تُقرأ فقط (بلا تعديل) من
~/workspace/videos/subs/؛ والملفات المعطوبة في ملفات مؤقتة.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import ass_shaping

SUBS_DIR = os.path.expanduser("~/workspace/videos/subs")
REAL_FILES = ["aisha2-scene%d.ass" % n for n in range(1, 7)] + \
             ["najjar-scene%d.ass" % n for n in range(1, 7)]

ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Naskh Arabic,46,&H00FFFFFF,&H000000FF,&H80000000,&H80000000,1,0,0,0,100,100,0,0,1,2.5,0,2,40,40,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ass_file(directory, name, dialogue_lines):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(ASS_HEAD)
        for i, text in enumerate(dialogue_lines):
            f.write("Dialogue: 0,0:00:0%d.00,0:00:0%d.00,Default,,0,0,0,,%s\n"
                    % (i, i + 1, text))
    return path


class TestRealCaptions(unittest.TestCase):
    def test_real_aisha2_and_najjar_pass(self):
        """الكابشنات الحقيقية (12 ملفًا) تمرّ بلا مشاكل تشكيل."""
        total_lines = 0
        for name in REAL_FILES:
            res = ass_shaping.audit_ass_file(
                os.path.join(SUBS_DIR, name))
            self.assertTrue(res["ok"], "%s: %s" % (name, res["issues"]))
            self.assertEqual(res["files_checked"], 1)
            self.assertGreater(res["lines_checked"], 0)
            total_lines += res["lines_checked"]
        self.assertEqual(total_lines, 30)

    def test_real_dir_audit(self):
        """تدقيق مجلد فيه نسخ الكابشنات الحقيقية الـ12 فقط."""
        tmp = tempfile.mkdtemp()
        try:
            for name in REAL_FILES:
                shutil.copy(os.path.join(SUBS_DIR, name),
                            os.path.join(tmp, name))
            res = ass_shaping.audit_ass_dir(tmp)
            self.assertTrue(res["ok"], res["issues"])
            self.assertEqual(res["files_checked"], 12)
            self.assertEqual(res["lines_checked"], 30)
        finally:
            shutil.rmtree(tmp)


class TestCorruptedCaptions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _audit(self, name, lines):
        path = _ass_file(self.tmp, name, lines)
        return ass_shaping.audit_ass_file(path)

    def test_replacement_char_detected(self):
        res = self._audit("bad-fffd.ass",
                          ["قصة حقيقية عن رجل � ضاع منه كل شيء."])
        self.assertFalse(res["ok"])
        self.assertEqual(res["issues"][0]["kind"], "replacement_char")

    def test_presentation_form_detected(self):
        # U+FEB5 حرف مشكّل مسبقًا (شين معزولة) — لا ترتيب منطقي.
        res = self._audit("bad-pres.ass", ["ﻵ قصة عن رجل فقير."])
        self.assertFalse(res["ok"])
        kinds = [i["kind"] for i in res["issues"]]
        self.assertIn("presentation_form", kinds)

    def test_bidi_start_digit_detected(self):
        res = self._audit("bad-bidi.ass",
                          ["3 قصص عن رجل فقير غيّرت حياته."])
        self.assertFalse(res["ok"])
        kinds = [i["kind"] for i in res["issues"]]
        self.assertIn("bidi_start", kinds)

    def test_bidi_start_latin_detected(self):
        res = self._audit("bad-bidi-latin.ass",
                          ["A قصة عن رجل فقير."])
        self.assertFalse(res["ok"])
        kinds = [i["kind"] for i in res["issues"]]
        self.assertIn("bidi_start", kinds)

    def test_long_line_detected(self):
        long_line = ("كان يا ما كان في قديم الزمان رجل فقير يعيش في قرية "
                     "بعيدة جدًا على أطراف الصحراء.")
        self.assertGreater(len(long_line), 70)
        res = self._audit("bad-long.ass", [long_line])
        self.assertFalse(res["ok"])
        kinds = [i["kind"] for i in res["issues"]]
        self.assertIn("wrap_long_line", kinds)
        detail = next(i["detail"] for i in res["issues"]
                      if i["kind"] == "wrap_long_line")
        self.assertIn("70", detail)

    def test_empty_visible_text_detected(self):
        res = self._audit("bad-empty.ass", ["{\\pos(360,640)}"])
        self.assertFalse(res["ok"])
        kinds = [i["kind"] for i in res["issues"]]
        self.assertIn("empty_text", kinds)

    def test_clean_line_passes(self):
        res = self._audit("good.ass",
                          ["كان عم حسن نجارًا فقيرًا يصلح أبواب البيوت."])
        self.assertTrue(res["ok"])
        self.assertEqual(res["issues"], [])

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            ass_shaping.audit_ass_file(
                os.path.join(self.tmp, "nope.ass"))


if __name__ == "__main__":
    unittest.main()
