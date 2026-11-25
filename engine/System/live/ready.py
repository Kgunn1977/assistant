r"""Emails Talk to your assistant wrote, put on the page as drafts in "Ready to send" (the owner's decision of 11/17/26, plan answers 48
and 49). The chat never sends and never shows an email's text in Talk to your assistant: each email it writes is one card here, and only
the owner's own press on the page sends (send.py, every rule of it and of the guardrails).

    make(action, when, n, batch)   one ACTION {"type": "draft", ...} from Talk to your assistant: a card in Ready to send, or the plain reason not;
                                   a reply, reply to all or forward carries the original email whole (mail.py)
    start_from_mail(rec)           the owner's Reply, Reply all, Forward or New email press in the Mail part: a draft to finish
    known_addresses(about)         who a draft may go to: the owner's known contacts, and the sender of the message it answers
    send_all(rec)                  the owner's one Send all press, covering each listed draft; each is checked and sent once
"""
import json
import os
import sys
import re

import common

KEY = "live:ready-"            # source_key of a draft Talk to your assistant wrote: live:ready-<batch>-<n>
AREA = "From you"


def known_addresses(about=None):
    """Addresses a draft may go to: every address of the owner's known contacts, plus the sender of the message the draft
    answers (the card it is about, as the mail service gave it)."""
    out = set()
    people = common.read_json(os.path.join(common.HOME, "known_people.json"), {}) or {}
    for p in people.get("people") or []:
        for e in (p.get("email") if isinstance(p.get("email"), list) else [p.get("email")]):
            if e:
                out.add(str(e).strip().lower())
    try:
        import db
        for (k,) in db.query("SELECT key FROM contacts WHERE starts_with(key, 'email:')"):
            out.add(str(k).split(":", 1)[1].strip().lower())
    except Exception:  # noqa: BLE001  no contacts table yet: the known people are enough
        pass
    if about:
        try:
            import db
            import items
            con = db.connect(read_only=True)
            try:
                rows = items.rows("id = ?", (about,))
                if rows:
                    reply = items.reply_for(con, rows[0].get("source_messages") or [])
                    out |= {str(a).lower() for a in (reply or {}).get("to") or []}
            finally:
                con.close()
        except Exception:  # noqa: BLE001
            pass
    return out


def _message_of(a, about):
    """The stored email a draft replies to or forwards: the ACTION's "message", else the newest email behind the card it is about."""
    raw = str(a.get("message") or "").strip().lstrip("#")
    if raw.isdigit():
        return int(raw)
    if about and a.get("kind") in ("reply", "reply_all", "forward"):
        import items
        rows = items.rows("id = ?", (about,))
        for mid in reversed((rows[0].get("source_messages") if rows else None) or []):
            if str(mid).isdigit():
                return int(mid)
    return None


def make(action, when, n, batch, made_by=None, require_body=True):
    """(card id or None, plain line for Talk to your assistant or ''). The draft is checked by the guardrails (B10) before any card is made.
    action: {"type": "draft", "kind": "new" | "reply" | "reply_all" | "forward", "message": <the email it answers or forwards>,
    "account", "to", "cc", "bcc", "subject", "body", "attach": [names of that email's files to keep, or omitted for all],
    "why", "about": <card id>}. A reply or forward carries the original (its text, its files, the headers that keep it in its
    conversation); recipients and subject not given are filled the way the page fills them."""
    import mail
    import send
    a = action or {}
    clean = lambda xs: [str(x).strip() for x in (xs if isinstance(xs, list) else [xs] if xs else []) if str(x).strip()]   # noqa: E731
    about = str(a.get("about") or "").strip() or None
    kind = str(a.get("kind") or "new").strip().lower().replace(" ", "_").replace("reply-all", "reply_all")
    kind = kind if kind in mail.KINDS else "new"
    src = None
    if kind != "new":
        mid = _message_of(dict(a, kind=kind), about)
        src = mail.source(mid) if mid else None
        if src is None:
            return None, ("I did not put one email on your page: the email to " + ("forward" if kind == "forward" else "answer")
                          + " was not found, so it could not carry the original.")
    start = mail.draft_for(src, kind)
    to, cc, bcc = clean(a.get("to")) or start["to"], clean(a.get("cc")) or start["cc"], clean(a.get("bcc"))
    found = []
    for field in (to, cc, bcc):         # a name with no address: the one on file is used (people.py), never a guess
        for i, x in enumerate(field):
            if "@" in x:
                continue
            import people as people_mod
            who = people_mod.lookup(x + " " + str(a.get("subject") or "") + " " + str(a.get("why") or ""), "email")
            if len(who) != 1:
                return None, (f"I did not put one email on your page: I need {x}'s email address and " +
                              ("it isn't on file. What is it?" if not who else "more than one person on file has that name: " +
                               ", ".join(people_mod.describe(p) for p in who[:4]) + ". Which one?"))
            field[i] = who[0]["email"][0]
            place = (who[0].get("where") or {}).get(field[i]) or people_mod.where_found(field[i])
            found.append(f"{who[0]['name']}'s address, {field[i]}, is from {place or 'your contacts'}.")
    subject = " ".join(str(a.get("subject") or "").split())[:300] or start["subject"]
    body = str(a.get("body") or "").strip()
    accounts = send.accounts()
    account = str(a.get("account") or "").strip()
    if account.lower() not in {x.lower() for x in accounts}:
        account = start["account"] or (accounts[0] if accounts else account)
    files = start["files"]
    if src and isinstance(a.get("attach"), list):
        keep = {str(x).strip().lower() for x in a["attach"]}
        files = [f for f in files if str(f["name"]).lower() in keep]
    for f in a.get("files") or []:            # files added from another email or an upload: {"name", "ref"}
        if isinstance(f, dict) and re.fullmatch(r"(att:\d+|msg:\d+:.+|up:[0-9a-f]{24})", str(f.get("ref") or "")):
            files.append({"name": str(f.get("name") or "file")[:200], "ref": str(f["ref"]), "size": f.get("size")})
    how = None
    if body and require_body:       # every draft the assistant writes: the owner's voice, then the humanize pass (voice.py)
        import voice
        try:
            body, how = voice.write(body, to, subject)
        except Exception as e:  # noqa: BLE001  the draft is never lost over its voice
            how = {"level": None, "humanized": False, "why_not": f"{type(e).__name__}"}
    people = known_addresses(about) | {x.lower() for x in ((src or {}).get("to") or []) + ((src or {}).get("cc") or []) + [(src or {}).get("from") or ""] if x}
    v = common.rulebook().check_draft({"to": to, "cc": cc, "bcc": bcc, "subject": subject, "body": body}, sorted(people),
                                      started=not require_body)
    if not v["ok"]:
        return None, "I did not put one email on your page: " + "; ".join(f"rule {b['rule']}: {b['says']}" for b in v["broken"])
    import items
    why = " ".join(str(a.get("why") or "").split())[:300] or "You asked for it in Talk to your assistant."
    if found:
        why = (why + " " + " ".join(found)).strip()
    draft = {"account": account, "to": to, "cc": cc, "bcc": bcc, "subject": subject, "body": body, "type": kind,
             "files": files, "attach": [f["name"] for f in files], "source": src}
    if how:
        draft["voice"] = how
    draft["base"] = mail.sig(draft)
    where = "in Talk to your assistant" if made_by is None else "from your mail"
    iid, _ = items.upsert(f"{KEY}{batch}-{n}", "chat", kind="approval", area=AREA, state="question", status=None,
                          title=subject or "(no subject)", detail=why, asks=["Send it?"], why=why, draft=draft,
                          source_who=common.owner(), source_when=when,
                          source_ref=f"Written by me {where}, {when.month}/{when.day} {when.strftime('%I:%M %p').lstrip('0')}",
                          extra={"ready": dict({"batch": batch, "why": why, "about": about}, **({"made_by": made_by} if made_by else {}))})
    return iid, ""


def start_from_mail(rec):
    """The owner's press on an email in the Mail part: {"mail_draft": {"message": <id or null>, "type": "reply" | "reply_all" |
    "forward" | "new"}}. A draft in Ready to send, recipients and files filled, the words left for him; nothing is sent."""
    try:
        got = json.loads(rec.get("text") or "")["mail_draft"]
        kind = str(got.get("type") or "new")
        mid = got.get("message")
    except (ValueError, KeyError, TypeError, AttributeError):
        return {"ok": False, "error": "That press could not be read. Nothing was made.", "items": []}
    when = common.now()
    names = {"reply": "a reply", "reply_all": "a reply to all", "forward": "a forward", "new": "a new email"}
    iid, said = make({"type": "draft", "kind": kind, "message": mid,
                      "why": f"You started {names.get(kind, 'an email')} from your mail."},
                     when, 0, f"mail-{when:%Y%m%d-%H%M%S-%f}", made_by=str(rec.get("id") or ""), require_body=False)
    if not iid:
        return {"ok": True, "items": [], "result": said}
    import answers
    import items
    item = items.card_for(iid)
    if item is not None:
        answers._patch_snapshot([item])
    return {"ok": True, "items": [item] if item else [], "result": "In Drafts, in Email.", "thought": False}


def adopt_card_drafts(pass_id):
    """A draft an earlier version left on a card itself (its old answer step wrote drafts there) goes to Ready to send,
    like every other draft, by the same checks; the card then says where it is. Returns (moved, problems)."""
    import replay_guard
    replay_guard.refuse("moving card drafts to Drafts")
    import items
    moved, problems = 0, []
    for it in items.rows(f"state <> 'done' AND draft IS NOT NULL AND source_key NOT LIKE '{KEY}%' AND source_key NOT LIKE 'test:%'"):
        d = it.get("draft") if isinstance(it.get("draft"), dict) else {}
        if d.get("outbox_id") or not str(d.get("body") or "").strip():
            continue
        title = str(it.get("short_header") or it.get("title") or "")[:120]
        iid, said = make({"type": "draft", "account": d.get("account"), "to": d.get("to"), "cc": d.get("cc"),
                          "subject": d.get("subject"), "body": d.get("body"), "about": it["id"],
                          "why": f"Written on the card \"{title}\"; it waits here for your Send."},
                         common.now(), 0, f"card-{it['id']}")
        if not iid:
            problems.append(f"The draft on the card \"{title}\" could not go to Drafts: {said}")
            continue
        did = (it.get("assistant_did") or "")
        items.update(it["id"], pass_id, draft=None, state="handled", status="Email in Drafts",
                     assistant_did=(did + "\n" if did else "") + "The draft written on this card is now in Drafts, in the Email part of "
                                                                  "your page; nothing is sent until you press Send there.")
        moved += 1
    return moved, problems


def _with_base(d):
    import mail
    d["base"] = mail.sig(d)
    return d


def keep(rec):
    """A reply the owner started on a card and left unsent: {"keep_draft": {"account", "to", "cc", "subject", "body"}} on key
    ready-keep:<card id>:<ms>. It goes to Ready to send as his own draft (one per card: the latest words replace the last)."""
    import re
    m = re.match(r"^ready-keep:(L\d+):\d+$", str(rec.get("id") or ""))
    try:
        d = json.loads(rec.get("text") or "")["keep_draft"]
    except (ValueError, KeyError, TypeError):
        d = None
    if not m or not isinstance(d, dict):
        return {"ok": False, "error": "That draft could not be read. Nothing was kept.", "items": []}
    words = common.rulebook().book()[1]
    addr = re.compile(words["address"])
    to = [str(x).strip() for x in d.get("to") or [] if str(x).strip()]
    cc = [str(x).strip() for x in d.get("cc") or [] if str(x).strip()]
    if not to or any(not addr.match(x) for x in to + cc):
        return {"ok": False, "error": "Not kept: someone in To or Copy to is not an email address.", "items": []}
    import items
    src = items.rows("id = ?", (m.group(1),))
    when = common.now()
    import dates
    shown = dates.show(str((src[0].get("short_header") or src[0].get("title")) if src else "") or "a message")   # a day says Today or a date
    why = f"Your reply to \"{shown}\", kept to send later."
    iid, _ = items.upsert(f"{KEY}reply-{m.group(1)}", "page", kind="approval", area=AREA, state="question", status=None,
                          title=" ".join(str(d.get("subject") or "").split())[:300] or "(no subject)", detail=why, asks=["Send it?"], why=why,
                          draft=_with_base({"account": str(d.get("account") or ""), "to": to, "cc": cc,
                                            "subject": " ".join(str(d.get("subject") or "").split())[:300], "body": str(d.get("body") or ""),
                                            "attach": [], "type": "new", "files": []}),
                          source_who=common.owner(), source_when=when, source_ref="Your own reply, kept",
                          extra={"ready": {"batch": f"reply-{m.group(1)}", "why": why, "about": m.group(1), "own": True}})
    import answers
    item = items.card_for(iid)
    if item:
        answers._patch_snapshot([item])
    return {"ok": True, "items": [item] if item else [], "result": "Kept in Drafts, in Email.", "thought": False}


def send_all(rec):
    """One Send all press: {"send_all": {"batch", "emails": [{"item", "account", "to", "cc", "subject", "body", "attach", "shown"}]}}.
    Each email is sent by send.py's own path as the owner's press, checked against what was on his screen; a card already sent
    or discarded (its draft gone) is not sent again. Returns the act_on_answer result."""
    import replay_guard
    replay_guard.refuse("Send all")
    import answers
    try:
        got = json.loads(rec.get("text") or "")["send_all"]
        emails = [e for e in got.get("emails") or [] if isinstance(e, dict)][:20]
    except (ValueError, KeyError, TypeError, AttributeError):
        return {"ok": False, "error": "That Send all could not be read. Nothing was sent.", "items": []}
    snap = {i.get("id"): i for i in (common.read_json(common.ITEMS_JSON, {}) or {}).get("items") or []}
    sent, said, changed = 0, [], []
    for e in emails:
        iid = str(e.get("item") or "")
        card = snap.get(iid) or {}
        if not str(card.get("source_key") or "").startswith(KEY) or not card.get("draft"):
            said.append(f"{e.get('subject') or 'An email with no subject'}: already sent or marked Done, not sent again")
            continue
        one = {"id": iid, "action": "answer", "device": rec.get("device"), "at": rec.get("at"), "label": "Send all",
               "text": json.dumps({"send_email": {k: e.get(k) for k in ("account", "to", "cc", "subject", "body", "attach", "shown")}})}
        out = answers._owner_send(one)
        changed += out.get("items") or []
        if out.get("sent"):
            sent += 1
        else:
            said.append(f"{e.get('subject') or 'An email with no subject'}: {out.get('result')}")
    result = f"Sent {sent} of {len(emails)}." + (" " + " ".join(said) if said else "")
    return {"ok": True, "items": changed, "result": result, "thought": False, "sent": sent > 0}


def from_file(path):
    """A draft written by a Claude session in the assistant's folder (its CLAUDE.md says how): the JSON file's email goes to
    Ready to send by the same path and checks as the chat's. Returns the plain line to show."""
    try:
        with open(path, encoding="utf-8") as f:
            a = json.load(f)
    except (OSError, ValueError) as e:
        return f"Not put on the page: the file could not be read ({type(e).__name__})."
    if not isinstance(a, dict):
        return "Not put on the page: the file holds no email."
    when = common.now()
    iid, said = make(dict(a, type="draft"), when, 0, f"desktop-{when:%Y%m%d-%H%M%S}")
    if not iid:
        return said or "Not put on the page."
    import answers
    import items
    made = items.card_for(iid)
    if made is not None:
        answers._patch_snapshot([made])
    shown = _refresh_page()             # a desktop session has no page waiting on its answer: the page is told now, like a pass
    return (f"In Drafts, in the Email part of the page ({iid}); nothing is sent until you press Send there."
            + ("" if shown else " The page could not be refreshed just now; it shows the next time I check for messages."))


def _refresh_page():
    """The page refreshed from the items as they stand (live_page/publish.py, as a pass does). True when it was."""
    import subprocess
    if not os.path.exists(common.PUBLISH):
        return False
    try:
        r = subprocess.run([sys.executable, common.PUBLISH], capture_output=True, text=True, timeout=90,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired):
        return False
    if r.returncode:
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"page refresh after a desktop draft failed: {(r.stdout + r.stderr)[-500:]}")
    return r.returncode == 0


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "draft":
        print(from_file(sys.argv[2]))
    else:
        print("python ready.py draft <file.json>")
