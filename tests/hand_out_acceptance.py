r"""Acceptance: after an update, each of the owner's other Claude sessions is offered its step (scripts\hand_out.py; the update
skill's step 4). Made-up sessions and projects in a throwaway folder; nothing is sent by this test or by the script.

1. From the desktop app's session list: every open session gets a reload; a roadmap project's main session (found by the id
   the roadmap keeps) also gets its roadmap's update, told to wait for the reload; this session, archived sessions and
   sessions that need nothing are left out; a roadmap whose main session is not open is left for the person.
2. Without a session list: the roadmap projects in the settings and the projects with a questions file stand in; one that
   cannot be messaged is left for the person; a questions file turned off is left out.
3. Nothing is sent without the yes: only "1" or "2 <numbers>" picks rows; "3", nothing, or any other words pick none.
4. The messages: the reload line put in front of the person, the roadmap step with its instructions' real path and the
   session to report back to; the skill asks before it sends.
5. The questions hook keeps the list of projects with a questions file; the roadmap's update instructions reach the plugin's
   data folder.

    python tests\hand_out_acceptance.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
SCRIPT = os.path.join(PKG, "scripts", "hand_out.py")
sys.path.insert(0, os.path.join(PKG, "scripts"))
sys.path.insert(0, os.path.join(PKG, "hooks"))
import hand_out  # noqa: E402

results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def put(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)


def main():
    tmp = tempfile.mkdtemp(prefix="hand-out-")
    try:
        root, data = os.path.join(tmp, "Assistant"), os.path.join(tmp, "plugin-data")
        a, b, c, d, e = (os.path.join(tmp, "Projects", n) for n in ("Garden Shed", "Bakery Site", "Tide Charts", "Choir Notes", "Old Ideas"))
        put(os.path.join(a, ".claude", "roadmap", "config.json"), {"director_session_id": "x1", "director_local_id": "local_aaa"})
        put(os.path.join(b, ".claude", "roadmap", "config.json"), {"director_session_id": "x2", "director_local_id": "local_bbb"})
        put(os.path.join(c, ".claude", "roadmap", "config.json"), {"director_session_id": "x3"})
        put(os.path.join(d, ".claude", "questions", "config.json"), {"on": True})
        put(os.path.join(e, ".claude", "questions", "config.json"), {"on": False})
        put(os.path.join(root, "Live", "personal", "settings.json"), {"roadmaps": [{"folder": a}, {"folder": b}, {"folder": c}]})
        put(os.path.join(data, "questions-projects.json"), {"projects": [d, e]})
        sessions = [
            {"sessionId": "local_aaa", "title": "Shed build", "cwd": a, "isArchived": False},
            {"sessionId": "local_wt1", "title": "Shed roof helper", "cwd": os.path.join(a, ".claude", "worktrees", "roof"), "isArchived": False},
            {"sessionId": "local_ccc", "title": "Recipe notes", "cwd": os.path.join(tmp, "Recipes"), "isArchived": False},
            {"sessionId": "local_old", "title": "Done long ago", "cwd": a, "isArchived": True},
            {"sessionId": "local_me", "title": "This update", "cwd": root, "isArchived": False},
        ]

        # 1. from the session list
        p = hand_out.plan(root, sessions, "local_me", data)
        rows = {r["id"]: r for r in p["rows"]}
        check("1 each open session gets the right step; this one and the archived one are left out",
              {k: r["steps"] for k, r in rows.items()},
              {"local_aaa": ["roadmap", "reload"], "local_wt1": ["reload"], "local_ccc": ["reload"]})
        check("1 one numbered line per session", [r["line"] for r in p["rows"]],
              ["1. Shed build (" + a + "): update its roadmap, after you reload it",
               "2. Shed roof helper (" + os.path.join(a, ".claude", "worktrees", "roof") + "): reload",
               "3. Recipe notes (" + os.path.join(tmp, "Recipes") + "): reload"])
        check("1 a roadmap whose main session is not open, or not recorded, is left for the person",
              [l.startswith(f + ": ") for l, f in zip(p["left"], (b, c))] + [("not among the open sessions" in p["left"][0]),
                                                                            ("does not record" in p["left"][1])],
              [True, True, True, True])
        check("1 the question: 1 send each, 2 pick which, 3 none", p["ask"],
              "Send each of these sessions its step? 1 send each its step, 2 pick which (for example \"2 1,3\"), 3 none.")
        check("1 nobody needs nothing: an empty list asks nothing", hand_out.plan(os.path.join(tmp, "Nobody"), [], "local_me", data),
              {"rows": [], "left": [], "ask": None, "from": "sessions"})

        # 4. the messages
        m1, m2 = rows["local_aaa"]["message"], rows["local_wt1"]["message"]
        skill_file = os.path.join(data, "skills", "roadmap-update", "SKILL.md").replace("\\", "/")
        check("4 roadmap main: the reload line first, then its roadmap update from the real instructions, then report back",
              ("/reload-plugins" in m1, m1.index("/reload-plugins") < m1.index(skill_file), "that is " + data.replace("\\", "/") in m1,
               "session local_me with SendMessage" in m1),
              (True, True, True, True))
        check("4 other sessions: only the reload line, no report back",
              ("/reload-plugins" in m2, "roadmap" in m2, "do not report back" in m2), (True, False, True))
        check("4 the end lines: what was done and what is left",
              (rows["local_aaa"]["if_sent"], rows["local_ccc"]["if_not_sent"]),
              ("Shed build: sent; it updates its roadmap after you type /reload-plugins there, and reports back",
               "Recipe notes: not sent; left for you: type /reload-plugins there"))

        # 3. nothing sent without the yes
        ids = lambda ans: [r["id"] for r in hand_out.pick(p, ans)]
        check("3 answers: 1 all, 2 with numbers those, anything else none",
              [ids("1"), ids("2 1,3"), ids("2: 2"), ids("3"), ids(""), ids("yes"), ids("sure, send them"), ids("2"), ids("13")],
              [["local_aaa", "local_wt1", "local_ccc"], ["local_aaa", "local_ccc"], ["local_wt1"], [], [], [], [], [], []])

        # 2. without a session list
        f = hand_out.plan(root, None, None, data)
        check("2 the known projects stand in: each roadmap's main session and the questions project; one turned off left out",
              [(os.path.basename(r["folder"]), r["steps"], r["sendable"]) for r in f["rows"]],
              [("Garden Shed", ["roadmap", "reload"], True), ("Bakery Site", ["roadmap", "reload"], True),
               ("Tide Charts", ["roadmap", "reload"], False), ("Choir Notes", ["reload"], False)])
        check("2 those that cannot be messaged are left for the person", f["left"],
              ["The main session of Tide Charts: not sent; left for you: type /reload-plugins there, then /assistant:roadmap-update",
               "The sessions in Choir Notes: not sent; left for you: type /reload-plugins there"])
        check("2 a pick never includes one that cannot be messaged", [r["id"] for r in hand_out.pick(f, "1")], ["local_aaa", "local_bbb"])
        only_q = hand_out.plan(os.path.join(tmp, "Nobody"), None, None, data)
        check("2 nothing that can be sent: no question asked", (only_q["ask"], len(only_q["left"])), (None, 1))

        # the commands, end to end, keeping their files in the plugin's data folder
        put(os.path.join(data, "hand-out", "sessions.json"), sessions)
        run = lambda *args: json.loads(subprocess.run([sys.executable, SCRIPT, *args, "--data", data], capture_output=True, text=True, check=True).stdout)
        out = run("plan", "--root", root, "--sessions", "--here", "local_me")
        check("commands: plan reads the saved list and keeps its plan", (len(out["rows"]), os.path.isfile(os.path.join(data, "hand-out", "plan.json"))), (3, True))
        check("commands: pick reads the kept plan; 3 sends nothing", ([r["id"] for r in run("pick", "--answer", "2 3")["send"]], run("pick", "--answer", "3")["send"]),
              (["local_ccc"], []))

        # 4. the skill asks before it sends
        skill = open(os.path.join(PKG, "skills", "update", "SKILL.md"), encoding="utf-8").read()
        step = skill[skill.index("## 4. Your other sessions"):]
        check("4 the update skill shows the lines and the question, ends its reply, and sends only what pick returns",
              ("Nothing is sent without the person's yes" in step, step.index("end your reply") < step.index("hand_out.py\" pick"),
               "Send each row under `send`" in step, "an empty `send` means nothing is sent" in step),
              (True, True, True, True))

        # 5. the questions hook keeps the list; the roadmap update instructions reach the data folder
        proj = os.path.join(tmp, "Projects", "Fence Plans")
        put(os.path.join(proj, ".claude", "questions", "config.json"), {"on": True})
        env = dict(os.environ, CLAUDE_PLUGIN_DATA=data, CLAUDE_PROJECT_DIR=proj)
        subprocess.run([sys.executable, os.path.join(PKG, "hooks", "questions_blocks.py")], text=True, env=env, capture_output=True,
                       input=json.dumps({"hook_event_name": "PostToolUse", "session_id": "s9", "cwd": proj, "tool_name": "Bash",
                                         "tool_input": {"command": 'python "C:/data/scripts/questions_setup.py" on'}}))
        listed = json.load(open(os.path.join(data, "questions-projects.json"), encoding="utf-8"))["projects"]
        check("5 turning the questions file on adds the project to the list, once", (listed[-1] == proj, listed.count(proj)), (True, 1))
        import working_copy
        dest = os.path.join(tmp, "copy")
        working_copy.sync(dest)
        check("5 the roadmap's update instructions are in the plugin's data folder",
              open(os.path.join(dest, "skills", "roadmap-update", "SKILL.md"), encoding="utf-8").read()
              == open(os.path.join(PKG, "skills", "roadmap-update", "SKILL.md"), encoding="utf-8").read(), True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    failed = [r for r in results if not r[1]]
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"\n     got  {got!r}\n     want {want!r}"))
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
