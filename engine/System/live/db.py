"""Database access. Every call opens and closes its own connection, because
DuckDB holds an exclusive file lock while a read-write connection is open.

Inside one process only one connection is open at a time (the gate below): threads take turns, and a call made while
the same thread already holds one opens its own on top only in the same way (reading only, or reading and writing).
DuckDB cannot safely have the same file open twice in one process, one way and the other, from two threads at once:
it refuses ("Unique file handle conflict", "different configuration") and can damage the file."""

import contextlib
import datetime as dt
import os
import sys
import threading
import time

import duckdb

# DuckDB looks for pandas each time it makes a Python value from a result, and with pandas not installed every look searches
# the whole import path (hundreds of times for one list). A module marked absent answers at once.
try:
    import importlib.util as _iu
    if _iu.find_spec("pandas") is None:
        sys.modules.setdefault("pandas", None)
except (ImportError, ValueError):
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402


LOCK_RETRIES = 12
LOCK_BACKOFF_SECONDS = 0.5
LOCK_BACKOFF_MAX = 5.0


def _busy(e):
    """True when the open failed only because someone else holds the database now: another process's file lock,
    or another thread of this same program holding it the other way (reading only, or reading and writing)."""
    if isinstance(e, duckdb.IOException):
        return "being used by another process" in str(e) or "lock" in str(e).lower()
    return isinstance(e, duckdb.ConnectionException) and "different configuration" in str(e)


_gate = threading.Condition(threading.Lock())
_held = {"thread": None, "depth": 0, "read_only": None, "by": "", "since": 0.0, "told": 0.0}


def _holder_gone():
    """True when the thread that holds the connection has ended without letting go (its hold can never be released by it)."""
    t = _held["thread"]
    return t is not None and t != threading.get_ident() and t not in {x.ident for x in threading.enumerate()}


def _enter(read_only, wait):
    """Takes this process's one connection for this thread, waiting up to `wait` seconds for another thread to let go.
    Returns the way to open it (read_only), or None when another thread still holds it. A thread that holds it already
    opens again only the same way: reading inside a write is done as a write; a write inside a read is refused."""
    me, end = threading.get_ident(), time.time() + wait
    with _gate:
        while _held["thread"] not in (None, me):
            if _holder_gone():                  # a hold left by a thread that has ended is cleared, not waited on for ever
                _note_held(time.time() - _held["since"], _held["by"], "its thread ended without closing it; cleared")
                _held.update(thread=None, depth=0, read_only=None)
                break
            left = end - time.time()
            if left <= 0:
                if time.time() - _held["since"] > HELD_NOTE_SECONDS and time.time() - _held["told"] > 60:      # name the holder once a minute, so a stuck hold is traced to its code
                    _held["told"] = time.time()
                    _note_held(time.time() - _held["since"], _held["by"], "still held while another part of this process waited")
                return None
            _gate.wait(left)
        if _held["thread"] == me:
            if _held["read_only"] and not read_only:
                return None                 # a write inside this thread's own read: it must close the read first
            read_only = _held["read_only"]
        if _held["thread"] != me:
            _held["since"], _held["by"] = time.time(), _opener()
        _held.update(thread=me, read_only=read_only)
        _held["depth"] += 1
        return read_only


def _leave():
    with _gate:
        _held["depth"] -= 1
        if _held["depth"] <= 0:
            _held.update(thread=None, depth=0, read_only=None)
            _gate.notify_all()


WROTE = []                      # called (no arguments) each time this process lets go of a connection that could write

HELD_NOTE_SECONDS = 20          # a connection kept longer than this is written to errors.log with the code that opened it


def _opener():
    """Where the connection was opened: the program's own frames, innermost last (a few, short)."""
    import traceback
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    frames = [f for f in traceback.extract_stack()[:-3] if f.filename.startswith(root)]
    return " < ".join(f"{os.path.relpath(f.filename, root)}:{f.lineno} {f.name}" for f in reversed(frames[-6:]))


def _note_held(secs, opener, how):
    try:
        with open(os.path.join(paths.HOME, "logs", "errors.log"), "a", encoding="utf-8") as f:
            f.write(f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} database held {secs:.0f}s by process {os.getpid()}"
                    f" ({how}), opened at {opener}\n")
    except OSError:
        pass


# DuckDB on Windows takes 0.5 to 2 s to fail an open that finds the file held by a writer (it looks up which program holds
# it), however short the hold is, so a page read that ran into a write waited that long. A writer therefore also holds a
# byte of a small side file for as long as it has the database open; a reader reads that byte (a read of a byte another
# program has locked is refused at once) and opens the database only when it is free, so it never runs into the lock.
try:
    import msvcrt
except ImportError:                                 # not Windows: no side lock, the open itself answers
    msvcrt = None
GATE_FILE = paths.DB + ".writing"
GATE_PEEK_SECONDS = 0.3         # how long a no-wait read waits for a write to let go before it answers "busy"


def _writer_active():
    """True when another program holds the database to write (its side-file byte is locked). Never waits."""
    if msvcrt is None:
        return False
    try:
        with open(GATE_FILE, "rb") as f:
            f.read(1)
        return False
    except PermissionError:
        return True
    except OSError:
        return False                                # no side file yet: no writer has ever run


def _take_writer_gate():
    """The writer's byte of the side file, or None when another writer holds it (or Windows locking is not there)."""
    if msvcrt is None:
        return False
    try:
        fd = os.open(GATE_FILE, os.O_RDWR | os.O_CREAT)
        if not os.fstat(fd).st_size:
            os.write(fd, b"w")
        os.lseek(fd, 0, 0)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    except OSError:
        try:
            os.close(fd)
        except (OSError, UnboundLocalError):
            pass
        return None
    return fd


def _drop_writer_gate(fd):
    if fd:
        try:
            os.lseek(fd, 0, 0)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        finally:
            os.close(fd)


class _Held:
    """The connection, plus when and where it was opened, so a long hold names its code (a pass that finds the
    database busy names only the process). Everything else is the connection itself."""
    __slots__ = ("_con", "_at", "_by", "_open", "_write", "_gate")

    def __init__(self, con, write=False, gate=False):
        self._con, self._at, self._by, self._open, self._write, self._gate = con, time.time(), _opener(), True, write, gate

    def __getattr__(self, name):
        return getattr(self._con, name)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self._open:
            self._open = False
            try:
                self._con.close()
            finally:
                try:
                    _drop_writer_gate(self._gate)
                finally:
                    _leave()
            if self._write:
                for f in WROTE:
                    f()
            held = time.time() - self._at
            if held > HELD_NOTE_SECONDS:
                _note_held(held, self._by, "closed")

    def __del__(self):
        if getattr(self, "_open", False):          # dropped without close: held until now
            _note_held(time.time() - self._at, self._by, "never closed, dropped")
            self._open = False
            try:
                self._con.close()
            except Exception:  # noqa: BLE001  already gone
                pass
            try:
                _drop_writer_gate(self._gate)
            except OSError:
                pass
            _leave()


GATE_WAIT_ONE = 3.0             # try_connect: how long it waits for another thread of this process (holds are short)


def connect(read_only: bool = False, retries: int = LOCK_RETRIES):
    """Open a fresh connection, waiting (about 30 seconds in all) while another process or thread holds it. The one
    way every part of the program opens the database; try_connect is its no-wait form."""
    os.makedirs(os.path.dirname(paths.DB), exist_ok=True)
    delay = LOCK_BACKOFF_SECONDS
    last = None
    window = sum(min(LOCK_BACKOFF_SECONDS * 1.5 ** i, LOCK_BACKOFF_MAX) for i in range(max(0, retries - 1))) or GATE_WAIT_ONE
    way = _enter(read_only, window)
    if way is None:
        raise TimeoutError("database busy: another part of this program held it for the whole wait.")
    for attempt in range(retries):
        gate = False
        try:
            if _writer_active() and not _wait_writer(GATE_PEEK_SECONDS if retries == 1 else delay):
                last = "another process is writing"             # not opened: a refused open costs a second or more
            else:
                gate = False if way else _take_writer_gate()
                if gate is None:
                    last = "another process is about to write"
                else:
                    try:
                        return _Held(duckdb.connect(paths.DB, read_only=way), write=not way, gate=gate)
                    except BaseException:
                        _drop_writer_gate(gate)
                        raise
        except (duckdb.IOException, duckdb.ConnectionException) as e:
            if not _busy(e):
                _leave()
                raise                       # a real problem, not someone else holding it
            last = e
        except Exception:
            _leave()
            raise
        if attempt < retries - 1:
            time.sleep(delay)
            delay = min(delay * 1.5, LOCK_BACKOFF_MAX)
    _leave()
    raise TimeoutError(
        f"database busy: another process held it for the whole retry window. {last}")


def _wait_writer(secs):
    """Waits up to `secs` for the writing program to let go; True when it did (the database can be opened now)."""
    end = time.time() + secs
    while _writer_active():
        if time.time() >= end:
            return False
        time.sleep(0.01)
    return True


def try_connect(read_only: bool = False):
    """The database now, or None when someone else holds it. Never waits: for the page's answers, which must reply at
    once and keep a press for later when the database is busy."""
    try:
        return connect(read_only=read_only, retries=1)
    except TimeoutError:
        return None


_reading = threading.local()


def start_reading():
    """One read-only connection for a run of reads in this thread: every query() until stop_reading() uses it instead of
    opening the file again. An open of a large home's database costs about a second (0.9 to 1.1s on 710 MB, 11/22/26), so a
    loop of reads that opened one each took minutes. A write inside is refused (db._enter), so only reads go between."""
    if getattr(_reading, "con", None) is None:
        _reading.con = connect(read_only=True)
        _reading.depth = 0
    _reading.depth += 1
    return _reading.con


def stop_reading():
    if getattr(_reading, "con", None) is None:
        return
    _reading.depth -= 1
    if _reading.depth <= 0:
        con, _reading.con = _reading.con, None
        con.close()


@contextlib.contextmanager
def reading():
    """start_reading() and stop_reading() as a with-block; yields the connection."""
    con = start_reading()
    try:
        yield con
    finally:
        stop_reading()


def reader():
    """This thread's open reading connection (start_reading), or None."""
    return getattr(_reading, "con", None)


def query(sql: str, params: tuple = ()):
    """Read: returns list of tuples. Opens and closes its own connection, or uses this thread's reading one."""
    if reader() is not None:
        return reader().execute(sql, params).fetchall()
    con = connect(read_only=True)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def execute(sql: str, params: tuple = ()):
    """Single write statement in its own connection."""
    con = connect()
    try:
        con.execute(sql, params)
    finally:
        con.close()


def insert(con, table: str, row: dict):
    """Add one row. Ids always come from the table's own sequence; a row that
    names its id is refused, because an id chosen by hand runs the sequence
    behind and the next insert collides."""
    if "id" in row:
        raise ValueError(f"insert into {table}: never pass an id, the sequence assigns it")
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    con.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(row.values()))


def new_person_id(con):
    """The next person id for a new contact, from its sequence, never one already in use (the owner is person 1, written
    without the sequence: a new home's first contact once got the owner's id)."""
    while True:
        n = con.execute("SELECT nextval('seq_person_id')").fetchone()[0]
        if not con.execute("SELECT 1 FROM contacts WHERE person_id = ? LIMIT 1", [n]).fetchone():
            return n


@contextlib.contextmanager
def transaction():
    """A write connection inside one transaction: commits on success, rolls
    back on any error, always closes."""
    con = connect()
    try:
        con.execute("BEGIN TRANSACTION")
        yield con
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


WATERMARK_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def watermark(source):
    """A source's watermark as a datetime, or None when it has none."""
    rows = query("SELECT position FROM watermarks WHERE source=?", (source,))
    try:
        return dt.datetime.strptime(rows[0][0], WATERMARK_FORMAT) if rows else None
    except ValueError:
        return None


def set_watermark(source, when, con=None):
    """Record how far a source has been read. Not while reading back (ASSISTANT_READ_SINCE): that reads from a date
    and leaves each source's place where it was."""
    if os.environ.get("ASSISTANT_READ_SINCE"):
        return
    pos = when.strftime(WATERMARK_FORMAT) if isinstance(when, dt.datetime) else when
    sql = ("INSERT OR REPLACE INTO watermarks (source, position, updated_at)"
           " VALUES (?,?,?)")
    if con is not None:
        con.execute(sql, (source, pos, dt.datetime.now()))
    else:
        execute(sql, (source, pos, dt.datetime.now()))


def record_source_status(run_id, source, status, detail, con=None):
    """Record how one source fared in a run. Does nothing without a run id;
    creates the runs row when the script runs outside a pass, so the foreign
    key never fails."""
    if not run_id:
        return
    now = dt.datetime.now()
    own = con is None
    con = con or connect()
    try:
        con.execute(
            "INSERT INTO runs (run_id, started_at, outcome, note)"
            " SELECT ?, ?, 'running', 'step run outside a pass'"
            " WHERE NOT EXISTS (SELECT 1 FROM runs WHERE run_id = ?)",
            (run_id, now, run_id))
        con.execute(
            "INSERT INTO source_status (run_id, source, status, detail, updated_at)"
            " VALUES (?,?,?,?,?)"
            " ON CONFLICT (run_id, source) DO UPDATE SET status=excluded.status,"
            " detail=excluded.detail, updated_at=excluded.updated_at",
            (run_id, source, status, (detail or "")[:2000], now))
    finally:
        if own:
            con.close()


def init_schema():
    """Apply schema.sql. Idempotent."""
    with open(os.path.join(getattr(paths, "CORE", paths.CONFIG), "schema.sql"), encoding="utf-8") as f:
        ddl = f.read()
    con = connect()
    try:
        con.execute(ddl)
    finally:
        con.close()


def tables():
    return [r[0] for r in query(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='main' ORDER BY table_name"
    )]
