r"""Acceptance: a mod proves itself on the owner's page (System\live\mod_checks.py). On a scratch copy laid down from this plugin:
a change that makes a mod writes its checks and they become cards; Works on a check passes it; Doesn't work opens the box and
its words go to the change path (a Claude stand-in makes the fix, with an undo copy first, only the mod's files), then the
check has a new card; when every check has passed the mod is proven and its cards are off the page; Done drops a check and
the mod stays unproven. No Claude run is made.

    python tests\mod_checks_acceptance.py
"""
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

INSIDE = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
import common, chat, answers, change_job, mods, items, mod_checks, settings_data
import setup_steps
sys.path.insert(0, os.path.join(sys.argv[1], "setup"))
import setup_changes as sc
out = {}
now = common.now()
items.ensure()
CHECKS = {"checks": [{"try": "Take a receipt photo", "expect": "It is complete within 15 minutes."},
                     {"try": "Open a category card", "expect": "It names the category."},
                     {"try": "Press Later on a card", "expect": "It comes back tomorrow."}]}

def make(name):
    def standin(c, folder):
        os.makedirs(folder, exist_ok=True)
        json.dump({"name": name, "title": "Tally", "on": True}, open(os.path.join(folder, "mod.json"), "w"))
        open(os.path.join(folder, "mod.py"), "w").write("x = 1\n")
        if "checks.json" in " ".join(c["paths"]):
            json.dump(CHECKS, open(os.path.join(folder, "checks.json"), "w"))
        return True, ""
    return standin

def press_go(cid, n):
    answers.start_hidden = lambda args: True
    answers.act_on_answer({"id": f"change-go:{cid}:{n}", "action": "answer", "text": json.dumps({"press": {"name": "change_go", "change": cid}}),
                           "at": now.isoformat(timespec="seconds"), "device": "t"})

real = sc.default_runner(setup_steps, "")
change_job.RUNNER = lambda step: (True, "stand-in") if step in ("restart the listener", "look at the page") else real(step)
change_job.tell = lambda c, text: None

# 1. a change that makes a mod also writes its checks; they become cards of their own kind
book = sc.Book(os.path.dirname(common.HOME), common.HOME)      # a change asked in the chat is a card; its Approve records it so
book.start("A tally mod.")
book.agree("ch-0001", "mods", "A mod tally with its checks.", ["Live/mods/tally/" + f for f in ("mod.json", "mod.py", "checks.json")])
press_go("ch-0001", 1)
change_job.edit = make("tally")
change_job.run("ch-0001")
def cards():
    return {r["source_key"]: r for r in items.rows("starts_with(source_key, 'live:modcheck-')")}
cs = cards()
out["the checks became cards"] = sorted(cs)
c1 = cs["live:modcheck-tally-c1r1"]
fin = items.finish(dict(c1))
out["a check card"] = [c1["state"], fin["asks"], [x["label"] for x in fin["choices"]]]
out["the card writer leaves it alone"] = mods.owns(c1)

def press(key, text):
    return answers.act_on_answer({"id": cards()[key]["id"], "action": "answer", "text": text, "at": now.isoformat(timespec="seconds"), "device": "t"})

# 2. Works passes a check; not proven yet
press("live:modcheck-tally-c1r1", "Works")
out["Works passes one check"] = [list(mod_checks.status("tally")), cards()["live:modcheck-tally-c1r1"]["state"]]

# 3. Doesn't work: the choice alone asks What happened?; the words go to the change path
r = press("live:modcheck-tally-c2r1", "Doesn't work")
out["Doesn't work alone asks"] = [r["result"], cards()["live:modcheck-tally-c2r1"]["state"]]
ran = []
def hidden(args):
    change_job.edit = make("tally")
    ran.append(args[-1])
    change_job.run(args[-1])
    return True
answers.start_hidden = hidden
press("live:modcheck-tally-c2r1", "It said nothing about the category")
ch = json.load(open(os.path.join(common.HOME, "changes", "ch-0002.json"), encoding="utf-8"))
out["the words went through the change path"] = [ran, ch["state"], "It said nothing about the category" in ch["agreed"], sorted(ch["paths"]), bool(ch["before"])]
cs = cards()
out["the fix puts up a new card"] = [sorted(k for k in cs if "-c2r" in k), cs["live:modcheck-tally-c2r1"]["state"], cs["live:modcheck-tally-c2r2"]["state"]]

# 4. Done drops a check without passing it; the mod stays unproven
answers.act_on_answer({"id": cards()["live:modcheck-tally-c3r1"]["id"], "action": "done", "at": now.isoformat(timespec="seconds"), "device": "t"})
mod_checks.sync("tally")
press("live:modcheck-tally-c2r2", "Works")
out["Done drops it, mod unproven"] = [list(mod_checks.status("tally")), [c["state"] for c in mod_checks.load("tally")["checks"]]]
out["Settings shows it unproven"] = [d["value"] for d in settings_data.defs()["settings"] if d.get("group") == "mod:tally" and d.get("id") == "proven"]

# 5. a second mod where every check passes is proven and its cards are done
book.start("A second mod.")
book.agree("ch-0003", "mods", "A mod tally2 with checks.", ["Live/mods/tally2/" + f for f in ("mod.json", "mod.py", "checks.json")])
press_go("ch-0003", 3)
change_job.edit = make("tally2")
change_job.run("ch-0003")
for n in (1, 2, 3):
    press(f"live:modcheck-tally2-c{n}r1", "Works")
out["every check passed"] = [list(mod_checks.status("tally2")), [cards()[f"live:modcheck-tally2-c{n}r1"]["state"] for n in (1, 2, 3)]]
out["Settings shows it proven"] = [d["value"] for d in settings_data.defs()["settings"] if d.get("group") == "mod:tally2" and d.get("id") == "proven"]
print(json.dumps(out, default=str))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="mod-checks-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_mc", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    a = os.path.join(data, "scripts", "assistant.py")
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, a, "lay-down", "--port", "47905", "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=900, cwd=tmp)
        got = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
        if not got:
            print(r.stderr.strip()[-2000:])
        check("the checks became cards", got.get("the checks became cards"), [f"live:modcheck-tally-c{n}r1" for n in (1, 2, 3)])
        check("a check card: numbered question, Works and Doesn't work", got.get("a check card"),
              ["question", ["Did it work?"], ["Works", "Doesn't work (say which)"]])
        check("the card writer leaves it alone", got.get("the card writer leaves it alone"), True)
        check("Works passes one check", got.get("Works passes one check"), [[False, 1, 3], "done"])
        check("Doesn't work alone asks What happened?", got.get("Doesn't work alone asks"), ["What happened? Say it in the box on the card.", "question"])
        w = got.get("the words went through the change path") or [[], "", False, [], False]
        check("the words went through the change path (undo copy first, only the mod's files)", w,
              [["ch-0002"], "done", True, ["Live/mods/tally/mod.json", "Live/mods/tally/mod.py"], True])
        check("the fix puts up a new card for that check", got.get("the fix puts up a new card"),
              [["live:modcheck-tally-c2r1", "live:modcheck-tally-c2r2"], "done", "question"])
        check("Done drops a check: the mod is not proven", got.get("Done drops it, mod unproven"), [[False, 2, 3], ["passed", "passed", "dropped"]])
        check("Settings shows it unproven", got.get("Settings shows it unproven"), ["Not yet proven: 2 of 3 checks passed"])
        check("every check passed: proven, cards done", got.get("every check passed"), [[True, 3, 3], ["done", "done", "done"]])
        check("Settings shows it proven", got.get("Settings shows it proven"), ["Proven: every check passed"])
        subprocess.run([sys.executable, a, "uninstall", "--remove-data", "--root", root], capture_output=True, text=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got_, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got_!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
