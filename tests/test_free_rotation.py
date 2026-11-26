#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات منهجية تناوب المسار المجاني — جولة v0.1.41 (بند 2
من استخراج AlphaCLI).

أهلية بالسعر على المحورين معًا (سعر مفقود = ليس مجانيًا
أبدًا)؛ وتدوير عند 429 إلى النموذج المجاني التالي بدل إعادة
المحاولة على النموذج نفسه؛ واكتشاف حي من /v1/models مع
أرضية مثبّتة لا تنقص أبدًا؛ وعرض اسم المنتج لا هوية المنبع.
كلها محاكاة (نماذج وأسعار و429 وهمية) — بلا شبكة حية وبلا
مفتاح OpenRouter (الاختبار الحي معلّق على المفتاح).
"""
import os
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import llm_state as state_lib
from lib import omniroute_client as client_lib
from lib.omniroute_client import LLMAllFailedError, OmniRouteError


class TestFreePricing(unittest.TestCase):
    def test_both_zero_is_free(self):
        for pricing in ({"prompt": 0, "completion": 0},
                        {"prompt": 0.0, "completion": 0.0},
                        {"prompt": "0", "completion": "0"},
                        {"prompt": "0.00", "completion": "0.00000000"}):
            self.assertTrue(client_lib.is_free_pricing(pricing),
                            pricing)

    def test_either_nonzero_is_not_free(self):
        for pricing in ({"prompt": 0, "completion": 0.0000004},
                        {"prompt": 0.00000005, "completion": 0},
                        {"prompt": 0.01, "completion": 0.01}):
            self.assertFalse(client_lib.is_free_pricing(pricing),
                             pricing)

    def test_priced_alias_excluded(self):
        # حالة انحدار من AlphaCLI: الاسم المستعار المُقاس
        # ‎/small (‏0.00000005/0.0000004) مستبعَد صراحةً.
        self.assertFalse(client_lib.is_free_pricing(
            {"prompt": 0.00000005, "completion": 0.0000004}))

    def test_missing_or_null_price_is_never_free(self):
        for pricing in (None, {}, {"prompt": 0},
                        {"completion": 0},
                        {"prompt": None, "completion": "0"},
                        {"prompt": "0", "completion": None},
                        {"prompt": "0"},
                        "free", 0):
            self.assertFalse(client_lib.is_free_pricing(pricing),
                             pricing)

    def test_non_numeric_price_is_not_free(self):
        self.assertFalse(client_lib.is_free_pricing(
            {"prompt": "free", "completion": "0"}))
        self.assertFalse(client_lib.is_free_pricing(
            {"prompt": "0", "completion": ""}))

    def test_bool_is_not_zero(self):
        self.assertFalse(client_lib.is_free_pricing(
            {"prompt": True, "completion": 0}))


class TestFreeModelIds(unittest.TestCase):
    def _catalog(self):
        return {"data": [
            {"id": "a:free",
             "pricing": {"prompt": "0", "completion": "0"}},
            {"id": "b-paid",
             "pricing": {"prompt": "0.01", "completion": "0.02"}},
            {"id": "c-no-pricing"},
            {"id": "d-null-price",
             "pricing": {"prompt": None, "completion": "0"}},
            {"id": "e:free",
             "pricing": {"prompt": 0, "completion": 0}},
            {"id": "a:free",
             "pricing": {"prompt": "0", "completion": "0"}},
            {"pricing": {"prompt": "0", "completion": "0"}},
            {"id": "  ", "pricing": {"prompt": "0",
                                      "completion": "0"}},
            "not-a-dict",
            {"id": "f:free",
             "pricing": {"prompt": "0.00000005",
                         "completion": "0.0000004"}},
            {"id": "openrouter/free",
             "pricing": {"prompt": "0", "completion": "0"}},
        ]}

    def test_dict_catalog_filters_by_price(self):
        self.assertEqual(
            client_lib.free_model_ids(self._catalog()),
            ["a:free", "e:free", "openrouter/free"])

    def test_bare_list_accepted(self):
        self.assertEqual(
            client_lib.free_model_ids(self._catalog()["data"]),
            ["a:free", "e:free", "openrouter/free"])

    def test_bad_shapes_return_empty(self):
        for catalog in (None, {}, {"data": "x"}, {"data": [None]},
                        {"other": []}, "x"):
            self.assertEqual(client_lib.free_model_ids(catalog), [])

    def test_free_suffix_but_priced_is_excluded(self):
        # لاحقة :free لا تكفي وحدها — الأهلية بالسعر لا بالاسم.
        catalog = {"data": [
            {"id": "x:free",
             "pricing": {"prompt": "0.001", "completion": "0"}}]}
        self.assertEqual(client_lib.free_model_ids(catalog), [])

    def test_is_free_model_entry(self):
        self.assertTrue(client_lib.is_free_model(
            {"id": "a:free",
             "pricing": {"prompt": "0", "completion": "0"}}))
        self.assertFalse(client_lib.is_free_model(
            {"id": "b"}))
        self.assertFalse(client_lib.is_free_model("a:free"))
        self.assertFalse(client_lib.is_free_model(None))


class TestMergeFreeModels(unittest.TestCase):
    def test_floor_never_shrinks(self):
        floor = ("openrouter/free", "z:free")
        self.assertEqual(
            client_lib.merge_free_models(["a:free"], floor),
            ["a:free", "openrouter/free", "z:free"])
        # اكتشاف فارغ ← الأرضية وحدها، لا قائمة فارغة.
        self.assertEqual(
            client_lib.merge_free_models([], floor), list(floor))
        self.assertEqual(
            client_lib.merge_free_models(None, floor), list(floor))

    def test_no_duplicates_and_discovered_first(self):
        self.assertEqual(
            client_lib.merge_free_models(
                ["openrouter/free", "a:free"],
                ("openrouter/free", "b:free")),
            ["openrouter/free", "a:free", "b:free"])

    def test_default_floor_is_pinned_alias(self):
        self.assertEqual(client_lib.PINNED_FREE_MODELS,
                         ("openrouter/free",))
        self.assertEqual(
            client_lib.merge_free_models(["a:free"]),
            ["a:free", "openrouter/free"])


class TestDiscoverFreeModels(unittest.TestCase):
    def _catalog(self):
        return {"data": [
            {"id": "a:free",
             "pricing": {"prompt": "0", "completion": "0"}},
            {"id": "b-paid",
             "pricing": {"prompt": "0.01", "completion": "0"}},
        ]}

    def test_live_discovery_merges_with_floor(self):
        seen = {}

        def fetcher(url, headers, timeout):
            seen["url"] = url
            seen["headers"] = headers
            return self._catalog()

        models = client_lib.discover_free_models(
            "https://openrouter.ai/api/v1", fetcher=fetcher)
        self.assertEqual(models, ["a:free", "openrouter/free"])
        self.assertEqual(seen["url"],
                         "https://openrouter.ai/api/v1/v1/models")
        self.assertEqual(seen["headers"],
                         {"Accept": "application/json"})

    def test_api_key_sent_as_bearer(self):
        seen = {}

        def fetcher(url, headers, timeout):
            seen["headers"] = headers
            return self._catalog()

        client_lib.discover_free_models(
            "https://openrouter.ai/api/v1", api_key="k-1",
            fetcher=fetcher)
        self.assertEqual(seen["headers"]["Authorization"],
                         "Bearer k-1")

    def test_failed_discovery_returns_floor_only(self):
        def raising(url, headers, timeout):
            raise urllib.error.URLError("no network")

        def http_error(url, headers, timeout):
            raise urllib.error.HTTPError(
                url, 500, "boom", {}, None)

        for fetcher in (raising, http_error):
            self.assertEqual(
                client_lib.discover_free_models(
                    "https://openrouter.ai/api/v1",
                    fetcher=fetcher),
                ["openrouter/free"])

    def test_bad_catalog_shape_returns_floor_only(self):
        for catalog in ({"nonsense": 1}, None, "x"):
            self.assertEqual(
                client_lib.discover_free_models(
                    "https://openrouter.ai/api/v1",
                    fetcher=lambda u, h, t, c=catalog: c),
                ["openrouter/free"])

    def test_custom_floor_respected(self):
        self.assertEqual(
            client_lib.discover_free_models(
                "https://example.invalid/v1",
                fetcher=lambda u, h, t: (_ for _ in ()).throw(
                    urllib.error.URLError("down")),
                floor=("my:free",)),
            ["my:free"])


class TestFreeRotationProviders(unittest.TestCase):
    def test_builds_flagged_providers(self):
        self.assertEqual(
            client_lib.free_rotation_providers(
                ["a:free", "b:free"]),
            [{"kind": "omniroute", "model": "a:free",
              "free_rotation": True},
             {"kind": "omniroute", "model": "b:free",
              "free_rotation": True}])

    def test_blanks_skipped(self):
        self.assertEqual(
            client_lib.free_rotation_providers(
                ["a:free", "", "  ", None, "b:free"]),
            [{"kind": "omniroute", "model": "a:free",
              "free_rotation": True},
             {"kind": "omniroute", "model": "b:free",
              "free_rotation": True}])
        self.assertEqual(client_lib.free_rotation_providers([]), [])
        self.assertEqual(client_lib.free_rotation_providers(None), [])


class TestFreeRotationChain(unittest.TestCase):
    MODELS = ["m1:free", "m2:free", "m3:free"]

    def _fake_cli(self, outcomes):
        """outcomes: {model: [رد | OmniRouteError, ...]} — كل
        استدعاء يستهلك أول عنصر؛ نفاد القائمة = نجاح عام."""
        calls = []

        def fake(model, *args, **kwargs):
            calls.append(model)
            queue = outcomes.get(model) or []
            if queue:
                item = queue.pop(0)
                if isinstance(item, Exception):
                    raise item
                return item
            return "رد %s" % model

        fake.calls = calls
        return fake

    def test_429_rotates_to_next_free_model(self):
        state = state_lib.default_state()
        seen = []

        def on_attempt(provider, ok, kind):
            # نفس توصيلة studio.py: تسجيل الحالة الحقيقي.
            state_lib.record_attempt(state, provider, ok, kind)
            seen.append((provider, ok, kind))

        fake = self._fake_cli({
            "m1:free": [OmniRouteError("HTTP 429: Too Many Requests")],
            "m2:free": ["رد الثاني"],
        })
        with mock.patch.object(client_lib, "chat_cli",
                               side_effect=fake):
            text, via, model = client_lib.chat_free_rotation(
                "مرحبا", self.MODELS[:2], system="نظام",
                retries=2, retry_delay=0, state=state,
                on_attempt=on_attempt)
        # لا إعادة محاولة على m1 رغم retries=2 — دوّر فورًا.
        self.assertEqual(fake.calls, ["m1:free", "m2:free"])
        self.assertEqual((text, via), ("رد الثاني", "cli"))
        # اسم المنتج للمستخدم لا معرّف المنبع.
        self.assertEqual(model, client_lib.FREE_LANE_DISPLAY_NAME)
        self.assertEqual(model, "المسار المجاني")
        # التدوير مسجَّل في الحالة: عدّاد + تهدئة لـ m1.
        entry = state["providers"]["m1:free"]
        self.assertEqual(entry.get("free_rotations"), 1)
        self.assertIn("last_free_rotation_at", entry)
        cooling, remaining = state_lib.cooling_down(state, "m1:free")
        self.assertTrue(cooling)
        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, state_lib.COOLDOWN_SECONDS)
        # on_attempt مرة واحدة لكل نموذج (بلا ازدواج في العدّ).
        self.assertEqual(seen, [("m1:free", False, "quota"),
                                ("m2:free", True, None)])
        self.assertEqual(state["daily"]["failures"]["m1:free"], 1)

    def test_429_on_two_models_then_third_wins(self):
        fake = self._fake_cli({
            "m1:free": [OmniRouteError("HTTP 429")],
            "m2:free": [OmniRouteError("rate limit exceeded")],
            "m3:free": ["رد الثالث"],
        })
        with mock.patch.object(client_lib, "chat_cli",
                               side_effect=fake):
            text, via, model = client_lib.chat_free_rotation(
                "مرحبا", self.MODELS, system="نظام",
                retries=1, retry_delay=0)
        self.assertEqual(fake.calls, self.MODELS)
        self.assertEqual(text, "رد الثالث")

    def test_429_skips_http_attempt_of_same_model(self):
        # مع مفتاح OmniRoute توجد محاولة HTTP لكل نموذج بعد
        # CLI — التدوير بعد 429 يتخطاها كلها للنموذج نفسه.
        fake_cli = self._fake_cli({
            "m1:free": [OmniRouteError("HTTP 429")],
            "m2:free": [OmniRouteError("HTTP 429")],
        })
        with mock.patch.object(client_lib, "chat_cli",
                               side_effect=fake_cli), \
             mock.patch.object(client_lib, "chat_http",
                               return_value="رد HTTP") as http, \
             mock.patch.dict(os.environ,
                             {"OMNIROUTE_API_KEY": "x"}):
            with self.assertRaises(LLMAllFailedError) as ctx:
                client_lib.chat_free_rotation(
                    "مرحبا", self.MODELS[:2], system="نظام",
                    retries=0, retry_delay=0)
        self.assertEqual(fake_cli.calls, ["m1:free", "m2:free"])
        http.assert_not_called()
        # فشل واحد لكل نموذج (لا تكرار CLI+HTTP).
        self.assertEqual(len(ctx.exception.failures), 2)
        self.assertEqual(
            {p: k for p, k, _d in ctx.exception.failures},
            {"m1:free": "quota", "m2:free": "quota"})

    def test_non_quota_error_still_retries_same_model(self):
        # التدوير عند 429 فقط — خطأ 5xx يُعاد كالمعتاد.
        state = state_lib.default_state()
        fake = self._fake_cli({
            "m1:free": [OmniRouteError("HTTP 503 overloaded"),
                        OmniRouteError("HTTP 503 overloaded")],
            "m2:free": ["رد الثاني"],
        })
        with mock.patch.object(client_lib, "chat_cli",
                               side_effect=fake):
            text, via, model = client_lib.chat_free_rotation(
                "مرحبا", self.MODELS[:2], system="نظام",
                retries=1, retry_delay=0, state=state)
        self.assertEqual(fake.calls,
                         ["m1:free", "m1:free", "m2:free"])
        self.assertEqual(text, "رد الثاني")
        # بلا تدوير مسجَّل لـ m1 (خطأ خادم لا حصة).
        self.assertNotIn("free_rotations",
                         state["providers"].get("m1:free", {}))

    def test_all_429_raises_with_cooldowns(self):
        state = state_lib.default_state()
        fake = self._fake_cli({
            "m1:free": [OmniRouteError("HTTP 429")],
            "m2:free": [OmniRouteError("HTTP 429")],
        })
        with mock.patch.object(client_lib, "chat_cli",
                               side_effect=fake):
            with self.assertRaises(LLMAllFailedError) as ctx:
                client_lib.chat_free_rotation(
                    "مرحبا", self.MODELS[:2], system="نظام",
                    retries=1, retry_delay=0, state=state)
        self.assertEqual(len(ctx.exception.failures), 2)
        for model in self.MODELS[:2]:
            cooling, _ = state_lib.cooling_down(state, model)
            self.assertTrue(cooling, model)
            self.assertEqual(
                state["providers"][model].get("free_rotations"), 1)

    def test_cooled_down_model_skipped_on_next_call(self):
        state = state_lib.default_state()
        fake = self._fake_cli({
            "m1:free": [OmniRouteError("HTTP 429")],
            "m2:free": ["رد الثاني"],
        })
        with mock.patch.object(client_lib, "chat_cli",
                               side_effect=fake):
            client_lib.chat_free_rotation(
                "مرحبا", self.MODELS[:2], system="نظام",
                retries=0, retry_delay=0, state=state)
            # المكالمة الثانية: m1 في تهدئة فيُتخطى مباشرة.
            text, via, model = client_lib.chat_free_rotation(
                "مرحبا", self.MODELS[:2], system="نظام",
                retries=0, retry_delay=0, state=state)
        self.assertEqual(fake.calls,
                         ["m1:free", "m2:free", "m2:free"])
        # المكالمة الثانية نجحت من m2 مباشرة (الرد العام
        # للمحاكي بعد استهلاك «رد الثاني» في الأولى).
        self.assertEqual(text, "رد m2:free")

    def test_empty_models_raises(self):
        with self.assertRaises(OmniRouteError):
            client_lib.chat_free_rotation("مرحبا", [])
        with self.assertRaises(OmniRouteError):
            client_lib.chat_free_rotation("مرحبا", None)

    def test_non_rotation_chain_still_retries_same_model(self):
        # عقد السلسلة العادية محفوظ: 429 بلا علَم تدوير يُعاد
        # على النموذج نفسه retries مرة.
        providers = [{"kind": "omniroute", "model": "m1"},
                     {"kind": "gemini",
                      "model": "gemini-3-flash-preview"}]
        calls = []

        def fake_cli(model, *args, **kwargs):
            calls.append(model)
            raise OmniRouteError("HTTP 429")

        with mock.patch.object(client_lib, "chat_cli",
                               side_effect=fake_cli), \
             mock.patch.object(client_lib, "chat_gemini",
                               return_value="رد Gemini"):
            text, via, model = client_lib.chat_chain(
                "مرحبا", providers, system="نظام",
                retries=1, retry_delay=0)
        self.assertEqual(calls, ["m1", "m1"])
        self.assertEqual((text, via, model),
                         ("رد Gemini", "gemini",
                          "gemini-3-flash-preview"))


class TestRunAttemptsRetryPolicy(unittest.TestCase):
    """جولة الأنماط W1: _run_attempts على سياسة retry_policy
    الموحّدة — أخطاء منطقية بلا إعادة، و429 تُعاد، وRetry-After
    طويل لا يُنام."""

    def _providers(self):
        return [{"kind": "omniroute", "model": "m1"},
                {"kind": "gemini",
                 "model": "gemini-3-flash-preview"}]

    def test_auth_error_never_retried(self):
        calls = []

        def fake_cli(model, *args, **kwargs):
            calls.append(model)
            raise OmniRouteError("HTTP 401 Unauthorized")

        with mock.patch.object(client_lib, "chat_cli",
                               side_effect=fake_cli), \
             mock.patch.object(client_lib, "chat_gemini",
                               return_value="رد Gemini"):
            text, via, model = client_lib.chat_chain(
                "مرحبا", self._providers(), system="نظام",
                retries=2, retry_delay=0)
        # 401 لا تُعاد أبدًا رغم retries=2 — استدعاء واحد فقط.
        self.assertEqual(calls, ["m1"])
        self.assertEqual(text, "رد Gemini")

    def test_403_error_never_retried(self):
        calls = []

        def fake_cli(model, *args, **kwargs):
            calls.append(model)
            raise OmniRouteError("HTTP 403 Forbidden")

        with mock.patch.object(client_lib, "chat_cli",
                               side_effect=fake_cli), \
             mock.patch.object(client_lib, "chat_gemini",
                               return_value="رد Gemini"):
            client_lib.chat_chain("مرحبا", self._providers(),
                                  system="نظام", retries=2,
                                  retry_delay=0)
        self.assertEqual(calls, ["m1"])

    def test_429_retried_then_success(self):
        calls = []

        def fake_cli(model, *args, **kwargs):
            calls.append(model)
            if len(calls) == 1:
                raise OmniRouteError("HTTP 429 Too Many Requests")
            return "رد بعد 429"

        with mock.patch.object(client_lib, "chat_cli",
                               side_effect=fake_cli):
            text, via, model = client_lib.chat_chain(
                "مرحبا", self._providers(), system="نظام",
                retries=1, retry_delay=0)
        self.assertEqual(calls, ["m1", "m1"])
        self.assertEqual(text, "رد بعد 429")

    def test_long_retry_after_not_slept(self):
        # Retry-After ‏300 ثانية: لا نوم داخل الكرون — يُسجَّل
        # الفشل ويُنتقل للمزود التالي فورًا.
        calls = []
        sleeps = []

        def fake_cli(model, *args, **kwargs):
            calls.append(model)
            err = OmniRouteError("HTTP 429")
            err.retry_after = 300.0
            raise err

        def fake_sleep(seconds):
            sleeps.append(seconds)

        with mock.patch.object(client_lib, "chat_cli",
                               side_effect=fake_cli), \
             mock.patch.object(client_lib, "chat_gemini",
                               return_value="رد Gemini"), \
             mock.patch.object(client_lib.time, "sleep",
                               side_effect=fake_sleep):
            text, via, model = client_lib.chat_chain(
                "مرحبا", self._providers(), system="نظام",
                retries=2, retry_delay=5)
        self.assertEqual(calls, ["m1"])
        self.assertEqual(sleeps, [])
        self.assertEqual(text, "رد Gemini")


if __name__ == "__main__":
    unittest.main()
