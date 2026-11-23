#!/usr/bin/env python3
"""اختبارات سلسلة بدائل LLM — جولة v0.1.38 (FreeLLMAPI).

تصنيف الأخطاء (429/402 حصة مقابل 401 مصادقة)؛ وترتيب
السلسلة والتخطي عند التهدئة؛ والفشل الكلي برسالة عربية؛
والمسار القديم لـ chat() بلا تغيير؛ وchat_gemini عبر
مساعد وهمي (نجاح/429/مفقود).
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import llm_state as state_lib
from lib import omniroute_client as client_lib
from lib.omniroute_client import LLMAllFailedError, OmniRouteError


class TestClassify(unittest.TestCase):
    def test_quota(self):
        for text in ("HTTP 429: Too Many Requests",
                     "HTTP Error 429", "rate limit exceeded",
                     "402 Payment Required", "quota exceeded",
                     "RESOURCE_EXHAUSTED"):
            self.assertEqual(client_lib.classify_llm_error(text),
                             "quota", text)

    def test_auth(self):
        for text in ("HTTP 401 Unauthorized", "HTTP Error 403",
                     "invalid api key", "API key not valid"):
            self.assertEqual(client_lib.classify_llm_error(text),
                             "auth", text)

    def test_server_network_unknown(self):
        self.assertEqual(
            client_lib.classify_llm_error("HTTP 503 overloaded"),
            "server")
        self.assertEqual(
            client_lib.classify_llm_error("connection timed out"),
            "network")
        self.assertEqual(
            client_lib.classify_llm_error("something weird"),
            "unknown")


class TestProvidersFromConfig(unittest.TestCase):
    def test_default_chain_includes_gemini_and_ollama_last(self):
        providers = client_lib.providers_from_config(
            {"model": "ddgw/gpt-5.4-mini",
             "fallback_model": "groq/openai/gpt-oss-120b"})
        self.assertEqual(
            [(p["kind"], p["model"]) for p in providers],
            [("omniroute", "ddgw/gpt-5.4-mini"),
             ("omniroute", "groq/openai/gpt-oss-120b"),
             ("gemini", "gemini-3.1-flash-lite"),
             ("gemini", "gemini-3-flash-preview"),
             ("ollama", "qwen2.5:7b")])
        self.assertEqual(providers[-1]["base_url"],
                         "http://localhost:11434")

    def test_gemini_lite_disabled(self):
        providers = client_lib.providers_from_config(
            {"model": "ddgw/gpt-5.4-mini",
             "fallback_model": "groq/openai/gpt-oss-120b",
             "gemini_lite_enabled": False})
        self.assertEqual(
            [(p["kind"], p["model"]) for p in providers],
            [("omniroute", "ddgw/gpt-5.4-mini"),
             ("omniroute", "groq/openai/gpt-oss-120b"),
             ("gemini", "gemini-3-flash-preview"),
             ("ollama", "qwen2.5:7b")])

    def test_gemini_lite_custom_model(self):
        providers = client_lib.providers_from_config(
            {"model": "m", "gemini_enabled": False,
             "gemini_lite_enabled": False,
             "gemini_lite_model": "gemini-2.0-flash-lite",
             "ollama_enabled": False})
        # النموذج المخصص لا يظهر مع تعطيل الساق
        self.assertEqual(
            [(p["kind"], p["model"]) for p in providers],
            [("omniroute", "m")])
        providers = client_lib.providers_from_config(
            {"model": "m", "ollama_enabled": False,
             "gemini_lite_model": "gemini-2.0-flash-lite"})
        self.assertEqual(
            [(p["kind"], p["model"]) for p in providers],
            [("omniroute", "m"),
             ("gemini", "gemini-2.0-flash-lite"),
             ("gemini", "gemini-3-flash-preview")])

    def test_gemini_disabled(self):
        providers = client_lib.providers_from_config(
            {"model": "ddgw/gpt-5.4-mini", "gemini_enabled": False})
        # المفتاح الرئيسي يُسقط ساقي Gemini معًا (Lite + رئيسي)
        self.assertEqual(
            [(p["kind"], p["model"]) for p in providers],
            [("omniroute", "ddgw/gpt-5.4-mini"),
             ("ollama", "qwen2.5:7b")])

    def test_ollama_disabled(self):
        providers = client_lib.providers_from_config(
            {"model": "ddgw/gpt-5.4-mini", "ollama_enabled": False})
        self.assertEqual(
            [(p["kind"], p["model"]) for p in providers],
            [("omniroute", "ddgw/gpt-5.4-mini"),
             ("gemini", "gemini-3.1-flash-lite"),
             ("gemini", "gemini-3-flash-preview")])

    def test_ollama_custom_model_and_url(self):
        providers = client_lib.providers_from_config(
            {"model": "m", "gemini_enabled": False,
             "ollama_model": "llama3.1:8b",
             "ollama_base_url": "http://127.0.0.1:11434"})
        self.assertEqual(providers[-1],
                         {"kind": "ollama", "model": "llama3.1:8b",
                          "base_url": "http://127.0.0.1:11434"})

    def test_dedup(self):
        providers = client_lib.providers_from_config(
            {"model": "m", "fallback_model": "m",
             "gemini_enabled": False})
        # الموديل المكرر ساق واحدة فقط + ساق Ollama الافتراضية
        self.assertEqual(
            [(p["kind"], p["model"]) for p in providers],
            [("omniroute", "m"), ("ollama", "qwen2.5:7b")])


class TestChatChain(unittest.TestCase):
    def _providers(self):
        return [{"kind": "omniroute", "model": "ddgw/gpt-5.4-mini"},
                {"kind": "gemini", "model": "gemini-3-flash-preview"}]

    def test_second_provider_wins(self):
        with mock.patch.object(
                client_lib, "chat_cli",
                side_effect=OmniRouteError("HTTP 429")) as cli, \
             mock.patch.object(
                 client_lib, "chat_gemini",
                 return_value="رد Gemini") as gem:
            text, via, model = client_lib.chat_chain(
                "مرحبا", self._providers(), retries=0)
        self.assertEqual((text, via, model),
                         ("رد Gemini", "gemini",
                          "gemini-3-flash-preview"))
        cli.assert_called_once()
        gem.assert_called_once()

    def test_cooling_down_provider_skipped(self):
        state = state_lib.default_state()
        state_lib.record_attempt(state, "ddgw/gpt-5.4-mini", False,
                                 "quota", now=1000000.0)
        with mock.patch.object(client_lib, "chat_cli") as cli, \
             mock.patch.object(client_lib, "chat_gemini",
                               return_value="رد Gemini"):
            # تهدئة يدوية بعيدة (حتى 2999) بدل انتظار 429 حقيقي
            state["providers"]["ddgw/gpt-5.4-mini"][
                "cooldown_until"] = "2999-01-01T00:00:00"
            text, via, model = client_lib.chat_chain(
                "مرحبا", self._providers(), retries=0, state=state)
        self.assertEqual(via, "gemini")
        cli.assert_not_called()

    def test_all_failed_arabic(self):
        with mock.patch.object(
                client_lib, "chat_cli",
                side_effect=OmniRouteError("HTTP 429")), \
             mock.patch.object(
                 client_lib, "chat_gemini",
                 side_effect=OmniRouteError("HTTP 401")):
            with self.assertRaises(LLMAllFailedError) as ctx:
                client_lib.chat_chain("مرحبا", self._providers(),
                                      retries=0)
        err = ctx.exception
        self.assertIsInstance(err, OmniRouteError)
        self.assertIn("فشلت كل مزودات", str(err))
        self.assertEqual(len(err.failures), 2)
        kinds = {p: k for p, k, _d in err.failures}
        self.assertEqual(kinds["ddgw/gpt-5.4-mini"], "quota")
        self.assertEqual(kinds["gemini-3-flash-preview"], "auth")

    def test_on_attempt_called_once_per_provider(self):
        seen = []

        def on_attempt(provider, ok, kind):
            seen.append((provider, ok, kind))

        with mock.patch.object(
                client_lib, "chat_cli",
                side_effect=OmniRouteError("boom")), \
             mock.patch.object(
                 client_lib, "chat_gemini",
                 return_value="ok"):
            client_lib.chat_chain("مرحبا", self._providers(),
                                  retries=1, retry_delay=0,
                                  on_attempt=on_attempt)
        self.assertEqual(seen, [("ddgw/gpt-5.4-mini", False, "unknown"),
                                ("gemini-3-flash-preview", True, None)])

    def test_empty_providers(self):
        with self.assertRaises(OmniRouteError):
            client_lib.chat_chain("مرحبا", [])


class TestGroqAndLiteInChain(unittest.TestCase):
    """جولة v0.1.40: Groq ركنًا ثانيًا بدل g4fpol، وFlash-Lite
    قبل Flash الرئيسي — كلها mock، بلا شبكة حية."""

    def test_groq_success_returns_groq_reply(self):
        providers = [{"kind": "omniroute",
                      "model": "groq/openai/gpt-oss-120b"},
                     {"kind": "gemini",
                      "model": "gemini-3.1-flash-lite"}]
        with mock.patch.object(
                client_lib, "chat_cli",
                return_value="رد Groq") as cli, \
             mock.patch.object(client_lib, "chat_gemini") as gem:
            text, via, model = client_lib.chat_chain(
                "مرحبا", providers, retries=0)
        self.assertEqual((text, via, model),
                         ("رد Groq", "cli",
                          "groq/openai/gpt-oss-120b"))
        cli.assert_called_once()
        gem.assert_not_called()

    def test_groq_auth_failure_skips_to_lite(self):
        """خطأ مصادقة محاكى من chat_cli عند Groq → السلسلة
        تتخطاه للركن التالي (Flash-Lite) بلا كسر."""
        providers = [{"kind": "omniroute",
                      "model": "groq/openai/gpt-oss-120b"},
                     {"kind": "gemini",
                      "model": "gemini-3.1-flash-lite"},
                     {"kind": "gemini",
                      "model": "gemini-3-flash-preview"}]
        with mock.patch.object(
                client_lib, "chat_cli",
                side_effect=OmniRouteError(
                    "HTTP 401 Unauthorized — invalid api key")), \
             mock.patch.object(
                 client_lib, "chat_gemini",
                 return_value="رد لايت") as gem:
            text, via, model = client_lib.chat_chain(
                "مرحبا", providers, retries=0)
        self.assertEqual((text, via, model),
                         ("رد لايت", "gemini",
                          "gemini-3.1-flash-lite"))
        gem.assert_called_once()
        # الاستدعاء الوحيد كان لـ Lite لا لـ Flash الرئيسي
        self.assertEqual(gem.call_args[1]["model"],
                         "gemini-3.1-flash-lite")

    def test_lite_wins_before_main_gemini(self):
        """chat_gemini يُستدعى أولًا بنموذج Lite؛ نجاحه يمنع
        الوصول لـ Flash الرئيسي."""
        providers = [{"kind": "gemini",
                      "model": "gemini-3.1-flash-lite"},
                     {"kind": "gemini",
                      "model": "gemini-3-flash-preview"}]
        seen_models = []

        def fake_gemini(prompt, model=None, **kwargs):
            seen_models.append(model)
            return "رد لايت"

        with mock.patch.object(client_lib, "chat_gemini",
                               side_effect=fake_gemini):
            text, via, model = client_lib.chat_chain(
                "مرحبا", providers, retries=0)
        self.assertEqual((text, via, model),
                         ("رد لايت", "gemini",
                          "gemini-3.1-flash-lite"))
        self.assertEqual(seen_models, ["gemini-3.1-flash-lite"])

    def test_lite_failure_falls_through_to_main_gemini(self):
        providers = [{"kind": "gemini",
                      "model": "gemini-3.1-flash-lite"},
                     {"kind": "gemini",
                      "model": "gemini-3-flash-preview"}]
        calls = []

        def fake_gemini(prompt, model=None, **kwargs):
            calls.append(model)
            if model == "gemini-3.1-flash-lite":
                raise OmniRouteError("HTTP 429 quota")
            return "رد Flash"

        with mock.patch.object(client_lib, "chat_gemini",
                               side_effect=fake_gemini):
            text, via, model = client_lib.chat_chain(
                "مرحبا", providers, retries=0)
        self.assertEqual((text, via, model),
                         ("رد Flash", "gemini",
                          "gemini-3-flash-preview"))
        self.assertEqual(calls, ["gemini-3.1-flash-lite",
                                 "gemini-3-flash-preview"])


class TestChatLegacy(unittest.TestCase):
    def test_cli_success_unchanged(self):
        with mock.patch.object(client_lib, "chat_cli",
                               return_value="رد") as cli:
            text, via, model = client_lib.chat(
                "مرحبا", "ddgw/gpt-5.4-mini",
                "groq/openai/gpt-oss-120b",
                retries=0)
        self.assertEqual((text, via, model),
                         ("رد", "cli", "ddgw/gpt-5.4-mini"))
        cli.assert_called_once()

    def test_fallback_cli_then_http(self):
        calls = []

        def cli(model, *args, **kwargs):
            calls.append(("cli", model))
            raise OmniRouteError("فشل CLI")

        def http(base, model, *args, **kwargs):
            calls.append(("http", model))
            return "رد HTTP"

        with mock.patch.object(client_lib, "chat_cli",
                               side_effect=cli), \
             mock.patch.object(client_lib, "chat_http",
                               side_effect=http), \
             mock.patch.dict(os.environ,
                             {"OMNIROUTE_API_KEY": "x"}):
            text, via, model = client_lib.chat(
                "مرحبا", "m1", "m2", retries=0)
        # الترتيب القديم: CLI(m1) ثم CLI(m2) ثم HTTP(m1)
        self.assertEqual(calls, [("cli", "m1"), ("cli", "m2"),
                                 ("http", "m1")])
        self.assertEqual((text, via, model),
                         ("رد HTTP", "http", "m1"))


class TestChatGemini(unittest.TestCase):
    def _fake_helper(self, tmp, body):
        path = os.path.join(tmp, "gemini.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        return path

    def test_success(self):
        with tempfile.TemporaryDirectory() as td:
            helper = self._fake_helper(
                td, "import sys\nprint('رد تجريبي')\n")
            out = client_lib.chat_gemini("مرحبا", helper=helper)
        self.assertEqual(out, "رد تجريبي")

    def test_http_429_error(self):
        with tempfile.TemporaryDirectory() as td:
            helper = self._fake_helper(
                td, "import sys\n"
                    "print('urllib.error.HTTPError: HTTP Error 429: "
                    "Too Many Requests', file=sys.stderr)\n"
                    "sys.exit(1)\n")
            with self.assertRaises(OmniRouteError) as ctx:
                client_lib.chat_gemini("مرحبا", helper=helper)
            self.assertIn("429", str(ctx.exception))
            self.assertEqual(
                client_lib.classify_llm_error(str(ctx.exception)),
                "quota")

    def test_missing_helper(self):
        with self.assertRaises(OmniRouteError) as ctx:
            client_lib.chat_gemini(
                "مرحبا", helper="/tmp/no-such-gemini-helper.py")
        self.assertIn("غير موجود", str(ctx.exception))

    def test_system_prepended(self):
        with tempfile.TemporaryDirectory() as td:
            helper = self._fake_helper(
                td, "import sys\n"
                    "print(sys.argv[sys.argv.index('--prompt') + 1])\n")
            out = client_lib.chat_gemini(
                "سؤال", system="نظام", helper=helper)
        self.assertTrue(out.startswith("نظام\n\nسؤال"))


if __name__ == "__main__":
    unittest.main()
