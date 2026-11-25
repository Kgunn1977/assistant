# Live item store: the contract

Owner: session live-engine. Reader: `System\live_page\`. This file is the exact shape; if it must change, this file changes first.

## Where it lives

- Home of the live system: `<home>` (the `Live` folder beside `System`)
- Database: `<home>\Resources\Database\assistant.duckdb` (a full copy of the engine's database, plus the table below)
- Table: `live_items`

## How the page should read it (important)

DuckDB on Windows lets one process write and nobody else read at the same time, and a pass holds the file for seconds at a time. So after every pass the engine also writes a snapshot the page can read with no lock:

- `<home>\items.json`: `{"written_at": "...", "pass_id": "...", "items": [ {every column below, same names}, ... ]}`. Every item whose state is not `done`, plus items done in the last 7 days (or the number of days the owner chose in Settings). Written whole to a temp file and renamed, so a reader never sees half a file.
- `<home>\health.json`: the health record (see the end).

Read those two files. Do not open the database from the page.

## How the page writes an answer back

Drop one file per answer into `<home>\answers\`, named `<id>-<unix time>.json`:

```json
{"id": "L1042", "action": "answer", "text": "Take the earlier date", "at": "2026-11-11T07:02:11"}
```

`action` is one of: `answer` (text is the owner's answer), `done` (finished), `not_mine` (hand it back), `reopen` (undo), `note` (text only). The next pass applies it, moves the file to `<home>\answers\applied\`, and the change shows in the next `items.json`. The page may show the answer at once from its own memory; the engine is the record. The engine never sends anything because of an answer.

A typed answer that changes a fact the card states rewrites the card itself (added 11/11/26): `title`, `detail`, `recommended` and `asks` are replaced whole from the latest facts, never kept with a note added on top. The owner's words and the questions they settled stay in `assistant_did`, and the result says `I rewrote the card to match.` An answer that changes no fact leaves the wording as it was.

A question the owner settled is never asked again (added 11/13/26). Each one is a history line `Answered by you: "<question>" (<their words>)`. Undo of a Done returns the card to its place without any question so settled, adds `Already answered, so not asked again: "<question>"` to that history line, and a card left naming nothing follows the rule below. Undo of an answer itself is the owner taking it back: the questions that answer settled return to `asks`, its history line ends `Asked again: "<question>"`, and from then on they count as open.

A card left with the owner names what it needs (added 11/11/26): an item written or rewritten in state `question` or `yours` always carries at least one line in `asks` (an open question, or the one action in plain words), a draft, a calendar choice or answer buttons. One that would name nothing gets its `recommended` step as that one line, starting `Your next step: `; with no recommendation either it becomes `handled` with `recommended` set to `Nothing is needed from you. You can close this card.` `detail` is the story, written afresh from the latest facts; what a new message adds to an item is a line in `assistant_did` starting `A new message came in: `, never added to `detail`.

## Columns of `live_items`

| Column | Type | Meaning |
|---|---|---|
| `id` | VARCHAR, primary key | Stable id, `L` plus a number (`L1042`). Assigned once, never changes, never reused. |
| `source_key` | VARCHAR, unique | What the item was made from, so a later pass updates it instead of making a twin. `task:<engine item key>` for items from the engine's task list, `live:<slug>` for the live system's own (`live:msg-<message id>` for an item made from new mail that had no item). |
| `kind` | VARCHAR | One of `question` (the owner must decide), `approval` (a draft waits for a yes), `task` (work that is the owner's), `waiting` (someone else owes the next move), `fyi` (told, nothing to do), `system` (about the assistant itself). |
| `area` | VARCHAR | The engine's area, as the owner's rules name them; `System` for the assistant itself. |
| `title` | VARCHAR | One plain sentence. |
| `detail` | VARCHAR | The story. No length limit (the page keeps it folded inside the card). May be null. |
| `state` | VARCHAR | One of `new` (arrived, not judged yet), `yours` (the owner's to do), `question` (waits on an answer), `in_motion` (the assistant or someone else is on it), `handled` (the assistant finished it; shown so the owner knows), `done`. |
| `importance` | INTEGER | 0 normal, 1 important (a phone alert goes out once). |
| `important_reason` | VARCHAR | Which line of the important list matched, in plain words. Null when 0. |
| `source_who` | VARCHAR | Who it came from, as a name (`Sam Lee`). |
| `source_when` | TIMESTAMP | When the newest message behind it arrived. |
| `source_ref` | VARCHAR | One plain line: who, when, which message. `Sam Lee, email to info@example.com, 11/10 1:19 PM (73173)`. |
| `source_messages` | VARCHAR (JSON list) | Engine message ids behind the item, newest first: `["73173","73144"]`. |
| `recommended` | VARCHAR | The assistant's recommended answer, one or two sentences. Null when it has none. |
| `asks` | VARCHAR (JSON list) | The exact questions for the owner, in order: `["Take the earlier date or wait?"]`. Empty list when none. |
| `draft` | VARCHAR (JSON object) | A draft that waits for approval: `{"outbox_id":1,"kind":"","to":[],"cc":[],"subject":"","body":"","account":"","attach":[]}`. Null when none. |
| `evidence` | VARCHAR | The evidence in one line. |
| `evidence_files` | VARCHAR (JSON list) | `[{"label":"The quote","path":"C:\\...full path"}]`. Full paths, files exist when written. |
| `assistant_did` | VARCHAR | What the assistant has already done on it, one line per action, newest last. Null when nothing. |
| `answer` | VARCHAR | The owner's latest answer from the page. Null until answered. |
| `answered_at` | TIMESTAMP | When it was answered. |
| `due_date` | DATE | Null when none. |
| `checkback_date` | DATE | When a waiting item should come back up. Null when none. |
| `created_at` | TIMESTAMP | When the item was first made. Never changes. |
| `from_at` | TIMESTAMP | When the card is from: the arrival of the earliest message behind it, else `created_at`. Stored once at export (`stamp_from`); an answer the owner types on the card, or gives a question by its choice button (not Approve, Done, Snooze, Not needed or other state buttons), sets it to the time of the answer, so the card becomes the newest (its first message stays in `source_messages`, `created_at`); shown at the card's top right and used by Newest first and Oldest first. |
| `last_at` | (exported) | When the newest of all the messages behind the card came, to the minute (`items.last_at`); absent with none. Recently active goes by it. |
| `updated_at` | TIMESTAMP | Last change of any column. |
| `state_changed_at` | TIMESTAMP | Last change of `state`. |
| `done_at` | TIMESTAMP | When it became `done`. Null otherwise. |
| `last_pass` | VARCHAR | The pass that last touched it. |
| `status` | VARCHAR | A short word for the page (`Answered`, `Approved`, `Snoozed to 11/12`, ...). Null when none. |
| `calendar` | VARCHAR (JSON object) | On an item that asks the owner to put something on the calendar: `{"title":"Coffee with Chris","date":"2026-11-12" or null,"start":"15:00" or null,"end":"16:00" or null,"all_day":false,"certain":true,"location":null}`. `certain` true means the day and time are both stated in the mail. After the answer, the same object holds what was chosen, plus `"chosen": true` and `"accepted_as_shown"`. |

The table may still hold columns no code reads; `items.json` does not carry them.

A calendar answer arrives as action `answer`, page_action `calendar`, `text` in plain words, plus a `calendar` object with exactly what was chosen. The engine adds the event to the owner's main calendar by the Calendar part's own code (calendar_view.add), then records it (state `handled`, status `Calendar: added`, what was added and where in `assistant_did`); when it cannot be added the card stays open with status `Calendar: not added` and the reason. A card whose event was added is never added twice.

Besides the columns, an item in `items.json` may carry `source_text` (the newest message's own words), `choices` (answer buttons) and `best_guess`.

An item that is not `done` and whose messages came with attached papers also carries `documents` (added 11/11/26), newest message first, so the owner can read the papers before answering: `[{"file": "Quote 118.pdf", "read": true, "pages": 2, "text": "the words read from it, [page 2] before each later page", "cut": false}, {"file": "Plan.dwg", "read": false}]`. `read` false means the assistant has not read that paper yet, so its words cannot be shown. The same paper sent twice shows once; pictures a mail program puts in a signature and attachments marked discarded are left out. All the words on one item together stay within 20,000 characters; a paper cut short ends with a line saying so and has `cut` true. Absent when there are none.

An item that is not `done` and whose newest message is an email also carries `reply` (added 11/11/26), so the page can offer a reply by email on it: `{"account": "the account it came to, or went from", "to": ["sam@example.com"], "subject": "Re: the message's subject"}`. `to` is the sender when the mail came in, or the people it went to when the owner sent it, lower case, never the account itself, at most 10. A subject already starting `Re:` is kept as it is; an empty one stays empty. Absent when the newest message is not an email or there is nobody to reply to. It only fills in the writing screen: what goes is still exactly what the owner leaves on screen and presses Send on.

`<home>\known_people.json` is the lookup the contact rule uses: every named contact with addresses and newest message, rewritten each pass.

In `items.json`, timestamps are ISO text (`2026-11-10T13:19:00`), dates are `2026-11-10`, and the JSON columns are already real lists or objects, not text.

Sort order the engine intends: importance 1 first, then state in the order question, yours, new, in_motion, handled, done, then newest `source_when`.

## health.json

```json
{
  "written_at": "2026-11-11T07:15:40",
  "last_pass": {"id": "20261111-071500", "started": "...", "secs": 38.2, "new_messages": 3, "ai_calls": 2, "outcome": "ok"},
  "last_new_mail_at": "2026-11-11T07:15:12",
  "sources": {"email:info@example.com": {"status": "ok", "detail": "", "at": "..."}, "calendar": {...}, "sms": {...}},
  "ai_steps": [{"at": "...", "step": "judge", "ok": true, "secs": 212, "tries": 1, "why": ""}],
  "problems": ["plain sentences, empty when all is well"],
  "alerts": {"enabled": false, "last_sent_at": null}
}
```

`problems` is what the page prints. `ai_steps` holds the last 20. `sources` holds only the sources the owner turned on.

## Sending an email the owner wrote (added 11/11/26)

The live system sends exactly one kind of thing: an email the owner wrote or edited on the page and pressed Send on themself. The rule and every check live in `send.py`, which only a person changes. Nothing else sends.

The page's data carries `send` in its top block: `{"on": true, "accounts": ["the owner's own sending accounts"]}`. When `on` is false the page offers no Send.

The top block also carries `people` (added 11/11/26), the address book the writing screen suggests recipients from, made from `<home>\known_people.json`: `[{"name": "Sam Lee", "company": "Example Co" or null, "email": ["sam@example.com"]}]`. Only people with a name and at least one plain email address (at most three each, lower case), ordered by how often the owner has written to them, then by their newest message; at most 300 people and 60,000 bytes. An empty list when the lookup is missing. Suggestions only: what goes is what the owner leaves in To and Copy to.

A Send press is saved like any answer, on the item the email belongs to (or on the key `compose` for an email written from scratch), with action `answer` and `text` holding JSON:

```json
{"send_email": {"account": "one of send.accounts", "to": ["a@b.c"], "cc": [], "subject": "...", "body": "...",
                "attach": ["file name exactly as the card lists it"],
                "shown": {"account": "...", "to": ["a@b.c"], "cc": [], "attach": ["..."]}}}
```

Before Send is pressed the page must show the account, every recipient (To, Copy to, Blind copy), the kind of email (new, reply, reply to all, forward) and every attachment; `shown` is exactly what was on screen, and the engine refuses a press whose `shown` differs from what would go. A draft in Drafts (in Mail) carries `type`, `bcc`, `files` (attachments by reference: a stored email's file, a file of another email, or one the owner added) and `source` (the email it answers or forwards); the engine builds the whole email from them (mail.py) and refuses the send when any file cannot be fetched. An answer's text holds at most 4,000 characters in all, so a long email is refused by the site until that limit is raised. Attachments are only files the item already lists (`evidence_files`, `documents`).

What comes back as the result of the press: `Sent from <account> to <recipients>: "<subject>".`, or `Not sent. <the reason>`, and the same line is added to the item's `assistant_did`. A sent item goes to `in_motion` with status `Sent` and its `draft` is cleared; a failed or refused send sets status `Send failed` and keeps the draft. One press sends once; the same email pressed again within two minutes sends nothing more. Every send is written to `<home>\\logs\\sent.log`.

## Roadmaps (added 11/15/26)

Roadmaps come from a separate plugin (Roadmap). The assistant holds none of its files; the link is that plugin's written agreement (`reference\agreement.md` there), which `System\live_page\roadmaps.py` follows as a reader and `setup_steps.py` follows when it lists the assistant in a project's `Roadmap page\readers.json`.

The owner chooses which projects to show (`roadmaps` in the personal folder's `settings.json`: `[{"folder": "full path", "applied": "..."}]`, written only by setup). With none chosen the page's data carries no `roadmaps` key and the page shows no roadmap part.

With one or more chosen, the top block carries `roadmaps`, one entry per project in the order chosen, read from each project's plain summary (`<project>\Roadmap page\roadmap.json`):

```json
{"key": "a1b2c3d4e5", "name": "Kitchen Remodel Roadmap", "folder": "Kitchen", "link": "https://claude.ai/...",
 "next": [{"label": "Working on now", "text": "..."}],
 "rows": [{"n": "2A", "name": "...", "kind": "step|phase|other", "status": "as the roadmap words it", "changed": "2026-03-04T10:05", "sub": true}],
 "rows_total": 14, "checks_waiting": 3, "questions_open": 1, "changed": "2026-03-04T10:05", "written": "2026-03-04T10:05:09"}
```

`sub` is true for a phase of a step. `changed` is the newest row change. `link` is there only when it is a claude.ai address. A chosen project whose roadmap has not been written yet is left out (with only such projects there is no `roadmaps` key); one that cannot be read for another reason carries `note` (one plain sentence saying why) in place of everything after `folder`. At most 12 next lines and 400 rows each. The page only reads this; it writes nothing back for a roadmap.

The 15-minute pass sends it with everything else. Between passes the listener looks at the dates of those files each time its wait comes back and sends the page a roadmap that changed. No AI is used for either.

## Where the page is served from

`page_hosting` in the personal folder's `settings.json` says where the owner's page is served from: `own_pc` (this computer, the default when nothing is set), `hosted` (the owner's web host) or `both`. `page_port` (default 47815) is the port of this computer's page. The listener serves this computer's page itself (`System\live_page\local_site.py`), on 127.0.0.1 only, from the same page files the web host gets; its password is set once at a one-time address made by `local_site.py --setup`. `publish.targets()` lists every place the page is served from; the sender and the listener treat each the same way, and a change made from one page is sent to the other.

## Settings the owner changes on the page (added 11/16/26)

The page has a Settings panel. The rule and every check live in `settings_page.py`.

The top block carries `settings`, the present values, for the panel to show:

```json
{"you": {"first_name": "", "full_name": "", "about": "", "page_title": "", "page_subtitle": "", "areas": []},
 "calendar": {"calendars": [{"name": "", "on": true}]},
 "watch": {"important": [], "own_domains": [], "ignore_senders": [],
           "paused": false, "paused_since": null, "every_minutes": 15},
 "alerts": {"on": false, "topic": "", "server": "", "quiet_from": "", "quiet_to": ""},
 "page": {"theme": "auto", "text_size": "normal", "order": {"main": ["decide", "small", "tracked", "roadmaps"], "side": ["today", "handled"]},
          "hidden": [], "done_days": 7, "snooze_days": 0, "clock": "12"},
 "signin": {"days": 90},
 "thinking": {"model": "opus", "models": [{"id": "haiku", "words": "..."}], "daily_limit": 0, "runs_today": 0, "limit_reached": false},
 "pc_only": {"roadmaps": [], "accounts": [{"name": "", "health": ""}], "sending": false, "lives": ""}}
```

`alerts.topic` is the private channel name of the owner's phone alerts; it is shown on the page and never logged. `pc_only` is for reading only. No password, sign-in or key is ever in it.

A Save press is saved like any answer, on the key `settings`, with action `answer` and `text` holding JSON for one group:

```json
{"settings": {"group": "you | watch | alerts | page | signin | thinking", "values": {"field": "value"}}}
```

The engine handles the key before any item lookup, as it does `chat` and `compose`. It takes only these fields, checks every value, and writes them the way the setup window does (the same functions in `setup_steps.py`):

| Group | Fields |
|---|---|
| `you` | `first_name`, `full_name`, `about`, `page_title`, `page_subtitle`, `areas` (list) |
| `calendar` | `calendars` (list of names to show in Today) |
| `watch` | `important` (list), `own_domains` (list), `ignore_senders` (list of addresses or domains), `paused` (true or false), `every_minutes` (15, 30 or 60) |
| `alerts` | `on` (true or false), `quiet_from`, `quiet_to` (`HH:MM`, both or neither) |
| `page` | `theme` (`auto`, `light`, `dark`), `text_size` (`small`, `normal`, `large`), `order` (`main` and `side`, each the same names in a new order), `hidden` (list of section names), `done_days` (3, 7, 14, 30), `snooze_days` (0, 1, 3, 7), `clock` (`12`, `24`) |
| `signin` | `days` (1, 7, 30, 90) |
| `thinking` | `model` (one of `thinking.models`), `daily_limit` (0 to 10000; 0 is no limit) |

Anything else refuses the whole save and changes no file: another group, another field, a value outside the list, or anything about sending, where the page lives, its port, a connection, a key or a roadmap. Those are changed only with a command typed in Claude on the owner's computer (`/assistant:change`, `/assistant:introduce`). The result of the press is one plain line: `Saved: <what>. <when it takes effect>` or `Not saved. <the reason>`.

Everything saved goes to the owner's personal folder: `personal.json` (the `you` group, `today_calendars`, `own_domains`, `ignore_senders`), `Important.md`, and `settings.json` (`alerts`, `gathering`: `{"paused", "paused_at", "every_minutes"}`, `page`, `signin_days`, `thinking`: `{"model", "daily_limit"}`). An absent setting behaves as before settings existed.

What each does in the engine:
- `ignore_senders`: mail from a listed address or domain is settled as noise before judging, so it makes no card and no alert. One of the owner's own domains is never ignored.
- `gathering.paused`: a pass that starts while paused gathers nothing and thinks about nothing new; it records the pause in `health.json` (`paused`: `{"since"}`) and ends. Answers on cards still work.
- `gathering.every_minutes`: the least time between gatherings. A pass that starts sooner ends at once. `<home>\last_gather.json` holds when the last gathering started.
- `alerts.quiet`: inside the hours no phone alert is sent. What would have alerted is kept in `<home>\alerts_held.json` and sent as one alert when the hours end, only for items still open and important.
- `page.done_days`: how long a done item stays in `items.json` (7 when absent).
- `thinking.model`: the model the judging and item writing steps run on (`opus` when absent). Reading pictures, typed answers and the chat box keep their own.
- `thinking.daily_limit`: every Claude run the assistant starts is counted in `<home>\ai_runs.json` (`{"day", "runs"}`). At the limit nothing new is thought about until midnight: a pass does not think, a typed answer is saved with status `Thinking` and read first the next day, and the chat box says so.

`today.json` also carries `calendars`, the names of every calendar the engine holds events for, for the panel's list.

The page's password, how long a sign-in lasts and "sign out everywhere" are the page server's own (`local_site.py`, `site\index.php`). The servers read `settings.signin.days` from the feed when a browser signs in. A password change (`api/password`: the present password, the new one twice) and sign out everywhere (`api/signout_all`) act on that server only and never reach the engine.

## Reaching this computer's page from anywhere (added 11/16/26)

`page_hosting` says where the page is served from and does not change. A second setting in the personal folder's `settings.json` says how this computer's own page is reached:

```json
"page_reach": {"how": "tailscale", "port": 8443, "address": "https://machine.tailnet.ts.net:8443", "read_at": "2026-11-16T12:00:00"}
```

`how` is `this_pc` (only from this computer; the same as no `page_reach` at all) or `tailscale` (also from anywhere, through Tailscale's Funnel). `port` is the public port Tailscale listens on for this page: 443, 8443 or 10000, the first one nothing else on this computer's Tailscale was using. `address` is the public address as last read back from Tailscale. Only the setup window writes it (`setup_steps.reach_on`, `reach_off`); no page can change it.

The relay hands every request to the page this computer already serves (`http://127.0.0.1:<page_port>`), so there is no new place in `publish.targets()` and answers reach the listener exactly as before. The page server (`local_site.py`) answers to this computer's own names and, while `how` is `tailscale`, to the name in `address`, and to nothing else. A request that came by the public name gets a sign-in cookie marked Secure, is never let through the engine's own doors (`api/feed`, `api/progress`, `api/files`, `api/answers` with the key), and has its wrong passwords counted apart from sign-ins made at the computer itself.

The page's data says it in `settings.pc_only.lives` (words) and `settings.pc_only.public_address` (the address, or absent).

## Design round 1: the card, the presses, the assistant's own section, settings as data (added 11/16/26)

Everything above stays valid, except the two sections on cards the assistant made about changing itself, which are gone (the assistant does not change its own program). An old card, an old press and an old page keep working: every field below is added, none is renamed or removed, and every new field is filled by the machinery for every card in `items.json` (never left to Claude's goodwill), so the page may rely on each one being there.

### New fields on every card in `items.json`

| Field | Type | Meaning, limit, example |
|---|---|---|
| `header` | text, always there | The card's one line, WHOLE: a short phrase written for the card by the same Claude run that writes it (the writer aims at 90 characters or less; the machinery never cuts it and never adds dots, so a longer one is shown whole). A card with no such phrase carries its whole `title` here. The page lets it wrap. Stored as `short_header`; a title rewritten without a new header clears it. A card that was open before 11/16/26 with a title over 90 characters is sent once, with the others like it, in one run on the fastest model (`headers.py`), and never again. |
| `needs` | one word, always there | What kind of thing the card needs from the owner: `answer` (a question to answer), `approval` (a draft or a yes waits), `do` (work only the owner can do), `waiting` (someone else owes the next move), `nothing` (it only informs; the page shows Got it). A card in state `done` carries `nothing`. Worked out by the machinery from the card's state, draft, questions and buttons. (The old `kind` column is unchanged and means something else; read `needs`.) |
| `wants` | text or null | The one thing wanted from the owner, one line, whole (never cut). Null only when `needs` is `waiting` or `nothing`. `"Take the earlier date or the later one?"`, `"Call the school about Friday pickup."`, `"Approve or change the draft to pat@example.com."` Written by Claude in the call that already writes the card; when that is missing the machinery uses the first question, else the recommended step, else the draft or calendar line. |
| `why` | text, always there | Why the assistant showed it, one short line, whole (never cut), WITHOUT the words "Here because:" (the page prints those). `"Pat asks you for a date by Friday."` Written by Claude in the same call that judges or writes the card, never an extra call. A card made before this, or one Claude gave none, gets a plain machine line: `"Pat Example wrote to you on 11/16."` When the judge marked a message behind the card not covered by any rule (`covered` false in `answered`), the line starts with its best guess: `"My rules don't cover this; my best guess: a supplier asking to confirm a delivery day. Pat Example wrote to you on 11/16."` |
| `uncovered` | text, optional | The judge's best guess (its reason) when no rule decided a message behind the card; the engine already put it into `why`, so the page needs nothing more. |
| `detail` | text or null | The story. It has **no length limit** now; the page keeps it folded inside the card. (Same field as before; only its limit is gone.) |
| `shelf` | `null`, `"later"` or `"someday"` | Where the card is while it is put off. `later`: off the page until `later_until`. `someday`: off the page until brought back. Null: on the page as usual. |
| `later_until` | ISO date and time, or null | With `shelf` `later`: when the card returns by itself (the first pass at or after that time clears `shelf`, with the history line `Back from Later ...`). The page may also treat a card whose `later_until` has passed as back. |
| `last_press` | object or null | What the newest press on this card did: `{"press": "later", "at": "2026-11-16T14:02:11", "happened": "Put off to tomorrow, Tue 11/17. It comes back by itself.", "claude": false, "open": null, "ok": true}`. `happened` is plain words for the owner. `claude` is true when a Claude run was started for this press. `open` is `"writing"` when the page should open the writing screen for this card's draft now (after Approve on a draft), else null. |

`status` keeps its short word (`Later to 11/17`, `Someday`, `Got it`, `Junk`, `Done`, `Approved`, ...).

### Presses

A press travels as an answer always did (page, page server, listener, engine). So that both page servers pass it unchanged, a press is the action `answer` whose `text` is JSON, the same way a Send press and a Save press already travel:

```json
{"key": "L1042", "record": {"id": "L1042", "action": "answer", "at": "2026-11-16T14:02:11",
                            "device": "Phone, Chrome", "text": "{\"press\": {\"name\": \"later\", \"when\": \"tomorrow\"}}"}}
```

`device` is a few plain words the page works out about the browser it runs in (at most 60 characters, for example `Phone, Chrome` or `Computer, Edge`); it is recorded with the press.

| `name` | Extra | What the engine does, at once, with no Claude run | `happened` says |
|---|---|---|---|
| `done` | | The card is done (`state` `done`, `status` `Done`). | `Marked done.` |
| `got_it` | | For a card that needs nothing: done, `status` `Got it`. On any other card it is refused, and the card stays. | `Closed.` |
| `got_it_all` | `ids`: list of card ids, or absent for every open card whose `needs` is `nothing` | Sent on the key and id `press`. Every listed card that needs nothing is closed as by `got_it`; any other is left as it is. | `Closed 9 cards that needed nothing.` |
| `later` | `when`: `today`, `tomorrow`, `next_week`, `date` (with `until`: `YYYY-MM-DD`) or `someday` | `today`: `shelf` `later`, back 3 hours after the press. `tomorrow`: back at 6:00 AM tomorrow. `next_week`: back at 6:00 AM next Monday. `date`: back at 6:00 AM that day (a day not after today is refused). `someday`: `shelf` `someday`, `status` `Someday`, no return time. | `Put off to tomorrow, Tue 11/17. It comes back by itself.` / `Put off to Someday, under Waiting, until you bring it back.` |
| `someday` | | The same as `later` with `when` `someday`. | as above |
| `bring_back` | | A card on a shelf returns to where it was: `shelf` and `later_until` cleared, `status` cleared, state untouched. | `Back on your page.` |
| `junk` | | The sender of the card's newest message goes on the owner's Always junk list the same moment (and off Never junk), and the card is done with `status` `Junk`. At the next sorting, mail from that sender makes no card. A card with no outside sender, or whose sender is one of the owner's own domains, is refused. | `sam@example.com is on your junk list. This card is closed.` |
| `never_junk` | | The sender goes on the owner's Never junk list the same moment (and off the junk lists). The card stays as it is. | `sam@example.com is on your never junk list. Its mail is always read.` |
| `approve` | | The owner's yes is recorded (`status` `Approved`). When the card holds a draft, `last_press.open` is `writing` and nothing else happens: nothing is sent; only the owner's own Send press sends. | `Your yes is recorded. Nothing is sent until you press Send.` |
| `undo` | | The newest press on the card is taken back: a Done, Got it, Later, Someday or Junk returns the card to where it was (Junk also takes the sender off the junk list); a Never junk takes the sender off that list; an answer taken back asks its questions again. On the key `press` it brings back every card the last `got_it_all` closed. | `Taken back.` |

The old forms still work and mean the same: action `done`; action `reopen` (and the page clearing its answer for a key) is `undo`; action `approve`; action `later` with no `until` is `later` `tomorrow`; action `snooze` with `until` is `later` `date`. On the junk question card (`choices` `Junk`, `Never junk`), the plain answer `Junk` or `Never junk` acts on every sender that card names. A junk question card about one sender, while it is open, also carries `sample: true`: the page offers Read a sample, which asks the page server's door `api/mail/sample?card=<id>[&id=<message id>]` and gets `{ok, sender, list: [{id, when, subject}], message}`, that sender's newest emails (at most 20, newest first) and one of them in full. It reads the mail stored on the computer only: nothing is marked read and nothing is asked of the mail service.

Words: any other `answer` text (the owner's own words, typed on a card) goes to Claude at once, exactly as before: the card shows `status` `Thinking`, `last_press.claude` is true, and the result replaces `last_press.happened` when the run ends. One typed answer starts one Claude run.

What the page receives after any press, always:
1. The answer mark for that key, as today: `status` `working`, then `done` or `failed`, and `outcome` (the same plain words as `happened`).
2. The card itself, sent again at once with its new state and `last_press`.
A press that cannot be acted on is never silent: `ok` is false in `last_press`, `happened` says why in plain words, and the card is unchanged.

Every press is one row in the table `live_presses` of the home's database (written the moment it is acted on; while a pass holds the database it waits in `<home>\presses_waiting.jsonl` and is written seconds later): `id`, `pressed_at` (the page's clock), `received_at`, `item_id`, `item_title`, `press`, `choice` (the `when`, the date, the button's text, or `-`), `words` (the owner's typed words, or `-`), `device` (or `unknown`), `happened`, `ok`, `claude_ran`, `secs` (from reaching the engine to being acted on; for a typed answer, to the end of the Claude run), `meaning` (one of `agrees`, `disagrees`, `contradicts-show`, `contradicts-hide`, `wrong-section`, `not-needed`, `needed`, `other`, `neutral`, the fixed list in presses.py; every press has one, Got it, Done and Snooze are `neutral`; a table from before meanings gets the column filled from each row's press), `button` (a choice button's id, or `-`). Nothing in it is a password or a key.

A choice button (`choice`): the answer carries the choice's words as before, plus `button` (its id) and `meaning` (from the list above). The words are read exactly as before; the row is press `choice` (or the press its words make, such as `standing`), `button` its id, `choice` its words, `meaning` as sent. A meaning not on the list, or no id, is refused like a press with an unknown name and nothing changes. Choices that name neither get their place on the question as id (`q1-2`) and the meaning `other`.

A choice Claude writes for a card (the card writer, prompts\items.md, and a card's chat, prompts\chat_card.md) is `{"text", "meaning"}`; items.card_extras keeps the meaning on the button only when it is on the list and not `other` or `neutral`, and drops any other, so its press records `other`. A bare string still works and records `other`. An add-on's own choice keeps its meaning only when it is on the list (items.own_meanings), so an add-on's card is never refused for a meaning word.

Switchable buttons (`switches` on a card, `[{"id", "label"}]`, decided by card.switches, never by Claude): `Hide mailings like this` (press `hide_like_this`, meaning `contradicts-show`) on an open card whose newest email is a mailing by rule 559's own test (the card's `mailing`); `Keep showing these` (press `keep_showing`, meaning `agrees`) on an open card from an outside sender that needs nothing. None on the system's own cards. Each is its own press (presses.SWITCHES): the page sends only its name, the meaning is the engine's. It closes the card (Not needed, or Got it) and changes no setting, list or rule itself; Undo takes it back. At learning level 1, and at level 2 while no rule change is open for the card's section, it then offers a rule through the teach flow, as This kind of message does (a show less rule for Hide mailings like this, an always show rule for Keep showing these): one small Claude run, a rule card, nothing in force until Approve. A press of one the card does not offer is refused. The grader counts each against the call it names (hide, show), so Keep showing these counts as agreeing with a show; every other `agrees` or `disagrees` (Approve, a choice) says nothing about show or hide. A row from a mailing card is in the section `mailings`.

The "I'd hide this" card (wouldhide.py; guardrail A13 as amended, and only this): after the judge runs in a check, each message it judged `noise` in that check, when neither the owner's own rules nor his Settings choices cover the verdict, gets one short card, `I'd hide this: <who>: <what>` (source key `live:wouldhide-<message id>`, kind fyi, needs nothing), with the switches `Hide things like this` (press `hide_like_this`) and `Keep showing` (press `keep_showing`), and no teaching menu. His rules cover it when its reason starts `owner rule <n>:` or its `leaned_on` names `owner rule <n>` for a rule of his that is on (a bare number never counts). His Settings choices cover it when its reason or `leaned_on` names `setting <name>` (each setting line the judge is told carries that tag) for a filter setting at a value that holds things back (wouldhide.SETTING_HIDES: strictness balanced or only what needs me, kept mailings only when due or wrong, notices only failed, mailings or short-number texts hidden, and the program-layer holds); when it leaned on rule 559 while mailings are hidden, or rule 560 while short-number texts are; and always while strictness is only what needs me. A noise verdict his rules or Settings choices cover stays hidden with no card, as before; so does every verdict a setting, a junk rule, a list, the first sort, an add-on or the history reload settled. The message's verdict stays noise, so its rule book row records call hide and layer judge: Hide things like this agrees with that call and offers a hide rule through the teach flow as Hide mailings like this does (a rule card; nothing in force until Approve); Keep showing contradicts it (its RSI job is queued like any miss) and offers no rule. One card per message, ever: I should have seen this on the message's row under Hidden acts on this card (open again if closed, marked Shown at your asking) and never makes a second one. The setting that hides cards needing nothing never hides it. A replay day makes none. The card writer, a rebuild and a join never change it.

Learning level 3, It improves itself (rsi_loop._improve, coach.self_promote; guardrail A15 as amended, and only this): in a section the owner set to level 3 in Settings, a queued RSI job runs rounds of grade, coach and grade-draft. A draft is promoted with no press only when it is a rule change, fully scored, breaks none of his answers his live rules matched, and matches more of them than his live rules do; any other draft is closed as rejected with why. It stops when every answer matches, after 10 rounds, or at the RSI daily cap (the job then waits). A setting or list change is never made on its own: it gets its Apply card as at level 2. Each promotion is a version in `personal\rsi_versions\` marked `by_itself`, shown in Change history (id `rsi-<stamp>`, status `learned`) with Undo, which puts back the rules kept before it (refused, changing nothing, when his rules changed since; a change he undid is never made on its own again). Levels 1 and 2 are unchanged.

### The assistant's own section ("Errors")

The top block carries `about`:

```json
{"problems": [{"text": "Your Google Calendar connection has not answered since 11/16 9:15 AM.", "what": "source"}],
 "ok": false, "last_gathered": "2026-11-16T14:10:00", "paused": false, "limit_reached": false}
```

`problems` is every health problem in plain words, empty when all is well (`ok` true); `what` is one of `source`, `thinking`, `page`, `pass`, `other`. No card is ever made about the assistant itself; a home that still holds such cards from before has them closed once, at its first pass (`items.close_retired`), with one history line, and they are left out of `items.json`.

### Settings sent as data

Beside `settings` (unchanged), the top block carries `settings_defs`, so the page draws any setting from data and needs no change when one is added:

```json
{"groups": [{"id": "watch", "label": "What it watches", "can_save": true}],
 "settings": [{"group": "watch", "id": "every_minutes", "label": "How often it gathers", "help": "A longer gap uses less.",
               "control": "choice", "choices": [{"value": 15, "label": "Every 15 minutes"}], "value": 15, "can_change": true}]}
```

`control` is one of `text`, `long_text`, `list` (lines of text), `toggle`, `choice`, `number` (with `min`, `max`), `time` (`HH:MM`), `checks` (several of `choices`; value is the list of chosen values), `order` (value as in `settings.page.order`), `words` (read only). `can_change` false means the page shows the value with `help` saying where it is changed and offers no control. A group with `can_save` true has one Save, sent exactly as before (`{"settings": {"group": ..., "values": {id: value}}}` on the key `settings`); the engine still checks every value against its own fixed list, whatever the page sends. The password, sign out everywhere and the phone alert test stay the page's own, outside this list.

A new list the owner can edit (group `watch`): `keep_words`, the words in a subject that keep an email with an unsubscribe link from being settled as junk before it is read (a bill, an order, a delivery...). The general part's starter list is empty.

## Design round 2: what was held back, teaching presses, the owner's rules, filter settings, cards that come back (added 11/16/26)

Everything in "Design round 1" stays. New presses travel the same way (action `answer`, `text` = `{"press": {...}}`, `device` on every one) and come back the same way (the answer mark, and the card again with `last_press`).

### What was held back

The feed carries one more document beside `current` and the parts, named `held` (the page reads it as `live.held`):

```json
{"written_at": "2026-11-16T14:10:00", "today": 43,
 "days": [{"date": "2026-11-16", "count": 43,
           "rows": [{"key": "held-10231", "who": "Loud Shop", "address": "deals@loudshop.example", "what": "Your weekly picks are in",
                     "at": "2026-11-16T09:12:00", "channel": "email", "why": "It is a mailing with an unsubscribe link, and its subject holds none of your keep words.",
                     "by": "setting", "shown": false}]}]}
```

Today and the six days before, newest day first, newest row first, at most 300 rows a day (`count` is the true number). A row is one message that came in and was kept off the page. `what` is the subject, or the first words when there is none (120 characters at most). `why` is one plain line naming what held it. `by` is one of `junk_list`, `ignore_list`, `setting`, `rule` (one of the owner's own rules; the line names it), `sorting` (the sorting step judged it needs nothing; the line gives its reason). `shown` true means the owner already pressed "I should have seen this" on it. The top block also carries `held_today` (the count), so the page can show the line without opening the list. A row whose `key` starts `card-` (and `channel` `card`) is a card kept out of the feed by the setting that hides things needing nothing; the same press brings it onto the page and keeps it there.

Press on a row, sent on the row's `key` as both key and id:

| `name` | What the engine does | `happened` (in the answer mark's `outcome`) |
|---|---|---|
| `should_have_seen` | Makes that message's card at once, with no Claude run in every case: header from the subject, the message's own words as the story, state `yours`, the one thing wanted `Read it and decide what it needs.`, why line `You said you should have seen this.` The row's `shown` becomes true. While a pass holds the database the card is made within seconds, and the mark says so. | `It is on your page now.` |

The card it makes carries `teach`: `["always_sender", "always_kind"]` (see below). The mark for this press also carries the new card in the feed at once.

### Teaching presses on a card

Every open card that came from someone outside carries `teach`, the choices the page may offer, in order. A card made by "I should have seen this" carries `["always_sender", "always_kind"]`; any other carries `["not_needed_this", "not_needed_sender", "not_needed_kind"]` (without `not_needed_sender` when the sender is one of the owner's own). A card with no outside sender carries `["not_needed_this"]`.

| `name` | Extra | What the engine does | Claude |
|---|---|---|---|
| `not_needed` | `scope`: `this` | The card is done with `status` `Not needed`; the press is recorded. | no |
| `not_needed` | `scope`: `sender` | The sender goes on the owner's ignore list the same moment (Settings, "Senders to always ignore"), and the card is done. The next message from them is held back with that reason. | no |
| `not_needed` | `scope`: `kind` | The card is done, and one small Claude run proposes one rule in a plain sentence. It arrives as a rule card (below). Nothing takes effect until Approve. | one run |
| `always_show` | `scope`: `sender` | The sender goes on "People who always get through" the same moment (and off the junk and ignore lists). The card stays. | no |
| `always_show` | `scope`: `kind` | One small Claude run proposes one "always show" rule, as a rule card. The card stays. | one run |

Undo (`undo`, or clearing the answer) takes back `this` and `sender` (the sender leaves the list). A rule proposal is taken back with No on its card.

A rule card: `source_key` `rule:<n>`, `needs` `approval`, `header` `New rule: <the sentence>`, `wants` `Approve this rule?`, and `rule`: `{"text": "Never show shipping notices unless something is late.", "way": "show_less" | "always_show", "from": "the card it came from, as its header"}`. Its presses:

| Press | What happens |
|---|---|
| `approve` | The rule is saved, switched on, and applies from the next pass. The card is done, `status` `Rule saved`. No Claude run. |
| typed words (the Change box) | One Claude run rewrites the proposed sentence from the owner's words; the card comes back with the new sentence. Still nothing in force. |
| `no` | The proposal is dropped; the card is done, `status` `Done`. No Claude run. The page shows No in Done's place on this card, on a standing approval offer and on a project write; there `no` is the third answer below. Done on any of them only marks it done. |

### The owner's rules, as a setting

`settings_defs` gains a group `filter` (label `What reaches you`, `can_save` true) and a new `control`:

- `rules`: a list of sentences the owner can add to, edit, pause and remove. `value` is `[{"id": 3, "text": "...", "way": "show_less", "on": true, "made": "2026-11-16T14:02:11", "from": "Loudshop wants A, B or C..."}]`; `ways` on the definition is `[{"value": "show_less", "label": "Show less"}, {"value": "always_show", "label": "Always show"}]`. A Save sends the whole list as the value of `rules` in group `filter`: each entry `{"id": 3 or null for a new one, "text", "way", "on"}`; an entry left out is removed. Text is 8 to 300 characters; at most 60 rules. The result line is `Saved: your rules. ...`, and when two rules that are on plainly contradict, it adds `These two pull against each other: "<one>" and "<the other>". Both are saved; change or pause one.`

The other settings in group `filter` are ordinary `choice` and `list` controls (ids and values):

| `id` | Values (default first) | How it is obeyed |
|---|---|---|
| `strict` | `balanced`, `show_more`, `needs_me` | The sorting step's instructions. A new home starts on `show_more` (H10). |
| `nothing_needed` | `line`, `hide`, `full` | Machinery and page: `hide` keeps cards that need nothing out of the feed and on the held-back list; `line` and `full` are the page's two ways of drawing them (read `settings.filter.nothing_needed`). |
| `first_time` | `show`, `ask_once`, `hold` | Machinery. `hold`: mail from a sender never seen before is held back. `ask_once`: held back, and one card per new sender asks `Show their mail` or `Hold it` (`choices`). |
| `newsletters` | `never`, `show` | Machinery (the unsubscribe-link rule on or off). A new home starts on `show`, `notices` on `show_each`, `copied_only` on `show`, `strict` on `show_more` (H10). |
| `kept_mailings` | `show_each`, `only_due_or_wrong` | The sorting step's instructions, for mailings kept by a keep word. |
| `notices` | `only_failed`, `show_each` | The sorting step's instructions. |
| `always_through` | list of names, addresses or domains, empty | Machinery: nothing from them is ever held back; a message the sorting step would hold gets a plain card instead. |
| `copied_only` | `only_if_named`, `show`, `fyi` | Machinery for `only_if_named` (mail the owner is not addressed on and that does not name them is held back); instructions for `fyi`. |
| `unknown_texts` | `fyi`, `show`, `hide` | Machinery for `hide`; instructions for `fyi`. |
| `short_texts` | `hide`, `show` | Machinery (rule 560, a text from a short number of 6 digits or fewer, on or off; `show` also tells the sorting step no junk rule about short numbers applies). A new home starts on `show`. |
| `show_why` | `on`, `off` | The page only: whether "Here because:" is drawn (read `settings.filter.show_why`). |

The review's "daily list" choices are left out this round (they belong to the daily summary, round 3).

Three more settings: in group `page`, `later_offers` (control `checks`; values any of `today`, `tomorrow`, `next_week`, `date`, `someday`; default all; the page offers only those under Later); in group `filter`, `waiting_back_days` (`3`, `2`, `5`, `7`, `0` for never) and `old_card_days` (`14`, `7`, `30`, `0` for never). In group `thinking`, `fast_sort` (`off`, `on`): the fastest model sorts what is plainly nothing first.

`settings` (the plain values) carries them all under `filter`, plus `page.later_offers` and `thinking.fast_sort`.

### A waiting card that comes back

A card waiting on someone carries `waiting_on` (who owes the next move, by name, written with the card; never the owner) and its `checkback_date` (the card writer's `next_check`); its front says whom it waits on, that day, and the recommended step. It (`needs` `waiting`) returns to the owner on its check-back date or when that person writes again, whichever is first. It then has state `yours`, `needs` `do`, `wants` like `No reply from Pat in 3 working days. Wait longer, write to them, or drop it?`, a history line saying what it waited for and how long, and:

```json
"came_back": {"why": "date" | "message", "who": "Pat Example", "waited_days": 3, "wait_days": 3}
```

`wait_days` is the setting's value, for the page to fill in first. Presses on it, none of which starts Claude:

| `name` | Extra | What happens |
|---|---|---|
| `wait_longer` | `days`: 1 to 60 (working days) | Waiting again, check-back date that many working days on. |
| `write_them` | | Recorded; nothing is drafted and nothing is sent. The page opens its writing screen for a reply (`reply` on the card says to whom). The card stays with the owner. |
| `drop` | | The card is done, `status` `Dropped`. |

### Old cards, asked about once

One card, `source_key` `live:old-cards`, `needs` `answer`, `header` like `5 cards have sat for two weeks`, `wants` `Keep, someday or drop each one.`, carries:

```json
"old_cards": [{"id": "L1042", "header": "...", "days": 16, "needs": "do"}]
```

Presses are sent on the asking card (its id), naming the card they are about: `{"press": {"name": "old_card", "card": "L1042", "do": "keep" | "someday" | "drop"}}`. Each acts on that one card (keep: its clock starts again; someday: the Someday shelf; drop: done, `status` `Dropped`) and takes it off the list; when the list is empty the asking card closes. A card is asked about once; a kept card is not asked about again until it has sat the full time again. Nothing is ever dropped without the press.

### Reading a held-back message (added 11/16/26)

A held-back row can be opened to read the message itself. The message is never in the `held` list; it is sent only when asked for, one message at a time.

The page asks with a press on the row's `key` (key and id), like "I should have seen this":

```json
{"key": "held-10231", "record": {"id": "held-10231", "action": "answer", "at": "2026-11-16T15:02:11", "device": "Phone, Chrome",
                                 "text": "{\"press\": {\"name\": \"read\", \"part\": 1}}"}}
```

`part` is 1 for the start (it may be left out) and 2, 3, ... for the rest of a long message. The answer mark comes back as for any press (`outcome` `Here it is.`, or the plain reason it could not be read). The message arrives in the feed as one more document, `reading` (the page reads `live.reading`), which holds the one message asked for last:

```json
{"key": "held-10231", "at": "2026-11-16T15:02:11", "ok": true, "part": 1, "parts": 3, "more": true,
 "from": "Loud Shop <deals@loudshop.example>", "to": "sam@example.com", "when": "2026-11-16T09:12:00", "channel": "email",
 "subject": "Your weekly picks are in", "text": "the message's own words...\n\n[There is more. Open the next part.]",
 "papers": ["Price list.pdf"]}
```

`key` and `at` are the row and the press it answers; the page shows it on that row when both match its own press. `text` is the message's own words with quoted earlier mail and signatures trimmed the way cards trim them, at most 12,000 characters a part; when `more` is true the last line of `text` says so and the next `part` gets the rest. `papers` are the names of attached files (not their words). `ok` false comes with `text` holding the plain reason (for example the assistant is in the middle of gathering; ask again in a moment) and nothing else. A row whose `key` starts `card-` gives the newest message behind that card.

Reading changes nothing: the message stays held back, no card is made, and no Claude run is started. It is recorded as one row in `live_presses` (press `read`, choice the part) and nowhere else. Only a signed-in page can ask (the page server refuses a press without a sign-in) and only a signed-in page gets the feed.

## Days on cards (added 11/16/26)

A card never says "this morning" four days later. Card text is stored with a day marker, `{day:2026-11-12}` or `{day:2026-11-12|morning}` (`afternoon`, `evening`, `night`), and the engine words it each time it sends the card: today, tomorrow, yesterday (this morning, tonight, last night, tomorrow evening...), otherwise the weekday and date (`Thu 11/12`, `Thu 11/12 in the morning`). A marker never reaches the page: `header`, `title`, `wants`, `why`, `detail`, `recommended`, `asks`, `status`, `last_press.happened` and the old-cards rows are already worded when the feed is built, at every pass and every press; the first pass after midnight words them again even when gathering is paused. The page draws them as plain text and needs no change.

How a date gets stored (`dates.py`): the Claude writer is told to write the marker itself; and whatever text is stored on a card, by any path, has every relative day word outside quotation marks turned into a marker counted from the day it is written (a date beside the word, as in "this morning (11/12)", wins). Words inside quotation marks, and the message's own text (`source_text`, a held-back card's story), are left as the sender wrote them. Results of Later and Wait longer carry markers too ("Put off to tomorrow." reads "Put off to today." the next day). History lines keep their real date and time stamps.

Once per home (`dates.fix_once`, at the first pass): open cards written before this get their old relative words turned into markers, counted from the day the words were written (the day of the newest message behind the card, or of the owner's last typed answer that rewrote it). No Claude run. What was found and what it became is in `<home>\logs\dates_fixed.log`.

## Design round 3: the top line, true order, grouping, standing approvals, the weekly review (added 11/16/26)

Everything above stays. New presses travel as before (action `answer`, `text` = `{"press": {...}}`, `device` on every one).

### My checks, written before building (each is shown on a stand-in with real presses)

- **H1 The top line.** With open cards that need him, `top.line` says how many and names the first one in true order ("3 things need you. Next: ..."); it says how many are late or due today when any are; with nothing left it says "Nothing needs you." (and how many wait on others).
- **H2 True order.** Every card carries `rank`: the soonest due date first, then important, then the oldest unanswered; the page sorts by `rank`.
- **H3 Grouping and sorting.** `group_by` (nothing, sender, area, conversation; default nothing) puts a `group` on each card only when it is on; `sort_by` (due date, newest first, oldest first, waiting longest, importance, recently active; default due date) changes `rank` as it says; a value outside the list is refused.
- **H4 No standing approval he did not approve.** The ladder is empty and stays empty unless he makes an entry: by pressing an answer on an offer card, or by saving the ladder in Settings. Typed words, the chat box, an unknown press and every other setting save create none. An offer appears only after he approved the same kind of thing in the same area the set number of times (default 5; 3, 5, 10 or never), and a No is remembered.
- **H5 Do it and tell me.** A new card of that kind and area is acted on at the next pass, says "Done for you" with the reason, is in the list and on the top line's count, in the presses table, and Undo brings it back and it is not acted on again.
- **H6 Do it quietly.** Acted on the same way, in the list and the presses table, and not on the top line's count.
- **H7 Pause, remove, area.** A paused entry stops at the next pass; a removed one is gone; an entry for one area does nothing in another; always ask never acts.
- **H8 Nothing is sent.** No kind of standing approval sends anything; a save naming a sending kind is refused; `send.py` is byte for byte unchanged.
- **H9 The weekly review.** On the chosen day after the chosen time one review card is made for the week, in three parts (get clear, get current, get creative) built from his cards, the Someday shelf, waiting-for and next week's calendar, with no Claude run; a second pass the same week makes none; "off" makes none; its rows' presses work.
- **H10 Nothing hidden at the start; a home made before is unchanged.** A new home (made by setup_steps.make_home with no personal.json and no database yet) starts with nothing hidden by a setting: `strict` `show_more`, `newsletters` `show`, `notices` `show_each`, `copied_only` `show`, `short_texts` `show` (filters.NEW_HOME, written once into its settings.json), so a newsletter is read and shown like any other mail. The setup interview asks no junk senders and no kinds of message never to show, and writes no hiding rule (setup\setup_home.py). A home made before keeps its settings exactly: a setting it never saved is still the first value in the table under "What reaches you" (strictness balanced, mailings and short-number texts hidden, as before), and bringing it forward with make_home writes nothing to its settings. With every round 3 setting at its default and no rule or standing approval saved, such a home has the same cards on the page as before round 3.
- **H11 A full timed pass** on the stand-in ends ok; round 2's press checks still pass.
- **H12 His home** (a copy): one pass ok, no card changes state, and the report lists what the top line would say and which offers his presses would already earn.

### The top of the page

The top block carries `top`:

```json
{"line": "3 things need you. 1 is late or due today. Next: Sam needs a date by Friday.", "need_you": 3, "late_or_due": 1, "clear": false,
 "next": {"id": "L1042", "header": "Sam needs a date by Friday"}, "waiting_on_others": 2, "done_for_you": 1}
```

`line` is plain words, worded for today, and is what the page prints at the top. `need_you` counts open cards that are not shelved and whose `needs` is `answer`, `approval` or `do`; `late_or_due` those among them with a due date today or earlier; `next` the first of them in `rank` order; `clear` is true when `need_you` is 0, and then `line` is `Nothing needs you.` (with ` 2 wait on others.` when some do). `done_for_you` counts what standing approvals did today at the level "do it and tell me" (see below). The counts and "since you last looked" tags are the page's own; the page may drop its count and chip rows for this line.

### Order, grouping, sorting

Every card carries `rank`, an integer from 1: its place in true order for the present `sort_by`. Whatever the value, what asks something of him (`needs` `answer`, `approval`, `do`) comes first, then what only waits on others, then what needs nothing, then finished and put-off cards; inside that the value decides. Default `due_first` (Due date): cards with a due date first, the soonest (so the late ones) first, then important, then how often he is in touch with the sender, then oldest unanswered (oldest message first). A card he has already answered or marked done but that is still open (`status` `Answered`, `Thinking`, `Done`, `Approved`) counts as waiting, not as asking him; an older Snooze or Not now whose day has not come counts as put off. So `top.next` is always the first card in `rank` order that asks him, and the page should draw its list of what needs him in `rank` order, with no regrouping that puts another card first. The other values: `newest_first` and `oldest_first` (by `from_at`), `waiting_longest` (the earliest `state_changed_at` first: longest where it is now), `important_senders_first` (Importance: the highest `importance` first, then the newest by `from_at`), `recently_active` (the latest `last_at` first). The page's bar at the top of Cards sets `sort_by` and `group_kinds` (true, the default: the kinds stay together in Card order and the sort applies within each; false: one list mixed only by the sort, which the page orders itself by the same keys without the asks-first rule). When `group_by` is not `nothing`, every card also carries `group`: `{"key": "sender:sam@example.com", "label": "Sam Lee"}` for `sender`, `{"key": "area:Work", "label": "Work"}` for `area`, `{"key": "conversation:<thread>", "label": "the subject of the newest message"}` for `conversation`; a card with none carries `{"key": "none", "label": "Other"}`. Groups are drawn in the order of their best-ranked card. With `group_by` `nothing` no card carries `group`.

Settings (group `page`): `group_by` (`nothing`, `sender`, `area`, `conversation`), an ordinary `choice` control; `sort_by` (`due_first`, `newest_first`, `oldest_first`, `waiting_longest`, `important_senders_first`, `recently_active`) and `group_kinds` (true or false), saved from the bar at the top of Cards, not drawn in Settings. All three are in `settings.page` too.

### Standing approvals

A standing approval lets the assistant do one kind of thing, for one area, without asking each time. Everything starts at **always ask**; nothing is acted on for him unless he has made an entry. Levels: `ask` (never acted on; the default for everything), `tell` (done at the next pass and shown), `quiet` (done at the next pass and kept in the record, not counted on the top line). Only things that can be undone have a ladder. This round's kinds (each in the feed's `standing.kinds`): `close_info` (a card that needs nothing is closed as by Got it) and `drop_waiting` (a waiting card that came back with no reply is dropped). Sending an email is asked each time, by his own Send press, unless he made the one sending approval described under "Standing approval to send replies" below.

The feed carries one more document, `standing`:

```json
{"written_at": "...", "today": 2,
 "kinds": [{"kind": "close_info", "label": "Close cards that need nothing", "what": "A card that only informs is closed for you at the next gathering."}],
 "ladder": [{"id": 1, "kind": "close_info", "label": "Close cards that need nothing", "area": "Work", "level": "tell", "on": true, "used": 3, "made": "2026-11-16T16:10:00", "from": "You said yes on a card"}],
 "log": [{"id": 7, "at": "2026-11-16T16:25:00", "kind": "close_info", "label": "Close cards that need nothing", "area": "Work", "card": "L1042", "header": "Dana: closed Friday for the holiday", "level": "tell", "undone": false}]}
```

`log` is every use, newest first, the last 100, at every level; `Undo` on the card (`{"press": {"name": "undo"}}` on the card's key) brings it back, the row says `undone` true and it is never acted on again. A card done this way has `status` `Done for you` and `last_press` `press` `standing_close` or `standing_drop`, `happened` saying which entry did it.

**Offers.** After he has approved the same kind of thing in the same area `offer_after` times (the number of his own presses of that kind on cards of that area, none of them done for him), one card is made for it: `source_key` `live:standing-<kind>-<area>`, `needs` `answer`, `header` like `You close the cards that need nothing in Work. Do it for you from now on?`, with `choices` `["Yes, do it and tell me", "Yes, do it quietly", "No"]`. His answer (the choice's text, as the page already sends a choice) is the only way an offer becomes an entry: the first two make the entry at that level; the third (or the press `no`) is remembered and the same offer comes back only after he has approved that many more times. An offer is made at most once while it waits.

**The ladder as a setting.** Group `acting` ("What it does for you", `can_save` true) with a control `ladder`: `value` is the list above (`id`, `kind`, `label`, `area`, `level`, `on`, `used` (how many times it has acted), `made`, `from`), `kinds` the kinds he may add, `areas` the areas he has, `levels` `[{"value": "ask", "label": "Always ask"}, {"value": "tell", "label": "Do it and tell me"}, {"value": "quiet", "label": "Do it quietly"}]`. A Save sends the whole list as `ladder` (an entry `{"id" or null, "kind", "area", "level", "on"}`; one left out is removed). The save is his approval. Anything naming another kind, area or level is refused. The other settings in the group are `offer_after` (`5`, `3`, `10`, `0` for never offer; default 5) and `send_cap` (`1`, `3`, `5`, `10` sends a day under standing approvals to send; default 3). The result line names what changed.

**Standing approval to send replies (11/16/26, his yes).** One more kind, `send_reply`, with its own offer, entry and checks. It is never in `kinds` for Settings to add. The page draws it like the others, with these differences:

- **Offer.** After he has sent, by his own Send press, `offer_after` short replies (one recipient, no copy, no attachment, 800 characters or fewer) to the same person from the same account on cards of the same area, one card is made: `source_key` `live:standing-send_reply-<area>-<address>` (a later offer adds `-<n>`), `needs` `answer`, `choices` `["Yes, do it and tell me", "Yes, do it quietly", "No"]`, `offer` `{"kind": "send_reply", "area", "scope": "<address>", "account", "count"}`. Its `detail` names the kind in plain words, the person and the account, lists up to three real examples (date and subject of replies he sent by hand), the limits, the daily cap, that every send is listed on the page, that a sent email cannot be taken back, and how to pause or remove it. A No is remembered; removing the entry is remembered too; the offer returns only after that many more hand sends. His Yes on the card is the only way an entry is made: Settings and the chat box refuse to make one.
- **Ladder row.** `kind` `send_reply`, `label` `Send replies to one person: <address>`, plus `scope` (the one address) . Settings may only pause it, change its level or remove it (leave it out of the Save); naming a new one, or another `scope`, is refused. At `ask` nothing is sent.
- **What is sent.** At the next gathering, for each open, unshelved `question` or `yours` card of that area with a draft, and only when ALL hold: sending is on and the account may send; the entry is on at `tell` or `quiet` (read again right before each send); today's standing sends are under `send_cap`; the draft goes to exactly the entry's one address, and that address is the sender of the message the card is about as the mail service gave it (the card's `reply.to`), never an address taken from anyone's words; no copy, blind copy or attachment; from the entry's account; subject and body present; 800 characters or fewer; no link. Anything else is left alone and comes to him as usual (the draft stays on its card).
- **After a send.** The card gets `status` `Sent for you`, its `detail` holds the message, the draft is cleared, and `last_press` `press` `standing_send`. `tell`: the card goes to `in_motion` (a card he can open). `quiet`: the card is `done` and the send is in the record. A sent email cannot be taken back, so there is no Undo for it.
- **The record.** Each send is a row in the `standing` document's `log` with the same fields as other rows plus `sent`: `{"to": [...], "account", "subject", "body", "approval": <ladder id>, "result"}`; `level` says which kind of notice it was. It is also in the presses table (device `standing approval`) and the owner's sent log (`standing`: the entry id).

### The weekly review

Setting (group `review`, "Weekly review"): `review_day` (`fri`, `off`, `mon`, `tue`, `wed`, `thu`, `sat`, `sun`; default `fri`) and `review_time` (`HH:MM`, default `15:00`). At the first pass on that day at or after that time, if this week has none, one card is made: `source_key` `live:review-<year>-W<week>`, `header` `Your weekly review, week of 11/16`, `needs` `do`, `wants` `Go through it, then press Done.`, and `review`:

```json
{"week": "2026-W47", "line": "12 cards wait on you, 2 are waiting past their date, 3 are on the Someday shelf.",
 "parts": [{"key": "waiting_on_you", "group": "clear", "title": "Waiting on you", "lines": ["12 cards wait on you. The oldest are below."],
            "rows": [{"id": "L1042", "header": "...", "note": "waiting 9 days", "presses": ["done", "later"]}]},
           {"key": "waiting_past_due", "group": "clear", "title": "Waiting on others, past their date", "lines": [], "rows": []},
           {"key": "old", "group": "clear", "title": "Cards that have sat", "lines": [], "rows": []},
           {"key": "next_week", "group": "current", "title": "Next week", "lines": ["Mon 11/23 9:00 AM Dentist"], "rows": []},
           {"key": "held", "group": "current", "title": "What was held back this week", "lines": ["37 messages, 26 by the sorting step."], "rows": []},
           {"key": "learned", "group": "current", "title": "What it learned", "lines": ["2 new rules, 1 standing approval."], "rows": []},
           {"key": "someday", "group": "creative", "title": "The Someday shelf", "lines": ["Pick one thing to start this week."],
            "rows": [{"id": "L1013", "header": "...", "note": "on the shelf 6 days", "presses": ["bring_back", "done"]}]}],
 "cost": "No Claude run: it is made from your cards and calendar."}
```

`group` is the three parts of the review (`clear`, `current`, `creative`); a part with no lines and no rows is left out.

`rows[].presses` are existing presses the page sends on that row's card key (`done`, `later` with a `when`, `bring_back`, `wait_longer`, `drop`, `keep` meaning `{"press": {"name": "old_keep"}}`). Get clear: what waits on him (the five oldest), waiting-for past its check-back date, cards that have sat. Get current: the next seven days of the calendars he shows, what was held back this week (counts), what he taught it this week (new rules and standing approvals). Get creative: the Someday shelf (each row with Bring it back) and a plain prompt to pick one. The card is closed with Done; it is the only press it needs. It costs no Claude run.

## Reading back, the history of what was done (added 11/16/26)

His words: reading back "should start to create the history of things that have been done ... It sees tasks coming in, it sees answers, it sees things getting completed, and records them as such." `readback.py` does it, from a start date he gives, for every connected source of mail, texts and other messages.

**Commands** (run hidden, from `System\live`):
- `python readback.py plan --since 2026-09-01` reads the sources from that date (no Claude), settles junk, his ignore list and mail he sent without Claude, and prints what it would cost: `{"since", "messages", "conversations_found", "conversations_to_read", "settled_without_claude", "claude_runs", "model", "per_run", "minutes", "words"}`. `words` is the plain sentence to show him before he says go: how many messages and conversations, how many are settled without Claude, how many Claude runs on the fastest model (20 conversations a run), about how many minutes, that it counts toward his daily limit, and that nothing else uses Claude.
- `python readback.py run --since 2026-09-01 --go [--max-runs N]` does it. Without `--go` it only plans. `--max-runs` stops after that many Claude runs (run again to go on). It takes the pass lock, so a pass and a reading back never run together; a pass that starts meanwhile logs that it is skipped.

**What it records** in the home's database:
- `live_history`: one row per event, `kind` `came_in` (a task came in, at the time of its first message), `answered` (he replied, at the time of his first reply, worked out from the messages, not by Claude), `completed` (the matter was finished, at the time the thread shows). Columns: `happened_at`, `kind`, `ref` (`<conversation>|<kind>`, unique, so an event is written once), `thread`, `title`, `who`, `channel`, `message_ids`, `note`, `unsure`, `source` (`readback`), `run_id`, `recorded_at`.
- `live_readback_threads`: every conversation read, so it is never read again, with `was_task`, `state` and `unsure`.
- `live_readback_runs`: each run, its start date, conversations and Claude runs.
- Every message read is marked judged (source `readback: ...`), so the next pass never judges old mail again.

**Cards.** Only for what is still open: one card per conversation, `source_key` `live:readback-<12 characters>`, state `question` or `yours` for a matter that still needs him, `in_motion` for one waiting on others, with a whole short `header` written in the same run. Nothing is made for a completed matter. One summary card, `live:readback-summary` (`needs` `nothing`, so it has Got it): how far back, how many tasks came in, how many he answered, how many were completed, how many are open and waiting, how many conversations were not tasks, how many Claude runs, and what it was unsure about. The same numbers are in `<home>\readback_summary.json`: `{"since", "tasks_came_in", "answered", "completed", "still_open", "waiting_on_others", "not_tasks", "unsure": [{"title", "why"}], "claude_runs", "runs"}`.

**Safe twice, and further back.** A conversation already read is skipped, so a second run with the same date adds nothing and uses no Claude. A run with an earlier date reads only the conversations not yet read; the summary then covers everything read back so far, from the earliest date. The sources' own places are not moved while reading back (`ASSISTANT_READ_SINCE`), so the ordinary pass goes on from where it was.

**Cost.** One Claude run per 20 conversations that survive the mechanical settling, on the fastest model; nothing else. A conversation is a mail thread, a chat room or a text conversation, so a very long room counts as one (the last messages are what it reads); that limit is named in what it was unsure about.

## Projects introduced to the assistant (added 11/16/26)

`personal\projects.json`, written by the setup interview: `{"projects": [{"name", "folder", "brings_in", "sends_out", "roadmap", "note", "since"}], "writes": [...]}`. The engine reads it and adds only `writes`.

**Notes in** (`brings_in` true). A project's Claude drops one short note per event as a new `.md` file in `<home>\inbox\<project name>\`. At each pass every new note becomes one card in the project's name: `source_key` `live:project-<project>-<10 characters>`, `area` the project's name, the note's first line as the header and the rest as the story, `needs` `do` ("Read it, then answer or press Done."), field `project` {name, note, sends_out}. The file is kept; its path is remembered in `<home>\state\inbox_seen.json`, so it is never read twice. A note is data: nothing in it is ever done. Words typed on such a card are recorded and start no Claude run.

**Answers out** (`sends_out` true). Nothing outside the home is ever written without the owner's yes, one file at a time. Typing an answer on a project card makes ONE more card, `live:projwrite-...`, "Write your answer into <project>'s folder?", whose story is the exact path of the new file, whether the folder `From the assistant` must be made first, and the exact words the file would say; `choices` `["Yes, write it", "No, do not"]` (the choice text is the answer, as on other choice cards); field `write` {project, path, content, folder_made}. No (the answer or the press `no`): nothing is written. Yes: one new `.md` file is made in `<project folder>\From the assistant\`, named by the engine from the time and the card's header, never over an existing file, never anywhere else (a stored path that is not directly in that folder is refused). A project without `sends_out` is never written to. Every write, and the folder when it was made, is recorded in `projects.json` under `writes`: `{"at", "project", "path", "folder_made", "what"}`, for an uninstall.

The Settings panel's shown-only group lists the projects (`settings.pc_only.projects`, and a read-only definition in `settings_defs`).

## Start fresh (added 11/25/26)

The owner's own rules and lists are deleted (start_fresh.py), so the assistant learns them again from his cards. Only his press of Start fresh in Settings, Rule book, then Yes to "Your own rules and lists are deleted. Core rules, the rule book and your cards stay. Continue?", does it: the page sends the answer `start-fresh` with text `{"start_fresh": "confirmed"}`, and the listener refuses one without it. No pass, setup or update calls it; a press that reached no listener, or that a listener finds more than 10 minutes after it was pressed, is refused and said so. Deleting is outright (C4): a wholly personal file is deleted; a shared file is rewritten without his entries; no To Delete folder is made. A home with nothing of his left changes nothing.

| Store | Core or personal | What start fresh does |
|---|---|---|
| `personal\filter_rules.json` (show less, always show, how cards are written) | personal | left holding no rules and its next rule number, so an old number is never reused |
| `personal\voice.json` (writing style, learned and his corrections) | personal | deleted |
| `personal\personal.json` `ignore_senders`, `keep_words` | personal entries in a shared file | those two lists taken out |
| `personal\settings.json` `filter.always_through` (priority senders) | personal entry in a shared file | that list taken out |
| `Resources\Rules\*.md` entries and `Resources\Data\Junk senders.md` lines (core\rules.py) | personal: every entry in the home's documents, with its "You said" line, is his (in a home made before, that includes its old copies of the core entries, which are no longer read) | his entries taken out; headings, intros and README's next rule number stay |
| `Resources\Rules\Draft\*.md` (shortened copies of his rules documents) | personal | deleted |
| Core rules: `Goals.md` and Junk rules 559-562 and 631, in the program's own `core_rules` folder | core, part of the program | never in a home, so untouched; an update changes them |
| `Changelog.md`, `Reference.md`, and a `Goals.md` left in a home made before (no longer read) | not rules | untouched |
| `personal\rule_book.jsonl`, `rule_book_waiting.json`, `rsi_versions\`, `state\rsi\` | rule book and RSI | untouched (a promote of an older draft is refused because his rules changed) |
| `personal\standing.json`, `standing_sends.json` (approvals to act for him) | personal, not rules | untouched |
| `personal\setup.json` (his interview answers: priority people, and in a home set up before, junk senders and show-less lines) | personal record | untouched; nothing re-applies it, and the interview no longer asks or writes junk senders or show-less lines |
| `personal\Important.md` (what deserves a notification) | personal, not a show or hide rule | untouched |
| `taught\rules\`, `mods\` (guardrails he added, his mods) | personal guardrails and changes | untouched |
| `personal.json` name, `own_domains`, `private_words`, `company_words`, `plan_words`; every setting choice | personal facts and settings | untouched (new defaults are not written by this step) |
| Cards, the database, mail rules on the mail service | data | untouched |

## The pick, and what the owner did (judgment rebuild phase 1, added 11/25/26)

Every open card carries a pick (picks.py): what I predict he will do with it, drawn on the page as its first button ("My pick"), and one press does it (learning level 1: nothing happens before his press). The card writer writes it (prompts\items.md, `pick`: a choice word for word, one of a few standard buttons, a reply with its gist, or leave it as it is); a card it did not write, or wrote with no usable pick, gets the program's (the recommended choice, Go ahead, Done, Keep waiting, or leave it). Cards with their own fixed buttons (rule, rule change, standing approval, project write, first-time sender, "I'd hide this", old cards, the review, a mod's) have none: their first button is the pick. A pressed pick arrives marked ("pick": "1"); "Leave it as it is" is its own press, leave, which changes nothing on the card.

Every press, and typed words on a card, writes rule book rows with the pick, what he did and whether they matched (pick, did, pick_outcome); typed words are neutral, so the show-or-hide learning is untouched, and a card with no messages behind it gets one row keyed card:<id>. When he did something else, it is kept by sender (else by area and kind) in personal\pick_habits.json; the next card like it shows it beside the pick ("Last time: ..."), and the one brain below makes it one of that card's own choices.

Each pass also records what he did outside the page (offpage.py): every message he sent on any channel the gathering reads (mail, texts, any other channel connected), matched to its card by conversation, else by person, with the card's pick beside it, and marked sent from the page when send.py's own log has it; and every invitation he answered or event he moved in his calendar (the calendar keeps his answer, my_response). The pass log line gives the pick's cost: picks the writer wrote, their output tokens (an estimate) against the writer's whole output, and 0 extra AI runs.

Drop (approved 11/25/26, "1a"): "Done says there was a task on the card that I completed, and drop says for one reason or another I don't want this card considered." Drop closes the card (status Dropped) and it isn't thought about again unless the matter comes back (a new message on it reopens it, as for any closed card). It is not a hide (that is Not needed): its rule book row has action drop and is neutral for show or hide. Done, Got it and Drop are three answers; none matches another against the pick. Every open card shows My pick, Done, Drop, Snooze and Other (a card that asks yes or no keeps its No in Done's place and has no Drop); Got it only on a card that asks nothing. Drop no longer stands for Done on a card back from waiting.

## One brain (judgment rebuild phase 2, added 11/25/26)

The judging run writes the cards (think.py, prompts\judge.md, its cards part built from prompts\items.md so the card's fields and writing rules are said once): in the same Claude run that decides what each message means, it writes the card of every matter its verdicts leave open (each item_key a task verdict names or a task_update leaves at needs_me or waiting_them), so the verdict, the recommendation, the questions, the choices and the pick come from one reading. It is shown, beside the judge's payload, each open matter's card (open questions, history, his latest answer), the notification list, and on each message from outside what he did last time on a card from that sender. The verdicts are committed and checked exactly as before (every message a verdict, urgent with a reason); the cards are then checked by the card guardrails, a refused one goes back to the same run, and the good ones go on their items in the write step with no Claude run. The card writer still writes what the judging run did not: a card owed a full writing, one left from an earlier check, a card whose judged card was refused, and new mail that rests on no item. The cheap first sort is unchanged.

The choices grow: when he did something other than the pick on the last card like this one (by sender, else area and kind), a choice or a few words of his, it is added as one of the new card's own choices (picks.grow), after my recommendation, whoever wrote the card. A press he made instead (Drop, Snooze...) is a standard button already, and a reply stays the Last time button.

The pass log line says what judging and writing cost: cards written with the verdicts and by the card writer, the Claude runs, output tokens and dollars of both steps this pass, against the average of the last 20 passes on record from before one brain (the AI log, which now keeps each run's cost).

Talk to your assistant searches every card, open and closed (card_search.py): its cards ACTION (prompts\chat.md) names words, a kind, a button or a state, and the program runs the chat again at once with the count (open and closed) and the cards with their buttons. The found data's few best-matching open cards are no longer what it counts from.

## Scores and levels per kind of work (judgment rebuild phases 4 and 5, added 11/25/26)

- Kinds of work are the rule book's six sections. Each row with a pick is scored by program code (work_rules.py): decisions (did he do my pick), wording (both carry words: the same, or most words shared), timing (either puts it off), urgency (a card marked important that he put off, dropped or didn't need is a miss). Settings, Learning levels, shows "My picks: N% matched what you did" with each way counted, then the show or hide score.
- A missed pick queues the coach for that kind of work (rsi_loop, kind "work"). It proposes one pick rule (cards from a sender, with words in the title, in an area or of a kind: my pick is X, and/or not urgent), scored on the past rows with no AI run, shown as a Pick change card with fixes, breaks and both scores, Approve and Reject. The coach runs at every level; the change waits for Approve at levels 1 and 2.
- Levels (levels.py; guardrails A15, A19, B1, B6, B12): 1 I suggest and he presses (where everything starts); 2 I do my pick myself where it has matched him at least 80% over 5 or more answers, only Got it, Drop, Snooze to tomorrow or Keep waiting, with a note and Undo on the card; 3 the same quietly, listed in one summary card each morning, and coach changes that match more and break none made on their own (Change history, Undo). In Reply drafts, level 2 or 3 is his standing approval to send the reply I drafted to the one person who wrote, under every check of B12 and the daily send cap; nothing is sent at level 1 and no other kind of work sends. The level control shows the picked level's words before Save, and Save says them back.
- Undo of a level action puts the card back, it is never done for him again, and it counts as a miss of my pick.
