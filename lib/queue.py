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
import os
import re
import tempfile
import threading

QUEUE_WAITING_MARKERS = ("في الانتظار", "دفعة ثانية")

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


def parse_waiting_entries(text):
    """اقرأ كل أسطر الانتظار المرقّمة من نص ملف الطابور.

    يرجع قائمة (رقم، عنوان، ملاحظة، رقم السطر) — لأسطر الأقسام
    «في الانتظار» و«دفعة ثانية» فقط.
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
            entries.append({"number": int(m.group(1)),
                            "title": m.group(2).strip(),
                            "note": (m.group(3) or "").strip(),
                            "line": i})
    return entries


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
            os.unlink(tmp)
        except OSError:
            pass
        raise
