#!/usr/bin/env python3
"""اختبارات تدفق «اطلب فيديو» (الجولة v0.1.43، البند 1).

تصنيف الطلب (قصة/موضوع)، توليد قصة من موضوع بـchat_fn
مزيفة، تمرير نص قصة كما هو، فشل LLM بخطأ عربي واضح،
وتنسيق الطلب الكامل (طابور + إنتاج) بـrun_fn مزيفة.
بلا شبكة وبلا إنتاج فيديو حقيقي — الإنتاج والطابور
يُحاكيان بالحقن، عدا اختبار واحد لمسار الحفظ الافتراضي
على ملف طابور مؤقت.
"""
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import request_flow
from lib.request_flow import (
    NoProjectError,
    RequestFlowError,
    classify_request,
    extract_title,
    request_to_run,
    request_to_story,
)

# قصة كاملة (أكثر من 80 كلمة — تُصنَّف قصة بالطول وحده).
LONG_STORY = (
    "كان يا ما كان، في قرية صغيرة على أطراف النيل، عاشت امرأة "
    "اسمها عائشة مع أولادها الثلاثة بعد وفاة زوجها، وكانت تعمل "
    "ليلًا ونهارًا لتطعمهم من حلال. وفي يوم من الأيام جاءتها "
    "حماتها وطردتها من البيت بلا رحمة، فقالت عائشة: حسبي الله "
    "ونعم الوكيل، ثم خرجت بأولادها إلى بيت صغير مهجور. وبعد "
    "ثلاث سنوات من الصبر والعمل الشاق، فتح الله عليها باب رزق "
    "لم تكن تحلم به، وعاد إليها حقها كاملًا أمام الجميع، وعرفت "
    "القرية كلها أن الظلم لا يدوم وأن الصبر مفتاح الفرج، وأن "
    "من ترك شيئًا لله عوّضه الله خيرًا منه، فكانت عبرة لكل من "
    "سمع قصتها في كل مكان."
)

# قصة متوسطة (30+ كلمة) بعلامتي سرد على الأقل — تُصنَّف قصة
# بالقاعدة الثانية لا بالطول وحده.
MEDIUM_STORY = (
    "كان هناك رجل فقير يعيش في قرية صغيرة مع زوجته وأولاده "
    "الخمسة، وفي يوم من الأيام وجد محفظة مليئة بالمال على "
    "الطريق، فقال لزوجته: هذا مال ليس لنا، ثم ذهب إلى صاحب "
    "المحفظة وأعادها إليه رغم فقره الشديد"
)

# قصة مولّدة مزيفة (أكثر من 20 كلمة — فوق حد القبول).
FAKE_GENERATED = (
    "في ليلة مظلمة وقف رجل فقير أمام باب جاره الغني يطلب "
    "لقمة لأولاده الجائعين، فطرده الحارس بلا رحمة، وبعد سبع "
    "سنوات انقلب الحال فصار الفقير صاحب مال والغني يطرق بابه، "
    "فعرف الجميع أن الدنيا دوّارة وأن العبرة في النهاية، وأن "
    "من يرحم يُرحم، فهل كنت ستفتح الباب؟ #قصة حقيقية"
)


def _fake_chat(return_text=FAKE_GENERATED):
    calls = []

    def chat_fn(prompt):
        calls.append(prompt)
        return return_text

    chat_fn.calls = calls
    return chat_fn


def _fake_queue_add(number=7):
    calls = []

    def queue_add_fn(cfg, title, story_text, studio_dir):
        calls.append({"cfg": cfg, "title": title,
                      "story_text": story_text,
                      "studio_dir": studio_dir})
        return {"number": number, "title": title,
                "text_file": "queue/%d-x.txt" % number}

    queue_add_fn.calls = calls
    return queue_add_fn


def _fake_run(output="/tmp/out/request.mp4"):
    calls = []

    def run_fn(cfg, story_text, title, project, out_path,
               allow_fallback, queue_number):
        calls.append({"cfg": cfg, "story_text": story_text,
                      "title": title, "project": project,
                      "out_path": out_path,
                      "allow_fallback": allow_fallback,
                      "queue_number": queue_number})
        return output

    run_fn.calls = calls
    return run_fn


class TestClassifyRequest(unittest.TestCase):
    def test_topic_short_phrase(self):
        self.assertEqual(classify_request("قصة عن الأمانة"), "topic")
        self.assertEqual(classify_request("ظلم الحماة"), "topic")

    def test_topic_with_one_marker_stays_topic(self):
        # جملة قصيرة فيها علامة سرد واحدة (ثم) — ما زالت موضوعًا.
        self.assertEqual(
            classify_request("قصة عن رجل ظلمته حماته ثم طردته"),
            "topic")

    def test_topic_question(self):
        self.assertEqual(
            classify_request("ممكن قصة عن بر الوالدين؟"), "topic")

    def test_story_long_text(self):
        self.assertEqual(classify_request(LONG_STORY), "story")

    def test_story_medium_with_markers(self):
        self.assertEqual(classify_request(MEDIUM_STORY), "story")

    def test_empty_raises(self):
        for bad in ("", "   ", "\n\t", None, 123):
            with self.assertRaises(ValueError, msg=repr(bad)):
                classify_request(bad)


class TestExtractTitle(unittest.TestCase):
    def test_first_sentence(self):
        self.assertEqual(
            extract_title("عائشة الأرملة ظلمتها حماتها. ثم صبرت "
                          "ثلاث سنوات."),
            "عائشة الأرملة ظلمتها حماتها")

    def test_long_title_truncated_on_word(self):
        title = extract_title(
            "هذه جملة أولى طويلة جدًا تتجاوز الستين حرفًا بلا شك "
            "وتستمر بعد ذلك بكلمات كثيرة لا تنتهي أبدًا")
        self.assertLessEqual(len(title), 61)
        self.assertTrue(title.endswith("…"))

    def test_star_removed_for_queue(self):
        self.assertNotIn("*", extract_title("قصة *مهمة* عن الأمانة."))

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            extract_title("   ")


class TestRequestToStory(unittest.TestCase):
    def test_story_passed_through_unchanged(self):
        calls = []

        def chat_fn(prompt):
            calls.append(prompt)
            raise AssertionError("لا يُستدعى LLM لنص قصة")

        self.assertEqual(request_to_story(chat_fn, LONG_STORY),
                         LONG_STORY.strip())
        self.assertEqual(calls, [])

    def test_story_quotes_stripped(self):
        self.assertEqual(
            request_to_story(None, "«" + LONG_STORY + "»"),
            LONG_STORY.strip())

    def test_topic_generated_via_chat_fn(self):
        chat_fn = _fake_chat()
        story = request_to_story(chat_fn, "الأمانة")
        self.assertEqual(story, FAKE_GENERATED)
        self.assertEqual(len(chat_fn.calls), 1)
        # الموجّه يحمل الموضوع وقواعد الأسلوب.
        self.assertIn("الأمانة", chat_fn.calls[0])
        self.assertIn("هوك صادم", chat_fn.calls[0])
        self.assertIn("قصة حقيقية", chat_fn.calls[0])
        self.assertIn("40–60", chat_fn.calls[0])

    def test_topic_without_chat_fn_raises(self):
        with self.assertRaises(RequestFlowError):
            request_to_story(None, "الأمانة")

    def test_llm_failure_is_clear_arabic_error(self):
        def failing_chat(prompt):
            raise RuntimeError("429 quota exceeded on all providers")

        with self.assertRaises(RequestFlowError) as ctx:
            request_to_story(failing_chat, "الأمانة")
        message = str(ctx.exception)
        self.assertIn("فشل توليد القصة", message)
        self.assertIn("llm-status", message)

    def test_empty_generation_raises(self):
        with self.assertRaises(RequestFlowError) as ctx:
            request_to_story(_fake_chat("   "), "الأمانة")
        self.assertIn("فارغًا", str(ctx.exception))

    def test_too_short_generation_raises(self):
        with self.assertRaises(RequestFlowError) as ctx:
            request_to_story(_fake_chat("قصة قصيرة جدًا."), "الأمانة")
        self.assertIn("قصيرة جدًا", str(ctx.exception))


class TestRequestToRun(unittest.TestCase):
    def setUp(self):
        self.cfg = {"paths": {"queue_file": "~/queue.md"}}
        self.silent = io.StringIO()

    def _run(self, text, chat_fn=None, run_fn=None, project=None,
             dry_run=False, queue_add_fn=None, out_path="/tmp/out.mp4"):
        return request_to_run(
            self.cfg, text, chat_fn if chat_fn is not None else _fake_chat(),
            out_path, run_fn=run_fn, project=project, dry_run=dry_run,
            queue_add_fn=queue_add_fn, print_fn=lambda *a: None)

    def test_dry_run_calls_nothing(self):
        queue_add_fn = _fake_queue_add()
        run_fn = _fake_run()
        result = self._run("الأمانة", run_fn=run_fn, dry_run=True,
                           queue_add_fn=queue_add_fn)
        self.assertEqual(result["status"], "dry-run")
        self.assertEqual(result["kind"], "topic")
        self.assertIsNone(result["output"])
        self.assertIsNone(result["queue_number"])
        self.assertEqual(queue_add_fn.calls, [])
        self.assertEqual(run_fn.calls, [])

    def test_full_run_topic_to_video(self):
        chat_fn = _fake_chat()
        queue_add_fn = _fake_queue_add(number=7)
        run_fn = _fake_run()
        result = self._run("الأمانة", chat_fn=chat_fn, run_fn=run_fn,
                           project="amana-proj",
                           queue_add_fn=queue_add_fn)
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["output"], "/tmp/out/request.mp4")
        self.assertEqual(result["queue_number"], 7)
        self.assertEqual(result["kind"], "topic")
        self.assertEqual(len(chat_fn.calls), 1)  # وُلّدت القصة
        self.assertEqual(len(queue_add_fn.calls), 1)
        self.assertEqual(queue_add_fn.calls[0]["story_text"],
                         FAKE_GENERATED)
        self.assertEqual(len(run_fn.calls), 1)
        call = run_fn.calls[0]
        self.assertEqual(call["story_text"], FAKE_GENERATED)
        self.assertEqual(call["project"], "amana-proj")
        self.assertEqual(call["out_path"], "/tmp/out.mp4")
        self.assertEqual(call["queue_number"], 7)

    def test_full_run_story_skips_llm(self):
        chat_fn = _fake_chat()
        queue_add_fn = _fake_queue_add()
        run_fn = _fake_run()
        result = self._run(LONG_STORY, chat_fn=chat_fn, run_fn=run_fn,
                           queue_add_fn=queue_add_fn)
        self.assertEqual(result["status"], "done")
        self.assertEqual(result["kind"], "story")
        self.assertEqual(chat_fn.calls, [])  # بلا توليد
        self.assertEqual(queue_add_fn.calls[0]["story_text"],
                         LONG_STORY.strip())

    def test_no_run_fn_queues_only(self):
        queue_add_fn = _fake_queue_add(number=9)
        result = self._run("الأمانة", queue_add_fn=queue_add_fn)
        self.assertEqual(result["status"], "queued")
        self.assertIsNone(result["output"])
        self.assertEqual(result["queue_number"], 9)
        self.assertEqual(len(queue_add_fn.calls), 1)

    def test_no_project_error_queues_only(self):
        def no_project(*args):
            raise NoProjectError(11, "الأمانة")

        result = self._run("الأمانة", run_fn=no_project,
                           queue_add_fn=_fake_queue_add(number=11))
        self.assertEqual(result["status"], "queued")
        self.assertIsNone(result["output"])
        self.assertEqual(result["queue_number"], 11)

    def test_run_fn_failure_raises(self):
        def failing_run(*args):
            raise RuntimeError("Concat غير موجود")

        with self.assertRaises(RequestFlowError) as ctx:
            self._run("الأمانة", run_fn=failing_run,
                      queue_add_fn=_fake_queue_add())
        self.assertIn("فشل خط الإنتاج", str(ctx.exception))

    def test_run_fn_no_output_raises(self):
        with self.assertRaises(RequestFlowError):
            self._run("الأمانة", run_fn=_fake_run(output=None),
                      queue_add_fn=_fake_queue_add())

    def test_empty_request_raises(self):
        with self.assertRaises(ValueError):
            self._run("   ")

    def test_llm_failure_propagates_no_queue_write(self):
        def failing_chat(prompt):
            raise RuntimeError("كل المزودين فشلوا")

        queue_add_fn = _fake_queue_add()
        with self.assertRaises(RequestFlowError):
            self._run("الأمانة", chat_fn=failing_chat,
                      run_fn=_fake_run(), queue_add_fn=queue_add_fn)
        self.assertEqual(queue_add_fn.calls, [])


class TestDefaultQueueAdd(unittest.TestCase):
    def test_saves_story_to_temp_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {"paths": {"queue_file": str(Path(tmp) / "queue.md")}}
            title = extract_title(MEDIUM_STORY)
            result = request_flow._default_queue_add(
                cfg, title, MEDIUM_STORY, studio_dir=tmp)
            self.assertEqual(result["number"], 1)
            queue_text = (Path(tmp) / "queue.md").read_text(
                encoding="utf-8")
            self.assertIn(title, queue_text)
            self.assertIn("(النص: queue/1-", queue_text)
            text_file = Path(result["text_file"])
            self.assertTrue(text_file.is_file())
            self.assertIn("رجل فقير",
                          text_file.read_text(encoding="utf-8"))

    def test_missing_queue_path_raises(self):
        with self.assertRaises(RequestFlowError):
            request_flow._default_queue_add({}, "عنوان", "نص قصة")


if __name__ == "__main__":
    unittest.main()
