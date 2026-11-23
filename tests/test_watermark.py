"""Tests for lib.watermark: logo overlay + quote-cards append + generation."""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import watermark

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# جولة v0.1.41 (إصلاح CI): بطاقات الاقتباس تُرسم بخط
# Noto Naskh Arabic (make_quote_cards.py) المثبّت محليًا فقط؛
# في CI يثبّته سير العمل (fonts-noto-core) والحراسة دفاع
# إضافي إن غاب (نمط test_ci_skips).
_ARABIC_FONT = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"
_HAS_ARABIC_FONT = os.path.isfile(_ARABIC_FONT)


def _make_test_video(path, seconds=2):
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=size=720x1280:rate=30:duration=%d" % seconds,
         "-f", "lavfi", "-i", "sine=frequency=440:duration=%d" % seconds,
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", path],
        check=True, timeout=60)


class TestWatermark(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wm-test-")
        self.video = os.path.join(self.tmp, "v.mp4")
        _make_test_video(self.video, seconds=2)

    def test_apply_watermark(self):
        out = os.path.join(self.tmp, "v-wm.mp4")
        watermark.apply_watermark(self.video, out)
        self.assertTrue(os.path.isfile(out))
        self.assertGreater(os.path.getsize(out), 1000)
        self.assertEqual(watermark.probe_size(out), (720, 1280))
        self.assertAlmostEqual(watermark.probe_duration(out), 2.0, delta=0.3)

    def test_apply_watermark_missing_badge(self):
        with self.assertRaises(watermark.WatermarkError):
            watermark.apply_watermark(
                self.video, os.path.join(self.tmp, "x.mp4"),
                badge=os.path.join(self.tmp, "nope.png"))

    @unittest.skipUnless(
        _HAS_ARABIC_FONT,
        "خط Noto Naskh Arabic غائب — بيئة CI بلا fonts-noto-core")
    def test_append_quote_cards(self):
        cards_dir = os.path.join(self.tmp, "cards")
        cards = watermark.generate_quote_cards(
            "عبرة اختبار قصيرة.", "حكمة اختبار قصيرة.",
            "موعظة اختبار قصيرة.", "", cards_dir)
        self.assertEqual(len(cards), 3)
        for c in cards:
            self.assertTrue(os.path.isfile(c))
        out = os.path.join(self.tmp, "v-cards.mp4")
        watermark.append_quote_cards(self.video, cards, out)
        self.assertTrue(os.path.isfile(out))
        # 2s video + 3 cards x 3s = ~11s
        self.assertAlmostEqual(watermark.probe_duration(out), 11.0, delta=0.6)
        self.assertEqual(watermark.probe_size(out), (720, 1280))

    @unittest.skipUnless(
        _HAS_ARABIC_FONT,
        "خط Noto Naskh Arabic غائب — بيئة CI بلا fonts-noto-core")
    def test_generate_quote_cards_files(self):
        cards_dir = os.path.join(self.tmp, "cards2")
        cards = watermark.generate_quote_cards(
            "عبرة.", "حكمة.", "موعظة.", "سورة الإسراء: آية 23", cards_dir)
        self.assertEqual(
            [os.path.basename(c) for c in cards],
            ["ibra.png", "hikma.png", "mawiza.png"])
        for c in cards:
            self.assertTrue(os.path.isfile(c))

    @unittest.skipUnless(
        _HAS_ARABIC_FONT,
        "خط Noto Naskh Arabic غائب — بيئة CI بلا fonts-noto-core")
    def test_find_cards(self):
        cards_dir = os.path.join(self.tmp, "cards3")
        made = watermark.generate_quote_cards(
            "عبرة.", "حكمة.", "موعظة.", "", cards_dir)
        self.assertEqual(watermark.find_cards(cards_dir), made)

    def test_find_cards_missing(self):
        empty = os.path.join(self.tmp, "empty")
        os.makedirs(empty)
        with self.assertRaises(watermark.WatermarkError):
            watermark.find_cards(empty)


class TestAssembleLogoDefault(unittest.TestCase):
    """خط النشر الخاص بالمستخدم يحتفظ بالشعار افتراضيًا
    (قاعدة 2026-11-22 تقابلها: طلبات العملاء بلا شعار صفحة
    أبدًا — انظر TestClientRunLogo في test_orders_payment.py).

    بلا ffmpeg هنا: فحص توقيع الدالة فقط، بلا فيديو.
    """

    def test_assemble_defaults_to_watermark_on(self):
        import inspect

        import studio

        params = inspect.signature(studio.cmd_assemble).parameters
        self.assertIn("watermark_on", params)
        self.assertTrue(params["watermark_on"].default)


if __name__ == "__main__":
    unittest.main()
