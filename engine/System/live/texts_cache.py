r"""A small read copy of the owner's texts, so the page's Texts part answers at once.

Opening the page's database costs most of a second each time, and a pass can hold it for minutes. The Texts part's reads (the list,
search, a conversation) therefore read this copy instead: its own DuckDB file in the state folder, holding only the text messages and
the contact names. Fourteen thousand texts are about a megabyte, so a search through every word of them takes a few hundredths of a second.

    enable()      the page's listener turns the copy on (until then, and in every other program, texts read the database itself)
    reader()      a cursor on the copy (with ... as con), or None when it cannot be had now; the copy is built the first time it is asked for
    refresh()     take the texts and names again from the database (a text the texts link stored calls it)

A refresh opens the database for the moment it takes, only if nothing holds it. A database that changed since the copy was made is looked
at again after a few seconds, by a short run started by a request; nothing runs on its own.
"""
import importlib.util
import os
import sys
import threading
import time

# DuckDB looks for pandas each time it makes a Python value, and with pandas missing every look searches the whole import path.
try:
    if importlib.util.find_spec("pandas") is None:
        sys.modules.setdefault("pandas", None)
except (ImportError, ValueError):
    pass

import duckdb  # noqa: E402

import db  # noqa: E402
import paths  # noqa: E402

ON = False
VERSION = 2                     # 2: the texts' pictures (attachments) too
FILE = os.path.join(paths.STATE, "texts_copy.duckdb")
EVERY_CHANGED = 5.0             # a changed database is looked at again after this long (a pass that holds it makes the look fail at once, at no cost)
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k VARCHAR PRIMARY KEY, v VARCHAR);
CREATE TABLE IF NOT EXISTS messages (id BIGINT, channel VARCHAR, thread_id VARCHAR, ts TIMESTAMP, direction VARCHAR, provider_id VARCHAR,
    from_key VARCHAR, person_id BIGINT, subject VARCHAR, body VARCHAR, ingested_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS contacts (person_id BIGINT, name VARCHAR, key VARCHAR);
CREATE TABLE IF NOT EXISTS attachments (id BIGINT, message_id BIGINT, original_filename VARCHAR, saved_filename VARCHAR, saved_path VARCHAR);
"""
CSV = "(FORMAT CSV, HEADER, AUTO_DETECT false, DELIMITER ',', QUOTE '\"', ESCAPE '\"')"
_lock = threading.Lock()         # one refresh at a time
_open = threading.Lock()
_state = {"con": None, "sig": None, "tried": 0.0, "built": False, "running": False}


def enable():
    global ON
    ON = True


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
                for p in (FILE, FILE + ".wal"):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                con = duckdb.connect(FILE)
                con.execute(SCHEMA)
            if not con.execute("SELECT 1 FROM meta WHERE k = 'version'").fetchone():
                con.execute("INSERT INTO meta VALUES ('version', ?)", [str(VERSION)])
            _state["built"] = bool(con.execute("SELECT 1 FROM meta WHERE k = 'built'").fetchone())
            _state["con"] = con
        return _state["con"]


def refresh():
    """The texts and names again from the database. False when the database is held this moment (the copy that is there stays)."""
    with _lock:
        _state["tried"] = time.time()
        sig = _sig()
        src = db.try_connect(read_only=True)
        if src is None:
            return False
        a = os.path.join(os.path.dirname(FILE), "texts_copy_messages.csv")
        b = os.path.join(os.path.dirname(FILE), "texts_copy_contacts.csv")
        c = os.path.join(os.path.dirname(FILE), "texts_copy_attachments.csv")
        try:
            os.makedirs(os.path.dirname(FILE), exist_ok=True)
            fa, fb, fc = a.replace("\\", "/"), b.replace("\\", "/"), c.replace("\\", "/")
            src.execute(f"COPY (SELECT id, channel, thread_id, ts, direction, provider_id, from_key, person_id, subject, body, ingested_at "
                        f"FROM messages WHERE channel='sms') TO '{fa}' (FORMAT CSV, HEADER)")
            src.execute(f"COPY (SELECT person_id, name, key FROM contacts) TO '{fb}' (FORMAT CSV, HEADER)")
            src.execute(f"COPY (SELECT a.id, a.message_id, a.original_filename, a.saved_filename, a.saved_path FROM attachments a "
                        f"JOIN messages m ON m.id = a.message_id WHERE m.channel='sms') TO '{fc}' (FORMAT CSV, HEADER)")
        finally:
            src.close()
        try:
            con = _connection()
            con.execute("BEGIN")
            try:
                con.execute("DELETE FROM messages")
                con.execute(f"COPY messages FROM '{fa}' {CSV}")
                con.execute("DELETE FROM contacts")
                con.execute(f"COPY contacts FROM '{fb}' {CSV}")
                con.execute("DELETE FROM attachments")
                con.execute(f"COPY attachments FROM '{fc}' {CSV}")
                con.execute("DELETE FROM meta WHERE k = 'built'")
                con.execute("INSERT INTO meta VALUES ('built', ?)", [str(time.time())])
                con.execute("COMMIT")
            except Exception:  # noqa: BLE001
                con.execute("ROLLBACK")
                raise
            _state["built"], _state["sig"] = True, sig
        finally:
            for p in (a, b, c):
                try:
                    os.remove(p)
                except OSError:
                    pass
        return True


def _later():
    try:
        refresh()
    finally:
        _state["running"] = False


class _Cursor:
    """A cursor on the copy that reads like the database's own connection and closes like it (with ... as con)."""
    def __init__(self, cur):
        self._cur = cur

    def __enter__(self):
        return self._cur

    def __exit__(self, *exc):
        self._cur.close()
        return False

    def __getattr__(self, name):
        return getattr(self._cur, name)

    def close(self):
        self._cur.close()


def reader():
    """A cursor on the copy, or None (then the caller reads the database itself)."""
    if not ON:
        return None
    try:
        con = _connection()
    except duckdb.Error:
        return None
    if not _state["built"]:
        if not refresh():
            return None
    elif _state["sig"] != _sig() and not _state["running"] and time.time() - _state["tried"] > EVERY_CHANGED:
        _state["running"] = True
        threading.Thread(target=_later, name="texts-copy", daemon=True).start()
    return _Cursor(con.cursor())
