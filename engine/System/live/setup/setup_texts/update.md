# Taking an update

Once a week (Sunday just after midnight) the assistant looks for a newer version, by comparing version numbers only (no Claude). When there is one, the page shows an update card. The owner either presses "Walk me through it" on the card (this walk-through starts in Talk to your assistant) or types /assistant:update in Claude on the computer. The words are the same in both places. "Not now" on the card hides it until the next Sunday's look, if the update is still waiting.

Talk as `interview.md` "How you talk" says; `HELPER` is as in its "The helper", including "Steps that need the computer".

## The update card

Built by the program from the new version's change list (the plugin's `docs\changes.md`: newest version first, a "## <version>" line, then one "- " line per change; the working copy has it at `${CLAUDE_PLUGIN_DATA}/docs/changes.md`). The wording is:

- Header: "An update is ready: version <new>"
- One line under it: "<n> improvements. Nothing changes until you say so."
- Folded inside: one line per entry in the change list, in its own plain words, newest first; at most 10, then "and <n> more".
- If the owner has made their own changes to how the assistant works: "You have made <n> changes of your own; the walk-through goes through each one with you."
- Buttons: "Walk me through it", "Not now" (with the small line "Asks again next Sunday").

## The walk-through

1. Say the version and what it brings, from the change list (the "- " lines under each "## <version>" newer than theirs in `${CLAUDE_PLUGIN_DATA}/docs/changes.md`), in a few plain lines. When the plugin's version is the same as theirs (`python "${CLAUDE_PLUGIN_DATA}/scripts/assistant.py" update-plan --root "<ROOT>"` shows the same "from" and "to"), there are no new notes: say instead that the program was changed on this computer since it was laid down, and how many files that takes. "Shall we go through it? It takes a few minutes; nothing changes until the very end. 1 yes, 2 not now."
2. Their own changes: follow `update-changes.md` steps 1 to 3, saving each decision as it is made with `HELPER update-decide <id> <built in | keep | drop | the combination file>` instead of keeping them to the end. If there are none, say so in one line.
3. Say back, in plain words: what the update brings, and what happens to each of their own changes. Ask "Shall I put the update in now? 1 yes, 2 not now."
4. **In Talk to your assistant**, on yes: this is the hand-off. Say: "The last part restarts me, so it has to be finished at your computer, where nothing can cut it off halfway. Your choices are saved. At your computer, open Claude and type /assistant:update. It carries on from here." End there. (The update is never written from the page: the page itself is stopped while it is written.)
5. **At the computer** (typed /assistant:update, or carrying on from the page): `HELPER update-show`. If it has decisions and nothing `still_to_decide`, say "Carrying on with the update you went through on your page.", say back step 3 once more in one or two lines from what it shows, and ask for the yes again. If some are still to decide, do those first (step 2). Then, on the yes:
   - `HELPER update-choices` (no details: it uses the saved decisions) makes the choices file.
   - The update itself is the update skill's own step, given that choices file. It writes the new version and the kept changes together, checks that the program loads and the page answers, and puts everything back by itself if a check fails. It does not check for new messages; say so, and that you check for new messages when they want (the check-pass step in the update skill).
   - When it says it succeeded: `HELPER update-after "<new version>"`. Say, one line per change, what became of it, and that the update card is gone. Then the update skill's step 4 offers each of the owner's other Claude sessions its step (a reload, and in a roadmap's main session the roadmap's own update).
   - If it put everything back: say which step failed and why, in plain words, that nothing was lost, and that the card stays so they can try again.
