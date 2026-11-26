---
name: roadmap-director
description: How a project's main session works with its roadmap - the roadmap is a log of the project that the person reads, so every decision they make and every change in the project goes on it the same turn (sent to the Roadmap writer, or written yourself in a project set to write its own roadmap); also reading it, and handling the person's Works / Doesn't work marks, notes, answers and settings presses. Use in the main session of a project set up with /assistant:roadmap-setup, whenever work is planned, started, reported or checked.
---

# The main session and the roadmap

## The roadmap is a log
The roadmap is a log of what is going on in the project, so the person can see the context you carry in your head. Put two things on it the same turn they happen, without being asked:
- **every decision the person makes**;
- **every change in the project**: work started, finished, stopped, dropped or replaced, a helper's report, a fault found.

Talk, ideas and questions are not decisions: never record them as decisions, and never turn them into a decision to move forward. An idea worth keeping can go on as an idea (`idea`: true). Nothing waits on a roadmap write except an actual decision; everything else is logged as it happens and never holds up the work.

## Who writes it
`.claude/roadmap/config.json` holds `page_url` (the page) and who writes the roadmap:
- **A Roadmap writer** (the default): you send it each change with SendMessage, `to` its `local_...` id (`writer.session_id`), saying plainly which rows change and to what. Its end-of-turn summary, which the app delivers to you, is its receipt and needs no forwarding. If it is gone, start a new one with `assistant:roadmap-start-writer`.
- **`"writes": "main"`**: you write it yourself, as in "Writing the roadmap yourself" below; read "send the writer" as "write it".

Helpers never write the roadmap or talk to the writer; they report to you and you log what their report means. The plugin may remind you at your next message of something not yet logged; a reminder never holds anything. Never change the plugin's files, `.claude/roadmap` or the settings yourself.

Read `${CLAUDE_PLUGIN_DATA}/reference/database.md` once (the database's layout and every call), and `Roadmap page/Project rules.md` if the project has it (its own rules, which add to these).

## Reading it
Before you plan or report where things stand, read the database (list "steps", get board/next) and fix any row that does not match what you know. After each message from the person, also read what the page may have told you in a comment you missed: open notes, answered questions, marks, and `board/ask-...` requests with status "open".

## Rows
Plain words for the person: what the piece does, what it does not do yet, what it needs from them. Steps for the ordered path, phases for parts of a step (always with `parent`), items for work outside the order; only the eight statuses in the manual.
- **Name**: the name the person uses for that part of the work, a colon, then what is true once it is finished, never the problem ("Kitchen: cabinets hung").
- A written plan goes whole on its row (`plan`), not in a file sent in chat.
- A piece a helper built that is not yet in the main copy is "Built, waiting to be merged".
- When the person says a row is done, it is "Done, confirmed" at once, with `shown_working` adding "You confirmed it, <date>".
- **Stepped or running**: chosen at setup. When the person asks to switch, run `python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" kind running` (or `stepped`) and make the one write it prints. A running roadmap uses items, `release` on finished rows and `idea` on unagreed ones.

## Checks
Check everything you can yourself first: the code path, a test page, or test cards (`assistant.py test-cards add` / `remove`; never press anything on real data, never send). You can't judge your own work: a row is "Done, confirmed" only on the person's word or their checks, never on yours. Work you fully checked is "Ready, waiting for your look" with `shown_working` reading "Checked by Claude, <date>: <what you checked>" and checks for the person to confirm it (their `needs_person`: "You confirm what I built; I can't judge my own work."), and the guard refuses a "Done, confirmed" write with no "Your checks" or "You confirmed it" line. Only what you truly cannot check goes to the person as a check of its own: the row is "Ready, waiting for your look" only when it carries checks, three to six, each with `needs_person` (why only they can: their phone, a real send, reconnecting an account, taste), and the "Checked by Claude" line, in the same write; the writer refuses a Ready status for a row with none, and so does the guard. Helpers do the same before they report.

Each check is one line and one thing: what to open (by its own name), what to do, what they should see. Have checks share as few things to open as possible ("Same file." for the next).

The person's marks:
- **Works** (read any note and log any wish in it): when every check on a row works, the row becomes "Done, confirmed", `shown_working` adds "Your checks, <date>", and its marks are deleted.
- **Doesn't work**: "Ready, known fault", with what failed and their note in `not_yet`; get it fixed, then a new check (new id) and the old mark deleted. An empty note: ask what they saw.
A comment on a check without an answer is a note. The page shows a fully marked row's result at once, but nothing is logged until you send it.

## Notes on a row
For each open note: act on it, log any decision in it, then mark it done with one line on what changed. Never leave one unanswered without telling the person why.

## Questions
A question raised by the work goes on the roadmap, on its row (row id, short topic, the question, any choices, pictures as file paths), and is answered there. A question raised in conversation goes in the asking session's questions file, if it keeps one, and is answered in chat; the roadmap shows a read-only copy of each such file (`board/questions-file--<session>`), written only by the session that keeps it.

For each answered roadmap question: act on it, log the decision, then mark it done with one line on what changed. A reply that is itself a question is not an answer: answer it, then ask again on the same question with clearer wording, keeping its id, topic and history (the manual's part "When the person answers with a question of their own").

## Settings pressed on the page
A press in the page's Settings writes `board/ask-<...>` (`setting`, `value`, status "open") and comments to you. Yours in both arrangements, once each:
- **`kind`** or **`helpers`**: run `python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" kind <value>` (or `helpers <value>`).
- **`questions`**: only by `assistant:questions-setup` / `assistant:questions-off`, after the person's yes in that session. For this session, ask here in one line; for another, message it to ask there. Leave the request open until `python "${CLAUDE_PLUGIN_DATA}/scripts/questions_setup.py" status` shows the change, or the person said no.
- **Who writes the roadmap** is never a request: the person runs that command themselves. Never run `writes-main` or `writes-writer`.
Then make the write the command printed (for a questions file, the one `roadmap_setup.py settings` prints; run `settings` once too when `board/settings` lacks `helpers`, `writes` or `sessions`), and update the request: `status` "done", `done_note` one line on what changed or why nothing did. With a writer, tell it the documents you wrote so it updates the copies.

## Helpers' model
The cheapest model that does the job well, unless the config has `"helpers": "strongest"`.

## Presses from another program's page
A message starting "Press from the live page on the roadmap" carries the person's own presses, one `[press id]` line each in the page's comment words. Handle each as that comment. A `board/ask-<...>` line is a settings request: write its document yourself as the press carries it, then handle it as above. Every other line goes to the writer once, with its press ids, as presses it writes as the page would have: it writes the mark, the answer or the note itself. A line saying ids were already given means send nothing for them.

## Writing the roadmap yourself
Only when the config has `"writes": "main"`. Then you alone write the database; helpers' writes are refused, except a session's copy of its own questions file.
- **When**: as "The roadmap is a log" says. A plain answer that changes nothing owes nothing, nor does a helper's turn-end note alone. After a finished helper's report the roadmap does not show, your reply is held once; log it then.
- **How**: one short step after the work, not a word about it in the chat, with the calls in the manual; several changes in one "batch"; only changed fields; `changed` set to the local date and time on every row you touch. A write refused as stale: get the document and redo it once; if it still fails, say once in one line what was not recorded.
- No program version number in any row, question or "What's next": name the change instead. Never invent a check; keep an unchanged check's id, give a reworded one a new id.
- Marks and notes are the person's: write one only for a press, delete one only once dealt with, never change their words.
- **Presses**: for each `[press id]`, once, make the call queued in `Roadmap page/from-page.json` with `data` unchanged (an update with `if_version` from a read); if it is gone, build it as the manual's part "Presses from another program's page" says. Skip one already written or older than the document; write nothing for a line you cannot place.
- **The copies**: when `Roadmap page/readers.json` lists a reader with `"full": true`, never touch `roadmap-full.json` or `roadmap.json` yourself: once per turn, after the last write, save this turn's writes as `{"writes": [...]}` (each `{"op", "collection", "doc_id", "data"}` as sent, plus a "set" of every page-changed document you read) and run `python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" full-patch "<that file>"`. If it says the copy is missing or damaged, say so once; rebuilding it is a whole write done only when the person asks. When readers are listed but none wants the full copy, update `Roadmap page/roadmap.json` as `${CLAUDE_PLUGIN_DATA}/reference/agreement.md` gives and run `roadmap_setup.py facts`. The database stays the only source.
