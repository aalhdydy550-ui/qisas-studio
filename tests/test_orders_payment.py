#!/usr/bin/env python3
"""اختبارات انحدار لبوابة دفع طلبات العملاء (الجولة 6، 2026-11-22).

القاعدة (قرار المستخدم 2026-11-22 11:10، يلغي تصميم «أول طلب
مجاني»): أول 10 طلبات لكل عميل (برقم الواتساب) تجربة مجانية —
تُنتَج تلقائيًا بلا تأكيد دفع (حالتها `new`). ومن الطلب الـ11
لنفس العميل فصاعدًا لا يُنتَج الفيديو إلا بعد تأكيد دفع صاحبه:
يبدأ `awaiting_payment` ويصير `paid` عبر `orders confirm`.
العدّ لكل رقم واتساب على حدة من سجل الطلبات؛ الطلب الفاشل
لا يستهلك من التجربة. الطلبات القديمة بحالة done لا تُمس أبدًا.

كل الاختبارات على ملف طلبات مؤقت (ORDERS_FILE/ORDERS_DIR
مستبدلة بدليل مؤقت) وبلا إنتاج فيديو حقيقي: الإنتاج يُحاكى
بـ mock على cmd_client_run. بلا شبكة.
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


def _row(order_id, status, **extra):
    row = {"id": order_id, "status": status,
           "client_name": "عميل اختبار",
           "contact": "01023468196",
           "whatsapp": "01023468196",
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
                     status="done"):
        for i in range(count):
            with mock.patch("sys.stdout", io.StringIO()):
                client_orders.append_order(
                    _row("%s-%02d" % (prefix, i + 1), status,
                         whatsapp=number, contact=number))

    # (أ) أول 10 طلبات لكل عميل تجربة مجانية
    def test_first_ten_orders_are_free_trial(self):
        for i in range(1, 11):
            with mock.patch("sys.stdout", io.StringIO()):
                client_orders.append_order(_row("QS-T%02d" % i, None))
        self.assertEqual([o["status"] for o in self._read()],
                         ["new"] * 10)

    def test_eleventh_order_same_number_waits_for_payment(self):
        self._fill_orders("01023468196", 10)
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(_row("QS-T11", None))
        self.assertEqual(self._read()[-1]["status"], "awaiting_payment")

    def test_eleventh_order_different_number_is_free(self):
        self._fill_orders("01023468196", 10)
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(
                _row("QS-T11B", None, whatsapp="01111111111",
                     contact="01111111111"))
        self.assertEqual(self._read()[-1]["status"], "new")

    def test_whatsapp_form_variants_count_as_one_client(self):
        for i in range(10):
            num = "01023468196" if i % 2 == 0 else "+201023468196"
            with mock.patch("sys.stdout", io.StringIO()):
                client_orders.append_order(
                    _row("QS-V%02d" % (i + 1), "done",
                         whatsapp=num, contact=num))
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(_row("QS-V11", None))
        self.assertEqual(self._read()[-1]["status"], "awaiting_payment")

    def test_failed_order_does_not_consume_trial(self):
        self._fill_orders("01023468196", 9)
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(
                _row("QS-FAIL-1", "failed", whatsapp="01023468196",
                     contact="01023468196"))
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(_row("QS-T10", None))
        self.assertEqual(self._read()[-1]["status"], "new")

    def test_no_whatsapp_order_is_free(self):
        row = _row("QS-NOWA", None)
        del row["whatsapp"]
        row["contact"] = ""
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(row)
        self.assertEqual(self._read()[0]["status"], "new")

    def test_free_trial_remaining_counts(self):
        self.assertEqual(
            client_orders.free_trial_remaining("01023468196"), 10)
        self._fill_orders("01023468196", 3)
        self.assertEqual(
            client_orders.free_trial_remaining("01023468196"), 7)
        self._fill_orders("01023468196", 7, prefix="QS-FILL2")
        self.assertEqual(
            client_orders.free_trial_remaining("01023468196"), 0)

    # التدفق الكامل: طلب أول مجاني يُنتج، والـ11 يتوقف حتى التأكيد
    def test_full_flow_first_free_eleventh_waits_then_produces(self):
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(_row("QS-FLOW-1", None))
        self._fill_orders("01023468196", 9, prefix="QS-FLOWF")
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.append_order(_row("QS-FLOW-11", None))
        self.assertEqual(
            [o["status"] for o in self._read()],
            ["new"] + ["done"] * 9 + ["awaiting_payment"])
        with mock.patch("sys.stdout", io.StringIO()), \
             mock.patch.object(client_orders, "cmd_client_run",
                               return_value=0) as run:
            rc = client_orders.cmd_process_queue({})
        self.assertEqual(rc, 0)
        # الطلب الأول المجاني أُنتج؛ الـ11 تُخطى.
        run.assert_called_once_with({}, "QS-FLOW-1")
        self.assertEqual(self._read()[-1]["status"], "awaiting_payment")
        # الإنتاج الحقيقي يعلّم الطلب done عند النجاح — نحاكي ذلك
        # حتى لا يعيد الطابور إنتاج الطلب الأول في التشغيل الثاني.
        with mock.patch("sys.stdout", io.StringIO()):
            client_orders.update_order("QS-FLOW-1", status="done")
            client_orders.confirm_payment("QS-FLOW-11")
        with mock.patch("sys.stdout", io.StringIO()), \
             mock.patch.object(client_orders, "cmd_client_run",
                               return_value=0) as run:
            rc = client_orders.cmd_process_queue({})
        self.assertEqual(rc, 0)
        run.assert_called_once_with({}, "QS-FLOW-11")

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


if __name__ == "__main__":
    unittest.main()
