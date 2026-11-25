r"""Acceptance: opening an email never waits for the unsubscribe lookup, and the lookup never waits for the mail service.

- the page's lookup answers at once ("pending") while the mail service is slow, and asks it in the background;
- two emails opened in a row, while that lookup is still running, each open in well under half a second;
- when the answer is in, it is shown, and a second email from the same sender is answered from the first's answer without asking.

    python tests\mail_unsub_speed_acceptance.py
"""
import datetime as dt
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
os.environ["ASSISTANT_LIVE_HOME"] = tempfile.mkdtemp(prefix="unsubspeed-")
sys.path.insert(0, LIVE)
sys.path.insert(0, os.path.join(LIVE, "core"))

import connections  # noqa: E402
import db  # noqa: E402
import mail  # noqa: E402
import mail_cache  # noqa: E402
import mail_handle  # noqa: E402
from connections import _store  # noqa: E402

db.init_schema()


def check(ok, what):
    print(("PASS  " if ok else "FAIL  ") + what)
    if not ok:
        sys.exit(1)


ACC = "me@example.com"
now = dt.datetime.now()
w = _store.MailWriter(ACC)
for pid, sender, mins in (("p1", "news@shop.example", 30), ("p2", "news@shop.example", 20), ("p3", "dana@vendor.example", 10)):
    w.add(pid, now - dt.timedelta(minutes=mins), "in", sender, ACC, "Hello " + pid, "body " + pid, thread_id="T-" + pid,
          state={"unread": True, "inbox": True, "header_id": "<" + pid + "@x>", "refs": "", "folders": ["I"], "synced": True})
w.commit()
mail.accounts = lambda: []
calls = []


class Service:
    @staticmethod
    def unsub_headers(conn, pid):
        calls.append(pid)
        time.sleep(2.0)
        return {"list": "<https://shop.example/u?t=" + pid + ">", "post": "List-Unsubscribe=One-Click"}


connections.mailbox = lambda address: ({"address": address}, Service)
mail_cache.enable()
mail_cache.refresh(True)
ids = {r["subject"]: r["id"] for r in mail.rows(account=ACC)["rows"]}
p1, p2, p3 = ids["Hello p1"], ids["Hello p2"], ids["Hello p3"]

t = time.time()
first = mail_handle.lookup(p1)
check(first.get("pending") and time.time() - t < 0.3, "the lookup answers at once, pending, while the service is slow")
for mid in (p1, p3):
    t = time.time()
    got = mail.thread(mid, fresh=False)
    check(got["ok"] and time.time() - t < 0.5, "an email opens in under half a second while a lookup is running")
t = time.time()
check(mail_handle.lookup(p3).get("pending") and time.time() - t < 0.3, "a second lookup meanwhile does not wait either")
check(mail_handle.lookup(p1).get("pending") and calls == ["p1", "p3"][:len(calls)] and calls.count("p1") == 1, "the same email is asked of the service once")
end = time.time() + 10
while time.time() < end and mail_handle._asking:
    time.sleep(0.1)
done = mail_handle.lookup(p1)
check(done.get("ok") and done.get("has") and done.get("one_click"), "the answer shows when it is in")
n = len(calls)
t = time.time()
same = mail_handle.lookup(p2)
check(same.get("has") and len(calls) == n and time.time() - t < 0.3, "another email from the same sender is answered without asking the service")
print("all passed")
