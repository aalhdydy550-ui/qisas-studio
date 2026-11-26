#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات إخفاء المعرّفات القابل للعكس (lib.id_mask).

تعمل بـ `python3 -m unittest tests.test_id_mask -v` من مجلد studio.
بلا ملفات خارجية وبلا شبكة.
"""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import id_mask


class TestMaskText(unittest.TestCase):
    def test_email_long_id_and_phone_in_one_text(self):
        text = (
            "تواصل مع ayman_201511@yahoo.com بخصوص الصفحة "
            "1048148471706586 أو على +201001234567"
        )
        masked, mapping = id_mask.mask_text(text)
        self.assertEqual(
            masked,
            "تواصل مع [EMAIL:1] بخصوص الصفحة [ID:1] أو على [PHONE:1]",
        )
        self.assertEqual(mapping["EMAIL:1"], "ayman_201511@yahoo.com")
        self.assertEqual(mapping["ID:1"], "1048148471706586")
        self.assertEqual(mapping["PHONE:1"], "+201001234567")

    def test_egyptian_mobile_01_form(self):
        masked, mapping = id_mask.mask_text("اتصل على 01012345678 من فضلك")
        self.assertEqual(masked, "اتصل على [PHONE:1] من فضلك")
        self.assertEqual(mapping["PHONE:1"], "01012345678")

    def test_round_trip_returns_original(self):
        text = (
            "البريد ayman_201511@yahoo.com والصفحة 1048148471706586 "
            "والهاتف +201001234567 والفيديو 7712431963046432008"
        )
        masked, mapping = id_mask.mask_text(text)
        self.assertEqual(id_mask.unmask_text(masked, mapping), text)

    def test_same_value_same_token_deterministic(self):
        masked, mapping = id_mask.mask_text(
            "أرسل إلى ayman_201511@yahoo.com ثم إلى ayman_201511@yahoo.com "
            "والصفحة 1048148471706586 مرتين 1048148471706586"
        )
        self.assertEqual(
            masked,
            "أرسل إلى [EMAIL:1] ثم إلى [EMAIL:1] "
            "والصفحة [ID:1] مرتين [ID:1]",
        )
        self.assertEqual(len(mapping), 2)

    def test_mapping_continues_across_calls(self):
        mapping = {}
        masked1, mapping = id_mask.mask_text("ayman_201511@yahoo.com", mapping)
        masked2, mapping = id_mask.mask_text("ayman_201511@yahoo.com", mapping)
        self.assertEqual(masked1, masked2)
        self.assertEqual(masked1, "[EMAIL:1]")
        masked3, mapping = id_mask.mask_text("other@example.com", mapping)
        self.assertEqual(masked3, "[EMAIL:2]")
        self.assertEqual(len(mapping), 2)

    def test_short_numbers_not_masked(self):
        text = "في 2026 نجح 3007 اختبارات خلال 45 ثانية من 60 ثانية"
        masked, mapping = id_mask.mask_text(text)
        self.assertEqual(masked, text)
        self.assertEqual(mapping, {})

    def test_arabic_text_preserved_verbatim(self):
        text = "قصة الأرملة عائشة عبرة عظيمة عن الصبر والرضا"
        masked, mapping = id_mask.mask_text(text)
        self.assertEqual(masked, text)
        self.assertEqual(mapping, {})

    def test_empty_input(self):
        masked, mapping = id_mask.mask_text("")
        self.assertEqual(masked, "")
        self.assertEqual(mapping, {})
        masked, mapping = id_mask.mask_text("", {"EMAIL:1": "a@b.com"})
        self.assertEqual(masked, "")
        self.assertEqual(mapping, {"EMAIL:1": "a@b.com"})

    def test_unmask_unknown_token_left_as_is(self):
        self.assertEqual(
            id_mask.unmask_text("اتصل بـ [PHONE:9]", {"PHONE:1": "01012345678"}),
            "اتصل بـ [PHONE:9]",
        )

    def test_sequential_numbering_per_type(self):
        masked, mapping = id_mask.mask_text(
            "a@b.com و c@d.com والصفحة 1048148471706586 ثم 1317605784778181"
        )
        self.assertEqual(
            masked, "[EMAIL:1] و [EMAIL:2] والصفحة [ID:1] ثم [ID:2]"
        )


class TestRedactSecrets(unittest.TestCase):
    def test_sk_key_redacted_and_not_in_mapping(self):
        text = "المفتاح sk-abc123XYZ456 لا تشاركه"
        self.assertEqual(
            id_mask.redact_secrets(text), "المفتاح [REDACTED] لا تشاركه"
        )
        masked, mapping = id_mask.mask_text(text)
        # الإخفاء القابل للعكس لا يمسّ الأسرار ولا يدخلها في الـmapping.
        self.assertEqual(masked, text)
        self.assertEqual(mapping, {})

    def test_ghp_token_redacted(self):
        text = "الرمز ghp_AbCdEfGh1234567890 سري"
        self.assertEqual(id_mask.redact_secrets(text), "الرمز [REDACTED] سري")
        _, mapping = id_mask.mask_text(text)
        self.assertEqual(mapping, {})

    def test_bearer_and_api_key_and_akia_redacted(self):
        text = (
            "Authorization: Bearer abc123token "
            "api_key=secret-value AKIAIOSFODNN7EXAMPLE"
        )
        self.assertEqual(
            id_mask.redact_secrets(text),
            "Authorization: [REDACTED] [REDACTED] [REDACTED]",
        )

    def test_redact_empty(self):
        self.assertEqual(id_mask.redact_secrets(""), "")


class TestMaskRecord(unittest.TestCase):
    def test_nested_structure_and_original_untouched(self):
        original = {
            "title": "قصة عائشة",
            "contact": "ayman_201511@yahoo.com",
            "page_id": "1048148471706586",
            "nested": {"phone": "+201001234567", "tags": ["قصة", "عبرة"]},
            "items": [{"owner": "other@example.com"}],
            "year": 2026,
            "views": 3007,
        }
        snapshot = copy.deepcopy(original)
        masked, mapping = id_mask.mask_record(original)
        self.assertEqual(original, snapshot)  # الأصل لم يُعدَّل
        self.assertEqual(masked["title"], "قصة عائشة")
        self.assertEqual(masked["contact"], "[EMAIL:1]")
        self.assertEqual(masked["page_id"], "[ID:1]")
        self.assertEqual(masked["nested"]["phone"], "[PHONE:1]")
        self.assertEqual(masked["nested"]["tags"], ["قصة", "عبرة"])
        self.assertEqual(masked["items"][0]["owner"], "[EMAIL:2]")
        self.assertEqual(masked["year"], 2026)
        self.assertEqual(masked["views"], 3007)
        # المفاتيح تُترك كما هي حتى لو طابقت نمطًا.
        self.assertIn("page_id", masked)
        # جولة ذهاب وإياب على القيم المخفية.
        self.assertEqual(
            id_mask.unmask_text(
                masked["contact"], mapping
            ),
            "ayman_201511@yahoo.com",
        )
        self.assertEqual(
            id_mask.unmask_text(masked["nested"]["phone"], mapping),
            "+201001234567",
        )

    def test_mask_record_empty(self):
        masked, mapping = id_mask.mask_record({})
        self.assertEqual(masked, {})
        self.assertEqual(mapping, {})


if __name__ == "__main__":
    unittest.main()
