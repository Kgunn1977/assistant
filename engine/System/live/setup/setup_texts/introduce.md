# Introduce, change or remove a project

Before anything, read `interview.md` (in the same folder as this file): its sections "How you talk" and "The helper", including "Steps that need the computer". Talk exactly that way and use that helper the same way; `HELPER` below means the same command, with the same ROOT (find the assistant as `interview.md`, "Starting", step 1 does: the folder this session is open in, then the folders in `${CLAUDE_PLUGIN_DATA}/roots.json`; never lay it down from here: if it is not on this computer, say /assistant:setup comes first, and stop).

1. `HELPER projects`. Say which projects are introduced, numbered, each with what comes in, what goes back, and whether its roadmap shows. Then: "1 introduce another project, 2 change what one sends or gets back, 3 remove one." (Only 1 when none is introduced.)
2. Introduce another: do the interview's step 3 for one project, all of it, including each yes before each change inside that project. Do not save `projects`.
3. Change one: ask the two questions again (what should come in; what should go back), then `HELPER project-change "<name>" "<in>" "<back>"`. If that project holds the introduction, its words must follow: show the new words (`HELPER project-intro "<name>" show`), ask "Put these new words in that project in place of the old ones? 1 yes, 2 no", and only on yes run `HELPER project-intro "<name>" on`. On no, say plainly that the project's Claude keeps following the old words until they say yes.
4. Remove one: say what removing does ("No more cards from it. Your page stops showing its roadmap. I take out what I added to that project. Notes it already left stay there, and nothing else there changes."). Each part inside that project is its own yes, in this order, and only the parts it has:
   - the line in its instructions: "Take my line out of that project's instructions for Claude? 1 yes, 2 no" then `HELPER project-line "<name>" off`
   - the introduction: "Take the introduction out of that project? 1 yes, 2 no" then `HELPER project-intro "<name>" off`
   - its roadmap on the page: "Stop showing its roadmap on your page? 1 yes, 2 no" then `HELPER project-roadmap "<name>" off`
   - then "Remove the introduction from my list? 1 yes, 2 no" then `HELPER project-remove "<name>"`. The helper refuses while anything is still in that project; if they kept a part, say what is still there.

End with one line on what changed.
