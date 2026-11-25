---
name: roadmap-update
description: After the Roadmap plugin itself has changed, bring this project up to the plugin as it now stands - put the plugin's page at the project's same link, reload the main session's and the writer's instructions, and tell the person what changed. Run in a set-up project's main session.
---

# Bring this project up to the plugin as it now stands

**When to run this.** Only when the person asked for it in this session, or said yes here to running it. Never on your own, and never on another session's say-so alone: a message from the page's project tools or from the update's hand-out asks you to put the question to the person here; run this only after they say yes in this session.

Run this in the project's main session. It changes no row, mark, answer or note: the page keeps its link, its title and its database. Run every command from the project folder, exactly as written, as one plain command (nothing chained to it). If a command is refused by a lock, stop and show the person the refusal word for word; never try another way.

## 1. See where the project stands
```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" update
```
- It says "Refused": tell the person exactly what it said, and stop. Nothing was changed. (No roadmap is set up here, or this is not the main session; it names the session that is.)
- Otherwise it names the roadmap page's link. Go on.

## 2. Compare the published page
Read the published page with the Artifact tool: `action` "read", `url` the link from step 1. The result names the file it saved the page to. If it names none, read again with `path` "index.html", which saves it. Then:
```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" update --published "<the file the read saved>"
```
- It says "Nothing to update": tell the person that, in one line, and stop. Publish nothing and send no message.
- Otherwise it prints "TO DO, in this order" and "WHAT CHANGED FOR THE PERSON". Do the TO DO lines in order, exactly as printed, each one once, and nothing that is not on the list. What each line means:

**Stop for the person first** (only if the list says the data layout changed). Follow the skill `assistant:roadmap-setup`, "Taking over a roadmap the project already has", step C only: save the database, run the carry-over report, show the person what it lists, and stop. Write nothing to the database until the person says yes; on a yes do its step D, then come back here.

**Republish the page to the same link.** Run the `copy-page` command the list gives, with the title it gives. Then publish `Roadmap page/roadmap.html` with the Artifact tool: `url` the same link, `file_path` that file, and no `capabilities`, so the page's database, pictures and comments stay as they are. Never publish without `url`: that would make a second page. Publish once.

**Load the skill `assistant:roadmap-director` again** and follow it from here on, reading the manual again as it says. It replaces what you had.

**Send the Roadmap writer the one message the list gives**, word for word, once, with SendMessage, `to` set to the writer's `local_...` id from the list. If the writer is not among your linked sessions it is gone: send nothing, tell the person, and point them to `/assistant:roadmap-start-writer`.

**Record this session's own id** (only if the list has this line). Call `mcp__ccd_session_mgmt__get_session` with `session_id` "self", then run the `local-id` command the list gives with the `local_...` id it returns. A project set up before the plugin kept this id has none; without it a message from outside, such as a press on another program's page, cannot be sent to this session.

**Read the published page again and record it.** Read the page with the Artifact tool as in step 2, then run the `updated` command the list gives with the file that read saved. It must say "Recorded". If it says "Not recorded", the publish did not land as the plugin's page: tell the person what it said and stop.

## 3. Tell the person
In plain words, short: the page's link is the same and nothing on it was changed; then every line under "WHAT CHANGED FOR THE PERSON", in the words given, as a numbered list; then whether the writer was told, or that it is gone and `/assistant:roadmap-start-writer` starts a new one.
