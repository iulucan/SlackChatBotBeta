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
from src.tools.policy_tool import query_handbook

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
# TOOL DISPATCH
# ─────────────────────────────────────────────

def dispatch(intent: str, text: str) -> dict:
    """
    Calls the correct tool based on the classified intent.

    Interface contract (do not change):
        Input:  intent: str, text: str
        Output: {"answer": str, "source": str} or {"error": str}

    Args:
        intent: classified intent — "policy", "holiday", "expense"
        text:   the employee's sanitised question

    Returns:
        dict with answer and source, or error message
    """
    if intent == "policy":
        return query_handbook(text)

    elif intent == "holiday":
        # holiday_tool.py coming
        return {
            "answer": "Holiday checking is coming. For now please check the Basel-Stadt cantonal calendar.",
            "source": "GreenLeaf Bot — feature in development"
        }

    elif intent == "expense":
        # expense_tool.py coming
        return {
            "answer": "Expense validation is coming. For now please contact Beat Müller directly.",
            "source": "GreenLeaf Bot — feature in development"
        }

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

    Interface contract (do not change):
        Input:  text: str — sanitised employee question
        Output: tuple(dict, str) — (result, tool_used)

    Args:
        text: the employee's sanitised question

    Returns:
        tuple: (result dict, tool_used str)
    """
    try:
        # Step 1 — classify intent
        intent = classify_intent(text)

        # Step 2 — dispatch to correct tool
        result = dispatch(intent, text)

        tool_used = f"{intent}_tool"
        return result, tool_used

    except Exception as e:
        print(f"[BRAIN ERROR] respond() failed: {e}")
        return {
            "error": "Something went wrong. Please contact HR directly."
        }, "unknown"


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