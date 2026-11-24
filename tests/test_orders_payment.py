#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات انحدار لبوابة دفع طلبات العملاء (الجولة 6، 2026-11-22؛
القاعدة الجديدة جولة v0.1.43، 2026-11-23).

القاعدة (قرار المستخدم 2026-11-23 18:38، يلغي قاعدة «أول 10
طلبات» 2026-11-22 11:10): طلبات العميل الجديد (برقم الواتساب)
مجانية خلال أول 30 يومًا من أول طلب له، بلا حد لعدد الطلبات
إطلاقًا — تُنتَج تلقائيًا بلا تأكيد دفع (حالتها `new`). وبعد
30 يومًا من أول طلب لا يُنتَج الفيديو إلا بعد تأكيد دفع صاحبه:
يبدأ `awaiting_payment` ويصير `paid` عبر `orders confirm`.
الحد دقيق: اليوم 30 نفسه مجاني، واليوم 31 مدفوع. تاريخ أول طلب
يُشتق من أقدم `created_at` لطلباته غير الفاشلة؛ الطلب الفاشل
لا يبدأ عدّاد التجربة. الطلبات القديمة بحالة done لا تُمس أبدًا.

كل الاختبارات على ملف طلبات مؤقت (ORDERS_FILE/ORDERS_DIR
مستبدلة بدليل مؤقت) وبلا إنتاج فيديو حقيقي: الإنتاج يُحاكى
بـ mock على cmd_client_run. بلا شبكة.

أرقام الواتساب الوهمية مولَّدة ببذرة ثابتة من
`lib.test_identity` (جولة v0.1.37 — البند 13) — لا أرقام
ثابتة مكتوبة يدًا، ولا رقم فودافون كاش الحقيقي كبيانات اختبار.
"""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import client_orders
from lib import test_identity

_FAKE_NUMBERS = test_identity.fake_whatsapp_numbers(count=4)
CLIENT_A = _FAKE_NUMBERS[0]
CLIENT_B = _FAKE_NUMBERS[1]


def _row(order_id, status, **extra):
    row = {"id": order_id, "status": status,
           "client_name": "عميل اختبار",
           "contact": CLIENT_A,
           "whatsapp": CLIENT_A,
           "description": "قصة اختبار قصيرة عن الأمانة.",
           "duration": "40-60", "size": "vertical", "logo": "page",
           "created_at": "2026-11-22T10:00:00"}
    row.update(extra)
    return row


class TestOrdersPayment(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.orig_dir = client_orders.ORDERS_DIR
        self.orig_file = client_orders.ORDERS_FILE
        self.orig_out = client_orders.OUT_ROOT
        client_orders.ORDERS_DIR = str(self.root)
        client_orders.ORDERS_FILE = str(self.root / "orders.jsonl")
        client_orders.OUT_ROOT = str(self.root / "out")

    def tearDown(self):
        client_orders.ORDERS_DIR = self.orig_dir
        client_orders.ORDERS_FILE = self.orig_file
        client_orders.OUT_ROOT = self.orig_out
        self.tmp.cleanup()

    def _write(self, *rows):
        (self.root / "orders.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
            encoding="utf-8")

    def _read(self):
        return client_orders.load_orders()

    def _fill_orders(self, number, count, prefix="QS-FILL",
                     status="done", created_at=None):
        extra = {}
        if created_at is not None:
            extra["created_at"] = created_at
        for i in range(count):
            with mock.patch("sys.stdout", io.StringIO()):
                client_orders.append_order(
                    _row("%s-%02d" % (prefix, i + 1), status,
                         whatsapp=number, contact=number, **extra))

    # (أ) طلبات العميل مجانية خلال أول 30 يومًا — بلا حد للعدد
    def test_many_orders_within_30_days_are_free(self):
        # 25 طلبًا في أول 29 يومًا → الطلب الـ26 مجاني أيضًا.
        for i in range(1, 26):
            with mock.patch("sys.stdout", io.StringIO()):
                client_orders.append_order(
                    _row("QS-T%02d" % i, None,
                         created_at="2026-11-%02dT10:00:00"
                         % (1 + (i - 1) % 29)))
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(
                _row("QS-T26", None, created_at="2026-11-29T10:00:00"))
        self.assertEqual([o["status"] for o in self._read()],
                         ["new"] * 26)

    def test_order_on_day_31_waits_for_payment(self):
        self._fill_orders(CLIENT_A, 25, created_at="2026-11-01T10:00:00")
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(
                _row("QS-T26", None, created_at="2026-12-01T10:00:00"))
        self.assertEqual(self._read()[-1]["status"], "awaiting_payment")

    def test_day_30_free_day_31_paid_boundary(self):
        # الحد دقيق: اليوم 30 من أول طلب مجاني، واليوم 31 مدفوع.
        self._fill_orders(CLIENT_A, 1, created_at="2026-11-01T10:00:00")
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(
                _row("QS-B30", None, created_at="2026-11-30T10:00:00"))
            client_orders.append_order(
                _row("QS-B31", None, created_at="2026-12-01T10:00:00"))
        statuses = [o["status"] for o in self._read()]
        self.assertEqual(statuses[-2:], ["new", "awaiting_payment"])

    def test_other_client_still_in_trial(self):
        self._fill_orders(CLIENT_A, 25, created_at="2026-11-01T10:00:00")
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(
                _row("QS-T11B", None, whatsapp=CLIENT_B,
                     contact=CLIENT_B, created_at="2026-12-01T10:00:00"))
        self.assertEqual(self._read()[-1]["status"], "new")

    def test_whatsapp_form_variants_share_one_trial_clock(self):
        # الصيغ الثلاث للرقم الواحد (محلي / +20 / 0020) عميل واحد:
        # ساعة التجربة واحدة، فطلب بعد 30 يومًا من أول طلب بأي
        # صيغة ينتظر الدفع.
        canon = test_identity.canonical_whatsapp(CLIENT_A)
        forms = ["0" + canon, "+20" + canon, "0020" + canon]
        for i in range(10):
            num = forms[i % 3]
            with mock.patch("sys.stdout", io.StringIO()):
                client_orders.append_order(
                    _row("QS-V%02d" % (i + 1), "done",
                         whatsapp=num, contact=num,
                         created_at="2026-11-01T10:00:00"))
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(
                _row("QS-V11", None, created_at="2026-12-01T10:00:00"))
        self.assertEqual(self._read()[-1]["status"], "awaiting_payment")

    def test_failed_order_does_not_start_trial_clock(self):
        # طلب فاشل قديم لا يبدأ عدّاد التجربة: أول طلب حقيقي
        # بعده مجاني حتى لو مرّت شهور على الفاشل.
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(
                _row("QS-FAIL-1", "failed", whatsapp=CLIENT_A,
                     contact=CLIENT_A, created_at="2026-10-01T10:00:00"))
            client_orders.append_order(
                _row("QS-T10", None, created_at="2026-11-22T10:00:00"))
        self.assertEqual(self._read()[-1]["status"], "new")

    def test_order_without_created_at_treated_as_in_trial(self):
        # طلب قديم بلا created_at لا يكسر طلبًا جديدًا: يُعامَل
        # العميل كأنه ضمن التجربة.
        row = _row("QS-NODATE", "done")
        del row["created_at"]
        self._write(row)
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(_row("QS-NEW", None))
        self.assertEqual(self._read()[-1]["status"], "new")

    def test_new_client_is_free(self):
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(_row("QS-NEWC", None))
        self.assertEqual(self._read()[0]["status"], "new")

    def test_free_trial_remaining_returns_days(self):
        from datetime import datetime, timezone
        # عميل جديد تمامًا → 30 يومًا.
        self.assertEqual(
            client_orders.free_trial_remaining(CLIENT_A), 30)
        # أول طلب قبل 5 أيام → 25 يومًا باقية.
        self._fill_orders(CLIENT_A, 3, created_at="2026-11-01T10:00:00")
        ref = datetime(2026, 11, 6, tzinfo=timezone.utc)
        self.assertEqual(
            client_orders.free_trial_remaining(CLIENT_A, now=ref), 25)
        # اليوم 30 نفسه → يوم واحد باقٍ؛ واليوم 31 → صفر.
        ref30 = datetime(2026, 11, 30, tzinfo=timezone.utc)
        self.assertEqual(
            client_orders.free_trial_remaining(CLIENT_A, now=ref30), 1)
        ref31 = datetime(2026, 12, 1, tzinfo=timezone.utc)
        self.assertEqual(
            client_orders.free_trial_remaining(CLIENT_A, now=ref31), 0)
        # طلبات كثيرة لا تنقص الأيام: العدد بلا أثر.
        self._fill_orders(CLIENT_A, 25, prefix="QS-FILL2",
                          created_at="2026-11-01T10:00:00")
        self.assertEqual(
            client_orders.free_trial_remaining(CLIENT_A, now=ref), 25)

    def test_no_whatsapp_order_is_free(self):
        row = _row("QS-NOWA", None)
        del row["whatsapp"]
        row["contact"] = ""
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(row)
        self.assertEqual(self._read()[0]["status"], "new")

    def test_cmd_trial_status_prints_days(self):
        from datetime import datetime, timedelta, timezone
        today = datetime.now(timezone.utc).date()
        first = (today - timedelta(days=5)).isoformat() + "T10:00:00"
        self._fill_orders(CLIENT_A, 3, created_at=first)
        with mock.patch("sys.stdout", io.StringIO()) as buf:
            rc = client_orders.cmd_trial_status(CLIENT_A)
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("أول طلب في %s" % (today - timedelta(days=5)), out)
        self.assertIn("أيام مجانية باقية: 25 من 30", out)
        # بعد انتهاء التجربة: رسالة الانتهاء وصفر أيام.
        old = (today - timedelta(days=40)).isoformat() + "T10:00:00"
        self._write(_row("QS-OLD1", "done",
                         created_at=old))
        with mock.patch("sys.stdout", io.StringIO()) as buf:
            rc = client_orders.cmd_trial_status(CLIENT_A)
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("أيام مجانية باقية: 0 من 30", out)
        self.assertIn("انتهت التجربة المجانية", out)

    # التدفق الكامل: طلب أول مجاني يُنتج، وطلب بعد 30 يومًا يتوقف
    # حتى التأكيد — مهما بلغ عدد الطلبات السابقة.
    def test_full_flow_first_free_day31_waits_then_produces(self):
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(
                _row("QS-FLOW-1", None, created_at="2026-11-01T10:00:00"))
        self._fill_orders(CLIENT_A, 25, prefix="QS-FLOWF",
                          created_at="2026-11-10T10:00:00")
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(
                _row("QS-FLOW-31", None, created_at="2026-12-01T10:00:00"))
        self.assertEqual(
            [o["status"] for o in self._read()],
            ["new"] + ["done"] * 25 + ["awaiting_payment"])
        with mock.patch("sys.stdout", io.StringIO()), \
             mock.patch.object(client_orders, "cmd_client_run",
                               return_value=0) as run:
            rc = client_orders.cmd_process_queue({})
        self.assertEqual(rc, 0)
        # الطلب الأول المجاني أُنتج؛ طلب اليوم 31 تُخطى.
        run.assert_called_once_with({}, "QS-FLOW-1")
        self.assertEqual(self._read()[-1]["status"], "awaiting_payment")
        # الإنتاج الحقيقي يعلّم الطلب done عند النجاح — نحاكي ذلك
        # حتى لا يعيد الطابور إنتاج الطلب الأول في التشغيل الثاني.
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.update_order("QS-FLOW-1", status="done")
            client_orders.confirm_payment("QS-FLOW-31")
        with mock.patch("sys.stdout", io.StringIO()), \
             mock.patch.object(client_orders, "cmd_client_run",
                               return_value=0) as run:
            rc = client_orders.cmd_process_queue({})
        self.assertEqual(rc, 0)
        run.assert_called_once_with({}, "QS-FLOW-31")

    def test_append_keeps_explicit_paid_and_done(self):
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(_row("QS-P1", "paid"))
            client_orders.append_order(_row("QS-D1", "done"))
        self.assertEqual([o["status"] for o in self._read()],
                         ["paid", "done"])

    # (ب) confirm يحوّل awaiting_payment إلى paid مع حقول التأكيد
    def test_confirm_turns_awaiting_to_paid(self):
        self._write(_row("QS-PAY-1", "awaiting_payment"))
        with mock.patch("sys.stdout", io.StringIO()):
            order = client_orders.confirm_payment("QS-PAY-1")
        self.assertEqual(order["status"], "paid")
        self.assertEqual(order["confirmed_by"], "owner")
        self.assertRegex(order["confirmed_at"],
                         r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
        self.assertEqual(order["updated_at"], order["confirmed_at"])
        self.assertEqual(self._read()[0]["status"], "paid")

    def test_confirm_records_custom_confirmer(self):
        self._write(_row("QS-PAY-2", "awaiting_payment"))
        with mock.patch("sys.stdout", io.StringIO()):
            order = client_orders.confirm_payment("QS-PAY-2",
                                                  confirmed_by="أيمن")
        self.assertEqual(order["confirmed_by"], "أيمن")

    def test_confirm_legacy_new_also_works(self):
        self._write(_row("QS-LEG-1", "new"))
        with mock.patch("sys.stdout", io.StringIO()):
            order = client_orders.confirm_payment("QS-LEG-1")
        self.assertEqual(order["status"], "paid")

    def test_confirm_unknown_id_clear_arabic_error(self):
        self._write(_row("QS-X", "awaiting_payment"))
        with self.assertRaises(client_orders.ClientOrderError) as ctx:
            client_orders.confirm_payment("QS-NOPE")
        self.assertIn("غير موجود", str(ctx.exception))
        self.assertIn("QS-NOPE", str(ctx.exception))

    def test_cmd_confirm_payment_exit_codes(self):
        self._write(_row("QS-CMD-1", "awaiting_payment"))
        with mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(
                client_orders.cmd_confirm_payment({}, "QS-NOPE"), 1)
            self.assertEqual(
                client_orders.cmd_confirm_payment({}, "QS-CMD-1"), 0)
            # تأكيد ثانٍ مرفوض (رمز 2).
            self.assertEqual(
                client_orders.cmd_confirm_payment({}, "QS-CMD-1"), 2)

    # تأكيد مرتين: الثانية مرفوضة وبلا أثر (السلوك المختار موثَّق هنا).
    def test_confirm_twice_rejected_without_effect(self):
        self._write(_row("QS-TWICE-1", "awaiting_payment"))
        with mock.patch("sys.stdout", io.StringIO()):
            first = client_orders.confirm_payment("QS-TWICE-1")
        first_stamp = first["confirmed_at"]
        with self.assertRaises(client_orders.ClientOrderError) as ctx:
            client_orders.confirm_payment("QS-TWICE-1")
        self.assertIn("مؤكَّد بالفعل", str(ctx.exception))
        after = self._read()[0]
        self.assertEqual(after["status"], "paid")
        self.assertEqual(after["confirmed_at"], first_stamp)
        self.assertEqual(after["confirmed_by"], "owner")

    def test_confirm_done_rejected_and_done_unchanged(self):
        done = _row("QS-OLD", "done", video_path="QS-OLD/video.mp4",
                    duration_seconds=50.0)
        self._write(done)
        before = json.dumps(self._read()[0], ensure_ascii=False,
                            sort_keys=True)
        with self.assertRaises(client_orders.ClientOrderError):
            client_orders.confirm_payment("QS-OLD")
        after = json.dumps(self._read()[0], ensure_ascii=False,
                           sort_keys=True)
        self.assertEqual(before, after)

    def test_confirm_failed_or_processing_rejected(self):
        for status in ("failed", "processing", "in_progress"):
            self._write(_row("QS-S-" + status, status))
            with self.assertRaises(client_orders.ClientOrderError,
                                   msg=status):
                client_orders.confirm_payment("QS-S-" + status)

    # (ج) process-queue يتخطى awaiting_payment وينتج المدفوع فقط
    def test_process_queue_skips_awaiting_payment(self):
        self._write(_row("QS-OLD", "done", video_path="QS-OLD/video.mp4"),
                    _row("QS-WAIT", "awaiting_payment"),
                    _row("QS-PAID", "paid"))
        with mock.patch("sys.stdout", io.StringIO()) as buf, \
             mock.patch.object(client_orders, "cmd_client_run",
                               return_value=0) as run:
            rc = client_orders.cmd_process_queue({})
        self.assertEqual(rc, 0)
        run.assert_called_once_with({}, "QS-PAID")
        out = buf.getvalue()
        self.assertIn("بانتظار تأكيد الدفع", out)
        self.assertIn("QS-WAIT", out)
        self.assertIn("orders confirm", out)
        # القديم done لم يُستدعَ له إنتاج إطلاقًا.
        self.assertNotIn("QS-OLD", [c.args[1] for c in run.call_args_list])

    def test_process_queue_only_awaiting_returns_zero(self):
        self._write(_row("QS-WAIT-ONLY", "awaiting_payment"))
        with mock.patch("sys.stdout", io.StringIO()) as buf, \
             mock.patch.object(client_orders, "cmd_client_run",
                               return_value=0) as run:
            rc = client_orders.cmd_process_queue({})
        self.assertEqual(rc, 0)
        run.assert_not_called()
        self.assertIn("QS-WAIT-ONLY", buf.getvalue())

    def test_process_queue_still_runs_legacy_new(self):
        # توافق رجعي: صفوف new القديمة (قبل البوابة) ما زالت تُنتَج.
        self._write(_row("QS-LEG-2", "new"))
        with mock.patch("sys.stdout", io.StringIO()), \
             mock.patch.object(client_orders, "cmd_client_run",
                               return_value=0) as run:
            rc = client_orders.cmd_process_queue({})
        self.assertEqual(rc, 0)
        run.assert_called_once_with({}, "QS-LEG-2")

    # حارس مباشر: client-run يرفض غير المدفوع قبل أي إنتاج
    def test_client_run_refuses_awaiting_payment(self):
        self._write(_row("QS-DIRECT", "awaiting_payment"))
        with mock.patch("sys.stdout", io.StringIO()) as buf:
            rc = client_orders.cmd_client_run({}, "QS-DIRECT")
        self.assertEqual(rc, 4)
        self.assertIn("بانتظار تأكيد الدفع", buf.getvalue())
        self.assertEqual(self._read()[0]["status"], "awaiting_payment")

    # (د) done القديم لا يتغير إطلاقًا عبر الطابور كله
    def test_old_done_never_changes_through_queue(self):
        done = _row("QS-OLD", "done", video_path="QS-OLD/video.mp4",
                    thumbnail_path="QS-OLD/thumbnail.jpg",
                    duration_seconds=50.77,
                    hook="هوك قديم", moral="عبرة قديمة")
        self._write(done, _row("QS-PAID", "paid"))
        before = json.dumps(self._read()[0], ensure_ascii=False,
                            sort_keys=True)
        with mock.patch("sys.stdout", io.StringIO()), \
             mock.patch.object(client_orders, "cmd_client_run",
                               return_value=0):
            client_orders.cmd_process_queue({})
        after = json.dumps(self._read()[0], ensure_ascii=False,
                           sort_keys=True)
        self.assertEqual(before, after)

    # أمر العرض: قائمة انتظار الدفع
    def test_list_orders_filters_awaiting_payment(self):
        self._write(_row("QS-A", "awaiting_payment"),
                    _row("QS-B", "paid"),
                    _row("QS-C", "done"))
        with mock.patch("sys.stdout", io.StringIO()) as buf:
            rc = client_orders.cmd_list_orders(status="awaiting_payment")
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("QS-A", out)
        self.assertNotIn("QS-B", out)
        self.assertNotIn("QS-C", out)
        self.assertIn("الإجمالي: 1", out)

    def test_list_orders_empty_status(self):
        self._write(_row("QS-A", "paid"))
        with mock.patch("sys.stdout", io.StringIO()) as buf:
            rc = client_orders.cmd_list_orders(status="awaiting_payment")
        self.assertEqual(rc, 0)
        self.assertIn("لا توجد طلبات", buf.getvalue())


class TestClientRunLogo(unittest.TestCase):
    """شعار الصفحة لا يظهر أبدًا على فيديوهات طلبات العملاء
    (قاعدة المستخدم 2026-11-22) — وشعار العميل الخاص يُطبَّق.

    الإنتاج الكامل يُحاكى (بلا سرد/صور/تجميع حقيقي)؛ ما يُثبَت
    هو القرار عند نقطة التجميع: watermark_on=False دائمًا في
    مسار الطلبات، وapply_watermark يُستدعى لشعار العميل فقط.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.orig_dir = client_orders.ORDERS_DIR
        self.orig_file = client_orders.ORDERS_FILE
        self.orig_out = client_orders.OUT_ROOT
        client_orders.ORDERS_DIR = str(self.root)
        client_orders.ORDERS_FILE = str(self.root / "orders.jsonl")
        client_orders.OUT_ROOT = str(self.root / "out")

    def tearDown(self):
        client_orders.ORDERS_DIR = self.orig_dir
        client_orders.ORDERS_FILE = self.orig_file
        client_orders.OUT_ROOT = self.orig_out
        self.tmp.cleanup()

    def _write(self, *rows):
        (self.root / "orders.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
            encoding="utf-8")

    def _read(self):
        return client_orders.load_orders()

    def test_resolve_order_logo_choice(self):
        resolve = client_orders.resolve_order_logo_choice
        self.assertEqual(resolve({"logo": "page"}), ("none", False))
        self.assertEqual(resolve({"logo": "custom"}), ("custom", True))
        self.assertEqual(resolve({"logo": "client"}), ("custom", True))
        self.assertEqual(resolve({"logo": "none"}), ("none", False))
        self.assertEqual(resolve({}), ("none", False))
        self.assertEqual(resolve({"logo": "weird"}), ("none", False))

    def _run_order(self, order_id, logo, logo_path=None):
        row = _row(order_id, "new", logo=logo)
        order_dir = self.root / "out" / order_id
        order_dir.mkdir(parents=True, exist_ok=True)
        if logo_path is not None:
            # logo_path مسار مطلق داخل مجلد الطلب — كما يكتبه
            # المراقب في watcher-runbook.md
            # (~/workspace/videos/client-orders/<id>/client-logo.<ext>).
            row["logo_path"] = str(order_dir / logo_path)
            # PNG صغير 1×1 (المحتوى لا يهم — apply_watermark محاكى،
            # لكن _resolve_order_logo الحقيقي يفحص الامتداد والحجم).
            (order_dir / logo_path).write_bytes(
                bytes.fromhex(
                    "89504e470d0a1a0a0000000d494844520000000100000001"
                    "08060000001f15c4890000000a49444154789c6301000000"
                    "0500010d0a2db40000000049454e44ae426082"))
        self._write(row)
        cfg = {"video": {"width": 720, "height": 1280},
               "paths": {"runs_dir": str(self.root / "runs")}}
        story = {"scenes": [{"image_keywords": ["أمانة"]}],
                 "hook": "هوك اختبار", "moral": "عبرة اختبار"}
        with mock.patch("sys.stdout", io.StringIO()), \
             mock.patch.object(client_orders, "expand_story",
                               return_value=story), \
             mock.patch.object(client_orders, "narrate_scenes",
                               return_value=(str(self.root / "n.wav"),
                                             50.0, [])), \
             mock.patch.object(client_orders, "fetch_scene_image",
                               return_value="https://example.invalid/x.jpg"), \
             mock.patch.object(client_orders, "build_project",
                               return_value="proj-test"), \
             mock.patch.object(client_orders.studio, "new_run",
                               return_value=("run-test",
                                             str(self.root / "rundir"))), \
             mock.patch.object(client_orders.studio, "cmd_produce",
                               return_value={"images": ["a.jpg"],
                                             "narration_duration": 50.0,
                                             "phrases": ["عبارة"]}), \
             mock.patch.object(client_orders.studio, "cmd_assemble",
                               side_effect=lambda c, r, h, o, w: (o, 50.0)) \
                as assemble, \
             mock.patch.object(client_orders.studio, "cmd_thumbnail",
                               side_effect=lambda c, o, h, t: t), \
             mock.patch.object(client_orders.studio.watermark,
                               "probe_duration", return_value=50.0), \
             mock.patch.object(client_orders.studio.watermark,
                               "apply_watermark") as apply_logo:
            rc = client_orders.cmd_client_run(cfg, order_id)
        self.assertEqual(rc, 0)
        self.assertEqual(self._read()[0]["status"], "done")
        return assemble, apply_logo

    def test_page_logo_never_applied(self):
        assemble, apply_logo = self._run_order("QS-LOGO-1", "page")
        assemble.assert_called_once()
        self.assertFalse(assemble.call_args[0][4])
        apply_logo.assert_not_called()

    def test_none_logo_no_watermark(self):
        assemble, apply_logo = self._run_order("QS-LOGO-2", "none")
        assemble.assert_called_once()
        self.assertFalse(assemble.call_args[0][4])
        apply_logo.assert_not_called()

    def test_custom_logo_applied_client_badge(self):
        assemble, apply_logo = self._run_order(
            "QS-LOGO-3", "custom", logo_path="client-logo.png")
        assemble.assert_called_once()
        self.assertFalse(assemble.call_args[0][4])
        apply_logo.assert_called_once()
        called = apply_logo.call_args
        self.assertEqual(called.kwargs.get("badge"),
                         str(self.root / "out" / "QS-LOGO-3"
                             / "client-logo.png"))


if __name__ == "__main__":
    unittest.main()
