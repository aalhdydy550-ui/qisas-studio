#!/usr/bin/env python3
"""بيان مصدر الفيديو — جولة v0.1.37 (مقترح tinker رقم 2).

كل فيديو ينتجه studio يحمل ملفًا جانبيًا `<الفيديو>.manifest.json`
يوثق مصدره: العنوان والهوك والعبرة والقصة والمشاهد والعبارات
والسرد (الصوت والسرعة) وبصمة SHA-256 للملف النهائي.

قاعدة grandfather (من التقرير): فيديوهات ما قبل v0.1.37
(عائشة ج1، النجار، منقشة ج2...) بلا بيان — تُعامل كـ legacy:
تحذير فقط في `check` و`publish`، لا فشل أبدًا. الفيديو
الجديد (معدَّل بعد `LEGACY_CUTOFF`) بلا بيان يُرفض نشره
إلا بتجاوز صريح `--allow-missing-manifest`.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from lib import check as check_lib

SCHEMA_VERSION = 1

def _legacy_cutoff():
    """حد Legacy: وقت إنشاء وحدة البيان نفسها.

    أي فيديو أقدم من الميزة (معدَّل قبل وجودها على القرص)
    فهو legacy: بلا بيان، تحذير فقط. فيديو أحدث بلا بيان
    فهو جديد — يُرفض نشره. الحد ذاتي المعايرة: لا تاريخ
    مكتوبًا يدويًا يفسد إن تأخر الإصدار؛ وإن عُدّلت الوحدة
    لاحقًا تحرك الحد للأمام (تساهل فقط، لا تشديد أبدًا).
    """
    try:
        mtime = os.path.getmtime(os.path.abspath(__file__))
        return datetime.fromtimestamp(mtime, tz=timezone.utc)
    except OSError:
        return datetime(2026, 11, 22, 18, 0, 0,
                        tzinfo=ZoneInfo("Africa/Cairo"))


LEGACY_CUTOFF = _legacy_cutoff()

REQUIRED_FIELDS = ("schema_version", "video", "title", "hook",
                   "created_at", "source")

CAIRO = ZoneInfo("Africa/Cairo")


def now_cairo_iso():
    return datetime.now(tz=CAIRO).isoformat(timespec="seconds")


def manifest_path_for(video_path):
    """مسار ملف البيان الجانبي لفيديو."""
    return os.path.abspath(os.path.expanduser(video_path)) + ".manifest.json"


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(video_path, *, title, hook, story=None, moral=None,
                   source="studio", scenes=None, phrases=None,
                   narration=None, extra=None):
    """ابنِ بيان فيديو من بياناته (لا يكتبه على القرص).

    video_path يجب أن يكون موجودًا — تُقرأ منه البصمة والمدة
    والمقاس عبر ffprobe. scenes: قائمة {scene,start,end,duration}
    أو نصوص؛ phrases: قائمة {start,end,text} من بيان الإنتاج.
    """
    video_path = os.path.abspath(os.path.expanduser(video_path))
    if not os.path.isfile(video_path):
        raise FileNotFoundError(
            "ملف الفيديو غير موجود: %s" % video_path)
    info = check_lib.probe(video_path)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "video": {
            "file": os.path.basename(video_path),
            "sha256": sha256_file(video_path),
            "duration_seconds": round(info["duration"], 3),
            "size_bytes": os.path.getsize(video_path),
            "width": info.get("width"),
            "height": info.get("height"),
        },
        "title": title or "",
        "hook": hook or "",
        "story": story or "",
        "moral": moral or "",
        "source": source,
        "created_at": now_cairo_iso(),
        "created_by": "studio.py v0.1.37",
        "scenes": scenes or [],
        "phrases": phrases or [],
        "narration": narration or {},
    }
    if extra:
        manifest["extra"] = extra
    return manifest


def write_manifest(video_path, manifest):
    """اكتب البيان الجانبي؛ ارجع مساره."""
    path = manifest_path_for(video_path)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    return path


def load_manifest(video_path):
    """اقرأ البيان الجانبي؛ None إن غاب أو تعذرت قراءته."""
    path = manifest_path_for(video_path)
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def is_legacy_video(video_path):
    """هل الفيديو من عصر ما قبل البيان (mtime قبل الحد الفاصل)؟"""
    try:
        mtime = os.path.getmtime(
            os.path.abspath(os.path.expanduser(video_path)))
    except OSError:
        return True
    return (datetime.fromtimestamp(mtime, tz=timezone.utc)
            < LEGACY_CUTOFF)


def verify_manifest(video_path, manifest=None):
    """تحقق من بيان فيديو.

    يرجع (الحالة، قائمة مشكلات):
    - "ok": البيان موجود وسليم والبصمة مطابقة.
    - "legacy": لا بيان والفيديو قديم (تحذير فقط، لا فشل أبدًا).
    - "missing": لا بيان والفيديو جديد (يُرفض النشر).
    - "mismatch": البيان موجود لكن البصمة لا تطابق (الفيديو
      تغيّر بعد كتابة البيان — ربما إضافة شعار؛ تحذير).
    - "invalid": البيان موجود لكنه ناقص/مشوَّه.
    """
    manifest = manifest if manifest is not None \
        else load_manifest(video_path)
    if manifest is None:
        if is_legacy_video(video_path):
            return ("legacy",
                    ["لا يوجد بيان مصدر — فيديو قديم (legacy بلا بيان)"])
        return ("missing",
                ["لا يوجد بيان مصدر — الفيديو جديد بلا بيان "
                 "(ولّده بـ: python3 studio.py manifest --video <ملف>)"])
    issues = []
    for field in REQUIRED_FIELDS:
        if not manifest.get(field):
            issues.append("حقل ناقص في البيان: %s" % field)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        issues.append("إصدار بيان غير معروف: %s"
                      % manifest.get("schema_version"))
    if issues:
        return ("invalid", issues)
    video = manifest.get("video") or {}
    try:
        actual = sha256_file(video_path)
    except OSError as e:
        return ("invalid", ["تعذرت قراءة الفيديو للبصمة: %s" % e])
    if video.get("sha256") and video["sha256"] != actual:
        return ("mismatch",
                ["بصمة البيان لا تطابق الفيديو الحالي — الفيديو "
                 "تغيّر بعد كتابة البيان (ربما إضافة شعار)"])
    return ("ok", [])
