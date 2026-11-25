r"""What the page shows about changes to the program: the feed document "changes", made from the change records.

The records are the guardrails' (Plugin build\RULEBOOK.md 4c): one file per change, <home>\changes\<id>.json, written only by
the change skill's helper (System\live\setup\setup_changes.py). This file only reads them. The page's shape is the page
lane's (Package\Test photos\program changes\page needs.md, section 1).

    doc()        the "changes" document, or None when this copy has no change skill and Level 3 made no change (the page
                 then shows nothing of it)
    learned()    the rows for the rule changes a Level 3 section made on its own (coach.self_promotions; guardrail A15 as
                 amended): id "rsi-<stamp>", status "learned" or "undone", each with Undo (answers routes it to coach.undo_self)
    undoing(id)  / done_undoing()   the mark that an Undo pressed on the page is being carried out
"""
import glob
import os

import common

DIR = os.path.join(common.HOME, "changes")
SKILL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "setup", "setup_changes.py")
UNDOING = os.path.join(common.paths.STATE, "undoing.json")
# the helper's step names, as the owner reads them
STEP_WORDS = {"undo copy": "Save the undo copy", "edit": "Edit the program", "rebuild the page": "Rebuild the page",
              "restart the listener": "Restart the listener", "run a check": "Run a check", "look at the page": "Look at the page"}
ORDER = list(STEP_WORDS)
LIST_STATES = {"go": "working", "doing": "working", "done": "done", "failed": "failed", "undone": "undone"}
PARTS = {"general": "general", "taught": "addon"}
CANNOT = "Cards it made, and anything sent on an approval given while it was working, stay as they are."


def records():
    out = []
    for f in glob.glob(os.path.join(DIR, "*.json")):
        c = common.read_json(f, None)
        if isinstance(c, dict) and c.get("id"):
            out.append(c)
    return sorted(out, key=lambda c: str(c.get("id")))


def _steps(c):
    """Each of the six steps with todo, doing, done or failed, from what the record says happened."""
    seen = {}
    for s in c.get("steps") or []:
        name = str(s.get("name") or "")
        if name in STEP_WORDS:
            seen[name] = s
    out, doing_marked = [], False
    for name in ORDER:
        s = seen.get(name)
        if s is not None:
            row = {"name": STEP_WORDS[name], "state": "done" if s.get("ok") else "failed"}
            if not s.get("ok") and s.get("why"):
                row["why"] = str(s["why"])[:300]
        elif c.get("state") in ("go", "doing") and not doing_marked:
            row, doing_marked = {"name": STEP_WORDS[name], "state": "doing"}, True
        else:
            row = {"name": STEP_WORDS[name], "state": "todo"}
        out.append(row)
    return out


def _failed(c):
    bad = [s for s in c.get("steps") or [] if not s.get("ok")]
    if not bad:
        return None, None
    s = bad[0]
    return STEP_WORDS.get(str(s.get("name")), str(s.get("name"))), str(s.get("why") or "")[:300]


def undoing(cid):
    common.write_json(UNDOING, {"id": cid, "at": common.now().isoformat(timespec="seconds")})


def done_undoing():
    if os.path.exists(UNDOING):
        os.remove(UNDOING)


LEARNED_PREFIX = "rsi-"
LEARNED_PART = "your rules (changed on its own at learning level 3)"


def learned():
    """Change history rows for the rule changes the Level 3 loop made on its own, newest first. Never raises."""
    try:
        import coach
        import rsi_loop
        import rule_book
        out = []
        for h in coach.self_promotions():
            sec = rule_book.SECTION_WORDS.get(h.get("section"), h.get("section"))
            change = rsi_loop._change_words({"kind": "work" if h.get("of") == "work" else "rule", "change": h.get("change"),
                                             "rules_before": (h.get("work_rules") if h.get("of") == "work"
                                                              else (h.get("rules") or {}).get("rules")) or []})
            row = {"id": LEARNED_PREFIX + h["id"], "words": f"I changed this myself: {change}",
                   "what": f"In {str(sec).lower()}. Why: {str(h.get('reason') or '').rstrip('.')}. It gets {rsi_loop._score_words(h.get('score_draft'))} "
                           f"of your past answers right instead of {rsi_loop._score_words(h.get('score_live'))}, and none wrong that I had right before.",
                   "at": h.get("at"), "part": "rsi", "part_name": LEARNED_PART,
                   "status": "undone" if h.get("undone_at") else "learned", "finished_at": h.get("at")}
            if h.get("undone_at"):
                row["undone_at"] = h["undone_at"]
            out.append(row)
        return list(reversed(out))
    except Exception as e:  # noqa: BLE001  the list of changes is never lost over these rows; the reason is logged
        common.log_line(os.path.join(common.LOGS, "errors.log"), f"changes learned: {type(e).__name__}: {e}")
        return []


def doc():
    rsi = learned()
    if not os.path.exists(SKILL):
        return {"active": None, "list": rsi} if rsi else None
    recs = records()
    being_undone = (common.read_json(UNDOING, {}) or {}).get("id")
    active = None
    for c in reversed(recs):
        if c.get("state") in ("talking", "go", "doing"):
            talking = c.get("state") == "talking"
            steps = _steps(c)
            now_step = next((s["name"] for s in steps if s["state"] == "doing"), None)
            waits = bool(talking and str(c.get("agreed") or "").strip() and not c.get("go"))
            active = {"id": c["id"], "words": c.get("asked") or "", "status": "asking" if talking else "working",
                      "awaiting_go": waits,       # only then is there a go to give: the page shows "Yes, make this change"
                      "summary": c.get("agreed") or "",
                      "step": (f"Now: {now_step}" if now_step else "Waiting for your go" if waits else
                               "agreeing exactly what changes" if talking else ""),
                      "steps": steps}
            break
    later = {}
    for c in recs:
        for b in c.get("built_on") or []:
            later.setdefault(b, []).append({"id": c["id"], "words": c.get("asked") or "", "status": c.get("state")})
    out = []
    for c in reversed(recs):
        state = c.get("state")
        if state not in LIST_STATES:
            continue            # talking, dropped, and the update's own states are not in the list of changes made
        row = {"id": c["id"], "words": c.get("asked") or "", "what": c.get("agreed") or "", "at": c.get("created"),
               "part": PARTS.get(c.get("part"), "general"), "status": "undoing" if being_undone == c["id"] else LIST_STATES[state]}
        if c.get("done_at"):
            row["finished_at"] = c["done_at"]
        if state in ("go", "doing"):
            row["step"] = next((s["name"] for s in _steps(c) if s["state"] == "doing"), "")
        if state == "failed":
            row["failed_step"], row["why"] = _failed(c)
        if c.get("undone_at"):
            row["undone_at"] = c["undone_at"]
        if later.get(c["id"]):
            row["built_on_by"] = [{"id": o["id"], "words": o["words"], "status": "undone" if o["status"] == "undone" else "done"}
                                  for o in later[c["id"]] if o["status"] in ("done", "undone")]
        if state == "done":
            row["cannot_take_back"] = [CANNOT]
        out.append(row)
    if rsi:
        out = sorted(out + rsi, key=lambda r: str(r.get("at") or ""), reverse=True)
    return {"active": active, "list": out}
