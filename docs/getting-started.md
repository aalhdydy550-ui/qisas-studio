# ابدأ هنا — من التثبيت إلى أول فيديو

دليل المستخدم الجديد في **qisas-studio**: استوديو إنتاج فيديوهات قصص
عربية قصيرة (فيسبوك + يوتيوب Shorts) بأمر واحد. النسخة الإنجليزية:
[`getting-started-en.md`](getting-started-en.md).

> **الوقت المتوقع:** ~15 دقيقة من التثبيت إلى أول فيديو تجريبي.
> **التكلفة:** $0 للمسار المجاني — بلا مفاتيح ولا رصيد.

## 1) ما هذا المشروع؟

`studio` طبقة تنسيق واحدة تجمع ثلاث أدوات مثبّتة على جهازك:

| الطبقة | الأداة | دورها |
|---|---|---|
| الذكاء | OmniRoute | الهوك والعنوان والكابشن عبر نماذج مجانية |
| الإنتاج | OpenMontage | السيناريو، السرد، الصور، التركيب |
| التجميع | Concat | مشروع قابل للتعديل + تصدير الفيديو |

النتيجة: فيديو عمودي **720×1280**، مدته **40–60 ثانية**، سرد عربي
بصوت رجل (Piper)، وكتابة على الشاشة متزامنة مع الكلام **أسفل الصورة
فقط**.

## 2) المتطلبات

- **لينكس (أوبونتو)** — على ويندوز استخدم WSL2 + أوبونتو (الطريقة
  المدعومة). على macOS يعمل عمومًا، لكن طبقة الاستعادة التلقائية
  لينكس فقط.
- Python 3 وffmpeg (المثبّت يفحصهما ويطبع PASS/FAIL صادقًا لكل فحص).
- لا تحتاج أي مفتاح API للبدء: المسار المجاني يعمل بلا مفاتيح.

## 3) التثبيت

```bash
# من مجلد studio:
bash setup.sh
```

المثبّت يفحص كل شيء — الأدوات، والموديلات، والخطوط، والشعار،
والخادم — وينشئ `config.yaml` من `config.example.yaml` إن غاب.
آمن لإعادة التشغيل: شغّله مرة أخرى في أي وقت.

ثم افحص الحالة فقط (بلا إصلاح):

```bash
python3 studio.py doctor
```

يجب أن ترى **26/26** فحصًا سليمًا. إن فشل فحص فاقرأ رسالته — فهي
تخبرك بالضبط ما المفقود وكيف تصلحه.

## 4) أول فيديو — التجريبي المدمج

```bash
python3 studio.py run --demo
```

هذا يبني فيديو عمودي حقيقي 720×1280 في ~دقيقة بالمسار المجاني فقط
(Piper + خلفيات مولّدة + شعار) — بلا مفاتيح ولا رصيد ولا إنترنت.
ابحث عن الملف الناتج في المجلد الذي يطبعه الأمر (تحت `runs/` أو
المسار الذي حددته).

تحقق من الفيديو:

```bash
python3 studio.py check --video <مسار-الفيديو>
```

## 5) أول فيديو من قصة حقيقية

مثال جاهز — قصة «العنزة» من مشروع OpenMontage الجاهز:

```bash
python3 studio.py run --story anza --project anza-part1 \
    --out ~/workspace/videos/studio-test.mp4 --allow-fallback
```

كل تشغيل ينشئ مجلدًا في `runs/<story>-<وقت>/` فيه:
`script-ai.json` (الهوك والكابشن)، `manifest.json` (الأصول)،
`assets/` (صور + سرد + كتابة)، و`run-log.json` (الخطوات والأزمنة).

وضع تجريبي يطبع الخطوات دون تنفيذ:

```bash
python3 studio.py run --story anza --project anza-part1 \
    --out ~/workspace/videos/out.mp4 --dry-run
```

## 6) صورة مصغرة

```bash
python3 studio.py thumbnail --video ~/workspace/videos/studio-test.mp4 \
    --hook "طردتني في نص الليل… وبعد سنة باست إيدي!"
```

## 7) النشر — جرّب أولًا بلا نشر حقيقي

```bash
python3 studio.py publish --video ~/workspace/videos/studio-test.mp4 \
    --title "باع بقرته ووزّع البذور | قصة قصيرة" --dry-run
```

`--dry-run` يعرض الحمولة الدقيقة قبل النشر. النشر الحقيقي:
فيسبوك يعمل مباشرة عبر `facebook-cli` المتصل؛ ويوتيوب يحتاج إعداد
OAuth لمرة واحدة — التفاصيل في [`README-AR.md`](../README-AR.md)
قسم «النشر على يوتيوب».

## 8) الخط اليومي — الطابور والدفعات

أضف قصة للطابور بسطر واحد:

```bash
python3 studio.py queue add --title "عنوان القصة" --text-file ~/workspace/story.txt
```

اطبع خطة اليوم بلا إنفاق:

```bash
python3 studio.py daily --dry-run
```

دفعة جماعية (تجريبي افتراضي يطبع الخطة؛ التنفيذ فقط مع `--execute`):

```bash
python3 studio.py batch --count 3 --source openmontage
```

## 9) أوامر تفيدك كل يوم

| الأمر | ماذا يفعل |
|---|---|
| `python3 studio.py status` | حالة الخادم والثنائيات |
| `python3 studio.py doctor` | 26 فحصًا للنظام |
| `python3 studio.py doctor --llm` | حالة أركنة الذكاء الخمسة |
| `python3 studio.py llm-status` | الأركنة بالترتيب والتاريخ |
| `python3 studio.py version` | الإصدار وحالة البعيد |
| `python3 studio.py help-ar` | مساعدة عربية لكل الأوامر |
| `python3 studio.py analyze --dna --video <ملف>` | تحليل DNA الفيروسي لفيديو |
| `python3 studio.py scene-plan --story 4` | خطة مشاهد قبل إنفاق أي رصيد |
| `python3 studio.py balance --cap 600` | سقف إنفاق Veo |

## 10) قواعد ذهبية للمستخدم الجديد

1. **لا مفاتيح في ملفات الإعداد أبدًا.** مفتاح بوابة OmniRoute (لو
   وُجد) يمرَّر عبر متغير البيئة `OMNIROUTE_API_KEY` فقط.
2. **جرّب بـ`--dry-run` قبل أي تنفيذ** — خاصة `publish` و`batch`
   و`daily`.
3. **الكتابة على الشاشة أسفل فقط** — بلا أي نص في الأعلى إطلاقًا؛
   والراوي دائمًا رجل؛ والفيديو العمودي 40–60 ثانية.
4. **لا تلمس الطابور الحقيقي ولا الفيديوهات المنشورة في تجاربك**
   — بيانات اختبار فقط.
5. قبل أي رفع إلى GitHub تحقق:
   `git check-ignore client_secrets.json youtube-token.json config.yaml .env`
   — يجب أن تظهر كلها كمُتجاهَلة.

## 11) استكشاف الأخطاء

| المشكلة | الحل |
|---|---|
| «أمر omniroute غير موجود في PATH» | `npm install -g omniroute` ثم `omniroute serve --no-open --daemon --port 20128` |
| «الخادم لا يرد» | شغّل الخادم بالأمر أعلاه؛ وتأكد بـ `python3 studio.py status`؛ وأوقفه بعد الانتهاء بـ `omniroute stop` |
| «لا يوجد تشغيل بهذا المعرّف» | شغّل `produce` أولًا (أو `run` كاملًا) قبل `assemble` |
| الذاكرة ضيقة | التصدير يحتاج الجهاز فاضيًا؛ لا تشغّل بناء APK أو ريندر آخر بالتوازي |

## 12) أين تذهب بعد ذلك؟

- المرجع الكامل: [`README-AR.md`](../README-AR.md)
- سجل التغييرات: [`CHANGELOG.md`](../CHANGELOG.md)
- أمثلة أوامر ومخرجات متوقعة: [`examples/`](../examples/)
- تريد المساهمة؟ [`CONTRIBUTING.md`](../CONTRIBUTING.md)
- وجدت ثغرة أمنية؟ [`SECURITY.md`](../SECURITY.md) — بلّغ سرًا، لا بـIssue عامة.
- سؤال؟ افتح Issue من قالب «سؤال» (`.github/ISSUE_TEMPLATE/question.md`).
