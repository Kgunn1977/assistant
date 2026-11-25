r"""Acceptance: presses that carry one clear meaning (the RSI plan, "Cards and buttons"). The engine's own press code, run in a
scratch home with made-up cards; the presses table is a scratch database made with the table as it was before meanings.
Nothing outside the scratch folder is touched, and nothing goes to Claude.

- A choice button sends its id and a meaning from the fixed list: its words are read exactly as before (not a press, still a
  choice that may go to Claude), and the press record keeps the button id, the choice's words and the meaning. A meaning not on the list, or a
  choice with no id, is refused like a press with an unknown name.
- No is its own press on a rule card, a standing approval offer and a project write, and is recorded as No with its meaning;
  Done on those cards only marks them done.
- live_presses gains meaning and button columns on a table made before them, every old row filled; a press that waited in the file from
  before meanings is written with one too.

    python tests\rsi_presses_acceptance.py
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
import datetime as dt, json, sys
sys.path.insert(0, sys.argv[1])
import duckdb
import presses, answers
out = {}
when = dt.datetime(2026, 11, 24, 9, 0)
legacy = lambda r: answers._transform(card, {**r, "page_action": None})

# --- 1. a choice button: id and meaning, checked ---
card = {"id": "L501", "source_key": "live:mail-501", "state": "question", "title": "Pat asks which day works", "assistant_did": "",
        "choices": [{"label": "Tuesday", "text": "Tuesday"}], "reply": {"can_email": True, "to": ["pat@example.test"]}}
good = {"id": "L501", "action": "answer", "text": "Tuesday", "label": "Tuesday", "button": "q1-1", "meaning": "agrees"}
out["1. a choice with a meaning on the list is read as its words, as before"] = [
    presses.parse(card, good), answers.kind_of(card, good), answers._decides_for_someone(card, good, presses.parse(card, good))]
bad = dict(good, meaning="likes-it")
nobtn = {k: v for k, v in good.items() if k != "button"}
refused = []
for r in (bad, nobtn):
    p = presses.parse(card, r)
    f = presses.fields(card, p, when, legacy)
    refused.append([p["name"], answers.kind_of(card, r), f["last_press"]["ok"], f["last_press"]["happened"], sorted(set(f) - {"last_press"})])
out["1. a meaning not on the list, or no button id, is refused like an unknown press"] = refused
rows = []
presses.record = lambda **row: rows.append(presses._row(**row))
answers._record(dict(good, at="2026-11-24T09:00:00"), 0, card, None, "Answered.", True, True, None)
answers._record({"id": "L501", "action": "answer", "text": "Tuesday", "at": "2026-11-24T09:00:00"}, 0, card, None, "Answered.", True, True, None)
out["1. the press record keeps the button id and the meaning; an older page's choice is recorded neutral"] = [
    {k: r[k] for k in ("press", "button", "choice", "words", "meaning")} for r in rows]

# --- 2. No is its own press; Done only means done ---
yes_no = {"rule:7": {"rule": {"text": "Hide sale emails."}},
          "live:standing-close_info-Work": {"extra": {"offer": {"kind": "close_info", "area": "Work", "count": 5}}},
          "live:projwrite-3": {"extra": {"write": {"project": "Shed", "path": "x.md", "content": "y"}}}}
no_rec, done_rec = {"action": "answer", "text": json.dumps({"press": {"name": "no"}})}, {"action": "answer", "text": json.dumps({"press": {"name": "done"}})}
nos, dones = [], []
rows.clear()
for key, more in yes_no.items():
    card = dict({"id": "L502", "source_key": key, "state": "question", "title": "A card that asks yes or no", "assistant_did": ""}, **more)
    p = presses.parse(card, no_rec)
    f = presses.fields(card, p, when, legacy)
    nos.append([p, f.get("state"), f.get("answer"), f["last_press"]["ok"]] + ([f.get("status"), f["last_press"]["happened"]] if key.startswith("rule:") else []))
    answers._record(dict(no_rec, id="L502", at="2026-11-24T09:00:00"), 0, card, p["name"], f["last_press"]["happened"], True, False, p)
    d = presses.parse(card, done_rec)
    fd = presses.fields(card, d, when, legacy)
    dones.append([d, fd.get("state"), fd.get("status"), fd.get("answer")])
out["2. No on a rule card, an offer and a project write is the no"] = nos
out["2. ... recorded as No, with the no it was and its meaning"] = [{k: r[k] for k in ("press", "choice", "meaning")} for r in rows]
out["2. Done on those cards only marks them done"] = dones
out["2. No on a card that asks no yes or no is refused"] = presses.fields({"id": "L503", "source_key": "live:mail-503", "state": "question"},
                                                                          presses.parse({}, no_rec), when, legacy)["last_press"]["ok"]

# --- 3. the meaning column on a table from before meanings ---
old_ddl = """CREATE SEQUENCE IF NOT EXISTS seq_live_press START 1;
CREATE TABLE IF NOT EXISTS live_presses (id BIGINT PRIMARY KEY DEFAULT nextval('seq_live_press'), pressed_at TIMESTAMP NOT NULL,
  received_at TIMESTAMP NOT NULL, item_id VARCHAR NOT NULL, item_title VARCHAR NOT NULL, press VARCHAR NOT NULL, choice VARCHAR NOT NULL,
  words VARCHAR NOT NULL, device VARCHAR NOT NULL, happened VARCHAR NOT NULL, ok BOOLEAN NOT NULL, claude_ran BOOLEAN NOT NULL, secs DOUBLE NOT NULL);"""
con = duckdb.connect(sys.argv[2])
con.execute(old_ddl)
for press, choice, happened in (("got_it", "-", "Done."), ("approve", "-", "Your yes is recorded."), ("not_needed", "this", "Done."),
                                ("standing", "-", "No standing approval was made. I will keep asking each time."),
                                ("standing", "-", "Done: from the next check I will do it quietly for this."), ("no", "-", "Done. Nothing was changed."),
                                ("words", "-", "Reading your words now."), ("rule_offer", "disapprove", "No rule saved.")):
    con.execute("INSERT INTO live_presses (pressed_at, received_at, item_id, item_title, press, choice, words, device, happened, ok, claude_ran, secs)"
                " VALUES (now(), now(), 'L9', 'A made-up card', ?, ?, '-', 'test', ?, true, false, 0)", (press, choice, happened))
waited = {c: v for c, v in presses._row(pressed_at=when, received_at=when, item_id="L9", item_title="Made up", press="should_have_seen",
                                       choice="-", words="-", device="test", happened="It is on your page now.", ok=True,
                                       claude_ran=False, secs=0).items() if c not in ("meaning", "button")}       # as a press waiting from before meanings
presses._insert(con, [waited])
presses.ensure_on(con)          # a second time changes nothing
out["3. the old table has meaning and button columns, every row filled"] = con.execute(
    "SELECT press, meaning, button FROM live_presses ORDER BY id").fetchall()
out["3. no row is left without a meaning"] = con.execute("SELECT count(*) FROM live_presses WHERE meaning IS NULL").fetchone()[0]
con.close()
print(json.dumps(out, default=str))
'''

WANT = {
    "1. a choice with a meaning on the list is read as its words, as before": [None, "button", True],
    "1. a meaning not on the list, or no button id, is refused like an unknown press": [
        ["unknown", "button", False, "I do not know that button, so nothing was changed.", []]] * 2,
    "1. the press record keeps the button id and the meaning; an older page's choice is recorded neutral": [
        {"press": "choice", "button": "q1-1", "choice": "Tuesday", "words": "-", "meaning": "agrees"},
        {"press": "answer", "button": "-", "choice": "Tuesday", "words": "-", "meaning": "neutral"}],
    "2. No on a rule card, an offer and a project write is the no": [
        [{"name": "no"}, "done", "No", True, "You turned this rule down", "Got it. I didn't make the rule."],
        [{"name": "standing", "level": "no", "via": "no"}, "done", "No", True],
        [{"name": "write", "level": "no", "via": "no"}, "done", "No", True]],
    "2. ... recorded as No, with the no it was and its meaning": [
        {"press": "no", "choice": "-", "meaning": "disagrees"},
        {"press": "no", "choice": "no", "meaning": "disagrees"},
        {"press": "no", "choice": "no", "meaning": "disagrees"}],
    "2. Done on those cards only marks them done": [[{"name": "done"}, "done", "Done", None]] * 3,
    "2. No on a card that asks no yes or no is refused": False,
    "3. the old table has meaning and button columns, every row filled": [
        ["got_it", "neutral", "-"], ["approve", "agrees", "-"], ["not_needed", "not-needed", "-"], ["standing", "disagrees", "-"],
        ["standing", "agrees", "-"], ["no", "disagrees", "-"], ["words", "neutral", "-"], ["rule_offer", "disagrees", "-"],
        ["should_have_seen", "contradicts-hide", "-"]],
    "3. no row is left without a meaning": 0,
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="rsipress-")
    try:
        env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"))
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, LIVE, os.path.join(tmp, "old.duckdb")],
                           capture_output=True, text=True, env=env, timeout=120)
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
