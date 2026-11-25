r"""Acceptance (quick): phase 1 of the judgment rebuild, "predict and record everywhere". On a scratch copy laid down from this
plugin, with made-up messages and people; the gathering and the Claude runs are stood in for (no Claude run, nothing sent).

- A pass with made-up messages gives each card a pick: the card writer's where it wrote one, the program's where it did not;
  the pick is on the card the page reads (items.json), and the pass log line says what the picks cost.
- A press of another button than the pick writes a rule book row with both; a press of the pick itself is a match; typed
  words on a card write a row too, with the pick beside them.
- What he did instead of the pick is kept, and the next card like it offers it ("Last time: ...").
- The next pass records a made-up sent email (matched to its card, the card's pick beside it), a made-up sent text (one from the
  phone recorded as outside the page, one sent from the page's Texts part as a page send), and an
  invitation accepted in the calendar, each as a rule book row, and its pass log line says so.

    python tests\rebuild_picks_acceptance.py
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
import datetime as dt, json, os, re, sys, time
live = sys.argv[1]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core")); os.chdir(live)
os.environ["ASSISTANT_PAGE_LATER"] = "1"; os.environ["ASSISTANT_QUICK_PASS"] = "1"
import common, db, items, think, gather, ai_steps, answers, rule_book, picks, card, updates
from connections import _store
P = __import__("pass")
out = {}
now = dt.datetime.now().replace(microsecond=0)
db.init_schema(); items.ensure()
con = db.connect()
for mid, fk, subj, body, thread in ((20001, "email:pat@example.test", "Shed day", "Which day works for the shed, Thursday or Friday?", "t-pat"),
                                    (20002, "email:lee@example.test", "Paint is in", "The paint you ordered is in at the shop. Can you pick it up?", "t-lee")):
    con.execute("INSERT INTO messages (id, channel, account, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)"
                " VALUES (?, 'email', 'me@example.test', ?, ?, 'in', ?, '[]', ?, ?, ?)", (mid, thread, now - dt.timedelta(hours=2), fk, subj, body, now))
    con.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES ('judged', ?, 'task', 'made-up', ?)", (f"msg:{mid}", now))
con.close()
common.write_json(common.THINK_STATE, {"failed_at": None, "rewrite_items": [], "pending_items": [], "pending_msgs": [20001, 20002], "last": []})
start = (now + dt.timedelta(days=1)).replace(hour=9, minute=0, second=0)
_store.calendar_events([("ev1", "Work", "Site walk", start, start + dt.timedelta(hours=1), False, "", "", now, "needsAction")], prune=False)

# the card writer, stood in for: Pat's card with its pick, Lee's with none (the program's pick then)
def writer(prompt, model, timeout, resume=None):
    payload = common.read_json(re.search(r"Read the input file: (\S+)", prompt).group(1), {})
    dest = re.search(r"Write your output file to exactly this path: (\S+)", prompt).group(1)
    new = []
    for m in payload.get("loose_messages") or []:
        if m["id"] == 20001:
            new.append({"messages": [20001], "kind": "question", "area": "Personal", "title": "Pat asks which day works for the shed",
                        "header": "Pat: which day for the shed?", "why": "Pat asks which day works.", "detail": "Pat's email asks Thursday or Friday.",
                        "recommended": "Say Thursday.", "asks": ["Which day works for the shed?"],
                        "choices": [{"text": "Thursday works", "meaning": "agrees"}, {"text": "Ask for Friday", "meaning": "other"}],
                        "recommended_choice": "Thursday works", "pick": {"do": "choice", "text": "Thursday works"},
                        "evidence": "Pat's email (20001)", "state": "question", "important": False})
        else:
            new.append({"messages": [m["id"]], "kind": "fyi", "area": "Personal", "title": "Lee says the paint is in at the shop",
                        "header": "Paint is in at the shop", "why": "Lee says the paint is in.", "detail": "Lee's email says the paint is in.",
                        "recommended": None, "asks": [], "evidence": f"Lee's email ({m['id']})", "state": "handled", "important": False})
    common.write_json(dest, {"items": [], "new_items": new, "loose": []})
    return ai_steps.Result(True, "ok", "s1", 1.0, 0.0, out_tokens=900)
think._engine_call = writer
updates.check = lambda pass_id: None          # no look for a newer version from a test

def gather_nothing(pass_id):
    return {"pass_id": pass_id, "secs": 0.1, "new_messages": [], "new_in": 0, "by_channel": {}, "new_attachments": 0,
            "pages_waiting": 0, "texted_images_waiting": 0, "unjudged": 0, "sources": {}, "follow": {}, "timing": {}, "problems": []}
gather.gather = gather_nothing

# --- 1. a pass: each card has a pick; the pass log line says what it cost ---
P.main()
snap = common.read_json(common.ITEMS_JSON, {}).get("items") or []
cards = {c["source_messages"][0]: c for c in snap if c.get("source_messages")}
pat, lee = cards.get("20001") or {}, cards.get("20002") or {}
out["1. each card has a pick: the writer's and the program's"] = [
    {k: (pat.get("pick") or {}).get(k) for k in ("do", "text", "label", "by")},
    {k: (lee.get("pick") or {}).get(k) for k in ("do", "press", "label", "by")}]
with open(common.PASS_LOG, encoding="utf-8") as f:
    line1 = f.read().splitlines()[-1]
out["1. the pass log line says the pick's cost"] = [
    bool(re.search(r"picks: 1 of 2 written card\(s\) picked by the writer, about \d+ output tokens \(estimate\) of the writer's 900 output tokens", line1)),
    "0 extra AI runs" in line1]

# --- 2. another button than the pick: a row with both; the pick itself: a match; typed words: a row ---
def act(c, rec):
    rec = dict({"id": c["id"], "action": "answer", "at": now.isoformat(timespec="seconds"), "acted_at": now.isoformat(timespec="seconds")}, **rec)
    return answers.act_on_answer(rec)
act(pat, {"text": json.dumps({"press": {"name": "later", "when": "tomorrow"}}), "label": "Snooze"})
r = next(x for x in rule_book._read() if x.get("card") == pat["id"])
out["2. Snooze on Pat's card: the row has my pick and what he did"] = [r["message"], r["press"], r["pick"]["do"], r["pick"]["text"],
                                                                        r["did"], r["pick_outcome"], r["call"]]
act(lee, {"text": json.dumps({"press": {"name": "got_it"}}), "label": "Got it", "pick": "1"})
r = [x for x in rule_book._read() if x.get("card") == lee["id"]][-1]
out["2. the pick itself pressed on Lee's card: a match"] = [r["press"], r["pick"]["press"], r["pick_outcome"]]
answers._record({"id": pat["id"], "action": "answer", "text": "Tell Pat Saturday instead", "at": now.isoformat(timespec="seconds")}, time.time(),
                pat, "words", "Reading.", True, True, None, pick=picks.of(pat))
r = [x for x in rule_book._read() if x.get("card") == pat["id"]][-1]
out["2. typed words on Pat's card: a row with the pick beside them, saying nothing about show or hide"] = [
    r["press"], r["meaning"], r["did"], r["pick_outcome"]]
sec = rule_book.for_settings()
you = [x["you"] for s in sec["sections"] for x in s["rows"] if x["message"] == "20001"]
out["2. Settings says what he did and what I'd picked"] = you

# --- 2b. Drop: the card leaves the page, a row with action drop that says nothing about show or hide; Done, Got it and Drop are
# three different answers against the pick
con = db.connect()
con.execute("INSERT INTO messages (id, channel, account, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)"
            " VALUES (20005, 'email', 'me@example.test', 't-kim', ?, 'in', 'email:kim@example.test', '[]', 'Raffle', 'Want raffle tickets?', ?)", (now, now))
con.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES ('judged', 'msg:20005', 'task', 'made-up', ?)", (now,))
iid = "L" + str(con.execute("SELECT nextval('seq_live_item')").fetchone()[0])
con.close()
db.execute("INSERT INTO live_items (" + ", ".join(items.BASE_COLUMNS) + ") VALUES (" + ", ".join("?" for _ in items.BASE_COLUMNS) + ")",
           (iid, "live:msg-20005", "question", "Personal", "Kim asks if you want raffle tickets", None, "question", 0, None, "Kim", now, "Kim",
            json.dumps(["20005"]), None, json.dumps(["Buy raffle tickets?"]), None, "Kim's email (20005)", "[]", None, None, None, None, None, now, now, now, None, "t"))
items.export("t")
kim = next(c for c in common.read_json(common.ITEMS_JSON, {})["items"] if c["id"] == iid)
act(kim, {"text": json.dumps({"press": {"name": "drop"}}), "label": "Drop"})
r = [x for x in rule_book._read() if x.get("card") == iid][-1]
k2 = items.card_for(iid)
out["2b. Drop closes the card as dropped, a row with action drop, neutral, no show-or-hide learning job"] = [
    k2["state"], k2["status"], (k2.get("last_press") or {}).get("happened"), r["press"], r["meaning"], r["did"], len([j for j in __import__("rsi_loop").jobs() if j.get("kind", "rules") == "rules"])]
O = picks.outcome
out["2b. Done, Got it and Drop never match each other"] = [O({"do": "press", "press": a}, {"do": "press", "press": b}) for a, b in
    (("done", "got_it"), ("got_it", "done"), ("drop", "done"), ("done", "drop"), ("got_it", "drop"), ("drop", "drop"))]

# --- 3. the choices grow: the next card from Pat offers what he did last time ---
nxt = {"id": "L999", "state": "question", "kind": "question", "area": "Personal", "title": "Pat asks about the fence", "source_messages": ["1"],
       "sender": {"key": "email:pat@example.test"}, "asks": ["Which fence?"], "extra": {"choices": [{"label": "Cedar (recommended)", "text": "Cedar", "recommended": True}, {"label": "Pine", "text": "Pine"}]}}
card.fill(nxt)
out["3. the next card from Pat: my pick, and what he did instead last time"] = [nxt["pick"]["label"], (nxt.get("last_time") or {}).get("label")]

# --- 4. the next pass: a sent email, a sent text and an accepted invitation, each a row ---
def gather_sent(pass_id):
    import texts            # a text sent from the page: the Texts part's own Send, reported sent by the link
    stamp = texts._iso(common.now())
    common.write_json(texts.OUTBOX, {"items": [{"id": "tx1", "conv": "", "gm": "", "gl": "", "phone": "5550002222", "name": "Jo",
                                                "text": "See you at  noon", "status": "sending", "created": stamp, "updated": stamp, "taken": stamp, "error": ""}]})
    texts.report("tx1", True)
    c = db.connect()
    c.execute("INSERT INTO messages (id, channel, account, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)"
              " VALUES (20003, 'email', 'me@example.test', 't-lee', ?, 'out', 'email:me@example.test', '[\"email:lee@example.test\"]',"
              " 'Re: Paint is in', 'Thanks, I will pick it up Saturday.', ?)", (now, now))
    c.execute("INSERT INTO messages (id, channel, account, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)"
              " VALUES (20004, 'sms', 'phone', 'sms:t-sam', ?, 'out', 'sms:me', '[\"sms:+15550001111\"]', NULL, 'Running late, there by 10', ?)", (now, now))
    c.execute("INSERT INTO messages (id, channel, account, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)"
              " VALUES (20006, 'sms', 'phone', 'sms:t-jo', ?, 'out', 'sms:me', '[\"sms:+15550002222\"]', NULL, 'See you at noon', ?)", (now, now))
    for mid in (20003, 20004, 20006):
        c.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES ('judged', ?, 'ignore', 'made-up', ?)", (f"msg:{mid}", now))
    c.close()
    _store.calendar_events([("ev1", "Work", "Site walk", start, start + dt.timedelta(hours=1), False, "", "", now, "accepted")], prune=False)
    return dict(gather_nothing(pass_id), new_messages=[20003, 20004, 20006], by_channel={"email": 1, "sms": 2})
gather.gather = gather_sent
time.sleep(1.2)
P.main()
with open(common.PASS_LOG, encoding="utf-8") as f:
    line2 = f.read().splitlines()[-1]
by = {x["message"]: x for x in rule_book._read() if x.get("off_page")}
e, t, cal, tp = by.get("20003") or {}, by.get("20004") or {}, by.get("cal:ev1") or {}, by.get("20006") or {}
out["4. the sent email: a row matched to Lee's card, his reply beside my pick"] = [
    e.get("press"), (e.get("off_page") or {}).get("where"), (e.get("off_page") or {}).get("channel"), e.get("card") == lee["id"],
    (e.get("pick") or {}).get("press"), (e.get("did") or {}).get("do"), e.get("pick_outcome"), e.get("meaning"), e.get("call")]
out["4. the sent text: a row, no card"] = [t.get("press"), (t.get("off_page") or {}).get("channel"), t.get("card"), t.get("section")]
out["4. a text from the phone is outside, one sent from the page is a page send"] = [(t.get("off_page") or {}).get("where"), (tp.get("off_page") or {}).get("where")]
out["4. the invitation accepted in the calendar: a row"] = [(cal.get("off_page") or {}).get("did"), cal.get("section"), cal.get("seen", {}).get("what")]
out["4. the pass log line says so"] = "4 thing(s) you did outside the page recorded" in line2
out["4. nothing about show or hide changed: no show-or-hide learning job queued"] = len([j for j in __import__("rsi_loop").jobs() if j.get("kind", "rules") == "rules"])
print(json.dumps(out, default=str))
'''

WANT = {
    "1. each card has a pick: the writer's and the program's": [
        {"do": "choice", "text": "Thursday works", "label": "Thursday works", "by": "writer"},
        {"do": "press", "press": "got_it", "label": "Got it", "by": "program"}],
    "1. the pass log line says the pick's cost": [True, True],
    "2. Snooze on Pat's card: the row has my pick and what he did": [
        "20001", "later", "choice", "Thursday works", {"do": "press", "press": "later"}, "differed", "show"],
    "2. the pick itself pressed on Lee's card: a match": ["got_it", "got_it", "matched"],
    "2. typed words on Pat's card: a row with the pick beside them, saying nothing about show or hide": [
        "words", "neutral", {"do": "words", "words": "Tell Pat Saturday instead"}, "differed"],
    "2. Settings says what he did and what I'd picked": ["You wrote: \"Tell Pat Saturday instead\". I'd picked \"Thursday works\"."],
    "2b. Drop closes the card as dropped, a row with action drop, neutral, no show-or-hide learning job": [
        "done", "Dropped", "Dropped. I won't bring it up again unless something new comes in about it.", "drop", "neutral",
        {"do": "press", "press": "drop"}, 0],
    "2b. Done, Got it and Drop never match each other": ["differed", "differed", "differed", "differed", "differed", "matched"],
    "3. the next card from Pat: my pick, and what he did instead last time": ["Cedar", "Tell Pat Saturday instead"],
    "4. the sent email: a row matched to Lee's card, his reply beside my pick": [
        "sent", "outside", "email", True, "got_it", "reply", "differed", "neutral", None],
    "4. the sent text: a row, no card": ["sent", "sms", None, "replies"],
    "4. a text from the phone is outside, one sent from the page is a page send": ["outside", "page"],
    "4. the invitation accepted in the calendar: a row": ["accepted", "calendar", "Site walk"],
    "4. the pass log line says so": True,
    "4. nothing about show or hide changed: no show-or-hide learning job queued": 0,
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="rebuild1-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    env.pop("ASSISTANT_REPLAY", None)
    spec = importlib.util.spec_from_file_location("ac_rebuild1", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47938", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=600)
        try:
            o = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            o = {}
            check("the checks ran", (r.stderr or r.stdout)[-2500:], "")
        for name, want in WANT.items():
            check(name, o.get(name), want)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
