r"""Presses: what each button on a card does, and the one table that records every press.

ITEMS.md ("Design round 1") is the contract. A press arrives as an answer whose text is JSON
({"press": {"name": ...}}) or in one of the older forms (done, reopen, approve, later, snooze).
A plain press is acted on at once and never starts Claude. Words the owner typed are not a press
and go to Claude as before (answers.py).

    parse(item, rec)             the press an answer carries, or None when it carries words
    chosen(rec)                  a pressed choice's button id and meaning, checked against MEANINGS
    meaning_of(press)            the one meaning a press records
    fields(item, press, when)    the columns the press changes (pure: same card and press, same result)
    junk_list(item, name)        Junk / Never junk: the owner's lists, written the same moment
    record(...)                  one row in live_presses (waits in a file while a pass holds the database)

Nothing here sends anything, and nothing here opens the database except record() and flush().
"""
import datetime as dt
import json
import os
import sys
import threading

import card
import common

NAMES = ("done", "got_it", "got_it_all", "later", "someday", "bring_back", "junk", "never_junk", "approve", "undo",
         # round 2: teaching presses, a rule card's No, a card back from waiting, the old cards, the Hidden list
         "not_needed", "always_show", "no", "wait_longer", "write_them", "drop", "old_card", "old_keep", "should_have_seen",
         "read", "standing", "write",
         # the weekly update card
         "update_start", "update_not_now",
         # a draft in Ready to send
         "discard",
         # a rule proposed from his words on a card: Approve, Disapprove, Discuss or Cancel (card_rules.py)
         "rule_offer",
         # a rule change card (rsi_loop.py): Promote a rule change, Apply a setting or list change, Reject either
         "rsi_promote", "rsi_apply", "rsi_reject",
         # the switchable standard buttons (SWITCHES): shown only where card.switches says
         "hide_like_this", "keep_showing",
         # the pick "Leave it as it is" (picks.py): recorded, the card unchanged
         "leave")
# What a press says about the assistant's call on the card, one of these and nothing else (the RSI plan, "Cards and buttons").
MEANINGS = ("agrees",            # he went along with what the card proposed or decided
            "disagrees",         # he said no to what it proposed (a rule, a standing approval, a project write)
            "contradicts-show",  # it should not have been shown
            "contradicts-hide",  # it should not have been hidden
            "wrong-section",     # the right card in the wrong part of the page
            "not-needed",        # he did not need this
            "needed",            # he needed this
            "other",             # a choice that names no call
            "neutral")           # says nothing about any call: Got it, Done, Snooze and the rest
_MEANING_OF = {"approve": "agrees", "no": "disagrees", "not_needed": "not-needed", "always_show": "needed",
               "should_have_seen": "contradicts-hide", "junk": "not-needed", "never_junk": "needed",
               "sender_show": "needed", "sender_hold": "not-needed",
               "rsi_promote": "agrees", "rsi_apply": "agrees", "rsi_reject": "disagrees"}
# The switchable standard buttons (the RSI plan, "Cards and buttons"): program code decides which a card shows (card.switches,
# guardrail A4), each is its own press with its meaning fixed here, never sent by the page, and each names the show-or-hide
# call it asks for, so the grader counts it against the call made (grader.signal). Pressing one records it and closes the card;
# it changes no setting, list or rule itself. At learning level 1 (level 2 while no rule change is open for the section) answers.py
# then offers a rule through the teach flow, as "This kind of message" does: a rule card, nothing in force until Approve.
SWITCHES = {"hide_like_this": {"label": "Hide mailings like this", "meaning": "contradicts-show", "call": "hide"},
            "keep_showing": {"label": "Keep showing these", "meaning": "agrees", "call": "show"}}
_MEANING_OF.update({k: v["meaning"] for k, v in SWITCHES.items()})
# The "I'd hide this" card (wouldhide.py, guardrail A13 as amended) offers the same two presses under its own labels: Hide things
# like this offers a hide rule through the teach flow as Hide mailings like this does; Keep showing only records its row.
WOULD_HIDE = "live:wouldhide-"
WOULD_HIDE_LABELS = {"hide_like_this": "Hide things like this", "keep_showing": "Keep showing"}


def is_would_hide(item):
    return str((item or {}).get("source_key") or "").startswith(WOULD_HIDE)


def switch_label(item, name):
    """A switchable button's label as this card shows it."""
    if is_would_hide(item) and name in WOULD_HIDE_LABELS:
        return WOULD_HIDE_LABELS[name]
    return SWITCHES[name]["label"]
OFFER_DOES = ("approve", "disapprove", "discuss", "cancel")
SCOPES = ("this", "sender", "kind")
ANSWER_WORDS = ("Answered", "Thinking", "Done", "Approved")
NEW_SENDER = "live:newsender-"      # the card that asks once about a first-time sender
SHOW_THEM, HOLD_THEM = "Show their mail", "Hold it"
WHENS = ("today", "tomorrow", "next_week", "date", "someday")
ALL_KEY = "press"               # the key and id a press on no single card arrives on (got_it_all, and its undo)
BACK_HOUR = 6                   # a card put off to a day returns at 6:00 AM that day
LATER_TODAY_HOURS = 3
JUNK_ASK = "task:system::noise rule proposals"      # the card that asks about senders judged junk three times


def is_junk_ask(item):
    """The card that asks Junk or Never junk about a sender judged junk three times: one card per sender
    (JUNK_ASK + "::<rule id>"), or the older card that asked about every waiting sender at once."""
    k = str((item or {}).get("source_key") or "")
    return k == JUNK_ASK or k.startswith(JUNK_ASK + "::")


def junk_ask_rule(item):
    """The waiting junk proposal a one-sender question card asks about, or None for the older card."""
    k = str((item or {}).get("source_key") or "")
    tail = k[len(JUNK_ASK) + 2:] if k.startswith(JUNK_ASK + "::") else ""
    return int(tail) if tail.isdigit() else None
WAITING = os.path.join(common.HOME, "presses_waiting.jsonl")
LAST_ALL = os.path.join(common.HOME, "state", "last_got_it_all.json")
_file_lock = threading.Lock()

DDL = """
CREATE SEQUENCE IF NOT EXISTS seq_live_press START 1;
CREATE TABLE IF NOT EXISTS live_presses (
  id          BIGINT PRIMARY KEY DEFAULT nextval('seq_live_press'),
  pressed_at  TIMESTAMP NOT NULL,
  received_at TIMESTAMP NOT NULL,
  item_id     VARCHAR NOT NULL,
  item_title  VARCHAR NOT NULL,
  press       VARCHAR NOT NULL,
  choice      VARCHAR NOT NULL,
  words       VARCHAR NOT NULL,
  device      VARCHAR NOT NULL,
  happened    VARCHAR NOT NULL,
  ok          BOOLEAN NOT NULL,
  claude_ran  BOOLEAN NOT NULL,
  secs        DOUBLE NOT NULL,
  meaning     VARCHAR NOT NULL,
  button      VARCHAR NOT NULL
);
"""
# a table made before presses carried a meaning gets the columns: meaning filled from each row's press (_fill_meanings), button "-"
MIGRATE = ("ALTER TABLE live_presses ADD COLUMN IF NOT EXISTS meaning VARCHAR;"
           " ALTER TABLE live_presses ADD COLUMN IF NOT EXISTS button VARCHAR;")
COLUMNS = ("pressed_at", "received_at", "item_id", "item_title", "press", "choice", "words", "device",
           "happened", "ok", "claude_ran", "secs", "meaning", "button")


# --- reading a press out of an answer -----------------------------------------------------------
def parse(item, rec):
    """The press this answer carries: {"name": ..., and what the name needs}. None when the answer
    carries the owner's own words (or anything that is not a press), and for a choice button whose meaning is on the list:
    its words are read as before, and its button id and meaning go into the press record (chosen). A choice whose meaning
    is not on the list is refused like a press with an unknown name. Done means done on every card; on a card that asks
    yes or no (a proposed rule, a standing approval offer, a project write) the no is its own press, No."""
    c = chosen(rec)
    if c and "bad" in c:
        return {"name": "unknown", "said": "choice"}
    out = _parse(item, rec)
    if out and out.get("name") == "no":
        key = str((item or {}).get("source_key") or "")
        if key.startswith("live:standing-"):
            return {"name": "standing", "level": "no", "via": "no"}
        if key.startswith("live:projwrite-"):
            return {"name": "write", "level": "no", "via": "no"}
    return out


def chosen(rec):
    """A choice button pressed on a card, as the page sends it beside the choice's words: {"button": its id, "meaning": one
    of MEANINGS}; {"bad": what came} when the id is missing or the meaning is not on the list; None when the answer
    carries neither (typed words, an older page)."""
    rec = rec or {}
    if rec.get("action") != "answer" or (rec.get("button") is None and rec.get("meaning") is None):
        return None
    m, b = rec.get("meaning"), " ".join(str(rec.get("button") or "").split())[:60]
    if not isinstance(m, str) or m not in MEANINGS or not b:
        return {"bad": str(m)[:40]}
    return {"button": b, "meaning": m}


def meaning_of(press):
    """The one meaning a press records, from the fixed list. A press that says nothing about the card's call is neutral."""
    press = press or {}
    name, level = press.get("name"), press.get("level")
    if name == "choice":
        return press.get("meaning") if press.get("meaning") in MEANINGS else "neutral"
    if name in ("standing", "write"):
        return {"tell": "agrees", "quiet": "agrees", "yes": "agrees", "no": "disagrees"}.get(level, "neutral")
    if name == "rule_offer":
        return {"approve": "agrees", "disapprove": "disagrees"}.get(press.get("do"), "neutral")
    return _MEANING_OF.get(name, "neutral")


def _row_meaning(press, choice, happened):
    """The meaning of a row written before presses carried one, from what the row kept."""
    level = choice if choice in ("tell", "quiet", "yes", "no") else None
    if press in ("standing", "write") and level is None:        # older rows kept no level: their own words say which
        h = str(happened or "")
        level = "no" if h.startswith(("No standing approval", "Got it. I'll keep asking", "Nothing was written")) else \
            "yes" if h.startswith(("Done: from the next check", "Done. From the next time I check", "Written into")) else None
    return meaning_of({"name": press, "level": level, "do": choice})


def _parse(item, rec):
    action, page = rec.get("action"), rec.get("page_action")
    text = (rec.get("text") or "").strip()
    if action == "answer" and text.startswith("{"):
        try:
            got = json.loads(text).get("press")
        except (ValueError, AttributeError):
            got = None
        if isinstance(got, dict) and got.get("name") in NAMES:
            out = {"name": got["name"]}
            if out["name"] == "later":
                out["when"] = got.get("when") if got.get("when") in WHENS else "tomorrow"
                out["until"] = str(got.get("until") or "")[:10]
            if out["name"] == "got_it_all" and isinstance(got.get("ids"), list):
                out["ids"] = [str(i) for i in got["ids"] if isinstance(i, str)][:2000]
            if out["name"] == "someday":
                out = {"name": "later", "when": "someday", "until": ""}
            if out["name"] in ("not_needed", "always_show"):
                out["scope"] = got.get("scope") if got.get("scope") in SCOPES else "this"
                words = " ".join(str(got.get("words") or "").split())[:500]
                if words and out["scope"] == "kind":
                    out["words"] = words            # Not needed, Other: what he did not need, in his words
            if out["name"] == "wait_longer":
                d = got.get("days")
                out["days"] = d if isinstance(d, int) and not isinstance(d, bool) and 1 <= d <= 60 else None
            if out["name"] == "write":
                out["level"] = got.get("level") if got.get("level") in ("yes", "no") else None
            if out["name"] in ("update_start", "update_not_now"):
                out["version"] = str(got.get("version") or "")[:20]
            if out["name"] == "standing":
                out["level"] = got.get("level") if got.get("level") in ("tell", "quiet", "no") else None
            if out["name"] == "read":
                out["part"] = got.get("part") if isinstance(got.get("part"), int) and not isinstance(got.get("part"), bool) else 1
            if out["name"] == "rule_offer":
                out["do"] = got.get("do") if got.get("do") in OFFER_DOES else None
                words = " ".join(str(got.get("words") or "").split())[:1500]
                if out["do"] == "discuss" and words:
                    out["words"] = words            # Discuss: his words on how the rule should read
            if out["name"] in ("rsi_promote", "rsi_apply", "rsi_reject"):
                out["proposal"] = str(got.get("proposal") or "")[:60]
                words = " ".join(str(got.get("words") or "").split())[:500]
                if out["name"] == "rsi_reject" and words:
                    out["words"] = words            # Reject: his typed words, kept as the reason
            if out["name"] == "old_card":
                out["card"] = str(got.get("card") or "")[:40]
                out["do"] = got.get("do") if got.get("do") in ("keep", "later", "done", "someday", "drop") else None
                if out["do"] == "later":
                    out["when"] = got.get("when") if got.get("when") in WHENS else "tomorrow"
                    out["until"] = str(got.get("until") or "")[:16]
            return out
        if isinstance(got, dict):
            return {"name": "unknown", "said": str(got.get("name"))[:40]}
    if action == "done":
        return {"name": "done"}
    if action == "reopen":
        return {"name": "undo"}
    if page == "approve":
        return {"name": "approve"}
    if page == "snooze" or (action == "note" and rec.get("until")):
        return {"name": "later", "when": "date", "until": str(rec.get("until") or "")[:10], "old": True}
    if page == "later":
        return {"name": "later", "when": "tomorrow", "until": ""}
    if action == "answer" and is_junk_ask(item) and text.lower() in ("junk", "never junk"):
        return {"name": "junk" if text.lower() == "junk" else "never_junk"}
    if action == "answer" and str((item or {}).get("source_key") or "").startswith("live:projwrite-") and text.lower() in ("yes, write it", "no, do not"):
        return {"name": "write", "level": "yes" if text.lower().startswith("yes") else "no"}
    if action == "answer" and str((item or {}).get("source_key") or "").startswith("live:standing-") \
            and text.lower() in ("yes, do it and notify me", "yes, do it and tell me", "yes, do it quietly", "no"):
        return {"name": "standing", "level": {"yes, do it and notify me": "tell", "yes, do it and tell me": "tell", "yes, do it quietly": "quiet", "no": "no"}[text.lower()]}
    if action == "answer" and str((item or {}).get("source_key") or "").startswith(NEW_SENDER) \
            and text.lower() in (SHOW_THEM.lower(), HOLD_THEM.lower()):
        return {"name": "sender_show" if text.lower() == SHOW_THEM.lower() else "sender_hold"}
    return None


def choice_of(press):
    if press.get("name") == "later":
        return press.get("until") if press.get("when") == "date" and press.get("until") else press.get("when") or "-"
    if press.get("name") == "got_it_all":
        return f"{len(press['ids'])} named" if "ids" in press else "every card that needs nothing"
    if press.get("name") in ("not_needed", "always_show"):
        return press.get("scope") or "this"
    if press.get("name") == "wait_longer":
        return f"{press.get('days') or 'the usual'} working days"
    if press.get("name") == "old_card":
        return f"{press.get('do')} {press.get('card')}"
    if press.get("name") == "rule_offer":
        return press.get("do") or "-"
    if press.get("name") in ("standing", "write"):
        return press.get("level") or "-"
    if press.get("name") == "rsi_reject":
        return "with your words" if press.get("words") else "-"
    return "-"


# --- what a press does to a card (pure) ---------------------------------------------------------
def _stamp(when):
    return f"{when.month}/{when.day} {when.strftime('%I:%M %p').lstrip('0')}"


def _token(d):
    """A day as stored on a card: the page shows it as today, tomorrow, yesterday or the date (dates.py)."""
    return "{day:" + d.isoformat() + "}"


def _day_words(d):
    return f"{d.strftime('%a')} {d.month}/{d.day}"


def _add(text, line):
    return f"{text}\n{line}" if text else line


def _mark(name, when, happened, ok=True, claude=False, opens=None, was=None):
    out = {"press": name, "at": when.isoformat(timespec="seconds"), "happened": happened, "claude": bool(claude),
           "open": opens, "ok": bool(ok)}
    if was is not None:
        out["was"] = was
    return out


def _was(item):
    """Where the card stands now, so an Undo of this press puts it back exactly."""
    def plain(v):
        return v.isoformat() if isinstance(v, (dt.datetime, dt.date)) else v
    out = {k: plain(item.get(k)) for k in ("state", "status", "shelf", "later_until", "checkback_date")}
    if isinstance(item.get("extra"), dict) and item["extra"].get("came_back"):
        out["extra"], out["asks"] = item["extra"], list(item.get("asks") or [])
    return out


def later_until(press, when):
    """(when the card returns or None for someday, the day it returns, problem or None)."""
    kind = press.get("when") or "tomorrow"
    six = lambda d: dt.datetime.combine(d, dt.time(BACK_HOUR, 0))  # noqa: E731
    if kind == "someday":
        return None, None, None
    if kind == "today":
        back = when + dt.timedelta(hours=LATER_TODAY_HOURS)
        return back.replace(microsecond=0), back.date(), None
    if kind == "next_week":
        d = when.date() + dt.timedelta(days=(7 - when.weekday()) or 7)
        return six(d), d, None
    if kind == "date":
        try:
            d = dt.date.fromisoformat(str(press.get("until") or ""))
        except ValueError:
            if press.get("old"):            # the older Snooze with a date that cannot be read: tomorrow, as it always was
                d = when.date() + dt.timedelta(days=1)
                return six(d), d, None
            return None, None, "That day could not be read, so nothing was snoozed."
        if d <= when.date():
            return None, None, "That day is not after today, so nothing was snoozed."
        return six(d), d, None
    d = when.date() + dt.timedelta(days=1)
    return six(d), d, None


def refusal(name, when, why):
    """A press that could not be acted on: the card is unchanged and says why."""
    return {"last_press": _mark(name, when, why, ok=False)}


def fields(item, press, when, legacy):
    """The columns this press changes on this card, always with last_press (what happened, in plain
    words). legacy(rec) is the older transform, used for the presses that already existed so their
    history lines and their handling of settled questions stay exactly as they were."""
    name = press["name"]
    did = item.get("assistant_did")
    need = card.needs(item)
    if name == "unknown":
        return refusal(press.get("said") or "press", when, "I do not know that button, so nothing was changed.")
    if name == "got_it_all":
        return refusal(name, when, "That button marks several cards Done at once and was sent to one card. Nothing was changed.")
    if str(item.get("source_key") or "").startswith("live:rsi-") and item.get("state") != "done"             and name in ("done", "got_it", "later", "drop", "not_needed"):
        # a rule change or setting card closes only by its own Promote, Apply or Reject, so no proposal is left holding its section
        return refusal(name, when, "This card closes only with Approve, Apply or Reject (Reject leaves everything as it is). "
                                   "Nothing was changed.")
    if name == "drop":         # he doesn't want this card considered: closed, not a task done and not a hide (that is Not needed);
        if item.get("state") == "done":     # a new message on the matter reopens it, as for any closed card
            return {"last_press": _mark(name, when, "It was already closed.")}
        return {"state": "done", "status": "Dropped", "shelf": None, "later_until": None, "checkback_date": None,
                "assistant_did": _add(did, f"You dropped it {_stamp(when)}."),
                "last_press": _mark(name, when, "Dropped. I won't bring it up again unless something new comes in about it.",
                                    was=_was(item))}
    if name == "leave":
        return {"assistant_did": _add(did, f"You left it as it is {_stamp(when)}."),
                "last_press": _mark(name, when, "Got it. I'll leave this as it is.")}
    if name == "done":
        f = legacy({"action": "done"})
        f.update(shelf=None, later_until=None)
        f["last_press"] = _mark(name, when, "Marked done." if item.get("state") != "done" else "Done.", was=_was(item))
        return f
    if name == "got_it":
        if item.get("state") == "done":
            return {"last_press": _mark(name, when, "It was already Done.")}
        if need != "nothing":
            return refusal(name, when, "This card still needs something from you, so it was not marked Done. Press Done if it is finished.")
        return {"state": "done", "status": "Got it", "shelf": None, "later_until": None,
                "assistant_did": _add(did, f"You pressed Got it {_stamp(when)}."),
                "last_press": _mark(name, when, "Done.", was=_was(item))}
    if name == "later":
        if item.get("state") == "done":
            return refusal(name, when, "This card is already done, so it was not snoozed.")
        back, day, problem = later_until(press, when)
        if problem:
            return refusal(name, when, problem)
        if press.get("when") == "someday":
            return {"shelf": "someday", "later_until": None, "status": "Someday", "checkback_date": None,
                    "assistant_did": _add(did, f"You snoozed it to Someday {_stamp(when)}."),
                    "last_press": _mark(name, when, "Snoozed to Someday, under Waiting, until you bring it back.", was=_was(item))}
        if press.get("when") == "today":
            to = back.strftime("%I:%M %p").lstrip("0")
            said, status = f"Snoozed until {to} {_token(day)}. It comes back by itself.", f"Snoozed until {to} {_token(day)}"
        else:
            said, status = f"Snoozed until {_token(day)}. It comes back by itself.", f"Snoozed until {_token(day)}"
        return {"shelf": "later", "later_until": back, "status": status, "checkback_date": day,
                "assistant_did": _add(did, f"You snoozed it {_stamp(when)}: back {_day_words(day)}"
                                           + (f" at {back.strftime('%I:%M %p').lstrip('0')}." if press.get("when") == "today" else ".")),
                "last_press": _mark(name, when, said, was=_was(item))}
    if name == "bring_back":
        if not item.get("shelf"):
            return {"last_press": _mark(name, when, "It is already on your page.")}
        st = item.get("status")
        last = item.get("last_press") if isinstance(item.get("last_press"), dict) else {}
        if last.get("press") == "later" and isinstance(last.get("was"), dict):
            st = last["was"].get("status")          # the word it carried before it was put off
        return {"shelf": None, "later_until": None, "checkback_date": None,
                "status": None if str(st or "").startswith(("Later", "Someday", "Snoozed", "Not now")) else st,
                "assistant_did": _add(did, f"You brought it back {_stamp(when)}."),
                "last_press": _mark(name, when, "Back on your page.", was=_was(item))}
    if name in ("junk", "never_junk"):
        who = sender_words(item)
        if not who:
            return refusal(name, when, "This card has no outside sender, so there is nobody to put on a list.")
        if name == "junk":
            if not can_junk(item):
                return refusal(name, when, f"{who} is one of your own, so it is never junk. Nothing was changed.")
            if item.get("state") == "done":
                return {"assistant_did": _add(did, f"You pressed Junk {_stamp(when)}: {who} is on your junk list."),
                        "last_press": _mark(name, when, f"{who} is on your junk list.", was=_was(item))}
            return {"state": "done", "status": "Junk", "shelf": None, "later_until": None,
                    "assistant_did": _add(did, f"You pressed Junk {_stamp(when)}: {who} is on your junk list."),
                    "last_press": _mark(name, when, f"{who} is on your junk list. This card is Done.", was=_was(item))}
        f = {"assistant_did": _add(did, f"You pressed Never junk {_stamp(when)}: {who} is on your never junk list."),
             "last_press": _mark(name, when, f"{who} is on your never junk list. Its mail is always read.", was=_was(item))}
        if is_junk_ask(item) and item.get("state") != "done":
            f.update(state="done", status="Never junk")
        return f
    if name == "approve" and not str(item.get("source_key") or "").startswith("rule:"):
        f = legacy({"action": "answer", "page_action": "approve", "text": ""})
        f.update(shelf=None, later_until=None)
        has_draft = isinstance(item.get("draft"), dict)
        f["last_press"] = _mark(name, when, "Your yes is recorded. Nothing is sent until you press Send." if has_draft
                                else "Your yes is recorded.", opens="writing" if has_draft else None, was=_was(item))
        return f
    key = str(item.get("source_key") or "")
    extra = dict(item.get("extra") or {}) if isinstance(item.get("extra"), dict) else {}
    if name in ("not_needed", "always_show"):
        who = sender_words(item)
        scope = press.get("scope") or "this"
        if key.startswith(("rule:", "live:old-cards", NEW_SENDER)):
            return refusal(name, when, "That button is not for this card. Nothing was changed.")
        if scope in ("sender", "kind") and not who:
            return refusal(name, when, "This card has no outside sender, so there is nothing to learn a sender or a kind from. Nothing was changed.")
        if name == "always_show":
            if scope == "sender":
                return {"assistant_did": _add(did, f"You pressed Always show this sender {_stamp(when)}: {who} always gets through."),
                        "last_press": _mark(name, when, f"{who} is on your list of people who always get through.", was=_was(item))}
            return {"assistant_did": _add(did, f"You asked {_stamp(when)} to always be shown this kind of message. I'm working out a rule to offer you."),
                    "last_press": _mark(name, when, "I'm working out a rule to offer you.", claude=True)}
        again = item.get("state") == "done"      # a wider choice after a narrower one on the same card still counts
        if again and scope == "this":
            return {"last_press": _mark(name, when, "It was already Done.")}
        if scope == "sender" and not can_junk(item):
            return refusal(name, when, f"{who} is one of your own, so it is never ignored. Nothing was changed.")
        said = {"this": "Done. Only this one; nothing else changes.",
                "sender": f"{who} is on your list of senders to always ignore. This card is Done.",
                "kind": "Done. I'm working out a rule to offer you."}[scope]
        line = {"this": "only this one", "sender": f"{who} is on your ignore list", "kind": "this kind of message, and I'm working out a rule to offer you"}[scope]
        f = {"assistant_did": _add(did, f"You pressed I did not need this {_stamp(when)}: {line}."),
             "last_press": _mark(name, when, said, claude=scope == "kind", was=None if again else _was(item))}
        if not again:
            f.update(state="done", status="Not needed", shelf=None, later_until=None)
        return f
    if name == "write":
        # the owner's yes or no to writing into a project's folder; the write itself is done by answers.py before this lands
        w = extra.get("write") if isinstance(extra.get("write"), dict) else None
        if not key.startswith("live:projwrite-") or not w or item.get("state") == "done" or press.get("level") is None:
            return refusal(name, when, "That answer is for a question about writing into a project. Nothing was changed.")
        if press["level"] == "no":
            return {"state": "done", "status": "Not written", "answer": "No", "answered_at": when,
                    "assistant_did": _add(did, f"You said no {_stamp(when)}. Nothing was written."),
                    "last_press": _mark(name, when, "Nothing was written.")}
        return {"state": "done", "status": "Written", "answer": "Yes", "answered_at": when,
                "assistant_did": _add(did, f"You said yes {_stamp(when)}. The file was written."),
                "last_press": _mark(name, when, "Written into the project's folder. It is listed for an uninstall.")}
    if name == "discard":
        if not key.startswith("live:ready-") or item.get("state") == "done":
            return refusal(name, when, "That is for an email waiting in Drafts. Nothing was changed.")
        return {"state": "done", "status": "Discarded", "answer": "Discarded", "answered_at": when, "draft": None,
                "assistant_did": _add(did, f"You discarded this email {_stamp(when)}. It was not sent."),
                "last_press": _mark(name, when, "Discarded. It was not sent.")}
    if name in ("update_start", "update_not_now"):
        up = extra.get("update") if isinstance(extra.get("update"), dict) else None
        if not key.startswith("live:update-") or not up or item.get("state") == "done" or press.get("version") != up.get("version"):
            return refusal(name, when, "That answer is for the update card of another version. Nothing was changed.")
        if name == "update_not_now":
            return {"state": "done", "status": "Not now", "answer": "Not now", "answered_at": when,
                    "assistant_did": _add(did, f"You said not now {_stamp(when)}. If this version still waits next Sunday, the card comes back."),
                    "last_press": _mark(name, when, "Not now. If this version is still waiting next Sunday, it comes back.")}
        return {"state": "in_motion", "status": "Updating", "answer": "Update", "answered_at": when,
                "assistant_did": _add(did, f"You pressed Update {_stamp(when)}. The update walks through in Talk to your assistant at the top of your page."),
                "last_press": _mark(name, when, f"The update to {up.get('version')} is starting in Talk to your assistant at the top of your page.")}
    if name in ("rsi_promote", "rsi_apply", "rsi_reject"):
        # a rule change card (rsi_loop.py): the coach's promote, apply or reject is done by answers.py before this lands
        r = extra.get("rsi") if isinstance(extra.get("rsi"), dict) else None
        fits = r and (name == "rsi_reject" or (name == "rsi_apply") == (r.get("kind") == "setting"))
        if not key.startswith("live:rsi-") or not fits or item.get("state") == "done" or press.get("proposal") != r.get("id"):
            return refusal(name, when, "That answer is for another rule change card. Nothing was changed.")
        if press.get("undecided"):
            return refusal(name, when, "Nothing was changed: this page couldn't reach your computer when you pressed it. Press it again.")
        if name == "rsi_reject":
            return {"state": "done", "status": "Rejected", "answer": "Reject", "answered_at": when,
                    "assistant_did": _add(did, f"You rejected this change {_stamp(when)}"
                                               + (f": \"{press['words']}\"." if press.get("words") else ". Nothing was changed.")),
                    "last_press": _mark(name, when, "Rejected. Nothing was changed, and the reason is kept.")}
        if name == "rsi_promote":
            work = r.get("kind") == "work"
            return {"state": "done", "status": "Promoted", "answer": "Promote", "answered_at": when,
                    "assistant_did": _add(did, f"You promoted this change {_stamp(when)}. "
                                               + ("My picks use it now." if work else "It is in your rules in Settings.")),
                    "last_press": _mark(name, when, "Done. I promoted the change. It starts the next time I check for messages.")}
        return {"state": "done", "status": "Promoted", "answer": "Promote", "answered_at": when,
                "assistant_did": _add(did, f"You promoted this change {_stamp(when)}. It is in Settings."),
                "last_press": _mark(name, when, "Done. I changed it in Settings. It starts the next time I check for messages.")}
    if name == "standing":
        # the only way a standing approval is made from a card: the owner's answer to the offer that earned it
        offer = extra.get("offer") if isinstance(extra.get("offer"), dict) else None
        if not key.startswith("live:standing-") or not offer or item.get("state") == "done" or press.get("level") is None:
            return refusal(name, when, "That answer is for an offer to do something without asking. Nothing was changed.")
        if press["level"] == "no":
            return {"state": "done", "status": "Not made", "answer": "No", "answered_at": when,
                    "assistant_did": _add(did, f"You said no {_stamp(when)}. I keep asking, and offer again only after you've done it yourself that many more times."),
                    "last_press": _mark(name, when, "Got it. I'll keep asking each time.")}
        words = {"tell": "do it and notify me", "quiet": "do it quietly"}[press["level"]]
        return {"state": "done", "status": "You let me do this without asking", "answer": words, "answered_at": when,
                "assistant_did": _add(did, f"You said yes, {words}, {_stamp(when)}. It is in Settings, under Approvals, where you can pause or remove it."),
                "last_press": _mark(name, when, f"Done. From the next time I check for messages, I'll {words} for this. You can pause or remove it in Settings, under Approvals.")}
    if key.startswith("rule:") and name in ("approve", "no"):
        if item.get("state") == "done":
            return {"last_press": _mark(name, when, "This rule card was already answered.")}
        if name == "approve":
            return {"state": "done", "status": "Rule saved", "answer": "Approved", "answered_at": when,
                    "assistant_did": _add(did, f"You approved this rule {_stamp(when)}. It starts the next time I check for messages."),
                    "last_press": _mark(name, when, "Done. I saved the rule. It starts the next time I check for messages.")}
        return {"state": "done", "status": "You turned this rule down", "answer": "No", "answered_at": when,
                "assistant_did": _add(did, f"You turned this rule down {_stamp(when)}. Nothing was changed."),
                "last_press": _mark(name, when, "Got it. I didn't make the rule.")}
    if name == "no":
        return refusal(name, when, "That button is for a card that asks yes or no. Nothing was changed.")
    if name in ("sender_show", "sender_hold"):
        who = sender_words(item) or "This sender"
        show = name == "sender_show"
        return {"state": "done", "status": "Showing their mail" if show else "Hiding their mail",
                "answer": SHOW_THEM if show else HOLD_THEM, "answered_at": when,
                "assistant_did": _add(did, f"You chose {_stamp(when)}: " + (f"show mail from {who}." if show else f"hide mail from {who}.")),
                "last_press": _mark(name, when, f"{who} always gets through from now on, and what they sent is on your page." if show
                                    else f"{who} is on your list of senders to always ignore.")}
    if name in ("wait_longer", "write_them"):
        if item.get("state") == "done":
            return {"last_press": _mark(name, when, "It was already Done.")}
        back = extra.get("came_back") if isinstance(extra.get("came_back"), dict) else {}
        who = back.get("who") or item.get("source_who") or "them"
        if name == "write_them":
            return {"assistant_did": _add(did, f"You chose {_stamp(when)} to write to {who}. Nothing is drafted or sent for you."),
                    "last_press": _mark(name, when, "Write your message. Nothing is sent until you press Send.", opens="writing")}
        import comeback
        import filters
        days = press.get("days") or back.get("wait_days") or filters.get()["waiting_back_days"] or 3
        day = comeback.add_working_days(when.date(), days)
        extra.pop("came_back", None)
        return {"state": "in_motion", "status": f"Waiting to {_token(day)}", "checkback_date": day, "asks": [],
                "extra": extra or None,
                "assistant_did": _add(did, f"You chose {_stamp(when)} to wait {days} more working day{'s' if days != 1 else ''}, to {_day_words(day)}."),
                "last_press": _mark(name, when, f"Waiting on {who} until {_token(day)}. It comes back by itself.", was=_was(item))}
    if name == "old_keep":
        return {"kept_at": when, "assistant_did": _add(did, f"You chose to keep it {_stamp(when)}."),
                "last_press": _mark(name, when, "Kept. I won't ask about it again until it has sat the full time again.")}
    if name == "old_card":
        rows = [r for r in extra.get("old_cards") or [] if isinstance(r, dict)]
        hit = next((r for r in rows if r.get("id") == press.get("card")), None)
        if not hit or not press.get("do"):
            return refusal(name, when, "That card is not on this list any more. Nothing was changed.")
        left = [r for r in rows if r is not hit]
        extra["old_cards"] = left
        said = {"keep": "Kept", "later": "Snoozed", "done": "Done", "someday": "Someday", "drop": "Done"}[press["do"]] + f": {hit.get('header')}"
        f = {"extra": extra, "assistant_did": _add(did, f"{said} ({_stamp(when)})."),
             "last_press": _mark(name, when, said + ("." if left else ". That was the last one; this card is Done."))}
        if left:
            n = len(left)
            f["title"] = f"{n} card{'s have' if n != 1 else ' has'} sat" + str(item.get("title") or "").split(" sat", 1)[-1]
        else:
            f.update(state="done", status="Answered")
        return f
    if name == "rule_offer":
        # the row under the box of a card whose words read as a rule; what needs Claude is done by answers.py after this lands
        offer = extra.get("rule_offer") if isinstance(extra.get("rule_offer"), dict) else None
        do = press.get("do")
        if not offer or item.get("state") == "done" or not do or (do == "discuss" and not press.get("words")):
            return refusal(name, when, "There is no rule waiting on this card for that answer. Nothing was changed."
                           if not offer or item.get("state") == "done" or not do else "Type what the rule should say first.")
        if do == "cancel":
            was = offer.get("was") if isinstance(offer.get("was"), dict) else {}
            rest = dict(was.get("extra") or extra) if isinstance(was.get("extra"), dict) else extra
            rest.pop("rule_offer", None)
            change = offer.get("made") == "change"      # a change he asked for in words (card_rules.asked_card)
            f = {"state": was.get("state") or item.get("state"), "status": "Cancelled" if offer.get("made") else was.get("status"),
                 "shelf": was.get("shelf"),
                 "later_until": _time(was.get("later_until")), "checkback_date": _date(was.get("checkback_date")),
                 "answer": None, "answered_at": None, "extra": rest or None,
                 "assistant_did": _add(did, f"You cancelled the proposed {'change' if change else 'rule'} {_stamp(when)}. "
                                            + ("Nothing was changed." if change else "No rule was saved." if offer.get("acted") else "Nothing was done.")),
                 "last_press": _mark(name, when, "Cancelled. Nothing was changed." if change else
                                     "Cancelled. No rule was saved." if offer.get("acted")      # words already acted on
                                     else "Cancelled. Nothing was done; your words are back in the box.")}
            if "asks" in was:
                f["asks"] = was.get("asks") or []
            return f
        if do == "discuss":
            talk = [t for t in offer.get("talk") or [] if isinstance(t, dict)]
            extra["rule_offer"] = dict(offer, talk=(talk + [{"who": "you", "text": press["words"]}])[-10:])
            return {"extra": extra, "status": "Thinking",
                    "assistant_did": _add(did, f"You asked {_stamp(when)} to reword the proposed rule: \"{press['words']}\""),
                    "last_press": _mark(name, when, "Rewording the rule.", claude=True)}
        rest = dict(extra)
        rest.pop("rule_offer", None)
        return {"extra": rest or None, "status": "Thinking",
                "assistant_did": _add(did, f"You pressed {'Approve' if do == 'approve' else 'Disapprove'} on the proposed rule "
                                           f"\"{offer.get('text')}\" {_stamp(when)}."),
                "last_press": _mark(name, when, ("Saving the rule." if offer.get("acted") else "Saving the rule and acting on this card.")
                                    if do == "approve" else ("No rule saved." if offer.get("acted")
                                                             else "Acting on this card, this one time."), claude=True)}
    if name in SWITCHES:
        if item.get("state") == "done":
            return {"last_press": _mark(name, when, "It was already Done.")}
        if not any(s["id"] == name for s in card.switches(item)):
            return refusal(name, when, "That button is not for this card. Nothing was changed.")
        hide = name == "hide_like_this"
        return {"state": "done", "status": "Not needed" if hide else "Got it", "shelf": None, "later_until": None,
                "assistant_did": _add(did, f"You pressed {switch_label(item, name)} {_stamp(when)}."),
                "last_press": _mark(name, when, "Done. Nothing else changes.",
                                    was=_was(item))}
    if name in ("should_have_seen", "read"):
        return refusal(name, when, "That button belongs to an entry under Hidden. Nothing was changed.")
    if name == "undo":
        last = item.get("last_press") if isinstance(item.get("last_press"), dict) else {}
        if last.get("ok") and last.get("press") in ("rsi_promote", "rsi_apply", "rsi_reject"):
            return refusal(name, when, "Nothing was taken back: a rule change you approved, applied or rejected stays as "
                                       "it is. Your rules and settings are in Settings.")
        was = last.get("was") if last.get("ok") else None
        if last.get("ok") and last.get("press") == "level_sent":
            return refusal(name, when, "Nothing was taken back: I already sent that reply, and a sent email can't be taken back.")
        if isinstance(was, dict) and str(last.get("press")).startswith("level_") or isinstance(was, dict) and last.get("press") in ("got_it", "later", "bring_back", "junk", "never_junk", "not_needed",
                                                           "always_show", "drop", "wait_longer", "standing_close", "standing_drop",
                                                           "hide_like_this", "keep_showing") \
                or (isinstance(was, dict) and last.get("press") == "done" and was.get("shelf")):
            f = {"assistant_did": _add(did, f"You took that back {_stamp(when)}."),
                 "last_press": _mark(name, when, "Taken back.")}
            if last["press"] not in ("never_junk", "always_show") or is_junk_ask(item):
                f.update(state=was.get("state") or item.get("state"), status=was.get("status"), shelf=was.get("shelf"),
                         later_until=_time(was.get("later_until")), checkback_date=_date(was.get("checkback_date")))
                if "extra" in was:
                    f.update(extra=was["extra"], asks=was.get("asks") or [])
                if str(last["press"]).startswith(("standing_", "level_")):     # taken back: the same card is never done for him again
                    f["extra"] = dict(f.get("extra") or extra, standing_skip=True)
            return f
        f = legacy({"action": "reopen"})
        f.update(shelf=None, later_until=None)
        was = last.get("was") if isinstance(last.get("was"), dict) else None
        if last.get("press") == "words" and was and was.get("state") in ("yours", "question"):
            f["state"] = was["state"]       # his words taken back: the card is where it was, not where a question would put it
            if was.get("status") not in ANSWER_WORDS:
                f["status"] = was.get("status")
        f["last_press"] = _mark(name, when, "Taken back.")
        return f
    return refusal(name, when, "I do not know that button, so nothing was changed.")


def _time(v):
    try:
        return dt.datetime.fromisoformat(str(v)) if v else None
    except ValueError:
        return None


def _date(v):
    try:
        return dt.date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


# --- Junk and Never junk: the owner's lists, written the same moment -----------------------------
def sender_words(item):
    s = item.get("sender") if isinstance(item.get("sender"), dict) else {}
    if is_junk_ask(item):
        rid = junk_ask_rule(item)
        if rid is None:
            return "Each sender this card names"
        try:
            e = next((x for x in _rules().parse("senders") if x["id"] == rid and x.get("pattern")), None)
        except Exception:  # noqa: BLE001  the words only; the press itself reads the list again
            e = None
        return e["pattern"].split(":", 1)[-1].replace("\\", "") if e else "The sender this card names"
    return str(s.get("address") or "").strip()


def can_junk(item):
    s = item.get("sender") if isinstance(item.get("sender"), dict) else {}
    return is_junk_ask(item) or bool(s.get("can_junk"))


def _rules():
    if common.paths.CORE not in sys.path:
        sys.path.insert(0, common.paths.CORE)
    import rules
    return rules


def _escape(s):
    return (s or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


OWNER_JUNK = "you pressed Junk on a card"           # an Always junk line the owner put there themself
OWNER_NEVER = "you pressed Never junk on a card"


def _own_lines(rules, key, sections):
    """The list lines that name exactly this sender (no subject part), in the given sections."""
    pat = _escape(key).lower()
    return [e for e in rules.parse("senders") if e.get("pattern") and not e.get("pattern2")
            and e["pattern"].lower() == pat and (e["status"] == "proposed" or e["section"] in sections)]


def junk_list(item, name, undo=False, when=None):
    """Write the owner's choice to their junk lists now. Returns (ok, plain words when it failed).
    Junk: the sender is on Always junk and off Never junk. Never junk: on Never junk and off the
    junk lists. undo takes back exactly what the press added. The junk question card answers every
    sender it asked about. Plain files only; the database is never needed."""
    try:
        rules = _rules()
        today = common.now()
        if is_junk_ask(item):
            rid, upto = junk_ask_rule(item), when or today
            # a one-sender card answers its own sender; the older card answers the senders waiting when he answered
            waiting = [e for e in rules.parse("senders") if e["status"] == "proposed" and e.get("pattern")
                       and (e["id"] == rid if rid is not None else (e.get("proposed_at") or upto) <= upto)]
            if undo:
                return False, "The senders were already filed, so this cannot be taken back here. Change the list in Settings."
            for e in waiting:
                (rules.confirm if name == "junk" else rules.never)(e["id"])
            return True, ""
        s = item.get("sender") if isinstance(item.get("sender"), dict) else {}
        key = str(s.get("key") or "").strip().lower()
        if not key:
            return False, "This card has no outside sender, so there is nobody to put on a list."
        mine, other = (rules.ALWAYS, rules.NEVER) if name == "junk" else (rules.NEVER, rules.ALWAYS)
        label = f"{OWNER_JUNK if name == 'junk' else OWNER_NEVER} {today.month}/{today.day}/{today:%y}"
        if undo:
            for e in _own_lines(rules, key, (mine,)):
                if e["section"] == mine and e["text"].startswith((OWNER_JUNK, OWNER_NEVER)):
                    rules._remove(e["id"])
            return True, ""
        for e in _own_lines(rules, key, (other, rules.PROBABLY)):
            rules._remove(e["id"])
        if not any(e["section"] == mine for e in _own_lines(rules, key, (mine,))):
            rules.add("junk", label, section=mine, pattern=_escape(key))
        return True, ""
    except Exception as e:  # noqa: BLE001  a list that cannot be written is said plainly, never hidden
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"junk list: {type(e).__name__}: {e}")
        return False, "Your junk list could not be written just now, so nothing was changed."


# --- the table of presses -----------------------------------------------------------------------
def _row(pressed_at, received_at, item_id, item_title, press, choice, words, device, happened, ok, claude_ran, secs, meaning=None,
         button=None):
    def t(v):
        try:
            return (v if isinstance(v, dt.datetime) else dt.datetime.fromisoformat(str(v))).isoformat(timespec="milliseconds")
        except (ValueError, TypeError):
            return common.now().isoformat(timespec="milliseconds")
    return {"pressed_at": t(pressed_at), "received_at": t(received_at), "item_id": str(item_id or "-")[:60],
            "item_title": " ".join(str(item_title or "-").split())[:300] or "-", "press": str(press or "-")[:40],
            "choice": str(choice or "-")[:200] or "-", "words": str(words or "-")[:4000] or "-",
            "device": " ".join(str(device or "").split())[:60] or "unknown",
            "happened": " ".join(str(happened or "-").split())[:600] or "-", "ok": bool(ok),
            "claude_ran": bool(claude_ran), "secs": round(float(secs or 0), 3),
            "meaning": meaning if meaning in MEANINGS else _row_meaning(str(press or "-"), str(choice or "-"), happened),
            "button": " ".join(str(button or "-").split())[:60] or "-"}


def ensure_on(con):
    """The table as it is now, on an open connection: made when missing, and a table from before meanings given its
    meaning and button columns, every row filled."""
    con.execute(DDL)
    con.execute(MIGRATE)
    _fill_meanings(con)


def _fill_meanings(con):
    con.execute("UPDATE live_presses SET button = '-' WHERE button IS NULL")
    rows = con.execute("SELECT id, press, choice, happened FROM live_presses WHERE meaning IS NULL").fetchall()
    by = {}
    for rid, press, choice, happened in rows:
        by.setdefault(_row_meaning(press, choice, happened), []).append(rid)
    for m, ids in by.items():
        for i in range(0, len(ids), 500):
            con.execute("UPDATE live_presses SET meaning = ? WHERE meaning IS NULL AND list_contains(?, id)", (m, ids[i:i + 500]))
    return len(rows)


def _insert(con, rows):
    ensure_on(con)
    for r in rows:
        if r.get("meaning") not in MEANINGS:        # a press that waited in the file from before meanings
            r = dict(r, meaning=_row_meaning(str(r.get("press") or "-"), str(r.get("choice") or "-"), r.get("happened")))
        r = dict(r, button=r.get("button") or "-")
        con.execute(f"INSERT INTO live_presses ({', '.join(COLUMNS)}) VALUES ({', '.join('?' for _ in COLUMNS)})",
                    tuple(r[c] for c in COLUMNS))


def _connect():
    import db
    return db.try_connect()


def flush(con=None):
    """Write every press that waited for the database (and fill in the rule book rows that waited for it). Returns how many
    presses were written."""
    try:
        import rule_book
        rule_book.drain()
    except Exception:  # noqa: BLE001  the rule book never stands in the way of the presses table
        pass
    with _file_lock:
        try:
            with open(WAITING, encoding="utf-8") as f:
                rows = [json.loads(x) for x in f.read().splitlines() if x.strip()]
        except (OSError, ValueError):
            rows = []
        if not rows:
            return 0
        own = con is None
        con = con or _connect()
        if con is None:
            return 0
        try:
            _insert(con, rows)
        finally:
            if own:
                con.close()
        try:
            os.remove(WAITING)
        except OSError:
            pass
        return len(rows)


def record(**row):
    """One press, written now. While a pass holds the database it waits in a file and is written by the
    next press, the next landing of an answer, or the next pass, whichever comes first. Never raises."""
    try:
        r = _row(**row)
        with _file_lock:
            os.makedirs(os.path.dirname(WAITING), exist_ok=True)
            with open(WAITING, "a", encoding="utf-8") as f:
                f.write(json.dumps(r) + "\n")
        flush()
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"press record: {type(e).__name__}: {e}")


# --- cards that come back by themselves -----------------------------------------------------------
def back_from_later(pass_id):
    """Every card whose snooze time has passed is on the page again. No Claude. Returns how many."""
    import db
    import items
    items.ensure()
    now = common.now()
    got = db.query("SELECT id, assistant_did, status FROM live_items WHERE shelf = 'later' AND later_until <= ?", (now,))
    for iid, did, status in got:
        db.execute("UPDATE live_items SET shelf=NULL, later_until=NULL, checkback_date=NULL, status=?, assistant_did=?,"
                   " updated_at=?, last_pass=? WHERE id=?",
                   (None if str(status or "").startswith(("Later", "Snoozed")) else status,
                    _add(did, f"Back from snooze {_stamp(now)}."), now, pass_id, iid))
    return len(got)
