#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات فرز تعليقات/رسائل الصفحة — جولة v0.1.63 (بند 26).

معزولة: عميل نموذج وهمي يُحقن في الدوال — بلا شبكة أبدًا،
وبلا قراءة ملفات خارج الشجرة.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import inbox_triage


class FakeClient:
    """عميل وهمي: يرجع ردودًا معدة سلفًا بالترتيب؛ ويسجّل الاستدعاءات."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, prompt, model, **kwargs):
        self.calls.append((prompt, model))
        if not self.replies:
            raise AssertionError("استدعاء نموذج غير متوقع")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def _reader_reply(sender="أحمد", kind="سؤال", awaits=True):
    return json.dumps({
        "sender": sender,
        "request": "متى الجزء الثاني؟",
        "deadline": None,
        "amount": None,
        "awaits_reply": awaits,
        "kind": kind,
    }, ensure_ascii=False)


def _decider_reply(decision, reason="سبب"):
    return json.dumps({"decision": decision, "reason": reason},
                      ensure_ascii=False)


class TestReader(unittest.TestCase):
    def test_reads_all_fields(self):
        client = FakeClient([_reader_reply()])
        reading = inbox_triage.read_message("متى الجزء الثاني؟",
                                            client=client)
        self.assertEqual(reading["sender"], "أحمد")
        self.assertEqual(reading["request"], "متى الجزء الثاني؟")
        self.assertIsNone(reading["deadline"])
        self.assertIsNone(reading["amount"])
        self.assertTrue(reading["awaits_reply"])
        self.assertEqual(reading["kind"], "سؤال")

    def test_unknown_kind_becomes_other(self):
        client = FakeClient([_reader_reply(kind="لغز")])
        reading = inbox_triage.read_message("نص", client=client)
        self.assertEqual(reading["kind"], "أخرى")

    def test_malformed_json_raises(self):
        client = FakeClient(["ليس json إطلاقًا"])
        with self.assertRaises(inbox_triage.TriageError):
            inbox_triage.read_message("نص", client=client)

    def test_model_failure_raises(self):
        client = FakeClient([RuntimeError("انقطاع")])
        with self.assertRaises(inbox_triage.TriageError):
            inbox_triage.read_message("نص", client=client)


class TestDecider(unittest.TestCase):
    def test_three_decisions(self):
        for decision in ("مهم", "يحتاج ردًا", "تخطٍّ"):
            client = FakeClient([_decider_reply(decision)])
            verdict = inbox_triage.decide({"sender": "أحمد", "kind": "سؤال"},
                                          client=client)
            self.assertEqual(verdict["decision"], decision)

    def test_unknown_decision_raises(self):
        client = FakeClient([_decider_reply("ربما")])
        with self.assertRaises(inbox_triage.TriageError):
            inbox_triage.decide({"sender": "أحمد"}, client=client)

    def test_recent_dismissal_skips_without_model_call(self):
        client = FakeClient([])
        verdict = inbox_triage.decide(
            {"sender": "مزعج", "kind": "سبام"},
            recent_dismissals=["مزعج"], client=client)
        self.assertEqual(verdict["decision"], "تخطٍّ")
        self.assertEqual(client.calls, [])


class TestTriageItem(unittest.TestCase):
    def test_full_flow_classifies(self):
        client = FakeClient([_reader_reply(), _decider_reply("مهم")])
        result = inbox_triage.triage_item(
            {"id": "c1", "text": "قصة رائعة"}, client=client)
        self.assertEqual(result["id"], "c1")
        self.assertEqual(result["status"], "مهم")
        self.assertEqual(result["reading"]["kind"], "سؤال")

    def test_reader_failure_defers_for_next_check(self):
        client = FakeClient([RuntimeError("انقطاع")])
        result = inbox_triage.triage_item(
            {"id": "c2", "text": "نص"}, client=client)
        self.assertEqual(result["status"], "deferred")
        self.assertIsNone(result["decision"])

    def test_decider_failure_defers(self):
        client = FakeClient([_reader_reply(), RuntimeError("انقطاع")])
        result = inbox_triage.triage_item(
            {"id": "c3", "text": "نص"}, client=client)
        self.assertEqual(result["status"], "deferred")

    def test_recent_dismissal_affects_next_decision(self):
        # العنصر الأول من مرسل مرفوض مؤخرًا يُتخطَّى؛ والثاني يُقرر.
        client = FakeClient([
            _reader_reply(sender="مزعج", kind="سبام"),
            _reader_reply(sender="أحمد", kind="سؤال"),
            _decider_reply("يحتاج ردًا"),
        ])
        results = inbox_triage.triage(
            [{"id": "c1", "text": "سبام"}, {"id": "c2", "text": "سؤال"}],
            recent_dismissals=["مزعج"], client=client)
        self.assertEqual(results[0]["status"], "تخطٍّ")
        self.assertEqual(results[1]["status"], "يحتاج ردًا")
        # المقرر استُدعي مرة واحدة فقط (للعنصر الثاني).
        self.assertEqual(len(client.calls), 3)

    def test_triage_mixed_batch(self):
        client = FakeClient([
            _reader_reply(sender="أ", kind="شكوى"),
            _decider_reply("مهم"),
            _reader_reply(sender="ب", kind="مدح"),
            _decider_reply("تخطٍّ"),
            RuntimeError("انقطاع"),
        ])
        results = inbox_triage.triage(
            [{"id": "1", "text": "x"}, {"id": "2", "text": "y"},
             {"id": "3", "text": "z"}], client=client)
        self.assertEqual([r["status"] for r in results],
                         ["مهم", "تخطٍّ", "deferred"])


if __name__ == "__main__":
    unittest.main()
