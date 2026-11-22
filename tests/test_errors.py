#!/usr/bin/env python3
"""اختبارات انحدار لترجمة الأخطاء (lib.errors) — الجولة 6 (بند 9).

تعمل بـ `python3 -m unittest tests.test_errors -v` من
~/workspace/studio/. بلا شبكة وبلا ملفات حقيقية: كل اختبار
يمرّر نص/استثناء محاكى إلى explain_error ويتحقق أن الناتج
عربي وفيه «ماذا حدث» و«ماذا تفعل» وخطوة عملية.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import errors

# كل ترجمة يجب أن تحوي هذه المفاتيح.
REQUIRED_KEYS = ("category", "title", "what_happened", "what_to_do",
                 "steps", "original", "ماذا حدث", "ماذا تفعل")


def _assert_arabic_explanation(test, result, category):
    test.assertEqual(result["category"], category)
    for key in REQUIRED_KEYS:
        test.assertIn(key, result, "مفتاح %s غائب" % key)
    test.assertTrue(result["what_happened"],
                    "«ماذا حدث» فارغة")
    test.assertTrue(result["what_to_do"],
                    "«ماذا تفعل» فارغة")
    test.assertEqual(result["ماذا حدث"], result["what_happened"])
    test.assertEqual(result["ماذا تفعل"], result["what_to_do"])
    # عربي فعلًا: معظم الحروف عربية.
    joined = result["what_happened"] + result["what_to_do"]
    arabic = sum(1 for ch in joined if "\u0600" <= ch <= "\u06FF")
    test.assertGreater(arabic, len(joined) // 2,
                       "الناتج ليس عربيًا في معظمه: %r" % joined)
    # خطوة عملية واحدة على الأقل: أمر أو ملف أو مسار.
    steps = result["steps"]
    test.assertIsInstance(steps, list)
    test.assertGreaterEqual(len(steps), 1)
    test.assertTrue(any(("studio.py" in s or "ls " in s or "config.yaml" in s
                         or "which " in s or "ffprobe" in s or "~/" in s)
                        for s in steps),
                    "لا خطوة عملية في: %r" % (steps,))


class TestFfmpegErrors(unittest.TestCase):
    def test_ffmpeg_not_found(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error("ffmpeg: command not found"),
            "ffmpeg_not_found")

    def test_ffprobe_not_found_arabic(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error("الأمر غير موجود: ffprobe"),
            "ffmpeg_not_found")

    def test_ffmpeg_encode_failed(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error(
                "Conversion failed! Error while opening encoder "
                "for output stream #0:0"),
            "ffmpeg_encode_failed")

    def test_ffmpeg_no_audio(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error(
                "Stream map '0:a' matches no streams. "
                "File does not contain any audio stream."),
            "ffmpeg_no_audio")

    def test_ffmpeg_no_audio_arabic(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error("لا يوجد مسار صوتي في الفيديو"),
            "ffmpeg_no_audio")


class TestOpenMontageErrors(unittest.TestCase):
    def test_project_missing(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error(
                "مشروع OpenMontage غير موجود: "
                "/home/hatch/workspace/openmontage/projects/nope"),
            "openmontage_project_missing")

    def test_stage_failed_script(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error(
                "ملف السيناريو غير موجود: "
                ".../projects/x/artifacts/script.json"),
            "openmontage_stage_failed")

    def test_stage_failed_no_images(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error("لا توجد صور في: .../assets/images"),
            "openmontage_stage_failed")


class TestFacebookErrors(unittest.TestCase):
    def test_facebook_not_installed(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error("facebook-cli غير متاح في PATH"),
            "facebook_not_installed")

    def test_facebook_token_expired(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error(
                "Error validating access token: Session has expired "
                "on Sunday, 22-Nov-26 (#190)"),
            "facebook_token")

    def test_facebook_publish_failed(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error(
                "فشل النشر على فيسبوك (رمز الخروج 1): "
                "Error (#200) Requires pages_manage_posts permission"),
            "facebook_publish_failed")


class TestYoutubeErrors(unittest.TestCase):
    def test_youtube_token_expired(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error(
                "invalid_grant: Token has been expired or revoked."),
            "youtube_token_expired")

    def test_youtube_token_expired_arabic(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error(
                "لا يوجد توكن يوتيوب صالح (youtube-token.json) — "
                "أكمل إعداد OAuth لمرة واحدة"),
            "youtube_token_expired")

    def test_youtube_quota(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error(
                "HttpError 403: The request cannot be completed "
                "because you have exceeded your quota. "
                "(quotaExceeded)"),
            "youtube_quota")

    def test_youtube_upload_failed(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error(
                "فشل الرفع على يوتيوب (رمز الخروج 1): "
                "رفض YouTube API الرفع: b'...HttpError 400...'"),
            "youtube_upload_failed")


class TestGenericAndVeoErrors(unittest.TestCase):
    def test_file_missing(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error(
                "[Errno 2] No such file or directory: "
                "'/tmp/nonexistent-video.mp4'"),
            "file_missing")

    def test_file_missing_arabic(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error(
                "ملف الفيديو غير موجود: /tmp/nonexistent-video.mp4"),
            "file_missing")

    def test_veo_balance_low(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error(
                "رصيد Veo المسجَّل 80 وحدة — أقل من فيديو Veo واحد "
                "(120 وحدة)"),
            "veo_balance_low")

    def test_veo_balance_stale(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error("رصيد Veo غير مسجَّل في الإعداد"),
            "veo_balance_stale")

    def test_concat_export_failed(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error("التصدير لم يكتمل: "
                                 '{"state": "failed"}'),
            "concat_export_failed")


class TestUnknownAndEdgeCases(unittest.TestCase):
    def test_unknown_error_generic_message(self):
        result = errors.explain_error(
            "Something completely unexpected happened at 0xDEADBEEF")
        _assert_arabic_explanation(self, result, "unknown")
        self.assertIn("غير متوقع", result["what_happened"])

    def test_empty_input_returns_generic(self):
        for empty in ("", "   ", None):
            result = errors.explain_error(empty)
            _assert_arabic_explanation(self, result, "unknown")

    def test_exception_object_input(self):
        result = errors.explain_error(
            RuntimeError("Conversion failed!"))
        self.assertEqual(result["category"], "ffmpeg_encode_failed")
        self.assertIn("Conversion failed", result["original"])

    def test_context_disambiguates_token(self):
        fb = errors.explain_error("Token has expired",
                                  context="facebook")
        self.assertEqual(fb["category"], "facebook_token")
        yt = errors.explain_error("Token has expired",
                                  context="youtube")
        self.assertEqual(yt["category"], "youtube_token_expired")

    def test_format_error_contains_sections(self):
        text = errors.format_error(
            errors.explain_error("quotaExceeded"))
        self.assertIn("ماذا حدث:", text)
        self.assertIn("ماذا تفعل:", text)
        self.assertIn("quotaExceeded", text)  # الأصل محفوظ للتشخيص

    def test_explain_error_text_returns_string(self):
        text = errors.explain_error_text("No such file or directory")
        self.assertIsInstance(text, str)
        self.assertIn("ماذا حدث:", text)

    def test_ssl_wrong_version_maps_to_youtube_upload(self):
        # الجولة 6: فشل الشبكة المميز لهذه الـVM — بروكسي TLS يرفض
        # youtube.googleapis.com بخطأ WRONG_VERSION_NUMBER.
        result = errors.explain_error(
            "ssl.SSLError: [SSL: WRONG_VERSION_NUMBER] wrong version "
            "number (_ssl.c:1000)", context="youtube")
        self.assertEqual(result["category"], "youtube_upload_failed")
        self.assertIn("WRONG_VERSION_NUMBER",
                      errors.format_error(result))

    def test_connection_error_youtube_maps_to_upload_failed(self):
        result = errors.explain_error(
            "ConnectionError: youtube.googleapis.com", context="youtube")
        self.assertEqual(result["category"], "youtube_upload_failed")

    def test_ssl_error_without_context_stays_unknown(self):
        # بلا سياق يوتيوب/فيسبوك لا نخمّن المنصة.
        result = errors.explain_error(
            "ssl.SSLError: [SSL: WRONG_VERSION_NUMBER]")
        self.assertEqual(result["category"], "unknown")

    def test_never_raises(self):
        # مدخلات غريبة لا تكسر الدالة أبدًا.
        for weird in (None, "", 0, [], {}, object()):
            result = errors.explain_error(weird)
            self.assertIn("category", result)
            self.assertIn("ماذا حدث", result)


class TestClipOutput(unittest.TestCase):
    """قصّ المخرجات الطويلة — جولة v0.1.37 (مقترح tinker رقم 12)."""

    def test_short_text_returned_unchanged(self):
        text = "\n".join("سطر %d" % i for i in range(10))
        self.assertEqual(errors.clip_output(text), text)

    def test_long_text_clipped_head_and_tail(self):
        text = "\n".join("سطر %d" % i for i in range(50))
        out = errors.clip_output(text)
        lines = out.splitlines()
        self.assertEqual(len(lines), 17)  # 8 رأس + سطر الحذف + 8 ذيل
        self.assertEqual(lines[0], "سطر 0")
        self.assertEqual(lines[-1], "سطر 49")
        self.assertIn("حُذفت 34 سطرًا", lines[8])

    def test_none_and_empty(self):
        self.assertEqual(errors.clip_output(None), "")
        self.assertEqual(errors.clip_output(""), "")

    def test_format_error_clips_long_original(self):
        long_msg = "\n".join("سطر %d" % i for i in range(50))
        text = errors.format_error(
            errors.explain_error("FileNotFoundError: " + long_msg))
        self.assertIn("حُذفت", text)
        self.assertIn("سطر 49", text)  # الذيل محفوظ
        self.assertNotIn("سطر 25", text)  # الوسط محذوف



if __name__ == "__main__":
    unittest.main()
