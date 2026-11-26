# التحقق من مقال Firecrawl (n8nar.com) مقابل المصادر الرسمية

**العامل:** A — التحقق مقابل المصادر الرسمية فقط (قراءة نص الصفحات، بلا تثبيت وبلا جلب فعلي)
**تاريخ التحقق:** 2026-11-24
**المقال المراجَع:** n8nar.com، منشور 2026-11-23، مراجعة لمستودع Firecrawl الرسمي كما في 23 نوفمبر 2026
**حالة المستودع لحظة التحقق:** آخر commit ‏`4924105f57c105fa678706e05fa234d66b5b061e`، ‏208,188 نجمة، 6,972 commit — والرابط القديم `github.com/mendableai/firecrawl` يعيد التوجيه إلى `github.com/firecrawl/firecrawl` (انتقلت المنظمة من mendableai إلى firecrawl).

## المصادر الرسمية المستخدمة

| المصدر | الرابط |
|---|---|
| المستودع الرسمي (README) | https://github.com/mendableai/firecrawl |
| التوثيق — المقدمة | https://docs.firecrawl.dev |
| التوثيق — حدود المعدل (Keyless) | https://docs.firecrawl.dev/rate-limits |
| إعلان Keyless الرسمي (مدونة Firecrawl) | https://www.firecrawl.dev/blog/firecrawl-keyless-launch |
| صفحة الأسعار | https://firecrawl.dev/pricing |
| ترخيص Python SDK (PyPI) | https://pypi.org/project/firecrawl-py/ |

**ملاحظة عن مصدر تعذّر الوصول إليه:** محاولة فتح ملف `LICENSE` مباشرة عبر GitHub فشلت بخطأ في جلب المصدر (rate limit / اتصال)، ولم تُعَد المحاولة. مع ذلك، الترخيص مؤكد من مصدرين رسميين آخرين في نفس المستودع: بيانات المستودع على GitHub تذكر «License: GNU Affero General Public License v3.0 (AGPL-3.0)»، وقسم License في الـREADME ينص عليه صراحة (انظر البند 4).

---

## 1. جدول التحقق من الادعاءات

### أ) طبيعة الأداة وقدراتها

| الادعاء في المقال | الحكم | الدليل الرسمي |
|---|---|---|
| Firecrawl أداة جلب محتوى ويب لوكلاء AI: Scrape (صفحة → Markdown)، Crawl، Map، Batch Scrape | **مؤكد** | الـREADME: «turns websites into clean markdown»؛ أقسام Scrape وCrawl وMap وBatch Scrape موثقة كلها؛ والتوثيق: «Search, scrape, and interact with the live web to get clean Markdown or structured data». |
| Cloud يضيف Search وInteract وAgent | **مؤكد** | جدول «What runs where» في الـREADME: Interact وAgent وMonitor خانة Local فيها فارغة وCloud فيها ✅؛ و«Move to Firecrawl Cloud when you need structured JSON, Interact, the Agent or scale beyond one machine». |
| Alexandria مكتبة 550+ مزود بيانات | **مؤكد** | الـREADME: «550+ data providers in one library (250M+ people, 75M+ companies, 41M+ research papers)»؛ ونفس الرقم في وصف المستودع. |
| Alexandria تعمل في Cloud فقط ولا توجد في الاستضافة الذاتية | **مؤكد** | الـREADME (قسم Self-hosting): «Alexandria runs on Firecrawl Cloud, so the self-hosted server does not include it»؛ وجدول القدرات: Alexandria في Local «Through Firecrawl Cloud after `firecrawl-local login`». |

### ب) طرق التشغيل الثلاث

| الادعاء في المقال | الحكم | الدليل الرسمي |
|---|---|---|
| Local: ‏`cargo install firecrawl-local`؛ أوامر scrape/crawl/serve على المنفذ 3002؛ بلا قاعدة بيانات | **مؤكد** | الـREADME حرفيًا: `cargo install firecrawl-local`؛ `firecrawl-local scrape … --markdown` و`crawl … --limit 50` و`map …`؛ «`serve` answers the Firecrawl v2 API on port 3002, so code written for Firecrawl runs against it unchanged and local routes need no API key»؛ «scrapes, crawls and maps from your own machine without a database, queue or container». |
| Local يحتاج Rust ومترجم C | **مؤكد (تفصيل إضافي صحيح)** | الـREADME: «You need Rust and a C compiler, which on macOS means `xcode-select --install` and on Debian or Ubuntu means `build-essential`». |
| Cloud: حسابات وحصص | **مؤكد** | صفحة الأسعار: خطط Free/Hobby/Standard/Growth/Scale/Enterprise بحصص ائتمان شهرية (انظر الخلاصة بالأرقام أدناه). |
| Self-hosted: يحتاج Redis وPostgreSQL ومتصفح؛ بلا Alexandria | **مؤكد** | الـREADME: «The server runs with Docker Compose alongside Redis, PostgreSQL and a browser service»؛ «Deploy the full Firecrawl server from `apps/api` with its own queues, workers and databases»؛ وبلا Alexandria (الدليل أعلاه). |

### ج) التحذيران

| الادعاء في المقال | الحكم | الدليل الرسمي |
|---|---|---|
| Local قد يلجأ افتراضيًا إلى Cloud إن تعذّر التحميل محليًا، ويُوسم بـ ‏`source: firecrawl-cloud` | **مؤكد** | الـREADME حرفيًا: «By default a single-page scrape that won't load there is fetched by Firecrawl Cloud instead and marked `"source": "firecrawl-cloud"` in the result. Those Cloud calls work without an account at a limited rate». |
| المنع بـ ‏`FIRECRAWL_CLOUD=off` | **مؤكد** | الـREADME حرفيًا: «Set `FIRECRAWL_CLOUD=off` to keep everything on your machine». |
| الترخيص الأساسي AGPL-3.0 والـSDKs بعضها MIT | **مؤكد** | بيانات المستودع: AGPL-3.0؛ الـREADME (قسم License): «This project is primarily licensed under the GNU Affero General Public License v3.0 (AGPL-3.0). The SDKs and some UI components are licensed under the MIT License»؛ وPyPI يؤكد أن Python SDK (‏`firecrawl-py` / ‏`firecrawl`) بترخيص MIT. |

### د) الحصة الشهرية Keyless في الـREADME

| الادعاء في المقال | الحكم | الدليل الرسمي |
|---|---|---|
| «الـREADME يذكر حصة شهرية Keyless من Cloud بلا مفتاح أو تسجيل لكنها محدودة» | **غير دقيق — خلط بين مستويين مختلفين** | الـREADME يقول فعلًا: «Firecrawl Keyless gives you 1,000 free credits a month with no API key or signup across MCP, the CLI and the API». لكن التوثيق الرسمي يصحح الصورة: **Keyless حدّ يومي لكل عنوان IP، وأرقامه غير منشورة** — صفحة Rate Limits: «Keyless usage is free and capped per IP address per day by two limits» (حد أقصى لعدد الطلبات + حد أقصى للائتمانات يوميًا، وتجاوزهما يرجع `429`)، ولا تذكر الصفحة أي رقم يومي. أما **1,000 ائتمان/شهر فهي حصة حساب Free المسجَّل** (بمفتاح API)، لا Keyless: «Sign up for a free API key to get 1,000 credits» وصفحة الأسعار «Free tier: 1,000 credits every month, refreshed monthly, no credit card required». فالمقال نقل نص الـREADME بأمانة، لكن النص نفسه يخلط؛ والصواب حسب التوثيق: Keyless = يومي لكل IP بأرقام غير معلنة، و1,000/شهر = حساب Free. |

---

## 2. حدود الحصة Keyless بالأرقام الدقيقة (من التوثيق الرسمي)

**المصدر:** https://docs.firecrawl.dev/rate-limits (محدَّثة 2026-11-16) + https://www.firecrawl.dev/blog/firecrawl-keyless-launch (منشورة 2026-06-16).

- **المبدأ:** Keyless مجاني، **بلا حساب وبلا مفتاح API وبلا بطاقة**، ويُعاد ضبطه **يوميًا** («resets every day» في إعلان الإطلاق؛ و«capped per IP address per day» في التوثيق).
- **الأرقام اليومية الدقيقة: غير منشورة رسميًا.** التوثيق يذكر حدّين فقط دون أرقام: (1) حد أقصى لعدد الطلبات في اليوم، (2) حد أقصى للائتمانات في اليوم. تجاوز أيٍّ منهما يرجع `429`. **لا تصمم أي استخدام إنتاجي على رقم يومي محدد — Firecrawl لا تنشره.**
- **النقاط المسموحة بلا مفتاح:**
  - عبر MCP المستضاف (`https://mcp.firecrawl.dev/v2/mcp`): **Search وScrape وParse فقط**.
  - عبر العملاء الرسميين (SDKs وCLI وREST API): **Search وScrape وParse وInteract أيضًا**.
  - نقاط بحث Research وDeveloper وGovernment على Cloud تعمل أيضًا بلا مفتاح.
- **النقاط الممنوعة بلا مفتاح (تحتاج حسابًا/مفتاحًا):** Crawl وMap وBatch Scrape وExtract وAgent وMonitors وAlexandria، وكل ما عداها.
- **طريقة الاستخدام بلا مفتاح فعلًا:**
  - REST: طلب عادي **بلا ترويسة `Authorization`**، مثل `POST https://api.firecrawl.dev/v2/scrape` مع `{"url": ..., "formats": ["markdown"]}`؛ و`POST https://api.firecrawl.dev/v2/search` للبحث.
  - Python/Node SDK: إنشاء العميل **بلا أي وسيطات**، مثل `Firecrawl()` — «with no arguments uses the keyless free tier».
  - CLI: ‏`npx firecrawl-cli@latest` ثم الأمر مباشرة (مثل `firecrawl search "…"`) بلا تسجيل دخول.
  - MCP: توجيه أي عميل MCP إلى `https://mcp.firecrawl.dev/v2/mcp` بلا مفتاح.
- **ملاحظة عملية:** حدود Keyless لكل IP تعني أنها غير موثوقة للإنتاج أو للاستخدام من شبكات مشتركة/VPN (قد تُرفض طلبات بعض الشبكات أصلًا)؛ والترقية هي التسجيل للحصول على مفتاح Free.

---

## 3. صفحة الأسعار — هل توجد فئة مجانية دائمة؟

**المصدر:** https://firecrawl.dev/pricing — الأسعار سارية منذ 4 سبتمبر 2026، بالدولار الأمريكي.

**نعم — توجد فئة Free دائمة (ليست تجريبية مؤقتة): 1,000 ائتمان كل شهر، تُجدَّد شهريًا، وبلا بطاقة ائتمانية.** (الأسئلة الشائعة في الصفحة نفسها: «Firecrawl gives you 1,000 free credits every month … and no card is required».)

| الخطة | السعر الشهري | الائتمانات/شهر |
|---|---|---|
| **Free** | $0 | **1,000** |
| Hobby | $19 شهريًا / $16 سنويًا | 5,000 |
| Standard | $99 شهريًا / $83 سنويًا | 100,000 |
| Growth | $399 شهريًا / $333 سنويًا | 500,000 |
| Scale | $749 شهريًا / $599 سنويًا | 1,000,000 |
| Enterprise | مخصص | مخصص |

**تكلفة العمليات (نفس المعدلات على كل الخطط):**
- Scrape وCrawl: **1 ائتمان/صفحة**؛ Map: **1 ائتمان/استدعاء**؛ Search: **2 ائتمان/10 نتائج**؛ Interact: **2 ائتمان/دقيقة متصفح**؛ Monitor: 1 ائتمان/صفحة/فحص (وفي موضع آخر 7 ائتمانات/صفحة/فحص لمحرك الاستخراج الحتمي — تناقض ظاهري في نص الصفحة نفسها، يُذكر تحفظًا).
- صيغ JSON وQuestion وHighlight في Scrape/Crawl تضيف **4 ائتمانات/صفحة**.
- Agent: في المعاينة — **5 تشغيلات مجانية يوميًا** + تسعير ديناميكي.
- الطلب الفاشل الذي لا يرجع نتيجة **بلا تكلفة**؛ أما الصفحة التي ترد بخطأ HTTP مثل 403 أو 404 فتُحسب **1 ائتمان**.
- ائتمانات Free لا تُرحَّل للشهر التالي (الترحيل لـScale شهر واحد وEnterprise مخصص فقط).
- الدفع حسب الاستخدام (pay-as-you-go) للخطط المدفوعة فقط، بزيادات $5.

**حدود معدل الخطة Free (من صفحة Rate Limits):** ‏/scrape و/map و/search: **10 طلب/دقيقة**؛ ‏/crawl: **2/دقيقة**؛ ‏/agent: ‏**2/دقيقة**؛ متصفحات متزامنة: **2**؛ وظائف في الانتظار: 50,000.

---

## 4. الترخيص — التفصيل والتبعات العملية

**المصدر:** بيانات مستودع GitHub + قسم License في الـREADME (نص ملف `LICENSE` نفسه تعذّر جلبه مباشرة — انظر الملاحظة أعلى التقرير).

- **الترخيص الأساسي مؤكد: AGPL-3.0** للمشروع (الخادم وFirecrawl Local والاستضافة الذاتية).
- **الـSDKs مؤكد أنها MIT:** نص الـREADME صريح («The SDKs and some UI components are licensed under the MIT License»)، وصفحة PyPI لحزمة `firecrawl-py`/`firecrawl` تذكر MIT صراحة، مع تنبيه أن المشروع الأكبر قد يكون بترخيص مختلف. (لم يُتحقق من كل SDK على حدة — Go وJava وRust وRuby و.NET وPHP وElixir — لكن نص الـREADME يعمّم على «The SDKs».)
- **ماذا يعني AGPL-3.0 عمليًا لمشروع تجاري يبيع تراخيص ويستخدم الأداة كأداة خارجية لجلب محتوى، دون تعديل كودها أو تقديمها كخدمة؟** (فهم عام، وليس استشارة قانونية):
  - مجرد **استخدام** الأداة — تشغيل ثنائية Local أو خادم Self-hosted دون تعديل، واستدعاؤها عبر API/SDK من برنامجك الخاص — **لا يجبرك AGPL على فتح مصدر برنامجك**؛ الـcopyleft في AGPL يلزم من **يعدّل البرنامج نفسه** ويوزعه أو **يتيحه عبر الشبكة** بأن يتيح مصدر النسخة المعدلة.
  - الخطر يبدأ إن: (أ) عدّلت كود Firecrawl نفسه (خادم/Local) ثم أتحته لمستخدمين عبر الشبكة — عندها يجب إتاحة مصدر النسخة المعدلة؛ (ب) قدّمت Firecrawl نفسها كخدمة مدفوعة للغير (وهذا هو نموذج Cloud التجاري الخاص بالشركة).
  - استخدام SDK الـMIT من برنامجك التجاري مسموح صراحة (بما فيه البيع) مع الاحتفاظ بإشعار الترخيص.
  - ملاحظتان إضافيتان من الـREADME: «It is the sole responsibility of end users to respect websites' policies when scraping» — وFirecrawl يحترم `robots.txt` افتراضيًا؛ والالتزام بسياسات المواقع المستهدفة مسؤولية المستخدم النهائي.
  - المستودع **لا يذكر توفر ترخيص تجاري بديل** للخادم — من أراد يقينًا تجاريًا يراسل الشركة (وهذا تحفظ موثق في مراجعة مستقلة أيضًا).

---

## 5. Local مقابل Cloud — القدرات الغائبة والمتطلبات

**المصدر:** جدول «What runs where» في الـREADME + قسم Firecrawl Local.

**جدول القدرات (من الـREADME حرفيًا):**

| القدرة | Local | Cloud |
|---|---|---|
| Scrape | Markdown وHTML وraw HTML وروابط | + JSON المنظم والملخصات ولقطات الشاشة وإجراءات المتصفح |
| Crawl وMap وBatch Scrape | ✅ | ✅ |
| PDF وملفات Office | ✅ | ✅ (+ Parse للملفات المرفوعة) |
| Search | عبر Cloud، بلا حساب | ✅ |
| Alexandria | عبر Cloud بعد `firecrawl-local login` | ✅ |
| Interact وAgent وMonitor | ❌ (الخانة فارغة) | ✅ |

**الغائب عن Local إذن:** JSON المنظم (structured JSON) والملخصات ولقطات الشاشة وإجراءات المتصفح (Interact) والوكيل (Agent) والمراقبة (Monitor)؛ أما Search وAlexandria فمتاحتان في Local **عبر Cloud** فقط (الأولى بلا حساب، والثانية بعد تسجيل الدخول).

**ما الذي يتطلب متصفحًا محليًا؟** الصفحات التي تحتاج JavaScript تُعرض في **Chrome أو Chromium الموجود أصلًا على جهازك** («Pages that need JavaScript render in the Chrome or Chromium already on your machine») — فلا متصفح مضمّن في الثنائية؛ وبلا متصفح تعمل الصفحات الثابتة فقط، والصفحة التي تحتاجه ترجع مع تحذير.

**متطلبات إضافية موثقة:** Rust + مترجم C للتثبيت عبر cargo؛ وNode.js ‏22+ لخادم MCP عند `firecrawl-local init`؛ و`serve` يخدم API v2 على المنفذ 3002 ومساراته المحلية بلا مفتاح.

---

## 6. الخلاصة بالأرقام الدقيقة (الحصة المجانية / Keyless)

| البند | الرقم الدقيق | المصدر |
|---|---|---|
| **Keyless — بلا مفتاح وبلا تسجيل** | حدّ يومي لكل عنوان IP (طلبات + ائتمانات) — **الأرقام غير منشورة رسميًا**؛ التجاوز = `429` | docs.firecrawl.dev/rate-limits |
| Keyless — النقاط المسموحة | MCP: ‏Search وScrape وParse؛ SDK/CLI/API: + Interact | docs.firecrawl.dev/rate-limits |
| Keyless — النقاط الممنوعة | Crawl وMap وBatch Scrape وExtract وAgent وMonitors وAlexandria | docs.firecrawl.dev/rate-limits |
| Keyless — إعادة الضبط | يوميًا | مدونة الإطلاق الرسمية |
| **حساب Free — بمفتاح، بلا بطاقة** | **1,000 ائتمان/شهر، تُجدَّد شهريًا** | firecrawl.dev/pricing |
| Free — معدل الطلبات | Scrape/Map/Search ‏10/دقيقة؛ Crawl ‏2/دقيقة؛ Agent ‏2/دقيقة | docs.firecrawl.dev/rate-limits |
| Free — متصفحات متزامنة | 2 | docs.firecrawl.dev/rate-limits |
| تكلفة الصفحة الواحدة | Scrape/Crawl ‏1 ائتمان؛ Search ‏2 ائتمان/10 نتائج؛ JSON ‏+4/صفحة | firecrawl.dev/pricing |
| Agent (معاينة) | 5 تشغيلات مجانية يوميًا | firecrawl.dev/pricing |

## 7. الحكم الإجمالي على المقال

- **معظم الادعاءات مؤكدة حرفيًا من المصادر الرسمية:** طبيعة الأداة وقدراتها، الطرق الثلاث، التحذيران (اللجوء إلى Cloud مع وسم `source: firecrawl-cloud` والمنع بـ`FIRECRAWL_CLOUD=off`)، وترخيص AGPL-3.0 مع SDKs بترخيص MIT.
- **الخلل الوحيد الجوهري:** ادعاء «حصة شهرية Keyless» — الـREADME يقولها فعلًا، لكن التوثيق الرسمي يبيّن أن Keyless حدّ **يومي لكل IP بأرقام غير منشورة**، وأن **1,000 ائتمان/شهر** هي حصة **حساب Free المسجَّل**، لا Keyless. أي استخدام يخطط على «1,000 شهريًا بلا مفتاح» مبني على خلط يجب تصحيحه.
- **تحفظات توثيقية:** (أ) نص ملف `LICENSE` نفسه تعذّر جلبه مباشرة في هذه الجلسة (فشل جلب المصدر) — والترخيص مع ذلك مؤكد من بيانات المستودع ومن نص الـREADME؛ (ب) صفحة الأسعار تذكر تكلفة Monitor بصيغتين مختلفتين (1 و7 ائتمانات/صفحة/فحص) في موضعين — يُرجَّح الرجوع للتوثيق قبل الاعتماد على رقمها؛ (ج) لم يُتحقق من ترخيص كل SDK على حدة، بل من نص الـREADME العام وPyPI لحزمة Python.
