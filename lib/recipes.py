#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""وصفات خطوات متكررة — جولة v0.1.63 (بند 37).

حفظ خطوات مهمة تجميع متكررة (مثل خطوات تجميع إعلان الموقع)
وإعادتها بلا نموذج: أمر واحد بدل إعادة كتابة الأوامر كل مرة.

كل وصفة ملف `.md` واحد في `recipes/`: واجهة YAML أمامية
(الاسم والوصف والخطوات) + جسم مقروء يشرح كل خطوة. الخطوة
أمر بلا غلاف shell (قائمة وسائط) يُنفَّذ كما هو.

قاعدة أمنية: الوصفة لا تحمل أسرارًا أبدًا — أي قيمة بشكل
سرّ في اسم أو وصف أو أمر ترفض الحفظ كله وتُعَدّ في الخطأ.
"""
import os
import re
import subprocess

__all__ = [
    "RecipeError",
    "MAX_STEPS",
    "MAX_STEP_ARGS",
    "slugify",
    "save_recipe",
    "load_recipe",
    "list_recipes",
    "run_recipe",
    "remove_recipe",
]

MAX_STEPS = 50
MAX_STEP_ARGS = 32
MAX_NAME_LEN = 100

_SLUG_BAD_RE = re.compile(r"[^\w\-.]", re.UNICODE)


class RecipeError(Exception):
    """خطأ في وصفة (رسالته عربية)."""


def slugify(name):
    """اسم ملف آمن من اسم الوصفة: مسافات إلى شرطات، بلا محارف خطرة."""
    slug = str(name).strip().replace(" ", "-")
    slug = _SLUG_BAD_RE.sub("", slug)
    slug = slug.strip("-.")
    return slug or "recipe"


def _check_no_secrets(text, where):
    """يرفض أي قيمة بشكل سرّ — الاستيراد كسول من lib/round_pack.py."""
    from lib.round_pack import count_secrets

    count = count_secrets(text or "")
    if count:
        raise RecipeError(
            "الوصفة تحمل %d قيمة بشكل سرّ في %s — الوصفات لا تحمل أسرارًا أبدًا"
            % (count, where)
        )


def _validate_steps(steps):
    """يتحقق من بنية الخطوات ويعيد نسخة منظفة."""
    if not isinstance(steps, list) or not steps:
        raise RecipeError("الوصفة تحتاج خطوة واحدة على الأقل.")
    if len(steps) > MAX_STEPS:
        raise RecipeError(
            "عدد الخطوات %d يتجاوز الحد %d" % (len(steps), MAX_STEPS)
        )
    cleaned = []
    for index, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            raise RecipeError("الخطوة %d ليست قاموسًا." % index)
        name = str(step.get("name") or "").strip()
        if not name:
            raise RecipeError("الخطوة %d بلا اسم." % index)
        command = step.get("command")
        if not isinstance(command, list) or not command:
            raise RecipeError("الخطوة %d بلا أمر." % index)
        if len(command) > MAX_STEP_ARGS:
            raise RecipeError(
                "أمر الخطوة %d يتجاوز %d وسيطًا" % (index, MAX_STEP_ARGS)
            )
        args = [str(arg) for arg in command]
        if any(not arg for arg in args):
            raise RecipeError("الخطوة %d فيها وسيط فارغ." % index)
        _check_no_secrets(" ".join(args), "أمر الخطوة %d" % index)
        _check_no_secrets(name, "اسم الخطوة %d" % index)
        cleaned.append(
            {
                "name": name,
                "command": args,
                "note": str(step.get("note") or "").strip(),
            }
        )
    return cleaned


def _recipe_path(recipes_dir, slug):
    return os.path.join(os.path.abspath(recipes_dir), slug + ".md")


def _render(name, description, steps):
    """يصيغ ملف الوصفة: واجهة YAML + جسم مقروء."""
    import yaml

    meta = {
        "recipe": name,
        "description": description or "",
        "steps": [
            {
                "name": step["name"],
                "command": step["command"],
                **({"note": step["note"]} if step["note"] else {}),
            }
            for step in steps
        ],
    }
    lines = ["---", yaml.safe_dump(
        meta, allow_unicode=True, sort_keys=False,
        default_flow_style=False,
    ).rstrip(), "---", ""]
    lines.append("# وصفة: %s" % name)
    lines.append("")
    if description:
        lines.append(description)
        lines.append("")
    lines.append("## الخطوات")
    lines.append("")
    for index, step in enumerate(steps, 1):
        lines.append("%d. **%s**" % (index, step["name"]))
        lines.append("")
        lines.append("   `%s`" % " ".join(step["command"]))
        lines.append("")
        if step["note"]:
            lines.append("   %s" % step["note"])
            lines.append("")
    return "\n".join(lines) + "\n"


def save_recipe(recipes_dir, name, description, steps, *, overwrite=False):
    """يحفظ وصفة جديدة ويعيد مسار ملفها.

    يرفض الحفظ إن حملت الوصفة أي قيمة بشكل سرّ، ويرفض
    الكتابة فوق وصفة موجودة بلا `overwrite`.
    """
    name = str(name or "").strip()
    if not name:
        raise RecipeError("اسم الوصفة مطلوب.")
    if len(name) > MAX_NAME_LEN:
        raise RecipeError(
            "اسم الوصفة %d حرفًا يتجاوز الحد %d" % (len(name), MAX_NAME_LEN)
        )
    description = str(description or "").strip()
    _check_no_secrets(name, "اسم الوصفة")
    _check_no_secrets(description, "وصف الوصفة")
    cleaned_steps = _validate_steps(steps)
    slug = slugify(name)
    path = _recipe_path(recipes_dir, slug)
    if os.path.isfile(path) and not overwrite:
        raise RecipeError("وصفة موجودة بالاسم نفسه: %s" % slug)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_render(name, description, cleaned_steps))
    return path


def load_recipe(recipes_dir, name):
    """يحمّل وصفة بالاسم (أو بالـslug) ويعيد قاموسها."""
    import yaml

    slug = slugify(name)
    path = _recipe_path(recipes_dir, slug)
    if not os.path.isfile(path):
        raise RecipeError("لا توجد وصفة باسم: %s" % name)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if not text.startswith("---\n"):
        raise RecipeError("ملف الوصفة %s بلا واجهة YAML." % slug)
    end = text.find("\n---\n", 4)
    if end < 0:
        raise RecipeError("واجهة YAML في %s غير مغلقة." % slug)
    try:
        meta = yaml.safe_load(text[4:end]) or {}
    except Exception as exc:
        raise RecipeError("واجهة YAML غير صالحة في %s: %s" % (slug, exc))
    if not isinstance(meta, dict) or not meta.get("recipe"):
        raise RecipeError("ملف الوصفة %s بلا اسم." % slug)
    steps = _validate_steps(meta.get("steps") or [])
    return {
        "name": meta["recipe"],
        "slug": slug,
        "description": meta.get("description") or "",
        "steps": steps,
        "path": path,
    }


def list_recipes(recipes_dir):
    """يسرد الوصفات: قائمة `{name, slug, description, steps}`."""
    recipes_dir = os.path.abspath(recipes_dir)
    found = []
    if not os.path.isdir(recipes_dir):
        return found
    for filename in sorted(os.listdir(recipes_dir)):
        if not filename.endswith(".md"):
            continue
        slug = filename[:-3]
        try:
            recipe = load_recipe(recipes_dir, slug)
        except RecipeError:
            continue
        found.append(
            {
                "name": recipe["name"],
                "slug": recipe["slug"],
                "description": recipe["description"],
                "steps": len(recipe["steps"]),
            }
        )
    return found


def run_recipe(recipes_dir, name, *, workdir=None, dry_run=False, env=None):
    """ينفّذ خطوات وصفة بالترتيب بلا نموذج ويعيد تقريرًا.

    يتوقف عند أول خطوة تفشل. `dry_run=True` يسرد الخطوات
    المخططة بلا تنفيذ. الأوامر بلا غلاف shell أبدًا.
    """
    recipe = load_recipe(recipes_dir, name)
    report = {"recipe": recipe["name"], "ok": True, "steps": []}
    for step in recipe["steps"]:
        report["steps"].append(
            {
                "name": step["name"],
                "command": step["command"],
                "returncode": None,
                "stdout": "",
                "stderr": "",
            }
        )
    for step, record in zip(recipe["steps"], report["steps"]):
        if dry_run:
            continue
        try:
            proc = subprocess.run(
                step["command"],
                cwd=workdir,
                env=env,
                capture_output=True,
                text=True,
                timeout=600,
            )
        except FileNotFoundError:
            record["stderr"] = "الأمر غير موجود: %s" % step["command"][0]
            record["returncode"] = 127
            report["ok"] = False
            report["failed_step"] = step["name"]
            break
        except subprocess.TimeoutExpired:
            record["stderr"] = "مهلة الخطوة انتهت (600 ثانية)."
            record["returncode"] = 124
            report["ok"] = False
            report["failed_step"] = step["name"]
            break
        record["returncode"] = proc.returncode
        record["stdout"] = proc.stdout or ""
        record["stderr"] = proc.stderr or ""
        if proc.returncode != 0:
            report["ok"] = False
            report["failed_step"] = step["name"]
            break
    return report


def remove_recipe(recipes_dir, name):
    """يحذف وصفة بالاسم؛ يعيد True إن وُجدت وحُذفت."""
    path = _recipe_path(recipes_dir, slugify(name))
    if not os.path.isfile(path):
        return False
    os.unlink(path)
    return True
