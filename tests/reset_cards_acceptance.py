r"""Acceptance (quick): resetting cards at the owner's request (rebuild.py reset). A card that came back after waiting, with an
old answer, a last press and a Later, is put back to the owner: those are cleared, its history is kept with one line added
(the reset, with his direction for that card), and the card writer is asked to write it afresh (a stand-in here, no Claude
run); Put them back returns it exactly. Other cards are untouched. On a scratch copy, made-up names.

    python tests\reset_cards_acceptance.py
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
import common, items, db, rebuild, think
now = common.now()
a, _ = items.upsert("live:test-credit", "t", kind="question", area="Work", state="yours", title="Robin chasing Acme for a credit",
                    asks=["No reply from Pat in 2 working days. Wait longer, write to them, or drop it?"])
items.update(a, "t", status="Back: no reply", answer="make that a rule", answered_at=now - dt.timedelta(days=2),
             last_press=json.dumps({"press": "words", "at": (now - dt.timedelta(days=2)).isoformat(timespec="seconds"), "ok": True}),
             assistant_did="You answered 11/18: \"write a draft\"\nI will write the split proposal to Pat.",
             extra=json.dumps({"waiting_on": "Pat", "came_back": {"why": "date", "who": "Pat", "waited_days": 2}}),
             checkback_date=(now + dt.timedelta(days=3)).date())
b, _ = items.upsert("live:test-other", "t", kind="question", area="Work", state="question", title="Another card", asks=["Keep it?"])
items.export("t")
c = db.connect(read_only=True); other_before = c.execute("SELECT * FROM live_items WHERE id = ?", [b]).fetchone(); c.close()
written = []
think.write_items = lambda new, old, owed: written.append(sorted(owed))
n, said = rebuild.reset([a], {a: "The split proposal to Pat is yours to approve or send."})
c = db.connect(read_only=True)
row = dict(zip(items.COLUMNS, c.execute(f"SELECT {', '.join(items.COLUMNS)} FROM live_items WHERE id = ?", [a]).fetchone()))
other_after = c.execute("SELECT * FROM live_items WHERE id = ?", [b]).fetchone()
c.close()
ex = json.loads(row["extra"] or "{}")
out = {"said": said, "written": written, "state": row["state"], "status": row["status"], "answer": row["answer"], "last_press": row["last_press"],
       "checkback": row["checkback_date"], "waiting": "waiting_on" in ex or "came_back" in ex,
       "history": (row["assistant_did"] or "").split("\n"), "other untouched": other_before == other_after}
rebuild.put_back()
c = db.connect(read_only=True)
out["put back"] = c.execute("SELECT status, answer FROM live_items WHERE id = ?", [a]).fetchone()
c.close()
print(json.dumps(out, default=str))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="reset-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("ac_reset", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47936", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=600)
        o = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stderr[-1500:]}
        check("the card is the owner's again: waiting, came back, old answer, last press and date cleared",
              (o.get("state"), o.get("status"), o.get("answer"), o.get("last_press"), o.get("checkback"), o.get("waiting")),
              ("yours", None, None, None, None, False))
        h = o.get("history") or []
        check("its history is kept, with the reset line and his direction added",
              (h[:2], h[-1] if h else None),
              (["You answered 11/18: \"write a draft\"", "I will write the split proposal to Pat."],
               f"Reset {__import__('datetime').date.today().month}/{__import__('datetime').date.today().day} at your request: the earlier plans and "
               "promises on this card are dropped; it is yours to decide or do. The split proposal to Pat is yours to approve or send."))
        check("the card writer is asked to write it afresh; nothing else is", len(o.get("written") or []), 1)
        check("other cards are untouched", o.get("other untouched"), True)
        check("Put them back returns it as it was", o.get("put back"), ["Back: no reply", "make that a rule"])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
