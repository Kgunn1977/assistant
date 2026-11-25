# Connecting Gmail, Google work mail, and Google Calendar

For Claude: walk these steps one at a time. Each step ends with a mark in square brackets saying where its screen names come from; never read the marks out. "docs" means the provider's own help page (sources at the end), checked 11/16/26; "unconfirmed" means no official page names it, so if the screen differs, believe the screen and tell the person what you expected. Nobody checked these steps on a live screen yet.

This is the assistant's own Google connection. It serves several Google accounts from one registration: register once (part A, about 15 minutes), then each mailbox or calendar is one sign-in (part B, about a minute each). Every Google account the person adds later skips part A.

## Before part A: say this

"Google only hands mail to a program registered with it. You register your own, for free; nobody else can use it. You do the clicking in your own browser; I tell you each click." If `HELPER account-kinds` says this kind does not need registration, part A is already done: go to part B.

## Part A: register once

1. Open console.cloud.google.com and sign in with your Google account. If it asks you to agree to terms, agree. [unconfirmed]
2. Make a project: open the menu at the top left, then "IAM & Admin", then "Create a Project". Name it "My assistant" and click "Create". When it is made, make sure it is the project picked at the top of the page. [docs: G-project]
3. Turn on Gmail: in the search bar at the top type Gmail API, click "Gmail API" in the results, then click "Enable". Do the same for "Google Calendar API" (needed for calendars). [unconfirmed: the button name; the step itself is in docs: G-quickstart]
4. Open the menu, then "Google Auth platform", then "Branding". If it says "Google Auth platform not configured yet", click "Get Started". [docs: G-consent]
5. On "App Information": App name "My assistant"; User support email: pick your own address. Click "Next". [docs: G-consent]
6. On "Audience": choose "External" and click "Next". (If every account you will connect is in one Google work organization and you see "Internal", you may choose that instead and skip steps 9 and 10.) [docs: G-consent]
7. On "Contact Information": your email address, "Next". [docs: G-consent]
8. On "Finish": tick that you agree to the Google API Services User Data Policy, click "Continue", then "Create". [docs: G-consent]
9. In the left menu click "Audience". Under "Test users" click "Add users", add every Google address you will connect, and click "Save". [docs: G-consent]
10. Still on "Audience", click "Publish app" and confirm, so the status says "In production". This matters: left in testing, Google ends your sign-in every 7 days. [docs: G-publish]
11. In the left menu click "Clients", then "Create Client". Application type: "Desktop app". Name: "My assistant". Leave the box "Use this client for an AI-powered agent" unticked. Click "Create". [docs: G-client]
12. A box shows "Client ID" and "Client secret". Google shows the secret only this once, so keep that box open. [docs: G-secret]
13. Tell me the "Client ID" here (it ends in .apps.googleusercontent.com; it is not secret). Claude then runs `HELPER connect google_mail '{"client_id": "..."}'` (or `google_calendar`), and a small window opens for the "Client secret": paste it there, not in this chat. If the box was closed and the secret lost: on the client's page click "Add Secret" and use the new one. [docs: G-secret]

## Part B: each mailbox or calendar

14. Your browser opens Google's own sign-in page. Pick the account you want. [unconfirmed]
15. Google warns that it has not verified this app. That is expected: the app is your own. Click "Advanced", then "Go to My assistant (unsafe)". [unconfirmed: only third-party pages describe these two buttons]
16. Tick every box Google lists (read mail, send mail, or see calendars) and click "Continue". Your password goes only to Google; your assistant never sees it. [unconfirmed]
17. The browser says "Signed in." Close that tab. Claude tells you whether the check read the account. [the assistant's own step: no outside screen]
18. For more Gmail or Google work accounts: repeat 14 to 17 for each (`HELPER connect google_mail '{}'`). Each must be in the test users from step 9. [the assistant's own step: no outside screen]

Calendar: connect it the same way with `google_calendar`. Afterwards Claude asks which calendars show under Today.

## If something goes wrong

- "Access blocked: My assistant has not completed the Google verification process": the address is not in the test users (step 9), or the app is not published (step 10).
- "Access blocked: admin policy" on a work account: the organization limits outside apps. Its Google administrator must allow your Client ID.
- Google may limit an unverified app to 100 users in its whole life. A personal assistant has one user, so this does not matter. [docs: G-verify]
- Later the page says "sign this account in again": type /assistant:change accounts and choose "sign one in again".

## Sources

- G-project: https://developers.google.com/workspace/guides/create-project
- G-quickstart: https://developers.google.com/gmail/api/quickstart/python
- G-consent: https://developers.google.com/workspace/guides/configure-oauth-consent
- G-publish: https://support.google.com/cloud/answer/15549945 and https://developers.google.com/identity/protocols/oauth2#expiration
- G-client: https://developers.google.com/workspace/guides/create-credentials
- G-secret: https://support.google.com/cloud/answer/15549257
- G-verify: https://support.google.com/cloud/answer/13463073
