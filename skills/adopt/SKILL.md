---
name: adopt
description: Move an assistant someone already runs (from before this plugin) onto the plugin in place, keeping everything it knows, with a few minutes without its page and a one-step way back. Use when the person types /assistant:adopt, or asks to take back such a move.
disable-model-invocation: true
---

# Taking over an assistant you already run

This moves an existing assistant (a folder holding its program, "System", and everything it knows, "Live") onto the plugin. Its cards, rules, people, settings, sign-ins and page password are kept as they are. Its page is away for a few minutes while the switch happens. Nothing changes until the person says a clear go.

## How you talk
Follow the rules in `${CLAUDE_PLUGIN_DATA}/setup_texts/interview.md`, "How you talk", every turn: plain words, one question at a time, open questions answered in their own words (numbered choices only for a pick between set options), one line for what just happened and one for what is next, never guess. Never show a place on the computer as C:\...; say it plainly ("the Assistant folder in your Documents"). Read that section first. If the file is not there, ask them to quit Claude completely (right-click its icon near the clock, "Quit"), open it again and type /assistant:adopt once more.

## The helper
`HELPER` below means: `python "${CLAUDE_PLUGIN_DATA}/scripts/assistant.py"`. Run each one as one plain command, exactly as written, with the Bash tool (never PowerShell: it drops quote marks), and read what it prints. Write OLD and NEW with forward slashes and no slash at the end (for example C:/Users/robin/Documents/Assistant). If a command is refused (by a lock or by the assistant's guardrails), stop and tell them the refusal word for word.

If they ask to go back after a move ("way back", "undo the move", "put it back"), skip to "The way back".

## 1. Say what this does
In three or four short lines: their assistant moves onto the plugin; everything it knows is kept; its page is away for a few minutes during the switch, at a time they choose; nothing changes until they say go; there is a one-step way back; they can stop at any time and type /assistant:adopt again later.

## 2. Find their assistant
If the folder this session is open in holds both a "System" folder (with "live" inside) and a "Live" folder, that is it: say so in one line and ask "Is this your assistant? 1 yes, 2 it's somewhere else." Otherwise ask them to open the folder that holds "System" and "Live" in File Explorer, click the address bar at the top, copy it and paste it here. Check both are there before going on. Call it OLD below.

## 3. Choose where it will live
Follow `${CLAUDE_PLUGIN_DATA}/setup_texts/folder.md` whole, with OLD as "where it is now". The folder confirmed there is NEW. If NEW is OLD itself, the assistant stays where it is and only its program is replaced: say so in one line, and everywhere below "the move" means only that.

## 4. Look at the plan
`HELPER adopt-plan --from "OLD" --root "NEW"`
Say in plain words: how many of its parts are already the same as the plugin's, how many the plugin adds, how many are its own and will be kept, and how many differ from the plugin's.

For each part that differs (the list "differ"), one at a time: read the old one (`OLD\<that part>`) and the plugin's (`${CLAUDE_PLUGIN_DATA}\engine\<that part>`) and say in one or two plain lines what is different. If the only difference is the names of the roadmap commands (an old "roadmap:" name where the plugin says "assistant:roadmap-"), say so and recommend the plugin's. Ask: "1 keep yours, 2 take the plugin's, 3 combine both." For 3, write the combination in the plugin's own folder, `${CLAUDE_PLUGIN_DATA}/adopt-combined/<that part>` (never inside OLD, where it would be taken for one of their own parts), show in plain lines what it does, and use it only on their yes.
Keep the answers in a small file in the plugin's own folder, `${CLAUDE_PLUGIN_DATA}/adopt-choices.json` (never inside OLD: the switch stops every program whose command line names OLD's data folder): `{"<that part, exactly as listed>": "mine" | "new" | "<the full place of the combined file>"}`, every place written with forward slashes (a backslash breaks the file).

## 5. Count what is on the page now
`HELPER status --root "OLD"`
Note "cards" and "cards_open". Say "Your page has <cards_open> open cards right now; I'll check the same number is there after."

## 6. The go
Say back, in a few plain lines: where it is now, where it will live, what happens to the parts that differ, that its page will be away for a few minutes (longer if it has a lot of new mail to read: the switch reads once to check everything works), and that the old program is left where it is as the way back.
Ask: "Shall I make the switch now? 1 yes, go, 2 not now." Go on only on a clear yes to this question. Anything else: stop and say nothing has changed.

## 7. The switch
`HELPER adopt --from "OLD" --root "NEW" --choices "${CLAUDE_PLUGIN_DATA}/adopt-choices.json"`
(Leave out `--choices` if nothing differed.) It stops the old one, moves everything it knows into NEW (a quick move, nothing copied), lays down the plugin's program, reads once to check, and starts the new one in the background. Tell them, in plain words, what it says. If it says the switch failed: say which step and why, that everything is back as it was and the old one is running again, and stop.

## 8. Checks after
`HELPER status --root "NEW"`
Check and say each in one line:
1. Both things Windows starts by itself in the background are on ("jobs" lists two).
2. The page answers on this computer ("page_answers" true). Ask them to open it in their browser and say whether it looks right.
3. The check read ended well ("last_pass" is "ok").
4. The open cards are the same number as before ("cards_open"). If not, say both numbers plainly.
5. If they open their page on their phone (reach from anywhere), ask them to open it there now: "Does your page open on your phone? 1 yes, 2 no." The page kept its place, so its phone address is the same.
If any check fails, say which, and offer: "1 look into it together, 2 go back to how it was (the way back)."

Finish: everything works; the old program is left unused in OLD as the way back, and can be put away later; from now on they use /assistant:update for updates and the plugin's commands in a Claude session opened in NEW.

## The way back
Say what it does: stops the new one, moves everything back to where it was, and starts the old one again; the plugin's program is left unused in NEW. Ask "Go back now? 1 yes, 2 no." On a clear yes:
`HELPER adopt-back --root "NEW"`
Tell them what it says, then check the old page answers (`HELPER status --root "OLD"`, "page_answers"), and ask them to look at it.
