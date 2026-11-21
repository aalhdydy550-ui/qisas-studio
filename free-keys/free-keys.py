#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حالة مفاتيح API المجانية للاستوديو — أسماء فقط، بلا قيم أبدًا.

يقرأ ~/workspace/studio/free-keys/.env (إن وُجد) ويعرض لكل مزود
هل مفتاحه مضبوط أم لا، مع رابط التسجيل الرسمي للمفقود.
لا يجري أي اتصال شبكي، ولا يطبع أي قيمة مفتاح.

الاستخدام:
    python3 free-keys.py              # الحالة + روابط التسجيل للمفقود
    python3 free-keys.py --env-file PATH   # ملف env بديل

الخروج: 0 إن كانت كل المفاتيح القابلة للإضافة مضبوطة، و1 إن نقص شيء.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ENV = os.path.join(HERE, ".env")

# (الاسم، متغير البيئة، رابط التسجيل، ملاحظة)
PROVIDERS = [
    ("Groq", "GROQ_API_KEY", "https://console.groq.com",
     "LLM سريع للهوك والكابشن"),
    ("OpenRouter", "OPENROUTER_API_KEY", "https://openrouter.ai",
     "LLM مجاني (openrouter/free)"),
    ("HuggingFace", "HF_TOKEN", "https://huggingface.co/settings/tokens",
     "تنزيل النماذج + Inference Providers"),
    ("Pexels", "PEXELS_API_KEY", "https://www.pexels.com/api",
     "فيديوهات/صور جاهزة — الإصدار متوقف مؤقتًا"),
    ("Pollinations", "POLLINATIONS_API_KEY", "https://enter.pollinations.ai",
     "توليد صور (Quest Pollen مجاني محدود)"),
]

# مزودون مربوطون أصلًا ولا يحتاجون مفتاحًا هنا
ALREADY_DONE = [
    ("Gemini", "مربوط أصلًا عبر موصل custom.gemini — لا حاجة لمفتاح هنا"),
    ("DuckDuckGo AI (ddgw)", "شغال بلا مفتاح عبر OmniRoute"),
]


def load_env(path):
    values = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip()
    return values


def main():
    parser = argparse.ArgumentParser(
        description="حالة مفاتيح API المجانية (أسماء فقط).")
    parser.add_argument("--env-file", default=DEFAULT_ENV,
                        help="ملف .env المراد فحصه")
    args = parser.parse_args()

    values = load_env(args.env_file)
    print("مفاتيح API المجانية للاستوديو — %s" % args.env_file)
    print("=" * 60)

    missing = []
    for name, env_var, signup, use in PROVIDERS:
        val = values.get(env_var)
        if val:
            print("✅ %-14s مضبوط (%d حرفًا) — %s" % (name, len(val), use))
        else:
            print("❌ %-14s غير مضبوط — %s" % (name, use))
            print("   سجّل من: %s" % signup)
            print("   ثم: python3 setup-key.py --provider %s"
                  % name.lower().replace(" ", ""))
            if name != "Pexels":
                missing.append(name)
            else:
                print("   ملاحظة: إصدار مفاتيح Pexels الجديدة متوقف مؤقتًا "
                      "من المزود نفسه.")

    print("-" * 60)
    for name, note in ALREADY_DONE:
        print("✅ %-14s %s" % (name, note))
    print("-" * 60)
    print("FreeLLMAPI: غير مثبّت (كتالوج فقط) — "
          "https://github.com/tashfeenahmed/freellmapi")
    print("التفاصيل الكاملة: free-keys.md")

    if missing:
        print("ناقص: %s" % "، ".join(missing))
        sys.exit(1)
    print("كل المفاتيح القابلة للإضافة مضبوطة.")
    sys.exit(0)


if __name__ == "__main__":
    main()
