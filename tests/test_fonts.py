#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات الخط العربي المثبّت في الشجرة (docs/fonts.md).

تعمل بـ `env -u PYTHONNOUSERSITE python3 -m unittest tests.test_fonts -v`
من جذر الشجرة. تتحقق من: وجود خط الشجرة ومطابقته للمواصفات
(Noto Naskh Arabic Bold v2.021 من google/fonts، مقسّم فرعيًا)،
وتفضيله في lib.moviepy_fx مع الرجوع لخط النظام عند غيابه،
وبقاء كابشنات ASS على اسم العائلة وخط النظام (قيد موثّق).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import capite_captions, moviepy_fx

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TREE_FONT = os.path.join(STUDIO_ROOT, "assets", "fonts",
                         "NotoNaskhArabic-Bold-subset.ttf")
SYSTEM_FONT = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"

try:
    from fontTools.ttLib import TTFont
except ImportError:  # pragma: no cover
    TTFont = None


@unittest.skipUnless(TTFont is not None, "fontTools غير مثبّت")
class TestTreeFont(unittest.TestCase):
    def test_tree_font_exists_and_is_smaller_than_variable_source(self):
        self.assertTrue(os.path.isfile(TREE_FONT),
                        "خط الشجرة مفقود: %s" % TREE_FONT)
        # الملف المُقسَّم أصغر من المتغير الأصلي (307,592 بايت).
        self.assertLess(os.path.getsize(TREE_FONT), 307592)
        self.assertGreater(os.path.getsize(TREE_FONT), 50000)

    def test_tree_font_identity(self):
        font = TTFont(TREE_FONT)
        try:
            self.assertEqual(font["name"].getDebugName(1),
                             "Noto Naskh Arabic")
            self.assertEqual(font["name"].getDebugName(2), "Bold")
            self.assertTrue(
                font["name"].getDebugName(5).startswith("Version 2.021"),
                font["name"].getDebugName(5))
            # مقسّم فرعيًا فعلًا: أقل glyphs من الأصل (1,719).
            self.assertLess(font["maxp"].numGlyphs, 1719)
            self.assertGreater(font["maxp"].numGlyphs, 500)
            cmap = font.getBestCmap()
            # حروف عربية مستعملة في الكابشن موجودة...
            for cp in (0x627, 0x644, 0x64A, 0x629, 0x60C, 0x61F):
                self.assertIn(cp, cmap, "U+%04X مفقود من المجموعة" % cp)
            # ...وحرف لاتيني لم يُطلب (é) غير موجود — التقسيم فعلي.
            self.assertNotIn(0xE9, cmap)
        finally:
            font.close()


class TestFontPreference(unittest.TestCase):
    def test_tree_font_preferred_when_present(self):
        self.assertTrue(os.path.isfile(moviepy_fx.TREE_FONT))
        self.assertEqual(moviepy_fx.arabic_font_path(),
                         moviepy_fx.TREE_FONT)

    def test_fallback_to_system_when_tree_missing(self):
        original = moviepy_fx.TREE_FONT
        try:
            moviepy_fx.TREE_FONT = os.path.join(
                os.path.dirname(original), "no-such-font.ttf")
            self.assertEqual(moviepy_fx.arabic_font_path(),
                             moviepy_fx.SYSTEM_FONT)
        finally:
            moviepy_fx.TREE_FONT = original

    def test_system_font_constant_unchanged(self):
        # ARABIC_FONT يبقى مسار النظام لتوافق المتصلين القدامى.
        self.assertEqual(moviepy_fx.ARABIC_FONT, SYSTEM_FONT)
        self.assertEqual(moviepy_fx.SYSTEM_FONT, SYSTEM_FONT)

    def test_render_with_default_font(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest("Pillow غير مثبّت في بايثون الحالي")
        img = moviepy_fx.render_arabic_text_image("عنزة صغيرة")
        self.assertGreater(img.size[0], 0)
        self.assertGreater(img.size[1], 0)

    def test_render_with_explicit_system_font_still_works(self):
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            self.skipTest("Pillow غير مثبّت في بايثون الحالي")
        img = moviepy_fx.render_arabic_text_image(
            "عنزة صغيرة", font_path=SYSTEM_FONT)
        self.assertGreater(img.size[0], 0)


class TestAssFontConstraint(unittest.TestCase):
    def test_ass_uses_family_name_not_tree_path(self):
        # ASS يحلّ الخط عبر fontconfig باسم العائلة — بلا مسار ملف.
        self.assertEqual(capite_captions.ASS_FONT_FAMILY,
                         "Noto Naskh Arabic")
        self.assertNotIn("/", capite_captions.ASS_FONT_FAMILY)

    def test_ass_header_still_names_system_family(self):
        words = [{"w": "قصة", "start": 0.0, "end": 0.5},
                 {"w": "وعبرة", "start": 0.6, "end": 1.2}]
        ass_text, _groups = capite_captions.words_to_karaoke_ass(words)
        self.assertIn("Noto Naskh Arabic", ass_text)
        self.assertNotIn("subset", ass_text)
        self.assertNotIn("assets/fonts", ass_text)


if __name__ == "__main__":
    unittest.main()
