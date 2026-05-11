# SubSync Studio

تطبيق ويب لمزامنة ملفات الترجمة مع أي نسخة فيديو (Web-DL / BluRay / HDTV ...) بدقة على طول الفيديو، عبر **تحليل الموجة الصوتية**.

## المميزات

- **مزامنة عبر الصوت (Audio VAD)** باستخدام [`ffsubsync`](https://github.com/smacke/ffsubsync) — تطابق دقيق طوال الفيديو حتى لو اختلفت الـ intros/outros/إعلانات.
- **مزامنة عبر ترجمة مرجعية** عندما يتوفر ملف ترجمة آخر متزامن مع نفس الفيديو.
- **معاينة الفيديو مع الترجمة** مباشرة في المتصفح بعد المزامنة.
- **محرر يدوي للتوقيتات** مع إزاحة جماعية بنقرة (+/- 500ms).
- **دعم متعدد الصيغ**: SRT, ASS/SSA, VTT, SUB (إدخال) — SRT/ASS/VTT (إخراج).
- **بحث وتحميل تلقائي من OpenSubtitles** (يحتاج API key مجاني).

## المتطلبات

- Python 3.9 أو أحدث.
- `ffmpeg` مثبّت على النظام (يستخدمه ffsubsync لاستخراج الصوت).
- (اختياري) مفتاح OpenSubtitles من https://www.opensubtitles.com/consumers

## التشغيل

```bash
git clone <repo-url>
cd Mohsin1222222

# (اختياري) فعّل البحث عن الترجمات من OpenSubtitles
export OPENSUBTITLES_API_KEY=your_key_here

./run.sh
```

ثم افتح المتصفح على: http://localhost:8000

### بدون السكربت

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

## كيف يعمل

1. ارفع **الفيديو** (أي صيغة/جودة).
2. ارفع **ملف الترجمة** غير المتزامن.
3. اضغط **مزامنة الآن** — يقوم الخادم باستخراج صوت الفيديو، يكشف فترات الكلام، ثم يطابقها مع توقيتات الترجمة.
4. شاهد المعاينة، عدّل يدوياً إن أردت، ثم نزّل الملف بصيغة SRT/ASS/VTT.

> 💡 إذا لم يتوفر فيديو، ارفع **ترجمة مرجعية** بدلاً منه — ستتم المزامنة بمقارنة سلاسل الأسطر زمنياً.

## بنية المشروع

```
backend/
  main.py            # FastAPI app + endpoints
  sync_engine.py     # ffsubsync wrapper
  opensubtitles.py   # REST client
  converters.py      # SRT/ASS/VTT conversion (pysubs2)
frontend/
  index.html
  styles.css
  app.js
storage/
  uploads/   # ملفات الإدخال المؤقتة
  outputs/   # نتائج المزامنة
```

## نقاط REST

| الطريقة | المسار | الوصف |
| ------ | ------ | ----- |
| GET    | `/api/health` | فحص جاهزية ffsubsync/ffmpeg/OpenSubtitles |
| POST   | `/api/sync` | يستقبل `subtitle` + (`video` أو `reference`) ويُعيد ملف متزامن + معاينة VTT |
| POST   | `/api/save` | حفظ تعديلات المحرر |
| GET    | `/api/download/{session}/{file}?fmt=srt\|ass\|vtt` | تنزيل النتيجة |
| GET    | `/api/search?q=...` | بحث في OpenSubtitles |
| POST   | `/api/fetch` | تحميل ملف ترجمة مختار |

## ملاحظات

- المعالجة محلية بالكامل، لا يُرسل أي ملف لخدمات خارجية إلا عند استخدام بحث OpenSubtitles.
- المزامنة عبر الصوت تستغرق عادة من 10 ثوانٍ إلى دقيقة على فيلم 2 ساعة.
- لتحسين الأداء، استخدم نسخة فيديو بمعدل عيّنات ثابت (CFR).
