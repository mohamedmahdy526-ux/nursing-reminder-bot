"""
🏥 Nursing Reminder Bot
- Job mode: يشتغل مرة واحدة كل ساعة (08:00 - 22:00 Cairo) عبر GitHub Actions
- Functions: توليد Reminder، منع التكرار (GitHub API)، إرسال Telegram
- أوامر يدوية: /now /status /topics /help (عبر GitHub Actions workflow_dispatch)
"""

import os
import sys
import json
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

# ============ Persistence ============
# بنستخدم GitHub Contents API كـ persistent storage (عشان مفيش local state في GitHub Actions)
# fallback للملف المحلي في حالة GSM Host
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip()
HISTORY_FILE = "sent_topics.json"
MAX_HISTORY = 50


def _gh_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "nursing-reminder-bot",
    }


def load_history():
    """تحميل المواضيع اللي اتبعتت قبل كده"""
    # GitHub API mode (للـ GitHub Actions)
    if GITHUB_TOKEN and GITHUB_REPO:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{HISTORY_FILE}"
            r = requests.get(url, headers=_gh_headers(), timeout=15)
            if r.status_code == 200:
                content_b64 = r.json().get("content", "")
                decoded = base64.b64decode(content_b64).decode("utf-8")
                history = json.loads(decoded)
                log.info(f"📥 Loaded {len(history)} topics from GitHub")
                return history
            elif r.status_code == 404:
                log.info("📥 No history file yet (first run)")
                return []
            else:
                log.warning(f"GitHub API error: {r.status_code}")
                return []
        except Exception as e:
            log.exception("load_history (GitHub) failed")
            return []

    # Fallback: ملف محلي (للـ GSM Host)
    local = Path(HISTORY_FILE)
    if local.exists():
        try:
            history = json.loads(local.read_text(encoding="utf-8"))
            log.info(f"📥 Loaded {len(history)} topics from local file")
            return history
        except Exception:
            return []
    return []


def save_history(history):
    """حفظ المواضيع"""
    history = history[-MAX_HISTORY:]
    content = json.dumps(history, ensure_ascii=False, indent=2)

    # GitHub API mode
    if GITHUB_TOKEN and GITHUB_REPO:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{HISTORY_FILE}"

            # Get current SHA (required for update)
            r = requests.get(url, headers=_gh_headers(), timeout=15)
            sha = r.json().get("sha") if r.status_code == 200 else None

            payload = {
                "message": "🤖 Update sent topics history",
                "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            }
            if sha:
                payload["sha"] = sha

            r = requests.put(url, headers=_gh_headers(), json=payload, timeout=15)
            if r.status_code in (200, 201):
                log.info(f"💾 History saved to GitHub ({len(history)} topics)")
            else:
                log.error(f"Save failed: {r.status_code} {r.text[:200]}")
        except Exception as e:
            log.exception("save_history (GitHub) failed")
        return

    # Fallback: ملف محلي
    try:
        Path(HISTORY_FILE).write_text(content, encoding="utf-8")
        log.info(f"💾 History saved locally ({len(history)} topics)")
    except Exception as e:
        log.exception("save_history (local) failed")


def pick_topic():
    """اختيار موضوع لم يتبعت من قبل"""
    history = load_history()
    available = [t for t in NURSING_TOPICS if t not in history]

    if not available:
        log.info("🔄 All topics used. Resetting history.")
        save_history([])
        available = NURSING_TOPICS

    chosen = random.choice(available)
    history.append(chosen)
    save_history(history)
    return chosen


# ============ المواضيع ============
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
    "Patient Safety - Patient Identification",
    "Communication - Therapeutic Communication",
    "Communication - ISBAR Handover",
    "Ethics - Patient Confidentiality",
    "Ethics - Informed Consent",
    "Fluid & Electrolytes - Hyponatremia",
    "Fluid & Electrolytes - Hyperkalemia",
    "Fluid & Electrolytes - IV Fluids Types",
    "Pain - Pain Assessment Scales (NRS, VAS, FLACC)",
    "Pain - Non-pharmacological Management",
    "Vital Signs - Blood Pressure Abnormalities",
    "Vital Signs - Oxygen Saturation & Hypoxia",
    "Ventilator - Modes (AC, SIMV, PSV)",
    "Ventilator - Weaning Criteria",
    "ECG - ST Elevation & MI Recognition",
    "ECG - Atrial Fibrillation",
    "ECG - Ventricular Tachycardia",
    "Diabetes - DKA Management",
    "Diabetes - Hypoglycemia Treatment",
    "Stroke - Ischemic vs Hemorrhagic",
    "Stroke - Thrombolytic Therapy",
    "Wound - Pressure Injury Stages",
    "Wound - Surgical Site Infection",
    "Blood - Transfusion Reactions",
    "Blood - Type & Crossmatch",
    "Respiratory - Pneumonia Nursing Care",
    "Respiratory - Asthma Exacerbation",
    "Respiratory - COPD Management",
    "Renal - Acute Kidney Injury",
    "Renal - Dialysis Basics",
    "Oncology - Chemotherapy Side Effects",
    "Oncology - Neutropenic Precautions",
    "Maternal - Postpartum Hemorrhage",
    "Maternal - Preeclampsia",
    "Maternal - Labor Stages",
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

━━━ 🗳️ POLL DATA ━━━
POLL_QUESTION: [نفس سؤال الـ MCQ]
POLL_OPTION_A: [الاختيار أ]
POLL_OPTION_B: [الاختيار ب]
POLL_OPTION_C: [الاختيار ج]
POLL_OPTION_D: [الاختيار د]
POLL_CORRECT: [الحرف الصح: A أو B أو C أو D]

━━━ 📚 المصدر ━━━
[WHO / CDC / NANDA / Hockenberry / Kozier & Erb's / Smeltzer - كتاب محدد]

⚠️ قواعد مهمة:
- باللهجة المصرية العامي
- مختصر جداً (سطر أو سطرين لكل section)
- من غير حشو
- ما تخترعش معلومات
- لو مش متأكد، اكتب "غير متأكد من المصدر" في الأخير
"""


# ============ OpenRouter API ============
def get_nursing_reminder():
    """يجيب Nursing Reminder من OpenRouter"""
    if not OPENROUTER_API_KEY:
        log.error("OPENROUTER_API_KEY is missing!")
        return None

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

    if message is None:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

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


def parse_poll_data(text):
    """يستخرج بيانات الـ Poll من النص"""
    poll_data = {
        "question": None,
        "options": [],
        "correct": None,
    }

    try:
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("POLL_QUESTION:"):
                poll_data["question"] = line.replace("POLL_QUESTION:", "").strip()
            elif line.startswith("POLL_OPTION_A:"):
                poll_data["options"].append(line.replace("POLL_OPTION_A:", "").strip())
            elif line.startswith("POLL_OPTION_B:"):
                poll_data["options"].append(line.replace("POLL_OPTION_B:", "").strip())
            elif line.startswith("POLL_OPTION_C:"):
                poll_data["options"].append(line.replace("POLL_OPTION_C:", "").strip())
            elif line.startswith("POLL_OPTION_D:"):
                poll_data["options"].append(line.replace("POLL_OPTION_D:", "").strip())
            elif line.startswith("POLL_CORRECT:"):
                poll_data["correct"] = line.replace("POLL_CORRECT:", "").strip().upper()
    except Exception as e:
        log.exception("parse_poll_data failed")

    return poll_data


def strip_poll_section(text):
    """يشيل قسم POLL DATA من النص قبل الإرسال"""
    lines = text.split("\n")
    cleaned = []
    skip = False
    for line in lines:
        if "━━━ 🗳️ POLL DATA ━━━" in line:
            skip = True
            continue
        if skip and line.strip().startswith("POLL_"):
            continue
        if skip and "━━━" in line:
            skip = False
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def send_telegram_poll(poll_data):
    """يبعت Poll على تليجرام"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    if not poll_data["question"] or len(poll_data["options"]) < 2:
        log.warning("Invalid poll data, skipping poll")
        return False

    # Telegram allows max 10 options, each max 100 chars
    options = [opt[:100] for opt in poll_data["options"][:10]]

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPoll"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "question": poll_data["question"][:300],  # Telegram max 300 chars
        "options": options,
        "is_anonymous": True,
    }

    # لو عايز نضيف الإجابة الصح بعد إغلاق الـ poll
    # Telegram polls مفيش فيها "correct answer" API رسمي، بس ممكن نضيف explanation
    if poll_data["correct"]:
        payload["explanation"] = f"✅ الإجابة الصح: {poll_data['correct']}"
        payload["explanation_parse_mode"] = "HTML"

    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 200:
            log.info(f"📊 Poll sent: {poll_data['question'][:50]}")
            return True
        log.error(f"Poll error: {r.status_code} {r.text[:200]}")
        return False
    except Exception as e:
        log.exception("send_telegram_poll failed")
        return False


def send_reminder_with_poll(full_text):
    """يبعت Reminder + Poll"""
    # 1. نستخرج الـ poll data
    poll_data = parse_poll_data(full_text)

    # 2. نشيل قسم POLL من النص
    clean_text = strip_poll_section(full_text)

    # 3. نبعت النص النضيف أولاً
    text_sent = send_telegram(clean_text)

    # 4. نبعت الـ poll (لو فيه)
    poll_sent = False
    if poll_data["question"] and len(poll_data["options"]) >= 2:
        poll_sent = send_telegram_poll(poll_data)

    return text_sent and poll_sent


# ============ أوامر ============
def cmd_status():
    """حالة البوت"""
    history = load_history()
    cairo_now = datetime.now(CAIRO_TZ)
    return (
        f"📊 حالة البوت:\n\n"
        f"🕐 الوقت الحالي (القاهرة): {cairo_now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🧠 الموديل: {OPENROUTER_MODEL}\n"
        f"📚 مواضيع اتبعتت: {len(history)}/{len(NURSING_TOPICS)}\n"
        f"⏰ الساعات النشطة: 08:00 - 22:00 بتوقيت القاهرة"
    )


def cmd_topics():
    """قائمة المواضيع"""
    return (
        f"📚 المواضيع المتاحة ({len(NURSING_TOPICS)} موضوع):\n\n"
        + "\n".join(f"• {t}" for t in NURSING_TOPICS[:15])
        + f"\n\n... و{len(NURSING_TOPICS) - 15} موضوع آخر."
    )


def cmd_help():
    """المساعدة"""
    return (
        "🏥 Nursing Reminder Bot\n\n"
        "📋 الأوامر المتاحة:\n"
        "/now - ابعت Reminder دلوقتي\n"
        "/status - حالة البوت\n"
        "/topics - المواضيع المتاحة\n"
        "/help - المساعدة\n\n"
        "⏰ هيوصلك Reminder كل ساعة من 08:00 لـ 22:00 بتوقيت القاهرة."
    )


# ============ Entry Point ============
def main():
    """الدالة الرئيسية - بتشتغل مرة واحدة لكل Job"""
    log.info("=" * 50)
    log.info(f"🏥 Nursing Reminder Bot - Job started at {datetime.now(CAIRO_TZ).strftime('%Y-%m-%d %H:%M:%S')} Cairo")
    log.info("=" * 50)

    # فحص الـ credentials
    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, OPENROUTER_API_KEY]):
        log.error("❌ Missing credentials!")
        log.error(f"  TELEGRAM_BOT_TOKEN: {'✓' if TELEGRAM_BOT_TOKEN else '✗'}")
        log.error(f"  TELEGRAM_CHAT_ID: {'✓' if TELEGRAM_CHAT_ID else '✗'}")
        log.error(f"  OPENROUTER_API_KEY: {'✓' if OPENROUTER_API_KEY else '✗'}")
        sys.exit(1)

    # الأمر المطلوب (من الـ workflow input)
    command = os.getenv("COMMAND", "auto").lower()

    if command == "now":
        log.info("⚡ Manual /now command")
        reminder = get_nursing_reminder()
        if send_reminder_with_poll(reminder):
            log.info("✅ Reminder + Poll sent successfully!")
        else:
            log.error("❌ Failed to send reminder")
            sys.exit(1)

    elif command == "status":
        log.info("📊 /status command")
        send_telegram(cmd_status())

    elif command == "topics":
        log.info("📚 /topics command")
        send_telegram(cmd_topics())

    elif command == "help":
        log.info("❓ /help command")
        send_telegram(cmd_help())

    else:  # auto (الجدولة العادية)
        log.info("⏰ Scheduled reminder")
        reminder = get_nursing_reminder()
        if send_reminder_with_poll(reminder):
            log.info("✅ Scheduled reminder + Poll sent!")
        else:
            log.error("❌ Failed to send scheduled reminder")
            sys.exit(1)

    log.info("👋 Job completed")


if __name__ == "__main__":
    main()
