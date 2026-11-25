r"""Acceptance of how cards are made and answered, on a scratch copy laid down from this plugin with made-up messages.
Each part names the fault it guards against. Nothing outside the scratch folder changes; no Claude run is made.

    python tests\cards_acceptance.py
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

# Runs inside the scratch home (ASSISTANT_LIVE_HOME set); prints one JSON line of named results.
INSIDE = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
import common, db, items, send
out = {}
p = common.read_json(common.PERSONAL_JSON, {}) or {}
p["send_accounts"] = ["work@example.com", "church@example.org"]
common.write_json(common.PERSONAL_JSON, p)
con = db.connect()
items.ensure_on(con) if hasattr(items, "ensure_on") else None
def msg(channel, account, frm, subject, body):
    return con.execute("""INSERT INTO messages (channel, account, provider_id, thread_id, ts, direction, from_key, to_keys,
                          subject, body, ingested_at) VALUES (?, ?, ?, 't1', now(), 'in', ?, ?, ?, ?, now()) RETURNING id""",
                       (channel, account, "p-" + subject, frm, account, subject, body)).fetchone()[0]
church = msg("email", "church@example.org", "Pat Doe <pat@friends.example>", "Sunday rota", "Can you take Sunday?")
chat = msg("chat", "church-chat", "chat:nate", "#maintenance", "The boiler is out again")
text = msg("sms", "phone", "sms:+15550001", "", "Running late")
elsewhere = msg("email", "old@example.net", "Lee Roe <lee@friends.example>", "Hello", "Hi there")
r = {k: items.reply_for(con, [v]) for k, v in (("church", church), ("chat", chat), ("text", text), ("elsewhere", elsewhere))}
con.close()
out["11 email reply goes from the account it came to"] = [r["church"].get("can_email"), r["church"].get("account")]
out["11 a chat card (a kind an addition brings): no email reply, says why"] = [r["chat"].get("can_email"), "chat" in (r["chat"].get("why") or "")]
out["11 text card: no email reply, says why"] = [r["text"].get("can_email"), "text" in (r["text"].get("why") or "")]
out["11 came to an account that cannot send: refused"] = [r["elsewhere"].get("can_email"), r["elsewhere"].get("account")]
# a reply may go from any of the owner's sending accounts he picks (the From choice); it defaults to the one it came to
send.switched_on = lambda: True
send.accounts = lambda: ["work@example.com", "church@example.org"]
def press(account):
    m = {"account": account, "to": ["pat@friends.example"], "cc": [], "subject": "Re: Sunday rota", "body": "Yes.", "attach": []}
    m["shown"] = {"account": account, "to": m["to"], "cc": [], "attach": []}
    return {"action": "answer", "id": "L1", "device": "test", "at": common.now().isoformat(timespec="seconds"),
            "text": json.dumps({"send_email": m})}
card = {"id": "L1", "reply": r["church"]}
def tried(account):
    try:
        send.prepare(press(account), card)
        return "ready"
    except send.Refused as e:
        return "refused: " + str(e)[:60]
out["11 server: reply from the account it came to is ready"] = tried("church@example.org")
out["11 server: reply from another account he picked is ready"] = tried("work@example.com")[:8]
# 12: the why line
import answers, card
out["12 fallback why has no raw channel prefix"] = card.why({"source_who": "Email: Pat Doe", "source_when": "2026-11-03"})
out["12 an answer's rewrite carries a new why"] = answers.rebuilt_card(
    {"title": "Old title", "why": "Old reason."}, {"title": "New title", "why": "Pat still needs the date by Friday."}).get("why")
# 13, 14, 18: answered, done and waiting cards
import datetime as dt, comeback
def card_row(iid, state, who="You", asks=None, extra=None, check=None, status=None):
    con = db.connect()
    con.execute("""INSERT INTO live_items (id, source_key, kind, area, title, state, importance, source_who, asks, extra,
                   checkback_date, status, source_messages, created_at, updated_at, state_changed_at)
                   VALUES (?, ?, 'task', 'Work', ?, ?, 0, ?, ?, ?, ?, ?, '[]', now(), now(), now() - INTERVAL 10 DAY)""",
                (iid, "live:test-" + iid, "Card " + iid, state, who, json.dumps(asks or []), json.dumps(extra or {}), check, status))
    con.close()
items.ensure()
card_row("L901", "in_motion", asks=["Old question?"])
done = answers.transform(items.rows("id='L901'")[0], {"action": "done", "id": "L901", "at": common.now().isoformat(timespec="seconds")})
items.update("L901", "test", **{k: v for k, v in done.items() if k in items.COLUMNS})
items.update("L901", "a-later-pass", state="in_motion")
r = items.rows("id='L901'")[0]
out["14 Done holds: a later pass does not reopen it"] = [r["state"], r["asks"]]
out["14 an answered card left with him shows its question, not waiting"] = card.needs({"state": "question", "status": "Answered", "asks": ["Which day?"]})
card_row("L902", "question", asks=["Approve the quote?"])
ap = answers.transform(items.rows("id='L902'")[0], {"action": "answer", "page_action": "approve", "id": "L902", "text": "Approved",
                                                     "at": common.now().isoformat(timespec="seconds")})
out["14 an approval moves the card on and clears the old question"] = [ap.get("state"), ap.get("asks")]
w = items.card_extras({"state": "in_motion", "waiting_on": "Pat at the print shop", "next_check": "2099-01-05"})
out["13 a waiting card keeps whom it waits on and when to look again"] = [json.loads(w.get("extra") or "{}").get("waiting_on"), str(w.get("checkback_date"))]
out["13 a day already past is not taken"] = "checkback_date" in items.card_extras({"state": "in_motion", "next_check": "2001-01-01"})
card_row("L903", "in_motion", who="You", extra={"waiting_on": "Pat at the print shop"}, check=dt.date.today() - dt.timedelta(days=1))
comeback.waiting("test")
r = items.rows("id='L903'")[0]
out["18 a card he added comes back naming whom it waited on"] = ["Pat at the print shop" in (r["asks"] or [""])[0], "You" in (r["asks"] or [""])[0]]
me = common.owner()
card_row("L904", "in_motion", who="You", extra={"waiting_on": me}, check=dt.date.today() - dt.timedelta(days=1))
old_did = f"Back 11/17 12:11 AM: it waited on {me} for 5 working days, since 11/10, and no word came."
card_row("L905", "question", asks=[f"No reply from {me} in 5 working days. Wait longer, write to them, or drop it?"],
         extra={"came_back": {"why": "date", "who": me, "waited_days": 5}})
card_row("L906", "done", asks=[])
con = db.connect()
con.execute("UPDATE live_items SET assistant_did = ? WHERE id IN ('L905', 'L906')", (old_did,))
con.close()
comeback.waiting("test")
r4, r5, r6 = (items.rows(f"id='{i}'")[0] for i in ("L904", "L905", "L906"))
hist = lambda r: " ".join([str(r.get("assistant_did") or "")] + [str(a) for a in r.get("asks") or []])
out["18 a come-back never names the owner, in its history or its question, even when he is the one recorded"] = [
    me in hist(r4), "someone else" in str(r4.get("assistant_did")), "someone else" in (r4["asks"] or [""])[0]]
out["18 an open card's older history naming the owner is cleaned; a done card is left as it was"] = [
    me in hist(r5), str(r5.get("assistant_did")), (json.loads(r5["extra"]) if isinstance(r5["extra"], str) else r5["extra"] or {}).get("came_back", {}).get("who"),
    r6.get("assistant_did") == old_did]
out["18 more than one question: the front says how many more"] = card.wants({"state": "question", "asks": ["A?", "B?", "C?"]})
ex = items.card_extras({"state": "yours"}, {"came_back": {"who": "Pat"}, "waiting_on": "Pat"}, answered=True)
out["18 his answer clears the come-back note and whom it waited on"] = json.loads(ex.get("extra") or "{}")
# 15: a card he asked to see is written by the card writer like any other, from the whole message
import held, think
con = db.connect()
seen = con.execute("""INSERT INTO messages (channel, account, provider_id, thread_id, ts, direction, from_key, to_keys, subject, body,
                      ingested_at) VALUES ('email', 'work@example.com', 'p-seen', 't9', now(), 'in', 'Sam <sam@vendor.example>',
                      'work@example.com', 'Re: the order', 'See below.

> We need the signed order by Friday.', now())
                      RETURNING id""").fetchone()[0]
con.close()
made, said = held.show(seen)
iid = (made or {}).get("id")
owed = (common.read_json(common.THINK_STATE, {}) or {}).get("rewrite_items") or []
row = items.rows("id=?", (iid,))[0] if iid else {}
entry = think._item_entry(row, set()) if row else {}
says = " ".join(m.get("says") or "" for m in entry.get("messages") or [])
out["15 the card he asked to see is owed to the card writer"] = bool(iid) and iid in owed
out["15 the writer sees the message whole, quoted text too"] = "signed order by Friday" in says
seen_work = []
think._write_batch = lambda work, loose, new_set, goals: (seen_work.extend(r["id"] for r in work), (True, ""))[1]
think.write_items([], [], set(owed))
out["15 an owed card is written even with no new message"] = iid in seen_work
# 16: button choices on any card with a question
c = items.card_extras({"state": "question", "asks": ["Which day suits the installer?"], "recommended": "Take Thursday.",
                       "choices": ["Ask for Friday", "Thursday works", "x" * 80, "Yes, as recommended"], "recommended_choice": "Thursday works"})
got = json.loads(c.get("extra") or "{}").get("choices") or []
out["16 a question card gets buttons, its recommended answer first and named"] = [g["label"] for g in got]
out["16 the recommended button answers with its own words"] = got[0]["text"] if got else None
gone = items.card_extras({"state": "in_motion"}, {"choices": got})
out["16 once nothing is asked the buttons go"] = "choices" in json.loads(gone.get("extra") or "{}")
f = card.fill(items.lift({"id": "L9", "state": "question", "asks": ["Which day?"], "extra": {"choices": got}, "title": "t"}))
out["16 the page receives them"] = len(f.get("choices") or [])
dup = items.card_extras({"state": "question", "asks": ["Does anything still use the key, or can it expire?"],
                         "recommended": "Let it expire unless something still uses it.", "choices": ["Let it expire", "Still in use, I'll replace it"]})
out["16 no generic yes, ever"] = [g["label"] for g in json.loads(dup.get("extra") or "{}").get("choices") or []]
f2 = card.fill(items.lift({"id": "L8", "state": "question", "asks": ["Does anything still use the key?"], "title": "t",
                           "recommended": "Let it expire unless something still uses it.",
                           "extra": {"choices": [{"label": "Yes, as recommended", "text": "Approved"}, {"label": "Let it expire", "text": "Let it expire"},
                                                 {"label": "Not sure", "text": "Not sure"}]}}))
out["16 an old generic yes is dropped and the recommendation shows on the front"] = [[c["label"] for c in f2.get("choices") or []], f2.get("rec_front")]
f3 = card.fill(items.lift({"id": "L7", "state": "question", "asks": ["Remind Lou?"], "title": "t", "status": "Back: no reply",
                           "extra": {"came_back": {"why": "date", "who": common.owner(), "waited_days": 5}}}))
out["18 a come-back note naming the owner is never shown"] = f3.get("came_back")
w = items.card_extras({"state": "question", "asks": ["Remind them?"]}, {"came_back": {"who": "Sam"}}, answered=True)
out["18 written afresh, the old come-back note goes"] = "came_back" in json.loads(w.get("extra") or "{}")
# 17: two open cards on one matter become one
card_row("L911", "question", asks=["Which size?"])
card_row("L912", "in_motion")
db.execute("UPDATE live_items SET source_messages='[\"901\"]', assistant_did='Answered by you: \"Which color?\" (red)' WHERE id='L911'")
db.execute("UPDATE live_items SET source_messages='[\"902\"]' WHERE id='L912'")
joined = items.join("L911", "L912", "test")
a, b = items.rows("id='L911'")[0], items.rows("id='L912'")[0]
owed = (common.read_json(common.THINK_STATE, {}) or {}).get("rewrite_items") or []
out["17 joined: the other card takes both cards' messages"] = [joined, b["source_messages"]]
out["17 joined: his answer on the joined card is kept"] = 'Answered by you: "Which color?" (red)' in (b["assistant_did"] or "").splitlines()
out["17 joined: that card closes, the other is written afresh"] = [a["state"], a["status"], "L912" in owed]
out["17 a card cannot join itself or a closed card"] = [items.join("L912", "L912", "t"), items.join("L912", "L911", "t")]
# 19: rebuild every open card, then put them all back
import rebuild
card_row("L921", "in_motion", asks=[])
db.execute("UPDATE live_items SET source_messages='[\"921\"]', answer='Yes, go ahead', answered_at=now(), status='Answered' WHERE id='L921'")
card_row("L922", "yours", asks=["Call Sam?"])
db.execute("UPDATE live_items SET source_messages='[\"922\"]', shelf='later', later_until=TIMESTAMP '2099-02-01 08:00:00' WHERE id='L922'")
card_row("L923", "in_motion", status="Done")       # pressed Done, reopened by a pass before Done held
def snap():
    return {r["id"]: [r["state"], r["status"], r["answer"], str(r["answered_at"]), r["shelf"], str(r["later_until"]), r["title"]]
            for r in items.rows("id IN ('L921', 'L922', 'L923')")}
before = snap()
answers.start_hidden = lambda args: True        # the rebuild's own run is not started here (no Claude run)
res = answers.act_on_answer({"id": "rebuild", "action": "answer", "text": json.dumps({"rebuild": "start"}),
                             "at": common.now().isoformat(timespec="seconds"), "device": "test"})
out["19 a card he pressed Done on closes again"] = items.rows("id='L923'")[0]["state"]
owed = (common.read_json(common.THINK_STATE, {}) or {}).get("rewrite_items") or []
out["19 from the page: every open card is saved and owed a writing"] = ["L921" in owed and "L922" in owed, "saved" in (res.get("result") or "")]
items.update("L921", "rebuild-pass", title="Rewritten title", state="question")      # what a writer could do
items.update("L922", "rebuild-pass", title="Rewritten too", asks=["Call Sam by Friday?"])
after = snap()
out["19 the writer keeps his state, answer and Later date"] = [after["L921"][:4] == before["L921"][:4], after["L922"][4:6] == before["L922"][4:6]]
n, said = rebuild.put_back()
out["19 put back: every card exactly as it was"] = snap() == before
out["19 put back: nothing of the rebuild is still owed"] = any(i in ((common.read_json(common.THINK_STATE, {}) or {}).get("rewrite_items") or []) for i in ("L921", "L922"))
# 20: a correction he gives becomes his rule, shown back, listed in Settings, obeyed by every card writing, removable
import filters, settings_page, chat
card_row("L931", "question", asks=["Reply to the vendor?"])
chat._run = lambda words, told, sess: ("You will call them instead.\n"
    'ACTION: {"type": "rule", "text": "From now on, file anything from Summit Ridge Fire Protection under Work, never Personal."}\n'
    'ACTION: {"type": "card", "state": "done", "settled": [1], "card": null}', "", 0.1, {})     # the chat's run, stood in
import card_rules
card_rules._claude = lambda prompt, timeout=None: ('{"cards": []}', "", 0.1)        # the rule scan, stood in: it covers no card
rec, said, _t = answers.think_on(items.finish(items.rows("id='L931'")[0]), "Wrong area, this is work. Always file them under Work.")
# on a card the rule is not saved at once: it is handed back to be proposed under the box (card_rules.py); Approve saves it
held = len([r for r in filters.rules() if r["way"] == "card_rule"])
said = filters.save_correction(_t.get("rule_offer"), "Approved on the card")[1]
mine = [r for r in filters.rules() if r["way"] == "card_rule"]
out["20 the correction is saved as his rule and shown back"] = [held, len(mine), "Saved: From now on, file anything" in said]
out["20 it is listed in Settings"] = "Summit Ridge Fire Protection under Work" in json.dumps(settings_page.for_page())
out["20 the card writer and answer reader are told it"] = ["Summit Ridge" in think._owner_filter(), "Summit Ridge" in filters.lines_for_writing()]
again = filters.save_correction(mine[0]["text"], "again")[0]
out["20 said twice, kept once"] = len([r for r in filters.rules() if r["way"] == "card_rule"])
chat_items, chat_line = chat._do({"type": "rule", "text": "Always put the job number first in a card's header."}, "words", common.now(), 0)
out["20 a correction in the chat is its own card, saved only on Approve"] = [bool(chat_items) and (chat_items[0].get("rule_offer") or {}).get("made") == "rule",
    "Cards, under Needs you" in chat_line, any("job number" in r["text"] for r in filters.rules())]
filters.save_rules([{"id": r["id"], "text": r["text"], "way": r["way"], "on": r.get("on", True)} for r in filters.rules()
                    if "Summit Ridge" not in r["text"]])
out["20 removed in Settings: no step is told it any more"] = ["Summit Ridge" in think._owner_filter(), "Summit Ridge" in filters.lines_for_writing()]
# 21: a Junk or Never junk answer acts on its sender, closes the card for good, and nothing reopens or rewrites it
import presses, think, rebuild
rules = presses._rules()
sys.path.insert(0, common.paths.CORE)
import judgment_commit as jc
r1 = rules.propose("senders", "judged junk 3 times in a row", "", rules.ALWAYS, pattern="email:a@junk.example")
r2 = rules.propose("senders", "judged junk 3 times in a row", "", rules.ALWAYS, pattern="email:b@junk.example")
e2 = next(e for e in rules.parse("senders") if e["id"] == r2)
rules._remove(r2)       # proposed after he answered the older card
rules._insert(e2["doc"], rules.WAITING, [rules._entry_line(r2, e2["text"], e2["pattern"], None, dt.datetime.now() + dt.timedelta(days=1), rules.ALWAYS)])
db.execute("INSERT INTO tasks (item_key, kind, area, title, detail, status, urgency, first_seen, last_seen, created_at, updated_at)"
           " VALUES (?, 'task', 'System', 'Junk or never junk: 1 sender(s)', 'x', 'needs_me', 'normal', today(), today(), now(), now())", (jc.ASK_KEY,))
con = db.connect()
con.execute("""INSERT INTO live_items (id, source_key, kind, area, title, state, importance, asks, source_messages, answer, answered_at,
               status, assistant_did, created_at, updated_at, state_changed_at)
               VALUES ('L941', ?, 'question', 'System', 'Mail from a@junk.example: junk or never junk?', 'question', 0, '[]', '[]',
               'Junk', now(), 'Answered', 'Recorded your answer: Junk. Nothing is sent while the live system runs beside the old one.',
               now(), now(), now())""", (presses.JUNK_ASK,))
con.close()
n, bad = answers.settle_junk_answers()
l941 = items.rows("id='L941'")[0]
def where(rid):
    e = next((x for x in rules.parse("senders") if x["id"] == rid), None)
    return e and (e["status"] if e["status"] == "proposed" else e["section"])
out["21 an answer recorded but never acted on is acted on, as of when he gave it"] = [n, bad, l941["state"], l941["status"], where(r1), where(r2)]
jc.ask_junk_senders()
items.sync_from_tasks("t1")
one = [r for r in items.rows("source_key LIKE 'task:system::noise rule proposals::%'")]
out["21 one card per sender, naming it, with its question and Junk / Never junk"] = [len(one), one and one[0]["source_key"].endswith("::" + str(r2)),
    one and "b@junk.example" in one[0]["title"], one and one[0]["state"], one and one[0]["asks"], items.finish(dict(one[0])).get("choices") if one else None]
out["21 the older card stays closed"] = items.rows("id='L941'")[0]["state"]
c2 = one[0]["id"] if one else None
at = str(items.rows(f"id='{c2}'")[0]["updated_at"])
jc.ask_junk_senders()
items.sync_from_tasks("t2")
out["21 a pass does not touch it again (never shown as new)"] = str(items.rows(f"id='{c2}'")[0]["updated_at"]) == at
db.execute("UPDATE live_items SET source_messages='[\"77\"]' WHERE id=?", (c2,))      # even with a message behind it
answers.start_hidden = lambda args: True
rebuild.start()
owed = (common.read_json(common.THINK_STATE, {}) or {}).get("rewrite_items") or []
out["21 a rebuild and the card writer leave it alone"] = [c2 in owed, think.write_items([], [], forced=[c2])[1]]
items.export("t3")
answers.act_on_answer({"id": c2, "action": "answer", "text": "Junk", "at": common.now().isoformat(timespec="seconds"), "device": "test"})
answers.wait_landed(30)
out["21 Junk on the card: its sender on the junk list, the card closed"] = [where(r2), items.rows(f"id='{c2}'")[0]["state"]]
jc.ask_junk_senders()
items.sync_from_tasks("t4")
out["21 closed for good: no pass reopens it"] = [items.rows(f"id='{c2}'")[0]["state"],
    db.query("SELECT status FROM tasks WHERE item_key=?", (jc.ASK_KEY + "::" + str(r2),))[0][0]]
# 22: a Rebuild press the listener could not act on is acted on by the pass; nothing it cannot use shows a file name
import glob, os
folder = rebuild.FOLDER
saves = lambda: len(glob.glob(os.path.join(folder, "saved-*.json")))
st = common.read_json(rebuild.STATE, {}) or {}
st["done_at"] = st["at"]
common.write_json(rebuild.STATE, st)
before_n = saves()
later = (dt.datetime.fromisoformat(st["at"]) + dt.timedelta(minutes=5)).isoformat(timespec="seconds")
answers._save({"id": "rebuild", "action": "answer", "text": json.dumps({"rebuild": "start"}), "at": later, "device": "test"})
n, bad, _c = answers.apply_files("t5")
out["22 a saved Rebuild press is run by the pass"] = [saves() - before_n, bad]
st = common.read_json(rebuild.STATE, {}) or {}
earlier = (dt.datetime.fromisoformat(st["at"]) - dt.timedelta(minutes=1)).isoformat(timespec="seconds")
answers._save({"id": "rebuild", "action": "answer", "text": json.dumps({"rebuild": "start"}), "at": earlier, "device": "test"})
mid_n = saves()
n, bad, _c = answers.apply_files("t6")
out["22 one pressed while a rebuild ran is cleared, not run twice"] = [saves() - mid_n, bad]
answers._save({"id": "L99999", "action": "answer", "text": "Yes", "at": common.now().isoformat(timespec="seconds"), "device": "test"})
n, bad, _c = answers.apply_files("t7")
out["22 an answer for a card that is gone is said plainly, with no file name"] = [len(bad), any(".json" in b for b in bad), bool(bad) and bad[0].startswith("An answer you gave")]
print(json.dumps(out, default=str))
'''

WANT = {
    "11 email reply goes from the account it came to": [True, "church@example.org"],
    "11 a chat card (a kind an addition brings): no email reply, says why": [False, True],
    "11 text card: no email reply, says why": [False, True],
    "11 came to an account that cannot send: refused": [False, None],
    "11 server: reply from the account it came to is ready": "ready",
    "11 server: reply from another account he picked is ready": "ready",
    "12 fallback why has no raw channel prefix": "Pat Doe wrote to you on 11/3.",
    "12 an answer's rewrite carries a new why": "Pat still needs the date by Friday.",
    "14 Done holds: a later pass does not reopen it": ["done", []],
    "14 an answered card left with him shows its question, not waiting": "answer",
    "14 an approval moves the card on and clears the old question": ["in_motion", []],
    "13 a waiting card keeps whom it waits on and when to look again": ["Pat at the print shop", "2099-01-05"],
    "13 a day already past is not taken": False,
    "18 a card he added comes back naming whom it waited on": [True, False],
    "18 a come-back never names the owner, in its history or its question, even when he is the one recorded": [False, True, True],
    "18 an open card's older history naming the owner is cleaned; a done card is left as it was": [
        False, "Back 11/17 12:11 AM: it waited on someone else for 5 working days, since 11/10, and no word came.", "someone else", True],
    "18 more than one question: the front says how many more": "A? (and 2 more; open the card)",
    "18 his answer clears the come-back note and whom it waited on": {},
    "15 the card he asked to see is owed to the card writer": True,
    "15 the writer sees the message whole, quoted text too": True,
    "15 an owed card is written even with no new message": True,
    "16 a question card gets buttons, its recommended answer first and named": ["Thursday works (recommended)", "Ask for Friday"],
    "16 the recommended button answers with its own words": "Thursday works",
    "16 once nothing is asked the buttons go": False,
    "16 the page receives them": 2,
    "16 no generic yes, ever": ["Let it expire", "Still in use, I'll replace it"],
    "16 an old generic yes is dropped and the recommendation shows on the front": [["Let it expire", "Not sure"], "Let it expire unless something still uses it."],
    "18 a come-back note naming the owner is never shown": None,
    "18 written afresh, the old come-back note goes": False,
    "19 a card he pressed Done on closes again": "done",
    "17 joined: the other card takes both cards' messages": [True, ["902", "901"]],
    "17 joined: his answer on the joined card is kept": True,
    "17 joined: that card closes, the other is written afresh": ["done", "Joined into L912", True],
    "17 a card cannot join itself or a closed card": [False, False],
    "19 from the page: every open card is saved and owed a writing": [True, True],
    "19 the writer keeps his state, answer and Later date": [True, True],
    "19 put back: every card exactly as it was": True,
    "19 put back: nothing of the rebuild is still owed": False,
    "20 the correction is saved as his rule and shown back": [0, 1, True],
    "20 it is listed in Settings": True,
    "20 the card writer and answer reader are told it": [True, True],
    "20 said twice, kept once": 1,
    "20 a correction in the chat is its own card, saved only on Approve": [True, True, False],
    "20 removed in Settings: no step is told it any more": [False, False],
    "21 an answer recorded but never acted on is acted on, as of when he gave it": [1, [], "done", "Junk", "Always junk", "proposed"],
    "21 one card per sender, naming it, with its question and Junk / Never junk": [1, True, True, "question", ["Junk or never junk?"], ["Junk", "Never junk"]],
    "21 the older card stays closed": "done",
    "21 a pass does not touch it again (never shown as new)": True,
    "21 a rebuild and the card writer leave it alone": [False, "no item needed writing"],
    "21 Junk on the card: its sender on the junk list, the card closed": ["Always junk", "done"],
    "21 closed for good: no pass reopens it": ["done", "done"],
    "22 a saved Rebuild press is run by the pass": [1, []],
    "22 one pressed while a rebuild ran is cleared, not run twice": [0, []],
    "22 an answer for a card that is gone is said plainly, with no file name": [1, False, True],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="cards-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_cards", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47898",
                            "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=300)
        got = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
        if not got:
            check("the checks ran", r.stderr.strip()[-400:], "")
        for name, want in WANT.items():
            check(name, got.get(name), want)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
