#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات اللقطة الخام لبيانات الأداء (v0.1.37 — البند 11).

`analyze` على بيانات مزيفة يكتب اللقطة؛ وإعادة التحليل من
اللقطة تعطي نفس الملخص؛ والعبث بالخام يُكتشف بالبصمة.
بلا شبكة وبلا حسابات.
"""
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import analyze
from lib import insights

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

YT_PLAYLIST = {"entries": [{"id": "pZvr09dFSik"}]}
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
            return FakeResult(0, json.dumps(YT_PLAYLIST))
        return FakeResult(0, json.dumps(YT_INFO))
    return run


class TestInsightsSnapshot(unittest.TestCase):
    def test_raw_sink_captures_verbatim(self):
        sink = {}
        fb, _note = analyze.fb_last_video(
            "/usr/local/bin/facebook-cli", "1048148471706586",
            run=fb_run(), raw_sink=sink)
        self.assertEqual(sink["facebook"], FB_JSON)
        self.assertEqual(fb["views"], 694)
        yt, _note = analyze.yt_latest_video(
            "UCz5VeqN-eolCaCPGTpiWtJw", run=yt_run(), raw_sink=sink)
        self.assertEqual(sink["youtube"]["playlist"], YT_PLAYLIST)
        self.assertEqual(sink["youtube"]["info"], YT_INFO)
        self.assertEqual(yt["views"], 254)

    def test_save_load_verify_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = insights.save_snapshot(
                d, FB_JSON, {"playlist": YT_PLAYLIST, "info": YT_INFO})
            self.assertTrue(os.path.basename(path).startswith("insights-"))
            record = insights.load_snapshot(path)
            self.assertIn("captured_at", record)
            self.assertIn("sha256", record)
            ok, _detail = insights.verify_snapshot(record)
            self.assertTrue(ok)

    def test_tampered_snapshot_fails_verify(self):
        with tempfile.TemporaryDirectory() as d:
            path = insights.save_snapshot(
                d, FB_JSON, {"playlist": YT_PLAYLIST, "info": YT_INFO})
            record = insights.load_snapshot(path)
            record["raw"]["facebook"]["results"][0]["metrics"][0][
                "rendered_text"] = "9999"
            ok, _detail = insights.verify_snapshot(record)
            self.assertFalse(ok)

    def test_summarize_from_snapshot_matches_live(self):
        sink = {}
        fb, _n1 = analyze.fb_last_video(
            "/usr/local/bin/facebook-cli", "1048148471706586",
            run=fb_run(), raw_sink=sink)
        yt, _n2 = analyze.yt_latest_video(
            "UCz5VeqN-eolCaCPGTpiWtJw", run=yt_run(), raw_sink=sink)
        with tempfile.TemporaryDirectory() as d:
            path = insights.save_snapshot(
                d, sink.get("facebook"), sink.get("youtube"))
            record = insights.load_snapshot(path)
            summary = insights.summarize(record)
        self.assertEqual(summary["facebook"], fb)
        self.assertEqual(summary["youtube"], yt)

    def test_cmd_analyze_writes_snapshot_and_references_it(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"paths": {"runs_dir": d},
                   "publish": {"page_id": "1048148471706586",
                               "youtube_channel_id":
                                   "UCz5VeqN-eolCaCPGTpiWtJw"}}
            fake_fb = ({"object_id": "122132250729269645",
                        "published_time": "2026-11-21T09:47:00+02:00",
                        "caption": "النجار الأمين",
                        "is_video": True, "views": 694,
                        "engagements": 3, "reactions": 2,
                        "shares": 0, "comments": 0}, None)
            fake_yt = ({"video_id": "pZvr09dFSik",
                        "title": "النجار الأمين",
                        "upload_date": "20261121", "duration": 48,
                        "views": 254, "likes": 10, "comments": 0},
                       None)

            def fake_fb_fetch(bin_path, page_id, raw_sink=None):
                if raw_sink is not None:
                    raw_sink["facebook"] = copy.deepcopy(FB_JSON)
                return fake_fb

            def fake_yt_fetch(channel_id, raw_sink=None):
                if raw_sink is not None:
                    raw_sink["youtube"] = {
                        "playlist": copy.deepcopy(YT_PLAYLIST),
                        "info": copy.deepcopy(YT_INFO)}
                return fake_yt

            buf = io.StringIO()
            with mock.patch.object(analyze, "fb_last_video",
                                   side_effect=fake_fb_fetch), \
                    mock.patch.object(analyze, "yt_latest_video",
                                      side_effect=fake_yt_fetch), \
                    mock.patch.object(studio.publish,
                                      "find_facebook_bin",
                                      return_value="/usr/local/bin/facebook-cli"):
                import contextlib
                with contextlib.redirect_stdout(buf):
                    rc = studio.cmd_analyze(cfg)
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("اللقطة الخام", out)
            snaps = [f for f in os.listdir(d)
                     if f.startswith("insights-")]
            self.assertEqual(len(snaps), 1)
            record = insights.load_snapshot(os.path.join(d, snaps[0]))
            ok, _detail = insights.verify_snapshot(record)
            self.assertTrue(ok)
            summaries = [f for f in os.listdir(d)
                         if f.startswith("analyze-")]
            self.assertEqual(len(summaries), 1)
            with open(os.path.join(d, summaries[0]),
                      encoding="utf-8") as f:
                summary = json.load(f)
            self.assertEqual(summary["snapshot_file"],
                             os.path.join(d, snaps[0]))
            self.assertEqual(
                insights.summarize(record)["facebook"]["views"], 694)


if __name__ == "__main__":
    unittest.main()
