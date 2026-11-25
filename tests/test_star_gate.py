#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات بوابة النجمة — جولة v0.1.48.

بحقن دالة HTTP وهمية + QISAS_LICENSE_DIR مؤقت: بلا شبكة وبلا
لمس ملف الحالة الحقيقي (~/.qisas-studio) أبدًا. الإثبات الحي
بالـCLI (بلا شبكة) خارج هذا الملف — في تقرير العامل.
"""
import contextlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import license as license_lib
from lib import star_gate as star_gate_lib

REAL_STAR_STATE = os.path.expanduser("~/.qisas-studio/star.json")
REAL_LICENSE_STATE = os.path.expanduser("~/.qisas-studio/license.json")

REPO_ITEM = {"full_name": "aalhdydy550-ui/qisas-studio"}
OTHER_ITEM = {"full_name": "someone/else"}


def _http_error(url, code):
    return urllib.error.HTTPError(url, code, "err-%d" % code, None, None)


class FakeGitHub:
    """محاكي GitHub API: صفحات {رقم الصفحة: قائمة} أو خطأ يُرفع."""

    def __init__(self, pages=None, error=None):
        self.pages = pages or {}
        self.error = error
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        if self.error is not None:
            raise self.error(url)
        page = 1
        if "page=" in url:
            page = int(url.rsplit("page=", 1)[1])
        return list(self.pages.get(page, []))


def _interactive_stdin():
    stdin = mock.Mock()
    stdin.isatty.return_value = True
    return stdin


def _non_interactive_stdin():
    stdin = mock.Mock()
    stdin.isatty.return_value = False
    return stdin


class StarGateTestBase(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.env = mock.patch.dict(
            os.environ, {license_lib.LICENSE_DIR_ENV: self.td})
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop(star_gate_lib.SKIP_ENV, None)
        # لقطة للحالة الحقيقية (إن وُجدت): الاختبارات لا تلمسها
        # أبدًا، وtearDown يثبت أنها لم تتغيّر.
        self._real_snapshots = {}
        for path in (REAL_STAR_STATE, REAL_LICENSE_STATE):
            if os.path.exists(path):
                with open(path, "rb") as fh:
                    self._real_snapshots[path] = fh.read()

    def tearDown(self):
        for path, content in self._real_snapshots.items():
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), content,
                                 "ملف حالة حقيقي تغيّر: %s" % path)
        for path in (REAL_STAR_STATE, REAL_LICENSE_STATE):
            if path not in self._real_snapshots:
                self.assertFalse(os.path.exists(path),
                                 "ملف حالة حقيقي أُنشئ: %s" % path)

    def _check(self, fetcher, username="someuser", interactive=True):
        stdin = (_interactive_stdin() if interactive
                 else _non_interactive_stdin())
        out = io.StringIO()
        with mock.patch("sys.stdin", stdin), \
                contextlib.redirect_stdout(out):
            result = star_gate_lib.check_star_gate(
                fetcher=fetcher,
                input_fn=lambda _prompt: username)
        return result, out.getvalue()

    def _star_path(self):
        return os.path.join(self.td, "star.json")


class TestHasStarred(StarGateTestBase):
    def test_starred_on_first_page(self):
        fake = FakeGitHub({1: [OTHER_ITEM, REPO_ITEM]})
        self.assertTrue(star_gate_lib.has_starred("u", fetcher=fake))
        self.assertEqual(len(fake.calls), 1)

    def test_not_starred_empty_list(self):
        fake = FakeGitHub({1: []})
        self.assertFalse(star_gate_lib.has_starred("u", fetcher=fake))
        self.assertEqual(len(fake.calls), 1)

    def test_star_on_second_page_found_by_pagination(self):
        fake = FakeGitHub({1: [OTHER_ITEM] * 100,
                           2: [REPO_ITEM]})
        self.assertTrue(star_gate_lib.has_starred("u", fetcher=fake))
        self.assertEqual(len(fake.calls), 2)

    def test_404_user_is_not_starred(self):
        fake = FakeGitHub(error=lambda url: _http_error(url, 404))
        self.assertFalse(star_gate_lib.has_starred("ghost", fetcher=fake))

    def test_403_rate_limit_raises_unavailable(self):
        fake = FakeGitHub(error=lambda url: _http_error(url, 403))
        with self.assertRaises(star_gate_lib.StarCheckUnavailable):
            star_gate_lib.has_starred("u", fetcher=fake)

    def test_network_error_raises_unavailable(self):
        fake = FakeGitHub(
            error=lambda url: urllib.error.URLError("no network"))
        with self.assertRaises(star_gate_lib.StarCheckUnavailable):
            star_gate_lib.has_starred("u", fetcher=fake)


class TestCheckStarGate(StarGateTestBase):
    def test_starred_user_passes_and_caches_positive(self):
        fake = FakeGitHub({1: [REPO_ITEM]})
        result, out = self._check(fake)
        self.assertTrue(result)
        self.assertEqual(out, "")
        path = self._star_path()
        self.assertTrue(os.path.isfile(path))
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data, {"github_user": "someuser",
                                "starred": True,
                                "checked_at": data["checked_at"],
                                "repo": "aalhdydy550-ui/qisas-studio"})
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.td).st_mode), 0o700)

    def test_non_starred_user_denied_and_not_cached(self):
        fake = FakeGitHub({1: [OTHER_ITEM]})
        result, out = self._check(fake)
        self.assertFalse(result)
        self.assertIn("النجمة مطلوبة", out)
        self.assertIn(star_gate_lib.REPO_URL, out)
        self.assertIn("مجانيًا", out)
        self.assertFalse(os.path.exists(self._star_path()))

    def test_404_user_denied(self):
        fake = FakeGitHub(error=lambda url: _http_error(url, 404))
        result, out = self._check(fake, username="ghost-user-404")
        self.assertFalse(result)
        self.assertIn("النجمة مطلوبة", out)
        self.assertFalse(os.path.exists(self._star_path()))

    def test_network_error_fail_open_with_warning(self):
        fake = FakeGitHub(
            error=lambda url: urllib.error.URLError("no network"))
        result, out = self._check(fake)
        self.assertTrue(result)
        self.assertIn("تحذير", out)
        self.assertIn("GitHub", out)
        self.assertFalse(os.path.exists(self._star_path()))

    def test_403_rate_limit_fail_open_with_warning(self):
        fake = FakeGitHub(error=lambda url: _http_error(url, 403))
        result, out = self._check(fake)
        self.assertTrue(result)
        self.assertIn("تحذير", out)
        self.assertFalse(os.path.exists(self._star_path()))

    def test_positive_cache_skips_network_entirely(self):
        star_gate_lib._save_cache("cached-user")

        def _boom(_url):
            raise AssertionError("يجب ألا تُستدعى الشبكة مع cache")

        out = io.StringIO()
        with mock.patch("sys.stdin", _non_interactive_stdin()), \
                contextlib.redirect_stdout(out):
            result = star_gate_lib.check_star_gate(
                fetcher=_boom,
                input_fn=lambda _p: (_ for _ in ()).throw(
                    AssertionError("يجب ألا يُسأل مع cache")))
        self.assertTrue(result)
        self.assertEqual(out.getvalue(), "")

    def test_corrupt_cache_ignored_and_rechecked(self):
        with open(self._star_path(), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        fake = FakeGitHub({1: [REPO_ITEM]})
        result, _out = self._check(fake)
        self.assertTrue(result)
        self.assertEqual(len(fake.calls), 1)

    def test_owner_exempt_no_network_no_prompt(self):
        license_lib.set_owner()

        def _boom(_url):
            raise AssertionError("يجب ألا تُستدعى الشبكة للمالك")

        out = io.StringIO()
        with mock.patch("sys.stdin", _interactive_stdin()), \
                contextlib.redirect_stdout(out):
            result = star_gate_lib.check_star_gate(
                fetcher=_boom,
                input_fn=lambda _p: (_ for _ in ()).throw(
                    AssertionError("يجب ألا يُسأل المالك")))
        self.assertTrue(result)
        self.assertEqual(out.getvalue(), "")
        self.assertFalse(os.path.exists(self._star_path()))

    def test_skip_env_disables_check(self):
        os.environ[star_gate_lib.SKIP_ENV] = "1"

        def _boom(_url):
            raise AssertionError("يجب ألا تُستدعى الشبكة مع التعطيل")

        out = io.StringIO()
        with mock.patch("sys.stdin", _interactive_stdin()), \
                contextlib.redirect_stdout(out):
            result = star_gate_lib.check_star_gate(
                fetcher=_boom,
                input_fn=lambda _p: (_ for _ in ()).throw(
                    AssertionError("يجب ألا يُسأل مع التعطيل")))
        self.assertTrue(result)
        self.assertEqual(out.getvalue(), "")

    def test_non_interactive_fail_open_without_prompt(self):
        fake = FakeGitHub({1: [REPO_ITEM]})
        result, out = self._check(fake, interactive=False)
        self.assertTrue(result)
        self.assertIn("تحذير", out)
        self.assertIn("غير تفاعلي", out)
        self.assertEqual(len(fake.calls), 0)
        self.assertFalse(os.path.exists(self._star_path()))


if __name__ == "__main__":
    unittest.main()
