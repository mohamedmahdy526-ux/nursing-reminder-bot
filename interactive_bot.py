"""
🏥 Nursing Interactive Bot
- Server mode: يستقبل أوامر من تليجرام 24/7 (GSM Host / VPS / Local)
- الميزات الأساسية:
  1. اختيار تخصصات تمريضية (/ثقف، /اختار)
  2. طلب معلومات سريرية (/معلومة)
  3. كويزات وأسئلة تفاعلية Native Quiz Poll (/mcq)
  4. 💬 النقاش التفاعلي المباشر: يمكنك الرد على أي معلومة أو طرح أي سؤال تمريضي
  5. تذكير دوري تلقائي كل ساعة مع إمكانية النقاش المباشر
"""

import os
import sys
import json
import base64
import time
import random
import logging
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
log = logging.getLogger("nursing-interactive-bot")

# ============ إعدادات ============
# تحميل المتغيرات من ملف .env محلياً إن وجد
env_path = Path(".env")
if env_path.exists():
    for env_line in env_path.read_text(encoding="utf-8").splitlines():
        env_line = env_line.strip()
        if env_line and not env_line.startswith("#") and "=" in env_line:
            k, v = env_line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# قيم افتراضية آمنة في حال التشغيل على منصات الجوال مثل GSM Host
_DEF_TG = base64.b64decode("ODkxODM2NTEzMTpBQUZzSGVDTDlJaW1MM0dCNklKX3FwRll1MGE5R19WZFpGdw==").decode()
_DEF_CHAT = "437169371"
_DEF_OR = base64.b64decode("c2stb3ItdjEtNjIxNTNiZDc1MTg0MDA4NTFmZTk0ZTFjMmU3YzZmMzgxM2Q0NDI5NTFkZDkwMzBjZmI1ZTAxNDRhZmFlNjRlNQ==").decode()
_DEF_GEMINI = base64.b64decode("QVEuQWI4Uk42S0M4UE1LU2Y1WlIxLUNGX2xuc2h2T0FZYmxjSnFjTmFmT0hVV2o5RTBHS1E=").decode()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", _DEF_TG).strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", _DEF_CHAT).strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", _DEF_OR).strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", _DEF_GEMINI).strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m3:free").strip()
CAIRO_TZ = ZoneInfo("Africa/Cairo")

# قائمة الموديلات البديلة المجانية لتفادي تعطل أي سيرفر فردي
FALLBACK_MODELS = [
    OPENROUTER_MODEL,
    "minimax/minimax-m3:free",
    "minimax/minimax-m2.7:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3.5-lightning:free",
    "z-ai/glm-5.2:free",
]
MODELS_TO_TRY = list(dict.fromkeys([m for m in FALLBACK_MODELS if m]))

# ============ Persistence (Local - GSM Host / VPS) ============
STATE_DIR = Path("state")
STATE_DIR.mkdir(exist_ok=True)
STATE_FILE = STATE_DIR / "user_state.json"
HISTORY_FILE = STATE_DIR / "topic_history.json"

# ============ الأقسام والمواضيع ============
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
        ],
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
        ],
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
        ],
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
        ],
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
        ],
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
        ],
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
        ],
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
        ],
    },
}

# ============ الـ Prompts ============
FACT_PROMPT_TEMPLATE = """أنت ممرض خبير ومحاضر تمريض مصري.

اكتب "ثقف نفسك" عن:

📌 الموضوع: {topic}
📂 القسم: {department}

⚠️ اكتب بالظبط بالشكل ده:

━━━ 🏥 معلومة ━━━
[3-4 أسطر بالمصري العامي. أسلوب مباشر زي "بص، الموضوع كذا..." أو "خد بالك من...". فسّر الموضوع بشكل كافي]

━━━ ❓ ليه مهمة ━━━
[الأهمية السريرية في 2-3 أسطر]

━━━ 🔗 Clinical Connection ━━━
[2-3 أسطر. مثال عملي واقعي أو سيناريو سريري من المستشفى]

━━━ 🧠 طريقة الحفظ ━━━
[Mnemonic أو طريقة سهلة للحفظ]

━━━ 📚 المصدر ━━━
[WHO / CDC / NANDA / Hockenberry / Kozier & Erb's / Smeltzer - كتاب محدد]

⚠️ قواعد:
- باللهجة المصرية العامي
- 3-4 أسطر لكل section (مفصّل ومفهوم)
- من غير حشو
- ما تخترعش معلومات
- لو مش متأكد، اكتب "غير متأكد من المصدر"
"""

DISCUSS_SYSTEM_PROMPT = """أنت ممرض خبير ومحاضر تمريض مصري في مستشفى جامعي.
مهمتك: مناقشة وشرح أي معلومة أو سؤال تمريضي أو حالة سريرية مع زميلك الممرض أو طالب التمريض.
قواعد الأسلوب:
- تحدث باللهجة المصرية العامية الودودة والمهنية في نفس الوقت (بأسلوب السينيور الشاطر اللي بيشرح للجونير بتاعه في النبطشية).
- الدقة السريرية والتركيز على أمان المريض (Patient Safety First).
- لو سُئلت عن أدوية أو جرعات، اذكر الـ Nursing Alerts والمحاذير السريرية مع التنبيه بضرورة مراجعة أمر الطبيب (Doctor's Order).
- قسّم إجابتك لنقاط واضحة ومباشرة بدون إطالة مملة أو حشو.
- إذا كان السؤال متعلقاً بمعلومة تم إرسالها سابقاً، اربط إجابتك بها مباشرة ووضّح النقطة التي استفسر عنها المستخدم."""

MCQ_PROMPT_TEMPLATE = """أنت ممرض خبير ومحاضر تمريض مصري.

اعمل سؤال MCQ سريري (اختيار من متعدد) عن:
📌 الموضوع: {topic}

اكتب بالظبط بالشكل التالي:

━━━ 📝 MCQ ━━━
السؤال: [نص السؤال السريري هنا]
أ) [الخيار الأول]
ب) [الخيار الثاني]
ج) [الخيار الثالث]
د) [الخيار الرابع]

━━━ ✅ الإجابة ━━━
الإجابة: [حرف واحد فقط: أ أو ب أو ج أو د]
الشرح: [سطر واحد يشرح سبب صحة الإجابة]

━━━ 📚 المصدر ━━━
[كتاب أو مرجع تمريضي معتمد]

⚠️ شروط هامة:
- باللهجة المصرية المبسطة
- سؤال تطبيقي عملي وليس مجرد حفظ
- من غير حشو"""


# ============ State Management ============
def load_state():
    """تحميل حالة المستخدمين"""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state):
    """حفظ حالة المستخدمين"""
    try:
        STATE_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        log.exception("Failed to save state")


def load_history():
    """تحميل المواضيع التي أُرسلت من قبل"""
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_history(history):
    """حفظ المواضيع"""
    try:
        HISTORY_FILE.write_text(
            json.dumps(history[-150:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        log.exception("Failed to save history")


def pick_topic(department_key):
    """اختيار موضوع لم يسبق إرساله في القسم"""
    department = DEPARTMENTS.get(department_key)
    if not department:
        return None, None

    history = load_history()
    available = [t for t in department["topics"] if t not in history]

    if not available:
        log.info(f"All topics used in {department['name']}. Resetting department history.")
        # مسح مواضيع هذا القسم من التاريخ لتكرار الدورة
        history = [t for t in history if t not in department["topics"]]
        save_history(history)
        available = department["topics"]

    chosen = random.choice(available)
    history.append(chosen)
    save_history(history)
    return chosen, department["name"]


def call_gemini(messages, max_tokens=1200, temperature=0.7):
    """استدعاء Google Gemini API كبديل فائق السرعة ومجاني"""
    if not GEMINI_API_KEY:
        return None, "GEMINI_API_KEY missing"
    try:
        system_instruction = ""
        contents = []
        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if role == "system":
                system_instruction += content + "\n"
            elif role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})

        gemini_models = ["gemini-3.6-flash", "gemini-2.5-flash-lite", "gemini-3.5-flash"]
        for g_model in gemini_models:
            log.info(f"🌟 Trying Gemini model: {g_model}...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": contents,
                "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
            }
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

            r = requests.post(url, json=payload, timeout=40)
            if r.status_code == 200:
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                log.info(f"✅ Gemini model {g_model} succeeded!")
                return text, None
            else:
                log.warning(f"⚠️ Gemini {g_model} returned {r.status_code}: {r.text[:120]}. Trying next Gemini model...")

    except Exception as e:
        log.exception("Gemini API call failed")
        return None, str(e)
    return None, "All Gemini models failed"


def call_openrouter(messages, max_tokens=1200, temperature=0.7, timeout=60):
    """استدعاء موحد لـ OpenRouter API و Gemini مع دعم التبديل التلقائي (Fallback) بين الموديلات"""
    # 1. إذا وجد مفتاح Gemini API نبدأ به فوراً لأنه يعطي 1500 رسالة مجانية يومياً
    if GEMINI_API_KEY:
        content, _ = call_gemini(messages, max_tokens, temperature)
        if content:
            return content, None

    if not OPENROUTER_API_KEY:
        log.error("Both OPENROUTER_API_KEY and GEMINI_API_KEY are missing!")
        return None, "❌ مفتاح API غير موجود!"

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
                    "X-Title": "Nursing Reminder & Discussion Bot",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=timeout,
            )

            if response.status_code == 200:
                data = response.json()
                choices = data.get("choices", [])
                if choices and "message" in choices[0] and choices[0]["message"].get("content"):
                    content = choices[0]["message"]["content"]
                    log.info(f"✅ Model {model} succeeded!")
                    return content, None

            # في حال وجود خطأ من المزود، نقرأ السبب
            try:
                error_data = response.json().get("error", {})
                last_error = error_data.get("message", response.text[:200])
            except Exception:
                last_error = response.text[:200]

            log.warning(f"⚠️ Model {model} failed ({response.status_code}): {last_error}. Trying next fallback...")

            # إذا كان الخطأ تجاوز الحصة اليومية المجانية في OpenRouter (429 Rate Limit)
            if response.status_code == 429 and "free-models-per-day" in last_error:
                if GEMINI_API_KEY:
                    return call_gemini(messages, max_tokens, temperature)
                else:
                    return None, "⚠️ تم استهلاك الحد اليومي المجاني لحساب OpenRouter (50 رسالة/يوم). يتجدد العداد تلقائياً 03:00 فجراً بتوقيت القاهرة، أو يمكنك إضافة GEMINI_API_KEY مجاناً."

        except requests.exceptions.Timeout:
            last_error = f"Timeout on {model}"
            log.warning(f"⏳ Model {model} timed out. Trying next fallback...")
        except Exception as e:
            last_error = str(e)
            log.warning(f"⚠️ Model {model} error: {e}. Trying next fallback...")

    # محاولة أخيرة عبر Gemini إن توفر
    if GEMINI_API_KEY:
        content, _ = call_gemini(messages, max_tokens, temperature)
        if content:
            return content, None

    log.error(f"❌ All fallback models failed. Last error: {last_error}")
    return None, f"⚠️ مزود الذكاء الاصطناعي مشغول حالياً: {last_error}"


def get_content(topic, department):
    """جلب معلومة تمريضية عن الموضوع"""
    messages = [
        {
            "role": "system",
            "content": "أنت ممرض خبير ومحاضر تمريض. تجاوب باللهجة المصرية العامية. مفصّل ومباشر بدون حشو.",
        },
        {
            "role": "user",
            "content": FACT_PROMPT_TEMPLATE.format(topic=topic, department=department),
        },
    ]
    content, err = call_openrouter(messages, max_tokens=1500, temperature=0.8)
    return content or err


# ============ Telegram Messaging Helpers ============
def escape_html(text):
    """تهريب رموز HTML الخاصة"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def format_for_telegram(text):
    """تحويل الفواصل والعناوين إلى HTML Bold منسق"""
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


def send_chat_action(chat_id, action="typing"):
    """إظهار حالة يكتب الآن في تليجرام"""
    if not TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendChatAction"
    try:
        requests.post(url, data={"chat_id": chat_id, "action": action}, timeout=5)
    except Exception:
        pass


def send_telegram(chat_id, text, parse_mode="HTML"):
    """إرسال رسالة تليجرام مع تقسيم آمن ومعالجة أخطاء HTML"""
    if not TELEGRAM_BOT_TOKEN or not text:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    def _post_chunk(chunk, mode):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "disable_web_page_preview": True,
        }
        if mode:
            payload["parse_mode"] = mode
        return requests.post(url, data=payload, timeout=30)

    # تقسيم ذكي لتجنب قطع الأسطر
    chunks = []
    if len(text) <= 3900:
        chunks = [text]
    else:
        current_chunk = []
        current_len = 0
        for line in text.split("\n"):
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
            r = _post_chunk(chunk, parse_mode)
            if r.status_code != 200:
                log.warning(f"Telegram parse_mode={parse_mode} failed ({r.status_code}): {r.text[:120]}. Retrying as plain text...")
                r_fallback = _post_chunk(chunk, "")
                if r_fallback.status_code != 200:
                    log.error(f"Telegram plain fallback failed: {r_fallback.text[:150]}")
                    success = False
        except Exception as e:
            log.exception("Failed to send telegram message chunk")
            success = False

    return success


def parse_mcq_from_text(text):
    """استخراج سؤال MCQ وخياراته وإجابته الصحيحة والشرح"""
    mcq = {
        "question": None,
        "options": [],
        "correct_letter": None,
        "explanation": None,
    }
    if not text:
        return mcq

    try:
        in_mcq = False
        in_answer = False
        letter_map = {
            "أ": "A", "ا": "A", "إ": "A", "آ": "A",
            "ب": "B",
            "ج": "C",
            "د": "D",
            "A": "A", "B": "B", "C": "C", "D": "D",
        }

        for line in text.split("\n"):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            if "MCQ" in line_stripped and "━━" in line_stripped:
                in_mcq = True
                in_answer = False
                continue

            if "الإجابة" in line_stripped and "━━" in line_stripped:
                in_mcq = False
                in_answer = True
                continue

            if in_mcq and ("━━━" in line_stripped or "━━" in line_stripped):
                in_mcq = False

            if in_mcq and line_stripped.startswith("السؤال:"):
                mcq["question"] = line_stripped.replace("السؤال:", "").strip()
                continue

            # استخراج الاختيارات
            if in_mcq:
                clean_line = line_stripped.lstrip("([{-")
                if len(clean_line) >= 2:
                    first_char = clean_line[0]
                    second_char = clean_line[1]
                    if first_char in letter_map and second_char in ")].- :":
                        letter = letter_map[first_char]
                        option_text = clean_line[2:].strip().lstrip(")-. :")
                        mcq["options"].append((letter, option_text))
                        continue

            # استخراج الإجابة والشرح
            if in_answer:
                if line_stripped.startswith("الإجابة:"):
                    ans_text = line_stripped.replace("الإجابة:", "").strip().upper()
                    for ch in ans_text:
                        if ch in letter_map:
                            mcq["correct_letter"] = letter_map[ch]
                            break
                elif line_stripped.startswith("الشرح:"):
                    mcq["explanation"] = line_stripped.replace("الشرح:", "").strip()

    except Exception as e:
        log.exception("parse_mcq_from_text failed")

    return mcq


def send_telegram_quiz(chat_id, mcq):
    """إرسال سؤال MCQ كـ Native Quiz Poll تفاعلي في تليجرام"""
    if not TELEGRAM_BOT_TOKEN:
        return False

    if not mcq.get("question") or len(mcq.get("options", [])) < 2:
        return False

    options = [text[:100] for _, text in mcq["options"][:10]]
    correct_option_id = None
    if mcq.get("correct_letter"):
        for idx, (letter, _) in enumerate(mcq["options"]):
            if letter == mcq["correct_letter"]:
                correct_option_id = idx
                break

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPoll"
    payload = {
        "chat_id": chat_id,
        "question": f"📝 {mcq['question']}"[:300],
        "options": options,
        "is_anonymous": True,
    }

    if correct_option_id is not None:
        payload["type"] = "quiz"
        payload["correct_option_id"] = correct_option_id
        if mcq.get("explanation"):
            payload["explanation"] = mcq["explanation"][:200]
    else:
        payload["type"] = "regular"

    try:
        r = requests.post(url, json=payload, timeout=30)
        return r.status_code == 200
    except Exception as e:
        log.exception("send_telegram_quiz failed")
        return False


# ============ Chat & Discussion Engine ============
def discuss_topic(chat_id, user_message):
    """إدارة النقاش التفاعلي مع المستخدم حول المعلومة الأخيرة أو استفسار تمريضي عام"""
    state = load_state()
    user_info = state.get(str(chat_id), {})
    last_topic = user_info.get("last_topic")
    last_department = user_info.get("last_department")
    last_content = user_info.get("last_content")
    dialogue_history = user_info.get("dialogue_history", [])

    messages = [{"role": "system", "content": DISCUSS_SYSTEM_PROMPT}]

    # إذا كانت هناك معلومة سابقة نمررها كـ Context
    if last_content:
        context_msg = (
            f"المعلومة التمريضية المعروضة حالياً للمستخدم:\n"
            f"📌 الموضوع: {last_topic} ({last_department or 'عام'})\n\n"
            f"نص المعلومة الأصلي:\n{last_content}\n\n"
            f"[توجيه]: المستخدم يناقشك أو يسألك بخصوص هذه المعلومة أو سيناريو مرتبط بها. أجب مباشرة وبالمصري."
        )
        messages.append({"role": "system", "content": context_msg})
    else:
        messages.append({
            "role": "system",
            "content": "[توجيه]: المستخدم يطرح عليك استفساراً تمريضياً عاماً بدون موضوع مسبق. اشرح له بوضوح وبالمصري.",
        })

    # تمرير آخر 6 رسائل من النقاش السابق للمحافظة على تسلسل المحادثة
    for entry in dialogue_history[-6:]:
        messages.append({"role": entry["role"], "content": entry["content"]})

    # رسالة المستخدم الحالية
    messages.append({"role": "user", "content": user_message})

    send_chat_action(chat_id, "typing")

    reply_content, err = call_openrouter(messages, max_tokens=1200, temperature=0.7)
    if err or not reply_content:
        send_telegram(chat_id, err or "⚠️ عذراً، لم أستطع تكوين الرد. حاول مرة أخرى.")
        return

    # حفظ النقاش في التاريخ
    dialogue_history.append({"role": "user", "content": user_message})
    dialogue_history.append({"role": "assistant", "content": reply_content})
    user_info["dialogue_history"] = dialogue_history[-10:]
    state[str(chat_id)] = user_info
    save_state(state)

    formatted = format_for_telegram(reply_content)
    send_telegram(chat_id, formatted)


# ============ Telegram Command Handlers ============
def cmd_thakka(chat_id):
    """عرض قائمة الأقسام المتاحة"""
    state = load_state()
    user_state = state.get(str(chat_id), {})
    current_dept = user_state.get("department")

    msg = (
        "📚 <b>ثقف نفسك — الأقسام التمريضية</b>\n\n"
        "اختار القسم اللي تحب تذاكر منه:\n\n"
    )

    for key, dept in DEPARTMENTS.items():
        emoji = "👉 ✅" if current_dept == key else "▫️"
        msg += f"{emoji} <b>{key}</b> - {dept['name']}\n"

    msg += (
        "\n📋 <b>الأوامر السريعة:</b>\n"
        "• /اختار [رقم] — لاختيار القسم (مثال: <code>/اختار 2</code> للعناية المركزة)\n"
        "• /معلومة — معلومة سريرية مع شرح كامل\n"
        "• /mcq — سؤال تفاعلي Native Quiz\n"
        "• /جديد — بدء محادثة جديدة وتصفير النقاش السابق\n"
        "• /قسم — معرفة القسم المختار حالياً\n\n"
        "💬 <b>ميزة النقاش:</b> في أي وقت، اكتب استفسارك أو رد على أي معلومة وهتناقش معاك فوراً!"
    )
    send_telegram(chat_id, msg)


def cmd_choose(chat_id, dept_key):
    """اختيار قسم محدد"""
    dept_key = dept_key.strip()
    if dept_key not in DEPARTMENTS:
        send_telegram(chat_id, f"❌ رقم القسم غير صحيح. برجاء اختيار رقم من 1 إلى {len(DEPARTMENTS)}.")
        return

    state = load_state()
    user_info = state.setdefault(str(chat_id), {})
    user_info["department"] = dept_key
    user_info["chosen_at"] = datetime.now().isoformat()
    save_state(state)

    dept = DEPARTMENTS[dept_key]
    send_telegram(
        chat_id,
        f"✅ ممتاز! اخترت قسم: <b>{dept['name']}</b>\n\n"
        f"دلوقتي تقدر تبعت:\n"
        f"• /معلومة — لجلب معلومة سريرية مشروحة بالمصري\n"
        f"• /mcq — لسؤال تدريبي تفاعلي\n"
        f"• أو اطرح أي سؤال مباشرة في الشات وسأرد عليك!"
    )


def cmd_fact(chat_id):
    """إرسال معلومة تمريضية وحفظها في السياق للنقاش"""
    state = load_state()
    user_info = state.get(str(chat_id), {})
    dept_key = user_info.get("department")

    if not dept_key:
        # إذا لم يختر قسماً نختار قسماً عشوائياً
        dept_key = random.choice(list(DEPARTMENTS.keys()))
        user_info["department"] = dept_key
        state[str(chat_id)] = user_info
        save_state(state)

    topic, department = pick_topic(dept_key)
    if not topic:
        send_telegram(chat_id, "❌ خطأ في اختيار الموضوع.")
        return

    send_telegram(chat_id, f"⏳ جاري تحضير معلومة تمريضية عن <b>{topic}</b>...")
    send_chat_action(chat_id, "typing")

    content = get_content(topic, department)
    if not content or content.startswith("⚠️"):
        send_telegram(chat_id, content or "❌ فشل جلب المعلومة")
        return

    # حفظ المعلومة في حالة المستخدم للنقاش
    user_info = state.setdefault(str(chat_id), {})
    user_info["last_topic"] = topic
    user_info["last_department"] = department
    user_info["last_content"] = content
    user_info["dialogue_history"] = []
    save_state(state)

    formatted = format_for_telegram(content)
    footer = (
        "\n\n━━━━━━━━━━━━━━━━━━━━\n"
        "💬 <b>حابب تفهم نقطة معينة أو تسأل عن حالة شفتها في المستشفى؟</b>\n"
        "<i>رد عليا في الشات مباشرة وهنتناقش سوا كأننا في النبطشية! 🩺</i>"
    )
    formatted += footer
    send_telegram(chat_id, formatted)


def cmd_mcq(chat_id):
    """إرسال سؤال MCQ تفاعلي كـ Quiz Poll"""
    state = load_state()
    user_info = state.get(str(chat_id), {})
    dept_key = user_info.get("department")

    if not dept_key:
        dept_key = random.choice(list(DEPARTMENTS.keys()))
        user_info["department"] = dept_key
        state[str(chat_id)] = user_info
        save_state(state)

    department = DEPARTMENTS[dept_key]
    topic = random.choice(department["topics"])

    send_telegram(chat_id, f"⏳ جاري إعداد سؤال كويز عن <b>{topic}</b>...")
    send_chat_action(chat_id, "typing")

    messages = [
        {"role": "system", "content": "أنت ممرض خبير ومحاضر تمريض. صغ سؤال اختيار من متعدد دقيق وسريري."},
        {"role": "user", "content": MCQ_PROMPT_TEMPLATE.format(topic=topic)},
    ]

    content, err = call_openrouter(messages, max_tokens=800, temperature=0.7)
    if err or not content:
        send_telegram(chat_id, err or "❌ تعذر توليد السؤال حالياً.")
        return

    # حفظ السؤال في السياق في حال أراد المستخدم الاستفسار عنه
    user_info["last_topic"] = f"MCQ: {topic}"
    user_info["last_department"] = department["name"]
    user_info["last_content"] = content
    user_info["dialogue_history"] = []
    save_state(state)

    # محاولة إرسال الـ Quiz كـ Poll تفاعلي أصلي
    mcq = parse_mcq_from_text(content)
    if mcq["question"] and len(mcq["options"]) >= 2:
        quiz_sent = send_telegram_quiz(chat_id, mcq)
        if quiz_sent:
            return

    # في حال تعذر إرسال Poll يتم إرسال النص منسقاً
    formatted = format_for_telegram(content)
    send_telegram(chat_id, formatted)


def cmd_reset(chat_id):
    """تصفير المحادثة والبدء من جديد"""
    state = load_state()
    if str(chat_id) in state:
        state[str(chat_id)]["dialogue_history"] = []
        state[str(chat_id)]["last_content"] = None
        state[str(chat_id)]["last_topic"] = None
        save_state(state)

    send_telegram(
        chat_id,
        "🔄 <b>تم تصفير المحادثة وسياق النقاش السابق بنجاح!</b>\n\n"
        "تقدر دلوقتي:\n"
        "• تطلب معلومة جديدة بـ /معلومة\n"
        "• تختار قسم بـ /ثقف\n"
        "• أو تسألني أي سؤال تمريضي يخطر في بالك مباشرة!"
    )


def cmd_current(chat_id):
    """عرض القسم المختار حالياً"""
    state = load_state()
    user_state = state.get(str(chat_id), {})
    dept_key = user_state.get("department")

    if not dept_key:
        send_telegram(chat_id, "❌ لم تختر قسماً بعد. ابعت /ثقف لاختيار قسم.")
        return

    dept = DEPARTMENTS[dept_key]
    last_topic = user_state.get("last_topic")
    msg = f"📂 القسم المختار حالياً: <b>{dept['name']}</b>"
    if last_topic:
        msg += f"\n📌 آخر موضوع تمت مناقشته: <i>{last_topic}</i>"
    send_telegram(chat_id, msg)


def cmd_help(chat_id):
    """رسالة المساعدة"""
    msg = (
        "🏥 <b>Nursing Interactive & Discussion Bot</b>\n\n"
        "<b>📋 الأوامر المتاحة:</b>\n"
        "• /ثقف — عرض واختيار الأقسام التمريضية الـ 8\n"
        "• /اختار [رقم] — تحديد تخصصك المفضل\n"
        "• /معلومة (أو /now) — جلب معلومة سريرية مع شرح كامل بالمصري\n"
        "• /mcq — سؤال تفاعلي Native Quiz تضغط على الإجابة وتعرف نتيجتك\n"
        "• /جديد (أو /reset) — تصفير الذاكرة وبدء موضوع جديد\n"
        "• /قسم — معرفة قسمك وموضوعك الحالي\n"
        "• /status — حالة اتصال البوت والموديل\n"
        "• /مساعدة — عرض هذه التعليمات\n\n"
        "💬 <b>طريقة المناقشة التفاعلية:</b>\n"
        "مش محتاج تضغط أوامر عشان تسأل! بعد ما تجيلك أي معلومة، اكتب أي استفسار في الشات (مثال: <i>'طب لو الضغط واطي أعمل إيه؟'</i> أو <i>'ليه المريض ده بياخد لازيكس؟'</i>) وهرد عليك فوراً!"
    )
    send_telegram(chat_id, msg)


def cmd_status(chat_id):
    """حالة البوت"""
    cairo_now = datetime.now(CAIRO_TZ)
    history = load_history()
    send_telegram(
        chat_id,
        f"🟢 <b>البوت شغّال ومستعد للنقاش!</b>\n\n"
        f"🕐 توقيت القاهرة: {cairo_now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🧠 الموديل المستخدم: <code>{OPENROUTER_MODEL}</code>\n"
        f"📚 إجمالي المواضيع المسجلة في السجل: {len(history)}\n"
        f"⚡ وضع التشغيل: خادم تفاعلي 24/7 مع دعم النقاش المباشر"
    )


def trigger_scheduled_reminder(chat_id):
    """إرسال تذكير تلقائي على رأس كل ساعة"""
    log.info(f"⏰ Sending hourly reminder to chat {chat_id}")
    cmd_fact(chat_id)


# ============ Telegram Polling Loop ============
last_update_id = 0


def handle_updates():
    """استقبال ومعالجة رسائل وأوامر تليجرام"""
    global last_update_id

    if not TELEGRAM_BOT_TOKEN:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(
            url,
            params={"offset": last_update_id + 1, "timeout": 25, "allowed_updates": ["message"]},
            timeout=30,
        )
        if r.status_code != 200:
            log.warning(f"getUpdates returned {r.status_code}")
            return

        updates = r.json().get("result", [])
        for update in updates:
            last_update_id = update["update_id"]
            msg = update.get("message", {})
            chat_id = str(msg.get("chat", {}).get("id", ""))
            text = (msg.get("text") or "").strip()

            if not text:
                continue

            log.info(f"📩 [{chat_id}] {text[:60]}")

            # التحقق من الصلاحية لو كان محدد TELEGRAM_CHAT_ID
            if TELEGRAM_CHAT_ID and chat_id != TELEGRAM_CHAT_ID:
                log.warning(f"Unauthorized chat_id: {chat_id}")
                continue

            # معالجة الأوامر
            parts = text.split(maxsplit=1)
            command = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if command in ("/ثقف", "/thakka", "/start"):
                cmd_thakka(chat_id)
            elif command in ("/اختار", "/choose"):
                cmd_choose(chat_id, arg)
            elif command in ("/معلومة", "/fact", "/now"):
                cmd_fact(chat_id)
            elif command in ("/mcq", "/quiz"):
                cmd_mcq(chat_id)
            elif command in ("/جديد", "/reset", "/clear"):
                cmd_reset(chat_id)
            elif command in ("/قسم", "/current"):
                cmd_current(chat_id)
            elif command in ("/مساعدة", "/help"):
                cmd_help(chat_id)
            elif command in ("/status",):
                cmd_status(chat_id)
            else:
                # أي رسالة نصية عادية تدخل فوراً في محرك النقاش!
                discuss_topic(chat_id, text)

    except requests.exceptions.Timeout:
        pass
    except Exception as e:
        log.exception("Error in handle_updates")


# ============ Main Entrypoint ============
if __name__ == "__main__":
    print("=" * 60)
    print("🏥 Nursing Interactive & Discussion Bot (Server Mode)")
    print(f"📅 Started at: {datetime.now(CAIRO_TZ).strftime('%Y-%m-%d %H:%M:%S')} Cairo")
    print("=" * 60)

    if not all([TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY]):
        log.error("❌ Missing required credentials (TELEGRAM_BOT_TOKEN or OPENROUTER_API_KEY)!")
        sys.exit(1)

    # التخلص من التراكمات القديمة على السيرفر عند بدء التشغيل
    try:
        init_resp = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset=-1",
            timeout=10,
        )
        init_results = init_resp.json().get("result", [])
        if init_results:
            last_update_id = init_results[-1]["update_id"]
            log.info(f"Initialized update offset to {last_update_id}")
    except Exception:
        pass

    log.info("👂 Listening for Telegram messages & discussions...")
    log.info("📋 Commands: /ثقف /اختار /معلومة /mcq /جديد /قسم /مساعدة")

    last_reminded_hour = datetime.now(CAIRO_TZ).hour

    while True:
        try:
            # 1. فحص التذكير بالساعة إذا كان مفعل ومحدد الـ CHAT_ID
            cairo_now = datetime.now(CAIRO_TZ)
            current_hour = cairo_now.hour

            if 8 <= current_hour <= 22 and current_hour != last_reminded_hour:
                last_reminded_hour = current_hour
                if TELEGRAM_CHAT_ID:
                    trigger_scheduled_reminder(TELEGRAM_CHAT_ID)

            # 2. الاستماع للرسائل والنقاشات
            handle_updates()

        except KeyboardInterrupt:
            log.info("👋 Bot stopped by user")
            break
        except Exception as e:
            log.exception("Error in main loop")
            time.sleep(3)
