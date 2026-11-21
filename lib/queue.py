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
import os
import re

QUEUE_WAITING_MARKERS = ("في الانتظار", "دفعة ثانية")


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
    """
    title = _norm_title(title)
    if not title:
        raise QueueError("عنوان القصة فارغ")
    if not text or not text.strip():
        raise QueueError("نص القصة فارغ")
    if not isinstance(parts, int) or parts < 1:
        raise QueueError("عدد الأجزاء يجب أن يكون 1 أو أكثر (وصل: %s)"
                         % parts)
    if not os.path.isfile(queue_path):
        with open(queue_path, "w", encoding="utf-8") as f:
            f.write("# طابور قصص\n\n## في الانتظار\n\n")
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
    if parts == 1:
        parts_note = "منشور واحد"
    else:
        parts_note = "يحتاج %d أجزاء" % parts
    if note:
        parts_note = "%s — %s" % (parts_note, note.strip())
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
    with open(queue_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return {"number": number, "title": title, "text_file": text_file}
