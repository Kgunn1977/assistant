r"""Act on one of the owner's answers the moment it arrives.

    import answers
    out = answers.act_on_answer(answer, on_update=None)

The page's listener calls this for every click or typed answer. The 15-minute
pass calls apply_files() for any answer that reached Live\answers another way,
so nothing is missed, and the same answer is never applied twice (the key is
id|action|at).

Button answers need no AI: done, not mine, reopen, not now, snooze, approve,
and a choice button. Words typed on a card go to Talk to your assistant with that card
attached (chat.handle): the same Claude, instructions and conversation as the box
at the top; what it decides about the card lands here (card_record).

SAFE BESIDE A RUNNING PASS. A pass can hold the database for a long time. So
the answer is first saved as a file in Live\answers (whole file, renamed into
place); then the database is tried once, without waiting. If it is free the
change lands now. If it is busy the function still returns at once with the
item as it will be, and a background thread (and, failing that, the next pass)
lands it. Every write of an answer checks its key in the same database
connection, so it lands exactly once.

Nothing here sends anything. An approval is recorded, not acted on by sending.
"""
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys
import threading
import time

import common
import db
import filters
import items
import card
import card as card_mod
import card_rules
import limits
import presses
import teach

FLUSH_MINUTES = 30
NOTE_PREFIX = "live:project-"
PARALLEL_NOTE = "Nothing was sent; only an email you write on the page and press Send on goes out."
DDL = "CREATE TABLE IF NOT EXISTS live_answers (key VARCHAR PRIMARY KEY, item_id VARCHAR, applied_at TIMESTAMP)"
DUPLICATE_SECONDS = 10   # the same answer on the same item again this soon is one answer
_recent = {}             # (id, action, text) -> (when it was acted on, what was returned)
_flusher = {"thread": None}
_lock = threading.Lock()
_landing = threading.Lock()     # one lander at a time in this process: the same answer is never written twice at once
_file_lock = threading.Lock()   # one change to items.json at a time inside this process


# --- small tools ----------------------------------------------------------------------
def _stamp(when):
    return f"{when.month}/{when.day} {when.strftime('%I:%M %p').lstrip('0')}"


def _key(rec):
    key = f"{rec.get('id')}|{rec.get('action')}|{rec.get('at')}"
    text = str(rec.get("text") or "")
    if rec.get("action") == "answer" and text.startswith('{"press"'):       # two presses in one second are two presses
        key += "|" + text[:80]
    return key


def _when(rec):
    try:
        return dt.datetime.fromisoformat(str(rec["at"]))
    except (KeyError, ValueError, TypeError):
        return common.now()


def _connect():
    """The database now, or None when a pass holds it. Never waits."""
    return db.try_connect()


def _add(text, line):
    return f"{text}\n{line}" if text else line


# --- a card left with the owner names what it needs -------------------------------------------
NOTHING_NEEDED = "Nothing is needed from you. You can mark this card Done."
NEXT_STEP = "Your next step: "


def name_what_is_needed(fields, item=None):
    """A card left with the owner (question or yours) always names the one thing to
    decide or do. One that names nothing gets its recommended step as that one action;
    with no recommendation either, it is handled and says plainly that nothing is
    needed. fields are the columns about to be written (changed in place and returned);
    item is the card as it stands, read for any column fields leave out."""
    item = item or {}
    get = lambda k: fields[k] if k in fields else item.get(k)
    if get("state") not in ("question", "yours"):
        return fields
    if [a for a in (get("asks") or []) if str(a or "").strip()] or get("draft") or get("choices"):
        return fields
    cal = get("calendar")
    if isinstance(cal, dict) and cal.get("title"):
        return fields
    rec = " ".join(str(get("recommended") or "").split())
    if rec and rec != NOTHING_NEEDED:
        fields["asks"] = [NEXT_STEP + rec]
    else:
        fields.update(state="handled", asks=[], recommended=NOTHING_NEEDED)
    return fields


def note_in_history(did, note):
    """What a new message adds to a card goes in its history, never on the end of its story."""
    note = " ".join(str(note or "").split())
    return _add(did, f"A new message came in: {note}") if note else did


# --- what an answer does to an item (no database, no clock of its own) --------------------
PUT_AWAY = "You put this away"          # the last history line of a finished card he dismissed: it is off the page
WAS = {"question": "a question for you", "yours": "yours to do", "in_motion": "waiting",
       "handled": "done without asking", "new": "just arrived"}


SETTLED_LINE = re.compile(r'^Answered by you: "(.+)" \((.*)\)$')
ASKED_AGAIN = "Asked again: "


def settled_in_force(did):
    """The questions the history records as answered by the owner and not since taken
    back, oldest first. A taken-back answer names what it asks again on its own line."""
    out = []
    for line in (did or "").split("\n"):
        m = SETTLED_LINE.match(line)
        if m:
            q = m.group(1).strip()
            if q.lower() not in {x.lower() for x in out}:
                out.append(q)
        elif (line.startswith("You took your answer back") and ASKED_AGAIN in line) or line.startswith(REOPENED):
            again = {q.strip().lower() for q in re.findall(r'"(.+?)"', line.split(ASKED_AGAIN, 1)[1] if ASKED_AGAIN in line
                                                           else line[len(REOPENED):])}
            out = [q for q in out if q.lower() not in again]
    return out


REOPENED = "New information came in, so this is asked again: "


def reopen_line(did, questions, when):
    """The history with the line that opens answered questions again (think.py, the writer's `reopen`)."""
    return _add(did, REOPENED + " ".join(f'"{q}"' for q in questions) + f" ({_stamp(when)}).")


def put_away(item):
    return item.get("state") == "done" and (item.get("assistant_did") or "").split("\n")[-1].startswith(PUT_AWAY)


def kind_of(item, rec):
    """'button' or 'typed'."""
    action, page = rec.get("action"), rec.get("page_action")
    if action == "_set" or action in ("done", "not_mine", "reopen"):
        return "button"
    if presses.parse(item, rec) is not None:    # a press never starts Claude
        return "button"
    if str(item.get("source_key") or "").startswith(("live:project-", "live:projwrite-")) and action == "answer":
        return "button"                         # words on a note from a project are recorded, not read by Claude
    if action == "note" or page in ("later", "snooze"):
        return "button"
    if page == "calendar" or isinstance(rec.get("calendar"), dict):
        return "button"
    text = (rec.get("text") or "").strip()
    if page == "approve" or text.lower().startswith("approved"):
        return "button"
    if rec.get("label") and (rec.get("question") or _question_no(item, rec)):
        return "button"                         # one numbered question's own button (found by its words when its number was lost)
    # the buttons as the page drew them: top-level on the page's copy, still in "extra" on the database row, so the
    # answer reads the same in both places (a press read as words there sat on "Reading..." with no run started)
    extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
    choices = [str(c.get("text") if isinstance(c, dict) else c).strip().lower()
               for c in (item.get("choices") or extra.get("choices") or [])]
    if text.lower() in choices:
        return "button"
    return "typed" if text else "button"


def transform(item, rec):
    """The columns this answer changes, as {column: value}. assistant_did is
    returned whole. Pure: the same item and answer always give the same result."""
    when = _when(rec)
    action, page = rec.get("action"), rec.get("page_action")
    text = (rec.get("text") or "").strip() or None
    did = item.get("assistant_did")
    if action == "_set":                       # a result the engine wrote itself
        f = dict(rec.get("fields") or {})
        if rec.get("did"):
            f["assistant_did"] = _add(did, rec["did"])
        return f
    if action == "done":
        if item.get("state") == "done":        # Put away on a finished card: it leaves the page, nothing else changes
            return {"assistant_did": _add(did, f"{PUT_AWAY} {_stamp(when)}.")}
        was = WAS.get(item.get("state"))
        return {"state": "done", "status": "Done", "answered_at": when, "asks": [],      # his Done holds: no pass reopens it
                "assistant_did": _add(did, f"You marked it done {_stamp(when)}" + (f" (it was {was})." if was else "."))}
    if action == "not_mine":
        return {"state": "done", "status": "Not yours",
                "assistant_did": _add(did, f"You said it is not yours {_stamp(when)}.")}
    if action == "reopen":
        last = (did or "").split("\n")[-1]
        if put_away(item):                     # a Put away taken back: the finished card is on the page again
            return {"assistant_did": _add(did, f"You brought it back {_stamp(when)}.")}
        if item.get("state") != "done" and not item.get("answer"):
            # a Not now or a Snooze taken back: the card stays in the place it was
            st = item.get("status")
            return {"status": None if str(st or "").startswith(("Snoozed", "Not now")) else st,
                    "assistant_did": _add(did, f"You took that back {_stamp(when)}.")}
        before = next((k for k, v in WAS.items() if item.get("state") == "done" and last.startswith("You marked it done")
                       and last.endswith(f"(it was {v}).")), None)
        if before:                             # a Done taken back: the card returns to the place it was
            # without any question its history shows he already answered: he is never asked twice
            done_qs = {q.lower() for q in settled_in_force(did)}
            asks = list(item.get("asks") or [])
            keep = [a for a in asks if str(a).strip().lower() not in done_qs]
            line = f"You took that back {_stamp(when)}."
            f = {"state": before, "status": None}
            if len(keep) != len(asks):
                f["asks"] = keep
                line += " Already answered, so not asked again: " + \
                    " ".join(f"\"{str(a).strip()}\"" for a in asks if a not in keep)
                name_what_is_needed(f, item)
            f["assistant_did"] = _add(did, line)
            return f
        # an answer taken back: the questions that answer settled are asked again
        ans = (item.get("answer") or "").strip()[:200]
        force = {q.lower() for q in settled_in_force(did)}
        asks = list(item.get("asks") or [])
        back = []
        for x in (did or "").split("\n"):
            m = SETTLED_LINE.match(x)
            q = m.group(1).strip() if m else ""
            if m and ans and m.group(2) == ans and q.lower() in force \
                    and q.lower() not in {a.lower() for a in asks + back}:
                back.append(q)
        asks += back
        line = f"You took your answer back {_stamp(when)}." + \
            (f" {ASKED_AGAIN}" + " ".join(f"\"{q}\"" for q in back) if back else "")
        f = {"state": "question" if asks else "yours", "status": None,
             "answer": None, "answered_at": None, "assistant_did": _add(did, line)}
        if back:
            f["asks"] = asks
        return f
    if page == "snooze" or (action == "note" and rec.get("until")):
        until = str(rec.get("until") or "")[:10]
        try:
            day = dt.date.fromisoformat(until)
        except ValueError:
            day = when.date() + dt.timedelta(days=1)
        return {"checkback_date": day, "status": f"Snoozed to {day.month}/{day.day}",
                "assistant_did": _add(did, f"You snoozed it to {day.month}/{day.day}.")}
    if page == "later" or action == "note":
        return {"status": "Not now", "checkback_date": when.date() + dt.timedelta(days=1),
                "assistant_did": _add(did, f"You said not now {_stamp(when)}." + (f" Note: {text}" if text and page != "later" else ""))}
    if page == "calendar" or isinstance(rec.get("calendar"), dict):
        chosen = dict(rec.get("calendar") or {})
        said = calendar_words(chosen) or (text or "no day or time given")
        held = dict(item.get("calendar") or {})
        held.update({k: chosen.get(k) for k in ("title", "date", "start", "end", "all_day", "location")
                     if k in chosen})
        held.update(certain=True, chosen=True, accepted_as_shown=bool(chosen.get("accepted_as_shown")))
        added = rec.get("calendar_added") if isinstance(rec.get("calendar_added"), dict) else {}
        if several(item) and (added.get("ok") or not added):
            # the calendar question of several (its buttons sit on the first question): it alone is settled; the card stays
            # for the others, and the event, now handled, leaves the card's front so its buttons do not move to the next one
            f = _settle_one(item, _question_no(item, rec) or 1, said, when,
                            f"You chose: {said}. {added.get('said')}" if added else f"You chose: {said}. Recorded {_stamp(when)}.")
            f["extra"] = dict(f.get("extra") or {}, calendar_answered=held)
            f["calendar"] = None
            return f
        if added.get("ok"):         # Add to calendar: added by the Calendar part's own code (act_on_answer, before this)
            held["added"] = added.get("id")
            return {"answer": text or said, "answered_at": when, "state": "handled", "status": "Calendar: added", "calendar": held,
                    "assistant_did": _add(did, f"You chose: {said}. {added.get('said')}")}
        if added:
            return {"answer": text or said, "answered_at": when, "status": "Calendar: not added", "calendar": held,
                    "assistant_did": _add(did, f"You chose: {said}. It was not added to your calendar: {added.get('said')}")}
        return {"answer": text or said, "answered_at": when, "state": "handled", "status": "Calendar: recorded",
                "calendar": held,
                "assistant_did": _add(did, f"You chose: {said}. Recorded {_stamp(when)}.")}
    kind = kind_of(item, rec)
    asks = [a for a in item.get("asks") or [] if str(a or "").strip()]
    n = _question_no(item, rec)
    approve = page == "approve" or (text or "").lower().startswith("approved")
    if several(item) and kind == "button" and (n or approve or len(asks) == 1) and (text or approve):
        # one question of several answered by its button (a yes on the first question is its Go ahead, Save this rule or
        # Check and send): that question is answered and kept on the card as answered; the card stays for the others
        if approve and item.get("draft"):
            # Check and send: the email waits on his own Send, so its question stays open until it goes
            return {"status": "Approved", "assistant_did": _add(did, f"Recorded your approval {_stamp(when)}. {PARALLEL_NOTE}")}
        return _settle_one(item, n or 1, text or "Approved", when,
                           f"Recorded your approval {_stamp(when)}. {PARALLEL_NOTE}" if approve else None,
                           reads=_decides_for_someone(item, rec, None))
    if len(asks) > 1 and kind == "button" and text and rec.get("label"):
        # a button on a card of several questions whose question did not come with it and cannot be told from its words:
        # it is recorded, and no question is taken as answered by a guess
        return {"from_at": when, "assistant_did": _add(did, f"Recorded your answer {_stamp(when)}: {text}. Which question it "
                                                            "answers did not come with it, so every question stays open.")}
    if kind == "typed":
        # his words are read before anything changes: the card stays where it is, with its questions and buttons,
        # until the assistant has read them (it closes only if they settle it)
        n = _question_no(item, rec)
        # the card is now from this answer (the date at its top right, Newest/Oldest first): it becomes the newest card.
        # Its first message still sits in source_messages and created_at.
        return {"answer": text, "answered_at": when, "status": "Thinking", "from_at": when,
                "assistant_did": _add(did, f"You wrote {_stamp(when)}" + (f", answering question {n}" if n else "") + f": \"{text}\"")}
    base = {"answer": text or "Approved", "answered_at": when, "state": "in_motion", "asks": []}   # the old question is answered
    if page == "approve" or (text or "").lower().startswith("approved"):
        return {**base, "status": "Approved",
                "assistant_did": _add(did, f"Recorded your approval {_stamp(when)}. {PARALLEL_NOTE}")}
    return {**base, "status": "Answered", "from_at": when,     # a question answered by its choice button: the card is from now
            "assistant_did": _add(did, f"Recorded your answer {_stamp(when)}: {text}. {PARALLEL_NOTE}")}


def _decides_for_someone(item, rec, press):
    """True for a choice button pressed on a card's question: his decision, so it is read like his words (act_on_answer)
    and acted on (a reply to whoever asked drafted for his Send, a to-do, a calendar entry on his words), not only recorded
    (the owner, 11/25: each question is a small card of its own, closed when its answer is acted on). A card's own presses
    (Junk, Done, Approve, a rule's buttons) are not choices."""
    text = (rec.get("text") or "").strip()
    if not item or press or rec.get("action") != "answer" or not text or text.lower().startswith("approved"):
        return False
    if rec.get("page_action") in ("later", "snooze", "calendar", "approve") or isinstance(rec.get("calendar"), dict):
        return False
    if str(item.get("source_key") or "").startswith(("live:project-", "live:projwrite-", "live:test-seen", "live:test-timing")):
        return False
    return kind_of(item, rec) == "button"


def _go_ahead_acts(item, press):
    """True for Go ahead (approve) pressed on a card's own yes-or-no question with a recommendation: his yes to it, so it is
    acted on like his words (spec 4.8: "There's no point in asking me a question if you're not going to do anything useful
    with it."), not only recorded. Not a rule, an update, a draft (Check and send), a standing offer, a project write or a
    rule change card, which have their own approve."""
    if not item or not press or press.get("name") != "approve":
        return False
    key = str(item.get("source_key") or "")
    if key.startswith(("rule:", "live:standing-", "live:projwrite-", "live:project-", "live:rsi-", "live:update-", "live:test-")):
        return False
    if item.get("draft") or item.get("rule") or (isinstance(item.get("update"), dict) and item["update"].get("version")):
        return False
    return bool(str(item.get("recommended") or item.get("rec_front") or "").strip() or _open_asks(item))


def _question_no(item, rec):
    """The number of the question this answer is for (1 for the first), when the page said and the card has it. A choice
    button whose number did not come with it (a page or site that dropped it) is found by its words among the card's
    questions' own choices, when exactly one question offers them."""
    try:
        n = int(rec.get("question") or 0)
    except (TypeError, ValueError):
        return 0
    asks = _open_asks(item)
    if 1 <= n <= len(asks):
        return n
    text = " ".join(str(rec.get("text") or "").split()).lower()
    if n or not rec.get("label") or len(asks) < 2 or not text:
        return 0
    hits = [i for i, q in enumerate(_questions(item), 1)
            if text in {" ".join(str(c.get("text") or c.get("value") or c.get("label") if isinstance(c, dict) else c).split()).lower()
                        for c in q.get("choices") or []}]
    return hits[0] if len(hits) == 1 else 0


def _open_asks(item):
    return [a for a in item.get("asks") or [] if str(a or "").strip()]


def _questions(item):
    """The card's open questions with their own choices, in order (card.questions), from the card as stored or as shown."""
    extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
    return card_mod.questions({"asks": _open_asks(item), "choices": item.get("choices") or extra.get("choices") or []}, extra)


ANSWERED_KEY = "answered"      # extra.answered: the questions of a card of several already answered, shown on it with Change


def answered_of(item):
    """[{"ask", "answer", "at", "did"}]: the card's questions answered one at a time, oldest first."""
    extra = _extra(item)
    open_now = {str(a).strip().lower() for a in _open_asks(item)}     # one asked again (new information) is open, not answered
    return [a for a in extra.get(ANSWERED_KEY) or [] if isinstance(a, dict) and a.get("ask")
            and str(a["ask"]).strip().lower() not in open_now]


def several(item):
    """True for a card whose questions are answered one by one: more than one open, or some answered already."""
    return len(_open_asks(item)) > 1 or bool(answered_of(item) and _open_asks(item))


def _extra(item_or_fields, fallback=None):
    ex = (item_or_fields or {}).get("extra")
    if isinstance(ex, str):
        try:
            ex = json.loads(ex)
        except ValueError:
            ex = None
    if not isinstance(ex, dict):
        ex = _extra(fallback) if fallback is not None else {}
    return dict(ex)


def _with_choices(extra, qs):
    """extra with each open question's own choices as the page reads them: the first's in extra.choices, the rest's in
    extra.questions. qs: [{"ask", "choices"}] for the open questions, in order."""
    extra.pop("choices", None)
    extra.pop("questions", None)
    if qs and qs[0]["choices"]:
        extra["choices"] = qs[0]["choices"]
    if [x for x in qs[1:] if x["choices"]]:
        extra["questions"] = [x for x in qs[1:] if x["choices"]]
    return extra


def all_answered_lines(answered):
    """One line per answer for the card's history when every question is answered and the card closes."""
    return [f'Answered "{a["ask"]}": {a.get("answer")}.' + (f' {a["did"]}' if a.get("did") else "") for a in answered]


def _settle_one(item, n, said, when, line=None, reads=False):
    """One question of several answered (n: its number): it leaves the open questions and is kept on the card as answered
    (extra.answered, shown with its answer and Change); the others keep their own choices. When it was the last one the
    card closes with one line per answer, unless the assistant still reads this answer (reads): that run closes it.
    The fields to write."""
    asks, qs = _open_asks(item), _questions(item)
    q = asks[n - 1]
    extra = _with_choices(_extra(item), [x for i, x in enumerate(qs) if i != n - 1])
    done = [a for a in answered_of(item) if a["ask"].strip().lower() != q.strip().lower()]
    extra[ANSWERED_KEY] = done + [{"ask": q, "answer": said, "at": when.isoformat(timespec="seconds"), "did": line or ""}]
    did = _add(item.get("assistant_did"), f'Answered by you: "{q}" ({said})')
    if line:
        did = _add(did, line)
    rest = [a for i, a in enumerate(asks) if i != n - 1]
    f = {"asks": rest, "state": item.get("state") if item.get("state") in ("question", "yours") else "question",
         "status": "Thinking" if reads else None, "from_at": when, "extra": extra}
    if reads:           # kept until the reply lands, so a run that could not be made is read again (think_pending)
        f.update(answer=said, answered_at=when)
    if not rest and not reads:
        f.update(state="done", status="Answered", answered_at=when)
        did = "\n".join([did] + all_answered_lines(extra[ANSWERED_KEY]))
    f["assistant_did"] = did
    return f


def _redo_of(item, rec):
    """Change on one answered question (the page's redo: its place in extra.answered, 1 for the first): that entry, or None."""
    try:
        k = int(rec.get("redo") or 0)
    except (TypeError, ValueError):
        return None
    got = answered_of(item)
    return got[k - 1] if 1 <= k <= len(got) else None


def after_one_answer(follow, item, others, said, changed=None, new="", before=None):
    """What the assistant's reply to one answer on a card of several may do to the card: the card's other open questions
    stay asked with their own buttons whatever the reply decided (the ones it settled leave), each answered question keeps
    its answer and what was done for it (changed: the answered question whose answer was changed to new), and once nothing
    is left asked the card closes with one line per answer, unless something waits on the owner (an email in Drafts for his
    Send, a step only he can take). follow: the record the reply made (changed in place and returned); item: the card as
    it stood when the reply was asked for; others: its open questions this answer was not for."""
    f = follow.get("fields") if isinstance(follow, dict) else None
    if not isinstance(f, dict):
        return follow
    lines = [m for m in (SETTLED_LINE.match(x) for x in str(follow.get("did") or "").split("\n")) if m]
    keep = [a for a in others if str(a or "").strip()]      # a reply to one answer never settles the other questions: each leaves by its own answer
    if keep:       # and its history never says he answered them
        mine = {str(a).strip().lower() for a in keep}
        follow["did"] = "\n".join(x for x in str(follow.get("did") or "").split("\n")
                                  if not ((m := SETTLED_LINE.match(x)) and m.group(1).strip().lower() in mine))
        lines = [m for m in (SETTLED_LINE.match(x) for x in follow["did"].split("\n")) if m]
    asks = [a for a in (f["asks"] if "asks" in f else _open_asks(item)) if str(a or "").strip()]
    if f.get("state") in ("done", "handled"):
        asks = [a for a in asks if a not in others] if "asks" in f else []
    asks += [a for a in keep if str(a).strip().lower() not in {str(x).strip().lower() for x in asks}]
    f["asks"] = asks
    extra = _extra(f, item)
    answered = [dict(a) for a in (answered_of({"extra": extra, "asks": asks}) or answered_of(item))]
    did_now = " ".join(str(said or "").split())[:300]
    have = {a["ask"].strip().lower() for a in answered}
    for m in lines:         # a question the reply settled from his words is answered on the card too
        if m.group(1).strip().lower() not in have and m.group(1).strip().lower() not in {a.lower() for a in asks}:
            answered.append({"ask": m.group(1).strip(), "answer": m.group(2), "at": common.now().isoformat(timespec="seconds"), "did": did_now})
            have.add(m.group(1).strip().lower())
    if changed:
        answered = [dict(a, answer=new, did=did_now, at=common.now().isoformat(timespec="seconds"))
                    if a["ask"].strip().lower() == changed["ask"].strip().lower() else a for a in answered]
    elif answered and not answered[-1].get("did"):
        answered[-1] = dict(answered[-1], did=did_now)
    if answered:
        extra[ANSWERED_KEY] = answered
    # each question still open keeps its own buttons, as the card had them before this answer; a question the reply added
    # takes the buttons the reply gave it
    old = {q["ask"].strip().lower(): q["choices"] for q in _questions(item)}
    old.update({q["ask"].strip().lower(): q["choices"] for q in _questions(before or {})})
    fresh = {q["ask"].strip().lower(): q["choices"] for q in card_mod.questions({"asks": asks, "choices": extra.get("choices") or []}, extra)}
    _with_choices(extra, [{"ask": a, "choices": old[a.strip().lower()] if a.strip().lower() in old else fresh.get(a.strip().lower(), [])}
                          for a in asks])
    f["extra"] = extra
    if keep:
        if f.get("state") in ("done", "handled", "in_motion") or not f.get("state"):
            f.update(state="question", status="Needs one more answer", answer=None, answered_at=None)
    elif not asks and answered:
        if f.get("status") == "Email in Drafts":
            f["state"] = "handled"          # the reply waits on his Send: the card stays with only that
        elif f.get("state", item.get("state")) in ("question", "handled", "done") and not str(f.get("state") or "") == "yours":
            f.update(state="done", status="Answered", answer=None)
            follow["did"] = "\n".join([x for x in (follow.get("did"), *all_answered_lines(answered)) if x])
    return follow


def _clock(hhmm):
    try:
        t = dt.datetime.strptime(str(hhmm), "%H:%M")
    except (ValueError, TypeError):
        return None
    return t.strftime("%I:%M %p").lstrip("0")


def _calendar_add(chosen, item):
    """A calendar card's Add to calendar: the event made by the Calendar part's own code (calendar_view.add) on his main calendar.
    {"ok", "id", "said"}. A card whose event was already added is not added twice."""
    if (item.get("calendar") or {}).get("added"):
        return {"ok": True, "id": item["calendar"]["added"], "said": "It was already on your calendar."}
    import calendar_view
    start, end, all_day = str(chosen.get("start") or ""), str(chosen.get("end") or ""), bool(chosen.get("all_day")) or not chosen.get("start")
    if start and not end:
        h, m = (int(x) for x in start.split(":"))
        end = f"{min(h + 1, 23):02d}:{m:02d}" if h < 23 else "23:59"
    out = calendar_view.add({"title": chosen.get("title") or item.get("short_header") or item.get("title"), "day": chosen.get("date"),
                             "all_day": all_day, "start": start, "end": end, "place": chosen.get("location") or "", "default_ok": True})
    return {"ok": bool(out.get("ok")), "id": (out.get("event") or {}).get("id"), "said": calendar_view.said(out, "add")}


def calendar_words(c):
    """A calendar choice in plain words: 'Test event, Thu 11/12/26, 3:00 PM to 4:00 PM'."""
    if not isinstance(c, dict):
        return ""
    try:
        d = dt.date.fromisoformat(str(c.get("date")))
        day = f"{d.strftime('%a')} {d.month}/{d.day}/{d.strftime('%y')}"
    except (ValueError, TypeError):
        day = None
    if not day:
        return ""
    if c.get("all_day") or not _clock(c.get("start")):
        when = f"{day}, all day"
    else:
        when = f"{day}, {_clock(c['start'])}" + (f" to {_clock(c['end'])}" if _clock(c.get("end")) else "")
    return ", ".join(x for x in (c.get("title"), when, c.get("location")) if x)


def _overlay(item, rec):
    """The item as it will read once rec lands (used when the database is busy)."""
    out = dict(item)
    for k, v in transform(item, rec).items():
        out[k] = v.isoformat() if isinstance(v, (dt.datetime, dt.date)) else v
    if rec.get("action") != "_set":
        out["updated_at"] = _when(rec).isoformat(timespec="seconds")
    return card.fill(out)


# --- landing a record in the database, exactly once ---------------------------------------
def _row(con, iid):
    r = con.execute(f"SELECT {', '.join(items.COLUMNS)} FROM live_items WHERE id=?", (iid,)).fetchone()
    if not r:
        return None
    d = dict(zip(items.COLUMNS, r))
    for c in items.JSON_COLUMNS:
        d[c] = json.loads(d[c]) if d[c] else (None if c in items.JSON_NULL else [])
    items.lift(d)
    if not d.get("choices"):
        import mods
        if mods.owns(d):        # a mod's card: its buttons as the page last had them; the mod's code never runs here
            shown = next((i for i in common.read_json(common.ITEMS_JSON, {}).get("items") or [] if i.get("id") == d["id"]), {})
            if shown.get("choices"):
                d["choices"] = shown["choices"]
    try:        # whom Junk and Never junk are about: needed to read the card's press exactly as the page's copy did
        d["sender"] = items.sender_for(con, d["source_messages"])
    except Exception:  # noqa: BLE001
        d["sender"] = None
    try:        # a card from a mailing, so Hide mailings like this reads the same here as on the page's copy (card.switches)
        d["mailing"] = items.mailing_for(con, d["source_messages"])
    except Exception:  # noqa: BLE001
        d["mailing"] = False
    return d


def _apply(con, rec):
    """Apply one record on an open connection. Returns the item afterwards, or
    None when the item is unknown. A record already applied changes nothing."""
    con.execute(DDL)
    items.ensure_on(con)
    item = _row(con, rec.get("id"))
    if item is None:
        return None
    key = _key(rec)
    if con.execute("SELECT 1 FROM live_answers WHERE key=?", (key,)).fetchone():
        return item
    if rec.get("action") == "answer" and item.get("answered_at") and \
            (rec.get("text") or "").strip() == (item.get("answer") or "") and \
            abs((_when(rec) - item["answered_at"]).total_seconds()) <= DUPLICATE_SECONDS:
        con.execute("INSERT INTO live_answers VALUES (?,?,?)", (key, item["id"], common.now()))
        return item
    f = transform(item, rec)
    import dates
    dates.store_fields(f)       # a day is stored as its date, never as "today" or "this morning"
    now = common.now()
    for c in items.JSON_COLUMNS:
        if c in f and not isinstance(f[c], (str, type(None))):
            f[c] = json.dumps(f[c], default=str)
    f = {k: v for k, v in f.items() if k in items.COLUMNS}
    if "state" in f and f["state"] != item["state"]:
        f["state_changed_at"] = now
        f["done_at"] = now if f["state"] == "done" else None
    f["updated_at"] = now
    f["last_pass"] = "answer"
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute(f"UPDATE live_items SET {', '.join(k + '=?' for k in f)} WHERE id=?",
                    (*f.values(), item["id"]))
        con.execute("INSERT INTO live_answers VALUES (?,?,?)", (key, item["id"], now))
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    return _row(con, item["id"])


def _save(rec):
    """The durable record of an answer: one whole file in Live\\answers."""
    os.makedirs(common.ANSWERS_APPLIED, exist_ok=True)
    name = f"{rec['id']}-{int(time.time() * 1000)}-{abs(hash(_key(rec))) % 10000:04d}.json"
    path = os.path.join(common.ANSWERS, name)
    common.write_json(path, rec)
    return path


def _file_done(path, refused=False):
    try:
        os.replace(path, os.path.join(common.ANSWERS_APPLIED,
                                      ("refused-" if refused else "") + os.path.basename(path)))
    except OSError:
        pass


def _pending(iid=None):
    out = []
    def age(path):          # a file another thread landed and moved a moment ago is simply no longer waiting
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0
    for p in sorted(glob.glob(os.path.join(common.ANSWERS, "*.json")), key=age):
        rec = common.read_json(p)
        if isinstance(rec, dict) and rec.get("id") and (iid is None or rec["id"] == iid):
            out.append((p, rec))
        elif not isinstance(rec, dict) or not rec.get("id"):
            _file_done(p, refused=True)
    return out


def missed_send_words(rec):
    """The plain line for an email written from scratch whose Send press reached no listener:
    which email (subject and recipients, never the body) and what to do. Never raises."""
    try:
        m = json.loads(rec.get("text") or "")["send_email"]
        m = m if isinstance(m, dict) else {}
    except (ValueError, KeyError, TypeError):
        m = {}
    subject = str(m.get("subject") or "").strip()[:120]
    who = [str(a).strip() for a in list(m.get("to") or []) + list(m.get("cc") or []) if str(a).strip()]
    which = "the email you wrote"
    if subject:
        which += f" \"{subject}\""
    if who:
        which += " to " + ", ".join(who[:5]) + (f" and {len(who) - 5} more" if len(who) > 5 else "")
    when = _when(rec)
    return (f"Not sent: {which}, pressed {_stamp(when)}, did not go out because this page couldn't "
            "reach your computer. Write it again and press Send.")


def _tell_in_chat(said):
    """Put the line in the page's running conversation, where it stays after the pass. Never raises."""
    try:
        import chat
        chat._add({"who": "assistant", "text": said, "source": None,
                   "at": common.now().isoformat(timespec="seconds")})
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"missed send note: {type(e).__name__}: {e}")


def apply_files(pass_id=None, con=None):
    """Land every answer file that is waiting. Returns (applied, problems,
    changed item ids). Used by the pass and by the background thread.
    Words for Talk to your assistant, roadmap presses, Settings saves and Rebuild presses are
    taken off the list here and acted on after this connection is closed: they
    can ask Claude or take seconds, and the database is never held meanwhile."""
    files = _pending()
    if not files:
        return 0, [], []
    own = con is None
    con = con or _connect()
    if con is None:
        return 0, [], []
    applied, problems, changed, later, setup_later = 0, [], [], [], []
    try:
        for path, rec in files:
            # words typed in the box while the listener was off, a press on a roadmap, a Save in Settings, a Rebuild
            # press: each acted on below, in the order pressed, once this connection is closed
            if rec.get("id") in ("chat", "rebuild", "settings", "voice-learn", "mail-reload") or str(rec.get("id") or "").startswith(("rm:", "tool:", "pt:", "rule-book:", "contact-note:")):
                if rec.get("action") == "answer":
                    later.append(rec)
                _file_done(path)
                continue
            if rec.get("id") == "start-fresh":  # Start fresh is done only by the listener at his press, never late by a pass
                if rec.get("action") == "answer":
                    import start_fresh
                    problems.append(start_fresh.MISSED)
                    _tell_in_chat(start_fresh.MISSED)
                _file_done(path, refused=True)
                continue
            row = _row(con, rec.get("id")) if rec.get("id") else None
            import onboard
            if onboard.is_setup(row):   # a setup card (onboard.py): acted on below, once this connection is closed
                setup_later.append(rec)
                _file_done(path)
                continue
            if is_test(row):            # a made-up card: only the card changes, whatever was pressed
                _apply(con, _test_record(row, rec))
                _file_done(path)
                continue
            import send
            if send.is_press(rec):      # a Send press that missed the listener is never sent late by a pass
                if _row(con, rec.get("id")) is not None:
                    _apply(con, _set(rec["id"], did="Not sent: this page couldn't reach your computer when you pressed Send. "
                                                    "Your draft is kept. Press Send again.", status="Send failed"))
                else:                   # an email written from scratch has no card to say it on
                    said = missed_send_words(rec)
                    problems.append(said)
                    _tell_in_chat(said)
                _file_done(path)
                continue
            if rec.get("action") not in ("answer", "done", "not_mine", "reopen", "note", "_set"):
                problems.append(f"An answer you gave {_stamp(_when(rec))} could not be used, so nothing was changed.")
                _file_done(path, refused=True)
                continue
            if _apply(con, rec) is None:
                problems.append(f"An answer you gave {_stamp(_when(rec))} was for a card that is gone, so nothing was changed.")
                _file_done(path, refused=True)
                continue
            _file_done(path)
            applied += 1
            changed.append(rec["id"])
    finally:
        if own:
            con.close()
    for rec in setup_later:     # a setup card's press or words that missed the listener (onboard.handle keeps each once)
        try:
            import onboard
            out = onboard.handle(rec)
            if out.get("ok"):
                applied += 1
                changed.append(rec["id"])
        except Exception as e:  # noqa: BLE001
            common.log_line(os.path.join(common.LOGS, "errors.log"), f"setup card {rec.get('id')}: {type(e).__name__}: {e}")
    for rec in later:       # after this connection is closed: each opens its own, briefly, when it writes
        try:
            _act_later(rec)
        except Exception as e:  # noqa: BLE001  one press's trouble never stops the others
            common.log_line(os.path.join(common.LOGS, "errors.log"), f"answers later {rec.get('id')}: {type(e).__name__}: {e}")
    return applied, problems, sorted(set(changed))


def _tool_start(rec):
    import tools
    m = re.match(r"^tool:([a-z][a-z_-]{0,29}):\d+$", str(rec.get("id") or ""))
    return tools.start(m.group(1) if m else "", rec.get("at"))


def _act_later(rec):
    """One press apply_files set aside, acted on with no database connection held."""
    iid = str(rec.get("id") or "")
    if iid == "chat":               # words typed in the box while the listener was off: answered now (Claude)
        import chat
        chat.handle(rec.get("text"), rec.get("at"))
    elif iid.startswith("rm:"):     # a press on a roadmap that reached no listener: queued now, the same way
        hold = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "live_page")
        if hold not in sys.path:
            sys.path.insert(0, hold)
        import roadmap_press
        roadmap_press.handle(rec)
    elif iid == "settings":         # a Save press that reached no listener: written now, by the same checks
        import settings_page
        settings_page.act(rec)
    elif iid.startswith("tool:"):   # Start on a tool that reached no listener: its walk-through starts now
        _tool_start(rec)
    elif iid.startswith("pt:"):     # a press on a project tool that reached no listener: acted on now
        import project_tools
        project_tools.handle(rec)
    elif iid.startswith("rule-book:"):  # Keep, Edit or Retire in Settings, Rule book, pressed while nothing listened
        import rule_book
        rule_book.act(rec)
    elif iid.startswith("contact-note:"):   # Save on a contact's notes, pressed while nothing listened
        import contacts_book
        contacts_book.act(rec)
    elif iid == "mail-reload":      # Reload all email history, pressed while nothing listened: started now
        import mail
        mail.reload_history()
    elif iid == "voice-learn":      # Learn my voice now, pressed while nothing listened: learned now
        import voice
        voice.learn_now()
    elif iid == "rebuild":          # a Rebuild press that reached no listener (or a busy database)
        import rebuild
        if not rebuild.covered(rec):
            rebuild.act(rec)


def _patch_snapshot(changed):
    """Put the landed items into Live\\items.json so the next answer, and the
    page, start from what is true now. Whole file, renamed into place."""
    if not changed:
        return
    with _file_lock:
        snap = common.read_json(common.ITEMS_JSON)
        if not snap:
            return
        by_id = {i["id"]: i for i in changed}
        snap["items"] = [by_id.pop(i.get("id"), i) for i in snap.get("items") or []] + list(by_id.values())
        snap["answers_applied_at"] = common.now().isoformat(timespec="seconds")
        tmp = f"{common.ITEMS_JSON}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            json.dump(snap, f, indent=1, default=common._plain)
        os.replace(tmp, common.ITEMS_JSON)


def land_now():
    """Land every waiting answer if the database is free. Returns True when
    nothing is left waiting. One lander at a time in this process."""
    with _landing:
        return _land_waiting()


def _land_waiting():
    files = _pending()
    if not files:
        return True
    con = _connect()
    if con is None:
        return False
    changed = {}
    try:
        for path, rec in files:
            item = _apply(con, rec)
            _file_done(path, refused=item is None)
            if item is not None:
                changed[item["id"]] = item
        changed = [items.read(con, it) for it in changed.values()]
    finally:
        con.close()
    changed = [items.finish(it) for it in changed]
    _patch_snapshot(changed)
    return not _pending()


def _flush_later():
    """Land waiting answers in the background, trying again while a pass holds
    the database. The next pass lands whatever this thread could not."""
    def run():
        end = time.time() + FLUSH_MINUTES * 60
        while time.time() < end:
            try:
                if land_now():
                    return
            except Exception as e:  # noqa: BLE001
                common.log_line(os.path.join(common.LOGS, "errors.log"), f"answers flush: {type(e).__name__}: {e}")
            time.sleep(1)
    with _lock:
        t = _flusher["thread"]
        if t is None or not t.is_alive():
            t = threading.Thread(target=run, name="answers-flush", daemon=True)
            _flusher["thread"] = t
            t.start()


def _own_landed(iid, timeout=30):
    """Wait until no answer for this card is waiting to land (the background step has written it), or the time runs out."""
    end = time.time() + timeout
    while _pending(iid) and time.time() < end:
        if not land_now():
            time.sleep(0.2)
    return not _pending(iid)


def wait_landed(timeout=60):
    """For a short-lived caller: wait until the background thread has landed
    everything, or the time runs out. A long-running listener never needs this."""
    end = time.time() + timeout
    while time.time() < end:
        t = _flusher["thread"]
        if not _pending() and (t is None or not t.is_alive()):
            return True
        time.sleep(0.2)
    return False


def _land(rec):
    """Save rec (the durable record), start landing it in the background, and
    return the item as it reads with every waiting answer applied. No database
    is opened here, so this takes milliseconds whatever a pass is doing."""
    path = _save(rec)
    snap = common.read_json(common.ITEMS_JSON, {}).get("items") or []
    item = next((i for i in snap if i.get("id") == rec["id"]), None)
    if item is None:
        _file_done(path, refused=True)
        return None, False
    for _p, older in _pending(rec["id"]):
        item = _overlay(item, older)
    # the file shows the answer at once, even while a pass holds the database;
    # the database landing follows in the background and writes the same thing
    try:
        _patch_snapshot([item])
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"answers file patch: {type(e).__name__}: {e}")
    _flush_later()
    return item, False


def _set(iid, did=None, **fields):
    """A result the engine writes itself, through the same once-only path."""
    return {"id": iid, "action": "_set", "at": common.now().isoformat(timespec="milliseconds"),
            "fields": fields, "did": did}


# --- words typed on a card: Talk to your assistant, about that card -------------------------------------
STATES = ("in_motion", "yours", "question", "done", "handled")


def think_on(item, text, model=None, at=None, rules=True, lead=None, pressed=None):
    """Words the owner typed on one card. They go to the same chat as the box at the top (chat.handle, with the card
    attached): the same Claude, instructions, saved rules, actions and conversation. Returns (record to land, plain
    result, timing dict); the record is None when no run could be made. pressed: the answer he gave by a button on the
    card's question, which is his authority for the action that answer leads to (a calendar entry)."""
    import chat
    out = chat.handle(text, at=at, card=item, rules=rules, own_step=lead, pressed=pressed)
    timing = {"think": float((out.get("secs") or {}).get("think") or 0), "api": 0.0, "tries": int((out.get("secs") or {}).get("runs") or 0),
              "rule_offer": out.get("rule_offer") or ""}       # a rule the answer gave or asked about: proposed under the box
    said = str(out.get("result") or "")
    if out.get("limit"):
        return None, said, timing
    if not out.get("ok") or out.get("failed"):
        return None, f"Your words are saved, but I could not read them just now. I'll read them the next time I check for messages.", timing
    rec = out.get("card_record")
    if isinstance(rec, dict) and isinstance(rec.get("fields"), dict) and (rec["fields"].get("state") or item.get("state")) != "done":
        rec["fields"].setdefault("answer", None)        # read: the words are in the card's conversation, nothing waits
    return rec, said, timing


def card_record(item, act, text, said, made, when=None):
    """What the chat's card ACTION (act: state, settled, card, ask, waiting_on, next_check) and the emails it wrote for
    the card (made: Ready to send card ids) do to the card: the record to land. With no card ACTION the card keeps its
    state and records his words and the reply."""
    act = act if isinstance(act, dict) else {}
    state = act.get("state") if act.get("state") in STATES else None
    fields = {"status": "Answered"}
    if state:
        fields["state"] = state
    state = state or item.get("state")
    old_asks, settled = settle_old_asks(item.get("asks"), act.get("settled"))
    card = rebuilt_card(item, act.get("card"))
    rewrote = bool(card.get("title"))         # written afresh as a new card (a new title); a front that only follows the talk is not
    if "asks" in card:
        done_qs = {a.lower() for a in settled}
        new_asks = [a for a in card.pop("asks") if a.lower() not in done_qs]
        remaining = new_asks if state not in ("done", "handled") else []
        fields["asks"] = list(remaining)
    else:
        remaining = [a for a in old_asks if a not in settled] if state not in ("done", "handled") else []
        if old_asks:
            fields["asks"] = list(remaining)
    fields.update(card)
    ask = str(act.get("ask") or "").strip()
    if ask:
        fields.update(state="question", asks=remaining + [a for a in [ask] if a not in remaining], status="Needs one more answer")
    elif remaining and fields.get("state", state) == "in_motion" and not made:
        fields.update(state="question", status="Needs one more answer")
    if made:
        # the email waits in Ready to send for his Send; the card itself asks nothing more of him
        if not ask and not remaining and fields.get("state", state) in ("question", "yours"):
            fields["state"] = "handled"
        fields["status"] = "Email in Drafts"
        if item.get("draft") and not (item.get("draft") or {}).get("outbox_id"):
            fields["draft"] = None
    card_ex = act.get("card") if isinstance(act.get("card"), dict) else {}
    fields.update(items.card_extras({**act, "state": fields.get("state", state), "asks": fields.get("asks", item.get("asks")),
                                     "recommended": fields.get("recommended", item.get("recommended")),
                                     "choices": card_ex.get("choices"), "recommended_choice": card_ex.get("recommended_choice"),
                                     "ask_choices": card_ex.get("ask_choices")},
                                    item.get("extra"), answered=True))
    if item.get("draft") and not (item.get("draft") or {}).get("outbox_id") and (fields.get("state") in ("done", "handled") or rewrote):
        fields["draft"] = None
    left_with_you = fields.get("state", state) in ("question", "yours")
    name_what_is_needed(fields, item)
    if left_with_you and fields.get("state") == "handled":
        said = (said + " " if said else "") + NOTHING_NEEDED
    if fields.get("state", state) in ("question", "yours") and not made:
        # the matter is back with him: the card shows open again, not as answered; the history keeps his words
        fields.update(answer=None, answered_at=None)
        fields["status"] = "Needs one more answer" if (ask or remaining) else None
    did = said
    if settled:
        did += "\n" + "\n".join(f"Answered by you: \"{q}\" ({text[:200]})" for q in settled)
    return _set(item["id"], did=did, **fields)


CLOSED_ON_SAVE = "Closed when you saved your words: nothing more is needed from you."


def close_if_free(rec, item):
    """Save closes the card (the owner's ask of 11/23): once his words are acted on, a card the assistant left with nothing
    for him (handled) is Done. One that still waits on him (a question, a step only he can take) stays open with the
    answer showing; one now waiting on someone else stays under Waiting, and one whose email waits in Drafts for his Send
    stays too. Changes rec in place and returns it."""
    f = rec.get("fields") if isinstance(rec, dict) else None
    if isinstance(f, dict) and (f.get("state") or item.get("state")) == "handled" and f.get("status") != "Email in Drafts":
        f["state"] = "done"
        rec["did"] = (rec.get("did") + "\n" if rec.get("did") else "") + CLOSED_ON_SAVE
    return rec


def rebuilt_card(item, card):
    """The card's front written afresh after a reply on it, as {column: value}, from the reply's `card`: the
    recommendation, the why, the questions (and, through card_extras, their choices), and the title and story when
    given. {} when there is none or it changes nothing. A part the reply leaves out stays as it was; one it gives empty
    is cleared."""
    if not isinstance(card, dict):
        return {}
    title = " ".join(str(card.get("title") or "").split())
    out = {"title": title[:300], "short_header": card_mod.whole(card.get("header")) or None} if title else {}
    if not title and card_mod.whole(card.get("header")):
        out["short_header"] = card_mod.whole(card.get("header"))     # a new header for the same title
    if not title and not any(k in card for k in ("why", "recommended", "asks", "detail")):
        return {}                   # nothing of the front written: the card stays as it was
    for k in ("detail", "recommended"):
        if k in card:
            out[k] = str(card.get(k) or "").strip() or None
    if card_mod.whole(card.get("why")):
        out["why"] = card_mod.whole(card.get("why"))
    if isinstance(card.get("asks"), list):
        out["asks"] = [" ".join(str(a).split()) for a in card["asks"] if str(a or "").strip()]
    same = all((item.get(k) or None) == v for k, v in out.items() if k != "asks") and \
        ("asks" not in out or [str(a).strip() for a in item.get("asks") or []] == out["asks"])
    return {} if same else out


def settle_old_asks(asks, settled):
    """(the item's questions, the ones the reply says his words settled). The reply names
    them by number, the first question being 1; anything else in the list is passed over."""
    old = [str(a).strip() for a in (asks or []) if str(a or "").strip()]
    nums = set()
    for n in settled if isinstance(settled, list) else []:
        if isinstance(n, bool):
            continue
        if isinstance(n, str) and n.strip().isdigit():
            n = int(n.strip())
        if isinstance(n, int) and 1 <= n <= len(old):
            nums.add(n)
    return old, [a for i, a in enumerate(old, 1) if i in nums]


def think_pending(pass_id, limit=5):
    """The pass's safety net: a typed answer still marked Thinking after a few
    minutes was never read (the listener was off or stopped). Read it now."""
    cutoff = common.now() - dt.timedelta(minutes=3)
    n, problems = 0, []
    import settings_page
    if settings_page.at_limit():        # the day's limit on thinking runs: typed answers wait, and are read first tomorrow
        return 0, []
    hour = common.now() - dt.timedelta(hours=1)
    waiting = items.rows("status = 'Thinking' AND state <> 'done' AND updated_at < ?", (cutoff,))
    seen = {it["id"] for it in waiting}
    for it in items.rows("answer IS NOT NULL AND state IN ('question', 'yours') AND answered_at < ?", (hour,)):
        lp = it.get("last_press") if isinstance(it.get("last_press"), dict) else {}
        read = str(lp.get("at") or "")[:19] >= it["answered_at"].isoformat(timespec="seconds") if it.get("answered_at") else bool(lp)
        if it["id"] not in seen and not read:      # an answer that sat an hour with no sign it was read or acted on
            waiting.append(it)
            seen.add(it["id"])
            common.log_line(os.path.join(common.LOGS, "answers.log"),
                            f"{it['id']} an answer of {it['answered_at']:%m/%d %H:%M} sat unread for over an hour: read now")
    for it in waiting[:limit]:
        import chat
        if not limits.enough((chat.FOLLOW_UPS + 1) * chat.RUN_SECONDS + 30):
            break
        limits.step(f"reading a typed answer ({it['id']})")
        rec, said, _t = think_on(items.finish(it), it["answer"] or "",
                                 at=it["answered_at"].isoformat(timespec="seconds") if it.get("answered_at") else None)
        if rec is None:
            problems.append(f"your answer on the card \"{it.get('title') or 'with no title'}\" could not be read: {said[:160]}")
            continue
        _save(rec)
        land_now()
        n += 1
    return n, problems


def _owner_send(rec):
    """A Send press from the page. send.py holds the rule and every check; this records the outcome on the card."""
    import send
    t0 = time.time()
    snap = common.read_json(common.ITEMS_JSON, {}).get("items") or []
    item = next((i for i in snap if i.get("id") == rec.get("id")), None)
    rec.setdefault("at", common.now().isoformat(timespec="seconds"))
    ready = item is not None and str(item.get("source_key") or "").startswith("live:ready-")
    if ready:       # a draft in Ready to send: the card as it stands now, never the page's copy of it
        try:
            con = db.connect()    # waits for a pass to let go; a busy store is never "already sent"
        except TimeoutError:
            said = "Not sent: I'm checking for messages right now, so nothing went out. Try again in a minute."
            return {"ok": True, "items": [], "result": said, "thought": False, "sent": False, "secs": {"own": round(time.time() - t0, 3)}}
        try:
            now_card = _row(con, item["id"])
        finally:
            con.close()
        if not now_card or not now_card.get("draft") or now_card.get("state") == "done":
            said = "Not sent: this email was already sent or marked Done."
            return {"ok": True, "items": [], "result": said, "thought": False, "sent": False, "secs": {"own": round(time.time() - t0, 3)}}
    out = send.send_owner_email(rec, item)
    changed = []
    if item is not None and not out.get("duplicate"):
        if out.get("sent") and ready:
            # sent from Ready to send: the card closes in the same step that records the send, with what went
            try:
                m = (json.loads(rec.get("text") or "{}") or {}).get("send_email") or {}
            except ValueError:
                m = {}
            story = (f"{out['result']}\n\nFrom: {m.get('account') or ''}\nTo: {', '.join(m.get('to') or [])}"
                     + (f"\nCopy to: {', '.join(m.get('cc') or [])}" if m.get("cc") else "")
                     + (f"\nBlind copy: {', '.join(m.get('bcc') or [])}" if m.get("bcc") else "")
                     + (f"\nAs: {dict(reply='a reply', reply_all='a reply to all', forward='a forward').get(m.get('type'), '')}" if m.get("type") in ("reply", "reply_all", "forward") else "")
                     + (f"\nAttached: {', '.join(m.get('attach') or [])}" if m.get("attach") else "")
                     + f"\nSubject: {m.get('subject') or ''}\n\n{m.get('body') or ''}")
            follow = _set(item["id"], did=out["result"], status="Sent", state="done", draft=None, detail=story, done_at=common.now())
            drafted = str(((now_card or {}).get("draft") or {}).get("body") or "")
            if drafted.strip():         # a draft I wrote: what he kept and changed is learned (writing.py); never stops the send's record
                import writing
                writing.on_sent(drafted, m.get("body") or "", "email", m.get("to") or [], subject=m.get("subject") or "", card=now_card)
        elif out.get("sent"):
            follow = _set(item["id"], did=out["result"], status="Sent", state="in_motion", draft=None)
        else:
            follow = _set(item["id"], did=out["result"], status="Send failed")
        landed, _ = _land(follow)
        if landed is not None:
            changed = [landed]
    common.log_line(os.path.join(common.LOGS, "answers.log"),
                    f"{rec.get('id')} send | pressed {rec.get('at')} | sent {bool(out.get('sent'))} | {out['result'][:120]}")
    return {"ok": True, "items": changed, "result": out["result"], "thought": False, "sent": bool(out.get("sent")),
            "secs": {"own": round(time.time() - t0, 3)}}


# --- presses: the junk lists, several cards at once, and the table that records every press ---------------
def _as_it_stands(iid):
    """The card as the page's data holds it now, with every answer still waiting applied. None when unknown."""
    snap = common.read_json(common.ITEMS_JSON, {}).get("items") or []
    item = next((i for i in snap if i.get("id") == iid), None)
    if item is None:
        return None
    for _p, older in _pending(iid):
        item = _overlay(item, older)
    return item


def _junk_first(before, press, rec):
    """Junk, Never junk, and an Undo of either: the owner's lists are written now. Returns the record to land:
    the press itself, or, when the list could not be written, a refusal that leaves the card as it was."""
    if not before or not press:
        return rec
    name, when = press["name"], _when(rec)
    try:
        if name in ("junk", "never_junk"):
            would = presses.fields(before, press, when, lambda r: {}).get("last_press") or {}
            if would.get("ok"):
                ok, why = presses.junk_list(before, name, when=when)
                if not ok:
                    return _set(rec["id"], last_press=presses._mark(name, when, why, ok=False))
        elif name == "undo":
            last = before.get("last_press") if isinstance(before.get("last_press"), dict) else {}
            if last.get("ok") and last.get("press") in ("junk", "never_junk"):
                ok, why = presses.junk_list(before, last["press"], undo=True)
                if not ok:
                    return _set(rec["id"], last_press=presses._mark(name, when, why, ok=False))
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"junk press: {type(e).__name__}: {e}")
        return _set(rec["id"], last_press=presses._mark(name, when, "Your junk list could not be written just now, "
                                                        "so nothing was changed.", ok=False))
    return rec


def settle_junk_answers():
    """A Junk or Never junk answer recorded on a junk question card but never acted on (an older version only
    recorded it): the owner's lists are written and the card closes now, by the same steps as the press, as
    of when he answered. Returns (cards settled, problems)."""
    import presses
    con = _connect()
    if con is None:
        return 0, []
    settled, problems = 0, []
    try:
        items.ensure_on(con)
        ids = [r[0] for r in con.execute("SELECT id FROM live_items WHERE state <> 'done' AND source_key LIKE ?",
                                         (presses.JUNK_ASK + "%",)).fetchall()]
        for iid in ids:
            item = _row(con, iid)
            said = str(item.get("answer") or "").strip()
            if not presses.is_junk_ask(item) or said.lower() not in ("junk", "never junk") or not item.get("answered_at"):
                continue
            rec = {"id": iid, "action": "answer", "text": said, "at": item["answered_at"].isoformat(timespec="seconds")}
            press = presses.parse(item, rec)
            got = _junk_first(item, press, rec)
            if got is not rec:          # the list could not be written: said on the card, tried again next pass
                _apply(con, got)
                problems.append(f"Your {said} answer on a junk question could not be written to your junk list. I'll try again the next time I check for messages.")
                continue
            f = presses.fields(item, press, _when(rec), lambda r: {})
            f["assistant_did"] = _add(f.get("assistant_did") or item.get("assistant_did"), f"Your {said} answer of {_stamp(_when(rec))} is acted on now.")
            _apply(con, _set(iid, **f))
            settled += 1
    finally:
        con.close()
    return settled, problems


def _ignore_list(address, add):
    """Put a sender on the owner's list of senders to always ignore, or take them off. True when it changed."""
    import setup_steps
    now = [str(x).strip().lower() for x in (common.personal().get("ignore_senders") or []) if str(x).strip()]
    address = str(address or "").strip().lower()
    if not address or (address in now) == add:
        return False
    setup_steps.ignore_senders(now + [address] if add else [x for x in now if x != address])
    return True


def _through_list(address, add):
    """Put a sender on "people who always get through", or take them off."""
    import filters
    now = filters.get()["always_through"]
    address = str(address or "").strip().lower()
    if not address or (address in [x.lower() for x in now]) == add:
        return False
    filters.write({"always_through": now + [address] if add else [x for x in now if x.lower() != address]})
    return True


def _lists_first(before, press, rec):
    """The teaching presses that change one of the owner's lists do it the same moment, before the card changes.
    Returns the record to land (a refusal when the list could not be written)."""
    if not before or not press or rec.get("action") == "_set":
        return rec
    name, when = press["name"], _when(rec)
    who = (before.get("sender") or {}) if isinstance(before.get("sender"), dict) else {}
    address = str(who.get("address") or "").lower()
    try:
        would = presses.fields(before, press, when, lambda r: {}).get("last_press") or {}
        if not would.get("ok"):
            return rec
        if name in ("rsi_promote", "rsi_apply", "rsi_reject"):    # a rule change card: the coach's promote, apply or reject
            import rsi_loop
            ok, said, close = rsi_loop.decide(before, press)
            if ok:
                return dict(rec, rsi_decided=True)      # landed later from its file (a busy database), it is still the one done
            if close:       # it can never be done now: the card closes with why, so its section is not held
                return _set(rec["id"], did=f"{said} ({_stamp(when)})", state="done", status="Closed", answered_at=when,
                            last_press=presses._mark(name, when, said))
            return _set(rec["id"], last_press=presses._mark(name, when, said, ok=False))
        if name == "not_needed" and press.get("scope") == "sender":
            _ignore_list(address, True)
        elif name == "always_show" and press.get("scope") == "sender":
            _through_list(address, True)
            _ignore_list(address, False)
            presses.junk_list(before, "never_junk")
        elif name == "sender_show":
            _through_list(address, True)
        elif name == "sender_hold":
            _ignore_list(address, True)
        elif name == "write":               # the owner's yes: the one new file, written now, only because they said yes
            if press.get("level") == "yes":
                import projects
                done, said = projects.write(before)
                if not done:
                    return _set(rec["id"], last_press=presses._mark(name, when, said, ok=False))
        elif name == "standing":            # the owner's answer to an offer is the one way a standing approval is made from a card
            import standing
            offer = (before.get("extra") or {}).get("offer") or {}
            if press.get("level") == "no":
                standing.decline(offer["kind"], offer["area"], offer.get("scope"))
            else:
                standing.make_entry(offer["kind"], offer["area"], press["level"], f"You said yes on a card, {when.month}/{when.day}",
                                    offer.get("scope"), offer.get("account"))
            standing.write_feed()
        elif name == "junk":
            _through_list(address, False)       # the newest choice wins
        elif name == "undo":
            last = before.get("last_press") if isinstance(before.get("last_press"), dict) else {}
            if last.get("ok") and str(last.get("press")) in ("standing_close", "standing_drop"):
                import standing
                standing.mark_undone(before["id"])
            if last.get("ok") and str(last.get("press")).startswith("level_"):     # a level 2 or 3 action taken back
                import levels
                levels.undone(before)
            if last.get("ok") and last.get("press") == "not_needed" and "ignore list" in str(before.get("assistant_did") or "").split("\n")[-1]:
                _ignore_list(address, False)
            if last.get("ok") and last.get("press") == "always_show" and "always get through" in str(last.get("happened") or ""):
                _through_list(address, False)
                presses.junk_list(before, "never_junk", undo=True)
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"list press: {type(e).__name__}: {e}")
        return _set(rec["id"], last_press=presses._mark(name, when, "Your list could not be written just now, so nothing was changed.", ok=False))
    return rec


def _old_card(press, rec):
    """An answer about one old card, pressed on the asking card: keep, someday or drop lands on that card itself."""
    todo = {"keep": {"name": "old_keep"}, "someday": {"name": "later", "when": "someday"}, "drop": {"name": "done"}, "done": {"name": "done"},
            "later": {"name": "later", "when": press.get("when") or "tomorrow", "until": press.get("until") or ""}}[press["do"]]
    item, _ = _land({"id": press["card"], "action": "answer", "text": json.dumps({"press": todo}), "at": rec["at"],
                     "acted_at": rec.get("acted_at")})
    return [item] if item is not None else []


def _held_press(rec, t0):
    """"I should have seen this" on a row of the Hidden list: that message's card, made now. No Claude."""
    import held
    press = presses.parse({}, rec) or {}
    if press.get("name") == "read":        # open the row to read the message: it stays hidden, nothing else changes
        ok, result = held.read(rec["id"], press.get("part"), rec.get("at"))
        presses.record(pressed_at=rec.get("at"), received_at=rec.get("acted_at") or common.now(), item_id=rec["id"],
                       item_title="A message under Hidden", press="read", choice=f"part {press.get('part') or 1}", words="-",
                       device=rec.get("device"), happened=result, ok=ok, claude_ran=False, secs=time.time() - t0)
        return {"ok": True, "items": [], "result": result, "thought": False, "secs": {"own": round(time.time() - t0, 3)}}
    calls = None
    if press.get("name") != "should_have_seen":
        result, item = "I do not know that button, so nothing was changed.", None
    else:
        calls = _rule_book("held_calls", rec["id"])      # what held it, read before its card is made: making it overwrites that
        m = held.KEY.match(str(rec["id"]))
        if m.group(2):      # a card kept out by the setting "hide things that need nothing": it is on the page from now on
            con = _connect()
            row = _row(con, m.group(2)) if con is not None else None
            if con is not None:
                con.close()
            if row is None:
                item, result = None, "I'm checking for messages right now. Press it again in a minute."
            else:
                _save(_set(m.group(2), did=f"You said {_stamp(_when(rec))} you should have seen this.", status=card.SEEN_STATUS))
                land_now()
                item = items.card_for(m.group(2))
                result = "It is on your page now."
                try:
                    held.write()
                except Exception:  # noqa: BLE001
                    pass
        else:
            item, result = held.show(int(m.group(1)))
        if item is not None:
            _patch_snapshot([item])
    _record(rec, t0, item or {"id": rec["id"], "title": "A message under Hidden"}, press.get("name") or "press", result,
            item is not None or "within" in result, False, press or None, calls=calls)
    common.log_line(os.path.join(common.LOGS, "answers.log"), f"{rec['id']} should_have_seen | pressed {rec.get('at')} | {round(time.time() - t0, 3)}s")
    return {"ok": True, "items": [item] if item else [], "result": result, "thought": False, "secs": {"own": round(time.time() - t0, 3)}}


def _record(rec, t0, item, name, happened, ok, claude_ran, press=None, calls=None, pick=None):
    """One row in the table of presses for this answer, whatever it was, with the one meaning it carries; and, for a press
    that landed on a card that came from messages, its rows in the rule book (rule_book.py). calls: what was decided about
    the card's messages, read before the press changed it. pick: what I predicted he would do on the card, read before the
    press (picks.of); then his typed words write rows too (neutral: they say nothing about show or hide), and every row
    carries the pick, what he did and whether it matched. The page marks a press of the pick itself ("pick": "1")."""
    text = (rec.get("text") or "").strip()
    typed = name == "words"
    if press and press.get("via"):         # No on a standing approval offer or a project write: recorded as the No it was
        name = press["via"]
    if not name:
        name = rec.get("page_action") or rec.get("action") or "answer"
        if name == "answer" and text.startswith("{"):
            name = "press"
    choice = presses.choice_of(press) if press else ("-" if typed or text.startswith("{") else (rec.get("label") or text or "-"))
    meaning, button = presses.meaning_of(press) if press else None, None
    picked = presses.chosen(rec) if not press else None
    if picked and "bad" not in picked:      # a choice button: its words were read as before; its id and meaning are kept here
        meaning, button = picked["meaning"], picked["button"]
        if typed or name in ("answer", "press"):
            name, choice, typed = "choice", rec.get("label") or text or "-", False
    presses.record(pressed_at=rec.get("at"), received_at=rec.get("acted_at") or common.now(),
                   item_id=(item or {}).get("id") or rec.get("id"), item_title=(item or {}).get("title") or "-",
                   press=name, choice=choice, words=text if typed else "-", device=rec.get("device"),
                   happened=happened, ok=ok, claude_ran=claude_ran, secs=time.time() - t0, meaning=meaning, button=button)
    took = str(rec.get("pick") or "") == "1"
    if ok and typed and pick is not None and text:
        _rule_book("on_press", item, "words", "neutral", "-", text[:200], rec.get("at"), calls, pick, took, text)
    elif ok and not typed and (press or button):
        _rule_book("on_press", item, name, meaning or presses._row_meaning(name, choice, happened), button or "-", choice,
                   rec.get("at"), calls, pick, took, text if name == "choice" else "")


def _pick_before(before):
    """The card's pick as it stood before the press (picks.of), or None; never in the way of a press."""
    try:
        import picks
        return picks.of(before) if before else None
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"pick: {type(e).__name__}: {e}")
        return None


def _switch_teaches(item):
    """A switchable button (presses.SWITCHES) offers a rule through the teach flow at learning level 1, and at levels 2 and 3
    while no rule change is open for the card's section (rsi_loop.open_card): "teach"; "waiting" when one is open; None
    otherwise (it only records). A rule offered this way is a rule card at every level: nothing is in force until Approve."""
    try:
        import rsi_loop
        import rule_book
        import settings_page
        sec = rule_book.section(item)
        level = settings_page.learning_levels().get(sec, 1)
        if level == 1 or (level in (2, 3) and rsi_loop.open_card(sec) is None):
            return "teach"
        return "waiting" if level in (2, 3) else None
    except Exception as e:  # noqa: BLE001  the press stands; only the offer is left out, and the reason is logged
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"switch teach: {type(e).__name__}: {e}")
        return None


def _rule_book(fn, *a):
    """The rule book (rule_book.py), never in the way of a press: anything it cannot do is logged and the press goes on."""
    try:
        import rule_book
        return getattr(rule_book, fn)(*a)
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"rule book: {type(e).__name__}: {e}")
        return None


def _press_all(rec, t0):
    """Got it all: every named card that needs nothing is closed (every such open card when none is named).
    Undo on the same key brings back the cards the last one closed. No Claude."""
    press = presses.parse({}, rec) or {}
    name, changed = press.get("name"), []
    snap = common.read_json(common.ITEMS_JSON, {}).get("items") or []
    if name == "got_it_all":
        want = set(press["ids"]) if "ids" in press else None
        ids = [i["id"] for i in snap if i.get("state") != "done" and card.needs(i) == "nothing"
               and (want is None or i["id"] in want)]
        got_it = json.dumps({"press": {"name": "got_it"}})
        for iid in ids:
            item, _ = _land({"id": iid, "action": "answer", "text": got_it, "at": rec["at"], "acted_at": rec["acted_at"]})
            if item is not None and item.get("state") == "done":
                changed.append(item)
        common.write_json(presses.LAST_ALL, {"at": rec["at"], "ids": [i["id"] for i in changed]})
        left = len(want) - len(changed) if want is not None else 0
        result = (f"Done: {len(changed)} card{'s' if len(changed) != 1 else ''} that needed nothing."
                  if changed else "No card needed closing.") + \
            (f" {left} still need{'s' if left == 1 else ''} something from you, so {'it was' if left == 1 else 'they were'} left." if left > 0 else "")
        ok = True
    elif name == "undo":
        last = common.read_json(presses.LAST_ALL, {}) or {}
        for iid in last.get("ids") or []:
            item, _ = _land({"id": iid, "action": "reopen", "at": common.now().isoformat(timespec="seconds"),
                             "acted_at": rec["acted_at"]})
            if item is not None:
                changed.append(item)
        common.write_json(presses.LAST_ALL, {"at": None, "ids": []})
        result, ok = (f"Brought back {len(changed)} card{'s' if len(changed) != 1 else ''}." if changed
                      else "There was nothing to bring back."), True
    else:
        result, ok = "I do not know that button, so nothing was changed.", False
    _record(rec, t0, {"id": "all", "title": f"{len(changed)} card(s)"}, name or "press", result, ok, False, press or None)
    if ok and changed:          # the rule book: each card it closed or brought back, one look at the database for all
        _rule_book("on_presses", changed, name, presses.meaning_of(press), "-", presses.choice_of(press), rec.get("at"))
    common.log_line(os.path.join(common.LOGS, "answers.log"),
                    f"press {name} | pressed {rec.get('at')} | {len(changed)} card(s) | {round(time.time() - t0, 3)}s")
    return {"ok": True, "items": changed, "result": result, "thought": False, "secs": {"own": round(time.time() - t0, 3)}}


# --- the one function the listener calls ------------------------------------------------------------
UNDO_SECONDS = 600
GO_WORDS = "Approve on the change's card (pressed on the page)"


def start_hidden(args):
    """Start a program hidden and on its own, so it outlives the listener it may restart: detached, out of the
    listener's job; where Windows will not let it leave that job, through Windows' own process service instead."""
    flags = 0x00000008 | 0x00000200 | 0x01000000 | getattr(subprocess, "CREATE_NO_WINDOW", 0)   # detached, own group, breakaway
    env = dict(os.environ, ASSISTANT_LIVE_HOME=common.HOME)
    try:
        subprocess.Popen(args, creationflags=flags, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True)
        return True
    except OSError:
        line = subprocess.list2cmdline(args)
        ps = ("$env:ASSISTANT_LIVE_HOME=" + json.dumps(common.HOME) + "; "
              "Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine=" + json.dumps(line) + "}")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=60)
        return r.returncode == 0


def _change_go(rec):
    """The owner's go on a change talked through in Talk to your assistant: recorded through the change helper (the undo copy is saved
    first), then change_job.py makes it, hidden, and says how it went in Talk to your assistant."""
    m = re.match(r"^change-go:(ch-\d{4,6}):\d+$", str(rec.get("id") or ""))
    try:
        press = (json.loads(rec.get("text") or "{}") or {}).get("press") or {}
    except ValueError:
        press = {}
    if not m or press.get("name") != "change_go" or press.get("change") != m.group(1):
        return {"ok": False, "error": "That press could not be read. Nothing was changed.", "items": []}
    cid = m.group(1)
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    r = subprocess.run([sys.executable, os.path.join(here, "setup", "setup_home.py"), "--root", root, "--home", common.HOME,
                        "change-go", cid, GO_WORDS], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), env=dict(os.environ, ASSISTANT_LIVE_HOME=common.HOME))
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        got = {"ok": False, "says": "your computer gave no answer"}
    if not got.get("ok"):
        return {"ok": True, "items": [], "result": f"Not started: {got.get('says') or 'your go did not reach the change'}. Nothing was changed.",
                "thought": False, "secs": {}}
    if not start_hidden([sys.executable, os.path.join(here, "change_job.py"), cid]):
        subprocess.run([sys.executable, os.path.join(here, "setup", "setup_home.py"), "--root", root, "--home", common.HOME,
                        "change-abandon", cid, "it could not be started on this computer"], capture_output=True, timeout=300,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), env=dict(os.environ, ASSISTANT_LIVE_HOME=common.HOME))
        return {"ok": True, "items": [], "result": "The change could not be started on your computer, so it was set back and "
                                                   "nothing was changed. Ask for it again in a minute.", "thought": False, "secs": {}}
    return {"ok": True, "items": [], "result": "Making the change now. Each step shows under Changes; how it went comes back in Talk to your assistant.",
            "thought": False, "secs": {}}


def _change_drop(rec):
    """The owner's Cancel on a change not yet given its go: set aside through the change helper (change-drop); nothing was edited."""
    m = re.match(r"^change-drop:(ch-\d{4,6}):\d+$", str(rec.get("id") or ""))
    try:
        press = (json.loads(rec.get("text") or "{}") or {}).get("press") or {}
    except ValueError:
        press = {}
    if not m or press.get("name") != "change_drop" or press.get("change") != m.group(1):
        return {"ok": False, "error": "That press could not be read. Nothing was changed.", "items": []}
    here = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run([sys.executable, os.path.join(here, "setup", "setup_home.py"), "--root", os.path.dirname(os.path.dirname(here)),
                        "--home", common.HOME, "change-drop", m.group(1)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), env=dict(os.environ, ASSISTANT_LIVE_HOME=common.HOME))
    try:
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        got = {"ok": False, "says": "your computer gave no answer"}
    if not got.get("ok"):
        return {"ok": True, "items": [], "result": f"Not cancelled: {got.get('says') or 'your computer refused'}.", "thought": False, "secs": {}}
    import chat         # the talk hears of it, so it never again speaks of this change as waiting
    chat._add({"who": "assistant", "source": None, "at": common.now().isoformat(timespec="seconds"),
               "text": f"Change {m.group(1)} was cancelled when you pressed Cancel this change; nothing was changed."})
    return {"ok": True, "items": [], "result": "Cancelled. The change was set aside before anything was edited.", "thought": False, "secs": {}}


MOD_FILES = ("mod.json", "mod.py", "checks.json")       # a change's own mod when the talk named no files


def _change_from_offer(offer):
    """Approve on a change he asked for (card_rules.asked_card): the change helper records it, agrees it in the words on the
    card, and takes the press as the go; then the change job makes it, as "Yes, make this change" did. (plain words, started)."""
    import chat
    here = os.path.dirname(os.path.abspath(__file__))
    if os.path.join(here, "setup") not in sys.path:
        sys.path.insert(0, os.path.join(here, "setup"))
    import setup_changes as sc
    book = sc.Book(os.path.dirname(common.HOME), common.HOME)
    c = None
    try:
        c = book.start(offer.get("words") or offer.get("text") or "")
        mod = str(offer.get("mod") or "").strip().lower()
        if not chat.MOD_NAME.match(mod):
            mod = "change-" + c["id"].split("-")[1]
        names = [str(f or "").replace("\\", "/").split("/")[-1] for f in offer.get("files") or []]
        names = [n for n in names if re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", n) and not n.startswith(".")] or list(MOD_FILES)
        names = list(dict.fromkeys(names + ["checks.json"]))
        book.agree(c["id"], "mods", offer.get("text") or "", [f"Live/mods/{mod}/{n}" for n in names])
    except sc.Refused as e:
        if c:
            try:
                book.drop(c["id"])
            except sc.Refused:
                pass
        return f"Not started: {e} Nothing was changed; the change is still on this card.", False
    out = _change_go({"id": f"change-go:{c['id']}:{int(time.time() * 1000)}",
                      "text": json.dumps({"press": {"name": "change_go", "change": c["id"]}})})
    said = str(out.get("result") or out.get("error") or "")
    if not said.startswith("Making the change"):
        try:            # not started: its record is set aside; the proposal stays on the card for another Approve
            book.drop(c["id"])
        except sc.Refused:
            pass
        return said.replace(".. ", ". ") + " The change is still on this card.", False
    return said, True


def _asked_told(item, offer, did, said):
    """Approve, Disapprove or Cancel on a rule or change he asked for in words: said in Talk to your assistant too, so the
    conversation knows where it stands (a Cancel the talk never heard of is how a change was once said to wait for a button)."""
    import chat
    about = {"id": item.get("id"), "title": str(item.get("short_header") or item.get("title") or "")[:200]}
    what = "change" if offer.get("made") == "change" else "rule"
    chat._add({"who": "assistant", "card": about, "at": common.now().isoformat(timespec="seconds"), "source": None,
               "text": f"{did} on the card: the {what} \"{offer.get('text') or ''}\". {said}".strip()})


def _undo_change(rec):
    """The owner's Undo of a change, from the page: the undo skill's own command does it (setup_home.py undo, in the program's setup folder),
    so the files go back exactly as the skill puts them back, by their saved copies. Later changes built on it go too: the page
    showed them before he pressed."""
    import changes_feed
    m = re.match(r"^change-undo:(ch-\d{4,6}):\d+$", str(rec.get("id") or ""))
    try:
        press = (json.loads(rec.get("text") or "{}") or {}).get("press") or {}
    except ValueError:
        press = {}
    if not m or press.get("name") != "undo_change" or press.get("change") != m.group(1):
        return {"ok": False, "error": "That Undo could not be read. Nothing was changed.", "items": []}
    cid = m.group(1)
    tool = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup", "setup_home.py")
    if not os.path.exists(tool):
        return {"ok": False, "error": "Undo is not on this computer yet. Nothing was changed.", "items": []}
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    changes_feed.undoing(cid)
    try:
        r = subprocess.run([sys.executable, tool, "--root", root, "--home", common.HOME, "undo", cid, "--with-later"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=UNDO_SECONDS,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), env=dict(os.environ, ASSISTANT_LIVE_HOME=common.HOME))
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
        except (ValueError, IndexError):
            got = {}
    except subprocess.TimeoutExpired:
        got = {"ok": False, "says": "the undo did not finish in time"}
    finally:
        changes_feed.done_undoing()
    if not got.get("ok"):
        return {"ok": False, "error": f"Not undone: {got.get('says') or 'the undo could not run'}. Nothing was changed.", "items": []}
    said = "Undone: the files are back as they were before the change."
    if len(got.get("undone") or []) > 1:
        said = f"Undone, with the {len(got['undone']) - 1} later change(s) built on it: the files are back as they were."
    if got.get("working") is False:
        bad = next((s for s in got.get("steps") or [] if not s.get("ok")), {})
        said += f" The page could not be checked afterwards ({bad.get('name')}: {bad.get('why')})."
    return {"ok": True, "items": [], "result": said, "thought": False, "secs": {}}


def _undo_learned(rec):
    """The owner's Undo, in Change history, of a rule change a Level 3 section made on its own (changes_feed.learned): his
    rules go back to the version kept before it (coach.undo_self). No Claude."""
    import changes_feed
    import coach
    m = re.match(r"^change-undo:rsi-(\d{8}-\d{6}-[0-9a-f]{4}):\d+$", str(rec.get("id") or ""))
    try:
        press = (json.loads(rec.get("text") or "{}") or {}).get("press") or {}
    except ValueError:
        press = {}
    if not m or press.get("name") != "undo_change" or press.get("change") != changes_feed.LEARNED_PREFIX + m.group(1):
        return {"ok": False, "error": "That Undo could not be read. Nothing was changed.", "items": []}
    try:
        said = coach.undo_self(m.group(1))
    except ValueError as e:
        return {"ok": False, "error": f"Not undone: {e}. Nothing was changed.", "items": []}
    except Exception as e:  # noqa: BLE001  something on this computer: nothing is claimed
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"undo learned: {type(e).__name__}: {e}")
        return {"ok": False, "error": f"Not undone: something went wrong on your computer ({type(e).__name__}).", "items": []}
    return {"ok": True, "items": [], "result": said, "thought": False, "secs": {}}


TEST_PREFIX = "test:"          # made-up cards (test_cards.py): a press changes only the card
TEST_SAYS = "Test card: nothing was sent, and no account, list or rule was touched."
CARD_ONLY = ("done", "got_it", "later", "someday", "bring_back")


def is_test(item):
    return str((item or {}).get("source_key") or "").startswith(TEST_PREFIX)


def _test_record(item, rec):
    """The record to land for a press on a test card: Done, Snooze, Bring back (and Not mine, Reopen) as on any card, which
    change only the card; anything else (Junk, Never junk, Not needed, Approve, Send, words) is noted on it and does nothing."""
    import presses
    action = rec.get("action")
    press = presses.parse(item, rec) if action == "answer" else None
    if action in ("done", "not_mine", "reopen", "note") or (press and press.get("name") in CARD_ONLY):
        return rec
    what = (press or {}).get("name") or ("send" if action not in ("answer",) else "words")
    return _set(item["id"], did=f"Test card: your {what.replace('_', ' ')} press is recorded here only. " + TEST_SAYS,
                last_press=presses._mark(what, _when(rec), TEST_SAYS))


def _scan_after(rule, source_id, on_update, item):
    """An approved rule goes over the other open cards (card_rules.scan). (the note the source card keeps or None, the plain
    words). The rule is saved whatever happens here."""
    if not rule:
        return None, ""
    if on_update:
        try:
            on_update([item])
        except Exception:  # noqa: BLE001
            pass
    try:
        n, sid = card_rules.scan(rule, exclude=[source_id], source=source_id)
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"rule scan: {type(e).__name__}: {e}")
        return None, "I couldn't go through your other open cards just now. The rule starts the next time I check for messages."
    return card_rules.note(n, sid, rule)


def _offer_after(card_was, follow, words, offered, said, rec):
    """The card's answer gave a rule, or asked in words whether to save one: it is proposed under the box with the four
    buttons instead, never asked in the reply. His words were already acted on, so the card stays open holding the proposal,
    and where the answer left it is kept (was) for Approve, Disapprove and Cancel. (the record to land, the plain words)."""
    got = card_rules.check(card_was, words, offered=offered) if card_rules.may_check(card_was) else None
    if not got:
        return follow, said
    f = follow["fields"]
    after = {**card_was, **f}           # the card as the answer left it
    fields = card_rules.offer_fields(after, words, got, _when(rec), was=presses._was(after), acted=True)
    said = " ".join(x for x in (said, card_rules.offer_said(got)) if x)
    f.update(fields)
    f["last_press"] = presses._mark("words", _when(rec), said, claude=True, was=presses._was(card_was))
    did = str(follow.get("did") or "").replace("\n" + CLOSED_ON_SAVE, "").replace(CLOSED_ON_SAVE, "")
    follow["did"] = (did + "\n" if did else "") + f"I offered it as a rule: \"{got['rule']}\""
    return follow, said


def _offer_answered(item, offer, do, when, on_update):
    """Approve or Disapprove on a rule proposed after his words were already acted on (offer "acted"): only the rule is
    answered; the card goes back where that answer left it. (the card, plain words, whether Claude ran)."""
    was = offer.get("was") if isinstance(offer.get("was"), dict) else {}
    back = {"state": was.get("state") or item.get("state"), "status": was.get("status"), "shelf": was.get("shelf"),
            "later_until": presses._time(was.get("later_until")), "checkback_date": presses._date(was.get("checkback_date"))}
    extra = dict(item.get("extra") or {}) if isinstance(item.get("extra"), dict) else {}
    extra.pop(card_rules.OFFER_KEY, None)
    made = offer.get("made")
    if do != "approve":
        said = ("Not made. Nothing was changed." if made == "change" else "No rule saved." if made
                else "No rule saved. Your words were already acted on for this card.")
        it, _ = _land(_set(item["id"], did=said, extra=extra or None, last_press=presses._mark("rule_offer", when, said), **back))
        if made:
            _asked_told(item, offer, "Disapproved", said)
        return it, said, False
    if made == "change":        # his Approve is the go: the change is recorded, agreed and made by the change job
        said, ok = _change_from_offer(offer)
        back = back if ok else {"state": "question", "status": "Change proposed"}
        if not ok:
            extra[card_rules.OFFER_KEY] = offer         # not started: the proposal stays, with its four buttons
        it, _ = _land(_set(item["id"], did=said, extra=extra or None, last_press=presses._mark("rule_offer", when, said, ok=ok), **back))
        _asked_told(item, offer, "Approved", said)
        return it, said, False
    rule = filters.add_rule(offer.get("text") or "", offer.get("way") or "card_rule",
                            "You told me in Talk to your assistant" if made else
                            f"Your words on the card \"{str(item.get('header') or item.get('title') or '')[:80]}\"",
                            reason=offer.get("reason") or "")
    if made:
        _asked_told(item, offer, "Approved", f"Your rule is saved: \"{rule['text']}\".")
    it, _ = _land(_set(item["id"], extra=extra or None, **back))
    note, scanned = _scan_after(rule, item["id"], on_update, it or item)
    if note:
        extra[card_rules.SCAN_KEY] = note
    said = " ".join(x for x in (f"Your rule is saved: \"{rule['text']}\".", scanned) if x)
    it, _ = _land(_set(item["id"], did=f"Your rule is saved: \"{rule['text']}\".", extra=extra or None,
                       last_press=presses._mark("rule_offer", when, said, claude=True)))
    return it, said, True


def _rule_offer(before, item, press, rec, on_update):
    """Approve, Disapprove or Discuss on a rule proposed from his words on this card (Cancel is all in presses.fields).
    Returns (the card, plain words, whether Claude ran)."""
    import chat
    offer = ((before or {}).get("extra") or {}).get(card_rules.OFFER_KEY) or {}
    do, when = press["do"], _when(rec)
    if on_update:
        try:
            on_update([item])
        except Exception:  # noqa: BLE001
            pass
    if do == "discuss":         # reworded on the card: the same four buttons under the new wording
        talk = [t for t in offer.get("talk") or [] if isinstance(t, dict)] + [{"who": "you", "text": press["words"]}]
        if offer.get("made") == "change":       # a change he asked for: its one sentence is reworded as a change, not a card rule
            got = card_rules.reword_change(offer, talk)
        else:
            got = card_rules.check(before, offer.get("words") or "", [{"who": "assistant", "text": f"Proposed rule: {offer.get('text')}"}] + talk)
        if not got:
            said = "I could not reword it just now. The rule is as it was; Discuss again, or Approve, Disapprove or Cancel."
            extra = dict(item.get("extra") or {}) if isinstance(item.get("extra"), dict) else {}
            extra[card_rules.OFFER_KEY] = dict(offer, talk=(talk + [{"who": "assistant", "text": said}])[-10:])
            it, _ = _land(_set(item["id"], extra=extra, status="Rule proposed",
                               last_press=presses._mark("rule_offer", when, said, ok=False, claude=True)))
            return it, said, True
        said = f"Reworded: \"{got['rule']}\"" + (f" {got['say']}" if got.get("say") else "")
        fields = card_rules.offer_fields(before, offer.get("words") or "", got, when,
                                         talk=talk + [{"who": "assistant", "text": said}], was=offer.get("was"), keep=offer)
        fields["extra"][card_rules.OFFER_KEY]["at"] = offer.get("at") or fields["extra"][card_rules.OFFER_KEY]["at"]
        chat.note_exchange(press["words"], said, before, rec.get("at"))
        it, _ = _land(_set(item["id"], did=f"Reworded: \"{got['rule']}\"",
                           last_press=presses._mark("rule_offer", when, said, claude=True), **fields))
        return it, said, True
    if offer.get("acted"):      # his words were acted on when the rule was offered: only the rule is answered now
        return _offer_answered(item, offer, do, when, on_update)
    # Approve and Disapprove: his words are acted on for this card, as any typed words are, and no rule is saved from the talk.
    # The rule is saved, and the other cards gone over, only once that run has acted; a run that could not be made leaves the
    # proposal on the card as it was, with its four buttons.
    if do == "approve":
        lead = (f"(I approved this as my standing rule: \"{offer.get('text')}\". The program saves it: do not save it yourself. "
                "Do on this card what the rule and my words say.)")
    else:
        lead = "(One time only, for this card: this is not a standing rule, so save no rule. Do on this card what my words say.)"
    _own_landed(item["id"])
    about = {"id": item["id"], "title": str(item.get("short_header") or item.get("title") or "")[:200]}
    chat._add({"who": "you", "at": rec.get("at") or when.isoformat(timespec="seconds"), "card": about,      # what he pressed, in his talk
               "text": (f"Approve the rule: \"{offer.get('text')}\"" if do == "approve" else "Disapprove the rule; this time only.")
               + f" ({offer.get('words') or ''})"})
    follow, said, _timing = think_on(item, offer.get("words") or "", at=rec.get("at"), rules=False, lead=lead)
    if follow is None:
        extra = dict(item.get("extra") or {}) if isinstance(item.get("extra"), dict) else {}
        extra[card_rules.OFFER_KEY] = offer
        said = f"{said} The rule is still proposed; press Approve or Disapprove again."
        it, _ = _land(_set(item["id"], extra=extra, state="question", status="Rule proposed",
                           last_press=presses._mark("rule_offer", when, said, ok=False, claude=True)))
        return it, said, True
    close_if_free(follow, item)
    it, _ = _land(follow)
    if do == "approve":
        rule = filters.add_rule(offer.get("text") or "", offer.get("way") or "card_rule",
                                f"Your words on the card \"{str((before or {}).get('header') or (before or {}).get('title') or '')[:80]}\"",
                                reason=offer.get("reason") or "")
        note, scanned = _scan_after(rule, item["id"], on_update, it or item)
        said = " ".join(x for x in (f"Your rule is saved: \"{rule['text']}\".", said, scanned) if x)
        now = it or item
        extra = dict(now.get("extra") or {}) if isinstance(now.get("extra"), dict) else {}
        if note:
            extra[card_rules.SCAN_KEY] = note
            it, _ = _land(_set(item["id"], extra=extra))
    it, _ = _land(_set(item["id"], last_press=presses._mark("rule_offer", when, said, claude=True)))
    return it, said, True


def act_on_answer(answer, on_update=None):
    """Act on one answer now. See the module text for what comes back."""
    t0 = time.time()
    secs = {"own": 0.0, "think": 0.0}
    try:
        rec = {k: v for k, v in dict(answer).items() if k != "fields"}
        if rec.get("id") == "chat":         # the box at the top of the page: words to the assistant, not an answer to an item
            import chat
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            # the card open on his page when he wrote ("this card"): sent by the page with his words; none when none was open
            oid = str(rec.get("open_card") or "")
            opened = _as_it_stands(oid) if re.fullmatch(r"L\d{1,7}", oid) else None
            return chat.handle(rec.get("text"), rec.get("at"), open_card=opened)
        if rec.get("id") == "settings":     # a Save press in the page's Settings panel: checked and written by settings_page.py
            import settings_page
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            out = settings_page.act(rec)
            _record(rec, t0, {"id": "settings", "title": "Settings"}, "save_settings", out.get("result"),
                    not str(out.get("result") or "").startswith("Not saved"), False)
            return out
        if rec.get("id") == "voice-learn":  # Settings, Your voice: Learn my voice now (voice.py); never done by a pass
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            import voice
            said = voice.learn_now()
            _record(rec, t0, {"id": "voice-learn", "title": "Learn style now"}, "voice_learn", said, True, False)
            return {"ok": True, "items": [], "result": said, "thought": False, "secs": {"own": round(time.time() - t0, 3)}}
        if rec.get("id") == "start-fresh":  # Settings, Rule book: Start fresh (start_fresh.py), only with his yes to its question
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            import start_fresh
            said = start_fresh.from_press(rec)
            _record(rec, t0, {"id": "start-fresh", "title": "Start fresh"}, "start_fresh", said, not said.startswith("Not done"), False)
            return {"ok": True, "items": [], "result": said, "thought": False, "secs": {"own": round(time.time() - t0, 3)}}
        if rec.get("id") == "mail-reload":  # Settings, Tools: Reload all email history (mail.py); the passes do the reading
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            import mail
            said = mail.reload_history()
            _record(rec, t0, {"id": "mail-reload", "title": "Reload all email history"}, "mail_reload", said, True, False)
            return {"ok": True, "items": [], "result": said, "thought": False, "secs": {"own": round(time.time() - t0, 3)}}
        if rec.get("id") == "rebuild":      # Settings: rebuild every open card, or put them back (rebuild.py)
            import rebuild
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            out = rebuild.act(rec)
            _record(rec, t0, {"id": "rebuild", "title": "Rebuild all cards"}, "rebuild", out.get("result"), True, False)
            return out
        test = _as_it_stands(rec["id"]) if rec.get("id") and not str(rec["id"]).startswith(("ready", "mail", "change", "tool:", "pt:", "rm:", "rule-scan:")) else None
        import onboard
        if onboard.is_setup(test):  # a setup card: its own steps (onboard.py), never the card writer or Claude's reading of a card
            return onboard.handle(rec, on_update=on_update)
        if is_test(test):           # a made-up card: before Send, the lists and Claude, so nothing leaves it
            item, _ = _land(_test_record(test, rec))
            return {"ok": True, "items": [item] if item else [], "thought": False, "secs": {},
                    "result": ((item or {}).get("last_press") or {}).get("happened") or TEST_SAYS}
        import send
        if send.is_press(rec):      # an email the owner wrote and pressed Send on: the one thing that may go out
            out = _owner_send(rec)
            _record(rec, t0, None, "send", out.get("result"), bool(out.get("sent")), False)
            return out
        if str(rec.get("id") or "").startswith("ready-keep:"):      # a reply he started and left: kept in Ready to send
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            import ready
            return ready.keep(rec)
        if str(rec.get("id") or "").startswith("ready-all:"):       # Send all in Ready to send: one press, each email checked and sent once
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            import ready
            out = ready.send_all(rec)
            try:        # the one press, recorded with every draft it covered
                covered = [str(e.get("item")) for e in (json.loads(rec.get("text") or "{}").get("send_all") or {}).get("emails") or []]
            except (ValueError, AttributeError):
                covered = []
            _record(rec, t0, {"id": rec["id"], "title": "Send all"}, "send_all",
                    f"{out.get('result') or out.get('error')} Covered: {', '.join(covered) or 'none'}.", out.get("ok"), False)
            return out
        if str(rec.get("id") or "").startswith("mail-pull:"):       # Refresh in the Mail part: every mailbox read now (mailpull.py)
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            import mail
            said = mail.pull_now()
            _record(rec, t0, {"id": rec["id"], "title": "Refresh mail"}, "mail_pull", said, not said.startswith("Not started"), False)
            return {"ok": True, "items": [], "result": said, "thought": False, "secs": {"own": round(time.time() - t0, 3)}}
        if str(rec.get("id") or "").startswith("mail-unsub:"):      # Unsubscribe on an email in the Mail part (mail_handle.py)
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            import mail
            import mail_handle
            try:
                out = mail_handle.unsubscribe(rec)
            except mail.Busy:
                out = {"ok": True, "items": [], "result": "Not done: your mail is being updated this moment. Press it again in a minute."}
            _record(rec, t0, {"id": rec["id"], "title": "Email"}, "mail_unsub", out.get("result") or out.get("error"), out.get("ok"), False)
            return out
        if str(rec.get("id") or "").startswith("mail-card:"):      # Card on picked emails in the Mail part (mail_card.py): teaches nothing
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            import mail_card
            out = mail_card.make(rec)
            _record(rec, t0, {"id": rec["id"], "title": "Email"}, "mail_card", out.get("result") or out.get("error"), out.get("ok"), bool(out.get("thought")))
            return out
        if str(rec.get("id") or "").startswith("contact-note:"):   # Settings, Contacts: Save on a person's notes (contacts_book.py)
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            import contacts_book
            out = contacts_book.act(rec)
            _record(rec, t0, {"id": rec["id"], "title": "Contacts"}, "contact_note", out.get("result"),
                    not str(out.get("result") or "").startswith("Not saved"), False)
            return out
        if str(rec.get("id") or "").startswith("rule-book:"):      # Settings, Rule book: Keep, Edit or Retire (rule_book.py)
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            import rule_book
            out = rule_book.act(rec)
            _record(rec, t0, {"id": rec["id"], "title": "Rule book"}, "rule_book_review", out.get("result"),
                    not str(out.get("result") or "").startswith("Not done"), False)
            return out
        if str(rec.get("id") or "").startswith("mail-rule:"):      # Settings, Mail rules: a Save or Delete press (mail_rules.py)
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            import mail_rules
            out = mail_rules.act(rec)
            _record(rec, t0, {"id": rec["id"], "title": "Mail rules"}, "mail_rule", out.get("result"),
                    not str(out.get("result") or "").startswith("Not done"), False)
            return out
        if str(rec.get("id") or "").startswith(("mail:", "mail-draft:")):     # a press on an email in the Mail part
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            if str(rec["id"]).startswith("mail-draft:"):
                import ready
                out = ready.start_from_mail(rec)
                what = "mail_draft"
            else:
                import mail
                try:
                    out = mail.act(rec)
                except mail.Busy:
                    out = {"ok": True, "items": [], "result": "Not done: your mail is being updated this moment. Press it again in a minute."}
                what = "mail_act"
            _record(rec, t0, {"id": rec["id"], "title": "Email"}, what, out.get("result") or out.get("error"), out.get("ok"), False)
            return out
        if str(rec.get("id") or "").startswith("rule-scan:"):      # Undo on "Your rule was applied to N other cards" (card_rules.py)
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            n, said = card_rules.undo(str(rec["id"]).split(":", 1)[1])
            _record(rec, t0, {"id": rec["id"], "title": "Undo a rule's changes"}, "rule_scan_undo", said, bool(n), False)
            return {"ok": True, "items": [], "result": said, "thought": False, "secs": {"own": round(time.time() - t0, 3)}}
        if str(rec.get("id") or "").startswith("change-go:"):       # "Yes, make this change", pressed on the page: the go
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            out = _change_go(rec)
            _record(rec, t0, {"id": rec["id"], "title": "Make a change"}, "change_go", out.get("result") or out.get("error"), out.get("ok"), False)
            return out
        if str(rec.get("id") or "").startswith("change-drop:"):     # "Cancel this change", pressed on the page before its go
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            out = _change_drop(rec)
            _record(rec, t0, {"id": rec["id"], "title": "Cancel a change"}, "change_drop", out.get("result") or out.get("error"), out.get("ok"), False)
            return out
        if str(rec.get("id") or "").startswith("change-undo:rsi-"):     # Undo of a rule change Level 3 made on its own
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            out = _undo_learned(rec)
            _record(rec, t0, {"id": rec["id"], "title": "Undo a change made on its own"}, "undo_change", out.get("result") or out.get("error"), out.get("ok"), False)
            return out
        if str(rec.get("id") or "").startswith("change-undo:"):     # Undo of a change, pressed on the page (asked twice there)
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            out = _undo_change(rec)
            _record(rec, t0, {"id": rec["id"], "title": "Undo a change"}, "undo_change", out.get("result") or out.get("error"), out.get("ok"), False)
            return out
        if str(rec.get("id") or "").startswith("change:"):          # "Change how your assistant works": the words go to Talk to your assistant
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            import chat
            common.write_json(os.path.join(common.paths.STATE, "change_walk.json"), {"started": common.now().isoformat(timespec="seconds")})
            return chat.handle(f"(I pressed Change how your assistant works.) {(rec.get('text') or '').strip()}", rec.get("at"))
        if str(rec.get("id") or "").startswith("tool:"):    # Start on a tool in Settings, Tools: its walk-through starts in Talk to your assistant
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            return _tool_start(rec)
        if str(rec.get("id") or "").startswith("pt:"):      # a press on a project tool in Settings, Tools (project_tools.py)
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            import project_tools
            return dict(project_tools.handle(rec), items=[], thought=False, secs={})
        if str(rec.get("id") or "").startswith("rm:"):      # a press on a roadmap shown on the page: the listener's roadmap_press.py queues it
            if rec.get("action") != "answer":
                return {"ok": True, "items": [], "result": "", "thought": False, "secs": {}}
            hold = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "live_page")
            if hold not in sys.path:
                sys.path.insert(0, hold)
            import roadmap_press
            out = roadmap_press.handle(rec)
            return dict(out, items=[], thought=False, secs={})
        if not rec.get("id") or rec.get("action") not in ("answer", "done", "not_mine", "reopen", "note"):
            return {"ok": False, "error": "The answer names no item or an action I do not know.", "items": []}
        rec.setdefault("at", common.now().isoformat(timespec="seconds"))
        rec.setdefault("acted_at", common.now().isoformat(timespec="milliseconds"))
        same = (rec["id"], rec["action"], (rec.get("text") or "").strip())
        seen = _recent.get(same)
        if seen and time.time() - seen[0] <= DUPLICATE_SECONDS and rec["action"] != "reopen":
            return dict(seen[1], duplicate=True)
        if rec["id"] == presses.ALL_KEY:        # one press on several cards (Got it all, and its Undo)
            out = _press_all(rec, t0)
            _recent[same] = (time.time(), out)
            return out
        import held
        if held.KEY.match(str(rec["id"])):      # "I should have seen this" on a row of the Hidden list
            out = _held_press(rec, t0)
            _recent[same] = (time.time(), out)
            return out
        # Junk and Never junk write the owner's lists the same moment, before the card changes
        before = _as_it_stands(rec["id"])
        if before and rec["action"] == "answer" and "bad" not in (presses.chosen(rec) or {}):     # a bad choice is refused below
            import mods         # a mod's own card: its answer and its buttons are the mod's (mods.py)
            got = mods.answer(before, rec, on_update)
            if got is not None:
                said = str(got.get("said") or "")
                item, _ = _land(_set(before["id"], did=said or None, **(got.get("fields") or {})))
                made = [c for c in (items.card_for(i) for i in got.get("made") or []) if c]
                if made:
                    _patch_snapshot(made)
                out = {"ok": True, "items": [item] + made, "result": said, "thought": bool(got.get("claude")),
                       "secs": {"own": round(time.time() - t0, 3)}}
                _record(rec, t0, item, "mod", said, True, bool(got.get("claude")))
                _recent[same] = (time.time(), out)
                return out
        if before and isinstance(rec.get("calendar"), dict) and not rec.get("calendar_added"):
            rec["calendar_added"] = _calendar_add(rec["calendar"], before)      # Add to calendar adds it, by the Calendar part's own code
        press = presses.parse(before, rec) if before else None
        for k in [k for k in _recent if k[0] == rec["id"] and k != same]:
            _recent.pop(k, None)        # a different press on this card since: the same press again is a new press
        item, landed = _land(_lists_first(before, press, _junk_first(before, press, rec)))
        if item is None:
            return {"ok": False, "error": "That card is gone, so nothing was changed.", "items": []}
        more = []       # other cards this press changed or made (an old card answered, a rule proposed)
        if rec["action"] == "answer" and not press and str(item.get("source_key") or "").startswith(NOTE_PREFIX):
            import projects     # words on a project's note: a card asks whether to write them into the project; nothing is written yet
            asked = projects.after_answer(item, rec)
            if asked:
                c = items.card_for(asked)
                if c is not None:
                    more.append(c)
        kind = kind_of(item, rec) if rec["action"] == "answer" else "button"
        ok_press = bool((item.get("last_press") or {}).get("ok")) if press else False
        if press and ok_press and press["name"] == "old_card":
            more += _old_card(press, rec)
        if press and ok_press and press["name"] == "update_start":
            import updates
            updates.start(item, press.get("version"))
        if press and ok_press and press["name"] == "approve" and teach.is_card(item):
            said = teach.approve(before)
            rid = int(str(item["source_key"])[len(teach.PREFIX):])
            kept, scanned = _scan_after(next((r for r in filters.rules() if r["id"] == rid), None), item["id"], on_update, item)
            said = " ".join(x for x in (said, scanned) if x)
            extra = dict(item.get("extra") or {}) if isinstance(item.get("extra"), dict) else {}
            if kept:
                extra[card_rules.SCAN_KEY] = kept
            item, _ = _land(_set(item["id"], extra=extra or None,
                                 last_press=presses._mark("approve", _when(rec), said)))
        if teach.is_card(item) and kind == "typed":
            kind = "rule words"
        mark = item.get("last_press") if isinstance(item.get("last_press"), dict) else {}
        result = mark.get("happened") or (item.get("assistant_did") or "").split("\n")[-1]
        secs["own"] = round(time.time() - t0, 3)
        thought = False

        import settings_page
        if kind == "typed" and settings_page.at_limit():
            # the day's limit on thinking runs: the answer is saved (status Thinking) and read first tomorrow
            kind = "waits"
            result = "Your answer is saved. " + settings_page.LIMIT_SAYS + " It is read first thing tomorrow."
            item, _ = _land(_set(item["id"], last_press=presses._mark("words", _when(rec), result)))
        way = None
        if press and ok_press and press["name"] in ("not_needed", "always_show") and press.get("scope") == "kind":
            way = "show_less" if press["name"] == "not_needed" else "always_show"
        elif press and ok_press and press["name"] == "keep_showing" and presses.is_would_hide(item):
            pass            # Keep showing on an "I'd hide this" card: its rule book row is the whole of it, no rule is offered
        elif press and ok_press and press["name"] in presses.SWITCHES:
            if _switch_teaches(item) == "teach":
                way = "show_less" if presses.SWITCHES[press["name"]]["call"] == "hide" else "always_show"     # the same teach flow
            elif _switch_teaches(item) == "waiting":
                result = "Done. Nothing else changes. A rule change for this is already waiting on your page."
                item, _ = _land(_set(item["id"], last_press=presses._mark(press["name"], _when(rec), result, was=presses._was(before))))
        if way:
            # one small Claude run proposes one rule; it is a card, and nothing is in force until Approve
            switch = presses.SWITCHES.get(press["name"])
            label = presses.switch_label(before, press["name"]) if switch else None
            if settings_page.at_limit():
                result = "Recorded. " + settings_page.LIMIT_SAYS + " Press it again tomorrow, or write the rule yourself in Settings."
                item, _ = _land(_set(item["id"], last_press=presses._mark(press["name"], _when(rec), result)))
            else:
                if on_update:
                    try:
                        on_update([item])
                    except Exception:  # noqa: BLE001
                        pass
                made, result = teach.propose(before, way, press.get("words") or "", pressed=label)
                thought = True
                secs["think"] = round(time.time() - t0 - secs["own"], 2)
                if switch:      # the press itself did what it recorded; the rule card is its offer
                    result = "Done. " + result
                item, _ = _land(_set(item["id"], last_press=presses._mark(press["name"], _when(rec), result,
                                                                          ok=bool(switch) or made is not None, claude=True,
                                                                          was=presses._was(before) if switch else None)))
                if made:
                    more.append(made)
        if kind == "rule words":       # the owner's Change on a rule card: the proposed sentence is rewritten, still not in force
            if settings_page.at_limit():
                result = "Your words are kept. " + settings_page.LIMIT_SAYS
            else:
                _own_landed(item["id"])          # the rewrite writes this very card: his words land first, never at the same moment
                made, result = teach.rewrite(before, (rec.get("text") or "").strip())
                thought = True
                secs["think"] = round(time.time() - t0 - secs["own"], 2)
                if made:        # the card as rewritten is what the page holds from now: header and sentence together
                    item = made
                    _patch_snapshot([made])
            item, _ = _land(_set(item["id"], state="question", status="Rule proposed", answer=None, answered_at=None,     # his words are in its history already
                                 last_press=presses._mark("words", _when(rec), result, claude=thought)))
        if press and ok_press and press["name"] == "rule_offer" and press.get("do") != "cancel":
            item, result, thought = _rule_offer(before, item, press, rec, on_update)
            secs["think"] = round(time.time() - t0 - secs["own"], 2)
        elif press and ok_press and press["name"] == "rule_offer":      # Cancel on a rule or change he asked for in words
            asked = ((before or {}).get("extra") or {}).get(card_rules.OFFER_KEY) or {}
            if asked.get("made"):
                _asked_told(item, asked, "Cancelled", result)
        # a choice pressed on a card from someone's request is his decision on it: read like his words, so it is acted on
        chosen = kind == "button" and _decides_for_someone(before, rec, press) and not settings_page.at_limit()
        go_ahead = kind == "button" and ok_press and _go_ahead_acts(before, press) and not teach.is_card(item) \
            and not settings_page.at_limit()
        chosen = chosen or go_ahead
        if kind == "typed" or chosen:
            if on_update:
                try:
                    on_update([item])
                except Exception:  # noqa: BLE001  the listener's own trouble never loses an answer
                    pass
            words, n = rec.get("text") or "", _question_no(before or item, rec)
            asked = _open_asks(before or item)
            redo = _redo_of(before or item, rec)
            if chosen and not n and len(asked) == 1 and several(before or item):
                n = 1           # the last open question of several: the page sends no number for it
            one = bool(redo) or (several(before or item) and bool(chosen or n))
            # an answer to one question of several: the others stay asked whatever the reply decides (after_one_answer)
            others = asked if redo else [a for i, a in enumerate(asked, 1) if i != n] if one else []
            if redo:        # Change on an answered question: his new answer, with what the old one led to
                words = (f'I am changing my answer to the question "{redo["ask"]}" (I had answered "{redo.get("answer")}"; what '
                         f'was done for it: {redo.get("did") or "nothing yet"}). My new answer: {words}. Undo or redo what that '
                         "needs, for that question only; the card's other questions are still open.")
            elif chosen and n and several(before or item):      # the press names its own question; only his own words carry authority
                words = (f'My answer to the question "{asked[n - 1]}", pressed on the card: "{words}". Act on it for that '
                         "question only" + ("; the card's other questions are still open." if others else "."))
            elif go_ahead:  # Go ahead on the card's question: his yes to what it recommends, acted on now
                rq = str((before or item).get("recommended") or (before or item).get("rec_front") or "").strip()
                ask = asked[0] if asked else ""
                words = (f'My answer to the question "{ask}", pressed on the card: "Yes, go ahead"'
                         + (f' (you recommended: {rq})' if rq else "") + ". Act on it now.")
            elif chosen:    # the press and its question are in the card's history; only his own words carry authority
                words = f'My answer, pressed on the card (its history has the question): "{words}". Act on it.'
            elif n:         # Other on one question: his words are that question's answer
                words = f'My answer to question {n} ("{asked[n - 1]}"): {words}'
            # words that read as a standing rule are not acted on: the rule is proposed under the box, with four buttons
            got = card_rules.check(before or item, rec.get("text") or "") if card_rules.may_check(before or item) and not chosen else None
            if got:
                import chat
                result = card_rules.offer_said(got)
                was = presses._was(before) if before else None
                fields = card_rules.offer_fields(before or item, rec.get("text") or "", got, _when(rec), was=was)
                fields["last_press"] = presses._mark("words", _when(rec), result, claude=True, was=was)
                chat.note_exchange(rec.get("text") or "", result, before or item, rec.get("at"))
                follow = _set(item["id"], did=f"It reads like a rule to keep, so I offered it: \"{got['rule']}\"", **fields)
                secs["think"] = round(time.time() - t0 - secs["own"], 2)
            else:
                follow, result, timing = think_on(item, words, at=rec.get("at"),
                                                  pressed=("Yes" if go_ahead else (rec.get("text") or "")) if chosen else None)
                secs["think"] = round(timing["think"], 2)
                secs["think_api"] = round(timing["api"], 2)
                if follow:      # what the run decided, and that a run was made, stay on the card
                    follow["fields"]["last_press"] = presses._mark("words", _when(rec), result, claude=True,
                                                                   was=presses._was(before) if before else None)
                    if one or several(before or item):      # a card of several: its answered questions are kept on it
                        after_one_answer(follow, item, others, result, changed=redo, new=rec.get("text") or "", before=before)
                    close_if_free(follow, item)
                    if timing.get("rule_offer"):        # the answer gave or asked about a rule: the four buttons ask it
                        follow, result = _offer_after(before or item, follow, rec.get("text") or "", timing["rule_offer"], result, rec)
                else:
                    follow = _set(item["id"], last_press=presses._mark("words", _when(rec), result, ok=False, claude=True))
            thought = True
            item, landed2 = _land(follow)
            landed = landed and landed2
        common.log_line(os.path.join(common.LOGS, "answers.log"),
                        f"{rec['id']} {rec.get('page_action') or rec['action']} | pressed {rec.get('at')} |"
                        f" reached the engine {rec.get('acted_at')} | own {secs['own']}s"
                        f" think {secs['think']}s | returned {common.now().isoformat(timespec='milliseconds')}")
        if more:
            try:
                _patch_snapshot(more)
            except Exception as e:  # noqa: BLE001
                common.log_line(os.path.join(common.LOGS, "errors.log"), f"answers file patch: {type(e).__name__}: {e}")
        import dates
        result = dates.show(result) if isinstance(result, str) else result      # the line he reads says Today or a date, never a stored day mark
        out = {"ok": True, "items": [item] + more, "result": result, "thought": thought, "secs": secs}
        mark = item.get("last_press") if isinstance(item.get("last_press"), dict) else {}
        _record(rec, t0, item, (press or {}).get("name") or ("words" if kind in ("typed", "waits", "rule words") else None),
                result, mark.get("ok", True), thought, press, pick=_pick_before(before))
        for k in [k for k, v in _recent.items() if time.time() - v[0] > 60]:
            _recent.pop(k, None)
        _recent[same] = (time.time(), out)
        return out
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"act_on_answer: {type(e).__name__}: {e}")
        return {"ok": False, "error": f"Something went wrong acting on that answer ({type(e).__name__}); "
                                      "it's saved, and I'll act on it the next time I check for messages.", "items": []}


# The timing test item (source_key live:test-timing) always comes back to
# "question", so the same card can be answered again and again while timing.
_transform = transform


def transform(item, rec):  # noqa: F811
    test = item.get("source_key") in ("live:test-seen", "live:test-timing")
    press = None if rec.get("action") == "_set" or test else presses.parse(item, rec)
    if press is not None and press["name"] in ("rsi_promote", "rsi_apply", "rsi_reject") and not rec.get("rsi_decided"):
        press = dict(press, undecided=True)     # a rule change card's press that reached no listener: the coach never ran
    if press is not None:       # a button: acted on here and now, with what happened in plain words
        return presses.fields(item, press, _when(rec), lambda r: _transform(item, {**rec, "page_action": None, **r}))
    f = _transform(item, rec)
    if "title" in f and "short_header" not in f:        # a new title without its own header: the old header goes with the old title
        f["short_header"] = None
    if rec.get("action") != "_set" and not test:
        typed = f.get("status") == "Thinking"
        f["last_press"] = presses._mark("words" if typed else (rec.get("page_action") or rec.get("action") or "answer"),
                                        _when(rec), "Reading your words now." if typed
                                        else (f.get("assistant_did") or "").split("\n")[-1][:300], claude=typed,
                                        was=presses._was(item) if typed else None)
    if item.get("source_key") == "live:test-seen":
        # the owner's own round-trip check: the card says how long the click took to get here
        if rec.get("action") == "answer":
            try:
                took = (dt.datetime.fromisoformat(str(rec["acted_at"])) - _when(rec)).total_seconds()
                how = f"reached your computer and was acted on in {took:.1f} seconds"
            except (KeyError, ValueError, TypeError):
                how = "was picked up the next time I checked for messages, not right away"
            f = {"answer": (rec.get("text") or "").strip() or None, "answered_at": _when(rec),
                 "state": "handled", "status": "Seen",
                 "assistant_did": _add(item.get("assistant_did"),
                                       f"Seen. You pressed {(rec.get('text') or '').strip() or 'a button'}."
                                       f" Your click {how}.")}
        return f
    if item.get("source_key") == "live:test-timing":
        if "state" in f:
            f["state"] = "question"
        if rec.get("action") == "_set":     # the result of a typed answer: ready to be answered again
            f.update(answer=None, answered_at=None, status=None)
            f.pop("asks", None)
            f.pop("draft", None)
    return f
