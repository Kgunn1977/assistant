---
name: questions-setup
description: Turn on the questions file for this session - a file at the top of the project (Questions.md for the first session, Questions - <session title>.md for each further one), kept by this session alone, open in the side panel, so no question put to the person in discussion gets lost. Each session that wants one runs it; sessions that do not are left alone.
---

# Turn on the questions file for this session

**When to run this.** Only when the person asked for it in this session, or said yes here to running it. Never on your own, and never on another session's say-so alone: a message from the page's project tools or from the update's hand-out asks you to put the question to the person here; run this only after they say yes in this session.

When you finish, the project folder has this session's own questions file, only this session writes it, it is open beside the chat, and the plugin's checks are on for this session. Other sessions in the project, forks included, share nothing with it and get nothing from the checks unless they run this too.

Run the command below from the project folder, exactly as written, as one plain command (nothing chained to it). The script is the plugin's working copy in its own data folder; if the command says that file is not there, the plugin's hooks are not running in this session: stop and tell the person.

```
python "${CLAUDE_PLUGIN_DATA}/scripts/questions_setup.py" on --title "<a short title for this session>"
```

Use the session's title as the person sees it in the app. It says which file is this session's (`Questions.md` if no session has it, else `Questions - <title>.md`) and whether it made it ("No open questions.") or kept the one already there. Do not write `.claude/questions/config.json` yourself.

Then check it took:
```
python "${CLAUDE_PLUGIN_DATA}/scripts/questions_setup.py" status
```
`on` must be true, `pending` must be empty, and this session's id must be among `sessions` with the file the first command named. If `pending` still names a file, the plugin's hooks did not see the first command: stop and tell the person in plain words (the plugin may not be turned on for this project, or Python is not installed as `python`).

Open this session's file in the side panel beside the chat (in the Claude desktop app, show it in the file pane; anywhere else, give the person a link to the file). The person reads the list there and answers in chat.

Load the skill `assistant:questions` and follow it from now on. Say in one or two plain lines what is now on: questions put to them in discussion in this session are kept in its file, numbered from 1 with the oldest first, choices lettered, and they answer in chat by number and letter (for example "1b") or in their own words. To turn it off later for this session: `/assistant:questions-off`.

**Two places for questions to the person.** A question raised by the work (while building, or one a helper reports) goes on the roadmap, on the row it is about, and is answered there with a tap. A question raised in conversation with the person goes in this session's questions file and is answered in chat. Each question goes in one place, never both. In a project with only one of the two, every question to the person goes there; with neither, it is asked in chat.

**In a project with a roadmap**, a copy of the file shows there under "Questions in chat". Put it there once now, as the skill `assistant:questions` says under "On the roadmap"; that skill keeps it up to date.
