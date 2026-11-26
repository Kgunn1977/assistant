r"""The live item store: one table of items that persist until done.

The shape is fixed by ITEMS.md. Items are made from the engine's task list in
the Live database and keep their id for life. After every pass the open items
are also written to Live\items.json, which is what the page reads.

    python items.py            # sync from the task list and rewrite items.json
    python items.py --show     # print the open items
"""
import datetime as dt
import glob
import json
import os
import re
import sys

import card
import common
import dates
import db
import duckdb

BASE_COLUMNS = ["id", "source_key", "kind", "area", "title", "detail", "state", "importance",
           "important_reason", "source_who", "source_when", "source_ref", "source_messages",
           "recommended", "asks", "draft", "evidence", "evidence_files", "assistant_did",
           "answer", "answered_at", "due_date", "checkback_date", "created_at", "updated_at",
           "state_changed_at", "done_at", "last_pass"]
# added later: a short status word for the page, a calendar choice
# then the card's own (ITEMS.md, "Design round 1"): why it is here, the shelf it is put off to, the newest press
# and "Design round 2": extra (a rule proposal, what a card that came back waited for, the old cards asked about),
# when the owner was asked about an old card, and when they chose to keep it
EXTRA_COLUMNS = {"status": "VARCHAR", "calendar": "VARCHAR", "why": "VARCHAR", "shelf": "VARCHAR",
                 "later_until": "TIMESTAMP", "last_press": "VARCHAR", "extra": "VARCHAR",
                 "asked_old_at": "TIMESTAMP", "kept_at": "TIMESTAMP",
                 # the header written whole for the card (never a cut title), and when an old card was sent for one
                 "short_header": "VARCHAR", "header_asked": "TIMESTAMP",
                 # the day a card was made or last touched by the day-by-day rebuild (replay.py): standing approvals never act on it
                 "replayed": "VARCHAR",
                 # when the card is from: the earliest message behind it, else when it was made (stamp_from); a typed answer resets it to the answer time
                 "from_at": "TIMESTAMP"}
COLUMNS = BASE_COLUMNS + list(EXTRA_COLUMNS)
JSON_COLUMNS = ("source_messages", "asks", "draft", "evidence_files", "calendar", "last_press", "extra")
JSON_NULL = ("draft", "calendar", "last_press", "extra")  # null when absent; the others are empty lists
STATES = ("new", "yours", "question", "in_motion", "handled", "done")
CLOSED_BY_ASSISTANT = "I closed it, no action taken"     # a card the assistant closed on its own reading, with nothing done by the owner
KINDS = ("question", "approval", "task", "waiting", "fyi", "system")
STATE_ORDER = {"question": 0, "yours": 1, "new": 2, "in_motion": 3, "handled": 4, "done": 5}
DONE_KEPT_DAYS = 7
# cards of two kinds the assistant no longer makes: closed once by close_retired(), never exported
RETIRED_PREFIXES = ("improve:", "built:")

DDL = """
CREATE SEQUENCE IF NOT EXISTS seq_live_item START 1001;
CREATE TABLE IF NOT EXISTS live_items (
  id               VARCHAR PRIMARY KEY,
  source_key       VARCHAR NOT NULL UNIQUE,
  kind             VARCHAR NOT NULL,
  area             VARCHAR,
  title            VARCHAR NOT NULL,
  detail           VARCHAR,
  state            VARCHAR NOT NULL,
  importance       INTEGER NOT NULL DEFAULT 0,
  important_reason VARCHAR,
  source_who       VARCHAR,
  source_when      TIMESTAMP,
  source_ref       VARCHAR,
  source_messages  VARCHAR,
  recommended      VARCHAR,
  asks             VARCHAR,
  draft            VARCHAR,
  evidence         VARCHAR,
  evidence_files   VARCHAR,
  assistant_did    VARCHAR,
  answer           VARCHAR,
  answered_at      TIMESTAMP,
  due_date         DATE,
  checkback_date   DATE,
  created_at       TIMESTAMP NOT NULL,
  updated_at       TIMESTAMP NOT NULL,
  state_changed_at TIMESTAMP NOT NULL,
  done_at          TIMESTAMP,
  last_pass        VARCHAR
);
"""


_made = {"done": False}


def ensure_on(con):
    """The table and every column added since, on an open connection. Once per program run."""
    if _made["done"]:
        return
    con.execute(DDL)
    for name, kind in EXTRA_COLUMNS.items():
        con.execute(f"ALTER TABLE live_items ADD COLUMN IF NOT EXISTS {name} {kind}")
    _made["done"] = True


def ensure():
    if _made["done"]:
        return
    con = db.connect()
    try:
        ensure_on(con)
    finally:
        con.close()


# --- reading the engine's side -------------------------------------------------
def _source(con, task_id):
    """The messages behind a task, newest first, and the one line that names
    the newest: who, when, which message."""
    ids = [r[0] for r in con.execute(
        """SELECT DISTINCT TRY_CAST(value AS BIGINT) AS mid FROM task_refs
           WHERE task_id=? AND kind='source' AND TRY_CAST(value AS BIGINT) IS NOT NULL
           ORDER BY mid DESC""", (task_id,)).fetchall()]
    if not ids:
        return None, None, None, []
    marks = ",".join("?" for _ in ids)
    row = con.execute(
        f"""SELECT m.id, m.channel, m.account, m.ts, m.direction, m.from_key,
                   (SELECT max(c.name) FROM contacts c WHERE c.person_id = m.person_id
                     AND c.name IS NOT NULL)
            FROM messages m WHERE m.id IN ({marks}) ORDER BY m.ts DESC LIMIT 1""", ids).fetchone()
    if not row:
        return None, None, None, []
    mid, channel, account, ts, direction, from_key, name = row
    who = common.owner() if direction == "out" else (name or from_key or "unknown sender")
    where = {"email": f"email {'from' if direction == 'out' else 'to'} {account}",
             }.get(channel) or common.channel_word(channel)
    stamp = f"{ts.month}/{ts.day} {ts.strftime('%I:%M %p').lstrip('0')}"
    return who, ts, f"{who}, {where}, {stamp} ({mid})", [str(i) for i in ids[:25]]


def _engine_view(status, area, asks, draft):
    """(kind, state) the engine's task status asks for."""
    if status in ("done", "dismissed"):
        return None, "done"
    if status == "waiting_them":
        return "waiting", "in_motion"
    if draft:
        return "approval", "question"
    if asks:
        return "question", "question"
    return ("system" if area == "System" else "task"), "yours"


def _did_for_draft(draft):
    if not draft:
        return None
    return f"Drafted a message to {', '.join(draft.get('to') or []) or 'the sender'}; it waits for your approval."


def _add_line(text, line):
    if not line or (text and line in text):
        return text
    return f"{text}\n{line}" if text else line


# --- sync ---------------------------------------------------------------------
JUNK_QUESTION = "Junk or never junk?"


def sync_from_tasks(pass_id, seeding=False):
    """Make an item for every open task, update the ones whose task changed,
    and close the ones whose task closed. Returns (created ids, changed ids,
    closed ids)."""
    import presses
    ensure()
    now = common.now()
    created, changed, closed = [], [], []
    con = db.connect()
    try:
        have = {r[0]: r for r in con.execute(
            "SELECT source_key, id, state, updated_at, state_changed_at, asks, draft, assistant_did,"
            " kind, answered_at FROM live_items").fetchall()}
        tasks = con.execute(
            """SELECT id, item_key, area, title, detail, status, due_date, checkback_date,
                      created_at, updated_at, resolved_reason FROM tasks
               WHERE status IN ('needs_me','waiting_them')
                  OR item_key IN (SELECT substr(source_key, 6) FROM live_items
                                  WHERE source_key LIKE 'task:%' AND state <> 'done')""").fetchall()
        for tid, key, area, title, detail, status, due, check, t_created, t_updated, reason in tasks:
            skey = f"task:{key}"
            old = have.get(skey)
            draft = None
            if old is None:
                if status in ("done", "dismissed"):
                    continue
                who, when, ref, mids = _source(con, tid)
                asks = [JUNK_QUESTION] if presses.is_junk_ask({"source_key": skey}) else []
                kind, state = _engine_view(status, area, asks, draft)
                iid = "L" + str(con.execute("SELECT nextval('seq_live_item')").fetchone()[0])
                con.execute(
                    f"INSERT INTO live_items ({', '.join(BASE_COLUMNS)}) VALUES"
                    f" ({', '.join('?' for _ in BASE_COLUMNS)})",
                    (iid, skey, kind, area, title, detail, state, 0, None, who, when, ref,
                     json.dumps(mids), None, json.dumps(asks), json.dumps(draft) if draft else None,
                     ref, "[]", _did_for_draft(draft), None, None, due, check,
                     t_created if seeding else now, now, now, None, pass_id))
                created.append(iid)
                continue
            iid, o_state, o_updated, o_state_at, o_asks, o_draft, o_did, o_kind, o_answered = old[1:]
            if o_state == "done" and presses.is_junk_ask({"source_key": skey}):
                continue        # answered Junk or Never junk: closed for good, never reopened by a pass
            asks = json.loads(o_asks) if o_asks else []
            kind, e_state = _engine_view(status, area, asks, draft)
            if e_state == "done":
                if o_state != "done" and o_answered:
                    con.execute("UPDATE live_items SET state='done', done_at=?, state_changed_at=?,"
                                " updated_at=?, last_pass=? WHERE id=?", (now, now, now, pass_id, iid))
                    closed.append(iid)
                elif o_state != "done":      # closed by the assistant's own reading, not by him: the card says so, and why
                    stamp = f"{now.month}/{now.day} {now.strftime('%I:%M %p').lstrip('0')}"
                    line = f"{stamp}: {CLOSED_BY_ASSISTANT}" + (f": {str(reason).strip()}" if str(reason or "").strip() else ", and I gave no reason.")
                    con.execute("UPDATE live_items SET state='done', status=?, assistant_did=?, done_at=?, state_changed_at=?,"
                                " updated_at=?, last_pass=? WHERE id=?",
                                (CLOSED_BY_ASSISTANT, "\n".join(x for x in (o_did, line) if x), now, now, now, pass_id, iid))
                    closed.append(iid)
                continue
            new_draft = json.dumps(draft) if draft else None
            if not draft and o_draft and not json.loads(o_draft).get("outbox_id"):
                new_draft = o_draft        # written from the owner's own answer on the page: it stays
            task_moved = t_updated > o_updated
            draft_moved = (draft or {}).get("outbox_id") != (json.loads(o_draft) if o_draft else {}).get("outbox_id")
            if not task_moved and not draft_moved:
                continue
            who, when, ref, mids = _source(con, tid)
            # title and detail stay as written for the owner; the think pass rewrites
            # them when new material arrives
            # the engine moves the state only when the task itself moved after
            # the state was last set, so an answer from the page is not undone
            state = e_state if (t_updated > o_state_at or draft_moved) else o_state
            did = _add_line(o_did, _did_for_draft(draft)) if draft_moved else o_did
            con.execute(
                """UPDATE live_items SET kind=?, area=?, state=?, source_who=?,
                   source_when=?, source_ref=?, source_messages=?, draft=?, assistant_did=?,
                   due_date=?, checkback_date=?, updated_at=?, state_changed_at=?, last_pass=?
                   WHERE id=?""",
                (kind if state == e_state else o_kind, area, state, who, when, ref,
                 json.dumps(mids), new_draft, did, due, check, now,
                 now if state != o_state else o_state_at, pass_id, iid))
            changed.append(iid)
    finally:
        con.close()
    return created, changed, closed


def enrich_from_briefing(pass_id):
    """Day one only: carry over what the last composed briefing already said
    about each open item (the asks, the proposal, the evidence files)."""
    files = [os.path.join(common.paths.STATE, "briefing_composed.json")]
    composed = common.read_json(files[0])
    if not composed:
        return 0
    n = 0
    con = db.connect()
    try:
        for section in composed.get("sections", []):
            for it in section.get("items", []):
                key = it.get("item_key")
                row = con.execute("SELECT id, draft, source_ref, kind, state FROM live_items WHERE source_key=?",
                                  (f"task:{key}",)).fetchone()
                if not row:
                    continue
                iid, draft, ref, kind, state = row
                text = it.get("text") or ""
                m = re.search(r"Proposed: (.+?\.)(?:\s|$)", text)
                asks = it.get("asks") or []
                files_ = []
                for ev in it.get("evidence") or []:
                    p = _find_file(ev.get("path"))
                    if p:
                        files_.append({"label": ev.get("label") or os.path.basename(p), "path": p})
                if not draft and it.get("draft"):
                    draft = json.dumps(it["draft"])
                group = it.get("group")
                if state != "in_motion":
                    if draft or group == "Approvals":
                        kind, state = "approval", "question"
                    elif asks or group == "Questions":
                        kind, state = "question", "question"
                evidence = "; ".join(f["label"] for f in files_) or ref
                con.execute(
                    """UPDATE live_items SET detail=?, recommended=?, asks=?, draft=?, evidence=?,
                       evidence_files=?, kind=?, state=?, last_pass=? WHERE id=?""",
                    (text, m.group(1) if m else None, json.dumps(asks), draft, evidence,
                     json.dumps(files_), kind, state, pass_id, iid))
                n += 1
    finally:
        con.close()
    return n


def _find_file(path):
    """A briefing's evidence path as a full path that exists, or None."""
    if not path:
        return None
    for base in ("", common.paths.ATTACHMENTS):
        p = path if os.path.isabs(path) else os.path.join(base, path)
        if os.path.isabs(p) and os.path.exists(p):
            return p
    return None


# --- answers from the page -------------------------------------------------------
def apply_answers(pass_id):
    """Apply each answer file waiting in Live\\answers (the listener's own
    answers have usually landed already; the same answer never lands twice)."""
    import answers
    applied, problems, _changed = answers.apply_files(pass_id)
    settled, bad = answers.settle_junk_answers()      # a Junk or Never junk answer recorded but never acted on
    return applied + settled, problems + bad


# --- writing for the page -------------------------------------------------------
def rows(where="1=1", params=()):
    ensure()
    got = db.query(f"SELECT {', '.join(COLUMNS)} FROM live_items WHERE {where}", params)
    out = []
    for r in got:
        d = dict(zip(COLUMNS, r))
        for c in JSON_COLUMNS:
            d[c] = json.loads(d[c]) if d[c] else (None if c in JSON_NULL else [])
        out.append(d)
    out.sort(key=lambda d: (-(d["importance"] or 0), STATE_ORDER.get(d["state"], 9),
                            -(d["source_when"].timestamp() if d["source_when"] else 0)))
    return out


DOC_TEXT_MAX = 20000          # the words of all of one card's papers together, in characters
DOC_CUT = "\n[cut here; the rest is in the original file]"
DOC_NO_ROOM = "[This paper is too long to fit on the card; it is in the original file.]"
# pictures mail programs tuck into a signature; never a paper anyone attached
INLINE_IMAGE = re.compile(r"^(image\d+|outlook-[\w.-]+)\.(png|jpe?g|gif|bmp)$", re.I)


def documents_for(con, message_ids):
    """The papers attached to the messages behind an item, newest message first:
    [{"file", "read": True, "pages", "text", "cut"}] for a paper the assistant has
    read, [{"file", "read": False}] for one it has not read yet. The same paper sent
    twice shows once; all the words together stay within DOC_TEXT_MAX."""
    ids = []
    for m in message_ids or []:
        try:
            ids.append(int(m))
        except (TypeError, ValueError):
            pass
    ids = ids[:25]
    if not ids:
        return []
    marks = ",".join("?" for _ in ids)
    order = {m: n for n, m in enumerate(ids)}
    files = {}
    for aid, mid, name, state in con.execute(
            f"SELECT id, message_id, original_filename, state FROM attachments"
            f" WHERE message_id IN ({marks})", ids).fetchall():
        files[("a", aid)] = {"file": os.path.basename(str(name or "")) or "attached file", "msg": mid,
                             "pos": aid, "pages": {}, "dropped": state == "discarded", "ref": f"att:{aid}"}
    for did, aid, mid, name, no, text in con.execute(
            f"""SELECT d.id, d.attachment_id, coalesce(d.message_id, a.message_id), a.original_filename,
                       p.page_no, p.text
                FROM documents d JOIN pages p ON p.document_id = d.id
                LEFT JOIN attachments a ON a.id = d.attachment_id
                WHERE coalesce(d.message_id, a.message_id) IN ({marks}) AND coalesce(p.text, '') <> ''
                ORDER BY d.id, p.page_no""", ids).fetchall():
        key = ("a", aid) if aid is not None else ("d", did)
        f = files.setdefault(key, {"file": os.path.basename(str(name or "")) or "attached paper", "msg": mid,
                                   "pos": aid if aid is not None else did, "pages": {}, "dropped": False,
                                   "ref": f"att:{aid}" if aid is not None else None})
        f["pages"].setdefault(no, str(text).replace("\r", "").strip())
    out, seen, names, room = [], set(), set(), DOC_TEXT_MAX
    for f in sorted(files.values(), key=lambda f: (order.get(f["msg"], len(order)), f["pos"] or 0)):
        if f["pages"]:
            nos = sorted(f["pages"])
            text = "\n\n".join((f"[page {n}]\n" if len(nos) > 1 else "") + f["pages"][n] for n in nos)
            if (f["file"].lower(), text) in seen:
                continue
            seen.add((f["file"].lower(), text))
            names.add(f["file"].lower())
            doc = {"file": f["file"], "read": True, "pages": len(nos), "text": text, "cut": False, "ref": f.get("ref"),
                   "kind": file_kind(f["file"]), "msg": f["msg"]}
            if room <= 0:
                doc.update(text=DOC_NO_ROOM, cut=True)
            elif len(text) > room:
                doc.update(text=text[:room] + DOC_CUT, cut=True)
            room -= len(text)
            out.append(doc)
    for f in sorted(files.values(), key=lambda f: (order.get(f["msg"], len(order)), f["pos"] or 0)):
        if f["pages"] or f["dropped"] or INLINE_IMAGE.match(f["file"]) or f["file"].lower() in names:
            continue
        names.add(f["file"].lower())
        out.append({"file": f["file"], "read": False, "ref": f.get("ref"), "kind": file_kind(f["file"]), "msg": f["msg"]})
    return out


def _from_at(con, message_ids, created):
    """When a card is from: the arrival of the earliest message behind it, else when the card was made."""
    ids = []
    for m in message_ids or []:
        try:
            ids.append(int(m))
        except (TypeError, ValueError):
            pass
    if ids:
        got = con.execute(f"SELECT min(ts) FROM messages WHERE id IN ({','.join('?' for _ in ids)})", ids).fetchone()
        if got and got[0]:
            return got[0]
    return created


def stamp_from():
    """Store from_at on every card that has none yet, once: a card keeps the time it is from even when later messages
    join it. Run at export, after a rebuild has dated its cards by their real past (replay._as_of_day), so a card with
    no message takes its made time, never the run's clock. A busy database leaves it to the next export; read() fills
    the gap meanwhile."""
    try:
        con = db.connect()
    except TimeoutError:
        return
    try:
        ensure_on(con)
        for iid, mids, created in con.execute(
                "SELECT id, source_messages, created_at FROM live_items WHERE from_at IS NULL").fetchall():
            try:
                mids = json.loads(mids) if mids else []
            except ValueError:
                mids = []
            con.execute("UPDATE live_items SET from_at=? WHERE id=?", (_from_at(con, mids, created), iid))
    except duckdb.Error:
        pass
    finally:
        con.close()


def file_kind(name):
    """How a paper opens on the page: pdf, image, or file (anything else is offered to save)."""
    low = str(name or "").lower()
    if low.endswith(".pdf"):
        return "pdf"
    if low.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
        return "image"
    return "file"


def messages_for(con, message_ids, most=10):
    """The messages behind a card, oldest first, as the page links them: [{id, when, who, subject, channel}]."""
    ids = []
    for m in message_ids or []:
        try:
            ids.append(int(m))
        except (TypeError, ValueError):
            pass
    if not ids:
        return []
    marks = ",".join("?" for _ in ids[:most])
    rows = con.execute(f"""SELECT m.id, m.ts, coalesce(c.name, nullif(s.from_name, ''), m.from_key), m.subject, m.channel, m.direction
                           FROM messages m LEFT JOIN contacts c ON c.key = m.from_key LEFT JOIN mail_state s ON s.message_id = m.id
                           WHERE m.id IN ({marks}) ORDER BY m.ts""", ids[:most]).fetchall()
    out = []
    for mid, ts, who, subject, channel, direction in rows:
        who = str(who or "").split(":", 1)[-1].strip()
        out.append({"id": mid, "when": ts.isoformat(timespec="minutes") if ts else None, "who": "You" if direction == "out" else who,
                    "subject": " ".join(str(subject or "").split()), "channel": channel})
    return out


def junk_judged(con, it, most=10):
    """The emails a one-sender Junk or never junk card is about: the ones from that sender the judge called junk, newest
    first (spec 3.9: the card shows every message judged junk, not one sample). [] for any other card."""
    import presses
    rid = presses.junk_ask_rule(it) if presses.is_junk_ask(it) else None
    if rid is None:
        return []
    e = next((x for x in presses._rules().parse("senders") if x["id"] == rid and x.get("pattern")), None)
    if not e:
        return []
    rows = con.execute("""SELECT m.id FROM messages m JOIN answered a ON a.domain = 'judged' AND a.key = 'msg:' || m.id
                          WHERE m.direction = 'in' AND m.channel = 'email' AND a.verdict = 'noise'
                          AND m.from_key ILIKE ? ESCAPE '\\' ORDER BY m.ts DESC LIMIT ?""", [e["pattern"], most]).fetchall()
    return [r[0] for r in rows]


def last_at(con, message_ids):
    """When the newest message behind a card came, to the minute, or None. The newest is picked here, not in the
    query: a max() over such a list once failed inside the database engine (comeback.py)."""
    ids = [int(m) for m in (message_ids or []) if str(m).isdigit()]
    if not ids:
        return None
    got = [r[0] for r in con.execute(f"SELECT ts FROM messages WHERE id IN ({','.join('?' for _ in ids)})", ids).fetchall() if r[0]]
    return max(got).isoformat(timespec="minutes") if got else None


EMAIL_ADDRESS = re.compile(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+")


def reply_for(con, message_ids):
    """Who a reply by email goes to, for an item whose newest message is an email:
    {"account": the account it came to or went from, "to": [addresses], "subject": "Re: ..."}.
    The sender when it came in; the people it went to when the owner sent it.
    None when the newest message is not an email or has nobody to reply to."""
    if not message_ids:
        return None
    row = con.execute("SELECT m.channel, m.account, m.direction, m.from_key, m.to_keys, m.subject, m.thread_id, coalesce(s.provider_id, m.provider_id), m.person_id, m.body"
                      " FROM messages m LEFT JOIN mail_state s ON s.message_id = m.id WHERE m.id=?",
                      (int(message_ids[0]),)).fetchone()
    if not row:
        return None
    if row[0] != "email":
        return _no_reply_here(row[0])
    _channel, account, direction, from_key, to_keys, subject, thread, provider_id, _person, body = row
    account = str(account or "").strip()
    if account.lower() not in {str(a).strip().lower() for a in common.personal().get("send_accounts") or []}:
        return {"can_email": False, "via": "email",
                "why": f"This came to {account or 'an account'}, which I can't send from, so a reply can't go out from here."}
    found = EMAIL_ADDRESS.findall(str(to_keys or "") if direction == "out" else str(from_key or ""))
    to = []
    for a in found:
        a = a.lower()
        if a != account.lower() and a not in to:
            to.append(a)
    if not to:
        return None
    if direction == "in":
        why = not_answerable(con, to[0], body)
        if why:
            return {"can_email": False, "why": why}
    subject = str(subject or "").strip()
    if subject and not re.match(r"re\s*:", subject, re.I):
        subject = "Re: " + subject
    return {"account": account, "to": to[:10], "subject": subject, "thread": str(thread or "") or None,
            "in_reply_to": str(provider_id or "") or None, "via": "email", "can_email": True}


AUTOMATIC = re.compile(r"^(?:[a-z0-9._-]*[._-])?(no-?reply|do-?not-?reply|noreply|notifications?|notify|alerts?|mailer-daemon|"
                       r"postmaster|bounces?|communications|updates|newsletters?|news|marketing|automated|automail)(?:[._+-][a-z0-9._-]*)?@", re.I)
UNSUBSCRIBE = re.compile(r"unsubscribe|opt[ -]?out|manage (your )?(email )?preferences", re.I)
_lists = {"at": 0.0, "ignore": [], "junk": []}


def _owner_lists():
    """The owner's ignore list and Always junk list, read at most every few seconds (one export asks for each card)."""
    import time
    if time.time() - _lists["at"] > 5:
        ignore = [str(e).strip().lower() for e in common.personal().get("ignore_senders") or [] if str(e).strip()]
        junk = []
        try:
            import sys
            if common.paths.CORE not in sys.path:
                sys.path.insert(0, common.paths.CORE)
            import rules
            junk = [e["pattern"] for e in rules.junk([rules.ALWAYS]) if e.get("pattern")]
        except Exception:  # noqa: BLE001  no junk list yet
            junk = []
        _lists.update(at=time.time(), ignore=ignore, junk=junk)
    return _lists


def not_answerable(con, address, body=""):
    """Why a message from this address is not one a person wrote that can be answered, or "" when it is. Never answerable:
    a sender on the owner's ignore or Always junk list. Not answerable unless he has written to them himself: an automatic
    sender (a no-reply or notification style address) or a mailing (a message with an unsubscribe line)."""
    a = str(address or "").strip().lower()
    lists = _owner_lists()
    dom = a.split("@")[-1]
    if any(a == e or dom == e.lstrip("@") or dom.endswith("." + e.lstrip("@")) for e in lists["ignore"]):
        return "This sender is on your list of senders to ignore."
    try:
        import sys
        if common.paths.CORE not in sys.path:
            sys.path.insert(0, common.paths.CORE)
        import rules
        if any(rules.matches("email:" + a, pat) for pat in lists["junk"]):
            return "This sender is on your junk list."
    except Exception:  # noqa: BLE001
        pass
    written = con.execute("SELECT count(*) FROM messages WHERE direction = 'out' AND channel = 'email' AND lower(to_keys) LIKE ?",
                          (f"%{a}%",)).fetchone()[0]
    if written:
        return ""
    if AUTOMATIC.match(a):
        return "This came from an automatic sender; a reply would reach nobody."
    if UNSUBSCRIBE.search(str(body or "")[-3000:]):
        return "This is a mailing; a reply would reach nobody who reads it."
    return ""


def _no_reply_here(channel):
    """A card whose newest message is not an email (a text, a chat message): a reply goes back the way it came, from the account
    or channel it came in on, and the assistant sends only email, so there is no Reply on it."""
    how = {"sms": "a text"}.get(channel) or (common.channel_word(channel) if channel else "another way")
    return {"can_email": False, "via": "text" if channel == "sms" else channel,
            "why": f"This came by {how}. A reply goes back the way it came, and I can only send email."}


def sender_for(con, message_ids):
    """The outside sender of the newest message that came in, for the Junk and Never junk buttons:
    {"key": the sender as the junk lists name it, "address": the address or number to show,
    "can_junk": False for one of the owner's own domains}. None when nothing came in from outside."""
    ids = [int(m) for m in (message_ids or [])[:25] if str(m).isdigit()]
    if not ids:
        return None
    row = con.execute(f"SELECT channel, from_key FROM messages WHERE id IN ({','.join('?' for _ in ids)})"
                      " AND direction = 'in' AND channel IN ('email', 'sms') AND from_key IS NOT NULL"
                      " ORDER BY ts DESC LIMIT 1", ids).fetchone()
    if not row or not str(row[1] or "").strip() or row[1] == "assistant":
        return None
    key = str(row[1]).strip().lower()
    address = key.split(":", 1)[-1]
    own = any(address.endswith("@" + d) or address.endswith("." + d) for d in common.paths.own_domains())
    return {"key": key, "address": address, "can_junk": not own}


def mailing_for(con, message_ids):
    """True when the newest email that came in behind a card is a mailing by rule 559's own test (an unsubscribe link or
    address in its body), whatever kept it on the page: the card then offers Hide mailings like this (card.switches)."""
    ids = [int(m) for m in (message_ids or [])[:25] if str(m).isdigit()]
    if not ids:
        return False
    if common.paths.CORE not in sys.path:
        sys.path.insert(0, common.paths.CORE)
    import judgment_payload as jp
    row = con.execute(f"SELECT substr(body, 1, {jp.RAW_BODY_LIMIT}) FROM messages WHERE id IN ({','.join('?' for _ in ids)})"
                      " AND direction = 'in' AND channel = 'email' ORDER BY ts DESC LIMIT 1", ids).fetchone()
    body = str((row or [""])[0] or "")
    return bool(jp.MAILTO.search(body) or jp.UNSUB_LINK.search(body))


def _extras(con, it):
    """Optional keys the page asked for; each is present only when known."""
    extra = {}
    if it["source_messages"] and it.get("state") != "done":
        try:
            extra["reply"] = reply_for(con, it["source_messages"])
        except (duckdb.Error, ValueError, TypeError):   # a reply address never costs the card the rest
            pass
    if it["source_messages"] and it.get("state") != "done":
        try:
            docs = documents_for(con, it["source_messages"])
        except duckdb.Error:      # papers never cost the card its message text
            docs = []
        if docs:
            extra["documents"] = docs
    if not it["source_messages"] and it.get("state") != "done":
        try:        # a junk question card: every email judged junk from its sender, each one he can open and read
            judged = junk_judged(con, it)
            if judged:
                extra["messages"] = messages_for(con, judged)
        except Exception:  # noqa: BLE001  the emails never cost the card the rest
            pass
    if it["source_messages"]:
        try:        # each message behind the card, so its Context can open it over the page
            extra["messages"] = messages_for(con, it["source_messages"])
        except (duckdb.Error, ValueError, TypeError):
            pass
        try:        # the latest message on the card, of all of them: what Recently active goes by (order.py)
            last = last_at(con, it["source_messages"])
            if last:
                extra["last_at"] = last
        except (duckdb.Error, ValueError, TypeError):
            pass
    if it["source_messages"] and it.get("state") != "done":
        try:        # how often the owner is in touch with whoever wrote it in (contact_strength.py): a higher place on the page
            import contact_strength
            newest = con.execute(f"SELECT id FROM messages WHERE id IN ({','.join('?' for _ in it['source_messages'][:25])}) "
                                 "AND direction = 'in' ORDER BY ts DESC LIMIT 1", [int(m) for m in it["source_messages"][:25]]).fetchone()
            got = contact_strength.for_message(con, newest[0]) if newest else None
            if got and got["level"]:
                extra["contact"] = got
        except (duckdb.Error, ValueError, TypeError):
            pass
    if it["source_messages"] and it.get("state") != "done":
        try:        # a card from a mailing: it may offer Hide mailings like this (card.switches)
            if mailing_for(con, it["source_messages"]):
                extra["mailing"] = True
        except (duckdb.Error, ValueError, TypeError):
            pass
    made_up = it.get("extra") if isinstance(it.get("extra"), dict) else {}
    if str(it.get("source_key") or "").startswith("test:") and isinstance(made_up.get("sender"), dict):
        extra["sender"] = made_up["sender"]         # a test card's made-up sender (test_cards.py): its presses touch no list
    if it["source_messages"]:
        try:        # who it came from, so Junk and Never junk know whom they are about
            who = sender_for(con, it["source_messages"])
            if who:
                extra["sender"] = who
        except (duckdb.Error, ValueError, TypeError):
            pass
    if it["source_messages"]:
        try:        # the judge said no rule decides a message behind it: its best guess, for the why line (card.fill)
            keys = ["msg:" + str(m) for m in it["source_messages"][:25]]
            row = con.execute(f"SELECT source FROM answered WHERE domain = 'judged' AND covered = false AND key IN "
                              f"({','.join('?' for _ in keys)}) ORDER BY answered_at DESC, key DESC LIMIT 1", keys).fetchone()
            if row:
                extra["uncovered"] = " ".join(str(row[0] or "").split())
        except (duckdb.Error, ValueError, TypeError):      # a home whose database has no covered column yet: no line
            pass
    if it["source_messages"]:
        try:        # which conversation it belongs to, for grouping
            t = con.execute("SELECT thread_id, subject FROM messages WHERE id=?", (int(it["source_messages"][0]),)).fetchone()
            if t and t[0]:
                extra["thread"] = {"key": str(t[0]), "label": " ".join(str(t[1] or "").split())}
        except (duckdb.Error, ValueError, TypeError):
            pass
    if it["source_messages"]:
        row = con.execute("SELECT subject, body FROM messages WHERE id=?",
                          (int(it["source_messages"][0]),)).fetchone()
        if row and row[1]:
            if common.paths.MODULE_A not in sys.path:
                sys.path.insert(0, common.paths.MODULE_A)
            import cleantext
            extra["source_text"] = cleantext.new_text(row[1], limit=6000, subject=row[0] or "")
    return {k: v for k, v in extra.items() if v not in (None, "")}


def write_today():
    """Live\\today.json: today's and tomorrow's events from the calendars the
    owner listed for it (personal "today_calendars"; none listed shows none).
    Other calendars stay in the table for the rest of the system."""
    today = dt.date.today()
    cals = [str(c).strip() for c in (common.personal().get("today_calendars") or []) if str(c).strip()]
    got = db.query(
        f"""SELECT start_ts, end_ts, all_day, summary, location FROM calendar_events
            WHERE CAST(start_ts AS DATE) BETWEEN ? AND ? AND trim(calendar) IN ({', '.join('?' for _ in cals)})
            ORDER BY start_ts""",
        (today, today + dt.timedelta(days=1), *cals)) if cals else []
    days = []
    for d in (today, today + dt.timedelta(days=1)):
        events = [{"start": None if a else s.strftime("%H:%M"),
                   "end": None if a or not e else e.strftime("%H:%M"),
                   "all_day": bool(a), "title": t, "location": loc}
                  for s, e, a, t, loc in got if s.date() == d]
        days.append({"date": d.isoformat(), "events": events})
    try:        # every calendar the engine holds events for, so the page's Settings can offer them
        known = sorted({str(r[0]).strip() for r in db.query("SELECT DISTINCT trim(calendar) FROM calendar_events")
                        if r[0] and str(r[0]).strip()})
    except Exception:  # noqa: BLE001
        known = []
    common.write_json(os.path.join(common.HOME, "today.json"), {"written_at": common.now(), "days": days, "calendars": known})


CHOICE_MAX = 60
RECOMMENDED_MARK = " (recommended)"          # on the button whose answer is the card's recommendation
OLD_GENERIC_YES = "Yes, as recommended"      # a button cards no longer get: it named no action; dropped wherever it is still kept


def join(src, dst, pass_id):
    """Two open cards that are one matter become one: dst takes src's messages and its history (his answers and
    presses on it among them), src closes as joined into dst, and dst is owed a full writing from all of them.
    Returns True when joined; nothing changes when either is not an open card or they are the same."""
    got = {r["id"]: r for r in rows("id IN (?, ?) AND state <> 'done'", (src, dst))}
    if src == dst or src not in got or dst not in got:
        return False
    import rsi_loop
    if any(rsi_loop.is_card(got[i]) for i in (src, dst)):
        return False        # a rule change card is one proposal: only its own Promote, Apply or Reject closes it
    import wouldhide
    if any(wouldhide.is_card(got[i]) for i in (src, dst)):
        return False        # an "I'd hide this" card is about its one message: only its own buttons close it
    if any(isinstance(got[i].get("extra"), dict) and got[i]["extra"].get("ready") for i in (src, dst)):
        return False        # a draft in Ready to send is one email, not the matter: discarding it must not close the matter
    a, b = got[src], got[dst]
    now = common.now()
    day = f"{now.month}/{now.day}"
    mids = list(b["source_messages"]) + [m for m in a["source_messages"] if m not in b["source_messages"]]
    note = f"{day}: I merged \"{a['title']}\" into this card. Both were about the same thing."     # a card is named by its title, never its number
    theirs = "\n".join(x if x.startswith("Answered by you:") else f"From \"{a['title']}\": {x}"     # his settled questions stay readable as such
                       for x in str(a.get("assistant_did") or "").split("\n") if x.strip())
    did = "\n".join(x for x in (b.get("assistant_did"), note, theirs) if x)
    keep = {"source_messages": json.dumps(mids), "assistant_did": did}
    if a.get("draft") and not b.get("draft"):
        keep["draft"] = json.dumps(a["draft"]) if not isinstance(a["draft"], str) else a["draft"]
    update(dst, pass_id, **keep)
    db.execute("UPDATE live_items SET state='done', status=?, answered_at=?, asks='[]', assistant_did=?, done_at=?,"
               " updated_at=?, state_changed_at=?, last_pass=? WHERE id=?",
               (f"Joined into {dst}", now, "\n".join(x for x in (a.get("assistant_did"), f"{day}: I merged this card into \"{b['title']}\", which stays open. Both were about the same thing.") if x),
                now, now, now, pass_id, src))
    owe_writing([dst])
    return True


def owe_writing(ids):
    """Cards the card writer owes a full writing at the next pass, new message or not (think.write_items): a stand-in
    made at once, a card that took another in, a rebuild. Kept in the think state as rewrite_items."""
    st = common.read_json(common.THINK_STATE, {}) or {}
    st["rewrite_items"] = sorted(set(st.get("rewrite_items") or []) | {str(i) for i in ids})
    common.write_json(common.THINK_STATE, st)


def card_extras(entry, extra=None, answered=False):
    """What a written card keeps beside its columns, from the writer's entry, as column updates ({} when nothing changes):
    - waiting (state in_motion): who owes the next move (`waiting_on`, kept in extra) and the day to look again
      (`next_check`, kept as checkback_date; a day already past is not taken);
    - choices (state question or yours): the writer's short answers to the first question, as buttons; the one the
      writer names as its recommendation (`recommended_choice`) comes first, marked "(recommended)". No generic yes is
      added: a card whose recommendation is no choice shows the recommendation on its front instead. Replaced each
      time the card is written, gone once nothing is asked. A choice is its words, or {"text", "meaning"}: the meaning (what
      pressing it says about the card's call, one of presses.MEANINGS) is kept on the button when it is on that list and
      not "other"; any other meaning is dropped, and the page then records the press as other;
    - the card's old come-back note is dropped when his answer settles it, or when the card is written afresh
      (answered: both, since either way the card now says what it waits on);
    - pick: what the writer predicts he will do (picks.from_writer), replaced only when the entry carries one."""
    try:
        ex = extra if isinstance(extra, dict) else (json.loads(extra) if extra else {})
    except ValueError:
        ex = {}
    ex = dict(ex) if isinstance(ex, dict) else {}
    before = json.dumps(ex, sort_keys=True)
    out = {}
    if answered:
        ex.pop("came_back", None)
    if entry.get("state") == "in_motion":
        on = " ".join(str(entry.get("waiting_on") or "").split())
        if on:
            ex["waiting_on"] = on
        try:
            day = dt.date.fromisoformat(str(entry.get("next_check") or "")[:10])
        except ValueError:
            day = None
        if day and day >= dt.date.today():
            out["checkback_date"] = day
    else:
        ex.pop("waiting_on", None)
    ex.pop("choices", None)
    if entry.get("state") in ("question", "yours") and entry.get("asks"):
        got = []
        pick = _written_choice(entry.get("recommended_choice"))[0].lower()
        for c in entry.get("choices") or []:
            c, m = _written_choice(c)
            if c and len(c) <= CHOICE_MAX and c.lower() != OLD_GENERIC_YES.lower() and c.lower() not in {g["text"].lower() for g in got}:
                got.append(dict({"label": c, "text": c}, **m))
        best = next((g for g in got if pick and g["text"].lower() == pick), None)
        if best:                # the recommended answer first, saying so
            got.remove(best)
            got.insert(0, dict(best, label=best["text"] + RECOMMENDED_MARK, recommended=True))
        if len(got) >= 2:
            ex["choices"] = got[:5]
    ex.pop("questions", None)
    if entry.get("state") in ("question", "yours") and isinstance(entry.get("ask_choices"), list):
        qs = []         # each further question's own short answers, its recommended one first
        for a, q in zip(list(entry.get("asks") or [])[1:], entry["ask_choices"][1:]):
            if not isinstance(q, dict):
                continue
            pick = _written_choice(q.get("recommended_choice"))[0].lower()
            got = []
            for c in q.get("choices") or []:
                c, m = _written_choice(c)
                if c and len(c) <= CHOICE_MAX and c.lower() not in {g["text"].lower() for g in got}:
                    got.append(dict({"label": c, "text": c}, **m))
            best = next((g for g in got if pick and g["text"].lower() == pick), None)
            if best:
                got.remove(best)
                got.insert(0, dict(best, recommended=True))
            if got:
                qs.append({"ask": " ".join(str(a).split()), "choices": got[:5]})
        if qs:
            ex["questions"] = qs
    if "pick" in entry:         # what the writer predicts he will do (picks.py); a pick it cannot use leaves the program's
        import picks
        ex.pop("pick", None)
        p = picks.from_writer(entry.get("pick"), ex.get("choices") or [])
        if p:
            ex["pick"] = dict(p, at=common.now().isoformat(timespec="seconds"))
    if json.dumps(ex, sort_keys=True) != before:
        out["extra"] = json.dumps(ex)
    return out


def _written_choice(c):
    """(its words, {"meaning": m} or {}) for one choice as Claude wrote it: a bare string, or {"text", "meaning"}. A meaning
    is kept only when it is on the fixed list (presses.MEANINGS) and says something (not other or neutral); anything else
    is dropped, so the press records other."""
    m = None
    if isinstance(c, dict):
        c, m = c.get("text") or c.get("label"), c.get("meaning")
    import presses
    keep = isinstance(m, str) and m in presses.MEANINGS and m not in ("other", "neutral")
    return " ".join(str(c or "").split()), ({"meaning": m} if keep else {})


def own_meanings(choices):
    """An add-on's own choices with any meaning not on the fixed list dropped, so a press on one is recorded as other and
    never refused as a press with an unknown meaning. Bare strings are left as they are."""
    import presses
    out = []
    for c in choices or []:
        if isinstance(c, dict) and "meaning" in c and c.get("meaning") not in presses.MEANINGS:
            c = {k: v for k, v in c.items() if k != "meaning"}
        out.append(c)
    return out


def lift(it):
    """The page draws its answer buttons from top-level keys."""
    import presses
    if presses.is_junk_ask(it):
        it["choices"] = ["Junk", "Never junk"]
        if presses.junk_ask_rule(it) is not None and it.get("state") != "done":
            it["sample"] = True             # one sender: the card can show that sender's recent emails (mail.sample)
    elif (it.get("source_key") or "").startswith("live:newsender-") and it.get("state") != "done":
        it["choices"] = ["Show their mail", "Hold it"]
    elif (it.get("source_key") or "").startswith("live:projwrite-") and it.get("state") != "done":
        it["choices"] = [{"label": "Yes, write it", "text": "Yes, write it", "recommended": True}]     # the no is the card's own No press
    elif (it.get("source_key") or "").startswith("live:standing-") and it.get("state") != "done":
        it["choices"] = ["Yes, do it and notify me", "Yes, do it quietly"]      # the no is the card's own No press
    elif it.get("source_key") == "live:test-seen":
        it["choices"] = ["Yes", "No"]
    elif (it.get("source_key") or "").startswith("live:setup-"):     # a setup card: its buttons follow where setup stands (onboard.py)
        import onboard
        it["choices"] = onboard.choices(it)
    return it


def _mod_choices(it):
    """A mod's own card: its own buttons (mods.py). The mod's code runs here, so this is only ever called with no
    database connection open (finish, export): a mod is someone else's code and may take its time."""
    if it.get("state") != "done":
        import mods
        got = mods.choices(it)
        if got:
            it["choices"] = own_meanings(got) if isinstance(got, list) else got
    return it


def read(con, it):
    """The part of preparing a card that needs the database: the optional keys the page asked for. Returns it.
    Then close the connection and finish(it)."""
    if con is not None and it is not None:
        if not it.get("from_at"):
            try:
                it["from_at"] = _from_at(con, it.get("source_messages"), it.get("created_at"))
            except (duckdb.Error, ValueError, TypeError):
                it["from_at"] = it.get("created_at")
        try:
            for k, v in _extras(con, it).items():
                if it.get(k) in (None, "", []):
                    it[k] = v
        except Exception:  # noqa: BLE001  an extra never costs the page its item
            pass
    return it


def finish(it):
    """One item in the exact shape items.json carries, after read() and with no database connection open: its
    buttons (a mod's card asks its mod), header and the rest."""
    lift(it)
    _mod_choices(it)
    card.fill(it)           # the header, what it needs, the one thing wanted, why it is here: on every card
    return json.loads(json.dumps(it, default=common._plain))


def card_for(iid, wait=False):
    """One card as the page carries it: read from the database, the connection closed, then finished. None when the
    card is not there, or when wait is False and the database is held this moment."""
    import answers
    con = db.connect() if wait else answers._connect()
    if con is None:
        return None
    try:
        it = read(con, answers._row(con, iid))
    finally:
        con.close()
    return finish(it) if it is not None else None


def export(pass_id):
    """Write Live\\items.json: everything not done, plus what was done lately."""
    import settings_page
    cutoff = common.now() - dt.timedelta(days=settings_page.done_days())     # the owner's choice in Settings; 7 when none
    stamp_from()
    items = [it for it in rows("state <> 'done' OR done_at >= ?", (cutoff,))
             if not (it.get("source_key") or "").startswith(RETIRED_PREFIXES)]
    import filters
    hide = filters.get()["nothing_needed"] == "hide"    # the owner's setting: they are on the Hidden list instead
    con = db.connect(read_only=True)
    try:
        for it in items:
            read(con, it)
    finally:
        con.close()
    for it in items:        # the connection is closed: a mod's card may ask its mod for its buttons
        lift(it)
        _mod_choices(it)
        card.fill(it)
    if hide:        # never one from someone who always gets through, nor an "I'd hide this" card: it is there for his answer
        import wouldhide
        items = [it for it in items if it.get("state") not in ("handled", "new") or it.get("shelf")
                 or it.get("status") == card.SEEN_STATUS or wouldhide.is_card(it)
                 or filters.gets_through((it.get("sender") or {}).get("key") or it.get("source_who"), it.get("source_who"))]
    # an answer that has not landed yet still shows: the page never sees it undone
    try:
        import answers
        waiting = answers._pending()
        if waiting:
            items = [json.loads(json.dumps(it, default=common._plain)) for it in items]
            for n, it in enumerate(items):
                for _p, rec in waiting:
                    if rec.get("id") == it["id"]:
                        items[n] = it = answers._overlay(it, rec)
    except Exception:  # noqa: BLE001
        pass
    try:
        write_today()
    except Exception:  # noqa: BLE001
        pass
    snap = {"written_at": common.now(), "pass_id": pass_id, "items": items}
    try:        # the one-time tips of a home that set up with cards (onboard.py): each the first time its thing appears
        import onboard
        onboard.tips(items, snap)
    except Exception:  # noqa: BLE001  a tip never costs the page its cards
        pass
    common.write_json(common.ITEMS_JSON, snap)
    return sum(1 for i in items if i["state"] != "done")


def close_retired(pass_id):
    """Every pass, before the export: a card of a retired kind that is not done yet is
    closed, with one line in its history saying why. Returns how many were closed.
    One read and nothing else when there is none."""
    ensure()
    where = " OR ".join("starts_with(source_key, ?)" for _ in RETIRED_PREFIXES)
    got = db.query(f"SELECT id, assistant_did FROM live_items WHERE ({where}) AND state <> 'done'", RETIRED_PREFIXES)
    if not got:
        return 0
    now = common.now()
    line = (f"Done {now.month}/{now.day}: I no longer change my own program, "
            "so this card needs nothing from you.")
    con = db.connect()
    try:
        for iid, did in got:
            con.execute("UPDATE live_items SET state='done', status='Closed', assistant_did=?, updated_at=?,"
                        " state_changed_at=?, done_at=?, last_pass=? WHERE id=?",
                        (f"{did}\n{line}" if did else line, now, now, now, pass_id, iid))
    finally:
        con.close()
    return len(got)


def upsert(source_key, pass_id, **fields):
    """Make the item for source_key, or change the named columns when any
    differ. Returns (id, 'made' | 'changed' | 'same')."""
    ensure()
    if "title" in fields and "short_header" not in fields:
        fields["short_header"] = None
    dates.store_fields(fields)      # a day is stored as its date, never as "today" or "this morning"
    for c in JSON_COLUMNS:
        if c in fields and not isinstance(fields[c], (str, type(None))):
            fields[c] = json.dumps(fields[c], default=str)
    bad = set(fields) - set(COLUMNS)
    if bad:
        raise ValueError(f"not item columns: {bad}")
    now = common.now()
    con = db.connect()
    try:
        row = con.execute(f"SELECT id, state, {', '.join(fields)} FROM live_items WHERE source_key=?",
                          (source_key,)).fetchone()
        if row is None:
            iid = "L" + str(con.execute("SELECT nextval('seq_live_item')").fetchone()[0])
            full = {"id": iid, "source_key": source_key, "importance": 0, "asks": "[]",
                    "source_messages": "[]", "evidence_files": "[]", "created_at": now,
                    "updated_at": now, "state_changed_at": now, "last_pass": pass_id, **fields}
            if full.get("state") == "done":
                full["done_at"] = now
            con.execute(f"INSERT INTO live_items ({', '.join(full)}) VALUES"
                        f" ({', '.join('?' for _ in full)})", tuple(full.values()))
            return iid, "made"
        iid, old_state = row[0], row[1]
        if _answered(con, iid) and old_state in ("in_motion", "done") and fields.get("state") != "done":
            # the owner answered this one: a pass does not put it back
            fields = {k: v for k, v in fields.items() if k not in ("state", "status")}
            row = (row[0], row[1], *con.execute(
                f"SELECT {', '.join(fields)} FROM live_items WHERE id=?", (iid,)).fetchone())
        diff = {k: v for k, v in zip(fields, row[2:]) if fields[k] != v}
        if not diff:
            return iid, "same"
        sets = {k: fields[k] for k in diff}
        sets.update(updated_at=now, last_pass=pass_id)
        if "state" in diff:
            sets["state_changed_at"] = now
            sets["done_at"] = now if fields["state"] == "done" else None
        con.execute(f"UPDATE live_items SET {', '.join(k + '=?' for k in sets)} WHERE id=?",
                    (*sets.values(), iid))
        return iid, "changed"
    finally:
        con.close()


def _answered(con, iid):
    r = con.execute("SELECT answered_at FROM live_items WHERE id=?", (iid,)).fetchone()
    return bool(r and r[0])


def update(iid, pass_id, **fields):
    """Set named columns on one item (used by the think pass). The state the owner's
    own answer set is not put back by a pass."""
    bad = set(fields) - set(COLUMNS)
    if bad:
        raise ValueError(f"not item columns: {bad}")
    if "title" in fields and "short_header" not in fields:
        fields["short_header"] = None
    dates.store_fields(fields)
    if "state" in fields and fields["state"] != "done":
        con = db.connect()
        try:
            cur = con.execute("SELECT state, answered_at FROM live_items WHERE id=?", (iid,)).fetchone()
        finally:
            con.close()
        if cur and cur[1] and cur[0] in ("in_motion", "done"):
            fields = {k: v for k, v in fields.items() if k not in ("state", "status")}
    for c in JSON_COLUMNS:
        if c in fields and not isinstance(fields[c], (str, type(None))):
            fields[c] = json.dumps(fields[c])
    now = common.now()
    fields.update(updated_at=now, last_pass=pass_id)
    if "state" in fields:
        fields["state_changed_at"] = now
    sets = ", ".join(f"{c}=?" for c in fields)
    db.execute(f"UPDATE live_items SET {sets} WHERE id=?", (*fields.values(), iid))


def main():
    if "--show" in sys.argv:
        for d in rows("state <> 'done'"):
            print(f"{d['id']}  {d['state']:<9} {d['kind']:<8} {'!' if d['importance'] else ' '} {d['title'][:90]}")
        return 0
    first = not db.query("SELECT 1 FROM information_schema.tables WHERE table_name='live_items'")
    pass_id = "manual-" + common.now().strftime("%Y%m%d-%H%M%S")
    made, changed, closed = sync_from_tasks(pass_id, seeding=first)
    carried = enrich_from_briefing(pass_id) if first else 0
    n = export(pass_id)
    print(f"items: {len(made)} made, {len(changed)} changed, {len(closed)} closed,"
          f" {carried} carried from the last briefing, {n} open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
