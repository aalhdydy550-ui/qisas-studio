#!/usr/bin/env python3
"""اختبارات الاستئناف بعد الانهيار — جولة v0.1.41 (بند 6 من
استخراج AlphaCLI). على مجلدات مؤقتة في /tmp فقط — بلا لمس
للطابور الحقيقي أو المنشورات أو بيانات العملاء."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import run_record, run_resume, runlog


def _begin(td, run_id="anza-20261123-090000", command="run"):
    settings = run_record.resolve_settings(
        {}, {"story": "anza", "project": "anza-part1",
             "backend": "concat"})
    return run_record.begin_record(td, command, settings, run_id=run_id)


def _inputs(run_dir):
    return {"story": "anza", "project": "anza-part1",
            "backend": "concat",
            "out_path": "/tmp/out/anza-part1.mp4",
            "watermark": True, "grade": None, "cards_dir": None,
            "lang": "ar", "allow_fallback": True,
            "run_dir": run_dir}


def _write_script(run_dir, title="العنزة التي أنقذت القرية"):
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "script-ai.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"title": title, "caption": "قصة حقيقية",
                   "source": "omniroute"}, fh, ensure_ascii=False)


def _write_manifest(run_dir):
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "manifest.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"images": ["a.png", "b.png"], "phrases": ["x", "y"]},
                  fh, ensure_ascii=False)


def _rewrite_record(path, **fields):
    with open(path, encoding="utf-8") as fh:
        record = json.load(fh)
    record.update(fields)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2)


class TestSaveCheckpoint(unittest.TestCase):
    def test_checkpoint_fields_and_order(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            cp = run_record.save_checkpoint(
                path, "produce", inputs={"story": "anza"},
                outputs={"manifest_file": "manifest.json",
                         "images": 2}, note="بعد الإنتاج")
            self.assertEqual(cp["step"], "produce")
            self.assertEqual(cp["completed"], ["script", "produce"])
            self.assertEqual(cp["outputs"]["images"], 2)
            self.assertIn("saved_at", cp)
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
            self.assertEqual(record["checkpoint"]["step"], "produce")
            self.assertEqual(record["status"], "running")

    def test_begin_record_carries_checkpoint_pid_boot(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
            self.assertIsNone(record["checkpoint"])
            self.assertEqual(record["pid"], os.getpid())
            self.assertEqual(record["boot_id"],
                             run_record.current_boot_id())

    def test_unknown_step_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            with self.assertRaises(ValueError):
                run_record.save_checkpoint(path, "render")

    def test_missing_record_raises(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                run_record.save_checkpoint(
                    os.path.join(td, "nope.json"), "script")

    def test_checkpoint_survives_finish(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            run_record.save_checkpoint(path, "script")
            finished = run_record.finish_record(
                path, "done", outputs=["/tmp/out.mp4"])
            self.assertEqual(finished["checkpoint"]["step"], "script")
            self.assertEqual(finished["status"], "done")


class TestMarkCrashed(unittest.TestCase):
    def test_running_becomes_crashed_keeping_checkpoint(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            run_record.save_checkpoint(path, "script",
                                       outputs={"title": "العنزة"})
            rec = run_record.mark_crashed(path, error="انقطع التيار")
            self.assertEqual(rec["status"], "crashed")
            self.assertIn("انقطع التيار", rec["error"])
            self.assertEqual(rec["checkpoint"]["step"], "script")
            self.assertIn("finished_at", rec)

    def test_terminal_status_not_remarked(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            run_record.finish_record(path, "done")
            rec = run_record.mark_crashed(path, error="متأخر")
            self.assertEqual(rec["status"], "done")
            self.assertIsNone(rec.get("error"))

    def test_missing_file_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(run_record.mark_crashed(
                os.path.join(td, "nope.json")))


class TestDetectCrashed(unittest.TestCase):
    def test_boot_changed_means_crashed(self):
        # محاكاة ريستارت VM: boot_id في السجل يختلف عن الحالي.
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            _rewrite_record(path, boot_id="boot-id-قديم-قبل-الريستارت")
            crashed = run_record.detect_crashed(td)
            self.assertEqual(len(crashed), 1)
            self.assertEqual(crashed[0][1]["status"], "crashed")
            self.assertIn("boot-changed", crashed[0][1]["error"])

    def test_live_process_stays_running(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            # pid حي (هذه العملية نفسها) + نفس boot_id = ما زال يعمل.
            self.assertEqual(run_record.detect_crashed(td), [])

    def test_dead_pid_means_crashed(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            _rewrite_record(path, pid=999999)
            crashed = run_record.detect_crashed(td)
            self.assertEqual(len(crashed), 1)
            self.assertIn("process-gone", crashed[0][1]["error"])

    def test_old_record_without_boot_or_pid_left_alone(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            _rewrite_record(path, boot_id=None, pid=None)
            self.assertEqual(run_record.detect_crashed(td), [])
            crashed = run_record.detect_crashed(td, force=True)
            self.assertEqual(len(crashed), 1)

    def test_done_and_missing_dir_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            run_record.finish_record(path, "done")
            self.assertEqual(run_record.detect_crashed(td), [])
            self.assertEqual(run_record.detect_crashed(
                os.path.join(td, "no-such-dir")), [])


class TestResumePlan(unittest.TestCase):
    def _crashed(self, td, step):
        path, _ = _begin(td)
        run_dir = os.path.join(td, "anza-20261123-090000")
        if step in ("script", "produce"):
            _write_script(run_dir)
        if step == "produce":
            _write_manifest(run_dir)
        run_record.save_checkpoint(path, step, inputs=_inputs(run_dir),
                                   outputs={"title": "العنزة"})
        run_record.mark_crashed(path, error="محاكاة")
        with open(path, encoding="utf-8") as fh:
            return json.load(fh), run_dir

    def test_after_script_next_is_produce(self):
        with tempfile.TemporaryDirectory() as td:
            record, _ = self._crashed(td, "script")
            plan = run_resume.resume_plan(record)
            self.assertEqual(plan["completed_steps"], ["script"])
            self.assertEqual(plan["next_step"], "produce")
            self.assertTrue(run_resume.should_skip("script", plan))
            self.assertFalse(run_resume.should_skip("produce", plan))
            self.assertEqual(plan["resume_args"]["story"], "anza")
            self.assertEqual(plan["resume_args"]["backend"], "concat")
            self.assertEqual(plan["resume_args"]["out_path"],
                             "/tmp/out/anza-part1.mp4")

    def test_after_produce_next_is_assemble(self):
        with tempfile.TemporaryDirectory() as td:
            record, _ = self._crashed(td, "produce")
            plan = run_resume.resume_plan(record)
            self.assertEqual(plan["completed_steps"],
                             ["script", "produce"])
            self.assertEqual(plan["next_step"], "assemble")

    def test_done_raises(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            run_record.finish_record(path, "done")
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
            with self.assertRaises(run_resume.ResumeError):
                run_resume.resume_plan(record)

    def test_running_raises(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            run_record.save_checkpoint(path, "script")
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
            with self.assertRaises(run_resume.ResumeError):
                run_resume.resume_plan(record)

    def test_no_checkpoint_raises(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            run_record.mark_crashed(path, error="انهار قبل أي خطوة")
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
            with self.assertRaises(run_resume.ResumeError):
                run_resume.resume_plan(record)

    def test_all_steps_done_raises(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            run_record.save_checkpoint(path, "assemble")
            run_record.mark_crashed(path, error="بعد التجميع")
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
            with self.assertRaises(run_resume.ResumeError):
                run_resume.resume_plan(record)

    def test_failed_with_checkpoint_is_resumable(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            run_dir = os.path.join(td, "anza-20261123-090000")
            _write_script(run_dir)
            run_record.save_checkpoint(path, "script",
                                       inputs=_inputs(run_dir))
            run_record.finish_record(path, "failed", error="سقطت الشبكة")
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
            plan = run_resume.resume_plan(record)
            self.assertEqual(plan["next_step"], "produce")


class TestLoadScriptResult(unittest.TestCase):
    def test_valid_returns_title(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = os.path.join(td, "run1")
            _write_script(run_dir, title="عنوان محفوظ")
            result = run_resume.load_script_result(run_dir)
            self.assertEqual(result["title"], "عنوان محفوظ")

    def test_missing_corrupt_or_titleless_raise(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = os.path.join(td, "run1")
            os.makedirs(run_dir)
            with self.assertRaises(run_resume.ResumeError):
                run_resume.load_script_result(run_dir)
            bad = os.path.join(run_dir, "script-ai.json")
            Path(bad).write_text("{not json", encoding="utf-8")
            with self.assertRaises(run_resume.ResumeError):
                run_resume.load_script_result(run_dir)
            Path(bad).write_text(json.dumps({"caption": "بلا عنوان"}),
                                 encoding="utf-8")
            with self.assertRaises(run_resume.ResumeError):
                run_resume.load_script_result(run_dir)


class TestVerifyResumeInputs(unittest.TestCase):
    def test_missing_manifest_blocks_produce_resume(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = os.path.join(td, "anza-20261123-090000")
            _write_script(run_dir)
            path, _ = _begin(td)
            run_record.save_checkpoint(path, "produce",
                                       inputs=_inputs(run_dir))
            run_record.mark_crashed(path)
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
            plan = run_resume.resume_plan(record)
            ok, missing = run_resume.verify_resume_inputs(plan)
            self.assertFalse(ok)
            self.assertTrue(any("manifest.json" in m for m in missing))

    def test_complete_artifacts_verify_ok(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = os.path.join(td, "anza-20261123-090000")
            _write_script(run_dir)
            _write_manifest(run_dir)
            path, _ = _begin(td)
            run_record.save_checkpoint(path, "produce",
                                       inputs=_inputs(run_dir))
            run_record.mark_crashed(path)
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
            plan = run_resume.resume_plan(record)
            ok, missing = run_resume.verify_resume_inputs(plan)
            self.assertTrue(ok)
            self.assertEqual(missing, [])


class TestPrepareResume(unittest.TestCase):
    def _setup_crashed(self, td, step="produce"):
        run_dir = os.path.join(td, "anza-20261123-090000")
        _write_script(run_dir)
        _write_manifest(run_dir)
        path, run_id = _begin(td)
        run_record.save_checkpoint(path, step, inputs=_inputs(run_dir),
                                   outputs={"title": "العنزة"})
        run_record.mark_crashed(path, error="محاكاة انهيار")
        return path, run_id, run_dir

    def test_prepare_by_run_id_reopens_and_returns_plan(self):
        with tempfile.TemporaryDirectory() as td:
            path, run_id, _ = self._setup_crashed(td)
            got_path, plan = run_resume.prepare_resume(td, run_id)
            self.assertEqual(got_path, path)
            self.assertEqual(plan["next_step"], "assemble")
            self.assertEqual(plan["resume_count"], 0)
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
            self.assertEqual(record["status"], "running")
            self.assertEqual(record["resume_count"], 1)
            self.assertIn("resumed_at", record)
            self.assertIsNone(record["error"])

    def test_prepare_by_path(self):
        with tempfile.TemporaryDirectory() as td:
            path, _, _ = self._setup_crashed(td)
            got_path, plan = run_resume.prepare_resume(td, path)
            self.assertEqual(got_path, path)
            self.assertEqual(plan["next_step"], "assemble")

    def test_unknown_id_raises(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(run_resume.ResumeError):
                run_resume.prepare_resume(td, "لا-يوجد-123")

    def test_missing_artifacts_raise(self):
        with tempfile.TemporaryDirectory() as td:
            path, run_id, run_dir = self._setup_crashed(td)
            os.remove(os.path.join(run_dir, "manifest.json"))
            with self.assertRaises(run_resume.ResumeError):
                run_resume.prepare_resume(td, run_id)

    def test_second_resume_counts_up(self):
        with tempfile.TemporaryDirectory() as td:
            path, run_id, _ = self._setup_crashed(td)
            run_resume.prepare_resume(td, run_id)
            run_record.mark_crashed(path, error="انهار مجددًا")
            _, plan = run_resume.prepare_resume(td, run_id)
            self.assertEqual(plan["resume_count"], 1)
            with open(path, encoding="utf-8") as fh:
                record = json.load(fh)
            self.assertEqual(record["resume_count"], 2)


class TestListResumable(unittest.TestCase):
    def test_lists_only_resumable_newest_first(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = os.path.join(td, "anza-20261123-090000")
            _write_script(run_dir)
            _write_manifest(run_dir)
            p1, _ = _begin(td, run_id="anza-20261123-090000")
            run_record.save_checkpoint(p1, "produce",
                                       inputs=_inputs(run_dir))
            _rewrite_record(p1, started_at="2026-11-23T09:00:00+02:00")
            run_record.mark_crashed(p1)
            p2, _ = _begin(td, run_id="hamati-20261123-190000")
            run_dir2 = os.path.join(td, "hamati-20261123-190000")
            _write_script(run_dir2)
            run_record.save_checkpoint(p2, "script",
                                       inputs=_inputs(run_dir2))
            _rewrite_record(p2, started_at="2026-11-23T19:00:00+02:00")
            run_record.mark_crashed(p2)
            p3, _ = _begin(td, run_id="done-20261123-070000")
            run_record.finish_record(p3, "done")
            p4, _ = _begin(td, run_id="nocheck-20261123-080000")
            run_record.mark_crashed(p4)  # بلا نقطة تفتيش — غير قابل
            items = run_resume.list_resumable(td)
            self.assertEqual([i["run_id"] for i in items],
                             ["hamati-20261123-190000",
                              "anza-20261123-090000"])
            self.assertEqual(items[0]["next_step"], "produce")
            self.assertEqual(items[1]["next_step"], "assemble")


class TestFindRecord(unittest.TestCase):
    def test_find_by_run_id(self):
        with tempfile.TemporaryDirectory() as td:
            path, run_id = _begin(td)
            self.assertEqual(run_resume.find_record(td, run_id), path)
            self.assertIsNone(run_resume.find_record(td, "غير-موجود"))


class TestSimulateCrash(unittest.TestCase):
    def test_simulate_crash_saves_checkpoint_and_marks(self):
        with tempfile.TemporaryDirectory() as td:
            path, _ = _begin(td)
            run_dir = os.path.join(td, "anza-20261123-090000")
            rec = run_resume.simulate_crash(
                path, step="script", inputs=_inputs(run_dir),
                outputs={"title": "العنزة"})
            self.assertEqual(rec["status"], "crashed")
            self.assertEqual(rec["checkpoint"]["step"], "script")
            self.assertEqual(rec["checkpoint"]["note"], "محاكاة انهيار")


class TestRunlogShowsCrashed(unittest.TestCase):
    def test_crashed_record_listed_with_resume_hint(self):
        with tempfile.TemporaryDirectory() as td:
            runs = Path(td) / "runs"
            runs.mkdir()
            path, run_id = _begin(str(runs))
            run_record.save_checkpoint(path, "produce")
            run_record.mark_crashed(path, error="ريستارت VM")
            p2, _ = _begin(str(runs), run_id="live-20261123-100000")
            entries = runlog.collect_runs(str(runs), today_only=False)
            by_id = {e.get("run_id"): e for e in entries}
            crashed = by_id[run_id]
            self.assertEqual(crashed["status"], "تعطّل")
            self.assertEqual(crashed["kind"], "تشغيل")
            self.assertIn("produce", crashed["detail"])
            self.assertIn("run --resume %s" % run_id, crashed["detail"])
            self.assertEqual(by_id["live-20261123-100000"]["status"],
                             "جارٍ")

    def test_corrupt_record_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            runs = Path(td) / "runs"
            runs.mkdir()
            (runs / "run-bad.json").write_text("{not json",
                                               encoding="utf-8")
            self.assertEqual(runlog.collect_runs(str(runs)), [])


if __name__ == "__main__":
    unittest.main()
