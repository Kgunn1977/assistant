r"""Rebuild the owner's data day by day, as a new user would have it: erase the working data, then read each day straight from
its sources and sort it as the 15-minute check would have that day, one week per run.

    python replay.py dry-run            what erase would move and keep, and what day 1 would read; touches nothing, asks no service
    python replay.py prepare [--start 2026-09-01] [--texts-folder <folder>]
                                        Sync off (the page's own Sync setting), one harmless read of every account, the phone
                                        backups filed by day (read once)
    python replay.py erase              the working data deleted outright; a fresh database keeping contacts
    python replay.py run-week           the next 7 days (or up to yesterday); stops and writes a report
    python replay.py continue           the same as run-week
    python replay.py status             where it stands
    python replay.py report             the last report again

Each day runs midnight to midnight in the owner's zone (America/Los_Angeles unless his settings name another), with real zone
math: a day of 23 or 25 hours is that long. A day is: its mail, calendar and texts (and any added connection
type's own day reader, replay_day) read and stored (the usual rules keep
each message once), the usual filing steps, then the usual sorting (judge, cards written) told that it is the end of that day
and shown nothing after it, then the usual closing of cards the record shows handled. The last finished day is recorded, so a
stop at any moment loses nothing: continue starts again at the first day not finished, and what that day already stored is
recognised and not stored twice.

Nothing goes out. This program sets ASSISTANT_REPLAY for itself and everything it starts, and every outbound function refuses
under it (replay_guard.py). Alerts, standing approvals, drafts moving to Drafts, snoozes marked unread at the mail
service, the texts link, invite answers, mods and the page refresh are not part of a replay day at all.

Sync stays off from prepare to the end, and is left off: the owner turns it back on.

A Tools entry on the page can start this later: one more entry in tools.TOOLS ("replay", with a walk-through text in
setup\setup_texts) whose steps run "replay.py status" and "replay.py run-week" through tools.run_setup (run-week as a LONG job).
Not added yet.
"""
import argparse
import datetime as dt
import json
import os
import shutil
import sys
import time

os.environ["ASSISTANT_REPLAY"] = "1"       # before anything else: this program and all it starts may not send (replay_guard)

import common  # noqa: E402
import replay_guard  # noqa: E402
replay_guard.install()        # also when common was imported before the flag was set

FOLDER = os.path.join(common.paths.STATE, "replay")
STATE = os.path.join(FOLDER, "state.json")
DAYS = os.path.join(FOLDER, "days.json")
REPORTS = os.path.join(FOLDER, "reports")
START = dt.date(2026, 9, 1)
WEEK = 7
ROUNDS = 8                  # sorting rounds a day may take (each round is one ordinary think pass's worth of work)
ZONE_NAME = "America/Los_Angeles"

# What erase deletes, relative to the home, and what each is. Anything not named here is left where it is.
ERASE = (
    ("Resources/Database/assistant.duckdb", "the database: every stored message of every channel, cards, tasks, the calendar copy, "
                                            "sorting marks, mail folders, read and inbox states, snoozes, unsubscribes"),
    ("Resources/Database/assistant.duckdb.wal", "the database's unsaved tail"),
    ("Resources/Attachments", "attachments and texted pictures"),
    ("items.json", "the cards as the page last showed them"),
    ("today.json", "the Today panel"),
    ("held.json", "Hidden"),
    ("state/held_shown.json", "Hidden: rows opened"),
    ("state/held_wanted.json", "Hidden: cards asked for"),
    ("state/held_reading.json", "Hidden: the message last read"),
    ("think_state.json", "the sorting state"),
    ("gather_state.json", "the gathering marks"),
    ("health.json", "the last check's health record"),
    ("answers", "answers on the old cards not yet applied"),
    ("presses_waiting.jsonl", "presses on the old cards waiting for the database"),
    ("state/last_got_it_all.json", "the last Got it all press"),
    ("alerts_sent.json", "which cards were notified"),
    ("alerts_mail_sent.json", "which emails were notified"),
    ("alerts_held.json", "notifications held over quiet hours"),
    ("known_people.json", "the people lookup made from contacts and mail"),
    ("state/names_in_mail.json", "names seen in mail"),
    ("state/mail_cache.duckdb", "the Email part's copy of stored mail"),
    ("state/mail_cache.duckdb.wal", "the Email part's copy: unsaved tail"),
    ("state/texts_copy.duckdb", "the Texts page's copy of stored texts"),
    ("state/texts_copy.duckdb.wal", "the Texts page's copy: unsaved tail"),
    ("state/texts_read.json", "which texts were read"),
    ("state/texts_link_convs.json", "the texts link's stored conversation matches"),
    ("state/text_backups_read.json", "which phone backups were read"),
    ("state/inline_images_seen.txt", "signature pictures seen in mail"),
    ("state/page_pictures", "PDF pages drawn for reading"),
    ("state/mail_plans.json", "mail handling plans on stored emails"),
    ("state/mail_pull.json", "the last mail Refresh"),
    ("state/items", "the sorting's full task records"),
    ("state/rebuild", "card sets saved by Rebuild all cards"),
    ("state/payload_*.json", "sorting payloads"),
    ("state/verdicts_*.json", "sorting verdicts"),
    ("state/live_*.json", "card writing and page reading payloads"),
)
# What stays, named from the code (paths relative to the home).
KEPT = (
    ("personal/filter_rules.json", "your rules"),
    ("personal/personal.json", "who you are, ignored and priority senders, your own domains, which sources are read"),
    ("personal/settings.json", "your settings, mods' settings included"),
    ("personal/voice.json", "your learned writing style"),
    ("personal/rule_book.jsonl", "the rule book: your presses on cards beside what the assistant had decided (a replay day writes none)"),
    ("personal/keys.dat, personal/connections.json, state/granted_scopes.json", "sign-ins and keys, and which accounts are connected"),
    ("personal/ (every other file)", "page address and key, projects, Important list, standing approvals, install records"),
    ("mods/ and taught/", "your mods and add-ons"),
    ("Resources/Rules, Resources/Data", "rule documents and junk-sender lists"),
    ("contacts (carried into the fresh database)", "names, companies, notes and who is the same person; counts from messages "
                                                   "are set to zero and recounted from the rebuilt messages"),
    ("chat.json, chat/, logs/, page_state/, mail/ (drafts, signatures), state/texts_outbox.json, state/texts_drafts.json",
     "Talk to your assistant, logs, the page's own files, and your own unsent drafts"),
)
CONTACT_KEEP = ("key", "person_id", "name", "name_source", "company", "notes", "updated_at")


# --- small things ---------------------------------------------------------------------------------------------------------
def say(*a):
    print(*a, flush=True)


def zone():
    from zoneinfo import ZoneInfo
    return ZoneInfo(str(common.personal().get("timezone") or ZONE_NAME))


def window(day, z=None):
    """(start, end) of one day in the zone, as moments: midnight to the next midnight, 23, 24 or 25 hours apart."""
    z = z or zone()
    return dt.datetime.combine(day, dt.time(), z), dt.datetime.combine(day + dt.timedelta(days=1), dt.time(), z)


def state():
    return common.read_json(STATE, {}) or {}


def save_state(st):
    common.write_json(STATE, st)


def days():
    return common.read_json(DAYS, []) or []


def _first_day(st):
    return dt.date.fromisoformat(st.get("start") or START.isoformat())


def next_day(st):
    last = st.get("last_done")
    return dt.date.fromisoformat(last) + dt.timedelta(days=1) if last else _first_day(st)


def _yesterday():
    return dt.datetime.now(zone()).date() - dt.timedelta(days=1)


def _sources_on():
    import connections
    on = {str(s).strip().lower() for s in (common.personal().get("sources") or [])}
    return [c for c in connections.listed() if c.get("kind") in on]


def _own_reader(c):
    """An added connection type's own day reader and its name: replay_day(conn, start, end) in the type's module, returning
    (how many stored, [what it could not read]); (None, None) for a type without one. See CONNECTIONS.md beside the connection types."""
    import connections
    try:
        mod = connections.module(c["type"])
    except Exception:  # noqa: BLE001  a type that cannot be loaded has no day reader; dry-run says it is left out
        return None, None
    fn = getattr(mod, "replay_day", None)
    return (fn, getattr(mod, "NAME", c["type"])) if callable(fn) else (None, None)


def _texts_folder(st):
    if st.get("texts_folder"):
        return st["texts_folder"]
    import connections
    for c in connections._file().get("connections") or []:     # read whole: the list of connections in use leaves this type out
        if c.get("type") == "phone_texts" and c.get("folder"):
            return c["folder"]
    return ""


def _sync_off():
    """Sync off through the page's own Sync setting (it switches the scheduled check off too). Returns its plain line."""
    import settings_page
    line = "Sync is off."
    if not settings_page.paused_flag():
        _saved, line = settings_page.save({"settings": {"group": "watch", "values": {"paused": True}}})
        if not settings_page.paused_flag():
            raise SystemExit("Sync could not be switched off, so the replay did not start: " + line)
    if settings_page.pass_job_off() is False:       # the setting says off but the scheduled check is on: switched off with it
        why = settings_page.switch_pass(False)
        if why:
            raise SystemExit("Sync could not be switched off, so the replay did not start: " + why)
    return line


def _size(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    return sum(os.path.getsize(os.path.join(r, f)) for r, _d, fs in os.walk(path) for f in fs)


def erase_list():
    """[(relative path, what it is, bytes)] of what erase would move now."""
    import glob
    out = []
    for rel, what in ERASE:
        for p in sorted(glob.glob(os.path.join(common.HOME, rel))):
            out.append((os.path.relpath(p, common.HOME), what, _size(p)))
    return out


# --- dry run ------------------------------------------------------------------------------------------------------------
def dry_run():
    st = state()
    say("DRY RUN: nothing is moved, stored or asked of any service.\n")
    say("Erase would delete these:")
    for rel, what, n in erase_list():
        say(f"  {rel}  ({n / 1e6:.1f} MB): {what}")
    say("\nErase keeps:")
    for rel, what in KEPT:
        say(f"  {rel}: {what}")
    day = next_day(st)
    s, e = window(day)
    say(f"\nDay 1 would be {day:%A %B %d, %Y}: {s:%Y-%m-%d %H:%M %Z} to {e:%Y-%m-%d %H:%M %Z} "
        f"({(e.timestamp() - s.timestamp()) / 3600:.0f} hours)")
    import replay_sources as rs
    for c in _sources_on():
        label = c.get("label") or c.get("address") or c["id"]
        if c["type"] == "google_mail":
            say(f"  mail {label}: Gmail search \"{rs.gmail_query(s, e)}\", sent and received, with attachments")
        elif c["type"] == "microsoft_mail":
            say(f"  mail {label}: {rs.graph_url(s, e, 'id,...')}")
        elif c["kind"] == "calendar":
            say(f"  calendar {label}: events starting from {s.isoformat()} to before {e.isoformat()}")
        elif _own_reader(c)[0]:
            say(f"  {_own_reader(c)[1]} {label}: read by its own day reader, from {s.isoformat()} to before {e.isoformat()}")
        else:
            say(f"  {label}: the replay has no day reader for this kind ({c['type']}); it is left out")
    folder = _texts_folder(st)
    full, hourly = rs.backups(folder)
    if full:
        filed = os.path.isfile(os.path.join(rs.TEXTS, "days", f"{day}.jsonl"))
        say(f"  texts: phone backups in {folder}: the full one {os.path.basename(full)} ({os.path.getsize(full) / 1e9:.1f} GB) and "
            f"{len(hourly)} hourly ones" + ("; this day's texts are already filed" if filed else "; prepare files them by day first"))
    else:
        say(f"  texts: no phone backups found{' in ' + folder if folder else ''}")
    return 0


# --- prepare ------------------------------------------------------------------------------------------------------------
def prepare(start=None, texts_folder=None):
    st = state()
    if start:
        st["start"] = start
    if texts_folder:
        st["texts_folder"] = texts_folder
    st.setdefault("start", START.isoformat())
    say("Sync: " + _sync_off())
    import connections
    bad = []
    for c in _sources_on():
        label = c.get("label") or c.get("address") or c["id"]
        try:
            say(f"  ok: {connections.module(c['type']).check(c)}")
        except Exception as e:  # noqa: BLE001
            bad.append(label)
            say(f"  PROBLEM: {label}: {type(e).__name__}: {str(e)[:200]}")
    folder = _texts_folder(st)
    if folder:
        import replay_sources as rs
        n_files, n_texts = rs.spool_texts(folder, _first_day(st), _yesterday(), zone(), say)
        say(f"  texts: {n_files} backup file(s) read, {n_texts} text(s) filed by day")
        st["texts_folder"] = folder
    else:
        say("  texts: no phone backup folder is known; texts are left out (prepare --texts-folder <folder> names one)")
    st["prepared_at"] = dt.datetime.now().isoformat(timespec="seconds")
    save_state(st)
    replay_guard.mark_running(True)         # from now on nothing else on the computer imports (the page's Refresh, the texts link)
    if bad:
        say(f"Prepared, but {len(bad)} account(s) did not answer: {', '.join(bad)}. Fix their sign-in before run-week.")
        return 1
    say("Prepared. Next: python replay.py erase")
    return 0


# --- erase --------------------------------------------------------------------------------------------------------------
def _hold_lock(name):
    import gather
    if not gather.take_lock(f"replay-{name}-{dt.datetime.now():%Y%m%d-%H%M%S}"):
        raise SystemExit("A check or another replay is running right now. Wait for it to finish and try again.")


def _read_old(path):
    """({sequence: last id used}, contact columns, contact rows) from the database as it stands; read before anything moves."""
    import duckdb
    if not os.path.isfile(path):
        return {}, [], []
    try:
        con = duckdb.connect(path, read_only=True)
    except duckdb.Error as e:
        raise SystemExit("Nothing was erased: the database is held open by another program (most likely your page). Close "
                         f"the page's program on this computer and run erase again. ({type(e).__name__})") from e
    try:
        seqs = {n: v for n, v in con.execute("SELECT sequence_name, last_value FROM duckdb_sequences()").fetchall()}
        have = {r[0] for r in con.execute("SELECT column_name FROM information_schema.columns WHERE table_name='contacts'").fetchall()}
        cols = [c for c in CONTACT_KEEP if c in have]
        rows = con.execute(f"SELECT {', '.join(cols)} FROM contacts").fetchall() if cols else []
        return seqs, cols, rows
    finally:
        con.close()


def _build_fresh(path, seqs, cols, rows):
    """The new database, built aside at `path`: every id sequence starts after the old one's (an answer or link made for an
    old card or message can never land on a new one), the schema, the cards table, the contacts with their counts at zero."""
    import duckdb
    import items
    with open(os.path.join(common.paths.CORE, "schema.sql"), encoding="utf-8") as f:
        ddl = f.read()
    con = duckdb.connect(path)
    try:
        for name, last in seqs.items():
            con.execute(f"CREATE SEQUENCE IF NOT EXISTS {name} START {int(last or 0) + 1}")
        con.execute(ddl)
        con.execute(items.DDL)
        for name, kind in items.EXTRA_COLUMNS.items():
            con.execute(f"ALTER TABLE live_items ADD COLUMN IF NOT EXISTS {name} {kind}")
        if rows:
            con.executemany(f"INSERT INTO contacts ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})", rows)
        con.execute("CHECKPOINT")
    finally:
        con.close()


def _ids_continue(seqs):
    """True when every old sequence's next id in the database now in place is past the last id the old one gave."""
    import db
    got = {n: s for n, s in db.query("SELECT sequence_name, start_value FROM duckdb_sequences()")}
    return all(n in got and int(got[n]) > int(last or 0) for n, last in seqs.items())


def erase():
    st = state()
    if not st.get("prepared_at"):
        raise SystemExit("Run prepare first: it switches Sync off and checks every account.")
    if st.get("erased_at"):
        raise SystemExit(f"Already erased on {st['erased_at'][:10]}. Next: python replay.py run-week")
    _sync_off()
    _hold_lock("erase")
    import gather
    try:
        # all or nothing: the working data is first moved into one folder in the home, which is deleted outright once the
        # fresh database is in place
        dest = os.path.join(common.HOME, f"replay-erasing-{dt.datetime.now():%Y%m%d-%H%M%S}")
        if os.path.exists(dest):
            raise SystemExit("Nothing was erased: its erasing folder is already there. Run erase again in a moment.")
        seqs, cols, rows = _read_old(common.paths.DB)
        new = common.paths.DB + ".replay-new"
        os.makedirs(dest, exist_ok=True)
        if os.path.exists(new):             # left by an erase that stopped: kept with the rest, never overwritten
            shutil.move(new, os.path.join(dest, "unfinished-" + os.path.basename(new)))
        os.makedirs(os.path.dirname(common.paths.DB), exist_ok=True)
        _build_fresh(new, seqs, cols, rows)
        moved = []

        def back(why, e=None):          # all or nothing: what was moved goes back, the new database waits aside
            for rel in reversed(moved):
                shutil.move(os.path.join(dest, rel), os.path.join(common.HOME, rel))
            raise SystemExit(f"Nothing was erased: {why}") from e
        todo = sorted(erase_list(), key=lambda x: not x[0].endswith((".duckdb", ".wal")))     # the databases first: one held open stops it all
        try:
            for rel, _what, _n in todo:
                to = os.path.join(dest, rel)
                os.makedirs(os.path.dirname(to), exist_ok=True)
                shutil.move(os.path.join(common.HOME, rel), to)
                moved.append(rel)
        except OSError as e:
            back(f"{e.filename or 'a file'} is held open by another program (most likely your page). Close the page's program "
                 "on this computer and run erase again.", e)
        if os.path.exists(common.paths.DB):     # another program made a database in the moment between: set aside with the rest
            try:
                rel = os.path.relpath(common.paths.DB, common.HOME) + ".appeared"
                shutil.move(common.paths.DB, os.path.join(dest, rel))
                moved.append(rel)
            except OSError as e:
                back("another program opened a new database while the old one was being moved (most likely your page). Close "
                     "the page's program on this computer and run erase again.", e)
        os.replace(new, common.paths.DB)
        import items
        items._made["done"] = False         # made once per program run: this run has a new database
        if not _ids_continue(seqs):
            raise SystemExit("Stopped after the move: the new database's numbering does not start after the old one's. "
                             f"Your old data is in {dest}; nothing was replayed.")
        common.write_json(gather.GATHER_STATE, {"page_mark_document": 0, "pages_skipped": []})     # every page of the replay is read
        shutil.rmtree(dest, ignore_errors=True)
        st.update(erased_at=dt.datetime.now().isoformat(timespec="seconds"), moved=moved, last_done=None)
        save_state(st)
        common.write_json(DAYS, [])
    finally:
        gather.drop_lock()
    say(f"Erased: {len(moved)} item(s) deleted. {len(rows)} contact(s) kept, their counts start again from zero.")
    say("Next: python replay.py run-week")
    return 0


# --- one day ------------------------------------------------------------------------------------------------------------
class DayStopped(Exception):
    """A day that could not be finished: a source could not be read, or the sorting did not get through it."""


def _marks():
    import db
    import items
    items.ensure()
    return (db.query("SELECT coalesce(max(id), 0) FROM messages")[0][0],
            {r[0]: r[1] for r in db.query("SELECT id, state FROM live_items")})


def run_day(day, z=None):
    """Read, sort and close one day. Returns its record; raises DayStopped when it could not be finished. A try that stops
    leaves what it spent and the cards as they were before it (state "partial"), so the day's record, finished on a later
    try, counts the whole day."""
    import think
    st = state()
    part = st.get("partial") if (st.get("partial") or {}).get("day") == day.isoformat() else None
    if part is None:
        part = {"day": day.isoformat(), "ai_calls": 0, "ai_secs": 0, "cards_before": _marks()[1]}
    calls0 = len(think.calls)
    try:
        rec = _run_day(day, z or zone(), part["cards_before"])
    except BaseException:
        mine = think.calls[calls0:]
        part.update(ai_calls=part["ai_calls"] + len(mine), ai_secs=part["ai_secs"] + round(sum(c.get("secs") or 0 for c in mine)))
        st = state()
        st["partial"] = part
        save_state(st)
        raise
    mine = think.calls[calls0:]
    rec.update(ai_calls=part["ai_calls"] + len(mine), ai_secs=part["ai_secs"] + round(sum(c.get("secs") or 0 for c in mine)))
    st = state()
    st.pop("partial", None)
    save_state(st)
    return rec


def _counts(start, end):
    """What the database holds for each source on the day, whichever try stored it."""
    import db
    lo, hi = start.astimezone().replace(tzinfo=None), end.astimezone().replace(tzinfo=None)
    out = {}
    for c in _sources_on():
        label = c.get("label") or c.get("address") or c["id"]
        if c["kind"] == "email":
            out[f"mail {label}"] = db.query("SELECT count(*) FROM messages WHERE channel='email' AND lower(account)=? AND ts >= ? AND ts < ?",
                                            (str(c.get("address") or "").lower(), lo, hi))[0][0]
        elif c["kind"] == "calendar":
            out[f"calendar {label}"] = db.query("SELECT count(*) FROM calendar_events WHERE start_ts >= ? AND start_ts < ?", (lo, hi))[0][0]
        elif _own_reader(c)[0]:     # an added chat-style type stores under its kind, with its label as the account
            out[f"{_own_reader(c)[1]} {label}"] = db.query("SELECT count(*) FROM messages WHERE channel=? AND account=? AND ts >= ? AND ts < ?",
                                                          (c["kind"], label, lo, hi))[0][0]
    if state().get("texts_folder") and "sms" in {str(s).lower() for s in common.personal().get("sources") or []}:
        out["texts"] = db.query("SELECT count(*) FROM messages WHERE channel='sms' AND ts >= ? AND ts < ?", (lo, hi))[0][0]
    return out


def _run_day(day, z, cards_before):
    import db
    import gather
    import items
    import limits
    import replay_sources as rs
    start, end = window(day, z)
    ends = (end.astimezone().replace(tzinfo=None) - dt.timedelta(microseconds=1))
    os.environ[common.AI_NOW] = ends.isoformat()        # the AI is told it is the end of this day, and sees nothing after it
    pid = f"replay-{day}"
    t0 = time.time()
    t_try = dt.datetime.now()
    limits.begin(pid)
    first_id = _marks()[0]
    dids = {r[0]: r[1] or "" for r in db.query("SELECT id, assistant_did FROM live_items")}
    rec = {"day": day.isoformat(), "hours": round((end.timestamp() - start.timestamp()) / 3600), "sources": {}, "problems": []}

    st = state()
    for c in _sources_on():
        label = c.get("label") or c.get("address") or c["id"]
        limits.step(f"replay read {label}")
        try:
            if c["kind"] == "email":
                rs.mail_day(c, start, end)
            elif c["kind"] == "calendar":
                rs.calendar_day(c, start, end)
            elif _own_reader(c)[0]:
                reader, name = _own_reader(c)
                _n, unreadable = reader(c, start, end)
                if unreadable:
                    rec["problems"].append(f"{name} {label}: could not read {', '.join(unreadable[:5])}")
        except replay_guard.Refused:
            raise
        except Exception as e:  # noqa: BLE001  the day is not sorted on half its record: it stops here, and continue reads it again
            raise DayStopped(f"{label} could not be read for {day}: {type(e).__name__}: {str(e)[:300]}") from e
    if "sms" in {str(s).lower() for s in common.personal().get("sources") or []} and st.get("texts_folder"):
        rs.texts_day(day)
    rec["sources"] = _counts(start, end)

    # the usual filing steps, then conversations for mail the service gave none (never snoozes: they reach the mail service),
    # then how often the owner is in touch with each person, counted as of the day's end
    import mail
    new_msgs = db.query("SELECT count(*) FROM messages WHERE id > ?", (first_id,))[0][0]
    limits.begin(pid)
    for name, path, args, takes_run in (gather.FOLLOW if new_msgs else ()):
        ok, tail = gather.run_script(path, *args, run_id=pid if takes_run else None, timeout=limits.FOLLOW)
        if not ok:
            rec["problems"].append(f"{name} step: {tail[:200]}")
    mail.rethread()
    try:
        import contact_strength
        contact_strength.refresh(now=ends)
    except Exception as e:  # noqa: BLE001
        rec["problems"].append(f"contacts not recounted: {type(e).__name__}: {e}"[:200])

    # the usual sorting, round after round until nothing of the day is owed
    import think
    ts = common.read_json(common.THINK_STATE, {}) or {}
    if ts.get("failed_at"):                 # an earlier try of this day failed: the replay tries again at once, never waits an hour
        ts["failed_at"] = None
        common.write_json(common.THINK_STATE, ts)
    for n in range(ROUNDS):
        limits.begin(pid)
        g = {"unjudged": gather.unjudged(), "pages_waiting": len(gather.pending_pages()),
             "texted_images_waiting": gather.texted_images_waiting(), "new_messages": [1] if n == 0 else [], "new_attachments": 0}
        if not think.needed(g):
            break
        t = think.think(pid)
        for s in t["steps"]:
            if not s["ok"]:
                rec["problems"].append(f"AI step '{s['step']}' failed: {s['why']}")
        if not t["ok"]:
            break
    # the usual closing: a card whose task the day's record closed is closed now
    items.sync_from_tasks(pid)
    items.close_retired(pid)
    still = gather.unjudged()
    if still:
        raise DayStopped(f"{day}: {still} message(s) were not sorted" + (f" ({rec['problems'][-1]})" if rec["problems"] else ""))

    try:
        import people
        people.write_people()
    except Exception as e:  # noqa: BLE001
        rec["problems"].append(f"people lookup not written: {type(e).__name__}: {e}"[:200])
    _as_of_day(day, start, end, ends, t_try, dids)
    items.export(pid)
    _no_alerts_later(pid)
    cards_after = _marks()[1]
    rec["cards_made"] = len([i for i in cards_after if i not in cards_before])
    rec["cards_closed"] = len([i for i, s in cards_after.items() if s == "done" and cards_before.get(i) != "done"])
    rec["secs"] = round(time.time() - t0)
    return rec


def _as_of_day(day, start, end, ends, t_try, dids):
    """The card history reads as the day it happened, not the day the replay ran: a card made this day is dated by its
    message (else the day's end), one closed this day by the day's end, and the dates in the history lines added this day
    say the day. updated_at and state_changed_at stay on the real clock: the engine compares them to see what changed.
    Every card the day touched is marked replayed: standing approvals never act on it."""
    import re
    import db
    lo, hi = start.astimezone().replace(tzinfo=None), end.astimezone().replace(tzinfo=None)
    real = {t_try.date(), dt.date.today()}
    stamp = re.compile("|".join(r"\b" + rf"{d.month}/{d.day}" + r"\b(?: \d{1,2}:\d{2} [AP]M)?" for d in real))
    con = db.connect()
    try:
        for iid, created, done, when, did, rp in con.execute(
                "SELECT id, created_at, done_at, source_when, coalesce(assistant_did, ''), replayed FROM live_items"
                " WHERE created_at >= ? OR done_at >= ? OR replayed IS NULL OR coalesce(assistant_did, '') <> ''", (t_try, t_try)).fetchall():
            sets = {}
            if created and created >= t_try:
                sets["created_at"] = when if when and lo <= when < hi else ends
            if done and done >= t_try:
                sets["done_at"] = ends
            old = dids.get(iid, "")
            if did != old and did.startswith(old):
                sets["assistant_did"] = old + stamp.sub(f"{day.month}/{day.day}", did[len(old):])
            if not rp:
                sets["replayed"] = day.isoformat()
            if sets:
                con.execute(f"UPDATE live_items SET {', '.join(k + '=?' for k in sets)} WHERE id=?", (*sets.values(), iid))
    finally:
        con.close()


def _no_alerts_later(pid):
    """Cards the replay leaves open are marked as already alerted, so the first check after Sync is back never alerts old
    matters (nothing is sent here: the file only says what not to send)."""
    import items
    sent = common.read_json(common.ALERTS_SENT, {}) or {}
    for it in items.rows("importance >= 1 AND state <> 'done'"):
        sent.setdefault(it["id"], {"at": common.now().isoformat(timespec="seconds"), "pass": pid})
    common.write_json(common.ALERTS_SENT, sent)


# --- a week -------------------------------------------------------------------------------------------------------------
def run_week(limit_days=WEEK):
    st = state()
    if not st.get("erased_at"):
        raise SystemExit("Run prepare and erase first.")
    if st.get("finished_at"):
        say(f"The replay reached today on {st['finished_at'][:10]}. Sync is off; turn it on in Settings when you are ready.")
        return 0
    say("Sync: " + _sync_off())
    _hold_lock("week")
    import gather
    z = zone()
    done_now, stopped = [], None
    try:
        if st.get("texts_folder"):
            import replay_sources as rs
            rs.spool_texts(st["texts_folder"], _first_day(st), _yesterday(), z, say)     # hourly backups that arrived since
        for _ in range(limit_days):
            st = state()
            day = next_day(st)
            if day > _yesterday():
                st["finished_at"] = dt.datetime.now().isoformat(timespec="seconds")
                save_state(st)
                replay_guard.mark_running(False)
                break
            say(f"{day:%a %m/%d}: reading and sorting ...")
            try:
                rec = run_day(day, z)
            except DayStopped as e:
                stopped = str(e)
                break
            except Exception as e:  # noqa: BLE001  said in the report and the error log; the day is read again on continue
                import traceback
                common.log_line(os.path.join(common.LOGS, "errors.log"), f"replay {day}\n{traceback.format_exc()}")
                stopped = f"{day}: {type(e).__name__}: {str(e)[:300]}"
                break
            all_days = [d for d in days() if d["day"] != rec["day"]] + [rec]
            common.write_json(DAYS, all_days)
            st["last_done"] = rec["day"]
            save_state(st)
            done_now.append(rec)
            say(f"  {_day_line(rec)}")
        else:
            st = state()
            if next_day(st) > _yesterday():
                st["finished_at"] = dt.datetime.now().isoformat(timespec="seconds")
                save_state(st)
                replay_guard.mark_running(False)
    finally:
        os.environ.pop(common.AI_NOW, None)
        gather.drop_lock()
    text = report(done_now, stopped)
    os.makedirs(REPORTS, exist_ok=True)
    path = os.path.join(REPORTS, f"report-{dt.datetime.now():%Y%m%d-%H%M%S}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    say("\n" + text)
    return 1 if stopped else 0


def _day_line(r):
    src = ", ".join(f"{k} {v}" for k, v in r["sources"].items())
    return (f"{r['day']} ({r['hours']}h): {src}; cards made {r.get('cards_made', 0)}, closed {r.get('cards_closed', 0)};"
            f" AI calls {r.get('ai_calls', 0)} ({r.get('ai_secs', 0) // 60} min); {r.get('secs', 0) // 60} min in all")


def _odd(rec, earlier):
    """What looked wrong on a day: a source with nothing that usually has something, and the day's own problems."""
    out = list(rec.get("problems") or [])
    for src, n in rec["sources"].items():
        seen = [d["sources"].get(src) for d in earlier if src in d["sources"]]
        if n == 0 and len(seen) >= 3 and sum(seen) / len(seen) >= 2:
            out.append(f"{src}: nothing on this day, against about {sum(seen) / len(seen):.0f} a day before it")
    return out


def report(done_now=None, stopped=None):
    st, every = state(), days()
    lines = []
    left = max(0, (_yesterday() - next_day(st)).days + 1) if not st.get("finished_at") else 0
    lines.append(f"Replay report, {dt.datetime.now():%Y-%m-%d %H:%M}")
    lines.append(f"Days done: {len(every)} (from {st.get('start')} to {st.get('last_done') or 'none yet'}); days left: {left}.")
    if done_now:
        lines.append("This run:")
        lines += [f"  {_day_line(r)}" for r in done_now]
    calls = sum(d.get("ai_calls", 0) for d in every)
    secs = sum(d.get("secs", 0) for d in every)
    lines.append(f"Cards made so far {sum(d.get('cards_made', 0) for d in every)}, closed {sum(d.get('cards_closed', 0) for d in every)}.")
    lines.append(f"AI calls so far: {calls}.")
    if every and left:
        per_calls, per_secs = calls / len(every), secs / len(every)
        lines.append(f"Estimate for the rest (from the days so far, a guess): about {per_calls * left:.0f} AI calls and "
                     f"{per_secs * left / 3600:.1f} hours over {left} days.")
    odd = []
    for i, r in enumerate(done_now or []):
        earlier = [d for d in every if d["day"] < r["day"]]
        odd += [f"{r['day']}: {o}" for o in _odd(r, earlier)]
    if stopped:
        odd.append(f"Stopped: {stopped}. Nothing of that day is lost; continue reads it again.")
    lines.append("Looked wrong:" if odd else "Looked wrong: nothing.")
    lines += [f"  {o}" for o in odd]
    if st.get("finished_at"):
        lines.append("The replay has reached today. Sync is still off: turn it on in Settings when you are ready; today's "
                     "messages come in with the first check after that.")
    else:
        lines.append("Sync is off. Next: python replay.py continue")
    return "\n".join(lines) + "\n"


def status():
    st, every = state(), days()
    if not st:
        say("No replay has been started. First: python replay.py dry-run, then prepare.")
        return 0
    say(f"Start {st.get('start')}; prepared {str(st.get('prepared_at') or 'no')[:16]}; erased {str(st.get('erased_at') or 'no')[:16]}.")
    say(f"Last finished day: {st.get('last_done') or 'none'}; {len(every)} day(s) done"
        + (f"; reached today on {st['finished_at'][:10]}" if st.get("finished_at") else f"; next {next_day(st)}") + ".")
    if every:
        say("Last day: " + _day_line(every[-1]))
    return 0


def show_report():
    got = sorted(os.listdir(REPORTS)) if os.path.isdir(REPORTS) else []
    if not got:
        say(report())
        return 0
    with open(os.path.join(REPORTS, got[-1]), encoding="utf-8") as f:
        say(f.read())
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rebuild the assistant's data day by day.")
    ap.add_argument("command", choices=("dry-run", "prepare", "erase", "run-week", "continue", "status", "report"))
    ap.add_argument("--start")
    ap.add_argument("--texts-folder")
    a = ap.parse_args(argv)
    if a.command == "dry-run":
        return dry_run()
    if a.command == "prepare":
        return prepare(a.start, a.texts_folder)
    if a.command == "erase":
        return erase()
    if a.command in ("run-week", "continue"):
        return run_week()
    if a.command == "status":
        return status()
    return show_report()


if __name__ == "__main__":
    sys.exit(main())
