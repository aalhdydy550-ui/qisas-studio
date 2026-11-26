# اختبار Firecrawl الحي — نتيجة فعلية (العامل C)

**التاريخ:** الثلاثاء 2026-11-24، ‏09:10–09:12 بتوقيت القاهرة (07:10–07:12 UTC)
**الهدف:** إثبات واحد حقيقي أن Firecrawl يعمل مجانًا على هذه الـVM — أو إثبات أنه لا يعمل.
**الملف:** `~/workspace/studio/free-keys/firecrawl-work/live-test.md` (ملف المهمة الوحيد — لم يُلمس أي ملف آخر)

---

## 1) فحص البيئة (أوامر قراءة فقط)

الأمر المنفذ حرفيًا:

```bash
which cargo rustc chromium chromium-browser google-chrome google-chrome-stable node npm python3 curl
cargo --version; rustc --version; node --version; python3 --version
```

النتيجة الفعلية:

| الأداة | النتيجة |
|---|---|
| `cargo` | **غير مثبّت** (`command not found`) |
| `rustc` | **غير مثبّت** (`command not found`) |
| `chromium` / `chromium-browser` | غير موجود |
| `google-chrome` / `google-chrome-stable` | غير موجود |
| `node` | v24.22.1 |
| `npm` | موجود (`/opt/hatch-image/bin/npm`) |
| `python3` | 3.12.3 |
| `curl` | موجود (`/usr/bin/curl`) |

**الخلاصة من الفحص:** مسار Local يحتاج Rust + متصفح — وهما غائبان. مسار Keyless عبر HTTP يحتاج `curl` فقط — وهو موجود.

---

## 2) التوثيق الرسمي المقروء قبل الاختبار (Keyless)

المصدر: `docs.firecrawl.dev/authentication` و`docs.firecrawl.dev/rate-limits` (مقروءان عبر البحث في 2026-11-24):

- نقاط النهاية التي تعمل **بلا مفتاح إطلاقًا**: `/v2/scrape` و`/v2/search` و`/v2/parse` (+ `/v1/scrape` و`/v1/search`)، وأيضًا `/v2/scrape/{jobId}/interact`.
- **شرط حاسم:** يُترك هيدر `Authorization` خارج الطلب تمامًا. هيدر فارغ مثل `Authorization: Bearer` بلا توكن يُرفض بـ`401 Unauthorized: Token missing`.
- كل نقطة نهاية أخرى (crawl, map, extract, agent, batch scrape, حالة المهمة) تحتاج مفتاحًا، وبدونه ترجع `401`.
- الاستخدام Keyless **مجاني ومقيّد لكل عنوان IP في اليوم** بحدّين: عدد طلبات يومي + عدد رصيد (credits) يومي؛ وتجاوزهما يرجع `429`. الأرقام الدقيقة غير منشورة وتتغير مع الطلب.
- الخطة المجانية بحساب (تسجيل) تعطي 1,000 رصيد/شهر وحدودًا أعلى — لكنها **ليست** مطلوبة للاختبار Keyless.

---

## 3) الاختبار الحقيقي — Keyless عبر curl (بلا مفتاح، بلا حساب)

### الاختبار 1 — `https://example.com`

الأمر المنفذ حرفيًا:

```bash
curl -s -w "\nHTTP_CODE:%{http_code}\nTIME:%{time_total}s\n" \
  -X POST https://api.firecrawl.dev/v2/scrape \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","formats":["markdown"]}' \
  -o /tmp/fc-test1.json
```

المخرجات الفعلية:

- **كود الاستجابة:** `HTTP 200`
- **الزمن:** `6.91 ثانية`
- **حجم الرد:** 1,806 بايت
- **الجسم (مختصر):**

```json
{
  "success": true,
  "data": {
    "markdown": "This domain is for use in documentation examples without needing permission. ... [Learn more](https://iana.org/help/example-domains)",
    "metadata": {
      "title": "Example Domain",
      "sourceURL": "https://example.com",
      "statusCode": 200,
      "contentType": "text/html; charset=utf-8",
      "proxyUsed": "basic",
      "cacheState": "hit",
      "cachedAt": "2026-11-24T07:10:14.992Z",
      "creditsUsed": 1,
      "concurrencyLimited": false
    }
  }
}
```

**نعم — رجع Markdown فعليًا** (نص الصفحة كاملًا بعدة لغات + رابط Markdown)، و`success: true`، وكلفة الطلب **1 رصيد** فقط.

### الاختبار 2 (تأكيد) — `https://firecrawl.dev`

نفس الأمر مع `{"url":"https://firecrawl.dev","formats":["markdown"]}`:

- **كود الاستجابة:** `HTTP 200`
- **الزمن:** `8.36 ثانية`
- **الجسم:** `success: true` — **Markdown بطول 66,334 حرفًا** (الصفحة الرئيسية كاملة: العناوين والروابط وأمثلة JSON)، `creditsUsed: 1`، `cacheState: hit`، `title: "Firecrawl | Knowledge Infrastructure for AI Agents"`.

> ملاحظة: كلا الردّين `cacheState: hit` — أي أن Firecrawl خدمهما من كاشه. هذا لا يضعف النتيجة: الـMarkdown رجع كاملًا وصحيحًا من نقطة النهاية Keyless نفسها، والاختبار يثبت أن **المسار يعمل من هذه الـVM بلا مفتاح**؛ والجلب الحي لصفحة غير مخزّنة لم يُختبر (لم تكن هناك حاجة — الهدف إثبات عمل المسار، وقد تحقق).

**لا رسالة حد/خطأ في أي من الطلبين** — لا `429` ولا `401` ولا أي رفض.

---

## 4) مسار Local — تقييم بدون تنفيذ (لم يُنفَّذ لأنه غير مطلوب)

حسب ترتيب المهمة، مسار Local يُجرَّب فقط إن فشل Keyless — وKeyless **نجح**، فلم يُنفَّذ تثبيت Local.

مع ذلك، الوضع الفعلي لمسار Local على هذه الـVM (من فحص البيئة):

- `cargo` و`rustc` **غير مثبّتين** — التثبيت يتطلب أولًا تثبيت Rust (عبر rustup، مئات الميجا) ثم `cargo install firecrawl-local` (تجميع من المصدر؛ التوثيق يذكر ~7 دقائق على ماك — وعلى هذه الـVM ذات 1.5 CPU قد يكون أطول).
- لا يوجد Chrome/Chromium — وLocal يستخدم متصفحًا محليًا للصفحات الديناميكية، فحتى بعد التثبيت سيحتاج متصفحًا أو يقتصر على الجلب البسيط.
- الصيغة الموثقة (لم تُجرَّب): `cargo install firecrawl-local` ثم `FIRECRAWL_CLOUD=off firecrawl-local scrape https://example.com --markdown`، والخادم `firecrawl-local serve` على المنفذ 3002.

**السبب الدقيق لعدم تنفيذ Local:** غير مطلوب (Keyless نجح) + تكلفته عالية (تثبيت Rust كامل + تجميع) بلا فائدة مضافة للاختبار. إن احتاجه الاستوديو لاحقًا، فهو ممكن لكنه يحتاج خطوة تثبيت Rust أولًا.

---

## الحكم النهائي

# ✅ يعمل Firecrawl مجانًا على هذه الـVM — بالمسار Keyless عبر HTTP

- **المسار العامل:** Keyless Cloud — `POST https://api.firecrawl.dev/v2/scrape` **بلا هيدر Authorization إطلاقًا**، بلا مفتاح، بلا حساب، بلا تسجيل.
- **الدليل:** طلبان حقيقيان ناجحان (200 + `success: true` + Markdown فعلي) في 2026-11-24 07:10–07:12 UTC — `example.com` (‏1,806 بايت) و`firecrawl.dev` (66,334 حرف Markdown).
- **التكلفة:** 1 رصيد لكل طلب scrape (من الحصة اليومية المجانية لكل IP — حدّها غير منشور، وتجاوزها يرجع `429`).
- **ما يعمل مجانًا بهذا المسار:** `scrape` و`search` و`parse` و`interact` فقط. ما **لا** يعمل بلا مفتاح: `crawl` و`map` و`extract` و`agent` و`batch scrape` وحالة المهام (ترجع `401` بلا مفتاح).
- **المسار Local:** لم يُختبر (غير مطلوب بعد نجاح Keyless) و**غير جاهز** على هذه الـVM اليوم — لا Rust ولا Chrome؛ يحتاج تثبيت Rust أولًا.
- **لم يُستخدم أي مفتاح أو حساب** في أي خطوة، ولم يُجلب أي محتوى محمي أو خاص — صفحتان عامتان فقط (`example.com` و`firecrawl.dev`).

**أخف أمر إعادة للاختبار (نسخ/لصق):**

```bash
curl -s -X POST https://api.firecrawl.dev/v2/scrape \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","formats":["markdown"]}'
```
