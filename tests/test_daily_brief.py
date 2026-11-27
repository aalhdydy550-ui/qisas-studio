#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات الموجز اليومي (lib.daily_brief) — جولة v0.1.63، بندا 22 و33.

تعمل بـ `python3 -m unittest tests.test_daily_brief -v` من مجلد studio.
بلا ملفات خارجية وبلا شبكة — الحالة في مجلد runs مؤقت.
"""
import json
import os
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import daily_brief


def _brief(**kwargs):
    return daily_brief.build_brief(
        "2026-11-27",
        needs_you=[{"title": "رد على بريد المعلن", "detail": "ينتظر منذ أمس"}],
        your_day=[{"title": "نشر الشورت الصباحي 09:00"}],
        important_emails=[{"title": "بريد من يوتيوب", "source": "gmail"}],
        routines=[{"title": "كرون الشورتات اليومي — نجح"}],
        **kwargs,
    )


class TestBuildAndRender(unittest.TestCase):
    def test_four_sections_in_order(self):
        brief = _brief()
        text = daily_brief.render_brief(brief)
        positions = [
            text.index(title) for title in daily_brief.SECTION_TITLES.values()
        ]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("رد على بريد المعلن", text)
        self.assertIn("Africa/Cairo", text)
        self.assertEqual(brief["timezone"], "Africa/Cairo")

    def test_empty_brief(self):
        brief = daily_brief.build_brief("2026-11-27")
        self.assertTrue(daily_brief.is_empty(brief))
        self.assertFalse(daily_brief.is_empty(_brief()))

    def test_server_card_makes_brief_non_empty(self):
        card = daily_brief.make_server_card("تنبيه", "نص")
        brief = daily_brief.build_brief("2026-11-27", server_cards=[card])
        self.assertFalse(daily_brief.is_empty(brief))

    def test_row_without_title_refused(self):
        with self.assertRaises(daily_brief.BriefError):
            daily_brief.build_brief("2026-11-27", needs_you=[{"detail": "x"}])

    def test_today_cairo_format(self):
        self.assertRegex(daily_brief.today_cairo(), r"^\d{4}-\d{2}-\d{2}$")


class TestDeliverOnce(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runs = os.path.join(self.tmp.name, "runs")

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_brief_never_published(self):
        brief = daily_brief.build_brief("2026-11-27")
        result = daily_brief.deliver_brief(brief, self.runs)
        self.assertEqual(result, {"delivered": False, "reason": "empty_brief"})
        self.assertFalse(os.path.exists(os.path.join(self.runs, "brief.json")))

    def test_deliver_once_then_second_refused(self):
        brief = _brief()
        first = daily_brief.deliver_brief(brief, self.runs)
        self.assertTrue(first["delivered"])
        self.assertEqual(first["reason"], "delivered")
        self.assertEqual(brief["status"], "delivered")
        second = daily_brief.deliver_brief(_brief(), self.runs)
        self.assertFalse(second["delivered"])
        self.assertEqual(second["reason"], "already_delivered")

    def test_state_file_records_timezone_and_important_rows(self):
        brief = _brief()
        daily_brief.deliver_brief(brief, self.runs)
        path = os.path.join(self.runs, "brief.json")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
        self.assertEqual(state["timezone"], "Africa/Cairo")
        self.assertEqual(state["brief_file"], "brief-2026-11-27.md")
        needs = brief["sections"]["needs_you"][0]["id"]
        mail = brief["sections"]["important_emails"][0]["id"]
        self.assertIn(needs, state["important_rows"])
        self.assertIn(mail, state["important_rows"])
        self.assertNotIn(
            brief["sections"]["your_day"][0]["id"], state["important_rows"]
        )
        self.assertIn("2026-11-27", state["delivered"])

    def test_load_state_missing_is_empty(self):
        state = daily_brief.load_state(self.runs)
        self.assertEqual(state["timezone"], "Africa/Cairo")
        self.assertEqual(state["delivered"], {})

    def test_other_brief_paused_not_deleted(self):
        brief = _brief()
        daily_brief.pause_brief(brief)
        self.assertEqual(brief["status"], "paused")
        self.assertEqual(brief["sections"]["needs_you"][0]["title"],
                         "رد على بريد المعلن")


class TestServerCards(unittest.TestCase):
    def test_make_server_card_flagged(self):
        card = daily_brief.make_server_card("تنبيه النظام", "نص البطاقة")
        self.assertTrue(daily_brief.is_server_card(card))
        self.assertTrue(card["serverCard"])
        self.assertTrue(card["id"].startswith("card-"))

    def test_agent_cannot_modify_server_card(self):
        card = daily_brief.make_server_card("تنبيه", "نص")
        with self.assertRaises(daily_brief.BriefError):
            daily_brief.apply_agent_update(card, {"title": "معدّل"})
        self.assertEqual(card["title"], "تنبيه")

    def test_agent_can_update_plain_card(self):
        card = {"id": "c1", "title": "قديم"}
        updated = daily_brief.apply_agent_update(card, {"title": "جديد"})
        self.assertEqual(updated["title"], "جديد")
        self.assertEqual(card["title"], "قديم")  # الأصل بلا تعديل

    def test_non_server_card_in_brief_refused(self):
        with self.assertRaises(daily_brief.BriefError):
            daily_brief.build_brief(
                "2026-11-27", server_cards=[{"title": "بلا علامة"}]
            )


class TestDismissOwnership(unittest.TestCase):
    def test_owner_can_dismiss(self):
        brief = _brief()
        row_id = brief["sections"]["needs_you"][0]["id"]
        daily_brief.dismiss_row(
            brief, row_id, owner="ayman", thread_owner="ayman"
        )
        self.assertIn(row_id, brief["dismissed"])

    def test_non_owner_cannot_dismiss(self):
        brief = _brief()
        row_id = brief["sections"]["needs_you"][0]["id"]
        with self.assertRaises(daily_brief.BriefError):
            daily_brief.dismiss_row(
                brief, row_id, owner="worker", thread_owner="ayman"
            )
        self.assertNotIn(row_id, brief["dismissed"])

    def test_dismiss_unknown_row_refused(self):
        brief = _brief()
        with self.assertRaises(daily_brief.BriefError):
            daily_brief.dismiss_row(
                brief, "row-missing", owner="ayman", thread_owner="ayman"
            )

    def test_dismiss_server_card_by_owner(self):
        card = daily_brief.make_server_card("تنبيه", "نص")
        brief = daily_brief.build_brief("2026-11-27", server_cards=[card])
        daily_brief.dismiss_row(
            brief, card["id"], owner="ayman", thread_owner="ayman"
        )
        self.assertIn(card["id"], brief["dismissed"])

    def test_dismissal_recorded_in_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = os.path.join(tmp, "runs")
            brief = _brief()
            row_id = brief["sections"]["needs_you"][0]["id"]
            daily_brief.dismiss_row(
                brief, row_id, owner="ayman", thread_owner="ayman"
            )
            daily_brief.deliver_brief(brief, runs)
            state = daily_brief.load_state(runs)
            self.assertIn(row_id, state["last_dismissals"])


if __name__ == "__main__":
    unittest.main()
