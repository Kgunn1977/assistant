r"""Acceptance: the roadmap and the questions file turned on together in one project. Every turn is played through all the
plugin's hooks the way Claude Code runs them (hooks\hooks.json read for each event; a JSON payload on stdin; context on stdout; a
held reply as exit 2 with the reason on stderr), in a throwaway project folder with made-up questions.

1. A question raised in discussion goes in Questions.md only: the questions check holds the reply until the file has it; the
   roadmap check does not hold.
2. A work question a helper raises goes on the roadmap only: the roadmap check holds until the roadmap is written; the
   questions check does not hold for a reply that says it was put on the roadmap, and the file is not touched.
3. Each answer in its own place: "1b" in chat changes the file; an answer read from the roadmap and echoed is not held by the
   questions check, and the file stays as it was.
4. A session start or resume shows both: the roadmap reminder and the open questions, each once.
5. Every message: each reminder appears once, never doubled. Holds are counted apart: the roadmap holding does not count toward
   the questions check's three-in-a-row let-go, and the questions check letting go does not stop the roadmap holding.
Setting up the questions file is not work the roadmap is owed.

    python tests\roadmap_questions_acceptance.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
SETUP = os.path.join(PKG, "scripts", "questions_setup.py")
HOOKS = json.load(open(os.path.join(PKG, "hooks", "hooks.json"), encoding="utf-8"))["hooks"]
MAIN, URL = "sess-main", "https://claude.ai/artifact/TestRoad01"
ROAD_HOLD = "Work happened this turn that the roadmap doesn't show yet"
Q_ASK = "This reply asks the person a question that is not in Questions.md"
Q_ANS = "The person answered a question this turn, but Questions.md has not changed"
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def scripts(event, tool=None):
    """The hook scripts Claude Code would run for this event, in order (the working-copy keeper left out: it touches no project)."""
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
    """Runs every hook for the event. Returns (held, stdout, stderr) combined as Claude Code shows them."""
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_DATA"}
    env["CLAUDE_PROJECT_DIR"] = project
    data = dict(payload, hook_event_name=event, cwd=project)
    data.setdefault("session_id", MAIN)
    held, out, err = False, [], []
    for s in scripts(event, data.get("tool_name")):
        r = subprocess.run([sys.executable, s], input=json.dumps(data), capture_output=True, text=True, env=env, timeout=60)
        held = held or r.returncode == 2
        if r.returncode not in (0, 2):
            err.append(f"[{os.path.basename(s)} exit {r.returncode}] " + r.stderr.strip())
        out += [r.stdout.strip()] if r.stdout.strip() else []
        err += [r.stderr.strip()] if r.returncode == 2 and r.stderr.strip() else []
    return held, "\n".join(out), "\n".join(err)


def say(project, prompt):
    return turn(project, "UserPromptSubmit", prompt=prompt)


def end(project, reply):
    return turn(project, "Stop", last_assistant_message=reply, stop_hook_active=False)


def roadmap_write(project, action="insert"):
    return turn(project, "PostToolUse", tool_name="ArtifactData", tool_input={"action": action, "url": URL})


def helper_report(project, n, result):
    return say(project, f"<task-notification><task-id>h{n}</task-id><status>completed</status>"
                        f"<summary>Agent \"bracket helper\" finished</summary><result>{result}</result></task-notification>")


def write_q(project, qs):
    head = "# Questions\n\nOpen questions for the person in this project, oldest first.\n\n"
    body = "\n".join(f"{n}. {q}\n\n    a. Yes  \n    b. No  \n\n    Recommended: a  \n    Asked: 11/19\n" for n, q in enumerate(qs, 1)) if qs else "No open questions.\n"
    with open(os.path.join(project, "Questions.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(head + body)


def file_q(project):
    return re.findall(r"^\d+\.\s+(.*\S)", open(os.path.join(project, "Questions.md"), encoding="utf-8").read(), re.M)


def owed(project):
    try:
        log = json.load(open(os.path.join(project, ".claude", "roadmap", "log.json"), encoding="utf-8"))
    except OSError:
        return []
    return [o for o in log.get("owed") or [] if o[0] > log.get("wrote", 0)]


def main():
    tmp = tempfile.mkdtemp(prefix="roadmap-questions-")
    project = os.path.join(tmp, "Shop sign project")
    os.makedirs(os.path.join(project, ".claude", "roadmap"))
    try:
        with open(os.path.join(project, ".claude", "roadmap", "config.json"), "w", encoding="utf-8") as f:
            json.dump({"director_session_id": MAIN, "page_url": URL, "writes": "main", "title": "Shop sign"}, f)
        subprocess.run([sys.executable, SETUP, "--project", project, "on"], capture_output=True, text=True, check=True)
        turn(project, "PostToolUse", tool_name="Bash", tool_input={"command": 'python "C:/data/scripts/questions_setup.py" on'})
        check("setting up the questions file is not work the roadmap is owed", owed(project), [])

        # 4 (first start): the roadmap reminder; no open questions yet, so nothing from the questions file
        held, out, err = turn(project, "SessionStart", source="startup")
        check("start: roadmap reminder shown once, no message-only line", (held, out.count("skill assistant:roadmap-director"),
              "After answering this message" in out, "skill assistant:questions" in out), (False, 1, False, False))

        # 1. a discussion question: the file only
        say(project, "What should the sign look like?")
        reply = "Two options for the face. Should the sign be red letters on white, or white letters on blue?"
        held, out, err = end(project, reply)
        check("1 discussion question not in the file: questions holds, roadmap does not",
              (held, Q_ASK in err, ROAD_HOLD in err), (True, True, False))
        write_q(project, ["Should the sign be red letters on white, or white letters on blue?\n\n    a. Red on white  \n    b. White on blue  "])
        check("1 written into the file: the reply ends", end(project, reply)[0], False)
        check("1 the roadmap owes nothing for a discussion question", owed(project), [])

        # 2. a work question a helper raises: the roadmap only
        held, out, err = helper_report(project, 1, "Drawing done. Open question: which supplier for the mounting brackets?")
        check("2 every message: each reminder once, the questions note says work questions go on the roadmap",
              (out.count("skill assistant:roadmap-director"), out.count("skill assistant:questions"),
               "a question raised by the work goes on the roadmap's row instead" in out), (1, 1, True))
        work = ("The helper finished the bracket drawing.\n\nI put its question on the roadmap, on the Brackets row: which supplier "
                "should we use for the mounting brackets?")
        before = file_q(project)
        held, out, err = end(project, work)
        check("2 helper's work question: roadmap holds, questions does not", (held, ROAD_HOLD in err, Q_ASK in err), (True, True, False))
        roadmap_write(project)
        check("2 written on the roadmap: the reply ends", end(project, work)[0], False)
        check("2 the questions file is untouched by the work question", file_q(project), before)
        sys.path.insert(0, os.path.join(PKG, "hooks"))
        import questions_blocks
        check("2 (control) the same reply in a project without a roadmap would have been held",
              bool(questions_blocks.asked(work, False)), True)

        # 3. each answer in its own place
        say(project, "1b")
        held, out, err = end(project, "Took 1b as: white letters on blue for the sign face.")
        check("3 answer in chat, file unchanged: questions holds, roadmap does not", (held, Q_ANS in err, ROAD_HOLD in err), (True, True, False))
        write_q(project, [])
        check("3 the question leaves the file: the reply ends", end(project, "Took 1b as: white letters on blue for the sign face.")[0], False)
        say(project, "I answered the bracket question on the roadmap.")
        turn(project, "PreToolUse", tool_name="ArtifactData", tool_input={"action": "query", "url": URL})
        roadmap_write(project, "update")
        held, out, err = end(project, "Took the roadmap's answer as: Northside Supply for the brackets, recorded on its row.")
        check("3 answer on the roadmap echoed: no hold from either, the file unchanged", (held, file_q(project)), (False, []))

        # 4. resume shows both
        write_q(project, ["How tall should the letters be?"])
        held, out, err = turn(project, "SessionStart", source="resume")
        check("4 resume: the roadmap reminder and the open question, each once",
              (held, out.count("skill assistant:roadmap-director"), out.count("skill assistant:questions"), "How tall should the letters be?" in out),
              (False, 1, 1, True))

        # 5. holds counted apart
        held, out, err = (helper_report(project, 2, "Mounts ordered."), end(project, "Done. Do you want the letters lit at night?"))[1]
        check("5 both owed in one turn: both hold, each reason once", (held, err.count(ROAD_HOLD), err.count(Q_ASK)), (True, 1, 1))
        check("5 the same turn ends next time: each held only once", end(project, "Done. Do you want the letters lit at night?")[0], False)
        rows = []
        for n in range(3, 6):                       # turns whose reply the roadmap holds; the questions check never does
            helper_report(project, n, "Step done.")
            rows.append(end(project, "Step recorded.")[2].count(ROAD_HOLD))
        st = json.load(open(os.path.join(project, ".claude", "questions", "state.json"), encoding="utf-8"))
        check("5 roadmap holds do not count toward the questions let-go", (rows, st["sessions"][MAIN].get("row")), ([1, 1, 1], 0))
        got = []
        for n in range(6, 10):                      # each turn's reply held by both: the questions check lets go on the fourth
            helper_report(project, n, "Step done.")
            err = end(project, f"Step {n} done. Should step {n + 1} be painted {['green', 'silver', 'black', 'gold'][n - 6]}?")[2]
            got.append((err.count(Q_ASK), err.count(ROAD_HOLD)))
        check("5 questions lets go after three in a row; the roadmap still holds its own", got, [(1, 1), (1, 1), (1, 1), (0, 1)])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    failed = [r for r in results if not r[1]]
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"\n     got  {got!r}\n     want {want!r}"))
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
