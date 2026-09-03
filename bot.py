import os
import time
import random
import requests
from datetime import datetime

# ============ الإعدادات (من Environment Variables) ============
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# الموديل المجاني من OpenRouter (غيّره لو عايز موديل تاني)
# كل الموديلات دي ":free" — مجانية 100%
OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "minimax/minimax-m3:free"
)

# الموديلات المجانية المتاحة (لو عايز تجرّب تاني):
# "minimax/minimax-m3:free"
# "google/gemma-4-31b-it:free"
# "nvidia/nemotron-3-super-120b-a12b:free"
# "nvidia/nemotron-3-ultra-550b-a55b:free"
# "nvidia/nemotron-3.5-lightning:free"
# "z-ai/glm-5.2:free"
# "cohere/north-mini-code:free"

# ============ مواضيع متنوعة عشان المعلومة متتكررش ============
NURSING_TOPICS = [
    "Neonatal Nursing (NICU)",
    "Intensive Care Nursing",
    "Pediatric Nursing",
    "Cardiac Nursing",
    "Emergency Nursing",
    "Surgical Nursing",
    "Infection Control",
    "Pharmacology basics for nurses",
    "IV therapy and venipuncture",
    "Wound care and dressing",
    "Vital signs interpretation",
    "Patient safety",
    "ECG basics",
    "Ventilator basics",
    "Fluid and electrolyte balance",
    "Pain management",
    "Diabetes management",
    "Hypertension management",
    "Communication with patients (ISBAR)",
    "Hand hygiene and PPE",
]

# ============ الـ Prompt ============
PROMPT_TEMPLATE = """أنت ممرض خبير ومحاضر تمريض مصري. المطلوب:

📋 **Nursing Reminder** عن موضوع: {topic}

النبطة بالشكل ده بالظبط:

1️⃣ **المعلومة**: جملة أو جملتين بالمصري العامي المباشر (زي: «بص، الموضوع كذا...» أو «خد بالك من...»)

2️⃣ **ليه مهمة؟**: ايه الأهمية السريرية ليها

3️⃣ **Clinical connection**: اربطها بحالة عملية أو إجراء تمريضي

4️⃣ **طريقة حفظ**: Mnemonic أو طريقة سهلة للحفظ

5️⃣ **MCQ**: سؤال اختيار من متعدد (4 اختيارات) عشان الطالب يختبر نفسه

6️⃣ **الإجابة**: الإجابة الصح مع شرحها في سطر

7️⃣ **المصدر**: منظمة أو كتاب محدد (WHO / CDC / NANDA / Kozier & Erb's Fundamentals of Nursing / Hockenberry)

⚠️ **قواعد مهمة**:
- بالعربي المصري العامي
- كل section في سطر أو سطرين بحد أقصى
- من غير حشو أو تكرار
- ما تخترعش معلومات — لو مش متأكد، قول "غير متأكد" في المصدر
"""

# ============ دوال OpenRouter ============
def get_nursing_reminder():
    """يجيب Nursing Reminder من OpenRouter API"""
    topic = random.choice(NURSING_TOPICS)

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://t.me/nursing_facts_bot",
                "X-Title": "Nursing Reminder Bot",
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "أنت ممرض خبير ومحاضر تمريض. تجاوب باللهجة المصرية العامية. مختصر ومباشر. ما تخترعش معلومات."
                    },
                    {
                        "role": "user",
                        "content": PROMPT_TEMPLATE.format(topic=topic)
                    }
                ],
                "max_tokens": 800,
                "temperature": 0.7,
            },
            timeout=60,
        )

        if response.status_code != 200:
            error_msg = response.json().get("error", {}).get("message", "Unknown error")
            return f"⚠️ OpenRouter Error: {error_msg}"

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return content

    except requests.exceptions.Timeout:
        return "⚠️ Timeout: OpenRouter took too long. Will retry next hour."
    except Exception as e:
        return f"⚠️ Error: {str(e)}"


# ============ دالة إرسال تليجرام ============
def send_telegram(message):
    """يبعت رسالة على تليجرام"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials missing!")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # تليجرام حد النص 4096 حرف — لو أطول نقسّمه
    if len(message) <= 4096:
        try:
            response = requests.post(
                url,
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=30,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Telegram error: {e}")
            return False
    else:
        # نقسّم على أجزاء
        parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
        for part in parts:
            try:
                requests.post(
                    url,
                    data={"chat_id": TELEGRAM_CHAT_ID, "text": part, "parse_mode": "HTML"},
                    timeout=30,
                )
            except Exception as e:
                print(f"Telegram error: {e}")
                return False
        return True


# ============ Main Loop ============
if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Nursing Reminder Bot Started!")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🧠 Model: {OPENROUTER_MODEL}")
    print("=" * 50)

    # فحص الـ credentials
    if not OPENROUTER_API_KEY:
        print("❌ OPENROUTER_API_KEY is missing!")
        exit(1)
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN is missing!")
        exit(1)
    if not TELEGRAM_CHAT_ID:
        print("❌ TELEGRAM_CHAT_ID is missing!")
        exit(1)

    # ابعت أول رسالة فوراً (عشان تعرف إنه شغّال)
    print("\n📤 Sending first reminder...")
    reminder = get_nursing_reminder()
    success = send_telegram(reminder)
    if success:
        print("✅ First reminder sent!")
    else:
        print("❌ Failed to send first reminder")

    # كل ساعة
    print("\n⏰ Now running on hourly schedule...")
    while True:
        time.sleep(3600)  # 3600 ثانية = ساعة
        try:
            now = datetime.now().strftime("%H:%M")
            print(f"\n[{now}] Generating next reminder...")
            reminder = get_nursing_reminder()
            send_telegram(reminder)
            print(f"✅ Sent at {now}")
        except KeyboardInterrupt:
            print("\n👋 Bot stopped.")
            break
        except Exception as e:
            print(f"❌ Error in loop: {e}")
            # استمر حتى لو حصلت مشكلة
            time.sleep(60)
