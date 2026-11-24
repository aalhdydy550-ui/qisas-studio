#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات كاش إعادة استخدام الريندر (lib.render_cache) —
الجولة v0.1.39.

تعمل بـ `python3 -m unittest discover -s tests -v`.
كل الكتابة في مجلدات مؤقتة — لا يُمس كاش runs/ الحقيقي.
فحص الفيديو بprobe مزيفة محقونة (بلا اعتماد على ffprobe)
عدا اختبار واحد حقيقي يُتخطى إن غاب ffmpeg/ffprobe.
بلا أي شبكة.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import render_cache

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


def _probe_ok(path):
    return {"duration": 50.0, "width": 720, "height": 1280,
            "has_audio": True}


def _probe_zero_duration(path):
    return {"duration": 0.0, "width": 720, "height": 1280,
            "has_audio": True}


def _probe_broken(path):
    raise RuntimeError("ملف تالف — لا يُقرأ")


def _make_output(td, name="out.mp4"):
    path = os.path.join(td, name)
    with open(path, "wb") as fh:
        fh.write(b"fake-video-bytes-" + name.encode("utf-8"))
    return path


class TestFingerprint(unittest.TestCase):
    def test_stable_for_same_inputs(self):
        inputs = {"script": "قصة العنزة",
                  "audio": "narration.wav",
                  "images": ["a.jpg", "b.jpg"],
                  "settings": {"backend": "concat", "width": 720,
                               "height": 1280, "watermark": True}}
        self.assertEqual(render_cache.fingerprint_inputs(inputs),
                         render_cache.fingerprint_inputs(inputs))

    def test_changes_when_script_changes(self):
        base = {"script": "قصة العنزة",
                "settings": {"width": 720}}
        changed = dict(base, script="قصة أخرى")
        self.assertNotEqual(
            render_cache.fingerprint_inputs(base),
            render_cache.fingerprint_inputs(changed))

    def test_changes_when_settings_change(self):
        base = {"script": "قصة", "settings": {"width": 720}}
        changed = {"script": "قصة", "settings": {"width": 1080}}
        self.assertNotEqual(
            render_cache.fingerprint_inputs(base),
            render_cache.fingerprint_inputs(changed))

    def test_key_order_does_not_matter(self):
        a = {"script": "قصة", "settings": {"width": 720,
                                           "height": 1280}}
        b = {"settings": {"height": 1280, "width": 720},
             "script": "قصة"}
        self.assertEqual(render_cache.fingerprint_inputs(a),
                         render_cache.fingerprint_inputs(b))

    def test_image_order_matters(self):
        # ترتيب المشاهد جزء من المدخلات — تبديله بصمة أخرى.
        a = {"images": ["a.jpg", "b.jpg"]}
        b = {"images": ["b.jpg", "a.jpg"]}
        self.assertNotEqual(render_cache.fingerprint_inputs(a),
                            render_cache.fingerprint_inputs(b))

    def test_file_content_not_filename(self):
        with tempfile.TemporaryDirectory() as td:
            p1 = os.path.join(td, "one.wav")
            p2 = os.path.join(td, "two.wav")
            with open(p1, "wb") as fh:
                fh.write(b"same-audio-bytes")
            with open(p2, "wb") as fh:
                fh.write(b"same-audio-bytes")
            self.assertEqual(
                render_cache.fingerprint_for(audio=p1),
                render_cache.fingerprint_for(audio=p2))
            with open(p2, "wb") as fh:
                fh.write(b"different-audio-bytes")
            self.assertNotEqual(
                render_cache.fingerprint_for(audio=p1),
                render_cache.fingerprint_for(audio=p2))

    def test_fingerprint_for_skips_absent_parts(self):
        self.assertNotEqual(
            render_cache.fingerprint_for(script="قصة"),
            render_cache.fingerprint_for(script="قصة",
                                         images=["a.jpg"]))

    def test_non_dict_inputs_raise(self):
        with self.assertRaises(render_cache.RenderCacheError):
            render_cache.fingerprint_inputs(["not", "a", "dict"])


class TestLookupStore(unittest.TestCase):
    def test_lookup_miss_when_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(render_cache.lookup(
                td, "abc", probe_fn=_probe_ok))

    def test_store_then_lookup_hit(self):
        with tempfile.TemporaryDirectory() as td:
            out = _make_output(td)
            fp = render_cache.fingerprint_for(script="قصة")
            entry = render_cache.store(td, fp, out,
                                       probe_fn=_probe_ok)
            self.assertIsNotNone(entry)
            self.assertEqual(entry["output"], os.path.abspath(out))
            self.assertEqual(entry["duration_seconds"], 50.0)
            self.assertEqual(entry["width"], 720)
            found = render_cache.lookup(td, fp, probe_fn=_probe_ok)
            self.assertIsNotNone(found)
            self.assertEqual(found["output"], os.path.abspath(out))

    def test_store_missing_file_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(render_cache.store(
                td, "fp", os.path.join(td, "غائب.mp4"),
                probe_fn=_probe_ok))
            self.assertIsNone(render_cache.lookup(
                td, "fp", probe_fn=_probe_ok))

    def test_store_broken_probe_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            out = _make_output(td)
            self.assertIsNone(render_cache.store(
                td, "fp", out, probe_fn=_probe_broken))
            self.assertIsNone(render_cache.lookup(
                td, "fp", probe_fn=_probe_ok))

    def test_lookup_rejects_deleted_output_and_prunes(self):
        with tempfile.TemporaryDirectory() as td:
            out = _make_output(td)
            fp = render_cache.fingerprint_for(script="قصة")
            render_cache.store(td, fp, out, probe_fn=_probe_ok)
            os.unlink(out)
            self.assertIsNone(render_cache.lookup(
                td, fp, probe_fn=_probe_ok))
            # الإدخال حُذف من الفهرس — بحث ثانٍ ما زال بلا نتيجة.
            index_path = render_cache.cache_index_path(td)
            with open(index_path, encoding="utf-8") as fh:
                index = json.load(fh)
            self.assertNotIn(fp, index["entries"])

    def test_lookup_rejects_zero_duration_and_prunes(self):
        with tempfile.TemporaryDirectory() as td:
            out = _make_output(td)
            fp = render_cache.fingerprint_for(script="قصة")
            render_cache.store(td, fp, out, probe_fn=_probe_ok)
            self.assertIsNone(render_cache.lookup(
                td, fp, probe_fn=_probe_zero_duration))

    def test_lookup_rejects_broken_probe_and_prunes(self):
        with tempfile.TemporaryDirectory() as td:
            out = _make_output(td)
            fp = render_cache.fingerprint_for(script="قصة")
            render_cache.store(td, fp, out, probe_fn=_probe_ok)
            self.assertIsNone(render_cache.lookup(
                td, fp, probe_fn=_probe_broken))
            index_path = render_cache.cache_index_path(td)
            with open(index_path, encoding="utf-8") as fh:
                index = json.load(fh)
            self.assertNotIn(fp, index["entries"])

    def test_lookup_rejects_dimension_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            out = _make_output(td)
            fp = render_cache.fingerprint_for(script="قصة")
            render_cache.store(td, fp, out, probe_fn=_probe_ok)
            self.assertIsNone(render_cache.lookup(
                td, fp, expected_width=1080, probe_fn=_probe_ok))
            # الرفض يحذف الإدخال — أعد التخزين قبل قبول بلا توقع.
            render_cache.store(td, fp, out, probe_fn=_probe_ok)
            self.assertIsNotNone(render_cache.lookup(
                td, fp, probe_fn=_probe_ok))

    def test_lookup_rejects_short_duration(self):
        with tempfile.TemporaryDirectory() as td:
            out = _make_output(td)
            fp = render_cache.fingerprint_for(script="قصة")
            render_cache.store(td, fp, out, probe_fn=_probe_ok)
            self.assertIsNone(render_cache.lookup(
                td, fp, min_duration=60.0, probe_fn=_probe_ok))
            render_cache.store(td, fp, out, probe_fn=_probe_ok)
            self.assertIsNotNone(render_cache.lookup(
                td, fp, min_duration=40.0, probe_fn=_probe_ok))

    def test_invalidate(self):
        with tempfile.TemporaryDirectory() as td:
            out = _make_output(td)
            fp = render_cache.fingerprint_for(script="قصة")
            render_cache.store(td, fp, out, probe_fn=_probe_ok)
            self.assertTrue(render_cache.invalidate(td, fp))
            self.assertFalse(render_cache.invalidate(td, fp))
            self.assertIsNone(render_cache.lookup(
                td, fp, probe_fn=_probe_ok))

    def test_corrupt_index_is_treated_as_empty(self):
        with tempfile.TemporaryDirectory() as td:
            path = render_cache.cache_index_path(td)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("{فهرس تالف\n")
            self.assertIsNone(render_cache.lookup(
                td, "fp", probe_fn=_probe_ok))
            # والتخزين بعد الفهرس التالف يعيد بناءه سليمًا.
            out = _make_output(td)
            fp = render_cache.fingerprint_for(script="قصة")
            self.assertIsNotNone(render_cache.store(
                td, fp, out, probe_fn=_probe_ok))
            self.assertIsNotNone(render_cache.lookup(
                td, fp, probe_fn=_probe_ok))

    @unittest.skipUnless(FFMPEG and FFPROBE,
                         "ffmpeg/ffprobe غير متاحين")
    def test_real_ffprobe_validates_real_video(self):
        """فحص حقيقي واحد: فيديو 1ث مولَّد بـffmpeg يُقبل، وملف
        نصي يُرفض — عبر probe الافتراضي (بلا probe مزيفة)."""
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "real.mp4")
            proc = subprocess.run(
                [FFMPEG, "-y", "-v", "error", "-f", "lavfi",
                 "-i", "color=c=black:s=720x1280:d=1",
                 "-f", "lavfi", "-i", "sine=frequency=440:d=1",
                 "-shortest", video],
                capture_output=True, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            fp = render_cache.fingerprint_for(script="قصة حقيقية")
            self.assertIsNotNone(render_cache.store(td, fp, video))
            found = render_cache.lookup(
                td, fp, expected_width=720, expected_height=1280)
            self.assertIsNotNone(found)
            self.assertEqual(found["width"], 720)
            # ملف نصي بامتداد mp4: probe الحقيقي يرفضه.
            fake = _make_output(td, "fake.mp4")
            fp2 = render_cache.fingerprint_for(script="مزيف")
            self.assertIsNone(render_cache.store(td, fp2, fake))


class TestFnv1a(unittest.TestCase):
    def test_known_vectors(self):
        # متجهات FNV-1a ‏64 بت المعروفة.
        self.assertEqual(render_cache.fnv1a_64(b""),
                         0xcbf29ce484222325)
        self.assertEqual(render_cache.fnv1a_64(b"a"),
                         0xaf63dc4c8601ec8c)

    def test_fingerprint_is_16_hex_chars(self):
        fp = render_cache.fnv1a_fingerprint({"script": "قصة"})
        self.assertEqual(len(fp), 16)
        int(fp, 16)  # hex صالح

    def test_fingerprint_deterministic(self):
        inputs = {"script": "قصة العنزة",
                  "settings": {"width": 720, "height": 1280}}
        self.assertEqual(render_cache.fnv1a_fingerprint(inputs),
                         render_cache.fnv1a_fingerprint(inputs))

    def test_fingerprint_key_order_does_not_matter(self):
        a = {"script": "قصة", "settings": {"width": 720,
                                           "height": 1280}}
        b = {"settings": {"height": 1280, "width": 720},
             "script": "قصة"}
        self.assertEqual(render_cache.fnv1a_fingerprint(a),
                         render_cache.fnv1a_fingerprint(b))

    def test_fingerprint_changes_when_inputs_change(self):
        base = {"script": "قصة", "settings": {"width": 720}}
        changed = {"script": "قصة أخرى", "settings": {"width": 720}}
        self.assertNotEqual(
            render_cache.fnv1a_fingerprint(base),
            render_cache.fnv1a_fingerprint(changed))

    def test_fingerprint_non_dict_raises(self):
        with self.assertRaises(render_cache.RenderCacheError):
            render_cache.fnv1a_fingerprint(["not", "a", "dict"])

    def test_store_records_quick_fp_when_inputs_given(self):
        with tempfile.TemporaryDirectory() as td:
            out = _make_output(td)
            inputs = {"script": "قصة العنزة",
                      "settings": {"width": 720}}
            fp = render_cache.fingerprint_for(script="قصة العنزة")
            entry = render_cache.store(td, fp, out, probe_fn=_probe_ok,
                                       inputs=inputs)
            self.assertIsNotNone(entry)
            self.assertEqual(entry["quick_fp"],
                             render_cache.fnv1a_fingerprint(inputs))
            # lookup ما زال بمفتاح SHA-256 كما هو.
            found = render_cache.lookup(td, fp, probe_fn=_probe_ok)
            self.assertIsNotNone(found)
            self.assertEqual(found["quick_fp"], entry["quick_fp"])

    def test_store_without_inputs_has_no_quick_fp(self):
        with tempfile.TemporaryDirectory() as td:
            out = _make_output(td)
            fp = render_cache.fingerprint_for(script="قصة")
            entry = render_cache.store(td, fp, out, probe_fn=_probe_ok)
            self.assertIsNotNone(entry)
            self.assertNotIn("quick_fp", entry)


if __name__ == "__main__":
    unittest.main()
