#!/usr/bin/env python3
"""دفعات جماعية — `studio.py batch` (الجولة 7، v0.1.31).

ينتج القصص التالية من الطابور في تشغيل واحد: لكل قصة جاهزة
(إنتاج + فحص `check` + مصغرة + تسجيل في run-log).

- الوضع التجريبي افتراضي: يطبع الخطة بلا أي تنفيذ وبلا كتابة
  أي ملف. التنفيذ الحقيقي فقط مع `--execute` (نمط `daily`).
- `--source veo|openmontage`: مسار Veo يفحص الرصيد ≥120 أولًا
  ويخضع لسقف الإنفاق (`balance.check_cap` — 120 وحدة متوقعة
  للفيديو: 6 مقاطع × 20)؛ وإن نقص الرصيد يُرفض مسار Veo
  برسالة عربية (البديل الصريح `--source openmontage`).
- إنتاج Veo نفسه في Google Flow يدويًا خارج studio — فقصة Veo
  بلا فيديو جاهز (`<slug>-batch.mp4` في videos_dir) تُسجَّل
  `needs-flow` وتُتخطى، بلا ادعاء إنتاج.
- لا نشر في batch (الإنتاج فقط)؛ والنتائج في
  `runs/batch-<تاريخ>.json` فقط — بلا إلحاق بخلاصة الطابور.
- الجاهزية عبر `ready_fn` محقونة (نفس `check_story_ready` في
  studio.py) — قابلة للاختبار بلا مشاريع حقيقية.
- الجولة v0.1.39: كاش ريندر (lib/render_cache) يتخطى إعادة
  ريندر المهمة غير المتغيرة، وسجل مهام دائم (lib/job_registry)
  يسجّل كل قصة في runs/jobs.jsonl.
- الجولة v0.1.39 (أ2-2/أ2-3): دفعات JSON كمدخل لـ `batch`
  (`load_json_batch` / `plan_batch_from_json`) ووضع `--no-spend`
  (`validate_batch` / `format_no_spend_report`) — فحص جاف كامل
  بلا أي إنتاج وبلا خصم رصيد وبلا شبكة.
"""
import json
import os
import time

from lib import ab as ab_lib
from lib import balance as balance_lib
from lib import errors as errors_lib
from lib import queue as queue_lib
from lib import render_cache as render_cache_lib
from lib import job_registry as job_registry_lib
from lib import scene_plan as scene_plan_lib

VEO_MIN_BALANCE = 120
VEO_UNITS_PER_VIDEO = 120
# دفعات JSON: عدد مقاطع Veo الافتراضي لكل جزء من القصة
# (6 مقاطع × 8 ثوانٍ = فيديو ~48 ثانية).
DEFAULT_CLIPS_PER_PART = 6
MIN_CLIPS_PER_PART = 1
MAX_CLIPS_PER_PART = 12
MIN_PARTS = 1
MAX_PARTS = 2


class BatchError(Exception):
    """خطأ في الدفعة (رسالته عربية)."""


def plan_batch(cfg, count, source="openmontage", ready_fn=None,
               queue_file=None):
    """خطط لدفعة بلا أي تنفيذ. يرجع قاموس الخطة.

    يرفع BatchError عند: عدد غير صالح، مصدر غير معروف، ملف
    طابور غائب، لا قصص انتظار، أو رصيد Veo أقل من 120 (مع
    --source veo)، أو تجاوز الإنفاق المتوقع السقف.
    """
    if isinstance(count, bool) or not isinstance(count, int) \
            or count < 1:
        raise BatchError("عدد القصص يجب أن يكون 1 أو أكثر (وصل: %s)"
                         % (count,))
    if source not in ("veo", "openmontage"):
        raise BatchError("المصدر غير صالح: %s (المسموح: veo/openmontage)"
                         % source)
    queue_path = os.path.expanduser(
        queue_file or (cfg.get("paths") or {}).get("queue_file") or "")
    if not os.path.isfile(queue_path):
        raise BatchError("ملف الطابور غير موجود: %s" % queue_path)
    with open(queue_path, encoding="utf-8") as f:
        text = f.read()
    entries = queue_lib.parse_waiting_entries(text)
    if not entries:
        raise BatchError("لا توجد قصص في الانتظار في ملف الطابور")
    entries = entries[:count]
    veo_cfg = (cfg.get("veo") or {}) if isinstance(cfg, dict) else {}
    if source == "veo":
        balance = veo_cfg.get("balance_units")
        if balance is None:
            raise BatchError(
                "رصيد Veo غير مسجَّل — حدّث veo.balance_units في "
                "config.yaml أو استخدم --source openmontage")
        try:
            balance = balance_lib._as_int(balance, "الرصيد")
        except ValueError:
            raise BatchError("رصيد Veo غير صالح: %s" % (balance,))
        if balance < VEO_MIN_BALANCE:
            raise BatchError(
                "رصيد Veo %d وحدة (أقل من %d) — مسار Veo مرفوض؛ "
                "استخدم --source openmontage" % (balance, VEO_MIN_BALANCE))
        ok, reason = balance_lib.check_cap(VEO_UNITS_PER_VIDEO, veo_cfg)
        if not ok:
            raise BatchError(reason)
    videos_dir = os.path.expanduser(
        (cfg.get("paths") or {}).get("videos_dir") or "~/workspace/videos")
    stories = []
    for entry in entries:
        ready, slug, project, reason = ((True, None, None, "")
                                         if ready_fn is None
                                         else ready_fn(entry))
        video = None
        video_ready = False
        if slug:
            video = os.path.join(videos_dir, "%s-batch.mp4" % slug)
            video_ready = os.path.isfile(video)
        item = {"number": entry["number"], "title": entry["title"],
                "note": entry.get("note") or "",
                "ready": bool(ready), "slug": slug, "project": project,
                "reason": reason,
                "video": video, "video_ready": video_ready,
                "scene_plan": None}
        if source == "veo" and ready:
            try:
                item["scene_plan"] = scene_plan_lib.build_scene_plan(
                    cfg, entry)
            except scene_plan_lib.CapError as e:
                item["ready"] = False
                item["reason"] = str(e)
                item["scene_plan"] = None
        stories.append(item)
    total_expected = (VEO_UNITS_PER_VIDEO
                      * len([s for s in stories if s["ready"]])
                      if source == "veo" else 0)
    if source == "veo":
        # فحص الرصيد مقابل إجمالي الدفعة لا فيديو واحد: كان
        # الفحص المسبق يقبل أي دفعة برصيد ≥120 ولو كان الإجمالي
        # (مثلًا 3 قصص = 360 وحدة) فوق الرصيد — فتُخطط دفعة
        # لا يمكن توليدها. السقف يبقى لكل فيديو (الفحص المسبق
        # أعلاه)؛ أما الرصيد فيُقاس على الإجمالي.
        balance = veo_cfg.get("balance_units")
        if balance is not None:
            try:
                balance = balance_lib._as_int(balance, "الرصيد")
            except ValueError:
                raise BatchError("رصيد Veo غير صالح: %s" % (balance,))
            if total_expected > balance:
                raise BatchError(
                    "الإنفاق المتوقع للدفعة (%d وحدة لـ%d قصص جاهزة) "
                    "يتجاوز الرصيد المسجَّل (%d وحدة) — قلّل العدد "
                    "بـ --count أو استخدم --source openmontage"
                    % (total_expected,
                       len([s for s in stories if s["ready"]]),
                       balance))
    return {
        "count": len(stories),
        "source": source,
        "balance_units": veo_cfg.get("balance_units"),
        "cap_units": veo_cfg.get("cap_units"),
        "expected_units_per_video": (VEO_UNITS_PER_VIDEO
                                     if source == "veo" else 0),
        "total_expected_units": total_expected,
        "stories": stories,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


# ------------------------------------------------------- دفعات JSON (أ2-2)
# مخطط ملف دفعة JSON (مثال كامل في docstring دالة load_json_batch):
#
#   {
#     "name": "دفعة الصباح",            // اختياري: اسم الدفعة
#     "source": "veo",                  // اختياري: veo/openmontage
#     "default_engine": "lite",         // اختياري: fast/lite لكل المهام
#     "tasks": [
#       {"title": "العنزة المباركة", "parts": 2, "engine": "lite",
#        "clips": 6, "note": "تحتاج جزأين"},
#       {"title": "عجائب الصدقة", "parts": 1}
#     ]
#   }
#
# أو قائمة مهام عارية [...] بلا غلاف (تُعامل كمصدر openmontage).
# حقول المهمة: title (مطلوب — أو story كمرادف)، parts (اختياري،
# 1–2، الافتراضي 1)، engine (اختياري fast/lite — الافتراضي
# default_engine ثم fast)، clips (اختياري، مقاطع Veo لكل جزء،
# 1–12، الافتراضي 6)، note/notes (اختياري)، slug (اختياري)،
# number (اختياري، رقم في الطابور). أي حقل آخر مرفوض.
# التكلفة: كل جزء = clips مقاطع؛ فمهمة جزأين × 6 مقاطع = 12
# مقطعًا (240 وحدة Fast / 120 وحدة Lite). التحقق صارم: أي
# ملف معطوب يُرفض كاملًا برسالة عربية (BatchError) قبل أي
# إنتاج — لا إنتاج جزئي لملف معطوب. بلا أي تكامل خارجي: الصيغة
# JSON فقط، وخط النشر الخاص بالمستخدم (لا طلبات عملاء).

_JSON_TOP_KEYS = ("tasks", "source", "default_engine", "name")
_JSON_TASK_KEYS = ("title", "story", "parts", "engine", "clips",
                   "note", "notes", "slug", "number")


def _json_int(value, field, minimum, maximum):
    """عدد صحيح ضمن مدى لحقل JSON — يرفع BatchError عربيًا."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise BatchError(
            "حقل «%s» في مهمة الدفعة يجب أن يكون عددًا صحيحًا "
            "(وصل: %s)" % (field, value))
    if value < minimum or value > maximum:
        raise BatchError(
            "حقل «%s» في مهمة الدفعة يجب أن يكون بين %d و%d "
            "(وصل: %d)" % (field, minimum, maximum, value))
    return value


def parse_json_batch(data):
    """تحقق صارم من بيانات دفعة JSON محمّلة وطبّعها.

    data: قاموس فيه "tasks" أو قائمة مهام عارية. يرجع قاموسًا
    فيه name/source/default_engine/tasks (كل مهمة مطبّعة:
    title/parts/engine/clips/note/slug/number). يرفع BatchError
    برسالة عربية عند أي عطب: بنية غير قاموس/قائمة، قائمة مهام
    فارغة، حقل مجهول، عنوان مفقود/فارغ، أجزاء/مقاطع خارج المدى،
    محرك/مصدر غير صالح، أو عناوين مكررة. لا إنتاج جزئي أبدًا:
    أول خطأ يرفض الملف كاملًا.
    """
    if isinstance(data, list):
        data = {"tasks": data}
    if not isinstance(data, dict):
        raise BatchError(
            "ملف الدفعة يجب أن يكون قاموسًا فيه «tasks» أو قائمة "
            "مهام (وصل: %s)" % type(data).__name__)
    for key in data:
        if key not in _JSON_TOP_KEYS:
            raise BatchError(
                "حقل غير معروف في ملف الدفعة: «%s» (المسموح: %s)"
                % (key, "/".join(_JSON_TOP_KEYS)))
    source = data.get("source", "openmontage")
    if source not in ("veo", "openmontage"):
        raise BatchError(
            "المصدر غير صالح في ملف الدفعة: %s (المسموح: "
            "veo/openmontage)" % source)
    default_engine = data.get("default_engine", "fast")
    if default_engine not in ("fast", "lite"):
        raise BatchError(
            "المحرك الافتراضي غير صالح في ملف الدفعة: %s (المسموح: "
            "fast/lite)" % default_engine)
    name = data.get("name")
    if name is not None:
        if not isinstance(name, str) or not name.strip():
            raise BatchError(
                "اسم الدفعة في ملف الدفعة يجب أن يكون نصًا غير فارغ")
        name = name.strip()
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise BatchError(
            "ملف الدفعة بلا مهام — ضع قائمة «tasks» فيها مهمة "
            "واحدة على الأقل")
    seen_titles = set()
    out_tasks = []
    for index, raw in enumerate(tasks, 1):
        if not isinstance(raw, dict):
            raise BatchError(
                "المهمة رقم %d في ملف الدفعة يجب أن تكون قاموسًا "
                "(وصل: %s)" % (index, type(raw).__name__))
        for key in raw:
            if key not in _JSON_TASK_KEYS:
                raise BatchError(
                    "حقل غير معروف في المهمة رقم %d: «%s» (المسموح: "
                    "%s)" % (index, key,
                             "/".join(_JSON_TASK_KEYS)))
        title = raw.get("title", raw.get("story"))
        if not isinstance(title, str) or not title.strip():
            raise BatchError(
                "المهمة رقم %d بلا عنوان — حقل «title» مطلوب "
                "وغير فارغ" % index)
        title = title.strip()
        if title.lower() in seen_titles:
            raise BatchError(
                "عنوان مكرر في ملف الدفعة: «%s» (المهمة رقم %d)"
                % (title, index))
        seen_titles.add(title.lower())
        parts = _json_int(raw.get("parts", MIN_PARTS), "parts",
                          MIN_PARTS, MAX_PARTS)
        clips = _json_int(raw.get("clips", DEFAULT_CLIPS_PER_PART),
                          "clips", MIN_CLIPS_PER_PART,
                          MAX_CLIPS_PER_PART)
        engine = raw.get("engine", default_engine)
        if engine not in ("fast", "lite"):
            raise BatchError(
                "محرك Veo غير صالح في المهمة رقم %d («%s»): %s "
                "(المسموح: fast/lite)" % (index, title, engine))
        note = raw.get("note", raw.get("notes", ""))
        if note is None:
            note = ""
        if not isinstance(note, str):
            raise BatchError(
                "ملاحظة المهمة رقم %d («%s») يجب أن تكون نصًا"
                % (index, title))
        slug = raw.get("slug")
        if slug is not None:
            if not isinstance(slug, str) or not slug.strip() \
                    or any(ch.isspace() for ch in slug):
                raise BatchError(
                    "معرّف المهمة رقم %d («%s») غير صالح — نص بلا "
                    "مسافات" % (index, title))
            slug = slug.strip()
        number = raw.get("number")
        if number is not None:
            number = _json_int(number, "number", 1, 10 ** 9)
        out_tasks.append({
            "title": title, "parts": parts, "engine": engine,
            "clips": clips, "total_clips": parts * clips,
            "note": note.strip(), "slug": slug,
            "number": number if number is not None else index,
        })
    return {"name": name, "source": source,
            "default_engine": default_engine, "tasks": out_tasks}


def load_json_batch(json_path):
    """اقرأ ملف دفعة JSON من القرص وتحقق منه صارمًا.

    مثال لملف صالح:
        {
          "name": "دفعة الصباح",
          "source": "veo",
          "default_engine": "lite",
          "tasks": [
            {"title": "العنزة المباركة", "parts": 2, "clips": 6},
            {"title": "عجائب الصدقة", "parts": 1, "engine": "fast"}
          ]
        }
    يرجع نتيجة parse_json_batch المطبّعة. يرفع BatchError
    برسالة عربية عند: ملف غائب، JSON غير صالح (يُشرح عبر
    lib/errors.py)، أو أي عطب في البنية/الحقول.
    """
    path = os.path.expanduser(json_path)
    if not os.path.isfile(path):
        raise BatchError("ملف الدفعة غير موجود: %s" % path)
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise BatchError("تعذرت قراءة ملف الدفعة: %s" % e)
    try:
        data = json.loads(text)
    except ValueError as e:
        raise BatchError(
            "ملف الدفعة ليس JSON صالحًا: %s\n%s"
            % (e, errors_lib.explain_error_text(str(e))))
    return parse_json_batch(data)


def _task_estimated_units(task, source):
    """وحدات Veo المتوقعة لمهمة (0 لمصدر openmontage).

    عبر ab.estimate_variant_cost — نفس تسعيرة المتغيرات:
    20 وحدة/مقطع Fast و10 وحدات/مقطع Lite.
    """
    if source != "veo":
        return 0
    est = ab_lib.estimate_variant_cost(
        clips=task["total_clips"], engine=task["engine"])
    return est["veo_units"]


def _veo_balance_or_raise(cfg):
    """الرصيد المسجَّل كعدد صحيح — يرفع BatchError عند غيابه
    أو فساده (نفس رسائل plan_batch)."""
    veo_cfg = (cfg.get("veo") or {}) if isinstance(cfg, dict) else {}
    balance = veo_cfg.get("balance_units")
    if balance is None:
        raise BatchError(
            "رصيد Veo غير مسجَّل — حدّث veo.balance_units في "
            "config.yaml أو استخدم --source openmontage")
    try:
        return balance_lib._as_int(balance, "الرصيد")
    except ValueError:
        raise BatchError("رصيد Veo غير صالح: %s" % (balance,))


def plan_batch_from_json(cfg, json_path=None, data=None, source=None,
                         ready_fn=None):
    """ابنِ خطة دفعة من ملف/بيانات JSON — كما من الطابور.

    json_path أو data (قاموس/قائمة كما في parse_json_batch) —
    أحدهما مطلوب. source (اختياري) يتجاوز مصدر الملف. ready_fn
    كما في plan_batch: ready_fn(entry) -> ‏(جاهزة؟، slug،
    مشروع، سبب)؛ وبلاها تُعتبر كل مهمة جاهزة بلا slug. الخطة
    المُرجَعة بنفس شكل plan_batch (count/source/stories/...) مع
    حقول إضافية لكل قصة: parts/engine/clips/total_clips/
    estimated_units/from_json، وحقل "json_name" باسم الدفعة.
    لمسار Veo: فحص الرصيد والسقف لكل فيديو (عبر
    balance.check_cap) ولإجمالي الدفعة، برسائل plan_batch
    نفسها. خطة المشاهد (scene_plan) تُبنى لمحرك Fast فقط —
    فـ build_scene_plan يفحص السقف بتسعيرة Fast (20 وحدة/
    مقطع)؛ ومهمة Lite تُبنى خطتها عند التنفيذ بنفس المقاطع.
    يرفع BatchError برسالة عربية عند أي عطب في الملف أو
    تجاوز للرصيد/السقف.
    """
    if json_path is not None:
        parsed = load_json_batch(json_path)
    elif data is not None:
        parsed = parse_json_batch(data)
    else:
        raise BatchError(
            "حدد ملف دفعة JSON (--from-json) أو بياناتها")
    batch_source = source or parsed["source"]
    if batch_source not in ("veo", "openmontage"):
        raise BatchError(
            "المصدر غير صالح: %s (المسموح: veo/openmontage)"
            % batch_source)
    tasks = parsed["tasks"]
    videos_dir = os.path.expanduser(
        (cfg.get("paths") or {}).get("videos_dir") or "~/workspace/videos")
    veo_cfg = (cfg.get("veo") or {}) if isinstance(cfg, dict) else {}
    balance = None
    if batch_source == "veo":
        balance = _veo_balance_or_raise(cfg)
    stories = []
    for task in tasks:
        entry = {"number": task["number"], "title": task["title"],
                 "note": task["note"]}
        ready, slug, project, reason = ((True, None, None, "")
                                         if ready_fn is None
                                         else ready_fn(entry))
        # slug صريح في JSON يسبق ما ترجعه ready_fn إن غاب منها.
        if not slug and task.get("slug"):
            slug = task["slug"]
        video = None
        video_ready = False
        if slug:
            video = os.path.join(videos_dir, "%s-batch.mp4" % slug)
            video_ready = os.path.isfile(video)
        units = _task_estimated_units(task, batch_source)
        item = {"number": task["number"], "title": task["title"],
                "note": task["note"],
                "ready": bool(ready), "slug": slug, "project": project,
                "reason": reason,
                "video": video, "video_ready": video_ready,
                "scene_plan": None,
                "parts": task["parts"], "engine": task["engine"],
                "clips": task["clips"],
                "total_clips": task["total_clips"],
                "estimated_units": units,
                "from_json": True}
        if batch_source == "veo" and ready:
            if balance is not None and units > 0 \
                    and balance < units:
                raise BatchError(
                    "رصيد Veo %d وحدة (أقل من %d وحدة لفيديو «%s») "
                    "— مسار Veo مرفوض؛ استخدم --source openmontage"
                    % (balance, units, task["title"]))
            if units > 0:
                ok, reason_cap = balance_lib.check_cap(
                    units, veo_cfg)
                if not ok:
                    raise BatchError(reason_cap)
            if task["engine"] == "fast":
                try:
                    item["scene_plan"] = scene_plan_lib.build_scene_plan(
                        cfg, entry, clips=task["clips"])
                except scene_plan_lib.CapError as e:
                    item["ready"] = False
                    item["reason"] = str(e)
                    item["scene_plan"] = None
        stories.append(item)
    total_expected = sum(
        s["estimated_units"] for s in stories if s["ready"])
    if batch_source == "veo" and balance is not None \
            and total_expected > balance:
        raise BatchError(
            "الإنفاق المتوقع للدفعة (%d وحدة لـ%d قصص جاهزة) "
            "يتجاوز الرصيد المسجَّل (%d وحدة) — قلّل المهام أو "
            "استخدم --source openmontage"
            % (total_expected,
               len([s for s in stories if s["ready"]]),
               balance))
    # المتوقع للفيديو الواحد (لحكم السقف): أعلى تكلفة مهمة
    # جاهزة — فمهام JSON تختلف تكلفتها بالمحرك والأجزاء.
    per_video = max(
        [s["estimated_units"] for s in stories if s["ready"]]
        or [0])
    return {
        "count": len(stories),
        "source": batch_source,
        "balance_units": veo_cfg.get("balance_units"),
        "cap_units": veo_cfg.get("cap_units"),
        "expected_units_per_video": per_video,
        "total_expected_units": total_expected,
        "stories": stories,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "json_name": parsed.get("name"),
        "from_json": True,
    }


# ------------------------------------------------------- وضع no-spend (أ2-3)
def validate_batch(cfg, plan, runs_dir=None, fingerprint_fn=None,
                   probe_fn=None):
    """حاكِ الدفعة كاملة بلا أي إنفاق — فحص جاف (no-spend).

    بلا produce_fn أصلًا في التوقيع: لا استدعاء إنتاج ممكن،
    وبلا أي طلب شبكة، وبلا خصم رصيد (لا record_spend_fn ولا
    كتابة في config). يفحص لكل قصة: الجاهزية، ومسار الإخراج
    (slug)، وفيديو Veo الجاهز، ويقدّر رصيد Veo عبر
    ab.estimate_variant_cost (مقاطع × 10 Lite / 20 Fast)،
    ويفحص كفاية الرصيد والسقف عبر balance.check_cap، ويذكر
    ما سيُعاد استخدامه من الكاش (lookup في runs_dir إن مُرّر
    — بلا إنتاج). يرجع تقريرًا: ok (بلا أي خطأ مانع)، وعدد
    المهام/الجاهزة/المعاد استخدامها، والرصيد المطلوب/المتاح
    وكفايته، وقائمة errors، وأول خطأ مانع first_blocking_error.
    ملاحظة: ok=False تعني وجود مهمة مانعة (متخطاة/بلا فيديو
    Veo/رصيد ناقص) — راجع قائمة tasks للتفاصيل.
    """
    source = plan.get("source")
    veo_cfg = (cfg.get("veo") or {}) if isinstance(cfg, dict) else {}
    balance = veo_cfg.get("balance_units")
    balance_int = None
    if balance is not None:
        try:
            balance_int = balance_lib._as_int(balance, "الرصيد")
        except ValueError:
            balance_int = None
    video_cfg = (cfg.get("video") or {}) if isinstance(cfg, dict) else {}
    expected_width = video_cfg.get("width")
    expected_height = video_cfg.get("height")
    errors = []
    task_reports = []
    total_units = 0
    reused_count = 0
    for item in plan.get("stories") or []:
        entry = {"number": item.get("number"),
                 "title": item.get("title"),
                 "ready": bool(item.get("ready")),
                 "engine": item.get("engine") or "fast",
                 "clips": item.get("total_clips")
                 or item.get("clips") or DEFAULT_CLIPS_PER_PART,
                 "estimated_units": 0,
                 "reused": False, "reused_from": None,
                 "status": None, "error": None}
        if not item.get("ready"):
            entry["status"] = "skipped"
            entry["error"] = item.get("reason") or "غير جاهزة"
            errors.append("«%s»: %s" % (entry["title"],
                                        entry["error"]))
            task_reports.append(entry)
            continue
        # تقدير الرصيد عبر ab (لـ Veo فقط؛ OpenMontage صفر) —
        # يُحسب أولًا ثم يُسقَط إن تبيّن أن المهمة معاد استخدامها
        # من الكاش (بلا إنتاج وبلا رصيد).
        est_units = 0
        if source == "veo":
            try:
                est = ab_lib.estimate_variant_cost(
                    clips=int(entry["clips"]),
                    engine=entry["engine"])
                est_units = est["veo_units"]
                entry["estimated_units"] = est_units
                entry["render_minutes_estimate"] = est[
                    "render_minutes_estimate"]
            except ValueError as e:
                entry["status"] = "blocked"
                entry["error"] = str(e)
                errors.append("«%s»: %s" % (entry["title"],
                                            entry["error"]))
                task_reports.append(entry)
                continue
        # الكاش: مخرج سابق بنفس البصمة وعلى مسار الإخراج نفسه.
        if runs_dir:
            fingerprint = _fingerprint_for(
                cfg, item, source, fingerprint_fn)
            if fingerprint:
                try:
                    cached = render_cache_lib.lookup(
                        runs_dir, fingerprint,
                        expected_width=expected_width,
                        expected_height=expected_height,
                        probe_fn=probe_fn)
                    if cached is not None and item.get("video") \
                            and os.path.abspath(os.path.expanduser(
                                cached.get("output") or "")) \
                            == os.path.abspath(os.path.expanduser(
                                item["video"])):
                        entry["reused"] = True
                        entry["reused_from"] = cached.get("output")
                        entry["estimated_units"] = 0
                        reused_count += 1
                except Exception:
                    pass
        if entry["reused"]:
            entry["status"] = "reused"
            task_reports.append(entry)
            continue
        total_units += est_units
        if not item.get("video"):
            entry["status"] = "blocked"
            entry["error"] = ("بلا مسار إخراج — القصة بلا slug/"
                              "مشروع؛ لا يمكن إنتاجها")
            errors.append("«%s»: %s" % (entry["title"],
                                        entry["error"]))
            task_reports.append(entry)
            continue
        if source == "veo" and not item.get("video_ready"):
            entry["status"] = "needs-flow"
            entry["error"] = ("مسار Veo بلا فيديو جاهز — أنتج "
                              "المشاهد في Google Flow أولًا")
            errors.append("«%s»: %s" % (entry["title"],
                                        entry["error"]))
            task_reports.append(entry)
            continue
        entry["status"] = "ready"
        task_reports.append(entry)
    # كفاية الرصيد والسقف (لـ Veo فقط، وعلى الإجمالي بعد الكاش).
    balance_sufficient = None
    cap_ok = None
    if source == "veo":
        if balance_int is None:
            errors.append(
                "رصيد Veo غير مسجَّل — حدّث veo.balance_units في "
                "config.yaml أو استخدم --source openmontage")
        elif total_units > 0:
            try:
                ok_cap, reason_cap = balance_lib.check_cap(
                    total_units, veo_cfg)
            except ValueError as e:
                ok_cap, reason_cap = False, str(e)
            balance_sufficient = ok_cap
            cap_ok = ok_cap
            if not ok_cap:
                errors.append(reason_cap)
        else:
            balance_sufficient = True
            cap_ok = True
    report = {
        "no_spend": True,
        "source": source,
        "count": len(task_reports),
        "ready_count": len([t for t in task_reports
                            if t["status"] in ("ready", "reused")]),
        "reused_count": reused_count,
        "reused_titles": [t["title"] for t in task_reports
                          if t["reused"]],
        "total_expected_units": total_units,
        "balance_units": balance_int,
        "balance_sufficient": balance_sufficient,
        "cap_ok": cap_ok,
        "ok": not errors,
        "errors": errors,
        "first_blocking_error": errors[0] if errors else None,
        "tasks": task_reports,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    return report


def format_no_spend_report(report):
    """نص عربي موجز لتقرير validate_batch (وضع --no-spend)."""
    lines = ["== تقرير no-spend — دفعة %d مهام (المصدر: %s) =="
             % (report.get("count") or 0,
                "Veo (في Google Flow)" if report.get("source") == "veo"
                else "OpenMontage (بلا رصيد)"),
             "المهام الجاهزة: %d — المعاد استخدامها من الكاش: %d"
             % (report.get("ready_count") or 0,
                report.get("reused_count") or 0)]
    if report.get("source") == "veo":
        balance = report.get("balance_units")
        verdict = ("ضمن الرصيد" if report.get("balance_sufficient")
                   else "يتجاوز الرصيد" if report.get(
                       "balance_sufficient") is False
                   else "غير مسجَّل")
        lines.append(
            "الرصيد المطلوب: %d وحدة (الرصيد المسجَّل: %s — %s)"
            % (report.get("total_expected_units") or 0,
               ("%d وحدة" % balance) if balance is not None
               else "غير مسجَّل", verdict))
    else:
        lines.append("الرصيد المطلوب: 0 وحدة (OpenMontage بلا رصيد)")
    reused = report.get("reused_titles") or []
    lines.append("المعاد استخدامه من الكاش: %s"
                 % ("، ".join("«%s»" % t for t in reused)
                    if reused else "لا شيء — كل المهام تحتاج إنتاجًا"))
    lines.append("")
    for t in report.get("tasks") or []:
        if t["status"] == "ready":
            lines.append("  %s. %s — جاهزة (%s: %d مقاطع — %d وحدة)"
                         % (t.get("number"), t.get("title"),
                            "Lite" if t.get("engine") == "lite"
                            else "Fast", t.get("clips") or 0,
                            t.get("estimated_units") or 0))
        elif t["status"] == "reused":
            lines.append("  %s. %s — تُعاد من الكاش بلا إنتاج "
                         "وبلا رصيد" % (t.get("number"), t.get("title")))
        elif t["status"] == "skipped":
            lines.append("  %s. %s — تُتخطى: %s"
                         % (t.get("number"), t.get("title"),
                            t.get("error") or ""))
        else:
            lines.append("  %s. %s — يمنع التنفيذ: %s"
                         % (t.get("number"), t.get("title"),
                            t.get("error") or ""))
    lines.append("")
    if report.get("ok"):
        lines.append("النتيجة: الدفعة جاهزة — بلا أخطاء مانعة.")
    else:
        lines.append("النتيجة: يمنع التنفيذ: %s"
                     % (report.get("first_blocking_error") or ""))
    lines.append("لم يُستدعَ أي إنتاج ولم يُخصم أي رصيد — "
                 "فحص جاف فقط (no-spend).")
    return "\n".join(lines) + "\n"


def required_units_line(plan):
    """سطر «الرصيد المطلوب» الصريح (الجولة 9 — v0.1.34).

    للمصدر veo: إجمالي الدفعة المطلوب مقابل الرصيد المسجَّل
    مع حكم صريح (ضمن الرصيد/يتجاوز الرصيد)؛ ولـ openmontage:
    0 وحدة صراحةً (بلا رصيد). كان format_plan يطبع الرصيد
    والسقف والمجموع في سطر مدمج واحد لمصدر veo فقط، ولا شيء
    إطلاقًا لمصدر openmontage — فلوحة التحكم تعرض الخطة
    حرفيًا كانت تبقى بلا هذين السطرين.
    """
    if plan["source"] == "openmontage":
        return "الرصيد المطلوب: 0 وحدة (OpenMontage بلا رصيد)"
    total = plan.get("total_expected_units") or 0
    balance = plan.get("balance_units")
    if balance is None:
        return ("الرصيد المطلوب: %d وحدة "
                "(الرصيد المسجَّل: غير مسجَّل)" % total)
    verdict = ("ضمن الرصيد" if total <= balance
               else "يتجاوز الرصيد")
    return ("الرصيد المطلوب: %d وحدة (الرصيد المسجَّل: %d وحدة "
            "— %s)" % (total, balance, verdict))


def cap_status_line(plan):
    """سطر «حالة السقف» الصريح (الجولة 9 — v0.1.34).

    للمصدر veo: حكم صريح على المتوقع للفيديو مقابل السقف
    (ضمن السقف/يتجاوز السقف/بلا سقف مضبوط)؛ ولـ openmontage:
    لا ينطبق صراحةً. السقف لكل فيديو (لا للدفعة كلها) —
    فالحكم يقيس المتوقع للفيديو الواحد.
    """
    if plan["source"] == "openmontage":
        return "حالة السقف: لا ينطبق (OpenMontage بلا رصيد ولا سقف)"
    cap = plan.get("cap_units")
    per_video = plan.get("expected_units_per_video") or 0
    if cap is None:
        return ("حالة السقف: بلا سقف مضبوط (المتوقع للفيديو %d "
                "وحدة — يُفحص الرصيد فقط)" % per_video)
    if per_video > cap:
        return ("حالة السقف: يتجاوز السقف (المتوقع للفيديو %d "
                "وحدة > سقف %d وحدة)" % (per_video, cap))
    return ("حالة السقف: ضمن السقف (المتوقع للفيديو %d وحدة "
            "≤ سقف %d وحدة)" % (per_video, cap))


def format_plan(plan):
    """نص عربي للخطة (وضع تجريبي)."""
    lines = ["== خطة الدفعة — %d قصص (المصدر: %s) =="
             % (plan["count"],
                "Veo (في Google Flow)" if plan["source"] == "veo"
                else "OpenMontage (بلا رصيد)"),
             required_units_line(plan),
             cap_status_line(plan)]
    lines.append("")
    for s in plan["stories"]:
        if not s["ready"]:
            status = "تُتخطى: %s" % s["reason"]
        elif plan["source"] == "veo" and not s["video_ready"]:
            status = "تحتاج توليدًا في Flow أولًا (بلا فيديو جاهز)"
        else:
            status = "جاهزة%s" % (
                " (مشروع %s)" % s["project"] if s["project"] else "")
        if s.get("from_json"):
            status += " — %s، %s، %d وحدة" % (
                "جزآن" if s.get("parts") == 2 else "جزء واحد",
                "Lite" if s.get("engine") == "lite" else "Fast",
                s.get("estimated_units") or 0)
        lines.append("  %d. %s — %s" % (s["number"], s["title"], status))
    lines.append("")
    if plan["source"] == "veo":
        lines.append("تنبيه: إنتاج Veo يتم في Google Flow يدويًا — "
                     "الدفعة تنتج فقط القصص التي لها فيديو جاهز.")
    return "\n".join(lines) + "\n"


def _default_fingerprint_inputs(cfg, item):
    """مدخلات البصمة الافتراضية لقصة في دفعة: slug + العنوان +
    المصدر + خطة المشاهد + مقاس الفيديو من الإعداد.

    قيد موثّق: هذه بصمة على مستوى الخطة لا على مستوى ملفات
    الأصول — تغيير ملف صوت/صورة بلا تغيير العنوان أو الخطة لا
    يغيّرها. لمسار أعمق مرّر fingerprint_fn يبني المدخلات من
    بصمات الملفات الفعلية (lib/render_cache.fingerprint_inputs).
    """
    video_cfg = (cfg.get("video") or {}) if isinstance(cfg, dict) else {}
    inputs = {"slug": item.get("slug"), "title": item.get("title"),
              "source": None,
              "settings": {"width": video_cfg.get("width"),
                           "height": video_cfg.get("height")}}
    return inputs


def _fingerprint_for(cfg, item, source, fingerprint_fn):
    """احسب بصمة قصة (أو None إن تعذر/لم تُطلب).

    fingerprint_fn(cfg, item) — اختياري — يرجع قاموس مدخلات
    (يُبصم عبر fingerprint_inputs) أو بصمة جاهزة (نص) أو None
    (بلا كاش لهذه القصة). بلا دالة يُستخدم الافتراضي أعلاه.
    أي خطأ هنا ← None (الكاش لا يكسر الدفعة أبدًا).
    """
    try:
        if fingerprint_fn is not None:
            value = fingerprint_fn(cfg, item)
            if value is None:
                return None
            if isinstance(value, str):
                return value
            return render_cache_lib.fingerprint_inputs(value)
        inputs = _default_fingerprint_inputs(cfg, item)
        inputs["source"] = source
        if item.get("scene_plan") is not None:
            inputs["scene_plan"] = item["scene_plan"]
        return render_cache_lib.fingerprint_inputs(inputs)
    except Exception:
        return None


def _safe_register(runs_dir, kind, story, title, fingerprint):
    """سجّل مهمة بلا كسر للدفعة عند أي خطأ (يرجع المعرّف أو None)."""
    try:
        job = job_registry_lib.register_job(
            runs_dir, kind, story=story, title=title,
            input_fingerprint=fingerprint)
        return job["job_id"]
    except Exception:
        return None


def _safe_update(runs_dir, job_id, **kwargs):
    """حدّث مهمة بلا كسر للدفعة عند أي خطأ."""
    if not job_id:
        return
    try:
        job_registry_lib.update_job(runs_dir, job_id, **kwargs)
    except Exception:
        pass


def execute_batch(cfg, plan, produce_fn, check_fn, thumbnail_fn,
                  runs_dir, continue_on_error=False,
                  record_spend_fn=None, use_cache=True,
                  fingerprint_fn=None, probe_fn=None):
    """نفّذ خطة الدفعة (بعد --execute الصريح).

    الدوال المحقونة (قابلة للاختبار بلا تنفيذ حقيقي):
      produce_fn(cfg, slug, project, out_path) -> 0/1
      check_fn(video) -> قاموس run_checks (فيه "passed")
      thumbnail_fn(video, hook, out_path) -> مسار المصغرة
      record_spend_fn(units) -> الرصيد الجديد أو None: تُستدعى
        بعد كل فيديو Veo مكتمل فقط (الجولة 8) — لا خصم لقصة
        متخطاة أو فاشلة، ولا خصم أبدًا في وضع تجريبي.
    كاش الريندر (الجولة v0.1.39): use_cache=True (الافتراضي)
    يبحث قبل الإنتاج عن مخرج سابق بنفس بصمة المدخلات؛ فإن
    وُجد سليمًا (ملف موجود + مدة/أبعاد صحيحة عبر ffprobe)
    يُتخطى produce_fn وتُسجَّل القصة reused بلا خصم رصيد،
    مع فحص الجودة الكامل على المخرج المعاد استخدامه — فإن
    فشل الفحص يُحذف إدخال الكاش وتفشل القصة (الدفعة التالية
    تعيد الريندر). fingerprint_fn(cfg, item) اختياري لبصمة
    أعمق (قاموس مدخلات أو بصمة نصية أو None لتعطيل الكاش
    لتلك القصة)؛ وprobe_fn اختياري لفحص الفيديو (الافتراضي
    lib.check.probe). كل مهمة تُسجَّل في سجل المهام الدائم
    (runs/jobs.jsonl — lib/job_registry).
    يرجع (رمز الخروج، قاموس النتائج المحفوظ في runs/batch-*.json).
    """
    result = {"date": time.strftime("%Y-%m-%d %H:%M:%S"),
              "count": plan["count"], "source": plan["source"],
              "stories": [], "total_spent_units": 0}
    overall = 0
    video_cfg = (cfg.get("video") or {}) if isinstance(cfg, dict) else {}
    expected_width = video_cfg.get("width")
    expected_height = video_cfg.get("height")
    for item in plan["stories"]:
        entry = {"number": item["number"], "title": item["title"],
                 "ready": item["ready"], "project": item["project"]}
        job_id = _safe_register(
            runs_dir, "batch", story=str(item["number"]),
            title=item["title"], fingerprint=None)
        if not item["ready"]:
            entry["status"] = "skipped"
            entry["reason"] = item["reason"]
            result["stories"].append(entry)
            _safe_update(runs_dir, job_id, status="skipped",
                         error=item["reason"])
            continue
        if plan["source"] == "veo" and not item["video_ready"]:
            entry["status"] = "needs-flow"
            entry["reason"] = ("مسار Veo بلا فيديو جاهز — أنتج "
                               "المشاهد في Google Flow أولًا")
            entry["scene_plan"] = item.get("scene_plan")
            result["stories"].append(entry)
            _safe_update(runs_dir, job_id, status="skipped",
                         error=entry["reason"])
            continue
        video = item["video"]
        # كاش الريندر: بصمة ثم بحث عن مخرج سابق سليم.
        fingerprint = _fingerprint_for(cfg, item, plan["source"],
                                       fingerprint_fn) \
            if use_cache else None
        cached = None
        if fingerprint:
            _safe_update(runs_dir, job_id,
                         input_fingerprint=fingerprint)
            try:
                cached = render_cache_lib.lookup(
                    runs_dir, fingerprint,
                    expected_width=expected_width,
                    expected_height=expected_height,
                    probe_fn=probe_fn)
                # المخرج المخزّن يخص مسار إخراج بعينه — إن
                # تغيّر مجلد الفيديو فالمسار المخزّن ليس مسار
                # هذه الخطة، فيُعامل كلا-إصابة (لا يُرجَع ملف
                # من مسار آخر على أنه مخرج هذه القصة).
                if cached is not None and os.path.abspath(
                        os.path.expanduser(cached.get("output") or "")) \
                        != os.path.abspath(os.path.expanduser(video)):
                    cached = None
            except Exception:
                cached = None
        t0 = time.time()
        if cached is not None:
            print("قصة %d (%s): مخرج سابق بنفس البصمة — أُعيد "
                  "استخدامه بلا إعادة ريندر" % (item["number"],
                                                item["title"]))
            entry["reused"] = True
            entry["reused_from"] = cached.get("output")
            entry["output"] = video
            entry["check_passed"] = None
            print("  فحص الجودة…")
            try:
                check = check_fn(video)
            except Exception as e:
                check = {"passed": False, "error": str(e)}
            entry["check_passed"] = bool(check.get("passed"))
            if not check.get("passed"):
                try:
                    render_cache_lib.invalidate(runs_dir, fingerprint)
                except Exception:
                    pass
                entry["status"] = "failed"
                entry["reason"] = ("فشل فحص الجودة على المخرج "
                                   "المعاد استخدامه")
                entry["seconds"] = round(time.time() - t0, 1)
                result["stories"].append(entry)
                overall = 1
                print("  فشل فحص الجودة")
                _safe_update(runs_dir, job_id, status="failed",
                             outputs=[video],
                             error=entry["reason"])
                if not continue_on_error:
                    print("توقفت الدفعة — استخدم --continue-on-error "
                          "للمتابعة بعد الفشل")
                    break
                continue
            thumb = cached.get("thumbnail")
            if not thumb or not os.path.isfile(thumb):
                thumb = thumbnail_fn(
                    video, item["title"],
                    os.path.splitext(video)[0] + "-thumbnail.jpg")
            entry["thumbnail"] = thumb
            entry["status"] = "reused"
            entry["seconds"] = round(time.time() - t0, 1)
            result["stories"].append(entry)
            _safe_update(runs_dir, job_id, status="reused",
                         outputs=[video], reused=True)
            print("  تمت (أُعيد استخدامه): %s" % video)
            continue
        print("قصة %d (%s): الإنتاج (%s)…"
              % (item["number"], item["title"], plan["source"]))
        rc = produce_fn(cfg, item["slug"], item["project"], video)
        entry["produce"] = "done" if rc == 0 else "failed"
        if rc != 0:
            entry["status"] = "failed"
            entry["seconds"] = round(time.time() - t0, 1)
            result["stories"].append(entry)
            overall = 1
            print("  فشل الإنتاج")
            _safe_update(runs_dir, job_id, status="failed",
                         error="فشل الإنتاج")
            if not continue_on_error:
                print("توقفت الدفعة — استخدم --continue-on-error "
                      "للمتابعة بعد الفشل")
                break
            continue
        print("  فحص الجودة…")
        check = check_fn(video)
        entry["check_passed"] = bool(check.get("passed"))
        if not check.get("passed"):
            entry["status"] = "failed"
            entry["reason"] = "فشل فحص الجودة"
            entry["seconds"] = round(time.time() - t0, 1)
            result["stories"].append(entry)
            overall = 1
            print("  فشل فحص الجودة")
            _safe_update(runs_dir, job_id, status="failed",
                         outputs=[video], error=entry["reason"])
            if not continue_on_error:
                print("توقفت الدفعة — استخدم --continue-on-error "
                      "للمتابعة بعد الفشل")
                break
            continue
        print("  الصورة المصغرة…")
        thumb = thumbnail_fn(video, item["title"],
                             os.path.splitext(video)[0] + "-thumbnail.jpg")
        entry["thumbnail"] = thumb
        entry["output"] = video
        entry["status"] = "done"
        # الجولة 8: فيديو Veo مكتمل فعلًا — يُخصم إنفاقه (120
        # وحدة) من الرصيد المسجَّل ويُختم الوقت.
        if plan["source"] == "veo" and record_spend_fn is not None:
            entry["units_spent"] = VEO_UNITS_PER_VIDEO
            entry["new_balance"] = record_spend_fn(
                VEO_UNITS_PER_VIDEO)
            result["total_spent_units"] += VEO_UNITS_PER_VIDEO
        entry["seconds"] = round(time.time() - t0, 1)
        result["stories"].append(entry)
        _safe_update(runs_dir, job_id, status="done",
                     outputs=[video])
        # كاش الريندر: سجّل المخرج الجديد تحت بصمته (إن حُسبت
        # والملف سليم) ليُعاد استخدامه في دفعة لاحقة.
        if fingerprint:
            try:
                render_cache_lib.store(runs_dir, fingerprint, video,
                                       thumbnail=thumb,
                                       probe_fn=probe_fn)
            except Exception:
                pass
        print("  تمت: %s" % video)
    os.makedirs(runs_dir, exist_ok=True)
    out_path = os.path.join(
        runs_dir, "batch-%s.json" % time.strftime("%Y%m%d-%H%M%S"))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("سُجّلت نتائج الدفعة في: %s" % out_path)
    return overall, result
