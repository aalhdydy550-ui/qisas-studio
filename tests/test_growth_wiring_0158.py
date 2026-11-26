#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات توصيل أوامر جولة v0.1.58 (مولدات الشورتس وخطوط التوليد):
trend-scout / scene-shorts / tiktok-check / script-check /
topic-brief / hook-title.

تعمل بـ `python3 -m unittest tests.test_growth_wiring_0158 -v` من
`~/workspace/studio`. بلا شبكة وبلا LLM إطلاقًا — كل المدخلات
ملفات مؤقتة تُبنى هنا، والفيديوهات تركيبية بـffmpeg.
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

HAS_FFMPEG = shutil.which("ffmpeg") is not None

GOOD_TITLE = "النجار الأمين | قصة حقيقية"
GOOD_HOOK = "ظلم أخاه وسرق ميراثه — فماذا فعل الله به؟"
# هوك العنوان المكتوب أقصر عمدًا: مواصفة hook-title ترفض ما لا
# يتسع في سطرين × 19 حرفًا داخل النطاق الأوسط.
HOOK_TITLE = "ظلم أخاه وسرق ميراثه؟"
GOOD_STORY = ("نجار فقير وجد ذهبًا في باب وأعاده لصاحبه. "
              "جملة ثانية في القصة. جملة ثالثة في القصة. "
              "العبرة: الظلم لا يدوم.")
GOOD_CAPTION = (GOOD_TITLE + "\n"
                "قصة حقيقية عن نجار فقير وجد ذهبًا وأعاده "
                "لصاحبه.\n"
                "العبرة: الأمانة ترفع صاحبها.\n"
                "#قصص #قصص_حقيقية #قصص_واقعية #قصة_وعبرة")

VIDEOS = [
    {"channel": "قناة تجريبية", "title": "قصة رجل عادي",
     "views": 1000, "likes": 100, "saves": 20, "shares": 10, "url": ""},
    {"channel": "قناة تجريبية", "title": "قصة امرأة صابرة",
     "views": 2000, "likes": 100, "saves": 15, "shares": 8, "url": ""},
    {"channel": "قناة تجريبية", "title": "قصة تاجر أمين",
     "views": 3000, "likes": 100, "saves": 10, "shares": 5, "url": ""},
    {"channel": "قناة تجريبية", "title": "قصة حقيقية هزت المدينة",
     "views": 40000, "likes": 1000, "saves": 209, "shares": 370,
     "url": ""},
]

QUEUE_TEXT = """# طابور قصص

## في الانتظار

1. **قصة 1** — بلا ملاحظات
2. **قصة 2** — بلا ملاحظات
3. **قصة 3** — بلا ملاحظات
4. **قصة 4** — بلا ملاحظات
5. **قصة 5** — بلا ملاحظات
6. **قصة 6** — بلا ملاحظات
7. **قصة 7** — بلا ملاحظات

## المنشور

1. **قصة منشورة** — نُشرت
"""

VALID_SCRIPT = {
    "title": "أخي سرق ميراثي",
    "hook": "ليه أخي سرق ميراثي؟ انكشف السر بعد عشر سنين!",
    "text": (
        "أخي وقّعني على ورقة وأنا مش عارفة إنها تنازل عن الميراث. "
        "صبرت ثلاث سنين والناس كلها شايفة وساكتة. "
        "وفي يوم لقيت الورقة الأصلية في درج قديم. "
        "الورقة أثبتت إن التوقيع مزوّر. "
        "رجّع أخي كل حاجة واعتذر قدام العيلة كلها. "
        "العبرة: الظلم مهما طال ليله، الحق بيظهر في الآخر."),
    "moral": "الظلم مهما طال ليله، الحق بيظهر.",
    "closing_question": "لو كنت مكانه، كنت هتعمل إيه؟",
    "parts": 1,
    "scenes": [
        "أخي وقّعني على ورقة تنازل عن الميراث.",
        "صبرت ثلاث سنين والناس شايفة وساكتة.",
        "لقيت الورقة الأصلية في درج قديم.",
        "الورقة أثبتت إن التوقيع مزوّر.",
        "رجّع أخي كل حاجة واعتذر.",
        "العبرة: الظلم مهما طال ليله، الحق بيظهر.",
    ],
}

BRIEF_CANDIDATES = [
    {"title": "قصة الرجل الذي أيقظ أولاده للصلاة",
     "hook": "أيقظ أولاده للصلاة",
     "moral_angle": "الصلاة تجلب الرزق",
     "source_url": "",
     "pattern": "إطار ديني/أخلاقي", "score": 9.5,
     "reason": "مرشح اختبار"},
    {"title": "قصة الأب وكيس المسامير",
     "hook": "كيس مسامير غيّر ولده",
     "moral_angle": "الكلمة الجارحة تترك أثرًا",
     "source_url": "",
     "pattern": "حكمة أبوية", "score": 8.0,
     "reason": "مرشح اختبار"},
]


def _capture(fn, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*args, **kwargs)
    return rc, buf.getvalue()


def _write(td, name, text):
    path = os.path.join(td, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def _make_video(path, size="720x1280", seconds=2):
    """فيديو اختبار (لون + نغمة)."""
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
           "color=c=0x336699:s=%s:d=%s" % (size, seconds),
           "-f", "lavfi", "-i", "sine=frequency=440:d=%s" % seconds,
           "-shortest", path]
    subprocess.run(cmd, check=True, timeout=180)


class TestTrendScoutCmd(unittest.TestCase):
    def test_ok_ranks_and_suggests(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "videos.json",
                          json.dumps(VIDEOS, ensure_ascii=False))
            rc, out = _capture(studio.cmd_trend_scout, {}, path)
            self.assertEqual(rc, 0)
            self.assertIn("كشّاف ترندات", out)
            self.assertIn("قصة حقيقية هزت المدينة", out)

    def test_json_pure(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "videos.json",
                          json.dumps(VIDEOS, ensure_ascii=False))
            rc, out = _capture(studio.cmd_trend_scout, {}, path,
                               as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(parsed["suggestions"][0]["title"],
                             "قصة حقيقية هزت المدينة")
            self.assertNotIn("كشّاف ترندات", out)

    def test_top_n_limits_suggestions(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "videos.json",
                          json.dumps(VIDEOS, ensure_ascii=False))
            rc, out = _capture(studio.cmd_trend_scout, {}, path, top_n=1,
                               as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(len(parsed["suggestions"]), 1)

    def test_missing_file_returns_2(self):
        rc, _out = _capture(studio.cmd_trend_scout, {},
                            "/tmp/لا-يوجد-فيديوهات.json")
        self.assertEqual(rc, 2)

    def test_corrupt_json_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "videos.json", "{ليس json")
            rc, _out = _capture(studio.cmd_trend_scout, {}, path)
            self.assertEqual(rc, 2)


class TestSceneShortsCmd(unittest.TestCase):
    def test_short_video_reports_incomplete(self):
        if not HAS_FFMPEG:
            self.skipTest("ffmpeg غير موجود")
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "long.mp4")
            _make_video(video, size="1280x720", seconds=4)
            scenes = _write(td, "scenes.json",
                            json.dumps([{"start": 0, "end": 4}],
                                       ensure_ascii=False))
            out_dir = os.path.join(td, "parts")
            rc, out = _capture(studio.cmd_scene_shorts, {},
                               video, scenes, out_dir=out_dir)
            self.assertEqual(rc, 1)
            self.assertIn("غير مكتمل", out)

    def test_short_video_json_pure(self):
        if not HAS_FFMPEG:
            self.skipTest("ffmpeg غير موجود")
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "long.mp4")
            _make_video(video, size="1280x720", seconds=4)
            scenes = _write(td, "scenes.json",
                            json.dumps([{"start": 0, "end": 4}],
                                       ensure_ascii=False))
            out_dir = os.path.join(td, "parts")
            rc, out = _capture(studio.cmd_scene_shorts, {},
                               video, scenes, out_dir=out_dir,
                               as_json=True)
            self.assertEqual(rc, 1)
            parsed = json.loads(out)
            self.assertEqual(parsed["parts"][0]["status"], "غير مكتمل")

    def test_missing_video_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            scenes = _write(td, "scenes.json",
                            json.dumps([{"start": 0, "end": 4}],
                                       ensure_ascii=False))
            rc, _out = _capture(studio.cmd_scene_shorts, {},
                                os.path.join(td, "nope.mp4"), scenes,
                                out_dir=os.path.join(td, "parts"))
            self.assertEqual(rc, 2)

    def test_corrupt_scenes_returns_2(self):
        if not HAS_FFMPEG:
            self.skipTest("ffmpeg غير موجود")
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "long.mp4")
            _make_video(video, size="1280x720", seconds=4)
            scenes = _write(td, "scenes.json", "{ليس json")
            rc, _out = _capture(studio.cmd_scene_shorts, {},
                                video, scenes,
                                out_dir=os.path.join(td, "parts"))
            self.assertEqual(rc, 2)

    def test_missing_scenes_file_returns_2(self):
        rc, _out = _capture(studio.cmd_scene_shorts, {},
                            "/tmp/فيديو.mp4",
                            "/tmp/لا-يوجد-مشاهد.json",
                            out_dir="/tmp/أجزاء")
        self.assertEqual(rc, 2)


class TestTiktokCheckCmd(unittest.TestCase):
    def test_ok_passes(self):
        with tempfile.TemporaryDirectory() as td:
            queue = _write(td, "queue.md", QUEUE_TEXT)
            story = _write(td, "story.txt", GOOD_STORY)
            rc, out = _capture(studio.cmd_tiktok_check, {}, GOOD_TITLE,
                               GOOD_CAPTION, hook=GOOD_HOOK,
                               story_file=story, queue_file=queue,
                               trend_keywords="ميراث,ظلم")
            self.assertEqual(rc, 0)
            self.assertIn("سليم", out)

    def test_json_pure(self):
        with tempfile.TemporaryDirectory() as td:
            queue = _write(td, "queue.md", QUEUE_TEXT)
            story = _write(td, "story.txt", GOOD_STORY)
            rc, out = _capture(studio.cmd_tiktok_check, {}, GOOD_TITLE,
                               GOOD_CAPTION, hook=GOOD_HOOK,
                               story_file=story, queue_file=queue,
                               trend_keywords="ميراث,ظلم",
                               as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertTrue(parsed["ok"])
            self.assertNotIn("سليم", out)

    def test_caption_without_moral_returns_1(self):
        caption = GOOD_CAPTION.replace(
            "العبرة: الأمانة ترفع صاحبها.\n", "")
        rc, _out = _capture(studio.cmd_tiktok_check, {}, GOOD_TITLE,
                            caption, hook=GOOD_HOOK,
                            trend_keywords="ميراث,ظلم")
        self.assertEqual(rc, 1)

    def test_empty_title_returns_2(self):
        rc, _out = _capture(studio.cmd_tiktok_check, {}, "   ",
                            GOOD_CAPTION, hook=GOOD_HOOK)
        self.assertEqual(rc, 2)

    def test_missing_queue_file_returns_2(self):
        rc, _out = _capture(studio.cmd_tiktok_check, {}, GOOD_TITLE,
                            GOOD_CAPTION, hook=GOOD_HOOK,
                            queue_file="/tmp/لا-يوجد-طابور.md")
        self.assertEqual(rc, 2)


class TestScriptCheckCmd(unittest.TestCase):
    def _script_file(self, td, script=None):
        return _write(td, "script.json",
                      json.dumps(script if script is not None
                                 else VALID_SCRIPT, ensure_ascii=False))

    def test_ok_passes(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out = _capture(studio.cmd_script_check, {},
                               self._script_file(td))
            self.assertEqual(rc, 0)
            self.assertIn("سليم", out)

    def test_json_pure(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out = _capture(studio.cmd_script_check, {},
                               self._script_file(td), as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertTrue(parsed["ok"])
            self.assertNotIn("سليم", out)

    def test_weak_hook_returns_1(self):
        with tempfile.TemporaryDirectory() as td:
            script = dict(VALID_SCRIPT)
            script["hook"] = "كان يا ما كان في رجل طيب."
            rc, _out = _capture(studio.cmd_script_check, {},
                                self._script_file(td, script))
            self.assertEqual(rc, 1)

    def test_missing_file_returns_2(self):
        rc, _out = _capture(studio.cmd_script_check, {},
                            "/tmp/لا-يوجد-سكريبت.json")
        self.assertEqual(rc, 2)

    def test_corrupt_json_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "script.json", "{ليس json")
            rc, _out = _capture(studio.cmd_script_check, {}, path)
            self.assertEqual(rc, 2)


class TestTopicBriefCmd(unittest.TestCase):
    def _input_file(self, td, theme="قصص عن الأمانة"):
        payload = {"theme": theme, "candidates": BRIEF_CANDIDATES,
                   "existing_titles": ["النجار الأمين"]}
        return _write(td, "brief.json",
                      json.dumps(payload, ensure_ascii=False))

    def test_ok_from_input_file(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out = _capture(studio.cmd_topic_brief, {},
                               input_file=self._input_file(td))
            self.assertEqual(rc, 0)
            self.assertIn("قصص عن الأمانة", out)

    def test_json_pure(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out = _capture(studio.cmd_topic_brief, {},
                               input_file=self._input_file(td),
                               as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(parsed["theme"], "قصص عن الأمانة")
            self.assertTrue(parsed["uncovered_angles"])

    def test_theme_plus_queue_file(self):
        with tempfile.TemporaryDirectory() as td:
            queue = _write(td, "queue.md", QUEUE_TEXT)
            cand = _write(td, "candidates.json",
                          json.dumps(BRIEF_CANDIDATES,
                                     ensure_ascii=False))
            rc, out = _capture(studio.cmd_topic_brief, {},
                               theme="قصص عن الأمانة",
                               candidates_file=cand, queue_file=queue)
            self.assertEqual(rc, 0)
            self.assertIn("قصص عن الأمانة", out)

    def test_no_theme_no_input_returns_2(self):
        rc, _out = _capture(studio.cmd_topic_brief, {})
        self.assertEqual(rc, 2)

    def test_missing_input_file_returns_2(self):
        rc, _out = _capture(studio.cmd_topic_brief, {},
                            input_file="/tmp/لا-يوجد-موجز.json")
        self.assertEqual(rc, 2)

    def test_corrupt_input_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "brief.json", "{ليس json")
            rc, _out = _capture(studio.cmd_topic_brief, {},
                                input_file=path)
            self.assertEqual(rc, 2)


class TestHookTitleCmd(unittest.TestCase):
    def test_spec_json_pure(self):
        rc, out = _capture(studio.cmd_hook_title, {}, None, HOOK_TITLE,
                           as_json=True)
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["text"], HOOK_TITLE)
        self.assertEqual(parsed["start"], 0.0)
        self.assertEqual(parsed["end"], 3.0)
        self.assertNotIn("حُرق", out)

    def test_apply_burns_title(self):
        if not HAS_FFMPEG:
            self.skipTest("ffmpeg غير موجود")
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "short.mp4")
            _make_video(video, seconds=2)
            out_path = os.path.join(td, "titled.mp4")
            rc, out = _capture(studio.cmd_hook_title, {}, video,
                               HOOK_TITLE, out=out_path)
            self.assertEqual(rc, 0)
            self.assertIn("حُرق عنوان الهوك", out)
            self.assertTrue(os.path.isfile(out_path))
            info = check_lib.probe(out_path)
            self.assertEqual((info["width"], info["height"]),
                             (720, 1280))
            self.assertTrue(1.5 <= info["duration"] <= 2.5)

    def test_apply_default_out_name(self):
        if not HAS_FFMPEG:
            self.skipTest("ffmpeg غير موجود")
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "short.mp4")
            _make_video(video, seconds=2)
            rc, _out = _capture(studio.cmd_hook_title, {}, video,
                                HOOK_TITLE)
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isfile(
                os.path.join(td, "short-hook-title.mp4")))

    def test_empty_title_returns_2(self):
        rc, _out = _capture(studio.cmd_hook_title, {}, None, "   ")
        self.assertEqual(rc, 2)

    def test_missing_video_returns_2(self):
        rc, _out = _capture(studio.cmd_hook_title, {},
                            "/tmp/لا-يوجد-شورت.mp4", HOOK_TITLE)
        self.assertEqual(rc, 2)

    def test_no_video_apply_returns_2(self):
        rc, _out = _capture(studio.cmd_hook_title, {}, None, HOOK_TITLE)
        self.assertEqual(rc, 2)


class TestGrowthDispatch0158(unittest.TestCase):
    def test_help_lists_six_commands(self):
        studio_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        proc = subprocess.run(
            [sys.executable, "studio.py", "--help"],
            cwd=studio_dir, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0)
        for cmd in ("trend-scout", "scene-shorts", "tiktok-check",
                    "script-check", "topic-brief", "hook-title"):
            self.assertIn(cmd, proc.stdout)

    def test_help_ar_lists_six_commands(self):
        argv = ["studio.py", "help-ar"]
        with mock.patch.object(sys, "argv", argv):
            rc, out = _capture(studio.main)
        self.assertEqual(rc, 0)
        for cmd in ("trend-scout", "scene-shorts", "tiktok-check",
                    "script-check", "topic-brief", "hook-title"):
            self.assertIn(cmd, out)

    def test_dispatch_trend_scout(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "videos.json",
                          json.dumps(VIDEOS, ensure_ascii=False))
            argv = ["studio.py", "trend-scout", "--videos-file", path]
            with mock.patch.object(sys, "argv", argv):
                rc, out = _capture(studio.main)
            self.assertEqual(rc, 0)
            self.assertIn("كشّاف ترندات", out)

    def test_dispatch_tiktok_check(self):
        with tempfile.TemporaryDirectory() as td:
            queue = _write(td, "queue.md", QUEUE_TEXT)
            story = _write(td, "story.txt", GOOD_STORY)
            argv = ["studio.py", "tiktok-check", "--title", GOOD_TITLE,
                    "--caption", GOOD_CAPTION, "--hook", GOOD_HOOK,
                    "--story-file", story, "--queue-file", queue,
                    "--trend-keywords", "ميراث,ظلم"]
            with mock.patch.object(sys, "argv", argv):
                rc, out = _capture(studio.main)
            self.assertEqual(rc, 0)
            self.assertIn("سليم", out)

    def test_dispatch_hook_title_json(self):
        argv = ["studio.py", "hook-title", "--title", HOOK_TITLE,
                "--json"]
        with mock.patch.object(sys, "argv", argv):
            rc, out = _capture(studio.main)
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["text"], HOOK_TITLE)


if __name__ == "__main__":
    unittest.main()
