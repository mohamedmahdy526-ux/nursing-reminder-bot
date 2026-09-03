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

# ضبط ترميز UTF-8 لدعم الإيموجي والعربية على Windows
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ============ Logging ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("nursing-bot")

# ============ إعدادات ============
# تحميل المتغيرات من ملف .env محلياً إن وجد
env_path = Path(".env")
if env_path.exists():
    for env_line in env_path.read_text(encoding="utf-8").splitlines():
        env_line = env_line.strip()
        if env_line and not env_line.startswith("#") and "=" in env_line:
            k, v = env_line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free").strip()
CAIRO_TZ = ZoneInfo("Africa/Cairo")

# قائمة الموديلات البديلة المجانية لتفادي تعطل أي سيرفر فردي
FALLBACK_MODELS = [
    OPENROUTER_MODEL,
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "minimax/minimax-m3:free",
    "z-ai/glm-5.2:free",
]
MODELS_TO_TRY = list(dict.fromkeys([m for m in FALLBACK_MODELS if m]))

# ============ Persistence ============
# بنستخدم GitHub Contents API كـ persistent storage (عشان مفيش local state في GitHub Actions)
# fallback للملف المحلي في حالة GSM Host
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip()
HISTORY_FILE = "sent_topics.json"
MAX_HISTORY = 100


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
[3-4 أسطر بالمصري العامي، أسلوب مباشر زي "بص، الموضوع كذا..." أو "خد بالك من...". فسّر الموضوع بشكل كافي عشان القارئ يفهمه بدون ما يدور على مصدر خارجي]

━━━ ❓ ليه مهمة ━━━
[الأهمية السريرية في 2-3 أسطر. ليه الـ nurse لازم يعرف ده؟ إيه العواقب لو ما اتعملش؟]

━━━ 🔗 Clinical Connection ━━━
[2-3 أسطر. اربطها بحالة عملية واقعية أو إجراء تمريضي محدد (الخطوات بالأرقام)]

━━━ 🧠 طريقة الحفظ ━━━
[Mnemonic أو طريقة سهلة للحفظ بالأحرف الأولى]

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
    """يجيب Nursing Reminder من OpenRouter مع دعم التبديل التلقائي (Fallback) بين الموديلات"""
    if not OPENROUTER_API_KEY:
        log.error("OPENROUTER_API_KEY is missing!")
        return None

    topic = pick_topic()
    log.info(f"📌 Topic: {topic}")

    messages = [
        {
            "role": "system",
            "content": "أنت ممرض خبير ومحاضر تمريض. تجاوب باللهجة المصرية العامية. مختصر ومباشر. ما تخترعش معلومات. لو مش متأكد، اكتب 'غير متأكد من المصدر'.",
        },
        {
            "role": "user",
            "content": PROMPT_TEMPLATE.format(topic=topic),
        },
    ]

    last_error = "Unknown error"

    for model in MODELS_TO_TRY:
        try:
            log.info(f"🤖 Trying model: {model}")
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/mohamedmahdy526-ux/nursing-reminder-bot",
                    "X-Title": "Nursing Reminder Bot",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": 1000,
                    "temperature": 0.8,
                },
                timeout=60,
            )

            if response.status_code == 200:
                data = response.json()
                choices = data.get("choices", [])
                if choices and "message" in choices[0] and choices[0]["message"].get("content"):
                    content = choices[0]["message"]["content"]
                    log.info(f"✅ Model {model} succeeded!")
                    return content

            try:
                error_data = response.json().get("error", {})
                last_error = error_data.get("message", response.text[:200])
            except Exception:
                last_error = response.text[:200]

            log.warning(f"⚠️ Model {model} failed ({response.status_code}): {last_error}. Trying next fallback...")

        except requests.exceptions.Timeout:
            last_error = f"Timeout on {model}"
            log.warning(f"⏳ Model {model} timed out. Trying next fallback...")
        except Exception as e:
            last_error = str(e)
            log.warning(f"⚠️ Model {model} error: {e}. Trying next fallback...")

    log.error(f"❌ All fallback models failed. Last error: {last_error}")
    return f"⚠️ تعذر الحصول على تذكير حالياً: {last_error}"


# ============ Telegram ============
def send_telegram(message):
    """يبعت رسالة على تليجرام مع تقسيم آمن ومعالجة HTML fallback"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.error("Telegram credentials missing!")
        return False

    if message is None:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    def _post(chunk, mode):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "disable_web_page_preview": True,
        }
        if mode:
            payload["parse_mode"] = mode
        return requests.post(url, data=payload, timeout=30)

    # تقسيم آمن عند نهايات الأسطر
    chunks = []
    if len(message) <= 3900:
        chunks = [message]
    else:
        current_chunk = []
        current_len = 0
        for line in message.split("\n"):
            line_len = len(line) + 1
            if current_len + line_len > 3700:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_len = line_len
            else:
                current_chunk.append(line)
                current_len += line_len
        if current_chunk:
            chunks.append("\n".join(current_chunk))

    success = True
    for chunk in chunks:
        try:
            r = _post(chunk, "HTML")
            if r.status_code != 200:
                log.warning(f"Telegram HTML send failed ({r.status_code}): {r.text[:120]}. Retrying plain text...")
                r_fallback = _post(chunk, "")
                if r_fallback.status_code != 200:
                    log.error(f"Telegram plain fallback failed: {r_fallback.text[:150]}")
                    success = False
        except Exception as e:
            log.exception("Telegram send failed")
            success = False
    return success


def escape_html(text):
    """يهرب من حروف HTML الخاصة"""
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;"))


def format_for_telegram(text):
    """يحوّل النص لصيغة HTML جميلة لتليجرام

    - يحول العناوين (━━━ xxx ━━━) لـ Bold
    - يحافظ على باقي النص عادي
    - يدعم emojis ✅
    """
    if not text:
        return ""

    lines = text.split("\n")
    formatted = []

    for line in lines:
        line_stripped = line.strip()

        # لو السطر عنوان (فيه ━━━)
        if "━━━" in line_stripped and len(line_stripped) < 100:
            # نشيل الـ ━━━ و نحطه bold
            # مثال: ━━━ 🏥 معلومة ━━━ → <b>🏥 معلومة</b>
            title = line_stripped.replace("━━━", "").strip()
            if title:
                formatted.append(f"<b>{escape_html(title)}</b>")
                formatted.append("")  # سطر فاضي بعد العنوان
            else:
                formatted.append("")
            continue

        formatted.append(escape_html(line))

    result = "\n".join(formatted)

    # نشيل الأسطر الفاضية المتكررة
    while "\n\n\n" in result:
        result = result.replace("\n\n\n", "\n\n")

    return result.strip()


def parse_mcq_from_text(text):
    """يستخرج سؤال MCQ من النص العادي"""
    mcq = {
        "question": None,
        "options": [],  # list of tuples (letter, text)
        "correct_letter": None,
    }

    try:
        in_mcq = False
        in_answer = False

        for line in text.split("\n"):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # تحديد قسم MCQ
            if "━━━ 📝 MCQ ━━━" in line_stripped or "━━ 📝 MCQ ━━━" in line_stripped:
                in_mcq = True
                in_answer = False
                continue

            # نهاية قسم MCQ
            if in_mcq and ("━━━" in line_stripped and "MCQ" not in line_stripped):
                in_mcq = False

            # استخراج السؤال
            if in_mcq and line_stripped.startswith("السؤال:"):
                mcq["question"] = line_stripped.replace("السؤال:", "").strip()
                continue

            # استخراج الاختيارات
            if in_mcq:
                clean_line = line_stripped.lstrip("([{-")
                if len(clean_line) >= 2:
                    first_char = clean_line[0]
                    second_char = clean_line[1]
                    letter_map = {
                        "أ": "A", "ا": "A", "إ": "A", "آ": "A",
                        "ب": "B",
                        "ج": "C",
                        "د": "D",
                        "A": "A", "B": "B", "C": "C", "D": "D",
                    }
                    if first_char in letter_map and second_char in ")].- :":
                        letter = letter_map[first_char]
                        option_text = clean_line[2:].strip().lstrip(")-. :")
                        mcq["options"].append((letter, option_text))
                        continue

            # استخراج الإجابة
            if line_stripped.startswith("الإجابة:"):
                answer_text = line_stripped.replace("الإجابة:", "").strip().upper()
                letter_map = {
                    "أ": "A", "ا": "A", "إ": "A", "آ": "A",
                    "ب": "B",
                    "ج": "C",
                    "د": "D",
                    "A": "A", "B": "B", "C": "C", "D": "D",
                }
                for ch in answer_text:
                    if ch in letter_map:
                        mcq["correct_letter"] = letter_map[ch]
                        break
                continue

    except Exception as e:
        log.exception("parse_mcq_from_text failed")

    return mcq


def strip_mcq_section(text):
    """يشيل قسم MCQ و الإجابة من النص (عشان نبعتهم منفصلين)"""
    lines = text.split("\n")
    cleaned = []
    skip = False
    in_answer = False

    for line in lines:
        line_stripped = line.strip()

        # ابدأ التخطي من MCQ
        if "━━━ 📝 MCQ ━━━" in line_stripped or "━━ 📝 MCQ ━━━" in line_stripped:
            skip = True
            continue

        # لو داخل skip، تخطي كل حاجة
        if skip:
            # لكن ممكن نرجع لو دخلنا في section تاني (المصدر)
            if "━━━ 📚 المصدر ━━━" in line_stripped or "━━ 📚 المصدر ━━━" in line_stripped:
                skip = False
                cleaned.append(line)
            continue

        cleaned.append(line)

    return "\n".join(cleaned).strip()


def send_telegram_quiz(mcq):
    """يبعت Quiz Poll على تليجرام"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    if not mcq["question"] or len(mcq["options"]) < 2:
        log.warning("Invalid MCQ data, skipping quiz")
        return False

    # نحول الاختيارات لـ list of strings
    options = [text[:100] for _, text in mcq["options"][:10]]

    # نحسب index الإجابة الصح
    correct_option_id = None
    if mcq["correct_letter"]:
        for idx, (letter, _) in enumerate(mcq["options"]):
            if letter == mcq["correct_letter"]:
                correct_option_id = idx
                break

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPoll"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "question": f"📝 {mcq['question']}"[:300],
        "options": options,
        "is_anonymous": True,
    }

    # لو فيه إجابة صح → quiz mode (Telegram يقولك صح/غلط)
    # لو مفيش → poll mode (مجرد سؤال)
    if correct_option_id is not None:
        payload["type"] = "quiz"
        payload["correct_option_id"] = correct_option_id
    else:
        payload["type"] = "regular"
        log.warning("No correct answer found, sending as regular poll")

    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 200:
            poll_type = payload["type"]
            log.info(f"📊 {poll_type.title()} sent: {mcq['question'][:50]}")
            return True
        log.error(f"Quiz error: {r.status_code} {r.text[:200]}")
        return False
    except Exception as e:
        log.exception("send_telegram_quiz failed")
        return False


def send_reminder_with_quiz(full_text):
    """يبعت Reminder + Quiz Poll"""
    # 1. نستخرج الـ MCQ (قبل التنسيق عشان parser يشتغل على النص الأصلي)
    mcq = parse_mcq_from_text(full_text)

    # 2. نشيل قسم MCQ من النص
    clean_text = strip_mcq_section(full_text)

    # 3. نحول النص لـ HTML (Bold للعناوين + emojis)
    formatted_text = format_for_telegram(clean_text)

    # 4. نبعت النص (بدون MCQ) أولاً
    text_sent = send_telegram(formatted_text)

    # 5. نبعت الـ Quiz (لو فيه)
    quiz_sent = False
    if mcq["question"] and len(mcq["options"]) >= 2:
        quiz_sent = send_telegram_quiz(mcq)

    if not text_sent:
        return False
    return True  # مفيش مشكلة لو الـ quiz متبعتش


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
        if send_reminder_with_quiz(reminder):
            log.info("✅ Reminder + Quiz sent successfully!")
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
        if send_reminder_with_quiz(reminder):
            log.info("✅ Scheduled reminder + Quiz sent!")
        else:
            log.error("❌ Failed to send scheduled reminder")
            sys.exit(1)

    log.info("👋 Job completed")


if __name__ == "__main__":
    main()
