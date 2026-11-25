r"""Kinds of work: how well my picks match what the owner does, and the pick rules that change them (the judgment rebuild,
phases 4 and 5: "The checker and coach across every kind of work").

Program code only. A kind of work is one of the rule book's sections (rule_book.SECTIONS). Each rule book row with a pick
(phase 1: picks.py, offpage.py) is scored in four ways, each only where it says something:

    decisions   did he do what I picked (picks.outcome)
    wording     where both my pick and what he did carry words (a choice, a reply's gist, his typed words): the same words,
                or most of them (WORDING_SHARE of the words shared)
    timing      where my pick or what he did puts it off (Snooze, Someday, Keep waiting): both put it off, or neither did
    urgency     on a card I marked important: he acted on it rather than putting it off, dropping it or not needing it

A pick rule (personal\work_rules.json, the coach's one change, made only by Promote or, at level 3, coach.self_promote) says:
for cards in one kind of work that match (sender, words in the title, area, kind), my pick is this one, and/or such a card is
not urgent. picks.of applies the pick part on every card; the urgency part reaches the card writer as a line of its rules
(filters.lines_for_writing). compare() tries a draft of the rules on the rule book's past rows exactly, with no AI run:
fixes N, breaks M, both scores.

    rules(section=None)              the rules in force
    match(rule, card)                True when a live card matches the rule
    pick_for(card, section)          the pick a rule sets for this card, or None
    writer_lines()                   the urgency rules as lines for the card writer
    score(rows, rules)               {aspect: [matched, counted]} and the per-row result
    compare(rows, live, draft)       fixes / breaks / both scores over the same rows
    check(change, live)              (the change, checked, None) or (None, why refused)
    apply(live, change, new_id)      the rules with the one change made (nothing written)
    save(rows)                       write the rules (Promote, Undo)
    words(change, live)              the one change in plain words
"""
import json
import os
import re
import threading

import common

STORE = os.path.join(common.PERSONAL, "work_rules.json")
ASPECTS = ("decisions", "wording", "timing", "urgency")
ASPECT_WORDS = {"decisions": "decisions", "wording": "wording", "timing": "timing", "urgency": "urgency"}
PUT_OFF = ("later", "someday", "wait_longer")
NOT_NOW = PUT_OFF + ("drop", "not_needed")
WORDING_SHARE = 0.5
MATCH_KEYS = ("sender", "words", "area", "kind")
MATCH_MIN, MATCH_MAX = 2, 80
RULES_MOST = 60
_lock = threading.Lock()


def _norm(s):
    return " ".join(str(s or "").split()).lower()


# --- the store -----------------------------------------------------------------------------------------------------------
def _file():
    got = common.read_json(STORE, {}) or {}
    return got if isinstance(got, dict) else {}


def rules(section=None, only_on=True):
    out = [r for r in _file().get("rules") or [] if isinstance(r, dict) and isinstance(r.get("match"), dict)
           and r.get("section") and (r.get("pick") or r.get("urgent") is False)]
    return [r for r in out if (not only_on or r.get("on", True)) and (section is None or r.get("section") == section)]


def save(rows):
    """Write the rules (Promote, Undo). Program code only."""
    with _lock:
        got = _file()
        got["rules"] = [dict(r) for r in rows]
        got["next"] = max([int(got.get("next") or 1)] + [int(r["id"]) + 1 for r in rows if isinstance(r.get("id"), int)])
        common.write_json(STORE, got)


def next_id():
    got = _file()
    return max([int(got.get("next") or 1)] + [int(r["id"]) + 1 for r in rules(only_on=False) if isinstance(r.get("id"), int)])


# --- matching ------------------------------------------------------------------------------------------------------------
def _fits(m, sender, words, area, kind):
    if not m:
        return False
    if m.get("sender") and _norm(m["sender"]) not in _norm(sender):
        return False
    if m.get("words") and _norm(m["words"]) not in _norm(words):
        return False
    if m.get("area") and _norm(m["area"]) != _norm(area):
        return False
    if m.get("kind") and _norm(m["kind"]) != _norm(kind):
        return False
    return True


def _card_sender(it):
    ex = it.get("extra") if isinstance(it.get("extra"), dict) else {}
    who = it.get("sender") if isinstance(it.get("sender"), dict) else ex.get("sender") if isinstance(ex.get("sender"), dict) else {}
    return " ".join(str(x or "") for x in (it.get("source_who"), who.get("name"), who.get("key"), who.get("address")))


def match(rule, it):
    it = it or {}
    return _fits(rule.get("match") or {}, _card_sender(it), " ".join(str(it.get(k) or "") for k in ("title", "short_header")),
                 it.get("area"), it.get("kind"))


def _row_fits(rule, row):
    seen = row.get("seen") or {}
    return row.get("section") == rule.get("section") and _fits(rule.get("match") or {}, seen.get("sender"), seen.get("what"),
                                                               row.get("card_area"), row.get("card_kind"))


def pick_for(it, section=None):
    """The pick the newest rule in force sets for this live card, or None."""
    import rule_book
    sec = section or rule_book.section(it)
    for r in sorted(rules(sec), key=lambda r: int(r.get("id") or 0), reverse=True):
        if r.get("pick") and match(r, it):
            return dict(r["pick"], by="rule", rule=r.get("id"))
    return None


def _match_words(m):
    parts = []
    if m.get("sender"):
        parts.append(f"from {m['sender']}")
    if m.get("words"):
        parts.append(f"with \"{m['words']}\" in the title")
    if m.get("area"):
        parts.append(f"in {m['area']}")
    if m.get("kind"):
        parts.append(f"of kind {m['kind']}")
    return " ".join(parts)


def writer_lines():
    """The urgency rules in force, as lines for the card writer (filters.lines_for_writing): never mark such a card important."""
    return [f"- assistant rule W{r['id']}: a card {_match_words(r['match'])} is not urgent: do not mark it important."
            + (f" Because: {r['reason']}" if r.get("reason") else "") for r in rules() if r.get("urgent") is False]


# --- scoring -------------------------------------------------------------------------------------------------------------
def _put_off(x):
    return bool(x) and x.get("do") == "press" and x.get("press") in PUT_OFF


def _not_now(did):
    return (did.get("do") == "press" and did.get("press") in NOT_NOW) or did.get("do") == "none"


def _words_of(x):
    x = x or {}
    return _norm(x.get("text") if x.get("do") == "choice" else x.get("gist") if x.get("do") == "reply"
                 else x.get("words") if x.get("do") == "words" else "")


def _same_words(a, b):
    if a == b:
        return True
    wa, wb = set(re.findall(r"[a-z0-9']+", a)), set(re.findall(r"[a-z0-9']+", b))
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= WORDING_SHARE


def aspects(row, pick=None, important=None):
    """{aspect: matched} for one row: with its recorded pick and importance, or with the pick and importance a draft gives
    it. Only the aspects this row says something about."""
    import picks
    did = row.get("did") if isinstance(row.get("did"), dict) else None
    recorded = row.get("pick") if isinstance(row.get("pick"), dict) else None
    p = pick if pick is not None else recorded
    if not did or not p:
        return {}
    as_recorded = pick is None or pick is recorded
    oc = row.get("pick_outcome") if as_recorded else picks.outcome(p, did)
    out = {}
    if oc in ("matched", "differed"):
        out["decisions"] = oc == "matched"
    if oc is not None:
        a, b = _words_of(p), _words_of(did)
        if a and as_recorded and oc == "matched" and not b:
            out["wording"] = True           # he pressed my pick itself: its words were his
        elif a and b:
            out["wording"] = _same_words(a, b)
        if _put_off(p) or _put_off(did):
            out["timing"] = _put_off(p) == _put_off(did)
    imp = row.get("card_important") if important is None else important
    if row.get("card_important") is True and oc is not None:
        acted = not _not_now(did)
        out["urgency"] = acted if imp else not acted
    return out


def _draft_view(row, draft):
    """(pick, importance) a draft of the rules gives one row: the newest matching rule's pick and urgency, else the row's own."""
    pick, imp = None, None
    for r in sorted(draft, key=lambda r: int(r.get("id") or 0), reverse=True):
        if not r.get("on", True) or not _row_fits(r, row):
            continue
        if pick is None and r.get("pick"):
            pick = {k: v for k, v in r["pick"].items() if k in ("do", "press", "text", "gist")}
        if imp is None and r.get("urgent") is False:
            imp = False
    return pick, imp


def score(rows, draft=None):
    """({aspect: [matched, counted]}, {row id: {aspect: matched}}) over the rows; with draft rules, as the draft would make them.
    A rule in force when the row was written already shaped its recorded pick, so the live rules give the rows as recorded."""
    per, total = {}, {a: [0, 0] for a in ASPECTS}
    for r in rows:
        if draft is None:
            got = aspects(r)
        else:
            pick, imp = _draft_view(r, draft)
            got = aspects(r, pick, imp)
        if got:
            per[r.get("id") or r.get("message")] = got
        for a, ok in got.items():
            total[a][0] += int(ok)
            total[a][1] += 1
    return total, per


def _line(m, n):
    return f"{m} of {n} matched"


def compare(rows, live, draft):
    """fixes / breaks between the rows as the live rules leave them (as recorded) and as the draft makes them, over every
    aspect of every row both sides score (each (row, aspect) once)."""
    _t, a = score(rows)
    _t2, b = score(rows, draft)
    keys = sorted({(k, x) for k, v in a.items() for x in v} & {(k, x) for k, v in b.items() for x in v}, key=str)
    fixed = [k for k in keys if not a[k[0]][k[1]] and b[k[0]][k[1]]]
    broken = [k for k in keys if a[k[0]][k[1]] and not b[k[0]][k[1]]]
    lm, dm = sum(a[k[0]][k[1]] for k in keys), sum(b[k[0]][k[1]] for k in keys)
    return {"fixes": len(fixed), "breaks": len(broken), "fixed": [f"{m} {x}" for m, x in fixed],
            "broken": [f"{m} {x}" for m, x in broken], "compared": len(keys), "score_live": _line(lm, len(keys)),
            "score_draft": _line(dm, len(keys)), "complete": True, "incomplete_why": [],
            "line": f"fixes {len(fixed)} of your past answers, breaks {len(broken)}"}


# --- the one change ------------------------------------------------------------------------------------------------------
def _check_pick(p):
    import picks
    if not isinstance(p, dict) or p.get("do") not in ("press", "reply", "none"):
        return None, "a pick is a press, a reply or leaving it"
    if p["do"] == "press":
        if p.get("press") not in picks.PRESSES or p["press"] == "approve":
            return None, f"a pick's press is one of: {', '.join(x for x in picks.PRESSES if x != 'approve')}"
        return {"do": "press", "press": p["press"]}, None
    if p["do"] == "reply":
        g = " ".join(str(p.get("gist") or "").split())
        if not 3 <= len(g) <= picks.GIST_MAX:
            return None, f"a reply's gist is 3 to {picks.GIST_MAX} characters"
        return {"do": "reply", "gist": g}, None
    return {"do": "none"}, None


def check(change, live, section):
    """(the change checked, None) or (None, why refused). add: match, and a pick and/or urgent false; remove: one of the rules
    in force for the section."""
    import coach
    c = change if isinstance(change, dict) else {}
    reason = c.get("reason")
    if not isinstance(reason, str) or "\n" in reason.strip() or not coach.REASON_MIN <= len(reason.strip()) <= coach.REASON_MAX:
        return None, f"the reason is one line of {coach.REASON_MIN} to {coach.REASON_MAX} characters"
    out = {"change": c.get("change"), "reason": " ".join(reason.split())}
    if c.get("change") == "remove":
        if set(c) - {"change", "rule", "reason"}:
            return None, "a remove holds exactly: change, rule, reason"
        rid = c.get("rule")
        if isinstance(rid, bool) or rid not in {r["id"] for r in live if r.get("section") == section}:
            return None, "the rule to remove is not one of the pick rules for this kind of work"
        out["rule"] = rid
        return out, None
    if c.get("change") != "add":
        return None, "the change is add or remove"
    if set(c) - {"change", "match", "pick", "urgent", "reason"}:
        return None, "an add holds only: change, match, pick, urgent, reason"
    m = c.get("match")
    if not isinstance(m, dict) or not m or set(m) - set(MATCH_KEYS):
        return None, f"match names one or more of: {', '.join(MATCH_KEYS)}"
    clean = {}
    for k, v in m.items():
        v = " ".join(str(v or "").split()) if isinstance(v, str) else None
        if not v or not MATCH_MIN <= len(v) <= MATCH_MAX:
            return None, f"each match is words of {MATCH_MIN} to {MATCH_MAX} characters"
        clean[k] = v
    out["match"] = clean
    if "pick" in c:
        p, why = _check_pick(c["pick"])
        if why:
            return None, why
        out["pick"] = p
    if "urgent" in c:
        if c["urgent"] is not False:
            return None, "urgent may only be false (I may stop marking cards important, never start)"
        out["urgent"] = False
    if "pick" not in out and "urgent" not in out:
        return None, "an add sets a pick, urgent false, or both"
    if any(r.get("section") == section and r.get("match") == clean and r.get("pick") == out.get("pick")
           and (r.get("urgent") is False) == ("urgent" in out) for r in live):
        return None, "that rule is already in force"
    if len(live) >= RULES_MOST:
        return None, f"there are already {RULES_MOST} pick rules"
    return out, None


def apply(live, change, section, new_id=None):
    if change["change"] == "remove":
        return [dict(r) for r in live if r["id"] != change["rule"]]
    rule = {"id": new_id or next_id(), "section": section, "match": change["match"], "on": True,
            "made": common.now().isoformat(timespec="seconds"), "from": "coach", "reason": change["reason"]}
    if change.get("pick"):
        rule["pick"] = change["pick"]
    if change.get("urgent") is False:
        rule["urgent"] = False
    return [dict(r) for r in live] + [rule]


def _pick_words(p):
    import picks
    return picks.label(p) if p else ""


def words(change, live=()):
    c = change or {}
    if c.get("change") == "remove":
        old = next((r for r in live if r.get("id") == c.get("rule")), None)
        return f"Stop the pick rule for cards {_match_words((old or {}).get('match') or {})}" if old else f"Stop pick rule {c.get('rule')}"
    said = []
    if c.get("pick"):
        said.append(f"my pick is \"{_pick_words(c['pick'])}\"")
    if c.get("urgent") is False:
        said.append("I stop marking them important")
    return f"For cards {_match_words(c.get('match') or {})}: " + " and ".join(said)


def same(a, b):
    keys = ("change", "rule", "match", "pick", "urgent")
    return {k: (a or {}).get(k) for k in keys} == {k: (b or {}).get(k) for k in keys}


if __name__ == "__main__":
    print(json.dumps(rules(), indent=1))
