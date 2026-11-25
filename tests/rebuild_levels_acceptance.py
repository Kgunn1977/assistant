r"""Acceptance (quick): the judgment rebuild's phases 4 and 5, scoring and levels per kind of work. In a scratch home with
made-up rule book rows, cards and people; the coach's Claude run and the mail service are stood in for (nothing is sent).

1. Every kind of work gets a score in Settings data, from the rule book's rows with a pick: decisions, wording, timing and
   urgency where they apply.
2. The coach proposes one change to my picks (not show or hide) for a kind of work, scored on the past rows: fixes and
   breaks, both scores; queued by a missed pick and shown as a Pick change card with Approve at level 1; Approve makes it
   the pick on the next card like it.
3. Level 2: a routine pick (Got it) I'm good at is done on its own with a note and Undo; Undo puts it back, never redoes
   it, and counts as a miss. Level 1 does nothing on its own.
4. Level 3: the same done quietly, and it lands in the one morning summary card.
5. Sending: the level words for Reply drafts name sending (and level 1 says it never sends); at level 1 nothing is sent; at
   level 2 the drafted reply goes once, recorded with its level; no other kind of work sends (guardrail B12); the
   guardrails' text says so (B1, B6, B12, A19).

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

# --- 2. the coach: one pick change, fixes and breaks, as a card at level 1, Approve ---
def ask(prompt, model):
    out["2 told"] = ["Acme Deals" in prompt, "decisions" in prompt, "show or hide" not in prompt.lower().split("kind of work:")[0][-60:]]
    return ai_steps.Result(True, json.dumps({"change": "add", "match": {"sender": "Acme Deals"},
                                             "pick": {"do": "press", "press": "drop"}, "reason": "You drop every Acme Deals mailing."}))
fresh = rows[0]
rsi_loop.on_rows([fresh])
out["2 queued"] = [(j["section"], j.get("kind")) for j in rsi_loop.jobs()]
made = rsi_loop.run(ask=ask)
c = made[0] if made else {}
r = ((c.get("extra") or {}).get("rsi") or {})
out["2 card"] = [c.get("title"), r.get("kind"), r.get("act"), r.get("fixes"), r.get("breaks"), r.get("score_live"), r.get("score_draft"),
                 [l for l in r.get("lines") or [] if l.startswith("My picks get")]]
coach.promote(r.get("id"))
iid, _ = items.upsert("live:test-acme", "t", kind="fyi", area="Bills", title="Acme Deals: weekend sale", state="new",
                      source_who="Acme Deals")
out["2 pick after promote"] = picks.of(items.card_for(iid, wait=True))

# --- 3. level 2: a routine pick done with a note and Undo; level 1 does nothing ---
iid2, _ = items.upsert("live:test-lee", "t", kind="fyi", area="Personal", title="Lee Park: the paint is in", state="new",
                       source_who="Lee Park")
n1 = levels.act("t")
lvl1 = items.card_for(iid2, wait=True)
out["3 level 1"] = [n1, lvl1["state"]]
settings_page.save({"settings": {"group": "learning", "values": {"learn_page": 2}}})
n2 = levels.act("t")
c2 = items.card_for(iid2, wait=True)
out["3 level 2"] = [n2, c2["state"], c2["status"], c2["last_press"]["press"], c2["last_press"]["happened"],
                    isinstance(c2["last_press"].get("was"), dict)]
f = presses.fields(c2, {"name": "undo"}, common.now(), lambda r: {})
items.update(iid2, "t", **{k: v for k, v in f.items()})
levels.undone(c2)
c3 = items.card_for(iid2, wait=True)
out["3 undo"] = [c3["state"], c3["last_press"]["happened"], (c3.get("extra") or {}).get("standing_skip"), levels.act("t"),
                 [a["undone"] for a in levels.actions()], rule_book.rows("page")[0].get("pick_outcome")]

# --- 4. level 3: done quietly, in the morning summary card ---
settings_page.save({"settings": {"group": "learning", "values": {"learn_page": 3}}})
iid4, _ = items.upsert("live:test-lee2", "t", kind="fyi", area="Personal", title="Lee Park: the van is back", state="new",
                       source_who="Lee Park")
n4 = levels.act("t")
c4 = items.card_for(iid4, wait=True)
made = levels.summary("t", now=now.replace(hour=7))
summ = [x for x in items.rows("source_key LIKE 'live:level-summary-%'")]
out["4 level 3"] = [n4, c4["state"], c4["status"], made, len(summ), "the van is back" in (summ[0]["detail"] if summ else ""),
                    levels.summary("t", now=now.replace(hour=8))]

# --- 5. sending ---
out["5 words"] = [levels.says("replies", 1), "send" in levels.says("replies", 2).lower(), "standing approval to send" in levels.says("replies", 2),
                  "send" in levels.says("replies", 3).lower(), "send the reply" in levels.says("page", 2)]
p = common.read_json(common.paths.PERSONAL_JSON, {}) or {}
p["send_accounts"] = ["me@example.test"]
common.write_json(common.paths.PERSONAL_JSON, p)
send.switched_on = lambda: True
send.accounts = lambda: ["me@example.test"]
con = db.connect()
con.execute("INSERT INTO messages (id, channel, account, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)"
            " VALUES (30001, 'email', 'me@example.test', 't-pat', ?, 'in', 'email:pat@example.test', '[]', 'Shed day', 'Which day works?', ?)", (now, now))
con.close()
iid5, _ = items.upsert("live:test-pat", "t", kind="question", area="Personal", title="Pat asks which day works", state="question",
                       source_who="Pat Doe", source_messages=["30001"],
                       draft={"to": ["pat@example.test"], "subject": "Re: Shed day", "body": "Thursday works for the shed.",
                              "account": "me@example.test"})
handed = []
hand = lambda m: handed.append(m) or "ok"
out["5 level 1"] = [levels.act("t", handoff=hand), len(handed)]
settings_page.save({"settings": {"group": "learning", "values": {"learn_replies": 2}}})
n5 = levels.act("t", handoff=hand)
c5 = items.card_for(iid5, wait=True)
try:
    with open(send.SENT_LOG, encoding="utf-8") as fh:
        sent = [json.loads(x) for x in fh.read().splitlines() if x.strip()]
except OSError:
    sent = []
    out["5 why not sent"] = [levels.good_at("replies", picks.of(c5)), picks.of(c5), rule_book.section(c5),
                             send.level_fit(c5, 2)[1], c5.get("reply")]
out["5 level 2"] = [n5, len(handed), (handed[0]["to"] if handed else None), c5["status"], [x.get("level") for x in sent],
                    levels.act("t", handoff=hand), len(handed)]
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
        check("2. the coach was told the misses", o["2 told"][:2], [True, True])
        check("2. a Pick change card at level 1: Approve, fixes 3, breaks 0, both scores",
              o["2 card"], ["Pick change: For cards from Acme Deals: my pick is \"Drop\"", "work", "Approve", 3, 0, "4 of 8 matched",
                            "7 of 8 matched", ["My picks get 3 more of your past answers right and 0 wrong.", "My picks get 4 of 8 of your past answers right now. With this change: 7 of 8."]])
        check("2. after Approve, my pick on the next Acme Deals card is Drop",
              {k: v for k, v in (o["2 pick after promote"] or {}).items() if k in ("do", "press", "by")}, {"do": "press", "press": "drop", "by": "rule"})
        check("3. level 1 does nothing on its own", o["3 level 1"], [0, "new"])
        lp = o["3 level 2"]
        check("3. level 2: Got it done on its own, with a note and Undo",
              [lp[0], lp[1], lp[2], lp[3], lp[4].startswith("I marked it Got it for you at level 2") and "Undo" in lp[4], lp[5]],
              [1, "done", "Done for you", "level_got_it", True, True])
        check("3. Undo puts it back, it is never redone, and it counts as a miss",
              o["3 undo"], ["new", "Taken back.", True, 0, [True], "differed"])
        check("4. level 3: done quietly, one morning summary card listing it, once a day",
              o["4 level 3"], [1, "done", "Done quietly", 1, 1, True, 0])
        w = o["5 words"]
        check("5. the level words for replies name sending; level 1 never sends; other kinds don't send",
              [w[0], w[1], w[2], w[3], w[4]],
              ["Level 1: I show my pick as the first button on each card in reply drafts and do nothing until you press it. "
               "I never send a reply on my own.", True, True, True, False])
        check("5. at level 1 nothing is sent", o["5 level 1"], [0, 0])
        check("5. at level 2 the drafted reply goes once, to the person who wrote, recorded with its level",
              o["5 level 2"], [1, 1, ["pat@example.test"], "Sent for you", [2], 0, 1])
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
