#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""بيان مفتاح-محتوى لمراحل خط الإنتاج — نمط Next.js §3 (1) و(2)،
مُعاد تنفيذه من الصفر بالمكتبة القياسية فقط (لا كود منقول).

الفكرة: خط الإنتاج فيه أربع مراحل مكلفة قابلة للتخزين بنفس
منطق طبقات التخزين في Next.js — نص Gemini ← صوت Piper ← مشاهد
مُصيَّرة ← فيديو مُجمَّع — كل مرحلة تُخزَّن بمفتاح hash مدخلاتها
وتُعاد فقط عند تغيّر المدخل (إبطال بالمحتوى)، لا بإعادة تشغيل
الخط كاملًا. هذا البيان مختلف عن `lib/manifest.py`: ذاك بيان
مصدر فيديو واحد جاهز (عنوان/هوك/بصمة ملف نهائي)، وهذا بيان
تخزين مؤقت لمراحل وسيطة أثناء الإنتاج.

والمصغّرات (thumbnails) على النمط نفسه: تُولَّد مرة واحدة لكل
مجموعة (المصدر + العرض + الارتفاع + الجودة + الصيغة) وتُحفظ
بمفتاح مشتق من محتوى المصدر، مع نسخ WebP/AVIF مسبقة بأحجام
ثابتة بدل صيغة واحدة كبيرة.

هذه الوحدة أداة يستدعيها الخط فقط — لا تغيّر أي مخرج ريندر
حالي، ولا تستدعي Gemini أو Piper أو ffmpeg بنفسها: التوليد
الفعلي (والترميز إلى WebP/AVIF) يبقى على المتصل، وهنا فقط
حساب المفاتيح وتسجيل النتائج والتحقق من الإصابة. التوصيل في
`studio.py` يطبقه المنسق (انظر تقرير W5a لنقاط الربط المقترحة).

التخزين: مجلد جذر واحد يحوي `manifest.json` (البيان) ومجلدًا
لكل مرحلة. الكتابة ذرّية (ملف مؤقت + `os.replace`)؛ وبيان
تالف يُعامل كبيان فارغ (لا يفشل الخط أبدًا بسببه).
"""
import hashlib
import json
import os
import shutil
import time

SCHEMA_VERSION = 1

# مراحل الخط بالترتيب (نفس أسماء المراحل في تقرير المسح).
STAGES = ("script", "audio", "scenes", "video")

# أحجام المصغّرات الثابتة: غلاف أفقي، وعمودي للشورت، وصغير.
THUMBNAIL_SIZES = ((1280, 720), (720, 1280), (640, 360))
THUMBNAIL_FORMATS = ("webp", "avif")
DEFAULT_THUMBNAIL_QUALITY = 80

_MANIFEST_NAME = "manifest.json"


class StageCacheError(Exception):
    """خطأ في بيان مراحل التخزين (رسالته عربية جاهزة للعرض)."""


def _canonical(value):
    """تسلسل قانوني لقيمة مدخلات (قواميس مرتبة المفاتيح)."""
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as e:
        raise StageCacheError(
            "مدخلات المرحلة غير قابلة للتسلسل القانوني: %s" % e)


def content_hash(value):
    """بصمة SHA-256 لقيمة مدخلات (نص/بايتات/قاموس/قائمة/عدد).

    القواميس تُسلسل بمفاتيح مرتبة فلا يؤثر ترتيب المفاتيح في
    البصمة؛ والبايتات تُبصم خامًا. أي تغيّر في المدخل — ولو
    حرف واحد — يغيّر البصمة (إبطال بالمحتوى).
    """
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        raw = value.encode("utf-8")
    else:
        raw = _canonical(value)
    return hashlib.sha256(raw).hexdigest()


def hash_file(path):
    """بصمة SHA-256 لمحتوى ملف (قراءة مجزأة — تصلح للفيديو)."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage_key(stage, inputs):
    """مفتاح مرحلة: بصمة (إصدار المخطط + اسم المرحلة + المدخلات)."""
    if stage not in STAGES:
        raise StageCacheError("مرحلة غير معروفة: %s (المراحل: %s)"
                              % (stage, ", ".join(STAGES)))
    return content_hash({"schema": SCHEMA_VERSION,
                         "stage": stage, "inputs": inputs})


def _source_hash(source):
    """بصمة مصدر مصغّرة: ملف موجود → بصمة محتواه؛ وإلا بصمة القيمة."""
    if isinstance(source, bytes):
        return content_hash(source)
    text = str(source)
    if os.path.isfile(text):
        return hash_file(text)
    return content_hash(text)


def thumbnail_key(source, width, height, quality=DEFAULT_THUMBNAIL_QUALITY,
                  fmt="webp"):
    """مفتاح مصغّرة: بصمة (محتوى المصدر + العرض + الارتفاع +
    الجودة + الصيغة). الصيغة تُطبَّع إلى أحرف صغيرة."""
    fmt = str(fmt).lower()
    if fmt not in THUMBNAIL_FORMATS and fmt != "jpg":
        raise StageCacheError("صيغة مصغّرة غير مدعومة: %s" % fmt)
    if width <= 0 or height <= 0:
        raise StageCacheError("أبعاد المصغّرة يجب أن تكون موجبة: %dx%d"
                              % (width, height))
    if not 1 <= int(quality) <= 100:
        raise StageCacheError("جودة المصغّرة بين 1 و100: %s" % quality)
    return content_hash({"schema": SCHEMA_VERSION,
                         "source": _source_hash(source),
                         "width": int(width), "height": int(height),
                         "quality": int(quality), "format": fmt})


def thumbnail_filename(key, fmt="webp"):
    """اسم ملف حتمي لمصغّرة من مفتاحها (بلا مسارات)."""
    return "%s.%s" % (key, str(fmt).lower())


def default_root():
    """جذر التخزين الافتراضي (خارج الشجرة — لا يُدفع معها)."""
    return os.path.join(os.path.expanduser("~"), ".cache",
                        "qisas-studio", "stage-cache")


class StageCache:
    """بيان تخزين مؤقت لمراحل الخط والمصغّرات في مجلد جذر واحد."""

    def __init__(self, root=None):
        self.root = os.path.abspath(os.path.expanduser(
            root or default_root()))
        self.manifest_path = os.path.join(self.root, _MANIFEST_NAME)
        os.makedirs(self.root, exist_ok=True)
        self._entries = self._load()

    # ---------------------------------------------------------- البيان
    def _load(self):
        try:
            with open(self.manifest_path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        if data.get("schema_version") != SCHEMA_VERSION:
            return {}
        entries = data.get("entries")
        return entries if isinstance(entries, dict) else {}

    def _save(self):
        data = {"schema_version": SCHEMA_VERSION,
                "entries": self._entries}
        tmp = self.manifest_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2,
                      sort_keys=True)
        os.replace(tmp, self.manifest_path)

    def _entry(self, key):
        entry = self._entries.get(key)
        if not entry:
            return None
        output = entry.get("output")
        if not output or not os.path.isfile(output):
            # ناتج مسجّل لكن ملفه غائب (حُذف يدويًا) — إصابة باطلة.
            return None
        return entry

    # ---------------------------------------------------------- المراحل
    def lookup(self, stage, inputs):
        """مسار الناتج المخزّن للمرحلة والمدخلات، أو None عند الغياب.

        الإصابة تعني: نفس المدخلات حرفيًا (نفس البصمة) + ملف
        الناتج ما زال موجودًا. أي تغيّر في المدخل يغيّر المفتاح
        فلا إصابة — إبطال بالمحتوى.
        """
        key = stage_key(stage, inputs)
        entry = self._entry(key)
        return entry["output"] if entry else None

    def is_fresh(self, stage, inputs):
        """صحيح إن كان ناتج المرحلة مخزّنًا وصالحًا للمدخلات."""
        return self.lookup(stage, inputs) is not None

    def store(self, stage, inputs, src_path, extra=None):
        """انسخ ناتج مرحلة إلى مجلد التخزين وسجّله؛ ارجع مسار النسخة.

        النسخة المخزّنة تحت `root/<stage>/<key>/output<ext>`؛ وإن
        كانت مسجّلة أصلًا بنفس المفتاح والناتج موجود رُجعت كما هي
        (لا نسخ مكرر). للفيديو النهائي الكبير استخدم `record`
        بدل النسخ.
        """
        key = stage_key(stage, inputs)
        if not os.path.isfile(src_path):
            raise StageCacheError("ناتج المرحلة غير موجود: %s" % src_path)
        entry = self._entry(key)
        if entry:
            return entry["output"]
        _ext = os.path.splitext(src_path)[1]
        dest_dir = os.path.join(self.root, stage, key)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, "output" + _ext)
        shutil.copyfile(src_path, dest)
        self._record(key, stage, inputs, dest, extra)
        return dest

    def record(self, stage, inputs, output_path, extra=None):
        """سجّل ناتج مرحلة في مكانه الحالي بلا نسخ (للمخرجات الكبيرة).

        يسجّل المسار المطلق كما هو؛ والإصابة لاحقًا مشروطة ببقاء
        الملف في مكانه.
        """
        key = stage_key(stage, inputs)
        output_path = os.path.abspath(os.path.expanduser(output_path))
        if not os.path.isfile(output_path):
            raise StageCacheError("ناتج المرحلة غير موجود: %s"
                                  % output_path)
        self._record(key, stage, inputs, output_path, extra)
        return output_path

    def _record(self, key, stage, inputs, output_path, extra=None):
        try:
            size = os.path.getsize(output_path)
        except OSError:
            size = None
        self._entries[key] = {
            "stage": stage,
            "inputs_hash": content_hash(inputs),
            "output": output_path,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "size_bytes": size,
            "extra": extra or {},
        }
        self._save()

    def invalidate(self, stage, inputs=None):
        """أبطل إدخال مرحلة (بمدخلات محددة) أو المرحلة كلها.

        يرجع عدد الإدخالات المُبطلة؛ وحذف الملفات المخزّنة
        (store) فقط — الملفات المسجّلة في مكانها (record) يبقى
        ملفها ولا يُحذف.
        """
        if stage not in STAGES and stage != "thumbnails":
            raise StageCacheError("مرحلة غير معروفة: %s" % stage)
        removed = 0
        if inputs is None:
            keys = [k for k, e in self._entries.items()
                    if e.get("stage") == stage]
        elif stage == "thumbnails":
            # المصغّرات تُبطل بالمرحلة كلها أو بـ clear؛ مفتاحها
            # يُحسب من (المصدر + الأبعاد + الجودة + الصيغة) لا من
            # مدخلات مرحلة — فلا إبطال مفرد بمدخلات هنا.
            raise StageCacheError(
                "إبطال مصغّرة مفردة غير مدعوم — استخدم invalidate"
                "(\"thumbnails\") للمرحلة كلها")
        else:
            key = stage_key(stage, inputs)
            keys = [key] if key in self._entries else []
        for key in keys:
            entry = self._entries.pop(key, None)
            if entry is None:
                continue
            removed += 1
            output = entry.get("output") or ""
            if output.startswith(os.path.join(self.root, stage) + os.sep):
                try:
                    os.remove(output)
                    parent = os.path.dirname(output)
                    if not os.listdir(parent):
                        os.rmdir(parent)
                except OSError:
                    pass
        if removed:
            self._save()
        return removed

    # -------------------------------------------------------- المصغّرات
    def lookup_thumbnail(self, source, width, height,
                         quality=DEFAULT_THUMBNAIL_QUALITY, fmt="webp"):
        """مسار المصغّرة المخزّنة للمجموعة، أو None إن لم تُولَّد بعد."""
        key = thumbnail_key(source, width, height, quality, fmt)
        entry = self._entry(key)
        return entry["output"] if entry else None

    def store_thumbnail(self, source, width, height, src_path,
                        quality=DEFAULT_THUMBNAIL_QUALITY, fmt="webp",
                        extra=None):
        """انسخ مصغّرة مولّدة إلى التخزين وسجّلها؛ ارجع مسار النسخة.

        المصغّرات تُخزَّن تحت `root/thumbnails/<key>.<fmt>` — نسخة
        واحدة لكل مجموعة (مصدر + أبعاد + جودة + صيغة)، فلا تُعاد
        توليدها في كل تشغيل.
        """
        key = thumbnail_key(source, width, height, quality, fmt)
        if not os.path.isfile(src_path):
            raise StageCacheError("ملف المصغّرة غير موجود: %s" % src_path)
        entry = self._entry(key)
        if entry:
            return entry["output"]
        dest_dir = os.path.join(self.root, "thumbnails")
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, thumbnail_filename(key, fmt))
        shutil.copyfile(src_path, dest)
        self._entries[key] = {
            "stage": "thumbnails",
            "inputs_hash": key,
            "output": dest,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "size_bytes": os.path.getsize(dest),
            "extra": dict(extra or {}, width=width, height=height,
                          quality=quality, format=str(fmt).lower()),
        }
        self._save()
        return dest

    def thumbnail_variants(self, source, quality=DEFAULT_THUMBNAIL_QUALITY,
                           formats=THUMBNAIL_FORMATS):
        """مفاتيح/مسارات النسخ المسبقة الثابتة لمصدر (WebP/AVIF × الأحجام).

        ترجع قاموسًا {(العرض، الارتفاع، الصيغة): مسار أو None} —
        يولّد المتصل ما غاب منها فقط ويسجّله بـ store_thumbnail.
        """
        out = {}
        for (width, height) in THUMBNAIL_SIZES:
            for fmt in formats:
                key = thumbnail_key(source, width, height, quality, fmt)
                entry = self._entry(key)
                out[(width, height, fmt)] = (
                    entry["output"] if entry else None)
        return out

    # ------------------------------------------------------------ صيانة
    def stats(self):
        """إحصاءات البيان: عدد الإدخالات وحجمها وتوزيعها على المراحل."""
        by_stage = {}
        total_bytes = 0
        for entry in self._entries.values():
            stage = entry.get("stage", "?")
            by_stage[stage] = by_stage.get(stage, 0) + 1
            total_bytes += entry.get("size_bytes") or 0
        return {"entries": len(self._entries),
                "total_bytes": total_bytes, "stages": by_stage,
                "root": self.root}

    def prune(self, max_bytes=None, max_age_seconds=None):
        """احذف أقدم الإدخالات حتى البقاء ضمن الميزانية/العمر.

        يرجع قائمة مفاتيح الإدخالات المحذوفة. الملفات المسجّلة
        في مكانها (record) يُلغى تسجيلها فقط ولا يُحذف ملفها.
        """
        now = time.time()
        keys = sorted(
            self._entries,
            key=lambda k: self._entries[k].get("created_at", ""))
        removed = []
        total = sum(e.get("size_bytes") or 0
                    for e in self._entries.values())
        for key in keys:
            entry = self._entries.get(key)
            if entry is None:
                continue
            too_old = (max_age_seconds is not None
                       and _age_seconds(entry.get("created_at"), now)
                       > max_age_seconds)
            over = (max_bytes is not None and total > max_bytes
                    and len(self._entries) > 1)
            if not (too_old or over):
                continue
            self._entries.pop(key, None)
            total -= entry.get("size_bytes") or 0
            removed.append(key)
            output = entry.get("output") or ""
            if output.startswith(self.root + os.sep):
                try:
                    os.remove(output)
                    parent = os.path.dirname(output)
                    if os.path.isdir(parent) and not os.listdir(parent):
                        os.rmdir(parent)
                except OSError:
                    pass
        if removed:
            self._save()
        return removed

    def clear(self, stage=None):
        """امسح البيان كاملًا (أو مرحلة واحدة)؛ يرجع عدد المحذوفات."""
        if stage is None:
            count = len(self._entries)
            self._entries = {}
            self._save()
            for name in STAGES + ("thumbnails",):
                shutil.rmtree(os.path.join(self.root, name),
                              ignore_errors=True)
            return count
        return self.invalidate(stage)


def _age_seconds(created_at, now):
    """عمر إدخال بالثواني من طابع `YYYY-MM-DDTHH:MM:SS`؛ 0 إن تعذّر."""
    try:
        parsed = time.strptime(created_at, "%Y-%m-%dT%H:%M:%S")
        return max(0.0, now - time.mktime(parsed))
    except (TypeError, ValueError):
        return 0.0
