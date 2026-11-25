#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات embed_ollama (lib.omniroute_client) — جولة v0.1.48.

POST /api/embed على نمط chat_ollama تمامًا (نفس معالجة
base_url/model/timeout/الأخطاء). كلها mock للـHTTP — بلا
شبكة وبلا خادم Ollama حقيقي. الاختبار الحي (نموذج
bge-m3، 1.2GB، بُعد 1024) موثّق في تقرير الجولة.
"""
import io
import json
import os
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import omniroute_client as client_lib
from lib.omniroute_client import OmniRouteError


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


class TestEmbedOllama(unittest.TestCase):
    def test_success_posts_to_api_embed(self):
        payload = {"model": "bge-m3",
                   "embeddings": [[0.1, -0.2, 0.3]],
                   "total_duration": 123}
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                return_value=_FakeHTTPResponse(payload)) as open_mock:
            vec = client_lib.embed_ollama("كان يا ما كان")
        self.assertEqual(vec, [0.1, -0.2, 0.3])
        req = open_mock.call_args[0][0]
        self.assertTrue(req.full_url.endswith("/api/embed"))
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["model"], "bge-m3")
        self.assertEqual(body["input"], "كان يا ما كان")

    def test_default_model_is_live_verified(self):
        # الاسم الافتراضي متحقق منه حيًا بـ `ollama list`
        # في هذه الجولة (bge-m3، 1.2GB) — لا رقم
        # من الذاكرة.
        self.assertEqual(client_lib.OLLAMA_DEFAULT_EMBED_MODEL,
                         "bge-m3")

    def test_custom_base_url_and_model(self):
        payload = {"embeddings": [[1.0, 2.0]]}
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                return_value=_FakeHTTPResponse(payload)) as open_mock:
            vec = client_lib.embed_ollama(
                "نص", model="bge-m3",
                base_url="http://127.0.0.1:11434/")
        self.assertEqual(vec, [1.0, 2.0])
        req = open_mock.call_args[0][0]
        self.assertTrue(req.full_url.startswith(
            "http://127.0.0.1:11434/api/embed"))
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["model"], "bge-m3")

    def test_empty_text_refused(self):
        with self.assertRaises(OmniRouteError):
            client_lib.embed_ollama("   ")

    def test_server_down_is_network(self):
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                side_effect=urllib.error.URLError(
                    "[Errno 111] Connection refused")):
            with self.assertRaises(OmniRouteError) as ctx:
                client_lib.embed_ollama("نص")
        self.assertIn("غير متاح", str(ctx.exception))
        self.assertIn("ollama serve", str(ctx.exception))
        self.assertEqual(
            client_lib.classify_llm_error(str(ctx.exception)),
            "network")

    def test_model_missing_is_not_found(self):
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                side_effect=_http_error(
                    "http://localhost:11434/api/embed", 404,
                    '{"error": "model \'bge-m3\' not found"}')):
            with self.assertRaises(OmniRouteError) as ctx:
                client_lib.embed_ollama("نص")
        self.assertIn("غير موجود", str(ctx.exception))
        self.assertIn("ollama pull bge-m3",
                      str(ctx.exception))
        self.assertEqual(
            client_lib.classify_llm_error(str(ctx.exception)),
            "not_found")

    def test_server_error_500(self):
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                side_effect=_http_error(
                    "http://localhost:11434/api/embed", 500,
                    "internal error")):
            with self.assertRaises(OmniRouteError) as ctx:
                client_lib.embed_ollama("نص")
        self.assertEqual(
            client_lib.classify_llm_error(str(ctx.exception)),
            "server")

    def test_unexpected_response(self):
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                return_value=_FakeHTTPResponse({"done": True})):
            with self.assertRaises(OmniRouteError):
                client_lib.embed_ollama("نص")

    def test_empty_embeddings_rejected(self):
        with mock.patch.object(
                client_lib.urllib.request, "urlopen",
                return_value=_FakeHTTPResponse({"embeddings": []})):
            with self.assertRaises(OmniRouteError):
                client_lib.embed_ollama("نص")


if __name__ == "__main__":
    unittest.main()
