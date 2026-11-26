#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""مولّد تقرير دخان APIs — جولة تطبيق الأنماط (W3، فكرة Newman §2.2).

صفحة HTML واحدة (كل endpoint وحالته وزمنه بالمللي ثانية
ورسالة الخطأ) + كاتب JUnit XML يدوي — كلاهما بالمكتبة
القياسية فقط، بلا Node.js وبلا Newman.

شكل النتيجة الواحدة (قاموس):
  {"provider", "model", "endpoint" ("POST /v1/..."),
   "status": "ok" | "failed" | "skipped",
   "elapsed_ms": int | None, "error": str}

الاستخدام:
  python -m lib.smoke_report [--html H] [--junit J]
                             [--results-json R]
- بلا R: كل مدخلات العقد تُسرد «متخطَّى» (الدخان الحي
  لم يُشغَّل — وهذا هو حال CI دائمًا).
- مع R: يُقرأ JSON كتبته اختبارات الدخان الحي
  (STUDIO_SMOKE_REPORT_JSON) فتظهر النتائج الحقيقية.
- لا يفشل أبدًا: أي خطأ داخلي يُطبع تحذيرًا على stderr
  ويُرجع 0 — خطوة التقرير في CI لا تُسقط التشغيل.
"""
import argparse
import html
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from lib import api_contract

STATUS_LABELS = {"ok": "ناجح", "failed": "فاشل",
                 "skipped": "متخطَّى"}
DEFAULT_HTML = "smoke-report.html"
DEFAULT_JUNIT = "smoke-report-junit.xml"


def result(provider, model, endpoint, status,
           elapsed_ms=None, error=""):
    """ابنِ نتيجة واحدة بالشكل المتفق عليه."""
    if status not in STATUS_LABELS:
        raise ValueError("حالة نتيجة غير معروفة: %r" % (status,))
    return {"provider": str(provider), "model": str(model),
            "endpoint": str(endpoint), "status": status,
            "elapsed_ms": elapsed_ms,
            "error": str(error or "")}


def skipped_results(reason):
    """كل مدخلات الدخان في العقد كـ«متخطَّى» مع السبب.

    هذا ما يراه CI دائمًا: الدخان الحي مبوَّب خارج
    التشغيل الافتراضي، فالتقرير يسرد ما كان سيُفحص
    وسبب تخطيه — لا يفشل التشغيل أبدًا.
    """
    out = []
    for entry in api_contract.smoke_entries():
        endpoint = "%s %s" % (entry["method"], entry["path"])
        out.append(result(entry["provider"], entry["model"],
                          endpoint, "skipped", None, reason))
    return out


def summarize(results):
    """عدّادات {ok, failed, skipped, total} من النتائج."""
    counts = {"ok": 0, "failed": 0, "skipped": 0, "total": 0}
    for item in (results or []):
        counts["total"] += 1
        if item.get("status") in counts:
            counts[item["status"]] += 1
    return counts


def _fmt_ms(value):
    if value is None:
        return "—"
    try:
        return "%d" % int(value)
    except (TypeError, ValueError):
        return "—"


def render_html(results, title="تقرير دخان APIs — qisas-studio",
                generated_at=None):
    """صفحة HTML واحدة: كل endpoint وحالته وزمنه وخطئه."""
    results = list(results or [])
    counts = summarize(results)
    when = generated_at or time.strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for item in results:
        status = item.get("status", "skipped")
        rows.append(
            "<tr><td>%s</td><td>%s</td><td><code>%s</code></td>"
            "<td class=\"%s\">%s</td><td>%s</td><td>%s</td></tr>"
            % (html.escape(str(item.get("provider", ""))),
               html.escape(str(item.get("model", ""))),
               html.escape(str(item.get("endpoint", ""))),
               html.escape(str(status)),
               html.escape(STATUS_LABELS.get(status, status)),
               _fmt_ms(item.get("elapsed_ms")),
               html.escape(str(item.get("error", "")))))
    if not rows:
        rows.append("<tr><td colspan=\"6\">لا نتائج — العقد فارغ."
                    "</td></tr>")
    return (
        "<!DOCTYPE html>\n<html lang=\"ar\" dir=\"rtl\">\n<head>\n"
        "<meta charset=\"utf-8\">\n<title>%s</title>\n"
        "<style>body{font-family:sans-serif;margin:2em}"
        "table{border-collapse:collapse;width:100%%}"
        "th,td{border:1px solid #999;padding:.4em;text-align:right}"
        ".ok{color:green}.failed{color:red}.skipped{color:#888}"
        "</style>\n</head>\n<body>\n<h1>%s</h1>\n"
        "<p>أُنشئ: %s — الإجمالي: %d (ناجح %d، فاشل %d، "
        "متخطَّى %d)</p>\n"
        "<table>\n<tr><th>المزود</th><th>النموذج</th>"
        "<th>المسار</th><th>الحالة</th><th>الزمن (ms)</th>"
        "<th>رسالة الخطأ</th></tr>\n%s\n</table>\n"
        "</body>\n</html>\n"
        % (html.escape(title), html.escape(title),
           html.escape(when), counts["total"], counts["ok"],
           counts["failed"], counts["skipped"],
           "\n".join(rows)))


def _xml_escape(text):
    return html.escape(str(text or ""), quote=True)


def render_junit(results, suite_name="studio-api-smoke"):
    """JUnit XML يدوي (~30 سطرًا) — يقرأه GitHub Actions."""
    from xml.sax.saxutils import quoteattr
    results = list(results or [])
    counts = summarize(results)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<testsuites>',
             '<testsuite name=%s tests="%d" failures="%d" '
             'skipped="%d">'
             % (quoteattr(suite_name), counts["total"],
                counts["failed"], counts["skipped"])]
    for item in results:
        name = "%s/%s %s" % (item.get("provider", ""),
                             item.get("model", ""),
                             item.get("endpoint", ""))
        elapsed = item.get("elapsed_ms")
        seconds = ("%.3f" % (elapsed / 1000.0)
                   if isinstance(elapsed, (int, float)) else "0.000")
        lines.append('  <testcase classname=%s name=%s time=%s>'
                     % (quoteattr(suite_name), quoteattr(name),
                        quoteattr(seconds)))
        status = item.get("status")
        if status == "failed":
            lines.append('    <failure message=%s>%s</failure>'
                         % (quoteattr(item.get("error", "فشل")[:500]),
                            _xml_escape(item.get("error", ""))))
        elif status == "skipped":
            lines.append('    <skipped message=%s />'
                         % quoteattr(item.get("error", "")[:500]))
        lines.append('  </testcase>')
    lines.append('</testsuite>')
    lines.append('</testsuites>')
    return "\n".join(lines) + "\n"


def load_results_json(path):
    """اقرأ نتائج JSON (قائمة قواميس) — خطأ الشكل ValueError."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError("ملف النتائج ليس قائمة: %s" % path)
    out = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("نتيجة ليست قاموسًا في %s" % path)
        out.append(result(item.get("provider", "?"),
                          item.get("model", "?"),
                          item.get("endpoint", "?"),
                          item.get("status", "skipped"),
                          item.get("elapsed_ms"),
                          item.get("error", "")))
    return out


def write_report(results, html_path, junit_path=None):
    """اكتب HTML وJUnit (إن أُعطي مساره)؛ يرجع المسارات."""
    written = []
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(results))
    written.append(html_path)
    if junit_path:
        with open(junit_path, "w", encoding="utf-8") as fh:
            fh.write(render_junit(results))
        written.append(junit_path)
    return written


def collect_results(results_json=None):
    """نتائج التقرير: من JSON إن وُجد، وإلا «متخطَّى» من العقد."""
    if results_json and os.path.isfile(results_json):
        return load_results_json(results_json)
    if os.environ.get("STUDIO_LIVE_SMOKE") == "1":
        reason = ("الدخان الحي مفعّل لكن ملف النتائج غير موجود "
                  "(شغّل الاختبار مع STUDIO_SMOKE_REPORT_JSON) "
                  "— لا نتائج حقيقية بعد.")
    else:
        reason = ("الدخان الحي مبوَّب خارج التشغيل الافتراضي "
                  "(STUDIO_LIVE_SMOKE غير مفعّل) — يُشغَّل عند "
                  "الطلب أو في cron ليلي، لا في كل push.")
    return skipped_results(reason)


def main(argv=None):
    """نقطة دخول CLI — لا ترفع أبدًا (ترجع 0 دائمًا)."""
    parser = argparse.ArgumentParser(
        description="ولّد تقرير دخان APIs (HTML + JUnit).")
    parser.add_argument("--html", default=DEFAULT_HTML)
    parser.add_argument("--junit", default=DEFAULT_JUNIT)
    parser.add_argument("--results-json", default=None)
    args = parser.parse_args(argv)
    try:
        results = collect_results(args.results_json)
        write_report(results, args.html, args.junit)
        counts = summarize(results)
        print("تقرير الدخان: %d نتيجة (ناجح %d، فاشل %d، "
              "متخطَّى %d) — %s + %s"
              % (counts["total"], counts["ok"], counts["failed"],
                 counts["skipped"], args.html, args.junit))
    except Exception as exc:  # noqa: BLE001 — التقرير لا يُسقط CI
        print("تحذير: تعذّر توليد تقرير الدخان: %s" % exc,
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
