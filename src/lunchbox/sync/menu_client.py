import logging
import time
from datetime import date

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
        self._client = httpx.Client(
            timeout=timeout, headers={"Accept": "application/json"}
        )
        self._max_retries = max_retries
        self._retry_delays = retry_delays
        self._min_request_delay = min_request_delay
        self._last_request_time = 0.0

    def _get_delay(self, attempt: int) -> float:
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
                            delay = min(float(retry_after), RETRY_AFTER_CAP)
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
        data = response.json()

        drift_warnings = _detect_drift(data)
        for warning in drift_warnings:
            logger.warning("SchoolCafe schema drift: %s", warning)

        return self._parse_response(data)

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
        districts = response.json()

        if not districts:
            return []

        district_id = districts[0].get("ISDId")
        if not district_id:
            return []

        response = self._request(
            f"{self.BASE_URL}/GetSchoolsList",
            params={"districtId": district_id},
        )
        schools = response.json()

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
