r"""Acceptance of the Mail part's read copy (mail_cache.py), on a scratch home with stand-in mail:

- the list, a conversation, the folders and a search read from the copy give what the database itself gives;
- while the database is held (a pass writing) the copy still answers, and a request that asks for the newest says it is stale;
- new mail and a changed state reach the copy at the next refresh; a row's words are made once and kept.

    python tests\mail_cache_acceptance.py
"""
import datetime as dt
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
os.environ["ASSISTANT_LIVE_HOME"] = tempfile.mkdtemp(prefix="mailcache-")
sys.path.insert(0, LIVE)
sys.path.insert(0, os.path.join(LIVE, "core"))

import db  # noqa: E402
import mail  # noqa: E402
import mail_cache  # noqa: E402
from connections import _store  # noqa: E402

db.init_schema()


def check(ok, what):
    print(("PASS  " if ok else "FAIL  ") + what)
    if not ok:
        sys.exit(1)


ACC = "me@example.com"
now = dt.datetime.now()
w = _store.MailWriter(ACC)
for pid, subj, body, mins in (("p1", "Plans", "<html><style>p{}</style><p>Dinner at <b>eight</b></p></html>", 50), ("p2", "Lunch", "the budget is due", 20),
                              ("p3", "Invoice", "please pay the invoice", 10)):
    w.add(pid, now - dt.timedelta(minutes=mins), "in", "x@example.org", ACC, subj, body, thread_id="T-" + pid,
          state={"unread": True, "inbox": True, "header_id": "<" + pid + "@x>", "refs": "", "folders": ["I"], "synced": True})
w.commit()
_store.put_folders(ACC, [{"id": "I", "path": "Inbox", "kind": "inbox"}, {"id": "X", "path": "Inbox/Suppliers", "parent": "I"}])
mail.accounts = lambda: []

direct = {"inbox": mail.rows(account=ACC), "search": mail.rows("all", account=ACC, q="budget"), "folders": mail.folders(ACC)}
tid = direct["inbox"]["rows"][0]["id"]
direct["thread"] = mail.thread(tid)

mail_cache.enable()
check(mail_cache.refresh(True), "the copy is built from the database")
got = mail.rows(account=ACC)
check([r["id"] for r in got["rows"]] == [r["id"] for r in direct["inbox"]["rows"]] and got["counts"] == direct["inbox"]["counts"], "the list from the copy is the database's list")
check([r["snippet"] for r in got["rows"]] == [r["snippet"] for r in direct["inbox"]["rows"]], "the words on each row are the same")
check([r["id"] for r in mail.rows("all", account=ACC, q="budget")["rows"]] == [r["id"] for r in direct["search"]["rows"]] and len(direct["search"]["rows"]) == 1, "a search finds the same email")
check(mail.folders(ACC) == direct["folders"], "the folder tree is the same")
check(mail.thread(tid) == direct["thread"], "a conversation is the same")

real = db.try_connect
db.try_connect = lambda read_only=False: None          # a pass holds the database
try:
    w = _store.MailWriter(ACC)
    db.try_connect = real
    w.add("p4", now, "in", "y@example.org", ACC, "New one", "fresh words", thread_id="T-p4",
          state={"unread": True, "inbox": True, "header_id": "<p4@x>", "refs": "", "folders": ["I"], "synced": True})
    w.commit()
    db.try_connect = lambda read_only=False: None
    held = mail.rows(account=ACC, fresh=True)
    check(held["ok"] and len(held["rows"]) == 3 and held.get("stale") is True, "while the database is held the copy answers, and says it is stale")
    check(mail.thread(tid, fresh=True)["ok"], "a conversation opens meanwhile")
finally:
    db.try_connect = real
check(mail_cache.refresh(True), "when the database can be read the copy catches up")
after = mail.rows(account=ACC, fresh=True)
check(len(after["rows"]) == 4 and not after.get("stale") and after["rows"][0]["subject"] == "New one", "the new email is listed, no longer stale")
con = mail_cache._connection().cursor()
check(con.execute("SELECT count(*) FROM snippets").fetchone()[0] == 4, "each row's words are kept once made")
# the file's size and time can lag (a pass holds the database open): changed folder rows still reach the copy
_store.put_folders(ACC, [{"id": "I", "path": "Inbox", "kind": "inbox"}, {"id": "X", "path": "Inbox/Suppliers", "parent": "I"}, {"id": "N", "path": "Inbox/Brand new", "parent": "I"}])
mail_cache._sig = lambda: mail_cache._state["sig"]        # the file looks unchanged
mail_cache._state["looked"] = 0
check(not mail_cache.stale(), "the database file looks unchanged")
check(mail_cache.look() and any(f["path"] == "Inbox/Brand new" for a in mail.folders(ACC)["accounts"] for f in a["folders"]), "changed folder rows reach the copy at its next refresh")
print("all passed")
