#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبار محاكاة الانهيار end-to-end — جولة v0.1.41 (بند 6).

خط إنتاج مصغّر يحاكي ترتيب خطوات cmd_run (script ← produce ←
assemble) بدوال وهمية تكتب الملفات الحقيقية نفسها
(script-ai.json وmanifest.json والفيديو) في مجلد مؤقت في
/tmp فقط: يُوقف التشغيل وسط التنفيذ (محاكاة ريستارت VM)،
ثم يُستأنف — ويُتحقق أنه يكمل من نقطة التفتيش ولا يعيد ما
اكتمل ولا يكرر مخرجات.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import run_record, run_resume


class SimulatedCrash(RuntimeError):
    """انهيار محاكى: انقطاع مفاجئ وسط التنفيذ (ريستارت VM)."""


class FakePipeline:
    """خط cmd_run مصغّر: script ثم produce ثم assemble.

    كل خطوة تكتب ملفها الحقيقي في run_dir وتحفظ نقطة تفتيشها.
    crash_after: اسم الخطوة التي ينهار التشغيل بعد اكتمالها
    مباشرة (أو "assemble-mid" للانهيار وسط التجميع قبل كتابة
    المخرج، أو "assemble-late" بعده وقبل إنهاء السجل).
    """

    TITLE = "العنزة التي أنقذت القرية"

    def __init__(self, runs_dir, run_id):
        self.runs_dir = runs_dir
        self.run_id = run_id
        self.run_dir = os.path.join(runs_dir, run_id)
        self.out_path = os.path.join(runs_dir, "out-%s.mp4" % run_id)
        self.record_path = None
        self.calls = {"script": 0, "produce": 0, "assemble": 0}
        self.skipped = []

    def _inputs(self):
        return {"story": "anza", "project": "anza-part1",
                "backend": "concat", "out_path": self.out_path,
                "watermark": True, "grade": None, "cards_dir": None,
                "lang": "ar", "allow_fallback": True,
                "run_dir": self.run_dir}

    def _step_script(self):
        self.calls["script"] += 1
        os.makedirs(self.run_dir, exist_ok=True)
        with open(os.path.join(self.run_dir, "script-ai.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"title": self.TITLE, "caption": "قصة حقيقية",
                       "source": "omniroute"}, fh, ensure_ascii=False)
        run_record.save_checkpoint(
            self.record_path, "script", inputs=self._inputs(),
            outputs={"title": self.TITLE, "script_file": "script-ai.json"})
        return self.TITLE

    def _step_produce(self):
        self.calls["produce"] += 1
        os.makedirs(self.run_dir, exist_ok=True)
        with open(os.path.join(self.run_dir, "manifest.json"), "w",
                  encoding="utf-8") as fh:
            json.dump({"images": ["a.png", "b.png"],
                       "phrases": ["عبارة 1", "عبارة 2"]},
                      fh, ensure_ascii=False)
        run_record.save_checkpoint(
            self.record_path, "produce", inputs=self._inputs(),
            outputs={"manifest_file": "manifest.json",
                     "images": 2, "phrases": 2})

    def _step_assemble(self, title, write_output=True):
        self.calls["assemble"] += 1
        if write_output:
            # محاكاة فيديو: بايتات ثابتة فوق نفس المسار (إعادة
            # الكتابة فوقه آمنة — لا نسخة مكررة أبدًا).
            with open(self.out_path, "wb") as fh:
                fh.write(b"FAKE-MP4-anza-part1")

    def execute(self, plan=None, crash_after=None):
        """شغّل الخط (من جديد أو استئنافًا حسب plan)."""
        if plan is None:
            settings = run_record.resolve_settings(
                {}, {"story": "anza", "project": "anza-part1",
                     "backend": "concat"})
            self.record_path, _ = run_record.begin_record(
                self.runs_dir, "run", settings, run_id=self.run_id)
        else:
            self.record_path = plan["_record_path"]
        title = None
        if plan is None or not run_resume.should_skip("script", plan):
            title = self._step_script()
        else:
            self.skipped.append("script")
            title = run_resume.load_script_result(
                self.run_dir)["title"]
        if crash_after == "script":
            raise SimulatedCrash("انقطع التيار بعد السيناريو")
        if plan is None or not run_resume.should_skip("produce", plan):
            self._step_produce()
        else:
            self.skipped.append("produce")
        if crash_after == "produce":
            raise SimulatedCrash("انقطع التيار بعد الإنتاج")
        if crash_after == "assemble-mid":
            # انهيار وسط التجميع قبل كتابة أي مخرج.
            self.calls["assemble"] += 1
            raise SimulatedCrash("انقطع التيار وسط التجميع")
        self._step_assemble(title)
        if crash_after == "assemble-late":
            # انهيار بعد كتابة المخرج وقبل إنهاء السجل.
            raise SimulatedCrash("انقطع التيار بعد كتابة المخرج")
        run_record.finish_record(self.record_path, "done",
                                 outputs=[self.out_path])
        return self.out_path

    def fake_vm_restart(self):
        """محاكاة ريستارت VM: boot_id السجل يصير من إقلاع قديم."""
        with open(self.record_path, encoding="utf-8") as fh:
            record = json.load(fh)
        record["boot_id"] = "boot-id-قبل-الريستارت"
        with open(self.record_path, "w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False, indent=2)

    def resume(self):
        """اكتشف الانقطاع ثم استأنف؛ ترجع (مسار السجل، الخطة)."""
        self.fake_vm_restart()  # ريستارت VM: الإقلاع تغيّر
        crashed = run_record.detect_crashed(self.runs_dir)
        assert len(crashed) == 1, crashed
        assert crashed[0][1]["status"] == "crashed"
        path, plan = run_resume.prepare_resume(
            self.runs_dir, self.run_id)
        plan["_record_path"] = path
        return path, plan


def _load_record(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class TestCrashAfterProduce(unittest.TestCase):
    def test_resume_skips_script_and_produce(self):
        with tempfile.TemporaryDirectory() as td:
            pipe = FakePipeline(td, "anza-20261123-090000")
            with self.assertRaises(SimulatedCrash):
                pipe.execute(crash_after="produce")
            self.assertEqual(pipe.calls,
                             {"script": 1, "produce": 1, "assemble": 0})
            path, plan = pipe.resume()
            self.assertEqual(plan["completed_steps"],
                             ["script", "produce"])
            self.assertEqual(plan["next_step"], "assemble")
            out = pipe.execute(plan=plan)
            self.assertEqual(out, pipe.out_path)
            # لا إعادة لأي خطوة مكتملة، والتجميع مرة واحدة فقط.
            self.assertEqual(pipe.calls,
                             {"script": 1, "produce": 1, "assemble": 1})
            self.assertEqual(pipe.skipped, ["script", "produce"])
            self.assertTrue(os.path.isfile(pipe.out_path))
            record = _load_record(path)
            self.assertEqual(record["status"], "done")
            self.assertEqual(record["outputs"], [pipe.out_path])
            self.assertEqual(record["resume_count"], 1)
            self.assertEqual(record["checkpoint"]["step"], "produce")
            # مخرج واحد فقط — بلا نسخة مكررة.
            self.assertEqual(
                [p for p in Path(td).glob("out-*.mp4")],
                [Path(pipe.out_path)])


class TestCrashAfterScript(unittest.TestCase):
    def test_resume_skips_script_only(self):
        with tempfile.TemporaryDirectory() as td:
            pipe = FakePipeline(td, "anza-20261123-091500")
            with self.assertRaises(SimulatedCrash):
                pipe.execute(crash_after="script")
            # طريق التعليم البديل: simulate_crash مباشرة.
            rec = run_resume.simulate_crash(
                pipe.record_path, step="script",
                inputs=pipe._inputs(),
                outputs={"title": FakePipeline.TITLE})
            self.assertEqual(rec["status"], "crashed")
            path, plan = run_resume.prepare_resume(
                td, pipe.run_id)
            plan["_record_path"] = path
            self.assertEqual(plan["next_step"], "produce")
            pipe.execute(plan=plan)
            self.assertEqual(pipe.calls,
                             {"script": 1, "produce": 1, "assemble": 1})
            self.assertEqual(pipe.skipped, ["script"])
            record = _load_record(path)
            self.assertEqual(record["status"], "done")
            self.assertEqual(record["outputs"], [pipe.out_path])


class TestCrashDuringAssemble(unittest.TestCase):
    def test_crash_mid_assemble_reruns_assemble_only(self):
        with tempfile.TemporaryDirectory() as td:
            pipe = FakePipeline(td, "anza-20261123-093000")
            with self.assertRaises(SimulatedCrash):
                pipe.execute(crash_after="assemble-mid")
            self.assertFalse(os.path.exists(pipe.out_path))
            _, plan = pipe.resume()
            self.assertEqual(plan["next_step"], "assemble")
            pipe.execute(plan=plan)
            self.assertEqual(pipe.calls,
                             {"script": 1, "produce": 1, "assemble": 2})
            self.assertEqual(pipe.skipped, ["script", "produce"])
            self.assertTrue(os.path.isfile(pipe.out_path))
            self.assertEqual(
                [p for p in Path(td).glob("out-*.mp4")],
                [Path(pipe.out_path)])

    def test_crash_after_output_overwrites_same_file(self):
        with tempfile.TemporaryDirectory() as td:
            pipe = FakePipeline(td, "anza-20261123-094500")
            with self.assertRaises(SimulatedCrash):
                pipe.execute(crash_after="assemble-late")
            # المخرج كُتب قبل الانهيار؛ الاستئناف يعيد كتابته
            # فوق نفس المسار — ملف واحد لا نسختان.
            self.assertTrue(os.path.isfile(pipe.out_path))
            _, plan = pipe.resume()
            pipe.execute(plan=plan)
            self.assertEqual(pipe.calls["assemble"], 2)
            self.assertEqual(
                [p for p in Path(td).glob("out-*.mp4")],
                [Path(pipe.out_path)])
            with open(pipe.out_path, "rb") as fh:
                self.assertEqual(fh.read(), b"FAKE-MP4-anza-part1")


class TestCrashBeforeAnyCheckpoint(unittest.TestCase):
    def test_no_checkpoint_means_fresh_run_required(self):
        with tempfile.TemporaryDirectory() as td:
            pipe = FakePipeline(td, "anza-20261123-100000")
            # انهيار أثناء السيناريو نفسه: بلا نقطة تفتيش أصلًا.
            settings = run_record.resolve_settings(
                {}, {"story": "anza", "project": "anza-part1"})
            path, _ = run_record.begin_record(td, "run", settings,
                                              run_id=pipe.run_id)
            pipe.record_path = path
            run_record.mark_crashed(path, error="انهار أثناء السيناريو")
            with self.assertRaises(run_resume.ResumeError):
                run_resume.prepare_resume(td, pipe.run_id)


class TestDoubleCrash(unittest.TestCase):
    def test_crash_twice_then_resume(self):
        with tempfile.TemporaryDirectory() as td:
            pipe = FakePipeline(td, "anza-20261123-101500")
            with self.assertRaises(SimulatedCrash):
                pipe.execute(crash_after="produce")
            _, plan = pipe.resume()
            plan["_record_path"] = pipe.record_path
            # انهيار ثانٍ أثناء استئناف التجميع.
            with self.assertRaises(SimulatedCrash):
                pipe.execute(plan=plan, crash_after="assemble-mid")
            _, plan2 = pipe.resume()
            self.assertEqual(plan2["resume_count"], 1)
            pipe.execute(plan=plan2)
            record = _load_record(pipe.record_path)
            self.assertEqual(record["status"], "done")
            self.assertEqual(record["resume_count"], 2)
            self.assertEqual(pipe.calls,
                             {"script": 1, "produce": 1, "assemble": 2})


if __name__ == "__main__":
    unittest.main()
