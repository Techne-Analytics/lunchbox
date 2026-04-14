import json
import logging
import time
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from lunchbox.sync.providers import MenuItemData, SchoolInfo

logger = logging.getLogger(__name__)

# Known category aliases — normalize to title case
CATEGORY_ALIASES: dict[str, str] = {
    "breakfast entrees": "Entrees",
    "entrees": "Entrees",
    "grains": "Grains",
    "vegetables": "Vegetables",
    "fruits": "Fruits",
    "milk": "Milk",
    "condiments": "Condiments",
}

RETRY_AFTER_CAP = 10


def _extract_item_name(item) -> str | None:
    """Extract item name with fallback strategies for schema drift."""
    if isinstance(item, str):
        return item.strip() or None

    if isinstance(item, dict):
        # Primary field
        for field in ("MenuItemDescription", "Name", "name", "description"):
            value = item.get(field)
            if value and isinstance(value, str):
                return value.strip()

        # Last resort: first non-numeric string value in the dict
        for value in item.values():
            if isinstance(value, str) and value.strip():
                stripped = value.strip()
                # Skip values that look like prices, IDs, or numbers
                try:
                    float(stripped)
                    continue
                except ValueError:
                    pass
                logger.warning(
                    "menu_client: used fallback extraction, key structure: %s",
                    list(item.keys()),
                )
                return stripped

    return None


def _normalize_category(category: str) -> str:
    """Normalize category name, accepting unknowns gracefully."""
    alias = CATEGORY_ALIASES.get(category.lower())
    if alias:
        return alias
    return category.title()


def _detect_drift(data: dict) -> list[str]:
    """Check for schema drift indicators. Returns list of warnings."""
    warnings = []
    for category, items in data.items():
        if not isinstance(items, list):
            warnings.append(f"category '{category}' value is not a list")
            continue
        for item in items[:1]:  # Check first item only
            if isinstance(item, str):
                warnings.append(
                    f"category '{category}' contains plain strings, not dicts"
                )
            elif isinstance(item, dict) and "MenuItemDescription" not in item:
                warnings.append(
                    f"category '{category}' items missing MenuItemDescription, "
                    f"found keys: {list(item.keys())}"
                )
    return warnings


class SchoolCafeClient:
    """Resilient SchoolCafe API client with self-healing parsing."""

    BASE_URL = "https://webapis.schoolcafe.com/api"

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delays: tuple[float, ...] = (1, 2, 4),
        min_request_delay: float = 0.1,
    ):
        if max_retries < 0:
            raise ValueError(f"max_retries must be >= 0, got {max_retries}")
        self._client = httpx.Client(
            timeout=timeout, headers={"Accept": "application/json"}
        )
        self._max_retries = max_retries
        self._retry_delays = retry_delays
        self._min_request_delay = min_request_delay
        self._last_request_time = 0.0

    def _get_delay(self, attempt: int) -> float:
        if not self._retry_delays:
            return 0.0
        if attempt < len(self._retry_delays):
            return self._retry_delays[attempt]
        return self._retry_delays[-1]

    def _throttle(self) -> None:
        """Sleep if less than _min_request_delay since last request."""
        if self._min_request_delay <= 0:
            return
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_delay:
            time.sleep(self._min_request_delay - elapsed)

    def _request(self, url: str, **kwargs) -> httpx.Response:
        """Make an HTTP GET with retry logic for transient failures."""
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            self._throttle()
            self._last_request_time = time.monotonic()

            try:
                response = self._client.get(url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    delay = self._get_delay(attempt)
                    logger.warning(
                        "Request timeout (attempt %d/%d), retrying in %.1fs",
                        attempt + 1,
                        self._max_retries + 1,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    raise
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status = exc.response.status_code

                if status == 429:
                    retry_after = exc.response.headers.get("Retry-After")
                    if retry_after is not None:
                        try:
                            delay = max(0, min(float(retry_after), RETRY_AFTER_CAP))
                        except (ValueError, TypeError):
                            # Try HTTP-date format (RFC 7231)
                            try:
                                dt = parsedate_to_datetime(retry_after)
                                delay = max(
                                    0,
                                    min(
                                        (
                                            dt - datetime.now(timezone.utc)
                                        ).total_seconds(),
                                        RETRY_AFTER_CAP,
                                    ),
                                )
                            except (ValueError, TypeError):
                                delay = self._get_delay(attempt)
                    else:
                        delay = self._get_delay(attempt)
                elif 500 <= status < 600:
                    delay = self._get_delay(attempt)
                else:
                    # 4xx (not 429) — don't retry
                    raise

                if attempt < self._max_retries:
                    logger.warning(
                        "HTTP %d (attempt %d/%d), retrying in %.1fs",
                        status,
                        attempt + 1,
                        self._max_retries + 1,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    raise

        raise last_exc  # type: ignore[misc]  # unreachable safety net

    def get_daily_menu(
        self,
        school_id: str,
        menu_date: date,
        meal_type: str,
        serving_line: str,
        grade: str,
    ) -> list[MenuItemData]:
        params = {
            "SchoolId": school_id,
            "ServingDate": menu_date.isoformat(),
            "ServingLine": serving_line,
            "MealType": meal_type,
            "Grade": grade,
            "PersonId": "",
        }

        response = self._request(
            f"{self.BASE_URL}/CalendarView/GetDailyMenuitemsByGrade",
            params=params,
        )

        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.warning(
                "SchoolCafe returned invalid JSON for %s %s", school_id, menu_date
            )
            return []

        if not isinstance(data, dict):
            logger.warning(
                "SchoolCafe returned non-dict response: %s", type(data).__name__
            )
            return []

        drift_warnings = _detect_drift(data)
        for warning in drift_warnings:
            logger.warning("SchoolCafe schema drift: %s", warning)

        return self._parse_response(data)

    def get_weekly_menu(
        self,
        school_id: str,
        week_date: date,
        meal_type: str,
        serving_line: str,
        grade: str,
    ) -> dict[date, list[MenuItemData]]:
        """Fetch a week's menu in one call. Returns dict mapping date to items.

        SchoolCafe returns Mon-Fri for the week containing week_date.
        Date keys in the response are US format (M/D/YYYY).
        """
        params = {
            "SchoolId": school_id,
            "ServingDate": week_date.isoformat(),
            "ServingLine": serving_line,
            "MealType": meal_type,
            "Grade": grade,
            "PersonId": "",
        }

        response = self._request(
            f"{self.BASE_URL}/CalendarView/GetWeeklyMenuitemsByGrade",
            params=params,
        )

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            logger.warning(
                "SchoolCafe returned invalid JSON for weekly %s %s",
                school_id,
                week_date,
            )
            # Raise so the engine treats this as a fetch failure and records
            # errors per date, rather than silently wiping a week of menu data.
            raise ValueError(
                f"SchoolCafe weekly returned invalid JSON for {school_id} {week_date}"
            ) from exc

        if not isinstance(data, dict):
            logger.warning(
                "SchoolCafe weekly returned non-dict response: %s",
                type(data).__name__,
            )
            raise ValueError(
                f"SchoolCafe weekly returned non-dict response: {type(data).__name__}"
            )

        result: dict[date, list[MenuItemData]] = {}
        for date_str, day_data in data.items():
            try:
                parsed_date = datetime.strptime(date_str, "%m/%d/%Y").date()
            except (ValueError, TypeError):
                logger.warning(
                    "SchoolCafe weekly: unparseable date key %r, skipping", date_str
                )
                continue

            if not isinstance(day_data, dict):
                logger.warning(
                    "SchoolCafe weekly: non-dict day_data for %s: %s",
                    date_str,
                    type(day_data).__name__,
                )
                continue

            drift_warnings = _detect_drift(day_data)
            for warning in drift_warnings:
                logger.warning(
                    "SchoolCafe schema drift [weekly %s]: %s", parsed_date, warning
                )

            result[parsed_date] = self._parse_response(day_data)

        return result

    def _parse_response(self, data: dict) -> list[MenuItemData]:
        items = []
        for category, raw_items in data.items():
            if not isinstance(raw_items, list):
                continue

            normalized_category = _normalize_category(category)

            for raw_item in raw_items:
                name = _extract_item_name(raw_item)
                if name:
                    items.append(
                        MenuItemData(category=normalized_category, item_name=name)
                    )

        # Deduplicate by (category, item_name)
        seen = set()
        unique = []
        for item in items:
            key = (item.category, item.item_name)
            if key not in seen:
                seen.add(key)
                unique.append(item)

        return unique

    def search_schools(self, query: str) -> list[SchoolInfo]:
        response = self._request(
            f"{self.BASE_URL}/GetISDByShortName",
            params={"shortname": query},
        )

        try:
            districts = response.json()
        except json.JSONDecodeError:
            logger.warning(
                "SchoolCafe returned invalid JSON for districts query: %s", query
            )
            return []

        if not isinstance(districts, list) or not districts:
            if districts:
                logger.warning(
                    "SchoolCafe returned non-list districts response: %s",
                    type(districts).__name__,
                )
            return []

        district_id = districts[0].get("ISDId")
        if not district_id:
            logger.warning(
                "SchoolCafe district missing ISDId, keys: %s",
                list(districts[0].keys()),
            )
            return []

        response = self._request(
            f"{self.BASE_URL}/GetSchoolsList",
            params={"districtId": district_id},
        )

        try:
            schools = response.json()
        except json.JSONDecodeError:
            logger.warning(
                "SchoolCafe returned invalid JSON for schools list: district %s",
                district_id,
            )
            return []

        if not isinstance(schools, list):
            logger.warning(
                "SchoolCafe returned non-list schools response: %s",
                type(schools).__name__,
            )
            return []

        return [
            SchoolInfo(
                school_id=s.get("SchoolId", ""),
                school_name=s.get("SchoolName", ""),
            )
            for s in schools
            if s.get("SchoolId")
        ]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self._client.close()
