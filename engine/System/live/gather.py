r"""The gather pass: code only, no AI.

    python gather.py

Reads every connection the owner has set up and turned on (connections\; nothing
is sent, moved or deleted), then says what is new since the last pass. Safe to
run every 15 minutes: one pass at a time, each kind of source on its own so one
failing does not stop the others, and the follow-on filing steps run only when
something new arrived. Nothing connected means nothing is gathered and the pass
still runs clean.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time

import common
import db
import limits

CORE = common.paths.CORE
READ = os.path.join(common.paths.CONNECTIONS, "run.py")     # reads every connection of one kind
ORDER = ("email", "calendar", "sms")      # a taught connection type's kind is read after these
SOURCE_SECONDS = 120                                        # a kind with no limit of its own

# filing steps, only when something new arrived: name, script, args, takes --run-id
FOLLOW = [
    ("contacts", os.path.join(CORE, "refresh_contacts.py"), (), False),
    ("extract", os.path.join(CORE, "extract_text.py"), (), True),
]


def sources_on():
    """The kinds of source to read this pass: (kind, seconds allowed). A kind is read when the
    owner has it turned on in their personal settings and has at least one connection of it."""
    import connections
    on = {str(s).strip().lower() for s in (common.personal().get("sources") or [])}
    kinds = []
    for c in connections.listed():
        if c.get("kind") in on and c["kind"] not in kinds:
            kinds.append(c["kind"])
    kinds.sort(key=lambda k: ORDER.index(k) if k in ORDER else len(ORDER))
    return [(k, limits.SOURCE.get(k) or common.channels().get(k, {}).get("seconds") or SOURCE_SECONDS) for k in kinds]


GATHER_STATE = os.path.join(common.HOME, "gather_state.json")


# --- one pass at a time --------------------------------------------------------
def _alive(pid):
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True,
                             text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return True
    return str(pid) in out


def take_lock(pass_id=None):
    """True when this process now holds the pass lock. A lock left by a dead
    process is taken over, and said in the error log: that pass ended without a
    word (its process crashed or was ended), and the log names the step it was in.
    A pass still holding it past limits.STALE_LOCK has hung: it is ended, with
    everything it started, and the lock is taken."""
    for _ in range(2):
        try:
            fd = os.open(common.LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, json.dumps({"pid": os.getpid(), "at": time.time(), "pass": pass_id, "step": "starting"}).encode())
            os.close(fd)
            return True
        except FileExistsError:
            held = common.read_json(common.LOCK) or {}
            age = time.time() - held.get("at", 0)
            if held.get("pid") and _alive(held["pid"]):
                if age < limits.STALE_LOCK or str(held.get("pass") or "").startswith("replay-"):
                    return False        # a replay holds the lock for hours on purpose: never ended as hung
                limits.end_tree(held["pid"])
                common.log_line(common.PASS_LOG, f"a check (process {held['pid']}) still held the lock after"
                                                 f" {age / 60:.0f} minutes and was ended so this one can run")
            elif held.get("pid"):           # its process is gone and it never let go: it ended suddenly
                said = (f"pass {held.get('pass') or '(started ' + time.strftime('%H:%M', time.localtime(held.get('at') or 0)) + ')'}: "
                        f"it ended suddenly, without finishing or writing its result (its process crashed or was ended), "
                        f"while in step '{held.get('step') or 'unknown'}'. This check carries on from where the data stands.")
                common.log_line(os.path.join(common.LOGS, "errors.log"), said)
                common.log_line(common.PASS_LOG, said)
            try:
                os.remove(common.LOCK)
            except OSError:
                return False
    return False


def drop_lock():
    held = common.read_json(common.LOCK) or {}
    if held.get("pid") == os.getpid():
        os.remove(common.LOCK)


# --- helpers --------------------------------------------------------------------
def run_script(path, *args, run_id=None, timeout=600, finishing=False):
    """(ok, last lines of output). A crash or timeout is a False, never a raise. finishing: the pass's last step (the page
    refresh), which may run past the point where new work stops."""
    cmd = [sys.executable, path, *args] + (["--run-id", run_id] if run_id else [])
    timeout = limits.finish_cap(timeout) if finishing else limits.cap(timeout)
    limits.step(os.path.basename(path))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, env=os.environ.copy(),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return False, f"stopped at its {timeout:.0f} second limit"
    except OSError as e:
        return False, f"could not start: {e}"
    text = (r.stdout if r.returncode == 0 else (r.stderr or r.stdout) or "").strip()
    tail = " | ".join(l.strip() for l in text.splitlines()[-4:] if l.strip())
    if r.returncode != 0:
        return False, f"exit {r.returncode}: {tail or 'no output'}"[:600]
    return True, tail[:600]


def _marks():
    return db.query("SELECT (SELECT coalesce(max(id),0) FROM messages),"
                    " (SELECT coalesce(max(id),0) FROM attachments),"
                    " (SELECT coalesce(max(id),0) FROM documents)")[0]


def state():
    s = common.read_json(GATHER_STATE)
    if s is None or "page_mark_document" not in s:
        # first pass: only pages arriving from now on are the live system's to read
        s = dict(s or {}, page_mark_document=_marks()[2], pages_skipped=(s or {}).get("pages_skipped", []))
        common.write_json(GATHER_STATE, s)
    return s


def pending_pages():
    """Pages with no readable text (a picture or an image-only PDF) that arrived
    since the live system started and still need reading:
    (page id, document id, page number, file path, message id). A picture sent
    by text is the engine's own describe step's, not this one's."""
    s = state()
    rows = db.query(
        """SELECT p.id, d.id, p.page_no, a.saved_path, d.message_id
           FROM pages p JOIN documents d ON d.id = p.document_id
           JOIN attachments a ON a.id = d.attachment_id
           WHERE p.method = 'needs_vision' AND d.id > ?
             AND NOT (d.doc_type = 'image' AND EXISTS
                      (SELECT 1 FROM messages m WHERE m.id = d.message_id AND m.channel = 'sms'))
           ORDER BY d.id, p.page_no""", (s["page_mark_document"],))
    skipped = set(s.get("pages_skipped", []))
    return [r for r in rows if r[0] not in skipped]


def _reloading():
    try:
        from connections import _store
        return _store.reloads_running()
    except Exception:  # noqa: BLE001  no reload step this pass; the new mail is never held up by it
        return False


def unjudged():
    bound, upto = common.until_sql()        # a replay's day: what comes after its end is not owed yet
    return db.query("""SELECT count(*) FROM messages m WHERE NOT EXISTS
                       (SELECT 1 FROM answered a WHERE a.domain='judged'
                        AND a.key = 'msg:' || m.id)""" + bound, tuple(upto))[0][0]


def texted_images_waiting():
    """Pictures sent by text and not yet described; those the replay stored are not owed a description."""
    skip, upto = common.describe_sql()
    return db.query("""SELECT count(*) FROM pages p JOIN documents d ON d.id = p.document_id
                       JOIN messages m ON m.id = d.message_id
                       WHERE p.method = 'needs_vision' AND d.doc_type = 'image'
                         AND m.channel = 'sms'""" + skip, tuple(upto))[0][0]


# --- the pass --------------------------------------------------------------------
def _catalog_only(pass_id, t0):
    """While the setup's envelope catalog is built (onboard.holding), nothing new is pulled in from any account: this pass
    builds the next portion of the catalog instead (catalog.py), so the first messages are judged with context."""
    import catalog
    limits.step("history catalog")
    problems, sources = [], {}
    if catalog.started():
        line = catalog.step(pass_id, time.time() + limits.cap(limits.CATALOG))
        sources["catalog"] = {"status": "degraded" if "PROBLEM" in line else "ok", "detail": line, "at": common.now()}
        if "PROBLEM" in line:
            problems.append(line[:400])
    else:
        sources["catalog"] = {"status": "skipped", "detail": "new messages wait until setup has chosen how far back to look",
                              "at": common.now()}
    return {"pass_id": pass_id, "secs": round(time.time() - t0, 1), "new_messages": [], "new_in": 0, "by_channel": {},
            "new_attachments": 0, "pages_waiting": 0, "texted_images_waiting": 0, "unjudged": unjudged(), "sources": sources,
            "follow": {}, "timing": {"catalog": round(time.time() - t0, 1)}, "problems": problems, "holding": True}


def gather(pass_id):
    """Run the intake. Returns a plain dict the caller logs and acts on."""
    t0 = time.time()
    problems, sources, timing = [], {}, {}
    state()
    import onboard
    if onboard.holding():
        return _catalog_only(pass_id, t0)
    before = _marks()
    db.execute("INSERT INTO runs (run_id, started_at, outcome, note) VALUES (?,?, 'running', 'live pass')",
               (pass_id, common.now()))

    for name, timeout in sources_on():
        t1 = time.time()
        ok, tail = run_script(READ, "--kind", name, run_id=pass_id, timeout=timeout)
        timing[name] = round(time.time() - t1, 1)
        sources[name] = {"status": "ok" if ok else "failed", "detail": tail, "at": common.now()}
        if not ok:
            problems.append(f"{name} could not be read: {tail[:200]}")
        elif tail.startswith("DEGRADED") or "DEGRADED" in tail:
            sources[name]["status"] = "degraded"
            said = [l.strip() for l in tail.splitlines() if "DEGRADED" in l] or [tail]      # the problem itself, never the progress before it
            problems.append(f"{name}: " + " | ".join(said)[:400])

    # what each source said of itself, mailbox by mailbox
    for src, status, detail, at in db.query(
            "SELECT source, status, detail, updated_at FROM source_status WHERE run_id=?", (pass_id,)):
        if src in sources and sources[src]["status"] != "ok":
            continue
        sources[src] = {"status": status, "detail": detail or "", "at": at}
        if status != "ok":
            problems.append(f"{src}: {status} ({(detail or '')[:400]})")

    mid = _marks()
    new_msgs = db.query("SELECT id, channel, direction FROM messages WHERE id > ? ORDER BY id", (before[0],))
    new_atts = mid[1] - before[1]

    follow = {}
    if new_msgs or new_atts:
        for name, path, args, takes_run in FOLLOW:
            if not limits.enough(20):
                follow[name] = "put off: the check was out of time"
                problems.append(f"{name} step waits until the next time I check: out of time")
                continue
            t1 = time.time()
            ok, tail = run_script(path, *args, run_id=pass_id if takes_run else None, timeout=limits.FOLLOW)
            timing[name] = round(time.time() - t1, 1)
            follow[name] = "ok" if ok else f"failed: {tail[:200]}"
            if not ok:
                problems.append(f"{name} step failed: {tail[:200]}")

    # the mail's slow work (changes made elsewhere, the backfill, folders, conversations, snoozes): its own step after the new
    # mail and its filing, with its own limit, so it never delays new mail or makes it count as not read.
    if any(name == "email" for name, _t in sources_on()) and limits.enough(limits.SYNC + 20):
        limits.step("mail sync")
        t1 = time.time()
        ok, tail = run_script(READ, "--kind", "email-sync", run_id=pass_id, timeout=limits.SYNC)
        timing["email-sync"] = round(time.time() - t1, 1)
        got = db.query("SELECT status, detail FROM source_status WHERE run_id=? AND source='email-sync'", (pass_id,))
        status, detail = (got[0][0], got[0][1] or "") if got else ("ok", "")
        if not ok and "limit" in tail:      # stopped at its limit: each mailbox's work is kept as it goes, and goes on next pass
            detail = (detail + "; " if detail else "") + "stopped at its limit, goes on the next time I check"
            db.record_source_status(pass_id, "email-sync", status, detail)
        elif not ok:
            status, detail = "degraded", (detail + "; " if detail else "") + tail[-400:]
        sources["email-sync"] = {"status": status, "detail": detail, "at": common.now()}
        if status != "ok":      # the problem is what went wrong, in full: never the progress lines after " || " (connections/run.py)
            problems.append(f"email-sync: {status} ({detail.split(' || ')[0][:400]})")

    # the full history reload (Settings, Tools): its own step, after the new mail and its filing, with its own limit, so it
    # never delays new mail; not in an update's check pass. Stopped at its limit, it goes on from its last portion next pass.
    if os.environ.get("ASSISTANT_QUICK_PASS") and any(name == "email" for name, _t in sources_on()):
        # left out of an update's check pass on purpose: said so, so the update never takes it for a source that failed
        sources["email-reload"] = {"status": "skipped", "detail": "left out of an update's check", "at": common.now()}
    elif _reloading() and limits.enough(limits.RELOAD + 20):
        limits.step("history reload")
        t1 = time.time()
        ok, tail = run_script(READ, "--kind", "email-reload", run_id=pass_id, timeout=limits.RELOAD)
        timing["email-reload"] = round(time.time() - t1, 1)
        got = db.query("SELECT status, detail FROM source_status WHERE run_id=? AND source='email-reload'", (pass_id,))
        if got:
            sources["email-reload"] = {"status": got[0][0], "detail": got[0][1] or "", "at": common.now()}
            if got[0][0] != "ok":
                problems.append(f"email-reload: {got[0][0]} ({(got[0][1] or '')[:400]})")
        elif not ok:
            sources["email-reload"] = {"status": "ok", "detail": "history reload: stopped at its limit this time; it goes on the next time I check",
                                       "at": common.now()}


    by_channel = {}
    for _id, channel, _dir in new_msgs:
        by_channel[channel] = by_channel.get(channel, 0) + 1
    result = {
        "pass_id": pass_id,
        "secs": round(time.time() - t0, 1),
        "new_messages": [r[0] for r in new_msgs],
        "new_in": sum(1 for r in new_msgs if r[2] == "in"),
        "by_channel": by_channel,
        "new_attachments": int(new_atts),
        "pages_waiting": len(pending_pages()),
        "texted_images_waiting": texted_images_waiting(),
        "unjudged": unjudged(),
        "sources": sources,
        "follow": follow,
        "timing": timing,
        "problems": problems,
    }
    db.execute("UPDATE runs SET outcome=?, finished_at=?, note=? WHERE run_id=?",
               ("failed" if any(v["status"] == "failed" for v in sources.values()) else "complete",
                common.now(), f"live check: {len(new_msgs)} new messages", pass_id))
    return result


def summary(g):
    chans = ", ".join(f"{n} {c}" for c, n in sorted(g["by_channel"].items())) or "none"
    bad = [s for s, v in g["sources"].items() if v["status"] not in ("ok", "skipped")]
    return (f"gather {g['secs']:.0f}s new messages: {len(g['new_messages'])} ({chans}),"
            f" attachments: {g['new_attachments']}, pages waiting: {g['pages_waiting']},"
            f" sources: {('all ok' if g['sources'] else 'none on') if not bad else 'PROBLEM ' + ', '.join(bad)}"
            + "".join(f" | {name}: {g['sources'][name]['detail'][:600]}" for name in ("email-sync", "email-reload", "catalog")
                      if name in g["sources"] and g["sources"][name]["status"] == "ok" and g["sources"][name].get("detail")))


def main():
    if not take_lock():
        print("another check is running; not starting")
        return 3
    try:
        pass_id = "live-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        g = gather(pass_id)
        line = f"pass {pass_id} (gather only) {summary(g)}"
        common.log_line(common.PASS_LOG, line)
        print(line)
        for p in g["problems"]:
            print("  problem:", p)
        return 0
    finally:
        drop_lock()


if __name__ == "__main__":
    sys.exit(main())
