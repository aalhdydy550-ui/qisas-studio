#!/usr/bin/env python3
"""اختبارات وحدة الترخيص — جولة v0.1.43، بند 2 (شهر مجاني).

كل الاختبارات على مجلد مؤقت عبر QISAS_LICENSE_DIR — لا تلمس
ملف الحالة الحقيقي (~/.qisas-studio) أبدًا، وتتحقق في النهاية
أن حالته لم تتغيّر: إن كان موجودًا (كحالة المالك على جهاز
التطوير — مسموح) فمحتواه كما هو، وإن لم يكن موجودًا فلم يُنشأ.
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from datetime import date
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import license as lic

REAL_STATE = os.path.expanduser("~/.qisas-studio/license.json")

D1 = date(2026, 11, 1)   # أول تشغيل
D30 = date(2026, 11, 30)  # اليوم 30 من التجربة
D31 = date(2026, 12, 1)   # اليوم 31 — منتهية


class LicenseTestBase(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.env = mock.patch.dict(
            os.environ, {lic.LICENSE_DIR_ENV: self.td})
        self.env.start()
        self.addCleanup(self.env.stop)
        # لقطة لحالة ملف الترخيص الحقيقي (إن وُجد — كحالة المالك
        # على جهاز التطوير): الاختبارات لا تلمسه أبدًا، وtearDown
        # يثبت أنه لم يتغيّر. (الحارس القديم «الملف غير موجود»
        # كان يفشل كل الاختبارات على أي جهاز فيه حالة مالك
        # مشروعة — عيب تكامل اكتُشف في تشغيل المجموعة الكاملة
        # لجولة v0.1.43.)
        self._real_snapshot = None
        if os.path.exists(REAL_STATE):
            with open(REAL_STATE, "rb") as fh:
                self._real_snapshot = fh.read()

    def tearDown(self):
        # الحارس: ملف الحالة الحقيقي لم يُنشأ ولم يُعدَّل
        # ولم يُحذف أثناء الاختبار.
        if self._real_snapshot is None:
            self.assertFalse(os.path.exists(REAL_STATE),
                             "الاختبار كتب في ملف الحالة الحقيقي!")
        else:
            self.assertTrue(os.path.exists(REAL_STATE),
                            "الاختبار حذف ملف الحالة الحقيقي!")
            with open(REAL_STATE, "rb") as fh:
                self.assertEqual(fh.read(), self._real_snapshot,
                                 "الاختبار عدّل ملف الحالة الحقيقي!")

    def _write_raw(self, data):
        with open(os.path.join(self.td, "license.json"), "w",
                  encoding="utf-8") as fh:
            if isinstance(data, str):
                fh.write(data)
            else:
                json.dump(data, fh)

    def _read_raw(self):
        with open(os.path.join(self.td, "license.json"),
                  encoding="utf-8") as fh:
            return json.load(fh)


class TestFirstRun(LicenseTestBase):
    def test_records_first_run_once_and_never_changes(self):
        st = lic.record_first_run(D1)
        self.assertEqual(st["first_run"], "2026-11-01")
        self.assertEqual(st["kind"], "trial")
        # تشغيل لاحق (وحتى أبكر) لا يغيّر التاريخ أبدًا.
        self.assertEqual(lic.record_first_run(D30)["first_run"],
                         "2026-11-01")
        self.assertEqual(lic.record_first_run(date(2026, 10, 1))
                         ["first_run"], "2026-11-01")
        self.assertEqual(self._read_raw()["first_run"], "2026-11-01")

    def test_record_preserves_owner_kind(self):
        lic.set_owner(D1)
        st = lic.record_first_run(D30)
        self.assertEqual(st["kind"], "owner")
        self.assertEqual(st["first_run"], "2026-11-01")

    def test_state_file_location_and_permissions(self):
        lic.record_first_run(D1)
        path = os.path.join(self.td, "license.json")
        self.assertTrue(os.path.isfile(path))
        mode = stat.S_IMODE(os.stat(path).st_mode)
        self.assertEqual(mode, 0o600)
        # لا شيء كُتب خارج المجلد المؤقت (عدا الملف نفسه).
        self.assertEqual(sorted(os.listdir(self.td)), ["license.json"])

    def test_status_is_read_only(self):
        # license_status / commercial_allowed لا تنشئان الملف.
        lic.license_status(D1)
        lic.commercial_allowed(D1)
        lic.status_lines()
        self.assertFalse(os.path.exists(
            os.path.join(self.td, "license.json")))


class TestTrialBoundaries(LicenseTestBase):
    def test_no_state_is_trial_not_started(self):
        st = lic.license_status(D1)
        self.assertEqual(st["status"], "trial")
        self.assertIsNone(st["first_run"])
        self.assertEqual(st["days_left"], 30)
        allowed, msg = lic.commercial_allowed(D1)
        self.assertTrue(allowed)
        self.assertIn("لم تبدأ", msg)

    def test_day1_is_30_days_left(self):
        lic.record_first_run(D1)
        st = lic.license_status(D1)
        self.assertEqual((st["status"], st["days_left"]),
                         ("trial", 30))

    def test_day30_is_1_day_left(self):
        lic.record_first_run(D1)
        st = lic.license_status(D30)
        self.assertEqual((st["status"], st["days_left"]),
                         ("trial", 1))
        allowed, msg = lic.commercial_allowed(D30)
        self.assertTrue(allowed)
        self.assertIn("1", msg)

    def test_day31_is_expired(self):
        lic.record_first_run(D1)
        st = lic.license_status(D31)
        self.assertEqual((st["status"], st["days_left"]),
                         ("trial_expired", 0))

    def test_mid_trial_days_left(self):
        lic.record_first_run(D1)
        st = lic.license_status(date(2026, 11, 16))
        self.assertEqual(st["days_left"], 15)

    def test_future_first_run_is_not_expired(self):
        # انحراف ساعة/تعديل يدوي: تاريخ مستقبلي = يوم أول.
        self._write_raw({"kind": "trial", "first_run": "2026-12-01",
                         "license_key": None, "license_type": None,
                         "licensed_on": None})
        st = lic.license_status(D1)
        self.assertEqual((st["status"], st["days_left"]),
                         ("trial", 30))


class TestExpiredMessage(LicenseTestBase):
    def test_expired_blocks_commercial_with_clear_arabic_message(self):
        lic.record_first_run(D1)
        allowed, msg = lic.commercial_allowed(D31)
        self.assertFalse(allowed)
        for needle in ("30", "1000", "5000", "01023468196",
                       "فودافون كاش", "Issue"):
            self.assertIn(needle, msg)
        self.assertIn("انتهت", msg)

    def test_expired_status_lines(self):
        lic.record_first_run(D1)
        lines = lic.status_lines(lic.license_status(D31))
        text = "\n".join(lines)
        self.assertIn("انتهت فترة التجربة", text)
        self.assertIn("1000", text)
        self.assertIn("5000", text)
        self.assertIn("01023468196", text)

    def test_trial_status_lines_mention_days_left(self):
        lic.record_first_run(D1)
        lines = lic.status_lines(lic.license_status(D30))
        text = "\n".join(lines)
        self.assertIn("بقي 1 يومًا", text)
        self.assertIn("2026-11-30", text)


class TestOwnerAndLicensed(LicenseTestBase):
    def test_owner_exempt_forever(self):
        lic.set_owner(D1)
        st = lic.license_status(date(2031, 11, 1))
        self.assertEqual(st["status"], "owner")
        self.assertIsNone(st["days_left"])
        allowed, _msg = lic.commercial_allowed(date(2031, 11, 1))
        self.assertTrue(allowed)
        lines = lic.status_lines(st)
        self.assertIn("معفى دائمًا", "\n".join(lines))

    def test_owner_after_trial_started(self):
        lic.record_first_run(D1)
        lic.set_owner(D30)
        self.assertEqual(lic.license_status(D31)["status"], "owner")
        self.assertEqual(self._read_raw()["first_run"], "2026-11-01")

    def test_licensed_allowed(self):
        st = lic.mark_licensed("STUDIO-COMM-2026-0001",
                               "individual", D1)
        self.assertEqual(st["kind"], "commercial")
        self.assertEqual(st["licensed_on"], "2026-11-01")
        status = lic.license_status(D31)
        self.assertEqual(status["status"], "licensed")
        self.assertTrue(status["licensed"])
        self.assertTrue(status["has_license_key"])
        allowed, _msg = lic.commercial_allowed(D31)
        self.assertTrue(allowed)
        # المفتاح سرّ: لا يظهر في أسطر الحالة أبدًا.
        lines = lic.status_lines(status)
        self.assertNotIn("STUDIO-COMM-2026-0001", "\n".join(lines))
        self.assertIn("أفراد", "\n".join(lines))

    def test_licensed_without_type(self):
        lic.mark_licensed("KEY-XYZ", now=D1)
        st = lic.license_status(D31)
        self.assertEqual(st["status"], "licensed")
        self.assertIsNone(st["license_type"])

    def test_mark_licensed_rejects_empty_key(self):
        for bad in ("", "   ", None, 123):
            with self.assertRaises(ValueError):
                lic.mark_licensed(bad)

    def test_mark_licensed_rejects_bad_type(self):
        with self.assertRaises(ValueError):
            lic.mark_licensed("KEY-XYZ", "gold")

    def test_commercial_without_key_falls_back_to_trial(self):
        self._write_raw({"kind": "commercial",
                         "first_run": "2026-11-01",
                         "license_key": None, "license_type": None,
                         "licensed_on": None})
        st = lic.license_status(D30)
        self.assertEqual(st["status"], "trial")
        self.assertFalse(st["licensed"])


class TestCorruptState(LicenseTestBase):
    def test_corrupt_json_is_trial_not_started_and_flagged(self):
        self._write_raw("{not json at all")
        st = lic.license_status(D1)
        self.assertEqual(st["status"], "trial")
        self.assertTrue(st["corrupt"])
        self.assertIsNone(st["first_run"])
        allowed, _msg = lic.commercial_allowed(D1)
        self.assertTrue(allowed)

    def test_invalid_kind_is_corrupt(self):
        self._write_raw({"kind": "gold", "first_run": "2026-11-01",
                         "license_key": None, "license_type": None,
                         "licensed_on": None})
        st = lic.license_status(D1)
        self.assertTrue(st["corrupt"])
        self.assertEqual(st["status"], "trial")

    def test_invalid_first_run_is_corrupt(self):
        self._write_raw({"kind": "trial", "first_run": "أمس",
                         "license_key": None, "license_type": None,
                         "licensed_on": None})
        st = lic.license_status(D1)
        self.assertTrue(st["corrupt"])
        self.assertIsNone(st["first_run"])

    def test_record_repairs_corrupt_state(self):
        self._write_raw("{broken")
        st = lic.record_first_run(D1)
        self.assertEqual(st["first_run"], "2026-11-01")
        self.assertFalse(lic.license_status(D1)["corrupt"])


class TestDoctorCheck(LicenseTestBase):
    def test_doctor_ok_for_owner_and_licensed(self):
        lic.set_owner(D1)
        self.assertTrue(lic.doctor_check(D31)["ok"])
        self._write_raw({"kind": "commercial",
                         "first_run": "2026-11-01",
                         "license_key": "K", "license_type": "company",
                         "licensed_on": "2026-11-01"})
        self.assertTrue(lic.doctor_check(D31)["ok"])

    def test_doctor_warns_when_trial_near_end(self):
        lic.record_first_run(D1)
        check = lic.doctor_check(date(2026, 11, 26))
        self.assertFalse(check["ok"])
        self.assertEqual(check["level"], "warn")
        self.assertIn("5", check["detail"])

    def test_doctor_errors_when_expired(self):
        lic.record_first_run(D1)
        check = lic.doctor_check(D31)
        self.assertFalse(check["ok"])
        self.assertEqual(check["level"], "error")
        self.assertIn("فودافون كاش", check["fix"])


if __name__ == "__main__":
    unittest.main()
