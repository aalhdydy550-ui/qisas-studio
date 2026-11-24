#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""إدارة بيئات studio الافتراضية — بيئة مشتركة خفيفة + تثبيت كسول للثقيلة.

v0.1.41 — حزمة «ضغطة واحدة + تخفيف ثقل الإعداد».

المشكلة: خمس بيئات افتراضية داخل الشجرة (~984 ميجا) تُنشأ كلها
مقدمًا، وأغلبها لا يحتاجه المستخدم الجديد في أول تشغيل:
- الثقيلة (تُثبَّت كسولًا فقط — عند أول استدعاء لأمرها، لا مقدمًا):
  ``whisper`` ‏(~478M: faster-whisper + ctranslate2 + onnxruntime)
  و``moviepy`` ‏(~269M: moviepy + numpy + حزمة ffmpeg مضمّنة).
- الخفيفة (بيئة واحدة مشتركة تسكن في ``.venv-youtube`` بدل
  ثلاث بيئات): ``gtts`` ‏(~20M) و``youtube`` ‏(~162M)
  و``autoeditor`` ‏(~55M). دمجها آمن: لا تعارض إصدارات بينها
  (لا numpy ولا protobuf مشتركًا بإصدارين مختلفين)، وتوفّر
  ~74 ميجا من قواعد البيئات المتكررة (كل بيئة فارغة ~15M
  أغلبها نسخة pip).

لماذا تسكن المشتركة في ``.venv-youtube`` لا في مجلد جديد؟
لأن هذا الاسم وحده مستثنى أصلًا في ``.gitignore`` وحارس
الأسرار (``lib/secret_guard.py``) وقوائم النسخ الاحتياطي —
فبيئة جديدة باسم آخر كانت ستُمسح بحثًا عن أسرار (ملفات
اكتشاف Google ‏JSON فيها سلاسل طويلة → 618 إصابة كاذبة
وفشل doctor) وتُضمّن في النسخ الاحتياطي. إعادة التسمية
لاحقًا إلى ``.venv-tools`` تحتاج سطرًا واحدًا في كل من تلك
الملفات الثلاثة (خارج ملكية هذه الحزمة — انظر docs/SETUP.md).

التوافق الرجعي: مسارات البيئات القديمة (``.venv-gtts`` و
``.venv-autoeditor``) تبقى صالحة — إما بيئة حقيقية قديمة
(تُحترم كما هي) أو رابط رمزي إلى ``.venv-youtube`` ينشئه
``setup.sh``؛ و``.venv-youtube`` نفسها هي المشتركة. و``doctor``
يفحص ``.venv-youtube/bin/python`` فيمر مباشرة. وآليات
الإصلاح الذاتي الحالية (``setup-env.sh`` + ``ensure-env.sh`` +
خطافا ``~/.bashrc`` و``~/.profile``) لا تمس البيئات أصلًا —
فلا شيء فيها يتغير.

الاستخدام (من جذر studio):
  python3 -m lib.ensure_env check [--json] [--root DIR]
  python3 -m lib.ensure_env install --shared [--dry-run]
  python3 -m lib.ensure_env install whisper [--dry-run]
  python3 -m lib.ensure_env install --all [--dry-run]
  python3 -m lib.ensure_env install --heavy [--dry-run]
  python3 -m lib.ensure_env verify [--shared|--all|TOOL ...]

أنماط AlphaCLI المطبَّقة هنا (تقييم 2026-11-23، §2.7):
- إصدارات مثبّتة لكل حزمة + احتياطي متدرج: فشل المثبّت →
  أحدث إصدار (عجلة أحدث لمنصتك)، وpip نفسه يبني من المصدر
  داخل كل محاولة إن غابت العجلة.
- تثبيت ذري: البيئة الجديدة تُنشأ باسم مؤقت ثم `os.replace`
  إلى اسمها النهائي قبل أي تثبيت حزم؛ والروابط الرمزية تُستبدل
  برابط مؤقت + `os.replace`. (نقل بيئة بعد تثبيت الحزم غير
  آمن: shebang الحزم يحمل المسار المطلق.)
- تحقق SHA-256 للتنزيل (`verify`): كل ملف مثبّت يُقارن
  بمجموعه في RECORD (فشل = إيقاف؛ وغياب بيانات التثبيت =
  تحذير لا تمرير صامت). وفحص `pip show` في `status()` يمنع
  مرور تثبيت مقطوع كجاهز.

الربط الكسول (لمنسق لاحق — سطر واحد في موضع الاستدعاء):
  من ``lib/whisper_captions.py`` أو غيره، قبل استخدام مفسّر
  البيئة الثقيلة: ``ensure_env.ensure("whisper")`` — ينشئ
  البيئة عند أول حاجة فقط ويرجع ``(ok, message)``. هذا الملف
  وحده لا يعدّل أي موضع استدعاء (خارج ملكية هذه الحزمة).

بلا أي أثر جانبي عند الاستيراد، وبلا شبكة إلا عند تثبيت
حزم pip صراحةً (``install`` بلا ``--dry-run``).
"""

import base64
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# البيئة المشتركة للأدوات الخفيفة — تسكن في الاسم التاريخي
# .venv-youtube (انظر سبب التسمية في docstring أعلاه).
SHARED_VENV = ".venv-youtube"

# السجل الوحيد للحقيقة: كل أداة ← بيئتها القديمة، وحزمها، واختبار
# استيرادها، وهل هي ثقيلة (كسولة) أم خفيفة (في البيئة المشتركة).
TOOLS = {
    "gtts": {
        "legacy": ".venv-gtts",
        "group": "tools",
        "packages": ["gtts==2.5.4"],
        "import": "gtts",
        "heavy": False,
        "desc": "صوت gTTS الثاني (اختياري)",
    },
    "youtube": {
        "legacy": ".venv-youtube",
        "group": "tools",
        "packages": [
            "google-api-python-client==2.202.0",
            "google-auth-oauthlib==1.5.0",
            "google-auth-httplib2==0.4.4",
        ],
        "import": "googleapiclient",
        "heavy": False,
        "desc": "النشر على يوتيوب عبر API",
    },
    "autoeditor": {
        "legacy": ".venv-autoeditor",
        "group": "tools",
        "packages": ["auto-editor==29.3.1"],
        "import": "auto_editor",
        "bin": "auto-editor",
        "heavy": False,
        "desc": "القص التلقائي للصمت",
    },
    "whisper": {
        "legacy": ".venv-whisper",
        "group": None,
        "packages": ["faster-whisper==1.2.1"],
        "import": "faster_whisper",
        "heavy": True,
        "desc": "تفريغ الصوت وكتابة الكابشنات (~478M — كسول)",
    },
    "moviepy": {
        "legacy": ".venv-moviepy",
        "group": None,
        "packages": ["moviepy==2.2.1", "arabic-reshaper==3.1.0",
                     "python-bidi==0.6.12"],
        "import": "moviepy",
        "heavy": True,
        "desc": "مؤثرات الفيديو (~269M — كسول)",
    },
}

# أحجام تقريبية مقاسة 2026-11-23 (du) — للرسائل فقط، لا لمنطق.
APPROX_MB = {
    "gtts": 20, "youtube": 162, "autoeditor": 55,
    "whisper": 478, "moviepy": 269,
}


def studio_dir(root=None):
    """جذر studio (يُتجاوز بـ --root في CLI والاختبارات)."""
    return os.path.abspath(root or STUDIO_DIR)


def venv_python_path(venv_dir):
    """مفسّر بيئة ما، أو None إن لم يكن ملفًا تنفيذيًا."""
    p = os.path.join(venv_dir, "bin", "python")
    if os.path.isfile(p) and os.access(p, os.X_OK):
        return p
    return None


def resolve_python(root, name):
    """مفسّر أداة ما أينما كان: بيئتها القديمة أولًا (حقيقية أو
    رابط رمزي)، ثم البيئة المشتركة لأدوات المجموعة الخفيفة.

    يرجع (python_path, where) حيث where في
    {"legacy", "shared", None}.
    """
    root = studio_dir(root)
    spec = TOOLS[name]
    legacy = venv_python_path(os.path.join(root, spec["legacy"]))
    if legacy is not None:
        return legacy, "legacy"
    if spec["group"] is not None:
        shared = venv_python_path(os.path.join(root, SHARED_VENV))
        if shared is not None:
            return shared, "shared"
    return None, None


def target_venv_dir(root, name):
    """مجلد البيئة الذي يُنشأ لأداة ما (المشتركة للخفيفة،
    والقديمة للثقيلة)."""
    root = studio_dir(root)
    spec = TOOLS[name]
    if spec["group"] is not None:
        return os.path.join(root, SHARED_VENV)
    return os.path.join(root, spec["legacy"])


def _import_ok(python, module):
    """هل يستورد مفسّر ما وحدة ما؟ (عملية فرعية قصيرة، بلا شبكة)."""
    try:
        r = subprocess.run(
            [python, "-c", "import %s" % module],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=120, check=False)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _pkg_name(spec):
    """اسم الحزمة من مواصفة pip (بلا قيد إصدار)."""
    for sep in ("==", ">=", "<=", "~=", "!=", ">", "<", "["):
        if sep in spec:
            return spec.split(sep, 1)[0].strip()
    return spec.strip()


def _dist_ok(python, packages):
    """هل بيانات تثبيت الحزم سليمة؟ (``pip show`` لكل حزمة).

    الاستيراد وحده لا يكفي: تثبيت مقطوع (قرص ممتلئ مثلًا) يترك
    ملفات جزئية تستورد بنجاح لكن بياناتها الوصفية تالفة
    (``invalid metadata entry 'name'``) — كُشف ذلك في sandbox
    2026-11-23 عندما امتلأ ‎/tmp (‏tmpfs ‏512M) أثناء التثبيت.
    """
    for spec in packages:
        name = _pkg_name(spec)
        if not name:
            continue
        try:
            r = subprocess.run(
                [python, "-m", "pip", "show", name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return False
        if r.returncode != 0:
            return False
    return True


def status(root, name):
    """حالة أداة واحدة: جاهزة؟ وأين مفسّرها؟

    الجاهزية = الاستيراد ينجح + بيانات التثبيت سليمة
    (``pip show``) — حتى لا يمر تثبيت مقطوع كجاهز.
    """
    root = studio_dir(root)
    spec = TOOLS[name]
    python, where = resolve_python(root, name)
    ready = bool(python) and _import_ok(python, spec["import"]) \
        and _dist_ok(python, spec["packages"])
    return {
        "name": name,
        "desc": spec["desc"],
        "heavy": bool(spec["heavy"]),
        "lazy": bool(spec["heavy"]),
        "ready": ready,
        "python": python,
        "where": where,
        "venv": target_venv_dir(root, name),
        "approx_mb": APPROX_MB.get(name, 0),
    }


def check_all(root=None):
    """حالة كل الأدوات."""
    root = studio_dir(root)
    return {name: status(root, name) for name in TOOLS}


def format_status(statuses):
    """سطور عربية لحالة الأدوات ([PASS]/[MISS]/[LAZY])."""
    lines = []
    for name in TOOLS:
        st = statuses[name]
        if st["ready"]:
            lines.append("[PASS] %s — جاهز (%s)"
                         % (name, st["where"] or "?"))
        elif st["heavy"]:
            lines.append("[LAZY] %s — غير مثبّت (~%dM) — يُثبَّت "
                         "تلقائيًا عند أول استخدام لأمره"
                         % (name, st["approx_mb"]))
        else:
            lines.append("[MISS] %s — غير جاهز (شغّل setup.sh)"
                         % name)
    return lines


def _run(cmd, timeout=1200):
    """شغّل أمرًا وأرجع (ok, آخر سطر من المخرجات)."""
    env = dict(os.environ)
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True,
                           timeout=timeout, env=env, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, "فشل تشغيل الأمر (%s)" % e
    tail = (r.stdout or "").strip().splitlines()
    tail = tail[-1] if tail else ""
    return r.returncode == 0, tail


def _unpinned(packages):
    """مواصفات بلا قيد إصدار (الاحتياطي المتدرج — أحدث إصدار)."""
    return [_pkg_name(p) for p in packages]


def _install_packages(python, packages):
    """ثبّت حزمًا باحتياطي متدرج (نمط AlphaCLI: إصدار مثبّت أولًا).

    المحاولة 1: الإصدارات المثبّتة (عجلات). والمحاولة 2: أحدث
    إصدار بلا قيد (تغطي منصة/بايثون بلا عجلة للإصدار المثبّت).
    وداخل كل محاولة يبني pip نفسه من المصدر (sdist) إن غابت
    العجلة — فالبناء من المصدر هو الاحتياطي الثالث الضمني.
    يرجع (ok, message) — والرسالة تذكر المحاولة الناجحة أو
    خطأي المحاولتين مع تلميح أدوات البناء.

    ملاحظة مساحة: يفكّ pip العجلات في TMPDIR (غالبًا ‎/tmp)،
    و‎/tmp في هذه الـVM ‏tmpfs ‏512M — فتثبيت whisper يملؤه
    ويفشل بـENOSPC رغم فراغ القرص. لذلك يُوجَّه TMPDIR أثناء
    التثبيت إلى مجلد مؤقت تحت البيئة نفسها (قرص واسع) ويُحذف
    بعده، ويُستعاد TMPDIR الأصلي. (اكتُشف 2026-11-23 في
    sandbox التشغيل الكامل --full.)
    """
    if not packages:
        return True, ""
    tmpdir = tempfile.mkdtemp(prefix=".pip-tmp-",
                              dir=os.path.dirname(os.path.dirname(python)))
    old_tmpdir = os.environ.get("TMPDIR")
    os.environ["TMPDIR"] = tmpdir
    try:
        return _install_packages_attempts(python, packages)
    finally:
        if old_tmpdir is None:
            os.environ.pop("TMPDIR", None)
        else:
            os.environ["TMPDIR"] = old_tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)


def _install_packages_attempts(python, packages):
    """محاولتا التثبيت المتدرجتان (يستدعيها _install_packages)."""
    ok, tail1 = _run([python, "-m", "pip", "install", "-q"]
                     + packages)
    if ok:
        return True, "بالإصدارات المثبّتة"
    unpinned = _unpinned(packages)
    if unpinned != packages:
        ok, tail2 = _run([python, "-m", "pip", "install", "-q"]
                         + unpinned)
        if ok:
            return True, ("باحتياطي أحدث إصدار (المثبّت فشل: %s)"
                          % tail1)
        return False, ("فشل المثبّت (%s) وفشل أحدث إصدار (%s) — "
                       "إن كان السبب غياب عجلة لمنصتك فثبّت أدوات "
                       "البناء (sudo apt-get install -y "
                       "build-essential python3-dev) ثم أعد المحاولة"
                       % (tail1, tail2))
    return False, ("تعذّر تثبيت الحزم (%s) — راجع الخطأ وأعد "
                   "المحاولة" % tail1)


def _create_venv_atomic(venv):
    """أنشئ بيئة ذريًا: باسم مؤقت ثم نقلها إلى اسمها النهائي.

    النقل قبل أي تثبيت حزم آمن: ``pyvenv.cfg`` يشير إلى بايثون
    النظام لا إلى مسار البيئة، وسكربتات الحزم تُكتب بعد النقل؛
    وسكربتات venv نفسه (pip/activate) تُصلح مساراتها بعد النقل
    بـ ``_fix_venv_paths``.
    يرجع (ok, message).
    """
    tmp = "%s.tmp-%d" % (venv, os.getpid())
    shutil.rmtree(tmp, ignore_errors=True)
    ok, tail = _run([sys.executable, "-m", "venv", tmp])
    if not ok:
        shutil.rmtree(tmp, ignore_errors=True)
        return False, ("تعذّر إنشاء البيئة %s (%s) — هل حزمة "
                       "python3-venv مثبّتة؟ %s"
                       % (os.path.basename(venv), tail,
                          "sudo apt-get install -y python3-venv"))
    try:
        os.replace(tmp, venv)
    except OSError as e:
        shutil.rmtree(tmp, ignore_errors=True)
        return False, ("تعذّر نقل البيئة إلى %s (%s)"
                       % (os.path.basename(venv), e))
    _fix_venv_paths(tmp, venv)
    return True, ""


def _fix_venv_paths(old, new):
    """أعد كتابة مسار البيئة داخل سكربتاتها بعد النقل الذري.

    إنشاء venv يكتب shebang سكربتاته (pip ‏...) وVIRTUAL_ENV في
    activate بمسار الإنشاء (المؤقت) — وبعد ``os.replace`` يصير
    ذلك المسار ميتًا فينفشل ``bin/pip`` مباشرة. أما ``python -m
    pip`` فيعمل لأنه يستخدم المفسّر نفسه (رابط رمزي لبايثون
    النظام)، وأما سكربتات الحزم المثبّتة بعد النقل فتكتب
    shebangها الصحيح وقت تثبيتها — فيبقى الخلل محصورًا في
    سكربتات venv نفسه، وهذه الدالة تصلحه: تستبدل المسار القديم
    بالجديد في كل ملف نصي عادي تحت ``bin/`` (تتخطى الروابط
    الرمزية) وفي ``pyvenv.cfg``.
    """
    old_b = os.path.abspath(old).encode()
    new_b = os.path.abspath(new).encode()
    for name in ("bin",):
        d = os.path.join(new, name)
        if not os.path.isdir(d):
            continue
        for entry in os.listdir(d):
            p = os.path.join(d, entry)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            try:
                with open(p, "rb") as f:
                    data = f.read()
            except OSError:
                continue
            if old_b in data:
                with open(p, "wb") as f:
                    f.write(data.replace(old_b, new_b))
    cfg = os.path.join(new, "pyvenv.cfg")
    if os.path.isfile(cfg):
        with open(cfg, "rb") as f:
            data = f.read()
        if old_b in data:
            with open(cfg, "wb") as f:
                f.write(data.replace(old_b, new_b))


def _site_packages(python):
    """مجلد site-packages لمفسّر ما، أو None."""
    try:
        r = subprocess.run(
            [python, "-c",
             "import sysconfig; print(sysconfig.get_path('purelib'))"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    path = (r.stdout or "").strip()
    return path or None


def _norm_dist_name(name):
    """طيّ اسم توزيعة للمقارنة (صغير، و-, _, . متكافئة)."""
    out = []
    for ch in name.lower():
        out.append("-" if ch in "-_." else ch)
    return "".join(out)


def _b64_sha256(path):
    """مجموع SHA-256 لملف بصيغة RECORD (base64url بلا حشو)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return base64.urlsafe_b64encode(h.digest()).decode().rstrip("=")


def verify_tool(root, name):
    """تحقق SHA-256 من ملفات بيئة أداة ما عبر RECORD (نمط AlphaCLI).

    يتحقق من **كل** توزيعة في البيئة (الحزمة المباشرة +
    تبعياتها — فتثبيت مقطوع قد يتلف تبعية بينما الحزمة
    المباشرة سليمة)، لا من الحزمة المذكورة وحدها.
    - كل ملف له مجموع في RECORD يُقارن بملفه الفعلي؛ عدم
      المطابقة أو ملف مفقود = فشل (خروج غير صفري).
    - غياب بيانات التثبيت لحزمة مذكورة (لا dist-info أو لا
      RECORD) = تحذير لا تمرير صامت — يُطبع ولا يُسكت عنه.
    - ملفات بلا مجموع (‏.pyc وبعض الملفات المولّدة) تُتخطى
      وتُعدّ في الملخص فقط.
    يرجع (ok, lines).
    """
    if name not in TOOLS:
        return False, ["[FAIL] أداة غير معروفة: %s" % name]
    root = studio_dir(root)
    spec = TOOLS[name]
    python, where = resolve_python(root, name)
    if python is None:
        return False, ["[FAIL] %s — بلا بيئة (غير مثبّت)" % name]
    site = _site_packages(python)
    if site is None:
        return False, ["[FAIL] %s — تعذّر تحديد site-packages" % name]
    ok = True
    lines = []
    checked = 0
    skipped = 0
    try:
        entries = os.listdir(site)
    except OSError as e:
        return False, ["[FAIL] %s — تعذّر قراءة site-packages (%s)"
                       % (name, e)]
    dists = [os.path.join(site, e) for e in entries
             if e.endswith(".dist-info")]
    seen_names = set()
    for dist in sorted(dists):
        meta = os.path.join(dist, "METADATA")
        dist_name = None
        try:
            with open(meta, encoding="utf-8",
                      errors="replace") as f:
                for line in f:
                    if line.lower().startswith("name:"):
                        dist_name = line.split(":", 1)[1].strip()
                        break
        except OSError:
            pass
        if dist_name:
            seen_names.add(_norm_dist_name(dist_name))
        record = os.path.join(dist, "RECORD")
        if not os.path.isfile(record):
            lines.append("[WARN] %s: %s بلا ملف RECORD — تحذير "
                         "لا تمرير صامت"
                         % (name, os.path.basename(dist)))
            continue
        try:
            with open(record, encoding="utf-8", newline="") as f:
                rows = list(csv.reader(f))
        except OSError as e:
            lines.append("[FAIL] %s: تعذّر قراءة RECORD في %s (%s)"
                         % (name, os.path.basename(dist), e))
            ok = False
            continue
        for row in rows:
            if len(row) < 2 or not row[0]:
                continue
            rel, digest = row[0], row[1]
            if not digest or not digest.startswith("sha256="):
                skipped += 1
                continue
            target = os.path.normpath(os.path.join(site, rel))
            if not target.startswith(os.path.normpath(site) + os.sep):
                skipped += 1
                continue
            if not os.path.isfile(target):
                lines.append("[FAIL] %s: ملف مفقود: %s"
                             % (name, rel))
                ok = False
                continue
            try:
                actual = _b64_sha256(target)
            except OSError as e:
                lines.append("[FAIL] %s: تعذّر قراءة %s (%s)"
                             % (name, rel, e))
                ok = False
                continue
            checked += 1
            if actual != digest[len("sha256="):]:
                lines.append("[FAIL] %s: مجموع SHA-256 لا يطابق: %s"
                             % (name, rel))
                ok = False
    for pkg_spec in spec["packages"]:
        if _norm_dist_name(_pkg_name(pkg_spec)) not in seen_names:
            lines.append("[WARN] %s: حزمة %s بلا بيانات تثبيت "
                         "(لا مجموع SHA-256) — تحذير لا تمرير صامت"
                         % (name, _pkg_name(pkg_spec)))
    if ok:
        lines.append("[PASS] %s — تحقق SHA-256: %d ملفًا مطابقًا "
                     "(%d بلا مجموع — متخطاة)"
                     % (name, checked, skipped))
    else:
        lines.append("[FAIL] %s — فشل التحقق من SHA-256 — أعد "
                     "التثبيت" % name)
    return ok, lines


def verify_tools(root, names):
    """تحقق SHA-256 لأدوات عدة — يرجع (ok, lines).

    أدوات تتشارك بيئة واحدة (الخفيفات الثلاث) تُتحقق مرة
    واحدة فقط؛ والتكرار يُسجَّل كمعلومة لا كإعادة عمل.
    """
    ok_all = True
    lines = []
    done_venvs = {}
    for name in names:
        python, _where = resolve_python(studio_dir(root), name)
        if python is not None and python in done_venvs:
            ok_all = ok_all and done_venvs[python]
            lines.append("[INFO] %s — نفس بيئة أداة سابقة "
                         "(تحقق واحد يكفي)" % name)
            continue
        ok, ls = verify_tool(root, name)
        ok_all = ok_all and ok
        if python is not None:
            done_venvs[python] = ok
        lines.extend(ls)
    return ok_all, lines


def ensure(name, root=None, dry_run=False):
    """تأكد أن أداة ما جاهزة، وثبّتها عند الحاجة.

    - الخفيفة: تُثبَّت في البيئة المشتركة ``.venv-youtube``.
    - الثقيلة: تُثبَّت في بيئتها القديمة وحدها (كسولة).
    - بيئة قديمة حقيقية موجودة وجاهزة: تُحترم ولا تُمس.
    - بيئة قديمة موجودة ومعطوبة: لا تُحذف تلقائيًا — يُرجع
      رسالة بالأمر اليدوي (حذف بيانات المستخدم يحتاج قراره).

    يرجع (ok, message عربي). بلا أي تغيير مع dry_run=True.
    """
    if name not in TOOLS:
        return False, "أداة غير معروفة: %s (المتاح: %s)" % (
            name, ", ".join(sorted(TOOLS)))
    root = studio_dir(root)
    spec = TOOLS[name]
    st = status(root, name)
    if st["ready"]:
        return True, "%s جاهز (%s)" % (name, st["where"])
    venv = target_venv_dir(root, name)
    legacy = os.path.join(root, spec["legacy"])
    if spec["group"] is None and os.path.isdir(legacy) \
            and not os.path.islink(legacy):
        # بيئة ثقيلة قديمة موجودة لكن الاستيراد فشل — لا نحذفها.
        return False, ("%s موجود لكنه معطوب (%s) — احذفه يدويًا "
                       "وأعد التثبيت: rm -rf %s && python3 -m "
                       "lib.ensure_env install %s"
                       % (spec["legacy"], st["python"] or "بلا مفسّر",
                          spec["legacy"], name))
    if dry_run:
        return True, ("WOULD: إنشاء %s وتثبيت %s (~%dM)"
                      % (os.path.basename(venv),
                         ", ".join(spec["packages"]),
                         st["approx_mb"]))
    if not os.path.isdir(venv):
        # ذري: إنشاء مؤقت ثم نقل قبل أي تثبيت حزم.
        ok, msg = _create_venv_atomic(venv)
        if not ok:
            return False, msg
    python = venv_python_path(venv)
    if python is None:
        return False, "أُنشئ %s بلا مفسّر python — بيئة تالفة" % venv
    note = ""
    if spec["packages"]:
        ok, msg = _install_packages(python, spec["packages"])
        if not ok:
            return False, "تعذّر تثبيت حزم %s — %s" % (name, msg)
        if "باحتياطي" in msg:
            note = " (%s)" % msg
    if not _import_ok(python, spec["import"]) \
            or not _dist_ok(python, spec["packages"]):
        return False, ("ثُبّت %s لكن التحقق فشل (استيراد أو بيانات "
                       "تثبيت) — تحقق من مساحة القرص وأعد التثبيت"
                       % name)
    return True, "%s جاهز الآن (%s)%s" % (
        name, "shared" if spec["group"] is not None else "legacy",
        note)


def _link_atomic(target, link):
    """أنشئ/استبدل رابطًا رمزيًا ذريًا (مؤقت + os.replace).

    لا نافذة يكون فيها المسار غائبًا — آمن حتى أثناء تشغيل
    نسخة قديمة تستخدم المسار. يرجع (ok, message).
    """
    tmp = "%s.tmp-%d" % (link, os.getpid())
    try:
        if os.path.islink(tmp) or os.path.lexists(tmp):
            os.unlink(tmp)
        os.symlink(target, tmp)
        os.replace(tmp, link)
    except OSError as e:
        try:
            if os.path.islink(tmp):
                os.unlink(tmp)
        except OSError:
            pass
        return False, "تعذّر إنشاء الرابط %s (%s)" % (link, e)
    return True, ""


def link_legacy_aliases(root=None, dry_run=False):
    """أنشئ روابط رمزية من المسارات القديمة للأدوات الخفيفة
    إلى البيئة المشتركة، حتى تبقى مواضع الاستدعاء الحالية
    (``.venv-gtts/bin/python`` …) تعمل بلا تعديل.

    - مسار قديم غير موجود → رابط رمزي إلى ``.venv-youtube``.
    - مسار قديم رابط رمزي صحيح → يُترك كما هو (بلا مساس).
    - مسار قديم رابط رمزي لهدف آخر → يُستبدل ذريًا.
    - مسار قديم بيئة حقيقية → يُترك كما هو (بلا مساس).
    - ``.venv-youtube`` نفسها هي المشتركة → تُتخطى.
    يرجع قائمة (name, action, detail) حيث action في
    {"linked", "kept", "would-link", "failed"}.
    """
    root = studio_dir(root)
    shared = os.path.join(root, SHARED_VENV)
    results = []
    for name in TOOLS:
        spec = TOOLS[name]
        if spec["group"] is None:
            continue
        legacy = os.path.join(root, spec["legacy"])
        if spec["legacy"] == SHARED_VENV:
            results.append((name, "kept",
                            "%s هي البيئة المشتركة نفسها"
                            % spec["legacy"]))
        elif os.path.islink(legacy) \
                and os.readlink(legacy) == SHARED_VENV:
            results.append((name, "kept",
                            "%s رابط رمزي موجود" % spec["legacy"]))
        elif os.path.isdir(legacy) and not os.path.islink(legacy):
            results.append((name, "kept",
                            "%s بيئة حقيقية قديمة — تُحترم"
                            % spec["legacy"]))
        elif os.path.lexists(legacy) and not os.path.islink(legacy):
            results.append((name, "failed",
                            "%s موجود لكنه ليس مجلدًا ولا رابطًا — "
                            "أصلحه يدويًا" % spec["legacy"]))
        elif dry_run:
            results.append((name, "would-link",
                            "WOULD: %s -> %s"
                            % (spec["legacy"], SHARED_VENV)))
        else:
            ok, msg = _link_atomic(SHARED_VENV, legacy)
            if ok:
                results.append((name, "linked",
                                "%s -> %s"
                                % (spec["legacy"], SHARED_VENV)))
            else:
                results.append((name, "failed", msg))
    return results


def ensure_shared(root=None, dry_run=False):
    """ثبّت كل الأدوات الخفيفة في البيئة المشتركة + الروابط.

    يرجع (ok, lines) — ok صحيح فقط إن صارت الأدوات الثلاث
    جاهزة (أو كانت جاهزة).
    """
    root = studio_dir(root)
    lines = []
    ok_all = True
    for name in TOOLS:
        if TOOLS[name]["group"] is None:
            continue
        ok, msg = ensure(name, root=root, dry_run=dry_run)
        ok_all = ok_all and ok
        lines.append(("[PASS] " if ok else "[FAIL] ") + msg)
    for _name, action, detail in link_legacy_aliases(
            root=root, dry_run=dry_run):
        if action == "failed":
            ok_all = False
            lines.append("[FAIL] " + detail)
        else:
            lines.append("[INFO] " + detail)
    return ok_all, lines


def disk_free_mb(path):
    """مساحة القرص الحرة (ميجا) عند مسار ما، أو -1 إن تعذّر القياس."""
    try:
        st = os.statvfs(path)
        return st.f_bavail * st.f_frsize // (1024 * 1024)
    except OSError:
        return -1


def _parse_args(argv):
    """حلّل وسيطات CLI — يرجع (cmd, opts) أو يرفع ValueError."""
    opts = {"root": None, "dry_run": False, "json": False,
            "shared": False, "all": False, "heavy": False,
            "tools": []}
    cmd = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "check":
            cmd = "check"
        elif a == "install":
            cmd = "install"
        elif a == "verify":
            cmd = "verify"
        elif a == "--root":
            i += 1
            if i >= len(argv):
                raise ValueError("--root يحتاج مسارًا")
            opts["root"] = argv[i]
        elif a.startswith("--root="):
            opts["root"] = a.split("=", 1)[1]
        elif a == "--dry-run":
            opts["dry_run"] = True
        elif a == "--json":
            opts["json"] = True
        elif a == "--shared":
            opts["shared"] = True
        elif a == "--all":
            opts["all"] = True
        elif a == "--heavy":
            opts["heavy"] = True
        elif a in ("-h", "--help"):
            cmd = "help"
        elif a.startswith("-"):
            raise ValueError("وسيط غير معروف: %s" % a)
        else:
            opts["tools"].append(a)
        i += 1
    if cmd is None:
        raise ValueError("الاستخدام: check | install [--shared|--all|"
                         "--heavy|TOOL ...] [--dry-run] | verify "
                         "[--shared|--all|TOOL ...] [--root DIR]")
    return cmd, opts


def _usage():
    return ("الاستخدام:\n"
            "  python3 -m lib.ensure_env check [--json] [--root DIR]\n"
            "  python3 -m lib.ensure_env install --shared [--dry-run]\n"
            "  python3 -m lib.ensure_env install TOOL ... [--dry-run]\n"
            "  python3 -m lib.ensure_env install --all | --heavy\n"
            "  python3 -m lib.ensure_env verify [--shared|--all|"
            "TOOL ...]\n"
            "\nالأدوات: gtts youtube autoeditor (خفيفة، مشتركة)؛ "
            "whisper moviepy (ثقيلة، كسولة).")


def _select_names(opts):
    """أسماء الأدوات من أعلام --shared/--all/--heavy أو المواضع."""
    if opts["all"]:
        return list(TOOLS)
    if opts["heavy"]:
        return [n for n in TOOLS if TOOLS[n]["heavy"]]
    if opts["shared"]:
        return [n for n in TOOLS if TOOLS[n]["group"] is not None]
    return list(opts["tools"])


def main(argv=None):
    """نقطة دخول CLI — خروج 0 جاهز/نجح، و1 فشل جزئي، و2 سوء استخدام."""
    try:
        cmd, opts = _parse_args(list(sys.argv[1:] if argv is None
                                     else argv))
    except ValueError as e:
        print("خطأ: %s" % e, file=sys.stderr)
        print(_usage(), file=sys.stderr)
        return 2
    if cmd == "help":
        print(_usage())
        return 0
    root = studio_dir(opts["root"])
    if cmd == "check":
        statuses = check_all(root)
        if opts["json"]:
            print(json.dumps(statuses, ensure_ascii=False, indent=2))
        else:
            for line in format_status(statuses):
                print(line)
        missing_light = [n for n in TOOLS
                         if not TOOLS[n]["heavy"]
                         and not statuses[n]["ready"]]
        return 0 if not missing_light else 1
    if cmd == "verify":
        names = _select_names(opts)
        if not names:
            print("خطأ: حدّد أداة أو --shared أو --all أو --heavy",
                  file=sys.stderr)
            print(_usage(), file=sys.stderr)
            return 2
        unknown = [n for n in names if n not in TOOLS]
        if unknown:
            print("خطأ: أداة غير معروفة: %s (المتاح: %s)"
                  % (", ".join(unknown), ", ".join(sorted(TOOLS))),
                  file=sys.stderr)
            return 2
        ok_all, lines = verify_tools(root, names)
        for line in lines:
            print(line)
        return 0 if ok_all else 1
    # install
    names = _select_names(opts)
    if not names:
        print("خطأ: حدّد أداة أو --shared أو --all أو --heavy",
              file=sys.stderr)
        print(_usage(), file=sys.stderr)
        return 2
    unknown = [n for n in names if n not in TOOLS]
    if unknown:
        print("خطأ: أداة غير معروفة: %s (المتاح: %s)"
              % (", ".join(unknown), ", ".join(sorted(TOOLS))),
              file=sys.stderr)
        return 2
    ok_all = True
    if opts["shared"] and not opts["tools"] and not opts["all"] \
            and not opts["heavy"]:
        ok_all, lines = ensure_shared(root=root,
                                      dry_run=opts["dry_run"])
        for line in lines:
            print(line)
        return 0 if ok_all else 1
    for name in names:
        ok, msg = ensure(name, root=root, dry_run=opts["dry_run"])
        ok_all = ok_all and ok
        print(("[PASS] " if ok else "[FAIL] ") + msg)
    if any(TOOLS[n]["group"] is not None for n in names):
        for _n, action, detail in link_legacy_aliases(
                root=root, dry_run=opts["dry_run"]):
            if action == "failed":
                ok_all = False
                print("[FAIL] " + detail)
            else:
                print("[INFO] " + detail)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
