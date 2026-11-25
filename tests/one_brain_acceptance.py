r"""Acceptance (quick): phase 2 of the judgment rebuild, "one brain". On a scratch copy laid down from this plugin, with made-up
messages, people and cards; the gathering and the Claude runs are stood in for (no Claude run, nothing sent).

- One pass with made-up messages: the judging run decides what each message means and, in the same run, writes the card of
  each matter it leaves open; the cards' recommendation, questions, choices and pick are the ones that run wrote, and no
  card writer run is made for them. The run was told how to write a card and what he did last time on a card from a sender.
- A card from a sender he answered differently last time offers that answer as one of its own choices.
- The pass log line says what judging and writing cost this pass against the passes on record from before.
- Talk to your assistant, asked "how many cards have an I'd hide this button", searches every card (30 made-up cards, open and
  closed, with other hide buttons among them) and answers with the right count.

    python tests\one_brain_acceptance.py
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
import common, db, items, think, gather, ai_steps, picks, updates, chat
P = __import__("pass")
out = {}
now = dt.datetime.now().replace(microsecond=0)
db.init_schema(); items.ensure()
con = db.connect()
for mid, fk, subj, body, thread in (
        (30001, "email:pat@example.test", "Walkthrough", "Can you do the walkthrough Tuesday or Wednesday?", "t-pat"),
        (30002, "email:lee@example.test", "Invoice 88", "Invoice 88 for the porch work, $400. Please approve it.", "t-lee"),
        (30003, "email:deals@example.test", "Big sale", "Everything is 20% off this week.", "t-deals")):
    con.execute("INSERT INTO messages (id, channel, account, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)"
                " VALUES (?, 'email', 'me@example.test', ?, ?, 'in', ?, '[]', ?, ?, ?)", (mid, thread, now - dt.timedelta(hours=2), fk, subj, body, now))
con.close()
# what he did last time on a card from Pat, instead of my pick (phase 1 keeps it)
picks.remember({"id": "L1", "sender": {"key": "email:pat@example.test"}}, {"do": "words", "words": "Ask Pat to call me"})
# the passes on record from before one brain: a judging run and a card writer run each
os.makedirs(common.LOGS, exist_ok=True)
with open(common.AI_LOG, "a", encoding="utf-8") as f:
    for n in (1, 2):
        f.write(json.dumps({"pass": f"live-old-{n}", "step": "judge", "ok": True, "out_tokens": 800, "cost": 0.03}) + "\n")
        f.write(json.dumps({"pass": f"live-old-{n}", "step": "write items", "ok": True, "out_tokens": 1200, "cost": 0.04}) + "\n")

runs, told = [], {}
def stand_in(prompt, model, timeout, resume=None):
    dest = re.search(r"Write your output file to exactly this path: (\S+)", prompt)
    if "judging pass" in prompt:
        runs.append("judge")
        pl = common.read_json(re.search(r"READ THE PAYLOAD:\s*(\S+)", prompt).group(1), {})
        told["how to write a card"] = all(w in prompt for w in ("ONE UNDERSTANDING", "`pick`", "`choices`", "`recommended`", "`asks`"))
        told["last time, by sender"] = {m["id"]: m.get("owner_last_time") for m in pl.get("messages") or []}
        doc = {"payload": re.search(r"READ THE PAYLOAD:\s*(\S+)", prompt).group(1), "verdicts": [
            {"id": 30001, "disposition": "task", "reason": "Pat asks for a day", "covered": False, "leaned_on": "a question to him",
             "task": {"item_key": "personal::pat-walkthrough", "area": "Personal", "title": "Pat asks which day for the walkthrough",
                      "detail": "Pat asks Tuesday or Wednesday (30001).", "status": "needs_me", "urgency": "normal"}},
            {"id": 30002, "disposition": "task", "reason": "an invoice to approve", "covered": False, "leaned_on": "a request to him",
             "task": {"item_key": "personal::lee-invoice-88", "area": "Personal", "title": "Lee's invoice 88 for $400",
                      "detail": "Lee asks to approve invoice 88, $400 (30002).", "status": "needs_me", "urgency": "normal"}},
            {"id": 30003, "disposition": "noise", "reason": "a sale mailing", "covered": False, "leaned_on": "a mailing"}],
            "cards": [
            {"item_key": "personal::pat-walkthrough", "title": "Pat asks which day works for the walkthrough", "header": "Pat: walkthrough day?",
             "why": "Pat asks which day works for the walkthrough.", "detail": "Pat's email asks Tuesday or Wednesday.",
             "recommended": "Say Tuesday.", "asks": ["Which day works for the walkthrough?"],
             "choices": [{"text": "Tuesday works", "meaning": "agrees"}, {"text": "Wednesday instead", "meaning": "other"}],
             "recommended_choice": "Tuesday works", "pick": {"do": "choice", "text": "Tuesday works"},
             "evidence": "Pat's email (30001)", "state": "question", "important": False},
            {"item_key": "personal::lee-invoice-88", "title": "Lee's invoice 88 for the porch, $400", "header": "Approve Lee's $400 invoice?",
             "why": "Lee asks you to approve invoice 88 for $400.", "detail": "Lee's email asks approval of invoice 88, $400.",
             "recommended": "Approve it.", "asks": ["Approve invoice 88 for $400?"],
             "choices": [{"text": "Approve it", "meaning": "agrees"}, {"text": "Hold it", "meaning": "disagrees"}],
             "recommended_choice": "Approve it", "pick": {"do": "choice", "text": "Approve it"},
             "evidence": "Lee's email (30002)", "state": "question", "important": False}]}
        common.write_json(dest.group(1), doc)
        return ai_steps.Result(True, "ok", "s-judge", 1.0, 0.05, out_tokens=1500)
    runs.append("other")
    if dest:
        common.write_json(dest.group(1), {"items": [], "new_items": [], "loose": [], "nothing": []})
    return ai_steps.Result(True, "ok", "s-other", 1.0, 0.0, out_tokens=10)
think._engine_call = stand_in
updates.check = lambda pass_id: None
def gather_new(pass_id):
    return {"pass_id": pass_id, "secs": 0.1, "new_messages": [30001, 30002, 30003], "new_in": 3, "by_channel": {"email": 3},
            "new_attachments": 0, "pages_waiting": 0, "texted_images_waiting": 0, "unjudged": 3, "sources": {}, "follow": {},
            "timing": {}, "problems": []}
gather.gather = gather_new

# --- 1. one pass: the judging run writes the cards, no card writer run ---
P.main()
snap = common.read_json(common.ITEMS_JSON, {}).get("items") or []
by = {c["source_key"]: c for c in snap}
pat, lee = by.get("task:personal::pat-walkthrough") or {}, by.get("task:personal::lee-invoice-88") or {}
out["1. the judging run was told how to write a card, and what he did last time on a card from Pat"] = [
    told.get("how to write a card"), (told.get("last time, by sender") or {}).get("30001") or (told.get("last time, by sender") or {}).get(30001)]
out["1. Claude runs this pass: the judging run alone"] = runs
def same(c):
    return [c.get("recommended"), c.get("asks"), (c.get("pick") or {}).get("text"), (c.get("pick") or {}).get("by"),
            [x.get("text") for x in c.get("choices") or []]]
out["1. Pat's card: recommendation, question, pick and choices from the judging run"] = same(pat)
out["1. Lee's card: the same"] = same(lee)
ai = [json.loads(x) for x in open(common.AI_LOG, encoding="utf-8")]
out["1. the AI log: the cards' run is the judging run"] = sorted({r["step"] for r in ai if str(r.get("pass", "")).startswith("live-2")})

# --- 2. the choices grow: Pat's card offers what he did last time, as one of its own choices ---
out["2. Pat's card offers 'Ask Pat to call me' as a choice, after my recommendation"] = [
    [x.get("label") for x in pat.get("choices") or []][:2], pat.get("last_time")]

# --- 3. the pass log line: the cost of the combined step against before ---
with open(common.PASS_LOG, encoding="utf-8") as f:
    line = f.read().splitlines()[-1]
m = re.search(r"one brain: [^|]*", line)
out["3. the pass log line"] = m.group(0).strip() if m else line

# --- 4. Talk to your assistant counts cards by a button, across every card ---
con = db.connect()
mid = 31000
def card_row(key, title, state, kind="fyi", msgs=None, extra=None, asks=None):
    iid = "L" + str(con.execute("SELECT nextval('seq_live_item')").fetchone()[0])
    con.execute("INSERT INTO live_items (" + ", ".join(items.BASE_COLUMNS) + ") VALUES (" + ", ".join("?" for _ in items.BASE_COLUMNS) + ")",
                (iid, key, kind, "Personal", title, None, state, 0, None, "Someone", now, "Someone", json.dumps(msgs or []), None,
                 json.dumps(asks or []), None, "made up", "[]", None, None, None, None, None, now, now, now,
                 now if state == "done" else None, "t"))
    if extra:
        con.execute("UPDATE live_items SET extra = ? WHERE id = ?", (json.dumps(extra), iid))
    return iid
for n in range(6):          # open "I'd hide this" cards: each shows Hide things like this
    card_row(f"live:wouldhide-{40000 + n}", f"I'd hide this: Shop {n}: a sale", "handled")
for n in range(2):          # closed ones: no buttons any more
    card_row(f"live:wouldhide-{40100 + n}", f"I'd hide this: Old shop {n}: a sale", "done")
for n in range(3):          # open mailings: Hide mailings like this, a different button
    mid += 1
    con.execute("INSERT INTO messages (id, channel, account, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)"
                " VALUES (?, 'email', 'me@example.test', ?, ?, 'in', ?, '[]', 'News', 'Our news. To stop these, https://news.example.test/unsubscribe?u=1', ?)",
                (mid, f"t-news{n}", now, f"email:news{n}@example.test", now))
    card_row(f"live:msg-{mid}", f"News {n} from a club", "handled", msgs=[str(mid)])
for n in range(18):         # everything else, open and closed
    card_row(f"live:made-{n}", f"Made-up matter {n}", "done" if n % 3 == 0 else "question", kind="question",
             asks=[] if n % 3 == 0 else [f"Question {n}?"],
             extra=None if n % 3 == 0 else {"choices": [{"label": "Yes", "text": "Yes"}, {"label": "No", "text": "No"}]})
con.close()
items.export("t")
in_store = db.query("SELECT count(*) FROM live_items WHERE starts_with(source_key, 'live:wouldhide-') OR starts_with(source_key, 'live:msg-3')"
                    " OR starts_with(source_key, 'live:made-')")[0][0]
asked = []
def chat_run(words, instructions, sess):
    asked.append(words)
    if len(asked) == 1:
        return 'ACTION: {"type": "cards", "button": "Hide things like this"}', "", 0.1, {}
    got = re.search(r'"card_search":\s*\[\s*\{.*?"count":\s*(\d+)', instructions, re.S)
    return (f"{got.group(1)} cards have that button." if got else "I could not find the count."), "", 0.1, {}
chat._run = chat_run
r = chat.handle("how many cards have an I'd hide this button")
import card_search
s = card_search.search(button="Hide things like this")
out["4. the made-up cards in the store"] = in_store
out["4. the chat's answer, after one search of every card"] = [r.get("result"), len(asked)]
out["4. the search: count, open, closed; the closed and the other hide buttons are not counted"] = [s["count"], s["open"], s["closed"],
    card_search.search(button="hide")["count"], card_search.search(kind="I'd hide this")["count"],
    card_search.search(kind="I'd hide this", state="closed")["count"]]
print(json.dumps(out, default=str))
'''

WANT = {
    "1. the judging run was told how to write a card, and what he did last time on a card from Pat": [True, "Ask Pat to call me"],
    "1. Claude runs this pass: the judging run alone": ["judge"],
    "1. Pat's card: recommendation, question, pick and choices from the judging run": [
        "Say Tuesday.", ["Which day works for the walkthrough?"], "Tuesday works", "writer",
        ["Tuesday works", "Ask Pat to call me", "Wednesday instead"]],
    "1. Lee's card: the same": ["Approve it.", ["Approve invoice 88 for $400?"], "Approve it", "writer", ["Approve it", "Hold it"]],
    "1. the AI log: the cards' run is the judging run": ["judge"],
    "2. Pat's card offers 'Ask Pat to call me' as a choice, after my recommendation": [
        ["Tuesday works (recommended)", "Ask Pat to call me"], None],
    "3. the pass log line": ("one brain: 2 card(s) written with the verdicts, 0 by the card writer; judging and writing took 1 Claude run(s),"
                             " 1500 output tokens, $0.05; before (judge and card writer apart, average of the last 2 pass(es) on record):"
                             " 2.0 Claude run(s), 2000 output tokens, $0.07"),
    "4. the made-up cards in the store": 30,
    "4. the chat's answer, after one search of every card": ["7 cards have that button.", 2],
    "4. the search: count, open, closed; the closed and the other hide buttons are not counted": [7, 7, 0, 10, 9, 2],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="onebrain-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    env.pop("ASSISTANT_REPLAY", None)
    spec = importlib.util.spec_from_file_location("ac_onebrain", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47939", "--sending", "no",
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
