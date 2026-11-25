r"""Acceptance of the mail system, on a scratch copy laid down from this plugin with a stand-in mail service (a connection
type written into the scratch home's own taught folder: two made-up mailboxes, made-up mail, a PDF). Everything else is the
real program: the runner reads the stand-in like any mailbox, the page server's doors answer a signed-in browser, presses go
through the answers, and a Send press is checked, built and handed to the stand-in, which keeps what it was handed so the
built email can be read back.

- The Mail part: one inbox across both addresses, filtered by address, searched (here and at the service), a thread with its files.
- Archive, delete (to the trash), label, unlabel, mark read and unread, each on one press, and refused plainly when the sign-in
  does not allow changing mail.
- Reply, reply all, forward and new from an email: a draft in Ready to send carrying the original and its PDF.
- The built forward and reply carry the thread (the forwarded-message block and original text; In-Reply-To, References and the
  quote) and the PDF; switching the type and the From works; Bcc goes; a missing attachment refuses the whole send.
- The same forward asked on a card and in the box at the top gives the same kind of draft.
Nothing outside the scratch folder changes.

    python tests\mail_acceptance.py
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
PKG = os.path.dirname(HERE)                                      # the plugin: this repository
results = []

STANDIN = r'''
r"""A stand-in mail service for the acceptance test: its mailboxes are one JSON file (STANDIN_BOX)."""
import datetime as dt
import json
import os
from connections import _store

TYPE = "standin_mail"
NAME = "Stand-in mail"
KIND = "email"
CAN_SEND = True
CAN_ACT = ("archive", "trash", "label", "read")
ACT_SCOPE = "change"
ASKS = []
SETUP = "A stand-in mailbox for the acceptance test."


class NotAllowed(RuntimeError):
    pass


def _load():
    with open(os.environ["STANDIN_BOX"], encoding="utf-8") as f:
        return json.load(f)


def _save(d):
    with open(os.environ["STANDIN_BOX"], "w", encoding="utf-8") as f:
        json.dump(d, f)


def check(conn):
    return "reachable"


def _store_all(conn, ms):
    w = _store.MailWriter(conn["address"])
    for m in ms:
        w.add(m["id"], dt.datetime.fromisoformat(m["ts"]), "out" if m["from"] == conn["address"] else "in", m["from"], ", ".join(m["to"]),
              m["subject"], m["body"], thread_id=m["thread"], attachments=[(n, bytes.fromhex(h)) for n, h in m.get("files", {}).items()],
              state={"unread": m["unread"], "inbox": True, "trashed": False, "labels": [], "cc": ", ".join(m.get("cc", [])),
                     "from_name": m["from_name"], "header_id": m["header_id"], "refs": m.get("refs", "")})
    return w.commit()


def gather(conn, ctx):
    n = _store_all(conn, [m for m in _load()["mail"] if m["account"] == conn["address"]])
    refresh(conn)
    return f"{n} new"


def refresh(conn, ctx=None):
    ms = [m for m in _load()["mail"] if m["account"] == conn["address"]]
    return _store.mail_flags(conn["address"], [m["id"] for m in ms if m.get("inbox", True)], [m["id"] for m in ms if m["unread"]],
                             dt.datetime(2000, 1, 1))


def act(conn, provider_id, what, label=None, thread_id=None):
    d = _load()
    if conn["address"] in d.get("locked", []):
        raise NotAllowed("no")
    d.setdefault("acts", []).append([conn["address"], provider_id, what, label, thread_id])
    _save(d)
    return provider_id


def labels(conn):
    return ["Bills", "Church"]


def search(conn, words, most=25):
    return [m["id"] for m in _load().get("far", []) if m["account"] == conn["address"] and words.lower() in m["subject"].lower()]


def fetch(conn, provider_ids):
    return _store_all(conn, [m for m in _load().get("far", []) if m["id"] in provider_ids])


def headers(conn, provider_id):
    m = next(m for m in _load()["mail"] + _load().get("far", []) if m["id"] == provider_id)
    return {"header_id": m["header_id"], "refs": m.get("refs", ""), "cc": ", ".join(m.get("cc", [])), "from_name": m["from_name"], "thread": m["thread"]}


def attachment(conn, provider_id, name):
    d = _load()
    if d.get("lose"):
        return None
    m = next((m for m in d["mail"] if m["id"] == provider_id), {})
    return bytes.fromhex(m["files"][name]) if name in m.get("files", {}) else None


def send_mime(conn, raw, thread_id=None):
    d = _load()
    d.setdefault("sent", []).append({"from": conn["address"], "raw": raw.decode("utf-8", "replace"), "thread": thread_id})
    _save(d)
    return "sent-1"
'''

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n" + b"x" * 30000

INSIDE = r'''
import datetime as dt, email, email.policy, hashlib, json, os, secrets, sys, time, urllib.request
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, os.path.join(os.path.dirname(sys.argv[1]), "live_page"))
import common, db, items, answers, chat, mail, ready, send, connections
A, B = "me@one.example", "me@two.example"
out = {}
os.makedirs(os.path.join(common.HOME, "taught", "connections"), exist_ok=True)
with open(os.path.join(common.HOME, "taught", "connections", "standin_mail.py"), "w", encoding="utf-8") as f:
    f.write(sys.argv[2])
for cid, addr in (("c1", A), ("c2", B)):
    connections.save({"id": cid, "type": "standin_mail", "address": addr, "label": addr, "send": True, "on": True})
p = common.read_json(common.PERSONAL_JSON, {}) or {}
p["send_accounts"] = [A, B]
common.write_json(common.PERSONAL_JSON, p)
send.switched_on = lambda: True
con = db.connect()
items.ensure_on(con)
con.execute("INSERT INTO contacts (key, person_id, name) VALUES ('email:pay@office.example', 902, 'Pat Payable')")
con.close()

# the runner reads both stand-in mailboxes like any mail
import connections.run as runner
sys.argv = ["run.py", "--kind", "email", "--run-id", "t-mail"]
out["the runner reads both mailboxes"] = runner.main()

# --- the Mail part's list, search and thread ---
r = mail.rows("inbox")
out["one inbox across both addresses"] = [sorted({x["account"] for x in r["rows"]}), len(r["rows"]), [x["unread"] for x in r["rows"]][:1]]
out["filtered by address"] = sorted({x["account"] for x in mail.rows("inbox", B)["rows"]})
inv = [x for x in mail.rows("all", "", "invoice 4410")["rows"]]
out["search finds the invoice"] = [len(inv), inv[0]["subject"] if inv else None, inv[0]["files"] if inv else None]
deep = mail.rows("all", "", "warranty", deep=True)
out["search at the service stores what it finds"] = [x["subject"] for x in deep["rows"]]
t = mail.thread(inv[0]["id"])
out["a thread, oldest first, with its files"] = [[m["subject"] for m in t["messages"]], [f["name"] for f in t["messages"][-1]["files"]],
                                               "Pay this one" in t["messages"][-1]["text"], mail.labels(A)["labels"]]
ref = t["messages"][-1]["files"][0]["ref"]
name, data = mail.file(ref)
out["a file is had from the computer"] = [name, data[:8].decode()]
con = db.connect()
path = con.execute("SELECT saved_path FROM attachments WHERE id = ?", [int(ref[4:])]).fetchone()[0]
con.close()
os.remove(path)
name, data = mail.file(ref)
out["and from the service when the computer no longer holds it"] = [name, data[:8].decode()]

# the page server's doors, for a signed-in browser
import local_site
srv = local_site.start()
tok = secrets.token_urlsafe(48)
csrf = secrets.token_hex(32)
with local_site.changed:
    local_site._save("sessions", {hashlib.sha256(tok.encode()).hexdigest(): {"made": int(time.time()), "seen": int(time.time()),
                     "exp": int(time.time()) + 3600, "len": 3600, "csrf": csrf}})
base = f"http://127.0.0.1:{srv.server_address[1]}"
def door(path, data=None, headers=None):
    req = urllib.request.Request(base + path, data=data, headers=dict({"Cookie": f"{local_site.cookie_name()}={tok}", "Host": f"127.0.0.1:{srv.server_address[1]}"}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
s1, b1 = door("/api/mail?view=inbox")
s2, b2 = door(f"/api/mail/thread?id={inv[0]['id']}")
s3, b3 = door(f"/api/mail/file?ref={ref}")
s4, b4 = door("/api/mail/upload", b"plain words in a file", {"X-Brief-Csrf": csrf, "X-File-Name": "notes%20one.txt", "Origin": base})
s5, _ = door("/api/mail/upload", b"x", {"X-Brief-Csrf": "wrong", "X-File-Name": "x.txt"})
up = json.loads(b4).get("file") or {}
out["the page's doors answer a signed-in browser"] = [s1, len(json.loads(b1)["rows"]) > 0, s2, len(json.loads(b2)["messages"]), s3, b3[:8].decode(),
                                                      s4, up.get("name"), s5]
# --- opening an email asks nothing of the mail service, and answers at once; the Label box's names are asked for apart ---
import time as _t
from connections import _http as _h, _oauth as _o
called = []
def _boom(*a, **k):
    called.append(1)
    raise RuntimeError("the mail service was called")
real = (_h.get_json, _h.post_form, _o.access, connections.mailbox, connections.module)
_h.get_json = _h.post_form = _o.access = connections.mailbox = connections.module = _boom
try:
    th = mail.thread(inv[0]["id"])
    t0 = _t.perf_counter()
    s6, b6 = door(f"/api/mail/thread?id={inv[0]['id']}")
    took = _t.perf_counter() - t0
finally:
    _h.get_json, _h.post_form, _o.access, connections.mailbox, connections.module = real
out["opening an email asks nothing of the mail service"] = [len(th["messages"]), sorted(th), len(called)]
out["the page's thread door answers in under half a second"] = [s6, len(json.loads(b6)["messages"]), took < 0.5]
mail._LABELS.clear()
s7, b7 = door("/api/mail/labels?account=" + A)
asked = []
mod = connections.module("standin_mail")
was = mod.labels
mod.labels = lambda conn: asked.append(1) or ["Gone"]
again = mail.labels(A)["labels"]
mod.labels = was
s8, _ = door("/api/mail/labels?account=nobody")
out["the Label box's names come from their own door, kept 10 minutes"] = [s7, json.loads(b7)["labels"], again, len(asked), s8]
# the sign-in pass is kept until shortly before it runs out, so each call does not first ask for a new one
posts = []
real2 = (_h.post_form, connections.secret, connections.note_granted)
_h.post_form = lambda url, form: posts.append(form) or {"access_token": "pass-" + str(len(posts)), "expires_in": 3600, "scope": "s"}
connections.secret = lambda conn, name: "lasting-one"
connections.note_granted = lambda conn, scope: None
try:
    p1 = _o.access({"id": "z"}, "https://token.example", "cid")
    p2 = _o.access({"id": "z"}, "https://token.example", "cid")
    _o._PASSES[next(iter(_o._PASSES))] = (_t.time() - 1, "pass-1")
    p3 = _o.access({"id": "z"}, "https://token.example", "cid")
finally:
    _h.post_form, connections.secret, connections.note_granted = real2
    _o._PASSES.clear()
out["the sign-in pass is kept until shortly before it runs out"] = [p1, p2, p3, len(posts)]
# --- a junk question card about one sender: Read a sample (stored mail only; nothing changes anywhere) ---
import presses
sys.path.insert(0, common.paths.CORE)
import rules as rules_mod
rid = rules_mod.propose("senders", "judged junk 3 times in a row", "", rules_mod.ALWAYS, pattern="email:dana@vendor.example")
con = db.connect()
for iid, skey in (("L970", presses.JUNK_ASK + "::" + str(rid)), ("L971", presses.JUNK_ASK)):
    con.execute("""INSERT INTO live_items (id, source_key, kind, area, title, detail, state, importance, asks, source_messages, created_at, updated_at, state_changed_at)
                   VALUES (?, ?, 'task', 'Work', 'Junk or never junk?', '', 'yours', 0, '[]', '[]', now(), now(), now())""", (iid, skey))
flags = lambda: con.execute("SELECT m.provider_id, s.unread, s.inbox, s.labels FROM messages m JOIN mail_state s ON s.message_id = m.id ORDER BY 1").fetchall()
before = flags()
con.close()
box_before = open(os.environ["STANDIN_BOX"], encoding="utf-8").read()
s6, b6 = door("/api/mail/sample?card=L970")
j6 = json.loads(b6)
s7, b7 = door(f"/api/mail/sample?card=L970&id={j6['list'][-1]['id']}")
j7 = json.loads(b7)
s8, b8 = door("/api/mail/sample?card=L971")
s9, _ = door("/api/mail/sample?card=L970&id=x")
con = db.connect()          # an HTML part stored for the newest email: the sample says so, as the email view does
con.execute("INSERT INTO mail_html (message_id, html, cids) VALUES (?, '<p>Formatted</p>', '[]')", (j6["message"]["id"],))
con.close()
j6h = json.loads(door("/api/mail/sample?card=L970")[1])
out["a sample carries the html flag of its email"] = [j6["message"]["html"], j6h["message"]["html"], j6h["message"]["remote"]]
out["a junk card's sample: the sender's newest email, the arrows reach only that sender's older ones"] = [
    s6, j6["sender"], [x["subject"] for x in j6["list"]], j6["message"]["from"], "Pay this one" in j6["message"]["text"],
    [f["name"] for f in j6["message"]["files"]], s7, j7["message"]["from"], "Ten years" in j7["message"]["text"],
    json.loads(b8), s9]
out["only a card about one sender offers it"] = [items.lift({"source_key": presses.JUNK_ASK + "::" + str(rid), "state": "yours"}).get("sample"),
                                                items.lift({"source_key": presses.JUNK_ASK, "state": "yours"}).get("sample"),
                                                items.lift({"source_key": presses.JUNK_ASK + "::" + str(rid), "state": "done"}).get("sample")]
con = db.connect()
out["reading a sample changes nothing: no read or unread, nothing at the mail service"] = [flags() == before,
                                                                                        open(os.environ["STANDIN_BOX"], encoding="utf-8").read() == box_before]
con.close()
srv.shutdown()

# --- presses on an email ---
def press(key, obj):
    return answers.act_on_answer({"id": key, "action": "answer", "text": json.dumps(obj), "device": "Computer, Chrome",
                                  "at": common.now().isoformat(timespec="seconds")})
mid = mail.rows("all", A, "lunch")["rows"][0]["id"]
said = [press(f"mail:{mid}:{i}", {"mail_act": dict({"message": mid, "act": a}, **({"label": "Bills"} if "label" in a else {}))})["result"]
        for i, a in enumerate(("read", "unread", "label", "unlabel", "archive", "trash"))]
box = json.load(open(os.environ["STANDIN_BOX"], encoding="utf-8"))
st = mail.thread(mid)["messages"][-1]
out["each mail press is made once, at the service"] = [said, [a[2] for a in box["acts"]], [st["inbox"], st["trashed"], st["unread"], st["labels"]]]
connections.note_granted({"id": "c2"}, "read only")
b_mid = mail.rows("inbox", B)["rows"][0]["id"]
r = press(f"mail:{b_mid}:9", {"mail_act": {"message": b_mid, "act": "archive"}})
out["a sign-in that does not allow changing mail is said plainly"] = [r["result"].startswith("Not done: the sign-in for " + B), connections.can(connections.get("c2"))["archive"],
                                                                       len(json.load(open(os.environ["STANDIN_BOX"], encoding="utf-8"))["acts"])]

# --- drafts started from an email ---
def made(r):
    it = (r.get("items") or [{}])[0]
    d = it.get("draft") or {}
    return it, d
orig = [x for x in mail.rows("all", A, "invoice 4410")["rows"]][0]
fw_it, fw = made(press(f"mail-draft:{orig['id']}:1", {"mail_draft": {"message": orig["id"], "type": "forward"}}))
rp_it, rp = made(press(f"mail-draft:{orig['id']}:2", {"mail_draft": {"message": orig["id"], "type": "reply"}}))
ra_it, ra = made(press(f"mail-draft:{orig['id']}:3", {"mail_draft": {"message": orig["id"], "type": "reply_all"}}))
nw_it, nw = made(press("mail-draft:new:4", {"mail_draft": {"message": None, "type": "new"}}))
out["reply, reply all, forward and new from an email"] = [
    [fw["type"], fw["to"], fw["subject"], [f["name"] for f in fw["files"]], fw["account"], fw["source"]["message"] == orig["id"]],
    [rp["type"], rp["to"], rp["subject"], [f["name"] for f in rp["files"]]],
    [ra["type"], ra["to"], ra["cc"]],
    [nw["type"], nw["to"], nw["files"], bool(fw_it.get("ready", {}).get("made_by"))]]

# --- the built email, read back without sending ---
def rec_for(it, d, **over):
    m = dict({"account": d["account"], "to": d["to"], "cc": d["cc"], "bcc": d.get("bcc", []), "subject": d["subject"], "body": "Please pay this.",
              "type": d["type"], "source": (d.get("source") or {}).get("message"), "files": [{"name": f["name"], "ref": f["ref"]} for f in d["files"]],
              "attach": [f["name"] for f in d["files"]]}, **over)
    m["shown"] = {"account": m["account"], "to": m["to"], "cc": m["cc"], "bcc": m["bcc"], "type": m["type"], "attach": m["attach"]}
    return {"id": it["id"], "action": "answer", "device": "Computer, Chrome", "at": common.now().isoformat(timespec="seconds"),
            "text": json.dumps({"send_email": m})}
def parsed(raw):
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    text = msg.get_body(("plain",)).get_content()
    files = [(p.get_filename(), p.get_content()[:8]) for p in msg.iter_attachments()]
    return msg, text, files
m = send.prepare(rec_for(fw_it, fw, to=["pay@office.example"]), fw_it)
raw, thread = send.built(m)
msg, text, files = parsed(raw)
out["the built forward carries the thread and the PDF"] = [msg["Subject"], msg["To"], "---------- Forwarded message ---------" in text,
    "From: Dana Vendor <dana@vendor.example>" in text, "Pay this one" in text, [(n, d[:4].decode()) for n, d in files]]
m = send.prepare(rec_for(rp_it, rp), rp_it)
raw, thread = send.built(m)
msg, text, files = parsed(raw)
out["the built reply stays in its thread with the PDF"] = [msg["Subject"], msg["In-Reply-To"], msg["References"], thread,
    "Dana Vendor <dana@vendor.example> wrote:" in text, "> Pay this one" in text, [n for n, _d in files]]
m = send.prepare(rec_for(ra_it, ra, account=B, type="reply_all", bcc=["pay@office.example"]), ra_it)
raw, thread = send.built(m)
msg, text, files = parsed(raw)
out["switching the type and the From, with a blind copy"] = [msg["From"], msg["To"], msg["Cc"], msg["Bcc"], msg["In-Reply-To"] is not None]
bad = dict(rec_for(fw_it, fw, to=["pay@office.example"]))
t2 = json.loads(bad["text"]); t2["send_email"]["shown"]["bcc"] = ["someone@else.example"]; bad["text"] = json.dumps(t2)
out["a press whose screen differs is refused"] = send.send_owner_email(bad, fw_it)["result"]

# a missing attachment refuses the whole send; nothing reaches the service
d = json.load(open(os.environ["STANDIN_BOX"], encoding="utf-8")); d["lose"] = True
json.dump(d, open(os.environ["STANDIN_BOX"], "w", encoding="utf-8"))
r = answers.act_on_answer(rec_for(fw_it, fw, to=["pay@office.example"]))
out["a missing attachment blocks Send"] = [r["result"], len(json.load(open(os.environ["STANDIN_BOX"], encoding="utf-8")).get("sent", []))]
d = json.load(open(os.environ["STANDIN_BOX"], encoding="utf-8")); d["lose"] = False
json.dump(d, open(os.environ["STANDIN_BOX"], "w", encoding="utf-8"))

# an upload and a file from another email ride along; Send hands the built email over once
answers.wait_landed()                   # the page's reads answer busy at once while this process lands an answer
other = [x for x in mail.rows("all", B, "")["rows"] if x["files"]][0]
o_ref = mail.thread(other["id"])["messages"][-1]["files"][0]
up = mail.upload("notes one.txt", b"plain words in a file")
r = answers.act_on_answer(rec_for(fw_it, dict(fw, files=fw["files"] + [o_ref, up]), to=["pay@office.example"]))
box = json.load(open(os.environ["STANDIN_BOX"], encoding="utf-8"))
msg, text, files = parsed(box["sent"][-1]["raw"].encode())
out["Send hands over the built email with every file"] = [r.get("sent"), len(box["sent"]), box["sent"][-1]["from"], [n for n, _d in files]]
answers.wait_landed(30)
it_now = answers._row(answers._connect(), fw_it["id"])
out["the sent draft leaves Ready to send"] = [it_now["state"], it_now["status"]]

# --- the same forward asked on a card and in the box at the top ---
con = db.connect()
con.execute("""INSERT INTO live_items (id, source_key, kind, area, title, detail, state, importance, asks, source_messages, created_at, updated_at, state_changed_at)
               VALUES ('L960', 'live:test-960', 'task', 'Work', 'Dana sent invoice 4410', 'Pay goes through Pat Payable.', 'yours', 0, '[]', ?, now(), now(), now())""",
            (json.dumps([str(orig["id"])]),))
con.close()
act = {"type": "draft", "kind": "forward", "message": str(orig["id"]), "to": ["pay@office.example"], "subject": "",
       "body": "Pat, please pay this one.", "why": "Invoices go to Pat."}
told = []
def run(words, given, sess):
    told.append(given)
    a = dict(act, about="L960") if "L960" in given else dict(act)
    return ("I put the forward in Ready to send.\nACTION: " + json.dumps(a)
            + ('\nACTION: {"type": "card", "state": "handled"}' if "L960" in given else "")), "", 0.1, {}
chat._run = run
answers.act_on_answer({"id": "L960", "action": "answer", "text": "Forward this to Pat", "device": "Computer, Chrome",
                       "at": common.now().isoformat(timespec="seconds")})
chat.handle("Forward Dana's invoice 4410 to Pat", common.now().isoformat(timespec="seconds"))
snap = [i for i in (common.read_json(common.ITEMS_JSON, {}) or {}).get("items") or [] if str(i.get("source_key") or "").startswith(ready.KEY)
        and (i.get("draft") or {}).get("type") == "forward" and (i.get("draft") or {}).get("to") == ["pay@office.example"]]
kinds = [[d["draft"]["type"], d["draft"]["subject"], d["draft"]["source"]["message"] == orig["id"], [f["name"] for f in d["draft"]["files"]]] for d in snap]
out["a card and the top box give the same kind of draft"] = [len(kinds), kinds[0] == kinds[-1] if kinds else None, kinds[0] if kinds else None,
                                                             '"emails"' in told[0] and str(orig["id"]) in told[0]]
print(json.dumps(out, default=str))
'''

WANT = {
    "opening an email asks nothing of the mail service": [2, ["messages", "ok"], 0],
    "the page's thread door answers in under half a second": [200, 2, True],
    "the Label box's names come from their own door, kept 10 minutes": [200, ["Bills", "Church"], ["Bills", "Church"], 0, 400],
    "the sign-in pass is kept until shortly before it runs out": ["pass-1", "pass-1", "pass-2", 2],
    "the runner reads both mailboxes": 0,
    "one inbox across both addresses": [["me@one.example", "me@two.example"], 3, [False]],      # one row per conversation
    "filtered by address": ["me@two.example"],
    "search finds the invoice": [1, "Invoice 4410 for the roof", 1],
    "search at the service stores what it finds": ["Warranty for the roof"],
    "a thread, oldest first, with its files": [["Invoice 4410 for the roof", "Invoice 4410 for the roof"], ["Invoice 4410.pdf"], True, ["Bills", "Church"]],
    "a file is had from the computer": ["Invoice 4410.pdf", "%PDF-1.4"],
    "and from the service when the computer no longer holds it": ["Invoice 4410.pdf", "%PDF-1.4"],
    "the page's doors answer a signed-in browser": [200, True, 200, 2, 200, "%PDF-1.4", 200, "notes one.txt", 403],
    "a junk card's sample: the sender's newest email, the arrows reach only that sender's older ones": [
        200, "dana@vendor.example", ["Invoice 4410 for the roof", "Invoice 4410 for the roof", "Warranty for the roof"], "dana@vendor.example", True, ["Invoice 4410.pdf"],
        200, "dana@vendor.example", True, {"ok": False, "error": "This card does not name one sender."}, 400],
    "a sample carries the html flag of its email": [False, True, False],
    "only a card about one sender offers it": [True, None, None],
    "reading a sample changes nothing: no read or unread, nothing at the mail service": [True, True],
    "each mail press is made once, at the service": [["Marked read.", "Marked unread.", 'Labeled "Bills".', 'Took off the label "Bills".', "Archived.", "Moved to the trash."],
                                                     ["read", "unread", "label", "unlabel", "archive", "trash"], [False, True, True, []]],
    "a sign-in that does not allow changing mail is said plainly": [True, False, 6],
    "reply, reply all, forward and new from an email": [
        ["forward", [], "Fwd: Invoice 4410 for the roof", ["Invoice 4410.pdf"], "me@one.example", True],
        ["reply", ["dana@vendor.example"], "Re: Invoice 4410 for the roof", ["Invoice 4410.pdf"]],
        ["reply_all", ["dana@vendor.example", "sam@vendor.example"], ["lee@vendor.example"]],
        ["new", [], [], True]],
    "the built forward carries the thread and the PDF": ["Fwd: Invoice 4410 for the roof", "pay@office.example", True, True, True, [["Invoice 4410.pdf", b"%PDF"]]],
    "the built reply stays in its thread with the PDF": ["Re: Invoice 4410 for the roof", "<m2@vendor.example>", "<m1@vendor.example> <m2@vendor.example>", "t-roof",
                                                         True, True, ["Invoice 4410.pdf"]],
    "switching the type and the From, with a blind copy": ["me@two.example", "dana@vendor.example, sam@vendor.example", "lee@vendor.example", "pay@office.example", True],
    "a press whose screen differs is refused": "Not sent. What was on your screen is not what would be sent, so nothing was sent. Open it and press Send again.",
    "a missing attachment blocks Send": ['Not sent. Not sent: "Invoice 4410.pdf" is no longer on that email at me@one.example. Nothing was sent.', 0],
    "Send hands over the built email with every file": [True, 1, "me@one.example", ["Invoice 4410.pdf", "Quote 77.pdf", "notes one.txt"]],
    "the sent draft leaves Ready to send": ["done", "Sent"],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def box():
    def mail(i, account, thread, ts, frm, name, to, subject, body, unread, header, refs="", cc=(), files=None):
        return {"id": i, "account": account, "thread": thread, "ts": ts, "from": frm, "from_name": name, "to": list(to), "cc": list(cc),
                "subject": subject, "body": body, "unread": unread, "header_id": header, "refs": refs, "files": files or {}}
    return {"mail": [
        mail("p1", "me@one.example", "t-roof", "2026-11-10T09:00:00", "dana@vendor.example", "Dana Vendor", ["me@one.example"],
             "Invoice 4410 for the roof", "<p>Here is the quote first.</p>", False, "<m1@vendor.example>"),
        mail("p2", "me@one.example", "t-roof", "2026-11-12T09:00:00", "dana@vendor.example", "Dana Vendor", ["me@one.example", "sam@vendor.example"],
             "Invoice 4410 for the roof", "<p>Pay this one, invoice 4410.</p><p>Thanks</p>", True, "<m2@vendor.example>", "<m1@vendor.example>",
             cc=["lee@vendor.example", "me@two.example"], files={"Invoice 4410.pdf": PDF.hex()}),
        mail("p3", "me@one.example", "t-lunch", "2026-11-13T09:00:00", "kim@friends.example", "Kim", ["me@one.example"],
             "Lunch Friday", "Lunch Friday at noon?", False, "<m3@friends.example>"),
        mail("q1", "me@two.example", "t-quote", "2026-11-11T09:00:00", "ray@supply.example", "Ray", ["me@two.example"],
             "Quote 77", "The quote is attached.", True, "<m4@supply.example>", files={"Quote 77.pdf": PDF.hex()})],
        "far": [mail("f1", "me@one.example", "t-old", "2025-01-02T09:00:00", "dana@vendor.example", "Dana Vendor", ["me@one.example"],
                     "Warranty for the roof", "Ten years.", False, "<m9@vendor.example>")]}


def main():
    tmp = tempfile.mkdtemp(prefix="mail-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    standin_box = os.path.join(tmp, "standin.json")
    with open(standin_box, "w", encoding="utf-8") as f:
        json.dump(box(), f)
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home, STANDIN_BOX=standin_box)
    spec = importlib.util.spec_from_file_location("assistant_copy_mail", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47896",
                            "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live, STANDIN], capture_output=True, text=True, env=env, timeout=600)
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
        except ValueError:
            got = {}
        if not got:
            check("the checks ran", r.stderr.strip()[-1500:], "")
        for name, want in WANT.items():
            want = json.loads(json.dumps(want, default=lambda b: b.decode()))
            check(name, got.get(name), want)
        sent = json.load(open(standin_box, encoding="utf-8")).get("sent", [])
        check("nothing else was handed to the mail service", len(sent), 1)
        # an update brings an older home's database forward before its check pass reads mail (the mail table was missing)
        drop = ("import sys; sys.path.insert(0, sys.argv[1]); import db; c = db.connect(); c.execute('DROP TABLE mail_state'); c.close(); "
                "print(len([t for t in db.tables() if t == 'mail_state']))")
        r = subprocess.run([sys.executable, "-c", drop, live], capture_output=True, text=True, env=env)
        sj = os.path.join(root, "Shipped", "shipped.json")
        d = json.load(open(sj, encoding="utf-8"))
        d["version"] = "0.0.9"
        json.dump(d, open(sj, "w", encoding="utf-8"))
        u = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "update-apply", "--root", root],
                           capture_output=True, text=True, env=env, timeout=900)
        r2 = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); import db; print(len([t for t in db.tables() if t == 'mail_state']))", live],
                            capture_output=True, text=True, env=env)
        health = json.load(open(os.path.join(home, "health.json"), encoding="utf-8")).get("last_pass") or {}
        check("an update makes the tables a new version reads, before its check pass", (r.stdout.strip(), u.returncode, r2.stdout.strip(), health.get("outcome")),
              ("0", 0, "1", "ok"))
    finally:
        _cleanup.remove(tmp)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
