r"""Microsoft mail, read through Microsoft Graph: work or school (Microsoft 365) and personal (outlook.com, hotmail.com, live.com)."""
import base64
import datetime as dt
import json
import mimetypes
import os
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from connections import _http, _oauth, _store
import connections

TYPE = "microsoft_mail"
NAME = "Microsoft mail (work, school, or personal Outlook.com and Hotmail)"
KIND = "email"
CAN_SEND = True
CAN_ACT = ("archive", "trash", "label", "read")     # needs Mail.ReadWrite
ACT_SCOPE = "Mail.ReadWrite"
APP = "microsoft"           # every Microsoft mailbox of one owner signs in through the same registration
APP_ASKS = [
    {"key": "client_id", "label": "Application (client) ID", "help": "From the Overview page of the app you registered (step 6)."},
    {"key": "tenant", "label": "Directory (tenant) ID", "help": "From the same Overview page, the line below it. Type common instead if you chose the choice that includes personal Microsoft accounts (step 3)."},
]
ASKS = []                   # nothing else is typed: the address comes from the sign-in

SETUP = """\
WHAT THIS CONNECTS
A Microsoft mailbox: at work or school (Microsoft 365), or a personal outlook.com, hotmail.com
or live.com one. I read new mail and its
attachments. I can also send an email you write and send yourself from your page, and archive,
delete (to Deleted Items), label (categories) or mark read an email when you press that on your page.

WHAT YOU NEED
- Your work email address and the ability to sign in to it in a browser.
- About 10 minutes, once. Every mailbox you add after the first skips straight to step 9.
- Your company may not let staff register an app (step 2 will tell you). If so, send your IT
  person steps 2 to 7 and ask them for the two IDs in step 6.

ONE TIME: REGISTER YOUR OWN CONNECTION WITH MICROSOFT
Microsoft only hands mail to a program that is registered with it. You register your own; it
is free, and nobody else can use it.
1. Open https://entra.microsoft.com and sign in with your work email.
2. In the left menu click "Entra ID", then "App registrations", then "New registration" at the top.
   If you see "You do not have access", your company blocks this; see WHAT YOU NEED above.
3. Name: type "My assistant". Under "Supported account types" choose "Accounts in any
   organizational directory and personal Microsoft accounts", so work and personal mailboxes
   (outlook.com, hotmail.com, live.com) both sign in through it. (If your company only allows
   the first choice, leave it: work mailboxes still connect.)
4. Under "Redirect URI": in the first box choose "Public client/native (mobile & desktop)".
   In the second box type exactly:  http://localhost
5. Click "Register".
6. You are now on the app's Overview page. Two lines matter: "Application (client) ID" and
   "Directory (tenant) ID". Each has a copy button at its right. Copy each into the matching
   box in the setup window. (These two are not passwords.) If you chose personal Microsoft
   accounts in step 3, type common in the tenant box instead of the Directory (tenant) ID.
7. In the left menu click "API permissions", then "Add a permission", then "Microsoft Graph",
   then "Delegated permissions". In the search box type Mail and tick "Mail.ReadWrite" and
   "Mail.Send". Search User and tick "User.Read" if it is not already there. Search offline and
   tick "offline_access". Search Contacts and tick "Contacts.Read" (so your assistant can read
   your Outlook contacts into Contacts). Click "Add permissions".
8. In the left menu click "Authentication". Near the bottom set "Allow public client flows"
   to Yes and click "Save".

EACH MAILBOX
9. In the setup window press "Sign in". Your browser opens Microsoft's own sign-in page.
10. Sign in with the mailbox you want to connect and click "Accept" on the permissions page.
    Your password goes only to Microsoft; I never see it.
11. The browser says "Signed in." Close that tab. The setup window shows the mailbox as connected.

IF SOMETHING GOES WRONG
- "Need admin approval": your company requires an administrator to approve. Send them the
  Application (client) ID from step 6 and ask them to grant consent for Mail.ReadWrite, Mail.Send,
  User.Read, Contacts.Read and offline_access.
- The page shows a health line "sign this account in again": Microsoft ended the sign-in
  (often after a password change). Open Setup, pick the mailbox, press "Sign in" again.
- Archive, Delete, Label or Mark read on your page says the sign-in "does not allow changing
  mail yet": the registration or the sign-in was made before I could change mail.
  Add "Mail.ReadWrite" in step 7 (your IT person may need to grant it), then open Setup, pick
  the mailbox and press "Sign in" again.
"""

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = ["offline_access", "User.Read", "Mail.ReadWrite", "Mail.Send", "MailboxSettings.ReadWrite", "Calendars.ReadWrite", "Contacts.Read"]   # MailboxSettings: the inbox rules (mail_rules.py); Calendars: answering meeting invites (invites.py)
HDR = {"Prefer": 'IdType="ImmutableId"'}      # a message keeps its id when it is moved to another folder (Microsoft's immutable ids)
OVERLAP = dt.timedelta(minutes=10)      # read a little before the watermark; duplicates are dropped on storing


def _get(url, token, params=None, extra=None):
    return _http.get_json(url, token, params, headers=dict(HDR, **(extra or {})))


def _urls():
    tenant = connections.app(APP).get("tenant") or "organizations"
    base = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0"
    return base + "/authorize", base + "/token"


def _token(conn):
    app = connections.app(APP)
    if not app.get("client_id"):
        raise _oauth.SignInFailed("the Microsoft registration is missing; open Setup and add it")
    return _oauth.access(conn, _urls()[1], app["client_id"])


def connect(conn, say=print, answers=None):
    """Sign one mailbox in. Fills in its address."""
    app = connections.app(APP)
    auth, token = _urls()
    answer = _oauth.sign_in(auth, token, app["client_id"], SCOPES, extra={"prompt": "select_account"}, say=say)
    connections.put_secret(conn, "refresh", answer["refresh_token"])
    me = _get(f"{GRAPH}/me", answer["access_token"], {"$select": "mail,userPrincipalName,displayName"})
    conn["address"] = (me.get("mail") or me.get("userPrincipalName") or "").lower()
    conn["label"] = conn["address"]
    conn.setdefault("send", True)
    return conn


def check(conn):
    """One harmless read. Returns a plain line; raises when the connection does not work."""
    got = _get(f"{GRAPH}/me/mailFolders/inbox", _token(conn), {"$select": "totalItemCount"})
    return f"{conn['address']}: reachable, {got.get('totalItemCount', 0)} messages in the inbox"


SELECT = ("id,subject,body,from,toRecipients,ccRecipients,receivedDateTime,conversationId,parentFolderId,"
          "hasAttachments,isDraft,isRead,categories,internetMessageId,flag")


def _addr(r):
    return ((r or {}).get("emailAddress") or {}).get("address", "")


def _one(token, m, account, writer, folders):
    ts = _store.local_naive(dt.datetime.strptime(m["receivedDateTime"][:19], "%Y-%m-%dT%H:%M:%S")
                            .replace(tzinfo=dt.timezone.utc))
    frm = _addr(m.get("from"))
    to = ",".join(_addr(r) for r in m.get("toRecipients", []))
    body, html = _texts(m)
    atts = []
    if m.get("hasAttachments") or "cid:" in (html or ""):
        for item in _attachments(token, m["id"]):
            if not item.get("contentBytes"):
                continue
            blob = base64.b64decode(item["contentBytes"])
            if not _store.is_decoration(item.get("name", ""), item.get("size") or 0, bool(item.get("isInline")), blob):
                atts.append((item.get("name"), blob, (item.get("contentId") or "").strip("<>") or None))
    folder = m.get("parentFolderId")
    state = {"unread": not m.get("isRead", True), "inbox": bool(folder and folder == folders.get("inbox")),
             "trashed": bool(folder and folder == folders.get("deleteditems")),
             "starred": ((m.get("flag") or {}).get("flagStatus") == "flagged"), "labels": list(m.get("categories") or []),
             "cc": ", ".join(_addr(r) for r in m.get("ccRecipients", [])),
             "from_name": ((m.get("from") or {}).get("emailAddress") or {}).get("name", ""),
             "header_id": m.get("internetMessageId") or "", "folders": [folder] if folder else None, "synced": True}
    writer.add(m["id"], ts, "out" if frm.lower() == account else "in", frm, to, m.get("subject"), body,
               folder=folder, thread_id=m.get("conversationId"), attachments=atts, state=state, html=html)


def _texts(m):
    """(the plain text the assistant reads, the HTML the page shows or None). Microsoft hands an HTML email as HTML only:
    its text is taken from it."""
    b = m.get("body") or {}
    content = b.get("content") or ""
    if str(b.get("contentType") or "").lower() == "html" and content.strip():
        return _store.html_text(content), content
    return content, None


def _attachments(token, msg_id):
    try:
        return _get(f"{GRAPH}/me/messages/{msg_id}/attachments", token).get("value", [])
    except _http.Refused:
        return []


def _html_only(token, m, account):
    """A stored email's HTML, from the reload's listing (its files are already stored: matched to the HTML's pictures by name)."""
    _body, html = _texts(m)
    if html:
        named = [(a.get("name"), None, (a.get("contentId") or "").strip("<>") or None)
                 for a in (_attachments(token, m["id"]) if "cid:" in html else [])]
        _store.put_html(account, m["id"], html, named)


def gather(conn, ctx):
    """New mail first. The oldest emails not yet stored, at most ctx.limit; the mark moves only to the newest one fetched, so a
    burst bigger than the cap is taken over the next passes and nothing is skipped. The slow work is sync(), after every
    mailbox has been read."""
    account = conn["address"]
    token = _token(conn)
    since = _store.since(f"email:{account}") - OVERLAP
    since_utc = since.astimezone(dt.timezone.utc)       # the stored time is local wall time
    writer = _store.MailWriter(account, dry_run=ctx.dry_run)
    folders = _kinds(conn, token)
    held = _store.held_ids(account)
    url = (f"{GRAPH}/me/messages?$filter=receivedDateTime ge {since_utc:%Y-%m-%dT%H:%M:%SZ}"
           f"&$select={SELECT}&$orderby=receivedDateTime asc&$top=50").replace(" ", "%20")
    fetched, more = 0, False
    while url:
        page = _get(url, token)
        for m in page.get("value", []):
            if m.get("isDraft") or m["id"] in held:     # this listing spans every folder; a draft is not mail yet
                continue
            if fetched >= ctx.limit:
                more = True
                break
            _one(token, m, account, writer, folders)
            fetched += 1
        url = None if more else page.get("@odata.nextLink")
    written = writer.commit()
    return f"{written} new" + (", more waiting for the next time I check" if more else "")


# --- the slow work: the folder tree, changes made elsewhere (delta), the backfill ----------------------------------------
FOLDER_SELECT = "id,displayName,parentFolderId,childFolderCount,unreadItemCount,totalItemCount"
WELL = {"inbox": "inbox", "sentitems": "sent", "deleteditems": "trash", "drafts": "drafts", "archive": "archive",
        "junkemail": "spam", "outbox": "outbox"}
SKIP_KINDS = ("drafts", "outbox")
DELTA_SELECT = "id,isRead,parentFolderId,internetMessageId,categories,flag"
DELTA_PREFER = 'IdType="ImmutableId", odata.maxpagesize=200'
FOLDERS_EVERY = dt.timedelta(minutes=10)


def _pages(url, token):
    while url:
        page = _get(url, token)
        yield from page.get("value", [])
        url = page.get("@odata.nextLink")


def _folders(conn, token):
    """Read the whole folder tree (children too) with its counts into the folders table; returns it."""
    account = conn["address"]
    named = {}
    for well, kind in WELL.items():
        try:
            named[_get(f"{GRAPH}/me/mailFolders/{well}", token, {"$select": "id"})["id"]] = kind
        except _http.Refused:
            pass
    rows = []

    def walk(url, parent, path):
        for f in _pages(url, token):
            here = f"{path}/{f['displayName']}" if path else f["displayName"]
            rows.append({"id": f["id"], "path": here, "parent": parent, "kind": named.get(f["id"], "folder"),
                         "unread": f.get("unreadItemCount"), "total": f.get("totalItemCount")})
            if f.get("childFolderCount"):
                walk(f"{GRAPH}/me/mailFolders/{f['id']}/childFolders?$top=100&$select={FOLDER_SELECT}", f["id"], here)

    walk(f"{GRAPH}/me/mailFolders?$top=100&$select={FOLDER_SELECT}", None, "")
    _store.put_folders(account, rows)
    _store.set_cursor(account, "folders_at", dt.datetime.now().isoformat())
    return _store.folders(account)


def _kinds(conn, token):
    """{'inbox': id, 'deleteditems': id}: from the stored folder list, read from Microsoft when none is stored yet."""
    want = {"inbox": "inbox", "trash": "deleteditems"}
    rows = _store.folders(conn["address"]) or _folders(conn, token)
    return {want[r["kind"]]: r["id"] for r in rows if r["kind"] in want}


MIGRATE_AT_ONCE = 200          # stored ids asked about in one portion; the place is kept after each, so a stop never redoes one


def _migrate(account, token, end):
    """Once per mailbox: the ids stored before immutable ids were asked for become the immutable ones (translateExchangeIds),
    so a moved email keeps its id. A portion at a time until `end`, its place kept after each. True when done."""
    if _store.cursor(account, "immutable") == "1":
        return True
    last = int(_store.cursor(account, "immutable_at") or 0)
    while time.time() < end:
        rows = _store.db.query("SELECT m.id, coalesce(s.provider_id, m.provider_id) FROM messages m LEFT JOIN mail_state s ON s.message_id = m.id"
                               " WHERE m.channel='email' AND m.account=? AND m.id>? AND m.provider_id IS NOT NULL ORDER BY m.id LIMIT ?",
                               (account, last, MIGRATE_AT_ONCE))
        if not rows:
            _store.set_cursor(account, "immutable", "1")
            return True
        pairs = _translate(token, [r[1] for r in rows], end)
        if pairs is None:       # out of time inside the portion: it is asked again next check
            break
        _store.remap_ids(account, pairs)
        last = rows[-1][0]
        _store.set_cursor(account, "immutable_at", str(last))
    return False


def _ask_ids(token, ids, source, target):
    _s, got = _http.call_json("POST", f"{GRAPH}/me/translateExchangeIds", token,
                              {"inputIds": ids, "sourceIdType": source, "targetIdType": target})
    return got.get("value", [])


def _translate(token, ids, end):
    """[(old, permanent)] for these ids, or None when `end` came first. Mail read since permanent ids were asked for already
    has one, and Microsoft refuses the whole request when any id in it is not of the type named (400, "expected:EntryId").
    A refused part is asked once more as permanent ids: answered in full, every id in it is already permanent and is left as
    it is (a mailbox stored after the switch, or rebuilt, costs two requests a portion, not two per email); else it is split in
    halves, a few parts asked at the same moment."""

    def one(part):
        try:
            got = _ask_ids(token, part, "restId", "restImmutableEntryId")
        except _http.Refused as e:
            if e.status != 400:
                raise
            if len(part) == 1:
                return []
            try:
                back = _ask_ids(token, part, "restImmutableEntryId", "restId")
                if len(back) == len(part) and all(x.get("targetId") and not x.get("errorDetails") for x in back):
                    return []
            except _http.Refused as e2:
                if e2.status != 400:
                    raise
            return None
        return [(x["sourceId"], x["targetId"]) for x in got
                if x.get("targetId") and not x.get("errorDetails") and x["targetId"] != x["sourceId"]]

    pairs, waiting = [], [ids] if ids else []
    with ThreadPoolExecutor(DELTA_AT_ONCE) as ex:
        while waiting:
            if time.time() >= end:
                return None
            split = []
            for part, got in zip(waiting, ex.map(one, waiting)):
                if got is None:
                    split += [part[:len(part) // 2], part[len(part) // 2:]]
                else:
                    pairs += got
            waiting = split
    return pairs


def _item(m, folder, kinds):
    """A sync result for one message from a Graph message (or delta entry); folder is where it is when it does not say."""
    pf = m.get("parentFolderId") or folder
    st = {"inbox": pf == kinds.get("inbox"), "trashed": pf == kinds.get("deleteditems")}
    if "isRead" in m:
        st["unread"] = not m["isRead"]
    if m.get("categories") is not None:
        st["labels"] = list(m["categories"])
    if "flag" in m:
        st["starred"] = (m["flag"] or {}).get("flagStatus") == "flagged"
    return {"pid": m["id"], "header": m.get("internetMessageId"), "folders": [pf], "state": st}


DELTA_AT_ONCE = 4               # folders asked at the same moment (Microsoft allows a mailbox about four requests at once)


def _delta(conn, token, end, kinds):
    """Each folder's changes since its stored deltaLink: moves, deletes, read state, categories. A folder's first round walks
    the whole folder (its emails' state is the backfill) a few pages per pass, its place kept as a nextLink. Every folder is
    asked in rounds, a few at the same moment (one after another, a mailbox of many folders spent its whole time on answers
    that held nothing new); the answers are applied in order. At least one round every pass. Returns (changes applied, True
    when every folder is current)."""
    account = conn["address"]
    changed, orphans = 0, []
    folders = [f for f in _store.folders(account) if f["kind"] not in SKIP_KINDS]
    urls, have = {}, _store.cursors(account, "delta:")
    for f in folders:
        cur = json.loads(have.get("delta:" + f["id"]) or "{}")
        urls[f["id"]] = cur.get("next") or cur.get("delta") or f"{GRAPH}/me/mailFolders/{f['id']}/messages/delta?$select={DELTA_SELECT}"

    def ask(fid):
        try:
            return fid, _get(urls[fid], token, extra={"Prefer": DELTA_PREFER}), None
        except _http.Refused as e:
            return fid, None, e

    waiting = [f["id"] for f in folders]
    rounds = 0
    with ThreadPoolExecutor(DELTA_AT_ONCE) as ex:
        while waiting and (time.time() < end or not rounds):
            rounds += 1
            more, places = [], {}
            for fid, page, err in ex.map(ask, waiting):
                scope = "delta:" + fid
                if err is not None:
                    if err.status not in (404, 410):
                        raise err
                    _store.set_cursor(account, scope, None)         # the service forgot this place: the folder is read again
                    _store.db.execute("UPDATE mail_state SET synced_at = NULL WHERE message_id IN"
                                      " (SELECT message_id FROM mail_folder_members WHERE account=? AND folder_id=?)", (account, fid))
                    continue
                items = [{"pid": v["id"], "drop": fid} if "@removed" in v else _item(v, fid, kinds) for v in page.get("value", [])]
                if items:
                    orphans += _store.apply_states(account, items)
                    changed += len(items)
                nxt = page.get("@odata.nextLink")
                places[scope] = json.dumps({"next": nxt} if nxt else {"delta": page.get("@odata.deltaLink")})
                if nxt:
                    urls[fid] = nxt
                    more.append(fid)
            _store.set_cursors(account, places)     # the round's places in one write
            waiting = more
    have = _store.cursors(account, "delta:")
    current = all("delta" in json.loads(have.get("delta:" + f["id"]) or "{}") for f in folders)
    if orphans:                 # left a folder and are in none: moved (the other folder's round may not have run yet) or deleted
        _recheck(token, account, orphans, kinds)
    return changed, current


def _recheck(token, account, pids, kinds):
    def one(pid):
        try:
            return _item(_get(f"{GRAPH}/me/messages/{pid}", token, {"$select": "id,isRead,parentFolderId,categories,internetMessageId,flag"}), None, kinds)
        except _http.Refused as e:
            if e.status == 404:
                return {"pid": pid, "state": {"trashed": True, "inbox": False}, "folders": []}
            raise
    with ThreadPoolExecutor(6) as ex:
        _store.apply_states(account, list(ex.map(one, pids)))


def sync(conn, ctx, end):
    """The slow work, after the new mail of every mailbox is in: ids made permanent (once), changes made elsewhere through
    each folder's delta, the stored mail no folder listed (one by one), then the folder tree with its counts when it is due
    and time is left (it is many requests one after another, so it never comes before the changes). Until `end`. Returns a
    plain line with the seconds of each part."""
    account = conn["address"]
    token = _token(conn)
    took = {}
    at = _store.cursor(account, "folders_at")
    due = not at or dt.datetime.now() - dt.datetime.fromisoformat(at) >= FOLDERS_EVERY
    t0 = time.time()
    if due or not _store.folders(account):      # the folder tree comes first, before the id migration and the time-limited work, so every address gets it every pass
        _folders(conn, token)
        due = False
        took["folders"] = time.time() - t0
    t0 = time.time()
    if not _migrate(account, token, end):
        return "still changing stored ids to permanent ones (the next time I check)" + (f" [folders {took['folders']:.0f}s]" if took.get("folders", 0) >= 1 else "")
    took["ids"] = time.time() - t0
    kinds = _kinds(conn, token)
    t0 = time.time()
    changed, current = _delta(conn, token, end, kinds)
    took["changes"] = time.time() - t0
    read = 0
    t0 = time.time()
    while current and time.time() < end:        # what no folder holds any more: asked of Microsoft one by one
        rows = _store.unsynced(account, 200)
        if not rows:
            break
        _recheck(token, account, [p for _, p in rows], kinds)
        read += len(rows)
    if read:
        took["checked"] = time.time() - t0
    left = len(_store.unsynced(account, 1))
    parts = ", ".join(f"{k} {v:.0f}s" for k, v in took.items() if v >= 1)
    return (f"{changed} changes read" + (f", {read} stored emails checked" if read else "")
            + ("" if current and not left else " (more to read the next time I check)")
            + (f" [{parts}]" if parts else ""))


# --- the envelope catalog (catalog.py): sender, subject and date only; a body only when a look-back needs it ---------------
ENVELOPE_SELECT = "id,subject,from,toRecipients,receivedDateTime,conversationId"


def envelopes(conn, since, cursor, end):
    """One portion of the catalog: pages of messages after `since`, headers only. cursor is Graph's next link."""
    account = conn["address"]
    token = _token(conn)
    rows = []
    url = cursor or (f"{GRAPH}/me/messages?$select={ENVELOPE_SELECT}&$top=500"
                     f"&$filter=receivedDateTime ge {since.isoformat()}T00:00:00Z")
    while url and time.time() < end:
        got = _get(url, token)
        for m in got.get("value", []):
            frm = _addr(m.get("from")).lower()
            ts = _store.local_naive(dt.datetime.strptime(m["receivedDateTime"][:19], "%Y-%m-%dT%H:%M:%S")
                                    .replace(tzinfo=dt.timezone.utc))
            rows.append({"provider_id": m["id"], "ts": ts, "direction": "out" if frm == account else "in", "from_key": frm,
                         "from_name": ((m.get("from") or {}).get("emailAddress") or {}).get("name", ""),
                         "to": [_addr(r).lower() for r in m.get("toRecipients", []) if _addr(r)],
                         "subject": m.get("subject") or "", "thread_id": m.get("conversationId")})
        url = got.get("@odata.nextLink")
    return {"rows": rows, "cursor": url, "done": not url}


def envelope_text(conn, provider_id):
    """One email's plain text, read when a look-back needs it; nothing is stored as a new message."""
    m = _get(f"{GRAPH}/me/messages/{provider_id}", _token(conn), {"$select": "body"})
    return _texts(m)[0]


def address_book(conn):
    """The account's own contacts: [{"name", "emails", "phones"}]. Needs the contacts permission; without it this raises and
    Contacts goes on without this book."""
    token = _token(conn)
    out = []
    url = f"{GRAPH}/me/contacts?$select=displayName,emailAddresses,mobilePhone,businessPhones,homePhones&$top=500"
    while url:
        got = _get(url, token)
        for p in got.get("value", []):
            out.append({"name": p.get("displayName") or "",
                        "emails": [str(e.get("address") or "").lower() for e in p.get("emailAddresses", []) if e.get("address")],
                        "phones": [x for x in [p.get("mobilePhone")] + list(p.get("businessPhones") or []) + list(p.get("homePhones") or []) if x]})
        url = got.get("@odata.nextLink")
    return out


def reload(conn, end):
    """The full history reload's portion for this mailbox: its own step of the pass, after the new mail and the filing, with its
    own time; never part of reading the new mail (connections/run.py --kind email-reload). It waits until the stored ids are
    permanent ones, which the slow work does first."""
    if _store.cursor(conn["address"], "immutable") != "1":
        return "history reload waits until this mailbox's stored ids are permanent (the next few times I check)" if _store.reload_state(conn["address"]) else ""
    token = _token(conn)
    return _reload(token, conn["address"], _kinds(conn, token), end)


RELOAD_PAGE = 25            # emails per portion of the full history reload


def _reload(token, account, kinds, end):
    """The full history reload (Settings, Tools), a portion at a time until `end`: every email in every folder, drafts left
    out. One already held is marked seen (and gains its HTML when it has none kept); any other is stored, paired with its
    stored copy where there is one (_store.MailWriter). Returns the progress line, or "" when no reload was started."""
    st = _store.reload_state(account)
    if not st or st.get("done"):
        return _store.reload_line(st) if st and st.get("done_at", "") >= (dt.datetime.now() - dt.timedelta(days=1)).isoformat() else ""
    started = dt.datetime.fromisoformat(st["started"])
    while True:                 # at least one portion every pass, so the reload always moves on
        url = st.get("page") or f"{GRAPH}/me/messages?$select={SELECT}&$top={RELOAD_PAGE}"
        got = _get(url, token)
        msgs = [m for m in got.get("value", []) if not m.get("isDraft")]
        held = _store.held_ids(account)
        _store.reload_seen_ids(account, [m["id"] for m in msgs if m["id"] in held])
        bare = _store.lacking_html(account, [m["id"] for m in msgs if m["id"] in held])     # stored before its HTML was kept
        for m in msgs:
            if m["id"] in bare:
                _html_only(token, m, account)
        writer = _store.MailWriter(account, reload=started)
        for m in msgs:
            if m["id"] not in held:
                _one(token, m, account, writer, kinds)
        st["new"] += writer.commit()
        st["paired"] += writer.paired
        st["read"] += len(msgs)
        st["page"] = got.get("@odata.nextLink")
        if not st["page"]:
            st = _store.reload_finish(account, st)
            break
        _store.set_reload_state(account, st)
        if time.time() >= end:
            break
    return _store.reload_line(st)


def fetch(conn, provider_ids):
    """Store these emails (found by a search) the same way a pass does. Returns how many were new."""
    token = _token(conn)
    writer = _store.MailWriter(conn["address"])
    folders = _kinds(conn, token)
    for pid in provider_ids:
        m = _get(f"{GRAPH}/me/messages/{pid}", token, {"$select": SELECT})
        if not m.get("isDraft"):
            _one(token, m, conn["address"], writer, folders)
    return writer.commit()


def search(conn, words, most=25):
    """Microsoft's own search over the whole mailbox: the ids of the best matches."""
    q = '"' + str(words).replace('"', " ") + '"'
    got = _get(f"{GRAPH}/me/messages", _token(conn), {"$search": q, "$select": "id", "$top": min(most, 250)})
    return [m["id"] for m in got.get("value", [])][:most]


def labels(conn):
    """The owner's categories (Microsoft's labels), when the sign-in may read them; [] otherwise."""
    try:
        got = _get(f"{GRAPH}/me/outlook/masterCategories", _token(conn))
    except _http.Refused:
        return []
    return sorted((c.get("displayName") for c in got.get("value", []) if c.get("displayName")), key=str.lower)


def headers(conn, provider_id):
    """What a reply or forward needs that a stored email may not hold: its Message-ID, References, Cc and sender's name."""
    m = _get(f"{GRAPH}/me/messages/{provider_id}", _token(conn),
                       {"$select": "internetMessageId,internetMessageHeaders,ccRecipients,from,conversationId"})
    refs = next((h.get("value", "") for h in m.get("internetMessageHeaders") or [] if str(h.get("name")).lower() == "references"), "")
    return {"header_id": m.get("internetMessageId") or "", "refs": " ".join(str(refs).split()),
            "cc": ", ".join(_addr(r) for r in m.get("ccRecipients", [])),
            "from_name": ((m.get("from") or {}).get("emailAddress") or {}).get("name", ""), "thread": m.get("conversationId")}


def unsub_headers(conn, provider_id):
    """The email's List-Unsubscribe and List-Unsubscribe-Post headers ("" when it has none)."""
    m = _get(f"{GRAPH}/me/messages/{provider_id}", _token(conn), {"$select": "internetMessageHeaders"})
    hdrs = {str(h.get("name")).lower(): str(h.get("value") or "") for h in m.get("internetMessageHeaders") or []}
    return {"list": hdrs.get("list-unsubscribe", ""), "post": hdrs.get("list-unsubscribe-post", "")}


def attachment(conn, provider_id, name):
    """One attachment's bytes, by its file name, read from the mail service; None when the email has no such file."""
    got = _get(f"{GRAPH}/me/messages/{provider_id}/attachments", _token(conn))
    for item in got.get("value", []):
        if item.get("name") == name and item.get("contentBytes"):
            return base64.b64decode(item["contentBytes"])
    return None


class NotAllowed(RuntimeError):
    """The sign-in on this computer does not allow changing mail."""


def _change(method, path, token, obj=None):
    try:
        return _http.call_json(method, f"{GRAPH}/me/{path}", token, obj, headers=HDR)[1]
    except _http.Refused as e:
        if e.status in (401, 403):
            raise NotAllowed("this mailbox's sign-in does not allow changing mail yet") from None
        raise


def act(conn, provider_id, what, label=None, thread_id=None):
    """Change one email at the owner's press: archive (moved to the Archive folder), trash (to Deleted Items, never deleted
    for good), junk (to Junk Email), restore (undo: back to the inbox), read, unread, label or unlabel (a category). Microsoft gives a moved email a new id: it is returned."""
    token = _token(conn)
    if what in ("archive", "trash"):
        moved = _change("POST", f"messages/{provider_id}/move", token, {"destinationId": "archive" if what == "archive" else "deleteditems"})
        return moved.get("id") or provider_id
    if what in ("junk", "restore"):     # to the Junk Email folder; restore (undo of archive, trash or junk) back to the inbox
        moved = _change("POST", f"messages/{provider_id}/move", token, {"destinationId": "junkemail" if what == "junk" else "inbox"})
        return moved.get("id") or provider_id
    if what in ("star", "unstar"):
        _change("PATCH", f"messages/{provider_id}", token, {"flag": {"flagStatus": "flagged" if what == "star" else "notFlagged"}})
        return provider_id
    if what == "move":          # label = the destination folder's id; the email keeps its id (immutable ids)
        moved = _change("POST", f"messages/{provider_id}/move", token, {"destinationId": str(label)})
        return moved.get("id") or provider_id
    if what in ("read", "unread"):
        _change("PATCH", f"messages/{provider_id}", token, {"isRead": what == "read"})
        return provider_id
    if what in ("label", "unlabel"):
        have = list(_get(f"{GRAPH}/me/messages/{provider_id}", token, {"$select": "categories"}).get("categories") or [])
        name = str(label or "").strip()
        want = (have + [name]) if what == "label" and name not in have else [c for c in have if c != name]
        _change("PATCH", f"messages/{provider_id}", token, {"categories": want})
        return provider_id
    raise ValueError(f"there is no mail action called {what}")


# --- folders themselves, on the owner's words ------------------------------------------------------------------------------------
FOLDER_DELETE_SAYS = "Outlook moves a deleted folder, with the email in it, to Deleted Items, where it can be taken back until that folder is emptied."


def _fid(folder_id):
    return urllib.parse.quote(str(folder_id), safe="")


def folder_create(conn, name, parent_id=None):
    path = f"mailFolders/{_fid(parent_id)}/childFolders" if parent_id else "mailFolders"
    return (_change("POST", path, _token(conn), {"displayName": name}) or {}).get("id")


def folder_rename(conn, folder_id, name):
    _change("PATCH", f"mailFolders/{_fid(folder_id)}", _token(conn), {"displayName": name})


def folder_move(conn, folder_id, parent_id=None):
    _change("POST", f"mailFolders/{_fid(folder_id)}/move", _token(conn), {"destinationId": str(parent_id) if parent_id else "msgfolderroot"})


def folder_delete(conn, folder_id):
    _change("DELETE", f"mailFolders/{_fid(folder_id)}", _token(conn))


def folder_info(conn, folder_id):
    """{"total": emails in it, "children": folders inside it}."""
    got = _get(f"{GRAPH}/me/mailFolders/{_fid(folder_id)}", _token(conn), {"$select": "totalItemCount,childFolderCount"})
    return {"total": int(got.get("totalItemCount") or 0), "children": int(got.get("childFolderCount") or 0)}


def folder_refresh(conn):
    _folders(conn, _token(conn))


def send_mime(conn, raw, thread_id=None):
    """Send one complete email built by the engine (its own To, Cc, Bcc and reply headers); Microsoft keeps the copy in
    Sent Items and files a reply in its conversation by those headers."""
    _http.post_raw(f"{GRAPH}/me/sendMail", _token(conn), base64.b64encode(raw), "text/plain", ok=(202,))
    return None


def save_draft(conn, raw, thread_id=None, replace=None):
    """Keep one complete email as a draft in this mailbox's Drafts (a draft saved before is replaced). Returns the draft's id."""
    token = _token(conn)
    if replace:
        delete_draft(conn, replace)
    return (_http.post_raw(f"{GRAPH}/me/messages", token, base64.b64encode(raw), "text/plain", ok=(201,))[1] or {}).get("id")


def delete_draft(conn, draft_id):
    try:
        _change("DELETE", f"messages/{urllib.parse.quote(str(draft_id), safe='')}", _token(conn))
    except _http.Refused as e:
        if e.status != 404:
            raise


class NotStarted(RuntimeError):
    """send_reply failed before anything was sent: the caller may send the email another way."""


def send_reply(conn, provider_id, kind, html, to, cc, bcc, files=()):
    """A reply, reply to all or forward made by Outlook itself (createReply, createReplyAll, createForward), so it files in the
    conversation the way Outlook files its own: the draft is given the owner's words, recipients and files, then sent. Anything
    that goes wrong before the send deletes the draft again and raises NotStarted, so nothing half-made stays in Drafts."""
    token = _token(conn)
    verb = {"reply": "createReply", "reply_all": "createReplyAll", "forward": "createForward"}[kind]
    did = None
    try:
        made = _http.post_json(f"{GRAPH}/me/messages/{urllib.parse.quote(str(provider_id), safe='')}/{verb}", token, {}, ok=(200, 201))[1] or {}
        did = made.get("id")
        if not did:
            raise RuntimeError("Outlook did not make the draft")
        rec = lambda xs: [{"emailAddress": {"address": a}} for a in xs]       # noqa: E731
        _change("PATCH", f"messages/{did}", token, {"body": {"contentType": "HTML", "content": html}, "toRecipients": rec(to),
                                                     "ccRecipients": rec(cc), "bccRecipients": rec(bcc)})
        for name, data, ctype in files:
            _http.post_json(f"{GRAPH}/me/messages/{did}/attachments", token,
                            {"@odata.type": "#microsoft.graph.fileAttachment", "name": name, "contentType": ctype,
                             "contentBytes": base64.b64encode(data).decode()}, ok=(201,))
    except Exception as e:
        if did:
            try:
                delete_draft(conn, did)
            except Exception:  # noqa: BLE001
                pass
        raise NotStarted(f"{type(e).__name__}") from None
    _http.post_json(f"{GRAPH}/me/messages/{did}/send", token, {}, ok=(202,))
    return None


def send(conn, to, cc, subject, html, files=()):
    """Send one email; Microsoft keeps the copy in Sent Items. Never a blind copy."""
    attachments = []
    for p in files:
        with open(p, "rb") as f:
            blob = base64.b64encode(f.read()).decode()
        attachments.append({"@odata.type": "#microsoft.graph.fileAttachment", "name": os.path.basename(p),
                            "contentType": mimetypes.guess_type(p)[0] or "application/octet-stream",
                            "contentBytes": blob})
    msg = {"message": {"subject": subject, "body": {"contentType": "HTML", "content": html},
                       "toRecipients": [{"emailAddress": {"address": a}} for a in to],
                       "ccRecipients": [{"emailAddress": {"address": a}} for a in cc],
                       "attachments": attachments},
           "saveToSentItems": True}
    _http.post_json(f"{GRAPH}/me/sendMail", _token(conn), msg, ok=(202,))
    return None


# --- inbox rules (Settings, Mail rules): the rules Outlook runs on its side --------------------------------------------
RULE_READ = ("MailboxSettings.Read", "MailboxSettings.ReadWrite")      # either lets the rules be listed
RULE_WRITE = ("MailboxSettings.ReadWrite",)                            # needed to create or delete one
RULE_NEEDS_ADDRESS = True                 # Outlook's from and to conditions take a full address, not a domain
RULE_CONDS = {"fromAddresses", "subjectContains", "sentToAddresses"}
RULE_ACTS = {"moveToFolder", "markAsRead", "markImportance"}
RULES = "mailFolders/inbox/messageRules"


def _addresses(items):
    return ", ".join(str((x.get("emailAddress") or {}).get("address") or "") for x in items or [])


def rules_list(conn):
    """The inbox rules of this mailbox, each in the terms the page shows: when (from, subject, to), then (move, read, star,
    archive). A rule with anything the page does not show is read only."""
    out = []
    for r in _get(f"{GRAPH}/me/{RULES}", _token(conn)).get("value") or []:
        c, a = r.get("conditions") or {}, r.get("actions") or {}
        extra = [k for k in c if k not in RULE_CONDS and c.get(k)] + [k for k in a if k not in RULE_ACTS and a.get(k)]
        many = any(len(c.get(k) or []) > 1 for k in RULE_CONDS)
        out.append({"id": r.get("id"), "enabled": bool(r.get("isEnabled", True)),
                    "when": {"from": _addresses(c.get("fromAddresses")), "subject": " ".join(c.get("subjectContains") or []),
                             "to": _addresses(c.get("sentToAddresses"))},
                    "then": {"move": a.get("moveToFolder") or None, "read": bool(a.get("markAsRead")),
                             "star": a.get("markImportance") == "high", "archive": False},
                    "read_only": bool(extra) or many or a.get("markImportance") not in (None, "high")})
    return out


def rule_create(conn, spec):
    """One inbox rule from the page's form: spec = {"when": {from, subject, to}, "do": move|archive|read|star, "folder", "name"}.
    Returns the new rule's id."""
    token = _token(conn)
    seq = max([int(r.get("sequence") or 0) for r in _get(f"{GRAPH}/me/{RULES}", token).get("value") or []] or [0]) + 1
    w = spec["when"]
    conds = {}
    if w.get("from"):
        conds["fromAddresses"] = [{"emailAddress": {"address": w["from"]}}]
    if w.get("subject"):
        conds["subjectContains"] = [w["subject"]]
    if w.get("to"):
        conds["sentToAddresses"] = [{"emailAddress": {"address": w["to"]}}]
    acts = {"move": {"moveToFolder": spec.get("folder")}, "archive": {"moveToFolder": spec.get("folder")},
            "read": {"markAsRead": True}, "star": {"markImportance": "high"}}[spec["do"]]
    body = {"displayName": str(spec.get("name") or "Rule from your assistant")[:200], "sequence": seq, "isEnabled": True,
            "conditions": conds, "actions": acts}
    return (_change("POST", RULES, token, body) or {}).get("id")


def rule_delete(conn, rule_id):
    _change("DELETE", RULES + "/" + urllib.parse.quote(str(rule_id), safe=""), _token(conn))


# --- meeting invites (invites.py) ----------------------------------------------------------------------------------------
class NotFound(RuntimeError):
    """The meeting is not on the account's calendar."""


def invite_source(conn, provider_id):
    """The meeting request this email is (an eventMessage with meetingMessageType), read with its event, or None."""
    import invites
    token = _token(conn)
    m = _get(f"{GRAPH}/me/messages/{provider_id}", token, {"$expand": "microsoft.graph.eventMessage/event"})
    if "meetingMessageType" not in m:
        return None
    return invites.from_event(m)


def invite_answer(conn, inv, answer, note=""):
    """accept, tentativelyAccept or decline on the related event, with the organizer told (sendResponse) and the owner's note as the comment."""
    verb = {"accept": "accept", "tentative": "tentativelyAccept", "decline": "decline"}[answer]
    if not inv.get("event_id"):
        raise NotFound("no event")
    try:
        _http.call_json("POST", f"{GRAPH}/me/events/{inv['event_id']}/{verb}", _token(conn), {"comment": note, "sendResponse": True}, headers=HDR)
    except _http.Refused as e:
        if e.status in (401, 403):
            raise NotAllowed("this mailbox's sign-in does not allow answering invites yet") from None
        if e.status == 404:
            raise NotFound("not on the calendar") from None
        raise
