r"""Acceptance of "one assistant everywhere", on a scratch copy laid down from this plugin with made-up mail. Claude's runs are
stood in for (each check names what the run was given and what it answered); everything else is the real program.

- Words typed on a card go to the page's chat, with the card attached: the same instructions, the same conversation, the
  same actions; what it decides lands on the card.
- The same request on a card and in the box at the top gives the same email, in Ready to send.
- A person's address is found in the gathered mail, not asked for.
- Nothing is promised that is not done: a promise is done in the same message, or becomes a job the next check runs.
- A draft an older version left on a card moves to Ready to send.
- A Claude session in the assistant's folder reads the same instructions and conversation, and can put a draft in Ready to send.
Nothing outside the scratch folder changes.

    python tests\one_assistant_acceptance.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                                      # the plugin: this repository
results = []

INSIDE = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
import common, db, items, answers, chat, people, ready
out = {}
p = common.read_json(common.PERSONAL_JSON, {}) or {}
p["send_accounts"] = ["me@work.example"]
common.write_json(common.PERSONAL_JSON, p)
import send
send.accounts = lambda: ["me@work.example"]
send.switched_on = lambda: True
con = db.connect()
items.ensure_on(con)
# Lou is on file only as an address with no name; his name is in the mail's headers
con.execute("INSERT INTO contacts (key, person_id, name) VALUES ('email:lmarsh@northwind.example', 901, NULL)")
body = ('<p>From: Robin Vale</p><p><b>To:</b> Lou Marsh &lt;<a href="mailto:LMARSH@northwind.example">LMARSH@northwind.example</a>&gt;</p>'
        '<p>Hello Lou, the heads never arrived. The cost is $1,310.40.</p>')
mid = con.execute("""INSERT INTO messages (channel, account, provider_id, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)
                     VALUES ('email', 'me@work.example', 'p-1', 't1', now(), 'in', 'email:robin@harbor.example', 'lmarsh@northwind.example',
                     'RE: Northwind paint, invoice 4417201', ?, now()) RETURNING id""", (body,)).fetchone()[0]
con.execute("""INSERT INTO live_items (id, source_key, kind, area, title, detail, state, importance, asks, source_messages,
               created_at, updated_at, state_changed_at)
               VALUES ('L951', 'live:test-951', 'task', 'Work', 'Robin is chasing Northwind for a $1,310.40 credit',
               'Lou Marsh at Northwind says the heads were delivered; Robin says they never arrived.', 'question', 0,
               '["Should we propose splitting the loss with Northwind?"]', ?, now(), now(), now())""", (json.dumps([str(mid)]),))
con.close()
people.write_people()
out["the address is found from the mail, by name"] = [[x["email"][0] for x in people.lookup("Lou", "email")],
                                                      people.settle_asks(["What is Lou's email at Northwind?"])[0]]

# Claude stood in: each run records what it was given and answers from a list
runs, replies = [], []
def run(words, told, sess):
    runs.append({"words": words, "told": told})
    return (replies.pop(0) if replies else "All set."), "", 0.1, {}
chat._run = run
DRAFT = {"type": "draft", "to": ["lmarsh@northwind.example"], "subject": "Northwind heads, invoice 4417201",
         "body": "Lou, nobody has these heads and it cannot be proven what happened to them. We propose splitting the $1,310.40.",
         "why": "The split you asked for."}

def ready_cards():
    return {r["id"]: r for r in items.rows("source_key LIKE 'live:ready-%' AND state <> 'done'")}

# 1. on the card: the chat's own instructions with the card attached; the email goes to Ready to send
items.export("t1")
replies[:] = ["I wrote the split proposal to Lou.\nACTION: " + json.dumps(DRAFT) +
              '\nACTION: {"type": "card", "state": "handled", "settled": [1], "card": null}']
before = set(ready_cards())
res = answers.act_on_answer({"id": "L951", "action": "answer", "text": "Write Lou the split proposal", "at": common.now().isoformat(timespec="seconds"), "device": "test"})
answers.wait_landed(30)
told = runs[-1]["told"]
made = [r for i, r in ready_cards().items() if i not in before]
card = items.rows("id='L951'")[0]
turns = chat.load("L951")["turns"]
out["a card reply runs the chat's own instructions, with the card attached"] = [told.startswith("WORKING INSTRUCTIONS"),
    "THIS MESSAGE WAS TYPED ON ONE CARD" in told, "Robin is chasing Northwind" in told, "Lou Marsh" in told]
out["the card reply is in the card's own conversation, with its card"] = [
    [t.get("who") for t in turns[-2:]], [(t.get("card") or {}).get("id") for t in turns[-2:]]]
out["the email is in Ready to send, answering the card, not on the card"] = [len(made), made and made[0]["draft"]["to"],
    made and (made[0].get("extra") or {}).get("ready", {}).get("about"), card.get("draft")]
out["the card says where the email is and closes its question"] = [card["state"], card["status"], card["asks"]]
out["the card shows the chat's reply"] = "in Drafts, in the Email part" in (res.get("result") or "")
# 2. the same request in the box at the top: the same email
replies[:] = ["I wrote the split proposal to Lou.\nACTION: " + json.dumps(DRAFT)]
before = set(ready_cards())
top = chat.handle("Write Lou at Northwind the split proposal about invoice 4417201")
made2 = [r for i, r in ready_cards().items() if i not in before]
out["the same request in the box at the top gives the same email"] = [len(made2), made2 and made2[0]["draft"]["to"] == made[0]["draft"]["to"],
    made2 and made2[0]["draft"]["subject"] == made[0]["draft"]["subject"]]
out["the box at the top is given the address from the mail"] = "lmarsh@northwind.example" in runs[-1]["told"]

# 3. a promise is done in the same message: a second run, with a fresh search for it
n0 = len(runs)
replies[:] = ["I will search the gathered mail for Lou's address, then write the split proposal.",
              "Done.\nACTION: " + json.dumps(DRAFT)]
before = set(ready_cards())
got = chat.handle("Write the split proposal to Lou")
out["a promise is done in the same message"] = [len(runs) - n0, len([i for i in ready_cards() if i not in before]),
    "I will search" in got["result"], "own next step" in runs[-1]["words"]]
# a promise that cannot be kept now becomes a job the next check runs, and its result is said in the chat
n0 = len(runs)
replies[:] = ["I will look through the older mail for the bill of lading."] * 3
got = chat.handle("Find the bill of lading")
queued = (common.read_json(chat.QUEUE, {}) or {}).get("jobs") or []
out["a promise not kept now is a real job, and says so"] = [len(runs) - n0, len(queued), chat.QUEUED_SAYS in got["result"],
                                                            "I will look" in got["result"]]
replies[:] = ["The bill of lading was signed 4/14 by the shop foreman."]
ran, bad = chat.run_queue()
out["the next check runs it and says the result in the chat"] = [ran, bad, (common.read_json(chat.QUEUE, {}) or {}).get("jobs"),
                                                                 "signed 4/14" in chat.load()["turns"][-1]["text"]]
# a run that asks for an address on file is run again with it
con = db.connect()
con.execute("""INSERT INTO live_items (id, source_key, kind, area, title, state, importance, asks, source_messages, created_at, updated_at, state_changed_at)
               VALUES ('L952', 'live:test-952', 'task', 'Work', 'Northwind credit, second card', 'question', 0, '[]', '[]', now(), now(), now())""")
con.close()
items.export("t2")
n0 = len(runs)
replies[:] = ['I need one thing first.\nACTION: {"type": "card", "state": "question", "ask": "What is Lou Marsh\'s email at Northwind?"}',
              "Written.\nACTION: " + json.dumps(DRAFT) + '\nACTION: {"type": "card", "state": "handled"}']
answers.act_on_answer({"id": "L952", "action": "answer", "text": "send Lou the proposal", "at": common.now().isoformat(timespec="seconds"), "device": "test"})
answers.wait_landed(30)
c2 = items.rows("id='L952'")[0]
out["it never asks for an address on file: it is run again with it"] = [len(runs) - n0, c2["asks"], c2["status"], "lmarsh@northwind.example" in runs[-1]["words"]]

# 4. a draft an older version left on a card goes to Ready to send
db.execute("""UPDATE live_items SET draft=?, status='Draft ready', state='yours' WHERE id='L952'""",
           (json.dumps({"to": ["lmarsh@northwind.example"], "cc": [], "subject": "Forward", "body": "Robin, forwarding the invoice.", "account": "me@work.example"}),))
before = set(ready_cards())
moved, bad = ready.adopt_card_drafts("t3")
c2 = items.rows("id='L952'")[0]
new = [r for i, r in ready_cards().items() if i not in before]
out["an old card draft moves to Ready to send"] = [moved, bad, len(new), new and new[0]["draft"]["subject"], c2["draft"], c2["status"]]

# 5. a Claude session in the assistant's folder
path = os.path.join(common.paths.ROOT, "CLAUDE.md")
note = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
out["the folder has its note for a Claude session"] = [note.startswith("# This folder is your assistant"), "chat.py --instructions" in note]
f = os.path.join(common.HOME, "desk-draft.json")
json.dump(dict(DRAFT, subject="From the desktop"), open(f, "w", encoding="utf-8"))
before = set(ready_cards())
said = ready.from_file(f)
out["a desktop session's draft goes to Ready to send"] = [said.startswith("In Drafts"), len([i for i in ready_cards() if i not in before])]
print(json.dumps(out, default=str))
'''

WANT = {
    "the address is found from the mail, by name": [["lmarsh@northwind.example"], []],
    "a card reply runs the chat's own instructions, with the card attached": [True, True, True, True],
    "the card reply is in the card's own conversation, with its card": [["you", "assistant"], ["L951", "L951"]],
    "the email is in Ready to send, answering the card, not on the card": [1, ["lmarsh@northwind.example"], "L951", None],
    "the card says where the email is and closes its question": ["handled", "Email in Drafts", []],
    "the card shows the chat's reply": True,
    "the same request in the box at the top gives the same email": [1, True, True],
    "the box at the top is given the address from the mail": True,
    "a promise is done in the same message": [2, 1, False, True],
    "a promise not kept now is a real job, and says so": [3, 1, True, False],
    "the next check runs it and says the result in the chat": [1, [], [], True],
    "it never asks for an address on file: it is run again with it": [2, [], "Email in Drafts", True],
    "an old card draft moves to Ready to send": [1, [], 1, "Forward", None, "Email in Drafts"],
    "the folder has its note for a Claude session": [True, True],
    "a desktop session's draft goes to Ready to send": [True, 1],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="one-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_one", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47897",
                            "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=300)
        got = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
        if not got:
            check("the checks ran", r.stderr.strip()[-600:], "")
        for name, want in WANT.items():
            check(name, got.get(name), want)
        r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(live, "chat.py"), "--instructions"], capture_output=True,
                           text=True, encoding="utf-8", env=env, timeout=60)
        check("a desktop session reads the chat's instructions; the card talk stays with its card", (r.returncode, r.stdout.startswith("WORKING INSTRUCTIONS"),
              "Write Lou the split proposal" in r.stdout), (0, True, False))
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "uninstall", "--root", root],
                           capture_output=True, text=True)
        check("taking it off removes the folder's note", os.path.exists(os.path.join(root, "CLAUDE.md")), False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
