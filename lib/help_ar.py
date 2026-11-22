#!/usr/bin/env python3
"""مساعدة عربية — `studio.py help-ar`: كل أمر ووظيفته ومثال عليه.

مساعدة نصية فقط (لا ترجمة كاملة للواجهة) — الأوامر نفسها
تبقى بالإنجليزية كما هي في كل الأدوات.
"""
COMMANDS = [
    ("status", "فحص حالة الطبقات الثلاث (OmniRoute وOpenMontage وConcat)",
     "python3 studio.py status"),
    ("doctor", "فحص بيئة studio كاملة (24 فحصًا) — PASS/FAIL صادق لكل فحص — ومع --accounts فحوصات الحسابات (فيسبوك/يوتيوب/Veo) في قسم منفصل؛ وتوكن يوتيوب بقي له يومان أو أقل = خطأ يطلب إعادة الموافقة فورًا عبر youtube-reauth",
     "python3 studio.py doctor --accounts"),
    ("init", "معالج إعداد تفاعلي موجَّه — يفحص كل حساب خطوة بخطوة (فيسبوك/يوتيوب/صوت الراوي) وينجز ما يمكن أتمتته ويعرض الباقي كخطوة واحدة واضحة؛ ويسأل عن الهوية والدفع (اسم الصفحة وملف الشعار PNG ورقم فودافون كاش) ويكتب config.yaml + الكرونات المقترحة",
     "python3 studio.py init"),
    ("run", "خط الإنتاج الكامل: قصة ← فيديو عمودي 720×1280 جاهز للنشر",
     "python3 studio.py run --story anza --project anza-part1 --out ~/workspace/videos/out.mp4"),
    ("run --demo", "القصة التجريبية المدمجة — فيديو حقيقي في ~دقيقة، بلا مفاتيح ولا رصيد",
     "python3 studio.py run --demo"),
    ("script", "توليد هوك وعنوان وكابشن للقصة عبر نماذج مجانية",
     "python3 studio.py script --story anza --allow-fallback"),
    ("produce", "تجهيز أصول مشروع OpenMontage (سيناريو + سرد + صور)",
     "python3 studio.py produce --project anza-part1"),
    ("assemble", "تجميع تشغيل سابق وتصديره فيديو (Concat افتراضيًا)",
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
    ("run-queue", "دفعة جماعية من ملف الطابور — القصص الجاهزة فقط تُشغَّل بالتتابع",
     "python3 studio.py run-queue --dry-run"),
    ("queue add", "إضافة قصة جديدة إلى ملف الطابور بسطر واحد",
     "python3 studio.py queue add --title \"قصة جديدة\" --text-file story.txt --parts 1"),
    ("queue import", "استيراد قصة طويلة من ملف نصي — تقسيم لأجزاء 40–60 ثانية سردًا مع مواعيد مقترحة (9:00/19:00 بالتناوب)",
     "python3 studio.py queue import --file story.txt --title \"قصة طويلة\" --start 2026-11-23"),
    ("logs", "آخر التشغيلات من runs/ ونتائجها بالعربي (نُشر/فشل/ولماذا) — اليوم افتراضيًا، و--all لكل الأيام",
     "python3 studio.py logs"),
    ("analyze", "تحليل آخر فيديو منشور بأرقام حقيقية (فيسبوك + يوتيوب) واقتراحات تحسين؛ ومع --dna تحليل DNA فيروسي: درجة الهوك (0–10) والإيقاع (متوسط طول اللقطة) وفواصل الصمت وكثافة الكلمات وحكم «ليه نجح / إيه الناقص» مربوطًا بالأرقام الحقيقية",
     "python3 studio.py analyze --dna --video ~/workspace/videos/najjar-full.mp4 --hook \"الهوك\""),
    ("ideas", "مولّد أفكار قصص بأسلوب الصفحة (هوك صادم + عبرة + سؤال ختام) مع منع تكرار أي عنوان في الطابور — --add يضيف الفكرة للطابور",
     "python3 studio.py ideas --count 5"),
    ("batch", "دفعة جماعية: إنتاج القصص التالية من الطابور في تشغيل واحد (كل فيديو: إنتاج + فحص + مصغرة + تسجيل)؛ مسار Veo يفحص الرصيد ≥120 أولًا ويحترم سقف Veo — الوضع التجريبي افتراضي يطبع الخطة، والتنفيذ الحقيقي فقط مع --execute",
     "python3 studio.py batch --count 3 --source openmontage --execute"),
    ("scene-plan", "خطة مشاهد Veo لقصة من الطابور قبل إنفاق أي رصيد: 6 موجهات × 8 ثوانٍ × 20 وحدة = 120 وحدة، مع فحص السقف والرصيد ورفض التجاوز برسالة عربية",
     "python3 studio.py scene-plan --story 4"),
    ("daily", "أمر اليوم الواحد: إنتاج + فحص + مصغرة + نشر المنصتين + نص أول تعليق — افتراضيًا وضع تجريبي، والتنفيذ فقط مع --execute؛ ومسار Veo يطبع خطة المشاهد ويحفظها ويتوقف للموافقة (أو --auto-approve)، والكرون يمضي داخل السقف بلا توقف",
     "python3 studio.py daily --slot evening --dry-run"),
    ("ab", "اختبار A/B: هوكان ومصغرتان لفيديو واحد + سجل الزوج — فيسبوك ويوتيوب بلا A/B أصلي، فالأداة تولّد النسخ وتتتبع المقارنة؛ ومع --cost-per-video N يسجّل تقدير تكلفة وحدات Veo لكل بديل",
     "python3 studio.py ab --video ~/workspace/videos/out.mp4 --hook-a \"الهوك الأول\" --hook-b \"الهوك الثاني\" --cost-per-video 120"),
    ("ab-results", "قارن مشاهدات نسختي اختبار A/B بعد نشرهما (فيسبوك + يوتيوب)",
     "python3 studio.py ab-results"),
    ("update", "جلب آخر إصدار من GitHub وتطبيق الملفات المتغيرة فقط، مع نسخة احتياطية أولًا — config.yaml والأسرار والطابور وبيانات العملاء لا تُمسّ أبدًا",
     "python3 studio.py update --dry-run"),
    ("backup", "نسخة احتياطية zip: الإعداد + الطابور + طلبات العملاء + سجلات التشغيل — مع احتفاظ بآخر 7 نسخ فقط (الأقدم تُحذف تلقائيًا)، وكرون يومي تلقائي للنسخ يُبلَّغ فقط عند الفشل",
     "python3 studio.py backup --keep 7"),
    ("restore --backup", "استرجاع الإعداد والطابور وطلبات العملاء من نسخة backup — بنسخة أمان تلقائية من الحالة الحالية وتأكيد قبل الكتابة؛ والأسرار (توكن يوتيوب/client_secrets) لا تُستعاد أبدًا",
     "python3 studio.py restore --backup backups/backup-20261122-084541.zip --dry-run"),
    ("balance", "توقع رصيد Veo بالأيام: كم يوم يكفي + تاريخ النفاد + توصية — من الرصيد المسجَّل في الإعداد وليس حيًا من API — ويُعرض عمر الرقم دائمًا بجانب القيمة، ورصيد أقدم من 24 ساعة يُحذَّر منه؛ ومع --record N --video NAME تسجيل إنفاق فعلي بعد توليد Flow (يسجَّل معه وقت التحديث)، و--history عرض السجل؛ ومع --cap N سقف إنفاق لكل توليد Veo (0 يلغي السقف) — أي توليد متوقع فوقه يُرفض تلقائيًا",
     "python3 studio.py balance --cap 200"),
    ("analyze-ref", "تحليل فيديو مرجعي لمنافس (الهوك وسرعة السرد والختام) — للتعلم فقط",
     "python3 studio.py analyze-ref --url https://www.youtube.com/watch?v=..."),
    ("publish", "نشر فيديو على فيسبوك (Reel) ويوتيوب معًا — أو --dry-run للمعاينة بلا نشر — ويفحص الكابشن أولًا (يرفض أي بوابة متابعة/تعليق) ويعرض الكابشن النهائي قبل النشر؛ ومع --schedule \"YYYY-MM-DD HH:MM\" (بتوقيت القاهرة) يجدول النشر على المنصتين بدل الفوري؛ ومع --platforms tiktok,instagram نشر إضافي على TikTok/Instagram (يتطلب توكنًا عبر tiktok-auth/instagram-auth — بلا توكن يُنشئ حزمة رفع يدوي)",
     "python3 studio.py publish --video ~/workspace/videos/out.mp4 --title \"العنوان\" --schedule \"2026-11-23 19:00\" --dry-run"),
    ("tiktok-auth", "إعداد نشر TikTok: يطبع الخطوات اليدوية الدقيقة (تطبيق مطوّر + موافقة Content Posting API) ويحفظ أي توكن يُعطى في ملف 600",
     "python3 studio.py tiktok-auth"),
    ("instagram-auth", "إعداد نشر Instagram: يطبع الخطوات اليدوية الدقيقة (حساب Business/Creator مربوط بصفحة فيسبوك + Graph API) ويحفظ أي توكن يُعطى في ملف 600",
     "python3 studio.py instagram-auth"),
    ("check", "فحص جودة فيديو قبل النشر (المدة والصمت والصوت والمقاس والشعار) — PASS/FAIL؛ وإن فشل الصمت فالإصلاح بأمر fix-audio",
     "python3 studio.py check --video ~/workspace/videos/out.mp4"),
    ("fix-audio", "إصلاح فجوات الصمت في فيديو تلقائيًا (وصفة عائشة ج2: مزج صوت المشاهد الأصلي مكبَّرًا ليستقر ~-28 ديسيبل + ضجيج وردي خافت 0.05 تحت السرد) — المدة والنص والإيقاع بلا تغيير؛ ويُستدعى تلقائيًا في assemble عند فشل فحص الصمت",
     "python3 studio.py fix-audio --video ~/workspace/videos/out.mp4"),
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
    ("orders confirm", "تأكيد دفع طلب عميل بعد التحقق من التحويل يدويًا — الطلب الـ11 فصاعدًا لنفس العميل (برقم الواتساب) لا يُنتَج إلا بعدها؛ وأول 10 طلبات لكل عميل تجربة مجانية",
     "python3 studio.py orders confirm QS-123456"),
    ("orders trial", "حالة التجربة المجانية لعميل: كم فيديو مجاني بقي له من أول 10 طلبات",
     "python3 studio.py orders trial 01023468196"),
    ("orders list", "عرض طلبات العملاء — اختياريًا بحالة معينة (مثال awaiting_payment لقائمة انتظار الدفع)",
     "python3 studio.py orders list --status awaiting_payment"),
    ("whisper-ass", "كابشنات ASS من faster-whisper (تجريبي — راجع WHISPER-TEST.md)",
     "python3 studio.py whisper-ass --audio narration.wav --out captions.ass"),
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
    lines = ["أوامر studio — المساعدة بالعربية", ""]
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
    return "\n".join(lines) + "\n"


def print_help():
    """اطبع المساعدة العربية."""
    print(help_text(), end="")
