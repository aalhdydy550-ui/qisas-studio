# المُثبِّتات العدائية — `tests/fixtures/adversarial/`

مُثبِّتات تحقن عمدًا عيوب الخط المعروفة، ليُثبت الاختبار أن الخط
يمسكها (v0.1.37 — البند 4 من تقرير tinker).

| الملف | العيب المحقون | ما يجب أن يمسكه |
|---|---|---|
| `hook-numeral.json` | هوك يبدأ برقم («3 أخطاء…») | `dna.normalize_hook` يعيد كتابته «ثلاثة…»؛ و`stage()` يطبّقه |
| `follow-gate-caption.txt` | جملة «لو عايز الجزء الثاني اعمل متابعة» | `caption_check` يرفضها؛ و`fix_caption` يستبدلها بالدعوة المعتمدة |
| `no-silence.wav` + `no-silence-captions.json` | سرد متصل بلا فاصل صمت (نغمة 3ث) | `detect_silences` يجد لا شيء؛ وفحص صوت العبارات يتخطى بلا إيجاب كاذب؛ وتوقيتات الكلمات تقسّم العبارات |
| `long-story.json` | مدة مخططة 61.5ث (>60ث) | `check.eval_duration` يرفضها؛ وفيديو 61ث حقيقي يفشل فحص المدة |
| `broken-caption.ass` | U+FFFD + حروف Presentation Forms | `ass_shaping.audit_ass_file` يعلّم `replacement_char` و`presentation_form` |

إعادة التوليد:

```bash
python3 tests/make_adversarial_fixtures.py
```

الصوت WAV يُولَّد برمجيًا (نغمة جيبية) والفيديو الطويل يُولَّد في
الاختبار عبر `ffmpeg lavfi` — لا ملفات ثنائية ملتزمة عمدًا.
الاختبار: `tests/test_demo_adversarial.py`.
