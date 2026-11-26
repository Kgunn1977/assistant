r"""The 15-minute job: gather, think if anything is new, refresh the page, send notifications.

    python pass.py

This is the one entry point: the page's listener runs it every 15 minutes (live_page/listen.py, passes()), and checks run it by hand.
One pass at a time: if the last one is still working, this one logs that and
ends. Every pass writes one line to Live\logs\pass.log and rewrites
Live\items.json and Live\health.json.
"""
import datetime as dt
import json
import os
import sys
import time
import traceback

import common
import gather
import limits

AI_STEPS_KEPT = 20


def publish():
    """Tell the page to refresh, if the page is there. Never stops a pass. An update's or a restore's check runs with the
    listener stopped (ASSISTANT_PAGE_LATER): the update refreshes the page itself once the listener is back."""
    if not os.path.exists(common.PUBLISH) or os.environ.get("ASSISTANT_PAGE_LATER"):
        return None
    ok, tail = gather.run_script(common.PUBLISH, timeout=limits.PUBLISH, finishing=True)
    if ok:
        return None
    common.log_line(os.path.join(common.LOGS, "errors.log"), f"page refresh failed: {tail[:500]}")
    return "I couldn't update your page after checking for messages."


def _error_log(pass_id, problems, already=()):
    """Every problem this pass found is also one line in the error log: the time, the pass and the plain message. A problem
    already written there by its own step (the page refresh, a stop on an error) is not written twice."""
    for p in problems:
        if p in already or str(p).startswith("the check stopped on an error"):
            continue
        try:
            common.log_line(os.path.join(common.LOGS, "errors.log"), f"pass {pass_id}: {p}")
        except OSError:
            pass


def write_health(pass_rec, g, t, problems):
    import alert
    old = common.read_json(common.HEALTH_JSON, {})
    steps = (old.get("ai_steps") or []) + ([s for s in t["steps"] if s["tries"] or not s["ok"]] if t else [])
    last_mail = old.get("last_new_mail_at")
    if g and g["new_messages"]:
        last_mail = common.now().isoformat(timespec="seconds")
    # a failed AI step stays a problem until a later think pass succeeds; one that only ran out of the pass's time was
    # put off, not failed (recorded as failed before 0.1.4's change), so it is not carried
    carried = [] if t else [p for p in old.get("problems") or [] if p.startswith("AI step") and "the check was out of time" not in p]
    health = {      # a full pass ran, so any earlier "paused" mark is gone with the old record
        "written_at": common.now(),
        "last_pass": pass_rec,
        "last_new_mail_at": last_mail,
        "sources": g["sources"] if g else old.get("sources", {}),
        "ai_steps": steps[-AI_STEPS_KEPT:],
        "problems": problems + [p for p in carried if p not in problems],
        "alerts": {"enabled": alert.enabled(), "last_sent_at": alert.last_sent()},
    }
    common.write_json(common.HEALTH_JSON, health)


def _stopped_at_limit(pass_id):
    """What the watchdog does before it ends a pass that ran out its time."""
    def on_limit(step, used):
        said = (f"I stopped checking for messages at my {limits.HARD_LIMIT // 60} minute limit, while in step"
                f" '{step}'. What I didn't finish waits for the next time I check.")
        try:
            common.log_line(common.PASS_LOG, f"pass {pass_id} STOPPED AT ITS LIMIT {used:.0f}s | in step: {step}")
            old = common.read_json(common.HEALTH_JSON, {})
            old["written_at"] = common.now()
            old["last_pass"] = {"id": pass_id, "secs": round(used, 1), "outcome": "stopped at its limit",
                                "step": step}
            old["problems"] = [said] + [p for p in old.get("problems") or [] if "stopped at its" not in p and "minute limit" not in p]
            common.write_json(common.HEALTH_JSON, old)
            common.log_line(os.path.join(common.LOGS, "errors.log"), f"pass {pass_id}: {said}")
        finally:
            gather.drop_lock()
    return on_limit


def _stand_down(pass_id, t0, paused):
    """A pass that must not gather: the owner paused gathering, or chose a longer gap and it is not time yet.
    Nothing is gathered and nothing is thought about. Answers that reached the answers folder are still
    applied (no AI), and the page is refreshed only when one was."""
    import settings_page
    try:
        import items
        import presses
        applied = items.apply_answers(pass_id)[0]
        presses.flush()
        applied += presses.back_from_later(pass_id)     # a card put off comes back even while gathering rests
        if paused:
            old = common.read_json(common.HEALTH_JSON, {}) or {}
            old["written_at"] = common.now()
            old["paused"] = {"since": settings_page.paused_since()}
            common.write_json(common.HEALTH_JSON, old)
        snap = common.read_json(common.ITEMS_JSON, {}) or {}
        new_day = str(snap.get("written_at") or "")[:10] != dt.date.today().isoformat()     # today became yesterday
        if applied or new_day:
            items.export(pass_id)
            publish()
        common.log_line(common.PASS_LOG, f"pass {pass_id} " + ("paused: gathering is paused in Settings" if paused else
                        f"not due: gathering is every {settings_page.every_minutes()} minutes")
                        + f" {time.time() - t0:.0f}s" + (f" | {applied} answer(s) applied" if applied else ""))
    finally:
        gather.drop_lock()
    return 0


def main():
    t0 = time.time()
    limits.raise_priority()
    pass_id = "live-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    try:            # a Python-level fatal error (not only an exception) leaves its stack in the logs, never nothing
        import faulthandler
        faulthandler.enable(file=open(os.path.join(common.LOGS, "crash.log"), "a", encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    if not gather.take_lock(pass_id):
        common.log_line(common.PASS_LOG, f"pass {pass_id} skipped: the check before it is still running")
        return 3
    try:        # the owner's Settings: gathering paused, or a longer gap between gatherings (settings_page.py)
        import settings_page
        if settings_page.paused_flag() or not settings_page.gather_due():      # a pass run by hand while the scheduled one is off still runs
            return _stand_down(pass_id, t0, settings_page.paused_flag())
        settings_page.gathered_now()
    except Exception as e:  # noqa: BLE001  a setting that cannot be read never stops a pass
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"{pass_id} settings check: {type(e).__name__}: {e}")
    limits.begin(pass_id)
    limits.watchdog(_stopped_at_limit(pass_id))
    g = t = None
    problems, parts, outcome = [], [], "ok"
    already = []                    # problems the error log has already got from their own step
    try:        # an owner's taught rule the guardrails would not take is said, so it is never silently ignored
        problems += common.rulebook().book()[2]
    except Exception as e:  # noqa: BLE001
        problems.append(f"the guardrails could not be read: {type(e).__name__}: {e}"[:200])
    open_items = 0
    try:
        import alert
        import items
        import think

        import offpage
        cal_before = offpage.calendar_before()          # his calendar before the gather: what changes is what he did there
        g = gather.gather(pass_id)
        problems += g["problems"]
        parts.append(gather.summary(g))
        n_off = offpage.record(pass_id, g["new_messages"], cal_before)      # sent messages and calendar answers, as rule book rows
        if n_off:
            parts.append(f"{n_off} thing(s) you did outside the page recorded")
        try:        # the setup cards (onboard.py): connect cards tick off, the catalog's progress card, the noticed cards
            import onboard
            said = onboard.pass_step(pass_id)
            if said:
                parts.append(said)
        except Exception as e:  # noqa: BLE001
            problems.append(f"the setup cards could not be brought up to date: {type(e).__name__}: {e}"[:200])
        if g["new_messages"] and limits.enough(limits.LOOKBACK + 240):
            try:    # each new sender or topic looked up in the history catalog, before the judge sees it (lookback.py)
                import lookback
                limits.step("look-back")
                said = lookback.run(pass_id, g["new_messages"], time.time() + limits.cap(limits.LOOKBACK))
                if said:
                    parts.append(said)
            except Exception as e:  # noqa: BLE001
                problems.append(f"the look-back step failed: {type(e).__name__}: {e}"[:200])
        try:        # the texts link's connection: it runs with the page; a pass only reads what it last said
            import textlink
            problems += textlink.pass_check()
        except Exception as e:  # noqa: BLE001
            problems.append(f"the texts link's connection could not be checked: {type(e).__name__}: {e}"[:200])

        limits.step("answers")
        applied, bad = items.apply_answers(pass_id)
        problems += bad
        import answers
        read, bad = answers.think_pending(pass_id)
        problems += bad
        if read:
            parts.append(f"{read} typed answer(s) read")
        import setup_steps
        setup_steps.desktop_note()                          # the folder's note for a Claude session there, current after an update
        import ready
        moved, bad = ready.adopt_card_drafts(pass_id)      # a draft left on a card goes to Ready to send
        problems += bad
        if moved:
            parts.append(f"{moved} card draft(s) moved to Drafts")
        import chat
        ran, bad = chat.run_queue()                         # what the chat said it would do, done now and said in the chat
        problems += bad
        if ran:
            parts.append(f"{ran} promised job(s) done")
        made, changed, closed = items.sync_from_tasks(pass_id)

        limits.step("thinking")
        why = think.needed(g)
        import settings_page
        if why and settings_page.at_limit():
            # the owner's daily limit on thinking runs: what is new waits, unjudged, for the first pass after midnight
            parts.append("think: waiting, today's limit on AI runs is reached")
        elif why and not limits.enough(240):
            # put off, not an error: what is new stays unjudged and the next pass thinks (the pass log says so)
            parts.append(f"think: put off to the next check, the gather took {g['secs']:.0f}s")
        elif why:
            t = think.think(pass_id, rest=think.resting(g))     # only a step that failed rests; the others run
            for s in t["steps"]:            # a step put off for time is in the pass log (think.summary), never an error
                if not s["ok"]:
                    problems.append(f"AI step '{s['step']}' failed: {s['why']}")
            made, changed, closed = made + t["made"], changed + t["changed"], closed + t["closed"]
            parts.append(think.summary(t))
        else:
            parts.append("think: not needed, 0 AI calls")

        limits.step("people")
        try:        # the people lookup file, then no question for a contact detail that is on file (after the mail is saved)
            import people
            try:
                people.write_people()
            except Exception as e:  # noqa: BLE001
                common.log_line(os.path.join(common.LOGS, "errors.log"), f"known people not written: {type(e).__name__}: {e}")
            n_settled = people.settle_open(pass_id)
            if n_settled:
                parts.append(f"{n_settled} contact question(s) settled from what is on file")
        except Exception as e:  # noqa: BLE001
            problems.append(f"the contact lookup's pass step failed: {type(e).__name__}: {e}"[:200])
        limits.step("cards")
        items.close_retired(pass_id)
        import presses
        presses.flush()                             # any press that waited for the database is in its table now
        back = presses.back_from_later(pass_id)     # cards put off whose time has come are on the page again
        if back:
            parts.append(f"{back} card(s) back from snooze")
        try:        # round 2, all on dates and lists, no Claude: hidden safety net, first-time senders, cards that come back
            import comeback
            import held
            import newsender
            import dates
            nd = dates.fix_once(pass_id)        # once: old relative day words on open cards become dates
            if nd:
                parts.append(f"{nd} card(s) had day words turned into dates")
            import headers
            n0 = headers.batch(pass_id)         # once: old cards whose only header was a cut title get a whole one
            if n0:
                parts.append(f"{n0} header(s) written whole in one run")
            n1, n2 = held.net(pass_id), newsender.cards(pass_id)
            n3, n4 = comeback.waiting(pass_id), comeback.old(pass_id)
            import review
            import standing
            import projects
            n8 = projects.read_notes(pass_id)
            if n8:
                parts.append(f"{n8} project note(s) made into cards")
            n5, n6, n7 = standing.offers(pass_id), standing.apply(pass_id), review.make(pass_id)
            import levels
            n9, n10 = levels.act(pass_id), levels.summary(pass_id)
            standing.write_feed()
            if n9:
                parts.append(f"{n9} thing(s) done on my own at learning levels 2 and 3")
            if n10:
                parts.append("morning summary of level 3 made")
            if n5:
                parts.append(f"{n5} standing-approval offer(s) made")
            if n6:
                parts.append(f"{n6} thing(s) done for you by standing approval")
            if n7:
                parts.append("weekly review made")
            if n1 or n2:
                parts.append(f"{n1 + n2} plain card(s) made")
            if n3:
                parts.append(f"{n3} waiting card(s) back")
            if n4:
                parts.append(f"{n4} old card(s) asked about")
        except Exception as e:  # noqa: BLE001
            problems.append(f"the come-back step failed: {type(e).__name__}: {e}"[:200])
        try:        # the owner's mods: each one's own step, time allowing (mods.py)
            import mods
            said, bad = mods.pass_steps(pass_id, limits.enough)
            parts += said
            problems += [b[:200] for b in bad]
        except Exception as e:  # noqa: BLE001
            problems.append(f"the mods step failed: {type(e).__name__}: {e}"[:200])
        try:
            import updates
            said = updates.check(pass_id)
            if said:
                parts.append(said)
        except Exception as e:  # noqa: BLE001
            problems.append(f"the weekly look for a newer version failed: {type(e).__name__}: {e}"[:200])
        try:        # a change still being talked through from before changes became cards: its card (card_rules.py)
            import card_rules
            said = card_rules.talking_to_cards()
            if said:
                parts.append(said)
        except Exception as e:  # noqa: BLE001
            problems.append(f"moving waiting changes onto cards failed: {type(e).__name__}: {e}"[:200])
        open_items = items.export(pass_id)
        try:
            held_today = held.write()
            parts.append(f"hidden today: {held_today}")
        except Exception as e:  # noqa: BLE001
            problems.append(f"the Hidden list could not be written: {type(e).__name__}: {e}"[:200])
        parts.append(f"items: {open_items} open (+{len(made)} new, {len(changed)} changed,"
                     f" {len(closed)} closed" + (f", {applied} answer(s) applied" if applied else "") + ")")

        limits.step("alerts")
        sent, skipped, bad = alert.alert_important(pass_id)
        problems += bad
        parts.append(f"notifications: {sent} sent" + (f", {skipped} skipped (no topic set)" if skipped else ""))
        try:        # new mail that matters: after the mail is stored and the item alerts, never slowing the pull
            import mail_alerts
            m_sent, _m_skipped, m_bad = mail_alerts.run(pass_id)
            problems += m_bad
            if m_sent:
                parts.append("mail notification sent")
        except Exception as e:  # noqa: BLE001
            problems.append(f"the mail notification step failed: {type(e).__name__}: {e}"[:200])
        limits.step("upkeep")
        try:        # how often the owner is in touch with each person: after the mail is saved and the cards are written,
            import contact_strength     # time allowing (else the next pass); never in an update's quick check
            if limits.enough(120) and not os.environ.get("ASSISTANT_QUICK_PASS"):
                t1 = time.time()
                contact_strength.refresh()
                parts.append(f"contacts recounted in {time.time() - t1:.0f}s")
        except Exception as e:  # noqa: BLE001
            problems.append(f"contact strength not recounted: {type(e).__name__}: {e}"[:200])
    except Exception as e:  # noqa: BLE001
        outcome = "failed"
        problems.append(f"the check stopped on an error: {type(e).__name__}: {e}"[:300])
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"{pass_id}\n{traceback.format_exc()}")
    finally:
        try:
            if problems and outcome == "ok":
                outcome = "problems"
            rec = {"id": pass_id, "started": dt.datetime.fromtimestamp(t0).isoformat(timespec="seconds"),
                   "secs": round(time.time() - t0, 1), "new_messages": len(g["new_messages"]) if g else 0,
                   "ai_calls": t["ai_calls"] if t else 0, "open_items": open_items, "outcome": outcome}
            write_health(rec, g, t, problems)
            page_problem = publish()
            if page_problem:
                already.append(page_problem)         # publish() wrote it to the error log itself
                problems.append(page_problem)
                rec["secs"] = round(time.time() - t0, 1)
                write_health(rec, g, t, problems)
            # the refresh also brings the owner's answers back; record them now so the
            # engine is current, and the page shows them on its next refresh
            try:
                import items as _items
                if _items.apply_answers(pass_id)[0]:
                    _items.export(pass_id)
                    parts.append("answers applied after the page refresh")
            except Exception as e:  # noqa: BLE001
                problems.append(f"answers could not be applied: {e}"[:200])
            _error_log(pass_id, problems, already)      # every problem is also in the error log, once
            common.log_line(common.PASS_LOG,
                            f"pass {pass_id} {outcome} {time.time() - t0:.0f}s | " + " | ".join(parts)
                            + (" | PROBLEMS: " + "; ".join(p[:160] for p in problems) if problems else ""))
        finally:
            gather.drop_lock()
    return 0 if outcome != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
