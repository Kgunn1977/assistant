r"""Acceptance: "Cards made simpler" in the engine, on a scratch copy laid down from this plugin with made-up cards built like the
real ones (an unpaid-invoice card with two papers and two messages; a two-question card) and Claude as a stand-in.

- A typed question on the invoice card: the card stays on the page with its questions, "Reading..." (status Thinking) until it is
  read, and the reply is written into the card's Conversation (its history), not only into the chat at the top.
- A typed answer that settles the card closes it.
- Question 2's own button answers question 2 only; the card stays for question 1. Other on question 2: the words reach the
  assistant as question 2's answer.
- Not needed: Just this one closes the card; Everything from this sender puts the sender on the junk list; Other, in his words,
  becomes a rule card to approve.
- The card carries each paper with the reference that opens it, and its messages; the page's door shows a PDF as a PDF and a
  picture as a picture, inside the page only; the page may frame its own papers and nothing else.
- Why it is here: two sentences at most, no label. Each question keeps its own choices and recommended answer.

    python tests\card_plan_engine_acceptance.py
"""
import importlib.util
import json
import os
import shutil
import _cleanup  # noqa: E402  the scratch folder goes when the test ends
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"
JPG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")

INSIDE = r'''
import datetime as dt, hashlib, json, os, secrets, sys, time, urllib.request
live = sys.argv[1]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(os.path.dirname(live), "live_page"))
import common, db, items, answers, chat, card, filters, teach, presses
from connections import _store
out = {}
PDF, JPG = bytes.fromhex(sys.argv[2]), bytes.fromhex(sys.argv[3])

# --- the made-up invoice card: two emails, a PDF and a picture ---
w = _store.MailWriter("me@one.example")
w.add("m1", dt.datetime(2026, 11, 3, 9, 41), "out", "me@one.example", "dana@vendor.example", "Invoices 1101 and 1102", "Please find the invoices attached.",
      thread_id="t1", attachments=[("Invoice 1101.pdf", PDF), ("Site photo.jpg", JPG)],
      state={"unread": False, "inbox": True, "trashed": False, "labels": [], "cc": "", "from_name": "Me", "header_id": "<m1@one.example>", "refs": ""})
w.add("m2", dt.datetime(2026, 11, 16, 8, 0), "in", "dana@vendor.example", "me@one.example", "Re: Invoices 1101 and 1102", "We will look into it.",
      thread_id="t1", attachments=[], state={"unread": True, "inbox": True, "trashed": False, "labels": [], "cc": "", "from_name": "Dana", "header_id": "<m2@vendor.example>", "refs": "<m1@one.example>"})
w.commit()
c = db.connect()
mids = [r[0] for r in c.execute("SELECT id FROM messages ORDER BY ts").fetchall()]
c.close()
long_why = "Two invoices to Acme, $6,000 in all, are unpaid. One was due 10/1, and there has been no reply in over two weeks. A third sentence that never shows."
iid, _ = items.upsert("live:inv-1", "t", kind="question", area="Work", state="question", title="Acme Supply owes Bayside Fire $6,000 on invoices 1101 and 1102",
                      detail="You emailed Dana Invoice 1101.pdf and the site photo on 11/3.", recommended="Send Dana a short reminder about both invoices.",
                      asks=["Remind Dana about the $6,000?"], why="Here because: " + long_why, source_who="Dana", source_when=common.now(), source_messages=mids)
items.export("t")
inv = items.card_for(iid, wait=True)
out["the card's why: two sentences at most, no label"] = inv["why"]
out["the card carries its papers with the reference that opens them, and its two messages"] = [
    sorted((d["file"], d.get("kind"), str(d.get("ref") or "")[:4]) for d in inv.get("documents") or []),
    [(m["who"], m["subject"]) for m in inv.get("messages") or []]]

# --- Claude, standing in: a reply for a question; an ACTION that settles the card for an answer ---
said_to = []
def stand_in(words, told, sess):
    said_to.append(words)
    if "send both of these" in words:
        return ("Both went out 11/3 at 9:41 AM, to dana@vendor.example.", "", 0.1, {})
    return ('Done: the reminder is not needed, Dana paid.\nACTION: {"type": "card", "state": "done", "settled": [1]}', "", 0.1, {})
chat._run = stand_in
import card_rules
card_rules._claude = lambda prompt, timeout=None: ('{"rule": "", "way": "card_rule", "say": "Only about this card."}', "", 0.1)     # the rule check: not a rule

# 3. a typed question: the card stays, the reply lands in its Conversation
before = answers.transform(dict(inv), {"id": iid, "action": "answer", "text": "When did I send both of these invoices?", "at": "2026-11-19T08:32:00"})
out["typed words: before they are read the card keeps its place, its questions, Reading..."] = [before.get("state"), "asks" in before, before.get("status")]
r = answers.act_on_answer({"id": iid, "action": "answer", "text": "When did I send both of these invoices?", "at": "2026-11-19T08:32:00"})
answers.wait_landed()
got = items.card_for(iid, wait=True)
out["a typed question: the card stays open with its question"] = [r.get("ok"), got["state"], got["asks"]]
out["... and the reply is in the card's Conversation, after his question"] = [
    [l for l in str(got["assistant_did"]).split("\n") if "send both" in l or "Both went out" in l]]
out["... kept in the card's own conversation, not in the chat at the top"] = [any("Both went out" in str(t.get("text")) for t in chat.load(iid)["turns"]),
    any("Both went out" in str(t.get("text")) for t in chat.load()["turns"])]

# 3. a typed answer that settles it closes it
r = answers.act_on_answer({"id": iid, "action": "answer", "text": "Dana paid this morning, no reminder needed.", "at": "2026-11-19T09:00:00"})
answers.wait_landed()
out["a typed answer that settles the card closes it"] = [r.get("ok"), items.card_for(iid, wait=True)["state"]]

# 4. a two-question card, each question with its own choices and recommended answer
q2, _ = items.upsert("live:two-1", "t", kind="question", area="Work", state="question", title="Acme invoices",
                     asks=["Remind Dana?", "Charge late fees on 1101?"], recommended="Remind Dana, no late fee.", source_who="Dana", source_when=common.now())
ex = items.card_extras({"state": "question", "asks": ["Remind Dana?", "Charge late fees on 1101?"], "choices": ["Send reminder", "Keep waiting"], "recommended_choice": "Send reminder",
                        "ask_choices": [{"choices": ["Send reminder", "Keep waiting"], "recommended_choice": "Send reminder"},
                                        {"choices": ["No late fee", "Add late fee"], "recommended_choice": "No late fee"}]})
items.update(q2, "t", **ex)
items.export("t")
two = items.card_for(q2, wait=True)
out["each question keeps its own choices, its recommended answer first"] = [
    [(q["ask"], [(c["label"].replace(" (recommended)", ""), bool(c.get("recommended"))) for c in q["choices"]]) for q in two["questions"]]]
r = answers.act_on_answer({"id": q2, "action": "answer", "label": "No late fee", "text": "No late fee", "question": 2, "at": "2026-11-19T09:10:00"})
answers.wait_landed()
two = items.card_for(q2, wait=True)
out["question 2's button answers question 2 only; the card stays for question 1"] = [r.get("ok"), two["state"], two["asks"],
    next((l for l in str(two["assistant_did"]).split("\n") if l.startswith('Answered by you: "Charge')), "")]
said_to.clear()
r = answers.act_on_answer({"id": q2, "action": "answer", "text": "Only if they are 30 days late", "question": 1, "at": "2026-11-19T09:20:00"})
answers.wait_landed()
out["Other on a question: the words reach the assistant as that question's answer"] = [r.get("ok"), any('My answer to question 1 ("Remind Dana?"): Only if they are 30 days late' in w for w in said_to)]

# 5. Not needed, each of the three choices
def fresh(n):
    i, _ = items.upsert(f"live:nn-{n}", "t", kind="fyi", area="Work", state="handled", title=f"Sale {n}", source_who="Dana", source_when=common.now(), source_messages=[mids[1]])
    items.export("t")
    return i
def press(i, p):
    out_ = answers.act_on_answer({"id": i, "action": "answer", "text": json.dumps({"press": p}), "at": "2026-11-19T10:00:00"})
    answers.wait_landed()
    return out_
a = fresh(1); press(a, {"name": "not_needed", "scope": "this"})
out["Not needed, Just this one: the card closes"] = items.card_for(a, wait=True)["state"]
b = fresh(2); press(b, {"name": "junk"})
listed = filters.rules if False else None
out["Not needed, Everything from this sender: the card closes and the sender is junked"] = [items.card_for(b, wait=True)["state"],
    "dana@vendor.example" in json.dumps(presses._rules().parse("senders")).lower()]
asked = []
teach._claude = lambda prompt, model: (asked.append(prompt) or ('{"rule": "Hide sale emails from this vendor.", "note": "From his words."}', "", 0.1, {}))
cc = fresh(3); rr = press(cc, {"name": "not_needed", "scope": "kind", "words": "sale emails from this vendor"})
rules = [x for x in items.rows("source_key LIKE 'rule:%'")]
out["Not needed, Other: his words become a rule card to approve"] = [items.card_for(cc, wait=True)["state"], [(x["status"], x["title"]) for x in rules],
    any("sale emails from this vendor" in p for p in asked)]

# 6. the papers open as themselves, on the page served from the computer
import local_site
srv = local_site.start()
tok = secrets.token_urlsafe(48)
with local_site.changed:
    local_site._save("sessions", {hashlib.sha256(tok.encode()).hexdigest(): {"made": int(time.time()), "seen": int(time.time()),
                     "exp": int(time.time()) + 3600, "len": 3600, "csrf": secrets.token_hex(32)}})
base = f"http://127.0.0.1:{srv.server_address[1]}"
def door(path):
    req = urllib.request.Request(base + path, headers={"Cookie": f"{local_site.cookie_name()}={tok}", "Host": f"127.0.0.1:{srv.server_address[1]}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, dict(resp.headers), resp.read()
refs = {d["file"]: d["ref"] for d in inv["documents"]}
s1, h1, b1 = door("/api/mail/file?ref=" + refs["Invoice 1101.pdf"].replace(":", "%3A") + "&view=1")
s2, h2, b2 = door("/api/mail/file?ref=" + refs["Site photo.jpg"].replace(":", "%3A") + "&view=1")
s3, h3, b3 = door("/api/mail/file?ref=" + refs["Invoice 1101.pdf"].replace(":", "%3A"))
s4, h4, _ = door("/")
out["a PDF opens as the PDF, inside the page only"] = [s1, h1.get("Content-Type"), h1.get("Content-Disposition", "")[:6], h1.get("X-Frame-Options"), b1[:5].decode()]
out["a picture opens as the picture"] = [s2, h2.get("Content-Type"), b2[:3] == JPG[:3]]
out["without view the paper is still a download"] = [s3, h3.get("Content-Type"), h3.get("Content-Disposition", "")[:10]]
out["the page may frame its own papers and nothing else"] = ["frame-src 'self'" in h4.get("Content-Security-Policy", ""), "frame-ancestors 'none'" in h4.get("Content-Security-Policy", "")]
import dates
shown = dates.show_card({"rec_front": "Put the visit on your calendar for {day:2026-11-19}, 6:00 to 6:15 AM.",
                         "questions": [{"ask": "Keep {day:2026-11-19}?", "choices": [{"label": "Yes, {day:2026-11-19}", "text": "Yes, {day:2026-11-19}"}, "Move to {day:2026-11-20}"]}],
                         "choices": ["Move to {day:2026-11-20}"]}, today=dt.date(2026, 11, 19))
out["day markers on the front are worded for today"] = "{day:" not in json.dumps(shown)
print(json.dumps(out, default=str))
'''

WHY = "Two invoices to Acme, $6,000 in all, are unpaid. One was due 10/1, and there has been no reply in over two weeks."
WANT = {
    "the card's why: two sentences at most, no label": WHY,
    "the card carries its papers with the reference that opens them, and its two messages":
        [[["Invoice 1101.pdf", "pdf", "att:"], ["Site photo.jpg", "image", "att:"]], [["You", "Invoices 1101 and 1102"], ["Dana", "Re: Invoices 1101 and 1102"]]],
    "typed words: before they are read the card keeps its place, its questions, Reading...": [None, False, "Thinking"],
    "a typed question: the card stays open with its question": [True, "question", ["Remind Dana about the $6,000?"]],
    "... and the reply is in the card's Conversation, after his question":
        [['You wrote 11/19 8:32 AM: "When did I send both of these invoices?"', "Both went out 11/3 at 9:41 AM, to dana@vendor.example."]],
    "... kept in the card's own conversation, not in the chat at the top": [True, False],
    "a typed answer that settles the card closes it": [True, "done"],
    "each question keeps its own choices, its recommended answer first":
        [[["Remind Dana?", [["Send reminder", True], ["Keep waiting", False]]], ["Charge late fees on 1101?", [["No late fee", True], ["Add late fee", False]]]]],
    "question 2's button answers question 2 only; the card stays for question 1":
        [True, "question", ["Remind Dana?"], 'Answered by you: "Charge late fees on 1101?" (No late fee)'],
    "Other on a question: the words reach the assistant as that question's answer": [True, True],
    "Not needed, Just this one: the card closes": "done",
    "Not needed, Everything from this sender: the card closes and the sender is junked": ["done", True],
    "Not needed, Other: his words become a rule card to approve": ["done", [["Rule proposed", "New rule: Hide sale emails from this vendor."]], True],
    "a PDF opens as the PDF, inside the page only": [200, "application/pdf", "inline", "SAMEORIGIN", "%PDF-"],
    "a picture opens as the picture": [200, "image/jpeg", True],
    "without view the paper is still a download": [200, "application/octet-stream", "attachment"],
    "the page may frame its own papers and nothing else": [True, True],
    "day markers on the front are worded for today": True,
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="cardplan-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_cardplan", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47915",
                            "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live, PDF.hex(), JPG.hex()], capture_output=True, text=True, env=env, timeout=900)
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = {}
            check("the checks ran", r.stderr.strip()[-2000:], "")
        for name, want in WANT.items():
            check(name, got.get(name), json.loads(json.dumps(want)))
    finally:
        _cleanup.remove(tmp)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
