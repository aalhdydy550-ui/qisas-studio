#!/usr/bin/env python3
"""اختبارات الجولة 8 (v0.1.33) — عمر رصيد Veo.

- `balance --set N`: يكتب الرصيد + `updated_at` بتوقيت القاهرة.
- الخصم التلقائي عند التنفيذ الفعلي فقط (موافقة خطة مشاهد في
  daily، وفيديو Veo مكتمل في batch، وفيديو Veo جاهز منشور في
  daily) — ولا خصم في وضع تجريبي.
- تحذير صريح لعمر مجهول أو أقدم من 7 أيام في `balance`
  و`doctor --accounts`.
كل الكتابة في مجلدات مؤقتة — لا يُمس config.yaml الحقيقي.
"""
import datetime
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import accounts
from lib import balance
from lib import batch
from lib import daily

NOW = datetime.datetime(2026, 11, 22, 12, 0,
                        tzinfo=datetime.timezone.utc)
TODAY = datetime.date(2026, 11, 22)

CONFIG_TEXT = """# إعداد اختبار
veo:
  balance_units: 680
  renews: "2026-12-13"
  daily_cost_min: 100
  daily_cost_max: 140
"""


def _iso(hours_ago, now=NOW):
    return (now - datetime.timedelta(hours=hours_ago)).isoformat()


def _write_config(td, text=CONFIG_TEXT):
    path = os.path.join(td, "config.yaml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def _cfg(tmpdir, balance_units=680):
    queue = os.path.join(tmpdir, "queue.md")
    with open(queue, "w", encoding="utf-8") as f:
        f.write("# طابور قصص\n\n## في الانتظار\n\n"
                "4. **العنزة المباركة** — تحتاج جزأين\n"
                "5. **عجائب الصدقة** — منشور واحد\n")
    return {
        "paths": {
            "queue_file": queue,
            "videos_dir": os.path.join(tmpdir, "videos"),
            "runs_dir": os.path.join(tmpdir, "runs"),
        },
        "publish": {"page_id": "1048148471706586",
                    "youtube_channel_id": "UCz5VeqN-eolCaCPGTpiWtJw"},
        "veo": {"balance_units": balance_units,
                "renews": "2026-12-13",
                "daily_cost_min": 100, "daily_cost_max": 140},
    }


def _ready(story):
    if story["number"] == 4:
        return True, "anza", "anza-part1", ""
    return False, None, None, "يحتاج تجهيز مشروع"


class TestNowIsoCairo(unittest.TestCase):
    def test_cairo_offset_in_november(self):
        # 22 نوفمبر: القاهرة +02:00 (شتاءً).
        stamp = balance.now_iso_cairo(NOW)
        self.assertTrue(stamp.endswith("+02:00"),
                        "الختم ليس بتوقيت القاهرة: %s" % stamp)
        self.assertIn("2026-11-22T14:00:00", stamp)

    def test_naive_now_treated_as_cairo(self):
        stamp = balance.now_iso_cairo(
            datetime.datetime(2026, 11, 22, 12, 0))
        self.assertTrue(stamp.endswith("+02:00"))


class TestBalanceAgeWarnings(unittest.TestCase):
    def test_unknown_age_warns(self):
        warnings = balance.balance_age_warnings(None, now=NOW)
        self.assertEqual(len(warnings), 1)
        self.assertIn("غير معروف", warnings[0])
        self.assertNotIn("قديم", warnings[0])

    def test_older_than_seven_days_warns(self):
        warnings = balance.balance_age_warnings(_iso(8 * 24), now=NOW)
        self.assertEqual(len(warnings), 1)
        self.assertIn("7 أيام", warnings[0])

    def test_thirty_hours_has_no_age_warning(self):
        # تحذير الـ24 ساعة («قديم») منفصل — هذه القائمة لا تكرره.
        self.assertEqual(
            balance.balance_age_warnings(_iso(30), now=NOW), [])

    def test_fresh_has_no_warning(self):
        self.assertEqual(
            balance.balance_age_warnings(_iso(1), now=NOW), [])


class TestFormatForecastAgeWarnings(unittest.TestCase):
    def test_unknown_age_warns_in_balance_output(self):
        out = balance.forecast(680, "2026-12-13", 100, 140,
                               today=TODAY)
        text = balance.format_forecast(out)
        self.assertIn("عمر الرقم: غير معروف العمر", text)
        self.assertIn("تحذير: عمر الرصيد غير معروف", text)

    def test_older_than_seven_days_warns_in_balance_output(self):
        eight_days_ago = (datetime.datetime.now(
            datetime.timezone.utc)
            - datetime.timedelta(days=8)).isoformat()
        out = balance.forecast(680, "2026-12-13", 100, 140,
                               today=TODAY,
                               updated_at=eight_days_ago)
        text = balance.format_forecast(out)
        self.assertIn("أقدم من 7 أيام", text)


class TestDoctorAccountsAgeWarnings(unittest.TestCase):
    def _veo_cfg(self, updated_at=None):
        veo = {"balance_units": 680, "renews": "2026-12-13",
               "daily_cost_min": 100, "daily_cost_max": 140}
        if updated_at is not None:
            veo["updated_at"] = updated_at
        return {"veo": veo}

    def test_unknown_age_warns_without_qadim(self):
        c = accounts.check_veo_balance(self._veo_cfg(), today=TODAY,
                                       now=NOW)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "warn")
        self.assertIn("غير معروف", c["detail"])
        self.assertNotIn("قديم", c["detail"])

    def test_older_than_seven_days_warns(self):
        c = accounts.check_veo_balance(
            self._veo_cfg(updated_at=_iso(8 * 24)), today=TODAY,
            now=NOW)
        self.assertFalse(c["ok"])
        self.assertIn("7 أيام", c["detail"])

    def test_fresh_balance_ok(self):
        c = accounts.check_veo_balance(
            self._veo_cfg(updated_at=_iso(1)), today=TODAY, now=NOW)
        self.assertTrue(c["ok"])


class TestRecordVeoSpend(unittest.TestCase):
    def test_deducts_and_stamps_cairo_time(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_config(td)
            new_balance = balance.record_veo_spend(path, 120, now=NOW)
            self.assertEqual(new_balance, 560)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("balance_units: 560", text)
            self.assertIn("updated_at: 2026-11-22T14:00:00+02:00",
                          text)

    def test_deduct_floors_at_zero(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_config(td)
            self.assertEqual(balance.record_veo_spend(path, 9999), 0)

    def test_no_recorded_balance_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_config(td, "veo:\n  renews: \"2026-12-13\"\n")
            self.assertIsNone(balance.record_veo_spend(path, 120))

    def test_invalid_units_raise(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_config(td)
            with self.assertRaises(ValueError):
                balance.record_veo_spend(path, 0)


class TestBalanceSetCommand(unittest.TestCase):
    def test_set_writes_balance_and_cairo_stamp(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_config(td)
            cfg = {"veo": {"balance_units": 680,
                           "renews": "2026-12-13",
                           "daily_cost_min": 100,
                           "daily_cost_max": 140}}
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = studio.cmd_balance(cfg, set_balance=500,
                                        config_path=path)
            self.assertEqual(rc, 0)
            self.assertIn("القاهرة", buf.getvalue())
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("balance_units: 500", text)
            # الختم بتوقيت القاهرة (+02:00 أو +03:00 حسب التوقيت
            # الصيفي) لا بتوقيت UTC (+00:00).
            self.assertRegex(text, r"updated_at: .*\+0[23]:00")
            self.assertNotIn("+00:00", text)

    def test_set_negative_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_config(td)
            cfg = {"veo": {}}
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = studio.cmd_balance(cfg, set_balance=-5,
                                        config_path=path)
            self.assertEqual(rc, 2)
            with open(path, encoding="utf-8") as f:
                self.assertIn("balance_units: 680", f.read())


class TestDailySpendHook(unittest.TestCase):
    def test_approved_scene_plan_deducts_once(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            plan = daily.plan_daily(cfg, "morning",
                                    ready_fn=_ready)
            self.assertEqual(plan["path"], "veo")
            self.assertIsNotNone(plan["scene_plan"])
            spent = []
            fns = (lambda c, s, p, o: 0,
                   lambda v: {"passed": True},
                   lambda v, h, o: o,
                   lambda c, v, t, cap, th: 0)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc, result = daily.execute_daily(
                    cfg, plan, *fns,
                    os.path.join(td, "runs"), auto_approve=True,
                    record_spend_fn=lambda u: spent.append(u) or 560)
            # بلا فيديو جاهز: يتوقف بعد الموافقة — لكن الخصم تم.
            self.assertEqual(rc, 1)
            self.assertEqual(spent, [120])
            self.assertEqual(
                result["steps"]["scene_plan"]["spent_units"], 120)

    def test_ready_veo_video_deducts_on_publish(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            videos = os.path.join(td, "videos")
            os.makedirs(videos, exist_ok=True)
            video = os.path.join(videos, "anza-daily.mp4")
            with open(video, "wb") as f:
                f.write(b"fake")
            plan = daily.plan_daily(cfg, "morning", video=video,
                                    ready_fn=_ready)
            self.assertTrue(plan["video_ready"])
            spent = []
            fns = (lambda c, s, p, o: 0,
                   lambda v: {"passed": True, "checks": []},
                   lambda v, h, o: o,
                   lambda c, v, t, cap, th: 0)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc, result = daily.execute_daily(
                    cfg, plan, *fns,
                    os.path.join(td, "runs"), auto_approve=True,
                    record_spend_fn=lambda u: spent.append(u) or 560)
            self.assertEqual(rc, 0)
            self.assertEqual(spent, [120])
            self.assertEqual(
                result["steps"]["veo_spend"]["spent_units"], 120)

    def test_openmontage_path_never_deducts(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td, balance_units=50)  # مسار OpenMontage
            plan = daily.plan_daily(cfg, "morning",
                                    ready_fn=_ready)
            self.assertEqual(plan["path"], "openmontage")
            spent = []
            fns = (lambda c, s, p, o: 0,
                   lambda v: {"passed": True, "checks": []},
                   lambda v, h, o: o,
                   lambda c, v, t, cap, th: 0)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc, _ = daily.execute_daily(
                    cfg, plan, *fns,
                    os.path.join(td, "runs"),
                    record_spend_fn=lambda u: spent.append(u))
            self.assertEqual(rc, 0)
            self.assertEqual(spent, [])


class TestBatchSpendHook(unittest.TestCase):
    def _plan(self, td):
        cfg = _cfg(td)
        videos = os.path.join(td, "videos")
        os.makedirs(videos, exist_ok=True)
        video = os.path.join(videos, "anza-batch.mp4")
        with open(video, "wb") as f:
            f.write(b"fake")
        return batch.plan_batch(cfg, 1, source="veo",
                                ready_fn=_ready)

    def test_completed_veo_video_deducts(self):
        with tempfile.TemporaryDirectory() as td:
            plan = self._plan(td)
            spent = []
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc, result = batch.execute_batch(
                    _cfg(td), plan,
                    lambda c, s, p, o: 0,
                    lambda v: {"passed": True},
                    lambda v, h, o: o,
                    os.path.join(td, "runs"),
                    record_spend_fn=lambda u: spent.append(u) or 560)
            self.assertEqual(rc, 0)
            self.assertEqual(spent, [120])
            self.assertEqual(result["total_spent_units"], 120)
            self.assertEqual(
                result["stories"][0]["units_spent"], 120)

    def test_skipped_story_deducts_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            plan = batch.plan_batch(
                cfg, 2, source="veo",
                ready_fn=lambda s: ((True, "anza", "anza-part1", "")
                                    if s["number"] == 4 else
                                    (False, None, None, "بلا مشروع")))
            spent = []
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc, result = batch.execute_batch(
                    cfg, plan,
                    lambda c, s, p, o: 0,
                    lambda v: {"passed": True},
                    lambda v, h, o: o,
                    os.path.join(td, "runs"),
                    record_spend_fn=lambda u: spent.append(u))
            # القصة 4 بلا فيديو جاهز (needs-flow) — لا خصم لها،
            # والقصة 5 متخطاة — لا خصم؛ المجموع صفر.
            self.assertEqual(spent, [])
            self.assertEqual(result["total_spent_units"], 0)


if __name__ == "__main__":
    unittest.main()
