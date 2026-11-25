#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""فهرس القصص والفيديوهات — Qdrant محلي + تضمينات Ollama
(جولة v0.1.48 — توصيتا المسح 1+2).

الوضع الوحيد: Qdrant **محلي** (`QdrantClient(path=...)`) —
بلا خادم وبلا Docker وبلا سحابة وبلا مفاتيح. التخزين تحت
`runs/story-index/` داخل مجلد studio (لا يُلوَّث جذر
المستودع بملفات فهرس مبعثرة — المجلد نفسه تحت `runs/` مع
باقي مخرجات التشغيل).

مجموعتان منفصلتان (لكل منهما بُعد المتجه نفسه، يُقاس من أول
تضمين فعلي):
- `stories`: قصص الطابور — حمولة {kind, title, text}.
- `videos`: فيديوهات منشورة سابقة — حمولة {kind, hook, title,
  views, hook_score} — للبحث عن «أقرب فيديو سابق» عند اقتراح
  هوك جديد أو تحليل أداء.

`qdrant_client` اعتمادية **اختيارية**: عند غيابها كل الدوال
ترجع «غير متاح» بأدب (False / [] / None) بلا استثناء، وكل
مستدعٍ (الطابور، التحليل، A/B) يعمل fail-open كأن الفهرس
غير موجود. التضمينات كذلك اختيارية: `embed_fn` قابلة للحقن
(للاختبارات)، والافتراضي `omniroute_client.embed_ollama`
(Ollama محلي — خادم متوقف أو موديل غير مثبّت = غير متاح).

التفعيل **صريح**: لا مستدعٍ يفحص الفهرس الافتراضي من
تلقاء نفسه — الفهرس يُمرَّر (كائن أو مسار) عند الاستدعاء،
والتوصيل في studio.py بيد المنسّق. السبب مثبَت حيًا في هذه
الجولة: فحص تلقائي بالفهرس الافتراضي رفض قصص اختبار
موجودة («قصة متوازية N» تختلف برقم فقط — شبه مكررة فعلًا
بـ 0.86–0.90) ولوّث الفهرس الدائم ببيانات اختبار فصار
يرفض إعادة إضافة القصة نفسها بتشابه 1.00.

عتبة التشابه `SIMILARITY_THRESHOLD = 0.70` (كوساين):
معايرة حيّة على القصص الحقيقية نفسها (جولة v0.1.48، نموذج
‏bge-m3): شبه مكررة 0.75–0.80 (النجار بصياغة مختلفة 0.8027،
عائشة بصياغة مختلفة 0.7475 — والقصة الصحيحة أولًا في
الحالتين)، وقصتان مختلفتا الموضوع 0.49–0.53، وغير متعلقة
(عنزة/سيارات) 0.28–0.42؛ فـ 0.70 يفصل المنطقتين: ~0.05
تحت أدنى شبه مكررة مقاسة (0.7475) و~0.17 فوق أعلى مختلف
مقاس (0.5285). البديل المرفوض nomic-embed-text
(~274MB) خلط المنطقتين: شبه مكررة 0.9117 مقابل قصة مختلفة
0.9005، وصياغة عائشة طابقت قصة خاطئة أولًا (0.8733 مقابل
0.8347 للقصة الصحيحة) — فلا يصلح رغم صغره. وإن غيّر نموذج
التضمين مستقبلًا تُعاد معايرة العتبة بأرقام جديدة قبل تغيير
الثابت، وتُعاد فهرسة المجموعات (بُعد المتجه جزء من
المجموعة).
"""
import os
import uuid

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import Distance, PointStruct, VectorParams
    _QDRANT_AVAILABLE = True
except ImportError:  # pragma: no cover - مسار الاعتمادية الاختيارية
    QdrantClient = None
    Distance = None
    PointStruct = None
    VectorParams = None
    _QDRANT_AVAILABLE = False


def qdrant_available():
    """هل مكتبة qdrant_client مثبّتة؟"""
    return _QDRANT_AVAILABLE


# عتبة التشابه (كوساين) — انظر توثيق المعايرة في docstring أعلاه.
SIMILARITY_THRESHOLD = 0.70

STORIES_COLLECTION = "stories"
VIDEOS_COLLECTION = "videos"

# مساحة اسم UUIDv5: معرّف ثابت لتوليد معرّفات نقاط حتمية
# (إعادة فهرسة القصة نفسها تحدّث نقطتها بدل تكرارها).
_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _studio_dir():
    """مجلد studio (أب مجلد lib/)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def default_index_path():
    """مسار التخزين الافتراضي: runs/story-index/ داخل studio."""
    return os.path.join(_studio_dir(), "runs", "story-index")


def _default_embed_fn():
    """دالة التضمين الافتراضية (Ollama المحلي)."""
    from lib import omniroute_client
    return omniroute_client.embed_ollama


class StoryIndex:
    """فهرس محلي واحد (قصص + فيديوهات) فوق Qdrant المحلي.

    path: مجلد تخزين Qdrant (افتراضي runs/story-index/).
    embed_fn: (text) -> list[float] — قابلة للحقن في
    الاختبارات؛ والافتراضي embed_ollama. vector_size: بُعد
    المتجه — يُقاس تلقائيًا من أول تضمين إن لم يُمرَّر.
    available: False إن غابت qdrant_client — وكل الطرق ترجع
    «غير متاح» بلا استثناء.
    """

    def __init__(self, path=None, embed_fn=None, vector_size=None):
        self.path = os.path.abspath(os.path.expanduser(
            path or default_index_path()))
        self.embed_fn = embed_fn
        self.vector_size = vector_size
        self.available = _QDRANT_AVAILABLE
        self._client = None
        self._collections_ready = set()

    def close(self):
        """أغلق عميل Qdrant المحلي (يتجنب ضجيج __del__ عند
        إغلاق المفسّر). آمنة عند غياب العميل."""
        client = self._client
        self._client = None
        self._collections_ready = set()
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    # -- بنية تحتية -------------------------------------------------
    def _client_or_none(self):
        if not self.available:
            return None
        if self._client is None:
            try:
                self._client = QdrantClient(path=self.path)
            except Exception:
                return None
        return self._client

    def _embed(self, text):
        fn = self.embed_fn or _default_embed_fn()
        vector = fn(text)
        if not isinstance(vector, (list, tuple)) or not vector:
            raise ValueError("التضمين فارغ أو غير صالح")
        return [float(v) for v in vector]

    def _ensure_collection(self, name, vector_size):
        client = self._client_or_none()
        if client is None:
            return False
        if name in self._collections_ready:
            return True
        try:
            if not client.collection_exists(name):
                client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=int(vector_size),
                        distance=Distance.COSINE))
        except Exception:
            return False
        self._collections_ready.add(name)
        return True

    def _collection_size(self, name):
        """بُعد متجهات مجموعة موجودة، أو None إن غابت."""
        client = self._client_or_none()
        if client is None:
            return None
        try:
            if not client.collection_exists(name):
                return None
            info = client.get_collection(name)
            vectors = info.config.params.vectors
            return int(getattr(vectors, "size", 0) or 0) or None
        except Exception:
            return None

    def _upsert(self, collection, point_id, vector, payload):
        if not self._ensure_collection(collection, len(vector)):
            return False
        client = self._client_or_none()
        if client is None:
            return False
        try:
            client.upsert(collection_name=collection, points=[
                PointStruct(id=point_id, vector=vector,
                            payload=payload)])
        except Exception:
            return False
        return True

    def _search(self, collection, vector, top_n, threshold):
        client = self._client_or_none()
        if client is None:
            return []
        size = self._collection_size(collection)
        if size is None or size != len(vector):
            # مجموعة غائبة أو بُعدها لا يطابق نموذج التضمين
            # الحالي (تبديل نموذج) — لا نتائج بدل خطأ.
            return []
        try:
            hits = client.query_points(
                collection_name=collection,
                query=vector,
                limit=max(1, int(top_n)),
                score_threshold=(threshold
                                 if threshold is not None else None),
                with_payload=True).points
        except Exception:
            return []
        out = []
        for hit in hits:
            payload = dict(hit.payload or {})
            payload["score"] = float(hit.score)
            out.append(payload)
        return out

    # -- قصص --------------------------------------------------------
    def index_story(self, title, text, payload=None):
        """فهرس قصة (عنوان + نص). يرجع معرّف النقطة أو None
        عند غياب الفهرس/التضمين. إعادة فهرسة القصة نفسها
        تحدّث نقطتها (معرّف حتمي من العنوان والنص)."""
        if not self.available:
            return None
        title = (title or "").strip()
        text = (text or "").strip()
        if not title or not text:
            return None
        try:
            vector = self._embed(title + "\n" + text)
        except Exception:
            return None
        point_id = str(uuid.uuid5(
            _NAMESPACE, "story\n%s\n%s" % (title, text)))
        data = {"kind": "story", "title": title, "text": text}
        if isinstance(payload, dict):
            data.update(payload)
        if self._upsert(STORIES_COLLECTION, point_id, vector, data):
            return point_id
        return None

    def find_similar(self, text, top_n=5,
                     threshold=SIMILARITY_THRESHOLD):
        """أقرب القصص المفهرسة لنص — قائمة حمولات فيها
        title/text/score (مرتبة تنازليًا بالتشابه)، أو []
        عند غياب الفهرس/التضمين أو عدم بلوغ العتبة."""
        if not self.available:
            return []
        text = (text or "").strip()
        if not text:
            return []
        try:
            vector = self._embed(text)
        except Exception:
            return []
        return self._search(STORIES_COLLECTION, vector,
                            top_n, threshold)

    # -- فيديوهات ---------------------------------------------------
    def index_video(self, hook, title=None, views=None,
                    hook_score=None, payload=None):
        """فهرس فيديو سابق بهوكه (نص البحث) + عنوانه ومشاهداته
        ودرجة هوكه. يرجع معرّف النقطة أو None عند الغياب.
        إعادة فهرسة الهوك نفسه تحدّث نقطته."""
        if not self.available:
            return None
        hook = (hook or "").strip()
        if not hook:
            return None
        try:
            vector = self._embed(hook)
        except Exception:
            return None
        point_id = str(uuid.uuid5(_NAMESPACE, "video\n%s" % hook))
        data = {"kind": "video", "hook": hook,
                "title": (title or "").strip() or None,
                "views": views, "hook_score": hook_score}
        if isinstance(payload, dict):
            data.update(payload)
        if self._upsert(VIDEOS_COLLECTION, point_id, vector, data):
            return point_id
        return None

    def find_nearest_video(self, hook_text, top_n=1):
        """أقرب فيديو سابق لهوك/عنوان — قاموس {hook, title,
        views, hook_score, similarity} أو None عند الغياب.
        بلا عتبة هنا عمدًا: «الأقرب» معلومة استرشادية في
        الاقتراحات (لا رفض)، فتُعرض مع درجتها ويحكم عليها
        القارئ — أما الرفض في الطابور فله عتبة 0.70."""
        if not self.available:
            return None
        hook_text = (hook_text or "").strip()
        if not hook_text:
            return None
        try:
            vector = self._embed(hook_text)
        except Exception:
            return None
        hits = self._search(VIDEOS_COLLECTION, vector,
                            top_n, threshold=None)
        if not hits:
            return None
        best = hits[0]
        return {"hook": best.get("hook"),
                "title": best.get("title"),
                "views": best.get("views"),
                "hook_score": best.get("hook_score"),
                "similarity": best.get("score")}


# -- دوال على مستوى الوحدة (فهرس افتراضي كسول) ----------------------
_default_index = None


def resolve_index(index=None, embed_fn=None):
    """حلّ فهرس للاستخدام — كائن StoryIndex جاهز، أو مسار
    مجلد (يُبنى StoryIndex عليه). بلا index ممرَّر يُرجع
    None: التفعيل **صريح** عند المستدعي (لا فحص تلقائي
    بالفهرس الافتراضي) — فالفهرس المشترك الدائم يتلوث
    ببيانات الاختبار ويُبطئ كل إضافة بتضمينين، والاختبارات
    الموجودة (قصص «متوازية» تختلف برقم فقط) شبه مكررة
    فعلًا فيرفضها الفحص. التوصيل يتم في studio.py (مالك
    المنسّق) بتمرير الفهرس الافتراضي صراحةً عندها."""
    if index is not None:
        if isinstance(index, str):
            return StoryIndex(path=index, embed_fn=embed_fn)
        return index
    return None


def nearest_video_for(hook_text, index=None, embed_fn=None):
    """أقرب فيديو سابق لهوك/عنوان — قاموس أو None.

    غلاف fail-open: أي غياب أو فشل (بلا qdrant-client، بلا
    index ممرَّر، بلا Ollama، بلا نتيجة) يرجع None بلا
    استثناء — فالمستدعي يحذف الحقل بصمت."""
    try:
        idx = resolve_index(index, embed_fn)
        if idx is None or not getattr(idx, "available", False):
            return None
        return idx.find_nearest_video(hook_text)
    except Exception:
        return None


def get_default_index(embed_fn=None):
    """الفهرس الافتراضي (runs/story-index/) — يُنشأ كسولًا
    مرة واحدة. None إن غابت qdrant_client."""
    global _default_index
    if _default_index is None:
        if not _QDRANT_AVAILABLE:
            return None
        _default_index = StoryIndex(embed_fn=embed_fn)
    return _default_index


def default_index_exists():
    """هل يوجد فهرس افتراضي مبني أصلًا (مجلده موجود)؟

    مساعِد للتوصيل في studio.py (مالك المنسّق) — لا
    يستخدمه أي مستدعٍ تلقائيًا (التفعيل صريح، انظر
    resolve_index)."""
    return os.path.isdir(default_index_path())


def index_story(title, text, payload=None, index=None):
    """فهرس قصة في الفهرس الافتراضي (أو الممرَّر)."""
    idx = index or get_default_index()
    if idx is None:
        return None
    return idx.index_story(title, text, payload=payload)


def find_similar(text, top_n=5, threshold=SIMILARITY_THRESHOLD,
                 index=None):
    """أقرب القصص لنص في الفهرس الافتراضي (أو الممرَّر)."""
    idx = index or get_default_index()
    if idx is None:
        return []
    return idx.find_similar(text, top_n=top_n, threshold=threshold)


def index_video(hook, title=None, views=None, hook_score=None,
                payload=None, index=None):
    """فهرس فيديو سابق في الفهرس الافتراضي (أو الممرَّر)."""
    idx = index or get_default_index()
    if idx is None:
        return None
    return idx.index_video(hook, title=title, views=views,
                           hook_score=hook_score, payload=payload)


def find_nearest_video(hook_text, top_n=1, index=None):
    """أقرب فيديو سابق في الفهرس الافتراضي (أو الممرَّر)."""
    idx = index or get_default_index()
    if idx is None:
        return None
    return idx.find_nearest_video(hook_text, top_n=top_n)
