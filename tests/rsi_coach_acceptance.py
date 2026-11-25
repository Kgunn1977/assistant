r"""Acceptance: the coach (the RSI plan, "The four parts" 3). The engine's own coach run in a scratch home with the grader
test's made-up messages, verdicts, rule book rows and rules. Nothing goes to Claude: the grader's layer runs and the
coach's own text run are stood in for with canned answers.

- A coach answer with one rule change gives the one draft file (live rules plus that change) and a proposal with fixes N,
  breaks M and both scores over the same rows.
- An answer with two changes is refused and nothing is written (outside the RSI run count).
- A program-layer miss gives a proposed setting or list change, and no draft rules.
- His live rules, the rule book, the guardrails and the grader's earlier grades are unchanged by coach().
- promote() gives his live rules the change, the coach's reason written into the rule it adds or edits, and keeps the rules before as a version with its reason; reject() keeps the
  draft as rejected with its reason; both reasons reach the next coach's prompt.
- The coach's own run has no tools; at the RSI cap the coach runs nothing.

    python tests\rsi_coach_acceptance.py
"""
import json
import os
import subprocess
import sys
import tempfile

import _cleanup  # noqa: E402  the scratch folder goes when the test ends
from rsi_grader_acceptance import INSIDE as GRADER_INSIDE

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
results = []
SETUP = GRADER_INSIDE.split("\n\ndef snapshot():")[0]       # the grader test's made-up home, used as it is

INSIDE = SETUP + r'''
import subprocess as sp, types
import coach, ai_steps
ENGINE = [os.path.join(sys.argv[1], "rules", "rulebook.json"), os.path.join(sys.argv[1], "grader.py"),
          os.path.join(sys.argv[1], "filters.py")]


def snapshot():
    files = {}
    for top, dirs, names in os.walk(common.HOME):
        rel = os.path.relpath(top, common.HOME).replace("\\", "/")
        if rel.startswith("logs"):
            continue
        for n in names:
            if not n.endswith((".duckdb", ".wal", ".lock")):
                with open(os.path.join(top, n), "rb") as f:
                    files[rel + "/" + n] = hashlib.sha1(f.read()).hexdigest()
    for p in ENGINE:
        with open(p, "rb") as f:
            files["engine:" + os.path.basename(p)] = hashlib.sha1(f.read()).hexdigest()
    files["db"] = hashlib.sha1(json.dumps({t: db.query(f"SELECT * FROM {t} ORDER BY 1") for t in ("answered", "tasks")},
                                          default=str).encode()).hexdigest()
    return files


def diff(a, b, keep=()):
    """Paths added, removed or changed between two snapshots, outside the given prefixes."""
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k) and not k.startswith(keep))


ADD = "Show every message about the shed paint"
EDIT = "Hide mail from the paint shop unless it is about the shed"


def stub(prompt, model, expect, payload):
    got = json.load(open(payload, encoding="utf-8"))
    ids = sorted(str(m["id"]) for m in got["messages"])
    if "says" in got["messages"][0]:
        common.write_json(expect, {"nothing": []})
    else:
        v = {"21": "noise", "22": "task", "23": "noise", "28": "noise"}
        if ADD in prompt:                   # the added rule: fixes 23 and 28, breaks 22
            v.update({"23": "task", "28": "task", "22": "noise"})
        if EDIT in prompt:                  # the edited rule: fixes 28
            v["28"] = "task"
        common.write_json(expect, {"verdicts": [{"id": int(i), "disposition": v[i], "reason": f"made-up reason {i}"}
                                                for i in ids]})
    return type("R", (), {"ok": True, "why": ""})()


asked = []


def answer(text):
    def ask(prompt, model):
        asked.append({"prompt": prompt, "model": model})
        return ai_steps.Result(True, text)
    return ask


ONE = json.dumps({"change": "add", "text": ADD, "way": "always_show", "reason": "He pressed should have seen on shed mail"})
OTHER = json.dumps({"change": "edit", "rule": 3, "text": EDIT, "way": "show_less", "reason": "Keep shed mail from the shop"})
TWO_LIST = json.dumps([json.loads(ONE), json.loads(OTHER)])
TWO_OBJECTS = ONE + "\n" + OTHER
TWO_INSIDE = json.dumps({"change": [json.loads(ONE), json.loads(OTHER)], "reason": "two at once"})
SETTING = json.dumps({"change": "setting", "what": "Turn newsletters to show, so mail with an unsubscribe link is read",
                      "reason": "He wanted a sale mailing the junk rule held back"})

grader.grade("page", runner=stub)        # the latest live grade the coach reads for the page section
start = snapshot()
old_grades = {k: v for k, v in start.items() if k.startswith("state/rsi/grades/")}
with open(grader.SCORES, encoding="utf-8") as f:
    old_scores = f.read()

# two changes: refused, nothing written
a = snapshot()
r1 = coach.coach("page", runner=stub, ask=answer(TWO_LIST))
r2 = coach.coach("page", runner=stub, ask=answer(TWO_OBJECTS))
r3 = coach.coach("page", runner=stub, ask=answer(TWO_INSIDE))
b = snapshot()
out["2. two changes refused, nothing written but the RSI run count"] = [r1, r2, r3, diff(a, b), os.path.exists(coach.DRAFT),
                                                                         os.path.exists(coach.PROPOSALS)]

# one rule change: the draft and a proposal with fixes and breaks
p1 = coach.coach("page", runner=stub, ask=answer(ONE))
draft = common.read_json(coach.DRAFT, {})
out["1. one change: the draft is the live rules plus that change"] = [
    [(r["id"], r["text"], r["way"]) for r in draft["rules"]], draft.get("next")]
out["1. the proposal: fixes N, breaks M, both scores over the same rows"] = [
    p1["kind"], p1["fixes"], p1["fixed"], p1["breaks"], p1["broken"], p1["score_live"], p1["score_draft"], p1["compared"],
    p1["complete"], p1["line"], os.path.exists(p1["file"]), p1["draft_file"] == coach.DRAFT]
out["1. the coach was told the page misses and his rules, on the judge's model, once"] = [
    len(asked), asked[-1]["model"], "\"message\": \"23\"" in asked[-1]["prompt"], "\"message\": \"28\"" in asked[-1]["prompt"],
    "rule 3 (show_less, on): Hide mail from the paint shop" in asked[-1]["prompt"], "\"message\": \"25\"" in asked[-1]["prompt"]]
p2 = coach.coach("page", runner=stub, ask=answer(OTHER))
out["1. a second proposal: an edit"] = [p2["fixes"], p2["fixed"], p2["breaks"], p2["score_live"], p2["score_draft"],
                                        [(r["id"], r["text"]) for r in common.read_json(coach.DRAFT, {})["rules"]]]

# a program-layer miss: a setting change, no draft rules
before_draft = snapshot()["state/rsi/draft_rules.json"]
p3 = coach.coach("mailings", runner=stub, ask=answer(SETTING))
out["3. program-layer miss: a setting change, no draft"] = [
    p3["kind"], p3["change"], p3["draft_rules"], p3.get("draft_file"), p3["misses"],
    snapshot()["state/rsi/draft_rules.json"] == before_draft, "ONE setting or list change" in asked[-1]["prompt"]]
wrong = coach.coach("mailings", runner=stub, ask=answer(ONE))
out["3. a rule change for a program-layer miss is refused"] = wrong

end = snapshot()
with open(grader.SCORES, encoding="utf-8") as f:
    scores_now = f.read()
out["4. live rules, rule book, guardrails, grader and earlier grades unchanged by coach()"] = [
    diff(start, end, keep=("state/rsi/",)), [k for k in old_grades if end.get(k) != old_grades[k]],
    scores_now.startswith(old_scores)]

# reject the edit, promote the add
rj = coach.reject(p2, "It would still hide the shop's other mail")
rec = common.read_json(rj["record"], {})
out["6. reject: the draft kept as rejected with its reason"] = [
    os.path.dirname(rj["record"]) == coach.VERSIONS, rec["kind"], rec["reason"], rec["coach_reason"], rec["section"],
    [(r["id"], r["text"]) for r in rec["draft"]], bool(rec["date"]), common.read_json(p2["file"], {})["status"],
    filters.rules() == p1["rules_before"]]
before_rules = common.read_json(filters.RULES_FILE, {})
pr = coach.promote(p1)
ver = common.read_json(pr["version"], {})
out["5. promote: the live rules get the change, the rules before kept as a version with its reason"] = [
    [(r["id"], r["text"], r["way"], r["from"], r.get("reason")) for r in filters.rules()], ver["kind"], ver["rules"] == before_rules,
    ver["reason"], ver["rule"], bool(ver["date"]), common.read_json(p1["file"], {})["status"]]
refused = []
for fn in (lambda: coach.promote(p1), lambda: coach.promote(p3)):
    try:
        fn()
        refused.append("not refused")
    except ValueError as e:
        refused.append(str(e))
out["5. a decided or setting proposal is not promoted"] = refused
coach.coach("page", runner=stub, ask=answer(TWO_LIST))
out["5. the next coach is told what was kept and rejected, and the rule's reason"] = [
    "kept " in asked[-1]["prompt"] and "He pressed should have seen on shed mail" in asked[-1]["prompt"],
    "Why rejected: It would still hide the shop's other mail" in asked[-1]["prompt"],
    f"rule 4 (always_show, on): {ADD} Reason: He pressed should have seen on shed mail" in asked[-1]["prompt"]]
p4 = coach.coach("page", runner=stub, ask=answer(OTHER))
pr4 = coach.promote(p4)
out["5. promote an edit: the rule gets the new words and the coach's reason; the draft carried it too"] = [
    [(r["id"], r["text"], r.get("reason")) for r in filters.rules()], pr4["rule"],
    [(r["id"], r.get("reason")) for r in p4["draft_rules"]]]

# the coach's own run on the default path: no tools, an RSI run, not the owner's
seen = []


def fake_run(cmd, input=None, timeout=None, **k):
    seen.append({"cmd": cmd, "timeout": timeout})
    return sp.CompletedProcess(cmd, 0, stdout=json.dumps({"result": SETTING, "session_id": "s", "total_cost_usd": 0}),
                               stderr="")


ai_steps.claude_exe = lambda: "claude-stand-in"
ai_steps.subprocess = types.SimpleNamespace(run=fake_run, TimeoutExpired=sp.TimeoutExpired)
daily, rsi = settings_page.runs_today(), grader.runs_today()
res = grader.ask_text("made-up prompt", "opus")
cmd = seen[-1]["cmd"]
out["7. the coach's run has no tools and counts as one RSI run"] = [
    res.ok, res.text == SETTING, cmd[cmd.index("--tools") + 1], seen[-1]["timeout"], settings_page.runs_today() - daily,
    grader.runs_today() - rsi]

# the RSI cap
st = common.settings()
st["rsi"] = {"daily_runs": grader.runs_today()}
common.write_json(common.SETTINGS, st)
a = snapshot()
n = len(asked)
capped = coach.coach("page", runner=stub, ask=answer(ONE))
out["7. at the RSI cap the coach runs nothing and writes nothing"] = [capped, len(asked) - n, diff(a, snapshot())]
print(json.dumps(out, default=str))
'''

LINES = ["refused: the answer holds more than one change; nothing was written"] * 3
WANT = {
    "2. two changes refused, nothing written but the RSI run count": [*LINES, ["state/rsi/runs.json"], False, False],
    "1. one change: the draft is the live rules plus that change": [
        [[3, "Hide mail from the paint shop", "show_less"], [4, "Show every message about the shed paint", "always_show"]], 5],
    "1. the proposal: fixes N, breaks M, both scores over the same rows": [
        "rule", 2, ["23", "28"], 1, ["22"], "3 of 5 matched", "4 of 5 matched", 5, True,
        "fixes 2 of your past corrections, breaks 1", True, True],
    "1. the coach was told the page misses and his rules, on the judge's model, once": [4, "opus", True, True, True, False],
    "1. a second proposal: an edit": [1, ["28"], 0, "3 of 5 matched", "4 of 5 matched",
                                      [[3, "Hide mail from the paint shop unless it is about the shed"]]],
    "3. program-layer miss: a setting change, no draft": [
        "setting", {"change": "setting", "reason": "He wanted a sale mailing the junk rule held back",
                    "what": "Turn newsletters to show, so mail with an unsubscribe link is read"},
        None, None, ["25"], True, True],
    "3. a rule change for a program-layer miss is refused":
        "refused: these misses were made by a program layer: only a setting or list change fits; nothing was written",
    "4. live rules, rule book, guardrails, grader and earlier grades unchanged by coach()": [[], [], True],
    "6. reject: the draft kept as rejected with its reason": [
        True, "rejected", "It would still hide the shop's other mail", "Keep shed mail from the shop", "page",
        [[3, "Hide mail from the paint shop unless it is about the shed"]], True, "rejected", True],
    "5. promote: the live rules get the change, the rules before kept as a version with its reason": [
        [[3, "Hide mail from the paint shop", "show_less", "made up", None],
         [4, "Show every message about the shed paint", "always_show", "I learned it from your answers: He pressed should have seen on shed mail",
          "He pressed should have seen on shed mail"]],
        "version", True, "He pressed should have seen on shed mail", 4, True, "promoted"],
    "5. a decided or setting proposal is not promoted": [
        "that proposal was already promoted",
        "a setting or list change is the owner's to make in Settings; nothing is approved"],
    "5. the next coach is told what was kept and rejected, and the rule's reason": [True, True, True],
    "5. promote an edit: the rule gets the new words and the coach's reason; the draft carried it too": [
        [[3, "Hide mail from the paint shop unless it is about the shed", "Keep shed mail from the shop"],
         [4, "Show every message about the shed paint", "He pressed should have seen on shed mail"]], 3,
        [[3, "Keep shed mail from the shop"], [4, "He pressed should have seen on shed mail"]]],
    "7. the coach's run has no tools and counts as one RSI run": [True, True, "", 300, 0, 1],
    "7. at the RSI cap the coach runs nothing and writes nothing": ["not coached: I've done my learning runs for today. The rest wait until tomorrow.", 0, []],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="rsicoach-")
    try:
        env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"), PYTHONPATH=HERE)
        env.pop("ASSISTANT_REPLAY", None)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, LIVE, "-"], capture_output=True, text=True,
                           env=env, timeout=180)
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = {}
        if r.returncode or not got:
            check("the checks ran", r.stderr.strip()[-2500:], "")
        for name, want in WANT.items():
            check(name, got.get(name), want)
    finally:
        _cleanup.remove(tmp)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
