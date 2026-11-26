r"""Learning from his edits to my drafts (the judgment rebuild, phase 3, "Writing").

Program code only, never Claude. When he sends a draft I wrote (an email from Drafts, a text from the Texts part), what I
drafted is compared with what went out (voice.compare): an unchanged send is a full match; a rewrite says what changed. Either
way it is one rule book row (kind of work: replies), and its lesson for the voice is kept aside until he next runs the voice
builder (voice.learn_edit). A replay writes
nothing (rule_book._append).

    on_sent(drafted, sent, channel, to, ...)   the row and the profile's lesson for one sent draft; never raises
    score()                                    how much of my drafts he kept, from the rule book's active rows
    score_line()                               the same in plain words, for Settings beside the learning levels
"""
import os
import uuid

import common

GIST = 200
NO_SCORE = "No drafts of mine sent yet"


def _log(what, e):
    common.log_line(os.path.join(common.LOGS, "errors.log"), f"writing {what}: {type(e).__name__}: {e}")


def on_sent(drafted, sent, channel, to="", name="", subject="", card=None, key=""):
    """One sent draft: the row (message "draft:<card id or key>") and the voice's lesson. Returns compare()'s result, or None
    when there was no draft of mine to compare or it could not be recorded."""
    if not str(drafted or "").strip() or not str(sent or "").strip():
        return None
    try:
        import rule_book
        import voice
        if rule_book._replaying():
            return None
        got = voice.learn_edit(drafted, sent, channel, to, name)
        who = name or (", ".join(to) if isinstance(to, (list, tuple)) else str(to or ""))
        c = card if isinstance(card, dict) else {}
        ref = c.get("id") or key or uuid.uuid4().hex[:12]
        row = {"id": uuid.uuid4().hex[:16], "at": common.now().isoformat(timespec="seconds"), "message": f"draft:{ref}",
               "section": "replies", "card": c.get("id"), "card_kind": c.get("kind"), "card_area": c.get("area"),
               "call": None, "layer": "owner", "verdict": None, "source": None, "rules": [], "covered": None, "leaned_on": None,
               "seen": {"sender": who[:120], "what": (" ".join(str(subject or "").split()) or " ".join(str(sent).split()))[:160],
                        "channel": channel},
               "press": "sent_draft", "meaning": "neutral", "button": "-", "choice": "-", "status": "active",
               "pick_outcome": "matched" if got["unchanged"] else "differed",
               "draft_edit": {"outcome": "unchanged" if got["unchanged"] else "rewritten", "kept": got["kept"],
                              "changes": got["changes"], "channel": voice.group_of(channel),
                              "drafted": " ".join(str(drafted).split())[:GIST], "sent": " ".join(str(sent).split())[:GIST]}}
        rule_book._append([row])
        return got
    except Exception as e:  # noqa: BLE001  a send is never troubled by its lesson
        _log("on sent", e)
        return None


def score():
    """{"drafts", "unchanged", "kept"} over the active rule book rows for sent drafts; kept is the average share of my words
    he kept (0 to 100), None when no draft was sent."""
    import rule_book
    got = [r["draft_edit"] for r in rule_book.rows(section="replies") if isinstance(r.get("draft_edit"), dict)]
    if not got:
        return {"drafts": 0, "unchanged": 0, "kept": None}
    return {"drafts": len(got), "unchanged": sum(1 for d in got if d.get("outcome") == "unchanged"),
            "kept": round(100 * sum(float(d.get("kept") or 0) for d in got) / len(got))}


def score_line():
    try:
        s = score()
    except Exception as e:  # noqa: BLE001  a score never costs the page its settings
        _log("score", e)
        return NO_SCORE
    if not s["drafts"]:
        return NO_SCORE
    n = s["drafts"]
    return (f"You kept {s['kept']}% of my words in the {n} draft{'' if n == 1 else 's'} you sent; "
            f"{s['unchanged']} went out unchanged.")
