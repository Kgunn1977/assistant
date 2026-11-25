r"""Standing approvals: a ladder per kind of action per area, everything starting at always ask.

ITEMS.md ("Design round 3") is the contract. A standing approval lets the assistant do one kind of thing, in one
area, without asking each time. It exists only because the owner made it: by answering an offer card, or by
saving the ladder in Settings. Nothing here is particular to anyone: the kinds are general, the areas are the
owner's own, and sending an email is asked each time, by the owner's own Send press, unless the owner made a "send replies to one
person" approval from an offer card (standing_send.py, send.send_standing: every check there, a daily cap, every send recorded).

    ladder()                the entries
    offers(pass_id)         an offer card for a kind and area the owner has approved enough times by hand
    apply(pass_id)          the things the owner's entries say to do, done and recorded
    make_entry(...)         one entry, from an answer to an offer card
    save_ladder(clean)      the ladder as the owner saved it in Settings
    write_feed()            <home>\standing_feed.json for the page: kinds, ladder, log
    mark_undone(card id)    the owner took one of them back
"""
import datetime as dt
import json
import os

import common

FILE = os.path.join(common.PERSONAL, "standing.json")
FEED = os.path.join(common.HOME, "standing_feed.json")
LEVELS = (("ask", "Ask first"), ("tell", "Do it and notify me"), ("quiet", "Do it quietly"))
OFFER_AFTER = (5, 3, 10, 0)
DEVICE = "standing approval"
LOG_KEPT = 100
OFFER_PREFIX = "live:standing-"
CHOICES = {"yes, do it and notify me": "tell", "yes, do it and tell me": "tell", "yes, do it quietly": "quiet", "no": "no"}
# the kinds: each is something that can be taken back. `presses` are the owner's own presses that count as approving it.
KINDS = {
    "close_info": {"label": "Mark cards Done that need nothing", "presses": ("got_it",),
                   "what": "I mark a card that only informs Done for you the next time I check for messages, the same as Got it.",
                   "sentence": "You mark the cards that need nothing in {area} Done. Shall I do it for you from now on?"},
    "drop_waiting": {"label": "Mark waiting cards Done that come back with no reply", "presses": ("drop",),
                     "what": "I mark a waiting card that came back with no reply Done for you the next time I check for messages, the same as Done.",
                     "sentence": "You mark the waiting cards in {area} that come back with no reply Done. Shall I do it for you from now on?"},
    # the owner's yes of 11/16/26: only ever made from an offer card; sends nothing unless send.send_standing agrees (send.py)
    "send_reply": {"label": "Send replies to one person", "presses": (),
                   "what": "I send a short reply I wrote to that one person's own message the next time I check for messages.",
                   "sentence": ""},
}
SEND_KIND = "send_reply"
LEVEL_LABELS = {"level": "Done on my own at a learning level", "level_send": "Reply sent on my own at a learning level"}
SEND_CAPS = (3, 1, 5, 10)           # sends a day under standing approvals; the first is the default
SKIP = ("rule:", "live:standing-", "live:review-", "live:old-cards", "live:newsender-", "live:setup-", "improve:", "built:", "live:rsi-",
        "live:level-")


def _data():
    got = common.read_json(FILE, {}) or {}
    return got if isinstance(got, dict) else {}


def _write(data):
    common.write_json(FILE, data)


def ladder():
    return [e for e in _data().get("entries") or [] if isinstance(e, dict) and e.get("kind") in KINDS and e.get("level") in dict(LEVELS)]


def send_cap():
    n = (common.settings().get("acting") or {}).get("send_cap") if isinstance(common.settings().get("acting"), dict) else None
    return n if n in SEND_CAPS else SEND_CAPS[0]


def send_left():
    """How many more sends under standing approvals today's cap allows."""
    import db
    try:
        used = db.query("SELECT count(*) FROM live_standing_log WHERE kind IN (?, 'level_send') AND CAST(done_at AS DATE) = ?", (SEND_KIND, dt.date.today()))[0][0]
    except Exception:  # noqa: BLE001
        used = 0
    return max(0, send_cap() - int(used))


def offer_after():
    n = (common.settings().get("acting") or {}).get("offer_after") if isinstance(common.settings().get("acting"), dict) else None
    return n if n in OFFER_AFTER else 5


def areas():
    import db
    me = common.personal()
    got = [str(a) for a in (me.get("areas") or []) if a] + ["Personal", "System"]
    try:
        got += [str(r[0]) for r in db.query("SELECT DISTINCT area FROM live_items WHERE area IS NOT NULL")]
    except Exception:  # noqa: BLE001
        pass
    return list(dict.fromkeys(a for a in got if a.strip()))


# --- the table of uses ---------------------------------------------------------------------------
DDL = """
CREATE SEQUENCE IF NOT EXISTS seq_live_standing START 1;
CREATE TABLE IF NOT EXISTS live_standing_log (
  id BIGINT PRIMARY KEY DEFAULT nextval('seq_live_standing'), done_at TIMESTAMP NOT NULL, entry_id INTEGER NOT NULL,
  kind VARCHAR NOT NULL, area VARCHAR NOT NULL, card VARCHAR NOT NULL, header VARCHAR NOT NULL, level VARCHAR NOT NULL,
  undone BOOLEAN NOT NULL DEFAULT FALSE);
ALTER TABLE live_standing_log ADD COLUMN IF NOT EXISTS detail VARCHAR;
"""


def ensure():
    import db
    con = db.connect()
    try:
        con.execute(DDL)
    finally:
        con.close()


# --- making entries: only ever on the owner's say ------------------------------------------------
def _next_id(data):
    n = max([int(data.get("next") or 1)] + [int(e["id"]) + 1 for e in data.get("entries") or [] if isinstance(e.get("id"), int)])
    data["next"] = n + 1
    return n


def make_entry(kind, area, level, source, scope=None, account=None):
    """One entry at the level the owner chose. Called only for the owner's answer to an offer card."""
    if kind not in KINDS or level not in ("tell", "quiet") or area not in areas() or (kind == SEND_KIND and not (scope and account)):
        raise ValueError("not an entry the owner can make")
    data = _data()
    keep = [e for e in data.get("entries") or [] if not (e.get("kind") == kind and e.get("area") == area and e.get("scope") == scope)]
    entry = {"id": _next_id(data), "kind": kind, "area": area, "level": level, "on": True, "used": 0,
             "made": common.now().isoformat(timespec="seconds"), "from": source}
    if scope:
        entry.update(scope=scope, account=account)
    data["entries"] = keep + [entry]
    _write(data)
    return entry


def decline(kind, area, scope=None):
    """He said No: the same offer comes back only after he has approved that many more times."""
    data = _data()
    if scope:
        import standing_send
        data.setdefault("declined", {})[f"{kind}|{area}|{scope}"] = sum(1 for _w, _a, to, _s, iid in standing_send.hand_sends() if to == scope and standing_send._area(iid) == area)
    else:
        data.setdefault("declined", {})[f"{kind}|{area}"] = count_approvals(kind, area)
    _write(data)


def check_ladder(value):
    """A Save of the ladder, checked: [{"id" or None, "kind", "area", "level", "on"}]. Raises ValueError, plain words."""
    if not isinstance(value, list) or len(value) > 60:
        raise ValueError("You can list at most 60 things I do without asking.")
    out, known = [], areas()
    have = {x["id"]: x for x in ladder()}
    for e in value:
        if not isinstance(e, dict) or set(e) - {"id", "kind", "area", "level", "on", "label", "used", "made", "from", "scope", "account"}:
            raise ValueError("Each entry holds its kind, its area, its level, and on or paused.")
        if e.get("kind") == SEND_KIND:
            # sending is never started from Settings: an entry exists only because the owner answered an offer card; here it may only be
            # paused, changed to another level, or removed (by leaving it out)
            was = have.get(e.get("id")) if not isinstance(e.get("id"), bool) else None
            if not was or was.get("kind") != SEND_KIND or was.get("area") != e.get("area") or (e.get("scope") not in (None, was.get("scope"))):
                raise ValueError("I may send without asking only after you say yes on an offer card. Here you can pause it, change its level or remove it.")
            if e.get("level") not in dict(LEVELS) or not isinstance(e.get("on", True), bool):
                raise ValueError("A level is Ask first, Do it and notify me, or Do it quietly. Each entry is on or paused.")
            out.append({"id": e["id"], "kind": SEND_KIND, "area": was["area"], "level": e["level"], "on": bool(e.get("on", True)), "scope": was.get("scope")})
            continue
        if e.get("kind") not in KINDS:
            raise ValueError("That isn't something I can do without asking.")
        if e.get("area") not in known:
            raise ValueError("That is not one of your areas.")
        if e.get("level") not in dict(LEVELS) or not isinstance(e.get("on", True), bool):
            raise ValueError("A level is Ask first, Do it and notify me, or Do it quietly. Each entry is on or paused.")
        rid = e.get("id")
        if rid is not None and (isinstance(rid, bool) or not isinstance(rid, int)):
            raise ValueError("I couldn't tell which entry that is.")
        out.append({"id": rid, "kind": e["kind"], "area": e["area"], "level": e["level"], "on": bool(e.get("on", True))})
    pairs = [(e["kind"], e["area"], e.get("scope")) for e in out]
    if len(pairs) != len(set(pairs)):
        raise ValueError("Each kind of thing has one entry for each area.")
    return out


def save_ladder(clean):
    """The owner's Save. Returns the plain line saying what changed."""
    data = _data()
    old = {e["id"]: e for e in ladder()}
    rows, said = [], []
    for e in clean:
        was = old.get(e["id"]) if e["id"] is not None else None
        entry = {"id": e["id"] if was else _next_id(data), "kind": e["kind"], "area": e["area"], "level": e["level"], "on": e["on"],
                 "used": (was or {}).get("used", 0), "made": (was or {}).get("made") or common.now().isoformat(timespec="seconds"),
                 "from": (was or {}).get("from") or "You set it in Settings"}
        if was and was.get("scope"):
            entry.update(scope=was["scope"], account=was.get("account"))
        rows.append(entry)
        label = f"{KINDS[e['kind']]['label'].lower()} in {e['area']}" + (f" ({was['scope']})" if was and was.get("scope") else "")
        if not was:
            said.append(f"added: {label}, {dict(LEVELS)[e['level']].lower()}")
        elif (was["level"], was.get("on", True)) != (e["level"], e["on"]):
            said.append(f"changed: {label}, {dict(LEVELS)[e['level']].lower()}" + ("" if e["on"] else ", paused"))
    for i, was in old.items():
        if i not in {e["id"] for e in rows}:
            if was.get("scope"):        # removed: the offer comes back only after that many more sends by hand
                import standing_send
                data.setdefault("declined", {})[f"{was['kind']}|{was['area']}|{was['scope']}"] = sum(
                    1 for _w, _a, to, _s, iid in standing_send.hand_sends() if to == was["scope"] and standing_send._area(iid) == was["area"])
            said.append(f"removed: {KINDS[was['kind']]['label'].lower()} in {was['area']}" + (f" ({was['scope']})" if was.get("scope") else ""))
    data["entries"] = rows
    _write(data)
    return "; ".join(said)


# --- offers ---------------------------------------------------------------------------------------
def count_approvals(kind, area):
    """How many times the owner, by hand, did this kind of thing on a card of this area."""
    import db
    marks = ",".join("?" for _ in KINDS[kind]["presses"])
    try:
        return db.query(f"SELECT count(*) FROM live_presses p JOIN live_items i ON i.id = p.item_id WHERE p.ok AND p.press IN ({marks})"
                        f" AND p.device <> ? AND i.area = ?", (*KINDS[kind]["presses"], DEVICE, area))[0][0]
    except Exception:  # noqa: BLE001  no presses table yet: nothing has been approved
        return 0


def earned():
    """[(kind, area, how many times approved)] the owner has earned an offer for: enough presses by hand, no entry,
    no offer waiting, and not turned down since."""
    import db
    n = offer_after()
    if not n:
        return []
    have = {(e["kind"], e["area"]) for e in ladder() if e["kind"] != SEND_KIND}
    declined = _data().get("declined") or {}
    waiting = [r[0] for r in db.query("SELECT source_key FROM live_items WHERE starts_with(source_key, ?) AND state <> 'done'", (OFFER_PREFIX,))]
    out = []
    for kind in KINDS:
        if kind == SEND_KIND:
            continue
        for area in areas():
            if (kind, area) in have or any(w == f"{OFFER_PREFIX}{kind}-{area}" or w.startswith(f"{OFFER_PREFIX}{kind}-{area}-") for w in waiting):
                continue
            c = count_approvals(kind, area)
            if c >= n and c - int(declined.get(f"{kind}|{area}") or 0) >= n:
                out.append((kind, area, c))
    return out


def offers(pass_id):
    """Make the offer cards the owner has earned. Returns how many."""
    import items
    items.ensure()
    made = 0
    declined = _data().get("declined") or {}
    for kind, area, c in earned():
        again = f"-{c}" if f"{kind}|{area}" in declined else ""        # an offer he turned down comes back as a new card
        items.upsert(f"{OFFER_PREFIX}{kind}-{area}{again}", pass_id, kind="question", area=area, state="question", status=None,
                     title=KINDS[kind]["sentence"].format(area=area),
                     detail=f"You have done this by hand {c} times for cards in {area}. {KINDS[kind]['what']} "
                            "You can pause or remove it any time in Settings, under Approvals, and every use is listed "
                            "with an Undo. Nothing is done for you unless you say yes here.",
                     asks=["Shall I do it for you from now on?"], why="You have done the same thing by hand several times.",
                     extra={"offer": {"kind": kind, "area": area, "count": c}})
        made += 1
    import standing_send
    for spec in standing_send.earned():
        standing_send.offer(spec, pass_id)
        made += 1
    return made


# --- doing what the owner's entries say -----------------------------------------------------------
def _candidates(entry):
    import card
    import items
    out = []
    for it in items.rows("state <> 'done' AND shelf IS NULL AND area = ?", (entry["area"],)):
        if str(it.get("source_key") or "").startswith(SKIP):
            continue
        extra = it.get("extra") if isinstance(it.get("extra"), dict) else {}
        if extra.get("standing_skip") or it.get("replayed"):
            continue                                    # he took one of these back, or the card came from the replay: never acted on
        if entry["kind"] == "close_info" and card.needs(it) == "nothing" and it["state"] in ("handled", "new"):
            out.append(it)
        elif entry["kind"] == "drop_waiting" and extra.get("came_back") and it["state"] == "yours":
            out.append(it)
    return out


def apply(pass_id):
    """Act on the owner's entries (level tell or quiet, on). Every use is recorded, at every level. Returns how many."""
    import replay_guard
    replay_guard.refuse("standing approvals")
    import db
    import items
    import presses
    entries = [e for e in ladder() if e.get("on", True) and e["level"] in ("tell", "quiet")]
    sends = [e for e in entries if e["kind"] == SEND_KIND]
    entries = [e for e in entries if e["kind"] != SEND_KIND]
    if not entries and not sends:
        return 0
    ensure()
    now, done = common.now(), 0
    data = _data()
    for entry in entries:
        for it in _candidates(entry):
            press = "standing_close" if entry["kind"] == "close_info" else "standing_drop"
            say = (f"Done for you: {KINDS[entry['kind']]['label'].lower()} in {entry['area']}, "
                   f"with the permission you gave me on {dt.datetime.fromisoformat(entry['made']):%m/%d}.").replace(" 0", " ").replace("/0", "/")
            mark = presses._mark(press, now, say, was=presses._was(it))
            line = f"{say} ({presses._stamp(now)})"
            db.execute("UPDATE live_items SET state='done', status='Done for you', done_at=?, assistant_did=?, last_press=?, updated_at=?,"
                       " state_changed_at=?, last_pass=? WHERE id=?",
                       (now, f"{it.get('assistant_did')}\n{line}" if it.get("assistant_did") else line, json.dumps(mark), now, now, pass_id, it["id"]))
            db.execute("INSERT INTO live_standing_log (done_at, entry_id, kind, area, card, header, level) VALUES (?,?,?,?,?,?,?)",
                       (now, entry["id"], entry["kind"], entry["area"], it["id"], " ".join(str(it["title"]).split())[:200], entry["level"]))
            presses.record(pressed_at=now, received_at=now, item_id=it["id"], item_title=it["title"], press=press, choice=entry["level"],
                           words="-", device=DEVICE, happened=say, ok=True, claude_ran=False, secs=0)
            for e in data.get("entries") or []:
                if e.get("id") == entry["id"]:
                    e["used"] = int(e.get("used") or 0) + 1
            done += 1
    if done:
        _write(data)
    if sends:
        import standing_send
        done += standing_send.apply(pass_id, sends)
    return done


def mark_undone(card_id):
    import db
    try:
        db.execute("UPDATE live_standing_log SET undone=TRUE WHERE card=? AND NOT undone", (card_id,))
        write_feed()
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"standing undo: {type(e).__name__}: {e}")


# --- what the page gets ----------------------------------------------------------------------------
def for_page():
    return [{"id": e["id"], "kind": e["kind"], "label": KINDS[e["kind"]]["label"] + (f": {e['scope']}" if e.get("scope") else ""), "area": e["area"],
             "level": e["level"], "on": bool(e.get("on", True)), "used": int(e.get("used") or 0), "made": e.get("made"), "from": e.get("from"),
             **({"scope": e["scope"]} if e.get("scope") else {})} for e in ladder()]


def write_feed():
    import db
    ensure()
    log = []
    for i, a, k, ar, c, h, lv, u, det in db.query(
            f"SELECT id, done_at, kind, area, card, header, level, undone, detail FROM live_standing_log ORDER BY id DESC LIMIT {LOG_KEPT}"):
        row = {"id": i, "at": a.isoformat(timespec="seconds"), "kind": k, "label": LEVEL_LABELS.get(k) or KINDS.get(k, {}).get("label", k), "area": ar, "card": c,
               "header": h, "level": lv, "undone": bool(u)}
        if det:
            try:
                row["sent"] = json.loads(det)         # what was sent, to whom and which approval allowed it
            except ValueError:
                pass
        log.append(row)
    today = dt.date.today().isoformat()
    doc = {"written_at": common.now(), "today": sum(1 for r in log if r["level"] == "tell" and not r["undone"] and r["at"][:10] == today),
           "kinds": [{"kind": k, "label": v["label"], "what": v["what"]} for k, v in KINDS.items()], "ladder": for_page(), "log": log}
    common.write_json(FEED, doc)
    return doc
