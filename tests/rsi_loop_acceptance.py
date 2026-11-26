r"""Acceptance: the RSI loop (the RSI plan, "Running and cost", "The four parts" 4, "Cards and buttons"). The engine's own
presses, queue, runner and rule change card in a scratch home with the grader test's made-up messages, verdicts, rule book
rows and rules. Nothing goes to Claude: every way the engine starts Claude is replaced by a recorder that must stay empty,
and the grader's and coach's runs are stood in for with canned answers.

- A press whose rule book row contradicts the call queues one job for its section; a neutral press queues none; the press
  itself returns without running Claude, and a second miss in a section with a job waiting adds none.
- The runner: a Level 1 job makes no card; a Level 2 job makes one rule change card with the one change, its reason,
  "Fixes N of your past corrections, breaks M" and both scores; a miss in a section whose card is open queues nothing.
- Promote changes his live rules through coach.promote and closes the card; Reject records the rejection with his typed
  words and closes the card; a setting proposal's Apply changes only that one setting; a setting proposal said in words
  only gets no card and does not hold its section.
- At the RSI daily cap the runner runs nothing and the job waits.
- The listener: after an answer is handled its RSI worker runs the queue on a thread of its own and sends a made card to
  the page.

    python tests\rsi_loop_acceptance.py
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
SETUP = COACH_INSIDE.split("\nasked = []")[0]       # the coach test's made-up home and its layer stand-in, used as they are

INSIDE = SETUP + r'''
import threading, time
import answers, coach, rsi_loop, convo, presses

claude = []                     # every start of Claude the engine could make: must stay empty


def boom(*a, **k):
    claude.append(str(a)[:80])
    raise AssertionError("Claude was started")


ai_steps.own_call = ai_steps.agent = convo.run = boom
_queue = rsi_loop.queue         # this test is about show or hide: the coach for my picks (kind "work") has its own test
rsi_loop.queue = lambda section, messages=(), kind="rules": False if kind == "work" else _queue(section, messages)
asked = []


def answer(text):
    def ask(prompt, model):
        asked.append(prompt)
        return ai_steps.Result(True, text)
    return ask


ADD_ONE = json.dumps({"change": "add", "text": ADD, "way": "always_show", "reason": "He pressed should have seen on shed mail"})
EDIT_ONE = json.dumps({"change": "edit", "rule": 3, "text": EDIT, "way": "show_less", "reason": "Keep shed mail from the shop"})
WORDS_ONLY = json.dumps({"change": "setting", "what": "Show newsletters, so sale mail is read", "reason": "He wanted the sale mail"})
SET_ONE = json.dumps({"change": "setting", "what": "Show newsletters, so sale mail is read",
                      "set": {"setting": "newsletters", "to": "show"}, "reason": "He wanted the sale mail"})
out["setup queued"] = [j["section"] for j in rsi_loop.jobs()]        # the grader's made-up presses held misses
common.write_json(rsi_loop.QUEUE, [])


def card_from(mid, title, tag=""):
    iid, _ = items.upsert(f"task:personal::made-up-{mid}{tag}", "made-up-pass", title=title, kind="task", area="Personal",
                          state="question", source_messages=[mid])
    answers._patch_snapshot([items.card_for(iid, wait=True)])      # on the page, as a pass leaves it
    return iid


def press(iid, p):
    return answers.act_on_answer({"id": iid, "action": "answer", "text": json.dumps({"press": p}),
                                  "at": common.now().isoformat(timespec="seconds"), "device": "test"})


def proposal_of(card):
    """The proposal a rule change card was made for."""
    return next(p for p in rsi_loop._proposals() if p["id"] == ((card or {}).get("rsi") or {}).get("id"))


def proposals():
    return sorted((p["id"], p["section"], p["status"]) for p in rsi_loop._proposals())


def mailings_miss():
    rule_book.on_press({"id": "L25", "kind": "task", "area": "Personal", "title": "Sale ends soon"}, "should_have_seen",
                       "contradicts-hide", calls={"25": {"call": "hide", "layer": "setting", "verdict": "noise",
                                                         "source": "rule:559", "rules": ["rule:559"],
                                                         "seen": {"sender": "deals@shop.example.test", "what": "Sale ends soon",
                                                                  "channel": "email"}}})


# 1. a neutral press queues nothing; a contradicting press queues one job, and starts no Claude
r0 = press(card_from(24, "Thanks from Sam"), {"name": "done"})
neutral = rsi_loop.jobs()
r1 = press(card_from(22, "Paint colours"), {"name": "not_needed", "scope": "this"})
one = [(j["section"], j["messages"]) for j in rsi_loop.jobs()]
r2 = press(card_from(21, "Shed day options"), {"name": "not_needed", "scope": "this"})
out["1. a neutral press queues none, a contradicting one queues one job, a second miss adds none"] = [
    r0["ok"], neutral, r1["ok"], one, [(j["section"], j["messages"]) for j in rsi_loop.jobs()]]
out["1. the press itself ran no Claude and coached nothing"] = [
    claude, r1["thought"], r2["thought"], len(asked), os.path.exists(coach.PROPOSALS)]

# 2. Level 1 (the default): no change is proposed (he teaches on the cards); the job is taken off the queue.
made = rsi_loop.run(runner=stub, ask=answer(ADD_ONE))
out["2. a level 1 job: no rule change card, the queue emptied"] = [
    len(made), ((made[0] if made else {}).get("rsi") or {}).get("act"), rsi_loop.jobs()]
if made:
    coach.reject(proposal_of(made[0])["id"], "Made-up test: cleared")
asked.clear()

# 3. Level 2: one rule change card with the change, its reason, fixes and breaks, and both scores
said = settings_page.save({"settings": {"group": "learning", "values": {"learn_page": 2, "learn_mailings": 2}}})
press(card_from(23, "Your parcel moved"), {"name": "always_show", "scope": "this"})
queued = [j["section"] for j in rsi_loop.jobs()]
made = rsi_loop.run(runner=stub, ask=answer(ADD_ONE))
c1 = made[0] if made else {}
p1 = proposal_of(c1)
out["3. a level 2 job: one rule change card"] = [
    said[0], queued, len(made), len(asked), c1.get("source_key") == "live:rsi-" + p1["id"], c1.get("state"),
    c1.get("title"), c1.get("asks"), c1.get("source_messages"), c1.get("teach")]
out["3. the card says the change, its reason, fixes and breaks, and both scores"] = (c1.get("rsi") or {}).get("lines")
out["3. its numbers are the proposal's"] = [
    (c1.get("rsi") or {}).get("fixes") == p1["fixes"], (c1.get("rsi") or {}).get("breaks") == p1["breaks"],
    (c1.get("rsi") or {}).get("score_live") == p1["score_live"], (c1.get("rsi") or {}).get("score_draft") == p1["score_draft"],
    p1["complete"], rsi_loop.open_card("page")["id"] == p1["id"]]

# 4. a second miss in that section while its card is open queues nothing
press(card_from(23, "Your parcel moved again", "-b"), {"name": "always_show", "scope": "this"})
out["4. a miss in a section with an open card queues nothing"] = [rsi_loop.jobs(), rsi_loop.queue("page")]

# 5. Promote: his live rules get the change through coach.promote; the card closes
wrong = press(c1["id"], {"name": "rsi_promote", "proposal": "not-this-one"})
got = press(c1["id"], {"name": "rsi_promote", "proposal": p1["id"]})
card = got["items"][0]
out["5. promote: live rules changed, the card closed, the proposal promoted"] = [
    wrong["result"], got["result"], card["state"], card["status"],
    [(r["id"], r["text"], r["way"]) for r in filters.rules()],
    common.read_json(p1["file"], {})["status"], rsi_loop.open_card("page"), claude]
undo = answers.act_on_answer({"id": c1["id"], "action": "reopen", "text": "", "page_action": "reopen", "label": "Undo",
                              "at": common.now().isoformat(timespec="seconds")})
out["5. Undo after Promote takes nothing back"] = [undo["result"], undo["items"][0]["state"], len(filters.rules())]

# 6. Reject: the rejection recorded with his words, the card closed. A press that agrees with the call queues nothing; the
# job is queued by hand, and the layer stand-in still hides message 21, so the new live grade has a miss to coach on.
agree = press(card_from(21, "Shed day options", "-b"), {"name": "always_show", "scope": "this"})
out["6. a press that agrees queues nothing"] = [agree["ok"], rsi_loop.jobs()]
rsi_loop.queue("page")
made = rsi_loop.run(runner=stub, ask=answer(EDIT_ONE))
p2 = proposal_of(made[0])
before = filters.rules()
got = press(made[0]["id"], {"name": "rsi_reject", "proposal": p2["id"], "words": "The shop sends more than paint news"})
rec = common.read_json(common.read_json(p2["file"], {})["rejected"], {})
out["6. reject: recorded with his words, nothing changed, the card closed"] = [
    len(made), got["result"], got["items"][0]["state"], got["items"][0]["status"], common.read_json(p2["file"], {})["status"],
    rec.get("kind"), rec.get("reason"), filters.rules() == before, rsi_loop.open_card("page"),
    rsi_loop.reason_of({"name": "rsi_reject"}), rsi_loop.reason_of({"words": "no"})]

# 6b. a Promote that reached no listener (landed later from its file) changes nothing; one his changed rules refuse closes
# the card with why, and the section is free again
rsi_loop.queue("page")
made = rsi_loop.run(runner=stub, ask=answer(json.dumps({"change": "add", "text": "Show every note about the garden fence",
                                                         "way": "always_show", "reason": "A made-up reason"})))
c5 = made[0]
p5 = proposal_of(c5)
answers._save({"id": c5["id"], "action": "answer", "text": json.dumps({"press": {"name": "rsi_promote", "proposal": p5["id"]}}),
               "at": common.now().isoformat(timespec="seconds")})
answers.apply_files()
late = items.card_for(c5["id"], wait=True)
out["6b. a press that reached no listener changes nothing"] = [
    late["state"], late["last_press"]["happened"], late["last_press"]["ok"], common.read_json(p5["file"], {})["status"],
    len(filters.rules())]
filters.add_rule("Hide made-up mail about the chess club", "show_less", source="made up")
got = press(c5["id"], {"name": "rsi_promote", "proposal": p5["id"]})
out["6b. a promote his changed rules refuse closes the card with why"] = [
    got["result"], got["items"][0]["state"], got["items"][0]["status"], common.read_json(p5["file"], {})["status"],
    rsi_loop.open_card("page"), [r["text"] for r in filters.rules()][-1]]

# 7. a setting proposal said in words only: no card, and the section is not held
mailings_miss()
made = rsi_loop.run(runner=stub, ask=answer(WORDS_ONLY))
p3 = rsi_loop._proposals("mailings")[-1]
out["7. a setting said in words only: no card, set aside"] = [made, p3["kind"], p3["status"], rsi_loop.open_card("mailings")]

# 8. a setting proposal's Apply changes only that setting
mailings_miss()
made = rsi_loop.run(runner=stub, ask=answer(SET_ONE))
c4 = made[0] if made else {}
p4 = proposal_of(c4)
settings_before, personal_before = common.read_json(common.SETTINGS, {}), common.read_json(common.paths.PERSONAL_JSON, {})
rules_before = common.read_json(filters.RULES_FILE, {})
got = press(c4["id"], {"name": "rsi_apply", "proposal": p4["id"]})
settings_after = common.read_json(common.SETTINGS, {})
changed = sorted(f"{g}.{k}" for g in set(settings_before) | set(settings_after)
                 for k in set((settings_before.get(g) or {}) if isinstance(settings_before.get(g), dict) else {"": 0})
                 | set((settings_after.get(g) or {}) if isinstance(settings_after.get(g), dict) else {"": 0})
                 if ((settings_before.get(g) or {}).get(k) if isinstance(settings_before.get(g), dict) else settings_before.get(g))
                 != ((settings_after.get(g) or {}).get(k) if isinstance(settings_after.get(g), dict) else settings_after.get(g)))
out["8. a setting card: Promote and Reject, the change in plain words"] = [
    c4.get("title"), (c4.get("rsi") or {}).get("act"), (c4.get("rsi") or {}).get("lines")]
out["8. apply: only that setting changed, the card closed"] = [
    got["result"], got["items"][0]["state"], changed, filters.get()["newsletters"],
    common.read_json(common.paths.PERSONAL_JSON, {}) == personal_before, common.read_json(filters.RULES_FILE, {}) == rules_before,
    common.read_json(p4["file"], {})["status"], [h["kind"] for h in coach.history("mailings")]]

# 8b. while a rule change card is open, a rule scan, a rebuild and a pass's card steps leave it exactly as it was
import card_rules, rebuild, think, comeback, standing, review
rsi_loop.queue("page")
c6 = rsi_loop.run(runner=stub, ask=answer(json.dumps({"change": "add", "text": "Show every note about the garden gate",
                                                       "way": "always_show", "reason": "A made-up reason"})))[0]
old_day = common.now() - dt.timedelta(days=60)          # old enough for every pass step that looks at age
db.execute("UPDATE live_items SET created_at=?, state_changed_at=?, source_when=?, updated_at=? WHERE id=?",
           (old_day, old_day, old_day, old_day, c6["id"]))
other = card_from(27, "Weekly letter", "-c")
answers._patch_snapshot([items.card_for(c6["id"], wait=True)])


def row6():
    return json.dumps(db.query("SELECT * FROM live_items WHERE id = ?", (c6["id"],)), default=str)


still, shown = row6(), []


def pick_all(prompt, seconds):          # a scan run that would close every card it is shown, and names the rule change card too
    import re
    ids = re.findall(r'"id": "(L\d+)"', prompt)
    shown.extend(ids)
    return json.dumps({"cards": [{"id": i, "do": "done"} for i in ids + [c6["id"]]]}), "", 0.0


card_rules._claude = pick_all
filters.add_rule("Mark every made-up card done", "show_less", source="made up")
scanned = card_rules.scan(filters.rules()[-1])
after_scan = row6()
answers.start_hidden = lambda *a, **k: False       # the rebuild's own writer is not started here
rebuilt = rebuild.start()
owed = (common.read_json(common.THINK_STATE, {}) or {}).get("rewrite_items") or []
reset = rebuild.reset([c6["id"]])
back = rebuild.put_back()
after_rebuild = row6()
writer = []


def writer_stub(prompt, model, expect, *a, **k):    # the pass's card writer: what it was shown, then a failed run
    writer.append(common.read_json(os.path.join(common.paths.STATE, "live_items_payload.json"), {}))
    return ai_steps.Result(False, why="made-up stop")


if not os.path.exists(common.paths.GOALS):
    os.makedirs(os.path.dirname(common.paths.GOALS), exist_ok=True)
    with open(common.paths.GOALS, "w", encoding="utf-8") as f:
        f.write("Made-up goals.")
ai_steps.agent = writer_stub
wrote = think.write_items([c6["id"], other], [], forced=[c6["id"], other])
ai_steps.agent = boom
joined = items.join(other, c6["id"], "made-up-pass") or items.join(c6["id"], other, "made-up-pass")
steps = [comeback.waiting("made-up-pass"), comeback.old("made-up-pass"), standing.apply("made-up-pass"),
         review.make("made-up-pass"), items.close_retired("made-up-pass"), presses.back_from_later("made-up-pass")]
after_pass = row6()
listed = json.dumps(db.query("SELECT extra FROM live_items WHERE source_key = 'live:old-cards'"), default=str)
out["8b. a scan, a rebuild and a pass leave an open rule change card as it was"] = [
    after_scan == still, bool(shown), c6["id"] in shown, c6["id"] in [c["id"] for c in card_rules._open_cards(set())],
    after_rebuild == still, c6["id"] in owed, reset[0],
    [[i["id"] for i in w.get("items") or []] == [other] for w in writer], any(c6["id"] in json.dumps(w) for w in writer),
    joined, after_pass == still, c6["id"] in listed, rsi_loop.open_card("page")["id"] == proposal_of(c6)["id"]]
rj = press(c6["id"], {"name": "rsi_reject", "proposal": proposal_of(c6)["id"]})
out["8b. its own Reject still closes it"] = [rj["items"][0]["state"], common.read_json(proposal_of(c6)["file"], {})["rejected_reason"]]

# 9. the RSI cap stops the runner; the job waits
st = common.settings()
st["rsi"] = dict(st.get("rsi") or {}, daily_runs=grader.runs_today())
common.write_json(common.SETTINGS, st)
rsi_loop.queue("page")
n, props = len(asked), proposals()
made = rsi_loop.run(runner=stub, ask=answer(ADD_ONE))
out["9. at the RSI cap the runner runs nothing and the job waits"] = [
    made, len(asked) - n, [j["section"] for j in rsi_loop.jobs()], proposals() == props]

# 10. the listener: after an answer its own RSI worker runs the queue and sends the card to the page
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(sys.argv[1])), "System", "live_page"))
import listen
ran, pushed, order = [], [], []
listen.engine = lambda: (lambda *a, **k: None)
listen.act = lambda cfg, fn, key, rec: order.append(("answer", threading.current_thread().name))
rsi_loop.run = lambda: (order.append(("rsi", threading.current_thread().name)), [{"id": "L999"}])[1]
listen.push = lambda cfg, changed, marks: pushed.append([c["id"] for c in changed])
listen.ALL[:] = [{"name": "made-up"}]
threading.Thread(target=listen.worker, name="answers", daemon=True).start()
threading.Thread(target=listen.rsi_worker, name="rsi", daemon=True).start()
listen.jobs.put(({"name": "made-up"}, "k", {"id": "L1", "action": "answer"}))
for _ in range(100):
    if pushed:
        break
    time.sleep(0.05)
out["10. the listener: the answer first, then the RSI queue on its own thread, the card sent to the page"] = [order, pushed]
out["no Claude anywhere"] = claude
before = [{"id": 5, "text": "Hide made-up mail from the kite club", "way": "show_less", "reason": "You said: \"kite mail is noise\""},
          {"id": 6, "text": "Hide made-up mail from the chess club", "way": "show_less"}]
shown = []
for c in ({"change": "edit", "rule": 5, "text": "Hide made-up mail from the kite club unless it names a race", "way": "show_less",
           "reason": "Race days matter to him"}, {"change": "remove", "rule": 6, "reason": "He wants chess mail again"}):
    f = rsi_loop.card_fields({"id": "made-up", "kind": "rule", "section": "page", "change": c, "reason": c["reason"],
                              "rules_before": before, "fixes": 1, "breaks": 0, "score_live": "1 of 2 matched",
                              "score_draft": "2 of 2 matched"})
    shown.append(f["extra"]["rsi"]["lines"][:3])
out["11. an edit or remove card shows the rule's reason now beside the change's Why"] = shown
print(json.dumps(out, default=str))
'''

ADD_WORDS = "Add a rule (always show): \"Show every message about the shed paint\""
KEEP = "type in the box first as your reason."
WANT = {
    "11. an edit or remove card shows the rule's reason now beside the change's Why": [
        ["The change: Change the rule \"Hide made-up mail from the kite club\" to (show less): \"Hide made-up mail from "
         "the kite club unless it names a race\"", "That rule's reason now: You said: \"kite mail is noise\"",
         "Why: Race days matter to him"],
        ["The change: Remove the rule \"Hide made-up mail from the chess club\"", "Why: He wants chess mail again",
         "It gets 1 more of your past answers right and 0 wrong."]],
    "setup queued": ["page", "mailings"],
    "1. a neutral press queues none, a contradicting one queues one job, a second miss adds none": [
        True, [], True, [["page", ["22"]]], [["page", ["22"]]]],
    "1. the press itself ran no Claude and coached nothing": [[], False, False, 0, False],
    "2. a level 1 job: no rule change card, the queue emptied": [0, None, []],
    "3. a level 2 job: one rule change card": [
        True, ["page"], 1, 1, True, "question", "Rule change: " + ADD_WORDS, ["Promote this rule change?"], [], []],
    "3. the card says the change, its reason, fixes and breaks, and both scores": [
        "The change: " + ADD_WORDS, "Why: He pressed should have seen on shed mail",
        "It gets 3 more of your past answers right and 0 wrong.", "I get 2 of 5 of your past answers right now. With this change: 5 of 5.",
        "Nothing changes until you press Promote. Reject leaves everything as it is, and I keep anything you " + KEEP],
    "3. its numbers are the proposal's": [True] * 6,
    "4. a miss in a section with an open card queues nothing": [[], False],
    "5. promote: live rules changed, the card closed, the proposal promoted": [
        "That answer is for another rule change card. Nothing was changed.",
        "Done. I promoted the change. It starts the next time I check for messages.", "done", "Promoted",
        [[3, "Hide mail from the paint shop", "show_less"], [4, "Show every message about the shed paint", "always_show"]],
        "promoted", None, []],
    "5. Undo after Promote takes nothing back": [
        "Nothing was taken back: a rule change you approved, applied or rejected stays as it is. Your rules and settings "
        "are in Settings.", "done", 2],
    "6. a press that agrees queues nothing": [True, []],
    "6b. a press that reached no listener changes nothing": [
        "question", "Nothing was changed: this page couldn't reach your computer when you pressed it. Press it again.", False,
        "open", 2],
    "6b. a promote his changed rules refuse closes the card with why": [
        "Nothing was changed: your rules changed since this was suggested. A new suggestion comes with your next "
        "correction.", "done", "Closed", "not shown", None, "Hide made-up mail about the chess club"],
    "6. reject: recorded with his words, nothing changed, the card closed": [
        1, "Rejected. Nothing was changed, and the reason is kept.", "done", "Rejected", "rejected", "rejected",
        "The shop sends more than paint news", True, None, "Rejected by you", "Rejected by you"],
    "7. a setting said in words only: no card, set aside": [[], "setting", "not shown", None],
    "8. a setting card: Promote and Reject, the change in plain words": [
        "Setting change: Change newsletters and promotions to \"show\"", "Promote",
        ["The change: Change newsletters and promotions to \"show\".", "Why: He wanted the sale mail",
         "I get 1 of 2 of your past answers right now. I can't try a setting on your past answers before you apply it, so there's "
         "no score with this change yet.", "Nothing changes until you press Promote. Reject leaves everything as it is, and I keep anything you " + KEEP]],
    "8. apply: only that setting changed, the card closed": [
        "Done. I changed it in Settings. It starts the next time I check for messages.", "done", ["filter.newsletters"], "show",
        True, True, "applied", ["version"]],
    "8b. a scan, a rebuild and a pass leave an open rule change card as it was": [
        True, True, False, False, True, False, 0, [True], False, False, True, False, True],
    "8b. its own Reject still closes it": ["done", "Rejected by you"],
    "9. at the RSI cap the runner runs nothing and the job waits": [[], 0, ["page"], True],
    "10. the listener: the answer first, then the RSI queue on its own thread, the card sent to the page": [
        [["answer", "answers"], ["rsi", "rsi"]], [["L999"]]],
    "no Claude anywhere": [],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="rsiloop-")
    try:
        env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"), PYTHONPATH=HERE)
        env.pop("ASSISTANT_REPLAY", None)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, LIVE, "-"], capture_output=True, text=True,
                           env=env, timeout=300)
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = {}
        if r.returncode or not got:
            check("the checks ran", r.stderr.strip()[-2500:], "")
        if os.environ.get("RSI_LOOP_SHOW"):
            print(json.dumps(got, indent=1))
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
