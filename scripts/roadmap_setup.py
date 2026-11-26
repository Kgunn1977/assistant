"""Records, for one project, what the roadmap blocks need: which session is the main session, which is the Roadmap
writer, and where the roadmap page is. Everything is kept in <project>/.claude/roadmap/config.json. Run it from the
project folder (or pass --project). Commands:
  director [--local-id <id>]   make the session running this command the project's main session; --local-id also
                               records that session's own local_... id, which is the one a message can be sent to
  local-id <id>                main session only: record its own local_... id in a project set up before this was kept
  copy-page --title "Name"     put a fresh copy of the roadmap page in "<project>/Roadmap page/roadmap.html"
  page <url>                   record the published roadmap page's link
  writer --id <session id> [--name roadmap-writer] [--title "Roadmap writer"]
                               record the Roadmap writer session the main session started
  writer-self                  run by the writer session itself: records its own id so it is reminded of its job
  status                       show what is recorded and whether the blocks are on
  off [--root <assistant folder>]
                               turn the roadmap off in this project (/assistant:roadmap-off): the project's
                               .claude/roadmap folder is deleted outright, the project is taken out of the
                               assistant's list of roadmaps, and every
                               roadmap hook stands down. The published page and "Roadmap page" stay as a record.
  plain-copy on|off [--reader name] [--full]
                               ask for the plain copy of the roadmap's facts, or stop asking (reference/agreement.md);
                               --full also asks for the full copy, which holds every document the page reads
  full                         run by the writer after it has written "Roadmap page/roadmap-full.json": checks the file
                               and stamps the time
  full-patch <file | ->        run by a main session that writes the roadmap itself, after its writes: the file holds
                               {"writes": [...]}, the writes just made ({"op", "collection", "doc_id", "data"}), and
                               the full copy and the plain copy are brought up to date from them alone
  facts                        run by the writer after it has written "Roadmap page/roadmap.json": checks the
                               file, fills in what it can work out, and stamps the time
  kind running|stepped         the roadmap's kind: "stepped" (default, a build with an end) or "running" (ongoing
                               work: only live rows, in groups, with a folded History). Records it in the config and
                               prints the one board/settings write that makes the page show it
  helpers cheapest|strongest   the model the main session's helpers use: "cheapest" (default, the cheapest model that
                               does the job well) or "strongest" (always the strongest model). Records it in the config
                               and prints the same write
  settings                     prints the one board/settings write that makes the roadmap page's Settings section show
                               the settings as they now are: kind, helpers, who writes it (and the command for the
                               person to change that), and the project's sessions with their questions file
  switch-off / switch-on       for the person only, never Claude: put the project's roadmap arrangement to one
                               side (the blocks stop), or bring it back
  writes-main / writes-writer  for the person only, never Claude: the main session writes the roadmap itself (no
                               Roadmap writer; the recorded writer is retired and nothing points at it any more), or
                               back to a Roadmap writer session (start one with /assistant:roadmap-start-writer)
For a project whose roadmap was made before the plugin (the take-over in /assistant:roadmap-setup):
  existing                     look in the project for a roadmap the plugin did not set up: its link, its name, its
                               writer session and its old locks. Writes nothing.
  carry-over <folder> [--write-to <folder>]
                               read an export of the old roadmap's database (the folder ArtifactData saved it to) and
                               report, document by document, what must change to fit the plugin's layout. Writes
                               nothing, unless --write-to names a folder for the changed fields, one file a document.
  old-locks [--apply]          find hook lines in the project's own settings that run older, hand-made roadmap locks,
                               and write "Plugin update copy-in/Retire the old roadmap locks" with the changed settings,
                               the settings as they were, and the two commands the person pastes. Changes nothing
                               else. --apply, for the person only, also puts the changed settings in place.
After the plugin itself changed (the update in /assistant:roadmap-update), in the project's main session only:
  update [--published <file>]  say what the project was last brought up to and where the plugin stands now; with the
                               published page as an Artifact read saved it, say exactly what is behind, what to do,
                               and what changed for the person. Writes nothing.
  updated --published <file>   record that the project is at the plugin as it now stands, once the published page is
                               the plugin's page with the project's own title.
The id of the session running a command comes from the plugin's own hook, which notes it a moment before the command
runs; if that note is missing, the plugin's hooks are not running in this session."""
import argparse, datetime, glob, hashlib, json, os, re, shutil, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "hooks"))
import roadmap_blocks as rb

TEMPLATE = os.path.join(ROOT, "page", "roadmap.html")
PLACEHOLDER = "Project Roadmap"
SEEN_MAX_AGE = 120            # seconds: the hook's note must be from this very command
ABOUT = ("Written by the Roadmap plugin's setup; change it by hand or by running /assistant:roadmap-setup again. "
         "director_session_id: the Claude Code session id of the main session; only its own calls are blocked. "
         "writer: the Roadmap writer session; a message to it is one addressed to its session_id, name or title. "
         "page_url: the roadmap page. lock_settings: false lets Claude edit .claude/settings*.json in this project. "
         "title: the roadmap's name. writes: \"main\" when the main session writes the roadmap itself (only the person "
         "sets it, with roadmap_setup.py writes-main or writes-writer). helpers: \"strongest\" when the main session's helpers "
         "always use the strongest model; absent, the cheapest model that does the job well (roadmap_setup.py helpers).")
AGREEMENT = 1                                             # reference/agreement.md: the plain copy
FULL_AGREEMENT = 2                                        # the same file, part 2: the full copy
FULL_COPY = os.path.join("Roadmap page", "roadmap-full.json")
FULL_PARTS = ("steps", "marks", "questions", "notes", "board")
LOCAL_ID = re.compile(r"^local_[A-Za-z0-9_-]{4,}$")
PLAIN_COPY = os.path.join("Roadmap page", "roadmap.json")
READERS = os.path.join("Roadmap page", "readers.json")
READERS_ABOUT = ("Programs that want this project's roadmap kept as a plain file (Roadmap page/roadmap.json). "
                 "Each adds and removes only its own entry.")
FULL_ABOUT = ("The full copy of this project's roadmap: every document the roadmap page reads, kept by the Roadmap writer "
              "while a reader asks for it. The page's own database is the source; never edit this by hand.")
OFF_NAME = "roadmap-off"
STATUSES = ("Not started", "Planned, not started", "Being worked on now", "Built, waiting to be merged",
            "Ready, waiting for your look", "Ready, known fault", "First pass, to be redone", "Done, confirmed")
READY = ("Ready, waiting for your look", "Ready, known fault")
KINDS = ("step", "phase", "item")
PLAIN_ABOUT = ("A plain copy of this project's roadmap, kept by the Roadmap writer after each change so programs that "
               "cannot read the roadmap page can show it. The page's own database is the source; never edit this by hand.")


def find_project(arg):
    if arg:
        return os.path.abspath(arg)
    os.environ.pop("CLAUDE_PROJECT_DIR", None)
    return rb.project_dir({"cwd": os.getcwd()})


def load(project):
    cfg = rb.load_json(rb.config_path(project), {})
    cfg.setdefault("about", ABOUT)
    cfg.setdefault("director_session_id", "")
    cfg.setdefault("director_local_id", "")
    cfg.setdefault("writer", {"session_id": "", "name": "roadmap-writer", "title": "Roadmap writer", "claude_session_id": ""})
    cfg.setdefault("page_url", "")
    cfg.setdefault("lock_settings", True)
    return cfg


def roadmap_name(project, cfg):
    """The roadmap's name: the one setup recorded, else the page copy's own title, else the folder's name."""
    if cfg.get("title"):
        return str(cfg["title"])
    try:
        with open(os.path.join(project, "Roadmap page", "roadmap.html"), encoding="utf-8") as fh:
            m = re.search(r"<title>(.*?)</title>", fh.read(20000), re.S)
        if m and m.group(1).strip():
            return " ".join(m.group(1).split())
    except OSError:
        pass
    return os.path.basename(os.path.abspath(project)) + " Roadmap"


def readers(project):
    """The names of the programs that asked for the plain copy (reference/agreement.md); none means it is not kept."""
    try:
        got = rb.load_json(os.path.join(project, READERS), {})
    except ValueError:
        return []
    listed = got.get("readers") if isinstance(got, dict) else None
    return sorted(str(k) for k in listed) if isinstance(listed, dict) else []


def full_readers(project):
    """The names of the readers that asked for the full copy as well ("full": true in their entry)."""
    try:
        got = rb.load_json(os.path.join(project, READERS), {})
    except ValueError:
        return []
    listed = got.get("readers") if isinstance(got, dict) else None
    if not isinstance(listed, dict):
        return []
    return sorted(str(k) for k, v in listed.items() if isinstance(v, dict) and v.get("full") is True)


def set_reader(project, name, wanted, full=False):
    path = os.path.join(project, READERS)
    try:
        got = rb.load_json(path, {})
    except ValueError:
        got = {}
    got = got if isinstance(got, dict) else {}
    listed = got.get("readers") if isinstance(got.get("readers"), dict) else {}
    if wanted:
        entry = listed.setdefault(name, {"since": datetime.datetime.now().isoformat(timespec="seconds")})
        if full and isinstance(entry, dict):
            entry["full"] = True
    else:
        listed.pop(name, None)
    rb.save_json({"about": READERS_ABOUT, "readers": listed}, path)


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def check_facts(doc):
    """(the tidy facts, the list of what is wrong) for a plain copy as the writer wrote it."""
    wrong, rows, seen = [], [], set()
    if not isinstance(doc, dict):
        return None, ["the file must hold one object with next, rows and questions_open"]
    nxt = doc.get("next")
    if not isinstance(nxt, list) or any(not isinstance(n, dict) or "label" not in n or "text" not in n for n in nxt):
        wrong.append('"next" must be a list of {"label", "text"} pairs (an empty list when there are none)')
        nxt = []
    if not isinstance(doc.get("rows"), list):
        wrong.append('"rows" must be a list (an empty list when the roadmap has no rows)')
    for i, r in enumerate(doc.get("rows") if isinstance(doc.get("rows"), list) else []):
        where = "row " + str(i + 1) + (" (" + str(r.get("id")) + ")" if isinstance(r, dict) and r.get("id") else "")
        if not isinstance(r, dict):
            wrong.append(where + ": must be an object")
            continue
        rid, name = str(r.get("id") or "").strip(), str(r.get("name") or "").strip()
        if not rid or not name:
            wrong.append(where + ": needs an id and a name")
        if rid in seen:
            wrong.append(where + ": the same id is listed twice")
        seen.add(rid)
        if r.get("status") not in STATUSES:
            wrong.append(where + ": status must be exactly one of the eight statuses")
        if r.get("kind") not in KINDS:
            wrong.append(where + ': kind must be "step", "phase" or "item"')
        if not isinstance(r.get("order"), (int, float)) or isinstance(r.get("order"), bool):
            wrong.append(where + ": order must be a number")
        checks, marked = _count(r.get("checks", 0)), _count(r.get("marked", 0))
        if checks is None or marked is None:
            wrong.append(where + ": checks and marked must be whole numbers (how many checks the row carries, and how many of them have a mark)")
        rows.append({"id": rid, "order": r.get("order"), "kind": r.get("kind"), "number": str(r.get("number") or ""),
                     "name": name, "parent": str(r.get("parent") or ""), "status": r.get("status"),
                     "changed": str(r.get("changed") or ""), "checks": checks or 0, "marked": marked or 0})
    questions = _count(doc.get("questions_open", 0))
    if questions is None:
        wrong.append('"questions_open" must be a whole number')
    if wrong:
        return None, wrong
    rows.sort(key=lambda r: r["order"])
    waiting = sum(max(0, r["checks"] - r["marked"]) for r in rows if r["status"] in READY)
    return {"facts_as_of": str(doc.get("facts_as_of") or ""),
            "next": [{"label": str(n["label"]), "text": str(n["text"])} for n in nxt],
            "rows": rows, "questions_open": questions, "checks_waiting": waiting}, []


def facts(project, cfg):
    path = os.path.join(project, PLAIN_COPY)
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        raise SystemExit("Not checked: there is no plain copy yet. Write it first: " + path)
    except ValueError as e:
        raise SystemExit("Not checked: the plain copy is not valid JSON (" + str(e) + "). Write the whole file again.")
    tidy, wrong = check_facts(doc)
    if wrong:
        raise SystemExit("Not accepted; the plain copy was left as it is. Fix these and run this again:\n- " + "\n- ".join(wrong[:30]))
    out = {"about": PLAIN_ABOUT, "agreement": AGREEMENT, "name": roadmap_name(project, cfg), "page_url": cfg.get("page_url") or "",
           "written": datetime.datetime.now().isoformat(timespec="seconds")}
    out.update(tidy)
    rb.save_json(out, path)
    print("Plain copy checked and stamped " + out["written"] + ": " + str(len(out["rows"])) + " rows, "
          + str(out["checks_waiting"]) + " checks waiting, " + str(out["questions_open"]) + " questions open.")
    return 0


def check_full(doc):
    """(the tidy full copy, the list of what is wrong) for the full copy as the writer wrote it."""
    if not isinstance(doc, dict) or not isinstance(doc.get("collections"), dict):
        return None, ['the file must hold one object with "collections"']
    wrong, cols = [], doc["collections"]
    for part in FULL_PARTS:
        got = cols.get(part)
        if not isinstance(got, dict):
            wrong.append('"collections" must hold "' + part + '" as an object of documents keyed by id (empty when there are none)')
        elif any(not isinstance(v, dict) for v in got.values()):
            wrong.append('every document in "' + part + '" must be an object')
    if wrong:
        return None, wrong
    return {"collections": {part: cols[part] for part in FULL_PARTS}}, []


def full_copy(project, cfg):
    path = os.path.join(project, FULL_COPY)
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        raise SystemExit("Not checked: there is no full copy yet. Write it first: " + path)
    except ValueError as e:
        raise SystemExit("Not checked: the full copy is not valid JSON (" + str(e) + "). Write the whole file again.")
    tidy, wrong = check_full(doc)
    if wrong:
        raise SystemExit("Not accepted; the full copy was left as it is. Fix these and run this again:\n- " + "\n- ".join(wrong[:30]))
    out = {"about": FULL_ABOUT, "agreement": FULL_AGREEMENT, "name": roadmap_name(project, cfg), "page_url": cfg.get("page_url") or "",
           "written": datetime.datetime.now().isoformat(timespec="seconds")}
    out.update(tidy)
    rb.save_json(out, path)
    print("Full copy checked and stamped " + out["written"] + ": " + ", ".join(
        str(len(out["collections"][p])) + " " + p for p in FULL_PARTS) + ".")
    return 0


PATCH_OPS = ("set", "update", "delete")


def apply_writes(cols, writes):
    """Applies database writes to the full copy's collections, as the database applies them: "set" puts the whole
    document, "update" merges its fields ({"__delete__": true} removes one), "delete" removes the document.
    Returns (what changed, the list of what is wrong); on anything wrong nothing is applied."""
    wrong, plan = [], []
    if not isinstance(writes, list) or not writes:
        return None, ['the patch must hold "writes": a list of {"op", "collection", "doc_id", "data"}, as sent to the database']
    staged = {p: dict(cols[p]) for p in FULL_PARTS}
    for i, w in enumerate(writes):
        where = "write " + str(i + 1)
        if not isinstance(w, dict):
            wrong.append(where + ": must be an object")
            continue
        op, part, doc_id, data = str(w.get("op") or w.get("action") or "").lower(),w.get("collection"), w.get("doc_id"), w.get("data")
        where += " (" + str(part) + "/" + str(doc_id) + ")"
        if op not in PATCH_OPS:
            wrong.append(where + ': op must be "set", "update" or "delete"')
        elif part not in FULL_PARTS:
            wrong.append(where + ": collection must be one of " + ", ".join(FULL_PARTS))
        elif not isinstance(doc_id, str) or not doc_id.strip():
            wrong.append(where + ": needs a doc_id")
        elif op != "delete" and not isinstance(data, dict):
            wrong.append(where + ": needs data, an object")
        elif op == "set":
            staged[part][doc_id] = {k: v for k, v in data.items() if not (isinstance(v, dict) and v.get("__delete__") is True)}
            plan.append(op + " " + part + "/" + doc_id)
        elif op == "update":
            if doc_id not in staged[part]:
                wrong.append(where + ": the full copy has no such document, so an update cannot be placed; hand its whole "
                             "document as a \"set\" (from a get)")
                continue
            doc = dict(staged[part][doc_id])
            for k, v in data.items():
                if isinstance(v, dict) and v.get("__delete__") is True:
                    doc.pop(k, None)
                else:
                    doc[k] = v
            staged[part][doc_id] = doc
            plan.append(op + " " + part + "/" + doc_id)
        else:
            staged[part].pop(doc_id, None)
            plan.append(op + " " + part + "/" + doc_id)
    if wrong:
        return None, wrong
    cols.update(staged)
    return plan, []


def facts_from(cols):
    """The plain copy's four things, worked out from the full copy's collections (reference/agreement.md, part 1)."""
    marks = cols.get("marks") or {}
    marked = {}
    for m in marks.values():
        if isinstance(m, dict) and m.get("row") and m.get("check"):
            marked.setdefault(str(m["row"]), set()).add(str(m["check"]))
    rows = []
    for rid, d in (cols.get("steps") or {}).items():
        checks = [c for c in d.get("checks") or [] if isinstance(c, dict)]
        ids = {str(c.get("id")) for c in checks}
        rows.append({"id": rid, "order": d.get("order"), "kind": d.get("kind"), "number": d.get("number"),
                     "name": d.get("name"), "parent": d.get("parent"), "status": d.get("status"),
                     "changed": d.get("changed"), "checks": len(checks), "marked": len(ids & marked.get(rid, set()))})
    nxt = (cols.get("board") or {}).get("next") or {}
    return {"facts_as_of": nxt.get("facts_as_of") or "", "next": nxt.get("lines") or [], "rows": rows,
            "questions_open": sum(1 for q in (cols.get("questions") or {}).values()
                                  if isinstance(q, dict) and q.get("status") == "open")}


def full_patch(project, cfg, source):
    """Brings the full copy up to date from only the writes the main session just made, then the plain copy from it,
    so neither is ever rewritten whole by Claude. The copy is never guessed at: a missing or damaged one is refused."""
    path = os.path.join(project, FULL_COPY)
    try:
        if source == "-":
            patch = json.load(sys.stdin)
        else:
            with open(source, encoding="utf-8") as fh:
                patch = json.load(fh)
    except (OSError, ValueError) as e:
        raise SystemExit("Not done: the patch could not be read (" + str(e) + "). Nothing was changed.")
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        raise SystemExit("Not done: there is no full copy to bring up to date (" + path + "). It has to be written whole "
                         "once, from a full read of the database, then checked with the \"full\" command.")
    except ValueError as e:
        raise SystemExit("Not done: the full copy is damaged (not valid JSON: " + str(e) + "), so it was left as it is. It "
                         "has to be written whole once, from a full read of the database, then checked with the \"full\" command.")
    tidy, wrong = check_full(doc)
    if wrong:
        raise SystemExit("Not done: the full copy is damaged, so it was left as it is (" + "; ".join(wrong[:5]) + "). It has "
                         "to be written whole once, from a full read of the database, then checked with the \"full\" command.")
    cols = tidy["collections"]
    plan, wrong = apply_writes(cols, patch.get("writes") if isinstance(patch, dict) else patch)
    if wrong:
        raise SystemExit("Not done; both copies were left as they are. Fix the patch and run this again:\n- " + "\n- ".join(wrong[:30]))
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    out = {"about": FULL_ABOUT, "agreement": FULL_AGREEMENT, "name": roadmap_name(project, cfg),
           "page_url": cfg.get("page_url") or "", "written": stamp, "collections": cols}
    plain, wrong = check_facts(facts_from(cols))
    if wrong:
        raise SystemExit("Not done; both copies were left as they are. After these writes the roadmap would not fit the "
                         "plain copy's shape:\n- " + "\n- ".join(wrong[:30]))
    rb.save_json(out, path)
    said = "Full copy brought up to date and stamped " + stamp + " (" + ", ".join(plan) + ")"
    if readers(project):
        fact = {"about": PLAIN_ABOUT, "agreement": AGREEMENT, "name": out["name"], "page_url": out["page_url"], "written": stamp}
        fact.update(plain)
        rb.save_json(fact, os.path.join(project, PLAIN_COPY))
        said += "; plain copy too"
    print(said + ".")
    return 0


def switch(project, off):
    """Put the project's .claude/roadmap folder to one side, or bring it back. With it aside every hook stands down."""
    live, aside = os.path.join(project, ".claude", "roadmap"), os.path.join(project, ".claude", OFF_NAME)
    src, dst = (live, aside) if off else (aside, live)
    if not os.path.isdir(src):
        print("Nothing to do: the roadmap arrangement is " + ("not on" if off else "not switched off") + " in " + project)
        return 0
    if os.path.exists(dst):
        raise SystemExit("Not done: both " + live + " and " + aside + " exist. Move one of them away by hand first.")
    os.rename(src, dst)
    print("The roadmap arrangement is switched " + ("off" if off else "on") + " in " + project)
    return 0


def roadmap_off(project, root=None):
    """Turn the roadmap off: delete .claude/roadmap outright, and unlist the project."""
    live = os.path.join(project, ".claude", "roadmap")
    if not os.path.isdir(live):
        print("Nothing to do: there is no roadmap set up in " + project + ". Nothing was changed.")
        return 0
    page = str(rb.load_json(rb.config_path(project), {}).get("page_url") or "") if os.path.isfile(rb.config_path(project)) else ""
    shutil.rmtree(live)
    print("Deleted " + live + ".")
    root = os.path.abspath(root or os.path.join(os.path.expanduser("~"), "Documents", "Assistant"))
    path = os.path.join(root, "Live", "personal", "settings.json")
    try:
        with open(path, encoding="utf-8") as fh:
            settings = json.load(fh)
    except (OSError, ValueError):
        settings = None
    listed = settings.get("roadmaps") if isinstance(settings, dict) else None
    here = os.path.normcase(os.path.abspath(project))
    if isinstance(listed, list):
        kept = [e for e in listed if not (isinstance(e, dict) and os.path.normcase(os.path.abspath(str(e.get("folder") or "x").rstrip("/\\"))) == here)]
        if len(kept) != len(listed):
            if kept:
                settings["roadmaps"] = kept
            else:
                settings.pop("roadmaps", None)
            rb.save_json(settings, path)
            print("Taken out of the assistant's list of roadmaps.")
    print("Every roadmap check is off in this project." + (" The roadmap page stays at " + page + " as a record." if page
          else " The roadmap page, if one was published, stays at its link as a record."))
    return 0


def set_kind(project, kind):
    """The roadmap's kind. The page reads it from board/settings (field "kind"); this records it and prints the write."""
    path = rb.config_path(project)
    if not os.path.isfile(path):
        raise SystemExit("Not done: " + project + " has no roadmap set up (run /assistant:roadmap-setup there first).")
    cfg = load(project)
    if kind == "stepped":
        cfg.pop("kind", None)
    else:
        cfg["kind"] = kind
    rb.save_json(cfg, path)
    print("This roadmap's kind is now " + kind + ".")
    return print_settings(project)


HELPERS = {"cheapest": "the cheapest model that does the job well", "strongest": "always the strongest model"}


def set_helpers(project, choice):
    """The model the main session's helpers use: "cheapest" (default, the cheapest that does the job well) or "strongest"."""
    path = rb.config_path(project)
    if not os.path.isfile(path):
        raise SystemExit("Not done: " + project + " has no roadmap set up (run /assistant:roadmap-setup there first).")
    cfg = load(project)
    if choice == "cheapest":
        cfg.pop("helpers", None)
    else:
        cfg["helpers"] = choice
    rb.save_json(cfg, path)
    print("Helpers in " + project + " now use " + HELPERS[choice] + ".")
    return print_settings(project)


def _alive(pid):
    """True when a process with this id is running."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)                  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(k.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259      # STILL_ACTIVE
        finally:
            k.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def project_sessions(project, cfg):
    """The project's sessions for the page's Settings: every Claude session open in the project folder (Claude's own list of
    running sessions, <claude config>/sessions/<pid>.json), and every session that keeps a questions file here though it is
    not open now. [{"id", "name", "questions": true|false, "role": "main" | "writer" | ""}]."""
    qc = rb.load_json(os.path.join(project, ".claude", "questions", "config.json"), {})
    keep = dict(qc.get("sessions") or {}) if qc.get("on") else {}
    if qc.get("on") and not keep and qc.get("main_session_id"):
        keep[str(qc["main_session_id"])] = "Questions.md"
    roles = {str(cfg.get("director_session_id") or ""): "main", str((cfg.get("writer") or {}).get("claude_session_id") or ""): "writer"}
    roles.pop("", None)
    here = os.path.normcase(os.path.abspath(project.rstrip("\\/")))
    base = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude"), "sessions")
    found, seen_ids = [], set()
    for f in sorted(glob.glob(os.path.join(base, "*.json"))):
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue  # a session file that cannot be read or parsed (a closed session's empty leftover) is skipped
        if not isinstance(d, dict):
            continue
        sid, name, cwd = str(d.get("sessionId") or ""), " ".join(str(d.get("name") or "").split()), str(d.get("cwd") or "")
        if len(name) > 120:                                    # cut at a word, never inside one
            name = name[:121].rsplit(" ", 1)[0] if " " in name[:121] else name[:120]
        if not sid or not name or not cwd or os.path.normcase(os.path.abspath(cwd.rstrip("\\/"))) != here or not _alive(d.get("pid")):
            continue
        host = str(d.get("hostSessionId") or "")
        own = host if host.startswith("local_") else sid      # the local_... id survives app restarts; questions files are kept by it
        if any(x["id"] in (sid, own) for x in found):
            continue
        found.append({"id": own, "name": name, "questions": own in keep or sid in keep, "role": roles.get(sid, ""), "at": d.get("updatedAt") or d.get("startedAt") or 0})
        seen_ids.update((sid, own))
    found.sort(key=lambda x: (x["role"] != "main", x["role"] == "writer", -(x["at"] if isinstance(x["at"], (int, float)) else 0)))
    for x in found:
        x.pop("at")
    for sid, fname in keep.items():
        if sid not in seen_ids:
            found.append({"id": sid, "name": os.path.splitext(str(fname))[0] + " (not open now)", "questions": True, "role": roles.get(sid, "")})
    return found


def page_settings(project, cfg):
    """What the roadmap page's Settings section shows, as board/settings holds it: the kind, the model helpers use, who writes
    the roadmap with the exact command the person runs themselves to change it (writes_switch; the page and Claude never run
    it), and the project's sessions with their questions file."""
    writes = "main" if rb.direct(cfg) else "writer"
    script = os.path.join(HERE, os.path.basename(__file__))
    return {"kind": "running" if cfg.get("kind") == "running" else "stepped",
            "helpers": "strongest" if cfg.get("helpers") == "strongest" else "cheapest",
            "writes": writes,
            "writes_switch": 'python "' + script + '" --project "' + os.path.abspath(project) + '" writes-' + ("writer" if writes == "main" else "main"),
            "sessions": project_sessions(project, cfg),
            "settings_as_of": datetime.datetime.now().isoformat(timespec="minutes")}


def print_settings(project):
    """Prints the one board/settings write that makes the roadmap page's Settings section show the settings as they now are."""
    path = rb.config_path(project)
    if not os.path.isfile(path):
        raise SystemExit("Not done: " + project + " has no roadmap set up (run /assistant:roadmap-setup there first).")
    data = page_settings(project, load(project))
    print("To make the roadmap page show the settings as they now are, write the page's settings: \"update\" with its if_version")
    print("(read it first), or \"set\" with no if_version when there is no such document. Write the data exactly as printed:")
    print('  ArtifactData {"collection": "board", "doc_id": "settings", "data": ' + json.dumps(data, ensure_ascii=False) + '}')
    return 0


def set_writes(project, mode):
    """Who writes the roadmap: "main" (the main session itself) or "writer" (a Roadmap writer session). The person's alone."""
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        raise SystemExit("Refused: only the person changes who writes the roadmap, not Claude. Run this yourself in a terminal.")
    path = rb.config_path(project)
    if not os.path.isfile(path):
        raise SystemExit("Not done: " + project + " has no roadmap set up (run /assistant:roadmap-setup there first).")
    cfg = load(project)
    if mode == "main":
        old = dict(cfg.get("writer") or {})
        cfg["writes"] = "main"
        cfg["writer"] = {"session_id": "", "name": "", "title": "", "claude_session_id": ""}
        log = rb.load_json(rb.log_path(project), {})
        for k in ("writer", "user", "report", "stop_refusals"):     # the writer arrangement's own marks
            log.pop(k, None)
        log["wrote"] = time.time()                                   # nothing is owed from before the switch
        rb.save_json(log, rb.log_path(project))
        rb.save_json(cfg, path)
        print("The main session now writes the roadmap itself in " + project + ". The Roadmap writer is no longer recorded.")
        if old.get("session_id"):
            print("The old Roadmap writer session (" + old["session_id"] + (", " + old["title"] if old.get("title") else "") +
                  ") is not used any more: archive it in the Claude app when you like.")
    else:
        cfg.pop("writes", None)
        rb.save_json(cfg, path)
        print("This project is back to a Roadmap writer session in " + project + ". In its main session, run /assistant:roadmap-start-writer.")
    status(project, cfg)
    return 0


# ---- taking over a roadmap that was made before the plugin ----
LINK = re.compile(r"https://claude\.ai/(?:code/)?artifact/[A-Za-z0-9-]+")
COLLECTIONS = ("steps", "marks", "questions", "notes", "board")
COPY_IN = os.path.join("Plugin update copy-in", "Retire the old roadmap locks")
HOOK_SCRIPT = re.compile(r"""[^\s"';|&]*\.(?:py|pyw|ps1|sh|bat|cmd|js|mjs)\b|"[^"]+\.(?:py|pyw|ps1|sh|bat|cmd|js|mjs)"|'[^']+\.(?:py|pyw|ps1|sh|bat|cmd|js|mjs)'""", re.I)
ROW_FIELDS = {"order", "kind", "number", "name", "parent", "status", "does", "not_yet", "uses", "shown_working", "waits_on_you",
              "checks", "table", "plan", "changed", "scores", "scores_title"}


def _read_small(path, limit=2_000_000):
    try:
        if os.path.getsize(path) > limit:
            return ""
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def existing(project, cfg):
    """What an older roadmap left in the project: where its link, name and writer session are written down."""
    page_dir = os.path.join(project, "Roadmap page")
    places = sorted(glob.glob(os.path.join(page_dir, "*.json")) + glob.glob(os.path.join(page_dir, "*.md"))
                    + glob.glob(os.path.join(page_dir, "*.html")) + glob.glob(os.path.join(project, ".claude", "*.json")))
    links, names, writers = {}, [], []
    for path in places:
        text, rel = _read_small(path), os.path.relpath(path, project)
        for url in LINK.findall(text):
            links.setdefault(url, []).append(rel)
        if path.endswith(".json"):
            try:
                doc = json.loads(text)
            except ValueError:
                doc = None
            if isinstance(doc, dict):
                if isinstance(doc.get("name"), str) and doc.get("page_url"):
                    names.append((doc["name"], rel))
                w = doc.get("writer")
                if isinstance(w, dict) and w.get("session_id"):
                    writers.append((str(w["session_id"]), rel))
        elif path.endswith(".html"):
            m = re.search(r"<title>(.*?)</title>", text[:20000], re.S)
            if m and m.group(1).strip():
                names.append((" ".join(m.group(1).split()), rel))
    print("Project:        " + project)
    if cfg.get("page_url"):
        print("Set up by the plugin already: " + cfg["page_url"] + ". There is nothing to take over.")
        return 0
    if not links:
        print("Roadmap page:   no link found in \"Roadmap page\" or .claude. Ask the person for the page's link, or set up a new roadmap.")
    for url, where in sorted(links.items(), key=lambda kv: -len(kv[1])):
        print("Roadmap page:   " + url + "   (written in " + ", ".join(sorted(set(where))) + ")")
    if len(links) > 1:
        print("                More than one link was found. Ask the person which one is the roadmap.")
    seen = set()
    for name, where in names:
        if name not in seen:
            print("Its name:       " + name + "   (from " + where + ")")
            seen.add(name)
    for sid, where in writers:
        print("Its writer:     " + sid + "   (from " + where + ")")
    if not writers:
        print("Its writer:     no writer session found written down")
    locks = find_old_locks(project)
    print("Older locks:    " + (str(sum(len(v["remove"]) for v in locks)) + " hook lines in the project's own settings run older roadmap locks (the command old-locks lists them)"
                                if locks else "none found in the project's own settings"))
    print("Nothing was written.")
    return 0


def plugin_status(old):
    """The plugin's status for a status written in other words, or None when it cannot be told."""
    if old in STATUSES:
        return old
    t = " ".join(str(old or "").lower().split())
    if not t:
        return None
    if "merge" in t:
        return "Built, waiting to be merged"
    if "fault" in t:
        return "Ready, known fault"
    if "waiting" in t and "look" in t:
        return "Ready, waiting for your look"
    if "first pass" in t:
        return "First pass, to be redone"
    if t.startswith("done") or "confirmed" in t:
        return "Done, confirmed"
    if t.startswith("being") or "in progress" in t or "under way" in t:
        return "Being worked on now"
    if "planned" in t:
        return "Planned, not started"
    if "not started" in t:
        return "Not started"
    return None


def _table_from_scores(title, scores):
    """The plugin's table from an older list of score lines (objects that share the same keys)."""
    lines = [r for r in scores if isinstance(r, dict)]
    keys = []
    for r in lines:
        for k in r:
            if k != "note" and k not in keys:
                keys.append(k)
    if not lines or not keys:
        return None
    # the column that names each line comes first: the first one whose values are all words, each different
    named = [k for k in keys if all(isinstance(r.get(k), str) and r.get(k).strip() for r in lines)
             and len({r.get(k) for r in lines}) == len(lines)]
    if named:
        keys.remove(named[0])
        keys.insert(0, named[0])
    cols =[k.replace("_", " ").strip().capitalize() for k in keys]
    rows = []
    for r in lines:
        row = {c: r.get(k) for k, c in zip(keys, cols)}
        if r.get("note") and row.get(cols[0]) is not None:
            row[cols[0]] = str(row[cols[0]]) + " (" + str(r["note"]) + ")"
        rows.append(row)
    sums = []
    for c in cols[1:]:
        vals = [row[c] for row in rows if isinstance(row[c], (int, float)) and not isinstance(row[c], bool)]
        if vals:
            total = sum(vals)
            sums.append(c + " " + str(int(total) if float(total).is_integer() else round(total, 2)))
    table = {"title": str(title or ""), "columns": cols, "rows": rows, "totals": True}
    if sums:
        table["summary"] = "Totals: " + ", ".join(sums)
    return table


def read_export(folder):
    """{collection: {doc id: document}} for every folder of saved documents in an export."""
    out = {}
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if not os.path.isdir(path):
            continue
        docs = {}
        for f in sorted(os.listdir(path)):
            if f.endswith(".json"):
                with open(os.path.join(path, f), encoding="utf-8-sig") as fh:
                    docs[f[:-5]] = json.load(fh)
        out[name] = docs
    return out


def carry_plan(export):
    """(changes, notes, stops). changes: [(collection, doc id, [plain lines], update data)]; notes: things kept as
    they are that the person should know; stops: things this command cannot settle, for the person to rule on."""
    changes, notes, stops = [], [], []
    steps = export.get("steps") or {}
    for doc_id, row in steps.items():
        if not isinstance(row, dict):
            stops.append("steps/" + doc_id + ": not a document with fields")
            continue
        lines, data = [], {}
        old = row.get("status")
        new = plugin_status(old)
        if new is None:
            stops.append("steps/" + doc_id + ": the status " + json.dumps(old, ensure_ascii=False) + " matches none of the eight; the person says which it is")
        elif new != old:
            lines.append("status: " + json.dumps(old, ensure_ascii=False) + " becomes " + json.dumps(new))
            data["status"] = new
        kind = row.get("kind")
        if kind not in KINDS:
            lines.append("kind: " + json.dumps(kind, ensure_ascii=False) + " becomes \"item\" (work outside the step order)")
            data["kind"] = "item"
        for k in sorted(row):
            if k.startswith("waits_on_") and k != "waits_on_you":
                if "waits_on_you" in row or "waits_on_you" in data:
                    stops.append("steps/" + doc_id + ": both " + k + " and waits_on_you are there; the person says which words stay")
                else:
                    lines.append(k + " becomes waits_on_you (the same words)")
                    data["waits_on_you"] = row[k]
                    data[k] = {"__delete__": True}
        if isinstance(row.get("scores"), list) and "table" not in row:
            table = _table_from_scores(row.get("scores_title"), row["scores"])
            if table:
                lines.append("scores (" + str(len(table["rows"])) + " lines) and scores_title become table, columns " + ", ".join(table["columns"]))
                data["table"] = table
                data["scores"] = {"__delete__": True}
                if "scores_title" in row:
                    data["scores_title"] = {"__delete__": True}
        if not isinstance(row.get("order"), (int, float)) or isinstance(row.get("order"), bool):
            stops.append("steps/" + doc_id + ": order is not a number")
        if not str(row.get("name") or "").strip():
            stops.append("steps/" + doc_id + ": no name")
        if (data.get("kind") or kind) == "phase" and row.get("parent") not in steps:
            stops.append("steps/" + doc_id + ": a phase whose parent " + json.dumps(row.get("parent"), ensure_ascii=False) + " is not a row")
        if lines:
            changes.append(("steps", doc_id, lines, data))
    checks = {rid: {c.get("id") for c in (r.get("checks") or []) if isinstance(c, dict)} for rid, r in steps.items() if isinstance(r, dict)}
    off_row = 0
    for doc_id, m in (export.get("marks") or {}).items():
        if not isinstance(m, dict) or m.get("result") not in ("works", "fails") or doc_id != str(m.get("row")) + "--" + str(m.get("check")):
            stops.append("marks/" + doc_id + ": not a mark the plugin's page can read (it needs row, check, result \"works\" or \"fails\", and the id <row>--<check>)")
        elif m.get("check") not in checks.get(m.get("row"), ()):
            off_row += 1
    if off_row:
        notes.append(str(off_row) + " marks are for checks no longer on their rows: kept as the record, not shown on the page")
    loose = 0
    for doc_id, q in (export.get("questions") or {}).items():
        if not isinstance(q, dict) or not str(q.get("question") or "").strip():
            stops.append("questions/" + doc_id + ": no question text")
            continue
        if q.get("status") not in ("open", "answered", "done"):
            notes.append("questions/" + doc_id + ": status " + json.dumps(q.get("status"), ensure_ascii=False) + " is shown as open")
        if q.get("row") not in steps:
            loose += 1
    if loose:
        notes.append(str(loose) + " questions name a row that is not on the roadmap: shown at the top under \"Questions not tied to a row\"")
    board = export.get("board") or {}
    nxt = board.get("next")
    if nxt is not None and (not isinstance(nxt, dict) or not isinstance(nxt.get("lines", []), list)
                            or any(not isinstance(l, dict) or "label" not in l or "text" not in l for l in nxt.get("lines", []))):
        stops.append("board/next: \"lines\" must be a list of {\"label\", \"text\"} pairs")
    if "settings" not in board:
        notes.append("board/settings is not there: the page uses its own words for the line under the title and the headings until the writer sets them")
    for name in board:
        if name not in ("next", "settings") and not name.startswith("ask-"):
            notes.append("board/" + name + ": kept, not shown on the page")
    for name in export:
        if name not in COLLECTIONS:
            notes.append("collection \"" + name + "\" (" + str(len(export[name])) + " documents): kept, not shown on the page")
    extra = {}
    for row in steps.values():
        for k in (row if isinstance(row, dict) else ()):
            if k not in ROW_FIELDS and not k.startswith("waits_on_"):
                extra[k] = extra.get(k, 0) + 1
    for k, n in sorted(extra.items()):
        notes.append("field \"" + k + "\" on " + str(n) + " rows: kept, not shown on the page")
    return changes, notes, stops


def carry_over(folder, write_to):
    if not os.path.isdir(folder):
        raise SystemExit("Not read: there is no folder " + folder + ". Save the old roadmap's database there first (ArtifactData reads with out_dir).")
    export = read_export(folder)
    if not export.get("steps"):
        raise SystemExit("Not read: " + folder + " has no saved rows (a folder \"steps\" of .json files). Save the database again.")
    changes, notes, stops = carry_plan(export)
    counts = ", ".join(name + " " + str(len(docs)) for name, docs in export.items())
    print("Read " + str(sum(len(d) for d in export.values())) + " documents from " + folder + " (" + counts + ").")
    if not changes and not stops:
        print("Nothing needs to change: every document already fits the plugin's layout.")
    if changes:
        print("\nTO CHANGE: " + str(len(changes)) + " documents, each one \"update\" pinned to the version its read showed. No document is moved or deleted.")
        for col, doc_id, lines, data in changes:
            print(col + "/" + doc_id)
            for l in lines:
                print("  " + l)
            print("  data: " + json.dumps(data, ensure_ascii=False))
    touched = {(c, d) for c, d, _, _ in changes}
    stay = [name + " " + str(sum(1 for d in docs if (name, d) not in touched)) for name, docs in export.items()]
    print("\nSTAYS AS IT IS: " + ", ".join(stay) + ".")
    if notes:
        print("\nTO KNOW:")
        for n in notes:
            print("- " + n)
    if stops:
        print("\nNOT SETTLED BY THIS COMMAND (stop and ask the person before writing anything):")
        for n in stops:
            print("- " + n)
    if write_to and changes:
        target, source = os.path.abspath(write_to), os.path.abspath(folder)
        if target == source or target.startswith(source + os.sep):
            raise SystemExit("Not written: --write-to must be a folder outside the export.")
        batch = []
        for col, doc_id, _, data in changes:
            path = os.path.join(target, col, doc_id + ".json")
            rb.save_json(data, path)
            batch.append({"op": "update", "collection": col, "doc_id": doc_id, "file_path": path})
        rb.save_json({"about": "The writes for the carry-over, at most 50 to a batch. Add to each entry if_version: the version the read showed for that document.",
                      "batches": [batch[i:i + 50] for i in range(0, len(batch), 50)]}, os.path.join(target, "batches.json"))
        print("\nThe changed fields were written, one file a document, under " + target + " (batches.json lists them). The database was not touched.")
    else:
        print("\nNothing was written.")
    return 1 if stops else 0


def _hook_command(h):
    return " ".join([str(h.get("command") or "")] + [str(a) for a in (h.get("args") or [])]) if isinstance(h, dict) else ""


def _old_lock_scripts(command, project):
    """The older roadmap scripts a hook line runs: script files, not the plugin's own, whose name or text speaks of the roadmap."""
    hits = []
    for raw in HOOK_SCRIPT.findall(command):
        path = raw.strip("\"'")
        if "${CLAUDE_PLUGIN_ROOT}" in path or os.path.abspath(path).lower().startswith(ROOT.lower() + os.sep):
            continue
        base = os.path.basename(path.replace("\\", "/"))
        local = os.path.join(project, ".claude", "hooks", base)
        here = local if os.path.isfile(local) else path
        if "roadmap" in base.lower() or "roadmap" in _read_small(here).lower():
            hits.append(base)
    return hits


def find_old_locks(project):
    """[{file, raw, remove: [(event, matcher, [script names])]}] for each settings file that runs older roadmap locks."""
    out = []
    for path in sorted(glob.glob(os.path.join(project, ".claude", "settings*.json"))):
        with open(path, "rb") as fh:
            raw = fh.read()
        try:
            data = json.loads(raw.decode("utf-8-sig"))
        except ValueError:
            continue
        remove = []
        for event, groups in ((data.get("hooks") or {}).items() if isinstance(data, dict) else ()):
            for g in (groups if isinstance(groups, list) else ()):
                for h in ((g.get("hooks") or []) if isinstance(g, dict) else ()):
                    names = _old_lock_scripts(_hook_command(h), project)
                    if names:
                        remove.append((event, str(g.get("matcher") or "every call"), names))
        if remove:
            out.append({"file": path, "raw": raw, "remove": remove})
    return out


def _without_old_locks(found, project):
    """(the settings file's text with the old lock lines taken out and everything else as it was, hook lines left)."""
    text = found["raw"].decode("utf-8-sig")
    data = json.loads(text)
    hooks, left = data.get("hooks") or {}, 0
    for event in list(hooks):
        groups = []
        for g in hooks[event]:
            if isinstance(g, dict) and isinstance(g.get("hooks"), list):
                keep = [h for h in g["hooks"] if not _old_lock_scripts(_hook_command(h), project)]
                if not keep:
                    continue
                left += len(keep)
                g = dict(g, hooks=keep)
            groups.append(g)
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]
    m = re.search(r"\n([ \t]+)\S", text)
    indent = m.group(1) if m else "  "
    out = json.dumps(data, ensure_ascii=False, indent=indent if "\t" in indent else len(indent))
    if "\r\n" in text:
        out = out.replace("\n", "\r\n")
    return out + ("\r\n" if text.endswith("\r\n") else "\n" if text.endswith("\n") else ""), left


def old_locks(project, apply):
    dest = os.path.join(project, COPY_IN)
    was = os.path.join(dest, "as it was")
    found = find_old_locks(project)

    def win(path):
        return os.path.abspath(path).replace("/", "\\")

    def copy_cmd(pairs):
        return "; ".join('Copy-Item -LiteralPath "' + win(a) + '" -Destination "' + win(b) + '" -Force' for a, b in pairs)

    if not found:
        kept = sorted(glob.glob(os.path.join(was, "settings*.json")))
        print("No hook line in this project's own settings runs an older roadmap lock. Nothing to retire.")
        if kept:
            print("The settings as they were before the old locks were retired are kept in " + win(was) + ". To put them back, paste in PowerShell:")
            print(copy_cmd([(k, os.path.join(project, ".claude", os.path.basename(k))) for k in kept]))
        return 0
    os.makedirs(was, exist_ok=True)
    report = ["# Retire the old roadmap locks", "",
              "This project ran roadmap locks of its own before it moved onto the Roadmap plugin. The plugin's blocks now do that job, "
              "so the old ones are switched off by taking their lines out of the project's settings. Only those lines change. "
              "The old script files and their own records stay where they are, unused.", ""]
    apply_pairs, back_pairs = [], []
    for f in found:
        name = os.path.basename(f["file"])
        text, left = _without_old_locks(f, project)
        with open(os.path.join(was, name), "wb") as fh:
            fh.write(f["raw"])
        with open(os.path.join(dest, name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        apply_pairs.append((os.path.join(dest, name), f["file"]))
        back_pairs.append((os.path.join(was, name), f["file"]))
        report += ["## " + os.path.join(".claude", name), "", "Lines taken out (" + str(len(f["remove"])) + "):", ""]
        report += ["- When: " + event + ", on: " + matcher + ". Ran: " + ", ".join(names) for event, matcher, names in f["remove"]]
        report += ["", "Hook lines left as they were: " + str(left) + ". Everything else in the file is unchanged.", ""]
    do, undo = copy_cmd(apply_pairs), copy_cmd(back_pairs)
    report += ["## The two commands", "", "Paste in your own PowerShell window, not in Claude.", "", "To retire the old locks:", "", "```", do, "```", "",
               "To put everything back as it was:", "", "```", undo, "```", "",
               "## Until you paste the first command", "",
               "Both sets of locks run. An old lock that guards the project's settings can refuse the plugin's own setup command; "
               "if it does, Claude cannot set up or change the roadmap arrangement here until the first command is pasted. "
               "Starting or messaging a helper is checked twice, once by each set, each against its own record of when the "
               "writer was last told, so the old set can refuse a helper the plugin's set would let go.", "",
               "## After you paste it", "",
               "The plugin's lock guards the project's settings, its .claude/hooks folder, and the roadmap's own records. "
               "The old lock scripts are no longer run by anything.", ""]
    with open(os.path.join(dest, "What changes.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(report))
    total = sum(len(f["remove"]) for f in found)
    print("Older roadmap locks found: " + str(total) + " hook lines in " + ", ".join(os.path.join(".claude", os.path.basename(f["file"])) for f in found) + ".")
    for f in found:
        for event, matcher, names in f["remove"]:
            print("  " + event + " (" + matcher + "): " + ", ".join(names))
    print("Written to " + win(dest) + ": the changed settings, the settings as they were (\"as it was\"), and \"What changes.md\".")
    if apply:
        for a, b in apply_pairs:
            shutil.copyfile(a, b)
        print("Done: the old locks are retired. Only the plugin's blocks run in this project now.")
    else:
        print("Nothing in .claude was changed. To retire the old locks, paste this in your own PowerShell window:")
        print(do)
    print("To put everything back as it was, paste:")
    print(undo)
    return 0


# ---- bringing a set-up project up to the plugin as it now stands ----
LAYOUT = 1                    # the database's layout (reference/database.md); raise it only when stored data must be changed to fit
CHANGES = os.path.join(ROOT, "reference", "changes.md")
INSTRUCTIONS = ("skills/roadmap-director/SKILL.md", "skills/roadmap-writer/SKILL.md", "reference/database.md", "reference/agreement.md")
STAMP = re.compile(r'<meta name="roadmap-plugin-page" content="([0-9a-f]+)">')
WRITER_NOTE = ("The Roadmap plugin was updated. Load the skill assistant:roadmap-writer again now and follow it from here on, "
               "reading the plugin's manual again as its first-turn steps say. It replaces the instructions you had. "
               "The page's link is the same. Change nothing on the roadmap because of this message.")


def page_stamp():
    """A short mark of the plugin's page as it stands; copy-page writes it into every copy."""
    with open(TEMPLATE, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def instructions_mark():
    h = hashlib.sha256()
    for rel in INSTRUCTIONS:
        with open(os.path.join(ROOT, rel), "rb") as fh:
            h.update(rel.encode() + b"\0" + fh.read().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()[:16]


def read_changes():
    """[(number, day, words)] from the plugin's list of what changed for the person, oldest first."""
    with open(CHANGES, encoding="utf-8") as fh:
        found = [(int(m.group(1)), m.group(2), m.group(3).strip())
                 for m in re.finditer(r"^(\d+)\. (\d{4}-\d\d-\d\d)\. (.+)$", fh.read(), re.M)]
    if [n for n, _, _ in found] != list(range(1, len(found) + 1)):
        raise SystemExit("The plugin's list of changes (reference/changes.md) is not numbered 1, 2, 3 in order; reinstall the plugin.")
    return found


def main_session_only(project, cfg):
    """Stops, having changed nothing, unless the project is set up and the session running this is its main session."""
    if not cfg.get("page_url") or not cfg.get("director_session_id"):
        raise SystemExit("Refused, and nothing was changed: no roadmap is set up by the plugin in " + project + ". Run /assistant:roadmap-setup first.")
    sid = seen_session(project)
    if sid != cfg["director_session_id"]:
        raise SystemExit("Refused, and nothing was changed: this is not the project's main session. The main session is "
                         + cfg["director_session_id"] + "; this session is " + sid + ". Run /assistant:roadmap-update in the main "
                         "session, or run /assistant:roadmap-setup here first to make this session the main one.")


def read_published(path):
    """(the page mark, the title) of a published page as an Artifact read saved it."""
    if not os.path.isfile(path):
        raise SystemExit("Not read: there is no file " + path + ". Read the published page with the Artifact tool and give the file it saved.")
    text = _read_small(path, 20_000_000)
    m, t = STAMP.search(text), re.search(r"<title>(.*?)</title>", text, re.S)
    return (m.group(1) if m else ""), (" ".join(t.group(1).split()) if t else "")


def update(project, cfg, published):
    main_session_only(project, cfg)
    changes, name, mark = read_changes(), roadmap_name(project, cfg), cfg.get("brought_up_to") or {}
    last = changes[-1]
    print("Project:        " + project)
    print("Roadmap page:   " + cfg["page_url"])
    print("Its name:       " + name)
    print("Brought up to:  " + ("change " + str(mark.get("change")) + ", on " + str(mark.get("when")) if mark
                                else "not recorded (the project was set up before the plugin kept this record)"))
    print("The plugin now: change " + str(last[0]) + ", of " + last[1])
    if not published:
        print("Next: read the published page (Artifact read of the link above) and run this again with --published \"<the file the read saved>\".")
        print("Nothing was changed.")
        return 0
    stamp, title = read_published(published)
    page_behind = stamp != page_stamp() or title != name
    told_behind = mark.get("instructions") != instructions_mark()
    layout_behind = int(mark.get("layout", LAYOUT)) < LAYOUT
    local_behind = not cfg.get("director_local_id")
    new = [c for c in changes if c[0] > int(mark.get("change", 0))]
    print("Published page: " + ("the plugin's page as it now stands" if not page_behind else
                                "behind: it is not the plugin's page as it now stands" + ("" if title == name else " (its title reads \"" + title + "\")")))
    print("Instructions:   " + ("behind: the main session's and the writer's have changed" if told_behind else "as they now stand"))
    print("Data layout:    " + ("CHANGED, from " + str(mark.get("layout")) + " to " + str(LAYOUT) if layout_behind else "the same"))
    print("Its own id:     " + ("not recorded: a message from outside cannot reach this session" if local_behind else "recorded"))
    if not (page_behind or told_behind or layout_behind or local_behind or new):
        print("\nNothing to update: this project is at the plugin as it now stands. Publish nothing and send no message.")
        print("Nothing was changed.")
        return 0
    script = '"' + os.path.join(HERE, os.path.basename(__file__)).replace("\\", "/") + '"'
    n, w = 0, cfg.get("writer") or {}
    print("\nTO DO, in this order:")
    if layout_behind:
        n += 1
        print(str(n) + ". STOP FOR THE PERSON FIRST. The stored data must be changed to fit. Save the page's database and run the "
              "carry-over report (the setup skill's take-over, step C); show the person what it lists and write nothing to the "
              "database until they say yes. Then do its step D.")
    if page_behind:
        n += 1
        print(str(n) + ". Republish the page to the SAME link. Run: python " + script + ' copy-page --title "' + name + '"')
        print("   Then publish \"Roadmap page/roadmap.html\" with the Artifact tool: url " + cfg["page_url"] + ", file_path that file, "
              "and no capabilities. Never without url. The database is not touched.")
    if told_behind:
        n += 1
        print(str(n) + ". Load the skill assistant:roadmap-director again now, and read the manual again as it says.")
        n += 1
        if w.get("session_id"):
            print(str(n) + ". Send the Roadmap writer (" + w["session_id"] + ") this one message, once. If it is not among your linked "
                  "sessions it is gone: send nothing, tell the person, and point them to /assistant:roadmap-start-writer.")
            print("   " + WRITER_NOTE)
        else:
            print(str(n) + ". No Roadmap writer is recorded: send nothing, tell the person, and point them to /assistant:roadmap-start-writer.")
    if local_behind:
        n += 1
        print(str(n) + ". Record this session's own id. Call get_session with session_id \"self\" (mcp__ccd_session_mgmt__get_session); "
              "its id is the local_... one. Run: python " + script + " local-id <that id>")
    n += 1
    print(str(n) + ". Read the published page again and record it. Run: python " + script + ' updated --published "<the file the read saved>"')
    if new:
        since = "since change " + str(mark["change"]) if mark.get("change") else "(no earlier record, so the whole list)"
        print("\nWHAT CHANGED FOR THE PERSON " + since + ", to tell them in these words:")
        for num, day, words in new:
            print("- " + day[5:7] + "/" + day[8:] + "/" + day[2:4] + ". " + words)
    else:
        print("\nWHAT CHANGED FOR THE PERSON: nothing they would notice.")
    print("\nNothing was changed.")
    return 0


def updated(project, cfg, published):
    main_session_only(project, cfg)
    stamp, title = read_published(published)
    name = roadmap_name(project, cfg)
    if stamp != page_stamp() or title != name:
        raise SystemExit("Not recorded: the published page is not the plugin's page as it now stands with the title \"" + name
                         + "\". Run copy-page, publish \"Roadmap page/roadmap.html\" to the same link, read the page again, and run this again.")
    last = read_changes()[-1]
    cfg["brought_up_to"] = {"change": last[0], "of": last[1], "layout": LAYOUT, "page": stamp, "instructions": instructions_mark(),
                            "when": datetime.datetime.now().isoformat(timespec="minutes")}
    rb.save_json(cfg, rb.config_path(project))
    print("Recorded: this project is brought up to the plugin as it now stands (change " + str(last[0]) + ", of " + last[1] + ").")
    return 0


def own_id(given):
    given = (given or "").strip()
    if not LOCAL_ID.match(given):
        raise SystemExit("Not recorded: that is not a session id of the form local_... . Get it from get_session with session_id \"self\".")
    return given


def seen_session(project):
    seen = rb.load_json(os.path.join(project, ".claude", "roadmap", "seen.json"), {})
    if not seen.get("session_id") or time.time() - float(seen.get("time", 0)) > SEEN_MAX_AGE:
        raise SystemExit("Not recorded: the Roadmap plugin's hooks did not see this command, so this session's id is not "
                         "known. Check the plugin is installed and turned on for this project, that Python runs as "
                         "'python', and that this command is run from the project folder (" + project + ").")
    return seen["session_id"]


def status(project, cfg):
    w = cfg["writer"]
    print("Project:        " + project)
    print("Main session:   " + (cfg["director_session_id"] or "not recorded"))
    print("Its own id:     " + (cfg.get("director_local_id") or "not recorded (the id a message to the main session is sent to)"))
    if rb.direct(cfg):
        print("Roadmap writes: by the main session itself (no Roadmap writer)")
    else:
        print("Roadmap writer: " + (w.get("session_id") or "not recorded") + (" (" + w.get("title", "") + ")" if w.get("session_id") else ""))
    print("Roadmap page:   " + (cfg["page_url"] or "not recorded"))
    print("Roadmap kind:   " + (cfg.get("kind") or "stepped"))
    print("Helpers use:    " + HELPERS["strongest" if cfg.get("helpers") == "strongest" else "cheapest"])
    asked = readers(project)
    print("Plain copy:     " + ("on, asked for by " + ", ".join(asked) + " (" + PLAIN_COPY + ")" if asked else "off"))
    print("Blocks:         " + (("ON: helpers never write the roadmap; a reply that owes it a write is held once" if rb.direct(cfg) else "ON")
                                 if rb.active(cfg) else "off until both the main session and the writer are recorded"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project")
    sub = ap.add_subparsers(dest="cmd", required=True)
    dr = sub.add_parser("director")
    dr.add_argument("--local-id")
    li = sub.add_parser("local-id")
    li.add_argument("id")
    cp = sub.add_parser("copy-page")
    cp.add_argument("--title", required=True)
    pg = sub.add_parser("page")
    pg.add_argument("url")
    wr = sub.add_parser("writer")
    wr.add_argument("--id", required=True)
    wr.add_argument("--name", default="roadmap-writer")
    wr.add_argument("--title", default="Roadmap writer")
    sub.add_parser("writer-self")
    sub.add_parser("status")
    pc = sub.add_parser("plain-copy")
    pc.add_argument("state", choices=("on", "off"))
    pc.add_argument("--reader", default="by hand")
    pc.add_argument("--full", action="store_true")
    sub.add_parser("facts")
    sub.add_parser("full")
    fp = sub.add_parser("full-patch")
    fp.add_argument("source")
    of = sub.add_parser("off")
    of.add_argument("--root")
    sub.add_parser("switch-off")
    sub.add_parser("switch-on")
    kd = sub.add_parser("kind")
    kd.add_argument("kind", choices=("running", "stepped"))
    hp = sub.add_parser("helpers")
    hp.add_argument("choice", choices=("cheapest", "strongest"))
    sub.add_parser("settings")
    sub.add_parser("writes-main")
    sub.add_parser("writes-writer")
    sub.add_parser("existing")
    co = sub.add_parser("carry-over")
    co.add_argument("folder")
    co.add_argument("--write-to")
    ol = sub.add_parser("old-locks")
    ol.add_argument("--apply", action="store_true")
    up = sub.add_parser("update")
    up.add_argument("--published")
    ud = sub.add_parser("updated")
    ud.add_argument("--published", required=True)
    args = ap.parse_args(argv)
    project = find_project(args.project)
    if args.cmd == "off":
        return roadmap_off(project, args.root)
    if args.cmd in ("switch-off", "switch-on"):
        return switch(project, args.cmd == "switch-off")
    if args.cmd == "kind":
        return set_kind(project, args.kind)
    if args.cmd == "helpers":
        return set_helpers(project, args.choice)
    if args.cmd == "settings":
        return print_settings(project)
    if args.cmd in ("writes-main", "writes-writer"):
        return set_writes(project, "main" if args.cmd == "writes-main" else "writer")
    if args.cmd == "carry-over":
        return carry_over(args.folder, args.write_to)
    if args.cmd == "old-locks":
        return old_locks(project, args.apply)
    cfg = load(project)
    if args.cmd == "existing":
        return existing(project, cfg)
    if args.cmd == "update":
        return update(project, cfg, args.published)
    if args.cmd == "updated":
        return updated(project, cfg, args.published)
    if args.cmd == "facts":
        return facts(project, cfg)
    if args.cmd == "full":
        return full_copy(project, cfg)
    if args.cmd == "full-patch":
        return full_patch(project, cfg, args.source)
    if args.cmd == "local-id":
        main_session_only(project, cfg)
        cfg["director_local_id"] = own_id(args.id)
        rb.save_json(cfg, rb.config_path(project))
        status(project, cfg)
        return 0
    if args.cmd == "plain-copy":                              # the readers' list only; the project's ids are not touched
        name = " ".join(args.reader.split())[:60] or "by hand"
        set_reader(project, name, args.state == "on", args.full)
        status(project, cfg)
        return 0

    if args.cmd == "status":
        status(project, cfg)
        return 0
    if args.cmd == "copy-page":
        title = " ".join(args.title.split())
        if not title or any(c in title for c in "<>&"):
            raise SystemExit("Give the page a plain title without < > or &.")
        with open(TEMPLATE, encoding="utf-8") as fh:
            html = fh.read()
        if html.count(PLACEHOLDER) != 2:
            raise SystemExit("The page template is not as expected; reinstall the plugin.")
        dest = os.path.join(project, "Roadmap page", "roadmap.html")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(html.replace(PLACEHOLDER, title).replace("</title>", '</title>\n<meta name="roadmap-plugin-page" content="' + page_stamp() + '">', 1))
        print("Page copy written: " + dest)
        cfg["title"] = title
        rb.save_json(cfg, rb.config_path(project))
        return 0
    if args.cmd == "director":
        cfg["director_session_id"] = seen_session(project)
        if args.local_id:
            cfg["director_local_id"] = own_id(args.local_id)
    elif args.cmd == "page":
        if not args.url.startswith("https://claude.ai/"):
            raise SystemExit("That is not a claude.ai artifact link.")
        cfg["page_url"] = args.url
    elif args.cmd == "writer":
        if rb.direct(cfg):
            raise SystemExit("Not recorded: this project's main session writes the roadmap itself, so it has no Roadmap writer. "
                             "Only the person switches it back (roadmap_setup.py writes-writer).")
        cfg["writer"].update({"session_id": args.id, "name": args.name, "title": args.title})
    elif args.cmd == "writer-self":
        sid = seen_session(project)
        if sid == cfg["director_session_id"]:
            raise SystemExit("Not recorded: this session is the main session. Run this only in the Roadmap writer session.")
        cfg["writer"]["claude_session_id"] = sid
    rb.save_json(cfg, rb.config_path(project))
    status(project, cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
