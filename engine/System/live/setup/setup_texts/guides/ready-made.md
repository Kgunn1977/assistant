# Connecting through Claude's ready-made connections

For Claude: walk these steps one at a time. Each step ends with a mark in square brackets saying where its screen names come from; never read the marks out. "docs" means Claude's own help pages (sources at the end), checked 11/16/26; "unconfirmed" means no official page names it, so believe the screen if it differs. Nobody checked these steps on a live screen yet.

Offer this way only for kinds that `HELPER account-kinds` marks `ready_made`. It works only once your assistant can read through these connections in the background; until the engine says so, no kind is marked and this guide is not used.

To say first: "Claude has ready-made connections to Gmail, Google Calendar and Microsoft 365. You switch one on in Claude once, and your assistant reads through it. Each read counts against your Claude plan, like a short chat."

## Switching one on

1. In your browser, open claude.ai and sign in with the same Claude account you use in the Claude app. [docs: C-connectors]
2. Open "Customize", then "Connectors" (or go straight to claude.ai/customize/connectors). [docs: C-connectors]
3. Find the one you want (for example "Gmail") and click "Connect". If it is not listed, click the "+" beside "Connectors" and look for it there. [docs: C-connectors]
4. A sign-in page from that company opens (Google or Microsoft). Sign in with the account you want your assistant to read, and allow what it asks. Your password goes only to that company. [unconfirmed: the company's own screens]
5. Back on claude.ai, it now shows as connected. Tell me. [unconfirmed]
6. Claude runs `HELPER connect-ready <its type>` (the `type` from the list of kinds). It reads once to check, and says whether it works. [the assistant's own step: no outside screen]

One ready-made connection reads one account. For a second Gmail or Google work account, use your assistant's own Google connection (`guides/google.md`), which takes as many as you like.

## If something goes wrong

- It shows as not connected, or asks to sign in again: on claude.ai, "Customize", "Connectors", click it and connect again. Then tell me, and Claude checks again.
- Your work account blocks it: its administrator limits outside apps. Use your assistant's own connection for that account instead.

## Not on the list

A kind of account your assistant cannot read at all yet: say plainly "Your assistant cannot read <that> yet." Do not promise it, and do not try another way round. Offer to go on with the next account. Record nothing for it.

## Sources

- C-connectors: https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities
