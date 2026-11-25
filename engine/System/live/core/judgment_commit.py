"""Commit a judgment pass, or refuse the whole thing.

    python judgment_commit.py verdicts.json --run-id RUN
    python judgment_commit.py verdicts.json --dry-run

The session reads a payload, applies the rules, and writes a verdicts file.
This script is the gate between that reasoning and the database.

WHAT IS CHECKED BEFORE ANYTHING IS WRITTEN
  coverage      every message in the payload has exactly one verdict
  real ids      every cited message id exists
  closes        no task closes without deterministic evidence
  shapes        areas are the owner's own; keys are unique
  no re-asking  nothing already settled in `answered` is raised again

A single failure aborts the commit, and the writes run in one transaction, so
a refused or failed pass leaves the database exactly as it was.

VERDICT FORMAT, one entry per message:
  {"id": 123, "disposition": "noise|phishing|task|evidence|ignore",
   "reason": "why, in a few words",
   "task": {...}          when disposition is task
   "evidence_for": "item_key", "proves": "..."   when disposition is evidence
   "covered": true|false, "leaned_on": "rule id or a few words"   optional
  }
covered=false says no rule decided the message and the call is the judge's own
best guess (its reason); a verdict without it counts as covered. Both are kept
on the message's row in `answered`.
Optional alongside: "task_updates" (status changes on existing tasks) and
"contacts_seen".
"""

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # System\live
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                    # System\live\core
import db  # noqa: E402
import paths  # noqa: E402
from validate import ContractViolation, Validator  # noqa: E402

DISPOSITIONS = {"noise", "phishing", "task", "evidence", "ignore"}
CLOSING = {"done", "dismissed"}
URGENCIES = {"urgent", "normal"}


def areas():
    """The areas a task may carry: the owner's own, from their settings."""
    return {a for a in paths.personal().get("areas") or [] if a} or {"Personal", "System"}


def cross_cited(key, mid, founded):
    """The other item a message belongs to, when citing it on `key` would
    tie two unrelated items together; None when the citation is fine."""
    home = founded.get(mid)
    if home == key:
        return None
    if not home:
        other = db.query("""SELECT t.item_key FROM task_refs r JOIN tasks t ON t.id = r.task_id
                             WHERE r.ref_type = 'message' AND r.value = ? AND t.item_key <> ?
                             LIMIT 1""", (mid, key))
        home = other[0][0] if other else None
    if not home:
        return None
    msg = db.query("SELECT thread_id, from_key, direction FROM messages WHERE CAST(id AS VARCHAR) = ?",
                   (mid,))
    if not msg or msg[0][2] == "out":
        return None
    thread, sender = msg[0][0], msg[0][1]
    own = db.query("""SELECT m.thread_id, m.from_key FROM task_refs r
                        JOIN tasks t ON t.id = r.task_id
                        JOIN messages m ON CAST(m.id AS VARCHAR) = r.value
                        WHERE r.ref_type = 'message' AND t.item_key = ? AND r.value <> ?""",
                   (key, mid))
    own += [(m[0], m[1]) for m in db.query(
        """SELECT thread_id, from_key FROM messages WHERE CAST(id AS VARCHAR) IN (
             SELECT k FROM (SELECT unnest(?) AS k))""",
        ([i for i, h in founded.items() if h == key and i != mid],))] if any(
        h == key for h in founded.values()) else []
    if not own:
        return None
    for t, f in own:
        if (thread is not None and t == thread) or (sender and f == sender):
            return None
    return home


def evidence_targets(x):
    """evidence_for is one item key or a list of them."""
    ev = x.get("evidence_for")
    if not ev:
        return []
    keys = [ev] if isinstance(ev, str) else list(ev)
    return [k.strip() for k in keys if k and k.strip()]


LEANED_MAX = 200


def leaned_on(x):
    """The rule or words the verdict leaned on, as stored text (None when not given). A rule id may come as a
    number, several as a list. Raises ValueError for anything else."""
    lo = x.get("leaned_on")
    if lo is None:
        return None
    parts = lo if isinstance(lo, list) else [lo]
    if any(isinstance(p, bool) or not isinstance(p, (str, int)) for p in parts):
        raise ValueError(f"leaned_on must be a rule id or a few words, not {lo!r}")
    text = "; ".join(" ".join(str(p).split()) for p in parts if str(p).strip())
    return text[:LEANED_MAX] or None


COVERAGE_COLUMNS = ("ALTER TABLE answered ADD COLUMN IF NOT EXISTS covered BOOLEAN",
                    "ALTER TABLE answered ADD COLUMN IF NOT EXISTS leaned_on VARCHAR")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("verdicts")
    ap.add_argument("--payload", help="defaults to the payload named in the verdicts")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--run-id")
    args = ap.parse_args()

    with open(args.verdicts, encoding="utf-8") as f:
        v = json.load(f)
    payload_path = args.payload or v.get("payload")
    with open(payload_path, encoding="utf-8") as f:
        payload = json.load(f)

    owed = [m["id"] for m in payload["messages"]]
    # the checks below only read, through one connection: an open per citation cost about a second each (db.start_reading)
    db.start_reading()
    val = Validator(args.run_id or "judgment")
    allowed_areas = areas()

    # {"ids": [...]} covers several messages of one conversation with one
    # noise or ignore ruling; expanded here to one verdict per message.
    conv_of = {m["id"]: m.get("conv") for m in payload["messages"]}
    verdicts = []
    for x in v.get("verdicts", []):
        ids = x.get("ids")
        if ids is None:
            verdicts.append(x)
            continue
        if x.get("disposition") not in ("noise", "ignore"):
            val.failures.append(f"grouped verdict {ids[:5]}: only noise or "
                                "ignore may cover several messages")
        convs = {conv_of.get(i) for i in ids}
        if len(convs) != 1 or None in convs:
            val.failures.append(f"grouped verdict {ids[:5]}: messages are "
                                "not all one conversation")
        for i in ids:
            verdicts.append({k: x[k] for k in x if k != "ids"} | {"id": i})

    # --- coverage: exactly one verdict per message ------------------------
    judged = [x.get("id") for x in verdicts]
    val.check_coverage(owed, judged)
    dupes = [i for i in set(judged) if judged.count(i) > 1]
    if dupes:
        val.failures.append(f"duplicate verdicts for messages {dupes[:10]}")
    strays = [i for i in judged if i not in set(owed)]
    if strays:
        val.failures.append(f"verdicts for messages not in the payload: {strays[:10]}")

    # --- shapes -----------------------------------------------------------
    for x in verdicts:
        d = x.get("disposition")
        if d not in DISPOSITIONS:
            val.failures.append(f"message {x.get('id')}: unknown disposition {d!r}")
        if not (x.get("reason") or "").strip():
            val.failures.append(f"message {x.get('id')}: no reason given")
        if "covered" in x and not isinstance(x["covered"], bool):
            val.failures.append(f"message {x.get('id')}: covered is {x['covered']!r}; it is"
                                " true or false (false: no rule decides it, the reason is your best guess)")
        try:
            leaned_on(x)
        except ValueError as e:
            val.failures.append(f"message {x.get('id')}: {e}")
        if d == "task":
            t = x.get("task") or {}
            for field in ("item_key", "area", "title"):
                if not (t.get(field) or "").strip():
                    val.failures.append(f"message {x.get('id')}: task missing {field}")
            if t.get("area") and t["area"] not in allowed_areas:
                val.failures.append(
                    f"message {x.get('id')}: unknown area {t['area']!r}; the areas"
                    f" are {', '.join(sorted(allowed_areas))}")
            # judgment ranks (rule 420): every task carries an urgency
            u = t.get("urgency", "normal")
            if u not in URGENCIES:
                val.failures.append(
                    f"message {x.get('id')}: urgency {u!r} is not "
                    f"{' or '.join(sorted(URGENCIES))}")
            if u == "urgent" and not (t.get("urgency_reason") or "").strip():
                val.failures.append(
                    f"message {x.get('id')}: urgent with no urgency_reason. "
                    "The bar is a consequence today or tomorrow AND the owner "
                    "having to act; say which.")
        if d == "evidence" and not evidence_targets(x):
            val.failures.append(f"message {x.get('id')}: evidence with no task named")

    val.check_ids_real("messages", judged)

    # --- closes need evidence ----------------------------------------------
    updates = v.get("task_updates", [])
    closes = [(u.get("item_key"), u.get("evidence"))
              for u in updates if u.get("status") in CLOSING]
    val.check_close_evidence(closes)
    for u in updates:
        cited = u.get("evidence_message_ids") or []
        val.check_ids_real("messages", cited)
        if u.get("status") in CLOSING and not cited and not u.get("owner_said"):
            val.failures.append(
                f"{u.get('item_key')}: closing needs a cited message or the owner's word")

    # --- updates and evidence must name items that exist ------------------
    known = {r[0] for r in db.query("SELECT item_key FROM tasks")}
    new_task_keys = {(x.get("task") or {}).get("item_key")
                     for x in verdicts if x.get("disposition") == "task"}
    STATUSES = {"needs_me", "waiting_them", "done", "dismissed"}
    # a compaction that is empty, or longer than what it replaces, is not a
    # compaction; refusing the whole commit is how stored history stays safe
    current_detail = {r[0]: (r[1] or "") for r in db.query(
        "SELECT item_key, detail FROM tasks")}
    # an update with no status keeps the item's current status
    current_status = {r[0]: r[1] for r in db.query(
        "SELECT item_key, status FROM tasks")}
    current_urgency = {r[0]: r[1] for r in db.query(
        "SELECT item_key, urgency FROM tasks")}
    filled = 0
    for u in updates:
        if "status" not in u and u.get("item_key") in current_status:
            u["status"] = current_status[u["item_key"]]
            filled += 1
    if filled:
        print(f"   task updates: {filled} without status, kept at current status")
    for u in updates:
        if u.get("item_key") not in known:
            val.failures.append(
                f"task update names an item that does not exist: {u.get('item_key')!r}")
        if u.get("status") not in STATUSES:
            val.failures.append(
                f"{u.get('item_key')}: unknown status {u.get('status')!r}")
        # urgency belongs to a status: a moved urgent item restates it
        if (u.get("item_key") in current_status
                and u.get("status") != current_status[u["item_key"]]
                and current_urgency.get(u["item_key"]) == "urgent"
                and "urgency" not in u):
            val.failures.append(
                f"{u.get('item_key')}: moves an urgent item to "
                f"{u.get('status')!r} without restating urgency; set "
                f"urgency (and urgency_reason when urgent)")
        if "detail_rewrite" in u:
            rw = (u.get("detail_rewrite") or "").strip()
            old = current_detail.get(u.get("item_key"), "")
            if not rw:
                val.failures.append(
                    f"{u.get('item_key')}: detail_rewrite is empty")
            elif len(rw) >= len(old):
                val.failures.append(
                    f"{u.get('item_key')}: detail_rewrite is {len(rw)} chars "
                    f"against an existing {len(old)}; a rewrite must be shorter")
    for x in verdicts:
        if x.get("disposition") != "evidence":
            continue
        for key in evidence_targets(x):
            if key not in known and key not in new_task_keys:
                val.failures.append(
                    f"message {x.get('id')}: evidence for unknown item {key!r}")

    # --- a message is cited only on the items it is about ------------------
    # A message that founded its own item, or is already cited on another one,
    # once printed under an unrelated item it was only loosely connected to.
    # Such a message may be cited on a further item only when it shares a
    # conversation or a sender with that item's own messages; otherwise it is
    # named in the text, not cited.
    founded = {}
    for x in verdicts:
        if x.get("disposition") == "task" and (x.get("task") or {}).get("item_key"):
            founded[str(x.get("id"))] = x["task"]["item_key"]
    citations = [(u.get("item_key"), m, "task update")
                 for u in updates for m in (u.get("evidence_message_ids") or [])]
    citations += [(k, x.get("id"), "evidence verdict")
                  for x in verdicts if x.get("disposition") == "evidence"
                  for k in evidence_targets(x)]
    for key, mid, how in citations:
        if mid is None or not key:
            continue
        unrelated = cross_cited(key, str(mid), founded)
        if unrelated:
            val.failures.append(
                f"{key}: {how} cites message {mid}, which belongs to {unrelated} "
                "and shares no conversation or sender with this item's messages; "
                "say what it changes in the detail text and drop the citation")

    # --- nothing already settled may be raised again ----------------------
    settled = {(r[0], r[1]) for r in db.query(
        "SELECT domain, key FROM answered WHERE domain <> 'judged'")}
    for x in verdicts:
        t = (x.get("task") or {}).get("item_key")
        if t and ("question", t) in settled:
            val.failures.append(f"{t}: already asked and answered; do not re-raise")

    db.stop_reading()
    try:
        val.raise_if_failed()
    except ContractViolation as e:
        print("COMMIT REFUSED\n")
        print(e)
        db.record_source_status(args.run_id, "judgment", "failed", str(e))
        return 1

    counts = {d: sum(1 for x in verdicts if x.get("disposition") == d)
              for d in DISPOSITIONS}
    print(f"contract passed: {len(verdicts)} verdicts covering {len(owed)} messages")
    for d, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        if n:
            print(f"   {d}: {n}")
    uncovered = sum(1 for x in verdicts if x.get("covered") is False)
    if uncovered:
        print(f"   not covered by a rule (best guess): {uncovered}")
    rewrites = sum(1 for u in updates if u.get("detail_rewrite"))
    print(f"   task updates: {len(updates)}"
          + (f" ({rewrites} detail compacted)" if rewrites else ""))

    if args.dry_run:
        print("\n(dry run: nothing written)")
        return 0

    now = dt.datetime.now()
    with db.transaction() as con:
        for ddl in COVERAGE_COLUMNS:        # a home laid down before the columns gets them here (schema.sql has them too)
            con.execute(ddl)
        created = updated = 0
        # phase 1: every task first, so evidence can cite a task raised in
        # this same pass
        for x in verdicts:
            if x.get("disposition") == "task":
                t = x["task"]
                row = con.execute("SELECT id FROM tasks WHERE item_key=?",
                                  [t["item_key"]]).fetchone()
                if row:
                    con.execute(
                        "UPDATE tasks SET last_seen=?, updated_at=?,"
                        " detail=coalesce(?, detail) WHERE id=?",
                        (now.date(), now, t.get("detail"), row[0]))
                    task_id = row[0]
                    updated += 1
                else:
                    task_id = con.execute(
                        "INSERT INTO tasks (item_key, kind, area, title, detail,"
                        " status, due_date, checkback_date, urgency,"
                        " urgency_reason, first_seen, last_seen,"
                        " created_at, updated_at)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id",
                        (t["item_key"], t.get("kind", "task"), t["area"],
                         t["title"], t.get("detail"), t.get("status", "needs_me"),
                         t.get("due_date"), t.get("checkback_date"),
                         t.get("urgency", "normal"), t.get("urgency_reason"),
                         now.date(), now.date(), now, now)).fetchone()[0]
                    created += 1
                # every task carries the message it came from
                con.execute(
                    "INSERT INTO task_refs (task_id, kind, ref_type, value, role,"
                    " noted_at) VALUES (?,'source','message',?,?,?)",
                    (task_id, str(x["id"]), "raised_by", now))

            elif x.get("disposition") == "phishing":
                m = next(mm for mm in payload["messages"] if mm["id"] == x["id"])
                pid = con.execute("SELECT provider_id FROM messages WHERE id=?",
                                  (x["id"],)).fetchone()
                con.execute(
                    "INSERT INTO junk_deleted (channel, account, provider_id,"
                    " from_address, subject, msg_ts, reason, action, note, deleted_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (m["channel"], m["account"], pid[0] if pid else None,
                     m.get("from"), m.get("subject"), m.get("ts"), x["reason"],
                     "flagged", "queued for deletion by judgment", now))

            # every message, whatever the verdict, is marked judged: this is
            # what makes the next run's coverage check meaningful. covered
            # and leaned_on go with it: NULL (not said) counts as covered
            con.execute(
                "INSERT INTO answered (domain, key, verdict, source, answered_at,"
                " covered, leaned_on) VALUES ('judged', ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (domain, key) DO UPDATE SET"
                " verdict=excluded.verdict, source=excluded.source,"
                " answered_at=excluded.answered_at, covered=excluded.covered,"
                " leaned_on=excluded.leaned_on",
                (f"msg:{x['id']}", x["disposition"], x["reason"][:200], now,
                 x.get("covered"), leaned_on(x)))

        # phase 2: evidence, now that every task it can point at exists; a
        # missing target refuses the whole commit
        for x in verdicts:
            if x.get("disposition") != "evidence":
                continue
            for key in evidence_targets(x):
                row = con.execute("SELECT id FROM tasks WHERE item_key=?",
                                  [key]).fetchone()
                if not row:
                    raise ContractViolation(
                        f"message {x['id']}: evidence for {key!r}, which does not"
                        " exist even after this pass created its tasks")
                con.execute(
                    "INSERT INTO task_refs (task_id, kind, ref_type, value,"
                    " role, noted_at) VALUES (?,'source','message',?,?,?)",
                    (row[0], str(x["id"]), x.get("proves", "evidence"), now))
                con.execute("UPDATE tasks SET last_seen=?, updated_at=? WHERE id=?",
                            (now.date(), now, row[0]))

        # An update moves an item; resolved_reason is written only on a close.
        # Appended notes carry a date stamp.
        try:
            _d = dt.date.fromisoformat(str(payload.get("days", [])[-1]))
        except Exception:
            _d = now.date()
        stamp = f"[{_d.month}/{_d.day}] "

        for u in updates:
            # a rewrite archives the old detail before replacing it
            if u.get("detail_rewrite"):
                row = con.execute(
                    "SELECT id, detail FROM tasks WHERE item_key=?",
                    [u["item_key"]]).fetchone()
                if row:
                    con.execute(
                        "INSERT INTO task_detail_archive (task_id,"
                        " archived_at, detail, run_id) VALUES (?,?,?,?)",
                        (row[0], now, row[1],
                         args.run_id or os.path.basename(payload_path)))
                    con.execute("UPDATE tasks SET detail=? WHERE id=?",
                                (u["detail_rewrite"], row[0]))

            sets, params = ["status=?", "updated_at=?", "last_seen=?"], \
                           [u["status"], now, now.date()]
            if u["status"] in CLOSING:
                sets.append("resolved_reason=?")
                params.append(u.get("evidence"))
            for field, col in (("due_date", "due_date"),
                               ("checkback_date", "checkback_date"),
                               ("urgency", "urgency"),
                               ("urgency_reason", "urgency_reason")):
                if field in u:
                    sets.append(f"{col}=?")
                    params.append(u[field])
            if u.get("detail_append"):
                sets.append("detail = coalesce(detail || chr(10) || chr(10), '') || ?")
                params.append(stamp + u["detail_append"])
            params.append(u["item_key"])
            con.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE item_key=?",
                        params)
            for mid in (u.get("evidence_message_ids") or []):
                row = con.execute("SELECT id FROM tasks WHERE item_key=?",
                                  [u["item_key"]]).fetchone()
                if row:
                    con.execute(
                        "INSERT INTO task_refs (task_id, kind, ref_type, value,"
                        " role, noted_at) VALUES (?,'source','message',?,?,?)",
                        (row[0], str(mid), u["status"], now))

        db.record_source_status(args.run_id, "judgment", "ok",
                                f"{len(verdicts)} judged, {created} tasks created",
                                con=con)

    print(f"\ncommitted: {created} tasks created, {updated} touched,"
          f" {len(updates)} status changes")
    left = db.query("""
        SELECT count(*) FROM messages m WHERE NOT EXISTS
        (SELECT 1 FROM answered a WHERE a.domain='judged' AND a.key='msg:' || m.id)"""
        )[0][0]
    print(f"messages still unjudged: {left}")

    asked = ask_junk_senders()
    if asked:
        print(f"rule 561: {asked} sender(s) raised on the briefing as junk "
              "or never junk")
    return 0


# --- rule 561: three junk calls in a row, then the owner decides ---------
JUNK_RUN = 3
ASK_KEY = "system::noise rule proposals"


def _escape_literal(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def close_settled_asks(pending) -> None:
    """Close every junk question whose sender no longer waits (answered,
    expired), and the older one card that asked about them all."""
    keep = {f"{ASK_KEY}::{rid}" for rid, _pat in pending}
    con = db.connect()
    try:
        for (key,) in con.execute(
                "SELECT item_key FROM tasks WHERE status='needs_me'"
                " AND (item_key=? OR item_key LIKE ?)",
                [ASK_KEY, ASK_KEY + "::%"]).fetchall():
            if key not in keep:
                con.execute(
                    "UPDATE tasks SET status='done', resolved_reason=?,"
                    " updated_at=now() WHERE item_key=? AND status='needs_me'",
                    ["its sender was answered or expired, or it is asked"
                     " one sender at a time now", key])
    finally:
        con.close()


def ask_junk_senders() -> int:
    """Rule 561: an email sender the judge calls junk 3 times in a row is
    raised in the briefing, and the owner's answer by number puts it on Always
    junk (rules.py confirm) or Never junk (rules.py never). Only the judge's
    own verdicts count; one a rule or an earlier engine's own record settled
    does not. Rule 562 senders, and senders any junk line already covers or
    proposes, are never raised."""
    import rules as rules_mod
    from judgment_payload import junk_guard

    rows = db.query("""
        WITH v AS (
          SELECT lower(m.from_key) fk, a.verdict,
                 row_number() OVER (PARTITION BY lower(m.from_key)
                                    ORDER BY m.ts DESC) rn
          FROM messages m
          JOIN answered a ON a.domain='judged' AND a.key='msg:'||m.id
          WHERE m.direction='in' AND m.channel='email'
            AND a.source NOT LIKE 'rule:%' AND a.source <> 'judged_by_v1'
            AND a.source NOT LIKE 'outbox:%' AND a.source NOT LIKE 'filed:%')
        SELECT fk FROM v WHERE rn <= ?
        GROUP BY fk HAVING count(*) = ? AND bool_and(verdict = 'noise')
        ORDER BY fk""", (JUNK_RUN, JUNK_RUN))
    # settled already (Always or Never junk) or already asked; a "Probably
    # junk" sender is still judged, so it is still asked about
    covered = [e["pattern"] for e in rules_mod.parse("senders") if e["pattern"]
               and (e["status"] == "proposed"
                    or e["section"] in (rules_mod.ALWAYS, rules_mod.NEVER))]
    guarded = junk_guard()
    asked = 0
    for (fk,) in rows:
        if guarded(fk) or any(rules_mod.matches(fk, p) for p in covered):
            continue
        rules_mod.propose("senders", f"marked junk {JUNK_RUN} times in a row",
                          "", rules_mod.ALWAYS, pattern=_escape_literal(fk))
        asked += 1

    pending = [(e["id"], e["pattern"]) for e in rules_mod.parse("senders")
               if e["status"] == "proposed" and e["pattern"]]
    close_settled_asks(pending)
    con = db.connect()
    try:
        # one card per sender, so Junk and Never junk act on exactly the
        # sender the card names; a card is written once and only touched
        # again when its words change, so a pass never shows it as new
        for rid, pat in pending:
            who = pat.split(":", 1)[-1].replace(chr(92), "")
            title = (f"I've marked mail from {who} as junk {JUNK_RUN} times "
                     "in a row. Junk or never junk?")
            detail = (f"I've marked mail from {who} as junk {JUNK_RUN} times "
                      "in a row. Junk puts it on your junk list. Never junk "
                      "means I always read its mail. Until you answer, I keep "
                      "reading each one.")
            con.execute(
                "INSERT INTO tasks (item_key, kind, area, title, detail,"
                " status, urgency, first_seen, last_seen, created_at, updated_at)"
                " VALUES (?, 'task', 'System', ?, ?,"
                " 'needs_me', 'normal', today(), today(), now(), now())"
                " ON CONFLICT (item_key) DO UPDATE SET detail=excluded.detail,"
                " title=excluded.title, last_seen=today(), updated_at=now()"
                " WHERE tasks.status='needs_me' AND (tasks.title IS DISTINCT FROM"
                " excluded.title OR tasks.detail IS DISTINCT FROM excluded.detail)",
                (f"{ASK_KEY}::{rid}", title, detail))
    finally:
        con.close()
    return asked


if __name__ == "__main__":
    sys.exit(main())
