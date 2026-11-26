# Connecting Microsoft mail (work, school, or personal Outlook.com and Hotmail)

For Claude: walk these steps one at a time. Each step ends with a mark in square brackets saying where its screen names come from; never read the marks out. "docs" means Microsoft's own page (sources at the end), checked 11/16/26; "unconfirmed" means no official page names it, so believe the screen if it differs. Nobody checked these steps on a live screen yet.

This covers a mailbox at work or school that runs on Microsoft 365 and a personal outlook.com, hotmail.com or live.com mailbox. Every mailbox the owner has is read; connect each one.

## Before you start: say this

"Microsoft only hands mail to a program registered with it. You register your own, for free, about 10 minutes, once. Your company may not let staff do this; step 2 shows that, and then your IT person can do steps 2 to 8 for you and give you the two codes from step 5."

## Register once

1. Open entra.microsoft.com and sign in with your work email. [docs: M-register]
2. In the left menu click "Entra ID", then "App registrations", then "New registration" at the top. If it says you do not have access, your company blocks this: see "Before you start". [docs: M-register]
3. Name: "My assistant". Under "Supported account types" choose the one that includes personal Microsoft accounts ("Accounts in any organizational directory and personal Microsoft accounts"), so work and personal mailboxes both sign in. If the company allows only "Single tenant only", leave that: work mailboxes still connect. [docs: M-desktop]
4. Click "Register". [docs: M-register]
5. You are on the app's "Overview". Two lines matter: "Application (client) ID" and "Directory (tenant) ID". Tell me both here; they are not secret. With personal Microsoft accounts chosen in step 3, the tenant is "common" instead of the Directory (tenant) ID. [docs: M-register]
6. In the left menu click "Authentication", then "Add a platform", then "Mobile and desktop applications". Tick or type the address http://localhost and click "Configure". [docs: M-desktop]
7. Still under "Authentication", find "Allow public client flows" (under "Advanced settings", or on a "Settings" tab in the newer layout) and set it to "Yes". Click "Save". [docs: M-desktop for the setting; the "Settings" tab is unconfirmed, from third-party guides]
8. In the left menu click "API permissions", then "Add a permission", then "Microsoft Graph", then "Delegated permissions". Under "Select permissions" search Mail and tick "Mail.Read" and "Mail.Send"; search offline and tick "offline_access". "User.Read" is already there. Click "Add permissions". [docs: M-permissions]
9. Claude runs `HELPER connect microsoft_mail '{"client_id": "...", "tenant": "..."}'`. [the assistant's own step: no outside screen]

## Each mailbox

10. Your browser opens Microsoft's own sign-in page. Sign in with the mailbox and click "Accept" on the permissions page. Your password goes only to Microsoft. [unconfirmed]
11. The browser says "Signed in." Close that tab. Claude tells you whether the check read the mailbox. [the assistant's own step: no outside screen]

## If something goes wrong

- "Need admin approval": your company needs an administrator to approve. Give them the "Application (client) ID" and ask them to grant consent for Mail.Read, Mail.Send, User.Read and offline_access.
- Later the page says "sign this account in again" (often after a password change): type /assistant:change accounts and choose "sign one in again".

## Sources

- M-register: https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app (dated 5/14/26, updated 6/15/26)
- M-desktop: https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-configuration (updated 6/15/26)
- M-permissions: https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-configure-app-access-web-apis (updated 6/15/26)
