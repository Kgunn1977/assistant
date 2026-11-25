r"""Contacts, in Settings (the owner, 11/25: "EVERY contact is tracked").

Everyone he ever wrote to or heard from, in mail, texts and any channel connected, one-time senders included, everyone in
the setup's history catalog, and everyone in his phone's and his mail accounts' address books (the contacts table, kept by
core\refresh_contacts.py). Each person carries:
    last_in_touch, how_often        when he and they last wrote either way, and how often (contact_strength's counts and words)
    open_matters                    open cards both ways: "yours" waits on him, "theirs" waits on them
    history                         recent messages, cards and decisions (his presses on their cards)
    notes, learned                  his own notes, and what the assistant learned (the look-back's context, the counts)
    where                           where they come from: mail, texts, another channel, the history catalog, an address book

    page(q, offset, limit)          one page for the page's Settings, newest contact first (asked for when Contacts opens)
    count()                         how many there are (in the Settings data; the list itself is never sent in one block)
    act(rec)                        Save on a person's notes ({"contact_note": {"person": id, "notes": "..."}})
"""
import datetime as dt
import json
import os
import re

import common
import db

NOTES = os.path.join(common.PERSONAL, "contact_notes.json")
NOTES_MAX = 2000
HISTORY_EACH = 3            # messages, cards and decisions kept per person in the list
ADDRESS = r"[a-z0-9][a-z0-9._%+=''-]*@[a-z0-9-]+(?:\.[a-z0-9-]+)+"
SOURCE_WORDS = {"self": "you", "seen_in_mail": "mail", "seen_in_history": "your history catalog", "seen_in_sms": "texts"}


def _where(src):
    s = str(src or "")
    if s.startswith("address_book:phone"):
        return "your phone's contacts"
    if s.startswith("address_book:"):
        return "the address book of " + s.split(":", 1)[1]
    if s.startswith("seen_in_"):
        return SOURCE_WORDS.get(s, common.channel_word(s[len("seen_in_"):]) + " messages")
    if s.endswith("_users_list"):
        return common.channel_word(s[:-len("_users_list")])
    return SOURCE_WORDS.get(s, "mail" if not s else s.replace("_", " "))


def _has(con, table):
    return bool(con.execute("SELECT 1 FROM information_schema.tables WHERE table_name = ?", [table]).fetchone())


def _plain(v):
    return v.isoformat(timespec="minutes") if isinstance(v, (dt.datetime, dt.date)) else v


def notes():
    return common.read_json(NOTES, {}) or {}


def _people(con):
    """{person id: summary} from the contacts table, and {key: person id}, and the owner's person ids."""
    cols = {r[0] for r in con.execute("SELECT column_name FROM information_schema.columns WHERE table_name='contacts'").fetchall()}
    want = [c for c in ("key", "person_id", "name", "name_source", "first_seen", "last_seen", "sent_count", "received_count",
                        "sent_90", "received_90", "weeks_written", "strength") if c in cols]
    rows = [dict(zip(want, r)) for r in con.execute(f"SELECT {', '.join(want)} FROM contacts").fetchall()]
    people = {}
    for r in rows:
        p = people.setdefault(r["person_id"], {"person": r["person_id"], "name": None, "keys": [], "where": [],
                                               "sent": 0, "received": 0, "sent_90": 0, "received_90": 0, "weeks_written": 0,
                                               "strength": 0.0})
        p["keys"].append(str(r["key"]).lower())
        p["name"] = p["name"] or r.get("name")
        w = _where(r.get("name_source"))
        if w not in p["where"]:
            p["where"].append(w)
        for a, b in (("sent", "sent_count"), ("received", "received_count"), ("sent_90", "sent_90"),
                     ("received_90", "received_90"), ("weeks_written", "weeks_written")):
            p[a] += int(r.get(b) or 0)
        p["strength"] = max(p["strength"], float(r.get("strength") or 0))
    owner = {r["person_id"] for r in rows if r.get("name_source") == "self"}
    key_to = {k: pid for pid, p in people.items() for k in p["keys"]}
    return people, key_to, owner


def _last(con, key_to):
    """{person id: last time either wrote}, counted in the database (grouped), plus the history catalog's envelopes."""
    last = {}

    def take(k, ts):
        pid = key_to.get(str(k or "").lower())
        if pid is not None and ts and (pid not in last or ts > last[pid]):
            last[pid] = ts
    for k, ts in con.execute("SELECT lower(from_key), max(ts) FROM messages WHERE direction='in' GROUP BY 1").fetchall():
        take(k, ts)
    for k, ts in con.execute("SELECT 'email:' || a, max(ts) FROM (SELECT unnest(regexp_extract_all(lower(coalesce(to_keys, '')), ?)) AS a, ts"
                             " FROM messages WHERE direction='out' AND channel='email') GROUP BY 1", [ADDRESS]).fetchall():
        take(k, ts)
    for k, ts in con.execute("SELECT lower(to_keys), max(ts) FROM messages WHERE direction='out' AND channel NOT IN ('email', 'calendar')"
                             " GROUP BY 1").fetchall():
        take(k, ts)
    if _has(con, "envelopes"):
        for k, ts in con.execute("SELECT lower(from_key), max(ts) FROM envelopes WHERE direction='in' GROUP BY 1").fetchall():
            take(k, ts)
        for k, ts in con.execute("SELECT 'email:' || a, max(ts) FROM (SELECT unnest(from_json(to_keys, '[\"VARCHAR\"]')) AS a, ts"
                                 " FROM envelopes WHERE direction='out') GROUP BY 1").fetchall():
            take(k, ts)
    return last


def count(con=None):
    """How many contacts there are (the owner left out), for Settings' line; one quick read."""
    own = con is None
    con = con or db.connect(read_only=True)
    try:
        return con.execute("SELECT count(DISTINCT person_id) FROM contacts WHERE person_id NOT IN "
                           "(SELECT person_id FROM contacts WHERE name_source = 'self')").fetchone()[0]
    finally:
        if own:
            con.close()


def page(q="", offset=0, limit=50, con=None):
    """One page of Contacts, newest contact first, narrowed by words in a name or an address: {"people", "total", "offset"}.
    The page asks for it when Contacts is opened (and for more as he scrolls or searches), never in one block."""
    own = con is None
    con = con or db.connect(read_only=True)
    try:
        people, key_to, owner = _people(con)
        last = _last(con, key_to)
        words = str(q or "").lower().strip()
        pids = [pid for pid, p in people.items() if pid not in owner and
                (not words or words in str(p["name"] or "").lower() or any(words in k for k in p["keys"]))]
        pids.sort(key=lambda pid: (str(last.get(pid) or ""), -pid), reverse=True)
        offset, limit = max(0, int(offset or 0)), max(1, min(int(limit or 50), 10000))
        chosen = pids[offset:offset + limit]
        out = _details(con, chosen, people, key_to, owner, last)
    finally:
        if own:
            con.close()
    return {"people": out, "total": len(pids), "offset": offset}


def for_settings(con=None):
    """Every contact with every field, in one list (the checks use it; the page asks for pages instead)."""
    return page(limit=10000, con=con)["people"]


def _details(con, chosen, people, key_to, owner, last):
    """Each chosen person whole: how often, open matters both ways, history, notes and what was learned."""
    import contact_strength
    if not chosen:
        return []
    keys = [k for pid in chosen for k in people[pid]["keys"]]
    want = set(chosen)
    hist, msg_people = {}, {}
    if len(keys) <= 400:        # a page's people: only their messages are read
        where = (f"WHERE (direction = 'in' AND lower(from_key) IN ({','.join('?' * len(keys))})) OR (direction = 'out' AND ("
                 + " OR ".join(["lower(to_keys) LIKE ?"] * len(keys)) + ")) ORDER BY ts DESC LIMIT 20000")
        args = keys + [f"%{_bare(k)}%" for k in keys]
    else:                       # everyone at once (the checks): one read of all
        where, args = "ORDER BY ts DESC", []
    for mid, ch, direction, fk, to, ts, subj, body in con.execute(
            "SELECT id, channel, direction, lower(from_key), lower(coalesce(to_keys, '')), ts, subject, "
            "CASE WHEN channel <> 'email' THEN left(coalesce(body, ''), 80) END FROM messages " + where, args).fetchall():
        mk = [fk] if direction == "in" else (["email:" + a for a in re.findall(ADDRESS, to)] if ch == "email"
                                             else [k.strip() for k in re.split(r"[,\[\]\"]", to) if ":" in k])
        pids = {key_to[k] for k in mk if k in key_to} & want
        msg_people[mid] = pids
        for pid in pids:
            h = hist.setdefault(pid, [])
            if len(h) < HISTORY_EACH:
                h.append({"at": _plain(ts), "way": "from them" if direction == "in" else "from you",
                          "channel": common.channel_word(ch), "what": " ".join(str(subj or body or "").split())[:100]})
    cards, matters = {}, {}
    if _has(con, "live_items"):
        rows = con.execute("SELECT id, coalesce(short_header, title), state, source_messages, updated_at FROM live_items "
                           "WHERE NOT starts_with(source_key, 'live:setup-') ORDER BY updated_at DESC LIMIT 5000").fetchall()
        for iid, title, state, srcs, upd in rows:
            try:
                mids = [int(x) for x in json.loads(srcs or "[]")]
            except (ValueError, TypeError):
                mids = []
            pids = set().union(*[msg_people.get(m, set()) for m in mids]) if mids else set()
            for pid in pids:
                c = cards.setdefault(pid, [])
                if len(c) < HISTORY_EACH:
                    c.append({"card": iid, "title": str(title or "")[:120], "state": state, "at": _plain(upd)})
                side = "yours" if state in ("question", "yours", "new") else "theirs" if state == "in_motion" else None
                if side:
                    matters.setdefault(pid, {"yours": [], "theirs": []})[side].append({"card": iid, "title": str(title or "")[:120]})
    card_people = {c["card"]: pid for pid, cs in cards.items() for c in cs}
    decisions = {}
    if _has(con, "live_presses") and card_people:
        ids = list(card_people)
        for iid, press, choice, at, happened in con.execute(
                "SELECT item_id, press, choice, pressed_at, happened FROM live_presses WHERE item_id IN ("
                + ",".join("?" * len(ids)) + ") ORDER BY pressed_at DESC", ids).fetchall():
            d = decisions.setdefault(card_people[iid], [])
            if len(d) < HISTORY_EACH:
                d.append({"card": iid, "press": choice or press, "at": _plain(at), "happened": str(happened or "")[:160]})
    learned = {}
    if _has(con, "sender_context"):
        for k, summary in con.execute("SELECT key, summary FROM sender_context WHERE kind='sender' AND key IN ("
                                      + ",".join("?" * len(keys)) + ")", keys).fetchall():
            if summary:
                learned[key_to[k]] = summary
    mine = notes()
    out = []
    for pid in chosen:
        p = people[pid]
        lv = contact_strength._words(p["name"] or "", p["weeks_written"], p["strength"])[1]
        often = (f"You wrote {p['sent']} and they wrote {p['received']}"
                 + (f"; {p['sent_90'] + p['received_90']} in the last 90 days" if p["sent_90"] or p["received_90"] else "; none in the last 90 days")
                 + ".")
        out.append({
            "person": pid, "name": p["name"] or _bare(p["keys"][0]),
            "addresses": [_bare(k) for k in p["keys"]], "where": p["where"],
            "last_in_touch": _plain(last.get(pid)), "how_often": often, "one_time": p["sent"] == 0 and p["received"] <= 1,
            "open_matters": matters.get(pid, {"yours": [], "theirs": []}),
            "history": {"messages": hist.get(pid, []), "cards": cards.get(pid, []), "decisions": decisions.get(pid, [])},
            "notes": (mine.get(str(pid)) or {}).get("notes") or "",
            "learned": " ".join(x for x in (learned.get(pid) or "", lv) if x).strip(),
        })
    return out


def _bare(key):
    k = str(key or "")
    return k.split(":", 1)[1] if ":" in k else k


def act(rec):
    """Save on a person's notes in Settings, Contacts, in the shape answers.act_on_answer returns. Never raises."""
    try:
        body = json.loads(rec.get("text") or "")
        p = body.get("contact_note") if isinstance(body, dict) else None
        pid = str((p or {}).get("person") or "")
        if not re.fullmatch(r"\d{1,9}", pid):
            said = "Not saved: that was not a contact's notes."
        else:
            words = str((p or {}).get("notes") or "").strip()[:NOTES_MAX]
            got = notes()
            if words:
                got[pid] = {"notes": words, "at": common.now().isoformat(timespec="seconds")}
            else:
                got.pop(pid, None)
            common.write_json(NOTES, got)
            said = "Your notes are saved." if words else "Your notes are cleared."
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"contact notes: {type(e).__name__}: {e}")
        said = f"Not saved: something went wrong on your computer ({type(e).__name__})."
    return {"ok": True, "items": [], "result": said, "thought": False, "secs": {}}
