#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
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

    def test_llm_all_failed(self):
        _assert_arabic_explanation(
            self,
            errors.explain_error(
                "فشلت كل مزودات الذكاء (2): ddgw/gpt-5.4-mini "
                "(quota)؛ gemini-3-flash-preview (auth)"),
            "llm_all_failed")

    def test_llm_all_failed_exception(self):
        from lib.omniroute_client import LLMAllFailedError
        err = LLMAllFailedError(
            [("ddgw/gpt-5.4-mini", "quota", "HTTP 429"),
             ("gemini-3-flash-preview", "auth", "HTTP 401")])
        _assert_arabic_explanation(
            self, errors.explain_error(err), "llm_all_failed")


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



class TestErrorCodes(unittest.TestCase):
    """رموز الأخطاء الثابتة وروابط runbook — جولة تطبيق الأنماط (W5b)."""

    def test_every_category_has_a_stable_code(self):
        for category in errors.CATEGORIES:
            code = errors.error_code(category)
            self.assertRegex(
                code, r"^STUDIO-[A-Z]+-\d{3}$",
                "رمز غير صالح للفئة %s: %s" % (category, code))

    def test_codes_are_unique(self):
        codes = [errors.error_code(c) for c in errors.CATEGORIES]
        self.assertEqual(len(codes), len(set(codes)),
                         "رمزان مكرران: %r" % (codes,))

    def test_every_category_has_a_runbook_link(self):
        for category in errors.CATEGORIES:
            link = errors.runbook_link(category)
            self.assertTrue(
                link.startswith("docs/ERRORS-RUNBOOK.md#studio-"),
                "رابط runbook غير صالح للفئة %s: %s" % (category, link))
            self.assertIn(errors.error_code(category).lower(),
                          link)

    def test_unknown_category_falls_back_to_unknown_code(self):
        self.assertEqual(errors.error_code("nope"),
                         "STUDIO-UNKNOWN-001")
        self.assertEqual(errors.error_code(None), "STUDIO-UNKNOWN-001")

    def test_explain_error_carries_code_and_runbook(self):
        result = errors.explain_error("ffmpeg: command not found")
        self.assertEqual(result["code"], "STUDIO-FFMPEG-001")
        self.assertEqual(result["runbook"],
                         "docs/ERRORS-RUNBOOK.md#studio-ffmpeg-001")

    def test_explain_error_unknown_carries_unknown_code(self):
        result = errors.explain_error(
            "Something completely unexpected happened at 0xDEADBEEF")
        self.assertEqual(result["code"], "STUDIO-UNKNOWN-001")
        self.assertEqual(result["runbook"],
                         "docs/ERRORS-RUNBOOK.md#studio-unknown-001")

    def test_format_error_prints_code_and_runbook(self):
        text = errors.format_error(
            errors.explain_error("quotaExceeded"))
        self.assertIn("STUDIO-YOUTUBE-002", text)
        self.assertIn("docs/ERRORS-RUNBOOK.md#studio-youtube-002", text)

    def test_runbook_has_a_section_for_every_code(self):
        studio_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(studio_dir, "docs", "ERRORS-RUNBOOK.md")
        self.assertTrue(os.path.isfile(path), "ملف runbook غائب: %s" % path)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        for category in errors.CATEGORIES:
            code = errors.error_code(category)
            # عنوان القسم يحمل الرمز حرفيًا (ومرساته المشتقة مطابقة
            # لرابط runbook_link).
            self.assertIn("## %s" % code, content,
                          "لا قسم في runbook للرمز %s" % code)
            anchor = errors.runbook_anchor(code)
            self.assertEqual(anchor, "#" + code.lower())


if __name__ == "__main__":
    unittest.main()
