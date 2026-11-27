#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات إعداد أول تشغيل — جولة v0.1.63، بند 34 (عقد ع19).

كل الاختبارات على مجلد مؤقت عبر QISAS_LICENSE_DIR — لا تلمس
ملف الحالة الحقيقي (~/.qisas-studio/license.json) أبدًا،
وتتحقق في النهاية أن حالته لم تتغيّر.
"""
import json
import os
import sys
import tempfile
import unittest
from datetime import date
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import license as lic

REAL_STATE = os.path.expanduser("~/.qisas-studio/license.json")

D1 = date(2026, 11, 1)   # أول تشغيل
D2 = date(2026, 11, 5)   # إعادة تشغيل لاحقة


class FirstRunTestBase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = self._td.name
        self.addCleanup(self._td.cleanup)
        self.env = mock.patch.dict(
            os.environ, {lic.LICENSE_DIR_ENV: self.td})
        self.env.start()
        self.addCleanup(self.env.stop)
        self._real_snapshot = None
        if os.path.exists(REAL_STATE):
            with open(REAL_STATE, "rb") as fh:
                self._real_snapshot = fh.read()

    def tearDown(self):
        # الحارس: ملف الحالة الحقيقي لم يُنشأ ولم يُعدَّل.
        if self._real_snapshot is None:
            self.assertFalse(os.path.exists(REAL_STATE),
                             "الاختبار كتب في ملف الحالة الحقيقي!")
        else:
            self.assertTrue(os.path.exists(REAL_STATE),
                            "الاختبار حذف ملف الحالة الحقيقي!")
            with open(REAL_STATE, "rb") as fh:
                self.assertEqual(fh.read(), self._real_snapshot,
                                 "الاختبار عدّل ملف الحالة الحقيقي!")

    def _read_state_bytes(self):
        with open(os.path.join(self.td, "license.json"),
                  "rb") as fh:
            return fh.read()


class TestFirstRunSetup(FirstRunTestBase):
    """إعداد أول تشغيل ينشئ البنية مرة واحدة فقط."""

    def test_first_run_is_true_before_setup(self):
        self.assertTrue(lic.is_first_run())

    def test_first_run_setup_creates_structure_and_report(self):
        setup = lic.first_run_setup(now=D1)
        self.assertFalse(setup["already_setup"])
        self.assertEqual(setup["first_run"], "2026-11-01")
        self.assertEqual(setup["timezone"], "Africa/Cairo")
        self.assertEqual(setup["morning_time"], "08:00")
        self.assertEqual(setup["morning_brief"], "08:00 Africa/Cairo")
        # البنية أُنشئت: ملف الحالة موجود بتاريخ أول تشغيل.
        self.assertTrue(os.path.isfile(
            os.path.join(self.td, "license.json")))
        state = json.loads(self._read_state_bytes())
        self.assertEqual(state["first_run"], "2026-11-01")
        self.assertEqual(state["kind"], "trial")
        # التقرير يطبع الخطوات وبطاقة إضافة مفتاح.
        self.assertTrue(setup["steps"])
        card = setup["key_card"]
        self.assertEqual(card["title"], "بطاقة إضافة مفتاح")
        self.assertIn("--token-file", card["command"])
        self.assertNotIn("--token ", card["command"])
        self.assertTrue(card["notes"])

    def test_rerun_never_reinitializes(self):
        first = lic.first_run_setup(now=D1)
        self.assertFalse(first["already_setup"])
        before = self._read_state_bytes()
        second = lic.first_run_setup(now=D2)
        self.assertTrue(second["already_setup"])
        # تاريخ أول تشغيل الأصلي باقٍ — لم يُعاد ضبطه.
        self.assertEqual(second["first_run"], "2026-11-01")
        self.assertEqual(second["timezone"], "Africa/Cairo")
        self.assertEqual(second["morning_time"], "08:00")
        # ملف الحالة بلا أي كتابة في إعادة التشغيل.
        self.assertEqual(self._read_state_bytes(), before)
        self.assertFalse(lic.is_first_run())

    def test_first_run_setup_preserves_existing_first_run(self):
        with open(os.path.join(self.td, "license.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"kind": "trial", "first_run": "2026-11-01",
                       "license_key": None, "license_type": None,
                       "licensed_on": None}, fh)
        before = self._read_state_bytes()
        setup = lic.first_run_setup(now=D2)
        self.assertTrue(setup["already_setup"])
        self.assertEqual(setup["first_run"], "2026-11-01")
        self.assertEqual(self._read_state_bytes(), before)

    def test_first_run_setup_repairs_corrupt_state(self):
        with open(os.path.join(self.td, "license.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertTrue(lic.is_first_run())
        setup = lic.first_run_setup(now=D1)
        self.assertFalse(setup["already_setup"])
        self.assertEqual(setup["first_run"], "2026-11-01")
        self.assertEqual(lic.license_status(now=D1)["status"], "trial")

    def test_first_run_lines_carry_timezone_and_morning(self):
        setup = lic.first_run_setup(now=D1)
        text = "\n".join(lic.first_run_lines(setup))
        self.assertIn("Africa/Cairo", text)
        self.assertIn("08:00", text)
        self.assertIn("2026-11-01", text)
        self.assertIn("بطاقة إضافة مفتاح", text)
        self.assertIn("--token-file", text)

    def test_first_run_lines_read_only_without_setup(self):
        # بلا تقرير: تُبنى قراءةً فقط — لا تسجّل أول تشغيل.
        lines = lic.first_run_lines()
        self.assertIn("Africa/Cairo", "\n".join(lines))
        self.assertTrue(lic.is_first_run())
        self.assertFalse(os.path.exists(
            os.path.join(self.td, "license.json")))

    def test_first_run_lines_after_setup_say_already_done(self):
        lic.first_run_setup(now=D1)
        setup = lic.first_run_setup(now=D2)
        text = "\n".join(lic.first_run_lines(setup))
        self.assertIn("مهيأ مسبقًا", text)
        self.assertIn("لا إعادة تهيئة", text)

    def test_first_run_steps_mention_doctor_and_key_card(self):
        steps = lic.first_run_steps()
        joined = "\n".join(steps)
        self.assertIn("doctor", joined)
        self.assertIn("08:00", joined)
        self.assertIn("Africa/Cairo", joined)


if __name__ == "__main__":
    unittest.main()
