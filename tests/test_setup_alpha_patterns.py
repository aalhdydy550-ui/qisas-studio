#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبارات أنماط مثبّت AlphaCLI المطبَّقة على setup.sh (v0.1.41).

الأنماط الستة (تقييم AlphaCLI §2.7 و§4.1 بند 1 وجدول §6 بند 1):
1. تحقق SHA-256 للتنزيل (فشل = إيقاف؛ غياب المجموع = تحذير).
2. تثبيت ذري (مؤقت + نقل فوق الهدف).
3. كتلة PATH معلَّمة وidempotent في ملفات بدء التشغيل.
4. تحقق من shell جديدة أن PATH يعمل.
5. --path-dry-run و--no-path.
6. إصدار مثبّت + احتياطي متدرج (أحدث إصدار، وبناء المصدر
   ضمنيًا داخل pip).
7. السكربت كله داخل main() تُستدعى في السطر الأخير.

بلا شبكة وبلا مساس بالبيئة الحية: مجلدات مؤقتة وHOME بديل.
"""
import base64
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP_SH = os.path.join(STUDIO_ROOT, "setup.sh")

sys.path.insert(0, STUDIO_ROOT)

from lib import ensure_env


def _stage_setup(tmp):
    """انسخ setup.sh + lib/ensure_env.py (+ __init__) إلى tmp."""
    shutil.copy2(SETUP_SH, os.path.join(tmp, "setup.sh"))
    lib = os.path.join(tmp, "lib")
    os.makedirs(lib)
    for name in ("__init__.py", "ensure_env.py"):
        shutil.copy2(os.path.join(STUDIO_ROOT, "lib", name),
                     os.path.join(lib, name))
    return os.path.join(tmp, "setup.sh")


def _sha256_b64(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return base64.urlsafe_b64encode(h.digest()).decode().rstrip("=")


class TestPinnedVersions(unittest.TestCase):
    def test_every_package_is_version_pinned(self):
        for name, spec in ensure_env.TOOLS.items():
            for pkg in spec["packages"]:
                self.assertIn("==", pkg,
                              "%s: %s بلا تثبيت إصدار" % (name, pkg))

    def test_pins_match_live_freeze(self):
        pins = {p for s in ensure_env.TOOLS.values()
                for p in s["packages"]}
        self.assertIn("gtts==2.5.4", pins)
        self.assertIn("google-api-python-client==2.202.0", pins)
        self.assertIn("auto-editor==29.3.1", pins)
        self.assertIn("faster-whisper==1.2.1", pins)
        self.assertIn("moviepy==2.2.1", pins)


class TestGraduatedFallback(unittest.TestCase):
    def test_pinned_then_unpinned(self):
        calls = []

        def fake_run(cmd, timeout=1200):
            calls.append(cmd)
            if "==" in " ".join(cmd):
                return False, "no matching distribution"
            return True, ""

        orig = ensure_env._run
        ensure_env._run = fake_run
        try:
            ok, msg = ensure_env._install_packages(
                sys.executable, ["somepkg==1.0"])
        finally:
            ensure_env._run = orig
        self.assertTrue(ok)
        self.assertEqual(len(calls), 2)
        self.assertIn("somepkg==1.0", calls[0])
        self.assertIn("somepkg", calls[1])
        self.assertNotIn("==", " ".join(calls[1]))
        self.assertIn("باحتياطي", msg)

    def test_both_attempts_fail_mentions_build_tools(self):
        orig = ensure_env._run
        ensure_env._run = lambda cmd, timeout=1200: (
            False, "boom")
        try:
            ok, msg = ensure_env._install_packages(
                sys.executable, ["somepkg==1.0"])
        finally:
            ensure_env._run = orig
        self.assertFalse(ok)
        self.assertIn("build-essential", msg)

    def test_empty_packages_is_noop(self):
        ok, _msg = ensure_env._install_packages(sys.executable, [])
        self.assertTrue(ok)


class TestAtomicVenvAndLinks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self._orig = dict(ensure_env.TOOLS)
        ensure_env.TOOLS["tinytest"] = {
            "legacy": ".venv-tinytest",
            "group": None,
            "packages": [],
            "import": "json",
            "heavy": True,
            "desc": "أداة اختبار وهمية",
        }

    def tearDown(self):
        ensure_env.TOOLS.clear()
        ensure_env.TOOLS.update(self._orig)
        self.tmp.cleanup()

    def test_tmpdir_under_venv_and_restored(self):
        # تثبيت يوجّه TMPDIR تحت البيئة (قرص واسع) ويستعيده بعدها،
        # وبلا بقايا .pip-tmp- — إصلاح ENOSPC في ‎/tmp (tmpfs ‏512M).
        seen = []
        orig = ensure_env._run

        def fake_run(cmd, timeout=1200):
            seen.append(os.environ.get("TMPDIR"))
            return True, ""

        venv = os.path.join(self.tmp.name, "venv-tmp")
        os.makedirs(os.path.join(venv, "bin"))
        py = os.path.join(venv, "bin", "python")
        with open(py, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\n")
        os.environ.pop("TMPDIR", None)
        try:
            ensure_env._run = fake_run
            ok, _msg = ensure_env._install_packages(
                py, ["pkgx==1.0"])
        finally:
            ensure_env._run = orig
        self.assertTrue(ok)
        self.assertEqual(len(seen), 1)
        self.assertTrue(seen[0].startswith(venv),
                        "TMPDIR كان %s لا تحت %s" % (seen[0], venv))
        self.assertNotIn("TMPDIR", os.environ)
        self.assertEqual([d for d in os.listdir(venv)
                          if d.startswith(".pip-tmp-")], [])

    def test_atomic_venv_scripts_point_at_final_path(self):
        # venv تُنشأ ذريًا: shebang سكربت pip وVIRTUAL_ENV في
        # activate تشيران إلى المسار النهائي لا المؤقت، وbin/pip
        # يعمل مباشرة (عيب وُجد في sandbox --full: shebang
        # المؤقت ميت بعد النقل).
        venv = os.path.join(self.tmp.name, "venv-atomic")
        ok, _msg = ensure_env._create_venv_atomic(venv)
        self.assertTrue(ok)
        self.assertFalse(os.path.exists(venv + ".tmp-%d" % os.getpid()))
        with open(os.path.join(venv, "bin", "pip"), "rb") as f:
            first = f.readline()
        self.assertIn(os.path.abspath(venv).encode(), first)
        self.assertNotIn(b".tmp-", first)
        r = subprocess.run(
            [os.path.join(venv, "bin", "pip"), "--version"],
            capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("pip ", r.stdout)

    def test_ensure_leaves_no_temp_venv(self):
        ok, msg = ensure_env.ensure("tinytest", root=self.root)
        self.assertTrue(ok, msg)
        leftovers = [e for e in os.listdir(self.root)
                     if ".tmp-" in e]
        self.assertEqual(leftovers, [])
        self.assertTrue(os.path.isdir(
            os.path.join(self.root, ".venv-tinytest")))

    def test_wrong_target_symlink_is_replaced_atomically(self):
        os.makedirs(os.path.join(self.root, ".venv-youtube", "bin"))
        wrong = os.path.join(self.root, ".venv-gtts")
        os.symlink("/nonexistent-wrong-target", wrong)
        results = ensure_env.link_legacy_aliases(root=self.root)
        by_name = {n: a for n, a, _d in results}
        self.assertEqual(by_name["gtts"], "linked")
        self.assertEqual(os.readlink(wrong), ".venv-youtube")
        leftovers = [e for e in os.listdir(self.root)
                     if ".tmp-" in e]
        self.assertEqual(leftovers, [])

    def test_correct_symlink_is_kept(self):
        os.makedirs(os.path.join(self.root, ".venv-youtube", "bin"))
        os.symlink(".venv-youtube",
                   os.path.join(self.root, ".venv-gtts"))
        results = ensure_env.link_legacy_aliases(root=self.root)
        by_name = {n: a for n, a, _d in results}
        self.assertEqual(by_name["gtts"], "kept")


class TestSha256Verify(unittest.TestCase):
    """تحقق RECORD: ملفات مصنوعة بلا شبكة في venv حقيقي."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.venv = os.path.join(self.root, ".venv-verifytest")
        subprocess.run([sys.executable, "-m", "venv", self.venv],
                       check=True, timeout=120)
        self.py = os.path.join(self.venv, "bin", "python")
        self.site = subprocess.run(
            [self.py, "-c",
             "import sysconfig; print(sysconfig.get_path('purelib'))"],
            capture_output=True, text=True, check=True,
            timeout=60).stdout.strip()
        self._orig = dict(ensure_env.TOOLS)
        ensure_env.TOOLS["verifytest"] = {
            "legacy": ".venv-verifytest",
            "group": None,
            "packages": ["fakepkg"],
            "import": "json",
            "heavy": True,
            "desc": "أداة اختبار تحقق",
        }
        # حزمة مزيفة: ملف + dist-info بـRECORD صحيح.
        pkg_dir = os.path.join(self.site, "fakepkg")
        os.makedirs(pkg_dir)
        self.mod = os.path.join(pkg_dir, "__init__.py")
        with open(self.mod, "w", encoding="utf-8") as f:
            f.write("VALUE = 1\n")
        dist = os.path.join(self.site, "fakepkg-1.0.dist-info")
        os.makedirs(dist)
        with open(os.path.join(dist, "METADATA"), "w",
                  encoding="utf-8") as f:
            f.write("Metadata-Version: 2.1\nName: fakepkg\n"
                    "Version: 1.0\n")
        self.record = os.path.join(dist, "RECORD")
        self._write_record()

    def _write_record(self):
        rel = "fakepkg/__init__.py"
        digest = "sha256=" + _sha256_b64(self.mod)
        with open(self.record, "w", encoding="utf-8") as f:
            f.write("%s,%s,\n" % (rel, digest))
            f.write("fakepkg-1.0.dist-info/METADATA,,\n")
            f.write("fakepkg-1.0.dist-info/RECORD,,\n")

    def tearDown(self):
        ensure_env.TOOLS.clear()
        ensure_env.TOOLS.update(self._orig)
        self.tmp.cleanup()

    def test_verify_passes_on_intact_files(self):
        ok, lines = ensure_env.verify_tool(self.root, "verifytest")
        self.assertTrue(ok, lines)
        self.assertTrue(any("[PASS]" in l for l in lines))

    def test_verify_fails_on_corrupted_file(self):
        with open(self.mod, "a", encoding="utf-8") as f:
            f.write("TAMPERED = True\n")
        ok, lines = ensure_env.verify_tool(self.root, "verifytest")
        self.assertFalse(ok)
        self.assertTrue(any("لا يطابق" in l for l in lines))

    def test_verify_fails_on_missing_file(self):
        os.unlink(self.mod)
        ok, lines = ensure_env.verify_tool(self.root, "verifytest")
        self.assertFalse(ok)
        self.assertTrue(any("مفقود" in l for l in lines))

    def test_missing_record_is_warning_not_silent_pass(self):
        os.unlink(self.record)
        ok, lines = ensure_env.verify_tool(self.root, "verifytest")
        self.assertTrue(ok)  # تحذير لا فشل
        self.assertTrue(any("[WARN]" in l for l in lines))
        self.assertTrue(any("RECORD" in l for l in lines))

    def test_missing_dist_info_is_warning_not_silent_pass(self):
        shutil.rmtree(os.path.join(
            self.site, "fakepkg-1.0.dist-info"))
        ok, lines = ensure_env.verify_tool(self.root, "verifytest")
        self.assertTrue(ok)
        self.assertTrue(any("[WARN]" in l for l in lines))
        self.assertTrue(any("بلا بيانات تثبيت" in l
                            for l in lines))

    def test_verify_cli_exit_codes(self):
        # حارس CI (جولة v0.1.42): بيئة gtts محلية فقط
        # (.venv-gtts أو المشتركة .venv-youtube) وغائبة في
        # checkout نظيف، فيفشل `verify` بـ«بلا بيئة (غير
        # مثبّت)» لا بخلل في الكود — يُتخطى. فحص الأداة غير
        # المعروفة (→ 2) بلا بيئة فيبقى يعمل دائمًا.
        python, _where = ensure_env.resolve_python(STUDIO_ROOT,
                                                   "gtts")
        if python is None:
            self.skipTest("بيئة gtts غائبة (لا .venv-gtts ولا "
                          ".venv-youtube — CI عارٍ)")
        # CLI عملية فرعية (بلا أداة وهمية): تحقق حقيقي قراءة فقط
        # على الشجرة الحية + أداة غير معروفة → 2.
        r = subprocess.run(
            [sys.executable, "-m", "lib.ensure_env", "verify",
             "gtts", "--root", STUDIO_ROOT],
            capture_output=True, text=True, timeout=180,
            cwd=STUDIO_ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[PASS] gtts", r.stdout)
        r = subprocess.run(
            [sys.executable, "-m", "lib.ensure_env", "verify",
             "nope", "--root", STUDIO_ROOT],
            capture_output=True, text=True, timeout=60,
            cwd=STUDIO_ROOT)
        self.assertEqual(r.returncode, 2)


class TestMainWrapper(unittest.TestCase):
    def test_last_line_calls_main(self):
        with open(SETUP_SH, encoding="utf-8") as f:
            lines = [l.rstrip() for l in f if l.strip()]
        self.assertEqual(lines[-1], 'main "$@"')
        self.assertTrue(any(l.startswith("main() {")
                            for l in lines))

    def test_no_forbidden_component_words(self):
        with open(SETUP_SH, encoding="utf-8") as f:
            text = f.read().lower()
        for word in ("openmontage", "concat"):
            self.assertNotIn(word, text)

    def test_truncated_without_main_call_runs_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(SETUP_SH, encoding="utf-8") as f:
                lines = f.readlines()
            # نسخة بلا سطر استدعاء main الأخير.
            self.assertEqual(lines[-1].strip(), 'main "$@"')
            partial = os.path.join(tmp, "setup.sh")
            with open(partial, "w", encoding="utf-8") as f:
                f.writelines(lines[:-1])
            env = dict(os.environ)
            env["HOME"] = tmp
            r = subprocess.run(["bash", partial],
                               capture_output=True, text=True,
                               timeout=60, cwd=tmp, env=env)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout.strip(), "")
            self.assertEqual(os.listdir(tmp), ["setup.sh"])

    def test_mid_truncated_script_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(SETUP_SH, encoding="utf-8") as f:
                lines = f.readlines()
            partial = os.path.join(tmp, "setup.sh")
            with open(partial, "w", encoding="utf-8") as f:
                f.writelines(lines[:120])
            env = dict(os.environ)
            env["HOME"] = tmp
            r = subprocess.run(["bash", partial],
                               capture_output=True, text=True,
                               timeout=60, cwd=tmp, env=env)
            self.assertNotEqual(r.returncode, 0)


class TestPathBlock(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self.tmp.name, "home")
        os.makedirs(self.home)
        self.work = os.path.join(self.tmp.name, "work")
        os.makedirs(self.work)
        self.script = _stage_setup(self.work)
        self.env = dict(os.environ)
        self.env["HOME"] = self.home
        self.env["SHELL"] = "/bin/bash"
        self.env["STUDIO_SETUP_NO_APT"] = "1"

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, *args):
        return subprocess.run(
            ["bash", self.script] + list(args),
            capture_output=True, text=True, timeout=120,
            cwd=self.work, env=self.env)

    def _block_count(self, path):
        if not os.path.isfile(path):
            return 0
        with open(path, encoding="utf-8") as f:
            return f.read().count("# >>> qisas-studio >>>")

    def test_path_dry_run_writes_nothing(self):
        r = self._run("--path-dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("# >>> qisas-studio >>>", r.stdout)
        self.assertIn(".bashrc", r.stdout)
        self.assertFalse(os.path.exists(
            os.path.join(self.home, ".bashrc")))
        self.assertFalse(os.path.exists(
            os.path.join(self.home, ".profile")))

    def test_path_only_applies_once_per_file(self):
        r = self._run("--path-only")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for name in (".bashrc", ".profile"):
            path = os.path.join(self.home, name)
            self.assertEqual(self._block_count(path), 1, name)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("$HOME/.local/bin", text)
            self.assertIn("$HOME/.npm-global/bin", text)

    def test_path_only_is_idempotent(self):
        self._run("--path-only")
        r = self._run("--path-only")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for name in (".bashrc", ".profile"):
            self.assertEqual(self._block_count(
                os.path.join(self.home, name)), 1, name)

    def test_remove_path_restores_files(self):
        marker = os.path.join(self.home, ".bashrc")
        with open(marker, "w", encoding="utf-8") as f:
            f.write("# my own line\nexport FOO=1\n")
        self._run("--path-only")
        self.assertEqual(self._block_count(marker), 1)
        r = self._run("--remove-path")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self._block_count(marker), 0)
        with open(marker, encoding="utf-8") as f:
            self.assertEqual(f.read(), "# my own line\nexport FOO=1\n")

    def test_fresh_shell_verification_passes(self):
        r = self._run("--path-only")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("shell جديدة ترى", r.stdout)

    def test_shadow_warning(self):
        # ثنائي ffmpeg في ~/.local/bin + آخر يتقدمه: سطر ظل بعد
        # الكتلة في .bashrc (فيُقرأ بعدها في shell التفاعلية).
        shadow_dir = os.path.join(self.tmp.name, "shadowbin")
        os.makedirs(shadow_dir)
        p = os.path.join(shadow_dir, "ffmpeg")
        with open(p, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho shadow\n")
        os.chmod(p, 0o755)
        local_bin = os.path.join(self.home, ".local", "bin")
        os.makedirs(local_bin)
        p = os.path.join(local_bin, "ffmpeg")
        with open(p, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho local\n")
        os.chmod(p, 0o755)
        r = self._run("--path-only")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # ألحق سطر ظل بعد الكتلة في .bashrc ثم أعد التحقق.
        with open(os.path.join(self.home, ".bashrc"), "a",
                  encoding="utf-8") as f:
            f.write('export PATH="%s:$PATH"\n' % shadow_dir)
        r = self._run("--path-only")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("يفوز على ffmpeg", r.stdout)

    def test_no_path_and_path_only_conflict(self):
        r = self._run("--path-only", "--no-path")
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
