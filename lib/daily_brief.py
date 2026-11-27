#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""الموجز اليومي «راقب يومي» — جولة v0.1.63 (بندا 22 و33، عقد ع16).

موجز واحد في اليوم بأقسام: Needs you / Your day /
Important emails / Routines. نتائج الروتينات تُسلَّم هنا
لا في سطور دردشة مستقلة.

القواعد (ع16):
- موجز فارغ لا يُنشر أبدًا.
- تسليم واحد فقط في المرة — الموجزات الأخرى متوقفة لا محذوفة.
- بطاقات الخادم تحمل `serverCard: true`، لا يعدّلها عامل،
  وتُعاد كسجلات فقط.
- الرفض (dismiss) يفحص ملكية الخيط ويعمل للمالك فقط.
- الحالة في `runs/brief.json`: ملف الموجز، منطقة التسجيل
  Africa/Cairo، الصفوف المهمة بالمعرّف، الرفضات الأخيرة.
- الكرون اليومي 08:00 ليس في الشجرة — إنشاؤه متابعة
  للوكيل الرئيسي.
"""
import json
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

__all__ = [
    "BriefError",
    "SECTIONS",
    "SECTION_TITLES",
    "TIMEZONE",
    "today_cairo",
    "now_cairo_iso",
    "build_brief",
    "is_empty",
    "render_brief",
    "make_server_card",
    "is_server_card",
    "apply_agent_update",
    "dismiss_row",
    "save_state",
    "load_state",
    "deliver_brief",
    "pause_brief",
]

TIMEZONE = "Africa/Cairo"
CAIRO = ZoneInfo(TIMEZONE)

SECTIONS = ("needs_you", "your_day", "important_emails", "routines")
SECTION_TITLES = {
    "needs_you": "Needs you — يحتاجك",
    "your_day": "Your day — يومك",
    "important_emails": "Important emails — بريد مهم",
    "routines": "Routines — روتينات",
}
STATE_FILENAME = "brief.json"


class BriefError(Exception):
    """خطأ في الموجز اليومي (رسالته عربية)."""


def today_cairo():
    """تاريخ اليوم بتوقيت القاهرة (YYYY-MM-DD)."""
    return datetime.now(tz=CAIRO).date().isoformat()


def now_cairo_iso():
    """الآن بتوقيت القاهرة بصيغة ISO مع المنطقة."""
    return datetime.now(tz=CAIRO).isoformat(timespec="seconds")


def _new_row_id():
    return "row-" + uuid.uuid4().hex[:8]


def _clean_items(items, section):
    """ينظّف صفوف قسم: كل صف معرّف وعنوان نصي."""
    cleaned = []
    for item in items or []:
        if isinstance(item, str):
            item = {"title": item}
        if not isinstance(item, dict):
            raise BriefError("صف غير صالح في قسم %s." % section)
        title = str(item.get("title") or "").strip()
        if not title:
            raise BriefError("صف بلا عنوان في قسم %s." % section)
        cleaned.append(
            {
                "id": str(item.get("id") or _new_row_id()),
                "title": title,
                "detail": str(item.get("detail") or "").strip(),
                "source": str(item.get("source") or "").strip(),
            }
        )
    return cleaned


def build_brief(date=None, *, needs_you=None, your_day=None,
                important_emails=None, routines=None, server_cards=None):
    """يبني موجز يوم: الأقسام الأربعة + بطاقات خادم اختيارية."""
    sections = {
        "needs_you": _clean_items(needs_you, "needs_you"),
        "your_day": _clean_items(your_day, "your_day"),
        "important_emails": _clean_items(important_emails, "important_emails"),
        "routines": _clean_items(routines, "routines"),
    }
    cards = []
    for card in server_cards or []:
        if not is_server_card(card):
            raise BriefError("بطاقة خادم بلا serverCard: true مرفوضة.")
        cards.append(dict(card))
    return {
        "id": "brief-" + (date or today_cairo()),
        "date": date or today_cairo(),
        "timezone": TIMEZONE,
        "sections": sections,
        "server_cards": cards,
        "status": "draft",
        "dismissed": [],
    }


def is_empty(brief):
    """هل الموجز فارغ؟ كل الأقسام فارغة وبلا بطاقات خادم."""
    sections = brief.get("sections") or {}
    has_rows = any(sections.get(name) for name in SECTIONS)
    return not has_rows and not (brief.get("server_cards") or [])


def render_brief(brief):
    """يصيغ الموجز نصًا عربيًا مقروءًا (الأقسام الأربعة بالترتيب)."""
    lines = [
        "الموجز اليومي — %s (%s)" % (brief.get("date"), TIMEZONE),
        "",
    ]
    sections = brief.get("sections") or {}
    for name in SECTIONS:
        lines.append("## %s" % SECTION_TITLES[name])
        rows = sections.get(name) or []
        if not rows:
            lines.append("- (لا شيء)")
        for row in rows:
            line = "- %s" % row["title"]
            if row.get("detail"):
                line += " — %s" % row["detail"]
            lines.append(line)
        lines.append("")
    for card in brief.get("server_cards") or []:
        lines.append("## بطاقة خادم: %s" % card.get("title"))
        if card.get("body"):
            lines.append(str(card["body"]))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def make_server_card(title, body=""):
    """بطاقة يبنيها النظام: `serverCard: true` ولا يعدّلها عامل."""
    title = str(title or "").strip()
    if not title:
        raise BriefError("بطاقة الخادم تحتاج عنوانًا.")
    return {
        "id": "card-" + uuid.uuid4().hex[:8],
        "serverCard": True,
        "title": title,
        "body": str(body or ""),
    }


def is_server_card(card):
    """هل هذا الكائن بطاقة خادم؟"""
    return isinstance(card, dict) and card.get("serverCard") is True


def apply_agent_update(card, updates):
    """تحديث عامل على بطاقة — مرفوض دائمًا لبطاقة خادم.

    بطاقة الخادم تُعاد كسجل فقط؛ أي محاولة تعديل من عامل
    ترفض بخطأ صريح. بطاقة عادية (بلا serverCard) تُحدَّث
    وتُعاد نسخة جديدة بلا تعديل الأصل.
    """
    if is_server_card(card):
        raise BriefError(
            "بطاقة الخادم غير قابلة للتعديل — تُعاد كسجل فقط."
        )
    if not isinstance(card, dict):
        raise BriefError("بطاقة غير صالحة.")
    updated = dict(card)
    for key, value in (updates or {}).items():
        updated[key] = value
    return updated


def dismiss_row(brief, row_id, *, owner, thread_owner):
    """يرفض صفًا من الموجز — للمالك فقط.

    الرفض يفحص ملكية الخيط: `owner` يجب أن يساوي
    `thread_owner`، وإلا رُفض. يعيد الموجز بعد تسجيل
    الرفض (الصف يبقى في الأقسام موسومًا مرفوضًا لا محذوفًا).
    """
    if owner != thread_owner:
        raise BriefError(
            "الرفض للمالك فقط — هذا الخيط يملكه غيرك."
        )
    found = False
    for name in SECTIONS:
        for row in (brief.get("sections") or {}).get(name) or []:
            if row.get("id") == row_id:
                found = True
    if not found:
        for card in brief.get("server_cards") or []:
            if card.get("id") == row_id:
                found = True
    if not found:
        raise BriefError("لا يوجد صف بالمعرّف: %s" % row_id)
    dismissed = list(brief.get("dismissed") or [])
    if row_id not in dismissed:
        dismissed.append(row_id)
    brief["dismissed"] = dismissed
    return brief


def _state_path(runs_dir):
    return os.path.join(os.path.abspath(runs_dir), STATE_FILENAME)


def save_state(runs_dir, state):
    """يكتب حالة الموجز `runs/brief.json` ذريًا بصلاحيات 0600."""
    path = _state_path(runs_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    return path


def load_state(runs_dir):
    """يقرأ حالة الموجز؛ غياب الملف يعيد حالة فارغة."""
    path = _state_path(runs_dir)
    if not os.path.isfile(path):
        return {
            "brief_file": None,
            "timezone": TIMEZONE,
            "important_rows": [],
            "last_dismissals": [],
            "delivered": {},
        }
    try:
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        raise BriefError("ملف حالة الموجز تالف: %s" % path)
    if not isinstance(state, dict):
        raise BriefError("ملف حالة الموجز ليس قاموسًا.")
    state.setdefault("timezone", TIMEZONE)
    state.setdefault("important_rows", [])
    state.setdefault("last_dismissals", [])
    state.setdefault("delivered", {})
    return state


def deliver_brief(brief, runs_dir, *, brief_file=None):
    """يسلّم الموجز مرة واحدة في اليوم.

    موجز فارغ لا يُنشر أبدًا. موجز آخر لنفس التاريخ سُلّم
    أصلًا يرفض التسليم الثاني (تسليم واحد فقط في المرة).
    يعيد `{"delivered": bool, "reason": ...}` ويسجّل
    الحالة في `runs/brief.json`.
    """
    state = load_state(runs_dir)
    date = brief.get("date") or today_cairo()
    if is_empty(brief):
        return {"delivered": False, "reason": "empty_brief"}
    delivered = state.get("delivered") or {}
    if delivered.get(date):
        return {"delivered": False, "reason": "already_delivered"}
    important = [
        row["id"]
        for name in SECTIONS
        for row in (brief.get("sections") or {}).get(name) or []
        if name in ("needs_you", "important_emails")
    ]
    state["brief_file"] = brief_file or "brief-%s.md" % date
    state["timezone"] = TIMEZONE
    state["important_rows"] = important
    state["last_dismissals"] = list(brief.get("dismissed") or [])
    delivered[date] = {
        "brief_id": brief.get("id"),
        "delivered_at": now_cairo_iso(),
    }
    state["delivered"] = delivered
    save_state(runs_dir, state)
    brief["status"] = "delivered"
    return {"delivered": True, "reason": "delivered", "date": date}


def pause_brief(brief):
    """يوقف موجزًا (لا يحذفه) — الموجزات الأخرى متوقفة لا محذوفة."""
    brief["status"] = "paused"
    return brief
