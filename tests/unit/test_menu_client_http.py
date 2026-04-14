from datetime import date

import httpx
import pytest
import respx

from lunchbox.sync.menu_client import SchoolCafeClient


BASE_URL = "https://webapis.schoolcafe.com/api"


class TestClientConfig:
    def test_default_constructor(self):
        client = SchoolCafeClient()
        assert client._max_retries == 3
        assert client._retry_delays == (1, 2, 4)
        assert client._min_request_delay == 0.1
        assert client._last_request_time == 0.0
        client.close()

    def test_custom_constructor(self):
        client = SchoolCafeClient(
            max_retries=5,
            retry_delays=(0.5, 1.0),
            min_request_delay=0.5,
        )
        assert client._max_retries == 5
        assert client._retry_delays == (0.5, 1.0)
        assert client._min_request_delay == 0.5
        client.close()


class TestGetDailyMenu:
    @respx.mock
    def test_successful_fetch(self, schoolcafe_fixture):
        data = schoolcafe_fixture("normal_lunch")
        respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade").mock(
            return_value=httpx.Response(200, json=data)
        )

        with SchoolCafeClient() as client:
            items = client.get_daily_menu(
                "s1", date(2026, 3, 16), "Lunch", "Trad", "05"
            )

        assert len(items) > 0
        assert items[0].item_name == "BBQ Chicken Drumstick"
        assert items[0].category == "Entrees"

    @respx.mock
    def test_schema_drift_still_parses(self, schoolcafe_fixture):
        data = schoolcafe_fixture("drifted_field_names")
        respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade").mock(
            return_value=httpx.Response(200, json=data)
        )

        with SchoolCafeClient() as client:
            items = client.get_daily_menu(
                "s1", date(2026, 3, 16), "Lunch", "Trad", "05"
            )

        assert len(items) > 0

    @respx.mock
    def test_http_500_raises(self):
        respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade").mock(
            return_value=httpx.Response(500)
        )

        with SchoolCafeClient(max_retries=0) as client:
            with pytest.raises(httpx.HTTPStatusError):
                client.get_daily_menu("s1", date(2026, 3, 16), "Lunch", "Trad", "05")

    @respx.mock
    def test_timeout_raises(self):
        respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade").mock(
            side_effect=httpx.TimeoutException("timed out")
        )

        with SchoolCafeClient(max_retries=0) as client:
            with pytest.raises(httpx.TimeoutException):
                client.get_daily_menu("s1", date(2026, 3, 16), "Lunch", "Trad", "05")


class TestSearchSchools:
    @respx.mock
    def test_search_returns_schools(self, schoolcafe_fixture):
        districts = schoolcafe_fixture("search_districts")
        schools = schoolcafe_fixture("search_schools")

        respx.get(f"{BASE_URL}/GetISDByShortName").mock(
            return_value=httpx.Response(200, json=districts)
        )
        respx.get(f"{BASE_URL}/GetSchoolsList").mock(
            return_value=httpx.Response(200, json=schools)
        )

        with SchoolCafeClient() as client:
            result = client.search_schools("springfield")

        assert len(result) == 2
        assert result[0].school_id == "school-001"
        assert result[0].school_name == "Springfield Elementary"

    @respx.mock
    def test_search_empty_districts(self):
        respx.get(f"{BASE_URL}/GetISDByShortName").mock(
            return_value=httpx.Response(200, json=[])
        )

        with SchoolCafeClient() as client:
            result = client.search_schools("nonexistent")

        assert result == []


class TestResponseValidation:
    @respx.mock
    def test_malformed_json_returns_empty(self):
        respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade").mock(
            return_value=httpx.Response(200, content=b"not json at all")
        )
        with SchoolCafeClient(max_retries=0) as client:
            items = client.get_daily_menu(
                "s1", date(2026, 3, 16), "Lunch", "Trad", "05"
            )
        assert items == []

    @respx.mock
    def test_non_dict_response_returns_empty(self):
        respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade").mock(
            return_value=httpx.Response(200, json=["not", "a", "dict"])
        )
        with SchoolCafeClient(max_retries=0) as client:
            items = client.get_daily_menu(
                "s1", date(2026, 3, 16), "Lunch", "Trad", "05"
            )
        assert items == []

    @respx.mock
    def test_null_response_returns_empty(self):
        respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade").mock(
            return_value=httpx.Response(200, json=None)
        )
        with SchoolCafeClient(max_retries=0) as client:
            items = client.get_daily_menu(
                "s1", date(2026, 3, 16), "Lunch", "Trad", "05"
            )
        assert items == []

    @respx.mock
    def test_search_malformed_json_returns_empty(self):
        respx.get(f"{BASE_URL}/GetISDByShortName").mock(
            return_value=httpx.Response(200, content=b"not json")
        )
        with SchoolCafeClient(max_retries=0) as client:
            result = client.search_schools("test")
        assert result == []

    @respx.mock
    def test_search_non_list_districts_returns_empty(self):
        respx.get(f"{BASE_URL}/GetISDByShortName").mock(
            return_value=httpx.Response(200, json={"error": "bad request"})
        )
        with SchoolCafeClient(max_retries=0) as client:
            result = client.search_schools("test")
        assert result == []

    @respx.mock
    def test_search_non_list_schools_returns_empty(self, schoolcafe_fixture):
        districts = schoolcafe_fixture("search_districts")
        respx.get(f"{BASE_URL}/GetISDByShortName").mock(
            return_value=httpx.Response(200, json=districts)
        )
        respx.get(f"{BASE_URL}/GetSchoolsList").mock(
            return_value=httpx.Response(200, json={"error": "bad"})
        )
        with SchoolCafeClient(max_retries=0) as client:
            result = client.search_schools("springfield")
        assert result == []


class TestRetry:
    @respx.mock
    def test_retry_succeeds_on_second_attempt(self, schoolcafe_fixture):
        data = schoolcafe_fixture("normal_lunch")
        route = respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade").mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(200, json=data),
            ]
        )

        with SchoolCafeClient(
            max_retries=3, retry_delays=(0, 0, 0), min_request_delay=0
        ) as client:
            items = client.get_daily_menu(
                "s1", date(2026, 3, 16), "Lunch", "Trad", "05"
            )

        assert len(items) > 0
        assert route.call_count == 2

    @respx.mock
    def test_429_respects_retry_after(self, schoolcafe_fixture):
        data = schoolcafe_fixture("normal_lunch")
        route = respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade")
        route.side_effect = [
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json=data),
        ]

        with SchoolCafeClient(
            max_retries=3, retry_delays=(0, 0, 0), min_request_delay=0
        ) as client:
            items = client.get_daily_menu(
                "s1", date(2026, 3, 16), "Lunch", "Trad", "05"
            )

        assert len(items) > 0
        assert route.call_count == 2

    @respx.mock
    def test_429_without_retry_after(self, schoolcafe_fixture):
        data = schoolcafe_fixture("normal_lunch")
        route = respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade")
        route.side_effect = [
            httpx.Response(429),  # no Retry-After header
            httpx.Response(200, json=data),
        ]

        with SchoolCafeClient(
            max_retries=3, retry_delays=(0, 0, 0), min_request_delay=0
        ) as client:
            items = client.get_daily_menu(
                "s1", date(2026, 3, 16), "Lunch", "Trad", "05"
            )

        assert len(items) > 0
        assert route.call_count == 2

    @respx.mock
    def test_retry_exhausted_raises(self):
        route = respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade").mock(
            return_value=httpx.Response(500)
        )

        with SchoolCafeClient(
            max_retries=3, retry_delays=(0, 0, 0), min_request_delay=0
        ) as client:
            with pytest.raises(httpx.HTTPStatusError):
                client.get_daily_menu("s1", date(2026, 3, 16), "Lunch", "Trad", "05")

        assert route.call_count == 4

    @respx.mock
    def test_4xx_not_retried(self):
        route = respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade").mock(
            return_value=httpx.Response(404)
        )

        with SchoolCafeClient(
            max_retries=3, retry_delays=(0, 0, 0), min_request_delay=0
        ) as client:
            with pytest.raises(httpx.HTTPStatusError):
                client.get_daily_menu("s1", date(2026, 3, 16), "Lunch", "Trad", "05")

        assert route.call_count == 1

    @respx.mock
    def test_timeout_retried(self, schoolcafe_fixture):
        data = schoolcafe_fixture("normal_lunch")
        route = respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade").mock(
            side_effect=[
                httpx.TimeoutException("timed out"),
                httpx.Response(200, json=data),
            ]
        )

        with SchoolCafeClient(
            max_retries=3, retry_delays=(0, 0, 0), min_request_delay=0
        ) as client:
            items = client.get_daily_menu(
                "s1", date(2026, 3, 16), "Lunch", "Trad", "05"
            )

        assert len(items) > 0
        assert route.call_count == 2
