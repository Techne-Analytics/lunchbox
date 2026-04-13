---
name: create-migration
description: Generate and apply an Alembic migration against Neon Postgres via Vercel env vars
disable-model-invocation: true
---

# Create Migration

Generate an Alembic migration for Neon Postgres. This workflow handles the Vercel env var dance required for Neon's unpooled connection.

## Steps

1. **Confirm the migration purpose** — ask what schema change is needed if not already clear.

2. **Pull Vercel env vars**:
   ```bash
   vercel env pull .env.vercel
   ```

3. **Source the env and generate migration**:
   ```bash
   source .env.vercel
   alembic revision --autogenerate -m "<description>"
   ```

4. **Review the generated migration** — read the new file in `alembic/versions/` and verify:
   - Only expected changes are present (no spurious diffs)
   - Downgrade path is correct
   - No data-destructive operations without explicit user approval

5. **Apply the migration**:
   ```bash
   source .env.vercel
   alembic upgrade head
   ```

6. **Clean up secrets**:
   ```bash
   rm .env.vercel
   ```
   NEVER commit `.env.vercel`.

7. **Report** — show the migration file path and summary of changes applied.

## Gotchas

- Always use the **unpooled** connection URL for migrations (Vercel's `DATABASE_URL` from env pull should be unpooled)
- Use `printf` not `echo` when piping values to `vercel env add` (echo adds trailing newline)
- NullPool is required in `db.py` for serverless — don't change pool settings in migrations
