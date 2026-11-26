#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""توسيع موجّه الحركة القصير — جولة v0.1.54 (تطبيق الأفضل
من مسح TAAFT، عامل W1).

نموذج لغوي يملكه الاستوديو يوسّع موجّه الحركة القصير بتفاصيل
الكاميرا والحركة والإضاءة والمزاج قبل إرساله إلى Wan/LTX.
خطوة اختيارية صريحة، fail-open، صفر GPU: أي فشل — حصة
ممتلئة، شبكة، رد فارغ أو طويل جدًا أو مسقِط لمحتوى الأصل —
يرجع الموجّه الأصلي كما هو مع `expanded=False` وسبب عربي،
بلا رفع استثناء أبدًا (عدا مدخل فارغ/غير نصي فيرفع
ValueError).

الاستدعاء الافتراضي عبر
`omniroute_client.chat_free_rotation` على قائمة التناوب
المجاني المثبّتة، مع فحص الحصة قبل الاستدعاء عبر
`llm_state.can_call` (النموذج فوق حدّه لا يُستدعَى أصلًا)
وتسجيل كل محاولة عبر `on_attempt` بنفس نمط
`studio._llm_chat` (record_attempt + حفظ الحالة).

الموجّه الموسَّع يُتحقَّق منه قبل قبوله: غير فارغ، وطوله
≤ ‏600 حرف (سقف موثّق هنا)، ويحفظ الكلمات المفتاحية
للموجّه الأصلي (تغطية ≥ 60%، وكلها إن كانت ≤ كلمتين)،
وفقرة واحدة. بلا طباعة قيم مفاتيح أبدًا؛ بلا اعتماديات
جديدة؛ تنفيذ بايثون من الصفر.
"""
import re

from lib import llm_state
from lib import omniroute_client

# النماذج الافتراضية: قائمة التناوب المجاني المثبّتة من
# omniroute_client (لا تنقص أبدًا — اكتشاف حي يضيف عليها
# ولا يحذف منها، وإن فشل الاكتشاف رجعت هي وحدها)، ثم
# الساق العاملة في الخط اليومي كبديل: `ddgw/gpt-5.4-mini`
# (متحقق حيًا 2026-11-26 — يرد عبر chat_free_rotation؛
# و`openrouter/free` وحده غير كافٍ: بوابة OmniRoute بلا
# مزود OpenRouter مهيأ بعد — مفتاحه لم يُحفظ أصلًا — فيفشل
# كل استدعاء بـLLMAllFailedError وتبقى الميزة معطلة عمليًا
# رغم fail-open؛ إصلاح دمج المنسق). الترتيب مقصود: المسبح
# المجاني أولًا (لا يستهلك ساق الخط اليومي عند اتصاله)،
# وddgw بديل عامل — بلا مزود جديد وبلا مفتاح جديد.
DEFAULT_MODELS = tuple(omniroute_client.PINNED_FREE_MODELS) + (
    "ddgw/gpt-5.4-mini",)

# سقف طول الموجّه الموسَّع (حرفًا): موجّه حركة لـWan/LTX
# فقرة واحدة — فوقه يُرفض ويُرجع الأصل (fail-open)، لا
# يُقصّ حتى لا ينقطع منتصف جملة.
MAX_EXPANDED_CHARS = 600

# أقل تغطية للكلمات المفتاحية في الموسَّع (60%): دونها
# يُعتبر الموسَّع مسقِطًا لمحتوى الأصل فيُرفض.
MIN_KEYWORD_COVERAGE = 0.6

DEFAULT_MAX_TOKENS = 300

# الموجّه النظامي للتوسيع (بالإنجليزية): يوسّع التفاصيل
# البصرية فقط — كاميرا/حركة/إضاءة/مزاج/استمرارية المشهد.
# ممنوع تغيير محتوى القصة أو الشخصيات أو إضافة/حذف ضربات
# سردية؛ فقرة واحدة.
EXPAND_SYSTEM_PROMPT = (
    "Expand the short motion prompt into one single paragraph "
    "of visual detail only: camera framing and movement, "
    "subject motion, lighting, and mood, keeping the scene "
    "continuous with the original shot. Do not change the "
    "story content, the characters, or the setting, and do "
    "not add or remove any narrative beats. Output only the "
    "expanded prompt, one paragraph, no explanations."
)

# كلمات وظيفية تُستبعَد من الكلمات المفتاحية (إنجليزية
# وعربية) — لا تحمل محتوى بصريًا فيُقاس الحفظ بدونها.
_STOPWORDS = frozenset("""
a an the and or of to in on at by with from for as is are was were
be been it its his her their he she they this that these those
then than so but not no very
في من إلى على و ثم بعد قبل أن إن ما لا هو هي كان كانت يكون تكون
""".split())

_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def _stem(token):
    """جذر تقريبي للكلمة (إنجليزي فقط): يحذف لاحقة صرفية
    واحدة (s/es/ed/ing/ly) ليطابق walk/walks/walking."""
    word = (token or "").lower()
    if word.endswith("'s"):
        word = word[:-2]
    if len(word) > 4:
        for suffix in ("ing", "ed", "ly", "es"):
            if word.endswith(suffix):
                word = word[: -len(suffix)]
                break
        else:
            if word.endswith("s"):
                word = word[:-1]
    return word


def _keywords(prompt):
    """الكلمات المفتاحية للموجّه: رموز بطول ≥ 3 بلا كلمات
    وظيفية، بلا تكرار، بالترتيب."""
    seen = set()
    words = []
    for token in _TOKEN_RE.findall(prompt or ""):
        word = token.lower()
        if len(word) < 3 or word in _STOPWORDS:
            continue
        if word not in seen:
            seen.add(word)
            words.append(word)
    return words


def _keyword_kept(keyword, expanded_lower):
    """هل بقيت الكلمة المفتاحية في الموسَّع؟ مطابقة جذر
    كامل أو بادئة (بطول ≥ 4) تغطي التصريف والجمع."""
    stem = _stem(keyword)
    for token in _TOKEN_RE.findall(expanded_lower):
        other = _stem(token)
        if stem == other:
            return True
        if len(stem) >= 4 and len(other) >= 4 and (
                other.startswith(stem) or stem.startswith(other)):
            return True
    return False


def _validate_expanded(original, expanded):
    """تحقَّق من الموسَّع: يرجع (مقبول؟، السبب العربي).

    غير فارغ، و≤ ‏600 حرف، ويحفظ الكلمات المفتاحية،
    ومختلف عن الأصل (إعادة الأصل حرفيًا ليست توسيعًا).
    """
    if not isinstance(expanded, str) or not expanded.strip():
        return False, "ردّ النموذج فارغًا — أُعيد الموجّه الأصلي كما هو"
    text = " ".join(expanded.split())
    if len(text) > MAX_EXPANDED_CHARS:
        return False, ("الموجّه الموسَّع أطول من الحدّ (%d حرف) — "
                       "أُعيد الموجّه الأصلي كما هو"
                       % MAX_EXPANDED_CHARS)
    if text.strip().lower() == original.strip().lower():
        return False, ("أعاد النموذج الموجّه نفسه بلا تفاصيل "
                       "إضافية — أُعيد الموجّه الأصلي كما هو")
    keywords = _keywords(original)
    if keywords:
        kept = sum(1 for word in keywords
                   if _keyword_kept(word, text.lower()))
        needed = (len(keywords) if len(keywords) <= 2
                  else max(1, int(len(keywords)
                                  * MIN_KEYWORD_COVERAGE + 0.999)))
        # ‎+0.999: تقريب لأعلى — 60% من 5 كلمات = 3 كلمات.
        if kept < needed:
            return False, ("الموجّه الموسَّع أسقط محتوى من الأصل "
                           "(حفظ %d من %d كلمة مفتاحية) — أُعيد "
                           "الموجّه الأصلي كما هو" % (kept,
                                                      len(keywords)))
    return True, None


def _on_attempt_recorder(state, runs_dir):
    """on_attempt بنمط studio._llm_chat: سجّل كل محاولة
    (نجاح/فشل + تهدئة الحصة) واحفظ الحالة إن وُجد runs_dir."""
    def on_attempt(provider, ok, kind):
        llm_state.record_attempt(state, provider, ok, kind)
        if runs_dir:
            try:
                llm_state.save_state(state, runs_dir)
            except OSError:
                pass
    return on_attempt


def _default_chat(short_prompt, system, max_tokens, state, runs_dir):
    """الاستدعاء الافتراضي عبر تناوب المسار المجاني.

    يرجع نص الرد (العنصر الأول من (نص، مسار، موديل)).
    """
    result = omniroute_client.chat_free_rotation(
        short_prompt, list(DEFAULT_MODELS), system=system,
        max_tokens=max_tokens, state=state,
        on_attempt=_on_attempt_recorder(state, runs_dir))
    if isinstance(result, (tuple, list)):
        return result[0] if result else ""
    return result


def expand_motion_prompt(short_prompt, *, chat_fn=None, state=None,
                         runs_dir=None, max_tokens=300):
    """وسّع موجّه حركة قصيرًا بتفاصيل بصرية (كاميرا/حركة/
    إضاءة/مزاج) عبر نموذج لغوي يملكه الاستوديو.

    short_prompt: الموجّه القصير (نص غير فارغ — وإلا
    ValueError). chat_fn (اختياري): دالة قابلة للحقن في
    الاختبارات — chat_fn(prompt, system=..., max_tokens=...)
    ترجع نصًا (أو (نص، ...) فيُؤخذ أوله)؛ وبلاها يُستدعَى
    تناوب المسار المجاني. state (اختياري): حالة llm_state؛
    وبلاها تُحمَّل بـ llm_state.load_state(runs_dir).
    max_tokens: حد رموز الرد (افتراضيًا 300؛ قيمة غير صالحة
    ترجع للافتراضي).

    يرجع {"prompt": str, "expanded": bool, "reason": str|None}:
    عند النجاح prompt هو الموسَّع وexpanded=True وreason=None؛
    وعند أي فشل آخر prompt هو الأصل كما هو وexpanded=False
    وreason عربي — بلا رفع استثناء.
    """
    if not isinstance(short_prompt, str) \
            or not short_prompt.strip():
        raise ValueError("موجّه الحركة فارغ أو غير نصي")
    original = short_prompt.strip()
    try:
        tokens = max_tokens
        if isinstance(tokens, bool) or not isinstance(tokens, int) \
                or tokens <= 0:
            tokens = DEFAULT_MAX_TOKENS
    except (TypeError, ValueError):
        tokens = DEFAULT_MAX_TOKENS
    try:
        if state is None:
            state = llm_state.load_state(runs_dir)
        # فحص الحصة قبل الاستدعاء — النموذج فوق حدّه لا
        # يُستدعَى أصلًا (نمط _run_attempts نفسه: can_call
        # لكل (مزود، موديل) قبل محاولته).
        denials = []
        for model in DEFAULT_MODELS:
            allowed, reason, _retry = llm_state.can_call(
                state, model, model=model, est_tokens=0)
            if not allowed:
                denials.append(reason or "quota")
        if len(denials) == len(DEFAULT_MODELS):
            return {"prompt": original, "expanded": False,
                    "reason": "الحصة ممتلئة لكل نماذج التوسيع "
                              "(%s) — أُعيد الموجّه الأصلي كما هو"
                              % (denials[0] if denials else "quota")}
        if chat_fn is not None:
            raw = chat_fn(original, system=EXPAND_SYSTEM_PROMPT,
                          max_tokens=tokens)
        else:
            raw = _default_chat(original, EXPAND_SYSTEM_PROMPT,
                                tokens, state, runs_dir)
        if isinstance(raw, (tuple, list)):
            raw = raw[0] if raw else ""
        if not isinstance(raw, str):
            return {"prompt": original, "expanded": False,
                    "reason": "ردّ النموذج ليس نصًا — أُعيد الموجّه "
                              "الأصلي كما هو"}
        expanded = " ".join(raw.split())
        ok, reason = _validate_expanded(original, expanded)
        if not ok:
            return {"prompt": original, "expanded": False,
                    "reason": reason}
        return {"prompt": expanded, "expanded": True, "reason": None}
    except Exception as exc:  # fail-open: أي فشل آخر
        # السبب بنوع الخطأ فقط — بلا نص رسالة قد يحمل
        # تفاصيل حساسة (مفاتيح/عناوين).
        return {"prompt": original, "expanded": False,
                "reason": "تعذّر توسيع الموجّه (%s) — أُعيد الموجّه "
                          "الأصلي كما هو" % type(exc).__name__}


def expand_motion_prompts(items, **kwargs):
    """وسّع دفعة موجّهات: items: [{"id": str?, "prompt": str}].

    يرجع [{"id", "prompt", "expanded_prompt", "expanded",
    "reason"}] بنفس ترتيب المدخل؛ فشل عنصر واحد (موجّه
    فارغ، حصة، شبكة...) لا يكسر باقي الدفعة — يرجع العنصر
    الفاشل بموجّهه الأصلي وexpanded=False وسبب عربي.
    **kwargs تُمرَّر إلى expand_motion_prompt (chat_fn/
    state/runs_dir/max_tokens).
    """
    if not isinstance(items, list):
        raise ValueError("الدفعة يجب أن تكون قائمة عناصر")
    results = []
    for item in items:
        if not isinstance(item, dict):
            results.append({"id": None, "prompt": "",
                            "expanded_prompt": "", "expanded": False,
                            "reason": "عنصر الدفعة غير صالح"})
            continue
        item_id = item.get("id")
        prompt = item.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            results.append({"id": item_id, "prompt":
                            prompt if isinstance(prompt, str) else "",
                            "expanded_prompt":
                            prompt if isinstance(prompt, str) else "",
                            "expanded": False,
                            "reason": "موجّه العنصر فارغ أو غير نصي"})
            continue
        try:
            result = expand_motion_prompt(prompt, **kwargs)
        except Exception as exc:  # دفاع أخير — لا يكسر الدفعة
            results.append({"id": item_id, "prompt": prompt,
                            "expanded_prompt": prompt,
                            "expanded": False,
                            "reason": "تعذّر توسيع الموجّه (%s) — "
                                      "أُعيد الموجّه الأصلي كما هو"
                                      % type(exc).__name__})
            continue
        results.append({"id": item_id, "prompt": prompt,
                        "expanded_prompt": result["prompt"],
                        "expanded": result["expanded"],
                        "reason": result["reason"]})
    return results
