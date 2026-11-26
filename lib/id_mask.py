#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""إخفاء معرّفات قابل للعكس قبل إخراج البيانات لنماذج خارجية (جولة v0.1.60).

النمط مأخوذ من مشروع OpenSRE (Tracer-Cloud/opensre، ‏Apache-2.0) — إخفاء
المعرّفات قبل إخراج البيانات لنماذج خارجية دون تسريب أسماء — والتنفيذ
هنا من الصفر بالمكتبة القياسية، بلا نسخ كود أو نصوص من المشروع.

القاعدة الأمنية: الأسرار (مفاتيح API ورموز الوصول) تُحجب نهائيًا
بـ `redact_secrets` ولا تُخفى إخفاءً قابلًا للعكس أبدًا — الإخفاء
القابل للعكس للمعرّفات (بريد، أرقام طويلة، هواتف) فقط، والـmapping
يبقى عند المتصل ولا يخرج مع النص المخفي.
"""
import re

__all__ = ["mask_text", "unmask_text", "mask_record", "redact_secrets"]

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+20\d{9,11}|(?<!\d)01\d{9})(?!\d)")
_LONG_ID_RE = re.compile(r"(?<!\d)\d{12,}(?!\d)")
_TOKEN_RE = re.compile(r"\[(EMAIL|ID|PHONE):(\d+)\]")

_SECRET_RES = [
    # Bearer <value> — القيمة كلها مع الكلمة تُستبدل بعلامة واحدة.
    re.compile(r"Bearer\s+\S+"),
    # تعيينات من شكل api_key=... / secret: ... / token=... وما يشبهها.
    re.compile(
        r"(?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    # مفاتيح شبيهة بمفاتيح OpenAI.
    re.compile(r"sk-[A-Za-z0-9_-]+"),
    # رموز GitHub الشخصية وما يشبهها.
    re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    # معرّف مفتاح وصول AWS.
    re.compile(r"AKIA[0-9A-Z]{16}"),
]


def _token_for(mapping, kind, value):
    """رمز حتمي لقيمة: نفس القيمة تأخذ نفس الرمز داخل نفس الـmapping."""
    key = None
    for existing_key, existing_value in mapping.items():
        if existing_key.startswith(kind + ":") and existing_value == value:
            key = existing_key
            break
    if key is None:
        used = sum(1 for k in mapping if k.startswith(kind + ":"))
        key = "%s:%d" % (kind, used + 1)
        mapping[key] = value
    return "[%s]" % key


def mask_text(text, mapping=None):
    """يخفي البريد والأرقام الطويلة والهواتف في نص، ويرجع (النص، mapping).

    الترقيم متسلسل لكل نوع داخل نفس الـmapping، ونفس القيمة الأصلية
    تأخذ نفس الرمز دائمًا. الـmapping قاموس يملكه المتصل ويُمرَّر بين
    الاستدعاءات للاستمرارية. مدخل فارغ يرجع فارغًا مع mapping فارغ.
    """
    if mapping is None:
        mapping = {}
    if not text:
        return "", mapping

    def _mask(kind, pattern, value):
        return pattern.sub(
            lambda m: _token_for(mapping, kind, m.group(0)), value
        )

    # الترتيب مهم: الهاتف قبل الأرقام الطويلة حتى لا يُبتلع رقم الهاتف
    # كمعرّف، والبريد أولًا حتى لا تُمسّ أرقام داخل عنوان بريد.
    masked = _mask("EMAIL", _EMAIL_RE, text)
    masked = _mask("PHONE", _PHONE_RE, masked)
    masked = _mask("ID", _LONG_ID_RE, masked)
    return masked, mapping


def unmask_text(masked_text, mapping):
    """يعكس الإخفاء بدقة باستخدام الـmapping؛ رمز بلا أصل يُترك كما هو."""
    if not masked_text:
        return ""
    if not mapping:
        return masked_text

    def _restore(match):
        key = "%s:%s" % (match.group(1), match.group(2))
        return mapping.get(key, match.group(0))

    return _TOKEN_RE.sub(_restore, masked_text)


def mask_record(obj, mapping=None):
    """يطبّق الإخفاء تكراريًا على dict/list/str ويرجع نسخة جديدة.

    المفاتيح تُترك كما هي؛ القيم النصية فقط تُخفى. الأصل لا يُعدَّل.
    الأنواع الأخرى (أرقام، None، bool...) تُعاد كما هي.
    """
    if mapping is None:
        mapping = {}
    if isinstance(obj, str):
        masked, _ = mask_text(obj, mapping)
        return masked, mapping
    if isinstance(obj, dict):
        return (
            {key: mask_record(value, mapping)[0] for key, value in obj.items()},
            mapping,
        )
    if isinstance(obj, list):
        return (
            [mask_record(item, mapping)[0] for item in obj],
            mapping,
        )
    return obj, mapping


def redact_secrets(text):
    """حجب نهائي لا عكسي لقيم شبيهة بالأسرار — بلا mapping ولا استرجاع.

    يغطي `sk-...` و`ghp_...` وما يشبهها و`AKIA...` و`Bearer <قيمة>`
    وتعيينات `api_key=...` وما يشبهها. الأسرار لا تُخفى إخفاءً قابلًا
    للعكس أبدًا: من يُحجب هنا لا يعود.
    """
    if not text:
        return ""
    redacted = text
    for pattern in _SECRET_RES:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted
