r"""Acceptance of the mail sync's three promises, on a scratch home with stand-in mail services (no real mailbox is called):

- a burst bigger than the 200-per-pass cap is taken over several passes and not one email is skipped;
- Gmail: a history id the service no longer has (404) starts a full resync, and a change made elsewhere (read, moved to a
  label) reaches the stored email through the history;
- Microsoft: an email moved to another folder keeps its stored identity and its folder membership follows the move (its id
  is matched by its Message-ID header when the service did give it a new one).

    python tests\mail_sync_acceptance.py
"""
import datetime as dt
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
home = tempfile.mkdtemp(prefix="mailsync-")
os.environ["ASSISTANT_LIVE_HOME"] = home
sys.path.insert(0, LIVE)
sys.path.insert(0, os.path.join(LIVE, "core"))

import db  # noqa: E402
from connections import _http, _store  # noqa: E402
from connections import google_mail, microsoft_mail  # noqa: E402

db.init_schema()


class Ctx:
    dry_run, limit = False, 200


def check(ok, what):
    print(("PASS  " if ok else "FAIL  ") + what)
    if not ok:
        sys.exit(1)


# --- 1. the burst -----------------------------------------------------------------------------------------------------
N = 450
BASE = int(dt.datetime.now().timestamp()) - 3600 * 5
GMAIL = {f"g{i:04d}": {"ts": BASE + i * 10, "labels": ["INBOX", "UNREAD"]} for i in range(N)}     # g0449 is the newest


def gmail_get(url, token=None, params=None, headers=None):
    params = params or {}
    if url.endswith("/profile"):
        return {"historyId": "500"}
    if url.endswith("/labels"):
        return {"labels": [{"id": "INBOX", "name": "INBOX", "type": "system"}, {"id": "L1", "name": "Suppliers", "type": "user"}]}
    m = re.search(r"/labels/(\w+)$", url)
    if m:
        return {"id": m.group(1), "name": m.group(1), "messagesUnread": 1, "messagesTotal": 2}
    if url.endswith("/messages"):
        after = int(re.search(r"after:(\d+)", params["q"]).group(1))
        ids = sorted((i for i, v in GMAIL.items() if v["ts"] > after), key=lambda i: -GMAIL[i]["ts"])
        return {"messages": [{"id": i} for i in ids]}
    m = re.search(r"/messages/(\w+)$", url)
    if m:
        v = GMAIL[m.group(1)]
        if params.get("format") == "minimal":
            return {"labelIds": v["labels"]}
        return {"id": m.group(1), "threadId": "t" + m.group(1), "internalDate": str(v["ts"] * 1000), "labelIds": v["labels"],
                "payload": {"headers": [{"name": "From", "value": f"a{m.group(1)}@example.org"}, {"name": "To", "value": "me@example.com"},
                                        {"name": "Subject", "value": "Subject " + m.group(1)}], "mimeType": "text/plain",
                            "body": {"data": "SGVsbG8gdGhlcmUgZnJvbSBtZQ=="}}}
    if url.endswith("/history"):
        raise _http.Refused(404, "too old")
    raise AssertionError(url)


google_mail._http.get_json = gmail_get
google_mail.token_for = lambda conn: "t"
conn = {"address": "me@example.com", "type": "google_mail"}

for n in range(4):
    google_mail.gather(conn, Ctx)
held = _store.held_ids("me@example.com")
check(len(held) == N and set(GMAIL) == held, f"a burst of {N} over a cap of 200 is taken whole over several passes, none skipped")

# --- 2. Gmail history: a stale id resyncs; a change elsewhere arrives ---------------------------------------------------
_store.set_cursor("me@example.com", "history", "1")
for _ in range(3):
    google_mail.sync(conn, Ctx, 1e12)
check(_store.cursor("me@example.com", "history") == "500", "a history id Gmail no longer has starts a full resync from its current one")
check(not _store.unsynced("me@example.com", 1), "the resync re-read every stored email's state")

GMAIL["g0000"]["labels"] = ["L1"]                      # read, archived and labelled elsewhere
google_mail._http.get_json = lambda url, token=None, params=None, headers=None: (
    {"history": [{"id": "501", "labelsRemoved": [{"message": {"id": "g0000"}}]}], "historyId": "502"} if url.endswith("/history")
    else gmail_get(url, token, params, headers))
google_mail.sync(conn, Ctx, 1e12)
con = db.connect(read_only=True)
row = con.execute("SELECT s.unread, s.inbox FROM messages m JOIN mail_state s ON s.message_id = m.id WHERE m.provider_id = 'g0000'").fetchone()
mem = con.execute("SELECT f.folder_id FROM messages m JOIN mail_folder_members f ON f.message_id = m.id WHERE m.provider_id = 'g0000'").fetchall()
con.close()
check(row == (False, False) and mem == [("L1",)], "a read, archived and relabelled email changes here through the history")

# --- 3. Microsoft: a move keeps the identity ----------------------------------------------------------------------------
ACC = "me@work.example"
w = _store.MailWriter(ACC)
now = dt.datetime.now()
for pid, hid in (("m1", "<a>"), ("m2", "<b>")):
    w.add(pid, now, "in", "x@example.org", ACC, "Hello " + pid, "body of " + pid, folder="I",
          state={"unread": True, "inbox": True, "header_id": hid, "folders": ["I"], "synced": True})
w.commit()
_store.put_folders(ACC, [{"id": "I", "path": "Inbox", "kind": "inbox"}, {"id": "X", "path": "Inbox/Suppliers", "parent": "I"},
                         {"id": "D", "path": "Deleted Items", "kind": "trash"}])
_store.set_cursor(ACC, "immutable", "1")
_store.set_cursor(ACC, "folders_at", dt.datetime.now().isoformat())
for f in "IXD":
    _store.set_cursor(ACC, "delta:" + f, '{"delta": "d%s"}' % f)
DELTAS = {"dI": {"value": [{"id": "m1", "@removed": {"reason": "deleted"}}, {"id": "m2", "@removed": {"reason": "deleted"}}]},
          "dX": {"value": [{"id": "m1", "parentFolderId": "X", "isRead": True, "internetMessageId": "<a>"},
                           {"id": "m2-new", "parentFolderId": "X", "isRead": False, "internetMessageId": "<b>"}]},
          "dD": {"value": []}}


def ms_get(url, token=None, params=None, extra=None):
    if "/me/messages/" in url:      # the one-by-one look at an email that left a folder
        if url.endswith("m2"):
            raise _http.Refused(404, "gone under that id")
        return {"id": "m1", "parentFolderId": "X", "isRead": True}
    return dict(DELTAS[url], **{"@odata.deltaLink": url + "2"})


microsoft_mail._get = ms_get
microsoft_mail._token = lambda conn: "t"
microsoft_mail.sync({"address": ACC, "type": "microsoft_mail"}, Ctx, 1e12)
con = db.connect(read_only=True)
got = con.execute("SELECT coalesce(s.provider_id, m.provider_id) AS pid, s.unread, s.inbox, s.trashed, string_agg(f.folder_id, ',')"
                  " FROM messages m JOIN mail_state s ON s.message_id = m.id"
                  " LEFT JOIN mail_folder_members f ON f.message_id = m.id WHERE m.account = ? GROUP BY ALL ORDER BY pid", [ACC]).fetchall()   # the current id
con.close()
check(got == [("m1", False, False, False, "X"), ("m2-new", True, False, False, "X")],
      "a moved email keeps its stored identity and its folder follows (an id the service changed is matched by its Message-ID)")

# --- 4. Gmail: ids from an earlier import are never sent; found by Message-ID or set aside --------------------------------
G2 = "lee@mail.example"
w = _store.MailWriter(G2)
for pid, hid in (("00000000AB12CD", "<x1@acme.example>"), ("imap:INBOX:<x2@acme.example>", None), ("imap:INBOX:1968", None),
                 ("00000000EF34", "<gone@acme.example>"), ("0123456789abcdef", None)):
    w.add(pid, now, "in", "x@example.org", G2, "Old " + pid, "body " + pid, state={"header_id": hid} if hid else None)
w.commit()
FOUND, sent = {"x1@acme.example": "aaaa0000bbbb1111", "x2@acme.example": "aaaa0000bbbb2222"}, []


def g2_get(url, token=None, params=None, headers=None):
    params = params or {}
    if url.endswith("/messages") and params.get("q", "").startswith("rfc822msgid:"):
        g = FOUND.get(params["q"][12:])
        return {"messages": [{"id": g}]} if g else {}
    m = re.search(r"/messages/([^/]+)$", url)
    if m:
        sent.append(m.group(1))
        if not re.fullmatch(r"[0-9a-f]{12,20}", m.group(1)):
            raise _http.Refused(400, "Invalid id value")
        return {"labelIds": ["INBOX"]}
    return gmail_get(url, token, params, headers)


google_mail._http.get_json = g2_get
_store.set_cursor(G2, "history", "500")
for _ in range(2):
    google_mail.sync({"address": G2, "type": "google_mail"}, Ctx, 1e12)
con = db.connect(read_only=True)
cur = dict(con.execute("SELECT m.provider_id, s.provider_id FROM messages m JOIN mail_state s ON s.message_id = m.id"
                       " WHERE m.account = ? AND s.synced_at IS NOT NULL", [G2]).fetchall())
aside = sorted(r[0] for r in con.execute("SELECT m.provider_id FROM messages m JOIN mail_state s ON s.message_id = m.id"
                                         " WHERE m.account = ? AND s.unmatched_at IS NOT NULL", [G2]).fetchall())
con.close()
check(all(re.fullmatch(r"[0-9a-f]{12,20}", x) for x in sent), "only Gmail's own ids are sent to Gmail")
check(cur == {"00000000AB12CD": "aaaa0000bbbb1111", "imap:INBOX:<x2@acme.example>": "aaaa0000bbbb2222", "0123456789abcdef": "0123456789abcdef"},
      "an imported email Gmail finds by its Message-ID takes Gmail's id and is read")
check(aside == ["00000000EF34", "imap:INBOX:1968"] and not _store.unsynced(G2, 10),
      "one Gmail cannot find, or with no Message-ID, is set aside and not asked for again")
# --- 5. Microsoft: the one-time move to permanent ids passes over mail that already has one --------------------------------
M2 = "lee@work.example"
w = _store.MailWriter(M2)
for pid in ("REST-1", "REST-2", "IMM-3", "REST-4", "IMM-5"):          # IMM-: read after permanent ids were asked for
    w.add(pid, now, "in", "x@example.org", M2, "Hi " + pid, "body " + pid)
w.commit()
asked = []


def translate(method, url, token, obj=None, headers=None):
    asked.append(len(obj["inputIds"]))
    assert url.endswith("/me/translateExchangeIds") and {obj["sourceIdType"], obj["targetIdType"]} == {"restId", "restImmutableEntryId"}
    permanent = obj["sourceIdType"] == "restImmutableEntryId"       # asked back as permanent ids: every one must be one
    if any(i.startswith("IMM") != permanent for i in obj["inputIds"]):
        raise _http.Refused(400, '{"error":{"code":"InvalidArgument","message":"Invalid value for arg: storeObjectId.IdType, value:ImmutableId, expected:EntryId"}}')
    return 200, {"value": [{"sourceId": i, "targetId": ("REST-" if permanent else "IMM-") + i} for i in obj["inputIds"]]}


microsoft_mail._http.call_json = translate
done = microsoft_mail._migrate(M2, "t", 1e12)
con = db.connect(read_only=True)
cur = sorted(r[0] for r in con.execute("SELECT coalesce(s.provider_id, m.provider_id) FROM messages m LEFT JOIN mail_state s"
                                       " ON s.message_id = m.id WHERE m.account = ?", [M2]).fetchall())
con.close()
check(done and cur == ["IMM-3", "IMM-5", "IMM-REST-1", "IMM-REST-2", "IMM-REST-4"],
      "the move to permanent ids finishes though some mail already has one (Microsoft refuses a mixed request)")
# --- 6. Microsoft: many folders with nothing new are asked a few at a time, not one after another -------------------------
import time as _t
M3 = "lee@many.example"
_store.put_folders(M3, [{"id": f"F{i}", "path": f"Inbox/F{i}", "kind": "folder"} for i in range(40)])
for i in range(40):
    _store.set_cursor(M3, f"delta:F{i}", '{"delta": "dF%d"}' % i)
microsoft_mail._get = lambda url, token=None, params=None, extra=None: (_t.sleep(0.3), {"value": [], "@odata.deltaLink": url})[1]
t0 = _t.time()
n, current = microsoft_mail._delta({"address": M3}, "t", _t.time() + 60, {})
took = _t.time() - t0
check(current and n == 0 and took < 6, f"forty folders with nothing new are read in rounds ({took:.1f}s, one by one would be 12s)")
# --- 7. Microsoft: a sync that stops at the id migration still writes the folders -----------------------------------------
M4 = "purchasing@cut.example"
_store.put_folders(M4, [{"id": "OLD", "path": "Old", "kind": "folder"}])
_store.set_cursor(M4, "folders_at", "2000-01-01T00:00:00")
w = _store.MailWriter(M4)
w.add("r1", dt.datetime.now(), "in", "x@example.org", M4, "Hi", "b", folder="OLD", state={"unread": True, "inbox": True, "header_id": "<q>", "folders": ["OLD"], "synced": True})
w.commit()
microsoft_mail._token = lambda conn: "t"
microsoft_mail._migrate = lambda account, token, end: False         # the migration runs out of time
microsoft_mail._folders = lambda conn, token: _store.put_folders(conn["address"], [{"id": "NEW", "path": "Fresh", "kind": "folder"}])
said = microsoft_mail.sync({"address": M4, "type": "microsoft_mail"}, Ctx, _t.time() + 60)
check("permanent ones" in said and [f["id"] for f in _store.folders(M4)] == ["NEW"], "a sync cut off by the id migration still writes the folders")
print("all passed")
