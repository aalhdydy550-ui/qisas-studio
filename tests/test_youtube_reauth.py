#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات انحدار — `youtube-reauth` واستدعاء الرافع المعزول (v0.1.35).

الخلل: `cmd_youtube_auth` كان يستدعي
`[venv_python, uploader, "auth", ...]` بلا `-I`، فيضيف بايثون
مجلد `lib/` إلى `sys.path` فيظلّل `lib/queue.py` وحدة stdlib
`queue`، فينكسر `urllib3` عند أول استيراد لجوجل:
`AttributeError: module 'queue' has no attribute 'LifoQueue'`
— فيخرج `youtube-reauth` بالكود 1 قبل فتح المتصفح أصلًا.
الإصلاح (سطر واحد): `"-I"` في الاستدعاء، كما في `preflight`
و`upload` في `lib/publish.py`.

الاختبارات الحية هنا بلا متصفح وبلا شبكة وبلا نشر: استدعاء
`_import_google()` فقط (استيراد مكتبات جوجل)، واستدعاء
`cmd_youtube_auth` بـ`subprocess.run` وهمية.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import publish

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_PYTHON = os.path.join(STUDIO_DIR, ".venv-youtube", "bin", "python")
UPLOADER = os.path.join(STUDIO_DIR, "lib", "youtube_upload.py")


class FakeProc(object):
    def __init__(self, returncode=0):
        self.returncode = returncode


def _fake_run_factory(captured, returncode=0):
    def _fake_run(argv, **kwargs):
        captured.append(list(argv))
        return FakeProc(returncode)
    return _fake_run


class TestYoutubeReauthIsolation(unittest.TestCase):
    def _call_auth(self, captured, returncode=0):
        """استدعِ cmd_youtube_auth مع subprocess وهمية وvenv وهمي."""
        with tempfile.TemporaryDirectory() as td:
            secrets = os.path.join(td, "client_secrets.json")
            with open(secrets, "w", encoding="utf-8") as f:
                f.write("{}")
            token = os.path.join(td, "token.json")
            with mock.patch.object(
                    studio.publish, "youtube_venv_python",
                    return_value="/fake/venv/bin/python"), \
                    mock.patch.object(
                        studio.subprocess, "run",
                        side_effect=_fake_run_factory(
                            captured, returncode)):
                return studio.cmd_youtube_auth(
                    {}, client_secrets=secrets, token=token)

    def test_auth_invocation_is_isolated(self):
        """استدعاء auth يجب أن يحمل "-I" بعد مفسّر البيئة مباشرةً."""
        captured = []
        rc = self._call_auth(captured)
        self.assertEqual(rc, 0)
        self.assertEqual(len(captured), 1)
        argv = captured[0]
        self.assertEqual(argv[0], "/fake/venv/bin/python")
        self.assertEqual(argv[1], "-I")
        self.assertTrue(argv[2].endswith(
            os.path.join("lib", "youtube_upload.py")))
        self.assertEqual(argv[3], "auth")
        self.assertIn("--client-secrets", argv)
        self.assertIn("--token", argv)

    def test_reauth_delegates_with_isolated_invocation(self):
        """`youtube-reauth` يمرّر نفس الاستدعاء المعزول."""
        captured = []
        with tempfile.TemporaryDirectory() as td:
            secrets = os.path.join(td, "client_secrets.json")
            with open(secrets, "w", encoding="utf-8") as f:
                f.write("{}")
            token = os.path.join(td, "token.json")
            with mock.patch.object(
                    studio.publish, "youtube_venv_python",
                    return_value="/fake/venv/bin/python"), \
                    mock.patch.object(
                        studio.subprocess, "run",
                        side_effect=_fake_run_factory(captured)):
                rc = studio.cmd_youtube_reauth(
                    {}, client_secrets=secrets, token=token)
        self.assertEqual(rc, 0)
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0][1], "-I")
        self.assertEqual(captured[0][3], "auth")

    @unittest.skipUnless(os.path.isfile(VENV_PYTHON),
                         "بيئة .venv-youtube غير موجودة")
    def test_no_isolation_breaks_google_import(self):
        """بلا -I: مجلد lib/ على sys.path فينكسر استيراد جوجل
        بنفس خطأ التقرير (LifoQueue) — إثبات أن الخلل حقيقي
        وأن -I ليست تجميلًا."""
        code = ("import sys; sys.path.insert(0, 'lib'); "
                "import youtube_upload; "
                "youtube_upload._import_google()")
        proc = subprocess.run(
            [VENV_PYTHON, "-c", code], cwd=STUDIO_DIR,
            capture_output=True, text=True, timeout=120)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("LifoQueue", proc.stderr)
        self.assertIn("AttributeError", proc.stderr)

    @unittest.skipUnless(os.path.isfile(VENV_PYTHON),
                         "بيئة .venv-youtube غير موجودة")
    def test_isolated_import_succeeds(self):
        """مجلد السكربت مستبعد من sys.path: استيراد جوجل ينجح —
        مرحلة الاستيراد تُتجاوز بلا متصفح.

        ملاحظة: الاختبار يستدعي بايثون بلا -I لكن باستيراد
        الحزمة (`lib.youtube_upload`) من دليل العمل — فمجلد
        `lib/` نفسه ليس على sys.path، وهو بالضبط الشرط الذي
        يضمنه -I عند تشغيل السكربت (مع -I يُسقط `-c` مدخل
        دليل العمل نفسه من sys.path فلا تُستورد الحزمة)."""
        code = ("import lib.youtube_upload as yu; "
                "yu._import_google()")
        proc = subprocess.run(
            [VENV_PYTHON, "-c", code], cwd=STUDIO_DIR,
            capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
