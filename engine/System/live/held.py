r"""What was hidden: every message that came in and was kept off the page, by day, with why.

ITEMS.md ("Design round 2") is the contract. Nothing is stored twice: the list is read from the
verdict every message already carries (who or what settled it is that verdict's source), so a message
can never be hidden without being on it. The pass writes <home>\held.json for the page; the page
sends "I should have seen this" on a row and show() makes that message's card at once. No Claude.

    write()            <home>\held.json: today and the six days before
    show(message id)   the card for a held message, made now (or queued for seconds while a pass holds the database)
    net(pass_id)       the pass's own safety net: queued cards, and mail from people who always get through
"""
import datetime as dt
import json
import os
import re

import card
import common
import dates
import filters

HELD_JSON = os.path.join(common.HOME, "held.json")
SHOWN = os.path.join(common.HOME, "state", "held_shown.json")       # {message id: the row as it was}, for rows he asked to see
QUEUE = os.path.join(common.HOME, "state", "held_wanted.json")      # message ids whose card waits for the database
DAYS = 7
ROWS_A_DAY = 300
HELD_VERDICTS = ("noise", "ignore", "phishing")
SEEN_WHY = "You said you should have seen this."
ASKS = "Read it and decide what it needs."
KEY = re.compile(r"^(?:held-(\d{1,12})|card-(L\d{1,12}))$")


def _rules():
    import sys
    if common.paths.CORE not in sys.path:
        sys.path.insert(0, common.paths.CORE)
    import rules
    return rules


def why(verdict, source, junk_ids=None):
    """(the plain line, by) for one verdict's source."""
    s = str(source or "").strip()
    if s in filters.SOURCES:
        return filters.SOURCES[s], "setting"
    if s.startswith("mod:"):
        import mods
        return mods.hold_reason(s) or "One of your add-ons hid it.", "setting"
    if s.startswith("setting:"):          # a setting that has since moved to one of his own additions
        return "One of your settings hid it.", "setting"
    if s == "owner:ignore":
        return "The sender is on your list of senders to always ignore.", "ignore_list"
    m = re.match(r"^rule:(\d+)$", s)
    if m:
        n = int(m.group(1))
        if n == 559:
            return "It is a mailing with an unsubscribe link, and its subject holds none of your keep words.", "setting"
        if n == 560:
            return "It is a text from a short number, the kind used for codes and adverts.", "setting"
        if junk_ids is None or n in junk_ids:
            return "The sender is on your junk list.", "junk_list"
        return "A junk rule hid it before I read it.", "setting"
    m = re.match(r"^owner rule (\d+):\s*(.*)$", s, re.I)
    if m:
        rule = next((r for r in filters.rules() if r["id"] == int(m.group(1))), None)
        return (f"Your rule hid it: \"{rule['text']}\"" if rule else f"One of your rules hid it: {m.group(2)}")[:300], "rule"
    if s.lower().startswith("fast:"):
        s = s[5:].strip()
    said = s[:1].lower() + s[1:] if s else "it needs nothing from you"
    if verdict == "phishing":
        return f"I read it and think it's likely a scam: {said}."[:300].replace("..", "."), "sorting"
    return f"I read it and saw nothing you need to do: {said}."[:300].replace("..", "."), "sorting"


def _who(name, from_key):
    return " ".join(str(name or "").split()) or str(from_key or "").split(":", 1)[-1] or "unknown sender"


def rows_for(db, since):
    """Every held message from `since` on, newest first, in the row shape the page gets."""
    try:
        junk_ids = {e["id"] for e in _rules().junk()}
    except Exception:  # noqa: BLE001
        junk_ids = None
    shown = common.read_json(SHOWN, {}) or {}
    out = []
    marks = ",".join("?" for _ in HELD_VERDICTS)
    for mid, channel, fk, subject, body, ts, verdict, source, name, ruled in db.query(
            f"""SELECT m.id, m.channel, m.from_key, m.subject, substr(m.body, 1, 400), m.ts, a.verdict, a.source,
                       (SELECT max(c.name) FROM contacts c WHERE c.person_id = m.person_id AND c.name IS NOT NULL), a.answered_at
                FROM messages m JOIN answered a ON a.domain='judged' AND a.key = 'msg:' || m.id
                WHERE m.direction = 'in' AND m.ts >= ? AND a.verdict IN ({marks})
                  AND coalesce(m.from_key, '') <> 'assistant' AND a.source <> 'rule:424'
                ORDER BY m.ts DESC""", (since, *HELD_VERDICTS)):
        line, by = why(verdict, source, junk_ids)
        line = dates.store(line, (ruled or ts).date())      # the day it was judged; worded again every time the list is built
        what = " ".join(str(subject or "").split()) or " ".join(str(body or "").split())
        out.append({"key": f"held-{mid}", "who": _who(name, fk), "address": str(fk or "").split(":", 1)[-1],
                    "what": card.clip(what, 120) or "(no words)", "at": ts.isoformat(timespec="seconds"), "channel": channel,
                    "why": line, "by": by, "shown": False})
    for mid, row in shown.items():          # rows he asked to see stay on the list, marked
        if isinstance(row, dict) and str(row.get("at") or "") >= since.isoformat():
            out.append(dict(row, shown=True))
    out.sort(key=lambda r: r["at"], reverse=True)
    return out


def hidden_cards(db, since):
    """Cards that need nothing, kept out of the feed by the setting "hide": they are on the list too. An "I'd hide this"
    card is never kept out (items.export): it is there for his answer."""
    if filters.get()["nothing_needed"] != "hide":
        return []
    import items
    import wouldhide
    out = []
    for it in items.rows("state IN ('handled', 'new') AND shelf IS NULL AND updated_at >= ?", (since,)):
        if (it.get("source_key") or "").startswith(items.RETIRED_PREFIXES) or wouldhide.is_card(it):
            continue
        if filters.gets_through(it.get("source_who"), it.get("source_who")) or it.get("status") == card.SEEN_STATUS:
            continue
        when = it.get("source_when") or it.get("updated_at")
        who = str(it.get("source_who") or "Your assistant")
        who = who.split(":", 1)[-1] if who.split(":", 1)[0] in common.sender_kinds() - {"text"} else who
        out.append({"key": f"card-{it['id']}", "who": who, "address": "",
                    "what": card.clip(it.get("title"), 120), "at": when.isoformat(timespec="seconds"), "channel": "card",
                    "why": filters.SOURCES["setting:nothing_needed"], "by": "setting", "shown": False})
    return out


def write():
    """<home>\\held.json for the page. Returns today's count."""
    import db
    today = dt.date.today()
    since = dt.datetime.combine(today - dt.timedelta(days=DAYS - 1), dt.time())
    rows = rows_for(db, since) + hidden_cards(db, since)
    rows.sort(key=lambda r: r["at"], reverse=True)
    days = []
    for n in range(DAYS):
        day = (today - dt.timedelta(days=n)).isoformat()
        mine = [r for r in rows if r["at"][:10] == day]
        days.append({"date": day, "count": sum(1 for r in mine if not r["shown"]), "rows": mine[:ROWS_A_DAY]})
    common.write_json(HELD_JSON, {"written_at": common.now(), "today": days[0]["count"], "days": days})
    return days[0]["count"]


def for_page():
    """The list as the page gets it: every stored day marker worded for today."""
    got = common.read_json(HELD_JSON, None)
    for day in (got or {}).get("days") or []:
        for row in day.get("rows") or []:
            if isinstance(row.get("why"), str):
                row["why"] = dates.show(row["why"])
    return got


# --- "I should have seen this" ----------------------------------------------------------------------
def _make(con, mid, pass_id, why_line=SEEN_WHY, teach=True):
    """The plain card for one message, on an open connection. Returns its id, or None when the message is unknown."""
    import items
    row = con.execute(
        """SELECT m.id, m.channel, m.account, m.ts, m.from_key, m.subject, m.body, a.verdict, a.source,
                  (SELECT max(c.name) FROM contacts c WHERE c.person_id = m.person_id AND c.name IS NOT NULL)
           FROM messages m LEFT JOIN answered a ON a.domain='judged' AND a.key = 'msg:' || m.id WHERE m.id=?""", (mid,)).fetchone()
    if not row:
        return None
    _id, channel, account, ts, fk, subject, body, verdict, source, name = row
    who = _who(name, fk)
    have = con.execute("SELECT id FROM live_items WHERE source_key=?", (f"live:msg-{mid}",)).fetchone()
    if have:
        return have[0]
    # the message's "I'd hide this" card (wouldhide.py): one message has one card, so the press acts on that card
    would = con.execute("SELECT id, assistant_did FROM live_items WHERE source_key=?", (f"live:wouldhide-{mid}",)).fetchone()
    if verdict in HELD_VERDICTS:        # remember the row as it was, so the list still shows it, marked
        line, by = why(verdict, source)
        line = dates.store(line, ts.date())
        shown = common.read_json(SHOWN, {}) or {}
        what = " ".join(str(subject or "").split()) or " ".join(str(body or "").split())
        shown[str(mid)] = {"key": f"held-{mid}", "who": who, "address": str(fk or "").split(":", 1)[-1],
                           "what": card.clip(what, 120) or "(no words)", "at": ts.isoformat(timespec="seconds"),
                           "channel": channel, "why": line, "by": by, "shown": True}
        common.write_json(SHOWN, shown)
    now = common.now()
    con.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES ('judged', ?, 'task', ?, ?)"
                " ON CONFLICT (domain, key) DO UPDATE SET verdict='task', source=excluded.source, answered_at=excluded.answered_at,"
                " covered=NULL, leaned_on=NULL",        # the owner's word, not the judge's guess: no stale "not covered" mark
                (f"msg:{mid}", "owner:should_have_seen" if teach else "owner:always_through", now))
    if would:       # that card is on the page from now on (open again if it was closed); no second card is made
        said = f"You said {now.month}/{now.day} {now.strftime('%I:%M %p').lstrip('0')} you should have seen this." if teach else why_line
        con.execute("UPDATE live_items SET state='handled', shelf=NULL, later_until=NULL, done_at=NULL, status=?, assistant_did=?,"
                    " updated_at=?, state_changed_at=?, last_pass=? WHERE id=?",
                    (card.SEEN_STATUS if teach else None, f"{would[1]}\n{said}" if would[1] else said, now, now, pass_id, would[0]))
        return would[0]
    title =" ".join(str(subject or "").split()) or " ".join(" ".join(str(body or "").split()).split(" ")[:12]) or "A message"
    title = dates.store(title, ts.date())
    where = f"email to {account}" if channel == "email" else common.channel_word(channel)
    ref = f"{who}, {where}, {ts.month}/{ts.day} {ts.strftime('%I:%M %p').lstrip('0')} ({mid})"
    iid = "L" + str(con.execute("SELECT nextval('seq_live_item')").fetchone()[0])
    cols = {"id": iid, "source_key": f"live:msg-{mid}", "kind": "task", "area": "Personal", "title": f"{who}: {title}"[:300],
            "detail": _story(subject, body), "state": "yours", "importance": 0, "source_who": who, "source_when": ts, "source_ref": ref,
            "source_messages": json.dumps([str(mid)]), "asks": json.dumps([ASKS]), "evidence": ref, "evidence_files": "[]",
            "created_at": now, "updated_at": now, "state_changed_at": now, "last_pass": pass_id, "why": why_line,
            "status": "Shown at your asking" if teach else None}
    con.execute(f"INSERT INTO live_items ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})", tuple(cols.values()))
    import items
    items.owe_writing([iid])      # a stand-in until the card writer writes it like any card at the next pass
    return iid


def _story(subject, body):
    """The message's own words, cleaned, as the card's story."""
    try:
        import sys
        if common.paths.MODULE_A not in sys.path:
            sys.path.insert(0, common.paths.MODULE_A)
        import cleantext
        return cleantext.clean_body(body or "", limit=3000) or None      # quoted text kept: he asked to see this message whole
    except Exception:  # noqa: BLE001
        return " ".join(str(body or "").split())[:3000] or None


def show(mid, pass_id="press"):
    """Make the card for a held message now. Returns (the card as the feed carries it or None, plain words)."""
    import db
    import items
    con = db.try_connect()
    if con is None:
        want = common.read_json(QUEUE, []) or []
        common.write_json(QUEUE, sorted(set(want) | {int(mid)}))
        return None, "I'm in the middle of checking for messages. The card will be on your page within a few minutes."
    try:
        items.ensure_on(con)
        iid = _make(con, int(mid), pass_id)
        if iid is None:
            return None, "That message is no longer on file, so no card could be made."
        import answers
        item = items.read(con, answers._row(con, iid))
    finally:
        con.close()
    item = items.finish(item) if item is not None else None
    try:
        write()
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"held list: {type(e).__name__}: {e}")
    return item, "It is on your page now."


READING = os.path.join(common.HOME, "state", "held_reading.json")      # the one message asked for last, for the feed
PART = 12000
MORE = "[There is more. Open the next part.]"


def read(key, part=1, at=None):
    """The message behind a hidden row, for the page to show on that row: written to the feed's `reading`
    document, one message at a time. Changes nothing else. Returns (ok, plain words)."""
    import db
    m = KEY.match(str(key))
    part = part if isinstance(part, int) and not isinstance(part, bool) and 1 <= part <= 200 else 1
    doc = {"key": str(key), "at": at, "ok": False, "part": part}
    con = db.try_connect()        # opened the way every other answer opens it
    if con is None:
        doc["text"] = "I'm in the middle of checking for messages. Open it again in a moment."
        common.write_json(READING, doc)
        return False, doc["text"]
    try:
        mid = int(m.group(1)) if m.group(1) else None
        if mid is None:         # a card kept out by a setting: the newest message behind it
            got = con.execute("SELECT source_messages FROM live_items WHERE id=?", (m.group(2),)).fetchone()
            ids = [int(x) for x in json.loads((got or ["[]"])[0] or "[]") if str(x).isdigit()]
            mid = ids[0] if ids else None
        row = con.execute(
            """SELECT m.channel, m.account, m.ts, m.from_key, m.to_keys, m.subject, m.body,
                      (SELECT max(c.name) FROM contacts c WHERE c.person_id = m.person_id AND c.name IS NOT NULL)
               FROM messages m WHERE m.id=?""", (mid,)).fetchone() if mid is not None else None
        if not row:
            doc["text"] = "That message is no longer on file, so it cannot be shown."
            common.write_json(READING, doc)
            return False, doc["text"]
        channel, account, ts, fk, to_keys, subject, body, name = row
        papers = [os.path.basename(str(r[0])) for r in con.execute(
            "SELECT original_filename FROM attachments WHERE message_id=? AND coalesce(state, '') <> 'discarded' ORDER BY id", (mid,)).fetchall()
            if r[0] and not INLINE.match(os.path.basename(str(r[0])))]
    finally:
        con.close()
    import sys
    if common.paths.MODULE_A not in sys.path:
        sys.path.insert(0, common.paths.MODULE_A)
    import cleantext
    text = cleantext.new_text(body or "", limit=2_000_000, subject=subject or "") or "(This message has no words of its own.)"
    parts = max(1, -(-len(text) // PART))
    part = min(part, parts)
    piece = text[(part - 1) * PART: part * PART]
    address = str(fk or "").split(":", 1)[-1]
    doc.update(ok=True, part=part, parts=parts, more=part < parts,
               text=piece + (f"\n\n{MORE}" if part < parts else ""), channel=channel,
               when=ts.isoformat(timespec="seconds"), subject=" ".join(str(subject or "").split()),
               to=str(to_keys or account or "").strip(), papers=papers[:40],
               **{"from": f"{' '.join(str(name).split())} <{address}>" if name else address})
    common.write_json(READING, doc)
    return True, "Here it is." if parts == 1 else f"Here is part {part} of {parts}."


INLINE = re.compile(r"^(image\d+|outlook-[\w.-]+)\.(png|jpe?g|gif|bmp)$", re.I)       # pictures a mail program tucks into a signature


def net(pass_id):
    """In the pass: cards that waited for the database, and a plain card for any held message from someone who
    always gets through (so nothing from them is ever kept off the page). Returns how many cards were made."""
    import db
    import items
    items.ensure()
    made = 0
    want = [int(m) for m in (common.read_json(QUEUE, []) or [])]
    through = []
    if filters.get()["always_through"]:
        since = common.now() - dt.timedelta(minutes=45)      # what this pass and the one before it settled, not old mail
        marks = ",".join("?" for _ in HELD_VERDICTS)
        for mid, fk, name in db.query(
                f"""SELECT m.id, m.from_key, (SELECT max(c.name) FROM contacts c WHERE c.person_id = m.person_id AND c.name IS NOT NULL)
                    FROM messages m JOIN answered a ON a.domain='judged' AND a.key = 'msg:' || m.id
                    WHERE m.direction='in' AND a.answered_at >= ? AND a.verdict IN ({marks})""", (since, *HELD_VERDICTS)):
            if filters.gets_through(fk, name):
                through.append(mid)
    if not want and not through:
        return 0
    con = db.connect()
    try:
        for mid in want:
            made += 1 if _make(con, mid, pass_id) else 0
        for mid in through:
            made += 1 if _make(con, mid, pass_id, "They are on your list of people who always get through.", teach=False) else 0
    finally:
        con.close()
    common.write_json(QUEUE, [])
    return made
