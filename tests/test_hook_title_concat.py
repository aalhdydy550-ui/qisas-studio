#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات انحدار: تضاعف عنوان الهوك على فيديوهات Concat.

العيب (إنتاج 2026-11-26 «أيقظ أولاده للصلاة»): فيديو Concat يحمل
أصلًا عنوانًا محروقًا أول ثوانٍ (title_add في lib.concat_mcp:
نص العنوان، 0–4ث، offsetY ‏+0.12 أي مركز y≈794 في 1280 — داخل
النطاق الأوسط لعنوان الهوك)، ثم `apply_hook_title` يحرق العنوان
نفسه مرة ثانية (Naskh ‏58، y0=711–y1=827 للعنوان نفسه) فينتج
عنوانان متداخلان مشوّهان في الشريط نفسه. أُعيد إنتاجه هنا على
فيديو اختبار داكن: بكسلات ساطعة في الشريط 711–827 قفزت من 7,982
(عنوان واحد) إلى 11,883 (+49%) بعد hook-title، والثلث العلوي
بقي صفرًا في الحالتين — العيب تضاعف لا خرق هندسة.

عقد الإصلاح الذي تثبّته هذه الاختبارات (هجين):
1. الحارس في lib.hook_title: `apply_hook_title(..., force=False)`
   يرفض (HookTitleError عربي يسمّي العنوان المحروق ويذكّر
   بـ--force في الـCLI) حين يعلن البيان الجانبي `<الفيديو>.manifest.json`
   (المعيار الذي يكتبه كل تجميع) عنوانًا محروقًا يتداخل مع
   العنوان المطلوب — ويكتشفه `detect_burned_title` (مطابقة
   بالتطبيع: تطابق أو احتواء، لا كلمة واحدة). بلا بيان أو بيان
   تالف: fail-open موثّق (لا رفض أعمى)؛ و--force (أو force=True
   في بايثون) يطبّق عند الطلب الصريح.
2. الحرق الواحد في مسار البناء: `mlt_stage.build_mlt(...,
   as_hook_title=True)` يحرق العنوان مرة واحدة بهندسة
   `hook_title_spec` (النطاق الأوسط، 0–3ث) بدل عنوان الأسفل
   4ث؛ والافتراضي بلا تغيير (تثبّت اختبارات القاعدة الدائمة).
3. بطاقة العنوان في الفيديو الطويل: `long_video.build_project`
   يسجّل `meta["title_cards"]` (المقدمة + بطاقة كل فصل +
   الخاتمة) مرة واحدة لكل بطاقة — لتكون العناوين المحروقة
   مقروءة آليًا عند التوصيل.

تعمل بـ `python3 -m unittest tests.test_hook_title_concat -v` من
مجلد studio. الوسائط تُولَّد محليًا بـffmpeg (بلا شبكة).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import check as check_lib
from lib import hook_title
from lib import long_video
from lib import mlt_stage

try:
    from PIL import Image
    import numpy as np
    _HAS_IMG = True
except ImportError:  # pragma: no cover
    _HAS_IMG = False

TITLE = "صحّى أولاده لصلاة الفجر"
FULL_HOOK = "صحّى أولاده لصلاة الفجر… وما كان في بيته ولا لقمة عيش!"
# خط Concat نفسه (lib.concat_mcp.TITLE_STYLE: Noto Kufi Arabic،
# fontSize ‏0.06 أي 77px على ارتفاع 1280، وزن 700 ≈ Bold).
KUFI_BOLD = ("/usr/share/fonts/truetype/noto/"
             "NotoKufiArabic-Bold.ttf")

MLT_MANIFEST = {
    "project": "test-story",
    "sequence": ["scene1.jpg", "scene2.jpg"],
    "image_clip_seconds": 5,
    "narration_duration": 12.0,
    "phrases": [
        {"text": "عبارة أولى", "start": 0.0, "end": 4.0},
        {"text": "عبارة ثانية", "start": 5.0, "end": 9.0},
    ],
}
MLT_VIDEO = {"width": 720, "height": 1280, "fps": 30}


def _make_video(path, seconds=10, size="720x1280"):
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i",
                    "color=c=0x2a2a2a:s=%s:r=30:d=%s" % (size, seconds),
                    "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=48000:duration=%s"
                    % seconds,
                    "-t", str(seconds), "-c:v", "libx264", "-preset",
                    "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", path],
                   check=True, timeout=300, capture_output=True,
                   text=True)


def _burn_concat_title(video, out):
    """عنوان بأسلوب Concat title_add: سطران، خط 77، مركز الكتلة
    y≈794 (offsetY ‏+0.12)، ظاهر 0–4ث."""
    filt = (
        "drawtext=text='صحّى أولاده لصلاة':fontfile=%s:fontsize=77:"
        "fontcolor=white:borderw=2:bordercolor=black:"
        "x=(w-text_w)/2:y=717:enable='between(t,0,4)',"
        "drawtext=text='الفجر':fontfile=%s:fontsize=77:"
        "fontcolor=white:borderw=2:bordercolor=black:"
        "x=(w-text_w)/2:y=794:enable='between(t,0,4)'"
        % (KUFI_BOLD, KUFI_BOLD))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video,
                    "-vf", filt, "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    out], check=True, timeout=300,
                   capture_output=True, text=True)


def _bright_pixels(frame_path, y0, y1):
    """عدد البكسلات الساطعة (>200) في شريط y0–y1 من إطار."""
    a = np.asarray(Image.open(frame_path).convert("L"), dtype=float)
    return int((a[y0:y1, :] > 200).sum())


def _write_manifest(video, title, hook=""):
    """بيان جانبي بالمعيار `<الفيديو>.manifest.json` (كما يكتبه
    تجميع studio — الحقول التي يقرأها الحارس فقط)."""
    man = {"schema_version": 1, "video": {}, "title": title,
           "hook": hook, "source": "studio",
           "created_at": "2026-11-26T17:33:12+02:00"}
    with open(video + ".manifest.json", "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False)


def _make_wav(path, seconds=2):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=%d" % seconds,
                    "-c:a", "pcm_s16le", path], check=True, timeout=60)


def _make_jpg(path, width=1280, height=720):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "testsrc=size=%dx%d:rate=30:duration=1"
                    % (width, height),
                    "-frames:v", "1", path], check=True, timeout=60)


def _fake_chapter(tmp, name, duration=2.0):
    wav = os.path.join(tmp, name + ".wav")
    _make_wav(wav, seconds=int(duration))
    img = os.path.join(tmp, name + ".jpg")
    _make_jpg(img)
    return {"title": name, "moral": "عبرة " + name, "narration": wav,
            "duration": duration, "images": [img],
            "phrases": [{"start": 0.0, "end": duration, "text": "نص تجريبي",
                         "words": long_video.estimate_word_times(
                             "نص تجريبي", 0.0, duration)}]}


class TestTitlesOverlap(unittest.TestCase):
    def test_exact_match_overlaps(self):
        self.assertTrue(hook_title.titles_overlap(TITLE, TITLE))

    def test_prefix_containment_overlaps(self):
        # حالة الإنتاج: العنوان المحروق بادئة من الهوك الكامل.
        self.assertTrue(hook_title.titles_overlap(TITLE, FULL_HOOK))
        self.assertTrue(hook_title.titles_overlap(FULL_HOOK, TITLE))

    def test_punctuation_and_alef_do_not_hide_overlap(self):
        self.assertTrue(hook_title.titles_overlap(
            TITLE + "!", TITLE))
        self.assertTrue(hook_title.titles_overlap(
            "صحى اولاده لصلاة الفجر", TITLE))
        # تشكيل (شدّة) في أحد الطرفين لا يخفي التطابق.
        self.assertTrue(hook_title.titles_overlap(
            "صَحَّى أولاده لصلاة الفجر", TITLE))

    def test_unrelated_titles_do_not_overlap(self):
        self.assertFalse(hook_title.titles_overlap(
            "قصة النجار الأمين", TITLE))
        self.assertFalse(hook_title.titles_overlap("", TITLE))
        self.assertFalse(hook_title.titles_overlap(TITLE, ""))

    def test_single_shared_word_is_not_a_double_title(self):
        # كلمة واحدة مشتركة ليست عنوانًا مضاعفًا — لا رفض أعمى.
        self.assertFalse(hook_title.titles_overlap("الفجر", TITLE))
        self.assertTrue(hook_title.titles_overlap(
            "أولاده لصلاة", TITLE))


class TestDetectBurnedTitle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hook-concat-detect-")
        self.video = os.path.join(self.tmp, "short.mp4")
        _make_video(self.video)

    def test_exact_manifest_title_detected(self):
        _write_manifest(self.video, TITLE, FULL_HOOK)
        self.assertEqual(
            hook_title.detect_burned_title(self.video, TITLE), TITLE)

    def test_prefix_manifest_title_detected_for_full_hook(self):
        _write_manifest(self.video, TITLE, FULL_HOOK)
        self.assertEqual(
            hook_title.detect_burned_title(self.video, FULL_HOOK), TITLE)

    def test_unrelated_manifest_title_not_detected(self):
        _write_manifest(self.video, "قصة النجار الأمين", FULL_HOOK)
        self.assertIsNone(
            hook_title.detect_burned_title(self.video, TITLE))

    def test_hook_field_alone_does_not_trigger(self):
        # حقل hook هو الهوك المنطوق لا المحروق — تطابقه وحده لا
        # يعني عنوانًا محروقًا، فلا رفض.
        _write_manifest(self.video, "قصة النجار الأمين", TITLE)
        self.assertIsNone(
            hook_title.detect_burned_title(self.video, TITLE))

    def test_missing_manifest_is_none(self):
        self.assertIsNone(
            hook_title.detect_burned_title(self.video, TITLE))

    def test_corrupt_manifest_is_none(self):
        with open(self.video + ".manifest.json", "w",
                  encoding="utf-8") as f:
            f.write("{invalid json")
        self.assertIsNone(
            hook_title.detect_burned_title(self.video, TITLE))

    def test_empty_manifest_title_is_none(self):
        _write_manifest(self.video, "", FULL_HOOK)
        self.assertIsNone(
            hook_title.detect_burned_title(self.video, TITLE))

    def test_missing_video_is_none(self):
        self.assertIsNone(hook_title.detect_burned_title(
            os.path.join(self.tmp, "nope.mp4"), TITLE))


class TestConcatGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="hook-concat-")
        base = os.path.join(cls.tmp, "base.mp4")
        _make_video(base)
        cls.base = base
        cls.concat = os.path.join(cls.tmp, "concat-style.mp4")
        _burn_concat_title(base, cls.concat)
        if _HAS_IMG:
            frame = os.path.join(cls.tmp, "frame-concat-only.png")
            check_lib.extract_frame(cls.concat, 1.5, frame)
            # خط الأساس: عنوان Concat وحده في الشريط 711–827.
            cls.concat_band = _bright_pixels(frame, 711, 827)

    def _copy_concat(self, name):
        path = os.path.join(self.tmp, name)
        shutil.copyfile(self.concat, path)
        return path

    def test_concat_video_with_manifest_refuses(self):
        video = self._copy_concat("refuse.mp4")
        _write_manifest(video, TITLE, FULL_HOOK)
        out = os.path.join(self.tmp, "refuse-out.mp4")
        with self.assertRaises(hook_title.HookTitleError) as cm:
            hook_title.apply_hook_title(video, TITLE, out)
        msg = str(cm.exception)
        self.assertIn("محروق", msg)
        self.assertIn(TITLE, msg)
        self.assertIn("--force", msg)
        self.assertFalse(os.path.isfile(out))

    def test_refusal_wins_over_too_long_hook(self):
        # الهوك الكامل أطول من سطرين × 19 حرفًا فيرفضه
        # hook_title_spec وحده — لكن الحارس أولًا: الفيديو يحمل
        # العنوان أصلًا، فالرفض الصحيح هو رفض التضاعف لا رفض
        # الطول (تقصير الهوك لن ينفع هنا).
        video = self._copy_concat("refuse-long.mp4")
        _write_manifest(video, TITLE, FULL_HOOK)
        out = os.path.join(self.tmp, "refuse-long-out.mp4")
        with self.assertRaises(hook_title.HookTitleError) as cm:
            hook_title.apply_hook_title(video, FULL_HOOK, out)
        self.assertIn("محروق", str(cm.exception))
        self.assertFalse(os.path.isfile(out))

    def test_refusal_does_not_touch_existing_out(self):
        video = self._copy_concat("refuse-keep.mp4")
        _write_manifest(video, TITLE, FULL_HOOK)
        out = os.path.join(self.tmp, "keep.mp4")
        with open(out, "w", encoding="utf-8") as f:
            f.write("sentinel")
        with self.assertRaises(hook_title.HookTitleError):
            hook_title.apply_hook_title(video, TITLE, out)
        with open(out, encoding="utf-8") as f:
            self.assertEqual(f.read(), "sentinel")

    def test_force_applies_over_burned_title(self):
        video = self._copy_concat("force.mp4")
        _write_manifest(video, TITLE, FULL_HOOK)
        out = os.path.join(self.tmp, "force-out.mp4")
        hook_title.apply_hook_title(video, TITLE, out, force=True)
        self.assertTrue(os.path.isfile(out))
        info = check_lib.probe(out)
        self.assertEqual((info["width"], info["height"]), (720, 1280))

    def test_unrelated_manifest_title_applies(self):
        video = self._copy_concat("unrelated.mp4")
        _write_manifest(video, "قصة النجار الأمين", FULL_HOOK)
        out = os.path.join(self.tmp, "unrelated-out.mp4")
        hook_title.apply_hook_title(video, TITLE, out)
        self.assertTrue(os.path.isfile(out))

    def test_no_manifest_applies_fail_open(self):
        out = os.path.join(self.tmp, "no-manifest-out.mp4")
        hook_title.apply_hook_title(self.base, TITLE, out)
        self.assertTrue(os.path.isfile(out))

    def test_corrupt_manifest_applies_fail_open(self):
        video = self._copy_concat("corrupt.mp4")
        with open(video + ".manifest.json", "w",
                  encoding="utf-8") as f:
            f.write("{invalid json")
        out = os.path.join(self.tmp, "corrupt-out.mp4")
        hook_title.apply_hook_title(video, TITLE, out)
        self.assertTrue(os.path.isfile(out))

    @unittest.skipUnless(_HAS_IMG, "PIL/numpy غير متاحتين")
    def test_force_doubling_is_measurable_in_same_band(self):
        # توصيف العيب نفسه: hook-title فوق عنوان Concat يضيف
        # حبرًا في الشريط نفسه (711–827) لا في موضع آخر —
        # والثلث العلوي يبقى نظيفًا في الحالتين.
        video = self._copy_concat("double.mp4")
        _write_manifest(video, TITLE, FULL_HOOK)
        out = os.path.join(self.tmp, "double-out.mp4")
        hook_title.apply_hook_title(video, TITLE, out, force=True)
        frame = os.path.join(self.tmp, "frame-double.png")
        check_lib.extract_frame(out, 1.5, frame)
        doubled = _bright_pixels(frame, 711, 827)
        self.assertGreater(doubled, int(self.concat_band * 1.2))
        self.assertEqual(_bright_pixels(frame, 0, 427), 0)


class TestBuildPathSingleTitle(unittest.TestCase):
    def test_mlt_hook_title_mode_burns_title_once(self):
        spec = hook_title.hook_title_spec(TITLE, 720, 1280)
        self.assertEqual(hook_title.validate_spec(spec), [])
        xml_text = mlt_stage.build_mlt(
            MLT_MANIFEST, TITLE, "/tmp/assets", dict(MLT_VIDEO),
            as_hook_title=True)
        root = ET.fromstring(xml_text)
        hooks = [f for f in root.findall("tractor/filter")
                 if (f.get("id") or "").startswith("filter-hook")]
        # سطرا العنوان فقط — بلا عنوان أسفل إضافي.
        self.assertEqual(len(hooks), len(spec["lines"]))
        # (v0.1.62) صندوق كل سطر متمركز بالهندسة المقاسة
        # (halign يتجاهله MLT 7.22) وارتفاعه 150 لا حجم الخط
        # (58 كان يقصّ العنوان) — x + w/2 = مركز الإطار (360).
        expected_xy = [(140, 440), (283, 154)]
        for filt, y, (ex, ew) in zip(hooks, spec["line_y"],
                                     expected_xy):
            x, gy, w, h = (int(v) for v in filt.find(
                "property[@name='geometry']").text.split())
            self.assertEqual((x, w), (ex, ew))
            self.assertEqual(x + w // 2, MLT_VIDEO["width"] // 2)
            self.assertEqual(gy, y)
            self.assertEqual(h, mlt_stage.HOOK_TITLE_BOX_HEIGHT)
            self.assertGreaterEqual(gy, spec["top_limit"])
            self.assertLessEqual(gy + h, spec["caption_zone_top"])
            self.assertEqual(filt.find(
                "property[@name='in']").text, "00:00:00.000")
            self.assertEqual(filt.find(
                "property[@name='out']").text, "00:00:02.967")
        phrases = [f for f in root.findall("tractor/filter")
                   if (f.get("id") or "").startswith("filter-phrase")]
        self.assertEqual(len(phrases), 2)

    def test_mlt_default_unchanged(self):
        # الافتراضي: عنوان واحد أسفل (y=860، h=150) 0–4ث —
        # y وh والتوقيت بلا تغيير؛ و(v0.1.62) x وw متمركزان
        # بالهندسة المقاسة (halign يتجاهله MLT 7.22).
        xml_text = mlt_stage.build_mlt(MLT_MANIFEST, "هوك صادم",
                                       "/tmp/assets", dict(MLT_VIDEO))
        root = ET.fromstring(xml_text)
        hooks = [f for f in root.findall("tractor/filter")
                 if (f.get("id") or "").startswith("filter-hook")]
        self.assertEqual(len(hooks), 1)
        x, y, w, h = (int(v) for v in hooks[0].find(
            "property[@name='geometry']").text.split())
        self.assertEqual((x, y, w, h), (228, 860, 264, 150))
        self.assertEqual(hooks[0].find(
            "property[@name='out']").text, "00:00:03.967")

    def test_long_video_title_cards_listed_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            ch1 = _fake_chapter(tmp, "القصة الأولى", 2.0)
            ch2 = _fake_chapter(tmp, "القصة الثانية", 2.0)
            intro_wav = os.path.join(tmp, "intro.wav")
            _make_wav(intro_wav, seconds=2)
            spec = {
                "title": "5 قصص مؤثرة",
                "hook": "5 قصص هزّت الأسبوع ده",
                "intro": {"text": "5 قصص هزّت الأسبوع ده",
                          "narration": intro_wav, "duration": 2.0},
                "outro": {"text": "اشترك في القناة",
                          "narration": intro_wav, "duration": 2.0},
                "chapters": [ch1, ch2], "music": None,
                "width": 1280, "height": 720, "fps": 30}
            project, meta = long_video.build_project(spec)
            cards = meta["title_cards"]
            # مقدمة + بطاقتا فصلين + خاتمة — كل بطاقة مرة واحدة.
            self.assertEqual(len(cards), 4)
            self.assertEqual(
                [(c["text"], c["start"], c["end"], c["position"])
                 for c in cards],
                [("5 قصص هزّت الأسبوع ده", 0.0, 3.0, "above"),
                 ("القصة الأولى", 3.0, 6.0, "middle"),
                 ("القصة الثانية", 8.0, 11.0, "middle"),
                 ("اشترك في القناة", 13.0, 16.0, "middle")])
            self.assertEqual(len({(c["text"], c["start"])
                                  for c in cards}), 4)
            # التسجيل لا يضيف حرقًا: مسارات النص كما قبل.
            texts = [t for t in project["tracks"]
                     if t["type"] == "text"]
            self.assertEqual(len(texts), 6)


if __name__ == "__main__":
    unittest.main()
