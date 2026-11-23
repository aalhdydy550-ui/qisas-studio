#!/usr/bin/env python3
"""الطابور — `studio.py queue add`: إضافة قصة إلى ملف الطابور بسطر واحد.

صيغة ملف الطابور (~/workspace/goals/goal/hidden_files/
story-queue-2026-11-20.md): قسم «في الانتظار» (أو «دفعة ثانية»)
فيه أسطر مرقّمة `N. **العنوان** — ملاحظة`. أمر الإضافة:

- يرفض العنوان المكرر (نفس العنوان بعد تجريد المسافات) في أي
  موضع من الملف — بلا تكرار أبدًا.
- يرقّم القصة الجديدة برقم أعلى رقم انتظار + 1، ويُلحقها بعد
  آخر سطر انتظار مرقّم (فتبقى في قسم الانتظار، لا في آخر الملف).
- يحفظ نص القصة الكامل في مجلد `queue/` داخل studio
  (`<رقم>-<slug>.txt`) ويشير إليه في الملاحظة؛ فملف الطابور
  يبقى قائمة موجزة كما هو، والنص الكامل محفوظ بجانبه.
- `parts`: عدد الأجزاء (1 = منشور واحد، 2+ = «يحتاج N أجزاء»).

لا يُمسّ أي قسم آخر من الملف، ولا يُعاد ترقيم شيء.
"""
import fcntl
import json
import os
import re
import tempfile
import threading

from lib import protect as protect_lib

QUEUE_WAITING_MARKERS = ("في الانتظار", "دفعة ثانية")

# --- حالات النشر متعدد المنصات — جولة v0.1.39 (أ2-8) ---
# مرجع تصميم من AutoContent.Live (المقارنة §4.11): قائمة
# انتظار نشر موحّدة — عنصر القائمة يحمل حالة نشر لكل منصة
# (facebook/youtube/tiktok/instagram: ‏pending/published/
# failed/skipped). المنصات الأربع هي نفسها منصات النشر في
# lib/publish.py (فيسبوك/يوتيوب) وlib/social_publish.py
# (TikTok/Instagram).
#
# التخزين: ملف جانبي JSON بجانب ملف الطابور
# (<طابور>.publish.json) — صيغة أسطر الطابور المرقّمة لا
# تُمسّ إطلاقًا، والعنصر القديم بلا حالات يُقرأ pending
# لكل المنصات. الملف الجانبي 600 مثل ملف الطابور نفسه.

PUBLISH_PLATFORMS = ("facebook", "youtube", "tiktok", "instagram")
PUBLISH_STATUSES = ("pending", "published", "failed", "skipped")
DEFAULT_PUBLISH_STATUS = "pending"

# قفل خيوط داخل العملية (يكمل قفل الملف بين العمليات).
_QUEUE_THREAD_LOCK = threading.Lock()


class QueueError(Exception):
    """خطأ في إضافة قصة للطابور (رسالته عربية)."""


# سطر انتظار مرقّم: `N. **العنوان** — ملاحظة` (الملاحظة اختيارية).
ENTRY_RE = re.compile(r"^\s*(\d+)\.\s+\*\*(.+?)\*\*\s*(?:—\s*(.*))?$")


def _norm_title(title):
    """طيّ العنوان للمقارنة: تجريد مسافات ومسافات داخلية زائدة."""
    return re.sub(r"\s+", " ", (title or "").strip())


def _slug(title):
    """slug عربي آمن لاسم الملف: حروف وأرقام وشرطات فقط."""
    text = re.sub(r"\s+", "-", _norm_title(title))
    text = re.sub(r"[^0-9A-Za-z\u0600-\u06FF\-_]+", "", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "qissa"


def parse_waiting_entries(text, publish_statuses=None):
    """اقرأ كل أسطر الانتظار المرقّمة من نص ملف الطابور.

    يرجع قائمة (رقم، عنوان، ملاحظة، رقم السطر) — لأسطر الأقسام
    «في الانتظار» و«دفعة ثانية» فقط. كل عنصر يحمل مفتاح
    "publish" (حالة نشر لكل منصة) — من publish_statuses
    (قاموس {رقم: {منصة: حالة}}) إن مُرّر، وإلا pending لكل
    المنصات (توافق رجعي: عنصر قديم بلا حالات).
    """
    entries = []
    waiting = False
    for i, line in enumerate(text.splitlines()):
        if line.startswith("## "):
            waiting = any(m in line for m in QUEUE_WAITING_MARKERS)
            continue
        if not waiting:
            continue
        m = ENTRY_RE.match(line.strip())
        if m:
            number = int(m.group(1))
            entries.append({"number": number,
                            "title": m.group(2).strip(),
                            "note": (m.group(3) or "").strip(),
                            "line": i,
                            "publish": _entry_publish(
                                publish_statuses, number)})
    return entries


def default_publish_statuses():
    """حالات نشر افتراضية: pending لكل المنصات الأربع."""
    return {p: DEFAULT_PUBLISH_STATUS for p in PUBLISH_PLATFORMS}


def _entry_publish(publish_statuses, number):
    """حالات عنصر واحد من خريطة الحالات — pending عند الغياب."""
    if not isinstance(publish_statuses, dict):
        return default_publish_statuses()
    raw = publish_statuses.get(number)
    if raw is None:
        raw = publish_statuses.get(str(number))
    if raw is None:
        return default_publish_statuses()
    try:
        return normalize_publish_statuses(raw)
    except QueueError:
        # خريطة تالفة جزئيًا لا تكسر قراءة الطابور كله.
        return default_publish_statuses()


def normalize_publish_statuses(value):
    """طبّع حالات نشر عنصر: {منصة: حالة} كاملة لكل المنصات.

    المنصات الغائبة pending؛ والمنصة أو الحالة غير المعروفة
    ترفع QueueError برسالة عربية. None/قاموس فارغ = الكل pending.
    """
    if value is None:
        return default_publish_statuses()
    if not isinstance(value, dict):
        raise QueueError(
            "حالات النشر يجب أن تكون قاموسًا {منصة: حالة} "
            "(وصل: %s)" % (value,))
    out = default_publish_statuses()
    for platform, status in value.items():
        if platform not in PUBLISH_PLATFORMS:
            raise QueueError(
                "منصة نشر غير معروفة: %s (المنصات: %s)"
                % (platform, "، ".join(PUBLISH_PLATFORMS)))
        if status not in PUBLISH_STATUSES:
            raise QueueError(
                "حالة نشر غير صالحة للمنصة %s: %s (الحالات: %s)"
                % (platform, status, "، ".join(PUBLISH_STATUSES)))
        out[platform] = status
    return out


def _normalize_statuses_map(statuses):
    """طبّع خريطة حالات كاملة {رقم: {منصة: حالة}} — مفاتيح int."""
    if statuses is None:
        return {}
    if not isinstance(statuses, dict):
        raise QueueError("خريطة حالات النشر يجب أن تكون قاموسًا")
    out = {}
    for number, value in statuses.items():
        try:
            key = int(number)
        except (TypeError, ValueError):
            raise QueueError(
                "رقم قصة غير صالح في حالات النشر: %s" % (number,))
        out[key] = normalize_publish_statuses(value)
    return out


def publish_statuses_path(queue_path):
    """مسار الملف الجانبي لحالات النشر بجانب ملف الطابور."""
    return queue_path + ".publish.json"


def load_publish_statuses(queue_path):
    """اقرأ حالات النشر من الملف الجانبي ({} إن غاب أو تلف).

    المدخلات التالفة تُتخطى مدخلًا مدخلًا — ملف جانبي تالف
    جزئيًا لا يكسر قراءة الطابور.
    """
    path = publish_statuses_path(queue_path)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    out = {}
    for number, value in data.items():
        try:
            out[int(number)] = normalize_publish_statuses(value)
        except (QueueError, TypeError, ValueError):
            continue
    return out


def save_publish_statuses(queue_path, statuses):
    """احفظ خريطة حالات النشر في الملف الجانبي (كتابة ذرية 600).

    يرجع الخريطة المطبّعة. يرفع QueueError عند خريطة غير صالحة.
    """
    statuses = _normalize_statuses_map(statuses)
    payload = {str(n): v for n, v in sorted(statuses.items())}
    _write_atomic(publish_statuses_path(queue_path),
                  json.dumps(payload, ensure_ascii=False, indent=2)
                  + "\n")
    return statuses


def get_platform_status(statuses, number, platform):
    """حالة منصة واحدة لعنصر — pending عند غياب أي سجل."""
    if platform not in PUBLISH_PLATFORMS:
        raise QueueError(
            "منصة نشر غير معروفة: %s (المنصات: %s)"
            % (platform, "، ".join(PUBLISH_PLATFORMS)))
    try:
        entry = (statuses or {}).get(int(number))
    except (TypeError, ValueError):
        raise QueueError(
            "رقم قصة غير صالح: %s" % (number,))
    if entry is None:
        entry = (statuses or {}).get(str(number))
    if not isinstance(entry, dict):
        return DEFAULT_PUBLISH_STATUS
    return entry.get(platform, DEFAULT_PUBLISH_STATUS)


def update_platform_status(statuses, number, platform, status):
    """حدّث حالة منصة لعنصر في خريطة ذاكرة (دالة نقية).

    يرجع حالات العنصر المطبّعة كاملة بعد التحديث. يرفع
    QueueError عند منصة/حالة/رقم غير صالح. لا يكتب أي ملف —
    للحفظ الدائم استخدم set_platform_status. يحدّث القاموس
    الممرَّر في مكانه (فيُرى التحديث عبر get_platform_status
    على القاموس نفسه).
    """
    if platform not in PUBLISH_PLATFORMS:
        raise QueueError(
            "منصة نشر غير معروفة: %s (المنصات: %s)"
            % (platform, "، ".join(PUBLISH_PLATFORMS)))
    if status not in PUBLISH_STATUSES:
        raise QueueError(
            "حالة نشر غير صالحة: %s (الحالات: %s)"
            % (status, "، ".join(PUBLISH_STATUSES)))
    try:
        key = int(number)
    except (TypeError, ValueError):
        raise QueueError("رقم قصة غير صالح: %s" % (number,))
    if not isinstance(statuses, dict):
        raise QueueError("خريطة حالات النشر يجب أن تكون قاموسًا")
    # طبّع المدخلات الموجودة في مكانها (مفاتيح str ← int).
    for old_key in list(statuses.keys()):
        try:
            int_key = int(old_key)
        except (TypeError, ValueError):
            raise QueueError(
                "رقم قصة غير صالح في حالات النشر: %s" % (old_key,))
        value = statuses.pop(old_key)
        statuses[int_key] = normalize_publish_statuses(value)
    entry = statuses.get(key, default_publish_statuses())
    entry[platform] = status
    statuses[key] = entry
    return dict(entry)


def set_platform_status(queue_path, number, platform, status):
    """حدّث حالة منصة لعنصر واحفظها في الملف الجانبي.

    تحت القفل نفسه المستخدَم في add_story (خيط + ملف) فلا
    تضيع تحديثات متوازية. يرجع حالات العنصر المطبّعة كاملة.
    يرفع QueueError عند منصة/حالة/رقم غير صالح.
    """
    if platform not in PUBLISH_PLATFORMS:
        raise QueueError(
            "منصة نشر غير معروفة: %s (المنصات: %s)"
            % (platform, "، ".join(PUBLISH_PLATFORMS)))
    if status not in PUBLISH_STATUSES:
        raise QueueError(
            "حالة نشر غير صالحة: %s (الحالات: %s)"
            % (status, "، ".join(PUBLISH_STATUSES)))
    with _QUEUE_THREAD_LOCK:
        lock_path = queue_path + ".lock"
        with open(lock_path, "a+", encoding="utf-8") as lock_f:
            fcntl.flock(lock_f, fcntl.LOCK_EX)
            try:
                # رقم غير موجود في الانتظار = QueueError (كما يعد
                # docstring) — وإلا كان الملف الجانبي يحمل حالة
                # لقصة وهمية لا تظهر في أي قائمة. ملف طابور
                # غائب = سلوك قديم (بلا تحقق) للتوافق.
                if os.path.isfile(queue_path):
                    with open(queue_path, encoding="utf-8") as qf:
                        waiting = parse_waiting_entries(qf.read())
                    try:
                        num = int(number)
                    except (TypeError, ValueError):
                        raise QueueError(
                            "رقم قصة غير صالح: %s" % (number,))
                    if num not in {e.get("number") for e in waiting}:
                        raise QueueError(
                            "لا توجد قصة بهذا الرقم في الانتظار: %s"
                            % (number,))
                statuses = load_publish_statuses(queue_path)
                entry = update_platform_status(statuses, number,
                                               platform, status)
                statuses[int(number)] = entry
                save_publish_statuses(queue_path, statuses)
                return dict(entry)
            finally:
                fcntl.flock(lock_f, fcntl.LOCK_UN)


def entries_with_publish(text, queue_path=None):
    """اقرأ عناصر الانتظار مع حالات نشرها.

    بلا queue_path: الكل pending (توافق رجعي). معه: تُقرأ
    الحالات من الملف الجانبي بجانب ملف الطابور.
    """
    statuses = (load_publish_statuses(queue_path)
                if queue_path else None)
    return parse_waiting_entries(text, statuses)


def pending_for_platform(entries, platform):
    """قائمة العناصر المعلّقة (pending) على منصة واحدة.

    يرجع قائمة العناصر نفسها (قواميس parse_waiting_entries)
    — لا أرقامًا فقط، ليظهر العنوان مع الرقم في أي واجهة.
    """
    if platform not in PUBLISH_PLATFORMS:
        raise QueueError(
            "منصة نشر غير معروفة: %s (المنصات: %s)"
            % (platform, "، ".join(PUBLISH_PLATFORMS)))
    out = []
    for entry in entries or []:
        publish = entry.get("publish") or default_publish_statuses()
        if publish.get(platform, DEFAULT_PUBLISH_STATUS) \
                == DEFAULT_PUBLISH_STATUS:
            out.append(entry)
    return out


def publish_summary(entries):
    """ملخص موحّد: عدد المعلق/المنشور/الفاشل/المتخطى لكل منصة.

    يرجع {"entries": N, <منصة>: {pending, published, failed,
    skipped, total}} — total لكل منصة يساوي عدد العناصر.
    """
    entries = list(entries or [])
    summary = {"entries": len(entries)}
    for platform in PUBLISH_PLATFORMS:
        counts = {s: 0 for s in PUBLISH_STATUSES}
        for entry in entries:
            publish = entry.get("publish") or default_publish_statuses()
            status = publish.get(platform, DEFAULT_PUBLISH_STATUS)
            if status not in counts:
                status = DEFAULT_PUBLISH_STATUS
            counts[status] += 1
        counts["total"] = len(entries)
        summary[platform] = counts
    return summary


def add_story(queue_path, title, text, parts=1, note=None,
              stories_dir=None):
    """أضف قصة إلى ملف الطابور. يرجع {"number", "title", "text_file"}.

    يرفع QueueError عند: عنوان فارغ، نص فارغ، عنوان مكرر، عدد
    أجزاء غير صالح، أو مجلد نصوص غير قابل للكتابة. ملف طابور
    غائب يُنشأ بالهيكل المعتاد بدل الرفض.

    إصلاح اختراق 2026-11-22: الإضافة كانت قراءة-تعديل-كتابة
    بلا قفل وبلا ذرية — إضافتان متوازيتان فقدتا إحداهما (أُثبت
    حيًا: 10 إضافات متوازية بقي منها 8 فقط). الآن قفل ملف
    حصري يغطي القراءة والحساب والكتابة كلها، والكتابة ذرية
    (ملف مؤقت + os.replace) فلا يتلف الطابور بانقطاع منتصف
    الكتابة.
    """
    title = _norm_title(title)
    if not title:
        raise QueueError("عنوان القصة فارغ")
    # إصلاح اختبار اختراق 2026-11-22 (M3): `*` في العنوان كان
    # يكسر تحليل `**...**` (عنوان فيه `** — ` يُقرأ عنوانًا
    # مقطوعًا فيتجاوز منع التكرار) — يُرفض صراحةً.
    if "*" in title:
        raise QueueError("عنوان القصة لا يجوز أن يحوي `*`: %s" % title)
    # إصلاح اختبار اختراق 2026-11-22 (L12): `parts=True` كان
    # يُقبل كـ1 لأن bool صنف فرعي من int — يُرفض صراحةً.
    if isinstance(parts, bool):
        raise QueueError("عدد الأجزاء يجب أن يكون عددًا صحيحًا (وصل: %s)"
                         % parts)
    if not text or not text.strip():
        raise QueueError("نص القصة فارغ")
    if not isinstance(parts, int) or parts < 1:
        raise QueueError("عدد الأجزاء يجب أن يكون 1 أو أكثر (وصل: %s)"
                         % parts)
    with _QUEUE_THREAD_LOCK:
        lock_path = queue_path + ".lock"
        with open(lock_path, "a+", encoding="utf-8") as lock_f:
            fcntl.flock(lock_f, fcntl.LOCK_EX)
            try:
                return _add_story_locked(queue_path, title, text,
                                         parts, note, stories_dir)
            finally:
                fcntl.flock(lock_f, fcntl.LOCK_UN)


def _add_story_locked(queue_path, title, text, parts, note,
                      stories_dir):
    """جسم الإضافة — يُستدعى والقفل ممسوك."""
    if not os.path.isfile(queue_path):
        content = "# طابور قصص\n\n## في الانتظار\n\n"
    else:
        with open(queue_path, encoding="utf-8") as f:
            content = f.read()
    entries = parse_waiting_entries(content)
    for e in entries:
        if _norm_title(e["title"]) == title:
            raise QueueError("القصة موجودة أصلًا في الطابور (رقم %d): %s"
                             % (e["number"], title))
    number = max((e["number"] for e in entries), default=0) + 1
    # حفظ نص القصة الكامل بجانب studio (لا داخل ملف الطابور).
    text_file = None
    if stories_dir:
        os.makedirs(stories_dir, exist_ok=True)
        name = "%d-%s.txt" % (number, _slug(title))
        text_file = os.path.join(stories_dir, name)
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(text.strip() + "\n")
        # إصلاح اختبار اختراق 2026-11-22 (L7): نص القصة حساس —
        # 600 صراحةً بدل الاعتماد على umask.
        os.chmod(text_file, 0o600)
    if parts == 1:
        parts_note = "منشور واحد"
    else:
        parts_note = "يحتاج %d أجزاء" % parts
    if note:
        # إصلاح اختبار اختراق 2026-11-22 (M2): سطر جديد في
        # الملاحظة كان يحقن سطر انتظار وهميًا ويختطف الترقيم —
        # تُطوى كل المسافات البيضاء (سطور/تبويبات) إلى مسافة واحدة
        # فيبقى الإدخال سطرًا واحدًا دائمًا.
        note = re.sub(r"\s+", " ", note.strip())
        parts_note = "%s — %s" % (parts_note, note)
    if text_file:
        parts_note += " (النص: queue/%s)" % os.path.basename(text_file)
    new_line = "%d. **%s** — %s" % (number, title, parts_note)
    lines = content.splitlines()
    if entries:
        insert_at = entries[-1]["line"] + 1
    else:
        # لا انتظار بعد — ألحق في نهاية قسم الانتظار إن وُجد،
        # وإلا في نهاية الملف.
        insert_at = len(lines)
        for i, line in enumerate(lines):
            if line.startswith("## ") and any(
                    m in line for m in QUEUE_WAITING_MARKERS):
                insert_at = i + 1
                break
    lines.insert(insert_at, new_line)
    _write_atomic(queue_path, "\n".join(lines) + "\n")
    return {"number": number, "title": title, "text_file": text_file}


def _write_atomic(path, text):
    """اكتب نصًا في ملف ذريًا: ملف مؤقت بنفس المجلد ثم
    os.replace — فلا يبقى الملف نصف مكتوب أبدًا."""
    dir_name = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(dir=dir_name, prefix=".queue-",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        # إصلاح اختبار اختراق 2026-11-22 (L7): ملف الطابور
        # حساس — 600 صراحةً بدل الاعتماد على umask.
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            protect_lib.safe_delete(tmp)
        except (OSError, protect_lib.ProtectDeniedError):
            pass
        raise
