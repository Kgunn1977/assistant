r"""Busy store (made-up data, stand-in mailbox): with the store held busy, a mail press the service took reports done, not failed,
and my own copy catches up once the store frees; a calendar delete made at Google while the store is busy says plainly it will show
at the next check.

    python tests\busy_store_acceptance.py
"""
import datetime as dt
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
home = tempfile.mkdtemp(prefix="busystore-")
box_path = os.path.join(home, "standin.json")
os.environ["ASSISTANT_LIVE_HOME"] = home
os.environ["STANDIN_BOX"] = box_path
sys.path.insert(0, LIVE)
sys.path.insert(0, os.path.join(LIVE, "core"))

STANDIN = r'''
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


def gather(conn, ctx):
    w = _store.MailWriter(conn["address"])
    for m in _load()["mail"]:
        w.add(m["id"], dt.datetime.fromisoformat(m["ts"]), "in", m["from"], conn["address"], m["subject"], m["body"], thread_id=m["id"],
              state={"unread": False, "inbox": True, "trashed": False, "labels": [], "cc": "", "from_name": m["name"], "header_id": "<" + m["id"] + "@x>", "refs": ""})
    return str(w.commit())


def refresh(conn, ctx=None):
    return 0


def act(conn, provider_id, what, label=None, thread_id=None):
    d = _load()
    d.setdefault("acts", []).append([provider_id, what])
    _save(d)
    return provider_id


def unsub_headers(conn, provider_id):
    return next(m for m in _load()["mail"] if m["id"] == provider_id).get("unsub", {"list": "", "post": ""})
'''

results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    os.makedirs(os.path.join(home, "taught", "connections"), exist_ok=True)
    with open(os.path.join(home, "taught", "connections", "standin_mail.py"), "w", encoding="utf-8") as f:
        f.write(STANDIN)
    ts = (dt.datetime.now() - dt.timedelta(days=2)).isoformat(timespec="seconds")
    with open(box_path, "w", encoding="utf-8") as f:
        json.dump({"mail": [{"id": "a1", "ts": ts, "from": "kim@friends.example", "name": "Kim", "subject": "Lunch", "body": "Lunch?",
                             "unsub": {"list": "", "post": ""}}]}, f)
    import db
    import connections
    import mail
    import calendar_view
    db.init_schema()
    connections.save({"id": "c1", "type": "standin_mail", "address": "me@one.example", "label": "me@one.example", "send": False, "on": True})
    import connections.run as runner
    sys.argv = ["run.py", "--kind", "email", "--run-id", "t-busy"]
    runner.main()
    mid = db.query("SELECT id FROM messages WHERE provider_id = 'a1'")[0][0]
    unread = lambda: db.query("SELECT s.unread FROM mail_state s WHERE s.message_id = ?", (mid,))[0][0]
    check("the stored mail starts read", unread(), False)

    # mail: the store is busy for the write after the service took the change
    real = db.connect
    busy = [True]

    def held(*a, **k):
        if busy[0] and not k.get("read_only"):
            raise TimeoutError("database busy: another process held it for the whole retry window.")
        return real(*a, **k)
    db.connect = held
    out = mail.act({"id": "t", "text": json.dumps({"mail_act": {"message": mid, "act": "unread"}})})
    check("a press the service took reports done, not failed, while the store is busy",
          [out["ok"], str(out["result"]).startswith("Not done"), "busy for a moment" in out["result"],
           [a[1] for a in json.load(open(box_path, encoding="utf-8")).get("acts", [])]], [True, False, True, ["unread"]])
    busy[0] = False
    check("the store frees and the next press or pass catches it up", [mail.catch_up(), unread(), mail.catch_up()], [1, True, 0])
    db.connect = real

    # calendar: a delete made at Google while the store is busy says it will show at the next check
    calendar_view._one = lambda b: ({"cal": {"id": "x", "name": "Home"}, "event_id": "e1", "row": ("e1", "Home", "Lunch", dt.datetime(2026, 12, 1, 12), dt.datetime(2026, 12, 1, 13), False, "", "")}, "")

    class Mod:
        def delete_event(self, *a):
            return {}
    calendar_view._conn = lambda cal: ({"id": "g"}, Mod())
    calendar_view._google = lambda call, verb, done: (call(), "")

    def busy_execute(*a, **k):
        raise TimeoutError("database busy")
    db.execute = busy_execute
    got = calendar_view.delete({"find": "lunch"})
    said = calendar_view.said(got, "delete")
    check("a calendar delete with the store busy is done and says it will show at the next check",
          [got["ok"], got.get("late"), "will show at the next check" in said], [True, True, True])

    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    finally:
        import shutil
        shutil.rmtree(home, ignore_errors=True)
    sys.exit(code)
