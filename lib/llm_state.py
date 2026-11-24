#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""حالة مزودي LLM — جولة v0.1.38 (سلسلة FreeLLMAPI).

ملف `runs/llm-provider-state.json` يسجّل لكل مزود (مفتاحه
اسم الموديل، مثل `ddgw/gpt-5.4-mini` أو
`gemini-3-flash-preview`): آخر خطأ ونوعه ووقته، ووقت انتهاء
التهدئة بعد خطأ حصة (429/402)، وعدادات يومية دائمة
(مكالمات/نجاحات/فشل لكل مزود حسب التاريخ).

الملف بلا أسرار إطلاقًا (أسماء موديلات وأوقات وعدادات فقط)
— لا مفاتيح ولا توكنات. الكتابة ذرية (ملف مؤقت + استبدال).
ملف تالف أو مفقود يُعامل كحالة جديدة بلا فشل.
"""
import json
import os
import time

STATE_FILENAME = "llm-provider-state.json"

# مدة التهدئة بعد خطأ حصة (429/402): 10 دقائق.
COOLDOWN_SECONDS = 600

# أنواع الأخطاء التي تُدخل المزود في تهدئة.
QUOTA_KINDS = ("quota",)


def default_state():
    """حالة فارغة جديدة."""
    return {"version": 1, "providers": {},
            "daily": {"date": time.strftime("%Y-%m-%d"),
                      "calls": {}, "successes": {}, "failures": {}}}


def state_path(runs_dir=None):
    """مسار ملف الحالة (مجلد التشغيل أو runs في الدليل الحالي)."""
    base = runs_dir or os.path.join(os.getcwd(), "runs")
    return os.path.join(base, STATE_FILENAME)


def load_state(runs_dir=None):
    """اقرأ ملف الحالة؛ مفقود أو تالف ← حالة جديدة."""
    path = state_path(runs_dir)
    try:
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        return default_state()
    if not isinstance(state, dict) or state.get("version") != 1:
        return default_state()
    state.setdefault("providers", {})
    state.setdefault("daily", {"date": time.strftime("%Y-%m-%d"),
                               "calls": {}, "successes": {},
                               "failures": {}})
    return state


def save_state(state, runs_dir=None):
    """اكتب ملف الحالة ذريًا؛ ارجع المسار."""
    path = state_path(runs_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


def _today():
    return time.strftime("%Y-%m-%d")


def _rollover_daily(state, now=None):
    """صفّر عدادات اليوم عند تغير التاريخ."""
    today = time.strftime("%Y-%m-%d",
                          time.localtime(now) if now else None)
    daily = state.setdefault("daily", {})
    if daily.get("date") != today:
        daily.update({"date": today, "calls": {}, "successes": {},
                      "failures": {}})
    daily.setdefault("calls", {})
    daily.setdefault("successes", {})
    daily.setdefault("failures", {})
    return daily


def record_attempt(state, provider, ok, error_kind=None, now=None):
    """سجّل محاولة مزود: عداد يومي + حالة المزود.

    ok=True: نجاح (يمسح التهدئة). ok=False مع error_kind
    "quota": تهدئة 10 دقائق من الآن. أي خطأ آخر: يُسجَّل
    بلا تهدئة. يرجع الحالة نفسها.
    """
    now = now if now is not None else time.time()
    provider = str(provider)
    daily = _rollover_daily(state, now)
    daily["calls"][provider] = daily["calls"].get(provider, 0) + 1
    entry = state.setdefault("providers", {}).setdefault(provider, {})
    entry["last_attempt_at"] = time.strftime(
        "%Y-%m-%dT%H:%M:%S", time.localtime(now))
    if ok:
        daily["successes"][provider] = \
            daily["successes"].get(provider, 0) + 1
        entry["last_error"] = None
        entry["last_error_kind"] = None
        entry["cooldown_until"] = None
        entry["consecutive_quota"] = 0
    else:
        daily["failures"][provider] = \
            daily["failures"].get(provider, 0) + 1
        entry["last_error_kind"] = error_kind or "unknown"
        entry["last_error_at"] = entry["last_attempt_at"]
        if (error_kind or "") in QUOTA_KINDS:
            entry["consecutive_quota"] = \
                entry.get("consecutive_quota", 0) + 1
            entry["cooldown_until"] = time.strftime(
                "%Y-%m-%dT%H:%M:%S",
                time.localtime(now + COOLDOWN_SECONDS))
        else:
            entry["consecutive_quota"] = 0
    return state


def _parse_time(text):
    try:
        return time.mktime(time.strptime(text, "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def cooling_down(state, provider, now=None):
    """هل المزود في تهدئة؟ يرجع (نعم؟، ثوانٍ متبقية)."""
    now = now if now is not None else time.time()
    entry = (state.get("providers") or {}).get(str(provider)) or {}
    until = _parse_time(entry.get("cooldown_until"))
    if until is None or until <= now:
        return False, 0
    return True, int(until - now)


def provider_status(state, provider):
    """حالة مزود واحد: {provider, cooling_down, cooldown_seconds,
    last_error_kind, last_error_at, calls_today, successes_today,
    failures_today}."""
    provider = str(provider)
    cooling, remaining = cooling_down(state, provider)
    daily = state.get("daily") or {}
    entry = (state.get("providers") or {}).get(provider) or {}
    return {"provider": provider,
            "cooling_down": cooling,
            "cooldown_seconds": remaining,
            "last_error_kind": entry.get("last_error_kind"),
            "last_error_at": entry.get("last_error_at"),
            "calls_today": (daily.get("calls") or {}).get(provider, 0),
            "successes_today": (daily.get("successes") or {})
                               .get(provider, 0),
            "failures_today": (daily.get("failures") or {})
                             .get(provider, 0)}


def status_lines(state, providers=None, now=None):
    """سطور عربية لحالة المزودين (لأمر llm-status).

    تدوير يومي أولًا في الذاكرة (بلا كتابة ملف): حالة
    بتاريخ الأمس تطبع تاريخ اليوم وعدادات صفرية لا تاريخ
    الأمس وعداداته — وإلا بدا «اليوم» قديمًا والعدادات
    منقولة من أمس (علة 2026-11-23).
    """
    now = now if now is not None else time.time()
    _rollover_daily(state, now)
    names = list(providers or [])
    if not names:
        names = sorted((state.get("providers") or {}).keys())
    daily = state.get("daily") or {}
    lines = ["حالة مزودي الذكاء — %s (اليوم: %s)"
             % (time.strftime("%Y-%m-%d %H:%M",
                              time.localtime(now)),
                daily.get("date", "—"))]
    if not names:
        lines.append("لا مزودين مسجَّلين بعد — لم تُجرِ أي مكالمة LLM")
        return lines
    for name in names:
        status = provider_status(state, name)
        if status["cooling_down"]:
            state_text = "في تهدئة (حصة) — متبقٍ %d ثانية" % \
                status["cooldown_seconds"]
        elif status["last_error_kind"]:
            state_text = "آخر خطأ: %s (%s)" % (
                status["last_error_kind"],
                status["last_error_at"] or "—")
        elif status["calls_today"]:
            state_text = "سليم"
        else:
            state_text = "لم يُستدعَ اليوم"
        lines.append("  %s — %s — مكالمات اليوم %d (ناجحة %d، فاشلة %d)"
                     % (name, state_text, status["calls_today"],
                        status["successes_today"],
                        status["failures_today"]))
    return lines
