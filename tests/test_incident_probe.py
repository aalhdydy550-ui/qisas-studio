#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات حلقة التحقيق في الحوادث (lib.incident_probe).

تعمل بـ `python3 -m unittest tests.test_incident_probe -v`
من مجلد studio. كل السياقات هنا اصطناعية تمامًا لأغراض
الاختبار فقط — لا تقرأ أي ملف خارج شجرة المستودع.
"""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import incident_probe
from lib.incident_probe import probe_incident


def _hypothesis(report, needle):
    """فرضية بعينها من التقرير حسب كلمة في نصها."""
    for hyp in report["hypotheses"]:
        if needle in hyp["hypothesis"]:
            return hyp
    raise AssertionError("لا فرضية تحوي %r" % needle)


class TestEnvironmentContext(unittest.TestCase):
    def test_missing_melt_supports_env_hypothesis(self):
        report = probe_incident({
            "title": "فشل التجميع بعد ريستارت",
            "failure_text": "melt غير موجود: الأمر melt غير معروف",
            "failure_class": "environment",
            "env_state": {"melt": False, "piper": True,
                          "pillow_ok": True, "mcp_ok": True,
                          "notes": ["أعيد تشغيل الجهاز الافتراضي"]},
        })
        env = _hypothesis(report, "بيئة")
        self.assertEqual(env["status"], "supported")
        self.assertTrue(env["evidence"])
        self.assertTrue(all(
            item["source"] == "env_state"
            for item in env["evidence"]))
        self.assertTrue(any("melt" in item["quote"]
                            for item in env["evidence"]))
        self.assertEqual(report["likely_root_cause"]["class"],
                         "environment")
        self.assertEqual(report["likely_root_cause"]["confidence"],
                         "high")
        self.assertIn("melt",
                      report["likely_root_cause"]["summary"])

    def test_missing_tool_without_class_still_supported(self):
        # أداة مفقودة في env_state وحدها تكفي — بلا تصنيف.
        report = probe_incident({
            "title": "فشل النطق",
            "failure_text": "piper غير موجود",
            "env_state": {"melt": True, "piper": False,
                          "pillow_ok": True, "mcp_ok": True},
        })
        env = _hypothesis(report, "بيئة")
        self.assertEqual(env["status"], "supported")
        self.assertEqual(report["likely_root_cause"]["class"],
                         "environment")

    def test_env_class_without_any_evidence_stays_untested(self):
        # تصنيف environment بلا أداة مفقودة وبلا ملاحظة وبلا
        # نص فشل: لا فرضية supported بلا دليل مقتبس.
        report = probe_incident({
            "title": "حادثة غامضة",
            "failure_class": "environment",
            "env_state": {"melt": True, "piper": True,
                          "pillow_ok": True, "mcp_ok": True},
        })
        env = _hypothesis(report, "بيئة")
        self.assertEqual(env["status"], "untested")
        self.assertEqual(env["evidence"], [])
        self.assertEqual(report["likely_root_cause"]["class"],
                         "unknown")


class TestCodeContext(unittest.TestCase):
    def test_matching_recent_change_supports_code_hypothesis(self):
        report = probe_incident({
            "title": "تضاعف عنوان الهوك",
            "failure_text": "فشل اختبار lib/hook_title.py: "
                            "تضاعف العنوان في الشريط",
            "failure_class": "code",
            "recent_changes": [
                "عدّلت lib/hook_title.py لإصلاح تضاعف العنوان",
                "حدّثت README.md",
            ],
        })
        code = _hypothesis(report, "كود")
        self.assertEqual(code["status"], "supported")
        sources = [item["source"] for item in code["evidence"]]
        self.assertIn("recent_changes", sources)
        self.assertIn("failure_text", sources)
        self.assertTrue(any("hook_title" in item["quote"]
                            for item in code["evidence"]))
        self.assertEqual(report["likely_root_cause"]["class"],
                         "code")
        self.assertEqual(report["likely_root_cause"]["confidence"],
                         "high")

    def test_unrelated_change_does_not_support_code(self):
        # تغيير في منطقة أخرى + كلمة «lib» وحدها لا تكفي.
        report = probe_incident({
            "title": "تضاعف عنوان الهوك",
            "failure_text": "فشل اختبار lib/hook_title.py: "
                            "تضاعف العنوان في الشريط",
            "failure_class": "code",
            "recent_changes": ["عدّلت lib/check.py لتحسين الفحص"],
        })
        code = _hypothesis(report, "كود")
        self.assertEqual(code["status"], "untested")
        self.assertEqual(report["likely_root_cause"]["class"],
                         "unknown")


class TestExternalContext(unittest.TestCase):
    def test_external_class_supports_external_hypothesis(self):
        report = probe_incident({
            "title": "رفض النشر في TikTok",
            "failure_text": "رفضت الخدمة الطلب: تجاوز حد المعدل",
            "failure_class": "external",
        })
        ext = _hypothesis(report, "خدمة خارجية")
        self.assertEqual(ext["status"], "supported")
        self.assertEqual(ext["evidence"][0]["source"],
                         "failure_text")
        self.assertEqual(report["likely_root_cause"]["class"],
                         "external")
        self.assertEqual(report["likely_root_cause"]["confidence"],
                         "high")
        self.assertEqual(_hypothesis(report, "بيئة")["status"],
                         "untested")
        self.assertEqual(_hypothesis(report, "كود")["status"],
                         "untested")

    def test_external_class_without_text_stays_untested(self):
        report = probe_incident({
            "title": "رفض بلا رسالة",
            "failure_class": "external",
        })
        ext = _hypothesis(report, "خدمة خارجية")
        self.assertEqual(ext["status"], "untested")
        self.assertEqual(report["likely_root_cause"]["class"],
                         "unknown")


class TestEmptyContext(unittest.TestCase):
    def test_empty_context_does_not_crash(self):
        report = probe_incident({})
        self.assertEqual(report["title"], "حادثة بلا عنوان")
        self.assertEqual(report["likely_root_cause"]["class"],
                         "unknown")
        self.assertEqual(report["likely_root_cause"]["confidence"],
                         "low")
        self.assertEqual(len(report["hypotheses"]), 3)
        for hyp in report["hypotheses"]:
            self.assertEqual(hyp["status"], "untested")
            self.assertEqual(hyp["evidence"], [])
        self.assertEqual(report["evidence"], [])
        self.assertTrue(report["next_steps"])

    def test_title_only_context(self):
        report = probe_incident({"title": "عطل بلا تفاصيل"})
        self.assertEqual(report["title"], "عطل بلا تفاصيل")
        self.assertEqual(report["likely_root_cause"]["class"],
                         "unknown")
        self.assertEqual(report["likely_root_cause"]["confidence"],
                         "low")
        for hyp in report["hypotheses"]:
            self.assertEqual(hyp["status"], "untested")


class TestQuotingAndInput(unittest.TestCase):
    def test_long_quote_is_truncated_to_200(self):
        long_text = "فشل " * 100  # 500 حرف.
        self.assertGreater(len(long_text), 200)
        report = probe_incident({
            "title": "فشل طويل",
            "failure_text": long_text,
            "failure_class": "external",
        })
        for item in report["evidence"]:
            self.assertLessEqual(len(item["quote"]), 200)
        for hyp in report["hypotheses"]:
            for item in hyp["evidence"]:
                self.assertLessEqual(len(item["quote"]), 200)
        ext = _hypothesis(report, "خدمة خارجية")
        self.assertEqual(ext["evidence"][0]["quote"],
                         long_text[:199] + "…")

    def test_input_is_not_modified(self):
        context = {
            "title": "فشل التجميع",
            "failure_text": "melt غير موجود بعد الريستارت",
            "failure_class": "environment",
            "last_test_failure": "test_check فشل",
            "recent_changes": ["حدّثت lib/check.py"],
            "env_state": {"melt": False, "piper": True,
                          "pillow_ok": True, "mcp_ok": True,
                          "notes": ["أعيد تشغيل الجهاز"]},
            "cron_logs": [{"cron": "qisas-top-shorts-daily",
                           "last_status": "failed"}],
        }
        before = copy.deepcopy(context)
        probe_incident(context)
        self.assertEqual(context, before)

    def test_failed_cron_is_collected_in_evidence(self):
        report = probe_incident({
            "title": "فشل النشر المجدول",
            "failure_text": "النشر المجدول لم يعمل",
            "cron_logs": [
                {"cron": "qisas-top-shorts-daily",
                 "last_status": "failed"},
                {"cron": "qisas-daily-0900", "last_status": "ok"},
            ],
        })
        cron_items = [item for item in report["evidence"]
                      if item["source"] == "cron_logs"]
        self.assertEqual(len(cron_items), 1)
        self.assertIn("qisas-top-shorts-daily",
                      cron_items[0]["quote"])

    def test_output_shape(self):
        report = probe_incident({
            "title": "حادثة اختبار",
            "failure_text": "melt غير موجود",
            "failure_class": "environment",
            "env_state": {"melt": False, "piper": True,
                          "pillow_ok": True, "mcp_ok": True},
        })
        self.assertEqual(set(report),
                         {"title", "likely_root_cause",
                          "hypotheses", "evidence", "next_steps"})
        self.assertEqual(set(report["likely_root_cause"]),
                         {"class", "summary", "confidence"})
        self.assertIn(report["likely_root_cause"]["confidence"],
                      ("high", "medium", "low"))
        for hyp in report["hypotheses"]:
            self.assertEqual(set(hyp),
                             {"hypothesis", "status", "evidence"})
            self.assertIn(hyp["status"],
                          ("supported", "refuted", "untested"))
            for item in hyp["evidence"]:
                self.assertEqual(set(item), {"source", "quote"})
                self.assertLessEqual(len(item["quote"]), 200)
        self.assertTrue(all(isinstance(step, str)
                            for step in report["next_steps"]))

    def test_no_supported_hypothesis_without_evidence(self):
        # كل فرضية supported يجب أن تحمل دليلًا مقتبسًا واحدًا
        # على الأقل — في كل السياقات المغطاة هنا.
        contexts = [
            {"title": "أ", "failure_class": "environment",
             "env_state": {"melt": False}},
            {"title": "ب", "failure_class": "external",
             "failure_text": "حد معدل"},
            {"title": "ج", "failure_class": "code",
             "failure_text": "فشل lib/hook_title.py",
             "recent_changes": ["عدّلت lib/hook_title.py"]},
            {},
            {"title": "د"},
        ]
        for ctx in contexts:
            report = probe_incident(ctx)
            for hyp in report["hypotheses"]:
                if hyp["status"] == "supported":
                    self.assertTrue(
                        hyp["evidence"],
                        "فرضية supported بلا دليل في %r" % (ctx,))


if __name__ == "__main__":
    unittest.main()
