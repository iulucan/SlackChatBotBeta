# Security filter — blocks sensitive queries before reaching the LLM

BLOCKED_KEYWORDS = [
    "wifi", "wi-fi", "password", "passwort",
    "mac address", "network key",
    "salary", "lohn", "gehalt", "payslip",
    "raise", "gehaltserhöhung"
]

def is_blocked(query: str) -> bool:
    query_lower = query.lower()
    for keyword in BLOCKED_KEYWORDS:
        if keyword in query_lower:
            return True
    return False

def get_block_message(query: str) -> str:
    query_lower = query.lower()
    if any(k in query_lower for k in ["wifi", "wi-fi", "password", "mac address", "network key"]):
        return "I'm not able to share network or security information. Please contact Sarah in IT directly."
    if any(k in query_lower for k in ["salary", "lohn", "gehalt", "payslip", "raise"]):
        return "I'm not able to help with salary or payroll questions. Please contact Beat Müller or HR directly."
    return "I'm not able to help with that. Please contact HR directly."
