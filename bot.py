"""
🏥 Nursing Reminder Bot
- بوت تليجرام يبعث معلومة تمريضية كل ساعة من 08:00 إلى 22:00 بتوقيت القاهرة
- /start لتفعيل التذكيرات
- /stop لإيقافها
- /now لإرسال Reminder فورًا للتجربة
- /status لمعرفة حالة البوت
- يحفظ المواضيع السابقة لمنع التكرار
- بدون إرسال رسالة تلقائية عند بدء التشغيل
- Africa/Cairo timezone
- Telegram Plain Text
- OpenRouter API
"""

import os
import json
import time
import random
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# ============ Logging ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("nursing-bot")

# ============ إعدادات من Environment Variables ============
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m3:free").strip()
CAIRO_TZ = ZoneInfo("Africa/Cairo")

# الساعات اللي البوت هيشتغل فيها بتوقيت القاهرة (08:00 → 22:00)
ACTIVE_HOURS = list(range(8, 23))  # 8, 9, 10, ..., 22

# ملف حفظ المواضيع اللي اتبعتت (عشان نمنع التكرار)
HISTORY_FILE = Path("sent_topics.json")
MAX_HISTORY = 50  # نحفظ آخر 50 موضوع

# ============ قائمة المواضيع ============
NURSING_TOPICS = [
    "Neonatal Nursing (NICU) - Respiratory Distress Syndrome",
    "Neonatal Nursing (NICU) - Apgar Score",
    "Neonatal Nursing (NICU) - Kangaroo Care",
    "Neonatal Nursing (NICU) - Phototherapy for Jaundice",
    "Neonatal Nursing (NICU) - Thermoregulation",
    "Neonatal Nursing (NICU) - Feeding & Breastfeeding",
    "Neonatal Nursing (NICU) - Neonatal Sepsis",
    "Intensive Care - Mechanical Ventilation Basics",
    "Intensive Care - Hemodynamic Monitoring",
    "Intensive Care - Shock Types & Management",
    "Intensive Care - Sepsis Bundle (Hour-1)",
    "Intensive Care - Vasopressors & Inotropes",
    "Intensive Care - Acid-Base Balance",
    "Intensive Care - ABG Interpretation",
    "Cardiac - 12-Lead ECG Basics",
    "Cardiac - Arrhythmias Recognition",
    "Cardiac - Acute Coronary Syndrome",
    "Cardiac - CPR & ACLS Algorithms",
    "Emergency - Triage Systems (ESI)",
    "Emergency - Trauma Assessment (ABCDE)",
    "Emergency - Anaphylaxis Management",
    "Emergency - Stroke Recognition (FAST)",
    "Pediatric - Growth & Development Milestones",
    "Pediatric - Vital Signs by Age",
    "Pediatric - Febrile Seizure",
    "Pediatric - Dehydration Assessment",
    "Surgical - Pre-Op Checklist",
    "Surgical - Post-Op Complications",
    "Surgical - Wound Care & Healing",
    "Surgical - Drain Management",
    "Infection Control - Hand Hygiene (5 Moments)",
    "Infection Control - PPE Donning & Doffing",
    "Infection Control - CLABSI Prevention",
    "Infection Control - CAUTI Prevention",
    "Infection Control - VAP Prevention",
    "IV Therapy - Peripheral IV Insertion",
    "IV Therapy - IV Flow Rate Calculation",
    "IV Therapy - Infiltration vs Extravasation",
    "Pharmacology - 10 Rights of Medication",
    "Pharmacology - Heparin & INR Monitoring",
    "Pharmacology - Insulin Types & Onset",
    "Pharmacology - Digoxin Toxicity",
    "Patient Safety - SBAR Communication",
    "Patient Safety - Fall Prevention",
    "Patient Safety - Pressure Ulcer Prevention",
    "Patient Safety - Identification (2 identifiers)",
    "Communication - Therapeutic Communication",
    "Communication - ISBAR Handover",
    "Ethics - Patient Confidentiality (HIPAA)",
    "Ethics - Informed Consent",
    "Fluid & Electrolytes - Hyponatremia",
    "Fluid & Electrolytes - Hyperkalemia",
    "Fluid & Electrolytes - IV Fluids (Crystalloids vs Colloids)",
    "Pain - Pain Assessment Scales (NRS, VAS, FLACC)",
    "Pain - Non-pharmacological Management",
    "Vital Signs - Blood Pressure Abnormalities",
    "Vital Signs - Oxygen Saturation & Hypoxia",
]

# ============ الـ Prompt ============
PROMPT_TEMPLATE = """أنت ممرض خبير ومحاضر تمريض مصري. اكتب "Nursing Reminder" عن:

📌 الموضوع: {topic}

⚠️ اكتب بالظبط بالشكل ده (سطر لكل section):

━━━ 🏥 معلومة ━━━
[جملة أو جملتين بالمصري العامي، أسلوب مباشر زي "بص، الموضوع كذا..." أو "خد بالك من..."]

━━━ ❓ ليه مهمة ━━━
[الأهمية السريرية في سطر أو سطرين]

━━━ 🔗 Clinical Connection ━━━
[اربطها بحالة عملية أو إجراء تمريضي في سطر]

━━━ 🧠 طريقة الحفظ ━━━
[Mnemonic أو طريقة سهلة للحفظ]

━━━ 📝 MCQ ━━━
السؤال: [السؤال]
أ) [اختيار 1]
ب) [اختيار 2]
ج) [اختيار 3]
د) [اختيار 4]

━━━ ✅ الإجابة ━━━
الإجابة: [الحرف]
الشرح: [سطر واحد]

━━━ 📚 المصدر ━━━
[WHO / CDC / NANDA / Hockenberry / Kozier & Erb's / Smeltzer - كتاب محدد]

⚠️ قواعد مهمة:
- باللهجة المصرية العامي
- مختصر جداً (سطر أو سطرين لكل section)
- من غير حشو
- ما تخترعش معلومات
- لو مش متأكد، اكتب "غير متأكد من المصدر" في الأخير
"""


# ============ دوال مساعدة ============
def load_history():
    """تحميل المواضيع اللي اتبعتت قبل كده"""
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_history(history):
    """حفظ المواضيع اللي اتبعتت"""
    # نحتفظ بآخر MAX_HISTORY بس
    history = history[-MAX_HISTORY:]
    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def pick_topic():
    """اختيار موضوع لم يتبعت من قبل"""
    history = load_history()
    available = [t for t in NURSING_TOPICS if t not in history]

    if not available:
        # لو خلصت المواضيع، نعيد التاريخ
        log.info("All topics used. Resetting history.")
        save_history([])
        available = NURSING_TOPICS

    chosen = random.choice(available)
    history.append(chosen)
    save_history(history)
    return chosen


# ============ OpenRouter API ============
def get_nursing_reminder():
    """يجيب Nursing Reminder من OpenRouter"""
    if not OPENROUTER_API_KEY:
        return "❌ OPENROUTER_API_KEY is missing!"

    topic = pick_topic()
    log.info(f"📌 Topic: {topic}")

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/mohamedmahdy526-ux/nursing-reminder-bot",
                "X-Title": "Nursing Reminder Bot",
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "أنت ممرض خبير ومحاضر تمريض. تجاوب باللهجة المصرية العامية. مختصر ومباشر. ما تخترعش معلومات. لو مش متأكد، اكتب 'غير متأكد من المصدر'.",
                    },
                    {
                        "role": "user",
                        "content": PROMPT_TEMPLATE.format(topic=topic),
                    },
                ],
                "max_tokens": 1000,
                "temperature": 0.8,
            },
            timeout=90,
        )

        if response.status_code != 200:
            error_msg = response.json().get("error", {}).get("message", "Unknown error")
            log.error(f"OpenRouter error: {error_msg}")
            return f"⚠️ OpenRouter Error: {error_msg}"

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return content

    except requests.exceptions.Timeout:
        return "⚠️ Timeout: OpenRouter took too long."
    except Exception as e:
        log.exception("Error in get_nursing_reminder")
        return f"⚠️ Error: {e}"


# ============ Telegram ============
def send_telegram(message):
    """يبعت رسالة على تليجرام (Plain Text)"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.error("Telegram credentials missing!")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Plain text (بدون parse_mode) لتجنب مشاكل HTML
    if len(message) <= 4096:
        try:
            r = requests.post(
                url,
                data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
                timeout=30,
            )
            if r.status_code == 200:
                return True
            log.error(f"Telegram error: {r.text}")
            return False
        except Exception as e:
            log.exception("Telegram send failed")
            return False
    else:
        # نقسّم على أجزاء
        parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
        for part in parts:
            try:
                requests.post(
                    url,
                    data={"chat_id": TELEGRAM_CHAT_ID, "text": part},
                    timeout=30,
                )
            except Exception as e:
                log.exception("Telegram part send failed")
                return False
        return True


# ============ الأوامر ============
def cmd_start():
    return (
        "👋 أهلاً يا محمد!\n\n"
        "أنا بوت الـ Nursing Reminder 🏥\n\n"
        "📋 الأوامر المتاحة:\n"
        "/now - ابعت Reminder دلوقتي (للتجربة)\n"
        "/status - حالة البوت\n"
        "/topics - المواضيع المتاحة\n"
        "/help - المساعدة\n\n"
        "⏰ هيوصلك Reminder كل ساعة من 08:00 لـ 22:00 بتوقيت القاهرة."
    )


def cmd_status():
    history = load_history()
    cairo_now = datetime.now(CAIRO_TZ)
    next_hour = cairo_now.hour + 1
    return (
        f"📊 حالة البوت:\n\n"
        f"🕐 الوقت الحالي (القاهرة): {cairo_now.strftime('%H:%M')}\n"
        f"🧠 الموديل: {OPENROUTER_MODEL}\n"
        f"📚 مواضيع اتبعتت: {len(history)}/{len(NURSING_TOPICS)}\n"
        f"⏰ الساعات النشطة: 08:00 - 22:00 بتوقيت القاهرة\n"
        f"⏭️ الـ Reminder الجاي: {'الساعة ' + str(next_hour) if next_hour in ACTIVE_HOURS else 'بكرة الصبح 08:00'}"
    )


def cmd_topics():
    return (
        f"📚 المواضيع المتاحة ({len(NURSING_TOPICS)} موضوع):\n\n"
        + "\n".join(f"• {t}" for t in NURSING_TOPICS[:15])
        + f"\n\n... و{len(NURSING_TOPICS) - 15} موضوع آخر."
    )


def cmd_now():
    """إرسال Reminder فوراً"""
    log.info("⚡ Manual /now triggered")
    reminder = get_nursing_reminder()
    success = send_telegram(reminder)
    if success:
        return None  # خلاص اتبعت، مفيش رسالة ترد
    return "❌ فشل إرسال Reminder. شوف الـ logs."


# ============ Telegram Polling ============
last_update_id = 0


def handle_telegram_commands():
    """يستقبل أوامر من تليجرام"""
    global last_update_id

    if not TELEGRAM_BOT_TOKEN:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(
            url,
            params={"offset": last_update_id + 1, "timeout": 5},
            timeout=15,
        )
        updates = r.json().get("result", [])

        for update in updates:
            last_update_id = update["update_id"]
            msg = update.get("message", {})
            chat_id = str(msg.get("chat", {}).get("id", ""))
            text = (msg.get("text") or "").strip()

            # نتأكد إن الرسالة من المستخدم الصحيح
            if chat_id != TELEGRAM_CHAT_ID:
                log.warning(f"Unauthorized chat_id: {chat_id}")
                continue

            log.info(f"📩 Command: {text}")

            if text == "/start":
                reply = cmd_start()
            elif text == "/status":
                reply = cmd_status()
            elif text == "/topics":
                reply = cmd_topics()
            elif text == "/now":
                cmd_now()
                continue  # مفيش رد
            elif text == "/help":
                reply = cmd_start()
            else:
                continue  # مش أمر، نتجاهله

            send_telegram(reply)

    except Exception as e:
        log.exception("Error in handle_telegram_commands")


# ============ Main Loop ============
def get_next_active_time():
    """الوقت اللي هيتبعت فيه الـ Reminder الجاي (Africa/Cairo)"""
    now = datetime.now(CAIRO_TZ)
    current_hour = now.hour
    current_minute = now.minute
    current_second = now.second

    # نشوف أقرب ساعة نشطة جاية
    for hour in ACTIVE_HOURS:
        if hour > current_hour or (hour == current_hour and current_minute == 0 and current_second == 0):
            target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if target > now:
                return target

    # لو مفيش ساعة جاية النهارده، نروح لبكرة الصبح 08:00
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=ACTIVE_HOURS[0], minute=0, second=0, microsecond=0)


if __name__ == "__main__":
    print("=" * 50)
    print("🏥 Nursing Reminder Bot Started")
    print(f"📅 {datetime.now(CAIRO_TZ).strftime('%Y-%m-%d %H:%M:%S')} (Cairo)")
    print(f"🧠 Model: {OPENROUTER_MODEL}")
    print("=" * 50)

    # فحص الـ credentials
    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, OPENROUTER_API_KEY]):
        log.error("❌ Missing credentials!")
        log.error(f"  TELEGRAM_BOT_TOKEN: {'✓' if TELEGRAM_BOT_TOKEN else '✗'}")
        log.error(f"  TELEGRAM_CHAT_ID: {'✓' if TELEGRAM_CHAT_ID else '✗'}")
        log.error(f"  OPENROUTER_API_KEY: {'✓' if OPENROUTER_API_KEY else '✗'}")
        exit(1)

    log.info("⏰ Active hours: 08:00 - 22:00 (Africa/Cairo)")
    log.info("📋 Commands: /start /now /status /topics /help")
    log.info("💡 No auto-message on startup. Waiting for next scheduled hour.")

    sent_today = set()

    while True:
        try:
            cairo_now = datetime.now(CAIRO_TZ)
            current_hour = cairo_now.hour
            current_date = cairo_now.date()

            # Reset يومي
            if sent_today and cairo_now.hour == 0 and cairo_now.minute < 2:
                sent_today.clear()

            # ابعت Reminder لو الساعة في ACTIVE_HOURS ومتبعتش النهارده
            if current_hour in ACTIVE_HOURS and current_hour not in sent_today:
                # ابعت أول دقيقة من كل ساعة نشطة
                if cairo_now.minute == 0:
                    log.info(f"⏰ Hour {current_hour:02d}:00 - Sending reminder...")
                    reminder = get_nursing_reminder()
                    if send_telegram(reminder):
                        sent_today.add(current_hour)
                        log.info(f"✅ Sent for hour {current_hour:02d}")
                    else:
                        log.error(f"❌ Failed for hour {current_hour:02d}")

            # نستقبل الأوامر كل 10 ثواني
            handle_telegram_commands()

            # نستنى 10 ثواني
            time.sleep(10)

        except KeyboardInterrupt:
            log.info("👋 Bot stopped by user")
            break
        except Exception as e:
            log.exception("Error in main loop")
            time.sleep(60)
