r"""The "I'd hide this" card: a judge's "noise" verdict that neither the owner's own rules nor his settings cover is shown,
not hidden (the RSI plan, "Nothing hidden at the start"; guardrail A13 as amended).

Program code only, no Claude (guardrail A4). After the judge has run in a pass, each message it judged noise in that pass
gets one short card, "I'd hide this: <who>: <what>", with two buttons decided by card.switches:
  - Hide things like this (press hide_like_this): the card closes and a hide rule is offered through the teach flow, as
    "Hide mailings like this" does (a rule card; nothing is in force until Approve);
  - Keep showing (press keep_showing): the card closes; its rule book row asks for the show the judge did not make.
Each press writes its rule book row like any other press. The message's verdict stays noise, so the row's call is hide.

A noise verdict stays hidden as before, with no card, when the owner's own written rules or his Settings choices cover it:
  - his rule: the judge's reason starts "owner rule <n>:" (filters.lines_for_sorting asks for that), or its leaned_on names
    "owner rule <n>" for a rule of his that is on. A bare number never counts: core and owner rule numbers overlap;
  - his Settings choice: the reason or leaned_on names "setting <name>" (filters.lines_for_sorting tags each setting line
    and asks for that) for a filter setting whose value in force holds things back (SETTING_HIDES); or it leaned on rule
    559 while his setting hides mailings, or rule 560 while it hides short-number texts; or the filter is set to only what
    needs him, under which everything else is noise by his own choice.
Only the judge's own verdicts make cards: a setting, a junk rule, a list, the first sort, an add-on and anything settled
before this pass never do. A replay day (ASSISTANT_REPLAY) makes none.

    is_card(item)                       True for an "I'd hide this" card
    covered(source, leaned_on)          True when his own rules or his Settings choices cover a verdict
    cards(message_ids, pass_id)         the cards for the messages judged this pass; returns how many were made
"""
import json
import os
import re

import card
import common

PREFIX = "live:wouldhide-"
TITLE = "I'd hide this"
HEADER_MOST = 90                # guardrail A3: a header is whole, on one line, 90 characters or less
OWNER_RULE = re.compile(r"\bowner rule (\d+)\b", re.I)
SETTING = re.compile(r"\bsetting ([a-z_]+)\b", re.I)
JUNK_RULE = re.compile(r"(?<![\w.])(?:rule\s*)?(559|560)(?![\w.])", re.I)
# A filter setting (filters.CHOICES) covers a noise verdict only at a value that holds things back; at one that shows, never.
SETTING_HIDES = {"strict": ("balanced", "needs_me"), "kept_mailings": ("only_due_or_wrong",), "notices": ("only_failed",),
                 "newsletters": ("never",), "short_texts": ("hide",), "first_time": ("hold",), "copied_only": ("only_if_named",),
                 "unknown_texts": ("hide",), "nothing_needed": ("hide",)}
NOT_JUDGE = ("rule:", "setting:", "owner:", "mod:", "fast:", "filed:", "readback:", "history reload", "judged_by_v1")


def is_card(item):
    return str((item or {}).get("source_key") or "").startswith(PREFIX)


def _judge_made(source):
    """True when the verdict's source is the judge's own words (not a program layer's mark or the first sort's)."""
    s = str(source or "").strip().lower()
    return bool(s) and not s.startswith(NOT_JUDGE) and not OWNER_RULE.match(s)


def _replaying():
    return os.environ.get("ASSISTANT_REPLAY") == "1"


def setting_covers(source, leaned_on, settings=None):
    """True when one of the owner's Settings choices decided a noise verdict: a setting named by its tag ("setting <name>")
    at a value that holds things back; rule 559 or 560 leaned on while his setting keeps that rule on; or the filter set to
    only what needs him, under which everything else is noise by his own choice."""
    import filters
    f = filters.get() if settings is None else settings
    if f.get("strict") == "needs_me":
        return True
    said = f"{source or ''} {leaned_on or ''}"
    if any(f.get(m.group(1).lower()) in SETTING_HIDES.get(m.group(1).lower(), ()) for m in SETTING.finditer(said)):
        return True
    return any((m.group(1) == "559" and f.get("newsletters") == "never") or (m.group(1) == "560" and f.get("short_texts") == "hide")
               for m in JUNK_RULE.finditer(str(leaned_on or "")))


def covered(source, leaned_on, rules=None, settings=None):
    """True when the owner's own written rules or his Settings choices decided the verdict: one of his rules (switched on)
    named at the start of the reason or by "owner rule <n>" in what the judge leaned on, or a Settings choice of his
    (setting_covers)."""
    import filters
    on = {r["id"] for r in (filters.rules(only_on=True) if rules is None else rules)}
    named = [OWNER_RULE.match(str(source or "").strip())] + list(OWNER_RULE.finditer(str(leaned_on or "")))
    return any(m and int(m.group(1)) in on for m in named) or setting_covers(source, leaned_on, settings)


def _why(reason, uncovered):
    """The card's why line. When the judge said no rule covers it, the card's own "My rules don't cover this" line already
    gives its guess (card.fill), so the reason is not said twice."""
    if uncovered:
        return "I would have hidden it, and none of your own rules or settings says to."
    said = " ".join(str(reason or "").split()).rstrip(".")
    return (f"I would have hidden it: {said[:1].lower() + said[1:]}. None of your own rules or settings says to." if said
            else "I would have hidden it, and none of your own rules or settings says to.")


def cards(message_ids, pass_id):
    """One "I'd hide this" card per message judged noise by the judge among message_ids (those judged this pass), when no
    rule or Settings choice of his covers it and the message has no card of this kind yet. Returns how many were made. A
    replay day makes none."""
    if _replaying():
        return 0
    ids = sorted({int(m) for m in message_ids or [] if str(m).lstrip("-").isdigit()})
    if not ids:
        return 0
    import db
    import filters
    import items
    items.ensure()
    cols = {str(r[0]) for r in db.query("SELECT column_name FROM information_schema.columns WHERE table_name = 'answered'")}
    mark = "a.covered, a.leaned_on" if {"covered", "leaned_on"} <= cols else "NULL, NULL"
    rows = db.query(
        f"""SELECT m.id, m.channel, m.ts, m.from_key, m.subject, m.body, a.source, {mark},
                   (SELECT max(c.name) FROM contacts c WHERE c.person_id = m.person_id AND c.name IS NOT NULL)
            FROM messages m JOIN answered a ON a.domain = 'judged' AND a.key = 'msg:' || m.id
            WHERE m.id IN ({','.join('?' for _ in ids)}) AND m.direction = 'in' AND a.verdict = 'noise'
              AND coalesce(m.from_key, '') <> 'assistant' ORDER BY m.id""", tuple(ids))
    rules, settings = filters.rules(only_on=True), filters.get()
    made = 0
    for mid, channel, ts, fk, subject, body, source, was_covered, leaned, name in rows:
        if not _judge_made(source) or covered(source, leaned, rules, settings):
            continue
        key = PREFIX + str(mid)
        if db.query("SELECT 1 FROM live_items WHERE source_key = ?", (key,)):
            continue            # one card per message, ever
        who = " ".join(str(name or "").split()) or str(fk or "").split(":", 1)[-1] or "Someone"
        what = " ".join(str(subject or "").split()) or " ".join(" ".join(str(body or "").split()).split(" ")[:12]) or "a message"
        title = card.whole(f"{TITLE}: {who}: {what}")
        head = title if len(title) <= HEADER_MOST else title[:HEADER_MOST].rsplit(" ", 1)[0].rstrip(" ,:;-")
        items.upsert(key, pass_id, kind="fyi", area="Personal", state="handled", title=title[:300], short_header=head,
                     detail=None, asks=[], source_who=who, source_when=ts, source_messages=json.dumps([str(mid)]),
                     why=_why(source, was_covered is False))
        made += 1
    return made
