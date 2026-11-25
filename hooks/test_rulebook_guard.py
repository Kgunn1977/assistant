"""Tests of the assistant's guard hook (rulebook_guard.py) against a stand-in rule book.

    python hooks/test_rulebook_guard.py

The stand-in rule book's toy rules exist only here; they test the plumbing (which calls reach the rule book, scope,
live reading, failing closed), not the assistant's real rules. Everything is made in a temporary folder and removed.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "rulebook_guard.py")

STAND_IN = r'''
import json, os, sys
SAYS = {"A1": "A card follows the page's rules.", "B1": "Claude never sends.", "C1": "The program is changed only on an agreed change."}
def _route(ev):
    broken = []
    for w in ev["writes"]:
        if "\.assistant\outbox\\" in w["path"] and '"ok": true' not in (w["text"] or ""):
            broken.append("A1")
    if ev["where"] != "elsewhere":
        if "send" in ev["tool"].lower():
            broken.append("B1")
        system = os.path.join(ev["root"], "System")
        go = os.path.exists(os.path.join(ev["home"], "personal", "go"))
        for w in ev["writes"]:
            if os.path.normcase(w["path"]).startswith(os.path.normcase(system + os.sep)) and not go:
                broken.append("C1")
        if ev["command"] and ev["command_writes"] and "system" in ev["command"].lower() and not go:
            broken.append("C1")
    return broken
if __name__ == "__main__" and sys.argv[1:3] == ["route", "-"]:
    ev = json.load(sys.stdin)
    broken = _route(ev)
    print(json.dumps({"ok": not broken, "broken": [{"rule": r, "says": SAYS[r]} for r in broken]}))
    sys.exit(2 if broken else 0)
'''

results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def run(data, argv=(), env_data=None):
    env = dict(os.environ)
    env.pop("CLAUDE_PLUGIN_DATA", None)
    if env_data:
        env["CLAUDE_PLUGIN_DATA"] = env_data
    r = subprocess.run([sys.executable, GUARD, *argv], input=json.dumps(data), capture_output=True, text=True, env=env)
    return r.returncode, r.stderr


def main():
    tmp = tempfile.mkdtemp(prefix="guard-test-")
    try:
        root = os.path.join(tmp, "Assistant")
        book = os.path.join(root, "System", "live", "rules", "rulebook.py")
        os.makedirs(os.path.dirname(book))
        os.makedirs(os.path.join(root, "Live", "personal"))
        with open(book, "w", encoding="utf-8") as f:
            f.write(STAND_IN)
        data_dir = os.path.join(tmp, "plugin-data")
        os.makedirs(data_dir)
        with open(os.path.join(data_dir, "roots.json"), "w", encoding="utf-8") as f:
            json.dump({"roots": [root]}, f)
        project = os.path.join(tmp, "Other project")
        outbox = os.path.join(project, ".assistant", "outbox", "n1.json")
        program = os.path.join(root, "System", "live", "items.py")
        elsewhere = os.path.join(tmp, "elsewhere.txt")

        def call(tool, ti, cwd, argv=()):
            return run({"tool_name": tool, "tool_input": ti, "cwd": cwd, "session_id": "t"}, argv, data_dir)[0]

        # reading
        check("reading is never checked", call("Read", {"file_path": program}, root), 0)
        # (a) everywhere
        check("(a) a bad card to a project's outbox, from any session: refused",
              call("Write", {"file_path": outbox, "content": '{"title": "x"}'}, project), 2)
        check("(a) a good card: let through", call("Write", {"file_path": outbox, "content": '{"ok": true}'}, project), 0)
        code, why = run({"tool_name": "Write", "tool_input": {"file_path": outbox, "content": "{}"}, "cwd": project}, (), data_dir)
        check("(a) the refusal names the rule", "rule A1: A card follows" in why, True)
        # (b) assistant scope only
        check("(b) a send tool in the assistant's folder: refused", call("mcp__mail__send_email", {"to": "x"}, root), 2)
        check("(b) the same send elsewhere: let through (scope)", call("mcp__mail__send_email", {"to": "x"}, project), 0)
        check("(b) the same send in a hidden run: refused", call("mcp__mail__send_email", {"to": "x"}, tmp, ("--root", root)), 2)
        # (c) program edits, file tools and shell
        check("(c) an edit to the program with no go: refused",
              call("Edit", {"file_path": program, "old_string": "a", "new_string": "b"}, root), 2)
        check("(c) a shell command changing the program: refused",
              call("Bash", {"command": 'cp x "' + program + '"'}, root), 2)
        check("(c) a shell command that only reads the program: let through",
              call("Bash", {"command": 'cat "' + program + '"'}, root), 0)
        # the real rule book's (b): the Claude app's own session messaging goes, every mail or chat send is refused
        real = os.path.join(tmp, "Real")
        shutil.copytree(os.path.join(os.path.dirname(HERE), "engine", "System", "live", "rules"),
                        os.path.join(real, "System", "live", "rules"))
        os.makedirs(os.path.join(real, "Live", "personal"))
        real_data = os.path.join(tmp, "real-data")
        os.makedirs(real_data)
        with open(os.path.join(real_data, "roots.json"), "w", encoding="utf-8") as f:
            json.dump({"roots": [real]}, f)

        def real_call(tool, ti):
            return run({"tool_name": tool, "tool_input": ti, "cwd": real, "session_id": "t"}, (), real_data)[0]

        for tool in ("mcp__ccd_session_mgmt__send_message", "mcp__ccd_session__start_session", "SendMessage"):
            check(f"(b) real rule book, the app's session messaging {tool}: let through", real_call(tool, {"message": "x"}), 0)
        for tool in ("mcp__plugin_clearstream_clearstream__send_message", "mcp__e375060a__chat_send_message",
                     "mcp__mail__send_email", "mcp__gmail__send_mail", "mcp__outlook__reply_to_message",
                     "mcp__teamchat__chat_schedule_message", "mcp__ccd_session_mgmtx__send_message"):
            check(f"(b) real rule book, a real send {tool}: refused", real_call(tool, {"to": "x"}), 2)
        # an update step's own command is allowed, alone or with reads beside it; a real edit to the program is not
        script = os.path.join(real_data, "engine", "System", "live", "setup", "setup_home.py")
        prog = os.path.join(real, "System", "live", "answers.py")
        log = os.path.join(real, "Live", "logs", "pass.log")
        after = 'python "' + script + '" --root "' + real + '" update-after "0.1.3"'
        check("real rule book: the update's own step, alone: let through", real_call("Bash", {"command": after}), 0)
        check("real rule book: the update's own step with a read-only cmp and tail beside it, output joined: let through",
              real_call("Bash", {"command": after + '; cmp "' + prog + '" "' + prog + '.bak" 2>&1; tail -5 "' + log + '"'}), 0)
        check("real rule book: a read-only compare of a program file, output joined: let through",
              real_call("Bash", {"command": 'cmp "' + prog + '" x 2>&1'}), 0)
        check("real rule book: a real edit to a program file: refused", real_call("Bash", {"command": 'echo x > "' + prog + '"'}), 2)
        check("real rule book: the update's own step chained with a real edit to a program file: refused",
              real_call("Bash", {"command": after + '; echo x > "' + prog + '"'}), 2)
        check("real rule book: the update's own step chained with a copy over a program file: refused",
              real_call("Bash", {"command": after + ' && cp x "' + prog + '"'}), 2)
        # a rule changed in the rule book is enforced without touching the hook
        with open(book, encoding="utf-8") as f:
            text = f.read()
        with open(book, "w", encoding="utf-8") as f:
            f.write(text.replace('if "send" in ev["tool"].lower():', 'if False:'))
        check("rule book changed (b removed): the same send now goes through, hook untouched",
              call("mcp__mail__send_email", {"to": "x"}, root), 0)
        with open(os.path.join(root, "Live", "personal", "go"), "w") as f:
            f.write("yes")
        check("rule book state changed (a go recorded): the program edit now goes through",
              call("Write", {"file_path": program, "content": "x"}, root), 0)
        # Edit is checked on the text the file will hold
        os.makedirs(os.path.dirname(outbox), exist_ok=True)
        with open(outbox, "w") as f:
            f.write('{"ok": true}')
        check("(a) an edit that breaks a good card: refused (checked on the text after the edit)",
              call("Edit", {"file_path": outbox, "old_string": '"ok": true', "new_string": '"ok": false'}, project), 2)
        # failing closed
        with open(book, "w", encoding="utf-8") as f:
            f.write("this is not python (")
        check("broken rule book: a write naming the assistant is refused",
              call("Write", {"file_path": os.path.join(root, "Live", "x.json"), "content": "{}"}, root), 2)
        check("broken rule book: a card to a project outbox is refused", call("Write", {"file_path": outbox, "content": "{}"}, project), 2)
        check("broken rule book: unrelated work elsewhere goes on", call("Write", {"file_path": elsewhere, "content": "x"}, tmp), 0)
        check("broken rule book: reading still goes on", call("Read", {"file_path": program}, root), 0)
        check("broken rule book: anything in a hidden run is refused",
              call("Write", {"file_path": elsewhere, "content": "x"}, tmp, ("--root", root)), 2)
        # no assistant on the computer
        os.remove(os.path.join(data_dir, "roots.json"))
        check("no copy of the assistant recorded: nothing is refused", call("Write", {"file_path": outbox, "content": "{}"}, project), 0)
        check("unreadable call: refused", subprocess.run([sys.executable, GUARD], input="not json", capture_output=True,
                                                          text=True).returncode, 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    failed = [r for r in results if not r[1]]
    for name, ok, got, want in results:
        if not ok:
            print(f"FAIL {name}: wanted {want!r}, got {got!r}")
    print(f"{len(results) - len(failed)} of {len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
