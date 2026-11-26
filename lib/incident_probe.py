#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""حلقة تحقيق في الحوادث — جولة v0.1.60.

المصدر (النمط فقط، بلا نسخ كود أو نصوص): مشروع OpenSRE ‏(Tracer-Cloud/opensre، رخصة Apache-2.0) — حلقة تحقيق تجمع سياقًا مترابطًا وتختبر الفرضيات وتنتج تقريرًا منظمًا بسبب جذري محتمل وأدلة مرتبطة؛ والتنفيذ هنا من الصفر بالمكتبة القياسية من فهم النمط.

الفكرة: `probe_incident(context)` يأخذ سياق حادثة جاهزًا
(نص فشل + تصنيف جاهز + آخر فشل اختبار + تغييرات أخيرة +
حالة بيئة + سجلات مهام مجدولة) ويرجع تقرير تحقيق منظمًا:
سبب جذري محتمل + ثلاث فرضيات مختبَرة + أدلة مرتبطة مجمعة
+ خطوات تالية مرتبة — بلا أي إصلاح وبلا أي أثر جانبي.

قواعد الفرضيات (تُطبَّق حرفيًا، وكل فرضية تبقى في التقرير
حتى بلا دليل — لا تُحذف فرضية أبدًا):
- «بيئة»: تُعلَن supported إن أظهر `env_state` أداة أو حزمة
  مفقودة (melt أو piper أو Pillow أو MCP)، أو وردت فيه
  ملاحظة، أو كان `failure_class` هو environment ومعه نص
  فشل يُقتبس منه. الدليل الأول دائمًا من `env_state`.
- «كود»: تُعلَن supported إن ذكرت `recent_changes` الملف أو
  المنطقة نفسها الواردة في نص الفشل — أي تشارك التغيير مع
  نص الفشل كلمة دالّة واحدة على الأقل بطول 4 أحرف فأكثر، أو
  كلمتين دالّتين فأكثر (الكلمات العامة وكلمات الفشل نفسها
  مثل «فشل» و«اختبار» لا تُحتسب). وإن غاب نص الفشل يُقارَن
  التغيير بآخر فشل اختبار (`last_test_failure`) بالمعيار
  نفسه. الدليل من `recent_changes` ومن نص الفشل.
- «خدمة خارجية»: تُعلَن supported إن كان `failure_class` هو
  external ومعه نص فشل أو آخر فشل اختبار يُقتبس منه.
- أي فرضية بلا دليل مقتبس تبقى untested — ولا فرضية تُعلَن
  supported بلا دليل مقتبس إطلاقًا، حتى لو وافقها التصنيف.
- سجلات المهام المجدولة الفاشلة (`cron_logs` بحالة failed)
  سياق مترابط يُجمع في الأدلة الكلية، ولا تدعم فرضية وحدها.

قواعد عامة:
- الوحدة قراءة فقط تمامًا: لا تنفّذ إصلاحًا ولا تكتب ملفات
  ولا تستدعي أوامر نظام ولا تتصل بشبكة.
- لا تستورد أي وحدة lib أخرى عند الاستيراد — التصنيف
  (`failure_class`) يأتي جاهزًا في السياق، ويركّبه عامل
  التوصيل لاحقًا من `failure_classify` خارج هذه الوحدة.
- لا تعدّل مدخل `context` إطلاقًا: يُنسخ نسخة عميقة أولًا
  ويُعمل على النسخة.
- الاقتباس الواحد ≤ 200 حرف (يُقصّ الأطول مع «…» ضمن الحد).
- `likely_root_cause`: أول فرضية مدعومة بترتيب الأولوية
  بيئة ثم كود ثم خدمة خارجية؛ وبلا فرضية مدعومة يكون
  الصنف unknown والثقة low. الثقة high إن وافق التصنيف
  صنف الفرضية، أو كان لها دليلان فأكثر، أو سمّت أداة
  مفقودة بالاسم؛ وإلا medium.
"""
import copy
import re

__all__ = ["probe_incident"]

_MAX_QUOTE = 200

# أسماء الأدوات في env_state وما يُعرض منها عند فقدانها.
_TOOL_LABELS = (("melt", "melt"), ("piper", "piper"),
                ("pillow_ok", "Pillow"), ("mcp_ok", "MCP"))

# كلمات عامة لا تميّز منطقة فاشلة عن أخرى — تُسقط من
# المقارنة بين التغيير الأخير ونص الفشل.
_STOPWORDS = frozenset((
    "في", "من", "إلى", "على", "أن", "إن", "ما", "لا", "لم", "لن",
    "كان", "كانت", "هو", "هي", "هذا", "هذه", "ذلك", "تلك", "مع",
    "بعد", "قبل", "عند", "بين", "عن", "غير", "كل", "قد", "ثم",
    "أو", "كما", "حتى", "منذ", "أي", "التي", "الذي", "الذين",
    "تم", "يتم", "دون", "نحو", "حول", "ضد", "خلال", "أثناء",
    "لدى", "لدي", "إذ", "إذا", "لكن", "بل", "أما", "هل", "ماذا",
    "كيف", "أين", "متى", "لماذا", "أنه", "أنها", "بأن", "فإن",
    "وأن", "إلا", "سوف", "يكون", "تكون", "هناك", "هنا", "أيضا",
    "فقط", "جدا", "مرة", "مرات", "أول", "آخر", "نفس", "بعض",
    "أحد", "إحدى", "كلما", "حين", "حينما", "عندما", "بينما",
    "رغم", "بالرغم", "منه", "منها", "فيه", "فيها", "عليه",
    "عليها", "إليه", "إليها", "له", "لها", "به", "بها", "منهم",
    "فيهم", "عليهم", "إليهم", "لهم", "بهم", "أنهم", "أنك",
    "أنني", "إنه", "إنها", "كنت", "كنا", "ليس", "ليست",
    # كلمات الفشل نفسها — ظهورها في الطرفين لا يعني أن
    # التغيير في المنطقة الفاشلة.
    "فشل", "فشلت", "فاشل", "فاشلة", "خطأ", "اختبار",
    "اختبارات", "test", "tests", "failed", "failure",
    "error", "errors", "assert", "traceback", "تغيير",
    "تعديل", "تحديث", "إصلاح", "اصلح",
))

_DIACRITICS_RE = re.compile(r"[\u064b-\u0652\u0670\u0640]")
_NORMALIZE_TABLE = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي",
})
_TOKEN_RE = re.compile(r"[0-9a-zA-Z\u0600-\u06FF]+")


def _norm(text):
    """طيّ نص عربي للمقارنة: تشكيل وتطويل وألفات موحّدة."""
    text = _DIACRITICS_RE.sub("", (text or ""))
    return text.translate(_NORMALIZE_TABLE)


def _meaningful_tokens(text):
    """كلمات دالّة من نص: مطبَّعة، بلا كلمات عامة، بطول ≥ 3."""
    tokens = set()
    for raw in _TOKEN_RE.findall(_norm(text).lower()):
        if len(raw) >= 3 and raw not in _STOPWORDS:
            tokens.add(raw)
    return tokens


def _quote(text):
    """اقتباس مقصوص ≤ 200 حرف (الأطول يُقصّ مع «…» ضمن الحد)."""
    text = (text or "").strip()
    if len(text) > _MAX_QUOTE:
        return text[:_MAX_QUOTE - 1] + "…"
    return text


def _as_text(value):
    """نص آمن من قيمة قد تكون غير نصية أو غائبة."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _as_list(value):
    """قائمة آمنة من قيمة قد تكون غير قائمة أو غائبة."""
    if isinstance(value, list):
        return value
    return []


def _as_dict(value):
    """قاموس آمن من قيمة قد تكون غير قاموس أو غائبة."""
    if isinstance(value, dict):
        return value
    return {}


def _matches_change(change, failure_text):
    """هل يذكر التغيير المنطقة نفسها الواردة في نص الفشل؟

    كلمة دالّة مشتركة واحدة بطول 4 أحرف فأكثر، أو كلمتان
    دالّتان مشتركتان فأكثر — فكلمة قصيرة واحدة (مثل «lib»)
    لا تكفي وحدها لإعلان تطابق منطقة.
    """
    shared = _meaningful_tokens(change) & _meaningful_tokens(
        failure_text)
    if not shared:
        return False
    if len(shared) >= 2:
        return True
    return any(len(word) >= 4 for word in shared)


def _missing_tools(env_state):
    """أسماء الأدوات المفقودة في env_state (قيم False فقط)."""
    missing = []
    for key, label in _TOOL_LABELS:
        if key in env_state and env_state[key] is False:
            missing.append(label)
    return missing


def _env_evidence(env_state, failure_class, failure_text):
    """أدلة فرضية البيئة: أدوات مفقودة وملاحظات من env_state،
    وإن خلت env_state من دليل وكان التصنيف environment يُقتبس
    نص الفشل. قائمة فارغة تعني: لا دليل — فتبقى untested."""
    evidence = []
    for label in _missing_tools(env_state):
        evidence.append({"source": "env_state",
                         "quote": "%s مفقود" % label})
    for note in _as_list(env_state.get("notes")):
        text = _as_text(note).strip()
        if text:
            evidence.append({"source": "env_state",
                             "quote": _quote(text)})
    if not evidence and failure_class == "environment" \
            and failure_text.strip():
        evidence.append({"source": "failure_text",
                         "quote": _quote(failure_text)})
    return evidence


def _code_evidence(recent_changes, failure_text, last_failure):
    """أدلة فرضية الكود: أول تغيير يطابق نص الفشل (أو آخر فشل
    اختبار إن غاب نص الفشل) + اقتباس نص الفشل نفسه."""
    effective = failure_text if failure_text.strip() \
        else last_failure
    source = "failure_text" if failure_text.strip() \
        else "last_test_failure"
    if not effective.strip():
        return []
    for change in _as_list(recent_changes):
        text = _as_text(change).strip()
        if text and _matches_change(text, effective):
            evidence = [{"source": "recent_changes",
                         "quote": _quote(text)},
                        {"source": source,
                         "quote": _quote(effective)}]
            if source == "failure_text" and last_failure.strip() \
                    and _matches_change(text, last_failure):
                evidence.append({"source": "last_test_failure",
                                 "quote": _quote(last_failure)})
            return evidence
    return []


def _external_evidence(failure_class, failure_text, last_failure):
    """أدلة فرضية الخدمة الخارجية: تصنيف external مع نص فشل
    أو آخر فشل اختبار يُقتبس منه."""
    if failure_class != "external":
        return []
    if failure_text.strip():
        return [{"source": "failure_text",
                 "quote": _quote(failure_text)}]
    if last_failure.strip():
        return [{"source": "last_test_failure",
                 "quote": _quote(last_failure)}]
    return []


def _cron_evidence(cron_logs):
    """أدلة سجلات المهام المجدولة: كل مهمة بحالة failed."""
    evidence = []
    for entry in _as_list(cron_logs):
        entry = _as_dict(entry)
        if entry.get("last_status") != "failed":
            continue
        name = _as_text(entry.get("cron")).strip() or "مهمة مجدولة"
        evidence.append({"source": "cron_logs",
                         "quote": "%s — آخر تشغيل فاشل" % name})
    return evidence


def _aggregate(all_evidence, failure_text, last_failure, env_state,
               cron_logs):
    """اجمع كل الأدلة المرتبطة بلا تكرار، بالترتيب: نص الفشل
    أولًا، ثم أدلة الفرضيات، ثم آخر فشل اختبار وملاحظات
    البيئة والمهام الفاشلة."""
    seen = set()
    out = []

    def _add(item):
        key = (item.get("source"), item.get("quote"))
        if key not in seen:
            seen.add(key)
            out.append(item)

    if failure_text.strip():
        _add({"source": "failure_text",
              "quote": _quote(failure_text)})
    for item in all_evidence:
        _add(item)
    if last_failure.strip():
        _add({"source": "last_test_failure",
              "quote": _quote(last_failure)})
    for note in _as_list(env_state.get("notes")):
        text = _as_text(note).strip()
        if text:
            _add({"source": "env_state", "quote": _quote(text)})
    for item in _cron_evidence(cron_logs):
        _add(item)
    return out


_NEXT_STEPS = {
    "environment": [
        "أعد تثبيت الأدوات المفقودة أو أعد ربطها حسب سكربت استعادة البيئة.",
        "شغّل فحص الطبيب (doctor) للتحقق من حالة البيئة كاملة.",
        "أعد تشغيل الاختبار الفاشل بعد استعادة البيئة ووثّق نتيجته.",
    ],
    "code": [
        "راجع التغيير الأخير في المنطقة الفاشلة سطرًا سطرًا.",
        "أعد تشغيل الاختبار الفاشل على التغيير وحده لعزله.",
        "أصلح الخلل أو أعد التغيير السابق إن ثبت أنه سببه.",
    ],
    "external": [
        "تحقق من حالة الخدمة الخارجية وحد المعدل المطبق عليها.",
        "أعد المحاولة بعد مهلة قصيرة ووثّق رسالة الحاجز كما ظهرت.",
        "قيّم بديلًا للخدمة إن تكرر الحاجز في المحاولات التالية.",
    ],
    "unknown": [
        "اجمع مزيدًا من السياق: نص الفشل الكامل وآخر تغيير وسجلات المهام.",
        "شغّل فحص الطبيب للتحقق من حالة البيئة.",
        "أعد تشغيل الاختبار الفاشل ووثّق نتيجته بدقة.",
    ],
}

_SUMMARY = {
    "environment": "الأرجح أن أداة مفقودة بعد إعادة تشغيل الجهاز الافتراضي سببت الحادثة.",
    "code": "الأرجح أن تغييرًا أخيرًا في المنطقة الفاشلة سبب الحادثة.",
    "external": "الأرجح أن خدمة خارجية فرضت حاجزًا أو حد معدل فسببت الحادثة.",
    "unknown": "لا يوجد دليل كافٍ لتحديد السبب الجذري المحتمل.",
}


def probe_incident(context):
    """حقّق في حادثة من سياق جاهز وارجع تقرير تحقيق منظمًا.

    `context` قاموس فيه (كلها اختيارية إلا title): title،
    failure_text، failure_class ‏(environment/code/external/
    unknown)، last_test_failure، recent_changes، env_state،
    cron_logs. الناتج قاموس فيه title وlikely_root_cause
    وhypotheses وevidence وnext_steps. قراءة فقط تمامًا،
    ولا يعدّل المدخل.
    """
    # نسخة عميقة أولًا — المدخل لا يُمسّ إطلاقًا.
    ctx = copy.deepcopy(context) if isinstance(context, dict) else {}
    title = _as_text(ctx.get("title")).strip() or "حادثة بلا عنوان"
    failure_text = _as_text(ctx.get("failure_text"))
    failure_class = _as_text(ctx.get("failure_class")).strip() \
        or "unknown"
    last_failure = _as_text(ctx.get("last_test_failure"))
    recent_changes = _as_list(ctx.get("recent_changes"))
    env_state = _as_dict(ctx.get("env_state"))
    cron_logs = _as_list(ctx.get("cron_logs"))

    env_ev = _env_evidence(env_state, failure_class, failure_text)
    code_ev = _code_evidence(recent_changes, failure_text,
                             last_failure)
    ext_ev = _external_evidence(failure_class, failure_text,
                                last_failure)

    hypotheses = [
        {"hypothesis": "بيئة: أداة أو حزمة مفقودة بعد ريستارت",
         "status": "supported" if env_ev else "untested",
         "evidence": env_ev},
        {"hypothesis": "كود: تغيير أخير في المنطقة الفاشلة",
         "status": "supported" if code_ev else "untested",
         "evidence": code_ev},
        {"hypothesis": "خدمة خارجية: حاجز أو حد معدل",
         "status": "supported" if ext_ev else "untested",
         "evidence": ext_ev},
    ]

    # السبب الجذري: أول فرضية مدعومة بترتيب الأولوية
    # بيئة ثم كود ثم خدمة خارجية.
    root_class = "unknown"
    root_evidence = []
    for hyp, cls in ((hypotheses[0], "environment"),
                     (hypotheses[1], "code"),
                     (hypotheses[2], "external")):
        if hyp["status"] == "supported":
            root_class = cls
            root_evidence = hyp["evidence"]
            break

    if root_class == "unknown":
        confidence = "low"
    elif failure_class == root_class \
            or len(root_evidence) >= 2 \
            or (root_class == "environment"
                and _missing_tools(env_state)):
        confidence = "high"
    else:
        confidence = "medium"

    summary = _SUMMARY[root_class]
    if root_class == "environment":
        missing = _missing_tools(env_state)
        if missing:
            summary = ("الأرجح أن %s مفقودة بعد إعادة تشغيل "
                       "الجهاز الافتراضي."
                       % " و".join(missing))

    all_evidence = env_ev + code_ev + ext_ev
    evidence = _aggregate(all_evidence, failure_text, last_failure,
                          env_state, cron_logs)

    return {
        "title": title,
        "likely_root_cause": {
            "class": root_class,
            "summary": summary,
            "confidence": confidence,
        },
        "hypotheses": hypotheses,
        "evidence": evidence,
        "next_steps": list(_NEXT_STEPS[root_class]),
    }
