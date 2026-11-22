#!/usr/bin/env python3
"""اختبار A/B — `studio.py ab` و`studio.py ab-results`.

لفيديو واحد: يولّد هوكين مختلفين ومصغرتين مختلفتين، ويسجّل
الزوج في `runs/ab-*.json` (الفيديو، الهوك أ/ب، المصغرة أ/ب،
تاريخ النشر). وبعد نشر النسختين يقارن `ab-results` مشاهداتهما
عبر `analyze` (فيسبوك + يوتيوب).

صراحة مهمة (تُطبع مع كل أمر): فيسبوك ويوتيوب بلا اختبار A/B
أصلي للريلز/الشورتس — الأداة تولّد النسختين وتتتبع المقارنة
بين منشورين منفصلين (عنوان النشر لكل نسخة هو هوكها، فيُميَّز
المنشوران بنص الهوك في الكابشن/العنوان). أي نسخة غير منشورة
بعد تُطبع «غير منشورة بعد» — بلا أرقام مخترعة أبدًا.
"""
import json
import os
import re
import subprocess
import time

from lib import analyze
from lib import ideas as ideas_lib
from lib import thumbnail

AB_NOTE = ("تنبيه: فيسبوك ويوتيوب بلا اختبار A/B أصلي للريلز/"
           "الشورتس — هذه الأداة تولّد النسختين وتتتبع المقارنة "
           "بين منشورين منفصلين؛ انشر كل نسخة بعنوانها (هوكها) "
           "ثم قارن بـ ab-results.")

_LOCAL_HOOK_B_SUFFIX = " — النهاية هتصدمك"

# لواحق محلية مميزة للبديل عند فشل النموذج (كلها تمرّ
# valid_hook مع العنوان؛ تُستخدم بالترتيب حتى n هوك).
_LOCAL_HOOK_SUFFIXES = (
    " — النهاية هتصدمك",
    " — والنهاية غير متوقعة",
    " — ليه عمل كده؟",
    " — الحقيقة انكشفت فجأة!",
    " — مستحيل تتوقع اللي حصل",
)


def _local_hooks(title, n):
    """بديل محلي: العنوان نفسه + العنوان بلواحق مميزة.
    يرجع حتى n هوكًا مميزًا صالحًا (بلا تكرار)."""
    title = _norm(title)
    base = title[:130] if len(title) > 130 else title
    out = []
    for cand in [title] + [base + s for s in _LOCAL_HOOK_SUFFIXES]:
        if cand and cand not in out and ideas_lib.valid_hook(cand):
            out.append(cand)
        if len(out) >= n:
            break
    # عنوان غير صالح أصلًا (يبدأ برقم مثلًا): بدائل عامة.
    generic = ["قصة صادمة — النهاية هتصدمك",
               "ليه حصل كده؟ الحقيقة انكشفت فجأة!",
               "ظلم وغدر — والنهاية غير متوقعة"]
    for cand in generic:
        if len(out) >= n:
            break
        if cand not in out and ideas_lib.valid_hook(cand):
            out.append(cand)
    return out[:n]


def _norm(text):
    return re.sub(r"\s+", " ", (text or "").strip())


def suggest_hooks(title, chat_fn=None):
    """اقترح هوكين مختلفين للعنوان: النموذج أولًا، وبديل محلي
    (العنوان نفسه + صيغة سؤال) عند غياب الشبكة. يرجع
    (هوك أ، هوك ب، المصدر)."""
    title = _norm(title)
    if chat_fn is not None:
        prompt = (
            "لصفحة فيسبوك «قصص وعبر» باللهجة المصرية: اقترح هوكين "
            "مختلفين لفيديو قصة بعنوان «%s». كل هوك جملة واحدة "
            "صادمة تُقال في أول ثانيتين ولا تبدأ برقم أبدًا. اكتب "
            "الهوكين في سطرين فقط، سطر لكل هوك، بلا أي نص آخر."
            % title)
        try:
            text = chat_fn(prompt)
            lines = [l.strip() for l in text.splitlines()
                     if l.strip()]
            hooks = [l for l in lines
                     if ideas_lib.valid_hook(l)]
            if len(hooks) >= 2 and hooks[0] != hooks[1]:
                return hooks[0], hooks[1], "omniroute"
        except Exception:
            pass
    return title, title + _LOCAL_HOOK_B_SUFFIX, "local"


def suggest_hooks_n(title, chat_fn=None, n=3):
    """اقترح n هوكًا مميزًا صالحًا للعنوان (افتراضي 3).

    نفس برومبت suggest_hooks ونفس قواعد ideas_lib.valid_hook،
    لكن يطلب من النموذج n هوكًا في n أسطر. عند فشل النموذج
    أو قلة الصالح منها يُكمَّل بالبديل المحلي (العنوان نفسه +
    لواحق مميزة). يرجع (قائمة الهوكات، المصدر)؛ المصدر
    "omniroute" إن جاءت كلها من النموذج، و"local" إن دخل
    البديل المحلي في أي منها، و"mixed" إن اختلطا.
    """
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("عدد الهوكات يجب أن يكون عددًا صحيحًا ≥ 1 "
                         "(وصل: %s)" % (n,))
    title = _norm(title)
    hooks = []
    src = "local"
    if chat_fn is not None:
        prompt = (
            "لصفحة فيسبوك «قصص وعبر» باللهجة المصرية: اقترح %d "
            "هوكات مختلفة لفيديو قصة بعنوان «%s». كل هوك جملة "
            "واحدة صادمة تُقال في أول ثانيتين ولا تبدأ برقم أبدًا. "
            "اكتب الهوكات في %d أسطر فقط، سطر لكل هوك، بلا أي نص "
            "آخر." % (n, title, n))
        try:
            text = chat_fn(prompt)
            lines = [l.strip() for l in text.splitlines()
                     if l.strip()]
            for line in lines:
                if line not in hooks and ideas_lib.valid_hook(line):
                    hooks.append(line)
                if len(hooks) >= n:
                    break
            if len(hooks) >= n:
                return hooks[:n], "omniroute"
            src = "mixed" if hooks else "local"
        except Exception:
            hooks = []
            src = "local"
    for cand in _local_hooks(title, n):
        if cand not in hooks:
            hooks.append(cand)
        if len(hooks) >= n:
            break
    return hooks[:n], src


def score_hooks(hooks, story_text=None):
    """درجة DNA لكل هوك عبر dna.score_hook الموجود (جدول
    maquina 0–10). يرجع قائمة قواميس score_hook بنفس ترتيب
    الإدخال؛ كل قاموس فيه hook/total/max/breakdown/verdict."""
    from lib import dna
    return [dna.score_hook(h, story_text=story_text)
            for h in (hooks or [])]


def create_ab_variants(video, hooks, out_dir, title=None,
                       cost_per_video=0, thumbnail_fn=None,
                       duration_fn=None, story_text=None):
    """ولّد مصغرة لكل نسخة من n هوكًا وسجّلها في ab-<وقت>.json.

    أوقات المصغرات موزعة بالتساوي بين 35% و65% من المدة
    (عند نسختين تطابق create_ab تمامًا: 35% و65%). يرجع
    السجل: variants مرتبة تنازليًا بدرجة DNA، وbest = الأعلى،
    مع بقاء hook_a/hook_b (أول نسختين) وcost_estimate_units
    (لكل نسخة + المجموع) للتوافق مع ab-results.
    cost_per_video: تقدير وحدات Veo لإنتاج كل بديل من جديد
    (الافتراضي 0 — نفس الفيديو، هوك+مصغرة فقط بلا توليد جديد).
    """
    video = os.path.abspath(os.path.expanduser(video))
    if not os.path.isfile(video):
        raise ValueError("ملف الفيديو غير موجود: %s" % video)
    hooks = [_norm(h) for h in (hooks or [])]
    if len(hooks) < 2:
        raise ValueError("اختبار A/B يحتاج هوكين مختلفين على الأقل "
                         "(وصل: %d)" % len(hooks))
    if any(not h for h in hooks):
        raise ValueError("الهوكات مطلوبة (لا هوك فارغ)")
    if any(not ideas_lib.valid_hook(h) for h in hooks):
        raise ValueError("كل هوك يجب أن يكون جملة واحدة صادمة بلا "
                         "رقم في البداية وبلا وسوم (≤140 حرفًا)")
    if len(set(hooks)) != len(hooks):
        raise ValueError("الهوكات متكررة — اختبار A/B يحتاج هوكات "
                         "مختلفة")
    if isinstance(cost_per_video, bool) \
            or not isinstance(cost_per_video, int) \
            or cost_per_video < 0:
        raise ValueError("تقدير تكلفة البديل يجب أن يكون عددًا صحيحًا "
                         "≥ 0 (وصل: %s)" % (cost_per_video,))
    duration_fn = duration_fn or thumbnail.video_duration
    thumbnail_fn = thumbnail_fn or thumbnail.make_thumbnail
    duration = duration_fn(video)
    scores = score_hooks(hooks, story_text=story_text)
    ts = time.strftime("%Y%m%d-%H%M%S")
    ab_dir = os.path.join(out_dir, "ab-%s" % ts)
    os.makedirs(ab_dir, exist_ok=True)
    count = len(hooks)
    variants = []
    for i, (hook, score) in enumerate(zip(hooks, scores)):
        frac = 0.35 if count == 1 else 0.35 + 0.30 * i / (count - 1)
        thumb = os.path.join(ab_dir, "thumb-%d.jpg" % (i + 1))
        thumbnail_fn(video, hook, thumb,
                     at_seconds=round(duration * frac, 1))
        variants.append({
            "hook": hook,
            "thumb": thumb,
            "dna_score": score["total"],
            "dna_max": score["max"],
            "dna_verdict": score["verdict"],
            "dna_breakdown": score["breakdown"],
            "cost": cost_per_video,
        })
    variants.sort(key=lambda v: v["dna_score"], reverse=True)
    best = variants[0]["hook"]
    cost_block = {
        "variant_%d" % (i + 1): cost_per_video
        for i in range(count)}
    cost_block["variant_a"] = cost_per_video
    cost_block["variant_b"] = cost_per_video
    cost_block["total"] = count * cost_per_video
    cost_block["note"] = ("نفس الفيديو — هوك ومصغرة فقط بلا توليد "
                          "جديد" if cost_per_video == 0
                          else "تقدير توليد كل بديل من جديد "
                               "(6 مقاطع Veo × 20 وحدة)")
    record = {
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "video": video,
        "title": title or "",
        "duration": round(duration, 1),
        "hook_a": hooks[0],
        "hook_b": hooks[1],
        "thumb_a": os.path.join(ab_dir, "thumb-1.jpg"),
        "thumb_b": os.path.join(ab_dir, "thumb-2.jpg"),
        "publish_title_a": hooks[0],
        "publish_title_b": hooks[1],
        "variants": variants,
        "best": best,
        "cost_estimate_units": cost_block,
        "note": AB_NOTE,
    }
    record_path = os.path.join(ab_dir, "ab-%s.json" % ts)
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    record["record_path"] = record_path
    return record


def create_ab(video, hook_a, hook_b, out_dir, title=None,
              thumbnail_fn=None, duration_fn=None, cost_per_video=0):
    """ولّد مصغرتين (أ عند 35% من المدة، ب عند 65%) وسجّل
    الزوج في ab-<وقت>.json داخل out_dir. يرجع السجل.
    thumbnail_fn(video, hook, out, at_seconds) -> مسار؛
    duration_fn(video) -> المدة بالثواني.
    cost_per_video: تقدير وحدات Veo لإنتاج كل بديل من جديد
    (الافتراضي 0 — نفس الفيديو، هوك+مصغرة فقط بلا توليد جديد؛
    وتوليد جديد كامل = 120 وحدة: 6 مقاطع × 20)."""
    video = os.path.abspath(os.path.expanduser(video))
    if not os.path.isfile(video):
        raise ValueError("ملف الفيديو غير موجود: %s" % video)
    hook_a, hook_b = _norm(hook_a), _norm(hook_b)
    if not hook_a or not hook_b:
        raise ValueError("الهوكان مطلوبان (أ و ب)")
    # نفس قواعد الأسلوب في ideas: بلا رقم في البداية وبلا وسوم
    # ASS و≤140 حرفًا — الهوك يُستخدم عنوان نشر أيضًا، فوسم
    # مثل {\fs200} كان يظهر في الكابشن/العنوان حرفيًا.
    if not ideas_lib.valid_hook(hook_a) \
            or not ideas_lib.valid_hook(hook_b):
        raise ValueError("الهوك يجب أن يكون جملة واحدة صادمة "
                         "بلا رقم في البداية وبلا وسوم (≤140 حرفًا)")
    if hook_a == hook_b:
        raise ValueError("الهوكان متطابقان — اختبار A/B يحتاج "
                         "هوكين مختلفين")
    if isinstance(cost_per_video, bool) \
            or not isinstance(cost_per_video, int) \
            or cost_per_video < 0:
        raise ValueError("تقدير تكلفة البديل يجب أن يكون عددًا صحيحًا "
                         "≥ 0 (وصل: %s)" % (cost_per_video,))
    duration_fn = duration_fn or thumbnail.video_duration
    thumbnail_fn = thumbnail_fn or thumbnail.make_thumbnail
    duration = duration_fn(video)
    ts = time.strftime("%Y%m%d-%H%M%S")
    ab_dir = os.path.join(out_dir, "ab-%s" % ts)
    os.makedirs(ab_dir, exist_ok=True)
    thumb_a = os.path.join(ab_dir, "thumb-a.jpg")
    thumb_b = os.path.join(ab_dir, "thumb-b.jpg")
    thumbnail_fn(video, hook_a, thumb_a,
                 at_seconds=round(duration * 0.35, 1))
    thumbnail_fn(video, hook_b, thumb_b,
                 at_seconds=round(duration * 0.65, 1))
    record = {
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "video": video,
        "title": title or "",
        "duration": round(duration, 1),
        "hook_a": hook_a,
        "hook_b": hook_b,
        "thumb_a": thumb_a,
        "thumb_b": thumb_b,
        "publish_title_a": hook_a,
        "publish_title_b": hook_b,
        "cost_estimate_units": {
            "variant_a": cost_per_video,
            "variant_b": cost_per_video,
            "total": 2 * cost_per_video,
            "note": ("نفس الفيديو — هوك ومصغرة فقط بلا توليد جديد"
                     if cost_per_video == 0
                     else "تقدير توليد كل بديل من جديد "
                          "(6 مقاطع Veo × 20 وحدة)"),
        },
        "note": AB_NOTE,
    }
    record_path = os.path.join(ab_dir, "ab-%s.json" % ts)
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    record["record_path"] = record_path
    return record


def fetch_fb_posts(facebook_bin, page_id, limit=10, run=None):
    """آخر منشورات الصفحة (حتى limit) كمقاييس موحّدة عبر
    analyze._fb_entry_metrics. يرجع (قائمة، ملاحظة)."""
    runner = run or (lambda cmd, **kw: subprocess.run(
        cmd, capture_output=True, text=True, timeout=120, **kw))
    try:
        proc = runner([facebook_bin, "pages", "posts", "list",
                       "--page-id", str(page_id),
                       "--limit", str(limit)])
    except FileNotFoundError:
        return [], "facebook-cli غير متاح"
    except subprocess.TimeoutExpired:
        return [], "انتهت مهلة قراءة منشورات فيسبوك"
    if proc.returncode != 0:
        return [], ("فشل قراءة منشورات فيسبوك (رمز الخروج %d)"
                    % proc.returncode)
    try:
        data = json.loads(proc.stdout or "")
    except ValueError:
        return [], "مخرجات facebook-cli ليست JSON صالحًا"
    entries = []
    for raw in (data.get("results") or []):
        try:
            entries.append(analyze._fb_entry_metrics(raw))
        except Exception:
            continue
    return entries, None


def fetch_yt_uploads(channel_id, limit=10, run=None):
    """آخر فيديوهات القناة (حتى limit): {title, views,
    video_id}. يرجع (قائمة، ملاحظة)."""
    if not channel_id:
        return [], "معرّف قناة يوتيوب غير مضبوط"
    if not re.fullmatch(r"UC[A-Za-z0-9_-]{10,}", channel_id):
        return [], "معرّف قناة يوتيوب غير صالح: %s" % channel_id
    import urllib.parse
    playlist_url = ("https://www.youtube.com/playlist?"
                    + urllib.parse.urlencode(
                        {"list": "UU" + channel_id[2:]}))
    try:
        playlist = analyze._run_ytdlp(
            ["--flat-playlist", "-J", playlist_url], run=run)
    except (analyze.AnalyzeError, FileNotFoundError) as e:
        return [], "تعذرت قراءة قائمة رفع يوتيوب: %s" % e
    except subprocess.TimeoutExpired:
        return [], "انتهت مهلة قراءة قائمة رفع يوتيوب"
    out = []
    for entry in (playlist.get("entries") or [])[:limit]:
        out.append({"title": entry.get("title") or "",
                    "views": entry.get("view_count"),
                    "video_id": entry.get("id") or ""})
    return out, None


def match_variant(entries, needle, text_key):
    """أول منشور يحتوي نص الهوك (بعد الطي). None إن لم يوجد."""
    needle = _norm(needle)
    if not needle:
        return None
    for entry in entries:
        if needle in _norm(entry.get(text_key) or ""):
            return entry
    return None


def compare_ab(record, fb_entries, yt_entries):
    """قارن النسختين: مشاهدات كل نسخة على كل منصة + المجموع +
    الفائز. نسخة غير موجودة في القوائم = غير منشورة بعد."""
    result = {"record": record["record_path"]
              if "record_path" in record else None,
              "variants": {}, "winner": None, "decisive": False}
    fb_a = match_variant(fb_entries, record["hook_a"], "caption")
    fb_b = match_variant(fb_entries, record["hook_b"], "caption")
    yt_a = match_variant(yt_entries, record["hook_a"], "title")
    yt_b = match_variant(yt_entries, record["hook_b"], "title")
    if fb_a is not None and fb_a is fb_b:
        fb_b = None
    if yt_a is not None and yt_a is yt_b:
        yt_b = None
    for key, fb, yt in (("a", fb_a, yt_a), ("b", fb_b, yt_b)):
        fb_views = fb.get("views") if fb else None
        yt_views = yt.get("views") if yt else None
        total = sum(v for v in (fb_views, yt_views)
                    if isinstance(v, (int, float)))
        result["variants"][key] = {
            "hook": record["hook_a" if key == "a" else "hook_b"],
            "facebook_views": fb_views,
            "youtube_views": yt_views,
            "total_views": total if (fb_views is not None
                                     or yt_views is not None) else None,
            "published": fb is not None or yt is not None,
        }
    a = result["variants"]["a"]
    b = result["variants"]["b"]
    if a["published"] and b["published"] \
            and a["total_views"] is not None \
            and b["total_views"] is not None:
        result["decisive"] = True
        if a["total_views"] > b["total_views"]:
            result["winner"] = "a"
        elif b["total_views"] > a["total_views"]:
            result["winner"] = "b"
        else:
            result["winner"] = "tie"
    return result


def format_comparison(record, comparison):
    """نص عربي لنتيجة المقارنة."""
    lines = ["== نتيجة اختبار A/B ==",
             "الفيديو: %s" % record["video"],
             "أ: %s" % record["hook_a"],
             "ب: %s" % record["hook_b"],
             ""]
    for key, label in (("a", "أ"), ("b", "ب")):
        v = comparison["variants"][key]
        if not v["published"]:
            lines.append("نسخة %s: غير منشورة بعد — انشرها بعنوان "
                         "هوكها ثم أعد ab-results" % label)
            continue
        lines.append("نسخة %s: فيسبوك %s — يوتيوب %s — المجموع %s"
                     % (label,
                        analyze.format_value(v["facebook_views"]),
                        analyze.format_value(v["youtube_views"]),
                        analyze.format_value(v["total_views"])))
    lines.append("")
    cost = record.get("cost_estimate_units") or {}
    if cost:
        lines.append("تقدير التكلفة (وحدات Veo): أ %s — ب %s — المجموع %s"
                     % (cost.get("variant_a"), cost.get("variant_b"),
                        cost.get("total")))
        if cost.get("note"):
            lines.append("  %s" % cost["note"])
        lines.append("")
    if not comparison["decisive"]:
        lines.append("النتيجة: غير حاسمة بعد — انشر النسختين "
                     "وانتظر مشاهداتهما.")
    elif comparison["winner"] == "tie":
        lines.append("النتيجة: تعادل — الهوكان متساويان حتى الآن.")
    else:
        win = comparison["winner"]
        lines.append("الفائز حتى الآن: نسخة %s (%s)"
                     % ("أ" if win == "a" else "ب",
                        comparison["variants"][win]["hook"]))
    lines.append("")
    lines.append(AB_NOTE)
    return "\n".join(lines) + "\n"
