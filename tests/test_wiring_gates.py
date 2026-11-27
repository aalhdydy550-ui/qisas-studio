#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات توصيل الموجة ب (جولة v0.1.63 — W11a).

قاعدة «بلا تغيير سلوك افتراضي»: النشر يعمل بلا ملف إعداد
موافقة؛ والرفض عند مستوى custom/أرضية الأمان (خروج 5)؛
وask غير التفاعلي يرجع خروج 3 بلا تعليق مع سؤال معلّق
مسجَّل؛ والموجّه fail-open عند موجّه يرمي؛ وترجمة خطأ
مزوّد إلى رمز مكتوب؛ ورفض حدود الاستخدام 429/409؛ وحفظ
قرار الموجّه في حالة LLM.

كلها hermetic: مجلدات tempfile، ومتغيرات بيئة موجَّهة
لمجلدات مؤقتة (QISAS_APPROVAL_DIR / QISAS_APPROVAL_RUNS_DIR)،
وبلا شبكة (كل المزوّدين mock)، وبلا كتابة في الشجرة الحقيقية.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import llm_state as state_lib
from lib import omniroute_client as oc
from lib import request_flow
from lib import router as router_lib
from lib import social_publish as sp
from lib import tiktok_publish as tp
from lib import usage_caps as caps_lib
from lib import youtube_upload as yu


def _mp4(tmpdir, size=1024):
    path = os.path.join(tmpdir, "video.mp4")
    with open(path, "wb") as f:
        f.write(b"\x00" * size)
    return path


def _probe():
    return {"duration": 45.0, "width": 720, "height": 1280,
            "has_audio": True}


@contextlib.contextmanager
def _approval_env(tmp, config=None):
    """وجّه إعداد الموافقة وسجل قراراتها إلى مجلد مؤقت."""
    adir = os.path.join(tmp, "approval")
    rdir = os.path.join(tmp, "runs")
    os.makedirs(adir, exist_ok=True)
    os.makedirs(rdir, exist_ok=True)
    if config is not None:
        with open(os.path.join(adir, "approval.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(config, fh, ensure_ascii=False)
    with mock.patch.dict(os.environ, {
            "QISAS_APPROVAL_DIR": adir,
            "QISAS_APPROVAL_RUNS_DIR": rdir}):
        yield adir, rdir


def _custom_config(**actions):
    """إعداد level=custom يرفض/يسأل عن أفعال بعينها."""
    return {"level": "custom", "custom": dict(actions),
            "grants": [], "mode": "normal", "drafts": [],
            "settings_version": 1}


def _ask_config():
    return {"level": "ask", "custom": {}, "grants": [],
            "mode": "normal", "drafts": [], "settings_version": 1}


def _decisions(rdir):
    path = os.path.join(rdir, "approval-decisions.jsonl")
    if not os.path.isfile(path):
        return []
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


class _NonInteractiveStdin:
    """سياق: stdin بلا طرفية (كرون/اختبار) — بلا تعليق أبدًا."""

    def __enter__(self):
        self._patch = mock.patch.object(
            sys, "stdin", io.StringIO())
        self._patch.__enter__()
        return self

    def __exit__(self, *exc):
        self._patch.__exit__(*exc)
        return False


# ─── 1. النشر يعمل بلا إعداد موافقة ───

class TestPublishWithoutApprovalConfig(unittest.TestCase):
    def test_tiktok_upload_allows_without_config(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            calls = []
            with _approval_env(td):
                def fake_http(method, url, body=None, token=None,
                              headers=None, timeout=300, **kw):
                    calls.append((method, url))
                    if url.endswith("/video/init/"):
                        return {"data": {
                            "publish_id": "pid-1",
                            "upload_url":
                                "https://example.invalid/up"}}
                    if url.endswith("/status/fetch/"):
                        return {"data": {
                            "status": "PUBLISH_COMPLETE",
                            "public_url":
                                "https://tiktok.example/v/1"}}
                    raise AssertionError("طلب غير متوقع: %s" % url)
                with mock.patch.object(sp, "_http_json", fake_http), \
                        mock.patch.object(
                            sp, "_http_put_bytes",
                            lambda *a, **k: None), \
                        mock.patch.object(
                            sp, "_check_duration",
                            lambda *a: None):
                    res = sp.upload_tiktok(
                        video, "عنوان", "كابشن",
                        "test-token-abcdef")
            self.assertEqual(res["publish_id"], "pid-1")
            self.assertEqual(len(calls), 2)

    def test_instagram_upload_allows_without_config(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with _approval_env(td):
                def fake_http(method, url, body=None, token=None,
                              headers=None, timeout=300, **kw):
                    if method == "POST" and url.endswith("/media"):
                        return {"id": "17841400000000000"}
                    if method == "POST" and url.endswith(
                            "/media_publish"):
                        return {"id": "18000000000000000"}
                    raise AssertionError("طلب غير متوقع: %s %s"
                                         % (method, url))
                with mock.patch.object(sp, "_http_json", fake_http), \
                        mock.patch.object(
                            sp, "_http_post_bytes_rupload",
                            lambda *a, **k: None), \
                        mock.patch.object(
                            sp, "_check_duration",
                            lambda *a: None), \
                        mock.patch.object(
                            sp, "_wait_ig_container_ready",
                            lambda *a, **k: True):
                    res = sp.upload_instagram(
                        video, "عنوان", "كابشن", "123456789",
                        "test-token-abcdef")
            self.assertEqual(res["media_id"], "18000000000000000")

    def test_youtube_upload_allows_without_config(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)

            class _FakeHttpError(Exception):
                pass

            class _FakeMedia:
                def __init__(self, *a, **k):
                    pass

            class _FakeInsert:
                def next_chunk(self):
                    return None, {"id": "yt-123"}

            class _FakeVideos:
                def insert(self, part, body, media_body):
                    self.last_body = body
                    return _FakeInsert()

            class _FakeService:
                def __init__(self):
                    self._videos = _FakeVideos()

                def videos(self):
                    return self._videos

            service = _FakeService()
            with _approval_env(td):
                with mock.patch.object(
                        yu, "_import_google",
                        lambda: (None, None, None, None,
                                 _FakeHttpError, _FakeMedia)):
                    res = yu.upload_video(
                        service, video, "عنوان", "وصف", ["وسم"])
            self.assertEqual(res["video_id"], "yt-123")
            self.assertIn("yt-123", res["url"])

    def test_tiktok_bundle_allows_without_config(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            bundle = os.path.join(td, "bundle")
            with _approval_env(td):
                res = tp.write_tiktok_bundle(
                    bundle, video, "عنوان القصة", "نص القصة.",
                    probe_info=_probe())
            self.assertTrue(os.path.isfile(
                os.path.join(bundle, "metadata.json")))
            self.assertTrue(os.path.isfile(
                os.path.join(bundle, "caption.txt")))

    def test_request_flow_allows_without_config(self):
        with tempfile.TemporaryDirectory() as td:
            runs = []

            def run_fn(cfg, story, title, project, out, fb, num):
                runs.append(title)
                return "/tmp/out/request.mp4"

            def queue_add(cfg, title, story, studio_dir):
                return {"number": 7, "title": title,
                        "text_file": "queue/7-x.txt"}

            story = ("في ليلة مظلمة وقف رجل فقير أمام باب جاره "
                     "الغني يطلب لقمة لأولاده الجائعين، فطرده "
                     "الحارس بلا رحمة، وبعد سبع سنوات انقلب "
                     "الحال فصار الفقير صاحب مال والغني يطرق "
                     "بابه، فعرف الجميع أن الدنيا دوّارة وأن "
                     "العبرة في النهاية، وأن من يرحم يُرحم، "
                     "فهل كنت ستفتح الباب؟")
            with _approval_env(td):
                result = request_flow.request_to_run(
                    {"paths": {"queue_file": "~/queue.md"}},
                    "الأمانة", lambda p: story, "/tmp/out.mp4",
                    run_fn=run_fn, queue_add_fn=queue_add,
                    print_fn=lambda *a: None)
            self.assertEqual(result["status"], "done")
            self.assertEqual(runs, [result["title"]])


# ─── 2. الرفض عند مستوى deny / أرضية الأمان ───

class TestApprovalDeny(unittest.TestCase):
    def test_custom_deny_blocks_tiktok_before_network(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            config = _custom_config(publish_tiktok="deny")
            with _approval_env(td, config):
                with mock.patch.object(
                        sp, "_http_json",
                        side_effect=AssertionError("شبكة!")):
                    with self.assertRaises(
                            sp.ApprovalBlockedError) as ctx:
                        sp.upload_tiktok(video, "عنوان", "كابشن",
                                         "test-token-abcdef")
            self.assertEqual(ctx.exception.exit_code, 5)
            self.assertIn("بوابة الموافقة", str(ctx.exception))

    def test_custom_deny_blocks_youtube_before_network(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            config = _custom_config(publish_youtube="deny")
            with _approval_env(td, config):
                with mock.patch.object(
                        yu, "_import_google",
                        side_effect=AssertionError("شبكة!")):
                    with self.assertRaises(
                            yu.ApprovalBlockedError) as ctx:
                        yu.upload_video(object(), video, "عنوان",
                                        "وصف", [])
            self.assertEqual(ctx.exception.exit_code, 5)

    def test_custom_deny_blocks_tiktok_bundle_before_write(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            bundle = os.path.join(td, "bundle")
            config = _custom_config(publish_tiktok="deny")
            with _approval_env(td, config):
                with self.assertRaises(
                        tp.ApprovalBlockedError) as ctx:
                    tp.write_tiktok_bundle(
                        bundle, video, "عنوان القصة", "نص القصة.",
                        probe_info=_probe())
            self.assertEqual(ctx.exception.exit_code, 5)
            self.assertFalse(os.path.exists(bundle))

    def test_safety_floor_denies_even_without_config(self):
        """أرضية الأمان deny دائمًا — حتى بلا ملف إعداد."""
        with tempfile.TemporaryDirectory() as td:
            runs = []

            def run_fn(cfg, story, title, project, out, fb, num):
                runs.append(title)
                return "/tmp/out/request.mp4"

            def queue_add(cfg, title, story, studio_dir):
                return {"number": 7, "title": title,
                        "text_file": "queue/7-x.txt"}

            story = ("في ليلة مظلمة وقف رجل فقير أمام باب جاره "
                     "الغني يطلب لقمة لأولاده الجائعين، فطرده "
                     "الحارس بلا رحمة، وبعد سبع سنوات انقلب "
                     "الحال فصار الفقير صاحب مال والغني يطرق "
                     "بابه، فعرف الجميع أن الدنيا دوّارة وأن "
                     "العبرة في النهاية، وأن من يرحم يُرحم، "
                     "فهل كنت ستفتح الباب؟")
            with _approval_env(td):  # بلا approval.json أصلًا
                with self.assertRaises(
                        request_flow.ApprovalBlockedError) as ctx:
                    request_flow.request_to_run(
                        {"paths": {"queue_file": "~/queue.md"}},
                        "الأمانة", lambda p: story, "/tmp/out.mp4",
                        run_fn=run_fn, queue_add_fn=queue_add,
                        approval_action="delete_published",
                        print_fn=lambda *a: None)
            self.assertEqual(ctx.exception.exit_code, 5)
            self.assertEqual(runs, [])  # لم يُنفَّذ الإنتاج

    def test_safety_floor_denies_even_under_full(self):
        with tempfile.TemporaryDirectory() as td:
            config = {"level": "full", "custom": {}, "grants": [],
                      "mode": "normal", "drafts": [],
                      "settings_version": 1}
            with _approval_env(td, config):
                with _NonInteractiveStdin():
                    with self.assertRaises(
                            sp.ApprovalBlockedError) as ctx:
                        sp._require_approval("spend_money")
            self.assertEqual(ctx.exception.exit_code, 5)


# ─── 3. ask غير التفاعلي: خروج 3 بلا تعليق + سؤال معلّق مسجَّل ───

class TestApprovalAskNonInteractive(unittest.TestCase):
    def test_tiktok_ask_noninteractive_exit_3(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with _approval_env(td, _ask_config()) as (_adir, rdir):
                with _NonInteractiveStdin():
                    with mock.patch.object(
                            sp, "_http_json",
                            side_effect=AssertionError("شبكة!")):
                        with self.assertRaises(
                                sp.ApprovalBlockedError) as ctx:
                            sp.upload_tiktok(
                                video, "عنوان", "كابشن",
                                "test-token-abcdef")
                records = _decisions(rdir)
            self.assertEqual(ctx.exception.exit_code, 3)
            self.assertIn("موافقة", str(ctx.exception))
            pending = [r for r in records
                       if r.get("action") == "publish_tiktok"
                       and r.get("decision") == "ask"]
            self.assertTrue(pending, records)

    def test_request_flow_ask_noninteractive_exit_3(self):
        with tempfile.TemporaryDirectory() as td:
            runs = []

            def run_fn(cfg, story, title, project, out, fb, num):
                runs.append(title)
                return "/tmp/out/request.mp4"

            def queue_add(cfg, title, story, studio_dir):
                return {"number": 7, "title": title,
                        "text_file": "queue/7-x.txt"}

            story = ("في ليلة مظلمة وقف رجل فقير أمام باب جاره "
                     "الغني يطلب لقمة لأولاده الجائعين، فطرده "
                     "الحارس بلا رحمة، وبعد سبع سنوات انقلب "
                     "الحال فصار الفقير صاحب مال والغني يطرق "
                     "بابه، فعرف الجميع أن الدنيا دوّارة وأن "
                     "العبرة في النهاية، وأن من يرحم يُرحم، "
                     "فهل كنت ستفتح الباب؟")
            with _approval_env(td, _ask_config()):
                with _NonInteractiveStdin():
                    with self.assertRaises(
                            request_flow.ApprovalBlockedError) \
                            as ctx:
                        request_flow.request_to_run(
                            {"paths": {"queue_file": "~/queue.md"}},
                            "الأمانة", lambda p: story,
                            "/tmp/out.mp4", run_fn=run_fn,
                            queue_add_fn=queue_add,
                            print_fn=lambda *a: None)
            self.assertEqual(ctx.exception.exit_code, 3)
            self.assertEqual(runs, [])


# ─── 4. الموجّه fail-open ───

class TestRouterFailOpen(unittest.TestCase):
    def _stub_chat_cli(self, calls, fail_with=None):
        def fake_chat_cli(model, prompt, system=None,
                          max_tokens=200, temperature=0.7,
                          timeout=180):
            calls.append(model)
            if fail_with is not None:
                raise fail_with
            return "رد من %s" % model
        return fake_chat_cli

    def test_route_model_falls_back_when_decider_raises(self):
        def raising_decider(state):
            raise RuntimeError("الموجّه تعطل")

        with mock.patch.object(router_lib, "log_decision",
                               lambda *a, **k: None):
            decision = oc._route_model("مرحبا", ["m1", "m2"],
                                       default="m1",
                                       decider=raising_decider)
        self.assertEqual(decision["source"], "fallback")
        self.assertEqual(decision["model"], "m1")

    def test_chat_uses_default_order_when_decider_raises(self):
        calls = []
        providers = [{"kind": "omniroute", "model": "m1"},
                     {"kind": "omniroute", "model": "m2"}]

        def raising_decider(state):
            raise RuntimeError("الموجّه تعطل")

        with mock.patch.object(router_lib, "log_decision",
                               lambda *a, **k: None), \
                mock.patch.object(
                    oc, "chat_cli",
                    self._stub_chat_cli(calls)):
            text, via, model = oc.chat(
                "مرحبا", "m1", "m2", providers=providers,
                system="نظام", retries=0,
                router_decider=raising_decider,
                check_usage_caps=False)
        self.assertEqual(model, "m1")
        self.assertEqual(calls[0], "m1")
        self.assertIn("m1", text)

    def test_chat_prefers_router_choice(self):
        calls = []
        providers = [{"kind": "omniroute", "model": "m1"},
                     {"kind": "omniroute", "model": "m2"}]

        def choosing_decider(state):
            return {"model": "m2", "effort": "low",
                    "confidence": 0.9}

        state = state_lib.default_state()
        with mock.patch.object(router_lib, "log_decision",
                               lambda *a, **k: None), \
                mock.patch.object(
                    oc, "chat_cli",
                    self._stub_chat_cli(calls)):
            text, via, model = oc.chat(
                "مرحبا", "m1", "m2", providers=providers,
                system="نظام", retries=0, state=state,
                router_decider=choosing_decider,
                check_usage_caps=False)
        self.assertEqual(model, "m2")
        self.assertEqual(calls[0], "m2")
        # قرار الموجّه محفوظ في الحالة.
        last = state_lib.last_router_decision(state)
        self.assertIsNotNone(last)
        self.assertEqual(last["model"], "m2")
        self.assertEqual(last["source"], "router")
        self.assertAlmostEqual(last["confidence"], 0.9)


# ─── 5. ترجمة خطأ مزوّد إلى رمز مكتوب ───

class TestProviderErrorCodes(unittest.TestCase):
    def test_classify_known_errors(self):
        self.assertEqual(
            oc.classify_provider_error("429 Too Many Requests"),
            "quota_or_region_restriction")
        self.assertEqual(
            oc.classify_provider_error("401 Unauthorized"),
            "invalid_credentials")
        self.assertEqual(
            oc.classify_provider_error(
                "503 Service Unavailable"),
            "upstream_outage")
        self.assertEqual(
            oc.classify_provider_error("model not found"),
            "model_catalog_outage")
        self.assertEqual(
            oc.classify_provider_error("شيء غريب بلا نمط"),
            "unknown")

    def test_failed_chat_carries_provider_codes(self):
        calls = []
        err = oc.OmniRouteError("429 rate limit exceeded")

        def failing_cli(model, prompt, system=None,
                        max_tokens=200, temperature=0.7,
                        timeout=180):
            calls.append(model)
            raise err

        with mock.patch.object(oc, "chat_cli", failing_cli):
            with self.assertRaises(oc.LLMAllFailedError) as ctx:
                oc.chat("مرحبا", "m1", "m2", system="نظام",
                        retries=0, check_usage_caps=False)
        self.assertEqual(calls, ["m1", "m2"])
        self.assertEqual(
            ctx.exception.provider_codes["m1"],
            "quota_or_region_restriction")
        self.assertEqual(
            ctx.exception.provider_codes["m2"],
            "quota_or_region_restriction")
        # شكل .failures القديم بلا تغيير.
        self.assertEqual(len(ctx.exception.failures), 2)
        self.assertEqual(ctx.exception.failures[0][1], "quota")


# ─── 6. رفض حدود الاستخدام 429 / 409 ───

class TestUsageCapsRefusal(unittest.TestCase):
    def _blocked(self, status):
        return {"allowed": False,
                "reason": "بُلغ الحد اليومي بالدولار (1 من 1)",
                "retry_after": 3600, "code": "spend_cap",
                "status": status, "usage": {}, "caps": {},
                "resets_at": "2026-11-28T00:00:00",
                "blocked_by": "dailyUsd"}

    def test_chat_unattended_refused_429(self):
        calls = []

        def _stub_cli(model, prompt, system=None, max_tokens=200,
                      temperature=0.7, timeout=180):
            calls.append(model)
            return "رد"

        with mock.patch.object(
                caps_lib, "check",
                return_value=self._blocked(429)):
            with mock.patch.object(oc, "chat_cli", _stub_cli):
                with self.assertRaises(oc.UsageCapError) as ctx:
                    oc.chat("مرحبا", "m1", system="نظام")
        self.assertEqual(ctx.exception.status, 429)
        self.assertEqual(ctx.exception.code, "spend_cap")
        self.assertEqual(ctx.exception.retry_after, 3600)
        self.assertEqual(calls, [])  # لم يُستدعَ أي مزود

    def test_chat_direct_under_everything_refused_409(self):
        with mock.patch.object(
                caps_lib, "check",
                return_value=self._blocked(409)):
            with self.assertRaises(oc.UsageCapError) as ctx:
                oc.chat("مرحبا", "m1", system="نظام",
                        usage_kind="direct")
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(ctx.exception.code, "spend_cap")

    def test_request_flow_cap_refused_409(self):
        def queue_add(cfg, title, story, studio_dir):
            return {"number": 7, "title": title,
                    "text_file": "queue/7-x.txt"}

        story = ("في ليلة مظلمة وقف رجل فقير أمام باب جاره "
                 "الغني يطلب لقمة لأولاده الجائعين، فطرده "
                 "الحارس بلا رحمة، وبعد سبع سنوات انقلب "
                 "الحال فصار الفقير صاحب مال والغني يطرق "
                 "بابه، فعرف الجميع أن الدنيا دوّارة وأن "
                 "العبرة في النهاية، وأن من يرحم يُرحم، "
                 "فهل كنت ستفتح الباب؟")
        with mock.patch.object(
                caps_lib, "check",
                return_value=self._blocked(409)):
            with self.assertRaises(request_flow.UsageCapError) \
                    as ctx:
                request_flow.request_to_run(
                    {"paths": {"queue_file": "~/queue.md"}},
                    "الأمانة", lambda p: story, "/tmp/out.mp4",
                    run_fn=lambda *a: "/tmp/out.mp4",
                    queue_add_fn=queue_add,
                    print_fn=lambda *a: None)
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(ctx.exception.code, "spend_cap")

    def test_real_caps_check_api_shape(self):
        """فحص حدود حقيقي (بلا شبكة): 409 مباشر / 429 غير
        مراقب عند بلوغ الحد — في مجلد مؤقت."""
        with tempfile.TemporaryDirectory() as td:
            caps = {"dailyUsd": 1, "monthlyUsd": None,
                    "dailyTokens": None, "monthlyTokens": None,
                    "stops": "everything"}
            totals = {"dailyUsd": 1, "monthlyUsd": 1,
                      "dailyTokens": 0, "monthlyTokens": 0,
                      "dailyUnits": 0, "monthlyUnits": 0,
                      "entries": 1}
            direct = caps_lib.check(
                "direct", studio_root=td, caps=caps,
                totals=totals)
            self.assertFalse(direct["allowed"])
            self.assertEqual(direct["status"], 409)
            self.assertEqual(direct["code"], "spend_cap")
            self.assertGreater(direct["retry_after"], 0)
            unattended = caps_lib.check(
                "unattended", studio_root=td, caps=caps,
                totals=totals)
            self.assertFalse(unattended["allowed"])
            self.assertEqual(unattended["status"], 429)


# ─── 7. حفظ قرار الموجّه في حالة LLM + سائق النموذج ───

class TestRouterDecisionInState(unittest.TestCase):
    def test_record_and_read_last_decision(self):
        state = state_lib.default_state()
        self.assertIsNone(state_lib.last_router_decision(state))
        state_lib.record_router_decision(
            state, {"model": "gemini-3.1-flash-lite",
                    "effort": "low", "source": "router",
                    "confidence": 0.85,
                    "attribution": "Picked by test · 85%",
                    "reason": None},
            task="chat")
        last = state_lib.last_router_decision(state)
        self.assertEqual(last["model"], "gemini-3.1-flash-lite")
        self.assertEqual(last["source"], "router")
        self.assertAlmostEqual(last["confidence"], 0.85)
        self.assertEqual(last["effort"], "low")
        self.assertEqual(len(state["router"]["history"]), 1)

    def test_history_capped_at_50(self):
        state = state_lib.default_state()
        for i in range(55):
            state_lib.record_router_decision(
                state, {"model": "m%d" % i, "source": "fallback",
                        "confidence": 0.0})
        self.assertEqual(len(state["router"]["history"]), 50)
        self.assertEqual(state["router"]["history"][-1]["model"],
                         "m54")

    def test_router_decision_survives_save_load(self):
        with tempfile.TemporaryDirectory() as td:
            state = state_lib.default_state()
            state_lib.record_router_decision(
                state, {"model": "m1", "source": "router",
                        "confidence": 0.7})
            state_lib.save_state(state, td)
            loaded = state_lib.load_state(td)
            last = state_lib.last_router_decision(loaded)
            self.assertEqual(last["model"], "m1")
            self.assertEqual(last["source"], "router")

    def test_old_state_without_router_loads_fine(self):
        with tempfile.TemporaryDirectory() as td:
            path = state_lib.state_path(td)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"version": 1, "providers": {},
                           "daily": {"date": "2026-11-27",
                                     "calls": {}, "successes": {},
                                     "failures": {}},
                           "windows": {}, "limits": {}}, fh)
            state = state_lib.load_state(td)
            self.assertEqual(state["router"]["last"], None)
            self.assertEqual(state["router"]["history"], [])

    def test_get_model_driver(self):
        driver = state_lib.get_model_driver("gemini")
        self.assertIsNotNone(driver)
        self.assertEqual(driver.name, "gemini")
        self.assertIsNone(state_lib.get_model_driver("لا-يوجد"))
        self.assertIsNone(state_lib.get_model_driver(""))
        self.assertIsNone(state_lib.get_model_driver(None))

    def test_try_driver_send_fake_driver(self):
        from lib import model_driver as driver_lib

        class _FakeDriver(driver_lib.Driver):
            name = "test-fake-w11a"

            def send(self, prompt, model=None, system=None,
                     max_tokens=200, temperature=0.7, timeout=120):
                return "رد وهمي"

            def models(self):
                return ["test-fake-w11a"]

            def health(self):
                return {"available": True, "reason": "ok"}

        state = state_lib.default_state()
        driver_lib.register("test-fake-w11a", _FakeDriver())
        try:
            text = state_lib.try_driver_send(
                state, "test-fake-w11a", "مرحبا")
            self.assertEqual(text, "رد وهمي")
            status = state_lib.provider_status(
                state, "test-fake-w11a")
            self.assertEqual(status["calls_today"], 1)
            self.assertEqual(status["successes_today"], 1)
            # سائق غير مسجل ← None (رجوع للمسار الحالي).
            self.assertIsNone(state_lib.try_driver_send(
                state, "غير-مسجل", "مرحبا"))
        finally:
            driver_lib.clear_registry()
            driver_lib.register_builtin_drivers()

    def test_try_driver_send_failure_falls_back(self):
        from lib import model_driver as driver_lib

        class _FailingDriver(driver_lib.Driver):
            name = "test-fail-w11a"

            def send(self, prompt, model=None, system=None,
                     max_tokens=200, temperature=0.7, timeout=120):
                raise driver_lib.ProviderError(
                    "invalid_credentials", "مفتاح باطل")

            def models(self):
                return ["test-fail-w11a"]

            def health(self):
                return {"available": False,
                        "reason": "invalid_credentials"}

        state = state_lib.default_state()
        driver_lib.register("test-fail-w11a", _FailingDriver())
        try:
            # فشل السائق ← None (رجوع للمسار الحالي) مع
            # تسجيل المحاولة الفاشلة في الحالة.
            self.assertIsNone(state_lib.try_driver_send(
                state, "test-fail-w11a", "مرحبا"))
            status = state_lib.provider_status(
                state, "test-fail-w11a")
            self.assertEqual(status["failures_today"], 1)
            self.assertEqual(status["last_error_kind"], "auth")
        finally:
            driver_lib.clear_registry()
            driver_lib.register_builtin_drivers()


# ─── 8. خطاف فرز التعليقات/الرسائل ───

class TestTriageHook(unittest.TestCase):
    def _fake_client(self):
        calls = []

        class _FakeClient:
            def chat(self, prompt, model, max_tokens=300,
                     temperature=0.0):
                calls.append(prompt)
                if len(calls) == 1:
                    return json.dumps({
                        "sender": "أحمد", "request": "أريد قصة",
                        "deadline": None, "amount": None,
                        "awaits_reply": True, "kind": "طلب قصة"},
                        ensure_ascii=False)
                return json.dumps({
                    "decision": "يحتاج ردًا",
                    "reason": "طلب قصة جديد"},
                    ensure_ascii=False)

        return _FakeClient(), calls

    def test_triage_inbox_uses_inbox_triage(self):
        client, calls = self._fake_client()
        results = sp.triage_inbox(
            [{"id": "c1", "text": "ممكن قصة عن الأمانة؟"}],
            client=client)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "يحتاج ردًا")
        self.assertEqual(len(calls), 2)

    def test_triage_inbox_failure_defers(self):
        class _FailingClient:
            def chat(self, *a, **k):
                raise RuntimeError("النموذج تعطل")

        results = sp.triage_inbox(
            [{"id": "c1", "text": "مرحبا"}],
            client=_FailingClient())
        self.assertEqual(results[0]["status"], "deferred")
        self.assertIsNone(results[0]["decision"])

    def test_triage_inbox_dismissed_sender_skipped(self):
        client, calls = self._fake_client()
        results = sp.triage_inbox(
            [{"id": "c1", "text": "ممكن قصة؟", "sender": "أحمد"}],
            recent_dismissals=["أحمد"], client=client)
        self.assertEqual(results[0]["status"], "تخطٍّ")
        # المرسل المرفوض يُتخطى في قرار المقرر بلا استدعاء
        # نموذج ثانٍ (استدعاء القارئ وحده).
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
