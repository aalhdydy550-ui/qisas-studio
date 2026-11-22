#!/usr/bin/env python3
"""تجميع Concat — طبقة التجميع النهائي في studio.

يقود خادم Concat بلا شاشة (`concat --mcp headless`) عبر MCP/stdin
بنفس تسلسل الاستدعاءات المثبت في اختبار Concat (مشروع عمودي، استيراد
وسائط، تسلسل صور، مسار صوتي، عنوان هوك، كتابة متزامنة، حفظ، تصدير).

تحسين عن الاختبار الأول: الكتابة والعنوان بحدود سوداء (strokeWidth)
لتكون مقروءة فوق الصور الفاتحة.
"""
import json
import os
import select
import shutil
import subprocess
import time


class ConcatError(Exception):
    pass


class MCP:
    def __init__(self, concat_bin, log_path):
        try:
            self.proc = subprocess.Popen(
                [concat_bin, "--mcp", "headless"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, bufsize=0)
        except FileNotFoundError:
            raise ConcatError("ثنائي Concat غير موجود: %s" % concat_bin)
        except OSError as e:
            raise ConcatError("تعذر تشغيل Concat (%s): %s"
                              % (concat_bin, e))
        self.rid = 0
        self.log = open(log_path, "a", encoding="utf-8")

    def send(self, obj):
        try:
            self.proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise ConcatError("انقطع الاتصال مع Concat أثناء الإرسال: %s"
                              % e)

    def read(self, timeout=300, expect_id=None):
        """يقرأ أول رسالة JSON-RPC مطابقة لـ expect_id.

        يتخطى الإشعارات (بلا id) وسطور السجل غير JSON حتى لا يلتقط
        الاستدعاء ردًا لا يخصه.
        """
        fd = self.proc.stdout.fileno()
        buf = b""
        start = time.time()
        while True:
            if time.time() - start > timeout:
                raise ConcatError("لا رد من Concat خلال %s ثانية" % timeout)
            r, _, _ = select.select([fd], [], [], 1.0)
            if not r:
                if self.proc.poll() is not None:
                    raise ConcatError("خرج Concat برمز %s" % self.proc.returncode)
                continue
            chunk = os.read(fd, 65536)
            if not chunk:
                raise ConcatError("أُغلق خرج Concat، رمز الخروج=%s"
                                  % self.proc.returncode)
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue  # سطر سجل غير JSON من الخادم — يُتخطى
                if not isinstance(msg, dict):
                    continue
                if expect_id is not None and msg.get("id") != expect_id:
                    continue  # إشعار أو رد لطلب آخر
                return msg

    def call(self, tool, args, timeout=300):
        self.rid += 1
        self.send({"jsonrpc": "2.0", "id": self.rid, "method": "tools/call",
                   "params": {"name": tool, "arguments": args}})
        res = self.read(timeout, expect_id=self.rid)
        self.log.write(json.dumps({"tool": tool, "res": res},
                                 ensure_ascii=False) + "\n")
        self.log.flush()
        return res

    def result(self, res, tool):
        if "error" in res:
            raise ConcatError("%s فشل: %s"
                              % (tool, json.dumps(res["error"])[:600]))
        result = res.get("result", {})
        # أخطاء الأدوات تأتي كـ result مع isError=true (نمط MCP) لا
        # كـ error على مستوى JSON-RPC؛ وإن لم تُرفع هنا تُبتلع ويكمل
        # التجميع بقيم null فينتهي بخطأ غامض لاحقًا (عيب 2026-11-21:
        # رفض export_start لمسار خارج /home/hatch ظهر كـ job=null
        # ثم «invalid type: null» في export_wait).
        if result.get("isError"):
            content = result.get("content", [])
            text = "".join(c.get("text", "") for c in content
                           if c.get("type") == "text")
            raise ConcatError("%s فشل: %s" % (tool, text[:600]))
        content = result.get("content", [])
        text = "".join(c.get("text", "") for c in content
                       if c.get("type") == "text")
        try:
            return json.loads(text) if text else {}
        except Exception:
            return {"_text": text}

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.terminate()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()
        self.log.close()


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

    m = MCP(concat_bin, log_path)
    try:
        m.send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "studio", "version": "0.1.3"}}})
        m.read(expect_id=1)
        m.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        r = m.call("project_create", {
            "location": projects_root, "name": project_name,
            "video": {"width": video["width"], "height": video["height"],
                      "rateNum": video["fps"], "rateDen": 1}})
        m.result(r, "project_create")

        r = m.call("timeline_read", {"path": proj_dir})
        tl = m.result(r, "timeline_read")
        tracks = tl.get("tracks", [])

        ids = {}
        for path in images:
            # استيراد كل صورة مرة واحدة حتى لو تكررت في التسلسل
            name = os.path.basename(path)
            if name not in ids:
                r = m.call("media_import", {"path": proj_dir, "file": path})
                ids[name] = m.result(r, "media_import").get("createdId")
        r = m.call("media_import", {"path": proj_dir, "file": narration})
        aud_id = m.result(r, "media_import").get("createdId")

        seq_ids = [ids[os.path.basename(p)] for p in images]
        start = 0.0
        # تسلسل على دفعتين كالاختبار المثبت (أولًا حتى 35ث ثم الباقي)
        # — هنا دفعة واحدة تكفي لأن clips_add_sequence يقبل القائمة كاملة.
        r = m.call("clips_add_sequence",
                   {"path": proj_dir, "mediaIds": seq_ids, "start": start})
        m.result(r, "clips_add_sequence")

        audio_track = None
        for t in tracks:
            if "audio" in str(t.get("kind", "")).lower():
                audio_track = t.get("id")
                break
        if audio_track is None:
            r = m.call("track_add", {"path": proj_dir, "bottom": True})
            audio_track = m.result(r, "track_add").get("createdId")
        r = m.call("clip_add", {"path": proj_dir, "mediaId": aud_id,
                                "trackId": audio_track, "start": 0})
        m.result(r, "clip_add")

        style = dict(TITLE_STYLE)
        r = m.call("title_add", {
            "path": proj_dir, "start": 0, "duration": 4,
            # قاعدة دائمة 2026-11-22: العنوان أسفل الشاشة فوق
            # الكابشنات (HOOK_OFFSET_Y) — لا نص أعلى أبدًا.
            # "above" طبقات لا موضع: الكلمة فوق الفيديو لا تحته.
            "above": True, "offsetY": HOOK_OFFSET_Y,
            "style": dict(style, content=title)})
        title_clip = m.result(r, "title_add").get("createdId")
        # حركة العنوان المُتحقق منها (TITLE_MOTION) — دخول وخروج ونبض.
        if title_clip:
            r = m.call("clip_update", {
                "path": proj_dir, "clipId": title_clip,
                "patch": {"motion": TITLE_MOTION}})
            m.result(r, "clip_update")

        caps = [{"start": p["start"], "end": p["end"], "text": p["text"]}
                for p in phrases]
        r = m.call("captions_add", {"path": proj_dir, "captions": caps,
                                    "offsetY": 0.35, "style": CAPTION_STYLE})
        m.result(r, "captions_add")

        r = m.call("project_save", {"path": proj_dir})
        m.result(r, "project_save")

        r = m.call("export_start", {
            "path": proj_dir, "output": out_path,
            "codec": video["codec"], "crf": video["crf"],
            "width": video["width"], "height": video["height"]})
        job = m.result(r, "export_start").get("job")
        state = {}
        for _ in range(10):
            r = m.call("export_wait", {"job": job, "timeoutSeconds": 120},
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
    finally:
        m.close()
