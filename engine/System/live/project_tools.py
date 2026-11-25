r"""The four project tools in Settings, Tools: Add roadmap to a project, Add questions file to a project, Remove roadmap from a
project, Remove questions file from a project. They work on one of the owner's projects, not on the assistant.

    TOOLS                the four entries: id, name, plain words, tool ("roadmap" or "questions"), op ("add" or "remove")
    projects()           what the page offers when one is pressed: [{folder, name, roadmap, questions, sessions}], each with
                         whether the tool is already on there. From the open Claude sessions on this computer (the folders they
                         are in), and from the projects the assistant knows: roadmap projects in its settings, projects with a
                         questions file, introduced projects.
    sessions_of(folder)  the project's open sessions for the person to choose from, none chosen for them: id, name, last active,
                         child (started from another session), has (keeps the questions file). Top-level sessions first.
    handle(rec)          one press from the page, id "pt:<op>-<tool>:<ms>", words {"folder": ..., "session": <the chosen id>}:
                           add     sends the CHOSEN session ONE message asking it to run /assistant:roadmap-setup or
                                   /assistant:questions-setup after the person says yes IN THAT SESSION. Nothing runs in the
                                   project from here. Chosen session gone, or not sent: "Not sent: ..." and the page shows the
                                   command to type in the project, with a Copy button.
                           remove  turns it off through the plugin's own off script (the roadmap's own files are deleted; a questions file is kept).
                                   The page asked for the owner's yes first. The questions file is per session, so the session
                                   that keeps it is chosen; a roadmap belongs to the project, so Remove roadmap names no session.

The message goes the way the roadmap presses go (live_page\roadmap_press.py deliver): a hidden Claude run with message tools only.
"""
import json
import os
import re
import subprocess
import sys

import common

HERE = os.path.dirname(os.path.abspath(__file__))
COMMANDS = {"roadmap": "/assistant:roadmap-setup", "questions": "/assistant:questions-setup"}
LABEL = {"roadmap": "roadmap", "questions": "questions file"}
SCRIPTS = {"roadmap": "roadmap_setup.py", "questions": "questions_setup.py"}
OFF_COMMANDS = {"roadmap": "/assistant:roadmap-off", "questions": "/assistant:questions-off"}
ID = re.compile(r"^pt:(add|remove)-(roadmap|questions):\d{6,14}$")
MAX_PROJECTS = 150
MAX_SESSIONS = 15

TOOLS = (
    {"id": "add-roadmap", "explain": "Sets up the roadmap in a project. You choose the project and its top session, and that session sets it up once you say yes there. If no session can be asked, the command to type in the project is shown with a Copy button.",
     "name": "Add roadmap to a project", "tool": "roadmap", "op": "add",
     "words": "Sets up the roadmap in a project. Choose the project and session; that session sets it up once you say yes there."},
    {"id": "add-questions", "explain": "Turns on the questions file in a project, which keeps one session's questions. You choose the project and the session, and that session does it once you say yes there.",
     "name": "Add questions file to a project", "tool": "questions", "op": "add",
     "words": "Turns on the questions file in a project. Choose the project and session; that session does it once you say yes there."},
    {"id": "remove-roadmap", "explain": "Turns a project's roadmap off after you confirm. Its page stays as a record, and the roadmap's own files are deleted.",
     "name": "Remove roadmap from a project", "tool": "roadmap", "op": "remove",
     "words": "Turns a project's roadmap off after you confirm. Its page stays as a record; the roadmap's own files are deleted."},
    {"id": "remove-questions", "explain": "Turns the questions file off for one session of a project after you confirm. Its file stays as it is, and nothing is deleted.",
     "name": "Remove questions file from a project", "tool": "questions", "op": "remove",
     "words": "Turns the questions file off for one session of a project after you confirm. Its file stays as it is; nothing is deleted."},
)


def listed():
    return [dict(id=t["id"], name=t["name"], words=t["words"], explain=t["explain"], tool=t["tool"], op=t["op"], command=COMMANDS[t["tool"]]) for t in TOOLS]


def _norm(folder):
    return os.path.normcase(os.path.abspath(str(folder or "").rstrip("\\/") or "."))


def _read(path, default):
    return common.read_json(path, default) or default


# ---- what is on, and which projects there are -------------------------------------------------------------------------------
def roadmap_on(folder):
    return os.path.isfile(os.path.join(folder, ".claude", "roadmap", "config.json"))


def questions_on(folder):
    return bool((_read(os.path.join(folder, ".claude", "questions", "config.json"), {}) or {}).get("on"))


def question_sessions(folder):
    """The ids of the sessions that keep a questions file in this project (a project set up before per-session files has its main one)."""
    qc = _read(os.path.join(folder, ".claude", "questions", "config.json"), {})
    if not qc.get("on"):
        return set()
    got = set((qc.get("sessions") or {}))
    return got or ({str(qc["main_session_id"])} if qc.get("main_session_id") else set())


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def data_dirs():
    """The plugin's data folders on this computer (where its scripts and its list of questions projects are), newest first."""
    one = os.environ.get("ASSISTANT_PLUGIN_DATA")
    if one:
        return [one]
    base = os.path.join(config_dir(), "plugins", "data")
    try:
        found = [os.path.join(base, n) for n in os.listdir(base) if n.startswith("assistant") and os.path.isdir(os.path.join(base, n, "scripts"))]
    except OSError:
        return []
    return sorted(found, key=lambda p: -os.path.getmtime(os.path.join(p, "scripts")))


def open_sessions():
    """The open Claude sessions on this computer, from Claude's own list of them: [{name, cwd, id, local, at}], most recently
    active first. No AI is used."""
    base = os.path.join(config_dir(), "sessions")
    try:
        names = os.listdir(base)
    except OSError:
        return []
    press = _press()
    out = []
    for n in names:
        if not n.endswith(".json"):
            continue
        d = _read(os.path.join(base, n), {})
        if not isinstance(d, dict) or not str(d.get("name") or "").strip() or not d.get("cwd"):
            continue
        if not press._alive(d.get("pid") or 0):
            continue
        out.append({"name": " ".join(str(d["name"]).split())[:200], "cwd": str(d["cwd"]), "id": str(d.get("sessionId") or ""),
                    "local": str(d.get("hostSessionId") or ""), "at": _iso(d.get("updatedAt") or d.get("startedAt") or "")})
    return sorted(out, key=lambda s: s["at"], reverse=True)


def _iso(v):
    """A time as text that sorts: Claude writes milliseconds since 1970; anything else is kept as it is."""
    import datetime as dt
    if isinstance(v, (int, float)) and v > 1e11:
        return dt.datetime.fromtimestamp(v / 1000).isoformat(timespec="seconds")
    return str(v or "")


def started_by():
    """{local session id: the id of the session that started it}, from the desktop app's session list the update saved
    (hand-out/sessions.json in the plugin's data folder; each session another one started carries "startedBy")."""
    out = {}
    for d in data_dirs():
        got = _read(os.path.join(d, "hand-out", "sessions.json"), [])
        for x in (got.get("sessions") if isinstance(got, dict) else got) or []:
            if isinstance(x, dict) and x.get("sessionId") and x.get("startedBy"):
                out[str(x["sessionId"])] = str(x["startedBy"])
    return out


def sessions_of(folder):
    """The open sessions in one project, for the person to choose from (nothing is chosen for them): [{id, name, at, child, has}].
    child: started from another session (the app's saved session list, or the roadmap's own Roadmap writer). has: it keeps the
    project's questions file. Top-level sessions first, each group most recently active first."""
    parent = started_by()
    rm = _read(os.path.join(folder, ".claude", "roadmap", "config.json"), {})
    keep = question_sessions(folder)
    writer = str((rm.get("writer") or {}).get("session_id") or "")
    here = [s for s in open_sessions() if _norm(s["cwd"]) == _norm(folder)]           # newest first already
    out = [{"id": s["id"] or s["local"], "name": s["name"], "at": s["at"],
            "child": bool(s["local"] and s["local"] in parent) or bool(writer and s["id"] == writer),
            "has": bool(s["id"]) and s["id"] in keep} for s in here]
    return [x for x in out if not x["child"]] + [x for x in out if x["child"]]


def worked_folders():
    """Every folder the person has worked in with Claude Code, most recently active first: for each folder under the config
    dir's projects folder, the real folder is the "cwd" in the first lines of its newest transcript (only those lines are read)."""
    base = os.path.join(config_dir(), "projects")
    try:
        names = os.listdir(base)
    except OSError:
        return []
    found = []
    for n in names:
        d = os.path.join(base, n)
        try:
            files = [(os.path.getmtime(os.path.join(d, f)), os.path.join(d, f)) for f in os.listdir(d) if f.endswith(".jsonl")]
        except OSError:
            continue
        if not files:
            continue
        at, newest = max(files)
        cwd = ""
        try:
            with open(newest, encoding="utf-8", errors="replace") as fh:
                for _ in range(20):
                    line = fh.readline(65536)
                    if not line:
                        break
                    m = re.search(r'"cwd"\s*:\s*("(?:[^"\\]|\\.)*")', line)
                    if m:
                        cwd = json.loads(m.group(1))
                        break
        except (OSError, ValueError):
            continue
        if cwd:
            found.append((at, cwd))
    return [c for _, c in sorted(found, key=lambda x: -x[0])]


def _real_project(folder):
    """False for a worktree, a temporary folder or a tool's cache: places a session ran in, not projects."""
    f = _norm(folder)
    if ".claude" + os.sep + "worktrees" in f.replace("/", os.sep) or os.sep + "scratchpad" in f:
        return False
    import tempfile
    tmp = _norm(tempfile.gettempdir())
    if f == tmp or f.startswith(tmp + os.sep):
        return False
    if _internal(folder):          # the assistant's own working folders (its thinking runs in <home>\state, Talk to your assistant in state\convo)
        return False
    return os.sep + "cache" + os.sep not in f + os.sep


def _internal(folder):
    """An assistant's own working folder: inside its data home, or named state or convo (where its thinking and chat run)."""
    return _in_assistant_home(folder) or os.path.basename(_norm(folder).rstrip(os.sep)) in ("state", "convo")


def _in_assistant_home(folder):
    """True for a folder inside an assistant's data home (one holding personal and state), or that home itself."""
    a = os.path.abspath(folder)
    for _ in range(6):
        if os.path.isdir(os.path.join(a, "personal")) and os.path.isdir(os.path.join(a, "state")):
            return True
        up = os.path.dirname(a)
        if up == a:
            break
        a = up
    return False


def known_folders():
    """Folders the assistant knows as projects, in order, without repeats."""
    seen, out = set(), []

    def add(f):
        f = str(f or "").strip()
        if f and os.path.isdir(f) and _norm(f) not in seen:
            seen.add(_norm(f))
            out.append(f)
    for e in common.settings().get("roadmaps") or []:
        add(e.get("folder") if isinstance(e, dict) else None)
    for d in data_dirs():
        for f in (_read(os.path.join(d, "questions-projects.json"), {}).get("projects") or []):
            add(f)
    for p in (_read(os.path.join(common.PERSONAL, "projects.json"), {}).get("projects") or []):
        add(p.get("folder") if isinstance(p, dict) else None)
    for s in open_sessions():
        if ".claude" + os.sep + "worktrees" not in s["cwd"].replace("/", os.sep) and not _internal(s["cwd"]):
            add(s["cwd"])
    home = _norm(os.path.expanduser("~"))
    for c in worked_folders():
        if _real_project(c) and _norm(c) != home:
            add(c)
    return out[:MAX_PROJECTS]


def projects():
    return [{"folder": f, "name": os.path.basename(f.rstrip("\\/")) or f, "roadmap": roadmap_on(f), "questions": questions_on(f),
             "sessions": sessions_of(f)[:MAX_SESSIONS]} for f in known_folders()]


# ---- the message ----------------------------------------------------------------------------------------------------------------
def message(tool, folder):
    return (f"A request from the person, made on the assistant's page (Settings, Tools): turn on the {LABEL[tool]} in this project "
            f"({folder}). Do nothing yet. First ask the person here, in this session, in one line, whether to go ahead. Only after "
            f"they answer yes in this session, run {COMMANDS[tool]}. If they say no, or do not answer, run nothing and change "
            "nothing. Nothing else is asked of this session.")


def _press():
    hold = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "live_page")
    if hold not in sys.path:
        sys.path.insert(0, hold)
    import roadmap_press
    return roadmap_press


def _deliver(folder, name, text):
    return _press().deliver(folder, name, text)


# ---- the press ----------------------------------------------------------------------------------------------------------------
def _fallback(tool, why):
    return f"Not sent: {why}. In that project's Claude session, type {COMMANDS[tool]}"


def handle(rec):
    """One press from the page. Returns {"ok", "result"} for the listener (a refusal is plain words in "result" too). The words
    carry the project and, except for Remove roadmap (a roadmap belongs to the project), the session the person chose."""
    m = ID.match(str(rec.get("id") or ""))
    try:
        body = json.loads(rec.get("text") or "")
        folder, chosen = str(body["folder"]), str(body.get("session") or "")
    except (ValueError, KeyError, TypeError, AttributeError):
        folder, chosen = "", ""
    if not m or not folder:
        return {"ok": True, "result": "Not done: that press was not one I could read. Nothing was changed."}
    op, tool = m.group(1), m.group(2)
    known = {_norm(f): f for f in known_folders()}
    folder = known.get(_norm(folder), "")
    if not folder:
        return {"ok": True, "result": "Not done: that project is not one I know. Nothing was changed."}
    name = os.path.basename(folder.rstrip("\\/")) or folder
    if op == "remove" and tool == "roadmap":
        if not roadmap_on(folder):
            return {"ok": True, "result": f"The roadmap is already off in {name}. Nothing was changed."}
        return {"ok": True, "result": _remove(tool, folder, name)}
    session = next((s for s in sessions_of(folder) if chosen and s["id"] == chosen), None)
    if session is None:
        return {"ok": True, "result": _fallback(tool, "the session you chose is no longer open in that project") if op == "add"
                else "Not done: the session you chose is no longer open in that project. Nothing was changed."}
    if op == "add":
        if (tool == "roadmap" and roadmap_on(folder)) or (tool == "questions" and session["has"]):
            return {"ok": True, "result": f"The {LABEL[tool]} is already on in {name}" + (" for that session" if tool == "questions" else "") + ". Nothing was sent."}
        outcome, detail = _deliver(folder, session["name"], message(tool, folder))
        if outcome != "delivered":
            return {"ok": True, "result": _fallback(tool, f"the session \"{session['name']}\" could not be reached")}
        return {"ok": True, "result": f"Sent to the session \"{session['name']}\" (the one you chose). Say yes there and it sets up the {LABEL[tool]} in {name}; "
                                      "nothing runs until you do."}
    if not session["has"]:
        return {"ok": True, "result": f"That session has no questions file in {name}. Nothing was changed."}
    return {"ok": True, "result": _remove(tool, folder, name, session["id"])}


def _remove(tool, folder, name, session=""):
    script = ""
    for d in data_dirs():
        if os.path.isfile(os.path.join(d, "scripts", SCRIPTS[tool])):
            script = os.path.join(d, "scripts", SCRIPTS[tool])
            break
    if not script:
        return f"Not done: the plugin's script is not on this computer. In that project's Claude session, type {OFF_COMMANDS[tool]}"
    cmd = [sys.executable, script, "--project", folder, "off"] + (["--root", os.path.dirname(common.HOME)] if tool == "roadmap" else ["--session", session])
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, env=env,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return f"Not done: it took too long and was stopped. In that project's Claude session, type {OFF_COMMANDS[tool]}"
    if r.returncode:
        return f"Not done: {' '.join((r.stderr or r.stdout).split())[-200:]}. In that project's Claude session, type {OFF_COMMANDS[tool]}"
    if tool == "roadmap":
        return f"The roadmap is off in {name}. Its page stays as a record; the roadmap's own files were deleted."
    return f"The questions file is off for that session in {name}. Its file stays as it is."
