r"""Every card, open and closed, searched for Talk to your assistant (the judgment rebuild, "One brain": it knows all of your
matters, not a handful).

The chat asks with its cards ACTION (prompts\chat.md); the program searches here and runs the chat again at once with what was
found, so it can count and list cards by their words, their kind, their buttons or their state.

    search(words, kind, button, state, most)   {"count", "open", "closed", "of_all", "cards": [the first `most`]}

Open cards and the lately closed are read as the page has them (items.json, with every button); older closed cards are read
from the store and finished the same way, without the database extras a closed card never shows. Nothing here calls Claude.
"""
import os
import re

import common

MOST = 40
# what a card is, by where it came from, in the words the page and the owner use
TYPES = (("live:wouldhide-", "I'd hide this"), ("live:rsi-", "rule change"), ("rule:", "rule proposal"),
         ("live:newsender-", "new sender"), ("live:ready-", "email to send"), ("live:standing-", "standing approval offer"),
         ("live:review-", "weekly review"), ("live:old-cards", "old cards"), ("live:projwrite-", "project write"),
         ("task:system::", "system"), ("task:calendar::", "calendar"), ("test:", "test card"))
STATES = ("question", "yours", "new", "in_motion", "handled", "done")


def type_of(it):
    key = str(it.get("source_key") or "")
    return next((name for pre, name in TYPES if key.startswith(pre)), "matter")


def _label(c):
    if isinstance(c, dict):
        return str(c.get("label") or c.get("text") or "").strip()
    return str(c or "").strip()


def buttons(it):
    """The buttons the card shows besides the page's standard ones: its pick, its answers to each question, its switches (Hide
    mailings like this, Hide things like this, Keep showing...) and what he did last time."""
    out = []
    for p in (it.get("pick"), it.get("last_time")):
        if isinstance(p, dict) and p.get("label"):
            out.append(str(p["label"]))
    for c in it.get("choices") or []:
        out.append(_label(c))
    for q in it.get("questions") or []:
        for c in (q.get("choices") if isinstance(q, dict) else None) or []:
            out.append(_label(c))
    for s in it.get("switches") or []:
        out.append(_label(s))
    return list(dict.fromkeys(b for b in out if b))


def _all_cards():
    """Every card: as the page has it (items.json) where it is there, else from the store, finished without database extras."""
    shown = {c.get("id"): c for c in (common.read_json(common.ITEMS_JSON, {}) or {}).get("items") or [] if isinstance(c, dict)}
    out = list(shown.values())
    try:
        import card
        import items
        for it in items.rows():
            if it["id"] in shown:
                continue
            try:
                items.lift(it)
                card.fill(it)
            except Exception:  # noqa: BLE001  a card that cannot be finished is still found by its own words
                pass
            out.append(it)
    except Exception as e:  # noqa: BLE001  the page's cards are still searched
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"card search: {type(e).__name__}: {e}")
    return out


def _closed(it):
    return it.get("state") == "done"


def _state_ok(it, state):
    s = str(state or "all").strip().lower().replace(" ", "_")
    if s in ("", "all", "any"):
        return True
    if s in ("open", "not_done"):
        return not _closed(it)
    if s in ("closed", "done", "finished"):
        return _closed(it)
    if s in ("snoozed", "later"):
        return it.get("shelf") == "later" and not _closed(it)
    if s == "someday":
        return it.get("shelf") == "someday"
    if s in ("waiting",):
        return it.get("state") == "in_motion"
    return str(it.get("state") or "") == s


def _hay(it, btns):
    sender = it.get("sender") if isinstance(it.get("sender"), dict) else {}
    parts = [it.get(k) for k in ("id", "title", "header", "short_header", "detail", "why", "wants", "source_who", "source_ref", "area",
                                 "kind", "status", "recommended", "answer", "assistant_did")]
    parts += [type_of(it), sender.get("address"), " ".join(btns), " ".join(str(a) for a in it.get("asks") or [])]
    return " ".join(str(p) for p in parts if p).lower()


def _words(text):
    return [w for w in re.findall(r"[a-z0-9][a-z0-9'@.\-]*", str(text or "").lower()) if len(w) > 1]


def search(words="", kind="", button="", state="all", most=MOST):
    """Cards matching every part given: words (each must be on the card: its title, story, sender, buttons and the rest), kind
    (the card's kind, what it is, or its area: "question", "I'd hide this", "Personal"), button (words of one of its buttons),
    state (all, open, closed, snoozed, someday, waiting, or a card state). Newest first."""
    want_words = _words(words)
    kind_l = " ".join(str(kind or "").lower().split())
    btn_l = " ".join(str(button or "").lower().split())
    got, n_all = [], 0
    for it in _all_cards():
        n_all += 1
        if not _state_ok(it, state):
            continue
        if kind_l and not any(kind_l in str(x or "").lower() for x in (it.get("kind"), type_of(it), it.get("area"))):
            continue
        btns = buttons(it)
        if btn_l and not any(btn_l in b.lower() for b in btns):
            continue
        if want_words:
            hay = _hay(it, btns)
            if not all(w in hay for w in want_words):
                continue
        got.append((it, btns))
    got.sort(key=lambda x: str(x[0].get("source_when") or x[0].get("created_at") or ""), reverse=True)
    return {"asked": {k: v for k, v in (("words", words), ("kind", kind), ("button", button), ("state", state)) if v},
            "count": len(got), "open": sum(1 for it, _b in got if not _closed(it)), "closed": sum(1 for it, _b in got if _closed(it)),
            "of_all": n_all,
            "cards": [{"id": it.get("id"), "header": it.get("header") or it.get("title"), "what": type_of(it), "kind": it.get("kind"),
                       "area": it.get("area"), "state": it.get("state"), "status": it.get("status"),
                       "from": it.get("source_ref") or it.get("source_who"), "when": str(it.get("source_when") or "")[:16] or None,
                       "buttons": b} for it, b in got[:max(0, int(most or MOST))]]}


def for_action(action):
    """The search a cards ACTION asks for (prompts\\chat.md)."""
    a = action if isinstance(action, dict) else {}
    try:
        most = int(a.get("most") or MOST)
    except (TypeError, ValueError):
        most = MOST
    return search(a.get("words") or "", a.get("kind") or "", a.get("button") or "", a.get("state") or "all", min(most, 200))
