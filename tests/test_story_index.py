#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات فهرس القصص المحلي (lib.story_index) + خطاف الطابور
+ حقول «أقرب فيديو سابق» في analyze/ab — جولة v0.1.48.

بلا شبكة في اختبارات الوحدة: تضمينات وهمية محقونة (embed_fn)
وHTTP وهمي في test_omniroute_embed.py. اختبارات Qdrant
الحقيقية (محلية، بلا خادم) تُتخطى بأدب إن غابت مكتبة
qdrant_client الاختيارية (unittest.skip) — ومسار الغياب
نفسه يُثبَت بتشغيل فرعي يحجب استيراد qdrant_client (stub
يرفع ImportError عبر PYTHONPATH — نمط test_ci_numpy.py).
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import story_index as si  # noqa: E402

# تضمين وهمي حتمي (4 أبعاد مواضيعية): تشابه عالٍ داخل
# الموضوع نفسه، منخفض عبر المواضيع — يثبت منطق العتبة بلا
# شبكة وبلا Ollama.
_TOPICS = (
    ("نجار", "ذهب", "خشبة", "باب", "عجوز", "أمانة"),
    ("أرملة", "أرض", "حفر", "قاضي", "وصية", "مزرعة"),
    ("حماة", "خياطة", "ابنة", "ظلم", "بيت"),
    ("سيارة", "صيانة", "ورشة", "ميكانيكا"),
)


def fake_embed(text):
    text = text or ""
    vec = [0.05] * len(_TOPICS)
    for i, words in enumerate(_TOPICS):
        for w in words:
            if w in text:
                vec[i] += 1.0
    norm = sum(v * v for v in vec) ** 0.5
    return [v / norm for v in vec]


NAJJAR = ("كان عم حسن نجاراً فقيراً يصلح أبواب البيوت القديمة، فوجد داخل "
          "الخشبة صرة فيها ذهب، فأعادها للعجوز وقالت له الأمانة أغلى من الذهب.")
NEAR_NAJJAR = ("نجار مسكين يصلح باب بيت سيدة مسنة فوجد في الخشبة كيس ذهب "
               "فأعاده لها بلا تردد فقالت له خذ نصفه فالأمانة أغلى من الذهب.")
AISHA = ("أرملة اشترت أرضاً فحفرت فيها فوجدت الماء والوصية، وذهبت إلى "
         "القاضي فأخذت حقها وصارت الأرض مزرعة.")
UNRELATED_CAR = ("مركز صيانة سيارات يقدم سمكرة وميكانيكا وورشة إصلاح "
                 "وقطع غيار في مدينة فاقوس.")


class TestFakeEmbedSanity(unittest.TestCase):
    def test_same_topic_high_cross_topic_low(self):
        import math

        def cos(a, b):
            return sum(x * y for x, y in zip(a, b))

        self.assertGreater(cos(fake_embed(NAJJAR),
                               fake_embed(NEAR_NAJJAR)), 0.85)
        self.assertLess(cos(fake_embed(NAJJAR),
                            fake_embed(UNRELATED_CAR)), 0.85)
        self.assertLess(cos(fake_embed(AISHA),
                            fake_embed(UNRELATED_CAR)), 0.85)


@unittest.skipUnless(si.qdrant_available(),
                     "qdrant_client غير مثبّتة (اعتمادية اختيارية)")
class TestStoryIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.idx = si.StoryIndex(
            path=os.path.join(self.tmp.name, "index"),
            embed_fn=fake_embed)

    def tearDown(self):
        self.idx.close()
        self.tmp.cleanup()

    def test_index_and_find_similar_above_threshold(self):
        pid = self.idx.index_story("النجار الأمين", NAJJAR)
        self.assertIsNotNone(pid)
        hits = self.idx.find_similar(
            "النجار الأمين\n" + NEAR_NAJJAR)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["title"], "النجار الأمين")
        self.assertGreaterEqual(hits[0]["score"],
                                si.SIMILARITY_THRESHOLD)

    def test_unrelated_below_threshold(self):
        self.idx.index_story("النجار الأمين", NAJJAR)
        self.idx.index_story("عائشة الأرملة", AISHA)
        hits = self.idx.find_similar(
            "مركز صيانة\n" + UNRELATED_CAR)
        self.assertEqual(hits, [])

    def test_threshold_parameter_respected(self):
        self.idx.index_story("النجار الأمين", NAJJAR)
        hits = self.idx.find_similar(
            "النجار الأمين\n" + NEAR_NAJJAR, threshold=0.99)
        self.assertEqual(hits, [])

    def test_reindex_updates_same_id(self):
        pid1 = self.idx.index_story("النجار الأمين", NAJJAR)
        pid2 = self.idx.index_story("النجار الأمين", NAJJAR)
        self.assertEqual(pid1, pid2)
        hits = self.idx.find_similar(
            "النجار الأمين\n" + NEAR_NAJJAR)
        self.assertEqual(len(hits), 1)

    def test_empty_inputs(self):
        self.assertIsNone(self.idx.index_story("", NAJJAR))
        self.assertIsNone(self.idx.index_story("عنوان", "   "))
        self.assertEqual(self.idx.find_similar(""), [])
        self.assertIsNone(self.idx.index_video("  "))
        self.assertIsNone(self.idx.find_nearest_video(""))

    def test_embed_failure_is_fail_open(self):
        def boom(text):
            raise RuntimeError("بلا Ollama")

        bad = si.StoryIndex(
            path=os.path.join(self.tmp.name, "bad"),
            embed_fn=boom)
        self.assertIsNone(bad.index_story("عنوان", NAJJAR))
        self.assertEqual(bad.find_similar(NAJJAR), [])
        self.assertIsNone(bad.index_video("هوك"))
        self.assertIsNone(bad.find_nearest_video("هوك"))
        bad.close()

    def test_index_video_and_find_nearest(self):
        self.idx.index_video(
            "قالوا لها بتحفر قبرها… طلعت بتحفر جنة بناتها",
            title="عائشة الأرملة", views=694, hook_score=2)
        nearest = self.idx.find_nearest_video(
            "أرملة تحفر أرضاً فتجد الوصية عند القاضي")
        self.assertIsNotNone(nearest)
        self.assertEqual(nearest["title"], "عائشة الأرملة")
        self.assertEqual(nearest["views"], 694)
        self.assertEqual(nearest["hook_score"], 2)
        self.assertIn("similarity", nearest)
        self.assertIn("hook", nearest)

    def test_find_nearest_video_empty_index(self):
        self.assertIsNone(self.idx.find_nearest_video("أي هوك"))

    def test_default_path_is_runs_story_index(self):
        self.assertTrue(si.default_index_path().endswith(
            os.path.join("runs", "story-index")))


class TestOptionalDependencyBlocked(unittest.TestCase):
    """بلا qdrant_client إطلاقًا: كل الدوال «غير متاح» بأدب.

    تشغيل فرعي بـ stub qdrant_client يرفع ImportError عبر
    PYTHONPATH (نمط test_ci_numpy.py) — يثبت مسار الاعتمادية
    الاختيارية بلا تعديل الكود.
    """
    _SNIPPET = (
        "import sys; sys.path.insert(0, '.');"
        "from lib import story_index as si;"
        "idx = si.StoryIndex(path='x', embed_fn=lambda t: [1.0, 0.0]);"
        "assert si.qdrant_available() is False, 'available';"
        "assert idx.available is False, 'idx.available';"
        "assert idx.index_story('ع', 'ن') is None, 'index_story';"
        "assert idx.find_similar('ن') == [], 'find_similar';"
        "assert idx.index_video('هوك') is None, 'index_video';"
        "assert idx.find_nearest_video('هوك') is None, 'nearest';"
        "assert si.index_story('ع', 'ن') is None, 'mod index';"
        "assert si.find_similar('ن') == [], 'mod similar';"
        "assert si.find_nearest_video('هوك') is None, 'mod nearest';"
        "print('OPTIONAL-DEP-OK')")

    def test_blocked_import_is_fail_open(self):
        studio_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        with tempfile.TemporaryDirectory() as stub_dir:
            stub_pkg = os.path.join(stub_dir, "qdrant_client")
            os.makedirs(stub_pkg)
            with open(os.path.join(stub_pkg, "__init__.py"),
                      "w", encoding="utf-8") as f:
                f.write("raise ImportError('qdrant_client محظورة عمدًا "
                        "للاختبار')\n")
            env = dict(os.environ)
            env["PYTHONPATH"] = stub_dir + os.pathsep + env.get(
                "PYTHONPATH", "")
            proc = subprocess.run(
                [sys.executable, "-c", self._SNIPPET],
                cwd=studio_dir, env=env, capture_output=True,
                text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("OPTIONAL-DEP-OK", proc.stdout)


SAMPLE_QUEUE = """# طابور قصص — تجريبي

## في الانتظار

1. **قصة قديمة** — بلا ملاحظات
"""


@unittest.skipUnless(si.qdrant_available(),
                     "qdrant_client غير مثبّتة (اعتمادية اختيارية)")
class TestQueueSimilarityHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.qpath = os.path.join(self.tmp.name, "queue.md")
        with open(self.qpath, "w", encoding="utf-8") as f:
            f.write(SAMPLE_QUEUE)
        self.stories_dir = os.path.join(self.tmp.name, "queue")
        self.idx = si.StoryIndex(
            path=os.path.join(self.tmp.name, "index"),
            embed_fn=fake_embed)
        self.idx.index_story("النجار الأمين", NAJJAR)

    def tearDown(self):
        self.idx.close()
        self.tmp.cleanup()

    def test_near_duplicate_rejected_naming_story_and_score(self):
        from lib import queue as queue_lib
        with self.assertRaises(queue_lib.QueueError) as ctx:
            queue_lib.add_story(
                self.qpath, "نجار آخر", NEAR_NAJJAR,
                stories_dir=self.stories_dir, story_index=self.idx)
        msg = str(ctx.exception)
        self.assertIn("النجار الأمين", msg)
        self.assertIn("0.", msg)  # الدرجة مذكورة
        # الرفض قبل أي كتابة: لا سطر ولا ملف نص جديد
        with open(self.qpath, encoding="utf-8") as f:
            self.assertNotIn("نجار آخر", f.read())
        self.assertFalse(os.path.exists(
            os.path.join(self.stories_dir, "2-نجار-آخر.txt")))

    def test_unrelated_added_and_indexed(self):
        from lib import queue as queue_lib
        result = queue_lib.add_story(
            self.qpath, "مركز السيارات", UNRELATED_CAR,
            stories_dir=self.stories_dir, story_index=self.idx)
        self.assertEqual(result["number"], 2)
        self.assertIn("similarity", result)
        self.assertTrue(result["similarity"]["checked"])
        # القصة المضافة نفسها صارت في الفهرس
        hits = self.idx.find_similar(
            "مركز السيارات\n" + UNRELATED_CAR)
        self.assertTrue(any(h["title"] == "مركز السيارات"
                            for h in hits))

    def test_embed_failure_is_fail_open_with_note(self):
        from lib import queue as queue_lib

        def boom(text):
            raise RuntimeError("بلا Ollama")

        bad = si.StoryIndex(
            path=os.path.join(self.tmp.name, "bad"),
            embed_fn=boom)
        result = queue_lib.add_story(
            self.qpath, "قصة جديدة", "نص جديد تمامًا",
            stories_dir=self.stories_dir, story_index=bad)
        self.assertEqual(result["number"], 2)
        self.assertIn("index_note", result)
        bad.close()

    def test_unavailable_index_is_fail_open(self):
        from lib import queue as queue_lib
        dead = si.StoryIndex(
            path=os.path.join(self.tmp.name, "dead"),
            embed_fn=fake_embed)
        dead.available = False  # محاكاة غياب qdrant_client
        result = queue_lib.add_story(
            self.qpath, "قصة جديدة", "نص جديد",
            stories_dir=self.stories_dir, story_index=dead)
        self.assertEqual(result["number"], 2)
        self.assertIn("index_note", result)
        dead.close()

    def test_no_index_behaves_like_before(self):
        # بلا story_index ممرَّر: المسار القديم كما كان — بلا
        # فحص وبلا مفاتيح إضافية في النتيجة (التفعيل صريح).
        from lib import queue as queue_lib
        result = queue_lib.add_story(
            self.qpath, "قصة جديدة", "نص جديد",
            stories_dir=self.stories_dir)
        self.assertEqual(result["number"], 2)
        self.assertNotIn("similarity", result)
        self.assertNotIn("index_note", result)


@unittest.skipUnless(si.qdrant_available(),
                     "qdrant_client غير مثبّتة (اعتمادية اختيارية)")
class TestNearestVideoFields(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.idx = si.StoryIndex(
            path=os.path.join(self.tmp.name, "index"),
            embed_fn=fake_embed)
        self.idx.index_video(
            "قالوا لها بتحفر قبرها… طلعت بتحفر جنة بناتها",
            title="عائشة الأرملة", views=694, hook_score=2)
        self.idx.index_story("عائشة الأرملة", AISHA)

    def tearDown(self):
        self.idx.close()
        self.tmp.cleanup()

    def test_analyze_suggest_has_nearest_when_available(self):
        from lib import analyze
        fb = {"views": 694, "reactions": 2, "comments": 0,
              "shares": 0, "engagements": 3}
        yt = {"views": 254, "likes": 10, "comments": 0,
              "title": "أرملة تحفر أرضاً فتجد الوصية عند القاضي"}
        tips = analyze.suggest(fb, yt, index=self.idx)
        self.assertIsNotNone(tips.nearest_video)
        self.assertEqual(tips.nearest_video["title"],
                         "عائشة الأرملة")
        self.assertTrue(any("أقرب فيديو سابق" in t for t in tips))

    def test_analyze_suggest_no_field_when_absent(self):
        from lib import analyze
        # فهرس فارغ (بلا فيديوهات): الحقل يُحذف بصمت.
        empty = si.StoryIndex(
            path=os.path.join(self.tmp.name, "empty-index"),
            embed_fn=fake_embed)
        fb = {"views": 694, "reactions": 2, "comments": 0,
              "shares": 0}
        yt = {"views": 254, "likes": 10, "comments": 0,
              "title": "عنوان بلا فهرس"}
        tips = analyze.suggest(fb, yt, index=empty)
        self.assertIsNone(tips.nearest_video)
        self.assertFalse(any("أقرب فيديو سابق" in t for t in tips))
        empty.close()

    def test_ab_suggest_hooks_unpacks_and_has_nearest(self):
        from lib import ab
        res = ab.suggest_hooks("أرملة تحفر أرضاً فتجد الوصية",
                               chat_fn=None, index=self.idx)
        a, b, src = res  # التفكيك القديم يعمل كما هو
        self.assertEqual(src, "local")
        self.assertIsNotNone(res.nearest_video)
        self.assertEqual(res.nearest_video["title"],
                         "عائشة الأرملة")

    def test_ab_suggest_hooks_no_field_when_absent(self):
        from lib import ab
        empty = si.StoryIndex(
            path=os.path.join(self.tmp.name, "empty-index"),
            embed_fn=fake_embed)
        res = ab.suggest_hooks("عنوان بلا فهرس", chat_fn=None,
                               index=empty)
        a, b, src = res
        self.assertIsNone(res.nearest_video)
        empty.close()

    def test_ab_score_hooks_nearest_key(self):
        from lib import ab
        scores = ab.score_hooks(
            ["أرملة تحفر أرضاً فتجد الوصية عند القاضي!"],
            index=self.idx)
        self.assertEqual(len(scores), 1)
        self.assertIn("nearest_video", scores[0])
        self.assertEqual(scores[0]["nearest_video"]["title"],
                         "عائشة الأرملة")
        self.assertIn("total", scores[0])

    def test_ab_score_hooks_no_key_when_absent(self):
        from lib import ab
        empty = si.StoryIndex(
            path=os.path.join(self.tmp.name, "empty-index"),
            embed_fn=fake_embed)
        scores = ab.score_hooks(["هوك صادم مختلف تمامًا!"],
                                index=empty)
        self.assertEqual(len(scores), 1)
        self.assertNotIn("nearest_video", scores[0])
        empty.close()


if __name__ == "__main__":
    unittest.main()
