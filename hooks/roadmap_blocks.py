"""The roadmap's hooks, for a project's main session only. A project works one of two ways, set by "writes" in its
config.json (only the person changes it, with roadmap_setup.py writes-main or writes-writer):

WRITES "main" (the main session writes the roadmap itself):
- PostToolUse, SubagentStop, UserPromptSubmit: note in the logbook work that the roadmap must show (a helper started,
  a helper's report) and each roadmap write the main session makes (ArtifactData set, update, delete or batch on the
  page's own url).
- Stop (the end check): when a finished helper's report was noted that no roadmap write has followed, the reply is held
  once, naming it; never twice for the same report, and never for a turn that owes nothing (a plain answer is never held).
- UserPromptSubmit also reminds, once, of other work the roadmap does not show yet (a helper started, a roadmap write with
  no full-patch run after it where a reader asks for the full copy); a reminder never holds anything.
- PreToolUse on ArtifactData: a roadmap write by a helper, or by any session but the main one, is refused: only the main
  session writes the roadmap, from their reports. A session's copy of its own questions file (a "board" document
  "questions-file--...") is the exception: that session writes it itself.

WRITES "writer" (today's arrangement, the default): "tell the Roadmap writer first" is a reminder, never a refusal.
- UserPromptSubmit, PostToolUse, SubagentStop: write to the logbook the time of each message from the user, each helper
  report, and each main-session message to the Roadmap writer.
- PreToolUse on Agent, Task, Workflow, SendMessage, start_session and send_message: starting or messaging anyone but the
  writer while a user message or helper report is newer than the last message to the writer goes ahead, and is noted.
- UserPromptSubmit: the main session is reminded once, at the start of the message, of a helper report not yet
  forwarded to the writer and of work started before the writer was told the plan.
Only calls whose session id is the main session's and that carry no helper id (agent_id) are noted or reminded as the
main session's own; helpers' calls and other sessions' calls (the writer, other sessions) pass untouched.
The ids live in <project>/.claude/roadmap/config.json, written by the plugin's setup. A project with no such file, or
with the main session or the writer not yet recorded, is left completely alone.
The Roadmap writer's own end-of-turn note (a side-sessions-event naming only the writer as finishing) is not a helper
report, and starting a session titled as the writer is allowed, so a writer can always be started."""
import json, os, re, sys, time

WRITE_TOOL = "ArtifactData"
WRITE_ACTIONS = {"set", "update", "delete", "batch"}
START_TOOLS = {"Agent", "Task", "Workflow", "mcp__ccd_session__start_session"}
COPY_RUN = re.compile(r"roadmap_setup\.py[\"']?(\s+--project\s+(\"[^\"]*\"|'[^']*'|\S+))?\s+(full-patch|full)([\s\"']|$)")
ARTIFACT_ID = re.compile(r"claude\.ai/(?:code/)?artifact/([A-Za-z0-9-]+)")
GUARDED = {"Agent", "Task", "Workflow", "SendMessage", "mcp__ccd_session__start_session", "mcp__ccd_session_mgmt__send_message"}
SEND_TOOLS = {"SendMessage", "mcp__ccd_session_mgmt__send_message"}
START_TOOL = "mcp__ccd_session__start_session"
NOTICE_PREFIX = re.compile(r"^\s*(another claude session sent a message:\s*)?", re.I)
# A side session's end-of-turn note: The session "Roadmap writer" you started (local_...) finished a turn.
FINISHED = re.compile(r'session\s+"([^"]*)"(?:\s+you\s+started)?\s*(?:\(([^)]*)\))?\s*finished', re.I)


def project_dir(data=None):
    """The project folder: the one Claude Code names, else the nearest folder above cwd that has been set up."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    start = os.path.abspath((data or {}).get("cwd") or os.getcwd())
    cur = start
    while True:
        if os.path.isfile(os.path.join(cur, ".claude", "roadmap", "config.json")):
            return cur
        up = os.path.dirname(cur)
        if up == cur:
            return start
        cur = up


def config_path(project):
    return os.path.join(project, ".claude", "roadmap", "config.json")


def log_path(project):
    return os.path.join(project, ".claude", "roadmap", "log.json")


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default


def save_json(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp" + str(os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1)
    os.replace(tmp, path)


def direct(cfg):
    """True when the main session writes the roadmap itself (no Roadmap writer)."""
    return str(cfg.get("writes") or "").lower() == "main"


def active(cfg):
    """The hooks bind once setup has recorded the main session and, unless the main session writes the roadmap itself, the writer."""
    return bool(cfg.get("director_session_id")) and (direct(cfg) or bool((cfg.get("writer") or {}).get("session_id")))


def artifact_id(url):
    m = ARTIFACT_ID.search(str(url or ""))
    return m.group(1) if m else None


def roadmap_write(data, cfg):
    """True when this call writes the roadmap page's database (not a read)."""
    ti = data.get("tool_input") or {}
    if data.get("tool_name") != WRITE_TOOL or str(ti.get("action") or "").lower() not in WRITE_ACTIONS:
        return False
    page = artifact_id(cfg.get("page_url"))
    return bool(page) and artifact_id(ti.get("url")) == page


def writer_names(cfg):
    w = cfg.get("writer") or {}
    return {str(v).strip().lower() for v in (w.get("session_id"), w.get("name"), w.get("title")) if v}


def is_director(data, cfg):
    return data.get("session_id") == cfg.get("director_session_id") and not data.get("agent_id") and not data.get("agent_type")


def to_writer(data, cfg):
    """True when this call is a message to the Roadmap writer."""
    tool, ti = data.get("tool_name"), data.get("tool_input") or {}
    if tool not in SEND_TOOLS:
        return False
    target = str(ti.get("to") if tool == "SendMessage" else ti.get("session_id") or "")
    target = re.sub(r"\s*\[[^\]]*\]\s*$", "", target).strip().lower()           # "name [ref]" is the same session
    return target in writer_names(cfg) and bool(str(ti.get("message") or "").strip())


def starts_writer(data, cfg):
    """True when this call starts a session titled or named as the Roadmap writer (a first or a replacement writer)."""
    if data.get("tool_name") != START_TOOL:
        return False
    ti = data.get("tool_input") or {}
    w = cfg.get("writer") or {}
    names = {str(v).strip().lower() for v in (w.get("name"), w.get("title")) if v}
    asked = {str(ti.get("title") or "").strip().lower(), str(ti.get("name") or "").strip().lower()} - {""}
    return bool(asked & names)


def from_writer(tag_text, cfg):
    m = re.search(r'from="([^"]*)"(?:\s+from-name="([^"]*)")?', tag_text)
    return bool(m) and bool({(m.group(1) or "").lower(), (m.group(2) or "").lower()} & writer_names(cfg))


def only_writer_finished(text, cfg):
    """True when the prompt names at least one session as finishing a turn and every one named is the writer."""
    names = writer_names(cfg)
    found = [m for m in FINISHED.finditer(text)]
    if not found:
        return False
    for m in found:
        ids = {(m.group(1) or "").strip().lower(), (m.group(2) or "").strip().lower()} - {""}
        if not ids & names:
            return False
    return True


def classify_prompt(text, cfg, turn_notes=True):
    """'user', 'report' or None (a notice that is neither, such as a writer's note or a delivery notice).
    turn_notes=False (the main session writes the roadmap itself): only a helper's own report is one: a message it sent,
    or a subagent's final hand-back; a side session's turn-end note and a finished background command are not."""
    body = NOTICE_PREFIX.sub("", text or "", count=1)
    if not re.match(r"\s*[<\[]", body):
        return "user"
    report = False
    known = False
    writer_only = None                                          # worked out once, only if a side-sessions-event is seen
    for m in re.finditer(r"<(task-notification|agent-message|cross-session-message|side-sessions-event)\b([^>]*)>(.*?)(?=</\1>|$)", body, re.S):
        known = True
        kind, attrs, inner = m.group(1), m.group(2), m.group(3)
        if kind == "task-notification":
            status = re.search(r"<status>\s*(\w+)", inner)
            summary = re.search(r"<summary>(.*?)</summary>", inner, re.S)
            if status and status.group(1).lower() == "completed" and not (summary and "waiting on" in summary.group(1).lower()):
                if turn_notes or "<result>" in inner or (summary and re.match(r"\s*Agent\b", summary.group(1))):
                    report = True
        elif kind == "cross-session-message":
            if not from_writer(attrs, cfg):
                report = True
        elif kind == "side-sessions-event":
            if not turn_notes:
                continue                                        # a turn-end note alone owes no roadmap write
            if writer_only is None:
                writer_only = only_writer_finished(body, cfg)
            if not writer_only:
                report = True
        else:
            report = True
    if known:
        return "report" if report else None
    if re.match(r"\s*\[(cross-session|request interrupted)", body, re.I):
        return None
    return "user"                                               # the user's own message that happens to start with < or [


def full_wanted(cfg):
    """True when a reader of this project's roadmap asks for the full copy ("full": true in Roadmap page/readers.json)."""
    try:
        got = load_json(os.path.join(cfg.get("_project") or "", "Roadmap page", "readers.json"), {})
    except ValueError:
        return False
    listed = got.get("readers") if isinstance(got, dict) else None
    return isinstance(listed, dict) and any(isinstance(v, dict) and v.get("full") is True for v in listed.values())


def copy_run(data):
    """True for a terminal command that runs the setup script's full-patch (or full) command."""
    if data.get("tool_name") not in ("Bash", "PowerShell"):
        return False
    return bool(COPY_RUN.search(str((data.get("tool_input") or {}).get("command") or "")))


def owe(log, now, what):
    log["owed"] = (log.get("owed") or [])[-30:] + [[now, what]]


def record_direct(data, cfg, log, now):
    """The logbook when the main session writes the roadmap itself: work the roadmap must show, and each write."""
    if data.get("session_id") != cfg.get("director_session_id"):
        return False
    event = data.get("hook_event_name")
    if event == "UserPromptSubmit":
        if classify_prompt(data.get("prompt") or "", cfg, turn_notes=False) == "report":
            owe(log, now, "a helper's report")
            return True
    elif event == "SubagentStop":
        if data.get("agent_id") in (log.get("helpers") or []):
            owe(log, now, "a helper's report")
            return True
    elif event == "PostToolUse" and is_director(data, cfg):
        tool = data.get("tool_name")
        if roadmap_write(data, cfg):
            log["wrote"] = now
            log["owed"] = [o for o in log.get("owed") or [] if o[0] > now]
            if full_wanted(cfg):
                log["unpatched"] = now                               # the full copy is behind until full-patch runs
            return True
        if copy_run(data):
            if log.get("unpatched"):
                log.pop("unpatched", None)
                return True
            return False
        if tool in START_TOOLS:
            resp = data.get("tool_response")
            if isinstance(resp, str):
                try:
                    resp = json.loads(resp)
                except ValueError:
                    resp = {"text": resp}
            resp = resp if isinstance(resp, dict) else {}
            aid = resp.get("agentId") or resp.get("agent_id")
            if aid:
                log["helpers"] = (log.get("helpers") or [])[-200:] + [aid]
            if str(resp.get("status", "")).lower() == "completed":
                owe(log, now, "a helper's report")
            else:
                owe(log, now, "a helper you started")
            return True
    return False


REPORT = "a helper's report"


def end_check(data, cfg, log):
    """Stop, when the main session writes the roadmap itself. Returns (refusal or None, whether the logbook changed).
    Held once only for a finished helper's report no roadmap write has followed; the same report is never held twice.
    Other owed work is a reminder at the next message (remind_direct)."""
    if not is_director(data, cfg):
        return None, False
    owed = [o for o in log.get("owed") or [] if o[1] == REPORT and o[0] > log.get("wrote", 0) and o[0] > log.get("caught", 0)]
    if not owed:
        return None, False
    log["caught"] = max(o[0] for o in owed)
    return ("Work happened this turn that the roadmap doesn't show yet (" + REPORT + "). Write it on the roadmap now, "
            "yourself, in one short step and without a word about it in the chat; if the write fails, say once what was not "
            "recorded. Then end your reply."), True


def remind_direct(data, cfg, log, now):
    """UserPromptSubmit, when the main session writes the roadmap itself: one reminder for work since the last roadmap write
    that is not held (a helper started) and for a full copy left behind. Returns (lines, whether the logbook changed)."""
    if not is_director(data, cfg):
        return [], False
    seen = max(log.get("reminded", 0), log.get("wrote", 0))
    owed = sorted({o[1] for o in log.get("owed") or [] if o[1] != REPORT and seen < o[0] < now})
    behind = log.get("unpatched", 0) > max(log.get("caught_copy", 0), log.get("reminded", 0))
    out = []
    if owed:
        out.append("Reminder: the roadmap does not show yet work from before this message (" + ", ".join(owed) + "). Write "
                   "it on the roadmap in this turn, yourself, in one short step and without a word about it in the chat.")
    if behind:
        log["caught_copy"] = log["unpatched"]
        out.append("Reminder: the roadmap was written but its full copy was not brought up to date (no full-patch since the "
                   "write). Hand those writes to full-patch in this turn, as your skill says.")
    if out:
        log["reminded"] = now
    return out, bool(out)


READY = ("Ready, waiting for your look", "Ready, known fault")
CHECKED = "Checked by Claude, "
READY_REFUSED = ("Refused: Run this check yourself first (code, test page or test cards); only checks you cannot do go to the "
                 "person, each with needs_person saying why.")


def _row_writes(ti):
    """The writes to rows ("steps") this call makes: [data dict]. Data given as a file is read from it."""
    action = str(ti.get("action") or "").lower()
    entries = ti.get("writes") if action == "batch" and isinstance(ti.get("writes"), list) else [dict(ti, op=action)]
    out = []
    for w in entries:
        if not isinstance(w, dict) or str(w.get("op") or "").lower() not in ("set", "update") or w.get("collection") != "steps":
            continue
        d = w.get("data")
        if d is None and w.get("file_path"):
            d = load_json(w["file_path"], None)
        if isinstance(d, dict):
            out.append(d)
    return out


def refuse_ready(data, cfg):
    """PreToolUse, whoever writes: a row written Ready must say, in the same write, that Claude ran the checks it could
    (shown_working with a "Checked by Claude, <date>: ..." line) and must carry only checks the person alone can do, each with
    needs_person saying why (his phone, a real send, reconnecting an account, his taste)."""
    if not roadmap_write(data, cfg):
        return None
    for d in _row_writes(data.get("tool_input") or {}):
        if d.get("status") not in READY:
            continue
        checks = d.get("checks")
        if not isinstance(checks, list) or not checks:
            return READY_REFUSED + " A Ready row carries its checks in the same write."
        if any(not isinstance(c, dict) or not str(c.get("needs_person") or "").strip() for c in checks):
            return READY_REFUSED
        if CHECKED not in str(d.get("shown_working") or ""):
            return ("Refused: a Ready row's shown_working needs a line \"Checked by Claude, <date>: ...\" naming what you checked "
                    "yourself (the code path, and a test page or test cards), in the same write.")
    return None


def questions_file_only(data):
    """True when every write of this call is to a session's copy of its questions file ("board" documents
    "questions-file--..."), which the session that keeps that file writes itself."""
    ti = data.get("tool_input") or {}
    action = str(ti.get("action") or "").lower()
    entries = ti.get("writes") if action == "batch" else [ti]
    return (isinstance(entries, list) and bool(entries) and not data.get("agent_id")
            and all(isinstance(w, dict) and w.get("collection") == "board" and str(w.get("doc_id") or "").startswith("questions-file--")
                    for w in entries))


def refuse_other_writer(data, cfg):
    """PreToolUse, when the main session writes the roadmap itself: nobody else writes it, except a session's copy of its
    questions file."""
    if not roadmap_write(data, cfg) or is_director(data, cfg) or questions_file_only(data):
        return None
    return ("Refused: only this project's main session writes the roadmap. Put what the roadmap should say in your report "
            "to the main session instead.")


def record(data, cfg, log, now):
    """Updates the logbook from one hook event. Returns True when something changed."""
    if direct(cfg):
        return record_direct(data, cfg, log, now)
    if data.get("session_id") != cfg.get("director_session_id"):
        return False
    event = data.get("hook_event_name")
    if event == "UserPromptSubmit":
        kind = classify_prompt(data.get("prompt") or "", cfg)
        if kind:
            log[kind] = now
            return True
    elif event == "SubagentStop":
        if data.get("agent_id") in (log.get("helpers") or []):
            log["report"] = now
            return True
    elif event == "PostToolUse" and is_director(data, cfg):
        tool = data.get("tool_name")
        if to_writer(data, cfg):
            log["writer"] = now
            return True
        if tool in ("Agent", "Task"):
            resp = data.get("tool_response")
            if isinstance(resp, str):
                try:
                    resp = json.loads(resp)
                except ValueError:
                    resp = {"text": resp}
            resp = resp if isinstance(resp, dict) else {}
            aid = resp.get("agentId") or resp.get("agent_id")
            if aid:
                log["helpers"] = (log.get("helpers") or [])[-200:] + [aid]
            if str(resp.get("status", "")).lower() == "completed":
                log["report"] = now
            return True
    return False


def note_untold(data, cfg, log, now):
    """PreToolUse: a helper started or messaged while the user or a helper report is newer than the last message to the
    writer goes ahead; it is noted for a reminder at the next message. Returns True when the logbook changed."""
    if not is_director(data, cfg) or data.get("tool_name") not in GUARDED or to_writer(data, cfg) or starts_writer(data, cfg):
        return False
    w = log.get("writer", 0)
    if max(log.get("user", 0), log.get("report", 0)) > w and log.get("untold", 0) <= max(w, log.get("reminded", 0)):
        log["untold"] = now
        return True
    return False


def remind_writer(data, cfg, log, now):
    """UserPromptSubmit: one reminder for a helper report not yet forwarded to the writer and for work started before the
    writer was told the plan. Returns (lines, whether the logbook changed)."""
    if not is_director(data, cfg):
        return [], False
    seen = max(log.get("writer", 0), log.get("reminded", 0))
    out = []
    if log.get("report", 0) > seen:
        out.append("Reminder: a helper has reported and the Roadmap writer has not been sent that report yet. Forward it to "
                   "the Roadmap writer in this turn.")
    if log.get("untold", 0) > seen:
        out.append("Reminder: a helper was started or messaged before the Roadmap writer was told the plan. Send the Roadmap "
                   "writer the plan and what was started in this turn.")
    if out:
        log["reminded"] = now
    return out, bool(out)


def main(data, cfg_path=None, log_file=None, now=None):
    """Returns (exit code, message)."""
    now = time.time() if now is None else now
    if cfg_path is None or log_file is None:
        project = project_dir(data)
        cfg_path, log_file = cfg_path or config_path(project), log_file or log_path(project)
    cfg = load_json(cfg_path, {})
    if not active(cfg):
        return 0, None
    cfg["_project"] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(log_file))))   # never saved
    log = load_json(log_file, {})
    event = data.get("hook_event_name")
    if event == "PreToolUse":
        why = None
        if direct(cfg):
            why = refuse_other_writer(data, cfg)
        elif note_untold(data, cfg, log, now):
            save_json(log, log_file)
        why = why or refuse_ready(data, cfg)
        return (2, why) if why else (0, None)
    if event == "Stop":
        if not direct(cfg):
            return 0, None
        why, changed = end_check(data, cfg, log)
        if changed:
            save_json(log, log_file)
        return (2, why) if why else (0, None)
    changed = record(data, cfg, log, now)
    said = []
    if event == "UserPromptSubmit":
        said, reminded = (remind_direct if direct(cfg) else remind_writer)(data, cfg, log, now)
        changed = changed or reminded
    if changed:
        save_json(log, log_file)
    return 0, (" ".join(said) or None)      # exit 0 with words: a reminder added to the message, never a hold


if __name__ == "__main__":
    data = {}
    try:
        data = json.load(sys.stdin)
        code, msg = main(data)
    except Exception as e:
        if not isinstance(data, dict) or data.get("hook_event_name") == "PreToolUse":
            code, msg = 2, "Refused: the roadmap check itself failed (" + repr(e) + ")."
        else:
            code, msg = 1, "The roadmap logbook could not be updated (" + repr(e) + ")."
    if msg:
        print(msg, file=sys.stderr if code else sys.stdout)      # a reminder (exit 0) goes to the message as context
    sys.exit(code)
