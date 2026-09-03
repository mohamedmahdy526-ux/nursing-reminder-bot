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
import re
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

━━━ 📝 MCQ ━━━
السؤال: [سؤال سريري تطبيقي يختبر فهم النقطة الأساسية]
أ) [الخيار الأول]
ب) [الخيار الثاني]
ج) [الخيار الثالث]
د) [الخيار الرابع]

━━━ ✅ الإجابة ━━━
الإجابة: [حرف واحد فقط: أ أو ب أو ج أو د]
الشرح: [سطر واحد مختصر يشرح سبب صحة الإجابة]

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


def call_gemini(messages, max_tokens=2500, temperature=0.7):
    """استدعاء Google Gemini API كبديل فائق السرعة ومجاني مع ضبط استهلاك الـ Tokens"""
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

        gemini_models = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.7-flash"]
        for g_model in gemini_models:
            log.info(f"🌟 Trying Gemini model: {g_model}...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": contents,
                "generationConfig": {
                    "maxOutputTokens": max(max_tokens, 2500),
                    "temperature": temperature,
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            }
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

            r = requests.post(url, json=payload, timeout=40)
            if r.status_code == 200:
                res_data = r.json()
                candidates = res_data.get("candidates", [])
                if candidates:
                    first_cand = candidates[0]
                    finish_reason = first_cand.get("finishReason")
                    if finish_reason == "MAX_TOKENS":
                        log.warning(f"⚠️ Gemini {g_model} output was truncated (MAX_TOKENS). Trying next model...")
                        continue
                    parts = first_cand.get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        text = parts[0]["text"]
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


def get_main_keyboard():
    """لوحة الأزرار السريعة الدائمة أسفل المحادثة"""
    return {
        "keyboard": [
            [{"text": "🏥 معلومة جديدة + كويز"}, {"text": "📝 كويز تدريبي"}],
            [{"text": "🩺 تخصصات التمريض (الأقسام)"}, {"text": "📌 القسم الحالي"}],
            [{"text": "🔄 محادثة جديدة"}, {"text": "📊 حالة البوت"}],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


DEPT_ARABIC_NAMES = {
    "1": "👶 حديثي الولادة (NICU)",
    "2": "🫀 العناية المركزة (ICU)",
    "3": "🧸 تمريض الأطفال",
    "4": "💊 علم الأدوية (Pharma)",
    "5": "📖 المصطلحات الطبية",
    "6": "🛡️ سلامة المرضى & ISBAR",
    "7": "📈 رسم القلب (ECG)",
    "8": "🚨 الطوارئ والحوادث (ER)",
}


def get_departments_inline_keyboard():
    """أزرار تفاعلية مضمنة داخل الشات لاختيار التخصص بضغطة واحدة"""
    keyboard = []
    keys = list(DEPARTMENTS.keys())
    for i in range(0, len(keys), 2):
        row = []
        for k in keys[i:i+2]:
            label = DEPT_ARABIC_NAMES.get(k, DEPARTMENTS[k]["name"])
            row.append({
                "text": label,
                "callback_data": f"dept_{k}"
            })
        keyboard.append(row)
    return {"inline_keyboard": keyboard}


def answer_callback_query(callback_query_id, text=None):
    """إشعار تليجرام باستلام الضغطة على الزر التفاعلي"""
    if not TELEGRAM_BOT_TOKEN or not callback_query_id:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    try:
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        requests.post(url, json=payload, timeout=5)
    except Exception:
        pass


def setup_bot_commands():
    """تسجيل الأوامر في زر القائمة الرسمي في تليجرام (Menu Button [/])"""
    if not TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setMyCommands"
    commands = [
        {"command": "fact", "description": "🏥 معلومة سريرية + كويز تفاعلي"},
        {"command": "mcq", "description": "📝 سؤال تدريبي تفاعلي"},
        {"command": "departments", "description": "🩺 تخصصات التمريض الـ 8"},
        {"command": "current", "description": "📌 معرفة القسم المختار حالياً"},
        {"command": "reset", "description": "🔄 تصفير النقاش وبدء محادثة جديدة"},
        {"command": "status", "description": "📊 حالة واتصال البوت"},
        {"command": "help", "description": "❓ شرح الأوامر والمساعدة"},
    ]
    try:
        r = requests.post(url, json={"commands": commands}, timeout=10)
        if r.status_code == 200:
            log.info("✅ Telegram Bot Commands Menu configured successfully!")
        else:
            log.warning(f"⚠️ Failed to set bot commands ({r.status_code}): {r.text[:100]}")

        # تفعيل زر القائمة بجوار خانة الكتابة
        btn_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setChatMenuButton"
        requests.post(btn_url, json={"menu_button": {"type": "commands"}}, timeout=5)
    except Exception as e:
        log.warning(f"Error setting bot commands: {e}")


def send_telegram(chat_id, text, parse_mode="HTML", reply_markup=None):
    """إرسال رسالة تليجرام مع تقسيم آمن ومعالجة أخطاء HTML ودعم الأزرار (reply_markup)"""
    if not TELEGRAM_BOT_TOKEN or not text:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    def _post_chunk(chunk, mode, markup=None):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "disable_web_page_preview": True,
        }
        if mode:
            payload["parse_mode"] = mode
        if markup:
            payload["reply_markup"] = json.dumps(markup)
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
    total_chunks = len(chunks)
    for idx, chunk in enumerate(chunks):
        markup = reply_markup if (idx == total_chunks - 1) else None
        try:
            r = _post_chunk(chunk, parse_mode, markup)
            if r.status_code != 200:
                log.warning(f"Telegram parse_mode={parse_mode} failed ({r.status_code}): {r.text[:120]}. Retrying as plain text...")
                r_fallback = _post_chunk(chunk, "", markup)
                if r_fallback.status_code != 200:
                    log.error(f"Telegram plain fallback failed: {r_fallback.text[:150]}")
                    success = False
        except Exception as e:
            log.exception("Failed to send telegram message chunk")
            success = False

    return success


def clean_md(text):
    """إزالة علامات الماركداون لتسهيل المطابقة النصية المرنة"""
    if not text:
        return ""
    return re.sub(r"[*_#`]", "", text).strip()


def parse_mcq_from_text(text):
    """استخراج سؤال MCQ وخياراته وإجابته الصحيحة والشرح بمرونة عالية مع مختلف النماذج"""
    mcq = {
        "question": None,
        "options": [],
        "correct_letter": None,
        "explanation": None,
    }
    if not text:
        return mcq

    letter_map = {
        "أ": "A", "ا": "A", "إ": "A", "آ": "A", "1": "A", "A": "A", "a": "A",
        "ب": "B", "2": "B", "B": "B", "b": "B",
        "ج": "C", "3": "C", "C": "C", "c": "C",
        "د": "D", "4": "D", "D": "D", "d": "D",
    }

    in_mcq = False
    in_answer = False

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        cleaned = clean_md(line)
        if not cleaned:
            continue

        # فحص بداية قسم MCQ
        if ("MCQ" in cleaned.upper() or "سؤال" in cleaned or "كويز" in cleaned) and (
            "━" in cleaned or "---" in cleaned or "###" in cleaned or "MCQ" in cleaned.upper()
        ):
            in_mcq = True
            in_answer = False
            continue

        # فحص قسم الإجابة
        if any(w in cleaned for w in ["الإجابة", "الاجابة", "الجواب", "Answer"]) and any(
            sep in cleaned for sep in ["━", "---", "###", "✅", "✔", "CHECK"]
        ):
            in_mcq = False
            in_answer = True
            continue

        # نهاية قسم MCQ / الإجابة لو دخلنا في قسم جديد (مثل المصدر)
        if (in_mcq or in_answer) and any(
            h in cleaned for h in ["المصدر", "معلومة", "ملاحظة", "Source", "Reference"]
        ) and ("━" in cleaned or "###" in cleaned or "---" in cleaned):
            in_mcq = False
            in_answer = False
            continue

        # استخراج السؤال
        if in_mcq and not mcq["question"]:
            for q_prefix in ["السؤال:", "سؤال:", "السؤال", "س:", "Question:"]:
                if cleaned.startswith(q_prefix):
                    q_text = cleaned[len(q_prefix):].strip()
                    if q_text:
                        mcq["question"] = q_text
                    break
            else:
                if not re.match(r"^[(]?([أاإآبجدABCDabcd1-4])[)\].:\-–]", cleaned):
                    if len(cleaned) > 10 and not cleaned.startswith("━"):
                        mcq["question"] = cleaned

        # استخراج الاختيارات
        if in_mcq:
            opt_match = re.match(r"^[(]?([أاإآبجدABCDabcd1-4])[)\].:\-–\s]+\s*(.+)$", cleaned)
            if opt_match:
                raw_let = opt_match.group(1)
                opt_text = opt_match.group(2).strip()
                norm_let = letter_map.get(raw_let)
                if norm_let and opt_text:
                    if not any(let == norm_let for let, _ in mcq["options"]):
                        mcq["options"].append((norm_let, opt_text))
            continue

        # استخراج الإجابة والشرح
        if in_answer or (in_mcq and any(ans_kw in cleaned for ans_kw in ["الإجابة:", "الاجابة:", "الجواب:", "Answer:"])):
            if any(ans_kw in cleaned for ans_kw in ["الإجابة:", "الاجابة:", "الجواب:", "الإجابة الصحيحة:", "الاجابة الصحيحة:", "Answer:"]):
                ans_text = cleaned.split(":", 1)[1].strip()
                for ch in ans_text:
                    if ch in letter_map:
                        mcq["correct_letter"] = letter_map[ch]
                        break
            elif any(exp_kw in cleaned for exp_kw in ["الشرح:", "شرح:", "السبب:", "Explanation:"]):
                mcq["explanation"] = cleaned.split(":", 1)[1].strip()

    return mcq


def strip_mcq_section(text):
    """فصل وتجريد قسم الـ MCQ والإجابة من نص المعلومة لإرسالهما منفصلين"""
    if not text:
        return ""
    lines = text.split("\n")
    cleaned = []
    skip = False

    for line in lines:
        line_stripped = line.strip()
        c = clean_md(line_stripped)

        # بداية قسم MCQ
        if ("MCQ" in c.upper() or "سؤال" in c or "كويز" in c) and (
            "━" in c or "---" in c or "###" in c or "MCQ" in c.upper()
        ):
            skip = True
            continue

        # نهاية التخطي لو دخلنا في قسم جديد مثل المصدر
        if skip and any(h in c for h in ["المصدر", "معلومة", "ملاحظة", "Source", "Reference"]) and (
            "━" in c or "###" in c or "---" in c
        ):
            skip = False
            cleaned.append(line)
            continue

        if skip:
            continue

        cleaned.append(line)

    return "\n".join(cleaned).strip()


def send_telegram_quiz(chat_id, mcq):
    """إرسال سؤال MCQ كـ Native Quiz Poll تفاعلي في تليجرام"""
    if not TELEGRAM_BOT_TOKEN:
        log.error("Telegram bot token is missing!")
        return False

    if not mcq.get("question") or len(mcq.get("options", [])) < 2:
        log.warning(f"Invalid MCQ data, skipping quiz: question={mcq.get('question')}, options_count={len(mcq.get('options', []))}")
        return False

    # تصفية الخيارات لتكون مميزة وغير مكررة (Telegram API يرفض التكرار)
    seen_texts = set()
    unique_options = []
    option_letters = []

    for letter, opt_text in mcq["options"]:
        clean_opt = opt_text.strip()[:100]
        if clean_opt and clean_opt not in seen_texts:
            seen_texts.add(clean_opt)
            unique_options.append(clean_opt)
            option_letters.append(letter)

    if len(unique_options) < 2:
        log.warning("Less than 2 distinct options for quiz poll")
        return False

    unique_options = unique_options[:10]
    option_letters = option_letters[:10]

    correct_option_id = None
    if mcq.get("correct_letter"):
        for idx, letter in enumerate(option_letters):
            if letter == mcq["correct_letter"]:
                correct_option_id = idx
                break

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPoll"
    payload = {
        "chat_id": chat_id,
        "question": f"📝 {mcq['question']}"[:300],
        "options": unique_options,
        "is_anonymous": True,
    }

    if correct_option_id is not None:
        payload["type"] = "quiz"
        payload["correct_option_id"] = correct_option_id
        if mcq.get("explanation"):
            payload["explanation"] = mcq["explanation"][:200]
    else:
        payload["type"] = "regular"
        log.warning("No correct answer found, sending as regular poll")

    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 200:
            log.info(f"📊 Quiz Poll ({payload['type']}) sent to {chat_id}: {mcq['question'][:50]}")
            return True
        log.error(f"Quiz error ({r.status_code}): {r.text[:200]}")
        return False
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
def cmd_start(chat_id):
    """رسالة الترحيب الأولى وتفعيل أزرار القائمة"""
    state = load_state()
    user_state = state.get(str(chat_id), {})
    current_dept = user_state.get("department")
    current_name = DEPARTMENTS[current_dept]["name"] if current_dept in DEPARTMENTS else "لم يحدد بعد (عشوائي)"

    welcome_msg = (
        "👋 <b>أهلاً بك في بوت التمريض التفاعلي والسريري!</b> 🩺\n\n"
        "أنا هنا لمساعدتك في المذاكرة والممارسة التمريضية العملية بأقوى المعلومات والأسئلة التفاعلية.\n\n"
        f"📌 <b>تخصصك المختار حالياً:</b> <b>{current_name}</b>\n\n"
        "💡 <b>كيف تستخدم البوت؟</b>\n"
        "• اختر تخصصك التمريضي من الأزرار بالأسفل 👇\n"
        "• أو اضغط <b>[🏥 معلومة جديدة + كويز]</b> في القائمة بالأسفل\n"
        "• وفي أي وقت، تقدر تسأل أو ترد على أي معلومة وندردش سوا!"
    )
    send_telegram(chat_id, welcome_msg, reply_markup=get_departments_inline_keyboard())
    send_telegram(chat_id, "✨ تم تفعيل لوحة الأزرار السريعة بالأسفل لراحتك 👇", reply_markup=get_main_keyboard())


def cmd_thakka(chat_id):
    """عرض قائمة الأقسام المتاحة مع أزرار تفاعلية مضمنة"""
    state = load_state()
    user_state = state.get(str(chat_id), {})
    current_dept = user_state.get("department")
    current_name = DEPARTMENTS[current_dept]["name"] if current_dept in DEPARTMENTS else "لم يحدد بعد (عشوائي)"

    msg = (
        "🩺 <b>الأقسام والتخصصات التمريضية الـ 8:</b>\n\n"
        f"📌 <b>القسم المختار حالياً:</b> <b>{current_name}</b>\n\n"
        "اضغط على أي تخصص بالأسفل لاختياره بلمسة واحدة: 👇"
    )
    send_telegram(chat_id, msg, reply_markup=get_departments_inline_keyboard())


def cmd_choose(chat_id, dept_key):
    """اختيار قسم محدد"""
    dept_key = dept_key.strip()
    if dept_key not in DEPARTMENTS:
        send_telegram(chat_id, f"❌ رقم القسم غير صحيح. برجاء اختيار رقم من 1 إلى {len(DEPARTMENTS)}.", reply_markup=get_main_keyboard())
        return

    state = load_state()
    user_info = state.setdefault(str(chat_id), {})
    user_info["department"] = dept_key
    user_info["chosen_at"] = datetime.now().isoformat()
    save_state(state)

    dept = DEPARTMENTS[dept_key]
    send_telegram(
        chat_id,
        f"✅ ممتاز! تم اختيار قسم: <b>{dept['name']}</b> بنجاح.\n\n"
        f"دلوقتي تقدر تبعت:\n"
        f"• 🏥 <b>معلومة جديدة + كويز</b> من الأزرار بالأسفل\n"
        f"• 📝 <b>كويز تدريبي</b>\n"
        f"• أو اطرح أي سؤال سريري في الشات وسأرد عليك فوراً!",
        reply_markup=get_main_keyboard()
    )


def cmd_fact(chat_id):
    """إرسال معلومة تمريضية متبوعة بسؤال Quiz Poll تفاعلي وحفظها في السياق للنقاش"""
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

    send_telegram(chat_id, f"⏳ جاري تحضير معلومة وكويز تفاعلي عن <b>{topic}</b>...")
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

    # 1. استخراج الـ MCQ من النص
    mcq = parse_mcq_from_text(content)

    # 2. تجريد قسم الكويز من نص الرسالة حتى لا تحترق الإجابة
    clean_text = strip_mcq_section(content)

    # 3. تنسيق النص وإضافة فوتر النقاش
    formatted = format_for_telegram(clean_text)
    footer = (
        "\n\n━━━━━━━━━━━━━━━━━━━━\n"
        "💬 <b>حابب تفهم نقطة معينة أو تسأل عن حالة شفتها في المستشفى؟</b>\n"
        "<i>رد عليا في الشات مباشرة وهنتناقش سوا كأننا في النبطشية! 🩺</i>"
    )
    formatted += footer
    send_telegram(chat_id, formatted)

    # 4. إرسال سؤال الـ Quiz Poll التفاعلي فوراً بعد المعلومة
    if mcq.get("question") and len(mcq.get("options", [])) >= 2:
        time.sleep(1)
        send_telegram_quiz(chat_id, mcq)
    else:
        log.warning(f"No valid MCQ found in content for topic '{topic}'. Skipped poll.")


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
        "تقدر دلوقتي تطلب معلومة جديدة أو تختار تخصصاً من القائمة بالأسفل 👇",
        reply_markup=get_main_keyboard(),
    )


def cmd_current(chat_id):
    """عرض القسم المختار حالياً"""
    state = load_state()
    user_state = state.get(str(chat_id), {})
    dept_key = user_state.get("department")

    if not dept_key:
        send_telegram(chat_id, "❌ لم تختر قسماً بعد. اضغط [🩺 تخصصات التمريض (الأقسام)] بالأسفل لاختيار تخصص.", reply_markup=get_main_keyboard())
        return

    dept = DEPARTMENTS[dept_key]
    last_topic = user_state.get("last_topic")
    msg = f"📂 القسم المختار حالياً: <b>{dept['name']}</b>"
    if last_topic:
        msg += f"\n📌 آخر موضوع تمت مناقشته: <i>{last_topic}</i>"
    send_telegram(chat_id, msg, reply_markup=get_main_keyboard())


def cmd_help(chat_id):
    """رسالة المساعدة"""
    msg = (
        "🏥 <b>دليل واستخدام بوت التمريض التفاعلي:</b>\n\n"
        "📋 <b>القائمة والأزرار السريعة بالأسفل:</b>\n"
        "• <b>[🏥 معلومة جديدة + كويز]</b>: جلب معلومة سريرية مشروحة بالمصري متبوعة بسؤال كويز تفاعلي.\n"
        "• <b>[📝 كويز تدريبي]</b>: سؤال MCQ تفاعلي Native Quiz تضغط على الإجابة وتعرف نتيجتك فوراً.\n"
        "• <b>[🩺 تخصصات التمريض]</b>: عرض الأقسام الـ 8 واختيار التخصص بلمسة واحدة.\n"
        "• <b>[📌 القسم الحالي]</b>: إظهار التخصص الطبي المختار حالياً.\n"
        "• <b>[🔄 محادثة جديدة]</b>: تصفير الذاكرة وبدء استفسار تمريضي جديد.\n"
        "• <b>[📊 حالة البوت]</b>: فحص حالة الموديل والاتصال.\n\n"
        "💬 <b>طريقة المناقشة التفاعلية:</b>\n"
        "مش محتاج تضغط أوامر عشان تسأل! بعد ما تجيلك أي معلومة، اكتب أي استفسار في الشات (مثال: <i>'طب لو الضغط واطي أعمل إيه؟'</i>) وهرد عليك فوراً!"
    )
    send_telegram(chat_id, msg, reply_markup=get_main_keyboard())


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
        f"⚡ وضع التشغيل: خادم تفاعلي 24/7 مع دعم النقاش المباشر والأزرار التفاعلية",
        reply_markup=get_main_keyboard(),
    )


def trigger_scheduled_reminder(chat_id):
    """إرسال تذكير تلقائي على رأس كل ساعة"""
    log.info(f"⏰ Sending hourly reminder to chat {chat_id}")
    cmd_fact(chat_id)


# ============ Telegram Polling Loop ============
last_update_id = 0


def handle_updates():
    """استقبال ومعالجة رسائل وأوامر ونقرات أزرار تليجرام"""
    global last_update_id

    if not TELEGRAM_BOT_TOKEN:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(
            url,
            params={"offset": last_update_id + 1, "timeout": 25, "allowed_updates": ["message", "callback_query"]},
            timeout=30,
        )
        if r.status_code != 200:
            log.warning(f"getUpdates returned {r.status_code}")
            return

        updates = r.json().get("result", [])
        for update in updates:
            last_update_id = update["update_id"]

            # 1. معالجة نقرات الأزرار التفاعلية (Inline Keyboard Callback)
            cb = update.get("callback_query")
            if cb:
                cb_id = cb.get("id")
                cb_chat_id = str(cb.get("message", {}).get("chat", {}).get("id", ""))
                cb_data = cb.get("data", "")

                if TELEGRAM_CHAT_ID and cb_chat_id != TELEGRAM_CHAT_ID:
                    continue

                if cb_data.startswith("dept_"):
                    dept_key = cb_data.replace("dept_", "")
                    answer_callback_query(cb_id, text="تم حفظ اختيار التخصص بنجاح ✅")
                    cmd_choose(cb_chat_id, dept_key)
                continue

            # 2. معالجة الرسائل وأزرار الكيبورد
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

            clean_text = text.lower()
            if text == "🏥 معلومة جديدة + كويز" or clean_text in ("/معلومة", "/fact", "/now", "معلومة"):
                cmd_fact(chat_id)
            elif text == "📝 كويز تدريبي" or clean_text in ("/mcq", "/quiz", "كويز"):
                cmd_mcq(chat_id)
            elif text == "🩺 تخصصات التمريض (الأقسام)" or clean_text in ("/ثقف", "/thakka", "/departments", "أقسام"):
                cmd_thakka(chat_id)
            elif text == "📌 القسم الحالي" or clean_text in ("/قسم", "/current"):
                cmd_current(chat_id)
            elif text == "🔄 محادثة جديدة" or clean_text in ("/جديد", "/reset", "/clear"):
                cmd_reset(chat_id)
            elif text == "📊 حالة البوت" or clean_text in ("/status", "status"):
                cmd_status(chat_id)
            elif clean_text in ("/مساعدة", "/help", "مساعدة"):
                cmd_help(chat_id)
            elif clean_text.startswith("/start"):
                cmd_start(chat_id)
            elif clean_text.startswith("/اختار") or clean_text.startswith("/choose"):
                parts = text.split(maxsplit=1)
                arg = parts[1] if len(parts) > 1 else ""
                cmd_choose(chat_id, arg)
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

    # تهيئة زر القائمة الرسمي في تليجرام
    setup_bot_commands()

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
    log.info("📋 Touch Menu & Commands: /start /معلومة /mcq /ثقف /قسم /جديد /status /help")

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
