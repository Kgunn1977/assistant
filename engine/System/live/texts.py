r"""The owner's texts on the page: every conversation newest first, a whole thread, search, unread marks, and sending.

Texts come from the texts link straight to Google Messages (textlink.py); texts stored earlier (by the Chrome extension the
assistant used before, and from older phone backups) stay as they are. All are stored as channel sms.
One person's backup thread and Google Messages conversation are one conversation here. Reading is the stored texts only.

Sending is only ever the owner's own press of Send. The page's Send press queues the text here (queue_send); nothing the
assistant writes is queued: its text drafts (draft) wait in the panel for the owner to edit and press Send. When the texts link is
signed in it takes each queued text (next_send) and sends it through Google straight away, then reports sent or failed (report).
A text the link cannot place (no conversation of the link's and no number) is not queued. A text is handed out once; one that was
handed out and never reported is marked failed, never sent again by itself.

    conversations(q, before, limit)   the list: {rows: [{id, name, group, last, when, from_me, unread, count}], more, next}
    thread(conv, limit)               one conversation, oldest first, with who can be answered, its sends and its draft
    mark_read(conv)                   the owner has seen it
    queue_send(conv, text, to, name)  the Send press: {ok, id} or {ok: False, error}
    cancel(id)                        a queued text not yet handed to the link, or a failed one, is taken off
    next_send()                       the link's sender: the oldest queued text, handed out once, or None
    report(id, ok, error)             the link's word on a text it was handed
    draft(...)                        the assistant's draft for the panel (never queued)
    for_chat(words)                   recent texts for the chat to read
"""
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import threading
import time

import common

STATE = common.paths.STATE
OWNER_THREADS = 40              # a person in this many threads is the owner's own number, not a contact
GM_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{4,}$")      # a conversation id of Messages
READ = os.path.join(STATE, "texts_read.json")
LINK_CONVS = os.path.join(STATE, "texts_link_convs.json")
PIC_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp")      # shown in the conversation; any other file is offered to save   # older conversations matched to the texts link's own: {thread id: {gl, phone}}
OUTBOX = os.path.join(STATE, "texts_outbox.json")
DRAFTS = os.path.join(STATE, "texts_drafts.json")
MOST_TEXT = 3000
MOST_QUEUED = 20
QUEUE_SECONDS = 180             # a text no tab picked up by then is failed, with the reason, not left waiting
LEASE_SECONDS = 180             # a text handed out and not reported by then is failed, never resent
SHOW_SENT_MINUTES = 10          # a sent text shows under the thread until the texts link has read it back, at most this long
SAME_SECONDS = 120
lock = threading.RLock()


class Busy(Exception):
    """A pass holds the database this moment."""


def _read(tries=6):
    import db
    import texts_cache
    cur = texts_cache.reader()          # the page's own small copy of the texts (a search takes hundredths of a second); None when it is off or not built
    if cur is not None:
        return cur
    for i in range(tries):
        con = db.try_connect(read_only=True)
        if con is not None:
            return con
        if i < tries - 1:
            time.sleep(0.5)
    raise Busy()


def _iso(ts):
    return ts.isoformat(timespec="seconds") if ts else ""


def _num(key):
    return key.split(":", 1)[1] if str(key or "").startswith("phone:") else ""


def _pretty(digits):
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}" if len(digits) == 10 else digits


def _names(con):
    """{person id: name} for every person with one. The one rule for a text person's name, used by a conversation's header and by
    each text's sender label: the contact's name; and when that name is only a number (a text from a group stored the number as
    the name), the one person's own name the backup gave their texts (a subject with no comma and not a number)."""
    names = {r[0]: r[1] for r in con.execute(
        "SELECT person_id, min(name) FROM contacts WHERE name IS NOT NULL AND name <> '' GROUP BY person_id").fetchall()}
    bare = [p for p, nm in names.items() if re.fullmatch(r"[\d\s()+.-]{3,}", nm.strip())]
    if bare:
        marks = ",".join("?" for _ in bare)
        for p, subj in con.execute(
                f"SELECT person_id, mode(subject) FROM messages WHERE channel='sms' AND person_id IN ({marks}) AND subject IS NOT NULL "
                f"AND subject NOT LIKE '%,%' AND NOT regexp_matches(subject, '^[0-9 ()+.-]*$') GROUP BY person_id", bare).fetchall():
            names[p] = subj
    return names


# --- conversations ----------------------------------------------------------------------------------------------
def _threads(con, links=True):
    """Every stored text thread, merged into conversations: one person's threads (a backup's, Google Messages') are one
    conversation; a thread of several people stays its own. With `links`, a conversation stored before the texts link gets
    the link's conversation id it was matched to (link_match), is one with the link's own thread of it, and a one-to-one
    conversation with no number on file gets the one number its texts show. Returns {conv id: {...}}."""
    rows = con.execute(
        "SELECT thread_id, max(ts), count(*), count(person_id), count(DISTINCT person_id), min(person_id), "
        "arg_max(coalesce(body, ''), ts), arg_max(direction, ts), mode(nullif(subject, '')), "
        "max(CASE WHEN provider_id LIKE 'gm:%' THEN ts END), arg_max(provider_id, CASE WHEN provider_id LIKE 'gm:%' THEN ts END), "
        "max(CASE WHEN provider_id LIKE 'gl:%' THEN ts END), arg_max(provider_id, CASE WHEN provider_id LIKE 'gl:%' THEN ts END) "
        "FROM messages WHERE channel='sms' AND thread_id IS NOT NULL GROUP BY thread_id").fetchall()
    names = _names(con)
    keys = {r[0]: r[1] for r in con.execute(
        "SELECT person_id, min(key) FROM contacts WHERE key LIKE 'phone:%' GROUP BY person_id").fetchall()}
    pairs = con.execute("SELECT thread_id, person_id FROM messages WHERE channel='sms' AND person_id IS NOT NULL AND thread_id IS NOT NULL "
                        "GROUP BY thread_id, person_id").fetchall()
    spread = {}
    for _t, p in pairs:
        spread[p] = spread.get(p, 0) + 1
    owner = {p for p, n in spread.items() if n >= OWNER_THREADS}        # the owner's own number sits in a great many threads, as one of two people
    who = {}
    for t, p in pairs:
        if p not in owner:
            who.setdefault(t, set()).add(p)
    by_name = {}
    for p, nm in names.items():
        by_name.setdefault(nm.lower(), set()).add(p)
    alias = {}                                                          # a person known only by name (an older import) is the phone person of the same name, when there is exactly one
    for p, nm in names.items():
        if p not in keys:
            same = {q for q in by_name[nm.lower()] if q in keys}
            if len(same) == 1:
                alias[p] = next(iter(same))
    out = {}
    groups = set((common.read_json(os.path.join(STATE, "google_messages_groups.json"), {}) or {}).get("convs") or [])
    for tid, last, n, withp, distinct, pid, body, direction, subject, gm_ts, gm_pid, gl_ts, gl_pid in rows:
        people = {alias.get(p, p) for p in who.get(tid, set())}
        pid = None
        if tid not in groups:
            if len(people) == 1:
                pid = next(iter(people))                                 # texts of one other person (the owner's own do not count); a group is never merged
            elif not people and subject and GM_ID.match(tid):            # a Messages conversation with no person on its texts: the one person who has its name
                same = {alias.get(p, p) for p in by_name.get(subject.lower(), set())} - owner
                if len(same) == 1:
                    pid = next(iter(same))
        one = pid is not None
        solo = not one and not people and tid not in groups              # a one-to-one thread whose person is not known: its own conversation, not a group
        cid = f"p{pid}" if one else f"t{tid}"
        c = out.setdefault(cid, {"id": cid, "threads": [], "last": None, "count": 0, "group": not (one or solo), "pid": pid if one else None,
                                 "subject": "", "gm": "", "gm_ts": None, "gl": "", "gl_ts": None, "phone": ""})
        c["threads"].append(tid)
        c["count"] += n
        if c["last"] is None or last > c["last"]:
            c["last"], c["body"], c["from_me"] = last, " ".join(body.split()), direction == "out"
        if subject and not c["subject"]:
            c["subject"] = subject
        if gm_pid and gm_ts and (c["gm_ts"] is None or gm_ts > c["gm_ts"]):
            c["gm_ts"], c["gm"] = gm_ts, gm_pid.split(":", 2)[1] if gm_pid.count(":") >= 2 else ""
        if gl_pid and gl_ts and (c["gl_ts"] is None or gl_ts > c["gl_ts"]):        # Google Messages' own conversation id, from the texts link
            c["gl_ts"], c["gl"] = gl_ts, gl_pid.split(":", 2)[1] if gl_pid.count(":") >= 2 else ""
        if one:
            c["phone"] = _num(keys.get(pid))
            if not c["phone"] and re.fullmatch(r"\+?\d[\d\s().-]{6,}", tid or ""):
                c["phone"] = re.sub(r"\D", "", tid)[-10:]
    for cid, c in out.items():
        if c["pid"] is not None:
            c["name"] = names.get(c["pid"]) or c["subject"] or (_pretty(c["phone"]) if c["phone"] else "Unknown")
        else:
            members = c["subject"] if ("," in c["subject"] or not c["group"]) else ""           # Messages' header gives a group's members; a backup row's subject is only one sender's name
            c["name"] = members or _group_name(con, c["threads"], names) or c["subject"] or ("Unknown" if not c["group"] else "Group conversation")
    byset = {}
    for cid, c in list(out.items()):                  # one group, one conversation: the backup's thread and Messages' conversation with the same members
        mem = frozenset(x.strip().lower() for x in c["name"].split(",") if x.strip()) if c["group"] and "," in c["name"] else None
        if mem and len(mem) >= 2:
            if mem in byset:
                have = out[byset[mem]]
                first, second = (have, c) if (have["gm"] or not c["gm"]) else (c, have)
                first["threads"] = first["threads"] + [t for t in second["threads"] if t not in first["threads"]]
                first["count"] += second["count"]
                if second["last"] and (first["last"] is None or second["last"] > first["last"]):
                    first["last"], first["body"], first["from_me"] = second["last"], second["body"], second["from_me"]
                del out[second["id"]]
                byset[mem] = first["id"]
            else:
                byset[mem] = cid
    if links:
        _linked(con, out, keys, owner, names)
    return out


def _merge(first, second):
    first["threads"] = first["threads"] + [t for t in second["threads"] if t not in first["threads"]]
    first["count"] += second["count"]
    if second["last"] and (first["last"] is None or second["last"] > first["last"]):
        first["last"], first["body"], first["from_me"] = second["last"], second["body"], second["from_me"]
    if second.get("gl") and (not first.get("gl") or (second.get("gl_ts") and (first.get("gl_ts") is None or second["gl_ts"] > first["gl_ts"]))):
        first["gl_ts"], first["gl"] = second.get("gl_ts"), second["gl"]
    first["phone"] = first["phone"] or second["phone"]
    if first["pid"] is None and second["pid"] is not None:
        first["pid"] = second["pid"]
    if first["name"].strip().lower() in NONAMES:
        first["name"] = second["name"]


def _keeper(a, b):
    """Of two conversations becoming one, the one whose id stays: a person's, then one with the link's id, then the larger."""
    rank = lambda c: (c["pid"] is not None, bool(c["gl"]), c["count"])
    return (a, b) if rank(a) >= rank(b) else (b, a)


def _join(out, a_id, b_id):
    first, second = _keeper(out[a_id], out[b_id])
    _merge(first, second)
    first["was"] = first.get("was", []) + [second["id"]] + second.get("was", [])      # its old ids still open it
    del out[second["id"]]
    return first["id"]


def _linked(con, out, keys, owner, names):
    m = (common.read_json(LINK_CONVS, {}) or {}).get("threads") or {}
    for c in out.values():
        if not c["gl"]:
            hit = next((m[t] for t in c["threads"] if isinstance(m.get(t), dict) and m[t].get("gl")), None)
            if hit:
                c["gl"] = str(hit["gl"])
                if not c["group"] and not c["phone"]:
                    c["phone"] = str(hit.get("phone") or "")
    mine = {_num(keys[p]) for p in owner if p in keys}
    my_names = {names[p].strip().lower() for p in owner if names.get(p)}
    for c in out.values():                       # no link id and no number: the one number its texts show
        if c["group"] or c["gl"] or c["phone"]:
            continue
        marks = ",".join("?" for _ in c["threads"])
        nums = {_num(r[0]) for r in con.execute(
            f"SELECT DISTINCT from_key FROM messages WHERE channel='sms' AND thread_id IN ({marks}) AND from_key LIKE 'phone:%'", list(c["threads"])).fetchall()}
        nums |= {_num(keys.get(r[0])) for r in con.execute(
            f"SELECT DISTINCT person_id FROM messages WHERE channel='sms' AND thread_id IN ({marks}) AND person_id IS NOT NULL", list(c["threads"])).fetchall()}
        nums.discard("")
        rest = nums - mine
        if len(rest) == 1:
            c["phone"] = rest.pop()
        elif not rest and len(nums) == 1 and c["name"].strip().lower() in my_names:
            c["phone"] = nums.pop()              # only his own number, under his own name: his notes to himself
    # one conversation, not several: threads with the same Messages conversation, or one-to-one threads with the same number,
    # are one; so are one-to-one conversations of the same name whose numbers and Messages conversations do not differ
    for field in ("gl", "phone"):
        seen = {}
        for cid in list(out):
            c = out.get(cid)
            if c is None or not c[field] or (c["group"] and field == "phone"):      # a group is one only by its Messages conversation
                continue
            have = seen.get(c[field])
            if have and have in out and have != cid:
                seen[c[field]] = _join(out, have, cid)
            else:
                seen[c[field]] = cid
    byname = {}
    for cid, c in out.items():
        nm = c["name"].strip().lower()
        if not c["group"] and nm not in NONAMES:
            byname.setdefault(nm, []).append(cid)
    for ids in byname.values():
        ids = [x for x in ids if x in out]
        phones = {out[x]["phone"] for x in ids} - {""}
        gls = {out[x]["gl"] for x in ids} - {""}
        if len(ids) < 2 or len(phones) > 1 or not (phones or gls):
            continue                              # two numbers: two people of one name. Several Messages conversations of one
                                                  # person (an SMS one and an RCS one) are one; it is answered in the newest
        kept = ids[0]
        for x in ids[1:]:
            kept = _join(out, kept, x)


def _norm(name):
    return " ".join(str(name or "").split()).lower()


def _ten(number):
    """A number as matched: its last ten digits, or a short code's digits (a text service's 5 or 6 digit number)."""
    d = re.sub(r"\D", "", str(number or ""))
    return d[-10:] if len(d) >= 10 else (d if len(d) >= 3 else "")


def _as_number(name):
    """A conversation whose name is only a number (or a short code) is matched by that number."""
    return _ten(name) if re.fullmatch(r"[\d\s()+.-]{3,}", str(name or "").strip()) else ""


def link_match(convs):
    """The texts link's conversation list (id, name, group, the other people's numbers and names) matched to the conversations
    stored before the link: by Messages id, then by number, then by name (a group by its exact members). One person often has
    several Messages conversations (a text one and a chat one): the one with the newest text is taken. Kept in LINK_CONVS,
    never taken away. Returns {"matched": n, "unmatched": n} over the older conversations (those with no link text of their own)."""
    ids, phone, name, gname, members, last = set(), {}, {}, {}, {}, {}
    listed = {"one-to-one": 0, "with a number": 0, "groups": 0}
    for v in convs or []:
        gid = str((v or {}).get("id") or "")[:120]
        if not gid:
            continue
        ids.add(gid)
        try:
            last[gid] = int(v.get("last") or 0)
        except (TypeError, ValueError):
            last[gid] = 0
        others = [o for o in (v.get("others") or []) if isinstance(o, dict)]
        names = {_norm(o.get("name")) for o in others} - {""}
        listed["groups" if v.get("group") else "one-to-one"] += 1
        if not v.get("group"):
            nums = {_ten(o.get("number")) for o in others} - {""}
            ph = next(iter(nums)) if len(nums) == 1 else ""
            listed["with a number"] += bool(ph)
            if ph:
                phone.setdefault(ph, set()).add((gid, ph))
            for nm in names | {_norm(v.get("name"))} - {""}:
                name.setdefault(nm, set()).add((gid, ph))
        else:
            if len(names) >= 2:
                members.setdefault(frozenset(names), set()).add((gid, ""))
            if _norm(v.get("name")):
                gname.setdefault(_norm(v.get("name")), set()).add((gid, ""))

    def one(found):
        """The newest of the Messages conversations found, when they are all one person's (one number, or none known)."""
        if not found or len({ph for _g, ph in found} - {""}) > 1:
            return None
        return max(found, key=lambda x: last.get(x[0], 0))

    with _read() as con:
        convs_here = _threads(con, links=False)
    with lock:
        d = common.read_json(LINK_CONVS, {}) or {}
        m = d.get("threads") if isinstance(d.get("threads"), dict) else {}
        matched = unmatched = 0
        left = []
        for c in convs_here.values():
            if c["gl"]:
                continue                         # the link's own: it has its id already
            gid, ph = (c["gm"] if c["gm"] in ids else None), ""
            if not gid and not c["group"]:
                num = c["phone"] or _as_number(c["name"])
                hit = one(phone.get(num)) if num else None
                if not hit and _norm(c["name"]) not in NONAMES:
                    hit = one(name.get(_norm(c["name"])))
                gid, ph = hit if hit else (None, "")
            elif not gid:
                mem = frozenset(_norm(x) for x in c["name"].split(",") if _norm(x)) if "," in c["name"] else None
                hit = one(members.get(mem)) if mem and len(mem) >= 2 else None
                hit = hit or (one(gname.get(_norm(c["name"]))) if _norm(c["name"]) not in NONAMES else None)
                gid = hit[0] if hit else None
            if gid:
                matched += 1
                for t in c["threads"]:
                    m[t] = {"gl": gid, "phone": "" if c["group"] else (c["phone"] or ph)}
            elif not any(isinstance(m.get(t), dict) for t in c["threads"]):
                unmatched += 1
                left.append(c)
            else:
                matched += 1                      # matched on an earlier run; that match is kept
        common.write_json(LINK_CONVS, dict(d, threads=m))
        with _read() as con:
            shown = _threads(con)
        older = [c for c in shown.values() if not any(t.startswith("gl:") for t in c["threads"])]
        matched = sum(1 for c in older if c["gl"])
        left = [c for c in older if not c["gl"]]
        unmatched = len(left)
        recent = common.now() - dt.timedelta(days=90)
        why = {"groups": sum(1 for c in left if c["group"]), "with a number": sum(1 for c in left if not c["group"] and c["phone"]),
               "with neither": sum(1 for c in left if not c["group"] and not c["phone"]),
               "last text in 90 days": sum(1 for c in left if c["last"] and c["last"] >= recent)}
        newest = sorted((c for c in left if c["last"]), key=lambda c: c["last"], reverse=True)[:40]
        common.write_json(LINK_CONVS, {"at": _iso(common.now()), "threads": m, "matched": matched, "unmatched": unmatched, "unmatched_kinds": why,
                                       "unmatched_newest": [{"id": c["id"], "name": c["name"], "last": _iso(c["last"]), "group": c["group"],
                                                             "number": bool(c["phone"])} for c in newest]})
    return {"matched": matched, "unmatched": unmatched, "kinds": why, "listed": listed}


def _group_name(con, threads, names):
    marks = ",".join("?" for _ in threads)
    rows = con.execute(f"SELECT from_key, person_id FROM messages WHERE channel='sms' AND direction='in' AND thread_id IN ({marks}) "
                       f"AND from_key IS NOT NULL GROUP BY from_key, person_id ORDER BY min(ts) LIMIT 4", list(threads)).fetchall()
    who = []
    for key, pid in rows:
        label = names.get(pid) or (str(key)[4:] if str(key).startswith("sms:") else _pretty(_num(key)))
        if label and label not in who:
            who.append(label)
    return ", ".join(who[:3])


def _marks():
    d = common.read_json(READ, None)
    if not isinstance(d, dict) or not d.get("base"):
        d = {"base": _iso(common.now()), "read": {}}      # texts already here when the page first looked are not unread
        common.write_json(READ, d)
    return d


def _unread(con, marks):
    """{thread id: [times of incoming texts after the baseline]}"""
    try:
        base = dt.datetime.fromisoformat(marks["base"])
    except ValueError:
        base = common.now()
    out = {}
    for tid, ts in con.execute("SELECT thread_id, ts FROM messages WHERE channel='sms' AND direction='in' AND ts > ?", [base]).fetchall():
        out.setdefault(tid, []).append(ts)
    return out


def conversations(q="", before="", limit=50):
    q = " ".join(str(q or "").split())[:200].lower()
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 50
    marks = _marks()
    with _read() as con:
        convs = _threads(con)
        un = _unread(con, marks)
        hit = None
        if q:
            hit = {r[0] for r in con.execute("SELECT DISTINCT thread_id FROM messages WHERE channel='sms' AND lower(coalesce(body,'')) LIKE ?",
                                             [f"%{q}%"]).fetchall()}
    rows = []
    for c in sorted(convs.values(), key=lambda c: c["last"], reverse=True):
        if q and not (q in c["name"].lower() or hit.intersection(c["threads"])):
            continue
        since = dt.datetime.fromisoformat(marks["read"][c["id"]]) if marks["read"].get(c["id"]) else None
        n = sum(1 for t in c["threads"] for ts in un.get(t, []) if since is None or ts > since)
        rows.append({"id": c["id"], "name": c["name"], "group": c["group"], "last": c["body"][:140], "when": _iso(c["last"]),
                     "from_me": c["from_me"], "unread": n, "count": c["count"]})
    if before:
        rows = [r for r in rows if r["when"] < before]
    more = len(rows) > limit
    rows = rows[:limit]
    return {"ok": True, "rows": rows, "more": more, "next": rows[-1]["when"] if rows and more else "",
            "unread": None if q else sum(1 for r in rows if r["unread"]), "drafts": _drafts(), "problem": _problem(), "link": _link()}


def _link():
    try:
        import textlink
        return textlink.public()
    except Exception:  # noqa: BLE001
        return {}


def _problem():
    """The texts link's own word on itself for the Texts part: nothing when it is connected, the paused line while a browser has
    Google Messages (by his choice in Settings)."""
    try:
        import textlink
        if textlink.status().get("state") == "browser_open":
            return textlink.PAUSED_BROWSER + "."
        return " ".join(textlink.problems())
    except Exception:  # noqa: BLE001
        return ""


def _find(con, conv):
    convs = _threads(con)
    return convs.get(conv) or next((c for c in convs.values() if conv in c.get("was", [])), None)


def thread(conv, limit=200, before=""):
    """One conversation: its newest `limit` texts (oldest first within the page) or, with `before` (a time from the previous page's `next`),
    the page before that. `more` says an older page exists; `next` is the time to ask for it with."""
    conv = str(conv or "")
    try:
        limit = max(1, min(int(limit), 500))
    except (TypeError, ValueError):
        limit = 200
    try:
        cut = dt.datetime.fromisoformat(str(before)) if before else None
    except ValueError:
        cut = None
    if not re.fullmatch(r"[pt].{1,200}", conv, re.S):
        return {"ok": False, "error": "That conversation could not be found."}
    with _read() as con:
        c = _find(con, conv)
        if c is None:
            return {"ok": False, "error": "That conversation could not be found."}
        conv = c["id"]                       # an old id of a conversation that was joined to another opens the joined one
        marks = ",".join("?" for _ in c["threads"])
        rows = con.execute(
            f"SELECT m.id, m.ts, m.direction, coalesce(m.body, ''), m.provider_id, m.from_key, m.person_id FROM messages m "
            f"WHERE m.channel='sms' AND m.thread_id IN ({marks})" + (" AND m.ts < ?" if cut else "") + " ORDER BY m.ts DESC, m.id DESC LIMIT ?",
            list(c["threads"]) + ([cut] if cut else []) + [limit + 1]).fetchall()
        ids = [r[0] for r in rows[:limit]]
        names = _names(con)
        files = {}
        for i in range(0, len(ids), 500):            # the texts' pictures and files
            part = ids[i:i + 500]
            for mid, aid, name, saved in con.execute(
                    f"SELECT message_id, id, coalesce(original_filename, ''), coalesce(saved_filename, '') FROM attachments "
                    f"WHERE message_id IN ({','.join('?' for _ in part)}) ORDER BY id", part).fetchall():
                files.setdefault(mid, []).append({"id": aid, "name": name or saved,
                                                  "pic": os.path.splitext((saved or name).lower())[1] in PIC_EXT})
    more = len(rows) > limit
    msgs = [{"id": r[0], "ts": _iso(r[1]), "out": r[2] == "out", "text": r[3], "media": files.get(r[0], []),
             "who": "" if r[2] == "out" or not c["group"] else (names.get(r[6]) or (str(r[5])[4:] if str(r[5]).startswith("sms:") else _pretty(_num(r[5]))) or "")}
            for r in reversed(rows[:limit])]
    if not cut:
        mark_read(conv)
    can = bool(c["gl"] or c["phone"])
    sends = [s for s in _outbox() if s["conv"] == conv and _shown(s, msgs)]
    drafts = [d for d in _drafts() if d["conv"] == conv]
    return {"ok": True, "id": conv, "name": c["name"], "group": c["group"], "messages": msgs, "more": more, "next": msgs[0]["ts"] if more and msgs else "", "can_send": can,
            "cant_send": "" if can else (NO_LINK_GROUP if c["group"] else NO_LINK),
            "sends": sends, "drafts": drafts, "problem": _problem()}


NONAMES = ("", "unknown", "group conversation")
NO_LINK = ("Google Messages on your phone does not list this conversation, and no number is on file for it, so it cannot be answered "
           "from here. Start a new text to their number with New text; it is answered from here once the texts link has read a text in it.")
NO_LINK_GROUP = ("Google Messages on your phone does not list this group, so it cannot be answered from here. Send a text in it from your "
                 "phone once; it is answered from here after the texts link has read it.")


def picture(att):
    """A text's picture or file, for the conversation: (name, saved name, bytes). Only a text's own, from the texts' folder."""
    from connections import _store
    with _read() as con:
        row = con.execute("SELECT a.original_filename, a.saved_filename, a.saved_path FROM attachments a JOIN messages m ON m.id = a.message_id "
                          "WHERE a.id = ? AND m.channel = 'sms'", [int(att)]).fetchone()
    if not row:
        raise LookupError("That picture is not known.")
    name, saved, path = row
    root = os.path.realpath(_store.MEDIA_DIR)
    if not path or not os.path.realpath(path).startswith(root + os.sep) or not os.path.isfile(path):
        raise LookupError("That picture is not on this computer.")
    with open(path, "rb") as f:
        return name or saved or os.path.basename(path), saved or os.path.basename(path), f.read()


def remove_duplicates():
    """A text stored twice (by the old extension and a backup, or two backups) is kept once: the same words (spacing aside), the same direction,
    in the same conversation, in the same minute. A picture's placeholder is left (two pictures in a minute are two texts). The
    copy kept is the one with a picture, then the texts link's, then the first stored. A removed row is deleted outright; one
    that anything points to (a picture, a document, a card) stays. Returns how many were removed."""
    import db
    from connections import _store
    con = db.connect(retries=3)
    try:
        convs = _threads(con)
        where = {t: cid for cid, c in convs.items() for t in c["threads"]}
        rows = con.execute(
            "SELECT m.id, m.provider_id, m.thread_id, m.ts, m.direction, m.body, m.person_id, m.subject, "
            "(SELECT count(*) FROM attachments a WHERE a.message_id = m.id) + (SELECT count(*) FROM documents d WHERE d.message_id = m.id) "
            "FROM messages m WHERE m.channel='sms' AND m.body IS NOT NULL AND m.body <> ? AND m.thread_id IS NOT NULL", [_store.NO_TEXT]).fetchall()
        refs = {r[0] for r in con.execute("SELECT DISTINCT value FROM task_refs").fetchall()}
        same = {}
        for r in rows:
            same.setdefault((where.get(r[2]), r[4], _store.words(r[5]), r[3].replace(second=0, microsecond=0)), []).append(r)
        gone = []
        for group in same.values():
            if len(group) < 2 or group[0][0] is None:
                continue
            keep = max(group, key=lambda r: (r[8] > 0, str(r[1]).startswith("gl:"), -r[0]))
            gone += [r for r in group if r is not keep and not r[8] and str(r[0]) not in refs and str(r[1]) not in refs]
        if not gone:
            return 0
        ids = [r[0] for r in gone]
        con.execute("BEGIN TRANSACTION")
        try:
            for i in range(0, len(ids), 500):
                part = ids[i:i + 500]
                con.execute(f"DELETE FROM messages WHERE id IN ({','.join('?' for _ in part)})", part)
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
    finally:
        con.close()
    try:
        import texts_cache
        if texts_cache.ON:
            texts_cache.refresh()
    except Exception:  # noqa: BLE001  the copy is only for speed
        pass
    return len(ids)


def mark_read(conv):
    with lock:
        d = _marks()
        d["read"][str(conv)[:210]] = _iso(common.now())
        common.write_json(READ, d)
    return {"ok": True}


# --- the outbox -------------------------------------------------------------------------------------------------
def _outbox_all():
    d = common.read_json(OUTBOX, {}) or {}
    return d.get("items") if isinstance(d.get("items"), list) else []


def _outbox():
    """The sends, with a lease run out turned into a failure (never into another try)."""
    with lock:
        items, changed = _outbox_all(), False
        now = common.now()
        for s in items:
            if s.get("status") == "sending":
                try:
                    since = dt.datetime.fromisoformat(s.get("taken") or s["updated"])
                except (KeyError, ValueError):
                    since = now - dt.timedelta(days=1)
                if (now - since).total_seconds() > LEASE_SECONDS:
                    s.update(status="failed", updated=_iso(now),
                             error="Google Messages did not say whether it went. Look " + "on your phone"
                                   + " before you send it again.")
                    changed = True
        for s in items:
            if s.get("status") == "queued":
                try:
                    waited = (now - dt.datetime.fromisoformat(s["created"])).total_seconds()
                except (KeyError, ValueError):
                    waited = QUEUE_SECONDS + 1
                if waited > QUEUE_SECONDS:
                    s.update(status="failed", updated=_iso(now),
                             error="Google Messages on this computer was not connected, so it did not go. Send it again once texts are connected.")
                    changed = True
        # old finished ones are dropped after a day
        keep = [s for s in items if s.get("status") in ("queued", "sending") or
                (now - dt.datetime.fromisoformat(s.get("updated") or _iso(now))).total_seconds() < 86400]
        if changed or len(keep) != len(items):
            common.write_json(OUTBOX, {"items": keep})
        return keep


def _shown(s, msgs):
    """A send shows under its thread while it is waiting or failed; a sent one until its text is read back by the texts link."""
    if s["status"] != "sent":
        return True
    try:
        at = dt.datetime.fromisoformat(s["updated"])
    except ValueError:
        return False
    if (common.now() - at).total_seconds() > SHOW_SENT_MINUTES * 60:
        return False
    want = " ".join(s["text"].split())
    return not any(m["out"] and " ".join(m["text"].split()) == want and
                   dt.datetime.fromisoformat(m["ts"]) >= dt.datetime.fromisoformat(s["created"]) - dt.timedelta(seconds=SAME_SECONDS) for m in msgs)


def _public(s):
    return {k: s.get(k) for k in ("id", "conv", "name", "text", "status", "error", "created", "updated")}


def outbox_for(conv):
    return [_public(s) for s in _outbox() if s["conv"] == conv]


def queue_send(conv, text, to="", name="", learn=True):
    """The owner's own Send press. A conversation already here is answered through its Google Messages conversation, or its number;
    a new text names a number or a person on file. A text I drafted for that conversation, sent from here, is compared with
    what he sent and learned from (writing.py); learn=False for a text sent on his words in Talk to your assistant."""
    text = str(text or "").replace("\r\n", "\n").strip()
    if not text:
        return {"ok": False, "error": "Write the text first."}
    if len(text) > MOST_TEXT:
        return {"ok": False, "error": f"That text is {len(text) - MOST_TEXT} characters too long to send from here."}
    try:
        import textlink
        if not textlink.signed_in():
            return {"ok": False, "error": "Sending texts needs Google Messages signed in on this computer first: " + textlink.SIGN_IN + "."}
    except Exception:  # noqa: BLE001
        pass
    conv, gm, gl, phone, label = str(conv or ""), "", "", "", " ".join(str(name or "").split())[:120]
    if conv:
        with _read() as con:
            c = _find(con, conv)
        if c is None:
            return {"ok": False, "error": "That conversation could not be found."}
        conv = c["id"]
        gm, gl, phone, label = c["gm"], c["gl"], c["phone"], c["name"]
        if not (gl or phone):
            return {"ok": False, "error": NO_LINK_GROUP if c["group"] else NO_LINK}
    else:
        who = " ".join(str(to or "").split())
        digits = re.sub(r"\D", "", who)
        if len(digits) >= 10 and not re.search(r"[A-Za-z]{2}", who):
            phone = digits[-10:]
            with _read() as con:
                for cid, c in _threads(con).items():          # a number already talked to opens that conversation
                    if c["phone"] == phone and c["pid"] is not None:
                        conv, gm, gl, label = cid, c["gm"], c["gl"], c["name"]
                        break
                else:
                    label = label or _pretty(phone)
        elif who:
            with _read() as con:
                found = [c for c in _threads(con).values() if c["pid"] is not None and c["name"].lower() == who.lower() and (c["gl"] or c["gm"] or c["phone"])]
            if len(found) != 1:
                return {"ok": False, "error": (f"More than one person is named {who}. Use the number." if found else
                                               f"No number is on file for {who}. Type the number.")}
            conv, gm, gl, phone, label = found[0]["id"], found[0]["gm"], found[0]["gl"], found[0]["phone"], found[0]["name"]
        else:
            return {"ok": False, "error": "Say who it goes to: a name from your texts, or a phone number."}
    if not (gl or phone):          # the link sends to its own conversation or to a number; nothing else could send this one
        return {"ok": False, "error": NO_LINK}
    with lock:
        items = _outbox()
        if sum(1 for s in items if s["status"] in ("queued", "sending")) >= MOST_QUEUED:
            return {"ok": False, "error": "Too many texts are waiting to go. Wait for them to be sent first."}
        now = _iso(common.now())
        item = {"id": secrets.token_hex(8), "conv": conv, "gm": gm, "gl": gl, "phone": phone, "name": label, "text": text, "status": "queued",
                "created": now, "updated": now, "error": ""}
        items.append(item)
        common.write_json(OUTBOX, {"items": items})
        mine = next((d for d in reversed(_drafts_all()) if (conv and d["conv"] == conv) or
                     (not d["conv"] and d.get("to") and str(d["to"]).lower() in (str(to or "").lower(), label.lower()))), None)
        drafts = [d for d in _drafts_all() if not (d["conv"] == conv and d["text"].strip() == text)]
        if conv:
            drafts = [d for d in drafts if d["conv"] != conv]
        common.write_json(DRAFTS, {"items": drafts})
    if conv:
        mark_read(conv)
    if mine and learn and not mine.get("learned"):
        import writing
        writing.on_sent(mine.get("drafted") or mine["text"], text, "sms", phone or to, label, key=f"text-{mine['id']}")
    try:
        import textlink
        textlink.kick()                 # the texts link sends it now when it is the one that sends
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "id": item["id"], "conv": conv}


def cancel(sid):
    with lock:
        items = _outbox()
        hit = next((s for s in items if s["id"] == str(sid)), None)
        if hit is None or hit["status"] not in ("queued", "failed"):
            return {"ok": False, "error": "It has already gone to Google Messages."}
        common.write_json(OUTBOX, {"items": [s for s in items if s is not hit]})
    return {"ok": True}


def _link_owns(s):
    try:
        import textlink
        return textlink.owns(s)
    except Exception:  # noqa: BLE001
        return False


def next_send(for_link=True):
    """The texts link's sender: hands out the oldest queued text the link can send, once."""
    with lock:
        items = _outbox()
        for s in items:
            if s["status"] == "queued" and _link_owns(s):
                now = _iso(common.now())
                s.update(status="sending", taken=now, updated=now, via="link")
                common.write_json(OUTBOX, {"items": items})
                return {"id": s["id"], "conv": s["gm"], "gl": s.get("gl") or "", "phone": s["phone"], "name": s["name"], "text": s["text"]}
    return None


def report(sid, ok, error=""):
    with lock:
        items = _outbox()
        hit = next((s for s in items if s["id"] == str(sid)), None)
        if hit is None or hit["status"] != "sending":
            return {"ok": False}
        hit.update(status="sent" if ok else "failed", updated=_iso(common.now()),
                   error="" if ok else (" ".join(str(error or "").split())[:200] or "Google Messages did not send it."))
        common.write_json(OUTBOX, {"items": items})
    if ok:
        _log_sent(hit)
    return {"ok": True}


def text_digest(text):
    """A text's words, spaces evened, as a short hash: how a sent text is matched to its copy read back from the phone."""
    return hashlib.sha256(" ".join(str(text or "").split()).encode("utf-8")).hexdigest()[:16]


def _log_sent(s):
    """A text sent from the page goes in the page's own send log (logs, sent.log) beside its emails, so its copy read back from
    the phone is known to have been sent from the page (offpage.py). Its words are kept only as a hash."""
    try:
        os.makedirs(common.LOGS, exist_ok=True)
        with open(os.path.join(common.LOGS, "sent.log"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"at": s.get("updated") or _iso(common.now()), "channel": "sms", "account": "texts",
                                "to": [s.get("phone") or s.get("name") or ""], "conv": s.get("conv") or "", "subject": None,
                                "item": None, "body_chars": len(s.get("text") or ""), "digest": text_digest(s.get("text")),
                                "allowed_by": "your Send press", "result": "sent"}, ensure_ascii=False) + "\n")
    except OSError as e:
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"texts: the send log could not be written: {e}")


# --- the assistant's drafts ---------------------------------------------------------------------------------------
def _drafts_all():
    d = common.read_json(DRAFTS, {}) or {}
    return d.get("items") if isinstance(d.get("items"), list) else []


def _drafts():
    return [dict(d) for d in _drafts_all()]


def draft(conv="", to="", name="", text="", why=""):
    """The chat's text draft: kept for the panel, to edit and send there. Returns a line for the reply, or ''."""
    text = str(text or "").strip()[:MOST_TEXT]
    if not text:
        return "I could not tell what the text should say, so I left it."
    conv, who = str(conv or ""), " ".join(str(to or name or "").split())
    with _read() as con:
        convs = _threads(con)
    if conv not in convs:
        conv = ""
        found = [c for c in convs.values() if who and c["name"].lower() == who.lower()]
        if len(found) == 1:
            conv = found[0]["id"]
        elif len(found) > 1:
            return f"More than one conversation is with {who}, so I left the text draft; tell me which."
    label = convs[conv]["name"] if conv else (who or "")
    try:            # in his voice for texts: to this person, or how he texts at all (voice.py)
        import voice
        text, _how = voice.write_text(text, convs[conv]["phone"] if conv else who, label)
    except Exception as e:  # noqa: BLE001  the draft is never lost over its voice
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"text draft voice: {type(e).__name__}: {e}")
    with lock:
        items =[d for d in _drafts_all() if d["conv"] != conv or not conv]
        items.append({"id": secrets.token_hex(6), "conv": conv, "to": "" if conv else who, "name": label, "text": text,
                      "why": " ".join(str(why or "").split())[:200], "at": _iso(common.now())})
        common.write_json(DRAFTS, {"items": items[-20:]})
    return ""


def learn_sent_outside(sent):
    """Texts he sent from his phone ([(thread id, when, words)]) while a text I drafted for that conversation waited here: what
    I drafted is compared with what he sent and learned from (writing.py), once; the draft stays for him to discard."""
    waiting = [d for d in _drafts_all() if d.get("conv") and not d.get("learned")]
    if not waiting or not sent:
        return 0
    with _read() as con:
        convs = _threads(con)
    n = 0
    for thread, ts, words in sent:
        for d in waiting:
            c = convs.get(d["conv"])
            if d.get("learned") or not c or thread not in (c.get("threads") or ()) or str(d.get("at") or "") > _iso(ts):
                continue
            import writing
            if writing.on_sent(d["text"], words, "sms", c.get("phone") or "", c.get("name") or "", key=f"text-{d['id']}"):
                d["learned"] = True
                n += 1
    if n:
        with lock:
            done = {d["id"] for d in waiting if d.get("learned")}
            common.write_json(DRAFTS, {"items": [dict(d, learned=True) if d["id"] in done else d for d in _drafts_all()]})
    return n


def discard_draft(did):
    with lock:
        common.write_json(DRAFTS, {"items": [d for d in _drafts_all() if d["id"] != str(did)]})
    return {"ok": True}


# --- the chat reads texts -------------------------------------------------------------------------------------------
WORDS = re.compile(r"\b(texts?|texted|texting|sms|messages?|messaged|imessage|rcs)\b", re.I)


def for_chat(words, text=""):
    """Recent texts for the chat to read: the newest conversations with their last few texts, and any conversation named in the words.
    Empty unless the words are about texts or name someone the owner texts."""
    try:
        held = _read(tries=3)
    except Busy:
        return []
    with held as con:
        convs = sorted(_threads(con).values(), key=lambda c: c["last"], reverse=True)
        named = [c for c in convs if len(c["name"]) >= 3 and re.search(r"\b" + re.escape(c["name"].split()[0].lower()) + r"\b", (text or "").lower())]
        picks = (named[:3] + ([c for c in convs if c not in named][:5] if WORDS.search(text or "") else []))[:6]
        out = []
        for c in picks:
            marks = ",".join("?" for _ in c["threads"])
            rows = con.execute(f"SELECT ts, direction, substr(coalesce(body,''), 1, 400) FROM messages WHERE channel='sms' AND thread_id IN ({marks}) "
                               f"ORDER BY ts DESC LIMIT 6", list(c["threads"])).fetchall()
            out.append({"conversation": c["id"], "with": c["name"], "group": c["group"],
                        "latest_first": [{"when": r[0].strftime("%m/%d/%Y %I:%M %p"), "from": "you" if r[1] == "out" else c["name"], "text": " ".join(r[2].split())}
                                         for r in rows]})
        return out
