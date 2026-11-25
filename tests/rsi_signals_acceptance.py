r"""Acceptance: buttons that carry real meanings, and nothing hidden at the start (the RSI plan, "Cards and buttons", "Nothing
hidden at the start"). The engine's own code, run in scratch homes with made-up messages and cards. Nothing outside the scratch
folder is touched, and nothing goes to Claude.

- A card from a mailing (rule 559's own test) offers Hide mailings like this, decided by program code; its press goes through
  the real answer path, closes the card, is recorded as contradicts-show in the presses table and the rule book (section
  mailings), the grader counts it as contradicting the show, and the mailings section gets its RSI job. A card that is no
  mailing does not offer it, and a press of it there is refused.
- A card from an outside sender that needs nothing offers Keep showing these; its press records agrees and the grader counts it
  as agreeing with the show. An Approve's agrees still says nothing about show or hide.
- A choice Claude wrote with a meaning on the list keeps it, and its press records that meaning; an unknown meaning, or a bare
  string, records other. The same for a further question's choices. An add-on's choice with a meaning off the list is cleared.
- A new home starts with strictness show_more, newsletters show, notices show_each, copied_only show and short-number texts
  show, and rules 559 and 560 settle nothing there. A home made before keeps its settings byte for byte when it is brought
  forward, and its short-number texts and mailings are still settled by 560 and 559.

    python tests\rsi_signals_acceptance.py
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

# --- A. buttons, in one scratch home -----------------------------------------------------------------------------------
BUTTONS = r'''
import datetime as dt, json, os, sys, time
sys.path.insert(0, sys.argv[1])
import common, db, items, presses, answers, rule_book, grader, rsi_loop, card, teach
out = {}
os.makedirs(common.LOGS, exist_ok=True)         # as every home has: teach logs its run there
asked = []          # teach's Claude run, stood in: it proposes one made-up rule per way
teach._claude = lambda prompt, model: (asked.append(prompt.split("\n", 1)[0]) or json.dumps(
    {"rule": "Hide sale mailings from shops." if "Hide" in prompt.split("\n", 1)[0] else "Keep showing delivery notes from people.",
     "reason": "Made up for the test."}), "", 0.1, None)
db.init_schema()
items.ensure()
db.execute(answers.DDL)
ts = dt.datetime(2026, 11, 23, 8, 0)
MAILING = ('<p>This week only: 20% off garden hoses.</p><p><a href="https://shop.example.test/u?id=9">Unsubscribe</a></p>')
msgs = [(21, "email", "email:deals@shop.example.test", "Garden hose sale", MAILING),
        (22, "email", "email:pat@example.test", "Shed paint colour", "Pat asks which grey you want for the shed."),
        (23, "email", "email:lee@example.test", "Shed delivered", "Lee says the shed kit was left by the gate.")]
con = db.connect()
for mid, ch, fk, subj, body in msgs:
    con.execute("INSERT INTO messages (id, channel, account, ts, direction, from_key, subject, body, ingested_at)"
                " VALUES (?, ?, 'me@example.test', ?, 'in', ?, ?, ?, ?)", (mid, ch, ts, fk, subj, body, ts))
con.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES"
            " ('judged', 'msg:21', 'task', 'A sale the owner might want', ?), ('judged', 'msg:22', 'task', 'Pat asks a question', ?),"
            " ('judged', 'msg:23', 'task', 'Lee says the shed arrived', ?)", (ts, ts, ts))
con.close()
items.upsert("task:home::hose-sale", "p1", kind="info", area="Home", state="question", title="A sale on garden hoses", detail="d",
             asks=["Buy a hose?"], source_who="email: deals@shop.example.test", source_when=ts, source_messages=["21"])
items.upsert("task:home::shed-paint", "p1", kind="question", area="Home", state="question", title="Pat: which grey for the shed?",
             detail="d", asks=["Which grey?"], source_who="email: pat@example.test", source_when=ts, source_messages=["22"])
items.upsert("task:home::shed-here", "p1", kind="info", area="Home", state="handled", title="The shed kit was delivered", detail="d",
             asks=[], source_who="email: lee@example.test", source_when=ts, source_messages=["23"])
items.export("p1")
ids = {r["source_key"]: r["id"] for r in items.rows("1=1")}
snap = {i["id"]: i for i in common.read_json(common.ITEMS_JSON, {})["items"]}
hose, paint, here = (snap[ids[k]] for k in ("task:home::hose-sale", "task:home::shed-paint", "task:home::shed-here"))
out["A1. program code picks the switchable buttons"] = [[s["id"] for s in c.get("switches") or []] for c in (hose, paint, here)]
out["A1. ... with plain labels"] = [s["label"] for s in hose["switches"] + here["switches"]]

def press(iid, name, at):
    got = answers.act_on_answer({"id": iid, "action": "answer", "text": json.dumps({"press": {"name": name}}), "at": at, "device": "t"})
    answers.land_now()          # what it wrote is in the database before the checks read it
    return got

got = press(ids["task:home::hose-sale"], "hide_like_this", "2026-11-24T09:00:00")
after = items.rows("id=?", (ids["task:home::hose-sale"],))[0]
out["A1. Hide mailings like this closes the card and says what it did"] = [got.get("ok"), after["state"], after["status"],
                                                                          (after.get("last_press") or {}).get("happened")]
r = next(x for x in rule_book.rows() if x["message"] == "21")
out["A1. ... recorded in the rule book as contradicts-show, section mailings"] = {k: r[k] for k in ("press", "meaning", "call", "section")}
out["A1. ... the grader counts it as contradicting the show"] = list(grader.signal(r))
out["A1. ... and the Rule book in Settings says it in plain words"] = rule_book._you(r)
out["A1. ... the presses table keeps the meaning"] = [list(x) for x in db.query(
    "SELECT press, meaning FROM live_presses WHERE item_id = ?", (ids["task:home::hose-sale"],))]
out["A1. ... and the mailings section has its RSI job"] = sorted(j["section"] for j in common.read_json(rsi_loop.QUEUE, []) or [] if j.get("kind", "rules") == "rules")
refused = press(ids["task:home::shed-paint"], "hide_like_this", "2026-11-24T09:01:00")
p2 = items.rows("id=?", (ids["task:home::shed-paint"],))[0]
out["A1. a card that is no mailing refuses it and is unchanged"] = [p2["state"], (p2.get("last_press") or {}).get("ok"),
                                                                    (p2.get("last_press") or {}).get("happened"),
                                                                    any(x["message"] == "22" for x in rule_book.rows())]

rules = lambda: [[r["source_key"].split(":")[0], r["state"], (r.get("extra") or {}).get("rule", {}).get("way"), r["why"]]
                 for r in items.rows("source_key LIKE 'rule:%'")]
out["A1. at learning level 1 it offers a rule through the teach flow: a rule card waiting for Approve"] = [rules(), asked[:1]]
got = press(ids["task:home::shed-here"], "keep_showing", "2026-11-24T09:02:00")
after = items.rows("id=?", (ids["task:home::shed-here"],))[0]
out["A1. Keep showing these offers an always-show rule the same way"] = [rules()[-1][2], asked[-1], len(rules())]
r = next(x for x in rule_book.rows() if x["message"] == "23")
out["A1. Keep showing these records agrees and the grader counts it as agreeing with the show"] = [
    after["state"], r["press"], r["meaning"], list(grader.signal(r))]
out["A1. an Approve's agrees still says nothing about show or hide"] = list(grader.signal(dict(r, press="approve")))

# --- A2. Claude-written choices carry their meaning ---
entry = {"state": "question", "asks": ["Which grey?", "Paint it this week?"], "recommended_choice": {"text": "Ask Pat for a swatch", "meaning": "agrees"},
         "choices": [{"text": "Ask Pat for a swatch", "meaning": "agrees"}, {"text": "Stop showing paint offers", "meaning": "contradicts-show"},
                     {"text": "Leave it", "meaning": "likes-it"}, "Warm grey"],
         "ask_choices": [{}, {"choices": [{"text": "Yes, this week", "meaning": "agrees"}, {"text": "Not now", "meaning": "maybe"}],
                             "recommended_choice": {"text": "Not now"}}]}
ex = json.loads(items.card_extras(entry)["extra"])
out["A2. the writer's choices keep a meaning on the list, drop any other; a recommendation given as a choice still counts"] = \
    [[c["text"], c.get("meaning"), bool(c.get("recommended"))] for c in ex["choices"]] + \
    [[c["text"], c.get("meaning"), bool(c.get("recommended"))] for c in ex["questions"][0]["choices"]]
rows = []
presses.record = lambda **row: rows.append(presses._row(**row))
it = {"id": "L60", "source_key": "task:home::shed-paint", "state": "question", "title": "Pat: which grey?", "choices": ex["choices"]}
for n, c in enumerate(ex["choices"]):            # what the page sends for each: its place as id, its meaning or other
    rec = {"id": "L60", "action": "answer", "text": c["text"], "label": c["label"], "button": f"q1-{n + 1}",
           "meaning": c.get("meaning") or "other", "at": "2026-11-24T09:03:00"}
    answers._record(rec, 0, it, None, "Answered.", True, True, None)
out["A2. ... and each press records it (valid kept, unknown and bare other)"] = [[r["choice"], r["meaning"]] for r in rows]
out["A2. a choice's words still go to Claude"] = answers.kind_of(it, {"id": "L60", "action": "answer", "text": "Leave it",
                                                                      "button": "q1-3", "meaning": "other"})
out["A2. an add-on's choice with a meaning off the list is cleared"] = items.own_meanings(
    ["Red", {"label": "Green", "text": "Green", "meaning": "likes-it"}, {"label": "Blue", "text": "Blue", "meaning": "agrees"}])

# --- C. what the page is sent (publish.build, its own per-card shaping) carries all it draws from ---
con = db.connect()
con.execute("INSERT INTO messages (id, channel, account, ts, direction, from_key, subject, body, ingested_at)"
            " VALUES (24, 'email', 'me@example.test', ?, 'in', 'email:letters@club.example.test', 'Club news', ?, ?)", (ts, MAILING, ts))
con.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES ('judged', 'msg:24', 'task', 'Club news', ?)", (ts,))
con.close()
items.upsert("task:home::club-news", "p2", kind="info", area="Home", state="handled", title="The club's weekly news", detail="d",
             asks=[], source_who="email: letters@club.example.test", source_when=ts, source_messages=["24"])
items.upsert("task:home::paint-pick", "p2", kind="question", area="Home", state="question", title="Pick a grey", detail="d",
             asks=["Which grey?"], source_who="Me", source_when=ts, extra=json.loads(items.card_extras(entry)["extra"]))
prop = {"id": "made-up-1", "kind": "rule", "section": "mailings", "reason": "Made up.", "fixes": 2, "breaks": 0, "rules_before": [],
        "change": {"change": "add", "way": "show_less", "text": "Hide sale mailings from shops."},
        "score_live": "3 of 5 matched", "score_draft": "5 of 5 matched"}
items.upsert(rsi_loop.PREFIX + "made-up-1", "p2", **rsi_loop.card_fields(prop))
items.export("p2")
sys.path.insert(0, os.path.join(os.path.dirname(sys.argv[1]), "live_page"))
import publish
sent = {i.get("source_key"): i for i in publish.build(common.ITEMS_JSON)[1].values()}
rc, club, pick = sent.get(rsi_loop.PREFIX + "made-up-1") or {}, sent.get("task:home::club-news") or {}, sent.get("task:home::paint-pick") or {}
r_ = rc.get("rsi") or {}
out["C. a rule change card reaches the page with what draws Approve and Reject"] = [r_.get("id"), r_.get("kind"), r_.get("act"),
                                                                                     len(r_.get("lines") or []) >= 4, rc.get("source_key")]
out["C. a switch card reaches the page with its switches and its key"] = [club.get("switches"), club.get("source_key")]
out["C. a card's choices reach the page with their meanings"] = [[c.get("text"), c.get("meaning")] for c in pick.get("choices") or []]
rid = items.rows("source_key = ?", (rsi_loop.PREFIX + "made-up-1",))[0]["id"]
refused = []
for name in ("done", "later"):
    press(rid, name, "2026-11-24T09:0" + str(5 + len(refused)) + ":00")
    r2 = items.rows("id=?", (rid,))[0]
    refused.append([r2["state"], (r2.get("last_press") or {}).get("ok")])
out["C. Done and Snooze on a rule change card change nothing, so no proposal is left holding its section"] = refused
# level 2 with a rule change already waiting for the section: the switch offers no rule and says so
import coach
s = common.settings(); s["rsi"] = {"levels": {"mailings": 2}}; common.write_json(common.SETTINGS, s)
common.write_json(os.path.join(coach.PROPOSALS, "made-up-1.json"), dict(prop, status="open", card_pending=True, at="2026-11-24T09:00:00"))
n_rules, n_asked = len(rules()), len(asked)
press(items.rows("source_key = 'task:home::club-news'")[0]["id"], "hide_like_this", "2026-11-24T09:09:00")
c2 = items.rows("source_key = 'task:home::club-news'")[0]
out["D. level 2 with a rule change waiting: no rule offered, and the result says why"] = [
    c2["state"], (c2.get("last_press") or {}).get("happened"), len(rules()) - n_rules, len(asked) - n_asked,
    next(x for x in rule_book.rows() if x["message"] == "24")["meaning"]]
print(json.dumps(out, default=str))
'''

# --- B. homes -----------------------------------------------------------------------------------------------------------
HOME = r'''
import datetime as dt, json, os, sys
sys.path.insert(0, sys.argv[1])
import common, setup_steps
setup_steps.desktop_note = lambda: None          # never writes a CLAUDE.md beside the program under test
existing = sys.argv[2] == "existing"
if existing:                                     # a home made before: its own files and database, one setting saved
    os.makedirs(common.PERSONAL, exist_ok=True)
    common.write_json(common.PERSONAL_JSON, dict(common.STARTER, owner="Sam"))
    common.write_json(common.SETTINGS, {"alerts": {"server": "https://ntfy.sh", "topic": ""}, "filter": {"strict": "needs_me"}})
    import db
    db.init_schema()
    before = open(common.SETTINGS, "rb").read()
setup_steps.make_home()
import filters, db
f = filters.get()
out = {"settings": [f[k] for k in ("newsletters", "notices", "copied_only", "short_texts", "strict")]}
if existing:
    out["unchanged"] = open(common.SETTINGS, "rb").read() == before
ts = dt.datetime(2026, 11, 23, 8, 0)
con = db.connect()
for mid, ch, fk, subj, body in ((31, "sms", "sms:54321", None, "Your pizza is on the way. Reply STOP to end."),
                                (32, "email", "email:letters@club.example.test", "Club news", '<a href="https://club.example.test/unsubscribe">Unsubscribe</a>')):
    con.execute("INSERT INTO messages (id, channel, account, ts, direction, from_key, subject, body, ingested_at)"
                " VALUES (?, ?, 'me@example.test', ?, 'in', ?, ?, ?, ?)", (mid, ch, ts, fk, subj, body, ts))
con.close()
sys.path.insert(0, common.paths.CORE)
import judgment_payload as jp
out["settled"] = sorted([m, r] for m, r in jp.junk_rule_hits())
out["sorting line"] = any("short number" in l for l in filters.lines_for_sorting())
print(json.dumps(out))
'''

WANT = {
    "A1. program code picks the switchable buttons": [["hide_like_this"], [], ["keep_showing"]],
    "A1. ... with plain labels": ["Hide mailings like this", "Keep showing these"],
    "A1. Hide mailings like this closes the card and says what it did": [
        True, "done", "Not needed",
        'Done. I proposed a rule: "Hide sale mailings from shops." It is a card on your page; nothing changes until you approve it.'],
    "A1. at learning level 1 it offers a rule through the teach flow: a rule card waiting for Approve": [
        [["rule", "question", "show_less", 'You pressed "Hide mailings like this" on a card.']],
        ['the owner pressed "Hide mailings like this" on one card of their assistant\'s page and chose "this kind of message".']],
    "A1. Keep showing these offers an always-show rule the same way": [
        "always_show", 'the owner pressed "Keep showing these" on one card of their assistant\'s page and chose "this kind of message".', 2],
    "A1. ... recorded in the rule book as contradicts-show, section mailings": {
        "press": "hide_like_this", "meaning": "contradicts-show", "call": "show", "section": "mailings"},
    "A1. ... the grader counts it as contradicting the show": ["contradicts", "hide"],
    "A1. ... and the Rule book in Settings says it in plain words": 'You pressed "Hide mailings like this". I\'d picked "Leave it as it is".',
    "A1. ... the presses table keeps the meaning": [["hide_like_this", "contradicts-show"]],
    "A1. ... and the mailings section has its RSI job": ["mailings"],
    "A1. a card that is no mailing refuses it and is unchanged": [
        "question", False, "That button is not for this card. Nothing was changed.", False],
    "A1. Keep showing these records agrees and the grader counts it as agreeing with the show": [
        "done", "keep_showing", "agrees", ["agrees", "show"]],
    "A1. an Approve's agrees still says nothing about show or hide": ["neutral", None],
    "A2. the writer's choices keep a meaning on the list, drop any other; a recommendation given as a choice still counts": [
        ["Ask Pat for a swatch", "agrees", True], ["Stop showing paint offers", "contradicts-show", False], ["Leave it", None, False],
        ["Warm grey", None, False], ["Not now", None, True], ["Yes, this week", "agrees", False]],
    "A2. ... and each press records it (valid kept, unknown and bare other)": [
        ["Ask Pat for a swatch (recommended)", "agrees"], ["Stop showing paint offers", "contradicts-show"], ["Leave it", "other"],
        ["Warm grey", "other"]],
    "A2. a choice's words still go to Claude": "button",
    "A2. an add-on's choice with a meaning off the list is cleared": [
        "Red", {"label": "Green", "text": "Green"}, {"label": "Blue", "text": "Blue", "meaning": "agrees"}],
    "C. a rule change card reaches the page with what draws Approve and Reject": ["made-up-1", "rule", "Approve", True, "live:rsi-made-up-1"],
    "C. a switch card reaches the page with its switches and its key": [
        [{"id": "hide_like_this", "label": "Hide mailings like this"}, {"id": "keep_showing", "label": "Keep showing these"}],
        "task:home::club-news"],
    "C. a card's choices reach the page with their meanings": [
        ["Ask Pat for a swatch", "agrees"], ["Stop showing paint offers", "contradicts-show"], ["Leave it", None], ["Warm grey", None]],
    "C. Done and Snooze on a rule change card change nothing, so no proposal is left holding its section": [["question", False]] * 2,
    "D. level 2 with a rule change waiting: no rule offered, and the result says why": [
        "done", "Done. Nothing else changes. A rule change for this is already waiting on your page.", 0, 0, "contradicts-show"],
    "B. a new home: nothing hidden at the start, strictness show more": ["show", "show_each", "show", "show", "show_more"],
    "B. ... rules 559 and 560 settle nothing there, and the sorting step is told": [[], True],
    "B. a home made before: its settings as they were, file unchanged by make_home": [["never", "only_failed", "only_if_named", "hide", "needs_me"], True],
    "B. ... its short-number text and mailing still settled by 560 and 559": [[[31, 560], [32, 559]], False],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def run(code, tmp, *args):
    env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"))
    env.pop("ASSISTANT_REPLAY", None)
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", code, LIVE, *args], capture_output=True, text=True, env=env, timeout=180)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1]), ""
    except (ValueError, IndexError):
        return {}, (r.stderr.strip() or r.stdout.strip())[-2500:]


def main():
    tmp = tempfile.mkdtemp(prefix="rsisignals-")
    try:
        got, err = run(BUTTONS, os.path.join(tmp, "a"))
        if err:
            check("the button checks ran", err, "")
        new, err2 = run(HOME, os.path.join(tmp, "new"), "new")
        old, err3 = run(HOME, os.path.join(tmp, "old"), "existing")
        for e, what in ((err2, "new home"), (err3, "home made before")):
            if e:
                check(f"the {what} checks ran", e, "")
        got["B. a new home: nothing hidden at the start, strictness show more"] = new.get("settings")
        got["B. ... rules 559 and 560 settle nothing there, and the sorting step is told"] = [new.get("settled"), new.get("sorting line")]
        got["B. a home made before: its settings as they were, file unchanged by make_home"] = [old.get("settings"), old.get("unchanged")]
        got["B. ... its short-number text and mailing still settled by 560 and 559"] = [old.get("settled"), old.get("sorting line")]
        for name, want in WANT.items():
            check(name, got.get(name), want)
    finally:
        _cleanup.remove(tmp)
    for name, ok, got_, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got_!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
