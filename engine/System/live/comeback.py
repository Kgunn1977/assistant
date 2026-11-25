r"""Cards that come back by themselves: a card waiting on someone, and cards that have sat untouched.

ITEMS.md ("Design round 2") is the contract. Both run in the pass, on dates and counts only: no Claude.

    waiting(pass_id)   a card waiting on someone returns to the owner on its check-back date, or when that
                       person writes again, whichever is first (setting waiting_back_days; 0 is never)
    old(pass_id)       the owner's own cards untouched for the set number of days are asked about once, all
                       on one card (setting old_card_days; 0 is never). Nothing is dropped without a press.
"""
import datetime as dt
import json

import common
import filters

OLD_KEY = "live:old-cards"
NOT_THESE = ("rule:", "live:old-cards", "live:newsender-", "live:setup-", "improve:", "built:", "live:rsi-")


def add_working_days(day, n):
    while n > 0:
        day += dt.timedelta(days=1)
        if day.weekday() < 5:
            n -= 1
    return day


def working_days_between(a, b):
    n, day = 0, a
    while day < b:
        day += dt.timedelta(days=1)
        if day.weekday() < 5:
            n += 1
    return n


def _stamp(when):
    return f"{when.month}/{when.day} {when.strftime('%I:%M %p').lstrip('0')}"


def _mine(key):
    return not str(key or "").startswith(NOT_THESE)


ELSE = "someone else"


def _owner_names():
    return {n for n in ("You", "you", common.owner()) if n}


def _not_owner(name):
    """The name a waiting card waited on, or "" when it names the owner himself: his own card waits on someone else."""
    name = " ".join(str(name or "").split())
    return "" if name in _owner_names() else name


def clean_owner_notes():
    """Open cards whose come-back history or question names the owner as the one waited on (written before 11/18) are
    rewritten to say someone else, the words a come-back writes now. Returns how many cards changed."""
    import db
    swaps = []
    for n in _owner_names():
        swaps += [(f"it waited on {n} for ", f"it waited on {ELSE} for "), (f"No reply from {n} in ", f"No reply from {ELSE} in "),
                  (f"{n} wrote again. ", f"{ELSE} wrote again. ")]
    changed = 0
    for iid, did, asks, extra in db.query("SELECT id, assistant_did, asks, extra FROM live_items WHERE state <> 'done'"):
        new_did, new_asks = did or "", asks or ""
        for a, b in swaps:
            new_did, new_asks = new_did.replace(a, b), new_asks.replace(a, b)
        ex = _extra(extra)
        cb = ex.get("came_back")
        fix_cb = isinstance(cb, dict) and str(cb.get("who") or "").strip() in _owner_names()
        if new_did == (did or "") and new_asks == (asks or "") and not fix_cb:
            continue
        if fix_cb:
            cb["who"] = ELSE
        db.execute("UPDATE live_items SET assistant_did=?, asks=?, extra=? WHERE id=?",
                   (new_did if did is not None else None, new_asks if asks is not None else None, json.dumps(ex), iid))
        changed += 1
    return changed


def _extra(raw):
    try:
        got = json.loads(raw) if raw else {}
    except ValueError:
        got = {}
    return got if isinstance(got, dict) else {}


def waiting(pass_id):
    """Returns how many waiting cards came back."""
    import db
    import items
    items.ensure()
    clean_owner_notes()
    days = filters.get()["waiting_back_days"]
    if not days:
        return 0
    now, today = common.now(), dt.date.today()
    back = 0
    for iid, key, who, started, check, msgs, did, extra in db.query(
            """SELECT id, source_key, source_who, state_changed_at, checkback_date, source_messages, assistant_did, extra
               FROM live_items WHERE state = 'in_motion' AND shelf IS NULL"""):
        if not _mine(key):
            continue
        ids = [int(m) for m in json.loads(msgs or "[]")[:25] if str(m).isdigit()]
        wrote = None
        if ids:
            # the newest message that came in since it was set aside. The newest is picked here, not in the query: a max() over
            # this list failed inside the database engine on one day's data (11/17/26), which stopped the whole come-back step
            got = db.query(f"SELECT ts FROM messages WHERE id IN ({','.join('?' for _ in ids)}) AND direction='in'", tuple(ids))
            wrote = max((r[0] for r in got if r[0] is not None and r[0] > started), default=None)
        due = check or add_working_days(started.date(), days)
        if not wrote and today < due:
            continue
        waited = working_days_between(started.date(), today)
        ex = _extra(extra)
        who = " ".join(str(who or "").split())
        who = who.split(":", 1)[-1].strip() if who.split(":", 1)[0].lower() in common.sender_kinds() - {"text"} else who
        who = _not_owner(ex.get("waiting_on")) or _not_owner(who) or ELSE     # his own card: the one it waits on is never him
        n = f"{waited} working day{'s' if waited != 1 else ''}"
        if wrote:
            ask = f"{who} wrote again. Read it, then wait longer, write to them, or mark it Done."
            line = f"Back {_stamp(now)}: {who} wrote again {_stamp(wrote)}. It was waiting on them since {started.month}/{started.day}."
            status = "Back: they wrote"
        else:
            ask = f"No reply from {who} in {n}. Wait longer, write to them, or mark it Done?" if waited else f"No reply yet from {who}. Wait longer, write to them, or mark it Done?"
            line = f"Back {_stamp(now)}: no word yet from {who} since {started.month}/{started.day}."
            status = "Back: still no reply"
        ex["came_back"] = {"why": "message" if wrote else "date", "who": who, "waited_days": waited, "wait_days": days}
        db.execute("UPDATE live_items SET state='yours', status=?, asks=?, checkback_date=NULL, extra=?, assistant_did=?,"
                   " answer=NULL, updated_at=?, state_changed_at=?, last_pass=? WHERE id=?",       # a new question: no answer is waiting
                   (status, json.dumps([ask]), json.dumps(ex), f"{did}\n{line}" if did else line, now, now, pass_id, iid))
        back += 1
    return back


def _old_words(days):
    return {7: "a week", 14: "two weeks", 30: "a month"}.get(days, f"{days} days")


def old(pass_id):
    """Returns how many cards are on the asking card now."""
    import card
    import db
    import items
    items.ensure()
    days = filters.get()["old_card_days"]
    now = common.now()
    listed = []
    if days:
        for iid, key, title, state, draft, kind, src, changed, kept, made, asked in db.query(
                """SELECT id, source_key, title, state, draft, kind, source_when, state_changed_at, kept_at, created_at, asked_old_at
                   FROM live_items WHERE state IN ('question', 'yours') AND shelf IS NULL"""):
            if not _mine(key):
                continue
            touch = max(t for t in (src, changed, kept, made) if t)
            age = (now - touch).days
            if asked and asked >= touch:
                listed.append((iid, title, age, state, draft, kind))        # asked already, not decided yet
            elif age >= days:
                db.execute("UPDATE live_items SET asked_old_at=? WHERE id=?", (now, iid))
                listed.append((iid, title, age, state, draft, kind))
    have = db.query("SELECT id, state FROM live_items WHERE source_key=?", (OLD_KEY,))
    if not listed:
        if have and have[0][1] != "done":
            items.upsert(OLD_KEY, pass_id, state="done", status="Answered", extra={"old_cards": []})
        return 0
    listed.sort(key=lambda r: -r[2])
    short = dict(db.query("SELECT id, short_header FROM live_items WHERE short_header IS NOT NULL"))
    rows = [{"id": i, "header": card.header_of(t, short.get(i)), "days": a,
             "needs": card.needs({"state": s, "draft": d, "kind": k})} for i, t, a, s, d, k in listed]
    n = len(rows)
    items.upsert(OLD_KEY, pass_id, kind="question", area="Personal", state="question", status=None,
                 title=f"{n} card{'s have' if n != 1 else ' has'} sat for {_old_words(days)}",
                 detail="Nothing has happened on these since they were made or last touched. Say for each one whether to keep it, "
                        "snooze it, or mark it Done. Nothing is marked Done unless you say so.",
                 asks=["Keep, snooze or mark Done each one."], why=f"Nothing has happened on them for {days} days or more.",
                 extra={"old_cards": rows})
    return n
