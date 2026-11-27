#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""تدفق «اطلب فيديو» داخل الاستوديو — الجولة v0.1.43، البند 1.

المستخدم يكتب طلبًا عاديًا (نص قصة كاملة أو موضوع قصير)
والاستوديو يولّد القصة إن لزم، ويحفظها في الطابور، وينتج
الفيديو كاملًا بلا ملفات يدوية.

الطبقات:
- ``classify_request(text)``: قصة كاملة أم موضوع قصير؟
- ``request_to_story(chat_fn, text)``: نص القصة النهائي — كما
  هو إن كان قصة، أو مولّد عبر LLM بنفس أسلوب قصص الصفحة
  إن كان موضوعًا.
- ``request_to_run(...)``: تنسيق واحد — حلّ الطلب → حفظه في
  الطابور → تشغيل خط الإنتاج عبر ``run_fn`` المحقونة.

فصل الاعتماديات عمدًا (لا استيراد لـ studio.py هنا — استيراد
دائري: studio يستورد lib.*):
- سلسلة LLM تصل عبر ``chat_fn(prompt) -> str`` يحقنها المنسّق
  من studio.py (غلاف رقيق فوق ``_llm_chat`` — السلسلة
  الحالية ddgw ← groq ← gemini-3.1-flash-lite ←
  gemini-3-flash-preview ← ollama، بلا إعادة اختراع).
- خط الإنتاج يصل عبر ``run_fn`` يحقنها المنسّق (غلاف فوق
  ``cmd_run`` — script → produce → assemble، بلا تكرار للمنطق).
- حفظ الطابور عبر ``lib.queue.add_story`` مباشرة (وحدة lib
  عادية بلا اعتماد دائري)، وقابل للحقن في الاختبارات.

قاعدة التصنيف (موثّقة وقابلة للاختبار):
- نص طويل (80 كلمة فأكثر) = قصة كاملة مهما كان محتواه.
- نص متوسط (30 كلمة فأكثر) فيه علامتا سرد على الأقل
  (كان/وفي يوم/فقال/ثم/فجأة/عندما...) = قصة كاملة.
- ما دون ذلك = موضوع يريد توليد قصة عنه.

لا ادعاء نجاح أبدًا: فشل توليد القصة (كل مزودي LLM فشلوا)
يرفع ``RequestFlowError`` برسالة عربية واضحة؛ وغياب مشروع
OpenMontage للإنتاج يرفع ``NoProjectError`` فتُحفظ القصة في
الطابور بحالة ``queued`` بدل فيديو وهمي.
"""
import os
import re
import sys

from lib import queue as queue_lib

# ─── حدود التصنيف ───
# قصة كاملة نص طويل عادةً؛ والموضوع جملة قصيرة. الحد الأدنى
# للنص المتوسط يمنع موضوعًا من جملة واحدة فيه علامة سرد
# عابرة (مثل «قصة عن رجل ثم تاب») من أن يُقرأ قصة.
STORY_LONG_WORDS = 80
STORY_MIN_WORDS = 30
STORY_MIN_MARKERS = 2
# أقصر قصة مولّدة مقبولة — دونها يكون مخرج المولّد منحلًا
# (رد فارغ أو جملة يتيمة) لا قصة.
GENERATED_MIN_WORDS = 20

# علامات السرد: كلمات/عبارات لا تظهر عادةً في موضوع قصير،
# وتكثر في نص قصة (أفعال ماضية وحروف عطف زمنية وافتتاحيات
# حكائية). تُقاس العلامات المميزة الموجودة، لا التكرار.
NARRATIVE_MARKERS = (
    "كان ", "كانت ", "وفي يوم", "ذات يوم", "في يوم من الأيام",
    "فقال", "فقالت", "ثم ", "بعدها", "فجأة", "عندما", "بينما",
    "قال ", "قالت ", "عاش ", "عاشت ", "تزوج", "ذهب ", "رجع ",
)

# موجّه توليد القصة من موضوع — نفس أسلوب قصص الصفحة
# (lib/prompts/story_system.md: الهوك جملة واحدة، الراوي رجل،
# المدة 40–60 ثانية، العبرة واضحة، الختام سؤال محيّر).
# موجّه النظام المشترك يصل أصلًا عبر chat_fn (غلاف _llm_chat)،
# فهذا الموجّه يضيف قيود الموضوع فقط.
STORY_GEN_PROMPT = (
    "اكتب قصة قصيرة مؤثرة بأسلوب صفحة فيسبوك «قصص وعبر» عن: "
    "{topic}\n\n"
    "القواعد:\n"
    "- ابدأ بهوك صادم من جملة واحدة يخفي النهاية.\n"
    "- بطل بسيط أمام موقف صعب، وأرقام محددة (سنوات/مبالغ/أيام).\n"
    "- انقلاب/مفاجأة في النهاية، ثم عبرة واضحة.\n"
    "- اختم بسؤال محيّر يفتح النقاش.\n"
    "- سرد 40–60 ثانية عند القراءة (نحو 120–180 كلمة).\n"
    "- اختم القصة بوسم «قصة حقيقية».\n"
    "- نص عربي فقط، بلا مقدمات وبلا شرح خارج القصة."
)

# رسالة فشل التوليد — تُلحق بها تفاصيل الخطأ الأصلي.
LLM_FAILED_MESSAGE = (
    "فشل توليد القصة: كل مزودي الذكاء فشلوا — جرّب لاحقًا أو "
    "تحقق من الشبكة ومن حالة المزودين بـ "
    "`python3 studio.py llm-status`")


class RequestFlowError(Exception):
    """خطأ في تدفق «اطلب فيديو» — رسالته عربية للمستخدم."""


class ApprovalBlockedError(RequestFlowError):
    """رفضت بوابة الموافقة الفعل قبل تنفيذه (جولة v0.1.63).

    .exit_code: 5 عند الرفض (deny أو رفض المستخدم تفاعليًا)،
    و3 حين يحتاج الفعل إجابة بشرية والتشغيل غير تفاعلي
    (سؤال معلّق مسجَّل في runs/approval-decisions.jsonl).
    """

    def __init__(self, message, exit_code=5):
        self.exit_code = exit_code
        super().__init__(message)


class UsageCapError(RequestFlowError):
    """رفض حدود الاستخدام قبل بدء عمل جديد (عقد ع9).

    .status: 429 للعمل غير المراقب، و409 للرسالة المباشرة
    تحت stops=everything؛ و.retry_after: ثوانٍ حتى إعادة
    الضبط؛ و.code: "spend_cap" دائمًا عند الرفض.
    """

    def __init__(self, message, status=429, retry_after=None,
                 code="spend_cap"):
        self.status = status
        self.retry_after = retry_after
        self.code = code
        super().__init__(message)


class NoProjectError(RequestFlowError):
    """لا مشروع OpenMontage للإنتاج — القصة محفوظة في الطابور.

    .queue_number: رقم القصة في الطابور؛ .title: عنوانها.
    يمسكها request_to_run فيحوّل النتيجة إلى حالة «queued»
    بدل الفشل — الفيديو ينتظر تجهيز مشروع، والقصة لم تضع.
    """

    def __init__(self, queue_number, title):
        self.queue_number = queue_number
        self.title = title
        super().__init__(
            "لا يوجد مشروع OpenMontage لهذه القصة بعد — القصة "
            "«%s» محفوظة في الطابور (رقم %d)؛ جهّز مشروعًا ثم "
            "شغّل `studio.py run --story <slug> --project <اسم "
            "المشروع> --out <مسار>` أو أعد الطلب مع --project"
            % (title, queue_number))


def _norm_ws(text):
    """اطوِ كل المسافات البيضاء إلى مسافات مفردة."""
    return re.sub(r"\s+", " ", (text or "")).strip()


# ─── توصيل الموجة ب (جولة v0.1.63): بوابة الموافقة + حدود الاستخدام ───
# الاستيرادات المتقاطعة كسولة داخل الدوال (بلا دورات)، وكل
# فشل في وحدة جديدة يرجع للسلوك الحالي بلا كسر — ما عدا
# أرضية الأمان فهي deny دائمًا.

def _require_approval(action, scope="*"):
    """افحص بوابة الموافقة قبل تنفيذ فعل — قاعدة «بلا تغيير
    سلوك افتراضي» (قرار المنسق الملزم).

    - بلا ملف إعداد (~/.qisas-studio/approval.json غائب):
      allow فورًا بلا أي سؤال — فيبقى سلوك الأوامر والكرونات
      الحالية كما هو.
    - أرضية الأمان (delete_published/spend_money/change_keys/
      delete_project_files): deny دائمًا حتى بلا إعداد.
    - allow ← يمضي؛ وdeny ← ApprovalBlockedError خروج 5؛
    - ask + stdin طرفية ← سؤال تفاعلي (نعم يمضي، وغيرها
      رفض خروج 5)؛ وask + بلا طرفية ← السؤال معلّق مسجَّل
      في runs/approval-decisions.jsonl (تسجله gate.check)
      + ApprovalBlockedError خروج 3 — بلا تعليق أبدًا.
    - أي عطل في وحدة الموافقة ← allow (fail-open للمسار
      القديم، ما عدا أرضية الأمان).
    """
    try:
        from lib import approval as approval_lib
    except Exception:  # noqa: BLE001 — البوابة غائبة = يمضي
        return "allow"
    try:
        if action in getattr(approval_lib, "SAFETY_FLOOR",
                             frozenset()):
            raise ApprovalBlockedError(
                "أرضية الأمان: الفعل «%s» مرفوض دائمًا — لا "
                "موافقة تسمح به" % action, exit_code=5)
        if not os.path.isfile(approval_lib.config_path()):
            return "allow"
        gate = approval_lib.ApprovalGate()
        decision = gate.check(action, scope=scope)
    except ApprovalBlockedError:
        raise
    except Exception:  # noqa: BLE001 — فشل البوابة = يمضي
        return "allow"
    if decision == "allow":
        return "allow"
    if decision == "deny":
        raise ApprovalBlockedError(
            "بوابة الموافقة رفضت الفعل «%s» — اضبط مستوى "
            "الموافقة أو امنح الفعل صراحةً ثم أعد الطلب"
            % action, exit_code=5)
    # ask: تفاعلي فقط حين يكون stdin طرفية.
    try:
        interactive = sys.stdin.isatty()
    except Exception:  # noqa: BLE001 — بلا طرفية = غير تفاعلي
        interactive = False
    if interactive:
        try:
            answer = input(
                "هذا الفعل يحتاج موافقتك — «%s» (نعم/لا): "
                % action).strip().lower()
        except EOFError:
            raise ApprovalBlockedError(
                "الفعل «%s» يحتاج موافقة بشرية — أُغلق الإدخال "
                "قبل الإجابة؛ وسُجّل السؤال المعلّق في "
                "runs/approval-decisions.jsonl" % action,
                exit_code=3)
        except KeyboardInterrupt:
            raise
        if answer in ("نعم", "ن", "yes", "y"):
            return "allow"
        raise ApprovalBlockedError(
            "رفضتَ الفعل «%s» — لم يُنفَّذ شيء" % action,
            exit_code=5)
    raise ApprovalBlockedError(
        "الفعل «%s» يحتاج موافقة بشرية — التشغيل غير تفاعلي "
        "(كرون/اختبار) فسُجّل السؤال المعلّق في "
        "runs/approval-decisions.jsonl؛ أجب عنه ثم أعد الطلب"
        % action, exit_code=3)


def _check_usage_caps(kind="direct"):
    """افحص حدود الاستخدام قبل بدء عمل جديد (عقد ع9).

    يرفع UsageCapError (429/409 برمز spend_cap) عند الرفض.
    أي عطل في وحدة الحدود ← يمضي العمل (fail-open).
    """
    try:
        from lib import usage_caps as caps_lib
    except Exception:  # noqa: BLE001 — الحدود غائبة = بلا حد
        return None
    try:
        result = caps_lib.check(kind)
    except Exception:  # noqa: BLE001 — فشل الفحص = بلا حد
        return None
    if not isinstance(result, dict) or result.get("allowed"):
        return result
    status = result.get("status") or (
        409 if kind == "direct" else 429)
    reason = result.get("reason") or "بُلغ حد الاستخدام"
    raise UsageCapError(
        "بُلغ حد الاستخدام — %s" % reason,
        status=status, retry_after=result.get("retry_after"),
        code=result.get("code") or "spend_cap")


def _word_count(text):
    return len(_norm_ws(text).split())


def _marker_count(text):
    """عدد علامات السرد المميزة الموجودة في النص."""
    flat = " " + _norm_ws(text) + " "
    return sum(1 for m in NARRATIVE_MARKERS if m.strip() and m in flat)


def classify_request(text):
    """صنّف طلبًا: "story" (نص قصة كاملة) أو "topic" (موضوع).

    قاعدة موثّقة (انظر أعلى الملف): طويل (80+ كلمة) = قصة؛
    متوسط (30+ كلمة) بعلامتي سرد على الأقل = قصة؛ ما دون
    ذلك = موضوع. طلب فارغ يرفع ValueError عربيًا.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("الطلب فارغ — اكتب نص قصة أو موضوعًا")
    words = _word_count(text)
    if words >= STORY_LONG_WORDS:
        return "story"
    if words >= STORY_MIN_WORDS \
            and _marker_count(text) >= STORY_MIN_MARKERS:
        return "story"
    return "topic"


def clean_story_text(text):
    """نظّف نص قصة: طيّ الأسطر الفارغة المتتالية، وحذف علامتي
    تنصيص تحيطان بالنص كله (يتيمة من مخرج LLM أحيانًا)."""
    cleaned = (text or "").strip()
    for opener, closer in (("«", "»"), ('"', '"'), ("'", "'")):
        if len(cleaned) >= 2 and cleaned.startswith(opener) \
                and cleaned.endswith(closer):
            cleaned = cleaned[1:-1].strip()
            break
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = "\n".join(line.rstrip() for line in cleaned.splitlines())
    return cleaned.strip()


def extract_title(story_text, max_chars=60):
    """عنوان القصة من جملتها الأولى (للأرشيف والطابور).

    أول جملة على حدود (. / ! / ؟ / سطر)؛ تُقطع عند 60 حرفًا
    على حد كلمة؛ وتُحذف `*` لأن lib.queue يرفضها في العنوان.
    """
    text = clean_story_text(story_text)
    if not text:
        raise ValueError("نص القصة فارغ — لا يمكن استخراج عنوان")
    first = re.split(r"[.!؟\n]+", text, maxsplit=1)[0].strip()
    first = first.replace("*", "").strip()
    if not first:
        raise ValueError("نص القصة فارغ — لا يمكن استخراج عنوان")
    if len(first) > max_chars:
        cut = first[:max_chars].rsplit(" ", 1)[0].strip() or first[:max_chars]
        first = cut.rstrip("،,") + "…"
    return first


def request_to_story(chat_fn, text):
    """حوّل طلبًا إلى نص قصة نهائي.

    قصة كاملة: تُعاد منظفة كما هي (بلا استدعاء LLM).
    موضوع: تُولَّد قصة عبر chat_fn بنفس أسلوب قصص الصفحة.
    فشل LLM أو مخرج فارغ/منحل يرفع RequestFlowError برسالة
    عربية واضحة — لا ادعاء نجاح أبدًا.
    """
    kind = classify_request(text)
    if kind == "story":
        return clean_story_text(text)
    if not callable(chat_fn):
        raise RequestFlowError(
            "لا توجد دالة توليد موصولة (chat_fn) — لا يمكن توليد "
            "قصة من موضوع بلا سلسلة LLM")
    prompt = STORY_GEN_PROMPT.format(topic=text.strip())
    try:
        raw = chat_fn(prompt)
    except RequestFlowError:
        raise
    except Exception as e:
        raise RequestFlowError(
            "%s (%s)" % (LLM_FAILED_MESSAGE, str(e)[:300])) from e
    story = clean_story_text(raw)
    if not story:
        raise RequestFlowError(
            "رجع المولّد نصًا فارغًا — جرّب لاحقًا أو تحقق من "
            "حالة المزودين بـ `python3 studio.py llm-status`")
    if _word_count(story) < GENERATED_MIN_WORDS:
        raise RequestFlowError(
            "القصة المولّدة قصيرة جدًا (%d كلمة) — مخرج منحل من "
            "المولّد؛ جرّب لاحقًا أو بصياغة أخرى للموضوع"
            % _word_count(story))
    return story


def _studio_dir(studio_dir=None):
    """مجلد studio (أب مجلد lib/) — أو الممرَّر صراحةً
    (للاختبار)، مثل lib.scene_plan._studio_dir."""
    if studio_dir:
        return os.path.abspath(os.path.expanduser(studio_dir))
    return os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))


def _default_queue_add(cfg, title, story_text, studio_dir=None):
    """احفظ القصة في الطابور عبر lib.queue.add_story.

    يرجع {"number", "title", "text_file"} كما يرجع add_story.
    مسار ملف الطابور من cfg["paths"]["queue_file"]، ومجلد نصوص
    القصص studio/queue (كما في cmd_queue_add). أي رفض من
    الطابور (عنوان مكرر/نص فارغ) يرفع RequestFlowError.
    """
    try:
        queue_path = os.path.expanduser(os.path.expandvars(str(
            (cfg or {}).get("paths", {}).get("queue_file") or "")))
    except Exception:
        queue_path = ""
    if not queue_path:
        raise RequestFlowError(
            "مسار ملف الطابور غير مضبوط في الإعدادات "
            "(paths.queue_file) — لا يمكن حفظ القصة")
    stories_dir = os.path.join(_studio_dir(studio_dir), "queue")
    try:
        return queue_lib.add_story(
            queue_path, title, story_text,
            note="طلب فيديو (studio.py request)",
            stories_dir=stories_dir)
    except queue_lib.QueueError as e:
        raise RequestFlowError(
            "تعذّر حفظ القصة في الطابور: %s" % e) from e


def _print_plan(print_fn, result):
    """اطبع خطة الطلب (لـ --dry-run وللتأكيد قبل الإنتاج)."""
    kind_label = "قصة كاملة" if result["kind"] == "story" \
        else "موضوع (توليد قصة)"
    print_fn("== طلب فيديو — %s ==" % result["title"])
    print_fn("النوع: %s — الكلمات: %d"
             % (kind_label, result["story_words"]))
    print_fn("الطابور: رقم %s"
             % (result["queue_number"]
                if result["queue_number"] is not None else "—"))
    print_fn("المشروع: %s"
             % (result["project"] or "بلا مشروع بعد"))
    print_fn("المخرج: %s" % (result["out_path"] or "—"))
    print_fn("الحالة: %s" % result["status"])


def request_to_run(cfg, text, chat_fn, out_path, run_fn=None,
                   project=None, dry_run=False, allow_fallback=False,
                   queue_add_fn=None, studio_dir=None,
                   print_fn=None, approval_action="produce_video",
                   approval_scope="*", usage_kind="direct",
                   check_usage_caps=True):
    """نسّق طلب فيديو كاملًا: حلّ الطلب → حفظه في الطابور →
    تشغيل خط الإنتاج. يرجع قاموس النتيجة.

    المعاملات:
    - cfg: إعدادات الاستوديو (لمسار الطابور فقط هنا).
    - text: الطلب كما كتبه المستخدم (نص قصة أو موضوع).
    - chat_fn(prompt) -> str: سلسلة LLM (يحقنها المنسّق من
      studio.py — غلاف فوق _llm_chat). تُستدعى للموضوع فقط.
    - out_path: مسار الفيديو النهائي المطلوب.
    - run_fn(cfg, story_text, title, project, out_path,
      allow_fallback, queue_number) -> str: خط الإنتاج
      (يحقنه المنسّق — غلاف فوق cmd_run). يرجع مسار الفيديو
      النهائي، ويرفع RequestFlowError عند الفشل، ويرفع
      NoProjectError عند غياب مشروع OpenMontage.
    - project: اسم مشروع OpenMontage الجاهز (اختياري — بلا
      مشروع تُحفظ القصة في الطابور فقط إن غاب run_fn أو رفع
      NoProjectError).
    - dry_run: اطبع الخطة فقط بلا حفظ وبلا إنتاج.
    - allow_fallback: يُمرَّر لخط الإنتاج كما في `run`.
    - queue_add_fn(cfg, title, story_text, studio_dir) ->
      {"number", ...}: للحقن في الاختبارات (الافتراضي حفظ
      حقيقي في الطابور).
    - studio_dir: مجلد studio لحفظ نص القصة (للاختبار).
    - print_fn: للحقن في الاختبارات (الافتراضي print).
    - approval_action: فعل بوابة الموافقة قبل تشغيل الإنتاج
      (الافتراضي "produce_video"؛ وNone يلغي البوابة).
      بلا ملف إعداد موافقة يمضي الإنتاج بلا سؤال؛ وdeny
      يرفع ApprovalBlockedError خروج 5 قبل أي إنتاج؛ وask
      غير التفاعلي يرفع خروج 3 (سؤال معلّق مسجَّل).
    - approval_scope: نطاق فعل الموافقة (الافتراضي "*").
    - usage_kind: نوع الفحص في حدود الاستخدام (الافتراضي
      "direct" — طلب مستخدم مباشر يعمل دائمًا تحت
      stops=unattended)؛ وcheck_usage_caps=False يلغي فحص
      الحدود. الفحص قبل بدء العمل الجديد فقط (الدور الجاري
      يُكمل)، ويرفع UsageCapError بأسلوب API عند الرفض.
    - dry_run: يطبع الخطة فقط بلا حفظ وبلا إنتاج — وبلا
      أي فحص بوابة/حدود (لا فعل يُنفَّذ).

    النتيجة: {"kind", "title", "story_text", "story_words",
    "project", "out_path", "queue_number", "output", "status"}؛
    وstatus إحدى: "done" (فيديو جاهز) أو "queued" (القصة في
    الطابور بلا فيديو — بلا مشروع أو بلا run_fn) أو "dry-run".
    فشل التوليد أو الحفظ أو الإنتاج يرفع RequestFlowError —
    لا مسار فيديو وهمي أبدًا.
    """
    printf = print_fn or print
    kind = classify_request(text)
    # حدود الاستخدام قبل بدء العمل الجديد (التوليد ثم
    # الإنتاج) — لا في dry-run (خطة بلا فعل يُنفَّذ).
    if not dry_run and check_usage_caps:
        _check_usage_caps(usage_kind)
    story_text = request_to_story(chat_fn, text)
    title = extract_title(story_text)
    result = {
        "kind": kind,
        "title": title,
        "story_text": story_text,
        "story_words": _word_count(story_text),
        "project": project,
        "out_path": out_path,
        "queue_number": None,
        "output": None,
        "status": "dry-run" if dry_run else "queued",
    }
    if dry_run:
        _print_plan(printf, result)
        return result
    add = queue_add_fn or _default_queue_add
    try:
        saved = add(cfg, title, story_text, studio_dir)
    except RequestFlowError:
        raise
    except Exception as e:
        raise RequestFlowError(
            "تعذّر حفظ القصة في الطابور: %s" % e) from e
    result["queue_number"] = saved.get("number")
    printf("أُضيفت القصة رقم %d إلى الطابور: %s"
           % (saved.get("number"), title))
    if run_fn is None:
        printf("بلا مسار إنتاج موصول — القصة محفوظة في الطابور "
               "بانتظار مشروع OpenMontage.")
        _print_plan(printf, result)
        return result
    # بوابة الموافقة قبل تنفيذ الإنتاج (الفعل المكلف) — بعد
    # حفظ القصة في الطابور (كالرفض عند غياب المشروع: القصة
    # محفوظة ولا فيديو وهمي). بلا ملف إعداد يمضي بلا سؤال.
    if approval_action is not None:
        _require_approval(approval_action, scope=approval_scope)
    try:
        out = run_fn(cfg, story_text, title, project, out_path,
                     allow_fallback, saved.get("number"))
    except NoProjectError as e:
        printf(str(e))
        _print_plan(printf, result)
        return result
    except RequestFlowError:
        raise
    except Exception as e:
        raise RequestFlowError(
            "فشل خط الإنتاج: %s" % e) from e
    if not out or not isinstance(out, str):
        raise RequestFlowError(
            "انتهى الإنتاج بلا مسار فيديو — راجع سجل التشغيل")
    result["output"] = out
    result["status"] = "done"
    printf("صُدّر الفيديو: %s" % out)
    _print_plan(printf, result)
    return result
