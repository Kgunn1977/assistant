r"""Acceptance: the two guardrail exceptions the owner approved on 11/25 (the RSI plan, the owner's answers of 11/25). The engine's
own code, run in scratch homes with made-up messages, verdicts, rule book rows and rules. Nothing outside the scratch folder
is touched, and nothing goes to Claude: every Claude run is stood in for with a canned answer.

A13 as amended, "I'd hide this":
- After the judge runs in a check (think.think, the judge stood in for), a message it judged noise that no rule of the
  owner's covers gets one "I'd hide this" card with Hide things like this and Keep showing; a noise verdict his own rule
  covers (by the reason's "owner rule <n>:" or by leaned_on), a junk rule's, the first sort's, and a task make none. A bare
  core rule number in leaned_on does not count as his rule.
- Hide things like this goes through the real answer path, closes the card and offers a hide rule through the teach flow (a
  rule card waiting for Approve); its rule book row agrees with the judge's hide. Keep showing closes its card, offers no
  rule, its row contradicts the hide, and the section gets its RSI job.

A15 as amended, Level 3:
- Level 3 can be chosen in Settings. With a stand-in grader runner and coach: a draft that scores higher but breaks an
  answer the live rules matched is not promoted (closed as rejected, with why); a better draft that breaks nothing is
  promoted with no press, the loop stops at 10 rounds (the cap not reached), and no card is made.
- The promotion is in Change history with Undo; Undo, sent as the page sends it, puts the rules back as they were; it is
  refused while the rules have changed since, and a second Undo is refused.
- Level 2 still makes a rule change card and changes nothing until Promote.

    python tests\rsi_guard_acceptance.py
"""
import json
import os
import subprocess
import sys
import tempfile

import _cleanup  # noqa: E402  the scratch folder goes when the test ends
from rsi_coach_acceptance import INSIDE as COACH_INSIDE

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
results = []

# --- A. "I'd hide this" ---------------------------------------------------------------------------------------------------
NOISE = r'''
import datetime as dt, json, os, sys
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, os.path.join(sys.argv[1], "core"))
import common, db, items, presses, answers, rule_book, grader, rsi_loop, card, teach, think, limits, ai_steps, filters
import judgment_commit as jc
out = {}
os.makedirs(common.LOGS, exist_ok=True)
asked = []
teach._claude = lambda prompt, model: (asked.append(prompt.split("\n", 1)[0]) or json.dumps(
    {"rule": "Do not show me routine shipping notices.", "reason": "Made up for the test."}), "", 0.1, None)
ai_steps.agent = lambda *a, **k: (_ for _ in ()).throw(AssertionError("Claude was started"))
db.init_schema()
items.ensure()
db.execute(answers.DDL)
for stmt in jc.COVERAGE_COLUMNS:
    db.execute(stmt)
common.write_json(filters.RULES_FILE, {"rules": [{"id": 3, "text": "Hide mail from the paint shop", "way": "show_less", "on": True,
                                                  "made": "2026-11-20", "from": "made up"}], "next": 4})
now = dt.datetime.now()
# id, from, subject, verdict, source, covered, leaned_on
msgs = [(41, "email:ship@store.example.test", "Your parcel moved", "noise", "a routine shipping notice", False, "nothing on parcels"),
        (42, "email:shop@paint.example.test", "Paint in stock", "noise", "the owner hides paint shop mail", True, "owner rule 3"),
        (43, "email:shop@paint.example.test", "Paint sale", "noise", "owner rule 3: hide mail from the paint shop", True, "owner rule 3"),
        (44, "email:deals@shop.example.test", "Sale ends soon", "noise", "rule:559", None, None),
        (45, "email:news@letters.example.test", "Weekly letter", "noise", "fast: a weekly newsletter", None, None),
        (46, "email:club@kites.example.test", "Kite club minutes", "noise", "minutes of a club meeting", True, "12"),
        (47, "email:pat@example.test", "Shed day", "task", "Pat asks which day works", True, "a goal"),
        # Settings choices (this made-up home: mailings hidden, kept mailings shown each, the filter balanced)
        (48, "email:news@weekly.example.test", "The weekly digest", "noise", "a newsletter, and mailings are set to hide", True, "setting newsletters"),
        (49, "email:news@monthly.example.test", "Monthly news", "noise", "a newsletter with an unsubscribe link", True, "559"),
        (50, "email:bulletin@garden.example.test", "Garden bulletin", "noise", "a garden bulletin", True, "setting kept_mailings")]
con = db.connect()
for mid, fk, subj, *_ in msgs:
    con.execute("INSERT INTO messages (id, channel, account, ts, direction, from_key, subject, body, ingested_at)"
                " VALUES (?, 'email', 'me@example.test', ?, 'in', ?, ?, ?, ?)", (mid, now, fk, subj, subj + ", made up.", now))
con.close()


def judge():            # the judge, stood in for: the verdicts as judgment_commit writes them
    c = db.connect()
    for mid, fk, subj, verdict, source, cov, leaned in msgs:
        c.execute("INSERT INTO answered (domain, key, verdict, source, answered_at, covered, leaned_on) VALUES ('judged', ?, ?, ?, ?, ?, ?)",
                  (f"msg:{mid}", verdict, source, dt.datetime.now(), cov, leaned))
    c.close()
    return True, "judged 10"


think.judge = judge
real_write = think.write_items
think.write_items = lambda *a, **k: (True, "nothing written here")
limits.begin("made-up-pass")
t = think.think("made-up-pass")
items.export("made-up-pass")
snap = {i.get("source_key"): i for i in common.read_json(common.ITEMS_JSON, {})["items"]}
made = sorted(k for k in snap if k.startswith("live:wouldhide-"))
out["A1. the check made an I'd hide this card only for the judge's noise no rule of his covers"] = [t["ok"], made]
c41 = snap.get("live:wouldhide-41") or {}
out["A1. one line, needs nothing, both buttons, no teaching menu"] = [
    c41.get("header"), c41.get("needs"), c41.get("switches"), c41.get("teach"), c41.get("source_messages")]
out["A1. a done card shows no buttons"] = card.switches(dict(c41, state="done"))


def press(iid, name):
    got = answers.act_on_answer({"id": iid, "action": "answer", "text": json.dumps({"press": {"name": name}}),
                                 "at": dt.datetime.now().isoformat(timespec="seconds"), "device": "t"})
    answers.land_now()
    return got


got = press(c41["id"], "hide_like_this")
after = items.rows("id=?", (c41["id"],))[0]
rules = [[r["source_key"].split(":")[0], r["state"], (r.get("extra") or {}).get("rule", {}).get("way")]
         for r in items.rows("source_key LIKE 'rule:%'")]
out["A2. Hide things like this closes the card and offers a hide rule through the teach flow, waiting for Approve"] = [
    got.get("ok"), after["state"], after["status"], (after.get("last_press") or {}).get("happened"), rules, asked,
    [r["text"] for r in filters.rules()]]
out["A2. ... its history names the button as the card showed it"] = (after.get("assistant_did") or "").split("\n")[-1][:34]
r41 = next(x for x in rule_book.rows() if x["message"] == "41")
out["A2. ... its rule book row agrees with the judge's hide"] = [r41["press"], r41["call"], r41["layer"], list(grader.signal(r41))]
common.write_json(rsi_loop.QUEUE, [])
c46 = snap.get("live:wouldhide-46") or {}
got = press(c46["id"], "keep_showing")
after = items.rows("id=?", (c46["id"],))[0]
r46 = next(x for x in rule_book.rows() if x["message"] == "46")
out["A3. Keep showing closes the card, offers no rule, contradicts the hide and queues its RSI job"] = [
    got.get("ok"), after["state"], len(items.rows("source_key LIKE 'rule:%'")), len(asked), r46["press"], list(grader.signal(r46)),
    [j["section"] for j in rsi_loop.jobs()]]
out["A4. a second check makes no second card for the same message"] = sorted(
    r["source_key"] for r in items.rows("source_key LIKE 'live:wouldhide-%'"))
import wouldhide
out["A4. ... and makes none again"] = wouldhide.cards([41, 46], "again")

# B. Settings choices cover a noise call too (approved 11/25): the judge is told each setting by its tag
lines = filters.lines_for_sorting()
out["B1. a newsletter a Settings choice hides makes no card; noise no rule or setting covers makes one"] = [
    "live:wouldhide-48" in made, "live:wouldhide-49" in made, "live:wouldhide-41" in made, "live:wouldhide-50" in made,
    "setting strict" in lines[0], any(x.startswith("[setting strict] How strict: balanced") for x in lines)]
out["B1. ... a setting covers only at a value that hides; only what needs me covers every noise call"] = [
    wouldhide.setting_covers("x", "setting strict", {"strict": "show_more"}), wouldhide.setting_covers("x", "setting strict", {"strict": "balanced"}),
    wouldhide.setting_covers("x", "a guess", {"strict": "needs_me"}), wouldhide.setting_covers("x", "559", {"strict": "show_more", "newsletters": "show"}),
    wouldhide.setting_covers("x", "rule 560", {"strict": "show_more", "short_texts": "hide"})]
c50 = items.rows("source_key=?", ("live:wouldhide-50",))[0]

# C. the card writer, a rebuild and a join leave an "I'd hide this" card alone (as they do a rule change card)
import rebuild
other, _ = items.upsert("task:personal::made-up-other", "made-up-pass", title="Made-up other card", kind="task", area="Personal",
                        state="question", source_messages=[47])


def row50():
    return json.dumps(db.query("SELECT * FROM live_items WHERE id = ?", (c50["id"],)), default=str)


still = row50()
answers.start_hidden = lambda *a, **k: False       # the rebuild's own writer is not started here
rebuild.start()
owed = (common.read_json(common.THINK_STATE, {}) or {}).get("rewrite_items") or []
reset = rebuild.reset([c50["id"]])
rebuild.put_back()
after_rebuild = row50()
writer = []


def writer_stub(prompt, model, expect, *a, **k):    # the pass's card writer: what it was shown, then a failed run
    writer.append(common.read_json(os.path.join(common.paths.STATE, "live_items_payload.json"), {}))
    return ai_steps.Result(False, why="made-up stop")


if not os.path.exists(common.paths.GOALS):
    os.makedirs(os.path.dirname(common.paths.GOALS), exist_ok=True)
    with open(common.paths.GOALS, "w", encoding="utf-8") as f:
        f.write("Made-up goals.")
keep_agent = ai_steps.agent
ai_steps.agent = writer_stub
real_write([c50["id"], other], [], forced=[c50["id"], other])
ai_steps.agent = keep_agent
joined = items.join(other, c50["id"], "made-up-pass") or items.join(c50["id"], other, "made-up-pass")
out["C. the card writer, a rebuild and a join leave an I'd hide this card as it was"] = [
    after_rebuild == still, c50["id"] in owed, reset[0], bool(writer), any(c50["id"] in json.dumps(w) for w in writer),
    joined, row50() == still]

# D. the setting that hides cards needing nothing never hides an "I'd hide this" card
import held
st = common.settings()
st["filter"] = dict(st.get("filter") or {}, nothing_needed="hide")
common.write_json(common.SETTINGS, st)
plain, _ = items.upsert("task:personal::made-up-fyi", "made-up-pass", title="Made-up note that needs nothing", kind="fyi",
                        area="Personal", state="handled", source_messages=[47])
items.export("made-up-pass")
feed = {i["id"] for i in common.read_json(common.ITEMS_JSON, {})["items"]}
kept_out = {r["key"] for r in held.hidden_cards(db, now - dt.timedelta(days=1))}
out["D. with cards needing nothing hidden, the I'd hide this card still shows and is not on the Hidden list"] = [
    c50["id"] in feed, f"card-{c50['id']}" in kept_out, plain in feed, f"card-{plain}" in kept_out]
st["filter"]["nothing_needed"] = "line"
common.write_json(common.SETTINGS, st)


# E. I should have seen this on the message's row under Hidden acts on its "I'd hide this" card, never a second one
def held_press(mid):
    got = answers.act_on_answer({"id": f"held-{mid}", "action": "answer", "text": json.dumps({"press": {"name": "should_have_seen"}}),
                                 "at": dt.datetime.now().isoformat(timespec="seconds"), "device": "t"})
    answers.land_now()
    return got


def cards_for(mid):
    return sorted(r["source_key"] for r in items.rows("source_messages LIKE ?", (f'%"{mid}"%',)))


rows_before = {r["key"] for r in held.rows_for(db, now - dt.timedelta(days=1)) if not r["shown"]}
g50 = held_press(50)
a50 = items.rows("id=?", (c50["id"],))[0]
g41 = held_press(41)                # its card was closed by Hide things like this: it is opened again
a41 = items.rows("id=?", (c41["id"],))[0]
common.write_json(held.QUEUE, [46])     # the queued path, as when the press came during a check; its card was closed too
held.net("made-up-pass")
a46 = items.rows("id=?", (c46["id"],))[0]
rows_after = {r["key"]: r["shown"] for r in held.rows_for(db, now - dt.timedelta(days=1))}
r50 = [x for x in rule_book.rows() if x["message"] == "50"]
out["E. the Hidden row's press acts on the existing card: one card per message, open, its row in the rule book"] = [
    "held-50" in rows_before, g50.get("result"), [i["id"] for i in g50.get("items") or []] == [c50["id"]], cards_for(50),
    a50["state"], a50["status"], cards_for(41), a41["state"], a41["status"], g41.get("result"), cards_for(46), a46["state"],
    rows_after.get("held-50"), [(x["press"], x["call"]) for x in r50]]

# F. a replay day makes no "I'd hide this" card
con = db.connect()
con.execute("INSERT INTO messages (id, channel, account, ts, direction, from_key, subject, body, ingested_at)"
            " VALUES (51, 'email', 'me@example.test', ?, 'in', 'email:tips@cook.example.test', 'Cooking tips', 'Made up.', ?)", (now, now))
con.execute("INSERT INTO answered (domain, key, verdict, source, answered_at, covered, leaned_on)"
            " VALUES ('judged', 'msg:51', 'noise', 'cooking tips', ?, false, 'a guess')", (dt.datetime.now(),))
con.close()
os.environ["ASSISTANT_REPLAY"] = "1"
on_replay = wouldhide.cards([51], "replay-pass")
none_made = cards_for(51)
del os.environ["ASSISTANT_REPLAY"]
out["F. a replay day makes no I'd hide this card; a real day makes it"] = [on_replay, none_made, wouldhide.cards([51], "real-pass"), cards_for(51)]

# G. the Level 3 Undo confirm speaks of the rules, not files
page = open(os.path.join(os.path.dirname(sys.argv[1]), "live_page", "page.html"), encoding="utf-8").read()
out["G. the Undo confirm for a change made on its own speaks of the rules"] = [
    "Your rules go back as they were before I changed them on my own." in page,
    "x.part === 'rsi' ? 'Your rules go back" in page]
print(json.dumps(out, default=str))
'''

# --- C. Level 3 ------------------------------------------------------------------------------------------------------------
LEVEL3 = COACH_INSIDE.split("\nasked = []")[0] + r'''
import time
import answers, coach, rsi_loop, changes_feed, convo, settings_data
claude = []


def boom(*a, **k):
    claude.append(str(a)[:80])
    raise AssertionError("Claude was started")


ai_steps.own_call = ai_steps.agent = convo.run = boom
st = common.settings()
st["rsi"] = dict(st.get("rsi") or {}, daily_runs=500)        # the cap far off: the loop must stop at its own 10 rounds
common.write_json(common.SETTINGS, st)
common.write_json(rsi_loop.QUEUE, [])
BREAK = "Show shed and parcel mail but hide paint colour notes"
VERDICTS = {"21": "noise", "22": "task", "23": "noise", "28": "noise"}
runs = []


def runner(prompt, model, expect, payload):
    """The grader's layer runs, stood in for: the live rules hide 23 and 28; the add rule shows 28; BREAK shows 23 and 28
    but hides 22."""
    got = json.load(open(payload, encoding="utf-8"))
    ids = sorted(str(m["id"]) for m in got["messages"])
    runs.append(1)
    if "says" in got["messages"][0]:
        common.write_json(expect, {"nothing": []})
    else:
        v = dict(VERDICTS)
        if ADD in prompt:
            v["28"] = "task"
        if BREAK in prompt:
            v.update({"23": "task", "28": "task", "22": "noise"})
        common.write_json(expect, {"payload": payload, "verdicts": [
            {"id": int(i), "disposition": v.get(i, "task"), "reason": f"made-up reason for {i}"} for i in ids]})
    return type("R", (), {"ok": True, "why": ""})()


asked = []


def coach_answers(seq):
    def ask(prompt, model):
        asked.append(prompt)
        n = len(asked)
        text = seq[n - 1] if n <= len(seq) else json.dumps(
            {"change": "add", "text": f"Show made-up mail about garden topic {n}", "way": "always_show", "reason": "A made-up try"})
        return ai_steps.Result(True, text)
    return ask


said = settings_page.save({"settings": {"group": "learning", "values": {"learn_page": 3}}})
out["C1. Level 3 can be chosen in Settings"] = [said[0], settings_page.learning_levels()["page"],
                                                 [c.get("disabled") for c in settings_data.learning({"learn_page": 3})[0]["choices"]]]
before = [(r["id"], r["text"]) for r in filters.rules()]
rsi_loop.queue("page")
made = rsi_loop.run(runner=runner, ask=coach_answers([
    json.dumps({"change": "add", "text": BREAK, "way": "always_show", "reason": "Fixes two, breaks one"}),
    json.dumps({"change": "add", "text": ADD, "way": "always_show", "reason": "He pressed should have seen on shed mail"})]))
props = sorted(rsi_loop._proposals("page"), key=lambda p: p["at"] + p["id"])
brk = next(p for p in props if (p.get("change") or {}).get("text") == BREAK)
good = next(p for p in props if (p.get("change") or {}).get("text") == ADD)
out["C2. a draft that scores higher but breaks a passing answer is not promoted"] = [
    brk["fixes"], brk["breaks"], brk["score_live"], brk["score_draft"], brk["status"], brk.get("rejected_reason")]
out["C2. a better draft that breaks nothing is promoted with no press, and no card is made"] = [
    good["fixes"], good["breaks"], good["score_live"], good["score_draft"], good["status"], good.get("by"),
    [(r["id"], r["text"]) for r in filters.rules()], made, items.rows("source_key LIKE 'live:rsi-%'")]
log = open(rsi_loop.LOG, encoding="utf-8").read().splitlines()
out["C2. the loop stopped at 10 rounds, the cap not reached, the job done"] = [
    len(asked), grader.at_cap(), bool(log) and "level 3 stopped after 10 rounds" in log[-1], rsi_loop.jobs(),
    sorted(p["status"] for p in props).count("rejected"), claude]
doc = changes_feed.doc() or {}
row = next((r for r in doc.get("list") or [] if str(r.get("id")).startswith("rsi-")), {})
out["C3. it is in Change history with Undo"] = [row.get("status"), row.get("words"), row.get("part_name"), bool(row.get("what"))]


def undo(cid):
    return answers.act_on_answer({"id": f"change-undo:{cid}:{int(time.time() * 1000)}", "action": "answer", "label": "Undo change",
                                  "text": json.dumps({"press": {"name": "undo_change", "change": cid}}),
                                  "at": common.now().isoformat(timespec="seconds"), "device": "test"})


kept = common.read_json(filters.RULES_FILE, {})
filters.add_rule("Hide made-up mail from the chess club", "show_less", source="made up")
refused = undo(row.get("id"))
common.write_json(filters.RULES_FILE, kept)
first = undo(row.get("id"))
again = undo(row.get("id"))
doc = changes_feed.doc() or {}
row2 = next((r for r in doc.get("list") or [] if r.get("id") == row.get("id")), {})
out["C3. Undo is refused while the rules changed since; then it puts the rules back; a second Undo is refused"] = [
    refused.get("ok"), refused.get("error"), first.get("ok"), first.get("result"), [(r["id"], r["text"]) for r in filters.rules()] == before,
    row2.get("status"), again.get("ok"), again.get("error"), (common.read_json(filters.RULES_FILE, {}) or {}).get("next", 0) > 4]

# D. Level 2 still waits for Promote
settings_page.save({"settings": {"group": "learning", "values": {"learn_page": 2}}})
asked.clear()
rsi_loop.queue("page")
made = rsi_loop.run(runner=runner, ask=coach_answers([json.dumps(
    {"change": "add", "text": "Show every message about the shed and its paint", "way": "always_show", "reason": "A made-up reason"})]))
out["D. Level 2 makes a rule change card and changes nothing until Promote"] = [
    len(made), (made[0] if made else {}).get("asks"), [(r["id"], r["text"]) for r in filters.rules()] == before, len(asked)]

# E. at Level 3 the daily cap stops the loop mid-way; the job keeps its rounds and the next day goes on to 10 in all
coach.reject(rsi_loop.open_card("page"), "A made-up rejection")
settings_page.save({"settings": {"group": "learning", "values": {"learn_page": 3}}})
st = common.settings(); st["rsi"] = dict(st.get("rsi") or {}, daily_runs=grader.runs_today() + 4); common.write_json(common.SETTINGS, st)
asked.clear()
rsi_loop.queue("page")
rsi_loop.run(runner=runner, ask=coach_answers([]))
used = (rsi_loop.jobs() or [{}])[0].get("rounds")
first = len(asked)
st = common.settings(); st["rsi"] = dict(st.get("rsi") or {}, daily_runs=500); common.write_json(common.SETTINGS, st)
rsi_loop.run(runner=runner, ask=coach_answers([]))
log = open(rsi_loop.LOG, encoding="utf-8").read().splitlines()
out["E. the cap stops it mid-way; the next run goes on to 10 rounds in all"] = [
    isinstance(used, int) and 0 < used < 10, isinstance(used, int) and len(asked) - first == 10 - used, rsi_loop.jobs(),
    "level 3 stopped after 10 rounds" in log[-1]]
print(json.dumps(out, default=str))
'''

WANT = {
    "A1. the check made an I'd hide this card only for the judge's noise no rule of his covers": [
        True, ["live:wouldhide-41", "live:wouldhide-46", "live:wouldhide-50"]],
    "A1. one line, needs nothing, both buttons, no teaching menu": [
        "I'd hide this: ship@store.example.test: Your parcel moved", "nothing",
        [{"id": "hide_like_this", "label": "Hide things like this"}, {"id": "keep_showing", "label": "Keep showing"}], [], ["41"]],
    "A1. a done card shows no buttons": [],
    "A2. Hide things like this closes the card and offers a hide rule through the teach flow, waiting for Approve": [
        True, "done", "Not needed",
        'Done. I proposed a rule: "Do not show me routine shipping notices." It is a card on your page; nothing changes until you approve it.',
        [["rule", "question", "show_less"]],
        ['the owner pressed "Hide things like this" on one card of their assistant\'s page and chose "this kind of message".'],
        ["Hide mail from the paint shop"]],
    "A2. ... its history names the button as the card showed it": "You pressed Hide things like this ",
    "A2. ... its rule book row agrees with the judge's hide": ["hide_like_this", "hide", "judge", ["agrees", "hide"]],
    "A3. Keep showing closes the card, offers no rule, contradicts the hide and queues its RSI job": [
        True, "done", 1, 1, "keep_showing", ["contradicts", "show"], ["page"]],
    "A4. a second check makes no second card for the same message": ["live:wouldhide-41", "live:wouldhide-46", "live:wouldhide-50"],
    "A4. ... and makes none again": 0,
    "B1. a newsletter a Settings choice hides makes no card; noise no rule or setting covers makes one": [
        False, False, True, True, True, True],
    "B1. ... a setting covers only at a value that hides; only what needs me covers every noise call": [False, True, True, False, True],
    "C. the card writer, a rebuild and a join leave an I'd hide this card as it was": [True, False, 0, True, False, False, True],
    "D. with cards needing nothing hidden, the I'd hide this card still shows and is not on the Hidden list": [True, False, False, True],
    "E. the Hidden row's press acts on the existing card: one card per message, open, its row in the rule book": [
        True, "It is on your page now.", True, ["live:wouldhide-50"], "handled", "Shown at your asking",
        ["live:wouldhide-41"], "handled", "Shown at your asking", "It is on your page now.", ["live:wouldhide-46"], "handled",
        True, [["should_have_seen", "hide"]]],
    "F. a replay day makes no I'd hide this card; a real day makes it": [0, [], 1, ["live:wouldhide-51"]],
    "G. the Undo confirm for a change made on its own speaks of the rules": [True, True],
    "C1. Level 3 can be chosen in Settings": [True, 3, [None, None, None]],
    "C2. a draft that scores higher but breaks a passing answer is not promoted": [
        2, 1, "3 of 5 matched", "4 of 5 matched", "rejected",
        "Not made on its own: it breaks 1 of your answers the rules now match"],
    "C2. a better draft that breaks nothing is promoted with no press, and no card is made": [
        1, 0, "3 of 5 matched", "4 of 5 matched", "promoted", "level 3",
        [[3, "Hide mail from the paint shop"], [4, "Show every message about the shed paint"]], [], []],
    "C2. the loop stopped at 10 rounds, the cap not reached, the job done": [10, False, True, [], 9, []],
    "C3. it is in Change history with Undo": [
        "learned", "I changed this myself: Add a rule (always show): \"Show every message about the shed paint\"",
        "your rules (changed on its own at learning level 3)", True],
    "C3. Undo is refused while the rules changed since; then it puts the rules back; a second Undo is refused": [
        False, "Not undone: your rules changed after it was made (a later change, or your own edit). Undo the later change first, "
               "or change your rules in Settings. Nothing was changed.",
        True, "Undone: your rules are back as they were before this change.", True, "undone",
        False, "Not undone: it was already undone. Nothing was changed.", True],
    "D. Level 2 makes a rule change card and changes nothing until Promote": [1, ["Promote this rule change?"], True, 1],
    "E. the cap stops it mid-way; the next run goes on to 10 rounds in all": [True, True, [], True],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def run(code, tmp, *args):
    env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"), PYTHONPATH=HERE)
    env.pop("ASSISTANT_REPLAY", None)
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", code, LIVE, *args], capture_output=True, text=True, env=env, timeout=300)
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        got = {}
    if r.returncode or not got:
        check("the checks ran", r.stderr.strip()[-2500:], "")
    return got


def main():
    got = {}
    for name, code in (("noise", NOISE), ("level3", LEVEL3)):
        tmp = tempfile.mkdtemp(prefix=f"rsiguard-{name}-")
        try:
            got.update(run(code, tmp, "-"))
        finally:
            _cleanup.remove(tmp)
    if os.environ.get("RSI_GUARD_SHOW"):
        print(json.dumps(got, indent=1))
    for name, want in WANT.items():
        check(name, got.get(name), want)
    for name, ok, g, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {g!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
