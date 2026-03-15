# SchoolCafe API Discovery

**Date:** 2026-01-22
**Status:** Verified Working

## API Base URL

```
https://webapis.schoolcafe.com/api/
```

## Authentication

**None required.** The API is publicly accessible without authentication, cookies, or session tokens.

---

## Endpoint: Get Daily Menu by Grade

### URL
```
GET https://webapis.schoolcafe.com/api/CalendarView/GetDailyMenuitemsByGrade
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| SchoolId | GUID | Yes | School identifier (e.g., `179f1f75-67b9-44db-b2c5-83c678da3a0e`) |
| ServingDate | Date | Yes | Date in ISO format (e.g., `2026-01-23`) |
| ServingLine | String | Yes | Menu line (e.g., `Traditional Lunch`, `Grab n Go Breakfast`) |
| MealType | String | Yes | Meal type (e.g., `Lunch`, `Breakfast`) |
| Grade | String | Yes | Grade level (e.g., `05`, `K`, `12`) |
| PersonId | GUID | No | Optional person identifier (can be empty) |

### Example Request - Lunch

```bash
curl -s "https://webapis.schoolcafe.com/api/CalendarView/GetDailyMenuitemsByGrade?SchoolId=179f1f75-67b9-44db-b2c5-83c678da3a0e&ServingDate=2026-01-23&ServingLine=Traditional%20Lunch&MealType=Lunch&Grade=05&PersonId=" \
  -H "Accept: application/json"
```

### Example Request - Breakfast

```bash
curl -s "https://webapis.schoolcafe.com/api/CalendarView/GetDailyMenuitemsByGrade?SchoolId=179f1f75-67b9-44db-b2c5-83c678da3a0e&ServingDate=2026-01-23&ServingLine=Grab%20n%20Go%20Breakfast&MealType=Breakfast&Grade=05&PersonId=" \
  -H "Accept: application/json"
```

### Response Format

```json
{
  "ENTREES": [
    {
      "MenuItemDescription": "BBQ Chicken",
      "Category": "ENTREES",
      "ServingLine": "Traditional Lunch",
      "ServingDate": "2026-01-23T06:00:00Z",
      "Calories": 214,
      "Allergens": "",
      ...
    }
  ],
  "GRAINS": [...],
  "VEGETABLES": [...],
  "FRUITS": [...],
  "MILK": [...]
}
```

**Key fields per item:**
- `MenuItemDescription` - The menu item name (e.g., "BBQ Chicken")
- `Category` - The food category (e.g., "ENTREES", "GRAINS")
- `ServingLine` - Confirms which menu line
- `ServingDate` - The date this item is served
- `Allergens` - Comma-separated allergens (e.g., "Milk,Wheat,Soy,Gluten")

---

## Endpoint: Get District by Short Name

### URL
```
GET https://webapis.schoolcafe.com/api/GetISDByShortName
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| shortname | String | Yes | District short code (e.g., `DPS`) |

### Example Request

```bash
curl -s "https://webapis.schoolcafe.com/api/GetISDByShortName?shortname=DPS"
```

### Response

```json
[{
  "ISDId": 1597,
  "ISDName": "DENVER PUBLIC SCHOOLS",
  "StateCd": "CO",
  "State": "Colorado",
  "Status": true
}]
```

---

## Endpoint: Get Schools List

### URL
```
GET https://webapis.schoolcafe.com/api/GetSchoolsList
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| districtId | Integer | Yes | District ID from GetISDByShortName (e.g., `1597`) |

### Example Request

```bash
curl -s "https://webapis.schoolcafe.com/api/GetSchoolsList?districtId=1597"
```

### Response (excerpt)

```json
[
  {
    "SchoolId": "179f1f75-67b9-44db-b2c5-83c678da3a0e",
    "SchoolName": "Shoemaker",
    "SchoolTypeId": 1297,
    "SiteTypeDescription": "Elementary School"
  },
  ...
]
```

---

## Known Values for DPS/Shoemaker

| Setting | Value |
|---------|-------|
| District Short Name | `DPS` |
| District ID | `1597` |
| Shoemaker School ID | `179f1f75-67b9-44db-b2c5-83c678da3a0e` |
| Lunch Serving Line | `Traditional Lunch` |
| Breakfast Serving Line | `Grab n Go Breakfast` |
| Meal Types | `Lunch`, `Breakfast` |

---

## Verified Test Results

### Lunch (2026-01-23)

**ENTREES:**
- Bonzo Butter & Jelly Sandwich (Peanut Free)
- BBQ Chicken
- Peanut Butter & Jelly Sandwich
- Southwestern Vegetarian Burrito
- Yogurt Basket w/ Cowboy Muffin (Gr K-5)

**GRAINS:**
- Cheddar Drop Biscuit

**VEGETABLES:**
- Baby Carrots
- Baked Beans
- Sweet Corn

**FRUITS:**
- Fresh Pear
- Orange Wedges
- Pineapple Tidbits

### Breakfast (2026-01-23)

**BREAKFAST ENTREES:**
- Honey Cheerios Cereal

**FRUITS:**
- Apple
- Orange
- Pears-Cupped IW

---

## Other Available Endpoints

```
CalendarView/GetWeeklyMenuitems
CalendarView/GetWeeklyMenuitemsByGrade
CalendarView/GetMonthlyMenuitems
CalendarView/GetMonthlyMenuitemsByGrade
CalendarView/GetHolidays
CalendarView/GetMenuItemsServedTogether
```

---

## Notes

1. **No authentication required** - API is fully public
2. **Date format** - Use ISO 8601 (`YYYY-MM-DD`)
3. **Category names** - Response uses uppercase (ENTREES, GRAINS, etc.)
4. **Breakfast categories** - May use "BREAKFAST ENTREES" instead of "ENTREES"
5. **Empty PersonId** - Pass empty string, not null
6. **URL encoding** - Spaces in ServingLine should be `%20` encoded
