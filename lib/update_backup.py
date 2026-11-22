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
import fnmatch
import hashlib
import json
import os
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
    """هل المسار النسبي محمي من التحديث؟"""
    parts = rel_path.replace("\\", "/").split("/")
    if any(p in PROTECTED_DIRS for p in parts[:-1]):
        return True
    name = parts[-1]
    if name in PROTECTED_NAMES:
        return True
    return any(fnmatch.fnmatch(name, pat)
               for pat in PROTECTED_PATTERNS)


def git_blob_sha(data):
    """بصمة git-blob لمحتوى ملف (SHA-1)."""
    header = ("blob %d\0" % len(data)).encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _http_get(url, timeout=60):
    req = urllib.request.Request(
        url, headers={"User-Agent": "qisas-studio-updater",
                      "Accept": "application/vnd.github+json"})
    for attempt in range(_MAX_ATTEMPTS):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
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


def apply_update(local_root, changes, fetch_fn, backup_fn=None):
    """طبّق التغييرات: نسخة احتياطية أولًا (إن أُعطيت
    backup_fn)، ثم كتابة كل ملف بمحتواه البعيد. يرجع قائمة
    المسارات المكتوبة."""
    if backup_fn is not None:
        existing = [c["path"] for c in changes
                    if os.path.isfile(os.path.join(local_root,
                                                  c["path"]))]
        backup_fn(existing)
    written = []
    for change in changes:
        # دفاع ثانٍ (plan_update يفحص أصلًا): لا كتابة خارج الجذر
        # أبدًا — لا عبر ‎../‎ ولا مسار مطلق ولا رابط رمزي.
        try:
            target = resolve_inside(
                local_root, os.path.join(local_root, change["path"]),
                "مسار في شجرة التحديث")
        except ValueError:
            raise UpdateError("مسار بعيد خارج مجلد المشروع — "
                              "رُفض التحديث: %s" % change["path"])
        data = fetch_fn(change["path"])
        os.makedirs(os.path.dirname(target) or local_root,
                    exist_ok=True)
        with open(target, "wb") as f:
            f.write(data)
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


def make_backup(studio_dir, cfg, out_dir=None):
    """أنشئ نسخة احتياطية zip مؤرخة. يرجع (مسار الzip،
    قائمة الملفات المضمّنة، قائمة المفقودة)."""
    out_dir = out_dir or os.path.join(studio_dir, "backups")
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    zip_path = os.path.join(out_dir, "backup-%s.zip" % ts)
    found, missing = collect_backup_files(studio_dir, cfg)
    if not found:
        raise UpdateError("لا توجد ملفات للنسخ الاحتياطي")
    with zipfile.ZipFile(zip_path, "w",
                         compression=zipfile.ZIP_DEFLATED) as zf:
        manifest = ["نسخة احتياطية studio — %s\n"
                    % time.strftime("%Y-%m-%d %H:%M:%S")]
        for arc, path in found:
            zf.write(path, arc)
            manifest.append(arc)
        if missing:
            manifest.append("\nمفقود (لم يُضمَّن):")
            manifest.extend(missing)
        zf.writestr("manifest.txt", "\n".join(manifest) + "\n")
    return zip_path, [a for a, _ in found], missing
