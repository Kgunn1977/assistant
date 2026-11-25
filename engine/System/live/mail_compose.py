r"""Writing mail on the Mail page: New, Reply, Reply all and Forward in a compose panel, the owner's own Send press.

The owner's own press sends directly, from the account he chose, through that account's real send (the reply threaded by its
In-Reply-To and References headers and the Gmail conversation id; Outlook makes its own reply, reply to all or forward when it
can). Nothing the assistant writes goes through here: its drafts keep waiting in Ready to send (ready.py, send.py) and can be
opened in this panel to edit; only the owner's Send press in the panel sends.

    config()                    the accounts that can send, each with its signature
    start(kind, message_id)     the panel's starting point for a new email, reply, reply to all or forward (who, subject, the
                                body with the account's signature and the quoted original, the original's files)
    suggest(q)                  addresses for To, Cc and Bcc as one types: known contacts and addresses seen in mail (local, fast)
    send(p)                     one email, sent now; p = {account, to, cc, bcc, subject, html, type, message, files, draft}
    save_draft(p)               keep the email unsent: here, and in the account's Drafts where the service allows
    drafts() / draft(id) / drop_draft(id)   the drafts kept here
    signatures() / set_signature(address, html)   the signature of each account
"""
import base64
import email.policy
import email.utils
import html as htmllib
import json
import mimetypes
import os
import re
import secrets
from email.message import EmailMessage
from html.parser import HTMLParser

import common
import mail

DIR = os.path.join(common.HOME, "mail")
DRAFTS = os.path.join(DIR, "drafts")
SIGNATURES = os.path.join(DIR, "signatures.json")
MOST_TOTAL = 25_000_000         # the files of one email together
MOST_TO = 100
SIG_MARK = "mc-sig"             # the class of the signature block in the body, so the page can swap it when From changes


# --- the body: a small set of tags, nothing that runs --------------------------------------------------------------------------
TAGS = {"b", "strong", "i", "em", "u", "br", "p", "div", "span", "ul", "ol", "li", "a", "blockquote", "pre", "h1", "h2", "h3", "hr"}
VOID = {"br", "hr"}
SAFE_URL = re.compile(r"^(https?://|mailto:)", re.I)


class _Clean(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.open, self.skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head", "title"):
            self.skip += 1
            return
        if self.skip or tag not in TAGS:
            return
        a = dict(attrs)
        extra = ""
        if tag == "a":
            href = str(a.get("href") or "").strip()
            if not SAFE_URL.match(href):
                return
            extra = f' href="{htmllib.escape(href, quote=True)}"'
        elif tag == "blockquote":
            extra = ' style="margin:0 0 0 .8ex;border-left:1px solid #ccc;padding-left:1ex"'
        elif tag in ("div", "span") and SIG_MARK in str(a.get("class") or "").split():
            extra = f' class="{SIG_MARK}"'
        self.out.append(f"<{tag}{extra}>")
        if tag not in VOID:
            self.open.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head", "title"):
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or tag not in TAGS or tag in VOID or tag not in self.open:
            return
        while self.open:
            t = self.open.pop()
            self.out.append(f"</{t}>")
            if t == tag:
                break

    def handle_data(self, data):
        if not self.skip:
            self.out.append(htmllib.escape(data))

    def result(self):
        while self.open:
            self.out.append(f"</{self.open.pop()}>")
        return "".join(self.out)


def clean_html(text):
    p = _Clean()
    p.feed(str(text or ""))
    p.close()
    return p.result()


def to_text(html_):
    """The plain-text twin of an email body, for mail programs that show text only."""
    t = re.sub(r"(?is)<(script|style).*?</\1>", "", str(html_ or ""))
    t = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-3]|blockquote|pre)>|<hr\s*/?>", "\n", t)
    t = re.sub(r"(?i)<li[^>]*>", "- ", t)
    t = re.sub(r"(?is)<a [^>]*href=\"([^\"]*)\"[^>]*>(.*?)</a>", lambda m: f"{re.sub('<[^>]+>', '', m.group(2))} ({m.group(1)})", t)
    t = htmllib.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"\n{3,}", "\n\n", t).strip() + "\n"


# --- accounts and signatures -----------------------------------------------------------------------------------------------------
def _sendable():
    """[(connection, module)] of the connected mailboxes that can send: sending is on for the connection and its type sends."""
    import connections
    out = []
    for c in connections.listed("email"):
        mod = connections.module(c["type"])
        if c.get("address") and c.get("send") and getattr(mod, "CAN_SEND", False):
            out.append((c, mod))
    return out


def signatures():
    got = common.read_json(SIGNATURES, {}) or {}
    return {str(k).lower(): str(v) for k, v in got.items() if isinstance(v, str)}


def set_signature(address, html_):
    address = str(address or "").strip().lower()
    if address not in {str(c["address"]).lower() for c, _m in _sendable()}:
        return {"ok": False, "error": "That is not one of your sending accounts."}
    sigs = signatures()
    body = clean_html(html_).strip()
    if to_text(body).strip():
        sigs[address] = body[:20_000]
    else:
        sigs.pop(address, None)
    os.makedirs(DIR, exist_ok=True)
    common.write_json(SIGNATURES, sigs)
    return {"ok": True, "signature": sigs.get(address, "")}


def config():
    sigs = signatures()
    return {"ok": True, "accounts": [{"address": str(c["address"]).lower(), "type": getattr(m, "NAME", c["type"]),
                                      "signature": sigs.get(str(c["address"]).lower(), "")} for c, m in _sendable()]}


def sig_block(address):
    s = signatures().get(str(address or "").lower(), "")
    return f'<div class="{SIG_MARK}">-- <br>{s}</div>' if s else ""


# --- who it can go to ------------------------------------------------------------------------------------------------------------
def suggest(q, limit=8):
    """[{name, email}] for what is typed so far (two letters or more): the owner's known contacts first, strongest first, then
    addresses seen in his mail. Stored data only; nothing is asked of a mail service."""
    q = str(q or "").strip().lower()
    if len(q) < 2:
        return {"ok": True, "found": []}
    out, seen = [], set()

    def add(name, addr):
        a = str(addr or "").strip().lower()
        if a and a not in seen and mail.ADDRESS.fullmatch(a) and len(out) < limit:
            seen.add(a)
            out.append({"name": str(name or "").strip(), "email": a})
    for p in (common.read_json(os.path.join(common.HOME, "known_people.json"), {}) or {}).get("people") or []:
        emails = p.get("email") if isinstance(p.get("email"), list) else [p.get("email")]
        if q in " ".join([str(p.get("name") or ""), str(p.get("company") or "")] + [str(e) for e in emails if e]).lower():
            for e in emails:
                add(p.get("name"), e)
    like = "%" + q.replace("%", "").replace("_", "") + "%"
    con = mail._read()
    try:
        for name, key in con.execute("SELECT name, key FROM contacts WHERE starts_with(key, 'email:') AND (lower(key) LIKE ? OR lower(coalesce(name, '')) LIKE ?)"
                                     " ORDER BY strength DESC, last_seen DESC NULLS LAST LIMIT 30", [like, like]).fetchall():
            add(name, str(key).split(":", 1)[1])
        if len(out) < limit:       # addresses seen in mail that the contacts have not caught up with yet
            for frm, name in con.execute("SELECT m.from_key, s.from_name FROM messages m LEFT JOIN mail_state s ON s.message_id = m.id"
                                         " WHERE m.channel = 'email' AND (lower(m.from_key) LIKE ? OR lower(coalesce(s.from_name, '')) LIKE ?)"
                                         " ORDER BY m.ts DESC LIMIT 60", [like, like]).fetchall():
                add(name, str(frm or "").split(":", 1)[-1])
    except Exception:  # noqa: BLE001  no contacts table yet: the known people are enough
        pass
    finally:
        con.close()
    own = mail.own_addresses()
    return {"ok": True, "found": [x for x in out if x["email"] not in own] + [x for x in out if x["email"] in own]}


# --- the panel's starting point ----------------------------------------------------------------------------------------------------
def _quote(src, kind):
    text = htmllib.escape(src.get("text") or "").replace("\r\n", "\n").replace("\n", "<br>\n")
    who = f"{src['from_name']} &lt;{htmllib.escape(src['from'])}&gt;" if src.get("from_name") else htmllib.escape(src["from"])
    if kind in ("reply", "reply_all"):
        return (f'<br><div>On {htmllib.escape(src["when"])}, {who} wrote:</div>'
                f'<blockquote>{text}</blockquote>')
    head = [("From", who), ("Date", htmllib.escape(src["when"])), ("Subject", htmllib.escape(src["subject"])),
            ("To", htmllib.escape(", ".join(src["to"])))] + ([("Cc", htmllib.escape(", ".join(src["cc"])))] if src.get("cc") else [])
    return "<br><div>---------- Forwarded message ---------<br>" + "".join(f"{k}: {v}<br>" for k, v in head) + f"</div><br>{text}"


def start(kind, message_id=None):
    """{ok, type, account, to, cc, bcc, subject, html, files, message, accounts} for a new panel."""
    kind = kind if kind in mail.KINDS else "new"
    src = mail.source(message_id) if message_id not in (None, "") and kind != "new" else None
    if kind != "new" and src is None:
        return {"ok": False, "error": "That email is not here any more."}
    have = config()["accounts"]
    if not have:
        return {"ok": False, "error": "No connected account can send yet. Open Setup, pick a mailbox and allow sending."}
    start_ = mail.draft_for(src, kind)
    names = [a["address"] for a in have]
    acct = (src or {}).get("account") if (src or {}).get("account") in names else names[0]
    body = "<p><br></p>" + sig_block(acct) + (_quote(src, kind) if src else "")
    return {"ok": True, "type": kind, "account": acct, "to": start_["to"], "cc": start_["cc"], "bcc": [], "subject": start_["subject"],
            "html": body, "files": [{"name": f["name"], "ref": f["ref"], "size": f.get("size")} for f in (src or {}).get("files") or []] if kind == "forward" else [],
            "message": (src or {}).get("message"), "accounts": have}


# --- building and sending ----------------------------------------------------------------------------------------------------------
class Refused(ValueError):
    """The email cannot go as it stands; the words are for the owner."""


def _clean_list(xs):
    out = []
    for x in xs if isinstance(xs, list) else re.split(r"[,;\n]+", str(xs or "")):
        m = re.search(r"<([^<>]+)>", str(x))
        a = (m.group(1) if m else str(x)).strip()
        if a:
            out.append(a)
    return out


def _check(p):
    """(clean payload, the sending connection and its type) or raises Refused."""
    acct = str(p.get("account") or "").strip().lower()
    pair = next(((c, m) for c, m in _sendable() if str(c["address"]).lower() == acct), None)
    if pair is None:
        raise Refused("Choose an account that can send.")
    to, cc, bcc = (_clean_list(p.get(k)) for k in ("to", "cc", "bcc"))
    bad = [a for a in to + cc + bcc if not mail.ADDRESS.fullmatch(a)]
    if not to and not cc and not bcc:
        raise Refused("Put at least one address in To.")
    if bad:
        raise Refused("Not an email address: " + ", ".join(bad[:3]))
    if len(to) + len(cc) + len(bcc) > MOST_TO:
        raise Refused(f"More than {MOST_TO} recipients.")
    kind = p.get("type") if p.get("type") in mail.KINDS else "new"
    return {"account": acct, "to": to, "cc": cc, "bcc": bcc, "subject": " ".join(str(p.get("subject") or "").split())[:300],
            "html": clean_html(p.get("html")), "type": kind, "message": p.get("message"),
            "files": [f for f in p.get("files") or [] if isinstance(f, dict)]}, pair


def _files(refs):
    """[(name, bytes, content type)]; the first file that cannot be had refuses the whole send."""
    out, total = [], 0
    for f in refs:
        try:
            name, data = mail.file(str(f.get("ref") or ""))
        except LookupError as e:
            raise Refused(str(e)) from None
        total += len(data)
        if total > MOST_TOTAL:
            raise Refused("The files are too large to send together.")
        out.append((name, data, mimetypes.guess_type(name)[0] or "application/octet-stream"))
    return out


def build(p, src, files, draft=False):
    """The complete email (bytes) and the conversation id (Gmail's threadId) it belongs to. A reply or reply to all carries
    In-Reply-To and References from the original, so mail programs keep it in the conversation."""
    msg = EmailMessage(policy=email.policy.SMTP)
    msg["From"] = p["account"]
    if p["to"]:
        msg["To"] = ", ".join(p["to"])
    if p["cc"]:
        msg["Cc"] = ", ".join(p["cc"])
    if p["bcc"]:
        msg["Bcc"] = ", ".join(p["bcc"])
    msg["Subject"] = p["subject"]
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=p["account"].split("@")[-1] or None)
    thread = None
    if src and p["type"] in ("reply", "reply_all"):
        if src.get("header_id"):
            msg["In-Reply-To"] = src["header_id"]
            msg["References"] = " ".join(x for x in (src.get("refs") or "", src["header_id"]) if x).strip()
        thread = src.get("thread")
    msg.set_content(to_text(p["html"]))
    msg.add_alternative("<html><body>" + p["html"] + "</body></html>", subtype="html")
    for name, data, ctype in files:
        major, _, minor = ctype.partition("/")
        msg.add_attachment(data, maintype=major, subtype=minor, filename=name)
    return msg.as_bytes(), thread


def _source_of(p):
    mid = p.get("message")
    if p["type"] == "new" or mid in (None, ""):
        return None
    return mail.source(int(mid))


def _provider_id(mid):
    con = mail._read()
    try:
        row = con.execute("SELECT coalesce(s.provider_id, m.provider_id) FROM messages m LEFT JOIN mail_state s ON s.message_id = m.id WHERE m.id = ?",
                          [int(mid)]).fetchone()
    finally:
        con.close()
    return row[0] if row else None


def send(payload):
    """The owner's Send press. Returns {ok, result} or {ok: False, error} in plain words; nothing is sent on a refusal."""
    import connections
    try:
        p, (conn, mod) = _check(payload or {})
        src = _source_of(p)
        if p["type"] != "new" and src is None:
            raise Refused("The email you are answering is not here any more. Close this and start again.")
        if not p["subject"]:
            raise Refused("Write a subject.")
        if not to_text(p["html"]).strip():
            raise Refused("Write the message.")
        files = _files(p["files"])
        raw, thread = build(p, src, files)
    except Refused as e:
        return {"ok": False, "error": str(e)}
    how = "send"
    try:
        sent = False
        if src and p["type"] != "new" and hasattr(mod, "send_reply") and _provider_id(p["message"]):
            try:
                mod.send_reply(conn, _provider_id(p["message"]), p["type"], "<html><body>" + p["html"] + "</body></html>",
                               p["to"], p["cc"], p["bcc"], files)
                sent, how = True, "service reply"
            except Exception as e:  # noqa: BLE001
                if type(e).__name__ != "NotStarted":      # it may have gone: never sent twice
                    raise
        if not sent:
            connections.send_mime(p["account"], raw, thread)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"Not sent: {p['account']} refused it ({type(e).__name__}). Your email is still open; nothing went out."}
    common.log_line(os.path.join(common.LOGS, "mail.log"), f"compose {p['type']} {how} {p['account']} to {len(p['to'])}+{len(p['cc'])}+{len(p['bcc'])}")
    if payload.get("draft"):
        drop_draft(payload["draft"])
    return {"ok": True, "result": "Sent."}


# --- drafts -------------------------------------------------------------------------------------------------------------------------
def _path(draft_id):
    if not re.fullmatch(r"[0-9a-f]{16}", str(draft_id or "")):
        raise Refused("That draft is not known.")
    return os.path.join(DRAFTS, f"{draft_id}.json")


def save_draft(payload):
    """Keep the email unsent. Stored here whatever it holds; also put in the account's Drafts when the service lets it
    (the answer says which). A draft saved before is replaced."""
    payload = payload or {}
    try:
        did = payload.get("draft") or secrets.token_hex(8)
        path = _path(did)
        acct = str(payload.get("account") or "").strip().lower()
        pair = next(((c, m) for c, m in _sendable() if str(c["address"]).lower() == acct), None)
        before = common.read_json(path, {}) or {}
        keep = {"id": did, "account": acct, "to": _clean_list(payload.get("to")), "cc": _clean_list(payload.get("cc")),
                "bcc": _clean_list(payload.get("bcc")), "subject": " ".join(str(payload.get("subject") or "").split())[:300],
                "html": clean_html(payload.get("html")), "type": payload.get("type") if payload.get("type") in mail.KINDS else "new",
                "message": payload.get("message"), "saved": common.now().isoformat(timespec="seconds"),
                "files": [{"name": str(f.get("name") or "")[:200], "ref": str(f.get("ref") or ""), "size": f.get("size")}
                          for f in payload.get("files") or [] if isinstance(f, dict)],
                "remote": before.get("remote")}
    except Refused as e:
        return {"ok": False, "error": str(e)}
    also = ""
    if pair is not None and hasattr(pair[1], "save_draft"):
        try:
            src = _source_of(keep)
            raw, thread = build(keep, src, _files(keep["files"]), draft=True)
            keep["remote"] = pair[1].save_draft(pair[0], raw, thread, replace=keep.get("remote"))
            also = f" and in the Drafts of {acct}"
        except Exception as e:  # noqa: BLE001  kept here all the same
            keep["remote"] = None
            also = f"; {acct} would not take it into its Drafts ({type(e).__name__})"
    os.makedirs(DRAFTS, exist_ok=True)
    common.write_json(path, keep)
    return {"ok": True, "id": did, "result": "Draft kept here" + also + "."}


def drafts():
    out = []
    if os.path.isdir(DRAFTS):
        for n in os.listdir(DRAFTS):
            d = common.read_json(os.path.join(DRAFTS, n), None)
            if isinstance(d, dict) and d.get("id"):
                out.append({"id": d["id"], "subject": d.get("subject") or "(no subject)", "to": d.get("to") or [], "saved": d.get("saved") or ""})
    return {"ok": True, "drafts": sorted(out, key=lambda d: d["saved"], reverse=True)}


def draft(draft_id):
    try:
        d = common.read_json(_path(draft_id), None)
    except Refused as e:
        return {"ok": False, "error": str(e)}
    if not isinstance(d, dict):
        return {"ok": False, "error": "That draft is not here any more."}
    return dict(d, ok=True, accounts=config()["accounts"])


def drop_draft(draft_id):
    """The owner's Throw away, or the draft having been sent: gone here and from the account's Drafts."""
    try:
        path = _path(draft_id)
    except Refused as e:
        return {"ok": False, "error": str(e)}
    d = common.read_json(path, None) or {}
    pair = next(((c, m) for c, m in _sendable() if str(c["address"]).lower() == d.get("account")), None)
    if d.get("remote") and pair is not None and hasattr(pair[1], "delete_draft"):
        try:
            pair[1].delete_draft(pair[0], d["remote"])
        except Exception:  # noqa: BLE001  gone here; the copy in Drafts can be deleted by hand
            pass
    try:
        os.remove(path)          # a draft is the owner's own working copy, kept only until it is sent or thrown away
    except OSError:
        pass
    return {"ok": True, "result": "Draft thrown away."}
