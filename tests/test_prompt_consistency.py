#!/usr/bin/env python3
"""اختبارات موجّه النظام المشترك — جولة v0.1.37 (مقترح tinker رقم 9).

ملف واحد `lib/prompts/story_system.md` هو مصدر قواعد الأسلوب
لكل استدعاء LLM في المشروع. الاختبارات هنا تضمن:
- الملف موجود ويحوي القواعد الدائمة الست.
- `load_system_prompt()` يرجعه حرفيًا بلا تعديل.
- `chat()` يستخدمه افتراضيًا في كل الأوامر، والموجّه الصريح
  الممرَّر من المتصل يغلبه.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import omniroute_client

PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "lib", "prompts", "story_system.md")

# القواعد الدائمة الست — إن تغيّرت صياغة واحدة في الملف،
# عدّل هذا الاختبار معها صراحة (لا تحذف القاعدة بصمت).
REQUIRED_RULES = (
    "الراوي رجل",
    "لا يبدأ برقم",
    "40–60 ثانية",
    "بكرة 7 مساءً",
    "عندك قصة حصلتلك؟",
    "#قصص_وعبر",
)


class TestSystemPromptFile(unittest.TestCase):
    def test_file_exists_and_has_all_rules(self):
        self.assertTrue(os.path.isfile(PROMPT_PATH),
                        "ملف الموجّه المشترك غائب: %s" % PROMPT_PATH)
        with open(PROMPT_PATH, encoding="utf-8") as fh:
            text = fh.read()
        self.assertGreater(len(text.strip()), 200)
        for rule in REQUIRED_RULES:
            self.assertIn(rule, text,
                          "القاعدة الدائمة غائبة من الموجّه: %s" % rule)

    def test_loader_returns_file_verbatim(self):
        with open(PROMPT_PATH, encoding="utf-8") as fh:
            expected = fh.read()
        self.assertEqual(omniroute_client.load_system_prompt(), expected)

    def test_loader_missing_file_returns_empty(self):
        with mock.patch.object(omniroute_client, "_SYSTEM_PROMPT_PATH",
                               "/tmp/no-such-prompt-xyz.md"):
            self.assertEqual(omniroute_client.load_system_prompt(), "")


class TestChatUsesSharedPrompt(unittest.TestCase):
    def test_chat_defaults_to_shared_prompt(self):
        captured = {}

        def fake_cli(model, prompt, system=None, max_tokens=200,
                     temperature=0.7, timeout=180):
            captured["system"] = system
            captured["prompt"] = prompt
            return "رد تجريبي"

        with mock.patch.object(omniroute_client, "chat_cli", fake_cli):
            text, via, model = omniroute_client.chat("اكتب قصة",
                                                     "ddgw/gpt-5.4-mini")
        self.assertEqual(text, "رد تجريبي")
        self.assertEqual(captured["system"],
                         omniroute_client.load_system_prompt())
        # الموجّه يُمرَّر كموجّه نظام، لا يُلصق في موجّه المستخدم.
        self.assertNotIn("قصص وعبر", captured["prompt"])

    def test_explicit_system_overrides_shared(self):
        captured = {}

        def fake_cli(model, prompt, system=None, max_tokens=200,
                     temperature=0.7, timeout=180):
            captured["system"] = system
            return "رد تجريبي"

        with mock.patch.object(omniroute_client, "chat_cli", fake_cli):
            omniroute_client.chat("اكتب قصة", "ddgw/gpt-5.4-mini",
                                  system="موجّه خاص بالاختبار")
        self.assertEqual(captured["system"], "موجّه خاص بالاختبار")


if __name__ == "__main__":
    unittest.main()
