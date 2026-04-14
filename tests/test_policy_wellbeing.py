import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.tools.policy_wellbeing import (
    classify_section_9_severity,
    query_handbook,
    SECTION_9_MINOR_QUOTE,
    SECTION_9_SERIOUS_QUOTE,
    OMBUDSMAN_EMAIL,
)


class TestPolicyWellbeingSection9(unittest.TestCase):
    """Tests for Section 9 conduct-related fixed messaging and severity routing."""

    def test_classify_section_9_severity_minor_conflict(self):
        message = "I have a disagreement with a coworker about our shift schedule."
        severity = classify_section_9_severity(message)
        self.assertEqual(severity, "minor")

    def test_classify_section_9_severity_serious_misconduct(self):
        message = "Someone is bullying me at work and I feel threatened."
        severity = classify_section_9_severity(message)
        self.assertEqual(severity, "serious")

    def test_query_handbook_returns_coffee_chat_for_minor_conflict(self):
        result = query_handbook("I have a conflict with a coworker over a small issue.")

        self.assertIn("Coffee Chat", result["answer"])
        self.assertIn("Section 9", result["source"])
        self.assertIn(SECTION_9_MINOR_QUOTE, result["source"])

    def test_query_handbook_returns_ombudsman_for_ambiguous_or_serious(self):
        result = query_handbook("I'm not sure if this is harassment or just a difficult conflict.")

        self.assertIn(OMBUDSMAN_EMAIL, result["answer"])
        self.assertIn("Section 9", result["source"])
        self.assertIn(SECTION_9_SERIOUS_QUOTE, result["source"])


if __name__ == '__main__':
    unittest.main(verbosity=2)
