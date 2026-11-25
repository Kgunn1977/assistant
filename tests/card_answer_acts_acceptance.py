r"""Acceptance: the owner's answer to a card's question is acted on, not only recorded (11/24, the staff party card). On a
scratch copy laid down from this plugin with made-up mail. Claude's runs are stood in for: the stand-in does what the run is
told, so it adds the event and drafts the reply only when its instructions say to and give it the card's day and who asked.
The calendar is stood in for too; everything else is the real program.

- Typed "yes, and add it to the calendar" on a sign-up card: the event is added once, on the card's day and time, a reply to
  the person who asked is in Drafts (never sent), and the card no longer asks either question.
- A choice button pressed on one question of such a card ("Yes, I am in") is read the same way: a reply is drafted to the
  person who asked; the calendar is not touched, since his press did not ask for it.
- Nothing outbound is tried.

    python tests\card_answer_acts_acceptance.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

import _cleanup  # noqa: E402  the scratch folder goes when the test ends

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []

INSIDE = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
import common, db, items, answers, chat, calendar_view, replay_guard
out = {}
import atexit
atexit.register(lambda: print(json.dumps(out, default=str)))
outbound = []
replay_guard.refuse = lambda what: outbound.append(what)
p = common.read_json(common.PERSONAL_JSON, {}) or {}
p["send_accounts"] = ["me@work.example"]
common.write_json(common.PERSONAL_JSON, p)
import send
send.accounts = lambda: ["me@work.example"]
send.switched_on = lambda: True

LENA = "lena@club.example"
CAL_Q, SWAP_Q = "Add the Book Club Winter Lunch on Fri 12/11 at 11:30 to your calendar?", "Do you want to join the cookie swap?"
con = db.connect()
items.ensure_on(con)
con.execute("INSERT INTO messages (channel, account, provider_id, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)"
            " VALUES ('email', 'me@work.example', 'p-0', 't0', now(), 'out', 'email:me@work.example', ?, 'Lunch', 'Thanks.', now())", (LENA,))
mid = con.execute("""INSERT INTO messages (channel, account, provider_id, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)
                     VALUES ('email', 'me@work.example', 'p-1', 't1', now(), 'in', ?, 'me@work.example', 'Book Club Winter Lunch',
                     'The lunch is Friday 12/11 at 11:30. Tell me by 11/30 if you want in on the cookie swap. Lena', now()) RETURNING id""",
                  ("email:" + LENA,)).fetchone()[0]
cal = {"title": "Book Club Winter Lunch", "date": "2026-12-11", "start": "11:30", "end": None, "all_day": False, "certain": True, "location": None}
for iid in ("L961", "L962"):
    con.execute("""INSERT INTO live_items (id, source_key, kind, area, title, detail, state, importance, asks, source_messages, source_who,
                   calendar, created_at, updated_at, state_changed_at)
                   VALUES (?, ?, 'question', 'Work', 'Book Club Winter Lunch Fri 12/11 at 11:30; cookie swap sign-up by 11/30',
                   'Lena asks who wants in on the cookie swap.', 'question', 0, ?, ?, 'Lena Marsh', ?, now(), now(), now())""",
                (iid, "live:test-" + iid, json.dumps([CAL_Q, SWAP_Q]), json.dumps([str(mid)]), json.dumps(cal)))
con.close()
items.export("t1")

adds = []
def add(body):
    adds.append(body)
    return {"ok": True, "event": {"id": f"ev{len(adds)}", "title": body.get("title"), "calendar": "Main", "all_day": False,
                                  "start": f"{body.get('day')}T{body.get('start')}", "end": f"{body.get('day')}T{body.get('end') or body.get('start')}"}}
calendar_view.add = add

runs = []
def run(words, told, sess):
    """Claude stood in: it acts on the answer only as far as its instructions say, from the facts it was given."""
    runs.append(words)
    acts = []
    told_to_act = "acted on in this same reply" in told and '"asked_by"' in told and LENA in told
    if told_to_act and "calendar" in words.lower() and '"2026-12-11"' in told:
        acts.append({"type": "calendar", "do": "add", "title": "Book Club Winter Lunch", "day": "2026-12-11", "start": "11:30"})
    if told_to_act:
        acts.append({"type": "draft", "to": [LENA], "subject": "Re: Book Club Winter Lunch",
                     "body": "Lena, count me in for the cookie swap. Robin", "why": "His yes to her sign-up."})
    if "pressed on the card" in words:
        acts.append({"type": "card", "settled": [], "card": {"asks": [CAL_Q]}})
    else:
        acts.append({"type": "card", "state": "handled", "settled": [1, 2] if told_to_act else [2], "card": None})
    return "Done.\n" + "\n".join("ACTION: " + json.dumps(a) for a in acts), "", 0.1, {}
chat._run = run

def ready_for(iid):
    return [r for r in items.rows("source_key LIKE 'live:ready-%' AND state <> 'done'")
            if ((r.get("extra") or {}).get("ready") or {}).get("about") == iid]

snap = next(i for i in common.read_json(common.ITEMS_JSON, {})["items"] if i["id"] == "L961")
out["the card can be answered by email to the person who asked"] = [(snap.get("reply") or {}).get("can_email"), (snap.get("reply") or {}).get("to")]

# 1. typed on the card: yes, and add it to the calendar
answers.act_on_answer({"id": "L961", "action": "answer", "text": "Yes, I want to do the cookie swap, and add it to the calendar",
                       "at": common.now().isoformat(timespec="seconds"), "device": "test"})
answers.wait_landed(30)
c = items.rows("id='L961'")[0]
made = ready_for("L961")
out["1. the event is added once, on the card's day and time"] = [len(adds), adds and [adds[0].get("day"), adds[0].get("start")]]
out["1. a reply to the person who asked is in Drafts, not sent"] = [len(made), made and made[0]["draft"]["to"], outbound]
out["1. the card no longer asks either question"] = [c["asks"], c["state"], (c.get("calendar") or {}).get("added")]

# 2. a choice button pressed on one question of the same kind of card
n0, a0 = len(runs), len(adds)
answers.act_on_answer({"id": "L962", "action": "answer", "text": "Yes, I am in", "label": "Yes, I am in", "question": 2,
                       "page_action": "answer", "at": common.now().isoformat(timespec="seconds"), "device": "test"})
answers.wait_landed(30)
c = items.rows("id='L962'")[0]
made = ready_for("L962")
out["2. a pressed choice is read and a reply drafted to the person who asked"] = [len(runs) - n0, len(made), made and made[0]["draft"]["to"]]
out["2. the calendar is untouched and only the question still open is asked"] = [len(adds) - a0, c["asks"]]
out["nothing outbound was tried"] = outbound
'''

WANT = {
    "the card can be answered by email to the person who asked": [True, ["lena@club.example"]],
    "1. the event is added once, on the card's day and time": [1, ["2026-12-11", "11:30"]],
    "1. a reply to the person who asked is in Drafts, not sent": [1, ["lena@club.example"], []],
    "1. the card no longer asks either question": [[], "handled", "ev1"],
    "2. a pressed choice is read and a reply drafted to the person who asked": [1, 1, ["lena@club.example"]],
    "2. the calendar is untouched and only the question still open is asked": [0, ["Add the Book Club Winter Lunch on Fri 12/11 at 11:30 to your calendar?"]],
    "nothing outbound was tried": [],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="cardacts-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_cardacts", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47923",
                            "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=600)
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = {}
        if r.returncode or not got:
            check("the checks ran", r.stderr.strip()[-2500:], "")
        for name, want in WANT.items():
            check(name, got.get(name), want)
    finally:
        _cleanup.remove(tmp)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
