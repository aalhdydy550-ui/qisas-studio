#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""حالة مزودي LLM — جولة v0.1.38 (سلسلة FreeLLMAPI) + جولة
الأنماط W2 (دفتر حصص منزلق + فحص حصة استباقي).

ملف `runs/llm-provider-state.json` يسجّل لكل مزود (مفتاحه
اسم الموديل، مثل `ddgw/gpt-5.4-mini` أو
`gemini-3-flash-preview`): آخر خطأ ونوعه ووقته، ووقت انتهاء
التهدئة بعد خطأ حصة (429/402)، وعدادات يومية دائمة
(مكالمات/نجاحات/فشل لكل مزود حسب التاريخ).

إضافة W2 — دفتر حصص منزلق: عدّادات RPM/RPD/TPM/TPD لكل
`(مزود، موديل، مفتاح)` في `state["windows"]` (طوابع زمنية
للاستدعاءات والرموز خلال آخر 60 ثانية / 24 ساعة)، مع
جدول حدود افتراضي `DEFAULT_LIMITS` من وثائق المزودين
نفسها (لا من كتالوج وسيط)، ودالة فحص `can_call` يراجعها
المتصل قبل الاستدعاء — فلا يُستدعَى نموذج تجاوز حدّه
أصلًا. وتهدئة استباقية: `apply_proactive_cooldown` تبرّد
المزود حين يقترب استهلاكه من حدّه (80% افتراضيًا)،
وسلّم تهدئة متصاعد عند تكرار خطأ الحصة (10 دقائق ثم
ساعة ثم يوم).

الملف بلا أسرار إطلاقًا (أسماء موديلات وأوقات وعدادات
فقط) — لا مفاتيح ولا توكنات؛ ومعرّف المفتاح `key_id` هو
تسمية يمرّرها المتصل (مثل `default` أو بصمة آخر 4 أحرف)،
وليس المفتاح نفسه أبدًا. الكتابة ذرية (ملف مؤقت +
استبدال). ملف تالف أو مفقود يُعامل كحالة جديدة بلا فشل.
"""
import json
import os
import time

STATE_FILENAME = "llm-provider-state.json"

# مدة التهدئة بعد خطأ حصة (429/402): 10 دقائق.
COOLDOWN_SECONDS = 600

# أنواع الأخطاء التي تُدخل المزود في تهدئة.
QUOTA_KINDS = ("quota",)

# نوافذ العدّادات المنزلقة (ثوانٍ).
WINDOW_MINUTE = 60
WINDOW_DAY = 86400

# عتبة التهدئة الاستباقية: نسبة من الحدّ يبدأ عندها التبريد.
PROACTIVE_THRESHOLD = 0.8
# مدة التهدئة الاستباقية (ثانية) — قصيرة: تنتظر انزلاق النافذة.
PROACTIVE_COOLDOWN_SECONDS = 60

# سلّم التهدئة عند تكرار خطأ الحصة على التوالي: الأول 10
# دقائق (كما قبل)، ثم ساعة، ثم يوم — على غرار سلّم التبريد
# في نمط FreeLLMAPI (فكرة فقط، لا كود منقول).
COOLDOWN_LADDER = (600, 3600, 86400)

# حدود افتراضية لكل مزود (مفاتيحها معرّف المزود كما في
# الحالة: اسم الموديل مثل `ddgw/gpt-5.4-mini`). المصادر:
# - gemini-3-flash-preview: كتالوج FreeLLMAPI الحي
#   2026-11-25 المطابق لحدّ الاستوديو (~20 طلب/يوم):
#   RPM ‏10 / RPD ‏20 / TPM ‏250,000.
# - openai/gpt-oss-120b (Groq): نفس الكتالوج: RPM ‏30 /
#   RPD ‏1000 / TPM ‏8,000 / TPD ‏200,000.
# - google/gemma-4-31b-it:free (OpenRouter ‏:free): RPM ‏20
#   / RPD ‏50 اسميًا؛ والمسبح الحقيقي 50 طلب/يوم على مستوى
#   الحساب (انظر تقرير المسح §2.6).
# - cerebras/gpt-oss-120b (Cerebras Free Trial): صفحة حدود
#   المعدل الرسمية (محدّثة 2026-11-18): RPM ‏5 / TPM غير
#   المخزّن 30,000 / TPM الإجمالي 90,000 / TPH ‏1M /
#   TPD ‏1M — والـTPM هنا غير المخزّن؛ نأخذ 30,000 حدًا
#   متحفظًا. لا شريحة مجانية دائمة (رصيد 5$ لمرة واحدة،
#   30 يومًا) — انظر PROVIDERS-TEST.md.
# مزود بلا حدّ هنا (مثل ddgw) = بلا سقف معروف: فحص الحصة
# يتحقق من التهدئة فقط.
DEFAULT_LIMITS = {
    "gemini-3-flash-preview": {"rpm": 10, "rpd": 20,
                               "tpm": 250000},
    "openai/gpt-oss-120b": {"rpm": 30, "rpd": 1000,
                            "tpm": 8000, "tpd": 200000},
    "google/gemma-4-31b-it:free": {"rpm": 20, "rpd": 50},
    "cerebras/gpt-oss-120b": {"rpm": 5, "tpm": 30000,
                              "tpd": 1000000},
}

# مفاتيح الحدود المعروفة.
LIMIT_KEYS = ("rpm", "rpd", "tpm", "tpd")


def default_state():
    """حالة فارغة جديدة."""
    return {"version": 1, "providers": {},
            "daily": {"date": time.strftime("%Y-%m-%d"),
                      "calls": {}, "successes": {}, "failures": {}},
            "windows": {}, "limits": {}}


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
    # نوافذ/حدود تالفة أو غائبة ← فارغة، بلا فشل.
    windows = state.get("windows")
    if not isinstance(windows, dict):
        state["windows"] = {}
    else:
        for key in list(windows):
            entry = windows[key]
            if not isinstance(entry, dict):
                del windows[key]
                continue
            calls = entry.get("calls")
            entry["calls"] = [c for c in calls
                              if isinstance(c, (int, float))] \
                if isinstance(calls, list) else []
            tokens = entry.get("tokens")
            clean_tokens = []
            if isinstance(tokens, list):
                for item in tokens:
                    if isinstance(item, (list, tuple)) \
                            and len(item) == 2 \
                            and isinstance(item[0], (int, float)) \
                            and isinstance(item[1], (int, float)):
                        clean_tokens.append([item[0], item[1]])
            entry["tokens"] = clean_tokens
    limits = state.get("limits")
    if not isinstance(limits, dict):
        state["limits"] = {}
    else:
        for key in list(limits):
            if not isinstance(limits[key], dict):
                del limits[key]
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


def _quota_key(provider, model=None, key_id="default"):
    """مفتاح دفتر الحصص: `مزود|موديل|معرّف-مفتاح`.

    معرّف المفتاح تسمية فقط (مثل `default`) — ليس المفتاح
    نفسه أبدًا. الموديل الفارغ = المزود نفسه هو الموديل
    (الاتفاق الحالي: `ddgw/gpt-5.4-mini`).
    """
    return "%s|%s|%s" % (str(provider), str(model or ""),
                         str(key_id or "default"))


def get_limits(state, provider, model=None, key_id="default"):
    """حدود (مزود، موديل، مفتاح): تجاوزات الحالة أولًا، ثم
    الافتراضي للمزود. يرجع نسخة (قد تكون فارغة = بلا سقف)."""
    limits = dict(DEFAULT_LIMITS.get(str(provider)) or {})
    stored = (state.get("limits") or {}).get(
        _quota_key(provider, model, key_id)) or {}
    for key in LIMIT_KEYS:
        value = stored.get(key)
        if isinstance(value, int) and value > 0:
            limits[key] = value
    return limits


def set_limits(state, provider, limits, model=None,
               key_id="default"):
    """ثبّت حدودًا مخصصة لـ(مزود، موديل، مفتاح) في الحالة.

    limits: dict جزئي بمفاتيح من rpm/rpd/tpm/tpd وقيم صحيحة
    موجبة؛ مفاتيح غير معروفة أو قيم غير صالحة تُتجاهل.
    يرجع الحالة نفسها.
    """
    clean = {}
    for key in LIMIT_KEYS:
        value = (limits or {}).get(key)
        if isinstance(value, int) and not isinstance(value, bool) \
                and value > 0:
            clean[key] = value
    if clean:
        state.setdefault("limits", {})[
            _quota_key(provider, model, key_id)] = clean
    return state


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


def _prune_windows(state, now):
    """احذف من النوافذ ما تجاوز عمره يومًا كاملًا."""
    windows = state.setdefault("windows", {})
    cutoff = now - WINDOW_DAY
    for key in list(windows):
        entry = windows.get(key) or {}
        calls = [c for c in (entry.get("calls") or [])
                 if c > cutoff]
        tokens = [[t, n] for t, n in (entry.get("tokens") or [])
                  if t > cutoff]
        if not calls and not tokens:
            del windows[key]
        else:
            entry["calls"] = calls
            entry["tokens"] = tokens
    return windows


def _window_counts(state, provider, model=None, key_id="default",
                   now=None):
    """عدّادات النافذة المنزلقة: (مكالمات/دقيقة، مكالمات/يوم،
    رموز/دقيقة، رموز/يوم) من طوابع الاستدعاءات والرموز."""
    now = now if now is not None else time.time()
    entry = (state.get("windows") or {}).get(
        _quota_key(provider, model, key_id)) or {}
    calls = entry.get("calls") or []
    tokens = entry.get("tokens") or []
    minute = now - WINDOW_MINUTE
    day = now - WINDOW_DAY
    rpm = sum(1 for c in calls if c > minute)
    rpd = sum(1 for c in calls if c > day)
    tpm = sum(n for t, n in tokens if t > minute)
    tpd = sum(n for t, n in tokens if t > day)
    return rpm, rpd, tpm, tpd


def _oldest_in_window(items, now, window):
    """أقدم طابع داخل النافذة (أو None)."""
    cutoff = now - window
    inside = [t for t in items if t > cutoff]
    return min(inside) if inside else None


def record_attempt(state, provider, ok, error_kind=None, now=None,
                   model=None, key_id="default", tokens=0):
    """سجّل محاولة مزود: عداد يومي + حالة المزود + نافذة منزلقة.

    ok=True: نجاح (يمسح التهدئة). ok=False مع error_kind
    "quota": تهدئة متصاعدة (10 دقائق، ثم ساعة، ثم يوم عند
    التكرار). أي خطأ آخر: يُسجَّل بلا تهدئة. tokens: عدد
    الرموز المستهلكة في المحاولة (0 = غير معروف — تُعَدّ
    المكالمة فقط). يرجع الحالة نفسها.
    """
    now = now if now is not None else time.time()
    provider = str(provider)
    daily = _rollover_daily(state, now)
    daily["calls"][provider] = daily["calls"].get(provider, 0) + 1
    entry = state.setdefault("providers", {}).setdefault(provider, {})
    entry["last_attempt_at"] = time.strftime(
        "%Y-%m-%dT%H:%M:%S", time.localtime(now))
    # النافذة المنزلقة لكل (مزود، موديل، مفتاح).
    windows = _prune_windows(state, now)
    window = windows.setdefault(
        _quota_key(provider, model, key_id),
        {"calls": [], "tokens": []})
    window.setdefault("calls", []).append(now)
    try:
        tokens = int(tokens)
    except (TypeError, ValueError):
        tokens = 0
    if tokens > 0:
        window.setdefault("tokens", []).append([now, tokens])
    if ok:
        daily["successes"][provider] = \
            daily["successes"].get(provider, 0) + 1
        entry["last_error"] = None
        entry["last_error_kind"] = None
        entry["cooldown_until"] = None
        entry["cooldown_reason"] = None
        entry["consecutive_quota"] = 0
    else:
        daily["failures"][provider] = \
            daily["failures"].get(provider, 0) + 1
        entry["last_error_kind"] = error_kind or "unknown"
        entry["last_error_at"] = entry["last_attempt_at"]
        if (error_kind or "") in QUOTA_KINDS:
            entry["consecutive_quota"] = \
                entry.get("consecutive_quota", 0) + 1
            step = min(entry["consecutive_quota"] - 1,
                       len(COOLDOWN_LADDER) - 1)
            entry["cooldown_until"] = time.strftime(
                "%Y-%m-%dT%H:%M:%S",
                time.localtime(now + COOLDOWN_LADDER[step]))
            entry["cooldown_reason"] = "quota"
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


def usage_fractions(state, provider, model=None, key_id="default",
                    now=None):
    """نسبة الاستهلاك من كل حدّ (0.0 بلا حدّ): {rpm, rpd, tpm, tpd}."""
    now = now if now is not None else time.time()
    limits = get_limits(state, provider, model, key_id)
    rpm, rpd, tpm, tpd = _window_counts(
        state, provider, model, key_id, now)
    used = {"rpm": rpm, "rpd": rpd, "tpm": tpm, "tpd": tpd}
    return {key: (used[key] / limits[key] if limits.get(key) else 0.0)
            for key in LIMIT_KEYS}


def can_call(state, provider, model=None, key_id="default",
             est_tokens=0, now=None):
    """فحص الحصة قبل الاستدعاء — يراجعه المتصل أولًا.

    يرجع (مسموح؟، السبب، ثوانٍ حتى إعادة المحاولة):
    السبب None عند السماح، وإلا واحد من: "cooldown" أو
    "rpm" أو "rpd" أو "tpm" أو "tpd". المزود بلا حدود
    معروفة يُفحص من التهدئة فقط. est_tokens: الرموز
    المتوقعة للطلب (0 = غير معروفة — تُفحص المكالمات فقط).
    النموذج الذي تجاوز حدّه لا يُستدعَى أصلًا.
    """
    now = now if now is not None else time.time()
    cooling, remaining = cooling_down(state, provider, now)
    if cooling:
        return False, "cooldown", remaining
    limits = get_limits(state, provider, model, key_id)
    if not limits:
        return True, None, 0
    rpm, rpd, tpm, tpd = _window_counts(
        state, provider, model, key_id, now)
    try:
        est_tokens = int(est_tokens)
    except (TypeError, ValueError):
        est_tokens = 0
    if est_tokens < 0:
        est_tokens = 0
    entry = (state.get("windows") or {}).get(
        _quota_key(provider, model, key_id)) or {}
    calls = entry.get("calls") or []
    tokens = entry.get("tokens") or []
    if limits.get("rpm") and rpm >= limits["rpm"]:
        oldest = _oldest_in_window(calls, now, WINDOW_MINUTE)
        retry = int(WINDOW_MINUTE - (now - oldest)) + 1 \
            if oldest is not None else WINDOW_MINUTE
        return False, "rpm", max(1, retry)
    if limits.get("rpd") and rpd >= limits["rpd"]:
        oldest = _oldest_in_window(calls, now, WINDOW_DAY)
        retry = int(WINDOW_DAY - (now - oldest)) + 1 \
            if oldest is not None else WINDOW_DAY
        return False, "rpd", max(1, retry)
    if limits.get("tpm") and tpm + est_tokens > limits["tpm"]:
        oldest = _oldest_in_window(
            [t for t, _ in tokens], now, WINDOW_MINUTE)
        retry = int(WINDOW_MINUTE - (now - oldest)) + 1 \
            if oldest is not None else WINDOW_MINUTE
        return False, "tpm", max(1, retry)
    if limits.get("tpd") and tpd + est_tokens > limits["tpd"]:
        oldest = _oldest_in_window(
            [t for t, _ in tokens], now, WINDOW_DAY)
        retry = int(WINDOW_DAY - (now - oldest)) + 1 \
            if oldest is not None else WINDOW_DAY
        return False, "tpd", max(1, retry)
    return True, None, 0


def apply_proactive_cooldown(state, provider, model=None,
                             key_id="default",
                             seconds=PROACTIVE_COOLDOWN_SECONDS,
                             threshold=PROACTIVE_THRESHOLD,
                             now=None):
    """تهدئة استباقية: إن بلغ استهلاك أي حدّ العتبة (80%
    افتراضيًا) برّد المزود مدة قصيرة وارجع True؛ وإلا ارجع
    False بلا تغيير. لا تعيد تبريد مزود في تهدئة أصلًا."""
    now = now if now is not None else time.time()
    cooling, _ = cooling_down(state, provider, now)
    if cooling:
        return False
    fractions = usage_fractions(state, provider, model, key_id, now)
    if not any(f >= threshold for f in fractions.values()):
        return False
    entry = state.setdefault("providers", {}).setdefault(
        str(provider), {})
    entry["cooldown_until"] = time.strftime(
        "%Y-%m-%dT%H:%M:%S", time.localtime(now + seconds))
    entry["cooldown_reason"] = "proactive"
    entry["last_attempt_at"] = entry.get("last_attempt_at") or \
        time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now))
    return True


def provider_status(state, provider, model=None, key_id="default",
                    now=None):
    """حالة مزود واحد: {provider, cooling_down, cooldown_seconds,
    last_error_kind, last_error_at, calls_today, successes_today,
    failures_today, quota_ok, quota_reason, quota_retry_after,
    rpm_calls, rpd_calls, tpm_tokens, tpd_tokens, limits}."""
    provider = str(provider)
    now = now if now is not None else time.time()
    cooling, remaining = cooling_down(state, provider, now)
    allowed, reason, retry = can_call(
        state, provider, model, key_id, now=now)
    daily = state.get("daily") or {}
    entry = (state.get("providers") or {}).get(provider) or {}
    rpm, rpd, tpm, tpd = _window_counts(
        state, provider, model, key_id, now)
    return {"provider": provider,
            "cooling_down": cooling,
            "cooldown_seconds": remaining,
            "last_error_kind": entry.get("last_error_kind"),
            "last_error_at": entry.get("last_error_at"),
            "calls_today": (daily.get("calls") or {}).get(provider, 0),
            "successes_today": (daily.get("successes") or {})
                               .get(provider, 0),
            "failures_today": (daily.get("failures") or {})
                             .get(provider, 0),
            "quota_ok": allowed,
            "quota_reason": reason,
            "quota_retry_after": retry,
            "rpm_calls": rpm,
            "rpd_calls": rpd,
            "tpm_tokens": tpm,
            "tpd_tokens": tpd,
            "limits": get_limits(state, provider, model, key_id)}


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
        status = provider_status(state, name, now=now)
        if status["cooling_down"]:
            state_text = "في تهدئة (حصة) — متبقٍ %d ثانية" % \
                status["cooldown_seconds"]
        elif not status["quota_ok"]:
            state_text = "تجاوز حد الحصة (%s) — متبقٍ %d ثانية" % (
                status["quota_reason"], status["quota_retry_after"])
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
