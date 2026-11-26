<!-- Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui) -->
<!-- Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE. -->
<!-- Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md. -->
# الحركة — قاعدة «التمديد بالإطار الأخير»

> **القاعدة: كل مقطع حركة يبدأ بآخر إطار من سابقه.**
> مقطع الفصل التالي لا يعيد البدء من الصورة الثابتة نفسها، بل من آخر
> إطار عُرض من المقطع السابق — فتستمر الحركة بلا قفزة للخلف.

## أين تُقرأ `first_frame` في المانيفست

يقرأها `load_motion_manifest` في `lib/motion_clips.py` من مصدرين:

- **JSON:** `generations_list[].first_frame` لكل توليد (مثال:
  `"images/long/img1-wide.jpg"`). حقل `first_frame_source` في
  المانيفست الحقيقي حقل إضافي يتجاهله المحمّل.
- **CSV:** عمود `first_frame` في كل صف توليد.

توليد مذكور في مقطع بلا صف في `generations_list` يُبنى صفه من
المعرّف نفسه وبـ `first_frame` فارغ — فيُكتشف بالتدقيق أدناه
كـ«سلسلة غير موثقة» لا كقيمة صحيحة.

## ما هو متحقق فعلًا في الكود

1. **داخل المقطع الواحد — التوليدان a/b مستقلان من نفس الإطار
   الأول** (قفزة موثقة، ليست استمرارًا): `plan_clip_segments`
   يستخدم a أولًا ثم بداية b لباقي المدة؛ ويثبته
   `test_need_7587_uses_a_full_then_b_start`.
2. **عند غياب التغطية — يُجمَّد آخر إطار في التوليد a:**
   مقطع `freeze` مصدره `a_path` في `plan_clip_segments`،
   ويحوّله `improve_motion` (في `lib/long_video.py`) إلى صورة
   عبر `extract_last_frame`؛ ويثبته
   `test_missing_b_freezes_remainder_with_warning`.
3. **مقاطع الفصل متتابعة لتغطية مدته لكن بلا سلسلة عبرها:**
   `resolve_chapter_motion` يمرّ على مقاطع الفصل بالترتيب،
   وكل مقطع يستخدم `first_frame` الخاص به من المانيفست —
   لا يربط مقطعًا بسابقه.
4. **بذرة التمديد — `resolve_next_first_frame`:** تستخرج آخر
   إطار يُعرض من المقطع السابق (التوليد b إن عُرض، وإلا a؛
   ومقطع `freeze` مصدره a أصلًا) عبر `extract_last_frame`
   القائمة؛ والمسار الافتراضي
   `<motion_dir>/<prev_clip_id>-last-frame.jpg`. هذه الدالة
   تنتج البذرة فقط — لا تولّد المقاطع ولا تغيّر التخطيط.
5. **تدقيق السلسلة — `check_first_frame_chain`:** فحص بيانات
   نقي (بلا قراءة ملفات) على ترتيب عرض معطى، يرجع تحذيرات
   عربية عند: توليد بلا `first_frame` مصرّح، أو توليدي
   المقطع الواحد من إطارين أولين مختلفين، أو مقطعين
   متتابعين يتشاركان `first_frame` نفسه (أي التالي يعيد
   البدء من نفس الصورة الثابتة بدل آخر إطار لسابقه).
   يُثبته `TestCheckFirstFrameChain`
   و`TestResolveNextFirstFrame` (14 اختبارًا جديدًا).

## القيد الصريح — ما هو مؤجل ولماذا

**المانيفست الحقيقي لا يطبّق القاعدة، ولا يمكن للكود إصلاح
ذلك بأثر رجعي.** الدليل (مانيفست
`~/workspace/flow-eval/phase1-wan-motion/manifest.json`،
81 مقطعًا و133 توليدًا، فحص 2026-11-26):

- قاعدة التوليد نفسها تنص صراحةً على العكس:
  `generation_rule: "…a second 5.04 s generation from the SAME
  first frame… (second take, not a continuation)"`.
- `check_first_frame_chain` على فصول 1–6 يرجع **59 تحذيرًا**:
  فصل 1: 8 تحذيرات (C01–C09 كلها من
  `images/long/img1-wide.jpg`)، فصل 2: 13، فصل 3: 8،
  فصل 4: 17، فصل 5: 9، فصل 6: 4 — أي كل زوج متتابع داخل
  الفصل تقريبًا يبدأ من الصورة الثابتة نفسها.
- التوليد نفسه (Wan) يجري خارج هذه الشجرة على GPU؛
  والمقاطع المولَّدة فعلًا لا يمكن أن تبدأ من آخر إطار
  لسابقها إلا بإعادة توليدها من البذرة الصحيحة.

**الحل المقترح للجولة التالية (جولة توليد، لا جولة كود):**
لكل مقطع تالٍ في فصل، يُستخرج آخر إطار من سابقه بـ
`resolve_next_first_frame`، ويُمرَّر كمدخل image-to-video
لتوليد Wan، ثم يُسجَّل مساره في `first_frame` للمانيفست
الجديد؛ وبعدها يُعاد تدقيق المانيفست بـ
`check_first_frame_chain` حتى يرجع قائمة فارغة لكل فصل.

**لم يُفرض الفحص داخل `resolve_chapter_motion` عمدًا:**
إضافة تحذيرات السلسلة عند كل عرض كانت ستغيّر سلوك التخطيط
القائم وتُغرق تقارير المقاطع المولَّدة فعلًا بتحذيرات لا
يملك العرض إصلاحها — الفحص أداة تدقيق لجولة التوليد،
لا فحص يُفرض عند العرض.

## حدود الفحص

- المقارنة على سلاسل `first_frame` النصية فقط: نسخة أُعيد
  ترميزها من الإطار نفسه باسم مختلف لن تُكتشف؛ مقارنة
  البكسلات خارج النطاق.
- ترتيب `clip_ids` الممرَّر لـ `check_first_frame_chain`
  هو ترتيب العرض؛ ترتيب مختلف يعطي نتيجة مختلفة.
- `resolve_next_first_frame` يحتاج ملف التوليد الأول
  موجودًا (يرفع `MotionError` عند غيابه، كـ
  `plan_clip_segments`)، و`ffmpeg` لاستخراج الإطار.

## مثال استخدام

```python
from lib import motion_clips

manifest = motion_clips.load_motion_manifest("manifest.json")

# تدقيق مانيفست جولة توليد جديدة قبل اعتماده:
warnings = motion_clips.check_first_frame_chain(
    manifest, ["C01", "C02", "C03"])
assert not warnings, warnings

# بذرة المقطع التالي في جولة التوليد:
seed = motion_clips.resolve_next_first_frame(
    "C01", manifest, "motion_dir")
# seed == "motion_dir/C01-last-frame.jpg" — يُمرَّر كـ first_frame
# لتوليد C02، ثم يُسجَّل في المانيفست.
```
