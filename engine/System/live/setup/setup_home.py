r"""The setup helper: the one way the setup skills read and change an owner's home.

Every setup skill (the interview and the later-change skills) runs this script and nothing else to change
the home. It records each interview answer in the home (personal\setup.json), so the interview can be
stopped and picked up later, and applies each answer through the engine's own setup steps, so the home is
written exactly the way the engine reads it. Re-answering a question replaces the earlier answer in the
home; nothing has to start over.

It names no person and holds nothing about one: everything it writes comes from the answers given.

    python setup_home.py [--engine FOLDER] [--home FOLDER] COMMAND [ARGS]

The engine folder is the one holding setup_steps.py (default: the assistant's laid-down engine,
Documents\Assistant\System\live). The home defaults to the engine's own (ASSISTANT_LIVE_HOME or
<root>\Live). Output is JSON on one line, for the skill to read; plain words are in "says".
Exit code 0 means done, 2 means refused (the reason is in "says"), 3 means the engine cannot do this yet.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys

ORDER = ("audit", "name", "work", "areas", "accounts", "calendars", "projects", "people", "matters", "since", "readback", "page",
         "sending", "turn_on")
LATER = ("standing_sends",)                          # answered only from the change texts, never asked in setup
OPTIONAL = {"calendars", "projects", "people", "matters"}
STEP = {"audit": 0, "name": 1, "work": 1, "areas": 1, "accounts": 2, "calendars": 2, "projects": 3, "people": 4, "matters": 4,
        "since": 5, "readback": 5, "page": 6, "sending": 7, "standing_sends": 7, "turn_on": 7}
# Junk senders and kinds of message never to show are not asked until the interview is rewritten: a new home starts with
# nothing hidden, and what to hide is learned from the owner's presses on cards. An answer to either writes nothing.
NOT_ASKED = ("junk_senders", "junk_kinds")
# asked on the page as setup cards instead (onboard.py), once `cards` is run: the desktop interview skips them
CARDS_MARK = "asked on the page's setup cards"
ON_CARDS = ("name", "work", "areas", "accounts", "calendars", "people", "matters", "since", "readback")
NOT_ASKED_SAYS = ("Not asked for now, and nothing was saved: a new assistant starts with nothing hidden and learns what to hide "
                  "from your cards (the button \"I did not need this\").")


class Refused(Exception):
    pass


class NotYet(Exception):
    pass


def default_engine():
    return os.path.join(os.path.expanduser("~"), "Documents", "Assistant", "System", "live")


def load_engine(engine, home, root=None):
    if root:
        engine, home = os.path.join(root, "System", "live"), os.path.join(root, "Live")
    engine = os.path.abspath(engine or os.environ.get("ASSISTANT_ENGINE") or default_engine())
    if not os.path.exists(os.path.join(engine, "setup_steps.py")):
        raise Refused(f"The assistant's program is not at {engine}. Lay it down first (the setup skill's first step).")
    if home:
        os.environ["ASSISTANT_LIVE_HOME"] = os.path.abspath(home)
    sys.dont_write_bytecode = True
    sys.path.insert(0, engine)
    import setup_steps  # noqa: E402
    return setup_steps


# --- the interview record --------------------------------------------------------------------------
def record_path(ss):
    return os.path.join(ss.common.PERSONAL, "setup.json")


def record(ss):
    got = ss.common.read_json(record_path(ss), None)
    if not isinstance(got, dict):
        got = {"started": now(), "answers": {}, "skipped": [], "pending_account": None, "finished": None}
    got.setdefault("answers", {})
    got.setdefault("skipped", [])
    return got


def save_record(ss, rec):
    os.makedirs(ss.common.PERSONAL, exist_ok=True)
    ss.common.write_json(record_path(ss), rec)


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def has_calendar(ss):
    return any(k == "calendar" for _, k in kinds_connected(ss))


def kinds_connected(ss):
    types = ss.connections.types()
    return [(c["id"], getattr(types.get(c["type"]), "KIND", "")) for c in ss.connections.listed(everything=True)]


def next_question(ss, rec):
    for q in ORDER:
        if q in rec["answers"] or q in rec["skipped"]:
            continue
        if q == "calendars" and not has_calendar(ss):
            continue
        return q
    return None


def progress(ss):
    rec = record(ss)
    q = next_question(ss, rec)
    looked = (ss.common.read_json(os.path.join(ss.common.PERSONAL, "audit.json"), None) or {}).get("findings")
    return {"next": q, "step": STEP.get(q) if q else None, "answered": [k for k in ORDER if k in rec["answers"]],
            "audit_started": bool(looked and any(f.get("decided") for f in looked)),
            "skipped": rec["skipped"], "pending_account": rec.get("pending_account"), "finished": rec.get("finished"),
            "says": "Everything is answered." if not q else f"Next is step {STEP[q]}, question '{q}'."}


# --- applying one answer -----------------------------------------------------------------------------
def _list(value, name):
    if isinstance(value, str):
        value = [ln for ln in value.splitlines()]
    if not isinstance(value, list):
        raise Refused(f"'{name}' needs a list.")
    return [str(v).strip() for v in value if str(v).strip()]


def _you(ss, rec, **change):
    a = {k: v for k, v in rec["answers"].items() if (v or {}).get("value") != CARDS_MARK}
    a.update({k: {"value": v} for k, v in change.items()})
    name = (a.get("name") or {}).get("value") or {}
    name = name if isinstance(name, dict) else {}       # asked on the setup cards: the cards keep the name (onboard.py)
    if not name.get("first"):
        raise Refused("The first name comes first.")
    ss.you(name["first"], name.get("full") or name["first"], (a.get("work") or {}).get("value") or "",
           (a.get("areas") or {}).get("value") or ())


def _people(ss, entries):
    import settings_page
    saved, says = settings_page.save({"settings": {"group": "filter", "values": {"always_through": entries}}})
    if not saved:
        raise Refused(says)


def _since(value):
    try:
        d = dt.date.fromisoformat(str(value))
    except ValueError:
        raise Refused("Give the date as year-month-day, for example 2026-09-01.")
    if d > dt.date.today():
        raise Refused("That date is in the future. Reading back needs a day in the past.")
    return d.isoformat()


def apply(ss, rec, q, value):
    if q in NOT_ASKED:
        raise Refused(NOT_ASKED_SAYS)
    if q not in ORDER and q not in LATER:
        raise Refused(f"There is no question called '{q}'.")
    if q == "name":
        if not isinstance(value, dict) or not str(value.get("first") or "").strip():
            raise Refused("A first name is needed.")
        value = {"first": str(value["first"]).strip(), "full": str(value.get("full") or value["first"]).strip()}
        _you(ss, rec, name=value)
    elif q == "work":
        value = str(value or "").strip()
        if not value:
            raise Refused("A sentence or two about what you do is needed.")
        _you(ss, rec, work=value)
    elif q == "areas":
        value = _list(value, q)
        _you(ss, rec, areas=value)
    elif q == "audit":
        left = [f["id"] for f in (ss.common.read_json(audit_path(ss), None) or {}).get("findings") or [] if not f.get("decided")]
        if value and left:
            raise Refused("Still to decide: " + ", ".join(left) + ".")
        value = bool(value)
    elif q in ("accounts", "projects"):
        value = bool(value)                         # "that is all for now"; the accounts and projects live in their own lists
    elif q == "calendars":
        value = _list(value, q)
        ss.show_calendars(value)
    elif q == "people":
        value = _list(value, q)
        _people(ss, value)
    elif q == "matters":
        value = _list(value, q)
        ss.what_matters(value)
    elif q == "since":
        value = _since(value)
    elif q == "readback":
        if not isinstance(value, dict):
            raise Refused("Record the reading back as what happened.")
    elif q == "page":
        if value not in ("this_pc", "anywhere"):
            raise Refused("Choose this_pc or anywhere.")
        ss.set_hosting("own_pc")
        if value == "anywhere" and ss.reach().get("how") != "tailscale":
            raise Refused("Reaching the page from anywhere is not switched on yet. Do the Tailscale steps first.")
        if value == "this_pc" and ss.reach().get("how") == "tailscale":
            ss.reach_off(say=lambda *_: None)
    elif q == "sending":
        if not isinstance(value, bool):
            raise Refused("Choose yes or no.")
        ss.allow(value)
    elif q == "standing_sends":
        value = _list(value, q)
        if value and not rec["answers"].get("sending", {}).get("value"):
            raise Refused("Sending is switched off, so there is nothing to approve ahead. Answer the sending question with yes first.")
        standing = os.path.join(ss.common.PERSONAL, "standing_sends.json")
        ss.common.write_json(standing, {"about": "Kinds of email the owner approved ahead, in their own words. "
                                                 "Each send under one is listed on the page.", "kinds": value})
    elif q == "turn_on":
        if not isinstance(value, bool):
            raise Refused("Choose yes or no.")
        if value and ss.job_names()[1] not in ss.tasks_on():      # the job is made by assistant.py turn-on, which keeps the install record
            raise Refused("The background part is not on yet. Switch it on first, then save this.")
    rec["answers"][q] = {"value": value, "at": now()}
    if q in rec["skipped"]:
        rec["skipped"].remove(q)
    save_record(ss, rec)
    return value


# --- the audit: what is already on this computer ------------------------------------------------------------
def audit_path(ss):
    return os.path.join(ss.common.PERSONAL, "audit.json")


def audit_ctx(ss):
    import setup_audit
    s = ss.common.settings()
    roots = [p for p in (os.environ.get("ASSISTANT_AUDIT_ROOTS") or "").split(os.pathsep) if p] or None
    return setup_audit.Ctx(os.path.dirname(ss.common.HOME), ss.common.HOME, own_jobs=ss.job_names(),
                           port=s.get("page_port") or getattr(ss, "FIRST_PORT", 47815),
                           claude_dir=os.environ.get("ASSISTANT_AUDIT_CLAUDE") or None, project_roots=roots)


def audit_scan(ss, **more):
    """Look (read only) and keep what was found, with any decision already made about the same thing."""
    import setup_audit
    got = ss.common.read_json(audit_path(ss), None) or {}
    before = {(f["kind"], f["where"]): f for f in got.get("findings") or []}
    found = setup_audit.scan(audit_ctx(ss), **more)
    for f in found:
        old = before.pop((f["kind"], f["where"]), None)
        if old and old.get("decided"):
            f.update({k: old[k] for k in ("decided", "done", "at") if k in old})
    kept = [f for f in before.values() if f.get("decided")]    # decided and since moved away: still on record
    allf = kept + found
    for i, f in enumerate(allf, 1):
        f["id"] = f"a{i}"
    ss.common.write_json(audit_path(ss), {"looked": now(), "findings": allf})
    return allf


def _free_port(start):
    import socket
    for n in range(start + 1, start + 200):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", n))
                return n
            except OSError:
                continue
    raise Refused("No free spot was found for your page.")


def audit_decide(ss, fid, choice):
    """Record the person's decision and carry it out. Call only after their yes to exactly this."""
    import setup_audit
    got = ss.common.read_json(audit_path(ss), None) or {}
    f = next((x for x in got.get("findings") or [] if x["id"] == fid), None)
    if not f:
        raise Refused(f"There is no finding {fid}. Look again first.")
    if choice not in f["choices"]:
        raise Refused(f"For this one the choices are: {', '.join(f['choices'])}.")
    done = "Left as it is."
    if choice == "remove":
        if f["kind"] in ("skill", "older"):
            import inuse
            try:
                inuse.refuse_if_used(f["where"])
            except inuse.InUse as e:
                raise Refused(str(e))
            where = f["where"]
            if os.path.isdir(where):
                shutil.rmtree(where)
            elif os.path.exists(where):
                os.remove(where)
            done = f"Deleted {where}."
        elif f["kind"] == "job":
            (getattr(ss, "audit_remove_job", None) or setup_audit.remove_job)(f["where"])
            done = f"Deleted the scheduled job \"{f['where']}\"."
        elif f["kind"] == "plugin":
            done = f"To be taken off by the person: /plugin uninstall {f['where']}."
        elif f["kind"] == "home":
            shutil.rmtree(ss.common.HOME)
            ss.make_home()
            done = "The earlier data was deleted; a fresh, empty one was made."
    elif choice == "change":
        if f["kind"] == "port":
            s = ss.common.settings()
            s["page_port"] = _free_port(int(f["where"]))
            ss.common.write_json(ss.common.SETTINGS, s)
            done = f"Your page now uses spot {s['page_port']}."
        else:
            done = "To be changed by the person, as shown."
    got = ss.common.read_json(audit_path(ss), None) or got     # a fresh home after "start fresh" has none
    if not any(x["id"] == fid for x in got.get("findings") or []):
        got = {"looked": now(), "findings": [f]}
    for x in got["findings"]:
        if x["id"] == fid:
            x.update(decided=choice, done=done, at=now())
    ss.common.write_json(audit_path(ss), got)
    return {"id": fid, "decided": choice, "done": done}


# --- changes to the program, undo, and updates meeting the owner's changes (CHANGES.md) --------------------
def change_book(ss):
    import setup_changes
    return setup_changes.Book(os.path.dirname(ss.common.HOME), ss.common.HOME)


def change_runner(ss, expect=""):
    import setup_changes
    made = getattr(ss, "change_runner", None)
    return made(expect) if made else setup_changes.default_runner(ss, expect)


def change_command(ss, a):
    import setup_changes
    import setup_update
    book, c = change_book(ss), a.cmd
    try:
        if c == "change-start":
            return {"ok": True, "change": book.start(a.asked)}
        if c == "change-agree":
            return {"ok": True, "change": book.agree(a.id, a.part, a.agreed, a.files)}
        if c == "change-go":
            return {"ok": True, "change": book.go(a.id, a.words)}
        if c == "change-edited":
            return dict(book.edited(a.id, a.result == "ok", a.why, change_runner(ss)), ok=True)
        if c == "change-check":
            return dict(book.check(a.id, change_runner(ss, a.expect)), ok=True)
        if c == "change-abandon":
            return dict(book.abandon(a.id, a.why, change_runner(ss)), ok=True)
        if c == "change-drop":
            return {"ok": True, "change": book.drop(a.id)}
        if c == "changes":
            o = book.open_one()
            return {"ok": True, "changes": book.listing(), "being_made": o["id"] if o else None}
        if c == "undo":
            return dict(book.undo(a.id, change_runner(ss), with_later=a.with_later, plan_only=a.plan), ok=True)
        work = os.path.join(ss.common.HOME, "changes", "update-work")
        if c == "update-sort":
            shipped = os.path.join(os.path.dirname(ss.common.HOME), "Shipped")
            got = setup_update.sort(book, shipped, a.new_root, work)
            ss.common.write_json(os.path.join(work, "sorted.json"), got)
            return {"ok": True, "changes": got}
        sorted_ = ss.common.read_json(os.path.join(work, "sorted.json"), None) or []
        saved_path = os.path.join(work, "decisions.json")
        saved = ss.common.read_json(saved_path, None) or {}
        if c == "update-show":
            return {"ok": True, "changes": sorted_, "decided": saved,
                    "still_to_decide": [x["id"] for x in sorted_ if x["kind"] != "untouched" and x["id"] not in saved]}
        if c == "update-decide":
            if a.id not in {x["id"] for x in sorted_}:
                raise Refused(f"Change {a.id} is not in this update's list. Sort the changes first.")
            saved[a.id] = a.decision
            ss.common.write_json(saved_path, saved)
            left = [x["id"] for x in sorted_ if x["kind"] != "untouched" and x["id"] not in saved]
            return {"ok": True, "decided": saved, "still_to_decide": left}
        decisions = _json(getattr(a, "decisions", ""), {}) or saved
        if c == "update-choices":
            path, pick = setup_update.choices(sorted_, decisions, work)
            return {"ok": True, "choices_file": path, "choices": pick}
        if c == "update-after":
            return {"ok": True, "changes": setup_update.after(book, sorted_, decisions, a.version)}
    except setup_changes.Refused as e:
        raise Refused(str(e))
    raise Refused(f"Unknown command {c}.")


# --- projects ------------------------------------------------------------------------------------------
def projects_path(ss):
    return os.path.join(ss.common.PERSONAL, "projects.json")


def projects(ss):
    got = ss.common.read_json(projects_path(ss), None)
    return got if isinstance(got, dict) and isinstance(got.get("projects"), list) else {
        "about": "Projects introduced to the assistant: what each sends in, and what goes back out.", "projects": []}


def project_add(ss, folder, name, brings_in, sends_out):
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        raise Refused(f"There is no folder at {folder}.")
    if not str(name or "").strip() or not str(brings_in or "").strip():
        raise Refused("A project needs a name and what it should bring in.")
    got = projects(ss)
    if any(os.path.normcase(p["folder"]) == os.path.normcase(folder) for p in got["projects"]):
        raise Refused("That project is already introduced. Change it instead.")
    got["projects"].append({"name": name.strip(), "folder": folder, "brings_in": brings_in.strip(),
                            "sends_out": (sends_out or "").strip(), "roadmap": False, "introduction": False,
                            "line": False, "changes": [], "since": now()})
    ss.common.write_json(projects_path(ss), got)
    return got["projects"][-1]


def project_change(ss, name, brings_in, sends_out):
    got, p = _project(ss, name)
    if not str(brings_in or "").strip():
        raise Refused("Say what should come in from this project.")
    p.update(brings_in=brings_in.strip(), sends_out=(sends_out or "").strip(), changed=now())
    ss.common.write_json(projects_path(ss), got)
    return p


def _project(ss, name):
    got = projects(ss)
    for p in got["projects"]:
        if p["name"].lower() == str(name).lower() or os.path.normcase(p["folder"]) == os.path.normcase(os.path.abspath(name)):
            return got, p
    raise Refused(f"No project called '{name}' has been introduced.")


def _changed(p, path, what, on):
    """Keep the list of every change made inside the project, so it can be listed and undone later."""
    p["changes"] = [c for c in p.get("changes") or [] if c["file"] != path]
    if on:
        p["changes"].append({"file": path, "what": what, "when": now()})


def project_roadmap(ss, name, on):
    got, p = _project(ss, name)
    (ss.apply_roadmap if on else ss.take_roadmap_off)(p["folder"])
    p["roadmap"] = bool(on)
    _changed(p, os.path.join(p["folder"], "Roadmap page", "readers.json"), "the assistant listed as a reader of the roadmap", on)
    ss.common.write_json(projects_path(ss), got)
    return p


def roadmap_writer_state(folder):
    """For a roadmap just connected: whether its plain copy is written yet, and the project's Roadmap writer session (its
    local id, as the project's roadmap setup recorded it), so the connecting session can ask it to write the copy now."""
    try:
        with open(os.path.join(folder, ".claude", "roadmap", "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = {}
    cfg = cfg if isinstance(cfg, dict) else {}
    w = cfg.get("writer") if isinstance(cfg.get("writer"), dict) else {}
    return {"has_plain_copy": os.path.isfile(os.path.join(folder, "Roadmap page", "roadmap.json")),
            "writer_session": str(w.get("session_id") or ""), "has_roadmap": bool(cfg)}


def _intro_dir(p):
    return os.path.join(p["folder"], ".assistant")


def intro_text(p):
    lines = ["# This project is introduced to a personal assistant", "",
             f"Agreed on {now()[:10]}, in the owner's words.", "",
             f"What should reach the assistant: {p['brings_in']}", "",
             "When that happens here, leave one note for the assistant: a new small file in the `outbox` folder beside "
             "this one, named for the time and a few words (for example `2026-11-16 0930 order 1182.json`), holding one JSON "
             'object: {"kind": "...", "title": "one line, what it is", "text": "what is wanted and by when", "when": "<date and time>"}.',
             "Write one note per thing. Never change or remove a note already in `outbox`; the assistant moves each one to "
             "`outbox/done` when it has made a card of it."]
    if p.get("sends_out"):
        lines += ["", f"What the assistant sends back: {p['sends_out']}. It arrives as files in the `from-assistant` folder beside "
                      "this one. Read any new ones at the start of work here."]
    else:
        lines += ["", "The assistant sends nothing back to this project."]
    return "\n".join(lines) + "\n"


def project_intro(ss, name, on, show_only=False):
    """The project's own .assistant folder: what was agreed (introduction.md) and the outbox for its notes."""
    got, p = _project(ss, name)
    folder = _intro_dir(p)
    path = os.path.join(folder, "introduction.md")
    if show_only:
        return {"file": path, "text": intro_text(p)}
    if on:
        os.makedirs(os.path.join(folder, "outbox"), exist_ok=True)
        if p.get("sends_out"):
            os.makedirs(os.path.join(folder, "from-assistant"), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(intro_text(p))
        said = "Added."
    else:
        if p.get("line"):
            raise Refused("Take the line out of that project's instructions first; it points to the introduction.")
        if os.path.exists(path):
            os.remove(path)
        notes = []
        for d in ("outbox", "from-assistant"):
            sub = os.path.join(folder, d)
            notes += [n for n in (os.listdir(sub) if os.path.isdir(sub) else []) if n != "done"]
            done = os.path.join(sub, "done")
            notes += os.listdir(done) if os.path.isdir(done) else []
        if os.path.isdir(folder) and not notes:
            shutil.rmtree(folder)
        said = "Taken out, except notes already written, which stay in that project." if notes else "Taken out."
    p["introduction"] = bool(on)
    _changed(p, folder, "a folder .assistant with introduction.md and an outbox", on)
    ss.common.write_json(projects_path(ss), got)
    return {"file": path, "on": bool(on), "says": said}


LINE = "This project is introduced to a personal assistant: read .assistant/introduction.md and do what it says."


def project_line(ss, name, on, show_only=False):
    """One line in the project's CLAUDE.md pointing its Claude at the introduction. The rest of the file is untouched."""
    got, p = _project(ss, name)
    path = os.path.join(p["folder"], "CLAUDE.md")
    if show_only:
        return {"file": path, "text": LINE}
    if on and not p.get("introduction"):
        raise Refused("Add the introduction first; this line points to it.")
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    new = "\n".join(ln for ln in old.split("\n") if ln.strip() != LINE)
    if on:
        new = (new.rstrip("\n") + "\n\n" if new.strip() else "") + LINE + "\n"
    elif old.endswith(LINE + "\n"):
        new = new.rstrip("\n") + "\n"
    if new != old and (os.path.exists(path) or new.strip()):
        with open(path, "w", encoding="utf-8", newline="\n") as f:      # edited in place, the rest kept as it was
            f.write(new)
    p["line"] = bool(on)
    _changed(p, path, "one line: " + LINE, on)
    ss.common.write_json(projects_path(ss), got)
    return {"file": path, "on": bool(on)}


def project_remove(ss, name):
    got, p = _project(ss, name)
    if p.get("roadmap") or p.get("introduction") or p.get("line"):
        raise Refused("Take off what was added to that project first, each with its own yes: its roadmap on the page, the introduction, the line.")
    got["projects"] = [x for x in got["projects"] if x is not p]
    ss.common.write_json(projects_path(ss), got)
    return p


# --- accounts ------------------------------------------------------------------------------------------
def ask_secret(label, help_text=""):
    """A small window with one hidden box, so a key never passes through the chat or a log."""
    import tkinter as tk
    from tkinter import simpledialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    got = simpledialog.askstring("Your assistant", f"{label}\n\n{help_text}\n\nPaste it here. It shows as dots.", show="•", parent=root)
    root.destroy()
    return (got or "").strip()


def account_kinds(ss):
    """The kinds of account the assistant can read. Claude's ready-made connections are listed first, but only
    when the engine says it can read through them in the background (ready_made_kinds); until then none are."""
    ready = getattr(ss, "ready_made_kinds", None)
    out = [dict(k, ready_made=True) for k in (ready() if ready else [])]
    return out + [{"type": t, "name": n, "kind": k, "needs_registration": bool(ss.registration_asks(t)), "ready_made": False}
                  for t, n, k, _ in ss.connection_types()]


def connect_ready(ss, type_name):
    """Connect one of Claude's ready-made connections (already switched on by the person on claude.ai) and read it
    once to check. Only when the engine can read through them in the background."""
    fn = getattr(ss, "connect_ready", None)
    if fn is None:
        raise NotYet("Your assistant cannot read through Claude's ready-made connections yet.")
    return fn(type_name)


def connect(ss, type_name, answers):
    rec = record(ss)
    rec["pending_account"] = {"type": type_name, "since": now()}
    save_record(ss, rec)
    reg = ss.registration_asks(type_name)
    if reg:
        got = {}
        for a in reg:
            got[a["key"]] = ask_secret(a["label"], a.get("help", "")) if a.get("secret") else answers.get(a["key"], "")
        ss.save_registration(type_name, got)
    for a in ss.connection_asks(type_name):
        if a.get("secret") and not answers.get(a["key"]):
            answers[a["key"]] = ask_secret(a["label"], a.get("help", ""))
    said = []
    conn = ss.add_connection(type_name, answers, say=said.append, conn_id=answers.pop("id", None))
    checked = [c for c in ss.check_connections() if c[0] == (conn.get("label") or conn["id"])]
    rec = record(ss)
    rec["pending_account"] = None
    save_record(ss, rec)
    ok = bool(checked and checked[0][1])
    return {"id": conn["id"], "label": conn.get("label") or conn["id"], "works": ok,
            "check": checked[0][2] if checked else "not checked", "said": said}


# --- reading back ----------------------------------------------------------------------------------------
def cards(ss):
    """The rest of setup moves to the page: the welcome card is made (onboard.begin), and the questions the cards ask are
    marked as asked there, so the interview goes on to what only the computer can do (the page, sending, switching on)."""
    ss.make_home()
    import onboard
    onboard.begin()
    rec = record(ss)
    for q in ON_CARDS:
        if q not in rec["answers"] and q not in rec["skipped"]:
            rec["answers"][q] = {"value": CARDS_MARK, "at": now()}
    rec["cards"] = now()
    save_record(ss, rec)
    return dict(progress(ss), cards=onboard.state().get("begun"))


def catalog_back(ss, since):
    """The look-back: catalog the envelopes of past messages back to `since` (catalog.py), and nothing more. Nothing is read or
    made into cards; new messages are then given context from it. The voice guide is built from it as on the setup cards."""
    ss.make_home()
    import catalog
    catalog.start(dt.date.fromisoformat(since))
    return {"since": since, "catalog": "started"}


def readback(ss, since, estimate_only):
    fn = getattr(ss, "read_back", None)
    if fn is None:
        raise NotYet("The assistant's program cannot read back to a chosen date yet.")
    return fn(since, estimate_only=estimate_only)


def _json(text, default):
    """A value as JSON; a place on the computer written with single backslashes is read as forward slashes."""
    if not text:
        return default
    if re.search(r"[A-Za-z]:\\", text):          # C:\... written with backslashes: read every run of them as /
        text = re.sub(r"\\+", "/", text)
    try:
        return json.loads(text)
    except ValueError:
        if text.lstrip()[:1] in "{[":                # a list or record whose quote marks were stripped on the way
            raise Refused("That answer lost its quote marks on the way, so nothing was saved. "
                          "Run this helper command with the Bash tool, never PowerShell.")
        return text


# --- the command line ----------------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", help="the assistant's folder (default Documents/Assistant); its program and data are inside")
    ap.add_argument("--engine")
    ap.add_argument("--home")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("folder-check"); s.add_argument("folder", nargs="?")
    sub.add_parser("where")
    sub.add_parser("ready")
    sub.add_parser("install-parts")
    sub.add_parser("start")
    sub.add_parser("progress")
    s = sub.add_parser("show"); s.add_argument("question", nargs="?")
    s = sub.add_parser("answer"); s.add_argument("question"); s.add_argument("value", help="JSON")
    s = sub.add_parser("skip"); s.add_argument("question")
    s = sub.add_parser("change-start"); s.add_argument("asked")
    s = sub.add_parser("change-agree"); s.add_argument("id"); s.add_argument("part"); s.add_argument("agreed"); s.add_argument("files", nargs="+")
    s = sub.add_parser("change-go"); s.add_argument("id"); s.add_argument("words")
    s = sub.add_parser("change-edited"); s.add_argument("id"); s.add_argument("result", choices=("ok", "fail")); s.add_argument("why", nargs="?", default="")
    s = sub.add_parser("change-check"); s.add_argument("id"); s.add_argument("--expect", default="")
    s = sub.add_parser("change-abandon"); s.add_argument("id"); s.add_argument("why", nargs="?", default="")
    s = sub.add_parser("change-drop"); s.add_argument("id")
    sub.add_parser("changes")
    s = sub.add_parser("undo"); s.add_argument("id"); s.add_argument("--with-later", action="store_true"); s.add_argument("--plan", action="store_true")
    s = sub.add_parser("update-sort"); s.add_argument("new_root")
    sub.add_parser("update-show")
    s = sub.add_parser("update-decide"); s.add_argument("id"); s.add_argument("decision", help="built in | keep | drop | a combination file")
    s = sub.add_parser("update-choices"); s.add_argument("decisions", nargs="?", default="", help="JSON; default: the decisions saved so far")
    s = sub.add_parser("update-after"); s.add_argument("version"); s.add_argument("decisions", nargs="?", default="")
    sub.add_parser("audit")
    s = sub.add_parser("audit-decide"); s.add_argument("id"); s.add_argument("choice", choices=("keep", "change", "remove"))
    sub.add_parser("account-kinds")
    s = sub.add_parser("account-steps"); s.add_argument("type")
    s = sub.add_parser("connect-ready"); s.add_argument("type")
    s = sub.add_parser("connect"); s.add_argument("type"); s.add_argument("answers", nargs="?", default="{}", help="JSON of plain answers")
    sub.add_parser("accounts")
    sub.add_parser("check-accounts")
    s = sub.add_parser("remove-account"); s.add_argument("id")
    sub.add_parser("calendar-choices")
    sub.add_parser("projects")
    s = sub.add_parser("project-add"); s.add_argument("folder"); s.add_argument("name"); s.add_argument("brings_in"); s.add_argument("sends_out", nargs="?", default="")
    s = sub.add_parser("project-change"); s.add_argument("name"); s.add_argument("brings_in"); s.add_argument("sends_out", nargs="?", default="")
    s = sub.add_parser("project-roadmap"); s.add_argument("name"); s.add_argument("on", choices=("on", "off"))
    s = sub.add_parser("project-intro"); s.add_argument("name"); s.add_argument("on", choices=("show", "on", "off"))
    s = sub.add_parser("project-line"); s.add_argument("name"); s.add_argument("on", choices=("show", "on", "off"))
    s = sub.add_parser("project-remove"); s.add_argument("name")
    s = sub.add_parser("catalog"); s.add_argument("since")
    s = sub.add_parser("readback-estimate"); s.add_argument("since")
    s = sub.add_parser("readback"); s.add_argument("since")
    sub.add_parser("reach-status")
    sub.add_parser("reach-on")
    sub.add_parser("reach-off")
    sub.add_parser("reach-check")
    sub.add_parser("open-page")
    sub.add_parser("voice-build")                    # the Writing style builder's steps (setup_texts/voice.md), as the page's chat runs them
    sub.add_parser("voice-show")
    s = sub.add_parser("voice-correct"); s.add_argument("part"); s.add_argument("items", nargs="?", default="[]", help="JSON list")
    s = sub.add_parser("voice-level"); s.add_argument("level")
    sub.add_parser("finish")
    sub.add_parser("cards")                          # the rest of setup on the page, as cards (onboard.py)
    a = ap.parse_args(argv)
    if a.cmd == "folder-check":                       # before anything is laid down: no program needed
        import setup_audit
        target = a.folder or a.root or setup_audit.documents_folder()
        name, why = setup_audit.synced(target)
        real = os.path.realpath(target)
        exists = os.path.isdir(real)
        out = {"ok": True, "folder": real, "synced": bool(name), "service": name, "why": why,
               "exists": exists, "empty": (not exists) or not os.listdir(real),
               "holds_assistant": os.path.isdir(os.path.join(real, "System", "live")) or os.path.isdir(os.path.join(real, "Live", "personal")),
               "other_things": sorted(n for n in (os.listdir(real) if exists else [])
                                      if n not in ("System", "Live", "Shipped", "docs", "desktop.ini") and not n.startswith("."))[:10],
               "documents": setup_audit.documents_folder(), "safe": setup_audit.SAFE_DEFAULT,
               "safe_synced": bool(setup_audit.synced(setup_audit.SAFE_DEFAULT)[0])}
        print(json.dumps(out, ensure_ascii=False))
        return 0
    try:
        ss = load_engine(a.engine, a.home, a.root)
        out = run(ss, a)
        code = 0
    except Refused as e:
        out, code = {"ok": False, "says": str(e)}, 2
    except NotYet as e:
        out, code = {"ok": False, "not_yet": True, "says": str(e)}, 3
    except Exception as e:  # noqa: BLE001  a failure is said plainly, with no key in it
        text = f"{type(e).__name__}: {e}"
        try:
            import keys
            text = keys.scrub(text)
        except Exception:  # noqa: BLE001
            pass
        out, code = {"ok": False, "says": "Something went wrong: " + text[:400]}, 1
    print(json.dumps(out, default=str, ensure_ascii=False))
    return code


def run(ss, a):
    c = a.cmd
    if c in ("voice-build", "voice-show", "voice-correct", "voice-level"):
        import tools                                 # the same step the page's chat runs, with the same read-back
        rest = [a.part, a.items] if c == "voice-correct" else [a.level] if c == "voice-level" else []
        said = tools._voice_step(c, rest)
        try:
            return json.loads(said)
        except ValueError:
            return {"ok": False, "says": said}
    if c == "where":
        return {"ok": True, "engine": ss.common.HERE, "home": ss.common.HOME, "home_made": os.path.isdir(ss.common.PERSONAL)}
    if c == "ready":
        return {"ok": True, "missing_parts": ss.parts_missing(), "claude": bool(ss.claude_ready())}
    if c == "install-parts":
        said = []
        ss.install_parts(say=said.append)
        return {"ok": not ss.parts_missing(), "said": said}
    if c == "start":
        ss.make_home()
        rec = record(ss)
        save_record(ss, rec)
        return dict(progress(ss), ok=True, home=ss.common.HOME)
    if c == "progress":
        return dict(progress(ss), ok=True)
    if c == "cards":
        return dict(cards(ss), ok=True)
    rec = record(ss)
    if c == "show":
        if a.question:
            return {"ok": True, "question": a.question, "answer": rec["answers"].get(a.question)}
        return {"ok": True, "answers": rec["answers"], "skipped": rec["skipped"], "accounts": ss.connected(),
                "projects": projects(ss)["projects"], "page": ss.reach(), "page_address": ss.local_page_address(), "sending": ss.allowed(), "jobs_on": ss.tasks_on()}
    if c == "answer":
        value = _json(a.value, a.value)
        v = apply(ss, rec, a.question, value)
        return dict(progress(ss), ok=True, saved={a.question: v})
    if c == "skip":
        if a.question in NOT_ASKED:                 # not asked any more: nothing to skip, nothing saved
            return dict(progress(ss), ok=True)
        if a.question not in OPTIONAL:
            raise Refused(f"'{a.question}' cannot be skipped.")
        rec["answers"].pop(a.question, None)
        if a.question not in rec["skipped"]:
            rec["skipped"].append(a.question)
        save_record(ss, rec)
        return dict(progress(ss), ok=True)
    if c.startswith("change") or c in ("undo",) or c.startswith("update-"):
        return change_command(ss, a)
    if c == "audit":
        found = audit_scan(ss)
        return {"ok": True, "findings": found, "undecided": [f["id"] for f in found if not f.get("decided")]}
    if c == "audit-decide":
        return dict(audit_decide(ss, a.id, a.choice), ok=True)
    if c == "account-kinds":
        return {"ok": True, "kinds": account_kinds(ss)}
    if c == "account-steps":
        return {"ok": True, "steps": ss.connections.module(a.type).SETUP}
    if c == "connect-ready":
        return dict(connect_ready(ss, a.type), ok=True)
    if c == "connect":
        return dict(connect(ss, a.type, _json(a.answers, {}) if isinstance(_json(a.answers, {}), dict) else {}), ok=True)
    if c == "accounts":
        return {"ok": True, "accounts": [{"id": i, "kind": k, "label": l} for i, k, l in ss.connected()]}
    if c == "check-accounts":
        return {"ok": True, "checks": [{"label": l, "works": w, "says": s} for l, w, s in ss.check_connections()]}
    if c == "remove-account":
        ss.remove_connection(a.id)
        return {"ok": True, "accounts": ss.connected()}
    if c == "calendar-choices":
        return {"ok": True, "calendars": ss.calendar_choices()}
    if c == "projects":
        return {"ok": True, "projects": projects(ss)["projects"]}
    if c == "project-add":
        return {"ok": True, "project": project_add(ss, a.folder, a.name, a.brings_in, a.sends_out)}
    if c == "project-change":
        return {"ok": True, "project": project_change(ss, a.name, a.brings_in, a.sends_out)}
    if c == "project-roadmap":
        p = project_roadmap(ss, a.name, a.on == "on")
        return {"ok": True, "project": p, "roadmap": roadmap_writer_state(p["folder"]) if a.on == "on" else None}
    if c == "project-intro":
        return dict(project_intro(ss, a.name, a.on == "on", show_only=a.on == "show"), ok=True)
    if c == "project-line":
        return dict(project_line(ss, a.name, a.on == "on", show_only=a.on == "show"), ok=True)
    if c == "project-remove":
        return {"ok": True, "removed": project_remove(ss, a.name)}
    if c == "catalog":
        return dict(catalog_back(ss, _since(a.since)), ok=True)
    if c in ("readback-estimate", "readback"):
        return dict(readback(ss, _since(a.since), c == "readback-estimate"), ok=True)
    if c == "reach-status":
        return dict(ss.reach_status(), ok=True)
    if c in ("reach-on", "reach-off"):
        said = []
        (ss.reach_on if c == "reach-on" else ss.reach_off)(say=said.append)
        return {"ok": True, "said": said, "reach": ss.reach()}
    if c == "reach-check":
        return {"ok": True, "result": ss.reach_check()}
    if c == "open-page":
        said = []
        ss.open_local_page(say=said.append)
        return {"ok": True, "said": said, "address": ss.local_page_address()}
    if c == "finish":
        missing = [q for q in ORDER if q not in rec["answers"] and q not in rec["skipped"]
                   and not (q == "calendars" and not has_calendar(ss))]
        if missing:
            raise Refused("Not finished: " + ", ".join(missing) + " still waits.")
        rec["finished"] = now()
        save_record(ss, rec)
        return {"ok": True, "finished": rec["finished"]}
    raise Refused(f"Unknown command {c}.")


if __name__ == "__main__":
    sys.exit(main())
