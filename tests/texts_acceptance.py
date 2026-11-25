r"""Acceptance: the Texts part of the page, on made-up texts only, in a scratch home (never the owner's, nothing sent to any real service).

  1. the list and a thread: newest first, names from contacts, a person's backup thread and Google Messages conversation as one,
     a group by its people, search, unread marks (texts already here are read; new ones are unread until opened);
  2. sending: the page's Send press queues a text at its own door (same address and page token only); a STUB extension (this test,
     speaking the extension's door with its token) takes it once, reports sent or failed; a wrong token and the public name are refused;
     an unreported text is failed, never resent; a text drafted by the assistant is never queued;
  3. the extension's files: the manifest's permissions are the known set, its version is raised, and the only code that types is behind the queue.

    python tests\texts_acceptance.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


INSIDE = r'''
import datetime as dt, json, os, sys, urllib.request, urllib.error, hashlib, secrets, time
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, os.path.join(os.path.dirname(sys.argv[1]), "live_page"))
import common, db, texts, textlink
from connections import _store
db.init_schema()
import socket
sk = socket.socket(); sk.bind(("127.0.0.1", 0)); free = sk.getsockname()[1]; sk.close()
common.write_json(common.SETTINGS, {"page_port": free})
out = {}
now = dt.datetime.now().replace(microsecond=0)
ph = _store.phone_key
def bk(i, who, name, direction, text, mins):
    return {"provider_id": f"bk:{who}:{i}:{direction}", "thread": who, "ts": now - dt.timedelta(minutes=mins), "direction": direction,
            "key": ph(who), "name": name, "text": text, "media": []}
_store.text_messages([bk(1, "+15550100199", "Alex Example", "in", "Are we still on for dinner?", 600), bk(2, "+15550100199", "Alex Example", "out", "Yes, see you at 6", 590),
                      bk(3, "+15550100177", "Pat Sample", "in", "Bring the ladder tomorrow", 300)])
def gm(i, conv, direction, text, mins, who="", name="", group=False):
    key = ph(who) if who else (None if group else ph("+1 (555) 010-0199"))
    return {"provider_id": f"gm:{conv}:{i}", "thread": conv, "ts": now - dt.timedelta(minutes=mins), "direction": direction, "key": key, "name": name, "text": text, "media": []}
_store.text_messages([gm("a1", "101", "in", "Running late, start without me", 120, name="Alex Example"),
                      gm("g1", "202", "in", "Group hello from Sam", 60, who="Sam Sample", group=True),
                      gm("g2", "202", "in", "Jo here too", 59, who="Jo Test", group=True)])
r = texts.conversations()
out["list"] = [[x["name"], x["group"], x["count"]] for x in r["rows"]]
out["unread at first look"] = [x["unread"] for x in r["rows"]]
alex = [x for x in r["rows"] if x["name"] == "Alex Example"][0]["id"]
t = texts.thread(alex)
out["thread"] = [[m["out"], m["text"]] for m in t["messages"]]
out["can answer"] = [t["can_send"], t["name"]]
gid = [x["id"] for x in r["rows"] if x["group"]][0]
g = texts.thread(gid)
out["group"] = [g["name"], [m["who"] for m in g["messages"]], g["can_send"]]
out["search"] = [[x["name"] for x in texts.conversations("ladder")["rows"]], [x["name"] for x in texts.conversations("alex")["rows"]], texts.conversations("nothing like this")["rows"]]
d = texts._marks(); d["base"] = (now - dt.timedelta(minutes=5)).isoformat(timespec="seconds"); d["read"] = {}; common.write_json(texts.READ, d)      # the page first looked five minutes ago
_store.text_messages([gm("a2", "101", "in", "Made it", 2, name="Alex Example")])
r2 = texts.conversations()
al = [x for x in r2["rows"] if x["name"] == "Alex Example"][0]
out["new text"] = [r2["rows"][0]["name"], al["unread"], al["last"]]
texts.thread(alex)
out["after opening"] = [x["unread"] for x in texts.conversations()["rows"] if x["name"] == "Alex Example"]

import local_site
srv = local_site.start()
import texts_cache
texts_cache.ON = False          # these checks write the database directly and read it back; the page's small copy has its own checks (google_messages_acceptance)
port = srv.server_address[1]
local_site.time.sleep = lambda s: None
def req(path, body=None, token=None, host=None, cookie=None, csrf=None):
    h = {"Host": host or f"127.0.0.1:{port}", "Content-Type": "application/json"}
    if token: h["X-Messages-Token"] = token
    if cookie: h["Cookie"] = cookie
    if csrf: h["X-Brief-Csrf"] = csrf
    rq = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=None if body is None else json.dumps(body).encode(), method="GET" if body is None else "POST", headers=h)
    try:
        with urllib.request.urlopen(rq, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, None
tok = secrets.token_urlsafe(48); csrf = secrets.token_hex(32)
local_site._save("sessions", {hashlib.sha256(tok.encode()).hexdigest(): {"made": int(time.time()), "seen": int(time.time()), "exp": int(time.time()) + 3600, "len": 3600, "csrf": csrf}})
ck = f"{local_site.cookie_name()}={tok}"
page = lambda path, body=None: req(path, body, cookie=ck, csrf=csrf)
# the texts link stood in as signed in: the queue is handed out to its sender here (next_send) and reported on (report); nothing is sent
textlink.signed_in = lambda st=None: True
ext = "link"
def queue(body, token=None, host=None):
    if body.get("report"):
        return 200, texts.report(str(body["report"]), bool(body.get("ok")), body.get("error") or "")
    return 200, {"ok": True, "send": texts.next_send()}
s, lst = page("/api/texts")
out["door list"] = [s, len(lst["rows"])]
ss, st = page("/api/texts/status")
out["door status"] = [ss, st.get("ok"), isinstance(st.get("problem"), str)]
out["signed out"] = [req("/api/texts")[0], req("/api/texts/thread?id=x")[0]]
s, th = page("/api/texts/thread?id=" + alex)
out["door thread"] = [s, th["name"], len(th["messages"]), th["can_send"]]
out["send without page token"] = [req("/api/texts/send", {"conv": alex, "text": "hi"}, cookie=ck)[0], req("/api/texts/send", {"conv": alex, "text": "hi"})[0]]
out["nothing queued"] = [queue({}, ext)[1]["send"], texts.outbox_for(alex)]
out["empty"] = page("/api/texts/send", {"conv": alex, "text": " "})[1]
s, r = page("/api/texts/send", {"conv": alex, "text": "On my way, 10 minutes"})
sid1 = r["id"]
out["queued"] = [s, r["ok"], [x["status"] for x in texts.outbox_for(alex)]]
out["the extension's doors are gone"] = [req("/api/messages/queue", {})[0] != 200, req("/api/messages/ingest", {})[0] != 200]
out["untouched by them"] = [x["status"] for x in texts.outbox_for(alex)]
s, got = queue({}, ext)
out["taken"] = [s, got["send"]["text"], got["send"]["conv"], got["send"]["id"] == sid1]
out["once"] = queue({}, ext)[1]["send"]
out["shows sending"] = [x["status"] for x in page("/api/texts/thread?id=" + alex)[1]["sends"]]
out["unknown report"] = queue({"report": "nope", "ok": True}, ext)[1]["ok"]
out["sent once"] = [queue({"report": sid1, "ok": True}, ext)[1]["ok"], queue({"report": sid1, "ok": False, "error": "x"}, ext)[1]["ok"], [x["status"] for x in texts.outbox_for(alex)]]
out["sent line shows"] = [x["status"] for x in page("/api/texts/thread?id=" + alex)[1]["sends"]]
_store.text_messages([gm("a3", "101", "out", "On my way, 10 minutes", 0, name="Alex Example")])
th = page("/api/texts/thread?id=" + alex)[1]
out["read back"] = [th["sends"], th["messages"][-1]["text"]]
s, r = page("/api/texts/send", {"conv": alex, "text": "Second one"})
sid2 = r["id"]; queue({}, ext); queue({"report": sid2, "ok": False, "error": "the Send button was not found"}, ext)
f = [x for x in texts.outbox_for(alex) if x["id"] == sid2][0]
out["failed"] = [f["status"], f["error"]]
s, r = page("/api/texts/send", {"conv": alex, "text": "Third one"})
sid3 = r["id"]
out["take back"] = [page("/api/texts/cancel", {"id": sid3})[1]["ok"], [x["status"] for x in texts.outbox_for(alex) if x["id"] == sid3], page("/api/texts/cancel", {"id": sid1})[1]["ok"]]
s, r = page("/api/texts/send", {"conv": alex, "text": "Fourth"})
sid4 = r["id"]; queue({}, ext)
items = texts._outbox_all()
for it in items:
    if it["id"] == sid4:
        it["taken"] = (dt.datetime.now() - dt.timedelta(seconds=texts.LEASE_SECONDS + 5)).isoformat(timespec="seconds")
common.write_json(texts.OUTBOX, {"items": items})
items = texts._outbox_all()
n_old = secrets.token_hex(4)
items.append({"id": n_old, "conv": alex, "gm": "101", "phone": "", "name": "Alex Example", "text": "stale", "status": "queued",
              "created": (dt.datetime.now() - dt.timedelta(seconds=texts.QUEUE_SECONDS + 5)).isoformat(timespec="seconds"), "updated": "", "error": ""})
common.write_json(texts.OUTBOX, {"items": items})
st = [x for x in texts.outbox_for(alex) if x["id"] == n_old][0]
out["stale queued"] = [st["status"], st["error"][:30], queue({}, ext)[1]["send"] is None or "not-stale"]
out["lease"] = [[x["status"] for x in texts.outbox_for(alex) if x["id"] == sid4], queue({}, ext)[1]["send"]]
s, r = page("/api/texts/send", {"conv": "", "to": "Pat Sample", "text": "Thanks"})
out["new to name"] = [r["ok"], r["conv"].startswith("p")]
s, r = page("/api/texts/send", {"conv": "", "to": "(555) 010-0555", "text": "Hello new number"})
n1, n2 = queue({}, ext)[1]["send"], queue({}, ext)[1]["send"]
out["new to number"] = [r["ok"], [n1["text"], n1["conv"], n1["phone"]], [n2["text"], n2["conv"], n2["phone"]]]
out["refused"] = [page("/api/texts/send", {"conv": "", "to": "", "text": "x"})[1]["ok"], page("/api/texts/send", {"conv": "", "to": "Nobody Known", "text": "x"})[1]["error"],
                  page("/api/texts/send", {"conv": gid, "text": "x"})[1]["ok"]]
queue({}, ext)
before = len(texts._outbox_all())
texts.draft(conv=alex, text="Sounds good, see you then", why="you asked for a reply")
th = page("/api/texts/thread?id=" + alex)[1]
out["draft"] = [len(texts._outbox_all()) == before, [d["text"] for d in th["drafts"]], queue({}, ext)[1]["send"]]
page("/api/texts/send", {"conv": alex, "text": "Sounds good, see you then"})
out["draft sent by press"] = [page("/api/texts/thread?id=" + alex)[1]["drafts"], queue({}, ext)[1]["send"]["text"]]
chat = texts.for_chat(set(), "what did Alex text me about dinner?")
out["chat"] = [chat[0]["with"] if chat else None, len(chat[0]["latest_first"]) if chat else 0]
out["chat other"] = texts.for_chat(set(), "what is on my calendar?")
import threading
def idle():
    c0 = time.time(); c = db.try_connect()                      # a write connection, asked for with no waiting
    ok = c is not None
    if ok: c.close()
    return [db._held["thread"], db._held["depth"], ok, time.time() - c0 < 1]
out["nothing held after the list, thread, send, failure, timeout, draft and chat paths: a write opens at once"] = idle()
db.GATE_WAIT_ONE = 0.2; texts.time.sleep = lambda s: None
hold, rel = threading.Event(), threading.Event()
def holder():
    c = db.connect(); hold.set(); rel.wait(30); c.close()
ht = threading.Thread(target=holder); ht.start(); hold.wait()
busy = [page("/api/texts"), page("/api/texts/thread?id=" + alex), page("/api/texts/status")[0]]
rel.set(); ht.join()
texts_cache.ON = True; texts_cache.refresh(); hold2, rel2 = threading.Event(), threading.Event()
def holder2():
    c = db.connect(); hold2.set(); rel2.wait(30); c.close()
ht2 = threading.Thread(target=holder2); ht2.start(); hold2.wait()
t0 = time.time(); copied = [page("/api/texts"), page("/api/texts/thread?id=" + alex)]
rel2.set(); ht2.join(); texts_cache.ON = False
out["with the copy on, the list and a thread answer at once while another part holds the database"] = [[b[1].get("busy") for b in copied], [bool(b[1].get("ok")) for b in copied], time.time() - t0 < 2]
out["while another part holds the database the page answers busy, and afterwards nothing is held"] = [[b[1].get("busy") for b in busy[:2]], busy[2], idle(), page("/api/texts")[1].get("busy")]
def dies():
    db._enter(False, 1)                                         # a thread that takes the database and ends without letting go
dt_ = threading.Thread(target=dies); dt_.start(); dt_.join()
c0 = time.time(); c = db.try_connect(); ok = c is not None
if ok: c.close()
out["a hold left by a thread that has ended is cleared, not waited on for ever"] = [ok, time.time() - c0 < 2, db._held["thread"], db._held["depth"]]
srv.shutdown()
_store.text_messages([{"provider_id": "gm:solo1:1", "thread": "solo1", "ts": now - dt.timedelta(minutes=1), "direction": "out", "key": None, "name": "", "text": "note to myself", "media": []}])
out["one to one with no known person"] = [[x["name"], x["group"]] for x in texts.conversations()["rows"] if x["last"] == "note to myself"]
# older conversations (stored before the texts link) matched to the link's list: by id, number, name, a group by its members
_store.text_messages([{"provider_id": "gm:gmself:1", "thread": "gmself", "ts": now - dt.timedelta(minutes=3), "direction": "out", "key": None, "name": "",
                       "subject": "Casey Example", "text": "Test 4", "media": []}])
rows = {x["name"]: x["id"] for x in texts.conversations()["rows"]}
solo = [x["id"] for x in texts.conversations()["rows"] if x["last"] == "note to myself"][0]
out["before matching"] = [texts.thread(rows["Casey Example"])["can_send"], texts.queue_send(rows["Casey Example"], "Test 5")["ok"]]
link_list = [{"id": "Lcasey", "name": "Casey Example", "group": False, "others": []},
             {"id": "Lpat", "name": "Pat Sample", "group": False, "others": [{"number": "+1 555-010-0177", "name": "Pat Sample"}]},
             {"id": "Lgrp", "name": "", "group": True, "others": [{"number": "+15550100101", "name": "Sam Sample"}, {"number": "+15550100102", "name": "Jo Test"}]},
             {"id": "101", "name": "Alex Example", "group": False, "others": [{"number": "+15550100199", "name": "Alex Example"}]},
             {"id": "Lother", "name": "Someone Else", "group": False, "others": [{"number": "+15550100188", "name": "Someone Else"}]}]
out["matched"] = {k: v for k, v in textlink.match(link_list).items() if k in ("matched", "unmatched")}
with texts._read() as con:
    th = texts._threads(con)
out["link ids"] = sorted([th[rows[n]]["gl"] for n in ("Casey Example", "Pat Sample", "Sam Sample, Jo Test", "Alex Example")])
r = texts.queue_send(rows["Casey Example"], "Test 5")
out["send from the older conversation"] = [r["ok"], [x["gl"] for x in texts._outbox_all() if x["id"] == r.get("id")], textlink.owns([x for x in texts._outbox_all() if x["id"] == r.get("id")][0])]
out["a group answers too"] = texts.thread(rows["Sam Sample, Jo Test"])["can_send"]
ns = texts.thread(solo)
out["no match: said plainly"] = [ns["can_send"], ns["cant_send"] == texts.NO_LINK, texts.queue_send(solo, "x")["error"] == texts.NO_LINK]
_store.text_messages([{"provider_id": "gl:Lcasey:m1", "thread": "gl:Lcasey", "ts": now, "direction": "out", "key": None, "name": "", "subject": "Casey Example",
                       "text": "Test 5", "media": []}])
out["one conversation with the link's own thread"] = [[x["count"], x["last"]] for x in texts.conversations()["rows"] if x["name"] == "Casey Example"]
out["kept on a later run"] = {k: v for k, v in textlink.match(link_list[1:]).items() if k in ("matched", "unmatched")}
out["logged"] = "older conversations matched 4, not matched 1" in open(textlink.TEXTS_LOG, encoding="utf-8").read()
# one person's threads from every source are one conversation: the numbered one, the link's, and threads with no number of the same name
_store.text_messages([bk(9, "+15550100133", "Casey Example", "in", "From the backup", 900)] +
                     [{"provider_id": f"gm:{t}:1", "thread": t, "ts": now - dt.timedelta(minutes=800), "direction": "out", "key": None, "name": "",
                       "subject": "Casey Example", "text": "old " + t, "media": []} for t in ("2230", "phone:x5550100133")])
cs = [x for x in texts.conversations()["rows"] if x["name"] == "Casey Example"]
one = texts.thread(cs[0]["id"]) if cs else {}
with texts._read() as con:
    cc = texts._threads(con).get(cs[0]["id"]) if cs else {}
out["one conversation per person"] = [len(cs), cs[0]["count"] if cs else 0, one.get("can_send"), cc.get("gl"), cc.get("phone")]
r = texts.queue_send(cs[0]["id"], "Test 6")
out["it sends through the link"] = [r["ok"], [x["gl"] for x in texts._outbox_all() if x["id"] == r.get("id")]]
# a second Messages conversation of the same person (an SMS one beside an RCS one) does not split it; its old ids still open it and send
_store.text_messages([{"provider_id": "gl:Lcasey2:m1", "thread": "gl:Lcasey2", "ts": now - dt.timedelta(minutes=700), "direction": "out", "key": None,
                       "name": "", "subject": "Casey Example", "text": "sms side", "media": []}])
cs = [x for x in texts.conversations()["rows"] if x["name"] == "Casey Example"]
old = [texts.thread("t2230").get("ok"), texts.thread("tgl:Lcasey2").get("id"), texts.queue_send("tgl:Lcasey2", "Test 7").get("ok")]
out["two Messages conversations of one person"] = [len(cs), cs[0]["count"] if cs else 0, old[0], old[1] == (cs[0]["id"] if cs else None), old[2],
                                                   [x["gl"] for x in texts._outbox_all() if x["text"] == "Test 7"]]
full = textlink.match(link_list, whole=True)      # before the extra conversations below
# one number with two Messages conversations (a text one and a chat one): the newer is taken; a short code is matched by its digits;
# two people of one name with different numbers are not guessed between
_store.text_messages([bk(11, "+15550100144", "Robin Sample", "in", "Robin here", 50), bk(12, "55501", "55501", "in", "Your code is 123", 40),
                      {"provider_id": "gm:gmdup:1", "thread": "gmdup", "ts": now - dt.timedelta(minutes=30), "direction": "out", "key": None, "name": "",
                       "subject": "Lee Twin", "text": "which Lee", "media": []}])
dup_list = link_list + [
    {"id": "Lrobin_sms", "name": "Robin Sample", "group": False, "last": 1000, "others": [{"number": "+1 555-010-0144", "name": "Robin Sample"}]},
    {"id": "Lrobin_rcs", "name": "Robin Sample", "group": False, "last": 2000, "others": [{"number": "+15550100144", "name": "Robin Sample"}]},
    {"id": "Lcode", "name": "55501", "group": False, "last": 5, "others": [{"number": "55501", "name": ""}]},
    {"id": "Llee1", "name": "Lee Twin", "group": False, "last": 9, "others": [{"number": "+15550100161", "name": "Lee Twin"}]},
    {"id": "Llee2", "name": "Lee Twin", "group": False, "last": 8, "others": [{"number": "+15550100162", "name": "Lee Twin"}]}]
textlink.match(dup_list, whole=True)
with texts._read() as con:
    th2 = texts._threads(con)
by = {c["name"]: c for c in th2.values()}
out["several Messages conversations of one number"] = [by.get("Robin Sample", {}).get("gl"), [c["gl"] for c in th2.values() if "bk:55501" in "".join(c["threads"]) or "55501" in c["threads"]],
                                                       by.get("Lee Twin", {}).get("gl")]
out["whole list logged with its kinds"] = [full["kinds"], "link: whole conversation list, 5 listed by Google Messages (4 one-to-one, 3 of them with a number; 1 groups)" in open(textlink.TEXTS_LOG, encoding="utf-8").read()]
# pictures: a picture the texts link brings for a text stored before it fills that text (no second row); the conversation shows it
# through its own door; a link text with the same words as an older one is not stored again
T = (now - dt.timedelta(hours=5)).replace(second=0)
_store.text_messages([{"provider_id": "bk:jamie:1", "thread": "+15550100155", "ts": T, "direction": "in", "key": ph("+15550100155"),
                       "name": "Jamie Sample", "text": _store.NO_TEXT, "media": []},
                      {"provider_id": "bk:jamie:2", "thread": "+15550100155", "ts": T + dt.timedelta(minutes=3), "direction": "in",
                       "key": ph("+15550100155"), "name": "Jamie Sample", "text": "Going out this evening", "media": []}])
png = b"\x89PNG\r\n\x1a\n" + b"\0" * 4000
c0 = db.try_connect(read_only=True)
before_n = c0.execute("SELECT count(*) FROM messages WHERE channel='sms'").fetchone()[0]
c0.close()
_store.text_messages([{"provider_id": "gl:Ljamie:p1", "thread": "gl:Ljamie", "ts": T + dt.timedelta(seconds=20), "direction": "in",
                       "key": ph("+15550100155"), "name": "Jamie Sample", "subject": "Jamie Sample", "text": _store.NO_TEXT,
                       "media": [(".png", "image.png", png, True)]},
                      {"provider_id": "gl:Ljamie:t1", "thread": "gl:Ljamie", "ts": T + dt.timedelta(minutes=3, seconds=10), "direction": "in",
                       "key": ph("+15550100155"), "name": "Jamie Sample", "subject": "Jamie Sample", "text": "Going out this evening", "media": []}])
c0 = db.try_connect(read_only=True)
after_n = c0.execute("SELECT count(*) FROM messages WHERE channel='sms'").fetchone()[0]
c0.close()
jid = [x["id"] for x in texts.conversations()["rows"] if x["name"] == "Jamie Sample"][0]
jt = texts.thread(jid)
pic = [m for m in jt["messages"] if m["media"]]
out["a picture fills the text stored before the link"] = [after_n - before_n, _store.filled[0], len(pic), pic[0]["media"][0]["pic"] if pic else None,
                                                          pic[0]["text"] if pic else None]
srv.server_close(); srv = local_site.start(); port = srv.server_address[1]; texts_cache.refresh()      # the page's copy, with the texts' pictures
sp, body = None, None
if pic:
    rq = urllib.request.Request(f"http://127.0.0.1:{port}/api/texts/file?id={pic[0]['media'][0]['id']}", headers={"Host": f"127.0.0.1:{port}", "Cookie": ck})
    with urllib.request.urlopen(rq, timeout=30) as r9:
        sp, body, kind = r9.status, r9.read(), r9.headers.get("Content-Type")
out["the conversation's picture door"] = [sp, body == png, kind if pic else None, req(f"/api/texts/file?id={pic[0]['media'][0]['id'] if pic else 1}")[0],
                                          page("/api/texts/file?id=999999")[0]]
srv.shutdown()
# a text stored twice before the link (same words, same conversation, same minute) is kept once; the removed row is deleted outright
cw = db.connect()
cw.execute("INSERT INTO messages (channel, account, provider_id, thread_id, ts, direction, from_key, person_id, subject, body, ingested_at) "
           "SELECT channel, account, 'bk:jamie:2b', thread_id, ts + INTERVAL 20 SECOND, direction, from_key, person_id, subject, body, ingested_at "
           "FROM messages WHERE provider_id = 'bk:jamie:2'")
cw.close()
texts_cache.refresh()
twice = sum(1 for m in texts.thread(jid)["messages"] if m["text"] == "Going out this evening")
gone = texts.remove_duplicates()
moved = [d for d in os.listdir(common.HOME) if d == "To Delete"]
# a text the link handed over before its picture was ready, handed over again with it: the picture goes onto that text
_store.text_messages([{"provider_id": "gl:Ljamie:p2", "thread": "gl:Ljamie", "ts": now - dt.timedelta(minutes=2), "direction": "out", "key": ph("+15550100155"),
                       "name": "Jamie Sample", "subject": "Jamie Sample", "text": _store.NO_TEXT, "media": []}])
_store.text_messages([{"provider_id": "gl:Ljamie:p2", "thread": "gl:Ljamie", "ts": now - dt.timedelta(minutes=2), "direction": "out", "key": ph("+15550100155"),
                       "name": "Jamie Sample", "subject": "Jamie Sample", "text": _store.NO_TEXT, "media": [(".png", "image.png", png, True)]}] * 2)
c0 = db.try_connect(read_only=True)
out["a picture that came after its text"] = c0.execute("SELECT count(DISTINCT m.id), count(a.id) FROM messages m LEFT JOIN attachments a ON a.message_id = m.id "
                                                       "WHERE m.provider_id = 'gl:Ljamie:p2'").fetchone()
c0.close()
out["a text stored twice is kept once"] = [twice, gone, sum(1 for m in texts.thread(jid)["messages"] if m["text"] == "Going out this evening"),
                                           len(moved), texts.remove_duplicates()]
# the same words with other spacing are the same text: kept once by the clean-up, and not stored again when one comes in
cw = db.connect()
cw.execute("INSERT INTO messages (channel, account, provider_id, thread_id, ts, direction, from_key, person_id, subject, body, ingested_at) "
           "SELECT channel, account, 'bk:jamie:2c', thread_id, ts + INTERVAL 30 SECOND, direction, from_key, person_id, subject, 'Going  out   this evening', ingested_at "
           "FROM messages WHERE provider_id = 'bk:jamie:2'")
cw.close()
texts_cache.refresh()
gone2 = texts.remove_duplicates()
w2 = _store.text_messages([{"provider_id": "bk:jamie:2d", "thread": "+15550100155", "ts": T + dt.timedelta(minutes=3, seconds=40), "direction": "in",
                            "key": ph("+15550100155"), "name": "Jamie Sample", "text": "Going out this\n evening", "media": []}])[0]
texts_cache.refresh()
out["spacing aside"] = [gone2, w2, sum(1 for m in texts.thread(jid)["messages"] if " ".join(m["text"].split()) == "Going out this evening")]
print(json.dumps(out))
'''

WANT = {
    "list": [["Sam Sample, Jo Test", True, 2], ["Alex Example", False, 3], ["Pat Sample", False, 1]],
    "unread at first look": [0, 0, 0],
    "thread": [[False, "Are we still on for dinner?"], [True, "Yes, see you at 6"], [False, "Running late, start without me"]],
    "can answer": [True, "Alex Example"],
    "group": ["Sam Sample, Jo Test", ["Sam Sample", "Jo Test"], False],      # not answerable until the link lists it (matched below)
    "one to one with no known person": [["Unknown", False]],
    "before matching": [False, False],
    "matched": {"matched": 4, "unmatched": 1},
    "link ids": ["101", "Lcasey", "Lgrp", "Lpat"],
    "send from the older conversation": [True, ["Lcasey"], True],
    "a group answers too": True,
    "no match: said plainly": [False, True, True],
    "one conversation with the link's own thread": [[2, "Test 5"]],
    "kept on a later run": {"matched": 3, "unmatched": 1},      # counted as the page shows them: Casey is now one with the link's own thread
    "logged": True,
    "one conversation per person": [1, 5, True, "Lcasey", "5550100133"],
    "it sends through the link": [True, ["Lcasey"]],
    "two Messages conversations of one person": [1, 6, True, True, True, ["Lcasey"]],
    "several Messages conversations of one number": ["Lrobin_rcs", ["Lcode"], ""],
    "a picture fills the text stored before the link": [0, 1, 1, True, "[media message, no text]"],
    "the conversation's picture door": [200, True, "image/png", 401, 404],
    "a text stored twice is kept once": [2, 1, 1, 0, 0],
    "a picture that came after its text": [1, 1],
    "spacing aside": [1, 0, 1],
    "whole list logged with its kinds": [{"groups": 0, "with a number": 0, "with neither": 1, "last text in 90 days": 1}, True],
    "search": [["Pat Sample"], ["Alex Example"], []],
    "new text": ["Alex Example", 1, "Made it"],
    "after opening": [0],
    "door list": [200, 3],
    "door status": [200, True, True],
    "signed out": [401, 401],
    "door thread": [200, "Alex Example", 4, True],
    "send without page token": [403, 401],
    "nothing queued": [None, []],
    "empty": {"ok": False, "error": "Write the text first."},
    "queued": [200, True, ["queued"]],
    "the extension's doors are gone": [True, True],
    "untouched by them": ["queued"],
    "taken": [200, "On my way, 10 minutes", "101", True],
    "once": None,
    "shows sending": ["sending"],
    "unknown report": False,
    "sent once": [True, False, ["sent"]],
    "sent line shows": ["sent"],
    "read back": [[], "On my way, 10 minutes"],
    "failed": ["failed", "the Send button was not found"],
    "take back": [True, [], False],
    "stale queued": ["failed", "Google Messages on this comput", True],
    "lease": [["failed"], None],
    "new to name": [True, True],
    "new to number": [True, ["Thanks", "", "5550100177"], ["Hello new number", "", "5550100555"]],
    "refused": [False, "No number is on file for Nobody Known. Type the number.", False],      # a group known only to the old extension: the link cannot place it yet
    "draft": [True, ["Sounds good, see you then"], None],
    "draft sent by press": [[], "Sounds good, see you then"],
    "chat": ["Alex Example", 5],
    "chat other": [],
    "a hold left by a thread that has ended is cleared, not waited on for ever": [True, True, None, 0],
    "nothing held after the list, thread, send, failure, timeout, draft and chat paths: a write opens at once": [None, 0, True, True],
    "with the copy on, the list and a thread answer at once while another part holds the database": [[None, None], [True, True], True],
    "while another part holds the database the page answers busy, and afterwards nothing is held": [[True, True], 200, [None, 0, True, True], None],
}


def engine_part():
    tmp = tempfile.mkdtemp(prefix="tx-")
    live = os.path.join(PKG, "engine", "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"))
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=300, encoding="utf-8")
    import _cleanup
    _cleanup.remove(tmp)                # the scratch home goes once the engine part has run
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        check("the engine checks ran", r.stderr.strip()[-1500:], "")
        return
    for k, v in WANT.items():
        check(k, got.get(k), v)


engine_part()
for name, ok, got, want in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"\n   got  {got}\n   want {want}"))
print(f"{sum(1 for r in results if r[1])}/{len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
