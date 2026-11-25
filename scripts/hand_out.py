r"""After an update: what each of the owner's other Claude sessions on this computer needs, and the message that hands it its step.

    python hand_out.py plan --root <assistant folder> [--sessions] [--here <local id>]
        --sessions: read the desktop app's session list (what list_sessions returns), saved as hand-out/sessions.json in
        the plugin's data folder. Without it, the projects the
        assistant knows stand in for sessions: the roadmap projects in its settings and the projects with a questions file.
        Prints JSON: "rows" (one per session that needs something: its line, its steps and the message to send it),
        "left" (steps for the person that no session can be sent), "ask" (the question to put, or none when nothing can
        be sent), and keeps the same as hand-out/plan.json there.
    python hand_out.py pick --answer "<the person's answer>"
        The rows to send, from the answer to the ask: 1 all, "2 <numbers>" those, anything else none. Prints JSON.

It sends nothing and changes nothing: the session running the update sends each chosen message itself, and only after the
person's yes. Every session needs a reload to pick up new commands and checks, which only the person can type in it; a
roadmap project's main session also brings its roadmap up to the plugin, after that reload, and reports back."""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RELOAD = "/reload-plugins"
QUESTIONS_REGISTRY = "questions-projects.json"


def read(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def norm(folder):
    return os.path.normcase(os.path.abspath(str(folder or "").rstrip("\\/") or "."))


def roadmaps(root):
    """[(folder, main session's local id or "")] for each roadmap project in the assistant's settings."""
    settings = read(os.path.join(root, "Live", "personal", "settings.json"), {}) or {}
    out = []
    for e in settings.get("roadmaps") or []:
        folder = e.get("folder") if isinstance(e, dict) else None
        if folder:
            cfg = read(os.path.join(folder, ".claude", "roadmap", "config.json"), {}) or {}
            out.append((folder, str(cfg.get("director_local_id") or "")))
    return out


def questions_projects(data):
    """Folders where the questions file is on, from the list the plugin's hook keeps as each is turned on."""
    listed = (read(os.path.join(data, QUESTIONS_REGISTRY), {}) or {}).get("projects") or []
    return [f for f in listed if (read(os.path.join(f, ".claude", "questions", "config.json"), {}) or {}).get("on")]


def message(steps, folder, here, data):
    """The words sent to one session."""
    skill = os.path.join(data, "skills", "roadmap-update", "SKILL.md").replace("\\", "/")
    where = data.replace("\\", "/")
    back = (" When it is done, or if it stops, send one line saying what happened to session " + here + " with SendMessage."
            if here else " When it is done, or if it stops, say in one line what happened.")
    if "roadmap" in steps:
        return ("The assistant plugin was just updated. This session has two steps. First, show the person this line and ask them "
                "to type it here themselves (only they can): " + RELOAD + " . After they have, bring this project's roadmap up to "
                "the plugin: read the file " + skill + " and follow it from step 1, as if the person had typed "
                "/assistant:roadmap-update; where it says ${CLAUDE_PLUGIN_DATA}, that is " + where + "." + back)
    return ("The assistant plugin was just updated. Show the person this one line and ask them to type it here themselves "
            "(only they can), so this session picks up the new commands and checks: " + RELOAD + " . Nothing else is needed in "
            "this session; do not report back.")


def row_line(n, title, folder, steps):
    what = "update its roadmap, after you reload it" if "roadmap" in steps else "reload"
    return f"{n}. {title}" + (f" ({folder})" if folder else "") + f": {what}"


def plan(root, sessions=None, here=None, data=None):
    data = data or os.path.dirname(HERE)
    maps = roadmaps(root)
    by_local = {lid: folder for folder, lid in maps if lid}
    rows, left = [], []
    if sessions is not None:
        seen = set()
        for s in sessions:
            sid = str(s.get("sessionId") or "")
            if not sid or s.get("isArchived") or sid == here:
                continue
            steps = ["reload"]
            folder = by_local.get(sid)
            if folder:
                steps = ["roadmap", "reload"]
                seen.add(sid)
            rows.append({"id": sid, "title": s.get("title") or "Untitled session", "folder": folder or s.get("cwd") or "",
                         "steps": steps, "sendable": True})
        for folder, lid in maps:
            if lid not in seen:
                left.append(f"{folder}: open its main session and type /assistant:roadmap-update"
                            + (" (its main session is not among the open sessions)" if lid else
                               " (the roadmap does not record which session is its main one)"))
    else:
        done = set()
        for folder, lid in maps:
            done.add(norm(folder))
            rows.append({"id": lid, "title": "The main session of " + os.path.basename(folder.rstrip("\\/")), "folder": folder,
                         "steps": ["roadmap", "reload"], "sendable": bool(lid)})
        for folder in questions_projects(data):
            if norm(folder) not in done:
                done.add(norm(folder))
                rows.append({"id": "", "title": "The sessions in " + os.path.basename(folder.rstrip("\\/")), "folder": folder,
                             "steps": ["reload"], "sendable": False})
    rows = [r for r in rows if r["steps"]]                      # a session that needs nothing is left out
    for n, r in enumerate(rows, 1):
        r["n"] = n
        r["line"] = row_line(n, r["title"], r["folder"], r["steps"])
        r["message"] = message(r["steps"], r["folder"], here, data) if r["sendable"] else None
        r["if_sent"] = (f"{r['title']}: sent; it updates its roadmap after you type {RELOAD} there, and reports back"
                        if "roadmap" in r["steps"] else f"{r['title']}: sent; left for you: type {RELOAD} there")
        r["if_not_sent"] = (f"{r['title']}: not sent; left for you: type {RELOAD} there"
                            + (", then /assistant:roadmap-update" if "roadmap" in r["steps"] else ""))
        if not r["sendable"]:
            left.append(r["if_not_sent"])
    can = [r for r in rows if r["sendable"]]
    ask = ("Send each of these sessions its step? 1 send each its step, 2 pick which (for example \"2 1,3\"), 3 none."
           if can else None)
    return {"rows": rows, "left": left, "ask": ask, "from": "sessions" if sessions is not None else "projects"}


def pick(p, answer):
    """The rows to send, from the person's answer. Only a plain 1 or 2 with numbers sends anything."""
    a = (answer or "").strip().lower()
    can = [r for r in p.get("rows") or [] if r.get("sendable")]
    if re.fullmatch(r"1\W*", a):
        return can
    m = re.fullmatch(r"2\W+([\d\s,]+)", a)
    if m:
        wanted = {int(x) for x in re.findall(r"\d+", m.group(1))}
        return [r for r in can if r["n"] in wanted]
    return []


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("--root", required=True)
    pl.add_argument("--sessions", action="store_true")
    pl.add_argument("--here")
    pl.add_argument("--data")
    pk = sub.add_parser("pick")
    pk.add_argument("--data")
    pk.add_argument("--answer", default="")
    a = ap.parse_args(argv)
    work = os.path.join(a.data or os.path.dirname(HERE), "hand-out")
    if a.cmd == "plan":
        sessions = None
        if a.sessions:
            got = read(os.path.join(work, "sessions.json"), None)
            sessions = got if isinstance(got, list) else (got or {}).get("sessions") if isinstance(got, dict) else None
            if not isinstance(sessions, list):
                print(json.dumps({"ok": False, "says": "The session list could not be read from " + os.path.join(work, "sessions.json") + "."}))
                return 1
        out = plan(a.root, sessions, a.here, a.data)
        os.makedirs(work, exist_ok=True)
        with open(os.path.join(work, "plan.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1)
    else:
        out = {"send": pick(read(os.path.join(work, "plan.json"), {}), a.answer)}
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
