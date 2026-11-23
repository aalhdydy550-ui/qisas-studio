#!/usr/bin/env python3
"""اختبارات إكمال نشر TikTok/Instagram كوديًا — جولة v0.1.39.

يغطي: التحقق الكامل من الحمولة قبل أي شبكة (فيديو/نص/وسوم/
مدة/أبعاد/صوت/مصغرة)، تحقق الإعدادات عبر lib.errors، وضع
--dry-run بلا أي طلب شبكة، شكل النتيجة الموحّد، وحالة
«ناقص إعداد» في doctor --accounts.

بلا أي اتصال شبكي وبلا أي نشر حقيقي — كل الشبكة محاكاة
(mock) ويُتأكد من عدم استدعائها في مسار dry-run.
"""
import datetime
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import accounts
from lib import errors as errors_lib
from lib import social_publish as sp

TODAY = datetime.date(2026, 11, 22)
UPLOAD_SCOPE = accounts.YT_UPLOAD_SCOPE


def _mp4(tmpdir, size=1024):
    path = os.path.join(tmpdir, "video.mp4")
    with open(path, "wb") as f:
        f.write(b"\x00" * size)
    return path


def _thumb(tmpdir, name="thumb.jpg"):
    path = os.path.join(tmpdir, name)
    with open(path, "wb") as f:
        f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    return path


def _tags(n):
    return " ".join("#وسم%d" % i for i in range(n))


def _probe(duration=45.0, width=720, height=1280, has_audio=True):
    return {"duration": duration, "width": width, "height": height,
            "has_audio": has_audio}


def _yt_token_file(td, days_ago=1):
    path = os.path.join(td, "youtube-token.json")
    data = {"token": "ya29.fake", "expiry": "2026-11-22T10:00:00Z",
            "scopes": [UPLOAD_SCOPE],
            "token_uri": "https://oauth2.googleapis.com/token",
            "refresh_token": "1//fake-refresh"}
    Path(path).write_text(json.dumps(data), encoding="utf-8")
    mtime = datetime.datetime(2026, 11, 22) - datetime.timedelta(
        days=days_ago)
    stamp = mtime.timestamp()
    os.utime(path, (stamp, stamp))
    return path


def _fb_proc(results, returncode=0):
    proc = mock.MagicMock()
    proc.returncode = returncode
    proc.stdout = json.dumps({"results": results})
    proc.stderr = ""
    return proc


class TestValidatePayload(unittest.TestCase):
    def test_valid_tiktok_payload_passes(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            info = sp.validate_social_payload(
                "tiktok", video, "عنوان القصة", "كابشن قصير")
            self.assertEqual(info["platform"], "tiktok")
            self.assertEqual(info["size"], 1024)
            self.assertEqual(info["text_length"],
                             len("عنوان القصة\nكابشن قصير"))

    def test_valid_instagram_payload_passes(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            info = sp.validate_social_payload(
                "instagram", video, "عنوان", "كابشن",
                ig_user_id="123456789")
            self.assertEqual(info["ig_user_id"], "123456789")
            self.assertEqual(info["hashtags"], [])

    def test_missing_video_rejected_arabic(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.validate_social_payload(
                    "tiktok", os.path.join(td, "nope.mp4"),
                    "عنوان", "")
            self.assertIn("غير موجود", str(cm.exception))

    def test_non_mp4_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "video.mov")
            with open(path, "wb") as f:
                f.write(b"\x00" * 10)
            with self.assertRaises(sp.SocialPublishError):
                sp.validate_social_payload(
                    "instagram", path, "عنوان", "",
                    ig_user_id="123456789")

    def test_empty_text_rejected_arabic(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.validate_social_payload("tiktok", video, "  ", "")
            self.assertIn("فارغ", str(cm.exception))
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.validate_social_payload(
                    "instagram", video, "", "",
                    ig_user_id="123456789")
            self.assertIn("فارغ", str(cm.exception))

    def test_tiktok_text_too_long_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.validate_social_payload("tiktok", video, "x" * 2201,
                                           "")
            self.assertIn("2200", str(cm.exception))

    def test_instagram_caption_too_long_rejected(self):
        # كان instagram_reel_payload بلا حد كابشن أصلًا — الآن
        # 2200 حرفًا مثل TikTok.
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.validate_social_payload(
                    "instagram", video, "x" * 2201, "",
                    ig_user_id="123456789")
            self.assertIn("2200", str(cm.exception))

    def test_instagram_excess_hashtags_rejected_arabic(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.validate_social_payload(
                    "instagram", video, "عنوان", _tags(31),
                    ig_user_id="123456789")
            self.assertIn("وسوم", str(cm.exception))
            self.assertIn("30", str(cm.exception))

    def test_instagram_30_hashtags_pass(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            info = sp.validate_social_payload(
                "instagram", video, "عنوان", _tags(30),
                ig_user_id="123456789")
            self.assertEqual(len(info["hashtags"]), 30)

    def test_instagram_missing_user_id_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.validate_social_payload("instagram", video,
                                           "عنوان", "")
            self.assertIn("معرّف حساب Instagram مفقود",
                          str(cm.exception))

    def test_unknown_platform_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with self.assertRaises(sp.SocialPublishError):
                sp.validate_social_payload("facebook", video,
                                           "عنوان", "")

    def test_duration_over_limit_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.validate_social_payload(
                    "instagram", video, "عنوان", "",
                    ig_user_id="123456789",
                    probe_info=_probe(duration=120.0))
            self.assertIn("90", str(cm.exception))
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.validate_social_payload(
                    "tiktok", video, "عنوان", "",
                    probe_info=_probe(duration=700.0))
            self.assertIn("600", str(cm.exception))

    def test_non_vertical_dimensions_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.validate_social_payload(
                    "instagram", video, "عنوان", "",
                    ig_user_id="123456789",
                    probe_info=_probe(width=1280, height=720))
            self.assertIn("9:16", str(cm.exception))

    def test_video_without_audio_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.validate_social_payload(
                    "tiktok", video, "عنوان", "",
                    probe_info=_probe(has_audio=False))
            self.assertIn("بلا مسار صوتي", str(cm.exception))

    def test_thumbnail_wrong_dimensions_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            thumb = _thumb(td)
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.validate_social_payload(
                    "tiktok", video, "عنوان", "", thumbnail=thumb,
                    thumbnail_probe=lambda p: (1080, 1920))
            self.assertIn("720×1280", str(cm.exception))

    def test_thumbnail_correct_dimensions_pass(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            thumb = _thumb(td)
            info = sp.validate_social_payload(
                "tiktok", video, "عنوان", "", thumbnail=thumb,
                thumbnail_probe=lambda p: (720, 1280))
            self.assertEqual(info["thumbnail"], (720, 1280))

    def test_thumbnail_missing_file_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.validate_social_payload(
                    "tiktok", video, "عنوان", "",
                    thumbnail=os.path.join(td, "nope.jpg"))
            self.assertIn("غير موجود", str(cm.exception))

    def test_thumbnail_bad_extension_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            thumb = _thumb(td, name="thumb.gif")
            with self.assertRaises(sp.SocialPublishError):
                sp.validate_social_payload(
                    "tiktok", video, "عنوان", "", thumbnail=thumb)


class TestDryRun(unittest.TestCase):
    def test_dry_run_tiktok_summary(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            res = sp.dry_run_summary("tiktok", video, "عنوان القصة",
                                     "كابشن قصير")
            self.assertTrue(res["ok"])
            self.assertEqual(res["mode"], "dry-run")
            self.assertEqual(res["network_calls"], 0)
            self.assertIn("تجريبي", res["summary"])
            self.assertIn("بلا أي طلب شبكة", res["summary"])
            self.assertEqual(res["payload"]["method"], "POST")
            self.assertIn("عنوان القصة",
                          res["payload"]["body"]["post_info"]["title"])

    def test_dry_run_instagram_summary(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            res = sp.dry_run_summary("instagram", video, "عنوان",
                                     "كابشن", ig_user_id="123456789")
            self.assertTrue(res["ok"])
            self.assertEqual(len(res["payload"]["steps"]), 4)
            self.assertIn("123456789", res["payload"]["steps"][0]["url"])

    def test_dry_run_instagram_without_user_id_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.dry_run_summary("instagram", video, "عنوان", "")
            self.assertIn("معرّف حساب Instagram مفقود",
                          str(cm.exception))

    def test_dry_run_makes_no_network_calls(self):
        # أي طلب شبكة أثناء dry-run يفشل الاختبار فورًا.
        import urllib.request
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            http_mock = mock.Mock(
                side_effect=AssertionError("شبكة في dry-run!"))
            with mock.patch.object(sp, "_http_json", http_mock), \
                    mock.patch.object(sp, "_http_put_bytes",
                                      mock.Mock(side_effect=AssertionError(
                                          "شبكة في dry-run!"))), \
                    mock.patch.object(sp, "_http_post_bytes_rupload",
                                      mock.Mock(side_effect=AssertionError(
                                          "شبكة في dry-run!"))), \
                    mock.patch.object(urllib.request, "urlopen",
                                      mock.Mock(side_effect=AssertionError(
                                          "شبكة في dry-run!"))):
                sp.dry_run_summary("tiktok", video, "عنوان", "كابشن")
                sp.dry_run_summary("instagram", video, "عنوان",
                                   "كابشن", ig_user_id="123456789")
                sp.build_social_payload("tiktok", video, "عنوان",
                                        "كابشن")
                sp.build_social_payload("instagram", video, "عنوان",
                                        "كابشن", "123456789")
            http_mock.assert_not_called()

    def test_dry_run_with_probe_info_reports_duration(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            res = sp.dry_run_summary(
                "tiktok", video, "عنوان", "",
                probe_info=_probe(duration=45.0))
            self.assertTrue(any("45.0" in c for c in res["checks"]))
            self.assertEqual(res["video"]["duration"], 45.0)


class TestRequireSocialConfig(unittest.TestCase):
    def test_tiktok_no_token_is_unlinked_arabic(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.require_social_config("tiktok", studio_dir=td)
            msg = str(cm.exception)
            self.assertIn("غير مربوط", msg)
            self.assertIn("tiktok-auth", msg)

    def test_instagram_no_token_is_unlinked_arabic(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.require_social_config(
                    "instagram", cfg={"publish": {
                        "instagram_user_id": "123456789"}},
                    studio_dir=td)
            self.assertIn("غير مربوط", str(cm.exception))

    def test_instagram_token_without_user_id_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            sp.save_token("instagram", "y" * 20, studio_dir=td)
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.require_social_config("instagram", cfg={},
                                         studio_dir=td)
            self.assertIn("معرّف حساب Instagram مفقود",
                          str(cm.exception))

    def test_instagram_token_and_user_id_pass(self):
        with tempfile.TemporaryDirectory() as td:
            sp.save_token("instagram", "y" * 20, studio_dir=td)
            res = sp.require_social_config(
                "instagram",
                cfg={"publish": {"instagram_user_id": "123456789"}},
                studio_dir=td)
            self.assertEqual(res["token"], "y" * 20)
            self.assertEqual(res["ig_user_id"], "123456789")

    def test_tiktok_token_passes(self):
        with tempfile.TemporaryDirectory() as td:
            sp.save_token("tiktok", "x" * 20, studio_dir=td)
            res = sp.require_social_config("tiktok", studio_dir=td)
            self.assertEqual(res["token"], "x" * 20)
            self.assertIsNone(res["ig_user_id"])

    def test_token_value_never_in_error(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(sp.SocialPublishError) as cm:
                sp.require_social_config("tiktok", studio_dir=td)
            self.assertNotIn("x" * 20, str(cm.exception))


class TestNormalizeResult(unittest.TestCase):
    def test_tiktok_result_unified(self):
        res = sp.normalize_result(
            "tiktok", {"publish_id": "pid-1",
                       "status": "PUBLISH_COMPLETE",
                       "public_url": "https://tiktok.example/v/1"})
        self.assertEqual(res["platform"], "tiktok")
        self.assertTrue(res["ok"])
        self.assertEqual(res["id"], "pid-1")
        self.assertEqual(res["status"], "PUBLISH_COMPLETE")
        self.assertEqual(res["url"], "https://tiktok.example/v/1")
        line = sp.format_result(res)
        self.assertIn("تيك توك", line)
        self.assertIn("pid-1", line)
        self.assertIn("https://tiktok.example/v/1", line)

    def test_instagram_result_unified(self):
        res = sp.normalize_result(
            "instagram", {"media_id": "18000000000000000",
                          "creation_id": "17841400000000000"})
        self.assertEqual(res["platform"], "instagram")
        self.assertEqual(res["id"], "18000000000000000")
        self.assertEqual(res["status"], "published")
        self.assertIsNone(res["url"])
        line = sp.format_result(res)
        self.assertIn("إنستغرام", line)
        self.assertIn("18000000000000000", line)

    def test_result_without_id_rejected(self):
        with self.assertRaises(sp.SocialPublishError):
            sp.normalize_result("tiktok", {"status": "FAILED"})
        with self.assertRaises(sp.SocialPublishError):
            sp.normalize_result("facebook", {"post_id": "1"})


class TestUploadValidatesBeforeNetwork(unittest.TestCase):
    def test_upload_tiktok_empty_title_makes_no_http_call(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            http_mock = mock.Mock()
            real_http = sp._http_json
            sp._http_json = http_mock
            try:
                with self.assertRaises(sp.SocialPublishError) as cm:
                    sp.upload_tiktok(video, "", "", "test-token-abcdef")
            finally:
                sp._http_json = real_http
            self.assertIn("فارغ", str(cm.exception))
            http_mock.assert_not_called()

    def test_upload_instagram_excess_hashtags_makes_no_http_call(self):
        with tempfile.TemporaryDirectory() as td:
            video = _mp4(td)
            http_mock = mock.Mock()
            real_http = sp._http_json
            sp._http_json = http_mock
            try:
                with self.assertRaises(sp.SocialPublishError) as cm:
                    sp.upload_instagram(video, "عنوان", _tags(31),
                                        "123456789",
                                        "test-token-abcdef")
            finally:
                sp._http_json = real_http
            self.assertIn("وسوم", str(cm.exception))
            http_mock.assert_not_called()


class TestSocialErrors(unittest.TestCase):
    def test_tiktok_token_missing_category(self):
        explained = errors_lib.explain_error(
            "توكن TikTok غير مربوط — لا يوجد ملف توكن صالح", "tiktok")
        self.assertEqual(explained["category"], "tiktok_token")
        text = errors_lib.explain_error_text(
            "توكن TikTok غير مربوط — لا يوجد ملف توكن صالح", "tiktok")
        self.assertIn("tiktok-auth", text)
        self.assertIn("ماذا تفعل", text)

    def test_instagram_user_id_missing_category(self):
        explained = errors_lib.explain_error(
            "معرّف حساب Instagram مفقود — اضبط "
            "publish.instagram_user_id في config.yaml", "instagram")
        self.assertEqual(explained["category"],
                         "instagram_user_id_missing")

    def test_tiktok_publish_failed_category(self):
        explained = errors_lib.explain_error(
            "فشل نشر TikTok (publish_id=pid-1): video_too_long",
            "tiktok")
        self.assertEqual(explained["category"], "tiktok_publish_failed")

    def test_instagram_publish_failed_category(self):
        explained = errors_lib.explain_error(
            "معالجة حاوية Instagram فشلت (status_code=ERROR)",
            "instagram")
        self.assertEqual(explained["category"],
                         "instagram_publish_failed")


class TestDoctorSocialIncomplete(unittest.TestCase):
    """doctor --accounts: مربوط/غير مربوط/ناقص إعداد — قراءة
    إعدادات فقط، بلا شبكة."""

    def test_instagram_token_without_user_id_is_incomplete(self):
        with tempfile.TemporaryDirectory() as td:
            sp.save_token("instagram", "y" * 20, studio_dir=td)
            c = accounts.check_instagram_token(studio_dir=td, cfg={})
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "warn")
        self.assertIn("ناقص إعداد", c["detail"])

    def test_instagram_token_with_user_id_is_linked(self):
        with tempfile.TemporaryDirectory() as td:
            sp.save_token("instagram", "y" * 20, studio_dir=td)
            cfg = {"publish": {"instagram_user_id": "123456789"}}
            c = accounts.check_instagram_token(studio_dir=td, cfg=cfg)
        self.assertTrue(c["ok"])
        self.assertIn("مربوط", c["detail"])

    def test_instagram_no_token_still_unlinked(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = {"publish": {"instagram_user_id": "123456789"}}
            c = accounts.check_instagram_token(studio_dir=td, cfg=cfg)
        self.assertFalse(c["ok"])
        self.assertEqual(c["level"], "warn")
        self.assertIn("غير مربوط", c["detail"])

    def test_instagram_check_without_cfg_keeps_old_behavior(self):
        # بلا cfg: توكن محفوظ = مربوط (توافق مع الاختبارات القديمة).
        with tempfile.TemporaryDirectory() as td:
            sp.save_token("instagram", "y" * 20, studio_dir=td)
            c = accounts.check_instagram_token(studio_dir=td)
        self.assertTrue(c["ok"])

    def test_run_account_checks_reports_five_with_ig_linked(self):
        fresh = (datetime.datetime.now(datetime.timezone.utc)
                 - datetime.timedelta(hours=1)).isoformat()
        with tempfile.TemporaryDirectory() as td:
            sp.save_token("tiktok", "x" * 20, studio_dir=td)
            sp.save_token("instagram", "y" * 20, studio_dir=td)
            cfg = {"publish": {
                       "page_id": "1048148471706586",
                       "youtube_token": _yt_token_file(td, 1),
                       "instagram_user_id": "123456789"},
                   "veo": {"balance_units": 680,
                           "renews": "2026-12-13",
                           "updated_at": fresh}}
            entry = {"object_id": "122",
                     "published_time": "2026-11-21T08:02:01Z",
                     "metadata": {"caption_excerpt": "قصة تجريبية",
                                  "metadata_text": "Video · 48s"},
                     "metrics": [{"field": "views", "value": 694}],
                     "activity": []}
            runner = lambda cmd, **kw: _fb_proc([entry])
            with mock.patch(
                    "lib.accounts.publish_lib.find_facebook_bin",
                    return_value="facebook-cli"):
                checks = accounts.run_account_checks(
                    cfg, runner=runner, today=TODAY, studio_dir=td)
        self.assertEqual(len(checks), 5)
        by_name = {c["name"]: c for c in checks}
        self.assertTrue(by_name["توكن TikTok"]["ok"])
        self.assertTrue(by_name["توكن Instagram"]["ok"])
        self.assertIn("مربوط", by_name["توكن Instagram"]["detail"])
        self.assertTrue(all(c["ok"] for c in checks))


if __name__ == "__main__":
    unittest.main()
