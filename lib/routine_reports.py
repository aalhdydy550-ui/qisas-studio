#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""تقارير الروتينات — جولة v0.1.63 (بند 20).

اتفاقية NOTHING NEW: الروتين الذي لا شيء جديد عنده يجيب
كائن JSON صغيرًا واحدًا `{"quiet": true}` — يُقرأ ولا
يُنشر أبدًا، وعناصره (إن وُجدت) تنتظر الفحص التالي.
إجابة مشوّهة (ليست JSON، أو ليست كائنًا، أو فيها حقل
غير معروف، أو quiet متناقض مع عناصر) تُفشل الجولة —
لا تُنشر أبدًا ولا تُقرأ كـ«لا جديد».

هذه الوحدة دوال نقية بلا ملفات وبلا شبكة: تستقبل إجابة
(قاموس أو نص JSON) وترجع نسخة موحّدة
{"quiet": bool, "items": [...], "checked_at": str|None}.
الكتابة في السجل والفشل الفعلي للجولة عند المستدعي
(lib/schedule_watch.py: record_no_new_data /
record_check_failed).
"""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

CAIRO = ZoneInfo("Africa/Cairo")

# اتفاقية NOTHING NEW — كائن واحد صغير، يُقرأ ولا يُنشر أبدًا.
NOTHING_NEW = {"quiet": True}

# الحقول الوحيدة المسموحة في إجابة روتين؛ أي حقل آخر
# يجعل الإجابة مشوّهة (لا تُقرأ).
_ALLOWED_KEYS = frozenset({"quiet", "items", "checked_at"})


class RoutineReportError(Exception):
    """إجابة روتين مشوّهة — تُفشل الجولة ولا تُنشر (رسالتها عربية)."""


def now_cairo_iso():
    """الآن بتوقيت القاهرة بصيغة ISO."""
    return datetime.now(tz=CAIRO).isoformat(timespec="seconds")


def nothing_new(checked_at=None):
    """اتفاقية NOTHING NEW: {"quiet": true, "checked_at": ...}.

    «لا جديد → لا دور ولا جولة، فقط checked at» — الطابع
    الزمني هو كل ما تتركه جولة بلا جديد.
    """
    return {"quiet": True,
            "checked_at": checked_at or now_cairo_iso()}


def parse_routine_report(raw):
    """حلّل إجابة روتين ووحّدها؛ وارفع RoutineReportError إن مشوّهة.

    raw: قاموس، أو نص JSON لكائن، أو None (بلا إجابة =
    مشوّهة). القواعد:
    - quiet=True مع عناصر غير فارغة ← تناقض ← مشوّهة.
    - quiet=False (أو غائب) مع عناصر غير فارغة ← قابلة
      للنشر (quiet=False).
    - بلا عناصر وبلا quiet=True ← إجابة فارغة مشوّهة
      (ليست «لا جديد» — «لا جديد» لها صيغتها الصريحة).
    - عناصر ليست قائمة، أو عنصر ليس قاموسًا/نصًا، أو
      quiet ليس منطقيًا، أو checked_at ليس نصًا، أو حقل
      غير معروف ← مشوّهة.
    يرجع {"quiet": bool, "items": list,
           "checked_at": str|None} — نسخة جديدة دائمًا.
    """
    if raw is None:
        raise RoutineReportError(
            "إجابة الروتين مفقودة — بلا إجابة تُفشل الجولة")
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            raise RoutineReportError(
                "إجابة الروتين فارغة — بلا إجابة تُفشل الجولة")
        try:
            raw = json.loads(text)
        except ValueError:
            raise RoutineReportError(
                "إجابة الروتين ليست JSON صالحًا — تُفشل الجولة")
    if not isinstance(raw, dict):
        raise RoutineReportError(
            "إجابة الروتين ليست كائن JSON — تُفشل الجولة")
    unknown = set(raw) - _ALLOWED_KEYS
    if unknown:
        raise RoutineReportError(
            "إجابة الروتين فيها حقل غير معروف (%s) — تُفشل "
            "الجولة" % ", ".join(sorted(unknown)))
    quiet = raw.get("quiet", False)
    if not isinstance(quiet, bool):
        raise RoutineReportError(
            "حقل quiet في إجابة الروتين ليس true/false — تُفشل "
            "الجولة")
    items = raw.get("items", [])
    if items is None:
        items = []
    if not isinstance(items, list):
        raise RoutineReportError(
            "حقل items في إجابة الروتين ليس قائمة — تُفشل الجولة")
    for item in items:
        if not isinstance(item, (dict, str)):
            raise RoutineReportError(
                "عنصر في إجابة الروتين ليس قاموسًا ولا نصًا — "
                "تُفشل الجولة")
    checked_at = raw.get("checked_at")
    if checked_at is not None and not isinstance(checked_at, str):
        raise RoutineReportError(
            "حقل checked_at في إجابة الروتين ليس نصًا — تُفشل "
            "الجولة")
    if quiet and items:
        raise RoutineReportError(
            "إجابة الروتين متناقضة: quiet=true مع عناصر — تُفشل "
            "الجولة")
    if not quiet and not items:
        raise RoutineReportError(
            "إجابة الروتين بلا عناصر وبلا quiet=true — ليست "
            "«لا جديد» ولا تقريرًا قابلًا للنشر؛ تُفشل الجولة")
    return {"quiet": bool(quiet), "items": list(items),
            "checked_at": checked_at}


def validate_routine_report(raw):
    """تحقق بلا رفع: (صالح؟، رسالة الخطأ أو None).

    غلاف حول parse_routine_report للمستدعين الذين يريدون
    قرارًا لا استثناءً.
    """
    try:
        parse_routine_report(raw)
    except RoutineReportError as exc:
        return False, str(exc)
    return True, None


def is_quiet(raw):
    """هل الإجابة اتفاقية NOTHING NEW؟ (مشوّهة ← False)."""
    try:
        return parse_routine_report(raw)["quiet"]
    except RoutineReportError:
        return False


def should_publish(raw):
    """هل تُنشر الإجابة؟ True فقط لغير الهادئة ذات العناصر.

    الهادئة لا تُنشر أبدًا؛ والمشوّهة لا تُنشر أبدًا (تُفشل
    الجولة بدلًا من ذلك عند parse_routine_report).
    """
    try:
        report = parse_routine_report(raw)
    except RoutineReportError:
        return False
    return (not report["quiet"]) and bool(report["items"])


def format_nothing_new(checked_at=None):
    """سطر NOTHING NEW جاهز للسجل: quiet + checked_at فقط."""
    return nothing_new(checked_at=checked_at)
