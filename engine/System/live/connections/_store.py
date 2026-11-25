r"""Putting what a connection read into the database, the same way for every connection.

A connection type fetches; these writers store. They hold the rules that keep
the database clean whatever the source: no message stored twice, signature
pictures left out, every time in local wall time.

    since(name, days)          how far back to read: the watermark kept under this name, or `days` ago
    MailWriter(account)        .add(...) each message, then .commit()
    chat_messages(...)         chat-style messages (one row each)
    calendar_events(...)       the rolling window of events
    text_messages(...)         phone texts, with their pictures
"""
import datetime as dt
import hashlib
import os
import re
import sys
import time

import duckdb

LIVE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (LIVE, os.path.join(LIVE, "core")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import db  # noqa: E402
import paths  # noqa: E402
from fingerprint import fingerprint  # noqa: E402

DEDUP_WINDOW = dt.timedelta(days=2)

# --- signature clutter ----------------------------------------------------------
# Signature logos, social icons and spacers arrive as real attachments; they are never kept.
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".ico")
INLINE_NAME = re.compile(r"^(image\d{3,}|Outlook-[a-z0-9]{8})\.(png|jpe?g|gif)$", re.I)
DECOR_WORDS = re.compile(
    r"(logo|signature|sig[-_]?\d|icon|banner|spacer|footer|header|social|"
    r"facebook|twitter|linkedin|instagram|badge|divider)", re.I)
TINY_IMAGE_BYTES = 25_000
DECOR_MAX_BYTES = 200_000       # bigger than this is real content pasted into a thread, never furniture
# The first copy of a picture in a message body is kept and read; a repeat is furniture.
SEEN_INLINE = os.path.join(paths.STATE, "inline_images_seen.txt")


def _sha(content):
    return hashlib.sha256(content).hexdigest()


def _seen_inline():
    try:
        with open(SEEN_INLINE, encoding="utf-8") as f:
            return {ln.strip() for ln in f if ln.strip()}
    except FileNotFoundError:
        return set()


def mark_seen(contents):
    new = {_sha(c) for c in contents} - _seen_inline()
    if new:
        os.makedirs(os.path.dirname(SEEN_INLINE), exist_ok=True)
        with open(SEEN_INLINE, "a", encoding="utf-8") as f:
            f.write("".join(h + "\n" for h in sorted(new)))


def is_decoration(name, size, inline, content=None):
    """True for signature furniture that should never be kept or judged."""
    ext = os.path.splitext(name or "")[1].lower()
    if ext not in IMAGE_EXT:
        return False                     # only ever discards images
    if size and size > DECOR_MAX_BYTES:
        return False
    if inline:
        if (size or 0) < TINY_IMAGE_BYTES or DECOR_WORDS.search(name or ""):
            return True
        return content is not None and _sha(content) in _seen_inline()
    if INLINE_NAME.match(name or ""):
        return True
    if DECOR_WORDS.search(name or ""):
        return True
    return bool(size) and size < TINY_IMAGE_BYTES


# --- shared helpers ---------------------------------------------------------------
def _not_now():
    """True while the day-by-day rebuild runs and this is another program (the page's Refresh, a search, the texts link):
    nothing is stored beside the replay, so its days are read in order (replay_guard)."""
    import replay_guard
    return replay_guard.import_blocked()


def since(name, days=30):
    """Where a source was last read up to, or `days` ago when it has never been read. Reading back sets
    ASSISTANT_READ_SINCE: then every source reads from that date, whatever it has read before."""
    forced = os.environ.get("ASSISTANT_READ_SINCE")
    if forced:
        try:
            return dt.datetime.fromisoformat(forced)
        except ValueError:
            pass
    return db.watermark(name) or dt.datetime.now() - dt.timedelta(days=days)


def local_naive(value):
    """Every time in the database is local wall time, stored without a zone."""
    if isinstance(value, dt.datetime) and value.tzinfo is not None:
        return value.astimezone().replace(tzinfo=None)
    return value


# --- mail ---------------------------------------------------------------------------
class MailWriter:
    """Buffers one mailbox's batch, then commits: no duplicates, attachments saved, watermark moved.

    A message already held is matched three ways: the provider's own id, the same content within
    two days (the same mail fetched two ways), and the same sender, subject and minute."""

    def __init__(self, account, dry_run=False, reload=None):
        self.account = account
        self.dry_run = dry_run
        self.rows = []
        self.skipped_id = 0
        self.skipped_fp = 0
        self.reload = reload            # the full history reload (its start time): pair with stored mail, never a loose match
        self.paired = 0

    def add(self, provider_id, ts, direction, from_addr, to_addrs, subject, body,
            folder=None, thread_id=None, attachments=None, state=None, html=None):
        """body: the email's plain text (what the assistant reads). html: its own HTML as sent, kept for the Mail page only.
        attachments: [(file name, bytes)] or [(file name, bytes, content id)] for a picture shown in the HTML, already
        filtered with is_decoration. state (optional): what the service says about the email, {"unread", "inbox", "trashed",
        "labels": [names], "cc": "a, b", "from_name", "header_id", "refs"}; it is kept in mail_state, and refreshed for an
        email already held (which also gains its HTML when it has none)."""
        self.rows.append({"state": state or None, "html": html or None,
            "provider_id": provider_id, "ts": ts, "direction": direction,
            "from_addr": (from_addr or "").lower(), "to_addrs": to_addrs or "",
            "subject": subject or "", "body": body or "", "folder": folder,
            "thread_id": thread_id, "attachments": attachments or [],
            "fp": fingerprint(self.account, from_addr, subject, body),
        })

    def commit(self):
        if not self.rows or _not_now():
            return 0
        os.makedirs(paths.ATTACHMENTS, exist_ok=True)
        con = db.connect()
        try:
            existing_ids = {r[0] for r in con.execute(
                "SELECT provider_id FROM messages WHERE channel='email' AND account=? UNION SELECT provider_id FROM mail_state"
                " WHERE account=? AND provider_id IS NOT NULL", [self.account, self.account]).fetchall()}
            people = dict(con.execute("SELECT key, person_id FROM contacts").fetchall())
            written = 0
            for r in self.rows:
                if r["provider_id"] in existing_ids:
                    self.skipped_id += 1
                    if r["state"] and not self.dry_run:
                        held = find_email(con, self.account, r["provider_id"], also_old=True)
                        if held:
                            put_state(con, held, self.account, r["provider_id"], r["state"], r["state"].get("folders"))
                            if self.reload:
                                _seen(con, held)
                    if r["html"] and not self.dry_run:
                        held = find_email(con, self.account, r["provider_id"], also_old=True)
                        if held and not has_html(con, held):
                            _put_html(con, held, r["html"], _cids_by_name(con, held, r["attachments"]))
                    continue
                if self.reload and not self.dry_run:
                    held = _pair(con, self.account, r, self.reload)
                    if held is not None:            # the stored copy keeps its row (attachments, documents, cards point at it)
                        put_state(con, held, self.account, r["provider_id"], dict(r["state"] or {}, synced=True),
                                  (r["state"] or {}).get("folders"))
                        con.execute("UPDATE mail_state SET provider_id=?, unmatched_at=NULL, server_gone=NULL WHERE message_id=?",
                                    [r["provider_id"], held])
                        _seen(con, held)
                        if r["html"]:
                            _put_html(con, held, r["html"], _cids_by_name(con, held, r["attachments"]))
                        existing_ids.add(r["provider_id"])
                        self.paired += 1
                        continue
                # Mail with no body (scans from a copier share one subject) relies on the id alone. A reload stores what
                # pairing did not find: no loose match drops it.
                if r["body"].strip() and not self.reload:
                    near = con.execute(
                        "SELECT count(*) FROM messages WHERE channel='email' AND account=?"
                        " AND fingerprint=? AND abs(epoch(ts - ?)) < ?",
                        [self.account, r["fp"], r["ts"], DEDUP_WINDOW.total_seconds()]).fetchone()[0]
                    if near:
                        self.skipped_fp += 1
                        continue
                envelope = 0 if self.reload else con.execute(
                    "SELECT count(*) FROM messages WHERE channel='email' AND account=?"
                    " AND coalesce(from_key,'') = ? AND coalesce(subject,'') = ?"
                    " AND abs(epoch(ts - ?)) < 60",
                    [self.account, f"email:{r['from_addr']}" if r["from_addr"] else "",
                     r["subject"] or "", r["ts"]]).fetchone()[0]
                if envelope:
                    self.skipped_fp += 1
                    continue
                if self.dry_run:
                    written += 1
                    continue
                fk = f"email:{r['from_addr']}" if r["from_addr"] else None
                mid = con.execute(
                    "INSERT INTO messages (channel, account, provider_id, thread_id,"
                    " folder, ts, direction, from_key, to_keys, person_id, subject, body,"
                    " fingerprint, ingested_at) VALUES ('email',?,?,?,?,?,?,?,?,?,?,?,?,?)"
                    " RETURNING id",
                    (self.account, r["provider_id"], r["thread_id"], r["folder"],
                     r["ts"], r["direction"], fk, r["to_addrs"], people.get(fk),
                     r["subject"], r["body"], r["fp"], dt.datetime.now())).fetchone()[0]
                existing_ids.add(r["provider_id"])
                if r["state"]:
                    put_state(con, mid, self.account, r["provider_id"], r["state"], r["state"].get("folders"))
                    if self.reload:
                        _seen(con, mid)
                if self.reload and r["ts"] < self.reload - dt.timedelta(days=1):    # old mail from the reload: history, not news
                    con.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES ('judged', ?, 'ignore',"
                                " 'history reload: old mail', ?) ON CONFLICT (domain, key) DO NOTHING", [f"msg:{mid}", dt.datetime.now()])
                cids = {}
                for att in r["attachments"]:
                    name, content = att[0], att[1]
                    safe = "".join(c for c in (name or "file") if c.isalnum() or c in "._- ")
                    saved = f"{r['ts']:%Y%m%d}_{mid}_{safe}"
                    path = os.path.join(paths.ATTACHMENTS, saved)
                    if os.path.exists(path):        # same-named attachments in one mail each keep a file
                        stem, ext = os.path.splitext(saved)
                        n = 2
                        while os.path.exists(os.path.join(paths.ATTACHMENTS, f"{stem}_{n}{ext}")):
                            n += 1
                        saved = f"{stem}_{n}{ext}"
                        path = os.path.join(paths.ATTACHMENTS, saved)
                    with open(path, "wb") as f:
                        f.write(content)
                    if os.path.splitext(saved)[1].lower() in IMAGE_EXT:
                        mark_seen([content])
                    aid = con.execute(
                        "INSERT INTO attachments (message_id, original_filename,"
                        " saved_filename, saved_path, saved_at) VALUES (?,?,?,?,?) RETURNING id",
                        (mid, name, saved, path, dt.datetime.now())).fetchone()[0]
                    if len(att) > 2 and att[2]:
                        cids[att[2]] = f"att:{aid}"
                if r["html"]:
                    _put_html(con, mid, r["html"], cids)
                written += 1
        finally:
            con.close()
        if not self.dry_run:
            # the mark moves to the newest email FETCHED (not only stored), so a duplicate never holds it back; the callers fetch
            # oldest first and stop at the cap, so everything not fetched is newer than the mark and comes next pass
            db.set_watermark(f"email:{self.account}", max(r["ts"] for r in self.rows))
        return written


# --- an email's own HTML (the Mail page shows it as sent; the assistant reads messages.body) -----------------------------
def html_text(markup):
    """The plain text of an email that came only as HTML: every word and link kept (the readers clip it themselves)."""
    from cleantext import clean_body
    return clean_body(markup or "", limit=10**9, keep_links=10**6)


def has_html(con, message_id):
    return bool(con.execute("SELECT 1 FROM mail_html WHERE message_id=?", [message_id]).fetchone())


def _put_html(con, message_id, markup, cids):
    import json
    con.execute("INSERT OR REPLACE INTO mail_html VALUES (?,?,?,?)",
                [message_id, markup, json.dumps(cids or {}), dt.datetime.now()])


def _cids_by_name(con, message_id, attachments):
    """{content id: "att:N"} for a stored email's pictures, matched to its own stored attachments by file name, in order."""
    rows = con.execute("SELECT id, original_filename FROM attachments WHERE message_id=? ORDER BY id", [message_id]).fetchall()
    out, used = {}, set()
    for att in attachments or []:
        if len(att) < 3 or not att[2]:
            continue
        for aid, name in rows:
            if aid not in used and name == att[0]:
                out[att[2]] = f"att:{aid}"
                used.add(aid)
                break
    return out


def lacking_html(account, pids):
    """Of these stored emails (current provider ids), the ones with no HTML kept yet."""
    with db.connect(read_only=True) as con:
        return {p for p in pids if (mid := find_email(con, account, p)) is not None and not has_html(con, mid)}


def put_html(account, pid, markup, attachments=()):
    """Keep a stored email's HTML (read again by the history reload); its pictures are matched to its stored attachments.
    attachments: [(file name, bytes or None, content id)]."""
    with db.transaction() as con:
        mid = find_email(con, account, pid)
        if mid is not None and markup:
            _put_html(con, mid, markup, _cids_by_name(con, mid, attachments))


STATE_FIELDS = ("unread","inbox", "trashed", "starred", "labels", "cc", "from_name", "header_id", "refs")


def put_state(con, message_id, account, provider_id, state, folders=None):
    """Write what the service says about one stored email. A field the service did not give keeps its last value.
    state["synced"] stamps the email as read from the service just now; folders (ids) replaces its folder membership."""
    import json
    st = {k: state.get(k) for k in STATE_FIELDS if state.get(k) is not None}
    if "labels" in st:
        st["labels"] = json.dumps([str(x) for x in st["labels"]][:50], ensure_ascii=False)
    now = dt.datetime.now()
    if state.get("synced"):
        st["synced_at"] = now
    if con.execute("SELECT count(*) FROM mail_state WHERE message_id=?", [message_id]).fetchone()[0]:
        if st:
            con.execute("UPDATE mail_state SET " + ", ".join(f"{k}=?" for k in st) + ", updated_at=? WHERE message_id=?",
                        list(st.values()) + [now, message_id])
    else:
        con.execute("INSERT INTO mail_state (message_id, account, provider_id, " + ", ".join(st) + (", " if st else "") + "updated_at)"
                    " VALUES (" + ", ".join("?" for _ in range(3 + len(st) + 1)) + ")",
                    [message_id, account, provider_id] + list(st.values()) + [now])
    if folders is not None:
        put_members(con, message_id, account, folders)


def put_members(con, message_id, account, folder_ids):
    con.execute("DELETE FROM mail_folder_members WHERE message_id=?", [message_id])
    for f in dict.fromkeys(str(x) for x in folder_ids):
        con.execute("INSERT INTO mail_folder_members VALUES (?,?,?)", [message_id, account, f])


# --- the mail sync's own records: cursors, folders, what is held and what still needs reading ---------------------------
SYNC_SECONDS = 60               # the slow work (changes made elsewhere, the backfill) a pass may spend on all mailboxes together;
                                # the step's own limit (limits.SYNC, 120) leaves room for the parts that cannot stop midway


def cursor(account, scope):
    r = db.query("SELECT cursor FROM mail_cursors WHERE account=? AND scope=?", (account, scope))
    return r[0][0] if r else None


def set_cursor(account, scope, value):
    db.execute("INSERT OR REPLACE INTO mail_cursors VALUES (?,?,?,?)", (account, scope, value, dt.datetime.now()))


def cursors(account, prefix):
    """{scope: value} of one mailbox's places whose scope starts with prefix, in one read."""
    return dict(db.query("SELECT scope, cursor FROM mail_cursors WHERE account=? AND starts_with(scope, ?)", (account, prefix)))


def set_cursors(account, values):
    """Several of one mailbox's places at once ({scope: value}), in one write."""
    if not values:
        return
    now = dt.datetime.now()
    with db.transaction() as con:
        for scope, value in values.items():
            con.execute("INSERT OR REPLACE INTO mail_cursors VALUES (?,?,?,?)", [account, scope, value, now])


def find_email(con, account, provider_id, also_old=False):
    """The stored email (its message id) whose current provider id this is: kept in mail_state, which follows the service
    when an id changes, else the one it was stored under (messages.provider_id, never changed: other tables point at that
    row, and the database cannot change an indexed column of a row that is pointed at). also_old: an id it had before counts
    too (translating ids, or an email arriving again under an old id). None when not held."""
    r = con.execute("SELECT m.id FROM messages m LEFT JOIN mail_state s ON s.message_id = m.id WHERE m.channel='email' AND m.account=?"
                    " AND coalesce(s.provider_id, m.provider_id)=?", [account, provider_id]).fetchone()
    if r or not also_old:
        return r[0] if r else None
    r = con.execute("SELECT id FROM messages WHERE channel='email' AND account=? AND provider_id=?", [account, provider_id]).fetchone()
    return r[0] if r else None


def held_ids(account):
    return {r[0] for r in db.query("SELECT provider_id FROM messages WHERE channel='email' AND account=? UNION SELECT provider_id"
                                   " FROM mail_state WHERE account=? AND provider_id IS NOT NULL", (account, account))}


def unsynced(account, limit):
    """[(message id, provider id)] of stored email not yet read from the service, newest first."""
    return db.query("SELECT m.id, coalesce(s.provider_id, m.provider_id) FROM messages m LEFT JOIN mail_state s ON s.message_id = m.id"
                    " WHERE m.channel='email' AND m.account=? AND m.provider_id IS NOT NULL AND s.synced_at IS NULL AND s.unmatched_at IS NULL"
                    " ORDER BY m.ts DESC LIMIT ?", (account, limit))


def reset_synced(account):
    db.execute("UPDATE mail_state SET synced_at = NULL WHERE account=?", (account,))


def put_folders(account, rows):
    """Replace the mailbox's folder list. rows: dicts id, path, parent, kind, unread, total."""
    now = dt.datetime.now()
    with db.transaction() as con:
        con.execute("DELETE FROM mail_folders WHERE account=?", [account])
        for r in rows:
            con.execute("INSERT INTO mail_folders VALUES (?,?,?,?,?,?,?,?)",
                        [account, r["id"], r.get("path"), r.get("parent"), r.get("kind") or "folder", r.get("unread"), r.get("total"), now])


def folders(account):
    return [dict(zip(("id", "path", "parent", "kind", "unread", "total"), r)) for r in db.query(
        "SELECT folder_id, path, parent_id, kind, unread, total FROM mail_folders WHERE account=? ORDER BY path", (account,))]


def apply_states(account, items):
    """One short write for a portion of sync results. items: dicts {pid, state (put_state's), folders (ids or None),
    header (the Message-ID, to match an email whose id changed), drop (a folder id the email left)}. An email is found by its
    provider id, else by its Message-ID header (its id then follows the service's). Returns the provider ids of emails that
    left a folder and are now in none: the caller asks the service where they went."""
    orphans = []
    if not items:
        return orphans
    with db.transaction() as con:
        # the portion's ids and headers are looked up in two queries, not two per email: a first walk of a large mailbox is
        # mostly email that is not stored, and asking for each one alone took seconds a portion
        ids = dict(con.execute("SELECT coalesce(s.provider_id, m.provider_id), m.id FROM messages m LEFT JOIN mail_state s ON s.message_id = m.id"
                               " WHERE m.channel='email' AND m.account=? AND coalesce(s.provider_id, m.provider_id) IN (SELECT unnest(?))",
                               [account, [str(it["pid"]) for it in items]]).fetchall())
        heads = [str(it["header"]) for it in items if it.get("header")]
        heads = dict(con.execute("SELECT s.header_id, m.id FROM messages m JOIN mail_state s ON s.message_id = m.id WHERE m.channel='email'"
                                 " AND m.account=? AND s.header_id IN (SELECT unnest(?))", [account, heads]).fetchall()) if heads else {}
        for it in items:
            held = ids.get(it["pid"])
            row = (held,) if held else None
            if not row and it.get("header") in heads:
                row = (heads[it["header"]],)    # its id changed at the service: the current id is kept beside it, the stored row never changes
                con.execute("UPDATE mail_state SET provider_id=? WHERE message_id=?", [it["pid"], row[0]])
                ids[it["pid"]] = row[0]
            if not row:
                continue
            if it.get("drop"):
                con.execute("DELETE FROM mail_folder_members WHERE message_id=? AND folder_id=?", [row[0], it["drop"]])
                if not con.execute("SELECT count(*) FROM mail_folder_members WHERE message_id=?", [row[0]]).fetchone()[0]:
                    orphans.append(it["pid"])
                continue
            put_state(con, row[0], account, it["pid"], dict(it.get("state") or {}, synced=True), it.get("folders"))
    return orphans


def remap_ids(account, pairs):
    """Stored emails' ids changed at the service (old, new): the new one becomes the current id, in mail_state; the
    messages row keeps the id it was stored under (find_email finds it by either). One already held under the new id is left.
    Returns the pairs that were applied."""
    done = []
    with db.transaction() as con:
        for old, new in pairs:
            mid = find_email(con, account, old, also_old=True)
            if mid is None or find_email(con, account, new, also_old=True) is not None:
                continue
            if con.execute("SELECT 1 FROM mail_state WHERE message_id=?", [mid]).fetchone():
                con.execute("UPDATE mail_state SET provider_id=? WHERE message_id=?", [new, mid])
            else:
                put_state(con, mid, account, new, {})
            done.append((old, new))
    return done


def header_ids(account, pids):
    """{current id: its Message-ID header} of these stored emails, where one is kept."""
    with db.connect(read_only=True) as con:
        out = {}
        for pid in pids:
            mid = find_email(con, account, pid)
            r = con.execute("SELECT header_id FROM mail_state WHERE message_id=?", [mid]).fetchone() if mid is not None else None
            if r and r[0]:
                out[pid] = r[0]
        return out


def mark_unmatched(account, pids):
    """Stored emails under ids the service does not know, that it could not find by their Message-ID either: set aside, so
    the backfill does not ask for them every pass."""
    now = dt.datetime.now()
    with db.transaction() as con:
        for pid in pids:
            mid = find_email(con, account, pid)
            if mid is None:
                continue
            if not con.execute("SELECT 1 FROM mail_state WHERE message_id=?", [mid]).fetchone():
                put_state(con, mid, account, pid, {})
            con.execute("UPDATE mail_state SET unmatched_at=? WHERE message_id=?", [now, mid])


def members(con, message_id):
    return [r[0] for r in con.execute("SELECT folder_id FROM mail_folder_members WHERE message_id=?", [message_id]).fetchall()]


def folder_of(con, account, folder_id):
    r = con.execute("SELECT path, kind FROM mail_folders WHERE account=? AND folder_id=?", [account, folder_id]).fetchone()
    return {"path": r[0], "kind": r[1]} if r else None


def mail_flags(account, inbox_ids, unread_ids, since_ts):
    """A pass's light refresh of one mailbox: of its emails stored since since_ts, those whose provider id is in
    inbox_ids are in the inbox and the rest are not; the same for unread. Returns how many rows changed."""
    inbox_ids, unread_ids = set(inbox_ids), set(unread_ids)
    con = db.connect()
    try:
        rows = con.execute("SELECT m.id, coalesce(s.provider_id, m.provider_id), s.inbox, s.unread, s.trashed FROM messages m LEFT JOIN mail_state s ON s.message_id = m.id"
                           " WHERE m.channel='email' AND m.account=? AND m.ts >= ?", [account, since_ts]).fetchall()
        n = 0
        for mid, pid, inbox, unread, trashed in rows:
            want = {"inbox": pid in inbox_ids, "unread": pid in unread_ids}
            if trashed and not want["inbox"]:
                want.pop("inbox")
            if (inbox, unread) != (want.get("inbox", inbox), want["unread"]):
                put_state(con, mid, account, pid, want)
                n += 1
        return n
    finally:
        con.close()


# --- chat ---------------------------------------------------------------------------
def chat_messages(channel, account, rows, watermark_name):
    """rows: dicts with provider_id, thread_id, ts, direction, from_key, where (the room or person,
    shown as the subject), text. Returns (written, already held)."""
    if _not_now():
        return 0, 0
    written = skipped = 0
    newest = None
    con = db.connect()
    try:
        known = {r[0] for r in con.execute("SELECT provider_id FROM messages WHERE channel=?", [channel]).fetchall()}
        people = dict(con.execute("SELECT key, person_id FROM contacts").fetchall())
        for r in sorted(rows, key=lambda x: x["ts"]):
            if not r.get("provider_id") or r["provider_id"] in known:
                skipped += 1
                continue
            con.execute(
                "INSERT INTO messages (channel, account, provider_id, thread_id,"
                " ts, direction, from_key, person_id, subject, body, ingested_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (channel, account, r["provider_id"], r.get("thread_id"), r["ts"], r["direction"],
                 r.get("from_key"), people.get(r.get("from_key")), r.get("where"), r.get("text") or "",
                 dt.datetime.now()))
            known.add(r["provider_id"])
            written += 1
            newest = r["ts"] if newest is None else max(newest, r["ts"])
        if newest:
            db.set_watermark(watermark_name, newest, con=con)
    finally:
        con.close()
    return written, skipped


# --- calendar -------------------------------------------------------------------------
def calendar_events(rows, prune):
    """rows: (event id, calendar name, summary, start, end, all day, location, description, updated[, his own answer to an
    invitation]). The table is a rolling window: with prune, what no calendar returned this time is dropped, in
    the same transaction, so a failed read leaves the last window in place."""
    if _not_now():
        return
    now = dt.datetime.now()
    with db.transaction() as con:
        con.execute("ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS my_response VARCHAR")
        con.execute("CREATE TEMP TABLE fetched (event_id VARCHAR)")
        if rows:
            con.executemany(
                "INSERT OR REPLACE INTO calendar_events (event_id, calendar, summary, start_ts, end_ts,"
                " all_day, location, description, updated_at, my_response, synced_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [tuple(r[:9]) + ((r[9] if len(r) > 9 else None), now) for r in rows])
            con.executemany("INSERT INTO fetched VALUES (?)", [(r[0],) for r in rows])
        if prune:
            con.execute("DELETE FROM calendar_events WHERE event_id NOT IN (SELECT event_id FROM fetched)")
        db.set_watermark("calendar", now, con=con)


# --- phone texts ------------------------------------------------------------------------
TEXT_DEDUP_SECONDS = 120
NO_TEXT = "[media message, no text]"
MEDIA_DIR = os.path.join(paths.ATTACHMENTS, "Texts")
MIN_FILE_BYTES = 2048        # smaller than this is an icon or stub, not a document
FILL_SECONDS = 60            # a text from the texts link is the same text stored before the link within this long
filled = [0]                 # pictures filled into texts stored before the link, since this program started (the link's log reads it)
upgraded = [0, 0, 0]         # pictures replaced by their full size since this program started: how many, bytes before, bytes after


def words(text):
    """A text's words as compared with another's: spaces, tabs and line breaks collapsed to one space (a backup and Google
    Messages keep the same text with different spacing)."""
    return " ".join(str(text or "").split())


SQL_WORDS = "regexp_replace(trim(coalesce(body, '')), '\\s+', ' ', 'g')"     # words(), in the database


def phone_key(number):
    digits = "".join(ch for ch in str(number or "") if ch.isdigit())
    if len(digits) >= 10:
        return "phone:" + digits[-10:]
    return "sms:" + (number or "unknown")


class Deferred(Exception):
    """The database could not be had for a write: what was stored before is kept, `rest` is what still has to be stored."""
    def __init__(self, rest, counts):
        super().__init__("database busy")
        self.rest, self.counts = rest, counts


TEXT_CHUNK = 20         # texts stored per write connection: each is a short transaction, so a pass never waits long for the database
TEXT_PAUSE = 1.5        # the database is let go for this long between two chunks, so a pass waiting for it gets in


def text_messages(rows):
    """rows: dicts with provider_id, thread, ts, direction, key (the other person's phone key), name, optional subject,
    text, media [(kind, file name, bytes, describable)]. Returns (written, already held, pictures queued
    to be described). A picture is stored as file -> attachment -> document -> a page waiting to be read.
    Everything that needs reading is read first, on one short read connection, and the checking is done in memory; the writing then
    goes in small transactions (TEXT_CHUNK texts each) on a connection opened and closed for each, so the database is never held
    for long. Raises Deferred (with what is left to store) when it cannot be had for a write."""
    if _not_now():
        return 0, 0, 0
    written = skipped = queued = 0
    now = dt.datetime.now()
    os.makedirs(MEDIA_DIR, exist_ok=True)
    last = {}                           # a text handed over again in the same batch (its placeholder, its thumbnail, its full picture): its full
    for r in rows:                      # picture, else one with its picture, else the last
        had = last.get(r["provider_id"])
        if had is None or (bool(r.get("full")), bool(r.get("media"))) >= (bool(had.get("full")), bool(had.get("media"))):
            last[r["provider_id"]] = r
    rows = sorted(last.values(), key=lambda x: x["ts"])
    fulls = {r["provider_id"] for r in rows if r.get("full")}
    con = db.connect(read_only=True)
    try:
        known = {r[0] for r in con.execute("SELECT provider_id FROM messages WHERE channel='sms'").fetchall()}
        people = dict(con.execute("SELECT key, person_id FROM contacts").fetchall())
        again = [r["provider_id"] for r in rows if r["provider_id"] in known and r.get("media")]
        bare = {}                       # a text handed over again with its picture (sent before the picture was ready): filled, once
        for i in range(0, len(again), 200):
            part = again[i:i + 200]
            for pid, mid, ts in con.execute(
                    "SELECT m.provider_id, m.id, m.ts FROM messages m WHERE m.channel='sms' AND m.provider_id IN (" + ",".join("?" for _ in part)
                    + ") AND NOT EXISTS (SELECT 1 FROM attachments a WHERE a.message_id = m.id)", part).fetchall():
                bare[pid] = (mid, ts)
        full = [pid for pid in again if pid not in bare and pid in fulls]
        stored = {}                     # a text held with its pictures that comes again with them at full size: [(attachment, file)]
        for i in range(0, len(full), 200):
            part = full[i:i + 200]
            for pid, aid, path in con.execute(
                    "SELECT m.provider_id, a.id, a.saved_path FROM attachments a JOIN messages m ON m.id = a.message_id WHERE m.channel='sms' "
                    "AND m.provider_id IN (" + ",".join("?" for _ in part) + ") ORDER BY a.id", part).fetchall():
                stored.setdefault(pid, []).append((aid, path))
        linked = [r for r in rows if str(r["provider_id"]).startswith("gl:") and r["provider_id"] not in known]
        older = []
        if linked:                      # texts stored before the link, around the link's ones: the same text is filled, never stored twice
            older = con.execute(
                "SELECT m.id, m.ts, m.direction, coalesce(m.body, ''), m.person_id, m.thread_id, "
                "(SELECT count(*) FROM attachments a WHERE a.message_id = m.id) FROM messages m WHERE m.channel='sms' "
                "AND m.provider_id NOT LIKE 'gl:%' AND m.ts BETWEEN ? AND ?",
                [min(r["ts"] for r in linked) - dt.timedelta(seconds=FILL_SECONDS),
                 max(r["ts"] for r in linked) + dt.timedelta(seconds=FILL_SECONDS)]).fetchall()
        said = sorted({words(r["text"]) for r in rows if r["text"] != NO_TEXT})
        same = {}
        for i in range(0, len(said), 200):
            part = said[i:i + 200]
            for d, body, ts in con.execute(f"SELECT direction, {SQL_WORDS}, ts FROM messages WHERE channel='sms' AND {SQL_WORDS} IN ("
                                           + ",".join("?" for _ in part) + ")", part).fetchall():
                same.setdefault((d, body), []).append(ts)
    finally:
        con.close()
    plan, filling = [], set()
    for r in rows:
        if r["provider_id"] in known:
            skipped += 1
            if r["provider_id"] in bare and r["provider_id"] not in filling:
                mid, ts = bare[r["provider_id"]]
                filling.add(r["provider_id"])
                plan.append({"fill": mid, "provider_id": r["provider_id"], "ts": ts, "media": r["media"]})
            elif r["provider_id"] in stored and r.get("full") and r["provider_id"] not in filling:
                filling.add(r["provider_id"])
                _upgrade(r["media"], stored[r["provider_id"]])
            continue
        known.add(r["provider_id"])
        hit = _older(r, older, people) if older and str(r["provider_id"]).startswith("gl:") else None
        if hit is not None:             # held already, from before the link: its picture is filled in when it has none
            skipped += 1
            if r.get("media") and not hit[6] and hit[0] not in filling:
                filling.add(hit[0])
                plan.append({"fill": hit[0], "provider_id": r["provider_id"], "ts": hit[1], "media": r["media"]})
            continue
        if r["text"] != NO_TEXT:
            seen = same.setdefault((r["direction"], words(r["text"])), [])
            if any(abs((t - r["ts"]).total_seconds()) < TEXT_DEDUP_SECONDS for t in seen):
                skipped += 1
                continue
            seen.append(r["ts"])
        plan.append(r)
    for i in range(0, len(plan), TEXT_CHUNK):
        part = plan[i:i + TEXT_CHUNK]
        try:
            con = db.connect(retries=3)
        except (TimeoutError, duckdb.Error) as e:
            raise Deferred(plan[i:], (written, skipped, queued)) from e
        try:
            con.execute("PRAGMA disable_checkpoint_on_shutdown")      # closing would rewrite the big file for a few seconds with the database held; the log is replayed by the next open and checkpointed by whoever closes after a big write
            con.execute("BEGIN TRANSACTION")
            try:
                got = _store_texts(con, part, people, now)
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
            written += got[0]
            queued += got[1]
        finally:
            con.close()
        if i + TEXT_CHUNK < len(plan):
            time.sleep(TEXT_PAUSE)
    return written, skipped, queued


def _older(r, older, people):
    """The text stored before the link that this one from the link is: the same direction, within FILL_SECONDS, the same person
    (or a thread matched to the link's conversation), and the same words, or a picture's placeholder. The nearest, or None."""
    pid = people.get(r["key"]) if r.get("key") else None
    also = set(r.get("older_threads") or ())
    best = None
    for row in older:
        _mid, ts, direction, body, person, thread, _n = row
        if direction != r["direction"] or abs((ts - r["ts"]).total_seconds()) > FILL_SECONDS:
            continue
        if not ((pid is not None and person == pid) or thread in also):
            continue
        if not (words(body) == words(r["text"]) or (body == NO_TEXT and (r["text"] == NO_TEXT or r.get("media")))):
            continue
        if best is None or abs((ts - r["ts"]).total_seconds()) < abs((best[1] - r["ts"]).total_seconds()):
            best = row
    return best


def _upgrade(media, atts):
    """A text's pictures stored at thumbnail size, replaced in place by the full ones (the same file, the same attachment, so the
    page and the picture's reading are unchanged). Only a bigger picture replaces one, so a thumbnail never replaces the full one."""
    kept = [m for m in media or [] if len(m[2]) >= MIN_FILE_BYTES]          # as _media stored them
    if len(kept) != len(atts):
        return
    root = os.path.realpath(MEDIA_DIR)
    for (_ext, _name, data, _d), (_aid, path) in zip(kept, atts):
        if not path or not os.path.realpath(path).startswith(root + os.sep) or not os.path.isfile(path):
            continue
        old = os.path.getsize(path)
        if len(data) <= old:
            continue
        with open(path + ".part", "wb") as f:
            f.write(data)
        os.replace(path + ".part", path)
        upgraded[0] += 1
        upgraded[1] += old
        upgraded[2] += len(data)


def _media(con, msg_id, ts, media, now):
    """A text's pictures and files: file -> attachment -> document (-> a page waiting to be read). Returns pictures queued."""
    queued = 0
    for n, (ext, name, data, describable) in enumerate(media or []):
        if len(data) < MIN_FILE_BYTES:
            continue
        base = f"{ts:%Y%m%d_%H%M%S}_{msg_id}_{n}{ext}"
        dest = os.path.join(MEDIA_DIR, base)
        with open(dest, "wb") as f:
            f.write(data)
        att = con.execute(
            "INSERT INTO attachments (message_id, original_filename,"
            " saved_filename, saved_path, saved_at, state)"
            " VALUES (?,?,?,?,?,'staged') RETURNING id",
            (msg_id, name or base, base, dest, now)).fetchone()[0]
        doc = con.execute(
            "INSERT INTO documents (message_id, attachment_id, doc_type, created_at)"
            " VALUES (?,?,?,?) RETURNING id",
            (msg_id, att, "image" if describable else "attachment", now)).fetchone()[0]
        if describable:
            con.execute(
                "INSERT INTO pages (document_id, page_no, method, text, extracted_at)"
                " VALUES (?,1,'needs_vision','',?)", (doc, now))
            queued += 1
    return queued


def _store_texts(con, part, people, now):
    written = queued = 0
    for r in part:
        if r.get("fill"):               # a picture for a text stored before the link
            queued += _media(con, r["fill"], r["ts"], r["media"], now)
            filled[0] += 1
            continue
        if r["key"] and r["key"] not in people:
            people[r["key"]] = db.new_person_id(con)
            con.execute(
                "INSERT INTO contacts (key, person_id, name, name_source,"
                " first_seen, last_seen, sent_count, updated_at)"
                " VALUES (?,?,?,'text_backup',?,?,0,?)",
                (r["key"], people[r["key"]], r["name"] or None, r["ts"], r["ts"], now))
        msg_id = con.execute(
            "INSERT INTO messages (channel, account, provider_id, thread_id, ts,"
            " direction, from_key, to_keys, person_id, subject, body, ingested_at)"
            " VALUES ('sms','sms',?,?,?,?,?,?,?,?,?,?) RETURNING id",
            (r["provider_id"], r["thread"], r["ts"], r["direction"],
             None if r["direction"] == "out" else r["key"],
             r["key"] if r["direction"] == "out" else None,
             people.get(r["key"]), (r["subject"] if "subject" in r else r["name"]) or None, r["text"], now)).fetchone()[0]
        queued += _media(con, msg_id, r["ts"], r.get("media"), now)
        written += 1
    return written, queued


# --- the full history reload (Settings, Tools: Reload all email history) ------------------------------------------------
# Each mailbox's whole history is read again from the service a portion per pass, in the slow work after the new mail. Each
# email is stored with the service's own id, folders, labels, conversation and state. A stored email is paired with the
# service's copy by its Message-ID, or (an earlier import's row with none) by sender, subject and the same second, so its
# attachments, documents and card links stay; nothing else pairs. When the reload is done, a stored email the service no
# longer has stays as history, marked server_gone. Nothing is deleted.
RELOAD = "reload"


def _seen(con, message_id):
    con.execute("UPDATE mail_state SET reload_seen=? WHERE message_id=?", [dt.datetime.now(), message_id])


def _pair(con, account, r, started):
    """The stored email this copy from the service is, by its Message-ID, or for a row with no Message-ID by sender, subject and
    time to the second; one already paired in this reload is not taken twice. None when there is none."""
    h = ((r["state"] or {}).get("header_id") or "").strip()
    if h:
        got = con.execute("SELECT s.message_id FROM mail_state s JOIN messages m ON m.id = s.message_id WHERE s.account=?"
                          " AND m.channel='email' AND s.header_id=? AND (s.reload_seen IS NULL OR s.reload_seen < ?)"
                          " ORDER BY m.id LIMIT 1", [account, h, started]).fetchone()
        if got:
            return got[0]
    got = con.execute("SELECT m.id FROM messages m LEFT JOIN mail_state s ON s.message_id = m.id WHERE m.channel='email'"
                      " AND m.account=? AND coalesce(s.header_id, '') = '' AND coalesce(m.from_key, '') = ?"
                      " AND coalesce(m.subject, '') = ? AND date_trunc('second', m.ts) = date_trunc('second', ?::TIMESTAMP)"
                      " AND (s.reload_seen IS NULL OR s.reload_seen < ?) ORDER BY m.id LIMIT 1",
                      [account, f"email:{r['from_addr']}" if r["from_addr"] else "", r["subject"] or "", r["ts"], started]).fetchone()
    return got[0] if got else None


def reload_state(account):
    import json
    raw = cursor(account, RELOAD)
    return json.loads(raw) if raw else None


def set_reload_state(account, st):
    import json
    set_cursor(account, RELOAD, json.dumps(st))


def reload_start(account):
    """Start (or start again) the full history reload of this mailbox."""
    set_reload_state(account, {"started": dt.datetime.now().isoformat(timespec="seconds"), "page": None, "read": 0,
                               "paired": 0, "new": 0, "done": False})


def reload_seen_ids(account, pids):
    """The service listed these emails, already held under these ids: seen in this reload."""
    now = dt.datetime.now()
    with db.transaction() as con:
        for pid in pids:
            mid = find_email(con, account, pid)
            if mid is not None:
                if not con.execute("SELECT 1 FROM mail_state WHERE message_id=?", [mid]).fetchone():
                    put_state(con, mid, account, pid, {})
                con.execute("UPDATE mail_state SET reload_seen=? WHERE message_id=?", [now, mid])


def reload_finish(account, st):
    """Every page read: a stored email (from before the reload began) the service did not list stays, marked as history."""
    started = dt.datetime.fromisoformat(st["started"])
    now = dt.datetime.now()
    with db.transaction() as con:
        con.execute("INSERT INTO mail_state (message_id, account, provider_id, updated_at) SELECT m.id, m.account, m.provider_id, ?"
                    " FROM messages m LEFT JOIN mail_state s ON s.message_id = m.id WHERE m.channel='email' AND m.account=?"
                    " AND s.message_id IS NULL AND m.ingested_at < ?", [now, account, started])
        con.execute("UPDATE mail_state SET server_gone=? WHERE account=? AND (reload_seen IS NULL OR reload_seen < ?)"
                    " AND message_id IN (SELECT id FROM messages WHERE channel='email' AND account=? AND ingested_at < ?)",
                    [now, account, started, account, started])
        st["gone"] = con.execute("SELECT count(*) FROM mail_state WHERE account=? AND server_gone=?", [account, now]).fetchone()[0]
    st.update(done=True, page=None, done_at=now.isoformat(timespec="seconds"))
    set_reload_state(account, st)
    return st


def reloads_running():
    """True when any mailbox's history reload has portions left (the pass then gives it its own step)."""
    for (raw,) in db.query("SELECT cursor FROM mail_cursors WHERE scope=?", (RELOAD,)):
        try:
            import json
            if not json.loads(raw).get("done"):
                return True
        except ValueError:
            pass
    return False


def reload_line(st):
    """The reload's progress in plain words, for the pass summary; empty when none was started."""
    if not st:
        return ""
    words = f"{st['read']} read, {st['paired']} matched to stored mail, {st['new']} new"
    if st.get("done"):
        return f"history reload done: {words}, {st.get('gone', 0)} kept as history (no longer at the service)"
    return f"history reload: {words} so far"
