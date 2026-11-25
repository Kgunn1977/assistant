---
name: talk
description: Make this Claude session the same conversation as Talk to your assistant, the box at the top of the assistant's page - what is said here shows there and what is said there is read here. Use when the person types /assistant:talk in a session opened in the assistant's folder, or presses Open in the Claude app on the page.
disable-model-invocation: true
---

# Join Talk to your assistant

This works only in the assistant's own folder (the one whose CLAUDE.md starts "# This folder is your assistant"). If this session is somewhere else, say in one line that it must be opened in the assistant's folder (the page's Open in the Claude app button does that) and stop.

Run from the assistant's folder, exactly as written, as one plain command:

```
python System\live\desk.py join
```

Say the line it prints, as it is. If it says the session could not be joined, add that the assistant plugin may need the Claude app restarted (right-click the Claude icon near the clock, "Quit", open it again) and stop.

Once joined, this session is the assistant of that folder's CLAUDE.md: follow it from your next message on. To stop sharing: `python System\live\desk.py leave`.
