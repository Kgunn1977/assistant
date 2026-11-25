r"""The weekly review the assistant prepares: get clear, get current, get creative.

ITEMS.md ("Design round 3") is the contract. One card a week, on the day and time the owner chose (default Friday
3 PM; "off" makes none). It is made from what the assistant already holds: his open cards, waiting-for, the
Someday shelf, the calendars he shows and the Hidden list. It costs no Claude run, ever.

    make(pass_id)   the week's review card, made once; refreshed while it is open. Returns 1 when it was made now.
"""
import datetime as dt
import json
import os

import card
import common
import dates
import filters

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
KEY = "live:review-"
COST = "I made this from your cards and calendar, without AI."


def settings():
    """(day, time): the owner's choice, default Friday 3 PM; the day may be "off"."""
    s = common.settings().get("review")
    s = s if isinstance(s, dict) else {}
    day = s.get("day") if s.get("day") in DAYS + ("off",) else "fri"
    time = s.get("time") if isinstance(s.get("time"), str) and len(s.get("time")) == 5 and s["time"][2] == ":" else "15:00"
    return day, time


def _clock(t):
    try:
        return dt.datetime.strptime(t, "%H:%M").time()
    except ValueError:
        return dt.time(15, 0)


def due_now(now=None):
    """True when this week's review is due: the chosen day, at or after the chosen time."""
    now = now or common.now()
    day, time = settings()
    return day != "off" and DAYS[now.weekday()] == day and now.time() >= _clock(time)


def _days(then, now):
    return max(0, (now - then).days) if then else 0


def _row(it, note, presses):
    return {"id": it["id"], "header": card.header_of(it.get("title"), it.get("short_header")), "note": note, "presses": presses}


def build(now=None):
    import db
    import items
    now = now or common.now()
    today = now.date()
    cards = [i for i in items.rows("state <> 'done'") if not str(i.get("source_key") or "").startswith(("rule:", "improve:", "built:", "live:rsi-", KEY))]
    for it in cards:
        it["needs"] = card.needs(it)
    mine = [i for i in cards if not i.get("shelf")]
    need = sorted([i for i in mine if i["needs"] in ("answer", "approval", "do")], key=lambda i: i.get("source_when") or i["created_at"])
    parts = []
    if need:
        parts.append({"key": "waiting_on_you", "group": "clear", "title": "Waiting on you",
                      "lines": [f"{len(need)} card{'s' if len(need) != 1 else ''} wait{'s' if len(need) == 1 else ''} on you. The oldest are below."],
                      "rows": [_row(i, f"waiting {_days(i.get('source_when') or i['created_at'], now)} days", ["done", "later"]) for i in need[:5]]})
    past = [i for i in mine if i["needs"] == "waiting" and i.get("checkback_date") and i["checkback_date"] < today]
    if past:
        parts.append({"key": "waiting_past_due", "group": "clear", "title": "Waiting on others, past their date",
                      "lines": [f"{len(past)} waiting card{'s are' if len(past) != 1 else ' is'} past the date to check back."],
                      "rows": [_row(i, f"was due {i['checkback_date'].month}/{i['checkback_date'].day}", ["wait_longer", "done"]) for i in past[:8]]})
    limit = filters.get()["old_card_days"] or 14
    old = [i for i in need if _days(max(t for t in (i.get("source_when"), i.get("state_changed_at"), i["created_at"]) if t), now) >= limit]
    if old:
        parts.append({"key": "old", "group": "clear", "title": "Cards that have sat",
                      "lines": [f"{len(old)} have sat for {limit} days or more."],
                      "rows": [_row(i, f"untouched {_days(max(t for t in (i.get('source_when'), i.get('state_changed_at'), i['created_at']) if t), now)} days",
                                    ["old_keep", "later", "done"]) for i in old[:8]]})
    cal = _calendar(today)
    parts.append({"key": "next_week", "group": "current", "title": "Next week",
                  "lines": cal or ["Nothing is on the calendars you show for the next seven days."], "rows": []})
    held = common.read_json(os.path.join(common.HOME, "held.json"), {}) or {}
    total = sum(d.get("count") or 0 for d in held.get("days") or [])
    parts.append({"key": "held", "group": "current", "title": "What was hidden this week",
                  "lines": [f"I hid {total} message{'s' if total != 1 else ''} in the last 7 days. Each is under Hidden in Cards, with why."], "rows": []})
    week_ago = (now - dt.timedelta(days=7)).isoformat()
    rules = [r for r in filters.rules() if str(r.get("made") or "") >= week_ago]
    import standing
    entries = [e for e in standing.ladder() if str(e.get("made") or "") >= week_ago]
    learned = []
    if rules:
        learned.append(f"{len(rules)} new rule{'s' if len(rules) != 1 else ''}: " + "; ".join(r["text"] for r in rules[:3]))
    if entries:
        learned.append(f"{len(entries)} new thing{'s' if len(entries) != 1 else ''} I may do without asking.")
    parts.append({"key": "learned", "group": "current", "title": "What I learned",
                  "lines": learned or ["Nothing new this week."], "rows": []})
    some = [i for i in cards if i.get("shelf") == "someday"]
    parts.append({"key": "someday", "group": "creative", "title": "Someday",
                  "lines": ([f"{len(some)} thing{'s are' if len(some) != 1 else ' is'} snoozed to Someday. Pick one to start this week, or leave them."]
                            if some else ["Nothing is snoozed to Someday. Is there something you have been meaning to start?"]),
                  "rows": [_row(i, f"snoozed {_days(i.get('state_changed_at') or i['created_at'], now)} days", ["bring_back", "done"]) for i in some[:8]]})
    line = f"{len(need)} card{'s' if len(need) != 1 else ''} wait on you, {len(past)} waiting past their date, {len(some)} snoozed to Someday."
    return {"week": f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}", "line": line, "parts": parts, "cost": COST}


def _calendar(today):
    import db
    shown = [str(c).strip() for c in (common.personal().get("today_calendars") or []) if str(c).strip()]
    if not shown:
        return []
    try:
        got = db.query(f"SELECT start_ts, all_day, summary FROM calendar_events WHERE CAST(start_ts AS DATE) BETWEEN ? AND ?"
                       f" AND trim(calendar) IN ({', '.join('?' for _ in shown)}) ORDER BY start_ts LIMIT 25",
                       (today, today + dt.timedelta(days=7), *shown))
    except Exception:  # noqa: BLE001
        return []
    return [f"{s.strftime('%a')} {s.month}/{s.day}" + ("" if a else f" {s.strftime('%I:%M %p').lstrip('0')}") + f" {t}" for s, a, t in got]


def make(pass_id, now=None):
    """The week's review card. Made once when it is due; refreshed while it is open. Returns 1 when made now."""
    import db
    import items
    items.ensure()
    now = now or common.now()
    week = now.isocalendar()
    key = f"{KEY}{week[0]}-W{week[1]:02d}"
    have = db.query("SELECT id, state FROM live_items WHERE source_key=?", (key,))
    if have and have[0][1] == "done":
        return 0
    if not have and not due_now(now):
        return 0
    doc = build(now)
    monday = (now - dt.timedelta(days=now.weekday())).date()
    items.upsert(key, pass_id, kind="task", area="Personal", state="yours", status=None,
                 title=f"Your weekly review, week of {monday.month}/{monday.day}", detail=doc["line"],
                 asks=["Go through it, then press Done."], why="It is your weekly review day.", extra={"review": doc})
    return 0 if have else 1
