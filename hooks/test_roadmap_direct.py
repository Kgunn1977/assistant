"""Proves the mode where the main session writes the roadmap itself (config "writes": "main"): the logbook, the end
check, the refusal of other writers, the reminder, the setup commands and the lock. Builds a throwaway project folder.
Run with no arguments: python hooks/test_roadmap_direct.py"""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.pop("CLAUDE_PROJECT_DIR", None)
import roadmap_blocks as rb, guard_blocks as gbk, reminder

TMP = tempfile.mkdtemp()
P = os.path.join(TMP, "Direct Project")
os.makedirs(P)
CFG, LOG = rb.config_path(P), rb.log_path(P)
MAIN, URL, OTHER_URL = "main-1", "https://claude.ai/artifact/AbC123", "https://claude.ai/artifact/ZzOther9"
STOP_MSG = "Work happened this turn that the roadmap doesn't show yet"
REMIND_MSG = "Reminder: the roadmap does not show yet work from before this message"
FORWARD_MSG = "Forward it to the Roadmap writer"
fails, total, clock = [], 0, [1000.0]


def check(name, got, want):
    global total
    total += 1
    if got != want:
        fails.append(f"{name}: wanted {want!r}, got {got!r}")
        print("FAIL", fails[-1])
    else:
        print("PASS", name)


def set_cfg(**extra):
    cfg = {"director_session_id": MAIN, "page_url": URL, **extra}
    rb.save_json(cfg, CFG)
    if os.path.exists(LOG):
        os.remove(LOG)
    return cfg


def run(event, session=MAIN, agent=None, **extra):
    clock[0] += 1
    d = {"hook_event_name": event, "session_id": session, "cwd": P, **extra}
    if agent:
        d["agent_id"], d["agent_type"] = agent, "general-purpose"
    return rb.main(d, CFG, LOG, clock[0])


def user(text="Do the next piece."):
    return run("UserPromptSubmit", prompt=text)


def report(aid="a1"):
    return run("UserPromptSubmit", prompt=f"<task-notification><task-id>{aid}</task-id><status>completed</status>"
                                          f"<summary>Agent \"helper\" finished</summary><result>done</result></task-notification>")


def started(aid, status="async_launched"):
    return run("PostToolUse", tool_name="Agent", tool_input={"prompt": "x"}, tool_response={"status": status, "agentId": aid})


def adata(action, url=URL, post=False, **kw):
    return run("PostToolUse" if post else "PreToolUse", tool_name="ArtifactData", tool_input={"action": action, "url": url}, **kw)


def wrote(url=URL, action="update"):
    return adata(action, url, post=True)


def stop():
    return run("Stop", stop_hook_active=False)


# 1
cfg = set_cfg(writes="main")
check("1 direct mode is active with no writer recorded", (rb.direct(cfg), rb.active(cfg)), (True, True))
cfgw = {"director_session_id": MAIN, "page_url": URL}
check("1 writer mode with no writer is not active", (rb.direct(cfgw), rb.active(cfgw)), (False, False))
check("1 writer mode with a writer is active", rb.active({**cfgw, "writer": {"session_id": "local_w"}}), True)

# 2
set_cfg(writes="main")
user("Go ahead.")
check("2a helper started then reported then roadmap written: setup", started("h1")[0], 0)
run("SubagentStop", agent="h1")
check("2a SubagentStop for own helper: logs", len(rb.load_json(LOG, {}).get("owed", [])) >= 1, True)
wrote()
check("2a Stop passes silently after SubagentStop and a write", stop(), (0, None))
set_cfg(writes="main")
user("Go ahead.")
report()
wrote()
check("2b Stop passes silently after a task-notification report and a write", stop(), (0, None))

# 3
set_cfg(writes="main")
user("What is the plan?")
for act in ("get", "list", "query"):
    adata(act, post=True)
    adata(act)
run("PostToolUse", tool_name="Bash", tool_input={"command": "ls"})
run("PostToolUse", tool_name="Read", tool_input={"file_path": "x"})
check("3 nothing owed: Stop passes silently", stop(), (0, None))

# 4
set_cfg(writes="main")
user("Start the helper.")
started("h2")
check("4a helper started, no write: the reply is not held", stop(), (0, None))
msg = user("And then?")[1]
check("4a the next message reminds, naming the owed work", ((msg or "").startswith(REMIND_MSG), "a helper you started" in (msg or "")), (True, True))
check("4b reminded once only", user("And then?"), (0, None))
report("h2")
code, msg = stop()
check("4c a later new helper report is caught again", (code, (msg or "").startswith(STOP_MSG), "a helper's report" in (msg or "")), (2, True, True))
check("4d and only once", stop(), (0, None))
set_cfg(writes="main")
report()
code, msg = stop()
check("4e a helper report alone also owes a write", (code, "a helper's report" in (msg or "")), (2, True))
set_cfg(writes="main")
started("h3", status="completed")
check("4f an Agent that returns completed owes a write", stop()[0], 2)

# 5
set_cfg(writes="main")
started("h4", status="completed")
wrote(OTHER_URL)
adata("get", post=True)
adata("query", post=True)
adata("list", post=True)
check("5 other-url write and reads on the page do not count: Stop refused", stop()[0], 2)
check("5 roadmap_write: other url", rb.roadmap_write({"tool_name": "ArtifactData", "tool_input": {"action": "update", "url": OTHER_URL}}, cfg), False)
check("5 roadmap_write: read on page url", rb.roadmap_write({"tool_name": "ArtifactData", "tool_input": {"action": "get", "url": URL}}, cfg), False)
check("5 roadmap_write: update on page url", rb.roadmap_write({"tool_name": "ArtifactData", "tool_input": {"action": "update", "url": URL}}, cfg), True)

# 6
set_cfg(writes="main")
user("What time is it?")
check("6a plain answer is never held", stop(), (0, None))
started("h5", status="completed")
check("6b owed report caught once", stop()[0], 2)
user("Thanks, and one more question?")
check("6c plain answer after an earlier catch is not held", stop(), (0, None))

# 7
cfg = set_cfg(writes="main")
user("x")
check("7 helper write refused", adata("update", agent="h1")[0], 2)
check("7 other session (worktree helper) write refused", adata("update", session="worktree-9")[0], 2)
for act in ("set", "delete", "batch"):
    check(f"7 helper {act} refused", adata(act, agent="h1")[0], 2)
check("7 main session write passes", adata("update"), (0, None))
for act in ("get", "list", "query"):
    check(f"7 helper read {act} passes", adata(act, agent="h1"), (0, None))
    check(f"7 other session read {act} passes", adata(act, session="worktree-9"), (0, None))
check("7 helper write to another artifact passes", adata("update", OTHER_URL, agent="h1"), (0, None))
set_cfg(writer={"session_id": "local_w", "name": "roadmap-writer", "title": "Roadmap writer", "claude_session_id": "w-own"})
check("7 writer mode: writer session's write passes", adata("update", session="local_w"), (0, None))
check("7 writer mode: writer session's write passes (own id)", adata("update", session="w-own"), (0, None))

# 8
set_cfg(writes="main")
user("Please start a helper.")
agent_in = {"prompt": "x", "subagent_type": "general-purpose"}
check("8 direct: Agent after user message passes", run("PreToolUse", tool_name="Agent", tool_input=agent_in), (0, None))
check("8 direct: SendMessage after user message passes", run("PreToolUse", tool_name="SendMessage", tool_input={"to": "someone", "message": "hi"}), (0, None))
check("8 direct: start_session after user message passes", run("PreToolUse", tool_name="mcp__ccd_session__start_session", tool_input={"title": "Other", "prompt": "x"}), (0, None))
set_cfg(writer={"session_id": "local_w", "name": "roadmap-writer", "title": "Roadmap writer", "claude_session_id": ""})
user("Please start a helper.")
check("8 writer: Agent after user message goes ahead (a reminder, not a refusal)", run("PreToolUse", tool_name="Agent", tool_input=agent_in)[0], 0)
check("8 writer: SendMessage to someone else goes ahead", run("PreToolUse", tool_name="SendMessage", tool_input={"to": "someone", "message": "hi"})[0], 0)
check("8 writer: start_session goes ahead", run("PreToolUse", tool_name="mcp__ccd_session__start_session", tool_input={"title": "Other", "prompt": "x"})[0], 0)
check("8 writer: the next message reminds to tell the writer the plan", "told the plan" in (user("Next.")[1] or ""), True)

# 9
set_cfg(writer={"session_id": "local_w", "name": "roadmap-writer", "title": "Roadmap writer", "claude_session_id": ""})
started("h6")
check("9 writer mode: a report arriving as a message carries the reminder to forward it", FORWARD_MSG in (report("h6")[1] or ""), True)
check("9 writer mode: Stop after a helper report is not held", stop(), (0, None))
check("9 writer logbook keys used, not owed", "owed" in rb.load_json(LOG, {}), False)

# 10
cfg = set_cfg(writes="main")
first = reminder.lines({"session_id": MAIN}, cfg)[0]
check("10 direct: first line says it writes the roadmap itself", "you write the roadmap's rows yourself" in first, True)
check("10 direct: first line mentions no Roadmap writer", "roadmap writer" in first.lower(), False)
cfgw = set_cfg(writer={"session_id": "local_w", "name": "roadmap-writer", "title": "Roadmap writer", "claude_session_id": ""})
check("10 writer: today's line", reminder.lines({"session_id": MAIN}, cfgw)[0],
      "You are this project's main session for the roadmap (skill assistant:roadmap-director): send the Roadmap writer "
      "every plan, decision and start before starting or messaging a helper, and forward every helper report to it.")
check("10 direct: helper gets no line", reminder.lines({"session_id": MAIN, "agent_id": "a"}, cfg), [])

# 11
clean_env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_PROJECT_DIR")}
claude_env = {**clean_env, "CLAUDECODE": "1"}
SETUP = os.path.join(ROOT, "scripts", "roadmap_setup.py")


def setup_run(env, *argv):
    return subprocess.run([sys.executable, SETUP, "--project", P, *argv], env=env, capture_output=True, text=True, cwd=TMP)


def old_writer_cfg():
    set_cfg(writer={"session_id": "local_oldwriter1", "name": "roadmap-writer", "title": "Roadmap writer", "claude_session_id": "oldwriter-own-cc"})
    rb.save_json({"writer": 5, "user": 6, "report": 7, "stop_refusals": 2, "helpers": ["h1"]}, LOG)


old_writer_cfg()
before = open(CFG, encoding="utf-8").read()
r = setup_run(claude_env, "writes-main")
check("11 refused under CLAUDECODE: non-zero", r.returncode != 0, True)
check("11 refused under CLAUDECODE: says only the person", "only the person" in r.stderr, True)
check("11 refused: config untouched", open(CFG, encoding="utf-8").read(), before)
r = setup_run({**clean_env, "CLAUDE_CODE_ENTRYPOINT": "cli"}, "writes-main")
check("11 refused under CLAUDE_CODE_ENTRYPOINT too", r.returncode != 0, True)
r = setup_run(clean_env, "writes-main")
check("11 clean env: succeeds", (r.returncode, r.stderr.strip()), (0, ""))
text = open(CFG, encoding="utf-8").read()
cfg2 = json.loads(text)
check("11 sets writes main", cfg2.get("writes"), "main")
check("11 no writer session id anywhere in config.json", ("local_oldwriter1" in text, "oldwriter-own-cc" in text, (cfg2.get("writer") or {}).get("session_id")), (False, False, ""))
log2 = rb.load_json(LOG, {})
check("11 log writer/user/report/stop_refusals removed", [k for k in ("writer", "user", "report", "stop_refusals") if k in log2], [])
check("11 log keeps other keys and stamps wrote", (log2.get("helpers"), "wrote" in log2), (["h1"], True))
check("11 prints the old writer session can be archived", ("local_oldwriter1" in r.stdout and "archive it" in r.stdout), True)
check("11 status shows by the main session itself", "by the main session itself" in r.stdout, True)
check("11 blocks active after switch", rb.active(cfg2), True)
r = setup_run(clean_env, "status")
check("11 status command shows by the main session itself", "by the main session itself" in r.stdout, True)
r = setup_run(clean_env, "writes-writer")
check("11 writes-writer succeeds", r.returncode, 0)
check("11 writes-writer removes writes", "writes" in rb.load_json(CFG, {}), False)
check("11 writes-writer: direct off", rb.direct(rb.load_json(CFG, {})), False)
r = setup_run(claude_env, "writes-writer")
check("11 writes-writer refused under CLAUDECODE", (r.returncode != 0, "only the person" in r.stderr), (True, True))

# 12
cfg = set_cfg(writes="main")
cmd = 'python "' + SETUP + '" writes-main'
lock = gbk.Lock(cfg, ROOT)
why = lock.decide({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": P})
check("12 Bash writes-main refused by decide", bool(why), True)
check("12 check_command returns a reason", bool(lock.check_command(cmd, P)), True)
check("12 PowerShell writes-main refused", bool(lock.decide({"tool_name": "PowerShell", "tool_input": {"command": cmd}, "cwd": P})), True)
check("12 writes-writer refused", bool(lock.decide({"tool_name": "Bash", "tool_input": {"command": cmd.replace("writes-main", "writes-writer")}, "cwd": P})), True)
check("12 plain status still allowed", lock.decide({"tool_name": "Bash", "tool_input": {"command": 'python "' + SETUP + '" status'}, "cwd": P}), None)

# 13 a roadmap write with no full-patch after it, where a reader asks for the full copy
COPY_MSG = "its full copy was not brought up to date"
READERS_FILE = os.path.join(P, "Roadmap page", "readers.json")
rb.save_json({"readers": {"assistant": {"since": "2026-11-18T10:00:00", "full": True}}}, READERS_FILE)


def patched(cmd=None):
    cmd = cmd or 'python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" full-patch "C:/scratch/patch.json"'
    return run("PostToolUse", tool_name="Bash", tool_input={"command": cmd}, tool_response={"stdout": "ok"})


set_cfg(writes="main")
user("Mark step 2 started.")
wrote()
check("13 write, then no patch: the reply is not held", stop(), (0, None))
check("13 write, then no patch: the next message reminds", COPY_MSG in (user("Next.")[1] or ""), True)
check("13 write, then no patch: reminded once only", user("Next."), (0, None))
set_cfg(writes="main")
user("Mark step 2 started.")
wrote()
patched()
check("13 write, then patch: silent", stop(), (0, None))
set_cfg(writes="main")
user("Mark step 2 started.")
wrote()
wrote(action="batch")
patched('python "C:/x/scripts/roadmap_setup.py" --project "C:/p q/r" full-patch -')
check("13 two writes, one patch after both (with --project): silent", stop(), (0, None))
set_cfg(writes="main")
user("Mark step 2 started.")
wrote()
patched()
wrote()
check("13 a write after the patch: reminded at the next message", (stop(), COPY_MSG in (user("Next.")[1] or "")), ((0, None), True))
set_cfg(writes="main")
user("Mark step 2 started.")
wrote()
patched('python "${CLAUDE_PLUGIN_DATA}/scripts/roadmap_setup.py" facts')
check("13 a facts run is not a patch: reminded", COPY_MSG in (user("Next.")[1] or ""), True)
set_cfg(writes="main")
user("Where do things stand?")
check("13 no write: silent", stop(), (0, None))
set_cfg(writes="main")
user("What does step 3 do?")
run("PostToolUse", tool_name="ArtifactData", tool_input={"action": "list", "url": URL, "collection": "steps"})
check("13 a plain answer (a read only): never held", stop(), (0, None))
set_cfg(writes="main")
started("hX")
msg = user("Next.")[1]
check("13 a helper started alone: reminded without the copy line", (stop(), REMIND_MSG in (msg or ""), COPY_MSG in (msg or "")), ((0, None), True, False))
os.remove(READERS_FILE)
set_cfg(writes="main")
user("Mark step 2 started.")
wrote()
check("13 no reader asks for the full copy: a write with no patch is silent", stop(), (0, None))

# 15 a helper's turn-end note alone owes no roadmap write; its own report does
NOTE = ('<side-sessions-event>The session "Build helper" you started (local_abc123) finished a turn. Its report: '
        '"The suites are still running."</side-sessions-event>')
BG = ('<task-notification><task-id>b1</task-id><status>completed</status><summary>Background command "Run the suites" '
      'completed (exit code 0)</summary></task-notification>')
HANDBACK = ('<task-notification><task-id>a9</task-id><status>completed</status><summary>Agent "Find the fault" finished'
            '</summary><result>Found it.</result></task-notification>')
SENT = ('Another Claude session sent a message:\n<cross-session-message from="uds:x" from-session="local_abc123" '
        'from-name="Build helper">Built and committed.</cross-session-message>')
for label, prompt, want in (("a side session's 'still running' turn note", NOTE, (0, None)),
                            ("a finished background command", BG, (0, None))):
    set_cfg(writes="main")
    run("UserPromptSubmit", prompt=prompt)
    check("15 " + label + " does not hold the reply", stop(), want)
for label, prompt in (("a subagent's final hand-back", HANDBACK), ("a message a helper sent", SENT)):
    set_cfg(writes="main")
    run("UserPromptSubmit", prompt=prompt)
    code, msg = stop()
    check("15 " + label + ", unwritten: held once", (code, STOP_MSG in (msg or ""), stop()), (2, True, (0, None)))
set_cfg(writes="main")
run("UserPromptSubmit", prompt=SENT)
wrote()
check("15 a helper's report, then written: silent", stop(), (0, None))
check("15 writer mode still counts a turn note as a report", rb.classify_prompt(NOTE, {"writer": {"session_id": "local_w"}}), "report")

# 14 the safeguard lock refuses only commands that change the safeguards
lock = gbk.Lock({}, ROOT)
CONF = "C:/Users/someone/Documents/Projects/Shop Plans/.claude/roadmap/config.json"
reads = [
    'cat "' + CONF + '" | python -c "import json,sys;d=json.load(sys.stdin);print({k:d.get(k) for k in [\'writes\',\'writer\',\'writes_main\',\'mode\']}); print([k for k in d])"',
    'type "' + CONF + '"',
    'Get-Content "' + CONF + '"',
    'python -c "import json;print(json.load(open(r\'' + CONF + '\')))"',
    'grep writes "' + CONF + '"',
]
for c in reads:
    check("14 read passes: " + c[:40], lock.check_command(c, P), None)
changes = [
    'echo {} > "' + CONF + '"', 'cat x >> "' + CONF + '"', 'mv "' + CONF + '" x', 'rm "' + CONF + '"',
    'Remove-Item "' + CONF + '"', 'Move-Item "' + CONF + '" y', 'Set-Content "' + CONF + '" x', 'cp x "' + CONF + '"',
    'python -c "open(r\'' + CONF + '\',\'w\').write(\'{}\')"',
    'python -c "import json;json.dump({},open(r\'' + CONF + '\',mode=\'w\'))"',
    'python -c "import os;os.remove(r\'' + CONF + '\')"',
    'python -c "import subprocess;subprocess.run([\'rm\',r\'' + CONF + '\'])"',
    'python -c "import pathlib;pathlib.Path(r\'' + CONF + '\').write_text(\'{}\')"',
]
for c in changes:
    check("14 change refused: " + c[:40], bool(lock.check_command(c, P)), True)

print(f"{total - len(fails)} of {total} passed")
if fails:
    print("\n".join("FAIL: " + f for f in fails))
sys.exit(1 if fails else 0)
