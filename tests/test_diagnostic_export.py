#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات حزمة التصدير التشخيصية (lib.diagnostic_export) — بند 29، جولة v0.1.63.

زوج موجب/سالب لكل سلوك: حدود الملفات والبايتات؛ ورفض
مجلد غير فارغ؛ و`--force` يحذف فقط ما في `manifest.json`؛
والحزمة بلا أسرار (تنقيح عبر `redact_deep` من
`lib.cli_output` مع رجوع احتياطي إلى `lib.id_mask`)؛
وقصّ النصوص عند 2,000 رسالة.

معزولة: `tempfile` فقط، بلا شبكة، بلا ملفات خارج الشجرة.
"""
import json
import os
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import diagnostic_export as de


def _job(job_id="job-1"):
    return {
        "job_id": job_id,
        "kind": "assemble",
        "status": "failed",
        "error": "render failed",
        "api_key": "sk-test-SECRET-VALUE-99999",
    }


class TestRedactForExport(unittest.TestCase):
    def test_secret_removed_from_strings_and_records(self):
        text = "key is sk-test-SECRET-VALUE-99999 end"
        self.assertNotIn("sk-test-SECRET-VALUE-99999",
                         de.redact_for_export(text))
        record = {"nested": {"token": "Bearer abcdef123456"}}
        blob = json.dumps(de.redact_for_export(record), ensure_ascii=False)
        self.assertNotIn("abcdef123456", blob)

    def test_non_string_values_pass_through(self):
        self.assertEqual(de.redact_for_export(42), 42)
        self.assertIsNone(de.redact_for_export(None))


class TestExportJob(unittest.TestCase):
    def test_writes_manifest_job_and_texts(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "pkg")
            manifest = de.export_job(
                _job(), out,
                sources=[{"name": "run.log",
                          "lines": ["line 1", "line 2"]}])
            self.assertEqual(manifest["job_id"], "job-1")
            self.assertEqual(manifest["timezone"], "Africa/Cairo")
            names = {entry["name"] for entry in manifest["files"]}
            self.assertEqual(names, {"job.json", "run.log"})
            self.assertEqual(manifest["total_files"], 3)  # + manifest
            for name in ("manifest.json", "job.json", "run.log"):
                path = os.path.join(out, name)
                self.assertTrue(os.path.isfile(path))
                self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
            with open(os.path.join(out, "job.json"),
                      encoding="utf-8") as handle:
                job = json.load(handle)
            blob = json.dumps(job, ensure_ascii=False)
            self.assertNotIn("sk-test-SECRET-VALUE-99999", blob)
            with open(os.path.join(out, "run.log"),
                      encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "line 1\nline 2\n")

    def test_text_clipped_at_2000_messages(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "pkg")
            lines = ["msg %d" % i for i in range(2500)]
            de.export_job(_job(), out,
                          sources=[{"name": "big.log", "lines": lines}])
            with open(os.path.join(out, "big.log"),
                      encoding="utf-8") as handle:
                kept = handle.read().splitlines()
            self.assertEqual(len(kept), 2001)  # 2000 + سطر قصّ
            self.assertIn("msg 1999", kept)
            self.assertNotIn("msg 2000", kept)
            self.assertTrue(kept[-1].startswith("[..."))

    def test_text_source_from_file_path(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "src.log")
            with open(src, "w", encoding="utf-8") as handle:
                handle.write("a\nb\n")
            out = os.path.join(td, "pkg")
            de.export_job(_job(), out,
                          sources=[{"name": "copied.log", "path": src}])
            with open(os.path.join(out, "copied.log"),
                      encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "a\nb\n")

    def test_missing_source_file_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(de.ExportError):
                de.export_job(_job(), os.path.join(td, "pkg"),
                              sources=[{"name": "x.log",
                                        "path": "/tmp/no-such-file.log"}])

    def test_invalid_job_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(de.ExportError):
                de.export_job({"kind": "run"}, os.path.join(td, "pkg"))

    def test_manifest_lists_sha256_and_sizes(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "pkg")
            manifest = de.export_job(_job(), out)
            entry = manifest["files"][0]
            self.assertEqual(entry["name"], "job.json")
            self.assertEqual(len(entry["sha256"]), 64)
            with open(os.path.join(out, "job.json"), "rb") as handle:
                self.assertEqual(entry["bytes"], len(handle.read()))

    def test_exported_at_carries_cairo_offset(self):
        with tempfile.TemporaryDirectory() as td:
            manifest = de.export_job(_job(), os.path.join(td, "pkg"))
            self.assertIn("+02:00", manifest["exported_at"])


class TestLimits(unittest.TestCase):
    def test_max_files_enforced_before_any_write(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "pkg")
            sources = [{"name": "f%d.log" % i, "lines": ["x"]}
                       for i in range(5)]
            with self.assertRaises(de.ExportError):
                de.export_job(_job(), out, sources=sources, max_files=3)
            self.assertFalse(os.path.exists(os.path.join(out, "job.json")))

    def test_max_bytes_enforced_before_any_write(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "pkg")
            big = "y" * 1000
            with self.assertRaises(de.ExportError):
                de.export_job(_job(), out,
                              sources=[{"name": "big.log",
                                        "lines": [big]}],
                              max_bytes=100)
            self.assertFalse(os.path.exists(os.path.join(out, "job.json")))

    def test_default_limits_allow_small_package(self):
        with tempfile.TemporaryDirectory() as td:
            manifest = de.export_job(_job(), os.path.join(td, "pkg"))
            self.assertEqual(manifest["limits"]["max_files"],
                             de.MAX_FILES_DEFAULT)
            self.assertEqual(manifest["limits"]["max_bytes"],
                             de.MAX_BYTES_DEFAULT)


class TestNonEmptyOutDir(unittest.TestCase):
    def test_non_empty_dir_rejected_without_force(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "pkg")
            os.makedirs(out)
            with open(os.path.join(out, "keep.txt"), "w") as handle:
                handle.write("keep me")
            with self.assertRaises(de.ExportError):
                de.export_job(_job(), out)
            self.assertTrue(os.path.isfile(os.path.join(out, "keep.txt")))

    def test_force_deletes_only_manifest_listed_files(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "pkg")
            de.export_job(_job("job-1"), out,
                          sources=[{"name": "old.log", "lines": ["old"]}])
            # ملف دخيل غير مسرود في الـmanifest.
            with open(os.path.join(out, "stranger.txt"), "w") as handle:
                handle.write("not mine")
            with self.assertRaises(de.ExportError):
                # --force يحذف المسرود فقط؛ فيبقى الدخيل فيرفض.
                de.export_job(_job("job-2"), out, force=True)
            self.assertTrue(os.path.isfile(
                os.path.join(out, "stranger.txt")))
            # بعد إزالة الدخيل يدويًا ينجح --force ويستبدل الحزمة.
            os.unlink(os.path.join(out, "stranger.txt"))
            manifest = de.export_job(_job("job-2"), out, force=True)
            self.assertEqual(manifest["job_id"], "job-2")
            self.assertFalse(os.path.exists(os.path.join(out, "old.log")))
            self.assertTrue(os.path.isfile(os.path.join(out, "job.json")))

    def test_force_without_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "pkg")
            os.makedirs(out)
            with open(os.path.join(out, "keep.txt"), "w") as handle:
                handle.write("keep me")
            with self.assertRaises(de.ExportError):
                de.export_job(_job(), out, force=True)
            self.assertTrue(os.path.isfile(os.path.join(out, "keep.txt")))

    def test_force_clean_deletes_only_listed(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "pkg")
            de.export_job(_job(), out,
                          sources=[{"name": "a.log", "lines": ["a"]}])
            with open(os.path.join(out, "b.txt"), "w") as handle:
                handle.write("b")
            deleted = de.force_clean(out)
            self.assertEqual(set(deleted), {"job.json", "a.log"})
            self.assertTrue(os.path.isfile(os.path.join(out, "b.txt")))
            self.assertTrue(os.path.isfile(
                os.path.join(out, "manifest.json")))

    def test_read_manifest_returns_none_when_absent(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(de.read_manifest(td))


if __name__ == "__main__":
    unittest.main()
