r"""Acceptance of writing mail from the Mail page, on a scratch home with made-up accounts and a stand-in sender (no real mailbox
is called, nothing is sent):

- a reply sets In-Reply-To and References from the original and names its Gmail conversation; a reply to all leaves out the
  owner's own addresses; a forward carries the original's files and no reply headers;
- Outlook's own reply (createReply) is used when the account has it, and an email sent from a card's draft is not needed here;
- a signature set for an account is in the new email's body, and the body is cleaned of anything that runs;
- addresses are suggested from what the mail has seen; a refused email sends nothing; a draft is kept and thrown away.

    python tests\mail_compose_acceptance.py
"""
import datetime as dt
import email
import email.policy
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
os.environ["ASSISTANT_LIVE_HOME"] = tempfile.mkdtemp(prefix="mailcompose-")
sys.path.insert(0, LIVE)
sys.path.insert(0, os.path.join(LIVE, "core"))

import connections  # noqa: E402
import db  # noqa: E402
import mail  # noqa: E402
import mail_compose as mc  # noqa: E402
from connections import _store  # noqa: E402

db.init_schema()


def check(ok, what):
    print(("PASS  " if ok else "FAIL  ") + what)
    if not ok:
        sys.exit(1)


GMAIL, OUTLOOK = "me@example.com", "me@example.net"
SENT = []


class Google:
    NAME, CAN_SEND = "Gmail", True

    @staticmethod
    def send_mime(conn, raw, thread_id=None):
        SENT.append(("mime", conn["address"], raw, thread_id))

    @staticmethod
    def save_draft(conn, raw, thread_id=None, replace=None):
        SENT.append(("draft", conn["address"], raw, replace))
        return "D1"

    @staticmethod
    def delete_draft(conn, did):
        SENT.append(("dropped", did))


class Outlook:
    NAME, CAN_SEND = "Outlook", True

    @staticmethod
    def send_mime(conn, raw, thread_id=None):
        SENT.append(("mime", conn["address"], raw, thread_id))

    @staticmethod
    def send_reply(conn, pid, kind, html, to, cc, bcc, files=()):
        SENT.append(("reply", pid, kind, to, [f[0] for f in files]))


CONNS = [{"id": "g", "kind": "email", "type": "google", "address": GMAIL, "send": True},
         {"id": "o", "kind": "email", "type": "outlook", "address": OUTLOOK, "send": True}]
connections.listed = lambda kind=None, everything=False: [c for c in CONNS if kind in (None, "email")]
connections.module = lambda t: {"google": Google, "outlook": Outlook}[t]

now = dt.datetime.now()
w = _store.MailWriter(GMAIL)
w.add("g1", now - dt.timedelta(minutes=30), "in", "pat@example.org", f"{GMAIL}, lee@example.org", "Plans", "Shall we meet?",
      thread_id="T-1", attachments=[("plan.txt", b"the plan")],
      state={"unread": True, "inbox": True, "header_id": "<g1@x>", "refs": "<g0@x>", "cc": "kim@example.org, " + GMAIL,
             "from_name": "Pat Example", "synced": True})
w.commit()
w = _store.MailWriter(OUTLOOK)
w.add("o1", now - dt.timedelta(minutes=20), "in", "sam@example.org", OUTLOOK, "Invoice", "See attached.",
      state={"unread": True, "inbox": True, "header_id": "<o1@x>", "refs": "", "synced": True})
w.commit()
gid = db.query("SELECT id FROM messages WHERE account = ?", (GMAIL,))[0][0]
oid = db.query("SELECT id FROM messages WHERE account = ?", (OUTLOOK,))[0][0]


def parse(raw):
    return email.message_from_bytes(raw, policy=email.policy.default)


# the panel's starting point
s = mc.start("reply", gid)
check(s["ok"] and s["account"] == GMAIL and s["to"] == ["pat@example.org"] and s["subject"] == "Re: Plans", "a reply starts to the sender, from the account it came to")
check("wrote:" in s["html"] and "Shall we meet?" in s["html"], "the quoted original is below the cursor")
s = mc.start("reply_all", gid)
check(s["to"] == ["pat@example.org", "lee@example.org"] and s["cc"] == ["kim@example.org"], "reply all keeps the others and drops the owner's own address")
f = mc.start("forward", gid)
check(f["subject"] == "Fwd: Plans" and f["files"] and f["files"][0]["name"] == "plan.txt" and f["to"] == [], "a forward starts empty and keeps the original's file")
check(mc.start("new")["account"] == GMAIL, "a new email starts from the first account")

# signature
mc.set_signature(GMAIL, "<b>Pat</b><script>alert(1)</script>")
check(mc.signatures()[GMAIL] == "<b>Pat</b>", "a signature is cleaned of anything that runs")
check('class="mc-sig"' in mc.start("new")["html"] and "Pat" in mc.start("new")["html"], "the signature is in a new email's body")
check(mc.set_signature("someone@else.example", "x")["ok"] is False, "a signature for an account that is not connected is refused")

# the one test of reply threading: the headers the sent reply carries
body = "<p>Yes, <b>Tuesday</b>.</p><script>x()</script>" + s["html"]
out = mc.send({"account": GMAIL, "to": "pat@example.org", "cc": "", "bcc": "boss@example.org", "subject": "Re: Plans", "html": body, "type": "reply",
               "message": gid, "files": []})
check(out["ok"], "a reply sends: " + str(out))
kind, acct, raw, thread = SENT[-1]
m = parse(raw)
check(m["In-Reply-To"] == "<g1@x>", "In-Reply-To is the original's Message-ID")
check(m["References"] == "<g0@x> <g1@x>", "References is the original's chain plus the original")
check(thread == "T-1", "the Gmail conversation id goes with it")
check(m["From"] == GMAIL and m["Bcc"] == "boss@example.org", "from the chosen account; the blind copy is in the message for the service to deliver")
htmlpart = m.get_body(("html",)).get_content()
check("<script" not in htmlpart and "<b>Tuesday</b>" in htmlpart and "Tuesday" in m.get_body(("plain",)).get_content(), "html and plain text, nothing that runs")

# a forward carries the file and has no reply headers
out = mc.send({"account": GMAIL, "to": ["x@example.org"], "subject": "Fwd: Plans", "html": f["html"], "type": "forward", "message": gid, "files": f["files"]})
m = parse(SENT[-1][2])
check(out["ok"] and m["In-Reply-To"] is None and [p.get_filename() for p in m.iter_attachments()] == ["plan.txt"], "a forward carries the file and no reply headers")

# Outlook makes its own reply
out = mc.send({"account": OUTLOOK, "to": ["sam@example.org"], "subject": "Re: Invoice", "html": "<p>Thanks</p>", "type": "reply", "message": oid, "files": []})
check(out["ok"] and SENT[-1][0] == "reply" and SENT[-1][2] == "reply", "an Outlook account answers through the service's own reply")

# refusals send nothing
n = len(SENT)
for what, p in (("no address", {"account": GMAIL, "to": [], "subject": "x", "html": "<p>x</p>"}),
                ("a bad address", {"account": GMAIL, "to": ["nobody"], "subject": "x", "html": "<p>x</p>"}),
                ("no subject", {"account": GMAIL, "to": ["a@example.org"], "subject": "", "html": "<p>x</p>"}),
                ("an empty message", {"account": GMAIL, "to": ["a@example.org"], "subject": "x", "html": "<p><br></p>"}),
                ("an account that is not connected", {"account": "z@example.org", "to": ["a@example.org"], "subject": "x", "html": "<p>x</p>"})):
    check(mc.send(p)["ok"] is False, "refused: " + what)
check(len(SENT) == n, "a refused email sends nothing")

# suggestions
check([x["email"] for x in mc.suggest("pat")["found"]] == ["pat@example.org"], "an address seen in mail is suggested as one types")
check(mc.suggest("p")["found"] == [], "one letter suggests nothing")

# drafts
sv = mc.save_draft({"account": GMAIL, "to": ["a@example.org"], "subject": "Later", "html": "<p>half</p>", "type": "new", "files": []})
check(sv["ok"] and mc.drafts()["drafts"][0]["subject"] == "Later" and SENT[-1][0] == "draft", "a draft is kept here and in the account's Drafts")
did = sv["id"]
check(mc.draft(did)["ok"], "a kept draft opens again")
mc.drop_draft(did)
check(mc.drafts()["drafts"] == [] and SENT[-1] == ("dropped", "D1"), "thrown away here and in the account's Drafts")
print("all passed")
