r"""Acceptance (quick): the judgment rebuild's phases 4 and 5, scoring and levels per kind of work. In a scratch home with
made-up rule book rows, cards and people; the coach's Claude run and the mail service are stood in for (nothing is sent).

1. Every kind of work gets a score in Settings data, from the rule book's rows with a pick: decisions, wording, timing and
   urgency where they apply.
2. The coach proposes one change to my picks (not show or hide) for a kind of work, scored on the past rows: fixes and
   breaks, both scores; queued by a missed pick and shown at level 2 as a Pick change card with Promote and Reject;
   Promote makes it the pick on the next card like it. At level 1 no change is proposed.
3. No learning level does a pick on a card on its own: at levels 1, 2 and 3 the card stays as it was.
4. Level 3: the morning summary card lists only changes made on its own; with none, no card.
5. Sending: no level sends: the level words for Reply drafts say so at every level, and at level 2 nothing is sent; a
   level send is refused by guardrail B12; the guardrails' text is as before (B1, B6, B12, A19).

    python tests\rebuild_levels_acceptance.py
"""
import json
import os
import subprocess
import sys
import tempfile

import _cleanup  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
results = []

ENGINE = r'''
import datetime as dt, json, os, sys, uuid
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, os.path.join(sys.argv[1], "core"))
import common, db, items, rule_book, settings_page, settings_data, grader, coach, rsi_loop, levels, picks, presses, send, ai_steps
db.init_schema(); items.ensure()
out = {}
now = common.now().replace(microsecond=0)

def row(sec, sender, what, pick, did, outcome, important=None, area="Personal", kind="fyi", n=[0]):
    n[0] += 1
    return {"id": uuid.uuid4().hex[:16], "at": (now - dt.timedelta(hours=200 - n[0])).isoformat(timespec="seconds"),
            "message": f"card:L{900 + n[0]}", "section": sec, "card": f"L{900 + n[0]}", "card_kind": kind, "card_area": area,
            "card_important": important, "call": None, "layer": "unknown", "verdict": None, "source": None, "rules": [],
            "seen": {"sender": sender, "what": what, "channel": "email"}, "press": did.get("press") or did.get("do"),
            "meaning": "neutral", "button": "-", "choice": "-", "status": "active", "pick": pick, "did": did, "pick_outcome": outcome}
GOT, DROP, LATER = {"do": "press", "press": "got_it"}, {"do": "press", "press": "drop"}, {"do": "press", "press": "later"}
rows = []
rows += [row("bills", "Acme Deals", f"Sale {i}", GOT, DROP, "differed", area="Bills") for i in range(3)]       # he drops Acme's notices
rows += [row("bills", "Garden Club", f"Dues {i}", GOT, GOT, "matched", area="Bills") for i in range(2)]
rows += [row("mailings", "Garden Club", f"News {i}", GOT, GOT, "matched") for i in range(2)]
rows += [row("bills", "Town Water", "Bill due", LATER, LATER, "matched", important=True)]
rows += [row("page", "Lee Park", f"Note {i}", GOT, GOT, "matched") for i in range(6)]
rows += [row("calendar", "Pat Doe", "Site walk", {"do": "choice", "text": "Accept"}, {"do": "choice", "text": "Accept it"}, "differed", kind="question")]
rows += [row("replies", "pat@example.test", f"Shed day {i}", {"do": "reply", "gist": "Thursday works for the shed"},
             {"do": "reply", "gist": "Thursday works for the shed, thanks"}, "matched", kind="question") for i in range(5)]
rows += [row("followups", "Sam Roe", "Quote", {"do": "press", "press": "wait_longer"}, DROP, "differed", important=True, kind="waiting")]
rule_book._append(rows)

# --- 1. a score for every kind of work in Settings data ---
d = settings_data.defs()
learn = {x["id"]: x for x in d["settings"] if x["group"] == "learning"}
out["1"] = {f: x["help"].split(". Show or hide")[0] for f, x in learn.items()}

# --- 2. the coach: one pick change, fixes and breaks; no card at level 1, a card at level 2, Promote ---
def ask(prompt, model):
    out["2 told"] = ["Acme Deals" in prompt, "decisions" in prompt, "show or hide" not in prompt.lower().split("kind of work:")[0][-60:]]
    return ai_steps.Result(True, json.dumps({"change": "add", "match": {"sender": "Acme Deals"},
                                             "pick": {"do": "press", "press": "drop"}, "reason": "You drop every Acme Deals mailing."}))
fresh = rows[0]
rsi_loop.on_rows([fresh])
out["2 queued"] = [(j["section"], j.get("kind")) for j in rsi_loop.jobs()]
out["2 level 1"] = [len(rsi_loop.run(ask=ask)), rsi_loop.jobs()]
settings_page.save({"settings": {"group": "learning", "values": {"learn_bills": 2}}})
rsi_loop.on_rows([fresh])
made = rsi_loop.run(ask=ask)
c = made[0] if made else {}
r = ((c.get("extra") or {}).get("rsi") or {})
out["2 card"] = [c.get("title"), r.get("kind"), r.get("act"), r.get("fixes"), r.get("breaks"), r.get("score_live"), r.get("score_draft"),
                 [l for l in r.get("lines") or [] if l.startswith("My picks get")]]
f = presses.fields(items.card_for(c["id"], wait=True), {"name": "rsi_promote", "proposal": r.get("id")}, common.now(), lambda x: {}) if c else {}
out["2 promote fits"] = [f.get("status"), f.get("answer")]
coach.promote(r.get("id"))
iid, _ = items.upsert("live:test-acme", "t", kind="fyi", area="Bills", title="Acme Deals: weekend sale", state="new",
                      source_who="Acme Deals")
out["2 pick after promote"] = picks.of(items.card_for(iid, wait=True))

# --- 3. no level does a pick on its own ---
iid2, _ = items.upsert("live:test-lee", "t", kind="fyi", area="Personal", title="Lee Park: the paint is in", state="new",
                       source_who="Lee Park")
got3 = []
for n in (1, 2, 3):
    settings_page.save({"settings": {"group": "learning", "values": {"learn_page": n}}})
    got3.append([levels.act("t"), items.card_for(iid2, wait=True)["state"]])
out["3 levels"] = got3

# --- 4. level 3: the morning summary lists only changes made on its own ---
out["4 level 3"] = [levels.summary("t", now=now.replace(hour=7)), len(items.rows("source_key LIKE 'live:level-summary-%'"))]

# --- 5. sending ---
out["5 words"] = [all("I never send a reply on my own at any level." in levels.says("replies", n) for n in (1, 2, 3)),
                  any("send" in levels.says("page", n).lower() for n in (1, 2, 3))]
handed = []
hand = lambda m: handed.append(m) or "ok"
settings_page.save({"settings": {"group": "learning", "values": {"learn_replies": 2}}})
out["5 level 2"] = [levels.act("t", handoff=hand), len(handed)]
v = common.rulebook().check_send({"account": "me@example.test", "to": ["pat@example.test"], "cc": [], "bcc": [], "subject": "Re: x",
                                  "body": "ok", "attach": []},
                                 {"kind": "level", "switched_on": True, "accounts": ["me@example.test"], "level": 2, "section": "page",
                                  "left": 3, "card": {"state": "question", "shelf": None,
                                                      "reply": {"via": "email", "to": ["pat@example.test"], "account": "me@example.test"}}})
v1 = common.rulebook().check_send({"account": "me@example.test", "to": ["pat@example.test"], "cc": [], "bcc": [], "subject": "Re: x",
                                   "body": "ok", "attach": []},
                                  {"kind": "level", "switched_on": True, "accounts": ["me@example.test"], "level": 1, "section": "replies",
                                   "left": 3, "card": {"state": "question", "shelf": None,
                                                       "reply": {"via": "email", "to": ["pat@example.test"], "account": "me@example.test"}}})
out["5 B12"] = [v["ok"], [b["rule"] for b in v["broken"]], v1["ok"], [b["rule"] for b in v1["broken"]]]
book = {r["id"]: r["says"] for r in json.load(open(os.path.join(sys.argv[1], "rules", "rulebook.json"), encoding="utf-8"))["rules"]}
out["5 guardrails"] = ["learning level 2 or 3" in book["B1"], "learning level 2 or 3" in book["B6"], "B12" in book, "A19" in book]
print(json.dumps(out, default=str))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="rebuild45-")
    try:
        env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"))
        env.pop("ASSISTANT_REPLAY", None)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", ENGINE, LIVE], capture_output=True, text=True, env=env, timeout=300,
                           encoding="utf-8")
        try:
            o = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            check("the engine part ran", (r.stderr or r.stdout).strip()[-3000:], "")
            return finish()
        s = o["1"]
        check("1. every kind of work has a score for my picks in Settings data",
              sorted(f for f, line in s.items() if "% right, over " in line),
              sorted(["learn_mailings", "learn_bills", "learn_page", "learn_calendar", "learn_replies", "learn_followups"]))
        check("1. the score names the ways it was counted (an important card put off is an urgency miss; most words shared is a wording match)",
              [s["learn_mailings"], s["learn_bills"], s["learn_calendar"], s["learn_followups"]],
              ["My picks: I got 100% right, over 2 answers of yours (decisions 100%)",
               "My picks: I got 50% right, over 8 answers of yours (decisions 50%, timing 100%, urgency 0%)",
               "My picks: I got 50% right, over 2 answers of yours (decisions 0%, wording 100%)",
               "My picks: I got 0% right, over 3 answers of yours (decisions 0%, timing 0%, urgency 0%)"])
        check("2. a missed pick queues the coach for that kind of work", o["2 queued"], [["bills", "work"]])
        check("2. at level 1 no change is proposed and the job is taken off the queue", o["2 level 1"], [0, []])
        check("2. the coach was told the misses", o["2 told"][:2], [True, True])
        check("2. a Pick change card at level 2: Promote, fixes 3, breaks 0, both scores",
              o["2 card"], ["Pick change: For cards from Acme Deals: my pick is \"Drop\"", "work", "Promote", 3, 0, "4 of 8 matched",
                            "7 of 8 matched", ["My picks get 3 more of your past answers right and 0 wrong.", "My picks get 4 of 8 of your past answers right now. With this change: 7 of 8."]])
        check("2. Promote is taken on a Pick change card", o["2 promote fits"], ["Promoted", "Promote"])
        check("2. after Promote, my pick on the next Acme Deals card is Drop",
              {k: v for k, v in (o["2 pick after promote"] or {}).items() if k in ("do", "press", "by")}, {"do": "press", "press": "drop", "by": "rule"})
        check("3. no level does a pick on a card on its own", o["3 levels"], [[0, "new"], [0, "new"], [0, "new"]])
        check("4. level 3: no morning summary card with no change made on its own", o["4 level 3"], [0, 0])
        check("5. the level words for replies say no level sends; other kinds don't speak of sending", o["5 words"], [True, False])
        check("5. at level 2 nothing is sent", o["5 level 2"], [0, 0])
        check("5. a level send for another kind of work, or at level 1, is refused (B12)", o["5 B12"], [False, ["B12"], False, ["B12"]])
        check("5. the guardrails say it (B1, B6, B12, A19)", o["5 guardrails"], [True, True, True, True])
    finally:
        _cleanup.remove(tmp)
    return finish()


def finish():
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if results and all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
