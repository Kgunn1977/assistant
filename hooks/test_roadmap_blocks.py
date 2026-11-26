"""Proves the Roadmap writer blocks, their lock, the reminder and the setup script decide correctly without running
through Claude Code. Builds a throwaway project folder, records a main session and a writer in it the way setup does,
then feeds sample hook inputs for the main session, a helper and the writer. Prints each failure and a count.
Run with no arguments: python hooks/test_roadmap_blocks.py"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.pop("CLAUDE_PROJECT_DIR", None)
import roadmap_blocks as rb, guard_blocks as gbk, reminder, roadmap_setup as setup

TMP = tempfile.mkdtemp()
P = os.path.join(TMP, "Some Project")
os.makedirs(P)
CFG, LOG = rb.config_path(P), rb.log_path(P)
DIR, WRITER, WRITER_CC = "made-up-main-session-id", "local_made-up-writer-session", "made-up-writer-own-id"      # made up; real ids are longer
fails, total, clock = [], 0, [1000.0]


def check(name, got, want):
    global total
    total += 1
    if got != want:
        fails.append(f"{name}: wanted {want!r}, got {got!r}")


def fresh():
    if os.path.exists(LOG):
        os.remove(LOG)


def run(event, session=DIR, agent=None, **extra):
    clock[0] += 1
    d = {"hook_event_name": event, "session_id": session, "cwd": P, **extra}
    if agent:
        d["agent_id"], d["agent_type"] = agent, "general-purpose"
    return rb.main(d, CFG, LOG, clock[0])[0]


def user(text="Do the next piece.", **kw):
    return run("UserPromptSubmit", prompt=text, **kw)


def start(**kw):
    return run("PreToolUse", tool_name="Agent", tool_input={"prompt": "x", "subagent_type": "general-purpose"}, **kw)


def started(aid, status="async_launched", **kw):
    return run("PostToolUse", tool_name="Agent", tool_input={"prompt": "x"}, tool_response={"status": status, "agentId": aid}, **kw)


def send(to, tool="SendMessage", post=False, **kw):
    ti = {"to": to, "message": "Change row x."} if tool == "SendMessage" else {"session_id": to, "message": "Change row x."}
    return run("PostToolUse" if post else "PreToolUse", tool_name=tool, tool_input=ti, **kw)


def stop(**kw):
    return run("Stop", stop_hook_active=False, **kw)


def nudge(text="Next.", **kw):
    """The reminder the main session is given at the start of a message (None when there is none)."""
    clock[0] += 1
    d = {"hook_event_name": "UserPromptSubmit", "session_id": DIR, "cwd": P, "prompt": text, **kw}
    return rb.main(d, CFG, LOG, clock[0])[1]


def new_session(title, name=None):
    ti = {"title": title, "prompt": "x"}
    if name:
        ti["name"] = name
    return run("PreToolUse", tool_name="mcp__ccd_session__start_session", tool_input=ti)


def setup_cmd(session, *argv, hook=True, agent=None):
    """Runs one setup command the way a session would: the lock hook sees the terminal call first, then the script runs."""
    cmd = 'python "' + os.path.join(ROOT, "scripts", "roadmap_setup.py") + '" ' + " ".join(argv)
    d = {"hook_event_name": "PreToolUse", "session_id": session, "cwd": P, "tool_name": "Bash", "tool_input": {"command": cmd}}
    if agent:
        d["agent_id"], d["agent_type"] = agent, "general-purpose"
    if hook:
        if gbk.Lock(rb.load_json(CFG, {}), ROOT).decide(d):
            return "refused"
        gbk.note_setup_session(d, P)
    try:
        return setup.main(["--project", P, *argv])
    except SystemExit as e:
        return "stopped" if isinstance(e.code, str) else e.code


def finished_note(title, sid):
    return (f'<system-reminder>\nThe session "{title}" you started ({sid}) finished a turn. It reported: row x changed.\n'
            f'</system-reminder>\n')


# ---- before setup: a project with nothing recorded is left completely alone ----
check("not set up: helper start goes", start(), 0)
check("not set up: Stop goes", stop(), 0)
check("not set up: no logbook is written", (user(), os.path.exists(LOG))[1], False)
check("not set up: the lock is off", gbk.main({"tool_name": "Write", "tool_input": {"file_path": ".claude/settings.json"}, "cwd": P}), None)
check("not set up: no reminder", reminder.lines({"session_id": DIR}, {}), [])

# ---- setup, as the setup skill runs it ----
_out = sys.stdout
sys.stdout = open(os.devnull, "w")
try:
    check("setup without the plugin's hooks is stopped", setup_cmd(DIR, "director", hook=False), "stopped")
    check("setup run by a helper is stopped", setup_cmd(DIR, "director", agent="a0"), "stopped")
    check("setup: main session recorded", setup_cmd(DIR, "director"), 0)
    check("setup: the id recorded is the one the hook saw", rb.load_json(CFG, {}).get("director_session_id"), DIR)
    check("main session only: blocks still off", (user(), start())[1], 0)
    check("main session only: reminder says start the writer", "start-writer" in " ".join(reminder.lines({"session_id": DIR}, rb.load_json(CFG, {}))), True)
    check("setup: page copy made", setup_cmd(DIR, "copy-page", "--title", "Kitchen Remodel Roadmap"), 0)
    check("setup: page link recorded", setup_cmd(DIR, "page", "https://claude.ai/artifact/EXAMPLE"), 0)
    check("setup: a link that is not a page is stopped", setup_cmd(DIR, "page", "https://example.com/x"), "stopped")
    check("setup: writer recorded", setup_cmd(DIR, "writer", "--id", WRITER), 0)
    check("setup: main session cannot record itself as the writer", setup_cmd(DIR, "writer-self"), "stopped")
    check("setup: writer records itself", setup_cmd(WRITER_CC, "writer-self"), 0)
    check("setup: status runs", setup_cmd(DIR, "status"), 0)
finally:
    sys.stdout.close()
    sys.stdout = _out
cfg = rb.load_json(CFG, {})
check("blocks are on after setup", rb.active(cfg), True)
page = open(os.path.join(P, "Roadmap page", "roadmap.html"), encoding="utf-8").read()
check("page copy carries the project's title twice", page.count("Kitchen Remodel Roadmap"), 2)
check("page copy has no placeholder left", "Project Roadmap" in page, False)
check("setup: the roadmap's name is recorded", cfg.get("title"), "Kitchen Remodel Roadmap")

# ---- the plain copy of the facts: off until asked for, checked and stamped by the setup script ----
PLAIN = os.path.join(P, "Roadmap page", "roadmap.json")
GOOD = {"facts_as_of": "2026-03-04", "next": [{"label": "Next", "text": "Order the tiles"}], "questions_open": 2, "rows": [
    {"id": "step-02", "order": 20, "kind": "step", "number": "2", "name": "Tiles", "parent": "", "status": "Ready, waiting for your look", "changed": "2026-03-04T10:05", "checks": 4, "marked": 1},
    {"id": "step-01", "order": 10, "kind": "step", "number": "1", "name": "Plumbing", "parent": "", "status": "Done, confirmed", "changed": "2026-03-01T09:00", "checks": 3, "marked": 0},
    {"id": "item-bin", "order": 90, "kind": "item", "number": "", "name": "Hire a bin", "parent": "", "status": "Ready, known fault", "changed": "2026-03-02T09:00", "checks": 2, "marked": 2}]}


def quiet(*argv, session=WRITER_CC):
    keep, sys.stdout = sys.stdout, open(os.devnull, "w")
    try:
        return setup_cmd(session, *argv)
    finally:
        sys.stdout.close()
        sys.stdout = keep


READERS = os.path.join(P, "Roadmap page", "readers.json")
check("plain copy: nobody has asked after setup", setup.readers(P), [])
check("plain copy: nothing to check yet is stopped", quiet("facts"), "stopped")
before = rb.load_json(CFG, {})
check("plain copy: asked for by hand", (quiet("plain-copy", "on"), setup.readers(P)), (0, ["by hand"]))
check("plain copy: a second reader lists itself", (quiet("plain-copy", "on", "--reader", "assistant"), setup.readers(P)), (0, ["assistant", "by hand"]))
check("plain copy: asking leaves the project's ids alone and the blocks on", (rb.load_json(CFG, {}), rb.active(rb.load_json(CFG, {}))), (before, True))
check("plain copy: one reader leaving keeps the other", (quiet("plain-copy", "off"), setup.readers(P)), (0, ["assistant"]))
other = os.path.join(TMP, "Never Set Up")
os.makedirs(other)
keep, sys.stdout = sys.stdout, open(os.devnull, "w")
try:
    asked = setup.main(["--project", other, "plain-copy", "on", "--reader", "assistant"])
finally:
    sys.stdout.close()
    sys.stdout = keep
check("plain copy: a reader may ask before the project has a roadmap, and nothing else is made there",
      (asked, setup.readers(other), sorted(os.listdir(other)), os.path.exists(rb.config_path(other))), (0, ["assistant"], ["Roadmap page"], False))
rb.save_json(GOOD, PLAIN)
check("plain copy: a good file is accepted", quiet("facts"), 0)
got = rb.load_json(PLAIN, {})
check("plain copy: name and link filled in", (got.get("name"), got.get("page_url")), ("Kitchen Remodel Roadmap", "https://claude.ai/artifact/EXAMPLE"))
check("plain copy: stamped, with the agreement's number", (bool(got.get("written")), got.get("agreement")), (True, 1))
check("plain copy: rows put in order", [r["id"] for r in got.get("rows", [])], ["step-01", "step-02", "item-bin"])
check("plain copy: checks waiting counts only unmarked checks on Ready rows", got.get("checks_waiting"), 3)
check("plain copy: open questions kept", got.get("questions_open"), 2)
check("plain copy: checking twice changes nothing but the stamp", (quiet("facts"), {k: v for k, v in rb.load_json(PLAIN, {}).items() if k != "written"}),
      (0, {k: v for k, v in got.items() if k != "written"}))
bad = json.loads(json.dumps(GOOD))
bad["rows"][0]["status"] = "Nearly done"
rb.save_json(bad, PLAIN)
check("plain copy: a status that is not one of the eight is stopped", quiet("facts"), "stopped")
check("plain copy: a refused file is left as it was", rb.load_json(PLAIN, {}), bad)
rb.save_json(GOOD, PLAIN)
quiet("facts")
check("plain copy: the last reader leaving turns it off", (quiet("plain-copy", "off", "--reader", "assistant"), setup.readers(P)), (0, []))

NOTE = "<task-notification>\n<task-id>a1</task-id>\n<status>completed</status>\n<summary>Agent \"x\" finished</summary>\n</task-notification>"
WAIT = "<task-notification>\n<task-id>a1</task-id>\n<status>completed</status>\n<summary>Agent \"x\" is waiting on its own background helpers</summary>\n</task-notification>"
FROM_WRITER = f'Another Claude session sent a message:\n<cross-session-message from="{WRITER}" from-name="Roadmap writer">\nDone: row x changed.\n</cross-session-message>'
FROM_BUILDER = 'Another Claude session sent a message:\n<cross-session-message from="local_123" from-name="Builder">\nFinished: merged.\n</cross-session-message>'
EVENT = "<side-sessions-event>finished</side-sessions-event>"
WRITER_DONE = finished_note("Roadmap writer", WRITER) + EVENT
WRITER_AND_BUILDER_DONE = finished_note("Roadmap writer", WRITER) + finished_note("Builder", "local_123") + EVENT
HELPER_DONE = finished_note("Builder", "local_123") + EVENT

# ---- tell the writer first is a reminder: a helper start before the writer is told goes ahead and is reminded ----
fresh(); user()
check("user spoke, helper start goes ahead (a reminder, not a refusal)", start(), 0)
check("user spoke, message to a helper goes ahead", send("a0123456789abcdef"), 0)
check("user spoke, a new session goes ahead", new_session("Build the thing"), 0)
check("user spoke, Workflow goes ahead", run("PreToolUse", tool_name="Workflow", tool_input={}), 0)
check("starting a replacement writer by title goes", new_session("Roadmap writer"), 0)
check("starting a replacement writer by name goes", new_session("Keeps the roadmap", name="roadmap-writer"), 0)
check("message to the writer by id goes", send(WRITER), 0)
check("message to the writer by name goes", send("roadmap-writer"), 0)
check("message to the writer by name and ref goes", send("Roadmap writer [3fa9c1]"), 0)
check("send_message to the writer goes", send(WRITER, tool="mcp__ccd_session_mgmt__send_message"), 0)
check("user spoke, Stop not held (no helper report)", stop(), 0)
check("started before the writer was told: reminded at the next message", "told the plan" in (nudge() or ""), True)
check("the same start is reminded once only", nudge(), None)
send(WRITER, post=True)
check("writer told, helper start goes", start(), 0)
check("writer told first: no reminder", nudge(), None)
check("a pure idle subscription to the writer is not a message", rb.to_writer({"tool_name": "SendMessage", "tool_input": {"to": WRITER, "notify_when_idle": True}}, cfg), False)

# ---- a report not forwarded: nothing is held; the next message reminds to forward it ----
fresh(); send(WRITER, post=True); started("a1"); run("SubagentStop", agent="a1", stop_hook_active=False)
check("report, no forward: Stop not held", stop(), 0)
check("report, no forward: helper start goes ahead", start(), 0)
check("report, no forward: message to another session goes ahead", send("someone-else"), 0)
check("report, no forward: reminded at the next message", "Forward it to the Roadmap writer" in (nudge() or ""), True)
fresh(); send(WRITER, post=True); started("a1"); run("SubagentStop", agent="a1", stop_hook_active=False)
send(WRITER, post=True)
check("forwarded: Stop goes", stop(), 0)
check("forwarded: no reminder", nudge(), None)

# ---- a report arriving as prompt text; the writer's own notes are not reports ----
for name, text, want in (("task-notification completed", NOTE, True), ("helper still waiting on its own helpers", WAIT, False),
                         ("agent-message", '<agent-message from="a1">done</agent-message>', True),
                         ("side-sessions-event", EVENT, True),
                         ("writer's message", FROM_WRITER, False), ("another session's message", FROM_BUILDER, True),
                         ("delivery notice", "[Cross-session delivery notice] held for approval", False),
                         ("writer's end-of-turn note alone", WRITER_DONE, False),
                         ("writer's and another session's end-of-turn notes", WRITER_AND_BUILDER_DONE, True),
                         ("helper session's end-of-turn note", HELPER_DONE, True)):
    fresh(); send(WRITER, post=True)
    check(name + ": reminded to forward it", "Forward it to the Roadmap writer" in (nudge(text) or ""), want)
    check(name + ": Stop never held", stop(), 0)
check("the user's text is the user's", rb.classify_prompt("Yes, 1a.", {}), "user")
check("writer's message is not the user's", rb.classify_prompt(FROM_WRITER, cfg), None)
check("writer's end-of-turn note is neither", rb.classify_prompt(WRITER_DONE, cfg), None)
check("writer's note named by name only", rb.classify_prompt(finished_note("roadmap-writer", "x").replace(" (x)", "") + EVENT, cfg), None)
check("writer's note plus another is a report", rb.classify_prompt(WRITER_AND_BUILDER_DONE, cfg), "report")
check("helper's note is a report", rb.classify_prompt(HELPER_DONE, cfg), "report")

# ---- a foreground helper's completed result is the report ----
fresh(); send(WRITER, post=True); started("a2", status="completed")
check("foreground helper finished: reminded to forward it", "Forward it to the Roadmap writer" in (nudge() or ""), True)

# ---- a helper's own helper finishing is not a report to the main session ----
fresh(); send(WRITER, post=True); run("SubagentStop", agent="a9", stop_hook_active=False)
check("nested helper finished: Stop goes", stop(), 0)
check("nested helper finished: no reminder", nudge(), None)

# ---- helpers and other sessions are never blocked or logged as the main session ----
fresh(); user(); started("a4", status="completed")
check("helper starts its own helper", start(agent="a4"), 0)
check("helper messages main", send("main", agent="a4"), 0)
check("helper's Stop", stop(agent="a4"), 0)
check("writer session messages anyone", send("someone", session=WRITER_CC), 0)
check("another session starts a helper", start(session="builder-session"), 0)
check("writer session's Stop", stop(session=WRITER_CC), 0)
fresh(); send(WRITER, post=True); user(session="other-session"); started("a5", status="completed", agent="a4")
check("other session's prompt and helper's helper leave the main session free", start(), 0)
check("other tools are not touched", run("PreToolUse", tool_name="Read", tool_input={"file_path": "x"}), 0)
fresh(); started("a6", session="other-session")
check("a helper started by another session is not the main session's", rb.load_json(LOG, {}).get("helpers"), None)

# ---- the reminder ----
check("reminder: main session gets its job and the questions check", len(reminder.lines({"session_id": DIR}, cfg)), 2)
check("reminder: names the project's own page", "https://claude.ai/artifact/EXAMPLE" in reminder.lines({"session_id": DIR}, cfg)[1], True)
check("reminder: names the answered questions, the marks and the open notes", all(w in reminder.lines({"session_id": DIR}, cfg)[1] for w in ("'questions'", "'answered'", "'marks'", "'notes'", "'open'")), True)
check("reminder: writer gets its job", "Roadmap writer" in " ".join(reminder.lines({"session_id": WRITER_CC}, cfg)), True)
check("reminder: a helper gets nothing", reminder.lines({"session_id": DIR, "agent_id": "a1"}, cfg), [])
check("reminder: another session gets nothing", reminder.lines({"session_id": "other"}, cfg), [])

# ---- the lock on the safeguards (plugin folder stood in by a made-up one) ----
PLUG = os.path.join(TMP, "plugins", "roadmap")
lock = gbk.Lock(cfg, PLUG)
for name, d, want in (
        ("Edit a guard switch in the plugin", {"tool_name": "Edit", "tool_input": {"file_path": os.path.join(PLUG, "hooks", "hooks.json")}}, True),
        ("Edit the roadmap holds in the plugin (an ordinary file now)", {"tool_name": "Edit", "tool_input": {"file_path": os.path.join(PLUG, "hooks", "roadmap_blocks.py")}}, False),
        ("Write the ids", {"tool_name": "Write", "tool_input": {"file_path": os.path.join(P, ".claude", "roadmap", "config.json")}}, False),
        ("Write the ids by a relative path", {"tool_name": "Write", "tool_input": {"file_path": ".claude/roadmap/config.json"}, "cwd": P}, False),
        ("Write the logbook", {"tool_name": "Write", "tool_input": {"file_path": os.path.join(P, ".claude", "roadmap", "log.json")}}, False),
        ("Write settings", {"tool_name": "Write", "tool_input": {"file_path": ".claude/settings.json"}, "cwd": P}, True),
        ("Write local settings", {"tool_name": "Write", "tool_input": {"file_path": ".claude/settings.local.json"}, "cwd": P}, True),
        ("Write a project file", {"tool_name": "Write", "tool_input": {"file_path": os.path.join(P, "Work List.md")}}, False),
        ("Write the page copy", {"tool_name": "Write", "tool_input": {"file_path": os.path.join(P, "Roadmap page", "roadmap.html")}}, False),
        ("Write the plain copy of the facts", {"tool_name": "Write", "tool_input": {"file_path": os.path.join(P, "Roadmap page", "roadmap.json")}}, False),
        ("Edit the plain copy by a relative path", {"tool_name": "Edit", "tool_input": {"file_path": "Roadmap page/roadmap.json"}, "cwd": P}, False),
        ("Write another .claude file", {"tool_name": "Write", "tool_input": {"file_path": os.path.join(P, ".claude", "notes.json")}}, False)):
    check(name, bool(lock.decide(d)), want)
check("settings unlocked when the project says so", bool(gbk.Lock({"lock_settings": False}, PLUG).decide(
    {"tool_name": "Write", "tool_input": {"file_path": ".claude/settings.json"}, "cwd": P})), False)
check("ids stay locked when settings are unlocked", bool(gbk.Lock({"lock_settings": False}, PLUG).decide(
    {"tool_name": "Write", "tool_input": {"file_path": ".claude/roadmap/config.json"}, "cwd": P})), False)
plug = PLUG.replace("\\", "/")
for cmd, want in (("Set-Content .claude\\roadmap\\config.json 'a'", False), ("echo a > .claude/settings.json", True),
                  ("cp x.py \"" + plug + "/hooks/x.py\"", False), ("cp x.py \"" + plug + "/hooks/guard_blocks.py\"", True), ("Remove-Item .claude\\roadmap\\config.json", False),
                  ("Remove-Item -Recurse .claude\\roadmap", False), ("rm -rf \"" + plug + "\"", True),
                  ("python -c \"open('.claude/roadmap/log.json','w')\"", False), ("git checkout main -- .claude/settings.json", True),
                  ("sed -i s/a/b/ .claude/roadmap/config.json", False), ("echo {} >> .claude/roadmap/log.json", False),
                  ("cd .claude/roadmap; Remove-Item log.json", False),
                  ("python \"" + plug + "/scripts/roadmap_setup.py\" director; rm .claude/roadmap/log.json", False),
                  ("cat .claude/roadmap/config.json", False), ("Get-Content .claude\\settings.json", False),
                  ("git diff -- .claude/settings.json", False), ("git add .claude/settings.json", False),
                  ("python \"" + plug + "/hooks/test_roadmap_blocks.py\" 2>&1", False),
                  ("python \"" + plug + "/scripts/roadmap_setup.py\" director", False),
                  ("python \"" + plug + "/scripts/roadmap_setup.py\" copy-page --title \"House move plan\"", False),
                  ("python \"" + plug + "/scripts/roadmap_setup.py\" writer --id local_1 --name roadmap-writer --title \"Roadmap writer\"", False),
                  ("python \"" + plug + "/scripts/roadmap_setup.py\" facts", False),
                  ("python \"" + plug + "/scripts/roadmap_setup.py\" plain-copy on", False),
                  ("python \"" + plug + "/scripts/roadmap_setup.py\" switch-off", False),
                  ("python \"" + plug + "/scripts/roadmap_setup.py\" --project . switch-on", False),
                  ("echo a > notes.txt", False), ("git status", False),
                  # prose that only mentions a safeguard, while writing a markdown doc, is not a write to it
                  ("Set-Content docs\\notes.md \"The lock keeps .claude/settings.json and .claude\\roadmap\\config.json safe.\"", False),
                  ("cat > docs/notes.md <<'EOF'\nNever edit .claude/settings.json or .claude/roadmap/config.json by hand.\nEOF", False),
                  ("python -c \"open('docs/notes.md','w').write('the roadmap config lives in .claude/roadmap/config.json')\"", False),
                  ("Set-Content .claude\\roadmap\\notes.md 'a'", False), ("Set-Content .claude\\settings.json '{}'", True)):
    check(cmd, bool(lock.decide({"tool_name": "PowerShell", "tool_input": {"command": cmd}, "cwd": P})), want)
if os.name == "nt" and len(plug) > 2 and plug[1] == ":":
    bash_form = "/" + plug[0].lower() + plug[2:]
    check("plugin folder written the Git Bash way is still locked", bool(lock.decide(
        {"tool_name": "Bash", "tool_input": {"command": "rm " + bash_form + "/hooks/guard_blocks.py"}, "cwd": P})), True)
script = os.path.join(TMP, "probe.py")
with open(script, "w", encoding="utf-8") as fh:
    fh.write("open(r'.claude/roadmap/config.json', 'w').write('x')\n")
check("a script that writes the ids", bool(lock.decide({"tool_name": "Bash", "tool_input": {"command": f'python "{script}"'}, "cwd": P})), False)
with open(script, "w", encoding="utf-8") as fh:
    fh.write("import subprocess\nsubprocess.run(['python', r'" + os.path.join(PLUG, "scripts", "roadmap_setup.py") + "', 'switch-off'])\n")
check("a script that switches the arrangement off", bool(lock.decide({"tool_name": "Bash", "tool_input": {"command": f'python "{script}"'}, "cwd": P})), False)

# ---- the hooks as Claude Code runs them: a real process, JSON in, exit code out ----
def as_process(script_name, data, project=P):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=project)
    r = subprocess.run([sys.executable, os.path.join(HERE, script_name)], input=json.dumps(data), capture_output=True, text=True, env=env)
    return r.returncode, r.stdout, r.stderr

fresh()
as_process("roadmap_blocks.py", {"hook_event_name": "UserPromptSubmit", "session_id": DIR, "cwd": P, "prompt": "Go."})
code, _, err = as_process("roadmap_blocks.py", {"hook_event_name": "PreToolUse", "session_id": DIR, "cwd": P, "tool_name": "Agent", "tool_input": {"prompt": "x"}})
check("run as a process: helper start goes ahead with exit code 0", (code, err), (0, ""))
code, out, _ = as_process("roadmap_blocks.py", {"hook_event_name": "UserPromptSubmit", "session_id": DIR, "cwd": P, "prompt": "Next."})
check("run as a process: the reminder is printed as the message's context, exit 0", (code, "told the plan" in out), (0, True))
code, _, _ = as_process("roadmap_blocks.py", {"hook_event_name": "PreToolUse", "session_id": DIR, "cwd": P, "tool_name": "SendMessage", "tool_input": {"to": WRITER, "message": "Plan: x."}})
check("run as a process: message to the writer goes", code, 0)
code, out, _ = as_process("reminder.py", {"hook_event_name": "UserPromptSubmit", "session_id": DIR, "cwd": P, "prompt": "Go."})
check("run as a process: reminder prints for the main session", (code, "assistant:roadmap-director" in out), (0, True))
code, _, err = as_process("guard_blocks.py", {"hook_event_name": "PreToolUse", "session_id": "x", "cwd": P, "tool_name": "Write", "tool_input": {"file_path": ".claude/settings.json"}})
check("run as a process: the lock refuses with exit code 2", (code, err.startswith("Refused:")), (2, True))
empty = os.path.join(TMP, "Untouched Project")
os.makedirs(empty)
code, out, err = as_process("roadmap_blocks.py", {"hook_event_name": "PreToolUse", "session_id": DIR, "cwd": empty, "tool_name": "Agent", "tool_input": {}}, project=empty)
check("run as a process: a project that is not set up is untouched", (code, out, err, os.listdir(empty)), (0, "", "", []))

# ---- switching the arrangement off and on: the person's alone; with it off every hook stands down ----
def switch(cmd, claude):
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_PROJECT_DIR")}
    if claude:
        env["CLAUDECODE"] = "1"
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "roadmap_setup.py"), "--project", P, cmd], capture_output=True, text=True, env=env)
    return r.returncode == 0 and "Refused" not in r.stderr

check("switch-off run inside Claude goes through: the arrangement put aside, no saved copy made",
      (switch("switch-off", True), os.path.isfile(CFG), os.path.isdir(os.path.join(P, ".claude", "roadmap-off")),
       os.path.exists(os.path.join(P, ".claude", "roadmap-saved"))), (True, False, True, False))
code, _, _ = as_process("roadmap_blocks.py", {"hook_event_name": "UserPromptSubmit", "session_id": DIR, "cwd": P, "prompt": "Go."})
code2, _, _ = as_process("roadmap_blocks.py", {"hook_event_name": "PreToolUse", "session_id": DIR, "cwd": P, "tool_name": "Agent", "tool_input": {"prompt": "x"}})
check("switched off: the blocks stand down and write nothing", (code, code2, os.path.isdir(os.path.join(P, ".claude", "roadmap"))), (0, 0, False))
code, _, _ = as_process("guard_blocks.py", {"hook_event_name": "PreToolUse", "session_id": "x", "cwd": P, "tool_name": "Write", "tool_input": {"file_path": ".claude/settings.json"}})
check("switched off: the lock stands down", code, 0)
check("switch-on brings it back as it was", (switch("switch-on", True), rb.load_json(CFG, {}).get("director_session_id"), rb.active(rb.load_json(CFG, {}))), (True, DIR, True))
as_process("roadmap_blocks.py", {"hook_event_name": "UserPromptSubmit", "session_id": DIR, "cwd": P, "prompt": "Go."})
as_process("roadmap_blocks.py", {"hook_event_name": "PreToolUse", "session_id": DIR, "cwd": P, "tool_name": "Agent", "tool_input": {"prompt": "x"}})
code, out, _ = as_process("roadmap_blocks.py", {"hook_event_name": "UserPromptSubmit", "session_id": DIR, "cwd": P, "prompt": "Next."})
check("switched back on: the reminder works again", (code, "told the plan" in out), (0, True))

# ---- the lock also covers the project's own hook scripts, and refuses putting changed settings in place ----
check("Write a project hook script", bool(lock.decide({"tool_name": "Write", "tool_input": {"file_path": ".claude/hooks/guard.py"}, "cwd": P})), True)
check("a command that deletes a project hook script", bool(lock.decide({"tool_name": "PowerShell", "tool_input": {"command": "Remove-Item .claude\\hooks\\guard.py"}, "cwd": P})), True)
check("running a project hook's own test stays allowed", bool(lock.decide({"tool_name": "PowerShell", "tool_input": {"command": "python .claude/hooks/test_guards.py"}, "cwd": P})), False)
check("hook scripts unlocked when the project unlocks its settings", bool(gbk.Lock({"lock_settings": False}, PLUG).decide(
    {"tool_name": "Write", "tool_input": {"file_path": ".claude/hooks/guard.py"}, "cwd": P})), False)
for cmd, want in (("python \"" + plug + "/scripts/roadmap_setup.py\" old-locks", False),
                  ("python \"" + plug + "/scripts/roadmap_setup.py\" existing", False),
                  ("python \"" + plug + "/scripts/roadmap_setup.py\" carry-over \"C:/tmp/saved\" --write-to \"C:/tmp/changes\"", False),
                  ("python \"" + plug + "/scripts/roadmap_setup.py\" old-locks --apply", False),
                  ("python \"" + plug + "/scripts/roadmap_setup.py\" --project . old-locks --apply", False)):
    check(cmd, bool(lock.decide({"tool_name": "PowerShell", "tool_input": {"command": cmd}, "cwd": P})), want)

# ---- taking over a roadmap made before the plugin: the report on a saved database ----
import contextlib, hashlib, io

def said(fn, *args):
    """(what the command returned or how it stopped, everything it printed)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            code = fn(*args)
        except SystemExit as e:
            code = "stopped: " + str(e.code)
    return code, out.getvalue()

def save_docs(folder, docs):
    for path, doc in docs.items():
        full = os.path.join(folder, *path.split("/")) + ".json"
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)

OLD = os.path.join(TMP, "old export")
save_docs(OLD, {
    "steps/step-01": {"order": 10, "kind": "step", "number": "1", "name": "Dig", "parent": "", "status": "Done, confirmed by Sam", "waits_on_sam": "Nothing."},
    "steps/phase-1a": {"order": 15, "kind": "phase", "number": "", "name": "Mark out", "parent": "step-01", "status": "In the garden, waiting for Sam's look",
                       "waits_on_sam": "A look.", "checks": [{"id": "c1", "text": "Open the gate. Walk the line. See pegs every metre."}]},
    "steps/tool-barrow": {"order": 300, "kind": "tool", "number": "", "name": "Barrow", "parent": "", "status": "First pass in the shed, to be rebuilt", "waits_on_sam": "Nothing.",
                          "scores_title": "Loads", "scores": [{"set": "Monday", "loads": 4, "spilt": 1, "note": "wet"}, {"set": "Tuesday", "loads": 6, "spilt": None}]},
    "steps/step-02": {"order": 20, "kind": "step", "number": "2", "name": "Plant", "parent": "", "status": "Planned, not started", "waits_on_you": "nothing", "extra": 1},
    "marks/phase-1a--c1": {"row": "phase-1a", "check": "c1", "text": "x", "result": "works", "note": "", "marked": "2026-03-04T10:05:00Z"},
    "marks/step-01--c9": {"row": "step-01", "check": "c9", "text": "x", "result": "works", "note": "", "marked": "2026-03-04T10:05:00Z"},
    "questions/q-step-02-what": {"row": "step-02", "topic": "What", "question": "Roses or beans?", "status": "answered", "answer": "Beans", "pictures": [{"url": "/_blob/abc", "caption": "The bed"}]},
    "board/next": {"facts_as_of": "2026-03-04", "lines": [{"label": "Next", "text": "Plant"}]}})
changes, notes, stops = setup.carry_plan(setup.read_export(OLD))
by = {doc_id: data for _, doc_id, _, data in changes}
check("carry-over: only the rows that differ are listed", sorted(by), ["phase-1a", "step-01", "tool-barrow"])
check("carry-over: a status in other words becomes the one it means", (by["step-01"]["status"], by["phase-1a"]["status"], by["tool-barrow"]["status"]),
      ("Done, confirmed", "Ready, waiting for your look", "First pass, to be redone"))
check("carry-over: waits_on_<name> becomes waits_on_you and the old field goes", (by["step-01"]["waits_on_you"], by["step-01"]["waits_on_sam"]), ("Nothing.", {"__delete__": True}))
check("carry-over: a kind that is not step or phase becomes item", by["tool-barrow"]["kind"], "item")
check("carry-over: a score list becomes the table, its naming column first", (by["tool-barrow"]["table"]["columns"], by["tool-barrow"]["table"]["rows"][0], by["tool-barrow"]["table"]["title"],
      by["tool-barrow"]["scores"], by["tool-barrow"]["scores_title"]),
      (["Set", "Loads", "Spilt"], {"Set": "Monday (wet)", "Loads": 4, "Spilt": 1}, "Loads", {"__delete__": True}, {"__delete__": True}))
check("carry-over: no mark, answer or picture is in any write", [c for c, _, _, _ in changes if c != "steps"], [])
check("carry-over: nothing it cannot settle", stops, [])
check("carry-over: says what is kept but not shown", (any("1 marks are for checks no longer" in n for n in notes), any('"extra"' in n for n in notes)), (True, True))
before = {f: open(os.path.join(dp, f), "rb").read() for dp, _, fs in os.walk(OLD) for f in fs}
code, text = said(setup.main, ["carry-over", OLD])
check("carry-over as a command: lists the changes and writes nothing", (code, "TO CHANGE: 3 documents" in text, "Nothing was written." in text,
      before == {f: open(os.path.join(dp, f), "rb").read() for dp, _, fs in os.walk(OLD) for f in fs}), (0, True, True, True))
OUT = os.path.join(TMP, "changed fields")
code, text = said(setup.main, ["carry-over", OLD, "--write-to", OUT])
check("carry-over --write-to: one file a changed document, and the batches", (code, sorted(os.listdir(os.path.join(OUT, "steps"))),
      [e["doc_id"] for e in rb.load_json(os.path.join(OUT, "batches.json"), {})["batches"][0]], rb.load_json(os.path.join(OUT, "steps", "step-01.json"), {})),
      (0, ["phase-1a.json", "step-01.json", "tool-barrow.json"], ["phase-1a", "step-01", "tool-barrow"], by["step-01"]))
check("carry-over --write-to inside the export is refused", said(setup.main, ["carry-over", OLD, "--write-to", os.path.join(OLD, "x")])[0].startswith("stopped: Not written"), True)
# after the changes are applied, and on a roadmap the plugin made, there is nothing to change
DONE_EXPORT = os.path.join(TMP, "after export")
after = {}
for name, docs in setup.read_export(OLD).items():
    for doc_id, doc in docs.items():
        doc = dict(doc)
        for k, v in by.get(doc_id, {}).items() if name == "steps" else ():
            if v == {"__delete__": True}:
                doc.pop(k, None)
            else:
                doc[k] = v
        after[name + "/" + doc_id] = doc
save_docs(DONE_EXPORT, after)
code, text = said(setup.main, ["carry-over", DONE_EXPORT])
check("carry-over: says nothing needs to change once carried over", (code, "Nothing needs to change" in text, "TO CHANGE" in text), (0, True, False))
BAD = os.path.join(TMP, "bad export")
save_docs(BAD, {"steps/step-01": {"order": "first", "kind": "step", "name": "Dig", "status": "Half way"},
                "marks/odd": {"row": "step-01", "check": "c1", "result": "maybe"}})
code, text = said(setup.main, ["carry-over", BAD])
check("carry-over: what it cannot place is left for the person, and the command says so", (code, "NOT SETTLED BY THIS COMMAND" in text, "Half way" in text, "marks/odd" in text), (1, True, True, True))
check("carry-over: a folder with no saved rows is refused", said(setup.main, ["carry-over", TMP])[0].startswith("stopped: Not read"), True)

# ---- finding the older roadmap, and retiring its locks by a copy-in the person pastes ----
Q = os.path.join(TMP, "Garden Project")
os.makedirs(os.path.join(Q, ".claude", "hooks"))
os.makedirs(os.path.join(Q, "Roadmap page"))
with open(os.path.join(Q, "Roadmap page", "How to update.md"), "w", encoding="utf-8") as fh:
    fh.write("Page: https://claude.ai/artifact/MadeUpGardenPage1\n")
with open(os.path.join(Q, "Roadmap page", "Garden Roadmap.html"), "w", encoding="utf-8") as fh:
    fh.write("<title>Garden Roadmap</title>")
with open(os.path.join(Q, ".claude", "old_blocks.json"), "w", encoding="utf-8") as fh:
    json.dump({"director_session_id": "made-up-old-main", "writer": {"session_id": "local_made-up-old-writer"}}, fh)
for name, text in (("old_blocks.py", "# holds the main session to the Roadmap writer\n"), ("old_guard.py", "# protects the roadmap blocks\n"),
                   ("folders.py", "# keeps work inside the project\n")):
    with open(os.path.join(Q, ".claude", "hooks", name), "w", encoding="utf-8") as fh:
        fh.write(text)
hook = lambda name: {"type": "command", "command": "\"python\" \"" + os.path.join(Q, ".claude", "hooks", name).replace("\\", "/") + "\"", "timeout": 30}
OLD_SETTINGS = json.dumps({"permissions": {"deny": ["Edit(**/.claude/hooks/**)"]}, "hooks": {
    "UserPromptSubmit": [{"hooks": [hook("old_blocks.py")]}],
    "PreToolUse": [{"matcher": "Bash|PowerShell", "hooks": [hook("folders.py")]}, {"matcher": "Write|Edit", "hooks": [hook("old_guard.py"), hook("folders.py")]},
                   {"matcher": "Agent", "hooks": [hook("old_blocks.py")]}],
    "Stop": [{"hooks": [hook("old_blocks.py")]}]}}, indent=2) + "\n"
QS = os.path.join(Q, ".claude", "settings.json")
with open(QS, "w", encoding="utf-8", newline="") as fh:
    fh.write(OLD_SETTINGS)
sha = lambda path: hashlib.sha256(open(path, "rb").read()).hexdigest()
was_sha = sha(QS)
code, text = said(setup.main, ["--project", Q, "existing"])
check("existing: finds the old page's link, name, writer and locks, and writes nothing", (code, "https://claude.ai/artifact/MadeUpGardenPage1" in text, "Garden Roadmap" in text,
      "local_made-up-old-writer" in text, "4 hook lines" in text, os.path.exists(os.path.join(Q, ".claude", "roadmap"))), (0, True, True, True, True, False))
code, text = said(setup.main, ["--project", os.path.join(TMP, "Untouched Project"), "existing"])
check("existing: a project with no roadmap says so", (code, "no link found" in text), (0, True))
code, text = said(setup.main, ["--project", P, "existing"])
check("existing: a project the plugin set up has nothing to take over", "nothing to take over" in text, True)
code, text = said(setup.main, ["--project", Q, "old-locks"])
COPY = os.path.join(Q, "Plugin update copy-in", "Retire the old roadmap locks")
new_settings = rb.load_json(os.path.join(COPY, "settings.json"), {})
ran = sorted(os.path.basename(h["command"].strip('"').split('"')[-1]) for groups in new_settings["hooks"].values() for g in groups for h in g["hooks"])
check("old-locks: writes the copy-in and changes nothing in .claude", (code, sha(QS) == was_sha, sha(os.path.join(COPY, "as it was", "settings.json")) == was_sha,
      os.path.isfile(os.path.join(COPY, "What changes.md")), "Copy-Item" in text), (0, True, True, True, True))
check("old-locks: the changed settings run only the hooks that are not roadmap locks", (ran, sorted(new_settings["hooks"]), new_settings["permissions"]),
      (["folders.py", "folders.py"], ["PreToolUse"], {"deny": ["Edit(**/.claude/hooks/**)"]}))
env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_PROJECT_DIR")}
script = os.path.join(ROOT, "scripts", "roadmap_setup.py")
r = subprocess.run([sys.executable, script, "--project", Q, "old-locks", "--apply"], capture_output=True, text=True, env=dict(env, CLAUDECODE="1"))
check("old-locks --apply inside Claude puts the changed settings in place", (r.returncode, sha(QS) == sha(os.path.join(COPY, "settings.json")), setup.find_old_locks(Q)), (0, True, []))
code, text = said(setup.main, ["--project", Q, "old-locks"])
check("old-locks afterwards: nothing to retire, the settings as they were are still kept", (code, "Nothing to retire" in text, sha(os.path.join(COPY, "as it was", "settings.json")) == was_sha), (0, True, True))
import shutil as _sh
_sh.copyfile(os.path.join(COPY, "as it was", "settings.json"), QS)
check("putting back gives the settings byte for byte as they were", sha(QS), was_sha)
check("the plugin's own hook lines are never taken for old locks", setup._old_lock_scripts('python "${CLAUDE_PLUGIN_ROOT}/hooks/roadmap_blocks.py"', Q), [])

# ---- the working copy the skills run, in the plugin's own data folder ----
import working_copy, glob as _glob
DATA = os.path.join(TMP, "home", ".claude", "plugins", "data", "roadmap-made-up")
check("working copy: nothing is copied when Claude Code names no data folder", working_copy.sync(dest=None) if not os.environ.get("CLAUDE_PLUGIN_DATA") else [], [])
check("working copy: first run writes every file", sorted(working_copy.sync(DATA)), sorted(working_copy.FILES))
same = all(open(os.path.join(DATA, f), "rb").read() == open(os.path.join(ROOT, f), "rb").read() for f in working_copy.FILES)
check("working copy: each file is the plugin's own, byte for byte", same, True)
check("working copy: a second run writes nothing", working_copy.sync(DATA), [])
with open(os.path.join(DATA, "reference", "database.md"), "a", encoding="utf-8") as fh:
    fh.write("changed")
check("working copy: a file that differs is put right, the others left", working_copy.sync(DATA), ["reference/database.md"])
check("working copy: the plugin's own folder is never copied onto itself", working_copy.sync(ROOT), [])
copy_script = os.path.join(DATA, "scripts", "roadmap_setup.py")
r = subprocess.run([sys.executable, copy_script, "--project", P, "status"], capture_output=True, text=True, env=env)
r0 = subprocess.run([sys.executable, script, "--project", P, "status"], capture_output=True, text=True, env=env)
check("working copy: the script run from the copy prints what the plugin's own prints", (r.returncode, r.stdout), (r0.returncode, r0.stdout))
E = os.path.join(TMP, "Copy Project")
os.makedirs(E)
r = subprocess.run([sys.executable, copy_script, "--project", E, "copy-page", "--title", "Copy Roadmap"], capture_output=True, text=True, env=env)
check("working copy: copy-page from the copy writes the page", (r.returncode, os.path.isfile(os.path.join(E, "Roadmap page", "roadmap.html"))), (0, True))
lock = gbk.Lock(rb.load_json(CFG, {}), ROOT, DATA)
for form, cmd in (("forward slashes", 'python "' + copy_script.replace("\\", "/") + '" status'),
                  ("backslashes", 'python "' + copy_script + '" director'),
                  ("carry-over with two folders", 'python "' + copy_script.replace("\\", "/") + '" carry-over "C:/x/old roadmap" --write-to "C:/x/changes"')):
    d = {"cwd": P, "tool_name": "PowerShell", "tool_input": {"command": cmd}}
    check("lock: the setup script run from the working copy is allowed, " + form, lock.decide(d), None)
d = {"cwd": P, "tool_name": "PowerShell", "tool_input": {"command": 'python "' + copy_script + '" status; del x'}}
check("lock: the working copy's script with something chained is not taken for a plain setup run", lock.own_setup(d["tool_input"]["command"]), False)
d = {"cwd": P, "tool_name": "Write", "tool_input": {"file_path": copy_script, "content": "x"}}
check("lock: a file tool cannot change the working copy", bool(lock.decide(d)), False)
d = {"cwd": P, "tool_name": "PowerShell", "tool_input": {"command": 'Set-Content "' + copy_script + '" "x"'}}
check("lock: a terminal command cannot change the working copy", bool(lock.decide(d)), False)
d = {"cwd": P, "tool_name": "PowerShell", "tool_input": {"command": 'python "' + copy_script + '" --project "' + P + '" old-locks --apply'}}
check("lock: old-locks --apply from the working copy is still refused", bool(lock.decide(d)), False)
# ---- the lock covers only the safeguard scripts: ordinary plugin files can be edited and committed ----
for name, path, want in (("an ordinary engine file in the plugin", os.path.join(ROOT, "engine", "made_up.py"), False),
                         ("an ordinary skill in the working copy", os.path.join(DATA, "skills", "made-up", "SKILL.md"), False),
                         ("the docs in the plugin", os.path.join(ROOT, "docs", "changes.md"), False),
                         ("the lock itself", os.path.join(ROOT, "hooks", "guard_blocks.py"), True),
                         ("the roadmap holds", os.path.join(ROOT, "hooks", "roadmap_blocks.py"), False),
                         ("the copy the lock loads, in the working copy", os.path.join(DATA, "hooks", "working_copy.py"), False),
                         ("what turns the hooks on", os.path.join(ROOT, "hooks", "hooks.json"), True),
                         ("setup in the working copy", os.path.join(DATA, "scripts", "roadmap_setup.py"), False)):
    check("lock: Edit " + name, bool(lock.decide({"cwd": P, "tool_name": "Edit", "tool_input": {"file_path": path}})), want)
rootf = ROOT.replace("\\", "/")
for cmd, want in (("git add engine/made_up.py; git commit -m \"Made-up change\"", False),
                  ("Set-Content engine/made_up.py \"x\"", False),
                  ("Set-Content hooks/guard_blocks.py \"x\"", True),
                  ("rm -rf hooks", True),
                  ("Remove-Item -Recurse \"" + rootf + "\"", True)):
    check("lock, run in the plugin folder: " + cmd, bool(lock.decide({"cwd": ROOT, "tool_name": "PowerShell", "tool_input": {"command": cmd}})), want)
# ordinary git work in the plugin repo goes through from a set-up project; the roadmap's own files stay locked
for cmd, want in (("git -C \"" + rootf + "\" merge made-up-branch", False),
                  ("git -C \"" + rootf + "\" checkout main", False),
                  ("git -C \"" + rootf + "\" apply made-up.patch", False),
                  ("git -C \"" + rootf + "\" checkout main -- hooks/guard_blocks.py", True),
                  ("git rm .claude/roadmap/log.json", False),
                  ("cd $MADE_UP_DIR; rm notes.txt", False),
                  ("cd $MADE_UP_DIR; rm guard_blocks.py", False)):
    check("lock, from a set-up project: " + cmd, bool(lock.decide({"cwd": P, "tool_name": "Bash", "tool_input": {"command": cmd}})), want)
check("lock, from a set-up project: a file tool write to .claude\\roadmap is still refused",
      bool(lock.decide({"cwd": P, "tool_name": "Write", "tool_input": {"file_path": os.path.join(P, ".claude", "roadmap", "log.json"), "content": "{}"}})), False)
named = [os.path.relpath(f, ROOT) for f in _glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md")) + _glob.glob(os.path.join(ROOT, "reference", "*.md"))
         if "${CLAUDE_PLUGIN_ROOT}" in open(f, encoding="utf-8").read()]
check("no skill or manual tells a session to run or read anything in the plugin's own folder", named, [])
texts = [open(f, encoding="utf-8").read() for f in _glob.glob(os.path.join(ROOT, "skills", "*", "SKILL.md"))]
runs = sum(t.count('python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py"') for t in texts)
check("every setup command in the skills runs the working copy", (runs > 0, runs), (True, sum(t.count("roadmap_setup.py") - t.count("`roadmap_setup.py") for t in texts)))

# ---- /assistant:roadmap-update: bringing a set-up project up to the plugin as it now stands ----
U = os.path.join(TMP, "Update Project")
os.makedirs(U)
UCFG = rb.config_path(U)
PUB = os.path.join(TMP, "published.html")                      # what an Artifact read of the published page saves


def ucmd(session, *argv, note=True):
    """One update command the way a session runs it: the lock hook notes who runs it, then the script runs."""
    d = {"hook_event_name": "PreToolUse", "session_id": session, "cwd": U, "tool_name": "PowerShell",
         "tool_input": {"command": 'python "' + script + '" ' + " ".join(argv)}}
    if note:
        gbk.note_setup_session(d, U)
    return said(setup.main, ["--project", U, *argv])


def publish():
    with open(os.path.join(U, "Roadmap page", "roadmap.html"), encoding="utf-8") as src, open(PUB, "w", encoding="utf-8") as dst:
        dst.write("<!doctype html><html><head><meta charset=utf8>" + src.read())


def tree(folder):
    return {os.path.relpath(os.path.join(dp, f), folder): sha(os.path.join(dp, f)) for dp, _, fs in os.walk(folder) for f in fs}


code, text = ucmd("made-up-update-main", "update")
check("update: refused in a project that is not set up, and nothing at all is written", (str(code).startswith("stopped: Refused"), "/assistant:roadmap-setup" in str(code), tree(U)), (True, True, {}))
code, text = ucmd("made-up-update-main", "updated", "--published", PUB)
check("updated: refused in a project that is not set up, and nothing at all is written", (str(code).startswith("stopped: Refused"), tree(U)), (True, {}))
rb.save_json({"director_session_id": "made-up-update-main", "director_local_id": "local_made-up-update-main", "page_url": "https://claude.ai/artifact/MadeUpUpdatePage", "title": "Update Roadmap",
              "writer": {"session_id": "local_made-up-update-writer", "name": "roadmap-writer", "title": "Roadmap writer"}}, UCFG)
with open(PUB, "w", encoding="utf-8") as fh:
    fh.write("<!doctype html><title>Update Roadmap</title><p>an older page</p>")
was_cfg = sha(UCFG)
code, text = ucmd("made-up-other-session", "update")
check("update: refused from a session that is not the main session, naming the one that is", (str(code).startswith("stopped: Refused"),
      "The main session is made-up-update-main" in str(code), "this session is made-up-other-session" in str(code), sha(UCFG) == was_cfg), (True, True, True, True))
code, text = ucmd("made-up-update-main", "update")
check("update: with no published page given, says where things stand and what to read next, and writes nothing",
      (code, "https://claude.ai/artifact/MadeUpUpdatePage" in text, "not recorded" in text, "--published" in text, sha(UCFG) == was_cfg), (0, True, True, True, True))
code, text = ucmd("made-up-update-main", "update", "--published", PUB)
all_changes = setup.read_changes()
check("the list of changes is numbered in order and has the twelve of 11/16/26", (len(all_changes) >= 12, [n for n, _, _ in all_changes[:12]], {d for _, d, _ in all_changes[:12]}),
      (True, list(range(1, 13)), {"2026-11-16"}))
check("update: an older page and no record: page and instructions behind, every change listed, nothing written",
      (code, "Published page: behind" in text, "Instructions:   behind" in text, "Data layout:    the same" in text, text.count("\n- "), sha(UCFG) == was_cfg),
      (0, True, True, True, len(all_changes), True))
check("update: the to-do names the same link, the title, the writer and its message once, and the record step",
      ('copy-page --title "Update Roadmap"' in text, "url https://claude.ai/artifact/MadeUpUpdatePage" in text, "no capabilities" in text,
       text.count(setup.WRITER_NOTE), "local_made-up-update-writer" in text, "updated --published" in text, "assistant:roadmap-director" in text), (True, True, True, 1, True, True, True))
code, text = ucmd("made-up-update-main", "updated", "--published", PUB)
check("updated: refuses to record while the published page is still the older one", (str(code).startswith("stopped: Not recorded"), sha(UCFG) == was_cfg), (True, True))
ucmd("made-up-update-main", "copy-page", "--title", "Update Roadmap")
publish()
code, text = ucmd("made-up-other-session", "updated", "--published", PUB)
check("updated: refused from a session that is not the main session", (str(code).startswith("stopped: Refused"), "brought_up_to" in rb.load_json(UCFG, {})), (True, False))
code, text = ucmd("made-up-update-main", "updated", "--published", PUB)
mark = rb.load_json(UCFG, {}).get("brought_up_to") or {}
check("updated: records what the project is brought up to", (code, "Recorded" in text, mark.get("change"), mark.get("layout"), mark.get("page")),
      (0, True, all_changes[-1][0], setup.LAYOUT, setup.page_stamp()))
was_cfg = sha(UCFG)
code, text = ucmd("made-up-update-main", "update", "--published", PUB)
check("update again at once: nothing to update, no to-do, no message, nothing written",
      (code, "Nothing to update" in text, "TO DO" in text, setup.WRITER_NOTE in text, "copy-page" in text, sha(UCFG) == was_cfg), (0, True, False, False, False, True))
cfg_u = rb.load_json(UCFG, {})
cfg_u["brought_up_to"]["change"] = 9
rb.save_json(cfg_u, UCFG)
code, text = ucmd("made-up-update-main", "update", "--published", PUB)
listed = [l for l in text.splitlines() if l.startswith("- ")]
check("update: a project last brought up to change 9 is shown exactly the changes after it",
      (len(listed), all(w in "\n".join(listed) for _, _, w in all_changes[9:]), any(w in text for _, _, w in all_changes[:9]), "since change 9" in text, "Republish" in text),
      (len(all_changes) - 9, True, False, True, False))
cfg_u["brought_up_to"].update({"change": all_changes[-1][0], "layout": setup.LAYOUT - 1})
rb.save_json(cfg_u, UCFG)
code, text = ucmd("made-up-update-main", "update", "--published", PUB)
check("update: a changed data layout puts stopping for the person first", (code, "1. STOP FOR THE PERSON FIRST" in text, "carry-over" in text), (0, True, True))
cfg_u["brought_up_to"].update({"layout": setup.LAYOUT, "instructions": "an-older-mark"})
rb.save_json(cfg_u, UCFG)
code, text = ucmd("made-up-update-main", "update", "--published", PUB)
check("update: changed instructions alone: reload and one message, no republish, nothing new for the person",
      (code, "Republish" in text, text.count(setup.WRITER_NOTE), "nothing they would notice" in text), (0, False, 1, True))
cfg_u["writer"]["session_id"] = ""
rb.save_json(cfg_u, UCFG)
code, text = ucmd("made-up-update-main", "update", "--published", PUB)
check("update: no writer recorded: no message, and the person is pointed to start-writer", (setup.WRITER_NOTE in text, "/assistant:roadmap-start-writer" in text), (False, True))
with open(os.path.join(U, "Roadmap page", "roadmap.html"), encoding="utf-8") as fh:
    made = fh.read()
check("copy-page: the copy is the plugin's page with the title and its mark, nothing else",
      made == open(os.path.join(ROOT, "page", "roadmap.html"), encoding="utf-8").read().replace("Project Roadmap", "Update Roadmap")
      .replace("</title>", '</title>\n<meta name="roadmap-plugin-page" content="' + setup.page_stamp() + '">', 1), True)
lock_u = gbk.Lock(rb.load_json(UCFG, {}), ROOT, DATA)
for argv in ("update", 'update --published "C:/x/artifact/index.html"', 'updated --published "C:/x/artifact/index.html"'):
    for root in (ROOT, DATA):
        d = {"cwd": U, "tool_name": "PowerShell", "tool_input": {"command": 'python "' + os.path.join(root, "scripts", "roadmap_setup.py") + '" ' + argv}}
        check("lock: the plugin's own " + argv.split()[0] + " command is allowed", lock_u.decide(d), None)
check("working copy: the list of changes and the two skills update weighs are kept in it",
      all(f in working_copy.FILES for f in ("reference/changes.md", "skills/roadmap-director/SKILL.md", "skills/roadmap-writer/SKILL.md")), True)
working_copy.sync(DATA)
r = subprocess.run([sys.executable, copy_script, "--project", U, "status"], capture_output=True, text=True, env=env)
sys.path.insert(0, os.path.join(DATA, "scripts"))
import importlib.util as _iu
spec = _iu.spec_from_file_location("setup_copy", copy_script)
setup_copy = _iu.module_from_spec(spec)
spec.loader.exec_module(setup_copy)
check("working copy: the copy weighs the page and the instructions the same as the plugin's own",
      (setup_copy.page_stamp(), setup_copy.instructions_mark(), setup_copy.read_changes()), (setup.page_stamp(), setup.instructions_mark(), all_changes))
update_skill = open(os.path.join(ROOT, "skills", "roadmap-update", "SKILL.md"), encoding="utf-8").read()
check("the update skill runs only the working copy and runs only on the person's ask or yes in that session", ("${CLAUDE_PLUGIN_ROOT}" in update_skill, "Only when the person asked for it in this session, or said yes here" in update_skill,
      update_skill.count('python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" update')), (False, True, 2))

# ---- (1) the main session's own id, the one a message can be sent to ----
OWN = "local_made-up-main-own-id"
code, text = ucmd("made-up-update-main", "local-id", "not-an-id")
check("local-id: something that is not a local_ id is stopped and writes nothing", (str(code).startswith("stopped: Not recorded"), rb.load_json(UCFG, {}).get("director_local_id")), (True, "local_made-up-update-main"))
code, text = ucmd("made-up-other-session", "local-id", OWN)
check("local-id: refused from a session that is not the main session", (str(code).startswith("stopped: Refused"), rb.load_json(UCFG, {}).get("director_local_id")), (True, "local_made-up-update-main"))
code, text = ucmd("made-up-update-main", "local-id", OWN)
check("local-id: the main session records its own id, and status shows it", (code, rb.load_json(UCFG, {}).get("director_local_id"), "Its own id:     " + OWN in text), (0, OWN, True))
cfg_n = rb.load_json(UCFG, {})
cfg_n.pop("director_local_id")
rb.save_json(cfg_n, UCFG)
code, text = ucmd("made-up-update-main", "update", "--published", PUB)
check("update: a project with no own id recorded is not 'nothing to update', and is told how to record it",
      (code, "Nothing to update" in text, "local-id <that id>" in text, "get_session" in text, "Its own id:     not recorded" in text), (0, False, True, True, True))
check("update: with only the id behind, no republish and no writer message", ("Republish" in text, setup.WRITER_NOTE in text), (False, False))
code, text = ucmd("made-up-update-main", "local-id", OWN)
code, text = ucmd("made-up-update-main", "update", "--published", PUB)
check("update: once the id is recorded it is no longer on the to-do list", (code, "Its own id:     recorded" in text, "local-id <that id>" in text), (0, True, False))
N = os.path.join(TMP, "Empty Project")
os.makedirs(N)
def ncmd(*argv):
    d = {"hook_event_name": "PreToolUse", "session_id": "made-up-empty-main", "cwd": N, "tool_name": "PowerShell",
         "tool_input": {"command": 'python "' + script + '" ' + " ".join(argv)}}
    gbk.note_setup_session(d, N)
    return said(setup.main, ["--project", N, *argv])
code, before = ncmd("director")
code2, after = ncmd("director", "--local-id", OWN)
old_lines = ["Project:        " + N, "Main session:   made-up-empty-main", "Roadmap writer: not recorded", "Roadmap page:   not recorded", "Roadmap kind:   stepped",
             "Helpers use:    the cheapest model that does the job well", "Plain copy:     off",
             "Blocks:         off until both the main session and the writer are recorded"]
check("setup in an empty project prints what it printed before plus one record line",
      (code, [l for l in before.splitlines() if not l.startswith("Its own id:")], sum(l.startswith("Its own id:") for l in before.splitlines())), (0, old_lines, 1))
check("setup with the id records it, and the line names it", (code2, [l for l in after.splitlines() if not l.startswith("Its own id:")], "Its own id:     " + OWN in after, rb.load_json(rb.config_path(N), {}).get("director_local_id")),
      (0, old_lines, True, OWN))
check("setup: a bad id stops it and leaves the earlier record", (str(ncmd("director", "--local-id", "xyz")[0]).startswith("stopped"), rb.load_json(rb.config_path(N), {}).get("director_local_id")), (True, OWN))
check("the setup skill gives the id at both ways in, and the update skill records it",
      (open(os.path.join(ROOT, "skills", "roadmap-setup", "SKILL.md"), encoding="utf-8").read().count("director --local-id <that id>"),
       "local-id" in open(os.path.join(ROOT, "skills", "roadmap-update", "SKILL.md"), encoding="utf-8").read()), (2, True))

# ---- (2) the one line in the director skill and the manual ----
for f in ("skills/roadmap-director/SKILL.md", "reference/database.md"):
    t = open(os.path.join(ROOT, *f.split("/")), encoding="utf-8").read()
    check("press line in " + f, ("Press from the live page on the roadmap" in t, "once" in t.split("Press from the live page on the roadmap", 1)[1][:900]), (True, True))
check("the change for the person is listed", any("another program's page" in w for _, _, w in setup.read_changes()), True)

# ---- (3) the reminder hook gives presses waiting in from-page.json to the main session, once each ----
R = os.path.join(TMP, "Press Project")
os.makedirs(os.path.join(R, "Roadmap page"))
RCFG, RMAIN = rb.config_path(R), "made-up-press-main"
rb.save_json({"director_session_id": RMAIN, "director_local_id": OWN, "title": "Press Roadmap", "page_url": "https://claude.ai/artifact/PRESS",
              "writer": {"session_id": "local_made-up-press-writer", "name": "roadmap-writer", "title": "Roadmap writer"}}, RCFG)
QUEUE, SENT = os.path.join(R, "Roadmap page", "from-page.json"), reminder.sent_path(R)
W1 = 'Marked on the roadmap: 3 Hang the doors, check c1 "Open the door.": Works. Note: ""'
W2 = 'Note on the roadmap: 3 Hang the doors: "Paint it grey too"'
def queue(**ps):
    rb.save_json({"presses": {i: {"op": "set", "path": "marks/x", "data": {}, "words": w, "at": 1, "sent": s} for i, (w, s) in ps.items()}}, QUEUE)
def given(prompt="Go.", session=RMAIN, **kw):
    return reminder.press_lines({"session_id": session, "prompt": prompt, **kw}, rb.load_json(RCFG, {}), R)
check("presses: no queue file, nothing given and nothing written", (given(), os.path.exists(SENT)), ([], False))
queue(**{"rm:a:1-1": (W1, None), "rm:a:2-1": (W2, None), "rm:a:3-1": ("Answered on the roadmap: question q1", 1700000000)})
check("presses: another session and a helper are given nothing and nothing is marked",
      (given(session="other"), given(agent_id="h1", agent_type="x"), os.path.exists(SENT)), ([], [], False))
got = given()
check("presses: the waiting ones are given, with the standing first line and last line, in the page's own words",
      (len(got), got[0], got[1], got[2], got[3]), (4, 'Press from the live page on the roadmap "Press Roadmap": 2 to put on the roadmap, as if pressed on the roadmap page.',
       "[rm:a:1-1] " + W1, "[rm:a:2-1] " + W2, reminder.PRESS_TAIL))
check("presses: the one the listener already sent is not given again", "rm:a:3-1" in " ".join(got), False)
check("presses: each given press is marked delivered", sorted(rb.load_json(SENT, {}).get("sent", {})), ["rm:a:1-1", "rm:a:2-1"])
check("presses: asked five more times, a press already given is never given again", [given() for _ in range(5)], [[]] * 5)
queue(**{"rm:a:1-1": (W1, None), "rm:a:2-1": (W2, None), "rm:a:4-1": ("Marked on the roadmap: 4 Paint, check c2: Doesn't work", None)})
got = given()
check("presses: a press made later is given alone; the earlier two are not repeated", (len(got), "rm:a:4-1" in got[1], "rm:a:1-1" in " ".join(got)), (3, True, False))
code, out, _ = as_process("reminder.py", {"hook_event_name": "UserPromptSubmit", "session_id": RMAIN, "cwd": R, "prompt": "Go."}, project=R)
check("presses: run as a process, nothing new is given and the reminder itself still prints", (code, "[rm:" in out, "assistant:roadmap-director" in out), (0, False, True))
queue(**{"rm:a:5-1": ("Note on the roadmap: 1 Plan: \"Hello\"", None)})
code, out, _ = as_process("reminder.py", {"hook_event_name": "UserPromptSubmit", "session_id": RMAIN, "cwd": R, "prompt": "Go."}, project=R)
code2, out2, _ = as_process("reminder.py", {"hook_event_name": "UserPromptSubmit", "session_id": RMAIN, "cwd": R, "prompt": "Go again."}, project=R)
check("presses: run as a process, a new press is printed once, then never", (code, out.count("[rm:a:5-1]"), code2, out2.count("[rm:a:5-1]")), (0, 1, 0, 0))
code, out, _ = as_process("reminder.py", {"hook_event_name": "UserPromptSubmit", "session_id": "someone-else", "cwd": R, "prompt": "Go."}, project=R)
queue(**{"rm:a:6-1": ("Note on the roadmap: 2 Tiles: \"x\"", None)})
code, out, _ = as_process("reminder.py", {"hook_event_name": "UserPromptSubmit", "session_id": "someone-else", "cwd": R, "prompt": "Go."}, project=R)
check("presses: another session run as a process gets nothing and marks nothing", (code, out, "rm:a:6-1" in rb.load_json(SENT, {}).get("sent", {})), (0, "", False))
# a message from the listener that names ids: those ids are noted, so the queue cannot give them again
listener = ('Another Claude session sent a message:\n<cross-session-message from="local_listener">\nPress from the live page on the roadmap "Press Roadmap": 2 to put on the roadmap, as if pressed on the roadmap page.\n'
            '[rm:a:6-1] Note on the roadmap: 2 Tiles: "x"\n[rm:a:1-1] ' + W1 + '\n' + reminder.PRESS_TAIL + '\n</cross-session-message>')
got = given(listener)
check("presses: a listener's message naming ids already given is answered with 'forward nothing for them'; the new id is noted and not given again from the queue",
      (len(got), got[0].startswith("Press ids already given to you before, forward nothing for them: rm:a:1-1"), "rm:a:6-1" in rb.load_json(SENT, {}).get("sent", {})), (1, True, True))
check("presses: so the queue's copy of that new press is not given again", given(), [])
check("presses: nothing is delivered twice, in all", sorted(rb.load_json(SENT, {}).get("sent", {})),
      ["rm:a:1-1", "rm:a:2-1", "rm:a:4-1", "rm:a:5-1", "rm:a:6-1"])
rb.save_json({"presses": "not a table"}, QUEUE)
check("presses: a queue that is not in shape gives nothing and breaks nothing", given(), [])
with open(QUEUE, "w", encoding="utf-8") as fh:
    fh.write("{ not json")
check("presses: a queue that is not even JSON gives nothing and breaks nothing", given(), [])

# ---- (4) the full copy, kept by the writer while a reader asks for it ----
code, text = said(setup.main, ["--project", R, "plain-copy", "on", "--reader", "viewer"])
code, text = said(setup.main, ["--project", R, "plain-copy", "on", "--reader", "livepage", "--full"])
check("full: a reader asks for it by name, another does not", (setup.readers(R), setup.full_readers(R)), (["livepage", "viewer"], ["livepage"]))
code, text = said(setup.main, ["--project", R, "plain-copy", "off", "--reader", "livepage"])
check("full: when that reader stops asking, the full copy is no longer asked for", (setup.readers(R), setup.full_readers(R)), (["viewer"], []))
FULLF = os.path.join(R, "Roadmap page", "roadmap-full.json")
code, text = said(setup.main, ["--project", R, "full"])
check("full: no file yet is stopped and says to write it", (str(code).startswith("stopped: Not checked"), os.path.exists(FULLF)), (True, False))
good = {"collections": {"steps": {"step-01": {"order": 10, "name": "Dig", "status": "Done, confirmed"}}, "marks": {}, "questions": {}, "notes": {"n1": {"row": "step-01", "text": "hi"}},
                        "board": {"next": {"working": "x"}, "settings": {}}}}
rb.save_json(good, FULLF)
code, text = said(setup.main, ["--project", R, "full"])
stamped = rb.load_json(FULLF, {})
check("full: a good file is checked and stamped with the agreement number, name, link and time, the documents untouched",
      (code, stamped.get("agreement"), stamped.get("name"), stamped.get("page_url"), bool(stamped.get("written")), stamped.get("collections") == good["collections"], "1 steps" in text),
      (0, 2, "Press Roadmap", "https://claude.ai/artifact/PRESS", True, True, True))
bad = {"collections": {"steps": {"s": "not a document"}, "marks": {}, "questions": {}}}
rb.save_json(bad, FULLF)
was = sha(FULLF)
code, text = said(setup.main, ["--project", R, "full"])
check("full: a file missing a part or holding a non-document is refused and left as it was", (str(code).startswith("stopped: Not accepted"), "notes" in str(code), "steps" in str(code), sha(FULLF) == was), (True, True, True, True))
lock_r = gbk.Lock(rb.load_json(RCFG, {}), ROOT, DATA)
check("lock: the writer's full check and the own-id command are allowed", [lock_r.decide({"cwd": R, "tool_name": "PowerShell", "tool_input": {"command": 'python "' + os.path.join(DATA, "scripts", "roadmap_setup.py") + '" ' + a}})
                                                                         for a in ("full", "local-id local_abc1234", "director --local-id local_abc1234")], [None, None, None])
wtext = open(os.path.join(ROOT, "skills", "roadmap-writer", "SKILL.md"), encoding="utf-8").read()
atext = open(os.path.join(ROOT, "reference", "agreement.md"), encoding="utf-8").read()
check("the writer skill and the agreement both describe the full copy", ("roadmap-full.json" in wtext, '"full": true' in wtext, "roadmap_setup.py\" full" in wtext, "roadmap-full.json" in atext, '"full": true' in atext), (True,) * 5)
check("the working copy carries the files the full copy and the id depend on", all(f in working_copy.FILES for f in ("reference/agreement.md", "scripts/roadmap_setup.py", "skills/roadmap-writer/SKILL.md")), True)

# ---- (5) a press from another program's page is written by the writer as the page would have written it ----
import re as _re
page_src = open(os.path.join(ROOT, "page", "roadmap.html"), encoding="utf-8").read()
manual = open(os.path.join(ROOT, "reference", "database.md"), encoding="utf-8").read()
part = manual.split("## Presses from another program's page", 1)[1]
rows = {l.split("|")[1].strip(): l.split("|") for l in part.splitlines() if l.startswith("| ") and not l.startswith("| Press") and not l.startswith("|---")}

def page_keys(anchor, nth=0):
    """The field names of the object the page itself passes in the call that starts at anchor (the nth place it appears)."""
    i = -1
    for _ in range(nth + 1):
        i = page_src.index(anchor, i + 1)
    i += len(anchor)
    body = page_src[i:page_src.index("})", i)]
    return set(_re.findall(r"(?:^|[{,])\s*(\w+)\s*:", "{" + body))

def manual_fields(cell):
    return set(_re.findall(r"`([a-z_]+)`", cell))

page_mark = page_keys('return data ? ref.set(')
page_answer = page_keys('db.doc("questions/" + id).update(')
page_note_check = page_keys('db.doc("notes/" + k).set(', 0)
page_note_new = page_keys('db.doc("notes/" + k).set(', 1)
page_note_changed = page_keys('db.doc("notes/" + k).update(')
check("the page's own writes were found", (sorted(page_mark), sorted(page_answer)),
      (["check", "marked", "note", "result", "row", "text"], ["answer", "answered", "choice", "note", "status"]))
mark_cell, answer_cell, note_cell = rows["A mark (Works / Doesn't work)"][3], rows["An answer"][3], rows["A note"][3]
check("press mark: the manual lists the fields the page writes, field for field", manual_fields(mark_cell), page_mark)
check("press answer: the manual lists the fields the page writes, field for field", manual_fields(answer_cell), page_answer)
check("press note: the manual lists the fields the page writes (new, on a check, changed), field for field", manual_fields(note_cell), page_note_check | page_note_new | page_note_changed)
check("page's changed note writes exactly text and changed", page_note_changed, {"text", "changed"})
check("press note: the page's new note and check note differ only by check and check_text", sorted(page_note_check - page_note_new), ["check", "check_text"])
check("press paths and calls: the manual names the page's own keys", ("`marks/<row id>--<check id>`" in part, "`questions/<question id>`" in part, "`notes/<row id>--<short id>`" in part, "`if_version`" in part),
      (True, True, True, True))
check("the page's own keys: marks by row--check, notes by row--time, questions by id",
      ('db.doc("marks/" + key)' in page_src, "function markKey(it, c) { return it._id + \"--\" + c.id; }" in page_src, 'db.doc("questions/" + id)' in page_src, 'var k = id + "--" + Date.now()' in page_src), (True,) * 4)
wskill = open(os.path.join(ROOT, "skills", "roadmap-writer", "SKILL.md"), encoding="utf-8").read()
dskill = open(os.path.join(ROOT, "skills", "roadmap-director", "SKILL.md"), encoding="utf-8").read()
wpart = wskill.split("## A press from another program's page", 1)[1].split("## The plain copy", 1)[0]
check("writer skill: a press handed by the main session is written as the page would have, data unchanged, by its id",
      ("from-page.json" in wpart, "data" in wpart and "unchanged" in wpart, "Never twice" in wpart, "press id" in wpart, "if_version" in wpart), (True,) * 5)
check("writer skill: nothing is written on its own, and the status is not changed by it", ("Write nothing for a line you cannot place" in wpart, "Change nothing else" in wpart, "plain and full copies" in wpart), (True,) * 3)
check("writer skill: no longer says only the page writes marks or notes", ("you never write a mark" in wskill, "the page writes these notes, never you" in wskill), (False, False))
check("writer skill: the three kinds are each named as written by the writer for a press", ("A press from another program's page" in wskill, wskill.count("press the main session hands you") >= 2), (True, True))
check("manual: marks and notes no longer say only the page writes them", ("Only the page writes these." in manual, "nothing else writes or changes them" in manual), (False, False))
check("director skill: the main session hands each press with its id to the writer to write as the page would have", ("press ids" in dskill, "writes the mark, the answer or the note itself" in dskill), (True, True))
check("agreement: from-page.json is described", ("from-page.json" in open(os.path.join(ROOT, "reference", "agreement.md"), encoding="utf-8").read(),), (True,))
# the queue's own press as the listener writes it, set beside the page's own call: the writer is told to make the call the press carries
press = {"rm:k:1760000000000-1": {"op": "set", "path": "marks/step-01--c1", "data": {"row": "step-01", "check": "c1", "text": "Open it.", "result": "works", "note": "", "marked": "2026-11-16T20:31:00"}}}
check("a press's data for a mark has exactly the fields the page's own mark has", set(press["rm:k:1760000000000-1"]["data"]), page_mark)

# ---- (6) a Ready status needs a check; work Claude checked is Done; the page shows a Ready row with no checks as a fault ----
page_src = open(os.path.join(ROOT, "page", "roadmap.html"), encoding="utf-8").read()
manual = open(os.path.join(ROOT, "reference", "database.md"), encoding="utf-8").read()
wskill = open(os.path.join(ROOT, "skills", "roadmap-writer", "SKILL.md"), encoding="utf-8").read()
dskill = open(os.path.join(ROOT, "skills", "roadmap-director", "SKILL.md"), encoding="utf-8").read()
wrule = wskill.split("**A Ready status needs a check the person alone can do**", 1)[1].split("\n", 1)[0] if "**A Ready status needs a check the person alone can do**" in wskill else ""
check("writer skill: a Ready status is written only with checks the person alone can do (needs_person) and the Checked by Claude line, otherwise refused and told to the main session",
      ('"Ready, waiting for your look"' in wrule, '"Ready, known fault"' in wrule, "`needs_person`" in wrule, "Checked by Claude, <date>" in wrule, "do not write the status" in wrule, "receipt" in wrule, "Never invent a check" in wrule), (True,) * 7)
check("manual: both Ready statuses need checks with needs_person and the Checked by Claude line, else refused; a row with none is shown as a fault",
      ("refused by the plugin's guard" in manual, '{"id", "text", "needs_person"}' in manual, "No checks to try: tell Claude" in manual, "the writer refuses to write it" in manual), (True, True, True, True))
check("manual: Done, confirmed also means Claude checked it, with the shown_working line", ('Checked by Claude, <date>: <what was checked>' in manual, "needs nothing from the person" in manual), (True, True))
check("director skill: Ready only with checks sent together; work Claude checked is Done, confirmed with the shown_working line",
      ("only when it carries checks" in dskill, "the writer refuses a Ready status for a row with none" in dskill, '"Done, confirmed" with `shown_working` reading "Checked by Claude, <date>: <what you checked>"' in dskill,
       "needs nothing from the person" in dskill), (True,) * 4)
check("page: a Ready row with no checks is shown as a fault in its tag, its colour, its filter and its count, and not as still to try",
      ('NOCHK_SHORT = "No checks to try: tell Claude"' in page_src, "function noChecks(it) { return CHECK_STATES.indexOf(it.status) >= 0 && !checksOf(it).length; }" in page_src,
       'short: NOCHK_SHORT, c: "--s-fault"' in page_src, "var st = tagOf(it);" in page_src.split("function makeRow", 1)[1][:200],
       "addFilter(NOCHK, NOCHK_SHORT" in page_src, "setFilter(NOCHK)" in page_src, "if (key === NOCHK) return noChecks(it);" in page_src,
       "shownStatus(it) === s.key && !noChecks(it)" in page_src), (True,) * 8)
check("page: a row with no checks still never counts as a check to try", "if (key === TOTRY) { var t = tally(it); return t.marked < t.all; }" in page_src, True)
check("page: the check buttons are untouched by this change", ("function makeChecks(it) {\n    var cs = checksOf(it);\n    if (!cs.length) return null;" in page_src.replace("\r\n", "\n")), True)
check("page: the template still holds exactly 2 title placeholders", page_src.count("Project Roadmap"), 2)

print(f"{total - len(fails)} of {total} passed (hooks: {HERE})")
for f in fails:
    print("FAIL", f)
sys.exit(1 if fails else 0)
