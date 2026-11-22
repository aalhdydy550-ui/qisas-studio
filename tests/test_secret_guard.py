#!/usr/bin/env python3
"""اختبارات حارس تسرّب الأسرار — جولة v0.1.37 (مقترح tinker رقم 1).

الشجرة الحقيقية يجب أن تبقى نظيفة دائمًا (أي إصابة تفشل
المجموعة)، والأنماط تُختبر على ملفات مؤقتة اصطناعية.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import secret_guard

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _scan_text(text, gitignore=""):
    """امسح نصًا واحدًا عبر شجرة مؤقتة؛ ارجع الإصابات."""
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, ".gitignore"), "w",
                  encoding="utf-8") as fh:
            fh.write(gitignore)
        path = os.path.join(td, "probe.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return secret_guard.scan_tree(td)


class TestRealTreeClean(unittest.TestCase):
    def test_real_tree_has_no_secrets(self):
        findings = secret_guard.scan_tree(STUDIO_ROOT)
        self.assertEqual(findings, [],
                         "إصابات أسرار في الشجرة الحقيقية: %s" % findings)

    def test_gitignore_covers_secret_files(self):
        self.assertEqual(secret_guard.check_gitignore(STUDIO_ROOT), [])

    def test_allowlist_documents_public_values(self):
        # رقم فودافون كاش ومعرّف الصفحة قيمان عامتان معلنتان —
        # وجودهما في القائمة موثق، وحذفهما بصمت مرفوض.
        self.assertIn("01023468196", secret_guard.ALLOWLIST_VALUES)
        self.assertIn("1048148471706586", secret_guard.ALLOWLIST_VALUES)

    def test_public_values_do_not_flag(self):
        text = ('page_id = "1048148471706586"\n'
                'vodafone_cash = "01023468196"\n')
        self.assertEqual(_scan_text(text), [])


class TestPatternsDetect(unittest.TestCase):
    def test_api_key_assignment_detected(self):
        fake = "sk_live_" + "9f8e7d6c5b4a39281706f5e4d3c2b1a0"
        text = 'api_key = "%s"\n' % fake
        found = _scan_text(text)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["pattern"], "assignment")

    def test_huggingface_token_detected(self):
        fake = "hf_" + "AbCdEfGhIjKlMnOpQr" + "StUvWxYz9876543210"
        text = 'x = "%s"\n' % fake
        found = _scan_text(text)
        self.assertTrue(any(f["pattern"] == "huggingface" for f in found))

    def test_bearer_token_detected(self):
        fake = "Bearer " + "abcdefghij9876543210KLMNOP"
        text = 'auth = "%s"\n' % fake
        found = _scan_text(text)
        self.assertTrue(any(f["pattern"] == "bearer" for f in found))

    def test_pem_block_detected(self):
        marker = "-----BEGIN " + "PRIVATE KEY-----"
        text = "key = '%s\nMIIEvg==\n'\n" % marker
        found = _scan_text(text)
        self.assertTrue(any(f["pattern"] == "pem" for f in found))

    def test_github_token_detected(self):
        text = 't = "ghp_' + "A" * 36 + '"\n'
        found = _scan_text(text)
        self.assertTrue(any(f["pattern"] == "github" for f in found))


class TestNoFalsePositives(unittest.TestCase):
    def test_fixture_token_not_flagged(self):
        # توكن اختبار وهمي في tests/test_publish.py — يجب ألا يُرفَض.
        text = 'token="test-token-1234567890"\n'
        self.assertEqual(_scan_text(text), [])

    def test_bearer_word_alone_not_flagged(self):
        # كلمة "Bearer token" في FIXES.md/CHANGELOG.md ليست سرًا.
        text = "# أرسل Bearer token في الترويسة\n"
        self.assertEqual(_scan_text(text), [])

    def test_path_value_not_flagged(self):
        # مسار ملف توكن في config.example.yaml — قيمة مسار لا سر.
        text = 'youtube_token: "~/workspace/studio/youtube-token.json"\n'
        self.assertEqual(_scan_text(text), [])

    def test_function_call_not_flagged(self):
        # استدعاء دالة load_token(...) لا سر.
        text = "token = social_lib.load_token(platform)\n"
        self.assertEqual(_scan_text(text), [])

    def test_hex_sha_not_flagged(self):
        # بصمة SHA أربعينية (هكس خالص) ليست سرًا.
        text = 'sha = "d685cc7b1d6d757f9990257a1d6d757f9990257a"\n'
        self.assertEqual(_scan_text(text), [])

    def test_gitignored_secret_file_skipped(self):
        # ملف سر حقيقي لكنه مغطى بـ .gitignore — لا يُفحص
        # (شرط بقائه في .gitignore يتحققه check_gitignore).
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, ".gitignore"), "w",
                      encoding="utf-8") as fh:
                fh.write("secret.json\n")
            with open(os.path.join(td, "secret.json"), "w",
                      encoding="utf-8") as fh:
                fake = "1//0aBcDeFg" + "HiJkLmNoPqRsTuVwXyZ"
                fh.write('{"refresh_token": "%s"}\n' % fake)
            self.assertEqual(secret_guard.scan_tree(td), [])

    def test_gitignore_missing_entry_reported(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, ".gitignore"), "w",
                      encoding="utf-8") as fh:
                fh.write("*.log\n")
            missing = secret_guard.check_gitignore(td)
            self.assertIn("config.yaml", missing)
            self.assertIn("youtube-token.json", missing)


if __name__ == "__main__":
    unittest.main()
