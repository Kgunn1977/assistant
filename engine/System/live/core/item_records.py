"""The full record of each open item, and the pointer the payloads carry.

Each open item gets one file under the home's state\\items\\ with its full
detail and every citation; the payloads carry only the short layer plus
full_record.path. The folder is cleared and rebuilt on every build, so it
never holds a closed item. Nothing here writes the database.
"""

import datetime as dt
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # System\live
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                    # System\live\core
import db  # noqa: E402
import paths  # noqa: E402

RECENT_CITATIONS = 5          # how many ride in the payload, newest first
SLUG_MAX = 80

ITEMS = os.path.join(paths.STATE, "items")


def slug(item_key, taken):
    """A filename from an item_key, unique across one build: a slug that
    collides with another key's carries a short hash of its own key. `taken`
    maps slug -> item_key, one dict per build."""
    s = re.sub(r"[^a-z0-9]+", "-", (item_key or "").lower()).strip("-")
    s = s[:SLUG_MAX].strip("-") or "item"
    if taken.get(s, item_key) != item_key:
        tag = hashlib.sha1((item_key or "").encode("utf-8")).hexdigest()[:8]
        s = f"{s[:SLUG_MAX - 9].strip('-')}-{tag}"
    taken[s] = item_key
    return s


class Records:
    """One per payload build. Clears the folder, then writes a record per item."""

    def __init__(self, folder=ITEMS):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)
        for name in os.listdir(folder):
            if name.endswith(".json"):
                os.remove(os.path.join(folder, name))
        self._taken = {}

    def citations_for(self, task_id):
        """Every message a task rests on, NEWEST FIRST. The one query both
        payloads use, so the record and the payload's five can never disagree."""
        rows = db.query("""
            SELECT r.value, r.role, m.ts, m.channel, m.account,
                   substr(coalesce(m.subject,''), 1, 90),
                   (SELECT max(c.name) FROM contacts c
                     WHERE c.person_id = m.person_id AND c.name IS NOT NULL)
            FROM task_refs r
            LEFT JOIN messages m ON CAST(m.id AS VARCHAR) = r.value
            WHERE r.task_id = ? AND r.ref_type = 'message'
            ORDER BY m.ts DESC""", (task_id,))
        return [{"message_id": c[0], "role": c[1],
                 "when": str(c[2]) if c[2] else None,
                 "channel": c[3], "account": c[4], "subject": c[5],
                 "from": c[6]} for c in rows]

    def write(self, item_key, title, status, area, detail, citations):
        """Write the item's full record; return the payload's full_record
        pointer. Written for every open item, including one with a short trail,
        so an agent never has to wonder whether the file is there."""
        path = os.path.join(self.folder, slug(item_key, self._taken) + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "item_key": item_key, "title": title, "status": status,
                "area": area, "detail": detail or "",
                "citations": citations,
                "written_at": str(dt.datetime.now()),
            }, f, indent=1, default=str)
        n = len(citations)
        return {"path": path, "citations_total": n,
                "citations_omitted": max(0, n - RECENT_CITATIONS)}
