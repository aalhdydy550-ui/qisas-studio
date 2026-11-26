#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات انحدار لهندسة نصوص MLT (جولة v0.1.62 — عيبا إنتاج v2).

العيبان (اكتُشفا حيًا أثناء بناء إعلان موقع الاستوديو v2،
2026-11-26؛ وكان سكريبت التجميع يرقّعهما يدويًا في ملف .mlt):
(أ) سطرا عنوان الهوك بصندوق ارتفاعه = حجم الخط (58) فيُقصّ
النص من الأعلى ويلتصق باليسار؛ (ب) العبارات تتجاهل halign
فتلتصق بالحافة اليسرى (x≈22 < هامش 36).

السبب الجذري (مثبّت بالريندر على خلفية داكنة، لا بقراءة XML):
مرشح dynamictext في MLT 7.22 يتجاهل halign تمامًا (halign
‏0/1/2 تعطي الإخراج نفسه بايتيًا، عربيًا وإنجليزيًا)، ويتجاهل
valign كذلك (ارتفاعا 150 و170 متماثلان بايتيًا) — فالتوسيط
الوحيد الذي يعمل هو التوسيط بالهندسة (قياس عرض النص بـPIL
بالخط نفسه ووضع الصندوق متمركزًا). واختبارات v0.1.59 كانت
تفحص XML فقط فانزلق العيبان — لذلك هذه الاختبارات تفحص
الهندسة المرئية (ريندر melt حقيقي + قياس بكسلات الإطار)،
وتفشل على الهندسة القديمة: سطر هوك قديم cx≈92، وعبارة قديمة
cx≈185، وهوك افتراضي قديم cx≈138 مع هامشين غير متماثلين
(26 مقابل 63).

تعمل بـ `python3 -m unittest tests.test_mlt_geometry_0162 -v`
من مجلد studio. اختبارات الريندر تُتخطى حين تغيب melt أو
xvfb-run أو ffmpeg أو PIL (نمط التخطي المتبع في
tests/test_text_bottom_only.py وtest_hook_title_concat.py)؛
وكل الملفات في مجلدات مؤقتة داخل شجرة الاختبار (بلا قراءة
خارج المستودع).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import hook_title
from lib import mlt_stage

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:  # pragma: no cover
    _HAS_PIL = False

_HAS_RENDER = bool(
    _HAS_PIL
    and shutil.which("melt")
    and shutil.which("xvfb-run")
    and shutil.which("ffmpeg"))

TITLE = "قصتك ممكن تتشاف مليون مرة"
# سطرا العنوان من المواصفة: «قصتك ممكن تتشاف» y=711،
# و«مليون مرة» y=769 — والنص مثبَّت أعلى الصندوق بإزاحة
# ثابتة (+46px عند خط 58) في MLT 7.22.
PHRASE = "عبارة قصيرة للاختبار"
MANIFEST = {
    "project": "test-geometry",
    "sequence": ["bg.jpg"],
    "image_clip_seconds": 5,
    "narration_duration": 0.0,
    "phrases": [{"text": PHRASE, "start": 0.0, "end": 4.0}],
}
VIDEO = {"width": 720, "height": 1280, "fps": 30}
FRAME_CX = 360
SAFE_MARGIN = 36


def _geometry(filt):
    return tuple(int(v) for v in filt.find(
        "property[@name='geometry']").text.split())


def _bright_bbox(frame_path, y0, y1, threshold=180):
    """صندوق البكسلات الساطعة (>threshold) في شريط y0–y1 من
    إطار: (n, min_x, max_x, center_x) — أو None بلا نص."""
    gray = Image.open(frame_path).convert("L")
    band = gray.crop((0, y0, gray.width, min(y1, gray.height)))
    bw = band.point(lambda v: 255 if v > threshold else 0)
    box = bw.getbbox()
    if not box:
        return None
    n = bw.histogram()[255]
    min_x, _, max_x, _ = box
    return n, min_x, max_x - 1, (min_x + max_x - 1) / 2.0


class TestCenteredGeometryXml(unittest.TestCase):
    def test_hook_title_lines_height_150_not_fontsize(self):
        # عيب (أ): الارتفاع القديم = حجم الخط (58) يقصّ النص.
        spec = hook_title.hook_title_spec(TITLE, 720, 1280)
        xml_text = mlt_stage.build_mlt(
            MANIFEST, TITLE, "/tmp/assets", dict(VIDEO),
            as_hook_title=True)
        root = ET.fromstring(xml_text)
        hooks = [f for f in root.findall("tractor/filter")
                 if (f.get("id") or "").startswith("filter-hook")]
        self.assertEqual(len(hooks), len(spec["lines"]))
        for filt, y in zip(hooks, spec["line_y"]):
            x, gy, w, h = _geometry(filt)
            self.assertEqual(h, 150)
            self.assertEqual(gy, y)
            # الصندوق متمركز أفقيًا: مركزه مركز الإطار.
            self.assertAlmostEqual(x + w // 2, 360, delta=1)

    def test_phrase_geometry_centered_from_measured_width(self):
        # عيب (ب): الهندسة القديمة (0, 720) تلتصق باليسار.
        xml_text = mlt_stage.build_mlt(
            MANIFEST, TITLE, "/tmp/assets", dict(VIDEO))
        root = ET.fromstring(xml_text)
        phrase = root.find("tractor/filter[@id='filter-phrase0']")
        x, y, w, h = _geometry(phrase)
        self.assertEqual((y, h), (1050, 170))
        self.assertEqual(
            (x, w), mlt_stage._centered_geometry(
                PHRASE, mlt_stage.CAPTION_FONTSIZE, 720))
        self.assertGreater(x, 0)
        self.assertAlmostEqual(x + w // 2, 360, delta=1)

    def test_default_hook_centered_when_it_fits_one_line(self):
        # الهوك الافتراضي كان ملتصقًا باليسار أيضًا (هامشا
        # عنوان 26 حرفًا: 26 يسارًا مقابل 63 يمينًا) — يُمركز
        # حين يتسع على سطر واحد.
        xml_text = mlt_stage.build_mlt(
            MANIFEST, "هوك صادم", "/tmp/assets", dict(VIDEO))
        root = ET.fromstring(xml_text)
        hook = root.find("tractor/filter[@id='filter-hook']")
        x, y, w, h = _geometry(hook)
        self.assertEqual((y, h), (860, 150))
        self.assertEqual(
            (x, w), mlt_stage._centered_geometry(
                "هوك صادم", mlt_stage.HOOK_FONTSIZE, 720))
        self.assertGreater(x, 0)
        self.assertAlmostEqual(x + w // 2, 360, delta=1)

    def test_too_wide_phrase_falls_back_to_old_geometry(self):
        # عبارة أوسع من العرض الآمن حتى وهي متمركزة مشكلة
        # طول محتوى لا عيب هندسة — ترجع للهندسة القديمة.
        long_phrase = "عبارة طويلة جدًا " * 6
        manifest = dict(MANIFEST)
        manifest["phrases"] = [{"text": long_phrase,
                                "start": 0.0, "end": 4.0}]
        xml_text = mlt_stage.build_mlt(
            manifest, TITLE, "/tmp/assets", dict(VIDEO))
        root = ET.fromstring(xml_text)
        phrase = root.find("tractor/filter[@id='filter-phrase0']")
        x, y, w, h = _geometry(phrase)
        self.assertEqual((x, w), (0, 720))

    def test_measure_fallback_never_crashes(self):
        # تعذّر القياس (خط مفقود) fail-open: بلا استثناء،
        # ويرجع None فيستخدم المتصل الهندسة القديمة.
        self.assertIsNone(mlt_stage._measure_text_width(
            "نص", 44, font_file="/nonexistent/font.ttf"))


@unittest.skipUnless(_HAS_RENDER,
                     "melt/xvfb-run/ffmpeg/PIL غير متاحة — تخطٍّ")
class TestRenderedGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = cls.tmp.name
        images = os.path.join(tmp, "images")
        os.makedirs(images)
        Image.new("RGB", (720, 1280), (30, 30, 30)).save(
            os.path.join(images, "bg.jpg"), quality=90)
        cls.frames = {}
        for label, hook_title_mode in (("hooktitle", True),
                                       ("default", False)):
            xml_text = mlt_stage.build_mlt(
                MANIFEST, TITLE, "/tmp/assets", dict(VIDEO),
                images_dir=images, as_hook_title=hook_title_mode)
            mlt_path = os.path.join(tmp, label + ".mlt")
            with open(mlt_path, "w", encoding="utf-8") as fh:
                fh.write(xml_text)
            out = os.path.join(tmp, label + ".mp4")
            mlt_stage.render_mlt(mlt_path, out)
            frame = os.path.join(tmp, label + ".png")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss",
                            "1.5", "-i", out, "-frames:v", "1",
                            frame], check=True, timeout=120)
            cls.frames[label] = frame

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_hook_title_line0_rendered_centered(self):
        # على الهندسة القديمة: cx≈92 وn≈385 (مقصوص) — هنا
        # سطر كامل متمركز.
        box = _bright_bbox(self.frames["hooktitle"], 750, 810)
        self.assertIsNotNone(box, "لا نص مرئي في شريط سطر الهوك 0")
        n, min_x, max_x, cx = box
        self.assertGreater(n, 1000)
        self.assertGreater(min_x, 100)
        self.assertAlmostEqual(cx, FRAME_CX, delta=20)

    def test_hook_title_line1_rendered_centered(self):
        # السطر القصير «مليون مرة» أظهر العيب أوضح: قديمًا
        # cx≈51 عند x=11 — هنا متمركز تمامًا.
        box = _bright_bbox(self.frames["hooktitle"], 815, 870)
        self.assertIsNotNone(box, "لا نص مرئي في شريط سطر الهوك 1")
        n, min_x, max_x, cx = box
        self.assertGreater(n, 500)
        self.assertAlmostEqual(cx, FRAME_CX, delta=20)

    def test_phrase_rendered_centered_inside_safe_margin(self):
        # قديمًا: cx≈185 وحافة يسرى x=22 < هامش 36 — هنا
        # متمركزة داخل المنطقة الآمنة.
        box = _bright_bbox(self.frames["hooktitle"], 1050, 1220)
        self.assertIsNotNone(box, "لا نص مرئي في شريط العبارة")
        n, min_x, max_x, cx = box
        self.assertGreater(n, 500)
        self.assertGreaterEqual(min_x, SAFE_MARGIN)
        self.assertLessEqual(max_x, 720 - SAFE_MARGIN)
        self.assertAlmostEqual(cx, FRAME_CX, delta=20)

    def test_default_hook_rendered_centered(self):
        # الهوك الافتراضي بالعنوان الكامل: قديمًا cx≈341
        # بهامشين غير متماثلين (26/63) — هنا متمركز.
        box = _bright_bbox(self.frames["default"], 860, 1010)
        self.assertIsNotNone(box, "لا نص مرئي في شريط الهوك")
        n, min_x, max_x, cx = box
        self.assertGreater(n, 1000)
        self.assertAlmostEqual(cx, FRAME_CX, delta=20)
        self.assertAlmostEqual(min_x - 0, 720 - max_x - 1,
                               delta=20)

    def test_old_geometry_is_measurably_left_aligned(self):
        # توصيف آلية العيب نفسها (هندسة قديمة مبنية يدويًا):
        # halign=1 مع x=0 وعرض 720 وارتفاع 58 — نص مقصوص
        # ملتصق باليسار، لا متمركز. هذا الاختبار يمر قبل
        # الإصلاح وبعده؛ فائدته تثبيت أن halign لا يوسّط.
        tmp = self.tmp.name
        mlt_path = os.path.join(tmp, "old.mlt")
        with open(mlt_path, "w", encoding="utf-8") as fh:
            fh.write(
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<mlt LC_NUMERIC="C" version="7.0" title="old" '
                'producer="main_bin">\n'
                '<profile width="720" height="1280" '
                'display_aspect_num="9" display_aspect_den="16" '
                'sample_aspect_num="1" sample_aspect_den="1" '
                'frame_rate_num="30" frame_rate_den="1" '
                'colorspace="709"/>\n'
                '<producer id="img0" in="00:00:00.000" '
                'out="00:00:04.966">'
                '<property name="resource">%s/images/bg.jpg</property>'
                '<property name="mlt_service">qimage</property>'
                '<property name="ttl">150</property></producer>\n'
                '<playlist id="playlist0">'
                '<entry producer="img0" in="00:00:00.000" '
                'out="00:00:04.966"/></playlist>\n'
                '<tractor id="timeline" title="old">'
                '<track producer="playlist0"/>\n'
                '<filter id="filter-t">'
                '<property name="argument">مليون مرة</property>'
                '<property name="geometry">0 700 720 58</property>'
                '<property name="family">Noto Naskh Arabic</property>'
                '<property name="size">58</property>'
                '<property name="weight">700</property>'
                '<property name="fgcolour">#ffffffff</property>'
                '<property name="bgcolour">#00000000</property>'
                '<property name="olcolour">#ff000000</property>'
                '<property name="outline">2</property>'
                '<property name="pad">20</property>'
                '<property name="halign">1</property>'
                '<property name="valign">1</property>'
                '<property name="mlt_service">dynamictext</property>'
                '<property name="in">00:00:00.000</property>'
                '<property name="out">00:00:04.966</property>'
                '</filter></tractor>\n'
                '<playlist id="main_bin">'
                '<entry producer="timeline" in="00:00:00.000" '
                'out="00:00:04.966"/></playlist></mlt>\n' % tmp)
        out = os.path.join(tmp, "old.mp4")
        mlt_stage.render_mlt(mlt_path, out)
        frame = os.path.join(tmp, "old.png")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "1.5",
                        "-i", out, "-frames:v", "1", frame],
                       check=True, timeout=120)
        box = _bright_bbox(frame, 700, 800)
        self.assertIsNotNone(box, "لا نص مرئي في هندسة قديمة")
        n, min_x, max_x, cx = box
        self.assertLess(cx, 200)
        self.assertLess(min_x, SAFE_MARGIN)


if __name__ == "__main__":
    unittest.main()
