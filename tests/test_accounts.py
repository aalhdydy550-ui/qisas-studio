#!/usr/bin/env python3
"""اختبارات فحوصات الحسابات — بلا شبكة وبلا حسابات حقيقية.

facebook-cli يُستبدل بمحاكاة؛ وتوكن يوتيوب ملف مؤقت بوقت
إنشاء مضبوط (os.utime)؛ ورصيد Veo من إعداد مؤقت.
"""
import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import accounts

TODAY = datetime.date(2026, 11, 22)
UPLOAD_SCOPE = accounts.YT_UPLOAD_SCOPE


def _fb_proc(results, returncode=0):
    proc = mock.MagicMock()
    proc.returncode = returncode
    proc.stdout = json.dumps({"results": results})
    proc.stderr = ""
    return proc


def _video_entry(caption="قصة تجريبية", views=694):
    return {"object_id": "122",
            "published_time": "2026-11-21T08:02:01Z",
            "metadata": {"caption_excerpt": caption,
                         "metadata_text": "Video · 48s"},
            "metrics": [{"field": "views", "value": views}],
            "activity": []}


def _token_file(td, days_ago=1, scopes=None, refresh=True):
    path = os.path.join(td, "youtube-token.json")
    data = {"token": "ya29.fake", "expiry": "2026-11-22T10:00:00Z",
            "scopes": scopes if scopes is not None else [UPLOAD_SCOPE],
            "token_uri": "https://oauth2.googleapis.com/token"}
    if refresh:
        data["refresh_token"] = "1//fake-refresh"
    Path(path).write_text(json.dumps(data), encoding="utf-8")
    mtime = datetime.datetime(2026, 11, 22) - datetime.timedelta(
        days=days_ago)
    stamp = mtime.timestamp()
    os.utime(path, (stamp, stamp))
    return path


class TestFacebookPage(unittest.TestCase):
    def test_missing_page_id_is_error(self):
        c = accounts.check_facebook_page({})
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "error")

    def test_non_numeric_page_id_is_error(self):
        c = accounts.check_facebook_page(
            {"publish": {"page_id": "abc"}})
        self.assertFalse(c["ok"])

    def test_no_facebook_bin_is_warning(self):
        cfg = {"publish": {"page_id": "1048148471706586"}}
        with mock.patch("lib.accounts.publish_lib.find_facebook_bin",
                        return_value=None):
            c = accounts.check_facebook_page(cfg)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "warn")

    def test_last_video_passes(self):
        cfg = {"publish": {"page_id": "1048148471706586"}}
        runner = lambda cmd, **kw: _fb_proc([_video_entry()])
        with mock.patch("lib.accounts.publish_lib.find_facebook_bin",
                        return_value="facebook-cli"):
            c = accounts.check_facebook_page(cfg, runner=runner)
        self.assertTrue(c["ok"])
        self.assertIn("694", c["detail"])

    def test_failed_read_is_warning_not_error(self):
        cfg = {"publish": {"page_id": "1048148471706586"}}
        runner = lambda cmd, **kw: _fb_proc([], returncode=1)
        with mock.patch("lib.accounts.publish_lib.find_facebook_bin",
                        return_value="facebook-cli"):
            c = accounts.check_facebook_page(cfg, runner=runner)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "warn")


class TestYoutubeToken(unittest.TestCase):
    def test_missing_token_is_warning(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = {"publish": {"youtube_token": os.path.join(
                td, "nope.json")}}
            c = accounts.check_youtube_token(cfg, today=TODAY)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "warn")

    def test_fresh_token_passes_with_days_left(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = {"publish": {"youtube_token": _token_file(td, 1)}}
            c = accounts.check_youtube_token(cfg, today=TODAY)
        self.assertTrue(c["ok"])
        self.assertIn("6 أيام", c["detail"])

    def test_token_with_two_days_left_is_error(self):
        # الجولة 6: يومان أو أقل = خطأ لا تنبيهًا — أعد الموافقة
        # فورًا (كان «warn» في الجولة 5؛ غيّره القرار الجديد).
        with tempfile.TemporaryDirectory() as td:
            cfg = {"publish": {"youtube_token": _token_file(td, 5)}}
            c = accounts.check_youtube_token(cfg, today=TODAY)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "error")
        self.assertIn("2 يومين", c["detail"])

    def test_expired_token_is_error(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = {"publish": {"youtube_token": _token_file(td, 8)}}
            c = accounts.check_youtube_token(cfg, today=TODAY)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "error")

    def test_token_without_refresh_is_error(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = {"publish": {"youtube_token": _token_file(
                td, 1, refresh=False)}}
            c = accounts.check_youtube_token(cfg, today=TODAY)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "error")

    def test_token_without_upload_scope_warns(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = {"publish": {"youtube_token": _token_file(
                td, 1, scopes=["https://www.googleapis.com/auth/"
                               "youtube.readonly"])}}
            c = accounts.check_youtube_token(cfg, today=TODAY)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "warn")

    def test_corrupt_token_is_error(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "youtube-token.json")
            Path(path).write_text("{not json", encoding="utf-8")
            c = accounts.check_youtube_token(
                {"publish": {"youtube_token": path}}, today=TODAY)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "error")


class TestVeoBalance(unittest.TestCase):
    def test_missing_veo_section_warns(self):
        c = accounts.check_veo_balance({}, today=TODAY)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "warn")

    def test_healthy_balance_passes(self):
        # رصيد سليم ومحدَّث قبل ساعة (عمر معروف وحديث — الجولة 8:
        # رصيد بلا updated_at يُحذَّر منه الآن، فالاختبار يمرّر
        # ختمًا حديثًا صراحةً).
        fresh = (datetime.datetime.now(datetime.timezone.utc)
                 - datetime.timedelta(hours=1)).isoformat()
        cfg = {"veo": {"balance_units": 680,
                       "renews": "2026-12-13",
                       "daily_cost_min": 100,
                       "daily_cost_max": 140,
                       "updated_at": fresh}}
        c = accounts.check_veo_balance(cfg, today=TODAY)
        self.assertTrue(c["ok"])
        self.assertIn("680", c["detail"])

    def test_balance_below_one_video_warns(self):
        cfg = {"veo": {"balance_units": 50,
                       "renews": "2026-12-13"}}
        c = accounts.check_veo_balance(cfg, today=TODAY)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "warn")

    def test_invalid_balance_is_error(self):
        cfg = {"veo": {"balance_units": -5,
                       "renews": "2026-12-13"}}
        c = accounts.check_veo_balance(cfg, today=TODAY)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "error")


class TestRunAccountChecks(unittest.TestCase):
    def test_returns_three_checks(self):
        fresh = (datetime.datetime.now(datetime.timezone.utc)
                 - datetime.timedelta(hours=1)).isoformat()
        with tempfile.TemporaryDirectory() as td:
            cfg = {"publish": {
                       "page_id": "1048148471706586",
                       "youtube_token": _token_file(td, 1)},
                   "veo": {"balance_units": 680,
                           "renews": "2026-12-13",
                           "updated_at": fresh}}
            runner = lambda cmd, **kw: _fb_proc([_video_entry()])
            with mock.patch(
                    "lib.accounts.publish_lib.find_facebook_bin",
                    return_value="facebook-cli"):
                checks = accounts.run_account_checks(
                    cfg, runner=runner, today=TODAY)
        self.assertEqual(len(checks), 3)
        self.assertTrue(all(c["ok"] for c in checks))


if __name__ == "__main__":
    unittest.main()
