#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات lib/channel_audit.py — تدقيق القناة بإصلاح واحد (v0.1.57).

كل البيانات تركيبية وموسومة بذلك في التعليقات — ليست أرقامًا حقيقية
للقناة. الهوكات المستخدمة هنا قُيست فعليًا بالمقياس القائم:
القوية 6/9، والضعيفة 2-4/9 (انظر lib/dna.py::score_hook).
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
from lib.channel_audit import audit_channel, format_report, to_json_dict
from lib.retention_read import RetentionError


def _capture(fn, *args, **kwargs):
    buf = io.StringIO()
    with mock.patch("sys.stdout", buf):
        rc = fn(*args, **kwargs)
    return rc, buf.getvalue()


def _write(td, name, text):
    path = os.path.join(td, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path

# 10 عناوين تركيبية متنوعة الصيغ (5 صيغ × 2).
HEALTHY_TITLES = [
    "عائشة الأرملة | الجزء 1 من 2 | قصة حقيقية",
    "النجار الأمين | قصة حقيقية",
    "هل تصدق ما فعله هذا الفقير؟",
    "3 دروس من قصة التاجر الأمين",
    "السر الذي غيّر حياة الحطاب",
    "منقشة الرغيف | الجزء 2 من 2 | قصة حقيقية",
    "التاجر الصادق | قصة حقيقية",
    "ماذا فعلت الأرملة حين طردتها حماتها؟",
    "5 أخطاء يقع فيها الكريم",
    "الحقيقة التي أبكت القاضي",
]

# نصوص مصغرات تركيبية قصيرة (≤3 كلمات) بلا تكرار لعناوينها.
HEALTHY_THUMBS = [
    "طردتها حماتها",
    "أمانة تنقذ صاحبها",
    "أعاد المال كاملًا",
    "حكمة تغيّر المصير",
    "انقلاب غير متوقع",
    "النهاية صادمة",
    "صدق ينجي صاحبه",
    "ظلم ثم عوض",
    "احذر هذه الأفعال",
    "دموع في المحكمة",
]

# هوكات قوية (6/9 بالمقياس القائم) — أسطر أولى تركيبية.
STRONG_HOOKS = [
    "هل تصدق أن فقيرًا أعاد 20 ألف ريال لصاحبها؟",
    "هل تصدق أن رجلًا فقيرًا وجد 20 ألف ريال وأعادها لصاحبها؟",
    "ماذا حدث حين أعاد التاجر 50 ألف جنيه إلى صاحبها؟",
]

# هوكات ضعيفة (2-4/9 بالمقياس القائم) — أسطر أولى تركيبية.
WEAK_HOOKS = [
    "قالوا بتحفر قبرها… طلعت بتحفر جنة بناتها!",
    "رجل وجد حقيبة فيها مسدس فضي في الزبالة",
    "باعت بقرتها ووزعت البذور على الفقراء",
]

# 10 أيام متتالية — إيقاع ثابت.
STEADY_DATES = ["2026-11-%02d" % d for d in range(1, 11)]

# دفعة (3 رفعات في 3 أيام) ثم صمت 20 يومًا.
BURST_SILENCE_DATES = ["2026-11-01", "2026-11-02", "2026-11-03",
                        "2026-11-23"]

# تصدير احتفاظ تركيبي: تسرب هوك 30% (غير صحي)، بلا منحدرات ولا انزلاق.
LEAK_CSV = """time,retention
0,100
5,94
10,88
15,82
20,76
25,72
30,70
35,70
40,69
45,69
50,68
55,68
60,68
"""

# تصدير احتفاظ تركيبي سليم: تسرب 18%، بلا منحدرات ولا انزلاق.
HEALTHY_CSV = """time,retention
0,100
5,96
10,93
15,90
20,87
25,84
30,82
35,81
40,81
45,80
50,80
55,79
60,79
"""

BAD_META = {
    "title": "النجار الأمين | قصة حقيقية",
    "description": "اشترك في القناة وفعل الجرس وشارك الفيديو مع أصدقائك.",
    "tags": ["قصص وعبر", "قصص واقعية"],
}


class TestHealthyChannel(unittest.TestCase):
    def test_healthy_channel_has_no_critical_fix(self):
        result = audit_channel(
            HEALTHY_TITLES, hooks=STRONG_HOOKS,
            thumb_texts=HEALTHY_THUMBS, upload_dates=STEADY_DATES)
        self.assertIsNone(result["fix"])
        self.assertGreaterEqual(len(result["working"]), 2)
        self.assertIn("لا تصلح ما يعمل", result["not_yet"]["text"])

    def test_healthy_working_items_are_specific(self):
        result = audit_channel(
            HEALTHY_TITLES, hooks=STRONG_HOOKS,
            thumb_texts=HEALTHY_THUMBS, upload_dates=STEADY_DATES)
        joined = " ".join(result["working"])
        self.assertIn("6/9", joined)
        self.assertIn("5 صيغ", joined)
        self.assertIn("ثابت", joined)

    def test_missing_optionals_are_not_assessed_not_guessed(self):
        result = audit_channel(HEALTHY_TITLES)
        self.assertIsNone(result["sections"]["hooks"])
        self.assertIsNone(result["sections"]["rhythm"])
        self.assertIsNone(result["sections"]["retention"])
        self.assertIsNone(result["sections"]["seo"])
        self.assertIsNone(result["fix"])
        report = format_report(result)
        self.assertIn("لم تُقيَّم", report)


class TestOneFixPriority(unittest.TestCase):
    def test_bad_thumbs_beat_weak_hooks(self):
        thumbs = list(HEALTHY_THUMBS)
        thumbs[0] = "عائشة الأرملة الجزء 1 من 2"
        thumbs[1] = "النجار الأمين قصة حقيقية"
        thumbs[2] = "هل تصدق ما فعله هذا الفقير"
        result = audit_channel(
            HEALTHY_TITLES, hooks=WEAK_HOOKS,
            thumb_texts=thumbs, upload_dates=STEADY_DATES)
        self.assertEqual(result["fix"]["section"], "thumbnails")
        self.assertGreaterEqual(
            result["sections"]["titles"]["bad_thumbs"], 3)

    def test_weak_hooks_are_the_fix(self):
        result = audit_channel(
            HEALTHY_TITLES, hooks=WEAK_HOOKS,
            thumb_texts=HEALTHY_THUMBS, upload_dates=STEADY_DATES)
        self.assertEqual(result["fix"]["section"], "hooks")
        self.assertIn("2/9", result["fix"]["title"])
        self.assertIn("لا توسّع النشر", result["not_yet"]["text"])

    def test_same_shape_titles_are_the_fix(self):
        titles = [
            "النجار الأمين | قصة حقيقية",
            "التاجر الصادق | قصة حقيقية",
            "الحطاب الفقير | قصة حقيقية",
            "الأرملة الصابرة | قصة حقيقية",
            "الخباز الكريم | قصة حقيقية",
            "الصياد الأمين | قصة حقيقية",
            "الجار الطيب | قصة حقيقية",
            "المعلم الحكيم | قصة حقيقية",
            "هل تصدق ما فعله هذا الفقير؟",
            "3 دروس من قصة التاجر الأمين",
        ]
        result = audit_channel(titles)
        self.assertEqual(result["fix"]["section"], "titles")
        self.assertTrue(result["sections"]["titles"]["same_shape"])
        self.assertEqual(
            result["sections"]["titles"]["top_format_share"], 0.8)

    def test_burst_then_silence_is_the_fix(self):
        result = audit_channel(
            HEALTHY_TITLES, hooks=STRONG_HOOKS,
            thumb_texts=HEALTHY_THUMBS,
            upload_dates=BURST_SILENCE_DATES)
        self.assertEqual(result["fix"]["section"], "rhythm")
        self.assertTrue(result["sections"]["rhythm"]["burst_silence"])
        self.assertEqual(
            result["sections"]["rhythm"]["longest_gap_days"], 20)

    def test_retention_hook_leak_is_the_fix(self):
        result = audit_channel(
            HEALTHY_TITLES, hooks=STRONG_HOOKS,
            thumb_texts=HEALTHY_THUMBS, upload_dates=STEADY_DATES,
            retention_csv=LEAK_CSV)
        self.assertEqual(result["fix"]["section"], "hooks")
        self.assertEqual(
            result["sections"]["retention"]["verdict"], "تسرب الهوك")
        self.assertEqual(
            result["sections"]["retention"]["hook_leak_pct"], 30.0)

    def test_healthy_retention_is_packaging_not_a_fix(self):
        result = audit_channel(
            HEALTHY_TITLES, hooks=STRONG_HOOKS,
            thumb_texts=HEALTHY_THUMBS, upload_dates=STEADY_DATES,
            retention_csv=HEALTHY_CSV)
        self.assertIsNone(result["fix"])
        ret = result["sections"]["retention"]
        self.assertEqual(ret["verdict"], "سليم")
        self.assertIsNotNone(ret["packaging_note"])

    def test_bad_seo_is_the_fix_when_nothing_else(self):
        result = audit_channel(
            HEALTHY_TITLES, hooks=STRONG_HOOKS,
            thumb_texts=HEALTHY_THUMBS, upload_dates=STEADY_DATES,
            latest_meta=BAD_META)
        self.assertFalse(result["sections"]["seo"]["ok"])
        self.assertEqual(result["fix"]["section"], "seo")


class TestInputErrors(unittest.TestCase):
    def test_empty_titles(self):
        with self.assertRaises(ValueError):
            audit_channel([])

    def test_titles_not_a_list(self):
        with self.assertRaises(ValueError):
            audit_channel("عنوان واحد")

    def test_empty_title_inside_list(self):
        with self.assertRaises(ValueError):
            audit_channel(["النجار الأمين", "  "])

    def test_bad_upload_date(self):
        with self.assertRaises(ValueError):
            audit_channel(HEALTHY_TITLES,
                          upload_dates=["2026-13-01"])

    def test_bad_retention_csv(self):
        with self.assertRaises(RetentionError):
            audit_channel(HEALTHY_TITLES, retention_csv="hello\nworld\n")

    def test_bad_latest_meta(self):
        with self.assertRaises(ValueError):
            audit_channel(HEALTHY_TITLES, latest_meta={"title": "  "})


class TestReportAndJson(unittest.TestCase):
    def test_format_report_contains_fix_working_not_yet(self):
        result = audit_channel(HEALTHY_TITLES, hooks=WEAK_HOOKS)
        report = format_report(result)
        self.assertIn("الإصلاح:", report)
        self.assertIn("أضعف هوك", report)
        self.assertIn("ما يعمل فعلًا:", report)
        self.assertIn("ما لا يُفعل بعد:", report)
        self.assertIn("الهوكات:", report)
        self.assertIn("العناوين (10):", report)

    def test_result_is_json_serializable(self):
        result = audit_channel(
            HEALTHY_TITLES, hooks=STRONG_HOOKS,
            thumb_texts=HEALTHY_THUMBS, upload_dates=STEADY_DATES,
            retention_csv=HEALTHY_CSV, latest_meta={
                "title": "النجار الأمين | قصة حقيقية",
                "description": "قصة حقيقية عن نجار أمين أعاد الأمانة "
                               "لصاحبها فعوّضه الله.",
                "tags": ["قصص وعبر", "قصص واقعية"]})
        text = json.dumps(to_json_dict(result), ensure_ascii=False)
        parsed = json.loads(text)
        self.assertEqual(parsed["sections"]["titles"]["count"], 10)
        self.assertEqual(parsed["sections"]["retention"]["verdict"], "سليم")


class TestChannelAuditCmd(unittest.TestCase):
    def _titles_file(self, td):
        return _write(td, "titles.txt", "\n".join(HEALTHY_TITLES) + "\n")

    def test_cmd_success(self):
        with tempfile.TemporaryDirectory() as td:
            titles = self._titles_file(td)
            hooks = _write(td, "hooks.txt", "\n".join(STRONG_HOOKS) + "\n")
            dates = _write(td, "dates.txt", "\n".join(STEADY_DATES) + "\n")
            rc, out = _capture(studio.cmd_channel_audit, {}, titles,
                               hooks_file=hooks, dates_file=dates)
            self.assertEqual(rc, 0)
            self.assertIn("الإصلاح:", out)
            self.assertIn("ما يعمل فعلًا:", out)

    def test_cmd_json_pure(self):
        with tempfile.TemporaryDirectory() as td:
            titles = self._titles_file(td)
            rc, out = _capture(studio.cmd_channel_audit, {}, titles,
                               as_json=True)
            self.assertEqual(rc, 0)
            parsed = json.loads(out)
            self.assertIsNone(parsed["fix"])
            self.assertEqual(
                parsed["sections"]["titles"]["count"], 10)

    def test_cmd_with_retention_csv(self):
        with tempfile.TemporaryDirectory() as td:
            titles = self._titles_file(td)
            csv = _write(td, "retention.csv", LEAK_CSV)
            rc, out = _capture(studio.cmd_channel_audit, {}, titles,
                               retention_csv=csv)
            self.assertEqual(rc, 0)
            self.assertIn("تسرب الهوك", out)

    def test_cmd_missing_titles_file_returns_2(self):
        rc, _out = _capture(studio.cmd_channel_audit, {},
                            "/tmp/لا-يوجد-عناوين.txt")
        self.assertEqual(rc, 2)

    def test_cmd_empty_titles_file_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write(td, "titles.txt", "\n\n")
            rc, _out = _capture(studio.cmd_channel_audit, {}, path)
            self.assertEqual(rc, 2)

    def test_cmd_partial_meta_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            titles = self._titles_file(td)
            rc, _out = _capture(studio.cmd_channel_audit, {}, titles,
                                title="النجار الأمين | قصة حقيقية")
            self.assertEqual(rc, 2)

    def test_cmd_bad_dates_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            titles = self._titles_file(td)
            dates = _write(td, "dates.txt", "2026-13-01\n")
            rc, _out = _capture(studio.cmd_channel_audit, {}, titles,
                                dates_file=dates)
            self.assertEqual(rc, 2)

    def test_dispatch_channel_audit(self):
        with tempfile.TemporaryDirectory() as td:
            titles = self._titles_file(td)
            argv = ["studio.py", "channel-audit",
                    "--titles-file", titles]
            with mock.patch.object(sys, "argv", argv):
                rc, out = _capture(studio.main)
            self.assertEqual(rc, 0)
            self.assertIn("الإصلاح:", out)

    def test_help_lists_channel_audit(self):
        studio_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        proc = subprocess.run(
            [sys.executable, "studio.py", "--help"],
            cwd=studio_dir, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("channel-audit", proc.stdout)

    def test_help_ar_lists_channel_audit(self):
        argv = ["studio.py", "help-ar"]
        with mock.patch.object(sys, "argv", argv):
            rc, out = _capture(studio.main)
        self.assertEqual(rc, 0)
        self.assertIn("channel-audit", out)


if __name__ == "__main__":
    unittest.main()
