#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات حارس تسرّب الأسرار — جولة v0.1.37 (مقترح tinker رقم 1).

الشجرة الحقيقية يجب أن تبقى نظيفة دائمًا (أي إصابة تفشل
المجموعة)، والأنماط تُختبر على ملفات مؤقتة اصطناعية.
"""
import json
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


class TestProviderDetectors(unittest.TestCase):
    """كواشف صيغة المزود (W8): زوج موجب/سالب لكل مزود.

    العينات الموجبة وهمية بصيغ صحيحة تُبنى وقت التشغيل
    (لا توجد مفاتيح حرفية في هذا الملف إطلاقًا — والسلاسل
    الطويلة مقسّمة حتى لا يطابق الحارس ملف اختباره هو).
    """

    def test_google_key_detected(self):
        fake = "AIza" + _mixed(35)
        found = _scan_text('x = "%s"\n' % fake)
        self.assertTrue(any(f["pattern"] == "google" for f in found),
                        found)

    def test_google_fake_example_allowlisted(self):
        # المفتاح الوهمي الموثق في قائمة السماح لا يُكتشف.
        self.assertIn(secret_guard._FAKE_GOOGLE_KEY,
                      secret_guard.ALLOWLIST_VALUES)
        found = _scan_text('x = "%s"\n' % secret_guard._FAKE_GOOGLE_KEY)
        self.assertEqual(found, [], found)

    def test_google_short_key_not_flagged(self):
        fake = "AIza" + _mixed(10)
        self.assertEqual(_scan_text('x = "%s"\n' % fake), [])

    def test_groq_key_detected(self):
        fake = "gsk_" + _mixed(48)
        found = _scan_text('x = "%s"\n' % fake)
        self.assertTrue(any(f["pattern"] == "groq" for f in found),
                        found)

    def test_groq_fake_example_allowlisted(self):
        self.assertIn(secret_guard._FAKE_GROQ_KEY,
                      secret_guard.ALLOWLIST_VALUES)
        found = _scan_text('x = "%s"\n' % secret_guard._FAKE_GROQ_KEY)
        self.assertEqual(found, [], found)

    def test_groq_short_key_not_flagged(self):
        fake = "gsk_" + _mixed(10)
        self.assertEqual(_scan_text('x = "%s"\n' % fake), [])

    def test_openrouter_key_detected_no_openai_double_count(self):
        fake = "sk-or-v1-" + _mixed(64)
        found = _scan_text('x = "%s"\n' % fake)
        self.assertTrue(any(f["pattern"] == "openrouter"
                            for f in found), found)
        # البادئة تبدأ بـ sk- لكنها ليست مفتاح OpenAI.
        self.assertFalse(any(f["pattern"] == "openai" for f in found),
                         found)

    def test_openrouter_fake_example_allowlisted(self):
        self.assertIn(secret_guard._FAKE_OPENROUTER_KEY,
                      secret_guard.ALLOWLIST_VALUES)
        found = _scan_text(
            'x = "%s"\n' % secret_guard._FAKE_OPENROUTER_KEY)
        self.assertEqual(found, [], found)

    def test_openrouter_short_key_not_flagged(self):
        fake = "sk-or-v1-" + _mixed(10)
        self.assertEqual(_scan_text('x = "%s"\n' % fake), [])

    def test_openai_key_detected(self):
        fake = "sk-" + _mixed(48)
        found = _scan_text('x = "%s"\n' % fake)
        self.assertTrue(any(f["pattern"] == "openai" for f in found),
                        found)

    def test_openai_proj_key_detected(self):
        fake = "sk-proj-" + _mixed(48)
        found = _scan_text('x = "%s"\n' % fake)
        self.assertTrue(any(f["pattern"] == "openai" for f in found),
                        found)

    def test_openai_fake_example_allowlisted(self):
        self.assertIn(secret_guard._FAKE_OPENAI_KEY,
                      secret_guard.ALLOWLIST_VALUES)
        found = _scan_text('x = "%s"\n' % secret_guard._FAKE_OPENAI_KEY)
        self.assertEqual(found, [], found)

    def test_openai_short_key_not_flagged(self):
        fake = "sk-" + _mixed(20)
        self.assertEqual(_scan_text('x = "%s"\n' % fake), [])

    def test_anthropic_key_detected_no_openai_double_count(self):
        fake = "sk-ant-api03-" + _mixed(93)
        found = _scan_text('x = "%s"\n' % fake)
        self.assertTrue(any(f["pattern"] == "anthropic"
                            for f in found), found)
        self.assertFalse(any(f["pattern"] == "openai" for f in found),
                         found)

    def test_anthropic_fake_example_allowlisted(self):
        self.assertIn(secret_guard._FAKE_ANTHROPIC_KEY,
                      secret_guard.ALLOWLIST_VALUES)
        found = _scan_text(
            'x = "%s"\n' % secret_guard._FAKE_ANTHROPIC_KEY)
        self.assertEqual(found, [], found)

    def test_anthropic_short_key_not_flagged(self):
        # قيمة قصيرة منخفضة الإنتروبيا حتى لا يلتقطها كاشف
        # السلسلة الطويلة العام — المقصود كاشف Anthropic وحده.
        fake = "sk-ant-api03-" + "A" * 20
        self.assertEqual(_scan_text('x = "%s"\n' % fake), [])

    def test_elevenlabs_key_detected(self):
        fake = "sk_" + ("a1b2c3d4e5f6" * 4)[:48]
        found = _scan_text('x = "%s"\n' % fake)
        self.assertTrue(any(f["pattern"] == "elevenlabs"
                            for f in found), found)

    def test_elevenlabs_fake_example_allowlisted(self):
        self.assertIn(secret_guard._FAKE_ELEVENLABS_KEY,
                      secret_guard.ALLOWLIST_VALUES)
        found = _scan_text(
            'x = "%s"\n' % secret_guard._FAKE_ELEVENLABS_KEY)
        self.assertEqual(found, [], found)

    def test_elevenlabs_short_key_not_flagged(self):
        fake = "sk_" + ("a1b2c3d4e5f6" * 2)[:24]
        self.assertEqual(_scan_text('x = "%s"\n' % fake), [])


class TestPrivateKeysAndDotenv(unittest.TestCase):
    """المفاتيح الخاصة (RSA/EC/OpenSSH/PKCS#8) وملفات .env (W8)."""

    def test_ec_private_key_detected(self):
        marker = "-----BEGIN " + "EC PRIVATE KEY-----"
        text = "key = '%s\nMIIEvg==\n'\n" % marker
        found = _scan_text(text)
        self.assertTrue(any(f["pattern"] == "pem" for f in found),
                        found)

    def test_encrypted_private_key_detected(self):
        marker = "-----BEGIN " + "ENCRYPTED PRIVATE KEY-----"
        text = "key = '%s\nMIIEvg==\n'\n" % marker
        found = _scan_text(text)
        self.assertTrue(any(f["pattern"] == "pem" for f in found),
                        found)

    def test_public_key_not_flagged(self):
        # مفتاح عام لا سر — علامة PUBLIC لا تطابق كاشف PEM.
        text = "key = '-----BEGIN " + "PUBLIC KEY-----\nMIIEvg==\n'\n"
        self.assertEqual(_scan_text(text), [])

    def test_committed_dotenv_file_flagged(self):
        # ملف .env غير مغطى بـ .gitignore يُبلَّغ بذاته.
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, ".gitignore"), "w",
                      encoding="utf-8") as fh:
                fh.write("")
            with open(os.path.join(td, ".env"), "w",
                      encoding="utf-8") as fh:
                fh.write("NOTE=hello\n")
            found = secret_guard.scan_tree(td)
            self.assertEqual(len(found), 1, found)
            self.assertEqual(found[0]["pattern"], "dotenv_file")
            self.assertEqual(found[0]["id"], "SG-DOTENV-001")
            self.assertEqual(found[0]["severity"], "critical")
            self.assertTrue(found[0]["fix"])

    def test_dotenv_example_not_flagged_as_file(self):
        # قالب .env.example مقصود الالتزام — اسمه وحده لا يُبلَّغ.
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, ".gitignore"), "w",
                      encoding="utf-8") as fh:
                fh.write("")
            with open(os.path.join(td, ".env.example"), "w",
                      encoding="utf-8") as fh:
                fh.write("GEMINI_API_KEY=your-api-key-here\n")
            self.assertEqual(secret_guard.scan_tree(td), [])

    def test_gitignored_dotenv_file_skipped(self):
        # ملف .env مغطى بـ .gitignore — لا يُفحص أصلًا (قاعدة 1).
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, ".gitignore"), "w",
                      encoding="utf-8") as fh:
                fh.write(".env\n")
            with open(os.path.join(td, ".env"), "w",
                      encoding="utf-8") as fh:
                fake = "AIza" + _mixed(35)
                fh.write('GEMINI_API_KEY="%s"\n' % fake)
            self.assertEqual(secret_guard.scan_tree(td), [])


class TestFindingTemplate(unittest.TestCase):
    """قالب الإصابات (W8): كل إصابة بمعرّف وخطورة وإصلاح."""

    def test_findings_carry_id_severity_fix(self):
        fake = "AIza" + _mixed(35)
        found = _scan_text('x = "%s"\n' % fake)
        self.assertTrue(found)
        for f in found:
            self.assertTrue(f["id"].startswith("SG-"), f)
            self.assertIn(f["severity"], ("critical", "high"), f)
            self.assertTrue(f["fix"], f)
            # الحقول القديمة باقية دون تغيير.
            self.assertIn("file", f)
            self.assertIn("line", f)
            self.assertIn("pattern", f)
            self.assertIn("value", f)
            # القيمة مبتورة — لا مفتاح كامل في التقرير.
            self.assertNotIn(fake, f["value"])

    def test_provider_finding_is_critical(self):
        fake = "gsk_" + _mixed(48)
        found = _scan_text('x = "%s"\n' % fake)
        groq = [f for f in found if f["pattern"] == "groq"]
        self.assertEqual(len(groq), 1)
        self.assertEqual(groq[0]["id"], "SG-GROQ-001")
        self.assertEqual(groq[0]["severity"], "critical")

    def test_error_code_not_a_secret(self):
        # رمز خطأ عام موثق (W5b) في lib/errors.py — ليس سرًا.
        text = 'facebook_token = "STUDIO-FACEBOOK-002"\n'
        self.assertEqual(_scan_text(text), [])
        # وقيمة مشابهة خارج الصيغة ما زالت تُكتشف (تُبنى
        # ديناميكيًا حتى لا يطابق الحارس ملف اختباره هو).
        value = "STUDIO-FACEBOOK-002" + "x"
        text = 'facebook_token = "%s"\n' % value
        found = _scan_text(text)
        self.assertTrue(any(f["pattern"] == "assignment"
                            for f in found), found)


def _mixed(n):
    """سلسلة وهمية مختلطة طولها n (بلا علامات أمثلة).

    الأبجدية مقسّمة ليترات قصيرة حتى لا يطابق الحارس ملف
    اختباره هو (كاشف السلسلة الطويلة يحتاج 32+ حرفًا).
    """
    alphabet = ("Qw7Er4Ty9Ui2Op5" "As6Df8Gh3Jk1Lz0X" "cVbNm")
    return (alphabet * ((n // len(alphabet)) + 1))[:n]


class TestSarifExport(unittest.TestCase):
    """مخرجات SARIF (W8 — أولوية دنيا): بنية صالحة بلا أسرار."""

    def test_sarif_structure(self):
        fake = "AIza" + _mixed(35)
        found = _scan_text('x = "%s"\n' % fake)
        sarif = secret_guard.to_sarif(found)
        self.assertEqual(sarif["version"], "2.1.0")
        run = sarif["runs"][0]
        self.assertEqual(run["tool"]["driver"]["name"], "secret-guard")
        rule_ids = [r["id"] for r in
                    run["tool"]["driver"]["rules"]]
        self.assertIn("SG-GOOGLE-001", rule_ids)
        self.assertEqual(len(run["results"]), len(found))
        res = run["results"][0]
        self.assertEqual(res["ruleId"], found[0]["id"])
        self.assertEqual(res["level"], "error")
        loc = res["locations"][0]["physicalLocation"]
        self.assertEqual(loc["artifactLocation"]["uri"], "probe.py")
        self.assertEqual(loc["region"]["startLine"], 1)
        # لا قيمة سرية في المخرجات إطلاقًا.
        self.assertNotIn(fake, json.dumps(sarif))

    def test_sarif_empty_findings(self):
        sarif = secret_guard.to_sarif([])
        run = sarif["runs"][0]
        self.assertEqual(run["results"], [])
        self.assertEqual(run["tool"]["driver"]["rules"], [])


if __name__ == "__main__":
    unittest.main()
