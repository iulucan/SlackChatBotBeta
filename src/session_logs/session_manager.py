"""
session_manager.py -- GreenLeaf Bot | Session & Privacy Layer
=============================================================
Handles name validation, session ID generation, and in-memory caching.

Responsibilities:
    - Validate employee names against greenleaf_employees.csv
    - Generate anonymous session_id and conversation_id from the name
    - Cache slack_user_id -> (session_id, conversation_id) in memory
    - Never store or return real names, employee IDs, or Slack user IDs

Privacy model:
    - session_id:      SHA256(name + period) truncated to 8 chars
                       e.g. "a3f8d2e1"
    - conversation_id: {normalized_name}_{YYYY}_{H1/H2}
                       e.g. "beat_2026_H1"
    - Both rotate every 6 months (H1 = Jan-Jun, H2 = Jul-Dec)
    - Same name + same period always produces the same IDs (deterministic)
"""

import csv
import hashlib
import os
import re
import unicodedata
from datetime import datetime
from typing import Optional

# Path to the employees CSV -- relative to project root
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
EMPLOYEES_CSV_PATH = os.path.join(PROJECT_ROOT, "data", "greenleaf_employees.csv")


def _normalize(text: str) -> str:
    """
    Lowercase, strip whitespace, and remove accents from a string.
    Used so "Muller", "muller", and "MULLER" all match each other.

    Examples:
        "Muller"  -> "muller"
        " Beat "  -> "beat"
        "BEAT"    -> "beat"
    """
    # Decompose accented characters (e.g. u-umlaut -> u + combining diaeresis)
    # then keep only ASCII characters
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
    return ascii_text.strip().lower()


def _extract_name_candidates(raw_input: str) -> list[str]:
    """
    Extracts likely name candidates from short introduction phrases.
    Keeps this deterministic and lightweight to avoid adding latency.
    """
    normalized_input = _normalize(raw_input)
    candidates = [normalized_input]

    patterns = [
        r"^(?:i am|i'm|my name is)\s+(.+)$",
        r"^(?:ich bin|mein name ist)\s+(.+)$",
        r"^(?:je m'appelle|mon nom est)\s+(.+)$",
        r"^(?:mi chiamo|il mio nome e)\s+(.+)$",
        r"^(?:it is|its|it's|this is)\s+(.+)$",
        r"^(?:es ist|das ist)\s+(.+)$",
        r"^(?:c est|ceci est)\s+(.+)$",
        r"^(?:e|ed)\s+(.+)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, normalized_input)
        if match:
            extracted = match.group(1).strip()
            if extracted:
                candidates.append(extracted)

    cleaned_input = re.sub(
        r"\b(?:try|then|please|pls|just|name|first|vorname|prenom|nome|bitte)\b",
        " ",
        normalized_input,
    )
    cleaned_input = re.sub(r"\s+", " ", cleaned_input).strip()
    if cleaned_input and cleaned_input != normalized_input:
        candidates.append(cleaned_input)

    parts = cleaned_input.split() if cleaned_input else normalized_input.split()
    if parts:
        candidates.append(parts[-1])
        if len(parts) >= 2:
            candidates.append(" ".join(parts[-2:]))

    unique_candidates = []
    for candidate in candidates:
        if candidate and candidate not in unique_candidates:
            unique_candidates.append(candidate)

    return unique_candidates


def _get_current_period() -> str:
    """
    Returns the current semi-annual period string.
    H1 = January-June, H2 = July-December.

    Examples:
        Called in April 2026  -> "2026_H1"
        Called in August 2026 -> "2026_H2"
    """
    now = datetime.now()
    half = "H1" if now.month <= 6 else "H2"
    return f"{now.year}_{half}"


class SessionManager:
    """
    Manages anonymous sessions for GreenLeaf bot users.

    Usage:
        manager = SessionManager()

        # Validate name and create session
        valid, matched_name = manager.validate_name("beat")
        if valid:
            session_id, conversation_id = manager.create_session("U123ABC", matched_name)

        # On subsequent messages -- retrieve cached IDs
        session_id = manager.get_session_id("U123ABC")
        conversation_id = manager.get_conversation_id("U123ABC")
    """

    def __init__(self, csv_path: str = EMPLOYEES_CSV_PATH):
        # In-memory cache: slack_user_id -> (session_id, conversation_id)
        self._cache = {}
        self._csv_path = csv_path

    # -------------------------------------------------------
    # PUBLIC METHODS
    # -------------------------------------------------------

    def validate_name(self, raw_input: str) -> tuple:
        """
        Checks if the users input matches any employee name in the CSV.
        Accepts first name, last name, or full name.
        Case-insensitive and accent-tolerant.

        Returns:
            (True, matched_full_name)  if found
            (False, None)              if not found
        """
        for candidate in _extract_name_candidates(raw_input):
            matched = self.lookup_employee_in_csv(candidate)
            if matched:
                return True, matched
        return False, None

    def create_session(self, slack_user_id: str, matched_name: str) -> tuple:
        """
        Generates session_id and conversation_id from the employees name,
        stores them in the cache mapped to the slack_user_id.

        Args:
            slack_user_id:  Slack user ID (e.g. "U123ABC") -- only used as cache key, never logged
            matched_name:   Full name as it appears in the CSV (e.g. "Beat Muller")

        Returns:
            (session_id, conversation_id)
        """
        session_id = self.generate_session_id(matched_name)
        conversation_id = self._generate_conversation_id(matched_name)
        self._cache[slack_user_id] = (session_id, conversation_id)
        print(
            f"[SESSION] Session created -- session_id: {session_id}, conversation_id: {conversation_id}"
        )
        return session_id, conversation_id

    def get_session_id(self, slack_user_id: str) -> Optional[str]:
        """Returns the cached session_id for a user, or None if not found."""
        entry = self._cache.get(slack_user_id)
        return entry[0] if entry else None

    def get_conversation_id(self, slack_user_id: str) -> Optional[str]:
        """Returns the cached conversation_id for a user, or None if not found."""
        entry = self._cache.get(slack_user_id)
        return entry[1] if entry else None

    def has_session(self, slack_user_id: str) -> bool:
        """Returns True if the user already has a validated session in cache."""
        return slack_user_id in self._cache

    def generate_session_id(self, name: str) -> str:
        """
        Generates a deterministic 8-character session ID.
        SHA256(name + current_period), truncated to 8 hex characters.

        Same name + same period always produces the same ID.

        Examples:
            "Beat Muller" in H1 2026 -> some 8-char hex (always the same)
            "Beat Muller" in H2 2026 -> different 8-char hex (rotates)
        """
        period = _get_current_period()
        raw = f"{name}_{period}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]

    def lookup_employee_in_csv(self, raw_input: str) -> Optional[str]:
        """
        Searches greenleaf_employees.csv for a matching employee name.
        Flexible: accepts first name, last name, or full name.
        Case-insensitive and accent-tolerant.

        Args:
            raw_input: whatever the user typed (e.g. "beat", "Muller", "beat muller")

        Returns:
            The full name as it appears in the CSV (e.g. "Beat Muller"), or None if not found.
        """
        normalized_input = _normalize(raw_input)

        try:
            with open(self._csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    full_name = row.get("Name", "").strip()
                    if not full_name:
                        continue

                    normalized_full = _normalize(full_name)
                    name_parts = normalized_full.split()

                    # Match full name, first name, or last name
                    if (
                        normalized_input == normalized_full  # "beat muller"
                        or normalized_input == name_parts[0]  # "beat"
                        or normalized_input == name_parts[-1]  # "muller"
                    ):
                        return full_name  # return original name from CSV

        except FileNotFoundError:
            print(f"[SESSION ERROR] CSV not found at: {self._csv_path}")
        except Exception as e:
            print(f"[SESSION ERROR] Failed to read CSV: {e}")

        return None

    # -------------------------------------------------------
    # PRIVATE METHODS
    # -------------------------------------------------------

    def _generate_conversation_id(self, name: str) -> str:
        """
        We use SHA256 to ensure no real names (like 'beat') are stored in the DB.
        """
        period = _get_current_period()
        # Instead of normalized name, we hash the name + period
        raw = f"conv_{name}_{period}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
