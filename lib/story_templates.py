#!/usr/bin/env python3
"""قوالب بنية قصة — `lib/story_templates.py` (الجولة v0.1.39).

قوالب جاهزة (هوك/تصعيد/انقلاب/عبرة) لثلاثة محاور مثبتة النجاح
عند صفحة «قصص وعبر» (من تحليل الصفحات المشهورة 2026-11-20
والمقارنة 2026-11-23، القسم 4.11 — قوالب Storyflick):

- ``relatives_injustice``: ظلم الأقارب والحماة.
- ``parents``: برّ/عقوق الوالدين.
- ``honesty_charity``: أمانة/صدقة.

`build_scene_outline(template, title, hero, situation, moral=None,
clips=6)` يرجع مخطط مشاهد: كل مشهد جملة سرد واحدة (8 ثوانٍ،
كأي مشهد في `lib/scene_plan.py`) مع طوره (هوك/تصعيد/انقلاب/
عبرة)؛ والمشهد الأول هوك دائمًا والأخير عبرة دائمًا.
`render_story_text(outline)` يجمع المخطط نص سرد واحدًا يصلح
ملف نص قصة (`queue add --text-file`).

القواعد الدائمة سارية على كل قالب: الراوي رجل، والهوك جملة
واحدة صادمة تخفي النهاية، والمدة 40–60 ثانية، والعبرة واضحة،
والختام سؤال محيّر — انظر `lib/prompts/story_system.md`.

ثنائية اللغة (الجولة v0.1.41): لكل قالب عربي قالب إنجليزي
موازٍ بنفس المفاتيح وبنية الأطوار نفسها (هوك صادم من جملة
واحدة، بطل بسيط، أرقام محددة، انقلاب في النهاية، عبرة
واضحة) في `TEMPLATES_EN`؛ و`get_template` /
`build_scene_outline` / `list_templates` تقبل `lang="ar"|"en"`
(العربي افتراضيًا دائمًا). `set_template_lang` يضبط لغة
القالب الافتراضية للعملية كلها — وهو الجسر الذي يستخدمه
`studio.py` لخيار `scene-plan --template-lang`، لأن
`lib/scene_plan.py` يستدعي `build_scene_outline` بلا
وسيط لغة (خارج هذه الحزمة فلا يُلمس): القيمة الافتراضية
`ar`، ويعيدها `studio.py` كما كانت بـ try/finally بعد
بناء الخطة.
"""
import re

# لغة القالب الافتراضية للعملية (ar دائمًا ما لم يضبطها
# studio.py مؤقتًا لأمر scene-plan --template-lang).
_DEFAULT_TEMPLATE_LANG = "ar"


def set_template_lang(lang):
    """اضبط لغة القالب الافتراضية للعملية (ar/en)؛
    قيمة غير معروفة ترفع ValueError عربيًا."""
    global _DEFAULT_TEMPLATE_LANG
    head = (lang or "").strip().lower()[:2] \
        if isinstance(lang, str) else ""
    if head not in ("ar", "en"):
        raise ValueError("لغة قالب غير معروفة: %s (المتاح: ar, en)"
                         % (lang,))
    _DEFAULT_TEMPLATE_LANG = head
    return head


def get_template_lang():
    """لغة القالب الافتراضية الحالية للعملية."""
    return _DEFAULT_TEMPLATE_LANG


def _norm_template_lang(lang):
    if lang is None:
        return _DEFAULT_TEMPLATE_LANG
    head = (lang or "").strip().lower()[:2] \
        if isinstance(lang, str) else ""
    if head not in ("ar", "en"):
        raise ValueError("لغة قالب غير معروفة: %s (المتاح: ar, en)"
                         % (lang,))
    return head

CLIP_SECONDS = 8
MIN_CLIPS = 1
MAX_CLIPS = 12

BEAT_LABELS = {
    "hook": "هوك",
    "escalation": "تصعيد",
    "twist": "انقلاب",
    "moral": "عبرة",
}

BEAT_LABELS_EN = {
    "hook": "Hook",
    "escalation": "Escalation",
    "twist": "Twist",
    "moral": "Moral",
}

# القوالب الإنجليزية الموازية (الجولة v0.1.41): نفس مفاتيح
# القوالب العربية وبنية الأطوار نفسها، بهوك صادم من جملة
# واحدة وبطل بسيط وأرقام محددة وانقلاب وعبرة واضحة.
TEMPLATES_EN = {
    "relatives_injustice": {
        "label": "Injustice by relatives and in-laws",
        "description": ("A simple hero is wronged by a relative or a "
                        "mother-in-law, endures it, then the wrong "
                        "turns back on its owner and the truth comes out."),
        "default_moral": ("Injustice never lasts — sooner or later, "
                          "the truth comes out."),
        "closing_question": "If you were in {hero}'s place, what would you do?",
        "beats": {
            "hook": ("{hero} {situation} — and in a single night, "
                     "everything turned upside down."),
            "escalation": ("The injustice grew day after day for 3 long "
                           "years, and {hero} stayed silent while "
                           "everyone watched and said nothing."),
            "twist": ("And just when everyone thought the truth was "
                      "lost forever, one piece of evidence — a letter "
                      "written 7 years earlier — turned everything "
                      "upside down."),
            "moral": "The lesson: {moral}",
        },
    },
    "parents": {
        "label": "Honoring / disobeying parents",
        "description": ("A son drifts away from his parents, then one "
                        "moment teaches him the value of what he lost."),
        "default_moral": ("Honoring your parents opens a door to "
                          "Paradise, and disobeying them is a debt "
                          "repaid in this life before the next."),
        "closing_question": ("When was the last time you said a kind "
                             "word to your father or your mother?"),
        "beats": {
            "hook": ("{hero} {situation} — and he had no idea that "
                     "night would change his whole life."),
            "escalation": ("The distance between him and his parents "
                           "grew — 10 years passed, and every day the "
                           "gap widened and the regret grew heavier."),
            "twist": ("Then one phone call changed everything — he ran "
                      "back home, and finally understood the value of "
                      "what he had lost."),
            "moral": "The lesson: {moral}",
        },
    },
    "honesty_charity": {
        "label": "Honesty / charity",
        "description": ("A poor man finds something entrusted to him, "
                        "returns it despite his need, and the reward "
                        "comes."),
        "default_moral": ("Honesty is never lost with God — whoever "
                          "gives something up for God is repaid with "
                          "better."),
        "closing_question": ("If you found a large sum of money that "
                             "wasn't yours, what would you do?"),
        "beats": {
            "hook": ("{hero} {situation} — and he faced one choice: "
                     "take what was not his, or return it."),
            "escalation": ("Poverty pressed him from every side, and "
                           "the temptation grew — he had only $20 left "
                           "in his pocket, but his conscience stayed "
                           "awake."),
            "twist": ("He returned the wallet with its $5,000 to its "
                      "owner despite his poverty — and days later, the "
                      "reward came from where he least expected it."),
            "moral": "The lesson: {moral}",
        },
    },
}

TEMPLATES = {
    "relatives_injustice": {
        "label": "ظلم الأقارب والحماة",
        "description": ("بطل بسيط يظلمه قريب أو حماة، يصبر، ثم "
                        "ينقلب الظلم على صاحبه ويظهر الحق."),
        "default_moral": "الظلم مهما طال ليله، الحق بيظهر في الآخر.",
        "closing_question": "لو كنت مكان {hero}، كنت هتعمل إيه؟",
        "beats": {
            "hook": ("{hero} {situation} — وفي ليلة واحدة، انقلب "
                     "كل شيء رأسًا على عقب."),
            "escalation": ("زاد الظلم يومًا بعد يوم، و{hero} صبر "
                           "وسكت، والناس كلها شايفة وساكتة."),
            "twist": ("وفي اللحظة اللي الكل افتكر إن الحق ضاع، ظهر "
                      "دليل واحد قلب الموازين كلها."),
            "moral": "العبرة: {moral}",
        },
    },
    "parents": {
        "label": "برّ/عقوق الوالدين",
        "description": ("ابن يبتعد عن أهله أو يعقّ والديه، ثم موقف "
                        "واحد يعلّمه قيمة ما ضيّعه."),
        "default_moral": ("برّ الوالدين باب من أبواب الجنة، وعقوقهما "
                          "دين يُردّ في الدنيا قبل الآخرة."),
        "closing_question": "إمتى آخر مرة قلت لأبوك أو لأمك كلمة حلوة؟",
        "beats": {
            "hook": ("{hero} {situation} — وما كانش يعرف إن الليلة "
                     "دي هتغيّر حياته كلها."),
            "escalation": ("كبرت المسافة بينه وبين أهله، وكل يوم "
                           "يعدّي كان البعد بيزيد والندم بيكبر."),
            "twist": ("وفي عزّ البعد، جاله خبر واحد خلّاه يرجع جري "
                      "— ويفهم أخيرًا قيمة اللي ضيّعه."),
            "moral": "العبرة: {moral}",
        },
    },
    "honesty_charity": {
        "label": "أمانة/صدقة",
        "description": ("فقير تقع في يده أمانة أو مال ليس له، "
                        "فيرجعها رغم حاجته، فيأتيه العوض."),
        "default_moral": ("الأمانة لا تضيع عند الله، ومن ترك شيئًا "
                          "لله عوّضه الله خيرًا منه."),
        "closing_question": "لو لقيت مبلغ كبير مش بتاعك، هتعمل إيه؟",
        "beats": {
            "hook": ("{hero} {situation} — وكان قدامه اختيار واحد: "
                     "ياخد اللي مش من حقه، أو يرجّعه."),
            "escalation": ("الفقر ضغط عليه من كل ناحية، والإغراء "
                           "كبر، لكن ضميره كان صاحي."),
            "twist": ("رجّع الأمانة لصاحبها رغم فقره — وبعدها بأيام، "
                      "جاله العوض من حيث لا يحتسب."),
            "moral": "العبرة: {moral}",
        },
    },
}


def list_templates(lang=None):
    """قائمة القوالب: [(الاسم، التسمية)] بالترتيب، بلغة معطاة
    (العربي افتراضيًا)."""
    lang = _norm_template_lang(lang)
    table = TEMPLATES_EN if lang == "en" else TEMPLATES
    return [(name, table[name]["label"]) for name in table]


def get_template(name, lang=None):
    """ارجع نسخة من قالب باسمه ولغته؛ ValueError إن لم يوجد
    (عربي افتراضيًا، إنجليزي مع lang="en")."""
    lang = _norm_template_lang(lang)
    table = TEMPLATES_EN if lang == "en" else TEMPLATES
    template = table.get((name or "").strip())
    if template is None:
        if lang == "en":
            raise ValueError(
                "Unknown story template: «%s» — available: %s"
                % (name, ", ".join(table)))
        raise ValueError(
            "قالب قصة غير معروف: «%s» — المتاح: %s"
            % (name, ", ".join(table)))
    return {
        "name": (name or "").strip(),
        "lang": lang,
        "label": template["label"],
        "description": template["description"],
        "default_moral": template["default_moral"],
        "closing_question": template["closing_question"],
        "beats": dict(template["beats"]),
    }


def _require_text(value, what):
    text = (value or "").strip() if isinstance(value, str) else ""
    if not text:
        raise ValueError("%s فارغ — لا يمكن بناء مخطط مشاهد" % what)
    return text


def _beats_for_clips(clips):
    """أطوار المشاهد لعدد مقاطع معطى: الأول هوك والأخير عبرة.

    1: [هوك]؛ 2: [هوك، عبرة]؛ 3: [هوك، انقلاب، عبرة]؛
    4 فأكثر: هوك، ثم تصعيد في النصف الأول من الوسط، ثم
    انقلاب في النصف الثاني، ثم عبرة.
    """
    if clips == 1:
        return ["hook"]
    if clips == 2:
        return ["hook", "moral"]
    if clips == 3:
        return ["hook", "twist", "moral"]
    middle = clips - 2
    esc_count = (middle + 1) // 2
    return (["hook"] + ["escalation"] * esc_count
            + ["twist"] * (middle - esc_count) + ["moral"])


def build_scene_outline(template, title, hero, situation,
                        moral=None, clips=6, lang=None):
    """ابنِ مخطط مشاهد من قالب + مدخلات.

    template: اسم القالب؛ title: عنوان القصة؛ hero: البطل
    (مثال «عائشة الأرملة»)؛ situation: الموقف (مثال «ظلمتها
    حماتها وطردتها من بيتها»)؛ moral: العبرة (افتراضيًا عبرة
    القالب)؛ clips: عدد المشاهد (1–12، الافتراضي 6 = 48 ثانية)؛
    lang: لغة القالب "ar" (افتراضيًا) أو "en" — والقالب
    الإنجليزي موازٍ للعربي بنفس الأطوار والأرقام المحددة.

    يرجع قاموسًا فيه القالب والعنوان والبطل والموقف والعبرة
    والهوك وسؤال الختام وقائمة scenes (كل مشهد: scene وbeat
    وbeat_label وprompt وduration_seconds) + حقل "lang".
    """
    if isinstance(clips, bool) or not isinstance(clips, int) \
            or clips < MIN_CLIPS or clips > MAX_CLIPS:
        raise ValueError("عدد المشاهد يجب أن يكون بين %d و%d (وصل: %s)"
                         % (MIN_CLIPS, MAX_CLIPS, clips))
    lang = _norm_template_lang(lang)
    tpl = get_template(template, lang=lang)
    title = _require_text(title, "عنوان القصة")
    hero = _require_text(hero, "اسم البطل")
    situation = _require_text(situation, "الموقف")
    moral = (moral or "").strip() if isinstance(moral, str) else ""
    moral = moral or tpl["default_moral"]
    values = {"title": title, "hero": hero,
              "situation": situation, "moral": moral}
    labels = BEAT_LABELS_EN if lang == "en" else BEAT_LABELS
    scenes = []
    for i, beat in enumerate(_beats_for_clips(clips)):
        prompt = tpl["beats"][beat].format(**values)
        if len(prompt) > 200:
            prompt = prompt[:200].rstrip() + "…"
        scenes.append({"scene": i + 1,
                       "beat": beat,
                       "beat_label": labels[beat],
                       "prompt": prompt,
                       "duration_seconds": CLIP_SECONDS})
    hook = scenes[0]["prompt"]
    closing_question = tpl["closing_question"].format(**values)
    return {
        "template": tpl["name"],
        "template_label": tpl["label"],
        "lang": lang,
        "title": title,
        "hero": hero,
        "situation": situation,
        "moral": moral,
        "hook": hook,
        "closing_question": closing_question,
        "clips": clips,
        "clip_seconds": CLIP_SECONDS,
        "total_duration_seconds": clips * CLIP_SECONDS,
        "scenes": scenes,
    }


def render_story_text(outline):
    """اجمع مخطط مشاهد نص سرد واحدًا (جمل المشاهد + سؤال الختام).

    يصلح ملف نص قصة (`queue add --text-file`) أو مدخلًا
    لـ `build_scene_plan` عبر ملف نص الطابور.
    """
    lines = [s["prompt"] for s in (outline or {}).get("scenes", [])]
    question = (outline or {}).get("closing_question") or ""
    if question.strip():
        lines.append(question.strip())
    text = "\n".join(lines).strip()
    if not text:
        raise ValueError("المخطط فارغ — لا يمكن تحويله إلى نص قصة")
    return text


def format_outline(outline):
    """نص المخطط للطباعة (عربي افتراضيًا؛ إنجليزي إن كان
    outline["lang"] == "en")."""
    lang = (outline or {}).get("lang") or "ar"
    if lang == "en":
        lines = ["== Story outline — %s (%s) ==" % (outline["title"],
                                                     outline["template_label"]),
                 "Hero: %s — Situation: %s" % (outline["hero"],
                                               outline["situation"]),
                 "Duration: %d scenes × %d seconds = %d seconds"
                 % (outline["clips"], outline["clip_seconds"],
                    outline["total_duration_seconds"]),
                 ""]
        for s in outline["scenes"]:
            lines.append("  Scene %d (%s): %s"
                         % (s["scene"], s["beat_label"], s["prompt"]))
        lines.append("")
        lines.append("Closing question: %s" % outline["closing_question"])
        return "\n".join(lines) + "\n"
    lines = ["== مخطط قصة — %s (%s) ==" % (outline["title"],
                                           outline["template_label"]),
             "البطل: %s — الموقف: %s" % (outline["hero"],
                                        outline["situation"]),
             "المدة: %d مشهدًا × %d ثوانٍ = %d ثانية"
             % (outline["clips"], outline["clip_seconds"],
                outline["total_duration_seconds"]),
             ""]
    for s in outline["scenes"]:
        lines.append("  المشهد %d (%s): %s"
                     % (s["scene"], s["beat_label"], s["prompt"]))
    lines.append("")
    lines.append("سؤال الختام: %s" % outline["closing_question"])
    return "\n".join(lines) + "\n"
