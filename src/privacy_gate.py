"""
privacy_gate.py — GreenLeaf Bot | Security & Privacy Filter
=============================================================
Acts as the first layer of defense for all incoming Slack messages.

Responsibilities:
    1. PII Masking  — mask names and employee IDs before any processing
    2. Block Filter — refuse sensitive queries (Wi-Fi, salary, etc.)
    3. Injection Guard — detect and block prompt injection attempts

Architecture position:
    app.py -> clean_input() -> is_blocked() -> brain.py -> tools

Compliance:
    Swiss FADP (nDSG): only masked text is logged or processed

Why Regex over NLP (spaCy / Presidio):
    - Zero dependencies, zero model download
    - 5-digit IDs and name patterns are predictable in this context
    - Sufficient accuracy for Sprint 1 scope
    - NLP can be added in a later sprint if needed

Sprint: Week 2 | Owner: Ibrahim (System Architect)
"""

import re

# ---------------------------------------------------------------------------
# PII MASKING
# ---------------------------------------------------------------------------

# Matches GreenLeaf employee IDs: exactly 6 consecutive digits
EMPLOYEE_ID_PATTERN = re.compile(r'\b\d{6}\b')

# Matches names introduced with common phrases
# Example: "My name is Beat Müller" -> "My name is [NAME]"
NAME_PHRASE_PATTERN = re.compile(
    r'(my name is|i am|i\'m|this is)\s+([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)*)',
    re.IGNORECASE
)

# Words excluded from name detection (months, days, locations, question words)
EXCLUDE_FROM_NAME_DETECTION = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
    "is", "are", "the", "a", "an", "my", "your", "his", "her", "our",
    "basel", "zurich", "geneva", "bern", "swiss", "switzerland",
    "greenleaf", "powerleaf", "how", "what", "when", "where", "why", "which"
}

# Matches standalone pairs of capitalized words (potential full names)
# Example: "Beat Müller asked" -> "[NAME] asked"
CAPITALIZED_NAME_PATTERN = re.compile(
    r'\b([A-ZÄÖÜ][a-zäöüß]+)\s+([A-ZÄÖÜ][a-zäöüß]+)\b'
)

# Matches email addresses
EMAIL_PATTERN = re.compile(r'\b[\w.-]+@[\w.-]+\.\w{2,}\b')


def clean_input(text: str) -> str:
    """
    Entry point for all incoming messages.
    Masks PII before any other component processes the text.

    Masking order:
        1. Email addresses     -> [EMAIL]
        2. Employee IDs        -> [ID]
        3. Named introductions -> [NAME]
        4. Capitalized pairs   -> [NAME] (excluding common words)

    Only the masked version is returned and logged.
    The original text is never stored or forwarded.
    """
    masked = text

    # Step 1 — Mask email addresses
    masked = EMAIL_PATTERN.sub('[EMAIL]', masked)

    # Step 2 — Mask 5-digit employee IDs
    masked = EMPLOYEE_ID_PATTERN.sub('[ID]', masked)

    # Step 3 — Mask names introduced with phrases ("My name is ...")
    masked = NAME_PHRASE_PATTERN.sub(lambda m: m.group(1) + ' [NAME]', masked)

    # Step 4 — Mask capitalized word pairs, skip common/excluded words
    def mask_name_pair(m):
        w1, w2 = m.group(1).lower(), m.group(2).lower()
        if w1 in EXCLUDE_FROM_NAME_DETECTION or w2 in EXCLUDE_FROM_NAME_DETECTION:
            return m.group(0)  # keep original — not a name
        return '[NAME]'

    masked = CAPITALIZED_NAME_PATTERN.sub(mask_name_pair, masked)

    # Log only the masked version — never the original
    if masked != text:
        print(f"[PRIVACY] Input masked before processing: {masked}")

    return masked


# ---------------------------------------------------------------------------
# BLOCK FILTER
# ---------------------------------------------------------------------------

BLOCKED_KEYWORDS = [
    # Network / IT security
    "wifi", "wi-fi", "password", "passwort",
    "mac address", "network key",
    # HR sensitive data
    "salary", "lohn", "gehalt", "payslip",
    "raise", "gehaltserhöhung"
]

# Prompt injection patterns — attempts to override bot instructions
INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "forget your instructions",
    "you are now",
    "act as if",
    "pretend you are",
    "disregard your",
    "new instructions:",
    "system prompt",
]


def is_blocked(query: str) -> bool:
    """
    Returns True if the query contains a blocked keyword
    or a prompt injection pattern. Check is case-insensitive.
    """
    query_lower = query.lower()

    for keyword in BLOCKED_KEYWORDS:
        if keyword in query_lower:
            return True

    for pattern in INJECTION_PATTERNS:
        if pattern in query_lower:
            return True

    return False


def get_block_message(query: str) -> str:
    """
    Returns a firm but professional refusal message.
    Redirects the user to the correct contact person.
    """
    query_lower = query.lower()

    if any(k in query_lower for k in ["wifi", "wi-fi", "password", "mac address", "network key"]):
        return "I'm not able to share network or security information. Please contact Sarah in IT directly."

    if any(k in query_lower for k in ["salary", "lohn", "gehalt", "payslip", "raise"]):
        return "I'm not able to help with salary or payroll questions. Please contact Beat Müller or HR directly."

    if any(p in query_lower for p in INJECTION_PATTERNS):
        return "I'm not able to process that request. Please ask me a question about GreenLeaf HR policies."

    return "I'm not able to help with that. Please contact HR directly."
