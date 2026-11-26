#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات توصيل أوامر النمو الخمسة (جولة v0.1.57، المرحلة 2):
seo-check / title-lint / hook-score / viral-rank / retention-read.

تعمل بـ `python3 -m unittest tests.test_growth_wiring -v` من
`~/workspace/studio`. بلا شبكة وبلا LLM إطلاقًا — كل المدخلات
ملفات مؤقتة تُبنى هنا.
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio

GOOD_TITLE = "النجار الأمين | قصة حقيقية"
GOOD_DESC = ("قصة حقيقية عن نجار فقير وجد ذهبًا وأعاده لصاحبه.\n"
             "والنهاية أغرب مما تتخيل.")
GOOD_TAGS = "قصص وعبر،قصص واقعية،قصص مؤثرة،حكايات،النجار الأمين"
GOOD_STORY = "نجار فقير وجد ذهبًا في باب وأعاده لصاحبه"

STRONG_HOOK = ("ليه الراجل ظلم أخوه 3 مرات؟ مستحيل يفلت — الحقيقة "
               "انكشفت فجأة!")
GOOD_HOOK = "ليه الراجل ظلم أخوه؟ الحقيقة انكشفت فجأة!"
WEAK_HOOK = "يا جماعة تعالوا أحكيلكم قصة راجل طيب"
AISHA_HOOK = "قالوا بتحفر قبرها… طلعت بتحفر جنة بناتها!"

HEALTHY_POINTS = [(0, 100), (5, 97), (10, 95), (15, 93), (20, 91),
                  (25, 90), (30, 88), (35, 87), (40, 86), (45, 85),
                  (50, 84), (55, 83), (60, 82)]
CLIFF_POINTS = [(0, 100), (5, 97), (10, 95), (15, 93), (20, 91),
                (25, 90), (30, 88), (35, 87), (40, 86), (45, 71),
                (50, 70), (55, 69), (60, 68)]

SRT_TRANSCRIPT = """1
00:00:00,000 --> 00:00:10,000
كان يا ما كان في قرية بعيدة

2
00:00:10,000 --> 00:00:19,000
عاش رجل فقير يعمل في السوق

3
00:00:19,000 --> 00:00:28,000
سار الرجل في السوق يبحث عن رزقه

4
00:00:28,000 --> 00:00:40,000
عاد إلى بيته متعبًا وجلس يستريح

5
00:00:40,000 --> 00:00:50,000
وفي يوم جاءه ضيف غريب يطلب الماء
"""


def _capture(fn, *args, **kwargs):
    buf = io.StringIO()
    with mock.patch("sys.stdout", buf):
        rc = fn(*args, **kwargs)
    return rc, buf.getvalue()


def _write(td, name, text):
    path = os.path.join(td, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def _csv(points):
    lines = ["Time (seconds),Audience retention"]
    for t, v in points:
        lines.append("%s,%s" % (t, v))
    return "\n".join(lines) + "\n"


def _video(channel, title, views, duration=45):
    return {"channel": channel, "title": title,
            "views": views, "duration": duration, "url": ""}


# قناتان تركيبيتان (أرقام مختلقة للاختبار فقط) — كل منهما
# 4 فيديوهات حتى يُحسب وسيطها.
VIDEOS = [
    _video("قناة تجريبية أ", "قصة رجل عادي", 100),
    _video("قناة تجريبية أ", "قصة امرأة صابرة", 200),
    _video("قناة تجريبية أ", "قصة تاجر أمين", 300),
    _video("قناة تجريبية أ", "قصة حقيقية هزت المدينة", 4000),
    _video("قناة تجريبية ب", "حكاية الجار", 800),
    _video("قناة تجريبية ب", "حكاية المسافر", 900),
    _video("قناة تجريبية ب", "حكاية المعلم", 1100),
    _video("قناة تجريبية ب", "كيف نجا من الغرق؟", 3000),
]


class TestSeoCheckCmd(unittest.TestCase):
    def test_ok_passes(self):
        rc, out = _capture(studio.cmd_seo_check, {}, GOOD_TITLE,
                           GOOD_DESC, GOOD_TAGS, story_file=None)
        self.assertEqual(rc, 0)
        self.assertIn("سليم", out)
        self.assertIn("تقرير فحص SEO", out)

    def test_ok_with_story_file(self):
        with tempfile.TemporaryDirectory() as td:
            story = _write(td, "story.txt", GOOD_STORY)
            rc, out = _capture(studio.cmd_seo_check, {}, GOOD_TITLE,
                               GOOD_DESC, GOOD_TAGS, story_file=story)
            self.assertEqual(rc, 0)
            self.assertIn("سليم", out)

    def test_json_pure(self):
        rc, out = _capture(studio.cmd_seo_check, {}, GOOD_TITLE,
                           GOOD_DESC, GOOD_TAGS, as_json=True)
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["title"], GOOD_TITLE)
        self.assertNotIn("تقرير فحص SEO", out)

    def test_not_ok_returns_1(self):
        rc, out = _capture(studio.cmd_seo_check, {}, GOOD_TITLE,
                           "", GOOD_TAGS)
        self.assertEqual(rc, 1)
        self.assertIn("فيه ملاحظات", out)

    def test_not_ok_json_still_pure(self):
        rc, out = _capture(studio.cmd_seo_check, {}, GOOD_TITLE,
                           "", GOOD_TAGS, as_json=True)
        self.assertEqual(rc, 1)
        parsed = json.loads(out)
        self.assertFalse(parsed["ok"])
        self.assertTrue(parsed["issues"])

    def test_empty_title_returns_2(self):
        rc, _out = _capture(studio.cmd_seo_check, {}, "   ",
                            GOOD_DESC, GOOD_TAGS)
        self.assertEqual(rc, 2)

    def test_missing_story_file_returns_2(self):
        rc, _out = _capture(studio.cmd_seo_check, {}, GOOD_TITLE,
                            GOOD_DESC, GOOD_TAGS,
                            story_file="/tmp/لا-يوجد-ملف-قصة.txt")
        self.assertEqual(rc, 2)


class TestTitleLintCmd(unittest.TestCase):
    def test_single_title(self):
        rc, out = _capture(studio.cmd_title_lint, {},
                           title="النجار الأمين | قصة حقيقية",
                           thumb="أمانة تنجي صاحبها")
        self.assertEqual(rc, 0)
        self.assertIn("العنوان", out)

    def test_single_title_json_pure(self):
        rc, out = _capture(studio.cmd_title_lint, {},
                           title="امرأة تبكي في مكة", as_json=True)
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["title"], "امرأة تبكي في مكة")
        self.assertTrue(parsed["ok"])

    def test_titles_file_ranks_best_first(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "titles.txt",
                          "قصة مؤثرة!!!\nامرأة تبكي في مكة\n")
            rc, out = _capture(studio.cmd_title_lint, {},
                               titles_file=path)
            self.assertEqual(rc, 0)
            self.assertLess(out.index("امرأة تبكي في مكة"),
                            out.index("قصة مؤثرة!!!"))

    def test_titles_file_json_pure(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "titles.txt",
                          "قصة مؤثرة!!!\nامرأة تبكي في مكة\n")
            rc, out = _capture(studio.cmd_title_lint, {},
                               titles_file=path, as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(len(parsed), 2)
            self.assertEqual(parsed[0]["title"], "امرأة تبكي في مكة")

    def test_empty_title_returns_2(self):
        rc, _out = _capture(studio.cmd_title_lint, {}, title="   ")
        self.assertEqual(rc, 2)

    def test_no_title_no_file_returns_2(self):
        rc, _out = _capture(studio.cmd_title_lint, {})
        self.assertEqual(rc, 2)

    def test_missing_titles_file_returns_2(self):
        rc, _out = _capture(studio.cmd_title_lint, {},
                            titles_file="/tmp/لا-يوجد-عناوين.txt")
        self.assertEqual(rc, 2)

    def test_empty_titles_file_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "titles.txt", "\n\n")
            rc, _out = _capture(studio.cmd_title_lint, {},
                                titles_file=path)
            self.assertEqual(rc, 2)


class TestHookScoreCmd(unittest.TestCase):
    def test_single_hook(self):
        rc, out = _capture(studio.cmd_hook_score, {}, hook=GOOD_HOOK)
        self.assertEqual(rc, 0)
        self.assertIn("لوحة تقييم الهوك", out)
        self.assertIn("تقييم إرشادي", out)

    def test_single_hook_json_pure(self):
        rc, out = _capture(studio.cmd_hook_score, {}, hook=STRONG_HOOK,
                           as_json=True)
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["total"], 8)
        self.assertTrue(parsed[0]["top_two"])

    def test_hook_file_five_marks_top_two(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "hooks.txt", "\n".join(
                [WEAK_HOOK, GOOD_HOOK, AISHA_HOOK,
                 "عليه سريع يمين", STRONG_HOOK]) + "\n")
            rc, out = _capture(studio.cmd_hook_score, {},
                               hook_file=path)
            self.assertEqual(rc, 0)
            self.assertIn("من أفضل اثنين", out)
            self.assertLess(out.index(STRONG_HOOK),
                            out.index(WEAK_HOOK))

    def test_hook_file_with_story_file(self):
        with tempfile.TemporaryDirectory() as td:
            hooks = _write(td, "hooks.txt", STRONG_HOOK + "\n")
            story = _write(td, "story.txt",
                           "كان فيه راجل ظالم. سرق مال أخوه. أنكر "
                           "الوصية. هرب من القرية. العبرة أن الظلم "
                           "لا يدوم.")
            rc, out = _capture(studio.cmd_hook_score, {},
                               hook_file=hooks, story_file=story,
                               as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(parsed[0]["max"], 10)

    def test_no_hook_no_file_returns_2(self):
        rc, _out = _capture(studio.cmd_hook_score, {})
        self.assertEqual(rc, 2)

    def test_empty_hook_returns_2(self):
        rc, _out = _capture(studio.cmd_hook_score, {}, hook="   ")
        self.assertEqual(rc, 2)

    def test_empty_hook_file_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "hooks.txt", "\n\n")
            rc, _out = _capture(studio.cmd_hook_score, {},
                                hook_file=path)
            self.assertEqual(rc, 2)

    def test_missing_hook_file_returns_2(self):
        rc, _out = _capture(studio.cmd_hook_score, {},
                            hook_file="/tmp/لا-يوجد-هوكات.txt")
        self.assertEqual(rc, 2)

    def test_missing_story_file_returns_2(self):
        rc, _out = _capture(studio.cmd_hook_score, {}, hook=GOOD_HOOK,
                            story_file="/tmp/لا-يوجد-ملف-قصة.txt")
        self.assertEqual(rc, 2)


class TestViralRankCmd(unittest.TestCase):
    def _videos_file(self, td, videos=VIDEOS):
        return _write(td, "videos.json",
                      json.dumps(videos, ensure_ascii=False))

    def test_ranks_by_channel_median(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out = _capture(studio.cmd_viral_rank, {},
                               self._videos_file(td))
            self.assertEqual(rc, 0)
            self.assertIn("قصة حقيقية هزت المدينة", out)
            self.assertIn("16.00", out)

    def test_json_pure(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out = _capture(studio.cmd_viral_rank, {},
                               self._videos_file(td), as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(parsed["ranked"][0]["title"],
                             "قصة حقيقية هزت المدينة")
            self.assertEqual(parsed["ranked"][0]["multiplier"], 16.0)

    def test_top_limits_ranked(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out = _capture(studio.cmd_viral_rank, {},
                               self._videos_file(td), top=2,
                               as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(len(parsed["ranked"]), 2)

    def test_missing_file_returns_2(self):
        rc, _out = _capture(studio.cmd_viral_rank, {},
                            "/tmp/لا-يوجد-فيديوهات.json")
        self.assertEqual(rc, 2)

    def test_corrupt_json_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "videos.json", "{ليس json")
            rc, _out = _capture(studio.cmd_viral_rank, {}, path)
            self.assertEqual(rc, 2)

    def test_empty_list_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "videos.json", "[]")
            rc, _out = _capture(studio.cmd_viral_rank, {}, path)
            self.assertEqual(rc, 2)

    def test_non_list_json_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "videos.json", '{"channel": "x"}')
            rc, _out = _capture(studio.cmd_viral_rank, {}, path)
            self.assertEqual(rc, 2)


class TestRetentionReadCmd(unittest.TestCase):
    def test_healthy_csv(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "retention.csv", _csv(HEALTHY_POINTS))
            rc, out = _capture(studio.cmd_retention_read, {}, path)
            self.assertEqual(rc, 0)
            self.assertIn("سليم", out)

    def test_json_pure(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "retention.csv", _csv(HEALTHY_POINTS))
            rc, out = _capture(studio.cmd_retention_read, {}, path,
                               as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertTrue(parsed["healthy"])
            self.assertAlmostEqual(parsed["hook_leak_pct"], 12.0)

    def test_cliff_with_transcript(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "retention.csv", _csv(CLIFF_POINTS))
            srt = _write(td, "transcript.srt", SRT_TRANSCRIPT)
            rc, out = _capture(studio.cmd_retention_read, {}, path,
                               transcript_file=srt)
            self.assertEqual(rc, 0)
            self.assertIn("المنحدرات", out)
            self.assertIn("كان يُقال", out)

    def test_duration_override(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "retention.csv", _csv(HEALTHY_POINTS))
            rc, out = _capture(studio.cmd_retention_read, {}, path,
                               duration=60.0, as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertEqual(parsed["duration_seconds"], 60.0)

    def test_missing_file_returns_2(self):
        rc, _out = _capture(studio.cmd_retention_read, {},
                            "/tmp/لا-يوجد-احتفاظ.csv")
        self.assertEqual(rc, 2)

    def test_corrupt_csv_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "retention.csv", "hello\nworld\n")
            rc, _out = _capture(studio.cmd_retention_read, {}, path)
            self.assertEqual(rc, 2)

    def test_missing_transcript_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "retention.csv", _csv(HEALTHY_POINTS))
            rc, _out = _capture(studio.cmd_retention_read, {}, path,
                                transcript_file="/tmp/لا-يوجد-نص.txt")
            self.assertEqual(rc, 2)


class TestGrowthDispatch(unittest.TestCase):
    def test_help_lists_five_commands(self):
        studio_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        proc = subprocess.run(
            [sys.executable, "studio.py", "--help"],
            cwd=studio_dir, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0)
        for cmd in ("seo-check", "title-lint", "hook-score",
                    "viral-rank", "retention-read"):
            self.assertIn(cmd, proc.stdout)

    def test_help_ar_lists_five_commands(self):
        argv = ["studio.py", "help-ar"]
        with mock.patch.object(sys, "argv", argv):
            rc, out = _capture(studio.main)
        self.assertEqual(rc, 0)
        for cmd in ("seo-check", "title-lint", "hook-score",
                    "viral-rank", "retention-read"):
            self.assertIn(cmd, out)

    def test_dispatch_seo_check(self):
        argv = ["studio.py", "seo-check", "--title", GOOD_TITLE,
                "--description", GOOD_DESC, "--tags", GOOD_TAGS]
        with mock.patch.object(sys, "argv", argv):
            rc, out = _capture(studio.main)
        self.assertEqual(rc, 0)
        self.assertIn("سليم", out)

    def test_dispatch_seo_check_not_ok_returns_1(self):
        argv = ["studio.py", "seo-check", "--title", GOOD_TITLE,
                "--description", "", "--tags", GOOD_TAGS]
        with mock.patch.object(sys, "argv", argv):
            rc, _out = _capture(studio.main)
        self.assertEqual(rc, 1)

    def test_dispatch_viral_rank(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "videos.json",
                          json.dumps(VIDEOS, ensure_ascii=False))
            argv = ["studio.py", "viral-rank",
                    "--videos-file", path, "--top", "2"]
            with mock.patch.object(sys, "argv", argv):
                rc, out = _capture(studio.main)
            self.assertEqual(rc, 0)
            self.assertIn("قصة حقيقية هزت المدينة", out)


if __name__ == "__main__":
    unittest.main()
