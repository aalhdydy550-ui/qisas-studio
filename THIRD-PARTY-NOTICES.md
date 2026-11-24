<!-- Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui) -->
<!-- Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE. -->
<!-- Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md. -->
# إشعارات الطرف الثالث — Third-Party Notices

هذا المشروع (qisas-studio) كود تنسيق أصلي مرخّص PolyForm Noncommercial 1.0.0
(انظر `LICENSE`). وهو **لا ينسخ كود** أي مشروع من المشاريع التالية — بل
يستدعيها كأدوات خارجية وقت التشغيل. الإشعارات التالية التزامًا بشروط
رخصها وللتوثيق.

## الأدوات المنسَّقة (لا يُوزَّع كودها هنا)

- **OpenMontage** — خط الإنتاج (بحث وسيناريو وسرد وصور)
  — https://github.com/OpenMontageInc/OpenMontage — ‏AGPL-3.0
- **Concat** — التجميع النهائي القابل للتعديل
  — https://github.com/jub0t/Concat — ‏AGPL-3.0
- **OmniRoute** — طبقة الذكاء (هوك/عناوين عبر نماذج مجانية)
  — https://github.com/ChrisCompton/omniroute — ‏MIT

## المنطق المُعاد تنفيذه (إسناد مطلوب)

- **Capite** — منطق تحويل توقيتات الكلمات إلى كابشنات ASS
  (ملف `lib/capite_captions.py`)
  — https://github.com/muneebkhan08/Capite — ‏MIT License
  — Copyright (c) 2026 Capite Contributors
  — ملاحظة: كود Capite نفسه لم يُشغَّل ولم يُثبَّت ولم يُنسخ حرفيًا في
    هذا المشروع؛ أُعيد تنفيذ الحد الأدنى من منطقه بعد قراءته نصيًا
    فقط، والمصدر مذكور أيضًا في رأس الملف. نص رخصة MIT الكامل في
    مستودع Capite على الرابط أعلاه.

## مكتبات وأدوات مساعدة (تُستدعى وقت التشغيل فقط)

- **faster-whisper** — توقيتات كلمات للكابشنات — MIT
- **Auto-Editor** — قص صمت الصوت الخام — Public domain (Unlicense)
- **MoviePy** — تركيبات وتأثيرات — MIT
- **MLT / melt** — خلفية تجميع بديلة — LGPL
- **LosslessCut** — القص بلا إعادة ترميز (العملية نفسها عبر ffmpeg) — GPL-2.0
- **yt-dlp** — جلب بيانات الفيديو المرجعي للتحليل الخاص — Public domain (Unlicense)
- **Piper TTS** — توليد السرد الصوتي — GPL-3.0 (نماذج الأصوات تحمل
  رخصها الخاصة ولا تُوزَّع في هذا المستودع)
- **Ollama** — اختُبر كنموذج محلي فقط ولم يُدمج — Apache-2.0
- **Supertonic 3** — راوٍ عربي ثانٍ اختياري (الصوت M1 فقط،
  عبر `lib/supertonic_voice.py`) — النموذج **OpenRAIL-M**
  (BigScience Open RAIL-M، 18 أغسطس 2022)؛ وكود الـSDK ‏MIT
  — https://huggingface.co/Supertone/supertonic-3
  (المستودع الرسمي `Supertone/supertonic-3`؛ الكود
  https://github.com/supertone-inc/supertonic — حزمة PyPI
  ‏`supertonic` ‏1.3.1). نسخة الرخصة الكاملة مشحونة في
  `lib/supertonic/LICENSE.txt` (المادة 4(ب): تُسلَّم نسخة
  لكل متلقٍّ عند التوزيع).

## Supertonic 3 — شروط الرخصة المعمول بها

- **الاستخدام:** التجاري مسموح؛ والمخرجات لك (المادة 6:
  «Licensor claims no rights in the Output you generate»)
  وأنت مسؤول عنها وعن استخداماتها اللاحقة.
- **الإفصاح الإلزامي (الملحق أ(هـ)):** يُحظر توليد/نشر
  محتوى دون إفصاح صريح ومفهوم بأنه مولّد آليًا. عمليًا:
  أي فيديو بصوت Supertonic يجب أن يحمل في وصفه سطر
  «صوت مولّد بالذكاء الاصطناعي» (الثابت `DISCLOSURE_LINE`
  في `lib/supertonic_voice.py`).
- **قيود الاستخدام المنقولة عند التوزيع (المادة 4(أ)):**
  قيود الاستخدام (المادة 5 / الملحق أ) **يجب** تضمينها
  كبند نافذ في أي اتفاقية قانونية تحكم استخدام/توزيع
  النموذج أو مشتقاته، مع إشعار المستخدمين اللاحقين بأن
  النموذج خاضع للمادة 5. ومن تلك القيود: حظر الانتحال
  (الملحق أ(ز) — deepfakes دون موافقة)؛ والمشروع يستخدم
  الأصوات المسبقة الاصطناعية فقط (M1) ولا يستنسخ أي صوت.
- **النموذج نفسه لا يُوزَّع هنا:** ملفاته (386MB) تبقى في
  كاش الجهاز (`~/.cache/supertonic3`) ولا تُنسخ إلى الشجرة.

## ما ليس في هذا المستودع

لا تُوزَّع هنا: القصص ولا الفيديوهات ولا الصور ولا الأصوات ولا المفاتيح
ولا بيانات الاعتماد — كلها مستثناة في `.gitignore`.
