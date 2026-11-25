# When an update meets the owner's own changes

Used by `update.md` (the update walk-through, in Talk to your assistant or at the computer), before anything is written. The agreed way: "there would have to be a step where the update skill goes through the changes the user has made and sees how they would be lost or changed in an update and handles them." Talk as `interview.md` "How you talk" says; `HELPER` is as in its "The helper".

1. `HELPER update-sort "${CLAUDE_PLUGIN_DATA}/engine"`. It reads the owner's change list and sorts each change that is live:
   - **untouched**: the update does not touch what it changed. Nothing to decide.
   - **needs adjusting**: the update changes other lines of the same files; the change fits beside them (a joined copy is ready).
   - **now built in**: the update does the same thing itself.
   - **clashes**: the update changes the very lines the owner changed, adds a file they added, or takes out a file they changed.
2. Say how many of each in one line, then go through every change that is not untouched, one at a time, by the owner's own words (`asked`) and what was agreed (`agreed`):
   - needs adjusting: "The update also changes <plain description>. Your change fits beside it. 1 keep your change (joined with the update), 2 drop your change." Offer to show the joined result.
   - now built in: always ask, and encourage the built-in one: "The update now does this itself: <what>. I suggest using the built-in one. It's kept up to date for you. 1 use the built-in one (suggested), 2 keep your own."
   - clashes: say exactly what each side does to the same place. "1 take the update's (your change is dropped), 2 keep yours (the update's change to that part is not taken), 3 combine them." For 3, write the combination into a new file under the home's `changes\update-work\` folder, show it in plain words, and use it only on their yes.
   Save each decision as it is made: `HELPER update-decide <id> <built in | keep | drop | the combination file's path>`.
3. For changes in their own part or taught add-ons (`check_rule_book`): read the new version's guardrails and check each against them. A change or add-on that would now break a rule: say so plainly and ask whether to keep it switched off until it is changed; never apply an update that leaves a rule broken without saying so.
4. Then go back to `update.md` step 3.
