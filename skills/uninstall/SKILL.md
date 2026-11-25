---
name: uninstall
description: Take the assistant off this computer - its background job, its program, and (only if the person says so) their data. Only when the person types /assistant:uninstall.
disable-model-invocation: true
---

# Take the assistant off this computer

Run every command exactly as written, one at a time, with the Bash tool (never PowerShell: it drops the quote marks inside answers).

## Which assistant
Find it as `${CLAUDE_PLUGIN_DATA}/setup_texts/interview.md`, "Starting", step 1 says: the folder this session is open in, then the folders in `${CLAUDE_PLUGIN_DATA}/roots.json`. If none is found, say it is not set up on this computer and go to step 5. Call its folder ROOT, written with forward slashes and no slash at the end.

`HELPER <what> [details]` means `python "${CLAUDE_PLUGIN_DATA}/engine/System/live/setup/setup_home.py" --root "<ROOT>" <what> [details]`.

## 1. What it changed in other projects (while its program is still there)
```
HELPER projects
```
For each project it lists that has its introduction or its line in that project, or shows its roadmap, ask once, numbered: "Take your assistant's things out of <project name> too? 1 yes, 2 leave them." On yes, run each that applies, one at a time: `HELPER project-line "<name>" off`, `HELPER project-intro "<name>" off`, `HELPER project-roadmap "<name>" off`, then `HELPER project-remove "<name>"`. On leave, say plainly what stays in that project.

## 2. Program only, or data too
Ask, numbered: "1 Remove the program and keep my data (your rules, history and sign-ins stay in your assistant's Live folder), or 2 remove everything, my data too. Removing data cannot be undone." Wait for the answer.

## 3. Take it off
For answer 1:
```
python "${CLAUDE_PLUGIN_DATA}/scripts/assistant.py" uninstall --root "<ROOT>"
```
For answer 2:
```
python "${CLAUDE_PLUGIN_DATA}/scripts/assistant.py" uninstall --root "<ROOT>" --remove-data
```
Tell the person what it printed in plain words. A line starting "Left in place" names something step 1 left in another project.

## 4. Check
```
python "${CLAUDE_PLUGIN_DATA}/scripts/assistant.py" status --root "<ROOT>"
```
It should show no jobs, nothing running and no program (and no data, for answer 2).

## 5. The last step is theirs
Tell them: type `/plugin uninstall assistant@assistant`, then close and reopen the Claude app. Roadmaps already set up in projects keep their pages; their blocks stop when the plugin is gone.
