r"""Acceptance: the questions file (skills questions-setup, questions, questions-off; scripts\questions_setup.py; hooks\questions_blocks.py),
in a throwaway project folder. The turns of a session are played through the real hook script the way Claude Code calls it (a JSON
payload on stdin; context on stdout; a held reply as exit 2 with the reason), and the file is edited the way the session would.

The plan's "How to tell it works", 1 to 7, with the 11/19 change (no "Open:" list in chat; the reply to an answer is a one-line echo):
1. Five questions asked over a few turns: all five in the file, numbered from 1 with no gaps after every edit.
2. "2b": the reply is the echo naming the question in words; the question leaves the file and the rest renumber.
3. An answer that asks for more detail: the question stays, reworded, in its place by age.
4. No list of open questions in chat: a reply is never held for leaving one out.
5. A reply after an answer that did not change the file is held once; a reply asking a question not in the file is held once; a
   session is let go after three holds in a row.
6. A session resumed is shown the open questions before it answers anything; a second session in the project with no file of its
   own is shown nothing and never held.
7. A project that also has a roadmap: the roadmap's own checks behave as before (its hook suites pass; this test runs the
   roadmap hook beside it on the same turns and it answers exactly as it does alone).
Also: a project that never turned it on is untouched; turning it off stops the checks and keeps the file.

    python tests\questions_acceptance.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
HOOK = os.path.join(PKG, "hooks", "questions_blocks.py")
ROADMAP_HOOK = os.path.join(PKG, "hooks", "roadmap_blocks.py")
SETUP = os.path.join(PKG, "scripts", "questions_setup.py")
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def hook(project, payload, script=HOOK):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=project)
    r = subprocess.run([sys.executable, script], input=json.dumps(dict(payload, cwd=project)), capture_output=True, text=True, env=env, timeout=60)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def write_q(project, qs, fname="Questions.md"):
    """The file as the session keeps it: the open questions, numbered from 1."""
    head = "# Questions\n\nOpen questions for the person in this project, oldest first.\nAnswer in chat by number and letter, for example \"1b\", or in your own words.\n\n"
    body = "\n".join(f"{n}. {q}\n\n    a. Yes  \n    b. No  \n\n    Recommended: a  \n    Asked: 11/19\n" for n, q in enumerate(qs, 1)) if qs else "No open questions.\n"
    with open(os.path.join(project, fname), "w", encoding="utf-8", newline="\n") as f:
        f.write(head + body)


def numbers(project):
    import re
    text = open(os.path.join(project, "Questions.md"), encoding="utf-8").read()
    return [int(m) for m in re.findall(r"^(\d+)\.", text, re.M)]


def per_session():
    """Two sessions in one project each get their own file, a third with none is left alone, off for one leaves the other on."""
    tmp = tempfile.mkdtemp(prefix="questions-two-")
    try:
        def turn_on(sid, title):
            out = json.loads(subprocess.run([sys.executable, SETUP, "--project", tmp, "on", "--title", title], capture_output=True, text=True).stdout)
            hook(tmp, {"hook_event_name": "PostToolUse", "session_id": sid, "tool_name": "Bash",
                       "tool_input": {"command": 'python "C:/data/scripts/questions_setup.py" on --title "' + title + '"'}})
            return out["name"]
        a_name, b_name = turn_on("sess-a", "Plan the sign"), turn_on("sess-b", "Order the parts")
        write_q(tmp, ["Which color for the sign?"], a_name)
        write_q(tmp, ["Which supplier sold the head?"], b_name)
        shown = lambda sid: hook(tmp, {"hook_event_name": "UserPromptSubmit", "session_id": sid, "prompt": "hello"})[1]
        held = lambda sid: hook(tmp, {"hook_event_name": "Stop", "session_id": sid, "last_assistant_message": "Which color do you want for the sign?"})[0]
        helper = hook(tmp, {"hook_event_name": "UserPromptSubmit", "session_id": "sess-a", "agent_id": "h1", "prompt": "x"})[1]
        text_a = open(os.path.join(tmp, a_name), encoding="utf-8").read()
        check("two sessions: each has its own file, the first keeps Questions.md, the layout is the chat's",
              [a_name, b_name, "1. Which color for the sign?\n\n    a. Yes" in text_a], ["Questions.md", "Questions - Order the parts.md", True])
        check("two sessions: each is shown only its own questions; a third with none, and a helper, get nothing",
              ["Which color" in shown("sess-a") and "supplier" not in shown("sess-a"), "supplier" in shown("sess-b") and "Which color" not in shown("sess-b"),
               shown("sess-c"), helper, held("sess-c")], [True, True, "", "", 0])
        subprocess.run([sys.executable, SETUP, "--project", tmp, "off", "--this-session"], capture_output=True, text=True)
        hook(tmp, {"hook_event_name": "PostToolUse", "session_id": "sess-a", "tool_name": "Bash",
                   "tool_input": {"command": 'python "C:/data/scripts/questions_setup.py" off --this-session'}})
        check("off for one session leaves the other on, and both files stay",
              [shown("sess-a"), "supplier" in shown("sess-b"), os.path.isfile(os.path.join(tmp, a_name)), os.path.isfile(os.path.join(tmp, b_name))],
              ["", True, True, True])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    tmp = tempfile.mkdtemp(prefix="questions-")
    project, other = os.path.join(tmp, "Test project"), os.path.join(tmp, "Untouched project")
    os.makedirs(project)
    os.makedirs(other)
    try:
        MAIN, SECOND = "sess-main", "sess-second"
        say = lambda sid, prompt: hook(project, {"hook_event_name": "UserPromptSubmit", "session_id": sid, "prompt": prompt})
        end = lambda sid, reply: hook(project, {"hook_event_name": "Stop", "session_id": sid, "last_assistant_message": reply, "stop_hook_active": False})

        # a project that never turned it on is untouched
        write_q(other, ["Which color for the sign?"])
        check("a project that never turned it on: nothing shown, nothing held",
              [hook(other, {"hook_event_name": "UserPromptSubmit", "session_id": "x", "prompt": "1a"}),
               hook(other, {"hook_event_name": "Stop", "session_id": "x", "last_assistant_message": "Which color do you want?"})],
              [(0, "", ""), (0, "", "")])

        # turned on: the file is made and the session that ran it becomes the one that writes it
        r = subprocess.run([sys.executable, SETUP, "--project", project, "on"], capture_output=True, text=True)
        made = json.loads(r.stdout)
        hook(project, {"hook_event_name": "PostToolUse", "session_id": MAIN, "tool_name": "Bash",
                       "tool_input": {"command": 'python "C:/data/scripts/questions_setup.py" on'}})
        st = json.loads(subprocess.run([sys.executable, SETUP, "--project", project, "status"], capture_output=True, text=True).stdout)
        check("turning it on makes Questions.md with no open questions and records this session as the writer",
              [made["made"], "No open questions." in open(os.path.join(project, "Questions.md"), encoding="utf-8").read(), st["on"], st["main_session"]],
              [True, True, True, MAIN])

        # 1. five questions over a few turns, numbered from 1 with no gaps after every edit
        asked = ["Who heads the writing team?", "Who runs the Thursday meeting?", "Who is hired first?", "Which week does it start?",
                 "Is the budget per month or per year?"]
        ok = []
        for i, pair in enumerate((asked[:2], asked[2:4], asked[4:])):
            say(MAIN, "Let's plan the team.")
            write_q(project, asked[:sum(len(p) for p in (asked[:2], asked[2:4], asked[4:])[:i + 1])])
            code, _o, _e = end(MAIN, "I put two questions in the file: " + " ".join(pair))
            ok.append((code, numbers(project)))
        check("1. five questions asked over three turns: all in the file, numbered from 1 with no gaps, no reply held",
              ok, [(0, [1, 2]), (0, [1, 2, 3, 4]), (0, [1, 2, 3, 4, 5])])

        # 6. a second session, and a resumed one, are shown the open questions first
        _c, shown, _e = say(SECOND, "What are we waiting on?")
        _c, resumed, _e = hook(project, {"hook_event_name": "SessionStart", "session_id": MAIN, "source": "resume"})
        check("6. a second session with no file of its own is shown nothing", shown, "")
        check("6. a resumed session is shown them too, as the one that keeps the file",
              ["Open questions in this session's Questions.md" in resumed, "Never list the open questions in chat" in resumed], [True, True])

        # 2. "2b": echo in words, the question leaves the file, the rest renumber
        _c, ctx, _e = say(MAIN, "2b")
        check("2. on each message the main session is shown the open questions with what to do", "Match the person's message against them" in ctx, True)
        write_q(project, [q for q in asked if q != asked[1]])
        code, _o, why = end(MAIN, "Took 2b as: the Thursday meeting is run by the writing team head.")
        check("2. \"2b\": the question leaves the file, the rest renumber 1 to 4, the one-line echo is not held",
              [code, numbers(project), open(os.path.join(project, "Questions.md"), encoding="utf-8").read().count("Thursday")], [0, [1, 2, 3, 4], 0])

        # 3. an answer asking for more detail: the question stays, reworded, in its place by age
        say(MAIN, "For 3, what would each of them cost?")
        left = [q for q in asked if q != asked[1]]
        left[1] = "Who is hired first? The editor costs about $500 a month and the designer about $400."
        write_q(project, left)
        code, _o, _e = end(MAIN, "Took 3 as a question about cost: I added what each costs to the hiring question, which stays open.")
        check("3. an answer asking for more: still open, reworded, still second by age (it was 3 before the answer to 2; 2 now)",
              [code, numbers(project), "costs about $500" in open(os.path.join(project, "Questions.md"), encoding="utf-8").read().split("\n2. ")[1].split("\n3. ")[0]],
              [0, [1, 2, 3, 4], True])

        # 4. never a list in chat: a reply without any "Open:" line is not held
        say(MAIN, "Thanks, that's all for now.")
        check("4. no list of open questions in chat: a reply without one is not held", end(MAIN, "Good. Nothing else is needed today.")[0], 0)

        # 5A. an answer that did not change the file is held once, with a plain reason; then it passes
        say(MAIN, "1a")
        code1, _o, why1 = end(MAIN, "Took 1a as: Dana heads the writing team.")
        code2, _o, _e = end(MAIN, "Took 1a as: Dana heads the writing team.")
        check("5. an answer that did not change the file: held once, with the plain reason; not held twice for the same turn",
              [code1, "has not changed" in why1, code2], [2, True, 0])
        # an answer in words, seen only by the reply's echo
        say(MAIN, "Dana should head it.")
        check("5. an answer in words, seen by the reply's echo, with the file unchanged: held", end(MAIN, "Took that as: Dana heads the writing team.")[0], 2)
        end(MAIN, "Took that as: Dana heads the writing team.")

        # 5B (the experiment). a new question put in the reply but not in the file is held; one already in the file is not
        say(MAIN, "What else do we need?")
        codeB, _o, whyB = end(MAIN, "One more thing to settle. Should the newsletter go out weekly or every two weeks?")
        check("5. a reply asking a new question that is not in the file: held once, naming it",
              [codeB, "Should the newsletter go out weekly or every two weeks?" in whyB], [2, True])
        write_q(project, left + ["Should the newsletter go out weekly or every two weeks?"])
        check("5. ... once it is written into the file, the same reply passes",
              end(MAIN, "One more thing to settle. Should the newsletter go out weekly or every two weeks?")[0], 0)
        say(MAIN, "Remind me of the hiring one.")
        check("5. a question already in the file, asked again in other words, is not held",
              end(MAIN, "Who should be hired first, the editor or the designer?")[0], 0)
        say(MAIN, "Write it up.")
        check("5. a question inside quoted words or code is not taken as a question to the person",
              end(MAIN, "The note says \"Who is coming on Friday?\" and the code has ```if x?```. I wrote it up.")[0], 0)

        # 5. let go after three holds in a row (each a new turn whose reply is held)
        held = []
        for i in range(4):
            say(MAIN, f"{i + 1}a")
            held.append(end(MAIN, "Took it as: yes.")[0])
        check("5. three holds in a row, then let go: never a loop", held, [2, 2, 2, 0])

        # a helper (subagent) and other sessions are never held
        say(MAIN, "1a")
        check("only the main session's own reply is held: a helper's end and another session's end pass",
              [hook(project, {"hook_event_name": "Stop", "session_id": MAIN, "agent_id": "a1", "last_assistant_message": "Which one?"})[0],
               end(SECOND, "Should we ask the person which one?")[0]], [0, 0])
        end(MAIN, "Took 1a as: yes.")

        # 7. a project with a roadmap too: the roadmap hook answers the same turns exactly as it does alone
        os.makedirs(os.path.join(project, ".claude", "roadmap"))
        with open(os.path.join(project, ".claude", "roadmap", "config.json"), "w") as f:
            json.dump({"director_session_id": MAIN, "writes": "main", "page_url": "https://claude.ai/code/artifact/abc"}, f)
        rm = [hook(project, {"hook_event_name": "UserPromptSubmit", "session_id": MAIN, "prompt": "go on"}, ROADMAP_HOOK),
              hook(project, {"hook_event_name": "Stop", "session_id": MAIN, "last_assistant_message": "Done."}, ROADMAP_HOOK)]
        alone = os.path.join(tmp, "Roadmap only")
        os.makedirs(os.path.join(alone, ".claude", "roadmap"))
        shutil.copy(os.path.join(project, ".claude", "roadmap", "config.json"), os.path.join(alone, ".claude", "roadmap", "config.json"))
        rm_alone = [hook(alone, {"hook_event_name": "UserPromptSubmit", "session_id": MAIN, "prompt": "go on"}, ROADMAP_HOOK),
                    hook(alone, {"hook_event_name": "Stop", "session_id": MAIN, "last_assistant_message": "Done."}, ROADMAP_HOOK)]
        check("7. with a roadmap too, the roadmap's own check answers exactly as in a project with only a roadmap", rm, rm_alone)

        # turned off: the checks stop, the file stays
        subprocess.run([sys.executable, SETUP, "--project", project, "off"], capture_output=True, text=True)
        say(MAIN, "1a")
        check("turned off: nothing shown, nothing held, the file kept as it was",
              [say(MAIN, "2a"), end(MAIN, "Which one do you mean?"), numbers(project)], [(0, "", ""), (0, "", ""), [1, 2, 3, 4, 5]])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    per_session()
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
