r"""What the owner did outside the page, recorded in the rule book (the judgment rebuild, phase 1, "What it learns from").

Program code only, never Claude, run by each pass around its gather (pass.py). Every message he sent on any channel the
gathering reads (mail, texts, and any other channel connected) and every answer or move he made in his calendar becomes one
rule book row: what he did, where, and the card it belongs to when there is one (the same conversation, else the same person),
with that card's pick beside it and whether they matched. These rows say nothing about show or hide (meaning neutral, no
call), so the show-or-hide learning is untouched. A replay day writes nothing (rule_book._append).

    calendar_before()                    the calendar as it stands now: {event id: (summary, start, end, his answer)}
    record(pass_id, new_ids, before)     the rows for his sent messages among new_ids and his calendar changes since before
"""
import datetime as dt
import json
import os
import re
import uuid

import common

ANSWERS = {"accepted": "accepted", "declined": "declined", "tentative": "tentative"}
CARD_DAYS = 14              # cards closed this recently can still be what a sent message answered
PAGE_SEND_HOURS = 6         # a sent message within this long of a Send on the page, same subject, was sent from the page
GIST = 200
SUBJECT_PREFIX = re.compile(r"^\s*((re|fw|fwd)\s*:\s*)+", re.I)


def _log(what, e):
    common.log_line(os.path.join(common.LOGS, "errors.log"), f"off page {what}: {type(e).__name__}: {e}")


def calendar_before():
    """{event id: (summary, start, end, his answer)}, or None when the calendar cannot be read (nothing is compared then)."""
    try:
        import db
        con = db.try_connect()
        if con is None:
            return None
        try:
            cols = {str(r[0]) for r in con.execute("SELECT column_name FROM information_schema.columns "
                                                   "WHERE table_name = 'calendar_events'").fetchall()}
            mine = "my_response" if "my_response" in cols else "NULL"
            return {str(e): (s, a, b, r) for e, s, a, b, r in con.execute(
                f"SELECT event_id, summary, start_ts, end_ts, {mine} FROM calendar_events").fetchall()}
        finally:
            con.close()
    except Exception as e:  # noqa: BLE001
        _log("calendar read", e)
        return None


def _subject(s):
    return SUBJECT_PREFIX.sub("", " ".join(str(s or "").split())).lower()


def _page_sends():
    """[(when, channel, subject or the text's hash, card id, level)] for each send the page made (its own log of sends: send.py
    writes the emails, texts.py the texts); level: sent by me on my own at learning level 2 or 3 (levels.py), else None."""
    out = []
    try:
        with open(os.path.join(common.LOGS, "sent.log"), encoding="utf-8") as f:
            for line in f.read().splitlines()[-2000:]:
                try:
                    r = json.loads(line)
                    if r.get("result") == "sent":
                        ch = r.get("channel") or "email"
                        out.append((dt.datetime.fromisoformat(r["at"]), ch,
                                    r.get("digest") if ch == "sms" else _subject(r.get("subject")), r.get("item"), r.get("level")))
                except (ValueError, KeyError, TypeError):
                    continue
    except OSError:
        pass
    return out


def _cards():
    """Open cards and those closed lately, with their messages' conversations and people."""
    import db
    import items
    cut = common.now() - dt.timedelta(days=CARD_DAYS)
    cards = items.rows("state <> 'done' OR done_at >= ?", (cut,))
    ids = sorted({int(m) for c in cards for m in c.get("source_messages") or [] if str(m).isdigit()})
    about = {}
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        for mid, thread, person in db.query(f"SELECT id, thread_id, person_id FROM messages WHERE id IN "
                                            f"({','.join('?' for _ in part)})", tuple(part)):
            about[str(mid)] = (thread, person)
    return cards, about


def _card_for(cards, about, thread, person):
    """The card a sent message belongs to: the newest one holding the same conversation, else the same person; or None."""
    for test in ((lambda t, p: thread and t == thread), (lambda t, p: person is not None and p == person)):
        for c in sorted(cards, key=lambda c: str(c.get("updated_at") or ""), reverse=True):
            if any(test(*about.get(str(m), (None, None))) for m in c.get("source_messages") or []):
                return c
    return None


def _row(at, key, section, card, seen, off, did_words=""):
    import picks
    import rule_book
    pick = picks.of(card, closed_too=True) if card else None
    return dict({"id": uuid.uuid4().hex[:16], "at": at, "message": key, "section": section,
                 "card": (card or {}).get("id"), "card_kind": (card or {}).get("kind"), "card_area": (card or {}).get("area"),
                 "card_important": rule_book._important(card) if card else None,
                 "call": None, "layer": "owner", "verdict": None, "source": None, "rules": [], "covered": None,
                 "leaned_on": None, "seen": seen, "press": off["did"] if off["did"] == "sent" else "calendar",
                 "meaning": "neutral", "button": "-", "choice": "-", "status": "active", "off_page": off},
                **(rule_book._pick_fields(card, "sent" if off["did"] == "sent" else "press", "-", did_words, pick, False)
                   if pick and off["did"] == "sent" else {}))


def _sent(new_ids, cards, about):
    import db
    ids = sorted({int(i) for i in new_ids or [] if str(i).isdigit()})
    if not ids:
        return []
    got = db.query(f"SELECT id, channel, account, thread_id, ts, to_keys, subject, body, person_id FROM messages WHERE"
                   f" direction = 'out' AND id IN ({','.join('?' for _ in ids)}) ORDER BY id", tuple(ids))
    if not got:
        return []
    import texts
    page = _page_sends()
    out = []
    texted = [(thread, ts, body) for mid, channel, account, thread, ts, to, subject, body, person in got
              if channel == "sms" and thread and str(body or "").strip()]
    if texted:          # a text from his phone answering a text I drafted: what he kept of it is learned (texts.py, writing.py)
        try:
            import texts
            texts.learn_sent_outside(texted)
        except Exception as e:  # noqa: BLE001
            _log("text draft lesson", e)
    for mid, channel, account, thread, ts, to, subject, body, person in got:
        key = _subject(subject) if channel == "email" else texts.text_digest(body) if channel == "sms" else ""
        hit = next(((item, lv) for when, ch, s, item, lv in page if key and ch == channel and s == key
                    and abs((when - ts).total_seconds()) <= PAGE_SEND_HOURS * 3600), None)
        if hit and hit[1]:
            continue                # I sent it on my own at a learning level: not something he did
        from_page = hit[0] if hit else False
        card = _card_for(cards, about, thread, person)
        if from_page and not card:
            card = next((c for c in cards if c.get("id") == from_page), None)
        gist = " ".join(str(body or "").split())[:GIST]
        try:
            to_words = ", ".join(json.loads(to)) if str(to or "").startswith("[") else str(to or "")
        except ValueError:
            to_words = str(to or "")
        off = {"did": "sent", "channel": channel, "account": account, "to": to_words[:200],
               "where": "page" if from_page is not False else "outside"}
        out.append(_row(ts.isoformat(timespec="seconds"), str(mid), "replies", card,
                        {"sender": to_words[:120], "what": (" ".join(str(subject or "").split()) or gist)[:160], "channel": channel},
                        off, gist))
    return out


def _calendar(before, cards):
    if not before:
        return []
    after = calendar_before() or {}
    out, now = [], common.now().isoformat(timespec="seconds")
    for eid, (summary, start, end, resp) in after.items():
        was = before.get(eid)
        if not was:
            continue
        did = None
        if was[3] and resp in ANSWERS and resp != was[3]:
            did = ANSWERS[resp]             # he answered the invitation (a first answer, or a change of mind)
        elif was[1] and start and start != was[1]:
            did = "moved"
        if not did:
            continue
        title = " ".join(str(summary or "").split())
        card = next((c for c in cards if isinstance(c.get("calendar"), dict)
                     and " ".join(str(c["calendar"].get("title") or "").split()).lower() == title.lower()), None) if title else None
        off = {"did": did, "channel": "calendar", "where": "outside",
               "was": str(was[1]) if did == "moved" else was[3], "now": str(start) if did == "moved" else resp}
        out.append(_row(now, f"cal:{eid}", "calendar", card, {"sender": "", "what": title[:160], "channel": "calendar"}, off))
    return out


def record(pass_id, new_ids, before):
    """Write the rows; returns how many. Never raises: anything it cannot do is logged and the pass goes on."""
    try:
        import rule_book
        if rule_book._replaying():
            return 0
        cards, about = _cards()
        rows = _sent(new_ids, cards, about) + _calendar(before, cards)
        n = rule_book._append(rows)
        if n:
            rule_book._misses(rows)         # a reply that differed from my pick queues the coach for its kind of work
        return n
    except Exception as e:  # noqa: BLE001
        _log(f"record {pass_id}", e)
        return 0
