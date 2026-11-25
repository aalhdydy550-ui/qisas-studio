#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات وحدة الأصول lib/assets.py — جولة تكامل أصول استوديو «قصص وعبر».

كل تجهيزة مولّدة بـffmpeg في مجلد مؤقت (فيديو testsrc ‏720×1280
ثانيتان + صوت sine؛ مؤثر sine بتردد مختلف؛ تراكب mp4 مولّد
بـffmpeg) — بلا اعتماد على ملفات adapted/ الحقيقية إلا في اختبار
الكتالوج (قراءة ADAPTED-AR.md نصًا فقط)، وبلا نسخ أي ملف صوتي
إلى شجرة الاستوديو.

العقد المختبر (حرفيًا من brief الجولة):
- التخطي fail-open: غياب مجلد الأصول أو الأصل المسمّى يرجع الفيديو
  نفسه بلا إعادة ترميز وبلا استثناء (مع تحذير مطبوع).
- الفيديو المدخل غير الموجود يرفع AssetsError؛ وasset_path بـ
  kind/name غير صالح يرفع AssetsError.
- التراكب لا يغطي شريط الكتابة السفلي (CAPTION_BAND_PX ‏200).
- أحداث SFX أزواج (name, at_seconds) — كما في الوحدة
  (``for name, at in events``): مثل ("pop", 1.0).
"""
import array
import contextlib
import io
import math
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.assets import (
    ASSETS_DIR_ENV,
    DEFAULT_ASSETS_DIR,
    BURN_OPACITY,
    GRAIN_OPACITY,
    CAPTION_BAND_PX,
    SFX,
    OVERLAYS,
    AssetsError,
    resolve_assets_dir,
    asset_path,
    add_sfx,
    apply_overlay,
    apply_assets,
)

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADAPTED_MD = os.path.join(
    os.path.dirname(STUDIO_DIR), "studio-work", "drive-assets",
    "adapted", "ADAPTED-AR.md")

WIDTH = 720
HEIGHT = 1280
DURATION = 2.0
SR = 48000
AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".opus")

# الكتالوج المتوقع حرفيًا من العقد (يُثبَّت هنا ليُكشف أي انحراف).
EXPECTED_SFX = {
    "whoosh": "sfx/whoosh-air-woosh.mp3",
    "whoosh-long": "sfx/whoosh-cinematic-transition.mp3",
    "impact": "sfx/impact-big-cinematic.mp3",
    "pop": "sfx/pop-message-alert.mp3",
    "page": "sfx/paper-page-turn.mp3",
    "shutter": "sfx/shutter-camera-click.mp3",
    "coins": "sfx/money-clinking-coins.mp3",
    "cash-register": "sfx/cash-register.mp3",
    "cash-register-short": "sfx/cash-register-short.mp3",
}
EXPECTED_OVERLAYS = {
    "burn": "overlays/overlay-film-burn-720x1280.mp4",
    "grain": "overlays/overlay-film-grain-720x1280.mp4",
}


def _run(cmd, timeout=120):
    """شغّل ffmpeg وارفع عند الفشل مع إظهار الأمر."""
    subprocess.run(cmd, check=True, timeout=timeout,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _decode_f32(path, sr=SR):
    """فكّ صوت ملف إلى عينات float32 أحادية (stdlib فقط)."""
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1",
         "-ar", str(sr), "-f", "f32le", "-"],
        check=True, timeout=120, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    samples = array.array("f")
    samples.frombytes(proc.stdout)
    if sys.byteorder == "big":
        samples.byteswap()
    return samples, sr


def _rms(samples, sr, t0, t1):
    """RMS لعينات الصوت في النافذة [t0, t1) بالثواني."""
    lo = max(0, int(t0 * sr))
    hi = min(len(samples), int(t1 * sr))
    window = samples[lo:hi]
    if not window:
        return 0.0
    return math.sqrt(sum(x * x for x in window) / len(window))


def _goertzel(samples, sr, freq):
    """سعة نغمة نقية بتردد freq عبر خوارزمية Goertzel (بلا numpy)."""
    n = len(samples)
    k = int(round(n * freq / sr))
    w = 2.0 * math.pi * k / n
    coeff = 2.0 * math.cos(w)
    s1 = s2 = 0.0
    for x in samples:
        s0 = x + coeff * s1 - s2
        s2, s1 = s1, s0
    power = s1 * s1 + s2 * s2 - coeff * s1 * s2
    return math.sqrt(max(power, 0.0)) / n


def _grab_frame(path, t=1.0):
    """إطار واحد RGB24 خام عند الثانية t (بايتات)."""
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(t), "-i", path,
         "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        check=True, timeout=120, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    return proc.stdout


def _band_mean_abs_diff(frame_a, frame_b, y0, y1, row_step=5, col_step=5):
    """متوسط فرق القيم المطلقة بين إطارين في شريط صفوف [y0, y1)
    (عيّنة متباعدة — كافية للفصل بين «مطابق» و«متغير»)."""
    total = 0
    count = 0
    stride = WIDTH * 3
    for y in range(y0, y1, row_step):
        base = y * stride
        for x in range(0, WIDTH, col_step):
            off = base + x * 3
            for c in range(3):
                total += abs(frame_a[off + c] - frame_b[off + c])
                count += 1
    return total / count if count else 0.0


def _band_mean_brightness(frame, y0, y1, row_step=5, col_step=5):
    """متوسط السطوع في شريط صفوف (0–255)."""
    total = 0
    count = 0
    stride = WIDTH * 3
    for y in range(y0, y1, row_step):
        base = y * stride
        for x in range(0, WIDTH, col_step):
            off = base + x * 3
            total += frame[off] + frame[off + 1] + frame[off + 2]
            count += 3
    return total / count if count else 0.0


def _audio_files_in_tree(exclude_top=("runs",)):
    """كل الملفات الصوتية في شجرة الاستوديو (مسارات نسبية)."""
    found = set()
    for root, dirs, files in os.walk(STUDIO_DIR):
        rel_root = os.path.relpath(root, STUDIO_DIR)
        if rel_root.split(os.sep)[0] in exclude_top:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs
                   if os.path.join(rel_root, d) not in exclude_top
                   and not (rel_root == "." and d in exclude_top)]
        for name in files:
            if name.lower().endswith(AUDIO_EXTS):
                found.add(os.path.relpath(
                    os.path.join(root, name), STUDIO_DIR))
    return found


class TestAssets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="qisas-assets-")
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self._video = None
        self._white_video = None
        self._assets = None

    # -- تجهيزات مولّدة بـffmpeg (تُبنى عند الطلب وتُحفظ للاختبار) --

    def _make_video(self, bottom_white=False):
        """فيديو اختبار 720×1280 ثانيتان + سرد sine ‏440Hz بمستوى 0.5.
        bottom_white: خلفية سوداء وشريط أبيض أسفل 200 بكسل (بديل
        نص الشاشة في اختبار حماية الشريط)."""
        if bottom_white:
            if self._white_video is None:
                path = os.path.join(self.dir, "video-white.mp4")
                _run(["ffmpeg", "-y", "-v", "error",
                      "-f", "lavfi", "-i",
                      "color=c=black:s=720x1280:r=30:d=2,"
                      "drawbox=x=0:y=1080:w=720:h=200:color=white:t=fill",
                      "-f", "lavfi", "-i",
                      "sine=frequency=440:duration=2",
                      "-af", "volume=0.5",
                      "-c:v", "libx264", "-pix_fmt", "yuv420p",
                      "-c:a", "aac", "-b:a", "128k", "-t", "2", path])
                self._white_video = path
            return self._white_video
        if self._video is None:
            path = os.path.join(self.dir, "video.mp4")
            _run(["ffmpeg", "-y", "-v", "error",
                  "-f", "lavfi", "-i",
                  "testsrc=size=720x1280:rate=30:duration=2",
                  "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                  "-af", "volume=0.5",
                  "-c:v", "libx264", "-pix_fmt", "yuv420p",
                  "-c:a", "aac", "-b:a", "128k", "-t", "2", path])
            self._video = path
        return self._video

    def _make_assets_dir(self, sfx=True, overlay=True):
        """مجلد أصول مؤقت بأسماء الكتالوج نفسها: مؤثر sine ‏1200Hz
        ‏0.3ث بمستوى 0.9، وتراكب أحمر ثابت 720×1280 ثانيتان."""
        if self._assets is not None:
            return self._assets
        base = os.path.join(self.dir, "assets")
        if sfx:
            os.makedirs(os.path.join(base, "sfx"), exist_ok=True)
            _run(["ffmpeg", "-y", "-v", "error",
                  "-f", "lavfi", "-i", "sine=frequency=1200:duration=0.3",
                  "-af", "volume=0.9",
                  "-c:a", "libmp3lame", "-b:a", "128k",
                  os.path.join(base, "sfx", "pop-message-alert.mp3")])
        if overlay:
            os.makedirs(os.path.join(base, "overlays"), exist_ok=True)
            _run(["ffmpeg", "-y", "-v", "error",
                  "-f", "lavfi", "-i", "color=c=red:s=720x1280:r=30:d=2",
                  "-c:v", "libx264", "-pix_fmt", "yuv420p",
                  os.path.join(base, "overlays",
                               "overlay-film-burn-720x1280.mp4")])
        self._assets = base
        return base

    # -- 2) التخطي عند غياب مجلد الأصول --

    def test_02_skip_when_assets_dir_missing(self):
        """resolve_assets_dir على مجلد فارغ → ‏apply_assets يرجع
        الفيديو نفسه بلا استثناء وبلا ملف جديد (مع تحذير مطبوع)."""
        video = self._make_video()
        empty = os.path.join(self.dir, "empty-assets")
        os.makedirs(empty)
        resolved = resolve_assets_dir(explicit=empty)
        self.assertIsNotNone(resolved, "المجلد الصريح الفارغ يجب أن يُرجَع")
        self.assertEqual(os.path.normpath(resolved),
                         os.path.normpath(empty))
        out = os.path.join(self.dir, "skipped.mp4")
        buf_out, buf_err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf_out), \
                contextlib.redirect_stderr(buf_err):
            result = apply_assets(
                video, out,
                sfx=[("pop", 0.5)],
                overlays=["burn"], assets_dir=resolved)
        self.assertEqual(os.path.abspath(result), os.path.abspath(video))
        self.assertFalse(os.path.exists(out), "ملف جديد رغم التخطي")
        self.assertTrue((buf_out.getvalue() + buf_err.getvalue()).strip(),
                        "التخطي بلا تحذير مطبوع")

    # -- 3) التخطي عند غياب أصل مسمّى --

    def test_03_missing_named_asset_skips_only_it(self):
        """مؤثر مسمّى غائب + مؤثر موجود → يُطبَّق الموجود ويُحذَّر
        عن الغائب؛ وasset_path للملف الغائب يرجع None."""
        video = self._make_video()
        assets = self._make_assets_dir(sfx=True, overlay=False)
        self.assertIsNone(asset_path("sfx", "whoosh", assets_dir=assets))
        out = os.path.join(self.dir, "sfx-only.mp4")
        buf_out, buf_err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf_out), \
                contextlib.redirect_stderr(buf_err):
            result = apply_assets(
                video, out,
                sfx=[("pop", 0.5), ("whoosh", 0.5)],
                overlays=(), assets_dir=assets)
        warned = buf_out.getvalue() + buf_err.getvalue()
        self.assertIn("whoosh", warned, "لا تحذير باسم الأصل الغائب")
        self.assertEqual(os.path.abspath(result), os.path.abspath(out))
        self.assertTrue(os.path.exists(out))
        samples, sr = _decode_f32(out)
        near = _rms(samples, sr, 0.5, 0.8)
        far = _rms(samples, sr, 1.5, 1.8)
        self.assertGreater(far, 0.0, "السرد غائب من الخرج")
        gain_db = 20.0 * math.log10(near / far)
        self.assertGreaterEqual(
            gain_db, 1.5,
            "المؤثر الموجود لم يُطبَّق (الطاقة قرب الحدث %s dB فقط)"
            % round(gain_db, 2))

    # -- 4) التراكب لا يغطي نص الشاشة --

    def test_04_overlay_protects_caption_band(self):
        """فيديو بشريط أبيض أسفل 200 بكسل → بعد apply_overlay
        أسفل 200 بكسل مطابق للبكسل، وفوقه متغير. «مطابق» هنا
        بمتوسط فرق < 2 لكل قناة لأن إعادة الترميز lossy قد
        تحرّك بكسلًا بدرجة أو درجتين؛ ويُشترط أيضًا بقاء
        الشريط أبيض (سطوع > 230)."""
        video = self._make_video(bottom_white=True)
        assets = self._make_assets_dir()
        out = os.path.join(self.dir, "overlayed.mp4")
        result = apply_overlay(video, "burn", out, assets_dir=assets)
        self.assertEqual(os.path.abspath(result), os.path.abspath(out))
        self.assertTrue(os.path.exists(out))
        before = _grab_frame(video)
        after = _grab_frame(out)
        self.assertEqual(len(before), WIDTH * HEIGHT * 3)
        self.assertEqual(len(after), len(before))
        band = HEIGHT - CAPTION_BAND_PX
        bottom_diff = _band_mean_abs_diff(before, after, band, HEIGHT)
        self.assertLess(bottom_diff, 2.0,
                        "التراكب غيّر شريط الكتابة (متوسط الفرق %s)"
                        % round(bottom_diff, 2))
        self.assertGreater(_band_mean_brightness(after, band, HEIGHT),
                           230.0, "الشريط السفلي لم يعد أبيض")
        top_diff = _band_mean_abs_diff(before, after, 0, band)
        self.assertGreater(top_diff, 20.0,
                           "التراكب لم يغيّر شيئًا فوق الشريط (%s)"
                           % round(top_diff, 2))

    # -- 5) أولوية resolve_assets_dir --

    def test_05_resolve_assets_dir_priority(self):
        """صريح > بيئة > افتراضي."""
        self.assertEqual(ASSETS_DIR_ENV, "QISAS_ASSETS_DIR")
        self.assertEqual(DEFAULT_ASSETS_DIR,
                         "~/workspace/studio-work/drive-assets/adapted/")
        dir_a = os.path.join(self.dir, "env-assets")
        dir_b = os.path.join(self.dir, "explicit-assets")
        os.makedirs(dir_a)
        os.makedirs(dir_b)
        old_env = os.environ.get(ASSETS_DIR_ENV)
        old_home = os.environ.get("HOME")
        try:
            os.environ[ASSETS_DIR_ENV] = dir_a
            self.assertEqual(os.path.normpath(
                resolve_assets_dir(explicit=dir_b)),
                os.path.normpath(dir_b), "الصريح يجب أن يغلب البيئة")
            self.assertEqual(os.path.normpath(resolve_assets_dir()),
                             os.path.normpath(dir_a),
                             "البيئة يجب أن تغلب الافتراضي")
            os.environ.pop(ASSETS_DIR_ENV, None)
            home = os.path.join(self.dir, "home")
            default_rel = os.path.join(
                "workspace", "studio-work", "drive-assets", "adapted")
            os.makedirs(os.path.join(home, default_rel))
            os.environ["HOME"] = home
            expected = os.path.join(home, default_rel)
            self.assertEqual(os.path.normpath(resolve_assets_dir()),
                             os.path.normpath(expected),
                             "بلا صريح وبلا بيئة يجب إرجاع الافتراضي")
        finally:
            if old_env is None:
                os.environ.pop(ASSETS_DIR_ENV, None)
            else:
                os.environ[ASSETS_DIR_ENV] = old_env
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home

    # -- 6) اسم غير صالح --

    def test_06_invalid_asset_name_raises(self):
        """asset_path بـkind/name خاطئ → ‏AssetsError."""
        assets = self._make_assets_dir()
        for kind, name in (("bogus", "serene"),
                           ("sfx", ""),
                           ("", "pop"),
                           ("overlays", "no-such-overlay")):
            with self.assertRaises(AssetsError, msg="%r/%r" % (kind, name)):
                asset_path(kind, name, assets_dir=assets)
        # والصحيح لا يرفع: مسار موجود لملف موجود، وNone لملف غائب.
        # kind التراكب مفرد ("overlay") كما في الوحدة.
        found_ov = asset_path("overlay", "burn", assets_dir=assets)
        self.assertIsNotNone(found_ov)
        self.assertTrue(found_ov.endswith(
            "overlays/overlay-film-burn-720x1280.mp4"))

    # -- 7) apply_assets بلا طلبات --

    def test_07_apply_assets_without_requests_is_noop(self):
        """apply_assets بلا مؤثرات ولا تراكبات →
        الفيديو نفسه بلا ملف جديد (حتى مع وجود أصول)."""
        video = self._make_video()
        assets = self._make_assets_dir()
        out = os.path.join(self.dir, "noop.mp4")
        result = apply_assets(video, out, assets_dir=assets)
        self.assertEqual(os.path.abspath(result), os.path.abspath(video))
        self.assertFalse(os.path.exists(out), "ملف جديد رغم غياب الطلبات")

    # -- 8) أحداث SFX في زمنها --

    def test_08_sfx_events_land_on_time(self):
        """طاقة الصوت حول at_seconds أعلى منها بعيدًا عنه
        (مؤثر 0.3ث عند 1.0ث؛ النافذة القريبة 0.95–1.30ث
        مقابل البعيدة 1.50–1.80ث)."""
        video = self._make_video()
        assets = self._make_assets_dir()
        out = os.path.join(self.dir, "sfx.mp4")
        result = add_sfx(video, [("pop", 1.0)],
                         out, assets_dir=assets)
        self.assertEqual(os.path.abspath(result), os.path.abspath(out))
        self.assertTrue(os.path.exists(out))
        samples, sr = _decode_f32(out)
        near = _rms(samples, sr, 0.95, 1.30)
        far = _rms(samples, sr, 1.50, 1.80)
        self.assertGreater(far, 0.0, "السرد غائب من الخرج")
        gain_db = 20.0 * math.log10(near / far)
        self.assertGreaterEqual(
            gain_db, 2.0,
            "لا ذروة طاقة حول at_seconds (الفرق %s dB فقط)"
            % round(gain_db, 2))

    # -- 9) الكتالوج موثّق في ADAPTED-AR.md --

    def test_09_catalog_documented_in_adapted_md(self):
        """كل مسار في SFX/OVERLAYS اسم ملف موجود في
        ADAPTED-AR.md (بما فيه cash-register-short.mp3)؛
        والثوابت مطابقة للعقد."""
        self.assertEqual(SFX, EXPECTED_SFX)
        self.assertEqual(OVERLAYS, EXPECTED_OVERLAYS)
        self.assertEqual(BURN_OPACITY, 0.85)
        self.assertEqual(GRAIN_OPACITY, 0.12)
        self.assertEqual(CAPTION_BAND_PX, 200)
        if not os.path.exists(ADAPTED_MD):
            # ADAPTED-AR.md وثيقة أصول تعيش خارج الشجرة
            # (studio-work/) فلا توجد في CI أبدًا — فحص التوثيق
            # يعمل محليًا فقط، وتأكيدات الثوابت أعلاه تعمل
            # في كل البيئات.
            self.skipTest("ADAPTED-AR.md غير موجود في هذه البيئة")
        with open(ADAPTED_MD, encoding="utf-8") as fh:
            doc = fh.read()
        catalog = dict(SFX)
        catalog.update(OVERLAYS)
        for name, rel_path in sorted(catalog.items()):
            self.assertIn(rel_path, doc,
                          "الأصل %r (%s) غير موثّق في ADAPTED-AR.md"
                          % (name, rel_path))

    # -- 10) لا نسخ إلى الشجرة؛ التوصيل من خارجها --

    def test_10_assets_read_from_outside_tree_nothing_copied_in(self):
        """apply_assets يعمل بمجلد أصول مؤقت خارج الشجرة ولا
        ينسخ شيئًا إليها. الثابت القابل للإنفاذ هو «لا ملف
        صوتي جديد»: الشجرة تحوي أصلًا ملفات صوتية سابقة
        (مخرجات runs/، وtests/fixtures/adversarial/no-silence.wav — تحقق
        2026-11-25) فلا يصح ادعاء «صفر ملف صوتي» مطلقًا؛
        لذا تُقارن لقطة قبل/بعد باستثناء runs/ (مخرجات
        تشغيل تتغير تحت الكرونات)، وتُفحص أسماء الكتالوج."""
        assets = self._make_assets_dir()
        self.assertFalse(
            os.path.abspath(assets).startswith(
                os.path.abspath(STUDIO_DIR) + os.sep),
            "تجهيزة الأصول يجب أن تكون خارج الشجرة")
        video = self._make_video()
        before = _audio_files_in_tree()
        for rel_path in list(SFX.values()) \
                + list(OVERLAYS.values()):
            self.assertNotIn(os.path.basename(rel_path),
                             {os.path.basename(p) for p in before},
                             "اسم كتالوج %s موجود أصلًا في الشجرة"
                             % rel_path)
        out = os.path.join(self.dir, "full.mp4")
        result = apply_assets(
            video, out,
            sfx=[("pop", 0.5)],
            overlays=["burn"], assets_dir=assets)
        self.assertEqual(os.path.abspath(result), os.path.abspath(out))
        self.assertTrue(os.path.exists(out))
        self.assertFalse(os.path.abspath(out).startswith(
            os.path.abspath(STUDIO_DIR) + os.sep),
            "الخرج يجب أن يبقى خارج الشجرة")
        after = _audio_files_in_tree()
        self.assertEqual(before, after,
                         "نُسخ ملف صوتي إلى الشجرة: %s"
                         % sorted(after - before))

    # -- قاعدة العقد خارج العشرة: الفيديو المدخل غير الموجود --

    def test_11_missing_input_video_raises(self):
        """الفيديو المدخل غير الموجود → ‏AssetsError (بلا إنشاء خرج)."""
        assets = self._make_assets_dir()
        missing = os.path.join(self.dir, "no-such-video.mp4")
        out = os.path.join(self.dir, "should-not-exist.mp4")
        with self.assertRaises(AssetsError):
            apply_assets(missing, out, assets_dir=assets)
        with self.assertRaises(AssetsError):
            add_sfx(missing, [("pop", 0.5)],
                    out, assets_dir=assets)
        with self.assertRaises(AssetsError):
            apply_overlay(missing, "burn", out, assets_dir=assets)
        self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
