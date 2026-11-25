r"""Acceptance (quick): made-up test cards go on the page and come off again, and no press on them reaches anything real.
On a scratch copy laid down from this plugin. Nothing outside the scratch folder changes.

1. add puts seven TEST: cards on the page (the page's own card list, without a pass).
2. Presses on them (Junk, Never junk, Not needed, Always show, Approve on the rule and the draft, Send reminder, typed words,
   Done, Later) change only the test cards: the owner's lists, rules and other files, the other cards and every other table
   are exactly as before.
3. remove takes every test card off and leaves no answer record of theirs behind.

    python tests\test_cards_acceptance.py
"""
import hashlib
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

PRESS = r'''
import json, os, sys
live = sys.argv[1]
sys.path.insert(0, live); os.chdir(live)
import common, answers
snap = common.read_json(common.ITEMS_JSON, {}).get("items") or []
by = {str(i.get("source_key")): i for i in snap if str(i.get("source_key") or "").startswith("test:")}
said = {}
def press(key, action="answer", text=None, **kw):
    rec = dict({"id": by[key]["id"], "action": action, "text": text}, **kw)
    out = answers.act_on_answer(rec)
    said[f"{key} {action} {text}"] = [out.get("ok"), out.get("result"), out.get("thought")]
press("test:junk", text="Junk")
press("test:junk", text="Never junk")
press("test:came-back", text=json.dumps({"press": {"name": "not_needed", "scope": "sender"}}))
press("test:came-back", text=json.dumps({"press": {"name": "not_needed", "scope": "kind", "words": "no invoice mail"}}))
press("test:fyi", text=json.dumps({"press": {"name": "always_show"}}))
press("test:rule", text=json.dumps({"press": {"name": "approve"}}))
press("test:draft", text=json.dumps({"press": {"name": "approve"}}))
press("test:came-back", text="Send reminder")
press("test:two-questions", text="Use Supplier B and call them first, please.")
press("test:calendar", action="done")
press("test:fyi", text=json.dumps({"press": {"name": "later", "when": "tomorrow"}}))
answers.wait_landed(60)
print(json.dumps(said))
'''


LEFTOVER = r'''
import datetime as dt, json, os, sys
live = sys.argv[1]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core")); os.chdir(live)
import common, db, items
from connections import _store
w = _store.MailWriter("me@one.example")
st = {"unread": False, "inbox": True, "trashed": False, "labels": [], "cc": "", "from_name": "Test Sender", "header_id": "<t1@x>", "refs": ""}
w.add("t1", dt.datetime.now(), "in", "test.sender@example.com", "me@one.example", "TEST: a made-up message for trying Junk", "Junk test.",
      thread_id="t1", attachments=[], state=st)
w.add("t2", dt.datetime.now(), "in", "riley@supply.example", "me@one.example", "TEST: results from the lab", "Real mail.",
      thread_id="t2", attachments=[], state=dict(st, from_name="Riley", header_id="<t2@x>"))
w.commit()
c = db.connect(read_only=True)
fake = c.execute("SELECT id FROM messages WHERE subject = 'TEST: a made-up message for trying Junk'").fetchone()[0]
real = c.execute("SELECT id FROM messages WHERE subject = 'TEST: results from the lab'").fetchone()[0]
c.close()
a, _ = items.upsert(f"live:msg-{fake}", "t", kind="question", area="Work", state="done", title="TEST: a made-up card for trying the Junk button",
                    source_messages=[fake], source_who="Test Sender")
b, _ = items.upsert(f"live:msg-{real}", "t", kind="fyi", area="Work", state="handled", title="TEST: results from the lab came in",
                    source_messages=[real], source_who="Riley")
items.export("t")
print(json.dumps({"fake_card": a, "real_card": b, "fake_msg": fake, "real_msg": real}))
'''

STILL = r'''
import json, sys
sys.path.insert(0, sys.argv[1]); import db
m = json.loads(sys.argv[2])
c = db.connect(read_only=True)
one = lambda q, p: c.execute(q, p).fetchone() is not None
print(json.dumps({"fake card": one("SELECT 1 FROM live_items WHERE id = ?", [m["fake_card"]]),
                  "fake message": one("SELECT 1 FROM messages WHERE id = ?", [m["fake_msg"]]),
                  "fake contact": one("SELECT 1 FROM contacts WHERE key = 'email:test.sender@example.com'", []),
                  "real card": one("SELECT 1 FROM live_items WHERE id = ?", [m["real_card"]]),
                  "real message": one("SELECT 1 FROM messages WHERE id = ?", [m["real_msg"]])}))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def fingerprint(home, live):
    """Every file of the owner's (personal, rules, taught, outbox and the like; not the page's card list, logs, answers or
    state) and every table but the cards, plus the real cards, hashed."""
    files = {}
    for folder, dirs, names in os.walk(home):
        rel = os.path.relpath(folder, home)
        top = rel.split(os.sep)[0]
        if top in ("logs", "answers", "state", "page_state", "Resources", "To Delete", "builds"):
            dirs[:] = []
            continue
        for n in names:
            if n in ("items.json", "health.json", "held.json", "today.json") or n.endswith((".lock", ".tmp")):
                continue
            with open(os.path.join(folder, n), "rb") as f:
                files[os.path.join(rel, n)] = hashlib.sha1(f.read()).hexdigest()
    code = r'''
import json, sys, os, hashlib
sys.path.insert(0, sys.argv[1]); import db
c = db.connect(read_only=True)
out = {}
for (t,) in c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall():
    if t == "live_items":
        rows = c.execute("SELECT * FROM live_items WHERE NOT starts_with(coalesce(source_key, ''), 'test:') ORDER BY id").fetchall()
    else:
        rows = c.execute(f'SELECT * FROM "{t}"').fetchall()
        rows.sort(key=repr)
    out[t] = hashlib.sha1(repr(rows).encode()).hexdigest()
c.close()
print(json.dumps(out))
'''
    r = subprocess.run([sys.executable, "-c", code, live], capture_output=True, text=True, env=dict(os.environ, ASSISTANT_LIVE_HOME=home))
    return files, json.loads(r.stdout.strip().splitlines()[-1])


def main():
    tmp = tempfile.mkdtemp(prefix="testcards-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_tc", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        helper = os.path.join(data, "scripts", "assistant.py")
        r = subprocess.run([sys.executable, helper, "lay-down", "--port", "47927", "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass", r.returncode, 0)
        before = fingerprint(home, live)
        r = subprocess.run([sys.executable, helper, "test-cards", "add", "--root", root], capture_output=True, text=True, timeout=300)
        got = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stdout[-600:] + r.stderr[-600:]}
        snap = (json.load(open(os.path.join(home, "items.json"), encoding="utf-8")).get("items") or [])
        tests = [i for i in snap if str(i.get("source_key") or "").startswith("test:")]
        check("1 add: seven test cards on the page's card list, each titled TEST:",
              (got.get("added"), len(tests), all(str(i.get("title") or "").startswith("TEST:") for i in tests)), (7, 7, True))
        cb = next((i for i in tests if i.get("source_key") == "test:came-back"), {})
        check("1 a test card with a made-up example.com sender offers all three Not needed choices",
              ((cb.get("sender") or {}).get("address"), cb.get("teach")), ("dana@example.com", ["not_needed_this", "not_needed_sender", "not_needed_kind"]))
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", PRESS, live], capture_output=True, text=True, env=env, timeout=600)
        said = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stderr[-1500:]}
        check("2 every press went through, and none ran Claude", (len(said), all(v[0] and not v[2] for v in said.values())), (11, True))
        check("2 a press that would write a list, a rule or send says it did nothing",
              [k for k, v in said.items() if any(w in k for w in ("Junk", "not_needed", "always_show", "approve", "Send", "Supplier B"))
               and "Test card" not in str(v[1])], [])
        snap = (json.load(open(os.path.join(home, "items.json"), encoding="utf-8")).get("items") or [])
        cal = next((i for i in snap if i.get("source_key") == "test:calendar"), {})
        check("2 Done on a test card closes it, as on any card", cal.get("state"), "done")
        after = fingerprint(home, live)
        check("2 the owner's files are exactly as before", [k for k in set(before[0]) | set(after[0]) if before[0].get(k) != after[0].get(k)], [])
        check("2 every table and the real cards are exactly as before (lists, rules, outbox, contacts); only the record of landed answers grew",
              [t for t in set(before[1]) | set(after[1]) if before[1].get(t) != after[1].get(t)], ["live_answers"])
        r = subprocess.run([sys.executable, helper, "test-cards", "remove", "--root", root], capture_output=True, text=True, timeout=300)
        got = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stdout[-600:] + r.stderr[-600:]}
        snap = (json.load(open(os.path.join(home, "items.json"), encoding="utf-8")).get("items") or [])
        check("3 remove: no test card left on the page or in the database", (got.get("removed"),
              [i["id"] for i in snap if str(i.get("source_key") or "").startswith("test:")]), (7, []))
        ids = set(json.loads(json.dumps(got)).get("ids") or [])
        left = []
        for folder in (os.path.join(home, "answers"), os.path.join(home, "answers", "applied")):
            for n in os.listdir(folder) if os.path.isdir(folder) else []:
                p = os.path.join(folder, n)
                if os.path.isfile(p) and n.endswith(".json") and str((json.load(open(p, encoding="utf-8")) or {}).get("id") or "") in {i["id"] for i in tests}:
                    left.append(n)
        check("3 no answer record of a test card is left", left, [])
        final = fingerprint(home, live)
        check("3 after remove, the owner's files and tables are exactly as before add",
              ([k for k in set(before[0]) | set(final[0]) if before[0].get(k) != final[0].get(k)],
               [t for t in set(before[1]) | set(final[1]) if before[1].get(t) != final[1].get(t)]), ([], []))
        check("3 add and remove both update the page", ("page is updated" in json.dumps(got)), True)

        # 4. a test card made by hand before this tool (a made-up message from an example address) is taken off too;
        #    a real card that only happens to be titled TEST: stays
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", LEFTOVER, live], capture_output=True, text=True, env=env, timeout=300)
        made = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stderr[-800:]}
        r = subprocess.run([sys.executable, helper, "test-cards", "remove", "--root", root], capture_output=True, text=True, timeout=300)
        got = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stdout[-600:] + r.stderr[-600:]}
        r = subprocess.run([sys.executable, "-c", STILL, live, json.dumps(made)], capture_output=True, text=True, env=env, timeout=120)
        check("4 the hand-made test card and its made-up message are gone; the real one titled TEST: stays",
              (got.get("made_up_removed", {}).get("cards"), json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else r.stderr[-600:]),
              ([made.get("fake_card")], {"fake card": False, "fake message": False, "fake contact": False, "real card": True, "real message": True}))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
