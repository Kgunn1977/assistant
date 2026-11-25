"""Assemble the judgment payload.

    python judgment_payload.py                 # ALL unjudged messages, one pass
    python judgment_payload.py --day 2026-08-24
    python judgment_payload.py --stats         # just the shape of it

Judgment is reasoning, so the session does it; this script prepares the
question. The payload is built and saved first, so the validator can later
check that every message it owed was judged.

One payload is one judging round, sized to finish inside one Claude run: whole
days oldest first, then whole conversations in time order until ROUND_MESSAGES
messages or ROUND_CHARS characters of new text (bodies and attachment text),
always at least one message. What it left is said on an OVER CAP line, so the
judge takes another round (on 10/15/26 a 142-message day timed out twice at
300 s; the busiest day before it, 104 messages, took 240 s). The judge's rules
ride in the payload. Message bodies carry only what each message adds
(cleantext.new_text): no HTML copy, quoted reply history or signature.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # System\live
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                    # System\live\core
import db  # noqa: E402
import item_records  # noqa: E402
import paths  # noqa: E402
import rules  # noqa: E402
from cleantext import new_text  # noqa: E402

# Bodies are cleaned, not truncated: the cap applies after cleaning.
RAW_BODY_LIMIT = 60_000      # guard against a pathological body
MAX_BODY_CHARS = 1500        # after cleaning
MAX_DOC_CHARS = 2500         # each attachment's text; past it, cut with a marker saying how much was left out
MESSAGE_CAP = 150            # past this, stop at whole-day boundaries
ROUND_MESSAGES = 40          # one round's messages (64 took 266 s of the 300 s a Claude run gets, 10/6/26)
ROUND_CHARS = 40_000         # one round's new text: cleaned bodies plus attachment text
COMPACT_AT = 2500            # task detail past this is handed back for a rewrite

# An unsubscribe address sitting in the body. Deliberately narrow: the
# address itself has to say what it is for.
MAILTO = re.compile(
    r"mailto:([^\s<>\"')?]*(?:unsubscribe|optout|opt-out|remove)[^\s<>\"')?]*)",
    re.I)


def _contact(mid):
    """How often the owner is in touch with this message's sender, in plain words, or None (contact_strength.py)."""
    try:
        live = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if live not in sys.path:
            sys.path.insert(0, live)
        import contact_strength
        if db.reader() is not None:         # build()'s one reading connection: never an open per message
            return contact_strength.for_message(db.reader(), mid)["words"] or None
        con = db.connect(read_only=True)
        try:
            return contact_strength.for_message(con, mid)["words"] or None
        finally:
            con.close()
    except Exception:  # noqa: BLE001  one fact less never costs the sorting
        return None


def _history(mid):
    """What the look-back found in the owner's history about this message's sender and topic, in plain words, or None
    (lookback.py)."""
    try:
        live = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if live not in sys.path:
            sys.path.insert(0, live)
        import lookback
        if db.reader() is not None:
            return lookback.words_for(db.reader(), mid)
        con = db.connect(read_only=True)
        try:
            return lookback.words_for(con, mid)
        finally:
            con.close()
    except Exception:  # noqa: BLE001  one fact less never costs the sorting
        return None


def judge_rules():
    """The judge's documents (rules.READERS['judge']), as the payload carries them.

    Junk entries fold into one line per label, every id and pattern kept.
    "Always junk" stays out: those messages are settled before the judge
    reads anything, so their patterns could never touch a message it sees.
    """
    out, index = [], {}
    for e in rules.load("judge"):
        if e["section"] == rules.ALWAYS:
            continue
        if e["pattern"] is None:
            out.append({"id": e["id"], "document": e["title"], "rule": e["text"]})
            continue
        term = f"from ~ {e['pattern']}"
        if e["pattern2"]:
            term += f" + subject ~ {e['pattern2']}"
        key = (e["section"], e["text"])
        entry = index.get(key)
        if entry is None:
            entry = {"ids": [], "document": e["title"], "section": e["section"],
                     "rule": e["text"], "patterns": ""}
            index[key] = entry
            out.append(entry)
        entry["ids"].append(e["id"])
        entry["patterns"] = (entry["patterns"] + "; " + term
                             if entry["patterns"] else term)
    return out


# Rule 559: a subject about any of these keeps an unsubscribe-link email
# in front of the judge. These are about the safety of an account, for anyone.
KEEP_SUBJECT = re.compile(
    r"secur|sign[- ]?in|log[- ]?in|password|fraud", re.I)


def keep_words():
    """Rule 559: the owner's own list of words (personal "keep_words") that also keep such an email in
    front of the judge when its subject holds one: a bill, an order, a delivery, whatever matters to
    them. Empty in the starter set. Lower case, each at least 3 characters."""
    return [w for w in (" ".join(str(x).lower().split()) for x in paths.personal().get("keep_words") or [])
            if len(w) >= 3]


def kept_subject(subject, words):
    s = subject or ""
    return bool(KEEP_SUBJECT.search(s)) or any(w in s.lower() for w in words)
# Rule 559: an unsubscribe link, as a link address or as a link's own words.
# The words matter: most senders hide the address behind a tracking redirect.
UNSUB_LINK = re.compile(
    r"https?://[^\s\"<>]*(?:unsub|optout|opt-out)"
    r"|<a\s[^>]*>[^<]{0,40}(?:unsubscribe|opt[- ]?out|"
    r"manage (?:your )?(?:email )?preferences)", re.I)
# Rule 560: a short number, 6 digits or fewer.
SHORT_NUMBER = re.compile(r"^sms:\d{1,6}$")
TEXT_KEEP = re.compile(r"fraud|secur|declin|suspicious|was this you|payment|"
                       r"\bcard\b|alarm", re.I)


OWNER_JUNK = "you pressed Junk on a card"     # an Always junk line the owner put there themself (presses.py)


def junk_guard():
    """Rule 562 as a test: True for a sender no junk rule may touch."""
    never = [e["pattern"] for e in rules.junk([rules.NEVER])]
    # the owner's contacts: a mail address they have written to or that is
    # more than seen in mail, or a saved text contact with a real name
    keys = {(r[0] or "").lower() for r in db.query("""
        SELECT key FROM contacts
        WHERE (key LIKE 'email:%' AND (coalesce(name_source, '') <> 'seen_in_mail'
                                       OR coalesce(sent_count, 0) > 0))
           OR ((key LIKE 'sms:%' OR key LIKE 'phone:%')
               AND regexp_matches(coalesce(name, ''), '[A-Za-z]')
               AND name <> '(Unknown)')""")}
    written = set()
    for (tok,) in db.query(
            "SELECT DISTINCT unnest(regexp_split_to_array(to_keys, "
            "'[,\"\\[\\] ]+')) FROM messages WHERE direction = 'out'"):
        if tok:
            written.add(tok.lower().split(":", 1)[-1])
    known = keys | written | {k.split(":", 1)[-1] for k in keys}
    import filters
    through = filters.gets_through
    own_domains = paths.own_domains()

    def guarded(from_key):
        fk = (from_key or "").lower()
        addr = fk.split(":", 1)[-1]
        if fk in known or addr in known:
            return True
        if through(fk):         # the owner's "people who always get through"
            return True
        if any(addr.endswith("@" + d) for d in own_domains):
            return True
        return any(rules.matches(fk, p) for p in never)
    return guarded


def junk_rule_hits(where="", params=()):
    """(message id, rule) for inbound mail rule 559 or 560 settles."""
    rows = db.query(f"""
        SELECT m.id, m.channel, m.from_key, m.subject,
               substr(m.body, 1, {RAW_BODY_LIMIT})
        FROM messages m
        WHERE m.direction = 'in' AND m.channel IN ('email', 'sms') {where}""",
                    params)
    guarded = junk_guard()
    words = keep_words()
    import filters
    f = filters.get()
    mailings_shown = f["newsletters"] == "show"     # the owner's setting: mailings are read like any mail
    short_shown = f["short_texts"] == "show"        # the owner's setting: texts from short numbers are read like any text
    hits = []
    for mid, channel, fk, subject, body in rows:
        if guarded(fk):
            continue
        if channel == "sms" and SHORT_NUMBER.match(fk or ""):
            if not short_shown and not TEXT_KEEP.search(body or ""):
                hits.append((mid, 560))
        elif (channel == "email" and not mailings_shown and not kept_subject(subject, words)
              and (MAILTO.search(body or "") or UNSUB_LINK.search(body or ""))):
            hits.append((mid, 559))
    return hits


def junk_preview(since):
    """What rules 559 and 560 would have settled among messages the judge
    read since a date, and what the judge called each. Writes nothing."""
    hits = junk_rule_hits(
        "AND m.ts >= ? AND EXISTS (SELECT 1 FROM answered a WHERE"
        " a.domain='judged' AND a.key='msg:'||m.id AND a.source NOT LIKE"
        " 'rule:%' AND a.source NOT LIKE 'outbox:%' AND a.source NOT LIKE"
        " 'filed:%' AND a.source <> 'judged_by_v1')", (since,))
    verdict = dict(db.query(
        "SELECT CAST(substr(key, 5) AS BIGINT), verdict FROM answered"
        " WHERE domain='judged' AND key LIKE 'msg:%'"))
    from collections import Counter
    tally = Counter((rule, verdict.get(mid)) for mid, rule in hits)
    for (rule, v), n in sorted(tally.items()):
        print(f"rule {rule}: judge said {v}: {n}")
    for mid, rule in hits:
        if verdict.get(mid) not in ("noise", "ignore"):
            r = db.query("SELECT from_key, subject FROM messages WHERE id=?",
                         (mid,))[0]
            print(f"  {mid} rule {rule} judge {verdict.get(mid)}: {r[0]} | "
                  f"{(r[1] or '')[:70]}")


def self_threads():
    """The text threads that are the owner's notes to themselves: the thread
    named after the owner, under their settings name or any name their own
    contact rows carry."""
    names = {paths.owner_name()}
    names.update(r[0] for r in db.query(
        "SELECT DISTINCT name FROM contacts"
        " WHERE name_source = 'self' AND name IS NOT NULL"))
    return [(f"sms:{n}",) for n in sorted(names) if n]


def owner_ignored():
    """Ids of inbound mail nothing has ruled on yet whose sender is on the
    owner's own ignore list (personal "ignore_senders": addresses or domains).
    One of the owner's own domains is never ignored, whatever the list says."""
    entries = [str(e).strip().lower() for e in paths.personal().get("ignore_senders") or [] if str(e).strip()]
    if not entries:
        return []
    own = paths.own_domains()
    hits = []
    for mid, fk in db.query(
            "SELECT m.id, m.from_key FROM messages m WHERE m.direction = 'in'"
            " AND m.channel = 'email' AND NOT EXISTS (SELECT 1 FROM answered a"
            " WHERE a.domain='judged' AND a.key = 'msg:' || m.id)"):
        addr = (fk or "").lower().split(":", 1)[-1]
        if "@" not in addr:
            continue
        dom = addr.rsplit("@", 1)[-1]
        if any(dom == d or dom.endswith("." + d) for d in own):
            continue
        if any(e == addr or ("@" not in e and (dom == e or dom.endswith("." + e))) for e in entries):
            hits.append(mid)
    return hits


def prefilter_noise():
    """Write verdict rows for mechanical noise before the payload is built, so
    the judge never reads it. Nothing is dropped silently: each message gets
    the same verdict row a judge pass writes, with the rule id as its source.

    Only the junk list's "Always junk" section applies here. Outgoing mail and
    the owner's self-notes are never filtered (rule 424), and noise exceptions
    beat noise rules, as they do for the judge.
    """
    always = [(e["id"], e["pattern"], e["pattern2"],
               str(e["text"] or "").startswith(OWNER_JUNK))
              for e in rules.junk([rules.ALWAYS])]
    never = [(e["pattern"],) for e in rules.junk([rules.NEVER])]
    # worked out before the connection opens: all read the database, through one reading connection (db.reading)
    with db.reading():
        guarded = junk_guard()
        shield = [(fk,) for (fk,) in db.query(
            "SELECT DISTINCT from_key FROM messages WHERE direction = 'in'"
            " AND from_key IS NOT NULL") if guarded(fk)]
        own_threads = self_threads()
        own = paths.own_domains()
        own_keys = [(fk,) for (fk,) in shield
                    if any((fk or "").lower().endswith("@" + d) or (fk or "").lower().endswith("." + d) for d in own)]
        # rules 559 and 560, over messages nothing has ruled on yet
        hits = junk_rule_hits(
            "AND NOT EXISTS (SELECT 1 FROM answered a WHERE a.domain='judged'"
            " AND a.key = 'msg:' || m.id)")
        ignored_hits = owner_ignored()
    import filters
    setting_hits = filters.holds(db, guarded)       # hidden by one of the owner's filter settings, before any reading
    with db.transaction() as con:
        # the junk list as scratch tables for this connection
        con.execute("CREATE TEMP TABLE junk_always "
                    "(id INTEGER, pattern VARCHAR, pattern2 VARCHAR,"
                    " by_owner BOOLEAN)")
        con.execute("CREATE TEMP TABLE junk_own (from_key VARCHAR)")
        con.execute("CREATE TEMP TABLE junk_never (pattern VARCHAR)")
        # rule 562: senders no junk rule may touch
        con.execute("CREATE TEMP TABLE junk_guarded (from_key VARCHAR)")
        # the owner's notes to themselves
        con.execute("CREATE TEMP TABLE junk_self (thread_id VARCHAR)")
        if shield:
            con.executemany("INSERT INTO junk_guarded VALUES (?)", shield)
        if always:
            con.executemany("INSERT INTO junk_always VALUES (?,?,?,?)", always)
        if own_keys:
            con.executemany("INSERT INTO junk_own VALUES (?)", own_keys)
        if never:
            con.executemany("INSERT INTO junk_never VALUES (?)", never)
        if own_threads:
            con.executemany("INSERT INTO junk_self VALUES (?)", own_threads)
        n = con.execute("""
            INSERT INTO answered (domain, key, verdict, source, answered_at)
            SELECT 'judged', 'msg:' || m.id,
                   'noise', 'rule:' || min(r.id), now()
            FROM messages m
            JOIN junk_always r ON m.from_key ILIKE r.pattern
                        AND (r.pattern2 IS NULL
                             OR coalesce(m.subject,'') ILIKE r.pattern2)
            WHERE m.direction = 'in'
              AND coalesce(m.thread_id,'') NOT IN (SELECT thread_id FROM junk_self)
              AND NOT EXISTS (SELECT 1 FROM junk_never e
                              WHERE m.from_key ILIKE e.pattern)
              AND (m.from_key NOT IN (SELECT from_key FROM junk_guarded)
                   OR (r.by_owner
                       AND m.from_key NOT IN (SELECT from_key FROM junk_own)))
              AND NOT EXISTS (SELECT 1 FROM answered a
                              WHERE a.domain='judged'
                                AND a.key = 'msg:' || m.id)
            GROUP BY m.id""").fetchone()[0]
        # alerts the assistant texted the owner (from_key 'assistant'):
        # ignore, rule 424
        n += con.execute("""
            INSERT INTO answered (domain, key, verdict, source, answered_at)
            SELECT 'judged', 'msg:' || m.id,
                   'ignore', 'rule:424', now()
            FROM messages m
            WHERE m.from_key = 'assistant'
              AND NOT EXISTS (SELECT 1 FROM answered a
                              WHERE a.domain='judged'
                                AND a.key = 'msg:' || m.id)""").fetchone()[0]
        # the owner's own ignore list (Settings on their page): settled as noise
        for mid in ignored_hits:
            n += con.execute("""
                INSERT INTO answered (domain, key, verdict, source,
                                      answered_at)
                SELECT 'judged', 'msg:' || ?,
                       'noise', 'owner:ignore', now()
                WHERE NOT EXISTS (SELECT 1 FROM answered a
                                  WHERE a.domain='judged'
                                    AND a.key = 'msg:' || ?)""",
                (mid, mid)).fetchone()[0]
        for mid, source in setting_hits:
            n += con.execute("""
                INSERT INTO answered (domain, key, verdict, source,
                                      answered_at)
                SELECT 'judged', 'msg:' || ?, 'noise', ?, now()
                WHERE NOT EXISTS (SELECT 1 FROM answered a
                                  WHERE a.domain='judged'
                                    AND a.key = 'msg:' || ?)""",
                (mid, source, mid)).fetchone()[0]
        # rules 559 and 560; a message the lists above already settled is
        # skipped by the same NOT EXISTS
        for mid, rule in hits:
            n += con.execute("""
                INSERT INTO answered (domain, key, verdict, source,
                                      answered_at)
                SELECT 'judged', 'msg:' || ?,
                       'noise', 'rule:' || ?, now()
                WHERE NOT EXISTS (SELECT 1 FROM answered a
                                  WHERE a.domain='judged'
                                    AND a.key = 'msg:' || ?)""",
                (mid, rule, mid)).fetchone()[0]
        return n


def unjudged_days():
    """(day, count) for days still holding messages nothing has ruled on. While a replay runs (ASSISTANT_NOW, its day end),
    nothing after that moment is offered: the judge sees the record only up to the day it is told it is."""
    until = os.environ.get("ASSISTANT_NOW")
    return db.query("""
        SELECT ts::DATE AS d, count(*) FROM messages m
        WHERE NOT EXISTS (SELECT 1 FROM answered a
                          WHERE a.domain='judged' AND a.key = 'msg:' || m.id)""" + (" AND m.ts < ?" if until else "") + """
        GROUP BY 1 ORDER BY 1""", (dt.datetime.fromisoformat(until),) if until else ())


def pick_days(day_counts):
    """All unjudged days, oldest first, until the cap; whole days only.

    Oldest first because a message left behind today is left behind again
    tomorrow; newest-first would starve the stragglers forever. Always at least
    one day, even if that day alone exceeds the cap: build() then takes it a
    round at a time (coverage is checked per payload, message by message).
    """
    chosen, total = [], 0
    for day, n in day_counts:
        if chosen and total + n > MESSAGE_CAP:
            break
        chosen.append(day)
        total += n
    return chosen, [d for d, _n in day_counts if d not in chosen]


def open_task_layer(rows, folder=None):
    """The open tasks as they travel, with each one's full record (detail and
    every citation) written beside them (folder: where the records go, the
    judge's own folder unless a dry run names its own). Detail is not clipped;
    past COMPACT_AT the task is flagged for the judge to rewrite."""
    records = item_records.Records(folder) if folder else item_records.Records()
    out = []
    for (tid, key, area, title, detail, status, due, checkback) in rows:
        entry = {"id": tid, "key": key, "area": area, "title": title,
                 "detail": detail, "status": status,
                 "due": str(due) if due else None,
                 "checkback": str(checkback) if checkback else None,
                 "full_record": records.write(
                     key, title, status, area, detail,
                     records.citations_for(tid))}
        if len(detail or "") > COMPACT_AT:
            entry["compact"] = True
        out.append(entry)
    return out


def _doc_text(text, full_len):
    """An attachment's text, cut at MAX_DOC_CHARS with a marker saying how much was left out."""
    text = text or ""
    if (full_len or 0) > MAX_DOC_CHARS:
        text = text[:MAX_DOC_CHARS].rstrip() + f"\n[... {full_len - MAX_DOC_CHARS} more characters of this attachment left out]"
    return text


def take_round(order, convs, cost, max_msgs=ROUND_MESSAGES, max_chars=ROUND_CHARS):
    """The message ids one round judges: whole conversations in order while they fit, a conversation too big for a round
    alone split in time order; always at least one message, so a day can never get stuck."""
    chosen, chars = [], 0

    def fits(n, c):
        return len(chosen) + n <= max_msgs and chars + c <= max_chars

    for key in order:
        ids = [m[0] for m in convs[key]]
        c = sum(cost[i] for i in ids)
        if fits(len(ids), c):
            chosen += ids
            chars += c
            continue
        if chosen:
            break
        for i in ids:                       # the first conversation alone is too big: as much of it as fits
            if chosen and not fits(1, cost[i]):
                break
            chosen.append(i)
            chars += cost[i]
        break
    return chosen


def build(days, max_msgs=ROUND_MESSAGES, max_chars=ROUND_CHARS, ids=None, records_folder=None):
    """Everything needed to judge one round of the given days, and nothing else. payload["left"] is how many of the days'
    unjudged messages wait for the next round. With ids, those messages whatever has been ruled on them (the grader's dry
    run, grader.py), their days taken from them; records_folder: where the open tasks' records go."""
    # the sender's name as a scalar: joining contacts would repeat a message
    # once per contact key
    if ids:
        where, params = f"m.id IN ({','.join('?' * len(ids))})", [int(i) for i in ids]
    else:
        where = (f"m.ts::DATE IN ({','.join('?' * len(days))}) AND NOT EXISTS (SELECT 1 FROM answered a "
                 "WHERE a.domain='judged' AND a.key = 'msg:' || m.id)")
        params = list(days)
    msgs = db.query(f"""
        SELECT m.id, m.channel, m.account, m.ts, m.direction, m.subject,
               substr(coalesce(m.body,''), 1, ?),
               (SELECT max(c.name) FROM contacts c
                 WHERE c.person_id = m.person_id AND c.name IS NOT NULL),
               m.from_key, m.to_keys, m.thread_id
        FROM messages m
        WHERE {where}
        ORDER BY m.ts""", [RAW_BODY_LIMIT] + params)
    if ids:
        days = sorted({str(m[3])[:10] for m in msgs})

    ids = [m[0] for m in msgs]
    docs = []
    if ids:
        ph = ",".join("?" * len(ids))
        docs = db.query(f"""
            SELECT d.message_id, d.doc_type, a.original_filename,
                   substr(string_agg(p.text, chr(10) ORDER BY p.page_no), 1, ?),
                   length(string_agg(p.text, chr(10) ORDER BY p.page_no))
            FROM documents d
            LEFT JOIN attachments a ON a.id = d.attachment_id
            LEFT JOIN pages p ON p.document_id = d.id
            WHERE d.message_id IN ({ph})
            GROUP BY 1,2,3""", [MAX_DOC_CHARS] + ids)
    docs = [(d[0], d[1], d[2], _doc_text(d[3], d[4])) for d in docs]
    bodies = {m[0]: new_text(m[6], MAX_BODY_CHARS, subject=m[5] or "") for m in msgs}
    cost = {i: len(bodies[i]) for i in ids}
    for d in docs:
        cost[d[0]] = cost.get(d[0], 0) + len(d[3])

    open_tasks = db.query("""
        SELECT id, item_key, area, title, detail, status, due_date, checkback_date
        FROM tasks WHERE status IN ('needs_me','waiting_them')
        ORDER BY area, id""")

    # the calendar mirror rides along (rule 431)
    calendar = db.query("""
        SELECT start_ts, end_ts, summary, calendar, all_day
        FROM calendar_events ORDER BY start_ts""")

    # what the owner has already settled, so nothing is raised twice
    settled = db.query("""
        SELECT domain, key, verdict FROM answered
        WHERE domain <> 'judged' ORDER BY answered_at DESC LIMIT 400""")

    # messages grouped by conversation, each in time order, conversations by
    # their first message; a message with no thread is its own conversation
    convs, order = {}, []
    for m in msgs:
        key = (m[1], m[10]) if m[10] else (m[1], f"msg:{m[0]}")
        if key not in convs:
            convs[key] = []
            order.append(key)
        convs[key].append(m)
    # one round: what fits in one Claude run; the rest is the next round's
    chosen = set(take_round(order, convs, cost, max_msgs, max_chars))
    left = len(msgs) - len(chosen)
    convs = {k: [m for m in v if m[0] in chosen] for k, v in convs.items()}
    order = [k for k in order if convs[k]]
    docs = [d for d in docs if d[0] in chosen]
    msgs = [m for key in order for m in convs[key]]
    conv_of = {m[0]: i for i, key in enumerate(order, 1) for m in convs[key]}
    in_round = sorted({str(m[3])[:10] for m in msgs})

    return {
        "days": [str(d) for d in days if str(d) in in_round] or [str(d) for d in days],
        "left": left,
        "goals": rules.goals(),
        "reference": rules.reference(),
        # the judge's documents (rules.READERS["judge"]), Goals.md beside them
        "active_rules": judge_rules(),
        "conversations": [
            {"conv": i, "channel": key[0], "messages": len(convs[key]),
             "ids": [m[0] for m in convs[key]]}
            for i, key in enumerate(order, 1)],
        "messages": [
            {"id": m[0], "conv": conv_of[m[0]], "channel": m[1],
             "account": m[2], "ts": str(m[3]),
             "direction": m[4], "subject": m[5],
             "body": bodies[m[0]],
             "from_name": m[7], "from": m[8], "to": m[9], "thread": m[10],
             "sender_contact": _contact(m[0]) if m[4] == "in" else None,
             "sender_history": _history(m[0]) if m[4] == "in" else None}
            for m in msgs],
        "documents": [
            {"message_id": d[0], "type": d[1], "filename": d[2], "text": d[3]}
            for d in docs],
        "calendar": [
            {"start": str(c[0]), "end": str(c[1]) if c[1] else None,
             "summary": c[2], "calendar": c[3], "all_day": bool(c[4])}
            for c in calendar],
        "open_tasks": open_task_layer(open_tasks, records_folder),
        "already_settled": [
            {"domain": s[0], "key": s[1], "verdict": s[2]} for s in settled],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--out")
    # accepted because the orchestrator passes it to every phase script
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--round-messages", type=int, default=ROUND_MESSAGES,
                    help="at most this many messages this round (the judge asks for fewer after a round timed out)")
    ap.add_argument("--junk-preview", metavar="SINCE",
                    help="what rules 559 and 560 would have settled since a "
                         "date, against the judge's own verdicts; writes nothing")
    args = ap.parse_args()
    if args.junk_preview:
        junk_preview(args.junk_preview)
        return 0

    if not args.stats:                       # --stats reads, never writes
        auto = prefilter_noise()
        if auto:
            print(f"prefilter: {auto} message(s) auto-noised by rule, "
                  "sources recorded as rule:<id>")

    # every read from here to the payload goes through one connection: an open per message (the sender's contact line)
    # cost about a second each and made a 150-message payload take over three minutes (11/22/26)
    db.start_reading()
    day_counts = unjudged_days()
    # an explicit --day always builds, even over an empty backlog
    if args.stats or (not day_counts and not args.day):
        total = sum(n for _d, n in day_counts)
        print(f"days with unjudged messages: {len(day_counts)}, "
              f"total {total}")
        for d, n in day_counts:
            print(f"   {d}: {n}")
        db.stop_reading()
        return 0

    if args.day:
        days, left_out = [dt.date.fromisoformat(args.day)], []
    else:
        days, left_out = pick_days(day_counts)

    n = max(1, args.round_messages)
    payload = build(days, n, ROUND_CHARS * min(n, ROUND_MESSAGES) // ROUND_MESSAGES)
    left = payload.pop("left")
    db.stop_reading()
    name = str(days[-1]) if len(days) == 1 else f"{days[0]}_to_{days[-1]}"
    out = args.out or os.path.join(paths.STATE, f"payload_{name}.json")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, default=str)

    size = os.path.getsize(out)
    n_compact = sum(1 for t in payload["open_tasks"] if t.get("compact"))
    print(f"payload for {', '.join(str(d) for d in days)}: "
          f"{len(payload['messages'])} messages in "
          f"{len(payload['conversations'])} conversations, "
          f"{len(payload['documents'])} documents, "
          f"{len(payload['open_tasks'])} open tasks "
          f"({n_compact} flagged for compaction), "
          f"{len(payload['active_rules'])} rule entries embedded")
    print(f"   {size/1024:.0f} KB at {out}")
    by_channel = {}
    for m in payload["messages"]:
        by_channel[m["channel"]] = by_channel.get(m["channel"], 0) + 1
    print(f"   by channel: {by_channel}")
    if left or left_out:
        print(f"   OVER CAP: {left} message(s) of {', '.join(str(d) for d in days)} for the next round, "
              f"{len(left_out)} more day(s) left for the next check"
              + (f": {', '.join(str(d) for d in left_out)}" if left_out else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
