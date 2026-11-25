r"""Acceptance: the grader (the RSI plan, "The four parts" 2), read-only. The engine's own grader run in a scratch home with
a scratch database of made-up messages, verdicts, rule book rows and rules. Nothing goes to Claude: a stand-in runner
returns canned verdicts and notes what it was given.

- Rows with a real signal are graded "X of N matched" per section: agreeing and contradicting rows scored right; a neutral
  press (Got it) is not counted.
- A row the judge or the first sort decided is run again, one run per layer batch, on the layer's own model; a row a
  program layer decided (rule 559, the ignore list) is never sent to a run, is graded from its recorded call and names
  the setting or list that decided.
- Each miss stands beside what the owner did and the layer's reason.
- A draft rules file, when given, is what the layer is told in place of the live rules.
- Nothing in the answered table, the cards, the Hidden lists, the live rules, the rule book or any other file of the home
  changes during a grade (outside the grader's own state\rsi folder).
- A score history line is appended per section per grade; the RSI runs are counted apart from the daily limit's count.

    python tests\rsi_grader_acceptance.py
"""
import json
import os
import subprocess
import sys
import tempfile

import _cleanup  # noqa: E402  the scratch folder goes when the test ends

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
results = []

INSIDE = r'''
import datetime as dt, hashlib, json, os, sys
sys.path.insert(0, sys.argv[1])
draft_file = sys.argv[2]
import common, db, items, filters, rule_book, grader, settings_page
out = {}
db.init_schema()
items.ensure()
common.settings()       # a home has its settings file (reading it makes the default one in a home with none)
ts = dt.datetime(2026, 11, 23, 8, 0)
# id, from, subject, verdict, source
msgs = [(21, "email:pat@example.test", "Shed day options", "task", "Pat asks which day works"),
        (22, "email:lee@example.test", "Paint colours", "task", "Lee sends paint colours"),
        (23, "email:ship@store.example.test", "Your parcel moved", "noise", "a routine shipping notice"),
        (24, "email:sam@example.test", "Thanks", "task", "Sam says thanks"),
        (25, "email:deals@shop.example.test", "Sale ends soon", "noise", "rule:559"),
        (26, "email:spam@nowhere.example.test", "Hello again", "ignore", "owner:ignore"),
        (27, "email:news@letters.example.test", "Weekly letter", "noise", "fast: a weekly newsletter"),
        (28, "email:shop@paint.example.test", "Shed paint in stock", "noise", "owner rule 3: hide mail from the paint shop")]
con = db.connect()
for mid, fk, subj, verdict, source in msgs:
    con.execute("INSERT INTO messages (id, channel, account, ts, direction, from_key, subject, body, ingested_at)"
                " VALUES (?, 'email', 'me@example.test', ?, 'in', ?, ?, ?, ?)", (mid, ts, fk, subj, subj + ", made up.", ts))
    con.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES ('judged', ?, ?, ?, ?)",
                (f"msg:{mid}", verdict, source, ts))
# open tasks: one from before the messages came in, the one message 21 itself made, one made later from nothing here
for key, at in (("personal::older", dt.datetime(2026, 11, 20, 8, 0)), ("personal::shed-day", dt.datetime(2026, 11, 23, 9, 0)),
                ("personal::later", dt.datetime(2026, 11, 24, 8, 0))):
    con.execute("INSERT INTO tasks (item_key, area, title, detail, status, created_at, updated_at) VALUES"
                " (?, 'Personal', 'Made up', 'made-up detail', 'needs_me', ?, ?)", (key, at, at))
con.execute("INSERT INTO task_refs (task_id, kind, ref_type, value, role) SELECT id, 'cites', 'message', '21', 'source'"
            " FROM tasks WHERE item_key = 'personal::shed-day'")
# what he settled: before the messages, about message 22 itself, and after the messages came in
for key, at in (("L1", dt.datetime(2026, 11, 22, 8, 0)), ("msg:22", dt.datetime(2026, 11, 22, 9, 0)),
                ("L9", dt.datetime(2026, 11, 24, 8, 0))):
    con.execute("INSERT INTO answered (domain, key, verdict, source, answered_at) VALUES ('card', ?, 'done', 'made up', ?)",
                (key, at))
con.close()
common.write_json(common.ITEMS_JSON, {"items": [{"id": "L1", "title": "Pick a shed day"}]})
items.upsert("task:personal::shed-day", "made-up-pass", title="Pick a shed day", kind="task", area="Personal", state="question")
common.write_json(filters.RULES_FILE, {"rules": [{"id": 3, "text": "Hide mail from the paint shop", "way": "show_less",
                                                  "on": True, "made": "2026-11-20", "from": "made up"}], "next": 4})
common.write_json(os.path.join(common.HOME, "held.json"), {"days": [{"rows": [{"key": "held-25", "who": "Shop"}]}]})
os.makedirs(os.path.join(common.paths.STATE, "items"), exist_ok=True)
common.write_json(os.path.join(common.paths.STATE, "items", "personal-shed-day.json"), {"item_key": "personal::shed-day"})

# the rule book: one press per message, the call read from its verdict the way the presses do
press = {21: ("not_needed", "not-needed"), 22: ("always_show", "needed"), 23: ("should_have_seen", "contradicts-hide"),
         24: ("got_it", "neutral"), 25: ("should_have_seen", "contradicts-hide"), 26: ("not_needed", "not-needed"),
         27: ("should_have_seen", "contradicts-hide"), 28: ("should_have_seen", "contradicts-hide")}
for mid, fk, subj, verdict, source in msgs:
    call, layer, rules = rule_book.call_of(verdict, source)
    card = {"id": f"L{mid}", "kind": "task", "area": "Personal", "title": subj}
    rule_book.on_press(card, press[mid][0], press[mid][1], when=f"2026-11-24T09:{mid}:00",
                       calls={str(mid): {"call": call, "layer": layer, "verdict": verdict, "source": source, "rules": rules,
                                         "seen": {"sender": fk.split(":")[1], "what": subj, "channel": "email"},
                                         **({"covered": False, "leaned_on": "made-up words on parcels"} if mid == 23 else {})}})
out["rows"] = sorted((r["message"], r["section"], r["layer"], r["call"]) for r in rule_book.rows())


def snapshot():
    files = {}
    for top, dirs, names in os.walk(common.HOME):
        rel = os.path.relpath(top, common.HOME).replace("\\", "/")
        if rel == "state/rsi" or rel.startswith("state/rsi/") or rel.startswith("logs"):
            continue
        for n in names:
            if n.endswith((".duckdb", ".wal", ".lock")):
                continue
            with open(os.path.join(top, n), "rb") as f:
                files[rel + "/" + n] = hashlib.sha1(f.read()).hexdigest()
    tables = {t: db.query(f"SELECT * FROM {t} ORDER BY 1") for t in ("answered", "tasks", "messages", "live_items")}
    assert tables["live_items"], "a card is on file to watch"
    return {"files": files, "tables": json.dumps(tables, default=str), "daily runs": settings_page.runs_today()}


calls = []
VERDICTS = {"21": "noise", "22": "task", "23": "noise", "28": "noise"}


def stub(prompt, model, expect, payload):
    got = json.load(open(payload, encoding="utf-8"))
    ids = sorted(str(m["id"]) for m in got["messages"])
    first = "says" in got["messages"][0]
    calls.append({"layer": "first_sort" if first else "judge", "model": model, "ids": ids,
                  "draft rule": "Show every message about the shed paint" in prompt,
                  "live rule": "Hide mail from the paint shop" in prompt,
                  "records": [t["full_record"]["path"] if isinstance(t.get("full_record"), dict) else t.get("full_record")
                              for t in got.get("open_tasks") or []],
                  "tasks": [t["key"] for t in got.get("open_tasks") or []],
                  "settled": [s["key"] for s in got.get("already_settled") or []]})
    if first:
        common.write_json(expect, {"nothing": []})
    else:
        v = dict(VERDICTS)
        if "Show every message about the shed paint" in prompt:
            v["28"] = "task"
        noise = [int(i) for i in ids if v.get(i) == "noise" and i != "28"]
        out = [{"ids": noise, "disposition": "noise", "reason": "made-up routine mail", "covered": False,
                "leaned_on": "nothing on routine mail"}]
        out += [{"id": int(i), "disposition": v[i], "reason": f"made-up reason for {i}"} for i in ids if i not in [str(n) for n in noise]]
        common.write_json(expect, {"payload": payload, "verdicts": out})
    return type("R", (), {"ok": True, "why": ""})()


before = snapshot()
live = grader.grade(runner=stub)
draft = grader.grade(rules_file=draft_file, runner=stub)
after = snapshot()

out["1. live: X of N per section"] = {k: v["line"] for k, v in live["sections"].items()}
out["1. each graded row: signal, wanted, now, matched"] = sorted(
    (r["message"], r["signal"], r["wanted"], r["call_now"], r["matched"]) for r in live["rows"])
out["2. neutral rows not counted"] = [live["neutral"], "24" in [r["message"] for r in live["rows"]]]
p = next(r for r in live["rows"] if r["message"] == "25")
i = next(r for r in live["rows"] if r["message"] == "26")
out["3. program layer: not rerun, graded from the call, names its setting or list"] = [
    p["rerun"], p["call_now"], p["decided_by"]["layer"], p["decided_by"]["source"], bool(p["decided_by"]["what"]),
    i["rerun"], i["decided_by"]["layer"], i["decided_by"]["source"], i["matched"]]
out["3. the runs: one per layer batch, the layer's model, no program-layer message sent"] = [
    (c["layer"], c["model"], c["ids"]) for c in calls[:2]]
m = next(x for x in live["sections"]["page"]["misses"] if x["message"] == "23")
out["4. a miss beside what he did and the layer's reason"] = [m["user"]["press"], m["user"]["meaning"], m["call_now"],
                                                            m["wanted"], m["reason"]]
pm = next(x for x in live["sections"]["mailings"]["misses"] if x["message"] == "25")
out["4. the judge's coverage mark kept on a miss, as recorded and as rerun; a program-layer miss has none"] = [
    m["covered_was"], m["leaned_on_was"], m["covered"], m["leaned_on"], pm["covered_was"], pm.get("covered")]
out["5. draft rules: told the draft, not the live rules; the live run was told the live ones"] = [
    [(c["layer"], c["draft rule"], c["live rule"]) for c in calls], {k: v["line"] for k, v in draft["sections"].items()},
    draft["rules"].startswith("draft: ")]
out["6. nothing live changed during the grades"] = [before == after,
                                                   sorted(set(before["files"]) ^ set(after["files"])),
                                                   [k for k in before["files"] if before["files"][k] != after["files"].get(k)]]
recs = [r for c in calls for r in c["records"]]
out["6. the open tasks' records went to the grader's own folder"] = [len(recs), all(
    os.path.normpath(str(r)).startswith(os.path.normpath(os.path.join(common.paths.STATE, "rsi"))) for r in recs)]
out["2. leakage: the rebuilt payload has the task from before, not the message's own task or a later one, nor what he settled about it or after"] = [
    calls[0]["tasks"], calls[0]["settled"], sorted(os.listdir(os.path.join(grader.WORK, "items")))]
out["7. score history: a line per section per grade"] = [(x["section"], x["matched"], x["graded"], x["rules"])
                                                         for x in grader.scores()]
out["7. the grades are on file, the RSI runs counted apart"] = [os.path.exists(live["file"]), os.path.exists(draft["file"]),
                                                                common.read_json(grader.RUNS, {}).get("runs")]
print(json.dumps(out, default=str))
'''

WANT = {
    "4. the judge's coverage mark kept on a miss, as recorded and as rerun; a program-layer miss has none": [
        False, "made-up words on parcels", False, "nothing on routine mail", None, None],
    "2. leakage: the rebuilt payload has the task from before, not the message's own task or a later one, nor what he settled about it or after": [
        ["personal::older"], ["L1"], ["personal-older.json"]],
    "rows": [["21", "page", "judge", "show"], ["22", "page", "judge", "show"], ["23", "page", "judge", "hide"],
             ["24", "page", "judge", "show"], ["25", "mailings", "setting", "hide"], ["26", "page", "ignore_list", "hide"],
             ["27", "mailings", "first_sort", "hide"], ["28", "page", "rule", "hide"]],
    "1. live: X of N per section": {"page": "3 of 5 matched", "mailings": "1 of 2 matched"},
    "1. each graded row: signal, wanted, now, matched": [
        ["21", "contradicts", "hide", "hide", True], ["22", "agrees", "show", "show", True],
        ["23", "contradicts", "show", "hide", False], ["25", "contradicts", "show", "hide", False],
        ["26", "agrees", "hide", "hide", True], ["27", "contradicts", "show", "show", True],
        ["28", "contradicts", "show", "hide", False]],
    "2. neutral rows not counted": [1, False],
    "3. program layer: not rerun, graded from the call, names its setting or list": [
        False, "hide", "setting", "rule:559", True, False, "ignore_list", "owner:ignore", True],
    "3. the runs: one per layer batch, the layer's model, no program-layer message sent": [
        ["judge", "opus", ["21", "22", "23", "28"]], ["first_sort", "haiku", ["27"]]],
    "4. a miss beside what he did and the layer's reason": ["should_have_seen", "contradicts-hide", "hide", "show",
                                                           "noise: made-up routine mail"],
    "5. draft rules: told the draft, not the live rules; the live run was told the live ones": [
        [["judge", False, True], ["first_sort", False, True], ["judge", True, False], ["first_sort", True, False]],
        {"page": "4 of 5 matched", "mailings": "1 of 2 matched"}, True],
    "6. nothing live changed during the grades": [True, [], []],
    "6. the open tasks' records went to the grader's own folder": [2, True],
    "7. score history: a line per section per grade": [
        ["mailings", 1, 2, "live"], ["page", 3, 5, "live"], ["mailings", 1, 2, "draft"], ["page", 4, 5, "draft"]],
    "7. the grades are on file, the RSI runs counted apart": [True, True, 4],
}

# the default runner, the Claude command stood in for at the process call: the pass clock long run out, the character cap
# small, then the RSI cap reached
CLOCK = INSIDE.split("\ncalls = []")[0] + r'''
import re, subprocess, time, types
import ai_steps, think, limits
limits._state["start"] = time.time() - 100000         # a listener that has run for more than a day
refused = think._logged_call("made-up prompt", "opus", 60)
seen = []


def fake_run(cmd, input=None, timeout=None, **k):
    expect = re.search(r"Write your output file to exactly this path: (.+)$", input, re.M).group(1).strip()
    got = json.load(open(expect.replace("verdicts_", "payload_"), encoding="utf-8"))
    first = "says" in got["messages"][0]
    seen.append({"layer": "first_sort" if first else "judge", "timeout": timeout, "ids": sorted(str(m["id"]) for m in got["messages"]),
                 "chars": sum(len(m.get("body") or "") for m in got["messages"])})
    common.write_json(expect, {"nothing": []} if first else
                      {"verdicts": [{"id": m["id"], "disposition": "task", "reason": "made up"} for m in got["messages"]]})
    return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({"result": "done", "session_id": "s", "total_cost_usd": 0}),
                                       stderr="")


ai_steps.claude_exe = lambda: "claude-stand-in"
ai_steps.subprocess = types.SimpleNamespace(run=fake_run, TimeoutExpired=subprocess.TimeoutExpired)
daily = settings_page.runs_today()
grader.BATCH_CHARS = 40
r = grader.grade()
out["1. the pass clock has run out (the pass's own call refuses) and a grade still runs, each run on its own time guard"] = [
    refused.ok, refused.why, sum(s["graded"] for s in r["sections"].values()), sorted({s["timeout"] for s in seen})]
out["3. over the character cap a batch is split: each judge run within it, every message once"] = [
    [s["ids"] for s in seen if s["layer"] == "judge"], all(s["chars"] <= 40 for s in seen if s["layer"] == "judge")]
out["4. the owner's daily count is unchanged; the runs count as RSI runs"] = [daily, settings_page.runs_today(),
                                                                              grader.runs_today(), len(seen), r["runs"]]
st = common.settings()
st["rsi"] = {"daily_runs": grader.runs_today()}
common.write_json(common.SETTINGS, st)
n = len(seen)
r2 = grader.grade()
out["4. at the RSI cap a grade runs nothing"] = [r2.get("result"), len(seen) - n, grader.daily_cap()]
print(json.dumps(out, default=str))
'''

WANT_CLOCK = {
    "1. the pass clock has run out (the pass's own call refuses) and a grade still runs, each run on its own time guard": [
        False, "not started: the check was out of time", 7, [300]],
    "3. over the character cap a batch is split: each judge run within it, every message once": [
        [["21"], ["22"], ["23"], ["28"]], True],
    "4. the owner's daily count is unchanged; the runs count as RSI runs": [0, 0, 5, 5, 5],
    "4. at the RSI cap a grade runs nothing": ["not graded: I've done my learning runs for today. The rest wait until tomorrow.", 0, 5],
}

REPLAY = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
import grader
def stub(*a):
    raise AssertionError("a replay day must not run anything")
got = grader.grade(runner=stub)
print(json.dumps({"replay": got.get("replay"), "store": os.path.exists(grader.STORE)}))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def run(code, env, *args):
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", code, LIVE, *args], capture_output=True, text=True, env=env,
                       timeout=180)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1]), r
    except (ValueError, IndexError):
        return {}, r


def main():
    tmp = tempfile.mkdtemp(prefix="rsigrader-")
    try:
        draft = os.path.join(tmp, "draft_rules.json")
        with open(draft, "w", encoding="utf-8") as f:
            json.dump({"rules": [{"id": 3, "text": "Show every message about the shed paint", "way": "always_show",
                                  "on": True}]}, f)
        env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"))
        env.pop("ASSISTANT_REPLAY", None)
        got, r = run(INSIDE, env, draft)
        if r.returncode or not got:
            check("the checks ran", r.stderr.strip()[-2500:], "")
        for name, want in WANT.items():
            check(name, got.get(name), want)
        got, r = run(CLOCK, dict(env, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Clock")), draft)
        if r.returncode or not got:
            check("the clock checks ran", r.stderr.strip()[-2500:], "")
        for name, want in WANT_CLOCK.items():
            check(name, got.get(name), want)
        got, r = run(REPLAY, dict(env, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Replay"), ASSISTANT_REPLAY="1"))
        if r.returncode or not got:
            check("the replay check ran", r.stderr.strip()[-2500:], "")
        check("8. a replay day grades nothing and writes nothing", got, {"replay": True, "store": False})
    finally:
        _cleanup.remove(tmp)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
