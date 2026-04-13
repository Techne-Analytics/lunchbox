---
name: sync-debug
description: Debug SchoolCafe menu sync failures — check logs, test menu client, diagnose issues
disable-model-invocation: true
---

# Sync Debug

Diagnose and fix SchoolCafe menu sync failures. The SchoolCafe API is external and fragile — schema drift and silent failures are common.

## Steps

1. **Check recent sync logs** — look at the `sync_log` table for recent entries:
   - Query for failed syncs or syncs with 0 items
   - Note any error messages or patterns

2. **Check Vercel function logs**:
   ```bash
   vercel logs https://lunchbox-ebon.vercel.app/api/sync/cron --limit 20
   ```

3. **Test the menu client directly** — read `src/lunchbox/sync/menu_client.py` and `src/lunchbox/sync/providers.py`, then:
   - Check if SchoolCafe endpoints are responding
   - Verify the response shape matches what the parser expects
   - Look for schema drift (new fields, changed structure, different date formats)

4. **Test the sync engine** — read `src/lunchbox/sync/engine.py` and check:
   - Are subscriptions active and pointing to valid schools?
   - Is the upsert logic handling duplicates correctly?
   - Are there transaction/connection issues (NullPool + Neon)?

5. **Run unit tests** to confirm baseline:
   ```bash
   pytest tests/unit/test_menu_client.py tests/unit/test_sync_engine.py -v
   ```

6. **Diagnose and fix** — based on findings:
   - If schema drift: update parser in `menu_client.py`, add defensive parsing
   - If connection issues: check Neon status, verify DATABASE_URL
   - If auth issues: verify CRON_SECRET matches Vercel config

7. **Report** — summarize root cause and fix applied.

## Key Files

- `src/lunchbox/sync/menu_client.py` — SchoolCafe HTTP client and parser
- `src/lunchbox/sync/engine.py` — sync orchestration and upsert logic
- `src/lunchbox/sync/providers.py` — provider configuration
- `src/lunchbox/api/sync.py` — cron endpoint (auth: `Authorization: Bearer <CRON_SECRET>`)
- `src/lunchbox/models/` — ORM models including `sync_log`
