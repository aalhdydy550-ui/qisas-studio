#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات عنوان الهوك المكتوب في أول 3 ثوانٍ (lib.hook_title).

تعمل بـ `python3 -m unittest tests.test_hook_title -v` من مجلد
studio. الوسائط تُولَّد محليًا بـffmpeg (بلا شبكة): مقطع
تركيبي 10 ثوانٍ 720×1280 بخلفية داكنة موحدة + نغمة sine،
فأي بكسل ساطع في إطار هو نص العنوان نفسه.
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import check as check_lib
from lib import hook_title

try:
    from PIL import Image
    import numpy as np
    _HAS_IMG = True
except ImportError:  # pragma: no cover
    _HAS_IMG = False


def _make_video(path, seconds=10, size="720x1280"):
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i",
                    "color=c=0x2a2a2a:s=%s:r=30:d=%s" % (size, seconds),
                    "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=48000:duration=%s"
                    % seconds,
                    "-t", str(seconds), "-c:v", "libx264", "-preset",
                    "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", path],
                   check=True, timeout=300, capture_output=True,
                   text=True)


def _bright_pixels(frame_path, y0, y1):
    """عدد البكسلات الساطعة (>200) في شريط y0–y1 من إطار."""
    a = np.asarray(Image.open(frame_path).convert("L"), dtype=float)
    return int((a[y0:y1, :] > 200).sum())


class TestSpecGeometry(unittest.TestCase):
    def test_default_spec_stays_in_middle_band(self):
        spec = hook_title.hook_title_spec("فجأة مات الملك")
        # الثلث العلوي المحظور: 1280/3 (من lib.check.QA_TOP_FRACTION).
        self.assertAlmostEqual(spec["top_limit"], 1280.0 / 3.0,
                               places=2)
        # منطقة الكابشنات: 1280 − MarginV ‏64 − سطرين × 52
        # (من نمط lib.whisper_captions.ass_header).
        self.assertEqual(spec["caption_zone_top"], 1112)
        self.assertGreaterEqual(spec["y0"], spec["top_limit"])
        self.assertLessEqual(spec["y1"], spec["caption_zone_top"])
        self.assertEqual(spec["start"], 0.0)
        self.assertEqual(spec["end"], 3.0)
        self.assertEqual(spec["fontsize"], 58)
        self.assertEqual(spec["font"], "Noto Naskh Arabic")
        self.assertEqual(len(spec["lines"]), 1)

    def test_one_line_is_vertically_centered_in_middle_band(self):
        spec = hook_title.hook_title_spec("فجأة مات الملك")
        middle = (spec["top_limit"] + spec["caption_zone_top"]) / 2.0
        center = (spec["y0"] + spec["y1"]) / 2.0
        self.assertAlmostEqual(center, middle, delta=1.0)

    def test_long_hook_wraps_to_two_lines_within_width(self):
        spec = hook_title.hook_title_spec(
            "فجأة انقلب كل شيء في ليلة واحدة")
        self.assertEqual(len(spec["lines"]), 2)
        # 720 − هامشي 5% = 648 بكسل ÷ (0.58 × 58) ≈ 19 حرفًا.
        self.assertEqual(spec["max_chars_per_line"], 19)
        for ln in spec["lines"]:
            self.assertLessEqual(len(ln), 19)
        self.assertGreaterEqual(spec["y0"], spec["top_limit"])
        self.assertLessEqual(spec["y1"], spec["caption_zone_top"])

    def test_custom_dimensions_keep_invariants(self):
        spec = hook_title.hook_title_spec("فجأة مات الملك",
                                               width=1080, height=1920)
        self.assertAlmostEqual(spec["top_limit"], 640.0, places=2)
        self.assertEqual(spec["caption_zone_top"], 1752)
        self.assertGreaterEqual(spec["y0"], spec["top_limit"])
        self.assertLessEqual(spec["y1"], spec["caption_zone_top"])
        self.assertEqual(spec["max_chars_per_line"], 28)

    def test_percent_is_normalized_to_arabic_sign(self):
        spec = hook_title.hook_title_spec("خصم 50% اليوم فقط!")
        self.assertIn("%", spec["text"])
        self.assertNotIn("%", spec["render_text"])
        self.assertIn("٪", spec["render_text"])
        self.assertIn("٪", " ".join(spec["lines"]))

    def test_empty_title_raises(self):
        with self.assertRaises(hook_title.HookTitleError):
            hook_title.hook_title_spec("")
        with self.assertRaises(hook_title.HookTitleError):
            hook_title.hook_title_spec("   ")

    def test_tiny_frame_raises(self):
        # إطار 200 بكسل: النطاق الأوسط (67–32) أضيق من كتلة
        # العنوان نفسها — لا موضع سليم، فيرفع بدل وضع نص خاطئ.
        with self.assertRaises(hook_title.HookTitleError):
            hook_title.hook_title_spec("فجأة مات الملك",
                                            width=720, height=200)

    def test_bad_dimensions_raise(self):
        with self.assertRaises(hook_title.HookTitleError):
            hook_title.hook_title_spec("فجأة", width=0, height=1280)


class TestEscaping(unittest.TestCase):
    def test_plain_text_unchanged(self):
        self.assertEqual(
            hook_title.escape_drawtext_text("مرحبا"), "مرحبا")

    def test_colon_is_escaped(self):
        # `:` تقسّم خيارات الفلتر حتى داخل الاقتباسات.
        self.assertEqual(
            hook_title.escape_drawtext_text("a:b"), "a\\:b")

    def test_percent_is_escaped(self):
        self.assertEqual(
            hook_title.escape_drawtext_text("100%"), "100\\\\%")

    def test_quote_is_normalized_to_arabic_quotes(self):
        # `'` ASCII يستحيل هروبها داخل text='...' — تُطبَّع
        # إلى «» بالتناوب كملاذ وحيد (مثبّت تجريبيًا).
        self.assertEqual(
            hook_title.escape_drawtext_text("a'b"), "a»b")

    def test_quote_normalization_pairs_in_spec(self):
        spec = hook_title.hook_title_spec("قال 'مرحبا' وانتهى")
        self.assertNotIn("'", spec["render_text"])
        self.assertIn("«مرحبا»", spec["render_text"])
        self.assertIn("'", spec["text"])

    def test_backslash_is_escaped(self):
        self.assertEqual(
            hook_title.escape_drawtext_text("a\\b"), "a\\\\\\\\b")

    def test_filter_has_one_drawtext_per_line_and_timing(self):
        spec = hook_title.hook_title_spec(
            "فجأة انقلب كل شيء في ليلة واحدة")
        filt = hook_title.build_drawtext_filter(spec)
        self.assertEqual(filt.count("drawtext="), 2)
        self.assertEqual(filt.count("enable='between(t,0.0,3.0)'"), 2)
        self.assertIn("fontsize=58", filt)
        self.assertIn("fontcolor=white", filt)
        self.assertIn("bordercolor=black", filt)
        self.assertIn("x=(w-text_w)/2", filt)
        self.assertIn("fontfile=/usr/share/fonts/truetype/noto/"
                      "NotoNaskhArabic-Bold.ttf", filt)

    def test_deterministic_spec_and_filter(self):
        first = hook_title.hook_title_spec("فجأة مات الملك")
        second = hook_title.hook_title_spec("فجأة مات الملك")
        self.assertEqual(first, second)
        self.assertEqual(hook_title.build_drawtext_filter(first),
                         hook_title.build_drawtext_filter(second))

    def test_validate_spec_catches_top_third(self):
        spec = hook_title.hook_title_spec("فجأة مات الملك")
        bad = dict(spec, y0=100, y1=158)
        problems = hook_title.validate_spec(bad)
        self.assertTrue(any("الثلث العلوي" in p for p in problems))

    def test_validate_spec_catches_caption_overlap(self):
        spec = hook_title.hook_title_spec("فجأة مات الملك")
        bad = dict(spec, y0=1100, y1=1158)
        problems = hook_title.validate_spec(bad)
        self.assertTrue(any("الكابشنات" in p for p in problems))

    def test_validate_spec_catches_wrong_timing(self):
        spec = hook_title.hook_title_spec("فجأة مات الملك")
        bad = dict(spec, end=5.0)
        problems = hook_title.validate_spec(bad)
        self.assertTrue(any("3.0" in p for p in problems))

    def test_build_filter_rejects_invalid_spec(self):
        spec = hook_title.hook_title_spec("فجأة مات الملك")
        bad = dict(spec, end=5.0)
        with self.assertRaises(hook_title.HookTitleError):
            hook_title.build_drawtext_filter(bad)


class TestApplyFFmpeg(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="hook-title-")
        cls.video = os.path.join(cls.tmp, "short.mp4")
        _make_video(cls.video)

    def test_applies_and_preserves_duration_size_audio(self):
        out = os.path.join(self.tmp, "titled.mp4")
        hook_title.apply_hook_title(self.video, "فجأة: مات الملك",
                                    out)
        self.assertTrue(os.path.isfile(out))
        info = check_lib.probe(out)
        self.assertEqual((info["width"], info["height"]),
                         (720, 1280))
        self.assertAlmostEqual(info["duration"], 10.0, delta=0.6)
        self.assertTrue(info["has_audio"])

    @unittest.skipUnless(_HAS_IMG, "PIL/numpy غير متاحتين")
    def test_title_visible_first_3s_only(self):
        out = os.path.join(self.tmp, "timed.mp4")
        hook_title.apply_hook_title(self.video, "فجأة مات الملك",
                                    out)
        early = os.path.join(self.tmp, "frame-early.png")
        late = os.path.join(self.tmp, "frame-late.png")
        check_lib.extract_frame(out, 1.5, early)
        check_lib.extract_frame(out, 5.0, late)
        # النطاق الأوسط: y ‏427–1112؛ والثلث العلوي: y ‏0–427.
        self.assertGreater(_bright_pixels(early, 427, 1112), 200)
        self.assertEqual(_bright_pixels(early, 0, 427), 0)
        self.assertEqual(_bright_pixels(late, 427, 1112), 0)

    @unittest.skipUnless(_HAS_IMG, "PIL/numpy غير متاحتين")
    def test_punctuation_hook_renders(self):
        # `%` و`:` و`'` معًا في نص عربي: أصعب حالة هروب
        # (إعادة ترتيب fribidi كانت تُسقط النص قبل التطبيع).
        out = os.path.join(self.tmp, "punct.mp4")
        hook_title.apply_hook_title(
            self.video, "نسبة 100%: قال 'مرحبا'", out)
        self.assertTrue(os.path.isfile(out))
        frame = os.path.join(self.tmp, "frame-punct.png")
        check_lib.extract_frame(out, 1.5, frame)
        self.assertGreater(_bright_pixels(frame, 427, 1112), 200)

    def test_missing_file_raises(self):
        with self.assertRaises(hook_title.HookTitleError):
            hook_title.apply_hook_title(
                os.path.join(self.tmp, "nope.mp4"), "فجأة",
                os.path.join(self.tmp, "out.mp4"))

    def test_empty_title_raises(self):
        with self.assertRaises(hook_title.HookTitleError):
            hook_title.apply_hook_title(
                self.video, "  ", os.path.join(self.tmp, "out2.mp4"))


if __name__ == "__main__":
    unittest.main()
