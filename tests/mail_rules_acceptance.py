r"""Acceptance of Settings, Mail rules, on a scratch home with stand-in Outlook and Gmail services (no real mailbox is called):

- each mailbox's rules are listed in plain words, and a rule with more than the page shows is read only;
- a rule is made from the form for Outlook (a full address) and for Gmail, and it reaches the service;
- a rule is deleted for both, and a read-only rule cannot be deleted from the page;
- a sign-in without the permission is said so plainly, and the other mailbox still works.

    python tests\mail_rules_acceptance.py
"""
import os
import sys
import tempfile
import types
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
home = tempfile.mkdtemp(prefix="mailrules-")
os.environ["ASSISTANT_LIVE_HOME"] = home
sys.path.insert(0, LIVE)
sys.path.insert(0, os.path.join(LIVE, "core"))

from connections import _http, google_mail, microsoft_mail  # noqa: E402
import connections  # noqa: E402
import mail_rules  # noqa: E402

OUT_ADDR, GM_ADDR = "pat@work.example", "pat@gmail.example"
MS_CONN = {"id": "c-ms", "type": "microsoft_mail", "address": OUT_ADDR}
GM_CONN = {"id": "c-gm", "type": "google_mail", "address": GM_ADDR}
FOLDERS = {OUT_ADDR: [{"id": "AAMk-f2", "path": "Inbox/Suppliers", "kind": "folder"},
                      {"id": "AAMk-arch", "path": "Archive", "kind": "archive"}],
           GM_ADDR: [{"id": "Label_1", "path": "Inbox/Suppliers", "kind": "label"}]}
GRANTED = {}


class Stand:
    """Outlook's inbox rules and Gmail's filters, kept in memory; the calls the module makes are answered here."""

    def __init__(self):
        self.rules = [{"id": "r1", "isEnabled": True, "conditions": {"fromAddresses": [{"emailAddress": {"address": "news@shop.example"}}]},
                       "actions": {"moveToFolder": "AAMk-f2"}}]
        self.filters = [{"id": "f1", "criteria": {"from": "acme.example"},
                         "action": {"addLabelIds": ["Label_1"], "removeLabelIds": ["INBOX"]}},
                        {"id": "f2", "criteria": {"from": "x@y.example", "hasAttachment": True},
                         "action": {"removeLabelIds": ["UNREAD"]}}]
        self.n = 10
        self.deny_graph = False

    def get(self, url, token=None, params=None, headers=None):
        if "messageRules" in url:
            return {"value": [dict(r) for r in self.rules]}
        if url.endswith("/settings/filters"):
            return {"filter": [dict(f) for f in self.filters]}
        raise AssertionError("unexpected read " + url)

    def call(self, method, url, token, obj=None, ok=(200, 201, 202, 204), headers=None):
        tail = urllib.parse.unquote(url.rsplit("/", 1)[1])
        if method == "GET":
            return 200, self.get(url, token)
        if "messageRules" in url:
            if self.deny_graph:
                raise _http.Refused(403, "Access is denied")
            if method == "POST":
                self.n += 1
                self.rules.append(dict(obj, id=f"r{self.n}"))
                return 201, self.rules[-1]
            if method == "DELETE":
                self.rules = [r for r in self.rules if r["id"] != tail]
                return 204, {}
        if url.endswith("/settings/filters") and method == "POST":
            self.n += 1
            self.filters.append(dict(obj, id=f"f{self.n}"))
            return 200, self.filters[-1]
        if "/settings/filters/" in url and method == "DELETE":
            self.filters = [f for f in self.filters if f["id"] != tail]
            return 204, {}
        raise AssertionError(f"unexpected {method} {url}")


stand = Stand()
_http.get_json = stand.get
_http.call_json = stand.call
microsoft_mail._token = lambda conn: "t"
google_mail.token_for = lambda conn: "t"

conns = [MS_CONN, GM_CONN]
connections.listed = lambda kind=None, everything=False: [dict(c) for c in conns]
connections.module = lambda t: {"microsoft_mail": microsoft_mail, "google_mail": google_mail}[t]
connections.mailbox = lambda addr: next(((dict(c), connections.module(c["type"])) for c in conns if c["address"] == addr), (None, None))
connections._granted = lambda: dict(GRANTED)

mail_stub = types.ModuleType("mail")
mail_stub.Busy = type("Busy", (Exception,), {})
mail_stub.folders = lambda account="": {"ok": True, "accounts": [{"address": a, "folders": FOLDERS[a]} for a in FOLDERS if not account or a == account]}
sys.modules["mail"] = mail_stub


def check(ok, what):
    print(("PASS  " if ok else "FAIL  ") + what)
    if not ok:
        sys.exit(1)


def press(op, **kw):
    return mail_rules.act({"id": "mail-rule:1", "action": "answer", "text": __import__("json").dumps({"mail_rule": dict(op=op, **kw)})})


# 1. listing: plain words, and read only for what the page does not show
listed = mail_rules.listing()
by = {a["address"]: a for a in listed["accounts"]}
ms_rules = by[OUT_ADDR]["rules"]
gm_rules = by[GM_ADDR]["rules"]
check(ms_rules[0]["words"] == "From news@shop.example → move to Inbox/Suppliers" and ms_rules[0]["can_delete"],
      "Outlook rule listed in plain words, and can be deleted")
check(gm_rules[0]["words"] == "From acme.example → move to Inbox/Suppliers" and gm_rules[0]["can_delete"],
      "Gmail filter listed in plain words, and can be deleted")
check(gm_rules[1]["read_only"] and not gm_rules[1]["can_delete"], "a filter with more than the page shows is read only")

# 2. create: Outlook needs a full address; Gmail takes a subject
bad = press("create", account=OUT_ADDR, when={"from": "acme.example", "subject": "", "to": ""}, do="move", folder="AAMk-f2")
check(bad["result"].startswith("Not done") and len(stand.rules) == 1, "Outlook refuses a domain where it needs a full address")
ok = press("create", account=OUT_ADDR, when={"from": "billing@acme.example", "subject": "", "to": ""}, do="move", folder="AAMk-f2")
check(ok["result"].startswith("Rule saved: From billing@acme.example") and len(stand.rules) == 2
      and stand.rules[-1]["actions"] == {"moveToFolder": "AAMk-f2"}, "Outlook rule made and sent to the service")
ok = press("create", account=GM_ADDR, when={"from": "", "subject": "invoice", "to": ""}, do="star")
check(ok["result"].startswith("Rule saved") and stand.filters[-1]["criteria"] == {"subject": "invoice"}
      and stand.filters[-1]["action"] == {"addLabelIds": ["STARRED"]}, "Gmail filter made and sent to the service")

# 3. delete: a confirmed delete removes the rule; a read-only filter is refused
ok = press("delete", account=GM_ADDR, rule="f1")
check(ok["result"].startswith("Deleted the rule") and all(f["id"] != "f1" for f in stand.filters), "Gmail filter deleted")
ok = press("delete", account=GM_ADDR, rule="f2")
check(ok["result"].startswith("Not done") and any(f["id"] == "f2" for f in stand.filters), "a read-only filter is not deleted")
ok = press("delete", account=OUT_ADDR, rule="r1")
check(ok["result"].startswith("Deleted the rule") and all(r["id"] != "r1" for r in stand.rules), "Outlook rule deleted")

# 4. no permission: said plainly, with the way to allow it; the other mailbox still works
GRANTED[MS_CONN["id"]] = "openid User.Read Mail.ReadWrite offline_access"
listed = mail_rules.listing()
by = {a["address"]: a for a in listed["accounts"]}
check("does not allow reading" in by[OUT_ADDR]["error"] and "press Sign in again" in by[OUT_ADDR]["error"],
      "an Outlook sign-in without the rules permission is said so, with the steps")
check(not by[GM_ADDR]["error"] and by[GM_ADDR]["rules"], "the Gmail mailbox still lists its rules")
GRANTED[MS_CONN["id"]] = "openid User.Read MailboxSettings.Read"
by = {a["address"]: a for a in mail_rules.listing()["accounts"]}
check(by[OUT_ADDR]["can_read"] and not by[OUT_ADDR]["can_write"] and "needs a new sign-in" in by[OUT_ADDR]["note"],
      "a sign-in that can read but not make rules says so, and lists the rules")
stand.deny_graph = True
no = press("create", account=OUT_ADDR, when={"from": "a@b.example", "subject": "", "to": ""}, do="read")
check(no["result"].startswith("Not done") and "press Sign in again" in no["result"], "a refused Outlook change says so plainly")

print("all mail rules checks passed")
