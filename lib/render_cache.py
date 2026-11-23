#!/usr/bin/env python3
"""كاش إعادة استخدام منتجات الريندر — جولة v0.1.39 (مقترح
MoneyPrinterTurbo: دفعات + history — المقارنة القسم 4.1
بند 1 والقسم 6 بند 4).

فكرة الكاش: مهمة ريندر بمدخلات لم تتغير (نفس النص/السيناريو
+ الصوت + الصور + إعدادات التجميع) تنتج المخرج نفسه — فلا
داعي لإعادة ريندرها. البصمة الحتمية SHA-256 لمدخلات الريندر
مفتاحٌ لمخرج سابق في فهرس `runs/render-cache.json`.

قواعد السلامة (لا استثناء لها):
- أي مخرج معاد استخدامه يُتحقق من سلامته قبل إرجاعه: الملف
  موجود + مدته وأبعاده صحيحة عبر ffprobe (حيث ينطبق).
- أي بصمة غير مطابقة تعيد الريندر — لا إرجاع لمخرج من بصمة
  مختلفة أبدًا.
- أي فشل في الكاش نفسه (فهرس تالف، ffprobe غائب، خطأ قراءة)
  يُعامل كـ«لا يوجد مخرج سابق» — الكاش لا يكسر الإنتاج أبدًا.
- المخرج التالف/الناقص يُرفض ويُحذف إدخاله من الفهرس.
"""
import fcntl
import hashlib
import json
import os
import tempfile
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

CAIRO = ZoneInfo("Africa/Cairo")

CACHE_FILENAME = "render-cache.json"
SCHEMA_VERSION = 1

# قفل خيوط داخل العملية (يكمل قفل الملف بين العمليات).
_CACHE_THREAD_LOCK = threading.Lock()


class RenderCacheError(Exception):
    """خطأ في كاش الريندر (رسالته عربية)."""


def now_cairo_iso():
    """الآن بتوقيت القاهرة بصيغة ISO."""
    return datetime.now(tz=CAIRO).isoformat(timespec="seconds")


def cache_index_path(runs_dir):
    """مسار فهرس الكاش (runs/render-cache.json)."""
    base = os.path.abspath(os.path.expanduser(runs_dir))
    return os.path.join(base, CACHE_FILENAME)


def sha256_file(path):
    """بصمة SHA-256 لملف (قراءة بالقطع — بلا تحميل كامل)."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(value):
    """حوّل قيمة إلى صيغة حتمية قابلة للبصمة.

    - مسار ملف موجود ← بصمة محتواه (لا مساره وحده: تغيير
      محتوى الصوت/الصورة يغيّر البصمة ولو بقي الاسم).
    - قائمة/قاموس ← ترتيب حتمي (sort_keys؛ والقوائم
      المرتبة كقائمة تبقى بترتيبها — ترتيب المشاهد مهم).
    - أي قيمة أخرى ← نصها (default=str).
    """
    if isinstance(value, dict):
        return {str(k): _canonical(v)
                for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, str) and os.path.isfile(
            os.path.expanduser(value)):
        try:
            return {"__file_sha256__": sha256_file(
                os.path.expanduser(value))}
        except OSError:
            return {"__file_missing__": value}
    return value


FNV1A_64_OFFSET = 14695981039346656037
FNV1A_64_PRIME = 1099511628211
_FNV1A_64_MASK = (1 << 64) - 1


def fnv1a_64(data: bytes) -> int:
    """هاش FNV-1a ‏64 بت لبايتات: الأساس 14695981039346656037
    والأس 1099511628211، مع قطع 64 بت بعد كل ضرب."""
    if not isinstance(data, (bytes, bytearray)):
        raise RenderCacheError(
            "هاش FNV-1a يحتاج بايتات (وصل: %s)"
            % type(data).__name__)
    h = FNV1A_64_OFFSET
    for byte in data:
        h ^= byte
        h = (h * FNV1A_64_PRIME) & _FNV1A_64_MASK
    return h


def fnv1a_fingerprint(inputs) -> str:
    """بصمة FNV-1a (16 حرف hex) لقاموس مدخلات ريندر.

    نفس التحويل الحتمي `_canonical` ونفس JSON الحتمي
    المستعمل في `fingerprint_inputs`، لكن بالهاش FNV-1a
    بدل SHA-256 — هاش رخيص وسريع لفحص التقادم قبل الهاش
    الثقيل. نفس المدخلات ← نفس البصمة دائمًا؛ وترتيب
    مفاتيح القاموس لا يغيّرها. يرفع RenderCacheError إن لم
    تكن المدخلات قاموسًا.
    """
    if not isinstance(inputs, dict):
        raise RenderCacheError(
            "مدخلات الريندر يجب أن تكون قاموسًا (وصل: %s)"
            % type(inputs).__name__)
    canonical = _canonical(inputs)
    text = json.dumps(canonical, ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"),
                      default=str)
    return "%016x" % fnv1a_64(text.encode("utf-8"))


def fingerprint_inputs(inputs):
    """بصمة حتمية لقاموس مدخلات ريندر.

    inputs: قاموس فيه أي من: script/text (نص أو مسار ملف)،
    audio (مسار ملف صوت أو نص)، images (قائمة مسارات أو نصوص)،
    settings (قاموس إعدادات التجميع: الخلفية، المقاس، الشعار،
    الدرجة، السرعة، الصوت...). نفس المدخلات ← نفس البصمة
    دائمًا؛ وأي تغيير فيها ← بصمة مختلفة. ترتيب مفاتيح
    القاموس لا يغيّر البصمة.
    """
    if not isinstance(inputs, dict):
        raise RenderCacheError(
            "مدخلات الريندر يجب أن تكون قاموسًا (وصل: %s)"
            % type(inputs).__name__)
    canonical = _canonical(inputs)
    text = json.dumps(canonical, ensure_ascii=False,
                      sort_keys=True, separators=(",", ":"),
                      default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprint_for(script=None, audio=None, images=None,
                    settings=None):
    """اختصار: بصمة من المكونات الأربعة مباشرة.

    أي مكوّن غائب يُستبعد من البصمة (لا يُعامل كقيمة فارغة
    ثابتة) — فبصمة بلا صور لا تطابق بصمة بصور.
    """
    inputs = {}
    if script is not None:
        inputs["script"] = script
    if audio is not None:
        inputs["audio"] = audio
    if images is not None:
        inputs["images"] = list(images)
    if settings is not None:
        inputs["settings"] = settings
    return fingerprint_inputs(inputs)


def _read_index_locked(path):
    """اقرأ الفهرس (يُستدعى والقفل ممسوك).

    مفقود أو تالف أو بلا إصدار معروف ← فهرس فارغ.
    """
    if not os.path.isfile(path):
        return {"version": SCHEMA_VERSION, "entries": {}}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {"version": SCHEMA_VERSION, "entries": {}}
    if not isinstance(data, dict) \
            or data.get("version") != SCHEMA_VERSION \
            or not isinstance(data.get("entries"), dict):
        return {"version": SCHEMA_VERSION, "entries": {}}
    return data


def _write_index_locked(path, index):
    """اكتب الفهرس ذريًا (يُستدعى والقفل ممسوك)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path),
                               prefix=".render-cache-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(index, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _locked(runs_dir):
    """قفل ملف حصري يغطي قراءة الفهرس وتعديله وكتابته."""
    path = cache_index_path(runs_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock_path = path + ".lock"
    lock_f = open(lock_path, "a+", encoding="utf-8")
    fcntl.flock(lock_f, fcntl.LOCK_EX)
    return path, lock_f


def _default_probe(video_path):
    """فحص الفيديو الافتراضي عبر lib.check.probe (ffprobe)."""
    from lib import check as check_lib
    return check_lib.probe(video_path)


def _entry_is_valid(entry, expected_width=None,
                    expected_height=None, min_duration=None,
                    probe_fn=None):
    """تحقق من سلامة مخرج مخزّن قبل إرجاعه.

    يرجع (سليم؟، سبب الرفض أو None). الفحص: الملف موجود،
    وffprobe يقرؤه (مدة موجبة، ومسار فيديو)، والمدة ≥ الحد
    الأدنى إن حُدد، والأبعاد مطابقة إن حُددت.
    """
    output = (entry or {}).get("output")
    if not output or not os.path.isfile(output):
        return False, "ملف المخرج غير موجود: %s" % output
    probe = probe_fn or _default_probe
    try:
        info = probe(output)
    except Exception as e:
        return False, "تعذر فحص المخرج عبر ffprobe: %s" % e
    duration = info.get("duration") or 0
    if duration <= 0:
        return False, "مدة المخرج غير مقروءة: %s" % output
    if min_duration is not None and duration < min_duration:
        return False, ("مدة المخرج %.1f ث أقل من الحد الأدنى "
                       "%.1f ث" % (duration, min_duration))
    if expected_width is not None \
            and info.get("width") != expected_width:
        return False, ("عرض المخرج %s لا يطابق المتوقع %s"
                       % (info.get("width"), expected_width))
    if expected_height is not None \
            and info.get("height") != expected_height:
        return False, ("ارتفاع المخرج %s لا يطابق المتوقع %s"
                       % (info.get("height"), expected_height))
    return True, None


def lookup(runs_dir, fingerprint, expected_width=None,
           expected_height=None, min_duration=None, probe_fn=None):
    """ابحث عن مخرج سابق بنفس البصمة؛ ارجعه إن وُجد وسليمًا.

    يرجع قاموس الإدخال {fingerprint, output, thumbnail,
    duration_seconds, width, height, sha256, created_at} أو
    None. مخرج تالف/ناقص يُرفض ويُحذف إدخاله من الفهرس.
    أي خطأ في الكاش نفسه يُرجع None (لا يكسر الإنتاج).
    """
    if not fingerprint:
        return None
    try:
        with _CACHE_THREAD_LOCK:
            path, lock_f = _locked(runs_dir)
            try:
                index = _read_index_locked(path)
                entry = (index.get("entries") or {}).get(fingerprint)
                if entry is None:
                    return None
                ok, _reason = _entry_is_valid(
                    entry, expected_width, expected_height,
                    min_duration, probe_fn)
                if not ok:
                    del index["entries"][fingerprint]
                    _write_index_locked(path, index)
                    return None
                return dict(entry)
            finally:
                fcntl.flock(lock_f, fcntl.LOCK_UN)
                lock_f.close()
    except OSError:
        return None


def store(runs_dir, fingerprint, output_path, thumbnail=None,
          probe_fn=None, inputs=None):
    """سجّل مخرجًا في الكاش تحت بصمته؛ ارجع الإدخال أو None.

    يُخزَّن فقط إن كان الملف موجودًا وقابلًا للفحص (مدة
    وأبعاد من probe حيث ينطبق)؛ وملف مفقود أو تالف لا يُخزَّن
    إطلاقًا. أي خطأ يُرجع None بدل رفع استثناء.
    inputs (اختياري): قاموس مدخلات الريندر — إن أُعطي سُجّل
    في الإدخال "quick_fp" (بصمة FNV-1a السريعة) لفحص
    التقادم قبل الهاش الثقيل؛ ولا يغيّر شيئًا في lookup
    (مفتاحه بصمة SHA-256 كما هو).
    """
    if not fingerprint or not output_path \
            or not os.path.isfile(output_path):
        return None
    probe = probe_fn or _default_probe
    try:
        info = probe(output_path)
        duration = info.get("duration")
        width = info.get("width")
        height = info.get("height")
    except Exception:
        return None
    if not duration or duration <= 0:
        return None
    try:
        digest = sha256_file(output_path)
    except OSError:
        return None
    entry = {
        "fingerprint": fingerprint,
        "output": os.path.abspath(os.path.expanduser(output_path)),
        "thumbnail": (os.path.abspath(os.path.expanduser(thumbnail))
                      if thumbnail and os.path.isfile(thumbnail)
                      else None),
        "duration_seconds": round(float(duration), 3),
        "width": width,
        "height": height,
        "sha256": digest,
        "created_at": now_cairo_iso(),
    }
    if inputs is not None:
        try:
            entry["quick_fp"] = fnv1a_fingerprint(inputs)
        except RenderCacheError:
            return None
    try:
        with _CACHE_THREAD_LOCK:
            path, lock_f = _locked(runs_dir)
            try:
                index = _read_index_locked(path)
                index.setdefault("entries", {})[fingerprint] = entry
                _write_index_locked(path, index)
            finally:
                fcntl.flock(lock_f, fcntl.LOCK_UN)
                lock_f.close()
    except OSError:
        return None
    return dict(entry)


def invalidate(runs_dir, fingerprint):
    """احذف إدخال بصمة من الفهرس (بعد فشل فحص مخرجها مثلًا).

    يرجع True إن كان الإدخال موجودًا وحُذف.
    """
    if not fingerprint:
        return False
    try:
        with _CACHE_THREAD_LOCK:
            path, lock_f = _locked(runs_dir)
            try:
                index = _read_index_locked(path)
                entries = index.setdefault("entries", {})
                if fingerprint not in entries:
                    return False
                del entries[fingerprint]
                _write_index_locked(path, index)
                return True
            finally:
                fcntl.flock(lock_f, fcntl.LOCK_UN)
                lock_f.close()
    except OSError:
        return False
