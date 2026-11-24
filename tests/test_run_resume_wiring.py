#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات توصيل run --resume في cmd_run — جولة v0.1.41 (بند 6).

تُحاكى الخطوات الثقيلة (cmd_script/cmd_produce/cmd_assemble)
ويُختبر تدفق السجل الحقيقي: detect_crashed عند البدء،
save_checkpoint بعد script/produce، وتخطي المكتمل عند الاستئناف.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import run_record


def _cfg(runs_dir):
    return {"paths": {"runs_dir": runs_dir},
            "narration": {}, "video": {"width": 720, "height": 1280},
            "omniroute": {}, "veo": {}}


class TestRunResumeWiring(unittest.TestCase):
    def _mocked_run(self, cfg, **kwargs):
        """شغّل cmd_run بكل الخطوات محاكاة؛ ارجع (code, mocks)."""
        script = mock.Mock(
            return_value=({"title": "عنوان"}, {"status": "ok"}))
        produce = mock.Mock(return_value={"images": ["a.png"],
                                          "phrases": [{"text": "x"}]})
        assemble = mock.Mock(return_value=("/tmp/out.mp4", 2.0))
        call_kwargs = {k: v for k, v in kwargs.items()
                       if k in ("resume", "backend")}
        with mock.patch.object(studio, "cmd_script", script), \
                mock.patch.object(studio, "cmd_produce", produce), \
                mock.patch.object(studio, "cmd_assemble", assemble):
            code = studio.cmd_run(cfg, kwargs.get("story", "قصة"),
                                  kwargs.get("project", "proj"),
                                  kwargs.get("out_path", "/tmp/out.mp4"),
                                  True, **call_kwargs)
        return code, script, produce, assemble

    def test_fresh_run_saves_checkpoints(self):
        with tempfile.TemporaryDirectory() as td:
            runs = os.path.join(td, "runs")
            code, script, produce, assemble = self._mocked_run(_cfg(runs))
            self.assertEqual(code, 0)
            self.assertEqual(script.call_count, 1)
            self.assertEqual(produce.call_count, 1)
            self.assertEqual(assemble.call_count, 1)
            records = [os.path.join(runs, f) for f in os.listdir(runs)
                       if f.startswith("run-") and f.endswith(".json")]
            self.assertEqual(len(records), 1)
            rec = run_record.load_record(records[0])
            self.assertEqual(rec["status"], "done")
            self.assertEqual((rec.get("checkpoint") or {}).get("step"),
                             "produce")

    def test_resume_skips_completed_steps(self):
        with tempfile.TemporaryDirectory() as td:
            runs = os.path.join(td, "runs")
            os.makedirs(runs)
            # سجل منقطع بعد produce مع ملفات الخطوات على القرص.
            run_id = "run-20261123-120000-test"
            run_dir = os.path.join(runs, run_id)
            os.makedirs(run_dir)
            with open(os.path.join(run_dir, "script-ai.json"), "w",
                      encoding="utf-8") as fh:
                json.dump({"title": "عنوان محفوظ"}, fh, ensure_ascii=False)
            with open(os.path.join(run_dir, "manifest.json"), "w",
                      encoding="utf-8") as fh:
                json.dump({"images": ["a.png"],
                           "phrases": [{"text": "x"}]}, fh,
                          ensure_ascii=False)
            settings = run_record.resolve_settings(
                _cfg(runs), {"backend": "concat", "grade": None,
                             "watermark": True, "story": "قصة",
                             "project": "proj"})
            path, _ = run_record.begin_record(runs, "run", settings,
                                              run_id=run_id)
            inputs = {"story": "قصة", "project": "proj",
                      "backend": "concat", "out_path": "/tmp/out.mp4",
                      "watermark": True, "grade": None, "cards_dir": None,
                      "lang": "ar", "allow_fallback": True,
                      "run_dir": run_dir}
            run_record.save_checkpoint(
                path, "script", inputs=inputs,
                outputs={"title": "عنوان محفوظ",
                         "script_file": "script-ai.json"})
            run_record.save_checkpoint(
                path, "produce", inputs=inputs,
                outputs={"manifest_file": "manifest.json",
                         "images": 1, "phrases": 1})
            run_record.finish_record(path, "failed",
                                     error=RuntimeError("x"))
            code, script, produce, assemble = self._mocked_run(
                _cfg(runs), resume=run_id)
            self.assertEqual(code, 0)
            self.assertEqual(script.call_count, 0)
            self.assertEqual(produce.call_count, 0)
            self.assertEqual(assemble.call_count, 1)
            # العنوان المستعاد من script-ai.json يصل إلى التجميع.
            self.assertEqual(assemble.call_args[0][2], "عنوان محفوظ")
            rec = run_record.load_record(path)
            self.assertEqual(rec["status"], "done")

    def test_detect_crashed_marks_old_running(self):
        with tempfile.TemporaryDirectory() as td:
            runs = os.path.join(td, "runs")
            os.makedirs(runs)
            settings = run_record.resolve_settings(_cfg(runs), {})
            path, _ = run_record.begin_record(runs, "run", settings,
                                              run_id="run-old")
            # boot_id مزيّف يختلف عن boot_id الحالي: السجل
            # running يُعلَّم crashed عند بدء تشغيل جديد.
            with open(path, encoding="utf-8") as fh:
                rec = json.load(fh)
            rec["boot_id"] = "00000000-0000-0000-0000-000000000000"
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(rec, fh, ensure_ascii=False, indent=2)
            code, _, _, _ = self._mocked_run(_cfg(runs))
            self.assertEqual(code, 0)
            rec = run_record.load_record(path)
            self.assertEqual(rec["status"], "crashed")


if __name__ == "__main__":
    unittest.main()
