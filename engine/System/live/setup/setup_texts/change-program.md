# Changing how the assistant works

The owner asks for a change to their assistant: how it works, how it looks, what its rules are. You talk it through until it is exactly clear, check it against the program and the guardrails, say it all back, and only on a very clear go make it, with every step it needs. In the owner's words: "a back and forth discussion about a change so that everyone understands exactly what it is before it's committed to, and then the change is made and committed to the program."

Before anything, read `interview.md` (in the same folder as this file): "How you talk" and "The helper". Talk exactly that way and use that helper the same way. Here the place a file lives may be named when the owner asks, but describe what changes in plain words first.

This works the same in Claude on the computer (/assistant:change, choice "how I work or look") and in Talk to your assistant. On the computer the edit itself is yours, made with your own editing tools; the program refuses any edit unless a change has been agreed and given its go (the helper's record is what it checks). In Talk to your assistant you only talk and record: `HELPER change-start` and `HELPER change-agree` are your ACTION lines change_start and change_agree; after the say-back, ask them to press Approve on the change's own card in Cards instead of asking for a typed go. That press is the go; the program then does sections 5 and 6 itself, hidden, and tells them how it went in Talk to your assistant, with an Undo. In Talk to your assistant, section 6's "Do you see it working?" is asked after that result arrives.

## 1. Hear it

`HELPER changes` first. If one is `open`, it was cut off part way: say so plainly and finish or undo it before anything new (sections 5 and 7).

Ask: "What would you like to change? Say it in your own words." Then `HELPER change-start "<their words, exactly>"`. Keep its `id`.

## 2. Make it exactly clear

Ask one question at a time until you could describe the change so precisely that someone else could make it and get the same result: what they see now, what they want to see, when it applies, what it must not affect. Never guess; if you are unsure, ask. Use examples from their own page when that helps ("Like the card from the school yesterday?").

## 3. Check it

Read, without changing anything:
- the guardrails (`System\RULEBOOK.md` in the assistant's folder; assumed place until the guardrails' own description settles it) and every rule it touches;
- the program files the change would touch, and what else uses them. Search the whole program for every place that says or does the same thing (the page, the engine's own code, the instructions Talk to your assistant reads about the page) and include them all, so the program never says two different things;
- `HELPER changes`: earlier changes on the same files or the same behaviour.

Look for conflicts: a rule it would break (cards that do not follow the page's rules, anything sent without the owner's press or a permission to send without asking that they accepted, anything personal in the general part, the three parts mixed), another part of the program it would upset, an earlier change it would undo or fight. For each conflict, say it plainly and offer one or two ways round it that keep the rules; never a way that breaks the guardrails.

Decide which part it belongs in, and ask only when it truly could go either way:
- **their own settings, lists and rules** (most "show me less of", "always", the wording of their own rules): this is not a program change. Make it through the matching part of `change.md`, or Settings on the page, and stop here.
- **mods**: anything about how the assistant works or looks, a new connection, card, button, step or rule of theirs: a mod, their own folder `Live/mods/<a short name>/`, kept apart from the program and never touched by an update. The program's own files (`System/`) are never changed; a mod takes the program's place where it applies. What a mod holds and the places the program asks it (its pass step, its cards' buttons and answers, the chat's tools, words and actions, its own rules, its Settings section) are written at the top of `System/live/mods.py`; read that first and build only through those places. A mod that needs to loosen one of the program's own rules says so in its `mod.json` "loosens" only after the owner's own yes to that, in their words and dated, and the guardrails show it. If the change cannot be made through those places, say so plainly: it needs the program itself changed, which is the plugin maker's, not done here.
- **taught**: a new connection type of their own, kept apart from the program (`Live/taught/`).

## 4. Say it all back, and get the go

Say back, in plain words and in this order: what will change; what will not; which part; any conflict and the way round it you agreed; what they will see on the page when it works; that if anything fails along the way everything goes back by itself; that they can undo it later. Then the files it will touch, by plain name.

**A mod proves itself.** When the change makes or changes a mod, `checks.json` is always one of its files (`Live/mods/<name>/checks.json`), and you say its checks back with the rest: one plain check for each thing the owner can try on their own, each saying what to try and what should happen ("Take a receipt photo after your next purchase: within about 15 minutes it should be complete in the expense system."). When the change is made they become cards on the owner's page with Works and Doesn't work; the program does the rest (a check that does not work is fixed through this same walk-through's steps, an undo copy first and only the mod's files), so you write nothing about it into the mod.

`HELPER change-agree <id> <part> "<the whole change, word for word as you just said it back, not shortened>" <each file, as a place inside the assistant's folder, for example Live/mods/receipts/mod.py>`

Ask: "Shall I make this change now? Say yes to go ahead." Their go covers everything you said back, including the way round any conflict; if they want a different way round, that is not a go. Only a clear yes is a go, starting with "yes", "go ahead" or "do it" (the guardrails check the go's first words). Anything else ("I think so", "maybe", "sure", a question, a new detail) is not a go: if it plainly means yes, ask them to answer "yes" so it is on record; otherwise answer it, change the agreement if needed, say it back again, and ask again. If they decide against it: `HELPER change-drop <id>`.

On the go: `HELPER change-go <id> "<their go, word for word>"`. It saves the undo copy first. If it refuses, tell them why in plain words and stop.

## 5. Make it

Say "Making the change now." Edit only the files agreed. Then:
- edits made: `HELPER change-edited <id> ok`
- an edit was refused or could not be made: `HELPER change-edited <id> fail "<which file and why, plainly>"`. Everything goes back by itself.

If you find mid-way that the change needs a file not agreed, or needs to be different from what was agreed: stop, `HELPER change-edited <id> fail "needs more than was agreed: <what>"`, tell them, and go back to section 2.

## 6. See it working

`HELPER change-check <id> --expect "<a few words that will be on the page when it works, if there are any>"`. It rebuilds the page, restarts the part that keeps the page answering, runs one check of the whole assistant, and looks at the page. The first step that fails puts everything back by itself; tell them which step and why, in plain words ("It did not work: the page would not open after the change, so I put everything back as it was."), and offer to try again from section 2.

When it passes, have them look: on the computer, open their page and show them where; in Talk to your assistant they are looking at it already. Ask: "Do you see it working? 1 yes, 2 no." On no: `HELPER change-abandon <id> "<what they saw>"`; everything goes back; say so. On yes: say "Done. It is on your list of changes, and you can undo it any time." 

## 7. Undo

When the owner asks to undo a change (or a change was cut off part way):
1. `HELPER changes`, and find it with them by their own words.
2. `HELPER undo <id> --plan`. Say plainly: what will go back to how it was (from the change's own `agreed` words in `HELPER changes`, turned around); a change that failed was already put back and never counts as built on it; any later changes built on it (they would be undone too, newest first); and what cannot be taken back (`cannot_take_back`: cards it already made, and anything sent on an approval given while it was live, stay as they are). If `changed_since` names files, say that something changed them since outside any change, and that undoing would lose that; do not go on without their clear yes.
3. Ask: "Undo it now? 1 yes, 2 no." Only on yes: `HELPER undo <id>` (with `--with-later` when later changes are to go too).
4. Say what was undone and whether the page is working again (`working`). If a step did not pass, say which and why.

A change made before an update cannot be undone this way (the helper says so); offer to make a new change that takes it out.

## What you never do

- Edit anything before the go, or anything the agreement does not name.
- Take an unclear answer as a go.
- Break the guardrails to make a change work.
- Leave a change half made: it is either seen working, or everything is put back.
