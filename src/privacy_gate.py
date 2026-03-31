"""
privacy_gate.py — GreenLeaf Bot | Security Filter Layer
=========================================================
This module acts as the first line of defense before any query
reaches the LLM (Gemini) or internal tools.

Architecture position (HLD):
    app.py → privacy_gate.py → brain.py → tools
                  ↓
         blocks sensitive queries here
         nothing sensitive reaches the LLM

What it blocks:
    - Network/IT data: Wi-Fi passwords, MAC addresses, network keys
    - HR sensitive data: salary, payslip, raise requests

Compliance:
    - Swiss FADP (nDSG): no PII or sensitive internal data exposed
    - No blocked query content is logged (privacy by design)

Sprint: Week 2 | Owner: Ibrahim (System Architect)
"""


# Keywords that trigger a security block
# Add new keywords here as new edge cases are discovered
BLOCKED_KEYWORDS = [
    # Network / IT security
    "wifi", "wi-fi", "password", "passwort",
    "mac address", "network key",
    # HR sensitive data
    "salary", "lohn", "gehalt", "payslip",
    "raise", "gehaltserhöhung"
]


def is_blocked(query: str) -> bool:
    """
    Returns True if the query contains a blocked keyword.
    Case-insensitive check.
    """
    query_lower = query.lower()
    for keyword in BLOCKED_KEYWORDS:
        if keyword in query_lower:
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
#   "What is the office wi-fi password?"→ BLOCKED (IT security)
#   "What is my salary?"                → BLOCKED (HR sensitive)
#   "Can I expense a 30 CHF lunch?"     → PASS
#   "Is May 1st a holiday in Basel?"    → PASS
#   "How many days bereavement leave?"  → PASS
#
# To add a new blocked keyword:
#   1. Add the keyword to BLOCKED_KEYWORDS list above
#   2. Add a test case to tests/test_privacy_gate.py
#   3. Run tests to confirm
# =============================================================================
