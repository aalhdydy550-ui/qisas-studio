#!/usr/bin/env python3
"""التحديث والنسخ الاحتياطي — `studio.py update` و`studio.py backup`.

`update`: يجلب آخر إصدار من مستودع GitHub العام عبر
Contents API (بلا مصادقة) ويطبّق الملفات المتغيرة فقط:
يقارن بصمة git-blob (SHA-1 على «blob <len>\\0<المحتوى>»)
فلا ينزّل إلا الملفات المختلفة فعلًا. قبل أي كتابة تُؤخذ
نسخة احتياطية من الملفات التي ستتغير. وضع `--dry-run`
يطبع ما سيتغير بلا أي كتابة.

ملفات محمية لا تُمسّ أبدًا: config.yaml وyoutube-token.json
وclient_secrets.json وملف الطابور وبيانات العملاء وأي مفاتيح
أو أسرار أو قواعد بيانات، ومجلدات runs/ وbackups/ وqueue/
وclient-orders/ والبيئات الافتراضية.

`backup`: يحفظ config.yaml + الطابور + طلبات العملاء +
سجلات التشغيل (runs/*.json) في ملف zip مؤرخ تحت backups/
مع manifest يعدد المحتويات.
"""
import contextlib
import fcntl
import fnmatch
import hashlib
import json
import os
import secrets
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from lib.paths import resolve_inside

GITHUB_API = "https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"
GITHUB_RAW = "https://raw.githubusercontent.com/{repo}/{branch}/{path}"

# أخطاء HTTP عابرة تستحق إعادة المحاولة مع تراجع تدريجي.
# شوهد 2026-11-22: حدّ GitHub الثانوي على IP الخروج المشترك
# يرد 403 مرتين ثم ينجح في الثالثة بلا أي تغيير — فلا يفشل
# التحديث من أول 403 عابر.
_RETRY_CODES = frozenset({403, 429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 3
_RETRY_DELAYS = (2, 5)  # ثوانٍ قبل المحاولتين 2 و3

PROTECTED_NAMES = {
    "config.yaml", "config.yml", "youtube-token.json",
    "client_secrets.json", ".env", ".env.local",
}
PROTECTED_PATTERNS = ("*.key", "*.pem", "*.token", "*.sqlite",
                      "*.sqlite3", "*.db", ".env*")
PROTECTED_DIRS = {
    "runs", "backups", "queue", "client-orders",
    ".venv-youtube", ".venv-gtts", ".venv-whisper",
    "__pycache__", ".git",
}
MAX_RUN_FILES = 200


class UpdateError(Exception):
    """خطأ في التحديث أو النسخ الاحتياطي (رسالته عربية)."""


def is_protected(rel_path):
    """هل المسار النسبي محمي من التحديث؟

    إصلاح اختبار اختراق 2026-11-22 (L11): المقارنة حساسة لحالة
    الأحرف كانت تترك `CONFIG.YAML` بلا حماية — المقارنة الآن
    بـcasefold() للاسم والأنماط معًا.
    """
    parts = rel_path.replace("\\", "/").split("/")
    if any(p.casefold() in {d.casefold() for d in PROTECTED_DIRS}
           for p in parts[:-1]):
        return True
    name = parts[-1]
    if name.casefold() in {n.casefold() for n in PROTECTED_NAMES}:
        return True
    name_cf = name.casefold()
    return any(fnmatch.fnmatch(name_cf, pat.casefold())
               for pat in PROTECTED_PATTERNS)


def git_blob_sha(data):
    """بصمة git-blob لمحتوى ملف (SHA-1)."""
    header = ("blob %d\0" % len(data)).encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


# L10 (round 4): urlopen follows redirects silently — a compromised or
# hijacked endpoint could redirect the updater to an arbitrary host and have
# its bytes written into the project. Only GitHub's own hosts are ever
# legitimate here (the API for the tree, raw.githubusercontent for files).
_ALLOWED_HTTP_HOSTS = frozenset({"api.github.com", "raw.githubusercontent.com"})


def _http_get(url, timeout=60):
    req = urllib.request.Request(
        url, headers={"User-Agent": "qisas-studio-updater",
                      "Accept": "application/vnd.github+json"})
    for attempt in range(_MAX_ATTEMPTS):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                # L10: verify the FINAL host after redirects — the initial
                # URL is built from trusted constants, the landing host is
                # what actually serves the bytes.
                final = urllib.parse.urlparse(resp.geturl())
                if (final.scheme != "https"
                        or final.hostname not in _ALLOWED_HTTP_HOSTS):
                    raise UpdateError(
                        "إعادة توجيه إلى مضيف غير موثوق: %s"
                        % (final.hostname or "?"))
                return resp.read()
        except UpdateError:
            raise
        except urllib.error.HTTPError as e:
            if e.code in _RETRY_CODES and attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_RETRY_DELAYS[attempt])
                continue
            raise UpdateError("GitHub رد HTTP %s على %s" % (e.code, url))
        except urllib.error.URLError as e:
            raise UpdateError("تعذر الوصول إلى %s: %s" % (url, e.reason))
    raise UpdateError("تعذر الوصول إلى %s بعد %d محاولات"
                      % (url, _MAX_ATTEMPTS))


def fetch_tree(repo, branch, http_get=None):
    """شجرة الملفات البعيدة: {مسار نسبي: بصمة blob}.
    http_get قابلة للحقن في الاختبارات."""
    get = http_get or _http_get
    raw = get(GITHUB_API.format(repo=urllib.parse.quote(repo, safe="/"),
                                branch=urllib.parse.quote(branch,
                                                          safe="/")))
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise UpdateError("رد GitHub للشجرة ليس JSON صالحًا")
    tree = {}
    for entry in data.get("tree") or []:
        if entry.get("type") == "blob":
            tree[entry.get("path")] = entry.get("sha")
    if not tree:
        raise UpdateError("شجرة GitHub فارغة أو بلا ملفات")
    return tree


def fetch_file_raw(repo, branch, path, http_get=None):
    """محتوى ملف بعيد (خام)."""
    get = http_get or _http_get
    return get(GITHUB_RAW.format(
        repo=urllib.parse.quote(repo, safe="/"),
        branch=urllib.parse.quote(branch, safe="/"),
        path=urllib.parse.quote(path, safe="/")))


def plan_update(local_root, tree):
    """قارن الشجرة البعيدة بالملفات المحلية. يرجع قائمة
    {"path", "action": "add"|"update"} للملفات المتغيرة فقط
    (المحمية تُتخطى دائمًا).

    إصلاح اختبار اختراق 2026-11-22: أي مسار في الشجرة يخرج
    من جذر المشروع (‎../‎ أو مسار مطلق أو عبر رابط رمزي)
    يُسقط التحديث كله فورًا بدل كتابته خارج الجذر — فالشجرة
    البعيدة بيانات غير موثوقة تمامًا حتى لو جاءت من GitHub.
    """
    changes = []
    for path in sorted(tree):
        # إصلاح اختبار اختراق 2026-11-22 (L10): مدخل شجرة فارغ
        # أو `.` كان يمرّ من resolve_inside ثم يعطّل التطبيق في
        # منتصفه (كتابة فوق جذر المشروع نفسه) — يُرفض فورًا.
        if (not isinstance(path, str) or not path.strip()
                or path.strip() in (".", "./")):
            raise UpdateError("مدخل شجرة تحديث فارغ أو غير صالح — "
                              "رُفض التحديث: %r" % (path,))
        try:
            local = resolve_inside(
                local_root, os.path.join(local_root, path),
                "مسار في شجرة التحديث")
        except ValueError:
            raise UpdateError("مسار بعيد خارج مجلد المشروع — "
                              "رُفض التحديث: %s" % path)
        if is_protected(path):
            continue
        if not os.path.isfile(local):
            changes.append({"path": path, "action": "add"})
            continue
        with open(local, "rb") as f:
            if git_blob_sha(f.read()) != tree[path]:
                changes.append({"path": path, "action": "update"})
    return changes


def apply_update(local_root, changes, fetch_fn, backup_fn=None,
                 tree=None):
    """طبّق التغييرات: تحقق من البصمات أولًا، ثم نسخة احتياطية
    (إن أُعطيت backup_fn)، ثم كتابة كل ملف بمحتواه البعيد.
    يرجع قائمة المسارات المكتوبة.

    إصلاح اختبار اختراق 2026-11-22 (H1، عالٍ): المحتوى المنزَّل
    كان يُكتب بلا أي مقارنة ببصمة الشجرة، فأي وسيط يبدّل
    `fetch_fn` (أو رد خام مخترَق) كان يحقن كودًا في المشروع.
    إن أُعطيت `tree` تُجلب كل الملفات وتُقارن بصمات git-blob
    بها *قبل أي كتابة أو نسخ احتياطي*؛ وأول عدم مطابقة يوقف
    التحديث كله بلا كتابة أي ملف. بلا `tree` يبقى السلوك القديم
    (للتوافق مع الاستدعاءات الداخلية) لكن المسارات تُفحص كلها
    قبل أي جلب.
    """
    # 1) فحص كل المسارات قبل أي جلب (دفاع ثانٍ: لا كتابة خارج
    # الجذر أبدًا، ولا استدعاء fetch لمسار مرفوض).
    targets = []
    for change in changes:
        try:
            target = resolve_inside(
                local_root, os.path.join(local_root, change["path"]),
                "مسار في شجرة التحديث")
        except ValueError:
            raise UpdateError("مسار بعيد خارج مجلد المشروع — "
                              "رُفض التحديث: %s" % change["path"])
        targets.append(target)
    # 2) جلب كل المحتوى والتحقق من بصماته قبل أي كتابة.
    payloads = []
    for change, target in zip(changes, targets):
        data = fetch_fn(change["path"])
        if tree is not None:
            expected = tree.get(change["path"])
            if expected is None or git_blob_sha(data) != expected:
                raise UpdateError(
                    "بصمة الملف البعيد لا تطابق الشجرة — رُفض التحديث "
                    "كله قبل الكتابة: %s" % change["path"])
        payloads.append((change, target, data))
    if backup_fn is not None:
        existing = [c["path"] for c in changes
                    if os.path.isfile(os.path.join(local_root,
                                                  c["path"]))]
        backup_fn(existing)
    written = []
    for change, target, data in payloads:
        os.makedirs(os.path.dirname(target) or local_root,
                    exist_ok=True)
        # كتابة ذرية: ملف مؤقت بنفس المجلد ثم os.replace.
        fd, tmp = tempfile.mkstemp(
            dir=os.path.dirname(target) or local_root,
            prefix=".update-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, target)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        written.append(change["path"])
    return written


def collect_backup_files(studio_dir, cfg):
    """ملفات النسخ الاحتياطي: (موجودة، مفقودة)."""
    wanted = []
    config_path = os.path.join(studio_dir, "config.yaml")
    wanted.append(("config.yaml", config_path))
    queue_path = os.path.expanduser(
        (cfg.get("paths") or {}).get("queue_file") or "")
    if queue_path:
        wanted.append(("story-queue.md", queue_path))
    orders_dir = os.path.join(studio_dir, "client-orders")
    for name in ("orders.jsonl", "orders.jsonl.bad"):
        wanted.append((os.path.join("client-orders", name),
                       os.path.join(orders_dir, name)))
    runs_dir = os.path.join(studio_dir, "runs")
    run_files = []
    if os.path.isdir(runs_dir):
        for root, _dirs, files in os.walk(runs_dir):
            for name in sorted(files):
                if name.endswith(".json"):
                    full = os.path.join(root, name)
                    # رابط رمزي داخل runs/ قد يشير لملف خارجي
                    # (محتواه يتسرب للنسخة) — يُتخطى.
                    if os.path.islink(full):
                        continue
                    run_files.append(full)
            if len(run_files) >= MAX_RUN_FILES:
                break
    for path in run_files[:MAX_RUN_FILES]:
        wanted.append((os.path.relpath(path, studio_dir), path))
    found, missing = [], []
    for arc, path in wanted:
        if os.path.isfile(path):
            found.append((arc, path))
        else:
            missing.append(arc)
    return found, missing


def _unique_backup_name(prefix):
    """اسم نسخة فريد: طابع زمني + PID + عشوائي.

    إصلاح اختبار اختراق 2026-11-22 (M7): الاسم بدقة ثانية كان
    يتصادم بين 5 نسخ متزامنة فيكتبن ملفًا واحدًا.
    """
    return "%s-%s-%d-%s.zip" % (
        prefix, time.strftime("%Y%m%d-%H%M%S"),
        os.getpid(), secrets.token_hex(4))


@contextlib.contextmanager
def _backup_lock(out_dir):
    """قفل حصري (flock) على مجلد النسخ أثناء توليد الاسم والكتابة."""
    os.makedirs(out_dir, exist_ok=True)
    lock_path = os.path.join(out_dir, ".backup.lock")
    with open(lock_path, "a", encoding="utf-8") as lock_f:
        fcntl.flock(lock_f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)


def _write_zip_atomic(out_dir, zip_name, entries, manifest_lines):
    """اكتب zip ذريًا (ملف مؤقت + os.replace) وبأذونات 600.

    entries: [(arc, path)] ملفات موجودة. يرجع المسار النهائي.
    إصلاح اختبار اختراق 2026-11-22 (L7): ملفات الإخراج كانت
    660 اعتمادًا على umask — النسخ الاحتياطية (وفيها الإعداد
    والطلبات) الآن 600 صراحةً.
    """
    final = os.path.join(out_dir, zip_name)
    fd, tmp = tempfile.mkstemp(dir=out_dir, prefix=".backup-",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as raw:
            with zipfile.ZipFile(raw, "w",
                                 compression=zipfile.ZIP_DEFLATED) as zf:
                for arc, path in entries:
                    zf.write(path, arc)
                zf.writestr("manifest.txt",
                            "\n".join(manifest_lines) + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, final)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return final


def make_pre_update_backup(local_root, paths, out_dir=None):
    """نسخة «قبل التحديث» من الملفات المتغيرة نفسها (كودًا كانت
    أو غيره) — لا الإعداد والطابور فقط.

    إصلاح اختبار اختراق 2026-11-22 (M5): النسخة القديمة
    (make_backup) لم تغطِّ ملفات الكود، فلم يكن هناك تراجع من
    تحديث فاسد. تُستعاد هذه النسخة بأمر `studio.py restore
    --file <zip>` (restore_backup) أو بفك الـzip يدويًا.
    يرجع (مسار الـzip أو None إن لم يوجد ملف قائم، الملفات
    المضمّنة).
    """
    out_dir = out_dir or os.path.join(local_root, "backups")
    entries = []
    for rel in paths or []:
        if is_protected(rel):
            continue
        try:
            full = resolve_inside(
                local_root, os.path.join(local_root, rel),
                "ملف قبل التحديث")
        except ValueError:
            continue
        if os.path.isfile(full) and not os.path.islink(full):
            entries.append((rel.replace("\\", "/"), full))
    if not entries:
        return None, []
    with _backup_lock(out_dir):
        zip_name = _unique_backup_name("pre-update")
        manifest = ["نسخة قبل التحديث — %s\n"
                    % time.strftime("%Y-%m-%d %H:%M:%S")]
        manifest.extend(a for a, _ in entries)
        zip_path = _write_zip_atomic(out_dir, zip_name, entries,
                                     manifest)
    return zip_path, [a for a, _ in entries]


MAX_RESTORE_BYTES = 50 * 1024 * 1024


def restore_backup(zip_path, local_root):
    """استعد ملفات من نسخة «قبل التحديث» (أو أي نسخة zip
    من make_backup/make_pre_update_backup).

    كل مدخل يُفحص: لا مسارات مطلقة ولا `..` ولا ملفات محمية،
    والكتابة ذرية داخل الجذر. يرجع قائمة المسارات المستعادة.
    """
    if not os.path.isfile(zip_path):
        raise UpdateError("ملف النسخة غير موجود: %s" % zip_path)
    restored = []
    total = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        infos = [i for i in zf.infolist()
                 if i.filename != "manifest.txt"
                 and not i.filename.endswith("/")]
        for info in infos:
            name = info.filename.replace("\\", "/")
            parts = [p for p in name.split("/") if p not in ("", ".")]
            if (not parts or any(p == ".." for p in parts)
                    or name.startswith("/")):
                raise UpdateError("مدخل نسخة خارج الجذر — رُفضت "
                                  "الاستعادة: %s" % info.filename)
            if is_protected(name):
                raise UpdateError("مدخل نسخة محمي — رُفضت الاستعادة: "
                                  "%s" % name)
            total += info.file_size
            if total > MAX_RESTORE_BYTES:
                raise UpdateError("حجم النسخة فوق الحد (%d بايت)"
                                  % MAX_RESTORE_BYTES)
        for info in infos:
            name = info.filename.replace("\\", "/")
            target = resolve_inside(
                local_root, os.path.join(local_root, name),
                "ملف مستعاد")
            data = zf.read(info.filename)
            os.makedirs(os.path.dirname(target) or local_root,
                        exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                dir=os.path.dirname(target) or local_root,
                prefix=".restore-", suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                os.replace(tmp, target)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
            restored.append(name)
    return restored


# --- استعادة نسخة مستخدم (الإعداد + الطابور + طلبات العملاء) ---

# ما يجوز استرجاعه من نسخة `backup` فقط — لا كود ولا سجلات تشغيل.
USER_RESTORE_FILES = ("config.yaml", "story-queue.md")
USER_RESTORE_DIRS = ("client-orders",)


def _is_user_restorable(name):
    if name in USER_RESTORE_FILES:
        return True
    return name.split("/")[0] in USER_RESTORE_DIRS


def _is_secret_entry(name):
    """هل المدخل سري لا يُستعاد أبدًا؟ (توكن/أسرار/مفاتيح)."""
    last = name.split("/")[-1]
    if last.casefold() in {"youtube-token.json",
                           "client_secrets.json", ".env",
                           ".env.local"}:
        return True
    name_cf = last.casefold()
    return any(fnmatch.fnmatch(name_cf, pat.casefold())
               for pat in ("*.key", "*.pem", "*.token"))


def _validate_config_yaml(data):
    """تحقق أن config.yaml المستعاد YAML صالح وقاموس — قبل أي كتابة."""
    try:
        import yaml
    except ImportError:
        return  # PyYAML غائب — doctor يبلغ عنه؛ لا نحجب الاسترجاع
    try:
        parsed = yaml.safe_load(data.decode("utf-8"))
    except Exception as e:
        raise UpdateError("config.yaml المستعاد ليس YAML صالحًا: %s"
                          % e)
    if parsed is not None and not isinstance(parsed, dict):
        raise UpdateError("config.yaml المستعاد ليس قاموس إعدادات")


def _check_zip_entry(info):
    """افحص مدخل zip واحد: يرجع اسمه المنظَّف أو None للمجلد/
    manifest، ويرفع UpdateError عند مدخل خارج الجذر أو رابط رمزي."""
    name = info.filename.replace("\\", "/")
    if name.endswith("/") or name == "manifest.txt":
        return None
    # رابط رمزي؟ (نوع الملف في البتات العليا لوضع يونكس)
    if (info.external_attr >> 28) == 0xA:
        raise UpdateError("مدخل نسخة رابط رمزي — رُفضت الاستعادة: %s"
                          % info.filename)
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if (not parts or any(p == ".." for p in parts)
            or name.startswith("/")):
        raise UpdateError("مدخل نسخة خارج الجذر — رُفضت الاستعادة: %s"
                          % info.filename)
    return "/".join(parts)


def plan_user_restore(zip_path, local_root):
    """خطط استعادة نسخة مستخدم: افحص كل المدخلات بلا كتابة.

    يرجع {"restorable": [أسماء], "raw": {اسم: اسم المدخل في الzip},
    "skipped": [أسماء], "total_bytes": n}.
    يرفع UpdateError عند أي مدخل خارج الجذر أو رابط رمزي أو سري،
    أو عند config.yaml غير صالح، أو عند غياب أي ملف قابل للاسترجاع.
    """
    if not os.path.isfile(zip_path):
        raise UpdateError("ملف النسخة غير موجود: %s" % zip_path)
    restorable, skipped, raw = [], [], {}
    total = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            name = _check_zip_entry(info)
            if name is None:
                continue
            if _is_secret_entry(name):
                raise UpdateError("مدخل نسخة سري — الأسرار لا تُستعاد "
                                  "أبدًا: %s" % name)
            if _is_user_restorable(name):
                restorable.append(name)
                raw[name] = info.filename
                total += info.file_size
                if total > MAX_RESTORE_BYTES:
                    raise UpdateError("حجم النسخة فوق الحد (%d بايت)"
                                      % MAX_RESTORE_BYTES)
            else:
                skipped.append(name)
        if "config.yaml" in restorable:
            _validate_config_yaml(zf.read(raw["config.yaml"]))
    if not restorable:
        raise UpdateError("لا ملفات قابلة للاسترجاع في النسخة "
                          "(الإعداد/الطابور/طلبات العملاء غائبة)")
    return {"restorable": restorable, "raw": raw, "skipped": skipped,
            "total_bytes": total}


def apply_user_restore(zip_path, local_root, plan):
    """اكتب الملفات المخططة ذرّيًا داخل الجذر. يرجع قائمة المستعادة."""
    restored = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in plan["restorable"]:
            target = resolve_inside(
                local_root, os.path.join(local_root, name),
                "ملف مستعاد")
            data = zf.read(plan["raw"][name])
            os.makedirs(os.path.dirname(target) or local_root,
                        exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                dir=os.path.dirname(target) or local_root,
                prefix=".restore-", suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                os.replace(tmp, target)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
            restored.append(name)
    return restored


def make_backup(studio_dir, cfg, out_dir=None):
    """أنشئ نسخة احتياطية zip مؤرخة. يرجع (مسار الzip،
    قائمة الملفات المضمّنة، قائمة المفقودة).

    إصلاح اختبار اختراق 2026-11-22 (M7/L7): الاسم الآن فريد
    (طابع + PID + عشوائي) تحت قفل flock، والكتابة ذرية
    (مؤقت + os.replace) وبأذونات 600.
    """
    out_dir = out_dir or os.path.join(studio_dir, "backups")
    found, missing = collect_backup_files(studio_dir, cfg)
    if not found:
        raise UpdateError("لا توجد ملفات للنسخ الاحتياطي")
    with _backup_lock(out_dir):
        zip_name = _unique_backup_name("backup")
        manifest = ["نسخة احتياطية studio — %s\n"
                    % time.strftime("%Y-%m-%d %H:%M:%S")]
        manifest.extend(a for a, _ in found)
        if missing:
            manifest.append("\nمفقود (لم يُضمَّن):")
            manifest.extend(missing)
        zip_path = _write_zip_atomic(out_dir, zip_name, found, manifest)
    return zip_path, [a for a, _ in found], missing
