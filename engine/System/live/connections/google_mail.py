r"""Gmail and Google Workspace mail, read through the Gmail API."""
import base64
import datetime as dt
import email.errors
import email.header
import email.utils
import mimetypes
import os
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage

from connections import _http, _oauth, _store
import connections

TYPE = "google_mail"
NAME = "Gmail or Google Workspace mail"
KIND = "email"
CAN_SEND = True
CAN_ACT = ("archive", "trash", "label", "read")     # needs the "change mail" permission below
ACT_SCOPE = ("https://www.googleapis.com/auth/gmail.modify", "https://mail.google.com/")
APP = "google"              # every Google account of one owner signs in through the same registration
APP_ASKS = [
    {"key": "client_id", "label": "Client ID", "help": "Ends in .apps.googleusercontent.com (step 9)."},
    {"key": "client_secret", "label": "Client secret", "secret": True,
     "help": "Shown beside the Client ID in step 9. It is typed into a hidden box and kept locked on this computer."},
]
ASKS = []

SETUP = """\
WHAT THIS CONNECTS
A Gmail mailbox, or a work or church mailbox that runs on Google (Google Workspace). I
read new mail and its attachments. I can also send an email you write and send
yourself from your page, and archive, delete (to the trash), label or mark read an email when
you press that on your page.

WHAT YOU NEED
- A Google account you can sign in to in a browser.
- About 15 minutes, once. Every Google mailbox or calendar you add after the first skips
  straight to step 10.

ONE TIME: REGISTER YOUR OWN CONNECTION WITH GOOGLE
Google only hands mail to a program that is registered with it. You register your own; it is
free, and nobody else can use it.
1. Open https://console.cloud.google.com and sign in. If asked, agree to the terms.
2. At the very top click the project box (it may say "Select a project"), then "New project".
   Name it "My assistant" and click "Create". Wait a few seconds, then pick it in the same box.
3. In the search bar at the top type "Gmail API", click the result, click "Enable".
   Do the same for "Google Calendar API" (you will want it for your calendar) and for
   "People API" (so your assistant can read your Google contacts into Contacts).
4. In the search bar type "OAuth consent screen" and open it. Click "Get started".
   App name: "My assistant". User support email: pick your address. Click "Next".
   Audience: choose "External". Click "Next". Contact email: your address. Agree and "Create".
   (If every account you will connect is in one Google Workspace organization and you see the
   choice "Internal", you may pick it instead; then skip steps 5 and 6.)
5. In the left menu click "Audience". Under "Test users" click "Add users" and add every
   Google address you plan to connect (yours, and any work one). Click "Save".
6. Still on "Audience", click "Publish app" and confirm. This matters: an app left in
   "Testing" makes Google end your sign-in every 7 days.
7. In the left menu click "Clients", then "Create client". Application type: "Desktop app".
   Name: "My assistant". Click "Create".
8. A box appears with "Client ID" and "Client secret".
9. Copy the Client ID into the "Client ID" box in the setup window. Copy the Client secret into
   the "Client secret" box (it shows dots; that is on purpose). Then click "OK" in Google's box.

EACH MAILBOX
10. In the setup window press "Sign in". Your browser opens Google's own sign-in page.
11. Pick the account. Google warns "Google hasn't verified this app": that is expected, because
    the app is your own. Click "Advanced", then "Go to My assistant (unsafe)".
12. Tick every box Google lists (read, compose, send, change your mail, and see your contacts) and click "Continue".
    Your password goes only to Google; I never see it.
13. The browser says "Signed in." Close that tab. The setup window shows the mailbox as connected.

IF SOMETHING GOES WRONG
- "Access blocked: My assistant has not completed the Google verification process": the address
  is not in the test users (step 5), or the app is not published (step 6).
- A work account says "Access blocked: admin policy": your organization limits outside apps.
  Its Google administrator must allow your Client ID (Admin console, Security, API controls).
- The page shows a health line "sign this account in again": open Setup, pick the mailbox,
  press "Sign in" again.
- Archive, Delete, Label or Mark read on your page says the sign-in "does not allow changing
  mail yet": the mailbox was signed in before I could change mail. Open Setup,
  pick the mailbox, press "Sign in" again and tick every box.
"""

AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
API = "https://gmail.googleapis.com/gmail/v1/users/me"
SCOPES = ["https://www.googleapis.com/auth/gmail.modify", "https://www.googleapis.com/auth/gmail.send",
          "https://www.googleapis.com/auth/gmail.settings.basic",
          "https://www.googleapis.com/auth/contacts.readonly"]   # modify: read, label, archive, trash; never delete for good; settings.basic: the filters (mail_rules.py)


def app_ready():
    return connections.app(APP).get("client_id"), connections.secret("app_" + APP, "secret")


def token_for(conn):
    client_id, secret = app_ready()
    if not client_id or not secret:
        raise _oauth.SignInFailed("the Google registration is missing; open Setup and add it")
    return _oauth.access(conn, TOKEN, client_id, secret)


def sign_in(conn, scopes, say):
    client_id, secret = app_ready()
    answer = _oauth.sign_in(AUTH, TOKEN, client_id, scopes, client_secret=secret,
                            extra={"access_type": "offline", "prompt": "consent select_account"}, say=say)
    connections.put_secret(conn, "refresh", answer["refresh_token"])
    return answer


def connect(conn, say=print, answers=None):
    """Sign one mailbox in. Fills in its address."""
    answer = sign_in(conn, SCOPES, say)
    me = _http.get_json(f"{API}/profile", answer["access_token"])
    conn["address"] = str(me.get("emailAddress") or "").lower()
    conn["label"] = conn["address"]
    conn.setdefault("send", True)
    return conn


def check(conn):
    me = _http.get_json(f"{API}/profile", token_for(conn))
    return f"{conn['address']}: reachable, {me.get('messagesTotal', 0)} messages"


def decode_header(value):
    """A raw mail header as the text a person would read (encoded words decoded, folds undone)."""
    if not value:
        return ""
    try:
        parts = email.header.decode_header(value)
    except (email.errors.HeaderParseError, ValueError):
        return " ".join(value.split())
    out = []
    for text, charset in parts:
        if isinstance(text, bytes):
            try:
                text = text.decode(charset or "utf-8", "replace")
            except LookupError:
                text = text.decode("utf-8", "replace")
        out.append(text)
    return " ".join("".join(out).split())


CHARSET = re.compile(r"charset\s*=\s*\"?([\w.:-]+)", re.I)


def _walk(token, msg_id, part, got=None, files=True):
    """{"plain": [text parts], "html": [html parts], "atts": [(file name, bytes, content id)]} of one email. files=False: the
    files are not downloaded (bytes None, nothing judged), only named, for an email already stored with its files."""
    got = got if got is not None else {"plain": [], "html": [], "atts": []}
    headers = {h["name"].lower(): h["value"] for h in part.get("headers", [])}
    mime = part.get("mimeType", "")
    if mime.startswith("text/") and part.get("body", {}).get("data"):
        raw = base64.urlsafe_b64decode(part["body"]["data"])
        cs = CHARSET.search(headers.get("content-type", ""))
        try:
            text = raw.decode(cs.group(1) if cs else "utf-8", "replace")
        except LookupError:
            text = raw.decode("utf-8", "replace")
        got["html" if mime.startswith("text/html") else "plain"].append(text)
    inline = "content-id" in headers or headers.get("content-disposition", "").lower().startswith("inline")
    cid = headers.get("content-id", "").strip().strip("<>").strip() or None
    name = part.get("filename") or (inline and mime.startswith("image/") and "inline." + mime.split("/")[1].split(";")[0])
    if name and part.get("body", {}).get("attachmentId"):
        size = part["body"].get("size") or 0
        ext = os.path.splitext(name)[1].lower()
        if not files:
            got["atts"].append((name, None, cid))
        elif (ext in _store.IMAGE_EXT and inline) or not _store.is_decoration(name, size, inline):
            one = _http.get_json(f"{API}/messages/{msg_id}/attachments/{part['body']['attachmentId']}", token)
            blob = base64.urlsafe_b64decode(one["data"])
            if not _store.is_decoration(name, size, inline, blob):
                got["atts"].append((name, blob, cid))
    for sub in part.get("parts", []) or []:
        _walk(token, msg_id, sub, got, files)
    return got


def _texts(got):
    """(the plain text the assistant reads, the HTML the page shows or None). An email sent only as HTML gets its text from
    the HTML."""
    html = "\n".join(got["html"]) or None
    plain = "\n".join(got["plain"])
    return (plain if plain.strip() or not html else _store.html_text(html)), html


SYSTEM_LABELS = {"INBOX", "UNREAD", "TRASH", "SPAM", "SENT", "DRAFT", "STARRED", "IMPORTANT", "CHAT"}
HIDDEN = {"UNREAD", "CHAT"}            # shown as state, never as a folder
KINDS = {"INBOX": "inbox", "SENT": "sent", "TRASH": "trash", "SPAM": "spam", "DRAFT": "drafts"}


def _label_names(token):
    """{label id: name} for the owner's own labels (Gmail's system ones are shown as state, not as labels)."""
    got = _http.get_json(f"{API}/labels", token)
    return {lb["id"]: lb["name"] for lb in got.get("labels", []) if lb.get("type") == "user"}


def _state(m, hdrs, names):
    ids = set(m.get("labelIds") or [])
    return {"unread": "UNREAD" in ids, "inbox": "INBOX" in ids, "trashed": "TRASH" in ids, "starred": "STARRED" in ids,
            "labels": [names[i] for i in ids if i in names], "folders": sorted(ids - HIDDEN), "synced": True,
            "cc": decode_header(hdrs.get("cc", "")), "from_name": email.utils.parseaddr(decode_header(hdrs.get("from", "")))[0],
            "header_id": hdrs.get("message-id", "").strip(), "refs": " ".join(hdrs.get("references", "").split())}


def _one(token, msg_id, account, writer, names):
    m = _http.get_json(f"{API}/messages/{msg_id}", token, {"format": "full"})
    hdrs = {h["name"].lower(): h["value"] for h in m.get("payload", {}).get("headers", [])}
    ts = dt.datetime.fromtimestamp(int(m["internalDate"]) / 1000)
    got = _walk(token, m["id"], m.get("payload", {}))
    body, html = _texts(got)
    frm = email.utils.parseaddr(hdrs.get("from", ""))[1].lower()
    writer.add(m["id"], ts, "out" if frm == account else "in", frm, decode_header(hdrs.get("to", "")),
               decode_header(hdrs.get("subject", "")), body, thread_id=m.get("threadId"), attachments=got["atts"],
               state=_state(m, hdrs, names), html=html)


def _html_only(token, msg_id, account):
    """A stored email's HTML, read again for the history reload (its files are already stored: they are only named)."""
    m = _http.get_json(f"{API}/messages/{msg_id}", token, {"format": "full"})
    got = _walk(token, msg_id, m.get("payload", {}), files=False)
    _body, html = _texts(got)
    if html:
        _store.put_html(account, msg_id, html, got["atts"])


def _ids(token, q, most, everywhere=False):
    refs, page = [], None
    while len(refs) < most:        # a listing holds at most 500 ids; follow every page
        params = {"q": q, "maxResults": min(most - len(refs), 500), "pageToken": page}
        if everywhere:
            params["includeSpamTrash"] = "true"
        listing = _http.get_json(f"{API}/messages", token, params)
        refs.extend(listing.get("messages", []))
        page = listing.get("nextPageToken")
        if not page:
            break
    return [r["id"] for r in refs[:most]]


LIST_MOST = 20000
OVERLAP = dt.timedelta(minutes=10)      # read a little before the mark; what is already stored is skipped


def gather(conn, ctx):
    """New mail first. The oldest emails not yet stored, at most ctx.limit; the mark moves only to the newest one fetched, so a
    burst bigger than the cap is taken over the next passes and nothing is skipped. The slow work is sync(), after every
    mailbox has been read."""
    account = conn["address"]
    token = token_for(conn)
    since = _store.since(f"email:{account}") - OVERLAP
    writer = _store.MailWriter(account, dry_run=ctx.dry_run)
    names = _label_names(token)
    held = _store.held_ids(account)
    ids = [i for i in _ids(token, f"after:{int(since.timestamp())}", LIST_MOST) if i not in held]
    for mid in ids[::-1][:ctx.limit]:           # the listing is newest first: fetch from the oldest end
        _one(token, mid, account, writer, names)
    written = writer.commit()
    more = max(0, len(ids) - ctx.limit)
    return f"{written} new" + (f", {more} more waiting for the next time I check" if more else "")


# --- the slow work: changes made elsewhere, the backfill, the label list ------------------------------------------------
CHANGES_MOST = 400              # emails whose labels are re-read in one go
FOLDERS_EVERY = dt.timedelta(minutes=10)


def _profile_history(token):
    return str(_http.get_json(f"{API}/profile", token).get("historyId") or "")


def _min(token, pid):
    try:
        return pid, _http.get_json(f"{API}/messages/{pid}", token, {"format": "minimal"}).get("labelIds") or []
    except _http.Refused as e:
        if e.status == 404:
            return pid, None                    # no longer in the mailbox
        raise


def _read_states(token, pids):
    with ThreadPoolExecutor(6) as ex:
        return list(ex.map(lambda p: _min(token, p), pids))


GMAIL_ID = re.compile(r"[0-9a-f]{12,20}")     # Gmail's own message ids; an earlier import's ids (Outlook's, imap:...) are not


def _rematch(token, account, pids):
    """Stored emails under ids that are not Gmail's: each is looked up in Gmail by its Message-ID header. One found takes
    Gmail's id as its current id; one not found, with no Message-ID, or already held under Gmail's id is set aside so it is
    not asked for again. Returns the Gmail ids now to read."""
    heads = _store.header_ids(account, pids)

    def look(pid):
        h = (heads.get(pid) or (pid.split(":", 2)[2] if pid.startswith("imap:") and pid.count(":") >= 2 else "")).strip()
        if not (h.startswith("<") and h.endswith(">") and len(h) > 2):
            return pid, None
        got = _ids(token, f"rfc822msgid:{h[1:-1]}", 1, everywhere=True)
        return pid, (got[0] if got else None)

    with ThreadPoolExecutor(6) as ex:
        found = list(ex.map(look, pids))
    done = _store.remap_ids(account, [(p, g) for p, g in found if g])
    moved = {p for p, _ in done}
    _store.mark_unmatched(account, [p for p, _ in found if p not in moved])
    return [g for _, g in done]


def _item(pid, label_ids, names):
    if label_ids is None:
        return {"pid": pid, "state": {"trashed": True, "inbox": False}, "folders": []}
    ids = set(label_ids)
    return {"pid": pid, "folders": sorted(ids - HIDDEN),
            "state": {"unread": "UNREAD" in ids, "inbox": "INBOX" in ids, "trashed": "TRASH" in ids, "starred": "STARRED" in ids,
                      "labels": [names[i] for i in ids if i in names]}}


def _folders(token, account):
    """The label list with its counts, kept in the folders table (asked of Gmail at most every 10 minutes)."""
    at = _store.cursor(account, "folders_at")
    if at and dt.datetime.now() - dt.datetime.fromisoformat(at) < FOLDERS_EVERY:
        return
    labels = [lb for lb in _http.get_json(f"{API}/labels", token).get("labels", []) if lb["id"] not in HIDDEN]
    with ThreadPoolExecutor(6) as ex:
        full = list(ex.map(lambda lb: _http.get_json(f"{API}/labels/{lb['id']}", token), labels))
    by_name = {lb["name"]: lb["id"] for lb in labels}
    rows = []
    for lb in full:
        name = lb["name"] if lb.get("type") == "user" else lb["name"].replace("_", " ").title()
        rows.append({"id": lb["id"], "path": name, "parent": by_name.get(name.rsplit("/", 1)[0]) if "/" in name else None,
                     "kind": KINDS.get(lb["id"], "label"), "unread": lb.get("messagesUnread"), "total": lb.get("messagesTotal")})
    _store.put_folders(account, rows)
    _store.set_cursor(account, "folders_at", dt.datetime.now().isoformat())


def _changes(token, account, names):
    """What was done to the mailbox elsewhere since the stored historyId: mail added, deleted, labelled, read, archived.
    Returns how many stored emails were re-read. A historyId Gmail no longer has (404) starts a full resync."""
    cur = _store.cursor(account, "history")
    if cur is None:
        _store.set_cursor(account, "history", _profile_history(token))      # from here on, history; the backfill covers the past
        return 0
    ids, gone, last, page = set(), set(), cur, None
    try:
        while True:
            got = _http.get_json(f"{API}/history", token, {"startHistoryId": cur, "maxResults": 500, "pageToken": page})
            for rec in got.get("history", []):
                for k in ("messagesAdded", "labelsAdded", "labelsRemoved"):
                    ids.update(x["message"]["id"] for x in rec.get(k, []))
                gone.update(x["message"]["id"] for x in rec.get("messagesDeleted", []))
                last = rec.get("id", last)
            page = got.get("nextPageToken")
            if not page:
                last = got.get("historyId", last)
                break
            if len(ids) + len(gone) >= CHANGES_MOST:        # the rest next pass, from the last record read
                break
    except _http.Refused as e:
        if e.status != 404:
            raise
        _store.set_cursor(account, "history", _profile_history(token))
        _store.reset_synced(account)                        # too old: every stored email is read again, a portion per pass
        return 0
    held = _store.held_ids(account)
    items = [_item(p, l, names) for p, l in _read_states(token, [i for i in ids - gone if i in held])]
    items += [_item(i, None, names) for i in gone if i in held]
    _store.apply_states(account, items)
    _store.set_cursor(account, "history", str(last))
    return len(items)


def sync(conn, ctx, end):
    """The slow work, after the new mail of every mailbox is in: the label list, changes made elsewhere, then the backfill of
    state for stored mail not read yet (portions, until `end`). Returns a plain line."""
    account = conn["address"]
    token = token_for(conn)
    names = _label_names(token)
    _folders(token, account)
    changed = _changes(token, account, names)
    read, size = 0, 50                  # at least one small portion every pass, so the backfill always moves on
    while True:
        rows = _store.unsynced(account, size)
        if not rows:
            break
        pids = [p for _, p in rows if GMAIL_ID.fullmatch(p)]       # only Gmail's own ids are sent to Gmail
        odd = [p for _, p in rows if not GMAIL_ID.fullmatch(p)]
        if odd:
            pids += _rematch(token, account, odd)
        _store.apply_states(account, [_item(p, l, names) for p, l in _read_states(token, pids)])
        read += len(rows)
        if time.time() >= end:
            break
        size = 200
    left = len(_store.unsynced(account, 1))
    return f"{changed} changed elsewhere, {read} stored emails read" + (" (more to read the next time I check)" if left else "")


def reload(conn, end):
    """The full history reload's portion for this mailbox: its own step of the pass, after the new mail and the filing, with its
    own time; never part of reading the new mail (connections/run.py --kind email-reload)."""
    token = token_for(conn)
    return _reload(token, conn["address"], _label_names(token), end)


RELOAD_PAGE = 25            # emails listed (and the new ones read whole) per portion of the full history reload


def _reload(token, account, names, end):
    """The full history reload (Settings, Tools), a portion at a time until `end`: every email Gmail has, trash and spam too,
    newest first. One already held is marked seen (and read again for its HTML when it has none kept); any other is read
    whole and stored, paired with its stored copy where there is one (_store.MailWriter). Returns the progress
    line, or "" when no reload was started."""
    st = _store.reload_state(account)
    if not st or st.get("done"):
        return _store.reload_line(st) if st and st.get("done_at", "") >= (dt.datetime.now() - dt.timedelta(days=1)).isoformat() else ""
    started = dt.datetime.fromisoformat(st["started"])
    while True:                 # at least one portion every pass, so the reload always moves on
        got = _http.get_json(f"{API}/messages", token, {"maxResults": RELOAD_PAGE, "pageToken": st.get("page"), "includeSpamTrash": "true"})
        ids = [r["id"] for r in got.get("messages", [])]
        held = _store.held_ids(account)
        _store.reload_seen_ids(account, [i for i in ids if i in held])
        for i in _store.lacking_html(account, [i for i in ids if i in held]):      # stored before its HTML was kept
            _html_only(token, i, account)
        writer = _store.MailWriter(account, reload=started)
        for i in ids:
            if i not in held:
                _one(token, i, account, writer, names)
        st["new"] += writer.commit()
        st["paired"] += writer.paired
        st["read"] += len(ids)
        st["page"] = got.get("nextPageToken")
        if not st["page"]:
            st = _store.reload_finish(account, st)
            break
        _store.set_reload_state(account, st)
        if time.time() >= end:
            break
    return _store.reload_line(st)


def fetch(conn, provider_ids):
    """Store these emails (found by a search) the same way a pass does. Returns how many were new."""
    token = token_for(conn)
    writer = _store.MailWriter(conn["address"])
    names = _label_names(token)
    for mid in provider_ids:
        _one(token, mid, conn["address"], writer, names)
    return writer.commit()


# --- the envelope catalog (catalog.py): sender, subject and date only; a body only when a look-back needs it ---------------
ENVELOPE_PAGE = 500             # ids listed per call; each id's headers are then read in parallel
ENVELOPE_HEADERS = ("From", "To", "Subject", "Date")


def _envelope(token, msg_id, account):
    m = _http.get_json(f"{API}/messages/{msg_id}", token, {"format": "metadata", "metadataHeaders": list(ENVELOPE_HEADERS)})
    hdrs = {h["name"].lower(): h["value"] for h in m.get("payload", {}).get("headers", [])}
    name, frm = email.utils.parseaddr(decode_header(hdrs.get("from", "")))
    out = "SENT" in (m.get("labelIds") or []) or frm.lower() == account
    return {"provider_id": m["id"], "ts": dt.datetime.fromtimestamp(int(m.get("internalDate") or 0) / 1000),
            "direction": "out" if out else "in", "from_key": frm.lower(), "from_name": name,
            "to": [a.lower() for _n, a in email.utils.getaddresses([decode_header(hdrs.get("to", ""))]) if a],
            "subject": decode_header(hdrs.get("subject", "")), "thread_id": m.get("threadId")}


def envelopes(conn, since, cursor, end):
    """One portion of the catalog: a page of ids after `since`, each read as headers only (no body, no files). cursor is
    Gmail's page token; done when there is no next page."""
    account = conn["address"]
    token = token_for(conn)
    rows = []
    while time.time() < end:
        q = f"after:{since.strftime('%Y/%m/%d')}"
        listing = _http.get_json(f"{API}/messages", token, {"q": q, "maxResults": ENVELOPE_PAGE, "pageToken": cursor,
                                                            "includeSpamTrash": "false"})
        ids = [r["id"] for r in listing.get("messages", [])]
        with ThreadPoolExecutor(8) as ex:
            rows += list(ex.map(lambda i: _envelope(token, i, account), ids))
        cursor = listing.get("nextPageToken")
        if not cursor:
            return {"rows": rows, "cursor": None, "done": True, "total": listing.get("resultSizeEstimate")}
    return {"rows": rows, "cursor": cursor, "done": False}


def envelope_text(conn, provider_id):
    """One email's plain text, read when a look-back needs it; nothing is stored as a new message."""
    token = token_for(conn)
    m = _http.get_json(f"{API}/messages/{provider_id}", token, {"format": "full"})
    body, _html = _texts(_walk(token, provider_id, m.get("payload", {}), files=False))
    return body


PEOPLE_API = "https://people.googleapis.com/v1"


def address_book(conn):
    """The account's own contacts: [{"name", "emails", "phones"}]. Needs the contacts permission and Google's People API
    turned on (the setup steps); without them it says so by raising, and Contacts goes on without this book."""
    token = token_for(conn)
    out, page = [], None
    while True:
        got = _http.get_json(f"{PEOPLE_API}/people/me/connections", token,
                             {"personFields": "names,emailAddresses,phoneNumbers", "pageSize": 1000, "pageToken": page})
        for p in got.get("connections", []):
            out.append({"name": ((p.get("names") or [{}])[0]).get("displayName") or "",
                        "emails": [e.get("value", "").lower() for e in p.get("emailAddresses", []) if e.get("value")],
                        "phones": [n.get("value", "") for n in p.get("phoneNumbers", []) if n.get("value")]})
        page = got.get("nextPageToken")
        if not page:
            return out


def search(conn, words, most=25):
    """Gmail's own search over the whole mailbox: the ids of the best matches."""
    return _ids(token_for(conn), str(words), most)


def labels(conn):
    return sorted(_label_names(token_for(conn)).values(), key=str.lower)


def headers(conn, provider_id):
    """What a reply or forward needs that a stored email may not hold: its Message-ID, References, Cc and sender's name."""
    m = _http.get_json(f"{API}/messages/{provider_id}", token_for(conn),
                       {"format": "metadata", "metadataHeaders": ["Message-ID", "References", "Cc", "From"]})
    hdrs = {h["name"].lower(): h["value"] for h in m.get("payload", {}).get("headers", [])}
    return {"header_id": hdrs.get("message-id", "").strip(), "refs": " ".join(hdrs.get("references", "").split()),
            "cc": decode_header(hdrs.get("cc", "")), "from_name": email.utils.parseaddr(decode_header(hdrs.get("from", "")))[0],
            "thread": m.get("threadId")}


def unsub_headers(conn, provider_id):
    """The email's List-Unsubscribe and List-Unsubscribe-Post headers ("" when it has none)."""
    m = _http.get_json(f"{API}/messages/{provider_id}", token_for(conn),
                       {"format": "metadata", "metadataHeaders": ["List-Unsubscribe", "List-Unsubscribe-Post"]})
    hdrs = {h["name"].lower(): h["value"] for h in m.get("payload", {}).get("headers", [])}
    return {"list": hdrs.get("list-unsubscribe", ""), "post": hdrs.get("list-unsubscribe-post", "")}


def attachment(conn, provider_id, name):
    """One attachment's bytes, by its file name, read from the mail service; None when the email has no such file."""
    token = token_for(conn)
    m = _http.get_json(f"{API}/messages/{provider_id}", token, {"format": "full"})
    stack = [m.get("payload", {})]
    while stack:
        part = stack.pop()
        stack.extend(part.get("parts", []) or [])
        if part.get("filename") == name:
            b = part.get("body", {})
            if b.get("attachmentId"):
                got = _http.get_json(f"{API}/messages/{provider_id}/attachments/{b['attachmentId']}", token)
                return base64.urlsafe_b64decode(got["data"])
            if b.get("data"):
                return base64.urlsafe_b64decode(b["data"])
    return None


class NotAllowed(RuntimeError):
    """The sign-in on this computer does not allow changing mail."""


def _change(path, token, obj=None):
    try:
        return _http.call_json("POST", f"{API}/{path}", token, obj)[1]
    except _http.Refused as e:
        if e.status in (401, 403):
            raise NotAllowed("this mailbox's sign-in does not allow changing mail yet") from None
        raise


def _label_id(token, name):
    for lid, nm in _label_names(token).items():
        if nm.lower() == name.lower():
            return lid
    return _change("labels", token, {"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"})["id"]


def act(conn, provider_id, what, label=None, thread_id=None):
    """Change one email at the owner's press: archive (its whole conversation leaves the inbox), trash (to the trash, never
    deleted for good), junk (to Spam), restore (undo of archive, trash or junk), read, unread, label or unlabel (label: the name; a new name makes the label). Returns the email's
    provider id afterwards (the same for Gmail)."""
    token = token_for(conn)
    if what == "archive":
        _change(f"threads/{thread_id}/modify" if thread_id else f"messages/{provider_id}/modify", token, {"removeLabelIds": ["INBOX"]})
    elif what == "trash":
        _change(f"messages/{provider_id}/trash", token)
    elif what == "junk":       # to Spam, out of the inbox
        _change(f"messages/{provider_id}/modify", token, {"addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX"]})
    elif what == "restore":    # undo of archive, trash or junk (label says which): back in the inbox
        if label == "trash":
            _change(f"messages/{provider_id}/untrash", token)
        if label == "archive" and thread_id:
            _change(f"threads/{thread_id}/modify", token, {"addLabelIds": ["INBOX"]})
        else:
            _change(f"messages/{provider_id}/modify", token, {"addLabelIds": ["INBOX"], "removeLabelIds": ["SPAM"] if label == "junk" else []})
    elif what in ("read", "unread"):
        _change(f"messages/{provider_id}/modify", token, {("removeLabelIds" if what == "read" else "addLabelIds"): ["UNREAD"]})
    elif what in ("star", "unstar"):
        _change(f"messages/{provider_id}/modify", token, {("addLabelIds" if what == "star" else "removeLabelIds"): ["STARRED"]})
    elif what == "move":       # label = the destination label's id: add it, and the email leaves the inbox
        _change(f"messages/{provider_id}/modify", token, {"addLabelIds": [str(label)], "removeLabelIds": ["INBOX"]})
    elif what in ("label", "unlabel"):
        lid = _label_id(token, str(label or "").strip())
        _change(f"messages/{provider_id}/modify", token, {("addLabelIds" if what == "label" else "removeLabelIds"): [lid]})
    else:
        raise ValueError(f"there is no mail action called {what}")
    return provider_id


# --- labels themselves (Gmail's folders), on the owner's words: a label inside another is named "Parent/Child" -------------------
FOLDER_DELETE_SAYS = "In Gmail deleting a label keeps every email: they stay in All Mail and in any other label they have."


def _label_call(method, path, token, obj=None):
    try:
        return _http.call_json(method, f"{API}/{path}", token, obj, ok=(200, 201, 204))[1]
    except _http.Refused as e:
        if e.status in (401, 403):
            raise NotAllowed("this mailbox's sign-in does not allow changing mail yet") from None
        raise


def _rename_tree(token, label_id, new_name):
    """A label renamed, and every label inside it renamed with it (Gmail keeps the nesting only in the names)."""
    names = _label_names(token)
    old = names.get(label_id)
    if old is None:
        raise ValueError("that label is not in this mailbox")
    for lid, nm in names.items():
        if lid == label_id:
            _label_call("PATCH", f"labels/{lid}", token, {"name": new_name})
        elif nm.startswith(old + "/"):
            _label_call("PATCH", f"labels/{lid}", token, {"name": new_name + nm[len(old):]})


def folder_create(conn, name, parent_id=None):
    token = token_for(conn)
    parent = _label_names(token).get(parent_id) if parent_id else None
    return _label_call("POST", "labels", token, {"name": f"{parent}/{name}" if parent else name, "labelListVisibility": "labelShow",
                                                 "messageListVisibility": "show"}).get("id")


def folder_rename(conn, folder_id, name):
    token = token_for(conn)
    old = _label_names(token).get(folder_id) or ""
    _rename_tree(token, folder_id, (old.rsplit("/", 1)[0] + "/" + name) if "/" in old else name)


def folder_move(conn, folder_id, parent_id=None):
    token = token_for(conn)
    names = _label_names(token)
    leaf = (names.get(folder_id) or "").rsplit("/", 1)[-1]
    _rename_tree(token, folder_id, f"{names[parent_id]}/{leaf}" if parent_id else leaf)


def folder_delete(conn, folder_id):
    _label_call("DELETE", f"labels/{folder_id}", token_for(conn))


def folder_info(conn, folder_id):
    """{"total": emails carrying the label, "children": labels inside it}."""
    token = token_for(conn)
    got = _http.get_json(f"{API}/labels/{folder_id}", token)
    name = got.get("name") or ""
    return {"total": int(got.get("messagesTotal") or 0), "children": sum(1 for n in _label_names(token).values() if n.startswith(name + "/"))}


def folder_refresh(conn):
    _store.set_cursor(conn["address"], "folders_at", "")
    _folders(token_for(conn), conn["address"])


def send_mime(conn, raw, thread_id=None):
    """Send one complete email built by the engine (its own To, Cc and Bcc); Google files the copy in Sent. A reply names
    its conversation so it stays in that thread."""
    body = {"raw": base64.urlsafe_b64encode(raw).decode()}
    if thread_id:
        body["threadId"] = thread_id
    _status, sent = _http.post_json(f"{API}/messages/send", token_for(conn), body)
    return sent.get("id")


def save_draft(conn, raw, thread_id=None, replace=None):
    """Keep one complete email as a draft in this mailbox's Drafts (a draft saved before is replaced). Returns the draft's id."""
    token = token_for(conn)
    if replace:
        delete_draft(conn, replace)
    msg = {"raw": base64.urlsafe_b64encode(raw).decode()}
    if thread_id:
        msg["threadId"] = thread_id
    return (_http.call_json("POST", f"{API}/drafts", token, {"message": msg})[1] or {}).get("id")


def delete_draft(conn, draft_id):
    try:
        _http.call_json("DELETE", f"{API}/drafts/" + urllib.parse.quote(str(draft_id), safe=""), token_for(conn))
    except _http.Refused as e:
        if e.status != 404:        # already gone is as good as deleted
            raise


def send(conn, to, cc, subject, html, files=()):
    """Send one email; Google files the copy in Sent itself. Never a blind copy."""
    msg = EmailMessage()
    msg["From"] = conn["address"]
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg.set_content("This message is formatted in HTML.")
    msg.add_alternative(html, subtype="html")
    for p in files:
        major, _, minor = (mimetypes.guess_type(p)[0] or "application/octet-stream").partition("/")
        with open(p, "rb") as f:
            msg.add_attachment(f.read(), maintype=major, subtype=minor, filename=os.path.basename(p))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    _status, sent = _http.post_json(f"{API}/messages/send", token_for(conn), {"raw": raw})
    return sent.get("id")


# --- filters (Settings, Mail rules): the filters Gmail runs on its side --------------------------------------------------
RULE_READ = ("https://www.googleapis.com/auth/gmail.settings.basic", "https://www.googleapis.com/auth/gmail.modify",
             "https://www.googleapis.com/auth/gmail.readonly", "https://mail.google.com/")
RULE_WRITE = ("https://www.googleapis.com/auth/gmail.settings.basic",)
RULE_NEEDS_ADDRESS = False
CRITERIA = ("from", "to", "subject")


def _settings(method, path, token, obj=None):
    try:
        return _http.call_json(method, f"{API}/settings/{path}", token, obj)[1]
    except _http.Refused as e:
        if e.status in (401, 403):
            raise NotAllowed("this mailbox's sign-in does not allow filters yet") from None
        raise


def rules_list(conn):
    """The filters of this mailbox, in the terms the page shows. A filter that does anything the page does not show, or
    several labels, is read only."""
    out = []
    for f in _settings("GET", "filters", token_for(conn)).get("filter") or []:
        c, a = f.get("criteria") or {}, f.get("action") or {}
        add, rem = set(a.get("addLabelIds") or []), set(a.get("removeLabelIds") or [])
        custom = add - {"STARRED"}
        move = next(iter(custom)) if len(custom) == 1 and "INBOX" in rem else None
        extra = [k for k in c if k not in CRITERIA and c.get(k)] + (["forward"] if a.get("forward") else [])
        out.append({"id": f.get("id"), "enabled": True,
                    "when": {k: str(c.get(k) or "") for k in CRITERIA},
                    "then": {"move": move, "read": "UNREAD" in rem, "star": "STARRED" in add,
                             "archive": "INBOX" in rem and move is None},
                    "read_only": bool(extra) or bool(rem - {"INBOX", "UNREAD"}) or "UNREAD" in add
                                 or (bool(custom) and move is None) or len(custom) > (1 if move else 0)})
    return out


def rule_create(conn, spec):
    """One filter from the page's form (the same spec as microsoft_mail.rule_create). Returns the new filter's id."""
    add, rem = [], []
    d = spec["do"]
    if d == "move":
        add.append(str(spec["folder"]))
        rem.append("INBOX")
    elif d == "archive":
        rem.append("INBOX")
    elif d == "read":
        rem.append("UNREAD")
    elif d == "star":
        add.append("STARRED")
    action = {k: v for k, v in (("addLabelIds", add), ("removeLabelIds", rem)) if v}
    body = {"criteria": {k: spec["when"][k] for k in CRITERIA if spec["when"].get(k)}, "action": action}
    return (_settings("POST", "filters", token_for(conn), body) or {}).get("id")


def rule_delete(conn, rule_id):
    _settings("DELETE", "filters/" + urllib.parse.quote(str(rule_id), safe=""), token_for(conn))


# --- meeting invites (invites.py) ----------------------------------------------------------------------------------------
def _calendar_conn(address):
    """The owner's Google Calendar connection for this same account, or None."""
    for c in connections.listed("calendar"):
        if c.get("type") == "google_calendar" and str(c.get("address") or "").lower() == str(address or "").lower():
            return c
    return None


def _find_event(conn, uid):
    """(calendar token, the account's copy of the event) by iCalUID on its main calendar, or (token, None)."""
    cal = _calendar_conn(conn["address"])
    if cal is None:
        return None, None
    token = token_for(cal)
    got = _http.get_json("https://www.googleapis.com/calendar/v3/calendars/primary/events", token, {"iCalUID": uid})
    items = [e for e in got.get("items", []) if e.get("status") != "cancelled"]
    return token, (items[0] if items else None)


def invite_source(conn, provider_id):
    """The meeting request this email carries (a text/calendar part or an .ics file), read from the service, or None."""
    import invites
    token = token_for(conn)
    m = _http.get_json(f"{API}/messages/{provider_id}", token, {"format": "full"})
    stack, text = [m.get("payload", {})], None
    while stack and text is None:
        part = stack.pop()
        stack.extend(part.get("parts", []) or [])
        if part.get("mimeType", "").lower().startswith("text/calendar") or str(part.get("filename") or "").lower().endswith(".ics"):
            b = part.get("body", {})
            if b.get("data"):
                text = base64.urlsafe_b64decode(b["data"]).decode("utf-8", "replace")
            elif b.get("attachmentId"):
                text = base64.urlsafe_b64decode(_http.get_json(f"{API}/messages/{provider_id}/attachments/{b['attachmentId']}", token)["data"]).decode("utf-8", "replace")
    inv = invites.parse_ics(text) if text else None
    if inv:
        try:        # what the owner already answered, when the account's calendar can be read
            _tok, ev = _find_event(conn, inv["uid"]) if inv["uid"] else (None, None)
            me = next((a for a in (ev or {}).get("attendees", []) if a.get("self")), None)
            inv["response"] = {"accepted": "accept", "tentative": "tentative", "declined": "decline"}.get((me or {}).get("responseStatus"), "")
        except Exception:  # noqa: BLE001 - the bar still shows; only the current answer is unknown
            pass
    return inv


class NotFound(RuntimeError):
    """The meeting is not on the account's calendar."""


def invite_answer(conn, inv, answer, note=""):
    """Set the owner's answer on the event (Calendar events.patch, attendee responseStatus, sendUpdates=all): the organizer is told."""
    if not inv.get("uid"):
        raise NotFound("no meeting id")
    try:
        token, ev = _find_event(conn, inv["uid"])
        if token is None:
            raise NotAllowed("no Google Calendar sign-in for this account")
        if ev is None:
            raise NotFound("not on the calendar")
        mine = [dict(a) for a in ev.get("attendees", [])]
        me = next((a for a in mine if a.get("self")), None)
        if me is None:
            raise NotFound("not an attendee")
        me["responseStatus"] = {"accept": "accepted", "tentative": "tentative", "decline": "declined"}[answer]
        if note:
            me["comment"] = note
        _http.call_json("PATCH", f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{urllib.parse.quote(ev['id'], safe='')}?sendUpdates=all",
                        token, {"attendees": mine})
    except _http.Refused as e:
        if e.status in (401, 403):
            raise NotAllowed("this sign-in does not allow answering invites yet") from None
        raise
