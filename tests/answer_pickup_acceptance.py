r"""Acceptance (quick): an answer that sat an hour with no sign it was read is picked up by the pass's safety net and read the
normal way (the card's words go to the chat), and logged; an answer already read is left alone. A card that comes back with
a new question drops the answer to its old one. On a scratch copy laid down from this plugin; the chat is a stand-in (no
Claude run).

    python tests\answer_pickup_acceptance.py
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
import datetime as dt, json, os, sys
live = sys.argv[1]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core")); os.chdir(live)
import common, items, answers, chat, limits, db
now = common.now()
old = now - dt.timedelta(hours=2)
unread, _ = items.upsert("live:test-unread", "t", kind="question", area="Work", state="yours", title="Robin chasing a credit",
                         asks=["Wait longer, write to them, or drop it?"])
read, _ = items.upsert("live:test-read", "t", kind="question", area="Work", state="yours", title="An RFQ for the listing",
                       asks=["Wait longer, write to them, or drop it?"])
items.update(unread, "t", answer="Write the split proposal to Pat.", answered_at=old)
items.update(read, "t", answer="Put it into an RFQ.", answered_at=old,
             last_press=json.dumps({"press": "words", "at": old.isoformat(timespec="seconds"), "happened": "Read.", "ok": True}))
items.export("t")
asked = []
def handle(text, at=None, card=None, **kw):
    asked.append([card["id"], text])
    return {"ok": True, "result": "Read now.", "secs": {}, "card_record": answers.card_record(card, {"state": "yours"}, text, "Read now.", [])}
chat.handle = handle
limits.begin("t")
n, problems = answers.think_pending("t")
answers.wait_landed(30)
c = db.connect(read_only=True)
left = {i: c.execute("SELECT answer FROM live_items WHERE id = ?", [i]).fetchone()[0] for i in (unread, read)}
c.close()
log = open(os.path.join(common.LOGS, "answers.log"), encoding="utf-8").read() if os.path.isfile(os.path.join(common.LOGS, "answers.log")) else ""
# a card that comes back drops the answer to its old question
import comeback
back, _ = items.upsert("live:test-back", "t", kind="question", area="Work", state="in_motion", title="Waiting on Acme",
                       asks=[], checkback_date=(now - dt.timedelta(days=3)).date())
items.update(back, "t", answer="Old words.", answered_at=old, state_changed_at=now - dt.timedelta(days=6),
             extra=json.dumps({"waiting_on": "Acme"}))
comeback.waiting("t")
c = db.connect(read_only=True)
bk = c.execute("SELECT state, status, answer FROM live_items WHERE id = ?", [back]).fetchone()
c.close()
print(json.dumps({"read now": n, "asked": asked, "left": [left[unread], left[read]], "logged": f"{unread} an answer of" in log,
                  "problems": problems, "came back": list(bk)}, default=str))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="pickup-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("ac_pickup", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47934", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=600)
        o = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stderr[-1500:]}
        check("the unread answer is read the normal way, once; the one already read is left alone",
              (o.get("read now"), [a[1] for a in o.get("asked") or []]), (1, ["Write the split proposal to Pat."]))
        check("once read, no answer is left waiting on the card", (o.get("left") or [None])[0], None)
        check("the pick-up is logged", o.get("logged"), True)
        check("a card that comes back asks afresh, and drops the answer to its old question", o.get("came back"), ["yours", "Back: still no reply", None])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
