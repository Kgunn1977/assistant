r"""Whole headers for cards whose only header was a long title.

A card written from now on gets its header from the same Claude run that writes the card. A card that was
open before that, with a title too long to read at a glance, is sent ONCE, with all the others like it, in
one run on the fastest model; it is never sent again. Until then, and for any card that run misses, the page
shows the whole title. Nothing is ever cut.
"""
import os

import card
import common
import dates

MODEL = "haiku"
MOST = 80


def batch(pass_id):
    """Returns how many cards got a whole header. At most one Claude run, and none when no card needs it."""
    import db
    import items
    items.ensure()
    rows = db.query("SELECT id, title, substr(coalesce(detail, ''), 1, 400) FROM live_items WHERE state <> 'done'"
                    " AND short_header IS NULL AND header_asked IS NULL AND length(title) > ? ORDER BY id LIMIT ?",
                    (card.HEADER_MAX, MOST))
    if not rows:
        return 0
    import settings_page
    if settings_page.at_limit():
        return 0
    import ai_steps
    import think
    think._current.update({"pass": pass_id, "step": "headers"})
    path = os.path.join(common.paths.STATE, "live_headers_payload.json")
    out = os.path.join(common.paths.STATE, "live_headers_out.json")
    common.write_json(path, {"cards": [{"id": i, "title": t, "story": s} for i, t, s in rows]})
    res = ai_steps.agent(think._prompt("headers", PAYLOAD_PATH=path), MODEL, out)
    if not res.ok:
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"{pass_id} headers: {res.why}")
        return 0
    owed = {r[0] for r in rows}
    got = {e.get("id"): card.whole(e.get("header")) for e in (common.read_json(out, {}) or {}).get("headers") or [] if isinstance(e, dict)}
    now, n = common.now(), 0
    for iid in owed:
        new = dates.store(got.get(iid), now.date()) or None
        db.execute("UPDATE live_items SET short_header=?, header_asked=?, updated_at=? WHERE id=?", (new, now, now, iid))
        n += 1 if new else 0
    return n
