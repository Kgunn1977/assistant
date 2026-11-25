r"""The pick: what the assistant predicts the owner will do with each card (the judgment rebuild, phase 1, "It predicts").

Every open card carries one pick, shown on the page as its first button; one press does it. The card writer writes it
(prompts\items.md, `pick`); a card it did not write, or wrote with no usable pick, gets the program's own (default()).
Learning level 1 only: nothing is done until he presses.

    DOES                          choice, press, reply, none
    from_writer(raw, choices)     a written pick, checked; None when it cannot be used
    default(it)                   the program's pick for a card, from its buttons and what it needs
    of(it)                        the card's pick as it stands: written, else the program's; None on a closed card
    shown(it)                     the pick as the page draws it: {do, label, press|text|gist, by}
    did_of(press, choice, words)  what he did, in the pick's own shape
    outcome(pick, did)            matched, differed, or None when what he did decides nothing (Undo, Read, Bring back)
    remember(item, did)           what he did when it was not the pick, kept for the next card like it ("the choices grow")
    habit(it)                     what he did instead of the pick on the last card like this one, as a button's words
    last_time(it)                 that, for a card like this one; None when he has always taken the pick
    grow(entry, like)             that, made one of a written card's own choices ("the choices grow")
    note_written(n_writer, chars) the card writer's picks this pass, for the pass log's cost line
    cost_line()                   that line
"""
import json
import os
import re
import threading

import common

DOES = ("choice", "press", "reply", "none")
# the standard buttons a pick may name, with the words its button carries
PRESSES = {"done": "Done", "got_it": "Got it", "later": "Snooze to tomorrow", "approve": "Go ahead",
           "not_needed": "Not needed", "wait_longer": "Keep waiting", "no": "No", "drop": "Drop"}
NOT_DECISIONS = ("undo", "read", "bring_back", "old_card", "update_not_now", "rule_book_edit")
SAME = {}       # Done (a task finished), Got it (read, nothing asked) and Drop (not to be considered) are three answers
TEXT_MAX = 60
GIST_MAX = 200
HABITS = os.path.join(common.PERSONAL, "pick_habits.json")      # what he did instead of the pick, by kind of card
HABITS_MOST = 500
PROGRAM_CARDS = ("live:rsi-", "live:level-", "rule:", "live:standing-", "live:projwrite-", "live:newsender-", "live:setup-",
                 "live:wouldhide-",
                 "live:old-cards", "live:review-", "task:system::")     # their own fixed buttons: the first one is the pick
_lock = threading.Lock()
_written = {"picks": 0, "chars": 0, "cards": 0}


def _words(s, most):
    s = " ".join(str(s or "").split())
    return s if len(s) <= most else ""


def from_writer(raw, choices=None):
    """A pick as the card writer wrote it, checked: {"do", ...}, or None when it cannot be used. A choice must be one of the
    card's own choices, word for word (case aside)."""
    if not isinstance(raw, dict) or raw.get("do") not in DOES:
        return None
    do = raw["do"]
    if do == "choice":
        t = _words(raw.get("text"), TEXT_MAX)
        known = {str(c.get("text") if isinstance(c, dict) else c).strip().lower(): c for c in choices or []}
        if not t or t.lower() not in known:
            return None
        c = known[t.lower()]
        return {"do": "choice", "text": str(c.get("text") if isinstance(c, dict) else c).strip(), "by": "writer"}
    if do == "press":
        return {"do": "press", "press": raw["press"], "by": "writer"} if raw.get("press") in PRESSES else None
    if do == "reply":
        g = _words(raw.get("gist"), GIST_MAX)
        return {"do": "reply", "gist": g, "by": "writer"} if g else None
    return {"do": "none", "by": "writer"}


def _key(it):
    return str((it or {}).get("source_key") or "")


def _extra(it):
    ex = (it or {}).get("extra")
    if isinstance(ex, str):
        try:
            ex = json.loads(ex)
        except ValueError:
            ex = None
    return ex if isinstance(ex, dict) else {}


def _choices(it):
    return (it or {}).get("choices") or _extra(it).get("choices") or []


def default(it):
    """The program's pick: the card's recommended choice; Go ahead on a draft, a proposed rule or a recommended step; Got it on a
    card that needs nothing; Keep waiting on a card back from waiting; else leave it as it is."""
    import card
    rec = next((c for c in _choices(it) if isinstance(c, dict) and c.get("recommended")), None)
    if rec:
        return {"do": "choice", "text": str(rec.get("text") or rec.get("label") or "").strip(), "by": "program"}
    need = card.needs(it)
    if it.get("draft") or it.get("rule"):
        return {"do": "press", "press": "approve", "by": "program"}
    if need == "nothing":
        return {"do": "press", "press": "got_it", "by": "program"}
    if it.get("came_back") or _extra(it).get("came_back"):
        return {"do": "press", "press": "wait_longer", "by": "program"}
    if need in ("answer", "approval", "do") and " ".join(str(it.get("recommended") or "").split()):
        return {"do": "press", "press": "approve", "by": "program"}
    return {"do": "none", "by": "program"}


def of(it, closed_too=False):
    """The card's pick as it stands, or None on a closed or Someday card (closed_too: still read, for something he did after
    closing it, such as a reply sent from his mail) and on a card with its own fixed buttons (PROGRAM_CARDS, a mod's card):
    there the first of its own buttons is already what it would do."""
    it = it or {}
    if (not closed_too and (it.get("state") == "done" or it.get("shelf") == "someday")) \
            or _key(it).startswith(PROGRAM_CARDS) or it.get("rsi"):
        return None
    try:
        import mods
        if mods.owns(it):
            return None
    except Exception:  # noqa: BLE001
        pass
    try:                    # a pick rule the owner promoted (work_rules.py) sets the pick for cards it matches
        import work_rules
        ruled = work_rules.pick_for(it)
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"pick rule: {type(e).__name__}: {e}")
        ruled = None
    if ruled:
        return ruled
    got = it.get("pick") if isinstance(it.get("pick"), dict) else _extra(it).get("pick")
    if isinstance(got, dict) and got.get("do") in DOES:
        if got["do"] != "choice" or any(str(c.get("text") if isinstance(c, dict) else c).strip().lower() == str(got.get("text")).lower()
                                       for c in _choices(it)):
            return {k: v for k, v in got.items() if k != "label"}
    return default(it)


def label(p):
    if not p:
        return ""
    if p["do"] == "choice":
        return p["text"]
    if p["do"] == "press":
        return PRESSES.get(p["press"], p["press"])
    if p["do"] == "reply":
        return "Draft a reply: " + p["gist"]
    return "Leave it as it is"


def shown(it):
    """The pick as the page draws it, or None."""
    p = of(it)
    return dict(p, label=label(p)) if p else None


# --- what he did, against the pick -------------------------------------------------------------------------------------
def did_of(press, choice="-", words=""):
    """What he did in the pick's shape: a choice's words, a standard press, his typed words, or leaving it."""
    press = str(press or "")
    if press == "choice":       # the choice's own words (what the page sends), else its button's label
        return {"do": "choice", "text": " ".join(str(words or choice or "").split())[:TEXT_MAX * 2]}
    if press == "words":
        return {"do": "words", "words": " ".join(str(words or "").split())[:300]}
    if press == "leave":
        return {"do": "none"}
    if press == "sent":
        return {"do": "reply", "gist": " ".join(str(words or "").split())[:GIST_MAX]}
    return {"do": "press", "press": press}


def outcome(pick, did, took_pick=False):
    """matched when he did what the pick said (or pressed the pick itself), differed when he did something else, None when
    there was no pick or what he did decides nothing."""
    if not pick or not did or (did.get("do") == "press" and did.get("press") in NOT_DECISIONS):
        return None
    if took_pick:
        return "matched"
    d, p = did.get("do"), pick.get("do")
    if p == "choice" and d == "choice":
        return "matched" if did.get("text", "").lower() == pick.get("text", "").lower() else "differed"
    if p == "press" and d == "press":
        return "matched" if SAME.get(did["press"], did["press"]) == SAME.get(pick["press"], pick["press"]) else "differed"
    if p == "reply" and d == "reply":
        return "matched"
    if p == "none" and d == "none":
        return "matched"
    return "differed"


def habit_key(it):
    """A card like this one: the same sender, else the same area and kind."""
    it = it or {}
    who = it.get("sender") if isinstance(it.get("sender"), dict) else _extra(it).get("sender")
    who = who if isinstance(who, dict) else {}
    if who.get("key"):
        return "sender:" + str(who["key"]).lower()
    return "kind:" + str(it.get("area") or "").strip().lower() + "|" + str(it.get("kind") or "").strip().lower()


def remember(it, did):
    """He did something other than the pick: kept as what he did last time for cards like this one, with how often. Never
    raises. A replay day keeps nothing."""
    try:
        if os.environ.get("ASSISTANT_REPLAY") == "1" or not did or did.get("do") not in ("choice", "press", "words", "reply", "none"):
            return False
        k = habit_key(it)
        with _lock:
            got = common.read_json(HABITS, {}) or {}
            was = got.get(k) or {}
            same = {x: was.get("did", {}).get(x) for x in did} == did
            got[k] = {"did": did, "count": (int(was.get("count") or 0) + 1) if same else 1,
                      "at": common.now().isoformat(timespec="seconds"), "card": (it or {}).get("id")}
            for old in sorted(got, key=lambda x: got[x].get("at", ""))[:-HABITS_MOST]:
                got.pop(old)
            common.write_json(HABITS, got)
        return True
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"pick habit: {type(e).__name__}: {e}")
        return False


def _habit_label(did):
    if did.get("do") == "choice":
        return did.get("text") or ""
    if did.get("do") == "words":
        w = did.get("words") or ""
        return w if len(w) <= TEXT_MAX else ""
    if did.get("do") == "press":
        return PRESSES.get(did.get("press")) or ""
    if did.get("do") == "reply":
        return "Draft a reply: " + (did.get("gist") or "") if did.get("gist") else ""
    return "Leave it as it is"


def habit(it):
    """What he did instead of the pick on the last card like this one (habit_key), with its button's words: {do, label,
    text|press|gist|words, count}; None when nothing is kept or it has no words a button could carry."""
    try:
        h = (common.read_json(HABITS, {}) or {}).get(habit_key(it))
    except Exception:  # noqa: BLE001
        return None
    if not h or not isinstance(h.get("did"), dict):
        return None
    lab = _habit_label(h["did"])
    return dict(h["did"], label=lab, count=int(h.get("count") or 1)) if lab else None


def last_time(it):
    """What he did on the last card like this one when it was not the pick, as a button the page can offer: {do, label,
    text|press|gist|words, count}; None when nothing is kept, it is the pick now, or it is already one of the card's choices."""
    h, p = habit(it), of(it)
    if not h or not p:
        return None
    did = {k: v for k, v in h.items() if k not in ("label", "count")}
    if outcome(p, did) == "matched":
        return None
    if did.get("do") in ("choice", "words") and h["label"].lower() in {str(c.get("text") if isinstance(c, dict) else c).strip().lower() for c in _choices(it)}:
        return None
    return h


def grow(entry, like):
    """The choices grow (the judgment rebuild, "The new loop" point 5): what he did instead of the pick on the last card like
    this one (like: {"sender", "area", "kind"}) becomes one of this card's own choices, when the card asks him something it
    answers (state question or yours, with asks) and it is a choice or a few words of his. entry: the written card, changed in
    place. Returns the words added, or None. A press (Drop, Snooze...) is a standard button already; a reply stays the Last
    time button (last_time)."""
    h = habit(like)
    if not h or h.get("do") not in ("choice", "words") or entry.get("state") not in ("question", "yours") or not entry.get("asks"):
        return None
    lab = h["label"]
    if not lab or len(lab) > TEXT_MAX:
        return None
    have = [c for c in entry.get("choices") or [] if c]
    if lab.lower() in {str(c.get("text") if isinstance(c, dict) else c).strip().lower() for c in have}:
        return None
    entry["choices"] = [{"text": lab, "meaning": "other"}] + have
    return lab


# --- cost ----------------------------------------------------------------------------------------------------------
def note_written(picks, chars, cards):
    _written["picks"] += picks
    _written["chars"] += chars
    _written["cards"] += cards


def reset():
    _written.update(picks=0, chars=0, cards=0)


def cost_line(writer_tokens=None):
    """The pick's cost this pass, for the pass log: picks the card writer wrote, the characters they took and about how many
    output tokens that is (an estimate: 4 characters a token), against the writer's whole output when known. The pick adds
    no AI runs of its own; a card the writer gave no pick gets the program's, at no AI cost."""
    n, ch, cards = _written["picks"], _written["chars"], _written["cards"]
    est = round(ch / 4)
    share = f" of the writer's {writer_tokens} output tokens ({est * 100 / writer_tokens:.1f}%)" if writer_tokens else ""
    return (f"picks: {n} of {cards} written card(s) picked by the writer, about {est} output tokens (estimate){share},"
            f" 0 extra AI runs")
