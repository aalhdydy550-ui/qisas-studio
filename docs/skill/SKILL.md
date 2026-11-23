# مهارة وكيل قصص وعبر — توليد فيديو قصة كامل من جملة واحدة

> نسخة الاستوديو: v0.1.39 — أوامر حقيقية فقط من `studio.py`.
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
اللوني، و`--no-watermark` لإلغاء الشعار. معرّف التشغيل
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

## استكشاف الأخطاء

| المشكلة | ماذا تفعل |
|---|---|
| `scene-plan` رفض السقف/الرصيد | قلّل `--clips` أو انتظر تجديد الرصيد (13 ديسمبر) أو استخدم مسار OpenMontage (`--source openmontage` في `batch`) — لا تتجاوز السقف أبدًا |
| فشل `script` (كل مزودي LLM) | أعد المحاولة لاحقًا، أو استخدم `--allow-fallback` للبديل من سيناريو OpenMontage الجاهز |
| `check` فشل | أصلح الملاحظات المطبوعة (صمت/صوت/مقاس) أو `fix-audio` للصوت — لا تنشر فيديو فاشلًا |
| `publish` رفض الكابشن | أعد كتابة الكابشن بالكابشن المقترح المطبوع (بلا بوابة متابعة) — لا تستخدم `--skip-caption-check` إلا بتوجيه صريح |
| `publish` رفض بيان المصدر | ولّد البيان بـ `manifest --video ...` ثم أعد النشر |
