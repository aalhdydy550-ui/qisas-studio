"""اختبارات انحدار لحارس البيئة (إصلاح 2026-11-22: حل مشكلة التثبيت
بعد إعادة التشغيل). بلا شبكة وبلا تنفيذ فعلي لسكربتات الإصلاح —
الفحص الجاف ومسبار قفل apt يعملان محليًا فقط."""
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
STUDIO = os.path.dirname(HERE)
WORKSPACE = os.path.dirname(STUDIO)
GUARD = os.path.join(WORKSPACE, "ensure-env.sh")
SETUP = os.path.join(WORKSPACE, "setup-env.sh")
RESTORE = os.path.join(WORKSPACE, "restore-system-tools.sh")
UPDATE_DB = os.path.join(WORKSPACE, "update-clamav-db.sh")
STUDIO_PY = os.path.join(STUDIO, "studio.py")

FULL_PATH = ":".join([
    os.path.expanduser("~/.local/bin"),
    os.path.expanduser("~/.npm-global/bin"),
    "/usr/local/bin", "/usr/bin", "/usr/sbin", "/bin", "/sbin",
])


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestGuardDryRun(unittest.TestCase):
    def test_dry_run_healthy(self):
        """بيئة سليمة: الفحص الجاف يخرج 0 ويبلغ OK عن كل شيء."""
        env = dict(os.environ, PATH=FULL_PATH)
        r = subprocess.run(["/bin/bash", GUARD, "--dry-run"],
                           capture_output=True, text=True, env=env,
                           timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("unit: OK", r.stdout)
        self.assertIn("home-tools missing: none", r.stdout)
        self.assertIn("links missing: none", r.stdout)
        self.assertIn("fc-list: OK", r.stdout)
        self.assertIn("python-libs yaml/PIL: OK", r.stdout)
        self.assertIn("apt-tools missing: none", r.stdout)
        self.assertIn("clamav-db: OK", r.stdout)

    def test_dry_run_apt_only_healthy(self):
        env = dict(os.environ, PATH=FULL_PATH)
        r = subprocess.run(["/bin/bash", GUARD, "--apt-only", "--dry-run"],
                           capture_output=True, text=True, env=env,
                           timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("apt-tools missing: none", r.stdout)
        self.assertIn("clamav-db: OK", r.stdout)


class TestAptLockProbe(unittest.TestCase):
    """مسبار قفل apt بـfcntl (لا بـflock — flock لا يرى قفل apt)."""

    def _probe_bash(self, lock_path, held):
        """شغّل دالة apt_lock_held المستخرجة من الحارس نفسه ضد ملف
        قفل مؤقت (ممسوك بـfcntl أو حر)، وأرجع exit code الدالة."""
        src = _read(GUARD)
        m = re.search(r"(?ms)^apt_lock_held\(\) \{.*?^\}", src)
        self.assertIsNotNone(m, "لم تُوجد دالة apt_lock_held في الحارس")
        holder = None
        with tempfile.TemporaryDirectory() as d:
            funcs = os.path.join(d, "funcs.sh")
            with open(funcs, "w", encoding="utf-8") as f:
                f.write(m.group(0) + "\n")
            if held:
                code = (
                    "import fcntl, sys, time\n"
                    "fh = open(sys.argv[1], 'r+')\n"
                    "fcntl.lockf(fh, fcntl.LOCK_EX)\n"
                    "open(sys.argv[2], 'w').write('locked')\n"
                    "time.sleep(15)\n"
                )
                ready = os.path.join(d, "ready")
                holder = subprocess.Popen(
                    [sys.executable, "-c", code, lock_path, ready])
                for _ in range(50):
                    if os.path.exists(ready):
                        break
                    time.sleep(0.1)
                self.assertTrue(os.path.exists(ready),
                                "حامل القفل لم يمسك القفل")
            try:
                script = ("source %s; APT_LOCKS=(%s); "
                          "apt_lock_held; echo $?") % (funcs, lock_path)
                r = subprocess.run(["/bin/bash", "-c", script],
                                   capture_output=True, text=True, timeout=30)
                return int(r.stdout.strip().splitlines()[-1])
            finally:
                if holder is not None:
                    holder.terminate()
                    holder.wait(timeout=5)

    def test_probe_sees_held_lock(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            self.assertEqual(self._probe_bash(path, held=True), 0)
        finally:
            os.unlink(path)

    def test_probe_sees_free_lock(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            self.assertEqual(self._probe_bash(path, held=False), 1)
        finally:
            os.unlink(path)


class TestGuardFixesPresent(unittest.TestCase):
    """الإصلاحات نفسها موجودة في السكربتات (حماية من الانحدار)."""

    def test_guard_checks_symlinks_and_pylibs(self):
        src = _read(GUARD)
        self.assertIn("missing_links", src)
        self.assertIn('readlink "/usr/local/bin/', src)
        self.assertIn("fc-list", src)
        self.assertIn("import yaml, PIL", src)
        self.assertIn("apt_lock_held", src)
        self.assertNotIn('BG_LOG="/tmp/ensure-env-bg.log"', src)
        self.assertIn('BG_LOG="$WORKSPACE/ensure-env-bg.log"', src)

    def test_restore_retries_and_proxy_and_exit_code(self):
        src = _read(RESTORE)
        self.assertIn("apt_retry", src)
        self.assertIn("80hatch-egress-proxy", src)
        self.assertIn("exit $FAILED", src)

    def test_setup_env_serializes_and_covers_extras(self):
        src = _read(SETUP)
        self.assertIn("flock -w 240 9", src)
        self.assertIn("fontconfig", src)
        self.assertIn("python3-yaml", src)
        self.assertIn("python3-pil", src)
        self.assertIn("ensure_apt_proxy", src)
        self.assertIn("/etc/environment", src)

    def test_update_db_proxy_fallback(self):
        self.assertIn("/etc/environment", _read(UPDATE_DB))

    def test_studio_expected_tools_cover(self):
        src = _read(STUDIO_PY)
        self.assertIn('"fc-list"', src)
        self.assertIn('("yaml", "PIL")', src)
        self.assertIn("find_spec", src)

    def test_all_guard_scripts_parse(self):
        for path in (GUARD, SETUP, RESTORE, UPDATE_DB):
            r = subprocess.run(["/bin/bash", "-n", path],
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, "%s: %s" % (path, r.stderr))


if __name__ == "__main__":
    unittest.main()
