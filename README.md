# Assistant

**The full manual:** [docs/Assistant manual.html](docs/Assistant%20manual.html). Download it and open it in your browser (GitHub shows it as text). Once set up, your page's Settings opens it too.

A Claude plugin for Windows. It gives you:

1. **An assistant** that runs on your own computer, reads your mail, messages and calendar every 15 minutes, and keeps one private page of what needs you, where you answer it.
2. **Roadmaps** for your projects: a live page per project that Claude keeps up to date while you work, which the assistant also shows on its page.

## What you need

- Windows 10 or 11.
- Python 3 from python.org, installed with "Add python.exe to PATH" ticked.
- The Claude desktop app, signed in on a paid plan, with the Code tab opened once.

## Install

In the Claude desktop app, open the Code tab, start a session in any folder, and send these two lines one at a time:

```
/plugin marketplace add Kgunn1977/assistant
```
```
/plugin install assistant@assistant --scope user
```

Close the Claude app completely and open it again. Then make a folder for your assistant (for example `Documents\Assistant`), open a Code tab session in it, and send:

```
/assistant:setup
```

Setup is an interview of about 30 minutes. Nothing runs in the background until its last step asks you and you say yes.

## Commands

| Command | What it does |
|---|---|
| `/assistant:setup` | First-time setup, as an interview |
| `/assistant:change` | Change a setting, or ask for a change to how your assistant works (also from Start beside Change in Settings, Tools, on your page) |
| `/assistant:introduce` | Introduce a project to the assistant |
| `/assistant:undo` | Undo a change you asked for to how your assistant works |
| `/assistant:adopt` | Move an assistant you already run onto the plugin, keeping everything it knows |
| `/assistant:update` | Bring everything up to date; your own changes are kept, and you choose where they meet the update |
| `/assistant:uninstall` | Take it off this computer |
| `/assistant:roadmap-setup` | Give a project a roadmap (send it in that project's folder) |
| `/assistant:roadmap-off` | Turn a project's roadmap off; its records are deleted and the page stays |
| `/assistant:roadmap-update` | Bring one project's roadmap page up to date |
| `/assistant:roadmap-start-writer` | Start a new Roadmap writer session for a project |
| `/assistant:questions-setup` | Keep this session's questions for you in its own file beside the chat (send it in that project's folder) |
| `/assistant:questions-off` | Stop this session's questions checks; its file stays |
| `/assistant:humanize-text` | Rewrite text so it reads as a person wrote it; every draft your assistant writes goes through it |

## Where things are

- The program runs from `Documents\Assistant\System` (or the folder you chose). Your data is in `Documents\Assistant\Live`. Nothing about you is ever in the plugin.
- One hidden background job, named "Assistant live listener ...", runs as you, with no admin rights: it serves your page and runs the 15-minute check. `/assistant:uninstall` removes it.

## Checking the roadmap blocks

```
python hooks/test_roadmap_blocks.py
```

It should end with every check passed.

## Checking for dead pointers

```
python tests/pointers_check.py
```

Silent and exit 0 when every "in Settings", "Settings, under X", "press X", "the X button" and "open the X section" in the page and its modules names something that exists; otherwise one line per bad message (file, line, missing name) and exit 1. `githooks/` holds a pre-commit and a pre-merge-commit hook that run it and refuse the commit when it fails (a squash merge ends in a commit, so it fires). Install once per clone, in the clone where squashing happens: `python githooks/install.py` (sets `core.hooksPath` to `githooks`; it is shared by every worktree of that clone). `python tests/pointers_acceptance.py` proves the check itself.
