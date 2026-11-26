r"""The RSI loop: a miss queues a job; the listener's own worker runs it; Level 2 puts a rule change card in front of the
owner (the RSI plan, "Running and cost", "The four parts" 4, "Cards and buttons").

- Queued at press time, by program code only: when a press writes a rule book row whose signal contradicts the assistant's
  call (grader.signal), one job for that row's section goes into state\rsi\queue.json. Never Claude: a press only writes.
  No job is queued for a section that already has one waiting, or while its rule change card is open.
- Run by the listener after the press is handled, in a worker of its own (never the chat's one-job-at-a-time queue), one
  section at a time, until the queue is empty or the RSI daily cap is reached (then the jobs wait for the next run).
  Level 1 (the default): the job does nothing more; teaching on cards is the Level 1 flow. Level 2: coach.coach(section),
  shown on a card; it is never promoted on its own.
  Level 3 (guardrail A15 as amended, only in a section the owner set to Level 3): rounds of grade, coach and grade-draft
  (coach.coach), each draft promoted on its own only by coach.self_promote (it scores higher than his live rules and breaks
  no answer they matched) and recorded in Change history with Undo; any other draft is closed as rejected with why. It stops
  when every answer matches, after ROUNDS rounds, or at the RSI daily cap (the job then waits). A setting or list change
  is never made on its own: it gets its Promote card as at Level 2.
- A proposal that is fully scored (a rule change) or names its one setting or list exactly (a setting change) becomes a rule
  change card, written here (guardrail A4): the one change and its reason, "Fixes N of your past corrections, breaks M"
  and both scores, with Promote and Reject (a setting or list change is made by rsi_apply under the same Promote). Scores outside Settings are
  shown only on these cards. Any other proposal is set aside as "not shown", with why, so it never holds the section.
- The card's presses (rsi_promote, rsi_apply, rsi_reject; presses.NAMES) call coach.promote, coach.apply_setting or
  coach.reject before the card closes (answers._lists_first, decide()).

    on_rows(rows)                    queue a job for each section a written row contradicts in; never raises
    run(runner=None, ask=None)       the listener's worker: every queued job it may run; returns the cards made
    open_card(section)               the section's open rule change card's proposal, or None (files only)
    decide(item, press)              (ok, said, close) for one press on a rule change card
    is_card(item)                    True for a rule change card: no scan, rebuild, join or pass step changes it
"""
import glob
import json
import os
import threading

import common

STORE = os.path.join(common.paths.STATE, "rsi")
QUEUE = os.path.join(STORE, "queue.json")
LOG = os.path.join(STORE, "loop.log")
PREFIX = "live:rsi-"                 # a rule change card's source key: PREFIX + the proposal's id
PRESSES = ("rsi_promote", "rsi_apply", "rsi_reject")
REJECTED_BY_YOU = "Rejected by you"
TRIES = 3                            # a job that trips this many times (the database held throughout) is dropped
NOT_SHOWN = "not shown"
ROUNDS = 10                          # Level 3: at most this many grade, coach and grade-draft rounds for one job
_lock = threading.Lock()


def _replaying():
    return os.environ.get("ASSISTANT_REPLAY") == "1"


def _log(text):
    common.log_line(LOG, text)


def _now():
    return common.now().isoformat(timespec="seconds")


def is_card(item):
    """True for a rule change card (or a setting card): only its own Promote or Reject changes or closes it."""
    return str((item or {}).get("source_key") or "").startswith(PREFIX)


# --- the queue ---------------------------------------------------------------------------------------------------------
def _jobs():
    got = common.read_json(QUEUE, []) or []
    return [j for j in got if isinstance(j, dict) and j.get("section")] if isinstance(got, list) else []


def jobs():
    """The jobs waiting, oldest first."""
    with _lock:
        return _jobs()


def queue(section, messages=(), kind="rules"):
    """One job for the section and kind ("rules": show or hide; "work": my picks), unless one waits already or the section's
    rule change card is open. True when queued."""
    if _replaying():
        return False
    with _lock:
        got = _jobs()
        if any(j["section"] == section and j.get("kind", "rules") == kind for j in got) or open_card(section):
            return False
        got.append({"section": section, "kind": kind, "at": _now(), "messages": [str(m) for m in messages][:25], "tries": 0})
        common.write_json(QUEUE, got)
    _log(f"queued {section} ({kind}): " + ("a press contradicted the call on " if kind == "rules" else "my pick missed on ")
         + (", ".join(str(m) for m in messages) or "a message"))
    return True


def on_rows(rows):
    """The rule book's rows just written: a job for each section where one contradicts the call it records. Never raises,
    so a press is never held up by it."""
    try:
        if _replaying():
            return 0
        import grader
        import work_rules
        by, work = {}, {}
        for r in rows or []:
            if isinstance(r, dict) and not r.get("pending") and r.get("status", "active") == "active" \
                    and grader.signal(r)[0] == "contradicts":
                by.setdefault(r.get("section") or "page", []).append(r.get("message"))
        for r in rows or []:           # my pick missed what he did, in some way: the coach for that kind of work
            if isinstance(r, dict) and not r.get("pending") and r.get("status", "active") == "active" and not all(work_rules.aspects(r).values()):
                work.setdefault(r.get("section") or "page", []).append(r.get("message"))
        return sum(queue(s, m) for s, m in by.items()) + sum(queue(s, m, "work") for s, m in work.items())
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"rsi queue: {type(e).__name__}: {e}")
        return 0


def _done(job):
    with _lock:
        common.write_json(QUEUE, [j for j in _jobs() if not (j["section"] == job["section"] and j["at"] == job["at"])])


def _tried(job):
    with _lock:
        got = _jobs()
        for j in got:
            if j["section"] == job["section"] and j["at"] == job["at"]:
                j["tries"] = int(j.get("tries") or 0) + 1
        common.write_json(QUEUE, got)


# --- proposals and their cards -----------------------------------------------------------------------------------------
def _proposals(section=None):
    import coach
    out = []
    for path in glob.glob(os.path.join(coach.PROPOSALS, "*.json")):
        got = common.read_json(path, None)
        if isinstance(got, dict) and (section is None or got.get("section") == section):
            out.append(dict(got, file=path))
    return sorted(out, key=lambda p: str(p.get("at")))


def _card_closed(card_id):
    """True when the page's own copy of the cards shows that card done (closed some other way than its buttons)."""
    snap = common.read_json(common.ITEMS_JSON, {}) or {}
    it = next((i for i in snap.get("items") or [] if isinstance(i, dict) and i.get("id") == card_id), None)
    return bool(it and it.get("state") == "done")


def open_card(section):
    """The section's proposal whose rule change card is open (or still to be made), else None. Files only."""
    for p in _proposals(section):
        if p.get("status") == "open" and (p.get("card_pending") or (p.get("card") and not _card_closed(p["card"]))):
            return p
    return None


def _set_aside(p, why):
    """A proposal that gets no card: kept, marked so it never holds the section."""
    got = common.read_json(p["file"], {}) or {}
    got.update(status=NOT_SHOWN, decided_at=_now(), not_shown_why=why)
    common.write_json(p["file"], got)
    _log(f"{p.get('section')}: proposal {p.get('id')} not shown: {why}")


def _change_words(p):
    """The one change, in plain words, from the checked change itself (never the coach's own wording of it)."""
    import coach
    import filters
    c = p.get("change") or {}
    if p.get("kind") == "work":
        import work_rules
        return work_rules.words(c, p.get("rules_before") or []) + "."
    if p.get("kind") == "setting":
        s = c.get("set")
        return coach.set_words(s)[:1].upper() + coach.set_words(s)[1:] + "."
    rules = {r.get("id"): r for r in p.get("rules_before") or []}
    old = (rules.get(c.get("rule")) or {}).get("text")
    way = filters.WAY_WORDS.get(c.get("way"), c.get("way"))
    if c.get("change") == "add":
        return f"Add a rule ({way}): \"{c.get('text')}\""
    if c.get("change") == "edit":
        return f"Change the rule \"{old}\" to ({way}): \"{c.get('text')}\""
    return f"Remove the rule \"{old}\""


def _score_words(line):
    """"3 of 5 matched" as "3 of 5"."""
    return str(line or "").replace(" matched", "")


def card_fields(p):
    """The rule change card's columns, all worked out here from the proposal (guardrail A4)."""
    import rule_book
    sec = rule_book.SECTION_WORDS.get(p.get("section"), p.get("section"))
    change = _change_words(p)
    lines = [f"The change: {change}", f"Why: {p.get('reason')}"]
    c = p.get("change") or {}
    old = next((r for r in p.get("rules_before") or [] if r.get("id") == c.get("rule")), None)
    if p.get("kind") == "rule" and c.get("change") in ("edit", "remove") and old and old.get("reason"):
        lines.insert(1, f"That rule's reason now: {old['reason']}")       # an edit's Why becomes the rule's new reason
    if p.get("kind") == "work":
        lines += [f"My picks get {p.get('fixes')} more of your past answers right and {p.get('breaks')} wrong.",
                  f"My picks get {_score_words(p.get('score_live'))} of your past answers right now. With this change: "
                  f"{_score_words(p.get('score_draft'))}."]
        ask, act = "Promote this change to my picks?", "Promote"
    elif p.get("kind") == "rule":
        lines += [f"It gets {p.get('fixes')} more of your past answers right and {p.get('breaks')} wrong.",
                  f"I get {_score_words(p.get('score_live'))} of your past answers right now. With this change: "
                  f"{_score_words(p.get('score_draft'))}."]
        ask, act = "Promote this rule change?", "Promote"
    else:
        live = common.read_json(p.get("live_grade") or "", {}) or {}
        now = ((live.get("sections") or {}).get(p.get("section")) or {}).get("line")
        lines += [f"I get {_score_words(now) or 'an unknown share'} of your past answers right now. I can't try a setting "
                  "on your past answers before you apply it, so there's no score with this change yet."]
        ask, act = "Promote this setting change?", "Promote"
    lines.append(f"Nothing changes until you press {act}. Reject leaves everything as it is, and I keep anything you "
                 "type in the box first as your reason.")
    title = {"rule": "Rule change: ", "work": "Pick change: "}.get(p.get("kind"), "Setting change: ") + change.rstrip(".")
    return {"kind": "question", "area": "System", "state": "question", "status": None, "title": title,
            "detail": "\n".join(lines), "asks": [ask],
            "why": (f"Some of my picks in {sec.lower()} didn't match what you did." if p.get("kind") == "work"
                    else f"Some of your corrections in {sec.lower()} didn't match what I did."),
            "extra": {"rsi": {"id": p["id"], "kind": p.get("kind"), "section": p.get("section"), "lines": lines,
                              "act": act, "fixes": p.get("fixes"), "breaks": p.get("breaks"),
                              "score_live": p.get("score_live"), "score_draft": p.get("score_draft")}}}


def _make_card(p, made):
    """The proposal's card, made now; when the database is held it is made on the next run (card_pending)."""
    import answers
    import items
    got = common.read_json(p["file"], {}) or {}
    try:
        iid, _how = items.upsert(PREFIX + p["id"], "rsi", **card_fields(p))
    except Exception as e:  # noqa: BLE001  the database held past its wait: the card waits, the section stays held
        got["card_pending"] = True
        common.write_json(p["file"], got)
        _log(f"{p.get('section')}: card for {p.get('id')} waits ({type(e).__name__})")
        return None
    got.pop("card_pending", None)
    got["card"] = iid
    common.write_json(p["file"], got)
    card = items.card_for(iid, wait=True)
    if card:
        answers._patch_snapshot([card])
        made.append(card)
    _log(f"{p.get('section')}: rule change card {iid} for proposal {p.get('id')}")
    return iid


def _show(p, made):
    """A proposal just coached: its card, or set aside with why."""
    import coach
    if p.get("kind") == "rule" and not p.get("complete"):
        return _set_aside(p, "not fully scored: " + "; ".join(p.get("incomplete_why") or []))
    if p.get("kind") == "setting" and coach.check_set((p.get("change") or {}).get("set"))[1]:
        return _set_aside(p, "the setting or list change was said in words only, so Promote could not make it")
    return _make_card(p, made)


# --- the runner --------------------------------------------------------------------------------------------------------
def _job(job, runner, ask, made):
    """One job: "done" (taken off the queue) or "again" (left first in the queue for the next run)."""
    import coach
    import grader
    import settings_page
    sec = job["section"]
    level = settings_page.learning_levels().get(sec, settings_page.LEARN_DEFAULT)
    if level == 3:
        return _improve(job, runner, ask, made)
    if level != 2:
        _log(f"{sec}: level 1: no change proposed; he teaches on the cards")
        return "done"
    if open_card(sec):
        _log(f"{sec}: a rule change card is already open")
        return "done"
    got = _coach(job, runner, ask)
    if isinstance(got, str):
        _log(f"{sec}: {got}")
        return "again" if grader.CAP_REACHED in got else "done"
    if got.get("kind") == "rule" and not got.get("complete") and grader.CAP_REACHED in " ".join(got.get("incomplete_why") or []):
        _set_aside(dict(got), "the RSI daily cap was reached while it was scored")
        return "again"
    _show(dict(got), made)
    return "done"


def _coach(job, runner, ask):
    """The coach for the job's kind: show or hide (coach.coach) or my picks (coach.coach_work)."""
    import coach
    if job.get("kind") == "work":
        return coach.coach_work(job["section"], ask=ask)
    return coach.coach(job["section"], runner=runner, ask=ask)


def _rounds(job, n):
    """The Level 3 rounds a waiting job has used, kept on it in the queue."""
    with _lock:
        got = _jobs()
        for j in got:
            if j["section"] == job["section"] and j["at"] == job["at"]:
                j["rounds"] = n
        common.write_json(QUEUE, got)


def _improve(job, runner, ask, made):
    """Level 3: "done" or "again", like _job. Every round runs the coach (which grades his live rules when no grade of them
    is current, writes one draft and grades it) and counts, whatever it gave. The rounds a job has used are kept on it, so a
    job the RSI daily cap stopped goes on from there the next day and never runs more than ROUNDS in all."""
    import coach
    import grader
    sec = job["section"]
    if open_card(sec):
        _log(f"{sec}: level 3: a setting change card is already open")
        return "done"
    for n in range(int(job.get("rounds") or 0) + 1, ROUNDS + 1):
        if grader.at_cap():
            _log(f"{sec}: level 3 round {n}: {grader.CAP_REACHED}; the job waits")
            _rounds(job, n - 1)
            return "again"
        got = _coach(job, runner, ask)
        if isinstance(got, str):
            _log(f"{sec}: level 3 round {n}: {got}")
            if got == coach.NOTHING:
                return "done"                   # every answer matches
            if grader.CAP_REACHED in got:
                _rounds(job, n - 1)
                return "again"
            continue                            # refused or failed: nothing was saved; the round counts
        p = dict(got)
        if p.get("kind") == "setting":          # never made on its own: its Promote card, as at Level 2
            _show(p, made)
            _log(f"{sec}: level 3 round {n}: a setting change waits for Promote")
            return "done"
        if not p.get("complete") and grader.CAP_REACHED in " ".join(p.get("incomplete_why") or []):
            _set_aside(p, "the RSI daily cap was reached while it was scored")
            _rounds(job, n)
            return "again"
        try:
            ok, said = coach.self_promote(p)
        except ValueError as e:                 # his rules changed while it was scored: closed with why; the round counts
            _set_aside(p, f"not made on its own: {e}")
            ok, said = False, str(e)
        if not ok:
            _log(f"{sec}: level 3 round {n}: proposal {p.get('id')} not made: {said}")
            continue
        _log(f"{sec}: level 3 round {n}: proposal {p.get('id')} made on its own ({p.get('score_live')} to "
             f"{p.get('score_draft')}); in Change history with Undo")
        dm = coach.matched(p.get("score_draft"))
        if dm is not None and dm == int(p.get("compared") or -1):
            _log(f"{sec}: level 3: every answer matches")
            return "done"
    _log(f"{sec}: level 3 stopped after {ROUNDS} rounds")
    return "done"


def run(runner=None, ask=None):
    """Every job the RSI daily cap allows, oldest first, one section at a time: the listener's own worker calls it after a
    press is handled. runner and ask stand in for the grader's and the coach's Claude runs (tests). Returns the cards made,
    as the page carries them. Never raises."""
    import grader
    made = []
    if _replaying():
        return made
    try:
        for p in _proposals():
            if p.get("status") == "open" and p.get("card_pending"):
                _make_card(p, made)                     # coached earlier while the database was held
        while True:
            got = jobs()
            if not got:
                break
            job = got[0]
            if grader.at_cap():
                _log(f"RSI daily cap reached: {len(got)} job(s) wait for tomorrow")
                break
            try:
                how = _job(job, runner, ask, made)
            except Exception as e:  # noqa: BLE001  a held database: tried again on the next run, then dropped
                _tried(job)
                _log(f"{job['section']}: tripped ({type(e).__name__}: {str(e)[:200]})")
                how = "again" if int(job.get("tries") or 0) + 1 < TRIES else "done"
            if how == "again":
                break
            _done(job)
    except Exception as e:  # noqa: BLE001
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"rsi run: {type(e).__name__}: {e}")
    return made


# --- the card's presses ------------------------------------------------------------------------------------------------
def reason_of(press):
    """Reject's reason: the owner's typed words, one line of the length coach.reject takes, else "Rejected by you"."""
    import coach
    words = " ".join(str((press or {}).get("words") or "").split())[:coach.REASON_MAX]
    return words if len(words) >= coach.REASON_MIN else REJECTED_BY_YOU


def _plain(why):
    """The coach's refusal as the owner reads it on the card."""
    if "changed since" in why:
        return "your rules changed since this was suggested. A new suggestion comes with your next correction."
    if "already" in why and "proposal" in why:
        return "this change was already decided."
    if "not fully scored" in why:
        return "it could not be checked against all of your past answers."
    return why.rstrip(".") + "."


def decide(item, press):
    """(ok, said, close) for one Promote, Apply or Reject on a rule change card, done now through the coach. A refusal that
    can never clear (already decided, his rules changed since, not fully scored) closes the card with that line and sets
    the proposal aside, so the section is never held by it. Never raises."""
    import coach
    pid = (((item or {}).get("extra") or {}).get("rsi") or {}).get("id")
    name = (press or {}).get("name")
    try:
        if name == "rsi_promote":
            coach.promote(pid)
            return True, "", False
        if name == "rsi_apply":
            coach.apply_setting(pid)
            return True, "", False
        coach.reject(pid, reason_of(press))
        return True, "", False
    except ValueError as e:
        try:
            got, path = coach._load(pid)
            if got.get("status") == "open":
                got.update(status=NOT_SHOWN, decided_at=_now(), not_shown_why=f"closed on {name}: {e}")
                common.write_json(path, got)
        except (ValueError, OSError):
            pass
        return False, "Nothing was changed: " + _plain(str(e)), True
    except Exception as e:  # noqa: BLE001  something on this computer: the card stays as it is, to press again
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"rsi press: {type(e).__name__}: {e}")
        return False, f"Nothing was changed: something went wrong on your computer ({type(e).__name__}). Press it again.", False


if __name__ == "__main__":
    print(json.dumps({"queue": jobs(), "made": [c.get("id") for c in run()]}, indent=1, default=str))
