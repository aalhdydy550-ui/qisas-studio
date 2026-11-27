#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""فرز تعليقات ورسائل الصفحة بنموذجين مساعدين — جولة v0.1.63 (بند 26).

نموذجان رخيصان لا يستطيعان الفعل فلا حاجة لسياج:
- القارئ: يقرأ كل تعليق/رسالة (المرسل، الطلب، المهلة، المبلغ،
  هل ينتظر ردًا، النوع).
- المقرر: يقرر مهم / يحتاج ردًا / تخطٍّ، سامعًا المرسلين الذين
  رفضهم المستخدم مؤخرًا.

الفشل يعني الانتظار للفحص التالي (حالة ``deferred``) — لا يسقط
العنصر أبدًا. دور كامل يعمل فقط عند ضغطة زر أو لتحضير رد.

استدعاءات النموذج تمر عبر عميل LLM الموجود (استيراد كسول لـ
``lib.omniroute_client`` داخل الدوال)؛ والاختبارات تحقن عميلًا
وهميًا — بلا شبكة أبدًا.
"""
import json
import re

# نموذجان رخيصان للفرز؛ قابلة للتجاوز عبر وسيطي model في الدوال.
READER_MODEL = "gemini-flash-lite"
DECIDER_MODEL = "gemini-flash-lite"

# أنواع تعليقات/رسائل صفحة «قصص وعبر».
KINDS = ("سؤال", "طلب قصة", "شكوى", "مدح", "سبام", "أخرى")

# قرارات المقرر.
DECISIONS = ("مهم", "يحتاج ردًا", "تخطٍّ")
DEFERRED = "deferred"


class TriageError(Exception):
    """فشل فرز عنصر — ينتظر الفحص التالي."""


def _default_client():
    """عميل LLM الموجود، باستيراد كسول (بلا اعتماد بناء)."""
    from lib import omniroute_client
    return omniroute_client


def _call_model(client, prompt, model):
    """استدعِ النموذج عبر العميل؛ ارجع نص الرد.

    العميل إما وحدة ``omniroute_client`` (ترجع ``chat`` ثلاثية
    نص/مسار/نموذج) أو عميل وهمي في الاختبارات يرجع نصًا.
    """
    if client is None:
        client = _default_client()
    result = client.chat(prompt, model, max_tokens=300, temperature=0.0)
    if isinstance(result, (tuple, list)):
        return result[0]
    return result


def _extract_json(text):
    """استخرج أول كائن JSON من نص رد؛ ارفع TriageError إن تعذّر."""
    if not isinstance(text, str):
        raise TriageError("رد النموذج ليس نصًا")
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise TriageError("رد النموذج بلا كائن JSON")
    try:
        data = json.loads(match.group(0))
    except ValueError:
        raise TriageError("رد النموذج JSON مشوّه")
    if not isinstance(data, dict):
        raise TriageError("رد النموذج ليس كائنًا")
    return data


def read_message(text, client=None, model=READER_MODEL):
    """القارئ: استخرج حقول تعليق/رسالة من نصه.

    يرجع قاموسًا: ``sender`` و``request`` و``deadline`` و``amount``
    و``awaits_reply`` (bool) و``kind`` (من KINDS). أي فشل يرفع
    TriageError — فينتظر العنصر الفحص التالي.
    """
    prompt = (
        "اقرأ التعليق/الرسالة التالية من صفحة قصص وعبر وأرجع JSON فقط "
        "بهذه الحقول: sender (المرسل أو null)، request (الطلب بجملة "
        "واحدة)، deadline (المهلة أو null)، amount (المبلغ أو null)، "
        "awaits_reply (true/false: هل ينتظر ردًا)، kind (واحد من: "
        "سؤال، طلب قصة، شكوى، مدح، سبام، أخرى).\n\n%s" % text
    )
    try:
        reply = _call_model(client, prompt, model)
    except Exception as exc:
        raise TriageError("فشل استدعاء نموذج القارئ: %s" % exc)
    data = _extract_json(reply)
    kind = data.get("kind")
    if kind not in KINDS:
        kind = "أخرى"
    return {
        "sender": data.get("sender"),
        "request": data.get("request") or "",
        "deadline": data.get("deadline"),
        "amount": data.get("amount"),
        "awaits_reply": bool(data.get("awaits_reply", False)),
        "kind": kind,
    }


def decide(reading, recent_dismissals=None, client=None,
           model=DECIDER_MODEL):
    """المقرر: مهم / يحتاج ردًا / تخطٍّ — مع احترام التجاهلات الأخيرة.

    مرسل رفضه المستخدم مؤخرًا يُتخطَّى مباشرة بلا استدعاء نموذج.
    أي فشل يرفع TriageError — فينتظر العنصر الفحص التالي.
    """
    sender = reading.get("sender")
    if recent_dismissals and sender and sender in recent_dismissals:
        return {"decision": "تخطٍّ",
                "reason": "المرسل ضمن التجاهلات الأخيرة"}
    prompt = (
        "قرر مصير هذا التعليق/الرسالة من صفحة قصص وعبر وأرجع JSON فقط "
        "بحقل decision (واحد من: مهم، يحتاج ردًا، تخطٍّ) وحقل reason "
        "(سبب بجملة واحدة). المرسلون الذين رفضهم المستخدم مؤخرًا: %s. "
        "القراءة: %s"
        % (", ".join(recent_dismissals or []) or "لا أحد",
           json.dumps(reading, ensure_ascii=False))
    )
    try:
        reply = _call_model(client, prompt, model)
    except Exception as exc:
        raise TriageError("فشل استدعاء نموذج المقرر: %s" % exc)
    data = _extract_json(reply)
    decision = data.get("decision")
    if decision not in DECISIONS:
        raise TriageError("قرار غير معروف من المقرر: %r" % (decision,))
    return {"decision": decision,
            "reason": data.get("reason") or ""}


def triage_item(item, recent_dismissals=None, client=None):
    """فرز عنصر واحد (تعليق/رسالة): قراءة ثم قرار.

    ``item`` قاموس فيه ``id`` و``text`` (و``sender`` اختياريًا
    يُمرَّر للقارئ). يرجع ``{"id", "status", "reading",
    "decision", "reason"}``؛ و``status`` هو القرار أو ``deferred``
    عند أي فشل.
    """
    item_id = item.get("id")
    try:
        reading = read_message(item.get("text", ""), client=client)
        if item.get("sender") and not reading.get("sender"):
            reading["sender"] = item.get("sender")
        verdict = decide(reading, recent_dismissals, client=client)
        return {"id": item_id, "status": verdict["decision"],
                "reading": reading, "decision": verdict["decision"],
                "reason": verdict["reason"]}
    except TriageError as exc:
        return {"id": item_id, "status": DEFERRED,
                "reading": None, "decision": None, "reason": str(exc)}


def triage(items, recent_dismissals=None, client=None):
    """فرز قائمة تعليقات/رسائل؛ كل فشل يؤجل عنصره للفحص التالي."""
    return [triage_item(item, recent_dismissals, client=client)
            for item in items]
