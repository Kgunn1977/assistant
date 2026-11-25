r"""Acceptance: the rule presses run through (I did not need this, this kind; Always show, this kind; Change on a rule
card), each ending with the rule card proposed or rewritten, with Claude a stand-in, each rule card carrying its reason (the
run's, else what was pressed; a rewrite with none keeps it) and Approve saving it; and a mod's code is never called
with the database open: a mod whose buttons take 3 seconds, while a write from another process goes through. On a
scratch copy laid down from this plugin; nothing outside the scratch folder changes.

    python tests\rules_and_mods_acceptance.py
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

MOD_JSON = {"name": "slowbuttons", "title": "Slow buttons", "on": True, "card_prefixes": ["live:slow-"]}
MOD_PY = r'''
import time
def choices(item):
    time.sleep(3)                   # someone else's code, taking its time
    return ["Left", "Right"]
'''

INSIDE = r'''
import datetime as dt, json, os, subprocess, sys, threading, time
live = sys.argv[1]
sys.path.insert(0, live)
import common, db, items, answers, teach
from connections import _store
out = {}

# --- the rule presses, with Claude standing in ---
w = _store.MailWriter("me@one.example")
for n in (1, 2):
    w.add(f"p{n}", dt.datetime(2026, 11, 18, 9, n), "in", f"news{n}@vendor.example", "me@one.example", f"Roof sale {n}", "Big roof sale.",
          thread_id=f"t{n}", attachments=[], state={"unread": True, "inbox": True, "trashed": False, "labels": [], "cc": "",
                                                    "from_name": "Vendor", "header_id": f"<p{n}@vendor.example>", "refs": ""})
w.commit()
c = db.connect()
mids = [r[0] for r in c.execute("SELECT id FROM messages ORDER BY provider_id").fetchall()]
c.close()
cards = []
for n, mid in enumerate(mids, 1):
    iid, _ = items.upsert(f"live:rulecase-{n}", "t", kind="message", area="Personal", state="handled", title=f"Roof sale {n}",
                          source_who="Vendor", source_when=common.now(), source_messages=[mid])
    cards.append(iid)
items.export("t")
replies = ['{"rule": "Hide sale emails from roofing vendors.", "reason": "Sale mail from vendors needs nothing from me.", "note": "From the roof sale card."}',
           '{"rule": "Always show emails about roof repairs from vendors.", "note": "From the second card."}',
           '{"rule": "Hide sale emails from roofing vendors, but never repair quotes.", "note": "Changed as asked."}']
asked = []
def stand_in(prompt, model):
    asked.append(prompt)
    return replies[len(asked) - 1], "", 0.1, {}
teach._claude = stand_in
def press(iid, name):
    return answers.act_on_answer({"id": iid, "action": "answer", "text": json.dumps({"press": {"name": name, "scope": "kind"}})})
def rule_cards():
    return {r["id"]: r for r in items.rows("source_key LIKE 'rule:%'")}
r1 = press(cards[0], "not_needed")
answers.wait_landed()
made1 = rule_cards()
r2 = press(cards[1], "always_show")
answers.wait_landed()
made2 = rule_cards()
new2 = [i for i in made2 if i not in made1]
out["I did not need this, this kind: a rule card is proposed"] = [r1.get("ok"), str(r1.get("result")).startswith("I proposed a rule"),
    [(r["status"], r["title"]) for r in made1.values()]]
out["Always show, this kind: a rule card is proposed"] = [r2.get("ok"), str(r2.get("result")).startswith("I proposed a rule"),
    [(made2[i]["status"], made2[i]["title"]) for i in new2]]
rid = next(iter(made1))
items.export("t")
r3 = answers.act_on_answer({"id": rid, "action": "answer", "text": "but never the repair quotes"})
answers.wait_landed()                   # the card's last line lands in the background, as on the page
out["Change on a rule card: the rule is rewritten"] = [r3.get("ok"), str(r3.get("result")).startswith("The rule now reads"),
    rule_cards()[rid]["title"], rule_cards()[rid]["status"], len(asked)]
out["R the rule cards carry their reason: the run's, else what was pressed"] = [
    (items.card_for(rid, wait=True).get("rule") or {}).get("reason"),
    [(items.card_for(i, wait=True).get("rule") or {}).get("reason") for i in new2]]
out["R a rewrite with no reason keeps it, shown on the card"] = (items.card_for(rid, wait=True).get("rule") or {}).get("reason")
ra = answers.act_on_answer({"id": rid, "action": "answer", "text": json.dumps({"press": {"name": "approve"}})})
answers.wait_landed()
import filters
out["R Approve saves the taught rule with its reason"] = [x.get("reason") for x in filters.rules() if "roofing" in x["text"]]
out["no press said Something went wrong"] = any("went wrong" in str(r.get("result") or r.get("error") or "") for r in (r1, r2, r3))

# --- a mod's buttons that take 3 s: the database is closed while the mod's code runs ---
items.upsert("live:slow-1", "t", kind="question", area="Slow", state="question", title="Pick a side", asks=["Which side?"],
             source_who="Slow", source_when=common.now())
WRITER = ("import sys, time; sys.path.insert(0, sys.argv[1]); import db; t = time.time(); c = db.connect(); "
          "c.execute('CREATE TABLE IF NOT EXISTS mod_probe(x INT)'); c.execute('INSERT INTO mod_probe VALUES (1)'); c.close()")
for name, run in (("the page's cards are written", lambda: items.export("t")),
                  ("one card is prepared for the page", lambda: items.card_for(items.rows("source_key='live:slow-1'")[0]["id"], wait=True))):
    got = {}
    th = threading.Thread(target=lambda: got.update(r=run()))
    t0 = time.time(); th.start(); time.sleep(0.5)
    wr = subprocess.run([sys.executable, "-c", WRITER, live], capture_output=True, text=True, timeout=120)
    w_done = time.time() - t0
    running = th.is_alive()
    th.join()
    out[f"while a mod's buttons take 3 s ({name}): another process writes"] = [wr.returncode, w_done < 3, running]
card = items.card_for(items.rows("source_key='live:slow-1'")[0]["id"], wait=True)
shown = next((i for i in common.read_json(common.ITEMS_JSON, {}).get("items") or [] if i.get("source_key") == "live:slow-1"), {})
out["the mod's buttons are still on its card"] = [card.get("choices"), shown.get("choices")]
print(json.dumps(out, default=str))
'''

WANT = {
    "I did not need this, this kind: a rule card is proposed": [True, True, [("Rule proposed", "New rule: Hide sale emails from roofing vendors.")]],
    "Always show, this kind: a rule card is proposed": [True, True, [("Rule proposed", "New rule: Always show emails about roof repairs from vendors.")]],
    "Change on a rule card: the rule is rewritten": [True, True, "New rule: Hide sale emails from roofing vendors, but never repair quotes.",
                                                     "Rule proposed", 3],
    "R the rule cards carry their reason: the run's, else what was pressed": [
        "Sale mail from vendors needs nothing from me.", ['You pressed "Always show this" on the card "Roof sale 2"']],
    "R a rewrite with no reason keeps it, shown on the card": "Sale mail from vendors needs nothing from me.",
    "R Approve saves the taught rule with its reason": ["Sale mail from vendors needs nothing from me."],
    "no press said Something went wrong": False,
    "while a mod's buttons take 3 s (the page's cards are written): another process writes": [0, True, True],
    "while a mod's buttons take 3 s (one card is prepared for the page): another process writes": [0, True, True],
    "the mod's buttons are still on its card": [["Left", "Right"], ["Left", "Right"]],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="rulesmods-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_rulesmods", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47913",
                            "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        md = os.path.join(home, "mods", "slowbuttons")
        os.makedirs(md)
        json.dump(MOD_JSON, open(os.path.join(md, "mod.json"), "w", encoding="utf-8"))
        open(os.path.join(md, "mod.py"), "w", encoding="utf-8").write(MOD_PY)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=900)
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = {}
            check("the checks ran", r.stderr.strip()[-1500:], "")
        for name, want in WANT.items():
            check(name, got.get(name), json.loads(json.dumps(want)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
