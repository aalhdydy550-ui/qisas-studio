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
import stat
import sys
import tempfile
import unittest
from unittest import mock

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


class TestWriteOnlyKeys(unittest.TestCase):
    """مفاتيح كتابة فقط (جولة v0.1.63، بند 13 — عقد ع12).

    كل الاختبارات على مجلد مؤقت عبر QISAS_KEYS_DIR — لا تلمس
    مخزن المفاتيح الحقيقي (~/.qisas-studio/keys.json) أبدًا،
    وتتحقق في النهاية أن حالته لم تتغيّر. المفاتيح وهمية
    تُبنى وقت التشغيل عبر _mixed (بلا قيم حرفية إطلاقًا).
    """

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = self._td.name
        self.addCleanup(self._td.cleanup)
        self.env = mock.patch.dict(
            os.environ, {secret_guard.KEYS_DIR_ENV: self.td})
        self.env.start()
        self.addCleanup(self.env.stop)
        self._real_snapshot = None
        if os.path.exists(REAL_KEYS):
            with open(REAL_KEYS, "rb") as fh:
                self._real_snapshot = fh.read()

    def tearDown(self):
        # الحارس: مخزن المفاتيح الحقيقي لم يُنشأ ولم يُعدَّل.
        if self._real_snapshot is None:
            self.assertFalse(os.path.exists(REAL_KEYS),
                             "الاختبار كتب في مخزن المفاتيح الحقيقي!")
        else:
            self.assertTrue(os.path.exists(REAL_KEYS),
                            "الاختبار حذف مخزن المفاتيح الحقيقي!")
            with open(REAL_KEYS, "rb") as fh:
                self.assertEqual(fh.read(), self._real_snapshot,
                                 "الاختبار عدّل مخزن المفاتيح الحقيقي!")

    def _fake(self, provider):
        if provider in ("gemini", "google"):
            return "AIza" + _mixed(35)
        if provider == "groq":
            return "gsk_" + _mixed(48)
        if provider == "openrouter":
            return "sk-or-v1-" + _mixed(64)
        if provider == "openai":
            return "sk-" + _mixed(48)
        return "sk-" + _mixed(48)

    def _read_store_bytes(self):
        path = os.path.join(self.td, secret_guard.KEYS_FILENAME)
        with open(path, "rb") as fh:
            return fh.read()

    def test_rejected_key_is_not_saved(self):
        # مزوّد محاكى يرفض المفتاح → لا حفظ إطلاقًا.
        fake = self._fake("gemini")
        with self.assertRaises(secret_guard.KeyTestError):
            secret_guard.set_key(
                "gemini", fake,
                tester=lambda provider, value: False)
        self.assertEqual(secret_guard.list_keys(), [])
        self.assertFalse(os.path.exists(
            os.path.join(self.td, secret_guard.KEYS_FILENAME)))

    def test_tester_exception_is_rejection_not_save(self):
        fake = self._fake("gemini")

        def _boom(provider, value):
            raise RuntimeError("انقطع الاتصال بالمزوّد")

        with self.assertRaises(secret_guard.KeyTestError):
            secret_guard.set_key("gemini", fake, tester=_boom)
        self.assertEqual(secret_guard.list_keys(), [])

    def test_accepted_key_saved_but_value_never_listed(self):
        fake = self._fake("gemini")
        entry = secret_guard.set_key(
            "gemini", fake, tester=lambda p, v: True)
        self.assertEqual(entry["name"], "gemini")
        self.assertEqual(entry["provider"], "gemini")
        self.assertTrue(entry["present"])
        self.assertNotIn("value", entry)
        listed = secret_guard.list_keys()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["name"], "gemini")
        self.assertTrue(listed[0]["present"])
        self.assertNotIn("value", listed[0])
        # لا قيمة سرية في أي مخرج سرد إطلاقًا.
        self.assertNotIn(fake, json.dumps(listed))
        self.assertNotIn(fake, json.dumps(entry))

    def test_default_tester_rejects_wrong_format(self):
        # بلا tester: تحقق صيغة فقط — صيغة خاطئة تُرفض.
        with self.assertRaises(secret_guard.KeyTestError):
            secret_guard.set_key("gemini", "not-a-real-key")
        self.assertEqual(secret_guard.list_keys(), [])

    def test_default_tester_accepts_right_format(self):
        fake = self._fake("groq")
        entry = secret_guard.set_key("groq", fake)
        self.assertEqual(entry["provider"], "groq")
        self.assertTrue(secret_guard.has_key("groq"))

    def test_provider_inferred_from_value_format(self):
        fake = self._fake("openrouter")
        entry = secret_guard.set_key("mykey", fake)
        self.assertEqual(entry["provider"], "openrouter")

    def test_rotate_keeps_old_until_new_passes(self):
        old = self._fake("gemini")
        secret_guard.set_key("gemini", old,
                             tester=lambda p, v: True)
        before = self._read_store_bytes()
        # تدوير بمفتاح يرفضه المزوّد → المخزن بلا أي تغيير.
        # (القيم الجديدة مبنية ببادئة حرف مختلف لأن _mixed
        # حتمي — وإلا تطابق الجديد القديم.)
        new_bad = "AIza" + "Y" + _mixed(34)
        with self.assertRaises(secret_guard.KeyTestError):
            secret_guard.rotate_key(
                "gemini", new_bad,
                tester=lambda p, v: False)
        self.assertEqual(self._read_store_bytes(), before)
        # تدوير بمفتاح يقبله المزوّد → يُكتب الجديد فقط.
        new_good = "AIza" + "Z" + _mixed(34)
        entry = secret_guard.rotate_key(
            "gemini", new_good, tester=lambda p, v: True)
        self.assertTrue(entry["present"])
        self.assertTrue(entry["rotated_at"])
        self.assertNotEqual(self._read_store_bytes(), before)
        stored = json.loads(self._read_store_bytes())
        self.assertEqual(stored["keys"]["gemini"]["value"], new_good)
        self.assertNotEqual(stored["keys"]["gemini"]["value"], old)

    def test_rotate_missing_key_raises(self):
        with self.assertRaises(secret_guard.KeyStoreError):
            secret_guard.rotate_key(
                "ghost", self._fake("gemini"),
                tester=lambda p, v: True)

    def test_list_shows_names_and_presence_only(self):
        secret_guard.set_key("gemini", self._fake("gemini"),
                             tester=lambda p, v: True)
        secret_guard.set_key("groq", self._fake("groq"),
                             tester=lambda p, v: True)
        listed = secret_guard.list_keys()
        self.assertEqual([e["name"] for e in listed],
                         ["gemini", "groq"])
        for entry in listed:
            self.assertTrue(entry["present"])
            self.assertNotIn("value", entry)
        self.assertNotIn("AIza", json.dumps(listed))
        self.assertNotIn("gsk_", json.dumps(listed))

    def test_diagnose_masks_keys(self):
        fake = self._fake("gemini")
        secret_guard.set_key("gemini", fake,
                             tester=lambda p, v: True)
        text = "\n".join(secret_guard.diagnose_keys())
        self.assertNotIn(fake, text)
        # القيمة المقنّعة (أول 4 + … + آخر 4) ظاهرة، لا الكاملة.
        self.assertIn(fake[:4] + "…" + fake[-4:], text)
        self.assertIn("gemini", text)
        self.assertIn("موجود", text)

    def test_redact_text_masks_provider_key(self):
        fake = self._fake("gemini")
        text = 'حدث خطأ أثناء استدعاء المفتاح "%s" — أعد المحاولة' % fake
        redacted = secret_guard.redact_text(text)
        self.assertNotIn(fake, redacted)
        self.assertIn(fake[:4] + "…" + fake[-4:], redacted)
        self.assertIn("حدث خطأ", redacted)

    def test_mask_secret_never_returns_full_value(self):
        fake = self._fake("openai")
        masked = secret_guard.mask_secret(fake)
        self.assertNotEqual(masked, fake)
        self.assertNotIn(fake, masked)
        self.assertTrue(masked.startswith(fake[:4]))
        self.assertTrue(masked.endswith(fake[-4:]))
        # قيمة قصيرة تُستبدل بنجوم بطولها.
        self.assertEqual(secret_guard.mask_secret("abc"), "***")
        self.assertEqual(secret_guard.mask_secret(""), "")

    def test_read_token_file(self):
        fake = self._fake("groq")
        path = os.path.join(self.td, "token.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(fake + "\n")
        self.assertEqual(secret_guard.read_token_file(path), fake)
        # ملف غائب أو فارغ = خطأ صريح.
        with self.assertRaises(secret_guard.KeyStoreError):
            secret_guard.read_token_file(
                os.path.join(self.td, "missing.txt"))
        empty = os.path.join(self.td, "empty.txt")
        with open(empty, "w", encoding="utf-8") as fh:
            fh.write("  \n")
        with self.assertRaises(secret_guard.KeyStoreError):
            secret_guard.read_token_file(empty)

    def test_invalid_name_rejected(self):
        fake = self._fake("gemini")
        for bad in ("", "bad/name", "bad name", "a" * 65):
            with self.assertRaises(ValueError, msg=bad):
                secret_guard.set_key(bad, fake,
                                     tester=lambda p, v: True)
        self.assertEqual(secret_guard.list_keys(), [])

    def test_empty_value_rejected(self):
        with self.assertRaises(ValueError):
            secret_guard.set_key("gemini", "   ",
                                 tester=lambda p, v: True)

    def test_store_file_is_0600(self):
        secret_guard.set_key("gemini", self._fake("gemini"),
                             tester=lambda p, v: True)
        path = os.path.join(self.td, secret_guard.KEYS_FILENAME)
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.td).st_mode), 0o700)

    def test_corrupt_store_is_not_silently_emptied(self):
        path = os.path.join(self.td, secret_guard.KEYS_FILENAME)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        with self.assertRaises(secret_guard.KeyStoreError):
            secret_guard.list_keys()
        with self.assertRaises(secret_guard.KeyStoreError):
            secret_guard.set_key("gemini", self._fake("gemini"),
                                 tester=lambda p, v: True)

    def test_has_key(self):
        self.assertFalse(secret_guard.has_key("gemini"))
        secret_guard.set_key("gemini", self._fake("gemini"),
                             tester=lambda p, v: True)
        self.assertTrue(secret_guard.has_key("gemini"))
        self.assertFalse(secret_guard.has_key("groq"))


REAL_KEYS = os.path.expanduser("~/.qisas-studio/keys.json")


if __name__ == "__main__":
    unittest.main()
