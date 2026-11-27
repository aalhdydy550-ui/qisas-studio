#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""مراجعة المهارات المتعلمة + مكتبة مهارات — جولة v0.1.63 (بند 25).

مراجعة تلقائية بعد N خطوات أدوات (``skillReviewSteps`` 3–100
من ``lib.features`` عبر استيراد كسول) تحدّث مهارات متعلمة من
المحادثات الطويلة؛ ومشاركة عبر مكتبة ``skills/library/`` بأوضاع
``shareLearnedSkills`` (``off|ask|auto``)؛ ومهارات كل عامل
تُستبعد بملف إلغاء اشتراك لكل عامل (``library-opt-out.json``).

قاعدة ملف إلغاء الاشتراك (من التقرير §4.14): إن وُجد الملف ولم
يُقرأ أو لم يكن قائمة أسماء، يحتفظ العامل بكل شيء ويُسجَّل ذلك
مرة واحدة — فلا يُستبعد شيء بصمت.
"""
import json
import os
import re

# --- افتراضات عقد ع7 ---
DEFAULT_REVIEW_STEPS = 10
MIN_REVIEW_STEPS = 3
MAX_REVIEW_STEPS = 100
SHARE_MODES = ("off", "ask", "auto")
DEFAULT_SHARE_MODE = "off"
OPT_OUT_FILENAME = "library-opt-out.json"


def _features():
    """اقرأ مزايا الاستوديو باستيراد كسول؛ غياب الوحدة = لا مزايا."""
    try:
        from lib import features
        return features
    except Exception:
        return None


def review_enabled():
    """هل مراجعة المهارات مفعّلة؟ (راية ``skillReview``، الافتراضي مطفأة)."""
    features = _features()
    if features is None:
        return False
    try:
        return bool(features.get("skillReview", False))
    except Exception:
        return False


def validate_steps(value):
    """تحقق أن عدد الخطوات صحيح بين 3 و100؛ ارفع ValueError وإلا."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("skillReviewSteps يجب أن يكون عددًا صحيحًا: %r" % (value,))
    if value < MIN_REVIEW_STEPS or value > MAX_REVIEW_STEPS:
        raise ValueError(
            "skillReviewSteps %d خارج النطاق %d–%d"
            % (value, MIN_REVIEW_STEPS, MAX_REVIEW_STEPS)
        )
    return value


def review_steps():
    """الفاصل بين المراجعات التلقائية (3–100)؛ الافتراضي 10.

    قيمة غير صالحة في الإعداد تُعاد إلى الافتراضي بدل رمي خطأ
    في منتصف تشغيل.
    """
    features = _features()
    if features is None:
        return DEFAULT_REVIEW_STEPS
    try:
        value = features.get("skillReviewSteps", DEFAULT_REVIEW_STEPS)
    except Exception:
        return DEFAULT_REVIEW_STEPS
    try:
        return validate_steps(value)
    except ValueError:
        return DEFAULT_REVIEW_STEPS


def should_review(step_count):
    """هل حان وقت مراجعة بعد ``step_count`` خطوة أداة؟

    المراجعة بعد N خطوات تمامًا: عند مضاعفات N فقط، والمراجعة
    مطفأة تعني أبدًا.
    """
    if not review_enabled():
        return False
    if not isinstance(step_count, int) or step_count <= 0:
        return False
    return step_count % review_steps() == 0


def share_mode():
    """وضع مشاركة المهارات المتعلمة: ``off|ask|auto`` (الافتراضي off)."""
    features = _features()
    if features is None:
        return DEFAULT_SHARE_MODE
    try:
        mode = features.get("shareLearnedSkills", DEFAULT_SHARE_MODE)
    except Exception:
        return DEFAULT_SHARE_MODE
    if mode not in SHARE_MODES:
        return DEFAULT_SHARE_MODE
    return mode


def load_opt_out(path):
    """اقرأ ملف إلغاء اشتراك عامل؛ ارجع (مجموعة الأسماء، تحذير أو None).

    ملف غائب = لا استبعاد. ملف موجود لكنه غير مقروء أو ليس
    قائمة أسماء = يحتفظ العامل بكل شيء (مجموعة فارغة) مع
    تحذير يُسجَّل مرة واحدة.
    """
    if not os.path.exists(path):
        return set(), None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return set(), (
            "ملف إلغاء الاشتراك %s غير مقروء — يحتفظ العامل بكل شيء"
            % path
        )
    if not isinstance(data, list) or not all(
            isinstance(item, str) for item in data):
        return set(), (
            "ملف إلغاء الاشتراك %s ليس قائمة أسماء — يحتفظ العامل بكل شيء"
            % path
        )
    return set(data), None


def opted_out_skills(worker_dir):
    """أسماء المهارات المستبعدة لعامل من ملف إلغاء اشتراكه."""
    names, _warning = load_opt_out(
        os.path.join(worker_dir, OPT_OUT_FILENAME))
    return names


def _safe_skill_name(name):
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-").lower()
    if not cleaned:
        raise ValueError("اسم مهارة فارغ بعد التنظيف: %r" % name)
    return cleaned


def skill_filename(name):
    """اسم ملف مهارة في المكتبة: ``<name>/SKILL.md``."""
    return os.path.join(_safe_skill_name(name), "SKILL.md")


def list_library(library_dir):
    """أسماء المهارات الموجودة في المكتبة (مجلدات فيها SKILL.md)."""
    if not os.path.isdir(library_dir):
        return []
    names = []
    for name in sorted(os.listdir(library_dir)):
        path = os.path.join(library_dir, name, "SKILL.md")
        if os.path.isfile(path):
            names.append(name)
    return names


def write_skill(library_dir, name, body):
    """اكتب مهارة متعلمة في المكتبة (كتابة ذرية)؛ ارجع مسارها."""
    if not body or not body.strip():
        raise ValueError("جسم المهارة فارغ: %s" % name)
    path = os.path.join(library_dir, skill_filename(name))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.tmp-%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(body.rstrip() + "\n")
    os.replace(tmp, path)
    return path


def summarize_steps(steps):
    """لخّص خطوات أدوات: عدّاد استخدام كل أداة + الأكثر تكرارًا."""
    counts = {}
    for step in steps:
        tool = step.get("tool") if isinstance(step, dict) else None
        if tool:
            counts[tool] = counts.get(tool, 0) + 1
    repeated = sorted(
        ((tool, n) for tool, n in counts.items() if n >= 2),
        key=lambda item: (-item[1], item[0]),
    )
    return {"counts": counts, "repeated": repeated}


def review_after_steps(step_count, steps, library_dir, worker_dir=None,
                       mode=None):
    """راجع بعد ``step_count`` خطوة؛ ارجع قرار المراجعة.

    يرجع قاموسًا: ``due`` (هل حان وقتها)، و``candidates`` (أدوات
    متكررة تستحق مهارة)، و``shared`` (مهارات كُتبت في المكتبة)،
    و``pending`` (مهارات تنتظر سؤال المستخدم في وضع ask)،
    و``warning`` (تحذير ملف إلغاء اشتراك إن وجد).
    """
    result = {"due": False, "candidates": [], "shared": [],
              "pending": [], "warning": None}
    if not should_review(step_count):
        return result
    result["due"] = True
    summary = summarize_steps(steps)
    excluded = set()
    if worker_dir is not None:
        excluded, warning = load_opt_out(
            os.path.join(worker_dir, OPT_OUT_FILENAME))
        result["warning"] = warning
    candidates = [tool for tool, _n in summary["repeated"]
                  if tool not in excluded]
    result["candidates"] = candidates
    if mode is None:
        mode = share_mode()
    if mode == "off":
        return result
    for tool in candidates:
        body = ("# مهارة متعلمة: %s\n\nنمط متكرر ظهر %d مرات في %d خطوة أداة.\n"
                % (tool, summary["counts"][tool], step_count))
        if mode == "auto":
            path = write_skill(library_dir, tool, body)
            result["shared"].append(path)
        elif mode == "ask":
            result["pending"].append({"name": tool, "body": body})
    return result
