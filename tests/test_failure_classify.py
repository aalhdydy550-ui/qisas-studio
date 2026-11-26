#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات وحدة تصنيف الفشل (lib.failure_classify).

تغطي: اختبار واحد على الأقل لكل عائلة إشارات (بيئة/خارجية/كود)،
والمدخل الفارغ، وبلا إشارات، وتعادل الإشارات (بيئة داخل Traceback
يغلب الكود)، وحالة إشارتين من فئتين مختلفتين (الأولوية الموثقة:
بيئة ثم خارجية ثم كود). لا تقرأ أي ملف خارج شجرة المستودع.
"""
import unittest

from lib.failure_classify import classify_failure


class TestEmptyAndUnknown(unittest.TestCase):
    def test_empty_string(self):
        result = classify_failure("")
        self.assertEqual(result["class"], "unknown")
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(result["signals"], [])
        self.assertEqual(result["suggestion"],
                         "لا إشارة كافية — أرفق السجل الكامل")

    def test_whitespace_only(self):
        result = classify_failure("   \n  ")
        self.assertEqual(result["class"], "unknown")
        self.assertEqual(result["confidence"], "low")

    def test_none_input(self):
        result = classify_failure(None)
        self.assertEqual(result["class"], "unknown")
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(result["signals"], [])

    def test_no_signals(self):
        result = classify_failure("All tests passed, video rendered ok.")
        self.assertEqual(result["class"], "unknown")
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(result["signals"], [])


class TestEnvironmentSignals(unittest.TestCase):
    def test_pythonnousersite(self):
        result = classify_failure(
            "PYTHONNOUSERSITE=1 hides user site packages")
        self.assertEqual(result["class"], "environment")
        self.assertIn("pythonnousersite", result["signals"])
        self.assertEqual(
            result["suggestion"],
            "أعد البيئة حسب دروس ~/AGENTS.md (أدوات/روابط/حزم)")

    def test_module_not_found_piper(self):
        result = classify_failure(
            "ModuleNotFoundError: No module named 'piper'")
        self.assertEqual(result["class"], "environment")
        self.assertIn("module_not_found_piper", result["signals"])
        self.assertEqual(result["confidence"], "high")

    def test_module_not_found_anyio(self):
        result = classify_failure(
            "ModuleNotFoundError: No module named 'anyio'")
        self.assertEqual(result["class"], "environment")
        self.assertIn("module_not_found_anyio", result["signals"])

    def test_module_not_found_mcp(self):
        result = classify_failure(
            "ModuleNotFoundError: No module named 'mcp'")
        self.assertEqual(result["class"], "environment")
        self.assertIn("module_not_found_mcp", result["signals"])

    def test_module_not_found_pillow(self):
        result = classify_failure(
            "ModuleNotFoundError: No module named 'PIL'")
        self.assertEqual(result["class"], "environment")
        self.assertIn("module_not_found_pil", result["signals"])

    def test_module_not_found_generic(self):
        result = classify_failure(
            "ModuleNotFoundError: No module named 'requests'")
        self.assertEqual(result["class"], "environment")
        self.assertIn("module_not_found", result["signals"])
        self.assertEqual(result["confidence"], "medium")

    def test_melt_not_found(self):
        result = classify_failure("melt: not found")
        self.assertEqual(result["class"], "environment")
        self.assertIn("melt_missing", result["signals"])

    def test_melt_home_tools_missing(self):
        result = classify_failure("home-tools missing: melt")
        self.assertEqual(result["class"], "environment")
        self.assertIn("melt_missing", result["signals"])

    def test_melt_links_missing(self):
        result = classify_failure("links missing: melt")
        self.assertEqual(result["class"], "environment")
        self.assertIn("melt_missing", result["signals"])

    def test_apt_lock(self):
        result = classify_failure(
            "E: Could not get lock /var/lib/dpkg/lock-frontend")
        self.assertEqual(result["class"], "environment")
        self.assertIn("apt_lock", result["signals"])

    def test_dpkg_lock(self):
        result = classify_failure("dpkg lock: resource busy")
        self.assertEqual(result["class"], "environment")
        self.assertIn("apt_lock", result["signals"])

    def test_sigterm(self):
        result = classify_failure("process killed by SIGTERM")
        self.assertEqual(result["class"], "environment")
        self.assertIn("sigterm", result["signals"])

    def test_setup_env_timeout(self):
        result = classify_failure(
            "setup-env.sh timed out after 300 seconds")
        self.assertEqual(result["class"], "environment")
        self.assertIn("setup_env_timeout", result["signals"])

    def test_mesa_vulkan(self):
        result = classify_failure(
            "mesa-vulkan-drivers missing, lavapipe not found")
        self.assertEqual(result["class"], "environment")
        self.assertIn("mesa_vulkan", result["signals"])

    def test_tunnel_connection_failed(self):
        result = classify_failure("ERR_TUNNEL_CONNECTION_FAILED")
        self.assertEqual(result["class"], "environment")
        self.assertIn("tunnel_connection_failed", result["signals"])


class TestExternalSignals(unittest.TestCase):
    def test_http_429(self):
        result = classify_failure("HTTP 429 Too Many Requests")
        self.assertEqual(result["class"], "external")
        self.assertIn("http_429", result["signals"])
        self.assertEqual(
            result["suggestion"],
            "انتظر التهدئة ثم أعد المحاولة — لا تكرر فورًا ضد حاجز")

    def test_rate_limit(self):
        result = classify_failure("rate limit exceeded, retry later")
        self.assertEqual(result["class"], "external")
        self.assertIn("rate_limit", result["signals"])

    def test_provider_rate_limit_stop(self):
        result = classify_failure("provider_rate_limit_stop")
        self.assertEqual(result["class"], "external")
        self.assertIn("provider_rate_limit_stop", result["signals"])

    def test_connector_rate_limited(self):
        result = classify_failure("connector_rate_limited")
        self.assertEqual(result["class"], "external")
        self.assertIn("connector_rate_limited", result["signals"])

    def test_http_403_github(self):
        result = classify_failure(
            "HTTP 403 Forbidden from github.com api")
        self.assertEqual(result["class"], "external")
        self.assertIn("http_403", result["signals"])

    def test_http_403_facebook(self):
        result = classify_failure("403 from facebook.com")
        self.assertEqual(result["class"], "external")
        self.assertIn("http_403", result["signals"])

    def test_http_403_tiktok(self):
        result = classify_failure("HTTP 403 from tiktok.com")
        self.assertEqual(result["class"], "external")
        self.assertIn("http_403", result["signals"])

    def test_bot_barrier(self):
        result = classify_failure(
            "bot check blocked the automated click")
        self.assertEqual(result["class"], "external")
        self.assertIn("bot_barrier", result["signals"])

    def test_captcha(self):
        result = classify_failure("captcha challenge appeared")
        self.assertEqual(result["class"], "external")
        self.assertIn("captcha", result["signals"])

    def test_policy_denied(self):
        result = classify_failure("policy_denied in cloud browser")
        self.assertEqual(result["class"], "external")
        self.assertIn("policy_denied", result["signals"])

    def test_arabic_barrier(self):
        result = classify_failure("يبدو حاجز بوت يتجاهل الضغطات")
        self.assertEqual(result["class"], "external")
        self.assertIn("bot_barrier", result["signals"])

    def test_connection_timed_out_external(self):
        result = classify_failure(
            "Connection timed out to github.com")
        self.assertEqual(result["class"], "external")
        self.assertIn("connection_timed_out_external",
                      result["signals"])


class TestCodeSignals(unittest.TestCase):
    def test_assertion_error(self):
        result = classify_failure("AssertionError: expected 9, got 8")
        self.assertEqual(result["class"], "code")
        self.assertIn("assertion_error", result["signals"])
        self.assertEqual(result["suggestion"],
                         "راجع الاختبار الفاشل وأصلح الكود")

    def test_unittest_failures(self):
        result = classify_failure("FAILED (failures=2)")
        self.assertEqual(result["class"], "code")
        self.assertIn("unittest_failed", result["signals"])

    def test_unittest_errors(self):
        result = classify_failure("FAILED (errors=1)")
        self.assertEqual(result["class"], "code")
        self.assertIn("unittest_failed", result["signals"])

    def test_traceback_key_error_in_lib(self):
        result = classify_failure(
            "Traceback (most recent call last):\n"
            '  File "lib/check.py", line 10, in count\n'
            "KeyError: 'x'")
        self.assertEqual(result["class"], "code")
        self.assertIn("traceback_code_error", result["signals"])

    def test_traceback_type_error_in_tests(self):
        result = classify_failure(
            "Traceback (most recent call last):\n"
            '  File "tests/test_check.py", line 5, in test\n'
            "TypeError: bad type")
        self.assertEqual(result["class"], "code")
        self.assertIn("traceback_code_error", result["signals"])

    def test_traceback_value_error_in_studio(self):
        result = classify_failure(
            "Traceback (most recent call last):\n"
            '  File "studio.py", line 20, in main\n'
            "ValueError: bad value")
        self.assertEqual(result["class"], "code")
        self.assertIn("traceback_code_error", result["signals"])

    def test_syntax_error(self):
        result = classify_failure(
            "SyntaxError: invalid syntax in lib/check.py")
        self.assertEqual(result["class"], "code")
        self.assertIn("syntax_error", result["signals"])

    def test_check_8_8_fail(self):
        result = classify_failure("check 8/8 FAIL")
        self.assertEqual(result["class"], "code")
        self.assertIn("check_failed", result["signals"])

    def test_check_9_9_fail(self):
        result = classify_failure("check 9/9 FAIL")
        self.assertEqual(result["class"], "code")
        self.assertIn("check_failed", result["signals"])


class TestPriority(unittest.TestCase):
    def test_environment_inside_traceback_beats_code(self):
        # Traceback فيه ModuleNotFoundError لـpiper + KeyError من
        # lib/ — البيئة تغلب الكود حسب الأولوية الموثقة.
        result = classify_failure(
            "Traceback (most recent call last):\n"
            '  File "lib/check.py", line 10, in count\n'
            "ModuleNotFoundError: No module named 'piper'\n"
            "KeyError: 'x'")
        self.assertEqual(result["class"], "environment")
        self.assertIn("module_not_found_piper", result["signals"])

    def test_environment_beats_external(self):
        result = classify_failure(
            "HTTP 429 Too Many Requests\n"
            "ModuleNotFoundError: No module named 'piper'")
        self.assertEqual(result["class"], "environment")

    def test_external_beats_code(self):
        result = classify_failure(
            "HTTP 429 Too Many Requests\n"
            "AssertionError: expected 9, got 8")
        self.assertEqual(result["class"], "external")
        self.assertIn("http_429", result["signals"])

    def test_two_signals_same_class(self):
        result = classify_failure(
            "ModuleNotFoundError: No module named 'piper'\n"
            "home-tools missing: melt")
        self.assertEqual(result["class"], "environment")
        self.assertIn("module_not_found_piper", result["signals"])
        self.assertIn("melt_missing", result["signals"])
        self.assertEqual(result["confidence"], "high")


if __name__ == "__main__":
    unittest.main()
