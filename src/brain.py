"""
brain.py — GreenLeaf Bot | Brain / Orchestrator
=================================================
This module is the brain of the GreenLeaf HR Agent.
It classifies the employee's intent using Gemini 2.5 Flash
and dispatches to the correct tool.

Architecture position (HLD):
    app.py → privacy_gate.py → brain.py → policy_tool.py
                                        → holiday_tool.py
                                        → expense_tool.py

How it works:
    1. classify_intent() — asks Gemini to classify the question
    2. dispatch()        — calls the correct tool
    3. respond()         — returns answer + tool used to app.py

Branch: feature/brain
"""

import os
import sys

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import google.generativeai as genai
from dotenv import load_dotenv
# We switch to Hooman's module because Issue #42/#43 requires:
# - loading/indexing the whole data/ folder
# - using only provided text
# - redirecting sensitive wellbeing matters to the ombudsman
from src.tools.policy_wellbeing import query_handbook
from src.tools.expense_tool import validate_expense

# Load API key from .env
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Initialize Gemini model
model = genai.GenerativeModel("gemini-2.5-flash")

# Valid intents
VALID_INTENTS = ["policy", "holiday", "expense"]


# ─────────────────────────────────────────────
# INTENT CLASSIFICATION
# ─────────────────────────────────────────────

def classify_intent(text: str) -> str:
    """
    Uses Gemini to classify the employee's question into one of:
    - policy:  working hours, leave, bereavement, handbook rules
    - holiday: public holidays, Basel-Stadt calendar
    - expense: expense claims, reimbursements, receipts

    Interface contract (do not change):
        Input:  text: str
        Output: "policy" | "holiday" | "expense"

    Args:
        text: the employee's sanitised question

    Returns:
        str: one of "policy", "holiday", "expense"
    """
    try:
        prompt = f"""
You are an HR assistant router for GreenLeaf Logistics in Basel, Switzerland.
Your only job is to classify employee questions into exactly one category.

Categories:
- policy:  questions about working hours, attendance, leave rules, 
           bereavement, vacation days, handbook rules, remote work
- holiday: questions about public holidays, Basel-Stadt calendar, 
           whether a specific date is a holiday
- expense: questions about expense claims, reimbursements, 
           receipts, lunch costs, what can be expensed

Employee question: "{text}"

Reply with exactly one word only: policy, holiday, or expense.
Do not explain. Do not add punctuation. Just one word.
"""
        response = model.generate_content(prompt)
        intent = response.text.strip().lower()

        # Validate response is one of the expected intents
        if intent not in VALID_INTENTS:
            print(f"[BRAIN] Unexpected intent from Gemini: {intent} — defaulting to policy")
            return "policy"

        print(f"[BRAIN] Intent classified as: {intent}")
        return intent

    except Exception as e:
        print(f"[BRAIN ERROR] Classification failed: {e} — defaulting to policy")
        return "policy"

# ─────────────────────────────────────────────
# POLICY TYPE CLASSIFICATION
# ─────────────────────────────────────────────

def classify_policy_type(text: str) -> str:
    try:
        prompt = f"""
You are an HR assistant for GreenLeaf Logistics.
An employee asked: "{text}"

GreenLeaf handbook clearly defines:
- Working hours and attendance
- Time off and vacation
- Bereavement and special leave
- Fire safety and emergency procedures
- Expense claims

NOT in handbook — requires empathetic guidance:
- Harassment and bullying
- Psychological wellbeing
- Mental health and stress
- Workplace conflict and misconduct

Which category?
Reply with only: policy_handbook or policy_wellbeing
"""
        response = model.generate_content(prompt)
        result = response.text.strip().lower()
        if result not in ["policy_handbook", "policy_wellbeing"]:
            return "policy_handbook"
        print(f"[BRAIN] Policy type: {result}")
        return result
    except Exception as e:
        print(f"[BRAIN ERROR] Policy type failed: {e} — defaulting to policy_handbook")
        return "policy_handbook"


# ─────────────────────────────────────────────
# ROLE CLARIFICATION CHECK
# ─────────────────────────────────────────────

def needs_role_clarification(text: str) -> bool:
    try:
        prompt = f"""
You are an HR assistant for GreenLeaf Logistics.
An employee asked: "{text}"

GreenLeaf has DIFFERENT working hour rules for EACH role:
- Warehouse staff: must be onsite by 07:00
- Customer support: operates on shift rotation schedule
- General office staff: core hours 08:30 to 17:30

If the question is about working hours, start time, office hours,
arrival time, when to come in, opening hours, or attendance schedule
— the answer DEPENDS on which role the employee has.

Does this question ask about working hours, arrival time,
or when to be at work?
Reply with only YES or NO.
"""
        response = model.generate_content(prompt)
        result = response.text.strip().upper()
        print(f"[BRAIN] Needs role clarification: {result}")
        return "YES" in result
    except Exception as e:
        print(f"[BRAIN ERROR] {e} — skipping clarification")
        return False


# ─────────────────────────────────────────────
# ROLE FILTER
# ─────────────────────────────────────────────

def filter_by_role(question: str, handbook_text: str) -> str:
    try:
        prompt = f"""
You are an HR assistant for GreenLeaf Logistics.
The employee asked: "{question}"

Handbook section:
{handbook_text}

Extract ONLY the information relevant to this employee's role.
Be concise. Do not include rules for other roles.
Do not add information not in the handbook.
"""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"[BRAIN ERROR] {e} — returning full answer")
        return handbook_text



# ─────────────────────────────────────────────
# TOOL DISPATCH
# ─────────────────────────────────────────────

def dispatch(intent: str, text: str) -> dict:

    if intent == "policy":
        policy_type = classify_policy_type(text)

        if policy_type == "policy_wellbeing":
            from src.tools.policy_wellbeing import query_handbook as query_policy_wellbeing
            return query_policy_wellbeing(text)

        from src.tools.policy_handbook import query_handbook as query_policy_handbook

        if needs_role_clarification(text):
            text_lower = text.lower()
            known_roles = [
                "warehouse staff", "warehouse worker", "warehouse",
                "customer support", "support team",
                "office staff", "office worker", "general staff"
            ]
            if any(role in text_lower for role in known_roles):
                handbook_result = query_policy_handbook(text)
                if "error" in handbook_result:
                    return handbook_result
                focused = filter_by_role(text, handbook_result["answer"])
                return {
                    "answer": focused,
                    "source": handbook_result["source"]
                }
            else:
                return {
                    "needs_clarification": True,
                    "original_english": text,
                    "question": (
                        "To give you the correct answer — which role are you?\n"
                        "• Warehouse staff\n"
                        "• Customer support\n"
                        "• General office staff"
                    )
                }

        return query_policy_handbook(text)

    elif intent == "holiday":
        return {
            "answer": "Holiday checking is coming. For now please check the Basel-Stadt cantonal calendar.",
            "source": "GreenLeaf Bot — feature in development"
        }

    elif intent == "expense":
        from src.tools.expense_tool import validate_expense
        return validate_expense(text)

    else:
        return {
            "error": "I could not understand your question. Please contact HR directly."
        }


# ─────────────────────────────────────────────
# MAIN RESPOND FUNCTION — called by app.py
# ─────────────────────────────────────────────

def respond(text: str) -> tuple:
    """
    Main function called by app.py.
    Classifies intent and dispatches to correct tool.
    Detect the user's language and respond in the SAME language.

    Interface contract (do not change):
        Input:  text: str — sanitised employee question
        Output: tuple(dict, str) — (result, tool_used)

    Args:
        text: the employee's sanitised question

    Returns:
        tuple: (result dict, tool_used str)
    """
    try:
        # Step 1: Detect language
        user_lang = detect_language(text)

        # Step 2: Convert text to English
        textInEnglish = translate_text(text, "en", user_lang)
        print("step 2 done")

        # Step 3: Classify intent
        intent = classify_intent(textInEnglish)
        print("step 3 done")

        # Step 4: Dispatch — pass language so tools can respond correctly
        result = dispatch(intent, textInEnglish)
        print("step 4 done")
        
        # Step 5: Convert answer back to user's language if needed
        resultInUserLang = translate_text(result.get("answer"), user_lang, "en")
        result["answer"] = resultInUserLang
        print("step 5 done")

        tool_used = f"{intent}_tool"
        return result, tool_used

    except Exception as e:
        error_message = "Something went wrong. Please contact HR directly."
        error_messageInUserLang = translate_text(error_message, user_lang, "en")
        return {
            "error": error_messageInUserLang
        }, "unknown"
    

def detect_language(text: str) -> str:
    """
    Detects the language of the user's message.
    Returns ISO 639-1 code: 'en', 'de', 'fr', 'it', etc.
    """
    prompt = f"""
You are a highly accurate language detector.
Analyze the following text and reply with **only** the ISO 639-1 language code (two letters).

Examples:
- "Hello, how are you?" → en
- "Wann muss ich im Büro sein?" → de
- "Quelle est la politique de congés ?" → fr
- "Quando è il prossimo giorno festivo a Basilea?" → it

Text: "{text}"

Reply with exactly two lowercase letters, nothing else.
"""

    try:
        response = model.generate_content(prompt)
        lang = response.text.strip().lower()[:2]

        # Safety fallback
        if lang not in ("en", "de", "fr", "it"):
            lang = "en"

        print(f"[BRAIN] Language detected: {lang}")
        return lang

    except Exception as e:
        print(f"[BRAIN] Language detection failed: {e} — defaulting to en")
        return "en"
    

def translate_text(text: str, target_lang: str, source_lang: str = None) -> str:
    """
    Translates text to the target language using Gemini.
    
    Args:
        text: The text to translate
        target_lang: Target language ISO 639-1 code (e.g., 'de', 'fr', 'it', 'en')
        source_lang: Optional source language code. If None, Gemini will auto-detect.

    Returns:
        Translated text in the target language
    """
    if not text or not text.strip():
        return text

    # No translation needed if target is same as source
    if source_lang and source_lang.lower() == target_lang.lower():
        return text.strip()

    try:
        # Build clear and effective prompt
        lang_names = {
            "en": "English",
            "de": "German",
            "fr": "French",
            "it": "Italian",
            "es": "Spanish",
            "ru": "Russian"
        }

        target_name = lang_names.get(target_lang.lower(), target_lang)
        source_info = f" from {lang_names.get(source_lang.lower(), 'the original language')}" if source_lang else ""

        prompt = f"""
You are a professional, accurate translator for an HR bot at GreenLeaf Logistics in Basel.

Translate the following text into **{target_name}**{source_info}.
- Keep the tone professional and friendly.
- Preserve meaning exactly.
- Do not add any explanations or extra text.
- Do not use markdown unless the original has it.
- If the text is already in {target_name}, return it unchanged.

Text to translate:
\"\"\"{text}\"\"\"

Reply with **only** the translated text. Nothing else.
"""

        response = model.generate_content(prompt)
        translated = response.text.strip()

        print(f"[BRAIN] Translated from {source_lang or 'auto'} → {target_lang}: {len(text)} → {len(translated)} chars")
        return translated

    except Exception as e:
        print(f"[BRAIN ERROR] Translation failed ({source_lang} → {target_lang}): {e}")
        # Fallback: return original text so the bot doesn't break
        return text

# =============================================================================
# HOW TO TEST
# =============================================================================
#
# Run the test file:
#   pytest tests/test_brain.py -v
#
# Expected results:
#   "When do I have to be in the office?"    → intent: policy
#   "Is May 1st a holiday in Basel?"         → intent: holiday
#   "Can I expense a 40 CHF lunch?"          → intent: expense
#   "Do I get leave for a family emergency?" → intent: policy
#
# =============================================================================