r"""The rule book: the answer key built only from the owner's presses (the RSI plan, "The rule book's rows").

Written by program code at press time, never by Claude: a press on a card that came from messages writes one row per message
to <home>\personal\rule_book.jsonl. A row says what the assistant decided about that message (the call: show or hide, the
verdict and its source), which layer decided it, the rules it leaned on where the source names them, the judge's own word on
whether a rule covered it (covered, leaned_on: as the answered table keeps them, None when not said), a small snapshot of
what was seen, and the press with its meaning. The file only grows. Reading it, the newest row with a signal wins for a message
and a neutral press (Got it) never replaces one; a row can be retired. A press while the database is held is written as
waiting and counts once drain() has filled in its call. A row whose press contradicts the call it records (a miss) queues
one RSI job for its section (rsi_loop.on_rows), and nothing more. A replay day (ASSISTANT_REPLAY) writes nothing.

    section(item, source, channel)      which part of the assistant a card or message belongs to (SECTIONS)
    call_of(verdict, source, shown)     (call, layer, rule ids) for one message's verdict
    held_calls(key)                     the call on a row under Hidden, read before its card is made (held.show overwrites it)
    on_press(item, press, ...)          the rows for one press on one card; never raises
    drain()                             fill in the call of rows written while the database was held
    rows(section=None, active_only)     the rule book as it reads now: one row per message, newest first
    retire(message id)                  the row for that message stops counting
    keep(message id), edit(id, right, note)   Settings review: marked reviewed; the owner's own right answer
    for_settings()                      the active rows for Settings, by section, in plain words
    act(record)                         one Keep, Edit or Retire press from Settings
"""
import json
import os
import re
import threading
import uuid

import common

STORE = os.path.join(common.PERSONAL, "rule_book.jsonl")
WAITING = os.path.join(common.PERSONAL, "rule_book_waiting.json")     # rows written while the database was held
SECTIONS = ("mailings", "bills", "page", "calendar", "replies", "followups")
HIDES = ("noise", "ignore", "phishing")
MOST = 25                       # messages a card writes rows for
_lock = threading.Lock()


def _replaying():
    return os.environ.get("ASSISTANT_REPLAY") == "1"


# --- sections ----------------------------------------------------------------------------------------------------------
def section(item=None, source=None, channel=None):
    """One of SECTIONS, by plain rules on the card's kind, key and area and the message's hold reason (source: given only
    for a message that was hidden); page when none fits."""
    it = item if isinstance(item, dict) else {}
    key = str(it.get("source_key") or "")
    kind = str(it.get("kind") or "").lower()
    area = str(it.get("area") or "").lower()
    src = str(source or "").lower()
    extra = it.get("extra") if isinstance(it.get("extra"), dict) else {}
    if kind.startswith("calendar") or channel == "calendar" or key.startswith(("task:calendar::", "calendar")):
        return "calendar"
    if kind == "waiting" or extra.get("came_back") or it.get("came_back"):
        return "followups"
    if key.startswith("live:ready-") or isinstance(it.get("draft"), dict) or kind == "reply":
        return "replies"
    if key.startswith("live:receipts-") or any(w in area for w in ("bill", "receipt", "financ", "money")):
        return "bills"
    if src == "rule:559" or it.get("mailing") is True or re.search(r"\b(unsubscribe|newsletters?|mailings?)\b", src):
        return "mailings"
    return "page"


# --- the call and the layer that made it -------------------------------------------------------------------------------
def _rule_ids(source):
    """The rules a verdict names in its structured source; never numbers guessed out of a reason's free words."""
    s = str(source or "").strip()
    m = re.match(r"^rule:(\d+)$", s)
    if m:
        return [f"rule:{m.group(1)}"]
    m = re.match(r"^owner rule (\d+):", s, re.I)
    if m:
        return [f"personal:{m.group(1)}"]
    if s.startswith("mod:"):
        return [s[:80]]
    return []


def _layer(verdict, source):
    """The layer that settled a verdict, in held.py's words, with its "sorting" split into the first sort and the judge."""
    s = str(source or "").strip()
    if s.startswith("owner:") and s != "owner:ignore":
        return "owner"
    if verdict in HIDES:
        import held
        by = held.why(verdict, s)[1]
        if by == "sorting":
            return "first_sort" if s.lower().startswith("fast:") else "judge"
        return by
    if s.lower().startswith("fast:"):
        return "first_sort"
    return "judge"


def call_of(verdict, source, shown=None):
    """(call, layer, rule ids) for one message. A card made at his asking (owner:should_have_seen, owner:always_through)
    keeps the call that held it, read from the Hidden row kept when the card was made (shown: held_shown.json's row)."""
    s = str(source or "").strip()
    if s in ("owner:should_have_seen", "owner:always_through") and isinstance(shown, dict) and shown.get("by"):
        return "hide", _held_layer(shown), []
    if verdict is None:
        return None, "unknown", []
    return ("hide" if verdict in HIDES else "show"), _layer(verdict, s), _rule_ids(s)


def _held_layer(row):
    by = str(row.get("by") or "unknown")
    return "judge" if by == "sorting" else by        # the Hidden row no longer tells the first sort from the judge


def held_calls(key):
    """{message id: the call as the Hidden row shows it} for a press on a row under Hidden, read before held.show() makes its
    card (making it overwrites the verdict). From the database when free, else from the Hidden list the page was shown.
    Never raises: {} when it cannot be read, and the press goes on."""
    try:
        return _held_calls(key)
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"rule book held: {type(e).__name__}: {e}")
        return {}


def _held_calls(key):
    import held
    m = held.KEY.match(str(key or ""))
    if not m:
        return {}
    if m.group(2):          # a card kept out by the setting "hide things that need nothing": the setting was the layer
        return {"card": m.group(2), "hide": {"call": "hide", "layer": "setting", "verdict": None,
                                             "source": "setting:nothing_needed", "rules": []}}
    mid = m.group(1)
    row = next((r for d in (common.read_json(held.HELD_JSON, {}) or {}).get("days") or [] for r in d.get("rows") or []
                if r.get("key") == f"held-{mid}"), None)
    got = _from_db([mid])[1].get(mid)
    if got and got.get("verdict") in HIDES:
        return {mid: got}
    if row:
        return {mid: {"call": "hide", "layer": _held_layer(row), "verdict": None, "source": None, "rules": [],
                      "seen": {"sender": row.get("who") or row.get("address"), "what": row.get("what"), "channel": row.get("channel")}}}
    return {mid: {"call": None, "layer": "unknown", "verdict": None, "source": None, "rules": []}}


def _from_db(mids):
    """(read, {message id: call, layer, verdict, source, rules, seen}) from the answered and messages tables; read is False
    while the database is held (a press never waits for it)."""
    ids = sorted({int(m) for m in mids if str(m).isdigit()})
    if not ids:
        return True, {}
    try:
        import db
        con = db.try_connect()
    except Exception:  # noqa: BLE001
        con = None
    if con is None:
        return False, {}
    got = []
    try:
        cols = {str(r[0]) for r in con.execute("SELECT column_name FROM information_schema.columns "
                                               "WHERE table_name = 'answered'").fetchall()}
        mark = ("a.covered, a.leaned_on" if {"covered", "leaned_on"} <= cols
                else "NULL, NULL")          # a home whose answered table has no coverage columns yet: not said
        for i in range(0, len(ids), 500):
            part = ids[i:i + 500]
            got += con.execute(
                f"""SELECT m.id, m.channel, m.direction, m.from_key, m.subject, substr(m.body, 1, 300), a.verdict, a.source,
                           (SELECT max(c.name) FROM contacts c WHERE c.person_id = m.person_id AND c.name IS NOT NULL),
                           {mark}
                    FROM messages m LEFT JOIN answered a ON a.domain = 'judged' AND a.key = 'msg:' || m.id
                    WHERE m.id IN ({','.join('?' for _ in part)})""", part).fetchall()
    except Exception as e:  # noqa: BLE001  a table not there yet: the rows say unknown
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"rule book read: {type(e).__name__}: {e}")
        got = []
    finally:
        con.close()
    shown = common.read_json(_shown_path(), {}) or {}
    out = {}
    for mid, channel, direction, fk, subject, body, verdict, source, name, covered, leaned in got:
        if direction != "in" and verdict is None:
            continue                # his own sent mail on the card: nothing was decided about it
        call, layer, rules = call_of(verdict, source, shown.get(str(mid)))
        first = " ".join(str(subject or "").split()) or " ".join(str(body or "").split())
        out[str(mid)] = {"call": call, "layer": layer, "verdict": verdict, "source": (str(source)[:200] if source else None),
                         "rules": rules, "covered": covered if isinstance(covered, bool) else None,
                         "leaned_on": str(leaned) if leaned is not None else None, "seen": {"sender": " ".join(str(name or "").split()) or str(fk or "").split(":", 1)[-1],
                                                  "what": first[:160], "channel": channel}}
    return True, out


def _shown_path():
    import held
    return held.SHOWN


# --- writing ---------------------------------------------------------------------------------------------------------
def _mids(item):
    got = (item or {}).get("source_messages")
    if isinstance(got, str):
        try:
            got = json.loads(got)
        except ValueError:
            got = []
    return [str(m) for m in got or [] if str(m).isdigit()][:MOST]


def _append(rows):
    if _replaying() or not rows:
        return 0
    with _lock:
        os.makedirs(os.path.dirname(STORE), exist_ok=True)
        with open(STORE, "a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    return len(rows)


def _misses(rows):
    """Rows just written that contradict the call they record queue an RSI job for their section (rsi_loop.on_rows): the
    queue only, never Claude. Never raises."""
    try:
        import rsi_loop
        rsi_loop.on_rows(rows)
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"rule book miss: {type(e).__name__}: {e}")


def _waiting(add=None, drop=None):
    """The ids of rows written while the database was held, still waiting for their call. Under the lock."""
    with _lock:
        ids = [i for i in (common.read_json(WAITING, []) or []) if isinstance(i, str)]
        if add or drop:
            ids = [i for i in ids if i not in set(drop or [])] + [i for i in add or [] if i not in ids]
            common.write_json(WAITING, ids)
        return ids


def on_press(item, press, meaning, button="-", choice="-", when=None, calls=None, pick=None, took_pick=False, words=""):
    """One row per message the card came from, for one press. calls: what was decided, when the caller read it before the
    press changed it (a row under Hidden). pick: what I predicted he would do (picks.of, read before the press); every row
    then carries the pick, what he did and whether they matched, and a card with no messages behind it gets one row of its
    own (message "card:<id>", no call). Returns how many rows were written. Never raises."""
    return on_presses([item], press, meaning, button, choice, when, calls, pick, took_pick, words)


CARD_ID = re.compile(r"^L\d+$")
ROW_KEY = re.compile(r"\d+|card:L\d+|cal:[^\s]{1,200}|draft:[^\s]{1,200}")     # a message, a card with no messages, a calendar event, a sent draft


def _important(item):
    """Whether the card was marked important when he pressed (urgency, work_rules.py); None when the card does not say."""
    if "importance" in (item or {}):
        return bool(item.get("importance"))
    if "important" in (item or {}):
        return bool(item.get("important"))
    return None


def _pick_fields(item, press, choice, words, pick, took_pick):
    """The pick, what he did and the outcome, for a row; and what he did is kept for the next card like it when it
    differed (picks.remember). {} when no pick was given."""
    if pick is None:
        return {}
    import picks
    did = picks.did_of(press, choice, words)
    out = picks.outcome(pick, did, took_pick)
    if out == "differed":
        picks.remember(item, did)
    return {"pick": {k: v for k, v in pick.items() if k != "label"}, "did": did, "pick_outcome": out}


def on_presses(cards, press, meaning, button="-", choice="-", when=None, calls=None, pick=None, took_pick=False, words=""):
    """The same for one press on several cards (Got it all), with one look at the database for all of them. While the
    database is held the rows are written as waiting (the press as it happened, no call yet) and drain() fills in the call
    once it is free; a waiting row does not count until then. Never raises."""
    try:
        if _replaying():
            return 0
        drain()
        calls = dict(calls or {})
        override = calls.pop("hide", None) if "card" in calls else None     # a card the nothing-needed setting kept out
        calls.pop("card", None)
        todo = []
        at = (when or common.now())
        at = at.isoformat(timespec="seconds") if hasattr(at, "isoformat") else str(at)
        alone = []          # a card with no messages behind it, pressed with a pick on it: one row of its own
        for item in cards or []:
            item = item if isinstance(item, dict) else {}
            mids = (list(calls) if len(cards) == 1 else []) or _mids(item)
            if mids:
                todo.append((item, mids))
            elif pick is not None and CARD_ID.match(str(item.get("id") or "")):
                alone.append(item)
        n_alone = 0
        for item in alone:
            n_alone += _append([dict({"id": uuid.uuid4().hex[:16], "at": at, "message": f"card:{item['id']}",
                                      "section": section(item), "card": item.get("id"), "card_kind": item.get("kind"),
                                      "card_area": item.get("area"), "card_important": _important(item), "call": None, "layer": "unknown", "verdict": None,
                                      "source": None, "rules": [], "covered": None, "leaned_on": None,
                                      "seen": {"sender": str(item.get("source_who") or "")[:120],
                                               "what": str(item.get("title") or "")[:160], "channel": None},
                                      "press": press, "meaning": meaning, "button": button or "-",
                                      "choice": str(choice or "-")[:200], "status": "active"},
                                     **_pick_fields(item, press, choice, words, pick, took_pick))])
        if not todo:
            return n_alone
        picked = {id(item): _pick_fields(item, press, choice, words, pick, took_pick) for item, _m in todo}
        read, found = _from_db([m for _it, mids in todo for m in mids if m not in calls])
        out, wait = [], []
        for item, mid in [(it, m) for it, mids in todo for m in mids]:
            c = dict(calls.get(mid) or found.get(mid) or {})
            pending = not c and not read and not override      # the database was held: its call is filled in by drain()
            if not c and not pending and not override:
                continue
            if override:
                c.update({k: override[k] for k in ("call", "layer", "source", "rules")})
            seen = c.get("seen") or {"sender": item.get("source_who"), "what": item.get("title"), "channel": None}
            row = {"id": uuid.uuid4().hex[:16], "at": at, "message": mid,
                   "section": section(item, c.get("source") if c.get("call") == "hide" else None, seen.get("channel")),
                   "card": item.get("id"), "card_kind": item.get("kind"), "card_area": item.get("area"),
                   "card_important": _important(item), "call": c.get("call"), "layer": c.get("layer"), "verdict": c.get("verdict"), "source": c.get("source"),
                   "rules": c.get("rules") or [], "covered": c.get("covered"), "leaned_on": c.get("leaned_on"),
                   "seen": {"sender": str(seen.get("sender") or "")[:120], "what": str(seen.get("what") or "")[:160],
                            "channel": seen.get("channel")},
                   "press": press, "meaning": meaning, "button": button or "-", "choice": str(choice or "-")[:200],
                   "status": "active", **picked.get(id(item), {})}
            if pending:
                row["pending"] = True
                wait.append(row["id"])
            out.append(row)
        n = _append(out)
        if wait and n:
            _waiting(add=wait)
        if n:
            _misses(out)
        return n + n_alone
    except Exception as e:  # noqa: BLE001  the press itself already happened; a row that cannot be written is logged
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"rule book: {type(e).__name__}: {e}")
        return 0


def drain():
    """Fill in the call, layer, source and rules of every row written while the database was held, now that it is free:
    one fill line per row, written after it (the file only grows). A message the database does not know gets layer
    unknown. Returns how many were filled; 0 while the database is still held. Never raises."""
    try:
        if _replaying():
            return 0
        ids = _waiting()
        if not ids:
            return 0
        filled = {r["fill"] for r in _read() if r.get("fill")}
        todo = [r for r in _read() if r.get("pending") and r.get("id") in ids and r["id"] not in filled]
        if not todo:
            _waiting(drop=ids)
            return 0
        read, found = _from_db([r["message"] for r in todo])
        if not read:
            return 0
        out = []
        for r in todo:
            c = found.get(str(r["message"])) or {"call": None, "layer": "unknown", "verdict": None, "source": None, "rules": []}
            seen = c.get("seen") or r.get("seen") or {}
            sec = r.get("section")
            if sec == "page":       # nothing on the card placed it: the message's own hold reason and channel may
                sec = section({}, c.get("source") if c.get("call") == "hide" else None, seen.get("channel"))
            out.append({"fill": r["id"], "message": r["message"], "at": common.now().isoformat(timespec="seconds"),
                        "call": c.get("call"), "layer": c.get("layer"), "verdict": c.get("verdict"), "source": c.get("source"),
                        "rules": c.get("rules") or [], "covered": c.get("covered"), "leaned_on": c.get("leaned_on"),
                        "seen": seen, "section": sec})
        _append(out)
        _waiting(drop=[r["id"] for r in todo])
        by = {f["fill"]: f for f in out}
        _misses([dict(r, **{k: v for k, v in by[r["id"]].items() if k not in ("fill", "at")}, pending=False) for r in todo])
        return len(out)
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"rule book drain: {type(e).__name__}: {e}")
        return 0


def retire(mid, why=""):
    """The message stops counting: a copy of the row that counts for it now, marked retired, written after it. A later press
    counts again. Returns True when there was one."""
    now = _resolve().get(str(mid))
    if not now or now[1].get("status") != "active":
        return False
    r = {k: v for k, v in now[1].items() if k not in ("pending",)}
    return _append([dict(r, id=uuid.uuid4().hex[:16], at=common.now().isoformat(timespec="seconds"), status="retired",
                         retired_why=" ".join(str(why or "").split())[:300])]) == 1


# --- review in Settings: Keep, Edit, Retire ----------------------------------------------------------------------------
def _counting(mid):
    """The active row that counts for a message now, as a copy ready to be written again, or None."""
    now = _resolve().get(str(mid))
    if not now or now[1].get("status") != "active":
        return None
    return {k: v for k, v in now[1].items() if k not in ("pending", "fill")}


def keep(mid):
    """Keep: the row stands as it is and is marked reviewed (a copy written after it, its date and press unchanged)."""
    r = _counting(mid)
    if r is None:
        return False
    return _append([dict(r, id=uuid.uuid4().hex[:16], reviewed_at=common.now().isoformat(timespec="seconds"),
                         review="keep")]) == 1


def edit(mid, right, note=""):
    """Edit: the owner says what the right answer was (show or hide, and a note). Written as his own answer: a copy of the
    row with his answer as its press and the meaning it carries against the assistant's call, so it counts over any older
    press for the message."""
    r = _counting(mid)
    if r is None or right not in ("show", "hide"):
        return False
    call = r.get("call")
    if call == right:
        meaning = "agrees"
    elif call in ("show", "hide"):
        meaning = "contradicts-hide" if right == "show" else "contradicts-show"
    else:
        meaning = "needed" if right == "show" else "not-needed"
    at = common.now().isoformat(timespec="seconds")
    row = dict(r, id=uuid.uuid4().hex[:16], at=at, reviewed_at=at, review="edit", press="rule_book_edit", meaning=meaning,
               button="edit", choice=right, right=right, by="owner", note=" ".join(str(note or "").split())[:300])
    if _append([row]) != 1:
        return False
    _misses([row])
    return True


SECTION_WORDS = {"mailings": "Mailings and unsubscribe", "bills": "Bills and receipts", "page": "What reaches the page",
                 "calendar": "Calendar", "replies": "Reply drafts", "followups": "Follow-ups and clearing"}
PRESS_WORDS = {"got_it": "Got it", "got_it_all": "Got it all", "done": "Done", "later": "Later", "someday": "Someday",
               "bring_back": "Bring back", "junk": "Junk", "never_junk": "Never junk", "approve": "Approve", "undo": "Undo",
               "not_needed": "Not needed", "always_show": "Always show", "no": "No", "wait_longer": "Wait longer",
               "write_them": "Write to them", "drop": "Drop", "old_card": "Old card", "old_keep": "Keep",
               "should_have_seen": "I should have seen this", "read": "Read", "rule_offer": "Rule"}
LAYER_WORDS = {"setting": "One of your settings hid it.", "junk_list": "The sender is on your junk list.",
               "ignore_list": "The sender is on your list of senders to always ignore.", "rule": "One of your rules hid it.",
               "first_sort": "My fast first look saw nothing you need to do.",
               "judge": "I read it and saw nothing you need to do."}
SHOWN_MOST = 200           # rows sent to the page's Settings; the rest are counted


def _did(r):
    """What the assistant did about the message, in plain words."""
    call, src = r.get("call"), str(r.get("source") or "")
    if isinstance(r.get("draft_edit"), dict):
        return "I wrote the draft."
    if r.get("off_page"):
        return "It was on your page as a card." if r.get("card") else "It wasn't on your page."
    if call is None and str(r.get("message") or "").startswith("card:"):
        return "It was a card on your page."
    if call == "hide":
        if src and not src.startswith("owner:"):
            try:
                import held
                return "Hid it. " + held.why(r.get("verdict"), src)[0]
            except Exception:  # noqa: BLE001
                pass
        return ("Hid it. " + LAYER_WORDS.get(r.get("layer"), "")).strip()
    if call == "show":
        return "Showed it on your page."
    return "I have no record of it."


def _you(r):
    """What the owner did, in plain words, and what I had picked when it was something else."""
    said = _you_did(r)
    if isinstance(r.get("draft_edit"), dict):
        return said
    if r.get("pick_outcome") == "differed" and isinstance(r.get("pick"), dict):
        import picks
        said += f" I'd picked \"{picks.label(r['pick'])}\"."
    elif r.get("pick_outcome") == "matched":
        said += " That was my pick."
    return said


OFF_PAGE_WORDS = {"sent": "You sent it from {where}.", "accepted": "You accepted it in your calendar.",
                  "declined": "You declined it in your calendar.", "tentative": "You said maybe in your calendar.",
                  "moved": "You moved it in your calendar."}


def _you_did(r):
    e = r.get("draft_edit")
    if isinstance(e, dict):
        if e.get("outcome") == "unchanged":
            return "You sent my draft unchanged."
        return (f"You rewrote my draft before sending it, keeping {round(100 * float(e.get('kept') or 0))}% of my words. "
                + " ".join(e.get("changes") or [])[:400]).strip()
    if r.get("review") == "edit" or r.get("press") == "rule_book_edit":
        return "You set the right answer here: " + ("show it." if r.get("right") == "show" else "hide it.")
    if r.get("off_page"):
        o = r["off_page"]
        return OFF_PAGE_WORDS.get(o.get("did"), "You did this outside the page.").format(
            where="this page" if o.get("where") == "page" else f"your {o.get('channel') or 'account'}")
    if r.get("press") == "words":
        return f"You wrote: \"{str(r.get('choice') or '')[:120]}\"."
    press, choice = str(r.get("press") or ""), str(r.get("choice") or "-")
    if press == "choice" and choice != "-":
        return f"You chose \"{choice}\"."
    import presses          # a switchable button's own label (presses.SWITCHES)
    words = PRESS_WORDS.get(press) or (presses.SWITCHES.get(press) or {}).get("label")
    return f"You pressed \"{words or press.replace('_', ' ').capitalize() or 'a button'}\"."


def for_settings(most=SHOWN_MOST):
    """The active rule book for the Settings part: {"sections": [{id, label, rows}], "count", "more"}. Sections in their
    fixed order (only those with rows), rows newest first by when the press was made; each row in plain words."""
    got = sorted(rows(), key=lambda r: str(r.get("at") or ""), reverse=True)
    shown, out = got[:most], {}
    for r in shown:
        seen = r.get("seen") or {}
        out.setdefault(r.get("section") if r.get("section") in SECTIONS else "page", []).append({
            "message": str(r.get("message")), "at": r.get("at"), "sender": seen.get("sender") or "",
            "what": seen.get("what") or "", "channel": seen.get("channel"), "call": r.get("call"),
            "did": _did(r), "you": _you(r), "right": r.get("right") or r.get("call"), "note": r.get("note") or "",
            "reviewed": r.get("reviewed_at"), "edited": r.get("review") == "edit"})
    return {"sections": [{"id": s, "label": SECTION_WORDS[s], "rows": out[s]} for s in SECTIONS if s in out],
            "count": len(got), "more": max(0, len(got) - len(shown))}


def act(rec):
    """One press in Settings, Rule book ({"rule_book": {"op": keep, edit or retire, "message": id, "right", "note"}}), in
    the shape answers.act_on_answer returns. Never raises."""
    try:
        body = json.loads(rec.get("text") or "")
        p = body.get("rule_book") if isinstance(body, dict) else None
        op, mid = (p.get("op"), str(p.get("message") or "")) if isinstance(p, dict) else (None, "")
        if op not in ("keep", "edit", "retire") or not ROW_KEY.fullmatch(mid):
            said = "Not done: that wasn't a rule book button."
        elif op == "keep":
            said = "Kept. It's marked reviewed." if keep(mid) else "Not done: that entry is no longer in the rule book."
        elif op == "edit":
            if p.get("right") not in ("show", "hide"):
                said = "Not done: choose Show it or Hide it."
            else:
                said = ("Saved as your answer." if edit(mid, p.get("right"), p.get("note"))
                        else "Not done: that entry is no longer in the rule book.")
        else:
            said = ("Done. I won't learn from this one." if retire(mid, "retired in Settings")
                    else "Not done: that entry is no longer in the rule book.")
    except Exception as e:  # noqa: BLE001  a press that trips never takes the listener with it
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"rule book review: {type(e).__name__}: {e}")
        said = f"Not done: something went wrong on your computer ({type(e).__name__})."
    return {"ok": True, "items": [], "result": said, "thought": False, "secs": {}}


# --- reading ---------------------------------------------------------------------------------------------------------
def _read():
    try:
        with open(STORE, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    out = []
    for x in lines:
        try:
            r = json.loads(x)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("message"):
            out.append(r)
    return out


def _resolve():
    """{message id: (its place in the file, the row that counts for it)}. The file's order is the truth: a waiting row counts
    only once filled; the newest row with a signal (any meaning but neutral) wins over every neutral row, older or newer; a
    neutral row counts only when the message has no signal; a retired row clears the message until a later press."""
    got = _read()
    fills = {r["fill"]: r for r in got if r.get("fill")}
    state = {}
    for n, r in enumerate(got):
        if r.get("fill"):
            continue
        if r.get("pending"):
            f = fills.get(r.get("id"))
            if f is None:
                continue                # still waiting for its call: it does not count yet
            r = dict(r, **{k: f[k] for k in ("call", "layer", "verdict", "source", "rules", "covered", "leaned_on", "seen",
                                                 "section") if k in f})
            r.pop("pending", None)
        mid = str(r["message"])
        if r.get("status") == "retired":
            state[mid] = {"retired": (n, r)}
            continue
        st = state.setdefault(mid, {})
        st.pop("retired", None)
        st["neutral" if r.get("meaning") == "neutral" else "signal"] = (n, r)
    return {mid: st.get("signal") or st.get("neutral") or st.get("retired") for mid, st in state.items()
            if st.get("signal") or st.get("neutral") or st.get("retired")}


def rows(section=None, active_only=True):
    """The rule book as it reads now: the row that counts for each message (_resolve), then filtered by status and section,
    so a retired message never lets an older row count again. Newest first."""
    got = sorted(_resolve().values(), key=lambda x: x[0], reverse=True)
    return [r for _n, r in got if (not active_only or r.get("status") == "active")
            and (section is None or r.get("section") == section)]
