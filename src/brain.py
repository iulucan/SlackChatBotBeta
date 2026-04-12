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
import json
from typing import Set
from datetime import date, datetime

from dotenv import load_dotenv

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception

# We switch to Hooman's module because Issue #42/#43 requires:
# - loading/indexing the whole data/ folder
# - using only provided text
# - redirecting sensitive wellbeing matters to the ombudsman
from src.tools.policy_wellbeing import query_handbook as query_policy_wellbeing
from src.tools.policy_handbook import query_handbook as query_policy_handbook
from src.tools.expense_tool import validate_expense
from src.tools.holiday_tool import SwissHolidayChecker

# Load API key from .env
load_dotenv()

client = genai.Client(
    api_key=os.getenv('GEMINI_API_KEY')
)

# Valid intents
VALID_INTENTS = ["policy", "holiday", "expense"]

# Keyword lists for deterministic routing in dispatch()
HANDBOOK_KEYWORDS = [
    "bereavement", "passed away", "funeral", "death of", "died",
    "remote work", "work from home", "wfh", "home office",
    "vacation", "annual leave", "time off", "sick leave", "sick day",
    "working hours", "office hours", "start time", "attendance",
    "arrive", "arrival", "what time", "shift", "onsite", "on-site",
    "fire safety", "emergency procedure",
]


WELLBEING_KEYWORDS = [
    "harass", "bully", "bullying", "stress", "burnout", "mental health",
    "misconduct", "whistleblow", "ombudsman", "being treated", "toxic",
]

VALID_CANTONS: Set[str] = {
    "AG", "AR", "AI", "BL", "BS", "BE", "FR", "GE", "GL",
    "GR", "JU", "LU", "NE", "NW", "OW", "SG", "SH", "SZ",
    "SO", "TG", "TI", "UR", "VD", "VS", "ZH", "ZG"
}

# Helper function for tenacity to check if the error is a 503/429 (ServiceUnavailable/ResourceExhausted)
def is_retryable_error(exception: BaseException) -> bool:
    error_str = str(exception)
    class_name = exception.__class__.__name__
    return (any(err in error_str for err in ["503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "ServerError"])
            or class_name in ["ServerError", "ServiceUnavailable", "ResourceExhausted", "APIError"])

@retry(
    retry=retry_if_exception(is_retryable_error),
    stop=stop_after_attempt(8),
    wait=wait_exponential_jitter(initial=1, max=30),
    before_sleep=lambda rs: print(f"[BRAIN] Capacity issue. Retrying... (Attempt {rs.attempt_number})"),
    reraise=True # Crucial fix: Forces Tenacity to raise the actual APIError instead of RetryError
)
def generate_with_backoff(model_name, prompt_entered, config_type):
    """
    Calls Gemini with automatic exponential backoff on 503/429 errors handled by Tenacity
    Error code 503 is for ServiceUnavailable/ResourceExhausted
    Error code 429 is for ResourceExhausted
    """
    response = client.models.generate_content(
        model=model_name,
        contents=prompt_entered,
        config=config_type
    )
    return response

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
        text: the employee's sanitized question

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
        response = generate_with_backoff(
            prompt_entered=prompt,
            model_name="gemini-2.5-flash",
            config_type=types.GenerateContentConfig(automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        )
        intent = response.text.strip().lower()

        # Validate response is one of the expected intents
        if intent not in VALID_INTENTS:
            print(f"[BRAIN] Unexpected intent from Gemini: {intent} — defaulting to policy")
            return "policy"

        print(f"[BRAIN] Intent classified as: {intent}")
        return intent

    except Exception as e:
        print(f"[BRAIN ERROR] Classification failed: {e.__class__.__name__}: {e} — defaulting to policy")
        return "policy"

# ─────────────────────────────────────────────
# POLICY TYPE CLASSIFICATION
# ─────────────────────────────────────────────

def classify_policy_type(text: str) -> str:
    try:
        prompt = f"""
You are an HR assistant for GreenLeaf Logistics.
An employee asked: "{text}"

Reply with policy_handbook if the question is about ANY of these:
- Working hours, attendance, start time, shift schedule
- Vacation days, annual leave, time off entitlement
- Bereavement leave, compassionate leave, death of family member
- Remote work, working from home
- Fire safety, emergency procedures
- Expense claims, reimbursements
- Any other written rule or policy in the employee handbook

Reply with policy_wellbeing ONLY if the question is about:
- Harassment or bullying (someone treating them badly)
- Mental health, stress, burnout, emotional distress
- Workplace conflict or misconduct between people
- Whistleblowing

IMPORTANT: Bereavement (death of a relative) is a handbook policy — reply policy_handbook.
IMPORTANT: Remote work is a handbook policy — reply policy_handbook.
IMPORTANT: When in doubt, reply policy_handbook.

Reply with only: policy_handbook or policy_wellbeing
"""
        response = generate_with_backoff(
            prompt_entered=prompt,
            model_name="gemini-2.5-flash",
            config_type=types.GenerateContentConfig(automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        )
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

Questions about leave, vacation, bereavement, sick days, time off,
remote work, or expense claims do NOT depend on role — reply NO for those.

Does this question specifically ask about working hours, arrival time,
or when to be physically present at work (NOT about leave, absence, or remote work)?
Reply with only YES or NO.
"""
        response = generate_with_backoff(
            prompt_entered=prompt,
            model_name="gemini-2.5-flash",
            config_type=types.GenerateContentConfig(automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        )
        result = response.text.strip().upper()
        print(f"[BRAIN] Needs role clarification: {result}")
        return "YES" in result
    except Exception as e:
        print(f"[BRAIN ERROR] Clarification check failed: {e} — skipping")
        return False


# ─────────────────────────────────────────────
# EMERGENCY TYPE CLASSIFICATION
# ─────────────────────────────────────────────

def classify_emergency_type(text: str) -> str:
    """
    Called only when "emergency" is detected in the text.
    Classifies whether it is a family/personal emergency (→ bereavement/leave section)
    or a physical/safety emergency (→ fire safety section).

    Returns: "bereavement" | "safety" | "other"
    """
    try:
        prompt = f"""
You are an HR assistant for GreenLeaf Logistics.
An employee said: "{text}"

Classify this as exactly one of:
- bereavement: the employee has a family emergency, personal emergency,
  urgent family situation, sick relative, death in the family, or needs emergency leave
- safety: the employee is asking about fire alarms, evacuation, assembly point,
  fire wardens, or physical building safety procedures
- other: anything else

Reply with only one word: bereavement, safety, or other.
"""
        response = generate_with_backoff(
            prompt_entered=prompt,
            model_name="gemini-2.5-flash",
            config_type=types.GenerateContentConfig(automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        )
        result = response.text.strip().lower()
        if result not in ["bereavement", "safety", "other"]:
            return "other"
        print(f"[BRAIN] Emergency type: {result}")
        return result
    except Exception as e:
        print(f"[BRAIN ERROR] Emergency classification failed: {e} — defaulting to other")
        return "other"


# ─────────────────────────────────────────────
# ROLE VALIDATION
# ─────────────────────────────────────────────

def validate_role(text: str) -> bool:
    """
    Returns True if the text clearly identifies one of the three GreenLeaf roles.
    Used to validate follow-up replies before passing to filter_by_role.
    """
    try:
        prompt = f"""
You are an HR assistant for GreenLeaf Logistics.
The employee replied: "{text}"

GreenLeaf has exactly three roles:
- Warehouse staff (also: warehouse, warehose, warehouss, warehouse worker, etc.)
- Customer support (also: customer service, support team, support agent, etc.)
- General office staff (also: office, office worker, general staff, etc.)

Does this reply clearly identify one of these three roles, even with spelling mistakes?
Reply with only YES or NO.
"""
        response = generate_with_backoff(
            prompt_entered=prompt,
            model_name="gemini-2.5-flash",
            config_type=types.GenerateContentConfig(automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        )
        result = response.text.strip().upper()
        print(f"[BRAIN] Role validated: {result}")
        return "YES" in result
    except Exception as e:
        print(f"[BRAIN ERROR] Role validation failed: {e}")
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

Extract the information relevant to this employee's role.
- Always include universal rules that apply to ALL roles (e.g. mandatory 45-minute lunch break).
- If specific hours or details are listed for their role, state them clearly.
- If the handbook gives partial information (e.g. "refer to IT schedules" or "shift rotation"),
  include that and tell the employee where to get the full details.
- Be concise. Do not include rules for other roles.
- Do not add information not in the handbook.
"""
        response = generate_with_backoff(
            prompt_entered=prompt,
            model_name="gemini-2.5-flash",
            config_type=types.GenerateContentConfig(automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        )
        return response.text.strip()
    except Exception as e:
        print(f"[BRAIN ERROR] Filter by role failed: {e} — returning full answer")
        return handbook_text



# ─────────────────────────────────────────────
# TOOL DISPATCH
# ─────────────────────────────────────────────

def dispatch(intent: str, text: str) -> dict:

    if intent == "policy":
        # Deterministic pre-check — route without asking Gemini to avoid misclassification
        text_lower_check = text.lower()
        if any(kw in text_lower_check for kw in WELLBEING_KEYWORDS):
            policy_type = "policy_wellbeing"
        elif any(kw in text_lower_check for kw in HANDBOOK_KEYWORDS):
            policy_type = "policy_handbook"
        else:
            policy_type = classify_policy_type(text)

        if policy_type == "policy_wellbeing":
            return query_policy_wellbeing(text)

        # Emergency pre-check — always run, no keyword trigger
        # Gemini classifies every policy question; returns "other" for non-emergency queries
        emergency_type = classify_emergency_type(text)
        if emergency_type == "bereavement":
            return query_policy_handbook("bereavement special leave personal tragedy")
        elif emergency_type == "safety":
            return query_policy_handbook("fire safety emergency procedure")
        # "other" falls through to normal flow

        if needs_role_clarification(text):
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
        text_lower_check = text.lower()
        detected_language = detect_language(text_lower_check)

        # 1. Use Gemini to detect the date and Canton via Structured JSON Output
        extraction_prompt = f"""
                Analyze this user request: "{text}"
                The current date is: {date.today().isoformat()}

                Extract the specific date and the Swiss Canton mentioned.
                Switzerland has 26 Cantons with these 2-letter codes: 
                AG, AR, AI, BL, BS, BE, FR, GE, GL, GR, JU, LU, NE, NW, OW, SG, SH, SZ, SO, TG, TI, UR, VD, VS, ZH, ZG.

                Rules:
                - If no Canton is explicitly mentioned, default to "BS" (Basel-Stadt).
                - If no year is mentioned, default to the current year.
                - Calculate relative dates (like "tomorrow") based on the current date.
                """

        # Using types.Schema to properly trigger the 'parsed' object in google.genai
        extraction_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "date": types.Schema(type=types.Type.STRING, description="YYYY-MM-DD format"),
                "canton": types.Schema(type=types.Type.STRING, description="2-letter Canton code")
            },
            required=["date", "canton"]
        )

        try:
            extraction_response = generate_with_backoff(
                prompt_entered=extraction_prompt,
                model_name="gemini-2.5-flash",
                config_type=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    response_schema=extraction_schema,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
            )

            # Safely access the natively parsed object (solves parsed=None issue)
            if extraction_response.parsed:
                parsed_obj = extraction_response.parsed
                # Handles both dictionary and object formats depending on GenAI internal parsing
                date_str = parsed_obj.get("date") if isinstance(parsed_obj, dict) else getattr(parsed_obj, "date", None)
                canton_code = parsed_obj.get("canton", "BS") if isinstance(parsed_obj, dict) else getattr(parsed_obj, "canton", "BS")
            else:
                extracted_data = json.loads(str(extraction_response.text))
                date_str = extracted_data.get("date")
                canton_code = extracted_data.get("canton", "BS") # Defaulting to Canton BS

            canton_to_check_for_holiday = canton_code if canton_code in VALID_CANTONS else "BS"
            date_to_check_for_holiday = datetime.strptime(str(date_str), "%Y-%m-%d").date()

        except Exception as e:
            print(f"[BRAIN ERROR] Could not extract date and Canton via Gemini: {e}")
            error_msg = translate_text("I couldn't understand the exact date or Canton you're asking about.",
                                            target_lang=detected_language, source_lang="en")
            return {"error": error_msg}

        # 2. Check the OpenHolidays API
        holiday_checker = SwissHolidayChecker(language=detected_language)

        try:
            holiday_info = holiday_checker.get_holiday(date_to_check_for_holiday, canton_to_check_for_holiday)
            formatted_date = date_to_check_for_holiday.strftime('%Y-%m-%d')

            if holiday_info:
                english_answer = f"Yes, {formatted_date} is a holiday in {canton_to_check_for_holiday}: {holiday_info.name}."
            else:
                english_answer = f"No, {formatted_date} is NOT a holiday in {canton_to_check_for_holiday}."

            holiday_answer = translate_text(english_answer, target_lang=detected_language, source_lang="en")
            print(f"[BRAIN] Holiday answer: {holiday_answer}")
            return {"answer": holiday_answer, "source": "OpenHolidays API call."}

        except Exception as e:
            print(f"[BRAIN ERROR] OpenHolidays API request failed: {e}")
            holiday_answer = translate_text("I'm sorry, I couldn't fetch the holiday data at this moment.",
                                            target_lang=detected_language, source_lang="en")
            return {
                "answer": holiday_answer,
                "source": "OpenHolidays API call."
            }

    elif intent == "expense":
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
        Input:  text: str — sanitized employee question
        Output: tuple(dict, str) — (result, tool_used)

    Args:
        text: the employee's sanitized question

    Returns:
        tuple: (result dict, tool_used str)
    """
    user_lang = "en"
    try:
        # Step 1: Detect language
        user_lang = detect_language(text)

        # Step 2: Convert text to English
        text_in_english = translate_text(text, "en", user_lang)
        print("step 2 done")

        # Step 3: Classify intent
        intent = classify_intent(text_in_english)
        print("step 3 done")

        # Step 4: Dispatch
        result = dispatch(intent, text_in_english)
        print("step 4 done")

        # Step 5: Convert answer back to user's language if needed
        if "answer" in result:
            result["answer"] = translate_text(result["answer"], user_lang, "en")
        print("step 5 done")

        tool_used = f"{intent}_tool"
        return result, tool_used

    except Exception as e:
        error_message = "Something went wrong. Please contact HR directly."
        error_message_in_user_lang = translate_text(error_message, user_lang, "en")
        return {
            "error": error_message_in_user_lang
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
        response = generate_with_backoff(
            prompt_entered=prompt,
            model_name="gemini-2.5-flash",
            config_type=types.GenerateContentConfig(automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        )
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

        response = generate_with_backoff(
            prompt_entered=prompt,
            model_name="gemini-2.5-flash",
            config_type=types.GenerateContentConfig(automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        )
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