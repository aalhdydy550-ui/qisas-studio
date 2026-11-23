#!/usr/bin/env python3
"""اختبارات انحدار لـnumpy في CI — جولة v0.1.42 (إصلاح CI #255).

الفرضية المثبتة عمليًا: بلا numpy يرفع detect_text_bands
‏CheckError فيُمسكها qa_safe_area ويتخطى الكشف البكسلي
فيُرجع ok=True، فتفشل اختبارات فيديو QA الثلاثة بـ
«AssertionError: True is not false»؛ ومع numpy تمر. وتخطئ
اختبارات TestQaSafeAreaBands الخمسة مباشرةً بـCheckError.

تُتحقق هنا بتشغيل الاختبارات المستهدفة في عملية فرعية
يُحجب فيها numpy وحده عبر PYTHONPATH (stub ‏numpy.py يرفع
‏ImportError) مع توريث باقي البيئة — لا بنمط HOME الفارغة
في test_ci_skips.py، لأن HOME الفارغة تخفي site-packages
المستخدم فينزل Pillow لإصدار نظام قديم بلا get_flattened_data
فيفشل count_gold_pixels بـAttributeError قبل الوصول إلى
‏qa_safe_area أصلًا (فخ وقعنا فيه أثناء الإثبات).
"""
import os
import subprocess
import sys
import tempfile
import unittest

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

QA_VIDEO_TESTS = [
    "tests.test_check.TestQaSafeAreaVideo.test_top_text_video_fails_qa",
    "tests.test_check.TestQaSafeAreaVideo.test_clipped_text_video_fails_qa",
    "tests.test_check.TestQaSafeAreaVideo."
    "test_video_without_ass_checks_frames_only",
]

_NUMPY_STUB = ("raise ImportError('numpy محظورة عمدا "
               "(محاكاة CI بلا numpy)')\n")


def _numpy_stub_dir():
    """مجلد مؤقت فيه numpy.py يرفع ImportError عند الاستيراد."""
    stub = tempfile.mkdtemp(prefix="no-numpy-")
    with open(os.path.join(stub, "numpy.py"), "w",
              encoding="utf-8") as fh:
        fh.write(_NUMPY_STUB)
    return stub


def _run_tests(test_ids, block_numpy):
    """شغّل اختبارات في عملية فرعية؛ block_numpy يحجب numpy
    وحدها عبر PYTHONPATH مع توريث باقي البيئة. يرجع
    (returncode, stdout+stderr)."""
    env = dict(os.environ)
    if block_numpy:
        stub = _numpy_stub_dir()
        old = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = stub + (os.pathsep + old if old else "")
    proc = subprocess.run(
        [sys.executable, "-m", "unittest"] + list(test_ids) + ["-v"],
        cwd=STUDIO_DIR, capture_output=True, text=True,
        env=env, timeout=600)
    return proc.returncode, proc.stdout + proc.stderr


class TestCiNumpy(unittest.TestCase):
    def test_ci_installs_numpy(self):
        """انحدار: سير العمل يثبّت numpy (سبب 8 فشلًا في #255:
        5 أخطاء TestQaSafeAreaBands + 3 فشل فيديو QA)."""
        path = os.path.join(STUDIO_DIR, ".github", "workflows",
                            "ci.yml")
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        self.assertIn("pip install pyyaml pillow numpy", content)

    def test_qa_video_tests_fail_without_numpy(self):
        """انحدار: بلا numpy تفشل اختبارات فيديو QA الثلاثة
        بـ«True is not false» لأن الكشف البكسلي يُتخطى فيُرجع
        qa ‏ok=True (lib/check.py سطر ~411)."""
        rc, out = _run_tests(QA_VIDEO_TESTS, block_numpy=True)
        self.assertNotEqual(rc, 0, out[-2000:])
        self.assertIn("FAILED", out)
        self.assertIn("failures=3", out)
        self.assertIn("True is not false", out)
        self.assertIn("الكشف البكسلي متخطى", out)

    def test_qa_video_tests_pass_with_numpy(self):
        """انحدار: مع numpy تمر اختبارات فيديو QA الثلاثة."""
        rc, out = _run_tests(QA_VIDEO_TESTS, block_numpy=False)
        self.assertEqual(rc, 0, out[-2000:])
        self.assertIn("OK", out)
        self.assertNotIn("skipped", out.lower())

    def test_qa_bands_error_without_numpy(self):
        """انحدار: بلا numpy تخطئ اختبارات TestQaSafeAreaBands
        الخمسة (detect_text_bands يرفع CheckError عند غياب
        numpy — lib/check.py سطر ~573)."""
        rc, out = _run_tests(
            ["tests.test_check.TestQaSafeAreaBands"],
            block_numpy=True)
        self.assertNotEqual(rc, 0, out[-2000:])
        self.assertIn("ERROR", out)
        self.assertIn("errors=5", out)
        self.assertIn("numpy", out)


if __name__ == "__main__":
    unittest.main()
