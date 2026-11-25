---
name: update
description: Bring the assistant (and the roadmap parts of the plugin) up to date, going through the person's own changes with them first. Only when the person types /assistant:update.
disable-model-invocation: true
---

# Bring the assistant up to date

Run every command exactly as written, one at a time, with the Bash tool (never PowerShell: it drops the quote marks inside answers). If a command is refused by a lock or by the assistant's guardrails, stop and show the person the refusal word for word.

## Which assistant
Find it as `${CLAUDE_PLUGIN_DATA}/setup_texts/interview.md`, "Starting", step 1 says: the folder this session is open in, then the folders in `${CLAUDE_PLUGIN_DATA}/roots.json`. If none is found, say the assistant is not set up on this computer (/assistant:setup comes first) and stop. Call its folder ROOT below, written with forward slashes and no slash at the end (for example C:/Users/robin/Documents/Assistant); the person's data is ROOT/Live.

`HELPER <what> [details]` below and in the texts it points to means, as `interview.md` "The helper" says:
`python "${CLAUDE_PLUGIN_DATA}/engine/System/live/setup/setup_home.py" --root "<ROOT>" <what> [details]`

## 1. Fetch the newest plugin
```
claude plugin marketplace update assistant
```
```
claude plugin update assistant@assistant
```
If the second says a newer version was installed: tell the person "Close the Claude app completely, open it again, and send /assistant:update once more." and stop.

## 2. The walk-through
Read `${CLAUDE_PLUGIN_DATA}/setup_texts/update.md` and follow it from "The walk-through", step 1. It says what the update brings (from the change list in `${CLAUDE_PLUGIN_DATA}/docs/changes.md`), goes through each of the person's own changes with them, and asks for their yes.

## 3. Writing the update (the walk-through's step 5 calls this "the update skill's own step")
Only after the person's yes in the walk-through, and after `HELPER update-choices` has written the choices file:
```
python "${CLAUDE_PLUGIN_DATA}/scripts/assistant.py" update-apply --root "<ROOT>" --choices "<ROOT>/Live/changes/update-work/choices.json"
```
It saves the old copy and the database first, writes the new version and the kept changes together, checks that the program loads and the page answers (it runs no pass), and puts everything back by itself if any step fails. A pass is run by hand when wanted: `python "${CLAUDE_PLUGIN_DATA}/scripts/assistant.py" check-pass --root "<ROOT>"` stops the page for it, runs one pass, starts the page again and says the pass's line. Tell the person its last line, then carry on with the walk-through's step 5 (on success, `HELPER update-after "<version>"`).

If it says "Nothing to update", this copy already matches the plugin file for file: say so in one line. The same version number with files that differ is still an update, and it goes through.

## 4. Your other sessions
Only after the update succeeded (and the walk-through's step 5 is done). Every other Claude session on this computer needs a reload to pick up the new commands and checks, which only the person can type in it; a roadmap project's main session also brings its roadmap up to the plugin. Nothing is sent without the person's yes.

1. Get the sessions: call `mcp__ccd_session_mgmt__list_sessions` (limit 100) and write what it returns, unchanged, to `${CLAUDE_PLUGIN_DATA}/hand-out/sessions.json` with the Write tool; call `mcp__ccd_session_mgmt__get_session` with `session_id` "self" for this session's own `local_...` id. If those tools are not in this session (outside the desktop app), skip the file and the id.
2. Run (leave out `--sessions` and `--here` when step 1 was skipped):
```
python "${CLAUDE_PLUGIN_DATA}/scripts/hand_out.py" plan --root "<ROOT>" --sessions --here "<this session's local id>"
```
3. If it has no rows and nothing under `left`, say nothing about other sessions and stop. When `ask` is empty (nothing can be sent from here), show the lines under `left` and stop. Otherwise show each row's `line`, one per line, then its `ask` word for word, and end your reply.
4. On the person's answer, run:
```
python "${CLAUDE_PLUGIN_DATA}/scripts/hand_out.py" pick --answer "<their answer, word for word>"
```
   Send each row under `send` its `message`, word for word, once, with SendMessage, `to` set to the row's `id`. Send nothing else and to no one else; an empty `send` means nothing is sent.
5. End with one line per row: its `if_sent` line when it was sent, its `if_not_sent` line when not, then each line under `left`. When a session reports back later, tell the person in one line what it said.
