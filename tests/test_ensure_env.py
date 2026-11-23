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
    @unittest.skipUnless(
        os.path.isfile(os.path.expanduser(
            "~/workspace/studio-env-restore.service")),
        "آلة غير مهيأة (بلا ملف خدمة) — بيئة CI")
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
        # Round 4 (L9): serialization is a mkdir lock dir now, not flock
        # on a predictable /tmp path — still a 240s blocking wait.
        self.assertIn("SETUP_LOCKDIR", src)
        self.assertIn("mkdir \"$SETUP_LOCKDIR\"", src)
        self.assertIn("_lock_waited", src)
        self.assertIn("240", src)
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



class TestRound4EnvFixes(unittest.TestCase):
    """إصلاحات الجولة الرابعة (2026-11-22): H2 وM6 وM7 وL7 وL9."""

    def test_omniroute_bind_uses_hostname(self):
        """H2: الحزمة تقرأ HOSTNAME لا OMNIROUTE_SERVER_HOST (server.js:
        `HOSTNAME || '0.0.0.0'`) — السكربتان والملف ~/.omniroute/.env
        يضبطون HOSTNAME، ويفحصان الربط الفعلي بعد الإقلاع."""
        for path in (GUARD, SETUP):
            src = _read(path)
            self.assertIn("HOSTNAME=127.0.0.1", src, path)
            self.assertIn("omniroute_bind_address", src, path)
            self.assertNotIn(
                "REQUIRE_API_KEY=true OMNIROUTE_SERVER_HOST=127.0.0.1",
                src, path)
            self.assertIn(
                "HOSTNAME=127.0.0.1 OMNIROUTE_SERVER_HOST=127.0.0.1",
                src, path)
        env_path = os.path.expanduser("~/.omniroute/.env")
        if not os.path.isfile(env_path):
            # تأكيدات السكربت أعلاه جرت؛ والملف الحي اختياري.
            raise unittest.SkipTest(
                "~/.omniroute/.env غائب — بيئة CI")
        with open(env_path, encoding="utf-8") as f:
            self.assertIn("HOSTNAME=127.0.0.1", f.read())

    def test_omniroute_bind_address_live(self):
        """H2 حيًا: الدالة المستخرجة من الحارس تقرأ /proc/net/tcp
        وتعيد 127.0.0.1 والخادم شغال."""
        src = _read(GUARD)
        m = re.search(r"(?ms)^omniroute_bind_address\(\) \{.*?^\}", src)
        self.assertIsNotNone(m, "لم تُوجد omniroute_bind_address في الحارس")
        env = dict(os.environ, PATH=FULL_PATH)
        health = subprocess.run(
            ["curl", "-sf", "--max-time", "2",
             "http://127.0.0.1:20128/api/health"],
            capture_output=True, timeout=30, env=env)
        if health.returncode != 0:
            self.skipTest("خادم OmniRoute متوقف — لا يمكن فحص الربط حيًا")
        with tempfile.TemporaryDirectory() as d:
            funcs = os.path.join(d, "funcs.sh")
            with open(funcs, "w", encoding="utf-8") as f:
                f.write(m.group(0) + "\nomniroute_bind_address\n")
            r = subprocess.run(["/bin/bash", funcs], capture_output=True,
                               text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "127.0.0.1")

    def test_clamav_proxy_writes_creds_only_with_at(self):
        """M6 حيًا (محاكاة منطق السكربت نفسه): بروكسي بلا '@' لا يكتب
        بيانات اعتماد وهمية، وبروكسي فيه '@' يكتبها صحيحة."""
        src = _read(UPDATE_DB)
        start = src.index('PROXY="${http_proxy')
        end = src.index('chmod 600 "$CFG"') + len('chmod 600 "$CFG"')
        block = src[start:end] + '\ncat "$CFG"\n'
        cases = [
            ("http://hatch-egress-proxy:3128", False, None, None),
            ("http://user1:s3cret@hatch-egress-proxy:3128",
             True, "user1", "s3cret"),
        ]
        for proxy, want_creds, user, password in cases:
            with tempfile.TemporaryDirectory() as d:
                script = os.path.join(d, "cfg.sh")
                with open(script, "w", encoding="utf-8") as f:
                    f.write("#!/bin/bash\nset -u\n" + block)
                env = {"PATH": "/usr/bin:/bin", "http_proxy": proxy}
                r = subprocess.run(["/bin/bash", script],
                                   capture_output=True, text=True,
                                   env=env, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("HTTPProxyServer hatch-egress-proxy", r.stdout)
            self.assertIn("HTTPProxyPort 3128", r.stdout)
            if want_creds:
                self.assertIn("HTTPProxyUsername %s" % user, r.stdout)
                self.assertIn("HTTPProxyPassword %s" % password, r.stdout)
            else:
                self.assertNotIn("HTTPProxyUsername", r.stdout)
                self.assertNotIn("HTTPProxyPassword", r.stdout)

    def test_proxy_fallback_keeps_inner_quotes(self):
        """L9 حيًا: بديل البروكسي من /etc/environment يزيل زوج علامات
        محيطة واحدًا فقط — كلمة سر فيها علامة اقتباس تبقى سليمة."""
        src = _read(UPDATE_DB)
        start = src.index('if [ -z "${http_proxy')
        end = src.index("\nfi\n", start) + len("\nfi\n")
        snippet = src[start:end]
        with tempfile.TemporaryDirectory() as d:
            env_file = os.path.join(d, "environment")
            with open(env_file, "w", encoding="utf-8") as f:
                f.write('http_proxy="http://user1:p"ss@host:3128"\n')
            snippet = snippet.replace("/etc/environment", env_file)
            script = os.path.join(d, "fb.sh")
            with open(script, "w", encoding="utf-8") as f:
                f.write("#!/bin/bash\nset -u\n" + snippet
                        + 'printf \'%s\' "$http_proxy"\n')
            r = subprocess.run(["/bin/bash", script], capture_output=True,
                               text=True,
                               env={"PATH": "/usr/bin:/bin"}, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, 'http://user1:p"ss@host:3128')

    def test_download_hardening_and_pin(self):
        """M7: curl مقيّد + تحقق SHA256 منشور + npm مثبّت الإصدار."""
        src = _read(SETUP)
        self.assertIn("verify_sha256", src)
        self.assertIn("SHA2-256SUMS", src)
        self.assertIn("sha256sum.txt", src)
        self.assertIn("--fail --proto =https --max-redirs 3 --max-time 60",
                      src)
        self.assertNotIn("curl -L", src)
        self.assertIn("npm install -g omniroute@3.8.54", src)

    def test_verify_sha256_logic_live(self):
        """M7 حيًا: الدالة المستخرجة تقبل ملفًا ببصمة صحيحة وترفض
        ملفًا ببصمة خاطئة (curl يُستبدل بنسخ ملف مجاميع مُعدّ)."""
        import hashlib
        src = _read(SETUP)
        m = re.search(r"(?ms)^verify_sha256\(\) \{.*?^\}", src)
        self.assertIsNotNone(m, "لم تُوجد verify_sha256 في setup-env.sh")
        with tempfile.TemporaryDirectory() as d:
            good = os.path.join(d, "good.bin")
            bad = os.path.join(d, "bad.bin")
            with open(good, "wb") as f:
                f.write(b"good-bytes")
            with open(bad, "wb") as f:
                f.write(b"tampered-bytes")
            digest = hashlib.sha256(b"good-bytes").hexdigest()
            sums = os.path.join(d, "SUMS")
            with open(sums, "w", encoding="utf-8") as f:
                f.write("%s  ./good.bin\n" % digest)
            funcs = os.path.join(d, "funcs.sh")
            with open(funcs, "w", encoding="utf-8") as f:
                f.write(m.group(0) + "\n")
                # stub curl: copy the prepared sums file to the -o target
                f.write('curl() { local out=""; local prev=""; '
                        'for a in "$@"; do '
                        'if [ "$prev" = "-o" ]; then out="$a"; fi; '
                        'prev="$a"; done; '
                        'cp "$SUMS_FILE" "$out"; }\n')
                f.write('export SUMS_FILE="%s"\n' % sums)
                f.write('verify_sha256 "%s" https://example.invalid/SUMS good.bin\n'
                        'echo "good=$?"\n' % good)
                f.write('verify_sha256 "%s" https://example.invalid/SUMS good.bin\n'
                        'echo "bad=$?"\n' % bad)
                f.write('[ -e "%s" ] && echo "bad-still-there" || echo "bad-deleted"\n'
                        % bad)
            r = subprocess.run(["/bin/bash", funcs], capture_output=True,
                               text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("good=0", r.stdout)
        self.assertIn("bad=1", r.stdout)
        self.assertIn("bad-deleted", r.stdout)

    def test_freshclam_config_is_mktemp(self):
        """L7: ملف إعداد freshclam عبر mktemp + umask 077 + حذف عند الخروج."""
        src = _read(UPDATE_DB)
        self.assertIn("mktemp /tmp/freshclam-runtime", src)
        self.assertIn("umask 077", src)
        self.assertIn('trap \'rm -f "$CFG"\' EXIT', src)
        self.assertNotIn("CFG=/tmp/freshclam-runtime.conf", src)

    def test_predictable_locks_and_tmps_gone(self):
        """L9: لا مسارات قفل /tmp متوقعة ولا ملفات .tmp متوقعة،
        وrestore يفشل سريعًا، ولا tr -d '\"' في أي سكربت."""
        guard = _read(GUARD)
        setup = _read(SETUP)
        self.assertNotIn("LOCK_FILE=", guard)
        self.assertNotIn("flock -n 9", guard)
        self.assertNotIn("SETUP_LOCK=", setup)
        self.assertNotIn("flock -w 240 9", setup)
        self.assertIn("lock.d", guard)
        self.assertIn("lock.d", setup)
        self.assertIn("mktemp", guard)
        self.assertIn("set -e", _read(RESTORE))
        self.assertIn("set -o pipefail", _read(RESTORE))
        for path in (SETUP, UPDATE_DB):
            # The old pattern survives only inside explanatory comments;
            # no live code may pipe through tr -d '"'.
            code = "\n".join(
                line for line in _read(path).splitlines()
                if not line.strip().startswith("#"))
            self.assertNotIn("| tr -d '\"'", code, path)


if __name__ == "__main__":
    unittest.main()
