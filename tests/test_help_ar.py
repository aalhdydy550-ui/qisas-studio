#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات المساعدة العربية (lib.help_ar).

تعمل بـ `python3 -m unittest discover -s tests -v`.
تتحقق فقط من أن نص المساعدة يغطي كل الأوامر الرئيسية
بالعربية مع مثال لكل أمر — بلا شبكة.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import help_ar


class TestHelpAr(unittest.TestCase):
    def test_text_covers_main_commands(self):
        text = help_ar.help_text()
        for cmd in ("run", "status", "doctor", "demo", "publish",
                    "queue add", "long-video", "long-narration",
                    "analyze", "thumbnail", "quote-cards", "assemble",
                    "client-run", "help-ar", "init", "check"):
            self.assertIn(cmd, text, "الأمر %s غائب من المساعدة" % cmd)

    def test_text_is_arabic_and_has_examples(self):
        text = help_ar.help_text()
        self.assertIn("python3 studio.py", text)
        self.assertIn("مثال:", text)
        # على الأقل عنوان عربي لكل أمر.
        self.assertIn("أوامر studio", text)
        self.assertIn("ملاحظات:", text)

    def test_every_command_has_description_and_example(self):
        for name, desc, example in help_ar.COMMANDS:
            self.assertTrue(name, "أمر بلا اسم")
            self.assertTrue(desc, "الأمر %s بلا وصف" % name)
            self.assertTrue(example, "الأمر %s بلا مثال" % name)
            self.assertIn("studio.py", example)

    def test_no_leading_numeral_in_examples(self):
        # قاعدة الفيديو: الهوك بلا رقم بادئ — والأمثلة كذلك.
        for name, desc, example in help_ar.COMMANDS:
            self.assertFalse(example.lstrip().startswith(
                ("1", "2", "3", "4", "5")))


if __name__ == "__main__":
    unittest.main()
