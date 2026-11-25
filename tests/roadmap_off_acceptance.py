r"""Acceptance: /assistant:roadmap-off (roadmap_setup.py off). Played in throwaway projects with made-up names, through every
hook the way Claude Code runs them (hooks\hooks.json read for each event; JSON on stdin).

1. A project with a roadmap (one writing it itself, one with a Roadmap writer): before off the hooks speak; off deletes
   .claude/roadmap outright (no To Delete folder), takes the project out of the assistant's list of roadmaps (the others stay),
   and says the page stays; afterwards every hook is silent on message, start and resume, reply end, helper start and a roadmap write.
2. Off in a project with no roadmap says so and changes nothing (no folder made, not even by the hooks).
3. The questions file in the same project is unaffected.
4. The guard: a plain edit of .claude/roadmap, or a move of it by command, goes through (only the settings and hooks stay locked); the off command is allowed.
5. A second off the same day deletes the new roadmap folder the same way.

    python tests\roadmap_off_acceptance.py
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
SETUP = os.path.join(PKG, "scripts", "roadmap_setup.py")
QSETUP = os.path.join(PKG, "scripts", "questions_setup.py")
HOOKS = json.load(open(os.path.join(PKG, "hooks", "hooks.json"), encoding="utf-8"))["hooks"]
MAIN, WRITER, URL = "sess-main", "sess-writer", "https://claude.ai/artifact/TestRoadOff1"
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def scripts(event, tool=None):
    out = []
    for group in HOOKS.get(event, []):
        m = group.get("matcher")
        if m and m != "*" and not (tool and re.fullmatch(m, tool)):
            continue
        for h in group["hooks"]:
            path = h["args"][0].replace("${CLAUDE_PLUGIN_ROOT}", PKG)
            if not path.endswith("assistant_copy.py"):
                out.append(path)
    return out


def turn(project, event, **payload):
    """(exit codes, stdout, stderr) over every hook for the event."""
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_DATA"}
    env["CLAUDE_PROJECT_DIR"] = project
    data = dict(payload, hook_event_name=event, cwd=project)
    data.setdefault("session_id", MAIN)
    codes, out, err = [], [], []
    for s in scripts(event, data.get("tool_name")):
        r = subprocess.run([sys.executable, s], input=json.dumps(data), capture_output=True, text=True, env=env, timeout=60)
        codes.append(r.returncode)
        out.append(r.stdout.strip())
        err.append(r.stderr.strip())
    return codes, "\n".join(x for x in out if x), "\n".join(x for x in err if x)


def silent(project):
    """The events on which some hook said or refused something (empty when every roadmap hook is silent)."""
    helper = dict(agent_id="helper-1")
    done = ('<task-notification><task-id>h1</task-id><status>completed</status><summary>Agent "x" finished</summary>'
            '<result>Done.</result></task-notification>')
    events = [
        ("UserPromptSubmit", dict(prompt="Please start the next step.")),
        ("UserPromptSubmit", dict(prompt=done)),
        ("SessionStart", dict(source="startup")),
        ("SessionStart", dict(source="resume")),
        ("PreToolUse", dict(tool_name="mcp__ccd_session__start_session", tool_input={"prompt": "do it", "title": "helper"})),
        ("PreToolUse", dict(tool_name="Agent", tool_input={"prompt": "do it"})),
        ("PreToolUse", dict(tool_name="ArtifactData", tool_input={"action": "set", "url": URL}, **helper)),
        ("PostToolUse", dict(tool_name="Agent", tool_input={"prompt": "x"}, tool_response={"agentId": "helper-2", "status": "completed"})),
        ("PostToolUse", dict(tool_name="ArtifactData", tool_input={"action": "set", "url": URL})),
        ("SubagentStop", dict(agent_id="helper-2")),
        ("Stop", dict(last_assistant_message="Step done, helper finished.", stop_hook_active=False)),
    ]
    bad = []
    for ev, p in events:
        codes, out, err = turn(project, ev, **p)
        if any(c != 0 for c in codes) or out or err:
            bad.append((ev, p.get("tool_name") or p.get("prompt", "")[:20], codes, (out + err)[:60]))
    return bad


def speaks(project):
    return "roadmap-director" in turn(project, "UserPromptSubmit", prompt="Please start the next step.")[1]


def refused(project, tool, **inp):
    return 2 in turn(project, "PreToolUse", tool_name=tool, tool_input=inp)[0]


def make(tmp, name, direct):
    project = os.path.join(tmp, name)
    os.makedirs(os.path.join(project, ".claude", "roadmap"))
    cfg = {"director_session_id": MAIN, "page_url": URL, "title": "Shop sign"}
    if direct:
        cfg["writes"] = "main"
    else:
        cfg["writer"] = {"session_id": WRITER, "name": "roadmap-writer", "title": "Roadmap writer", "claude_session_id": WRITER}
    with open(os.path.join(project, ".claude", "roadmap", "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    with open(os.path.join(project, ".claude", "roadmap", "log.json"), "w", encoding="utf-8") as f:
        json.dump({"wrote": 1}, f)
    return project


def off(project, root):
    r = subprocess.run([sys.executable, SETUP, "--project", project, "off", "--root", root], capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_DATA"})
    return r.returncode, r.stdout + r.stderr


def tree(folder):
    return sorted(os.path.relpath(os.path.join(d, f), folder) for d, _, fs in os.walk(folder) for f in fs)


def main():
    tmp = tempfile.mkdtemp(prefix="roadmap-off-")
    try:
        root = os.path.join(tmp, "Assistant")
        os.makedirs(os.path.join(root, "Live", "personal"))
        a, b, other = make(tmp, "Shop sign", True), make(tmp, "Lamp post", False), os.path.join(tmp, "Other project")
        os.makedirs(other)
        sp = os.path.join(root, "Live", "personal", "settings.json")
        with open(sp, "w") as f:
            json.dump({"page_port": 8080, "roadmaps": [{"folder": a, "applied": "x"}, {"folder": other, "applied": "y"},
                                                        {"folder": b, "applied": "z"}]}, f)
        subprocess.run([sys.executable, QSETUP, "--project", a, "on"], capture_output=True, text=True, check=True)
        qfile, qcfg = os.path.join(a, "Questions.md"), os.path.join(a, ".claude", "questions", "config.json")
        qbefore = (open(qfile, encoding="utf-8").read(), open(qcfg, encoding="utf-8").read())

        # 4. the guard, before off
        fwd = a.replace("\\", "/")
        # Kevin 11/25/26: "The roadmap IS NOT A CRITICAL FUNCTION. it should have very few blocks." Its own files are
        # ordinary: the lock refuses only real changes to the guards themselves
        check("4 a plain edit of .claude/roadmap goes through",
              refused(a, "Write", file_path=os.path.join(a, ".claude", "roadmap", "config.json"), content="{}"), False)
        check("4 a move of .claude/roadmap by command goes through", refused(a, "Bash", command='mv "' + fwd + '/.claude/roadmap" /tmp/x'), False)
        check("4 an edit of the project's settings is still refused",
              refused(a, "Write", file_path=os.path.join(a, ".claude", "settings.json"), content="{}"), True)
        check("4 the off command alone is allowed", refused(a, "Bash", command='python "' + SETUP.replace("\\", "/") + '" off'), False)

        # 1. before off the hooks speak (so the test means something), after off they are silent
        check("1 before off: the writing-itself project's hooks speak", speaks(a), True)
        check("1 before off: the writer project's hooks speak", speaks(b), True)
        check("1 before off: a helper's roadmap write is refused",
              2 in turn(a, "PreToolUse", tool_name="ArtifactData", tool_input={"action": "set", "url": URL}, agent_id="h")[0], True)
        for name, project in (("writing itself", a), ("with a writer", b)):
            code, said = off(project, root)
            check(f"1 {name}: off succeeds and says the page stays", (code, "stays" in said and "record" in said), (0, True))
            check(f"1 {name}: the folder is deleted outright, no To Delete folder is made",
                  (os.path.isdir(os.path.join(project, ".claude", "roadmap")), os.path.exists(os.path.join(project, "To Delete"))), (False, False))
            check(f"1 {name}: every hook is silent", silent(project), [])
            check(f"1 {name}: the hooks make no roadmap folder again", os.path.exists(os.path.join(project, ".claude", "roadmap")), False)
        got = json.load(open(sp))
        check("1 the projects leave the assistant's list; the other stays; other settings kept",
              (got.get("page_port"), [e["folder"] for e in got["roadmaps"]]), (8080, [other]))

        # 3. the questions file
        check("3 the questions file and its setting are unchanged",
              (open(qfile, encoding="utf-8").read(), open(qcfg, encoding="utf-8").read()), qbefore)

        # 2. off with no roadmap
        before = tree(other)
        code, said = off(other, root)
        check("2 no roadmap: says so, changes nothing",
              (code, "no roadmap" in said, tree(other), os.path.exists(os.path.join(other, "To Delete"))), (0, True, before, False))
        turn(other, "PreToolUse", tool_name="Bash", tool_input={"command": 'python "' + SETUP + '" off'}, session_id="s1")
        check("2 the hooks make no folder either", os.path.exists(os.path.join(other, ".claude")), False)
        check("2 the list is untouched by it", [e["folder"] for e in json.load(open(sp))["roadmaps"]], [other])

        # 5. a second off the same day
        os.makedirs(os.path.join(a, ".claude", "roadmap"))
        with open(os.path.join(a, ".claude", "roadmap", "config.json"), "w") as f:
            f.write("{}")
        code, said = off(a, root)
        check("5 a second off the same day deletes it the same way",
              (code, os.path.isdir(os.path.join(a, ".claude", "roadmap")), os.path.exists(os.path.join(a, "To Delete"))), (0, False, False))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    failed = [r for r in results if not r[1]]
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"\n     got  {got!r}\n     want {want!r}"))
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
