r"""First-time senders, when the owner's setting is "ask me once": one plain card per new sender.

The mail itself is hidden (filters.holds marks it); this makes the one card that asks whether to show
that sender's mail. "Show their mail" puts the sender on "people who always get through" and the held
mail gets its cards at the next pass (held.net); "Hold it" puts them on the ignore list. No Claude.
"""
import json

import card
import common
import filters
import presses


def cards(pass_id):
    """Returns how many asking cards were made."""
    if filters.get()["first_time"] != "ask_once":
        return 0
    import db
    import items
    items.ensure()
    made = 0
    since = common.now().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = db.query(
        """SELECT m.from_key, max(m.id), count(*), max(m.ts), arg_max(m.subject, m.id),
                  (SELECT max(c.name) FROM contacts c WHERE c.key = m.from_key AND c.name IS NOT NULL)
           FROM messages m JOIN answered a ON a.domain='judged' AND a.key = 'msg:' || m.id
           WHERE a.source = 'setting:first_time_ask' AND a.answered_at >= ? GROUP BY m.from_key""", (since,))
    for fk, mid, n, ts, subject, name in rows:
        key = presses.NEW_SENDER + str(fk)
        if db.query("SELECT 1 FROM live_items WHERE source_key=?", (key,)):
            continue
        who = " ".join(str(name or "").split()) or str(fk).split(":", 1)[-1]
        ids = [str(r[0]) for r in db.query("SELECT id FROM messages WHERE from_key=? AND direction='in' ORDER BY id DESC LIMIT 10", (fk,))]
        items.upsert(key, pass_id, kind="question", area="Personal", state="question",
                     title=card.clip(f"New sender: {who} wrote \"{' '.join(str(subject or '').split()) or 'no subject'}\"", 300),
                     detail=f"This is the first mail from {who}. It is hidden until you say. "
                            + (f"They have sent {n} messages so far." if n > 1 else ""),
                     asks=[f"Show mail from {who} from now on, or hold it?"], source_who=who, source_when=ts,
                     source_messages=json.dumps(ids), why="A sender you have not heard from before wrote, and you asked to be asked once.")
        made += 1
    return made
