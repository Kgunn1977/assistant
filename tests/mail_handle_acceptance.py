r"""Acceptance of handling mail (mail_handle.py), on a scratch home with a stand-in mailbox of made-up mail (no real mailbox is called):

- the List-Unsubscribe header is read: one-click, only an https address, a mailto, http left out, none;
- a bulk archive from the assistant's chat: the plan shows its count and a sample and changes nothing; a yes in the same message,
  a not-quite-yes and a plan gone stale do nothing; a plain yes in a later message archives every email found, at the service and
  in the stored mail, once; the plan cannot be done twice;
- an Unsubscribe press posts the one-click and marks it done; one that needs the owner's page is refused.

    python tests\mail_handle_acceptance.py
"""
import datetime as dt
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
home = tempfile.mkdtemp(prefix="mailhandle-")
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
    now = dt.datetime.now()
    old = lambda days: (now - dt.timedelta(days=days)).isoformat(timespec="seconds")
    mail = [{"id": f"n{i}", "ts": old(60 + i), "from": "news@shop.example", "name": "Shop News", "subject": f"Weekly deals {i}", "body": "Deals.",
             "unsub": {"list": "<https://shop.example/u/1>, <mailto:u@shop.example?subject=stop>", "post": "List-Unsubscribe=One-Click"}} for i in range(5)]
    mail += [{"id": "new1", "ts": old(1), "from": "news@shop.example", "name": "Shop News", "subject": "Deals today", "body": "Deals.", "unsub": {"list": "", "post": ""}},
             {"id": "kim1", "ts": old(90), "from": "kim@friends.example", "name": "Kim", "subject": "Lunch", "body": "Lunch?", "unsub": {"list": "", "post": ""}},
             {"id": "pg1", "ts": old(70), "from": "page@club.example", "name": "Club", "subject": "Club news", "body": "News.",
              "unsub": {"list": "<https://club.example/leave>", "post": ""}}]
    with open(box_path, "w", encoding="utf-8") as f:
        json.dump({"mail": mail}, f)

    import common
    import db
    import connections
    import mail_handle as mh
    db.init_schema()
    connections.save({"id": "c1", "type": "standin_mail", "address": "me@one.example", "label": "me@one.example", "send": False, "on": True})
    import connections.run as runner
    sys.argv = ["run.py", "--kind", "email", "--run-id", "t-handle"]
    runner.main()

    # --- the header ---
    p = mh.parse_unsub
    check("one-click: an https address and the post header", p("<https://a.example/u?x=1>", "List-Unsubscribe=One-Click"),
          {"has": True, "one_click": True, "https": "https://a.example/u?x=1", "mailto": None})
    check("an https address alone is not one-click", [p("<https://a.example/u>")["one_click"], p("<https://a.example/u>")["https"]], [False, "https://a.example/u"])
    mt = p("<mailto:leave@a.example?subject=remove%20me>, <http://a.example/u>")
    check("a mailto is read with its subject, and http is left out", [mt["mailto"], mt["https"], mt["has"]],
          [{"to": "leave@a.example", "subject": "remove me", "body": ""}, "", True])
    check("no header, and a post header without an https address", [p("")["has"], p("<mailto:bad>", "List-Unsubscribe=One-Click")["has"],
                                                                      p("<http://a.example/u>", "List-Unsubscribe=One-Click")["one_click"]], [False, False, False])

    # --- a bulk archive from the chat ---
    acts = lambda: json.load(open(box_path, encoding="utf-8")).get("acts", [])
    inbox_ids = lambda: [r[0] for r in db.query("SELECT m.provider_id FROM messages m JOIN mail_state s ON s.message_id = m.id WHERE s.inbox AND regexp_matches(m.provider_id, '^n[0-9]$') ORDER BY 1")]
    t0 = common.now()
    plan = {"type": "mail_plan", "op": "archive", "find": {"from": "news@shop.example", "older_than_days": 30}}
    line = mh.chat_action(plan, t0, "archive the old shop emails")
    check("the plan says what it would do, with a count and a sample, and changes nothing",
          ["I would archive 5 emails from news@shop.example older than 30 days in inbox" in line, "Weekly deals 0" in line, "tell me yes" in line,
           acts(), len(inbox_ids())], [True, True, True, [], 5])
    check("a yes in the same message that planned it does nothing", [mh.chat_action({"type": "mail_go"}, t0, "yes").startswith("I will not do it in the same message"), acts()],
          [True, []])
    t1 = common.now() + dt.timedelta(seconds=5)
    check("a yes with a condition does nothing", [mh.chat_action({"type": "mail_go"}, t1, "yes but not the ones from last week").startswith("I did not take that as a plain yes"), acts()],
          [True, []])
    check("no find means no action on a whole mailbox", mh.chat_action({"type": "mail_plan", "op": "archive", "find": {}}, t1, "x").startswith("I need a sender, words from the subject"), True)
    done = mh.chat_action({"type": "mail_go"}, t1, "Yes, go ahead")
    check("a plain yes in a later message archives every email found, at the service and in the stored mail",
          [done.startswith("Archived 5 of 5 emails."), sorted({a[1] for a in acts()}), len(acts()), inbox_ids()], [True, ["archive"], 5, []])
    check("the same plan cannot be done twice", [mh.chat_action({"type": "mail_go"}, common.now() + dt.timedelta(seconds=9), "yes").startswith("I could not find that plan"), len(acts())],
          [True, 5])
    other = [r[0] for r in db.query("SELECT m.provider_id FROM messages m JOIN mail_state s ON s.message_id = m.id WHERE s.inbox ORDER BY 1")]
    check("other mail is untouched", other, ["kim1", "new1", "pg1"])

    # --- one email by a description (11/24: "Mark my newest email unread" found nothing, then waited for a yes) ---
    import chat
    chat._sent_now.clear()
    got, line = chat._do_all([{"type": "mail_plan", "op": "unread", "find": {"newest": 1}}], "Mark my newest email unread", common.now())
    unread_new1 = db.query("SELECT s.unread FROM messages m JOIN mail_state s ON s.message_id = m.id WHERE m.provider_id = 'new1'")[0][0]
    check("my newest email marked unread at once, with no yes asked, and said",
          [line.startswith("Marked unread:"), "Deals today" in line, "yes" in line, acts()[-1], unread_new1, chat._sent_now],
          [True, True, False, ["new1", "unread"], True, [{"what": "mail", "ok": True}]])
    check("a find for several still only shows the plan", "tell me yes" in mh.chat_action(
        {"type": "mail_plan", "op": "read", "find": {"from": "news@shop.example", "folder": "all", "newest": 2}}, common.now(), "x"), True)

    # --- a search in one account covers what that account sent (the TEST mails of 11/24 sat in Sent mail) ---
    from connections import _store as st
    w = st.MailWriter("me@one.example")
    w.add("sent1", now, "out", "me@one.example", "kim@friends.example", "[TEST-A] Sent copy", "Body.", thread_id="sent1",
          state={"unread": False, "inbox": False, "trashed": False, "labels": [], "cc": "", "from_name": "Me", "header_id": "<sent1@x>", "refs": ""})
    w.commit()
    subs = lambda spec: sorted(r["subject"] for r in mh.find(spec)["rows"])
    check("a find in an account with no folder named covers its sent mail",
          subs({"subject": "TEST-A", "account": "me@one.example"}), ["[TEST-A] Sent copy"])
    check("a find with no account or folder still skips sent mail, and folder sent finds only it",
          [subs({"subject": "TEST-A"}), subs({"subject": "TEST-A", "folder": "sent"}), subs({"subject": "Lunch", "folder": "sent"})],
          [[], ["[TEST-A] Sent copy"], []])

    # --- Unsubscribe ---
    posted = []
    mh._post = lambda url: posted.append(url) or 200
    mh._public_host = lambda url: True
    mid = lambda pid: db.query("SELECT id FROM messages WHERE provider_id = ?", (pid,))[0][0]
    press = lambda pid, via="auto": mh.unsubscribe({"id": "mail-unsub:t", "text": json.dumps({"mail_unsub": {"message": mid(pid), "via": via}})})
    r1 = press("n0")
    check("Unsubscribe posts the one-click and is marked done", [r1["result"], posted, mh.info(mid("n0"))["done"]],
          ["Unsubscribed from shop.example. It can take a few days to stop.", ["https://shop.example/u/1"], True])
    r2 = press("pg1")
    check("a sender with only a page is left to the owner's page, and nothing is posted", [r2["result"].startswith("Not done: that sender needs you"), len(posted)], [True, 1])
    check("an email without the header offers nothing", [mh.info(mid("kim1"))["has"], press("kim1")["result"]], [False, "Not done: that email has no unsubscribe link."])
    r3 = press("n1", "mailto")
    check("the mailto way is sent only when sending is on", r3["result"].startswith("Not done: sending is not on for me@one.example"), True)

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
