r"""How often the owner is in touch with each person, from their real two-way messages: mail, texts and any other kind read.

Each contact (contacts table) carries, recounted at every pass from the messages themselves:
    sent_count      messages the owner sent them (email to their address, a text to their number, a message in a
                    conversation they wrote in)
    received_count  messages from them that are personal: not from an automatic address, not mailing-list mail (an
                    unsubscribe link), not judged noise, ignore or phishing
    sent_90, received_90   the same in the last 90 days
    weeks_written   of the last 13 weeks, how many the owner wrote to them in
    strength        a recent-weighted measure of two-way contact: each of those messages in the last 90 days counts
                    less the older it is (halving about every three weeks); 0 when the owner never wrote to them or
                    they never wrote personally, so a mailing list the owner once answered is not a frequent contact

A person is the sum of their keys (person_id). It is one input: a higher place on the page and a lean toward showing their
message; it never overrides the owner's own rules, junk lists, or how strict the filter is.

    refresh(con=None, now=None)   recount every contact (each pass): a quick read, the counting with the database closed,
                                  one short write of what changed
    for_person(con, person_id or key)   {"level": 0-3, "words": "You write to Dana most weeks." or ""}
    for_message(con, message_id)        the same for the sender of one message; level 0 for list or automatic mail
"""
import datetime as dt
import math
import os
import re

import common
import db

WINDOW_DAYS = 90
HALF_LIFE_DAYS = 21
WEEKS = 13
COLUMNS = (("received_count", "INTEGER DEFAULT 0"), ("sent_90", "INTEGER DEFAULT 0"), ("received_90", "INTEGER DEFAULT 0"),
           ("weeks_written", "INTEGER DEFAULT 0"), ("strength", "DOUBLE DEFAULT 0"), ("counted_at", "TIMESTAMP"))
NOT_PERSONAL = ("noise", "ignore", "phishing")
ADDRESS = re.compile(r"[a-z0-9._%+'-]+@[a-z0-9.-]+\.[a-z]{2,}")


def ensure(con):
    for name, kind in COLUMNS:
        con.execute(f"ALTER TABLE contacts ADD COLUMN IF NOT EXISTS {name} {kind}")


def _has(con, table):
    return bool(con.execute("SELECT 1 FROM information_schema.tables WHERE table_name = ?", [table]).fetchone())


VALUES = ("sent_count", "received_count", "sent_90", "received_90", "weeks_written", "strength")


def _read(con):
    """Everything the recount needs, in a few quick reads: each message's people and time (and, for incoming mail, whether
    its end has an unsubscribe link, decided by the database), the judged-not-personal messages, and each contact's counts as
    they stand. No message body leaves the database."""
    import items
    have = {r[0] for r in con.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'contacts'").fetchall()}
    bad = {r[0] for r in con.execute("SELECT key FROM answered WHERE domain = 'judged' AND verdict IN (?, ?, ?)",
                                     NOT_PERSONAL).fetchall()} if _has(con, "answered") else set()
    msgs = con.execute("SELECT id, channel, direction, from_key, lower(coalesce(to_keys, '')), thread_id, ts, "
                       "direction = 'in' AND regexp_matches(right(coalesce(body, ''), 4000), ?) FROM messages",
                       ["(?i)" + items.UNSUBSCRIBE.pattern]).fetchall()
    cols = [c for c in VALUES if c in have]
    current = {r[0]: tuple(r[1:]) for r in con.execute("SELECT key" + "".join(", " + c for c in cols) + " FROM contacts").fetchall()}
    return {"missing": [c for c, _k in COLUMNS if c not in have], "bad": bad, "msgs": msgs, "current": current,
            "complete": len(cols) == len(VALUES)}


def _count(got, now):
    """{key: (sent, received, sent_90, received_90, weeks_written, strength)} for every contact. No database."""
    import items
    since, weeks_since = now - dt.timedelta(days=WINDOW_DAYS), now - dt.timedelta(weeks=WEEKS)
    msgs, bad, keys = got["msgs"], got["bad"], list(got["current"])
    keyset = set(keys)
    threads = {}            # a conversation (a text thread, a chat room): the people who wrote in it
    for mid, ch, d, fk, _to, th, _ts, _l in msgs:
        if d == "in" and fk and th:
            threads.setdefault((ch, th), set()).add(str(fk).lower())
    counts = {}

    def add(key, kind, ts):
        c = counts.setdefault(key, {"sent": 0, "received": 0, "sent_90": 0, "received_90": 0, "weeks": set(), "w": 0.0})
        c[kind] += 1
        if ts and ts >= since:
            c[kind + "_90"] += 1
            c["w"] += math.pow(0.5, (now - ts).total_seconds() / 86400 / HALF_LIFE_DAYS)
        if kind == "sent" and ts and ts >= weeks_since:
            c["weeks"].add(ts.isocalendar()[:2])
    emails = {k.split(":", 1)[1]: k for k in keys if k.startswith("email:")}
    for mid, ch, d, fk, to, th, ts, listy in msgs:
        if d == "in" and fk:
            if not listy and f"msg:{mid}" not in bad and not items.AUTOMATIC.match(str(fk).split(":", 1)[-1]):
                add(str(fk).lower(), "received", ts)
        elif d == "out":
            hit = set()
            if ch == "email":
                hit = {emails[a] for a in ADDRESS.findall(to) if a in emails}
            elif to:
                hit = {t.strip() for t in to.split(",") if t.strip() in keyset}
            if th and ch != "email":
                hit |= {k for k in threads.get((ch, th), ()) if k in keyset}
            for k in hit:
                add(k, "sent", ts)
    out = {}
    for k in keys:
        c = counts.get(k.lower()) or counts.get(k) or {"sent": 0, "received": 0, "sent_90": 0, "received_90": 0, "weeks": set(), "w": 0.0}
        two_way = c["sent"] > 0 and c["received"] > 0
        out[k] = (c["sent"], c["received"], c["sent_90"], c["received_90"], len(c["weeks"]), round(c["w"], 3) if two_way else 0.0)
    return out


def _same(a, b):
    return a is not None and len(a) == len(b) and all((x or 0) == y if not isinstance(y, float) else abs(float(x or 0) - y) < 0.0005
                                                      for x, y in zip(a, b))


def _changed_file(got, new):
    """The contacts whose counts changed, written to a small file before the database is opened to write: the database
    reads a file in one step (binding a value at a time takes seconds for a few hundred contacts). (path or None, count)"""
    import csv
    import tempfile
    changed = [(k,) + v for k, v in new.items() if not (got["complete"] and _same(got["current"].get(k), v))]
    if not changed:
        return None, 0
    fd, path = tempfile.mkstemp(prefix="contact-counts-", suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(changed)
    return path, len(changed)


def _write(con, got, path, now):
    """One short write: the columns if missing, the changed counts from the file in one statement, and the time."""
    if got["missing"]:
        ensure(con)
    con.execute("BEGIN TRANSACTION")
    try:
        if path:
            src = path.replace("\\", "/").replace("'", "''")
            con.execute("CREATE OR REPLACE TEMP TABLE contact_counts AS SELECT * FROM read_csv('" + src + "', header = false, quote = '\"', "
                        "columns = {'k': 'VARCHAR', 's': 'INTEGER', 'r': 'INTEGER', 's9': 'INTEGER', 'r9': 'INTEGER', 'w': 'INTEGER', 'st': 'DOUBLE'})")
            con.execute("UPDATE contacts SET sent_count = v.s, received_count = v.r, sent_90 = v.s9, received_90 = v.r9, "
                        "weeks_written = v.w, strength = v.st FROM contact_counts v WHERE contacts.key = v.k")
            con.execute("DROP TABLE contact_counts")
        con.execute("UPDATE contacts SET counted_at = ?", [now])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise


def refresh(con=None, now=None):
    """Recount every contact from the messages. Returns how many contacts were counted. The database is open only for a
    quick read and then a short write; the counting itself runs with it closed, so the page and other steps never wait."""
    now = now or dt.datetime.now()
    if con is not None:
        got = _read(con)
    else:
        c = db.connect(read_only=True)
        try:
            got = _read(c)
        finally:
            c.close()
    new = _count(got, now)
    path, _n = _changed_file(got, new)
    try:
        if con is not None:
            _write(con, got, path, now)
        else:
            c = db.connect()
            try:
                _write(c, got, path, now)
            finally:
                c.close()
    finally:
        if path:
            os.remove(path)                 # the program's own scratch file, made a moment ago
    return len(new)


def levels(con):
    """{contact key: 0-3} for every contact, read at once (what for_person gives as "level"), so a long job can look levels
    up with the database closed. Empty before the first recount."""
    if not con.execute("SELECT 1 FROM information_schema.columns WHERE table_name = 'contacts' AND column_name = 'strength'").fetchone():
        return {}
    rows = con.execute("SELECT c.key, p.w, p.st FROM contacts c JOIN (SELECT person_id, sum(coalesce(weeks_written, 0)) AS w, "
                       "sum(coalesce(strength, 0)) AS st FROM contacts WHERE coalesce(name_source, '') <> 'self' GROUP BY person_id) p "
                       "ON p.person_id = c.person_id").fetchall()
    return {k: _words(None, int(w or 0), float(st or 0))[0] for k, w, st in rows}


def _words(name, weeks, strength):
    who = name or "them"
    if weeks >= 7:
        return 3, f"You write to {who} most weeks."
    if weeks >= 3:
        return 2, f"You write to {who} every few weeks."
    if strength > 0:
        return 1, f"You have written back and forth with {who}."
    return 0, ""


def for_person(con, person):
    """{"level", "words"} for a person (their id, or one of their keys). Reads only: before the first recount, none."""
    if not con.execute("SELECT 1 FROM information_schema.columns WHERE table_name = 'contacts' AND column_name = 'strength'").fetchone():
        return {"level": 0, "words": ""}
    if isinstance(person, str):
        row = con.execute("SELECT person_id FROM contacts WHERE key = ?", [person.lower()]).fetchone()
        if not row:
            return {"level": 0, "words": ""}
        person = row[0]
    row = con.execute("SELECT max(name), sum(coalesce(weeks_written, 0)), sum(coalesce(strength, 0)) FROM contacts "
                      "WHERE person_id = ? AND coalesce(name_source, '') <> 'self'", [person]).fetchone()
    if not row or row[2] is None:
        return {"level": 0, "words": ""}
    name = row[0]
    if not name:        # no name on file: the one their newest mail gives
        got = con.execute("SELECT s.from_name FROM messages m JOIN mail_state s ON s.message_id = m.id WHERE m.direction = 'in' "
                          "AND m.from_key IN (SELECT key FROM contacts WHERE person_id = ?) AND coalesce(s.from_name, '') <> '' "
                          "ORDER BY m.ts DESC LIMIT 1", [person]).fetchone() if _has(con, "mail_state") else None
        name = got[0] if got else None
    level, words = _words(str(name or "").split(" ")[0] or None, int(row[1] or 0), float(row[2] or 0))
    return {"level": level, "words": words}


def for_message(con, mid):
    """The sender's contact strength for one message; none for a message from an automatic address or with an unsubscribe
    link (a frequent contact's mailing-list mail gets no boost)."""
    import items
    row = con.execute("SELECT direction, from_key, body FROM messages WHERE id = ?", [int(mid)]).fetchone()
    if not row or row[0] != "in" or not row[1]:
        return {"level": 0, "words": ""}
    if items.AUTOMATIC.match(str(row[1]).split(":", 1)[-1]) or items.UNSUBSCRIBE.search(str(row[2] or "")[-4000:]):
        return {"level": 0, "words": ""}
    return for_person(con, str(row[1]))
