#!/usr/bin/env python3
"""اختبارات الجولة 6 — فحوصات الحسابات (بند 2 وبند 5).

توكن يوتيوب: يومان أو أقل = خطأ (لا تنبيهًا)؛ ورصيد Veo:
عمر الرقم يُعرض دائمًا، وبلا updated_at = «غير معروف العمر»
بلا تحذير قدم، وأقدم من 24 ساعة = تحذير قدم.

بلا شبكة وبلا حسابات حقيقية — توكن وهمي بوقت إنشاء مضبوط
(os.utime)، ورصيد من إعداد مؤقت.
"""
import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import accounts

TODAY = datetime.date(2026, 11, 22)
NOW = datetime.datetime(2026, 11, 22, 12, 0,
                        tzinfo=datetime.timezone.utc)
UPLOAD_SCOPE = accounts.YT_UPLOAD_SCOPE


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


def _iso(hours_ago):
    return (NOW - datetime.timedelta(hours=hours_ago)).isoformat()


def _veo_cfg(balance_units=680, updated_at=None):
    veo = {"balance_units": balance_units,
           "renews": "2026-12-13",
           "daily_cost_min": 100,
           "daily_cost_max": 140}
    if updated_at is not None:
        veo["updated_at"] = updated_at
    return {"veo": veo}


class TestYoutubeTokenRound6(unittest.TestCase):
    def test_one_day_left_is_error(self):
        # توكن وهمي بقي عليه يوم واحد → خطأ (الجولة 6).
        with tempfile.TemporaryDirectory() as td:
            cfg = {"publish": {"youtube_token": _token_file(td, 6)}}
            c = accounts.check_youtube_token(cfg, today=TODAY)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "error")
        self.assertIn("يوم", c["detail"])
        self.assertIn("youtube-reauth", c["fix"])

    def test_two_days_left_is_error(self):
        # يومان → خطأ أيضًا (لا تنبيهًا كما كان قبل الجولة 6).
        with tempfile.TemporaryDirectory() as td:
            cfg = {"publish": {"youtube_token": _token_file(td, 5)}}
            c = accounts.check_youtube_token(cfg, today=TODAY)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "error")
        self.assertIn("youtube-reauth", c["fix"])

    def test_three_days_left_still_warns(self):
        # 3 أيام: الحد — ما زال تنبيهًا لا خطأ.
        with tempfile.TemporaryDirectory() as td:
            cfg = {"publish": {"youtube_token": _token_file(td, 4)}}
            c = accounts.check_youtube_token(cfg, today=TODAY)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "warn")

    def test_five_days_left_is_not_error(self):
        # توكن بقي عليه 5 أيام → ليس خطأ (ناجح).
        with tempfile.TemporaryDirectory() as td:
            cfg = {"publish": {"youtube_token": _token_file(td, 2)}}
            c = accounts.check_youtube_token(cfg, today=TODAY)
        self.assertTrue(c["ok"])
        self.assertIn("5 أيام", c["detail"])


class TestVeoBalanceAgeRound6(unittest.TestCase):
    def test_balance_without_updated_at_is_unknown_age(self):
        # رصيد بلا updated_at → «غير معروف العمر» مع تحذير صريح
        # (الجولة 8: العمر المجهول يُحذَّر منه — كان «بلا تحذير
        # قدم» في الجولة 6؛ السلوك الجديد مقصود).
        c = accounts.check_veo_balance(_veo_cfg(), today=TODAY,
                                       now=NOW)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "warn")
        self.assertIn("غير معروف العمر", c["detail"])
        self.assertNotIn("قديم", c["detail"])

    def test_balance_updated_30_hours_ago_warns_stale(self):
        # رصيد محدَّث قبل 30 ساعة → تحذير قدم.
        c = accounts.check_veo_balance(_veo_cfg(updated_at=_iso(30)),
                                       today=TODAY, now=NOW)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "warn")
        self.assertIn("قديم", c["detail"])
        self.assertIn("يوم", c["detail"])

    def test_balance_updated_one_hour_ago_no_warning(self):
        # رصيد محدَّث قبل ساعة → بلا تحذير.
        c = accounts.check_veo_balance(_veo_cfg(updated_at=_iso(1)),
                                       today=TODAY, now=NOW)
        self.assertTrue(c["ok"])
        self.assertIn("ساعة", c["detail"])
        self.assertNotIn("قديم", c["detail"])

    def test_stale_and_low_balance_warns_with_both(self):
        # قديم + أقل من فيديو واحد → تحذير يذكر السببين.
        c = accounts.check_veo_balance(
            _veo_cfg(balance_units=50, updated_at=_iso(30)),
            today=TODAY, now=NOW)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "warn")
        self.assertIn("قديم", c["detail"])
        self.assertIn("120", c["detail"])


if __name__ == "__main__":
    unittest.main()
