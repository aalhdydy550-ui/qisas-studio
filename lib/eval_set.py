#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""مجموعة التقييم الثابتة — جولة v0.1.37 (مقترح tinker رقم 5).

`lib/eval_set.json` (بذرة 20261122): خمسة فيديوهات منشورة/
جاهزة بأرقام DNA ومشاهدات حقيقية قيسَت في 2026-11-22.
الترتيب ثابت (بالبذرة) حتى تبقى المقارنات قابلة للتكرار.
`null` تعني «غير مقاس/غير متاح» لا صفرًا.
"""
import json
import os

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "eval_set.json")


def load_eval_set(path=None):
    """اقرأ مجموعة التقييم؛ ارجع القاموس الكامل."""
    path = path or DEFAULT_PATH
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def eval_videos(eval_set=None):
    """فيديوهات المجموعة بالترتيب الثابت (قائمة قواميس)."""
    data = eval_set or load_eval_set()
    return list(data.get("videos") or [])


def compare_measurement(baseline, measured):
    """قارن قياسًا جديدًا بالأساس؛ ارجع قائمة فروقات.

    baseline/measured: قاموسا فيديو واحد (نفس الحقول).
    كل فرق: {metric, baseline, measured, delta, changed}.
    الحقول null في الأساس أو القياس تُتخطى (غير مقاسة).
    """
    diffs = []
    for metric in ("hook_score", "duration_seconds", "shot_count",
                   "avg_shot_seconds", "wpm"):
        base = baseline.get(metric)
        new = measured.get(metric)
        if base is None or new is None:
            continue
        delta = round(new - base, 2)
        diffs.append({"metric": metric, "baseline": base,
                      "measured": new, "delta": delta,
                      "changed": delta != 0})
    for metric in ("silence_ok",):
        base = baseline.get(metric)
        new = measured.get(metric)
        if base is None or new is None:
            continue
        diffs.append({"metric": metric, "baseline": base,
                      "measured": new, "delta": None,
                      "changed": base != new})
    return diffs
