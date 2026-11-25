r"""Standing approvals to send replies: the offer, and doing what an entry says.

The owner's yes of 11/16/26. Everything the ladder (standing.py) promises holds here too, and more:
  - the kind is "send replies to one person": it can only come from an offer card the owner answered; the Settings
    Save can pause, change the level of or remove such an entry but never make one;
  - the offer names the person and shows two or three real examples of what it would have covered (the subjects and
    dates of replies the owner sent by hand to that person), the limits, and how to stop it;
  - a send goes only through send.send_standing, which reads the entry fresh and checks every rule (send.py);
  - every send is recorded (the log, the presses table, the sent log), with what was sent, to whom and which approval.

    earned()      [{"kind", "area", "scope", "account", "count", "examples"}] the offers the owner's own sends have earned
    offer(spec)   the offer card for one of them
    apply(pass_id, entries)   send what fits, within the daily cap; returns how many were sent
"""
import datetime as dt
import json
import os

import common
import standing

KIND = "send_reply"
MAX_BODY = 800


def send_log():
    """The owner's sent log, newest last: [dict]."""
    out = []
    try:
        with open(os.path.join(common.LOGS, "sent.log"), encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def hand_sends():
    """Replies the owner sent by hand that look like the kind: sent, one recipient, no copy, no attachment, short, not under
    a standing approval. [(when, account, recipient, subject, card id)]."""
    out = []
    for r in send_log():
        to = [str(a).lower() for a in r.get("to") or []]
        if r.get("result") == "sent" and (r.get("channel") or "email") == "email" and not r.get("standing") and not r.get("level") and len(to) == 1 and not r.get("cc") and not r.get("attach") \
                and isinstance(r.get("body_chars"), int) and r["body_chars"] <= MAX_BODY and r.get("item"):
            out.append((r.get("at"), r.get("account"), to[0], str(r.get("subject") or ""), r.get("item")))
    return out


def _area(item_id):
    import db
    got = db.query("SELECT area FROM live_items WHERE id=?", (item_id,))
    return got[0][0] if got else None


def earned():
    """The offers the owner's own hand-sent replies have earned: the same recipient and area enough times (the setting), no
    entry, none waiting, and not turned down since."""
    import db
    n = standing.offer_after()
    if not n:
        return []
    have = {(e["area"], e.get("scope")) for e in standing.ladder() if e["kind"] == KIND}
    declined = standing._data().get("declined") or {}
    waiting = [r[0] for r in db.query("SELECT source_key FROM live_items WHERE starts_with(source_key, ?) AND state <> 'done'", (standing.OFFER_PREFIX + KIND,))]
    groups = {}
    for when, account, to, subject, item_id in hand_sends():
        area = _area(item_id)
        if area:
            groups.setdefault((area, to, account), []).append((when, subject))
    out = []
    for (area, to, account), rows in groups.items():
        c = len(rows)
        key = f"{KIND}|{area}|{to}"
        if (area, to) in have or any(w.startswith(f"{standing.OFFER_PREFIX}{KIND}-{area}-{to}") for w in waiting):
            continue
        if c >= n and c - int(declined.get(key) or 0) >= n:
            out.append({"kind": KIND, "area": area, "scope": to, "account": account, "count": c, "examples": rows[-3:]})
    return out


def _name(scope):
    import db
    got = db.query("SELECT max(c.name) FROM contacts c WHERE c.key = ?", (f"email:{scope}",))
    return " ".join(str(got[0][0]).split()) if got and got[0][0] else scope


def offer(spec, pass_id):
    """Make the offer card for one earned offer. Names the kind in plain words, with the examples it would have covered."""
    import db
    import items
    who, scope, area = _name(spec["scope"]), spec["scope"], spec["area"]
    examples = "\n".join(f"- {dt.datetime.fromisoformat(w):%m/%d}: \"{s}\"" for w, s in spec["examples"])
    base = f"{standing.OFFER_PREFIX}{KIND}-{area}-{scope}"
    keys = {r[0] for r in db.query("SELECT source_key FROM live_items WHERE source_key = ? OR starts_with(source_key, ?)", (base, base + "-"))}
    again, k = "", 1
    while base + again in keys:         # the first key not used before: an earlier offer's card is never reused
        k += 1
        again = f"-{k}"
    iid, _ = items.upsert(f"{standing.OFFER_PREFIX}{KIND}-{area}-{scope}{again}", pass_id, kind="question", area=area, state="question", status=None,
                          title=f"You have sent short replies to {who} {spec['count']} times. Shall I send replies like these to {who} for you from now on, without asking?",
                          detail=(f"The kind: a short reply from {spec['account']} to {who} ({scope}), written by me, answering a message {who} sent you, "
                                  f"on a card in {area}.\n\nThe last ones you sent by hand, which this would have covered:\n{examples}\n\n"
                                  f"What would be sent for you, and only this: one recipient ({scope}), no copy, no attachment, under {MAX_BODY} characters, no link, "
                                  "and only when it is plainly a reply to {who}'s own message. Anything else comes to you as it does today. "
                                  f"At most {standing.send_cap()} a day (you can change that in Settings). Every one is listed on your page with what was sent, to whom, "
                                  "and which approval allowed it. A sent email cannot be taken back. You can pause or remove this any time in Settings, "
                                  "under Approvals, and the next send stops at once. Nothing is sent for you unless you say yes here.").replace("{who}", who),
                          asks=["Shall I send replies like these for you from now on?"], why="You have sent the same kind of reply by hand several times.",
                          extra={"offer": {"kind": KIND, "area": area, "scope": scope, "account": spec["account"], "count": spec["count"]}})
    return iid


def _decorated(entry):
    """Open cards in the entry's area that hold a draft, as the page's data carries them (with `reply`)."""
    import db
    import items
    out = []
    con = db.connect(read_only=True)
    try:
        for it in items.rows("state IN ('question', 'yours') AND shelf IS NULL AND area = ? AND draft IS NOT NULL", (entry["area"],)):
            if str(it.get("source_key") or "").startswith(standing.SKIP):
                continue
            extra = it.get("extra") if isinstance(it.get("extra"), dict) else {}
            if extra.get("standing_skip") or it.get("replayed"):     # a card from the replay is never sent for
                continue
            out.append(items.read(con, it))
    finally:
        con.close()
    return [items.finish(it) for it in out]     # the connection is closed: a mod's card may ask its mod


def apply(pass_id, entries):
    """Send what fits, one at a time, inside the daily cap. Every entry is read fresh again by send.send_standing right before
    each send, so a pause or removal stops the next one. Returns how many were sent."""
    import replay_guard
    replay_guard.refuse("replies by standing approval")
    import db
    import presses
    import send
    sent = 0
    now = common.now()
    for entry in entries:
        for it in _decorated(entry):
            if standing.send_left() <= 0:
                return sent
            out = send.send_standing(it, entry["id"])
            if not out.get("sent"):
                continue
            m, level = out["message"], entry["level"]
            tell = level == "tell"
            say = (f"Sent for you: \"{m['subject']}\" to {m['to'][0]}, with the permission you gave me on {dt.datetime.fromisoformat(entry['made']):%m/%d}.").replace(" 0", " ").replace("/0", "/")
            mark = presses._mark("standing_send", now, say)
            line = f"{say} ({presses._stamp(now)})"
            story = f"{say}\n\nTo: {m['to'][0]}\nFrom: {m['account']}\nSubject: {m['subject']}\n\n{m['body']}"
            db.execute("UPDATE live_items SET state=?, status='Sent for you', draft=NULL, detail=?, done_at=?, assistant_did=?, last_press=?, updated_at=?, state_changed_at=?, last_pass=? WHERE id=?",
                       ("in_motion" if tell else "done", story, None if tell else now, f"{it.get('assistant_did')}\n{line}" if it.get("assistant_did") else line,
                        json.dumps(mark), now, now, pass_id, it["id"]))
            detail = {"to": m["to"], "account": m["account"], "subject": m["subject"], "body": m["body"], "approval": entry["id"], "result": out["result"]}
            db.execute("INSERT INTO live_standing_log (done_at, entry_id, kind, area, card, header, level, detail) VALUES (?,?,?,?,?,?,?,?)",
                       (now, entry["id"], KIND, entry["area"], it["id"], f"{m['subject']} to {m['to'][0]}"[:200], level, json.dumps(detail)))
            presses.record(pressed_at=now, received_at=now, item_id=it["id"], item_title=it["title"], press="standing_send", choice=level, words="-",
                           device=standing.DEVICE, happened=say, ok=True, claude_ran=False, secs=0)
            data = standing._data()
            for e in data.get("entries") or []:
                if e.get("id") == entry["id"]:
                    e["used"] = int(e.get("used") or 0) + 1
            standing._write(data)
            sent += 1
    return sent
