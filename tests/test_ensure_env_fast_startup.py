#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات انحدار لبطء بدء تشغيل الاستوديو (عيب 2026-11-26:
`studio.py version` استغرق 323 ثانية).

السبب الجذري: `_ensure_environment` كانت تشغّل `setup-env.sh`
بشكل متزامن بمهلة 300 ثانية لمجرد غياب ملف خدمة systemd، حتى
لو كانت كل الأدوات موجودة — وبعد ريستارت VM ملف الخدمة غائب
دائمًا، وسكربت الاستعادة نفسه قد ينتظر قفل apt حتى 240 ثانية
+ `apt-get update/install` مع محاولات، فينتهي بمهلة 300 ثانية.

السلوك الجديد المثبَّت هنا (بلا شبكة وبلا تنفيذ فعلي لسكربتات
الإصلاح — `subprocess.run` و`subprocess.Popen` يُستبدلان بمحاكاة):
1. أمر قراءة فقط (`version`) لا يطلق أي استرداد متزامن أبدًا،
   ولا استردادًا في الخلفية، ولا فحص أدوات الحماية ولا خادم
   OmniRoute — تحذير على stderr فقط، وstdout يبقى نظيفًا.
2. غياب ملف الخدمة وحده (كل الأدوات موجودة) يطلق الاستعادة
   في الخلفية (Popen) بدل حظر التشغيل 300 ثانية — خطوة 0 من
   سكربت الاستعادة نفسه تعيد تثبيت ملف الخدمة من نسخة الـhome،
   فالإصلاح الذاتي يبقى ويحدث خلال ثوانٍ بلا حظر.
3. أداة غائبة فعلًا ما زالت تطلق الاسترداد المتزامن (مهلة 300
   ثانية معلنة في التحذير) — الإصلاح الذاتي للأوامر الإنتاجية
   محفوظ كما هو.
4. فحص الأمان `_script_safe_to_run` ما زال يرفض سكربتًا غير
   آمن (قابل للكتابة من الجميع / مالك غريب) في المسارين
   المتزامن والخلفي معًا.

ملاحظة تسلسل: هذا الملف كُتب قبل تطبيق الإصلاح في studio.py،
فاختبارات السلوك الجديد تفشل على الكود القديم عمدًا حتى تُطبَّق
التغييرات في `_ensure_environment` وموضع استدعائها في `main()`.
"""
import contextlib
import io
import os
import subprocess
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio


class _GuardHarness:
    """تشغيل `_ensure_environment` بمحاكاة كاملة: لا سكربتات
    حقيقية ولا خادم ولا شبكة."""

    def __init__(self, test, which=None, isfile=None, safe=True):
        self.test = test
        self.which = which
        self.isfile = isfile
        self.safe = safe

    def run(self, read_only=False):
        env = {"PATH": "/usr/bin:/bin"}
        stderr = io.StringIO()
        stdout = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch("shutil.which",
                           side_effect=(lambda c: "/usr/bin/%s" % c)
                           if self.which is None else self.which), \
                mock.patch("os.path.isfile",
                           side_effect=self.isfile), \
                mock.patch.object(studio, "_script_safe_to_run",
                                  return_value=self.safe), \
                mock.patch.object(studio.subprocess, "run") as run, \
                mock.patch.object(studio.subprocess, "Popen") as popen, \
                mock.patch.object(studio, "_omniroute_server_up",
                                  return_value=True), \
                mock.patch.object(studio, "_ensure_protection_tools") \
                as protect, \
                mock.patch.object(studio, "_ensure_omniroute_server") \
                as omni, \
                contextlib.redirect_stderr(stderr), \
                contextlib.redirect_stdout(stdout):
            started = time.monotonic()
            studio._ensure_environment(read_only=read_only)
            elapsed = time.monotonic() - started
        return {"run": run, "popen": popen, "protect": protect,
                "omni": omni, "stderr": stderr.getvalue(),
                "stdout": stdout.getvalue(), "elapsed": elapsed}


def _all_present_isfile(path):
    return True


def _unit_missing_isfile(path):
    return path != studio._UNIT_FILE


class TestReadOnlyVersionNeverBlocks(unittest.TestCase):
    """(ب) أوامر القراءة فقط لا تحظر أبدًا."""

    def test_readonly_unit_missing_no_restore_at_all(self):
        """version مع ملف خدمة غائب وأدوات موجودة يرجع سريعًا:
        لا استرداد متزامن ولا خلفي، وتحذير على stderr فقط."""
        res = _GuardHarness(self, isfile=_unit_missing_isfile).run(
            read_only=True)
        res["run"].assert_not_called()
        res["popen"].assert_not_called()
        self.assertIn("ملف الخدمة", res["stderr"])
        self.assertEqual(res["stdout"], "")
        self.assertLess(res["elapsed"], 5.0)

    def test_readonly_tool_missing_no_sync_restore(self):
        """version مع أداة غائبة فعلًا: تحذير فقط، بلا انتظار
        متزامن وبلا إطلاق خلفي."""
        res = _GuardHarness(self, which=lambda c: None,
                            isfile=lambda p: True).run(read_only=True)
        res["run"].assert_not_called()
        res["popen"].assert_not_called()
        self.assertIn("غائبة", res["stderr"])
        self.assertEqual(res["stdout"], "")

    def test_readonly_skips_protection_and_omniroute(self):
        """version لا يحتاج أدوات حماية ولا خادم OmniRoute،
        فلا يُستدعيان أصلًا في مسار القراءة فقط."""
        res = _GuardHarness(self, isfile=_all_present_isfile).run(
            read_only=True)
        res["protect"].assert_not_called()
        res["omni"].assert_not_called()

    def test_non_readonly_still_runs_protection_and_omniroute(self):
        """الأوامر الإنتاجية مع بيئة سليمة ما زالت تمر على
        فحص الحماية والخادم كما قبل."""
        res = _GuardHarness(self, isfile=_all_present_isfile).run(
            read_only=False)
        res["protect"].assert_called_once()
        res["omni"].assert_called_once()


class TestUnitMissingOnlyGoesBackground(unittest.TestCase):
    """(أ) غياب ملف الخدمة وحده لا يحظر التشغيل."""

    def test_unit_missing_only_background_restore(self):
        """كل الأدوات موجودة وملف الخدمة غائب: الاستعادة تُطلق
        في الخلفية (Popen) ولا يوجد أي استدعاء متزامن."""
        res = _GuardHarness(self, isfile=_unit_missing_isfile).run(
            read_only=False)
        res["run"].assert_not_called()
        res["popen"].assert_called_once()
        args, kwargs = res["popen"].call_args
        self.assertEqual(args[0][-1], studio._SETUP_ENV_SCRIPT)
        self.assertEqual(args[0][0], "/bin/bash")
        self.assertTrue(kwargs.get("start_new_session"))
        self.assertEqual(kwargs.get("stdout"), subprocess.DEVNULL)
        self.assertIn("الخلفية", res["stderr"])
        self.assertEqual(res["stdout"], "")
        self.assertLess(res["elapsed"], 5.0)

    def test_all_present_nothing_launched(self):
        """بيئة سليمة تمامًا: لا استرداد متزامن ولا خلفي."""
        res = _GuardHarness(self, isfile=_all_present_isfile).run(
            read_only=False)
        res["run"].assert_not_called()
        res["popen"].assert_not_called()


class TestRealMissingToolStillRestoresSynchronously(unittest.TestCase):
    """الإصلاح الذاتي للأدوات الغائبة فعلًا محفوظ."""

    def test_tool_missing_still_sync_restore(self):
        """أداة غائبة فعلًا في أمر إنتاجي: الاسترداد المتزامن
        يُطلق مرة واحدة بمهلة 300 ثانية معلنة، وبلا إطلاق خلفي."""
        res = _GuardHarness(self, which=lambda c: None,
                            isfile=lambda p: True).run(read_only=False)
        res["run"].assert_called_once()
        args, kwargs = res["run"].call_args
        self.assertIn("setup-env.sh", args[0][-1])
        self.assertEqual(kwargs["timeout"], 300)
        self.assertEqual(kwargs["env"].get("STUDIO_ENV_RESTORED"), "1")
        res["popen"].assert_not_called()
        self.assertIn("300", res["stderr"])

    def test_missing_tool_and_no_script_warns_only(self):
        """أداة غائبة ولا يوجد سكربت استعادة: تحذير فقط وبلا
        استثناء وبلا أي إطلاق."""
        res = _GuardHarness(self, which=lambda c: None,
                            isfile=lambda p: False).run(read_only=False)
        res["run"].assert_not_called()
        res["popen"].assert_not_called()


class TestUnsafeScriptStillRefused(unittest.TestCase):
    """فحص الأمان لم يُمسّ: سكربت غير آمن لا يُنفَّذ أبدًا."""

    def test_unsafe_script_blocks_sync_restore(self):
        res = _GuardHarness(self, which=lambda c: None,
                            isfile=lambda p: True, safe=False).run(
            read_only=False)
        res["run"].assert_not_called()
        res["popen"].assert_not_called()
        self.assertIn("غير آمن", res["stderr"])

    def test_unsafe_script_blocks_background_restore(self):
        res = _GuardHarness(self, isfile=_unit_missing_isfile,
                            safe=False).run(read_only=False)
        res["run"].assert_not_called()
        res["popen"].assert_not_called()
        self.assertIn("غير آمن", res["stderr"])


class TestMainPassesReadOnlyForVersion(unittest.TestCase):
    """موضع الاستدعاء: `main()` يمرر read_only لأمر version فقط."""

    def test_main_version_calls_guard_read_only(self):
        with mock.patch.object(studio, "_ensure_environment") as guard, \
                mock.patch.object(sys, "argv",
                                  ["studio.py", "version"]), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(studio.main(), 0)
        guard.assert_called_once()
        _, kwargs = guard.call_args
        self.assertTrue(kwargs.get("read_only"))

    def test_main_doctor_still_skips_guard(self):
        """doctor يقرأ الحالة الخام بلا إصلاح — الحارس لا يُستدعى
        له أصلًا كما قبل (السلوك القائم محفوظ)."""
        with mock.patch.object(studio, "_ensure_environment") as guard, \
                mock.patch.object(sys, "argv",
                                  ["studio.py", "doctor"]), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            studio.main()
        guard.assert_not_called()


def _healthy_live_env():
    """بيئة حية سليمة فعلًا (أدوات + ملف خدمة + خادم OmniRoute
    شغال) — وإلا فالفحص الحي يُتخطى (CI مثلًا)."""
    import shutil
    import urllib.request
    if any(shutil.which(t) is None for t in studio._EXPECTED_TOOLS):
        return False
    if not os.path.isfile(studio._UNIT_FILE):
        return False
    try:
        with urllib.request.urlopen(
                studio._OMNIROUTE_URL + "/api/health",
                timeout=2) as resp:
            return 200 <= resp.status < 500
    except Exception:
        return False


class TestVersionLiveFastWhenHealthy(unittest.TestCase):
    """دخان حي: `version` في بيئة سليمة يرجع خلال ثوانٍ."""

    @unittest.skipUnless(_healthy_live_env(),
                         "بيئة حية غير سليمة (أدوات/خدمة/خادم) — "
                         "بيئة CI")
    def test_version_subprocess_returns_quickly(self):
        env = dict(os.environ)
        env.pop("STUDIO_ENV_RESTORED", None)
        started = time.monotonic()
        r = subprocess.run(
            [sys.executable,
             os.path.join(os.path.dirname(os.path.dirname(
                 os.path.abspath(__file__))), "studio.py"),
             "version"],
            capture_output=True, text=True, env=env, timeout=60)
        elapsed = time.monotonic() - started
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("studio "), r.stdout)
        self.assertLess(elapsed, 30.0)


if __name__ == "__main__":
    unittest.main()
