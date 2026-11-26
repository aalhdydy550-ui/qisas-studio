#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات بيان مفتاح-المحتوى لمراحل الخط (lib.stage_cache).

تعمل بـ `env -u PYTHONNOUSERSITE python3 -m unittest tests.test_stage_cache -v`
من جذر الشجرة. كل الاختبارات على مجلدات مؤقتة — بلا كتابة
خارجها وبلا شبكة.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import stage_cache
from lib.stage_cache import StageCache, StageCacheError


def _write(directory, name, data):
    path = os.path.join(directory, name)
    with open(path, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))
    return path


class TestContentHash(unittest.TestCase):
    def test_same_inputs_same_hash(self):
        self.assertEqual(stage_cache.content_hash({"a": 1, "b": [2, 3]}),
                         stage_cache.content_hash({"a": 1, "b": [2, 3]}))

    def test_dict_key_order_irrelevant(self):
        self.assertEqual(stage_cache.content_hash({"a": 1, "b": 2}),
                         stage_cache.content_hash({"b": 2, "a": 1}))

    def test_changed_input_changes_hash(self):
        self.assertNotEqual(
            stage_cache.content_hash({"text": "قصة أ", "voice": "kareem"}),
            stage_cache.content_hash({"text": "قصة ب", "voice": "kareem"}))

    def test_bytes_and_str(self):
        self.assertEqual(stage_cache.content_hash(b"abc"),
                         stage_cache.content_hash(b"abc"))
        self.assertNotEqual(stage_cache.content_hash("abc"),
                            stage_cache.content_hash("abd"))

    def test_hash_file_matches_content(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write(d, "a.bin", b"\x00\x01\x02" * 1000)
            import hashlib
            self.assertEqual(stage_cache.hash_file(path),
                             hashlib.sha256(b"\x00\x01\x02" * 1000).hexdigest())

    def test_stage_key_rejects_unknown_stage(self):
        with self.assertRaises(StageCacheError):
            stage_cache.stage_key("nope", {"x": 1})

    def test_stage_key_differs_by_stage_and_inputs(self):
        a = stage_cache.stage_key("script", {"text": "x"})
        b = stage_cache.stage_key("audio", {"text": "x"})
        c = stage_cache.stage_key("script", {"text": "y"})
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(a, stage_cache.stage_key("script", {"text": "x"}))


class TestStageCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = StageCache(os.path.join(self.tmp.name, "cache"))
        self.work = os.path.join(self.tmp.name, "work")
        os.makedirs(self.work)

    def tearDown(self):
        self.tmp.cleanup()

    def test_lookup_miss_then_store_then_hit(self):
        inputs = {"text": "أمانة مغترب", "model": "gemini-3-flash"}
        self.assertIsNone(self.cache.lookup("script", inputs))
        self.assertFalse(self.cache.is_fresh("script", inputs))
        src = _write(self.work, "script.json", '{"title": "أمانة"}')
        stored = self.cache.store("script", inputs, src)
        self.assertTrue(os.path.isfile(stored))
        self.assertEqual(self.cache.lookup("script", inputs), stored)
        self.assertTrue(self.cache.is_fresh("script", inputs))

    def test_changed_input_invalidates(self):
        src = _write(self.work, "audio.wav", b"WAVE" * 100)
        self.cache.store("audio", {"scene": 1, "voice": "kareem"}, src)
        # تغيّر حرف واحد في المدخل → لا إصابة (إبطال بالمحتوى).
        self.assertIsNone(
            self.cache.lookup("audio", {"scene": 1, "voice": "kareem2"}))
        self.assertIsNone(
            self.cache.lookup("audio", {"scene": 2, "voice": "kareem"}))

    def test_store_twice_returns_same_path(self):
        inputs = {"scene": 1}
        src = _write(self.work, "scene.png", b"PNG" * 50)
        first = self.cache.store("scenes", inputs, src)
        second = self.cache.store("scenes", inputs, src)
        self.assertEqual(first, second)

    def test_record_without_copy(self):
        out = _write(self.work, "final.mp4", b"MP4" * 100)
        recorded = self.cache.record("video", {"title": "t"}, out)
        self.assertEqual(recorded, out)
        self.assertEqual(self.cache.lookup("video", {"title": "t"}), out)
        # الملف الأصلي ما زال هو نفسه (بلا نسخة مكررة).
        self.assertTrue(os.path.isfile(out))

    def test_lookup_miss_when_output_deleted(self):
        inputs = {"text": "x"}
        src = _write(self.work, "s.json", "{}")
        stored = self.cache.store("script", inputs, src)
        os.remove(stored)
        self.assertIsNone(self.cache.lookup("script", inputs))

    def test_manifest_survives_reopen(self):
        inputs = {"text": "x"}
        src = _write(self.work, "s.json", "{}")
        stored = self.cache.store("script", inputs, src)
        reopened = StageCache(os.path.join(self.tmp.name, "cache"))
        self.assertEqual(reopened.lookup("script", inputs), stored)

    def test_corrupt_manifest_starts_empty(self):
        with open(self.cache.manifest_path, "w", encoding="utf-8") as fh:
            fh.write("{not json!!!")
        reopened = StageCache(os.path.join(self.tmp.name, "cache"))
        self.assertEqual(reopened.stats()["entries"], 0)
        # وما زال يعمل بعدها.
        src = _write(self.work, "s.json", "{}")
        self.assertIsNotNone(
            reopened.store("script", {"text": "x"}, src))

    def test_invalidate_one_entry_then_stage(self):
        src1 = _write(self.work, "a.wav", b"A" * 10)
        src2 = _write(self.work, "b.wav", b"B" * 10)
        self.cache.store("audio", {"scene": 1}, src1)
        self.cache.store("audio", {"scene": 2}, src2)
        self.assertEqual(self.cache.invalidate("audio", {"scene": 1}), 1)
        self.assertIsNone(self.cache.lookup("audio", {"scene": 1}))
        self.assertIsNotNone(self.cache.lookup("audio", {"scene": 2}))
        self.assertEqual(self.cache.invalidate("audio"), 1)
        self.assertIsNone(self.cache.lookup("audio", {"scene": 2}))

    def test_store_missing_source_raises(self):
        with self.assertRaises(StageCacheError):
            self.cache.store("script", {"text": "x"},
                             os.path.join(self.work, "ghost.json"))

    def test_stats_and_clear(self):
        src = _write(self.work, "s.json", "{}")
        self.cache.store("script", {"text": "x"}, src)
        stats = self.cache.stats()
        self.assertEqual(stats["entries"], 1)
        self.assertEqual(stats["stages"], {"script": 1})
        self.assertGreater(stats["total_bytes"], 0)
        self.assertEqual(self.cache.clear(), 1)
        self.assertEqual(self.cache.stats()["entries"], 0)

    def test_prune_to_budget_keeps_newest(self):
        for i in range(3):
            src = _write(self.work, "f%d.bin" % i, b"X" * 100)
            self.cache.store("script", {"n": i}, src)
        removed = self.cache.prune(max_bytes=150)
        self.assertEqual(len(removed), 2)
        self.assertEqual(self.cache.stats()["entries"], 1)
        # الأحدث (n=2) هو الباقي.
        self.assertIsNotNone(self.cache.lookup("script", {"n": 2}))


class TestThumbnails(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = StageCache(os.path.join(self.tmp.name, "cache"))
        self.work = os.path.join(self.tmp.name, "work")
        os.makedirs(self.work)
        self.src = _write(self.work, "frame.jpg", b"JPEGDATA" * 100)

    def tearDown(self):
        self.tmp.cleanup()

    def test_key_deterministic_and_sensitive(self):
        k = stage_cache.thumbnail_key(self.src, 1280, 720, 80, "webp")
        self.assertEqual(
            k, stage_cache.thumbnail_key(self.src, 1280, 720, 80, "webp"))
        self.assertNotEqual(
            k, stage_cache.thumbnail_key(self.src, 720, 1280, 80, "webp"))
        self.assertNotEqual(
            k, stage_cache.thumbnail_key(self.src, 1280, 720, 90, "webp"))
        self.assertNotEqual(
            k, stage_cache.thumbnail_key(self.src, 1280, 720, 80, "avif"))

    def test_key_changes_when_source_content_changes(self):
        other = _write(self.work, "other.jpg", b"OTHERDATA" * 100)
        self.assertNotEqual(
            stage_cache.thumbnail_key(self.src, 1280, 720),
            stage_cache.thumbnail_key(other, 1280, 720))

    def test_key_rejects_bad_format_and_size(self):
        with self.assertRaises(StageCacheError):
            stage_cache.thumbnail_key(self.src, 1280, 720, fmt="bmp")
        with self.assertRaises(StageCacheError):
            stage_cache.thumbnail_key(self.src, 0, 720)
        with self.assertRaises(StageCacheError):
            stage_cache.thumbnail_key(self.src, 1280, 720, quality=0)

    def test_generate_once_then_hit(self):
        self.assertIsNone(
            self.cache.lookup_thumbnail(self.src, 1280, 720, 80, "webp"))
        thumb = _write(self.work, "t.webp", b"WEBP" * 50)
        stored = self.cache.store_thumbnail(self.src, 1280, 720, thumb,
                                            80, "webp")
        self.assertTrue(os.path.isfile(stored))
        self.assertEqual(
            self.cache.lookup_thumbnail(self.src, 1280, 720, 80, "webp"),
            stored)
        # التوليد مرة واحدة: تخزين ثانٍ بنفس المجموعة يرجع المسار نفسه.
        thumb2 = _write(self.work, "t2.webp", b"WEBP2" * 50)
        self.assertEqual(
            self.cache.store_thumbnail(self.src, 1280, 720, thumb2,
                                       80, "webp"),
            stored)

    def test_variants_cover_fixed_sizes_and_formats(self):
        variants = self.cache.thumbnail_variants(self.src)
        self.assertEqual(len(variants),
                         len(stage_cache.THUMBNAIL_SIZES)
                         * len(stage_cache.THUMBNAIL_FORMATS))
        self.assertTrue(all(v is None for v in variants.values()))
        # ولّد نسخة واحدة وسجّلها — تظهر وحدها.
        thumb = _write(self.work, "t.avif", b"AVIF" * 50)
        self.cache.store_thumbnail(self.src, 1280, 720, thumb, 80, "avif")
        variants = self.cache.thumbnail_variants(self.src)
        self.assertIsNotNone(variants[(1280, 720, "avif")])
        self.assertIsNone(variants[(1280, 720, "webp")])
        self.assertIsNone(variants[(720, 1280, "avif")])


if __name__ == "__main__":
    unittest.main()
