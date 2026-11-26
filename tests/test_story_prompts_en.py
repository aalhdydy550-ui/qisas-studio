#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات الموجّه الإنجليزي الأصلي — الجولة v0.1.53 (الطلب 4، EN-05).

`lib/prompts/story_system_en.md` موجّه نظام إنجليزي أصلي (لا
ترجمة حرفية للعربي) بنفس بنية الخمس ضربات: هوك صادم من جملة
واحدة يخفي النهاية ← قرار أخلاقي واحد ← انقلاب/عوض ← عبرة من
سطر واحد تُستنتج لا تُلَقَّن ← سؤال ختامي محيّر؛ و`load_system_prompt`
واعٍ باللغة (العربي افتراضيًا دائمًا).

القصص الثلاث هنا عينات إنجليزية أصلية (fixtures) مكتوبة
لهذا الملف، وكل واحدة تمر على فحص البنية نفسه الذي يجب أن
تمر عليه أي قصة إنجليزية مولّدة: هوك جملة واحدة + عبرة من
سطر واحد + سؤال ختامي ينتهي بعلامة استفهام.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import omniroute_client

PROMPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "lib", "prompts")
PROMPT_PATH_EN = os.path.join(PROMPTS_DIR, "story_system_en.md")
PROMPT_PATH_AR = os.path.join(PROMPTS_DIR, "story_system.md")

# نطاق الحروف العربية — لا حرف عربي واحد مسموح في الموجّه
# الإنجليزي ولا في العينات (توليد أصلي، لا ترجمة حرفية).
_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")

# القواعد الدائمة التي يجب أن يحملها الموجّه الإنجليزي
# (مرآة روح العربي بصياغة إنجليزية أصلية).
REQUIRED_RULES_EN = (
    "always a man",          # الراوي رجل دائمًا
    "40–60 seconds",         # مدة الفيديو
    "one shocking sentence",  # هوك جملة واحدة
    "never a sermon",        # العبرة تُستنتج لا تُلَقَّن
    "closing question",      # سؤال ختامي محيّر
    "No sensitive content",  # بلا محتوى حساس/رعب
    "short scenes",          # القصة مقسمة مشاهد قصيرة
)

# أمثلة إنجليزية: أسماء/أماكن/عملات.
REQUIRED_EXAMPLES_EN = ("James", "Ohio", "$20,000")


def check_story_structure(story):
    """فحص بنية قصة إنجليزية واحدة (هوك/عبرة/سؤال).

    يرفع AssertionError برسالة عربية توضح الضربة المخالفة.
    """
    hook = (story.get("hook") or "").strip()
    moral = (story.get("moral") or "").strip()
    question = (story.get("closing_question") or "").strip()
    title = story.get("title") or "القصة"
    # الهوك جملة واحدة: سطر واحد ينتهي بعلامة إنهاء جملة
    # واحدة فقط (بلا «Mr.» أو اختصار يخفي نقطة ثانية).
    assert hook, "هوك فارغ في %s" % title
    assert "\n" not in hook, "الهوك أكثر من سطر في %s" % title
    ends = re.findall(r"[.!?]", hook)
    assert len(ends) == 1, \
        "الهوك ليس جملة واحدة في %s (علامات إنهاء: %d)" \
        % (title, len(ends))
    # العبرة سطر واحد.
    assert moral, "عبرة فارغة في %s" % title
    assert "\n" not in moral, "العبرة أكثر من سطر في %s" % title
    # السؤال الختامي ينتهي بعلامة استفهام.
    assert question, "سؤال ختامي فارغ في %s" % title
    assert question.endswith("?"), \
        "السؤال الختامي لا ينتهي بعلامة استفهام في %s" % title
    # كل حقل غير فارغ نصًا إنجليزيًا (بلا عربي).
    for field, value in (("hook", hook), ("moral", moral),
                         ("closing_question", question)):
        assert not _ARABIC_RE.search(value), \
            "حرف عربي في حقل %s من %s" % (field, title)


# 3 قصص عينة إنجليزية أصلية (fixtures) — أمانة، برّ والدين،
# وظلم قريب؛ كل واحدة ببنية الخمس ضربات ومدة 40–60 ثانية.
SAMPLE_STORIES_EN = (
    {
        "title": "The bag in the trash",
        "hero": "James",
        "hook": ("James, a delivery driver in Ohio, found a leather "
                 "bag in the trash — and inside it, $20,000 and a "
                 "silver pistol."),
        "choice": ("Keep the money, or return the bag to its owner."),
        "twist": ("He returned the bag, and two weeks later a job "
                  "offer arrived from the last place he expected."),
        "moral": ("What you give up for the sake of what is right "
                  "is never really lost."),
        "closing_question": ("If you found $20,000 that was not "
                             "yours, what would you do?"),
    },
    {
        "title": "The phone call after ten years",
        "hero": "Michael",
        "hook": ("Michael had not called his mother in ten years — "
                 "and one rainy night in Chicago, his phone rang "
                 "with her name on the screen."),
        "choice": ("Let it ring, or answer the call he had avoided "
                   "for a decade."),
        "twist": ("He answered, and the voice on the other end "
                  "forgave him before he could even apologize."),
        "moral": ("A kind word to a parent is never too late until "
                  "it is."),
        "closing_question": ("When was the last time you said a kind "
                             "word to your father or your mother?"),
    },
    {
        "title": "The letter from seven years ago",
        "hero": "Sarah",
        "hook": ("Sarah lost her house to her own brother in a "
                 "single night — and everyone in Texas believed "
                 "his story, not hers."),
        "choice": ("Stay silent and walk away, or fight for the "
                   "truth with nothing but her word."),
        "twist": ("Then a letter written seven years earlier surfaced, "
                  "and the truth turned everything upside down."),
        "moral": ("Injustice never lasts — sooner or later, the "
                  "truth comes out."),
        "closing_question": ("If you were in Sarah's place, what "
                             "would you do?"),
    },
)


class TestEnglishPromptFile(unittest.TestCase):
    def test_file_exists_and_has_five_beat_structure(self):
        self.assertTrue(os.path.isfile(PROMPT_PATH_EN),
                        "ملف الموجّه الإنجليزي غائب: %s" % PROMPT_PATH_EN)
        with open(PROMPT_PATH_EN, encoding="utf-8") as fh:
            text = fh.read()
        self.assertGreater(len(text.strip()), 200)
        for rule in REQUIRED_RULES_EN:
            self.assertIn(rule, text,
                          "قاعدة دائمة غائبة من الموجّه الإنجليزي: %s"
                          % rule)
        for example in REQUIRED_EXAMPLES_EN:
            self.assertIn(example, text,
                          "مثال إنجليزي غائب من الموجّه: %s" % example)

    def test_no_arabic_in_english_prompt(self):
        with open(PROMPT_PATH_EN, encoding="utf-8") as fh:
            text = fh.read()
        match = _ARABIC_RE.search(text)
        self.assertIsNone(match,
                          "حرف عربي في الموجّه الإنجليزي عند: %r"
                          % (text[max(0, match.start() - 20):
                                  match.start() + 20]
                             if match else ""))


class TestLoadSystemPromptLang(unittest.TestCase):
    def test_en_returns_english_prompt_verbatim(self):
        with open(PROMPT_PATH_EN, encoding="utf-8") as fh:
            expected = fh.read()
        self.assertEqual(omniroute_client.load_system_prompt("en"),
                         expected)

    def test_ar_returns_arabic_prompt_verbatim(self):
        with open(PROMPT_PATH_AR, encoding="utf-8") as fh:
            expected = fh.read()
        self.assertEqual(omniroute_client.load_system_prompt("ar"),
                         expected)

    def test_no_arg_returns_arabic(self):
        with open(PROMPT_PATH_AR, encoding="utf-8") as fh:
            expected = fh.read()
        self.assertEqual(omniroute_client.load_system_prompt(), expected)

    def test_unknown_lang_falls_back_to_arabic(self):
        with open(PROMPT_PATH_AR, encoding="utf-8") as fh:
            expected = fh.read()
        for lang in ("fr", "xx", "", None):
            self.assertEqual(
                omniroute_client.load_system_prompt(lang), expected,
                "لغة غير معروفة لم ترجع للعربي: %r" % (lang,))
        # "EN" الكبيرة تُقبل كإنجليزية (تطبيع الحالة).
        self.assertEqual(
            omniroute_client.load_system_prompt("EN"),
            omniroute_client.load_system_prompt("en"))
        # التطبيع يأخذ أول حرفين فقط (كما في story_templates):
        # "ENGLISH" تُقرأ en.
        self.assertEqual(
            omniroute_client.load_system_prompt("ENGLISH"),
            omniroute_client.load_system_prompt("en"))

    def test_en_and_ar_differ(self):
        self.assertNotEqual(
            omniroute_client.load_system_prompt("en"),
            omniroute_client.load_system_prompt("ar"))


class TestSampleStoriesStructure(unittest.TestCase):
    def test_three_samples_present(self):
        self.assertEqual(len(SAMPLE_STORIES_EN), 3)

    def test_each_sample_passes_structure_check(self):
        for story in SAMPLE_STORIES_EN:
            with self.subTest(title=story["title"]):
                check_story_structure(story)

    def test_each_sample_has_all_five_beats(self):
        for story in SAMPLE_STORIES_EN:
            for beat in ("hook", "choice", "twist", "moral",
                         "closing_question"):
                self.assertTrue((story.get(beat) or "").strip(),
                                "ضربة %s فارغة في %s"
                                % (beat, story["title"]))

    def test_no_arabic_in_samples(self):
        for story in SAMPLE_STORIES_EN:
            for field, value in story.items():
                self.assertIsNone(
                    _ARABIC_RE.search(value),
                    "حرف عربي في %s.%s" % (story["title"], field))


if __name__ == "__main__":
    unittest.main()
