"""
privacy_gate.py — GreenLeaf Bot | Security Filter Layer
=========================================================
This module acts as the first line of defense before any query
reaches the LLM (Gemini) or internal tools.

Architecture position (HLD):
    app.py → privacy_gate.py → brain.py → tools
                  ↓
         1. clean_input()  — mask PII (names, IDs, emails)
         2. is_blocked()   — block sensitive queries and injections

Compliance:
    - Swiss FADP (nDSG): no PII or sensitive internal data exposed
    - No blocked query content is logged (privacy by design)

Sprint: Week 2 | Owner: Ibrahim (System Architect)
"""

import re

# ---------------------------------------------------------------------------
# PII Masking Patterns
# ---------------------------------------------------------------------------

EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
EMPLOYEE_ID_PATTERN = re.compile(r'\b\d{5}\b')
NAME_PHRASE_PATTERN = re.compile(r'(my name is|I am|I\'m)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', re.IGNORECASE)
CAPITALIZED_NAME_PATTERN = re.compile(r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b')

# Words that look like names but should not be masked
EXCLUDE_FROM_NAME_DETECTION = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "is", "are", "the", "basel", "zurich", "bern", "geneva", "lausanne",
    "greenleaf", "switzerland", "swiss", "beat", "sarah", "muller", "müller"
}


def clean_input(text: str) -> str:
    """
    Masks PII in the input text before any processing.
    Original text is never logged or forwarded.

    Masks: email addresses, 5-digit employee IDs, names after phrases,
           capitalized word pairs (first + last name pattern).
    """
    masked = EMAIL_PATTERN.sub('[EMAIL]', text)
    masked = EMPLOYEE_ID_PATTERN.sub('[ID]', masked)
    masked = NAME_PHRASE_PATTERN.sub(lambda m: m.group(1) + ' [NAME]', masked)

    def mask_name_pair(m):
        w1, w2 = m.group(1).lower(), m.group(2).lower()
        if w1 in EXCLUDE_FROM_NAME_DETECTION or w2 in EXCLUDE_FROM_NAME_DETECTION:
            return m.group(0)
        return '[NAME]'

    masked = CAPITALIZED_NAME_PATTERN.sub(mask_name_pair, masked)

    if masked != text:
        print(f"[PRIVACY] Input masked before processing: {masked}")

    return masked


# ---------------------------------------------------------------------------
# Block Filter
# ---------------------------------------------------------------------------

BLOCKED_KEYWORDS = [
    # Network / IT security
    "wifi", "wi-fi", "password", "passwort",
    "mac address", "network key",
    # HR sensitive data
    "salary", "lohn", "gehalt", "payslip",
    "raise", "gehaltserhöhung"
]

INJECTION_PHRASES = [
    "ignore previous instructions",
    "ignore all instructions",
    "pretend you are",
    "act as if",
    "you are now",
    "forget your instructions",
    "disregard your",
    "override your",
]


def is_blocked(query: str) -> bool:
    """
    Returns True if the query contains a blocked keyword or injection phrase.
    Case-insensitive check.
    """
    query_lower = query.lower()
    for keyword in BLOCKED_KEYWORDS:
        if keyword in query_lower:
            return True
    for phrase in INJECTION_PHRASES:
        if phrase in query_lower:
            return True
    return False


def get_block_message(query: str) -> str:
    """
    Returns a safe, user-friendly refusal message.
    Redirects the user to the correct contact person.
    Does NOT reveal why the query was blocked in technical terms.
    """
    query_lower = query.lower()

    if any(k in query_lower for k in ["wifi", "wi-fi", "password", "mac address", "network key"]):
        return "I'm not able to share network or security information. Please contact Sarah in IT directly."

    if any(k in query_lower for k in ["salary", "lohn", "gehalt", "payslip", "raise"]):
        return "I'm not able to help with salary or payroll questions. Please contact Beat Müller or HR directly."

    return "I'm not able to help with that. Please contact HR directly."


# =============================================================================
# HOW TO TEST
# =============================================================================
#
# Run the test file:
#   python tests/test_privacy_gate.py
#
# Expected results:
#   "What is the wifi password?"        → BLOCKED (IT security)
#   "What is my salary?"                → BLOCKED (HR sensitive)
#   "Ignore previous instructions"      → BLOCKED (injection)
#   "My name is Beat Müller"            → "My name is [NAME]"
#   "My ID is 12345"                    → "My ID is [ID]"
#   "Is May 1st a holiday in Basel?"    → PASS (no masking)
# =============================================================================
