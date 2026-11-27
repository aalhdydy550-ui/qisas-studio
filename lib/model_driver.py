#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""سجل محركات نماذج (Driver SPI) بأخطاء مكتوبة النوع — جولة
v0.1.63 (بند 9).

واجهة محرك واحدة (`send`, `models`, `health`) + ملف لكل
مزوّد + سطر تسجيل واحد؛ ومحرك مجهول يتدهور إلى «غير
متاح» ولا يُسقط السرب أبدًا.

رموز `ProviderError` المكتوبة (عقد ع10) ولكلٍّ قاعدة
تعامل: `retry` (تراجع/إعادة بعد انتظار) أو
`switch_provider` (بدّل المزوّد) أو `stop` (أوقف — خطأ
إعداد يحتاج تدخلًا بشريًا):
- `missing_cli` — أداة سطر الأوامر غائبة → بدّل المزوّد.
- `invalid_credentials` — مفتاح باطل/مصادقة → أوقف.
- `inactive_subscription` — اشتراك غير فعّال → أوقف.
- `insufficient_funds` — رصيد/دفع غير كافٍ → أوقف.
- `quota_or_region_restriction` — حصة/معدل/منطقة → بدّل المزوّد.
- `upstream_outage` — عطل عند المزوّد (5xx) → أعد لاحقًا.
- `model_catalog_outage` — كتالوج النماذج معطل/الموديل
  غير موجود → بدّل المزوّد.
- `turn_not_started` — الدور لم يبدأ → أعد لاحقًا.
- `turn_usage_limit_refused` — رُفض حد استخدام الدور
  (مع `resetsAt` ونطاق engine/model/credits) → بدّل المزوّد.

المحركات المدمجة تغلّف النماذج الموجودة في المشروع
(`lib/omniroute_client.py`: Gemini وFlash-Lite وOllama
وOmniRoute CLI والتناوب المجاني عبر OpenRouter) باستيراد
كسول داخل الدوال — فلا دورات استيراد ولا شبكة عند
استيراد هذه الوحدة.
"""
import os
import shutil

__all__ = [
    "ERROR_CODES", "ERROR_MESSAGES_AR", "ERROR_HANDLING",
    "ProviderError", "classify_provider_error", "handling_for",
    "Driver", "UnknownDriver",
    "register", "get_driver", "list_drivers", "clear_registry",
    "register_builtin_drivers", "failover_driver",
    "driver_health_all",
]

# ─── رموز الأخطاء المكتوبة ───
ERROR_CODES = (
    "missing_cli",
    "invalid_credentials",
    "inactive_subscription",
    "insufficient_funds",
    "quota_or_region_restriction",
    "upstream_outage",
    "model_catalog_outage",
    "turn_not_started",
    "turn_usage_limit_refused",
    "unknown_driver",
    "unknown",
)

ERROR_MESSAGES_AR = {
    "missing_cli": "أداة سطر الأوامر للمزوّد غير موجودة",
    "invalid_credentials": "بيانات اعتماد المزوّد غير صالحة",
    "inactive_subscription": "اشتراك المزوّد غير فعّال",
    "insufficient_funds": "رصيد المزوّد غير كافٍ",
    "quota_or_region_restriction": "تجاوزت حصة المزوّد أو قيد المنطقة",
    "upstream_outage": "المزوّد معطل مؤقتًا",
    "model_catalog_outage": "كتالوج نماذج المزوّد معطل أو الموديل غير موجود",
    "turn_not_started": "دور النموذج لم يبدأ بعد",
    "turn_usage_limit_refused": "رُفض حد استخدام الدور",
    "unknown_driver": "محرك نموذج غير معروف",
    "unknown": "خطأ غير معروف من المزوّد",
}

# قاعدة التعامل لكل رمز: retry | switch_provider | stop.
ERROR_HANDLING = {
    "missing_cli": "switch_provider",
    "invalid_credentials": "stop",
    "inactive_subscription": "stop",
    "insufficient_funds": "stop",
    "quota_or_region_restriction": "switch_provider",
    "upstream_outage": "retry",
    "model_catalog_outage": "switch_provider",
    "turn_not_started": "retry",
    "turn_usage_limit_refused": "switch_provider",
    "unknown_driver": "switch_provider",
    "unknown": "retry",
}


class ProviderError(Exception):
    """خطأ مزوّد مكتوب النوع.

    code: رمز من ERROR_CODES؛ وdetail: تفصيل مختصر عربي
    أو نص المزوّد؛ وresetsAt: وقت إعادة الضبط (لحدود
    الاستخدام)؛ وscope: نطاق الحد engine/model/credits.
    """

    def __init__(self, code, detail="", resets_at=None,
                 scope=None):
        if code not in ERROR_CODES:
            code = "unknown"
        self.code = code
        self.detail = detail or ""
        self.resets_at = resets_at
        self.scope = scope
        message = ERROR_MESSAGES_AR[code]
        if self.detail:
            message = "%s: %s" % (message, self.detail)
        super().__init__(message)


def handling_for(code):
    """قاعدة التعامل لرمز خطأ: retry | switch_provider | stop."""
    return ERROR_HANDLING.get(code, "retry")


# ─── تصنيف أخطاء المزوّدين ───
_QUOTA_PATTERNS = ("429", "402", "rate limit", "rate_limit",
                   "quota", "too many requests",
                   "resource exhausted", "resource_exhausted")
_FUNDS_PATTERNS = ("insufficient funds", "insufficient_funds",
                   "payment required", "out of credits",
                   "no credits", "رصيد غير كاف")
_AUTH_PATTERNS = ("401", "403", "unauthorized",
                  "invalid api key", "invalid_api_key",
                  "api key not valid", "authentication",
                  "permission denied", "invalid credentials")
_SERVER_PATTERNS = ("500", "502", "503", "504",
                    "internal error", "overloaded",
                    "service unavailable", "bad gateway",
                    "upstream")
_CATALOG_PATTERNS = ("model not found", "model_not_found",
                     "catalog", "unknown model",
                     "الموديل غير موجود")
_CLI_PATTERNS = ("command not found", "not found in path",
                 "غير موجود في path", "no such file",
                 "أمر omniroute غير موجود",
                 "مساعد gemini غير موجود")
_SUBSCRIPTION_PATTERNS = ("inactive subscription",
                          "subscription inactive",
                          "subscription expired",
                          "اشتراك غير فعّال")


def classify_provider_error(text, status=None):
    """صنّف رسالة/حالة خطأ مزوّد إلى رمز `ProviderError`.

    status: رمز HTTP (إن وُجد) يفوز على النص: 401/403 ←
    مصادقة، 402 ← رصيد، 429 ← حصة، 404 ← كتالوج،
    5xx ← عطل مزوّد. بلا حالة يُصنَّف النص بالأنماط.
    """
    if status is not None:
        try:
            status = int(status)
        except (TypeError, ValueError):
            status = None
    if status in (401, 403):
        return "invalid_credentials"
    if status == 402:
        return "insufficient_funds"
    if status == 429:
        return "quota_or_region_restriction"
    if status == 404:
        return "model_catalog_outage"
    if status is not None and 500 <= status <= 599:
        return "upstream_outage"
    low = (text or "").lower()
    for pattern in _CLI_PATTERNS:
        if pattern.lower() in low:
            return "missing_cli"
    for pattern in _SUBSCRIPTION_PATTERNS:
        if pattern.lower() in low:
            return "inactive_subscription"
    for pattern in _FUNDS_PATTERNS:
        if pattern.lower() in low:
            return "insufficient_funds"
    for pattern in _QUOTA_PATTERNS:
        if pattern.lower() in low:
            return "quota_or_region_restriction"
    for pattern in _AUTH_PATTERNS:
        if pattern.lower() in low:
            return "invalid_credentials"
    for pattern in _CATALOG_PATTERNS:
        if pattern.lower() in low:
            return "model_catalog_outage"
    for pattern in ("turn_usage_limit", "usage limit refused",
                    "turn usage limit"):
        if pattern in low:
            return "turn_usage_limit_refused"
    for pattern in ("turn not started", "turn_not_started"):
        if pattern in low:
            return "turn_not_started"
    for pattern in _SERVER_PATTERNS:
        if pattern.lower() in low:
            return "upstream_outage"
    return "unknown"


# ─── واجهة المحرك ───
class Driver:
    """واجهة محرك نموذج: `send` / `models` / `health`.

    `send` يرجع نص الرد أو يرفع `ProviderError` برمز
    مكتوب. `health` لا ترمي أبدًا وترجع قاموسًا فيه على
    الأقل {"available": bool, "reason": str}.
    """

    name = "base"

    def send(self, prompt, model=None, system=None,
             max_tokens=200, temperature=0.7, timeout=120):
        """أرسل برومبت وأرجع نص الرد."""
        raise NotImplementedError(
            "المحرك %s لا ينفّذ send" % self.name)

    def models(self):
        """معرّفات النماذج التي يخدمها المحرك."""
        return []

    def health(self):
        """فحص خفيف بلا شبكة ثقيلة — لا يرمي أبدًا."""
        return {"available": False, "reason": "unknown_driver"}


class UnknownDriver(Driver):
    """محرك مجهول: يتدهور إلى «غير متاح» ولا يُسقط السرب."""

    name = "unknown"

    def send(self, prompt, model=None, system=None,
             max_tokens=200, temperature=0.7, timeout=120):
        raise ProviderError("unknown_driver",
                            "لا يوجد محرك مسجل بهذا الاسم")

    def models(self):
        return []

    def health(self):
        return {"available": False, "reason": "unknown_driver"}


# ─── السجل ───
_REGISTRY = {}


def register(name, driver):
    """سجّل محركًا باسم — سطر تسجيل واحد لكل مزوّد.

    يرفع ValueError لاسم فارغ أو محرك بلا واجهة Driver
    (بلا send/models/health).
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("اسم المحرك مطلوب")
    for method in ("send", "models", "health"):
        if not callable(getattr(driver, method, None)):
            raise ValueError(
                "المحرك %s بلا دالة %s" % (name, method))
    _REGISTRY[name.strip()] = driver
    return driver


def get_driver(name):
    """أرجع المحرك المسجل — أو محركًا مجهولًا (لا يرمي أبدًا)."""
    if isinstance(name, str) and name.strip() in _REGISTRY:
        return _REGISTRY[name.strip()]
    return UnknownDriver()


def list_drivers():
    """أسماء المحركات المسجلة مرتبة."""
    return sorted(_REGISTRY)


def clear_registry():
    """أفرغ السجل (للاختبارات وإعادة التسجيل)."""
    _REGISTRY.clear()


def failover_driver(current_name, code):
    """المحرك البديل بعد خطأ — أو None إن كانت القاعدة
    ليست تبديل مزوّد.

    يرجع أول محرك مسجل آخر غير الحالي بترتيب التسجيل
    (المحركات المدمجة مسجلة بترتيب التدهور: Gemini
    Flash-Lite ثم Gemini ثم OpenRouter المجاني ثم Ollama).
    """
    if handling_for(code) != "switch_provider":
        return None
    for name in _REGISTRY:
        if name != current_name:
            return name
    return None


def driver_health_all():
    """حالة كل محرك مسجل: {الاسم: قاموس health} — لا ترمي أبدًا."""
    result = {}
    for name in sorted(_REGISTRY):
        try:
            health = _REGISTRY[name].health()
        except Exception as exc:  # noqa: BLE001 — صحة محرك لا تُسقط الباقي
            health = {"available": False, "reason": "unknown",
                      "detail": str(exc)[:200]}
        if not isinstance(health, dict):
            health = {"available": False, "reason": "unknown"}
        result[name] = health
    return result


# ─── المحركات المدمجة (تغلّف lib/omniroute_client.py) ───
def _translate_error(exc):
    """حوّل خطأ استدعاء إلى ProviderError برمز مكتوب."""
    if isinstance(exc, ProviderError):
        return exc
    status = getattr(exc, "status_code", None)
    code = classify_provider_error(str(exc), status=status)
    return ProviderError(code, str(exc)[:300])


class _GeminiDriver(Driver):
    """محرك Gemini عبر المساعد الآمن (lib/omniroute_client)."""

    def __init__(self, name, model):
        self.name = name
        self._model = model

    def send(self, prompt, model=None, system=None,
             max_tokens=200, temperature=0.7, timeout=120):
        from lib import omniroute_client
        try:
            return omniroute_client.chat_gemini(
                prompt, model=model or self._model, system=system,
                max_tokens=max_tokens, temperature=temperature,
                timeout=timeout)
        except Exception as exc:  # noqa: BLE001 — يُترجم لرمز مكتوب
            raise _translate_error(exc)

    def models(self):
        return [self._model]

    def health(self):
        try:
            from lib import omniroute_client
            helper = omniroute_client.GEMINI_HELPER
            if os.path.isfile(helper):
                return {"available": True, "model": self._model,
                        "detail": "مساعد Gemini موجود"}
            return {"available": False, "reason": "missing_cli",
                    "detail": "مساعد Gemini غير موجود"}
        except Exception as exc:  # noqa: BLE001 — الصحة لا ترمي أبدًا
            return {"available": False, "reason": "unknown",
                    "detail": str(exc)[:200]}


class _OmniRouteDriver(Driver):
    """محرك OmniRoute CLI (نماذج البوابة عبر `omniroute chat`)."""

    name = "omniroute"

    def send(self, prompt, model=None, system=None,
             max_tokens=200, temperature=0.7, timeout=120):
        from lib import omniroute_client
        try:
            return omniroute_client.chat_cli(
                model or "openrouter/free", prompt, system=system,
                max_tokens=max_tokens, temperature=temperature,
                timeout=timeout)
        except Exception as exc:  # noqa: BLE001 — يُترجم لرمز مكتوب
            raise _translate_error(exc)

    def models(self):
        return []

    def health(self):
        if shutil.which("omniroute"):
            return {"available": True,
                    "detail": "أمر omniroute موجود في PATH"}
        return {"available": False, "reason": "missing_cli",
                "detail": "أمر omniroute غير موجود في PATH"}


class _OpenRouterFreeDriver(Driver):
    """محرك التناوب المجاني (OpenRouter ‎:free عبر OmniRoute CLI)."""

    name = "openrouter-free"

    def send(self, prompt, model=None, system=None,
             max_tokens=200, temperature=0.7, timeout=120):
        from lib import omniroute_client
        try:
            models = [model] if model else list(
                omniroute_client.PINNED_FREE_MODELS)
            _text, _via, _used = omniroute_client.chat_free_rotation(
                prompt, models, system=system,
                max_tokens=max_tokens, temperature=temperature,
                timeout=timeout)
            return _text
        except Exception as exc:  # noqa: BLE001 — يُترجم لرمز مكتوب
            raise _translate_error(exc)

    def models(self):
        try:
            from lib import omniroute_client
            return list(omniroute_client.PINNED_FREE_MODELS)
        except Exception:  # noqa: BLE001 — بلا شبكة وبلا رفع
            return ["openrouter/free"]

    def health(self):
        if shutil.which("omniroute"):
            return {"available": True,
                    "model": "openrouter/free",
                    "detail": "فحص خفيف بلا شبكة — التوفر الحقيقي "
                              "يظهر عند أول استدعاء"}
        return {"available": False, "reason": "missing_cli",
                "detail": "أمر omniroute غير موجود في PATH"}


class _OllamaDriver(Driver):
    """محرك Ollama المحلي (ساق أخيرة دون اتصال)."""

    name = "ollama"

    def send(self, prompt, model=None, system=None,
             max_tokens=200, temperature=0.7, timeout=120):
        from lib import omniroute_client
        try:
            return omniroute_client.chat_ollama(
                prompt, model=model or
                omniroute_client.OLLAMA_DEFAULT_MODEL,
                system=system, max_tokens=max_tokens,
                temperature=temperature, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 — يُترجم لرمز مكتوب
            raise _translate_error(exc)

    def models(self):
        try:
            from lib import omniroute_client
            return [omniroute_client.OLLAMA_DEFAULT_MODEL]
        except Exception:  # noqa: BLE001 — بلا رفع
            return ["qwen2.5:7b"]

    def health(self):
        try:
            from lib import omniroute_client
            return omniroute_client.ollama_status(timeout=5)
        except Exception as exc:  # noqa: BLE001 — الصحة لا ترمي أبدًا
            return {"available": False, "reason": "unknown",
                    "detail": str(exc)[:200]}


def register_builtin_drivers():
    """سجّل محركات النماذج الموجودة في المشروع.

    الترتيب هو ترتيب التدهور عند التبديل: Flash-Lite ثم
    Gemini ثم OpenRouter المجاني ثم Ollama المحلي ثم
    OmniRoute CLI. إعادة التسجيل آمنة (تستبدل).
    """
    from lib import omniroute_client
    register("gemini-flash-lite", _GeminiDriver(
        "gemini-flash-lite",
        omniroute_client.GEMINI_LITE_DEFAULT_MODEL))
    register("gemini", _GeminiDriver(
        "gemini", omniroute_client.GEMINI_DEFAULT_MODEL))
    register("openrouter-free", _OpenRouterFreeDriver())
    register("ollama", _OllamaDriver())
    register("omniroute", _OmniRouteDriver())
    return list_drivers()


register_builtin_drivers()
