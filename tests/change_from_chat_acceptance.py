r"""Acceptance: a change to how the assistant works, made entirely from the page's chat (change_job.py). On a scratch copy
laid down from this plugin: the chat records the change and its agreed words; the page's "Yes, make this change" is the
go; the hidden job writes only the change's own mod, checks it and reports in the chat, with an Undo; a change whose check
fails puts itself back; Undo from the page puts a made change back; the chat alone cannot edit anything.
The edit itself is a stand-in unless --with-claude is given (then one real Claude run makes it). The restart of the
page's own job, which a scratch copy does not have, is a stand-in; every other step is the real one.

    python tests\change_from_chat_acceptance.py [--with-claude]
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                                      # the plugin: this repository
results = []

INSIDE = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
real_claude = sys.argv[2] == "1"
import common, chat, answers, changes_feed, change_job, mods, items
import setup_steps
sys.path.insert(0, os.path.join(sys.argv[1], "setup"))
import setup_changes as sc
out = {}
now = common.now()

def say(action, n=0):
    chat._asked_now.clear()
    return chat._do(action, action.get("words") or "words", common.now(), n)      # his message is what he typed

def press(card_id, do):
    items.export("t")       # the page's copy, as a pass writes it: a press reads the card from there
    return answers.act_on_answer({"id": card_id, "action": "answer", "at": common.now().isoformat(timespec="seconds"), "device": "t",
                                  "text": json.dumps({"press": {"name": "rule_offer", "do": do}})})

def records():
    d = os.path.join(common.HOME, "changes")
    return sorted(f for f in os.listdir(d) if f.endswith(".json")) if os.path.isdir(d) else []

# 1. asked in the chat: its own card in Cards, the change said back in one sentence, the four buttons; nothing recorded yet
made, line = say({"type": "change_start", "words": "Put a small Tally card on my page each pass.",
                  "change": "A mod named tally: mod.json names it and claims cards starting live:tally-; mod.py has pass_step making one card titled Tally.",
                  "mod": "tally", "files": ["mod.json", "mod.py"]})
card1 = items.card_for(made[0]["id"]) if made else {}
offer = card1.get("rule_offer") or {}
out["the chat puts the change on its own card"] = [line.startswith("I put it on a card in Cards, under Needs you"), card1.get("state"),
                                                   offer.get("made"), offer.get("mod"), bool(offer.get("text"))]
out["nothing is recorded and no banner waits before Approve"] = [(changes_feed.doc() or {}).get("active"), records()]

# 2. Approve on the card is the go: recorded, agreed as the mod, its undo copy saved, and the hidden job started
started = []
answers.start_hidden = lambda args: started.append(args) or True
got = press(card1.get("id"), "approve")
c = json.load(open(os.path.join(common.HOME, "changes", "ch-0001.json"), encoding="utf-8"))
out["Approve is the go and starts the hidden job"] = [got.get("result", "")[:24], c["state"], bool(c.get("go")), started[0][-1] if started else None, c.get("paths")]
# 3. the hidden job: the edit (Claude, or a stand-in), then the real check steps; the restart of the page's job is a stand-in
def standin_edit(c, folder):
    os.makedirs(folder, exist_ok=True)
    json.dump({"name": "tally", "title": "Tally", "on": True, "card_prefixes": ["live:tally-"]}, open(os.path.join(folder, "mod.json"), "w"))
    open(os.path.join(folder, "mod.py"), "w").write("import common, items\ndef pass_step(pass_id):\n"
        "    items.upsert('live:tally-1', pass_id, kind='fyi', area='Tally', state='handled', title='Tally', detail='d', asks=[],"
        " source_who='Tally', source_when=common.now())\n    return 'tally'\n")
    return True, ""
if not real_claude:
    change_job.edit = standin_edit
real = sc.default_runner(setup_steps, "")
change_job.RUNNER = lambda step: (True, "stand-in") if step in ("restart the listener", "look at the page") else real(step)
change_job.tell = lambda c, text: chat._add({"who": "assistant", "text": text, "source": "", "at": common.now().isoformat(timespec="seconds"),
                                             "change": c["id"]})        # as the job tells it, with no page to publish to here
code = change_job.run("ch-0001")
c = json.load(open(os.path.join(common.HOME, "changes", "ch-0001.json"), encoding="utf-8"))
folder = os.path.join(common.HOME, "mods", "tally")
last = chat.load()["turns"][-1]
out["made: done, as a mod, checked"] = [code, c["state"], sorted(os.listdir(folder)) if os.path.isdir(folder) else [], [s["name"] for s in c["steps"] if s["ok"]][-4:]]
out["the mod works"] = [m["name"] for m, mod in mods.on()]
out["why"] = [last["text"], [s for s in c["steps"] if not s["ok"]], open(change_job.LOG, encoding="utf-8").read()[-1500:] if os.path.exists(change_job.LOG) else ""]
out["the result is in the chat, with its change for the Undo"] = [last["text"][:21], last.get("change")]

# 4. a change whose check fails puts itself back; a mod name outside the mods folder is never used
made2, _ = say({"type": "change_start", "words": "Another small card.", "change": "A mod with mod.json and mod.py.", "mod": "../System", "files": ["mod.json", "mod.py"]}, 1)
press(made2[0]["id"], "approve")
change_job.edit = lambda c, folder: (os.makedirs(folder, exist_ok=True), open(os.path.join(folder, "mod.json"), "w").write("{}"),
                                     open(os.path.join(folder, "mod.py"), "w").write("x = 1\n"), (True, ""))[-1]
change_job.RUNNER = lambda step: (False, "the check found a fault") if step == "run a check" else (True, "stand-in")
change_job.run("ch-0002")
c2 = json.load(open(os.path.join(common.HOME, "changes", "ch-0002.json"), encoding="utf-8"))
f2 = os.path.join(common.HOME, "mods", "change-0002")
out["a failing check puts it back by itself"] = [c2["state"], [x for x in (os.listdir(f2) if os.path.isdir(f2) else [])],
                                                 chat.load()["turns"][-1]["text"][:26]]
out["a mod name outside the mods folder is not used"] = sorted({p.split("/")[2] for p in c2.get("paths") or []})
# 5. Cancel on its card, before Approve: the card closes, nothing recorded or edited
made3, _ = say({"type": "change_start", "words": "A third change, then cancelled.", "change": "A third change."}, 2)
got = press(made3[0]["id"], "cancel")
items.export("t")
c3 = answers._as_it_stands(made3[0]["id"]) or {}
out["Cancel on its card closes it"] = [c3.get("state"), str(got.get("result")), records()]
print(json.dumps(out, default=str))
'''

UNDO = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
import common, answers
got = answers.act_on_answer({"id": "change-undo:ch-0001:3", "action": "answer", "text": json.dumps({"press": {"name": "undo_change", "change": "ch-0001"}}),
                             "at": common.now().isoformat(timespec="seconds"), "device": "t"})
c = json.load(open(os.path.join(common.HOME, "changes", "ch-0001.json"), encoding="utf-8"))
folder = os.path.join(common.HOME, "mods", "tally")
print(json.dumps([c["state"], sorted(os.listdir(folder)) if os.path.isdir(folder) else [], str(got.get("result") or got.get("error"))[:80]]))
'''

GUARD = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
import common
rb = common.rulebook()
ev = {"tool": "Write", "where": "hidden", "home": common.HOME, "root": sys.argv[2], "writes": [{"path": sys.argv[3], "text": "x"}]}
print(json.dumps(rb.route(ev)["ok"]))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    with_claude = "--with-claude" in sys.argv
    tmp = tempfile.mkdtemp(prefix="change-chat-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_chg", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    a = os.path.join(data, "scripts", "assistant.py")
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, a, "lay-down", "--port", "47904", "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live, "1" if with_claude else "0"], capture_output=True, text=True,
                           env=env, timeout=1800, cwd=tmp)
        got = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
        if not got:
            check("the checks ran", r.stderr.strip()[-800:], "")
        check("the chat puts the change on its own card, with the four buttons", got.get("the chat puts the change on its own card"),
              [True, "question", "change", "tally", True])
        check("nothing is recorded and no banner waits before Approve", got.get("nothing is recorded and no banner waits before Approve"), [None, []])
        check("Cancel on its card closes it, nothing recorded", got.get("Cancel on its card closes it"),
              ["done", "Cancelled. Nothing was changed.", ["ch-0001.json", "ch-0002.json"]])
        js = open(os.path.join(root, "System", "live_page", "site", "app", "app.js"), encoding="utf-8").read()
        check("the page has no Change how your assistant works link", "Change how your assistant works</button>" in js, False)
        check("a mod name outside the mods folder is not used", got.get("a mod name outside the mods folder is not used"), ["change-0002"])
        g = got.get("Approve is the go and starts the hidden job") or []
        check("Approve is the go and starts the hidden job", g, ["Making the change now. E", "go", True, "ch-0001",
              ["Live/mods/tally/mod.json", "Live/mods/tally/mod.py", "Live/mods/tally/checks.json"]])
        m = got.get("made: done, as a mod, checked") or []
        check("made: done, as a mod, checked", (m[:2], "mod.json" in (m[2] if len(m) > 2 else []), m[3] if len(m) > 3 else None),
              ([0, "done"], True, ["rebuild the page", "restart the listener", "run a check", "look at the page"]))
        check("the mod works", got.get("the mod works"), ["tally"])
        if got.get("made: done, as a mod, checked", [0, "done"])[1] != "done":
            print("WHY:", json.dumps(got.get("why"))[:1200])
        check("the result is in the chat, with its change for the Undo", got.get("the result is in the chat, with its change for the Undo"),
              ["The change is made: P", "ch-0001"])
        check("a failing check puts it back by itself", got.get("a failing check puts it back by itself"),
              ["failed", [], "The change was not made: r"])
        plan = json.loads(subprocess.run([sys.executable, a, "update-plan", "--root", root], capture_output=True, text=True).stdout or "{}")
        check("the program's own files are untouched by the change", (plan.get("keep"), plan.get("yours"), plan.get("conflict")), (0, [], []))
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", UNDO, live], capture_output=True, text=True, env=env, timeout=900, cwd=tmp)
        u = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else [r.stderr[-300:]]
        check("Undo from the page puts it back", u[:2], ["undone", []])
        # the chat alone cannot edit: its run has no editing tool, and a hidden write to a mod with no change under a go is refused
        src = open(os.path.join(live, "chat.py"), encoding="utf-8").read()
        check("the chat's run has no editing tool", ('TOOLS = "Read,Grep,Glob"' in src, "Edit" not in src.split('TOOLS = "')[1].split('"')[0]), (True, True))
        r = subprocess.run([sys.executable, "-c", GUARD, live, root, os.path.join(home, "mods", "tally", "mod.py")], capture_output=True, text=True, env=env)
        check("a hidden write to a mod with no change under a go is refused", r.stdout.strip(), "false")
        subprocess.run([sys.executable, a, "uninstall", "--remove-data", "--root", root], capture_output=True, text=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got_, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got_!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
