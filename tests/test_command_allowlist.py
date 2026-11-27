#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات قائمة سماح الأوامر الدقيقة — جولة v0.1.63، البند 18.

كل الاختبارات على مجلد مؤقت — لا تلمس ملف القواعد الحقيقي
(~/.qisas-studio/allowlist.json) أبدًا، وتتحقق في النهاية أن
حالته لم تتغيّر.
"""
import json
import os
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import command_allowlist as allowlist

REAL_CONFIG = os.path.expanduser("~/.qisas-studio/allowlist.json")


class AllowlistTestBase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = self._td.name
        self.addCleanup(self._td.cleanup)
        self._real_snapshot = None
        if os.path.exists(REAL_CONFIG):
            with open(REAL_CONFIG, "rb") as fh:
                self._real_snapshot = fh.read()

    def tearDown(self):
        if self._real_snapshot is None:
            self.assertFalse(os.path.exists(REAL_CONFIG),
                             "الاختبار كتب في ملف القواعد الحقيقي!")
        else:
            self.assertTrue(os.path.exists(REAL_CONFIG),
                            "الاختبار حذف ملف القواعد الحقيقي!")
            with open(REAL_CONFIG, "rb") as fh:
                self.assertEqual(fh.read(), self._real_snapshot,
                                 "الاختبار عدّل ملف القواعد الحقيقي!")

    def _save(self, rules):
        return allowlist.save_rules(rules, self.td)


class TestAllowed(AllowlistTestBase):
    def test_bare_command_allowed(self):
        self._save([{"command": "ls"}])
        self.assertTrue(allowlist.allowed("ls", directory=self.td))
        self.assertTrue(allowlist.allowed(["ls"], directory=self.td))

    def test_exact_args_allowed(self):
        self._save([{"command": "melt", "args": [["-version"]]}])
        self.assertTrue(allowlist.allowed("melt -version",
                                          directory=self.td))
        self.assertFalse(allowlist.allowed("melt -noversion",
                                           directory=self.td))
        self.assertFalse(allowlist.allowed("melt",
                                           directory=self.td))

    def test_bare_rule_rejects_args(self):
        self._save([{"command": "ls"}])
        self.assertFalse(allowlist.allowed("ls -la", directory=self.td))

    def test_outside_list_rejected_even_under_full(self):
        # أمر خارج القائمة مرفوض حتى تحت مستوى full — الفصل بين
        # «ما يُسمح به» و«ما يُوافَق عليه» (لا فحص لمستوى هنا؛
        # القائمة نفسها ترفض بلا استثناء).
        self._save([{"command": "ls"}])
        for command in ("rm -rf /", "curl https://example.com",
                        "python3 -c 'import os'", "melt -version",
                        "cat /etc/passwd"):
            self.assertFalse(allowlist.allowed(command, directory=self.td),
                             command)

    def test_wildcard_single_and_rest(self):
        self._save([{"command": "cat", "args": [["*"]]},
                    {"command": "python3",
                     "args": [["-m", "unittest", "**"]]}])
        self.assertTrue(allowlist.allowed("cat file.txt",
                                          directory=self.td))
        self.assertFalse(allowlist.allowed("cat a b",
                                           directory=self.td))
        self.assertTrue(allowlist.allowed(
            "python3 -m unittest tests.test_x -v", directory=self.td))
        self.assertFalse(allowlist.allowed(
            "python3 -m pip install x", directory=self.td))

    def test_missing_file_means_nothing_allowed(self):
        self.assertEqual(allowlist.load_rules(self.td), [])
        self.assertFalse(allowlist.allowed("ls", directory=self.td))

    def test_empty_or_broken_command_rejected(self):
        self._save([{"command": "ls"}])
        self.assertFalse(allowlist.allowed("", directory=self.td))
        self.assertFalse(allowlist.allowed("   ", directory=self.td))
        self.assertFalse(allowlist.allowed(None, directory=self.td))
        self.assertFalse(allowlist.allowed("ls 'unterminated",
                                           directory=self.td))

    def test_explicit_rules_argument(self):
        rules = [{"command": "pwd"}]
        self.assertTrue(allowlist.allowed("pwd", rules=rules))
        self.assertFalse(allowlist.allowed("ls", rules=rules))


class TestSaveLoad(AllowlistTestBase):
    def test_save_load_roundtrip(self):
        rules = [{"command": "ls"},
                 {"command": "melt", "args": [["-version"]]}]
        saved = self._save(rules)
        self.assertEqual(saved, rules)
        self.assertEqual(allowlist.load_rules(self.td), rules)

    def test_saved_file_is_0600(self):
        self._save([{"command": "ls"}])
        path = os.path.join(self.td, "allowlist.json")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["rules"], [{"command": "ls"}])

    def test_corrupt_file_loads_empty(self):
        with open(os.path.join(self.td, "allowlist.json"), "w",
                  encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertEqual(allowlist.load_rules(self.td), [])
        with open(os.path.join(self.td, "allowlist.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"rules": [{"command": ""}]}, fh)
        self.assertEqual(allowlist.load_rules(self.td), [])

    def test_ensure_creates_defaults(self):
        rules = allowlist.ensure_allowlist(self.td)
        self.assertEqual(rules, allowlist.default_rules())
        self.assertTrue(allowlist.allowed("melt -version",
                                          directory=self.td))
        # موجودة أصلًا: لا تُستبدل.
        self._save([{"command": "ls"}])
        self.assertEqual(allowlist.ensure_allowlist(self.td),
                         [{"command": "ls"}])

    def test_invalid_rules_rejected(self):
        for bad in ({"command": ""}, {"command": "a b"},
                    {"command": "ls", "args": []},
                    {"command": "ls", "args": [[""]]},
                    "not-a-dict", {"no-command": "ls"}):
            with self.assertRaises(allowlist.AllowlistError, msg=bad):
                allowlist.validate_rule(bad)
        with self.assertRaises(allowlist.AllowlistError):
            allowlist.save_rules([{"command": ""}], self.td)
        path = os.path.join(self.td, "allowlist.json")
        self.assertFalse(os.path.exists(path),
                         "حفظ فاشل لا ينشئ ملفًا")


class TestAddRemove(AllowlistTestBase):
    def test_add_and_remove_rule(self):
        allowlist.add_rule({"command": "ls"}, self.td)
        self.assertTrue(allowlist.allowed("ls", directory=self.td))
        # إضافة قاعدة بنفس الأمر تستبدلها.
        allowlist.add_rule({"command": "ls", "args": [["-la"]]},
                           self.td)
        self.assertFalse(allowlist.allowed("ls", directory=self.td))
        self.assertTrue(allowlist.allowed("ls -la", directory=self.td))
        self.assertTrue(allowlist.remove_rule("ls", self.td))
        self.assertFalse(allowlist.allowed("ls -la", directory=self.td))
        self.assertFalse(allowlist.remove_rule("ls", self.td))

    def test_remove_empty_name_rejected(self):
        with self.assertRaises(allowlist.AllowlistError):
            allowlist.remove_rule("", self.td)


if __name__ == "__main__":
    unittest.main()
