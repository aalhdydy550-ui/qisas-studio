#!/usr/bin/env python3
"""ترجمة أخطاء studio التقنية إلى عربي واضح — الجولة 6 (بند 9).

الأوامر الرئيسية (run/assemble/publish/check) كانت تُظهر أخطاء
خامًا بالإنجليزية من الطبقات التحتية (ffmpeg، OpenMontage،
facebook-cli، YouTube API) فيفهم المستخدم الجديد القليل منها.

`explain_error(exc_or_text, context=None)` تحوّل أي خطأ (استثناء
أو نص) إلى قاموس عربي فيه:

  - "ماذا حدث": شرح مبسط لما حصل فعلًا.
  - "ماذا تفعل": خطوة عملية واحدة على الأقل (أمر يُشغَّل أو ملف
    يُفحص)، وقائمة "steps" الكاملة.

`format_error(explained)` يحوّل القاموس إلى نص عربي جاهز
للطباعة في الطرفية. `explain_error_text(...)` اختصار يجمع
الاثنين.

القاعدة: الترجمة للأخطاء فقط — لا تغيّر سلوك النجاح لأي أمر،
ولا تُخفي الخطأ الأصلي (يُحفظ مختصرًا في حقل "original" ويُطبع
في نهاية التنسيق للتشخيص).

الفئات المغطاة (انظر CATEGORIES): ffmpeg (ثنائي مفقود، ترميز
فشل، بلا صوت)، OpenMontage (مشروع غير موجود، فشل مرحلة)،
facebook-cli (غير مثبّت، توكن منتهٍ/مرفوض، فشل النشر)، YouTube
API (توكن منتهٍ، حصة يومية، رفع فشل)، ملف مفقود عام، رصيد Veo
(منخفض/غير محدَّث)، تصدير Concat فشل، وخطأ غير معروف برسالة
عامة لطيفة.
"""
import re

# الفئات بالترتيب — الأولى أولوية عند تطابق أكثر من نمط.
CATEGORIES = (
    "ffmpeg_not_found",
    "ffmpeg_encode_failed",
    "ffmpeg_no_audio",
    "openmontage_project_missing",
    "openmontage_stage_failed",
    "facebook_not_installed",
    "facebook_token",
    "facebook_publish_failed",
    "tiktok_token",
    "tiktok_publish_failed",
    "instagram_token",
    "instagram_user_id_missing",
    "instagram_publish_failed",
    "youtube_token_expired",
    "youtube_quota",
    "youtube_upload_failed",
    "concat_export_failed",
    "file_missing",
    "veo_balance_low",
    "veo_balance_stale",
    "llm_all_failed",
    "unknown",
)

_UNKNOWN_WHAT = (
    "حصل خطأ غير متوقع أثناء تنفيذ الأمر، ولم نتعرف على سببه "
    "من رسالته — لا يعني هذا أن ملفاتك تضررت.")
_UNKNOWN_DO = (
    "أعد تشغيل الأمر نفسه مرة واحدة؛ فإن تكرر الخطأ، انسخ "
    "السطر الأخير من رسالة الخطأ الأصلية (أسفل هذه الرسالة) "
    "وأرسله مع اسم الأمر الذي كنت تشغّله.")


def _entry(category, title, what, do, steps):
    return {"category": category, "title": title,
            "what_happened": what, "what_to_do": do, "steps": steps}


# كل فئة: (الفئة، العنوان، ماذا حدث، ماذا تفعل، خطوات عملية، أنماط).
_RULES = [
    _entry(
        "ffmpeg_not_found",
        "أداة الفيديو ffmpeg غير مثبّتة أو غير موجودة",
        "الأمر يحتاج أداة ffmpeg (أو ffprobe) لتحويل الفيديو أو "
        "قراءته، لكن النظام لم يجدها — فتوقف قبل أن يبدأ أي عمل.",
        "ثبّت ffmpeg ثم أعد الأمر نفسه.",
        ["شغّل: python3 studio.py doctor — سيظهر سطر ffmpeg "
         "كـ FAIL إن كان مفقودًا فعلًا.",
         "ثبّت الأداة بـ: sudo apt-get install -y ffmpeg",
         "تأكد بعدها بـ: which ffmpeg",
         "أعد الأمر الذي فشل كما هو."]),
    _entry(
        "ffmpeg_no_audio",
        "الفيديو بلا صوت",
        "ملف الفيديو أو الصوت لا يحوي أي مسار صوتي — فشل "
        "التحويل/الفحص لأنه توقع سردًا صوتيًا ولم يجده.",
        "تأكد أن ملف السرد موجود وسليم، ثم أعد توليد الصوت.",
        ["افحص الملف بـ: python3 studio.py check --video "
         "<مسار الفيديو>",
         "تأكد أن ملف السرد (narration-full.wav) موجود في "
         "مجلد تشغيل القصة runs/<القصة>/assets/audio/",
         "إن كان السرد مفقودًا أعد خطوة الإنتاج "
         "(studio.py produce) أو السرد (studio.py long-narration)."]),
    _entry(
        "ffmpeg_encode_failed",
        "فشل ترميز الفيديو (ffmpeg)",
        "بدأ ffmpeg تحويل الفيديو لكنه توقف في المنتصف — غالبًا "
        "ملف دخل تالف أو غير مدعوم، أو خيار ترميز غير صالح.",
        "افحص ملف الدخل أولًا، ثم أعد المحاولة.",
        ["تأكد أن ملف الفيديو/الصوت المدخَل موجود ويُفتح "
         "(جرّب تشغيله في مشغّل عادي).",
         "افحصه بـ: ffprobe -v error -show_format "
         "<مسار الملف>",
         "إن كان الملف تالفًا أعد توليده (المشهد في Flow أو "
         "خطوة الإنتاج)، ثم أعد الأمر.",
         "إن تكرر الفشل انسخ آخر 10 أسطر من رسالة ffmpeg "
         "الأصلية أسفل هذه الرسالة."]),
    _entry(
        "openmontage_project_missing",
        "مشروع OpenMontage غير موجود",
        "اسم المشروع المطلوب غير موجود في مجلد مشاريع "
        "OpenMontage — ربما خطأ إملائي في الاسم، أو المشروع لم "
        "يُنشأ/يُنقل بعد.",
        "اعرض قائمة المشاريع الموجودة وصحّح الاسم.",
        ["اعرض المشاريع بـ: ls ~/workspace/openmontage/projects",
         "قارن الاسم حرفًا بحرف مع ما مرّرته في الأمر "
         "(--project أو اسم القصة).",
         "أعد الأمر بالاسم الصحيح، أو أنشئ المشروع في "
         "OpenMontage أولًا ثم أعد المحاولة."]),
    _entry(
        "openmontage_stage_failed",
        "فشل تجهيز مشروع OpenMontage",
        "المشروع موجود لكن تجهيز أصوله توقف — ملف ناقص أو تالف "
        "داخل المشروع (سيناريو، كتابة، صور، أو سرد).",
        "افتح مجلد المشروع وتأكد من اكتمال ملفاته.",
        ["افتح مجلد المشروع في "
         "~/workspace/openmontage/projects/<اسم المشروع>/",
         "تأكد من وجود: artifacts/script.json و"
         "artifacts/captions.json وassets/images/ (فيها صور) "
         "وassets/audio/narration-full.wav",
         "أكمل الملف الناقص في OpenMontage، ثم أعد: "
         "python3 studio.py produce --project <اسم المشروع>."]),
    _entry(
        "facebook_not_installed",
        "أداة فيسبوك facebook-cli غير مثبّتة",
        "النشر على فيسبوك يحتاج أداة facebook-cli المتصلة، "
        "لكنها غير موجودة في هذا الجهاز — فلم يُرسل أي شيء "
        "إلى فيسبوك.",
        "أكمل ربط facebook-cli أولًا، ثم أعد النشر.",
        ["تأكد بـ: which facebook-cli",
         "اتبع خطوات الربط في README (قسم فيسبوك) أو شغّل: "
         "python3 studio.py doctor — سيوضح سطر فيسبوك ما ينقص.",
         "بعد الربط أعد: python3 studio.py publish --video "
         "<الملف> ..."]),
    _entry(
        "facebook_token",
        "توكن فيسبوك منتهٍ أو مرفوض",
        "رفض فيسبوك بيانات الاعتماد: التوكن منتهي الصلاحية أو "
        "أُلغي أو بلا صلاحية النشر على الصفحة — فلم يُنشر شيء.",
        "جدّد اتصال فيسبوك، ثم أعد النشر.",
        ["أعد ربط حساب فيسبوك (نفس خطوات الربط الأولى في "
         "README) ليصدر توكن جديد.",
         "تأكد أن الحساب المربوط مشرف على الصفحة المطلوبة.",
         "أعد النشر بعد الربط: python3 studio.py publish --video "
         "<مسار الفيديو> --title <العنوان>؛ وإن تكرر الرفض افتح "
         "Meta Business Suite وتأكد أن الصفحة غير مقيدة."]),
    _entry(
        "facebook_publish_failed",
        "فشل النشر على فيسبوك",
        "أُرسل الفيديو إلى فيسبوك لكن النشر لم يُؤكَّد — رُفض "
        "الطلب أو تعذّر تأكيد حالته (شبكة، كابشن أطول من الحد، "
        "أو ملف غير مقبول).",
        "راجع الكابشن والفيديو، ثم أعد النشر مرة واحدة.",
        ["تأكد أن الكابشن أقل من 1024 حرفًا وأن الفيديو "
         "عمودي 720×1280 وأقل من 60 ثانية.",
         "افحص الفيديو بـ: python3 studio.py check --video "
         "<مسار الفيديو>",
         "أعد النشر مرة واحدة؛ وإن تكرر الفشل تحقق من حالة "
         "الصفحة في Meta Business Suite قبل إعادة المحاولة."]),
    _entry(
        "tiktok_token",
        "توكن TikTok غير صالح أو غير مربوط",
        "لا يوجد توكن TikTok محفوظ وصالح — الحساب غير مربوط بعد، "
        "أو التوكن منتهٍ/مرفوض — فلم يُرسل أي شيء إلى TikTok.",
        "أكمل ربط TikTok مرة واحدة، ثم أعد النشر.",
        ["شغّل: python3 studio.py tiktok-auth — لطباعة خطوات "
         "الربط (تطبيق مطوّر + موافقة Content Posting API).",
         "احفظ التوكن بـ: python3 studio.py tiktok-auth --token "
         "<التوكن> — يُحفظ في tiktok-token.json بصلاحية 600 "
         "ولا يُعرض.",
         "تحقق من الربط بـ: python3 studio.py doctor --accounts",
         "أعد النشر بعدها: python3 studio.py publish --video "
         "<مسار الفيديو> --title <العنوان> --platforms tiktok"]),
    _entry(
        "tiktok_publish_failed",
        "فشل النشر على TikTok",
        "أُرسل الفيديو إلى TikTok لكن النشر لم يُؤكَّد — رُفض "
        "الطلب أو تعذّر تأكيد حالته (توكن، نص أطول من الحد، "
        "أو فيديو غير مقبول).",
        "راجع النص والفيديو والتوكن، ثم أعد النشر مرة واحدة.",
        ["تأكد أن نص النشر أقل من 2200 حرف وأن الفيديو عمودي "
         "9:16 وأقل من 10 دقائق.",
         "افحص الفيديو بـ: python3 studio.py check --video "
         "<مسار الفيديو>",
         "تأكد أن التوكن سارٍ بـ: python3 studio.py doctor "
         "--accounts — وإن كان منتهيًا أعد tiktok-auth.",
         "أعد النشر مرة واحدة؛ وإن تكرر الفشل راجع حالة "
         "التطبيق في developers.tiktok.com."]),
    _entry(
        "instagram_token",
        "توكن Instagram غير صالح أو غير مربوط",
        "لا يوجد توكن Instagram محفوظ وصالح — الحساب غير مربوط "
        "بعد، أو التوكن منتهٍ/مرفوض — فلم يُرسل أي شيء إلى "
        "Instagram.",
        "أكمل ربط Instagram مرة واحدة، ثم أعد النشر.",
        ["شغّل: python3 studio.py instagram-auth — لطباعة خطوات "
         "الربط (حساب Business/Creator مربوط بصفحة فيسبوك).",
         "احفظ التوكن بـ: python3 studio.py instagram-auth "
         "--token <التوكن> — يُحفظ في instagram-token.json "
         "بصلاحية 600 ولا يُعرض.",
         "تحقق من الربط بـ: python3 studio.py doctor --accounts",
         "أعد النشر بعدها: python3 studio.py publish --video "
         "<مسار الفيديو> --title <العنوان> --platforms instagram"]),
    _entry(
        "instagram_user_id_missing",
        "معرّف حساب Instagram مفقود",
        "توكن Instagram موجود لكن معرّف الحساب (instagram_user_id) "
        "غير مضبوط — وبدونه لا يعرف Graph API أي حساب ينشر "
        "الريل، فلم يُرسل أي شيء.",
        "اضبط معرّف الحساب في الإعداد، ثم أعد النشر.",
        ["اعرف معرّف حساب Instagram (instagram_business_account "
         "id) من Graph API.",
         "اضبطه في config.yaml تحت publish.instagram_user_id، "
         "أو مرّر --ig-user-id مع أمر النشر.",
         "تحقق بـ: python3 studio.py doctor --accounts — يجب أن "
         "يظهر «مربوط» لا «ناقص إعداد»."]),
    _entry(
        "instagram_publish_failed",
        "فشل النشر على Instagram",
        "أُرسل الريل إلى Instagram لكن النشر لم يُؤكَّد — رُفض "
        "الطلب أو فشلت معالجة الحاوية أو تعذّر تأكيد حالتها.",
        "راجع النص والفيديو والتوكن، ثم أعد النشر مرة واحدة.",
        ["تأكد أن الكابشن أقل من 2200 حرفًا وبحد أقصى 30 وسمًا، "
         "وأن الفيديو عمودي 9:16 وأقل من 90 ثانية.",
         "افحص الفيديو بـ: python3 studio.py check --video "
         "<مسار الفيديو>",
         "تأكد أن التوكن سارٍ ومعرّف الحساب مضبوط بـ: "
         "python3 studio.py doctor --accounts",
         "أعد النشر مرة واحدة؛ وإن تكرر الفشل راجع صلاحيتي "
         "instagram_basic وinstagram_content_publish في تطبيق "
         "Meta للمطورين."]),
    _entry(
        "youtube_token_expired",
        "توكن يوتيوب منتهٍ أو مرفوض",
        "رفضت Google بيانات اعتماد يوتيوب: التوكن منتهي أو "
        "أُلغي ولا يمكن تجديده تلقائيًا — فلم يُرفع شيء.",
        "أعد تبادل OAuth ليوتيوب مرة واحدة، ثم أعد النشر.",
        ["شغّل: python3 studio.py youtube-auth — سيفتح المتصفح "
         "لتسجيل الدخول بحساب القناة.",
         "تأكد أن الملف youtube-token.json حُفظ بعدها في "
         "~/workspace/studio/",
         "أعد أمر النشر نفسه بعد ذلك."]),
    _entry(
        "youtube_quota",
        "انتهت الحصة اليومية ليوتيوب",
        "رفض YouTube API الرفع لأن الحصة اليومية المسموحة "
        "للمشروع انتهت — ليست مشكلة في الفيديو ولا في التوكن، "
        "وتتجدد الحصة تلقائيًا غدًا.",
        "انتظر حتى الغد، أو ارفع الفيديو يدويًا اليوم.",
        ["لا تعيد المحاولة اليوم — كل محاولة تستهلك من الحصة "
         "ولن تنجح قبل التجديد.",
         "للرفع اليوم: استخدم حزمة الرفع اليدوي في "
         "~/workspace/videos/publish-<تاريخ>-youtube/ — اتبع "
         "steps.txt داخلها في YouTube Studio.",
         "راجع استهلاك الحصة في Google Cloud Console ← "
         "YouTube Data API v3 ← Quotas."]),
    _entry(
        "youtube_upload_failed",
        "فشل الرفع على يوتيوب",
        "بدأ الرفع إلى يوتيوب لكنه لم يكتمل — رفض API الطلب أو "
        "انقطع الاتصال أثناء الرفع.",
        "تأكد من الفيديو والاتصال، ثم أعد الرفع مرة واحدة.",
        ["تأكد أن الفيديو موجود وسليم: "
         "python3 studio.py check --video <مسار الفيديو>",
         "تأكد أن العنوان أقل من 100 حرف والوصف أقل من "
         "5000 حرف.",
         "أعد أمر النشر مرة واحدة؛ وإن تكرر الفشل ارفع "
         "الفيديو يدويًا من YouTube Studio بالعنوان والوصف "
         "من حزمة الرفع اليدوي.",
         "إن كان الخطأ الأصلي فيه WRONG_VERSION_NUMBER: بروكسي "
         "الشبكة يمنع الاتصال المباشر بـ YouTube API من هذه "
         "الـVM — الرفع اليدوي من YouTube Studio هو الحل."]),
    _entry(
        "concat_export_failed",
        "فشل تصدير الفيديو من Concat",
        "بنى Concat المشروع لكن التصدير لم يكتمل — توقف الريندر "
        "قبل إنتاج ملف الفيديو النهائي.",
        "أعد التجميع مرة واحدة؛ فإن تكرر، جرّب الخلفية البديلة.",
        ["أعد: python3 studio.py assemble --run <مجلد التشغيل> "
         "أو أعد أمر run نفسه.",
         "إن تكرر الفشل جرّب الخلفية البديلة: "
         "python3 studio.py run ... --backend headless",
         "راجع سجل التجميع في مجلد التشغيل (concat-mcp.jsonl) "
         "لرؤية آخر خطوة توقفت عندها."]),
    _entry(
        "file_missing",
        "ملف مطلوب غير موجود",
        "الأمر طلب ملفًا غير موجود في المسار المذكور — ربما "
        "خطأ إملائي في المسار، أو الملف في مجلد آخر، أو الخطوة "
        "التي تُنتجه لم تُنفذ بعد.",
        "تأكد من المسار حرفًا بحرفًا، ثم نفّذ الخطوة المنتجة.",
        ["اعرض المجلد بـ: ls <مجلد الملف> وتأكد من الاسم "
         "والامتداد (.mp4 / .wav / .json).",
         "إن كان فيديو تجميع: شغّل produce ثم assemble أولًا "
         "(أو run كاملًا) قبل النشر أو الفحص.",
         "أعد الأمر بالمسار الصحيح."]),
    _entry(
        "veo_balance_low",
        "رصيد Veo منخفض — لا يكفي لفيديو جديد",
        "الرصيد المسجَّل لـ Veo أقل من تكلفة فيديو واحد "
        "(120 وحدة) — توليد مشهد جديد في Flow سيرفض أو "
        "سيستهلك آخر الرصيد.",
        "تحقق من الرصيد الحقيقي في Flow، ثم بدّل الخطة مؤقتًا.",
        ["شغّل: python3 studio.py balance — لترى كم يومًا "
         "يكفي الرصيد ومتى يتجدد.",
         "افتح Google Flow وتأكد من الرصيد الحقيقي، وحدّث "
         "veo.balance_units في config.yaml بالقيمة الصحيحة.",
         "حتى التجديد: استخدم مشاهد OpenMontage الجاهزة أو "
         "أجّل توليد Veo الجديد."]),
    _entry(
        "veo_balance_stale",
        "رصيد Veo المسجَّل غير محدَّث",
        "الرصيد المحفوظ في الإعداد قديم أو غير مسجَّل أصلًا — "
        "فأي توقع مبني عليه قد يكون خاطئًا. هذا الرصيد مسجَّل "
        "يدويًا وليس حيًا من أي API.",
        "حدّث الرصيد من Flow يدويًا بعد كل توليد.",
        ["افتح Google Flow واقرأ الرصيد الحالي.",
         "حدّث veo.balance_units في config.yaml بالقيمة "
         "المقروءة (وveo.renews بتاريخ التجديد إن تغيّر).",
         "تأكد بـ: python3 studio.py balance"]),
    _entry(
        "llm_all_failed",
        "كل مزودات الذكاء فشلت",
        "جرّب studio كل مزود ذكاء متاح (OmniRoute ثم Gemini ثم "
        "Ollama المحلي كاحتياطي أخير) ولم يرد أي واحد — غالبًا "
        "انقطاع شبكة أو حصة مستنفدة أو مفتاح مصادقة مرفوض أو "
        "خادم Ollama غير شغال. لا ملفات تضررت؛ والأمر توقف "
        "قبل أي إنتاج.",
        "تحقق من حالة المزودين ثم أعد الأمر نفسه.",
        ["شغّل: python3 studio.py llm-status — لترى أي مزود "
         "في تهدئة (حصة) وأي مزود آخر خطأ أصابه.",
         "شغّل: python3 studio.py doctor --llm — للتأكد أن "
         "بوابة OmniRoute ومساعد Gemini موجودان.",
         "إن كان الخطأ «حصة» (429) انتظر انتهاء التهدئة "
         "(10 دقائق) ثم أعد المحاولة.",
         "للاحتياطي المحلي: تأكد أن Ollama شغال "
         "(`ollama serve`) وأن الموديل مثبّت "
         "(`ollama pull qwen2.5:7b`).",
         "أعد الأمر الذي فشل كما هو."]),
]

_RULE_BY_CATEGORY = {r["category"]: r for r in _RULES}

# أنماط إنجليزية/عربية خام كما تصل فعلًا من الطبقات التحتية.
# (تُطابَق على نص منخفض الحالة؛ والعربية تُطابَق كما هي.)
_PATTERNS = [
    ("ffmpeg_not_found", [
        r"ffmpeg.*not found", r"ffprobe.*not found",
        r"ffmpeg.*command not found", r"ffprobe.*command not found",
        r"no such file or directory: ['\"]?ff(mpeg|probe)",
        r"command not found.*ff(mpeg|probe)",
        r"الأمر غير موجود:\s*ff(mpeg|probe)",
        r"ffmpeg غير (متاح|موجود)",
    ]),
    ("ffmpeg_no_audio", [
        r"no audio stream", r"does not contain any audio",
        r"stream map ['\"]?0:a['\"]? matches no streams",
        r"no audio", r"لا يوجد مسار صوتي",
        r"output file .* does not contain any stream",
    ]),
    ("ffmpeg_encode_failed", [
        r"conversion failed", r"error while opening encoder",
        r"unknown encoder", r"could not find tag for codec",
        r"error.*encod", r"failed to encode",
        r"invalid argument.*codec", r"codec.*not (found|supported)",
        r"فشل ffmpeg", r"تعذر تحويل الصوت عبر ffmpeg",
        r"فشل الترميز",
    ]),
    ("openmontage_project_missing", [
        r"مشروع openmontage غير موجود",
        r"openmontage project.*not found",
        r"project .* not found",
    ]),
    ("openmontage_stage_failed", [
        r"فشل (مرحلة|التجهيز|تجهيز)",
        r"ملف السيناريو (غير موجود|تالف)",
        r"ملف الكتابة (غير موجود|تالف)",
        r"لا توجد صور في",
        r"ملف السرد الكامل غير موجود",
        r"بنية ملف (السيناريو|الكتابة) غير متوقعة",
        r"stage.*fail",
    ]),
    ("facebook_not_installed", [
        r"facebook-cli غير متاح",
        r"facebook-cli.*not found",
        r"no such file or directory: ['\"]?facebook-cli",
        r"command not found.*facebook-cli",
    ]),
    ("facebook_token", [
        r"error validating access token",
        r"invalid oauth access token",
        r"session (has )?expired",
        r"\(\#190\)", r"oauth.*expired",
        r"توكن فيسبوك",
        r"access token.*(expired|invalid|revoked)",
    ]),
    ("facebook_publish_failed", [
        r"فشل النشر على فيسبوك",
        r"النشر لم يُؤكد",
        r"الجدولة لم تُؤكد",
        r"إيصال فيسبوك ليس json",
        r"facebook.*(publish|post).*fail",
        r"publish.*fail.*facebook",
        r"\(\#200\)",  # رفض صلاحية النشر على الصفحة
    ]),
    ("tiktok_token", [
        r"توكن tiktok",
        r"tiktok.*token",
        r"tiktok.*غير مربوط",
        r"لا يوجد توكن tiktok",
    ]),
    ("tiktok_publish_failed", [
        r"فشل (النشر|الرفع).*tiktok",
        r"فشل نشر tiktok",
        r"فشل رفع مقطع tiktok",
        r"open\.tiktokapis\.com",
        r"tiktok.*(publish|upload).*fail",
    ]),
    ("instagram_token", [
        r"توكن instagram",
        r"instagram.*token",
        r"instagram.*غير مربوط",
        r"لا يوجد توكن instagram",
    ]),
    ("instagram_user_id_missing", [
        r"معرّف حساب instagram مفقود",
        r"instagram_user_id.*مفقود",
        r"معرّف حساب instagram.*غير مضبوط",
    ]),
    ("instagram_publish_failed", [
        r"فشل (النشر|الرفع).*instagram",
        r"معالجة حاوية instagram فشلت",
        r"فشل رفع مقطع instagram",
        r"graph\.facebook\.com",
        r"rupload\.facebook\.com",
        r"instagram.*(publish|upload).*fail",
    ]),
    ("youtube_token_expired", [
        r"invalid_grant",
        r"token has been (expired|revoked)",
        r"token.*expired or revoked",
        r"refresh token.*(expired|revoked|invalid)",
        r"توكن يوتيوب غير صالح",
        r"توكن يوتيوب.*(منته|مرفوض|غير صالح)",
        r"لا يوجد توكن يوتيوب",
        r"توكن يوتيوب",
        r"youtube.*token.*(expired|invalid)",
    ]),
    ("youtube_quota", [
        r"quotaexceeded", r"quota exceeded",
        r"dailylimitexceeded", r"exceeded.*quota",
        r"quota.*exceeded", r"الحصة اليومية",
    ]),
    ("youtube_upload_failed", [
        r"فشل الرفع على يوتيوب",
        r"رفض youtube api الرفع",
        r"رفع.*يوتيوب.*فشل",
        r"youtube.*upload.*fail",
        r"upload.*fail.*youtube",
        r"videos\.insert",
        r"httperror.*(400|403|500)",
    ]),
    ("concat_export_failed", [
        r"التصدير لم يكتمل",
        r"export_(start|wait).*fail",
        r"خرج concat برمز",
        r"أُغلق خرج concat",
        r"انقطع الاتصال مع concat",
        r"لا رد من concat",
    ]),
    ("file_missing", [
        r"no such file or directory",
        r"filenotfounderror",
        r"\[errno 2\]",
        r"ملف .* غير موجود",
        r"مجلد .* غير موجود",
        r"غير موجود:\s*\S",
    ]),
    ("veo_balance_low", [
        r"أقل من فيديو veo واحد",
        r"رصيد veo.*(منخفض|نفد|انتهى|لا يكفي)",
        r"veo.*balance.*(low|insufficient|exhausted|out)",
        r"out of credits",
        r"insufficient.*credit",
    ]),
    ("veo_balance_stale", [
        r"رصيد veo غير مسجَّل",
        r"رصيد veo.*(غير محدَّث|قديم|مسجَّل وليس حيًا)",
        r"veo.*balance.*(not (recorded|updated)|stale|missing)",
        r"رصيد.*غير مسجَّل في الإعداد",
    ]),
    ("llm_all_failed", [
        r"فشلت كل مزودات",
        r"كل مزودات الذكاء فشلت",
        r"all llm providers?.*failed",
        r"llm.*all.*failed",
    ]),
]

_COMPILED = [(cat, [re.compile(p, re.IGNORECASE) for p in pats])
             for cat, pats in _PATTERNS]

# كلمات تفرّق بين توكن فيسبوك وتوكن يوتيوب عند غموض النص.
_YOUTUBE_MARKERS = ("youtube", "google", "invalid_grant", "refresh",
                    "يوتيوب")
_FACEBOOK_MARKERS = ("facebook", "فيسبوك", "fb ", "meta",
                    "access token", "(#190)", "(#200)")


def _as_text(exc_or_text):
    """حوّل المدخل إلى نص آمن — بلا استثناء أبدًا."""
    if exc_or_text is None:
        return ""
    if isinstance(exc_or_text, str):
        return exc_or_text
    try:
        return str(exc_or_text)
    except Exception:
        return ""


def _detect_category(text, context=None):
    """حدّد الفئة من النص والسياق (None تعني: بلا سياق)."""
    low = text.lower()
    ctx = (context or "").strip().lower()

    # 1) التوكن الغامض: السياق أو العلامات تحسم فيسبوك/يوتيوب.
    if re.search(r"token.*(expired|invalid|revoked)|توكن.*(منته|مرفوض|غير صالح)",
                 low):
        if ctx in ("facebook", "fb"):
            return "facebook_token"
        if ctx in ("youtube", "yt", "google"):
            return "youtube_token_expired"
        if "tiktok" in low or "تيك توك" in low:
            return "tiktok_token"
        if ("instagram" in low or "إنستغرام" in low
                or "انستغرام" in low):
            return "instagram_token"
        if any(m in low for m in _FACEBOOK_MARKERS):
            return "facebook_token"
        if any(m in low for m in _YOUTUBE_MARKERS):
            return "youtube_token_expired"
        # بلا علامات: توكن يوتيوب هو الحالة الشائعة في studio
        # (توكن وضع الاختبار ينتهي بعد 7 أيام).
        return "youtube_token_expired"

    # 2) 403 غامض: السياق يحسم الحصة/النشر.
    if "403" in low and "quota" not in low:
        if ctx in ("youtube", "yt"):
            return "youtube_upload_failed"
        if ctx in ("facebook", "fb"):
            return "facebook_publish_failed"

    # 2.5) خطأ شبكة/SSL (الجولة 6): بروكسي TLS في هذه الـVM يرفض
    # الاتصال المباشر بـ youtube.googleapis.com بخطأ
    # SSL: WRONG_VERSION_NUMBER — وهو فشل رفع يوتيوب لا فشل فيديو.
    if re.search(r"wrong_version_number|sslerror|ssl.*wrong|"
                 r"urlopen error|max retries exceeded|"
                 r"connection.*(refused|reset|timed? ?out|error)|"
                 r"youtube\.googleapis\.com", low):
        if ctx in ("youtube", "yt", "google"):
            return "youtube_upload_failed"
        if ctx in ("facebook", "fb"):
            return "facebook_publish_failed"
        if ctx in ("tiktok",):
            return "tiktok_publish_failed"
        if ctx in ("instagram", "ig"):
            return "instagram_publish_failed"

    # 3) الأنماط المرتبة — وأولوية للسياق داخل الفئة نفسها.
    for cat, regexes in _COMPILED:
        if any(rx.search(low) for rx in regexes):
            return cat
    return "unknown"


def explain_error(exc_or_text, context=None):
    """ترجم خطأ إلى قاموس عربي: ماذا حدث + ماذا تفعل.

    exc_or_text: استثناء أو نص الخطأ الخام (أو None/فارغ).
    context: سياق اختياري يحسم الغموض — "facebook" أو
        "youtube" أو "ffmpeg" أو "openmontage" أو "veo" أو
        "check" أو "publish" أو "assemble" أو "run".
    يرجع قاموسًا بمفاتيح: category, title, what_happened,
    what_to_do, steps, original — إضافة إلى مفتاحي
    "ماذا حدث" و"ماذا تفعل" بالعربية.
    لا يرفع استثناءً أبدًا — المدخل الفارغ أو غير المعروف
    يرجع الرسالة العامة.
    """
    try:
        original = _as_text(exc_or_text)
    except Exception:
        original = ""
    text = original.strip()
    if not text:
        category = "unknown"
    else:
        try:
            category = _detect_category(text, context)
        except Exception:
            category = "unknown"
    if category == "unknown":
        result = {"category": "unknown",
                  "title": "خطأ غير معروف",
                  "what_happened": _UNKNOWN_WHAT,
                  "what_to_do": _UNKNOWN_DO,
                  "steps": [_UNKNOWN_DO,
                            "شغّل: python3 studio.py doctor — "
                            "للتأكد أن بيئة studio سليمة قبل إعادة المحاولة."],
                  "original": original[:4000]}
    else:
        rule = _RULE_BY_CATEGORY[category]
        result = {"category": rule["category"],
                  "title": rule["title"],
                  "what_happened": rule["what_happened"],
                  "what_to_do": rule["what_to_do"],
                  "steps": list(rule["steps"]),
                  "original": original[:4000]}
    result["ماذا حدث"] = result["what_happened"]
    result["ماذا تفعل"] = result["what_to_do"]
    return result


def format_error(explained):
    """نسّق قاموس explain_error كنص عربي جاهز للطباعة."""
    if isinstance(explained, str):
        explained = explain_error(explained)
    lines = ["خطأ: %s" % explained.get("title", "خطأ غير معروف"),
             "ماذا حدث: %s" % explained.get("what_happened", ""),
             "ماذا تفعل: %s" % explained.get("what_to_do", "")]
    steps = explained.get("steps") or []
    if len(steps) > 1:
        for i, step in enumerate(steps, 1):
            lines.append("  %d) %s" % (i, step))
    original = (explained.get("original") or "").strip()
    if original:
        lines.append("الخطأ الأصلي: %s" % clip_output(original))
    return "\n".join(lines)


def explain_error_text(exc_or_text, context=None):
    """اختصار: ترجمة + تنسيق في استدعاء واحد — يرجع نصًا."""
    return format_error(explain_error(exc_or_text, context))


# --- قصّ المخرجات الطويلة (جولة v0.1.37 — مقترح tinker رقم 12) ---
# مخرجات طويلة (مسارات ملفات، مخرجات أدوات، رسائل خطأ) تُقصّ
# إلى رأس + ذيل مع إعلان عدد الأسطر المحذوفة، حتى تبقى
# التقارير والسجلات قابلة للقراءة.

_CLIP_HEAD_LINES = 8
_CLIP_TAIL_LINES = 8


def clip_output(text, head_lines=_CLIP_HEAD_LINES,
                tail_lines=_CLIP_TAIL_LINES):
    """قصّ نص طويل إلى رأسه وذيله.

    النص القصير (أقل من أو يساوي رأس+ذيل) يُرجَع كما هو.
    النص الطويل يُرجَع كـ:
        <أول head_lines سطرًا>
        ... (حُذفت N سطرًا) ...
        <آخر tail_lines سطرًا>
    """
    if text is None:
        return ""
    text = str(text)
    lines = text.splitlines()
    limit = head_lines + tail_lines
    if len(lines) <= limit:
        return text
    head = lines[:head_lines]
    tail = lines[-tail_lines:] if tail_lines > 0 else []
    omitted = len(lines) - head_lines - tail_lines
    return "\n".join(
        head + ["... (حُذفت %d سطرًا) ..." % omitted] + tail)
