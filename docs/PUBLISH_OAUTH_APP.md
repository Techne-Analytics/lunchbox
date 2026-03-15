# Publishing Your OAuth App

**Goal:** Eliminate the 7-day OAuth token expiration by moving your app from "Testing" to "Published" status.

**Impact:** After publishing, your OAuth refresh token will last indefinitely instead of expiring every 7 days.

---

## Why This Matters

Google enforces strict limits on OAuth apps in "Testing" mode:
- **Refresh tokens expire after 7 days**
- Requires manual re-authentication every week

Published apps don't have this limitation:
- **Refresh tokens last indefinitely** (unless manually revoked)
- No periodic re-authentication needed

---

## Prerequisites

Before you begin, create a privacy policy URL. Google requires this for published apps.

### Option 1: Create a Simple Privacy Policy (Recommended)

1. Go to https://gist.github.com
2. Create a new public gist with filename `privacy-policy.md`
3. Paste this content:

```markdown
# School Menu Calendar - Privacy Policy

**Effective Date:** February 9, 2026

## What We Access
This application accesses your Google Calendar to create school menu events.

## What We Store
- OAuth credentials (stored locally on your server)
- No user data is transmitted to third parties
- No analytics or tracking

## Data Usage
Calendar access is used solely to create school menu events from SchoolCafe data.

## Data Retention
OAuth tokens are stored in `/docker/n8n/tasks_data/token.json` on your local server.
No data is sent to external services except:
- Google Calendar API (to create events)
- SchoolCafe API (to fetch menu data)

## Contact
This is a personal-use application. For questions, contact the application owner.
```

4. Click "Create public gist"
5. Copy the URL (e.g., `https://gist.github.com/yourusername/abc123`)

### Option 2: Host on GitHub Pages

If you prefer a proper URL, you can create a simple GitHub Pages site with your privacy policy.

---

## Step-by-Step: Publish Your OAuth App

### 1. Navigate to OAuth Consent Screen

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project (the one you created for Calendar API)
3. In the left sidebar, go to **APIs & Services** → **OAuth consent screen**

### 2. Review App Information

Ensure these fields are filled in:
- **App name** (e.g., "School Menu Calendar")
- **User support email** (your email)
- **Developer contact information** (your email)

### 3. Add Privacy Policy URL

1. Find the "App domain" section
2. Paste your privacy policy URL in the **Privacy policy link** field
3. (Optional) Add the same URL to **Terms of service link**

### 4. Publish the App

1. Scroll to the top of the page
2. You should see a button that says **"PUBLISH APP"**
3. Click **"PUBLISH APP"**

### 5. Handle the Verification Warning

Google will show a warning:

> **"Your app needs verification"**
> This app has not been verified by Google. Unverified apps may pose a risk to your personal data.

**You can IGNORE this warning** because:
- This is a personal-use app (only you will use it)
- You're not distributing it publicly
- You have fewer than 100 users (it's just you)

**Click "Confirm"** to proceed with publishing.

### 6. Verify Status Changed

After publishing, the OAuth consent screen should show:
- **Publishing status:** In Production (or Published)
- The warning "App needs verification" may still appear - **this is normal**

You do NOT need to go through Google's verification process for personal use.

---

## Step 3: Re-Authorize Your App

After publishing, you need to re-authorize once to get a new refresh token that won't expire.

### 1. Delete the Old Token

```bash
cd D:\docker\n8n
rm tasks_data\token.json
```

### 2. Run the Authorization Flow

```bash
docker compose run --rm -p 8080:8080 -e OAUTH_PORT=8080 -e OAUTH_BIND_HOST=0.0.0.0 -e OAUTH_REDIRECT_HOST=localhost tasks python app.py --authorize
```

### 3. Complete Authorization

1. The container will print an authorization URL
2. Open the URL in your browser
3. Sign in with your Google account
4. You may see a warning: **"Google hasn't verified this app"**
   - Click **"Advanced"**
   - Click **"Go to School Menu Calendar (unsafe)"**
   - This is normal for personal apps - you're authorizing your own app
5. Grant the requested permissions
6. You'll be redirected back automatically
7. The token is saved to `tasks_data/token.json`

### 4. Restart the Service

```bash
docker compose restart tasks
```

---

## Verification

Check the logs to ensure the new token is working:

```bash
docker compose logs tasks
```

You should see:
```
Scheduler started.
  - Menu sync: daily at 06:00 America/Denver
  - Credential refresh: daily at 05:00 America/Denver
  - Health check: daily at 05:30 America/Denver
```

No errors about credentials should appear.

---

## What Happens Now

With your app published and re-authorized:

1. **Automated monitoring** runs daily at 5:30 AM
   - Checks token health
   - Sends Discord alerts if issues detected

2. **Proactive refresh** runs daily at 5:00 AM
   - Refreshes access token before expiry
   - Prevents sync failures

3. **Menu sync** runs daily at 6:00 AM
   - Fetches menus for next 7 days
   - Creates/updates calendar events

4. **No more weekly re-authentication**
   - Your refresh token now lasts indefinitely
   - Only expires if you manually revoke access

---

## If You Still Get Expiration Alerts

If you continue receiving expiration alerts after publishing:

1. **Verify publishing status**
   - Go to OAuth consent screen
   - Confirm status is "In Production" or "Published"
   - Not "Testing"

2. **Check token was regenerated**
   - Verify you deleted old `token.json` and re-authorized
   - The new token should have been created after publishing

3. **Review token details**
   ```bash
   cat tasks_data\token.json
   ```
   - Look for `"refresh_token"` field
   - Should be present and non-empty

4. **Check Google Account permissions**
   - Go to https://myaccount.google.com/permissions
   - Verify "School Menu Calendar" appears with recent access date

---

## Troubleshooting

### "App needs verification" won't go away

This is normal. Google shows this warning for all unpublished apps, even after you click "Publish App". For personal use with <100 users, you can safely ignore this warning.

### Can't find "PUBLISH APP" button

Make sure:
- You're on the "OAuth consent screen" page (not Credentials)
- Your app is currently in "Testing" mode
- You've filled in all required fields (app name, support email, etc.)

### Browser shows "This app is blocked"

This means Google has restricted the app. To fix:
1. Go back to OAuth consent screen
2. Verify you're using an allowed scope: `https://www.googleapis.com/auth/calendar`
3. Remove any sensitive/restricted scopes if you added extras

### Token still expires after 7 days

Double-check:
1. OAuth consent screen shows "Published" or "In Production" (not "Testing")
2. You deleted the old token and re-authorized AFTER publishing
3. The new `token.json` was created after the publishing date

---

## Security Notes

- Your OAuth credentials are stored locally in `tasks_data/token.json`
- No credentials are transmitted to third parties
- The Discord webhook URL in the code should be kept private (it's in your docker-compose.yml)
- Your client_secret.json should never be committed to version control

---

## Need Help?

If you encounter issues during publishing:
1. Check the Google Cloud Console for error messages
2. Verify your Google account has permission to publish apps in the project
3. Review the logs: `docker compose logs tasks`
