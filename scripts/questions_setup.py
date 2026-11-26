r"""The questions file for a project: turned on or off by the person, from a Claude session open in the project folder. Each
session that turns it on has its own file; the first keeps Questions.md, each further one gets "Questions - <session title>.md".

    python questions_setup.py on --title "<session title>"
                                        turn it on for this session: its file is made if it is not there ("No open questions.")
                                        and named in the output; the plugin's hook records this session as its owner
    python questions_setup.py off --this-session
                                        turn it off for this session only (the hook takes its file out of the record; the
                                        file stays as it is); with no session left the project's checks stop
    python questions_setup.py off --session <session id>
                                        turn it off for the one session with that id (the page's Remove questions file, where the
                                        person chose the session): its file stays as it is, other sessions' files are untouched,
                                        and with no session left the project's checks stop
    python questions_setup.py off       turn it off for the whole project; every file stays as it is
    python questions_setup.py status    whether it is on, which sessions have files, and how many questions are open in each
    python questions_setup.py roadmap [--file "<file name>"]
                                        in a project with a roadmap: saves the one database write that copies this file, as
                                        written, to the roadmap page (board/questions-file--<session id>), and, when a reader
                                        keeps the full copy, the patch for it. Run after each turn the file changed. The page
                                        shows it; answers are given in chat or under the copy there. With no roadmap it says so and changes nothing.

Sessions are recorded by their local_... id (it survives app restarts); an older record by the session's own id is moved to
the local id the next time that session is seen.
The setting is <project>\.claude\questions\config.json. A project that never ran "on" is untouched by the questions hooks.
Run from the project folder (or give --project <folder>). No file is ever deleted. In a project with a roadmap, "off" also
saves the deletes that take the turned-off files' copies off the roadmap page ("writes_file", as "roadmap" does).
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

FILE = "Questions.md"
EMPTY = ("# Questions\n\n"
         "Answer in chat by number and letter, for example \"1b\", or in your own words.\n\nNo open questions.\n")
ENTRY = re.compile(r"^(\d+)\.\s+(.*\S)", re.M)


def config_path(project):
    return os.path.join(project, ".claude", "questions", "config.json")


def read(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def open_questions(project, fname=FILE):
    try:
        with open(os.path.join(project, fname), encoding="utf-8") as f:
            return [m.group(2) for m in ENTRY.finditer(f.read())]
    except OSError:
        return []


def sessions_of(cfg):
    got = dict(cfg.get("sessions") or {})
    if not got and cfg.get("main_session_id"):
        got[cfg["main_session_id"]] = FILE
    return got


def file_for(project, cfg, title):
    """Questions.md when no session has it, else "Questions - <title>.md" (a number added when that name is taken)."""
    claimed = set(sessions_of(cfg).values())
    if FILE not in claimed:
        return FILE
    clean = " ".join(re.sub(r'[<>:"/\|?*]', " ", title or "").split())
    if len(clean) > 60:                                         # cut at a word, never inside one
        clean = clean[:61].rsplit(" ", 1)[0] if " " in clean[:61] else clean[:60]
    clean = clean.strip(" .") or "session"
    name, n = f"Questions - {clean}.md", 1
    while name in claimed:
        n += 1
        name = f"Questions - {clean} {n}.md"
    return name


def sessions_dir():
    return os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude"), "sessions")


def session_name(key):
    """The name the app shows for the session recorded as key (its local_... id, or an older record's own id), or ""."""
    try:
        listed = os.listdir(sessions_dir())
    except OSError:
        return ""
    for f in listed:
        if f.endswith(".json"):
            d = read(os.path.join(sessions_dir(), f), {})
            if isinstance(d, dict) and key in (d.get("hostSessionId"), d.get("sessionId")):
                return " ".join(str(d.get("name") or "").split())
    return ""


def doc_id(key):
    return "questions-file--" + (re.sub(r"[^A-Za-z0-9._-]", "", key)[:100] or "first")


def full_copy_kept(project):
    got = read(os.path.join(project, "Roadmap page", "readers.json"), {})
    listed = got.get("readers") if isinstance(got, dict) else None
    return isinstance(listed, dict) and any(isinstance(v, dict) and v.get("full") is True for v in listed.values())


def save_writes(project, writes, out, dest=""):
    """Saves the database writes to make and names them (and, when a reader keeps the full copy, the patch for it) in out."""
    dest = dest or os.path.join(os.environ.get("TEMP") or os.environ.get("TMPDIR") or project, "questions-roadmap-writes.json")
    write(dest, {"writes": writes})
    out["writes_file"] = dest
    if full_copy_kept(project):
        out["full_patch"] = f'python "${{CLAUDE_PLUGIN_DATA}}/scripts/roadmap_setup.py" full-patch "{dest}"'


def roadmap_sync(project, cfg, a):
    """The questions file copied to the roadmap: see the module's notes for "roadmap"."""
    road = read(os.path.join(project, ".claude", "roadmap", "config.json"), {})
    if not road.get("page_url"):
        print(json.dumps({"ok": True, "roadmap": False, "says": "This project has no roadmap; the questions file works on its own."}))
        return 0
    got = sessions_of(cfg)
    name = a.file or (sorted(set(got.values()))[0] if len(set(got.values())) == 1 else FILE)
    path = os.path.join(project, name)
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        print(json.dumps({"ok": False, "says": f"There is no {name} in this project. Nothing was changed."}))
        return 1
    key = next((k for k, v in got.items() if v == name), "")
    title = (session_name(key) if key else "") or (cfg.get("titles") or {}).get(name) or a.title or os.path.splitext(name)[0]
    changed = dt.datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="minutes")
    data = {"session": key, "session_name": title, "file": name, "text": text, "open": len(ENTRY.findall(text)), "changed": changed}
    out = {"ok": True, "roadmap": True, "file": name, "open": data["open"], "doc_id": doc_id(key or name), "page_url": road["page_url"]}
    save_writes(project, [{"op": "set", "collection": "board", "doc_id": out["doc_id"], "data": data}], out, a.out)
    print(json.dumps(out, ensure_ascii=False))
    return 0


def off_write(project, keys, out):
    """In a project with a roadmap, the deletes that take these sessions' questions files off the page."""
    keys = [k for k in keys if k]
    if keys and read(os.path.join(project, ".claude", "roadmap", "config.json"), {}).get("page_url"):
        save_writes(project, [{"op": "delete", "collection": "board", "doc_id": doc_id(k)} for k in keys], out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=os.getcwd())
    ap.add_argument("--title", default="")
    ap.add_argument("--this-session", action="store_true")
    ap.add_argument("--session", default="")
    ap.add_argument("--file", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("cmd", choices=("on", "off", "status", "roadmap"))
    a = ap.parse_args(argv)
    project = os.path.abspath(a.project)
    cfg_path = config_path(project)
    cfg = read(cfg_path, {})
    if a.cmd == "roadmap":
        return roadmap_sync(project, cfg, a)
    if a.cmd == "on":
        name = file_for(project, cfg, a.title)
        if a.title:
            cfg.setdefault("titles", {})[name] = a.title
        qfile = os.path.join(project, name)
        made = False
        if not os.path.exists(qfile):
            with open(qfile, "w", encoding="utf-8", newline="\n") as f:
                f.write(EMPTY)
            made = True
        cfg.update(on=True, pending=name, turned_on=dt.datetime.now().isoformat(timespec="seconds"))
        write(cfg_path, cfg)
        print(json.dumps({"ok": True, "file": qfile, "name": name, "made": made, "open": len(open_questions(project, name)),
                          "says": (f"{name} made, with no open questions. " if made else f"{name} was already there and is kept as it is. ")
                                  + "The questions checks are on for this session, which writes that file only."}))
    elif a.cmd == "off":
        if a.session:
            got = sessions_of(cfg)
            if a.session not in got:                            # named by its other id: the app's own id or its local_... id
                for f in (os.listdir(sessions_dir()) if os.path.isdir(sessions_dir()) else []):
                    d = read(os.path.join(sessions_dir(), f), {}) if f.endswith(".json") else {}
                    ids = (d.get("sessionId"), d.get("hostSessionId")) if isinstance(d, dict) else ()
                    if a.session in ids:
                        a.session = next((i for i in ids if i in got), a.session)
            if a.session not in got:
                print(json.dumps({"ok": False, "says": "That session has no questions file in this project. Nothing was changed."}))
                return 1
            gone = got.pop(a.session)
            cfg["sessions"] = got
            if gone == FILE:
                cfg.pop("main_session_id", None)
            if not got:
                cfg["on"] = False
            write(cfg_path, cfg)
            out = {"ok": True, "says": "The questions checks are off for that session. Its file stays as it is; other sessions' files are untouched."}
            off_write(project, [a.session], out)
            print(json.dumps(out))
        elif a.this_session:
            out = {"ok": True, "says": "The questions checks are off for this session. Its file stays as it is; other sessions' files are untouched."}
            me = os.environ.get("CLAUDE_CODE_HOST_SESSION_ID", "")
            off_write(project, [me] if me in sessions_of(cfg) else [], out)
            print(json.dumps(out))
        else:
            cfg["on"] = False
            write(cfg_path, cfg)
            out = {"ok": True, "says": "The questions checks are off for this project. Every questions file stays as it is."}
            off_write(project, list(sessions_of(cfg)), out)
            print(json.dumps(out))
    else:
        got = sessions_of(cfg)
        print(json.dumps({"ok": True, "on": bool(cfg.get("on")), "sessions": got, "main_session": cfg.get("main_session_id"),
                          "pending": cfg.get("pending"),
                          "open": {n: len(open_questions(project, n)) for n in sorted(set(got.values()))}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
