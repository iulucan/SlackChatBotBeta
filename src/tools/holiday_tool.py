"""
holiday_tool.py

A secure, high-performance module to interface with the OpenHolidays API.
Designed to be imported by other services (like brain.py) to check for
National and Cantonal holidays in Switzerland.

Security & Architectural Features:
- Validates all input prior to outbound requests to prevent injection or malformed queries.
- Enforces strict HTTP request timeouts to prevent system hangs.

Usage:
    checker = SwissHolidayChecker(language="EN")
    is_holiday1 = checker.is_holiday(date(2026, 5, 1), "BS"), the answer is YES
    is_holiday2 = checker.is_holiday(date(2026, 12, 25), "BS"), the answer is YES
    is_holiday3 = checker.is_holiday(date(2026, 9, 21), "VD"), the answer is YES
    is_holiday4 = checker.is_holiday(date(2026, 9, 21), "BS"), the answer is NO
"""

import logging
from datetime import date, datetime
from typing import Dict, Optional, List, Set, Any
from dataclasses import dataclass
import requests

# Configure logging for the tool
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


@dataclass
class Holiday:
    """
    A data class representing a single holiday returned by the API.

    Attributes:
        date (date): The exact date of the holiday.
        name (str): The localized name of the holiday (e.g., "Swiss National Day").
        type (str): The classification of the holiday (e.g., "Public", "Regional").
        nationwide (bool): True if the holiday applies to the entire country of Switzerland.
        canton (Optional[str]): The 2-letter code of the canton if this is a regional holiday, otherwise None.
    """
    date: date
    name: str
    type: str
    nationwide: bool
    canton: Optional[str] = None


class HolidayAPIError(Exception):
    """
    Custom exception raised for errors encountered while communicating
    with the OpenHolidays API (e.g., network timeouts, HTTP errors, bad JSON formatting).
    """
    pass


class SwissHolidayChecker:
    """
    A client for fetching Swiss holiday data from the OpenHolidays API.

    Attributes:
        BASE_URL (str): The root endpoint for the OpenHolidays API PublicHolidays service.
        VALID_CANTONS (Set[str]): A strict set of recognized 2-letter Swiss Canton codes
                                  used to sanitize and validate inputs.
    """
    BASE_URL = "https://openholidaysapi.org/PublicHolidays"

    VALID_CANTONS: Set[str] = {
        "AG", "AR", "AI", "BL", "BS", "BE", "FR", "GE", "GL",
        "GR", "JU", "LU", "NE", "NW", "OW", "SG", "SH", "SZ",
        "SO", "TG", "TI", "UR", "VD", "VS", "ZH", "ZG"
    }

    def __init__(self, timeout: float = 5.0, language: str = "EN") -> None:
        """
        Initializes the SwissHolidayChecker.

        Args:
            timeout (float): The maximum time (in seconds) to wait for an API response.
                             Defaults to 5.0 seconds to prevent denial-of-service hanging.
            language (str): The ISO-639-1 language code for holiday names returned by the API.
                            Accepts values like 'EN', 'FR', 'DE', 'IT'. Defaults to 'EN'.
        """
        self.timeout = timeout
        self.language = language.upper()

    def _validate_canton(self, canton: str) -> str:
        """
        Sanitizes and validates the provided canton code against the known list of Swiss cantons.

        Args:
            canton (str): The 2-letter canton abbreviation to validate.

        Returns:
            str: The uppercase, validated canton code.

        Raises:
            ValueError: If the canton code is not present in the VALID_CANTONS set.
        """
        canton = canton.upper()
        if canton not in self.VALID_CANTONS:
            raise ValueError(f"Invalid Swiss canton code: '{canton}'. Must be one of {self.VALID_CANTONS}")
        return canton

    def _fetch_from_api(self, year: int, subdivision_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Executes the HTTP GET request to the OpenHolidays API with appropriate parameters.

        Args:
            year (int): The 4-digit year to request holidays for (e.g., 2026).
            subdivision_code (Optional[str]): The specific ISO-3166-2 subdivision code
                                              (e.g., 'CH-VD' for Vaud). If omitted, fetches nationwide holidays.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries representing the JSON data returned by the API.

        Raises:
            HolidayAPIError: If a network error, HTTP error (4xx/5xx), or data parsing error occurs.
        """
        params = {
            "countryIsoCode": "CH",
            "languageIsoCode": self.language,
            "validFrom": f"{year}-01-01",
            "validTo": f"{year}-12-31"
        }

        if subdivision_code:
            params["subdivisionCode"] = subdivision_code

        try:
            logger.debug(f"Fetching holidays for {year} (Subdivision: {subdivision_code})")
            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Unexpected API response format: expected a JSON list.")
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Network or HTTP error while calling OpenHolidays API: {e}")
            raise HolidayAPIError("Failed to communicate with the holiday API.") from e
        except ValueError as e:
            logger.error(f"Data integrity error: {e}")
            raise HolidayAPIError("Failed to parse the holiday API response securely.") from e

    def get_holiday(self, target_date: date, canton: str) -> Optional[Holiday]:
        """
        Determines whether a specified date is a holiday within a specific canton.

        This method checks for nationwide holidays first, then falls back to cantonal holidays,
        making live network requests each time.

        Args:
            target_date (datetime.date): The specific date object to check.
            canton (str): The 2-letter Swiss canton code (e.g., 'VD', 'ZH').

        Returns:
            Optional[Holiday]: A populated Holiday dataclass if the date falls on a holiday,
                               otherwise None.

        Raises:
            TypeError: If the target_date argument is not a valid datetime.date instance.
            ValueError: If the canton code is invalid.
            HolidayAPIError: If the API fails during a necessary fetch operation.
        """
        if not isinstance(target_date, date):
            raise TypeError("target_date must be a datetime.date object")

        canton = self._validate_canton(canton)
        year = target_date.year

        # 1. Fetch and check Nationwide Holidays
        ch_data = self._fetch_from_api(year)
        for item in ch_data:
            try:
                start_date = datetime.strptime(item["startDate"], "%Y-%m-%d").date()
                if start_date == target_date:
                    name = item.get("name", [{}])[0].get("text", "Unknown Holiday")
                    return Holiday(
                        date=start_date,
                        name=name,
                        type=item.get("type", "Public"),
                        nationwide=True
                    )
            except (KeyError, IndexError, ValueError) as e:
                logger.warning(f"Skipping malformed holiday entry: {item} - Error: {e}")

        # 2. Fetch and check Cantonal Holidays
        subdivision = f"CH-{canton}"
        canton_data = self._fetch_from_api(year, subdivision_code=subdivision)

        for item in canton_data:
            try:
                start_date = datetime.strptime(item["startDate"], "%Y-%m-%d").date()
                if start_date == target_date:
                    name = item.get("name", [{}])[0].get("text", "Unknown Holiday")
                    return Holiday(
                        date=start_date,
                        name=name,
                        type=item.get("type", "Regional"),
                        nationwide=item.get("nationwide", False),
                        canton=canton
                    )
            except (KeyError, IndexError, ValueError) as e:
                logger.warning(f"Skipping malformed cantonal holiday entry: {item} - Error: {e}")

        return None

    def is_holiday(self, target_date: date, canton: str) -> bool:
        """
        A convenience wrapper around `get_holiday` that simply returns a boolean indicating
        holiday status. Extremely useful for quick logic gating in calling services (e.g., brain.py).

        Args:
            target_date (datetime.date): The specific date object to check.
            canton (str): The 2-letter Swiss canton code (e.g., 'VD', 'ZH').

        Returns:
            bool: True if the target date is a holiday (national or cantonal), False otherwise.

        Raises:
            TypeError: If the target_date argument is not a valid datetime.date instance.
            ValueError: If the canton code is invalid.
            HolidayAPIError: If the API fails during a necessary fetch operation.
        """
        return self.get_holiday(target_date, canton) is not None