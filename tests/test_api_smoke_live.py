#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبار دخان حي للـAPIs الخارجية — جولة تطبيق الأنماط (W3).

يستدعي `lib/omniroute_client.py` و`lib/social_publish.py`
نفسيهما (سلوك لا HTTP خام) فيختبر التوجيه والمساعدات
والمسارات الحقيقية، لا الطبقة الأرقّ.

قواعد صارمة (فكرة Newman §2.1 منقولة إلى Python):
- مبوَّب خارج التشغيل الافتراضي: يتخطى دائمًا إلا بوجود
  `STUDIO_LIVE_SMOKE=1` **و** مفاتيح/إعدادات مهيأة لكل مزود.
- قراءة فقط أبدًا: لا نشر ولا كتابة على أي منصة — لا
  `upload_tiktok` ولا `upload_instagram` ولا أي دالة كتابة،
  والمنصات الاجتماعية تُفحص بـ GET للقراءة فقط
  (`/me` و`/v2/user/info/`) عبر مساعد social_publish نفسه.
- مكالمة واحدة صغيرة لكل مزود كحد أقصى (برومبت من كلمة
  واحدة، max_tokens=10) — والاختيار الواحد من كل مزود
  يأتي من `lib/api_contract.py` عبر `subTest`.
- يتخطى نظيفًا عند تهدئة المزود: قبل كل مزود LLM تُقرأ
  حالة `lib/llm_state.py`، والمزود في تهدئة (429/402)
  يُتخطَّى مع الثواني المتبقية — وكذلك خطأ الحصة أثناء
  الاستدعاء نفسه. خادم Ollama المتوقف أو موديله غير
  المثبّت = تخطٍّ لا فشل (network/not_found بلا تهدئة).

التشغيل اليدوي/الليلي فقط (لا في كل push):
  STUDIO_LIVE_SMOKE=1 STUDIO_SMOKE_REPORT_JSON=smoke-results.json \
      python -m unittest tests.test_api_smoke_live -v
  python -m lib.smoke_report --results-json smoke-results.json
"""
import json
import os
import shutil
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import api_contract
from lib import llm_state
from lib import omniroute_client
from lib import smoke_report
from lib import social_publish as sp

LIVE = os.environ.get("STUDIO_LIVE_SMOKE") == "1"

# برومبت الدخان: كلمة واحدة — أصغر مكالمة توليد ممكنة.
PROMPT = "قل كلمة «اختبار» فقط."
SMALL_MAX_TOKENS = 10


def _elapsed_ms(start):
    return int((time.monotonic() - start) * 1000)


@unittest.skipUnless(
    LIVE,
    "الدخان الحي مغلق — فعّله بـ STUDIO_LIVE_SMOKE=1 "
    "(تشغيل يدوي/ليلي فقط، لا في كل push)")
class TestApiSmokeLive(unittest.TestCase):
    """دخان حي: مدخل عقد واحد لكل مزود عبر subTest."""

    RESULTS = []

    @classmethod
    def setUpClass(cls):
        cls.RESULTS = []

    @classmethod
    def tearDownClass(cls):
        path = api_contract.results_json_path()
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(cls.RESULTS, fh, ensure_ascii=False,
                          indent=2)
        except OSError as exc:
            print("تحذير: تعذّرت كتابة نتائج الدخان في %s: %s"
                  % (path, exc), file=sys.stderr)

    # ─── مساعدات ───
    def _record(self, entry, status, elapsed_ms, error=""):
        endpoint = "%s %s" % (entry["method"], entry["path"])
        self.__class__.RESULTS.append(smoke_report.result(
            entry["provider"], entry["model"], endpoint, status,
            elapsed_ms, error))

    def _skip(self, entry, elapsed_ms, reason):
        """سجّل «متخطَّى» في النتائج ثم ارفع SkipTest."""
        self._record(entry, "skipped", elapsed_ms, reason)
        raise unittest.SkipTest(reason)

    def _check_cooldown(self, entry, start):
        """تخطَّ نظيفًا إن كان مزود LLM في تهدئة (llm_state)."""
        state = llm_state.load_state()
        cooling, remaining = llm_state.cooling_down(
            state, entry["model"])
        if cooling:
            self._skip(entry, _elapsed_ms(start),
                       "المزود %s في تهدئة (حصة) — متبقٍ %d ثانية"
                       % (entry["model"], remaining))

    def _should_skip_error(self, entry, exc):
        """هل خطأ الاستدعاء يستحق التخطي لا الفشل؟"""
        text = str(exc)
        provider = entry["provider"]
        if provider in ("gemini", "omniroute", "ollama"):
            kind = omniroute_client.classify_llm_error(text)
            if kind == "quota":
                return True
            if provider == "ollama" and kind in ("network",
                                                  "not_found"):
                return True
            return False
        if provider == "openrouter":
            return getattr(exc, "code", None) == 429
        if provider == "instagram":
            return "429" in text
        if provider == "tiktok":
            # 429 تهدئة؛ و401/403 نطاق لا مصادقة: توكن النشر
            # (video.upload) قد لا يحمل user.info.basic أصلًا.
            return ("429" in text or "(HTTP 401)" in text
                    or "(HTTP 403)" in text)
        return False

    # ─── الاستدعاءات (واحدة صغيرة لكل مزود) ───
    def _dispatch(self, entry, start):
        provider = entry["provider"]
        model = entry["model"]
        if provider == "gemini":
            self._check_cooldown(entry, start)
            if not os.path.isfile(omniroute_client.GEMINI_HELPER):
                self._skip(entry, _elapsed_ms(start),
                           "مساعد Gemini غير موجود — لم يُهيَّأ")
            text = omniroute_client.chat_gemini(
                PROMPT, model=model, system="",
                max_tokens=SMALL_MAX_TOKENS, temperature=0,
                timeout=60)
            self.assertTrue(text.strip(),
                            "رد Gemini فارغ للموديل %s" % model)
        elif provider == "omniroute":
            self._check_cooldown(entry, start)
            if shutil.which("omniroute"):
                text = omniroute_client.chat_cli(
                    model, PROMPT, system="",
                    max_tokens=SMALL_MAX_TOKENS, temperature=0,
                    timeout=120)
            elif os.environ.get("OMNIROUTE_API_KEY", "").strip():
                text = omniroute_client.chat_http(
                    "http://localhost:20128", model, PROMPT,
                    system="", max_tokens=SMALL_MAX_TOKENS,
                    temperature=0, timeout=120)
            else:
                self._skip(entry, _elapsed_ms(start),
                           "لا أمر omniroute ولا OMNIROUTE_API_KEY")
            self.assertTrue(text.strip(),
                            "رد OmniRoute فارغ للموديل %s" % model)
        elif provider == "ollama":
            self._check_cooldown(entry, start)
            text = omniroute_client.chat_ollama(
                PROMPT, model=model, system="",
                max_tokens=SMALL_MAX_TOKENS, temperature=0,
                timeout=60)
            self.assertTrue(text.strip(),
                            "رد Ollama فارغ للموديل %s" % model)
        elif provider == "openrouter":
            # جلب واحد للكتالوج العام ثم تحليل محلي —
            # بلا جلب ثانٍ وبلا توليد وبلا مفتاح.
            url = (omniroute_client.OPENROUTER_DEFAULT_BASE_URL
                   + "/v1/models")
            catalog = omniroute_client._default_models_fetcher(
                url, {"Accept": "application/json"}, 15)
            self.assertIsInstance(catalog, dict,
                                  "كتالوج OpenRouter ليس قاموسًا")
            self.assertTrue(
                api_contract.has_nested_field(catalog, "data"),
                "كتالوج OpenRouter بلا حقل data")
            data = catalog.get("data") or []
            self.assertIsInstance(data, list)
            self.assertGreater(len(data), 0,
                               "كتالوج OpenRouter فارغ")
            free_ids = omniroute_client.free_model_ids(catalog)
            self.assertGreater(
                len(free_ids), 0,
                "لا نماذج مجانية في كتالوج OpenRouter")
        elif provider == "instagram":
            token = sp.load_token("instagram")
            if not token:
                self._skip(entry, _elapsed_ms(start),
                           "لا توكن Instagram محفوظ")
            url = "%s/%s/me?fields=id" % (sp.IG_API_BASE,
                                          sp.IG_API_VERSION)
            resp = sp._http_json("GET", url, token=token,
                                 timeout=30, context="instagram")
            self.assertTrue(
                api_contract.has_nested_field(resp, "id"),
                "رد Graph /me بلا id: %s" % str(resp)[:200])
        elif provider == "tiktok":
            token = sp.load_token("tiktok")
            if not token:
                self._skip(entry, _elapsed_ms(start),
                           "لا توكن TikTok محفوظ")
            url = ("https://open.tiktokapis.com"
                   "/v2/user/info/?fields=open_id,display_name")
            resp = sp._http_json("GET", url, token=token,
                                 timeout=30, context="tiktok")
            self.assertTrue(
                api_contract.has_nested_field(
                    resp, "data.user.open_id"),
                "رد TikTok /v2/user/info بلا open_id: %s"
                % str(resp)[:200])
        else:
            raise AssertionError(
                "مزود بلا مسار دخان في العقد: %s" % provider)

    def _run_entry(self, entry):
        start = time.monotonic()
        try:
            self._dispatch(entry, start)
        except unittest.SkipTest:
            raise
        except Exception as exc:  # noqa: BLE001 — يُصنَّف أدناه
            elapsed = _elapsed_ms(start)
            if self._should_skip_error(entry, exc):
                self._skip(entry, elapsed,
                           "تخطَّ عند الاستدعاء: %s"
                           % str(exc)[:200])
            self._record(entry, "failed", elapsed,
                         str(exc)[:500])
            raise
        elapsed = _elapsed_ms(start)
        self._record(entry, "ok", elapsed, "")
        self.assertLessEqual(
            elapsed, entry["time_budget_ms"],
            "تجاوز %s/%s ميزانية الزمن: %dms > %dms"
            % (entry["provider"], entry["model"], elapsed,
               entry["time_budget_ms"]))

    def test_live_smoke(self):
        """مدخل عقد واحد لكل مزود — مكالمة صغيرة واحدة لكلٍّ."""
        for entry in api_contract.smoke_entries():
            with self.subTest(provider=entry["provider"],
                              model=entry["model"]):
                self._run_entry(entry)


if __name__ == "__main__":
    unittest.main()
