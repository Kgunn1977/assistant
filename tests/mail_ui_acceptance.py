r"""Acceptance of the Mail part's engine side, on a scratch home with a stand-in mail service (no real mailbox is called):

- emails the service gave no conversation id are threaded from their References headers (JWZ), a list shows one row per conversation;
- a Move through the press keeps the email's identity (same stored id) and its folder follows;
- a snoozed email leaves the inbox and comes back at its time (marked unread); a search filter narrows the list.

    python tests\mail_ui_acceptance.py
"""
import datetime as dt
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
os.environ["ASSISTANT_LIVE_HOME"] = tempfile.mkdtemp(prefix="mailui-")
sys.path.insert(0, LIVE)
sys.path.insert(0, os.path.join(LIVE, "core"))

import connections  # noqa: E402
import db  # noqa: E402
import mail  # noqa: E402
from connections import _store  # noqa: E402

db.init_schema()


def check(ok, what):
    print(("PASS  " if ok else "FAIL  ") + what)
    if not ok:
        sys.exit(1)


ACC = "me@example.com"
now = dt.datetime.now()
w = _store.MailWriter(ACC)
# a made-up conversation without service ids (a, b reply to a, c reply to b), one apart (d), and one with a service id (e)
for pid, hid, refs, subj, mins in (("p1", "<a@x>", "", "Plans", 50), ("p2", "<b@x>", "<a@x>", "Re: Plans", 40), ("p3", "<c@x>", "<a@x> <b@x>", "Re: Plans", 30),
                                   ("p4", "<d@x>", "", "Lunch", 20), ("p5", "<e@x>", "", "Invoice", 10)):
    w.add(pid, now - dt.timedelta(minutes=mins), "in", "x@example.org", ACC, subj, "body of " + pid + (" has the word budget" if pid == "p4" else ""),
          thread_id="T-invoice" if pid == "p5" else None,
          state={"unread": True, "inbox": True, "header_id": hid, "refs": refs, "folders": ["I"], "synced": True})
w.commit()
_store.put_folders(ACC, [{"id": "I", "path": "Inbox", "kind": "inbox"}, {"id": "X", "path": "Inbox/Suppliers", "parent": "I"}])


def listing(**kw):
    out = mail.rows(account=ACC, **kw)
    return out["rows"], out


rows, _ = listing()
check(len(rows) == 5, "before threading every email is its own row")
check(mail.rethread() == 3, "the three emails sharing References are linked")
rows, out = listing()
plans = [r for r in rows if r["subject"] == "Re: Plans"]
check(len(rows) == 3 and plans and plans[0]["count"] == 3 and plans[0]["unread"], "the list shows one row per conversation, newest line, count 3")
check(out["counts"][ACC]["inbox"] == 5, "unread counts on the inbox")
check(len(mail.thread(plans[0]["id"])["messages"]) == 3, "opening the row shows the whole conversation")

rows, _ = listing(q="from:x@example.org budget before:2999-01-01 has:attachment")
check(rows == [], "has:attachment narrows to nothing when no email has a file")
rows, _ = listing(q="from:x@example.org budget")
check([r["subject"] for r in rows] == ["Lunch"], "from: with a word finds the one email")

# a Move: the stand-in service keeps the id
mid = rows[0]["id"]
pid_before = db.query("SELECT provider_id FROM messages WHERE id=?", (mid,))[0][0]


class Mod:
    @staticmethod
    def act(conn, pid, what, label=None, thread_id=None):
        Mod.last = (pid, what, label)
        return pid


connections.mailbox = lambda a: ({"address": ACC, "type": "t"}, Mod)
connections.can = lambda c: {"archive": True, "trash": True, "label": True, "read": True}
res = mail.act({"id": f"mail:{mid}:1", "text": json.dumps({"mail_act": {"message": mid, "act": "move", "folder": "X"}})})
con = db.connect(read_only=True)
got = con.execute("SELECT m.provider_id, s.inbox, (SELECT string_agg(folder_id, ',') FROM mail_folder_members f WHERE f.message_id = m.id) FROM messages m"
                  " JOIN mail_state s ON s.message_id = m.id WHERE m.id = ?", [mid]).fetchone()
con.close()
check(res["result"].startswith("Moved to") and got == (pid_before, False, "X") and Mod.last == (pid_before, "move", "X"),
      "a Move keeps the stored email and its id, and its folder follows")
rows, _ = listing(view="folder", folder="X")
check([r["id"] for r in rows] == [mid], "the folder lists it")

# a snooze
inbox_ids = {r["id"] for r in listing()[0]}
check(mid not in inbox_ids, "(moved out of the inbox)")
other = next(r["id"] for r in listing()[0] if r["subject"] == "Invoice")
until = (dt.datetime.now() + dt.timedelta(hours=3)).isoformat(timespec="seconds")
r = mail.act({"id": f"mail:{other}:2", "text": json.dumps({"mail_act": {"message": other, "act": "snooze", "until": until}})})
check(r["result"].startswith("Snoozed") and other not in {x["id"] for x in listing()[0]} and other in {x["id"] for x in listing(view="snoozed")[0]},
      "a snoozed email leaves the inbox and shows in Snoozed")
db.execute("UPDATE mail_state SET snooze_until = ? WHERE message_id = ?", (dt.datetime.now() - dt.timedelta(minutes=1), other))   # its time has come
check(mail.wake() == 1 and other in {x["id"] for x in listing()[0]}, "when its time comes it is back in the inbox")
check(Mod.last[1] == "unread", "and the service is told it is unread")
print("all passed")
