#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات مفاتيح المزايا الموحدة (lib.features) —
جولة v0.1.63، بند 24 (ع7) + بند 23 (parallelRoomJobs).

تعمل بـ `env -u PYTHONNOUSERSITE python3 -m unittest
tests.test_features`. كل الكتابة في مجلدات مؤقتة — لا يُمس
ملف ``~/.qisas-studio/config.json`` الحقيقي. بلا شبكة.
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import features
from lib.features import FeatureError


def _config(tmpdir, content=None):
    path = os.path.join(tmpdir, "config.json")
    if content is not None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(content, handle)
    return path


class TestTriState(unittest.TestCase):
    def test_missing_is_not_false(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            self.assertIsNone(features.get("skillReview", path=path))
            self.assertFalse(features.is_set("skillReview", path=path))
            self.assertIsNone(features.get("skillReview", path=path))

    def test_false_differs_from_missing(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            features.set("skillReview", False, path=path)
            self.assertIs(features.get("skillReview", path=path), False)
            self.assertTrue(features.is_set("skillReview", path=path))

    def test_true_differs_from_false(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            features.set("skillReview", True, path=path)
            self.assertIs(features.get("skillReview", path=path), True)


class TestMergeNotReplace(unittest.TestCase):
    def test_set_merges_and_keeps_other_keys(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td, {"features": {"skillReview": True, "autoRecall": True},
                                "other": "kept"})
            features.set("roomMemoryCapture", False, path=path)
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            self.assertEqual(data["other"], "kept")
            self.assertIs(data["features"]["skillReview"], True)
            self.assertIs(data["features"]["autoRecall"], True)
            self.assertIs(data["features"]["roomMemoryCapture"], False)

    def test_set_makes_backup(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td, {"features": {"skillReview": True}})
            features.set("skillReview", False, path=path)
            with open(path + ".bak", encoding="utf-8") as handle:
                backup = json.load(handle)
            self.assertIs(backup["features"]["skillReview"], True)

    def test_written_file_is_0600(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            features.set("skillReview", True, path=path)
            mode = stat.S_IMODE(os.stat(path).st_mode)
            self.assertEqual(mode, 0o600)


class TestEnvOverride(unittest.TestCase):
    def test_env_1_and_0_win(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td, {"features": {"skillReview": False}})
            with mock.patch.dict(os.environ, {"QISAS_FEATURE_SKILLREVIEW": "1"}):
                self.assertIs(features.get("skillReview", path=path), True)
            with mock.patch.dict(os.environ, {"QISAS_FEATURE_SKILLREVIEW": "0"}):
                self.assertIs(features.get("skillReview", path=path), False)

    def test_other_env_strings_are_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td, {"features": {"skillReview": False}})
            for value in ("true", "yes", "2", "", "TRUE"):
                with mock.patch.dict(os.environ, {"QISAS_FEATURE_SKILLREVIEW": value}):
                    self.assertIs(
                        features.get("skillReview", path=path), False,
                        "القيمة %r يجب أن تُتجاهل" % value,
                    )

    def test_env_override_does_not_write_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            with mock.patch.dict(os.environ, {"QISAS_FEATURE_SKILLREVIEW": "1"}):
                self.assertIs(features.get("skillReview", path=path), True)
            self.assertFalse(os.path.exists(path))


class TestKnownKeyValidation(unittest.TestCase):
    def test_skill_review_steps_bounds(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            features.set("skillReviewSteps", 3, path=path)
            features.set("skillReviewSteps", 100, path=path)
            for bad in (2, 101, 0, "10", True):
                with self.assertRaises(FeatureError):
                    features.set("skillReviewSteps", bad, path=path)

    def test_share_learned_skills_values(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            for value in ("off", "ask", "auto"):
                features.set("shareLearnedSkills", value, path=path)
                self.assertEqual(
                    features.get("shareLearnedSkills", path=path), value
                )
            with self.assertRaises(FeatureError):
                features.set("shareLearnedSkills", "always", path=path)

    def test_bool_keys_reject_non_bool(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            with self.assertRaises(FeatureError):
                features.set("skillReview", "true", path=path)
            with self.assertRaises(FeatureError):
                features.set("skillReview", 1, path=path)


class TestDefaultsAndList(unittest.TestCase):
    def test_webhook_receiver_defaults_false(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            self.assertIs(features.get("webhookReceiver", default=False, path=path), False)
            listed = features.list_features(path=path)
            self.assertIs(listed["webhookReceiver"], False)

    def test_list_shows_unset_as_none(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            listed = features.list_features(path=path)
            self.assertIsNone(listed["skillReview"])
            self.assertIsNone(listed["skillReviewSteps"])
            self.assertIsNone(listed["autoRecall"])

    def test_corrupt_config_reads_as_empty(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "config.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{not json")
            self.assertIsNone(features.get("skillReview", path=path))
            features.set("skillReview", True, path=path)
            self.assertIs(features.get("skillReview", path=path), True)


class TestParallelRoomJobs(unittest.TestCase):
    def test_default_is_true(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            self.assertTrue(features.parallel_enabled(path=path))
            self.assertTrue(features.list_features(path=path)["parallelRoomJobs"])

    def test_false_means_sequential(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            features.set("parallelRoomJobs", False, path=path)
            self.assertFalse(features.parallel_enabled(path=path))

    def test_env_zero_disables(self):
        with tempfile.TemporaryDirectory() as td:
            path = _config(td)
            with mock.patch.dict(
                os.environ, {"QISAS_FEATURE_PARALLELROOMJOBS": "0"}
            ):
                self.assertFalse(features.parallel_enabled(path=path))
            with mock.patch.dict(
                os.environ, {"QISAS_FEATURE_PARALLELROOMJOBS": "1"}
            ):
                self.assertTrue(features.parallel_enabled(path=path))


class TestConfigPathResolution(unittest.TestCase):
    def test_default_path_is_under_home(self):
        path = features.config_path()
        self.assertTrue(path.endswith(os.path.join(".qisas-studio", "config.json")))

    def test_env_config_path_wins(self):
        with mock.patch.dict(os.environ, {"QISAS_CONFIG_PATH": "/tmp/x-test.json"}):
            self.assertEqual(features.config_path(), "/tmp/x-test.json")


if __name__ == "__main__":
    unittest.main()
