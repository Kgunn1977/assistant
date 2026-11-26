# The roadmap page's database: layout and every call

The page's own database is the only source of the roadmap's facts. There is no roadmap file to edit, and the page is never rewritten or republished for a change of facts: change the database and every open copy of the page shows it within seconds.

**The page's link** is `page_url` in `.claude/roadmap/config.json` in the project folder. Read it from there; it is written `PAGE` below.

**Tool:** ArtifactData (if it is not loaded: ToolSearch "select:ArtifactData"). Only the page's owner and editors can write; everyone else who can open the page only reads.

**Always** set `changed` to the local date and time (for example 2026-03-04T10:05) on every row you change; the page marks the rows changed within 2 hours of the newest change in blue.

## Rows: collection "steps"
One document per row. A row is a step, a phase of a step, or a piece of work outside the step order. Fields:
- `order`: a number; the page lists rows by it. Leave gaps (10, 20, 30 ...) so a new row can take a number between its neighbours. A phase's number falls between its step and the next step.
- `kind`: "step", "phase", or "item" (work outside the step order: a tool, a side job, a standing task; listed after the steps in each section of the page)
- `number`: the step's number as text ("1", "2"), a phase's ("2A"), "" for an item
- `name`: the name without its number. Name each row as the name the person already uses for the part of the work it belongs to, a colon, then what is true once the row is finished, stating the result and never the problem, for example "Kitchen: cabinets hung" or "Chapter 3: draft finished".
- `parent`: for a phase, the id of its step (for example "step-02"), always; "" otherwise. The page puts each phase right under its step, and folds a done step's done phases into it
- `status`: exactly one of the eight below
- `does`, `not_yet`, `uses`, `shown_working`, `waits_on_you`: plain sentences; "not recorded" when nothing is known. `waits_on_you` is what the row needs from the person whose project this is; "nothing" when it needs nothing.
- `release` (optional): for a finished row, the release or version it shipped in, as text ("0.1.4"). A running roadmap groups its History by it; without it, by the date the row last changed.
- `idea` (optional): true on a planned row that was talked about but not agreed. A running roadmap shows it under Ideas instead of Next batch. Leave it out (or false) on agreed work.
- `checks` (optional): see "Checks" below
- `table` (optional): a small table shown in the row's open view: {"title": "...", "columns": ["Name", "Tried", "Passed"], "rows": [{"Name": "Set A", "Tried": 12, "Passed": 11}], "totals": true, "summary": "one line shown on the closed row"}. Each row is an object keyed by the column names; a value not yet known is null (shown as a dash). `totals` adds a line that sums the number columns. The table is replaced whole on update.
- `plan` (optional): the row's written plan as text. Headings (#), numbered and bulleted lists, **bold** and short tables (lines of | cells |) show. The page keeps it folded behind "Show plan" in the row's open view and says "Plan written" on the closed row. Replaced whole on update; leave it out when there is none.
- `changed`: date and time of the last change

The eight statuses, written exactly:
| Status | Means |
|---|---|
| Not started | Nothing decided about it yet |
| Planned, not started | Agreed and planned; no work begun |
| Being worked on now | Someone is working on it right now |
| Built, waiting to be merged | A helper reports it finished, but it is not yet in the main copy of the work |
| Ready, waiting for your look | It is in the main copy and Claude has checked all it can; the person has not yet tried what only they can. Written with at least one check, each with `needs_person`, and a "Checked by Claude, <date>: ..." line in `shown_working`, in the same write; any other Ready write is refused by the plugin's guard. |
| Ready, known fault | It is in the main copy and something about it is known not to work. Written the same way as "Ready, waiting for your look" (checks with `needs_person`, and the "Checked by Claude" line); any other Ready write is refused. |
| First pass, to be redone | A rough version exists and is to be redone |
| Done, confirmed | The person tried it and confirmed it. Also: Claude checked it and it needs nothing from the person; `shown_working` then reads "Checked by Claude, <date>: <what was checked>". |

A Ready status is written only on a row that carries at least one check, in the same write or already there. A row set to a Ready status with no checks has nothing for the person to try; the page shows it as a fault ("No checks to try: tell Claude"), not as waiting on the person, and the writer refuses to write it.

Document ids: `step-01`, `step-02` ... for steps; `phase-2a` for a phase; `item-short-name` for an item. Read the live list (action "list") for the current ids before relying on memory.

## "What's next": collection "board", document "next"
- `facts_as_of`: date, written 2026-03-04
- `lines`: a list of {"label", "text"} pairs shown in order, for example {"label": "Working on now", "text": "nothing"}, {"label": "Waiting on you", "text": "..."}, {"label": "Next", "text": "..."}. An update replaces the whole list, so send every line.

## The roadmap's kind: `kind` in "board" / "settings"
Two kinds. **Stepped** (the default; leave `kind` out) is for a build with an end: every step in order, the strip of numbered squares, the counts. **Running** (`kind` "running") is for ongoing work that never finishes: the page shows only live rows, in these groups from the top: Now (being built), Being fixed, Waiting on you (checks and questions), Next batch, Ideas; rows are numbered 1, 2, 3 in page order among the live rows only, as a display (stored ids and `number` do not change); there is no strip and no counter tiles, only one short line of counts; and finished rows fold into a History section at the bottom, grouped by `release` or else by date. The mapping from the stored status: "Being worked on now" (and "Built, waiting to be merged") to Now; "Ready, known fault" to Being fixed; "Ready, waiting for your look" (and any row with an open question) to Waiting on you; "Planned, not started", "Not started" and "First pass, to be redone" to Next batch, or to Ideas when `idea` is true; "Done, confirmed" to History. Checks, questions, marks and notes work as in the stepped kind. Switch with `python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" kind running|stepped`, which prints the one settings write to make. Optional wording for the running groups: `now_heading`, `fault_heading`, `wait_heading`, `next_heading`, `ideas_heading`, `history_heading`.

## The page's wording: collection "board", document "settings" (optional)
`subtitle` (the line under the title), `steps_heading` (default "Steps"), `extras_heading` (default "Other work"), `checks_heading` (default "Try these"), and the names of the three sections: `planning_heading` (default "Planning"), `working_heading` (default "Working"), `done_heading` (default "Done"). Leave a field out to keep its default.

## The page's Settings: collection "board", document "settings" and documents "ask-..."
The page has a folding Settings section at the bottom showing this project's settings, each from `board/settings` as the main session last wrote it, never a guess:
- `kind`: "stepped" or "running" (see "The roadmap's kind"); absent means stepped.
- `helpers`: "cheapest" (each helper gets the cheapest model that does its job well) or "strongest" (always the strongest model).
- `writes`: "writer" (a Roadmap writer session writes the roadmap) or "main" (the main session writes it itself), and `writes_switch`: the exact command the person runs themselves, outside Claude, to change it. The page shows it with Copy and never runs or asks for it.
- `sessions`: the project's sessions, a list of {"id" (the session's local_... id where known), "name", "questions": true or false, "role": "main", "writer" or ""}.
- `settings_as_of`: when they were recorded.
Absent fields show "Not recorded yet". The main session writes all of them at once, exactly as `python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" settings` prints them (`kind` and `helpers` print the same write after their change). The wording fields above are left as they are.

A press in Settings changes nothing itself. The page writes one request, `board/ask-<setting>` ("ask-kind", "ask-helpers") or `board/ask-questions--<session id>`, with "set": `setting` ("kind", "helpers" or "questions"), `value` ("stepped"/"running", "cheapest"/"strongest", "on"/"off"), for a questions file `session` and `session_name`, `asked` (date and time), `status` "open". It then sends Claude a comment: `Asked on the roadmap: change the setting "<name>" to "<choice>" (board/ask-<...>)`, or `Asked on the roadmap: turn the questions file on|off for the session "<name>" (board/ask-questions--<id>)`. Until `board/settings` shows the new choice, the page shows it as asked. Only the main session acts on a request (roadmap-director, "Settings asked on the roadmap page"); it then writes `board/settings` and marks the request done: "update", data {"status": "done", "done_note": "<one line: what changed, or why nothing did>"}. A done request whose choice did not change shows its `done_note` as "Not changed: ...".

## The exact calls
A new document is made with "set" and no `if_version`. Every write to a document that already exists needs the version it had when last read (`if_version`). If the version is not known, first do a "get"; a write with a stale version is refused and names the current one, then redo it with that number.

Read one row:
```
ArtifactData {"action": "get", "url": "PAGE", "collection": "steps", "doc_id": "step-02"}
```
Make a row:
```
ArtifactData {"action": "set", "url": "PAGE", "collection": "steps", "doc_id": "step-02", "data": {"order": 20, "kind": "step", "number": "2", "name": "...", "parent": "", "status": "Planned, not started", "does": "...", "not_yet": "not recorded", "uses": "not recorded", "shown_working": "not recorded", "waits_on_you": "nothing", "changed": "2026-03-04T10:05"}}
```
Change a status:
```
ArtifactData {"action": "update", "url": "PAGE", "collection": "steps", "doc_id": "step-02", "if_version": 1, "data": {"status": "Being worked on now", "changed": "2026-03-04T10:05"}}
```
Change "What's next" (the first time, "set" with no `if_version`):
```
ArtifactData {"action": "update", "url": "PAGE", "collection": "board", "doc_id": "next", "if_version": 1, "data": {"facts_as_of": "2026-03-04", "lines": [{"label": "Working on now", "text": "..."}, {"label": "Waiting on you", "text": "..."}, {"label": "Next", "text": "..."}]}}
```
Several rows at once (one approval): action "batch" with `writes`, each entry {"op": "set" or "update", "collection": "steps", "doc_id": "...", "if_version": n, "data": {...}}, up to 50.

Read everything: action "list", collection "steps", query {"limit": 100}; then "get" on board/next.

## Checks: the person's Works / Doesn't work marks
Rows with status "Ready, waiting for your look" or "Ready, known fault" carry a `checks` list: things the person can try themselves, each one line, three to six per row. They open the row and answer each check on what looks like three overlapping buttons, drawn as a Venn diagram: "Works" and "Doesn't work" side by side, and "Comment" below them, overlapping the inner lower part of both. That gives five places to press. The part of "Works" or of "Doesn't work" that "Comment" does not overlap writes the mark at once with no note. Where "Comment" overlaps an answer (shown as the two colours mixed, with no words of its own) a box opens for that answer, headed "Works, with a comment" or "Doesn't work, with a comment". The part of "Comment" that overlaps neither ("Comment only") opens the same box for a comment that answers nothing: it becomes a note on the row (see "Notes" below) and the check stays unmarked. From any of the three comment places nothing is written or sent until they tap Done, and what they have typed is kept only in the open page until then. The top of the page counts the checks still to try.

- The wording is on the row: `checks` is a list of {"id", "text", "needs_person"} on the "steps" document. `needs_person` is a short reason only the person can do it (their phone, a real send to a real person, reconnecting an account, a matter of taste); the page shows it under the check. Claude runs every other check itself first (the code, a test page or test cards) and says so in `shown_working`: "Checked by Claude, <date>: ...". A Ready write without both is refused by the plugin's guard; a Ready row written before this rule stays readable, but cannot be written Ready again without them. Only the writer writes it, from wording the main session sends. The list is replaced whole on update.
- Each mark is its own document in collection "marks", id `<row id>--<check id>` (for example `step-02--c2`), fields `row`, `check`, `text` (the wording they saw), `result` ("works" or "fails"), `note`, `marked`. Only the page writes these, and the writer writes one only for a press from another program's page (see "Presses from another program's page"). A row update can therefore never wipe out a mark, and a mark can never wipe out a row change.
- Every check says three things, in one line: what to open (where to try it, or which example to try it on, by its own name), what to do, and what should be seen. It names nothing that does not exist yet. A check missing any of the three goes back to the main session to be completed; the writer does not guess it.
- Each check is one thing, as small as it can be, and two are never combined into one. What checks share is the thing to open: where several wait, they use as few different ones as possible, ideally one, so the person can do several in one go. A later check on the same one may say so ("Same file.") and give only what to do and what to see.
- Keep an unchanged check's id so its mark stays with it; a reworded or new check gets a new id (c7, c8 ...) so an old mark does not attach to new wording.

Read the marks (all, then only the ones that do not work):
```
ArtifactData {"action": "list", "url": "PAGE", "collection": "marks", "query": {"limit": 1000}}
ArtifactData {"action": "query", "url": "PAGE", "collection": "marks", "query": {"where": [["result", "==", "fails"]], "limit": 1000}}
```
An unmarked check has no document, and neither has a comment answer the person has not finished with Done. A "Comment only" never makes a mark. `note` holds what they said about it, on a "works" mark as well as a "fails" one; a plain answer, or one finished without saying anything, has `note` "".

When a mark saves, the page sends Claude a comment at once, as it does for an answered question: `Marked on the roadmap: the check "<wording>" on <row name> (marks/<mark id>): Works`, or `Works. Note: <their note>`, or `Doesn't work. Note: <their note>`, or `Doesn't work, no note`, or `cleared`. A plain answer arrives at once, with no note. An answer given where "Comment" overlaps it arrives once, when the person taps Done, with their finished words. Either arrives again only if they later change the answer or what they said about it. If no Claude session is listening the comment is left on the page. A comment can be missed, so the main session still reads the marks after each message from the person.

When every check on a row is marked, the page shows the row at once with the status its marks give ("Done, confirmed" when all work, "Ready, known fault" when any does not) and says "Claude is recording it." This is shown from the marks only; the page never writes the row. The row's real change (status, `shown_working`, marks deleted) is still the writer's to make, sent by the main session as before.

Delete a dealt-with mark: action "delete", collection "marks", doc_id `<row id>--<check id>`, `if_version` from the read.

## Questions: collection "questions"
Each question sits in the open view of the row it is about; the row's closed line says "A question for you"; the top of the page counts open questions. A question whose `row` is not a roadmap row shows at the top under "Questions not tied to a row".

**Questions in chat** are not here. A session's questions file shows as a copy under "Questions in chat", from `board/questions-file--<session's local id>`: `session`, `session_name`, `file`, `text` (the file as written, shown as markdown), `open` (how many), `changed` (date and time). Only that session writes it, as `python "${CLAUDE_PLUGIN_DATA}/scripts/questions_setup.py" roadmap` saves it (skill `assistant:questions`, "On the roadmap"); turning the file off deletes it. Answers are given in that chat or in the box under the copy, which writes one request, `board/ask-answer--<session id>--<time>`, with "set": `setting` "answer", `session`, `session_name`, `file`, `answer` (the person's words), `asked`, `status` "open", and sends Claude a comment: `Answered on the roadmap, for the questions file of the session "<name>" (<file>): <answer> (board/ask-answer--<...>)`. The main session takes it, or sends it on to the session that keeps the file, and marks it done (roadmap-director, "Settings pressed on the page"). Older `questions` documents with `source` "chat" are not shown.

Posting a question:
1. Upload each picture to the page's file store: Artifact {"action": "publish", "url": "PAGE", "asset": true, "file_paths": ["<picture 1>", "<picture 2>"]}. Keep each `url` the result gives, exactly as given.
2. Write the question with action "set", collection "questions", a new doc_id (`q-<row id>-<short-name>`), and data:
   - `row`: the row id
   - `topic`: a few words, shown as the question's heading
   - `question`: the question in plain words; **bold**, lists and line breaks show
   - `pictures`: a list of {"url", "caption"}, url from step 1 (leave out when there are none)
   - `choices` (optional): a list of short choices; the page letters them a, b, c
   - `status`: "open"
   - `asked`: date and time
   - `answer`, `choice`, `note`, `answered`: leave out; the page writes them
   - `history`: leave out on a new question; see "When the person answers with a question of their own"
3. Set the row's `changed`.

`history` (optional) is what was asked and answered before on the same question: a list, oldest first, of {"at": "<date and time>", "who": "asked" or "you" or "asked again", "text": "<the words>"}. "asked" is an earlier wording of the question (with `topic`, the topic it had then, only when the topic changed), "you" is the person's own words, "asked again" is a later rewording. Missing or empty means no history. The page shows it folded under the question as "Earlier on this question (N)", on open, answered and done questions alike. The list is replaced whole on update, so send every entry.

When the person taps Answer the page updates the same document: `status` "answered", `answer` (the whole answer as text), `choice` (the letter, or ""), `note`, `answered`. It then sends Claude a comment saying the question was answered; if no Claude session is listening it leaves the comment on the page. An answer can be changed until the question is marked done.

Read the answers:
```
ArtifactData {"action": "query", "url": "PAGE", "collection": "questions", "query": {"where": [["status", "==", "answered"]], "limit": 200}}
```
Open questions: the same query with "open".

### When the person answers with a question of their own
Their reply is not an answer, so the same question is asked again in clearer words. Keep the same document and the same id; never post a new question for it, and never replace the wording without the history. The topic stays the same unless the main session says otherwise. Read the document ("get"), then one "update" with its version:
- `history`: the list it had, plus two entries: the wording being replaced ({"at": the document's `asked`, "who": "asked", "text": the document's `question`}; when the document already has a history, "who" may be "asked again"), then the person's words ({"at": the document's `answered`, "who": "you", "text": the document's `answer`})
- `question`: the clearer wording the main session sent
- `status`: "open"
- `asked`: date and time now
- `answer`, `choice`, `note`, `answered`: removed, each written as {"__delete__": true}
```
ArtifactData {"action": "update", "url": "PAGE", "collection": "questions", "doc_id": "q-step-02-colour", "if_version": 3, "data": {"history": [{"at": "2026-03-04T16:09", "who": "asked", "text": "Which colour for the family room?"}, {"at": "2026-03-05T08:44", "who": "you", "text": "What family room are you talking about?"}], "question": "The room off the kitchen, with the fireplace: which colour for it?", "status": "open", "asked": "2026-03-05T09:10", "answer": {"__delete__": true}, "choice": {"__delete__": true}, "note": {"__delete__": true}, "answered": {"__delete__": true}}}
```
Then set the row's `changed`. The page shows the question open again with an empty answer box, and the old wording and the person's words folded under it.

Marking one done: action "update", the doc_id, `if_version` from the read, data {"status": "done", "done_note": "<one line: what changed because of it>"}. A done question folds into "Earlier questions, already acted on" on its row and can no longer be changed. When a question is deleted its pictures can be removed with Artifact {"action": "delete", "url": "PAGE", "path": "<asset id>"}.

## Notes: what the person writes on a row, collection "notes"
Every row, whatever its status, has a part "Say something about this" in its open view. The person types and taps Done; nothing is written or sent before that, and what they have typed is kept only in the open page until then.

- Each note is its own document, id `<row id>--<short id made from the time>`, fields `row`, `text` (their words), `written` (date and time), `status` "open", and `changed` (date and time) when they changed their words. Only the page writes a note's words; the writer writes one only for a press from another program's page (see "Presses from another program's page"), never otherwise.
- A note written from a check's "Comment only" is the same kind of document on the check's row, with two more fields: `check` (the check's id) and `check_text` (its wording when they wrote). It marks nothing: the check stays unmarked and the row's status does not change. Its comment reads `Written on the roadmap: a comment on the check "<wording>" on <row name> (notes/<note id>), not an answer to it: <their words>`, and arrives once, when they tap Done. The row lists it with the other notes, under "About the check: <wording>".
- When a note saves, the page sends Claude a comment at once, as it does for an answer: `Written on the roadmap: on <row name> (notes/<note id>): <their words>`. If they change an open note: `Changed on the roadmap: what was written on <row name> (notes/<note id>) now reads: <their words>`. If they take one back the page deletes it and sends `Taken back on the roadmap: ...`. If no Claude session is listening the comment is left on the page. A comment can be missed, so the main session still reads the open notes after each message from the person.
- A message from another program's page that starts "Press from the live page on the roadmap" carries the person's own presses, one line each in the words of the page's own comment above, each starting with a press id in square brackets. It is handled exactly as that comment, once for each press id, and the main session hands each press to the writer, which writes it as the page would have (next part). The plugin notes the ids it has given the main session, and presses made while that session was closed are given to it at its next message.
- The row's closed line counts its open notes ("1 note for Claude"), and the filter "Your notes" lists the rows that have any.

Read the open notes:
```
ArtifactData {"action": "query", "url": "PAGE", "collection": "notes", "query": {"where": [["status", "==", "open"]], "limit": 200}}
```
Marking one done: action "update", the doc_id, `if_version` from the read, data {"status": "done", "done_note": "<one line: what changed because of it>"}. The row then shows that line under "What changed", and the person can no longer change the note or take it back. Never change `text`.

A note is deleted (action "delete", the doc_id, `if_version` from the read) only when the main session says so, for example when its row is removed from the roadmap. A done note stays on its row as the record of what was asked and what came of it.

## What lives in the page itself
The status list, the colours, the layout and the filters. The page lays every row out in three folding sections by its status: Planning ("Planned, not started", "Not started"), Working (every other status) and Done ("Done, confirmed", last, and folded until the person opens it). Inside a section the steps and their phases come first, then the other work, each under its own small heading when a section holds both; each phase sits right under its step, and a phase whose step is in another section names its step. A done step folds its done phases into itself: it shows as one row saying how many are folded inside, and opening it shows them under it; a filter that picks out a folded phase opens its step. Which done steps a person left open is remembered in their browser. A row moves section as soon as its status changes, and the page remembers what the person folded in their browser. Change those only by editing "Roadmap page/roadmap.html" in the project folder and publishing it to the same link (Artifact publish with that file and `url` set to PAGE, leaving out `capabilities` so the database settings stay). The page's capabilities are {"db": {"rules": [{"path": "", "read": "view", "write": "admin"}]}, "assets": {}, "comments": {}}: the database, the picture store, and the comment it sends Claude when a question is answered, a check is marked or the person writes on a row.

## A roadmap that was made before the plugin
`/assistant:roadmap-setup` can take over a roadmap page a project already has, keeping its link and everything on it. Its command `carry-over` reads a saved copy of the old database and lists, document by document, what must change to fit this layout. It understands a roadmap already shaped like this one (rows in "steps", marks in "marks", questions in "questions", "What's next" in board/next) whose words differ: a status worded another way becomes the one of the eight it means, a `kind` that is not "step" or "phase" becomes "item", a field `waits_on_<a name>` becomes `waits_on_you`, and an older `scores` list with `scores_title` becomes `table`. Ids never change, no document is moved or deleted, and marks, answers, notes and pictures are not touched. Anything it cannot place it lists for the person to rule on. A project's own rules for its roadmap, carried over from its old instructions, live in `Roadmap page/Project rules.md` in the project.

## Presses from another program's page
A program that shows this roadmap on a page of its own (an assistant's live page) sends the person's presses back to the project. Each press is queued in `Roadmap page/from-page.json` under a press id like `rm:<key>:<unix ms>-<n>`: `{"op": "set" | "update" | "delete", "path": "<collection>/<id>", "data": {...}, "words": "...", "at": ..., "sent": ...}`. `op`, `path` and `data` are exactly the call the roadmap page itself would have made. The main session hands the press (its id and words) to the writer, and the writer makes that call itself, because here no page wrote it. It writes nothing of its own accord: only a press the main session hands it. A settings request (`board/ask-...`) is the exception: the main session writes it itself, as the press carries it, and never hands it to the writer.

The documents are the page's own, field for field:

| Press | Call | Document, fields exactly |
|---|---|---|
| A mark (Works / Doesn't work) | `set` `marks/<row id>--<check id>`; `delete` of it when the person cleared it | `row`, `check`, `text` (the check's wording they saw), `result` ("works" or "fails"), `note` ("" when none), `marked` (date and time) |
| An answer | `update` `questions/<question id>` with `if_version` from a read | `status` "answered", `answer` (the whole answer: "<letter>. <choice>" then a new line and their words, or just their words), `choice` (the letter, or ""), `note` (their words when a choice was picked, else ""), `answered` (date and time) |
| A note | `set` `notes/<row id>--<short id>` for a new one; `update` of it for changed words; `delete` when taken back | new: `row`, `text`, `written`, `status` "open" (and `check`, `check_text` when it was a comment on a check); changed: `text` and `changed` (date and time) |
| A settings request | `set` `board/ask-<setting>` or `board/ask-questions--<session id>`, written by the main session itself | `setting`, `value`, `session` and `session_name` (a questions file only), `asked` (date and time), `status` "open" |

Write `data` as the press carries it, changing nothing. When the press is no longer in the queue, build the document from its words and this table, with the time the press was made. Each press is written once, by its id:
- a `set` whose document already exists with the same content, a `delete` of a document already gone, and any press whose time (the unix ms in its id) is older than the document's own `marked`, `answered`, `written` or `changed`, is skipped; say so in the receipt;
- an answer to a question already "done" is skipped, and the receipt says the main session must tell the person;
- a press for a row or check that no longer exists is skipped and named in the receipt.

Then the main session acts on the press as on the page's own comment. After writing, bring the plain and full copies up to date as for any change.
