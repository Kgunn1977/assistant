r"""The owner's mail on the page: one inbox across every connected address, search, threads with their files, the owner's
presses on an email (archive, delete to the trash, label, read or unread), and the emails the assistant writes for him as
new emails, replies, replies to all and forwards, built whole (the real thread and the original's files) before his Send.

Nothing here sends: send.py sends, on the owner's Send press only, the email this module builds. Every change to his mail
is one press of his on the page; a mail service that cannot make a change says so in plain words, and nothing works around it.

    accounts()                          every connected mail address: {address, send, can: {archive, trash, label, read}}
    rows(view, account, q, before, limit, deep, folder)   the list the Mail part shows (newest first); view "folder" lists one
                                        folder (account and folder id), including mail in Inbox subfolders
    folders(account)                    each mailbox's folder tree or label list with the service's and the stored unread counts
    pull_now()                          asks for an immediate pull of every mailbox (the Refresh press); pull_status() says how it stands
    thread(message_id)                  one conversation, oldest first, with each email's files (stored mail only: the
                                        mail service is not asked, so an email opens at once); html: it has its own HTML kept,
                                        remote: that HTML has pictures from the internet
    body_doc(message_id, pictures=True) the email as it was sent, made safe, a whole document for the page's frame
    labels(address)                     the label names a mailbox has, for the Label box (asked of the service, then kept
                                        for 10 minutes)
    sample(card, message_id)            a junk question card's sender: their recent emails, newest first, and one in full
                                        (stored mail only: nothing is asked of the service, nothing is marked read)
    file(ref, message_id)               (file name, bytes) of one attachment or upload, fetched from the service when not held
    upload(name, data)                  a file the owner added from his computer: {name, ref, size}
    act(rec)                            one press {"mail_act": {"message", "act", "label"}}: the change, made once; or a meeting
                                        invite's answer {"mail_invite": {"message", "answer", "note"}} (invites.py)
    source(message_id)                  what a reply or forward is built from (who, when, the text, the files, its headers)
    draft_for(message_id, kind)         a draft's starting point for that kind (recipients, subject, files), as the page computes it
    build(m, source)                    the complete email (bytes) a Send press would send, and the conversation it belongs to
    sig(draft)                          the draft's signature, so the page can tell an older saved edit from the current draft
"""
import datetime as dt
import email.policy
import email.utils
import hashlib
import html
import json
import mimetypes
import os
import re
import sys
import time
from email.message import EmailMessage

import common

UPLOADS = os.path.join(common.HOME, "mail", "uploads")
MOST_UPLOAD = 15_000_000
SOURCE_TEXT = 20_000            # the original's text a draft carries (and the page folds)
PREFIX = re.compile(r"^\s*((re|fwd?|aw|wg|sv)\s*(\[\d+\])?\s*:\s*)+", re.I)
ADDRESS = re.compile(r"[^@\s<>,;\"']+@[^@\s<>,;\"']+\.[A-Za-z]{2,}")
KINDS = ("new", "reply", "reply_all", "forward")
ACTS = {"archive": "archive", "trash": "trash", "junk": "trash", "restore": "archive", "read": "read", "unread": "read", "label": "label", "unlabel": "label", "move": "label",
        "star": "label", "unstar": "label", "snooze": "read", "unsnooze": "read"}
DONE_WORDS = {"archive": "Archived.", "trash": "Moved to the trash.", "junk": "Moved to junk.", "restore": "Put back in the inbox.", "read": "Marked read.", "unread": "Marked unread.",
              "label": "Labeled \"{label}\".", "unlabel": "Took off the label \"{label}\".", "move": "Moved to \"{label}\".", "star": "Starred.", "unstar": "Star taken off.",
              "snooze": "Snoozed until {label}.", "unsnooze": "Back in the inbox."}
LOCAL_ACTS = ("snooze", "unsnooze")     # kept on this computer only: the mail service is not asked
KIND_VIEWS = {"sent": "sent", "drafts": "drafts", "junk": "spam"}
TKEY = "coalesce(m.thread_id, s.conv, 'm' || cast(m.id AS VARCHAR))"       # one conversation: the service's id, else the threader's


class Busy(Exception):
    """A pass holds the database this moment."""


def _read(tries=6):
    """A read-only connection; tries every half second (about three seconds at most). The page's own doors try once and
    answer busy at once, and the page asks again half a second later."""
    import db
    for i in range(tries):
        con = db.try_connect(read_only=True)
        if con is not None:
            return con
        if i < tries - 1:
            time.sleep(0.5)
    raise Busy()


def _mailcon(fresh=False):
    """The connection the Mail part reads from: the listener's read copy (mail_cache.py) when it is on, else the database."""
    import mail_cache
    return mail_cache.reader(fresh) if mail_cache.ON else _read(1)


def snip(body):
    """The first words of an email, for its row in the list (made from the start of the body only)."""
    import mail_cache
    return " ".join(_clean((body or "")[:mail_cache.SNIP_FROM], 400).split())[:160]


def _clean(text, limit=SOURCE_TEXT):
    import sys
    core = os.path.join(os.path.dirname(os.path.abspath(__file__)), "core")
    if core not in sys.path:
        sys.path.insert(0, core)
    from cleantext import clean_body, dedupe_parts
    return dedupe_parts(clean_body(text or "", limit=limit, keep_links=40))


def _when(ts):
    return f"{ts.month}/{ts.day}/{ts:%y} {ts.strftime('%I:%M %p').lstrip('0')}" if ts else ""


def _addrs(s):
    return [a.lower() for a in ADDRESS.findall(str(s or ""))]


def own_addresses():
    import connections
    return {str(c.get("address") or "").lower() for c in connections.listed("email") if c.get("address")}


def accounts():
    import connections
    import send
    can_send = {a.lower() for a in send.accounts()}
    out = []
    for c in connections.listed("email"):
        a = str(c.get("address") or "").lower()
        if a:
            out.append({"address": a, "send": a in can_send, "can": connections.can(c)})
    import settings_page
    return settings_page.mail_ordered(out, lambda x: x["address"])


RELOADS = ("google_mail", "microsoft_mail")


def reload_history():
    """Settings, Tools: Reload all email history. Each live Gmail and Microsoft mailbox reads its whole history again, a portion
    per pass after the new mail (connections/_store.py). Returns what the page says."""
    import connections
    from connections import _store
    started = [c["address"] for c in connections.listed("email") if c.get("type") in RELOADS and c.get("address")]
    for a in started:
        _store.reload_start(a)
    if not started:
        return "No Gmail or Microsoft mailbox is connected, so there is no history to reload."
    return ("Reloading the whole history of " + ", ".join(started) + ", a portion with every check; the progress shows here and in "
            "each check's summary. Nothing stored is deleted.")


def reload_status():
    """[{account, read, paired, new, done, gone}] of each mailbox's history reload, for the page."""
    import connections
    from connections import _store
    out = []
    for c in connections.listed("email"):
        st = _store.reload_state(c.get("address")) if c.get("type") in RELOADS else None
        if st:
            out.append(dict(account=c["address"], line=_store.reload_line(st), done=bool(st.get("done"))))
    return out


# --- the list, a thread, a file ---------------------------------------------------------------------------------------
SELECT = """SELECT m.id, m.account, m.thread_id, m.ts, m.from_key, m.to_keys, m.subject, m.body, m.direction,
                   s.unread, s.inbox, s.trashed, s.labels, s.cc, s.from_name, s.header_id, s.refs, coalesce(s.provider_id, m.provider_id),     -- the current id
                   (SELECT count(*) FROM attachments a WHERE a.message_id = m.id) AS files, s.starred, s.snooze_until, s.conv
            FROM messages m LEFT JOIN mail_state s ON s.message_id = m.id WHERE m.channel = 'email'"""


LIST_SELECT = SELECT.replace("m.subject, m.body,", "m.subject, NULL,")      # the list carries no bodies: its words come from snip()


def _row(r, text=False, kept=None):
    (mid, account, thread, ts, frm, to, subject, body, direction, unread, inbox, trashed, labels, cc, from_name, header_id,
     refs, pid, files, starred, snooze, conv) = r
    out = {"id": mid, "account": account, "thread": thread, "ts": ts.isoformat(timespec="seconds") if ts else "", "when": _when(ts),
           "from": str(frm or "").split(":", 1)[-1], "from_name": from_name or "", "to": _addrs(to), "cc": _addrs(cc),
           "subject": subject or "", "unread": bool(unread), "inbox": bool(inbox), "trashed": bool(trashed),
           "labels": json.loads(labels) if labels else [], "files": files, "out": direction == "out", "starred": bool(starred),
           "snoozed": snooze.isoformat(timespec="minutes") if snooze and snooze > dt.datetime.now() else ""}
    if text:
        out["text"] = kept if kept is not None else _clean(body, 60_000)
    else:
        out["snippet"] = kept if kept is not None else " ".join(_clean(body, 400).split())[:160]
    out["_pid"], out["_header"], out["_refs"], out["_conv"] = pid, header_id or "", refs or "", conv or ""
    return out


def _public(row):
    return {k: v for k, v in row.items() if not k.startswith("_")}


FILTER = re.compile(r'(?<!\S)(from|to|in|has|before|after):("[^"]*"|\S+)', re.I)


def _date(s):
    try:
        return dt.datetime.combine(dt.date.fromisoformat(s.strip('"').replace("/", "-")), dt.time())
    except ValueError:
        return None


def parse_query(q):
    """(filters [(name, value)], words) from a search: from:, to:, in:, has:attachment, before:, after: and the plain words."""
    q = str(q or "")
    fl = [(n.lower(), v.strip('"').lower()) for n, v in FILTER.findall(q)]
    return fl, FILTER.sub(" ", q).split()[:8]


def rows(view="inbox", account="", q="", before="", limit=50, deep=False, folder="", fresh=False):
    """{ok, accounts, rows, more, next, counts} for the Mail part, one row per conversation (the newest email that fits, with
    its count). view: inbox, unread, starred, snoozed, sent, drafts, junk or all (all leaves out the trash), or folder (one
    folder of one account: pass account and folder; the trash and every subfolder are listed as they are).
    q: words, with from:, to:, in:, has:attachment, before: and after: (a date) among them."""
    limit = max(1, min(int(limit or 50), 100))
    said = ""
    if deep and str(q or "").strip():
        said = _deep(q, account)
    now = dt.datetime.now()
    snoozed = "(s.snooze_until IS NOT NULL AND s.snooze_until > ?)"
    in_kind = ("EXISTS (SELECT 1 FROM mail_folder_members f JOIN mail_folders ff ON ff.account = f.account AND ff.folder_id = f.folder_id"
               " WHERE f.message_id = m.id AND ff.kind = ?")
    import mail_cache
    cached = mail_cache.ON
    con = _mailcon(fresh)
    try:
        where, args = [], []
        if view == "inbox":
            where.append("s.inbox AND NOT " + snoozed); args.append(now)
        elif view == "folder":
            if not (account and folder):
                return {"ok": False, "error": "A folder view needs the mailbox and the folder."}
            where.append("EXISTS (SELECT 1 FROM mail_folder_members f WHERE f.message_id = m.id AND f.folder_id = ?)")
            args.append(str(folder))
        elif view == "unread":
            where.append("s.unread AND NOT coalesce(s.trashed, false) AND NOT " + snoozed); args.append(now)
        elif view == "starred":
            where.append("s.starred AND NOT coalesce(s.trashed, false)")
        elif view == "snoozed":
            where.append(snoozed); args.append(now)
        elif view in KIND_VIEWS:
            where.append("(" + in_kind + ")" + (" OR m.direction = 'out'" if view == "sent" else "") + ")" + (" AND NOT coalesce(s.trashed, false)" if view == "sent" else ""))
            args.append(KIND_VIEWS[view])
        else:
            where.append("NOT coalesce(s.trashed, false)")
        if account:
            where.append("lower(m.account) = ?")
            args.append(str(account).lower())
        fl, words = parse_query(q)
        for name, v in fl:
            like = f"%{v}%"
            if name == "from":
                where.append("(lower(coalesce(m.from_key,'')) LIKE ? OR lower(coalesce(s.from_name,'')) LIKE ?)"); args += [like, like]
            elif name == "to":
                where.append("(lower(coalesce(m.to_keys,'')) LIKE ? OR lower(coalesce(s.cc,'')) LIKE ?)"); args += [like, like]
            elif name == "has":
                if v.startswith("attach"):
                    where.append("EXISTS (SELECT 1 FROM attachments a WHERE a.message_id = m.id)")
            elif name in ("before", "after") and _date(v):
                where.append("m.ts " + ("<" if name == "before" else ">=") + " ?"); args.append(_date(v))
            elif name == "in":
                kind = KIND_VIEWS.get(v, v if v in ("inbox", "trash", "archive") else None)
                if kind:
                    where.append(in_kind + ")"); args.append(kind)
                else:
                    where.append("EXISTS (SELECT 1 FROM mail_folder_members f JOIN mail_folders ff ON ff.account = f.account AND ff.folder_id = f.folder_id"
                                 " WHERE f.message_id = m.id AND lower(ff.path) LIKE ?)"); args.append(like)
        for w in words:
            where.append("(lower(coalesce(m.subject,'')) LIKE ? OR " + ("m.lc" if cached else "lower(coalesce(m.body,''))") + " LIKE ? OR lower(coalesce(m.from_key,'')) LIKE ?"
                         " OR lower(coalesce(m.to_keys,'')) LIKE ? OR lower(coalesce(s.cc,'')) LIKE ? OR lower(coalesce(s.from_name,'')) LIKE ?)")
            args += [f"%{w.lower()}%"] * 6
        qual = "" if view == "drafts" else f" QUALIFY row_number() OVER (PARTITION BY m.account, {TKEY} ORDER BY m.ts DESC) = 1"
        sql = "SELECT * FROM (" + (LIST_SELECT if cached else SELECT) + "".join(" AND " + w for w in where) + qual + ") t"
        if before:
            sql += " WHERE ts < ?"; args.append(dt.datetime.fromisoformat(str(before)))
        got = con.execute(sql + " ORDER BY ts DESC LIMIT ?", args + [limit + 1]).fetchall()
        words_of = mail_cache.kept(con, "snippets", [r[0] for r in got[:limit]], snip) if cached else {}
        out = [_row(r, kept=words_of.get(r[0])) for r in got[:limit]]
        keys = {(r["account"], r["thread"] or r["_conv"]): r for r in out if r["thread"] or r["_conv"]}
        if keys:        # the whole conversation's count and unread, whatever the view
            ks = list({k[1] for k in keys})
            for acct, k, n, u in con.execute(f"SELECT m.account, {TKEY}, count(*), count(*) FILTER (WHERE s.unread) FROM messages m"
                                             " LEFT JOIN mail_state s ON s.message_id = m.id WHERE m.channel = 'email' AND "
                                             f"coalesce(m.thread_id, s.conv) IN ({','.join('?' * len(ks))}) GROUP BY 1, 2", ks).fetchall():
                if (acct, k) in keys:
                    keys[(acct, k)]["count"], keys[(acct, k)]["unread"] = n, u > 0
        counts = {}
        for a, i, u, st, sn in con.execute(
                "SELECT lower(m.account), count(*) FILTER (WHERE s.inbox AND s.unread AND NOT " + snoozed + "), count(*) FILTER (WHERE s.unread AND NOT coalesce(s.trashed, false)"
                " AND NOT " + snoozed + "), count(*) FILTER (WHERE s.starred AND NOT coalesce(s.trashed, false)), count(*) FILTER (WHERE " + snoozed + ")"
                " FROM messages m JOIN mail_state s ON s.message_id = m.id WHERE m.channel = 'email' GROUP BY 1", [now] * 3).fetchall():
            counts[a] = {"inbox": i, "unread": u, "starred": st, "snoozed": sn}
    finally:
        con.close()
    for r in out:
        r.setdefault("count", 1)
    out = [_public(r) for r in out]
    res = {"ok": True, "accounts": accounts(), "rows": out, "more": len(got) > limit, "next": out[-1]["ts"] if out else "", "counts": counts}
    if fresh and cached and mail_cache.stale():
        res["stale"] = True             # the database could not be read just now (a pass holds it): these are the last copy
    if said:
        res["said"] = said
    return res


def folders(account="", fresh=False):
    """{ok, accounts: [{address, folders: [{id, path, parent, kind, unread, total, stored_unread, stored_total}]}]}. unread and
    total are the mail service's own counts (as of the last folder refresh, at most 10 minutes old); stored_* count only the
    email held here. path reads like "Inbox/Suppliers"; kind is inbox, sent, trash, spam, drafts, archive, folder or label."""
    con = _mailcon(fresh)
    try:
        where, args = ("WHERE lower(account) = ?", [str(account).lower()]) if account else ("", [])
        fl = con.execute("SELECT account, folder_id, path, parent_id, kind, unread, total FROM mail_folders " + where + " ORDER BY account, path", args).fetchall()
        got = con.execute("SELECT f.account, f.folder_id, count(*), count(*) FILTER (WHERE s.unread) FROM mail_folder_members f"
                          " LEFT JOIN mail_state s ON s.message_id = f.message_id " + where.replace("account", "f.account") + " GROUP BY 1, 2", args).fetchall()
    finally:
        con.close()
    stored = {(a, f): (n, u) for a, f, n, u in got}
    out = {}
    for a, fid, path, parent, kind, unread, total in fl:
        n, u = stored.get((a, fid), (0, 0))
        out.setdefault(a, []).append({"id": fid, "path": path, "parent": parent, "kind": kind, "unread": unread, "total": total,
                                      "stored_unread": u, "stored_total": n})
    import settings_page
    return {"ok": True, "accounts": settings_page.mail_ordered([{"address": a, "folders": v} for a, v in out.items()], lambda x: x["address"])}


PULL_STATE = os.path.join(common.HOME, "state", "mail_pull.json")


def pull_status():
    return common.read_json(PULL_STATE, {}) or {}


def pull_now():
    """The Refresh press: every mailbox is read now (new mail first, then the changes made elsewhere) in its own hidden run, which
    waits its turn behind a pass. Returns plain words."""
    import replay_guard
    if replay_guard.import_blocked():
        return "Not pulled: your history is being rebuilt day by day, and new mail comes in when that is done."
    import onboard
    if onboard.holding():
        return "Not pulled yet: new mail comes in once your history catalog is built (the setup card shows how long is left)."
    import answers
    st = pull_status()
    if st.get("running") and time.time() - st.get("t", 0) < 20 * 60:
        return "Your mail is already being pulled."
    common.write_json(PULL_STATE, {"running": common.now().isoformat(timespec="seconds"), "t": time.time(), "done_at": st.get("done_at")})
    if not answers.start_hidden([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "mailpull.py")]):
        common.write_json(PULL_STATE, {"running": None, "done_at": st.get("done_at")})
        return "Not started: your mail could not be pulled from here. I'll read it the next time I check for messages, within a few minutes."
    return "Pulling your mail now."


def _deep(q, account=""):
    """Ask each mail service's own search; store the matches not held yet. Returns a plain line when a service could not be asked."""
    import connections
    bad = []
    for c in connections.listed("email"):
        if account and str(c.get("address") or "").lower() != str(account).lower():
            continue
        mod = connections.module(c["type"])
        if not hasattr(mod, "search") or not hasattr(mod, "fetch"):
            bad.append(f"{c.get('address')} cannot be searched from here")
            continue
        try:
            ids = mod.search(c, q, 25)
            con = _read()
            try:
                held = {r[0] for r in con.execute("SELECT provider_id FROM messages WHERE channel='email' AND lower(account)=?"
                                                  " UNION SELECT provider_id FROM mail_state WHERE lower(account)=? AND provider_id IS NOT NULL",
                                                  [str(c.get("address")).lower(), str(c.get("address")).lower()]).fetchall()}
            finally:
                con.close()
            new = [i for i in ids if i not in held]
            if new:
                mod.fetch(c, new)
        except Exception as e:  # noqa: BLE001  one mailbox failing never stops the others; it is named
            bad.append(f"{c.get('address')} could not be searched ({type(e).__name__})")
    return ("Not searched: " + "; ".join(bad) + ".") if bad else ""


def thread(message_id, fresh=False):
    """{ok, messages} for one conversation: every stored email of the same account and conversation, oldest first.
    Stored mail only: nothing is asked of the mail service (the label names come from labels(), when the Label box opens)."""
    import mail_cache
    cached = mail_cache.ON
    con = _mailcon(fresh)
    try:
        one = con.execute(SELECT + " AND m.id = ?", [int(message_id)]).fetchone()
        if not one:
            return {"ok": False, "error": "That email is not here any more."}
        first = _row(one)
        if first["thread"] or first["_conv"]:
            got = con.execute(SELECT + " AND m.account = ? AND coalesce(m.thread_id, s.conv) = ? ORDER BY m.ts",
                              [first["account"], first["thread"] or first["_conv"]]).fetchall()
        else:
            got = [one]
        last = got[-40:]
        texts = mail_cache.kept(con, "texts", [r[0] for r in last], lambda b: _clean(b, 60_000)) if cached else {}
        msgs = [_public(_row(r, text=True, kept=texts.get(r[0]))) for r in last]
        import mailhtml
        for m in msgs:
            m["files"] = [{"name": n or s, "ref": f"att:{a}", "size": _size(p)} for a, n, s, p in con.execute(
                "SELECT id, original_filename, saved_filename, saved_path FROM attachments WHERE message_id = ? ORDER BY id", [m["id"]]).fetchall()]
            if cached:      # whether its HTML has pictures from the internet is worked out once and kept
                got = con.execute("SELECT length(html) > 0, remote FROM mail_html WHERE message_id = ?", [m["id"]]).fetchone()
                m["html"] = bool(got and got[0])
                if got and got[0] and got[1] is None:
                    remote = bool(mailhtml.sanitize(con.execute("SELECT html FROM mail_html WHERE message_id = ?", [m["id"]]).fetchone()[0], m["id"])[1])
                    mail_cache.keep_remote(m["id"], remote)
                    got = (got[0], remote)
                m["remote"] = bool(got and got[0] and got[1])
                continue
            got = con.execute("SELECT html FROM mail_html WHERE message_id = ?", [m["id"]]).fetchone()
            m["html"] = bool(got and got[0])
            m["remote"] = bool(got and got[0] and mailhtml.sanitize(got[0], m["id"])[1])
    finally:
        con.close()
    res = {"ok": True, "messages": msgs}
    if fresh and cached and mail_cache.stale():
        res["stale"] = True
    return res


def body_doc(message_id, pictures=True):
    """(the email as sent, made safe: a whole document for the page's frame, whether it has pictures from the internet), or
    None when the email has no HTML kept. pictures: show pictures from the internet."""
    import mailhtml
    con = _mailcon()
    try:
        got = con.execute("SELECT html, cids FROM mail_html WHERE message_id = ?", [int(message_id)]).fetchone()
    finally:
        con.close()
    if not got or not got[0]:
        return None
    return mailhtml.sanitize(got[0], int(message_id), json.loads(got[1] or "{}"), pictures)


SAMPLES = 20


def sample_pattern(card):
    """(the sender pattern a one-sender Junk or never junk card asks about, the words to show), or (None, None)."""
    import presses
    con = _read(1)
    try:
        got = con.execute("SELECT source_key FROM live_items WHERE id = ?", [str(card)]).fetchone()
    finally:
        con.close()
    rid = presses.junk_ask_rule({"source_key": got[0]}) if got and presses.is_junk_ask({"source_key": got[0]}) else None
    if rid is None:
        return None, None
    e = next((x for x in presses._rules().parse("senders") if x["id"] == rid and x.get("pattern")), None)
    if not e:
        return None, None
    return e["pattern"], e["pattern"].split(":", 1)[-1].replace("\\", "")


def sample(card, message_id=None):
    """{ok, sender, list: [{id, when, subject}] newest first, message: one in full} for a junk question card's sender.
    Read from the stored mail only, so nothing is marked read and nothing is asked of the mail service."""
    pattern, words = sample_pattern(card)
    if not pattern:
        return {"ok": False, "error": "This card does not name one sender."}
    con = _read(1)
    try:
        got = con.execute(SELECT + " AND m.direction = 'in' AND m.from_key ILIKE ? ESCAPE '\\' ORDER BY m.ts DESC LIMIT ?",
                          [pattern, SAMPLES]).fetchall()
        rows_ = [_row(r, text=True) for r in got]
        pick = next((r for r in rows_ if message_id is not None and r["id"] == int(message_id)), rows_[0] if rows_ else None)
        if pick is not None:
            pick["files"] = [{"name": n or s, "ref": f"att:{a}", "size": _size(p)} for a, n, s, p in con.execute(
                "SELECT id, original_filename, saved_filename, saved_path FROM attachments WHERE message_id = ? ORDER BY id",
                [pick["id"]]).fetchall()]
            import mailhtml          # the same two flags the email view carries, so an HTML-only email shows formatted
            got = con.execute("SELECT html FROM mail_html WHERE message_id = ?", [pick["id"]]).fetchone()
            pick["html"] = bool(got and got[0])
            pick["remote"] = bool(got and got[0] and mailhtml.sanitize(got[0], pick["id"])[1])
    finally:
        con.close()
    if pick is None:
        return {"ok": True, "sender": words, "list": [], "message": None}
    return {"ok": True, "sender": words, "list": [{"id": r["id"], "when": r["when"], "subject": r["subject"]} for r in rows_],
            "message": _public(pick)}


def _size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return None


LABELS_KEPT = 600               # seconds the label names of a mailbox are kept before the service is asked again
_LABELS = {}                    # address -> (when asked, names)


def labels(address):
    """{ok, address, labels} for the Label box: the mailbox's label names, asked of the mail service at most once in
    10 minutes. A list that cannot be had is empty: a name can still be typed."""
    import connections
    key = str(address or "").strip().lower()
    conn, mod = connections.mailbox(key)
    if conn is None:
        return {"ok": False, "error": "That mailbox is not connected."}
    got = _LABELS.get(key)
    if got and time.time() - got[0] < LABELS_KEPT:
        return {"ok": True, "address": key, "labels": got[1]}
    names = []
    if hasattr(mod, "labels"):
        try:
            names = list(mod.labels(conn))[:200]
        except Exception:  # noqa: BLE001  the list of label names only helps typing; a name can still be typed
            return {"ok": True, "address": key, "labels": got[1] if got else []}
    _LABELS[key] = (time.time(), names)
    return {"ok": True, "address": key, "labels": names}


def file(ref, message_id=None):
    """(file name, bytes) for one attachment ref; raises LookupError with plain words when it cannot be had."""
    ref = str(ref or "")
    if ref.startswith("up:"):
        hexed = ref[3:]
        if not re.fullmatch(r"[0-9a-f]{24}", hexed):
            raise LookupError("That file is not one you added.")
        folder = os.path.join(UPLOADS, hexed)
        names = os.listdir(folder) if os.path.isdir(folder) else []
        if not names:
            raise LookupError("The file you added is not on this computer any more. Add it again.")
        with open(os.path.join(folder, names[0]), "rb") as f:
            return names[0], f.read()
    m = re.fullmatch(r"att:(\d+)", ref) or re.fullmatch(r"msg:(\d+):(.+)", ref)
    if not m:
        raise LookupError("That attachment is not known.")
    con = _read()
    try:
        if ref.startswith("att:"):
            row = con.execute("SELECT a.original_filename, a.saved_filename, a.saved_path, m.account, coalesce(s.provider_id, m.provider_id) FROM attachments a"
                              " JOIN messages m ON m.id = a.message_id LEFT JOIN mail_state s ON s.message_id = m.id WHERE a.id = ?",
                              [int(m.group(1))]).fetchone()
        else:
            row = con.execute("SELECT a.original_filename, a.saved_filename, a.saved_path, m.account, coalesce(s.provider_id, m.provider_id) FROM messages m"
                              " LEFT JOIN mail_state s ON s.message_id = m.id"
                              " LEFT JOIN attachments a ON a.message_id = m.id AND a.original_filename = ? WHERE m.id = ?",
                              [m.group(2), int(m.group(1))]).fetchone()
            if row and row[0] is None:
                row = (m.group(2), None, None, row[3], row[4])
    finally:
        con.close()
    if not row:
        raise LookupError("That attachment is not known.")
    name, saved, path, account, pid = row
    name = name or saved
    if path and os.path.isfile(path):
        with open(path, "rb") as f:
            return name, f.read()
    import connections
    conn, mod = connections.mailbox(account)
    if conn is None or not hasattr(mod, "attachment"):
        raise LookupError(f"\"{name}\" is not on this computer and {account} cannot hand it over.")
    try:
        data = mod.attachment(conn, pid, name)
    except Exception as e:  # noqa: BLE001
        raise LookupError(f"\"{name}\" could not be fetched from {account} ({type(e).__name__}).") from None
    if data is None:
        raise LookupError(f"\"{name}\" is no longer on that email at {account}.")
    return name, data


def upload(name, data):
    """Keep a file the owner added on the page. Returns {name, ref, size} or raises ValueError with plain words."""
    name = os.path.basename(str(name or "").replace("\\", "/")).strip()
    name = "".join(c for c in name if c.isalnum() or c in "._- ()[]&,'+")[:150].strip(" .") or "file"
    if not data:
        raise ValueError("That file is empty.")
    if len(data) > MOST_UPLOAD:
        raise ValueError(f"That file is larger than {MOST_UPLOAD // 1_000_000} MB.")
    hexed = hashlib.sha256(data + name.encode("utf-8")).hexdigest()[:24]
    folder = os.path.join(UPLOADS, hexed)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "wb") as f:
        f.write(data)
    return {"name": name, "ref": f"up:{hexed}", "size": len(data)}


# --- the owner's presses on an email ------------------------------------------------------------------------------------
def act(rec):
    """One press {"mail_act": {"message", "act", "label"}}. Returns the act_on_answer result."""
    catch_up()
    try:
        pressed = json.loads(rec.get("text") or "")
    except ValueError:
        pressed = {}
    if isinstance(pressed, dict) and "mail_invite" in pressed:       # Accept / Maybe / Decline on a meeting invite (invites.py)
        import invites
        return invites.respond(rec, pressed["mail_invite"])
    try:
        got = json.loads(rec.get("text") or "")["mail_act"]
        mid, what, label = int(got["message"]), str(got["act"]), str(got.get("label") or "").strip()[:100]
        folder = str(got.get("folder") or "").strip()[:300]
        until = dt.datetime.fromisoformat(str(got["until"])) if what == "snooze" else None
    except (ValueError, KeyError, TypeError):
        return {"ok": False, "error": "That press could not be read. Nothing was changed.", "items": []}
    if what not in ACTS or (what == "restore" and label not in ("archive", "trash", "junk")) or (what in ("label", "unlabel") and not label) or (what == "move" and not folder) or (what == "snooze" and until <= dt.datetime.now()):
        return {"ok": False, "error": "That press could not be read. Nothing was changed.", "items": []}
    mids = [mid]
    if got.get("all"):          # a row of several emails: the change reaches the ones it applies to
        mids = _conversation(mid, what)
    out = [_act_one(rec, i, what, label, folder, until) for i in mids]
    bad = [o for o in out if str(o.get("result", "")).startswith("Not done")]
    res = bad[0] if bad else out[-1]
    if len(out) > 1 and not bad:
        res = dict(res, result=res["result"] + f" ({len(out)} emails)")
    return res


def _conversation(mid, what):
    """The stored emails of one conversation a change applies to, the one pressed first (at most 40)."""
    if what in ("unread", "star", "unstar"):
        return [mid]
    con = _read()
    try:
        one = con.execute(SELECT + " AND m.id = ?", [mid]).fetchone()
        if not one:
            return [mid]
        r = _row(one)
        key = r["thread"] or r["_conv"]
        if not key:
            return [mid]
        more = {"read": " AND s.unread", "archive": " AND s.inbox"}.get(what, "")
        ids = [x[0] for x in con.execute(f"SELECT m.id FROM messages m LEFT JOIN mail_state s ON s.message_id = m.id WHERE m.channel = 'email' AND m.account = ?"
                                         f" AND coalesce(m.thread_id, s.conv) = ?{more} ORDER BY m.ts DESC LIMIT 40", [r["account"], key]).fetchall()]
    finally:
        con.close()
    return [mid] + [i for i in ids if i != mid]


def _act_one(rec, mid, what, label, folder, until=None):
    con = _read()
    try:
        row = con.execute(SELECT + " AND m.id = ?", [mid]).fetchone()
    finally:
        con.close()
    if not row:
        return {"ok": True, "items": [], "result": "Not done: that email is not here any more."}
    r = _row(row)
    if what in LOCAL_ACTS:      # kept here only: nothing is asked of the mail service
        import db
        from connections import _store
        w = db.connect()
        try:
            _store.put_state(w, r["id"], r["account"], r["_pid"], {})
            w.execute("UPDATE mail_state SET snooze_until = ? WHERE message_id = ?", [until, r["id"]])
        finally:
            w.close()
        return {"ok": True, "items": [], "result": DONE_WORDS[what].format(label=_when(until) if until else "")}
    if what == "move":          # the destination must be one of this mailbox's own folders
        con = _read()
        try:
            dest = con.execute("SELECT path, kind FROM mail_folders WHERE account = ? AND folder_id = ?", [r["account"], folder]).fetchone()
        finally:
            con.close()
        if not dest:
            return {"ok": True, "items": [], "result": f"Not done: {r['account']} has no such folder."}
        label = dest[0]
    import replay_guard
    replay_guard.refuse("changing an email at the mail service")
    import connections
    conn, mod = connections.mailbox(r["account"])
    if conn is None:
        return {"ok": True, "items": [], "result": f"Not done: {r['account']} is not connected."}
    if not connections.can(conn).get(ACTS[what]) or not hasattr(mod, "act"):
        return {"ok": True, "items": [], "result": not_allowed(r["account"], what)}
    try:
        new_pid = mod.act(conn, r["_pid"], what, label=(folder if what == "move" else label) or None, thread_id=r["thread"])
    except Exception as e:  # noqa: BLE001
        if type(e).__name__ == "NotAllowed":
            return {"ok": True, "items": [], "result": not_allowed(r["account"], what)}
        return {"ok": True, "items": [], "result": f"Not done: {r['account']} refused it ({type(e).__name__}). Nothing was changed."}
    late = ""
    try:
        _after(r, what, label, new_pid, folder)
    except TimeoutError:        # the mail service has changed it; only my own copy waits for the store to free
        _park(r, what, label, new_pid, folder)
        late = " My own copy is busy for a moment; it will show the change when it frees."
    common.log_line(os.path.join(common.LOGS, "mail.log"), f"{rec.get('id')} {what} {mid} {r['account']}" + (f" label {label}" if label else ""))
    return {"ok": True, "items": [], "result": DONE_WORDS[what].format(label=label) + late}


def _parked_path():
    import paths
    return os.path.join(paths.STATE, "mail_catchup.json")


def _park(r, what, label, new_pid, folder):
    """Keeps a change the service already made, for my own copy to take when the store frees (catch_up)."""
    keep = {k: r.get(k) for k in ("id", "account", "_pid", "thread", "labels")}
    path = _parked_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
    except (OSError, ValueError):
        items = []
    items.append({"r": keep, "what": what, "label": label, "new_pid": new_pid, "folder": folder})
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f)


def catch_up():
    """Applies the parked changes to my own copy, in order. Runs at the start of each press and of each pass, so it adds no
    program of its own. Any that find the store busy stay for the next time. Returns how many it applied."""
    path = _parked_path()
    try:
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
    except (OSError, ValueError):
        return 0
    left, n = [], 0
    for it in items:
        if left:                # keep the order: nothing goes ahead of one still waiting
            left.append(it)
            continue
        try:
            _after(it["r"], it["what"], it["label"], it["new_pid"], it["folder"])
            n += 1
        except TimeoutError:
            left.append(it)
    if left:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(left, f)
    elif os.path.isfile(path):
        os.remove(path)
    return n


def _is_gmail(account):
    import connections
    conn, _mod = connections.mailbox(account)
    return bool(conn) and conn.get("type") == "google_mail"


def not_allowed(address, what):
    return (f"Not done: the sign-in for {address} does not allow changing mail yet, so it was not "
            f"{'archived' if what == 'archive' else 'moved to the trash' if what == 'trash' else 'moved to junk' if what == 'junk' else 'put back' if what == 'restore' else 'labeled' if what in ('label', 'unlabel') else 'marked'}. "
            "To allow it, open the assistant's Setup, pick that mailbox and press Sign in again.")


def _after(r, what, label, new_pid, folder=""):
    """Keep the stored email's state as the service now has it."""
    import db
    from connections import _store
    con = db.connect()
    try:
        if new_pid and new_pid != r["_pid"]:      # the current id follows the service; the stored row keeps its own
            con.execute("UPDATE mail_state SET provider_id = ? WHERE message_id = ?", [new_pid, r["id"]])
        if what == "archive":
            ids = [x[0] for x in con.execute("SELECT id FROM messages WHERE channel='email' AND account=? AND thread_id=?",
                                             [r["account"], r["thread"]]).fetchall()] if r["thread"] else [r["id"]]
            for i in ids:
                _store.put_state(con, i, r["account"], None, {"inbox": False})
        elif what == "move":
            kind = (_store.folder_of(con, r["account"], folder) or {}).get("kind")
            have = [f for f in _store.members(con, r["id"]) if f != "INBOX"] if _is_gmail(r["account"]) else []
            _store.put_state(con, r["id"], r["account"], new_pid, {"inbox": kind == "inbox", "trashed": kind == "trash"}, have + [folder])
        elif what == "trash":
            _store.put_state(con, r["id"], r["account"], new_pid, {"trashed": True, "inbox": False})
        elif what in ("junk", "restore"):     # to the spam folder, or back in the inbox (undo): its stored folders follow
            kinds = {f: (_store.folder_of(con, r["account"], f) or {}).get("kind") for f in _store.members(con, r["id"])}
            want = (con.execute("SELECT folder_id FROM mail_folders WHERE account = ? AND kind = ?", [r["account"], "spam" if what == "junk" else "inbox"]).fetchone() or [None])[0]
            keep = [f for f, k in kinds.items() if k not in ("inbox", "trash", "spam", "archive")] if _is_gmail(r["account"]) else []
            _store.put_state(con, r["id"], r["account"], new_pid, {"inbox": what == "restore", "trashed": False}, keep + ([want] if want else []))
            if what == "restore" and r["thread"]:
                for i in [x[0] for x in con.execute("SELECT id FROM messages WHERE channel='email' AND account=? AND thread_id=?", [r["account"], r["thread"]]).fetchall()]:
                    if label == "archive" and i != r["id"]:
                        _store.put_state(con, i, r["account"], None, {"inbox": True})
        elif what in ("read", "unread"):
            _store.put_state(con, r["id"], r["account"], new_pid, {"unread": what == "unread"})
        elif what in ("star", "unstar"):
            _store.put_state(con, r["id"], r["account"], new_pid, {"starred": what == "star"})
        else:
            have = [x for x in r["labels"] if x.lower() != label.lower()]
            _store.put_state(con, r["id"], r["account"], new_pid, {"labels": have + ([label] if what == "label" else [])})
    finally:
        con.close()


# --- conversations the service gave no id for, and snoozed email coming back (both run in the pass, after the new mail) -----------
def rethread():
    """Give each stored email the service gave no conversation id a conversation from its References / Message-ID headers
    (JWZ threading, vendor/jwzthreading.py), kept in mail_state.conv. A conversation holding an email that has a service id
    takes that id, so both sides open as one. One read, then one short write. Returns how many emails were linked."""
    import db
    vend = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
    if vend not in sys.path:
        sys.path.append(vend)
    catch_up()
    import jwzthreading as jwz
    got = db.query("SELECT m.id, m.account, m.thread_id, s.conv, s.header_id, s.refs, m.subject FROM messages m JOIN mail_state s ON s.message_id = m.id"
                   " WHERE m.channel = 'email' AND coalesce(s.header_id, '') <> '' AND m.account IN (SELECT m2.account FROM messages m2"
                   " LEFT JOIN mail_state s2 ON s2.message_id = m2.id WHERE m2.channel = 'email' AND m2.thread_id IS NULL AND s2.conv IS NULL)")
    by = {}
    for r in got:
        by.setdefault(r[1], []).append(r)
    sets = []
    for acct, rs in by.items():
        msgs, seen = [], set()
        for mid, _a, tid, conv, hid, refs, subj in rs:
            m = jwz.Message((mid, tid, conv))
            m.message_id = hid.strip().strip("<>")
            if not m.message_id or m.message_id in seen:
                continue
            seen.add(m.message_id)
            m.references = jwz.uniq(jwz.msgid_pat.findall(refs or ""))
            m.subject = subj or ""
            msgs.append(m)

        def members(c):
            return ([c.message] if c.message else []) + [x for k in c.children for x in members(k)]
        for top in jwz.thread(msgs).values():
            ms = members(top)
            if len(ms) < 2:
                continue
            key = next((m.message[1] for m in ms if m.message[1]), None) or "jwz:" + min(m.message_id for m in ms)
            sets += [(key, m.message[0]) for m in ms if not m.message[1] and m.message[2] != key]
    if sets:
        with db.transaction() as con:
            for key, mid in sets:
                con.execute("UPDATE mail_state SET conv = ? WHERE message_id = ?", [key, mid])
    return len(sets)


def wake(limit=20):
    """Snoozed email whose time has come returns to the inbox as unread (its snooze is cleared; the mail service is told it is
    unread, as far as it answers). Returns how many came back."""
    import replay_guard
    replay_guard.refuse("snoozed email coming back (marked unread at the mail service)")
    import connections
    import db
    now = dt.datetime.now()
    got = db.query("SELECT message_id, account, provider_id FROM mail_state WHERE snooze_until IS NOT NULL AND snooze_until <= ?", (now,))
    if not got:
        return 0
    db.execute("UPDATE mail_state SET snooze_until = NULL, unread = true WHERE snooze_until IS NOT NULL AND snooze_until <= ?", (now,))
    for _mid, acct, pid in got[:limit]:
        conn, mod = connections.mailbox(acct)
        try:
            if conn is not None and pid and hasattr(mod, "act") and connections.can(conn).get("read"):
                mod.act(conn, pid, "unread")
        except Exception:  # noqa: BLE001  it is unread here; the service is told at the next change
            pass
    return len(got)


# --- what a reply or forward is built from -------------------------------------------------------------------------------
def source(message_id):
    """The original a reply or forward is made from: who, when, the text, its files and the headers that keep a reply in its
    conversation. None when there is no such email."""
    con = _read()
    try:
        one = con.execute(SELECT + " AND m.id = ?", [int(message_id)]).fetchone()
        if not one:
            return None
        r = _row(one, text=True)
        files = [{"name": n or s, "ref": f"att:{a}", "size": _size(p)} for a, n, s, p in con.execute(
            "SELECT id, original_filename, saved_filename, saved_path FROM attachments WHERE message_id = ? ORDER BY id", [r["id"]]).fetchall()]
    finally:
        con.close()
    header, refs, thread_id = r["_header"], r["_refs"], r["thread"]
    if not header:              # an email stored before the headers were kept: asked of the service once, kept from then on
        import connections
        conn, mod = connections.mailbox(r["account"])
        if conn is not None and hasattr(mod, "headers"):
            try:
                hd = mod.headers(conn, r["_pid"])
                header, refs = hd.get("header_id") or "", hd.get("refs") or ""
                r["cc"] = r["cc"] or _addrs(hd.get("cc"))
                r["from_name"] = r["from_name"] or hd.get("from_name") or ""
                import db
                from connections import _store
                w = db.try_connect()
                if w is not None:
                    try:
                        _store.put_state(w, r["id"], r["account"], r["_pid"], {k: hd.get(k) for k in ("header_id", "refs", "cc", "from_name") if hd.get(k)})
                    finally:
                        w.close()
            except Exception:  # noqa: BLE001  the reply still goes; it may show apart from its conversation in some mail programs
                pass
    return {"message": r["id"], "account": r["account"], "from": r["from"], "from_name": r["from_name"], "to": r["to"], "cc": r["cc"],
            "ts": r["ts"], "when": r["when"], "subject": r["subject"], "text": r["text"][:SOURCE_TEXT], "files": files,
            "thread": thread_id, "header_id": header, "refs": refs}


def base_subject(subject):
    return PREFIX.sub("", str(subject or "")).strip()


def draft_for(src, kind, accounts_=None):
    """{account, to, cc, bcc, subject, type, files} for a draft of this kind made from src (a source(); None for a new email).
    The same rules the page uses when the owner switches the type."""
    own = own_addresses() | {a.lower() for a in (accounts_ or [])}
    import send
    sendable = send.accounts()
    if not src or kind == "new":
        return {"account": (src or {}).get("account") if (src or {}).get("account") in sendable else (sendable[0] if len(sendable) == 1 else ""),
                "to": [], "cc": [], "bcc": [], "subject": base_subject((src or {}).get("subject")), "type": "new", "files": []}
    base = base_subject(src["subject"])
    acct = src["account"] if src["account"] in sendable else (sendable[0] if len(sendable) == 1 else "")
    sender = [src["from"]] if src["from"] and src["from"].lower() not in own else [x for x in src["to"] if x.lower() not in own][:1]
    if kind == "reply":
        return {"account": acct, "to": sender, "cc": [], "bcc": [], "subject": "Re: " + base, "type": "reply", "files": list(src["files"])}
    if kind == "reply_all":
        to = list(dict.fromkeys(sender + [x for x in src["to"] if x.lower() not in own]))
        cc = [x for x in src["cc"] if x.lower() not in own and x not in to]
        return {"account": acct, "to": to, "cc": cc, "bcc": [], "subject": "Re: " + base, "type": "reply_all", "files": list(src["files"])}
    return {"account": acct, "to": [], "cc": [], "bcc": [], "subject": "Fwd: " + base, "type": "forward", "files": list(src["files"])}


def sig(d):
    """The draft's signature: it changes whenever the engine writes the draft anew."""
    return hashlib.sha256(json.dumps([d.get(k) for k in ("account", "to", "cc", "bcc", "subject", "body", "type")] +
                                     [[f.get("ref") for f in d.get("files") or []], (d.get("source") or {}).get("message")],
                                     ensure_ascii=False, default=str).encode("utf-8")).hexdigest()[:16]


# --- building the email a Send press sends ------------------------------------------------------------------------------
def _quote_html(text):
    return html.escape(text or "").replace("\r\n", "\n").replace("\n", "<br>\n")


def build(m, src, files):
    """The complete email: m = {account, to, cc, bcc, subject, body, type}; src = source() or None; files = [(name, bytes)].
    Returns (bytes, conversation id or None). A reply keeps its conversation (In-Reply-To, References) and quotes the
    original under "On <date>, <who> wrote:"; a forward carries the "Forwarded message" block and the original text."""
    import send
    kind = m.get("type") if m.get("type") in KINDS else "new"
    msg = EmailMessage(policy=email.policy.SMTP)
    msg["From"] = m["account"]
    msg["To"] = ", ".join(m["to"])
    if m.get("cc"):
        msg["Cc"] = ", ".join(m["cc"])
    if m.get("bcc"):
        msg["Bcc"] = ", ".join(m["bcc"])
    msg["Subject"] = m["subject"]
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=str(m["account"]).split("@")[-1] or None)
    body = send._as_html(m["body"])
    plain = m["body"]
    thread = None
    if src and kind in ("reply", "reply_all"):
        who = f"{src['from_name']} <{src['from']}>" if src.get("from_name") else src["from"]
        body += f'<br>\n<div>On {html.escape(src["when"])}, {html.escape(who)} wrote:</div>\n<blockquote style="margin:0 0 0 .8ex;border-left:1px solid #ccc;padding-left:1ex">' \
                + _quote_html(src["text"]) + "</blockquote>"
        plain += f"\n\nOn {src['when']}, {who} wrote:\n" + "\n".join("> " + ln for ln in (src["text"] or "").split("\n"))
        if src.get("header_id"):
            msg["In-Reply-To"] = src["header_id"]
            msg["References"] = " ".join(x for x in (src.get("refs") or "", src["header_id"]) if x).strip()
        thread = src.get("thread")
    elif src and kind == "forward":
        head = [("From", f"{src['from_name']} <{src['from']}>" if src.get("from_name") else src["from"]), ("Date", src["when"]),
                ("Subject", src["subject"]), ("To", ", ".join(src["to"]))] + ([("Cc", ", ".join(src["cc"]))] if src.get("cc") else [])
        body += "<br>\n<div>---------- Forwarded message ---------<br>\n" + "".join(f"{k}: {html.escape(v)}<br>\n" for k, v in head) + "</div><br>\n" + _quote_html(src["text"])
        plain += "\n\n---------- Forwarded message ---------\n" + "".join(f"{k}: {v}\n" for k, v in head) + "\n" + (src["text"] or "")
    msg.set_content(plain)
    msg.add_alternative(body, subtype="html")
    for name, data in files:
        major, _, minor = (mimetypes.guess_type(name)[0] or "application/octet-stream").partition("/")
        msg.add_attachment(data, maintype=major, subtype=minor, filename=name)
    return msg.as_bytes(), thread
