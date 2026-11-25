r"""Acceptance: the RSI defaults (the RSI plan, "Nothing hidden at the start", "Start fresh"; ITEMS.md H10 and the Start fresh
store map). The program is copied into a scratch folder and the setup helper is run there as the setup skill runs it; every
home is made up, nothing outside the scratch folder is touched, and nothing goes to Claude.

a. A new home made by setup starts on strictness show_more (with newsletters, notices, copied-only and short-number texts
   shown); a made-up newsletter is settled by no junk rule, held by no setting, and the sorting step is told to show more and
   to read mailings like any other mail.
b. Setup step 4 asks no junk senders and no kinds of message never to show: answers to either are refused with plain words
   and write no junk line and no show-less rule; skipping them is fine.
c. The core rules (Goals.md, Junk rules 559-562 and 631) are read from the program's own folder: no copy is in the new home,
   the judge's payload carries them and the goals, the card writer's goals are the program's, and nothing removes one; the
   owner's own rule lands in his home and the program's copy is unchanged.
d. Start fresh on that home deletes only the home's own rule stores; the program's core rules are unchanged and
   still read.
e. A home made before, with its own saved settings and old copies of the core rules (an old Goals.md too), keeps its settings
   byte for byte when setup brings it forward; its old copies are not read (the program's are, once each); start fresh deletes
   those copies with its own rules and leaves its Goals.md.

    python tests\rsi_defaults_acceptance.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

import _cleanup  # noqa: E402  the scratch folder goes when the test ends

HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEM = os.path.join(os.path.dirname(HERE), "engine", "System")
results = []

# --- the new home, after setup made it -------------------------------------------------------------------------------
NEW = r'''
import datetime as dt, hashlib, json, os, sys
live = sys.argv[1]
sys.path.insert(0, live)
import common, db, filters
sys.path.insert(0, common.paths.CORE)
import rules, judgment_payload as jp
CORE = os.path.join(live, "core_rules")
def digest():
    h = hashlib.sha256()
    for n in sorted(os.listdir(CORE)):
        h.update(n.encode()); h.update(open(os.path.join(CORE, n), "rb").read())
    return h.hexdigest()
def entries(folder):
    out = []
    for n in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        p = os.path.join(folder, n)
        if n.endswith(".md") and os.path.isfile(p):
            out += [n + ": " + ln for ln in open(p, encoding="utf-8").read().split("\n") if ln.startswith("- [")]
    return out
core_before = digest()
out = {}
f = filters.get()
out["a.settings"] = [f[k] for k in ("strict", "newsletters", "notices", "copied_only", "short_texts")]
ts = dt.datetime(2026, 11, 23, 8, 0)
con = db.connect()
con.execute("INSERT INTO messages (id, channel, account, ts, direction, from_key, subject, body, ingested_at)"
            " VALUES (41, 'email', 'me@example.test', ?, 'in', 'email:news@garden.example.test', 'Garden club newsletter', ?, ?)",
            (ts, '<p>Spring bulbs are in at the made-up garden club.</p><a href="https://garden.example.test/unsubscribe">Unsubscribe</a>', ts))
con.close()
out["a.newsletter"] = [[m for m, _r in jp.junk_rule_hits()], [m for m, _s in filters.holds(db, lambda fk: False)]]
jp.prefilter_noise()
out["a.after the junk step"] = db.query("SELECT verdict FROM answered WHERE key = 'msg:41'")
lines = filters.lines_for_sorting()
out["a.sorting"] = [any(l.startswith("[setting strict] How strict: show more") for l in lines), any(l.startswith("[setting newsletters] Mailings:") for l in lines)]

out["c.home"] = [sorted(os.listdir(common.paths.RULES)), entries(common.paths.RULES) + entries(common.paths.DATA)]
out["c.core read"] = [[e["id"] for e in rules.parse("junk") if e["core"]], rules.goals() == open(os.path.join(CORE, "Goals.md"), encoding="utf-8").read().strip(),
                      os.path.dirname(common.paths.GOALS) == CORE]
p = jp.build([], ids=[41])
ids = sorted(i for r in p["active_rules"] for i in ([r["id"]] if "id" in r else r["ids"]))
out["c.judge payload"] = [ids, p["goals"].startswith("# Goals") and "[G9]" in p["goals"]]
out["c.no change to a core rule"] = [rules.delete(559), rules._remove(631), [e["id"] for e in rules.parse("junk") if e["core"]]]
rid = rules.add("junk", "(G9) A made-up raffle notice from the example school is junk.")
rules.add("reading", "(G1) A note from the made-up choir is an FYI.")
filters.add_rule("Show less of the made-up seed catalog mail.", "show_less", source="card")
out["c.his rule lands in his home"] = [rid > 631, [x.split(": ", 1)[0] for x in entries(common.paths.RULES)],
                                       sorted(e["id"] for e in rules.parse("junk"))[:5]]
out["c.program copy unchanged"] = digest() == core_before

import start_fresh
got = start_fresh.start_fresh(common.paths.HOME)
out["d.moved"] = sorted(m["file"].replace("\\", "/") for m in got["moved"])
out["d.after"] = [entries(common.paths.RULES), filters.rules(), [e["id"] for e in rules.parse("junk")], digest() == core_before,
                  sorted(i for r in jp.judge_rules() for i in ([r["id"]] if "id" in r else r["ids"]))]
print(json.dumps(out, default=str))
'''

# --- a home made before -------------------------------------------------------------------------------------------------
OLD = r'''
import json, os, sys
live = sys.argv[1]
sys.path.insert(0, live)
import common, setup_steps
setup_steps.desktop_note = lambda: None
os.makedirs(common.PERSONAL, exist_ok=True)
common.write_json(common.PERSONAL_JSON, dict(common.STARTER, owner="Sam"))
common.write_json(common.SETTINGS, {"filter": {"newsletters": "never", "notices": "only_failed"}, "voice": {"level": "casual"}})
import db
db.init_schema()
os.makedirs(common.paths.RULES, exist_ok=True)
core_jr = open(os.path.join(live, "core_rules", "Junk rules.md"), encoding="utf-8").read()
with open(os.path.join(common.paths.RULES, "Junk rules.md"), "w", encoding="utf-8", newline="\n") as f:     # as an older setup copied it
    f.write(core_jr.replace("- [631]", "- [650] (G9) A made-up club mailing is junk.\n- [631]"))
with open(os.path.join(common.paths.RULES, "Goals.md"), "w", encoding="utf-8", newline="\n") as f:
    f.write("# Goals\n\n- [G1] A made-up old goal of this home.\n")
before = open(common.SETTINGS, "rb").read()
setup_steps.make_home()
import filters
sys.path.insert(0, common.paths.CORE)
import rules, judgment_payload as jp, start_fresh
f = filters.get()
out = {"e.settings": [[f[k] for k in ("strict", "newsletters", "notices")], open(common.SETTINGS, "rb").read() == before]}
ids = [e["id"] for e in rules.everything()]
out["e.read"] = [sorted(ids), [e["id"] for e in rules.parse("junk") if not e["core"]], "made-up old goal" in rules.goals(),
                 sorted(i for r in jp.judge_rules() for i in ([r["id"]] if "id" in r else r["ids"]))]
got = start_fresh.start_fresh(common.paths.HOME)
moved = next(m for m in got["moved"] if m["file"].endswith("Junk rules.md"))
out["e.start fresh"] = [sorted(int(x.split("]")[0][3:]) for x in moved["entries"]), os.path.exists(common.paths.GOALS),
                        os.path.exists(os.path.join(common.paths.RULES, "Goals.md")),
                        [e["id"] for e in rules.parse("junk")]]
print(json.dumps(out, default=str))
'''

CORE_IDS = [559, 560, 561, 562, 631]
NOT_ASKED = ("Not asked for now, and nothing was saved: a new assistant starts with nothing hidden and learns what to hide "
             "from your cards (the button \"I did not need this\").")
WANT = {
    "a. setup made the home": True,
    "a. a new home starts on show more, with nothing hidden by a setting": ["show_more", "show", "show_each", "show", "show"],
    "a. a made-up newsletter is settled by no junk rule and held by no setting": [[], []],
    "a. ... and the junk step leaves it for the judge": [],
    "a. ... and the sorting step is told to show more and to read mailings like any other mail": [True, True],
    "b. step 4 refuses a junk sender answer and a kinds-never-shown answer, in plain words": [[2, NOT_ASKED], [2, NOT_ASKED]],
    "b. ... skipping them is fine": 0,
    "b. ... and no junk line, show-less rule or junk answer was written": [[], [], []],
    "c. no copy of the core rules in the new home: no Goals.md, no entry in its documents": [False, []],
    "c. the core rules and goals are read from the program": [CORE_IDS, True, True],
    "c. the judge's payload carries the core rules and the goals": [CORE_IDS, True],
    "c. a core rule cannot be removed": [False, None, CORE_IDS],
    "c. his own rule lands in his home, beside the core rules read from the program": [
        True, ["Junk rules.md", "Reading messages.md"], CORE_IDS],
    "c. the program's copy is unchanged": True,
    "d. start fresh moves only the home's own rule stores": [
        "Resources/Rules/Junk rules.md", "Resources/Rules/Reading messages.md", "personal/filter_rules.json"],
    "d. ... and the core rules are untouched and still read": [[], [], CORE_IDS, True, CORE_IDS],
    "d. the program folder under test is unchanged": True,
    "e. a home made before keeps its saved settings byte for byte": [["balanced", "never", "only_failed"], True],
    "e. its old copies of the core rules are not read; the program's are, once each, beside its own rule; its old Goals.md is not read": [
        CORE_IDS + [650], [650], False, CORE_IDS + [650]],
    "e. start fresh moves its old copies with its own rule, leaves its Goals.md, and the core rules are still read": [
        CORE_IDS + [650], True, True, CORE_IDS],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def run(code, env, *args):
    r = subprocess.run([sys.executable, "-X", "utf8", *(["-c", code] if code else []), *args], capture_output=True, text=True,
                       env=env, timeout=180, encoding="utf-8")
    try:
        return json.loads(r.stdout.strip().splitlines()[-1]), r
    except (ValueError, IndexError):
        return {}, r


def digest(folder):
    h = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(folder)):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for n in sorted(files):
            if n.endswith((".pyc", ".log")):
                continue
            h.update(os.path.relpath(os.path.join(root, n), folder).encode())
            with open(os.path.join(root, n), "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


def main():
    tmp = tempfile.mkdtemp(prefix="rsidefaults-")
    try:
        shutil.copytree(SYSTEM, os.path.join(tmp, "System"), ignore=shutil.ignore_patterns("__pycache__"))
        live = os.path.join(tmp, "System", "live")
        program_before = digest(os.path.join(live, "core_rules"))
        helper = os.path.join(live, "setup", "setup_home.py")
        env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"))
        for k in ("ASSISTANT_REPLAY", "ASSISTANT_RULES_DIR", "ASSISTANT_DATA_DIR", "ASSISTANT_ENGINE"):
            env.pop(k, None)
        got = {}

        started, r = run(None, env, helper, "--root", tmp, "start")
        got["a. setup made the home"] = bool(started.get("ok")) and os.path.isdir(os.path.join(tmp, "Live", "personal"))
        if not started.get("ok"):
            check("setup's start ran", (r.stderr or r.stdout).strip()[-2500:], "")
        answers = [run(None, env, helper, "--root", tmp, "answer", q, v) for q, v in
                   (("junk_senders", '["deals@shop.example.test", "promo.example.test"]'),
                    ("junk_kinds", '["Newsletters from made-up suppliers"]'))]
        got["b. step 4 refuses a junk sender answer and a kinds-never-shown answer, in plain words"] = [
            [rr.returncode, a.get("says")] for a, rr in answers]
        _s, rs = run(None, env, helper, "--root", tmp, "skip", "junk_senders")
        got["b. ... skipping them is fine"] = rs.returncode
        home = os.path.join(tmp, "Live")
        senders = [ln for ln in open(os.path.join(home, "Resources", "Data", "Junk senders.md"), encoding="utf-8").read().split("\n")
                   if ln.startswith("- [")]
        fr_path = os.path.join(home, "personal", "filter_rules.json")
        fr = json.load(open(fr_path, encoding="utf-8")).get("rules", []) if os.path.exists(fr_path) else []
        rec = json.load(open(os.path.join(home, "personal", "setup.json"), encoding="utf-8"))
        got["b. ... and no junk line, show-less rule or junk answer was written"] = [
            senders, fr, [k for k in list(rec.get("answers", {})) + list(rec.get("skipped", [])) if k.startswith("junk")]]
        got["c. no copy of the core rules in the new home: no Goals.md, no entry in its documents"] = None   # filled below

        new, r = run(NEW, env, live)
        if not new:
            check("the new home's checks ran", (r.stderr or r.stdout).strip()[-2500:], "")
        else:
            got["a. a new home starts on show more, with nothing hidden by a setting"] = new["a.settings"]
            got["a. a made-up newsletter is settled by no junk rule and held by no setting"] = new["a.newsletter"]
            got["a. ... and the junk step leaves it for the judge"] = new["a.after the junk step"]
            got["a. ... and the sorting step is told to show more and to read mailings like any other mail"] = new["a.sorting"]
            got["c. no copy of the core rules in the new home: no Goals.md, no entry in its documents"] = [
                "Goals.md" in new["c.home"][0], new["c.home"][1]]
            got["c. the core rules and goals are read from the program"] = new["c.core read"]
            got["c. the judge's payload carries the core rules and the goals"] = new["c.judge payload"]
            got["c. a core rule cannot be removed"] = new["c.no change to a core rule"]
            got["c. his own rule lands in his home, beside the core rules read from the program"] = new["c.his rule lands in his home"]
            got["c. the program's copy is unchanged"] = new["c.program copy unchanged"]
            got["d. start fresh moves only the home's own rule stores"] = new["d.moved"]
            got["d. ... and the core rules are untouched and still read"] = new["d.after"]
        got["d. the program folder under test is unchanged"] = digest(os.path.join(live, "core_rules")) == program_before

        env_old = dict(env, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Old"))
        old, r = run(OLD, env_old, live)
        if not old:
            check("the older home's checks ran", (r.stderr or r.stdout).strip()[-2500:], "")
        else:
            got["e. a home made before keeps its saved settings byte for byte"] = old["e.settings"]
            got["e. its old copies of the core rules are not read; the program's are, once each, beside its own rule; its old Goals.md is not read"] = old["e.read"]
            got["e. start fresh moves its old copies with its own rule, leaves its Goals.md, and the core rules are still read"] = old["e.start fresh"]
        for name, want in WANT.items():
            check(name, got.get(name), want)
    finally:
        _cleanup.remove(tmp)
    bad = [x for x in results if not x[1]]
    for name, ok, g, w in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"\n   got:  {json.dumps(g)[:1500]}\n   want: {json.dumps(w)[:1500]}"))
    print(f"{len(results) - len(bad)} of {len(results)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
