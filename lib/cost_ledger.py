#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""سجل تكاليف Veo الفعلي — `runs/cost-ledger.jsonl`.

كل سطر JSON: {"date", "video", "clips", "units"} — يُسجَّل يدويًا
بعد كل توليد في Flow عبر `balance --record N --video NAME`
(لأن Flow لا يعرض API للرصيد). الكتابة عبر O_APPEND فالأسطر
لا تتداخل حتى مع تسجيلين متوازيين. الأسطر التالفة تُتخطى
عند القراءة ولا تُسقط السجل كله.
"""
import json
import os
import time


def ledger_path(studio_root):
    return os.path.join(studio_root, "runs", "cost-ledger.jsonl")


def record(studio_root, units, video, clips=None, when=None):
    """سجّل إنفاقًا فعليًا. يرجع القيد. يرفع ValueError لقيم غير صالحة."""
    if not (video or "").strip():
        raise ValueError("اسم الفيديو مطلوب: --video NAME")
    try:
        units = int(units)
    except (TypeError, ValueError):
        raise ValueError("عدد الوحدات يجب أن يكون رقمًا صحيحًا")
    if units <= 0:
        raise ValueError("عدد الوحدات يجب أن يكون أكبر من صفر")
    if clips is not None:
        try:
            clips = int(clips)
        except (TypeError, ValueError):
            raise ValueError("عدد المقاطع يجب أن يكون رقمًا صحيحًا")
        if clips <= 0:
            raise ValueError("عدد المقاطع يجب أن يكون أكبر من صفر")
    entry = {"date": when or time.strftime("%Y-%m-%d %H:%M"),
             "video": video.strip(),
             "clips": clips,
             "units": units}
    path = ledger_path(studio_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = (json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, line)
    finally:
        os.close(fd)
    return entry


def history(studio_root):
    """اقرأ كل القيود (الأقدم أولًا). الأسطر التالفة تُتخطى."""
    path = ledger_path(studio_root)
    entries = []
    if not os.path.isfile(path):
        return entries
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict) and "units" in entry:
                entries.append(entry)
    return entries


def totals(entries):
    """مجاميع السجل: عدد القيود والوحدات والمقاطع."""
    return {"entries": len(entries),
            "units": sum(int(e.get("units") or 0) for e in entries),
            "clips": sum(int(e.get("clips") or 0) for e in entries
                         if e.get("clips") is not None)}


def format_history(entries):
    """نص عربي للسجل + المجاميع."""
    if not entries:
        return ("لا قيود إنفاق مسجلة بعد — سجّل أول توليد:\n"
                "  studio.py balance --record 120 "
                "--video 'اسم الفيديو' --clips 6")
    lines = ["سجل تكاليف Veo (%d قيود):" % len(entries)]
    for e in entries:
        clips = (" — %d مقاطع" % e["clips"]) if e.get("clips") else ""
        lines.append("  %s — %s: %d وحدة%s"
                     % (e.get("date") or "؟", e.get("video") or "؟",
                        e.get("units") or 0, clips))
    t = totals(entries)
    lines.append("المجموع: %d وحدة في %d قيود (%d مقطعًا)"
                 % (t["units"], t["entries"], t["clips"]))
    return "\n".join(lines)
