#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات وحدة توسيع الموجّه — جولة v0.1.54 (تطبيق الأفضل
من مسح TAAFT، عامل W1).

التوسيع وحدها (mock لـ chat_fn) + التوصيل عبر
chat_free_rotation (mock للشبكة) + السقوط النظيف (حصة
ممتلئة/خطأ شبكة/رد فارغ/موسَّع مسقِط لمحتوى الأصل) + أن
الموسَّع لا يغيّر بنية القصة + الدُفعة (فشل عنصر واحد لا
يكسر الباقي). بلا شبكة حية وبلا مفاتيح.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import llm_state
from lib import omniroute_client
from lib import prompt_expand
from lib.prompt_expand import (
    EXPAND_SYSTEM_PROMPT,
    MAX_EXPANDED_CHARS,
    expand_motion_prompt,
    expand_motion_prompts,
)

SHORT = "a man walks in the rain at night"
EXPANDED = ("a man walks slowly in the rain at night, camera tracking "
            "beside him in a low wide shot, cold blue moonlight "
            "reflecting on the wet street, somber mood")


def _fresh_state():
    return llm_state.default_state()


def _fake_chat(text, **kwargs):
    return text


class TestExpandAlone(unittest.TestCase):
    def test_success_returns_expanded(self):
        seen = {}

        def fake(prompt, system=None, max_tokens=None):
            seen["prompt"] = prompt
            seen["system"] = system
            seen["max_tokens"] = max_tokens
            return EXPANDED

        result = expand_motion_prompt(SHORT, chat_fn=fake,
                                      state=_fresh_state())
        self.assertEqual(result["prompt"], EXPANDED)
        self.assertTrue(result["expanded"])
        self.assertIsNone(result["reason"])
        self.assertEqual(seen["prompt"], SHORT)
        self.assertEqual(seen["system"], EXPAND_SYSTEM_PROMPT)
        self.assertEqual(seen["max_tokens"], 300)

    def test_max_tokens_passed_through(self):
        def fake(prompt, system=None, max_tokens=None):
            self.assertEqual(max_tokens, 120)
            return EXPANDED

        result = expand_motion_prompt(SHORT, chat_fn=fake,
                                      state=_fresh_state(),
                                      max_tokens=120)
        self.assertTrue(result["expanded"])

    def test_tuple_reply_uses_first_element(self):
        def fake(prompt, system=None, max_tokens=None):
            return (EXPANDED, "cli", "some-model")

        result = expand_motion_prompt(SHORT, chat_fn=fake,
                                      state=_fresh_state())
        self.assertEqual(result["prompt"], EXPANDED)
        self.assertTrue(result["expanded"])

    def test_invalid_input_raises_value_error(self):
        for bad in ("", "   ", None, 42, ["a man"], b"bytes"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                expand_motion_prompt(bad, chat_fn=_fake_chat,
                                     state=_fresh_state())

    def test_system_prompt_expands_visuals_only(self):
        # الموجّه النظامي بالإنجليزية: تفاصيل بصرية فقط،
        # وممنوع تغيير القصة أو الشخصيات أو الضربات السردية.
        self.assertIn("camera", EXPAND_SYSTEM_PROMPT)
        self.assertIn("lighting", EXPAND_SYSTEM_PROMPT)
        self.assertIn("mood", EXPAND_SYSTEM_PROMPT)
        self.assertIn("Do not change the story content",
                      EXPAND_SYSTEM_PROMPT)
        self.assertIn("do not add or remove any narrative beats",
                      EXPAND_SYSTEM_PROMPT)
        self.assertIn("one single paragraph", EXPAND_SYSTEM_PROMPT)
        # بلا أي عربية في الموجّه النظامي.
        self.assertTrue(all(ord(c) < 128
                            for c in EXPAND_SYSTEM_PROMPT))

    def test_expanded_keeps_story_structure(self):
        # الموسَّع يحفظ كل الكلمات المفتاحية للأصل: لا يسقط
        # محتوى ولا يبدّل الشخصيات/المكان/الزمان.
        result = expand_motion_prompt(
            SHORT, chat_fn=lambda p, system=None, max_tokens=None:
            EXPANDED, state=_fresh_state())
        self.assertTrue(result["expanded"])
        lowered = result["prompt"].lower()
        for word in ("man", "walks", "rain", "night"):
            self.assertIn(word, lowered, word)


class TestFailOpen(unittest.TestCase):
    def test_quota_full_never_calls_chat(self):
        state = _fresh_state()
        for model in prompt_expand.DEFAULT_MODELS:
            llm_state.record_attempt(state, model, False, "quota")
        calls = []

        def fake(prompt, system=None, max_tokens=None):
            calls.append(prompt)
            return EXPANDED

        result = expand_motion_prompt(SHORT, chat_fn=fake,
                                      state=state)
        self.assertEqual(calls, [])
        self.assertEqual(result["prompt"], SHORT)
        self.assertFalse(result["expanded"])
        self.assertIn("الحصة", result["reason"])

    def test_network_error_fails_open(self):
        def fake(prompt, system=None, max_tokens=None):
            raise ConnectionError("شبكة مقطوعة")

        result = expand_motion_prompt(SHORT, chat_fn=fake,
                                      state=_fresh_state())
        self.assertEqual(result["prompt"], SHORT)
        self.assertFalse(result["expanded"])
        self.assertIn("تعذّر توسيع الموجّه", result["reason"])
        # بلا نص رسالة الخطأ الأصلي في السبب.
        self.assertNotIn("مقطوعة", result["reason"])

    def test_empty_reply_fails_open(self):
        for reply in ("", "   ", "\n\n"):
            result = expand_motion_prompt(
                SHORT,
                chat_fn=lambda p, system=None, max_tokens=None: reply,
                state=_fresh_state())
            self.assertEqual(result["prompt"], SHORT, repr(reply))
            self.assertFalse(result["expanded"])
            self.assertIn("فارغ", result["reason"])

    def test_non_text_reply_fails_open(self):
        result = expand_motion_prompt(
            SHORT,
            chat_fn=lambda p, system=None, max_tokens=None: 123,
            state=_fresh_state())
        self.assertEqual(result["prompt"], SHORT)
        self.assertFalse(result["expanded"])

    def test_too_long_expanded_rejected(self):
        long_text = EXPANDED + " " + ("x" * MAX_EXPANDED_CHARS)
        self.assertGreater(len(long_text), MAX_EXPANDED_CHARS)
        result = expand_motion_prompt(
            SHORT,
            chat_fn=lambda p, system=None, max_tokens=None: long_text,
            state=_fresh_state())
        self.assertEqual(result["prompt"], SHORT)
        self.assertFalse(result["expanded"])
        self.assertIn("أطول من الحدّ", result["reason"])

    def test_at_length_cap_accepted(self):
        # حدّ 600 حرف بالضبط يُقبل (مع حفظ الكلمات المفتاحية).
        text = EXPANDED + " " + ("x" * (MAX_EXPANDED_CHARS
                                         - len(EXPANDED) - 1))
        self.assertEqual(len(text), MAX_EXPANDED_CHARS)
        result = expand_motion_prompt(
            SHORT,
            chat_fn=lambda p, system=None, max_tokens=None: text,
            state=_fresh_state())
        self.assertTrue(result["expanded"], result)
        self.assertEqual(result["prompt"], text)

    def test_expanded_dropping_original_content_rejected(self):
        dropped = ("a cat sleeps on a sofa in daylight, static "
                   "camera, warm sunlight, peaceful mood")
        result = expand_motion_prompt(
            SHORT,
            chat_fn=lambda p, system=None, max_tokens=None: dropped,
            state=_fresh_state())
        self.assertEqual(result["prompt"], SHORT)
        self.assertFalse(result["expanded"])
        self.assertIn("أسقط محتوى", result["reason"])

    def test_expanded_identical_to_original_rejected(self):
        result = expand_motion_prompt(
            SHORT,
            chat_fn=lambda p, system=None, max_tokens=None: SHORT,
            state=_fresh_state())
        self.assertEqual(result["prompt"], SHORT)
        self.assertFalse(result["expanded"])
        self.assertIn("بلا تفاصيل", result["reason"])

    def test_state_loaded_from_runs_dir_when_not_passed(self):
        with tempfile.TemporaryDirectory() as runs_dir:
            calls = []

            def fake(prompt, system=None, max_tokens=None):
                calls.append(prompt)
                return EXPANDED

            result = expand_motion_prompt(SHORT, chat_fn=fake,
                                          runs_dir=runs_dir)
            self.assertTrue(result["expanded"])
            self.assertEqual(calls, [SHORT])


class TestFreeRotationWiring(unittest.TestCase):
    def test_default_models_include_working_fallback(self):
        # إصلاح دمج المنسق: `openrouter/free` وحده غير كافٍ —
        # بوابة OmniRoute بلا مزود OpenRouter مهيأ (مفتاحه لم
        # يُحفظ) فيفشل كل استدعاء؛ والبديل ساق الخط اليومي
        # العاملة `ddgw/gpt-5.4-mini` (متحقق حيًا) — بلا مزود
        # جديد وبلا مفتاح جديد. الترتيب مقصود: المسبح المجاني
        # أولًا، وddgw بديلًا.
        self.assertIn("openrouter/free", prompt_expand.DEFAULT_MODELS)
        self.assertIn("ddgw/gpt-5.4-mini", prompt_expand.DEFAULT_MODELS)
        self.assertEqual(prompt_expand.DEFAULT_MODELS[0],
                         "openrouter/free")

    def test_default_call_uses_chat_free_rotation(self):
        state = _fresh_state()
        captured = {}

        def fake_rotation(prompt, models, system=None, max_tokens=None,
                          state=None, on_attempt=None):
            captured["prompt"] = prompt
            captured["models"] = models
            captured["system"] = system
            captured["max_tokens"] = max_tokens
            captured["state"] = state
            captured["on_attempt"] = on_attempt
            return (EXPANDED, "المسار المجاني", "openrouter/free")

        with mock.patch.object(omniroute_client,
                               "chat_free_rotation",
                               side_effect=fake_rotation):
            result = expand_motion_prompt(SHORT, state=state)
        self.assertTrue(result["expanded"])
        self.assertEqual(result["prompt"], EXPANDED)
        self.assertEqual(captured["prompt"], SHORT)
        self.assertEqual(list(captured["models"]),
                         list(prompt_expand.DEFAULT_MODELS))
        self.assertEqual(captured["system"], EXPAND_SYSTEM_PROMPT)
        self.assertEqual(captured["max_tokens"], 300)
        self.assertIs(captured["state"], state)
        self.assertIsNotNone(captured["on_attempt"])

    def test_on_attempt_records_provider_state(self):
        state = _fresh_state()
        captured = {}

        def fake_rotation(prompt, models, system=None, max_tokens=None,
                          state=None, on_attempt=None):
            captured["on_attempt"] = on_attempt
            return (EXPANDED, "cli", "openrouter/free")

        with mock.patch.object(omniroute_client,
                               "chat_free_rotation",
                               side_effect=fake_rotation):
            result = expand_motion_prompt(SHORT, state=state)
        self.assertTrue(result["expanded"])
        # محاكاة ما يفعله _run_attempts: on_attempt لكل مزود
        # بنتيجته النهائية — هنا نجاح واحد.
        captured["on_attempt"]("openrouter/free", True, None)
        self.assertEqual(state["daily"]["calls"]
                         .get("openrouter/free"), 1)
        self.assertEqual(state["daily"]["successes"]
                         .get("openrouter/free"), 1)

    def test_rotation_failure_fails_open(self):
        with mock.patch.object(
                omniroute_client, "chat_free_rotation",
                side_effect=omniroute_client.LLMAllFailedError(
                    [("openrouter/free", "quota", "429")])) \
                as fake_rotation:
            result = expand_motion_prompt(SHORT,
                                          state=_fresh_state())
        self.assertEqual(result["prompt"], SHORT)
        self.assertFalse(result["expanded"])
        fake_rotation.assert_called_once()

    def test_rotation_quota_full_never_calls_rotation(self):
        state = _fresh_state()
        for model in prompt_expand.DEFAULT_MODELS:
            llm_state.record_attempt(state, model, False, "quota")
        with mock.patch.object(omniroute_client,
                               "chat_free_rotation") as fake_rotation:
            result = expand_motion_prompt(SHORT, state=state)
        fake_rotation.assert_not_called()
        self.assertFalse(result["expanded"])
        self.assertEqual(result["prompt"], SHORT)

    def test_rotation_state_saved_to_runs_dir(self):
        state = _fresh_state()
        captured = {}

        def fake_rotation(prompt, models, system=None, max_tokens=None,
                          state=None, on_attempt=None):
            captured["on_attempt"] = on_attempt
            return (EXPANDED, "cli", "openrouter/free")

        with tempfile.TemporaryDirectory() as runs_dir:
            with mock.patch.object(omniroute_client,
                                   "chat_free_rotation",
                                   side_effect=fake_rotation):
                result = expand_motion_prompt(SHORT, state=state,
                                              runs_dir=runs_dir)
            self.assertTrue(result["expanded"])
            captured["on_attempt"]("openrouter/free", True, None)
            saved = llm_state.load_state(runs_dir)
            self.assertEqual(saved["daily"]["calls"]
                             .get("openrouter/free"), 1)


class TestBatch(unittest.TestCase):
    def test_batch_mixed_success_and_failure(self):
        def fake(prompt, system=None, max_tokens=None):
            if "rain" in prompt:
                raise ConnectionError("شبكة")
            return ("a boy plays in the sun at noon, camera circling "
                    "him in a wide shot, bright sunlight, joyful mood")

        items = [{"id": "a", "prompt": SHORT},
                 {"id": "b",
                  "prompt": "a boy plays in the sun at noon"},
                 {"id": "c", "prompt": ""},
                 {"id": "d"}]
        results = expand_motion_prompts(items, chat_fn=fake,
                                        state=_fresh_state())
        self.assertEqual(len(results), 4)
        self.assertEqual([r["id"] for r in results],
                         ["a", "b", "c", "d"])
        # عنصر a فشل شبكة → أصله كما هو، والباقي لم ينكسر.
        self.assertFalse(results[0]["expanded"])
        self.assertEqual(results[0]["expanded_prompt"], SHORT)
        self.assertTrue(results[1]["expanded"])
        self.assertFalse(results[2]["expanded"])
        self.assertIn("فارغ", results[2]["reason"])
        self.assertFalse(results[3]["expanded"])

    def test_batch_preserves_order_and_ids(self):
        results = expand_motion_prompts(
            [{"id": "x", "prompt": SHORT},
             {"prompt": SHORT}],
            chat_fn=lambda p, system=None, max_tokens=None: EXPANDED,
            state=_fresh_state())
        self.assertEqual(results[0]["id"], "x")
        self.assertIsNone(results[1]["id"])
        self.assertTrue(all(r["expanded"] for r in results))

    def test_batch_non_list_raises(self):
        for bad in (None, "x", {"id": "a"}):
            with self.assertRaises(ValueError, msg=repr(bad)):
                expand_motion_prompts(bad)

    def test_batch_empty_list_returns_empty(self):
        self.assertEqual(expand_motion_prompts([]), [])

    def test_batch_non_dict_item_fails_open(self):
        results = expand_motion_prompts(
            ["not a dict", {"id": "ok", "prompt": SHORT}],
            chat_fn=lambda p, system=None, max_tokens=None: EXPANDED,
            state=_fresh_state())
        self.assertFalse(results[0]["expanded"])
        self.assertIsNone(results[0]["id"])
        self.assertTrue(results[1]["expanded"])


if __name__ == "__main__":
    unittest.main()
