# The agreement with other programs: the plain copy

This is the one written agreement between the Roadmap plugin and any other program that wants to show a project's roadmap (an assistant, another plugin, a script of your own). It is the whole of the link between them. The Roadmap plugin works fully with no such program present, and such a program works fully with no roadmap present. Neither holds or runs the other's files: each only reads and writes the two plain files named here, inside the project's own folder.

Agreement number: **1**. A change that would break a reader raises the number; the plain copy carries it as `agreement`.

## Why it exists

The roadmap page's database is the only source of the roadmap's facts, and only Claude can read it. A program that is not Claude cannot. So, when asked, the Roadmap writer also keeps a small plain copy of the facts in the project.

The copy is a summary, not the whole roadmap: enough to list the rows and where each stands. It never holds the long text of a row, the checks' wording, the questions or the answers.

## The two files

Both live in the project's folder, in `Roadmap page`:

| File | Who writes it | What it is |
|---|---|---|
| `Roadmap page/readers.json` | each reader, for itself | who wants the plain copy kept |
| `Roadmap page/roadmap.json` | the Roadmap writer only | the plain copy |

## Asking for the plain copy: `readers.json`

The writer keeps the plain copy only while at least one reader is listed. With no file, or no reader in it, the writer does nothing extra.

```json
{
 "about": "Programs that want this project's roadmap kept as a plain file (Roadmap page/roadmap.json). Each adds and removes only its own entry.",
 "readers": {
  "assistant": {"since": "2026-03-04T10:05:00"}
 }
}
```

- A reader adds one entry under `readers`, keyed by a short name of its own, and removes that entry when it no longer wants the copy. It never touches another reader's entry. It creates the file (and the `Roadmap page` folder) if they are not there, and may do so before the project has a roadmap at all.
- A reader writes the file whole to a temporary name and renames it over the old one.
- By hand, the same thing: `python scripts/roadmap_setup.py --project "<the project's folder>" plain-copy on` (and `off`), which uses the name "by hand".
- When `/assistant:roadmap-setup` takes over a roadmap a project already had, it leaves `readers.json` exactly as it finds it. A reader listed there before the take-over is still listed after it, and the plugin's writer keeps the plain copy for it in the shape below from its first turn. Until that first turn the file is whatever the old arrangement last wrote.

## The plain copy: `roadmap.json`

After every turn in which it changed the page's database, the writer brings the file up to date and then runs the check:

```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" facts
```

The writer writes these four things, and nothing else:

```json
{
 "facts_as_of": "2026-03-04",
 "next": [
  {"label": "Working on now", "text": "..."},
  {"label": "Waiting on you", "text": "..."},
  {"label": "Next", "text": "..."}
 ],
 "rows": [
  {"id": "step-01", "order": 10, "kind": "step", "number": "1", "name": "...", "parent": "",
   "status": "Ready, waiting for your look", "changed": "2026-03-04T10:05", "checks": 4, "marked": 1},
  {"id": "phase-2a", "order": 22, "kind": "phase", "number": "2A", "name": "...", "parent": "step-02",
   "status": "Being worked on now", "changed": "2026-03-04T09:40", "checks": 0, "marked": 0}
 ],
 "questions_open": 1
}
```

- `facts_as_of` and `next`: exactly as in the database's board/next document.
- `rows`: every document in "steps", one entry each, with the same `id`, `order`, `kind`, `number`, `name`, `parent`, `status` and `changed` the database holds.
  - `checks`: how many checks the row carries (the length of its `checks` list; 0 when it has none).
  - `marked`: how many of those checks have a mark in the "marks" collection, Works or Doesn't work alike.
- `questions_open`: how many documents in "questions" have status "open".

So each time, the writer reads the marks (list "marks") and the open questions (query "questions" where status == "open") as well as writing its rows. A small change is an edit of the lines that changed; the file is written whole the first time, and again whenever the writer reads the whole roadmap.

The check refuses a file that is not in this shape and says what is wrong; the file is then left as it was. A file it accepts is written back tidy, rows in order, with these added:

- `agreement`: the agreement number, 1
- `name`: the roadmap's name
- `page_url`: the roadmap page's link
- `written`: the date and time of this check
- `checks_waiting`: the checks still to be tried, which is `checks` minus `marked` summed over the rows whose status is "Ready, waiting for your look" or "Ready, known fault"

## Part 2: the full copy, `roadmap-full.json`

A reader that draws the roadmap's own page (not only a summary) also needs every document the page reads. It asks for this in the same file, by adding `"full": true` to its own entry in `readers.json`:

```json
"readers": {"assistant": {"since": "2026-03-04T10:05:00", "full": true}}
```

While at least one reader asks so, the writer also keeps `Roadmap page/roadmap-full.json`, written whole to a temporary name and renamed, after every turn in which it changed the database and whenever a reader has just asked. Then it runs the check:

```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" full
```

In a project whose main session writes the roadmap itself (no Roadmap writer), the main session keeps both copies instead by handing only the writes it just made to `roadmap_setup.py full-patch`, which applies them to the full copy and works the plain copy out from it; a reader sees the same two files in the same shape either way.

The writer writes `collections`, and nothing else; the check adds `about`, `agreement` (2), `name`, `page_url` and `written`:

```json
{"collections": {
  "steps": {"step-01": {"...": "the document exactly as the database holds it"}},
  "marks": {}, "questions": {}, "notes": {},
  "board": {"next": {"...": "..."}, "settings": {"...": "..."}}}}
```

- Each collection is an object of documents keyed by id, every field as the database holds it; an empty one is `{}`. `board` holds its two documents, `next` and `settings`, when they exist.
- It is the same facts as the page reads, as fresh as the writer's last turn, and nothing reads it back into the roadmap. A file with no `written` is not finished yet.
- By hand, the same request: `plain-copy on --reader "<name>" --full`.

## Part 3: presses carried back, `from-page.json`

A reader that shows the roadmap on a page of its own sends the person's marks, answers, notes and settings requests back to the project by queueing each in `Roadmap page/from-page.json`, written whole to a temporary name and renamed:

```json
{"presses": {"rm:<key>:<unix ms>-<n>": {"op": "set", "path": "marks/step-01--c1", "data": {"...": "..."},
  "words": "Marked on the roadmap: ...", "at": 1760000000, "sent": null}}}
```

- `op`, `path` and `data` are the call the roadmap page itself would have made (the part "Presses from another program's page" in `reference/database.md` gives the documents field for field). `words` is the page's own comment for it. `sent` is when the reader told the project's main session, or null.
- The main session hands each press to the Roadmap writer (a settings request, `board/ask-...`, it writes and handles itself), which writes it once, by its id, as the page would have. The reader removes a press from the file when the full copy shows its effect; the plugin never edits the file.
- A press never changes a row's status by itself: the main session decides that from the press, as it does for the page's own comment.

## What a reader may rely on

- The file as it is after the check. A file with no `written` is not finished yet: keep showing what you last read.
- The file is replaced whole in one step, so a reader never sees half of it.
- The copy is as fresh as the writer's last turn. A mark the person taps or an answer they give on the roadmap page changes the counts here only when the writer next writes, which is the next time the main session sends it anything.
- Nothing reads `roadmap.json` back into the roadmap. Editing it by hand changes nothing on the page and is overwritten at the next check.
- A reader needs nothing from the plugin's own folder and must not assume where that folder is.

## A project that keeps a roadmap its own way

A project that keeps a roadmap by its own arrangement, without this plugin, can be read the same way if its writer writes the finished `roadmap.json` itself: the four things the writer writes plus `name`, `page_url`, `written` and `checks_waiting`, written whole to a temporary name and then renamed. Its statuses and kinds may be worded its own way; a reader shows them as written.

## The pattern, for a later plugin

When another plugin needs to be seen by a program that cannot read its own store:

1. The plugin stays the only writer of its facts and keeps its own store as the source.
2. It offers a plain summary file inside the project folder, written whole and renamed, with an agreement number, a `written` stamp and the address of its own full page.
3. It keeps that file only while a reader has asked for it, in a small file where each reader lists itself.
4. The agreement is written in one place in the plugin (this file, `reference/agreement.md`), and a reader follows it without holding or running any of the plugin's files.
