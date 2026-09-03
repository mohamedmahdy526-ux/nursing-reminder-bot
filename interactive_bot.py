"""
🏥 Nursing Interactive Bot
- Server mode: يستقبل أوامر من تليجرام 24/7
- بيشتغل على GSM Host أو أي VPS
- الأوامر: /ثقف (اختار قسم) → معلومة / MCQ / Quiz
"""

import os
import json
import time
import random
import logging
import base64
from pathlib import Path
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# ============ Logging ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("nursing-bot")

# ============ إعدادات ============
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m3:free").strip()
CAIRO_TZ = ZoneInfo("Africa/Cairo")

# ============ Persistence (Local - GSM Host) ============
STATE_DIR = Path("state")
STATE_DIR.mkdir(exist_ok=True)
STATE_FILE = STATE_DIR / "user_state.json"
HISTORY_FILE = STATE_DIR / "topic_history.json"

# ============ الأقسام ============
DEPARTMENTS = {
    "1": {
        "name": "Neonatal Nursing (NICU)",
        "topics": [
            "Respiratory Distress Syndrome",
            "Apgar Score",
            "Kangaroo Care",
            "Phototherapy for Jaundice",
            "Thermoregulation",
            "Feeding & Breastfeeding",
            "Neonatal Sepsis",
            "Neonatal Resuscitation",
            "Umbilical Catheter Care",
            "Pain Assessment in Neonates",
        ]
    },
    "2": {
        "name": "Intensive Care (ICU)",
        "topics": [
            "Mechanical Ventilation Basics",
            "Hemodynamic Monitoring",
            "Shock Types & Management",
            "Sepsis Bundle (Hour-1)",
            "Vasopressors & Inotropes",
            "Acid-Base Balance",
            "ABG Interpretation",
            "Ventilator Modes (AC, SIMV, PSV)",
            "Weaning Criteria",
            "Delirium in ICU",
        ]
    },
    "3": {
        "name": "Pediatric Nursing",
        "topics": [
            "Growth & Development Milestones",
            "Vital Signs by Age",
            "Febrile Seizure",
            "Dehydration Assessment",
            "Pediatric Pain Management",
            "Vaccination Schedule",
            "Common Childhood Diseases",
            "Pediatric Respiratory Distress",
        ]
    },
    "4": {
        "name": "Pharmacology for Nurses",
        "topics": [
            "10 Rights of Medication",
            "Heparin & INR Monitoring",
            "Insulin Types & Onset",
            "Digoxin Toxicity",
            "Antibiotic Classes",
            "Pain Medication Ladder",
            "Drug Interactions",
            "IV Medication Administration",
        ]
    },
    "5": {
        "name": "Medical Terminology",
        "topics": [
            "Cardiology Terms",
            "Respiratory Terms",
            "Renal Terms",
            "Endocrine Terms",
            "Oncology Terms",
            "Surgical Terms",
            "Anatomy Prefixes & Suffixes",
            "Common Abbreviations in Medicine",
        ]
    },
    "6": {
        "name": "Patient Safety & ISBAR",
        "topics": [
            "ISBAR Communication",
            "SBAR Communication",
            "Hand Hygiene (5 Moments)",
            "PPE Donning & Doffing",
            "Fall Prevention",
            "Pressure Ulcer Prevention",
            "Patient Identification (2 identifiers)",
            "Medication Safety",
            "Handoff Communication",
        ]
    },
    "7": {
        "name": "ECG & Cardiac",
        "topics": [
            "12-Lead ECG Basics",
            "Arrhythmias Recognition",
            "Acute Coronary Syndrome",
            "CPR & ACLS Algorithms",
            "ST Elevation & MI Recognition",
            "Atrial Fibrillation",
            "Ventricular Tachycardia",
            "Heart Failure Management",
        ]
    },
    "8": {
        "name": "Emergency & Trauma",
        "topics": [
            "Triage Systems (ESI)",
            "Trauma Assessment (ABCDE)",
            "Anaphylaxis Management",
            "Stroke Recognition (FAST)",
            "DKA Management",
            "Hypoglycemia Treatment",
            "Status Epilepticus",
            "Poisoning & Overdose",
        ]
    },
}

# ============ الـ Prompt ============
PROMPT_TEMPLATE = """أنت ممرض خبير ومحاضر تمريض مصري.

اكتب "ثقف نفسك" عن:

📌 الموضوع: {topic}
📂 القسم: {department}

⚠️ اكتب بالظبط بالشكل ده:

━━━ 🏥 معلومة ━━━
[3-4 أسطر بالمصري العامي. أسلوب مباشر زي "بص، الموضوع كذا..." أو "خد بالك من...". فسّر الموضوع بشكل كافي]

━━━ ❓ ليه مهمة ━━━
[الأهمية السريرية في 2-3 أسطر]

━━━ 🔗 Clinical Connection ━━━
[2-3 أسطر. مثال عملي واقعي]

━━━ 🧠 طريقة الحفظ ━━━
[Mnemonic أو طريقة سهلة للحفظ]

━━━ 📚 المصدر ━━━
[WHO / CDC / NANDA / Hockenberry / Kozier & Erb's / Smeltzer - كتاب محدد]

⚠️ قواعد:
- باللهجة المصرية العامي
- 3-4 أسطر لكل section (مفصّل شوية)
- من غير حشو
- ما تخترعش معلومات
- لو مش متأكد، اكتب "غير متأكد من المصدر"
"""


# ============ State Management ============
def load_state():
    """تحميل حالة المستخدم (القسم المختار)"""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state):
    """حفظ حالة المستخدم"""
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_history():
    """تحميل المواضيع اللي اتبعتت"""
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_history(history):
    """حفظ المواضيع"""
    HISTORY_FILE.write_text(
        json.dumps(history[-100:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def pick_topic(department_key):
    """اختيار موضوع من القسم لم يتبعت من قبل"""
    department = DEPARTMENTS.get(department_key)
    if not department:
        return None, None

    history = load_history()
    available = [t for t in department["topics"] if t not in history]

    if not available:
        # لو خلصت، نعيد
        log.info(f"All topics used in {department['name']}. Resetting.")
        save_history([])
        available = department["topics"]

    chosen = random.choice(available)
    history.append(chosen)
    save_history(history)
    return chosen, department["name"]


# ============ OpenRouter API ============
def get_content(topic, department):
    """يجيب المحتوى من OpenRouter"""
    if not OPENROUTER_API_KEY:
        return "❌ OPENROUTER_API_KEY is missing!"

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/mohamedmahdy526-ux/nursing-reminder-bot",
                "X-Title": "Nursing Thakka Bot",
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "أنت ممرض خبير ومحاضر تمريض. تجاوب باللهجة المصرية العامية. مفصّل ومباشر. ما تخترعش معلومات. لو مش متأكد، اكتب 'غير متأكد من المصدر'.",
                    },
                    {
                        "role": "user",
                        "content": PROMPT_TEMPLATE.format(
                            topic=topic, department=department
                        ),
                    },
                ],
                "max_tokens": 1500,
                "temperature": 0.8,
            },
            timeout=90,
        )

        if response.status_code != 200:
            error_msg = response.json().get("error", {}).get("message", "Unknown error")
            return f"⚠️ OpenRouter Error: {error_msg}"

        data = response.json()
        return data["choices"][0]["message"]["content"]

    except requests.exceptions.Timeout:
        return "⚠️ Timeout: OpenRouter took too long."
    except Exception as e:
        log.exception("Error in get_content")
        return f"⚠️ Error: {e}"


# ============ Helpers ============
def escape_html(text):
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;"))


def format_for_telegram(text):
    """يحوّل النص لـ HTML (Bold للعناوين)"""
    if not text:
        return ""

    lines = text.split("\n")
    formatted = []
    for line in lines:
        line_stripped = line.strip()
        if "━━━" in line_stripped and len(line_stripped) < 100:
            title = line_stripped.replace("━━━", "").strip()
            if title:
                formatted.append(f"<b>{escape_html(title)}</b>")
                formatted.append("")
            else:
                formatted.append("")
            continue
        formatted.append(escape_html(line))

    result = "\n".join(formatted)
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")
    return result.strip()


def send_telegram(chat_id, text, parse_mode="HTML"):
    """يبعت رسالة على تليجرام"""
    if not TELEGRAM_BOT_TOKEN:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            data={
                "chat_id": chat_id,
                "text": text[:4000],
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if r.status_code == 200:
            return True
        log.error(f"Telegram error: {r.text[:200]}")
        return False
    except Exception as e:
        log.exception("Telegram send failed")
        return False


# ============ Telegram Commands ============
def cmd_thakka(chat_id):
    """عرض الأقسام"""
    state = load_state()
    user_state = state.get(str(chat_id), {})

    msg = (
        "📚 <b>ثقف نفسك</b>\n\n"
        "اختار القسم اللي عايز تتعلم منه:\n\n"
    )

    for key, dept in DEPARTMENTS.items():
        emoji = "✅" if user_state.get("department") == key else "▫️"
        msg += f"{emoji} <b>{key}</b> - {dept['name']}\n"

    msg += (
        "\n📋 <b>الأوامر:</b>\n"
        "/ثقف - عرض الأقسام\n"
        "/اختار [رقم] - اختيار قسم (مثال: /اختار 1)\n"
        "/معلومة - معلومة من القسم المختار\n"
        "/mcq - سؤال MCQ من القسم المختار\n"
        "/قسم - القسم المختار حالياً\n"
        "/مساعدة - المساعدة\n\n"
        "💡 بعد ما تختار قسم، ابعت /معلومة أو /mcq"
    )
    send_telegram(chat_id, msg)


def cmd_choose(chat_id, dept_key):
    """اختيار قسم"""
    if dept_key not in DEPARTMENTS:
        send_telegram(chat_id, f"❌ القسم غير صحيح. اختار من 1 لـ {len(DEPARTMENTS)}")
        return

    state = load_state()
    state[str(chat_id)] = {"department": dept_key, "chosen_at": datetime.now().isoformat()}
    save_state(state)

    dept = DEPARTMENTS[dept_key]
    send_telegram(
        chat_id,
        f"✅ تمام! اخترت قسم: <b>{dept['name']}</b>\n\n"
        f"دلوقتي ابعت:\n"
        f"/معلومة - عشان تجيب معلومة\n"
        f"/mcq - عشان تجيب سؤال MCQ"
    )


def cmd_fact(chat_id):
    """إرسال معلومة من القسم المختار"""
    state = load_state()
    user_state = state.get(str(chat_id), {})
    dept_key = user_state.get("department")

    if not dept_key:
        send_telegram(chat_id, "❌ لم تختر قسماً بعد. ابعت /ثقف الأول.")
        return

    topic, department = pick_topic(dept_key)
    if not topic:
        send_telegram(chat_id, "❌ خطأ في اختيار الموضوع.")
        return

    send_telegram(chat_id, f"⏳ جاري تجهيز معلومة عن <b>{topic}</b>...")

    content = get_content(topic, department)
    if not content or content.startswith("⚠️"):
        send_telegram(chat_id, content or "❌ فشل جلب المعلومة")
        return

    formatted = format_for_telegram(content)
    send_telegram(chat_id, formatted)


def cmd_mcq(chat_id):
    """إرسال MCQ من القسم المختار"""
    state = load_state()
    user_state = state.get(str(chat_id), {})
    dept_key = user_state.get("department")

    if not dept_key:
        send_telegram(chat_id, "❌ لم تختر قسماً بعد. ابعت /ثقف الأول.")
        return

    department = DEPARTMENTS[dept_key]
    topic = random.choice(department["topics"])

    send_telegram(chat_id, f"⏳ جاري تجهيز سؤال MCQ عن <b>{topic}</b>...")

    # نستخدم prompt خاص بالـ MCQ
    mcq_prompt = f"""أنت ممرض خبير ومحاضر تمريض مصري.

اعمل سؤال MCQ عن: {topic}

━━━ 📝 MCQ ━━━
السؤال: [السؤال]
أ) [اختيار 1]
ب) [اختيار 2]
ج) [اختيار 3]
د) [اختيار 4]

━━━ ✅ الإجابة ━━━
الإجابة: [حرف واحد فقط: أ أو ب أو ج أو د]
الشرح: [سطر واحد]

━━━ 📚 المصدر ━━━
[كتاب أو منظمة محددة]

⚠️ باللهجة المصرية، مختصر، من غير حشو."""

    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "user", "content": mcq_prompt},
                ],
                "max_tokens": 800,
                "temperature": 0.7,
            },
            timeout=60,
        )

        if response.status_code != 200:
            send_telegram(chat_id, f"⚠️ Error: {response.text[:200]}")
            return

        content = response.json()["choices"][0]["message"]["content"]
        formatted = format_for_telegram(content)
        send_telegram(chat_id, formatted)
    except Exception as e:
        send_telegram(chat_id, f"⚠️ Error: {e}")


def cmd_current(chat_id):
    """القسم المختار حالياً"""
    state = load_state()
    user_state = state.get(str(chat_id), {})
    dept_key = user_state.get("department")

    if not dept_key:
        send_telegram(chat_id, "❌ لم تختر قسماً بعد. ابعت /ثقف.")
        return

    dept = DEPARTMENTS[dept_key]
    send_telegram(chat_id, f"📂 القسم المختار حالياً: <b>{dept['name']}</b>")


def cmd_help(chat_id):
    """المساعدة"""
    msg = (
        "🏥 <b>Nursing Interactive Bot</b>\n\n"
        "<b>الأوامر الأساسية:</b>\n"
        "/ثقف - عرض الأقسام المتاحة\n"
        "/اختار [رقم] - اختيار قسم\n"
        "/معلومة - معلومة من القسم المختار\n"
        "/mcq - سؤال MCQ\n"
        "/قسم - القسم المختار حالياً\n"
        "/مساعدة - هذه الرسالة\n\n"
        "<b>مثال:</b>\n"
        "1. ابعت /ثقف\n"
        "2. اختار رقم (مثلاً: 1 لـ NICU)\n"
        "3. ابعت /معلومة أو /mcq\n"
        "4. كل مرة تبعت الأمر، هيجيلك محتوى جديد"
    )
    send_telegram(chat_id, msg)


# ============ Telegram Polling ============
last_update_id = 0


def handle_updates():
    """يستقبل الأوامر من تليجرام"""
    global last_update_id

    if not TELEGRAM_BOT_TOKEN:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(
            url,
            params={"offset": last_update_id + 1, "timeout": 30, "allowed_updates": ["message"]},
            timeout=35,
        )
        updates = r.json().get("result", [])

        for update in updates:
            last_update_id = update["update_id"]
            msg = update.get("message", {})
            chat_id = str(msg.get("chat", {}).get("id", ""))
            text = (msg.get("text") or "").strip()

            if not text:
                continue

            log.info(f"📩 [{chat_id}] {text}")

            # Check authorization
            if TELEGRAM_CHAT_ID and chat_id != TELEGRAM_CHAT_ID:
                log.warning(f"Unauthorized: {chat_id}")
                continue

            # Parse command
            parts = text.split(maxsplit=1)
            command = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if command in ("/ثقف", "/thakka", "/start"):
                cmd_thakka(chat_id)
            elif command in ("/اختار", "/choose"):
                cmd_choose(chat_id, arg.strip())
            elif command in ("/معلومة", "/fact"):
                cmd_fact(chat_id)
            elif command in ("/mcq", "/quiz"):
                cmd_mcq(chat_id)
            elif command in ("/قسم", "/current"):
                cmd_current(chat_id)
            elif command in ("/مساعدة", "/help"):
                cmd_help(chat_id)
            elif command in ("/status",):
                send_telegram(
                    chat_id,
                    f"🟢 البوت شغّال!\n"
                    f"🕐 {datetime.now(CAIRO_TZ).strftime('%H:%M:%S')} Cairo\n"
                    f"🧠 {OPENROUTER_MODEL}"
                )
            else:
                # لو مش أمر، لو فيه قسم مختار، ممكن نبعت معلومة
                state = load_state()
                if state.get(str(chat_id), {}).get("department"):
                    # ممكن نرد بـ "ابعت /معلومة"
                    pass
                else:
                    send_telegram(chat_id, "ابعت /ثقف للبدء 👈")

    except Exception as e:
        log.exception("Error in handle_updates")


# ============ Main ============
if __name__ == "__main__":
    print("=" * 50)
    print("🏥 Nursing Interactive Bot (Server Mode)")
    print(f"📅 {datetime.now(CAIRO_TZ).strftime('%Y-%m-%d %H:%M:%S')} Cairo")
    print("=" * 50)

    if not all([TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY]):
        log.error("❌ Missing credentials!")
        sys.exit(1)

    log.info("👂 Listening for Telegram messages...")
    log.info("📋 Commands: /ثقف /اختار /معلومة /mcq /قسم /مساعدة")

    # تنظيف الـ state file لو موجود من قبل
    if not STATE_FILE.exists():
        save_state({})

    while True:
        try:
            handle_updates()
        except KeyboardInterrupt:
            log.info("👋 Bot stopped")
            break
        except Exception as e:
            log.exception("Error in main loop")
            time.sleep(5)
