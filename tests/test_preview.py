#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات صفحة معاينة الفيديو — فيديو اصطناعي قصير عبر ffmpeg."""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import check as check_lib
from lib import preview


def _make_video(path, seconds=45):
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=black:s=720x1280:d=%d" % seconds,
                    "-f", "lavfi", "-i",
                    "sine=frequency=440:d=%d" % seconds,
                    "-shortest", "-c:v", "libx264", "-c:a", "aac",
                    "-y", path], check=True, timeout=120)


class TestBuildPreview(unittest.TestCase):
    def test_preview_page_has_frames_audio_checks_caption(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "test.mp4")
            _make_video(video)
            out, result = preview.build_preview(
                video, caption="كابشن تجريبي <b>مهم</b>",
                first_comment="أول تعليق تجريبي",
                out_dir=td, title="قصة تجريبية")
            self.assertTrue(os.path.isfile(out))
            self.assertEqual(out, os.path.join(td,
                                               "قصة تجريبية-preview.html"))
            page = open(out, encoding="utf-8").read()
            self.assertIn("25%", page)
            self.assertIn("50%", page)
            self.assertIn("75%", page)
            self.assertIn("data:image/png;base64", page)
            self.assertIn("ديسيبل", page)
            self.assertIn("فحص الجودة", page)
            # الكابشن يُهرَّب ولا يحقن HTML
            self.assertIn("&lt;b&gt;مهم&lt;/b&gt;", page)
            self.assertNotIn("<b>مهم</b>", page)
            self.assertIn("كابشن تجريبي", page)
            self.assertIn("أول تعليق تجريبي", page)
            self.assertEqual(result["duration"], 45)

    def test_preview_defaults_next_to_video(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            _make_video(video, seconds=5)
            out, _result = preview.build_preview(video)
            self.assertEqual(out, os.path.join(td, "v-preview.html"))
            page = open(out, encoding="utf-8").read()
            self.assertIn("لم يُحدد كابشن بعد", page)
            self.assertIn("لم يُحدد أول تعليق بعد", page)

    def test_preview_missing_video_raises(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(check_lib.CheckError):
                preview.build_preview(os.path.join(td, "nope.mp4"))

    def test_render_html_escapes_title(self):
        result = {"path": "x.mp4", "duration": 45.0, "width": 720,
                  "height": 1280, "long": False, "passed": True,
                  "checks": [{"name": "المدة", "ok": True,
                              "detail": "45 ثانية"}]}
        page = preview.render_html(
            "x.mp4", result, [], (None, None),
            caption=None, first_comment=None,
            title="<script>alert(1)</script>")
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)


if __name__ == "__main__":
    unittest.main()
