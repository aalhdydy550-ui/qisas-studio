#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات توصيل جولة v0.1.39 في studio.py.

أوامر jobs/reframe/shorts-cut الجديدة + أوامر queue publish-*
+ ‏batch --from-json/--no-spend + ‏scene-plan --template
+ ‏publish --generate-meta (LLM محاكى — بلا شبكة) + ‏ab --engine
+ ‏llm-status سطر Ollama + مداخل help_ar + ‏VERSION 0.1.39.
كل الكتابة في مجلدات مؤقتة — بلا شبكة وبلا لمس الطابور
الحقيقي أو أي منشور.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import check as check_lib
from lib import job_registry as job_registry_lib

HAS_FFMPEG = shutil.which("ffmpeg") is not None

QUEUE_TEXT = """# طابور قصص

## في الانتظار

4. **العنزة المباركة** — تحتاج جزأين
5. **عجائب الصدقة** — منشور واحد
"""

FAKE_META_TEXT = (
    "العنزة المباركة | الجزء 1 من 2\n"
    "قصة حقيقية عن عنزة مباركة جلبت الخير لصاحبها الفقير، "
    "وعبرتها أن البركة في القليل الحلال.\n"
    "#قصص_وعبر #قصص_حقيقية\n"
)

FAKE_HOOKS_TEXT = (
    "عنزة فقير غيّرت حياة صاحبها في ليلة واحدة\n"
    "سر العنزة التي بكى عليها أهل القرية كلها\n"
    "رجل فقير وجد في عنزته سرًا لم يتوقعه أحد\n"
)


def _cfg(td, balance=680):
    videos = os.path.join(td, "videos")
    runs = os.path.join(td, "runs")
    projects = os.path.join(td, "projects")
    os.makedirs(os.path.join(projects, "anza-part1"), exist_ok=True)
    queue = os.path.join(td, "queue.md")
    with open(queue, "w", encoding="utf-8") as f:
        f.write(QUEUE_TEXT)
    return {
        "paths": {"queue_file": queue, "videos_dir": videos,
                  "runs_dir": runs},
        "publish": {"page_id": "1048148471706586"},
        "veo": {"balance_units": balance, "renews": "2026-12-13"},
        "openmontage": {"projects_dir": projects},
        "omniroute": {},
        "video": {"width": 720, "height": 1280},
    }


def _capture(fn, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*args, **kwargs)
    return rc, buf.getvalue()


def _make_video(path, size="720x1280", seconds=2, gap=None):
    """فيديو اختبار (لون + نغمة). gap=(بدء، نهاية) بالثواني:
    فاصل صمت في الصوت — يقسّم الكلام إلى مقطعين فيختلف
    اختيار نوافذ shorts-cut عن الصوت المتصل (نافذة واحدة)."""
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
           "color=c=0x336699:s=%s:d=%s" % (size, seconds),
           "-f", "lavfi", "-i", "sine=frequency=440:d=%s" % seconds]
    if gap is not None:
        cmd += ["-af", "volume=0:enable='between(t,%s,%s)'"
                % (gap[0], gap[1])]
    cmd += ["-shortest", path]
    subprocess.run(cmd, check=True, timeout=180)


class TestVersion0143(unittest.TestCase):
    def test_version_is_0143(self):
        self.assertEqual(studio.VERSION, "0.1.63")


class TestJobsWiring(unittest.TestCase):
    def test_list_show_and_missing(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            runs = cfg["paths"]["runs_dir"]
            job = job_registry_lib.register_job(
                runs, kind="batch", story="4", title="العنزة المباركة")
            job_registry_lib.update_job(runs, job["job_id"],
                                        status="done")
            rc, out = _capture(studio.cmd_jobs_list, cfg)
            self.assertEqual(rc, 0)
            self.assertIn(job["job_id"], out)
            rc, out = _capture(studio.cmd_jobs_list, cfg, status="done")
            self.assertEqual(rc, 0)
            self.assertIn(job["job_id"], out)
            rc, out = _capture(studio.cmd_jobs_list, cfg, status="failed")
            self.assertEqual(rc, 0)
            self.assertNotIn(job["job_id"], out)
            rc, out = _capture(studio.cmd_jobs_show, cfg, job["job_id"])
            self.assertEqual(rc, 0)
            self.assertIn("العنزة المباركة", out)
            rc, _out = _capture(studio.cmd_jobs_show, cfg, "job-nope")
            self.assertEqual(rc, 1)


class TestQueuePublishWiring(unittest.TestCase):
    def test_status_summary_pending(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            q = cfg["paths"]["queue_file"]
            rc, out = _capture(studio.cmd_queue_publish_summary, cfg)
            self.assertEqual(rc, 0)
            self.assertIn("youtube", out)
            rc, out = _capture(studio.cmd_queue_pending, cfg, "youtube")
            self.assertEqual(rc, 0)
            self.assertIn("العنزة المباركة", out)
            rc, out = _capture(studio.cmd_queue_publish_status,
                               cfg, 4, "youtube", "published")
            self.assertEqual(rc, 0)
            sidecar = q + ".publish.json"
            self.assertTrue(os.path.isfile(sidecar))
            with open(sidecar, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["4"]["youtube"], "published")
            rc, out = _capture(studio.cmd_queue_pending, cfg, "youtube")
            self.assertEqual(rc, 0)
            self.assertNotIn("العنزة المباركة", out)
            self.assertIn("عجائب الصدقة", out)
            rc, out = _capture(studio.cmd_queue_publish_summary, cfg)
            self.assertIn("منشور 1", out)

    def test_invalid_platform_and_number(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            rc, _out = _capture(studio.cmd_queue_publish_status,
                                cfg, 4, "myspace", "published")
            self.assertEqual(rc, 2)
            rc, _out = _capture(studio.cmd_queue_publish_status,
                                cfg, 99, "youtube", "published")
            self.assertEqual(rc, 1)
            rc, _out = _capture(studio.cmd_queue_pending, cfg, "myspace")
            self.assertEqual(rc, 2)
            rc, _out = _capture(studio.cmd_queue_publish_status,
                                cfg, 4, "youtube", "maybe")
            self.assertEqual(rc, 2)


class TestBatchJsonNoSpendWiring(unittest.TestCase):
    def _json_batch(self, td):
        path = os.path.join(td, "batch.json")
        data = {"name": "دفعة اختبار", "source": "openmontage",
                "tasks": [{"number": 4, "title": "العنزة المباركة",
                           "parts": 1, "engine": "fast", "clips": 6}]}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return path

    def test_no_spend_ok_and_rejected_with_execute(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            path = self._json_batch(td)
            rc, out = _capture(studio.cmd_batch, cfg, from_json=path,
                               no_spend=True)
            self.assertEqual(rc, 0)
            self.assertIn("العنزة المباركة", out)
            rc, _out = _capture(studio.cmd_batch, cfg, from_json=path,
                                no_spend=True, execute=True)
            self.assertEqual(rc, 2)

    def test_no_spend_bad_json(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            path = os.path.join(td, "bad.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"tasks": [{"parts": 1}]}, f)
            rc, _out = _capture(studio.cmd_batch, cfg, from_json=path,
                                no_spend=True)
            self.assertEqual(rc, 1)


class TestScenePlanTemplateWiring(unittest.TestCase):
    def test_template_builds_plan(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            rc, out = _capture(
                studio.cmd_scene_plan, cfg, story="4", clips=3,
                template="relatives_injustice",
                template_hero="رجل فقير",
                template_situation="ظلمته حماته",
                template_moral="الصبر مفتاح الفرج")
            self.assertEqual(rc, 0)
            self.assertIn("حُفظت الخطة في:", out)
            plans = [f for f in os.listdir(cfg["paths"]["runs_dir"])
                     if f.startswith("scene-plan-")]
            self.assertEqual(len(plans), 1)

    def test_unknown_template_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            rc, out = _capture(studio.cmd_scene_plan, cfg, story="4",
                               clips=3, template="nope")
            self.assertEqual(rc, 2)
            self.assertIn("قالب غير معروف", out)


class TestPublishGenerateMetaWiring(unittest.TestCase):
    def test_generate_meta_dry_run_with_mock_llm(self):
        if not HAS_FFMPEG:
            self.skipTest("ffmpeg غير موجود")
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            video = os.path.join(td, "clip.mp4")
            _make_video(video)
            orig = studio._llm_chat
            studio._llm_chat = lambda *a, **k: (FAKE_META_TEXT,
                                                "mock", "mock-model")
            try:
                # (انحدار CI #255): مسار dry-run يبني أمر فيسبوك
                # عبر find_facebook_bin — بلا هذه المحاكاة يرجع
                # cmd_publish ‏1 في CI حيث facebook-cli غير مثبّت،
                # بينما يمر محليًا بفضل /opt/hatch/bin/facebook-cli.
                with mock.patch("lib.publish.find_facebook_bin",
                                return_value="facebook-cli"):
                    rc, out = _capture(
                        studio.cmd_publish, cfg, video, "العنزة المباركة",
                        None, platforms=("facebook", "youtube"),
                        dry_run=True, skip_check=True, generate_meta=True,
                        part=1, parts=2)
            finally:
                studio._llm_chat = orig
            self.assertEqual(rc, 0)
            self.assertIn("العنزة المباركة | الجزء 1 من 2", out)
            self.assertIn("بيانات النشر المولّدة", out)

    def test_generate_meta_explicit_caption_wins(self):
        if not HAS_FFMPEG:
            self.skipTest("ffmpeg غير موجود")
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            video = os.path.join(td, "clip.mp4")
            _make_video(video)
            orig = studio._llm_chat
            studio._llm_chat = lambda *a, **k: (FAKE_META_TEXT,
                                                "mock", "mock-model")
            try:
                # (انحدار CI #255 — كما في الاختبار السابق):
                # بلا محاكاة find_facebook_bin يرجع cmd_publish ‏1
                # في CI حيث facebook-cli غير مثبّت.
                with mock.patch("lib.publish.find_facebook_bin",
                                return_value="facebook-cli"):
                    rc, out = _capture(
                        studio.cmd_publish, cfg, video, "العنزة المباركة",
                        "كابشن صريح من المستخدم",
                        platforms=("facebook",),
                        dry_run=True, skip_check=True, generate_meta=True,
                        part=1, parts=2)
            finally:
                studio._llm_chat = orig
            self.assertEqual(rc, 0)
            self.assertIn("كابشن صريح من المستخدم", out)


class TestAbEngineWiring(unittest.TestCase):
    def test_binary_ab_lite_cost_lines(self):
        if not HAS_FFMPEG:
            self.skipTest("ffmpeg غير موجود")
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            video = os.path.join(td, "clip.mp4")
            _make_video(video, seconds=6)
            rc, out = _capture(
                studio.cmd_ab, cfg, video,
                "عنزة فقير غيّرت حياة صاحبها في ليلة واحدة",
                "سر العنزة التي بكى عليها أهل القرية كلها",
                "العنزة المباركة",
                cfg["paths"]["runs_dir"],
                cost_per_video=120, variants=2, engine="lite",
                balance_units=680, ledger_entries=[])
            self.assertEqual(rc, 0)
            self.assertIn("Lite", out)
            self.assertIn("وحدة Veo", out)

    def test_variants_ab_lite_cost_lines(self):
        if not HAS_FFMPEG:
            self.skipTest("ffmpeg غير موجود")
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            video = os.path.join(td, "clip.mp4")
            _make_video(video, seconds=6)
            orig = studio._llm_chat
            studio._llm_chat = lambda *a, **k: (FAKE_HOOKS_TEXT,
                                                "mock", "mock-model")
            try:
                rc, out = _capture(
                    studio.cmd_ab, cfg, video,
                    "عنزة فقير غيّرت حياة صاحبها في ليلة واحدة",
                    "سر العنزة التي بكى عليها أهل القرية كلها",
                    "العنزة المباركة",
                    cfg["paths"]["runs_dir"],
                    cost_per_video=120, variants=3, engine="lite",
                    balance_units=680, ledger_entries=[])
            finally:
                studio._llm_chat = orig
            self.assertEqual(rc, 0)
            self.assertIn("Lite", out)
            self.assertIn("الفائز", out)


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg غير موجود")
class TestReframeWiring(unittest.TestCase):
    def test_horizontal_to_vertical(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            src = os.path.join(td, "wide.mp4")
            out = os.path.join(td, "vert.mp4")
            _make_video(src, size="1280x720", seconds=2)
            rc, res = _capture(studio.cmd_reframe, cfg, src, out)
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isfile(out))
            info = check_lib.probe(out)
            self.assertEqual((info["width"], info["height"]),
                             (720, 1280))
            self.assertIn("720x1280", res)

    def test_vertical_passthrough(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            src = os.path.join(td, "vert.mp4")
            out = os.path.join(td, "vert2.mp4")
            _make_video(src, size="720x1280", seconds=2)
            rc, res = _capture(studio.cmd_reframe, cfg, src, out)
            self.assertEqual(rc, 0)
            self.assertIn("بلا إعادة ترميز", res)

    def test_missing_video(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            rc, _out = _capture(studio.cmd_reframe, cfg,
                                os.path.join(td, "nope.mp4"),
                                os.path.join(td, "o.mp4"))
            self.assertEqual(rc, 1)


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg غير موجود")
class TestShortsCutWiring(unittest.TestCase):
    def test_cut_two_shorts(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            long_video = os.path.join(td, "long.mp4")
            # صمت 45–50ث يقسّم الكلام إلى (0–45) و(50–95) —
            # نافذتان 40–60ث.
            _make_video(long_video, size="1280x720", seconds=95,
                        gap=(45, 50))
            out_dir = os.path.join(td, "shorts")
            rc, out = _capture(studio.cmd_shorts_cut, cfg, long_video,
                               out_dir=out_dir, count=2)
            self.assertEqual(rc, 0)
            shorts = sorted(f for f in os.listdir(out_dir)
                            if f.endswith(".mp4"))
            self.assertEqual(len(shorts), 2)
            for name in shorts:
                info = check_lib.probe(os.path.join(out_dir, name))
                self.assertEqual((info["width"], info["height"]),
                                 (720, 1280))
                self.assertTrue(40 <= info["duration"] <= 60)

    def test_cut_with_phrases_writes_ass(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            long_video = os.path.join(td, "long.mp4")
            _make_video(long_video, size="1280x720", seconds=95,
                        gap=(45, 50))
            ass = os.path.join(td, "long.ass")
            with open(ass, "w", encoding="utf-8") as f:
                f.write("[Script Info]\nTitle: test\n\n"
                        "[V4+ Styles]\n"
                        "Format: Name, Fontname, Fontsize, PrimaryColour, "
                        "SecondaryColour, OutlineColour, BackColour, Bold, "
                        "Italic, Underline, StrikeOut, ScaleX, ScaleY, "
                        "Spacing, Angle, BorderStyle, Outline, Shadow, "
                        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
                        "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,"
                        "&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,"
                        "10,10,10,1\n\n"
                        "[Events]\n"
                        "Format: Layer, Start, End, Style, Name, MarginL, "
                        "MarginR, MarginV, Effect, Text\n"
                        "Dialogue: 0,0:00:02.00,0:00:08.00,Default,,0,0,0,,"
                        "كان يا ما كان في قرية بعيدة\n"
                        "Dialogue: 0,0:00:45.00,0:00:52.00,Default,,0,0,0,,"
                        "وجاءت العنزة تحمل الخير\n"
                        "Dialogue: 0,0:01:20.00,0:01:28.00,Default,,0,0,0,,"
                        "وعاش الجميع في سلام\n")
            out_dir = os.path.join(td, "shorts")
            rc, _out = _capture(studio.cmd_shorts_cut, cfg, long_video,
                                out_dir=out_dir, count=2, phrases=ass)
            self.assertEqual(rc, 0)
            shorts = sorted(f for f in os.listdir(out_dir)
                            if f.endswith(".mp4"))
            self.assertEqual(len(shorts), 2)
            ass_files = sorted(f for f in os.listdir(out_dir)
                               if f.endswith(".ass"))
            self.assertEqual(len(ass_files), 2)
            with open(os.path.join(out_dir, ass_files[0]),
                      encoding="utf-8") as f:
                self.assertIn("Dialogue:", f.read())

    def test_missing_video(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            rc, _out = _capture(studio.cmd_shorts_cut, cfg,
                                os.path.join(td, "nope.mp4"),
                                out_dir=os.path.join(td, "s"))
            self.assertEqual(rc, 1)


class TestLlmStatusOllamaLine(unittest.TestCase):
    def test_llm_status_prints_ollama_line(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(td)
            rc, out = _capture(studio.cmd_llm_status, cfg)
            self.assertEqual(rc, 0)
            self.assertIn("Ollama", out)


class TestHelpArWiring(unittest.TestCase):
    def test_new_entries_present(self):
        from lib import help_ar
        names = [c[0] for c in help_ar.COMMANDS]
        for name in ("jobs", "reframe", "shorts-cut",
                     "queue publish-status", "queue publish-summary",
                     "queue pending"):
            self.assertIn(name, names)
        batch = dict((c[0], c[1]) for c in help_ar.COMMANDS)["batch"]
        self.assertIn("--no-spend", batch)
        self.assertIn("--from-json", batch)


class TestCliHelpWiring(unittest.TestCase):
    """مسارات argparse الجديدة تُعرض بلا أخطاء (subprocess)."""

    def test_subcommand_helps(self):
        studio_py = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "studio.py")
        for args in (["jobs", "--help"], ["reframe", "--help"],
                     ["shorts-cut", "--help"],
                     ["queue", "publish-status", "--help"],
                     ["queue", "publish-summary", "--help"],
                     ["queue", "pending", "--help"],
                     ["batch", "--help"], ["scene-plan", "--help"],
                     ["ab", "--help"], ["publish", "--help"]):
            proc = subprocess.run(
                [sys.executable, studio_py, *args],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(proc.returncode, 0, args)
            self.assertIn("usage:", proc.stdout.lower(), args)


if __name__ == "__main__":
    unittest.main()
