r"""Handling mail: Unsubscribe on the Mail page, and the assistant's bulk handling from its chat (archive, delete to the trash,
junk, move, unsubscribe, make a mail rule). Archive, delete, junk and Undo for one email or several are mail.py's presses.

Nothing here deletes for good: Delete is the account's trash, Junk its spam or junk folder, both with Undo.

UNSUBSCRIBE. An email's List-Unsubscribe header (asked of the mail service once, kept in mail_unsub) says how:
    one-click   an https address and List-Unsubscribe-Post "List-Unsubscribe=One-Click": a press on the page posts to it (RFC 8058)
    https       only an address: the page opens it for the owner, who finishes it there
    mailto      an email to write: sent only on the owner's own press, only when sending is on for that account
    parse_unsub(list_header, post_header)   {has, one_click, https, mailto: {to, subject, body}}
    info(message_id)                        the same for one stored email, with whether it was done
    unsubscribe(rec)                        one press {"mail_unsub": {"message", "via": "auto" | "mailto"}}

THE CHAT. The assistant's reply carries ACTION lines (chat.py). A plan is made first and shown, then done only on the owner's yes:
    {"type": "mail_plan", "op": "archive|trash|junk|move|unsubscribe|rule", "find": {...}, ...}   finds the mail and says what it
        would do (the count and a sample); nothing is changed. The program writes that line, not the model.
    {"type": "mail_go"}   does the newest plan not done yet, only when the plan was made in an EARLIER message, is under 30 minutes
        old, is not done yet, and the owner's own message now is a plain yes. A rule is made the same way (op "rule").
    find(spec)    the stored emails a find matches {count, ids, sample}: from, subject, older_than_days, newer_than_days,
                  unread, newest (only the newest this many), account, folder (inbox, all, junk, archive, trash; default inbox)
    A plan that finds exactly one email (any op but unsubscribe and rule) is done at once, as that email's own button does it,
    with no yes asked: one email is never a bulk change. done_now[0] says so to the chat for that call.
    Organizing (move between folders, mark read or unread, archive, label, star) is done at once, however many emails, when the
    owner's own words in that message plainly ask for it: he gave the box full access to organize his mail (spec 1.2).
"""
import datetime as dt
import email.message
import ipaddress
import json
import os
import re
import secrets
import socket
import threading
import time
import urllib.parse
import urllib.request

import common

HERE = os.path.dirname(os.path.abspath(__file__))
PLANS = os.path.join(common.paths.STATE, "mail_plans.json")
MOST = 200                      # emails one plan covers
MOST_SENDERS = 25               # senders one unsubscribe plan looks at
PLAN_MINUTES = 30
SAMPLE = 5
ORGANIZE = ("move", "read", "unread", "archive", "label", "unlabel", "star", "unstar")     # done at once on his plain words
HEDGE = re.compile(r"\b(don'?t|do not|never|not yet|hold off|should i|should we|would you|whether|what if|how many|which)\b|\?\s*$", re.I)
OPS = ("archive", "trash", "junk", "move", "unsubscribe", "rule", "read", "unread", "star", "unstar", "label", "unlabel")
OP_WORDS = {"archive": "archive", "trash": "move to the trash (nothing is deleted for good)", "junk": "move to junk", "move": "move",
            "read": "mark read", "unread": "mark unread", "star": "star (flag)", "unstar": "take the star (flag) off", "label": "label", "unlabel": "take a label off"}
DONE_OP = {"archive": "Archived", "trash": "Moved to the trash", "junk": "Moved to junk", "move": "Moved", "read": "Marked read", "unread": "Marked unread",
           "star": "Starred", "unstar": "Took the star off", "label": "Labeled", "unlabel": "Took the label off"}
URLS = re.compile(r"<\s*([^<>\s]+)\s*>")
YES = re.compile(r"^\W*(yes|yep|yeah|yup|y|ok|okay|sure|go ahead|do it|go for it|please do|confirmed?|approved?|proceed|sounds good|that'?s fine|that is fine)\b", re.I)
BUT = re.compile(r"\b(but|except|not|don'?t|do not|only|instead|change|wait|stop|no)\b", re.I)


# --- the List-Unsubscribe header ---------------------------------------------------------------------------------------
def parse_unsub(value, post=""):
    """What an email's List-Unsubscribe (and List-Unsubscribe-Post) headers allow. Only https addresses count (never http);
    one_click needs both an https address and the post header naming One-Click."""
    urls = URLS.findall(str(value or ""))
    https = next((u for u in urls if u.lower().startswith("https://")), "")
    mail = next((u for u in urls if u.lower().startswith("mailto:")), "")
    mailto = None
    if mail:
        parts = urllib.parse.urlsplit(mail)
        q = urllib.parse.parse_qs(parts.query)
        to = urllib.parse.unquote(parts.path).strip()
        if re.fullmatch(r"[^@\s,;<>]+@[^@\s,;<>]+", to):
            mailto = {"to": to, "subject": (q.get("subject") or ["unsubscribe"])[0][:200], "body": (q.get("body") or [""])[0][:1000]}
    one = bool(https) and "list-unsubscribe=one-click" in str(post or "").lower().replace(" ", "")
    return {"has": bool(https or mailto), "one_click": one, "https": https, "mailto": mailto}


def _table(w):
    w.execute("CREATE TABLE IF NOT EXISTS mail_unsub (message_id BIGINT PRIMARY KEY, account VARCHAR, list_value VARCHAR, post_value VARCHAR,"
               " checked_at TIMESTAMP, done_at TIMESTAMP, how VARCHAR)")


def _stored(mid):
    import mail
    con = mail._read(1)
    try:
        try:
            got = con.execute("SELECT list_value, post_value, done_at, how FROM mail_unsub WHERE message_id = ?", [mid]).fetchone()
        except Exception:  # noqa: BLE001  the table is made on the first lookup
            return None
        return got
    finally:
        con.close()


def _email(mid):
    import mail
    con = mail._read(1)
    try:
        one = con.execute(mail.SELECT + " AND m.id = ?", [int(mid)]).fetchone()
    finally:
        con.close()
    return mail._row(one) if one else None


def info(message_id, ask=True):
    """{ok, has, one_click, https, mailto, done, how, from} for one stored email. The mail service is asked once (its headers)
    and the answer kept; ask=False reads only what is kept."""
    r = _email(message_id)
    if r is None:
        return {"ok": False, "error": "That email is not here any more."}
    got = _stored(r["id"])
    if got is None:
        if not ask:
            return {"ok": True, "known": False, "has": False, "one_click": False, "https": "", "mailto": None, "done": False}
        import connections
        conn, mod = connections.mailbox(r["account"])
        if conn is None or not hasattr(mod, "unsub_headers"):
            return {"ok": False, "error": f"{r['account']} is not connected."}
        try:
            hd = mod.unsub_headers(conn, r["_pid"])
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"Could not ask {r['account']} just now ({type(e).__name__})."}
        got = (hd.get("list") or "", hd.get("post") or "", None, None)
        import db
        w = db.try_connect()
        if w is not None:
            try:
                _table(w)
                w.execute("INSERT OR REPLACE INTO mail_unsub VALUES (?,?,?,?,?,NULL,NULL)", [r["id"], r["account"], got[0], got[1], dt.datetime.now()])
            except Exception:  # noqa: BLE001  not kept this time; asked again next time
                pass
            finally:
                w.close()
    out = parse_unsub(got[0], got[1])
    out.update({"ok": True, "known": True, "done": bool(got[2]), "how": got[3] or "", "from": r["from"]})
    return out


# --- the page's lookups: answered at once from what is held; a mail service is asked in the background, never in the request ---
_asking = {}                    # message id -> when a background ask began (one at a time for each email)
_failed = {}                    # message id -> when its last ask failed (not asked again for a minute)
_asks = threading.BoundedSemaphore(3)
ASK_AGAIN = 60


def _basic(mid):
    """(account, the service's id, the sender's address, where it is held) for one email, from the read copy when it is on."""
    import mail
    import mail_cache
    if mail_cache.ON:
        con = mail._mailcon()
        try:
            got = con.execute("SELECT m.account, coalesce(s.provider_id, m.provider_id), m.from_key FROM messages m"
                              " LEFT JOIN mail_state s ON s.message_id = m.id WHERE m.id = ?", [int(mid)]).fetchone()
        finally:
            con.close()
        return (got[0], got[1], str(got[2] or "").split(":", 1)[-1].lower()) if got else None
    r = _email(mid)
    return (r["account"], r["_pid"], r["from"].lower()) if r else None


def _ask(mid, account, pid, sender):
    """In a thread of its own: ask the mail service for the email's headers, keep the answer here and in the database."""
    try:
        with _asks:
            import connections
            import mail_cache
            conn, mod = connections.mailbox(account)
            if conn is None or not hasattr(mod, "unsub_headers"):
                _failed[mid] = time.time()
                return
            hd = mod.unsub_headers(conn, pid)
            mail_cache.unsub_put(mid, account, sender, hd.get("list") or "", hd.get("post") or "")
    except Exception:  # noqa: BLE001  asked again after a minute
        _failed[mid] = time.time()
    finally:
        _asking.pop(mid, None)


def lookup(message_id, fresh=False):
    """info() for the page's door: never waits for the mail service. Answers from what is held (the email's own answer, or its
    sender's from the last weeks); otherwise {ok, pending: True} and the service is asked in the background, and the page asks again."""
    import mail
    import mail_cache
    if not mail_cache.ON:
        return info(message_id)
    mid = int(message_id)
    basic = _basic(mid)
    if basic is None:
        return {"ok": False, "error": "That email is not here any more."}
    account, pid, sender = basic
    con = mail_cache.reader(fresh) if fresh else mail._mailcon()
    try:
        got = mail_cache.unsub_known(con, mid, account, sender)
    finally:
        con.close()
    if got is None:
        if mid in _failed and time.time() - _failed[mid] < ASK_AGAIN:
            return {"ok": False, "error": f"Could not ask {account} just now."}
        if mid not in _asking:
            _asking[mid] = time.time()
            threading.Thread(target=_ask, args=(mid, account, pid, sender), name="mail-unsub-ask", daemon=True).start()
        return {"ok": True, "pending": True}
    out = parse_unsub(got[0], got[1])
    out.update({"ok": True, "known": True, "done": bool(got[2]), "how": got[3] or "", "from": sender})
    return out


def lookups(ids, fresh=False):
    out = {}
    for i in list(ids)[:MOST_SENDERS]:
        out[str(i)] = lookup(i, fresh)
    return {"ok": True, "info": out}


def infos(ids):
    """info() for several emails, as the page's selection asks (at most MOST_SENDERS of them)."""
    out = {}
    for i in list(ids)[:MOST_SENDERS]:
        out[str(i)] = info(i)
    return {"ok": True, "info": out}


def _mark(mid, how):
    import db
    w = db.try_connect()
    if w is not None:
        try:
            w.execute("UPDATE mail_unsub SET done_at = ?, how = ? WHERE message_id = ?", [dt.datetime.now(), how, mid])
        finally:
            w.close()


def _public_host(url):
    """Never post to this computer or its own network: an email's address can point anywhere."""
    host = urllib.parse.urlsplit(url).hostname or ""
    if not host or host.lower() == "localhost":
        return False
    try:
        for fam, _t, _p, _c, sa in socket.getaddrinfo(host, 443):
            ip = ipaddress.ip_address(sa[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
    except (OSError, ValueError):
        return False
    return True


def _post(url):
    """RFC 8058's one-click: a POST with List-Unsubscribe=One-Click. Returns the HTTP status."""
    req = urllib.request.Request(url, data=b"List-Unsubscribe=One-Click", method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "assistant-unsubscribe"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.status


def _no(text):
    return {"ok": True, "items": [], "result": "Not done: " + text}


def unsubscribe(rec):
    """One press {"mail_unsub": {"message", "via"}}. via "auto": the one-click post. via "mailto": the email the sender asked for,
    sent now because the owner pressed it (sending must be on for that account). Returns the act_on_answer result."""
    try:
        got = json.loads(rec.get("text") or "")["mail_unsub"]
        mid, via = int(got["message"]), str(got.get("via") or "auto")
    except (ValueError, KeyError, TypeError):
        return {"ok": False, "error": "That press could not be read. Nothing was changed.", "items": []}
    if via not in ("auto", "mailto"):
        return {"ok": False, "error": "That press could not be read. Nothing was changed.", "items": []}
    r = info(mid)
    if not r.get("ok"):
        return _no(r.get("error") or "that email could not be read.")
    if not r["has"]:
        return _no("that email has no unsubscribe link.")
    who = (r.get("from") or "").split("@")[-1] or "the sender"
    if via == "auto":
        if not r["one_click"]:
            return _no("that sender needs you to finish it on their page, or by email.")
        if not _public_host(r["https"]):
            return _no("that sender's address is not a public one, so it was not used.")
        try:
            status = _post(r["https"])
        except Exception as e:  # noqa: BLE001
            return _no(f"{who} did not accept it ({type(e).__name__}). Nothing was changed.")
        if not 200 <= status < 300:
            return _no(f"{who} answered {status}. Nothing was changed.")
        _mark(mid, "one-click")
        common.log_line(os.path.join(common.LOGS, "mail.log"), f"{rec.get('id')} unsubscribe one-click {mid}")
        return {"ok": True, "items": [], "result": f"Unsubscribed from {who}. It can take a few days to stop."}
    if not r["mailto"]:
        return _no("that sender gives no address to write to.")
    import connections
    import send
    e = _email(mid)
    acct = e["account"]
    if not send.switched_on() or acct.lower() not in [a.lower() for a in send.accounts()]:
        return _no(f"sending is not on for {acct}, so the unsubscribe email was not sent.")
    conn, mod = connections.mailbox(acct)
    if conn is None or not hasattr(mod, "send_mime"):
        return _no(f"{acct} is not connected.")
    m = email.message.EmailMessage()
    m["From"], m["To"], m["Subject"] = acct, r["mailto"]["to"], r["mailto"]["subject"]
    m.set_content(r["mailto"]["body"] or "unsubscribe")
    try:
        mod.send_mime(conn, bytes(m))
    except Exception as ex:  # noqa: BLE001
        return _no(f"{acct} refused it ({type(ex).__name__}). Nothing was sent.")
    _mark(mid, "mailto")
    common.log_line(os.path.join(common.LOGS, "mail.log"), f"{rec.get('id')} unsubscribe mailto {mid}")
    return {"ok": True, "items": [], "result": f"Sent the unsubscribe email for {who}."}


# --- finding mail --------------------------------------------------------------------------------------------------------
def find(spec, limit=MOST):
    """The stored emails (never ones the owner wrote) a find matches, newest first: {count, ids, rows}. spec: from, subject,
    older_than_days, newer_than_days, unread, newest (only the newest this many: "my newest email" is newest 1), account,
    folder (inbox | all | sent | junk | archive | trash; inbox when not given, inbox and sent mail when an account is given).
    Needs at least one of from, subject, older_than_days, newer_than_days, unread or newest, so no find means the whole mailbox."""
    import mail
    spec = spec if isinstance(spec, dict) else {}
    where, args = [], []
    frm, subj = str(spec.get("from") or "").strip().lower()[:200], str(spec.get("subject") or "").strip().lower()[:200]
    try:
        older = float(spec.get("older_than_days")) if spec.get("older_than_days") not in (None, "") else None
        newer = float(spec.get("newer_than_days")) if spec.get("newer_than_days") not in (None, "") else None
    except (TypeError, ValueError):
        return {"ok": False, "error": "I could not read the age in that."}
    unread = spec.get("unread") in (True, "true", "yes")
    try:
        newest = max(1, min(int(spec.get("newest")), limit)) if spec.get("newest") not in (None, "", False, 0, "0") else None
    except (TypeError, ValueError):
        return {"ok": False, "error": "I could not read how many of the newest emails that means."}
    if not (frm or subj or older is not None or newer is not None or unread or newest):
        return {"ok": False, "error": "I need a sender, words from the subject, an age, unread or the newest to pick mail by; I will not act on a whole mailbox."}
    said = str(spec.get("folder") or "").strip().lower()
    folder = said or "inbox"
    kinds = {"junk": "spam", "spam": "spam", "archive": "archive", "trash": "trash", "inbox": "inbox"}
    # the mail he wrote sits in the account's Sent mail: a find for one account (with no folder named) and "all" cover it too, "sent" is only it
    with_sent = folder in ("all", "sent") or (not said and bool(spec.get("account")))
    if folder == "sent":
        where.append("m.direction = 'out'")
    elif folder == "inbox":
        where.append("(s.inbox OR m.direction = 'out')" if with_sent else "s.inbox")
    elif folder in kinds:
        where.append("EXISTS (SELECT 1 FROM mail_folder_members f JOIN mail_folders ff ON ff.account = f.account AND ff.folder_id = f.folder_id"
                     " WHERE f.message_id = m.id AND ff.kind = ?)")
        args.append(kinds[folder])
    if not with_sent:
        where.append("m.direction <> 'out'")
    if folder != "trash":
        where.append("NOT coalesce(s.trashed, false)")
    if frm:
        where.append("(lower(coalesce(m.from_key,'')) LIKE ? OR lower(coalesce(s.from_name,'')) LIKE ?)")
        args += [f"%{frm}%"] * 2
    if subj:
        where.append("lower(coalesce(m.subject,'')) LIKE ?")
        args.append(f"%{subj}%")
    now = dt.datetime.now()
    if older is not None:
        where.append("m.ts < ?")
        args.append(now - dt.timedelta(days=older))
    if newer is not None:
        where.append("m.ts >= ?")
        args.append(now - dt.timedelta(days=newer))
    if unread:
        where.append("s.unread")
    if spec.get("account"):
        where.append("lower(m.account) = ?")
        args.append(str(spec["account"]).strip().lower())
    w = " AND ".join(where)
    con = mail._read()
    try:
        count = con.execute("SELECT count(*) FROM messages m LEFT JOIN mail_state s ON s.message_id = m.id WHERE m.channel = 'email' AND " + w, args).fetchone()[0]
        got = con.execute(mail.SELECT + " AND " + w + " ORDER BY m.ts DESC, m.id DESC LIMIT ?", args + [newest or limit]).fetchall()
    finally:
        con.close()
    if newest:
        count = min(count, newest)
    rows = [mail._public(mail._row(r)) for r in got]
    return {"ok": True, "count": count, "ids": [r["id"] for r in rows], "rows": rows}


def _sample(rows):
    out = []
    for r in rows[:SAMPLE]:
        who = r["from_name"] or r["from"]
        out.append(f"{r['when']}, {who}: \"{r['subject'][:70]}\"")
    return "; ".join(out)


def _said_find(spec):
    bits = []
    if spec.get("from"):
        bits.append(f"from {spec['from']}")
    if spec.get("subject"):
        bits.append(f"with \"{spec['subject']}\" in the subject")
    if spec.get("older_than_days") not in (None, ""):
        bits.append(f"older than {spec['older_than_days']} days")
    if spec.get("newer_than_days") not in (None, ""):
        bits.append(f"from the last {spec['newer_than_days']} days")
    if spec.get("unread") in (True, "true", "yes"):
        bits.append("unread")
    if spec.get("newest") not in (None, "", False, 0, "0"):
        bits.insert(0, "the newest" + (f" {spec['newest']}" if str(spec["newest"]) != "1" else ""))
    where = str(spec.get("folder") or "inbox")
    return " ".join(bits) + f" in {where}" + (f" ({spec['account']})" if spec.get("account") else "")


# --- plans: found and shown first, done only on the owner's yes ------------------------------------------------------------
def _plans():
    d = common.read_json(PLANS, {}) or {}
    cut = (dt.datetime.now() - dt.timedelta(days=1)).isoformat(timespec="seconds")
    return {k: v for k, v in d.items() if str(v.get("created") or "") >= cut}


def _keep(plan):
    d = _plans()
    d[plan["id"]] = plan
    for k in sorted(d, key=lambda x: d[x]["created"])[:-20]:
        d.pop(k)
    common.write_json(PLANS, d)


def _folder_target(account, wanted):
    """(folder id, its path) of one of this mailbox's own folders by path (a trailing part is enough), or (None, None)."""
    import mail_rules
    want = str(wanted or "").strip().lower().strip("/")
    rows = [f for f in mail_rules._folders(account) if f.get("kind") in ("inbox", "archive", "folder", "label")] if want else []
    for f in rows:
        if str(f["id"]) == str(wanted) or f["path"].lower() == want:
            return str(f["id"]), f["path"]
    hits = [f for f in rows if f["path"].lower().endswith("/" + want)]
    return (str(hits[0]["id"]), hits[0]["path"]) if len(hits) == 1 else (None, None)


done_now = [False]      # the last plan() was done at once (one email): the chat then says only the program's line


def _plainly(text):
    """True when the owner's own words in this message plainly ask for something to be done (not a question, not put off)."""
    t = " ".join(str(text or "").split())
    return bool(t) and not HEDGE.search(t)


def plan(action, when, text=""):
    """A mail_plan ACTION: finds the mail, keeps the plan, and returns the line that shows it (count and a sample) and asks for
    the yes; nothing is changed. A plan that finds exactly one email is done at once instead, and so is organizing asked for
    in his own plain words (see the top)."""
    done_now[0] = False
    op = str(action.get("op") or "")
    if op not in OPS:
        return "I could not tell what to do with that mail, so I left it alone."
    base = {"id": "mp-" + secrets.token_hex(3), "created": dt.datetime.now().isoformat(timespec="seconds"),
            "when": when.isoformat(timespec="seconds"), "op": op, "used": False}
    if op == "rule":
        return _plan_rule(action, base)
    spec = action.get("find") or {}
    try:
        got = find(spec)
    except Exception as e:  # noqa: BLE001
        return f"I could not look through your mail just now ({type(e).__name__}); ask again in a minute."
    if not got.get("ok"):
        return got["error"]
    if not got["count"]:
        return "I found no mail like that, so there is nothing to do."
    base.update({"spec": spec, "ids": got["ids"], "count": got["count"]})
    what = _said_find(spec)
    more = f" (this is the first {len(got['ids'])} of {got['count']}; ask again for the rest)" if got["count"] > len(got["ids"]) else ""
    if op == "unsubscribe":
        return _plan_unsub(base, got["rows"], what)
    if op == "move":
        accts = {r["account"] for r in got["rows"]}
        if len(accts) != 1:
            return f"That matches mail in {len(accts)} mailboxes; folders belong to one mailbox, so tell me which address to move from."
        acct = accts.pop()
        fid, path = _folder_target(acct, action.get("folder"))
        if not fid:
            return f"{acct} has no folder I can tell apart called \"{action.get('folder')}\"; tell me its full name."
        base.update({"folder": fid, "folder_path": path, "account": acct})
        words = f"move to \"{path}\""
    elif op in ("label", "unlabel"):
        name = " ".join(str(action.get("label") or "").split())[:100]
        if not name:
            return "Tell me the label's name, so I left that mail alone."
        base["label"] = name
        words = f"{OP_WORDS[op]} \"{name}\" on" if op == "label" else f"take the label \"{name}\" off"
    else:
        words = OP_WORDS[op]
    if op in ORGANIZE and len(got["ids"]) > 1 and _plainly(text):      # organizing on his own words: done at once
        base["used"] = True
        _keep(base)
        done_now[0] = True
        return _go_acts(base) + (f" There are {got['count'] - len(got['ids'])} more {what}; ask again for the rest." if more else "")
    if got["count"] == 1 and len(got["ids"]) == 1:      # one email: done at once, as its own button does it
        base["used"] = True
        _keep(base)
        line = _go_acts(base)
        if line.startswith(f"{DONE_OP[op]} 1 of 1"):
            done_now[0] = True
            return f"{DONE_OP[op]}: {_sample(got['rows'])}." + line[len(f"{DONE_OP[op]} 1 of 1 email."):]
        return line
    _keep(base)
    return (f"I would {words} {len(got['ids'])} email{'s' if len(got['ids']) != 1 else ''} {what}{more}. For example: {_sample(got['rows'])}. "
            "Nothing is changed yet: tell me yes to do it, or what to change.")


def _plan_unsub(base, rows, what):
    seen, targets = set(), []
    for r in rows:                      # newest email of each sender
        key = (r["account"], r["from"].lower())
        if key in seen or len(seen) >= MOST_SENDERS:
            continue
        seen.add(key)
        i = info(r["id"])
        kind = "none" if not i.get("ok") or not i["has"] else "done" if i["done"] else "one_click" if i["one_click"] else "link" if i["https"] else "mail"
        targets.append({"message": r["id"], "sender": r["from"], "kind": kind})
    n = {k: sum(1 for t in targets if t["kind"] == k) for k in ("one_click", "link", "mail", "none", "done")}
    base.update({"targets": targets, "ids": [], "count": len(targets)})
    _keep(base)
    left = []
    if n["link"] or n["mail"]:
        left.append(f"{n['link'] + n['mail']} only give a web page or an email address to use, so those are for you to press in the Email part")
    if n["none"]:
        left.append(f"{n['none']} give no unsubscribe link")
    if n["done"]:
        left.append(f"{n['done']} you already unsubscribed from")
    if not n["one_click"]:
        return f"Of {len(targets)} senders {what}, none can be unsubscribed from here" + (": " + "; ".join(left) if left else "") + "."
    return (f"I would unsubscribe you from {n['one_click']} sender{'s' if n['one_click'] != 1 else ''} {what} by their one-click link, for example "
            + ", ".join(t["sender"] for t in targets if t["kind"] == "one_click")[:200] + (f". Of the others, {'; '.join(left)}" if left else "")
            + ". Nothing is changed yet: tell me yes to do it.")


def _plan_rule(action, base):
    import mail_rules
    addr = str(action.get("account") or "").strip().lower()
    got = {"op": "create", "account": addr, "when": action.get("when") or {}, "do": str(action.get("do") or ""), "folder": ""}
    if got["do"] == "move":
        fid, _path = _folder_target(addr, action.get("folder"))
        if not fid:
            return f"{addr} has no folder I can tell apart called \"{action.get('folder')}\"; tell me its full name."
        got["folder"] = fid
    out = mail_rules.act({"text": json.dumps({"mail_rule": got})}, dry=True)
    if str(out.get("result") or "").startswith("Not done"):
        return out["result"]
    base.update({"rule": got, "account": addr})
    _keep(base)
    return (f"I would make this mail rule at {addr}, so it runs on all future mail there: {out['result']} It does not touch mail already there. "
            "Nothing is made yet: tell me yes to make it.")


def go(action, when, text):
    """A mail_go ACTION: does a kept plan, only on the owner's yes (see the top). Returns the line for the reply."""
    live = [v for v in _plans().values() if not v["used"]]
    p = max(live, key=lambda v: v["created"]) if live else None
    if p is None:
        return "I could not find that plan any more (they last 30 minutes), so nothing was done. Ask me again."
    if p["used"]:
        return "That was already done."
    if p["when"] == when.isoformat(timespec="seconds"):
        return "I will not do it in the same message that planned it; tell me yes after you have seen it."
    if dt.datetime.now() - dt.datetime.fromisoformat(p["created"]) > dt.timedelta(minutes=PLAN_MINUTES):
        return "That plan is more than 30 minutes old, so nothing was done. Ask me again."
    if not YES.search(text or "") or BUT.search(text or ""):
        return "I did not take that as a plain yes, so nothing was done. Say yes to go ahead, or tell me what to change."
    p["used"] = True                    # once, whatever happens next
    _keep(p)
    if p["op"] == "rule":
        import mail_rules
        return mail_rules.act({"id": "chat:" + p["id"], "text": json.dumps({"mail_rule": p["rule"]})}).get("result") or ""
    if p["op"] == "unsubscribe":
        return _go_unsub(p)
    if p["op"] == "folder_delete":
        return _folder_delete_now(p["account"], p["folder"], p["path"])
    return _go_acts(p)


def _go_acts(p):
    import mail
    op = p["op"]
    done, why = 0, ""
    for i in p["ids"]:
        a = {"message": i, "act": op if op != "move" else "move"}
        if op == "move":
            a["folder"] = p["folder"]
        if op in ("label", "unlabel"):
            a["label"] = p.get("label") or ""
        try:
            out = mail.act({"id": "chat:" + p["id"], "text": json.dumps({"mail_act": a})})
        except mail.Busy:
            out = {"result": "Not done: your mail is being updated this moment."}
        said = str(out.get("result") or out.get("error") or "")
        if said.startswith("Not done") or not out.get("ok", True):
            why = said
            if "does not allow" in said or "being updated" in said:
                break
            continue
        done += 1
    n = len(p["ids"])
    line = f"{DONE_OP[op]} {done} of {n} email{'s' if n != 1 else ''}." + (" You can take them out again from your mail service or the Email part." if done and op in ("trash", "junk") else "")
    return line + (f" {why}" if why else "")


def _go_unsub(p):
    done, left = 0, []
    for t in p["targets"]:
        if t["kind"] != "one_click":
            continue
        out = unsubscribe({"id": "chat:" + p["id"], "text": json.dumps({"mail_unsub": {"message": t["message"], "via": "auto"}})})
        if str(out.get("result") or "").startswith("Not done"):
            left.append(t["sender"])
        else:
            done += 1
    return (f"Unsubscribed from {done} sender{'s' if done != 1 else ''}. It can take a few days to stop."
            + (f" {len(left)} did not accept it: {', '.join(left)[:200]}." if left else ""))


# --- folders and labels themselves: made, renamed, moved and deleted on the owner's words ------------------------------------
FOLDER_DOS = ("create", "rename", "move", "delete")
FOLDER_WORDS = {"create": r"\b(make|create|add|new|set up|start)\b", "rename": r"\b(rename|call|name)\b",
                "move": r"\b(move|put|nest|under|inside|into)\b", "delete": r"\b(delete|remove|get rid of|drop)\b"}
FOLDER_NOT = r"\b(don'?t|do not|never|not yet|should i|should we|whether)\b"
OWN_KINDS = ("folder", "label")         # the mailbox's own folders (inbox, sent, trash, spam, drafts, archive) are never changed


def _mail_folder(account, wanted):
    """(the stored folder row, '') for one of this mailbox's own folders or labels by path (a trailing part is enough), or
    (None, the plain reason)."""
    import mail_rules
    want = str(wanted or "").strip().strip("/").lower()
    rows = list(mail_rules._folders(account)) if want else []
    hit = [f for f in rows if str(f["id"]) == str(wanted) or f["path"].lower() == want] or \
          [f for f in rows if f["path"].lower().endswith("/" + want)]
    if len(hit) != 1:
        return None, (f"{account} has no folder or label I can tell apart called \"{wanted}\"; tell me its full name." if not hit else
                      f"More than one folder in {account} ends in \"{wanted}\": " + ", ".join(f["path"] for f in hit[:5]) + ". Which one?")
    if hit[0].get("kind") not in OWN_KINDS:
        return None, f"\"{hit[0]['path']}\" is one of the mailbox's own folders, so I left it as it is."
    return hit[0], ""


def folder(action, when, text):
    """{"type": "mail_folder", "do": "create | rename | move | delete", "account", "folder": its path (not for create), "name": the
    new name (create, rename), "parent": the folder it goes under (create, move; empty for the top)}. Done by the mailbox's own
    connection on the owner's words of this message. A folder that holds mail or other folders is deleted only after he has seen
    what is in it and says yes in a later message (mail_go); an empty one goes at once."""
    import connections
    a = action or {}
    do, account = str(a.get("do") or ""), str(a.get("account") or "").strip().lower()
    if do not in FOLDER_DOS:
        return "I could not tell what to do with that folder, so nothing was changed."
    why = common.rulebook().said_refusal(text, want=FOLDER_WORDS[do], not_words=FOLDER_NOT)
    if why:
        return "Nothing was changed in your mail folders: " + why.replace("the owner's", "your") + "."
    conn, mod = connections.mailbox(account)
    if conn is None:
        return f"{account or 'That address'} is not one of your connected mailboxes; tell me which address."
    if not hasattr(mod, "folder_create"):
        return f"{account}'s connection cannot change folders yet, so nothing was changed."
    parent = None
    if str(a.get("parent") or "").strip() and do in ("create", "move"):
        parent, why = _mail_folder(account, a.get("parent"))
        if parent is None:
            return why
    name = " ".join(str(a.get("name") or "").replace("/", " ").split())[:100]
    under = f"\"{parent['path']}\"" if parent else "the top level"
    try:
        if do == "create":
            if not name:
                return "Tell me the new folder's name, so nothing was made."
            mod.folder_create(conn, name, parent["id"] if parent else None)
            said = f"Made the folder \"{name}\" under {under} in {account}."
        else:
            f, why = _mail_folder(account, a.get("folder"))
            if f is None:
                return why
            if do == "rename":
                if not name:
                    return "Tell me the new name, so nothing was changed."
                mod.folder_rename(conn, f["id"], name)
                said = f"Renamed \"{f['path']}\" to \"{name}\" in {account}."
            elif do == "move":
                if parent and (parent["id"] == f["id"] or parent["path"].lower().startswith(f["path"].lower() + "/")):
                    return "A folder cannot go inside itself, so nothing was changed."
                mod.folder_move(conn, f["id"], parent["id"] if parent else None)
                said = f"Moved \"{f['path']}\" to {under} in {account}."
            else:
                info = mod.folder_info(conn, f["id"])
                if not info.get("total") and not info.get("children"):
                    return _folder_delete_now(account, f["id"], f["path"])
                p = {"id": "mp-" + secrets.token_hex(3), "created": dt.datetime.now().isoformat(timespec="seconds"),
                     "when": when.isoformat(timespec="seconds"), "op": "folder_delete", "used": False, "ids": [],
                     "account": account, "folder": f["id"], "path": f["path"]}
                _keep(p)
                held = [f"{info['total']} email{'s' if info['total'] != 1 else ''}" if info.get("total") else "",
                        f"{info['children']} folder{'s' if info['children'] != 1 else ''} inside it" if info.get("children") else ""]
                return (f"\"{f['path']}\" in {account} holds " + " and ".join(x for x in held if x) + ". " + mod.FOLDER_DELETE_SAYS
                        + " Nothing is changed yet: tell me yes to delete it.")
    except Exception as e:  # noqa: BLE001
        return f"{account} did not take that change ({type(e).__name__}), so nothing was changed."
    _refresh_folders(conn, mod)
    return said


def _folder_delete_now(account, folder_id, path):
    import connections
    conn, mod = connections.mailbox(account)
    if conn is None:
        return f"{account} is not connected any more, so nothing was deleted."
    try:
        mod.folder_delete(conn, folder_id)
    except Exception as e:  # noqa: BLE001
        return f"{account} did not delete \"{path}\" ({type(e).__name__}), so nothing was changed."
    _refresh_folders(conn, mod)
    return f"Deleted the folder \"{path}\" in {account}. " + mod.FOLDER_DELETE_SAYS


def _refresh_folders(conn, mod):
    """The Email part's folder list read again now, so the change shows there at once (the next check would do it too)."""
    try:
        mod.folder_refresh(conn)
    except Exception:  # noqa: BLE001
        pass


def chat_action(action, when, text):
    """The ACTION types of the chat for mail. Returns the line to add to the reply."""
    kind = str((action or {}).get("type") or "")
    if kind == "mail_plan":
        return plan(action, when, text)
    if kind == "mail_go":
        return go(action, when, text)
    if kind == "mail_folder":
        return folder(action, when, text)
    return ""
