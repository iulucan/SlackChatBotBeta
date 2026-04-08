"""
test_holiday_tool.py

Unit tests for the SwissHolidayChecker module.
Run this file directly using: python -m unittest test_holiday_tool.py
"""
import sys
import os
import unittest
from datetime import date

# Ensure the src directory is in the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.tools.holiday_tool import SwissHolidayChecker


class TestSwissHolidayChecker(unittest.TestCase):

    def setUp(self):
        """
        Set up the test case. This runs before every individual test method.
        We initialize the checker here to reuse it across tests.
        """
        self.checker = SwissHolidayChecker(language="EN")

    def test_swiss_national_day(self):
        """
        Example 1: Check Swiss National Day (August 1st).
        It should return a valid Holiday object, and nationwide should be True.
        """
        test_date = date(2026, 8, 1)
        canton = "BS"

        holiday_info = self.checker.get_holiday(test_date, canton)

        # Assert that it actually found a holiday (is not None)
        self.assertIsNotNone(holiday_info, f"Expected {test_date} to be a holiday in {canton}")

        # Assert that it is flagged as a nationwide holiday
        self.assertTrue(holiday_info.nationwide, "Swiss National Day should be nationwide")

    def test_negative_output_federal_fast_monday_in_BS(self):
        """
        Example 2: Check that Federal Fast Monday is NOT a public holiday in BS to verify negative output.
        Monday, September 21st, 2026 (Lundi du Jeûne) is a public holiday in Vaud (VD),
        but it is NOT a public holiday in Basel (BS). Therefore, checking Sept 21st
        for BS should return False.
        """
        test_date = date(2026, 9, 21)
        canton = "BS"

        is_holiday = self.checker.is_holiday(test_date, canton)

        # Assert that the result is False
        self.assertFalse(is_holiday, f"Expected {test_date} NOT to be a holiday in {canton}")

    def test_labour_day_specific_cantons(self):
        """
        Example 3: Check Labour Day on May 1st.
        It is specific to certain cantons like BS.
        """
        test_date = date(2026, 5, 1)
        canton = "BS"

        is_holiday = self.checker.is_holiday(test_date, canton)

        # Assert that the result is True
        self.assertTrue(is_holiday, f"Expected {test_date} to be a holiday in {canton}")

    def test_invalid_canton_handling(self):
        """
        Bonus Test: Ensure the checker raises a ValueError if given a fake canton code.
        """
        with self.assertRaises(ValueError):
            self.checker.is_holiday(date(2026, 1, 1), "XX")


if __name__ == "__main__":
    unittest.main()