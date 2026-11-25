r"""Acceptance: a session's questions file copied to the project's roadmap (scripts\questions_setup.py roadmap), with made-up data.

1. A made-up "Questions - Garden plans.md" with 3 questions syncs to ONE board document holding its text, with the session's
   name (from the app's session list, by its local_... id) and when it changed; no "questions" documents are written.
2. Answering in chat (the question leaves the file) and syncing again updates the same document.
3. With no roadmap, the command changes nothing; with a reader keeping the full copy, a patch for it is named too.
4. In a project whose main session writes the roadmap itself, another session may write its own file's copy; a row write
   or a "questions" write from it is still refused.
5. The questions hook moves a record made by the app's own id to the session's local_... id, so a restart keeps it.
6. Turning the file off saves the delete that takes the copy off the page.
7. The page template has the read-only "Questions in chat" section and no "From chat" cards.

    python tests\questions_on_roadmap_acceptance.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
SETUP = os.path.join(PKG, "scripts", "questions_setup.py")
HOOK = os.path.join(PKG, "hooks", "roadmap_blocks.py")
URL = "https://claude.ai/artifact/TestRoad77"
FNAME = "Questions - Garden plans.md"
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def put(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj))


def run(project, *args, env=None):
    r = subprocess.run([sys.executable, SETUP, "--project", project, *args], capture_output=True, text=True, timeout=60, env=env)
    return json.loads(r.stdout or "{}")


def qfile(project):
    with open(os.path.join(project, FNAME), encoding="utf-8") as f:
        return f.read()


WOOD = "2. Which wood for the raised beds?\n\n    Recommended: no recommendation  \n    Asked: 11/25\n\n"
QFILE = ("# Questions\n\nAnswer in chat by number and letter, for example \"1b\", or in your own words.\n\n"
         "1. Should the tomato bed go by the fence?\n\n    a. By the fence  \n    b. By the shed  \n\n    Recommended: a, more sun  \n    Asked: 11/25\n\n"
         + WOOD + "3. How deep should the beds be?\n\n    a. 30 cm  \n    b. 45 cm  \n\n    Recommended: b  \n    Asked: 11/25\n")


LOCAL = "local_made-up-garden-0001"
QHOOK = os.path.join(PKG, "hooks", "questions_blocks.py")
PAGE = os.path.join(PKG, "page", "roadmap.html")


def writes_of(got):
    return json.load(open(got["writes_file"], encoding="utf-8"))["writes"]


def main():
    project = tempfile.mkdtemp(prefix="q-road-")
    conf = os.path.join(project, "claude-config")
    env = dict(os.environ, CLAUDE_CONFIG_DIR=conf, TEMP=project, TMPDIR=project, CLAUDE_PROJECT_DIR=project)
    env.pop("CLAUDE_CODE_HOST_SESSION_ID", None)
    try:
        # the app's list of running sessions: the garden session, under a new own id after a restart
        put(os.path.join(conf, "sessions", "1234.json"), {"pid": os.getpid(), "sessionId": "sess-garden-after-restart",
            "hostSessionId": LOCAL, "name": "Garden plans", "cwd": project})
        put(os.path.join(project, ".claude", "questions", "config.json"),
            {"on": True, "sessions": {"sess-main": "Questions.md", LOCAL: FNAME}})
        put(os.path.join(project, FNAME), QFILE)

        got = run(project, "roadmap", "--file", FNAME, env=env)
        check("3. no roadmap: says so", got.get("roadmap"), False)
        check("3. no roadmap: file untouched", qfile(project), QFILE)

        put(os.path.join(project, ".claude", "roadmap", "config.json"), {"page_url": URL, "director_session_id": "sess-main", "writes": "main"})

        got = run(project, "roadmap", "--file", FNAME, env=env)
        writes = writes_of(got)
        check("1. one board document", [(w["op"], w["collection"], w["doc_id"]) for w in writes], [("set", "board", "questions-file--" + LOCAL)])
        d = writes[0]["data"]
        check("1. holds the file's text as written", d["text"], QFILE)
        check("1. session name and count", (d["session_name"], d["session"], d["file"], d["open"]), ("Garden plans", LOCAL, FNAME, 3))
        check("1. when it changed", bool(d.get("changed")), True)
        check("1. no question documents", any(w["collection"] == "questions" for w in writes), False)
        check("1. file untouched", qfile(project), QFILE)

        # 2. the person answers the wood question in chat: the session takes it out and renumbers, then syncs
        after = QFILE.replace(WOOD, "").replace("3. How deep", "2. How deep")
        put(os.path.join(project, FNAME), after)
        put(os.path.join(project, "Roadmap page", "readers.json"), {"readers": {"live page": {"full": True}}})
        got = run(project, "roadmap", "--file", FNAME, env=env)
        writes2 = writes_of(got)
        check("2. same document, new text", (writes2[0]["doc_id"], writes2[0]["data"]["text"], writes2[0]["data"]["open"]),
              ("questions-file--" + LOCAL, after, 2))
        check("3. full copy patch named", "full-patch" in got.get("full_patch", ""), True)

        # 4. the guard: another session's own file copy passes; a row or a questions write is refused
        def guard(ti, sid="sess-garden-after-restart"):
            r = subprocess.run([sys.executable, HOOK], input=json.dumps({"hook_event_name": "PreToolUse", "session_id": sid, "cwd": project,
                               "tool_name": "ArtifactData", "tool_input": ti}), capture_output=True, text=True, timeout=60, env=env)
            return r.returncode
        check("4. other session writes its file copy", guard({"action": "batch", "url": URL, "writes": writes2}), 0)
        check("4. other session's row write refused", guard({"action": "set", "url": URL, "collection": "steps", "doc_id": "step-01", "data": {}}), 2)
        check("4. other session's questions write refused", guard({"action": "set", "url": URL, "collection": "questions", "doc_id": "q-x", "data": {}}), 2)

        # 5. a record made by the app's own id moves to the local id
        put(os.path.join(project, ".claude", "questions", "config.json"),
            {"on": True, "sessions": {"sess-main": "Questions.md", "sess-garden-after-restart": FNAME}})
        subprocess.run([sys.executable, QHOOK], input=json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "sess-garden-after-restart",
                       "cwd": project, "prompt": "hello"}), capture_output=True, text=True, timeout=60, env=env)
        cfg = json.load(open(os.path.join(project, ".claude", "questions", "config.json"), encoding="utf-8"))
        check("5. record moved to the local id", cfg["sessions"], {"sess-main": "Questions.md", LOCAL: FNAME})

        # 6. off for that session (named by its app id) saves the delete
        got = run(project, "off", "--session", "sess-garden-after-restart", env=env)
        check("6. off deletes the copy", [(w["op"], w["collection"], w["doc_id"]) for w in writes_of(got)], [("delete", "board", "questions-file--" + LOCAL)])

        page = open(PAGE, encoding="utf-8").read()
        check("7. page has the section", all(w in page for w in ('id="qfiles"', '"Questions in chat"', "questions-file--", "session_name")), True)
        check("7. page shows no From chat cards", ("From chat" in page, 'q.source !== "chat"' in page), (False, True))
    finally:
        shutil.rmtree(project, ignore_errors=True)
    bad = [r for r in results if not r[1]]
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"\n   got:  {got!r}\n   want: {want!r}"))
    print(f"{len(results) - len(bad)} of {len(results)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
