#!/usr/bin/env python3
"""خطة مشاهد Veo + الموافقة المسبقة — الجولة 7 (v0.1.31).

قبل إنفاق أي رصيد Veo، تُبنى خطة مشاهد مكتوبة (الموجهات + المدة +
الوحدات المتوقعة) وتُطبع وتُحفظ، ويُفحص الإنفاق المتوقع مقابل
سقف الإنفاق (`veo.cap_units` من `balance --cap`) والرصيد المسجَّل:

- `build_scene_plan(cfg, story, clips=6)`: يقرأ نص القصة من ملف
  الطابور (إشارة «النص: queue/<file>.txt») إن وُجد، ويقسّم أول
  جمله إلى `clips` مشهدًا؛ كل مشهد 8 ثوانٍ × 20 وحدة (تكلفة مقطع
  Veo 3.1 Fast كما في عائشة ج2: 6 مقاطع × 20 = 120 وحدة).
  بلا نص: موجِّهات مسودة من العنوان مع تنبيه صريح أنها تحتاج
  صياغة قبل Flow. تجاوز السقف أو الرصيد يرفع CapError برسالة
  عربية — بلا أي إنفاق.
- `save_plan(plan, runs_dir)`: يحفظ الخطة JSON في
  `runs/scene-plan-<slug>-<وقت>.json`.
- `request_approval(plan, auto_approve=False)`: التشغيل التفاعلي
  يتوقف ويسأل «نعم»؛ و`--auto-approve` أو التشغيل غير التفاعلي
  (كرون — stdin ليس tty) يمضي داخل السقف ويسجّل الموافقة بلا توقف.
"""
import json
import os
import re
import sys
import time

from lib import balance as balance_lib

VEO_UNITS_PER_CLIP = 20
VEO_CLIP_SECONDS = 8
DEFAULT_CLIPS = 6
MAX_CLIPS = 12
MIN_CLIPS = 1


class CapError(Exception):
    """رفض توليد Veo — تجاوز السقف أو الرصيد (رسالته عربية)."""


def _slug(title):
    """slug عربي آمن لاسم الملف: حروف وأرقام وشرطات فقط."""
    text = re.sub(r"\s+", "-", (title or "").strip())
    text = re.sub(r"[^0-9A-Za-z\u0600-\u06FF\-_]+", "", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "qissa"


def _split_sentences(text):
    """قسّم نصًا إلى جمل على حدود (./!/؟/أسطر) — بلا جمل فارغة."""
    parts = re.split(r"[.!؟\n]+", text or "")
    return [p.strip() for p in parts if p.strip()]


def _studio_dir(studio_dir=None):
    """مجلد studio (أب مجلد lib/) — أو الممرَّر صراحةً
    (للاختبار)."""
    if studio_dir:
        return os.path.abspath(os.path.expanduser(studio_dir))
    return os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))


def story_text_path(cfg, story, studio_dir=None):
    """مسار ملف نص القصة من ملاحظة الطابور («النص: queue/<file>.txt»)،
    أو None إن لم تُذكر الإشارة أو لم يوجد الملف. الحصر داخل
    مساحة العمل (lib.paths) — إشارة خارجية تُرفض بلا قراءة.

    إصلاح: كان المسار النسبي «queue/...» يُحلّ مقابل مجلد
    العمل الحالي (CWD) — فمن أي مجلد غير studio كان الملف
    لا يُوجد أبدًا ويسقط الكود بصمت إلى موجِّهات مسودة؛
    والآن يُثبَّت على مجلد studio (حيث يحفظ `queue add` نصوص
    القصص في studio/queue/) مهما كان CWD.
    """
    note = (story or {}).get("note") or ""
    m = re.search(r"النص:\s*queue/([^\s)]+)", note)
    if not m:
        return None
    rel = "queue/" + m.group(1)
    candidate = os.path.join(_studio_dir(studio_dir), rel)
    try:
        from lib.paths import resolve_inside_workspace
        path = resolve_inside_workspace(candidate, "ملف نص القصة")
    except ValueError:
        return None
    return path if os.path.isfile(path) else None


def build_scene_plan(cfg, story, clips=DEFAULT_CLIPS):
    """ابنِ خطة مشاهد Veo لقصة من الطابور. يرجع قاموس الخطة.

    يرفع CapError إن تجاوز الإنفاق المتوقع السقف أو الرصيد،
    وValueError إن كان عدد المقاطع خارج 1–12.
    """
    if isinstance(clips, bool) or not isinstance(clips, int) \
            or clips < MIN_CLIPS or clips > MAX_CLIPS:
        raise ValueError("عدد المقاطع يجب أن يكون بين %d و%d (وصل: %s)"
                         % (MIN_CLIPS, MAX_CLIPS, clips))
    title = (story or {}).get("title") or ""
    if not title.strip():
        raise ValueError("عنوان القصة فارغ — لا يمكن بناء خطة مشاهد")
    slug = _slug(title)
    text = ""
    text_path = story_text_path(cfg, story)
    if text_path:
        with open(text_path, encoding="utf-8") as f:
            text = f.read()
    sentences = _split_sentences(text)
    scenes = []
    draft = False
    for i in range(clips):
        if i < len(sentences):
            prompt = sentences[i]
        else:
            # نص أقصر من عدد المقاطع (أو غائب): موجِّه مسودة من
            # العنوان — مع تنبيه صريح في الخطة أنها تحتاج صياغة.
            prompt = ("مشهد %d من قصة «%s»" % (i + 1, title.strip()))
            draft = True
        if len(prompt) > 200:
            prompt = prompt[:200].rstrip() + "…"
        scenes.append({"scene": i + 1,
                       "prompt": prompt,
                       "duration_seconds": VEO_CLIP_SECONDS,
                       "units": VEO_UNITS_PER_CLIP})
    total_units = clips * VEO_UNITS_PER_CLIP
    veo_cfg = (cfg.get("veo") or {}) if isinstance(cfg, dict) else {}
    ok, reason = balance_lib.check_cap(total_units, veo_cfg)
    if not ok:
        raise CapError(reason)
    return {
        "story_number": (story or {}).get("number"),
        "story_title": title.strip(),
        "slug": slug,
        "clips": clips,
        "clip_seconds": VEO_CLIP_SECONDS,
        "units_per_clip": VEO_UNITS_PER_CLIP,
        "total_units": total_units,
        "balance_units": veo_cfg.get("balance_units"),
        "cap_units": veo_cfg.get("cap_units"),
        "draft_prompts": draft,
        "text_source": text_path,
        "scenes": scenes,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def save_plan(plan, runs_dir):
    """احفظ الخطة JSON في runs/. يرجع مسار الملف."""
    os.makedirs(runs_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(
        runs_dir, "scene-plan-%s-%s.json" % (plan["slug"], ts))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    return path


def format_plan(plan):
    """نص عربي للخطة (للطباعة قبل الموافقة)."""
    lines = ["== خطة مشاهد Veo — %s ==" % plan["story_title"],
             "المقاطع: %d × %d ثوانٍ — الوحدات: %d × %d = %d وحدة"
             % (plan["clips"], plan["clip_seconds"],
                plan["clips"], plan["units_per_clip"],
                plan["total_units"]),
             "الرصيد المسجَّل: %s — السقف: %s"
             % (plan["balance_units"] if plan["balance_units"] is not None
                else "غير مسجَّل",
                ("%d وحدة" % plan["cap_units"])
                if plan["cap_units"] is not None else "بلا سقف"),
             ""]
    for s in plan["scenes"]:
        lines.append("  المشهد %d (%d ثوانٍ، %d وحدة): %s"
                     % (s["scene"], s["duration_seconds"], s["units"],
                        s["prompt"]))
    lines.append("")
    if plan["draft_prompts"]:
        lines.append("تنبيه: بعض الموجهات مسودة من العنوان فقط — "
                     "صِغها في Flow قبل التوليد.")
    lines.append("لا يُنفَق أي رصيد قبل موافقتك على هذه الخطة.")
    return "\n".join(lines) + "\n"


def request_approval(plan, auto_approve=False, input_fn=None,
                     is_tty=None):
    """اطلب الموافقة على إنفاق وحدات الخطة.

    يرجع True عند الموافقة. `--auto-approve` أو التشغيل غير
    التفاعلي (كرون) يمضي بلا توقف؛ والتفاعلي يسأل «نعم».
    input_fn/is_tty للحقن في الاختبارات.
    """
    total = plan["total_units"]
    if auto_approve:
        print("موافقة تلقائية (--auto-approve) على إنفاق %d وحدة — "
              "الخطة محفوظة." % total)
        return True
    tty = sys.stdin.isatty() if is_tty is None else is_tty
    if not tty:
        print("تشغيل غير تفاعلي (كرون) — يمضي داخل السقف (%d وحدة) "
              "والخطة مسجَّلة." % total)
        return True
    ask = input_fn or input
    answer = ask("توافق على إنفاق %d وحدة Veo على هذه الخطة؟ "
                 "اكتب «نعم» للموافقة: " % total).strip().lower()
    if answer in ("نعم", "yes", "y"):
        print("تمت الموافقة — الخطة محفوظة.")
        return True
    print("أُلغي التوليد قبل إنفاق أي رصيد.")
    return False
