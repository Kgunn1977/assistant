r"""A test page for the chat panel (Texts): long threads (300 messages) and slow answers (2 seconds), on a scratch home.

Nothing real is read or sent: the texts come from a stand-in, and the home is a scratch folder.
It prints the page's one-time sign-in address. New messages arrive when a file named arrive.flag appears in the scratch folder
(the folder is printed too).

    python tests\chat_panels_server.py [port] [delay_seconds]
"""
import json
import os
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SYS = os.path.join(os.path.dirname(HERE), "engine", "System")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 47933
DELAY = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
tmp = tempfile.mkdtemp(prefix="chatpanels-")
os.environ["ASSISTANT_LIVE_HOME"] = os.path.join(tmp, "Live")
os.makedirs(os.path.join(tmp, "Live", "personal"))
with open(os.path.join(tmp, "Live", "personal", "settings.json"), "w") as f:
    json.dump({"page_port": PORT}, f)
sys.path.insert(0, os.path.join(SYS, "live"))
sys.path.insert(0, os.path.join(SYS, "live_page"))
import texts  # noqa: E402

import datetime as dt
import random

N = 300
random.seed(7)
NOW = time.time()
TX = {}      # conversation -> messages, oldest first
TXNAME = {}  # conversation -> name
PEOPLE = ["Alex Rivera", "Sam Lee", "Jo Park", "Max Cho", "Dana Ortiz", "Kim Walsh", "5551230142", "Pat Quinn"]
WORDS = ["Sounds good", "On my way", "Can you send the file?", "Thanks!", "See you at 7", "I will check and tell you tomorrow, there are a few things to look at first", "Ok", "Running late", "Did you see the new schedule? It changed again this week.", "Yes"]


def times(n, end):
    """n times ending at `end`: bundles of a few messages a minute apart, then gaps of hours and days"""
    out, t = [], end
    for _ in range(n):
        out.append(t)
        t -= random.choice([20, 40, 60, 90, 120, 30, 45, 200, 4000, 9000, 40000]) if random.random() > 0.15 else random.choice([5000, 30000, 100000])
    return list(reversed(out))


for i in range(1, 9):
    grp = i in (2, 5)
    TXNAME["p%d" % i] = "Sam Lee, Jo Park, Max Cho" if i == 2 else "Dana Ortiz, Kim Walsh, Alex Rivera, Pat Quinn" if i == 5 else PEOPLE[i - 1]
    TX["p%d" % i] = [{"id": i * 1000 + k, "ts": dt.datetime.fromtimestamp(t).isoformat(timespec="seconds"), "out": random.random() < 0.4, "text": "%s (%d)" % (random.choice(WORDS), k + 1), "who": ""} for k, t in enumerate(times(N, NOW - 3000 * i * i))]
    if grp:
        for m in TX["p%d" % i]:
            m["who"] = "" if m["out"] else random.choice(TXNAME["p%d" % i].split(", "))




def t_conversations(q="", before="", limit=50):
    rows = [{"id": c, "name": TXNAME[c], "group": c in ("p2", "p5"), "last": TX[c][-1]["text"], "when": TX[c][-1]["ts"], "from_me": TX[c][-1]["out"], "unread": 2 if c == "p3" else 0, "count": len(TX[c])} for c in sorted(TX)]
    return {"ok": True, "rows": rows, "more": False, "next": "", "unread": 0, "drafts": [], "problem": ""}


def t_thread(conv, limit=200, before=""):
    time.sleep(DELAY)
    if conv not in TX:
        return {"ok": False, "error": "That conversation could not be found."}
    msgs = TX[conv]
    page = msgs[-limit:]
    return {"ok": True, "id": conv, "name": TXNAME[conv], "group": conv in ("p2", "p5"), "messages": page, "more": len(msgs) > limit, "can_send": True, "cant_send": "", "sends": [], "drafts": [], "problem": ""}


texts.conversations = t_conversations
texts.thread = t_thread
texts._problem = lambda: ""
texts.mark_read = lambda conv: {"ok": True}


def arrivals():
    flag = os.path.join(tmp, "arrive.flag")
    n = 0
    while True:
        time.sleep(0.5)
        if os.path.exists(flag):
            os.remove(flag)
            n += 1
            for c, ms in TX.items():
                ms.append({"id": int(c[1:]) * 1000 + len(ms) + 500, "ts": dt.datetime.now().isoformat(timespec="seconds"), "out": False, "text": "ARRIVED %d" % n, "who": ""})


threading.Thread(target=arrivals, daemon=True).start()
import local_site  # noqa: E402

local_site.start()
print(tmp, flush=True)
print(local_site.make_setup(), flush=True)
while True:
    time.sleep(60)
