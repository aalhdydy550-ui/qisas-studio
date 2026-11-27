#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختيار الأدوات بقائمتي Allow/Exclude — جولة v0.1.63، بند 15 (ع6).

لكل دور عامل قائمتا أدوات:

- ``allow`` — فقط الأدوات المذكورة (وقائمة فارغة تعني: لا أدوات).
- ``deny`` — كل شيء إلا المذكورة؛ وExclude يفوز دائمًا على Allow.

المحددات بأسمائها الأصلية الحساسة لحالة الأحرف، قبل أي اسم
مستعار، على الصيغتين فقط:

- محدد دقيق: ``native:read`` أو ``mcp:mail:read_notes``.
- بدل كامل المقطع: ``native:*`` أو ``mcp:mail:*`` فقط.

البدل الجزئي مثل ``native:read*`` باطل. واسم صحيح غير متاح
يختار لا شيء — لا عودة أبدًا إلى كل الأدوات. والحدود:
≤256 محددًا لكل قائمة، و≤1024 حرفًا لكل محدد.

حفظ فاشل لا يمنح أدوات أبدًا: هذه الوحدة لا تحفظ شيئًا بنفسها،
ودوالها خالصة؛ فأي مسار حفظ يفشل قبل استدعائها لا يصل إليها
اختيار جديد، والاختيار القديم يبقى ساريًا.

الوحدة مستقلة تمامًا: مكتبة قياسية فقط، ولا تستورد أي وحدة
``lib`` أخرى ولا ``studio``.
"""

import re

__all__ = [
    "MAX_SELECTORS",
    "MAX_SELECTOR_LENGTH",
    "ToolSelectionError",
    "is_valid_selector",
    "validate_selectors",
    "matches_selector",
    "allowed",
    "select_tools",
]

# سقوف القوائم (ع6).
MAX_SELECTORS = 256
MAX_SELECTOR_LENGTH = 1024

# محدد دقيق: مقطع أو أكثر مفصولة بنقطتين، بلا بدل إطلاقًا.
_EXACT_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*(:[A-Za-z0-9_][A-Za-z0-9_.-]*)*$")
# بدل كامل المقطع: مقطع أو أكثر ثم ``:*`` في النهاية فقط.
_WILDCARD_RE = re.compile(
    r"^[A-Za-z0-9_][A-Za-z0-9_.-]*(:[A-Za-z0-9_][A-Za-z0-9_.-]*)*:\*$"
)


class ToolSelectionError(Exception):
    """خطأ في قوائم اختيار الأدوات (رسالته عربية)."""


def is_valid_selector(selector):
    """هل المحدد صحيح؟ دقيق أو بدل مقطع كامل فقط — بلا بدل جزئي."""
    if not isinstance(selector, str):
        return False
    if not selector or len(selector) > MAX_SELECTOR_LENGTH:
        return False
    if "*" in selector:
        return bool(_WILDCARD_RE.match(selector))
    return bool(_EXACT_RE.match(selector))


def validate_selectors(selectors, label="القائمة"):
    """تحقق من قائمة محددات وارجع نسخة منها.

    يرفع ``ToolSelectionError`` عند: قائمة ليست قائمة، أو عنصر
    ليس نصًا، أو محدد باطل (ومنها البدل الجزئي)، أو تجاوز
    سقف 256 محددًا، أو محدد أطول من 1024 حرفًا.
    """
    if selectors is None:
        return []
    if not isinstance(selectors, (list, tuple)):
        raise ToolSelectionError(
            "قائمة الأدوات «%s» يجب أن تكون قائمة محددات، لا %s."
            % (label, type(selectors).__name__)
        )
    if len(selectors) > MAX_SELECTORS:
        raise ToolSelectionError(
            "قائمة الأدوات «%s» فيها %d محددًا، والحد الأقصى %d."
            % (label, len(selectors), MAX_SELECTORS)
        )
    cleaned = []
    for selector in selectors:
        if not isinstance(selector, str):
            raise ToolSelectionError(
                "محدد الأدوات في «%s» يجب أن يكون نصًا، لا %s."
                % (label, type(selector).__name__)
            )
        if len(selector) > MAX_SELECTOR_LENGTH:
            raise ToolSelectionError(
                "محدد الأدوات «%s…» في «%s» أطول من %d حرفًا."
                % (selector[:40], label, MAX_SELECTOR_LENGTH)
            )
        if not is_valid_selector(selector):
            raise ToolSelectionError(
                "محدد الأدوات «%s» في «%s» باطل: المسموح محدد دقيق "
                "مثل native:read أو بدل مقطع كامل مثل native:* فقط — "
                "والبدل الجزئي مثل native:read* مرفوض."
                % (selector, label)
            )
        cleaned.append(selector)
    return cleaned


def matches_selector(selector, tool):
    """هل يطابق المحدد الصحيح اسم الأداة؟

    المحدد الدقيق يطابق الاسم نفسه فقط؛ وبدل المقطع الكامل
    ``native:*`` يطابق كل أداة يبدأ اسمها بـ ``native:``.
    محدد باطل لا يطابق شيئًا أبدًا (ولا يرمي).
    """
    if not isinstance(tool, str) or not tool:
        return False
    if not is_valid_selector(selector):
        return False
    if selector.endswith(":*"):
        prefix = selector[:-1]  # يبقي النقطتين: «native:»
        return tool.startswith(prefix)
    return tool == selector


def allowed(tool, allow, deny, available=None):
    """هل الأداة مسموحة؟ (ع6)

    - اسم غير متاح (حين تُمرَّر ``available``) يختار لا شيء.
    - Exclude يفوز دائمًا: أي تطابق في ``deny`` يرفض.
    - Allow فارغة تعني: لا أدوات.
    - غير ذلك: الأداة مسموحة فقط إن طابقها محدد في ``allow``.

    محدد باطل في أي قائمة يرفع ``ToolSelectionError`` — فالاختيار
    المشوّه يوقف الدور بخطأ إعداد بدل أن يمنح أدوات ضمنيًا.
    """
    allow = validate_selectors(allow, "allow")
    deny = validate_selectors(deny, "deny")
    if available is not None and tool not in available:
        return False
    if any(matches_selector(selector, tool) for selector in deny):
        return False
    if not allow:
        return False
    return any(matches_selector(selector, tool) for selector in allow)


def select_tools(allow, deny, available):
    """ارجع الأدوات المتاحة المسموحة، مرتبة، بلا تكرار.

    اسم صحيح غير متاح لا يظهر هنا أبدًا — لا عودة إلى كل
    الأدوات. وقائمة ``allow`` فارغة ترجع قائمة فارغة.
    """
    allow = validate_selectors(allow, "allow")
    deny = validate_selectors(deny, "deny")
    if available is None:
        return []
    chosen = [
        tool
        for tool in sorted(set(available))
        if allowed(tool, allow, deny, available=available)
    ]
    return chosen
