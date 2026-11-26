#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""لوحة تقييم الهوك — قائمة فحص yt-script (الجولة v0.1.57، W3).

أول 15 ثانية هي كل العمل: الهوك يؤكد النقرة، ويفتح سؤالًا لا
يُغلق، ويثبت وجود العائد. القاعدة من yt-script: اكتب خمسة
هوكات، وقيّمها، وأبقِ أفضل اثنين بالدرجات — لا يُسلَّم هوك
واحد أبدًا.

لا مسجّل جديد هنا: التقييم كله من مسجّل الاستوديو القائم
`lib.dna.score_hook` (0–10 بالتفصيل)، والتطبيع من
`lib.dna.normalize_hook` (رقم بداية الهوك كلمات — قاعدة
صيغة الاستوديو: الهوك لا يبدأ برقم). هذه الوحدة تغلّف
الدالتين كأمر فقط: تطبّع كل هوك، وتقيّمه، وترتّب، وتميّز
أفضل اثنين، وتطبع لوحة عربية.

التقييم إرشادي (heuristic) لا تنبؤ — درجة منخفضة سبب
لإعادة النظر، ودرجة عالية ليست وعدًا بالمشاهدات. كل تقرير
يطبعه `format_panel` ينتهي بهذا التحذير صراحةً.
"""
from lib.dna import DnaError, normalize_hook, score_hook

# التحذير الصريح — يختم كل تقرير لوحة (سطر أخير حرفيًا).
WARNING = ("تقييم إرشادي (heuristic) وليس تنبؤًا بالمشاهدات — "
           "درجة منخفضة سبب لإعادة النظر، ودرجة عالية ليست وعدًا")

# تسميات تفصيل الدرجة بالعربية (نفس ترتيب score_hook).
_BREAKDOWN_LABELS = (
    ("curiosity_gap", "فجوة فضول (0–3)"),
    ("specific_fact", "حقيقة محددة (0–2)"),
    ("conflict", "صراع/رأي قوي (0–2)"),
    ("direct_entry", "دخول مباشر (0–1)"),
    ("payoff", "عائد داخل المقطع (0–1)"),
    ("self_contained", "قائم بذاته (0–1)"),
)


def score_hooks(hooks, story_text=None):
    """قيّم قائمة هوكات ورتّبها تنازليًا، وميّز أفضل اثنين.

    كل هوك يُطبَّع أولًا بـ `normalize_hook` ثم يُقيَّم بـ
    `score_hook` (مع `story_text` إن وُجد، وإلا يبقى معيار
    العائد «غير مقاس» والحد الأقصى 9).

    يرجع قائمة لوحات، كل لوحة قاموس بمفاتيح: `hook` (النص
    المطبَّع)، و`total` (المجموع)، و`max` (الحد الأقصى)،
    و`breakdown` (التفصيل)، و`verdict` (الحكم)، و`rank`
    (الترتيب 1..N)، و`top_two` (True لأفضل اثنين فقط).

    مدخل فارغ أو قائمة فارغة → DnaError برسالة عربية.
    هوك فارغ داخل القائمة → DnaError من score_hook نفسه.
    """
    if hooks is None:
        raise DnaError("قائمة الهوكات فارغة — مرّر خمسة هوكات")
    if isinstance(hooks, str):
        raise DnaError("مرّر قائمة هوكات لا هوكًا واحدًا")
    hooks = list(hooks)
    if not hooks:
        raise DnaError("قائمة الهوكات فارغة — مرّر خمسة هوكات")
    panels = []
    for hook in hooks:
        normalized = normalize_hook(hook)
        scored = score_hook(normalized, story_text=story_text)
        panels.append({
            "hook": scored["hook"],
            "total": scored["total"],
            "max": scored["max"],
            "breakdown": scored["breakdown"],
            "verdict": scored["verdict"],
        })
    # ترتيب تنازلي بالمجموع؛ والترتيب المستقر يحفظ ترتيب
    # الإدخال عند التساوي (حتمي بلا عشوائية).
    panels.sort(key=lambda p: p["total"], reverse=True)
    for i, panel in enumerate(panels):
        panel["rank"] = i + 1
        panel["top_two"] = i < 2
    return panels


def format_panel(result):
    """نص عربي يعرض لوحة كل هوك، وينتهي بسطر التحذير.

    `result`: قائمة لوحات من `score_hooks` (أو لوحة واحدة
    تُغلَّف في قائمة). قائمة فارغة → DnaError برسالة عربية.
    """
    if isinstance(result, dict):
        result = [result]
    if not result:
        raise DnaError("لا لوحات لعرضها — قيّم الهوكات أولًا")
    lines = ["== لوحة تقييم الهوك ==",
             "أول 15 ثانية هي كل العمل: تؤكد النقرة، وتفتح سؤالًا "
             "لا يُغلق، وتثبت وجود العائد.",
             ""]
    for panel in result:
        mark = " — من أفضل اثنين" if panel.get("top_two") else ""
        lines.append("الهوك %d%s: «%s»"
                     % (panel.get("rank", "?"), mark, panel["hook"]))
        lines.append("  الدرجة: %d/%d — %s"
                     % (panel["total"], panel["max"], panel["verdict"]))
        breakdown = panel.get("breakdown") or {}
        for key, label in _BREAKDOWN_LABELS:
            value = breakdown.get(key)
            lines.append("  %s: %s" % (
                label,
                "غير مقاس (يحتاج نص القصة)" if value is None else value))
        lines.append("")
    lines.append(WARNING)
    return "\n".join(lines) + "\n"
