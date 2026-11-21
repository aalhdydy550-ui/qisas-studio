#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مساعد إدخال مفاتيح API المجانية للاستوديو.

يقرأ المفتاح من المستخدم دون إظهاره أبدًا (getpass عند الطرفية،
أو سطر من stdin عند التوجيه)، ويحفظه في ملف .env بصلاحيات 600
بجانب هذا السكربت، ويستطيع اختبار صلاحية المفتاح باستدعاء خفيف
للمزود (قائمة موديلات/حساب — بلا استهلاك توكنات).

الاستخدام:
    python3 setup-key.py                        # تفاعلي: اختر المزود ثم الصق المفتاح
    python3 setup-key.py --provider groq        # إدخال مفتاح Groq
    python3 setup-key.py --provider groq --test  # اختبار المفتاح المحفوظ
    echo 'gsk_...' | python3 setup-key.py --provider groq   # من stdin (لا يُظهره)

لا يطبع السكربت قيمة المفتاح أبدًا — فقط اسم المزود وطوله.
"""

import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, ".env")

PROVIDERS = {
    "groq": {
        "label": "Groq",
        "env": "GROQ_API_KEY",
        "prefix": "gsk_",
        "min_len": 20,
        "signup": "https://console.groq.com",
        "test_url": "https://api.groq.com/openai/v1/models",
        "test_auth": "bearer",
        "use": "LLM سريع للهوك والكابشن والسيناريو",
    },
    "openrouter": {
        "label": "OpenRouter",
        "env": "OPENROUTER_API_KEY",
        "prefix": "sk-or-v1-",
        "min_len": 20,
        "signup": "https://openrouter.ai",
        "test_url": "https://openrouter.ai/api/v1/key",
        "test_auth": "bearer",
        "use": "LLM مجاني (openrouter/free) للهوك والكابشن",
    },
    "huggingface": {
        "label": "HuggingFace",
        "env": "HF_TOKEN",
        "prefix": "hf_",
        "min_len": 10,
        "signup": "https://huggingface.co/settings/tokens",
        "test_url": "https://huggingface.co/api/whoami",
        "test_auth": "bearer",
        "use": "تنزيل النماذج + Inference Providers",
    },
    "pexels": {
        "label": "Pexels",
        "env": "PEXELS_API_KEY",
        "prefix": None,  # بلا بادئة ثابتة
        "min_len": 10,
        "signup": "https://www.pexels.com/api",
        "test_url": "https://api.pexels.com/v1/search?query=test&per_page=1",
        "test_auth": "plain",
        "use": "فيديوهات/صور جاهزة للفيديوهات الطويلة",
        "paused": True,
    },
    "pollinations": {
        "label": "Pollinations",
        "env": "POLLINATIONS_API_KEY",
        "prefix": "sk_",
        "min_len": 10,
        "signup": "https://enter.pollinations.ai",
        "test_url": "https://gen.pollinations.ai/v1/models",
        "test_auth": "bearer",
        "use": "توليد صور (مصغرات/مشاهد)",
    },
}

PLACEHOLDERS = {"test", "xxx", "xxxx", "your-key", "your_api_key",
                "your-key-here", "changeme", "key", "api-key"}


def read_secret(prompt):
    """اقرأ سرًا دون إظهاره: getpass في الطرفية، سطر من stdin عند التوجيه."""
    if sys.stdin.isatty():
        return getpass.getpass(prompt)
    return sys.stdin.readline().strip()


def load_env():
    values = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip()
    return values


def save_key(env_var, key):
    """احفظ/حدّث سطر المفتاح في .env بصلاحيات 600 (بلا تكرار)."""
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    out = []
    found = False
    for line in lines:
        if line.strip().startswith(env_var + "="):
            out.append(env_var + "=" + key)
            found = True
        else:
            out.append(line)
    if not found:
        out.append(env_var + "=" + key)
    header = ("# مفاتيح API المجانية للاستوديو — لا تشارك هذا الملف "
              "أبدًا ولا ترفعه على git (صلاحيات 600).")
    if not any(l.startswith("#") for l in out):
        out.insert(0, header)
    fd = os.open(ENV_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, ("\n".join(out) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(ENV_PATH, 0o600)


def validate_key(provider, key):
    """تحقق شكلي من المفتاح قبل الحفظ. يعيد رسالة خطأ أو None."""
    if not key:
        return "المفتاح فارغ."
    if any(c.isspace() for c in key):
        return "المفتاح يحتوي مسافات — انسخه كما هو بلا مسافات حوله."
    if key.lower() in PLACEHOLDERS:
        return "هذه قيمة وهمية، وليست مفتاحًا حقيقيًا."
    info = PROVIDERS[provider]
    if len(key) < info["min_len"]:
        return "المفتاح أقصر من المتوقع لمزود %s." % info["label"]
    prefix = info["prefix"]
    if prefix and not key.startswith(prefix):
        return ("المفتاح لا يبدأ بـ %s كما هو متوقع لمزود %s — "
                "تأكد أنك نسخت المفتاح الصحيح." % (prefix, info["label"]))
    return None


def test_key(provider, key):
    """استدعاء خفيف للتحقق من صلاحية المفتاح. يعيد (ok, رسالة)."""
    info = PROVIDERS[provider]
    if info["test_auth"] == "bearer":
        auth = "Bearer " + key
    else:
        auth = key
    req = urllib.request.Request(
        info["test_url"], headers={"Authorization": auth})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp.read(512)
            return True, "المفتاح صالح (رد %s)." % resp.status
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False, "المفتاح مرفوض من المزود (HTTP %s) — راجع النسخ." % e.code
        return False, "المزود رد بخطأ HTTP %s." % e.code
    except urllib.error.URLError as e:
        return False, "تعذر الوصول للمزود: %s." % getattr(e, "reason", e)
    except Exception as e:  # noqa: BLE001 — رسالة ودودة بدل تتبع
        return False, "خطأ أثناء الاختبار: %s." % e


def choose_provider_interactive():
    names = list(PROVIDERS)
    print("اختر المزود:")
    for i, name in enumerate(names, 1):
        info = PROVIDERS[name]
        note = " (الإصدار متوقف مؤقتًا)" if info.get("paused") else ""
        print("  %d) %s — %s%s" % (i, info["label"], info["use"], note))
    try:
        choice = input("رقم المزود: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)
    try:
        idx = int(choice) - 1
        return names[idx]
    except (ValueError, IndexError):
        print("اختيار غير صالح.")
        sys.exit(2)


def main():
    parser = argparse.ArgumentParser(
        description="إدخال مفتاح API مجاني وحفظه في .env (600).")
    parser.add_argument("--provider", choices=sorted(PROVIDERS),
                        help="المزود (إن لم يُذكر يُسأل عنه تفاعليًا)")
    parser.add_argument("--test", action="store_true",
                        help="اختبر المفتاح المحفوظ بدل إدخال واحد جديد")
    args = parser.parse_args()

    provider = args.provider or choose_provider_interactive()
    info = PROVIDERS[provider]

    if info.get("paused"):
        print("تنبيه: إصدار مفاتيح %s الجديدة متوقف مؤقتًا من المزود "
              "نفسه — قد يفشل التسجيل حتى تُستأنف." % info["label"])

    if args.test:
        stored = load_env().get(info["env"])
        if not stored:
            print("لا يوجد مفتاح محفوظ لـ %s. أضفه أولًا بـ:"
                  % info["label"])
            print("  python3 setup-key.py --provider %s" % provider)
            sys.exit(2)
        ok, msg = test_key(provider, stored)
        print("%s: %s" % (info["label"], msg))
        sys.exit(0 if ok else 1)

    print("المزود: %s — %s" % (info["label"], info["use"]))
    print("التسجيل: %s" % info["signup"])
    key = read_secret("الصق المفتاح (لن يظهر أثناء الكتابة): ").strip()
    err = validate_key(provider, key)
    if err:
        print("خطأ: %s لم يُحفظ شيء." % err)
        sys.exit(2)
    save_key(info["env"], key)
    print("تم حفظ مفتاح %s في .env (الطول: %d حرفًا) — ولم يُطبع هنا."
          % (info["label"], len(key)))
    try:
        answer = input("اختبر المفتاح الآن؟ (y/N): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if answer in ("y", "yes", "نعم"):
        ok, msg = test_key(provider, key)
        print("%s: %s" % (info["label"], msg))
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
