<!-- Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui) -->
<!-- Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE. -->
<!-- Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md. -->
# مثال: أول فيديو تجريبي — `run --demo`

## الأمر

```bash
python3 studio.py run --demo
```

## ما الذي يحدث؟

1. يبني قصة تجريبية مدمجة بالمسار المجاني فقط (Piper + خلفيات
   مولّدة + شعار) — بلا مفاتيح ولا رصيد ولا إنترنت.
2. يركّب فيديو عمودي **720×1280** في ~دقيقة.
3. يطبع مسار الفيديو الناتج وملخص الخطوات.

## المخرجات المتوقعة (نصية — الأزمنة والمسارات تختلف)

```
[demo] building demo story (free path only: Piper + generated backgrounds + logo)
[script] hook ready
[produce] assets ready: images + narration + captions
[assemble] backend: concat
[assemble] export done in ~35s
[done] video: runs/demo-<time>/demo.mp4 (720x1280, ~50s)
```

ثم تحقق من الفيديو:

```bash
python3 studio.py check --video runs/demo-<time>/demo.mp4
```

المخرجات المتوقعة:

```
[check] duration: OK (~50s, vertical 720x1280)
[check] audio: OK (narration present)
[check] manifest: OK
[check] result: PASS
```

## إن فشل شيء

- «الخادم لا يرد» → شغّل `omniroute serve --no-open --daemon --port 20128`
  ثم أعد المحاولة؛ أو أضف `--allow-fallback` ليستخدم هوكًا جاهزًا.
- «أمر omniroute غير موجود في PATH» → `npm install -g omniroute`.
- أي فشل آخر → انسخ رسالة الخطأ كاملة وافتح Issue بقالب «الإبلاغ
  عن عيب» (انظر [CONTRIBUTING.md](../CONTRIBUTING.md)).
