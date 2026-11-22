#!/usr/bin/env python3
"""اختبارات الأمر اليومي الواحد (lib.daily).

تعمل بـ `python3 -m unittest discover -s tests -v`.
كل الكتابة في مجلدات مؤقتة — لا يُمس الطابور الحقيقي ولا
أي منشور، وبلا أي إنفاق Veo (الإنتاج والفحص والنشر كلها
دوال مزيفة محقونة).
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import daily

QUEUE_TEXT = """# طابور قصص

## في الانتظار

4. **العنزة المباركة** — تحتاج جزأين
5. **عجائب الصدقة** — منشور واحد
"""


def _cfg(tmpdir, balance=750):
    queue = os.path.join(tmpdir, "queue.md")
    with open(queue, "w", encoding="utf-8") as f:
        f.write(QUEUE_TEXT)
    return {
        "paths": {
            "queue_file": queue,
            "videos_dir": os.path.join(tmpdir, "videos"),
            "runs_dir": os.path.join(tmpdir, "runs"),
        },
        "publish": {"page_id": "1048148471706586",
                    "youtube_channel_id": "UCz5VeqN-eolCaCPGTpiWtJw"},
        "veo": {"balance_units": balance, "renews": "2026-12-13",
                "daily_cost_min": 100, "daily_cost_max": 140},
    }


def _ready(story):
    if story["number"] == 4:
        return True, "anza", "anza-part1", ""
    return False, None, None, "يحتاج تجهيز مشروع"


class TestDecidePath(unittest.TestCase):
    def test_morning_with_balance_is_veo(self):
        path, _reason = daily.decide_path("morning", 750)
        self.assertEqual(path, "veo")

    def test_morning_low_balance_falls_back(self):
        path, _reason = daily.decide_path("morning", 100)
        self.assertEqual(path, "openmontage")
        path, _reason = daily.decide_path("morning", 119)
        self.assertEqual(path, "openmontage")

    def test_morning_at_threshold_is_veo(self):
        path, _reason = daily.decide_path("morning", 120)
        self.assertEqual(path, "veo")

    def test_evening_always_openmontage(self):
        path, _reason = daily.decide_path("evening", 750)
        self.assertEqual(path, "openmontage")

    def test_unknown_balance_falls_back(self):
        path, _reason = daily.decide_path("morning", None)
        self.assertEqual(path, "openmontage")


class TestFirstComment(unittest.TestCase):
    def test_multi_part_comment(self):
        text = daily.build_first_comment(
            "العنزة", "الصبر يحوّل الأرض البور إلى جنة.",
            "لو كنت مكانه، كنت عملت إيه؟", 2)
        self.assertIn("الصبر يحوّل الأرض البور إلى جنة", text)
        self.assertIn("لو كنت مكانه، كنت عملت إيه؟", text)
        self.assertIn("الجزء الثاني بكرة 7 مساءً", text)

    def test_final_part_comment(self):
        text = daily.build_first_comment("قصة", "عبرة.", "سؤال؟", 1)
        self.assertIn("ابعتها في رسائل الصفحة", text)
        self.assertNotIn("الجزء الثاني", text)

    def test_story_parts(self):
        self.assertEqual(daily.story_parts("تحتاج 3 أجزاء"), 3)
        self.assertEqual(daily.story_parts("منشور واحد"), 1)
        self.assertEqual(daily.story_parts(""), 1)


class TestPlan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg = _cfg(self.tmp)

    def test_morning_plan_dry_run(self):
        plan = daily.plan_daily(self.cfg, "morning",
                                ready_fn=_ready)
        self.assertEqual(plan["story"]["title"], "العنزة المباركة")
        self.assertEqual(plan["story"]["parts"], 2)
        self.assertEqual(plan["path"], "veo")
        self.assertTrue(plan["ready"])
        self.assertEqual(plan["project"], "anza-part1")
        self.assertIn("الجزء الثاني بكرة 7 مساءً",
                      plan["first_comment"])
        self.assertIn("#قصص_وعبر", plan["caption"])
        self.assertIsNone(plan["fb_argv"])  # بلا فيديو جاهز بعد
        self.assertIsNone(plan["yt_payload"])

    def test_evening_plan_is_openmontage(self):
        plan = daily.plan_daily(self.cfg, "evening",
                                ready_fn=_ready)
        self.assertEqual(plan["path"], "openmontage")

    def test_low_balance_morning_falls_back(self):
        cfg = _cfg(self.tmp, balance=50)
        plan = daily.plan_daily(cfg, "morning", ready_fn=_ready)
        self.assertEqual(plan["path"], "openmontage")

    def test_ready_video_builds_payloads(self):
        videos = os.path.join(self.tmp, "videos")
        os.makedirs(videos, exist_ok=True)
        video = os.path.join(videos, "ready.mp4")
        with open(video, "wb") as f:
            f.write(b"fake")
        plan = daily.plan_daily(self.cfg, "morning", video=video,
                                ready_fn=_ready)
        self.assertTrue(plan["video_ready"])
        self.assertIsNotNone(plan["fb_argv"])
        self.assertIn("pages", plan["fb_argv"])
        self.assertIsNotNone(plan["yt_payload"])
        self.assertEqual(plan["yt_payload"]["method"],
                         "youtube.videos.insert")

    def test_empty_queue_raises(self):
        cfg = _cfg(self.tmp)
        with open(cfg["paths"]["queue_file"], "w",
                  encoding="utf-8") as f:
            f.write("# طابور\n\n## في الانتظار\n\n")
        with self.assertRaises(daily.DailyError):
            daily.plan_daily(cfg, "morning", ready_fn=_ready)

    def test_bad_slot_raises(self):
        with self.assertRaises(daily.DailyError):
            daily.plan_daily(self.cfg, "noon", ready_fn=_ready)


class TestExecute(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cfg = _cfg(self.tmp)
        self.runs_dir = self.cfg["paths"]["runs_dir"]
        self.calls = []

    def _fakes(self, produce_rc=0, check_passed=True, publish_rc=0):
        def produce_fn(cfg, slug, project, out):
            self.calls.append(("produce", slug, project))
            return produce_rc

        def check_fn(video):
            self.calls.append(("check", video))
            return {"passed": check_passed, "checks": []}

        def thumbnail_fn(video, hook, out):
            self.calls.append(("thumbnail", video))
            return out

        def publish_fn(cfg, video, title, caption, thumb):
            self.calls.append(("publish", video))
            return publish_rc

        return produce_fn, check_fn, thumbnail_fn, publish_fn

    def test_execute_openmontage_full_flow(self):
        cfg = _cfg(self.tmp, balance=50)  # بديل OpenMontage
        plan = daily.plan_daily(cfg, "morning", ready_fn=_ready)
        fns = self._fakes()
        rc, result = daily.execute_daily(cfg, plan, *fns,
                                         runs_dir=self.runs_dir)
        self.assertEqual(rc, 0)
        self.assertEqual(result["steps"]["produce"]["status"], "done")
        self.assertTrue(result["steps"]["check"]["passed"])
        self.assertIn("thumbnail", result["steps"])
        self.assertEqual(result["steps"]["publish"]["status"], "done")
        self.assertIn("first_comment", result["steps"])
        self.assertEqual([c[0] for c in self.calls],
                         ["produce", "check", "thumbnail", "publish"])
        saved = [f for f in os.listdir(self.runs_dir)
                 if f.startswith("daily-")]
        self.assertEqual(len(saved), 1)
        with open(os.path.join(self.runs_dir, saved[0]),
                  encoding="utf-8") as f:
            self.assertEqual(json.load(f)["slot"], "morning")

    def test_execute_veo_without_video_stops(self):
        plan = daily.plan_daily(self.cfg, "morning", ready_fn=_ready)
        self.assertEqual(plan["path"], "veo")
        fns = self._fakes()
        rc, result = daily.execute_daily(self.cfg, plan, *fns,
                                         runs_dir=self.runs_dir)
        self.assertEqual(rc, 1)
        self.assertEqual(result["steps"]["produce"]["status"],
                         "needs-flow")
        self.assertEqual(self.calls, [])  # لم يُستدعَ شيء

    def test_execute_check_failure_stops_before_publish(self):
        cfg = _cfg(self.tmp, balance=50)
        plan = daily.plan_daily(cfg, "morning", ready_fn=_ready)
        fns = self._fakes(check_passed=False)
        rc, result = daily.execute_daily(cfg, plan, *fns,
                                         runs_dir=self.runs_dir)
        self.assertEqual(rc, 1)
        self.assertFalse(result["steps"]["check"]["passed"])
        self.assertNotIn("publish", result["steps"])
        self.assertEqual([c[0] for c in self.calls],
                         ["produce", "check"])


if __name__ == "__main__":
    unittest.main()
