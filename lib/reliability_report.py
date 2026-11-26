#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""تقرير موثوقية 30 يومًا — جولة v0.1.60 (النمط من مشروع OpenSRE ‏(Tracer-Cloud/opensre، ‏main، ‏d3d0af888005dd6ed29cb5a5ec7223c6150b1fdf، ‏Apache-2.0) — الفكرة فقط، والتنفيذ من الصفر بالمكتبة القياسية بلا نسخ كود أو نصوص).

يبني `build_reliability_report` تقريرًا من قائمة سجلات تشغيل
جاهزة (تُمرَّر كبيانات — الوحدة خالصة، بلا قراءة ملفات وبلا
شبكة): معدلات الفشل إجمالًا ولكل نوع، وتصنيف الفشل حسب
الفئة (بيئة/كود/خارجي/غير معروف)، والزمن الأحمر لكل نوع
(من أول فشل حتى أول نجاح تالٍ من النوع نفسه، وإن بقيت
الفترة مفتوحة حتى نهاية النافذة تُحسب حتى نهايتها)، ومتوسط
الزمن بين فشلين متتاليين (MTBF) ومتوسط زمن الاسترداد (MTTR).

شكل السجل الواحد:
  {"id": str, "kind": "test-suite"|"cron"|"publish"|"build",
   "started_at": ISO-8601 str, "duration_s": number,
   "status": "ok"|"failed", "failure_text": str (اختياري),
   "failure_class": "environment"|"code"|"external"|"unknown"
   (اختياري)}

السجل التالف (بلا id، أو بلا started_at صالح، أو status غير
ok/failed) يُتخطى ويُعدّ في `skipped` ولا يُسقط الدالة أبدًا.
مفاتيح JSON إنجليزية ASCII، والنصوص البشرية عربية.
"""
from datetime import datetime, timedelta, timezone

__all__ = ["build_reliability_report", "KNOWN_KINDS",
           "KNOWN_CLASSES"]

KNOWN_KINDS = ("test-suite", "cron", "publish", "build")
KNOWN_CLASSES = ("environment", "code", "external", "unknown")


def _parse_started_at(value):
    """حلّل ISO-8601 إلى datetime واعٍ (UTC) — None إن تعذّر.

    يقبل اللاحقة Z، ويقبل التاريخ بلا وقت، ويعامل التاريخ
    الساذج (بلا منطقة زمنية) على أنه UTC.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _rate(failed, total):
    """معدل فشل 0..1 مقربًا 4 خانات (0.0 بلا تشغيلات)."""
    if total <= 0:
        return 0.0
    return round(failed / total, 4)


def _seconds(delta):
    """ثواني timedelta كعدد عشري مقرب 4 خانات."""
    return round(delta.total_seconds(), 4)


def _empty_kind_stats():
    return {"total": 0, "ok": 0, "failed": 0, "failure_rate": 0.0}


def build_reliability_report(runs, window_days=30):
    """ابنِ تقرير موثوقية من سجلات تشغيل جاهزة.

    `runs`: قائمة قواميس بالشكل الموثق في docstring الوحدة.
    `window_days`: طول النافذة بالأيام (الافتراضي 30)؛ نهاية
    النافذة = أحدث `started_at` بين السجلات الصالحة، وبدايتها
    = النهاية ناقص `window_days`. مدخل فارغ يرجع تقريرًا
    صفريًا صالحًا (النافذة بلا تواريخ، وmtbf/mttr ‏null).
    """
    try:
        days = int(window_days)
    except (TypeError, ValueError):
        days = 30
    if days <= 0:
        days = 30

    skipped = 0
    valid = []  # (started_at, record) مرتبة زمنيًا لاحقًا
    notes = []
    unknown_kind_seen = False

    for record in (runs or []):
        if not isinstance(record, dict):
            skipped += 1
            continue
        run_id = record.get("id")
        if run_id is None or (isinstance(run_id, str)
                              and not run_id.strip()):
            skipped += 1
            continue
        started_at = _parse_started_at(record.get("started_at"))
        if started_at is None:
            skipped += 1
            continue
        if record.get("status") not in ("ok", "failed"):
            skipped += 1
            continue
        valid.append((started_at, record))

    # الترتيب زمنيًا (الدالة ترتّب بنفسها مهما كان ترتيب المدخل).
    valid.sort(key=lambda item: (item[0], str(item[1].get("id"))))

    total = len(valid)
    ok_count = sum(1 for _, r in valid if r["status"] == "ok")
    failed_count = total - ok_count

    if total == 0:
        window = {"days": days, "start": None, "end": None}
    else:
        end = valid[-1][0]
        start = end - timedelta(days=days)
        window = {"days": days, "start": start.isoformat(),
                  "end": end.isoformat()}

    by_kind = {kind: _empty_kind_stats() for kind in KNOWN_KINDS}
    for _, record in valid:
        kind = record.get("kind")
        if kind not in KNOWN_KINDS:
            kind = "unknown"
            unknown_kind_seen = True
        stats = by_kind.setdefault(kind, _empty_kind_stats())
        stats["total"] += 1
        if record["status"] == "ok":
            stats["ok"] += 1
        else:
            stats["failed"] += 1
    for stats in by_kind.values():
        stats["failure_rate"] = _rate(stats["failed"],
                                      stats["total"])

    by_class = {cls: 0 for cls in KNOWN_CLASSES}
    by_class["unclassified"] = 0
    for _, record in valid:
        if record["status"] != "failed":
            continue
        cls = record.get("failure_class")
        if cls in KNOWN_CLASSES:
            by_class[cls] += 1
        else:
            by_class["unclassified"] += 1

    # الزمن الأحمر لكل نوع + MTTR (فترات مغلقة فقط).
    total_red = timedelta(0)
    longest_red = timedelta(0)
    red_periods = 0
    recoveries = []  # ثواني كل فترة حمراء مغلقة بنجاح تالٍ
    open_red = False
    if total:
        window_end = valid[-1][0]
        for kind in by_kind:
            red_start = None
            for started_at, record in valid:
                if record.get("kind") not in KNOWN_KINDS:
                    record_kind = "unknown"
                else:
                    record_kind = record.get("kind")
                if record_kind != kind:
                    continue
                if record["status"] == "failed":
                    if red_start is None:
                        red_start = started_at
                elif red_start is not None:
                    span = started_at - red_start
                    total_red += span
                    longest_red = max(longest_red, span)
                    red_periods += 1
                    recoveries.append(span.total_seconds())
                    red_start = None
            if red_start is not None:
                span = window_end - red_start
                total_red += span
                longest_red = max(longest_red, span)
                red_periods += 1
                open_red = True

    # MTBF: متوسط الفارق بين فشلين متتاليين (كل الأنواع معًا).
    failure_times = [started_at for started_at, record in valid
                     if record["status"] == "failed"]
    if len(failure_times) >= 2:
        gaps = [(later - earlier).total_seconds()
                for earlier, later in zip(failure_times,
                                          failure_times[1:])]
        mtbf_s = round(sum(gaps) / len(gaps), 4)
    else:
        mtbf_s = None

    if recoveries:
        mttr_s = round(sum(recoveries) / len(recoveries), 4)
    else:
        mttr_s = None

    if total == 0:
        notes.append("لا توجد تشغيلات في النافذة.")
    if skipped:
        notes.append("تُخطّي %d سجلًا تالفًا." % skipped)
    if unknown_kind_seen:
        notes.append("يوجد تشغيل بنوع غير معروف.")
    if by_class["unclassified"]:
        notes.append("يوجد %d فشل بلا تصنيف فئة."
                     % by_class["unclassified"])
    if open_red:
        notes.append("ما زالت فترة حمراء مفتوحة حتى نهاية النافذة.")

    return {
        "window": window,
        "total_runs": total,
        "ok": ok_count,
        "failed": failed_count,
        "failure_rate": _rate(failed_count, total),
        "by_kind": by_kind,
        "by_class": by_class,
        "red_time": {
            "total_red_s": _seconds(total_red),
            "longest_red_s": _seconds(longest_red),
            "red_periods": red_periods,
        },
        "mtbf_s": mtbf_s,
        "mttr_s": mttr_s,
        "skipped": skipped,
        "notes": notes,
    }
