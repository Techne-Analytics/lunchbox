# School Lunch Menu to Google Calendar

Automated n8n workflow that fetches school lunch menus from schoolcafe.com/DPS and creates Google Calendar events.

## What This Does

Every day at 6:00 AM, this workflow:
1. Fetches lunch and breakfast menus for the next 7 school days from schoolcafe.com/DPS
2. Filters out unwanted categories (Milk, Condiments) and always-available items (PB&J)
3. Creates separate all-day Google Calendar events with menu details
4. Skips weekends and non-school days (when no menu data exists)
5. Updates existing events if menus change

## Example Calendar Event

**Title:** `Lunch: Chicken Nuggets, Grilled Cheese Sandwich, Focaccia, Carrots, Apple`

**Description:**
```
**Entrees:**
- Chicken Nuggets
- Grilled Cheese Sandwich

**Grains:**
- Focaccia

**Vegetables:**
- Carrots

**Fruits:**
- Apple
```

## Quick Start

1. **Set up Google Calendar OAuth** → See [GOOGLE_CALENDAR_SETUP.md](./GOOGLE_CALENDAR_SETUP.md)
2. **Import and configure workflow** → See [WORKFLOW_SETUP.md](./WORKFLOW_SETUP.md)
3. **Test with a single date** → Follow testing steps in WORKFLOW_SETUP.md
4. **Enable daily automation** → Activate the workflow

## Python Task Runner (Alternative)

If you prefer not to use n8n, a Dockerized Python scheduler is available:
- **[TASKS_PYTHON.md](./TASKS_PYTHON.md)** - setup and usage

## Files

- **[2026-01-19-school-lunch-menu-workflow-design.md](./plans/2026-01-19-school-lunch-menu-workflow-design.md)** - Detailed design document
- **[GOOGLE_CALENDAR_SETUP.md](./GOOGLE_CALENDAR_SETUP.md)** - Step-by-step Google Calendar OAuth setup
- **[WORKFLOW_SETUP.md](./WORKFLOW_SETUP.md)** - Workflow import, configuration, and testing guide
- **[../workflows/school-lunch-menu-calendar.json](../workflows/school-lunch-menu-calendar.json)** - n8n workflow JSON file

## Configuration

Current settings (configured for Shoemaker Elementary):
- **School:** Shoemaker
- **Grade:** 05
- **Meal Types:** Lunch and Breakfast (Lunch first)
- **Line:** Traditional Lunch (Lunch), Traditional Breakfast (Breakfast)
- **Schedule:** Daily at 6:00 AM
- **Lookahead:** Next 7 days
- **Calendar ID:** `9f867f13c96a005bbc667c7093806b5eff527dfddee1f95718dccad8e83ab2a0@group.calendar.google.com`

To customize, edit the "Generate Next 7 Days" node in the workflow.

## Requirements

- n8n instance running
- Scraper service with browser automation (Puppeteer), reachable from n8n (`SCRAPER_BASE_URL`)
- Google Calendar API access
- Google Calendar OAuth credentials configured

## Known Limitations

1. **Site-specific:** Workflow is built for schoolcafe.com/DPS structure
   - If site changes, selectors may need updates

2. **Scraper endpoint:** Assumes the scraper service is running
   - Adjust `SCRAPER_BASE_URL` if you change the service URL

3. **Slow site:** schoolcafe.com can be very slow
   - Workflow uses 20-25 second wait times
   - May need adjustment based on site performance

4. **Breakfast line may differ:** Adjust the breakfast line in the workflow settings if your school uses a different label

## Troubleshooting

### Workflow not extracting menu data
- Check that schoolcafe.com site structure hasn't changed
- Verify the scraper service is running and accessible
- Review browser automation script selectors

### Calendar events not created
- Verify Google Calendar OAuth credentials
- Check Calendar ID is correct
- Ensure you have write access to the calendar

### Duplicate events
- Workflow attempts to detect duplicates
- If menu changes, titles change, so new events are created
- Manually delete duplicates if needed

## Future Enhancements

- [ ] Email notifications on workflow failures
- [ ] Menu change detection and notifications
- [ ] Support for multiple schools/grades
- [ ] Better duplicate detection
- [ ] Retry logic for failed menu fetches

## Support

For issues or questions:
1. Check the troubleshooting sections in docs
2. Review n8n execution logs for errors
3. Test manually to isolate issues

## License

This workflow is provided as-is for personal use.
