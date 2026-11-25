r"""Acceptance (quick): the judge says "my rules don't cover this" instead of guessing silently. On a scratch copy laid down
from this plugin, with made-up messages and canned verdict files; no Claude run.

- A verdict with covered=false and leaned_on is accepted, and both are stored on the message's row in `answered`.
- An old-style verdict without the two fields is still accepted, and counts as covered (NULL).
- A home whose `answered` table predates the two columns gets them at the commit; its older rows read NULL.
- A covered value that is not true or false refuses the whole commit, and nothing is written.
- The card resting on an uncovered message says "My rules don't cover this; my best guess: ..." where it says why it is
  here; a card on a covered message does not.
- An uncovered row rewritten by "I should have seen this" or by the card writer's skip keeps no stale covered=false.

    python tests\uncovered_verdict_acceptance.py
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
import datetime as dt, json, os, subprocess, sys
live, work = sys.argv[1], sys.argv[2]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core")); os.chdir(live)
import common, db, items
import judgment_commit as jc
out = {}
now = dt.datetime(2026, 11, 20, 9, 30)
con = db.connect()
def msg(frm, subject, body):
    return con.execute("INSERT INTO messages (channel, account, thread_id, ts, direction, from_key, to_keys, subject, body,"
                       " ingested_at) VALUES ('email', 'work@example.com', ?, ?, 'in', ?, '[]', ?, ?, ?) RETURNING id",
                       ("t:" + subject, now, frm, subject, body, now)).fetchone()[0]
a = msg("email:news@letters.example", "Weekly letter", "Made-up newsletter text.")
b = msg("email:sam@supplier.example", "Delivery window", "Can you confirm Tuesday for the made-up delivery?")
c = msg("email:promo@shop.example", "Big sale", "Made-up sale text.")
d = msg("email:lee@friends.example", "Lunch", "Made-up lunch question.")
# an old home: the answered table as it was before the two columns, with a row already in it
con.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES ('judged', 'msg:999999', 'noise', 'old', ?)", (now,))
con.execute("ALTER TABLE answered DROP COLUMN covered")
con.execute("ALTER TABLE answered DROP COLUMN leaned_on")
con.close()
area = sorted(jc.areas())[0]

def commit(name, verdicts, ids):
    payload = os.path.join(work, f"payload_{name}.json")
    with open(payload, "w", encoding="utf-8") as f:
        json.dump({"days": ["2026-11-20"], "messages": [{"id": i, "conv": f"c{i}"} for i in ids]}, f)
    vfile = os.path.join(work, f"verdicts_{name}.json")
    with open(vfile, "w", encoding="utf-8") as f:
        json.dump({"payload": payload, "verdicts": verdicts}, f)
    r = subprocess.run([sys.executable, os.path.join(live, "core", "judgment_commit.py"), vfile, "--run-id", "t-" + name],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr

def row(mid):
    got = db.query("SELECT verdict, covered, leaned_on FROM answered WHERE domain='judged' AND key=?", (f"msg:{mid}",))
    return list(got[0]) if got else None

rc, said = commit("old", [{"id": a, "disposition": "noise", "reason": "a newsletter"}], [a])
out["old"] = [rc, row(a), row(999999)]
rc, said = commit("uncovered", [
    {"id": b, "disposition": "task", "reason": "a supplier asking to confirm a delivery day", "covered": False,
     "leaned_on": "no rule; the sender reads like a supplier",
     "task": {"item_key": "personal::delivery-window", "area": area, "title": "Confirm the delivery day",
              "detail": f"Sam asks to confirm Tuesday ({b}).", "status": "needs_me", "urgency": "normal"}},
    {"id": c, "disposition": "noise", "reason": "a sale mailing", "covered": True, "leaned_on": 12}], [b, c])
out["uncovered"] = [rc, row(b), row(c), "not covered by a rule (best guess): 1" in said]
rc, said = commit("bad", [{"id": d, "disposition": "ignore", "reason": "a friend", "covered": "false"}], [d])
out["bad"] = [rc, "COMMIT REFUSED" in said, "covered is 'false'" in said, row(d)]

db.init_schema()          # the schema applied again over a home that has the columns: no harm
out["schema again"] = row(b)

con = db.connect()
for iid, mid in (("L9001", b), ("L9002", c)):
    con.execute("""INSERT INTO live_items (id, source_key, kind, area, title, state, importance, asks, source_messages, source_who,
                   source_when, created_at, updated_at, state_changed_at)
                   VALUES (?, ?, 'task', ?, 'Made-up card', 'yours', 0, '[]', ?, 'Sam Example', ?, now(), now(), now())""",
                (iid, f"live:msg-{mid}", area, json.dumps([str(mid)]), now))
con.close()
def why(iid):
    it = items.rows(f"id='{iid}'")[0]
    con = db.connect(read_only=True)
    try:
        items.read(con, it)
    finally:
        con.close()
    return items.finish(it)["why"]
out["card uncovered"] = why("L9001")
out["card covered"] = why("L9002")

# a row the judge marked uncovered, rewritten by "I should have seen this" (held.py) and by the card writer's skip (think.py)
con = db.connect()
e = msg("email:pat@club.example", "Club night", "Made-up club note.")
f = msg("email:kim@school.example", "Form", "Made-up form note.")
con.close()
rc, said = commit("rewrites", [{"id": i, "disposition": "noise", "reason": "looks like a mailing", "covered": False,
                                "leaned_on": "no rule"} for i in (e, f)], [e, f])
before = [row(e), row(f)]
import held, think
con = db.connect()
try:
    held._make(con, e, "t-held")
finally:
    con.close()
problems = think._commit_items({"items": [], "new_items": [], "loose": [{"message": f, "skip": "nothing needed"}]},
                               {"items": [], "loose_messages": [{"id": f}]}, {})
out["rewrites"] = [rc, before, row(e), problems, row(f)]
print(json.dumps(out, default=str))
'''

WANT = {
    "old": [0, ["noise", None, None], ["noise", None, None]],
    "uncovered": [0, ["task", False, "no rule; the sender reads like a supplier"], ["noise", True, "12"], True],
    "bad": [1, True, True, None],
    "schema again": ["task", False, "no rule; the sender reads like a supplier"],
    "card uncovered": "You haven't told me how to handle this kind yet. My guess: a supplier asking to confirm a delivery day. "
                      "Sam Example wrote to you on 11/20.",
    "card covered": "Sam Example wrote to you on 11/20.",
    "rewrites": [0, [["noise", False, "no rule"], ["noise", False, "no rule"]], ["task", None, None], [], ["ignore", None, None]],
}
NAMES = {
    "old": "an old-style verdict without covered or leaned_on is accepted; an old home gets the columns, its rows read NULL",
    "uncovered": "a verdict with covered=false and leaned_on is accepted and stored; covered=true with a rule id too",
    "bad": "covered set to the text 'false' refuses the whole commit, naming it; nothing is written",
    "schema again": "the schema applied again keeps what was stored",
    "card uncovered": "the card from an uncovered verdict says 'My rules don't cover this; my best guess: ...' in its why",
    "card covered": "a card from a covered verdict keeps its plain why",
    "rewrites": "an uncovered row rewritten by 'I should have seen this' (held.py) or the card writer's skip (think.py) keeps"
                " no stale covered=false",
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="uncovered-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    work = os.path.join(tmp, "work")
    os.makedirs(work)
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("ac_uncovered", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47961", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live, work], capture_output=True, text=True, env=env, timeout=300)
        o = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
        if not o:
            check("the checks ran", r.stderr.strip()[-1500:], "")
        for key, want in WANT.items():
            check(NAMES[key], o.get(key), want)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
