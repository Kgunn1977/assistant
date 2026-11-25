"""The questions file's hooks, for a project that turned it on with /assistant:questions-setup (questions_setup.py on). A project
that did not, or turned it off, is left completely alone. Each session that turned it on has its own file (the first keeps
Questions.md, each further one gets "Questions - <session title>.md"); a session without a file gets nothing from these hooks.

- SessionStart and UserPromptSubmit (D1): when the session's own file has open questions, they are put in front of it as plain
  facts, with what to do: match the message against them and keep the file.
- PostToolUse on Bash or PowerShell: the session that ran "questions_setup.py on" is recorded as the owner of the file the
  script named (config "pending"); "questions_setup.py off --this-session" takes that session's file out of the record.
  A session is recorded by its local_... id, which survives app restarts (the app's own id for it does not); a record made
  by the app's own id is moved to the local id the next time that session is seen.
- Stop (D2), for a session with a file: the reply is held once with a plain reason when
  A. the person answered a question this turn (an answer by number and letter, such as "2b", or the reply's own one-line echo
     "Took ... as: ...") and the file has not changed since the message came in;
  B. the reply asks the person a new question that is not in the file (an experiment: a sentence of the reply ending in "?"
     whose words match no open question).
  Each is held at most once a turn, and a session is let go after three holds in a row, so a reply can never loop.
The open questions are never listed in chat: the side panel shows the file."""
import hashlib, json, os, re, sys

FILE = "Questions.md"
ENTRY = re.compile(r"^(\d+)\.\s+(.*\S)", re.M)
SETUP_RUN = re.compile(r"questions_setup\.py[\"']?(?:\s+--project\s+(?:\"[^\"]*\"|'[^']*'|\S+))?\s+on(?:[\s\"']|$)")
ANSWER = re.compile(r"(?:^|[\s,;(])([1-9]\d?)\s?([a-z])(?=$|[\s,.;:)!?])", re.I)
LEAD_NUMBER = re.compile(r"^\s*([1-9]\d?)\b")
ECHO = re.compile(r"(?im)^\W*took\b.{0,200}?\bas\s*:")
STOP_TRIES = 3
SETUP_OFF = re.compile(r"questions_setup\.py[\"']?(?:\s+--project\s+(?:\"[^\"]*\"|'[^']*'|\S+))?\s+off\s+--this-session")
WORD = re.compile(r"[a-z0-9']+")
SMALL = set("the a an and or of to in on for with is are was were be been it its this that these those you your yours we our "
            "i me my do does did can could should would will shall may might what which who whom when where why how any some "
            "there here have has had not no yes from by at as into about than then so if".split())


def project_dir(data):
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    cur = os.path.abspath((data or {}).get("cwd") or os.getcwd())
    start = cur
    while True:
        if os.path.isfile(os.path.join(cur, ".claude", "questions", "config.json")):
            return cur
        up = os.path.dirname(cur)
        if up == cur:
            return start
        cur = up


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp" + str(os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, path)


def questions(text):
    """[(number, the whole entry's text)] for each open question in the file, in order."""
    out, marks = [], list(ENTRY.finditer(text))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((int(m.group(1)), text[m.start():end].strip()))
    return out


def file_text(project, fname):
    try:
        with open(os.path.join(project, fname), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def digest(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest() if text is not None else None


def sessions_of(cfg):
    """{session id: file name} for the sessions that turned it on (a project set up before per-session files has only its main one)."""
    got = dict(cfg.get("sessions") or {})
    if not got and cfg.get("main_session_id"):
        got[cfg["main_session_id"]] = FILE
    return got


def session_key(sid):
    """The session's local_... id from the app's list of running sessions (<claude config>/sessions/<pid>.json), else sid."""
    base = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude"), "sessions")
    try:
        listed = os.listdir(base)
    except OSError:
        return sid
    for f in listed:
        if f.endswith(".json"):
            d = load(os.path.join(base, f), {})
            if isinstance(d, dict) and d.get("sessionId") == sid and str(d.get("hostSessionId") or "").startswith("local_"):
                return d["hostSessionId"]
    return sid


def own_file(data, cfg):
    """The file name this session keeps, or None: a helper (subagent) and a session that never turned it on have none."""
    if data.get("agent_id") or data.get("agent_type") or not data.get("session_id"):
        return None
    got = sessions_of(cfg)
    return got.get(data.get("_key") or data["session_id"]) or got.get(data["session_id"])


def move_to_key(cfg, sid, key):
    """Moves a record made by the app's own id to the session's local_... id. True when it changed."""
    got = sessions_of(cfg)
    if key == sid or sid not in got or key in got:
        return False
    got[key] = got.pop(sid)
    cfg["sessions"] = got
    if cfg.get("main_session_id") == sid:
        cfg["main_session_id"] = key
    return True


def facts(qs, fname, roadmap=False):
    first = lambda t: " ".join(t.split("\n", 1)[0].split()[1:])
    listed = "; ".join(f"{n}. {first(t)}" for n, t in qs)
    return (f"Open questions in this session's {fname} (the person sees the file in the side panel; these are its numbers): "
            + listed + ". Match the person's message against them, by number and letter or by meaning. For an answer, in this "
            "turn: echo it in one line naming the question in words (\"Took 2b as: ...\"), record the decision where this project "
            "keeps decisions, take the question out of the file and renumber from 1, oldest first. A question for the person goes "
            "into the file before you ask it" + ("; a question raised by the work goes on the roadmap's row instead, never both"
            if roadmap else "") + ". Never list the open questions in chat. (skill assistant:questions)")


def last_reply(data):
    """The text of the reply that is ending: the payload's own, else the newest assistant message in the transcript."""
    said = data.get("last_assistant_message")
    if isinstance(said, str) and said.strip():
        return said
    path = data.get("transcript_path")
    if not path or not os.path.isfile(path):
        return ""
    texts = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                msg = row.get("message") if isinstance(row.get("message"), dict) else row
                if row.get("type") == "user" or msg.get("role") == "user":
                    if any(isinstance(c, dict) and c.get("type") == "text" for c in (msg.get("content") or [])) or isinstance(msg.get("content"), str):
                        texts = []          # a new message from the person: the reply starts after it
                    continue
                if row.get("type") == "assistant" or msg.get("role") == "assistant":
                    content = msg.get("content")
                    if isinstance(content, str):
                        texts.append(content)
                    else:
                        texts += [c.get("text") or "" for c in content or [] if isinstance(c, dict) and c.get("type") == "text"]
    except OSError:
        return ""
    return "\n".join(t for t in texts if t)


def chat_part(reply, roadmap=False):
    """The reply without code blocks and, in a project with a roadmap, without the paragraphs that speak of the roadmap: there a
    work question is reported as put on its row, or a roadmap answer is echoed, and neither belongs to the questions file."""
    body = re.sub(r"```.*?```", " ", reply or "", flags=re.S)
    if roadmap:
        body = "\n\n".join(p for p in re.split(r"\n\s*\n", body) if not re.search(r"\broadmap\b", p, re.I))
    return body


def asked(reply, roadmap=False):
    """The sentences of the reply that put a question (ending in "?"), outside code, quoted lines and roadmap paragraphs."""
    body = chat_part(reply, roadmap)
    body = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith((">", "|")))
    body = re.sub(r"\"[^\"\n]{0,300}\"|“[^”\n]{0,300}”", " ", body)
    out = []
    for s in re.split(r"(?<=[.!?])\s+|\n+", body):
        s = s.strip(" -*•\t")
        if s.endswith("?") and len(WORD.findall(s.lower())) >= 3:
            out.append(s)
    return out


def words(text):
    return {w for w in WORD.findall((text or "").lower()) if len(w) >= 4 and w not in SMALL}


def in_file(question, qs):
    """True when a question's words are found in one open question of the file (most of its words, or a word-for-word match)."""
    mine = words(question)
    if not mine:
        return True
    for _n, t in qs:
        if question.strip().lower() in t.lower() or len(mine & words(t)) >= max(1, round(0.6 * len(mine))):
            return True
    return False


def remember(project):
    """Adds the project to the list of projects with a questions file, in the plugin's data folder, which the step
    handed to each session after an update reads when the desktop app's session list is not available."""
    data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data or not os.path.isdir(data):
        return
    path = os.path.join(data, "questions-projects.json")
    got = load(path, {})
    listed = [p for p in (got.get("projects") or []) if isinstance(p, str)]
    if os.path.normcase(project) not in {os.path.normcase(p) for p in listed}:
        save(path, {"about": "Projects where the questions file was turned on; kept by the plugin's questions hook.",
                    "projects": listed + [project]})


def main(data, project=None):
    """Returns (exit code, message for stderr when holding, text for stdout as context)."""
    project = project or project_dir(data)
    cfg_path = os.path.join(project, ".claude", "questions", "config.json")
    cfg = load(cfg_path, {})
    if not cfg.get("on"):
        return 0, None, None
    event = data.get("hook_event_name")
    state_path = os.path.join(project, ".claude", "questions", "state.json")
    if data.get("session_id") and not data.get("agent_id") and not data.get("agent_type"):
        data = dict(data, _key=session_key(data["session_id"]))
        if move_to_key(cfg, data["session_id"], data["_key"]):
            save(cfg_path, cfg)
    if event == "PostToolUse":
        cmd = str((data.get("tool_input") or {}).get("command") or "")
        sid = data.get("_key") or data.get("session_id")
        if sid and not data.get("agent_id") and not data.get("agent_type"):
            if SETUP_RUN.search(cmd):
                got = sessions_of(cfg)
                pending = cfg.pop("pending", None)
                if sid not in got and pending:
                    got[sid] = pending
                    if pending == FILE:
                        cfg["main_session_id"] = sid
                cfg["sessions"] = got
                save(cfg_path, cfg)
                remember(project)
            elif SETUP_OFF.search(cmd) and sid in sessions_of(cfg):
                got = sessions_of(cfg)
                gone = got.pop(sid)
                cfg["sessions"] = got
                if gone == FILE:
                    cfg.pop("main_session_id", None)
                if not got:
                    cfg["on"] = False
                save(cfg_path, cfg)
        return 0, None, None
    fname = own_file(data, cfg)
    if not fname:
        return 0, None, None
    text = file_text(project, fname)
    qs = questions(text or "")
    roadmap = os.path.isfile(os.path.join(project, ".claude", "roadmap", "config.json"))
    if event in ("SessionStart", "UserPromptSubmit"):
        if event == "UserPromptSubmit":
            prompt = str(data.get("prompt") or "")
            hit = [m for m in ANSWER.finditer(prompt) if int(m.group(1)) <= len(qs)]
            lead = LEAD_NUMBER.match(prompt)
            st = load(state_path, {})
            st.setdefault("sessions", {})[data["session_id"]] = dict(
                (st.get("sessions") or {}).get(data["session_id"]) or {}, hash=digest(text), open=len(qs), held=[],
                answer=bool(hit) or bool(lead and int(lead.group(1)) <= len(qs)))
            save(state_path, st)
        return 0, None, (facts(qs, fname, roadmap) if qs else None)
    if event == "Stop":
        st = load(state_path, {})
        me = (st.get("sessions") or {}).get(data["session_id"]) or {}
        reply = last_reply(data)
        why = None
        changed = digest(text) != me.get("hash")
        if "A" not in (me.get("held") or []) and (me.get("answer") or ECHO.search(chat_part(reply, roadmap))) and not changed and me.get("hash") is not None:
            why = ("The person answered a question this turn, but " + fname + " has not changed. In this same turn: take that question out "
                   "of the file, record the decision where this project keeps decisions, and renumber the rest from 1, oldest first. Keep "
                   "the reply to the one-line echo naming the question in words; do not list the open questions in chat. Then end your reply.")
            case = "A"
        if why is None and "B" not in (me.get("held") or []):
            missing = [q for q in asked(reply, roadmap) if not in_file(q, qs)]
            if missing:
                why = ("This reply asks the person a question that is not in " + fname + ": \"" + (missing[0] if len(missing[0]) <= 200 else missing[0][:201].rsplit(" ", 1)[0] + " ...") + "\". Write it into "
                       "the file first (after the open ones, numbered in order, with lettered choices where there are real choices, its "
                       "recommendation and the date asked), then end your reply. Do not list the open questions in chat. If it is not a question "
                       "for the person (words you are quoting, a heading, a question you answer yourself), end your reply as it is.")
                case = "B"
        if why and int(me.get("row") or 0) >= STOP_TRIES:        # held three times in a row: let go, never a loop
            me["row"] = 0
            why = None
        elif why:
            me["row"] = int(me.get("row") or 0) + 1
            me["held"] = list(me.get("held") or []) + [case]
        else:
            me["row"] = 0
        st.setdefault("sessions", {})[data["session_id"]] = me
        save(state_path, st)
        return (2, why, None) if why else (0, None, None)
    return 0, None, None


if __name__ == "__main__":
    data = {}
    try:
        data = json.load(sys.stdin)
        code, msg, context = main(data)
    except Exception as e:
        code, msg, context = 0, None, None          # the questions check never stops a session by failing
        print("The questions check could not run (" + repr(e) + ").", file=sys.stderr)
    if context:
        print(context)
    if msg:
        print(msg, file=sys.stderr)
    sys.exit(code)
