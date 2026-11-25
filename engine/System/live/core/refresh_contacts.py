"""Keep the identity graph current.

    python refresh_contacts.py            # add/refresh, then relink messages
    python refresh_contacts.py --dry-run

The owner's own addresses are contacts (person 1); a chat service's users are keyed by
user id and merged onto the person already known by display name or email. Every contact
is tracked (the owner, 11/25: "EVERY contact is tracked"): everyone he ever wrote to or heard
from, in mail, texts or any other channel connected, one-time senders included; everyone in the
setup's history catalog (catalog.py); and everyone in his phone's and his mail accounts' own
address books, each book entry's addresses and numbers kept as one person.
"""

import argparse
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # System\live
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                    # System\live\core
import db  # noqa: E402
import paths  # noqa: E402


def paths_channels():
    import common
    return common.channels()


def id_people():
    """{kind: {id: {"name", "email", "is_bot", "deleted"}}}: real names for the people a kind of connection knows by id (a chat
    service's users), so its messages can name their author."""
    try:
        import connections
        kinds = sorted({getattr(t, "KIND", "") for t in connections.types().values() if hasattr(t, "people")} - {""})
        return {k: got for k in kinds for got in [connections.people(k)] if got}
    except Exception:
        return {}


def address_books():
    """[(book, [{"name", "emails", "phones"}])]: his phone's contacts as Google Messages names them (textlink.phone_book) and
    each mail account's own address book (a connection type's address_book()). Asked before the database is opened; a book
    that cannot be read is said and left out."""
    out = []
    try:
        import common
        got = (common.read_json(os.path.join(common.paths.STATE, "phone_book.json"), {}) or {}).get("people") or []
        if got:
            out.append(("phone", [{"name": p.get("name"), "emails": [], "phones": [p.get("number")]} for p in got]))
    except Exception as e:  # noqa: BLE001
        print(f"phone book not read: {type(e).__name__}")
    try:
        import connections
        for c in connections.listed():
            mod = connections.module(c["type"])
            if not hasattr(mod, "address_book"):
                continue
            try:
                out.append((c.get("label") or c["id"], mod.address_book(c) or []))
            except Exception as e:  # noqa: BLE001  no permission yet, or the service said no: this book waits
                import keys
                print(f"address book of {c.get('label') or c['id']} not read: " + keys.scrub(f"{type(e).__name__}: {e}")[:200])
    except Exception as e:  # noqa: BLE001
        print(f"address books not read: {type(e).__name__}")
    return out


def _phone_key(number):
    digits = "".join(ch for ch in str(number or "") if ch.isdigit())
    return "phone:" + digits[-10:] if len(digits) >= 10 else None


def _add(con, key, name, source, now, pid=None, first=None, last=None):
    con.execute("INSERT INTO contacts (key, person_id, name, name_source, first_seen, last_seen, sent_count, updated_at)"
                " VALUES (?,?,?,?,?,?,0,?) ON CONFLICT DO NOTHING",
                (key, pid or db.new_person_id(con), name, source, first or now, last or now, now))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    now = dt.datetime.now()
    added = merged = 0

    known = id_people()         # asked of the services before the database is opened: never held across the network
    books = address_books()
    con = db.connect()
    try:
        # ---- 1. the owner, on every address they own ---------------------
        for acct in paths.accounts():
            key = f"email:{acct}"
            if not con.execute("SELECT 1 FROM contacts WHERE key=?", [key]).fetchone():
                if not args.dry_run:
                    con.execute(
                        "INSERT INTO contacts (key, person_id, name, name_source,"
                        " company, first_seen, last_seen, sent_count, notes, updated_at)"
                        " VALUES (?,?,?,'self',NULL,?,?,0,'the owner''s own mailbox',?)",
                        (key, 1, paths.owner_name(), now, now, now))
                added += 1

        # ---- 2. id-keyed contacts (a chat service's users), merged onto the name-keyed ones --
        for kind, uid, info in ((k, u, i) for k, us in known.items() for u, i in us.items()):
            key = f"{kind}:{uid}"
            if con.execute("SELECT 1 FROM contacts WHERE key=?", [key]).fetchone():
                continue
            # reuse the person already known under '<kind>:Display Name',
            # or an email match, so this does not create a second owner
            pid = None
            if info.get("name"):
                row = con.execute("SELECT person_id FROM contacts WHERE key=?",
                                  [f"{kind}:{info['name']}"]).fetchone()
                if row:
                    pid = row[0]
                    merged += 1
            if pid is None and info.get("email"):
                row = con.execute("SELECT person_id FROM contacts WHERE key=?",
                                  [f"email:{info['email']}"]).fetchone()
                if row:
                    pid = row[0]
                    merged += 1
            if pid is None:
                pid = db.new_person_id(con)
            if not args.dry_run:
                con.execute(
                    "INSERT INTO contacts (key, person_id, name, name_source, company,"
                    " first_seen, last_seen, sent_count, notes, updated_at)"
                    " VALUES (?,?,?,?,NULL,?,?,0,?,?)",
                    (key, pid, info.get("name"), f"{kind}_users_list", now, now,
                     "deactivated" if info.get("deleted") else None, now))
            added += 1

        # ---- 3. Real email correspondents ---------------------------------
        # the owner wrote to them, or they wrote more than once; a To address
        # is read out of its display-name form before it is compared.
        candidates = con.execute("""
            WITH inbound AS (
                SELECT from_key AS k, count(*) AS n FROM messages
                WHERE channel='email' AND direction='in' AND from_key IS NOT NULL
                GROUP BY 1
            ), outbound AS (
                SELECT DISTINCT unnest(regexp_extract_all(lower(to_keys),
                       '[a-z0-9][a-z0-9._%+=''-]*@[a-z0-9-]+(?:\\.[a-z0-9-]+)+')) AS addr
                FROM messages WHERE channel='email' AND direction='out'
                  AND to_keys IS NOT NULL
            ), everyone AS (
                SELECT i.k, i.n,
                       EXISTS (SELECT 1 FROM outbound o
                               WHERE o.addr = replace(i.k, 'email:', '')) AS wrote_back
                FROM inbound i
                UNION ALL
                SELECT 'email:' || o.addr, 0, TRUE FROM outbound o
                WHERE NOT EXISTS (SELECT 1 FROM inbound i
                                  WHERE i.k = 'email:' || o.addr)
            )
            SELECT e.k, e.n, e.wrote_back
            FROM everyone e
            LEFT JOIN contacts c ON c.key = e.k
            WHERE c.key IS NULL
        """).fetchall()
        for key, n, wrote_back in candidates:
            if "/o=exchangelabs" in key:      # unusable X500 form, not an address
                continue
            if not args.dry_run:
                con.execute(
                    "INSERT INTO contacts (key, person_id, name, name_source,"
                    " first_seen, last_seen, sent_count, updated_at)"
                    " VALUES (?,?,NULL,'seen_in_mail',?,?,0,?)",
                    (key, db.new_person_id(con), now, now, now))
            added += 1

        # ---- 3b. Every other channel: whoever wrote, and whoever he wrote to there ----
        others = con.execute("""
            SELECT DISTINCT k, ch FROM (
                SELECT from_key AS k, channel AS ch FROM messages
                WHERE channel NOT IN ('email', 'calendar') AND direction = 'in' AND from_key IS NOT NULL
                UNION ALL
                SELECT to_keys, channel FROM messages
                WHERE channel NOT IN ('email', 'calendar') AND direction = 'out' AND to_keys LIKE '%:%' AND to_keys NOT LIKE '%,%'
                  AND to_keys NOT LIKE '[%')
            WHERE k NOT IN (SELECT key FROM contacts)""").fetchall()
        for key, ch in others:
            if not args.dry_run:
                _add(con, key, None, f"seen_in_{ch}", now)
            added += 1

        # ---- 3c. Everyone in the history catalog (the setup's envelopes) ----
        try:
            import catalog
            for key, p in catalog.people(con).items():
                if "/o=exchangelabs" in key or con.execute("SELECT 1 FROM contacts WHERE key=?", [key]).fetchone():
                    continue
                if not args.dry_run:
                    _add(con, key, p.get("name"), "seen_in_history", now, first=p.get("first"), last=p.get("last"))
                added += 1
        except Exception as e:  # noqa: BLE001  no catalog: nothing from it
            print(f"history catalog not read: {type(e).__name__}")

        # ---- 3d. His own address books: each entry is one person, all its addresses and numbers ----
        for book, entries in books:
            for e in entries:
                keys = [f"email:{a}" for a in e.get("emails") or []] + [_phone_key(n) for n in e.get("phones") or []]
                keys = [k for k in dict.fromkeys(keys) if k]
                if not keys:
                    continue
                known = [r[0] for k in keys for r in con.execute("SELECT person_id FROM contacts WHERE key=?", [k]).fetchall()]
                pid = known[0] if known else None
                for k in keys:
                    row = con.execute("SELECT name FROM contacts WHERE key=?", [k]).fetchone()
                    if args.dry_run:
                        added += row is None
                        continue
                    if row is None:
                        pid = pid or db.new_person_id(con)
                        _add(con, k, e.get("name") or None, f"address_book:{book}", now, pid=pid)
                        added += 1
                    elif not row[0] and e.get("name"):
                        con.execute("UPDATE contacts SET name=?, name_source=?, updated_at=? WHERE key=?",
                                    (e["name"], f"address_book:{book}", now, k))

        # ---- 4. Relink every message that now has a resolvable identity ----
        if not args.dry_run:
            con.execute("""
                UPDATE messages SET person_id = c.person_id
                FROM contacts c
                WHERE messages.person_id IS NULL
                  AND c.key = coalesce(messages.from_key, messages.to_keys)
            """)
        totals = {
            ch: con.execute(
                "SELECT count(*), count(*) FILTER (WHERE person_id IS NULL)"
                " FROM messages WHERE channel=?", [ch]).fetchone()
            for ch in sorted(set(paths_channels()) - {"calendar"})
        }
        contact_total = con.execute("SELECT count(*) FROM contacts").fetchone()[0]
        people_total = con.execute(
            "SELECT count(DISTINCT person_id) FROM contacts").fetchone()[0]
    finally:
        con.close()

    print(f"contacts: +{added} added ({merged} merged onto a person already known)"
          + ("  (dry run)" if args.dry_run else ""))
    print(f"          {contact_total} keys covering {people_total} people")
    for ch, (tot, unl) in totals.items():
        print(f"   {ch}: {tot - unl}/{tot} attributed to a person")
    return 0


if __name__ == "__main__":
    sys.exit(main())
