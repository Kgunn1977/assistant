# Change something set on the computer

Before anything, read `interview.md` (in the same folder as this file): its sections "How you talk" and "The helper", including "Steps that need the computer". Talk exactly that way and use that helper the same way; `HELPER` below means the same command, with the same ROOT (find the assistant as `interview.md`, "Starting", step 1 does: the folder this session is open in, then the folders in `${CLAUDE_PLUGIN_DATA}/roots.json`; never lay it down from here: if it is not on this computer, say /assistant:setup comes first, and stop).

If the person typed a word after /assistant:change, go straight to that part. Otherwise ask: "What would you like to change? 1 your accounts, 2 where your page can be opened, 3 what I may send, 4 read further back, 5 switch me on, 6 how I work or look, 7 undo a change made before." For 6 (or a word like program, works, looks, rule), follow `change-program.md` (in this folder). For 7 (or undo), follow its section 7. Do one part, end with one line saying what changed, then ask "Anything else to change? 1 yes, 2 no."

Every choice list below leaves out what is already true and is numbered afresh from 1.

## accounts

1. `HELPER accounts`. Say what is connected now, numbered, one line each. Then: "1 connect another account, 2 sign one of these in again, 3 remove one." With none connected, say so and go straight to connecting one.
2. Connect another **[at the computer]**: do the interview's step 2 for one account, the whole way including the check (its guides are in `guides/` beside this file). Do not ask "Another account?" or save `accounts`; one is done. If it was a calendar, ask which calendars show under Today (`HELPER calendar-choices`, then `HELPER answer calendars '[...]'`).
3. Sign in again **[at the computer]**: say their browser will open the provider's own sign-in page, then `HELPER connect <its type> '{"id": "<its id>"}'`. It reads the account once to check; say the result.
4. Remove: name the account and say what removing does: "I stop reading it the next time I check for messages. What I already read stays in my history. Nothing in the account itself changes." Ask "Remove <its name>? 1 yes, 2 no." Only on yes: `HELPER remove-account <id>`, then `HELPER accounts` and say what is left.

It takes effect the next time I check for messages, within 15 minutes.

## page

1. `HELPER show page`. Say in one line how it is reached now: only on this computer, or from anywhere at its address.
2. Offer: "1 only on this computer, 2 from anywhere, your phone too, 3 check that it can be reached."
3. Only on this computer: say "Its address from outside stops working at once; on this computer nothing changes." Ask "Go ahead? 1 yes, 2 no." On yes: `HELPER answer page '"this_pc"'`.
4. From anywhere **[at the computer]**: do the interview's step 6, choice 2, all of it (`guides/tailscale.md`). If `HELPER reach-on` already answers that it is on, do not ask for an approval in the browser.
5. Check: `HELPER reach-check` and say the result. If it failed, say the matching line from the Tailscale guide's "If something goes wrong".

## sending

Say the rule once: nothing is sent without their approval, either in the moment (they press Send) or ahead of time (they said yes ahead to one kind of message).

1. `HELPER show sending` and `HELPER show standing_sends`. Say both, one line each.
2. Offer: "1 allow sending when you approve, 2 never send anything, 3 change the kinds I may send without asking." (3 only while sending is allowed.)
3. Allow: `HELPER answer sending true`.
4. Never: say "Then nothing can be sent at all, and any kinds you approved ahead end too. Go ahead? 1 yes, 2 no." On yes: `HELPER answer standing_sends '[]'`, then `HELPER answer sending false`.
5. Change kinds: read the current kinds back, numbered. Ask what to add or remove, in their words. Say the whole new list back and ask "Is this right? 1 yes, 2 no." On yes: `HELPER answer standing_sends '[...the whole new list...]'`.

## read-back

1. `HELPER show since`. Say how far back you have read ("I've read back to September 1."), or that you haven't yet.
2. Ask: "To which date should I read back now?" Take a real date, say it back and confirm, as the interview's step 5 does. A date later than the one it already read to needs nothing: say so and stop.
3. Do the interview's step 5, parts 2 and 3: the cost first, then their yes, then the reading and the one summary. Only after the reading finished: `HELPER answer since '"<date, year-month-day>"'`, then `HELPER answer readback '{...}'` as there.

## switch-on [at the computer]

From Talk to your assistant this part cannot start at all: the page only answers while you are switched on. Say so if asked there.

1. `HELPER show`. If `jobs_on` lists both, it is already on: say so and stop.
2. Ask the interview's `turn_on` question, word for word, and do what it says there (including opening the page for its password).
