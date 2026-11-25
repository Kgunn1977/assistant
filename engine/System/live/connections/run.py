r"""Read what is new from every connection of one kind. Run by the timed pass, once per kind.

    python run.py --kind email --run-id <pass id>
    python run.py --kind email --dry-run          fetch and report, write nothing
    python run.py --kind email --only c3          one connection
    python run.py --check                         one harmless read on every connection, nothing written

Each connection is read on its own: one failing is reported by name and never stops the others.
Exit 0 when every connection of the kind was read, 1 when any failed. Nothing printed, logged or
recorded here ever holds a sign-in.
"""
import argparse
import os
import sys
import time

LIVE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if LIVE not in sys.path:
    sys.path.insert(0, LIVE)
import connections  # noqa: E402
import db  # noqa: E402
import keys  # noqa: E402
from connections import _store  # noqa: E402


class Ctx:
    """What a connection's gather() is handed."""

    def __init__(self, run_id, dry_run, limit):
        self.run_id = run_id
        self.dry_run = dry_run
        self.limit = limit          # most messages to fetch from one account in one pass
        self.events = []            # calendar connections add their events here


def _plain(e):
    return keys.scrub(f"{type(e).__name__}: {e}")[:400]


def check():
    bad = 0
    for c in connections.listed():
        try:
            print("ok     ", connections.module(c["type"]).check(c))
        except Exception as e:  # noqa: BLE001
            bad += 1
            print("PROBLEM", c.get("label") or c["id"], "-", _plain(e))
    return 1 if bad else 0


def sync_mail(a):
    """The mail's slow work, its own step of the pass after the new mail is read and filed (gather.py), with its own time:
    changes made elsewhere, the backfill of state, the folder list, then conversations and snoozes. Its own source
    ("email-sync"): a plain progress line with each mailbox's seconds, and a mailbox it could not do said in full; it never
    marks the new mail as not read."""
    ctx = Ctx(a.run_id, a.dry_run, a.limit)
    syncing = [c for c in connections.listed("email") if hasattr(connections.module(c["type"]), "sync")]
    if syncing:                 # each pass starts with the next mailbox, so a slow one never keeps the others waiting
        first = int(_store.cursor("", "sync_next") or 0) % len(syncing)
        syncing = syncing[first:] + syncing[:first]
    else:
        first = 0
    total_end = time.time() + a.sync_seconds
    done, trouble = [], []

    def note(more=""):          # written after every mailbox, so a step stopped at its limit still says what each took
        if syncing and not a.dry_run:   # what went wrong first, then " || " and the progress (gather.py names only the first part as the problem)
            went = "; ".join(done) + more
            db.record_source_status(a.run_id, "email-sync", "degraded" if trouble else "ok",
                                    "; ".join(trouble) + (" || " + went.lstrip("; ") if trouble and went else went))
    for i, c in enumerate(syncing):
        label = c.get("label") or c.get("address") or c["id"]
        if i and time.time() >= total_end:      # out of time: the rest come first next pass
            later = [x.get("label") or x.get("address") or x["id"] for x in syncing[i:]]
            done.append("next check: " + ", ".join(later))
            break
        end = time.time() + max(0, total_end - time.time()) / (len(syncing) - i)
        t0 = time.time()
        if not a.dry_run:       # moved on before the mailbox is read: one stopped at the step's limit is not first again next pass
            _store.set_cursor("", "sync_next", str((first + i + 1) % len(syncing)))
        note(f"; now reading {label}")
        try:
            line = connections.module(c["type"]).sync(c, ctx, end)
            done.append(f"{label}: {line} ({time.time() - t0:.0f}s)")
            print(f"  {done[-1]}", flush=True)
        except Exception as e:  # noqa: BLE001  the new mail is stored; only the marks wait for the next pass, and the owner is told
            trouble.append(f"{label}: changes made elsewhere and folders were not read ({_plain(e)}, after {time.time() - t0:.0f}s)")
            print(f"  SYNC PROBLEM {trouble[-1]}", flush=True)
        note()
    t0 = time.time()
    try:                    # conversations the service gave no id for; snoozed email whose time has come
        import mail
        mail.rethread()
        mail.wake()
        done.append(f"conversations and snoozes ({time.time() - t0:.0f}s)")
    except Exception as e:  # noqa: BLE001  the mail is stored; these wait for the next pass, and the owner is told
        trouble.append(f"conversations and snoozes were not updated ({_plain(e)})")
        print(f"  SYNC PROBLEM {trouble[-1]}", flush=True)
    note()
    return 0


RELOAD_SECONDS = 60             # the history reload's own time each pass, all mailboxes together (gather.py gives it its own step)


def reload_history(a):
    """The full history reload's portions (Settings, Tools: Reload all email history): every mailbox with one running gets a
    share of the time, at least one portion. Its own source, "email-reload": a plain progress line, never the new mail's."""
    want = [c for c in connections.listed("email") if hasattr(connections.module(c["type"]), "reload")]
    end_all = time.time() + RELOAD_SECONDS
    done, trouble = [], []
    for i, c in enumerate(want):
        label = c.get("label") or c.get("address") or c["id"]
        end = time.time() + max(0, end_all - time.time()) / (len(want) - i)
        try:
            line = connections.module(c["type"]).reload(c, end)
            if line:
                print(f"  {label}: {line}")
                done.append(f"{label}: {line}")
        except Exception as e:  # noqa: BLE001  the portion is read again next pass; the owner is told
            trouble.append(f"{label}: the history reload's portion was not read ({_plain(e)})")
            print(f"  RELOAD PROBLEM {trouble[-1]}")
    if not a.dry_run and (done or trouble):
        db.record_source_status(a.run_id, "email-reload", "degraded" if trouble else "ok", "; ".join(trouble or done))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind")
    ap.add_argument("--run-id")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--sync-seconds", type=int, default=_store.SYNC_SECONDS)   # the slow work after the new mail, all mailboxes together
    ap.add_argument("--only")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check()
    if not a.kind:
        ap.error("--kind is needed")
    if a.kind == "email-reload":
        return reload_history(a)
    if a.kind == "email-sync":
        return sync_mail(a)
    conns = [c for c in connections.listed(a.kind) if not a.only or c["id"] == a.only]
    ctx = Ctx(a.run_id, a.dry_run, a.limit)
    failures, degraded, lines = [], [], []
    for c in conns:
        label = c.get("label") or c.get("address") or c["id"]
        t0 = time.time()
        try:
            line = connections.module(c["type"]).gather(c, ctx)
            status = "degraded" if str(line).startswith("DEGRADED") else "ok"
        except Exception as e:  # noqa: BLE001
            line, status = _plain(e), "failed"
        if a.kind == "email" and status != "degraded":
            line = f"{line} ({time.time() - t0:.0f}s)"
        print(f"  {label}: {'FAILED ' if status == 'failed' else ''}{line}")
        lines.append(f"{label}: {line}")
        if status == "failed":
            failures.append(f"{label}: {line}")
        elif status == "degraded":
            degraded.append(str(line))
        if not a.dry_run and (len(conns) > 1 or a.kind == "email"):
            db.record_source_status(a.run_id, f"{a.kind}:{label}", "ok" if status == "degraded" else status, line)
    if a.kind == "calendar" and not a.dry_run and conns:
        # the window is rebuilt whole; what is no longer there is dropped only when every calendar answered
        _store.calendar_events(ctx.events, prune=not failures)
    if not a.dry_run and not a.only:
        if failures:
            db.record_source_status(a.run_id, a.kind, "failed", "; ".join(failures))
        else:
            detail = degraded[0] if degraded else ("; ".join(lines) if len(conns) == 1 else f"all {len(conns)} ok")
            db.record_source_status(a.run_id, a.kind, "ok", detail)
    for d in degraded:
        print(d)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
