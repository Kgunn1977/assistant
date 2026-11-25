r"""Acceptance (quick): a Claude desktop session in the assistant's folder that joined (/assistant:talk) shares Talk to your
assistant. Its words and reply land in the one conversation marked "desktop" and reach the page's data; it is shown what
the box said; a session that never joined is left alone; ACTION lines it hands to desk.py act are done by the box's own
handling with the owner's recorded words as their authority. On a scratch home laid down from this plugin; nothing is sent.

    python tests\desk_talk_acceptance.py
"""
import glob
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="desktalk-")
    data, root = os.path.join(tmp, "data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("ac_desk", os.path.join(PKG, "hooks", "assistant_copy.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    def hook(payload):
        r = subprocess.run([sys.executable, os.path.join(PKG, "hooks", "desk_turns.py")], input=json.dumps(dict(payload, cwd=root)),
                           capture_output=True, text=True, env=env, timeout=150)
        return r.stdout

    def turns():
        return (json.load(open(os.path.join(home, "chat.json"), encoding="utf-8")).get("turns") or []) if os.path.exists(os.path.join(home, "chat.json")) else []

    try:
        m.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47946", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import db; db.init_schema()", live],
                       env=env, cwd=live, check=True)
        with open(os.path.join(root, "CLAUDE.md"), encoding="utf-8") as f:
            note = f.read()
        check("the folder's CLAUDE.md is the new text", ("desk.py act" in note, "chat.py --instructions" in note), (True, True))
        with open(os.path.join(home, "items.json"), "w", encoding="utf-8") as f:      # a home after its first check has its cards
            json.dump({"items": []}, f)
        with open(os.path.join(home, "chat.json"), "w", encoding="utf-8") as f:       # the box said something first
            json.dump({"turns": [{"who": "you", "text": "box words about the garden trailer", "at": "2026-11-23T09:00:00"},
                                 {"who": "assistant", "text": "box reply about the trailer", "at": "2026-11-23T09:00:05"}]}, f)

        hook({"session_id": "other", "hook_event_name": "UserPromptSubmit", "prompt": "not joined"})
        check("a session that never joined adds nothing", len(turns()), 2)

        hook({"session_id": "s1", "hook_event_name": "PreToolUse", "tool_input": {"command": r"python System\live\desk.py join"}})
        r = subprocess.run([sys.executable, os.path.join(live, "desk.py"), "join"], capture_output=True, text=True, env=env, cwd=root)
        check("join says the session is joined", r.stdout.startswith("This session is now Talk to your assistant"), True)

        out = hook({"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": "add a task to call the trailer shop"})
        ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"] if out.strip() else ""
        check("the session is shown what the box said", "box reply about the trailer" in ctx, True)
        t = turns()[-1]
        check("his words land in the conversation, marked desktop", (t["who"], t["text"], t["desktop"]), ("you", "add a task to call the trailer shop", "s1"))

        tr = os.path.join(tmp, "t.jsonl")
        with open(tr, "w", encoding="utf-8") as f:
            for e in ({"type": "user", "message": {"role": "user", "content": "add a task to call the trailer shop"}},
                      {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Bash"}]}},
                      {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "That call is a task for you."}]}}):
                f.write(json.dumps(e) + "\n")
        hook({"session_id": "s1", "hook_event_name": "Stop", "transcript_path": tr})
        hook({"session_id": "s1", "hook_event_name": "Stop", "transcript_path": tr})       # a held reply's second stop
        t = turns()
        check("the reply lands once, marked desktop", (t[-1]["who"], t[-1]["text"], t[-1]["desktop"], len(t)), ("assistant", "That call is a task for you.", "s1", 4))

        hook({"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": "<task-notification>a helper finished</task-notification>"})
        hook({"session_id": "s1", "hook_event_name": "Stop", "transcript_path": tr})
        check("a notice that is not his typing is not added, nor its reply", len(turns()), 4)

        acts = os.path.join(tmp, "acts.txt")
        with open(acts, "w", encoding="utf-8") as f:
            f.write('ACTION: {"type": "task", "title": "Call the trailer shop"}\n')
        # the words the box's handling is given are the ones the hook recorded for the session running act
        probe = ("import sys, json; sys.path.insert(0, sys.argv[1]); import chat, desk; seen = []; real = chat._do_all\n"
                 "def spy(a, text, when, first=0):\n    seen.append(text); return real(a, text, when, first)\n"
                 "chat._do_all = spy; said = desk.act(open(sys.argv[2], encoding='utf-8').read()); print(json.dumps([seen, said]))")

        def act_as(sid):
            hook({"session_id": sid, "hook_event_name": "PreToolUse", "tool_input": {"command": r"python System\live\desk.py act " + acts}})
            r = subprocess.run([sys.executable, "-c", probe, live, acts], capture_output=True, text=True, env=env, cwd=live, timeout=200)
            return json.loads(r.stdout.strip().splitlines()[-1])

        seen, said = act_as("s1")
        check("ACTION goes through chat's own handling with his recorded words", seen, ["add a task to call the trailer shop"])
        check("the program says what it did", said.startswith("Done on the page: 1 card changed"), True)
        snap = json.load(open(os.path.join(home, "items.json"), encoding="utf-8")).get("items") or []
        check("the task card is on the page's items", any(i.get("title") == "Call the trailer shop" for i in snap), True)

        with open(acts, "w", encoding="utf-8") as f:
            f.write('ACTION: {"type": "calendar", "do": "delete", "find": "trailer"}\n')
        seen, said = act_as("s1")
        check("a calendar removal his words do not ask for is refused by the box's own check", said.startswith("Nothing was changed on your calendar"), True)
        hook({"session_id": "s2", "hook_event_name": "PreToolUse", "tool_input": {"command": r"python System\live\desk.py join"}})
        seen, said = act_as("s2")
        check("another session's act never borrows s1's words", seen, [""])

        # the box's own checks on the reply's words, with the box's outcome
        def reply(prompt, text):
            hook({"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": prompt})
            with open(tr, "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "user", "message": {"role": "user", "content": prompt}}) + "\n")
                f.write(json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}) + "\n")

        def stop():
            out = hook({"session_id": "s1", "hook_event_name": "Stop", "transcript_path": tr}).strip()
            return (json.loads(out) if out else {}), turns()[-1]

        reply("write the trailer shop an email", "I've put the email in your drafts, ready to send.")
        back, t = stop()
        check("a draft claimed but never made: the box's words replace it", (back, t["text"]),
              ({}, "I did not put any email on your page this time. Ask me again and I will write it."))
        reply("tell the shop yes", "I sent the email to the shop.")
        back, t = stop()
        check("a send claimed but never done: the box's words replace it", (back, t["text"]),
              ({}, "Nothing was sent or changed on your calendar this time. Tell me plainly what to do and I will do it."))
        reply("look into the trailer", "Here is what I know. I will check the trailer registration.")
        b1, t1 = stop()
        b2, _ = stop()
        b3, t3 = stop()
        queued = json.load(open(os.path.join(home, "chat", "queue.json"), encoding="utf-8")).get("jobs") or []
        check("a promise no ACTION kept: sent back twice to do it now, then a job for the next check, as the box does",
              (b1.get("decision"), b2.get("decision"), b3, t1["text"], t3["text"], queued[-1]["do"]),
              ("block", "block", {}, "Here is what I know.",
               "Here is what I know. I'll finish this the next time I check for messages, within 15 minutes, and tell you here.",
               "I will check the trailer registration."))

        # the page's Sending... line waits for the box's own reply, not a Claude app turn landing in between
        js = open(os.path.join(PKG, "engine", "System", "live_page", "site", "app", "app.js"), encoding="utf-8").read()
        line = [x for x in js.splitlines() if "turns.slice(at + 1).some(" in x][0].strip()
        probe = ("var talk = {pending: null}; function run(turns) { var p = talk.pending = {at: 'A'}, at = 1; " + line +
                 " return p === null; }\nconsole.log(JSON.stringify([run([{who: 'you', at: 'X'}, {who: 'you', at: 'A'}, {who: 'you', desktop: 's1'},"
                 " {who: 'assistant', desktop: 's1'}]), run([{who: 'you', at: 'X'}, {who: 'you', at: 'A'}, {who: 'you', desktop: 's1'},"
                 " {who: 'assistant'}])]));")
        r = subprocess.run(["node", "-e", probe], capture_output=True, text=True, timeout=60)
        check("Sending... stays through a Claude app turn and ends at the box's reply", r.stdout.strip(), "[false,true]")

        # the Open in the Claude app link as the app delivers it: its "/" arrives fullwidth, so no command runs; the folder's
        # CLAUDE.md has the session run the join itself. Hook input in the app's own shape (Claude app 2.1.328, 2026-11-23).
        sid = "ed25ffcf-0000-4000-8000-000000000001"
        tr2 = os.path.join(tmp, sid + ".jsonl")
        base = {"session_id": sid, "transcript_path": tr2, "permission_mode": "auto"}
        check("the folder's CLAUDE.md has a link-opened session run the join and claim nothing before it",
              ("Join Talk to your assistant." in note, r"python System\live\desk.py join" in note, "never say it is joined" in note), (True, True, True))
        before = len(turns())
        hook(dict(base, hook_event_name="UserPromptSubmit", prompt="／assistant:talk"))
        hook(dict(base, hook_event_name="PreToolUse", tool_name="PowerShell", tool_use_id="toolu_1",
                  tool_input={"command": r"python System\live\desk.py join", "description": "Join Talk to your assistant"}))
        r = subprocess.run([sys.executable, os.path.join(live, "desk.py"), "join"], capture_output=True, text=True, env=env, cwd=root)
        check("the link-opened session is joined by its own join command", r.stdout.startswith("This session is now Talk to your assistant"), True)
        hook(dict(base, hook_event_name="Stop", stop_hook_active=False))
        check("the join itself adds nothing to the conversation", len(turns()), before)
        typed = "Just looking to see if this chat works"
        hook(dict(base, hook_event_name="UserPromptSubmit", prompt=typed))
        with open(tr2, "w", encoding="utf-8") as f:         # the transcript's own entry shapes
            for e in ({"type": "user", "isSidechain": False, "message": {"role": "user", "content": "／assistant:talk"},
                       "origin": {"kind": "human"}, "promptSource": "sdk", "turnOrigin": "human", "sessionId": sid},
                      {"type": "assistant", "isSidechain": False, "message": {"role": "assistant", "content": [
                          {"type": "tool_use", "id": "toolu_1", "name": "PowerShell", "input": {"command": r"python System\live\desk.py join"}}]}},
                      {"type": "user", "isSidechain": False, "message": {"role": "user", "content": [
                          {"type": "tool_result", "tool_use_id": "toolu_1", "content": "This session is now Talk to your assistant"}]}},
                      {"type": "system", "subtype": "stop_hook_summary", "hookCount": 5, "hookErrors": []},
                      {"type": "user", "isSidechain": False, "message": {"role": "user", "content": typed},
                       "origin": {"kind": "human"}, "promptSource": "sdk", "turnOrigin": "human", "sessionId": sid},
                      {"type": "assistant", "isSidechain": False, "message": {"role": "assistant", "content": [
                          {"type": "text", "text": "It works. Your message reached me here."}]}}):
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        hook(dict(base, hook_event_name="Stop", stop_hook_active=False))
        check("the typed message and the reply land in the conversation, marked desktop",
              [(t["who"], t["text"], t.get("desktop")) for t in turns()[before:]],
              [("you", typed, sid), ("assistant", "It works. Your message reached me here.", sid)])

        pages = [p for p in glob.glob(os.path.join(home, "page_state", "**", "*.json"), recursive=True)]
        blob = "".join(open(p, encoding="utf-8").read() for p in pages)
        check("the page's data carries the desktop turns and the open link",
              ('"desktop": "s1"' in blob or '"desktop":"s1"' in blob, "claude://code/new?folder=" in blob), (True, True))
        check("the open link asks in plain words, with no slash command", ("q=Join%20Talk%20to%20your%20assistant." in blob, "q=%2F" in blob), (True, False))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
