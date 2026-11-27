<!-- Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui) -->
<!-- Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE. -->
<!-- Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md. -->
# مهارة وكيل قصص وعبر — توليد فيديو قصة كامل من جملة واحدة

> نسخة الاستوديو: v0.1.62 — أوامر حقيقية فقط من `studio.py`.
> كل أمر في هذا الملف موجود فعلًا في الاستوديو (تحقّق منه قبل
> الاستخدام بـ `python3 studio.py help-ar`). لا تخترع أوامر ولا
> وسائط غير مذكورة هنا.

## القواعد الصارمة (لا تُخالَف أبدًا)

- **الراوي رجل دائمًا** — السرد بصوت Piper العربي الذكوري
  (`ar_JO-kareem-medium`)؛ لا صوت نسائي ولا صوت آخر أبدًا.
- **الكتابة على الشاشة أسفل الشاشة فقط** — كابشنات ASS متزامنة
  عبارة بعبارة مع السرد؛ لا نص أعلى الشاشة أبدًا.
- **مدة الفيديو 40–60 ثانية** — قصة من جزء أو جزأين، 6 مقاطع
  × 8 ثوانٍ في مسار Veo.
- **الهوك جملة واحدة صادمة** تخفي النهاية، ولا يبدأ برقم أبدًا.
- **عنوان الهوك مكتوب كبيرًا أول 3 ثوانٍ** (منذ v0.1.58 — أمر
  `hook-title`): نص الهوك نفسه من السكريبت (بلا اختراع نص) في
  النطاق الأوسط من الإطار فقط — أبدًا في الثلث العلوي (حيث «لا
  نص أعلى الشاشة أبدًا») وأبدًا متداخلًا مع الكابشنات أسفل
  الصورة؛ وسطرين كحد أقصى × 19 حرفًا للسطر (فالهوك الطويل
  يُختصر لجوهره قبل حرقه).
- **العبرة واضحة** في نهاية القصة، والختام سؤال محيّر يفتح النقاش.
- **الدعوة لطيفة دائمًا**: «الجزء الثاني بكرة 7 مساءً — اعمل
  متابعة عشان يوصلك أول ما ينزل» — ولا تجعل الجزء الثاني
  مشروطًا بمتابعة أو تعليق أبدًا.
- **سطر ثابت في كل وصف نشر**: «عندك قصة حصلتلك؟ ابعتها في
  رسائل الصفحة وهنحكيها باسمك أو بدون اسم.»
- **الهاشتاغات الثابتة**: #قصص_وعبر #قصص_واقعية #قصص_مؤثرة #حكايات.
- لا صور اقتباس داخل الفيديو — بطاقات الاقتباس صور مستقلة فقط.
- لا تذكر منصات منافسة ولا روابط خارجية في نص القصة.
- المصدر الوحيد لقواعد الأسلوب: `lib/prompts/story_system.md`.

## حدود ما لا يفعله الوكيل

- **لا نشر حي بلا تأكيد صريح من المستخدم** — اعرض دائمًا
  `--dry-run` أولًا، وانشر فقط بعد موافقته على العنوان
  والكابشن والموعد.
- **لا توليد Veo بلا رصيد كافٍ** — افحص `balance` و`scene-plan`
  أولًا؛ ورفض السقف أو الرصيد يعني التوقف قبل أي إنفاق، لا
  تجاوزه.
- لا يخترع أرقام أداء ولا ينشر فيديو فشل فحص الجودة (`check`).
- لا يمسّ `config.yaml` ولا الأسرار ولا الطابور إلا بالأوامر
  المخصصة لذلك.

## الخطوات: من جملة واحدة إلى فيديو منشور

### 0. افحص البيئة (مرة في بداية الجلسة)

```bash
python3 studio.py doctor
python3 studio.py llm-status
```

`doctor` يجب أن يكون أخضر (26 فحصًا)؛ و`llm-status` يعرض
سلسلة الذكاء الحالية (OmniRoute ثم Gemini) وأي مزود في تهدئة.

### 1. اكتب القصة — أو اختر قالب بنية جاهزًا

القصة نص قصير: هوك صادم من جملة واحدة، بطل بسيط أمام موقف
صعب، تصعيد، انقلاب/مفاجأة في النهاية، عبرة واضحة، سؤال ختامي.

إن لم تكن لديك قصة جاهزة، استخدم أحد قوالب `lib/story_templates.py`
الثلاثة (محاور مثبتة النجاح عند الصفحة):

| القالب | المحور |
|---|---|
| `relatives_injustice` | ظلم الأقارب والحماة |
| `parents` | برّ/عقوق الوالدين |
| `honesty_charity` | أمانة/صدقة |

```python
from lib import story_templates
outline = story_templates.build_scene_outline(
    "relatives_injustice", "عائشة الأرملة", "عائشة الأرملة",
    "ظلمتها حماتها وطردتها من بيتها")
text = story_templates.render_story_text(outline)
```

أو ولّد أفكارًا جديدة بأسلوب الصفحة (مع منع تكرار أي عنوان
في الطابور):

```bash
python3 studio.py ideas --count 5
python3 studio.py ideas --count 5 --theme "ظلم الحماة"
```

### 2. أضف القصة إلى الطابور

```bash
python3 studio.py queue add --title "عائشة الأرملة" --text-file story.txt --parts 2
python3 studio.py queue validate
```

`--parts 2` لقصة من جزأين (الجزء الثاني بكرة 7 مساءً).
تحقق من الطابور قبل المتابعة — طابور معطوب يوقف `daily` و`batch`.

### 3. ولّد الهوك والعنوان والكابشن

```bash
python3 studio.py script --story anza --allow-fallback
```

`--story` هنا اسم القصة (slug) كما في الأمثلة المدمجة.
يولّد الهوك والعنوان والكابشن عبر سلسلة LLM الحالية
(ddgw ثم Groq ثم Gemini) مع بديل محلي عند الفشل، ويطبع
أيضًا وصف النشر والهاشتاغات (`lib/script_meta.py`).

### 4. خطط مشاهد Veo قبل أي إنفاق (مسار Veo فقط)

```bash
python3 studio.py balance
python3 studio.py scene-plan --story 4 --clips 6
```

- `balance`: الرصيد المسجَّل (ليس حيًا) + تاريخ التجديد.
- `scene-plan`: خطة مكتوبة (6 موجهات × 8 ثوانٍ × 20 وحدة
  = 120 وحدة) مع فحص السقف والرصيد — تُطبع وتُحفظ في
  `runs/` قبل أي إنفاق، ورفضها يوقف التوليد.
- عند غياب نص القصة، تُؤخذ الموجهات من قالب بنية القصة
  (برمجيًا عبر `lib.scene_plan.build_scene_plan_from_template`)
  بدل موجِّهات المسودة.

### 5. أنتج الفيديو

المسار الكامل بأمر واحد (بعد التأكد من الرصيد في الخطوة 4):

```bash
python3 studio.py run --story anza --project anza-part1 --out ~/workspace/videos/out.mp4
```

أو جرّب أولًا بلا مفاتيح وبلا رصيد:

```bash
python3 studio.py run --demo
```

أو خطوة بخطوة (تجهيز أصول مشروع OpenMontage ثم التجميع):

```bash
python3 studio.py produce --project anza-part1
python3 studio.py assemble --run <RUN_ID> --out ~/workspace/videos/out.mp4
```

`assemble` يقبل `--backend concat|headless|mlt|openreel`
(الافتراضي Concat) و`--grade warm|vivid|cinematic` للتدرج
اللوني، و`--no-watermark` لإلغاء الشعار. و`--no-title` (منذ
v0.1.62) يتخطى حرق عنوان الهوك على Concat — والبيان يكتب عنوانًا
فارغًا فيسمح `hook-title` لاحقًا. معرّف التشغيل
(`RUN_ID`) هو مجلد التشغيل في `runs/` الذي أنشأه `produce`.

للدفعات (قصص متتابعة من الطابور — تجريبي افتراضيًا):

```bash
python3 studio.py batch --count 3 --source openmontage
python3 studio.py batch --count 3 --source openmontage --execute
```

ولليوم الواحد (إنتاج + فحص + مصغرة + نشر — تجريبي افتراضيًا):

```bash
python3 studio.py daily --slot evening --dry-run
python3 studio.py daily --slot evening --execute
```

### 6. افحص الجودة والمصغرة قبل النشر

```bash
python3 studio.py check --video ~/workspace/videos/out.mp4
python3 studio.py thumbnail --video ~/workspace/videos/out.mp4 --hook "الهوك الصادم"
python3 studio.py manifest --video ~/workspace/videos/out.mp4 --title "عائشة الأرملة"
```

- `check`: فحص الجودة (المدة والصمت والصوت والمقاس) — فيديو
  فاشل لا يُنشر.
- `thumbnail`: مصغرة 720×1280 بنص الهوك أعلى الصورة.
- `manifest`: بيان مصدر الفيديو — فيديو جديد بلا بيان
  يُرفَض نشره إلا بتجاوز صريح (`--allow-missing-manifest`).

إن ظهر خلل صوتي، أصلحه قبل النشر:

```bash
python3 studio.py fix-audio --video ~/workspace/videos/out.mp4 --out ~/workspace/videos/fixed.mp4
```

### 7. ولّد عنوان النشر ووسومه، ثم انشر (بعد التأكيد)

عنوان النشر ووسومه ووصفه القصير تُولَّد من مكتبة بايثون
`lib/publish_meta.py` (نفس سلسلة LLM في الخطوة 3، مع بديل
محلي صارم بلا شبكة: عنوان «اسم القصة | الجزء X من Y» +
«قصة حقيقية» + الوسوم الثابتة) — **لا يوجد أمر CLI لهذا
بعد**، فتُمرَّر القيم يدويًا لأمر النشر:

```python
from lib import publish_meta
meta = publish_meta.generate_publish_meta(
    {"title": "عائشة الأرملة", "text": "نص القصة",
     "hook": "الهوك الصادم"}, part=1, parts=2)
args = publish_meta.format_for_publish(meta)  # title/caption/tags
```

ثم اعرض الحمولة الدقيقة أولًا (بلا نشر):

```bash
python3 studio.py publish --video ~/workspace/videos/out.mp4 --title "عائشة الأرملة | الجزء 1 من 2" --caption "الوصف القصير" --tags "قصص وعبر,قصص واقعية,قصص مؤثرة,حكايات" --dry-run
```

وبعد موافقة المستخدم الصريحة على العنوان والكابشن والموعد،
انشر (أو جدوِل على موعدي الصفحة 09:00 و19:00 بتوقيت القاهرة):

```bash
python3 studio.py publish --video ~/workspace/videos/out.mp4 --title "عائشة الأرملة | الجزء 1 من 2" --caption "الوصف القصير" --schedule "2026-11-23 19:00"
```

- `--platforms facebook,youtube` هو الافتراضي؛ و`--platforms
  tiktok,instagram` متاح لكن مساراه غير مختبَرين حيًا بعد.
- `--preflight` يفحص مسار يوتيوب فقط (التوكن + جلسة رفع)
  بلا نشر.
- فحص امتثال الكابشن مسبق افتراضيًا — أي بوابة متابعة
  ترفض النشر كله قبل أي فحص فيديو.

### 8. بعد النشر: أول تعليق وتحليل الأداء

```bash
python3 studio.py schedule --watch --post-id <POST_ID> --story anza --slot evening --moral "العبرة: ..." --question "لو كنت مكانه، كنت عملت إيه؟" --execute
python3 studio.py analyze --dna --video ~/workspace/videos/out.mp4 --hook "الهوك الصادم"
```

- `schedule --watch`: ينشر أول تعليق (العبرة + سؤال محيّر
  + موعد الجزء التالي بالدعوة اللطيفة) فور نشر المنشور المجدول.
- `analyze --dna`: تحليل DNA الفيروسي للفيديو المنشور
  بأرقام حقيقية (فيسبوك + يوتيوب) — وحسّن الفيديو التالي
  على ما نقص فيه قبل إنتاجه.

## مثال كامل: من جملة واحدة إلى فيديو

المستخدم: «عايز فيديو عن أرملة ظلمتها حماتها».

```bash
python3 studio.py doctor
python3 studio.py ideas --count 5 --theme "ظلم الحماة"
# اكتب القصة (أو من قالب relatives_injustice) في story.txt
python3 studio.py queue add --title "عائشة الأرملة" --text-file story.txt --parts 2
python3 studio.py script --story anza --allow-fallback
python3 studio.py balance
python3 studio.py scene-plan --story 4 --clips 6
python3 studio.py run --story anza --project anza-part1 --out ~/workspace/videos/aisha-part1.mp4
python3 studio.py check --video ~/workspace/videos/aisha-part1.mp4
python3 studio.py thumbnail --video ~/workspace/videos/aisha-part1.mp4 --hook "الهوك الصادم"
python3 studio.py publish --video ~/workspace/videos/aisha-part1.mp4 --title "عائشة الأرملة | الجزء 1 من 2" --caption "الوصف القصير" --schedule "2026-11-23 19:00" --dry-run
# بعد موافقة المستخدم: نفس الأمر بلا --dry-run
```

## أوامر مساعدة (لا تدخل في خط الإنتاج اليومي)

```bash
python3 studio.py status        # حالة الطبقات الثلاث
python3 studio.py version       # إصدار studio + حالة البعيد
python3 studio.py help-ar       # مساعدة عربية لكل أمر
python3 studio.py backup        # نسخة احتياطية zip
python3 studio.py logs          # آخر التشغيلات ونتائجها
python3 studio.py ab --video ~/workspace/videos/out.mp4 --hook-a "الهوك الأول" --hook-b "الهوك الثاني"
```

## أدوات نمو يوتيوب (منذ v0.1.57 — تشخيص فقط، لا تدخل في خط الإنتاج اليومي)

ستة أوامر عربية من قوائم فحص youtube-agent-skill (تنفيذ أصلي من
الصفر — بلا نسخ كود). كلها خارج بوابتي الترخيص والنجمة، و`--json`
خالص في الستة:

```bash
python3 studio.py seo-check --title "النجار الأمين | قصة حقيقية" --description "قصة حقيقية عن نجار فقير وجد ذهبًا وأعاده لصاحبه." --tags "قصص وعبر،قصص واقعية"
# فحص SEO قبل النشر: العنوان (≤100 حرفًا) + أول سطرين من الوصف (يحملان الوعد — هما مقتطف البحث) + الوسوم (≤15) + اختبار 3 استعلامات هدف — خروج 1 عند أي ملاحظة و0 عند السلامة
python3 studio.py title-lint --title "النجار الأمين | قصة حقيقية" --thumb "أمانة تنجي صاحبها"
# عنوان + مصغرة كوحدة: القطع 60 حرفًا (سطح مكتب) و40 (موبايل)، المصغرة ≤3 كلمات وبلا تكرار للعنوان، العنصر الملموس (رقم أو اسم أو مكان)
python3 studio.py hook-score --hook-file hooks.txt
# تقييم هوكات (أول 15 ثانية هي كل العمل) — أفضل اثنين بالدرجات؛ والتقييم إرشادي (heuristic) لا تنبؤ بالمشاهدات
python3 studio.py viral-rank --videos-file videos.json --top 5
# ترتيب فيديوهات بمضاعف كل قناة على وسيطها الخاص (لا بالمشاهدات الخام) — القناة تحتاج 4 فيديوهات على الأقل
python3 studio.py retention-read --csv retention.csv
# قراءة تصدير احتفاظ YouTube Studio (CSV): تسرب الهوك في أول 30 ثانية (صحي <25%) + المنحدرات + انزلاق الثلث الأوسط — أكبر تسرب + تغيير واحد
python3 studio.py channel-audit --titles-file titles.txt --hooks-file hooks.txt --dates-file dates.txt
# تدقيق قناة ينتهي في إصلاح واحد + 3 أشياء تعمل فعلًا + ما لا يُفعل بعد — من ملفات صريحة فقط (عناوين/هوكات/نصوص مصغرات/تواريخ/تصدير احتفاظ/بيانات نشر)
```

## أدوات شورتس وTikTok (منذ v0.1.58 — تشخيص وقدرات، لا تدخل في خط الإنتاج اليومي)

ستة أوامر عربية من مولدات الشورتس وخطوط التوليد الكاملة
(MoneyPrinterTurbo/OpenReels/ViralMint/tiktok-skills — تنفيذ أصلي
من الصفر، بلا نسخ كود). كلها خارج بوابتي الترخيص والنجمة، و`--json`
خالص في الستة:

```bash
python3 studio.py trend-scout --videos-file videos.json --top-n 5
# كشّاف ترندات أسبوعي: الترتيب بنسب الحفظ والمشاركة ومضاعف القناة (لا بالإعجابات الخام) — القناة تحتاج 4 فيديوهات على الأقل؛ والرعب يُوسم «مستبعد» ولا يُقترح أبدًا؛ والاقتراحات لا تكتب في الطابور
python3 studio.py scene-shorts --video long.mp4 --scenes-file scenes.json --out parts-dir
# قصّ فيديو طويل إلى أجزاء مشهدية 40–60 ثانية (مشاهد كاملة فقط) + تقرير مقارنة (الفيديو الكامل مقابل الأجزاء) — الجزء غير المكتمل يُسجَّل ولا يُحذف
python3 studio.py tiktok-check --title "النجار الأمين | قصة حقيقية" --caption "..." --hook "ظلم أخاه وسرق ميراثه — فماذا فعل الله به؟"
# فحص قبل النشر على TikTok: هوك 3 ثوانٍ (≥6 — ويحتاج ملف قصة لقياس العائد) + كابشن (4 وسوم + عبرة + بلا رابط يوتيوب + بلا بوابة) + ترند + خطة الأسبوع — خروج 1 عند أي ملاحظة و0 عند السلامة
python3 studio.py script-check script.json --json
# بوابة سكريبت نصية قبل الإنتاج: هوك + عبرة + سؤال ختامي + 5–7 مشاهد + بلا بوابة + بلا موسيقى + نهايات معلنة للأجزاء — خروج 1 عند ملاحظة؛ والمدة «غير مقاسة» بلا عبارات موقوتة أو صوت سرد
python3 studio.py topic-brief --input brief-input.json --json
# موجز بحث لموضوع قبل الكتابة: أنماط رابحة + هوكات ناجحة + عناوين الطابور الحالية + زوايا غير مغطاة — نص جاهز لبرومبت الكتابة
python3 studio.py hook-title --video short.mp4 --title "ظلم أخاه وسرق ميراثه؟"
# عنوان هوك كبير مكتوب أول 3 ثوانٍ على شورت جاهز — التغيير الوحيد في ثوابت الصيغة بهذه الجولة (قرار 10:09): النطاق الأوسط فقط، أبدًا في الثلث العلوي أو منطقة الكابشنات؛ ومع --json يعرض المواصفة فقط بلا حرق. وإن أعلن بيان الفيديو عنوانًا محروقًا متداخلًا يرفض الحرق إلا مع --force (منذ v0.1.59)، ورسالة الرفض نفسها تسمّي `--force` منذ v0.1.62. التطبيق التلقائي في مسار البناء خطوة لاحقة — اليوم خطوة مستقلة على الشورت الجاهز.
```

## أدوات موثوقية SRE (منذ v0.1.60 — تشخيص فقط، لا تدخل في خط الإنتاج اليومي)

ستة أوامر عربية من أنماط OpenSRE (Tracer-Cloud/opensre، Apache-2.0 —
الأنماط فقط، تنفيذ أصلي من الصفر بالمكتبة القياسية، بلا نسخ كود).
كلها خارج بوابتي الترخيص والنجمة، و`--json` خالص في الستة:

```bash
python3 studio.py reliability-report --runs-json runs.json --window-days 30 --json
# تقرير موثوقية 30 يومًا من سجلات تُمرَّر كبيانات: معدلات فشل حسب النوع (test-suite/cron/publish/build) والفئة (بيئة/كود/خارجية/غير معروف) + الزمن الأحمر + MTTR/MTBF — السجل التالف يُتخطى ويُعدّ ولا يُسقط التقرير
python3 studio.py failure-classify --text "ModuleNotFoundError: No module named 'piper'" --json
# تصنيف نص فشل إلى بيئة/كود/خدمة خارجية/غير معروف — الأولوية موثقة: إشارات البيئة أولًا (PYTHONNOUSERSITE، حزم ممسوحة، melt مفقود، قفل apt، SIGTERM)، ثم الخارجية (429/403/حاجز بوت)، ثم الكود (AssertionError وTraceback في lib/)
python3 studio.py incident-probe --context-json incident.json --json
# حلقة تحقيق في حادث: 3 فرضيات دائمة (بيئة/كود/خدمة خارجية) لا تُحذف أبدًا + سبب جذري محتمل بأدلة مقتبسة (≤200 حرف) + خطوات تالية — قراءة فقط، بلا إصلاح تلقائي؛ ومع --mask تُخفى المعرّفات في المخرج (والـmapping في --mapping-out فقط، ولا يُطبع أبدًا)
python3 studio.py id-mask --text "راسل ayman_201511@yahoo.com" --json
# إخفاء معرّفات قابل للعكس: بريد ومعرّفات طويلة (12+ رقمًا) وهواتف برموز حتمية ([EMAIL:1]...) — والـmapping لا يُطبع أبدًا في stdout؛ ومع --redact حجب نهائي لا عكسي للأسرار (sk-... وghp_... وBearer) بلا mapping؛ ومع --unmask --mapping FILE يُعاد النص الأصلي
python3 studio.py runbook-check --runbook env-restore --json
# فحص دفتر تشغيل مقروء آليًا (خطوات قراءة فقط: أداة/ملف/رابط رمزي/استيراد بايثون/حقل JSON/مدة فيديو) — خروج 1 عند أي خطوة فاشلة؛ والدفتران المدمجان: env-restore (استعادة البيئة بعد ريستارت) وpublish-failure (فشل النشر) — والمسارات النسبية فيهما عبر {root}
python3 studio.py failure-drill --all --json
# تدريب على الأعطال: يحاكي melt مفقودًا ورابط piper مكسورًا وPillow قديمة داخل مجلد مؤقت فقط ويتحقق أن الكشف يعمل — بلا أي مساس بالبيئة الحقيقية (لا HOME ولا PATH ولا ملفات خارج workdir) — خروج 1 إن فشل أي drill في الكشف
```

## قدرات التنسيق متعدد الوكلاء (منذ v0.1.63 — من أنماط OpenMausBot، تنفيذ أصلي من الصفر، بلا نسخ كود؛ ومزايا enterprise مستبعدة نهائيًا)

```bash
python3 studio.py approval show
# مستويات الموافقة الخمسة (ask/edits/auto/full/custom)؛ والافتراضي ask؛ وأرضية أمان ترفض دائمًا: حذف منشور/إنفاق مال/تغيير مفاتيح/حذف ملفات مشروع — حتى تحت full
python3 studio.py team apply --dry-run
# ملف team.yaml: فرق وبوتات (نموذج INSTANCE/MODEL، جهد، موافقة، حاسوب local|off، أدوات allow/deny، أسرار {env|file} فقط) — وcheck خروج 6 عند تغيير معلّق، وإعادة التطبيق تطبع No changes. و`cwd` يقبل توسيع متغيرات البيئة `$VAR`/`${VAR}` — وأشهرها `${STUDIO_HOME}` لجذر الاستوديو (يضبطه أمر `team` تلقائيًا إن لم يكن معرَّفًا) — والمسار بعد التوسيع يجب أن يكون كاملًا وموجودًا.
python3 studio.py doctor --json
# تقرير JSON {ok, problems, warnings, checks:[{id,status,message,fix}]} — وخروج 7 عند أي FAIL؛ و--fix يصلح ما يمكن ثم يعيد الفحص؛ وفحوص مضيف (شبكة/قرص/melt/piper)
python3 studio.py usage caps show
# حدود استخدام (يومي/شهري بالدولار والرموز) — الرفض 429 + Retry-After، و409 برمز spend_cap للرسالة المباشرة تحت everything؛ وتحت unattended (الافتراضي) المباشر يعمل دائمًا
python3 studio.py keys set --provider NAME --token-file FILE
# مفاتيح كتابة فقط: تُختبر عند الحفظ والمرفوض لا يُحفظ؛ والتدوير بعد نجاح الاختبار فقط؛ والمفتاح عبر --token-file أبدًا --token على سطر الأوامر
python3 studio.py brief show
# الموجز اليومي (Needs you / Your day / Important emails / Routines) — والفارغ لا يُنشر أبدًا؛ والكرون 08:00 ليس في الشجرة بعد
python3 studio.py webhook serve
# مرفوض والراية webhookReceiver مطفأة (الافتراضي) — لا مستمع حي بلا قرار صريح لاحق
```

- كل الأوامر الجديدة تقبل `--json` و`--quiet` (رايتا الجذر) وترجع رمز خروج من ع1 (0/1/2/3/4/5/6/7/8/130)؛ و`ask` غير التفاعلي يُسجَّل ويُرفض برمز 3 بلا تعليق؛ وبلا ملف إعداد موافقة يمضي النشر كما كان بلا أسئلة. وكل الأوقات المعروضة Africa/Cairo. والأوامر الكاملة: `approval` و`team` و`routines` و`check-back` و`usage` و`models` و`round-pack` و`handoffs` و`keys` و`sentinel` و`control` و`inspect` و`read-log` و`search-log` و`send-work` و`wait-job` و`interrupt-job` و`switch-model` و`wait` و`events` و`brief` و`workers` و`export` و`features` و`triage` و`recipe` و`webhook` و`setup` و`router test`.

## إصلاحات v0.1.62 (جولة إصلاح — لا أوامر جديدة)

- `assemble --no-title`: يتخطى حرق عنوان الهوك على خلفية Concat؛ والبيان يكتب عنوانًا فارغًا فيسمح `hook-title` لاحقًا. مسار `run`/`produce` الافتراضي بلا تغيير.
- رسالة رفض حارس `hook-title` تسمّي راية CLI ‏`--force` (لا `force=True` البايثونية).
- هندسة نص MLT: `halign` يتجاهله MLT 7.22 تمامًا (وريندرات 0/1/2 متطابقة بالبايت) والارتفاع وحده لا يوسّط — فسطور الهوك والعبارات والهوك الافتراضي متمركزة الآن بهندسة مقاسة بخط النص نفسه (PIL)، وارتفاع صندوق الهوك 150 لا 58 (58 كان يقصّ العنوان)؛ والعبارات الأوسع من العرض الآمن تحتفظ بالهندسة القديمة.

## أدوات SEO من GuinRank (منذ v0.1.61 — تشخيص فقط، لا تدخل في خط الإنتاج اليومي)

سبعة أوامر عربية من طرق GuinRank (أداة SEO تجارية مصرية، تأسست
2020، guinrank.com — مغلقة بلا مستودع وبلا API: الطرق فقط، تنفيذ
أصلي من الصفر بالمكتبة القياسية، بلا نسخ كود). كلها خارج بوابتي
الترخيص والنجمة، و`--json` خالص في السبعة، وقراءة فقط بلا شبكة
وبلا LLM وبلا عشوائية — والمقاييس يزوّدها المشغّل من vidIQ وبحث
الترند، وأي قيمة غير مقاسة «غير مقاس» بلا أرقام مخترعة:

```bash
python3 studio.py keyword-analyze --keyword "قصص" --metrics-json metrics.json --json
# تحليل كلمة مفتاحية: صعوبة 0–100 = 0.60×المنافسة + 0.40×قوة SERP + حكم استهداف/حذر/تجنّب؛ و--keywords-json للدفعية (قائمة {keyword, metrics?}) — المقاييس: volume وcompetition وgrowth_pct وserp
python3 studio.py content-optimize --title "عنوان القصة" --keyword "قصص" --body-file body.txt --phrases-json phrases.json --json
# درجة محتوى 0–100 لعنوان/وصف/نص ضد كلمة مفتاحية — **النطاق الصحي 55–75 لا 100%**: فوق 75 خطر حشو كلمات وبلا توصية إضافة كلمات؛ والعبارات الموصى بها {phrase, used_by_top} من بحث المشغّل
python3 studio.py keyword-generate --seed "الصدقة" --corpus-json corpus.json --limit 20 --json
# توليد كلمات ذات صلة من بذرة بقوالب عربية حتمية من مجال القصص + corpus اختياري من كلمات vidIQ ذات الصلة — والبادئات تُتخطى حين تكون البذرة نفسها كلمة فئة (قصص/قصة/حكاية/حكايات) فلا «قصص قصص» أبدًا
python3 studio.py micro-niche --niches-json niches.json --library-json library.json --json
# تخصصات دقيقة قليلة المنافسة: ترتيب بدرجة فرصة من حجم الطلب والمنافسة وتغطية مكتبتنا — المدخل {name, keywords} (أو قاموس فيه niches ومكتبة library)
python3 studio.py page-analyze --page-json page.json --json
# تحليل صفحة/فيديو (عنوان + وصف + وسوم + مدة + رابط + كلمة مستهدفة اختيارية) بدرجة 0–100 واقتراحات مرتبة بالأولوية
python3 studio.py fresh-keywords --trends-json trends.json --days 7 --json
# كلمات اليوم الطازجة: ترتيب بالحداثة والنمو، واستبعاد ما تجاوز نافذة الأيام — المدخل {keyword, growth_pct?, volume?, date, source?}؛ و--today تاريخ مرجعي YYYY-MM-DD
python3 studio.py topical-authority --library-json library.json --json
# قياس سلطة الموضوع: تغطية 12 موضوعًا من مجال القصص وعمقها عبر مكتبة قصصنا {title, topic?} وكشف الفجوات — و--topics-json لخريطة مواضيع مخصصة
```

## استكشاف الأخطاء

| المشكلة | ماذا تفعل |
|---|---|
| `scene-plan` رفض السقف/الرصيد | قلّل `--clips` أو انتظر تجديد الرصيد (13 ديسمبر) أو استخدم مسار OpenMontage (`--source openmontage` في `batch`) — لا تتجاوز السقف أبدًا |
| فشل `script` (كل مزودي LLM) | أعد المحاولة لاحقًا، أو استخدم `--allow-fallback` للبديل من سيناريو OpenMontage الجاهز |
| `check` فشل | أصلح الملاحظات المطبوعة (صمت/صوت/مقاس) أو `fix-audio` للصوت — لا تنشر فيديو فاشلًا |
| `publish` رفض الكابشن | أعد كتابة الكابشن بالكابشن المقترح المطبوع (بلا بوابة متابعة) — لا تستخدم `--skip-caption-check` إلا بتوجيه صريح |
| `publish` رفض بيان المصدر | ولّد البيان بـ `manifest --video ...` ثم أعد النشر |
