r"""Acceptance (quick): the full history reload (Settings, Tools: Reload all email history) on a made-up Gmail mailbox with a
stand-in Gmail (no real mailbox is called). It goes a portion per pass; stored mail is paired with the service's copy by its
Message-ID, or (an earlier import's row with none) by sender, subject and the same second, and keeps its row and attachment;
a looser likeness never pairs; a stored email the service no longer has stays, marked as history; nothing is stored twice and
nothing is deleted.

    python tests\mail_reload_acceptance.py
"""
import datetime as dt
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
os.environ["ASSISTANT_LIVE_HOME"] = tempfile.mkdtemp(prefix="mailreload-")
sys.path.insert(0, LIVE)
sys.path.insert(0, os.path.join(LIVE, "core"))

import db  # noqa: E402
from connections import _http, _store, google_mail  # noqa: E402

db.init_schema()
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


ACC = "pat@mail.example"
T0 = dt.datetime(2025, 3, 4, 9, 30, 15)
# What the service holds: 60 emails, each a Gmail id; four of them are mail stored before, under other ids.
SERVICE = {}
for i in range(60):
    SERVICE[f"{0xa000 + i:016x}"] = {"ts": T0 + dt.timedelta(hours=i), "from": f"lee{i}@acme.example", "subject": f"Order {i}",
                                    "mid": f"<o{i}@acme.example>", "labels": ["INBOX"] if i % 2 else ["L1"]}
pid = list(SERVICE)
# stored before: an import with a Message-ID (o0), an import with none but the same sender, subject and second (o1), an
# import with none and only a near time (o2, 40 seconds off: never paired), one already held under Gmail's id (o3), and one
# the service no longer has.
w = _store.MailWriter(ACC)
w.add("00000000AAAA", SERVICE[pid[0]]["ts"], "in", "lee0@acme.example", ACC, "Order 0", "old body 0",
      attachments=[("Order 0.pdf", b"%PDF-1.4 made up")], state={"header_id": "<o0@acme.example>"})
w.add("00000000BBBB", SERVICE[pid[1]]["ts"], "in", "lee1@acme.example", ACC, "Order 1", "old body 1")
w.add("imap:INBOX:77", SERVICE[pid[2]]["ts"] + dt.timedelta(seconds=40), "in", "lee2@acme.example", ACC, "Order 2", "old body 2")
w.add(pid[3], SERVICE[pid[3]]["ts"], "in", "lee3@acme.example", ACC, "Order 3", "body 3", state={"header_id": "<o3@acme.example>"})
w.add("00000000GONE", T0 - dt.timedelta(days=30), "in", "old@acme.example", ACC, "Long gone", "deleted at the server")
w.commit()
con = db.connect(read_only=True)
before = dict(con.execute("SELECT provider_id, id FROM messages WHERE account=?", [ACC]).fetchall())
con.close()


def get(url, token=None, params=None, headers=None):
    params = params or {}
    if url.endswith("/labels"):
        return {"labels": [{"id": "INBOX", "name": "INBOX", "type": "system"}, {"id": "L1", "name": "Suppliers", "type": "user"}]}
    lb = re.search(r"/labels/(\w+)$", url)
    if lb:
        return {"id": lb.group(1), "name": lb.group(1), "messagesUnread": 0, "messagesTotal": 0}
    if url.endswith("/profile"):
        return {"historyId": "9"}
    if url.endswith("/history"):
        return {"history": [], "historyId": "9"}
    if url.endswith("/messages"):
        assert params.get("includeSpamTrash") == "true"
        if str(params.get("q") or "").startswith("rfc822msgid:"):          # the backfill's lookup of an import by its Message-ID
            return {"messages": [{"id": i} for i, v in SERVICE.items() if v["mid"] == "<" + params["q"][12:] + ">"]}
        start = int(params.get("pageToken") or 0)
        n = int(params["maxResults"])
        nxt = start + n if start + n < len(pid) else None
        return {"messages": [{"id": i} for i in pid[start:start + n]], **({"nextPageToken": str(nxt)} if nxt else {})}
    m = re.search(r"/messages/([^/]+)$", url)
    if m:
        v = SERVICE[m.group(1)]
        if params.get("format") == "minimal":
            return {"labelIds": v["labels"]}
        return {"id": m.group(1), "threadId": "t" + m.group(1), "internalDate": str(int(v["ts"].timestamp() * 1000)),
                "labelIds": v["labels"], "payload": {"mimeType": "text/plain", "body": {"data": "SGVsbG8="}, "headers": [
                    {"name": "From", "value": v["from"]}, {"name": "To", "value": ACC}, {"name": "Subject", "value": v["subject"]},
                    {"name": "Message-ID", "value": v["mid"]}]}}
    raise AssertionError(url)


google_mail._http.get_json = get
google_mail.token_for = lambda c: "t"
_store.set_cursor(ACC, "history", "9")
conn = {"address": ACC, "type": "google_mail"}
for _ in range(3):                      # the backfill of the stored mail's state comes first and is done before the reload
    google_mail.sync(conn, None, 0)
_store.reload_start(ACC)
lines = []
for _ in range(10):
    google_mail.sync(conn, None, 0)                        # the slow work no longer holds any of the reload
    lines.append(google_mail.reload(conn, 0))              # its own step: no time to spare, one portion each pass
    if (_store.reload_state(ACC) or {}).get("done"):
        break
st = _store.reload_state(ACC)
check("the reload goes a portion per pass (25 of 60 a pass) and finishes", (len(lines), st.get("done")), (3, True))
check("the pass summary says how far it has got", "history reload: 25 read" in lines[0] and "history reload done" in lines[-1], True)

con = db.connect(read_only=True)
cur = dict(con.execute("SELECT m.provider_id, coalesce(s.provider_id, m.provider_id) FROM messages m JOIN mail_state s"
                       " ON s.message_id = m.id WHERE m.account=?", [ACC]).fetchall())
rows = con.execute("SELECT count(*) FROM messages WHERE account=?", [ACC]).fetchone()[0]
current = [r[0] for r in con.execute("SELECT coalesce(s.provider_id, m.provider_id) FROM messages m LEFT JOIN mail_state s"
                                     " ON s.message_id = m.id WHERE m.account=?", [ACC]).fetchall()]
gone = sorted(r[0] for r in con.execute("SELECT m.provider_id FROM messages m JOIN mail_state s ON s.message_id = m.id"
                                        " WHERE m.account=? AND s.server_gone IS NOT NULL", [ACC]).fetchall())
att = con.execute("SELECT count(*) FROM attachments WHERE message_id=?", [before["00000000AAAA"]]).fetchone()[0]
folders = con.execute("SELECT folder_id FROM mail_folder_members WHERE message_id=?", [before["00000000AAAA"]]).fetchall()
still = all(con.execute("SELECT 1 FROM messages WHERE id=?", [i]).fetchone() for i in before.values())
con.close()
check("an imported email with a Message-ID keeps its row and attachment and takes Gmail's id and labels",
      (cur["00000000AAAA"], att, folders), (pid[0], 1, [("L1",)]))
check("an imported email with none is paired by sender, subject and the same second", cur["00000000BBBB"], pid[1])
check("a near time alone never pairs: Gmail's copy is stored and the old one stays", cur["imap:INBOX:77"], "imap:INBOX:77")
check("no email is held twice under one id; every Gmail email is held once", (len(current) == len(set(current)),
      sorted(set(current) & set(pid)) == sorted(pid)), (True, True))
check("rows: the 60 from Gmail plus the two old copies kept", rows, 62)
check("stored mail Gmail no longer has stays, marked as history", gone, ["00000000GONE", "imap:INBOX:77"])
check("nothing stored before was deleted", still, True)
con = db.connect(read_only=True)
settled = con.execute("SELECT count(*) FROM answered WHERE domain='judged' AND source='history reload: old mail'").fetchone()[0]
con.close()
check("the reload's old mail is settled, never sent to thinking as news (57 new, all older than a day)", settled, 57)
check("the slow work says nothing of the reload", any("history reload" in google_mail.sync(conn, None, 0) for _ in range(1)), False)
check("the counts: 60 read, 1 matched to stored mail, 57 new (two were already held, one matched by the backfill before), 2 kept as history",
      (st["read"], st["paired"], st["new"], st["gone"]), (60, 1, 57, 2))
for name, ok, got, want in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
print(f"{sum(r[1] for r in results)} of {len(results)} passed")
sys.exit(0 if all(r[1] for r in results) else 1)
