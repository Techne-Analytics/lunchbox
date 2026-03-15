import json
from pathlib import Path

from lunchbox.sync.menu_client import (
    SchoolCafeClient,
    _detect_drift,
    _extract_item_name,
    _normalize_category,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "schoolcafe"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestExtractItemName:
    def test_standard_field(self):
        assert _extract_item_name({"MenuItemDescription": "Pizza"}) == "Pizza"

    def test_fallback_name_field(self):
        assert _extract_item_name({"Name": "Burger"}) == "Burger"

    def test_fallback_description_field(self):
        assert _extract_item_name({"description": "Taco"}) == "Taco"

    def test_plain_string(self):
        assert _extract_item_name("Apple") == "Apple"

    def test_empty_string(self):
        assert _extract_item_name("") is None

    def test_empty_dict(self):
        assert _extract_item_name({}) is None

    def test_strips_whitespace(self):
        assert _extract_item_name({"MenuItemDescription": "  Pizza  "}) == "Pizza"


class TestNormalizeCategory:
    def test_known_alias(self):
        assert _normalize_category("breakfast entrees") == "Entrees"
        assert _normalize_category("Entrees") == "Entrees"

    def test_unknown_gets_title_cased(self):
        assert _normalize_category("hot entrees") == "Hot Entrees"
        assert _normalize_category("SEASONAL FRUITS") == "Seasonal Fruits"


class TestDetectDrift:
    def test_no_drift(self):
        data = load_fixture("normal_lunch.json")
        assert _detect_drift(data) == []

    def test_missing_standard_field(self):
        data = load_fixture("drifted_field_names.json")
        warnings = _detect_drift(data)
        assert len(warnings) > 0
        assert any("MenuItemDescription" in w for w in warnings)

    def test_plain_strings(self):
        data = load_fixture("drifted_field_names.json")
        warnings = _detect_drift(data)
        assert any("plain strings" in w for w in warnings)


class TestParseResponse:
    def test_normal_response(self):
        data = load_fixture("normal_lunch.json")
        client = SchoolCafeClient.__new__(SchoolCafeClient)
        items = client._parse_response(data)

        categories = {i.category for i in items}
        assert "Entrees" in categories
        assert "Fruits" in categories

        names = {i.item_name for i in items}
        assert "BBQ Chicken Drumstick" in names
        assert "Pear" in names

    def test_drifted_response_still_parses(self):
        data = load_fixture("drifted_field_names.json")
        client = SchoolCafeClient.__new__(SchoolCafeClient)
        items = client._parse_response(data)

        assert len(items) > 0
        names = {i.item_name for i in items}
        assert "Pizza" in names
        assert "Apple" in names

    def test_empty_response(self):
        data = load_fixture("empty_response.json")
        client = SchoolCafeClient.__new__(SchoolCafeClient)
        items = client._parse_response(data)
        assert items == []

    def test_unknown_categories(self):
        data = load_fixture("unknown_categories.json")
        client = SchoolCafeClient.__new__(SchoolCafeClient)
        items = client._parse_response(data)

        categories = {i.category for i in items}
        assert "Hot Entrees" in categories
        assert "Seasonal Fruits" in categories
