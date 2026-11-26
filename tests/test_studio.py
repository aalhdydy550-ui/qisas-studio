#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات آلية لـ studio — تحويل فحوصات التحقق اليدوية (FIXES.md)
إلى اختبارات تعمل بـ `python3 -m unittest discover -s tests -v`.

مكتبة قياسية فقط، بلا شبكة وبلا خوادم خارجية: كل ما يحتاج خادمًا
يُستبدل بمحاكاة (mock) — عدا استيراد حزمتي `mcp` و`anyio` اللتين
تستخدمهما اختبارات Concat لبناء كائنات نتائج حقيقية ومحاكاة عميل
الـSDK (بلا أي اتصال فعلي).
"""
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import anyio
from mcp.shared.exceptions import MCPError
from mcp.types import (CallToolResult, ListToolsResult, ServerCapabilities,
                       TextContent, Tool)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import omniroute_client, concat_mcp, openmontage_stage
from lib import thumbnail
from lib import whisper_captions


class TestCleanCliOutput(unittest.TestCase):
    def test_removes_loaded_env_and_box_lines(self):
        raw = ("📋 Loaded env from /home/x/.env\n"
               "│ Update available: 3.8.54 → 3.9.0 │\n"
               "│ نص داخل صندوق │\n"
               "عنوان تجريبي من 8 كلمات\n"
               "كابشن تشويقي لا يكشف النهاية.")
        out = omniroute_client._clean_cli_output(raw)
        self.assertEqual(out, "عنوان تجريبي من 8 كلمات\n"
                              "كابشن تشويقي لا يكشف النهاية.")

    def test_strips_ansi(self):
        self.assertEqual(omniroute_client._strip_ansi("\x1b[32mنص\x1b[0m"),
                         "نص")

    def test_keeps_arabic_text_with_diacritics(self):
        text = "قصةٌ حقيقيةٌ بعبرة"
        self.assertEqual(omniroute_client._clean_cli_output(text), text)


class TestFallbackScript(unittest.TestCase):
    def test_anza_keeps_its_hook(self):
        title, _ = studio._fallback_script("anza")
        self.assertIn("عنزة", title)

    def test_other_story_gets_generic_hook(self):
        title, caption = studio._fallback_script("قصة التاجر الأمين")
        self.assertNotIn("عنزة", title)
        self.assertNotIn("عنزة", caption)
        self.assertIn("التاجر", title)


class TestMcpClientConnect(unittest.TestCase):
    """اتصال عميل Concat عبر الـSDK الرسمي (v0.1.49).

    يستبدل TestMcpRead الذي كان يختبر read() اليدوي بأنبوب وهمي
    (حُذف مع العميل اليدوي): الدخول يتحقق من إصدار البروتوكول
    والقدرات ووجود الأدوات الـ12، ومهلة call وأخطاء call_tool
    تتحول إلى ConcatError. العميل الحقيقي (mcp.Client) يُستبدل
    بعميل وهمي مدير سياق غير متزامن عبر mock.patch.object،
    والكود غير المتزامن يُشغَّل بـ anyio.run داخل الاختبارات
    المتزامنة.
    """

    # الأدوات الـ12 التي يستدعيها assemble() فعليًا، بترتيبه نفسه
    # (العقد §0) — القائمة هنا مستقلة عن الوحدة لتختبرها هي نفسها.
    TOOLS = ["project_create", "timeline_read", "media_import",
             "clips_add_sequence", "track_add", "clip_add", "title_add",
             "clip_update", "captions_add", "project_save", "export_start",
             "export_wait"]

    def _fake_client_class(self, tools=None, protocol_version="2026-07-28",
                           capabilities_tools=True, call_tool=None):
        """عميل SDK وهمي: مدير سياق غير متزامن بخصائص
        protocol_version وserver_capabilities وlist_tools()
        وcall_tool() — نفس السطح الذي يستخدمه MCP الجديد."""
        tools = list(self.TOOLS) if tools is None else list(tools)
        seen = {}

        class FakeClient:
            def __init__(self, params, *args, **kwargs):
                seen["params"] = params
                self.protocol_version = protocol_version
                self.server_capabilities = ServerCapabilities(
                    tools={"listChanged": False}
                    if capabilities_tools else None)
                self._tools = tools
                self._call_tool = call_tool

            async def __aenter__(self):
                seen["entered"] = True
                return self

            async def __aexit__(self, *exc):
                seen["exited"] = True
                return False

            async def list_tools(self):
                return ListToolsResult(tools=[
                    Tool(name=name, inputSchema={"type": "object"})
                    for name in self._tools])

            async def call_tool(self, tool, args):
                if self._call_tool is not None:
                    return await self._call_tool(tool, args)
                return CallToolResult(
                    content=[TextContent(type="text", text="{}")])

        return FakeClient, seen

    def _enter(self, log):
        async def _run():
            async with concat_mcp.MCP("/bin/false", log) as m:
                return m
        return _run

    def test_connect_success_verifies_twelve_tools(self):
        fake_cls, seen = self._fake_client_class()
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "log.jsonl")
            with mock.patch.object(concat_mcp, "Client", fake_cls):
                m = anyio.run(self._enter(log))
            self.assertIsNotNone(m)
            self.assertTrue(seen.get("entered"))
            self.assertTrue(seen.get("exited"))
            # نفس معاملات إطلاق الخادم كما في العقد §0
            self.assertEqual(seen["params"].command, "/bin/false")
            self.assertEqual(seen["params"].args, ["--mcp", "headless"])
            # الدخول يفتح ملف السجل (append) فينشئه ولو بلا استدعاءات
            self.assertTrue(os.path.exists(log))

    def test_missing_tool_raises_naming_it(self):
        tools = [t for t in self.TOOLS if t != "export_wait"]
        fake_cls, _seen = self._fake_client_class(tools=tools)
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "log.jsonl")
            with mock.patch.object(concat_mcp, "Client", fake_cls):
                with self.assertRaises(concat_mcp.ConcatError) as cm:
                    anyio.run(self._enter(log))
            self.assertIn("export_wait", str(cm.exception))

    def test_empty_protocol_version_raises(self):
        fake_cls, _seen = self._fake_client_class(protocol_version="")
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "log.jsonl")
            with mock.patch.object(concat_mcp, "Client", fake_cls):
                with self.assertRaises(concat_mcp.ConcatError):
                    anyio.run(self._enter(log))

    def test_missing_tools_capability_raises(self):
        fake_cls, _seen = self._fake_client_class(capabilities_tools=False)
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "log.jsonl")
            with mock.patch.object(concat_mcp, "Client", fake_cls):
                with self.assertRaises(concat_mcp.ConcatError):
                    anyio.run(self._enter(log))

    def test_call_timeout_raises(self):
        async def _never(tool, args):
            await anyio.sleep_forever()

        fake_cls, _seen = self._fake_client_class(call_tool=_never)
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "log.jsonl")

            async def _call():
                async with concat_mcp.MCP("/bin/false", log) as m:
                    await m.call("project_create", {}, timeout=1)

            with mock.patch.object(concat_mcp, "Client", fake_cls):
                with self.assertRaises(concat_mcp.ConcatError) as cm:
                    anyio.run(_call)
            self.assertIn("لا رد من Concat خلال 1 ثانية",
                          str(cm.exception))

    def test_mcp_error_becomes_concat_error(self):
        async def _boom(tool, args):
            raise MCPError(-32602, "unknown tool boom")

        fake_cls, _seen = self._fake_client_class(call_tool=_boom)
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "log.jsonl")

            async def _call():
                async with concat_mcp.MCP("/bin/false", log) as m:
                    await m.call("project_create", {})

            with mock.patch.object(concat_mcp, "Client", fake_cls):
                with self.assertRaises(concat_mcp.ConcatError) as cm:
                    anyio.run(_call)
            self.assertIn("project_create فشل:", str(cm.exception))
            self.assertIn("boom", str(cm.exception))

    def test_call_returns_result_and_logs_one_line(self):
        async def _ok(tool, args):
            return CallToolResult(
                content=[TextContent(type="text",
                                     text='{"createdId": "m1"}')],
                structured_content={"createdId": "m1"})

        fake_cls, _seen = self._fake_client_class(call_tool=_ok)
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "log.jsonl")

            async def _call():
                async with concat_mcp.MCP("/bin/false", log) as m:
                    return await m.call(
                        "media_import",
                        {"path": "/tmp/p", "file": "a.jpg"})

            with mock.patch.object(concat_mcp, "Client", fake_cls):
                res = anyio.run(_call)
            self.assertFalse(res.is_error)
            self.assertEqual(res.structured_content, {"createdId": "m1"})
            with open(log, encoding="utf-8") as f:
                lines = [ln for ln in f.read().splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["tool"], "media_import")
            self.assertIn("res", entry)


class TestConfigValidation(unittest.TestCase):
    def test_bad_section_type_restored_to_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "config.yaml"), "w",
                      encoding="utf-8") as f:
                f.write('omniroute: "not-a-dict"\n')
            old_file = studio.__file__
            studio.__file__ = os.path.join(tmp, "studio.py")
            try:
                cfg = studio.load_config()
            finally:
                studio.__file__ = old_file
            self.assertIsInstance(cfg["omniroute"], dict)
            self.assertEqual(cfg["omniroute"]["model"],
                             studio.DEFAULTS["omniroute"]["model"])


class TestNewRun(unittest.TestCase):
    def test_same_second_gets_unique_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("time.strftime",
                            return_value="20261120-120000"):
                id1, _ = studio.new_run(tmp, "test")
                id2, _ = studio.new_run(tmp, "test")
            self.assertNotEqual(id1, id2)
            self.assertTrue(id2.endswith("-2"))

    def test_valid_slugs_create_dir_inside_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_id, run_dir = studio.new_run(tmp, "anza")
            self.assertTrue(run_id.startswith("anza-"))
            self.assertTrue(os.path.isdir(run_dir))
            self.assertTrue(
                Path(run_dir).resolve().is_relative_to(Path(tmp).resolve()))

    def test_invalid_slugs_raise(self):
        # عبور مسار (`..` و`/` و`\`)، وبدء بنقطة، وNUL، وقيمة فارغة.
        bad = ["../evil", "..", ".hidden", "a/b", "a\\b", "a..b",
               "a\x00b", "", "/etc", "anza/../../evil"]
        with tempfile.TemporaryDirectory() as tmp:
            for slug in bad:
                with self.subTest(slug=slug):
                    with self.assertRaises(ValueError):
                        studio.new_run(tmp, slug)
                    # لم يُنشأ أي مجلد هروب داخل مجلد التشغيل
                    self.assertFalse(os.path.exists(os.path.join(tmp, "evil")))

    def test_run_dir_for_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ["../../evil", "/etc", ".hidden", "a/b"]:
                with self.subTest(run_id=bad):
                    with self.assertRaises(ValueError):
                        studio.run_dir_for(tmp, bad)
            ok = studio.run_dir_for(tmp, "anza-20261121-124702")
            self.assertTrue(
                Path(ok).resolve().is_relative_to(Path(tmp).resolve()))


class TestNaturalKey(unittest.TestCase):
    def test_scene2_before_scene10(self):
        names = ["scene10.jpg", "scene2.jpg", "scene1.jpg"]
        self.assertEqual(sorted(names, key=openmontage_stage._natural_key),
                         ["scene1.jpg", "scene2.jpg", "scene10.jpg"])


class TestOpenMontageStage(unittest.TestCase):
    def _project(self, tmp, script=None, words=None):
        proj = os.path.join(tmp, "proj")
        os.makedirs(os.path.join(proj, "artifacts"), exist_ok=True)
        os.makedirs(os.path.join(proj, "assets", "images"), exist_ok=True)
        os.makedirs(os.path.join(proj, "assets", "audio"), exist_ok=True)
        if script is not None:
            with open(os.path.join(proj, "artifacts", "script.json"), "w",
                      encoding="utf-8") as f:
                f.write(script)
        if words is not None:
            with open(os.path.join(proj, "artifacts", "captions.json"),
                      "w", encoding="utf-8") as f:
                json.dump(words, f, ensure_ascii=False)
        return proj

    def test_find_project_valid_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = os.path.join(tmp, "projects", "anza-part1")
            os.makedirs(proj)
            found = openmontage_stage.find_project(tmp, "anza-part1")
            self.assertEqual(found, proj)

    def test_find_project_missing_raises_stage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(openmontage_stage.StageError):
                openmontage_stage.find_project(tmp, "no-such-project")

    def test_find_project_rejects_traversal_names(self):
        bad = ["../../evil", "..", "/etc", ".hidden", "a/b", "a\\b",
               "a..b", "", "x\x00y"]
        with tempfile.TemporaryDirectory() as tmp:
            for name in bad:
                with self.subTest(name=name):
                    with self.assertRaises(ValueError):
                        openmontage_stage.find_project(tmp, name)

    def test_load_script_missing_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._project(tmp)
            with self.assertRaises(openmontage_stage.StageError):
                openmontage_stage.load_script(proj)

    def test_load_script_corrupt_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._project(tmp, script="{not json")
            with self.assertRaises(openmontage_stage.StageError):
                openmontage_stage.load_script(proj)

    def test_load_script_hook(self):
        script = json.dumps({"sections": [
            {"label": "Hook", "text": "هوك صادم"},
            {"label": "Body", "text": "باقي القصة"}]}, ensure_ascii=False)
        with tempfile.TemporaryDirectory() as tmp:
            proj = self._project(tmp, script=script)
            hook, full = openmontage_stage.load_script(proj)
        self.assertEqual(hook, "هوك صادم")
        self.assertIn("باقي القصة", full)

    def test_build_phrases_groups_by_page_break(self):
        words = [
            {"word": "في", "startMs": 0, "endMs": 300},
            {"word": "نص", "startMs": 300, "endMs": 600,
             "pageBreakAfter": True},
            {"word": "الليل", "startMs": 600, "endMs": 1000},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "captions.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(words, f, ensure_ascii=False)
            phrases = openmontage_stage.build_phrases(p)
        self.assertEqual(len(phrases), 2)
        self.assertEqual(phrases[0]["text"], "في نص")
        self.assertAlmostEqual(phrases[0]["end"], 0.6)
        self.assertEqual(phrases[1]["text"], "الليل")
        # توقيتات الكلمات تُحفظ في العبارة لفحص حدود المشاهد
        # (تصحيح 2026-11-22: حد بين كلمتين لا يفشل).
        self.assertEqual(phrases[0]["words"],
                         [{"w": "في", "start": 0.0, "end": 0.3},
                          {"w": "نص", "start": 0.3, "end": 0.6}])
        self.assertEqual(phrases[1]["words"],
                         [{"w": "الليل", "start": 0.6, "end": 1.0}])

    def test_build_phrases_bad_word_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "captions.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump([{"word": "بلا توقيت"}], f, ensure_ascii=False)
            with self.assertRaises(openmontage_stage.StageError):
                openmontage_stage.build_phrases(p)


class TestOmniRouteRetry(unittest.TestCase):
    def test_retry_then_success(self):
        calls = {"n": 0}

        def flaky(model, prompt, system=None, max_tokens=200,
                  temperature=0.7, timeout=180):
            calls["n"] += 1
            if calls["n"] == 1:
                raise omniroute_client.OmniRouteError("انقطاع عابر")
            return "رد تجريبي"

        with mock.patch.dict(os.environ, {"OMNIROUTE_API_KEY": ""}), \
                mock.patch.object(omniroute_client, "chat_cli",
                                  side_effect=flaky):
            text, via, model = omniroute_client.chat(
                "اختبار", "ddgw/gpt-5.4-mini", retries=1, retry_delay=0)
        self.assertEqual(text, "رد تجريبي")
        self.assertEqual(via, "cli")
        self.assertEqual(calls["n"], 2)

    def test_retry_exhausted_raises(self):
        with mock.patch.dict(os.environ, {"OMNIROUTE_API_KEY": ""}), \
                mock.patch.object(
                    omniroute_client, "chat_cli",
                    side_effect=omniroute_client.OmniRouteError("دائمًا فاشل")):
            with self.assertRaises(omniroute_client.OmniRouteError):
                omniroute_client.chat("اختبار", "ddgw/gpt-5.4-mini",
                                      retries=1, retry_delay=0)


class TestThumbnailWrap(unittest.TestCase):
    def test_short_hook_one_line(self):
        self.assertEqual(thumbnail.wrap_hook("طردتني في نص الليل"),
                         ["طردتني في نص الليل"])

    def test_long_hook_two_lines(self):
        lines = thumbnail.wrap_hook("طردتني في نص الليل وبعد سنة باست إيدي")
        self.assertLessEqual(len(lines), 2)
        self.assertEqual(" ".join(lines),
                         "طردتني في نص الليل وبعد سنة باست إيدي")


class TestConcatArabicFeatures(unittest.TestCase):
    """مزايا Concat المُتحقق منها في CONCAT-FEATURES-TEST.md (مشروع
    feat-test، 2026-11-21): إعداد الكابشن العربي وحركة العنوان."""

    def test_caption_style_is_arabic_preset(self):
        style = concat_mcp.CAPTION_STYLE
        self.assertEqual(style["fontFamily"], "Noto Kufi Arabic")
        # لوحة خلفية شبه شفافة لمقروئية النص فوق الصور الفاتحة
        self.assertEqual(style["background"], "#000000B3")
        # حد عرض السطر حتى لا يلتصق النص بحواف الإطار العمودي
        self.assertEqual(style["maxWidth"], 0.9)
        self.assertGreater(style["strokeWidth"], 0)

    def test_title_motion_uses_known_moves(self):
        motion = concat_mcp.TITLE_MOTION
        # أسماء من مخطط Concat: MotionMove (in/out) وClipLoop (loop)
        self.assertIn(motion["in"]["kind"],
                      ("fade", "slide-left", "slide-right", "slide-up",
                       "slide-down", "zoom-in", "zoom-out", "pop", "drop",
                       "rise", "spin", "flip", "swing", "squash"))
        self.assertIn(motion["out"]["kind"],
                      ("fade", "slide-left", "slide-right", "slide-up",
                       "slide-down", "zoom-in", "zoom-out", "pop", "drop",
                       "rise", "spin", "flip", "swing", "squash"))
        self.assertIn(motion["loop"]["kind"],
                      ("pulse", "heartbeat", "float", "wiggle", "sway",
                       "jitter", "spin", "flicker", "breathe"))
        self.assertGreater(motion["in"]["seconds"], 0)
        self.assertGreater(motion["loop"]["seconds"], 0)

    def test_assemble_applies_title_motion_and_arabic_captions(self):
        calls = []

        class FakeMCP:
            """محاكاة MCP الجديد: مدير سياق غير متزامن."""

            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def call(self, tool, args, timeout=300):
                calls.append((tool, args))
                canned = {
                    "project_create": {},
                    "timeline_read": {"tracks": []},
                    "media_import": {"createdId": "m1"},
                    "clips_add_sequence": {},
                    "track_add": {"createdId": "t9"},
                    "clip_add": {"createdId": "c2"},
                    "title_add": {"createdId": "c11"},
                    "captions_add": {},
                    "clip_update": {},
                    "project_save": {},
                    "export_start": {"job": "j1"},
                    "export_wait": {"state": "done"},
                }
                return canned[tool]

            def result(self, res, tool):
                return res

        manifest = {"sequence": ["img.jpg"],
                    "phrases": [{"start": 0, "end": 1,
                                 "text": "في نص الليل"}]}
        video = {"width": 720, "height": 1280, "fps": 30,
                 "codec": "h264", "crf": 23}
        with tempfile.TemporaryDirectory() as tmp:
            assets = os.path.join(tmp, "assets")
            os.makedirs(os.path.join(assets, "images"))
            os.makedirs(os.path.join(assets, "audio"))
            # التصدير الوهمي لا ينشئ ملفًا؛ assemble يتحقق من وجوده
            open(os.path.join(tmp, "out.mp4"), "w").close()
            with mock.patch.object(concat_mcp, "MCP", FakeMCP):
                out = concat_mcp.assemble(
                    "/bin/false", tmp, "p1", assets, manifest,
                    "هوك صادم", os.path.join(tmp, "out.mp4"), video,
                    os.path.join(tmp, "log.jsonl"))
        self.assertEqual(out, os.path.join(tmp, "out.mp4"))
        by_tool = {}
        for tool, args in calls:
            by_tool.setdefault(tool, []).append(args)
        # حركة العنوان تُطبَّق على مقطع العنوان نفسه بعد إنشائه
        motion_calls = [a for a in by_tool.get("clip_update", [])
                        if a.get("patch", {}).get("motion")]
        self.assertEqual(len(motion_calls), 1)
        self.assertEqual(motion_calls[0]["clipId"], "c11")
        self.assertEqual(motion_calls[0]["patch"]["motion"],
                         concat_mcp.TITLE_MOTION)
        # العنوان أسفل الشاشة فوق الكابشنات (قاعدة دائمة
        # 2026-11-22: لا نص أعلى الشاشة أبدًا): كان offsetY=-0.26
        # أعلى الشاشة (وقبله -0.35 يصطدم بالشارة)؛ الآن +0.12
        # (صُحح من +0.17 بعد تداخل حي مع أول عبارة).
        self.assertEqual(by_tool["title_add"][0]["offsetY"], 0.12)
        # الكابشنات تُرسَل بإعداد العربي نفسه
        self.assertEqual(by_tool["captions_add"][0]["style"],
                         concat_mcp.CAPTION_STYLE)

    def test_assemble_replaces_existing_project(self):
        # عيب 2026-11-21: إعادة تجميع نفس التشغيل كانت تفشل لأن
        # Concat يرفض project_create على مجلد مشروع موجود — مجلد
        # المشروع يُعاد بناؤه من البيان في كل تجميع فيُستبدل.
        calls = []

        class FakeMCP:
            """محاكاة MCP الجديد: مدير سياق غير متزامن."""

            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def call(self, tool, args, timeout=300):
                calls.append((tool, args))
                canned = {
                    "project_create": {},
                    "timeline_read": {"tracks": []},
                    "media_import": {"createdId": "m1"},
                    "clips_add_sequence": {},
                    "track_add": {"createdId": "t9"},
                    "clip_add": {"createdId": "c2"},
                    "title_add": {"createdId": "c11"},
                    "captions_add": {},
                    "clip_update": {},
                    "project_save": {},
                    "export_start": {"job": "j1"},
                    "export_wait": {"state": "done"},
                }
                return canned[tool]

            def result(self, res, tool):
                return res

        manifest = {"sequence": ["img.jpg"],
                    "phrases": [{"start": 0, "end": 1,
                                 "text": "في نص الليل"}]}
        video = {"width": 720, "height": 1280, "fps": 30,
                 "codec": "h264", "crf": 23}
        with tempfile.TemporaryDirectory() as tmp:
            assets = os.path.join(tmp, "assets")
            os.makedirs(os.path.join(assets, "images"))
            os.makedirs(os.path.join(assets, "audio"))
            # مجلد مشروع قديم من تجميع سابق بملف داخله
            stale = os.path.join(tmp, "p1", "stale.txt")
            os.makedirs(os.path.dirname(stale))
            with open(stale, "w") as f:
                f.write("قديم")
            open(os.path.join(tmp, "out.mp4"), "w").close()
            with mock.patch.object(concat_mcp, "MCP", FakeMCP):
                out = concat_mcp.assemble(
                    "/bin/false", tmp, "p1", assets, manifest,
                    "هوك صادم", os.path.join(tmp, "out.mp4"), video,
                    os.path.join(tmp, "log.jsonl"))
            self.assertEqual(out, os.path.join(tmp, "out.mp4"))
            self.assertFalse(os.path.exists(stale))


class TestWhisperCaptions(unittest.TestCase):
    """تجميع كلمات whisper في عبارات + توليد ASS — بلا موديل
    (دوال نقية؛ تشغيل الموديل نفسه موثق في WHISPER-TEST.md)."""

    WORDS = [
        {"w": "في", "start": 0.00, "end": 0.16},
        {"w": "نص", "start": 0.16, "end": 0.54},
        {"w": "الليل", "start": 0.54, "end": 1.12},
        {"w": "حماتي", "start": 1.12, "end": 2.46},
        {"w": "طردتني", "start": 2.46, "end": 3.40},
    ]

    def test_groups_on_silence_gap(self):
        phrases = whisper_captions.group_words_into_phrases(
            self.WORDS, max_words=10, max_gap=0.6)
        # لا فجوة > 0.6ث بين الكلمات الخمس → عبارة واحدة
        self.assertEqual(len(phrases), 1)
        self.assertEqual(phrases[0]["text"],
                         "في نص الليل حماتي طردتني")
        self.assertAlmostEqual(phrases[0]["start"], 0.0)
        self.assertAlmostEqual(phrases[0]["end"], 3.40)
        # توقيتات الكلمات تُحفظ في العبارة لفحص حدود المشاهد.
        self.assertEqual(len(phrases[0]["words"]), 5)
        self.assertEqual(phrases[0]["words"][0],
                         {"w": "في", "start": 0.0, "end": 0.16})

    def test_splits_on_gap_and_max_words(self):
        words = self.WORDS + [{"w": "أنا", "start": 5.00, "end": 5.30}]
        phrases = whisper_captions.group_words_into_phrases(
            words, max_words=3, max_gap=0.6)
        self.assertEqual([p["text"] for p in phrases],
                         ["في نص الليل", "حماتي طردتني", "أنا"])

    def test_ass_time_format(self):
        self.assertEqual(whisper_captions.format_ass_time(0), "0:00:00.00")
        self.assertEqual(whisper_captions.format_ass_time(1.5),
                         "0:00:01.50")
        self.assertEqual(whisper_captions.format_ass_time(65.24),
                         "0:01:05.24")

    def test_phrases_to_ass_matches_subs_style(self):
        ass = whisper_captions.phrases_to_ass(
            [{"start": 0.0, "end": 1.12, "text": "في نص الليل"}])
        self.assertIn("Noto Naskh Arabic,52", ass)
        self.assertIn("Dialogue: 0,0:00:00.00,0:00:01.12,"
                      "Default,,0,0,0,,في نص الليل", ass)

    def test_load_wav_16k_resamples(self):
        import math
        import wave
        with tempfile.NamedTemporaryFile(suffix=".wav",
                                        delete=False) as tmp:
            path = tmp.name
        try:
            with wave.open(path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(22050)
                frames = b"".join(
                    int(10000 * math.sin(2 * math.pi * 440 * i / 22050))
                    .to_bytes(2, "little", signed=True)
                    for i in range(22050))
                w.writeframes(frames)
            audio = whisper_captions.load_wav_16k(path)
            self.assertAlmostEqual(len(audio), 16000, delta=2)
            self.assertTrue(all(-1.0 <= s <= 1.0 for s in audio))
        finally:
            os.unlink(path)

    def test_ensure_wav_passes_wav_through(self):
        path, tmpdir = whisper_captions.ensure_wav("/tmp/x.wav")
        self.assertEqual(path, "/tmp/x.wav")
        self.assertIsNone(tmpdir)

    def test_transcribe_without_faster_whisper_errors_clearly(self):
        # في بيئة python3 النظامية faster-whisper غير مثبّت (في
        # .venv-whisper فقط) — يجب أن يكون الخطأ إرشاديًا لا غامضًا.
        with mock.patch.dict("sys.modules", {"faster_whisper": None}):
            with self.assertRaises(whisper_captions.WhisperError) as cm:
                whisper_captions.transcribe_words("/tmp/x.wav")
        self.assertIn(".venv-whisper", str(cm.exception))


class TestRunQueue(unittest.TestCase):
    """قراءة ملف الطابور + جاهزية المشروع + سلوك الدفعة (بمحاكاة
    cmd_run — لا تصدير حقيقي هنا)."""

    QUEUE_TEXT = """# قائمة قصص

## المنشور

1. **قصة منشورة** — نُشرت أمس

## في الانتظار (بالترتيب)

3. **عائشة الأرملة في السودان** — أرض قاحلة، بئر وذهب.
4. **العنزة المباركة** — القاهرة 1184هـ. تحتاج جزأين.
5. **عجائب الصدقة** — مهندس راتب 9000 ريال.

## دفعة ثانية — وصلت بعد الظهر

9. **لا تعطي سرك لأحد** — منشور واحد.
10. **الظالم والصياد** — سمكة وعضة.
"""

    def _write_queue(self, tmp):
        p = os.path.join(tmp, "queue.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(self.QUEUE_TEXT)
        return p

    def _cfg(self, tmp):
        cfg = studio.load_config()
        cfg["paths"]["queue_file"] = os.path.join(tmp, "queue.md")
        cfg["paths"]["runs_dir"] = os.path.join(tmp, "runs")
        cfg["paths"]["videos_dir"] = os.path.join(tmp, "videos")
        cfg["openmontage"]["projects_dir"] = os.path.join(tmp, "projects")
        return cfg

    def test_parse_queue_only_waiting_sections_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            stories = studio.parse_queue(self._write_queue(tmp))
        self.assertEqual([s["number"] for s in stories],
                         [3, 4, 5, 9, 10])
        self.assertEqual(stories[1]["title"], "العنزة المباركة")
        # القصة المنشورة (رقم 1) لا تدخل الطابور
        self.assertNotIn(1, [s["number"] for s in stories])

    def test_check_ready_only_anza_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._cfg(tmp)
            os.makedirs(os.path.join(tmp, "projects", "anza-part1"))
            stories = studio.parse_queue(self._write_queue(tmp))
            ready, slug, project, _ = studio.check_story_ready(
                cfg, stories[1])
            self.assertTrue(ready)
            self.assertEqual((slug, project), ("anza", "anza-part1"))
            ready, _, _, reason = studio.check_story_ready(
                cfg, stories[0])
            self.assertFalse(ready)
            self.assertIn("يحتاج تجهيز مشروع", reason)

    def test_dry_run_prints_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._cfg(tmp)
            self._write_queue(tmp)
            os.makedirs(os.path.join(tmp, "projects", "anza-part1"))
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = studio.cmd_run_queue(cfg, limit=2, dry_run=True)
            self.assertEqual(rc, 0)
            self.assertIn("العنزة المباركة", buf.getvalue())
            self.assertIn("تُتخطى", buf.getvalue())
            self.assertFalse(os.path.exists(
                os.path.join(tmp, "runs")))

    def test_real_queue_skips_unready_and_runs_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._cfg(tmp)
            self._write_queue(tmp)
            os.makedirs(os.path.join(tmp, "projects", "anza-part1"))
            calls = []

            def fake_run(cfg_, story, project, out, allow_fallback):
                calls.append((story, project))
                return 0

            with mock.patch.object(studio, "cmd_run",
                                   side_effect=fake_run):
                rc = studio.cmd_run_queue(cfg, limit=2,
                                          allow_fallback=True)
            self.assertEqual(rc, 0)
            self.assertEqual(calls, [("anza", "anza-part1")])
            logs = os.listdir(os.path.join(tmp, "runs"))
            self.assertEqual(len(logs), 1)
            self.assertTrue(logs[0].startswith("queue-"))
            with open(os.path.join(tmp, "runs", logs[0]),
                      encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(
                [s["status"] for s in data["stories"]],
                ["skipped", "done"])

    def test_failure_stops_without_continue_on_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._cfg(tmp)
            os.makedirs(os.path.join(tmp, "projects", "anza-part1"))
            # قصة العنزة جاهزة مرتين في الطابور المعدّل
            with open(os.path.join(tmp, "queue.md"), "w",
                      encoding="utf-8") as f:
                f.write("## في الانتظار\n\n"
                        "4. **العنزة المباركة** — أولى.\n"
                        "4. **العنزة المباركة** — ثانية.\n")
            calls = {"n": 0}

            def failing_run(cfg_, story, project, out, allow_fallback):
                calls["n"] += 1
                return 1

            with mock.patch.object(studio, "cmd_run",
                                   side_effect=failing_run):
                rc = studio.cmd_run_queue(cfg, continue_on_error=False)
            self.assertEqual(rc, 1)
            self.assertEqual(calls["n"], 1)


class TestRefAnalyzer(unittest.TestCase):
    """تحليل الفيديو المرجعي — دوال نقية + تنسيق بمحاكاة الشبكة
    والتفريغ (لا تنزيل حقيقي هنا)."""

    WORDS = [
        {"w": "في", "start": 0.5, "end": 0.8},
        {"w": "نص", "start": 0.8, "end": 1.2},
        {"w": "الليل", "start": 1.2, "end": 1.9},
        {"w": "طردتني", "start": 2.0, "end": 2.8},
        {"w": "حماتي", "start": 50.0, "end": 50.6},
        {"w": "صح؟", "start": 50.6, "end": 51.0},
    ]

    def test_video_id_from_url(self):
        from lib import ref_analyzer
        self.assertEqual(ref_analyzer.video_id_from_url(
            "https://www.youtube.com/watch?v=IeUkpZ3X8Lw"),
            "IeUkpZ3X8Lw")
        self.assertEqual(ref_analyzer.video_id_from_url(
            "https://www.youtube.com/shorts/3IH3H8wWPw8"),
            "3IH3H8wWPw8")
        self.assertEqual(ref_analyzer.video_id_from_url(
            "https://youtu.be/bU7U50uViBM?t=5"), "bU7U50uViBM")
        self.assertIsNone(ref_analyzer.video_id_from_url(
            "https://www.facebook.com/OyoonElshaab/"))

    def test_analyze_words_hook_wpm_ending_question(self):
        from lib import ref_analyzer
        a = ref_analyzer.analyze_words(self.WORDS, 60.0)
        self.assertEqual(a["hook_first_10s"], "في نص الليل طردتني")
        self.assertEqual(a["word_count"], 6)
        self.assertEqual(a["words_per_minute"], 6.0)
        self.assertEqual(a["ending_last_10s"], "حماتي صح؟")
        self.assertTrue(a["ending_has_question"])

    def test_fetch_metadata_parses_dump_json(self):
        from lib import ref_analyzer
        payload = json.dumps({
            "id": "IeUkpZ3X8Lw", "title": "قصة تجريبية",
            "uploader": "قناة تجريبية", "duration": 60,
            "view_count": 1234, "like_count": 56,
            "upload_date": "20261120"}, ensure_ascii=False)

        class R:
            returncode = 0
            stdout = payload
            stderr = ""

        with mock.patch.object(ref_analyzer.shutil, "which",
                               return_value="/usr/bin/yt-dlp"), \
                mock.patch.object(ref_analyzer, "_run", return_value=R()):
            meta = ref_analyzer.fetch_metadata(
                "https://www.youtube.com/watch?v=IeUkpZ3X8Lw")
        self.assertEqual(meta["title"], "قصة تجريبية")
        self.assertEqual(meta["duration_seconds"], 60)
        self.assertEqual(meta["view_count"], 1234)

    def test_fetch_metadata_failure_raises_ref_error(self):
        from lib import ref_analyzer

        class R:
            returncode = 1
            stdout = ""
            stderr = "ERROR: Video unavailable"

        with mock.patch.object(ref_analyzer.shutil, "which",
                               return_value="/usr/bin/yt-dlp"), \
                mock.patch.object(ref_analyzer, "_run", return_value=R()):
            with self.assertRaises(ref_analyzer.RefError):
                ref_analyzer.fetch_metadata(
                    "https://www.youtube.com/watch?v=xxxxxxxxxxx")

    def test_analyze_reference_skips_transcription_gracefully(self):
        from lib import ref_analyzer
        meta = {"id": "abc123", "url": "https://example.invalid/v",
                "title": "ت", "uploader": "ق", "duration_seconds": 30,
                "view_count": 0, "like_count": 0, "upload_date": ""}
        with mock.patch.object(ref_analyzer, "fetch_metadata",
                               return_value=meta), \
                mock.patch.object(ref_analyzer, "download_audio",
                                  return_value="/tmp/audio.wav"), \
                mock.patch.object(
                    ref_analyzer, "transcribe_audio",
                    side_effect=ref_analyzer.RefError("بلا whisper")):
            res = ref_analyzer.analyze_reference(
                "https://example.invalid/v")
        self.assertEqual(res["transcription"]["status"], "skipped")
        self.assertIsNone(res["analysis"])
        self.assertIn("للاستخدام الخاص فقط", res["notice"])


class TestHeadlessStage(unittest.TestCase):
    """ربط headless-editor — بناء المشروع (نقي) + استدعاء الريندر
    (محاكاة لعملية editor.py)."""

    MANIFEST = {
        "project": "anza-part1",
        "sequence": ["scene1.jpg", "scene2.jpg", "scene3.jpg"],
        "image_clip_seconds": 5,
        "narration_duration": 14.0,
        "phrases": [
            {"start": 0.0, "end": 4.0, "text": "عبارة أولى"},
            {"start": 4.0, "end": 9.0, "text": "عبارة ثانية"},
        ],
    }
    VIDEO = {"width": 720, "height": 1280, "fps": 30,
             "image_clip_seconds": 5}

    def _project(self, title="هوك تجريبي"):
        from lib import headless_stage
        return headless_stage.build_project(
            self.MANIFEST, title, "/tmp/assets", self.VIDEO)

    def test_image_clips_hard_cuts_cover_sequence(self):
        p = self._project()
        imgs = [t for t in p["tracks"] if t["type"] == "image"]
        self.assertEqual(len(imgs), 3)
        self.assertEqual([(t["start"], t["duration"]) for t in imgs],
                         [(0.0, 5), (5.0, 5), (10.0, 5)])
        self.assertTrue(all(t["transition_in"] == "none" for t in imgs))

    def test_last_image_extends_to_cover_narration(self):
        # سرد 14 ث مع 3 صور × 5 ث = 15 ث — لا تمديد (الصور تغطي).
        # بسرد أطول من الصور (17 ث) يمتد المقطع الأخير للفرق فقط.
        from lib import headless_stage
        manifest = dict(self.MANIFEST, narration_duration=17.0)
        p = headless_stage.build_project(manifest, "هوك", "/tmp/assets",
                                         self.VIDEO)
        imgs = [t for t in p["tracks"] if t["type"] == "image"]
        self.assertEqual(imgs[-1]["duration"], 7.0)
        self.assertEqual(imgs[-1]["start"], 10.0)
        total = sum(t["duration"] for t in imgs)
        self.assertAlmostEqual(total, 17.0)

    def test_audio_track_uses_narration_duration(self):
        p = self._project()
        aud = [t for t in p["tracks"] if t["type"] == "audio"]
        self.assertEqual(len(aud), 1)
        self.assertEqual(aud[0]["src"],
                         "/tmp/assets/audio/narration-full.wav")
        self.assertEqual(aud[0]["duration"], 14.0)
        self.assertEqual(aud[0]["volume"], 1.0)

    def test_hook_and_phrases_as_text_tracks(self):
        p = self._project()
        texts = [t for t in p["tracks"] if t["type"] == "text"]
        hook = texts[0]
        self.assertEqual(hook["text"], "هوك تجريبي")
        self.assertEqual((hook["start"], hook["end"]), (0, 4.0))
        self.assertEqual(hook["position"], "above")
        self.assertEqual(hook["fontsize"], 58)
        caps = texts[1:]
        self.assertEqual(len(caps), 2)
        self.assertEqual(caps[0]["text"], "عبارة أولى")
        self.assertEqual((caps[0]["start"], caps[0]["end"]), (0.0, 4.0))
        self.assertEqual(caps[0]["position"], "bottom")

    def test_empty_title_skips_hook_track(self):
        p = self._project(title="")
        texts = [t for t in p["tracks"] if t["type"] == "text"]
        self.assertEqual(len(texts), 2)  # العبارتان فقط

    def test_dimensions_from_video_config(self):
        p = self._project()
        self.assertEqual((p["width"], p["height"], p["fps"]),
                         (720, 1280, 30))

    def test_render_success_returns_seconds_and_size(self):
        from lib import headless_stage
        with tempfile.TemporaryDirectory() as d:
            editor = os.path.join(d, "editor.py")
            with open(editor, "w") as f:
                f.write("# fake editor\n")
            out = os.path.join(d, "out.mp4")

            class R:
                returncode = 0
                stdout = "تم الريندر بنجاح"
                stderr = ""

            def fake_run(cmd, **kw):
                self.assertIn("render", cmd)
                self.assertIn(out, cmd)
                with open(out, "wb") as f:
                    f.write(b"fake-mp4")
                return R()

            with mock.patch.object(headless_stage.subprocess, "run",
                                  side_effect=fake_run):
                res = headless_stage.render_project(
                    editor, os.path.join(d, "project.json"), out)
            self.assertEqual(res["output"], out)
            self.assertEqual(res["size_bytes"], 8)
            self.assertIn("seconds", res)

    def test_render_failure_raises_headless_error(self):
        from lib import headless_stage
        with tempfile.TemporaryDirectory() as d:
            editor = os.path.join(d, "editor.py")
            with open(editor, "w") as f:
                f.write("# fake editor\n")

            class R:
                returncode = 1
                stdout = ""
                stderr = "ffmpeg boom"

            with mock.patch.object(headless_stage.subprocess, "run",
                                  return_value=R()):
                with self.assertRaises(headless_stage.HeadlessError) as ctx:
                    headless_stage.render_project(
                        editor, os.path.join(d, "project.json"),
                        os.path.join(d, "nope.mp4"))
        self.assertIn("ffmpeg boom", str(ctx.exception))

    def test_render_missing_editor_raises(self):
        from lib import headless_stage
        with self.assertRaises(headless_stage.HeadlessError):
            headless_stage.render_project("/no/such/editor.py",
                                          "/fake/project.json",
                                          "/tmp/nope.mp4")


class TestAutoEdit(unittest.TestCase):
    """تنظيف الصوت الخام عبر Auto-Editor — حارس السرد النهائي +
    بناء الأمر + مسار الفشل والنجاح (محاكاة)."""

    def test_final_narration_path_detection(self):
        from lib import autoedit
        self.assertTrue(autoedit.is_final_narration_path(
            "/x/videos/narration-male/scene1.wav"))
        self.assertTrue(autoedit.is_final_narration_path(
            "/x/videos/narration/scene1.wav"))
        self.assertFalse(autoedit.is_final_narration_path(
            "/tmp/raw-with-silence.wav"))
        self.assertFalse(autoedit.is_final_narration_path(
            "/x/narration-notes.txt"))

    def test_build_command(self):
        from lib import autoedit
        cmd = autoedit.build_command("/bin/auto-editor", "/tmp/in.wav",
                                     "/tmp/out.wav")
        self.assertEqual(cmd[0], "/bin/auto-editor")
        self.assertIn("--edit", cmd)
        self.assertIn("audio:threshold=0.02", cmd)
        self.assertIn("--no-open", cmd)
        self.assertIn("/tmp/out.wav", cmd)

    def test_clean_refuses_final_narration_without_force(self):
        from lib import autoedit
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "narration-male", "scene1.wav")
            os.makedirs(os.path.dirname(src))
            with open(src, "wb") as f:
                f.write(b"fake")
            with self.assertRaises(autoedit.AutoEditError) as ctx:
                autoedit.clean_audio(src, os.path.join(d, "out.wav"))
        self.assertIn("سرد نهائي", str(ctx.exception))

    def test_clean_missing_input_raises(self):
        from lib import autoedit
        with self.assertRaises(autoedit.AutoEditError):
            autoedit.clean_audio("/no/such/file.wav", "/tmp/out.wav")

    def test_clean_bad_threshold_raises(self):
        from lib import autoedit
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "raw.wav")
            with open(src, "wb") as f:
                f.write(b"fake")
            with self.assertRaises(autoedit.AutoEditError):
                autoedit.clean_audio(src, os.path.join(d, "out.wav"),
                                     threshold=2.0)

    def test_clean_success_with_mock(self):
        from lib import autoedit
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "raw.wav")
            with open(src, "wb") as f:
                f.write(b"fake")
            out = os.path.join(d, "clean.wav")
            editor = os.path.join(d, "auto-editor")
            with open(editor, "w") as f:
                f.write("# fake\n")

            class R:
                returncode = 0
                stdout = ""
                stderr = ""

            def fake_run(cmd, **kw):
                with open(out, "wb") as f:
                    f.write(b"clean")
                return R()

            with mock.patch.object(autoedit.subprocess, "run",
                                  side_effect=fake_run), \
                    mock.patch.object(autoedit, "find_auto_editor",
                                     return_value=editor):
                res = autoedit.clean_audio(src, out)
            self.assertEqual(res["size_bytes"], 5)
            self.assertIn("seconds", res)


class TestMoviePyFx(unittest.TestCase):
    """مساعد MoviePy — حساب التكبير والنافذة (نقي) + إعادة تشكيل
    العربية (يعمل فقط حيث مكتبتا التشكيل مثبّتتان) + مسارات الخطأ."""

    def test_zoom_at(self):
        from lib import moviepy_fx
        self.assertEqual(moviepy_fx.zoom_at(0, 5.0, 1.15), 1.0)
        self.assertAlmostEqual(moviepy_fx.zoom_at(5.0, 5.0, 1.15), 1.15)
        self.assertAlmostEqual(moviepy_fx.zoom_at(2.5, 5.0, 1.15), 1.075)
        self.assertEqual(moviepy_fx.zoom_at(10.0, 5.0, 1.15), 1.15)

    def test_zoom_at_invalid(self):
        from lib import moviepy_fx
        with self.assertRaises(moviepy_fx.MoviePyFxError):
            moviepy_fx.zoom_at(0, 0, 1.15)
        with self.assertRaises(moviepy_fx.MoviePyFxError):
            moviepy_fx.zoom_at(0, 5.0, 0.9)

    def test_crop_window_aspect_and_bounds(self):
        from lib import moviepy_fx
        # صورة غلاف 1706×1280، خرج 720×1280
        x0, y0, ww, wh = moviepy_fx.crop_window(1706, 1280, 1.0)
        self.assertEqual((ww, wh), (720, 1280))
        self.assertEqual((x0, y0), (493, 0))
        # مع التكبير تصغر النافذة وتبقى داخل الصورة
        x0, y0, ww2, wh2 = moviepy_fx.crop_window(1706, 1280, 1.15)
        self.assertLess(ww2, ww)
        self.assertLess(wh2, wh)
        self.assertTrue(0 <= x0 and x0 + ww2 <= 1706)
        self.assertTrue(0 <= y0 and y0 + wh2 <= 1280)
        self.assertAlmostEqual(ww2 / wh2, 720 / 1280, places=2)

    @unittest.skipUnless(
        importlib.util.find_spec("PIL") is not None,
        "Pillow غير مثبّت في بايثون الحالي")
    @unittest.skipUnless(
        # جولة v0.1.41 (إصلاح CI): خط Noto Naskh Arabic مثبّت
        # محليًا فقط؛ في CI يثبّته سير العمل (fonts-noto-core)
        # والحراسة دفاع إضافي إن غاب (نمط test_ci_skips).
        os.path.isfile("/usr/share/fonts/truetype/noto/"
                       "NotoNaskhArabic-Bold.ttf"),
        "خط Noto Naskh Arabic غائب — بيئة CI بلا fonts-noto-core")
    def test_render_arabic_text_image(self):
        from lib import moviepy_fx
        img = moviepy_fx.render_arabic_text_image("عنزة صغيرة")
        self.assertEqual(img.mode, "RGBA")
        self.assertLessEqual(img.width, 660 + 20)
        # فيها بكسلات نص غير شفافة فعلًا
        alpha = img.split()[3]
        self.assertGreater(max(alpha.get_flattened_data()), 0)
        # نص طويل يُصغَّر ليدخل العرض الأقصى
        img2 = moviepy_fx.render_arabic_text_image(
            "عنزة صغيرة هزّت القاهرة كلها والناس ركعوا لها في 1184",
            max_width=300)
        self.assertLessEqual(img2.width, 300 + 20)

    def test_render_arabic_text_empty_raises(self):
        from lib import moviepy_fx
        with self.assertRaises(moviepy_fx.MoviePyFxError):
            moviepy_fx.render_arabic_text_image("   ")

    def test_ken_burns_missing_image_raises(self):
        from lib import moviepy_fx
        with self.assertRaises(moviepy_fx.MoviePyFxError):
            moviepy_fx.ken_burns_clip("/no/such/image.jpg", 5.0)

    def test_render_missing_image_raises(self):
        from lib import moviepy_fx
        with self.assertRaises(moviepy_fx.MoviePyFxError):
            moviepy_fx.render_fx("/no/such/image.jpg", "/tmp/x.mp4", 5.0)


class TestCapiteCaptions(unittest.TestCase):
    """كابشنات الكاريوكي (منطق Capite مُعاد تنفيذه) — تجميع الأسطر
    + توقيت الأحداث + نص سليم بلا تقسيم لوني (v0.1.47: libass
    يعكس مقاطع RTL المقسّمة ب{\\c}...{\\r}) + قاعدة اليتيم."""

    def _timed(self, texts):
        t = 0.0
        out = []
        for w in texts:
            out.append({"w": w, "start": round(t, 2),
                        "end": round(t + 0.4, 2)})
            t += 0.5
        return out

    def _words(self):
        # 10 كلمات عربية بتوقيتات متتابعة (مثل سرد حماتي م1)
        texts = ["في", "نص", "الليل", "حماتي", "طردتني", "أنا",
                 "وبنتي", "الصغيرة", "في", "الشارع"]
        return self._timed(texts)

    def test_group_fits_one_line(self):
        from lib import capite_captions
        groups = capite_captions.group_words_into_lines(
            self._words(), max_chars=60, max_lines=2)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]["lines"]), 1)

    def test_group_wraps_to_second_line(self):
        from lib import capite_captions
        groups = capite_captions.group_words_into_lines(
            self._words(), max_chars=15, max_lines=2)
        # المجموعة الأولى سطران: [في نص الليل] و[حماتي طردتني]،
        # ثم مجموعات جديدة لباقي الكلمات
        self.assertEqual(len(groups[0]["lines"]), 2)
        total = sum(len(ln) for g in groups for ln in g["lines"])
        self.assertEqual(total, 10)

    def test_group_starts_new_group_when_full(self):
        from lib import capite_captions
        groups = capite_captions.group_words_into_lines(
            self._words(), max_chars=8, max_lines=2)
        self.assertGreater(len(groups), 1)
        total = sum(len(ln) for g in groups for ln in g["lines"])
        self.assertEqual(total, 10)

    def test_events_plain_text_no_colour_split(self):
        from lib import capite_captions
        ass_text, groups = capite_captions.words_to_karaoke_ass(
            self._words(), max_chars=60)
        dialogues = [ln for ln in ass_text.splitlines()
                     if ln.startswith("Dialogue:")]
        self.assertEqual(len(dialogues), 10)
        # v0.1.47: بلا تقسيم لوني إطلاقًا (لا {\c ولا {\r}) — النص
        # سليم حرفيًا، وبنية التوقيت (حدث لكل كلمة) كما هي
        self.assertNotIn("\\kf", ass_text)
        self.assertNotIn("\\c", ass_text)
        self.assertNotIn("\\r", ass_text)
        self.assertIn("في نص الليل حماتي طردتني أنا وبنتي الصغيرة في الشارع",
                      dialogues[0])
        # الحدث الأول ينتهي عند بداية الكلمة الثانية ناقص 10ms
        self.assertIn("0:00:00.00,0:00:00.49", dialogues[0])

    def test_line_text_plain_with_active_word(self):
        from lib import capite_captions
        line = self._timed(["في", "نص", "الليل"])
        # الكلمة النشطة وسطية — الخرج نص سليم بلا وسوم لون
        self.assertEqual(
            capite_captions._line_text(line, 1), "في نص الليل")
        # والنشطة أول/آخر تعطي النص نفسه
        self.assertEqual(
            capite_captions._line_text(line, 0), "في نص الليل")
        self.assertEqual(
            capite_captions._line_text(line, 2), "في نص الليل")
        for active in (0, 1, 2):
            text = capite_captions._line_text(line, active)
            self.assertNotIn("\\c", text)
            self.assertNotIn("\\r", text)

    def test_orphan_function_word_moves_to_next_line(self):
        from lib import capite_captions
        # «في» كانت ستنهي السطر الأول — تنتقل لبداية السطر التالي
        groups = capite_captions.group_words_into_lines(
            self._timed(["ذهب", "الرجل", "في", "السوق"]),
            max_chars=15, max_lines=2)
        self.assertEqual(len(groups), 1)
        lines = [[w["w"] for w in ln] for ln in groups[0]["lines"]]
        self.assertEqual(lines, [["ذهب", "الرجل"], ["في", "السوق"]])
        # ومع علامة ترقيم ملتصقة («في،») تُعامل كوظيفية أيضًا
        groups = capite_captions.group_words_into_lines(
            self._timed(["ذهب", "الرجل", "في،", "السوق"]),
            max_chars=15, max_lines=2)
        lines = [[w["w"] for w in ln] for ln in groups[0]["lines"]]
        self.assertEqual(lines, [["ذهب", "الرجل"], ["في،", "السوق"]])
        # وكل الكلمات محفوظة بلا فقدان
        total = sum(len(ln) for g in groups for ln in g["lines"])
        self.assertEqual(total, 4)

    def test_orphan_single_function_word_line_stays(self):
        from lib import capite_captions
        # «في» وحدها في السطر — لا تُنقل (حتى لا يُترك سطر فارغ)
        groups = capite_captions.group_words_into_lines(
            self._timed(["في", "الشارع", "الكبير"]),
            max_chars=8, max_lines=2)
        lines = [[w["w"] for w in ln] for ln in groups[0]["lines"]]
        self.assertEqual(lines, [["في"], ["الشارع"]])
        total = sum(len(ln) for g in groups for ln in g["lines"])
        self.assertEqual(total, 3)

    def test_english_grouping_unaffected(self):
        from lib import capite_captions
        # كلمات إنجليزية لا تطابق القائمة العربية أبدًا — حتى "in"
        # في آخر سطر لا تُنقل
        groups = capite_captions.group_words_into_lines(
            self._timed(["go", "in", "the", "house"]),
            max_chars=6, max_lines=2)
        lines = [[w["w"] for w in ln] for ln in groups[0]["lines"]]
        self.assertEqual(lines, [["go", "in"], ["the"]])
        groups = capite_captions.group_words_into_lines(
            self._timed(["the", "quick", "brown", "fox"]),
            max_chars=10, max_lines=2)
        lines = [[w["w"] for w in ln] for ln in groups[0]["lines"]]
        self.assertEqual(lines, [["the", "quick"], ["brown", "fox"]])

    def test_escape_ass_text(self):
        from lib import capite_captions
        self.assertEqual(capite_captions.escape_ass_text("a{b}\\c"),
                         "a\\{b\\}\\\\c")

    def test_empty_words_raises(self):
        from lib import capite_captions
        with self.assertRaises(capite_captions.CapiteError):
            capite_captions.words_to_karaoke_ass([])


class TestTrim(unittest.TestCase):
    """القص بلا إعادة ترميز — بناء الأمر + التحقق من المدخلات +
    مسار النجاح (محاكاة)."""

    def test_build_command_lossless(self):
        from lib import trim
        cmd = trim.build_command("/tmp/in.mp4", "/tmp/out.mp4",
                                 2.0, 4.0)
        self.assertEqual(cmd[0], "ffmpeg")
        self.assertIn("-c", cmd)
        self.assertIn("copy", cmd)
        # بحث سريع: -ss قبل -i
        self.assertLess(cmd.index("-ss"), cmd.index("-i"))
        self.assertNotIn("libx264", cmd)

    def test_build_command_exact_reencodes(self):
        from lib import trim
        cmd = trim.build_command("/tmp/in.mp4", "/tmp/out.mp4",
                                 2.0, 4.0, exact=True)
        self.assertIn("libx264", cmd)
        self.assertNotIn("copy", cmd)
        # بحث دقيق: -ss بعد -i
        self.assertGreater(cmd.index("-ss"), cmd.index("-i"))

    def test_trim_missing_input_raises(self):
        from lib import trim
        with self.assertRaises(trim.TrimError):
            trim.trim_lossless("/no/such.mp4", "/tmp/out.mp4",
                               start=0, duration=2)

    def test_trim_both_end_and_duration_raises(self):
        from lib import trim
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "in.mp4")
            with open(src, "wb") as f:
                f.write(b"fake")
            with self.assertRaises(trim.TrimError):
                trim.trim_lossless(src, os.path.join(d, "out.mp4"),
                                   start=0, end=5, duration=5)

    def test_trim_negative_start_raises(self):
        from lib import trim
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "in.mp4")
            with open(src, "wb") as f:
                f.write(b"fake")
            with self.assertRaises(trim.TrimError):
                trim.trim_lossless(src, os.path.join(d, "out.mp4"),
                                   start=-1, duration=2)

    def test_trim_success_with_mock(self):
        from lib import trim
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "in.mp4")
            with open(src, "wb") as f:
                f.write(b"fake")
            out = os.path.join(d, "out.mp4")

            class R:
                returncode = 0
                stdout = ""
                stderr = ""

            def fake_run(cmd, **kw):
                with open(out, "wb") as f:
                    f.write(b"trimmed")
                return R()

            with mock.patch.object(trim.subprocess, "run",
                                  side_effect=fake_run), \
                    mock.patch.object(trim, "probe_duration",
                                     return_value=4.2):
                res = trim.trim_lossless(src, out, start=2.0, end=6.0)
            self.assertEqual(res["size_bytes"], 7)
            self.assertAlmostEqual(res["out_duration"], 4.2)
            self.assertFalse(res["exact"])


class TestMltStage(unittest.TestCase):
    """خلفية MLT/melt — زمن MLT + بناء XML + مسار الريندر (محاكاة)."""

    def _manifest(self):
        return {
            "project": "anza-part1",
            "sequence": ["a.jpg", "b.jpg"],
            "image_clip_seconds": 5,
            "narration_duration": 11.0,
            "phrases": [
                {"text": "عبارة أولى", "start": 0.5, "end": 4.5},
                {"text": "عبارة ثانية", "start": 5.5, "end": 9.5},
            ],
        }

    def test_format_timecode(self):
        from lib import mlt_stage
        self.assertEqual(mlt_stage.format_timecode(0), "00:00:00.000")
        self.assertEqual(mlt_stage.format_timecode(4.5), "00:00:04.500")
        self.assertEqual(mlt_stage.format_timecode(65.25), "00:01:05.250")
        self.assertEqual(mlt_stage.format_timecode(-1), "00:00:00.000")

    def test_build_mlt_structure(self):
        from lib import mlt_stage
        import xml.etree.ElementTree as ET
        xml_text = mlt_stage.build_mlt(
            self._manifest(), "هوك صادم", "/tmp/assets",
            {"width": 720, "height": 1280, "fps": 30,
             "image_clip_seconds": 5})
        root = ET.fromstring(xml_text)
        self.assertEqual(root.tag, "mlt")
        profile = root.find("profile")
        self.assertEqual(profile.get("width"), "720")
        self.assertEqual(profile.get("height"), "1280")
        # صورتان في القائمة + منتجا صور + سرد
        playlist = root.find("playlist")
        self.assertEqual(len(list(playlist)), 2)
        producers = [p for p in root.findall("producer")
                     if p.get("id", "").startswith("img")]
        self.assertEqual(len(producers), 2)
        self.assertEqual(producers[0].find(
            "property[@name='mlt_service']").text, "qimage")
        self.assertEqual(producers[0].find(
            "property[@name='ttl']").text, "150")
        # آخر صورة ممددة لتغطي السرد (11ث: 5 + 6)
        self.assertEqual(producers[1].find(
            "property[@name='ttl']").text, "180")
        narration = [p for p in root.findall("producer")
                     if p.get("id") == "narration"]
        self.assertEqual(len(narration), 1)
        # التايم لاين: مساران + انتقال mix + 3 مرشحات نص
        tractor = root.find("tractor")
        tracks = tractor.findall("track")
        self.assertEqual(len(tracks), 2)
        self.assertEqual(tracks[1].get("hide"), "video")
        filters = tractor.findall("filter")
        self.assertEqual(len(filters), 3)
        # ترتيب المستند: المنتجات قبل القوائم قبل التراكتور قبل
        # main_bin (مرجع أمامي يُسقَط بصمت من محلل melt)
        tags = [c.tag for c in root]
        first_producer = tags.index("producer")
        first_playlist = tags.index("playlist")
        tractor_idx = tags.index("tractor")
        playlists = [i for i, t in enumerate(tags) if t == "playlist"]
        self.assertLess(first_producer, first_playlist)
        self.assertLess(first_playlist, tractor_idx)
        self.assertLess(tractor_idx, playlists[-1])
        main_bin = [p for p in root.findall("playlist")
                    if p.get("id") == "main_bin"]
        self.assertEqual(len(main_bin), 1)
        self.assertEqual(main_bin[0].find("entry").get("producer"),
                         "timeline")
        services = [f.find("property[@name='mlt_service']").text
                    for f in filters]
        self.assertEqual(services, ["dynamictext"] * 3)
        hook = filters[0]
        self.assertEqual(hook.find("property[@name='argument']").text,
                         "هوك صادم")
        self.assertEqual(hook.find("property[@name='family']").text,
                         "Noto Naskh Arabic")

    def test_build_mlt_no_duration_raises(self):
        from lib import mlt_stage
        with self.assertRaises(mlt_stage.MltError):
            mlt_stage.build_mlt(
                {"sequence": [], "narration_duration": 0},
                "عنوان", "/tmp/assets",
                {"width": 720, "height": 1280, "fps": 30})

    def test_render_missing_file_raises(self):
        from lib import mlt_stage
        with self.assertRaises(mlt_stage.MltError):
            mlt_stage.render_mlt("/no/such.mlt", "/tmp/out.mp4")

    def test_render_success_with_mock(self):
        from lib import mlt_stage
        with tempfile.TemporaryDirectory() as d:
            mlt_path = os.path.join(d, "proj.mlt")
            with open(mlt_path, "w") as f:
                f.write("<mlt/>")
            out = os.path.join(d, "out.mp4")

            class FakePopen:
                pid = 4242
                returncode = 0

                def __init__(self, cmd, **kw):
                    assert "/usr/bin/melt" in cmd
                    assert kw.get("start_new_session") is True
                    self._cmd = cmd

                def communicate(self, timeout=None):
                    with open(out, "wb") as f:
                        f.write(b"rendered")
                    return ("", "")

                def wait(self, timeout=None):
                    return self.returncode

            with mock.patch.object(mlt_stage.subprocess, "Popen",
                                   side_effect=FakePopen), \
                    mock.patch.object(mlt_stage, "find_melt",
                                     return_value="/usr/bin/melt"):
                res = mlt_stage.render_mlt(mlt_path, out)
            self.assertEqual(res["size_bytes"], 8)

    def test_render_timeout_kills_process_group(self):
        # المهلة يجب أن تقتل مجموعة عمليات melt كلها (لا xvfb-run
        # وحده) — وإلا يبقى melt يتيمًا يريندر للأبد (2026-11-22).
        import signal
        import subprocess
        from lib import mlt_stage
        with tempfile.TemporaryDirectory() as d:
            mlt_path = os.path.join(d, "proj.mlt")
            with open(mlt_path, "w") as f:
                f.write("<mlt/>")
            out = os.path.join(d, "out.mp4")
            killed = []

            class SlowPopen:
                pid = 4242
                returncode = None

                def communicate(self, timeout=None):
                    raise subprocess.TimeoutExpired("melt", timeout)

                def wait(self, timeout=None):
                    return -9

            def fake_popen(cmd, **kw):
                assert kw.get("start_new_session") is True
                return SlowPopen()

            with mock.patch.object(mlt_stage.subprocess, "Popen",
                                   side_effect=fake_popen), \
                    mock.patch.object(mlt_stage, "find_melt",
                                     return_value="/usr/bin/melt"), \
                    mock.patch.object(os, "killpg",
                                     side_effect=lambda pgid, sig: killed.append((pgid, sig))):
                with self.assertRaises(mlt_stage.MltError) as ctx:
                    mlt_stage.render_mlt(mlt_path, out, timeout=5)
            self.assertIn("انتهت مهلة ريندر melt", str(ctx.exception))
            self.assertEqual(killed, [(4242, signal.SIGKILL)])

    def test_prepare_fill_images_crops_to_frame(self):
        from lib import mlt_stage
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            src_dir = os.path.join(d, "assets", "images")
            os.makedirs(src_dir)
            # عريضة 1280×960 وعمودية 1280×1927 — كلتاهما يجب أن
            # تخرجا 720×1280 بلا أشرطة
            Image.new("RGB", (1280, 960), (200, 30, 30)).save(
                os.path.join(src_dir, "a.jpg"), quality=90)
            Image.new("RGB", (1280, 1927), (30, 30, 200)).save(
                os.path.join(src_dir, "b.jpg"), quality=90)
            out = mlt_stage.prepare_fill_images(
                self._manifest(), os.path.join(d, "assets"),
                os.path.join(d, "filled"), 720, 1280)
            self.assertEqual(sorted(out), ["a.jpg", "b.jpg"])
            for p in out.values():
                with Image.open(p) as im:
                    self.assertEqual(im.size, (720, 1280))

    def test_prepare_fill_images_missing_source_raises(self):
        from lib import mlt_stage
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(mlt_stage.MltError):
                mlt_stage.prepare_fill_images(
                    self._manifest(), os.path.join(d, "assets"),
                    os.path.join(d, "filled"), 720, 1280)

    def test_build_mlt_uses_images_dir(self):
        from lib import mlt_stage
        import xml.etree.ElementTree as ET
        xml_text = mlt_stage.build_mlt(
            self._manifest(), "هوك صادم", "/tmp/assets",
            {"width": 720, "height": 1280, "fps": 30,
             "image_clip_seconds": 5},
            images_dir="/tmp/filled")
        root = ET.fromstring(xml_text)
        producers = [p for p in root.findall("producer")
                     if p.get("id", "").startswith("img")]
        self.assertEqual(len(producers), 2)
        for p in producers:
            res = p.find("property[@name='resource']").text
            self.assertTrue(res.startswith("/tmp/filled/"), res)

    def test_build_mlt_landscape_aspect(self):
        # عيب 2026-11-21: نسبة العرض كانت 9/16 مثبتة في الـprofile
        # فتفسد الأفقي 1280×720 (يحتاج 16/9) — الفيديو الطويل الأسبوعي.
        from lib import mlt_stage
        import xml.etree.ElementTree as ET
        for w, h, num, den in ((1280, 720, "16", "9"),
                               (720, 1280, "9", "16")):
            xml_text = mlt_stage.build_mlt(
                self._manifest(), "هوك صادم", "/tmp/assets",
                {"width": w, "height": h, "fps": 30,
                 "image_clip_seconds": 5})
            profile = ET.fromstring(xml_text).find("profile")
            self.assertEqual(profile.get("width"), str(w))
            self.assertEqual(profile.get("height"), str(h))
            self.assertEqual(profile.get("display_aspect_num"), num)
            self.assertEqual(profile.get("display_aspect_den"), den)
            # صندوق الهوك أسفل الشاشة فوق صندوق العبارات
            # (قاعدة دائمة 2026-11-22: لا نص أعلى أبدًا):
            # (v0.1.62) متمركز بالهندسة المقاسة — عرضه 264
            # ("هوك صادم" بخط 58) وx=(w-264)//2 — وy=height-420
            # وارتفاع 150.
            hook = ET.fromstring(xml_text).find(
                "tractor/filter[@id='filter-hook']")
            geometry = hook.find(
                "property[@name='geometry']").text.split()
            self.assertEqual(geometry, [str((w - 264) // 2),
                                        str(h - 420), "264", "150"])


class TestEnsureEnvironment(unittest.TestCase):
    """الإصلاح الذاتي عند بدء التشغيل (v0.1.15): بلا شبكة وبلا تنفيذ
    فعلي لسكربت الاستعادة — subprocess.run يُستبدل بمحاكاة."""

    def _run(self, which=None, isfile=None, run_side=None):
        env = {"PATH": "/usr/bin:/bin"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch("shutil.which",
                           side_effect=(lambda c: "/usr/bin/%s" % c)
                           if which is None else which), \
                mock.patch("os.path.isfile",
                           side_effect=isfile), \
                mock.patch.object(studio, "_script_safe_to_run",
                                  return_value=True), \
                mock.patch.object(studio.subprocess, "run",
                                  side_effect=run_side) as run, \
                mock.patch.object(studio, "_omniroute_server_up",
                                  return_value=True):
            studio._ensure_environment()
            return run

    def test_all_present_no_restore(self):
        run = self._run(isfile=lambda p: True)
        run.assert_not_called()

    def test_missing_unit_file_triggers_restore_once(self):
        # تحديث 2026-11-26 (إصلاح بطء بدء التشغيل: version استغرق
        # 323ث): غياب ملف الخدمة وحده لم يعد يطلق الاسترداد المتزامن
        # بمهلة 300ث — صار يطلقه في الخلفية (Popen) مرة واحدة بلا
        # حظر، لأن خطوة 0 من setup-env.sh تعيد الملف من نسخة
        # الـhome في ثوانٍ. التأكيد الجديد أشد: يثبت الخلفية
        # وغياب المتزامن معًا.
        with mock.patch.object(studio.subprocess, "Popen") as popen:
            run = self._run(
                isfile=lambda p: p != studio._UNIT_FILE)
        run.assert_not_called()  # لا استرداد متزامن إطلاقًا
        popen.assert_called_once()
        args, kwargs = popen.call_args
        self.assertEqual(args[0][0], "/bin/bash")
        self.assertIn("setup-env.sh", args[0][-1])
        self.assertEqual(kwargs["env"].get("STUDIO_ENV_RESTORED"), "1")
        self.assertTrue(kwargs.get("start_new_session"))
        self.assertEqual(kwargs.get("stdout"), studio.subprocess.DEVNULL)

    def test_missing_tool_and_no_script_warns_only(self):
        run = self._run(which=lambda c: None,
                        isfile=lambda p: False)
        run.assert_not_called()  # لا سكربت فلا تنفيذ، وبلا استثناء

    def test_restore_failure_does_not_raise(self):
        run = self._run(which=lambda c: None,
                        isfile=lambda p: p == studio._SETUP_ENV_SCRIPT,
                        run_side=OSError("boom"))
        run.assert_called_once()  # حاول ثم أكمل بلا استثناء

    def test_unsafe_script_is_skipped(self):
        # إصلاح اختبار اختراق 2026-11-21: سكربت قابل للكتابة من
        # الجميع لا يُنفَّذ تلقائيًا أبدًا.
        with tempfile.NamedTemporaryFile("w", suffix=".sh",
                                        delete=False) as f:
            f.write("#!/bin/bash\necho hi\n")
            path = f.name
        try:
            os.chmod(path, 0o666)
            self.assertFalse(studio._script_safe_to_run(path))
            os.chmod(path, 0o700)
            self.assertTrue(studio._script_safe_to_run(path))
            self.assertFalse(studio._script_safe_to_run(path + ".missing"))
        finally:
            os.unlink(path)


class TestEnsureOmnirouteServer(unittest.TestCase):
    """خادم OmniRoute يجب أن يعمل قبل أي استدعاء ذكاء (عيب v0.1.16):
    أمر `chat` عميل HTTP للخادم، وبدونه يفشل بصمت (exit 1 بلا رسالة).
    بلا شبكة وبلا تنفيذ فعلي — كل شيء محاكاة."""

    def _run(self, health, which=None, run_side=None):
        with mock.patch.object(studio, "_omniroute_server_up",
                               side_effect=health), \
                mock.patch("shutil.which",
                           side_effect=(lambda c: "/usr/bin/%s" % c)
                           if which is None else which), \
                mock.patch.object(studio.subprocess, "run",
                                  side_effect=run_side) as run, \
                mock.patch("time.sleep"):
            studio._ensure_omniroute_server()
            return run

    def test_server_up_no_start(self):
        run = self._run([True])
        run.assert_not_called()

    def test_server_down_starts_on_loopback(self):
        run = self._run([False, True])
        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertEqual(args[0][:4],
                         ["omniroute", "serve", "--no-open", "--daemon"])
        self.assertEqual(args[0][4:], ["--port", "20128"])
        self.assertEqual(kwargs["env"].get("OMNIROUTE_SERVER_HOST"),
                         "127.0.0.1")

    def test_no_omniroute_binary_no_start(self):
        run = self._run([False], which=lambda c: None)
        run.assert_not_called()

    def test_server_never_comes_up_warns_only(self):
        run = self._run([False] * 31)
        run.assert_called_once()  # حاول مرة واحدة ثم أكمل بلا استثناء

    def test_start_failure_warns_only(self):
        run = self._run([False], run_side=OSError("boom"))
        run.assert_called_once()  # حاول ثم أكمل بلا استثناء


class TestConcatResultError(unittest.TestCase):
    """أخطاء أدوات MCP (is_error) يجب أن تُرفع فورًا برسالة واضحة
    بدل ابتلاعها وإكمال التجميع بقيم null (عيب v0.1.16).

    أُعيدت كتابته في v0.1.49 على كائنات CallToolResult حقيقية من
    mcp.types بدل قواميس JSON-RPC الخام (حُذفت مع العميل اليدوي)؛
    وفرع {"_text": ...} أُلغي — نص غير-JSON بلا structured_content
    يرجع {}."""

    def _mcp(self):
        # __init__ الجديد يخزّن المعاملات فقط (بلا عملية فرعية)،
        # فيُبنى مباشرة بلا دخول سياق.
        return concat_mcp.MCP(
            "/bin/false",
            os.path.join(tempfile.gettempdir(), "concat-mcp-test.jsonl"))

    def _text_result(self, text, is_error=False):
        return CallToolResult(
            content=[TextContent(type="text", text=text)],
            is_error=is_error)

    def test_is_error_raises_with_message(self):
        m = self._mcp()
        res = self._text_result(
            "/tmp/x.mp4 is outside where this API writes (/home/hatch) "
            "(code: refused)", is_error=True)
        with self.assertRaises(concat_mcp.ConcatError) as cm:
            m.result(res, "export_start")
        self.assertIn("export_start فشل:", str(cm.exception))
        self.assertIn("outside where this API writes", str(cm.exception))

    def test_ok_result_still_parses(self):
        m = self._mcp()
        res = self._text_result('{"job": "j1"}')
        self.assertEqual(m.result(res, "export_start"), {"job": "j1"})

    def test_structured_content_returned_directly(self):
        m = self._mcp()
        res = CallToolResult(
            content=[TextContent(type="text", text='{"job": "j1"}')],
            structured_content={"job": "j1", "state": "done"})
        self.assertEqual(m.result(res, "export_wait"),
                         {"job": "j1", "state": "done"})

    def test_non_json_text_without_structured_content_returns_empty(self):
        m = self._mcp()
        res = self._text_result("ok - not json at all")
        self.assertEqual(m.result(res, "project_save"), {})


class TestParseSize(unittest.TestCase):
    """خيار --size (v0.1.18): مقاس الفيديو WxH للفيديو الأفقي."""

    def test_valid_sizes(self):
        import studio
        self.assertEqual(studio.parse_size("1280x720"), (1280, 720))
        self.assertEqual(studio.parse_size("720x1280"), (720, 1280))
        self.assertEqual(studio.parse_size(" 1920X1080 "), (1920, 1080))

    def test_invalid_sizes_raise(self):
        import studio
        for bad in ("abc", "1280", "1280x", "x720", "0x720", "1280x0",
                    "-5x720", "1280x720x1", "", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                studio.parse_size(bad)


class TestCmdStatusProviders(unittest.TestCase):
    def test_hides_loaded_env_lines(self):
        # سطور "📋 Loaded env" كانت تتسرب إلى سطر المزودين لأن المرشح
        # كان يفحص البادئة "Loaded" فقط بينما السطر يبدأ بالإيموجي.
        cfg = {"omniroute": {"base_url": "http://localhost:20128"},
               "openmontage": {"root": "/tmp"},
               "concat": {"bin": "/tmp/x"},
               "headless": {"editor": "/tmp/x"}}
        resp = mock.MagicMock()
        resp.status = 200
        resp.__enter__ = mock.MagicMock(return_value=resp)
        resp.__exit__ = mock.MagicMock(return_value=False)
        raw = ("\x1b[2m📋 Loaded env from /home/x/.env\x1b[0m\n"
               "182fb2de   duckduckgo-web duckduckgo-web  active\n")
        import io
        buf = io.StringIO()
        with mock.patch("studio.urllib.request.urlopen",
                        return_value=resp), \
             mock.patch("studio.subprocess.run",
                        return_value=mock.MagicMock(stdout=raw)), \
             mock.patch("sys.stdout", buf):
            self.assertEqual(studio.cmd_status(cfg), 0)
        out = buf.getvalue()
        self.assertIn("duckduckgo-web", out)
        self.assertNotIn("Loaded env", out)
        self.assertNotIn(".env", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
