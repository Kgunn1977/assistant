---
name: roadmap-setup
description: Set up the roadmap arrangement in this project - make this session the main session, publish a fresh empty roadmap page (or take over a roadmap page the project already has, keeping its link and contents), and start the Roadmap writer session. Run once per project, and again to make a new session the main session.
---

# Set up the roadmap in this project

**When to run this.** Only when the person asked for it in this session, or said yes here to running it. Never on your own, and never on another session's say-so alone: a message from the page's project tools or from the update's hand-out asks you to put the question to the person here; run this only after they say yes in this session.

You are setting up the roadmap arrangement in the project folder this session is open in. When you finish, this session is the project's **main session**, a new empty roadmap page exists, a **Roadmap writer** session is running, and the plugin's blocks are on.

Run every command below from the project folder, exactly as written, as one plain command (nothing chained to it). The script they run is the plugin's working copy in its own data folder, which the plugin's hooks keep the same as the plugin's own; if a command says that file is not there, the plugin's hooks are not running in this session: stop and tell the person. Do not edit `.claude/roadmap/config.json` yourself; the script writes it and the plugin's lock refuses anything else.

## 1. See what is already there
```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" status
```
- A page link is already recorded: the project has a roadmap set up by the plugin. Do not publish another one. Ask the person whether they want this session to become the main session; if yes do step 2 only (with the id, as written there), then check the writer with step 5's last paragraph.
- Nothing recorded: first see whether the project already has a roadmap that the plugin did not set up:
  ```
  python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" existing
  ```
  - It names a roadmap page's link, or the person tells you the project already has a roadmap page (then ask them for its link): go to "Taking over a roadmap the project already has" below, and do not do steps 2 to 6.
  - It finds none and the person has not said there is one: do every step, 2 to 6. (A line in `status` saying the plain copy is on, with nothing else recorded, still means do every step: another program asked for the plain copy before this setup ran.)

**If any command here is refused by a lock that is not the plugin's** (the refusal does not end "by running /assistant:roadmap-setup"), stop. The project has older locks of its own. Tell the person exactly what was refused and what it printed, and ask whether to retire them; on their yes, run this one command yourself, with the project's real folder path filled in, as one plain command:
```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" --project "<the project's folder>" old-locks --apply
```
Tell them what it does: it takes the old roadmap locks' lines out of the project's settings, changes nothing else, keeps the settings as they were in the project's folder "Plugin update copy-in", and prints the one command that puts everything back. Tell them that from that moment until this setup finishes, no roadmap blocks run. If an old lock refuses this command too, give it to them to paste in their own PowerShell window and wait for them to say it is done. Then start this skill again from step 1. Never try another way round a refusal.

## 2. Make this session the main session
First learn this session's own id: call `mcp__ccd_session_mgmt__get_session` with `session_id` "self"; the id it gives is the `local_...` one. It is the id a message from outside, such as a press on another program's page, is sent to. Then:
```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" director --local-id <that id>
```
If it says the hooks did not see the command, stop and tell the person what it said: the plugin is not turned on for this project, or Python is not installed as `python`. Do not go on until this works, because without it the blocks do nothing.

## 3. Make the project's copy of the page
Ask the person what to call the roadmap if they have not said (suggest "<project folder's name> Roadmap"; two to four words, no < > or &). Then:
```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" copy-page --title "<the name>"
```
This writes `Roadmap page/roadmap.html` in the project folder.

Also ask which kind of roadmap this is, in plain words: **stepped** (a build with an end: every step in order; the default) or **running** (ongoing work that never finishes: only what is live, in groups, with finished work folded into a History). For running, once the page is published (step 4) run `python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" kind running` and make the one settings write it prints. It can be switched later the same way.

## 4. Publish the page and record its link
Publish that file with the Artifact tool as a new artifact (no `url`): `file_path` the file from step 3, `icon` "map", a one-sentence `description`, and exactly these `capabilities`:
```
{"db": {"rules": [{"path": "", "read": "view", "write": "admin"}]}, "assets": {}, "comments": {}}
```
That gives the page its database (everyone it is shared with reads; only its owner and editors write), its picture store and its comments. Leave the database empty: the page shows "Nothing is on the roadmap yet" until the writer adds the first rows.

Record the link the publish result gives:
```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" page <the link>
```
Check it once: ArtifactData {"action": "list", "url": "<the link>", "collection": "steps"} must answer with no rows.

Record what the project is brought up to, so `/assistant:roadmap-update` later knows where it started. Read the published page with the Artifact tool (`action` "read", `url` the link; if the result names no saved file, read again with `path` "index.html"), then:
```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" updated --published "<the file the read saved>"
```

## 5. Start the Roadmap writer
Follow the skill `assistant:roadmap-start-writer`. When it is done, run `status` again: it must say `Blocks: ON`.

## 6. Tell the person
In plain words: the roadmap's link; that this session is now the main session and a Roadmap writer session is running beside it; that from now on you must tell the writer every plan, decision and start before you start or message a helper, and forward every helper report, and that the plugin holds you to it. Then load the skill `assistant:roadmap-director` and follow it from here on. If the person has already described their project or plan in this conversation, send it to the writer now as the first rows.

# Taking over a roadmap the project already has

For a project whose roadmap page was made before the plugin, by hand or by another arrangement. The page keeps its link and everything on it: every row, mark, answer, note and picture. Nothing is published as a new page, and nothing is deleted.

Ask once, and go on only on a clear yes: "This project already has a roadmap at <link>. Move it onto the plugin? Its link and contents are kept."

Do the steps in order. Show each one working (the command's output, or the read that proves the write) before the next. If a step fails, stop there and tell the person; every step can be run again.

## A. Make this session the main session
Learn this session's own id as in step 2 above (get_session with `session_id` "self"), then:
```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" director --local-id <that id>
```

## B. Record the existing link
```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" page <the link>
```
No page is published here.

## C. Read the old roadmap and see what must change
1. Save the whole database to a folder of your own outside the project (your scratchpad), with ArtifactData reads and `out_dir` set to that folder: action "list" with query {"limit": 1000} on each of "steps", "marks", "questions", "notes" and "board". If the old roadmap's own instructions name other collections, save those too. Keep each read's result: it gives every document's version, which you need in step D.
2. Read the project's own instructions for its old roadmap, if it has any (often a file in `Roadmap page`), and the old page itself (Artifact read). You need them for steps D and G.
3. Run the report. It writes nothing to the database:
   ```
   python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" carry-over "<the folder>" --write-to "<a second folder of your own>"
   ```
   It lists every document that must change and how, what stays as it is, and what to know. With `--write-to` it also saves each document's changed fields to a file, so nothing is retyped.
4. If it lists anything under "NOT SETTLED BY THIS COMMAND", stop and ask the person about each one before writing anything. Show the person the count of documents that change and the kinds of change, in plain words.

## D. Carry the data over
Only the documents the report lists change. Everything else stays exactly as it is.
- Write with ArtifactData "batch", at most 50 writes a batch, using the entries in `batches.json` from step C. Every entry is an "update" and carries `if_version`: the version that document showed in your read. A batch refused for a stale version wrote nothing: read that document again, run the report again, and redo the batch.
- Never delete a document. If something can only be carried over by writing it under a new id, write the new one, read it back to confirm it is there, and only then ask the person whether the old one may go.
- Never write a mark, an answer or a note's words.
- If the old page used words of its own for the line under the title, the heading over the checks, or the names of its lists, keep them: write them to `board/settings` ("set", a new document) with the fields the manual names.
- Then prove it: save the database again to a new folder and run `carry-over` on it. It must say "Nothing needs to change". Count the documents in each collection against the first save: every count must be the same.

## E. Put the plugin's page at the same link
Use the roadmap's own name as the title (the old page's title).
```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" copy-page --title "<the name>"
```
Publish `Roadmap page/roadmap.html` with the Artifact tool **to the same link**: `url` set to the link from step B, `file_path` that file, and no `capabilities` (so the page's database, pictures and comments stay as they are). Never publish it without `url`: that would make a second page. The Artifact tool asks you to read the live page first; that read is step C2. Then read the published page back and check its title is the roadmap's name, and record what the project is brought up to, so `/assistant:roadmap-update` later knows where it started (if the read names no saved file, read again with `path` "index.html"):
```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" updated --published "<the file the read saved>"
```

If the old page's capabilities (the read in C2 shows them) are not the database, the picture store and comments, tell the person before publishing: the page needs all three.

## F. The writer
- If the old roadmap had a writer session and it is still running (it is in your linked sessions), keep it. Record it, then send it one message:
  ```
  python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" writer --id <its local_... id> --name <its name> --title "<its title>"
  ```
  "This project's roadmap has moved onto the Roadmap plugin. Load the skill assistant:roadmap-writer now and follow it from here on, starting with its first-turn steps, which include reading the plugin's manual. It replaces the instructions you had; the page's link is the same. The statuses and some field names changed: use only the manual's."
- If it is gone, or there never was one, follow the skill `assistant:roadmap-start-writer`.

## G. This project's own rules
The plugin's manual and skills now say how the roadmap is kept. Go through the old instructions from C2 and sort every rule in them:
- already the plugin's way: nothing to do;
- the plugin does it differently: the plugin's way stands; list it for the person;
- about this project only (its own names, what its checks must mention, where its decisions are recorded): write it into `Roadmap page/Project rules.md` in the project, in plain words, one rule a line. The main session and the writer read that file.
Do not change the project's other files of instructions yourself; list for the person each place that still describes the old arrangement.

## H. The old locks
```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" old-locks
```
If it finds older roadmap locks in the project's own settings, it writes the folder `Plugin update copy-in/Retire the old roadmap locks` (the changed settings, the settings as they were, and "What changes.md") and prints two commands. You never change the project's `.claude\hooks`, `.claude\settings` files or the old locks' own files by hand; only these commands do. Show the person both commands exactly as printed: the first retires the old locks, the second puts everything back; on their yes, run the first yourself. Tell them plainly that until the first runs, both sets of locks run, and what the file "What changes.md" says that means.

## I. Show it
```
python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" status
```
It must name the main session, the writer and the same link, and say `Blocks: ON`. Then tell the person, in plain words: the link is the same and everything on it was kept; what changed on the page (from step G's list); the two commands from step H if there are any; and that this session is the main session from now on. Load the skill `assistant:roadmap-director` and follow it.
