r"""Levels per kind of work (the judgment rebuild, phase 5; the owner's words of 11/25, "Kinds of work and levels").

Every kind of work (rule_book.SECTIONS) starts at level 1. Only the owner raises one, in Settings, under Learning levels:

    Level 1   I show my pick as the first button on each card, and do nothing until he presses it.
    Level 2   For the things I'm good at, I do them myself and tell him: the card keeps a note of what I did, with Undo.
    Level 3   I do them quietly; they are listed in one summary card each morning.

What I may do on my own is fixed here (guardrail A19): a card's pick when it is Got it, Drop, Snooze to tomorrow or Keep
waiting, and only where that same pick has matched what he did at least GOOD_SHARE of the time over GOOD_MIN or more of his
answers in that kind of work ("things it's good at"). In Reply drafts, raising the level is his standing approval to send
that kind of message (his answer 1 of 11/25): the reply I drafted goes through send.send_level and every check there
(guardrails B1, B5 and B12): one person's own email, no copy, attachment or link, 800 characters or less, within the daily
send limit. Nothing is ever sent at level 1, and no other kind of work sends.

Every action is recorded (state\levels\actions.jsonl, the Approvals log in Settings, the presses table) with Undo on its card,
except a sent email, which can't be taken back. An Undo makes that card mine no more and counts as a miss of my pick.

    says(section, level)          the plain words of what I'll do on my own at that level, shown before it takes effect
    good_at(section, pick)        (True or False, matched, answers) for one pick in one kind of work
    act(pass_id, handoff=None)    level 2 and 3 actions on the open cards; returns how many
    undone(item)                  his Undo of one of them: recorded, and the card is never done for him again
    summary(pass_id)              the morning summary card of level 3 actions, once a day; returns 1 when made
"""
import datetime as dt
import json
import os
import uuid

import common

ACTS = {"got_it": "marked it Got it", "drop": "dropped it", "later": "snoozed it to tomorrow",
        "wait_longer": "kept waiting on them"}
ACT_LABELS = {"got_it": "Got it", "drop": "Drop", "later": "Snooze to tomorrow", "wait_longer": "Keep waiting"}
GOOD_MIN, GOOD_SHARE = 5, 0.8
PRESS_PREFIX = "level_"             # the press a level action leaves on its card: level_got_it, level_drop, level_sent ...
SUMMARY_PREFIX = "live:level-summary-"
SUMMARY_HOUR = 6
DEVICE = "learning level {n}"
SEND_SECTION = "replies"


def _store():
    return os.path.join(common.paths.STATE, "levels")


def _log_file():
    return os.path.join(_store(), "actions.jsonl")


def _summary_file():
    return os.path.join(_store(), "summary.json")


def level(section):
    import settings_page
    return settings_page.learning_levels().get(section, settings_page.LEARN_DEFAULT)


# --- the words of each level ------------------------------------------------------------------------------------------
def _acts_words():
    return "Got it, Drop, Snooze to tomorrow or Keep waiting"


def says(section, n):
    """What I'll do on my own in this kind of work at level n, in plain words, sending named where it applies."""
    import rule_book
    import standing
    where = rule_book.SECTION_WORDS.get(section, section).lower()
    good = (f"where my pick has matched what you did at least {round(GOOD_SHARE * 100)}% of the time, "
            f"over {GOOD_MIN} or more of your answers")
    send = section == SEND_SECTION
    if n == 1:
        return (f"Level 1: I show my pick as the first button on each card in {where} and do nothing until you press it."
                + (" I never send a reply on my own." if send else " I never send anything."))
    one = (f"I do my pick myself on cards in {where} {good}, when it is {_acts_words()}.")
    if send:
        one += (f" I also send the reply I drafted, on my own, when it answers one person's own email with no copy, "
                f"attachment or link, in 800 characters or less, up to {standing.send_cap()} a day. Raising this to level "
                f"{n} is your standing approval to send these replies. A sent email can't be taken back.")
    if n == 2:
        return (f"Level 2: {one} Each card keeps a note of what I did, and Undo puts it back. "
                "Changes to my picks or rules still wait for your Approve.")
    return (f"Level 3: {one} I do it quietly: no note on each card. Everything I did is listed in one summary card each "
            "morning, and Undo is on each card. I also make a change to my picks or rules myself when it matches more of "
            "your past answers and breaks none; it's in that summary and in Change history, with Undo.")


# --- what I'm good at ---------------------------------------------------------------------------------------------------
def _sig(p):
    """A pick's shape: Go ahead on a card holding my draft reply is the same as a reply."""
    p = p or {}
    if p.get("do") == "press" and p.get("press") == "approve":
        return ("reply", None)
    return (p.get("do"), p.get("press") if p.get("do") == "press" else None)


def good_at(section, pick):
    """(good, matched, answers): how often this same pick matched what he did in this kind of work, from the rule book."""
    import grader
    want, matched, n = _sig(pick), 0, 0
    for r in grader.work_rows(section):
        if _sig(r.get("pick")) != want or r.get("pick_outcome") not in ("matched", "differed"):
            continue
        n += 1
        matched += r["pick_outcome"] == "matched"
    return (n >= GOOD_MIN and matched >= GOOD_SHARE * n), matched, n


# --- acting -------------------------------------------------------------------------------------------------------------
def _skip_keys():
    import picks
    import standing
    return tuple(dict.fromkeys(picks.PROGRAM_CARDS + standing.SKIP + (SUMMARY_PREFIX,)))


def _log(entry):
    os.makedirs(_store(), exist_ok=True)
    with open(_log_file(), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def actions():
    try:
        with open(_log_file(), encoding="utf-8") as f:
            got = [json.loads(x) for x in f.read().splitlines() if x.strip()]
    except (OSError, ValueError):
        return []
    undone = {x["undo_of"] for x in got if x.get("undo_of")}
    return [dict(x, undone=x["id"] in undone) for x in got if not x.get("undo_of")]


def _candidates():
    import items
    skip = _skip_keys()
    out = []
    for it in items.rows("state <> 'done' AND shelf IS NULL"):
        extra = it.get("extra") if isinstance(it.get("extra"), dict) else {}
        if str(it.get("source_key") or "").startswith(skip) or extra.get("standing_skip") or extra.get("level_skip") \
                or it.get("replayed"):
            continue
        out.append(it)
    return out


def _record_use(it, section, n, did, note, sent=None):
    import db
    import presses
    import standing
    now = common.now()
    standing.ensure()
    db.execute("INSERT INTO live_standing_log (done_at, entry_id, kind, area, card, header, level, detail) VALUES (?,?,?,?,?,?,?,?)",
               (now, 0, "level_send" if sent else "level", str(it.get("area") or section), it["id"], " ".join(str(it.get("title") or "").split())[:200],
                "tell" if n == 2 else "quiet", json.dumps(sent) if sent else None))
    presses.record(pressed_at=now, received_at=now, item_id=it["id"], item_title=it.get("title") or "-", press=PRESS_PREFIX + did,
                   choice=str(n), words="-", device=DEVICE.format(n=n), happened=note, ok=True, claude_ran=False, secs=0)
    _log({"id": uuid.uuid4().hex[:12], "at": now.isoformat(timespec="seconds"), "card": it["id"], "title": it.get("title"),
          "section": section, "level": n, "did": did, "note": note, **({"sent": sent} if sent else {})})


def _press(it, section, n, name, pass_id):
    """Do one routine pick on the card, as his press would, with a note and the Undo his press would get."""
    import items
    import presses
    now = common.now()
    f = presses.fields(it, {"name": name, "when": "tomorrow"}, now, lambda r: {})
    last = f.get("last_press") or {}
    if not last.get("ok") or not isinstance(last.get("was"), dict):
        return False
    note = (f"I {ACTS[name]} for you at level {n}, because my pick matches what you do on cards like this. "
            "Press Undo to put it back.")
    did = it.get("assistant_did")
    f["assistant_did"] = f"{did}\n{note[:-len(' Press Undo to put it back.')]} ({presses._stamp(now)})" if did else \
        f"{note[:-len(' Press Undo to put it back.')]} ({presses._stamp(now)})"
    f["last_press"] = dict(last, press=PRESS_PREFIX + name, happened=note, level=n)
    if f.get("state") == "done":
        f["status"] = "Done for you" if n == 2 else "Done quietly"
        f["done_at"] = now
    items.update(it["id"], pass_id, **f)
    _record_use(it, section, n, name, note)
    return True


def _send(it, section, n, pass_id, handoff):
    import items
    import presses
    import db
    import send
    con = db.connect(read_only=True)
    try:
        full = items.read(con, it)          # the card as the page carries it, with the email it answers (`reply`)
    finally:
        con.close()
    full = items.finish(full) if full else None
    if not full:
        return False
    got = send.send_level(full, n, handoff)
    if not got.get("sent"):
        return False
    m = got.get("message") or {}
    now = common.now()
    note = f"I sent your reply for you at level {n}: {got.get('result')} A sent email can't be taken back."
    did = it.get("assistant_did")
    line = f"{note} ({presses._stamp(now)})"
    items.update(it["id"], pass_id, state="done", status="Sent for you", done_at=now, draft=None,
                 assistant_did=f"{did}\n{line}" if did else line,
                 last_press={"press": PRESS_PREFIX + "sent", "at": now.isoformat(timespec="seconds"), "happened": note,
                             "claude": False, "open": None, "ok": True, "level": n})
    _record_use(it, section, n, "sent", note, {"to": m.get("to"), "subject": m.get("subject"), "account": m.get("account")})
    return True


def act(pass_id, handoff=None):
    """The level 2 and 3 actions on the open cards. Returns how many. Never raises: anything it cannot do is logged and the
    card stays with him."""
    try:
        import replay_guard
        if replay_guard.on() or os.environ.get("ASSISTANT_REPLAY") == "1":
            return 0
        import card
        import picks
        import rule_book
        done, levels = 0, {}
        for it in _candidates():
            sec = rule_book.section(it)
            n = levels.setdefault(sec, level(sec))
            if n not in (2, 3):
                continue
            p = picks.of(it)
            if not p:
                continue
            if sec == SEND_SECTION and isinstance(it.get("draft"), dict) and (
                    p.get("do") == "reply" or (p.get("do") == "press" and p.get("press") == "approve")):
                if good_at(sec, p)[0] and _send(it, sec, n, pass_id, handoff):
                    done += 1
                continue
            if p.get("do") != "press" or p.get("press") not in ACTS:
                continue
            if p["press"] == "got_it" and card.needs(it) != "nothing":
                continue
            if good_at(sec, p)[0] and _press(it, sec, n, p["press"], pass_id):
                done += 1
        return done
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"levels act: {type(e).__name__}: {e}")
        return 0


def is_mine(last):
    return isinstance(last, dict) and last.get("ok") and str(last.get("press") or "").startswith(PRESS_PREFIX)


def undone(item):
    """His Undo of a level action on this card: the action marked undone, the Approvals log too, and a rule book row saying
    my pick missed (so what I'm good at counts it). Never raises."""
    try:
        import rule_book
        import standing
        last = item.get("last_press") if isinstance(item.get("last_press"), dict) else {}
        did = str(last.get("press") or "")[len(PRESS_PREFIX):]
        mine = [a for a in actions() if a.get("card") == item.get("id") and not a.get("undone")]
        now = common.now().isoformat(timespec="seconds")
        if mine:
            _log({"undo_of": mine[-1]["id"], "at": now, "card": item.get("id")})
        standing.mark_undone(item.get("id"))
        rule_book._append([{"id": uuid.uuid4().hex[:16], "at": now, "message": f"card:{item.get('id')}",
                            "section": rule_book.section(item), "card": item.get("id"), "card_kind": item.get("kind"),
                            "card_area": item.get("area"), "card_important": rule_book._important(item), "call": None,
                            "layer": "unknown", "verdict": None, "source": None, "rules": [], "covered": None,
                            "leaned_on": None, "seen": {"sender": str(item.get("source_who") or "")[:120],
                                                        "what": str(item.get("title") or "")[:160], "channel": None},
                            "press": "undo_level", "meaning": "neutral", "button": "-", "choice": "-", "status": "active",
                            "pick": {"do": "press", "press": did, "by": "level"}, "did": {"do": "press", "press": "undo"},
                            "pick_outcome": "differed"}])
        return True
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"levels undo: {type(e).__name__}: {e}")
        return False


# --- the morning summary ------------------------------------------------------------------------------------------------
def _line(a):
    at = dt.datetime.fromisoformat(a["at"])
    when = f"{at.strftime('%a')} {at.month}/{at.day} {at.strftime('%I:%M %p').lstrip('0')}"
    title = " ".join(str(a.get("title") or "").split())[:90]
    if a.get("did") == "sent":
        s = a.get("sent") or {}
        return f"- {when}: I sent your reply \"{s.get('subject') or title}\" to {', '.join(s.get('to') or [])}."
    return f"- {when}: I {ACTS.get(a.get('did'), a.get('did'))} on \"{title}\"." + (" You took it back." if a.get("undone") else "")


def summary(pass_id, now=None):
    """Once a day, from SUMMARY_HOUR: one card listing what I did quietly at level 3 since the last summary, and the changes
    to my picks and rules I made on my own. None made when there is nothing to list. Returns 1 when made."""
    try:
        import coach
        import items
        now = now or common.now()
        if now.hour < SUMMARY_HOUR:
            return 0
        day = now.date().isoformat()
        st = common.read_json(_summary_file(), {}) or {}
        if st.get("day") == day:
            return 0
        since = str(st.get("last") or "")
        quiet = [a for a in actions() if a.get("level") == 3 and str(a.get("at")) > since]
        changed = [h for h in coach.self_promotions() if str(h.get("at")) > since]
        if not quiet and not changed:
            return 0
        lines = [_line(a) for a in quiet]
        for h in changed:
            import rsi_loop
            words = rsi_loop._change_words({"kind": "work" if h.get("of") == "work" else "rule", "change": h.get("change"),
                                            "rules_before": (h.get("work_rules") if h.get("of") == "work"
                                                             else (h.get("rules") or {}).get("rules")) or []})
            lines.append(f"- I changed {'my picks' if h.get('of') == 'work' else 'your rules'}: {words}"
                         + (" You undid it." if h.get("undone_at") else " Undo is in Change history, under Tools."))
        sends = sum(1 for a in quiet if a.get("did") == "sent")
        detail = ("Here's what I did on my own since " + (f"the last summary" if since else "you raised a level") + ".\n"
                  + "\n".join(lines) + "\n"
                  + "To take one back, open that card under Done and press Undo."
                  + (" A sent email can't be taken back." if sends else ""))
        n = len(quiet) + len(changed)
        items.upsert(SUMMARY_PREFIX + day, pass_id, kind="fyi", area="System", state="new", status=None,
                     title=f"What I did on my own: {n} thing{'s' if n != 1 else ''}", detail=detail, asks=[],
                     why="You set these kinds of work to level 3, so I do them quietly and list them here each morning.",
                     extra={"level_summary": {"day": day, "actions": [a["id"] for a in quiet],
                                              "changes": [h.get("id") for h in changed]}})
        common.write_json(_summary_file(), {"day": day, "last": now.isoformat(timespec="seconds")})
        return 1
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"levels summary: {type(e).__name__}: {e}")
        return 0
