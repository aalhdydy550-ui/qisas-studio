#!/usr/bin/env python3
"""اختبارات مزود Ollama المحلي في سلسلة LLM — جولة v0.1.39.

chat_ollama عبر /api/chat (نجاح/خادم متوقف/موديل غير موجود)؛
وموضع Ollama أخيرًا في السلسلة بعد Gemini؛ والتخطي الهادئ
عند غيابه؛ والسلسلة بلا Ollama كما قبل؛ وفحص التوفر
ollama_status (GET /api/tags). كلها mock للـHTTP — بلا شبكة
وبلا خادم Ollama حقيقي.
"""
import io
import json
import os
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import llm_state as state_lib
from lib import omniroute_client as client_lib
from lib.omniroute_client import LLMAllFailedError, OmniRouteError


class _FakeHTTPResponse:
    """رد HTTP وهمي يدعم `with` (لـ urlopen)."""

    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _http_error(url, code, body):
    return urllib.error.HTTPError(
        url, code, "HTTP %s" % code, hdrs=None,
        fp=io.BytesIO(body.encode("utf-8")))


class TestChatOllama(unittest.TestCase):
    def test_success(self):
        payload = {"message": {"role": "assistant",
                               "content": "  رد محلي  "},
                   "done": True}
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                return_value=_FakeHTTPResponse(payload)) as open_mock:
            out = client_lib.chat_ollama("مرحبا")
        self.assertEqual(out, "رد محلي")
        req = open_mock.call_args[0][0]
        self.assertTrue(req.full_url.endswith("/api/chat"))
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["model"], "qwen2.5:7b")
        self.assertFalse(body["stream"])
        self.assertEqual(body["messages"][-1]["content"], "مرحبا")

    def test_system_prompt_sent(self):
        payload = {"message": {"role": "assistant", "content": "ok"}}
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                return_value=_FakeHTTPResponse(payload)) as open_mock:
            client_lib.chat_ollama("سؤال", system="نظام")
        body = json.loads(open_mock.call_args[0][0].data.decode("utf-8"))
        self.assertEqual(body["messages"][0],
                         {"role": "system", "content": "نظام"})

    def test_server_down_is_network(self):
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                side_effect=urllib.error.URLError(
                    "[Errno 111] Connection refused")):
            with self.assertRaises(OmniRouteError) as ctx:
                client_lib.chat_ollama("مرحبا")
        self.assertIn("غير متاح", str(ctx.exception))
        self.assertIn("ollama serve", str(ctx.exception))
        self.assertEqual(
            client_lib.classify_llm_error(str(ctx.exception)),
            "network")

    def test_model_missing_is_not_found(self):
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                side_effect=_http_error(
                    "http://localhost:11434/api/chat", 404,
                    '{"error": "model \'qwen2.5:7b\' not found"}')):
            with self.assertRaises(OmniRouteError) as ctx:
                client_lib.chat_ollama("مرحبا")
        self.assertIn("غير موجود", str(ctx.exception))
        self.assertIn("ollama pull qwen2.5:7b", str(ctx.exception))
        self.assertEqual(
            client_lib.classify_llm_error(str(ctx.exception)),
            "not_found")

    def test_server_error_500(self):
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                side_effect=_http_error(
                    "http://localhost:11434/api/chat", 500,
                    "internal error")):
            with self.assertRaises(OmniRouteError) as ctx:
                client_lib.chat_ollama("مرحبا")
        self.assertEqual(
            client_lib.classify_llm_error(str(ctx.exception)),
            "server")

    def test_unexpected_response(self):
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                return_value=_FakeHTTPResponse({"done": True})):
            with self.assertRaises(OmniRouteError):
                client_lib.chat_ollama("مرحبا")

    def test_custom_base_url_and_model(self):
        payload = {"message": {"role": "assistant", "content": "ok"}}
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                return_value=_FakeHTTPResponse(payload)) as open_mock:
            client_lib.chat_ollama(
                "مرحبا", model="llama3.1:8b",
                base_url="http://127.0.0.1:11434/")
        req = open_mock.call_args[0][0]
        self.assertTrue(req.full_url.startswith(
            "http://127.0.0.1:11434/api/chat"))
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["model"], "llama3.1:8b")


class TestOllamaStatus(unittest.TestCase):
    def test_available_when_model_installed(self):
        payload = {"models": [{"name": "qwen2.5:7b"},
                              {"name": "llama3.1:8b"}]}
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                return_value=_FakeHTTPResponse(payload)):
            status = client_lib.ollama_status()
        self.assertTrue(status["available"])
        self.assertEqual(status["model"], "qwen2.5:7b")
        self.assertIn("مثبّت", status["detail"])

    def test_unavailable_when_server_down(self):
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                side_effect=urllib.error.URLError("refused")):
            status = client_lib.ollama_status()
        self.assertFalse(status["available"])
        self.assertIn("غير شغال", status["detail"])

    def test_unavailable_when_model_missing(self):
        payload = {"models": [{"name": "llama3.1:8b"}]}
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                return_value=_FakeHTTPResponse(payload)):
            status = client_lib.ollama_status()
        self.assertFalse(status["available"])
        self.assertIn("ollama pull qwen2.5:7b", status["detail"])

    def test_never_raises(self):
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                side_effect=_http_error(
                    "http://localhost:11434/api/tags", 500, "boom")):
            status = client_lib.ollama_status()
        self.assertFalse(status["available"])


class TestOllamaInChain(unittest.TestCase):
    def _providers(self):
        return client_lib.providers_from_config(
            {"model": "ddgw/gpt-5.4-mini",
             "fallback_model": "groq/openai/gpt-oss-120b"})

    def test_ollama_is_last(self):
        providers = self._providers()
        self.assertEqual(
            [(p["kind"], p["model"]) for p in providers],
            [("omniroute", "ddgw/gpt-5.4-mini"),
             ("omniroute", "groq/openai/gpt-oss-120b"),
             ("gemini", "gemini-3.1-flash-lite"),
             ("gemini", "gemini-3-flash-preview"),
             ("ollama", "qwen2.5:7b")])
        self.assertEqual(providers[-1]["kind"], "ollama")
        self.assertEqual(providers[-1]["model"], "qwen2.5:7b")

    def test_ollama_wins_after_cloud_and_gemini_fail(self):
        with mock.patch.object(
                client_lib, "chat_cli",
                side_effect=OmniRouteError("HTTP 429")), \
             mock.patch.object(
                 client_lib, "chat_gemini",
                 side_effect=OmniRouteError("HTTP 401")), \
             mock.patch.object(
                 client_lib, "chat_ollama",
                 return_value="رد Ollama") as ollama:
            text, via, model = client_lib.chat_chain(
                "مرحبا", self._providers(), retries=0)
        self.assertEqual((text, via, model),
                         ("رد Ollama", "ollama", "qwen2.5:7b"))
        ollama.assert_called_once()

    def test_server_down_skips_ollama_quietly(self):
        """الخادم متوقف → فشل السلسلة كاملة برسالة عربية،
        وساق Ollama مسجلة network بلا تهدئة."""
        state = state_lib.default_state()
        seen = []

        def on_attempt(provider, ok, kind):
            seen.append((provider, ok, kind))
            state_lib.record_attempt(state, provider, ok, kind)

        with mock.patch.object(
                client_lib, "chat_cli",
                side_effect=OmniRouteError("HTTP 429")), \
             mock.patch.object(
                 client_lib, "chat_gemini",
                 side_effect=OmniRouteError("HTTP 401")), \
             mock.patch.object(
                 client_lib, "chat_ollama",
                 side_effect=OmniRouteError(
                     "خادم Ollama غير متاح على "
                     "http://localhost:11434 — connection refused")):
            with self.assertRaises(LLMAllFailedError) as ctx:
                client_lib.chat_chain(
                    "مرحبا", self._providers(), retries=0,
                    state=state, on_attempt=on_attempt)
        err = ctx.exception
        self.assertIn("فشلت كل مزودات", str(err))
        kinds = {p: k for p, k, _d in err.failures}
        self.assertEqual(kinds["qwen2.5:7b"], "network")
        # بلا تهدئة: خطأ شبكة لا حصة
        cooling, _ = state_lib.cooling_down(state, "qwen2.5:7b")
        self.assertFalse(cooling)
        self.assertIn(("qwen2.5:7b", False, "network"), seen)

    def test_model_missing_skips_ollama_without_cooldown(self):
        state = state_lib.default_state()
        with mock.patch.object(
                client_lib, "chat_cli",
                side_effect=OmniRouteError("HTTP 429")), \
             mock.patch.object(
                 client_lib, "chat_gemini",
                 side_effect=OmniRouteError("HTTP 401")), \
             mock.patch.object(
                 client_lib, "chat_ollama",
                 side_effect=OmniRouteError(
                     "الموديل qwen2.5:7b غير موجود في Ollama — "
                     "model not found")):
            with self.assertRaises(LLMAllFailedError) as ctx:
                client_lib.chat_chain(
                    "مرحبا", self._providers(), retries=0,
                    state=state,
                    on_attempt=lambda p, ok, k: state_lib
                    .record_attempt(state, p, ok, k))
        kinds = {p: k for p, k, _d in ctx.exception.failures}
        self.assertEqual(kinds["qwen2.5:7b"], "not_found")
        cooling, _ = state_lib.cooling_down(state, "qwen2.5:7b")
        self.assertFalse(cooling)

    def test_chain_without_ollama_unchanged(self):
        """سلسلة بلا ساق Ollama تعمل كما قبل تمامًا."""
        providers = [{"kind": "omniroute",
                      "model": "ddgw/gpt-5.4-mini"},
                     {"kind": "gemini",
                      "model": "gemini-3-flash-preview"}]
        with mock.patch.object(
                client_lib, "chat_cli",
                side_effect=OmniRouteError("HTTP 429")), \
             mock.patch.object(
                 client_lib, "chat_gemini",
                 return_value="رد Gemini"), \
             mock.patch.object(client_lib, "chat_ollama") as ollama:
            text, via, model = client_lib.chat_chain(
                "مرحبا", providers, retries=0)
        self.assertEqual((text, via, model),
                         ("رد Gemini", "gemini",
                          "gemini-3-flash-preview"))
        ollama.assert_not_called()

    def test_earlier_success_never_touches_ollama(self):
        with mock.patch.object(
                client_lib, "chat_cli",
                return_value="رد سحابي"), \
             mock.patch.object(client_lib, "chat_ollama") as ollama:
            text, via, model = client_lib.chat_chain(
                "مرحبا", self._providers(), retries=0)
        self.assertEqual(via, "cli")
        ollama.assert_not_called()


if __name__ == "__main__":
    unittest.main()
