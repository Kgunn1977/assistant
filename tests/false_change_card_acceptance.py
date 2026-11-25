r"""Acceptance (quick): a change card is made only when his own words ask for a change (a fault seen at 5:05 PM).
On a scratch home, with made-up words; the Claude run is stood in with a reply shaped like the one that caused the fault.

  1. a 5:05 message "One half works now, let's try the other half.", after two Claude app turns of 5:04, with the
     reply that asked him which he meant and named a button not on the page: no card is made, the question is kept, the
     button sentence is dropped, and the run is given the two app turns marked as said in the Claude app;
  2. a real change asked in his words, with a reply saying it was noted and no ACTION line: its card is made;
  3. a change_start ACTION line still makes its card.

    python tests\false_change_card_acceptance.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


INSIDE = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
import common
assert os.path.abspath(common.HOME).startswith(os.path.abspath(sys.argv[2])), "not a scratch home: " + common.HOME
import db, items, chat, settings_page
db.init_schema()
items.ensure()
os.makedirs(common.LOGS, exist_ok=True)
os.makedirs(os.path.dirname(common.AI_LOG), exist_ok=True)
out = {}
replies, told = [], []
chat._run = lambda words, t, sess: (told.append(t) or (replies.pop(0) if replies else "(extra run) " + words[:200]), "", 0.1, {})
chat.instructions = lambda found, turns, **k: json.dumps(chat.thread(turns))      # what the run is given of the conversation
chat.found_for = lambda *a, **k: {}
settings_page.at_limit = lambda: False

def cards():
    con = db.connect()
    try:
        return [r[0] for r in con.execute("SELECT title FROM live_items WHERE source_key LIKE 'live:asked-%' ORDER BY source_key").fetchall()]
    finally:
        con.close()

# the conversation as chat.json would hold it at 5:05 PM: two turns of a joined Claude app session (made up)
common.write_json(chat.CHAT_JSON, {"turns": [
    {"who": "you", "text": "Checking whether that holds...", "at": "2026-11-23T17:04:34", "desktop": "a1b2c3d4"},
    {"who": "assistant", "text": "It holds so far. Your \"Checking whether that holds...\" is already in the page's conversation, marked as said from this desktop session.",
     "at": "2026-11-23T17:04:42", "desktop": "a1b2c3d4"}]})
# 1. the box's reply of 5:05:30, as the run would give it
replies.append("Which one do you mean: closing the three garden show cards, or the 1-hour and 12-hour reminders on calendar entries? "
               "The reminders still need your \"Yes, make this change\" on the page, and the garden show cards are still open until you tell me to mark them done.")
got = chat.handle("One half works now, let's try the other half.", at="2026-11-23T17:05:21")
seen = json.loads(told[-1])
out["5:05 replay: no card"] = cards()
out["5:05 replay: the reply"] = got.get("result")
out["5:05 replay: the run saw the app turns"] = [[t.get("said")[:25], t.get("in_the_claude_app")] for t in seen[:2]]
out["the instructions explain app turns"] = "in_the_claude_app was said in a Claude app session" in open(os.path.join(sys.argv[1], "prompts", "chat.md"), encoding="utf-8").read()
# 2. a real change in his words; the reply says it was noted, with no ACTION line
replies.append("Noted: that change is recorded, so every new calendar entry gets a 30-minute reminder.")
got = chat.handle("From now on, put a 30-minute reminder on every calendar entry you add.")
out["his change in words: card"] = cards()
out["his change in words: line"] = str(got.get("result"))
# 3. a change_start ACTION line
replies.append("I will put that on a card for your Approve.\nACTION: " + json.dumps({"type": "change_start", "words": "Show my cards in two columns.",
                                                                                  "change": "The Cards list shows in two columns."}))
got = chat.handle("Show my cards in two columns.")
out["change_start: card"] = cards()
print(json.dumps(out, default=str))
'''


def main():
    tmp = tempfile.mkdtemp(prefix="false-card-")
    live = os.path.join(PKG, "engine", "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"))
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live, tmp], capture_output=True, text=True, env=env, timeout=300, encoding="utf-8")
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        check("the engine checks ran", (r.stdout + r.stderr).strip()[-3000:], "")
        got = {}
    if got:
        check("5:05 replay: no card is made", got["5:05 replay: no card"], [])
        check("5:05 replay: the question is kept, the missing button dropped", got["5:05 replay: the reply"],
              "Which one do you mean: closing the three garden show cards, or the 1-hour and 12-hour reminders on calendar entries?")
        check("5:05 replay: the run is given the two app turns, marked", got["5:05 replay: the run saw the app turns"],
              [["Checking whether that hol", True], ["It holds so far. Your \"Ch", True]])
        check("the instructions say app turns are this conversation", got["the instructions explain app turns"], True)
        check("a change asked in his words gets its card", got["his change in words: card"],
              ["From now on, put a 30-minute reminder on every calendar entry you add."])
        check("its line says where the card is", got["his change in words: line"].startswith("I put it on a card in Cards, under Needs you"), True)
        check("a change_start ACTION line makes its card", got["change_start: card"],
              ["From now on, put a 30-minute reminder on every calendar entry you add.", "Show my cards in two columns."])
    for name, ok, g, w in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {w!r}, got {g!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
