r"""Acceptance: the rule book's rows (the RSI plan, "The rule book's rows"). The engine's own press code, run in a scratch home
with a scratch database of made-up messages, verdicts and cards. Nothing outside the scratch folder is touched, and nothing
goes to Claude.

- "I should have seen this" on a row under Hidden writes a row naming the layer that held the message (read before its card
  is made, since making it overwrites the verdict), with the press's meaning.
- A press on a card the judge made writes a row with the judge's call; Got it (neutral) writes one too.
- On read a neutral press never replaces a signal: Got it after "I should have seen this" (or after Not needed) keeps the
  signal; a neutral row counts only for a message with no signal. Retire takes the message out of the active rule book and no
  older row comes back; a newer press after it counts again.
- A press while the database is held is written as waiting, does not count, and once the database is free (the presses'
  own drain) ends with the real call and layer.
- A row carries the judge's coverage mark (covered, leaned_on) as the answered table keeps it, also after a held press; a
  home whose table has no such columns still reads the call.
- Sections: plain rules on card kind, key, area and hold reason; unknown goes to page.
- A replay run (ASSISTANT_REPLAY) writes no rows, and replay keeps the file (named in what erase keeps, never in what it moves).

    python tests\rsi_rows_acceptance.py
"""
import json
import os
import subprocess
import sys
import tempfile

import _cleanup  # noqa: E402  the scratch folder goes when the test ends

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
results = []

INSIDE = r'''
import datetime as dt, json, sys, time
sys.path.insert(0, sys.argv[1])
import common, db, items, presses, answers, held, rule_book
out = {}
db.init_schema()
items.ensure()
ts = dt.datetime(2026, 11, 23, 8, 0)
msgs = [(11, "email", "email:deals@shop.example.test", "Big sale this week", "held by a junk rule"),
        (12, "email", "email:pat@example.test", "Which day works for the shed?", "the judge showed it"),
        (13, "email", "email:news@letters.example.test", "Weekly letter", "the first sort hid it"),
        (14, "email", "email:lee@example.test", "Shed paint", "the judge showed it, its reason says emailing")]
con = db.connect()
for mid, ch, fk, subj, body in msgs:
    con.execute("INSERT INTO messages (id, channel, account, ts, direction, from_key, subject, body, ingested_at)"
                " VALUES (?, ?, 'me@example.test', ?, 'in', ?, ?, ?, ?)", (mid, ch, ts, fk, subj, body, ts))
con.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES"
            " ('judged', 'msg:11', 'noise', 'rule:77', ?), ('judged', 'msg:12', 'task', 'Pat asks which day works for the shed', ?),"
            " ('judged', 'msg:13', 'noise', 'fast: a weekly newsletter', ?),"
            " ('judged', 'msg:14', 'task', 'Lee is emailing about the shed paint and its mailing list', ?)", (ts, ts, ts, ts))
con.close()
common.write_json(common.ITEMS_JSON, {"items": []})

# --- 1. a press on a row under Hidden: the holding layer, read before its card is made ---
press = json.dumps({"press": {"name": "should_have_seen"}})
got = answers._held_press({"id": "held-11", "action": "answer", "text": press, "at": "2026-11-24T09:00:00",
                           "acted_at": "2026-11-24T09:00:01"}, time.time())
r = rule_book.rows()
out["1. should have seen this on a held row: one row naming the holding layer"] = [
    {k: x[k] for k in ("message", "call", "layer", "verdict", "source", "rules", "press", "meaning", "status")} for x in r]
out["1. ... with a snapshot of what was seen and the card it made"] = [r[0]["seen"]["what"], r[0]["seen"]["channel"],
                                                                      bool(r[0]["card"]), r[0]["card_kind"]]
v = db.query("SELECT verdict, source FROM answered WHERE key = 'msg:11'")[0]
out["1. (making the card did overwrite the verdict, which is why it is read first)"] = list(v)

# --- 2. a press on a card the judge made: the judge's call ---
card = {"id": "L7", "source_key": "task:personal::shed-day", "kind": "question", "area": "Personal", "state": "question",
        "title": "Pat: which day works for the shed?", "source_messages": ["12"]}
answers._record({"id": "L7", "action": "answer", "text": json.dumps({"press": {"name": "not_needed", "scope": "this"}}),
                 "at": "2026-11-24T09:05:00"}, time.time(), card, "not_needed", "Done.", True, False, {"name": "not_needed", "scope": "this"})
x = next(x for x in rule_book.rows() if x["message"] == "12")
out["2. a judged card's press: the judge's call and the meaning"] = {k: x[k] for k in ("call", "layer", "verdict", "source", "press",
                                                                                      "meaning", "section", "card_kind", "card_area")}
out["2. typed words and a refused press write no row"] = [
    answers._record({"id": "L7", "action": "answer", "text": "thanks", "at": "2026-11-24T09:06:00"}, time.time(), card, "words",
                    "Reading.", True, True, None),
    answers._record({"id": "L7", "action": "answer", "text": json.dumps({"press": {"name": "no"}}), "at": "2026-11-24T09:06:00"},
                    time.time(), card, "no", "That button is for a card that asks yes or no.", False, False, {"name": "no"}),
    len([x for x in rule_book._read() if x["message"] == "12"])]

# --- 3. a neutral press never replaces a signal ---
made = {"id": r[0]["card"], "kind": "task", "area": "Personal", "title": "Made from a Hidden row", "source_messages": ["11"]}
for c, at in ((made, "2026-11-24T09:10:00"), (card, "2026-11-24T09:11:00")):
    answers._record({"id": c["id"], "action": "answer", "text": json.dumps({"press": {"name": "got_it"}}), "at": at},
                    time.time(), c, "got_it", "Done.", True, False, {"name": "got_it"})
out["3. Got it after should have seen this, and after Not needed, keeps the signal on read; both Got it rows are kept"] = [
    [(x["message"], x["press"], x["meaning"], x["layer"]) for x in rule_book.rows()], len(rule_book._read())]

# --- 4. retire ---
out["4. retire: gone from the active rule book, kept as retired, no older row comes back"] = [
    rule_book.retire("12", "made-up reason"), [x["message"] for x in rule_book.rows()],
    [(x["message"], x["status"]) for x in rule_book.rows(active_only=False)], rule_book.retire("12")]
answers._record({"id": "L7", "action": "answer", "text": json.dumps({"press": {"name": "always_show", "scope": "sender"}}),
                 "at": "2026-11-24T09:20:00"}, time.time(), card, "always_show", "On your list.", True, False,
                {"name": "always_show", "scope": "sender"})
out["4. a newer press after a retire counts again"] = [(x["message"], x["press"], x["status"]) for x in rule_book.rows()]

# --- 5. the first sort is named; sections ---
fs = rule_book._from_db(["13"])[1]["13"]
out["5. a message the first sort hid names the first sort"] = [fs["call"], fs["layer"]]
S = rule_book.section
out["5. sections"] = [S({"kind": "calendar_ok"}), S({"kind": "waiting"}), S({"source_key": "live:ready-3"}),
                      S({"area": "Bills"}), S({"source_key": "live:receipts-9"}), S({}, "rule:559"), S({}, "fast: a newsletter"),
                      S({"kind": "task", "area": "Personal"}), S(None)]
out["5. by section"] = [len(rule_book.rows("page")), len(rule_book.rows("mailings"))]

# --- 7. a shown card's reason never picks its section; Got it all: one row per card; the database held ---
lee = {"id": "L9", "kind": "task", "area": "Personal", "title": "Lee: shed paint", "source_messages": ["14"]}
rule_book.on_presses([lee, card], "got_it_all", "neutral", "-", "every card that needs nothing", "2026-11-24T09:30:00")
by = {x["message"]: x for x in rule_book.rows()}
out["7. Got it all: a row for each card; it counts only where there is no signal; a shown card's reason never picks mailings"] = [
    (by["14"]["press"], by["14"]["section"]), (by["12"]["press"], by["12"]["meaning"]),
    len([x for x in rule_book._read() if x.get("press") == "got_it_all"])]
real = db.try_connect
db.try_connect = lambda *a, **k: None
answers._record({"id": "L9", "action": "answer", "text": json.dumps({"press": {"name": "not_needed", "scope": "this"}}),
                 "at": "2026-11-24T09:40:00"}, time.time(), lee, "not_needed", "Done.", True, False, {"name": "not_needed", "scope": "this"})
x = next(x for x in rule_book.rows() if x["message"] == "14")
waiting = [w for w in rule_book._read() if w.get("pending")]
out["7. a press while the database is held is written waiting and does not count yet"] = [
    x["press"], [(w["message"], w["press"], w["call"], w["layer"]) for w in waiting], len(common.read_json(rule_book.WAITING, []))]
db.try_connect = real
presses.flush()             # the presses' own drain, as the next press, landing or pass does it
x = next(x for x in rule_book.rows() if x["message"] == "14")
out["7. once the database is free it ends with the real call and layer, and nothing waits"] = [
    x["press"], x["meaning"], x["call"], x["layer"], x["source"], x["seen"]["what"], common.read_json(rule_book.WAITING, []),
    rule_book.drain()]

# --- 8. the judge's coverage mark goes on the row as the answered table keeps it ---
db.execute("UPDATE answered SET covered = false, leaned_on = 'the shed thread' WHERE key = 'msg:14'")
pat = {"id": "L10", "kind": "task", "area": "Personal", "title": "Pat: shed day", "source_messages": ["12"]}
for c, at in ((lee, "2026-11-24T09:50:00"), (pat, "2026-11-24T09:51:00")):
    answers._record({"id": c["id"], "action": "answer", "text": json.dumps({"press": {"name": "not_needed", "scope": "this"}}),
                     "at": at}, time.time(), c, "not_needed", "Done.", True, False, {"name": "not_needed", "scope": "this"})
by = {x["message"]: x for x in rule_book.rows()}
db.try_connect = lambda *a, **k: None
answers._record({"id": "L9", "action": "answer", "text": json.dumps({"press": {"name": "always_show", "scope": "sender"}}),
                 "at": "2026-11-24T09:55:00"}, time.time(), lee, "always_show", "On your list.", True, False,
                {"name": "always_show", "scope": "sender"})
db.try_connect = real
presses.flush()
late = next(x for x in rule_book.rows() if x["message"] == "14")
out["8. covered and leaned_on on the row: a judge's uncovered call, a call that did not say, and after a held press"] = [
    (by["14"]["covered"], by["14"]["leaned_on"]), (by["12"]["covered"], by["12"]["leaned_on"]),
    (late["press"], late["covered"], late["leaned_on"])]
db.execute("ALTER TABLE answered DROP COLUMN covered")
db.execute("ALTER TABLE answered DROP COLUMN leaned_on")
old = rule_book._from_db(["13"])[1]["13"]
out["8. a home without the coverage columns still reads the call; covered is not said"] = [
    old["call"], old["layer"], old["covered"], old["leaned_on"]]
print(json.dumps(out, default=str))
'''

REPLAY = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
os.environ.pop("ASSISTANT_REPLAY", None)
import replay, rule_book
card = {"id": "L8", "kind": "task", "title": "Made up", "source_messages": ["12"]}
before = len(rule_book._read())
calls = {"12": {"call": "show", "layer": "judge", "verdict": "task", "source": "made up", "rules": []}}
wrote = [rule_book.on_press(card, "got_it", "neutral", calls=calls), rule_book.retire("12")]
print(json.dumps({"flag": os.environ.get("ASSISTANT_REPLAY"), "wrote": wrote, "rows": len(rule_book._read()) - before,
                  "kept": any(rel == "personal/rule_book.jsonl" for rel, _ in replay.KEPT),
                  "moved": [rel for rel, _w, _n in replay.erase_list() if "rule_book" in rel]}))
'''

WANT = {
    "1. should have seen this on a held row: one row naming the holding layer": [
        {"message": "11", "call": "hide", "layer": "junk_list", "verdict": "noise", "source": "rule:77", "rules": ["rule:77"],
         "press": "should_have_seen", "meaning": "contradicts-hide", "status": "active"}],
    "1. ... with a snapshot of what was seen and the card it made": ["Big sale this week", "email", True, "task"],
    "1. (making the card did overwrite the verdict, which is why it is read first)": ["task", "owner:should_have_seen"],
    "2. a judged card's press: the judge's call and the meaning": {
        "call": "show", "layer": "judge", "verdict": "task", "source": "Pat asks which day works for the shed", "press": "not_needed",
        "meaning": "not-needed", "section": "page", "card_kind": "question", "card_area": "Personal"},
    "2. typed words and a refused press write no row": [None, None, 1],
    "3. Got it after should have seen this, and after Not needed, keeps the signal on read; both Got it rows are kept": [
        [["12", "not_needed", "not-needed", "judge"], ["11", "should_have_seen", "contradicts-hide", "junk_list"]], 4],
    "4. retire: gone from the active rule book, kept as retired, no older row comes back": [
        True, ["11"], [["12", "retired"], ["11", "active"]], False],
    "4. a newer press after a retire counts again": [["12", "always_show", "active"], ["11", "should_have_seen", "active"]],
    "5. a message the first sort hid names the first sort": ["hide", "first_sort"],
    "5. sections": ["calendar", "followups", "replies", "bills", "bills", "mailings", "mailings", "page", "page"],
    "5. by section": [2, 0],
    "7. Got it all: a row for each card; it counts only where there is no signal; a shown card's reason never picks mailings": [
        ["got_it_all", "page"], ["always_show", "needed"], 2],
    "7. a press while the database is held is written waiting and does not count yet": [
        "got_it_all", [["14", "not_needed", None, None]], 1],
    "7. once the database is free it ends with the real call and layer, and nothing waits": [
        "not_needed", "not-needed", "show", "judge", "Lee is emailing about the shed paint and its mailing list", "Shed paint", [], 0],
    "8. covered and leaned_on on the row: a judge's uncovered call, a call that did not say, and after a held press": [
        [False, "the shed thread"], [None, None], ["always_show", False, "the shed thread"]],
    "8. a home without the coverage columns still reads the call; covered is not said": ["hide", "first_sort", None, None],
}
WANT_REPLAY = {"flag": "1", "wrote": [0, False], "rows": 0, "kept": True, "moved": []}


def check(name, got, want):
    results.append((name, got == want, got, want))


def run(code, env, *args):
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", code, LIVE, *args], capture_output=True, text=True, env=env, timeout=180)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1]), r
    except (ValueError, IndexError):
        return {}, r


def main():
    tmp = tempfile.mkdtemp(prefix="rsirows-")
    try:
        env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"))
        env.pop("ASSISTANT_REPLAY", None)
        got, r = run(INSIDE, env)
        if r.returncode or not got:
            check("the checks ran", r.stderr.strip()[-2500:], "")
        for name, want in WANT.items():
            check(name, got.get(name), want)
        got, r = run(REPLAY, env)
        if r.returncode or not got:
            check("the replay check ran", r.stderr.strip()[-2500:], "")
        check("6. a replay run writes no rows (a press and a retire), and replay keeps the file", got, WANT_REPLAY)
    finally:
        _cleanup.remove(tmp)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
