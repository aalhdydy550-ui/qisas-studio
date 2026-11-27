#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات ملف الفريق الإعلاني (lib.team_file) —
جولة v0.1.63، بند 4 (ع17) + بند 31 (سقوف القوائم).

تعمل بـ `env -u PYTHONNOUSERSITE python3 -m unittest
tests.test_team_file`. كل الكتابة في مجلدات مؤقتة — بلا شبكة،
وبلا ملفات خارج الشجرة (حارس skip-if-absent عند غياب ملف
اختياري مثل مثال الفريق).
"""
import copy
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import team_file
from lib.team_file import TeamApplyError, TeamFileError


def _bot(name, team="crew", **extra):
    bot = {"name": name, "team": team, "model": "gemini/gemini-3-flash-preview"}
    bot.update(extra)
    return bot


def _data(bots, teams=None):
    data = {"bots": bots}
    if teams is not None:
        data["teams"] = teams
    return data


def _team(name, **extra):
    team = {"name": name}
    team.update(extra)
    return team


class TestConstants(unittest.TestCase):
    def test_roster_caps(self):
        self.assertEqual(team_file.ROSTER_MAX_BOTS, 40)
        self.assertEqual(team_file.OTHERS_MIN_BOTS, 8)


class TestExampleFile(unittest.TestCase):
    def test_example_parses_with_three_roles(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "team.yaml",
        )
        if not os.path.isfile(path):
            self.skipTest("ملف مثال الفريق غائب")
        data = team_file.load_team_file(path)
        self.assertEqual(len(data["bots"]), 3)
        names = {b["name"] for b in data["bots"]}
        self.assertEqual(names, {"doctor", "narrator", "publisher"})
        # النماذج كلها بصيغة INSTANCE/MODEL.
        for bot in data["bots"]:
            self.assertIn("/", bot["model"])

    def test_example_validates_with_local_cwd(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "team.yaml",
        )
        if not os.path.isfile(path):
            self.skipTest("ملف مثال الفريق غائب")
        data = team_file.load_team_file(path)
        with tempfile.TemporaryDirectory() as td:
            for bot in data["bots"]:
                bot["cwd"] = td
            self.assertEqual(team_file.validate_all(data), [])


class TestPlanApplyIdempotent(unittest.TestCase):
    def test_plan_then_apply_then_no_changes(self):
        data = _data(
            [_bot("doctor", chief=True), _bot("narrator")],
            teams=[_team("crew")],
        )
        state = team_file.empty_state()
        planned = team_file.plan(data, state)
        self.assertTrue(planned["changed"])
        self.assertEqual(len(planned["actions"]), 3)  # فريق + بوتان
        result = team_file.apply(data, state)
        self.assertTrue(result["changed"])
        self.assertEqual(len(result["applied"]), 3)
        # إعادة التطبيق بلا تغييرات.
        again = team_file.apply(data, result["state"])
        self.assertFalse(again["changed"])
        self.assertEqual(again["message"], team_file.NO_CHANGES_MESSAGE)
        self.assertEqual(again["applied"], [])

    def test_dry_run_changes_nothing(self):
        data = _data([_bot("doctor")], teams=[_team("crew")])
        state = team_file.empty_state()
        result = team_file.apply(data, state, dry_run=True)
        self.assertTrue(result["changed"])
        self.assertEqual(result["state"]["bots"], {})
        self.assertEqual(result["state"]["teams"], {})

    def test_check_exit_semantics(self):
        data = _data([_bot("doctor")], teams=[_team("crew")])
        state = team_file.empty_state()
        self.assertTrue(team_file.check(data, state))  # سيتغيّر → خروج 6
        applied = team_file.apply(data, state)
        self.assertFalse(team_file.check(data, applied["state"]))

    def test_field_left_out_is_left_as_is(self):
        data = _data([_bot("doctor", effort="low")], teams=[_team("crew")])
        result = team_file.apply(data, team_file.empty_state())
        # تحديث بلا حقل effort: يبقى low، ويتغيّر العنوان فقط.
        update = _data(
            [_bot("doctor", title="طبيب جديد")], teams=[_team("crew")]
        )
        planned = team_file.plan(update, result["state"])
        self.assertEqual(len(planned["actions"]), 1)
        self.assertEqual(planned["actions"][0]["changes"], ["title"])
        applied = team_file.apply(update, result["state"])
        bot = applied["state"]["bots"]["doctor"]
        self.assertEqual(bot["effort"], "low")
        self.assertEqual(bot["title"], "طبيب جديد")


class TestRename(unittest.TestCase):
    def test_rename_via_was(self):
        data = _data([_bot("doctor")], teams=[_team("crew")])
        result = team_file.apply(data, team_file.empty_state())
        renamed = _data(
            [_bot("scribe", was="doctor")], teams=[_team("crew")]
        )
        applied = team_file.apply(renamed, result["state"])
        self.assertIn("scribe", applied["state"]["bots"])
        self.assertNotIn("doctor", applied["state"]["bots"])

    def test_rename_over_existing_name_rejected(self):
        data = _data(
            [_bot("doctor"), _bot("scribe")], teams=[_team("crew")]
        )
        result = team_file.apply(data, team_file.empty_state())
        clash = _data(
            [_bot("scribe", was="doctor")], teams=[_team("crew")]
        )
        with self.assertRaises(TeamFileError):
            team_file.plan(clash, result["state"])

    def test_case_insensitive_matching(self):
        data = _data([_bot("Doctor")], teams=[_team("crew")])
        result = team_file.apply(data, team_file.empty_state())
        update = _data(
            [_bot("DOCTOR", title="جديد")], teams=[_team("crew")]
        )
        applied = team_file.apply(update, result["state"])
        self.assertEqual(len(applied["state"]["bots"]), 1)


class TestValidation(unittest.TestCase):
    def test_unknown_field_rejected(self):
        errors = team_file.validate_all(_data([_bot("a", wizard=True)]))
        self.assertTrue(any("مجهولة" in e for e in errors))
        with self.assertRaises(TeamFileError):
            team_file.validate(_data([_bot("a", wizard=True)]))

    def test_duplicate_bot_name_rejected(self):
        errors = team_file.validate_all(
            _data([_bot("a"), _bot("A")], teams=[_team("crew")])
        )
        self.assertTrue(any("مكرر" in e for e in errors))

    def test_two_chiefs_rejected(self):
        errors = team_file.validate_all(
            _data(
                [_bot("a", chief=True), _bot("b", chief=True)],
                teams=[_team("crew")],
            )
        )
        self.assertTrue(any("رئيسان" in e for e in errors))

    def test_model_without_instance_rejected(self):
        errors = team_file.validate_all(
            _data([_bot("a", model="gemini-3-flash-preview")])
        )
        self.assertTrue(any("النموذج" in e for e in errors))

    def test_computer_browser_rejected_in_v1(self):
        errors = team_file.validate_all(
            _data([_bot("a", computer="browser")])
        )
        self.assertTrue(any("الحاسوب" in e for e in errors))
        for ok in ("local", "off"):
            self.assertEqual(
                team_file.validate_all(_data([_bot("a", computer=ok)])), []
            )

    def test_cwd_tilde_rejected_and_missing_rejected(self):
        errors = team_file.validate_all(
            _data([_bot("a", cwd="~/studio")])
        )
        self.assertTrue(any("~" in e for e in errors))
        errors = team_file.validate_all(
            _data([_bot("a", cwd="/no-such-dir-xyz")])
        )
        self.assertTrue(any("غير موجود" in e for e in errors))

    def test_cwd_relative_rejected(self):
        errors = team_file.validate_all(
            _data([_bot("a", cwd="studio")])
        )
        self.assertTrue(any("كامل" in e for e in errors))

    def test_soul_over_24k_bytes_rejected(self):
        errors = team_file.validate_all(
            _data([_bot("a", soul="س" * 13000)])
        )
        self.assertTrue(any("soul" in e for e in errors))

    def test_name_length_bounds(self):
        errors = team_file.validate_all(_data([_bot("")]))
        self.assertTrue(errors)
        errors = team_file.validate_all(_data([_bot("x" * 101)]))
        self.assertTrue(errors)

    def test_partial_wildcard_tools_rejected(self):
        errors = team_file.validate_all(
            _data([_bot("a", tools={"allow": ["native:read*"]})])
        )
        self.assertTrue(any("باطل" in e for e in errors))

    def test_malformed_yaml_rejected(self):
        with self.assertRaises(TeamFileError) as ctx:
            team_file.parse_team_text("bots: [unclosed")
        self.assertEqual(ctx.exception.exit_code, 8)


class TestSecrets(unittest.TestCase):
    def test_plain_key_rejected_with_exit_2(self):
        data = _data([_bot("a", key="sk-abcdef")])
        with self.assertRaises(TeamFileError) as ctx:
            team_file.validate(data)
        self.assertEqual(ctx.exception.exit_code, 2)
        self.assertIn("key", str(ctx.exception))

    def test_env_and_file_refs_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            data = _data([
                _bot("a", key={"env": "GEMINI_API_KEY"}),
                _bot("b", key={"file": os.path.join(td, "key.txt")}),
            ])
            self.assertEqual(team_file.validate_all(data), [])

    def test_malformed_ref_rejected(self):
        data = _data([_bot("a", key={"env": "bad-name!"})])
        errors = team_file.validate_all(data)
        self.assertTrue(any("مرجع سرّي" in e for e in errors))
        data = _data([_bot("a", key={"env": "X", "file": "/tmp/k"})])
        errors = team_file.validate_all(data)
        self.assertTrue(any("مرجع سرّي" in e for e in errors))


class TestPrune(unittest.TestCase):
    def _seed(self):
        data = _data(
            [_bot("a"), _bot("b")],
            teams=[_team("crew", prune=True), _team("other")],
        )
        return team_file.apply(data, team_file.empty_state())["state"]

    def test_no_prune_keeps_unlisted_bots(self):
        state = self._seed()
        data = _data([_bot("a")], teams=[_team("crew", prune=True)])
        result = team_file.apply(data, state, prune=False)
        self.assertIn("b", result["state"]["bots"])

    def test_prune_deletes_only_in_prune_team(self):
        state = self._seed()
        # انقل b إلى فريق غير موسوم prune.
        state["bots"]["b"]["team"] = "other"
        data = _data([_bot("a")], teams=[_team("crew", prune=True)])
        result = team_file.apply(data, state, prune=True)
        self.assertIn("b", result["state"]["bots"])
        # وأعده إلى crew: يُحذف الآن.
        state["bots"]["b"]["team"] = "crew"
        result = team_file.apply(data, state, prune=True)
        self.assertNotIn("b", result["state"]["bots"])
        self.assertIn("a", result["state"]["bots"])

    def test_teams_never_deleted(self):
        state = self._seed()
        data = _data([_bot("a")], teams=[_team("crew", prune=True)])
        result = team_file.apply(data, state, prune=True)
        self.assertIn("crew", result["state"]["teams"])
        self.assertIn("other", result["state"]["teams"])


class TestRosterCap(unittest.TestCase):
    def test_41_bots_rejected(self):
        bots = [_bot("bot%d" % i) for i in range(41)]
        errors = team_file.validate_all(_data(bots))
        self.assertTrue(any("40" in e for e in errors))

    def test_40_bots_accepted(self):
        bots = [_bot("bot%d" % i) for i in range(40)]
        self.assertEqual(team_file.validate_all(_data(bots)), [])

    def test_apply_beyond_cap_rejected(self):
        bots = [_bot("bot%d" % i) for i in range(40)]
        state = team_file.apply(_data(bots), team_file.empty_state())["state"]
        with self.assertRaises(TeamFileError):
            team_file.plan(_data([_bot("extra")]), state)


class TestNotAtomicAndBusy(unittest.TestCase):
    def _two_bot_data(self, **extra_b):
        bots = [_bot("a", title="أول"), _bot("b", title="ثانٍ", **extra_b)]
        return _data(bots, teams=[_team("crew")])

    def test_stop_at_refusal_then_resume(self):
        state = team_file.apply(
            self._two_bot_data(), team_file.empty_state()
        )["state"]
        update = _data(
            [_bot("a", title="أول جديد"), _bot("b", title="ثانٍ جديد")],
            teams=[_team("crew")],
        )
        busy = {"b"}
        with self.assertRaises(TeamApplyError) as ctx:
            team_file.apply(
                update, state,
                wait_idle_seconds=0,
                busy_check=lambda name: name in busy,
            )
        self.assertEqual(len(ctx.exception.applied), 1)
        partial = ctx.exception.state
        self.assertEqual(partial["bots"]["a"]["title"], "أول جديد")
        self.assertEqual(partial["bots"]["b"]["title"], "ثانٍ")
        # إعادة التطبيق تكمل من حيث توقف.
        done = team_file.apply(update, partial)
        self.assertEqual(done["state"]["bots"]["b"]["title"], "ثانٍ جديد")

    def test_busy_bot_waits_until_idle(self):
        state = team_file.apply(
            self._two_bot_data(), team_file.empty_state()
        )["state"]
        update = _data(
            [_bot("a", title="جديد")], teams=[_team("crew")]
        )
        calls = {"n": 0}

        def busy_check(name):
            calls["n"] += 1
            return calls["n"] <= 2

        result = team_file.apply(
            update, state, wait_idle_seconds=120, busy_check=busy_check
        )
        self.assertEqual(result["state"]["bots"]["a"]["title"], "جديد")


class TestExport(unittest.TestCase):
    def test_export_roundtrip(self):
        data = _data([_bot("a")], teams=[_team("crew")])
        state = team_file.apply(data, team_file.empty_state())["state"]
        exported = team_file.export_state(state)
        self.assertEqual(len(exported["bots"]), 1)
        self.assertEqual(len(exported["teams"]), 1)
        self.assertEqual(team_file.validate_all(exported), [])


if __name__ == "__main__":
    unittest.main()
