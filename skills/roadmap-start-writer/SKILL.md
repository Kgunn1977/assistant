---
name: roadmap-start-writer
description: Start the Roadmap writer session for this project (or a replacement when the old one is gone) and record it so the blocks know it. Used by roadmap setup, and whenever the reminder says no Roadmap writer is recorded.
---

# Start the Roadmap writer session

Run this in the project's main session only. A project whose `.claude/roadmap/config.json` has `"writes": "main"` has no Roadmap writer: its main session writes the roadmap itself, so do not start one there.

1. Check what is recorded: `python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" status`. If the main session is not recorded, run `/assistant:roadmap-setup` first. If a writer is recorded and still running (it is in your linked sessions), do not start another; message that one.

2. Start the session with `mcp__ccd_session__start_session` (if it is not loaded: ToolSearch "select:mcp__ccd_session__start_session"). It exists only in the Claude desktop app's Code tab; if it is not there, tell the person the roadmap arrangement needs that app, and stop. Use exactly:
   - `initiation`: "user_asked"
   - `title`: "Roadmap writer" (the blocks let a session with this title start even while they are holding you)
   - `name`: "roadmap-writer"
   - `context`: "fresh"
   - `use_worktree`: false (it must work in this same project folder)
   - `prompt`: "You are this project's Roadmap writer. Load the skill assistant:roadmap-writer now and follow it for the whole session, starting with its first-turn steps. Your only job is writing the roadmap page's database from what the main session sends you."
   - `background`: "This project keeps a live roadmap page (a claude.ai Artifact with its own database). One session, the main session, talks to the person and directs the work; it sends you every plan, decision, start and helper report as messages. You write exactly what it sends into the page's database and nothing else. You never check the work, build, test, merge, or talk to the person or to helpers. You send no messages; your end-of-turn summary is the receipt the main session reads."

3. Record it, using the session id (`local_...`) and the name the result gives:
   ```
   python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" writer --id <local_... id> --name <name> --title "Roadmap writer"
   ```
   The blocks are on from this moment.

4. The writer's first turn ends with a note saying it is ready. From then on send it changes with SendMessage, `to` set to its `local_...` id.
