r"""Acceptance: frequent contacts come first (contact_strength.py), on a scratch copy laid down from this plugin with made-up people.

- The counts stay current across passes: what the owner sent and received is recounted from the messages at every pass.
- Received counts only personal messages: not mailing-list mail, not automatic addresses.
- Strength is two-way and recent: a frequent correspondent outweighs someone written to once, months ago.
- Two otherwise identical asks, from a frequent and a rare contact, land in that order on the page.
- A frequent contact's mailing-list mail gets no boost.
- The owner's own marks and rules still win: an important card (first by default, and under Importance, where equals go
  newest first) and the owner's ignore list.
- The card writer and the filter see it in plain words ("You write to Dana most weeks.").
Nothing outside the scratch folder changes.

    python tests\contacts_acceptance.py
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
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core"))
import common, db, items, order, contact_strength, think
from connections import _store
out = {}
now = dt.datetime.now().replace(microsecond=0)
ME = "me@one.example"
NAMES = {"dana@acme.example": "Dana Ross", "riley@supply.example": "Riley Park"}
n = [0]
def mail(direction, other, subject, body, days_ago, thread):
    n[0] += 1
    w = _store.MailWriter(ME)
    frm, to = (ME, other) if direction == "out" else (other, ME)
    w.add(f"p{n[0]}", now - dt.timedelta(days=days_ago, hours=1), direction, frm, to, subject, body, thread_id=thread, attachments=[],
          state={"unread": False, "inbox": True, "trashed": False, "labels": [], "cc": "", "from_name": NAMES.get(other, "") if direction == "in" else "",
                 "header_id": f"<p{n[0]}@x>", "refs": ""})
    w.commit()
    c = db.connect(); i = c.execute("SELECT max(id) FROM messages").fetchone()[0]; c.close()
    return i
# Dana: the owner writes to her most weeks and she writes back
for wk in range(9):
    mail("out", "dana@acme.example", f"Week {wk}", "Hi Dana, here is this week's order.", 7 * wk + 1, f"d{wk}")
    mail("in", "dana@acme.example", f"Re: Week {wk}", "Thanks, got it.", 7 * wk, f"d{wk}")
# Riley: one exchange, eighty days ago
mail("out", "riley@supply.example", "Quote", "Hi Riley, can you quote this?", 81, "r1")
mail("in", "riley@supply.example", "Re: Quote", "Here it is.", 80, "r1")
# a newsletter from an automatic address the owner never writes to, and Dana's own mailing list mail
mail("in", "news@deals.example", "Big sale", "Sale now. Unsubscribe here: https://deals.example/u", 2, "n1")
dana_list = mail("in", "dana@acme.example", "Acme monthly news", "Our news. To unsubscribe click https://acme.example/unsubscribe", 1, "n2")
# the contacts step, then the recount every pass makes
import refresh_contacts
sys.argv = ["refresh_contacts.py"]; refresh_contacts.main()
contact_strength.refresh()
c = db.connect(read_only=True)
row = lambda k: c.execute("SELECT sent_count, received_count, weeks_written, strength > 0 FROM contacts WHERE key = ?", [k]).fetchone()
out["counts"] = {"dana": list(row("email:dana@acme.example")), "riley": list(row("email:riley@supply.example"))}
out["levels"] = {"dana": contact_strength.for_person(c, "email:dana@acme.example"), "riley": contact_strength.for_person(c, "email:riley@supply.example")["level"]}
out["list mail from Dana"] = contact_strength.for_message(c, dana_list)
c.close()

# two otherwise identical asks: Dana's and Riley's, Riley's made a minute earlier (older, so first by age alone)
dana_ask = mail("in", "dana@acme.example", "Delivery date?", "Can you confirm the delivery date?", 0, "q1")
riley_ask = mail("in", "riley@supply.example", "Delivery date?", "Can you confirm the delivery date?", 0, "q2")
made = {}
for who, mid, mins in (("riley", riley_ask, 2), ("dana", dana_ask, 1)):
    iid, _ = items.upsert(f"live:ask-{who}", "t", kind="question", area="Work", state="question", title="Confirm the delivery date",
                          asks=["Which date?"], source_who=who, source_when=now - dt.timedelta(minutes=mins), source_messages=[mid])
    made[who] = iid
def ranked(sort="due_first", extra=None):
    cards = []
    for who, iid in made.items():
        it = items.card_for(iid, wait=True)
        it.update((extra or {}).get(who) or {})
        cards.append(it)
    today = dt.date.today()
    ordered = sorted(cards, key=lambda it: order.key_for(it, sort, today))      # the key order.annotate ranks by
    return [next(w for w, i in made.items() if i == it["id"]) for it in ordered]
out["order"] = ranked()
out["card says"] = (items.card_for(made["dana"], wait=True).get("contact") or {}).get("words")
# the owner's marks win: Riley's card marked important comes first
out["important wins"] = ranked(extra={"riley": {"importance": 1}})
# Importance (the bar at the top of Cards): the most important first, and between equals the newest first
out["importance first"] = ranked(sort="important_senders_first", extra={"riley": {"importance": 1}})
# (both asks came in the same minute, so Dana's is dated later here)
out["importance ties go newest"] = ranked(sort="important_senders_first", extra={"dana": {"from_at": now.isoformat()}})
# the counts stay current across passes: new messages, then a real pass
mail("out", "riley@supply.example", "Follow up", "Hi Riley, following up.", 0, "r2")
print(json.dumps(out, default=str))
'''

AFTER = r'''
import json, os, sys
live = sys.argv[1]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core"))
import common, db, contact_strength, think
c = db.connect(read_only=True)
out = {"riley sent after the pass": c.execute("SELECT sent_count FROM contacts WHERE key = 'email:riley@supply.example'").fetchone()[0]}
mid = c.execute("SELECT max(id) FROM messages WHERE direction = 'in' AND from_key = 'email:dana@acme.example' AND subject = 'Delivery date?'").fetchone()[0]
c.close()
out["the card writer sees"] = think._message(mid)["sender_contact"]
p = common.read_json(common.PERSONAL_JSON, {}) or {}
p["ignore_senders"] = ["dana@acme.example"]
common.write_json(common.PERSONAL_JSON, p)
import datetime as dt
from connections import _store
w = _store.MailWriter("me@one.example")
w.add("late1", dt.datetime.now(), "in", "dana@acme.example", "me@one.example", "Lunch?", "Lunch on Friday?", thread_id="z1", attachments=[],
      state={"unread": True, "inbox": True, "trashed": False, "labels": [], "cc": "", "from_name": "Dana Ross", "header_id": "<late1@x>", "refs": ""})
w.commit()
c = db.connect(read_only=True); fresh = c.execute("SELECT max(id) FROM messages").fetchone()[0]; c.close()
import judgment_payload
out["the owner's ignore list still holds a frequent contact"] = fresh in judgment_payload.owner_ignored()
print(json.dumps(out, default=str))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="contacts-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_contacts", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47923", "--sending", "no", "--root", root],
                           capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=900)
        try:
            o = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            o = {}
            check("the checks ran", r.stderr.strip()[-2000:], "")
        check("counts: Dana sent 9, received 9 personal (her list mail not counted), 9 weeks written, two-way",
              (o.get("counts") or {}).get("dana"), [9, 9, 9, True])
        check("counts: Riley sent 1, received 1, written to in one week of the last thirteen", (o.get("counts") or {}).get("riley"), [1, 1, 1, True])
        check("strength in plain words: Dana most weeks; Riley only back and forth once",
              [((o.get("levels") or {}).get("dana") or {}).get("words"), (o.get("levels") or {}).get("riley")], ["You write to Dana most weeks.", 1])
        check("a frequent contact's mailing-list mail gets no boost", o.get("list mail from Dana"), {"level": 0, "words": ""})
        check("two otherwise identical asks: the frequent contact's first, though the rare one's is older", o.get("order"), ["dana", "riley"])
        check("the card carries it in plain words", o.get("card says"), "You write to Dana most weeks.")
        check("the owner's marks win: an important card comes first", o.get("important wins"), ["riley", "dana"])
        check("Importance puts the important card first", o.get("importance first"), ["riley", "dana"])
        check("Importance breaks a tie by the newest", o.get("importance ties go newest"), ["dana", "riley"])
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", AFTER, live], capture_output=True, text=True, env=env, timeout=600)
        try:
            a = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            a = {}
            check("the checks after the pass ran", r.stderr.strip()[-2000:], "")
        check("the counts stay current across passes: the next pass counts the new message to Riley", a.get("riley sent after the pass"), 2)
        check("the card writer sees how often the owner is in touch with the sender", a.get("the card writer sees"), "You write to Dana most weeks.")
        check("the owner's ignore list still holds a frequent contact's message", a.get("the owner's ignore list still holds a frequent contact"), True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
