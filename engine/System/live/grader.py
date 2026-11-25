r"""The grader: how many of the owner's corrections the show-or-hide layers get right (the RSI plan, "The four parts" 2).

Read-only. It reads the rule book (rule_book.rows), marks each active row agrees / contradicts / neutral from its press's
meaning against the call the assistant made, and grades only the rows with a real signal:

- a row the judge or the first sort decided (layer judge, first_sort, or rule: the judge following one of his own rules) is
  decided again in a dry run: what that layer would see now for those messages (judgment_payload.build by message ids,
  think.first_sort_input), the layer's own instructions and model, one Claude run per batch, his live rules or a draft
  rules file given in their place. The verdicts are read here and never committed: nothing goes to the answered table,
  the cards, the Hidden lists or any live store;
- a row a program layer decided (a setting, rules 559/560, the junk list, the ignore list) is not run again: it is graded
  from the call it made, and names the setting or list that decided.

Each graded row keeps the judge's coverage mark as recorded (covered_was, leaned_on_was: from the rule book row, None when
not said) and, for a judge rerun, as the rerun gave it (covered, leaned_on). They are kept, never scored.

What it writes is its own, under <home>\state\rsi\: the result (grades\<time>.json), the score history (scores.jsonl, one
line per section per grade) and the RSI runs it started today (runs.json, apart from his daily limit's count). A replay
day (ASSISTANT_REPLAY) grades nothing.

    grade(section=None, rules_file=None, runner=None)   the result: "X of N matched" per section, each miss beside what he did
    signal(row)                                         ("agrees" | "contradicts" | "neutral", the call his press asks for)
    ask_text(prompt, model, runner=None)                one tool-less RSI run (the coach's), under the same cap
"""
import json
import os
import re
import sys
import uuid

import common
import db
import rule_book

if common.paths.CORE not in sys.path:
    sys.path.insert(0, common.paths.CORE)
import judgment_payload as jp  # noqa: E402

STORE = os.path.join(common.paths.STATE, "rsi")
GRADES = os.path.join(STORE, "grades")
WORK = os.path.join(STORE, "work")              # the dry runs' payloads and verdicts, and the open tasks' records
SCORES = os.path.join(STORE, "scores.jsonl")
RUNS = os.path.join(STORE, "runs.json")
RERUN = {"judge": "judge", "rule": "judge", "first_sort": "first_sort"}     # the layer run again for a row's layer
PROGRAM = ("setting", "junk_list", "ignore_list")
# the call a press's meaning asks for; every other meaning says nothing about show or hide
WANTS = {"contradicts-hide": "show", "needed": "show", "contradicts-show": "hide", "not-needed": "hide"}
OWN_RULES = "{owner}'s own rules, in their words."     # how filters.lines_for_sorting heads his rules
RUN_SECONDS = 300               # each grader run's own time guard (a pass's Claude run gets the same); never the pass clock
DAILY_CAP = 30                  # RSI runs a day, unless settings "rsi": {"daily_runs": n}
CAP_REACHED = "I've done my learning runs for today. The rest wait until tomorrow."
BATCH_MESSAGES, BATCH_CHARS = jp.ROUND_MESSAGES, jp.ROUND_CHARS     # a judge batch: the judge's own round caps
FIRST_CHARS = jp.ROUND_CHARS    # a first sort batch's characters


def _replaying():
    return os.environ.get("ASSISTANT_REPLAY") == "1"


# --- signals -----------------------------------------------------------------------------------------------------------
def signal(row):
    """(mark, wanted call) for one rule book row: agrees when his press asks for the call made, contradicts when it asks
    for the other one, neutral (wanted None) when it says nothing about show or hide or no call is known. A switchable button
    (presses.SWITCHES: Hide mailings like this, Keep showing these) asks for the call it names, whatever its meaning word, so
    its "agrees" counts; any other agrees or disagrees (an Approve, a choice) says nothing about show or hide."""
    import presses
    named = (presses.SWITCHES.get(row.get("press")) or {}).get("call")
    call, wants = row.get("call"), named or WANTS.get(row.get("meaning"))
    if call not in ("show", "hide") or wants is None:
        return "neutral", None
    return ("agrees" if wants == call else "contradicts"), wants


# --- the rules given ---------------------------------------------------------------------------------------------------
def _draft_rules(path):
    """His rules as a draft file gives them (the shape of personal\filter_rules.json, or a bare list), checked the way
    filters.rules checks his live ones."""
    import filters
    got = common.read_json(path, None)
    if got is None:
        raise ValueError(f"the draft rules file could not be read: {path}")
    got = got.get("rules") if isinstance(got, dict) else got
    out = [r for r in got or [] if isinstance(r, dict) and r.get("text") and r.get("way") in filters.WAYS]
    return [r for r in out if r.get("on", True)]


def owner_filter(rules_file=None):
    """The owner's lines the layers are told: his live settings and rules, or his live settings with the draft's rules in
    place of his live ones. Nothing live is changed to say it."""
    import filters
    import think
    lines = filters.lines_for_sorting()
    if not rules_file:
        return think._owner_filter(lines)
    draft = _draft_rules(rules_file)
    head = OWN_RULES.format(owner=common.owner())
    said = next((x for x in lines if x.startswith(head)), None)
    lines = [x for x in lines if not x.startswith(head) and not x.startswith("  owner rule ")]
    if draft:
        lines.append(said or (f"{head} Obey each one. When a rule is the reason for a verdict of noise or ignore, start the "
                              "reason with `owner rule <its number>:` exactly."))
        lines += [f"  owner rule {r.get('id')} ({filters.WAY_WORDS[r['way']]}): {r['text']}{filters.because(r)}" for r in draft]
    return think._owner_filter(lines)


# --- the dry runs ------------------------------------------------------------------------------------------------------
def daily_cap():
    """RSI runs allowed a day: settings "rsi": {"daily_runs": n}, else DAILY_CAP. Apart from his daily AI limit."""
    got = ((common.read_json(common.SETTINGS, {}) or {}).get("rsi") or {}).get("daily_runs")
    return got if isinstance(got, int) and not isinstance(got, bool) and got >= 0 else DAILY_CAP


def runs_today():
    got = common.read_json(RUNS, {}) or {}
    return int(got.get("runs") or 0) if got.get("day") == common.now().date().isoformat() else 0


def at_cap():
    return runs_today() >= daily_cap()


def _count_run():
    """One more RSI run started today, kept apart from his daily limit's count. Never raises."""
    try:
        common.write_json(RUNS, {"day": common.now().date().isoformat(), "runs": runs_today() + 1})
    except (OSError, ValueError):
        pass


def _run(prompt, model, expect, payload):
    """The default runner: the engine's AI step runner (ai_steps.agent) on the run itself (ai_steps.own_call), never a
    pass's wrapper or its clock, so it works inside the long-running listener. Each try is one RSI run: checked against
    the RSI cap, counted in runs.json and not in his daily count, and held to RUN_SECONDS of its own."""
    import ai_steps

    def once(p, m, t):
        if at_cap():
            return ai_steps.Result(False, why=CAP_REACHED)
        _count_run()
        return ai_steps.own_call(p, m, min(t, RUN_SECONDS), count=False)
    return ai_steps.agent(prompt, model, expect, RUN_SECONDS, call=once)


def _ask(runner, prompt, model, expect, path):
    """One batch to the layer: the default runner, or a stand-in (tests), which counts as one RSI run."""
    if runner is None:
        return _run(prompt, model, expect, path)
    import ai_steps
    if at_cap():
        return ai_steps.Result(False, why=CAP_REACHED)
    _count_run()
    return runner(prompt, model, expect, path)


def ask_text(prompt, model, runner=None):
    """One plain text run with no tools (the coach's): checked against the RSI cap and counted as one RSI run, on the run
    itself (ai_steps.own_call) with RUN_SECONDS of its own, tried once. runner(prompt, model) stands in for it (tests).
    Returns an ai_steps.Result whose text is the reply."""
    import ai_steps
    if at_cap():
        return ai_steps.Result(False, why=CAP_REACHED)
    _count_run()
    if runner is not None:
        return runner(prompt, model)
    return ai_steps.own_call(prompt, model, RUN_SECONDS, count=False, tools="")


def _batches(rows, most, chars, size):
    """rows in order, cut into batches of at most `most` rows and `chars` characters; a row alone is never cut."""
    out, cur, used = [], [], 0
    for r in rows:
        n = size(r)
        if cur and (len(cur) >= most or used + n > chars):
            out.append(cur)
            cur, used = [], 0
        cur.append(r)
        used += n
    return out + ([cur] if cur else [])


def _as_before(payload, part):
    """Take out of a rebuilt judge payload what the batch's messages produced or what came after them, so the judge sees
    what it saw before deciding, as near as the stores allow: open tasks that cite one of them or were made after the
    first of them came in (their records go too), and what the owner settled after then or about one of them. Inside the
    batch's reading connection."""
    ph = ",".join("?" * len(part))
    cut = db.query(f"SELECT min(ingested_at) FROM messages WHERE id IN ({ph})", tuple(int(i) for i in part))[0][0]
    drop = {r[0] for r in db.query(f"SELECT DISTINCT task_id FROM task_refs WHERE ref_type = 'message' AND value IN ({ph})",
                                   tuple(part))}
    later = set()
    if cut is not None:
        drop |= {r[0] for r in db.query("SELECT id FROM tasks WHERE created_at > ?", (cut,))}
        later = set(db.query("SELECT domain, key FROM answered WHERE domain <> 'judged' AND answered_at > ?", (cut,)))
    kept = []
    for t in payload.get("open_tasks") or []:
        if t.get("id") not in drop:
            kept.append(t)
            continue
        rec = t.get("full_record")
        rec = rec.get("path") if isinstance(rec, dict) else rec
        if rec and os.path.isfile(str(rec)) and os.path.normpath(str(rec)).startswith(os.path.normpath(WORK)):
            os.remove(str(rec))
    payload["open_tasks"] = kept
    mine = re.compile(r"\bmsg:(?:" + "|".join(re.escape(i) for i in part) + r")\b")
    payload["already_settled"] = [s for s in payload.get("already_settled") or []
                                  if (s.get("domain"), s.get("key")) not in later and not mine.search(str(s.get("key")))]
    return payload


def _judge_runs(ids, text, runner, stamp):
    """{message id: (call, reason, its coverage mark)} from the judge run again on those messages, in batches the payload
    builder cuts to BATCH_MESSAGES and BATCH_CHARS; a failed batch's messages get none."""
    import think
    out, failed, left, n = {}, [], [str(i) for i in ids], 0
    while left:
        n += 1
        with db.reading():          # held only while the payload is built, never through the Claude run
            payload = jp.build([], max_msgs=BATCH_MESSAGES, max_chars=BATCH_CHARS, ids=left,
                               records_folder=os.path.join(WORK, "items"))
            part = [str(m["id"]) for m in payload.get("messages") or []]
            if not part:
                break                   # what is left is not in the database: no verdict, not graded
            payload = _as_before(payload, part)
        left = [i for i in left if i not in part]
        path = os.path.join(WORK, f"payload_{stamp}_judge{n}.json")
        common.write_json(path, think.judge_view(payload))
        expect = os.path.join(WORK, f"verdicts_{stamp}_judge{n}.json")
        res = _ask(runner, think.judge_prompt(path, text), think.model(), expect, path)
        if not getattr(res, "ok", False):
            failed.append(str(getattr(res, "why", "") or "the run failed"))
            continue
        for v in (common.read_json(expect, {}) or {}).get("verdicts") or []:
            if not isinstance(v, dict):
                continue
            for mid in (v.get("ids") if isinstance(v.get("ids"), list) else [v.get("id")]):
                if str(mid) in part and v.get("disposition"):
                    out[str(mid)] = ("hide" if v["disposition"] in rule_book.HIDES else "show",
                                     f"{v['disposition']}: " + " ".join(str(v.get("reason") or "").split())[:300],
                                     _coverage(v))
    return out, failed


def _coverage(v):
    """The judge's coverage mark on one rerun verdict, kept as judgment_commit would store it (None when not said)."""
    import judgment_commit as jc
    try:
        leaned = jc.leaned_on(v)
    except ValueError:
        leaned = None
    return {"covered": v["covered"] if isinstance(v.get("covered"), bool) else None, "leaned_on": leaned}


def _first_sort_runs(ids, text, runner, stamp):
    """{message id: (call, reason)} from the first sort run again: a message it sets aside is hidden, one it leaves goes on
    to the judge (shown by this layer). A sender the first sort never sets aside is not sent to it. Batches of at most
    think.FAST_MOST messages and FIRST_CHARS characters of what it reads."""
    import think
    out, failed = {}, []
    with db.reading():
        guarded = jp.junk_guard()
        rows = db.query(f"SELECT {think.FIRST_SORT_SEES} FROM messages m WHERE m.id IN ({','.join('?' * len(ids))})"
                        " ORDER BY m.id", tuple(int(i) for i in ids)) if ids else []
    sent = []
    for r in rows:
        if guarded(r[2]):
            out[str(r[0])] = ("show", "a sender the first sort never sets aside: left for the judge")
        else:
            sent.append(r)
    size = lambda r: len(json.dumps(think.first_sort_input([r])["messages"][0], default=str))  # noqa: E731
    for n, part in enumerate(_batches(sent, think.FAST_MOST, FIRST_CHARS, size), 1):
        path = os.path.join(WORK, f"payload_{stamp}_first{n}.json")
        common.write_json(path, think.first_sort_input(part))
        expect = os.path.join(WORK, f"verdicts_{stamp}_first{n}.json")
        res = _ask(runner, think.first_sort_prompt(path, text), think.FAST_MODEL, expect, path)
        if not getattr(res, "ok", False):
            failed.append(str(getattr(res, "why", "") or "the run failed"))
            continue
        hidden = {str(e.get("id")): " ".join(str(e.get("reason") or "").split())[:300]
                  for e in (common.read_json(expect, {}) or {}).get("nothing") or []
                  if isinstance(e, dict) and str(e.get("reason") or "").strip()}
        for r in part:
            mid = str(r[0])
            out[mid] = ("hide", f"set aside: {hidden[mid]}") if mid in hidden else ("show", "left for the judge")
    return out, failed


# --- grading -----------------------------------------------------------------------------------------------------------
def _decider(row):
    """The setting or list that decided a program layer's call, by its source and in plain words (held.why)."""
    import held
    src = row.get("source")
    return {"layer": row.get("layer"), "source": src,
            "what": held.why(row.get("verdict"), src)[0] if src else "Recorded without its source."}


def _user(row):
    return {k: row.get(k) for k in ("press", "meaning", "button", "choice", "at")}


def grade(section=None, rules_file=None, runner=None):
    """Grade the rule book's active rows (one section, or all), the judge and first sort run again with his live rules or
    the draft rules file given. runner(prompt, model, expect, payload_path) stands in for the AI step runner (tests);
    it must write the file expect. Returns the result, also written to grades\\<time>.json."""
    if _replaying():
        return {"replay": True, "sections": {}, "note": "a replay day grades nothing"}
    if at_cap():
        return {"result": f"not graded: {CAP_REACHED}", "sections": {}, "runs": 0, "cap": daily_cap()}
    now = common.now()
    stamp = now.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    text = owner_filter(rules_file)
    graded, neutral, not_graded, todo = [], 0, [], {"judge": [], "first_sort": []}
    for row in rule_book.rows(section):
        mark, wanted = signal(row)
        if mark == "neutral":
            neutral += 1
            continue
        entry = {"message": str(row.get("message")), "section": row.get("section"), "layer": row.get("layer"),
                 "signal": mark, "call_was": row.get("call"), "wanted": wanted, "user": _user(row),
                 "was_source": row.get("source"), "seen": row.get("seen"),
                 "covered_was": row.get("covered"), "leaned_on_was": row.get("leaned_on")}
        if row.get("layer") in PROGRAM:
            entry.update(rerun=False, call_now=row.get("call"), decided_by=_decider(row),
                         reason=_decider(row)["what"])
            graded.append(entry)
        elif row.get("layer") in RERUN:
            entry["rerun"] = True
            todo[RERUN[row["layer"]]].append(entry)
        else:
            not_graded.append(dict(entry, why=f"no layer to grade: decided by {row.get('layer') or 'unknown'}"))
    os.makedirs(WORK, exist_ok=True)
    runs, failed = runs_today(), []
    for layer, fn in (("judge", _judge_runs), ("first_sort", _first_sort_runs)):
        if not todo[layer]:
            continue
        got, bad = fn([e["message"] for e in todo[layer]], text, runner, stamp)
        failed += [f"{layer}: {b}" for b in bad]
        for e in todo[layer]:
            if e["message"] in got:
                e["call_now"], e["reason"], *mark = got[e["message"]]
                if mark:
                    e.update(mark[0])           # the rerun judge's coverage mark: kept, not scored
                graded.append(e)
            else:
                not_graded.append(dict(e, why=f"the {layer} run gave no verdict for it"))
    sections = {}
    for e in graded:
        e["matched"] = e["call_now"] == e["wanted"]
        s = sections.setdefault(e["section"], {"matched": 0, "graded": 0, "misses": []})
        s["graded"] += 1
        s["matched"] += e["matched"]
        if not e["matched"]:
            s["misses"].append({k: e.get(k) for k in ("message", "layer", "call_was", "call_now", "wanted", "reason", "user",
                                                    "decided_by", "seen", "rerun", "covered_was", "leaned_on_was",
                                                    "covered", "leaned_on")})
    for s in sections.values():
        s["line"] = f"{s['matched']} of {s['graded']} matched"
    result = {"at": now.isoformat(timespec="seconds"), "section": section,
              "rules": f"draft: {rules_file}" if rules_file else "live",
              "sections": sections, "neutral": neutral, "not_graded": not_graded, "runs": max(0, runs_today() - runs), "failed": failed,
              "rows": graded}
    os.makedirs(GRADES, exist_ok=True)
    result["file"] = os.path.join(GRADES, f"{stamp}.json")
    common.write_json(result["file"], result)
    with open(SCORES, "a", encoding="utf-8") as f:
        for name, s in sorted(sections.items()):
            f.write(json.dumps({"date": now.date().isoformat(), "at": result["at"], "section": name,
                                "matched": s["matched"], "graded": s["graded"], "rules": "draft" if rules_file else "live",
                                "grade": os.path.basename(result["file"])}) + "\n")
    return result


def scores(section=None):
    """The score history, oldest first: one line per section per grade."""
    try:
        with open(SCORES, encoding="utf-8") as f:
            got = [json.loads(x) for x in f.read().splitlines() if x.strip()]
    except (OSError, ValueError):
        return []
    return [x for x in got if section is None or x.get("section") == section]


# --- every kind of work: my picks against what he did (the judgment rebuild, phase 4) -----------------------------------
WORK_GRADES = os.path.join(STORE, "work_grades")
WORK_SCORES = os.path.join(STORE, "work_scores.jsonl")


def work_rows(section=None):
    """The rule book's rows that carry my pick, one per press on a card (a card with several messages wrote a row for each;
    they are one answer), oldest first."""
    seen, out = set(), []
    for r in reversed(rule_book.rows(section)):
        if not isinstance(r.get("pick"), dict) or not isinstance(r.get("did"), dict):
            continue
        key = (r.get("card") or r.get("message"), r.get("at"), r.get("press"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _work_miss(r, got):
    import picks
    seen = r.get("seen") or {}
    did = r.get("did") or {}
    return {"row": r.get("id") or r.get("message"), "at": r.get("at"), "missed": sorted(a for a, ok in got.items() if not ok),
            "sender": seen.get("sender"), "what": seen.get("what"), "area": r.get("card_area"), "kind": r.get("card_kind"),
            "important": r.get("card_important"), "my_pick": picks.label(r["pick"]) if r["pick"].get("do") in picks.DOES else None,
            "he_did": picks._habit_label(did) or did.get("do"), "where": (r.get("off_page") or {}).get("where") or "page"}


def grade_work(section=None):
    """Score my picks in every kind of work (one, or all) against what he did, by decisions, wording, timing and urgency
    (work_rules.score). Program code only: no AI run, nothing live changed. Writes the result to work_grades\\<time>.json and
    one line per kind of work to work_scores.jsonl; returns the result."""
    import work_rules
    if _replaying():
        return {"replay": True, "sections": {}}
    now = common.now()
    stamp = now.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    secs = {}
    for sec in ([section] if section else rule_book.SECTIONS):
        rows = work_rows(sec)
        total, per = work_rules.score(rows)
        misses = [_work_miss(r, per[r.get("id") or r.get("message")]) for r in rows
                  if not all(per.get(r.get("id") or r.get("message"), {}).values())]
        m, n = sum(v[0] for v in total.values()), sum(v[1] for v in total.values())
        secs[sec] = {"aspects": total, "matched": m, "graded": n, "answers": len([r for r in rows if per.get(r.get("id") or r.get("message"))]),
                     "line": f"{m} of {n} matched", "misses": misses}
    result = {"at": now.isoformat(timespec="seconds"), "section": section, "sections": secs}
    os.makedirs(WORK_GRADES, exist_ok=True)
    result["file"] = os.path.join(WORK_GRADES, f"{stamp}.json")
    common.write_json(result["file"], result)
    with open(WORK_SCORES, "a", encoding="utf-8") as f:
        for name, s in secs.items():
            f.write(json.dumps({"date": now.date().isoformat(), "at": result["at"], "section": name, "aspects": s["aspects"],
                                "matched": s["matched"], "graded": s["graded"], "answers": s["answers"]}) + "\n")
    return result


def work_scores(section=None):
    """The score history of every kind of work, oldest first."""
    try:
        with open(WORK_SCORES, encoding="utf-8") as f:
            got = [json.loads(x) for x in f.read().splitlines() if x.strip()]
    except (OSError, ValueError):
        return []
    return [x for x in got if section is None or x.get("section") == section]


if __name__ == "__main__":
    print(json.dumps(grade(sys.argv[1] if len(sys.argv) > 1 else None), indent=1, default=str))
