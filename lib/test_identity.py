#!/usr/bin/env python3
"""هوية اختبار عشوائية مزروعة — جولة v0.1.37 (مقترح tinker رقم 13).

اختبارات العملاء كانت تستخدم أرقامًا وهمية ثابتة (بل رقم فودافون
كاش الحقيقي نفسه كبيانات اختبار!)؛ فإن اعتمد كود ما على الرقم
نفسه دون أن يدري، يمر الاختبار كاذبًا. المولّد هنا يأخذ بذرة
ثابتة (20261122) ويولّد N رقم واتساب مختلفًا بصيغ مختلفة
(`01…` / `+201…` / `00201…`) لكل تشغيل — حتمي بنفس البذرة،
مختلف عبر الحالات.
"""
import random

DEFAULT_SEED = 20261122

_PREFIXES = ("010", "011", "012", "015")


def _base_number(rng):
    """رقم مصري أساسي 11 رقمًا: 01x + 8 أرقام."""
    return rng.choice(_PREFIXES) + "".join(
        rng.choice("0123456789") for _ in range(8))


def fake_whatsapp_numbers(seed=DEFAULT_SEED, count=10):
    """N رقم واتساب وهمي مختلف بصيغ مختلفة، حتمي بالبذرة.

    كل رقم قاعدة مختلفة (بلا تكرار)؛ وصيغته عشوائية من
    (محلي `01…` / دولي `+201…` / دولي `00201…`).
    """
    if count < 1:
        raise ValueError("العدد يجب أن يكون 1 أو أكثر")
    rng = random.Random(seed)
    seen = set()
    out = []
    while len(out) < count:
        base = _base_number(rng)
        if base in seen:
            continue
        seen.add(base)
        form = rng.choice(("local", "plus", "double_zero"))
        if form == "local":
            out.append(base)
        elif form == "plus":
            out.append("+20" + base[1:])
        else:
            out.append("0020" + base[1:])
    return out


def canonical_whatsapp(number):
    """وحّد صيغ رقم مصري واحد → 10 أرقام تبدأ بـ 1.

    مرآة `client_orders._canonical_whatsapp` — يُختبر اتفاقهما
    على الأرقام المولدة (لا استيراد متقاطع هنا).
    """
    n = (number or "").strip().replace(" ", "").replace("-", "")
    if n.startswith("+20"):
        n = n[3:]
    elif n.startswith("0020"):
        n = n[4:]
    elif n.startswith("0"):
        n = n[1:]
    return n
