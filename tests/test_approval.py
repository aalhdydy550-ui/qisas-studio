#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات مستويات الموافقة الخمسة — جولة v0.1.63، البنود 1 و10 و18 و20.

كل الاختبارات على مجلدات مؤقتة (إعداد + سجل قرارات) — لا تلمس
ملف الإعداد الحقيقي (~/.qisas-studio/approval.json) أبدًا،
وتتحقق في النهاية أن حالته لم تتغيّر.
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import approval

REAL_CONFIG = os.path.expanduser("~/.qisas-studio/approval.json")
CAIRO = ZoneInfo("Africa/Cairo")


class ApprovalTestBase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = self._td.name
        self.addCleanup(self._td.cleanup)
        self.runs = os.path.join(self.td, "runs")
        os.makedirs(self.runs)
        self._real_snapshot = None
        if os.path.exists(REAL_CONFIG):
            with open(REAL_CONFIG, "rb") as fh:
                self._real_snapshot = fh.read()

    def tearDown(self):
        if self._real_snapshot is None:
            self.assertFalse(os.path.exists(REAL_CONFIG),
                             "الاختبار كتب في ملف الإعداد الحقيقي!")
        else:
            self.assertTrue(os.path.exists(REAL_CONFIG),
                            "الاختبار حذف ملف الإعداد الحقيقي!")
            with open(REAL_CONFIG, "rb") as fh:
                self.assertEqual(fh.read(), self._real_snapshot,
                                 "الاختبار عدّل ملف الإعداد الحقيقي!")

    def _gate(self, level="ask"):
        gate = approval.ApprovalGate(config_dir=self.td,
                                     runs_directory=self.runs)
        if level != "ask":
            gate.set_level(level)
        return gate


class TestLevels(ApprovalTestBase):
    def test_ask_asks_everything(self):
        gate = self._gate("ask")
        self.assertEqual(gate.check("publish"), "ask")
        self.assertEqual(gate.check("edit_text"), "ask")
        self.assertEqual(gate.check("delete"), "ask")

    def test_edits_accepts_text_edits_only(self):
        gate = self._gate("edits")
        self.assertEqual(gate.check("edit_text"), "allow")
        self.assertEqual(gate.check("publish"), "ask")
        self.assertEqual(gate.check("delete"), "ask")

    def test_auto_approves_on_behalf(self):
        gate = self._gate("auto")
        self.assertEqual(gate.check("publish"), "allow")
        self.assertEqual(gate.check("edit_text"), "allow")

    def test_full_allows_except_floor(self):
        gate = self._gate("full")
        self.assertEqual(gate.check("publish"), "allow")
        self.assertEqual(gate.check("send_message"), "allow")

    def test_custom_map(self):
        gate = self._gate("custom")
        gate.set_custom_action("edit_text", "allow")
        gate.set_custom_action("publish", "deny")
        self.assertEqual(gate.check("edit_text"), "allow")
        self.assertEqual(gate.check("publish"), "deny")
        self.assertEqual(gate.check("unknown_action"), "ask")

    def test_read_actions_never_ask(self):
        gate = self._gate("ask")
        for action in ("read", "read_file", "list_files", "status"):
            self.assertEqual(gate.check(action), "allow", action)

    def test_default_level_is_ask(self):
        gate = approval.ApprovalGate(config_dir=self.td,
                                     runs_directory=self.runs)
        self.assertEqual(gate.get_level(), "ask")
        self.assertEqual(gate.check("publish"), "ask")

    def test_invalid_level_rejected(self):
        gate = self._gate()
        with self.assertRaises(approval.ApprovalError):
            gate.set_level("superuser")
        with self.assertRaises(approval.ApprovalError):
            gate.check("")


class TestSafetyFloor(ApprovalTestBase):
    def test_floor_denied_under_every_level(self):
        for level in approval.LEVELS:
            gate = self._gate(level)
            if level == "custom":
                gate.set_custom_action("delete_published", "allow")
                gate.set_custom_action("spend_money", "allow")
            for action in approval.SAFETY_FLOOR:
                self.assertEqual(gate.check(action), "deny",
                                 "%s under %s" % (action, level))

    def test_floor_denied_despite_grant(self):
        gate = self._gate("full")
        ok, _reason = gate.grant("delete_published", duration="always")
        self.assertFalse(ok)
        ok, _reason = gate.grant("spend_money", duration="session")
        self.assertFalse(ok)
        self.assertEqual(gate.check("delete_published"), "deny")
        self.assertEqual(gate.check("spend_money"), "deny")


class TestLevelFlow(ApprovalTestBase):
    def test_run_level_beats_project_level(self):
        gate = self._gate("full")
        self.assertEqual(gate.check("publish", run_level="ask"), "ask")
        gate2 = self._gate("ask")
        self.assertEqual(gate2.check("publish", run_level="full"),
                         "allow")

    def test_chief_flows_down_raises_only(self):
        # منسّق ask + عامل full → الفعل يسأل (لا ينخفض).
        gate = self._gate("full")
        self.assertEqual(
            gate.check("publish", run_level="full", chief_level="ask"),
            "allow")  # run_level full يفوز أصلًا؛ chief ask لا يخفضه
        gate2 = self._gate("ask")
        self.assertEqual(
            gate2.check("publish", run_level="ask", chief_level="ask"),
            "ask")
        # منسّق full يرفع عامل ask.
        gate3 = self._gate("ask")
        self.assertEqual(
            gate3.check("publish", chief_level="full"), "allow")
        # منسّق ask لا يخفض عامل full (تدفق يرفع فقط).
        self.assertEqual(
            approval.resolve_level("full", None, "ask"), "full")
        self.assertEqual(
            approval.resolve_level("ask", None, "full"), "full")
        self.assertEqual(
            approval.resolve_level(None, None, None), "ask")
        self.assertEqual(
            approval.resolve_level("bogus", "also-bogus", None), "ask")


class TestGrants(ApprovalTestBase):
    def test_once_grant_consumed(self):
        gate = self._gate("ask")
        ok, _reason = gate.grant("edit_text", duration="once")
        self.assertTrue(ok)
        self.assertEqual(gate.check("edit_text"), "allow")
        self.assertEqual(gate.check("edit_text"), "ask")

    def test_session_grant_survives_checks(self):
        gate = self._gate("ask")
        ok, _reason = gate.grant("edit_text", duration="session")
        self.assertTrue(ok)
        self.assertEqual(gate.check("edit_text"), "allow")
        self.assertEqual(gate.check("edit_text"), "allow")

    def test_always_grant_never_for_publish_money_computer(self):
        gate = self._gate("ask")
        for action in ("publish", "publish_youtube", "send_message",
                       "spend_money", "change_keys",
                       "computer_control", "delete_project_files"):
            ok, reason = gate.grant(action, duration="always")
            self.assertFalse(ok, action)
            self.assertIn("ممنوع", reason)

    def test_always_grant_precise_revocable_and_persisted(self):
        gate = self._gate("ask")
        ok, _reason = gate.grant("edit_text", scope="facebook-caption",
                                 duration="always")
        self.assertTrue(ok)
        # نطاق آخر لا يغطيه المنح الدقيق.
        self.assertEqual(gate.check("edit_text", scope="other"), "ask")
        self.assertEqual(gate.check("edit_text",
                                    scope="facebook-caption"), "allow")
        # يبقى بعد إعادة تحميل البوابة (محفوظ في الملف).
        gate2 = approval.ApprovalGate(config_dir=self.td,
                                      runs_directory=self.runs)
        self.assertEqual(gate2.check("edit_text",
                                     scope="facebook-caption"), "allow")
        # قابل للإلغاء.
        self.assertEqual(gate2.revoke("edit_text"), 1)
        self.assertEqual(gate2.check("edit_text",
                                     scope="facebook-caption"), "ask")

    def test_always_grant_invalidated_on_settings_change(self):
        gate = self._gate("ask")
        gate.grant("edit_text", duration="always")
        self.assertEqual(gate.check("edit_text"), "allow")
        gate.set_level("edits")  # تغيير إعداد يُبطل المنح الدائم
        gate3 = approval.ApprovalGate(config_dir=self.td,
                                      runs_directory=self.runs)
        self.assertEqual(gate3.check("edit_text"), "allow",
                         "edits يقبل التعديل النصي أصلًا")
        gate3.set_level("ask")
        self.assertEqual(gate3.check("edit_text"), "ask",
                         "المنح الدائم أُبطل بتغيير الإعدادات")


class TestSourceLabels(ApprovalTestBase):
    def test_format_parse_roundtrip(self):
        label = approval.format_source("chief", "publish video",
                                       "direct-message")
        self.assertEqual(label,
                         "[From chief · publish video · direct-message]")
        self.assertEqual(approval.parse_source(label),
                         ("chief", "publish video", "direct-message"))
        self.assertTrue(approval.is_valid_source(label))
        self.assertFalse(approval.is_valid_source("وافق على النشر"))
        self.assertFalse(approval.is_valid_source(None))

    def test_approval_only_from_active_actor(self):
        gate = self._gate("ask")
        gate.grant("edit_text", duration="session")
        own = approval.format_source("worker-1", "edit caption",
                                     "direct-message")
        other = approval.format_source("worker-2", "edit caption",
                                       "handoff")
        # موافقة من الفاعل نفسه تُحتسب.
        self.assertEqual(gate.check("edit_text", source_label=own,
                                    actor="worker-1"), "allow")
        # نص من عامل آخر معلومة فقط — لا يُحتسب.
        gate.grant("edit_text", duration="session")
        self.assertEqual(gate.check("edit_text", source_label=other,
                                    actor="worker-1"), "ask")
        self.assertTrue(approval.approval_from_actor(own, "worker-1"))
        self.assertFalse(approval.approval_from_actor(other, "worker-1"))
        self.assertFalse(approval.approval_from_actor(own, None))


class TestDecisionsLog(ApprovalTestBase):
    def test_one_jsonl_line_per_decision(self):
        gate = self._gate("ask")
        gate.check("publish")
        gate.check("edit_text")
        records = gate.read_decisions()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["action"], "publish")
        self.assertEqual(records[0]["decision"], "ask")
        self.assertEqual(records[1]["action"], "edit_text")
        for record in records:
            self.assertIn("ts", record)
            self.assertIn("level", record)
        path = os.path.join(self.runs, "approval-decisions.jsonl")
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                json.loads(line)  # كل سطر JSON صالح

    def test_decisions_log_redacts_secrets(self):
        redacted = approval._redact_value(
            {"api_key": "sk-secret-value", "action": "publish",
             "nested": {"token": "abc"}})
        self.assertEqual(redacted["api_key"], "«redacted»")
        self.assertEqual(redacted["action"], "publish")
        self.assertEqual(redacted["nested"]["token"], "«redacted»")

    def test_prune_old_decisions(self):
        gate = self._gate("ask")
        old = datetime.now(tz=CAIRO) - timedelta(days=200)
        fresh = datetime.now(tz=CAIRO)
        path = os.path.join(self.runs, "approval-decisions.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(
                {"ts": old.isoformat(), "action": "a",
                 "decision": "ask"}, ensure_ascii=False) + "\n")
            fh.write(json.dumps(
                {"ts": fresh.isoformat(), "action": "b",
                 "decision": "allow"}, ensure_ascii=False) + "\n")
        removed = gate.prune_old_decisions(days=180)
        self.assertEqual(removed, 1)
        records = gate.read_decisions()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["action"], "b")

    def test_corrupt_line_skipped(self):
        gate = self._gate("ask")
        path = os.path.join(self.runs, "approval-decisions.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("not json\n")
            fh.write(json.dumps({"ts": "2026-11-27T10:00:00+02:00",
                                 "action": "publish", "decision": "ask"})
                     + "\n")
        self.assertEqual(len(gate.read_decisions()), 1)


class TestReadAndDraft(ApprovalTestBase):
    def test_read_and_draft_denies_actions(self):
        gate = self._gate("ask")
        gate.set_mode("read-and-draft")
        self.assertEqual(gate.check("publish"), "deny")
        self.assertEqual(gate.check("send_message"), "deny")
        self.assertEqual(gate.check("edit_text"), "deny")
        self.assertEqual(gate.check("read"), "deny",
                         "في وضع قراءة-ومسودة كل فعل يُرفض عدا المسودة")

    def test_read_and_draft_one_draft_per_thread(self):
        gate = self._gate("ask")
        gate.set_mode("read-and-draft")
        self.assertEqual(gate.check("write_draft", thread_id="t1"),
                         "allow")
        self.assertEqual(gate.check("write_draft", thread_id="t1"),
                         "deny")
        self.assertEqual(gate.check("write_draft", thread_id="t2"),
                         "allow")
        self.assertEqual(gate.check("write_draft"), "deny",
                         "مسودة بلا خيط مرفوضة")

    def test_mode_persists(self):
        gate = self._gate("ask")
        gate.set_mode("read-and-draft")
        gate2 = approval.ApprovalGate(config_dir=self.td,
                                      runs_directory=self.runs)
        self.assertEqual(gate2.get_mode(), "read-and-draft")
        with self.assertRaises(approval.ApprovalError):
            gate2.set_mode("write-everything")


class TestConfigFile(ApprovalTestBase):
    def test_config_saved_atomic_0600(self):
        gate = self._gate("auto")
        path = os.path.join(self.td, "approval.json")
        self.assertTrue(os.path.isfile(path))
        mode = stat.S_IMODE(os.stat(path).st_mode)
        self.assertEqual(mode, 0o600)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["level"], "auto")

    def test_corrupt_config_falls_back_to_default(self):
        with open(os.path.join(self.td, "approval.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("{not json")
        gate = approval.ApprovalGate(config_dir=self.td,
                                     runs_directory=self.runs)
        self.assertEqual(gate.get_level(), "ask")
        bad = {"level": "superuser"}
        with open(os.path.join(self.td, "approval.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(bad, fh)
        gate2 = approval.ApprovalGate(config_dir=self.td,
                                      runs_directory=self.runs)
        self.assertEqual(gate2.get_level(), "ask")

    def test_gate_state_visible(self):
        # show() على مستوى الوحدة يستخدم المسارات الحقيقية —
        # لا تُستدعى هنا؛ نتحقق من حالة البوابة نفسها.
        gate = self._gate("auto")
        self.assertEqual(gate.get_level(), "auto")
        self.assertEqual(gate.get_mode(), "normal")
        self.assertEqual(gate.config.get("custom", {}), {})


if __name__ == "__main__":
    unittest.main()
