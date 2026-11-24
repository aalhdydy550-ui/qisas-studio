<!-- Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui) -->
<!-- Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE. -->
<!-- Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md. -->
# مثال: حمولة النشر قبل النشر — `publish --dry-run`

## الأمر

```bash
python3 studio.py publish --video ~/workspace/videos/studio-test.mp4 \
    --title "باع بقرته ووزّع البذور | قصة قصيرة" --dry-run
```

## ما الذي يحدث؟

`--dry-run` يعرض **الحمولة الدقيقة** التي ستُنشر (العنوان، الكابشن،
المنصات، حدود الأحرف) **دون نشر أي شيء**. استخدمه دائمًا قبل النشر
الحقيقي.

## المخرجات المتوقعة (نصية — القيم تختلف حسب الفيديو)

```
[publish] dry-run — nothing will be uploaded
[publish] video: ~/workspace/videos/studio-test.mp4 (720x1280, ~55s)
[publish] title: باع بقرته ووزّع البذور | قصة قصيرة
[publish] platforms: facebook, youtube
[publish] facebook caption: <caption, max 1024 chars> — OK
[publish] youtube description: <description> — OK
[publish] hashtags: #قصص_وعبر #قصة_حقيقية ...
[publish] first comment (moral): <the moral of the story>
[publish] dry-run complete — re-run without --dry-run to publish
```

## النشر الحقيقي

```bash
python3 studio.py publish --video ~/workspace/videos/studio-test.mp4 \
    --title "باع بقرته ووزّع البذور | قصة قصيرة"
```

- فيسبوك يُنشر فورًا عبر `facebook-cli` المتصل.
- يوتيوب يحتاج إعداد OAuth لمرة واحدة (انظر `README-AR.md`
  قسم «النشر على يوتيوب»)؛ وبلا توكن يُنشئ `publish` حزمة رفع
  يدوي (فيديو + وصف + خطوات) بدل ادعاء رفع لم يحدث.
- نشر TikTok/Instagram موجود في الكود لكن مساراته لم تُختبَر حيًا
  بعد — `--dry-run` فقط حتى إشعار آخر.
