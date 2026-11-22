#!/usr/bin/env python3
"""اختبار انحدار للقاعدة الدائمة (2026-11-22): كل نصوص الشاشة في
الفيديو أسفل فقط، ولا نص أعلى الشاشة أبدًا.

يبني مشاريع كل خلفيات التجميع الأربع من بيان واحد ويتحقق أن لا
موضع "top" في أيٍّ منها، وأن الهوك يجلس أسفل الشاشة فوق
الكابشنات. يعمل بـ `python3 -m unittest
tests.test_text_bottom_only -v` من مجلد studio — بلا ريندر وبلا
شبكة (دوال بناء نقية + فحص إعداد Concat الثابت).
"""
import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import concat_mcp
from lib import headless_stage
from lib import mlt_stage
from lib import openreel_render as or_lib

MANIFEST = {
    "project": "test-story",
    "sequence": ["scene1.jpg", "scene2.jpg"],
    "image_clip_seconds": 5,
    "narration_duration": 12.0,
    "phrases": [
        {"text": "عبارة أولى", "start": 0.0, "end": 4.0},
        {"text": "عبارة ثانية", "start": 5.0, "end": 9.0},
    ],
}
VIDEO = {"width": 720, "height": 1280, "fps": 30}


class TestBottomOnlyRule(unittest.TestCase):
    def test_openreel_no_top_hook_below(self):
        project = or_lib.build_project(MANIFEST, "هوك صادم",
                                       "/tmp/assets", VIDEO)
        texts = project["texts"]
        self.assertFalse(any(t["position"] == "top" for t in texts))
        hook = texts[0]
        self.assertEqual(hook["position"], "bottom")
        # إحداثيات صريحة: حافة الهوك السفلى فوق أسفل الإطار،
        # أي في النصف السفلي حتمًا وفوق نطاق الكابشن.
        self.assertGreater(hook["y"], VIDEO["height"] // 2)
        self.assertEqual(hook["x"], VIDEO["width"] // 2)
        caps = texts[1:]
        self.assertTrue(all(t["position"] == "bottom" for t in caps))

    def test_headless_no_top_hook_above_captions(self):
        project = headless_stage.build_project(MANIFEST, "هوك تجريبي",
                                               "/tmp/assets", VIDEO)
        texts = [t for t in project["tracks"] if t["type"] == "text"]
        self.assertFalse(any(t["position"] == "top" for t in texts))
        hook = texts[0]
        self.assertEqual(hook["position"], "above")
        self.assertEqual((hook["start"], hook["end"]), (0, 4.0))
        caps = texts[1:]
        self.assertTrue(all(t["position"] == "bottom" for t in caps))

    def test_mlt_hook_geometry_in_lower_half(self):
        xml_text = mlt_stage.build_mlt(MANIFEST, "هوك صادم",
                                       "/tmp/assets", dict(VIDEO))
        root = ET.fromstring(xml_text)
        hook = root.find("tractor/filter[@id='filter-hook']")
        x, y, w, h = (int(v) for v in hook.find(
            "property[@name='geometry']").text.split())
        # صندوق الهوك كاملًا في النصف السفلي وفوق صندوق العبارات.
        self.assertEqual((x, w), (0, VIDEO["width"]))
        self.assertGreater(y, VIDEO["height"] // 2)
        self.assertEqual(h, 150)
        phrases = [f for f in root.findall("tractor/filter")
                   if (f.get("id") or "").startswith("filter-phrase")]
        self.assertEqual(len(phrases), 2)
        cap_y = int(phrases[0].find(
            "property[@name='geometry']").text.split()[1])
        self.assertGreater(cap_y, y + h)

    def test_concat_hook_offset_below_center(self):
        # عنوان Concat: إزاحة موجبة (أسفل المنتصف) وفوق الكابشنات
        # عند +0.35 — لا سالبة (أعلى) أبدًا.
        self.assertGreater(concat_mcp.HOOK_OFFSET_Y, 0)
        self.assertLess(concat_mcp.HOOK_OFFSET_Y, 0.35)


if __name__ == "__main__":
    unittest.main()
