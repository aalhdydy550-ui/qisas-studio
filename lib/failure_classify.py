#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""تصنيف فشل تشغيل/اختبار إلى بيئة أو كود أو خارجي أو غير معروف.

المصدر (النمط فقط، بلا نسخ): مشروع OpenSRE — مستودع Tracer-Cloud/opensre، الفرع main، الالتزام d3d0af888005dd6ed29cb5a5ec7223c6150b1fdf (2026-11-26)، رخصة Apache-2.0، ~15,734 نجمة؛ النمط المأخوذ منه فصل فشل CI عن فشل الكود (CI-caused مقابل code-caused)، والتنفيذ هنا من الصفر بالمكتبة القياسية.

ترتيب الأولوية (موثّق): إشارات البيئة أولًا، ثم الخارجية، ثم الكود.
فمثلًا Traceback فيه ModuleNotFoundError لـpiper يُصنَّف بيئة لا كود،
لأن غياب حزمة/أداة من البيئة يفسّر الفشل قبل أي خطأ في الكود نفسه.
`signals` في النتيجة هي إشارات الفئة الفائزة فقط (لا كل الإشارات)،
و`confidence` عالية لإشارة محددة واضحة، ومتوسطة لـModuleNotFoundError
عام وحده (اسم حزمة غير معروف)، ومنخفضة عند غياب الإشارات.
"""
import re

SUGGESTION_ENVIRONMENT = (
    "أعد البيئة حسب دروس ~/AGENTS.md (أدوات/روابط/حزم)")
SUGGESTION_CODE = "راجع الاختبار الفاشل وأصلح الكود"
SUGGESTION_EXTERNAL = (
    "انتظر التهدئة ثم أعد المحاولة — لا تكرر فورًا ضد حاجز")
SUGGESTION_UNKNOWN = "لا إشارة كافية — أرفق السجل الكامل"

_SUGGESTIONS = {
    "environment": SUGGESTION_ENVIRONMENT,
    "code": SUGGESTION_CODE,
    "external": SUGGESTION_EXTERNAL,
    "unknown": SUGGESTION_UNKNOWN,
}

# حزم نظامية معروفة في بيئة الاستوديو (الإشارة المحددة لها).
_SYSTEM_MODULES = {"piper", "anyio", "mcp", "pil", "pillow"}

# مضيفات خارجية معروفة (لإشارة "Connection timed out").
_EXTERNAL_HOSTS = (
    "github", "facebook", "tiktok", "google", "youtube",
    "openrouter", "huggingface", "openai", "anthropic", "groq",
    "vidiq",
)

_CODE_TRACEBACK_ERRORS = ("KeyError", "TypeError", "ValueError",
                          "AttributeError")


def _env_signals(text, lower):
    """إشارات البيئة (بالترتيب الثابت داخل الفئة)."""
    signals = []
    if "pythonnousersite" in lower:
        signals.append("pythonnousersite")
    # ModuleNotFoundError: محدد (piper/anyio/mcp/PIL) أو عام.
    for match in re.finditer(
            r"ModuleNotFoundError[^'\"]*['\"]([^'\"]+)['\"]", text):
        name = match.group(1).strip().split(".")[0].lower()
        if name in _SYSTEM_MODULES:
            signal = "module_not_found_%s" % name
        else:
            signal = "module_not_found"
        if signal not in signals:
            signals.append(signal)
    if "modulenotfounderror" in lower and not signals:
        # بلا اسم حزمة مقتبس — إشارة عامة ضعيفة لكنها بيئة.
        signals.append("module_not_found")
    if "melt" in lower and (
            "home-tools missing: melt" in lower
            or "links missing: melt" in lower
            or "not found" in lower
            or "missing" in lower):
        signals.append("melt_missing")
    if "could not get lock" in lower or "dpkg lock" in lower:
        signals.append("apt_lock")
    if "SIGTERM" in text:
        signals.append("sigterm")
    if "setup-env.sh" in text and "timed out" in lower:
        signals.append("setup_env_timeout")
    if "mesa-vulkan" in lower or "lavapipe" in lower:
        signals.append("mesa_vulkan")
    if "ERR_TUNNEL_CONNECTION_FAILED" in text:
        signals.append("tunnel_connection_failed")
    return signals


def _external_signals(text, lower):
    """إشارات خارجية (بالترتيب الثابت داخل الفئة)."""
    signals = []
    if re.search(r"\b429\b", text):
        signals.append("http_429")
    if "rate limit" in lower or "rate-limit" in lower:
        signals.append("rate_limit")
    if "provider_rate_limit_stop" in lower:
        signals.append("provider_rate_limit_stop")
    if "connector_rate_limited" in lower:
        signals.append("connector_rate_limited")
    if re.search(r"\b403\b", text) and any(
            host in lower for host in ("github", "facebook", "tiktok")):
        signals.append("http_403")
    if re.search(r"\bbot\b", lower):
        signals.append("bot_barrier")
    if "captcha" in lower:
        signals.append("captcha")
    if "policy_denied" in lower:
        signals.append("policy_denied")
    if "حاجز" in text and "bot_barrier" not in signals:
        signals.append("bot_barrier")
    if "connection timed out" in lower and any(
            host in lower for host in _EXTERNAL_HOSTS):
        signals.append("connection_timed_out_external")
    return signals


def _code_signals(text, lower):
    """إشارات الكود (بالترتيب الثابت داخل الفئة)."""
    signals = []
    if "AssertionError" in text:
        signals.append("assertion_error")
    if ("failed (failures=" in lower
            or "failed (errors=" in lower):
        signals.append("unittest_failed")
    if "SyntaxError" in text:
        signals.append("syntax_error")
    # Traceback ينتهي بخطأ كود ومسار من شجرة المشروع.
    idx = text.find("Traceback")
    if idx != -1:
        tail = text[idx:]
        if (any(err in tail for err in _CODE_TRACEBACK_ERRORS)
                and re.search(r"(lib/|tests/|studio\.py)", tail)):
            signals.append("traceback_code_error")
    if (re.search(r"check\s+(8/8|9/9)", lower)
            and re.search(r"\bFAIL\b", text)):
        signals.append("check_failed")
    return signals


def classify_failure(text):
    """صنّف نص فشل (سجل/خرج اختبار) إلى فئة واقتراح للخطوة التالية.

    يرجع {"class": "environment"|"code"|"external"|"unknown",
    "confidence": "high"|"medium"|"low",
    "signals": [أسماء الإشارات المطابقة من الفئة الفائزة],
    "suggestion": "نص عربي قصير بالخطوة التالية"}.
    مدخل فارغ أو بلا إشارات ← unknown/low.
    الأولوية: البيئة، ثم الخارجية، ثم الكود (انظر docstring الوحدة).
    """
    if not text or not isinstance(text, str) or not text.strip():
        return {"class": "unknown", "confidence": "low",
                "signals": [], "suggestion": SUGGESTION_UNKNOWN}
    lower = text.lower()
    env = _env_signals(text, lower)
    external = _external_signals(text, lower)
    code = _code_signals(text, lower)
    if env:
        cls, signals = "environment", env
    elif external:
        cls, signals = "external", external
    elif code:
        cls, signals = "code", code
    else:
        return {"class": "unknown", "confidence": "low",
                "signals": [], "suggestion": SUGGESTION_UNKNOWN}
    if len(signals) >= 2:
        confidence = "high"
    elif signals == ["module_not_found"]:
        # ModuleNotFoundError عام وحده بلا اسم حزمة نظامية معروفة.
        confidence = "medium"
    else:
        confidence = "high"
    return {"class": cls, "confidence": confidence,
            "signals": signals, "suggestion": _SUGGESTIONS[cls]}
