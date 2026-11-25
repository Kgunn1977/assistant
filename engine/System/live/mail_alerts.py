r"""Phone notifications for new mail that matters, sent after the pass has stored its mail.

    run(pass_id)    one grouped notification for the new inbox mail that matters; returns (sent, skipped, problems)

The owner's Settings choice (notifications, "mail"): "matters" (the default), "every" (every new email in the inbox) or "none".
Mail matters, decided by script with no AI call, when its sender always gets through (Settings, What reaches you), when it
is in a conversation the owner has written in (a reply to a thread they are in), or when an open card the assistant's sort
already marked important rests on it (only if that sort has already run; the sort is never called for a notification). Several arriving in one pass make
one notification; one email is never alerted twice (alerts_mail_sent.json); quiet hours send nothing and the mail notifications when they
end. An email whose card was already alerted is not alerted again. Delivery is alert.send; the tap opens the email.
"""
import datetime as dt
import os

import common

SENT = os.path.join(common.HOME, "alerts_mail_sent.json")
MODES = ("matters", "every", "none")
FRESH_HOURS = 24
MOST_LISTED = 8


def mode():
    got = (common.settings().get("alerts") or {}).get("mail")
    return got if got in MODES else "matters"


def _new_inbox_mail(db, cutoff):
    return db.query(
        """SELECT m.id, m.from_key, coalesce(s.from_name, ''), coalesce(m.subject, '')
           FROM messages m JOIN mail_state s ON s.message_id = m.id
           WHERE m.channel = 'email' AND m.direction = 'in' AND s.inbox AND NOT coalesce(s.trashed, false)
             AND s.unread AND m.ts >= ? ORDER BY m.ts""", (cutoff,))


def _my_threads(db, ids):
    """The ids among these emails that sit in a conversation the owner has written in."""
    if not ids:
        return set()
    got = db.query("SELECT m.id FROM messages m WHERE m.id IN (%s) AND m.thread_id IS NOT NULL AND EXISTS "
                   "(SELECT 1 FROM messages o WHERE o.thread_id = m.thread_id AND o.direction = 'out' AND o.channel = 'email')"
                   % ",".join(str(int(i)) for i in ids))
    return {r[0] for r in got}


def _link(mid=None):
    import setup_steps
    site = setup_steps.page_address().rstrip("/")
    return f"{site}/#mail={mid}" if site and mid else (site or "")


def _who(frm, name):
    return " ".join(str(name or "").split()) or str(frm or "").split(":", 1)[-1]


def build(rows):
    """The notification for these (id, from_key, name, subject) rows: one email, or one grouped alert."""
    if len(rows) == 1:
        mid, frm, name, subject = rows[0]
        out = {"title": _who(frm, name)[:120], "message": (subject or "(no subject)")[:900], "priority": 4, "tags": ["email"]}
        click = _link(mid)
    else:
        out = {"title": f"{len(rows)} emails that matter", "priority": 4, "tags": ["email"],
               "message": "\n".join(f"- {_who(f, n)[:40]}: {(s or '(no subject)')[:100]}" for _, f, n, s in rows[:MOST_LISTED])[:900]}
        click = _link()
    if click:
        out["click"] = click
    return out


def run(pass_id, send=None, db=None):
    """Alert for new mail that matters. `send` and `db` are for tests; by default alert.send and the database."""
    import replay_guard
    replay_guard.refuse("a new-mail notification")
    import alert
    import filters
    import items
    import settings_page
    if db is None:
        import db
    send = send or alert.send
    if mode() == "none" or not alert.enabled():
        return 0, 0, []
    first = not os.path.exists(SENT)
    seen = common.read_json(SENT, {}) or {}
    rows = [r for r in _new_inbox_mail(db, common.now() - dt.timedelta(hours=FRESH_HOURS)) if str(r[0]) not in seen]
    now = common.now().isoformat(timespec="seconds")
    if first:           # the first run only learns what is already there: no flood on switching on
        common.write_json(SENT, {str(r[0]): {"at": now, "pass": "baseline"} for r in rows})
        return 0, 0, []
    if not rows:
        return 0, 0, []
    if settings_page.in_quiet():
        return 0, len(rows), []
    cards = items.rows("importance >= 1 AND state <> 'done'")
    on_card = {int(i) for c in cards for i in (c.get("source_messages") or []) if str(i).lstrip("-").isdigit()}
    alerted = common.read_json(common.ALERTS_SENT, {}) or {}
    covered = {int(i) for c in cards if c["id"] in alerted for i in (c.get("source_messages") or []) if str(i).lstrip("-").isdigit()}
    every = mode() == "every"
    mine = set() if every else _my_threads(db, [r[0] for r in rows])
    pick, quiet_done = [], {}
    for r in rows:
        mid, frm, name, _subject = r
        if mid in covered:
            quiet_done[str(mid)] = {"at": now, "pass": pass_id}      # its card already alerted
        elif every or mid in mine or mid in on_card or filters.gets_through(frm, name):
            pick.append(r)
        # mail that does not matter is left unmarked and costs nothing next pass
    problems, sent = [], 0
    if pick:
        status, detail = send(build(pick))
        common.log_line(common.PASS_LOG, f"mail notification {status}: {detail}: {len(pick)} email(s)")
        if status == "sent":
            sent = 1
            quiet_done.update({str(r[0]): {"at": now, "pass": pass_id} for r in pick})
        elif status == "failed":
            problems.append(f"the mail notification could not be sent: {detail}")
    if quiet_done:
        seen.update(quiet_done)
        common.write_json(SENT, seen)
    return sent, (len(pick) if not sent and not problems else 0), problems
