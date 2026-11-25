r"""Days on cards: stored as real dates, worded when shown.

A card must never say "this morning" four days later. So card text is stored with a day marker,
`{day:2026-11-12}` (or `{day:2026-11-12|morning}` for a part of the day), and the word is worked out
each time the card is shown: today, tomorrow, yesterday, otherwise the weekday and date.

    store(text, on)   text about to be stored: every relative day word ("today", "this morning",
                      "tomorrow night", "yesterday") becomes a marker, counted from `on`, the day the
                      words were written. A date given beside the word ("this morning (11/12)") wins.
                      Words inside quotation marks are someone's own words and are left as written.
    show(text, today) text about to be shown: every marker becomes the right word for today.
    fix_once(pass_id) once per home: open cards written before this existed get their old relative
                      words turned into markers, counted from the day the words were written. No Claude.
"""
import datetime as dt
import json
import os
import re

import common

MARK = re.compile(r"\{day:(\d{4}-\d{2}-\d{2})(?:\|(morning|afternoon|evening|night))?\}")
ECHO = re.compile(r"\{day:(\d{4}-\d{2}-\d{2})(\|(?:morning|afternoon|evening|night))?\}(,?\s+(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day,?\s+(\d{1,2})/(\d{1,2}))")


_WD = r"(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day"
LONE = re.compile(
    r"(?:\b(?P<w1>" + _WD + r"),?\s+)?(?P<m>\{day:(?P<d>\d{4}-\d{2}-\d{2})(?:\|(?:morning|afternoon|evening|night))?\})(?:,?\s+(?P<w2>" + _WD + r")\b(?!\s*,?\s*\d{1,2}/\d{1,2}))?",
    re.I)


def _near(month, day, to):
    return min((dt.date(to.year + k, month, day) for k in (-1, 0, 1)), key=lambda d: abs((d - to).days))


ON = re.compile(r"\b([Oo]n\s+)\{day:(\d{4}-\d{2}-\d{2})(?:\|(morning|afternoon|evening|night))?\}")
PARTS = "morning|afternoon|evening|night"
# the relative words, longest first; each gives (days from the day of writing, part of the day or None)
WORDS = re.compile(
    r"\b(?:(this)\s+(morning|afternoon|evening)|(tonight)|(last)\s+night"
    r"|(tomorrow|yesterday|today)(?:\s+(" + PARTS + r"))?)\b"
    r"(\s*\(\s*(?:(\d{4})-(\d{1,2})-(\d{1,2})|(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?)\s*\))?", re.I)
QUOTED = re.compile(r"\"[^\"\n]{0,2000}\"|“[^”\n]{0,2000}”")
TEXT_COLUMNS = ("title", "detail", "recommended", "why", "short_header")
DONE = os.path.join(common.HOME, "state", "dates_fixed_all_states.json")      # the fix runs once per home, for cards of every state
LOG = os.path.join(common.LOGS, "dates_fixed.log")


def _explicit(m, on):
    """The date written in brackets beside the word, or None."""
    try:
        if m.group(8):
            return dt.date(int(m.group(8)), int(m.group(9)), int(m.group(10)))
        if m.group(11):
            month, day = int(m.group(11)), int(m.group(12))
            if m.group(13):
                y = int(m.group(13))
                return dt.date(y + 2000 if y < 100 else y, month, day)
            best = min((dt.date(on.year + k, month, day) for k in (-1, 0, 1)), key=lambda d: abs((d - on).days))
            return best
    except ValueError:
        return None
    return None


def _mark(m, on):
    if m.group(1):
        days, part = 0, m.group(2).lower()
    elif m.group(3):
        days, part = 0, "night"
    elif m.group(4):
        days, part = -1, "night"
    else:
        days = {"today": 0, "tomorrow": 1, "yesterday": -1}[m.group(5).lower()]
        part = (m.group(6) or "").lower() or None
    day = on + dt.timedelta(days=days)
    if m.group(7):
        given = _explicit(m, on)
        if given is None:
            return m.group(0)       # brackets that are not a date: leave it all alone
        day = given
    return "{day:" + day.isoformat() + ("|" + part if part else "") + "}"


def store(text, on=None):
    """text with every relative day word outside quotation marks turned into a marker, counted from `on`."""
    if not isinstance(text, str) or not text:
        return text
    on = on or common.ai_today()            # a replay's day while one runs
    if isinstance(on, dt.datetime):
        on = on.date()
    out, last = [], 0
    for q in QUOTED.finditer(text):
        out.append(WORDS.sub(lambda m: _mark(m, on), text[last:q.start()]))
        out.append(q.group(0))
        last = q.end()
    out.append(WORDS.sub(lambda m: _mark(m, on), text[last:]))
    return "".join(out)


def _date_words(d, today):
    return f"{d.strftime('%a')} {d.month}/{d.day}" + (f"/{d:%y}" if d.year != today.year else "")


def _word(day, part, today):
    diff = (day - today).days
    if part is None:
        return {0: "today", 1: "tomorrow", -1: "yesterday"}.get(diff) or _date_words(day, today)
    if diff == 0:
        return "tonight" if part == "night" else f"this {part}"
    if diff == -1:
        return "last night" if part == "night" else f"yesterday {part}"
    if diff == 1:
        return f"tomorrow {part}"
    return _date_words(day, today) + (" at night" if part == "night" else f" in the {part}")


def show(text, today=None):
    """text with every marker turned into the right word for today. A word that starts the text or a
    sentence gets its capital letter."""
    if not isinstance(text, str) or "{day:" not in text:
        return text
    today = today or dt.date.today()

    def swap(m):
        try:
            w = _word(dt.date.fromisoformat(m.group(1)), m.group(2), today)
        except ValueError:
            return m.group(0)
        before = text[:m.start()].rstrip()
        if not before or before[-1] in ".!?:\n":
            w = w[:1].upper() + w[1:]
        return w

    def echo_swap(m):       # a weekday and date written beside the marker for the same day says it twice: keep the marker
        try:
            same = dt.date.fromisoformat(m.group(1)) == _near(int(m.group(4)), int(m.group(5)), dt.date.fromisoformat(m.group(1)))
        except ValueError:
            return m.group(0)
        return m.group(0)[:m.start(3) - m.start(0)] if same else m.group(0)

    def on_swap(m):         # "on tomorrow" is not English: the "on" stays only before a weekday and date
        try:
            day = dt.date.fromisoformat(m.group(2))
        except ValueError:
            return m.group(0)
        if abs((day - today).days) > 1:
            return m.group(0)
        w = _word(day, m.group(3), today)
        before = text[:m.start()].rstrip()
        return w[:1].upper() + w[1:] if (not before or before[-1] in ".!?:\n") else w
    def lone_swap(m):       # a weekday written right beside the marker for the same day ("Thursday today"): the marker says it once
        try:
            day = dt.date.fromisoformat(m.group("d"))
        except ValueError:
            return m.group(0)
        name = (m.group("w1") or m.group("w2") or "").lower()
        return m.group("m") if day.strftime("%A").lower() == name else m.group(0)
    text = ON.sub(on_swap, text)
    text = ECHO.sub(echo_swap, text)
    text = LONE.sub(lone_swap, text)
    return MARK.sub(swap, text)


def store_fields(fields, on=None):
    """The text columns of a card about to be written, each through store(). Changed in place and returned."""
    for k in TEXT_COLUMNS:
        if isinstance(fields.get(k), str):
            fields[k] = store(fields[k], on)
    if isinstance(fields.get("asks"), list):
        fields["asks"] = [store(a, on) if isinstance(a, str) else a for a in fields["asks"]]
    return fields


def _show_choice(c, today):
    if isinstance(c, str):
        return show(c, today)
    if isinstance(c, dict):
        return {k: show(v, today) if k in ("label", "text") and isinstance(v, str) else v for k, v in c.items()}
    return c


def show_card(it, today=None):
    """Every text of one card, worded for today (changed in place and returned)."""
    for k in TEXT_COLUMNS + ("header", "wants", "status", "rec_front"):
        if isinstance(it.get(k), str):
            it[k] = show(it[k], today)
    for q in it.get("questions") or []:         # each question and its own choices (the card's front)
        if isinstance(q, dict):
            if isinstance(q.get("ask"), str):
                q["ask"] = show(q["ask"], today)
            q["choices"] = [_show_choice(c, today) for c in q.get("choices") or []]
    if isinstance(it.get("choices"), list):
        it["choices"] = [_show_choice(c, today) for c in it["choices"]]
    if isinstance(it.get("asks"), list):
        it["asks"] = [show(a, today) if isinstance(a, str) else a for a in it["asks"]]
    press = it.get("last_press")
    if isinstance(press, dict) and isinstance(press.get("happened"), str):
        press["happened"] = show(press["happened"], today)
    for row in it.get("old_cards") or []:
        if isinstance(row, dict) and isinstance(row.get("header"), str):
            row["header"] = show(row["header"], today)
    rule = it.get("rule")
    if isinstance(rule, dict) and isinstance(rule.get("from"), str):
        rule["from"] = show(rule["from"], today)
    return it


STAMP = re.compile(r"^You answered (\d{1,2})/(\d{1,2}) ")


def written_on(source_when, created_at, history):
    """The day a card's words were written: the day of the newest message behind it (the writer runs when a
    message arrives), or the day of the owner's last typed answer that rewrote it, whichever is later."""
    day = (source_when or created_at).date() if (source_when or created_at) else dt.date.today()
    lines = str(history or "").split("\n")
    for n, line in enumerate(lines):
        if "I rewrote the card" in line:
            for back in range(n, -1, -1):
                m = STAMP.match(lines[back])
                if m:
                    try:
                        cand = min((dt.date(day.year + k, int(m.group(1)), int(m.group(2))) for k in (-1, 0, 1)),
                                   key=lambda d: abs((d - day).days))
                        day = max(day, cand)
                    except ValueError:
                        pass
                    break
    return day


def fix_once(pass_id):
    """Once per home (cards of every state, finished ones too). Returns how many cards were changed. What was found and what it became is written
    to logs\\dates_fixed.log, one line per text."""
    if os.path.exists(DONE):
        return 0
    import db
    import items
    items.ensure()
    changed = 0
    now = common.now()
    for iid, title, detail, rec, why, short, asks, src, made, did in db.query(
            "SELECT id, title, detail, recommended, why, short_header, asks, source_when, created_at, assistant_did"
            " FROM live_items"):                  # every card the owner can see, finished ones included
        on = written_on(src, made, did)
        old = {"title": title, "detail": detail, "recommended": rec, "why": why, "short_header": short}
        new = {k: store(v, on) for k, v in old.items()}
        try:
            old_asks = json.loads(asks or "[]")
        except ValueError:
            old_asks = []
        new_asks = [store(a, on) if isinstance(a, str) else a for a in old_asks]
        diff = {k: v for k, v in new.items() if v != old[k]}
        if new_asks != old_asks:
            diff["asks"] = json.dumps(new_asks)
        if not diff:
            continue
        for k in diff:
            before = old_asks if k == "asks" else old[k]
            after = new_asks if k == "asks" else new[k]
            common.log_line(LOG, f"{iid} {k} (words written {on.isoformat()}) | WAS: {json.dumps(before)[:600]} | NOW: {json.dumps(after)[:600]}")
        # day words only: nothing else on the card changes, not even when it was last touched
        db.execute(f"UPDATE live_items SET {', '.join(k + '=?' for k in diff)} WHERE id=?", (*diff.values(), iid))
        changed += 1
    common.write_json(DONE, {"at": now, "pass": pass_id, "cards_changed": changed})
    return changed
