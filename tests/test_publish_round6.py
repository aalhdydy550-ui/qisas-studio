#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات نشر مجدول بأمر واحد — الجولة 6 (v0.1.29).

`studio.py publish --schedule "YYYY-MM-DD HH:MM"` (بتوقيت
Africa/Cairo): فيسبوك عبر --scheduled-publish-time (Unix)،
ويوتيوب عبر publishAt مع privacyStatus=private (شرط API).

بلا نشر حقيقي وبلا شبكة: facebook-cli ورفع يوتيوب يُستبدلان
بمحاكاة (mock)، والجدولة الحقيقية لم تُختبر هنا عمدًا.
"""
import io
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import publish
from lib import youtube_upload

# 2026-11-23 19:00 بتوقيت القاهرة (UTC+2) = 17:00 UTC.
CAIRO_TEXT = "2026-11-23 19:00"
CAIRO_EPOCH = 1795453200
CAIRO_PUBLISH_AT = "2026-11-23T17:00:00Z"


class TestParseSchedule(unittest.TestCase):
    def test_cairo_text_to_unix(self):
        # "الآن" المرجعي قبل الموعد بكثير، حتى لا يعتمد الاختبار
        # على ساعة تشغيله.
        epoch = publish.parse_schedule(CAIRO_TEXT, now=1790000000)
        self.assertEqual(epoch, CAIRO_EPOCH)

    def test_unix_passthrough_kept(self):
        # --schedule القديم (Unix int) ما زال يعمل.
        self.assertEqual(publish.parse_schedule(CAIRO_EPOCH,
                                                now=1790000000),
                         CAIRO_EPOCH)
        self.assertEqual(publish.parse_schedule(str(CAIRO_EPOCH),
                                                now=1790000000),
                         CAIRO_EPOCH)

    def test_format_schedule_roundtrip(self):
        self.assertEqual(publish.format_schedule(CAIRO_EPOCH),
                         "2026-11-23 19:00 Africa/Cairo")
        self.assertEqual(publish.schedule_publish_at(CAIRO_EPOCH),
                         CAIRO_PUBLISH_AT)

    def test_past_date_rejected(self):
        with self.assertRaises(publish.PublishError):
            publish.parse_schedule("2026-11-23 19:00", now=CAIRO_EPOCH)
        with self.assertRaises(publish.PublishError):
            publish.parse_schedule("2020-01-01 09:00", now=1790000000)
        with self.assertRaises(publish.PublishError):
            publish.parse_schedule(CAIRO_EPOCH - 60, now=CAIRO_EPOCH)

    def test_bad_format_rejected(self):
        bad = ["23/11/2026 19:00", "2026-11-23", "2026-11-23 19:00:00",
               "2026-11-23 25:00", "2026-13-01 19:00", "غدًا 19:00",
               "2026-11-23 19:00 ", " 2026-11-23 19:00"]
        # الملاحظة: النصان الأخيران بمسافات زائدة يقبلهما التقليم
        # عمدًا — يُستثنيان من الرفض أدناه.
        for text in bad[:6]:
            with self.assertRaises(publish.PublishError, msg=text):
                publish.parse_schedule(text, now=1790000000)

    def test_whitespace_trimmed(self):
        self.assertEqual(publish.parse_schedule(" 2026-11-23 19:00 ",
                                                now=1790000000),
                         CAIRO_EPOCH)


class TestScheduledFacebookCommand(unittest.TestCase):
    def test_scheduled_argv_has_unix_time(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            Path(video).write_bytes(b"fake")
            argv = publish.facebook_argv(
                "1048148471706586", video, "كابشن",
                schedule=CAIRO_EPOCH, facebook_bin="facebook-cli")
            self.assertIn("--scheduled-publish-time", argv)
            self.assertIn(str(CAIRO_EPOCH), argv)
            self.assertIn("--privacy", argv)
            self.assertIn("PUBLIC", argv)

    def test_unscheduled_argv_has_no_publish_time(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            Path(video).write_bytes(b"fake")
            argv = publish.facebook_argv(
                "1048148471706586", video, "كابشن",
                facebook_bin="facebook-cli")
            self.assertNotIn("--scheduled-publish-time", argv)


class TestScheduledYoutubePayload(unittest.TestCase):
    def test_payload_has_publish_at_and_private(self):
        # حتى مع privacy=public الممرَّرة: الجدولة تفرض private
        # (شرط YouTube API — public + publishAt يُرفض 400).
        payload = publish.youtube_payload(
            "عنوان", "وصف", ["قصص"], privacy="public",
            schedule=CAIRO_EPOCH)
        status = payload["body"]["status"]
        self.assertEqual(status["publishAt"], CAIRO_PUBLISH_AT)
        self.assertEqual(status["privacyStatus"], "private")

    def test_payload_schedule_display_block(self):
        payload = publish.youtube_payload(
            "عنوان", "وصف", ["قصص"], privacy="public",
            schedule=CAIRO_EPOCH)
        sched = payload["schedule"]
        self.assertEqual(sched["cairo"], "2026-11-23 19:00 Africa/Cairo")
        self.assertEqual(sched["timezone"], "Africa/Cairo")
        self.assertEqual(sched["publishAt"], CAIRO_PUBLISH_AT)
        self.assertEqual(sched["unix"], CAIRO_EPOCH)

    def test_unscheduled_payload_keeps_public_no_publish_at(self):
        payload = publish.youtube_payload(
            "عنوان", "وصف", ["قصص"], privacy="public")
        status = payload["body"]["status"]
        self.assertEqual(status["privacyStatus"], "public")
        self.assertNotIn("publishAt", status)
        self.assertNotIn("schedule", payload)

    def test_uploader_body_forces_private_with_publish_at(self):
        body = youtube_upload.build_upload_body(
            "عنوان", "وصف", ["قصص"], privacy="public",
            publish_at=CAIRO_PUBLISH_AT)
        self.assertEqual(body["status"]["privacyStatus"], "private")
        self.assertEqual(body["status"]["publishAt"], CAIRO_PUBLISH_AT)

    def test_uploader_body_keeps_privacy_without_publish_at(self):
        body = youtube_upload.build_upload_body(
            "عنوان", "وصف", ["قصص"], privacy="unlisted")
        self.assertEqual(body["status"]["privacyStatus"], "unlisted")
        self.assertNotIn("publishAt", body["status"])

    def test_bundle_steps_mention_schedule(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            Path(video).write_bytes(b"fake")
            bundle = publish.write_youtube_bundle(
                os.path.join(td, "bundle"), video, "عنوان", "وصف",
                ["قصص"], privacy="public", schedule=CAIRO_EPOCH)
            steps = Path(bundle, "steps.txt").read_text(encoding="utf-8")
            self.assertIn("2026-11-23 19:00 Africa/Cairo", steps)
            self.assertIn(CAIRO_PUBLISH_AT, steps)
            self.assertIn("private (مجدول", steps)


class TestScheduledDryRun(unittest.TestCase):
    def _cfg(self, td):
        return {"publish": {"page_id": "1048148471706586",
                            "youtube_token": os.path.join(td, "t.json"),
                            "youtube_privacy": "public"},
                "paths": {"videos_dir": td}}

    def test_dry_run_prints_full_schedule_and_runs_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            video = os.path.join(td, "v.mp4")
            Path(video).write_bytes(b"fake")
            # الموعد المجدول يجب أن يكون في المستقبل دائمًا —
            # cmd_publish يرفض الموعد الماضي (return 1). الثابت
            # CAIRO_EPOCH (2026-11-23 19:00) كان يفشل هذا الاختبار
            # بعد 19:00 القاهرة في يومه نفسه — قنبلة موقوتة
            # اكتُشفت في تشغيل المجموعة الكاملة لجولة v0.1.43.
            future = int(time.time()) + 7200
            with mock.patch("lib.publish.find_facebook_bin",
                            return_value="facebook-cli"), \
                 mock.patch("lib.publish.subprocess.run") as run_mock, \
                 mock.patch("lib.publish.subprocess.Popen") as popen_mock:
                run_mock.side_effect = AssertionError(
                    "dry-run استدعى تنفيذًا حقيقيًا!")
                popen_mock.side_effect = AssertionError(
                    "dry-run استدعى تنفيذًا حقيقيًا!")
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    rc = studio.cmd_publish(
                        self._cfg(td), video, "عنوان التجربة",
                        "كابشن تجريبي",
                        platforms=("facebook", "youtube"),
                        schedule=future, dry_run=True,
                        skip_check=True, skip_caption_check=True)
            self.assertEqual(rc, 0)
            run_mock.assert_not_called()
            popen_mock.assert_not_called()
            out = buf.getvalue()
            self.assertIn("وضع تجريبي", out)
            self.assertIn("--scheduled-publish-time", out)
            self.assertIn(str(future), out)
            self.assertIn(publish.schedule_publish_at(future), out)
            self.assertIn(publish.format_schedule(future), out)
            self.assertIn('"privacyStatus": "private"', out)


if __name__ == "__main__":
    unittest.main()
