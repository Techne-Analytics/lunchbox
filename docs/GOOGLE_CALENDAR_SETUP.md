# Google Calendar OAuth Setup for n8n

This guide walks you through setting up Google Calendar API access in n8n.

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" at the top
3. Click "NEW PROJECT"
4. Enter project name: "n8n-school-menu" (or any name you prefer)
5. Click "CREATE"

## Step 2: Enable Google Calendar API

1. In the Google Cloud Console, make sure your new project is selected
2. Go to "APIs & Services" → "Library" (left sidebar)
3. Search for "Google Calendar API"
4. Click on "Google Calendar API"
5. Click "ENABLE"

## Step 3: Configure OAuth Consent Screen

1. Go to "APIs & Services" → "OAuth consent screen" (left sidebar)
2. Select "External" user type
3. Click "CREATE"
4. Fill in required fields:
   - **App name:** n8n School Menu
   - **User support email:** Your email
   - **Developer contact email:** Your email
5. Click "SAVE AND CONTINUE"
6. On "Scopes" page, click "ADD OR REMOVE SCOPES"
7. Search for "Google Calendar API"
8. Select: `https://www.googleapis.com/auth/calendar` (full calendar access)
9. Click "UPDATE" then "SAVE AND CONTINUE"
10. On "Test users" page, click "ADD USERS"
11. Add your Google email address
12. Click "SAVE AND CONTINUE"

## Step 4: Create OAuth Credentials

1. Go to "APIs & Services" → "Credentials" (left sidebar)
2. Click "CREATE CREDENTIALS" → "OAuth client ID"
3. Select "Web application"
4. Name: "n8n OAuth Client"
5. Under "Authorized redirect URIs", click "ADD URI"
6. Add: `http://localhost:5678/rest/oauth2-credential/callback`
   - If your n8n is on a different URL/port, adjust accordingly
7. Click "CREATE"
8. **IMPORTANT:** Copy the "Client ID" and "Client Secret" that appear
   - Save these somewhere safe - you'll need them in the next step

## Step 5: Configure n8n Google Calendar Credentials

1. Open your n8n instance at `http://localhost:5678`
2. Go to "Settings" (gear icon) → "Credentials"
3. Click "Add Credential"
4. Search for and select "Google Calendar OAuth2 API"
5. Fill in the form:
   - **Credential Name:** School Menu Calendar
   - **Client ID:** Paste from Step 4
   - **Client Secret:** Paste from Step 4
6. Click "Connect my account"
7. You'll be redirected to Google sign-in
8. Sign in with your Google account
9. Click "Allow" to grant permissions
10. You'll be redirected back to n8n
11. Click "Save"

## Step 6: Find Your Calendar ID

You need the Calendar ID for the calendar where you want to add events.

### Option A: Use the iCal link you provided
From your iCal URL: `https://calendar.google.com/calendar/ical/9f867f13c96a005bbc667c7093806b5eff527dfddee1f95718dccad8e83ab2a0%40group.calendar.google.com/private-faf77a9102bd867db83b0d0ac1d82401/basic.ics`

The Calendar ID is: `9f867f13c96a005bbc667c7093806b5eff527dfddee1f95718dccad8e83ab2a0@group.calendar.google.com`

### Option B: Find it manually
1. Go to [Google Calendar](https://calendar.google.com)
2. Find the calendar in the left sidebar
3. Click the three dots next to it → "Settings and sharing"
4. Scroll down to "Integrate calendar"
5. Copy the "Calendar ID"

**Note:** If you want to use your primary calendar, the Calendar ID is just your Gmail address.

## Step 7: Test the Connection

1. In n8n, create a new workflow
2. Add a "Manual Trigger" node
3. Add a "Google Calendar" node
4. Select your "School Menu Calendar" credentials
5. Set operation to "Get All"
6. Set Calendar ID to the ID from Step 6
7. Click "Execute node"
8. If you see calendar events (or an empty array), the connection works!

## Troubleshooting

### "Access blocked: This app's request is invalid"
- Make sure you added your email as a test user in Step 3
- Check that the redirect URI exactly matches in both Google Cloud and n8n

### "Error: invalid_grant"
- Credentials may have expired
- Delete and recreate the credential in n8n
- Go through the OAuth flow again

### "403: Access Not Configured"
- Google Calendar API is not enabled
- Return to Step 2 and enable the API

### "Calendar not found"
- Check that the Calendar ID is correct
- Make sure the Google account you authenticated with has access to that calendar

## Security Notes

- Keep your Client ID and Client Secret secure
- Don't commit them to version control
- The OAuth token is stored securely in n8n's database
- You can revoke access anytime at [Google Account Permissions](https://myaccount.google.com/permissions)

## Next Steps

Once setup is complete, you can use the Google Calendar credentials in your school menu workflow!
