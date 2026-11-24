#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات التحديث والنسخ الاحتياطي (lib.update_backup).

تعمل بـ `python3 -m unittest discover -s tests -v`.
كل الشبكة مزيفة (شجرة وملفات في الذاكرة) وكل الكتابة في
مجلدات مؤقتة — لا يُمس المستودع الحقيقي ولا config.yaml
الحقيقي أبدًا.
"""
import hashlib
import json
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import update_backup


def _blob_sha(data):
    header = ("blob %d\0" % len(data)).encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _tree(entries):
    return {path: _blob_sha(data) for path, data in entries.items()}


class TestProtected(unittest.TestCase):
    def test_config_and_secrets_protected(self):
        for path in ("config.yaml", "youtube-token.json",
                     "client_secrets.json", ".env", "key.pem",
                     "token.key", "data.sqlite", "x.db"):
            self.assertTrue(update_backup.is_protected(path),
                            path)

    def test_protected_dirs(self):
        for path in ("runs/a.json", "backups/b.zip",
                     "queue/1-x.txt", "client-orders/orders.jsonl",
                     ".venv-youtube/bin/python",
                     "__pycache__/m.pyc"):
            self.assertTrue(update_backup.is_protected(path), path)

    def test_normal_files_not_protected(self):
        for path in ("studio.py", "lib/ideas.py", "README.md",
                     "tests/test_ideas.py"):
            self.assertFalse(update_backup.is_protected(path), path)


class TestPlanUpdate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.local = os.path.join(self.tmp, "studio")
        os.makedirs(os.path.join(self.local, "lib"))

    def _write(self, rel, data):
        path = os.path.join(self.local, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    def test_no_changes_when_identical(self):
        self._write("studio.py", b"print(1)\n")
        tree = _tree({"studio.py": b"print(1)\n"})
        self.assertEqual(update_backup.plan_update(self.local, tree),
                         [])

    def test_changed_and_new_files(self):
        self._write("studio.py", b"old\n")
        self._write("config.yaml", b"page_id: 1\n")
        tree = _tree({
            "studio.py": b"new\n",
            "lib/ideas.py": b"# new\n",
            "config.yaml": b"page_id: 2\n",  # محمي — لا يُمس
        })
        changes = update_backup.plan_update(self.local, tree)
        self.assertEqual(
            [(c["path"], c["action"]) for c in changes],
            [("lib/ideas.py", "add"), ("studio.py", "update")])

    def test_empty_tree_allowed_but_no_changes(self):
        self.assertEqual(update_backup.plan_update(self.local, {}),
                         [])


class TestApplyUpdate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.local = os.path.join(self.tmp, "studio")
        os.makedirs(self.local)

    def test_apply_writes_files_and_backs_up_first(self):
        with open(os.path.join(self.local, "studio.py"), "wb") as f:
            f.write(b"old\n")
        remote = {"studio.py": b"new\n", "lib/x.py": b"# x\n"}
        tree = _tree(remote)
        changes = update_backup.plan_update(self.local, tree)
        backed_up = []

        def backup_fn(paths):
            backed_up.extend(paths)

        def fetch_fn(path):
            return remote[path]

        written = update_backup.apply_update(
            self.local, changes, fetch_fn, backup_fn)
        self.assertEqual(backed_up, ["studio.py"])
        self.assertEqual(sorted(written), ["lib/x.py", "studio.py"])
        with open(os.path.join(self.local, "studio.py"), "rb") as f:
            self.assertEqual(f.read(), b"new\n")
        with open(os.path.join(self.local, "lib", "x.py"),
                  "rb") as f:
            self.assertEqual(f.read(), b"# x\n")


class TestFetchTree(unittest.TestCase):
    def test_tree_parsed_from_fake_api(self):
        payload = json.dumps({
            "tree": [
                {"path": "studio.py", "type": "blob",
                 "sha": "abc"},
                {"path": "lib", "type": "tree", "sha": "def"},
            ]}).encode("utf-8")

        def fake_get(url):
            self.assertIn("api.github.com", url)
            return payload

        tree = update_backup.fetch_tree("o/r", "main",
                                        http_get=fake_get)
        self.assertEqual(tree, {"studio.py": "abc"})

    def test_bad_json_raises(self):
        with self.assertRaises(update_backup.UpdateError):
            update_backup.fetch_tree("o/r", "main",
                                     http_get=lambda u: b"not json")


class TestBackup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.studio = os.path.join(self.tmp, "studio")
        os.makedirs(os.path.join(self.studio, "client-orders"))
        os.makedirs(os.path.join(self.studio, "runs", "r1"))
        with open(os.path.join(self.studio, "config.yaml"),
                  "w", encoding="utf-8") as f:
            f.write("publish:\n  page_id: '1'\n")
        self.queue = os.path.join(self.tmp, "queue.md")
        with open(self.queue, "w", encoding="utf-8") as f:
            f.write("# طابور\n")
        with open(os.path.join(self.studio, "client-orders",
                               "orders.jsonl"), "w",
                  encoding="utf-8") as f:
            f.write('{"order": 1}\n')
        with open(os.path.join(self.studio, "runs", "r1",
                               "run-log.json"), "w",
                  encoding="utf-8") as f:
            f.write("{}\n")
        with open(os.path.join(self.studio, "runs",
                               "analyze-1.json"), "w",
                  encoding="utf-8") as f:
            f.write("{}\n")
        self.cfg = {"paths": {"queue_file": self.queue}}

    def test_backup_zip_contains_everything(self):
        zip_path, included, missing = update_backup.make_backup(
            self.studio, self.cfg)
        self.assertTrue(os.path.isfile(zip_path))
        self.assertTrue(zip_path.endswith(".zip"))
        self.assertIn("config.yaml", included)
        self.assertIn("story-queue.md", included)
        self.assertIn("client-orders/orders.jsonl", included)
        self.assertIn("runs/r1/run-log.json", included)
        self.assertIn("runs/analyze-1.json", included)
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
        self.assertIn("manifest.txt", names)
        self.assertIn("config.yaml", names)
        # orders.jsonl.bad غير موجود — يُذكر كمفقود
        self.assertIn("client-orders/orders.jsonl.bad", missing)


class TestRetry(unittest.TestCase):
    """إعادة المحاولة مع تراجع تدريجي على 403/429 (اختراق
    2026-11-22: حدّ GitHub الثانوي ردّ 403 مرتين ثم نجح)."""

    def _fake_response(self, payload):
        class Resp:
            def __init__(self, data):
                self._data = data

            def geturl(self):
                # A real HTTPResponse always carries the final URL; the
                # round-4 host allowlist in _http_get reads it.
                return ("https://api.github.com/repos/o/r/git/trees/"
                        "main?recursive=1")

            def read(self):
                return self._data

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return Resp(payload)

    def test_403_twice_then_success(self):
        import time as time_mod
        import urllib.error
        from unittest import mock

        payload = json.dumps({"tree": [{"type": "blob",
                                        "path": "a.py",
                                        "sha": "s1"}]}).encode("utf-8")
        calls = {"n": 0}

        def flaky(req, timeout=None):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise urllib.error.HTTPError(
                    req.full_url, 403, "rate limited", {}, None)
            return self._fake_response(payload)

        with mock.patch("urllib.request.urlopen", flaky), \
                mock.patch.object(time_mod, "sleep", lambda s: None):
            tree = update_backup.fetch_tree("o/r", "main")
        self.assertEqual(tree, {"a.py": "s1"})
        self.assertEqual(calls["n"], 3)

    def test_persistent_403_raises_after_three(self):
        import time as time_mod
        import urllib.error
        from unittest import mock

        calls = {"n": 0}

        def always403(req, timeout=None):
            calls["n"] += 1
            raise urllib.error.HTTPError(
                req.full_url, 403, "forbidden", {}, None)

        with mock.patch("urllib.request.urlopen", always403), \
                mock.patch.object(time_mod, "sleep", lambda s: None):
            with self.assertRaises(update_backup.UpdateError):
                update_backup.fetch_tree("o/r", "main")
        self.assertEqual(calls["n"], 3)

    def test_404_no_retry(self):
        import urllib.error
        from unittest import mock

        calls = {"n": 0}

        def err404(req, timeout=None):
            calls["n"] += 1
            raise urllib.error.HTTPError(
                req.full_url, 404, "not found", {}, None)

        with mock.patch("urllib.request.urlopen", err404):
            with self.assertRaises(update_backup.UpdateError):
                update_backup.fetch_tree("o/r", "main")
        self.assertEqual(calls["n"], 1)


class TestBackupSymlink(TestBackup):
    def test_symlinked_run_file_not_backed_up(self):
        # اختبار انحدار (اختراق 2026-11-22): رابط رمزي في runs/
        # يشير لملف خارجي كان محتواه يتسرب للنسخة الاحتياطية.
        secret = os.path.join(self.tmp, "secret.txt")
        with open(secret, "w", encoding="utf-8") as f:
            f.write("SECRET-CONTENT\n")
        link = os.path.join(self.studio, "runs", "evil.json")
        os.symlink(secret, link)
        zip_path, included, _missing = update_backup.make_backup(
            self.studio, self.cfg)
        self.assertNotIn("runs/evil.json", included)
        with zipfile.ZipFile(zip_path) as zf:
            self.assertNotIn("runs/evil.json", zf.namelist())
            self.assertNotIn(b"SECRET-CONTENT", zf.read("manifest.txt"))


if __name__ == "__main__":
    unittest.main()
