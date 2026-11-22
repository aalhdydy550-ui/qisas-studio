#!/usr/bin/env python3
"""مولّد أفكار قصص — `studio.py ideas`.

يولّد أفكار قصص بأسلوب الصفحة (لهجة مصرية، هوك صادم من جملة
واحدة في أول ثانيتين، عبرة واضحة، ختام بسؤال محيّر، 40–60
ثانية / 5–7 مشاهد، والهوك لا يبدأ برقم أبدًا).

المصادر بالترتيب:
1. OmniRoute المجاني (ddgw) عند توفره — يُطلب منه N فكرة
   بصيغة سطر واحد لكل فكرة، وتُفحص كل فكرة بقواعد الأسلوب.
2. بنك مواضيع محلي بقوالب جاهزة — بديل بلا شبكة، ويُكمل ما
   نقص من توليد النموذج.

منع التكرار: تُقرأ كل العناوين في ملف الطابور الحقيقي (كل
الأقسام: المنشور والمجدول والمخطط له وفي الانتظار — لا
الانتظار فقط) وتُطوى إلى «جوهر» العنوان (بلا أقواس وبلا
«الجزء N»)؛ فأي فكرة جوهرها يساوي جوهر عنوان موجود أو يبدأ
به (أو العكس) تُرفض قبل العرض.
"""
import re

from lib import queue as queue_lib

IDEAS_PROMPT = (
    "أنت كاتب قصص لصفحة فيسبوك «قصص وعبر» باللهجة المصرية. "
    "ولّد {count} أفكار قصص جديدة في موضوع: {theme}. قواعد كل فكرة: "
    "عنوان جذاب؛ هوك صادم من جملة واحدة يُقال في أول ثانيتين ولا "
    "يبدأ برقم أبدًا؛ عبرة واضحة في جملة؛ ختام بسؤال محيّر "
    "للمشاهدين؛ عدد أجزاء مقترح (1 أو 2 أو 3). اكتب كل فكرة في "
    "سطر واحد بهذا الشكل بالظبط: العنوان | الهوك | العبرة | "
    "عدد الأجزاء | سؤال الختام. بلا أي نص آخر قبل الأفكار أو بعدها.")

# بنك المواضيع المحلي — بديل بلا شبكة (أفكار مكتوبة يدويًا
# بأسلوب الصفحة؛ لا أفكار منشورة أو في الطابور هنا).
TOPIC_BANK = [
    {"theme": "ظلم الحماة والأقارب", "ideas": [
        {"title": "حماتي سرقت ذهبي",
         "hook": "حماتي دخلت أوضتي وأنا نايمة… وطلعت بالدهب!",
         "moral": "الظلم مهما طال ليله، الحق بيظهر.",
         "parts": 2,
         "question": "لو مكانها، تسامحي ولا تاخدي حقك؟"},
        {"title": "أخي أخذ ميراثي",
         "hook": "أخي وقّعني على ورقة… وأنا مش عارفة إنها تنازل عن الميراث!",
         "moral": "الميراث حق، واللي يأكله بياكل نار.",
         "parts": 2,
         "question": "الميراث يفرّق الإخوات ولا الحق يرجع؟"},
        {"title": "عمّي طردنا من البيت",
         "hook": "عمّي غيّر الكالون… وأمي وأنا في الشارع بلا مأوى!",
         "moral": "ربنا بيعوّض المظلوم من حيث لا يحتسب.",
         "parts": 2,
         "question": "تفتكروا ربنا عوّضهم إزاي؟"},
    ]},
    {"theme": "عوض ربنا", "ideas": [
        {"title": "بعت البقرة وربنا عوّضني",
         "hook": "بعت آخر بقرة عندي… وتاني يوم لقيت الباب بيخبط!",
         "moral": "من ترك شيئًا لله عوّضه الله خيرًا منه.",
         "parts": 1,
         "question": "إيه آخر حاجة ضحّيت بيها وربنا عوّضك؟"},
        {"title": "الشغل اللي ضاع مني",
         "hook": "اتفصلت من الشغل وأنا مديون… وبعد شهر جالي عرض أضعاف راتبي!",
         "moral": "الرزق مكتوب، والباب اللي يتقفل بيتفتح غيره.",
         "parts": 1,
         "question": "حصل معاك باب اتقفل واتفتح أحسن منه؟"},
        {"title": "دعوة أمي في الفجر",
         "hook": "أمي دعت لي في الفجر… والصبح حصل اللي ماكنتش أحلم بيه!",
         "moral": "دعوة الأم لا تُرد.",
         "parts": 1,
         "question": "إيه الدعوة اللي غيّرت حياتك؟"},
    ]},
    {"theme": "الأمانة", "ideas": [
        {"title": "لقيت محفظة فيها مليون",
         "hook": "لقيت محفظة فيها مليون جنيه… ورجّعتها لصاحبها!",
         "moral": "الأمانة أغلى من الدهب.",
         "parts": 1,
         "question": "لو لقيت المليون ده، كنت رجّعته؟"},
        {"title": "الخزنة المفتوحة",
         "hook": "الخزنة كانت مفتوحة والفلوس قدامي… ومحدش شايفني!",
         "moral": "من راقب الله في السر، حفظه الله في العلن.",
         "parts": 1,
         "question": "إيه اللي يمنعك تاخد حق مش حقك؟"},
        {"title": "أمانة الجار",
         "hook": "جاري سلّمني مفاتيح بيته وسافر… ولما رجع لقى حاجة غريبة!",
         "moral": "الأمانة أمانة ولو مع جار.",
         "parts": 1,
         "question": "تأمّن جارك على بيتك؟"},
    ]},
    {"theme": "بر الوالدين", "ideas": [
        {"title": "أمي باعت ذهبها عشاني",
         "hook": "أمي باعت ذهبها عشان أدخل الجامعة… وأنا نسيت!",
         "moral": "بر الأم دين لا يُسدّد.",
         "parts": 2,
         "question": "إيه اللي عملته أمك عشانك ونسيته؟"},
        {"title": "أمي في دار المسنين",
         "hook": "حطيت أمي في دار مسنين… وبعد سنة جيت أزورها فلقيت المفاجأة!",
         "moral": "الجنة تحت أقدام الأمهات.",
         "parts": 2,
         "question": "لو أمك كبرت، تعمل إيه؟"},
        {"title": "دعاء أبي قبل موته",
         "hook": "أبي دعا لي قبل ما يموت بساعة… والدعوة دي غيّرت حياتي!",
         "moral": "دعاء الوالد لولده لا يُرد.",
         "parts": 1,
         "question": "إيه الدعوة اللي لسه مستنيها؟"},
    ]},
    {"theme": "الصدقة", "ideas": [
        {"title": "صدقة السر",
         "hook": "كنت بتصدق في السر كل جمعة… وفي يوم لقيت الظرف راجع لي!",
         "moral": "الصدقة تطفئ غضب الرب وتدفع ميتة السوء.",
         "parts": 1,
         "question": "بتصدق في السر ولا العلن؟"},
        {"title": "صدقة الفقير",
         "hook": "فقير تصدق بآخر جنيه في جيبه… وتاني يوم حصلت المعجزة!",
         "moral": "ما نقص مال من صدقة.",
         "parts": 1,
         "question": "تصدق ولو بالقليل؟"},
    ]},
    {"theme": "حسن الظن", "ideas": [
        {"title": "جارتي اللي ظلمتها",
         "hook": "ظلمت جارتي عشر سنين… وفي يوم عرفت الحقيقة!",
         "moral": "حسن الظن عبادة، وسوء الظن ظلم.",
         "parts": 2,
         "question": "ظلمت حد بسوء ظن قبل كده؟"},
        {"title": "الرسالة اللي فهمتها غلط",
         "hook": "رسالة واحدة فهمتها غلط… ودمّرت صداقة عشرين سنة!",
         "moral": "التمس لأخيك سبعين عذرًا.",
         "parts": 1,
         "question": "حصل وفهمت حد غلط؟"},
    ]},
    {"theme": "دروس في الأمانة والصدق", "ideas": [
        {"title": "الكذبة اللي كبرت",
         "hook": "كذبة صغيرة قلتها وأنا صغير… وكبرت معايا لحد ما دمّرت بيتي!",
         "moral": "الصدق منجاة، والكذب أول طريق الهلاك.",
         "parts": 2,
         "question": "كذبة صغيرة ممكن تدمر بيت؟"},
        {"title": "الشهادة الزور",
         "hook": "شهدت زور عشان صاحبي… وبعد عشر سنين الشهادة دي رجعت لي!",
         "moral": "شهادة الزور من أكبر الكبائر.",
         "parts": 1,
         "question": "تشهد زور عشان صاحبك؟"},
    ]},
    {"theme": "التوبة والرجوع", "ideas": [
        {"title": "ابني اللي ضاع ورجع",
         "hook": "ابني ضاع مني ثلاث سنين… ولقيته في مكان مستحيل!",
         "moral": "من تاب تاب الله عليه، ومن دعا استجاب الله له.",
         "parts": 2,
         "question": "إيه المكان اللي لقيته فيه؟"},
        {"title": "التاجر الظالم",
         "hook": "التاجر كان بيغش في الميزان… لحد ما جه اليوم اللي اتقلب فيه الميزان عليه!",
         "moral": "الظلم ظلمات يوم القيامة.",
         "parts": 1,
         "question": "الغش في الميزان بيضيع البركة؟"},
    ]},
]

THEMES = [t["theme"] for t in TOPIC_BANK]

_DIGITS = set("0123456789٠١٢٣٤٥٦٧٨٩")


def valid_hook(hook):
    """هل الهوك يطابق قواعد الأسلوب؟ جملة واحدة غير فارغة،
    لا تبدأ برقم أبدًا (القاعدة الدائمة: الأرقام كلمات لا أرقام
    في بداية السطر — خلل bidi في libass)، وبلا وسوم ASS
    ({ } \\) — وسوم مثل {\fs200} كانت تمرّ إلى المسودة
    والطابور فتُقال حرفيًا أو تشوّه الريندر (اختراق 2026-11-22؛
    المصارف تهربها أصلًا لكن المصدر يرفضها)."""
    hook = (hook or "").strip()
    if not hook:
        return False
    if hook[0] in _DIGITS:
        return False
    if len(hook) > 140:
        return False
    if any(c in hook for c in "{}\\"):
        return False
    return True


def _core(title):
    """جوهر العنوان للمقارنة: بلا أقواس وبلا «الجزء N» وبلا
    مسافات زائدة."""
    text = re.sub(r"\s+", " ", (title or "").strip())
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"[—\-]\s*الجزء.*$", "", text)
    text = re.sub(r"\s*الجزء\s+.*$", "", text)
    text = re.sub(r"\s+", " ", text).strip(" —-")
    return text.strip()


def existing_titles(queue_path):
    """كل عناوين القصص في ملف الطابور (كل الأقسام) كجوهور
    مطوية. ملف غائب = مجموعة فارغة (بلا منع تكرار)."""
    cores = set()
    try:
        with open(queue_path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return cores
    for span in re.findall(r"\*\*(.+?)\*\*", text):
        core = _core(span)
        if core:
            cores.add(core)
    for entry in queue_lib.parse_waiting_entries(text):
        core = _core(entry["title"])
        if core:
            cores.add(core)
    return cores


def is_duplicate(title, existing_cores):
    """هل العنوان مكرر؟ جوهره يساوي جوهرًا موجودًا أو يبدأ به
    أو يبدأ به جوهر موجود (مثل «عائشة الأرملة» مقابل
    «عائشة الأرملة في السودان»)."""
    core = _core(title)
    if not core:
        return True
    for other in existing_cores:
        if core == other or core.startswith(other) \
                or other.startswith(core):
            return True
    return False


def _clean_idea(raw):
    """نظّف فكرة خام (من النموذج أو البنك) وصحّح أجزاءها.
    يرجع القاموس أو None إن خالفت قواعد الأسلوب."""
    title = (raw.get("title") or "").strip()
    hook = (raw.get("hook") or "").strip()
    moral = (raw.get("moral") or "").strip()
    question = (raw.get("question") or "").strip()
    try:
        parts = int(raw.get("parts") or 1)
    except (TypeError, ValueError):
        parts = 1
    if not title or not moral:
        return None
    if not valid_hook(hook):
        return None
    if parts < 1:
        parts = 1
    if parts > 3:
        parts = 3
    return {"title": title, "hook": hook, "moral": moral,
            "parts": parts,
            "question": question or "لو كنت مكانه، كنت عملت إيه؟"}


def parse_llm_ideas(text):
    """فسّر رد النموذج: سطر لكل فكرة بالصيغة
    «العنوان | الهوك | العبرة | الأجزاء | السؤال». يرجع أفكارًا
    نظيفة فقط (المخالفة لقواعد الأسلوب تُسقط)."""
    ideas = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        # النموذج يغلّف الحقول أحيانًا بعلامات تنصيص — أزلها
        # من الطرفين قبل الفحص (وإلا ظهرت في العنوان/الهوك).
        fields = [f.strip().strip("\"“”«»") for f in line.split("|")]
        if len(fields) < 4:
            continue
        try:
            parts = int(fields[3])
        except ValueError:
            parts = 1
        idea = _clean_idea({
            "title": fields[0], "hook": fields[1],
            "moral": fields[2], "parts": parts,
            "question": fields[4] if len(fields) > 4 else "",
        })
        if idea:
            ideas.append(idea)
    return ideas


def local_ideas(count, theme, existing_cores):
    """أفكار من البنك المحلي (بلا شبكة): دوران حتمي على
    الأفكار — يبدأ من موضع يعتمد على حجم الطابور فيتنوع
    مع نموه — مع تخطي أي مكرر. يرجع (أفكار، عدد المتخطى)."""
    pool = []
    for topic in TOPIC_BANK:
        if theme and topic["theme"] != theme:
            continue
        for idea in topic["ideas"]:
            pool.append((topic["theme"], idea))
    if not pool:
        return [], 0
    start = len(existing_cores) % len(pool)
    ordered = pool[start:] + pool[:start]
    picked = []
    skipped = 0
    for topic_theme, raw in ordered:
        if len(picked) >= count:
            break
        idea = _clean_idea(raw)
        if idea is None:
            skipped += 1
            continue
        if is_duplicate(idea["title"], existing_cores):
            skipped += 1
            continue
        idea = dict(idea)
        idea["theme"] = topic_theme
        idea["source"] = "local"
        picked.append(idea)
    return picked, skipped


def generate_ideas(queue_path, count=5, theme=None, chat_fn=None):
    """ولّد أفكارًا: النموذج أولًا (إن أُعطي chat_fn)، ثم
    البنك المحلي لتكملة العدد. كل فكرة تحمل theme وsource
    («omniroute» أو «local»). يرجع (أفكار، ملاحظات)."""
    if count < 1:
        count = 1
    if count > 10:
        count = 10
    existing = existing_titles(queue_path)
    notes = []
    ideas = []
    if theme and theme not in THEMES:
        notes.append("موضوع غير معروف (%s) — يُستخدم كل البنك" % theme)
        theme = None
    if chat_fn is not None:
        prompt_theme = theme or "، ".join(THEMES[:4])
        try:
            text = chat_fn(IDEAS_PROMPT.format(count=count,
                                               theme=prompt_theme))
            for idea in parse_llm_ideas(text):
                if len(ideas) >= count:
                    break
                if is_duplicate(idea["title"], existing):
                    continue
                if is_duplicate(idea["title"],
                                {_core(i["title"]) for i in ideas}):
                    continue
                idea = dict(idea)
                idea["theme"] = theme or "عام"
                idea["source"] = "omniroute"
                ideas.append(idea)
            if ideas:
                notes.append("توليد عبر النموذج: %d فكرة" % len(ideas))
        except Exception as e:
            notes.append("فشل توليد النموذج (%s) — البديل المحلي"
                         % str(e)[:120])
    if len(ideas) < count:
        taken = set(existing) | {_core(i["title"]) for i in ideas}
        rest, skipped = local_ideas(count - len(ideas), theme, taken)
        ideas.extend(rest)
        if skipped:
            notes.append("تُخطي %d فكرة مكررة من البنك" % skipped)
        if len(ideas) < count:
            notes.append("البنك المحلي نفد بعد منع التكرار — "
                         "المُنتَج %d من %d" % (len(ideas), count))
    return ideas, notes


def format_ideas(ideas):
    """نص عربي مرقّم للأفكار: العنوان + الهوك + العبرة +
    الأجزاء + سؤال الختام + المصدر."""
    lines = ["== أفكار قصص جديدة (%d) ==" % len(ideas), ""]
    for i, idea in enumerate(ideas, 1):
        lines.append("%d. %s [%s — %s]"
                     % (i, idea["title"], idea["theme"],
                        "نموذج" if idea.get("source") == "omniroute"
                        else "محلي"))
        lines.append("   الهوك: %s" % idea["hook"])
        lines.append("   العبرة: %s" % idea["moral"])
        lines.append("   الأجزاء: %d — سؤال الختام: %s"
                     % (idea["parts"], idea["question"]))
        lines.append("")
    return "\n".join(lines)


def draft_text(idea):
    """مسودة نص القصة للطابور (تُصاغ كاملة قبل الإنتاج)."""
    return ("{title}\n\n"
            "الهوك: {hook}\n\n"
            "العبرة: {moral}\n\n"
            "سؤال الختام: {question}\n\n"
            "(مسودة مولّدة آليًا بأمر ideas — تحتاج صياغة كاملة "
            "قبل الإنتاج.)\n"
            .format(title=idea["title"], hook=idea["hook"],
                    moral=idea["moral"], question=idea["question"]))


def add_idea(queue_path, idea, stories_dir):
    """أضف فكرة إلى الطابور عبر مسار queue add الموجود.
    يرجع نتيجة add_story (رقم وعنوان وملف النص)."""
    return queue_lib.add_story(
        queue_path, idea["title"], draft_text(idea),
        parts=idea["parts"],
        note="فكرة مولّدة (%s)" % ("نموذج" if idea.get("source")
                                    == "omniroute" else "محلي"),
        stories_dir=stories_dir)
