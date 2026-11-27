#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات دخان لأوامر الموجة ب (جولة v0.1.63).

كل أمر جديد: يقبل --help (خروج 0) ويعمل باستدعاء تجريبي
hermetic (HOME مؤقت، بلا شبكة، بلا كتابة خارج الشجرة — مجلد
runs مؤقت يُمرَّر عبر ترقيع load_config، وكل حالة ~/.qisas-studio
تحت HOME المؤقت).

التشغيل: env -u PYTHONNOUSERSITE python3 -m unittest tests.test_new_commands
"""
import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

import studio
from lib import request_flow


def _parse_json_stdout(text):
    """فسّر stdout كوثيقة JSON واحدة (يجب أن تكون سطرًا واحدًا)."""
    lines = [line for line in text.split("\n") if line.strip()]
    if len(lines) != 1:
        raise AssertionError(
            "المتوقع وثيقة JSON واحدة على stdout، وصل %d أسطر: %r"
            % (len(lines), text[:500]))
    return json.loads(lines[0])


class NewCommandsTest(unittest.TestCase):
    """بيئة hermetic مشتركة لكل اختبار دخان."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(
            prefix="test-new-commands-")
        self.addCleanup(self.tmp.cleanup)
        self.home = os.path.join(self.tmp.name, "home")
        os.makedirs(self.home)
        self.runs = os.path.join(self.tmp.name, "runs")
        os.makedirs(self.runs)
        self.videos = os.path.join(self.tmp.name, "videos")
        os.makedirs(self.videos)
        self.env_patch = mock.patch.dict(os.environ, {
            "HOME": self.home,
            "STUDIO_ENV_RESTORED": "1",
        })
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        base_cfg = studio.load_config()
        cfg = copy.deepcopy(base_cfg)
        cfg["paths"]["runs_dir"] = self.runs
        cfg["paths"]["videos_dir"] = self.videos
        self.cfg_patch = mock.patch.object(
            studio, "load_config", return_value=copy.deepcopy(cfg))
        self.cfg_patch.start()
        self.addCleanup(self.cfg_patch.stop)
        # بلا استعادة بيئة وبلا خادم OmniRoute في الاختبارات.
        self.env_ensure_patch = mock.patch.object(
            studio, "_ensure_environment", return_value=None)
        self.env_ensure_patch.start()
        self.addCleanup(self.env_ensure_patch.stop)

    def run_cli(self, argv):
        """شغّل main() بوسائط معطاة؛ ارجع (رمز الخروج، stdout، stderr)."""
        sys.argv = ["studio.py"] + list(argv)
        out, err = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(out), redirect_stderr(err):
                code = studio.main()
        except SystemExit as exc:
            code = exc.code
        return code, out.getvalue(), err.getvalue()

    def run_json(self, argv):
        """شغّل أمرًا بـ --json وارجع (رمز الخروج، القاموس)."""
        code, out, _err = self.run_cli(["--json"] + list(argv))
        return code, _parse_json_stdout(out)

    def run_help(self, argv):
        """شغّل أمرًا مع --help؛ ارجع رمز الخروج (SystemExit)."""
        sys.argv = ["studio.py"] + list(argv) + ["--help"]
        out, err = io.StringIO(), io.StringIO()
        try:
            with redirect_stdout(out), redirect_stderr(err):
                studio.main()
        except SystemExit as exc:
            return exc.code
        return None


HELP_CASES = [
    ["approval", "show"], ["approval", "set"],
    ["team", "apply"], ["team", "export"], ["team", "check"],
    ["routines", "ledger"], ["routines", "missed"],
    ["check-back", "add"], ["check-back", "list"],
    ["check-back", "cancel"],
    ["usage", "caps", "show"], ["usage", "caps", "set"],
    ["models", "list"], ["models", "health"],
    ["round-pack", "export"], ["round-pack", "import"],
    ["round-pack", "review"],
    ["handoffs", "list"],
    ["keys", "set"], ["keys", "test"], ["keys", "rotate"],
    ["keys", "list"],
    ["sentinel"],
    ["control"],
    ["inspect", "jobs"], ["inspect", "runs"],
    ["read-log"], ["search-log"],
    ["send-work"], ["wait-job"], ["interrupt-job"], ["switch-model"],
    ["wait"], ["events"],
    ["brief", "show"], ["brief", "dismiss"],
    ["workers", "pause"], ["workers", "resume"], ["workers", "stop"],
    ["export"],
    ["features", "list"], ["features", "set"],
    ["triage", "inbox"],
    ["recipe", "save"], ["recipe", "run"], ["recipe", "list"],
    ["webhook", "serve"], ["webhook", "token"],
    ["setup"],
    ["router", "test"],
]


class HelpTest(NewCommandsTest):
    """كل أمر جديد يقبل --help (خروج 0)."""

    def test_all_new_commands_accept_help(self):
        for argv in HELP_CASES:
            with self.subTest(argv=argv):
                self.assertEqual(self.run_help(argv), 0)

    def test_root_and_doctor_help_subprocess(self):
        env = dict(os.environ)
        env["HOME"] = self.home
        env["STUDIO_ENV_RESTORED"] = "1"
        studio_py = os.path.join(studio.STUDIO_DIR, "studio.py")
        for argv in (["--help"], ["doctor", "--help"],
                     ["approval", "show", "--help"]):
            with self.subTest(argv=argv):
                proc = subprocess.run(
                    [sys.executable, studio_py] + argv,
                    capture_output=True, text=True, env=env, timeout=120)
                self.assertEqual(proc.returncode, 0)


class ApprovalTeamTest(NewCommandsTest):
    def test_approval_show_set_json(self):
        code, data = self.run_json(["approval", "show"])
        self.assertEqual(code, 0)
        self.assertTrue(data["ok"])
        self.assertEqual(data["level"], "ask")
        code, out, _err = self.run_cli(
            ["approval", "set", "--level", "auto"])
        self.assertEqual(code, 0)
        code, data = self.run_json(["approval", "show"])
        self.assertEqual(data["level"], "auto")

    def test_team_check_apply_export(self):
        team_file = os.path.join(studio.STUDIO_DIR,
                                 "examples", "team.yaml")
        code, _out, _err = self.run_cli(["team", "check", team_file])
        self.assertEqual(code, 6)
        code, _out, _err = self.run_cli(
            ["team", "apply", "--dry-run", team_file])
        self.assertEqual(code, 0)
        code, _out, _err = self.run_cli(["team", "apply", team_file])
        self.assertEqual(code, 0)
        code, out, _err = self.run_cli(["team", "apply", team_file])
        self.assertEqual(code, 0)
        self.assertIn("No changes.", out)
        code, data = self.run_json(["team", "export"])
        self.assertEqual(code, 0)
        self.assertEqual(len(data["teams"]), 1)
        self.assertEqual(len(data["bots"]), 3)


class RoutinesCheckBackUsageTest(NewCommandsTest):
    def test_routines_ledger_and_missed_empty(self):
        code, data = self.run_json(["routines", "ledger"])
        self.assertEqual(code, 0)
        self.assertEqual(data["count"], 0)
        code, data = self.run_json(["routines", "missed"])
        self.assertEqual(code, 0)
        self.assertEqual(data["collapsed"], 0)

    def test_check_back_add_list_cancel(self):
        code, data = self.run_json([
            "check-back", "add", "--run-id", "r1", "--worker", "w1",
            "--in-minutes", "5"])
        self.assertEqual(code, 0)
        check_id = data["check_back"]["id"]
        code, data = self.run_json(["check-back", "list"])
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["pending"], 1)
        code, _out, _err = self.run_cli(
            ["check-back", "cancel", "--id", check_id])
        self.assertEqual(code, 0)
        code, data = self.run_json(
            ["check-back", "list", "--status", "cancelled"])
        self.assertEqual(data["count"], 1)
        code, _out, _err = self.run_cli(
            ["check-back", "cancel", "--id", "nope"])
        self.assertEqual(code, 7)

    def test_usage_caps_show_set(self):
        code, data = self.run_json(["usage", "caps", "show"])
        self.assertEqual(code, 0)
        self.assertEqual(data["caps"]["stops"], "unattended")
        code, _out, _err = self.run_cli(
            ["usage", "caps", "set", "--daily-usd", "5"])
        self.assertEqual(code, 0)
        code, data = self.run_json(["usage", "caps", "show"])
        self.assertEqual(data["caps"]["dailyUsd"], 5)


class ModelsPacksHandoffsTest(NewCommandsTest):
    def test_models_list_health(self):
        code, data = self.run_json(["models", "list"])
        self.assertEqual(code, 0)
        self.assertIn("gemini-flash-lite", data["drivers"])
        code, data = self.run_json(["models", "health"])
        self.assertEqual(code, 0)
        self.assertIn("gemini", data["health"])

    def test_round_pack_export_review_import(self):
        pack_dir = os.path.join(self.tmp.name, "pack")
        os.makedirs(pack_dir)
        with open(os.path.join(pack_dir, "note.txt"),
                  "w", encoding="utf-8") as fh:
            fh.write("hello pack\n")
        pack_path = os.path.join(self.tmp.name, "p1.md")
        code, data = self.run_json([
            "round-pack", "export", "--dir", pack_dir,
            "--file", "note.txt", "--name", "t1",
            "--version", "0.1.63", "--out", pack_path])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(pack_path))
        code, data = self.run_json(
            ["round-pack", "review", "--pack", pack_path])
        self.assertEqual(code, 0)
        self.assertTrue(data["ok"])
        dest = os.path.join(self.tmp.name, "imp")
        code, data = self.run_json([
            "round-pack", "import", "--pack", pack_path,
            "--dest", dest])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(
            os.path.join(dest, "note.txt")))

    def test_handoffs_send_work_list(self):
        code, data = self.run_json(["handoffs", "list"])
        self.assertEqual(code, 0)
        self.assertEqual(data["count"], 0)
        code, data = self.run_json(
            ["send-work", "--title", "اختبار"])
        self.assertEqual(code, 0)
        self.assertEqual(data["delivery"]["state"], "source")
        code, data = self.run_json(["handoffs", "list"])
        self.assertEqual(data["count"], 1)


class KeysTest(NewCommandsTest):
    def setUp(self):
        super().setUp()
        self.token_file = os.path.join(self.tmp.name, "tok.txt")
        with open(self.token_file, "w", encoding="utf-8") as fh:
            fh.write("AIza" + "x" * 35 + "\n")

    def test_keys_set_test_rotate_list(self):
        code, data = self.run_json([
            "keys", "set", "--name", "gemini",
            "--token-file", self.token_file])
        self.assertEqual(code, 0)
        self.assertEqual(data["key"]["name"], "gemini")
        code, data = self.run_json([
            "keys", "test", "--provider", "gemini",
            "--token-file", self.token_file])
        self.assertEqual(code, 0)
        self.assertTrue(data["ok"])
        code, _out, _err = self.run_cli([
            "keys", "rotate", "--name", "gemini",
            "--token-file", self.token_file])
        self.assertEqual(code, 0)
        code, out, _err = self.run_cli(["keys", "list"])
        self.assertEqual(code, 0)
        self.assertIn("gemini", out)
        self.assertNotIn("AIza", out)

    def test_keys_set_rejects_token_flag(self):
        code, _out, err = self.run_cli([
            "keys", "set", "--name", "gemini", "--token", "AIza" + "x" * 35,
            "--token-file", self.token_file])
        self.assertEqual(code, 2)
        self.assertIn("--token-file", err + _out)

    def test_keys_rotate_missing_returns_7(self):
        code, _out, _err = self.run_cli([
            "keys", "rotate", "--name", "nope",
            "--token-file", self.token_file])
        self.assertEqual(code, 7)


class SentinelControlInspectTest(NewCommandsTest):
    def test_sentinel_runs(self):
        data_dir = os.path.join(self.tmp.name, "data")
        os.makedirs(os.path.join(data_dir, "runs"))
        out_dir = os.path.join(self.tmp.name, "sentinel-out")
        code, data = self.run_json([
            "sentinel", "--data-dir", data_dir,
            "--out", out_dir])
        self.assertEqual(code, 0)
        self.assertIn("total_issues", data)
        self.assertIn("out_dir", data)

    def test_sentinel_rejects_out_inside_data(self):
        code, _out, _err = self.run_cli([
            "sentinel", "--data-dir", self.tmp.name,
            "--out", os.path.join(self.tmp.name, "inside")])
        self.assertEqual(code, 2)

    def test_control_read_and_mutating_refusal(self):
        code, data = self.run_json(["control", "inspect"])
        self.assertEqual(code, 0)
        self.assertEqual(data["verb"], "inspect")
        code, _out, _err = self.run_cli(["control", "publish"])
        self.assertEqual(code, 2)
        code, _out, _err = self.run_cli(["control", "bogus"])
        self.assertEqual(code, 2)

    def test_inspect_jobs_runs(self):
        code, data = self.run_json(["inspect", "jobs"])
        self.assertEqual(code, 0)
        self.assertEqual(data["count"], 0)
        code, data = self.run_json(["inspect", "runs"])
        self.assertEqual(code, 0)
        self.assertEqual(data["count"], 0)


class LogsJobsTest(NewCommandsTest):
    def setUp(self):
        super().setUp()
        from lib import job_registry as _jr
        from lib import log_reader as _lr
        self.done_job = _jr.register_job(
            self.runs, "run", story="anza", title="test-job")
        _jr.update_job(self.runs, self.done_job["job_id"],
                       status="done")
        self.running_job = _jr.register_job(
            self.runs, "run", story="anza", title="run-job")
        _lr.append_job_event(self.runs, self.done_job["job_id"],
                             {"kind": "completed"})
        self.log_file = os.path.join(self.tmp.name, "test.log")
        with open(self.log_file, "w", encoding="utf-8") as fh:
            fh.write('{"level": "info", "msg": "hello world"}\n')
            fh.write("plain line hello\n")

    def test_read_search_log(self):
        code, data = self.run_json(
            ["read-log", "--file", self.log_file])
        self.assertEqual(code, 0)
        self.assertEqual(data["count"], 2)
        code, data = self.run_json([
            "search-log", "--file", self.log_file, "--query", "hello"])
        self.assertEqual(code, 0)
        self.assertEqual(data["count"], 2)
        code, _out, _err = self.run_cli(
            ["read-log", "--file",
             os.path.join(self.tmp.name, "nope.log")])
        self.assertEqual(code, 7)

    def test_wait_job_done_and_missing(self):
        code, data = self.run_json([
            "wait-job", "--job-id", self.done_job["job_id"],
            "--timeout", "5", "--poll", "0.1"])
        self.assertEqual(code, 0)
        self.assertEqual(data["outcome"], "settled")
        code, _out, _err = self.run_cli(
            ["wait-job", "--job-id", "nope",
             "--timeout", "1", "--poll", "0.1"])
        self.assertEqual(code, 7)

    def test_wait_and_events(self):
        code, data = self.run_json([
            "wait", "--job-id", self.done_job["job_id"],
            "--timeout", "5", "--poll", "0.1"])
        self.assertEqual(code, 0)
        self.assertEqual(data["outcome"], "settled")
        code, data = self.run_json(
            ["events", "--job-id", self.done_job["job_id"]])
        self.assertEqual(code, 0)
        self.assertEqual(data["count"], 1)

    def test_interrupt_job_and_export(self):
        code, data = self.run_json([
            "interrupt-job", "--job-id", self.running_job["job_id"]])
        self.assertEqual(code, 0)
        self.assertEqual(data["changed"], 1)
        code, _out, _err = self.run_cli(
            ["interrupt-job", "--job-id", "nope"])
        self.assertEqual(code, 7)
        out_dir = os.path.join(self.tmp.name, "exp")
        code, _out, _err = self.run_cli([
            "export", "--job", self.done_job["job_id"],
            "--out", out_dir])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(
            os.path.join(out_dir, "manifest.json")))

    def test_switch_model_known_and_unknown(self):
        code, data = self.run_json(
            ["switch-model", "--model", "gemini-flash-lite"])
        self.assertEqual(code, 0)
        self.assertEqual(data["model"], "gemini-flash-lite")
        code, _out, _err = self.run_cli(
            ["switch-model", "--model", "no-such-driver"])
        self.assertEqual(code, 7)


class BriefWorkersFeaturesTest(NewCommandsTest):
    def test_brief_show_and_dismiss(self):
        code, data = self.run_json(["brief", "show"])
        self.assertEqual(code, 0)
        self.assertTrue(data["empty"])
        code, _out, _err = self.run_cli([
            "brief", "dismiss", "--row-id", "x",
            "--owner", "a", "--thread-owner", "a"])
        self.assertEqual(code, 7)
        code, _out, _err = self.run_cli([
            "brief", "dismiss", "--row-id", "x",
            "--owner", "a", "--thread-owner", "b"])
        self.assertEqual(code, 5)

    def test_workers_pause_resume_stop(self):
        code, data = self.run_json(
            ["workers", "pause", "--worker", "w1"])
        self.assertEqual(code, 0)
        self.assertEqual(data["workers"][0]["state"], "paused")
        code, data = self.run_json(
            ["workers", "resume", "--worker", "w1"])
        self.assertEqual(data["workers"][0]["state"], "active")
        code, data = self.run_json(
            ["workers", "stop", "--worker", "w1"])
        self.assertEqual(data["workers"][0]["state"], "stopped")
        code, _out, _err = self.run_cli(
            ["workers", "resume", "--worker", "w1"])
        self.assertEqual(code, 1)

    def test_features_list_set(self):
        code, data = self.run_json(["features", "list"])
        self.assertEqual(code, 0)
        self.assertTrue(data["features"]["parallelRoomJobs"])
        code, data = self.run_json([
            "features", "set", "--name", "skillReview",
            "--value", "true"])
        self.assertEqual(code, 0)
        self.assertTrue(data["value"])


class TriageRecipeWebhookTest(NewCommandsTest):
    def test_triage_inbox_with_fake_client(self):
        from lib import inbox_triage as _triage

        class _FakeClient:
            def chat(self, prompt, model, max_tokens=300,
                     temperature=0.0):
                if "قرر مصير" in prompt:
                    return ('{"decision": "تخطٍّ", '
                            '"reason": "تجربة"}')
                return ('{"sender": null, "request": "سؤال عن قصة", '
                        '"deadline": null, "amount": null, '
                        '"awaits_reply": false, "kind": "سؤال"}')

        with mock.patch.object(
                _triage, "_default_client",
                return_value=_FakeClient()):
            code, data = self.run_json(
                ["triage", "inbox", "--text", "مرحبًا، هل توجد قصة؟"])
        self.assertEqual(code, 0)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["status"], "تخطٍّ")

    def test_recipe_save_run_list(self):
        recipes_dir = os.path.join(self.tmp.name, "recipes")
        code, _out, _err = self.run_cli([
            "recipe", "save", "--dir", recipes_dir,
            "--name", "تجربة", "--step", "قول: echo hello"])
        self.assertEqual(code, 0)
        code, data = self.run_json(
            ["recipe", "list", "--dir", recipes_dir])
        self.assertEqual(code, 0)
        self.assertEqual(data["count"], 1)
        code, data = self.run_json([
            "recipe", "run", "--dir", recipes_dir,
            "--name", "تجربة", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertTrue(data["ok"])
        code, data = self.run_json([
            "recipe", "run", "--dir", recipes_dir,
            "--name", "تجربة"])
        self.assertEqual(code, 0)
        self.assertTrue(data["ok"])

    def test_webhook_serve_refused_when_disabled(self):
        code, out, err = self.run_cli(["webhook", "serve"])
        self.assertEqual(code, 5)
        self.assertIn("features set webhookReceiver", out + err)

    def test_webhook_token_shown_once(self):
        code, out, _err = self.run_cli(["webhook", "token"])
        self.assertEqual(code, 0)
        lines = [line.strip() for line in out.split("\n")
                 if line.strip()]
        token = lines[1]
        self.assertGreaterEqual(len(token), 20)
        token_path = os.path.join(self.home, ".qisas-studio",
                                  "webhook-token.json")
        with open(token_path, encoding="utf-8") as fh:
            stored = json.load(fh)
        self.assertIn("token_sha256", stored)
        self.assertNotIn(token, json.dumps(stored))


class SetupRouterDoctorTest(NewCommandsTest):
    def test_setup_first_run(self):
        code, data = self.run_json(["setup"])
        self.assertEqual(code, 0)
        self.assertFalse(data["already_setup"])
        code, data = self.run_json(["setup"])
        self.assertTrue(data["already_setup"])

    def test_router_test_fallback(self):
        code, data = self.run_json(
            ["router", "test", "--task", "اختبار"])
        self.assertEqual(code, 0)
        self.assertEqual(data["source"], "fallback")
        self.assertEqual(data["reason"], "no_choice")

    def test_doctor_json_structure(self):
        code, out, _err = self.run_cli(["doctor", "--json"])
        self.assertIn(code, (0, 7))
        data = json.loads(out)
        self.assertIn("ok", data)
        self.assertIn("problems", data)
        self.assertIn("warnings", data)
        self.assertIn("checks", data)
        self.assertGreater(len(data["checks"]), 0)
        for check in data["checks"]:
            self.assertIn("id", check)
            self.assertIn(check["status"], ("pass", "fail", "warn"))
            self.assertIn("message", check)
            self.assertIn("fix", check)
            if check["status"] == "fail":
                self.assertTrue(check["fix"])
        if data["problems"]:
            self.assertEqual(code, 7)
        else:
            self.assertEqual(code, 0)

    def test_root_json_and_quiet_flags(self):
        code, data = self.run_json(["approval", "show"])
        self.assertEqual(code, 0)
        self.assertTrue(data["ok"])
        code, _out, _err = self.run_cli(
            ["--quiet", "approval", "show"])
        self.assertEqual(code, 0)


class RequestExitCodesTest(NewCommandsTest):
    """ربط رموز الخروج في أمر request (ملاحظة W11a).

    استثناء يحمل .exit_code يرجع قيمته بدل 1؛ وUsageCapError
    يرجع 1 مع طباعة الحالة والرمز spend_cap (لا 4: ع1 يعني
    بـ4 «يحتاج تسجيل دخول/مهلة» لا «بُلغ حد إنفاق»).
    """

    def _run_request_with_error(self, error):
        with mock.patch.object(
                studio.star_gate_lib, "check_star_gate",
                return_value=True), \
                mock.patch.object(
                    studio.request_flow, "request_to_run",
                    side_effect=error):
            return self.run_cli(["request", "قصة تجريبية"])

    def test_request_approval_denied_returns_5(self):
        code, _out, _err = self._run_request_with_error(
            request_flow.ApprovalBlockedError(
                "بوابة الموافقة رفضت الفعل", exit_code=5))
        self.assertEqual(code, 5)

    def test_request_approval_pending_returns_3(self):
        code, _out, _err = self._run_request_with_error(
            request_flow.ApprovalBlockedError(
                "يحتاج موافقة بشرية", exit_code=3))
        self.assertEqual(code, 3)

    def test_request_usage_cap_returns_1_with_status(self):
        code, out, _err = self._run_request_with_error(
            request_flow.UsageCapError(
                "بُلغ حد الاستخدام", status=429, retry_after=60,
                code="spend_cap"))
        self.assertEqual(code, 1)
        self.assertIn("429", out)
        self.assertIn("spend_cap", out)

    def test_request_plain_error_returns_1(self):
        code, _out, _err = self._run_request_with_error(
            request_flow.RequestFlowError("فشل عام"))
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
