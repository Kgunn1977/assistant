# What changed for the person

One numbered line for each change a person using a roadmap would notice, oldest first, newest last. `/assistant:roadmap-update` shows a project the lines after the one it was last brought up to, so a line is never renumbered or taken out; a new change is added at the end with the next number and the day it was made. Plain words, said to the person.

1. 2026-11-16. A question you answered keeps its history: if Claude asks it again, the earlier answers stay under it.
2. 2026-11-16. A check you mark is told to Claude at once; you no longer wait for Claude to look at the page.
3. 2026-11-16. A row shows where it stands the moment you mark its last check: done if every check works, known fault if one does not.
4. 2026-11-16. Each check has five places to press: Works, Doesn't work, each of those with a comment, and Comment only, which writes a note on the row and marks nothing. These replace the four buttons.
5. 2026-11-16. Words you type in a comment box are sent only when you press Done; leaving the box sends nothing.
6. 2026-11-16. The page has three sections, Planning, Working and Done, in place of one long list.
7. 2026-11-16. You can write to Claude on any row ("Say something about this"); Claude is told, and the row shows the note until it is dealt with.
8. 2026-11-16. A row can carry its written plan: "Plan written" shows on the row and "Show plan" opens it.
9. 2026-11-16. A step that is done folds its done parts inside it; open the step to see them. A part that is not done yet stays in Working.
10. 2026-11-16. A project that already had a roadmap page can be moved onto the plugin with `/assistant:roadmap-setup`, keeping its link and everything on it.
11. 2026-11-16. Setup now works in a project that refuses commands reaching outside its own folder: Claude runs the plugin's working copy, kept in the plugin's own data folder.
12. 2026-11-16. `/assistant:roadmap-update`, typed in a project's main session, brings that project up to the plugin as it now stands and tells you what changed.
13. 2026-11-16. A press on this roadmap made on another program's page reaches the project's main session, and a press made while it was closed reaches it at its next message.
14. 2026-11-17. A row that says it is ready for your look but has nothing to try now shows "No checks to try: tell Claude" as a fault, and Claude no longer sets that status without checks.
15. 2026-11-17. The roadmap is now part of the assistant plugin. Its commands start /assistant: (/assistant:roadmap-setup, /assistant:roadmap-update, /assistant:roadmap-start-writer); the skills the main session and the writer load are assistant:roadmap-director and assistant:roadmap-writer.
16. 2026-11-18. A project can be switched so its main session writes the roadmap itself, with no Roadmap writer session; only you switch it (roadmap_setup.py writes-main). Projects not switched work as before.
17. 2026-11-23. Each row is named as the part of the work it belongs to, a colon, then what is true once it is finished, for example "Kitchen: cabinets hung".
18. 2026-11-23. The roadmap page has its own Settings section at the bottom: the roadmap's kind, who writes it, the questions file for each of the project's sessions, and the model helpers use. A press there asks the project's main session to make the change, and the page shows the new choice once it is made. Who writes the roadmap shows the command for you to run yourself, with Copy.
