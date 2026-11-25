r"""The one thing the live system may send.

THE RULE, IN CODE. The live system sends exactly four kinds of thing (1, 2, 2b and 3 below).
  1. An email the owner wrote or edited on the page and pressed Send on themself, from the
     account they chose, to the recipients shown on their screen at that press (To, Copy to and
     Blind copy), as a new email, a reply or a forward, with the files shown.
  2. A draft that fits a STANDING APPROVAL the owner made (their yes of 11/16/26): an entry of the kind
     "send replies to one person" that they made by answering an offer card that named the kind and
     showed what it would have covered. send_standing() below is the only code that sends this way, and it
     refuses unless every check there holds: the owner's entry is on and not "always ask"; the draft goes only
     to the one person the owner's approvals went to, who is also the sender of the message the card is
     about (never an address taken from a message's own words); one recipient, no copy, no attachment, short,
     no link; sending is on and the account may send; the daily cap on such sends is not used up. Every such
     send is recorded with which approval allowed it. A draft that does not clearly fit is never sent: it
     stays on its card for the owner, as always.
  2b. A reply the assistant drafted, when the owner raised Reply drafts to learning level 2 or 3 in Settings (his answer
     of 11/25: raising a kind of reply to level 2 or 3 is the standing approval to send that kind of message). send_level()
     below is the only code that sends this way; the level is read fresh from Settings at the send, and every check of a
     standing approval holds (rule B12): only to the one person who wrote the card's own email, no copy, attachment or link,
     800 characters or less, from the account that email came to, within the same daily cap; never at level 1, never for
     any other kind of work. Every such send is recorded with its level.
  3. An email the assistant wrote (in Drafts, or in the same reply) that the owner's own words in Talk to your assistant,
     or typed on a card, tell it to send (chat._send): his words of that same message must ask to send (rule B11, checked
     here again), and the reply says what went, to whom and from which address. The record carries "origin": "chat" and
     "said": {"words", "at"} instead of a page press; every other check below is the same.
Nothing else sends: not a pass on its own account, not a card's Approve, not the assistant's own words, not a chase or a
reminder. No other code in the assistant can send mail.

A press arrives as an answer from the page whose text is JSON:

    {"send_email": {"account": "...", "to": ["..."], "cc": [], "bcc": [], "subject": "...", "body": "...",
                    "type": "new" | "reply" | "reply_all" | "forward", "source": <the email it answers or forwards, or null>,
                    "files": [{"name": "...", "ref": "att:12" | "msg:345:name" | "up:<hex>"}],
                    "attach": ["file name as shown"],
                    "shown": {"account": "...", "to": ["..."], "cc": [], "bcc": [], "type": "...", "attach": ["..."]}}}

`shown` is what the page had on screen when Send was pressed: the account,
every recipient, the kind of email and every attachment. The engine refuses a
press whose `shown` is not exactly what would go.

WHAT IS CHECKED BEFORE ANYTHING GOES (prepare):
  - owner sending is switched on in the owner's settings ("owner_send": {"on": true});
  - the record is a press from the page (an answer, with the page's device mark,
    pressed within the last few minutes), not something a program made up;
  - the account is one of the owner's own sending accounts (personal settings);
  - every recipient (To, Copy to, Blind copy) is a plain email address, 20 at most;
  - subject and body are not empty;
  - every attachment is a file of the owner's own mail, a file he added on the page, or a file
    the assistant holds for that item, and every one is fetched before anything goes: one that
    cannot be fetched means nothing is sent;
  - `shown` equals what would be sent.
ONE PRESS SENDS ONCE. A press is known by its item and its time. It is written
down as "sending" before the hand-off, so the same press again, or the same
email pressed twice within two minutes, sends nothing more.
EVERY SEND IS LOGGED (<home>\logs\sent.log): time, account, recipients,
subject, attachments, result. Never the body.

THE HAND-OFF goes through the owner's own connection for that account
(connections\). The email is built whole here first (mail.build: a reply keeps its
conversation and quotes the original, a forward carries the forwarded-message block and the
original text, with the files). The message lands in that account's own Sent folder.

    prepare(rec, item)                 everything up to the hand-off, sending nothing
    send_owner_email(rec, item)        prepare, then hand off once
"""
import datetime as dt
import hashlib
import html
import json
import os
import re
import threading

import common

SENT_LOG = os.path.join(common.LOGS, "sent.log")
PRESSES = os.path.join(common.HOME, "sent", "presses.json")
ADDRESS = re.compile(r"^[^@\s<>,;\"']+@[^@\s<>,;\"']+\.[A-Za-z]{2,}$")
MAX_RECIPIENTS = 20
MAX_ATTACH_BYTES = 20_000_000
PRESS_FRESH_SECONDS = 600           # a press older than this is not sent; the owner presses again
SAME_EMAIL_SECONDS = 120            # the same email pressed again this soon is the same press
_lock = threading.Lock()


class Refused(Exception):
    """Why a press was not sent, in plain words for the page."""


OFF = ("Sending email from your page is switched off. To turn it on, type /assistant:change sending in Claude on your computer.")
NO_ACCOUNT = ("No connected account can send yet. To connect a mail account, type /assistant:change accounts in Claude on your computer; "
              "a connected mail account can send unless you turned that off.")


def switched_on():
    return bool((common.settings().get("owner_send") or {}).get("on"))


def status():
    """Where sending from the page stands, in plain words: {"on", "accounts", "ready", "says"}.
    Ready means a Send press on the page would pass every check up to the hand-off."""
    on, who = switched_on(), accounts()
    says = OFF if not on else NO_ACCOUNT if not who else (
        "Sending is on: an email you press Send on, or tell me to send, goes out from " + ", ".join(who)
        + ". Nothing else is ever sent.")
    return {"on": on, "accounts": who, "ready": bool(on and who), "says": says}


def accounts():
    """The owner's own accounts that can send: named in their personal settings, connected, with sending on."""
    import connections
    can = {str(c.get("address") or "").lower() for c in connections.listed("email")
           if c.get("send") and getattr(connections.module(c["type"]), "CAN_SEND", False)}
    return [a for a in (common.personal().get("send_accounts") or []) if str(a).lower() in can]


def is_press(rec):
    """True when an answer from the page is a Send press."""
    return rec.get("action") == "answer" and str(rec.get("text") or "").lstrip().startswith('{"send_email"')


def _clean(addresses):
    return [str(a).strip() for a in (addresses or []) if str(a).strip()]


def _files_for(item, names):
    """The files the assistant already holds for this item, by the names the page showed."""
    held = {}
    for f in (item or {}).get("evidence_files") or []:
        if isinstance(f, dict) and f.get("path"):
            held[str(f.get("label") or os.path.basename(f["path"]))] = f["path"]
            held[os.path.basename(f["path"])] = f["path"]
    for d in (item or {}).get("documents") or []:
        if isinstance(d, dict) and d.get("path"):
            held[str(d.get("name") or os.path.basename(d["path"]))] = d["path"]
    out, size = [], 0
    for n in names:
        p = held.get(str(n))
        if not p or not os.path.isfile(p):
            raise Refused(f"The attachment \"{n}\" is not a file I hold for this item.")
        size += os.path.getsize(p)
        out.append(p)
    if size > MAX_ATTACH_BYTES:
        raise Refused("The attachments are too large to send together.")
    return out


# the owner's plain words for each broken rule of a Send press, in the order he has always been told them
PRESS_WORDS = (("B3", "did not come", "That did not come from pressing Send on the page."),
               ("B3", "no readable time", "That Send has no time I can read."),
               ("B3", "too old", "That Send is too old to act on. Press Send again."),
               ("B5", "copy or an attachment", "When I send without asking, it never has a copy or an attachment."),
               ("B2", "sending accounts", "That is not one of your sending accounts."),
               ("B4", "nobody in to", "There is nobody in To."),
               ("B4", "too many", f"More than {MAX_RECIPIENTS} recipients."),
               ("B4", "not an email address", None),
               ("B4", "is empty", "The subject or the message is empty."),
               ("B3", "on the screen", "What was on your screen is not what would be sent, so nothing was sent. Open it and press Send again."))


def _press_words(v, addresses):
    for rule, mark, words in PRESS_WORDS:
        for b in v["broken"]:
            if b["rule"] == rule and mark in b["says"].lower():
                if words is None:
                    return "Not an email address: " + ", ".join([a for a in addresses if not ADDRESS.match(a)][:3])
                return words
    return v["broken"][0]["says"]


def prepare(rec, item=None):
    """Everything up to the hand-off. Returns the message exactly as it would go. Sends nothing."""
    if not switched_on():
        raise Refused(OFF)
    m = None
    said = rec.get("origin") == "chat" and isinstance(rec.get("said"), dict)    # his own words in the box or on a card (chat._send)
    if rec.get("action") == "answer" and rec.get("at") and (said or (not rec.get("origin") and rec.get("device"))):
        try:
            m = json.loads(rec.get("text") or "")["send_email"]
        except (ValueError, KeyError, TypeError):
            raise Refused("I couldn't read the email from what you pressed.")
        if not isinstance(m, dict):
            raise Refused("I couldn't read the email from what you pressed.")
    m = m or {}
    account = str(m.get("account") or "").strip()
    to, cc = _clean(m.get("to")), _clean(m.get("cc"))
    subject, body = str(m.get("subject") or "").strip(), str(m.get("body") or "")
    names = [str(n) for n in (m.get("attach") or [])]
    # the guardrails' guard (b): the same checks the hooks use, the same plain words as before
    now = common.now().isoformat(timespec="seconds")
    authority = ({"kind": "said", "switched_on": True, "accounts": accounts(), "now": now,
                  "said": {"words": rec["said"].get("words"), "at": rec["said"].get("at")}} if said else
                 {"kind": "press", "switched_on": True, "accounts": accounts(), "now": now,
                  "press": {"action": rec.get("action"), "origin": rec.get("origin"), "device": rec.get("device"), "at": rec.get("at"),
                            "shown": m.get("shown") if isinstance(m.get("shown"), dict) else None}})
    v = common.rulebook().check_send(
        {"account": account, "to": to, "cc": cc, "bcc": m.get("bcc"), "subject": subject, "body": body, "attach": names,
         "type": m.get("type") or "new"}, authority)
    if said and not v["ok"] and any(b["rule"] == "B11" for b in v["broken"]):
        b = next(b for b in v["broken"] if b["rule"] == "B11")
        raise Refused(b["says"].rsplit("(", 1)[-1].rstrip(")").replace("the owner's", "your").capitalize() + ", so nothing was sent.")
    if not v["ok"]:
        raise Refused(_press_words(v, to + cc + _clean(m.get("bcc"))))
    bcc = _clean(m.get("bcc"))
    kind = str(m.get("type") or "new")
    refs = [f for f in (m.get("files") or []) if isinstance(f, dict) and f.get("ref")]
    if refs and [str(f.get("name")) for f in refs] != names:
        raise Refused("What was on your screen is not what would be sent, so nothing was sent. Open it and press Send again.")
    if refs:
        files = _fetch(refs, item)
    else:
        files = [(os.path.basename(p), _bytes(p)) for p in _files_for(item, names)]
    if sum(len(b) for _n, b in files) > MAX_ATTACH_BYTES:
        raise Refused("The attachments are too large to send together.")
    src = None
    if kind in ("reply", "reply_all", "forward"):
        import mail
        try:
            src = mail.source(int(m.get("source"))) if m.get("source") not in (None, "") else None
        except (ValueError, TypeError):
            src = None
        if src is None:
            raise Refused("The email this answers or forwards is not here any more, so nothing was sent.")
    digest = hashlib.sha256(json.dumps([account, to, cc, bcc, subject, body, names, kind, (src or {}).get("message")],
                                       ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"account": account, "to": to, "cc": cc, "bcc": bcc, "subject": subject, "type": kind, "source": src,
            "body": body, "attach": names, "files": files, "press": f"{rec.get('id')}|{rec.get('at')}", "digest": digest}


def _bytes(path):
    with open(path, "rb") as f:
        return f.read()


def _fetch(refs, item=None):
    """Every file the press names, as (name, bytes); the first that cannot be had refuses the whole send."""
    import mail
    held = {os.path.basename(str(f.get("path") or "")): f.get("path") for f in (item or {}).get("evidence_files") or [] if isinstance(f, dict)}
    out = []
    for f in refs[:20]:
        ref = str(f.get("ref"))
        try:
            if ref.startswith("card:") and held.get(ref[5:]) and os.path.isfile(held[ref[5:]]):
                out.append((str(f.get("name") or ref[5:]), _bytes(held[ref[5:]])))
                continue
            name, data = mail.file(ref)
        except LookupError as e:
            raise Refused(f"Not sent: {e} Nothing was sent.") from None
        except Exception as e:  # noqa: BLE001  the mail service could not be reached: the same
            raise Refused(f"Not sent: \"{f.get('name')}\" could not be fetched ({type(e).__name__}). Nothing was sent.") from None
        out.append((str(f.get("name") or name), data))
    return out


MARKUP = re.compile(r"<(p|div|br|span|a|table|ul|ol|b|i|strong|em|html|body)\b[^>]*>", re.I)


def _as_html(body):
    """Mail goes out as HTML. Plain words the owner typed keep their line breaks; markup is left as it is."""
    if MARKUP.search(body):
        return body
    return "<div>" + html.escape(body).replace("\r\n", "\n").replace("\n", "<br>\n") + "</div>"


def built(m):
    """The complete email a press would send, as bytes, and its conversation: for checking without sending."""
    import mail
    return mail.build(m, m.get("source"), m.get("files") or [])


def _handoff(m):
    """The last step: the owner's own connection for that account, handed the email built whole."""
    import connections
    if not m.get("files_are_paths"):
        conn, mod = connections.mailbox(m["account"])
        if mod is not None and hasattr(mod, "send_mime"):
            raw, thread = built(m)
            return connections.send_mime(m["account"], raw, thread)
        if m.get("bcc") or m.get("type") not in (None, "new"):
            raise RuntimeError(f"the {getattr(mod, 'NAME', 'mail')} connection can only send a plain new email")
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:        # a type that sends files by their place on the computer
            paths = []
            for i, (name, data) in enumerate(m.get("files") or []):
                os.makedirs(os.path.join(tmp, str(i)))
                paths.append(os.path.join(tmp, str(i), name))
                with open(paths[-1], "wb") as f:
                    f.write(data)
            return connections.send(m["account"], m["to"], m["cc"], m["subject"], _as_html(m["body"]), paths)
    return connections.send(m["account"], m["to"], m["cc"], m["subject"], _as_html(m["body"]), list(m["files"]))


def _presses():
    return common.read_json(PRESSES, {}) or {}


def send_owner_email(rec, item=None, handoff=None):
    """Send one email the owner pressed Send on. Returns {"ok", "sent", "result", ...}; never raises."""
    import replay_guard
    if replay_guard.on():
        return {"ok": False, "sent": False, "result": "Not sent: nothing goes out while I rebuild your history (replay)."}
    try:
        m = prepare(rec, item)
    except Refused as e:
        return {"ok": False, "sent": False, "result": f"Not sent. {e}"}
    now = common.now()
    with _lock:
        seen = _presses()
        earlier = seen.get(m["press"])
        if earlier is None:
            for p in seen.values():        # the same email, pressed twice in a row
                try:
                    recent = (now - dt.datetime.fromisoformat(p["at"])).total_seconds() <= SAME_EMAIL_SECONDS
                except (KeyError, ValueError):
                    recent = False
                if recent and p.get("digest") == m["digest"] and p.get("state") != "failed":
                    earlier = p
                    break
        if earlier is not None:
            return {"ok": True, "sent": False, "duplicate": True,
                    "result": earlier.get("result") or "That email is already being sent; it was not sent a second time."}
        seen[m["press"]] = {"state": "sending", "at": now.isoformat(timespec="seconds"), "digest": m["digest"]}
        common.write_json(PRESSES, seen)      # written down before the hand-off: this press can never send twice
    who = ", ".join(m["to"] + m["cc"] + m.get("bcc", []))
    try:
        detail = (handoff or _handoff)(m)
        ok, result = True, f"Sent from {m['account']} to {who}: \"{m['subject']}\"."
    except Exception as e:  # noqa: BLE001
        ok, detail = False, f"{type(e).__name__}: {str(e)[:200]}"
        result = f"Not sent: the mail service refused it ({type(e).__name__}). Your draft is kept; press Send to try again."
    with _lock:
        seen = _presses()
        seen[m["press"]] = {"state": "sent" if ok else "failed", "at": now.isoformat(timespec="seconds"),
                            "digest": m["digest"], "result": result}
        for k in sorted(seen, key=lambda k: seen[k].get("at", ""))[:-500]:
            seen.pop(k)
        common.write_json(PRESSES, seen)
    os.makedirs(os.path.dirname(SENT_LOG), exist_ok=True)
    with open(SENT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now.isoformat(timespec="seconds"), "account": m["account"], "to": m["to"], "cc": m["cc"],
                            "bcc": m.get("bcc", []), "type": m.get("type", "new"), "source": (m.get("source") or {}).get("message"),
                            "subject": m["subject"], "attach": m["attach"], "item": rec.get("id"), "body_chars": len(m["body"]),
                            "allowed_by": ("your words: " + str((rec.get("said") or {}).get("words") or "")[:200]) if rec.get("origin") == "chat" else "your Send press",
                            "result": "sent" if ok else "failed", "detail": str(detail)[:200]}, ensure_ascii=False) + "\n")
    return {"ok": ok, "sent": ok, "result": result, "account": m["account"], "to": m["to"], "cc": m["cc"], "bcc": m.get("bcc", []),
            "subject": m["subject"]}


# --- a draft that fits a standing approval the owner made ----------------------------------------------------------------
STANDING_MAX_BODY = 800             # a longer draft is never sent for him
LINK = re.compile(r"https?://|www\.", re.I)


def standing_fit(item, entry):
    """(the message as it would go, None) when this draft clearly fits the owner's entry, else (None, the plain reason).
    Sends nothing. The recipient must be the one person the entry names AND the sender of the message the card is about,
    as the mail service gave it (the card's `reply`), never an address found in anybody's words."""
    d = item.get("draft") if isinstance(item.get("draft"), dict) else None
    if not d:
        return None, "it has no draft"
    to, cc = [a.lower() for a in _clean(d.get("to"))], _clean(d.get("cc"))
    scope = str(entry.get("scope") or "").lower()
    reply = item.get("reply") if isinstance(item.get("reply"), dict) else None
    account = str(d.get("account") or (reply or {}).get("account") or "").strip()
    subject, body = str(d.get("subject") or "").strip(), str(d.get("body") or "")
    import standing
    v = common.rulebook().check_send(
        {"account": account, "to": to, "cc": cc, "bcc": d.get("bcc"), "subject": subject, "body": body, "attach": d.get("attach") or []},
        {"kind": "standing", "switched_on": switched_on(), "accounts": accounts(), "entry": entry, "left": standing.send_left(),
         "card": {"state": item.get("state"), "shelf": item.get("shelf"), "reply": reply}})
    if not v["ok"]:     # the first rule broken, in plain words; it comes to him as usual
        b = v["broken"][0]
        return None, (b["says"].split("(")[-1].rstrip(")") if "(" in b["says"] else b["says"]) + f" (rule {b['rule']})"
    digest = hashlib.sha256(json.dumps([account, [scope], [], subject, body, []], ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"account": account, "to": [scope], "cc": [], "subject": subject, "body": body, "attach": [], "files": [], "files_are_paths": True,
            "press": f"standing|{entry.get('id')}|{item.get('id')}|{digest[:16]}", "digest": digest}, None


def send_standing(item, entry_id, handoff=None):
    """Send one draft under the owner's standing approval. The entry is read fresh from the owner's file now, so a pause or a
    removal made a moment ago stops this send. Returns {"ok", "sent", "result", "message"}; never raises."""
    import replay_guard
    if replay_guard.on():
        return {"ok": False, "sent": False, "result": "Not sent: nothing goes out while I rebuild your history (replay)."}
    import standing
    if not switched_on():
        return {"ok": False, "sent": False, "result": OFF}
    entry = next((e for e in standing.ladder() if e["id"] == entry_id), None)
    if not entry or entry.get("kind") != "send_reply" or not entry.get("on", True) or entry.get("level") not in ("tell", "quiet"):
        return {"ok": False, "sent": False, "result": "Not sent. I'm not allowed to send this without asking right now."}
    if standing.send_left() <= 0:
        return {"ok": False, "sent": False, "result": "Not sent. I've reached today's limit on replies I send without asking, so it comes to you."}
    m, why = standing_fit(item, entry)
    if m is None:
        return {"ok": False, "sent": False, "result": f"Not sent: {why}. It comes to you as usual."}
    now = common.now()
    with _lock:
        seen = _presses()
        if m["press"] in seen or any(p.get("digest") == m["digest"] and p.get("state") != "failed" and
                                     (now - dt.datetime.fromisoformat(p["at"])).total_seconds() <= SAME_EMAIL_SECONDS for p in seen.values() if p.get("at")):
            return {"ok": True, "sent": False, "duplicate": True, "result": "That email is already being sent; it was not sent a second time."}
        seen[m["press"]] = {"state": "sending", "at": now.isoformat(timespec="seconds"), "digest": m["digest"]}
        common.write_json(PRESSES, seen)
    try:
        detail = (handoff or _handoff)(m)
        ok, result = True, f"Sent from {m['account']} to {m['to'][0]}: \"{m['subject']}\"."
    except Exception as e:  # noqa: BLE001
        ok, detail, result = False, f"{type(e).__name__}: {str(e)[:200]}", f"Not sent: the mail service refused it ({type(e).__name__}). It comes to you."
    with _lock:
        seen = _presses()
        seen[m["press"]] = {"state": "sent" if ok else "failed", "at": now.isoformat(timespec="seconds"), "digest": m["digest"], "result": result}
        common.write_json(PRESSES, seen)
    os.makedirs(os.path.dirname(SENT_LOG), exist_ok=True)
    with open(SENT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now.isoformat(timespec="seconds"), "account": m["account"], "to": m["to"], "cc": [], "subject": m["subject"], "attach": [],
                            "item": item.get("id"), "body_chars": len(m["body"]), "standing": entry_id, "result": "sent" if ok else "failed",
                            "detail": str(detail)[:200]}, ensure_ascii=False) + "\n")
    return {"ok": ok, "sent": ok, "result": result, "message": m}


def level_fit(item, level):
    """(the message as it would go, None) when this card's draft fits a send at learning level 2 or 3 (rule B12), else (None,
    the plain reason). Sends nothing. The recipient is the one person who wrote the card's own email, as the mail service
    gave it (the card's `reply`), never an address found in anybody's words; the account is the one that email came to."""
    d = item.get("draft") if isinstance(item.get("draft"), dict) else None
    if not d:
        return None, "it has no draft"
    reply = item.get("reply") if isinstance(item.get("reply"), dict) else None
    to = [a.lower() for a in _clean(d.get("to"))]
    account = str((reply or {}).get("account") or d.get("account") or "").strip()
    subject, body = str(d.get("subject") or "").strip(), str(d.get("body") or "")
    import rule_book
    import standing
    v = common.rulebook().check_send(
        {"account": account, "to": to, "cc": _clean(d.get("cc")), "bcc": d.get("bcc"), "subject": subject, "body": body,
         "attach": d.get("attach") or []},
        {"kind": "level", "switched_on": switched_on(), "accounts": accounts(), "level": level,
         "section": rule_book.section(item), "left": standing.send_left(),
         "card": {"state": item.get("state"), "shelf": item.get("shelf"), "reply": reply}})
    if not v["ok"]:
        b = v["broken"][0]
        return None, (b["says"].split("(")[-1].rstrip(")") if "(" in b["says"] else b["says"]) + f" (rule {b['rule']})"
    digest = hashlib.sha256(json.dumps([account, to, [], subject, body, []], ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"account": account, "to": to, "cc": [], "subject": subject, "body": body, "attach": [], "files": [],
            "files_are_paths": True, "press": f"level|{level}|{item.get('id')}|{digest[:16]}", "digest": digest}, None


def send_level(item, level, handoff=None):
    """Send one reply I drafted because the owner raised Reply drafts to learning level 2 or 3. The level is read fresh from
    Settings now and must match, so a lowering made a moment ago stops this send. Returns {"ok", "sent", "result",
    "message"}; never raises."""
    import replay_guard
    if replay_guard.on():
        return {"ok": False, "sent": False, "result": "Not sent: nothing goes out while the history is being rebuilt (replay)."}
    import rule_book
    import settings_page
    import standing
    if not switched_on():
        return {"ok": False, "sent": False, "result": OFF}
    now_level = settings_page.learning_levels().get(rule_book.section(item))
    if level not in (2, 3) or now_level != level:
        return {"ok": False, "sent": False, "result": "Not sent. Reply drafts are not at level 2 or 3."}
    if standing.send_left() <= 0:
        return {"ok": False, "sent": False, "result": "Not sent. The daily limit on sends I make on my own is used up; it comes to you."}
    m, why = level_fit(item, level)
    if m is None:
        return {"ok": False, "sent": False, "result": f"Not sent: {why}. It comes to you as usual."}
    now = common.now()
    with _lock:
        seen = _presses()
        if m["press"] in seen or any(p.get("digest") == m["digest"] and p.get("state") != "failed" and
                                     (now - dt.datetime.fromisoformat(p["at"])).total_seconds() <= SAME_EMAIL_SECONDS for p in seen.values() if p.get("at")):
            return {"ok": True, "sent": False, "duplicate": True, "result": "That email is already being sent; it was not sent a second time."}
        seen[m["press"]] = {"state": "sending", "at": now.isoformat(timespec="seconds"), "digest": m["digest"]}
        common.write_json(PRESSES, seen)
    try:
        detail = (handoff or _handoff)(m)
        ok, result = True, f"Sent from {m['account']} to {m['to'][0]}: \"{m['subject']}\"."
    except Exception as e:  # noqa: BLE001
        ok, detail, result = False, f"{type(e).__name__}: {str(e)[:200]}", f"Not sent: the mail service refused it ({type(e).__name__}). It comes to you."
    with _lock:
        seen = _presses()
        seen[m["press"]] = {"state": "sent" if ok else "failed", "at": now.isoformat(timespec="seconds"), "digest": m["digest"], "result": result}
        common.write_json(PRESSES, seen)
    os.makedirs(os.path.dirname(SENT_LOG), exist_ok=True)
    with open(SENT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": now.isoformat(timespec="seconds"), "account": m["account"], "to": m["to"], "cc": [], "subject": m["subject"], "attach": [],
                            "item": item.get("id"), "body_chars": len(m["body"]), "level": level, "result": "sent" if ok else "failed",
                            "detail": str(detail)[:200]}, ensure_ascii=False) + "\n")
    return {"ok": ok, "sent": ok, "result": result, "message": m}
