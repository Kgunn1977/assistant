r"""A small read copy of the owner's mail, so the page's Mail part answers at once and never waits for a pass.

The page's database allows one writer, and a pass holds it for minutes; opening it also costs most of a second each time.
The Mail part's reads (the list, search, a conversation, the folder tree, an email's own HTML) therefore read this copy
instead: its own DuckDB file in the state folder, kept open by the listener, holding only the mail tables.

    enable()            the listener turns the copy on (until then, and in every other program, mail reads the database itself)
    reader(fresh)       a connection on the copy, or raises mail.Busy when it has never been built; a refresh is started when
                        the database file has changed since the copy was made and the database can be read now
    kept(con, table, ids, make)   each email's first words (snippets) or cleaned text (texts), kept in the copy once made
                        (cleaning a whole body is the slow part)

A refresh asks the database for only what is new (emails, HTML) or small (state, files, folders), holds it for the time
that takes, and lets go; if a pass holds it, the copy that is there is used and the next request tries again. Nothing runs
on its own: a refresh is started by a request, inside the listener.
"""
import os
import tempfile
import threading
import time

import duckdb

import db
import paths

ON = False
FILE = os.path.join(paths.STATE, "mail_cache.duckdb")
VERSION = 2                     # a new layout is rebuilt from the database
EVERY_CHANGED = 5.0             # a changed database is looked at again after this long
EVERY_BUSY = 12.0               # a database that was held is tried again after this long (a pass's holds are long)
FOLDERS_LOOK = 30.0             # the database's folder rows are compared with the copy's this often, whatever its file's size and time say
FORCE_EVERY = 1.0               # a press's reload asks for the newest, at most this often
LOWER_FROM = 100000             # a search looks through this much of each body (kept lowercased)
SNIP_FROM = 20000               # a snippet is made from the first part of a body only

_lock = threading.Lock()        # one refresh at a time
_state = {"con": None, "sig": None, "tried": 0.0, "ok": False, "busy": False, "error": ""}
_open = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k VARCHAR PRIMARY KEY, v VARCHAR);
CREATE TABLE IF NOT EXISTS messages (id BIGINT, channel VARCHAR, account VARCHAR, provider_id VARCHAR, thread_id VARCHAR, ts TIMESTAMP,
    direction VARCHAR, from_key VARCHAR, to_keys VARCHAR, subject VARCHAR, body VARCHAR, lc VARCHAR);
CREATE TABLE IF NOT EXISTS mail_state (message_id BIGINT, account VARCHAR, provider_id VARCHAR, unread BOOLEAN, inbox BOOLEAN, trashed BOOLEAN,
    labels VARCHAR, cc VARCHAR, from_name VARCHAR, header_id VARCHAR, refs VARCHAR, starred BOOLEAN, snooze_until TIMESTAMP, conv VARCHAR);
CREATE TABLE IF NOT EXISTS attachments (id BIGINT, message_id BIGINT, original_filename VARCHAR, saved_filename VARCHAR, saved_path VARCHAR);
CREATE TABLE IF NOT EXISTS mail_html (message_id BIGINT, html VARCHAR, cids VARCHAR, remote BOOLEAN);
CREATE TABLE IF NOT EXISTS mail_folders (account VARCHAR, folder_id VARCHAR, path VARCHAR, parent_id VARCHAR, kind VARCHAR, unread BIGINT, total BIGINT);
CREATE TABLE IF NOT EXISTS mail_folder_members (account VARCHAR, folder_id VARCHAR, message_id BIGINT);
CREATE TABLE IF NOT EXISTS unsub_main (message_id BIGINT, list_value VARCHAR, post_value VARCHAR, done_at TIMESTAMP, how VARCHAR);
CREATE TABLE IF NOT EXISTS unsub (message_id BIGINT PRIMARY KEY, account VARCHAR, sender VARCHAR, list_value VARCHAR, post_value VARCHAR, checked_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS snippets (message_id BIGINT PRIMARY KEY, kept VARCHAR);
CREATE TABLE IF NOT EXISTS texts (message_id BIGINT PRIMARY KEY, kept VARCHAR);
"""
SMALL = {       # table: the columns copied whole each refresh
    "mail_state": "message_id, account, provider_id, unread, inbox, trashed, labels, cc, from_name, header_id, refs, starred, snooze_until, conv",
    "attachments": "id, message_id, original_filename, saved_filename, saved_path",
    "mail_folders": "account, folder_id, path, parent_id, kind, unread, total",
    "mail_folder_members": "account, folder_id, message_id",
}
MESSAGE_COLS = "id, channel, account, provider_id, thread_id, ts, direction, from_key, to_keys, subject, body"


def enable():
    global ON
    ON = True
    if _wrote not in db.WROTE:
        db.WROTE.append(_wrote)


def _wrote():
    """This program wrote to the database (a press of his, say): the next read of mail takes the change first."""
    _state["dirty"] = True


def _sig():
    """The database file's size and time (and its log's): changes whenever anyone writes, and is read without opening it."""
    out = []
    for p in (paths.DB, paths.DB + ".wal"):
        try:
            st = os.stat(p)
            out.append((st.st_size, st.st_mtime_ns))
        except OSError:
            out.append(None)
    return tuple(out)


def _connection():
    with _open:
        if _state["con"] is None:
            os.makedirs(os.path.dirname(FILE), exist_ok=True)
            try:
                con = duckdb.connect(FILE)
                con.execute(SCHEMA)
                got = con.execute("SELECT v FROM meta WHERE k = 'version'").fetchone()
                if got and got[0] != str(VERSION):
                    raise duckdb.Error("older layout")
            except duckdb.Error:
                try:
                    con.close()
                except Exception:  # noqa: BLE001
                    pass
                for p in (FILE, FILE + ".wal"):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                con = duckdb.connect(FILE)
                con.execute(SCHEMA)
            if not con.execute("SELECT 1 FROM meta WHERE k = 'version'").fetchone():
                con.execute("INSERT INTO meta VALUES ('version', ?)", [str(VERSION)])
            got = con.execute("SELECT v FROM meta WHERE k = 'built'").fetchone()
            _state["ok"] = bool(got)
            _state["con"] = con
        return _state["con"]


FOLDERS_FP = "SELECT count(*), coalesce(max(updated_at), TIMESTAMP '1970-01-01'), coalesce(sum(hash(account || '|' || folder_id || '|' || coalesce(path, '') || '|' || coalesce(unread, -1) || '|' || coalesce(total, -1))), 0) FROM mail_folders"


def _folders_fp(main):
    return tuple(str(x) for x in main.execute(FOLDERS_FP).fetchone())


def look():
    """Compare the database's folder rows with those the copy was made from; a difference refreshes the copy now. The file's size
    and time can lag while a pass holds the database open, so the rows themselves are the check. Returns True when it refreshed."""
    _state["looked"] = time.time()
    main = db.try_connect(read_only=True)
    if main is None:
        return False
    try:
        fp = _folders_fp(main)
    finally:
        main.close()
    if fp == _state.get("fp"):
        return False
    return refresh(wait=True)


def stale():
    """True when the database has changed since the copy was made."""
    return _state["sig"] != _sig()


def built():
    return bool(_state["ok"])


def refresh(wait=False):
    """Bring the copy up to the database now, if the database can be read. Returns True when the copy is current.
    The way a request (or a test) asks; refresh_later starts it without waiting."""
    if not _lock.acquire(blocking=wait):
        return False
    try:
        con = _connection().cursor()
        sig = _sig()
        main = db.try_connect(read_only=True)
        if main is None:
            _state["busy"] = True
            return False
        _state["busy"] = False
        tmp = tempfile.mkdtemp(prefix="mailcache-")
        try:
            have = con.execute("SELECT count(*), coalesce(max(id), 0) FROM messages").fetchone()
            n, top = main.execute("SELECT count(*), coalesce(max(id), 0) FROM messages WHERE channel = 'email'").fetchone()
            if n != have[0] + main.execute("SELECT count(*) FROM messages WHERE channel = 'email' AND id > ?", [have[1]]).fetchone()[0]:
                have = (0, 0)               # something was removed from the database: take the mail again whole
            files = {}
            parts = {"messages": f"SELECT {MESSAGE_COLS} FROM messages WHERE channel = 'email' AND id > {int(have[1])}"}
            fp = _folders_fp(main)          # taken with the folder rows below, in the same read
            for t, cols in SMALL.items():
                parts[t] = f"SELECT {cols} FROM {t}" + (" WHERE message_id IN (SELECT id FROM messages WHERE channel = 'email')" if t == "mail_folder_members" else "")
            top_html = con.execute("SELECT coalesce(max(message_id), 0) FROM mail_html").fetchone()[0]
            parts["mail_html"] = f"SELECT message_id, html, cids FROM mail_html WHERE message_id > {int(top_html)}"
            for t, sql in parts.items():
                files[t] = os.path.join(tmp, t + ".parquet").replace("\\", "/")
                main.execute(f"COPY ({sql}) TO '{files[t]}' (FORMAT parquet)")
            files["unsub_main"] = os.path.join(tmp, "unsub_main.parquet").replace("\\", "/")
            try:        # the unsubscribe answers the database keeps (the table is made by the first lookup)
                main.execute(f"COPY (SELECT message_id, list_value, post_value, done_at, how FROM mail_unsub) TO '{files['unsub_main']}' (FORMAT parquet)")
            except duckdb.Error:
                files["unsub_main"] = None
        finally:
            main.close()                    # the database is let go before the copy is written
        try:
            con.execute("BEGIN TRANSACTION")
            if have == (0, 0):
                con.execute("DELETE FROM messages")
                con.execute("DELETE FROM snippets")
                con.execute("DELETE FROM texts")
            con.execute(f"INSERT INTO messages SELECT {MESSAGE_COLS}, lower(substr(body, 1, {LOWER_FROM})) FROM read_parquet('{files['messages']}')")
            for t in SMALL:
                con.execute(f"DELETE FROM {t}")
                con.execute(f"INSERT INTO {t} SELECT * FROM read_parquet('{files[t]}')")
            if have == (0, 0):
                con.execute("DELETE FROM mail_html")
            con.execute(f"INSERT INTO mail_html SELECT message_id, html, cids, NULL FROM read_parquet('{files['mail_html']}')")
            con.execute("DELETE FROM unsub_main")
            if files["unsub_main"]:
                con.execute(f"INSERT INTO unsub_main SELECT * FROM read_parquet('{files['unsub_main']}')")
            con.execute("DELETE FROM meta WHERE k = 'built'")
            con.execute("INSERT INTO meta VALUES ('built', ?)", [str(time.time())])
            con.execute("COMMIT")
        except BaseException:
            try:
                con.execute("ROLLBACK")
            except duckdb.Error:
                pass
            raise
        finally:
            for f in files.values():
                try:
                    os.remove(f or "")
                except OSError:
                    pass
            try:
                os.rmdir(tmp)
            except OSError:
                pass
        _fill(con)
        _state.update(sig=sig, ok=True, error="", fp=fp, looked=time.time())
        return True
    except Exception as e:  # noqa: BLE001  the copy that is there keeps being used
        _state["error"] = f"{type(e).__name__}: {e}"[:300]
        return False
    finally:
        _state["tried"] = time.time()
        _lock.release()


def _fill(con, most=150, secs=2.0):
    """Snippets for the newest emails that have none, so the first list is not made slow by cleaning them."""
    import mail
    end = time.time() + secs
    got = con.execute("SELECT m.id, m.body FROM messages m LEFT JOIN snippets s ON s.message_id = m.id WHERE s.message_id IS NULL"
                      " ORDER BY m.ts DESC LIMIT ?", [most]).fetchall()
    keep = []
    for mid, body in got:
        if time.time() > end:
            break
        keep.append((mid, mail.snip(body)))
    if keep:
        con.executemany("INSERT OR REPLACE INTO snippets VALUES (?, ?)", keep)


def _wanted(fresh):
    if _state["sig"] is None:
        return True
    gap = time.time() - _state["tried"]
    if fresh:
        return gap >= FORCE_EVERY
    if _sig() == _state["sig"]:
        return False
    return gap >= (EVERY_BUSY if _state["busy"] else EVERY_CHANGED)


def _later():
    if _lock.locked():
        return
    threading.Thread(target=refresh, name="mail-cache", daemon=True).start()


def reader(fresh=False):
    """A connection on the copy for one request (close it when done). Raises mail.Busy when the copy was never built.
    fresh: the request follows a change the owner just made, so the database is asked again at once."""
    import mail
    con = _connection()
    if not built():
        refresh(wait=False)                 # the first build; the page asks again meanwhile
        if not built():
            raise mail.Busy()
    elif _state.get("dirty") and time.time() - _state["tried"] >= FORCE_EVERY:
        _state["dirty"] = False
        refresh(wait=True)                  # a change made by this program: shown, when the database can be read, at once
    elif _wanted(fresh):
        if fresh:
            refresh(wait=True)              # a press's reload shows the change if the database can be read
        else:
            _later()
    elif time.time() - _state.get("looked", 0.0) >= FOLDERS_LOOK and not _lock.locked():
        _state["looked"] = time.time()
        threading.Thread(target=look, name="mail-cache-folders", daemon=True).start()
    return con.cursor()


def kept(con, table, ids, make):
    """{message_id: text} for these ids from the table 'snippets' or 'texts', made with make(body) and kept when missing."""
    ids = list(ids)
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    got = dict(con.execute(f"SELECT message_id, kept FROM {table} WHERE message_id IN ({marks})", ids).fetchall())
    miss = [i for i in ids if i not in got]
    if miss:
        body = dict(con.execute(f"SELECT id, body FROM messages WHERE id IN ({','.join('?' * len(miss))})", miss).fetchall())
        made = [(i, make(body.get(i))) for i in miss]
        got.update(made)
        try:
            _connection().cursor().executemany(f"INSERT OR REPLACE INTO {table} VALUES (?, ?)", made)
        except duckdb.Error:
            pass
    return got


def keep_remote(message_id, remote):
    try:
        _connection().cursor().execute("UPDATE mail_html SET remote = ? WHERE message_id = ?", [bool(remote), int(message_id)])
    except duckdb.Error:
        pass


UNSUB_KEEP = 30 * 86400         # a sender's unsubscribe offer is kept this long
UNSUB_NONE_KEEP = 2 * 86400     # a sender whose email offered none is not asked again for this long


def unsub_known(con, mid, account, sender):
    """(list_value, post_value, done_at, how) for this email from what is held here, or None when it must be asked of the mail
    service: its own answer (from the database's, or asked earlier), else its sender's from the last weeks."""
    got = con.execute("SELECT list_value, post_value, done_at, how FROM unsub_main WHERE message_id = ?", [mid]).fetchone()
    if got:
        return got
    got = con.execute("SELECT list_value, post_value FROM unsub WHERE message_id = ?", [mid]).fetchone()
    if got:
        return (got[0], got[1], None, None)
    if sender:
        got = con.execute("SELECT list_value, post_value, checked_at FROM unsub WHERE account = ? AND sender = ? ORDER BY checked_at DESC LIMIT 1",
                          [account, sender]).fetchone()
        if got:
            age = (time.time() - got[2].timestamp()) if got[2] else 1e12
            if age < (UNSUB_KEEP if (got[0] or "") else UNSUB_NONE_KEEP):
                return (got[0], got[1], None, None)
    return None


def unsub_put(mid, account, sender, list_value, post_value):
    import datetime as dt
    try:
        _connection().cursor().execute("INSERT OR REPLACE INTO unsub VALUES (?,?,?,?,?,?)",
                                       [mid, account, sender, list_value or "", post_value or "", dt.datetime.now()])
    except duckdb.Error:
        pass
