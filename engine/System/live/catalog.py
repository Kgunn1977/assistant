r"""The envelope catalog: sender, subject and date (never the body) of every message in the look-back span, from every
connected account, so a look-back is a local search and not a slow one at the mail service.

Built once at setup (the setup cards, onboard.py), inside the 15-minute pass: each pass builds a portion, picking up where
the last one stopped, until every account is done. No new message is pulled in until it is built (gather.py, textlink.py,
mail.py ask holding()). A message's full text is fetched only when a look-back needs it (full_text), and kept beside its
envelope, never as a new message to judge.

A connection type adds itself to the catalog with two optional functions (connections/CONNECTIONS.md):
    envelopes(conn, since, cursor, end) -> {"rows": [...], "cursor": str or None, "done": bool}
        each row {"provider_id", "ts", "direction" in|out, "from_key", "from_name", "to", "subject", "thread_id"}
    envelope_text(conn, provider_id) -> the message's plain text
A type without envelopes() reaches back only as far as it downloads (texts and other channels may): the catalog says so.

    start(since)            begin a catalog for the span from that date (the setup card's answer)
    building()              True while a catalog was started and is not built yet
    step(pass_id, end)      build a portion until time end; returns a plain line
    progress()              {"accounts": [...], "total", "done", "left_minutes" (an estimate), ...}
    search(from_key=, words=, most=)   envelopes, newest first
    full_text(env_id)       the message's text, fetched once when a look-back needs it
"""
import datetime as dt
import json
import os
import re
import time

import common
import db

STATE = os.path.join(common.paths.STATE, "catalog.json")
DDL = """
CREATE SEQUENCE IF NOT EXISTS seq_envelope START 1;
CREATE TABLE IF NOT EXISTS envelopes (
  id          BIGINT PRIMARY KEY DEFAULT nextval('seq_envelope'),
  kind        VARCHAR NOT NULL,
  account     VARCHAR NOT NULL,
  conn_id     VARCHAR,
  provider_id VARCHAR NOT NULL,
  ts          TIMESTAMP NOT NULL,
  direction   VARCHAR NOT NULL,
  from_key    VARCHAR,
  from_name   VARCHAR,
  to_keys     VARCHAR,
  subject     VARCHAR,
  thread_id   VARCHAR,
  body        VARCHAR,
  fetched_at  TIMESTAMP,
  UNIQUE (kind, account, provider_id)
);
"""
ADDRESS = re.compile(r"[a-z0-9._%+'=-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+")
# a rough rate for the time-left estimate before any account has reported its own (Gmail's is the slowest)
FIRST_GUESS_PER_MINUTE = 600


def ensure(con=None):
    if con is not None:
        con.execute(DDL)
        return
    db.execute(DDL)


def state():
    return common.read_json(STATE, {}) or {}


def _save(st):
    common.write_json(STATE, st)


def start(since):
    """Begin (or begin again) a catalog of the span from `since` (a date) to now. Accounts connected later join it."""
    st = state()
    st.update({"since": str(since)[:10], "started": common.now().isoformat(timespec="seconds"), "built_at": None})
    st.setdefault("accounts", {})
    for a in st["accounts"].values():
        a.update(done=False, cursor=None)
    _save(st)
    ensure()
    return st


def started():
    return bool(state().get("since"))


def built():
    return bool(state().get("built_at"))


def building():
    st = state()
    return bool(st.get("since")) and not st.get("built_at")


def _accounts():
    """Every connection that is on, with its module: (conn, module, has envelopes)."""
    import connections
    out = []
    for c in connections.listed():
        try:
            mod = connections.module(c["type"])
        except KeyError:
            continue
        if getattr(mod, "KIND", "") == "calendar":
            continue                # a calendar has no envelopes: it is read as it stands
        out.append((c, mod, hasattr(mod, "envelopes")))
    return out


def _label(c):
    return c.get("label") or c.get("address") or c["id"]


def _key(kind, value):
    v = str(value or "").strip().lower()
    if not v:
        return None
    if ":" in v and not ADDRESS.fullmatch(v):
        return v                    # already a key (sms:..., phone:..., a chat user's id)
    return f"{'email' if kind == 'email' else kind}:{v}"


def _store(c, mod, rows):
    """Keep the rows; one already held is skipped. Returns how many were new."""
    if not rows:
        return 0
    account = str(c.get("address") or c.get("label") or c["id"]).lower()
    kind = getattr(mod, "KIND", "email")
    con = db.connect()
    try:
        ensure(con)
        n0 = con.execute("SELECT count(*) FROM envelopes WHERE account=? AND kind=?", (account, kind)).fetchone()[0]
        for r in rows:
            ts = r.get("ts")
            if isinstance(ts, str):
                try:
                    ts = dt.datetime.fromisoformat(ts[:19])
                except ValueError:
                    continue
            if not isinstance(ts, dt.datetime) or not r.get("provider_id"):
                continue
            to = r.get("to") or []
            if isinstance(to, str):
                to = ADDRESS.findall(to.lower()) or [x.strip() for x in to.split(",") if x.strip()]
            con.execute("INSERT INTO envelopes (kind, account, conn_id, provider_id, ts, direction, from_key, from_name, to_keys,"
                        " subject, thread_id) VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                        (kind, account, c["id"], str(r["provider_id"]), ts, "out" if r.get("direction") == "out" else "in",
                         _key(kind, r.get("from_key")), " ".join(str(r.get("from_name") or "").split())[:200] or None,
                         json.dumps([str(x).lower() for x in to][:50]), " ".join(str(r.get("subject") or "").split())[:500],
                         r.get("thread_id")))
        return con.execute("SELECT count(*) FROM envelopes WHERE account=? AND kind=?", (account, kind)).fetchone()[0] - n0
    finally:
        con.close()


def step(pass_id, end):
    """Build a portion of the catalog until time `end` (a time.time()). Each account goes on from its own cursor; an account
    that fails is said and tried again next pass. When every account is done the catalog is built: each mail account's
    place is set to the start of today, so the first gathering brings in today's mail and not the whole span again."""
    st = state()
    if not st.get("since") or st.get("built_at"):
        return ""
    since = dt.date.fromisoformat(st["since"])
    accts = st.setdefault("accounts", {})
    said, trouble = [], []
    for c, mod, can in _accounts():
        a = accts.setdefault(c["id"], {"label": _label(c), "kind": getattr(mod, "KIND", ""), "count": 0, "done": False,
                                        "cursor": None, "secs": 0.0})
        a["label"], a["kind"] = _label(c), getattr(mod, "KIND", "")
        if a.get("done"):
            continue
        if not can:
            a.update(done=True, reach="as far as it downloads")
            said.append(f"{a['label']}: reaches back only as far as it downloads")
            continue
        if time.time() >= end:
            break
        t0 = time.time()
        try:
            got = mod.envelopes(c, since, a.get("cursor"), end) or {}
            n = _store(c, mod, got.get("rows") or [])
            a["count"] = int(a.get("count") or 0) + n
            a["cursor"] = got.get("cursor")
            a["done"] = bool(got.get("done"))
            if got.get("total"):
                a["total"] = int(got["total"])
            a.pop("problem", None)
            said.append(f"{a['label']}: {a['count']} envelope(s)" + ("" if a["done"] else ", going on"))
        except Exception as e:  # noqa: BLE001  one account's trouble never stops the others; it is tried again next pass
            import keys
            a["problem"] = keys.scrub(f"{type(e).__name__}: {e}")[:300]
            trouble.append(f"{a['label']}: {a['problem']}")
        a["secs"] = round(float(a.get("secs") or 0) + time.time() - t0, 1)
        _save(st)
    left = [x for x in accts.values() if not x.get("done")]
    if not left and accts is not None:
        st["built_at"] = common.now().isoformat(timespec="seconds")
        _start_places()
        said.append("catalog built")
    _save(st)
    return "catalog: " + "; ".join(said + [f"PROBLEM {t}" for t in trouble]) if said or trouble else "catalog: nothing connected yet"


def _start_places():
    """Each mail account with no place of its own starts today: the first gathering after the catalog is today's mail."""
    import connections
    today = dt.datetime.combine(dt.date.today(), dt.time())
    for c in connections.listed("email"):
        name = f"email:{str(c.get('address') or '').lower()}"
        if c.get("address") and db.watermark(name) is None:
            db.set_watermark(name, today)


def progress():
    """Where the catalog stands, for the progress card: each account's count and whether it is done, the total, and an
    estimate of the minutes left (from each account's own pace, or a rough first guess)."""
    st = state()
    accts = []
    left_min = 0.0
    for cid, a in (st.get("accounts") or {}).items():
        accts.append({"id": cid, "label": a.get("label"), "kind": a.get("kind"), "count": a.get("count", 0),
                      "done": bool(a.get("done")), "reach": a.get("reach"), "problem": a.get("problem")})
        if not a.get("done"):
            rate = (a.get("count") or 0) / max(1.0, float(a.get("secs") or 0)) * 60 or FIRST_GUESS_PER_MINUTE
            total = a.get("total") or max((a.get("count") or 0) * 2, 3000)
            left_min = max(left_min, max(0, total - (a.get("count") or 0)) / rate)
    return {"since": st.get("since"), "started": st.get("started"), "built_at": st.get("built_at"), "accounts": accts,
            "total": sum(x["count"] or 0 for x in accts), "done": built(),
            "left_minutes": 0 if built() else max(1, round(left_min))}


def search(from_key=None, words=None, most=20, con=None, kind=None):
    """Envelopes from or to this person, or whose subject holds these words, newest first: [dict]."""
    where, args = [], []
    if from_key:
        k = str(from_key).lower()
        bare = k.split(":", 1)[1] if ":" in k else k
        where.append("(lower(from_key) = ? OR to_keys LIKE ?)")
        args += [k, f'%"{bare}"%']
    for w in [w for w in re.findall(r"[a-z0-9']{4,}", str(words or "").lower())][:6]:
        where.append("lower(subject) LIKE ?")
        args.append(f"%{w}%")
    if kind:
        where.append("kind = ?")
        args.append(kind)
    sql = ("SELECT id, kind, account, provider_id, ts, direction, from_key, from_name, to_keys, subject, thread_id, body IS NOT NULL"
           " FROM envelopes" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY ts DESC LIMIT ?")
    args.append(int(most))
    try:
        rows = (con.execute(sql, args).fetchall() if con is not None else db.query(sql, tuple(args)))
    except Exception:  # noqa: BLE001  no catalog yet: nothing found
        return []
    keys = ("id", "kind", "account", "provider_id", "ts", "direction", "from_key", "from_name", "to_keys", "subject", "thread_id", "has_text")
    return [dict(zip(keys, r)) for r in rows]


def full_text(env_id):
    """The message's text: kept from an earlier fetch, else fetched now from its account (envelope_text) and kept beside its
    envelope. None when its account cannot give it."""
    got = db.query("SELECT conn_id, provider_id, body FROM envelopes WHERE id=?", (int(env_id),))
    if not got:
        return None
    conn_id, pid, body = got[0]
    if body is not None:
        return body
    import connections
    c = connections.get(conn_id)
    if not c:
        return None
    mod = connections.module(c["type"])
    if not hasattr(mod, "envelope_text"):
        return None
    text = str(mod.envelope_text(c, pid) or "")[:20000]
    db.execute("UPDATE envelopes SET body=?, fetched_at=? WHERE id=?", (text, common.now(), int(env_id)))
    return text


def people(con):
    """Everyone in the catalog, with their counts: {key: {"name", "first", "last", "in", "out", "kinds"}} (contacts)."""
    out = {}
    try:
        rows = con.execute("SELECT kind, direction, from_key, from_name, to_keys, ts FROM envelopes").fetchall()
    except Exception:  # noqa: BLE001
        return out
    for kind, direction, fk, name, to, ts in rows:
        if direction == "in" and fk:
            keys = [(fk, name)]
        else:
            try:
                keys = [(_key(kind, x), None) for x in json.loads(to or "[]")]
            except ValueError:
                keys = []
        for k, nm in keys:
            if not k:
                continue
            p = out.setdefault(k, {"name": None, "first": ts, "last": ts, "in": 0, "out": 0, "kinds": set()})
            p["name"] = p["name"] or nm
            p["first"], p["last"] = min(p["first"], ts), max(p["last"], ts)
            p["in" if direction == "in" else "out"] += 1
            p["kinds"].add(kind)
    return out
