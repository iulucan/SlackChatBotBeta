"""
GreenLeaf Logistics - Expense Validation Tool
=============================================
This module contains the business logic for expense validation.

Design approach:
- Use deterministic handbook rules first (amount limit, client presence, alcohol keywords)
- Use AI as a backup semantic detector for alcohol mentions that are not caught by keywords
- Fail safely: if AI alcohol audit is unavailable, do NOT automatically approve

Handbook rules implemented:
- Client lunches are reimbursable only if at least one external client is present
- Maximum 35 CHF per person
- Alcohol is strictly non-reimbursable
- Receipts must be submitted via the ScanPro app

This module returns Slack-ready strings for the interface layer.
"""

import os
from google import genai
from dotenv import load_dotenv

# Load environment variables from the project .env file
load_dotenv()

# Initialize Gemini client
# We use API version v1 and a current Flash model for stable generation calls.
client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"),
    http_options={"api_version": "v1"}
)

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


def contains_alcohol_keywords(text):
    """
    Fast deterministic alcohol detection.

    Returns:
        True if the text contains an alcohol-related keyword or brand
        False otherwise
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in ALCOHOL_KEYWORDS)


def check_alcohol_with_ai(text):
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
    We do NOT use AI as the only detector. Deterministic keywords are checked first.
    """

    prompt = (
        f"You are a strict expense auditor. Analyze this receipt text: '{text}'. "
        "Does it mention any alcohol, beer, wine, spirits, liquor, whiskey, whisky, vodka, cocktails, "
        "or alcohol brands? "
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
        # we return None, not False, so the caller can reject safely instead of blindly approving.
        print(f"CRITICAL AI ERROR: {e}")
        return None


def answer_expense_policy(text):
    """
    Handles general expense-policy questions that do not need amount calculation.

    Example:
    - How do I submit receipts?
    - What app do I use for receipts?
    """
    text_lower = text.lower()

    if (
        "receipt" in text_lower
        or "receipts" in text_lower
        or "submit" in text_lower
        or "submission" in text_lower
        or "scanpro" in text_lower
    ):
        return (
            'All receipts must be scanned using the "ScanPro" app. '
            "We no longer accept physical paper receipts or photos of crumpled paper."
        )

    return (
        "I can help with expense rules, reimbursement limits, alcohol restrictions, "
        "and receipt submission via ScanPro."
    )


def validate_expense(text, amount):
    """
    Main entry point for expense validation.

    Validation logic:
    1. Check alcohol deterministically via keyword list
    2. If not found, run AI alcohol audit as backup
    3. Check whether an external business contact is present
    4. Check amount limit
    5. Return approval or rejection with reasons

    Args:
        text (str): original user query
        amount (float): extracted CHF amount

    Returns:
        str: formatted response ready for Slack
    """
    text_lower = text.lower()

    # Step 1: deterministic alcohol detection
    keyword_alcohol = contains_alcohol_keywords(text)

    # Step 2: AI alcohol detection only if keyword detector found nothing
    # This avoids unnecessary AI calls and makes brand detection more reliable.
    ai_alcohol = False
    if not keyword_alcohol:
        ai_alcohol = check_alcohol_with_ai(text)

    # Step 3: combine both alcohol signals
    # If keyword_alcohol is True, we already know the answer deterministically.
    has_alcohol = keyword_alcohol or (ai_alcohol is True)

    # Step 4: check whether the expense includes an external business contact
    has_client = any(keyword in text_lower for keyword in CLIENT_KEYWORDS)

    # Step 5: collect rejection reasons
    reasons = []

    # Handbook rule: maximum 35 CHF per person
    if amount > 35:
        reasons.append("Amount is above the 35 CHF limit")

    # Handbook rule: alcohol is never reimbursable
    if has_alcohol:
        if keyword_alcohol:
            reasons.append("Receipt contains alcohol or a known alcohol brand")
        else:
            reasons.append("Receipt contains alcohol (detected by AI audit)")
    elif ai_alcohol is None:
        # Important fail-safe:
        # if deterministic detection found nothing and AI failed,
        # we reject safely instead of approving without a valid alcohol audit.
        reasons.append("Alcohol audit service unavailable — cannot safely approve expense")

    # Handbook rule: must involve an external client / equivalent business contact
    if not has_client:
        reasons.append("Expenses must be associated with a client or guest")

    # Final decision
    if not reasons:
        return "✅ Approved! Please use our exclusive scanning app as stated in the handbook."

    reason_str = "\n• ".join(reasons)
    return (
        f"❌ Rejected:\n• {reason_str}\n\n"
        "Note: Please use our exclusive scanning app as stated in the handbook."
    )