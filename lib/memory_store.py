#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""مخزن ذاكرة بميزانية وأرشفة واستدعاء محدود — جولة v0.1.63 (بند 14).

يطبّق عقد ع13 من خطة الجولة: ميزانية تحميل (أول 200 سطر / 24KB
من MEMORY.md)، وأرشفة تُكتب قبل إعادة الكتابة، واستدعاء قبل
كل دور (≤4 ملاحظات + ≤4 مقاطع، ≤6,000 حرف)، وتنقيح بيانات
الاعتماد إلى «redacted N chars» قبل الكتابة على القرص،
وصلاحيات 0600 وكتابة ذرية، وانتهاء بعلامة «· until YYYY-MM-DD»،
وفهرس مواضيع ≤40 موضوعًا / 2,000 حرف، وسقف إدخال 1,000 حرف /
20 سطرًا.

الملفات تحت ``memory/`` في الشجرة: ``MEMORY.md`` و``<topic>.md``
و``archive.md`` و``log/YYYY-MM-DD.md`` و``threads/<id>.md``.
"""
import os
import re
from datetime import date

# --- حدود العقد ع13 ---
MAX_LOAD_LINES = 200
MAX_LOAD_BYTES = 24 * 1024
MAX_RECALL_NOTES = 4
MAX_RECALL_SNIPPETS = 4
MAX_RECALL_CHARS = 6000
MAX_ENTRY_CHARS = 1000
MAX_ENTRY_LINES = 20
MAX_TOPICS = 40
MAX_INDEX_CHARS = 2000

# علامة انتهاء الصلاحية: «· until YYYY-MM-DD».
EXPIRY_RE = re.compile(r"·\s*until\s+(\d{4}-\d{2}-\d{2})")

# أنماط قيم بيانات الاعتماد في إسنادات نصية — تُنقَّح قبل الكتابة.
_CREDENTIAL_RE = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|"
    r"secret|bearer)\s*[:=]\s*(\S+)"
)
_BEARER_RE = re.compile(r"(?i)(Bearer\s+)(\S+)")


def redact_credentials(text):
    """نقّح قيم بيانات الاعتماد في نص إلى «redacted N chars».

    يبقى اسم الحقل كما هو، وتُستبدل القيمة بعدد محارفها فقط —
    فلا يصل أي سر إلى القرص أبدًا.
    """
    def _replace(match):
        value = match.group(2)
        return "%s«redacted %d chars»" % (match.group(1), len(value))

    text = _CREDENTIAL_RE.sub(_replace, text)
    text = _BEARER_RE.sub(
        lambda m: "%s«redacted %d chars»" % (m.group(1), len(m.group(2))),
        text,
    )
    return text


def is_expired(text, today=None):
    """هل انتهت صلاحية نص يحمل علامة «· until YYYY-MM-DD»؟

    نص بلا علامة لا ينتهي أبدًا. ``today`` تاريخ اختياري
    (``date``) للاختبارات؛ الافتراضي اليوم.
    """
    match = EXPIRY_RE.search(text)
    if not match:
        return False
    if today is None:
        today = date.today()
    try:
        until = date.fromisoformat(match.group(1))
    except ValueError:
        return False
    return today > until


def check_entry(text):
    """تحقق من سقف الإدخال (1,000 حرف / 20 سطرًا)؛ ارفع ValueError إن تجاوز."""
    if len(text) > MAX_ENTRY_CHARS:
        raise ValueError(
            "الإدخال %d حرفًا يتجاوز السقف %d حرفًا"
            % (len(text), MAX_ENTRY_CHARS)
        )
    lines = text.splitlines()
    if len(lines) > MAX_ENTRY_LINES:
        raise ValueError(
            "الإدخال %d سطرًا يتجاوز السقف %d سطرًا"
            % (len(lines), MAX_ENTRY_LINES)
        )
    return text


def load_limited(path):
    """اقرأ ملفًا ضمن ميزانية التحميل: أول 200 سطر / 24KB.

    يرجع النص المقروء فقط؛ ملف غائب يرجع سلسلة فارغة.
    """
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = []
        total = 0
        for line in fh:
            if len(lines) >= MAX_LOAD_LINES:
                break
            encoded = len(line.encode("utf-8"))
            if total + encoded > MAX_LOAD_BYTES:
                room = MAX_LOAD_BYTES - total
                if room > 0:
                    cut = line.encode("utf-8")[:room].decode(
                        "utf-8", errors="ignore")
                    lines.append(cut)
                break
            lines.append(line)
            total += encoded
        return "".join(lines)


def _atomic_write(path, text):
    """اكتب نصًا ذريًا بصلاحيات 0600 (عبر ملف مؤقت ثم استبدال)."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = "%s.tmp-%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _append_atomic(path, text):
    """ألحق نصًا بملف مع ضبط صلاحياته 0600."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(text)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _safe_name(name):
    """اسم ملف آمن لموضوع أو خيط: حروف وأرقام وشرطة وشرطة سفلية فقط."""
    cleaned = re.sub(r"[^A-Za-z0-9_\u0600-\u06FF-]+", "_", name).strip("_")
    if not cleaned:
        raise ValueError("اسم موضوع/خيط فارغ بعد التنظيف: %r" % name)
    return cleaned


class MemoryStore:
    """مخزن ذاكرة المشروع تحت مجلد ``memory/`` واحد."""

    def __init__(self, root):
        self.root = root

    # --- مسارات ---
    def memory_path(self):
        return os.path.join(self.root, "MEMORY.md")

    def topic_path(self, topic):
        return os.path.join(self.root, "%s.md" % _safe_name(topic))

    def archive_path(self):
        return os.path.join(self.root, "archive.md")

    def log_path(self, day=None):
        if day is None:
            day = date.today()
        return os.path.join(self.root, "log", "%s.md" % day.isoformat())

    def thread_path(self, thread_id):
        return os.path.join(
            self.root, "threads", "%s.md" % _safe_name(thread_id))

    # --- تحميل واستدعاء ---
    def load_memory(self):
        """حمّل MEMORY.md ضمن الميزانية (200 سطر / 24KB)."""
        return load_limited(self.memory_path())

    def list_topics(self):
        """أسماء ملفات المواضيع (بلا MEMORY.md وarchive.md وREADME.md)."""
        if not os.path.isdir(self.root):
            return []
        skip = {"MEMORY.md", "archive.md", "README.md"}
        topics = []
        for name in sorted(os.listdir(self.root)):
            if name.endswith(".md") and name not in skip:
                topics.append(name[:-3])
        return topics

    def build_index(self):
        """فهرس مواضيع ≤40 موضوعًا / 2,000 حرف: سطر لكل موضوع."""
        topics = self.list_topics()[:MAX_TOPICS]
        lines = []
        for topic in topics:
            path = os.path.join(self.root, "%s.md" % topic)
            try:
                with open(path, "r", encoding="utf-8",
                          errors="replace") as fh:
                    first = fh.readline().strip()
            except OSError:
                first = ""
            lines.append("- %s%s" % (topic, (": " + first) if first else ""))
        index = "\n".join(lines)
        return index[:MAX_INDEX_CHARS]

    def recall(self, query, today=None):
        """استدعاء قبل الدور: ≤4 ملاحظات + ≤4 مقاطع، ≤6,000 حرف.

        يبحث في MEMORY.md وملفات المواضيع وسجل اليوم عن كلمات
        الاستعلام؛ ويسقط المنتهية الصلاحية. يرجع قاموسًا
        ``{"notes": [...], "snippets": [...], "chars": N}``.
        """
        words = [w for w in re.split(r"\s+", query.strip().lower()) if w]
        notes = []
        snippets = []
        total = 0

        def _take(bucket, text):
            nonlocal total
            if len(bucket) >= (MAX_RECALL_NOTES if bucket is notes
                               else MAX_RECALL_SNIPPETS):
                return
            if is_expired(text, today=today):
                return
            if total + len(text) > MAX_RECALL_CHARS:
                room = MAX_RECALL_CHARS - total
                if room <= 0:
                    return
                text = text[:room]
            bucket.append(text)
            total += len(text)

        candidates = []
        memory = self.load_memory()
        if memory:
            candidates.append(memory)
        for topic in self.list_topics():
            candidates.append(load_limited(
                os.path.join(self.root, "%s.md" % topic)))

        for text in candidates:
            # الانتهاء يُفحص سطرًا سطرًا: سطر منتهٍ لا يُسقط بقية الملف.
            units = [line for line in text.splitlines() if line.strip()]
            for unit in units:
                if total >= MAX_RECALL_CHARS:
                    break
                if is_expired(unit, today=today):
                    continue
                if not words:
                    _take(notes, unit)
                    continue
                if any(w in unit.lower() for w in words):
                    _take(snippets, unit)
                elif len(notes) < MAX_RECALL_NOTES:
                    _take(notes, unit)
            if total >= MAX_RECALL_CHARS:
                break
        return {"notes": notes, "snippets": snippets, "chars": total}

    # --- كتابة ---
    def add_note(self, topic, text, until=None):
        """أضف ملاحظة إلى ملف موضوع (بعد تنقيح وسقف إدخال)."""
        check_entry(text)
        if until is not None:
            text = "%s · until %s" % (text.rstrip(), until)
        text = redact_credentials(text)
        _append_atomic(self.topic_path(topic), text.rstrip() + "\n")
        return self.topic_path(topic)

    def add_log_entry(self, text, day=None):
        """أضف سطر سجل يومي إلى ``log/YYYY-MM-DD.md``."""
        check_entry(text)
        _append_atomic(self.log_path(day), redact_credentials(text) + "\n")
        return self.log_path(day)

    def add_thread_note(self, thread_id, text):
        """أضف ملاحظة إلى خيط محادثة ``threads/<id>.md``."""
        check_entry(text)
        _append_atomic(self.thread_path(thread_id),
                       redact_credentials(text) + "\n")
        return self.thread_path(thread_id)

    def archive(self):
        """اكتب الأرشيف من MEMORY.md الحالية (قبل أي إعادة كتابة)."""
        current = ""
        path = self.memory_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                current = fh.read()
        if current.strip():
            _append_atomic(self.archive_path(), current)
            if not current.endswith("\n"):
                _append_atomic(self.archive_path(), "\n")
        return self.archive_path()

    def rewrite_memory(self, new_text):
        """أعد كتابة MEMORY.md: الأرشيف أولًا ثم كتابة ذرية 0600."""
        self.archive()
        _atomic_write(self.memory_path(), redact_credentials(new_text))
        return self.memory_path()
