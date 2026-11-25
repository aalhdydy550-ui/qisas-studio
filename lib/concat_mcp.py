#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""تجميع Concat — طبقة التجميع النهائي في studio.

يقود خادم Concat بلا شاشة (`concat --mcp headless`) عبر عميل MCP
الرسمي (حزمة `mcp`) فوق stdio، بنفس تسلسل الاستدعاءات المثبت في
اختبار Concat (مشروع عمودي، استيراد وسائط، تسلسل صور، مسار صوتي،
عنوان هوك، كتابة متزامنة، حفظ، تصدير).

تحسين عن الاختبار الأول: الكتابة والعنوان بحدود سوداء (strokeWidth)
لتكون مقروءة فوق الصور الفاتحة.
"""
import json
import os
import shutil

# الاستيراد الكسول لـ mcp/anyio (انظر _ensure_mcp أدناه): استيرادهما
# أعلى الوحدة كان يكسر اختبارات البيئة العارية (test_ci_skips
# وtest_publish) — فعملياتها الفرعية تعمل بـHOME مؤقت بلا
# site-packages للمستخدم، و`import studio` يجب أن ينجح فيها بلا
# mcp. تُستوردان عند أول استخدام فعلي (assemble أو دخول MCP)،
# وتُرفع ConcatError واضحة إن غابتا. الأسماء الأربعة تبقى سمات
# على مستوى الوحدة لتحافظ اختبارات TestMcpClientConnect على نقطة
# الترقيع نفسها (mock.patch.object(concat_mcp, "Client", ...)).
anyio = None
Client = None
StdioServerParameters = None
MCPError = None


def _ensure_mcp():
    """استورد mcp/anyio عند أول حاجة إليهما (لا عند استيراد الوحدة).

    لا يكتب فوق اسم رقّعه اختبار (Client وهمي مثلًا) — يُستورد
    فقط ما ما زال None. يرفع ConcatError واضحة إن غابت الحزمة.
    """
    global anyio, Client, StdioServerParameters, MCPError
    if (anyio is None or Client is None
            or StdioServerParameters is None or MCPError is None):
        try:
            import anyio as _anyio
            from mcp import Client as _Client
            from mcp import StdioServerParameters as _Params
            from mcp.shared.exceptions import MCPError as _MCPError
        except ImportError as exc:
            raise ConcatError(
                "حزمة mcp غير مثبّتة — ثبّت المتطلبات: "
                "pip install -r requirements.txt (mcp[cli]==2.3.0)"
            ) from exc
        if anyio is None:
            anyio = _anyio
        if Client is None:
            Client = _Client
        if StdioServerParameters is None:
            StdioServerParameters = _Params
        if MCPError is None:
            MCPError = _MCPError


class ConcatError(Exception):
    pass


# الأدوات الـ12 التي يستدعيها assemble() فعليًا، بترتيب الاستدعاء.
EXPECTED_TOOLS = [
    "project_create", "timeline_read", "media_import",
    "clips_add_sequence", "track_add", "clip_add", "title_add",
    "clip_update", "captions_add", "project_save", "export_start",
    "export_wait",
]


class MCP:
    """عميل Concat عبر الـSDK الرسمي (`mcp`).

    مدير سياق غير متزامن: الدخول يطلق الخادم (`concat --mcp headless`)
    ويتفاوض على البروتوكول ويتحقق من الأدوات الـ12؛ والخروج يغلق
    العميل وملف السجل.
    """

    def __init__(self, concat_bin, log_path):
        self.concat_bin = concat_bin
        self.log_path = log_path
        self.client = None
        self.log = None
        self._client = None

    async def __aenter__(self):
        _ensure_mcp()
        params = StdioServerParameters(
            command=self.concat_bin, args=["--mcp", "headless"])
        self._client = Client(params, read_timeout_seconds=300)
        try:
            self.client = await self._client.__aenter__()
            if not self.client.protocol_version:
                raise ConcatError("لم يتفاوض Concat على إصدار بروتوكول")
            caps = self.client.server_capabilities
            if caps is None or not getattr(caps, "tools", None):
                raise ConcatError("خادم Concat لا يعلن قدرة الأدوات")
            tools = await self.client.list_tools()
            names = [t.name for t in tools.tools]
            missing = [t for t in EXPECTED_TOOLS if t not in names]
            if missing:
                raise ConcatError("أدوات ناقصة في Concat: %s"
                                  % ", ".join(missing))
            self.log = open(self.log_path, "a", encoding="utf-8")
        except Exception:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception:
                pass
            raise
        return self

    async def __aexit__(self, *exc):
        try:
            if self._client is not None:
                await self._client.__aexit__(*exc)
        finally:
            if self.log is not None:
                try:
                    self.log.close()
                except Exception:
                    pass
                self.log = None
        return False

    async def call(self, tool, args, timeout=300):
        _ensure_mcp()
        try:
            with anyio.fail_after(timeout):
                res = await self.client.call_tool(tool, args)
        except TimeoutError:
            raise ConcatError("لا رد من Concat خلال %s ثانية" % timeout)
        except MCPError as e:
            raise ConcatError("%s فشل: %s" % (tool, str(e)[:600]))
        except Exception as e:
            raise ConcatError("%s فشل: %s" % (tool, str(e)[:600]))
        self._log_call(tool, res)
        return res

    def _log_call(self, tool, res):
        """سطر JSON واحد {tool, res} في السجل؛ لا يرفع أبدًا."""
        try:
            data = res.model_dump(mode="json")
        except Exception:
            try:
                data = {
                    "content": [
                        {"type": getattr(c, "type", None),
                         "text": getattr(c, "text", "")}
                        for c in res.content
                    ],
                    "is_error": bool(getattr(res, "is_error", False)),
                }
                sc = getattr(res, "structured_content", None)
                if sc is not None:
                    data["structured_content"] = sc
            except Exception:
                return
        try:
            self.log.write(json.dumps({"tool": tool, "res": data},
                                      ensure_ascii=False, default=str) + "\n")
            self.log.flush()
        except Exception:
            pass

    def result(self, res, tool):
        if res.is_error:
            text = "".join(c.text for c in res.content
                           if getattr(c, "type", None) == "text")
            raise ConcatError("%s فشل: %s" % (tool, text[:600]))
        if res.structured_content is not None:
            return res.structured_content
        text = "".join(c.text for c in res.content
                       if getattr(c, "type", None) == "text")
        try:
            return json.loads(text) if text else {}
        except Exception:
            return {}


TITLE_STYLE = {
    "fontFamily": "Noto Kufi Arabic",
    "fontSize": 0.06,
    "fontWeight": 700,
    "color": "#FFFFFF",
    "align": "center",
    "strokeWidth": 0.01,
    "strokeColor": "#000000",
    "shadow": True,
}

CAPTION_STYLE = {
    "fontFamily": "Noto Kufi Arabic",
    "fontSize": 0.045,
    "fontWeight": 600,
    "color": "#FFFFFF",
    "align": "center",
    "strokeWidth": 0.008,
    "strokeColor": "#000000",
    "shadow": True,
    # إعداد عربي مُتحقق منه في CONCAT-FEATURES-TEST.md (مشروع feat-test،
    # 2026-11-21): لوحة خلفية شبه شفافة + حد أقصى لعرض السطر حتى لا يلتصق
    # النص بحواف الإطار العمودي.
    "background": "#000000B3",
    "maxWidth": 0.9,
}

# إزاحة العنوان العمودية في Concat (كسر من ارتفاع الإطار من
# المنتصف: سالب = أعلى، موجب = أسفل؛ الكابشنات عند +0.35).
# قاعدة دائمة 2026-11-22: كل نصوص الشاشة أسفل فقط، ولا نص أعلى
# أبدًا — فالعنوان يجلس أسفل الشاشة فوق الكابشنات مباشرة.
# (قبلها: -0.35 ثم -0.26 أعلى الشاشة — إصلاح 2026-11-21 كان
# يُبعده عن شارة الشعار فقط.) القيمة الأولية +0.17 تداخلت مع
# أول عبارة في ريندر حي للعنزة (عنوان 3 أسطر + عبارة أولى
# 4 أسطر) فصُححت إلى +0.12: مركز العنوان نحو y≈794 في 1280px،
# عنوان 3 أسطر (~300px) حافته السفلى ~944 وقمة العبارة ~980
# — فجوة ~36px بلا تداخل؛ و"above" أدناه طبقات لا موضع
# (الكلمة فوق الفيديو لا تحته) فيبقى True.
HOOK_OFFSET_Y = 0.12


# حركة عنوان الهوك — مُتحقق منها في مشروع feat-test (2026-11-21):
# دخول pop وخروج fade ونبض pulse طوال مدة العنوان (4 ثوانٍ)، وتظهر
# نظيفة في الإطار المصدَّر بلا ازدواج. أسماء الحركات من مخطط Concat
# (MotionMove: pop/fade…، وClipLoop: pulse…).
TITLE_MOTION = {
    "in": {"kind": "pop", "seconds": 0.5},
    "out": {"kind": "fade", "seconds": 0.5},
    "loop": {"kind": "pulse", "seconds": 1.0, "amount": 1.0},
}


def assemble(concat_bin, projects_root, project_name, assets_dir, manifest,
             title, out_path, video, log_path):
    """يبني مشروع Concat ويصدّره. يرجع مسار ملف الفيديو عند النجاح."""
    _ensure_mcp()
    return anyio.run(_assemble_async, concat_bin, projects_root,
                     project_name, assets_dir, manifest, title, out_path,
                     video, log_path)


async def _assemble_async(concat_bin, projects_root, project_name, assets_dir,
                          manifest, title, out_path, video, log_path):
    """التسلسل نفسه كما في assemble() المتزامنة سابقًا، عبر الـSDK."""
    from lib.paths import resolve_inside, safe_component
    images_dir = os.path.join(assets_dir, "images")
    images = []
    for n in manifest["sequence"]:
        # إصلاح اختبار اختراق 2026-11-21: اسم من البيان بلا تحقق
        # كان يشير إلى ملف خارج مجلد الأصول.
        safe_component(n, "اسم الصورة")
        images.append(resolve_inside(images_dir,
                                     os.path.join(images_dir, n),
                                     "صورة المشروع"))
    narration = os.path.join(assets_dir, "audio", "narration-full.wav")
    phrases = manifest["phrases"]
    proj_dir = os.path.join(projects_root, project_name)
    os.makedirs(projects_root, exist_ok=True)
    # إصلاح 2026-11-21: إعادة تجميع نفس التشغيل كانت تفشل لأن Concat
    # يرفض project_create على مجلد مشروع موجود. مجلد المشروع يُعاد
    # بناؤه كاملًا من البيان في كل تجميع، فإزالة النسخة القديمة آمنة
    # وتجعل assemble قابلًا لإعادة التشغيل (إعادة المحاولة بعد فشل،
    # وتغيير الخلفية/المقاس، وسلاسل البدائل في الكرونات).
    if os.path.isdir(proj_dir):
        print("مشروع Concat موجود سلفًا — يُستبدل: %s" % proj_dir)
        shutil.rmtree(proj_dir)

    async with MCP(concat_bin, log_path) as m:
        r = await m.call("project_create", {
            "location": projects_root, "name": project_name,
            "video": {"width": video["width"], "height": video["height"],
                      "rateNum": video["fps"], "rateDen": 1}})
        m.result(r, "project_create")

        r = await m.call("timeline_read", {"path": proj_dir})
        tl = m.result(r, "timeline_read")
        tracks = tl.get("tracks", [])

        ids = {}
        for path in images:
            # استيراد كل صورة مرة واحدة حتى لو تكررت في التسلسل
            name = os.path.basename(path)
            if name not in ids:
                r = await m.call("media_import", {"path": proj_dir, "file": path})
                ids[name] = m.result(r, "media_import").get("createdId")
        r = await m.call("media_import", {"path": proj_dir, "file": narration})
        aud_id = m.result(r, "media_import").get("createdId")

        seq_ids = [ids[os.path.basename(p)] for p in images]
        start = 0.0
        # تسلسل على دفعتين كالاختبار المثبت (أولًا حتى 35ث ثم الباقي)
        # — هنا دفعة واحدة تكفي لأن clips_add_sequence يقبل القائمة كاملة.
        r = await m.call("clips_add_sequence",
                         {"path": proj_dir, "mediaIds": seq_ids, "start": start})
        m.result(r, "clips_add_sequence")

        audio_track = None
        for t in tracks:
            if "audio" in str(t.get("kind", "")).lower():
                audio_track = t.get("id")
                break
        if audio_track is None:
            r = await m.call("track_add", {"path": proj_dir, "bottom": True})
            audio_track = m.result(r, "track_add").get("createdId")
        r = await m.call("clip_add", {"path": proj_dir, "mediaId": aud_id,
                                      "trackId": audio_track, "start": 0})
        m.result(r, "clip_add")

        style = dict(TITLE_STYLE)
        r = await m.call("title_add", {
            "path": proj_dir, "start": 0, "duration": 4,
            # قاعدة دائمة 2026-11-22: العنوان أسفل الشاشة فوق
            # الكابشنات (HOOK_OFFSET_Y) — لا نص أعلى أبدًا.
            # "above" طبقات لا موضع: الكلمة فوق الفيديو لا تحته.
            "above": True, "offsetY": HOOK_OFFSET_Y,
            "style": dict(style, content=title)})
        title_clip = m.result(r, "title_add").get("createdId")
        # حركة العنوان المُتحقق منها (TITLE_MOTION) — دخول وخروج ونبض.
        if title_clip:
            r = await m.call("clip_update", {
                "path": proj_dir, "clipId": title_clip,
                "patch": {"motion": TITLE_MOTION}})
            m.result(r, "clip_update")

        caps = [{"start": p["start"], "end": p["end"], "text": p["text"]}
                for p in phrases]
        r = await m.call("captions_add", {"path": proj_dir, "captions": caps,
                                          "offsetY": 0.35, "style": CAPTION_STYLE})
        m.result(r, "captions_add")

        r = await m.call("project_save", {"path": proj_dir})
        m.result(r, "project_save")

        r = await m.call("export_start", {
            "path": proj_dir, "output": out_path,
            "codec": video["codec"], "crf": video["crf"],
            "width": video["width"], "height": video["height"]})
        job = m.result(r, "export_start").get("job")
        state = {}
        for _ in range(10):
            r = await m.call("export_wait", {"job": job, "timeoutSeconds": 120},
                             timeout=180)
            state = m.result(r, "export_wait")
            if state.get("state") in ("done", "failed", "cancelled"):
                break
        if state.get("state") != "done":
            raise ConcatError("التصدير لم يكتمل: %s" % json.dumps(state)[:400])
        if not os.path.isfile(out_path):
            raise ConcatError("انتهى التصدير لكن ملف الخرج غير موجود: %s"
                              % out_path)
        return out_path
