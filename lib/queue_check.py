#!/usr/bin/env python3
"""تحقق بنية الطابور — جولة v0.1.37 (مقترح tinker رقم 8).

وحدة جديدة مستقلة — **لا تلمس lib/queue.py القائم** (يظلّل
stdlib `queue` وسبق أن كسر urllib3 بهذا). تستورد من
`lib.queue` محللاته الجاهزة (parse_waiting_entries وENTRY_RE)
وتضيف قواعد سلامة فوقها:

- لا سطر مشوّه في قسم الانتظار (رقم بلا صيغة مدخل كاملة).
- لا رقم مكرر ولا عنوان مكرر في الانتظار.
- لا خانتين (مجدولة/مخطط لها) لنفس الموعد (Unix واحد).
- كل فيديو مشار إليه في خانة مجدولة/مخطط لها موجود على القرص.

تُستدعى في بداية `daily`/`batch` (بوابة: طابور معطوب =
لا إنتاج) وفي `doctor`، وبأمر `queue validate`.
"""
import os
import re

from lib import queue as queue_lib

# أقسام تحمل سطور خانات (عنوان + موعد Unix).
_SLOT_SECTIONS = ("المجدول", "المخطط له")
QUEUE_SCHEDULED_MARKERS = ("المجدول",)
QUEUE_PLANNED_MARKERS = ("المخطط له",)
_UNIX_RE = re.compile(r"Unix\s+(\d+)")
_VIDEO_RE = re.compile(r"~/workspace/videos/[A-Za-z0-9_\-\.]+\.mp4")


def _section_of(line, current):
    """حدّث القسم الحالي من سطر عنوان ##؛ ارجع القسم الجديد."""
    if line.startswith("## "):
        for marker in QUEUE_SCHEDULED_MARKERS:
            if marker in line:
                return "scheduled"
        for marker in QUEUE_PLANNED_MARKERS:
            if marker in line:
                return "planned"
        for marker in queue_lib.QUEUE_WAITING_MARKERS:
            if marker in line:
                return "waiting"
        return "other"
    return current


def validate_queue_text(text):
    """حقّق نص الطابور؛ ارجع قائمة مشكلات (فارغة = سليم)."""
    issues = []
    lines = text.splitlines()

    # --- قسم الانتظار: أسطر مشوهة ---
    section = None
    waiting_lines = []
    for i, line in enumerate(lines, 1):
        section = _section_of(line, section)
        if section != "waiting":
            continue
        stripped = line.strip()
        if re.match(r"^\d+\.", stripped):
            waiting_lines.append((i, line))
            if not queue_lib.ENTRY_RE.match(stripped):
                issues.append(
                    "سطر %d: مدخل انتظار مشوّه (رقم بلا عنوان/أجزاء): %s"
                    % (i, stripped[:80]))

    # --- الانتظار: أرقام وعناوين مكررة ---
    entries = queue_lib.parse_waiting_entries(text)
    seen_numbers = {}
    for entry in entries:
        number = entry["number"]
        if number in seen_numbers:
            issues.append("رقم انتظار مكرر: %d (السطران %d و%d)"
                          % (number, seen_numbers[number],
                             entry["line"]))
        else:
            seen_numbers[number] = entry["line"]
    seen_titles = {}
    for entry in entries:
        title = queue_lib._norm_title(entry["title"])
        if title in seen_titles:
            issues.append("عنوان مكرر في الانتظار: «%s» (السطران %d و%d)"
                          % (entry["title"], seen_titles[title],
                             entry["line"]))
        else:
            seen_titles[title] = entry["line"]

    # --- الخانات: موعد مكرر + فيديو مفقود ---
    section = None
    seen_slots = {}
    for i, line in enumerate(lines, 1):
        section = _section_of(line, section)
        if section not in ("scheduled", "planned"):
            continue
        stripped = line.strip()
        if not stripped.startswith("- **"):
            continue
        m = _UNIX_RE.search(stripped)
        if m:
            unix = m.group(1)
            if unix in seen_slots:
                issues.append(
                    "موعد مكرر (Unix %s): السطران %d و%d — خانتان "
                    "لنفس الموعد" % (unix, seen_slots[unix], i))
            else:
                seen_slots[unix] = i
        for ref in _VIDEO_RE.findall(stripped):
            if not os.path.isfile(os.path.expanduser(ref)):
                issues.append("سطر %d: فيديو مشار إليه غير موجود: %s"
                              % (i, ref))
    return issues


def validate_queue_file(path):
    """حقّق ملف طابور؛ ارجع (سليم؟، قائمة مشكلات)."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        return False, ["تعذر قراءة ملف الطابور %s: %s" % (path, e)]
    issues = validate_queue_text(text)
    return (not issues), issues
