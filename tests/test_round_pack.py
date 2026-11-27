#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات صيغة حزمة الجولة (lib.round_pack) — جولة v0.1.63، بند 11.

تعمل بـ `python3 -m unittest tests.test_round_pack -v` من مجلد studio.
بلا ملفات خارجية وبلا شبكة — كل الملفات في مجلدات مؤقتة.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import round_pack


def _write(base, rel_path, content):
    full = os.path.join(base, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    mode = "wb" if isinstance(content, bytes) else "w"
    with open(full, mode, encoding=None if isinstance(content, bytes) else "utf-8") as fh:
        fh.write(content)
    return full


class TestExportImportRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, "src")
        os.makedirs(self.src)
        self.out = os.path.join(self.tmp.name, "pack.md")
        self.dest = os.path.join(self.tmp.name, "dest")

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip_returns_same_content(self):
        _write(self.src, "a.txt", "محتوى أول\nسطر ثانٍ\n")
        _write(self.src, "sub/b.txt", "نص بلا سطر أخير")
        _write(self.src, "c.md", "نص فيه ``` سياج\nوثلاث شرطات --- داخل النص\n")
        summary = round_pack.export_pack(
            self.src, ["a.txt", "sub/b.txt", "c.md"],
            name="test-pack", version="0.1.63",
            changes=["تغيير أول"], tests=["اختبار أول"],
            out_path=self.out,
        )
        self.assertEqual(summary["files"], 3)
        self.assertEqual(summary["secrets_scrubbed"], 0)
        result = round_pack.import_pack(self.out, self.dest)
        self.assertEqual(sorted(result["files"]),
                         ["a.txt", "c.md", "sub/b.txt"])
        for rel in ("a.txt", "sub/b.txt", "c.md"):
            with open(os.path.join(self.src, rel), encoding="utf-8") as fh:
                expected = fh.read()
            with open(os.path.join(self.dest, rel), encoding="utf-8") as fh:
                got = fh.read()
            self.assertEqual(got, expected, rel)

    def test_review_ok_for_valid_pack(self):
        _write(self.src, "a.txt", "سليم\n")
        round_pack.export_pack(
            self.src, ["a.txt"], name="ok-pack", version="0.1.63",
            changes=[], tests=[], out_path=self.out,
        )
        review = round_pack.review_pack(self.out)
        self.assertTrue(review["ok"], review["errors"])
        self.assertEqual(review["secrets_remaining"], 0)
        self.assertIn("حزمة: ok-pack", review["summary_lines"][0])


class TestSecretScrubbing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, "src")
        os.makedirs(self.src)
        self.out = os.path.join(self.tmp.name, "pack.md")

    def tearDown(self):
        self.tmp.cleanup()

    def test_secret_scrubbed_and_counted(self):
        _write(self.src, "a.txt", "المفتاح sk-abcdefgh12345678 هنا\n")
        summary = round_pack.export_pack(
            self.src, ["a.txt"], name="scrub", version="0.1.63",
            changes=[], tests=[], out_path=self.out,
        )
        self.assertEqual(summary["secrets_scrubbed"], 1)
        with open(self.out, encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("sk-abcdefgh12345678", text)
        self.assertIn("[REDACTED]", text)
        self.assertEqual(round_pack.count_secrets(text), 0)

    def test_assignment_secret_scrubbed(self):
        cleaned, n = round_pack.scrub_text("api_key=supersecretvalue")
        self.assertEqual(n, 1)
        self.assertNotIn("supersecretvalue", cleaned)

    def test_review_rejects_pack_still_holding_secret(self):
        # حزمة مكتوبة يدًا تحمل سرًا (لم تمر عبر التصدير).
        with open(self.out, "w", encoding="utf-8") as fh:
            fh.write(
                "---\npack: bad\nversion: '1'\nfiles: 1\n"
                "total_bytes: 30\nsecrets_scrubbed: 0\n"
                "routines_stopped: true\n---\n\n"
                "## الملفات\n\n### `a.txt`\n\n```\n"
                "token sk-abcdefgh12345678\n```\n"
            )
        review = round_pack.review_pack(self.out)
        self.assertFalse(review["ok"])
        self.assertGreater(review["secrets_remaining"], 0)
        with self.assertRaises(round_pack.PackError):
            round_pack.import_pack(self.out, os.path.join(self.tmp.name, "d"))


class TestLimitsAndForbidden(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, "src")
        os.makedirs(self.src)
        self.out = os.path.join(self.tmp.name, "pack.md")

    def tearDown(self):
        self.tmp.cleanup()

    def _export(self, rel_paths):
        return round_pack.export_pack(
            self.src, rel_paths, name="p", version="0.1.63",
            changes=[], tests=[], out_path=self.out,
        )

    def test_too_many_files_rejected(self):
        paths = []
        for i in range(round_pack.MAX_FILES + 1):
            paths.append("f%02d.txt" % i)
            _write(self.src, paths[-1], "x")
        with self.assertRaises(round_pack.PackError):
            self._export(paths)

    def test_file_over_size_limit_rejected(self):
        _write(self.src, "big.txt", "x" * (round_pack.MAX_FILE_BYTES + 1))
        with self.assertRaises(round_pack.PackError):
            self._export(["big.txt"])

    def test_total_over_limit_rejected(self):
        paths = []
        chunk = round_pack.MAX_FILE_BYTES
        for i in range(5):  # 5 × 128KB = 640KB > 512KB
            paths.append("t%d.txt" % i)
            _write(self.src, paths[-1], "x" * chunk)
        with self.assertRaises(round_pack.PackError):
            self._export(paths)

    def test_hidden_file_rejected(self):
        _write(self.src, ".hidden.txt", "سر")
        with self.assertRaises(round_pack.PackError):
            self._export([".hidden.txt"])

    def test_binary_file_rejected(self):
        _write(self.src, "bin.dat", b"\x00\x01\x02\x03")
        with self.assertRaises(round_pack.PackError):
            self._export(["bin.dat"])

    def test_key_named_file_rejected(self):
        _write(self.src, "api_key.txt", "x")
        with self.assertRaises(round_pack.PackError):
            self._export(["api_key.txt"])

    def test_node_modules_rejected(self):
        _write(self.src, "node_modules/x.js", "x")
        with self.assertRaises(round_pack.PackError):
            self._export(["node_modules/x.js"])

    def test_forbidden_memory_path_rejected(self):
        _write(self.src, "memory/note.txt", "x")
        with self.assertRaises(round_pack.PackError):
            self._export(["memory/note.txt"])

    def test_depth_over_limit_rejected(self):
        deep = "/".join(["d%d" % i for i in range(6)]) + "/f.txt"
        _write(self.src, deep, "x")
        with self.assertRaises(round_pack.PackError):
            self._export([deep])

    def test_missing_file_rejected(self):
        with self.assertRaises(round_pack.PackError):
            self._export(["nope.txt"])


class TestPreviousBackup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, "src")
        self.dest = os.path.join(self.tmp.name, "dest")
        os.makedirs(self.src)
        os.makedirs(self.dest)
        self.out = os.path.join(self.tmp.name, "pack.md")

    def tearDown(self):
        self.tmp.cleanup()

    def test_previous_backup_on_replace(self):
        _write(self.src, "a.txt", "جديد\n")
        _write(self.dest, "a.txt", "قديم\n")
        round_pack.export_pack(
            self.src, ["a.txt"], name="p", version="0.1.63",
            changes=[], tests=[], out_path=self.out,
        )
        result = round_pack.import_pack(self.out, self.dest, allow_overwrite=True)
        self.assertEqual(result["backed_up"], ["a.txt.previous"])
        with open(os.path.join(self.dest, "a.txt.previous"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "قديم\n")
        with open(os.path.join(self.dest, "a.txt"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "جديد\n")

    def test_replace_without_permission_refused(self):
        _write(self.src, "a.txt", "جديد\n")
        _write(self.dest, "a.txt", "قديم\n")
        round_pack.export_pack(
            self.src, ["a.txt"], name="p", version="0.1.63",
            changes=[], tests=[], out_path=self.out,
        )
        with self.assertRaises(round_pack.PackError):
            round_pack.import_pack(self.out, self.dest)
        with open(os.path.join(self.dest, "a.txt"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "قديم\n")


class TestImportLimits(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = os.path.join(self.tmp.name, "pack.md")

    def tearDown(self):
        self.tmp.cleanup()

    def _write_pack(self, files):
        import yaml
        meta = {
            "pack": "big", "version": "1", "files": len(files),
            "total_bytes": sum(len(c) for _, c in files),
            "secrets_scrubbed": 0, "routines_stopped": True,
        }
        lines = ["---", yaml.safe_dump(meta, allow_unicode=True).rstrip(),
                 "---", "", "## الملفات", ""]
        for path, content in files:
            lines.append("### `%s`" % path)
            lines.append("")
            lines.append("```")
            lines.append(content)
            lines.append("```")
            lines.append("")
        with open(self.out, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

    def test_import_file_over_1mb_rejected(self):
        self._write_pack([("big.txt", "x" * (round_pack.IMPORT_MAX_FILE_BYTES + 1))])
        review = round_pack.review_pack(self.out)
        self.assertFalse(review["ok"])

    def test_import_too_many_files_rejected(self):
        files = [("f%03d.txt" % i, "x") for i in range(301)]
        self._write_pack(files)
        review = round_pack.review_pack(self.out)
        self.assertFalse(review["ok"])


if __name__ == "__main__":
    unittest.main()
