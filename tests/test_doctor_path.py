#!/usr/bin/env python3
"""اختبارات فحص PATH في shell جديدة (بند 8 — AlphaCLI، جولة v0.1.41).

الفحص يطلق shell دخول نظيفة (بيئة فارغة إلا HOME، وPATH أدنى)
ويسألها أين تجد piper وffmpeg وomniroute — فيثبت أن تعديل
PATH يعمل بدل افتراضه. كل سيناريوهات الـshell تُحقن عبر
`runner` (بلا shell حقيقية) إلا اختبار الدخان الحي في الأسفل،
الذي يشغّل الـshell النظيفة فعلًا ويتحقق من بنية النتيجة فقط
(بلا ادعاء على ok — فالـCI قد لا يملك piper).
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import doctor as doctor_lib

CHECK_NAME = "PATH في shell جديدة (piper/ffmpeg/omniroute)"


def _canned_runner(found_map):
    """runner وهمي يرجع سطور `name=path` كما تطبعها الـshell."""
    lines = []
    for cmd in doctor_lib._CLEAN_SHELL_BINARIES:
        lines.append("%s=%s" % (cmd, found_map.get(cmd, "__MISSING__")))
    stdout = "\n".join(lines) + "\n"

    def run(script, timeout=15):
        return stdout, ""

    return run


class TestCleanShellPathCheck(unittest.TestCase):
    # مواضع متوقعة ثابتة للحقن — بلا اعتماد على آلة المطوّر
    # (فالـCI قد لا يملك piper أصلًا).
    EXPECTED = {"piper": "/usr/local/bin/piper",
                "ffmpeg": "/usr/bin/ffmpeg",
                "omniroute": "/usr/local/bin/omniroute"}

    def _check_with(self, found_map, expected=None):
        exp = dict(self.EXPECTED)
        if expected is not None:
            exp.update(expected)
        with mock.patch.object(
                doctor_lib, "_expected_binary_path",
                side_effect=lambda cmd: exp.get(cmd)):
            return doctor_lib._clean_shell_path_check(
                runner=_canned_runner(found_map))

    def test_clean_shell_finds_expected_binaries_passes(self):
        # الـshell النظيفة تجد الثنائي نفسه عبر مسار رابط رمزي
        # مختلف (مثال: ~/.local/bin/piper مقابل /usr/local/bin/piper)
        # — حل الروابط الرمزية يجعلها مطابقة فيمرّ الفحص.
        found = {cmd: os.path.realpath(path)
                 for cmd, path in self.EXPECTED.items()}
        result = self._check_with(found)
        self.assertEqual(result["name"], CHECK_NAME)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["level"], "warn")

    def test_clean_shell_without_path_misses_binaries_warns(self):
        # shell نظيفة بلا PATH (لا تجد شيئًا) → تحذير لا فشل،
        # مع رسالة عربية تقول ماذا يفعل المستخدم.
        result = self._check_with({})
        self.assertFalse(result["ok"])
        self.assertEqual(result["level"], "warn")
        self.assertIn("PATH", result["fix"])
        self.assertIn("bashrc", result["fix"])

    def test_other_binary_wins_warns(self):
        # ثنائي آخر يفوز بالاسم → تحذير يسمّي الفائز والمتوقع.
        found = {cmd: os.path.realpath(path)
                 for cmd, path in self.EXPECTED.items()}
        found["piper"] = "/tmp/other-piper/piper"
        result = self._check_with(found)
        self.assertFalse(result["ok"])
        self.assertEqual(result["level"], "warn")
        self.assertIn("/tmp/other-piper/piper", result["detail"])
        self.assertIn(self.EXPECTED["piper"], result["detail"])

    def test_shell_failure_is_warning_not_error(self):
        result = doctor_lib._clean_shell_path_check(
            runner=lambda script, timeout=15: (None, "لا توجد shell"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["level"], "warn")
        self.assertIn("لا توجد shell", result["detail"])

    def test_binary_not_installed_at_all_warns(self):
        found = {cmd: os.path.realpath(path)
                 for cmd, path in self.EXPECTED.items()}
        result = self._check_with(found, expected={"piper": None})
        self.assertFalse(result["ok"])
        self.assertEqual(result["level"], "warn")
        self.assertIn("غير مثبّت", result["detail"])

    def test_live_clean_shell_returns_well_formed_result(self):
        # دخان حي: الـshell النظيفة الحقيقية تعمل، والنتيجة
        # قاموس فحص سليم البنية (المستوى تحذير دائمًا).
        result = doctor_lib._clean_shell_path_check()
        self.assertEqual(result["name"], CHECK_NAME)
        self.assertEqual(result["level"], "warn")
        self.assertIn("ok", result)
        self.assertIn("detail", result)
        self.assertIn("fix", result)


class TestRunChecksCount(unittest.TestCase):
    def test_main_checks_now_27_including_path_check(self):
        checks = doctor_lib.run_checks({})
        self.assertEqual(len(checks), 27)
        names = [c["name"] for c in checks]
        self.assertIn(CHECK_NAME, names)

    def test_llm_checks_still_6(self):
        # قسم LLM لم يتغير — الفحص الجديد في doctor الأساسية فقط.
        self.assertEqual(len(doctor_lib.run_llm_checks()), 6)


if __name__ == "__main__":
    unittest.main()
