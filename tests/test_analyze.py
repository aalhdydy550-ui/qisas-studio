#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات تحليل آخر فيديو `analyze` (lib.analyze).

تعمل بـ `python3 -m unittest discover -s tests -v`.
كل الاختبارات بمخرجات مزيفة لبرنامجي facebook-cli وyt-dlp
(تُحقن عبر وسيط run=) — بلا شبكة وبلا حسابات.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import analyze

FB_JSON = {
    "results": [
        {"object_id": "122132250729269645",
         "published_time": "2026-11-21T09:47:00+02:00",
         "metadata": {"caption_excerpt": "النجار الأمين — كابشن تجريبي",
                      "metadata_text": "Video • Reel"},
         "metrics": [
             {"field": "views", "rendered_text": "694", "value": None},
             {"field": "engagements", "rendered_text": "3",
              "value": None}],
         "activity": [
             {"field": "reactions", "rendered_text": "2", "value": None},
             {"field": "shares", "rendered_text": "0", "value": None},
             {"field": "comment_count", "rendered_text": "0",
              "value": None}]}
    ]
}

YT_INFO = {"id": "pZvr09dFSik", "title": "النجار الأمين",
           "upload_date": "20261121", "duration": 48,
           "view_count": 254, "like_count": 10, "comment_count": 0}


class FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def fb_run(stdout=FB_JSON, code=0):
    return lambda cmd, **kw: FakeResult(code, json.dumps(stdout))


def yt_run():
    def run(cmd, **kw):
        if "--flat-playlist" in cmd:
            return FakeResult(0, json.dumps(
                {"entries": [{"id": "pZvr09dFSik"}]}))
        return FakeResult(0, json.dumps(YT_INFO))
    return run


class TestParseIntDisplay(unittest.TestCase):
    def test_plain_int(self):
        self.assertEqual(analyze._parse_int_display("694"), 694)
        self.assertEqual(analyze._parse_int_display("  12  "), 12)

    def test_abbreviated_is_unknown(self):
        # "1.2K" لا تُحوَّل أبدًا إلى رقم — تُعامل مجهولة.
        self.assertIsNone(analyze._parse_int_display("1.2K"))
        self.assertIsNone(analyze._parse_int_display(None))
        self.assertIsNone(analyze._parse_int_display(""))

    def test_thousands_separator_ok(self):
        # "1,234" عدد صريح بفاصل آلاف — يُقبل.
        self.assertEqual(analyze._parse_int_display("1,234"), 1234)


class TestFbLastVideo(unittest.TestCase):
    def test_parses_metrics(self):
        fb, note = analyze.fb_last_video(
            "/usr/local/bin/facebook-cli", "1048148471706586",
            run=fb_run())
        self.assertIsNotNone(fb)
        self.assertEqual(fb["views"], 694)
        self.assertEqual(fb["engagements"], 3)
        self.assertEqual(fb["reactions"], 2)
        self.assertEqual(fb["comments"], 0)
        self.assertEqual(fb["shares"], 0)
        self.assertIn("النجار الأمين", fb["caption"])

    def test_abbreviated_metric_unknown(self):
        import copy
        fake = copy.deepcopy(FB_JSON)
        fake["results"][0]["metrics"][0]["rendered_text"] = "1.2K"
        fb, note = analyze.fb_last_video(
            "/usr/local/bin/facebook-cli", "1048148471706586",
            run=fb_run(fake))
        self.assertIsNone(fb["views"])
        # باقي الأرقام الصريحة ما زالت تُقرأ.
        self.assertEqual(fb["reactions"], 2)

    def test_failed_command_returns_none(self):
        fb, note = analyze.fb_last_video(
            "/usr/local/bin/facebook-cli", "1048148471706586",
            run=fb_run(code=1))
        self.assertIsNone(fb)
        self.assertTrue(note)

    def test_no_posts_returns_none(self):
        fb, note = analyze.fb_last_video(
            "/usr/local/bin/facebook-cli", "1048148471706586",
            run=fb_run({"results": []}))
        self.assertIsNone(fb)
        self.assertTrue(note)

    def test_non_video_post_noted(self):
        import copy
        fake = copy.deepcopy(FB_JSON)
        fake["results"][0]["metadata"]["metadata_text"] = "Photo"
        fb, note = analyze.fb_last_video(
            "/usr/local/bin/facebook-cli", "1048148471706586",
            run=fb_run(fake))
        self.assertIsNotNone(fb)
        self.assertIn("ليس فيديو", note)


class TestYtLatestVideo(unittest.TestCase):
    def test_parses_stats(self):
        yt, note = analyze.yt_latest_video(
            "UCz5VeqN-eolCaCPGTpiWtJw", run=yt_run())
        self.assertIsNotNone(yt)
        self.assertEqual(yt["video_id"], "pZvr09dFSik")
        self.assertEqual(yt["views"], 254)
        self.assertEqual(yt["likes"], 10)
        self.assertEqual(yt["comments"], 0)
        self.assertEqual(yt["duration"], 48)

    def test_no_channel_id(self):
        yt, note = analyze.yt_latest_video("")
        self.assertIsNone(yt)
        self.assertIn("معرّف قناة يوتيوب", note)

    def test_failed_command(self):
        def bad_run(cmd, **kw):
            return FakeResult(1, "", "خطأ")
        yt, note = analyze.yt_latest_video(
            "UCz5VeqN-eolCaCPGTpiWtJw", run=bad_run)
        self.assertIsNone(yt)
        self.assertTrue(note)

    def test_uploads_playlist_id_strips_uc(self):
        # قائمة الرفوعات = "UU" + المعرف بلا "UC" — لا "UUUC...".
        seen = []

        def spy_run(cmd, **kw):
            seen.append(cmd)
            if "--flat-playlist" in cmd:
                return FakeResult(0, json.dumps(
                    {"entries": [{"id": "pZvr09dFSik"}]}))
            return FakeResult(0, json.dumps(YT_INFO))

        yt, note = analyze.yt_latest_video(
            "UCz5VeqN-eolCaCPGTpiWtJw", run=spy_run)
        self.assertIsNotNone(yt)
        playlist_url = seen[0][-1]
        self.assertIn("list=UUz5VeqN-eolCaCPGTpiWtJw", playlist_url)
        self.assertNotIn("UUUC", playlist_url)


class TestSuggest(unittest.TestCase):
    def test_zero_comments_zero_shares(self):
        fb = {"views": 694, "reactions": 2, "comments": 0, "shares": 0,
              "engagements": 3}
        yt = {"views": 254, "likes": 10, "comments": 0}
        tips = analyze.suggest(fb, yt)
        self.assertGreaterEqual(len(tips), 2)
        joined = " ".join(tips)
        self.assertIn("تعليق", joined)
        self.assertIn("مشاركات", joined)

    def test_low_like_rate_hook(self):
        fb = {"views": 1000, "reactions": 5, "comments": 3, "shares": 2}
        yt = {"views": 1000, "likes": 5, "comments": 3}
        tips = analyze.suggest(fb, yt)
        self.assertTrue(any("قوِّ الهوك" in t for t in tips))

    def test_strong_video_no_hook_tip(self):
        fb = {"views": 500, "reactions": 40, "comments": 5, "shares": 3}
        yt = {"views": 500, "likes": 40, "comments": 5}
        tips = analyze.suggest(fb, yt)
        self.assertFalse(any("قوِّ الهوك" in t for t in tips))

    def test_both_unknown(self):
        tips = analyze.suggest(None, None)
        self.assertEqual(len(tips), 1)
        self.assertIn("لا أرقام متاحة", tips[0])

    def test_views_gap(self):
        fb = {"views": 100, "reactions": 5, "comments": 2, "shares": 1}
        yt = {"views": 500, "likes": 20, "comments": 2}
        tips = analyze.suggest(fb, yt)
        self.assertTrue(any("فيسبوك" in t for t in tips))

    def test_format_value(self):
        self.assertEqual(analyze.format_value(694), "694")
        self.assertEqual(analyze.format_value(None), "غير معروف")


if __name__ == "__main__":
    unittest.main()
