#!/usr/bin/env python3
"""اختبارات مولّد أفكار القصص (lib.ideas).

تعمل بـ `python3 -m unittest discover -s tests -v`.
كل الكتابة في مجلدات مؤقتة — لا يُمس ملف الطابور الحقيقي
أبدًا، ولا شبكة في أي اختبار (chat_fn مزيفة).
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import ideas
from lib import queue as queue_lib

QUEUE_TEXT = """# طابور قصص

## المنشور

1. **منقشة الرغيف (عبدالجبار وزهرة وفاطنة)** — نُشر الجزء 1
2. **النجار الأمين** — نُشر

## المجدول

- **حذاء أبي (نسخة محسّنة)** — مجدول 2026-11-21 19:00

## في الانتظار

3. **عائشة الأرملة في السودان** — تحتاج 3 أجزاء
4. **العنزة المباركة** — تحتاج جزأين
5. **عجائب الصدقة** — منشور واحد
"""


def _queue_file(tmpdir, text=QUEUE_TEXT):
    path = os.path.join(tmpdir, "queue.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


class TestHookRules(unittest.TestCase):
    def test_hook_starting_with_digit_rejected(self):
        self.assertFalse(ideas.valid_hook("3 قصص غيّرت حياتي"))
        self.assertFalse(ideas.valid_hook("٥ أشياء لا تعرفها"))

    def test_hook_normal_accepted(self):
        self.assertTrue(ideas.valid_hook("حماتي دخلت أوضتي وأنا نايمة!"))

    def test_hook_empty_rejected(self):
        self.assertFalse(ideas.valid_hook(""))
        self.assertFalse(ideas.valid_hook("   "))

    def test_hook_with_ass_tags_rejected(self):
        # اختبار انحدار (اختراق 2026-11-22): وسوم ASS في الهوك
        # كانت تمرّ إلى المسودة والطابور.
        self.assertFalse(ideas.valid_hook("نص {\\fs200}خدعة"))
        self.assertFalse(ideas.valid_hook("نص {\\pos(10,10)} هنا"))
        self.assertFalse(ideas.valid_hook("شرطة \\ هنا"))
        self.assertFalse(ideas.valid_hook("هوك طويل " + "x" * 140))


class TestDedup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.queue = _queue_file(self.tmp)

    def test_existing_titles_cover_all_sections(self):
        cores = ideas.existing_titles(self.queue)
        self.assertIn("منقشة الرغيف", cores)
        self.assertIn("النجار الأمين", cores)
        self.assertIn("حذاء أبي", cores)
        self.assertIn("عائشة الأرملة في السودان", cores)
        self.assertIn("العنزة المباركة", cores)

    def test_duplicate_core_variants(self):
        cores = ideas.existing_titles(self.queue)
        # جوهر بلا أقواس يطابق العنوان بالأقواس
        self.assertTrue(ideas.is_duplicate("منقشة الرغيف", cores))
        # عنوان أقصر يبدأ به عنوان موجود (أو العكس) = مكرر
        self.assertTrue(ideas.is_duplicate("عائشة الأرملة", cores))
        self.assertTrue(ideas.is_duplicate(
            "عائشة الأرملة في السودان — الجزء 2", cores))

    def test_new_title_not_duplicate(self):
        cores = ideas.existing_titles(self.queue)
        self.assertFalse(ideas.is_duplicate("لقيت محفظة فيها مليون",
                                            cores))

    def test_missing_queue_file_means_no_dedup(self):
        self.assertEqual(
            ideas.existing_titles(os.path.join(self.tmp, "nope.md")),
            set())


class TestParseLlm(unittest.TestCase):
    def test_good_lines_parsed(self):
        text = ("قصة جديدة | هوك صادم! | العبرة واضحة. | 2 | سؤال؟\n"
                "أخرى | هوك ثانٍ! | عبرة ثانية. | 1 | سؤال ثانٍ؟\n")
        out = ideas.parse_llm_ideas(text)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["title"], "قصة جديدة")
        self.assertEqual(out[0]["parts"], 2)
        self.assertEqual(out[1]["question"], "سؤال ثانٍ؟")

    def test_hook_starting_with_digit_dropped(self):
        text = "عنوان | 3 أشياء حدثت! | عبرة. | 1 | سؤال؟\n"
        self.assertEqual(ideas.parse_llm_ideas(text), [])

    def test_malformed_lines_dropped(self):
        text = "بلا فواصل أصلًا\nعنوان فقط | هوك\n"
        self.assertEqual(ideas.parse_llm_ideas(text), [])

    def test_quotes_stripped(self):
        text = '"عنوان" | "هوك صادم!" | "عبرة." | 1 | "سؤال؟"\n'
        out = ideas.parse_llm_ideas(text)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["title"], "عنوان")
        self.assertEqual(out[0]["hook"], "هوك صادم!")


class TestGenerate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.queue = _queue_file(self.tmp)

    def test_offline_fallback_no_network(self):
        got, notes = ideas.generate_ideas(self.queue, count=5,
                                          chat_fn=None)
        self.assertEqual(len(got), 5)
        for idea in got:
            self.assertEqual(idea["source"], "local")
            self.assertTrue(ideas.valid_hook(idea["hook"]))
            self.assertTrue(idea["moral"])
            self.assertIn(idea["parts"], (1, 2, 3))
        cores = ideas.existing_titles(self.queue)
        for idea in got:
            self.assertFalse(ideas.is_duplicate(idea["title"], cores))

    def test_local_fallback_skips_duplicates(self):
        # طابور فيه عنوان من البنك نفسه
        dup_queue = _queue_file(
            self.tmp, QUEUE_TEXT + "\n## في الانتظار\n\n"
            "6. **لقيت محفظة فيها مليون** — منشور واحد\n")
        got, _notes = ideas.generate_ideas(dup_queue, count=5,
                                           chat_fn=None)
        titles = [i["title"] for i in got]
        self.assertNotIn("لقيت محفظة فيها مليون", titles)

    def test_llm_success_used_first(self):
        def fake_chat(prompt):
            return ("فكرة النموذج | هوك النموذج! | عبرة النموذج. "
                    "| 1 | سؤال النموذج؟\n")
        got, _notes = ideas.generate_ideas(self.queue, count=3,
                                           chat_fn=fake_chat)
        self.assertEqual(got[0]["title"], "فكرة النموذج")
        self.assertEqual(got[0]["source"], "omniroute")
        self.assertEqual(len(got), 3)

    def test_llm_failure_falls_back_to_local(self):
        def boom(prompt):
            raise RuntimeError("بلا شبكة")

        got, notes = ideas.generate_ideas(self.queue, count=3,
                                          chat_fn=boom)
        self.assertEqual(len(got), 3)
        self.assertTrue(all(i["source"] == "local" for i in got))
        self.assertTrue(any("البديل المحلي" in n for n in notes))

    def test_theme_filter(self):
        got, _notes = ideas.generate_ideas(
            self.queue, count=3, theme="الأمانة", chat_fn=None)
        self.assertEqual(len(got), 3)
        self.assertTrue(all(i["theme"] == "الأمانة" for i in got))


class TestAddIdea(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.queue = _queue_file(self.tmp)
        self.stories_dir = os.path.join(self.tmp, "queue")

    def test_add_idea_to_queue(self):
        got, _notes = ideas.generate_ideas(self.queue, count=1,
                                           chat_fn=None)
        result = ideas.add_idea(self.queue, got[0], self.stories_dir)
        self.assertEqual(result["title"], got[0]["title"])
        self.assertTrue(os.path.isfile(result["text_file"]))
        with open(self.queue, encoding="utf-8") as f:
            self.assertIn(got[0]["title"], f.read())

    def test_add_duplicate_idea_rejected(self):
        got, _notes = ideas.generate_ideas(self.queue, count=1,
                                           chat_fn=None)
        ideas.add_idea(self.queue, got[0], self.stories_dir)
        with self.assertRaises(queue_lib.QueueError):
            ideas.add_idea(self.queue, got[0], self.stories_dir)


if __name__ == "__main__":
    unittest.main()
