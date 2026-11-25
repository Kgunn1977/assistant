r"""What every card carries so the page can show it short: the fields the machinery itself guarantees.

ITEMS.md ("Design round 1") is the contract. Nothing here calls Claude and nothing here opens the
database: each field is worked out from the card as it stands, so every card has them, old or new,
whatever wrote it.

    header   the card's one line: a whole short phrase written for it, else the whole title. Never cut.
    needs    what kind of thing the card needs: answer, approval, do, waiting, nothing
    wants    the one thing wanted from the owner, one line (None when it waits or needs nothing)
    why      why it is here, one line (Claude's words when the card has them, else a plain line); when the judge said
             no rule decides a message behind it ("uncovered", its best guess, put there by items.read), the line
             starts "My rules don't cover this; my best guess: ..."
    pick     what I predict the owner will do, drawn as the card's first button (picks.shown); None on a closed card
    last_time what he did instead of the pick on the last card like this one, offered as a button (picks.last_time)
"""
import datetime as dt
import re

import common

HEADER_MAX = 90         # two lines of a phone at normal text size
WANTS_MAX = 140
WHY_MAX = 120
NEEDS = ("answer", "approval", "do", "waiting", "nothing")
NEXT_STEP = "Your next step: "
WHY_SENTENCES = 2                   # the why on the front: a summary of two sentences at most, with no label
UNCOVERED = "You haven't told me how to handle this kind yet. My guess: "
UNCOVERED_WAS = "My rules don't cover this; my best guess: "      # the same line as saved on older cards


DOTS = re.compile(r"\s*(?:\.{2,}|\u2026)+\s*$")


def whole(text):
    """text on one line, whole: nothing is ever cut, and it never ends in dots."""
    return DOTS.sub("", " ".join(str(text or "").split()))


def clip(text, most):
    """Kept for callers of the old name: the text whole, on one line. Nothing is cut any more."""
    return whole(text)


def header_of(title, short=None):
    """The card's header: the short phrase written for it when it has one, else its whole title."""
    return whole(short) or whole(title) or "(no title)"


def needs(it):
    """What kind of thing the card needs from the owner, from its state, draft, questions and buttons."""
    state = it.get("state")
    if state in ("question", "yours"):          # typed words being read leave it here, with its questions and buttons
        if it.get("draft") or (it.get("kind") == "approval" and state == "question"):
            return "approval"
        return "answer" if state == "question" else "do"
    if state == "in_motion":
        return "waiting"
    return "nothing"            # handled, done, just arrived: it only informs


def _choice_words(choices):
    words = [str(c.get("text") if isinstance(c, dict) else c).strip() for c in choices or []]
    words = [w for w in words if w]
    if not words:
        return ""
    return "Choose: " + (", ".join(words[:-1]) + " or " + words[-1] if len(words) > 1 else words[0]) + "."


def wants(it, need=None):
    """The one thing wanted from the owner, one line; None when the card waits or needs nothing.
    The first question, else the recommended step, else the draft, calendar or buttons line."""
    need = need or needs(it)
    if need in ("waiting", "nothing"):
        return None
    asks = [" ".join(str(a or "").split()) for a in it.get("asks") or []]
    asks = [a for a in asks if a]
    if asks:
        a = asks[0][len(NEXT_STEP):] if asks[0].startswith(NEXT_STEP) else asks[0]
        more = f" (and {len(asks) - 1} more; open the card)" if len(asks) > 1 else ""
        return clip(a[:1].upper() + a[1:], WANTS_MAX) + more
    draft = it.get("draft")
    if isinstance(draft, dict):
        to = ", ".join(str(a) for a in (draft.get("to") or [])[:2])
        return clip(f"Approve or change the draft{' to ' + to if to else ''}.", WANTS_MAX)
    cal = it.get("calendar")
    if isinstance(cal, dict) and cal.get("title") and not cal.get("chosen"):
        return clip(f"Choose the day and time for {cal['title']}.", WANTS_MAX)
    said = _choice_words(it.get("choices"))
    if said:
        return clip(said, WANTS_MAX)
    rec = " ".join(str(it.get("recommended") or "").split())
    if rec:
        return clip(rec, WANTS_MAX)
    return {"answer": "Answer this, or press Done if it is settled.",
            "approval": "Say yes or no to this.",
            "do": "Do this, then press Done."}[need]


def _day(value):
    try:
        d = value if isinstance(value, (dt.datetime, dt.date)) else dt.datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return ""
    return f"{d.month}/{d.day}"


def why(it):
    """Why the card is here, one line without the words "Here because:". Claude's line when the card
    carries one; otherwise a plain line from who it came from and when."""
    said = " ".join(str(it.get("why") or "").split())
    if said.lower().startswith("here because"):
        said = said.split(":", 1)[-1].strip() if ":" in said[:16] else said[12:].strip()
    if said.startswith(UNCOVERED_WAS):
        said = UNCOVERED + said[len(UNCOVERED_WAS):]
    if said.startswith(UNCOVERED):
        return said             # already worded by fill() for an uncovered verdict: kept whole
    if said:
        return two_sentences(said[:1].upper() + said[1:])
    who, day = " ".join(str(it.get("source_who") or "").split()), _day(it.get("source_when"))
    if who.split(":", 1)[0].strip().lower() in common.sender_kinds() and ":" in who:
        who = who.split(":", 1)[1].strip()          # a sender as the messages name it ("Email: Pat"), shown as the person
    if who in ("You", common.owner()):
        return f"You added it on {day}." if day else "You added it."
    if who and day:
        return clip(f"{who} wrote to you on {day}.", WHY_MAX)
    if who:
        return clip(f"It came from {who}.", WHY_MAX)
    made = _day(it.get("created_at"))
    return f"It has been on your list since {made}." if made else "It is on your list."


def two_sentences(text):
    """The text whole up to the end of its second sentence."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", whole(text))
    return " ".join(parts[:WHY_SENTENCES]).strip()


def questions(it, extra):
    """Every open question with its own choices and recommended answer, in order: [{"ask", "choices": [{label, text,
    recommended?}]}]. The writer's per-question choices when it gave them; else the card's choices go with the first."""
    asks = [whole(a) for a in it.get("asks") or [] if isinstance(a, str) and whole(a)]
    kept = {whole(q.get("ask")).lower(): q.get("choices") or [] for q in extra.get("questions") or []
            if isinstance(q, dict) and q.get("ask")}
    out = []
    for n, a in enumerate(asks):
        ch = kept.get(a.lower())
        if ch is None:
            ch = (it.get("choices") or []) if n == 0 else []
        out.append({"ask": a, "choices": [c for c in ch if isinstance(c, (dict, str))]})
    return out


def fill(it):
    """Put the guaranteed fields on one card (changed in place and returned)."""
    need = needs(it)
    it["header"] = header_of(it.get("title"), it.get("short_header"))
    it["needs"] = need
    it["wants"] = wants(it, need)
    it["why"] = why(it)
    guess = whole(it.get("uncovered")).rstrip(".!? ")
    if guess and not it["why"].startswith(UNCOVERED):       # the judge's own best guess, said as one: never silent
        it["why"] = f"{UNCOVERED}{guess}. {it['why']}"
    if it.get("shelf") not in ("later", "someday"):
        it["shelf"] = None
    if it["shelf"] != "later":
        it["later_until"] = None
    if not isinstance(it.get("last_press"), dict):
        it["last_press"] = None
    extra = it.get("extra") if isinstance(it.get("extra"), dict) else {}
    for k in ("rule", "came_back", "old_cards", "offer", "review", "write", "project", "update", "ready", "waiting_on",     # a rule proposal, a card back from waiting, the old cards, an offer, the review
              "rule_offer", "rule_scan",            # a rule proposed from his words on this card, and what an approved rule did to other cards
              "rsi"):                               # a rule change card: the one change, its scores, Promote or Apply (rsi_loop.py)
        it[k] = extra.get(k) or None
    if not it.get("choices") and extra.get("choices"):
        it["choices"] = extra["choices"]          # the writer's answers to the first question, as buttons
    if isinstance(it.get("choices"), list):         # a generic "Yes, as recommended" kept from before: it named no action
        it["choices"] = [c for c in it["choices"] if str(c.get("label") if isinstance(c, dict) else c).strip() != "Yes, as recommended"] or None
    # the recommendation is on the front when no button carries it (ITEMS.md: rec_front)
    marked = any(isinstance(c, dict) and c.get("recommended") for c in it.get("choices") or [])
    it["rec_front"] = " ".join(str(it.get("recommended") or "").split()) or None \
        if it.get("needs") in ("answer", "approval", "do", "waiting") else None      # on the front of every card that has one
    cb = it.get("came_back")
    if isinstance(cb, dict) and str(cb.get("who") or "").strip() in ("You", "you", common.owner()):
        it["came_back"] = None          # a note that named the owner as the one waited on (kept from before 11/18): never shown
    it["teach"] = teach(it)
    it["switches"] = switches(it)
    it["questions"] = questions(it, extra) if it.get("state") in ("question", "yours") else []
    # a card of several questions: each one answered is a small card of its own, closed, shown with its answer, what was
    # done for it and Change, until every one is answered and the card closes (answers.py); one asked again is open
    open_now = {whole(a).lower() for a in it.get("asks") or [] if isinstance(a, str)}
    it["answered"] = [{k: a.get(k) for k in ("ask", "answer", "did", "at")} for a in extra.get("answered") or []
                      if isinstance(a, dict) and a.get("ask") and whole(a["ask"]).lower() not in open_now] \
        if it.get("state") not in ("done",) else []
    import picks        # what I predict he will do, his first button; and what he did instead on the last card like it
    it["pick"] = picks.shown(it)
    it["last_time"] = picks.last_time(it) if it["pick"] else None
    import dates
    return dates.show_card(it)      # every day marker becomes today, tomorrow, yesterday or the date, as of now


SEEN_STATUS = "Shown at your asking"       # a card the owner asked for from the Hidden list


def switches(it):
    """The switchable standard buttons this card shows, in order, as [{"id", "label"}] (presses.SWITCHES), decided here from
    what the card is about (guardrail A4), never by Claude: Hide mailings like this on an open card whose newest email is a
    mailing by rule 559's own test (items.mailing_for, kept as "mailing"); Keep showing these on an open card from an outside
    sender that needs nothing of the owner; Hide things like this and Keep showing on an "I'd hide this" card (wouldhide.py).
    None on the system's own cards, a rule change card, or a done or Someday card."""
    import presses
    key = str(it.get("source_key") or "")
    if key.startswith(presses.WOULD_HIDE):      # the "I'd hide this" card: its own two buttons, by their own labels
        if it.get("state") == "done" or it.get("shelf") == "someday":
            return []
        return [{"id": n, "label": presses.switch_label(it, n)} for n in ("hide_like_this", "keep_showing")]
    if it.get("state") == "done" or it.get("shelf") == "someday" or not it.get("source_messages")             or key.startswith(("rule:", "live:old-cards", "live:newsender-", "live:setup-", "live:standing-", "live:review-", "live:projwrite-",
                               "live:rsi-", "live:ready-", "task:system::")):
        return []
    out = []
    if it.get("mailing") is True:
        out.append("hide_like_this")
    if isinstance(it.get("sender"), dict) and needs(it) == "nothing":
        out.append("keep_showing")
    return [{"id": n, "label": presses.SWITCHES[n]["label"]} for n in out]


def teach(it):
    """The teaching choices the page may offer on this card, in order (ITEMS.md, "Design round 2")."""
    key = str(it.get("source_key") or "")
    if it.get("state") == "done" or key.startswith(("rule:", "live:old-cards", "live:newsender-", "live:setup-", "live:standing-", "live:review-", "live:projwrite-", "live:rsi-", "live:wouldhide-", "task:system::")):
        return []
    who = it.get("sender") if isinstance(it.get("sender"), dict) else None
    if not who:
        return ["not_needed_this"]
    if it.get("status") == SEEN_STATUS:
        return ["always_sender", "always_kind"]
    return ["not_needed_this"] + (["not_needed_sender"] if who.get("can_junk") else []) + ["not_needed_kind"]
