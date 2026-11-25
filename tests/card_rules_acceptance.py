r"""Acceptance: words typed on a card that read as a rule, and the rule scan (card_rules.py), on a scratch copy laid down from
this plugin with made-up cards. Claude's runs are stood in for (the rule check, the scan and the card's chat); everything else
is the real program. The page's side (Save beside the box, the four buttons) is checked in card_plan_page_acceptance.py.

- Words that are not a rule are acted on as before, with no rule proposed; Save closes a card that needs nothing more.
- Words that read as a rule are not acted on: the card stays open with the rule proposed (extra.rule_offer).
- Discuss rewords it on the card (same buttons), Cancel changes nothing and gives the words back, Disapprove acts this one time
  and saves no rule, Approve saves the rule, acts on the card, and scans the other open cards.
- The scan is shown the open cards oldest first, changes only the cards it picks, in that order, saves them first, and one
  Undo puts them all back. A rule saved in Talk to your assistant scans too, with its Undo on the reply.
- Nothing outbound is tried at any step.
- Every rule carries its reason: the run's, kept through Discuss, saved on Approve; a rule asked in Talk has his words as its
  reason; Settings saves, keeps and refuses as it should; an old rule with none still loads; the prompts' lines carry it.

    python tests\card_rules_acceptance.py
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
import datetime as dt, json, os, re, sys
sys.path.insert(0, sys.argv[1])
import common, items, answers, chat, card_rules, filters, replay_guard, settings_page
out = {}
import atexit
atexit.register(lambda: print(json.dumps(out, default=str)))     # what was found, even when a step fails
outbound = []
replay_guard.refuse = lambda what: outbound.append(what)        # every outbound step calls this first
now = common.now()

def make(key, title, why, days_ago, state="question", area="Work"):
    iid, _ = items.upsert(key, "t", kind="question", area=area, state=state, title=title, why=why, source_who="Email: UPS",
                          source_when=now - dt.timedelta(days=days_ago), asks=[] if state != "question" else ["What next?"])
    items.update(iid, "t", from_at=now - dt.timedelta(days=days_ago))
    return iid

src = make("live:cr-src", "Your UPS package 1Z999 shipped", "UPS says a package shipped.", 1)
ship_new = make("live:cr-s3", "Your UPS package 1Z300 is out for delivery", "A shipping notice.", 2, state="handled")
ship_old = make("live:cr-s1", "Your UPS package 1Z100 shipped", "A shipping notice.", 9, state="handled")
ship_mid = make("live:cr-s2", "Your FedEx package 7788 shipped", "A shipping notice.", 5, state="handled")
other = make("live:cr-o1", "Acme invoice 1101 is unpaid", "An invoice is overdue.", 7)
meet = make("live:cr-o2", "Pat asks to move Tuesday's meeting", "Pat wants a new time.", 3)
plain = make("live:cr-p1", "Dana sent the signed contract", "The contract came back signed.", 4)
items.export("t")

# Claude, standing in. The rule check: words with "from now on" are a rule, a reword follows the talk; the scan picks the
# shipping notices; the card's chat settles the card and also tries to save a rule (which must be dropped after a button)
checks, scans, chats = [], [], []
def claude(prompt, timeout=None):
    if "Decide whether the words are a STANDING" in prompt:
        checks.append(prompt)
        if "Only UPS" in prompt:
            return '{"rule": "Mark every UPS shipping notice Done.", "way": "card_rule", "say": "Only UPS now."}', "", 0.1
        if "from now on" in prompt.splitlines()[1].lower():          # his words are the second line
            return ('{"rule": "Mark every shipping notice Done.", "way": "card_rule", "say": "It catches shipping notices from any carrier.", '
                    '"reason": "Shipping notices need nothing from me."}'), "", 0.1
        return '{"rule": "", "way": "card_rule", "say": "Only about this card."}', "", 0.1
    lines = prompt.splitlines()
    rows = json.loads("\n".join(lines[lines.index("["):lines.index("]") + 1]))       # the cards, as the scan is shown them
    scans.append([r["id"] for r in rows])
    picks = [dict({"id": r["id"]}, **({"do": "snooze", "until": "2030-01-07"} if "FedEx" in r["title"] else {"do": "retag", "area": "Shipping"}
                  if "1Z300" in r["title"] else {"do": "done"})) for r in rows if "package" in r["title"]]
    return json.dumps({"cards": list(reversed(picks))}), "", 0.1          # given newest first: applied oldest first all the same
card_rules._claude = claude
def run(words, told, sess):
    chats.append(words)
    tries = "standing rule" in words or "One time only" in words      # after a button: a rule the chat tries to save is dropped
    return ('Done with it.\n' + ('ACTION: {"type": "rule", "text": "From now on never show me anything"}\n' if tries else '') +
            'ACTION: {"type": "card", "state": "handled", "settled": [1], "card": null}'), "", 0.1, {}
chat._run = run

def card(i):
    answers.wait_landed(30)
    return items.card_for(i, wait=True)
def say(i, text, at):
    r = answers.act_on_answer({"id": i, "action": "answer", "text": text, "at": at, "device": "test"})
    answers.wait_landed(30)
    return r
def press(i, p, at):
    r = answers.act_on_answer({"id": i, "action": "answer", "text": json.dumps({"press": p}), "at": at, "device": "test"})
    answers.wait_landed(30)
    return r

# 4. words that are not a rule: acted on as before, no proposal; Save closes the card when nothing more is needed
r = say(plain, "Filed it, thanks.", "2026-11-23T09:00:00")
c = card(plain)
out["not a rule: acted on at once, no proposal, the card closed"] = [len(checks), len(chats), c["state"], c.get("rule_offer"),
                                                                   "Closed when you saved" in c["assistant_did"]]
rules0 = len(filters.rules())

# 2. words that read as a rule: proposed, not acted on
n_chat = len(chats)
r = say(src, "From now on mark these shipping notices done", "2026-11-23T09:01:00")
c = card(src)
o = c.get("rule_offer") or {}
out["a rule: proposed on the card, not acted on"] = [c["state"], c["status"], o.get("text"), o.get("words"), len(chats) - n_chat,
                                                     r["result"].startswith("That reads like a rule to keep")]
out["R typed words: the proposed rule carries the run's reason"] = o.get("reason")
# Discuss: reworded on the card, still a proposal; no rule, no chat
r = press(src, {"name": "rule_offer", "do": "discuss", "words": "Only UPS ones"}, "2026-11-23T09:02:00")
c = card(src)
o = c.get("rule_offer") or {}
out["Discuss rewords it on the card"] = [o.get("text"), [t["who"] for t in o.get("talk") or []], o.get("words"), c["state"],
                                         len(filters.rules()) - rules0, len(chats) - n_chat]
out["R a reword with no reason keeps the one before"] = o.get("reason")
# Cancel: nothing happens, the card is as it was, his words go back (the page puts them in the box)
r = press(src, {"name": "rule_offer", "do": "cancel"}, "2026-11-23T09:03:00")
c = card(src)
out["Cancel: no rule, no action, the card as it was"] = [c.get("rule_offer"), c["state"], c["status"], c["asks"],
                                                        len(filters.rules()) - rules0, len(chats) - n_chat]
# Disapprove: acted on this one time, no rule saved (not even the one the chat tried)
say(src, "From now on mark these shipping notices done", "2026-11-23T09:04:00")
r = press(src, {"name": "rule_offer", "do": "disapprove"}, "2026-11-23T09:05:00")
c = card(src)
out["Disapprove: acted on once, no rule saved"] = [c.get("rule_offer"), c["state"], len(filters.rules()) - rules0,
                                                  "(about card" in chats[-1] and "One time only" in chats[-1], len(scans)]
# Approve: saved, acted on, then the scan
items.update(src, "t", state="question", status=None)
items.export("t")
say(src, "From now on mark these shipping notices done", "2026-11-23T09:06:00")
# a run that cannot be made after Approve: the proposal stays as it was, no rule saved, no card gone over
chat._run = lambda words, told, sess: (None, "Claude is not reachable", 0.1, {})
r = press(src, {"name": "rule_offer", "do": "approve"}, "2026-11-23T09:06:30")
c = card(src)
out["a failed run after Approve leaves the proposal, saves nothing"] = [c["state"], c["status"], (c.get("rule_offer") or {}).get("text"),
                                                                       len(filters.rules()) - rules0, len(scans), (c.get("last_press") or {}).get("ok")]
chat._run = run
answers._recent.clear()        # the same press again at once is otherwise one press
look = lambda i: (lambda x: (x["state"], x.get("shelf"), x.get("area"), str(x.get("later_until") or "")[:10]))(card(i))
before = {i: look(i) for i in (ship_old, ship_mid, ship_new, other, meet)}
r = press(src, {"name": "rule_offer", "do": "approve"}, "2026-11-23T09:07:00")
c = card(src)
saved = filters.rules()
after = {i: look(i) for i in (ship_old, ship_mid, ship_new, other, meet)}
out["Approve: the rule saved once, the card acted on"] = [[x["text"] for x in saved[rules0:]], c["state"],
                                                         "standing rule" in chats[-1] and "do not save it yourself" in chats[-1]]
out["R typed words: the approved rule is saved with its reason"] = [x.get("reason") for x in saved[rules0:]]
out["3. done, snoozed and retagged as the scan said"] = [after[ship_old][0], after[ship_mid][1:], after[ship_new][2]]
sc = c.get("rule_scan") or {}
rec = common.read_json(os.path.join(card_rules.FOLDER, sc.get("id", "") + ".json"), {}) or {}
out["3. the scan was shown the open cards oldest first, never the card it came from"] = (scans[-1] if scans else None) == [ship_old, other, ship_mid, meet, ship_new]
out["3. it changed only the matching cards, oldest first, each saved first"] = [
    [k for k in after if after[k] != before[k]] == [ship_old, ship_mid, ship_new], rec.get("order") == [ship_old, ship_mid, ship_new],
    sorted(rec.get("cards") or {}) == sorted([ship_old, ship_mid, ship_new]), after[other] == before[other], after[meet] == before[meet]]
out["3. the card it came from says so, with its Undo"] = [sc.get("n"), sc.get("said"), "Your rule was applied to 3 other cards." in r["result"]]
# Undo puts them all back
u = answers.act_on_answer({"id": "rule-scan:" + sc["id"], "action": "answer", "text": json.dumps({"press": {"name": "scan_undo"}}),
                           "at": "2026-11-23T09:08:00", "device": "test"})
answers.wait_landed(30)
back = {i: look(i) for i in (ship_old, ship_mid, ship_new, other, meet)}
out["3. one Undo puts every one of them back"] = [back == before, u["result"], bool((card(src).get("rule_scan") or {}).get("undone"))]

# a rule saved in Talk to your assistant goes over the open cards too, its Undo on the reply
def run2(words, told, sess):
    chats.append(words)
    return 'Saved.\nACTION: {"type": "rule", "text": "From now on file every UPS shipping notice as done."}', "", 0.1, {}
chat._run = run2
r = chat.handle("UPS notices should always just be done", at="2026-11-23T09:09:00")
answers.wait_landed(30)
made = [i for i in r.get("items") or [] if str(i.get("source_key") or "").startswith("live:asked-")]
asked = card(made[0]["id"]) if made else {}
saved_before = len([x for x in filters.rules() if "UPS" in x["text"]])
items.export("t")
answers.act_on_answer({"id": asked.get("id"), "action": "answer", "at": "2026-11-23T09:10:00", "device": "t",
                       "text": json.dumps({"press": {"name": "rule_offer", "do": "approve"}})})
after = card(asked.get("id")) if asked else {}
out["a rule from Talk to your assistant is its own card; Approve saves it and applies it, with its Undo"] = [
    (asked.get("rule_offer") or {}).get("made"), saved_before, len([x for x in filters.rules() if "UPS" in x["text"]]),
    (after.get("rule_scan") or {}).get("n"), after.get("state")]
ups = [x for x in filters.rules() if "UPS" in x["text"]]
out["R a rule asked in Talk has his words as its reason, on the card and saved"] = [
    (asked.get("rule_offer") or {}).get("reason"), [x.get("reason") for x in ups]]

# R. Settings: a reason is saved, kept and loaded; an old rule with none still loads; other keys are still refused
filters._write_rules(filters.rules() + [{"id": 900, "text": "Never show me the weekly bakery coupon mail.", "way": "show_less",
                                          "on": True, "made": "2026-01-02T08:00:00", "from": "You wrote it in Settings"}])
old = next((x for x in filters.rules() if x["id"] == 900), {})
out["R an old rule without a reason still loads"] = [old.get("text"), "reason" in old,
    next((x for x in filters.rules_for_page() if x["id"] == 900), {}).get("reason"),
    "  owner rule 900 (show less): Never show me the weekly bakery coupon mail." in filters.lines_for_sorting()]
def fsave(rows):
    return settings_page.save({"settings": {"group": "filter", "values": {"rules": rows, "rules_seen": [x["id"] for x in filters.rules()]}}})
sent = [dict(x, reason="The bakery coupons are never for me.") if x["id"] == 900 else x for x in filters.present()["rules"]]
ok1, line1 = fsave(sent)
on_disk = {x["id"]: x for x in (common.read_json(filters.RULES_FILE, {}) or {}).get("rules") or []}
out["R a reason saved in Settings survives save and load"] = [ok1, "nothing was different" in line1, on_disk.get(900, {}).get("reason"),
    next((x for x in filters.present()["rules"] if x["id"] == 900), {}).get("reason")]
ok2, line2 = fsave([{k: v for k, v in x.items() if k != "reason"} for x in filters.present()["rules"]])
out["R a Save that sends no reason keeps the saved one"] = [ok2, next(x for x in filters.rules() if x["id"] == 900).get("reason")]
ok3, line3 = fsave([dict(x, colour="red") for x in filters.present()["rules"]])
ok4, line4 = fsave([dict(x, reason="x" * 301) if x["id"] == 900 else x for x in filters.present()["rules"]])
out["R Settings still refuses other keys, and a reason too long"] = [ok3, line3.startswith("Not saved."), ok4, line4.startswith("Not saved."),
    next(x for x in filters.rules() if x["id"] == 900).get("reason")]
out["R the sorting and writing prompts carry the reason"] = [
    "  owner rule 900 (show less): Never show me the weekly bakery coupon mail. (because: The bakery coupons are never for me.)"
    in filters.lines_for_sorting(), "Mark every shipping notice Done. (because: Shipping notices need nothing from me.)" in filters.lines_for_writing()]

# a rule that names a subject marker reaches an open card whose email subject carries it, though its title and words do not
seen_rows = []
def claude3(prompt, timeout=None):
    lines = prompt.splitlines()
    rows = json.loads("\n".join(lines[lines.index("["):lines.index("]") + 1]))
    seen_rows.extend(rows)
    return json.dumps({"cards": [{"id": r["id"], "do": "rewrite", "title": "Test C: " + r["title"]} for r in rows
                                 if any("TEST-C" in s for s in r.get("email_subjects") or [])]}), "", 0.1
card_rules._claude = claude3
shed = {"id": "Lshed", "title": "Garden shed: by the fence or by the back door?", "why": "An email asks where the garden shed goes.",
         "area": "Work", "from_at": "2026-11-24T10:05:00", "messages": [{"id": 1, "subject": "[TEST-C] Question about the shed spot"}]}
unrel = {"id": "Lother", "title": "Acme invoice 1101 is unpaid", "why": "An invoice is overdue.", "area": "Work",
         "from_at": "2026-11-24T10:06:00", "messages": [{"id": 2, "subject": "Invoice 1101"}]}
got3 = card_rules._pick({"id": 99, "text": 'Cards for messages with TEST-C in the subject start their title with "Test C".'}, [shed, unrel])
out["6. a rule naming a subject marker picks the open card whose email subject carries it"] = [
    [c["id"] for c, x in got3], seen_rows[0].get("email_subjects")]

out["5. nothing outbound was tried"] = outbound
'''

WANT = {
    "not a rule: acted on at once, no proposal, the card closed": [1, 1, "done", None, True],
    "a rule: proposed on the card, not acted on": ["question", "Rule proposed", "Mark every shipping notice Done.",
                                                   "From now on mark these shipping notices done", 0, True],
    "Discuss rewords it on the card": ["Mark every UPS shipping notice Done.", ["you", "assistant"],
                                       "From now on mark these shipping notices done", "question", 0, 0],
    "Cancel: no rule, no action, the card as it was": [None, "question", None, ["What next?"], 0, 0],
    "Disapprove: acted on once, no rule saved": [None, "done", 0, True, 0],
    "Approve: the rule saved once, the card acted on": [["Mark every shipping notice Done."], "done", True],
    "3. the scan was shown the open cards oldest first, never the card it came from": True,
    "a failed run after Approve leaves the proposal, saves nothing": ["question", "Rule proposed", "Mark every shipping notice Done.", 0, 0, False],
    "3. done, snoozed and retagged as the scan said": ["done", ["later", "Work", "2030-01-07"], "Shipping"],
    "3. it changed only the matching cards, oldest first, each saved first": [True, True, True, True, True],
    "3. the card it came from says so, with its Undo": [3, "Your rule was applied to 3 other cards.", True],
    "3. one Undo puts every one of them back": [True, "Put back: the 3 cards your rule changed are as they were.", True],
    "a rule from Talk to your assistant is its own card; Approve saves it and applies it, with its Undo": ["rule", 0, 1, 3, "done"],
    "5. nothing outbound was tried": [],
    "R typed words: the proposed rule carries the run's reason": "Shipping notices need nothing from me.",
    "R a reword with no reason keeps the one before": "Shipping notices need nothing from me.",
    "R typed words: the approved rule is saved with its reason": ["Shipping notices need nothing from me."],
    "R a rule asked in Talk has his words as its reason, on the card and saved": ['You said: "UPS notices should always just be done"', ['You said: "UPS notices should always just be done"']],
    "R an old rule without a reason still loads": ["Never show me the weekly bakery coupon mail.", False, None, True],
    "R a reason saved in Settings survives save and load": [True, False, "The bakery coupons are never for me.", "The bakery coupons are never for me."],
    "R a Save that sends no reason keeps the saved one": [True, "The bakery coupons are never for me."],
    "R Settings still refuses other keys, and a reason too long": [False, True, False, True, "The bakery coupons are never for me."],
    "R the sorting and writing prompts carry the reason": [True, True],
    "6. a rule naming a subject marker picks the open card whose email subject carries it": [["Lshed"], ["[TEST-C] Question about the shed spot"]],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="cardrules-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_cardrules", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47917",
                            "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=600)
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = {}
        if r.returncode:
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
