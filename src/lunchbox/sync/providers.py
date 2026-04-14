from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass
class MenuItemData:
    category: str
    item_name: str


@dataclass
class SchoolInfo:
    school_id: str
    school_name: str


class MenuProvider(Protocol):
    def get_daily_menu(
        self,
        school_id: str,
        menu_date: date,
        meal_type: str,
        serving_line: str,
        grade: str,
    ) -> list[MenuItemData]: ...

    def get_weekly_menu(
        self,
        school_id: str,
        week_date: date,
        meal_type: str,
        serving_line: str,
        grade: str,
    ) -> dict[date, list[MenuItemData]]: ...

    def search_schools(self, query: str) -> list[SchoolInfo]: ...
