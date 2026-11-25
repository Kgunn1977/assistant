r"""Acceptance (quick): Talk to your assistant does what the page's own buttons do, by the owner's words, through the same code.
On a scratch home with made-up data; the Claude run, the mail hand-off, the texts queue and Google are stood in, so nothing is
sent and no real calendar is touched.

  1. calendar add, change and delete: the calendar ACTION reaches the Google connection's add_event, change_event and
     delete_event with the right calendar, event and fields, and the reply says what was done;
  2. send email: "send it" sends the email drafted in the same reply through the page's own Send code (the hand-off gets the
     draft's account, To and subject), the reply says what went, to whom and from which address, and the card closes; without
     the owner's word "send" nothing goes;
  3. send text: the text_send ACTION reaches the Texts part's own Send code (queue_send) with the conversation and the words;
  4. the same from a card reply: words typed on a card add a calendar event through the same code.

    python tests\chat_full_acceptance.py
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
import datetime as dt, json, os, sys
sys.path.insert(0, sys.argv[1])
import common
assert os.path.abspath(common.HOME).startswith(os.path.abspath(sys.argv[2])), "not a scratch home: " + common.HOME
import db, items, answers, chat, calendar_view, texts, settings_page
import send as mailer
from connections import _store
import connections
db.init_schema()
os.makedirs(common.LOGS, exist_ok=True)
os.makedirs(os.path.dirname(common.AI_LOG), exist_ok=True)
common.write_json(common.SETTINGS, dict(common.settings(), owner_send={"on": True}))
out = {}
# the stand-ins: the Claude run gives a canned reply; nothing reaches Google, a mail service or the phone
replies = []
chat._run = lambda words, told, sess: (replies.pop(0), "", 0.1, {})
chat.instructions = lambda *a, **k: ""
chat.found_for = lambda *a, **k: {}
settings_page.at_limit = lambda: False
mailer.accounts = lambda: ["me@example.com"]
handed = []
mailer._handoff = lambda m: handed.append([m["account"], m["to"], m["subject"], m["body"]]) or "stood in"
import ready
ready_make = ready.make
made_actions = []
def make(action, when, n, batch, **k):         # the draft as ready.make keeps it, without the voice pass or the contacts lookup
    made_actions.append(action)
    iid, _ = items.upsert(f"{ready.KEY}{batch}-{n}", "chat", kind="approval", area=ready.AREA, state="question", title=action["subject"],
                          asks=["Send it?"], draft={"account": "me@example.com", "to": action["to"], "cc": [], "bcc": [], "subject": action["subject"],
                                                   "body": action["body"], "type": "new", "files": [], "attach": [], "source": None},
                          source_who="Owner", source_when=when, extra={"ready": {"batch": batch}})
    return iid, ""
ready.make = make
gc = connections.module("google_calendar")
real_listed = connections.listed
connections.listed = lambda kind=None, *a, **k: [{"id": "c1", "type": "google_calendar", "kind": "calendar", "address": "me@example.com"}] if kind == "calendar" else real_listed(kind, *a, **k)
gc.writable = lambda conn: [("me@example.com", "Main"), ("fam@example.com", "Family")]
calls = []
gc.add_event = lambda conn, cid, ev: (calls.append(["add", cid, ev["summary"], ev["start"], ev["end"]]), dict(ev, id="new1", updated="2030-03-01T10:00:00.000Z"))[1]
gc.change_event = lambda conn, cid, eid, f: (calls.append(["change", cid, eid, f]), {"id": eid, "summary": "Dentist", "start": f["start"], "end": f["end"]})[1]
gc.delete_event = lambda conn, cid, eid: calls.append(["delete", cid, eid])
d = dt.datetime(2030, 3, 4)
_store.calendar_events([("ev7", "Family", "Dentist", d + dt.timedelta(hours=9), d + dt.timedelta(hours=10), False, "", "", d),
                        ("ev8", "Main", "Crew lunch", d + dt.timedelta(hours=12), d + dt.timedelta(hours=13), False, "", "", d)], prune=False)
calendar_view._W["at"] = 0
def say(words, reply, card=None):
    replies.append(reply)
    return chat.handle(words, card=card).get("result")
A = lambda o: "ACTION: " + json.dumps(o)
out["calendar add"] = [say("add a site walk on 3/5/2030 at 7:30 am to my calendar",
                           "Done.\n" + A({"type": "calendar", "do": "add", "title": "Site walk", "day": "2030-03-05", "start": "07:30", "end": "08:30"})), calls[-1]]
out["calendar change"] = [say("move the dentist on 3/4 to 2 pm",
                              A({"type": "calendar", "do": "change", "find": "dentist", "on_day": "2030-03-04", "start": "14:00"})), calls[-1][:3], sorted(calls[-1][3])]
out["calendar delete"] = [say("cancel crew lunch on 3/4", A({"type": "calendar", "do": "delete", "find": "crew lunch", "on_day": "2030-03-04"})), calls[-1]]
_store.calendar_events([("ev9", "Family", "Weekend trip", d + dt.timedelta(days=5), d + dt.timedelta(days=7), True, "", "", d)], prune=False)
say("rename the weekend trip to Lake trip", A({"type": "calendar", "do": "change", "find": "weekend trip", "title": "Lake trip", "all_day": None, "place": ""}))
out["all-day rename"] = calls[-1][3]
say("move the lake trip to 3/12/2030", A({"type": "calendar", "do": "change", "find": "weekend trip", "day": "2030-03-12", "all_day": None}))
out["all-day move keeps its days"] = [calls[-1][3]["start"], calls[-1][3]["end"]]
n = len(calls)
out["calendar not on a question"] = [say("should we cancel crew lunch?", A({"type": "calendar", "do": "delete", "find": "crew lunch"})), len(calls) - n]
email = {"type": "draft", "kind": "new", "to": ["pat@example.com"], "subject": "Running late", "body": "Be there at 9."}
out["send email: no send word, nothing goes"] = [say("write Pat that I am running late", A(email) + "\n" + A({"type": "send"})), len(handed)]
out["send email: a question is not a go"] = [say("did Pat send me the invoice? answer him", A(dict(email, subject="Invoice")) + "\n" + A({"type": "send"})),
                                             say("send me a summary of it", A(dict(email, subject="Summary")) + "\n" + A({"type": "send"})), len(handed)]
out["a task reply keeps its words"] = say("remind me to call the shop", "I've added that to your tasks.\n" + A({"type": "task", "title": "Call the shop"}))
r = say("write Pat that I am running late and send it", A(email) + "\n" + A({"type": "send"}))
out["send email"] = [r, handed]
sent = [json.loads(l) for l in open(mailer.SENT_LOG, encoding="utf-8")]
out["send log"] = [sent[-1]["result"], sent[-1]["allowed_by"]]
q = []
texts.queue_send = lambda conv, words, to="", name="", learn=True: (q.append([conv, words, to]), {"ok": True, "id": "t1", "conv": conv})[1]
texts._outbox = lambda: [{"id": "t1", "name": "Pat", "phone": "5551234567"}]
out["send text"] = [say("text Pat I'm on my way, send it", A({"type": "text_send", "conversation": "conv9", "text": "On my way."})), q]
iid, _ = items.upsert("test-card:1", "chat", kind="question", area="Work", state="question", title="Pick a day for the inspection",
                      asks=["Which day?"], source_who="Someone", source_when=d)
card = items.card_for(iid)
r = say("put it on my calendar 3/6/2030 all day", A({"type": "calendar", "do": "add", "title": "Inspection", "day": "2030-03-06", "all_day": True})
        + "\n" + A({"type": "card", "state": "handled", "settled": [1]}), card=card)
out["card reply adds to the calendar"] = [r, calls[-1]]

# --- round 2: the presses that were page-only, and mail organizing -------------------------------------------------------------
import mail, mail_handle, held, rebuild, mail_compose, project_tools, mail_rules
got = []
mail.act = lambda rec: (got.append(json.loads(rec["text"])["mail_act"]), {"ok": True, "items": [], "result": "Done."})[1]
out["one email: label, mark unread"] = [say("label the Acme email Suppliers", A({"type": "mail", "do": "label", "message": 41, "label": "Suppliers"})),
                                        say("mark it unread", A({"type": "mail", "do": "unread", "message": 41})), list(got)]
got.clear()
mail_handle.find = lambda spec: {"ok": True, "count": 2, "ids": [51, 52], "rows": [{"id": 51, "account": "me@example.com", "from": "a@x.example", "subject": "One"},
                                                                                   {"id": 52, "account": "me@example.com", "from": "a@x.example", "subject": "Two"}]}
mail_handle._sample = lambda rows: "One; Two"
p1 = say("star everything from acme", A({"type": "mail_plan", "op": "star", "find": {"from": "acme"}}))
import time; time.sleep(1.2)       # the yes comes in a later message than the plan
g1 = say("yes", A({"type": "mail_go"}))
out["many emails by description: planned, then done on yes"] = [p1, g1, list(got)]
fold = []
class FakeBox:
    FOLDER_DELETE_SAYS = "(stand-in mailbox)"
    folder_create = staticmethod(lambda conn, name, parent=None: fold.append(["create", name, parent]))
    folder_rename = staticmethod(lambda conn, fid, name: fold.append(["rename", fid, name]))
    folder_move = staticmethod(lambda conn, fid, parent=None: fold.append(["move", fid, parent]))
    folder_delete = staticmethod(lambda conn, fid: fold.append(["delete", fid]))
    folder_info = staticmethod(lambda conn, fid: {"total": 3 if fid == "F2" else 0, "children": 0})
    folder_refresh = staticmethod(lambda conn: None)
connections.mailbox = lambda addr: ({"address": addr}, FakeBox) if addr == "me@example.com" else (None, None)
mail_rules._folders = lambda addr: [{"id": "F1", "path": "Clients", "kind": "folder"}, {"id": "F2", "path": "Clients/Old", "kind": "folder"},
                                    {"id": "F3", "path": "Empty", "kind": "folder"}, {"id": "INBOX", "path": "Inbox", "kind": "inbox"}]
M = lambda **k: A(dict({"type": "mail_folder", "account": "me@example.com"}, **k))
out["folders"] = [say("make a folder Suppliers inside Clients", M(do="create", name="Suppliers", parent="Clients")),
                  say("rename Empty to Spare", M(do="rename", folder="Empty", name="Spare")),
                  say("move Clients/Old to the top", M(do="move", folder="Clients/Old")),
                  say("delete the Empty folder", M(do="delete", folder="Empty")),
                  say("delete Clients/Old", M(do="delete", folder="Clients/Old")), list(fold)]
time.sleep(1.2)
out["a folder with mail is deleted only on yes"] = [say("yes", A({"type": "mail_go"})), fold[-1]]
out["the Inbox is never changed"] = say("rename Inbox to Main", M(do="rename", folder="Inbox", name="Main"))
tx = []
texts.mark_read = lambda conv: tx.append(["read", conv]) or {"ok": True}
texts.cancel = lambda sid: tx.append(["cancel", sid]) or {"ok": True}
texts._drafts = lambda: [{"id": "d1", "conv": "c1", "name": "Pat", "text": "hi"}]
texts.discard_draft = lambda did: tx.append(["discard", did]) or {"ok": True}
out["texts"] = [say("mark Pat's texts read", A({"type": "text", "do": "read", "conversation": "c1"})),
                say("don't send that text to Pat", A({"type": "text", "do": "cancel", "id": "q1"})),
                say("throw away the text draft", A({"type": "text", "do": "discard", "id": "d1"})), tx]
shown = []
held.show = lambda mid: (shown.append(mid), (None, "It is on your page now."))[1]
out["I should have seen this"] = [say("show me the hidden Acme email", A({"type": "press", "id": "held-777", "name": "should_have_seen"})), shown]
rb = []
rebuild.start = lambda: (rb.append("start"), (0, "Rebuilding every open card now."))[1]
out["rebuild"] = [say("rebuild all my cards", A({"type": "page", "do": "rebuild_cards"})), say("ok", A({"type": "page", "do": "rebuild_cards"})), rb]
fpath = os.path.join(sys.argv[2], "quote.pdf")
open(fpath, "wb").write(b"%PDF-1.4 stand-in")
made_actions.clear()
say(f"write Pat with {fpath} attached", A(dict(email, subject="Quote", attach_paths=[fpath], files=[{"name": "plan.pdf", "ref": "att:12"}])))
refused = say("write Pat with the settings attached", A(dict(email, subject="X", attach_paths=[os.path.join(common.PERSONAL, "settings.json")])))
out["attach"] = [[f["name"] for f in made_actions[0]["files"]], made_actions[0]["files"][1]["ref"][:3], refused]
mail_compose._sendable = lambda: [({"address": "me@example.com"}, None)]
out["signature"] = [say("set my signature to Pat Owner, Owner Co", A({"type": "signature", "account": "me@example.com", "text": "Pat Owner\nOwner Co"})),
                    mail_compose.signatures().get("me@example.com")]
sys.path.insert(0, os.path.join(os.path.dirname(sys.argv[1]), "live_page"))
import roadmaps, roadmap_press
roadmaps.full_docs = lambda: {"roadmap-abc1234567": {"key": "abc1234567", "name": "Shop", "steps": {"step-02": {"name": "Login", "status": "Ready",
    "checks": [{"id": "c2", "text": "Sign in works"}]}}, "questions": {"q-1": {"row": "step-02", "question": "Which color?", "choices": ["Blue", "Red"], "status": "open"}}}}
rp = []
roadmap_press.handle = lambda rec: (rp.append(json.loads(rec["text"])["roadmap"]), {"ok": True, "result": "Saved. It is on its way to the project's own session."})[1]
say("the login check works on the shop roadmap", A({"type": "roadmap", "project": "abc1234567", "do": "works", "row": "step-02", "check": "c2"}))
say("answer the color question: red", A({"type": "roadmap", "project": "abc1234567", "do": "answer", "question": "q-1", "choice": "b"}))
out["roadmap"] = [[x["op"], x["path"], x["data"].get("result") or x["data"].get("answer")] for x in rp]
pt = []
project_tools.handle = lambda rec: (pt.append([rec["id"].split(":")[1], json.loads(rec["text"])]), {"ok": True, "result": "Sent to the session."})[1]
out["project tool"] = [say("turn on the roadmap for the shop", A({"type": "project_tool", "op": "add", "tool": "roadmap", "folder": "C:/p/shop", "session": "s1"})), pt]
ciid, _ = items.upsert("live:calcard-1", "chat", kind="question", area="Work", state="question", title="Site visit",
                       asks=["When?"], calendar={"title": "Site visit", "date": "2030-03-08", "start": "10:00"}, source_who="Someone", source_when=d)
common.write_json(common.ITEMS_JSON, dict(common.read_json(common.ITEMS_JSON, {}) or {}, items=[items.card_for(ciid)]))
n = len(calls)
r = answers.act_on_answer({"id": ciid, "action": "answer", "page_action": "calendar", "text": "Sat 3/8/30, 10:00 AM",
                           "calendar": {"title": "Site visit", "date": "2030-03-08", "start": "10:00", "end": None, "all_day": False},
                           "at": dt.datetime.now().isoformat(timespec="seconds"), "device": "t"})
card_now = items.card_for(ciid)
out["calendar card's Add to calendar adds it"] = [calls[n:], card_now.get("status"), (card_now.get("assistant_did") or "").split("\n")[-1]]
# put away: the page's own Done press, whatever the card still needs; on a finished card it takes it off the page
piid, _ = items.upsert("test-card:putaway", "chat", kind="question", area="Work", state="question", title="[TEST-A] Final notice",
                       asks=["Which day?"], source_who="Someone", source_when=d)
common.write_json(common.ITEMS_JSON, dict(common.read_json(common.ITEMS_JSON, {}) or {}, items=[items.card_for(piid)]))
r1 = say("put away the TEST-A card", A({"type": "press", "id": piid, "name": "done"}))
out["put away"] = [r1, items.card_for(piid).get("state"), "still needs" in r1]

# the two mailboxes' own folder calls (the network stood in): the address and the method each one uses
from connections import _http
net = []
_http.call_json = lambda method, url, token, obj=None, **k: (net.append([method, url.split("/v1")[-1].split(".0")[-1], obj]), (200, {"id": "new"}))[1]
_http.get_json = lambda url, token, params=None, **k: {"messagesTotal": 4, "name": "Clients"} if "labels/" in url else {"totalItemCount": 2, "childFolderCount": 1}
gm, ms = connections.module("google_mail"), connections.module("microsoft_mail")
gm.token_for = lambda conn: "t"
gm._label_names = lambda token: {"L1": "Clients", "L2": "Clients/Old", "L3": "Spare"}
ms._token = lambda conn: "t"
gm.folder_create({}, "Suppliers", "L1"); gm.folder_rename({}, "L1", "Customers"); gm.folder_move({}, "L3", "L1"); gm.folder_delete({}, "L3")
ms.folder_create({}, "Suppliers", "F1"); ms.folder_rename({}, "F1", "Customers"); ms.folder_move({}, "F2", None); ms.folder_delete({}, "F3")
out["mailbox folder calls"] = [net, gm.folder_info({}, "L1"), ms.folder_info({}, "F1")]
print(json.dumps(out, default=str))
'''

WANT = {
    "calendar add": ["Added to your calendar: \"Site walk\", Tue 3/5, 7:30 AM to 8:30 AM, on your Main calendar.",
                     ["add", "me@example.com", "Site walk", {"dateTime": None}, {"dateTime": None}]],
}


def main():
    tmp = tempfile.mkdtemp(prefix="chatfull-")
    live = os.path.join(PKG, "engine", "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"))
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live, tmp], capture_output=True, text=True, env=env, timeout=300, encoding="utf-8")
    import _cleanup
    _cleanup.remove(tmp)
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        check("the engine checks ran", (r.stdout + r.stderr).strip()[-3000:], "")
        return
    a = got["calendar add"]
    check("calendar add reaches add_event on the main calendar, said back",
          [a[0], a[1][:3], "dateTime" in a[1][3]], [WANT["calendar add"][0], ["add", "me@example.com", "Site walk"], True])
    c = got["calendar change"]
    check("calendar change reaches change_event for the one matching event, keeping its length",
          [c[1], c[2], c[0].startswith("Changed \"Dentist\", Mon 3/4, 9:00 AM")], [["change", "fam@example.com", "ev7"], ["end", "start"], True])
    dl = got["calendar delete"]
    check("calendar delete reaches delete_event", [dl[1], dl[0].startswith("Taken off your calendar: \"Crew lunch\"")],
          [["delete", "me@example.com", "ev8"], True])
    check("a question is not a go: nothing changed", got["calendar not on a question"][1], 0)
    check("without the word send nothing is sent", got["send email: no send word, nothing goes"][1], 0)
    check("\"did Pat send me ...?\" and \"send me ...\" send nothing", got["send email: a question is not a go"][2], 0)
    check("a task reply keeps its own words", got["a task reply keeps its words"].startswith("I've added that to your tasks."), True)
    check("an all-day rename changes only the title", got["all-day rename"], {"summary": "Lake trip"})
    check("an all-day move keeps how many days it spans", got["all-day move keeps its days"], [{"date": "2030-03-12"}, {"date": "2030-03-14"}])
    s = got["send email"]
    check("send it: the page's own Send code hands off the draft, and the reply says what, to whom, from where",
          [s[1], "Sent from me@example.com to pat@example.com: \"Running late\"." in s[0], "Be there at 9." in s[0]],
          [[["me@example.com", ["pat@example.com"], "Running late", "Be there at 9."]], True, True])
    check("the send log records it, allowed by his words", got["send log"],
          ["sent", "your words: write Pat that I am running late and send it"])
    t = got["send text"]
    check("text send reaches queue_send and says to whom", [t[1], "to Pat ((555) 123-4567)" in t[0] or "to Pat (" in t[0]],
          [[["conv9", "On my way.", None]], True])
    g = got["one email: label, mark unread"]
    check("one email: label and mark unread reach mail.act", g[2], [{"message": 41, "act": "label", "label": "Suppliers"}, {"message": 41, "act": "unread"}])
    g = got["many emails by description: planned, then done on yes"]
    check("many emails: planned and shown, then done on yes", [g[0].startswith("I would star (flag) 2 emails"), g[1], [x["act"] for x in g[2]]],
          [True, "Starred 2 of 2 emails.", ["star", "star"]])
    f = got["folders"]
    check("folders: make, rename, move, delete an empty one", f[5], [["create", "Suppliers", "F1"], ["rename", "F3", "Spare"], ["move", "F2", None], ["delete", "F3"]])
    check("a folder holding mail says what is in it and waits", f[4].endswith("holds 3 emails. (stand-in mailbox) Nothing is changed yet: tell me yes to delete it."), True)
    check("it is deleted on his yes", got["a folder with mail is deleted only on yes"][1], ["delete", "F2"])
    check("the Inbox is never changed", got["the Inbox is never changed"].endswith("so I left it as it is."), True)
    check("texts: read, take back, throw away", got["texts"][3], [["read", "c1"], ["cancel", "q1"], ["discard", "d1"]])
    check("I should have seen this reaches the Hidden row's own press", got["I should have seen this"], ["It is on your page now.", [777]])
    check("rebuild only on his words for it", [got["rebuild"][0], got["rebuild"][2]], ["Rebuilding every open card now.", ["start"]])
    a = got["attach"]
    check("attach: a file his words name, and one of his emails' files; never the assistant's own", [a[0], a[1], a[2].startswith("I attach only")],
          [["plan.pdf", "quote.pdf"], "up:", True])
    check("signature saved by the writing screen's own code", got["signature"][1], "<div>Pat Owner<br>Owner Co</div>")
    check("roadmap mark and answer built to its contract and passed to its press code", got["roadmap"],
          [["set", "marks/step-02--c2", "works"], ["update", "questions/q-1", "b. Red"]])
    check("project tool press", got["project tool"][1], [["add-roadmap", {"folder": "C:/p/shop", "session": "s1"}]])
    c = got["calendar card's Add to calendar adds it"]
    check("a calendar card's Add to calendar adds it", [c[0][0][:3], c[1], "Added to your calendar" in c[2]], [["add", "me@example.com", "Site visit"], "Calendar: added", True])
    n = got["mailbox folder calls"]
    check("Gmail and Outlook folder calls", [[x[0], x[1]] for x in n[0]], [
        ["POST", "/users/me/labels"], ["PATCH", "/users/me/labels/L1"], ["PATCH", "/users/me/labels/L2"], ["PATCH", "/users/me/labels/L3"],
        ["DELETE", "/users/me/labels/L3"],
        ["POST", "/me/mailFolders/F1/childFolders"], ["PATCH", "/me/mailFolders/F1"], ["POST", "/me/mailFolders/F2/move"], ["DELETE", "/me/mailFolders/F3"]])
    check("folder contents asked of each", n[1:], [{"total": 4, "children": 1}, {"total": 2, "children": 1}])
    pa = got["put away"]
    check("put away presses the page's Done, which works on a card that still needs something",
          [pa[0], pa[1], pa[2]], ["Marked done.", "done", False])
    k = got["card reply adds to the calendar"]
    check("from a card reply, the same calendar code", [k[1][:3], k[1][3]], [["add", "me@example.com", "Inspection"], {"date": "2030-03-06"}])


main()
for name, ok, got, want in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"\n   got  {got}\n   want {want}"))
print(f"{sum(1 for r in results if r[1])}/{len(results)} passed")
sys.exit(0 if results and all(r[1] for r in results) else 1)
