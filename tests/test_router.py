#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات موجّه النماذج (lib/router) — بند 5 + بند 32.

بلا شبكة حقيقية: الموجّه يُحقن كدالة وهمية، والسجلات
في مجلدات مؤقتة.
"""
import json
import os
import stat
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import router


ROLES = [
    {"name": "المولّد", "model": "gemini-flash-lite",
     "effort": "medium"},
    {"name": "المراجع", "model": "gemini-flash",
     "effort": "high"},
]
DEFAULT = {"model": "gemini-flash", "effort": "medium"}


def _decider_ok(state):
    return {"model": "gemini-flash-lite", "effort": "low",
            "confidence": 0.94}


class TestClip(unittest.TestCase):
    def test_clip_each_field_at_its_limit(self):
        self.assertEqual(len(router.clip_name("x" * 200)),
                         router.CLIP_NAME)
        self.assertEqual(len(router.clip_title("x" * 200)),
                         router.CLIP_TITLE)
        self.assertEqual(len(router.clip_description("x" * 500)),
                         router.CLIP_DESCRIPTION)
        self.assertEqual(len(router.clip_line("x" * 600)),
                         router.CLIP_LINE)
        self.assertEqual(len(router.clip_request("x" * 9000)),
                         router.CLIP_REQUEST)
        self.assertEqual(router.clip_name("abc"), "abc")

    def test_clip_none_is_empty(self):
        self.assertEqual(router.clip(None, 10), "")
        self.assertEqual(router.clip_context(None), "")

    def test_clip_context_takes_newest_backwards(self):
        # ثلاثة أسطر (2000 حرف لكلٍّ) + فاصلان = 6002 > 6000،
        # فيُؤخذ الأحدثان كاملين ويُستبعد الأقدم.
        lines = ["A" * 2000, "B" * 2000, "C" * 2000]
        clipped = router.clip_context(lines)
        self.assertTrue(clipped.endswith("C" * 2000))
        self.assertIn("B" * 2000, clipped)
        self.assertNotIn("A", clipped)
        self.assertLessEqual(len(clipped), router.CLIP_CONTEXT)

    def test_clip_context_string_takes_tail(self):
        text = "a" * 4000 + "b" * 4000
        clipped = router.clip_context(text)
        self.assertEqual(len(clipped), router.CLIP_CONTEXT)
        self.assertEqual(clipped, "a" * 2000 + "b" * 4000)
        self.assertTrue(clipped.endswith("b" * 4000))

    def test_clip_context_single_huge_line_takes_tail(self):
        clipped = router.clip_context(["z" * 9000])
        self.assertEqual(clipped, "z" * router.CLIP_CONTEXT)

    def test_build_state_clips_everything(self):
        state = router.build_state(
            "مهمة " * 300, ROLES,
            ["سطر " * 2000, "سطر " * 2000, "سطر " * 2000],
            "طلب " * 3000)
        self.assertLessEqual(len(state["task"]), router.CLIP_LINE)
        self.assertLessEqual(len(state["new_message"]),
                             router.CLIP_REQUEST)
        self.assertLessEqual(len(state["recent_messages"]),
                             router.CLIP_CONTEXT)
        self.assertEqual(len(state["roles"]), 2)
        self.assertLessEqual(len(state["roles"][0]["name"]),
                             router.CLIP_NAME)


class TestRoute(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log_dir = os.path.join(self.tmp.name, "decider-log")

    def tearDown(self):
        self.tmp.cleanup()

    def _route(self, decider=_decider_ok, **kwargs):
        kwargs.setdefault("log_dir", self.log_dir)
        kwargs.setdefault("now", "2026-11")
        # إعداد صريح حتى لا يقرأ الاختبار إعداد البيت الحقيقي.
        kwargs.setdefault("config", {"provider": "gemini-flash-lite",
                                     "threshold": 0.6})
        return router.route("ولّد قصة", ROLES, ["سياق"],
                            "اكتب قصة قصيرة", DEFAULT,
                            decider=decider, **kwargs)

    def test_choice_above_threshold(self):
        result = self._route()
        self.assertEqual(result["source"], "router")
        self.assertEqual(result["model"], "gemini-flash-lite")
        self.assertEqual(result["effort"], "low")
        self.assertAlmostEqual(result["confidence"], 0.94)
        self.assertEqual(result["attribution"],
                         "Picked by gemini-flash-lite · 94%")
        self.assertIsNone(result["reason"])

    def test_fail_open_on_decider_exception(self):
        def boom(state):
            raise RuntimeError("انقطع المزوّد")
        result = self._route(decider=boom)
        self.assertEqual(result["source"], "fallback")
        self.assertEqual(result["model"], DEFAULT["model"])
        self.assertEqual(result["reason"], "provider_error")

    def test_fail_open_on_timeout(self):
        def slow(state):
            time.sleep(3)
            return {"model": "gemini-flash-lite", "effort": "low",
                    "confidence": 0.99}
        started = time.monotonic()
        result = self._route(decider=slow)
        elapsed = time.monotonic() - started
        self.assertEqual(result["source"], "fallback")
        self.assertEqual(result["reason"], "timeout")
        self.assertLess(elapsed, 2.5)

    def test_low_confidence_falls_back(self):
        def unsure(state):
            return {"model": "gemini-flash-lite", "effort": "low",
                    "confidence": 0.5}
        result = self._route(decider=unsure)
        self.assertEqual(result["source"], "fallback")
        self.assertEqual(result["reason"], "low_confidence")

    def test_confidence_at_threshold_accepted(self):
        def edge(state):
            return {"model": "gemini-flash", "effort": "high",
                    "confidence": 0.6}
        result = self._route(decider=edge)
        self.assertEqual(result["source"], "router")
        self.assertEqual(result["model"], "gemini-flash")

    def test_unoffered_choice_rejected(self):
        def wrong(state):
            return {"model": "gpt-99", "effort": "low",
                    "confidence": 0.99}
        result = self._route(decider=wrong)
        self.assertEqual(result["source"], "fallback")
        self.assertEqual(result["reason"], "no_choice")

    def test_non_numeric_confidence_rejected(self):
        def bad(state):
            return {"model": "gemini-flash-lite", "effort": "low",
                    "confidence": "عالية"}
        result = self._route(decider=bad)
        self.assertEqual(result["source"], "fallback")
        self.assertEqual(result["reason"], "malformed")

    def test_malformed_decision_rejected(self):
        for bad in (None, "gemini-flash-lite", {},
                    {"model": "gemini-flash-lite"}):
            result = self._route(decider=lambda s, b=bad: b)
            self.assertEqual(result["source"], "fallback",
                             bad)
            self.assertEqual(result["reason"], "malformed")

    def test_no_decider_falls_back_without_raising(self):
        result = self._route(decider=None)
        self.assertEqual(result["source"], "fallback")
        self.assertEqual(result["reason"], "no_choice")
        self.assertEqual(result["model"], DEFAULT["model"])

    def test_route_never_raises(self):
        # أدوار تالفة + افتراضي تالف + موجّه يرمي: لا رفع أبدًا.
        result = router.route(None, None, None, None, None,
                              decider=lambda s: 1 / 0,
                              log_dir=self.log_dir)
        self.assertEqual(result["source"], "fallback")
        self.assertIn("reason", result)

    def test_log_has_no_request_text_or_key(self):
        probe = "مفتاح-" + "سري-" + "للاختبار-12345"
        request = "اكتب قصة عن %s" % probe
        router.route("مهمة", ROLES, ["سياق"], request, DEFAULT,
                     decider=_decider_ok, log_dir=self.log_dir,
                     config={"provider": "gemini-flash-lite",
                             "threshold": 0.6},
                     now="2026-11")
        path = os.path.join(self.log_dir, "2026-11.ndjson")
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        self.assertEqual(len(lines), 1)
        entry = json.loads(lines[0])
        self.assertNotIn(probe, lines[0])
        self.assertNotIn("اكتب قصة", lines[0])
        self.assertEqual(len(entry["state_hash"]), 16)
        self.assertEqual(entry["model"], "gemini-flash-lite")
        self.assertIsNone(entry["reason"])
        mode = stat.S_IMODE(os.stat(path).st_mode)
        self.assertEqual(mode, 0o600)

    def test_log_records_failure_reason_only(self):
        def failing(state):
            raise RuntimeError("429")
        router.route("مهمة", ROLES, ["سياق"], "طلب سري",
                     DEFAULT, decider=failing,
                     log_dir=self.log_dir,
                     config={"provider": "gemini-flash-lite",
                             "threshold": 0.6},
                     now="2026-11")
        with open(os.path.join(self.log_dir, "2026-11.ndjson"),
                  encoding="utf-8") as fh:
            entry = json.loads(fh.read().splitlines()[0])
        self.assertEqual(entry["reason"], "provider_error")
        self.assertEqual(entry["source"], "fallback")
        self.assertNotIn("طلب سري", json.dumps(entry))


class TestConfig(unittest.TestCase):
    def test_load_config_defaults_when_missing(self):
        config = router.load_config(
            path=os.path.join(tempfile.gettempdir(),
                              "no-such-router-config.json"))
        self.assertEqual(config["threshold"],
                         router.DEFAULT_THRESHOLD)
        self.assertIsNone(config["key_ref"])

    def test_load_config_rejects_plain_key(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False,
                encoding="utf-8") as fh:
            json.dump({"provider": "gemini-flash",
                       "threshold": 0.7,
                       "key": "sk-plain-secret"}, fh)
            path = fh.name
        try:
            config = router.load_config(path=path)
        finally:
            os.remove(path)
        self.assertIsNone(config["key_ref"])
        self.assertEqual(config["threshold"], 0.7)

    def test_load_config_accepts_env_ref(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False,
                encoding="utf-8") as fh:
            json.dump({"key": {"env": "GEMINI_API_KEY"}}, fh)
            path = fh.name
        try:
            config = router.load_config(path=path)
        finally:
            os.remove(path)
        self.assertEqual(config["key_ref"],
                         {"env": "GEMINI_API_KEY"})

    def test_key_ref_rejects_bad_shapes(self):
        self.assertIsNone(router.key_ref({"key": "plain"}))
        self.assertIsNone(router.key_ref({"key": {}}))
        self.assertIsNone(router.key_ref({"key": {"env": "  "}}))
        self.assertEqual(router.key_ref(
            {"key": {"file": "/tmp/k.txt"}}),
            {"file": "/tmp/k.txt"})


class TestPrune(unittest.TestCase):
    def test_prune_deletes_older_than_180_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("2026-04.ndjson", "2026-05.ndjson",
                         "2026-11.ndjson", "notes.txt",
                         "bad-name.ndjson"):
                with open(os.path.join(tmp, name), "w",
                          encoding="utf-8") as fh:
                    fh.write("{}\n")
            now = time.struct_time((2026, 11, 27, 0, 0, 0, 0, 0, 0))
            deleted = router.prune_old_logs(
                log_dir=tmp, retention_days=180, now=now)
            # القطع: 2026-11-01 ناقص 180 يومًا ≈ 2026-05-05،
            # فيُحذف 2026-04 فقط ويبقى 2026-05.
            self.assertEqual(deleted, ["2026-04.ndjson"])
            self.assertFalse(os.path.exists(
                os.path.join(tmp, "2026-04.ndjson")))
            self.assertTrue(os.path.exists(
                os.path.join(tmp, "2026-05.ndjson")))
            self.assertTrue(os.path.exists(
                os.path.join(tmp, "2026-11.ndjson")))
            self.assertTrue(os.path.exists(
                os.path.join(tmp, "notes.txt")))

    def test_prune_missing_dir_returns_empty(self):
        self.assertEqual(router.prune_old_logs(
            log_dir=os.path.join(tempfile.gettempdir(),
                                 "no-such-decider-log")), [])


if __name__ == "__main__":
    unittest.main()
