"""
GreenLeaf Logistics - Expense Validation Tool
=============================================
Reliability-first version.

Design priorities:
- Never auto-approve a suspicious beverage if alcohol cannot be ruled out safely
- Deterministic rules first
- AI used as a backup for ambiguous drink-like cases
- Fail safe: ambiguous or unverified beverage cases go to manual review

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

SOURCE_LABEL = "GreenLeaf Handbook — Expense Policy"

AMOUNT_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:chf|francs?|fr\.?)",
    re.IGNORECASE
)

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
    "mojito",
    "pina colada",
    "piña colada",
    "bloody mary",
    "moscow mule",
    "margarita",
    "negroni",
    "old fashioned",
    "cosmopolitan",
    "daiquiri",
    "spritz",
    "gin tonic",
    "gin and tonic",
    "cuba libre",
    "b52",
    "b-52",
    "green mexican",
    "green mexicain",
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
    "chivas regal",
    "monkey shoulder",
    "obolon",
    "rosé",
    "rose wine",
    "grolsch",
]

# Generic phrases that explicitly mean "no alcohol"
NON_ALCOHOLIC_PATTERNS = [
    "didnt drink alcohol",
    "didn't drink alcohol",
    "did not drink alcohol",
    "we didnt drink alcohol",
    "we didn't drink alcohol",
    "we did not drink alcohol",
    "no alcohol",
    "without alcohol",
    "non-alcoholic",
    "non alcoholic",
    "alcohol-free",
    "alcohol free",
    "0.0%",
    "0%",
]

CLIENT_KEYWORDS = [
    "client",
    "customer",
    "guest",
    "prospect",
    "business partner",
    "external client",
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
    "what can be expensed",
]

SAFE_MEAL_WORDS = {
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
    "soup",
    "rice",
    "steak",
    "fish",
    "chicken",
    "dessert",
}

SUSPICIOUS_DRINK_WORDS = [
    "drink",
    "drank",
    "bar",
    "pub",
    "bottle",
    "glass",
    "shot",
    "cocktail",
    "aperitif",
    "digestif",
]

# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def extract_amount(text: str):
    """
    Extract CHF-like amount from text.
    Returns float if found, otherwise None.
    """
    match = AMOUNT_RE.search(text)
    return float(match.group(1)) if match else None


def looks_like_policy_question(text: str) -> bool:
    """
    Detect whether the user is asking about expense policy
    instead of asking to validate a specific expense.
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in POLICY_KEYWORDS)


def answer_expense_policy(text: str) -> dict:
    """
    Handles general expense policy questions.
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
            "source": SOURCE_LABEL,
        }

    if "limit" in text_lower or "maximum" in text_lower or "35" in text_lower:
        return {
            "answer": "Client meals are reimbursable up to a maximum of 35 CHF per person.",
            "source": SOURCE_LABEL,
        }

    if "alcohol" in text_lower:
        return {
            "answer": "Alcohol is strictly non-reimbursable under the GreenLeaf expense policy.",
            "source": SOURCE_LABEL,
        }

    return {
        "answer": (
            "I can help with expense rules, reimbursement limits, alcohol restrictions, "
            "and receipt submission via ScanPro."
        ),
        "source": SOURCE_LABEL,
    }


def manual_review_response(reason: str) -> dict:
    """
    Standard response for ambiguous cases.
    Reliability-first: ambiguous drink cases should never auto-approve.
    """
    return {
        "answer": (
            f"⚠️ I could not safely validate this expense automatically.\n"
            f"• {reason}\n\n"
            "Please provide more detail or contact Finance / HR if needed."
        ),
        "source": SOURCE_LABEL,
    }


def contains_non_alcoholic_pattern(text: str) -> bool:
    """
    Detect explicit generic non-alcoholic phrasing.
    This should override only generic 'alcohol' mentions,
    not specific drink names like wine, beer, mojito, etc.
    """
    text_lower = text.lower()
    return any(pattern in text_lower for pattern in NON_ALCOHOLIC_PATTERNS)


def contains_specific_alcohol_keywords(text: str) -> bool:
    """
    Deterministic alcohol detection excluding the generic word 'alcohol'.
    This prevents false positives in phrases like:
    - we didn't drink alcohol
    - no alcohol
    """
    text_lower = text.lower()

    specific_keywords = [kw for kw in ALCOHOL_KEYWORDS if kw != "alcohol"]

    for keyword in specific_keywords:
        if " " in keyword:
            if keyword in text_lower:
                return True
        else:
            if re.search(rf"\b{re.escape(keyword)}\b", text_lower):
                return True

    return False


def contains_generic_alcohol_word(text: str) -> bool:
    """
    Detect the standalone generic word 'alcohol'.
    """
    return re.search(r"\balcohol\b", text.lower()) is not None


def contains_fuzzy_alcohol_keywords(text: str) -> bool:
    """
    Detect likely misspellings of known alcohol words/brands.

    Examples:
    - guiness -> guinness
    - screwdirver -> screwdriver (via AI route if not in keywords)
    """
    words = re.findall(r"\b[\w'-]+\b", text.lower())
    single_word_keywords = [
        kw for kw in ALCOHOL_KEYWORDS
        if " " not in kw and kw != "alcohol"
    ]

    for word in words:
        match = get_close_matches(word, single_word_keywords, n=1, cutoff=0.88)
        if match:
            return True

    return False


def has_client_context(text: str) -> bool:
    """
    Check whether an external business contact is mentioned.
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in CLIENT_KEYWORDS)


def looks_alcohol_suspicious(text: str) -> bool:
    """
    Identify general drink-like wording that should trigger AI audit.
    """
    text_lower = text.lower()
    return any(word in text_lower for word in SUSPICIOUS_DRINK_WORDS)


def extract_named_item_phrase(text: str):
    """
    Extract a named consumable item from common expense phrasing.
    Supports drinks/brands/cocktails, including alphanumeric names like B52.
    """
    text_lower = text.lower()

    patterns = [
        r"\bi had (?:a|an)\s+([a-zA-Z0-9][a-zA-Z0-9' -]{1,40})\s+with\s+(?:a\s+)?(?:external\s+)?(?:client|customer|guest|prospect|business partner)\b",
        r"\bcan i expense (?:a|an)\s+([a-zA-Z0-9][a-zA-Z0-9' -]{1,40})\s+with\s+(?:a\s+)?(?:external\s+)?(?:client|customer|guest|prospect|business partner)\b",
        r"\bi ordered (?:a|an)\s+([a-zA-Z0-9][a-zA-Z0-9' -]{1,40})\s+with\s+(?:a\s+)?(?:external\s+)?(?:client|customer|guest|prospect|business partner)\b",
        r"\bi spent \d+(?:\.\d+)?\s*(?:chf|francs?|fr\.?)\s+on\s+([a-zA-Z0-9][a-zA-Z0-9' -]{1,40})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip()

    return None


def is_safe_meal_phrase(phrase: str) -> bool:
    """
    Check whether the extracted phrase is clearly a meal item.
    """
    if not phrase:
        return False

    words = set(re.findall(r"\b[\w'-]+\b", phrase.lower()))
    return bool(words & SAFE_MEAL_WORDS)


def looks_like_ambiguous_drink_case(text: str) -> bool:
    """
    Returns True when:
    - message has client context
    - amount exists
    - text appears to reference a named consumable item
    - item is not clearly a safe meal
    """
    if extract_amount(text) is None:
        return False

    if not has_client_context(text):
        return False

    phrase = extract_named_item_phrase(text)
    if not phrase:
        return False

    if is_safe_meal_phrase(phrase):
        return False

    return True


def contains_meal_plus_drink_pattern(text: str) -> bool:
    """
    Detect patterns like:
    - I had lunch with an external client with a B52 for 30 CHF
    - I had dinner with a customer with a green mexicain for 30 CHF
    """
    text_lower = text.lower()

    if not any(meal in text_lower for meal in ["lunch", "dinner", "breakfast", "meal"]):
        return False

    pattern = (
        r"\b(?:lunch|dinner|breakfast|meal)\b.*?"
        r"\bwith\s+(?:an?\s+)?(?:external\s+)?(?:client|customer|guest|prospect|business partner)\b.*?"
        r"\bwith\s+(?:a|an)\s+([a-zA-Z0-9][a-zA-Z0-9' -]{1,40})\b"
    )

    match = re.search(pattern, text_lower)
    if not match:
        return False

    candidate = match.group(1).strip()
    if candidate in SAFE_MEAL_WORDS:
        return False

    return True


@lru_cache(maxsize=256)
def check_alcohol_with_ai(text: str):
    """
    Cached AI alcohol detector.

    Return values:
        True  -> alcohol detected
        False -> no alcohol detected
        None  -> AI service unavailable or unclear result
    """
    prompt = (
        f"You are a strict expense auditor. Analyze this expense text: '{text}'. "
        "Decide whether the item mentioned is alcoholic. "
        "Treat cocktails, spirits, wine, beer, liqueurs, and alcohol brands as alcoholic. "
        "If the message is ambiguous or you are not sure, answer UNCLEAR. "
        "Reply with exactly one word only: YES, NO, or UNCLEAR."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        result = response.text.strip().upper()
        print(f"DEBUG [AI Audit]: Alcohol detected? {result}")

        if result == "YES":
            return True
        if result == "NO":
            return False
        return None

    except Exception as e:
        print(f"CRITICAL AI ERROR: {e}")
        return None


# ─────────────────────────────────────────────
# MAIN FUNCTION
# ─────────────────────────────────────────────

def validate_expense(text: str) -> dict:
    """
    Reliability-first flow:
    1. Policy question check
    2. Amount extraction
    3. Client context check
    4. Explicit non-alcoholic patterns
    5. Exact alcohol keywords
    6. Fuzzy alcohol matching
    7. AI audit for ambiguous drink-like cases
    8. Manual review instead of approval when uncertainty remains
    """
    text_lower = text.lower()

    # Step 0 — expense policy questions
    if looks_like_policy_question(text):
        return answer_expense_policy(text)

    # Step 1 — amount extraction
    amount = extract_amount(text)
    if amount is None:
        return manual_review_response(
            "Could not detect the expense amount in CHF. "
            "Please include the amount, for example: 'Lunch with a client for 20 CHF'."
        )

    # Step 2 — client context
    has_client = has_client_context(text)

    # Step 3 — explicit non-alcoholic phrasing
    explicit_non_alcoholic = contains_non_alcoholic_pattern(text)

    # Step 4 — exact alcohol detection
    specific_keyword_alcohol = contains_specific_alcohol_keywords(text)

    # Generic 'alcohol' only counts if there is no explicit negation
    generic_alcohol_word = False
    if not explicit_non_alcoholic:
        generic_alcohol_word = contains_generic_alcohol_word(text)

    keyword_alcohol = specific_keyword_alcohol or generic_alcohol_word

    # Step 5 — fuzzy alcohol detection
    fuzzy_alcohol = False
    if not explicit_non_alcoholic and not keyword_alcohol:
        fuzzy_alcohol = contains_fuzzy_alcohol_keywords(text)

    # Step 6 — AI audit for ambiguous drink-like cases
    ai_alcohol = False
    ai_checked = False
    if not explicit_non_alcoholic and not keyword_alcohol and not fuzzy_alcohol:
        if (
            looks_alcohol_suspicious(text)
            or looks_like_ambiguous_drink_case(text)
            or contains_meal_plus_drink_pattern(text)
        ):
            ai_checked = True
            ai_alcohol = check_alcohol_with_ai(text)

    has_alcohol = keyword_alcohol or fuzzy_alcohol or (ai_alcohol is True)

    # Step 7 — apply handbook rules
    reasons = []

    if amount > 35:
        reasons.append("Amount is above the 35 CHF limit")

    if has_alcohol:
        if specific_keyword_alcohol or generic_alcohol_word:
            reasons.append("Receipt contains alcohol or a known alcohol brand")
        elif fuzzy_alcohol:
            reasons.append("Receipt likely contains alcohol (matched against known alcohol terms/brands)")
        else:
            reasons.append("Receipt contains alcohol (detected by AI audit)")

    if not has_client:
        reasons.append(
            "Expenses must be associated with an external client, customer, guest, prospect, or business partner"
        )

    # Step 8 — safety gate
    if not has_alcohol and has_client:
        ambiguous_drink_case = (
            looks_like_ambiguous_drink_case(text)
            or contains_meal_plus_drink_pattern(text)
        )

        if ambiguous_drink_case:
            if ai_checked and ai_alcohol is None:
                return manual_review_response(
                    "This appears to be a named beverage or drink-like item, but I could not safely determine whether it contains alcohol."
                )

            if not ai_checked:
                return manual_review_response(
                    "This appears to be a named beverage or drink-like item, and I cannot safely auto-approve it without confirming whether it contains alcohol."
                )

    # Step 9 — final decision
    if not reasons:
        return {
            "answer": "✅ Approved based on the provided information. Please submit the receipt via the ScanPro app.",
            "source": SOURCE_LABEL,
        }

    reason_str = "\n• ".join(reasons)

    return {
        "answer": (
            f"❌ Rejected based on the provided information:\n"
            f"• {reason_str}\n\n"
            "Please submit receipts via the ScanPro app."
        ),
        "source": SOURCE_LABEL,
    }