<!-- Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui) -->
<!-- Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE. -->
<!-- Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md. -->
# أصوات الراوي (Piper) — وتراخيصها

الراوي رجل دائمًا، في العربية والإنجليزية. هذا الملف هو المرجع
الوحيد لترخيص كل صوت: **ترخيص المحرك (Piper) ليس ترخيص الصوت**
— كل صوت يحمل ترخيص التسجيلات التي دُرّب عليها، ويُقرأ من بطاقة
نموذجه (MODEL_CARD) قبل أي شحن. لا يُفترض أن أي صوت حر تجاريًا.

## جدول الأصوات

| اللغة | الموديل | الجنس | الحجم | الترخيص | تجاري؟ |
|---|---|---|---|---|---|
| العربية (ar_JO) | `ar_JO-kareem-medium` | رجل | medium (~63 ميجا) | غير موثَّق بعد (انظر أدناه) | يُعامل كغير تجاري حتى يُحسم |
| الإنجليزية (en_US) | `en_US-ryan-medium` | رجل | medium (~63 ميجا، 22050 هرتز) | **CC BY-NC-SA 4.0** | **لا — شخصي/تجريبي فقط** |

ملفات الموديلات في `~/workspace/tts-models/` (كل موديل ملف `.onnx`
ومعه `.onnx.json`). الصوت الإنجليزي يُختار صراحةً فقط
(`synthesize_long(..., lang="en")` أو `--lang en` بعد ربط CLI)؛
والعربي هو الافتراضي دائمًا. `en_US-lessac-medium` أنثى فلا تصلح
راويًا أبدًا — لا تُستخدم هنا.

## ترخيص `en_US-ryan-medium` — حرفيًا من بطاقته

بطاقة النموذج (MODEL_CARD) في مستودع الأصوات الرسمي
`rhasspy/piper-voices` — المسار داخل المستودع:
`en/en_US/ryan/medium/MODEL_CARD`. نص البطاقة حرفيًا (حقل الترخيص
وسطرا الإسناد):

> | License | CC BY-NC-SA 4.0 |
>
> Trained on Ryan Speech dataset. Fine-tuned from lessac medium.
>
> Re-hosted from rhasspy/piper-voices.

أي: الصوت مدرَّب على **مجموعة Ryan Speech**، ومُصقَّل (fine-tuned)
من صوت lessac medium، وترخيصه هو **Creative Commons
Attribution-NonCommercial-ShareAlike 4.0 International**
(‏CC BY-NC-SA 4.0) — نص الرخصة:
https://creativecommons.org/licenses/by-nc-sa/4.0/

### ما يعنيه ذلك

- **إسناد (BY):** يجب ذكر المصدر (Ryan Speech / Piper) عند
  الاستخدام.
- **غير تجاري (NC):** **يُمنع الاستخدام التجاري** — لا يُستخدم صوت
  ryan في فيديوهات تُباع للعملاء، ولا في أي منتج مدفوع، ولا في
  محتوى يُحقَّق منه ربح مباشر.
- **المشاركة بالمثل (SA):** أي عمل مشتق يُنشر بالرخصة نفسها.

### القيد الصريح — اقرأه قبل الشحن

**صوت `en_US-ryan-medium` للاستخدام الشخصي/التجريبي فقط، ولا
يُشحن للعملاء التجاريين.** المسار الإنجليزي في الاستوديو
(القصة الإنجليزية العينة، والعرض التجريبي) استخدام غير تجاري
مشروع؛ أما فيديو عميل مدفوع بالإنجليزية فيحتاج صوتًا بترخيص
تجاري صريح (خيار لاحق — مثل Kokoro، Apache 2.0 — خارج هذه
الجولة). ترخيص الاستوديو نفسه (PolyForm Noncommercial) لا
يغيّر ترخيص الصوت ولا يبيح تجاوزه.

## ترخيص `ar_JO-kareem-medium` — غير موثَّق بعد

بطاقة kareem لا تذكر ترخيصًا مستقلًا («See source» — تحيل إلى
المصدر)، وسلالته من صوت Lessac (تسجيلات للاستخدام غير التجاري/
البحثي). لذلك يُعامل kareem أيضًا **كغير تجاري حتى تُقرأ بطاقته
حرفيًا** وتُوثَّق هنا. هذا قيد احترازي موثَّق، لا ترخيصًا مُختلقًا.

## كيف وُثّق ترخيص ryan (2026-11-26)

- الجلب المباشر لبطاقة النموذج الرسمية من
  `rhasspy/piper-voices` رُدّ بـ**HTTP 429** (تحديد معدل) في
  2026-11-26 — فلم تُقرأ البطاقة الرسمية مباشرةً في هذه الجولة.
- البطاقة المعاد استضافتها حرفيًا من المستودع الرسمي — صفحة
  Trelis/piper-en-us-ryan-medium (تشهد: «Re-hosted from
  rhasspy/piper-voices»):
  https://huggingface.co/Trelis/piper-en-us-ryan-medium
- تأكيد مستقل ثانٍ — تقرير تقني قرأ كل بطاقة صوت في المستودع
  الرسمي (المراجعة c10ece1، أكتوبر 2026)، ويسجّل:
  «`en_US-ryan-medium` … Non-commercial CC BY-NC-SA 4.0»:
  https://loudness.ai/research/piper-tts-voices-ranked/
  (التقرير الكامل:
  https://loudness.ai/assets/research/piper-voices-v1/LA-RB-2026-003-en.pdf)
- تأكيد مستقل ثالث — صفحة إعادة استضافة Ryan high تقتبس البطاقة
  الأصلية: «The original Ryan voice card identifies the
  RyanSpeech dataset and states **CC BY-NC-SA 4.0** for that
  dataset»:
  https://huggingface.co/Autognosi/piper-en_US-ryan-high-int8

المصادر الثلاثة متفقة على الترخيص نفسه؛ وإن اختلف أي مصدر
لاحقًا تُراجَع هذه الصفحة أولًا قبل أي استخدام تجاري.
