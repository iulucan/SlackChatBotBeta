"""
GreenLeaf Logistics - Expense Validation Tool
=============================================
This module contains the business logic for expense validation.

Design approach:
- Use deterministic handbook rules first (amount limit, client presence, alcohol keywords)
- Use AI only as a backup semantic detector for alcohol mentions not caught by keywords
- Fail safely: if the case is ambiguous, do NOT auto-approve
- Distinguish between:
    1. expense policy questions
    2. actual expense validation requests

Handbook rules implemented:
- Client lunches are reimbursable only if at least one external client is present
- Maximum 35 CHF per person
- Alcohol is strictly non-reimbursable
- Receipts must be submitted via the ScanPro app

Integration contract:
- Called by brain.py
- Input: text (str) — full user message
- Output: dict with "answer" and "source"

Why this structure:
- Deterministic logic is easier to test and explain
- AI is used only as a backup detector, not as the main decision-maker
- User-facing answers should be structured and Slack-ready
"""

import os
import re
from google import genai
from dotenv import load_dotenv

# ─────────────────────────────────────────────
# INITIALIZATION
# ─────────────────────────────────────────────

# Load environment variables from the project .env file
load_dotenv()

# Initialize Gemini client
# We use API version v1 and a current Flash model for stable generation calls.
client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"),
    http_options={"api_version": "v1"}
)

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# Deterministic alcohol dictionary
# Why this exists:
# AI is helpful, but business-critical policy checks should not rely on AI alone.
# This list catches common alcohol categories, brands, and likely misspellings.
ALCOHOL_KEYWORDS = [
    "alcohol",
    "beer",
    "wine",
    "whisky",
    "whiskey",
    "wiskey",
    "vodka",
    "rum",
    "gin",
    "tequila",
    "champagne",
    "cider",
    "cocktail",
    "liquor",
    "spirits",
    "brandy",
    "bourbon",
    "scotch",
    "lager",
    "ale",
    "prosecco",
    "aperol",
    "campari",
    "jack daniels",
    "jack daniel's",
    "jim beam",
    "johnnie walker",
    "johnny walker",
    "absolut",
    "smirnoff",
    "bacardi",
    "hennessy",
    "heineken",
    "corona",
    "guinness",
    "carlsberg",
    "jagermeister",
    "jägermeister",
    "moet",
    "moët",
    "chivas"
]

# Allowed external-party keywords for reimbursable business meals
CLIENT_KEYWORDS = [
    "client",
    "customer",
    "guest",
    "prospect",
    "business partner"
]

# Keywords that usually indicate an expense-policy / handbook question,
# not a specific expense claim that needs approval/rejection logic.
POLICY_KEYWORDS = [
    "policy",
    "rule",
    "rules",
    "limit",
    "maximum",
    "how do i submit",
    "how can i submit",
    "how to submit",
    "submit receipt",
    "submit receipts",
    "receipt submission",
    "receipt",
    "receipts",
    "scanpro",
    "what app",
    "which app",
    "can i expense alcohol",
    "what can be expensed"
]

SOURCE_LABEL = "GreenLeaf Handbook — Expense Policy"

# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def contains_alcohol_keywords(text: str) -> bool:
    """
    Fast deterministic alcohol detection.

    Returns:
        True if the text contains an alcohol-related keyword or brand
        False otherwise
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in ALCOHOL_KEYWORDS)


def check_alcohol_with_ai(text: str):
    """
    Backup AI alcohol detector.

    Why it exists:
    - catches less obvious semantic mentions
    - helps detect alcohol references not covered by keyword list

    Return values:
        True  -> alcohol detected
        False -> no alcohol detected
        None  -> AI service unavailable / failed

    Important:
    We do NOT use AI as the only detector.
    Deterministic keywords are checked first.
    """
    prompt = (
        f"You are a strict expense auditor. Analyze this receipt text: '{text}'. "
        "Does it mention any alcohol, beer, wine, spirits, liquor, whiskey, whisky, "
        "vodka, cocktails, or alcohol brands? "
        "Answer ONLY with the word 'YES' or 'NO'."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        result = response.text.strip().upper()
        print(f"DEBUG [AI Audit]: Alcohol detected? {result}")

        return "YES" in result

    except Exception as e:
        # Fail-safe behavior:
        # we return None, not False, so the caller can handle ambiguity safely.
        print(f"CRITICAL AI ERROR: {e}")
        return None


def extract_amount(text: str) -> float:
    """
    Extract amount from expense text.

    Supported examples:
    - 20 CHF
    - 20 chf
    - 20 francs
    - 20 fr.

    Why CHF-aware regex:
    We should not match unrelated numbers such as:
    - "I have 3 receipts for a 20 CHF lunch"
    - "US-07 expense request"

    Returns:
        float amount, or 0.0 if no CHF-like amount is found
    """
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:chf|francs?|fr\.?)",
        text,
        re.IGNORECASE
    )
    return float(match.group(1)) if match else 0.0


def looks_like_policy_question(text: str) -> bool:
    """
    Detect whether the user is asking about expense policy,
    rather than asking to validate a specific expense.

    This helps us avoid running approval/rejection logic on
    general handbook questions.
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in POLICY_KEYWORDS)


def answer_expense_policy(text: str) -> dict:
    """
    Handles general expense-policy questions that do not need
    amount calculation or approval logic.

    Examples:
    - How do I submit receipts?
    - What app do I use for receipts?
    - What is the maximum reimbursable amount?
    - Can alcohol be expensed?
    """
    text_lower = text.lower()

    if (
        "receipt" in text_lower
        or "receipts" in text_lower
        or "submit" in text_lower
        or "submission" in text_lower
        or "scanpro" in text_lower
        or "app" in text_lower
    ):
        return {
            "answer": (
                'All receipts must be scanned using the "ScanPro" app. '
                "We no longer accept physical paper receipts or photos of crumpled paper."
            ),
            "source": SOURCE_LABEL
        }

    if "limit" in text_lower or "maximum" in text_lower or "35" in text_lower:
        return {
            "answer": "Client meals are reimbursable up to a maximum of 35 CHF per person.",
            "source": SOURCE_LABEL
        }

    if "alcohol" in text_lower or "wine" in text_lower or "beer" in text_lower:
        return {
            "answer": "Alcohol is strictly non-reimbursable under the GreenLeaf expense policy.",
            "source": SOURCE_LABEL
        }

    return {
        "answer": (
            "I can help with expense rules, reimbursement limits, alcohol restrictions, "
            "and receipt submission via ScanPro."
        ),
        "source": SOURCE_LABEL
}


def manual_review_response(reason: str) -> dict:
    """
    Standard response for ambiguous cases where the tool cannot
    safely auto-approve or auto-reject.

    This is safer than forcing an AI-based yes/no decision.
    """
    return {
        "answer": (
            f"⚠️ I could not safely validate this expense automatically.\n"
            f"• {reason}\n\n"
            "Please provide more detail or contact Finance / HR if needed."
        ),
        "source": SOURCE_LABEL
    }

# ─────────────────────────────────────────────
# MAIN FUNCTION (CALLED BY BRAIN)
# ─────────────────────────────────────────────

def validate_expense(text: str) -> dict:
    """
    Main entry point for expense validation.

    Flow:
    1. Distinguish policy questions from validation requests
    2. Extract amount from text
    3. Detect alcohol (keyword → AI fallback)
    4. Check client presence
    5. Apply handbook rules
    6. Return structured response

    Returns:
        dict: {"answer": str, "source": str}
    """
    text_lower = text.lower()

    # Step 0 — detect expense policy questions
    # If the user is asking about rules/process, answer policy directly.
    if looks_like_policy_question(text):
        return answer_expense_policy(text)

    # Step 1 — extract amount
    amount = extract_amount(text)

    # Missing amount should not become an accidental approval.
    if amount == 0.0:
        return manual_review_response(
            "Could not detect the expense amount in CHF. "
            "Please include the amount, for example: 'Lunch with a client for 20 CHF'."
        )

    # Step 2 — alcohol detection
    # Deterministic logic first, AI only as backup.
    keyword_alcohol = contains_alcohol_keywords(text)

    ai_alcohol = False
    if not keyword_alcohol:
        ai_alcohol = check_alcohol_with_ai(text)

    has_alcohol = keyword_alcohol or (ai_alcohol is True)

    # Step 3 — client detection
    has_client = any(keyword in text_lower for keyword in CLIENT_KEYWORDS)

    # Step 4 — apply rules
    reasons = []

    # Rule: max 35 CHF
    if amount > 35:
        reasons.append("Amount is above the 35 CHF limit")

    # Rule: alcohol forbidden
    if has_alcohol:
        if keyword_alcohol:
            reasons.append("Receipt contains alcohol or a known alcohol brand")
        else:
            reasons.append("Receipt contains alcohol (detected by AI audit)")
    elif ai_alcohol is None:
        # AI failed and deterministic detector found nothing.
        # This is ambiguous: safer to ask for manual review than auto-approve.
        return manual_review_response(
            "Alcohol audit service is unavailable, so I cannot safely confirm whether the expense contains alcohol."
        )

    # Rule: must include client / external business contact
    if not has_client:
        reasons.append(
            "Expenses must be associated with an external client, customer, guest, prospect, or business partner"
        )

    # Step 5 — final decision
    if not reasons:
        return {
            "answer": "✅ Approved based on the provided information. Please submit the receipt via the ScanPro app.",
            "source": SOURCE_LABEL
        }

    reason_str = "\n• ".join(reasons)

    return {
        "answer": (
            f"❌ Rejected based on the provided information:\n"
            f"• {reason_str}\n\n"
            "Please submit receipts via the ScanPro app."
        ),
        "source": SOURCE_LABEL
    }