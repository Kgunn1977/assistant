r"""Learning levels per kind of work (the owner's accepted plan: the video's three trust levels for the learning loop).

Every kind of work (rule_book.SECTIONS) starts at level 1, and all of them learn at once. Only the owner raises one, in
Settings, under Learning levels:

    Level 1   He teaches on the cards; the loop scores my calls and proposes no change.
    Level 2   The loop writes one change in a draft beside his live rules and shows it on a card with both scores, the
              change, and one choice: Promote or Reject. It never promotes on its own (rsi_loop.py, coach.py).
    Level 3   Automatic: the loop tries one change at a time and promotes it only when it scores higher and breaks nothing
              that passed before; it stops after rsi_loop.ROUNDS (10) tries. Each change is in Change history with Undo,
              and listed in one summary card the next morning.

No level acts on a card or sends anything on its own: acting for him takes his own standing approval (standing.py).

    level(section)                the section's level
    says(section, level)          the plain words of what the loop does at that level, shown before it takes effect
    act(pass_id, handoff=None)    nothing is done on a card by a learning level: always 0 (kept for the pass's call)
    undone(item)                  his Undo of an action recorded by an earlier version: recorded as a miss
    summary(pass_id)              the morning summary card of the changes level 3 made on its own; returns 1 when made
"""
import json
import os
import uuid

import common

PRESS_PREFIX = "level_"             # the press a level action leaves on its card: level_got_it, level_drop, level_sent ...
SUMMARY_PREFIX = "live:level-summary-"
SUMMARY_HOUR = 6
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
def says(section, n):
    """What the learning loop does in this kind of work at level n, in plain words (the video's three levels, the owner's
    accepted plan): 1 he teaches on the cards, 2 one change proposed with both scores for Promote or Reject, 3 automatic,
    at most rsi_loop.ROUNDS tries. No level ever acts on a card or sends on its own: that takes his standing approval."""
    import rsi_loop
    import rule_book
    where = rule_book.SECTION_WORDS.get(section, section).lower()
    send = " I never send a reply on my own at any level." if section == SEND_SECTION else ""
    if n == 1:
        return (f"Level 1: I learn from everything you do on cards in {where} and keep my score here. I don't propose "
                f"changes to my rules or picks: you teach me on the cards, and nothing changes until you approve it.{send}")
    if n == 2:
        return (f"Level 2: when I miss in {where}, I write one change in a draft beside your live rules and bring it to you "
                "on a card with both scores (now and with the change) and the change itself. You Promote or Reject it; "
                f"I never promote one on my own.{send}")
    return (f"Level 3: automatic. When I miss in {where}, I try one change at a time, each scored against your past answers, "
            "and promote it on my own only when it scores higher and breaks nothing that passed before. I stop after "
            f"{rsi_loop.ROUNDS} tries. Each change is in Change history with Undo.{send}")


# --- acting: none -------------------------------------------------------------------------------------------------------
def _log(entry):
    os.makedirs(_store(), exist_ok=True)
    with open(_log_file(), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def actions():
    """Actions recorded by an earlier version that did picks on its own at levels 2 and 3 (none are made now)."""
    try:
        with open(_log_file(), encoding="utf-8") as f:
            got = [json.loads(x) for x in f.read().splitlines() if x.strip()]
    except (OSError, ValueError):
        return []
    undone = {x["undo_of"] for x in got if x.get("undo_of")}
    return [dict(x, undone=x["id"] in undone) for x in got if not x.get("undo_of")]


def act(pass_id, handoff=None):
    """A learning level never does a pick or sends on its own: level 2 proposes a change for Promote or Reject and level 3
    changes my rules or picks (rsi_loop.py); acting on a card takes his standing approval (standing.py). Always 0."""
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
def summary(pass_id, now=None):
    """Once a day, from SUMMARY_HOUR: one card listing the changes to my picks and rules level 3 made on its own since the
    last summary. None made when there is nothing to list. Returns 1 when made."""
    try:
        import coach
        import items
        import rsi_loop
        now = now or common.now()
        if now.hour < SUMMARY_HOUR:
            return 0
        day = now.date().isoformat()
        st = common.read_json(_summary_file(), {}) or {}
        if st.get("day") == day:
            return 0
        since = str(st.get("last") or "")
        changed = [h for h in coach.self_promotions() if str(h.get("at")) > since]
        if not changed:
            return 0
        lines = []
        for h in changed:
            words = rsi_loop._change_words({"kind": "work" if h.get("of") == "work" else "rule", "change": h.get("change"),
                                            "rules_before": (h.get("work_rules") if h.get("of") == "work"
                                                             else (h.get("rules") or {}).get("rules")) or []})
            lines.append(f"- I changed {'my picks' if h.get('of') == 'work' else 'your rules'}: {words}"
                         + (" You undid it." if h.get("undone_at") else " Undo is in Change history, under Tools."))
        detail = ("Here's what I changed on my own since " + ("the last summary" if since else "you raised a level") + ".\n"
                  + "\n".join(lines))
        n = len(changed)
        items.upsert(SUMMARY_PREFIX + day, pass_id, kind="fyi", area="System", state="new", status=None,
                     title=f"What I changed on my own: {n} change{'s' if n != 1 else ''}", detail=detail, asks=[],
                     why="You set these kinds of work to level 3, so I make changes that score higher on my own and list them here each morning.",
                     extra={"level_summary": {"day": day, "actions": [], "changes": [h.get("id") for h in changed]}})
        common.write_json(_summary_file(), {"day": day, "last": now.isoformat(timespec="seconds")})
        return 1
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"levels summary: {type(e).__name__}: {e}")
        return 0
