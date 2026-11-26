r"""The Card press in the Email part: older mail the owner picks becomes a card at once, by the same judging and card writing
as gathered mail (think.py), never waiting for the next check. New mail already becomes cards on its own; nothing old is
worked unless he picks it.

    make(rec)       one press {"mail_card": {"messages": [id, ...], "all": true}} on key mail-card:<ms>

Each picked email stands for its conversation (as the Email part's rows do). An email already on a card (an open one, or a
finished one still on the page) makes no new card: the result names that card, and the page opens it. The rest are judged
first when they carry no verdict yet, then placed by the card writer in one run, grouped by topic as gathered mail is: several
emails on one matter make one card, and one that belongs to an open card goes onto it. The writer may not pass a picked
email over. A Card press teaches like every other press (the judgment learns from everything he does): each card it made or
added to gets a rule book row per email behind it, meaning he needed it, so a call that kept it off the page counts as a
miss and the learning loop takes it up. No rule is written.
"""
import datetime as dt
import json

import common

MOST_PICKED = 15        # emails worked per press: one writing run's worth (think.LOOSE_BATCH)
PER_CONVERSATION = 6    # a conversation's newest emails a press puts on its card


def _conversation(mid):
    import mail
    return mail._conversation(mid, "card")[:PER_CONVERSATION]


def _on_cards(ids):
    """{message id: card id} for the picked emails already on a card that is open, or finished and still on the page."""
    import items
    import settings_page
    cutoff = common.now() - dt.timedelta(days=settings_page.done_days())
    want, out = {str(i) for i in ids}, {}
    for r in sorted(items.rows("state <> 'done' OR done_at >= ?", (cutoff,)), key=lambda r: r["state"] == "done"):
        if str(r.get("source_key") or "").startswith(items.RETIRED_PREFIXES):
            continue
        for m in want & set(r["source_messages"] or []):
            out.setdefault(m, r["id"])
    return out


def _unjudged(ids):
    import db
    marks = ",".join("?" for _ in ids)
    done = {r[0] for r in db.query(f"SELECT key FROM answered WHERE domain='judged' AND key IN ({marks})",
                                   tuple(f"msg:{i}" for i in ids))}
    return [i for i in ids if f"msg:{i}" not in done]


def _cards_for(ids):
    """The cards the emails are on now, newest change first."""
    import items
    want = {str(i) for i in ids}
    got = [r for r in items.rows("state <> 'done'") if want & set(r["source_messages"] or [])]
    return [r["id"] for r in sorted(got, key=lambda r: str(r.get("updated_at") or ""), reverse=True)]


def _result(words, card_ids):
    import answers
    import items
    shown = [c for c in (items.card_for(i, wait=True) for i in card_ids) if c is not None]
    if shown:
        answers._patch_snapshot(shown)
    return {"ok": True, "items": shown, "result": words, "thought": bool(card_ids)}


def _teach(card_ids, picked):
    """The press's rule book rows: one per email behind each card it made or added to, "needed" (rule_book.on_press). Never
    raises."""
    try:
        import items
        import rule_book
        want = {str(i) for i in picked}
        for cid in card_ids:
            it = items.card_for(cid, wait=True)
            if it and want & {str(m) for m in it.get("source_messages") or []}:
                rule_book.on_press(it, "mail_card", "needed", button="Card")
    except Exception as e:  # noqa: BLE001  the cards are made; a row that cannot be written is logged
        common.log_line(common.PASS_LOG, f"Card press rule book rows not written: {type(e).__name__}: {e}")


def make(rec):
    try:
        got = json.loads(rec.get("text") or "")["mail_card"]
        picked = [int(i) for i in got["messages"]][:MOST_PICKED]
    except (ValueError, KeyError, TypeError):
        return {"ok": False, "error": "That press could not be read. Nothing was made.", "items": []}
    if not picked:
        return {"ok": False, "error": "That press could not be read. Nothing was made.", "items": []}
    import gather
    import items
    import limits
    import think
    pass_id = "card-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    if not gather.take_lock(pass_id):
        return {"ok": True, "items": [], "result": "Not done: I'm checking your messages right now. Press Card again in a minute."}
    try:
        convs = [_conversation(m) if got.get("all") else [m] for m in picked]
        everything = sorted({i for c in convs for i in c})
        on = _on_cards(everything)
        had = list(dict.fromkeys(on[str(i)] for c in convs for i in c if str(i) in on))
        fresh = sorted({i for c in convs if not any(str(i) in on for i in c) for i in c}, reverse=True)
        if not fresh:
            return _result(("That email is already on a card." if len(picked) == 1 else "Those emails are already on a card.")
                           if len(had) == 1 else f"Those emails are already on {len(had)} cards.", had)
        limits.begin(pass_id)
        think._current["pass"] = pass_id
        if _unjudged(fresh):                    # never judged yet: the same judging as gathered mail, first
            ok, said = think.judge()
            if not ok and _unjudged(fresh):
                return {"ok": True, "items": [], "result": "Not done: I couldn't read those emails just now. Press Card again in a minute."}
        before = {r["id"] for r in items.rows("state <> 'done'")}
        with open(common.paths.GOALS, encoding="utf-8") as f:
            goals = f.read()
        ok, why = think._write_batch([], fresh, {str(i) for i in fresh}, goals, picked=set(fresh))
        if not ok:
            common.log_line(common.PASS_LOG, f"{pass_id}: Card press on {len(fresh)} email(s) not done: {why}")
            return {"ok": True, "items": [], "result": "Not done: I couldn't write the card just now. Press Card again in a minute."}
        made = _cards_for(fresh)
        common.log_line(common.PASS_LOG, f"{pass_id}: Card press on {len(fresh)} email(s): card(s) {', '.join(made) or 'none'}")
        _teach(made, fresh)
        items.export(pass_id)
        new, old = [c for c in made if c not in before], [c for c in made if c in before]
        one = len(fresh) == 1
        words = " ".join(x for x in (
            ("I made a card from that email." if one else "I made a card from those emails." if len(new) == 1
             else f"I made {len(new)} cards from those emails, one for each topic.") if new else "",
            ("I added it to a card you already have." if one else "I added some to a card you already have." if new
             else "I added them to a card you already have.") if old else "") if x) or "Not done: no card came of it."
        return _result(words, list(dict.fromkeys(made + had)))
    finally:
        gather.drop_lock()
