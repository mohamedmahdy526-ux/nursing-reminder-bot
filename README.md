# 🏥 Nursing Reminder Bot

بوت تليجرام يبعث **معلومة تمريضية** كل ساعة باللهجة المصرية العامية، بأسلوب تعليمي مُنظَّم.

## 📋 الـ Prompt Format

كل رسالة بتيجي بالشكل ده:

1️⃣ **المعلومة** — جملة أو جملتين بالمصري
2️⃣ **ليه مهمة؟** — الأهمية السريرية
3️⃣ **Clinical connection** — ربط بحالة عملية
4️⃣ **طريقة حفظ** — Mnemonic
5️⃣ **MCQ** — سؤال اختيار من متعدد
6️⃣ **الإجابة** — مع الشرح
7️⃣ **المصدر** — منظمة أو كتاب معتمد

## 🧰 Tech Stack

- **Python 3.11+**
- **OpenRouter API** (موديل مجاني)
- **Telegram Bot API**
- **GSM Host** (Free Tier) أو أي VPS

## 🚀 التشغيل محلياً

### 1. تنصيب المكتبات
```bash
pip install -r requirements.txt
```

### 2. حط الـ Secrets كـ Environment Variables
```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
export OPENROUTER_API_KEY="..."
```

### 3. شغّل
```bash
python bot.py
```

## 🔐 إعداد Telegram Bot

1. ابعت لـ **@BotFather** على تليجرام
2. اكتب `/newbot` واتبع الخطوات
3. انسخ الـ **Token**
4. ابعت أي رسالة للبوت بتاعك
5. افتح `https://api.telegram.org/bot<TOKEN>/getUpdates` وانسخ الـ **chat_id**

## 🔑 إعداد OpenRouter

1. سجّل في [openrouter.ai](https://openrouter.ai)
2. روح لـ [Keys](https://openrouter.ai/settings/keys)
3. اعمل **API Key** جديد
4. انسخه

## 📦 الملفات

- `bot.py` — السكريبت الرئيسي
- `requirements.txt` — المكتبات المطلوبة
- `.github/workflows/run-bot.yml` — GitHub Actions (24/7)

## 🆓 الموديلات المجانية المتاحة

عدّل `OPENROUTER_MODEL` في `bot.py`:

| Model | الميزة |
|---|---|
| `minimax/minimax-m3:free` | الافتراضي |
| `google/gemma-4-31b-it:free` | جودة عالية |
| `nvidia/nemotron-3-super-120b-a12b:free` | قوي |
| `nvidia/nemotron-3.5-lightning:free` | سريع |

## 📜 الترخيص

MIT
