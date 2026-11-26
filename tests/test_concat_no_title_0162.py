#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
"""اختبارات: خيار بلا عنوان في تجميع Concat (جولة v0.1.62).

العيب (إنتاج 2026-11-26 «أيقظ أولاده للصلاة»): عنوان القصة هو
الهوك نفسه، فـ`lib/concat_mcp.py::assemble()` يحرقه مرة بـtitle_add
(0–4ث، offsetY ‏+0.12) ثم `hook-title` يحرقه مرة ثانية فينتج
عنوانان متداخلان. حارس v0.1.59 في lib/hook_title.py يرفض الحرق
الثاني صاخبًا؛ والإصلاح الدائم هنا: `assemble(..., title=None)`
يتخطى title_add وحركة العنوان كليًا، وعلم CLI ‏`--no-title`
يمرّر الاختيار عبر `cmd_assemble`، والبيان الجانبي لا يدّعي
عنوانًا محروقًا حينها فيبقى hook-title ممكنًا.

تعمل بـ `python3 -m unittest tests.test_concat_no_title_0162 -v`
من مجلد studio. محاكاة MCP على نمط TestConcatArabicFeatures في
tests/test_studio.py (mock.patch.object(concat_mcp, "MCP", ...)).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import concat_mcp
from lib import hook_title

TITLE = "صحّى أولاده لصلاة الفجر"
VIDEO = {"width": 720, "height": 1280, "fps": 30,
         "codec": "h264", "crf": 23}
MANIFEST = {"sequence": ["img.jpg"],
            "phrases": [{"start": 0, "end": 1, "text": "في نص الليل"}]}

# الأدوات التي يستدعيها assemble() بلا عنوان، بترتيب الاستدعاء.
TOOLS_NO_TITLE = [
    "project_create", "timeline_read", "media_import", "media_import",
    "clips_add_sequence", "track_add", "clip_add", "captions_add",
    "project_save", "export_start", "export_wait",
]
# ومع عنوان: title_add + clip_update (الحركة) بعد clip_add.
TOOLS_WITH_TITLE = [
    "project_create", "timeline_read", "media_import", "media_import",
    "clips_add_sequence", "track_add", "clip_add", "title_add",
    "clip_update", "captions_add", "project_save", "export_start",
    "export_wait",
]


class FakeMCP:
    """محاكاة MCP على نمط tests/test_studio.py — تسجّل كل استدعاء."""

    def __init__(self, *a, **k):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def call(self, tool, args, timeout=300):
        self.calls.append((tool, args))
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


def _run_assemble(tmp, title, **kwargs):
    """شغّل concat_mcp.assemble بمحاكاة MCP؛ يرجع (الخرج، الاستدعاءات)."""
    fake = FakeMCP()
    assets = os.path.join(tmp, "assets")
    os.makedirs(os.path.join(assets, "images"))
    os.makedirs(os.path.join(assets, "audio"))
    out_path = os.path.join(tmp, "out.mp4")
    open(out_path, "w").close()
    with mock.patch.object(concat_mcp, "MCP", lambda *a, **k: fake):
        out = concat_mcp.assemble(
            "/bin/false", tmp, "p1", assets, MANIFEST,
            title, out_path, VIDEO, os.path.join(tmp, "log.jsonl"),
            **kwargs)
    return out, fake.calls


class TestAssembleNoTitle(unittest.TestCase):
    def test_title_given_burns_title_once_with_motion(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, calls = _run_assemble(tmp, TITLE)
            self.assertEqual(out, os.path.join(tmp, "out.mp4"))
            self.assertEqual([t for t, _ in calls], TOOLS_WITH_TITLE)
            by_tool = {}
            for tool, args in calls:
                by_tool.setdefault(tool, []).append(args)
            # title_add مرة واحدة بمحتوى العنوان نفسه.
            self.assertEqual(len(by_tool["title_add"]), 1)
            self.assertEqual(
                by_tool["title_add"][0]["style"]["content"], TITLE)
            self.assertEqual(by_tool["title_add"][0]["start"], 0)
            self.assertEqual(by_tool["title_add"][0]["duration"], 4)
            self.assertEqual(by_tool["title_add"][0]["offsetY"], 0.12)
            # حركة العنوان على مقطع العنوان نفسه.
            self.assertEqual(len(by_tool["clip_update"]), 1)
            self.assertEqual(by_tool["clip_update"][0]["clipId"], "c11")
            self.assertEqual(
                by_tool["clip_update"][0]["patch"]["motion"],
                concat_mcp.TITLE_MOTION)

    def test_title_none_skips_title_and_motion(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, calls = _run_assemble(tmp, None)
            self.assertEqual(out, os.path.join(tmp, "out.mp4"))
            # كل الأدوات الأخرى بالترتيب نفسه — بلا title_add
            # وبلا أي clip_update (حركة العنوان هي clip_update
            # الوحيد في assemble).
            self.assertEqual([t for t, _ in calls], TOOLS_NO_TITLE)
            tools = [t for t, _ in calls]
            self.assertNotIn("title_add", tools)
            self.assertNotIn("clip_update", tools)
            # الكابشنات ما زالت تُرسَل بإعداد العربي نفسه.
            caps = [a for t, a in calls if t == "captions_add"]
            self.assertEqual(len(caps), 1)
            self.assertEqual(caps[0]["style"], concat_mcp.CAPTION_STYLE)

    def test_title_omitted_defaults_to_no_title(self):
        # assemble() بلا وسيط title إطلاقًا = بلا عنوان.
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeMCP()
            assets = os.path.join(tmp, "assets")
            os.makedirs(os.path.join(assets, "images"))
            os.makedirs(os.path.join(assets, "audio"))
            out_path = os.path.join(tmp, "out.mp4")
            open(out_path, "w").close()
            with mock.patch.object(concat_mcp, "MCP",
                                   lambda *a, **k: fake):
                out = concat_mcp.assemble(
                    "/bin/false", tmp, "p1", assets, MANIFEST,
                    out_path=out_path, video=VIDEO,
                    log_path=os.path.join(tmp, "log.jsonl"))
            self.assertEqual(out, out_path)
            self.assertEqual([t for t, _ in fake.calls], TOOLS_NO_TITLE)


def _make_video(path, seconds=2):
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i",
                    "color=c=0x2a2a2a:s=720x1280:r=30:d=%s" % seconds,
                    "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=48000:duration=%s"
                    % seconds,
                    "-t", str(seconds), "-c:v", "libx264", "-preset",
                    "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", path],
                   check=True, timeout=300, capture_output=True,
                   text=True)


class TestCmdAssembleNoTitle(unittest.TestCase):
    def _setup_run(self, tmp):
        """تشغيل ببيان إنتاج وسيناريو عنوانه هو الهوك."""
        run_dir = os.path.join(tmp, "runs", "run1")
        os.makedirs(run_dir)
        produce = {"project": "test-story", "sequence": ["img.jpg"],
                   "hook": TITLE, "full_text": "نص القصة",
                   "phrases": [{"start": 0.0, "end": 1.0,
                                "text": "في نص الليل"}]}
        with open(os.path.join(run_dir, "manifest.json"), "w",
                  encoding="utf-8") as f:
            json.dump(produce, f, ensure_ascii=False)
        with open(os.path.join(run_dir, "script-ai.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"title": TITLE}, f, ensure_ascii=False)
        return run_dir

    def _cfg(self, tmp):
        return {"concat": {"bin": "/bin/false",
                           "projects_dir": os.path.join(tmp, "projects")},
                "video": dict(VIDEO),
                "narration": {"voice": "piper", "atempo": 1.0}}

    def _run_cmd_assemble(self, tmp, no_title):
        """cmd_assemble بتجميع Concat وهمي وإنهاء وهمي؛ يرجع
        (العنوان الممرَّر إلى assemble، مسار البيان الجانبي)."""
        run_dir = self._setup_run(tmp)
        out_path = os.path.join(tmp, "out.mp4")
        _make_video(out_path)
        seen = {}
        def fake_assemble(*args, **kwargs):
            seen["title"] = args[5]
            return out_path
        with mock.patch.object(studio.concat_mcp, "assemble",
                               fake_assemble), \
                mock.patch.object(studio, "_finish_video",
                                  return_value=out_path):
            out, _secs = studio.cmd_assemble(
                self._cfg(tmp), run_dir, TITLE, out_path,
                no_title=no_title)
        self.assertEqual(out, out_path)
        return seen["title"], out_path + ".manifest.json"

    def test_no_title_manifest_claims_no_burned_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            title_arg, man_path = self._run_cmd_assemble(tmp, True)
            self.assertIsNone(title_arg)
            with open(man_path, encoding="utf-8") as f:
                man = json.load(f)
            # البيان لا يدّعي عنوانًا محروقًا رغم أن السيناريو
            # يحمل العنوان — وإلا رفض الحارس hook-title لاحقًا.
            self.assertEqual(man.get("title"), "")
            # الحارس يرى None (fail-open): hook-title مسموح.
            out_path = os.path.join(tmp, "out.mp4")
            self.assertIsNone(
                hook_title.detect_burned_title(out_path, TITLE))

    def test_with_title_manifest_claims_burned_title(self):
        # الضابط: بلا --no-title يبقى البيان كما قبل — العنوان
        # محروق والحارس يرفض حرقه ثانية.
        with tempfile.TemporaryDirectory() as tmp:
            title_arg, man_path = self._run_cmd_assemble(tmp, False)
            self.assertEqual(title_arg, TITLE)
            with open(man_path, encoding="utf-8") as f:
                man = json.load(f)
            self.assertEqual(man.get("title"), TITLE)
            out_path = os.path.join(tmp, "out.mp4")
            self.assertEqual(
                hook_title.detect_burned_title(out_path, TITLE), TITLE)


class TestCliNoTitle(unittest.TestCase):
    def _run_main(self, tmp, extra_args):
        """شغّل main() بأمر assemble وهمي cmd_assemble؛ يرجع
        (رمز الخروج، استدعاءات cmd_assemble المسجلة)."""
        runs_dir = os.path.join(tmp, "runs")
        run_dir = os.path.join(runs_dir, "run1")
        os.makedirs(run_dir)
        with open(os.path.join(run_dir, "script-ai.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"title": TITLE}, f, ensure_ascii=False)
        cfg = {"paths": {"runs_dir": runs_dir},
               "video": dict(VIDEO),
               "concat": {"bin": "/bin/false",
                          "projects_dir": os.path.join(tmp, "projects")}}
        calls = []
        def fake_cmd_assemble(cfg_, run_dir_, title, out_path,
                              *args, **kwargs):
            calls.append({"title": title, "kwargs": kwargs})
            return (out_path, 1.0)
        argv = ["studio", "--noncommercial", "assemble", "--run", "run1",
                "--out", os.path.join(tmp, "out.mp4")] + extra_args
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(studio, "load_config",
                                  return_value=cfg), \
                mock.patch.object(studio, "_ensure_environment"), \
                mock.patch.object(studio.star_gate_lib,
                                  "check_star_gate", return_value=True), \
                mock.patch.object(studio, "cmd_assemble",
                                  fake_cmd_assemble):
            rc = studio.main()
        return rc, calls

    def test_assemble_no_title_reaches_cmd_assemble(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, calls = self._run_main(tmp, ["--no-title"])
            self.assertEqual(rc, 0)
            self.assertEqual(len(calls), 1)
            # العنوان يصل كما هو (للسجل) لكن العلم يمرَّر —
            # وcmd_assemble هو من يحوّله إلى None في Concat.
            self.assertEqual(calls[0]["title"], TITLE)
            self.assertTrue(calls[0]["kwargs"].get("no_title"))

    def test_assemble_without_flag_defaults_to_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, calls = self._run_main(tmp, [])
            self.assertEqual(rc, 0)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["title"], TITLE)
            self.assertFalse(calls[0]["kwargs"].get("no_title"))


if __name__ == "__main__":
    unittest.main()
