#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات أوامر المرحلة 2 (preview/logs/balance/queue import/
الصوت الافتراضي) — بلا نشر وبلا لمس للطابور الحقيقي."""
import argparse
import datetime
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import cost_ledger

EN_LICENSE_NOTE = ("الصوت الإنجليزي للاستخدام الشخصي/التجريبي فقط "
                   "(CC BY-NC-SA 4.0) — لا يُستخدم لفيديوهات عملاء مدفوعة")

SENTENCE = ("في يوم من الأيام خرج رجل فقير من بيته يبحث عن رزق حلال "
            "لأولاده الجياع.")


def _capture(fn, *args, **kwargs):
    buf = io.StringIO()
    with mock.patch("sys.stdout", buf):
        rc = fn(*args, **kwargs)
    return rc, buf.getvalue()


class TestBalanceLedgerCmd(unittest.TestCase):
    def test_record_and_history(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(studio, "STUDIO_DIR", td):
                rc, out = _capture(studio.cmd_balance, {},
                                   record=120, video="عائشة ج2",
                                   clips=6)
                self.assertEqual(rc, 0)
                self.assertIn("120 وحدة", out)
                rc, out = _capture(studio.cmd_balance, {}, record=100,
                                   video="العنزة ج1", clips=5)
                self.assertEqual(rc, 0)
                rc, out = _capture(studio.cmd_balance, {},
                                   history_flag=True)
                self.assertEqual(rc, 0)
                self.assertIn("220 وحدة", out)
                self.assertEqual(len(cost_ledger.history(td)), 2)

    def test_record_without_video_fails(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(studio, "STUDIO_DIR", td):
                rc, _out = _capture(studio.cmd_balance, {}, record=120)
            self.assertEqual(rc, 2)
            self.assertEqual(cost_ledger.history(td), [])

    def test_history_empty(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(studio, "STUDIO_DIR", td):
                rc, out = _capture(studio.cmd_balance, {},
                                   history_flag=True)
            self.assertEqual(rc, 0)
            self.assertIn("لا قيود", out)

    def test_forecast_still_works(self):
        cfg = {"veo": {"balance_units": 680, "renews": "2026-12-13",
                       "daily_cost_min": 100, "daily_cost_max": 140}}
        rc, out = _capture(studio.cmd_balance, cfg)
        self.assertEqual(rc, 0)
        self.assertIn("680", out)


class TestDefaultVoice(unittest.TestCase):
    def test_voice_from_config(self):
        self.assertEqual(studio._default_voice({}), "piper")
        self.assertEqual(
            studio._default_voice({"narration": {"voice": "gtts"}}),
            "gtts")
        self.assertEqual(
            studio._default_voice({"narration": {"voice": "bogus"}}),
            "piper")
        self.assertEqual(
            studio._default_voice({"narration": {}}), "piper")

    def test_long_narration_dispatch_uses_config_voice(self):
        """التوزيع يمرّر صوت الإعداد عند غياب --voice."""
        cfg = studio.load_config()
        expected = studio._default_voice(cfg)
        fake = {"output": "/tmp/x.wav", "duration": 1.0, "chunks": [1]}
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "n.wav")
            argv = ["studio.py", "long-narration", "--text", "نص",
                    "--out", out]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch("lib.long_narration.synthesize_long",
                            return_value=fake) as synth:
                rc = studio.main()
            self.assertEqual(rc, 0)
            self.assertEqual(synth.call_args.kwargs.get("voice")
                             or synth.call_args[1].get("voice"),
                             expected)


def _make_video(path, seconds=5):
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=black:s=720x1280:d=%d" % seconds,
                    "-f", "lavfi", "-i",
                    "sine=frequency=440:d=%d" % seconds,
                    "-shortest", "-c:v", "libx264", "-c:a", "aac",
                    "-y", path], check=True, timeout=120)


class TestPreviewCmd(unittest.TestCase):
    def test_preview_command_writes_page(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            _make_video(video)
            rc, out = _capture(studio.cmd_preview, {}, video,
                               caption="كابشن <b>تجريبي</b>",
                               first_comment="تعليق أول",
                               out_dir=td, title="قصة")
            self.assertEqual(rc, 0)
            page_path = os.path.join(td, "قصة-preview.html")
            self.assertTrue(os.path.isfile(page_path))
            with open(page_path, encoding="utf-8") as fh:
                page = fh.read()
            self.assertIn("&lt;b&gt;تجريبي&lt;/b&gt;", page)
            self.assertIn("تعليق أول", page)
            self.assertIn("صفحة المعاينة", out)

    def test_preview_missing_video_fails(self):
        rc, out = _capture(studio.cmd_preview, {}, "/tmp/nope.mp4")
        self.assertEqual(rc, 1)
        self.assertIn("تعذرت المعاينة", out)


class TestLogsCmd(unittest.TestCase):
    def _setup(self, td):
        # التواريخ نسبية لليوم الحقيقي: كان الاختبار مثبّتًا على
        # 2026-11-22 ففشل في أي يوم آخر (اليوم = anza، أمس = hamati).
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        runs = Path(td) / "runs"
        anza_day = today.strftime("%Y%m%d")
        (runs / ("anza-%s-070000" % anza_day)).mkdir(parents=True)
        (runs / ("anza-%s-070000" % anza_day) / "run-log.json").write_text(
            json.dumps({"run": "anza-%s-070000" % anza_day, "story": "anza",
                        "started": "%sT07:00:00" % today.isoformat(),
                        "steps": {"render": {"status": "ok"}}},
                       ensure_ascii=False), encoding="utf-8")
        hamati_day = yesterday.strftime("%Y%m%d")
        (runs / ("hamati-%s-190000" % hamati_day)).mkdir(parents=True)
        (runs / ("hamati-%s-190000" % hamati_day) / "run-log.json").write_text(
            json.dumps({"run": "hamati-%s-190000" % hamati_day,
                        "story": "hamati",
                        "started": "%sT19:00:00" % yesterday.isoformat(),
                        "steps": {"script": {"status": "failed",
                                             "error": "خطأ تجريبي"}}},
                       ensure_ascii=False), encoding="utf-8")
        return str(runs)

    def test_logs_today_only_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            runs = self._setup(td)
            cfg = {"paths": {"runs_dir": runs}}
            rc, out = _capture(studio.cmd_logs, cfg, today=True)
            self.assertEqual(rc, 0)
            self.assertIn("anza", out)
            self.assertNotIn("hamati", out)

    def test_logs_all_days(self):
        with tempfile.TemporaryDirectory() as td:
            runs = self._setup(td)
            cfg = {"paths": {"runs_dir": runs}}
            rc, out = _capture(studio.cmd_logs, cfg, today=False)
            self.assertEqual(rc, 0)
            self.assertIn("anza", out)
            self.assertIn("hamati", out)
            self.assertIn("فشل", out)


class TestQueueImportCmd(unittest.TestCase):
    def _setup(self, td):
        # ملف النص يجب أن يكون داخل ~/workspace (قيد الأمان).
        # المجلد الأب قد لا يوجد (CI: بلا ~/workspace) فيُنشأ أولًا.
        os.makedirs(os.path.expanduser("~/workspace"), exist_ok=True)
        ws_tmp = tempfile.mkdtemp(prefix=".test-qi-",
                                  dir=os.path.expanduser("~/workspace"))
        self.addCleanup(shutil.rmtree, ws_tmp, True)
        text_path = os.path.join(ws_tmp, "story.txt")
        Path(text_path).write_text(
            "\n".join(SENTENCE for _ in range(30)), encoding="utf-8")
        queue_path = os.path.join(td, "story-queue.md")
        return queue_path, text_path

    def test_import_command_adds_parts(self):
        with tempfile.TemporaryDirectory() as td:
            queue_path, text_path = self._setup(td)
            cfg = {"paths": {"queue_file": queue_path}}
            with mock.patch.object(studio, "STUDIO_DIR", td):
                rc, out = _capture(studio.cmd_queue_import, cfg,
                                   text_path, "قصة تجريبية",
                                   start="2026-11-23")
            self.assertEqual(rc, 0)
            self.assertIn("أجزاء", out)
            content = Path(queue_path).read_text(encoding="utf-8")
            self.assertIn("**قصة تجريبية — الجزء 1**", content)
            self.assertIn("2026-11-23 09:00", content)

    def test_import_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            queue_path, text_path = self._setup(td)
            cfg = {"paths": {"queue_file": queue_path}}
            with mock.patch.object(studio, "STUDIO_DIR", td):
                rc, _o = _capture(studio.cmd_queue_import, cfg,
                                  text_path, "قصة مكررة")
                self.assertEqual(rc, 0)
                rc, _o = _capture(studio.cmd_queue_import, cfg,
                                  text_path, "قصة مكررة")
            self.assertEqual(rc, 1)

    def test_import_bad_start_date(self):
        with tempfile.TemporaryDirectory() as td:
            queue_path, text_path = self._setup(td)
            cfg = {"paths": {"queue_file": queue_path}}
            rc, _o = _capture(studio.cmd_queue_import, cfg, text_path,
                              "عنوان", start="not-a-date")
            self.assertEqual(rc, 2)


def _run_main(argv):
    """شغّل studio.main() بالوسائط المعطاة؛ ارجع (رمز الخروج، المخرجات).

    البوابتان (التجاري/النجمة) محاكاتان بالسماح حتى لا يعتمد الاختبار
    على حالة الترخيص/النجمة في بيئة التشغيل. أخطاء argparse تذهب
    إلى stderr فيُلتقط مع stdout."""
    buf = io.StringIO()
    err = io.StringIO()
    with mock.patch.object(sys, "argv", argv), \
         mock.patch("sys.stdout", buf), \
         mock.patch("sys.stderr", err), \
         mock.patch.object(studio.license_lib, "record_first_run"), \
         mock.patch.object(studio.license_lib, "commercial_allowed",
                           return_value=(True, "")), \
         mock.patch.object(studio.star_gate_lib, "check_star_gate",
                           return_value=True):
        try:
            rc = studio.main()
        except SystemExit as e:
            return e.code, buf.getvalue() + err.getvalue()
    return rc, buf.getvalue() + err.getvalue()


def _quick_cfg(td):
    return {"paths": {"runs_dir": os.path.join(td, "runs"),
                      "videos_dir": os.path.join(td, "videos")},
            "video": {"width": 720, "height": 1280, "fps": 30},
            "omniroute": {"model": "m", "fallback_model": "f",
                          "base_url": "http://localhost:20128",
                          "retries": 1, "retry_delay_seconds": 5}}


def _fake_wav(td, name="narr.wav"):
    path = os.path.join(td, name)
    Path(path).write_bytes(b"")
    return path


def _fake_synth_info(td):
    return {"output": _fake_wav(td), "duration": 5.0,
            "chunks": [{"text": "Hello world.", "start": 0.0,
                        "end": 5.0}]}


class TestQuickArgParsing(unittest.TestCase):
    def test_quick_help_lists_flags_and_license_note(self):
        _rc, out = _run_main(["studio.py", "quick", "--help"])
        self.assertIn("--lang", out)
        self.assertIn("--dry-run", out)
        self.assertIn("--publish", out)
        self.assertIn("--allow-fallback", out)
        self.assertIn("--voice", out)
        # argparse يلفّ سطر المساعدة الطويل — فتُطابَق بعد تطبيع الفراغات.
        self.assertIn(EN_LICENSE_NOTE, " ".join(out.split()))
        # والقيد نفسه ثابت حرفي في الكود.
        self.assertEqual(studio.EN_VOICE_LICENSE_NOTE, EN_LICENSE_NOTE)

    def test_quick_parsing_passes_lang_voice_dry_run(self):
        with mock.patch.object(studio, "cmd_quick",
                               return_value=0) as quick:
            rc, _out = _run_main([
                "studio.py", "quick", "عنوان تجريبي", "--lang", "en",
                "--voice", "en_US-ryan-medium", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertEqual(quick.call_count, 1)
        kwargs = quick.call_args[1]
        self.assertEqual(kwargs.get("lang"), "en")
        self.assertEqual(kwargs.get("voice"), "en_US-ryan-medium")
        self.assertTrue(kwargs.get("dry_run"))
        self.assertEqual(quick.call_args[0][1], "عنوان تجريبي")

    def test_quick_global_lang_reaches_command(self):
        with mock.patch.object(studio, "cmd_quick",
                               return_value=0) as quick:
            rc, _out = _run_main(["studio.py", "--lang", "en", "quick",
                                  "عنوان"])
        self.assertEqual(rc, 0)
        self.assertEqual(quick.call_args[1].get("lang"), "en")

    def test_quick_dry_run_prints_plan_without_producing(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out = _capture(studio.cmd_quick, _quick_cfg(td),
                               "عنوان تجريبي", dry_run=True)
        self.assertEqual(rc, 0)
        self.assertIn("عنوان تجريبي", out)
        self.assertIn("kenburns", out)
        self.assertIn("بلا انتظار GPU", out)
        self.assertIn("لا — لاحق بأمر publish الصريح", out)
        self.assertNotIn("الهوك:", out)

    def test_quick_dry_run_en_prints_license_note(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out = _capture(studio.cmd_quick, _quick_cfg(td),
                               "A Test Title", lang="en", dry_run=True)
        self.assertEqual(rc, 0)
        self.assertIn("اللغة: en", out)
        self.assertIn(EN_LICENSE_NOTE, out)

    def test_quick_rejects_unknown_and_female_voices(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _quick_cfg(td)
            for bad in ("lessac", "en_US-lessac-medium", "bogus-voice"):
                rc, out = _capture(studio.cmd_quick, cfg, "عنوان",
                                   voice=bad, dry_run=True)
                self.assertEqual(rc, 2, bad)
                self.assertIn("غير معروف", out)
            rc, out = _capture(studio.cmd_quick, cfg, "عنوان",
                               voice="en_US-ryan-medium", dry_run=True)
            self.assertEqual(rc, 0)
            self.assertIn("en_US-ryan-medium", out)

    def test_quick_template_story_has_formula_structure(self):
        for lang, qmark in (("ar", "؟"), ("en", "?")):
            story = studio._quick_template_story("النجار الأمين", lang)
            self.assertTrue(story["hook"])
            self.assertTrue(story["body"])
            self.assertTrue(story["moral"])
            self.assertTrue(story["question"].rstrip().endswith(qmark))
            self.assertEqual(story["source"], "template:honesty_charity")

    def test_parse_quick_story_labeled_and_unlabeled(self):
        labeled = ("HOOK: A poor man found a wallet.\n"
                   "STORY: He was hungry but returned it.\n"
                   "MORAL: Honesty is never lost.\n"
                   "QUESTION: What would you do?")
        parsed = studio._parse_quick_story(labeled, "en")
        self.assertEqual(parsed["hook"], "A poor man found a wallet.")
        self.assertIn("returned it", parsed["body"])
        self.assertEqual(parsed["moral"], "Honesty is never lost.")
        self.assertEqual(parsed["question"], "What would you do?")
        unlabeled = ("First sentence hooks. Middle story here. "
                     "Last moral line. What would you do?")
        parsed = studio._parse_quick_story(unlabeled, "en")
        self.assertEqual(parsed["hook"], "First sentence hooks.")
        self.assertEqual(parsed["question"], "What would you do?")
        self.assertEqual(parsed["moral"], "Last moral line.")

    def test_quick_full_run_en_with_mocks_writes_video_and_latin_ass(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _quick_cfg(td)
            out_mp4 = os.path.join(td, "quick.mp4")
            proj_path = os.path.join(td, "proj.json")
            project = {"tracks": [
                {"type": "text", "words": [
                    {"w": "Hello", "start": 0.0, "end": 0.5},
                    {"w": "world.", "start": 0.5, "end": 1.0}]}]}
            Path(proj_path).write_text(json.dumps(project),
                                       encoding="utf-8")
            llm_text = ("HOOK: A poor carpenter found a wallet full "
                        "of money.\n"
                        "STORY: He was hungry and his children were "
                        "hungry too. He returned the wallet to its "
                        "owner anyway.\n"
                        "MORAL: Honesty is never lost.\n"
                        "QUESTION: What would you do if you found it?")
            fake_info = _fake_synth_info(td)

            def _fake_img(path, width, height, hue="gold", seed=7):
                from PIL import Image
                Image.new("RGB", (16, 16)).save(path, "JPEG")
                return path

            with mock.patch.object(studio, "_llm_chat",
                                   return_value=(llm_text, "omniroute",
                                                 "m")), \
                 mock.patch("lib.long_narration.synthesize_long",
                            return_value=fake_info) as synth, \
                 mock.patch.object(studio.demo, "make_scene_image",
                                   side_effect=_fake_img), \
                 mock.patch("lib.long_video.build_fast_draft",
                            return_value={
                                "output": out_mp4, "duration": 45.0,
                                "report": {"project_json": proj_path}}), \
                 mock.patch.object(studio, "_finish_video",
                                   return_value=out_mp4):
                rc, out = _capture(
                    studio.cmd_quick, cfg, "The Honest Carpenter",
                    lang="en", voice="en_US-ryan-medium",
                    out_path=out_mp4)
            self.assertEqual(rc, 0, out)
            self.assertIn("اكتمل quick", out)
            self.assertIn("كابشن لاتيني", out)
            # السرد استُدعي باللغة الإنجليزية وموديل ryan صراحةً.
            for call in synth.call_args_list:
                self.assertEqual(call.kwargs.get("lang"), "en")
                self.assertTrue(
                    str(call.kwargs.get("model") or "").endswith(
                        "en_US-ryan-medium.onnx"))
            ass_path = os.path.splitext(out_mp4)[0] + "-captions-en.ass"
            self.assertTrue(os.path.isfile(ass_path))
            ass = Path(ass_path).read_text(encoding="utf-8")
            self.assertIn("Direction: LTR", ass)
            self.assertIn("Noto Sans", ass)
            runs = os.path.join(td, "runs")
            stories = [os.path.join(runs, r, "quick-story.json")
                       for r in os.listdir(runs)]
            self.assertEqual(len(stories), 1)
            record = json.loads(Path(stories[0]).read_text(
                encoding="utf-8"))
            self.assertIn("wallet", record["hook"])
            self.assertEqual(record["moral"], "Honesty is never lost.")
            self.assertTrue(record["question"].endswith("?"))

    def test_quick_llm_failure_without_fallback_stops(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _quick_cfg(td)
            with mock.patch.object(
                    studio, "_llm_chat",
                    side_effect=studio.omniroute_client.OmniRouteError(
                        "كل المزودين فشلوا")):
                rc, out = _capture(studio.cmd_quick, cfg, "عنوان",
                                   out_path=os.path.join(td, "q.mp4"))
            self.assertEqual(rc, 1)
            self.assertIn("فشل توليد القصة", out)

    def test_quick_llm_failure_with_fallback_uses_template(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _quick_cfg(td)
            out_mp4 = os.path.join(td, "quick.mp4")
            fake_info = _fake_synth_info(td)

            def _fake_img(path, width, height, hue="gold", seed=7):
                from PIL import Image
                Image.new("RGB", (16, 16)).save(path, "JPEG")
                return path

            with mock.patch.object(
                    studio, "_llm_chat",
                    side_effect=studio.omniroute_client.OmniRouteError(
                        "كل المزودين فشلوا")), \
                 mock.patch("lib.long_narration.synthesize_long",
                            return_value=fake_info), \
                 mock.patch.object(studio.demo, "make_scene_image",
                                   side_effect=_fake_img), \
                 mock.patch("lib.long_video.build_fast_draft",
                            return_value={
                                "output": out_mp4, "duration": 45.0,
                                "report": {"project_json": os.path.join(
                                    td, "nope.json")}}), \
                 mock.patch.object(studio, "_finish_video",
                                   return_value=out_mp4):
                rc, out = _capture(
                    studio.cmd_quick, cfg, "النجار الأمين",
                    allow_fallback=True, out_path=out_mp4)
            self.assertEqual(rc, 0, out)
            self.assertIn("القصة المدمجة من القوالب", out)


class TestQuickChapterBudget(unittest.TestCase):
    """ميزانية مدة فصل quick (40ث — الفيديو الكامل 40–60ث)."""

    def test_quick_prompts_cap_body_at_250_chars(self):
        # العربي أبطأ سردًا (~6.5 حرف/ث) من الإنجليزي (~20 حرف/ث)،
        # فالسقف الإنجليزي أعلى ليصل الفيديو الكامل إلى 40–60ث.
        self.assertIn("250", studio._QUICK_PROMPT_AR)
        self.assertIn("450", studio._QUICK_PROMPT_EN)
        self.assertIn("600", studio._QUICK_PROMPT_EN)

    def test_fit_quick_chapter_within_budget_returns_unchanged(self):
        story = {"body": "جملة قصيرة واحدة.",
                 "moral": "الأمانة لا تضيع."}
        info = {"output": "c.wav", "duration": 30.0, "chunks": []}
        with mock.patch("lib.long_narration.synthesize_long") as synth:
            text, out = studio._fit_quick_chapter(
                story, story["body"] + " " + story["moral"], info,
                "/tmp", "piper", None, "ar")
        synth.assert_not_called()
        self.assertIs(out, info)
        self.assertEqual(text, story["body"] + " " + story["moral"])

    def test_fit_quick_chapter_trims_trailing_body_sentences(self):
        body = ("كان النجار يعمل ليل نهار في ورشته الصغيرة ليطعم "
                "أولاده الجياع ويسدد دينًا قديمًا عليه. وفي يوم وجد "
                "خشبًا ثمينًا مرميًا في مخزن الزبون يكفي لعمل دولاب "
                "فاخر يباع بثمن كبير. وقرر أن يرجع الخشب لصاحبه رغم "
                "حاجته الشديدة للمال ورغم أن أحدًا لم يكن ليعرف أبدًا.")
        story = {"body": body, "moral": "الأمانة لا تضيع أبدًا."}
        chapter = (body + " " + story["moral"]).strip()
        first = {"output": "c.wav", "duration": len(chapter) / 6.0,
                 "chunks": []}
        self.assertGreater(first["duration"], 40.0)

        def _fake_synth(text, out, **_kw):
            return {"output": out, "duration": len(text) / 6.0,
                    "chunks": []}

        with tempfile.TemporaryDirectory() as td, \
                mock.patch("lib.long_narration.synthesize_long",
                           side_effect=_fake_synth) as synth:
            text, out = studio._fit_quick_chapter(
                story, chapter, first, td, "piper", None, "ar")
        # حُذفت الجملة الأخيرة من الجسم فقط؛ والعبرة بلا مساس.
        self.assertNotIn("وقرر أن يرجع الخشب", text)
        self.assertIn("الأمانة لا تضيع أبدًا.", text)
        self.assertIn("كان النجار يعمل", text)
        self.assertLessEqual(out["duration"], 40.0)
        self.assertEqual(synth.call_count, 1)

    def test_fit_quick_chapter_single_sentence_warns(self):
        body = "جملة واحدة طويلة جدًا " * 30
        story = {"body": body.strip(), "moral": "الأمانة لا تضيع."}
        chapter = (body + " " + story["moral"]).strip()
        info = {"output": "c.wav", "duration": len(chapter) / 6.0,
                "chunks": []}
        self.assertGreater(info["duration"], 40.0)
        with tempfile.TemporaryDirectory() as td, \
                mock.patch("lib.long_narration.synthesize_long") as synth:
            _rc, out = _capture(studio._fit_quick_chapter,
                                story, chapter, info, td,
                                "piper", None, "ar")
        synth.assert_not_called()
        self.assertIn("تحذير", out)


class TestLangThreading(unittest.TestCase):
    def test_narration_lang_en_and_voice_model(self):
        fake = {"output": "/tmp/x.wav", "duration": 1.0, "chunks": [1]}
        with mock.patch("lib.long_narration.synthesize_long",
                        return_value=fake) as synth:
            studio.cmd_long_narration({}, "Hello world", None, "/tmp/o.wav",
                                      0.35, 1.0, voice="piper", lang="en")
        kwargs = synth.call_args.kwargs
        self.assertEqual(kwargs.get("lang"), "en")
        self.assertEqual(kwargs.get("voice"), "piper")
        self.assertIsNone(kwargs.get("model"))
        with mock.patch("lib.long_narration.synthesize_long",
                        return_value=fake) as synth:
            studio.cmd_long_narration({}, "Hello world", None, "/tmp/o.wav",
                                      0.35, 1.0,
                                      voice="en_US-ryan-medium", lang="ar")
        kwargs = synth.call_args.kwargs
        self.assertEqual(kwargs.get("voice"), "piper")
        self.assertEqual(kwargs.get("lang"), "ar")
        self.assertTrue(str(kwargs.get("model") or "").endswith(
            "en_US-ryan-medium.onnx"))
        with mock.patch("lib.long_narration.synthesize_long",
                        return_value=fake) as synth:
            studio.cmd_long_narration({}, "Hello world", None, "/tmp/o.wav",
                                      0.35, 1.0, voice="ryan", lang="ar")
        self.assertTrue(str(synth.call_args.kwargs.get("model") or "")
                        .endswith("en_US-ryan-medium.onnx"))

    def test_narration_unknown_or_female_voice_raises(self):
        for bad in ("lessac", "en_US-lessac-medium", "bogus-voice"):
            with self.assertRaises(ValueError, msg=bad):
                studio.cmd_long_narration({}, "Hello", None, "/tmp/o.wav",
                                          0.35, 1.0, voice=bad)

    def test_prompt_lang_en_reaches_llm(self):
        cfg = {"omniroute": {"model": "m", "fallback_model": "f",
                             "base_url": "http://localhost:20128",
                             "retries": 1, "retry_delay_seconds": 5}}
        with mock.patch("lib.omniroute_client.load_system_prompt",
                        return_value="EN-SYSTEM") as load, \
             mock.patch.object(
                 studio, "_llm_chat",
                 return_value=("عنوان\nكابشن", "omniroute", "m")) as chat:
            result, _step = studio.cmd_script(cfg, "anza", True, lang="en")
        self.assertIsNotNone(result)
        load.assert_called_with("en")
        self.assertEqual(chat.call_args.kwargs.get("system"), "EN-SYSTEM")

    def test_llm_chat_forwards_system_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = {"omniroute": {"model": "m1", "fallback_model": "m2",
                                 "base_url": "http://localhost:20128",
                                 "retries": 1, "retry_delay_seconds": 5},
                   "paths": {"runs_dir": td}}
            with mock.patch("lib.omniroute_client.chat",
                            return_value=("t", "via", "m")) as chat:
                studio._llm_chat(cfg, "prompt", system="SYS")
            self.assertEqual(chat.call_args.kwargs.get("system"), "SYS")

    def test_karaoke_ass_en_uses_latin_path(self):
        words = [{"w": "Hello", "start": 0.0, "end": 0.5},
                 {"w": "world.", "start": 0.5, "end": 1.0}]
        with tempfile.TemporaryDirectory() as td:
            ass = os.path.join(td, "c.ass")
            with mock.patch(
                    "lib.whisper_captions.transcribe_words",
                    return_value=(words, "Hello world.")):
                studio.cmd_karaoke_ass({}, "/tmp/a.wav", ass, "small", 28,
                                      lang="en")
            text = Path(ass).read_text(encoding="utf-8")
            self.assertIn("Direction: LTR", text)
            self.assertIn("Noto Sans", text)
            self.assertIn("Hello", text)

    def test_karaoke_ass_ar_keeps_capite_path(self):
        with tempfile.TemporaryDirectory() as td:
            ass = os.path.join(td, "c.ass")
            with mock.patch("lib.capite_captions.karaoke_ass",
                            return_value=([{"lines": [[{"w": "x"}]]}],
                                          "نص")) as karaoke:
                studio.cmd_karaoke_ass({}, "/tmp/a.wav", ass, "small", 28,
                                      lang="ar")
            karaoke.assert_called_once()

    def test_write_latin_ass_from_project(self):
        with tempfile.TemporaryDirectory() as td:
            ass = os.path.join(td, "c.ass")
            project = {"tracks": [
                {"type": "text", "words": [
                    {"w": "Hello", "start": 0.0, "end": 0.5}]}]}
            self.assertEqual(
                studio._write_latin_ass_from_project(project, ass), ass)
            self.assertIn("Direction: LTR",
                          Path(ass).read_text(encoding="utf-8"))
            self.assertIsNone(
                studio._write_latin_ass_from_project({"tracks": []},
                                                     os.path.join(td,
                                                                  "e.ass")))

    def test_resolve_long_chapter_passes_lang(self):
        os.makedirs(os.path.expanduser("~/workspace"), exist_ok=True)
        ws_tmp = tempfile.mkdtemp(prefix=".test-lv-",
                                  dir=os.path.expanduser("~/workspace"))
        self.addCleanup(shutil.rmtree, ws_tmp, True)
        text_path = os.path.join(ws_tmp, "ch.txt")
        Path(text_path).write_text("Hello world.", encoding="utf-8")
        img_path = os.path.join(ws_tmp, "cover.jpg")
        from PIL import Image
        Image.new("RGB", (16, 16)).save(img_path, "JPEG")
        fake_info = {"output": _fake_wav(ws_tmp), "duration": 5.0,
                     "chunks": [{"text": "Hello world.", "start": 0.0,
                                 "end": 5.0}]}
        entry = {"type": "text", "title": "Ch", "text_file": text_path,
                 "cover": img_path}
        with tempfile.TemporaryDirectory() as td, \
             mock.patch("lib.long_narration.synthesize_long",
                        return_value=fake_info) as synth:
            ch = studio._resolve_long_chapter({}, entry, td, 1.0, 0,
                                              voice="piper", lang="en")
        self.assertEqual(synth.call_args.kwargs.get("lang"), "en")
        self.assertEqual(len(ch["phrases"]), 1)

    def test_long_video_threads_lang_voice_and_latin_ass(self):
        os.makedirs(os.path.expanduser("~/workspace"), exist_ok=True)
        ws_tmp = tempfile.mkdtemp(prefix=".test-lv2-",
                                  dir=os.path.expanduser("~/workspace"))
        self.addCleanup(shutil.rmtree, ws_tmp, True)
        text_path = os.path.join(ws_tmp, "ch.txt")
        Path(text_path).write_text("Hello world.", encoding="utf-8")
        img_path = os.path.join(ws_tmp, "cover.jpg")
        from PIL import Image
        Image.new("RGB", (16, 16)).save(img_path, "JPEG")
        with tempfile.TemporaryDirectory() as td:
            cfg = studio.load_config()
            cfg["paths"]["runs_dir"] = os.path.join(td, "runs")
            cfg["long_video"] = {"default_music": "none"}
            chfile = os.path.join(td, "chapters.json")
            Path(chfile).write_text(json.dumps(
                {"title": "T", "hook": "H",
                 "chapters": [{"type": "text", "title": "Ch",
                               "text_file": text_path,
                               "cover": img_path}]},
                ensure_ascii=False), encoding="utf-8")
            out_mp4 = os.path.join(td, "long.mp4")
            fake_info = _fake_synth_info(td)
            project = {"tracks": [
                {"type": "text", "words": [
                    {"w": "Hello", "start": 0.0, "end": 0.5},
                    {"w": "world.", "start": 0.5, "end": 1.0}]}]}
            meta = {"total_duration": 30.0,
                    "intro": {"start": 0.0, "end": 5.0},
                    "outro": {"start": 25.0, "end": 30.0},
                    "chapters": [{"index": 1, "title": "Ch",
                                  "start": 5.0, "end": 25.0,
                                  "moral": ""}]}
            args = argparse.Namespace(
                out=out_mp4, title=None, hook=None, intro=None,
                outro=None, music=None, story=[], project=[],
                run_id=[], chapter_dir=[], chapter_text=[],
                text_file=[], cover=[], moral=[],
                chapters_file=chfile, auto_week=False, since=None,
                queue_file=None, motion="kenburns",
                motion_manifest=None, motion_dir=None, atempo=1.0,
                no_watermark=True, voice="en_US-ryan-medium",
                cmd_lang="en", improve_motion=False)
            with mock.patch("lib.long_narration.synthesize_long",
                            return_value=fake_info) as synth, \
                 mock.patch("lib.long_video.build_project",
                            return_value=(project, meta)) as build, \
                 mock.patch("lib.headless_stage.render_project",
                            return_value={"output": out_mp4,
                                          "seconds": 1.0,
                                          "size_bytes": 100}), \
                 mock.patch.object(studio, "_finish_video",
                                   return_value=out_mp4):
                rc, out = _capture(studio.cmd_long_video, cfg, args,
                                   lang="ar")
            self.assertEqual(rc, 0, out)
            self.assertEqual(build.call_args[0][0]["motion"], "kenburns")
            for call in synth.call_args_list:
                self.assertEqual(call.kwargs.get("lang"), "en")
                self.assertTrue(
                    str(call.kwargs.get("model") or "").endswith(
                        "en_US-ryan-medium.onnx"))
            ass_path = os.path.splitext(out_mp4)[0] + "-captions-en.ass"
            self.assertTrue(os.path.isfile(ass_path))
            self.assertIn("Direction: LTR",
                          Path(ass_path).read_text(encoding="utf-8"))

    def test_long_video_improve_motion_calls_improver(self):
        os.makedirs(os.path.expanduser("~/workspace"), exist_ok=True)
        ws_tmp = tempfile.mkdtemp(prefix=".test-lv3-",
                                  dir=os.path.expanduser("~/workspace"))
        self.addCleanup(shutil.rmtree, ws_tmp, True)
        text_path = os.path.join(ws_tmp, "ch.txt")
        Path(text_path).write_text("Hello world.", encoding="utf-8")
        img_path = os.path.join(ws_tmp, "cover.jpg")
        from PIL import Image
        Image.new("RGB", (16, 16)).save(img_path, "JPEG")
        with tempfile.TemporaryDirectory() as td:
            cfg = studio.load_config()
            cfg["paths"]["runs_dir"] = os.path.join(td, "runs")
            cfg["long_video"] = {"default_music": "none"}
            chfile = os.path.join(td, "chapters.json")
            Path(chfile).write_text(json.dumps(
                {"title": "T", "hook": "H",
                 "chapters": [{"type": "text", "title": "Ch",
                               "text_file": text_path,
                               "cover": img_path}]},
                ensure_ascii=False), encoding="utf-8")
            manifest = os.path.join(td, "motion.json")
            Path(manifest).write_text(json.dumps({"clips": []}),
                                      encoding="utf-8")
            motion_dir = os.path.join(td, "clips")
            os.makedirs(motion_dir)
            out_mp4 = os.path.join(td, "long.mp4")
            fake_info = _fake_synth_info(td)
            project = {"tracks": []}
            meta = {"total_duration": 30.0,
                    "intro": {"start": 0.0, "end": 5.0},
                    "outro": {"start": 25.0, "end": 30.0},
                    "chapters": [{"index": 1, "title": "Ch",
                                  "start": 5.0, "end": 25.0,
                                  "moral": ""}]}

            def _improve(spec, manifest_arg, dir_arg, **kwargs):
                self.assertEqual(manifest_arg, manifest)
                self.assertEqual(dir_arg, motion_dir)
                return {"spec": dict(spec, motion="clips"),
                        "motion": "clips", "reused": [], "generated": [],
                        "warnings": [],
                        "report": {"chapters": []}}

            args = argparse.Namespace(
                out=out_mp4, title=None, hook=None, intro=None,
                outro=None, music=None, story=[], project=[],
                run_id=[], chapter_dir=[], chapter_text=[],
                text_file=[], cover=[], moral=[],
                chapters_file=chfile, auto_week=False, since=None,
                queue_file=None, motion="kenburns",
                motion_manifest=manifest, motion_dir=motion_dir,
                atempo=1.0, no_watermark=True, voice="piper",
                cmd_lang=None, improve_motion=True)
            with mock.patch("lib.long_narration.synthesize_long",
                            return_value=fake_info), \
                 mock.patch("lib.long_video.improve_motion",
                            side_effect=_improve) as improve, \
                 mock.patch("lib.long_video.build_project",
                            return_value=(project, meta)) as build, \
                 mock.patch("lib.headless_stage.render_project",
                            return_value={"output": out_mp4,
                                          "seconds": 1.0,
                                          "size_bytes": 100}), \
                 mock.patch.object(studio, "_finish_video",
                                   return_value=out_mp4):
                rc, out = _capture(studio.cmd_long_video, cfg, args)
            self.assertEqual(rc, 0, out)
            self.assertEqual(improve.call_count, 1)
            self.assertEqual(build.call_args[0][0]["motion"], "clips")

    def test_long_video_improve_motion_without_manifest_fails(self):
        os.makedirs(os.path.expanduser("~/workspace"), exist_ok=True)
        ws_tmp = tempfile.mkdtemp(prefix=".test-lv4-",
                                  dir=os.path.expanduser("~/workspace"))
        self.addCleanup(shutil.rmtree, ws_tmp, True)
        text_path = os.path.join(ws_tmp, "ch.txt")
        Path(text_path).write_text("Hello world.", encoding="utf-8")
        img_path = os.path.join(ws_tmp, "cover.jpg")
        from PIL import Image
        Image.new("RGB", (16, 16)).save(img_path, "JPEG")
        with tempfile.TemporaryDirectory() as td:
            cfg = studio.load_config()
            cfg["paths"]["runs_dir"] = os.path.join(td, "runs")
            cfg["long_video"] = {"default_music": "none"}
            chfile = os.path.join(td, "chapters.json")
            Path(chfile).write_text(json.dumps(
                {"title": "T", "hook": "H",
                 "chapters": [{"type": "text", "title": "Ch",
                               "text_file": text_path,
                               "cover": img_path}]},
                ensure_ascii=False), encoding="utf-8")
            args = argparse.Namespace(
                out=os.path.join(td, "long.mp4"), title=None, hook=None,
                intro=None, outro=None, music=None, story=[],
                project=[], run_id=[], chapter_dir=[],
                chapter_text=[], text_file=[], cover=[], moral=[],
                chapters_file=chfile, auto_week=False, since=None,
                queue_file=None, motion="kenburns",
                motion_manifest=None, motion_dir=None, atempo=1.0,
                no_watermark=True, voice="piper", cmd_lang=None,
                improve_motion=True)
            fake_info = _fake_synth_info(td)
            with mock.patch("lib.long_narration.synthesize_long",
                            return_value=fake_info):
                rc, out = _capture(studio.cmd_long_video, cfg, args)
            self.assertEqual(rc, 1)
            self.assertIn("motion-manifest", out)


class TestMotionDefault(unittest.TestCase):
    def test_long_video_help_says_kenburns_default(self):
        _rc, out = _run_main(["studio.py", "long-video", "--help"])
        self.assertIn("kenburns (الافتراضي", out)
        self.assertNotIn("clips (الافتراضي", out)

    def test_long_video_default_motion_is_kenburns(self):
        with mock.patch.object(studio, "cmd_long_video",
                               return_value=0) as cmd:
            rc, _out = _run_main(["studio.py", "long-video",
                                  "--out", "/tmp/x.mp4"])
        self.assertEqual(rc, 0)
        self.assertEqual(cmd.call_args[0][1].motion, "kenburns")

    def test_improve_motion_flag_exists(self):
        with mock.patch.object(studio, "cmd_long_video",
                               return_value=0) as cmd:
            rc, _out = _run_main([
                "studio.py", "long-video", "--out", "/tmp/x.mp4",
                "--improve-motion", "--motion-manifest", "/tmp/m.json"])
        self.assertEqual(rc, 0)
        self.assertTrue(cmd.call_args[0][1].improve_motion)
        self.assertEqual(cmd.call_args[0][1].motion_manifest, "/tmp/m.json")


class TestAssembleNoMusic(unittest.TestCase):
    def test_assemble_music_flag_rejected(self):
        rc, out = _run_main(["studio.py", "assemble", "--run", "x",
                             "--out", "y.mp4", "--music", "z.mp3"])
        self.assertEqual(rc, 2)
        self.assertIn("unrecognized arguments: --music", out)


class TestRunLangVoice(unittest.TestCase):
    def test_run_parsing_passes_lang_and_voice(self):
        with mock.patch.object(studio, "cmd_run",
                               return_value=0) as run:
            rc, _out = _run_main([
                "studio.py", "run", "--story", "s", "--project", "p",
                "--out", "o.mp4", "--lang", "en",
                "--voice", "en_US-ryan-medium", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertEqual(run.call_args[1].get("lang"), "en")
        self.assertEqual(run.call_args[1].get("voice"),
                         "en_US-ryan-medium")

    def test_run_dry_run_prints_lang_and_voice(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = studio.load_config()
            cfg["paths"]["runs_dir"] = os.path.join(td, "runs")
            rc, out = _capture(
                studio.cmd_run, cfg, "s", "p", os.path.join(td, "o.mp4"),
                True, dry_run=True, lang="en",
                voice="en_US-ryan-medium")
        self.assertEqual(rc, 0)
        self.assertIn("en_US-ryan-medium", out)
        self.assertIn("اللغة: en", out)

    def test_run_rejects_unknown_voice(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = studio.load_config()
            cfg["paths"]["runs_dir"] = os.path.join(td, "runs")
            rc, out = _capture(
                studio.cmd_run, cfg, "s", "p", os.path.join(td, "o.mp4"),
                True, dry_run=True, voice="lessac")
        self.assertEqual(rc, 2)
        self.assertIn("غير معروف", out)

    def test_run_passes_lang_to_script(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = studio.load_config()
            cfg["paths"]["runs_dir"] = os.path.join(td, "runs")
            script = mock.Mock(
                return_value=({"title": "عنوان"}, {"status": "ok"}))
            produce = mock.Mock(return_value={
                "images": ["a.png"], "phrases": [{"text": "x"}]})
            assemble = mock.Mock(return_value=("/tmp/out.mp4", 2.0))
            with mock.patch.object(studio, "cmd_script", script), \
                 mock.patch.object(studio, "cmd_produce", produce), \
                 mock.patch.object(studio, "cmd_assemble", assemble):
                rc = studio.cmd_run(cfg, "قصة", "proj",
                                    os.path.join(td, "out.mp4"), True,
                                    lang="en")
            self.assertEqual(rc, 0)
            self.assertEqual(script.call_args[1].get("lang"), "en")


class TestExpandMotionPromptsCmd(unittest.TestCase):
    """أمر expand-motion-prompts (جولة v0.1.54 — W2)."""

    def _write_prompts(self, td, items):
        path = os.path.join(td, "prompts.json")
        Path(path).write_text(json.dumps(items, ensure_ascii=False),
                              encoding="utf-8")
        return path

    def _read_out(self, path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def _fake_expand(self, items):
        out = []
        for item in items:
            if item.get("id") == "bad":
                out.append({"id": "bad", "prompt": item["prompt"],
                            "expanded_prompt": item["prompt"],
                            "expanded": False,
                            "reason": "llm-unavailable"})
            else:
                out.append({"id": item.get("id"),
                            "prompt": item["prompt"],
                            "expanded_prompt": item["prompt"] + " — موسّع",
                            "expanded": True, "reason": None})
        return out

    def test_valid_file_expands_and_reports_arabic_summary(self):
        with tempfile.TemporaryDirectory() as td:
            src = self._write_prompts(td, [
                {"id": "s1", "prompt": "رجل يمشي في السوق"},
                {"id": "bad", "prompt": "امرأة تفتح الباب"}])
            out_path = os.path.join(td, "out.json")
            rc, out = _capture(studio.cmd_expand_motion_prompts, {},
                               src, out_path,
                               expand_fn=self._fake_expand)
            self.assertEqual(rc, 0, out)
            self.assertIn("وُسّع 1 من 2", out)
            self.assertIn("رُجع 1 للأصل", out)
            self.assertIn("llm-unavailable", out)
            self.assertIn("كُتب الناتج في", out)
            rows = self._read_out(out_path)
            self.assertEqual(len(rows), 2)
            self.assertTrue(rows[0]["expanded"])
            self.assertIn("موسّع", rows[0]["expanded_prompt"])
            self.assertIsNone(rows[0]["reason"])
            self.assertFalse(rows[1]["expanded"])
            self.assertEqual(rows[1]["expanded_prompt"],
                             "امرأة تفتح الباب")
            self.assertEqual(rows[1]["reason"], "llm-unavailable")

    def test_missing_file_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out = _capture(studio.cmd_expand_motion_prompts, {},
                               os.path.join(td, "nope.json"),
                               os.path.join(td, "out.json"),
                               expand_fn=self._fake_expand)
            self.assertEqual(rc, 2)
            self.assertIn("غير موجود", out)
            self.assertFalse(os.path.exists(os.path.join(td, "out.json")))

    def test_invalid_json_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            bad = os.path.join(td, "bad.json")
            Path(bad).write_text("{not json", encoding="utf-8")
            rc, _out = _capture(studio.cmd_expand_motion_prompts, {},
                                bad, os.path.join(td, "out.json"),
                                expand_fn=self._fake_expand)
            self.assertEqual(rc, 2)
            self.assertFalse(os.path.exists(os.path.join(td, "out.json")))

    def test_non_list_top_level_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            src = self._write_prompts(td, {"prompt": "x"})
            rc, _out = _capture(studio.cmd_expand_motion_prompts, {},
                                src, os.path.join(td, "out.json"),
                                expand_fn=self._fake_expand)
            self.assertEqual(rc, 2)

    def test_item_without_prompt_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            for items in ([{"id": "s1"}],
                          [{"id": "s1", "prompt": ""}],
                          [{"id": "s1", "prompt": "   "}],
                          [{"id": "s1", "prompt": 42}],
                          ["not-a-dict"]):
                src = self._write_prompts(td, items)
                rc, out = _capture(studio.cmd_expand_motion_prompts, {},
                                   src, os.path.join(td, "out.json"),
                                   expand_fn=self._fake_expand)
                self.assertEqual(rc, 2, items)
                self.assertIn("prompt", out)

    def test_failed_item_falls_back_to_original_and_is_saved(self):
        with tempfile.TemporaryDirectory() as td:
            src = self._write_prompts(td, [
                {"id": "bad", "prompt": "رجل يجلس تحت شجرة"}])
            out_path = os.path.join(td, "out.json")
            rc, out = _capture(studio.cmd_expand_motion_prompts, {},
                               src, out_path,
                               expand_fn=self._fake_expand)
            self.assertEqual(rc, 0, out)
            rows = self._read_out(out_path)
            self.assertEqual(len(rows), 1)
            self.assertFalse(rows[0]["expanded"])
            self.assertEqual(rows[0]["prompt"], "رجل يجلس تحت شجرة")
            self.assertEqual(rows[0]["expanded_prompt"],
                             "رجل يجلس تحت شجرة")
            self.assertEqual(rows[0]["reason"], "llm-unavailable")
            self.assertIn("رُجع للأصل: bad", out)

    def test_expand_fn_raising_falls_back_all_items(self):
        """فشل التوسيع الكامل fail-open: كل الموجّهات بأصلها."""
        def _boom(_items):
            raise RuntimeError("provider down")

        with tempfile.TemporaryDirectory() as td:
            src = self._write_prompts(td, [
                {"id": "s1", "prompt": "رجل يمشي"},
                {"prompt": "طفل يلعب"}])
            out_path = os.path.join(td, "out.json")
            rc, out = _capture(studio.cmd_expand_motion_prompts, {},
                               src, out_path, expand_fn=_boom)
            self.assertEqual(rc, 0, out)
            rows = self._read_out(out_path)
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertFalse(row["expanded"])
                self.assertEqual(row["expanded_prompt"], row["prompt"])
            self.assertIn("وُسّع 0 من 2", out)

    def test_lazy_import_uses_lib_prompt_expand_contract(self):
        """مسار الاستيراد الكسول يطابق عقد W1 حرفيًا."""
        import lib
        import types
        stub = types.ModuleType("lib.prompt_expand")

        def _stub_expand(items, **kwargs):
            return [{"id": it.get("id"), "prompt": it["prompt"],
                     "expanded_prompt": it["prompt"] + " (موسّع)",
                     "expanded": True, "reason": None}
                    for it in items]

        stub.expand_motion_prompts = _stub_expand
        with tempfile.TemporaryDirectory() as td:
            src = self._write_prompts(td, [
                {"id": "s1", "prompt": "رجل يمشي"}])
            out_path = os.path.join(td, "out.json")
            # إصلاح دمج المنسق: ترقيع sys.modules وحده يعتمد
            # على الترتيب — فـ`from lib import prompt_expand`
            # يرجع سمة حزمة `lib` إن وُجدت (الوحدة الحقيقية
            # مستوردة أصلًا في المجموعة الكاملة) بلا مراجعة
            # sys.modules، فيتجاهل الـstub ويفشل الاختبار.
            # ترقيع السمة نفسها (مع sys.modules) حاسم في
            # الترتيبين.
            with mock.patch.dict(sys.modules,
                                 {"lib.prompt_expand": stub}), \
                 mock.patch.object(lib, "prompt_expand", stub,
                                   create=True):
                rc, out = _capture(studio.cmd_expand_motion_prompts, {},
                                   src, out_path)
            self.assertEqual(rc, 0, out)
            rows = self._read_out(out_path)
            self.assertTrue(rows[0]["expanded"])
            self.assertIn("(موسّع)", rows[0]["expanded_prompt"])

    def test_real_module_expands_via_free_rotation_mock(self):
        """تكامل حقيقي مع وحدة W1 بعد دمجها: الاستيراد الكسول
        يستدعي expand_motion_prompts الفعلية (لا stub)."""
        from lib import prompt_expand
        expanded = ("رجل يمشي في السوق بخطوات واثقة والكاميرا "
                    "تتبعه من الخلف في ضوء الشمس الدافئ")
        with tempfile.TemporaryDirectory() as td:
            src = self._write_prompts(td, [
                {"id": "s1", "prompt": "رجل يمشي في السوق"}])
            out_path = os.path.join(td, "out.json")
            fresh = prompt_expand.llm_state.default_state()
            with mock.patch.object(prompt_expand.llm_state,
                                   "load_state",
                                   return_value=fresh), \
                 mock.patch.object(
                     prompt_expand.omniroute_client,
                     "chat_free_rotation",
                     return_value=(expanded, "free",
                                   "openrouter/free")) as chat:
                rc, out = _capture(studio.cmd_expand_motion_prompts, {},
                                   src, out_path)
            self.assertEqual(rc, 0, out)
            self.assertEqual(chat.call_count, 1)
            self.assertIn("وُسّع 1 من 1", out)
            rows = self._read_out(out_path)
            self.assertTrue(rows[0]["expanded"])
            self.assertEqual(rows[0]["expanded_prompt"], expanded)
            self.assertIsNone(rows[0]["reason"])

    def test_arg_parsing_wires_prompts_and_out(self):
        with mock.patch.object(studio, "cmd_expand_motion_prompts",
                               return_value=0) as cmd:
            rc, _out = _run_main([
                "studio.py", "expand-motion-prompts",
                "--prompts", "/tmp/p.json", "--out", "/tmp/o.json"])
        self.assertEqual(rc, 0)
        self.assertEqual(cmd.call_count, 1)
        self.assertEqual(cmd.call_args[0][1], "/tmp/p.json")
        self.assertEqual(cmd.call_args[0][2], "/tmp/o.json")

    def test_help_lists_prompts_and_out_flags(self):
        _rc, out = _run_main(["studio.py", "expand-motion-prompts",
                              "--help"])
        self.assertIn("--prompts", out)
        self.assertIn("--out", out)


if __name__ == "__main__":
    unittest.main()
