"""
GreenLeaf Logistics - Expense Validation Tool
=============================================
This module contains the business logic for expense validation.

Design approach:
- Use deterministic handbook rules first (amount limit, client presence, alcohol keywords)
- Use fuzzy matching for common misspellings of alcohol words/brands
- Use AI only as a backup semantic detector for suspicious alcohol mentions
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
"""

import os
import re
from functools import lru_cache
from difflib import get_close_matches

from google import genai
from dotenv import load_dotenv

# ─────────────────────────────────────────────
# INITIALIZATION
# ─────────────────────────────────────────────

load_dotenv()

client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"),
    http_options={"api_version": "v1"}
)

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

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
    "martini",
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
    "chivas",
    "monkey shoulder",
    "obolon",
    "rosé",
    "rose wine",
]

CLIENT_KEYWORDS = [
    "client",
    "customer",
    "guest",
    "prospect",
    "business partner"
]

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

SUSPICIOUS_DRINK_WORDS = [
    "drink",
    "drank",
    "bar",
    "pub",
    "bottle",
    "glass",
    "shot",
    "aperitif",
    "digestif"
]

MEAL_WORDS = {
    "lunch",
    "dinner",
    "breakfast",
    "meal",
    "sandwich",
    "salad",
    "pizza",
    "pasta",
    "burger",
    "snack",
    "coffee"
}

SOURCE_LABEL = "GreenLeaf Handbook — Expense Policy"

AMOUNT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:chf|francs?|fr\.?)",
    re.IGNORECASE
)

# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def contains_alcohol_keywords(text: str) -> bool:
    """
    Deterministic alcohol detection.

    Single-word keywords use word boundaries to reduce false positives.
    Multi-word brands use substring matching.
    """
    text_lower = text.lower()

    for keyword in ALCOHOL_KEYWORDS:
        if " " in keyword:
            if keyword in text_lower:
                return True
        else:
            if re.search(rf"\b{re.escape(keyword)}\b", text_lower):
                return True

    return False


def contains_fuzzy_alcohol_keywords(text: str) -> bool:
    """
    Detect likely misspellings of known alcohol words/brands.

    Examples:
    - guiness -> guinness
    - martiny -> martini

    Uses only single-word alcohol keywords.
    """
    words = re.findall(r"\b[\w'-]+\b", text.lower())
    single_word_keywords = [kw for kw in ALCOHOL_KEYWORDS if " " not in kw]

    for word in words:
        match = get_close_matches(word, single_word_keywords, n=1, cutoff=0.88)
        if match:
            return True

    return False


def looks_alcohol_suspicious(text: str) -> bool:
    """
    Decide whether the text is suspicious enough to justify an AI alcohol audit.

    This keeps the tool fast:
    - obvious alcohol brands/keywords are handled deterministically
    - AI is called only for ambiguous drink-like wording
    """
    text_lower = text.lower()
    return any(word in text_lower for word in SUSPICIOUS_DRINK_WORDS)


def looks_like_unknown_drink_phrase(text: str) -> bool:
    """
    Detect suspicious beverage-like phrasing such as:
    - I had a Monkey Shoulder with a client
    - I had an Obolon with customer
    - I had a martiny with client

    Used to trigger AI fallback when deterministic rules miss.
    """
    text_lower = text.lower()

    suspicious_patterns = [
        r"\bi had (?:a|an)\s+([a-zA-Z][a-zA-Z' -]{2,30})\s+with\s+(?:a\s+)?(?:client|customer|guest|prospect|business partner)\b",
        r"\bi spent \d+(?:\.\d+)?\s*(?:chf|francs?|fr\.?)\s+on\s+([a-zA-Z][a-zA-Z' -]{2,30})\b",
    ]

    for pattern in suspicious_patterns:
        match = re.search(pattern, text_lower)
        if match:
            phrase = match.group(1).strip()
            if phrase not in MEAL_WORDS:
                return True

    return False


@lru_cache(maxsize=256)
def check_alcohol_with_ai(text: str):
    """
    Cached AI alcohol detector.

    Return values:
        True  -> alcohol detected
        False -> no alcohol detected
        None  -> AI service unavailable / failed
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
        print(f"CRITICAL AI ERROR: {e}")
        return None


def extract_amount(text: str):
    """
    Extract CHF-like amount from the text.

    Supported examples:
    - 20 CHF
    - 20 chf
    - 20 francs
    - 20 fr.

    Returns:
        float if found, otherwise None
    """
    match = AMOUNT_RE.search(text)
    return float(match.group(1)) if match else None


def looks_like_policy_question(text: str) -> bool:
    """
    Detect whether the user is asking about expense policy,
    rather than asking to validate a specific expense claim.
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in POLICY_KEYWORDS)


def answer_expense_policy(text: str) -> dict:
    """
    Handles general expense-policy questions that do not need
    approval/rejection logic.
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

    if (
        "alcohol" in text_lower
        or "wine" in text_lower
        or "beer" in text_lower
        or "whisky" in text_lower
        or "whiskey" in text_lower
    ):
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
    3. Detect alcohol (keyword → fuzzy → AI fallback only if suspicious)
    4. Check client presence
    5. Apply handbook rules
    6. Return structured response
    """
    text_lower = text.lower()

    # Step 0 — detect expense policy questions
    if looks_like_policy_question(text):
        return answer_expense_policy(text)

    # Step 1 — extract amount
    amount = extract_amount(text)

    if amount is None:
        return manual_review_response(
            "Could not detect the expense amount in CHF. "
            "Please include the amount, for example: 'Lunch with a client for 20 CHF'."
        )

    # Step 2 — deterministic alcohol detection first
    keyword_alcohol = contains_alcohol_keywords(text)
    fuzzy_alcohol = contains_fuzzy_alcohol_keywords(text)

    # Step 3 — AI alcohol detection only when needed
    ai_alcohol = False
    if not keyword_alcohol and not fuzzy_alcohol:
        if looks_alcohol_suspicious(text) or looks_like_unknown_drink_phrase(text):
            ai_alcohol = check_alcohol_with_ai(text)

    has_alcohol = keyword_alcohol or fuzzy_alcohol or (ai_alcohol is True)

    # Step 4 — client / external business contact detection
    has_client = any(keyword in text_lower for keyword in CLIENT_KEYWORDS)

    # Step 5 — apply handbook rules
    reasons = []

    if amount > 35:
        reasons.append("Amount is above the 35 CHF limit")

    if has_alcohol:
        if keyword_alcohol:
            reasons.append("Receipt contains alcohol or a known alcohol brand")
        elif fuzzy_alcohol:
            reasons.append("Receipt likely contains alcohol (matched against known alcohol terms/brands)")
        else:
            reasons.append("Receipt contains alcohol (detected by AI audit)")
    elif ai_alcohol is None:
        return manual_review_response(
            "Alcohol audit service is unavailable, so I cannot safely confirm whether the expense contains alcohol."
        )

    if not has_client:
        reasons.append(
            "Expenses must be associated with an external client, customer, guest, prospect, or business partner"
        )

    # Step 6 — final decision
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
            "Please submit the receipt via the ScanPro app."
        ),
        "source": SOURCE_LABEL
    }