---
name: change
description: Change something about the assistant - its accounts, where its page can be opened, what it may send, reading further back, switching it on, or how the assistant itself works or looks (a change to its program, talked through and checked before it is made, and undone by itself if it fails). Use when the person types /assistant:change (optionally followed by accounts, page, sending, read-back, switch-on or program), or asks for one of these.
disable-model-invocation: true
---

# Change something set on the computer

Read the file `${CLAUDE_PLUGIN_DATA}/setup_texts/change.md` whole and follow it. If the person typed a word after /assistant:change, it names the part to go to. If the file is not there, ask the person to close the Claude app completely (right-click the Claude icon near the clock, "Quit"), open it again and type the same thing once more; if it is still missing, say plainly that the assistant's parts are missing on this computer and stop.
