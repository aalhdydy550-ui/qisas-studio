#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات هوية الاختبار العشوائية المزروعة (v0.1.37 — البند 13).

المولّد يأخذ بذرة ثابتة ويولّد N رقم واتساب مختلفًا بصيغ
مختلفة لكل تشغيل؛ واختبار يؤكد أن الأرقام المولدة مختلفة
عبر الحالات وأن التطبيع يجمع صيغ الرقم الواحد كعميل واحد.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import client_orders
from lib import test_identity


class TestSeededTestIdentity(unittest.TestCase):
    def test_same_seed_same_numbers(self):
        first = test_identity.fake_whatsapp_numbers(count=10)
        second = test_identity.fake_whatsapp_numbers(count=10)
        self.assertEqual(first, second)

    def test_different_seed_different_numbers(self):
        base = test_identity.fake_whatsapp_numbers(count=10)
        other = test_identity.fake_whatsapp_numbers(seed=1, count=10)
        self.assertNotEqual(base, other)

    def test_generated_numbers_distinct_and_valid(self):
        numbers = test_identity.fake_whatsapp_numbers(count=10)
        self.assertEqual(len(numbers), 10)
        canonical = [test_identity.canonical_whatsapp(n)
                     for n in numbers]
        self.assertEqual(len(set(canonical)), 10)
        for n in numbers:
            # كل رقم مولد صالح عند بوابة العملاء الحقيقية.
            self.assertEqual(client_orders.validate_whatsapp(n), n)

    def test_generated_numbers_use_all_three_formats(self):
        numbers = test_identity.fake_whatsapp_numbers(count=10)
        forms = {"local": 0, "plus": 0, "double_zero": 0}
        for n in numbers:
            if n.startswith("0020"):
                forms["double_zero"] += 1
            elif n.startswith("+20"):
                forms["plus"] += 1
            else:
                forms["local"] += 1
        self.assertTrue(all(v >= 1 for v in forms.values()),
                        "الصيغ المولدة: %s" % (forms,))

    def test_canonical_groups_three_formats_as_one_client(self):
        base = test_identity.fake_whatsapp_numbers(count=1)[0]
        canon = test_identity.canonical_whatsapp(base)
        forms = ["0" + canon, "+20" + canon, "0020" + canon]
        self.assertEqual(
            [test_identity.canonical_whatsapp(f) for f in forms],
            [canon] * 3)
        # والتطبيع المحلي يتفق مع تطبيع بوابة العملاء الحقيقية.
        self.assertEqual(
            [client_orders._canonical_whatsapp(f) for f in forms],
            [canon] * 3)

    def test_count_zero_raises(self):
        with self.assertRaises(ValueError):
            test_identity.fake_whatsapp_numbers(count=0)


if __name__ == "__main__":
    unittest.main()
