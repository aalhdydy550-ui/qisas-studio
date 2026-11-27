#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات حدود الاستخدام (lib/usage_caps) — بند 8.

بلا شبكة حقيقية: دفتر التكلفة يُبنى في مجلد مؤقت
بسطور JSONL، والإشعارات تُحقن كوحدة وهمية.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import usage_caps as uc

NOW = datetime(2026, 11, 27, 12, 0, 0)


def _write_ledger(root, entries):
    path = os.path.join(root, "runs", "cost-ledger.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for entry in entries:
            if isinstance(entry, str):
                fh.write(entry + "\n")
            else:
                fh.write(json.dumps(entry, ensure_ascii=False)
                         + "\n")
    return path


def _entry(date, usd=0, tokens=0, scope=None):
    entry = {"date": date, "video": "فيديو اختبار",
             "units": 20}
    if usd:
        entry["usd"] = usd
    if tokens:
        entry["tokens"] = tokens
    if scope:
        entry["scope"] = scope
    return entry


class UsageCapsTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        uc.reset_state()

    def tearDown(self):
        self.tmp.cleanup()
        uc.reset_state()


class TestTotals(UsageCapsTestCase):
    def test_totals_read_from_ledger(self):
        _write_ledger(self.root, [
            _entry("2026-11-27 10:00", usd=3, tokens=1000),
            _entry("2026-11-26 10:00", usd=4, tokens=2000),
            _entry("2026-10-15 10:00", usd=10, tokens=5000),
        ])
        totals = uc.current_totals(studio_root=self.root, now=NOW)
        self.assertEqual(totals["dailyUsd"], 3)
        self.assertEqual(totals["monthlyUsd"], 7)
        self.assertEqual(totals["dailyTokens"], 1000)
        self.assertEqual(totals["monthlyTokens"], 3000)
        self.assertEqual(totals["dailyUnits"], 20)
        self.assertEqual(totals["monthlyUnits"], 40)

    def test_corrupt_lines_skipped(self):
        _write_ledger(self.root, [
            _entry("2026-11-27 10:00", usd=3, tokens=1000),
            "{not json",
            _entry("2026-11-27 11:00", usd=2, tokens=500),
            "",
        ])
        totals = uc.current_totals(studio_root=self.root, now=NOW)
        self.assertEqual(totals["dailyUsd"], 5)
        self.assertEqual(totals["entries"], 2)

    def test_appended_lines_update_running_totals(self):
        path = _write_ledger(self.root, [
            _entry("2026-11-27 10:00", usd=3, tokens=1000),
        ])
        first = uc.current_totals(studio_root=self.root, now=NOW)
        self.assertEqual(first["dailyUsd"], 3)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(
                _entry("2026-11-27 11:00", usd=2, tokens=500),
                ensure_ascii=False) + "\n")
        second = uc.current_totals(studio_root=self.root, now=NOW)
        self.assertEqual(second["dailyUsd"], 5)
        self.assertEqual(second["dailyTokens"], 1500)

    def test_scope_totals_filter_entries(self):
        _write_ledger(self.root, [
            _entry("2026-11-27 10:00", usd=3, scope="worker-a"),
            _entry("2026-11-27 10:00", usd=4, scope="worker-b"),
        ])
        totals = uc.current_totals(studio_root=self.root, now=NOW,
                                   scope="worker-a")
        self.assertEqual(totals["dailyUsd"], 3)
        all_totals = uc.current_totals(studio_root=self.root,
                                       now=NOW, scope="studio")
        self.assertEqual(all_totals["dailyUsd"], 7)

    def test_empty_ledger_is_zero(self):
        totals = uc.current_totals(studio_root=self.root, now=NOW)
        self.assertEqual(totals["dailyUsd"], 0)
        self.assertEqual(totals["entries"], 0)


class TestCheck(UsageCapsTestCase):
    def _caps(self, **overrides):
        caps = {"dailyUsd": None, "monthlyUsd": None,
                "dailyTokens": None, "monthlyTokens": None,
                "stops": "unattended"}
        caps.update(overrides)
        return caps

    def test_no_caps_allows_everything(self):
        result = uc.check("unattended", studio_root=self.root,
                          caps=self._caps(), now=NOW)
        self.assertTrue(result["allowed"])
        self.assertIsNone(result["code"])

    def test_daily_cap_blocks_unattended_with_429(self):
        _write_ledger(self.root, [
            _entry("2026-11-27 10:00", usd=10),
        ])
        result = uc.check("unattended", studio_root=self.root,
                          caps=self._caps(dailyUsd=10), now=NOW)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["code"], "spend_cap")
        self.assertEqual(result["status"], 429)
        self.assertEqual(result["blocked_by"], "dailyUsd")
        self.assertGreater(result["retry_after"], 0)
        self.assertIsNotNone(result["resets_at"])

    def test_daily_cap_keeps_direct_working_under_unattended(self):
        _write_ledger(self.root, [
            _entry("2026-11-27 10:00", usd=10),
        ])
        result = uc.check("direct", studio_root=self.root,
                          caps=self._caps(dailyUsd=10), now=NOW)
        self.assertTrue(result["allowed"])
        self.assertEqual(result["blocked_by"], "dailyUsd")

    def test_everything_blocks_direct_with_409(self):
        _write_ledger(self.root, [
            _entry("2026-11-27 10:00", usd=10),
        ])
        result = uc.check(
            "direct", studio_root=self.root,
            caps=self._caps(dailyUsd=10, stops="everything"),
            now=NOW)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["code"], "spend_cap")
        self.assertEqual(result["status"], 409)

    def test_token_cap_blocks(self):
        _write_ledger(self.root, [
            _entry("2026-11-27 10:00", tokens=5000),
        ])
        result = uc.check("unattended", studio_root=self.root,
                          caps=self._caps(dailyTokens=5000),
                          now=NOW)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["blocked_by"], "dailyTokens")

    def test_monthly_cap_blocks(self):
        _write_ledger(self.root, [
            _entry("2026-11-01 10:00", usd=50),
        ])
        result = uc.check("unattended", studio_root=self.root,
                          caps=self._caps(monthlyUsd=50), now=NOW)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["blocked_by"], "monthlyUsd")

    def test_auto_resume_after_reset(self):
        _write_ledger(self.root, [
            _entry("2026-11-27 10:00", usd=10),
        ])
        blocked = uc.check("unattended", studio_root=self.root,
                           caps=self._caps(dailyUsd=10), now=NOW)
        self.assertFalse(blocked["allowed"])
        next_day = datetime(2026, 11, 28, 12, 0, 0)
        allowed = uc.check("unattended", studio_root=self.root,
                           caps=self._caps(dailyUsd=10),
                           now=next_day)
        self.assertTrue(allowed["allowed"])

    def test_check_does_not_consume_or_change_state(self):
        # الفحص استشاري فقط: فحصان متتاليان بنفس النتيجة،
        # والدفتر بلا تغيير.
        _write_ledger(self.root, [
            _entry("2026-11-27 10:00", usd=5),
        ])
        caps = self._caps(dailyUsd=10)
        first = uc.check("unattended", studio_root=self.root,
                         caps=caps, now=NOW)
        second = uc.check("unattended", studio_root=self.root,
                          caps=caps, now=NOW)
        self.assertEqual(first["allowed"], second["allowed"])
        self.assertTrue(first["allowed"])

    def test_warn_at_80_percent_writes_one_log_line(self):
        _write_ledger(self.root, [
            _entry("2026-11-27 10:00", usd=8),
        ])
        caps = self._caps(dailyUsd=10)
        uc.check("unattended", studio_root=self.root,
                 caps=caps, now=NOW)
        uc.check("unattended", studio_root=self.root,
                 caps=caps, now=NOW)
        log_path = os.path.join(self.root, "runs",
                                "usage-caps.log")
        with open(log_path, encoding="utf-8") as fh:
            lines = [line for line in fh.read().splitlines()
                     if line.strip()]
        warn_lines = [line for line in lines if "تحذير" in line]
        self.assertEqual(len(warn_lines), 1)
        self.assertIn("80%", warn_lines[0])

    def test_cap_reached_notifies_once(self):
        # وحدة notify الحقيقية (ع5) بمخزن إزالة تكرار في
        # مجلد runs المؤقت — إشعار واحد رغم فحصين.
        from lib import notify
        runs_dir = os.path.join(self.root, "runs")
        _write_ledger(self.root, [
            _entry("2026-11-27 10:00", usd=10),
        ])
        caps = self._caps(dailyUsd=10)
        uc.check("unattended", studio_root=self.root,
                 caps=caps, now=NOW)
        uc.check("unattended", studio_root=self.root,
                 caps=caps, now=NOW)
        key = "usage-cap:studio:dailyUsd:2026-11-27"
        self.assertTrue(notify.was_notified(key,
                                            runs_dir=runs_dir))
        self.assertEqual(len(notify.list_notified(
            runs_dir=runs_dir)), 1)

    def test_notify_failure_is_tolerated(self):
        # فشل الإشعار نفسه لا يكسر الفحص أبدًا.
        from unittest import mock
        from lib import notify
        _write_ledger(self.root, [
            _entry("2026-11-27 10:00", usd=10),
        ])
        with mock.patch.object(
                notify, "notify_once",
                side_effect=RuntimeError("تعطل الإشعار")):
            result = uc.check("unattended",
                              studio_root=self.root,
                              caps=self._caps(dailyUsd=10),
                              now=NOW)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["code"], "spend_cap")

    def test_one_shot_deferred_to_reset(self):
        _write_ledger(self.root, [
            _entry("2026-11-27 10:00", usd=10),
        ])
        result = uc.check("unattended", studio_root=self.root,
                          caps=self._caps(dailyUsd=10), now=NOW)
        deferred = uc.defer_one_shot(result)
        self.assertTrue(deferred["deferred"])
        self.assertEqual(deferred["run_at"],
                         result["resets_at"])
        allowed = uc.check("unattended", studio_root=self.root,
                           caps=self._caps(), now=NOW)
        self.assertEqual(uc.defer_one_shot(allowed),
                         {"deferred": False, "run_at": None})


class TestLoadCaps(UsageCapsTestCase):
    def test_env_wins_field_by_field(self):
        config_path = os.path.join(self.root, "usage-caps.json")
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump({"dailyUsd": 5, "monthlyUsd": 50,
                       "stops": "everything"}, fh)
        env = {"QISAS_USAGE_CAP_DAILY_USD": "10"}
        caps = uc.load_caps(config_path=config_path, env=env)
        self.assertEqual(caps["dailyUsd"], 10)
        self.assertEqual(caps["monthlyUsd"], 50)
        self.assertEqual(caps["stops"], "everything")

    def test_non_numeric_env_ignored(self):
        env = {"QISAS_USAGE_CAP_DAILY_USD": "ليس رقمًا",
               "QISAS_USAGE_CAP_STOPS": "bogus"}
        caps = uc.load_caps(config_path=os.path.join(
            self.root, "no-such.json"), env=env)
        self.assertIsNone(caps["dailyUsd"])
        self.assertEqual(caps["stops"], "unattended")

    def test_zero_or_empty_means_no_limit(self):
        config_path = os.path.join(self.root, "usage-caps.json")
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump({"dailyUsd": 0, "monthlyTokens": "",
                       "dailyTokens": -5}, fh)
        caps = uc.load_caps(config_path=config_path, env={})
        self.assertIsNone(caps["dailyUsd"])
        self.assertIsNone(caps["monthlyTokens"])
        self.assertIsNone(caps["dailyTokens"])

    def test_corrupt_config_means_no_limits(self):
        config_path = os.path.join(self.root, "usage-caps.json")
        with open(config_path, "w", encoding="utf-8") as fh:
            fh.write("{corrupt")
        caps = uc.load_caps(config_path=config_path, env={})
        self.assertIsNone(caps["dailyUsd"])
        self.assertEqual(caps["stops"], "unattended")


class TestReset(UsageCapsTestCase):
    def test_next_reset_daily_and_monthly(self):
        daily = uc.next_reset("daily", now=NOW)
        self.assertEqual(daily.strftime("%Y-%m-%dT%H:%M:%S"),
                         "2026-11-28T00:00:00")
        monthly = uc.next_reset("monthly", now=NOW)
        self.assertEqual(monthly.strftime("%Y-%m-%dT%H:%M:%S"),
                         "2026-12-01T00:00:00")
        year_end = uc.next_reset(
            "monthly", now=datetime(2026, 12, 15, 12, 0, 0))
        self.assertEqual(year_end.strftime("%Y-%m-%d"),
                         "2027-01-01")

    def test_format_caps_arabic(self):
        text = uc.format_caps(
            {"dailyUsd": 10, "monthlyUsd": None,
             "dailyTokens": None, "monthlyTokens": None,
             "stops": "unattended"},
            usage={"dailyUsd": 3, "monthlyUsd": 7,
                   "dailyTokens": 100, "monthlyTokens": 300})
        self.assertIn("الحد اليومي بالدولار: 10", text)
        self.assertIn("بلا حد", text)
        self.assertIn("3 دولار اليوم", text)


if __name__ == "__main__":
    unittest.main()
