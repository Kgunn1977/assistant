r"""Acceptance: every answer on a card with several questions is acted on (the owner's fault of 11/25: "a card had several
questions on it, however in my experience only one answer was acted on"). On a scratch copy laid down from this plugin with
made-up cards and mail. Claude's runs are stood in for: the stand-in acts on the answer it is given, and when a pressed
answer is read it says the card is handled (as a real run may), so the program, not the run, must keep the other questions
asked. The calendar is stood in for too; everything else is the real program.

The owner's model: a card of several questions is a card of small cards. Each question closes when it is answered (its
action done or started) and shows as answered with Change; it opens again on new information; the main card closes when
every question is answered (staying only for what waits on him, such as an email's Send); Done closes it any time.
Made-up cards ask three questions (add the lunch to the calendar, join the gift swap: a reply to the person who asked, add
a to-do to buy a gift) or two (the last two).

- In one go (typed on the card): the event is added once, a reply is in Drafts, the to-do is on the page, nothing is left
  asked, and the card stays only for the reply's Send.
- One at a time, as the page sends them: Add to calendar adds the event and leaves the other two asked, each with its own
  buttons, the answered one shown as answered; the gift-swap button drafts the reply and leaves the to-do asked although
  the run said handled; the last button adds the to-do and the main card closes with one line per answer.
- Two questions: a choice whose number was lost on the way (the hosted site dropped it) answers its own question only;
  Change gives that question a new answer and leaves the other asked; new information opens it again; Done part way
  closes the card.
- New information on a closed main card opens that one question and the card; the others stay answered.
- Nothing outbound is tried.

    python tests\multi_answer_acceptance.py
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

NIA = "nia@garden.example"
CAL_Q = "Add the Garden Club Lunch on Fri 12/11 at 11:30 to your calendar?"
SWAP_Q = "Do you want to join the gift swap?"
GIFT_Q = "Add a to-do to buy a gift under $30?"
IN, TODO = "Yes, I am in", "Yes, add the to-do"
con = db.connect()
items.ensure_on(con)
con.execute("INSERT INTO messages (channel, account, provider_id, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)"
            " VALUES ('email', 'me@work.example', 'p-0', 't0', now(), 'out', 'email:me@work.example', ?, 'Lunch', 'Thanks.', now())", (NIA,))
mid = con.execute("""INSERT INTO messages (channel, account, provider_id, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)
                     VALUES ('email', 'me@work.example', 'p-1', 't1', now(), 'in', ?, 'me@work.example', 'Garden Club Lunch',
                     'The lunch is Friday 12/11 at 11:30. Tell me by 11/30 if you want in on the gift swap. Nia', now()) RETURNING id""",
                  ("email:" + NIA,)).fetchone()[0]
cal = {"title": "Garden Club Lunch", "date": "2026-12-11", "start": "11:30", "end": None, "all_day": False, "certain": True, "location": None}
swap = [{"label": IN, "text": IN, "recommended": True}, {"label": "No thanks", "text": "No thanks"}]
gift = [{"label": TODO, "text": TODO, "recommended": True}, {"label": "No to-do", "text": "No to-do"}]
cards = {"L971": ([CAL_Q, SWAP_Q, GIFT_Q], cal, {"questions": [{"ask": SWAP_Q, "choices": swap}, {"ask": GIFT_Q, "choices": gift}]}),
         "L972": ([CAL_Q, SWAP_Q, GIFT_Q], cal, {"questions": [{"ask": SWAP_Q, "choices": swap}, {"ask": GIFT_Q, "choices": gift}]}),
         "L973": ([SWAP_Q, GIFT_Q], None, {"choices": swap, "questions": [{"ask": GIFT_Q, "choices": gift}]})}
for iid, (asks, c, extra) in cards.items():
    con.execute("""INSERT INTO live_items (id, source_key, kind, area, title, detail, state, importance, asks, source_messages, source_who,
                   calendar, extra, created_at, updated_at, state_changed_at)
                   VALUES (?, ?, 'question', 'Club', 'Garden Club Lunch Fri 12/11 at 11:30; gift swap sign-up by 11/30',
                   'Nia asks who wants in on the gift swap.', 'question', 0, ?, ?, 'Nia Park', ?, ?, now(), now(), now())""",
                (iid, "live:test-" + iid, json.dumps(asks), json.dumps([str(mid)]), json.dumps(c) if c else None, json.dumps(extra)))
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
    """Claude stood in: it acts on the answers it is given. A pressed answer is followed by 'handled', as a real run may say."""
    runs.append(words)
    acts, settled = [], []
    pressed = "pressed on the card" in words or "changing my answer" in words
    low = words.lower()
    if "changing my answer" in words:      # Change: the new answer is a no; nothing more to do for it
        return "Done.\nACTION: " + json.dumps({"type": "card", "state": "handled", "settled": [], "card": None}), "", 0.1, {}
    if not pressed and "calendar" in low:
        acts.append({"type": "calendar", "do": "add", "title": "Garden Club Lunch", "day": "2026-12-11", "start": "11:30"})
        settled.append(1)
    if IN.lower() in low:
        acts.append({"type": "draft", "to": [NIA], "subject": "Re: Garden Club Lunch",
                     "body": "Nia, count me in for the gift swap. Sam", "why": "His yes to her sign-up."})
        settled.append(2)
    if "to-do" in low:
        acts.append({"type": "task", "title": "Buy a gift for the Garden Club swap (under $30)"})
        settled.append(3)
    acts.append({"type": "card", "state": "handled", "settled": [] if pressed else settled, "card": None})
    return "Done.\n" + "\n".join("ACTION: " + json.dumps(a) for a in acts), "", 0.1, {}
chat._run = run

def ready_for(iid):
    return [r for r in items.rows("source_key LIKE 'live:ready-%' AND state <> 'done'")
            if ((r.get("extra") or {}).get("ready") or {}).get("about") == iid]

def tasks():
    return [r["title"] for r in items.rows("source_key LIKE 'chat:%'")]

def card(iid):
    return items.rows(f"id='{iid}'")[0]

def shown_card(iid):
    """The card as the page draws it."""
    return items.card_for(iid)

import datetime as dt
_tick = [0]
def now():
    """Each press its own second, as the page stamps them (two presses in one second on one card would be one answer)."""
    _tick[0] += 1
    return (common.now() + dt.timedelta(seconds=_tick[0])).isoformat(timespec="seconds")

def press(iid, text, n=None):
    """A choice button as the page sends it: its words and label, and its question's number when the card shows several."""
    rec = {"id": iid, "action": "answer", "text": text, "label": text, "page_action": "answer", "at": now(), "device": "test"}
    if n:
        rec["question"] = n
    answers.act_on_answer(rec)
    answers.wait_landed(30)

# 1. in one go: his words on the card answer all three
answers.act_on_answer({"id": "L971", "action": "answer", "at": now(), "device": "test",
                       "text": "Add it to the calendar. Yes, I am in for the swap. And add the to-do for the gift."})
answers.wait_landed(30)
c = card("L971")
out["1. in one go: the event is added once"] = len(adds)
out["1. in one go: a reply to the person who asked is in Drafts"] = [len(ready_for("L971")), [r["draft"]["to"] for r in ready_for("L971")]]
out["1. in one go: the to-do is on the page"] = len(tasks())
out["1. in one go: nothing is left asked; the card waits only on the reply's Send"] = [c["asks"], c["state"], c["status"]]

# 2. three questions, one at a time, as the page sends each press (the questions renumber as each one is answered)
a0, t0 = len(adds), len(tasks())
answers.act_on_answer({"id": "L972", "action": "answer", "page_action": "calendar", "label": "Add to calendar", "at": now(), "device": "test",
                       "text": "Add to calendar: Fri 12/11 11:30", "calendar": dict(cal, accepted_as_shown=True)})
answers.wait_landed(30)
c = card("L972")
out["2a. Add to calendar adds the event once; the other two stay asked"] = [len(adds) - a0, c["asks"], c["state"], c.get("calendar")]
shown = shown_card("L972")
out["2a. the answered question shows on the card, answered"] = [[a["ask"] for a in shown["answered"]], [q["ask"] for q in shown["questions"]],
                                                                 [x["text"] for x in shown["questions"][0]["choices"]]]
press("L972", IN, c["asks"].index(SWAP_Q) + 1)
c = card("L972")
out["2b. the swap button drafts the reply; the to-do stays asked though the run said handled"] = [len(ready_for("L972")), c["asks"], c["state"]]
press("L972", TODO)         # the only question left: the page sends no number
c = card("L972")
out["2c. the last button adds the to-do and the main card closes"] = [len(tasks()) - t0, c["asks"], c["state"]]
out["2c. the closed card says what was done for each answer"] = sorted(l.split('"')[1] for l in (c["assistant_did"] or "").split("\n")
                                                                       if l.startswith('Answered "'))

# 3. two questions: a choice whose number was lost on the way is found by its words; Change; new information; Done part way
press("L973", IN)
c = card("L973")
out["3a. a choice without its number answers its own question only"] = [c["asks"], c["state"], len(ready_for("L973"))]
answers.act_on_answer({"id": "L973", "action": "answer", "text": "No thanks after all", "redo": 1, "at": now(), "device": "test"})
answers.wait_landed(30)
c = card("L973")
out["3b. Change gives the answered question its new answer; the other stays asked"] = [
    [(a["ask"], a["answer"]) for a in answers.answered_of(c)], c["asks"], c["state"]]
import think
row = items.rows("id='L973'")[0]
again = think._reopened({"reopen": [SWAP_Q]}, row)
answers._land(answers._set("L973", did=None, asks=c["asks"] + again, state="question",
                           assistant_did=answers.reopen_line(row.get("assistant_did"), again, common.now())))
answers.wait_landed(30)
c = card("L973")
out["3c. new information opens that question again; it is no longer shown as answered"] = [
    again, c["asks"], [a["ask"] for a in answers.answered_of(c)], SWAP_Q in answers.settled_in_force(c["assistant_did"])]
answers.act_on_answer({"id": "L973", "action": "done", "at": now(), "device": "test"})
answers.wait_landed(30)
c = card("L973")
out["3d. Done part way closes the main card and every question on it"] = [c["asks"], c["state"]]

# 4. new information on a closed main card opens one of its questions, and with it the card
row = items.rows("id='L972'")[0]
again = think._reopened({"reopen": [GIFT_Q]}, row)
answers._land(answers._set("L972", asks=again, state="question",
                           assistant_did=answers.reopen_line(row.get("assistant_did"), again, common.now())))
answers.wait_landed(30)
shown = shown_card("L972")
out["4. the reopened question is open, the other two still answered, the card open"] = [
    [q["ask"] for q in shown["questions"]], sorted(a["ask"] for a in shown["answered"]), shown["state"]]
out["nothing outbound was tried"] = outbound
'''

CAL_Q = "Add the Garden Club Lunch on Fri 12/11 at 11:30 to your calendar?"
SWAP_Q = "Do you want to join the gift swap?"
GIFT_Q = "Add a to-do to buy a gift under $30?"
WANT = {
    "1. in one go: the event is added once": 1,
    "1. in one go: a reply to the person who asked is in Drafts": [1, [["nia@garden.example"]]],
    "1. in one go: the to-do is on the page": 1,
    "1. in one go: nothing is left asked; the card waits only on the reply's Send": [[], "handled", "Email in Drafts"],
    "2a. Add to calendar adds the event once; the other two stay asked": [1, [SWAP_Q, GIFT_Q], "question", None],
    "2a. the answered question shows on the card, answered": [[CAL_Q], [SWAP_Q, GIFT_Q], ["Yes, I am in", "No thanks"]],
    "2b. the swap button drafts the reply; the to-do stays asked though the run said handled": [1, [GIFT_Q], "question"],
    "2c. the last button adds the to-do and the main card closes": [1, [], "done"],
    "2c. the closed card says what was done for each answer": sorted([CAL_Q, SWAP_Q, GIFT_Q]),
    "3a. a choice without its number answers its own question only": [[GIFT_Q], "question", 1],
    "3b. Change gives the answered question its new answer; the other stays asked": [[[SWAP_Q, "No thanks after all"]], [GIFT_Q], "question"],
    "3c. new information opens that question again; it is no longer shown as answered": [[SWAP_Q], [GIFT_Q, SWAP_Q], [], False],
    "3d. Done part way closes the main card and every question on it": [[], "done"],
    "4. the reopened question is open, the other two still answered, the card open": [[GIFT_Q], sorted([CAL_Q, SWAP_Q]), "question"],
    "nothing outbound was tried": [],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="multians-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_multians", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47924",
                            "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=900)
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
