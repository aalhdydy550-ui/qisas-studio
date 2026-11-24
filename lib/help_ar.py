#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""مساعدة عربية — `studio.py help-ar`: كل أمر ووظيفته ومثال عليه.

مساعدة نصية فقط (لا ترجمة كاملة للواجهة) — الأوامر نفسها
تبقى بالإنجليزية كما هي في كل الأدوات.
"""
COMMANDS = [
    ("status", "فحص حالة الطبقات الثلاث (OmniRoute وOpenMontage وConcat)",
     "python3 studio.py status"),
    ("doctor", "فحص بيئة studio كاملة (28 فحصًا) — PASS/FAIL صادق لكل فحص — ومع --accounts فحوصات الحسابات (فيسبوك/يوتيوب/Veo/TikTok/Instagram) في قسم منفصل، ومع --llm فحوصات سلسلة LLM (بوابة OmniRoute + مساعد Gemini + توفر Ollama المحلي) في قسم منفصل؛ وتوكن يوتيوب بقي له يومان أو أقل = خطأ يطلب إعادة الموافقة فورًا عبر youtube-reauth",
     "python3 studio.py doctor --accounts"),
    ("llm-status", "حالة مزودي الذكاء: السلسلة المهيأة (OmniRoute (ddgw وGroq) ثم Gemini Flash-Lite ثم Gemini ثم Ollama المحلي كاحتياطي أخير) + أي مزود في تهدئة حصة + عدادات مكالمات اليوم + سطر توفر Ollama الحي (متاح/غير متاح) — قراءة فقط، بلا أي استدعاء توليد",
     "python3 studio.py llm-status"),
    ("protect", "فحص حماية المشروع — تقرير عربي واحد: سلامة الملفات + صلاحياتها + مسح الأسرار + آخر نسخة احتياطية (قراءة فقط، لا يحذف ولا يحجر)؛ ومعه فحص «حماية المشروع» داخل doctor",
     "python3 studio.py protect"),
    ("init", "معالج إعداد تفاعلي موجَّه — يفحص كل حساب خطوة بخطوة (فيسبوك/يوتيوب/صوت الراوي) وينجز ما يمكن أتمتته ويعرض الباقي كخطوة واحدة واضحة؛ ويسأل عن الهوية والدفع (اسم الصفحة وملف الشعار PNG ورقم فودافون كاش) ويكتب config.yaml + الكرونات المقترحة",
     "python3 studio.py init"),
    ("run", "خط الإنتاج الكامل: قصة ← فيديو عمودي 720×1280 جاهز للنشر — ومع --backend openreel تجميع عبر الوضع التلقائي لـOpenReel (أبطأ ~3× بلا GPU)، ومع --grade PRESET تدرج لوني بعد الريندر وقبل الشعار",
     "python3 studio.py run --story anza --project anza-part1 --out ~/workspace/videos/out.mp4"),
    ("run --demo", "القصة التجريبية المدمجة — فيديو حقيقي في ~دقيقة، بلا مفاتيح ولا رصيد",
     "python3 studio.py run --demo"),
    ("script", "توليد هوك وعنوان وكابشن للقصة عبر سلسلة بدائل ذكاء مجانية (OmniRoute (ddgw وGroq) ثم Gemini Flash-Lite ثم Gemini ثم Ollama المحلي عند الحصة) — ومعه وصف نشر وهاشتاغات فيسبوك مولّدة (تُطبع وتُحفظ في script-ai.json)",
     "python3 studio.py script --story anza --allow-fallback"),
    ("produce", "تجهيز أصول مشروع OpenMontage (سيناريو + سرد + صور)",
     "python3 studio.py produce --project anza-part1"),
    ("assemble", "تجميع تشغيل سابق وتصديره فيديو (Concat افتراضيًا) — ومع --backend headless/mlt/openreel خلفية بديلة (openreel: الوضع التلقائي لـOpenReel، أبطأ ~3× بلا GPU)، ومع --grade PRESET تدرج لوني بعد الريندر وقبل الشعار",
     "python3 studio.py assemble --run <RUN_ID> --out ~/workspace/videos/out.mp4"),
    ("thumbnail", "توليد صورة مصغرة 720×1280 بنص الهوك أعلى الصورة",
     "python3 studio.py thumbnail --video ~/workspace/videos/out.mp4 --hook \"العنوان الصادم\""),
    ("quote-cards", "توليد بطاقات الاقتباس الثلاث (عبرة/حكمة/موعظة) كصور مستقلة",
     "python3 studio.py quote-cards --ibra \"...\" --hikma \"...\" --mawiza \"...\" --out-dir ~/workspace/videos/quote-cards/"),
    ("long-video", "فيديو طويل أفقي 1280×720 (8–12 دقيقة) من عدة قصص",
     "python3 studio.py long-video --out ~/workspace/videos/long.mp4 --title \"قصص الأسبوع\" --story anza"),
    ("long-video --auto-week", "الفيديو الطويل من قصص الأسبوع المنشورة تلقائيًا (بلا تجميع يدوي)",
     "python3 studio.py long-video --auto-week --out ~/workspace/videos/long.mp4"),
    ("long-narration", "سرد طويل مقسّم بصوت الراوي — نص إلى WAV واحد بفواصل صمت",
     "python3 studio.py long-narration --text-file story.txt --out narration.wav"),
    ("run-queue", "مسار إرثي للتوافق فقط: دفعة جماعية قديمة من ملف الطابور — القصص الجاهزة فقط تُشغَّل بالتتابع؛ والمسار الحالي للدفعات هو `batch` (يفحص الرصيد والسقف قبل التخطيط) — لا يُدمج المساران، واستخدم `batch` لأي دفعة جديدة",
     "python3 studio.py run-queue --dry-run"),
    ("queue add", "إضافة قصة جديدة إلى ملف الطابور بسطر واحد",
     "python3 studio.py queue add --title \"قصة جديدة\" --text-file story.txt --parts 1"),
    ("queue validate", "تحقق بنية الطابور (قراءة فقط): سطور انتظار سليمة، بلا أرقام أو عناوين مكررة، بلا مواعيد Unix مكررة، وبلا ملفات mp4 مفقودة مشار إليها — طابور معطوب يوقف daily وbatch قبل أي تخطيط؛ ويُفحص تلقائيًا ضمن doctor",
     "python3 studio.py queue validate"),
    ("queue import", "استيراد قصة طويلة من ملف نصي — تقسيم لأجزاء 40–60 ثانية سردًا مع مواعيد مقترحة (9:00/19:00 بالتناوب)",
     "python3 studio.py queue import --file story.txt --title \"قصة طويلة\" --start 2026-11-23"),
    ("logs", "آخر التشغيلات من runs/ ونتائجها بالعربي (نُشر/فشل/ولماذا) — اليوم افتراضيًا، و--all لكل الأيام",
     "python3 studio.py logs"),
    ("jobs", "سجل المهام الدائم (runs/jobs.jsonl): jobs list يعرض المهام (الأحدث أولًا، مع تصفية --status/--story/--date/--kind/--limit) وjobs show <id> يعرض مهمة واحدة — المهام من دفعات ومسار التشغيل",
     "python3 studio.py jobs list"),
    ("reframe", "إعادة تأطير مقطع أفقي إلى عمودي 720×1280 (قصّ ذكي بلا تشويه): --video/--out و--focus-x 0.0–1.0 (يسار–يمين) و--safety-margin بالبكسلات — الفيديو العمودي يمر بلا إعادة ترميز",
     "python3 studio.py reframe --video clip.mp4 --out clip-v.mp4"),
    ("shorts-cut", "تقطيع فيديو طويل إلى شورتات عمودية 40–60 ثانية (للفيديو الأسبوعي): --video/--out/--count و--phrases <ملف ASS> لتحسين الاختيار؛ والكابشنات المولّدة ملفات ASS منفصلة أسفل الشاشة فقط",
     "python3 studio.py shorts-cut --video long.mp4 --count 3"),
    ("queue publish-status", "تحديث حالة نشر قصة لمنصة واحدة: --number/--platform facebook|youtube|tiktok|instagram/--status pending|published|failed|skipped (يُحفظ في <طابور>.publish.json)",
     "python3 studio.py queue publish-status --number 30 --platform youtube --status published"),
    ("queue publish-summary", "ملخص حالات النشر لكل منصة في الطابور (معلق/منشور/فاشل/متخطى) — قراءة فقط",
     "python3 studio.py queue publish-summary"),
    ("queue pending", "عرض القصص المعلقة النشر على منصة واحدة --platform — قراءة فقط",
     "python3 studio.py queue pending --platform youtube"),
    ("analyze", "تحليل آخر فيديو منشور بأرقام حقيقية (فيسبوك + يوتيوب) واقتراحات تحسين؛ ومع --dna تحليل DNA فيروسي: درجة الهوك (0–10) والإيقاع (متوسط طول اللقطة) وفواصل الصمت وكثافة الكلمات وحكم «ليه نجح / إيه الناقص» مربوطًا بالأرقام الحقيقية؛ ومع --reference <فيديو محلي> --story <نص قصة> يقترح إعادة بناء قصة جديدة على نمط الفيديو المرجعي؛ ومع --snapshot يعيد قياس فيديوهات مجموعة التقييم الثابتة ويقارنها بالأساس — وأي تحليل يحفظ الاستجابتين الخام حرفيًا في runs/insights-<وقت>.json مع بصمة sha256 قبل حساب أي ملخص؛ ومع --dna تقرير Viral DNA منظّم (نوع الهوك وقوته + بنية اللقطات + الإيقاع بالوسيط والتباين + المنحنى العاطفي من نص القصة + نقاط ضعف مقاسة)؛ ومع --dna --audio-profile <ملف wav> يُلحق ملف أداء الصوت (منحنى الطاقة + الصمت + العبارات المؤكَّدة) بالتقرير",
     "python3 studio.py analyze --dna --video ~/workspace/videos/najjar-full.mp4 --hook \"الهوك\""),
    ("ideas", "مولّد أفكار قصص بأسلوب الصفحة (هوك صادم + عبرة + سؤال ختام) مع منع تكرار أي عنوان في الطابور — --add يضيف الفكرة للطابور",
     "python3 studio.py ideas --count 5"),
    ("batch", "دفعة جماعية — المسار الحالي للدفعات: إنتاج القصص التالية من الطابور في تشغيل واحد (كل فيديو: إنتاج + فحص + مصغرة + تسجيل)؛ مسار Veo يفحص الرصيد ≥120 أولًا ويحترم سقف Veo — الوضع التجريبي افتراضي يطبع الخطة، والتنفيذ الحقيقي فقط مع --execute؛ وعند التنفيذ الفعلي يُخصم إنفاق Veo تلقائيًا من الرصيد المسجَّل (لا خصم في التجريبي)؛ أما `run-queue` فمسار إرثي للتوافق فقط؛ وفي التجريبي تُطبع بعد الخطة عيّنة المشهد الأول للقصة الجاهزة الأولى (الكابشن الأول + أول جملة سرد + مدة المقطع + سرعة atempo) — بلا أي إنفاق؛ ومع --from-json <ملف> تُبنى الخطة من ملف JSON بدل الطابور؛ ومع --no-spend محاكاة كاملة بلا أي إنفاق (تقدير رصيد + فحص كفاية + ما سيُعاد استخدامه)؛ والمنتجات غير المتغيرة تُعاد من الكاش بلا إعادة ريندر وبلا خصم رصيد (تعطيله بـ --no-cache)؛ وكل مهمة تُسجَّل في سجل المهام الدائم (أمر jobs)",
     "python3 studio.py batch --count 3 --source openmontage --execute"),
    ("scene-plan", "خطة مشاهد Veo لقصة من الطابور قبل إنفاق أي رصيد: 6 موجهات × 8 ثوانٍ × 20 وحدة = 120 وحدة، مع فحص السقف والرصيد ورفض التجاوز برسالة عربية؛ ومع --template <قالب> --hero <بطل> --situation <موقف> --moral <عبرة> تُبنى الموجهات من قالب قصة جاهز (ظلم أقارب/بر والدين/أمانة) عند غياب نص الطابور",
     "python3 studio.py scene-plan --story 4"),
    ("daily", "أمر اليوم الواحد: إنتاج + فحص + مصغرة + نشر المنصتين + نص أول تعليق — افتراضيًا وضع تجريبي، والتنفيذ فقط مع --execute؛ ومسار Veo يطبع خطة المشاهد ويحفظها ويتوقف للموافقة (أو --auto-approve)، والكرون يمضي داخل السقف بلا توقف؛ وعند التنفيذ الفعلي يُخصم إنفاق Veo تلقائيًا من الرصيد المسجَّل بعد الموافقة على الخطة أو عند نشر فيديو Veo جاهز (لا خصم في التجريبي)؛ ومع --backend openreel التجميع عبر الوضع التلقائي لـOpenReel، ومع --grade PRESET تدرج لوني؛ وفي التجريبي تُطبع بعد الخطة عيّنة المشهد الأول (الكابشن الأول + أول جملة سرد + مدة المقطع + سرعة atempo) — بلا أي إنفاق",
     "python3 studio.py daily --slot evening --dry-run"),
    ("schedule --watch", "مراقبة منشور مجدول ونشر أول تعليق عليه (العبرة + سؤال محيّر + موعد الجزء التالي بالدعوة اللطيفة المعتمدة) فور نشره — يغلق ثغرة كروني النشر اللذين يتخطيان المنشورات المجدولة مسبقًا؛ افتراضيًا وضع تجريبي يطبع الخطة والنص بلا قراءة وبلا تعليق، والتنفيذ فقط مع --execute؛ وعند فشل التعليق يُعاد مرة واحدة فقط؛ وإن لم يكن المنشور منشورًا بعد فلا تعليق ويُعاد التشغيل لاحقًا",
     "python3 studio.py schedule --watch --post-id 122132235897269645 --story anza --slot morning --moral \"الظلم مهما طال ليله، الحق بيظهر.\" --question \"لو كنت مكانه، كنت عملت إيه؟\""),
    ("ab", "اختبار A/B: هوكان ومصغرتان لفيديو واحد + سجل الزوج — فيسبوك ويوتيوب بلا A/B أصلي، فالأداة تولّد النسخ وتتتبع المقارنة؛ ومع --cost-per-video N يسجّل تقدير تكلفة وحدات Veo لكل بديل؛ ومع --variants N (افتراضي 3) يولّد N نسخة هوك مرتبة بدرجة DNA مع الفائز (الأعلى درجة)؛ وكل نسخة تطبع تقدير تكلفتها (وحدات Veo + وقت ريندر + $0) مع --engine fast/lite (بعد تقاعد Fast في 5 ديسمبر استخدم lite) وفحص كفاية الرصيد المسجَّل؛ ومع --eval-set يقترح هوكات بديلة لفيديوهات مجموعة التقييم الثابتة (بذرة 20261122) ويقارنها بدرجات الأساس",
     "python3 studio.py ab --video ~/workspace/videos/out.mp4 --hook-a \"الهوك الأول\" --hook-b \"الهوك الثاني\" --cost-per-video 120"),
    ("ab-results", "قارن مشاهدات نسختي اختبار A/B بعد نشرهما (فيسبوك + يوتيوب)",
     "python3 studio.py ab-results"),
    ("update", "جلب آخر إصدار من GitHub وتطبيق الملفات المتغيرة فقط، مع نسخة احتياطية أولًا — config.yaml والأسرار والطابور وبيانات العملاء لا تُمسّ أبدًا",
     "python3 studio.py update --dry-run"),
    ("backup", "نسخة احتياطية zip: الإعداد + الطابور + طلبات العملاء + سجلات التشغيل — مع احتفاظ بآخر 7 نسخ فقط (الأقدم تُحذف تلقائيًا)، وكرون يومي تلقائي للنسخ يُبلَّغ فقط عند الفشل",
     "python3 studio.py backup --keep 7"),
    ("restore --backup", "استرجاع الإعداد والطابور وطلبات العملاء من نسخة backup — بنسخة أمان تلقائية من الحالة الحالية وتأكيد قبل الكتابة؛ والأسرار (توكن يوتيوب/client_secrets) لا تُستعاد أبدًا",
     "python3 studio.py restore --backup backups/backup-20261122-084541.zip --dry-run"),
    ("balance", "توقع رصيد Veo بالأيام: كم يوم يكفي + تاريخ النفاد + توصية — من الرصيد المسجَّل في الإعداد وليس حيًا من API — ويُعرض عمر الرقم دائمًا بجانب القيمة، ورصيد أقدم من 24 ساعة يُحذَّر منه، وعمر مجهول (بلا updated_at) أو أقدم من 7 أيام يُحذَّر منه صراحةً؛ ومع --record N --video NAME تسجيل إنفاق فعلي بعد توليد Flow (يسجَّل معه وقت التحديث)، و--history عرض السجل؛ ومع --cap N سقف إنفاق لكل توليد Veo (0 يلغي السقف) — أي توليد متوقع فوقه يُرفض تلقائيًا؛ ومع --set N ضبط الرصيد المسجَّل مع ختم وقت التحديث بتوقيت القاهرة الآن",
     "python3 studio.py balance --cap 200"),
    ("analyze-ref", "تحليل فيديو مرجعي لمنافس (الهوك وسرعة السرد والختام) — للتعلم فقط",
     "python3 studio.py analyze-ref --url https://www.youtube.com/watch?v=..."),
    ("publish", "نشر فيديو على فيسبوك (Reel) ويوتيوب معًا — أو --dry-run للمعاينة بلا نشر — ويفحص الكابشن أولًا (يرفض أي بوابة متابعة/تعليق) ويعرض الكابشن النهائي قبل النشر؛ ومع --schedule \"YYYY-MM-DD HH:MM\" (بتوقيت القاهرة) يجدول النشر على المنصتين بدل الفوري؛ ومع --platforms tiktok,instagram نشر إضافي على TikTok/Instagram (يتطلب توكنًا عبر tiktok-auth/instagram-auth — بلا توكن يُنشئ حزمة رفع يدوي؛ و--dry-run يتحقق من الحمولة كاملة قبل أي شبكة، وإنستغرام بلا معرّف حساب يُرفض بخطأ عربي)؛ ومع --generate-meta [--part N --parts M] يولّد العنوان والوصف والوسوم من نص القصة عبر سلسلة LLM مع بديل محلي؛ ومع --preflight فحص ما قبل النشر على يوتيوب فقط (التوكن + جلسة رفع بلا بايتات وبلا نشر)",
     "python3 studio.py publish --video ~/workspace/videos/out.mp4 --title \"العنوان\" --schedule \"2026-11-23 19:00\" --dry-run"),
    ("publish --preflight", "فحص ما قبل النشر على يوتيوب: صلاحية التوكن أولًا ثم إنشاء جلسة رفع قابلة للاستئناف بلا إرسال أي بايت من الفيديو وبلا نشر — فإن نجح يطبع «المسار يعمل من الـVM»، وإن فشل بخطأ SSL (بروكسي الـVM) يطبع رسالة الرفع اليدوي من YouTube Studio",
     "python3 studio.py publish --video ~/workspace/videos/out.mp4 --title \"العنوان\" --preflight"),
    ("version", "إصدار studio الحالي + حالة البعيد من سجل المزامنة المحلي (بلا شبكة إجبارية — «غير معروفة» إن غاب السجل)",
     "python3 studio.py version"),
    ("tiktok-auth", "إعداد نشر TikTok: يطبع الخطوات اليدوية الدقيقة (تطبيق مطوّر + موافقة Content Posting API) ويحفظ أي توكن يُعطى في ملف 600",
     "python3 studio.py tiktok-auth"),
    ("instagram-auth", "إعداد نشر Instagram: يطبع الخطوات اليدوية الدقيقة (حساب Business/Creator مربوط بصفحة فيسبوك + Graph API) ويحفظ أي توكن يُعطى في ملف 600",
     "python3 studio.py instagram-auth"),
    ("check", "فحص جودة فيديو قبل النشر (المدة والصمت والصوت والمقاس والشعار والنص والمنطقة الآمنة) — PASS/FAIL؛ وإن فشل الصمت فالإصلاح بأمر fix-audio؛ ومع --captions <مجلد ASS> يدقّق أيضًا تشكيل الكابشن العربي (حروف متصلة، RTL صحيح، بلا U+FFFD، والتفاف الكلمات الطويلة)؛ ومع بيان مصدر (<فيديو>.manifest.json) يضيف تأكيدات تغطية المشاهد وحدودها الآمنة (حد داخل كلمة منطوقة = فشل) وصوت كل عبارة، ويطبع حالة البيان؛ وكل فحص يستخرج عيّنة سلوكية (3 لقطات + معاينة 3ث في runs/samples/<الفيديو>/) بلا أثر على النجاح/الفشل؛ ومع --avatar-image <صورة> يقارن نسبة أبعاد الفيديو بنسبة صورة الأفاتار (تحذير فقط، بلا أثر في كود الخروج — و--aspect-policy native/crop/pad/rotate)",
     "python3 studio.py check --video ~/workspace/videos/out.mp4"),
    ("fix-audio", "إصلاح فجوات الصمت في فيديو تلقائيًا (وصفة عائشة ج2: مزج صوت المشاهد الأصلي مكبَّرًا ليستقر ~-28 ديسيبل + ضجيج وردي خافت 0.05 تحت السرد) — المدة والنص والإيقاع بلا تغيير؛ ويُستدعى تلقائيًا في assemble عند فشل فحص الصمت؛ ومع --denoise إزالة ضجيج (afftdn) بعده، ومع --loudnorm تطبيع جهارة إلى -16 LUFS بعدهما",
     "python3 studio.py fix-audio --video ~/workspace/videos/out.mp4"),
    ("grade", "تدرج لوني على فيديو بـpreset جاهز عبر فلتر lut3d (الفيديو يُعاد ترميزه والصوت يُنسخ): warm دافئ ذهبي (هوية الصفحة) أو vivid أو cinematic أو soft — و--list-presets وحده يعرض المتاح (بلا --video)",
     "python3 studio.py grade --video ~/workspace/videos/out.mp4 --preset warm"),
    ("manifest", "توليد بيان مصدر لفيديو (العنوان والهوك والقصة والعبرة والمصدر + المشاهد والعبارات الموقَّتة + بصمة sha256) — يُكتب تلقائيًا مع كل فيديو يُنتَج؛ وفيديو جديد بلا بيان يُرفض في publish إلا مع --allow-missing-manifest؛ والفيديوهات القديمة (قبل v0.1.37) تحذير «legacy» فقط لا فشل",
     "python3 studio.py manifest --video ~/workspace/videos/out.mp4"),
    ("avatar-job", "تحقق من وظيفة أفاتار ناطق (LongCat) — أمر تحقق نحيف بلا موفر بعد (لا تشغيل على الـVM ولا دمج قبل نجاح اختبار Kaggle): مع --validate <وظيفة JSON> يتحقق (برومبت + صورة + صوت ≤300ث + para بمدتين متطابقتين + audio.kind=narration + الإعدادات) ويطبع أعلام ملف العتاد؛ ومع --template يطبع وظيفة مثال (برومبت أداء مولَّد — و--scene-type narration/dialogue/singing)؛ ومع --list-profiles يعرض الملفات الثلاثة (t4x2-int8 افتراضيًا، a100-bf16، rtx4090-int8) + أعلامها؛ وملاحظة: s_audio=4 قد يسبب احمرار الشفاه في النسخة غير المقطرة",
     "python3 studio.py avatar-job --template"),
    ("preview", "صفحة معاينة HTML لفيديو قبل النشر (إطارات 25/50/75% + مستوى الصوت + فحص الجودة + الكابشن + أول تعليق)",
     "python3 studio.py preview --video ~/workspace/videos/out.mp4 --caption \"...\""),
    ("youtube-auth", "تبادل OAuth ليوتيوب لمرة واحدة (يفتح المتصفح للموافقة)",
     "python3 studio.py youtube-auth"),
    ("youtube-reauth", "إعادة الموافقة على يوتيوب (نفس تبادل OAuth في youtube-auth) — يُستخدم عندما يقترب توكن الاختبار من الانتهاء؛ وdoctor --accounts يحذّر عند ≤3 أيام ويخطئ عند ≤يومين",
     "python3 studio.py youtube-reauth"),
    ("client-run", "تنفيذ طلب فيديو عميل واحد من صفحة «طلب فيديو»",
     "python3 studio.py client-run --order QS-123456"),
    ("process-queue", "تنفيذ كل طلبات العملاء الجديدة دفعة واحدة",
     "python3 studio.py process-queue"),
    ("orders confirm", "تأكيد دفع طلب عميل بعد التحقق من التحويل يدويًا — الطلب بعد أول 30 يومًا من أول طلب لنفس العميل (برقم الواتساب) لا يُنتَج إلا بعدها؛ وطلبات أول 30 يومًا تجربة مجانية بلا حد لعدد الطلبات",
     "python3 studio.py orders confirm QS-123456"),
    ("orders trial", "حالة التجربة المجانية لعميل: تاريخ أول طلب وكم يومًا مجانيًا بقي له من أول 30 يومًا (بلا حد لعدد الطلبات)",
     "python3 studio.py orders trial 01023468196"),
    ("request", "اطلب فيديو بنص عادي — نص قصة كاملة يُستخدم كما هو، وموضوع قصير تُولَّد قصته عبر سلسلة LLM بأسلوب الصفحة ثم تُحفظ في الطابور ويُشغَّل خط الإنتاج؛ وبلا مشروع OpenMontage جاهز ينتهي الطلب بحالة queued صادقة",
     "python3 studio.py request \"رجل فقير وجد محفظة\""),
    ("license", "حالة الترخيص وفترة التجربة (قراءة فقط) — مالك المشروع معفى، والتجربة 30 يومًا من أول تشغيل، وبعدها رخصة تجارية (أفراد 1000 / شركات 5000 جنيه)",
     "python3 studio.py license"),
    ("orders list", "عرض طلبات العملاء — اختياريًا بحالة معينة (مثال awaiting_payment لقائمة انتظار الدفع)",
     "python3 studio.py orders list --status awaiting_payment"),
    ("whisper-ass", "كابشنات ASS من faster-whisper (تجريبي — راجع WHISPER-TEST.md)",
     "python3 studio.py whisper-ass --audio narration.wav --out captions.ass"),
    ("srt-ass", "تحويل ملف SRT إلى ASS بنمط subs/ (خط Noto Naskh Arabic، محاذاة أسفل الوسط) — الكتل التالفة تُتخطى وتُحتسب",
     "python3 studio.py srt-ass --srt captions.srt --out captions.ass"),
    ("karaoke-ass", "كابشنات كاريوكي كلمة-بكلمة من الصوت",
     "python3 studio.py karaoke-ass --audio narration.wav --out karaoke.ass"),
    ("trim", "قص مقطع فيديو بلا إعادة ترميز (تنظيف مقاطع Veo قبل التجميع)",
     "python3 studio.py trim --input clip.mp4 --out clip-cut.mp4 --start 0.5 --end 7.5"),
    ("fx", "تركيبة MoviePy: Ken Burns + نص عربي متحرك على صورة",
     "python3 studio.py fx --image cover.jpg --out clip.mp4 --text \"الهوك\""),
    ("clean-audio", "قص صمت الصوت الخام عبر Auto-Editor (أبدًا على السرد النهائي)",
     "python3 studio.py clean-audio --input raw.wav --out clean.wav"),
    ("help-ar", "هذه المساعدة بالعربية — كل أمر ووظيفته ومثال عليه",
     "python3 studio.py help-ar"),
]


def help_text():
    """نص المساعدة العربية الكامل."""
    lines = ["أوامر studio — المساعدة بالعربية",
             "",
             "== بداية سريعة — 3 خطوات ==",
             "  1) python3 studio.py init — معالج الإعداد الموجَّه "
             "(يفحص الحسابات ويسأل عن الهوية والدفع)",
             "  2) python3 studio.py run --demo — فيديو تجريبي حقيقي "
             "في ~دقيقة، بلا مفاتيح ولا رصيد",
             "  3) python3 studio.py daily --dry-run — خطة اليوم "
             "(القصة + المسار + الكابشن + أول تعليق) بلا تنفيذ",
             "  ملاحظة: `daily` افتراضيًا وضع تجريبي — لا ينفّذ "
             "شيئًا (لا إنتاج ولا نشر ولا كتابة ملفات)؛ والتنفيذ "
             "الحقيقي فقط مع --execute.",
             ""]
    for cmd, desc, example in COMMANDS:
        lines.append("  %s" % cmd)
        lines.append("    %s" % desc)
        lines.append("    مثال: %s" % example)
        lines.append("")
    lines.append("ملاحظات:")
    lines.append("  - الراوي الافتراضي رجل (Piper Kareem)؛ والصوت الثاني "
                 "الاختياري عبر --voice gtts في long-narration وlong-video — "
                 "والصوت الافتراضي نفسه يُضبط في معالج init "
                 "(narration.voice في config.yaml).")
    lines.append("  - النشر يفحص الكابشن أولًا (يرفض أي جملة تجعل الجزء "
                 "التالي مشروطًا بالمتابعة أو التعليق) ويعرض الكابشن "
                 "النهائي قبل النشر؛ وتجاوزه بـ --skip-caption-check "
                 "فقط عند الضرورة.")
    lines.append("  - النشر يفحص جودة الفيديو أولًا تلقائيًا (المدة "
                 "والصمت والصوت والمقاس والشعار)؛ وتجاوزه بـ --skip-check "
                 "فقط عند الضرورة.")
    lines.append("  - عند أي فشل (ffmpeg أو OpenMontage أو فيسبوك أو "
                 "يوتيوب أو ملف مفقود) يظهر شرح بالعربي: ماذا حدث وماذا "
                 "تفعل — لا رسالة تقنية خام.")
    lines.append("  - كل فيديو يُنشر مدته 40–60 ثانية؛ والفيديو الطويل "
                 "8–12 دقيقة أفقي ليوتيوب فقط.")
    lines.append("  - للفحص الكامل: python3 studio.py doctor")
    lines.append("  - توصيل `schedule --watch` بالكرونين (قرار منفصل "
                 "لاحقًا): بعد نجاح النشر المجدول يُشغَّل أمر ثانٍ بعد "
                 "موعد النشر بدقائق بالـpost-id من إيصال النشر مع "
                 "--moral و--question و--execute؛ ونشر التعليق يطلق "
                 "بطاقة موافقة أصلية جديدة لكل تعليق، فالتشغيل من "
                 "الكرون سيتوقف بانتظار الموافقة ما لم تُمنح مسبقًا.")
    return "\n".join(lines) + "\n"


def print_help():
    """اطبع المساعدة العربية."""
    print(help_text(), end="")
