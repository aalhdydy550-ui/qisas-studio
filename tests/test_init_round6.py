#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات الجولة 6 لمعالج الإعداد (lib.init_wizard).

تغطي: حقول الهوية والدفع الجديدة، ونسخ الشعار (PNG صالح
يُنسخ، وغير الصالح يُرفض)، وخطوات الربط عند غياب التوكنات،
وعلم --check-only (بلا كتابة)، وعدم المساس بأي ملف حقيقي.

تعمل بـ `python3 -m unittest tests.test_init_round6 -v` من
~/workspace/studio/. كل الكتابة في مجلدات مؤقتة — لا يُمس
config.yaml الحقيقي ولا ملف الطابور الحقيقي أبدًا.
"""
import hashlib
import os
import shutil
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import init_wizard

REAL_CONFIG = os.path.expanduser("~/workspace/studio/config.yaml")
REAL_LOGO = os.path.expanduser(
    "~/workspace/studio/assets/qisas-logo-badge.png")

BASE_CFG = {
    "publish": {"page_id": "", "youtube_channel_id": "",
                "youtube_token": ""},
    "paths": {"queue_file": "~/workspace/queue.md",
              "videos_dir": "~/workspace/videos"},
    "schedule": {"morning": "09:00", "evening": "19:00"},
    "narration": {"voice": "piper"},
}


def _read_yaml(path):
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _make_png(path, width=4, height=4):
    """اكتب PNG صالحًا صغيرًا (1×1 فعليًا بأبعاد معطاة)."""
    def chunk(kind, data):
        c = struct.pack(">I", len(data)) + kind + data
        return c + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x00\x00\x00" * width
                   for _ in range(height))
    data = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(data)
    return path


class _FakeProc:
    def __init__(self, returncode=1, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fb_fail_runner(cmd, **kw):
    return _FakeProc(returncode=1, stdout="", stderr="boom")


class TestIdentityPaymentValidation(unittest.TestCase):
    def test_payment_number_valid(self):
        self.assertEqual(
            init_wizard.validate_payment_number("01023468196"),
            "01023468196")
        self.assertEqual(
            init_wizard.validate_payment_number("+201023468196"),
            "01023468196")
        self.assertEqual(
            init_wizard.validate_payment_number("0102 346 8196"),
            "01023468196")
        self.assertEqual(init_wizard.validate_payment_number(""), "")

    def test_payment_number_invalid(self):
        for bad in ("123", "0102346819", "010234681960", "abc",
                    "+442071234567", "02023468196"):
            with self.assertRaises(init_wizard.InitError, msg=bad):
                init_wizard.validate_payment_number(bad)

    def test_page_name(self):
        self.assertEqual(init_wizard.validate_page_name("قصص وعبر"),
                         "قصص وعبر")
        self.assertEqual(init_wizard.validate_page_name("  "), "")
        with self.assertRaises(init_wizard.InitError):
            init_wizard.validate_page_name("x" * 101)

    def test_apply_identity_payment(self):
        cfg = init_wizard.apply_answers(BASE_CFG, {
            "page_name": "قصص وعبر",
            "payment_number": "+201011122233"})
        self.assertEqual(cfg["identity"]["page_name"], "قصص وعبر")
        self.assertEqual(cfg["payment"]["method"], "vodafone_cash")
        self.assertEqual(cfg["payment"]["vodafone_cash"], "01011122233")

    def test_apply_empty_identity_keeps_current(self):
        cfg = init_wizard.apply_answers(
            dict(BASE_CFG, identity={"page_name": "قديم"},
                 payment={"vodafone_cash": "01000000000"}),
            {"page_name": "", "payment_number": ""})
        self.assertEqual(cfg["identity"]["page_name"], "قديم")
        self.assertEqual(cfg["payment"]["vodafone_cash"], "01000000000")


class TestLogo(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="init6-logo-")

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_valid_png_accepted(self):
        src = _make_png(os.path.join(self.td, "logo.png"), 120, 60)
        self.assertEqual(init_wizard.validate_logo_png(src), (120, 60))

    def test_non_png_rejected(self):
        bad = os.path.join(self.td, "not-png.png")
        Path(bad).write_text("أنا نص ولست صورة", encoding="utf-8")
        with self.assertRaises(init_wizard.InitError):
            init_wizard.validate_logo_png(bad)

    def test_missing_file_rejected(self):
        with self.assertRaises(init_wizard.InitError):
            init_wizard.validate_logo_png(
                os.path.join(self.td, "ghost.png"))

    def test_install_logo_copies_atomically(self):
        src = _make_png(os.path.join(self.td, "logo.png"), 8, 8)
        dest, w, h = init_wizard.install_logo(src, self.td)
        self.assertEqual(
            dest, os.path.join(self.td, "assets", "qisas-logo-badge.png"))
        self.assertEqual((w, h), (8, 8))
        self.assertEqual(Path(dest).read_bytes(), Path(src).read_bytes())

    def test_install_logo_rejects_invalid(self):
        bad = os.path.join(self.td, "bad.png")
        Path(bad).write_bytes(b"\x89PNG\r\n\x1a\n" + b"short")
        with self.assertRaises(init_wizard.InitError):
            init_wizard.install_logo(bad, self.td)
        self.assertFalse(os.path.exists(
            os.path.join(self.td, "assets", "qisas-logo-badge.png")))


class TestRunWizardRound6(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="init6-run-")
        self.cfg_path = os.path.join(self.td, "config.yaml")
        self.out = []
        self.printer = self.out.append
        self.cfg = dict(BASE_CFG)
        self.cfg["publish"] = dict(BASE_CFG["publish"])
        self.cfg["publish"]["youtube_token"] = os.path.join(
            self.td, "no-token.json")

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def _run(self, flags, **kw):
        return init_wizard.run_wizard(
            self.cfg, self.cfg_path, flags=flags, print_fn=self.printer,
            fb_runner=_fb_fail_runner, **kw)

    def test_writes_identity_payment_and_logo(self):
        src = _make_png(os.path.join(self.td, "logo.png"), 16, 16)
        rc = self._run({"page_id": "123", "page_name": "قصص وعبر",
                        "payment_number": "01011122233",
                        "logo_file": src})
        self.assertEqual(rc, 0)
        cfg = _read_yaml(self.cfg_path)
        self.assertEqual(cfg["identity"]["page_name"], "قصص وعبر")
        self.assertEqual(cfg["identity"]["logo_file"],
                         "assets/qisas-logo-badge.png")
        self.assertEqual(cfg["payment"]["method"], "vodafone_cash")
        self.assertEqual(cfg["payment"]["vodafone_cash"], "01011122233")
        dest = os.path.join(self.td, "assets", "qisas-logo-badge.png")
        self.assertTrue(os.path.isfile(dest))
        self.assertEqual(Path(dest).read_bytes(), Path(src).read_bytes())

    def test_invalid_logo_fails_without_writing_config(self):
        bad = os.path.join(self.td, "bad.png")
        Path(bad).write_text("ليس PNG", encoding="utf-8")
        rc = self._run({"page_id": "123", "logo_file": bad})
        self.assertEqual(rc, 1)
        self.assertFalse(os.path.isfile(self.cfg_path))

    def test_link_steps_printed_when_tokens_missing(self):
        cfg = dict(self.cfg)
        cfg["publish"] = dict(self.cfg["publish"], page_id="123")
        steps = init_wizard.check_link_steps(
            cfg, fb_runner=_fb_fail_runner)
        by_key = {s["key"]: s for s in steps}
        self.assertFalse(by_key["facebook"]["ok"])
        self.assertIn("connect-url", by_key["facebook"]["fix"])
        self.assertFalse(by_key["youtube"]["ok"])
        self.assertIn("youtube-auth", by_key["youtube"]["fix"])
        text = init_wizard.format_link_steps(steps)
        self.assertIn("فيسبوك", text)
        self.assertIn("يوتيوب", text)
        self.assertIn("youtube-auth", text)
        self.assertIn("خطوة", text)

    def test_check_only_writes_nothing(self):
        rc = init_wizard.run_wizard(
            self.cfg, self.cfg_path, flags={"page_id": "123"},
            print_fn=self.printer, check_only=True,
            fb_runner=_fb_fail_runner)
        self.assertEqual(rc, 1)  # فيسبوك/يوتيوب ناقصان في هذا الإعداد
        self.assertFalse(os.path.isfile(self.cfg_path))
        self.assertFalse(os.path.isfile(
            os.path.join(self.td, "suggested-crons.md")))
        self.assertTrue(any("فيسبوك" in line for line in self.out))

    def test_readme_payment_number_updated(self):
        for name in ("README.md", "README_EN.md"):
            Path(os.path.join(self.td, name)).write_text(
                "ادفع إلى **01023468196** وشكرًا.\n", encoding="utf-8")
        updated = init_wizard.update_readme_payment_number(
            self.td, "01011122233", print_fn=self.printer)
        self.assertEqual(len(updated), 2)
        for name in ("README.md", "README_EN.md"):
            text = Path(os.path.join(self.td, name)).read_text(
                encoding="utf-8")
            self.assertIn("01011122233", text)
            self.assertNotIn("01023468196", text)

    def test_readme_untouched_without_new_number(self):
        Path(os.path.join(self.td, "README.md")).write_text(
            "ادفع إلى **01023468196**.\n", encoding="utf-8")
        before = Path(os.path.join(self.td, "README.md")).read_bytes()
        updated = init_wizard.update_readme_payment_number(
            self.td, "", print_fn=self.printer)
        self.assertEqual(updated, [])
        self.assertEqual(
            Path(os.path.join(self.td, "README.md")).read_bytes(), before)
        updated = init_wizard.update_readme_payment_number(
            self.td, "01023468196", print_fn=self.printer)
        self.assertEqual(updated, [])

    def test_interactive_identity_after_overwrite_confirm(self):
        Path(self.cfg_path).write_text("قديم\n", encoding="utf-8")
        src = _make_png(os.path.join(self.td, "logo.png"), 8, 8)
        answers = iter(["555", "UCy", "piper", "07:30", "21:00",
                        os.path.join(self.td, "q.md"), "y",
                        "قصص وعبر", src, "01011122233"])

        def fake_input(prompt=""):
            return next(answers)

        rc = init_wizard.run_wizard(
            self.cfg, self.cfg_path, flags=None,
            input_fn=fake_input, print_fn=self.printer,
            fb_runner=_fb_fail_runner)
        self.assertEqual(rc, 0)
        cfg = _read_yaml(self.cfg_path)
        self.assertEqual(cfg["publish"]["page_id"], "555")
        self.assertEqual(cfg["identity"]["page_name"], "قصص وعبر")
        self.assertEqual(cfg["payment"]["vodafone_cash"], "01011122233")
        self.assertTrue(os.path.isfile(
            os.path.join(self.td, "assets", "qisas-logo-badge.png")))

    @unittest.skipUnless(
        os.path.isfile(REAL_CONFIG) and os.path.isfile(REAL_LOGO),
        "ملفات الإعداد الحقيقية غائبة — بيئة CI")
    def test_real_files_untouched(self):
        def _sig(path):
            st = os.stat(path)
            with open(path, "rb") as f:
                digest = hashlib.sha256(f.read()).hexdigest()
            return (st.st_mtime_ns, st.st_size, digest)

        before_cfg = _sig(REAL_CONFIG)
        before_logo = _sig(REAL_LOGO)
        src = _make_png(os.path.join(self.td, "logo.png"), 8, 8)
        rc = self._run({"page_id": "123", "page_name": "اختبار",
                        "payment_number": "01011122233",
                        "logo_file": src})
        self.assertEqual(rc, 0)
        self.assertEqual(_sig(REAL_CONFIG), before_cfg)
        self.assertEqual(_sig(REAL_LOGO), before_logo)


if __name__ == "__main__":
    unittest.main()
