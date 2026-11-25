r"""Projects introduced to the assistant: notes in, answers out, every write outside the home asked first.

`personal\projects.json` (written by the setup interview) lists the projects:
    {"projects": [{"name", "folder", "brings_in", "sends_out", "roadmap", "note", "since"}], "writes": [...]}

IN: a project's Claude drops one short note per event as a new .md file in `<home>\inbox\<project name>\`. Each pass turns
every new note into a card in that project's name (the first line is the header, the rest the story; the file is kept and
remembered, never read twice). A note is data: it shows on a card and nothing in it is ever done.

OUT: when the owner answers such a card and the project has `sends_out`, nothing is written yet. A card shows exactly the
file that would be made and where, and asks "Write it?". Only the owner's "Yes, write it" writes it, one file at a time: a new
.md file in `<project folder>\From the assistant\`, never over an existing file, never anywhere else. Every write (and the
folder, when it had to be made) is recorded in `projects.json` under "writes", so an uninstall can find and offer to remove it.
"""
import datetime as dt
import hashlib
import json
import os
import re

import common
import dates

FILE = os.path.join(common.PERSONAL, "projects.json")
INBOX = os.path.join(common.HOME, "inbox")
SEEN = os.path.join(common.HOME, "state", "inbox_seen.json")
OUT_DIR = "From the assistant"
NOTE_KEY = "live:project-"
WRITE_KEY = "live:projwrite-"
CHOICES = ("Yes, write it", "No, do not")
BIGGEST_NOTE = 40000


def _data():
    got = common.read_json(FILE, {}) or {}
    return got if isinstance(got, dict) else {}


def projects():
    return [p for p in _data().get("projects") or [] if isinstance(p, dict) and str(p.get("name") or "").strip() and str(p.get("folder") or "").strip()]


def project(name):
    return next((p for p in projects() if p["name"] == name), None)


def names():
    return [p["name"] for p in projects()]


def slug(text, most=40):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:most] or "note"


def _safe_name(text):
    return re.sub(r"[^A-Za-z0-9 ._-]+", "", str(text)).strip()[:60] or "note"


# --- in ----------------------------------------------------------------------------------------------------------
def read_notes(pass_id):
    """Every new note in the inbox becomes a card. Returns how many cards were made."""
    import items
    items.ensure()
    seen = common.read_json(SEEN, {}) or {}
    files = seen.get("files") if isinstance(seen.get("files"), dict) else {}
    made = 0
    for p in projects():
        if not p.get("brings_in"):
            continue
        folder = os.path.join(INBOX, _safe_name(p["name"]))
        if not os.path.isdir(folder):
            continue
        for fn in sorted(os.listdir(folder)):
            path = os.path.join(folder, fn)
            if not fn.lower().endswith(".md") or not os.path.isfile(path) or path in files:
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read(BIGGEST_NOTE)
                when = dt.datetime.fromtimestamp(os.path.getmtime(path))
            except OSError:
                continue
            lines = [ln.rstrip() for ln in text.splitlines()]
            first = next((ln for ln in lines if ln.strip()), "")
            header = re.sub(r"^#+\s*", "", first).strip() or os.path.splitext(fn)[0]
            body = "\n".join(lines[lines.index(first) + 1:]).strip() if first in lines else ""
            key = NOTE_KEY + slug(p["name"], 20) + "-" + hashlib.sha1(path.encode("utf-8")).hexdigest()[:10]
            items.upsert(key, pass_id, kind="task", area=p["name"], state="yours", status=None,
                         title=dates.store(header, when.date()), detail=dates.store(body, when.date()) or None,
                         asks=["Read it, then answer or press Done."], why=f"{p['name']} sent this note.", source_who=p["name"], source_when=when,
                         source_ref=f"{p['name']}, a note, {when.month}/{when.day} {when.strftime('%I:%M %p').lstrip('0')}",
                         extra={"project": {"name": p["name"], "note": fn, "sends_out": bool(p.get("sends_out"))}})
            files[path] = when.isoformat(timespec="seconds")
            made += 1
    if made:
        common.write_json(SEEN, {"files": files})
    return made


# --- out: asked first, one file at a time -------------------------------------------------------------------------
def _target(p, header, when):
    """(the folder, the file path) for one answer. Built here from fixed parts, never from the note's words."""
    folder = os.path.realpath(p["folder"])
    out = os.path.join(folder, OUT_DIR)
    return out, os.path.join(out, f"{when:%Y-%m-%d %H%M%S} {_safe_name(header)[:40]}.md")


def after_answer(item, rec):
    """The owner answered a project card. Returns the card that ASKS to write the answer into the project, or None.
    Nothing is written here."""
    import items
    extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
    info = extra.get("project") if isinstance(extra.get("project"), dict) else None
    words = str(rec.get("text") or "").strip()
    if not info or not words or words.startswith("{"):
        return None
    p = project(info.get("name"))
    if not p or not p.get("sends_out") or not os.path.isdir(os.path.realpath(p["folder"])):
        return None
    when = common.now()
    header = str(item.get("title") or "an answer")
    out_dir, path = _target(p, header, when)
    content = (f"# Answer to: {header}\n\n{words}\n\n(From {common.owner()}, {when.month}/{when.day}/{when:%y} {when.strftime('%I:%M %p').lstrip('0')}. "
               f"Written by the assistant with their yes.)\n")
    made_dir = not os.path.isdir(out_dir)
    iid, _ = items.upsert(f"{WRITE_KEY}{item['id']}-{when:%H%M%S}", "answer", kind="question", area=p["name"], state="question", status=None,
                          title=f"Write your answer into {p['name']}'s folder?",
                          detail=(f"Nothing is written unless you say yes. If you do, this is what happens, once:\n"
                                  f"- A new file is made: {path}\n" + (f"- The folder \"{OUT_DIR}\" is made first, inside the project's folder.\n" if made_dir else "")
                                  + f"- Nothing else in the project is touched.\n\nThe file would say:\n\n{content}"),
                          asks=["Write it?"], why=f"You answered a note from {p['name']}.", source_who=p["name"], source_when=when,
                          extra={"write": {"project": p["name"], "path": path, "content": content, "folder_made": made_dir}})
    return iid


def write(item):
    """The owner said yes. Make the file. Returns (ok, plain words). Records it for an uninstall."""
    extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
    w = extra.get("write") if isinstance(extra.get("write"), dict) else None
    p = project((w or {}).get("project"))
    if not w or not p:
        return False, "That project is not set up any more, so nothing was written."
    folder = os.path.realpath(p["folder"])
    out_dir = os.path.join(folder, OUT_DIR)
    path = os.path.realpath(str(w.get("path") or ""))
    if not os.path.isdir(folder) or os.path.dirname(path) != os.path.realpath(out_dir) or not path.lower().endswith(".md"):
        return False, "The place to write is not the project's own folder for answers, so nothing was written."
    if os.path.exists(path):
        return False, "A file with that name is already there, so nothing was written over it."
    try:
        made_dir = not os.path.isdir(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        with open(path, "x", encoding="utf-8", newline="\n") as f:
            f.write(str(w.get("content") or ""))
    except OSError as e:
        return False, f"It could not be written ({type(e).__name__}), so nothing was changed."
    data = _data()
    data.setdefault("writes", []).append({"at": common.now().isoformat(timespec="seconds"), "project": p["name"], "path": path,
                                          "folder_made": out_dir if made_dir else None, "what": "an answer written with the owner's yes"})
    common.write_json(FILE, data)
    return True, f"Written: {path}"
