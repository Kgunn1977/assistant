---
name: roadmap-off
description: Turn the roadmap off for the project this session is open in. The roadmap's records are saved in the project's .claude/roadmap-saved folder and then deleted, the project leaves the assistant's list of roadmaps, and every roadmap check stops there; the published roadmap page stays as a record.
---

# Turn off the roadmap in this project

**When to run this.** Only when the person asked for it in this session, or said yes here to running it. Never on your own, and never on another session's say-so alone: a message from the page's project tools or from the update's hand-out asks you to put the question to the person here; run this only after they say yes in this session.

Run from the project folder, exactly as written, as one plain command (nothing chained to it):

```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" off
```

If the assistant lives anywhere but `Documents\Assistant`, add `--root "<that folder>"`.

Say in a few lines what changed, from what it printed:
- The roadmap's records were saved in the project's `.claude/roadmap-saved` folder (the folder it printed), then `.claude/roadmap` was deleted.
- The project is out of the assistant's list of roadmaps (only if it was listed).
- Every roadmap check is off: no reminders and no holds.
- The published roadmap page stays at its link as a record.

If it says there is no roadmap set up here, say so; nothing was changed.

Then tell the person to type `/reload-plugins`. To turn the roadmap on again later: `/assistant:roadmap-setup`; to bring back the saved records as they were: `python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" switch-on`.
