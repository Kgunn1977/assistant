r"""Acceptance: Start fresh (the RSI plan, "Start fresh"; ITEMS.md "Start fresh"). In a scratch home with made-up rules,
lists and senders; nothing outside the scratch folder is touched, nothing goes to Claude.

1. A Start fresh press without the confirm, one that reached no listener (picked up by apply_files, as a pass does), and
   a confirmed one a listener finds hours late delete nothing; the missed ones are said so.
2. The confirmed press, handed to the engine as the listener hands it (answers.act_on_answer), deletes every personal
   store outright: voice.json and the drafts of his rules documents are gone, filter_rules.json is left with no rules and
   its next number; his lists are out of personal.json and settings.json and his entries out of the rules documents. No
   To Delete folder is made anywhere.
3. Core rules (Goals.md and Junk rules 559-562 and 631, in the program's own folder, never in a home) are unchanged and
   still read; README's next number, the rule book, RSI versions and state, standing approvals, Important.md, taught
   guardrails and every setting choice are unchanged.
4. A second run deletes nothing and writes nothing. A folder that is not an assistant home is refused.
5. The page's code (picked out of page.html, run under node): Start fresh asks the exact question first; only Yes sends one
   press, carrying the confirm; No sends nothing.
6. Nothing but answers.py reaches start_fresh.py: no pass, setup, update, chat or desk file names it, and chat's page
   buttons do not hold it.

    python tests\start_fresh_acceptance.py
"""
import datetime as dt
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

import _cleanup  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
PAGE_DIR = os.path.join(os.path.dirname(HERE), "engine", "System", "live_page")
PAGE = os.path.join(PAGE_DIR, "page.html")
results = []

OWNER_JUNK_RULE = "- [701] (G9) A mailing from a garden shop example is junk."
OWNER_WAITING = ["- [702] (proposed 2026-11-20 09:00, for Rules) A raffle notice example is junk.",
                 "  You said: raffles are never for me"]
OWNER_SENDERS = ["- [703] from `deals.example.com`: named in setup", "- [704] from `pat@example.org`: Pat Example, never junk"]
OWNER_READING = "- [705] (G1) A note from the made-up choir example is an FYI."

PRESS = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
import common, db, answers
db.init_schema()
out = {}
out["bare"] = answers.act_on_answer({"id": "start-fresh", "action": "answer", "at": "2026-11-25T09:00:00", "text": ""})["result"]
out["wrong"] = answers.act_on_answer({"id": "start-fresh", "action": "answer", "at": "2026-11-25T09:00:10",
                                      "text": json.dumps({"start_fresh": "yes"})})["result"]
os.makedirs(common.ANSWERS_APPLIED, exist_ok=True)     # as answers._save makes it
common.write_json(os.path.join(common.ANSWERS, "start-fresh-1-0001.json"),
                  {"id": "start-fresh", "action": "answer", "at": "2026-11-25T09:01:00", "text": json.dumps({"start_fresh": "confirmed"})})
applied, problems, changed = answers.apply_files()
out["missed"] = problems
out["missed_left"] = [os.path.basename(p) for p in os.listdir(common.ANSWERS) if p.endswith(".json")]
import datetime as dt
old = (dt.datetime.now() - dt.timedelta(hours=3)).isoformat(timespec="seconds")
out["stale"] = answers.act_on_answer({"id": "start-fresh", "action": "answer", "at": old,
                                      "text": json.dumps({"start_fresh": "confirmed"})})["result"]
out["to_delete_before"] = os.path.isdir(os.path.join(common.paths.HOME, "To Delete"))
out["said"] = answers.act_on_answer({"id": "start-fresh", "action": "answer", "at": dt.datetime.now().isoformat(timespec="seconds"),
                                     "text": json.dumps({"start_fresh": "confirmed"})})["result"]
print(json.dumps(out))
'''

AGAIN = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
import start_fresh
out = {"again": start_fresh.start_fresh(sys.argv[2])}
try:
    start_fresh.start_fresh(sys.argv[3])
    out["refused"] = False
except ValueError as e:
    out["refused"] = str(e).startswith("not an assistant home")
print(json.dumps(out))
'''

NODE = r'''
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8").replace(/\r\n/g, "\n");
const pick = (name) => { const i = src.indexOf("  function " + name + "("); if (i < 0) throw new Error("no function " + name);
  let d = 0, j = src.indexOf("{", i); for (; j < src.length; j++) { if (src[j] === "{") d++; else if (src[j] === "}" && --d === 0) break; } return src.slice(i, j + 1); };
const S = {ans: {}, db: {posts: [], setAnswer: function (k, r) { this.posts.push({key: k, rec: r}); return Promise.resolve(); }}};
function h(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
function isoLocal() { return "2026-11-25T09:00:00"; }
const device = "test";
function render() {}
eval(src.slice(src.indexOf("  var FRESH = {"), src.indexOf("\n", src.indexOf("  var FRESH = {"))));
eval(pick("freshLine"));
const a0 = src.indexOf("    if (a === 'fresh-ask')"), a1 = src.indexOf("    if (a === 'reb-no')", a0);
eval("function click(a) {\n" + src.slice(a0, a1) + "}");
const out = {};
out.first = freshLine();
click("fresh-ask"); out.asked = freshLine(); out.postsAsked = S.db.posts.length;
click("fresh-no"); out.no = freshLine(); out.postsNo = S.db.posts.length;
click("fresh-ask"); click("fresh-go"); out.posts = S.db.posts.map((p) => ({key: p.key, id: p.rec.id, action: p.rec.action, text: p.rec.text}));
S.ans["start-fresh"] = {status: "done", result: "Started fresh: 7 of your own rule stores deleted."};
out.after = freshLine();
out.inRuleBook = (pick("rbBlock").match(/freshLine\(\)/g) || []).length;
console.log(JSON.stringify(out));
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def run(code, env, *args):
    r = subprocess.run([sys.executable, "-X", "utf8", "-c", code, LIVE, *args], capture_output=True, text=True, env=env, timeout=180,
                       encoding="utf-8")
    try:
        return json.loads(r.stdout.strip().splitlines()[-1]), r
    except (ValueError, IndexError):
        return {}, r


def put(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj, indent=1))


def text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def digest(paths_):
    h = hashlib.sha256()
    for p in paths_:
        for f in sorted(glob.glob(os.path.join(p, "**", "*"), recursive=True)) if os.path.isdir(p) else [p]:
            if os.path.isfile(f):
                h.update(f.encode("utf-8"))
                with open(f, "rb") as fh:
                    h.update(fh.read())
    return h.hexdigest()


def listing(root):
    return sorted(os.path.relpath(f, root) for f in glob.glob(os.path.join(root, "**", "*"), recursive=True))


def make_home(home):
    """A made-up home: the starter's rules and data as setup copies them, then his own rules and lists on top."""
    starter = os.path.join(LIVE, "starter")
    for sub in ("Rules", "Data"):
        shutil.copytree(os.path.join(starter, sub), os.path.join(home, "Resources", sub))
    rules = os.path.join(home, "Resources", "Rules")
    jr = os.path.join(rules, "Junk rules.md")
    put(jr, text(jr).rstrip("\n") + "\n" + OWNER_JUNK_RULE + "\n\n## Waiting for your OK\n\n" + "\n".join(OWNER_WAITING) + "\n")
    js = os.path.join(home, "Resources", "Data", "Junk senders.md")
    put(js, text(js).replace("Settled before the judge reads anything.\n", "Settled before the judge reads anything.\n\n" + OWNER_SENDERS[0] + "\n")
        .replace("No junk rule may touch these.\n", "No junk rule may touch these.\n\n" + OWNER_SENDERS[1] + "\n"))
    put(os.path.join(rules, "Reading messages.md"), "# Reading messages\n\nRead by the judge.\n\n## Rules\n\n" + OWNER_READING + "\n")
    put(os.path.join(rules, "Draft", "Junk rules.md"), text(jr))
    p = os.path.join(home, "personal")
    put(os.path.join(p, "filter_rules.json"), {"rules": [
        {"id": 3, "text": "Show less of the made-up seed catalog mail.", "way": "show_less", "on": True, "made": "2026-11-01T08:00:00",
         "from": "card", "reason": "never ordered seeds"},
        {"id": 7, "text": "Cards about the example choir say the rehearsal day first.", "way": "card_rule", "on": True,
         "made": "2026-11-02T08:00:00", "from": "card"}], "next": 9})
    put(os.path.join(p, "voice.json"), {"learned": {"greetings": ["Hi"]}, "owner": {"never": ["Circling back"]}})
    put(os.path.join(p, "personal.json"), {"owner": "Pat", "full_name": "Pat Example", "private_words": ["Example Co"],
                                           "own_domains": ["example.net"], "ignore_senders": ["promo.example.com"],
                                           "keep_words": ["warranty"], "company_words": ["fence"]})
    put(os.path.join(p, "settings.json"), {"filter": {"strict": "needs_me", "newsletters": "never",
                                                      "always_through": ["Lee Example", "boss@example.net"]},
                                           "voice": {"level": "casual"}, "rsi": {"levels": {"page": 2}}})
    put(os.path.join(p, "rule_book.jsonl"), json.dumps({"id": "r1", "message": "11", "rules": [3]}) + "\n")
    put(os.path.join(p, "rsi_versions", "v-1.json"), {"kind": "version", "rules": [{"id": 3}]})
    put(os.path.join(p, "standing.json"), {"kinds": {"reply": "ask"}})
    put(os.path.join(p, "Important.md"), "- a made-up water leak alarm\n")
    put(os.path.join(home, "state", "rsi", "draft_rules.json"), {"rules": [{"id": 3}]})
    put(os.path.join(home, "taught", "rules", "extra.json"), {"rules": [{"id": "a90", "guard": "a"}]})


def main():
    tmp = tempfile.mkdtemp(prefix="startfresh-")
    try:
        home = os.path.join(tmp, "Live")
        make_home(home)
        kept = [os.path.join(home, "personal", n) for n in ("rule_book.jsonl", "rsi_versions", "standing.json", "Important.md")] + \
               [os.path.join(home, "Resources", "Rules", n) for n in ("README.md", "Changelog.md")] + \
               [os.path.join(LIVE, "core_rules")] + \
               [os.path.join(home, "state", "rsi"), os.path.join(home, "taught"), os.path.join(home, "Resources", "Data", "Reference.md")]
        before_kept = digest(kept)
        originals = {rel: text(os.path.join(home, *rel)) for rel in (
            ("personal", "filter_rules.json"), ("personal", "voice.json"), ("personal", "personal.json"), ("personal", "settings.json"),
            ("Resources", "Rules", "Junk rules.md"), ("Resources", "Data", "Junk senders.md"), ("Resources", "Rules", "Reading messages.md"),
            ("Resources", "Rules", "Draft", "Junk rules.md"))}
        env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
        env.pop("ASSISTANT_REPLAY", None)
        got, r = run(PRESS, env)
        if r.returncode or not got:
            check("the engine ran", r.stderr.strip()[-2500:], "")
            return finish()
        check("1. a press without the confirm deletes nothing", [got["bare"], got["wrong"]],
              ["Not done: Start fresh needs your yes to its question first. Nothing was deleted."] * 2)
        check("1. a press that reached no listener is refused by apply_files (as a pass runs it), said so, and deletes nothing",
              [any(p.startswith("Not done: this page couldn't reach your computer when you pressed Start fresh") for p in got["missed"]),
               got["missed_left"]], [True, []])
        check("1. a confirmed press a listener finds hours later (it was off) is refused the same way; no To Delete folder before the live press",
              [got["stale"].startswith("Not done: this page couldn't reach your computer"), got["to_delete_before"]], [True, False])
        check("2. the confirmed press says what it did", got["said"],
              "Started fresh: I deleted 8 of your own sets of personal rules and lists. The core rules (how the system works, the built-in ones and yours), the rule book and your cards stay.")

        # wholly personal files: deleted outright
        fr = json.loads(text(os.path.join(home, "personal", "filter_rules.json")))
        check("2. filter_rules.json holds no rules and keeps its next rule number", fr, {"rules": [], "next": 9})
        check("2. voice.json and the draft of a rules document are deleted from the home",
              [os.path.exists(os.path.join(home, "personal", "voice.json")),
               os.path.exists(os.path.join(home, "Resources", "Rules", "Draft", "Junk rules.md"))], [False, False])
        check("2. no To Delete folder is made anywhere",
              [d for d, _sub, _f in os.walk(tmp) if os.path.basename(d) == "To Delete"], [])

        # shared files: his entries out
        me = json.loads(text(os.path.join(home, "personal", "personal.json")))
        st = json.loads(text(os.path.join(home, "personal", "settings.json")))
        check("2. personal.json loses only ignore_senders and keep_words; settings.json only filter.always_through; every choice stays",
              [sorted(me), st], [sorted(["owner", "full_name", "private_words", "own_domains", "company_words"]),
                                 {"filter": {"strict": "needs_me", "newsletters": "never"}, "voice": {"level": "casual"},
                                  "rsi": {"levels": {"page": 2}}}])
        jr, js, rd = (text(os.path.join(home, *rel)) for rel in (("Resources", "Rules", "Junk rules.md"), ("Resources", "Data", "Junk senders.md"),
                                                                 ("Resources", "Rules", "Reading messages.md")))
        core_jr = text(os.path.join(LIVE, "core_rules", "Junk rules.md"))
        core_lines = [ln for ln in core_jr.split("\n") if ln.startswith("- [")]
        his = [OWNER_JUNK_RULE] + OWNER_WAITING + OWNER_SENDERS + [OWNER_READING]
        check("2. his entries (with their You said line) are out of the rules documents and headings stay; the core rules 559-562 "
              "and 631 were never in the home (the program holds them)",
              [[x for x in his if x in jr + js + rd], [ln for ln in core_lines if ln in originals[("Resources", "Rules", "Junk rules.md")]],
               len(core_lines), all(s in js for s in ("## Always junk", "## Never junk", "Settled before the judge reads anything.")),
               "Goals.md" in os.listdir(os.path.join(home, "Resources", "Rules"))], [[], [], 5, True, False])
        check("3. core rules (the program's own folder), README's next number, Changelog, Reference, the rule book, RSI versions "
              "and state, standing approvals, Important.md and taught guardrails are unchanged", digest(kept), before_kept)

        snap = listing(home)
        again, r2 = run(AGAIN, env, home, os.path.join(tmp, "not-a-home"))
        if r2.returncode or not again:
            check("the second run ran", r2.stderr.strip()[-2500:], "")
            return finish()
        check("4. a second run deletes nothing and writes nothing", [again["again"]["moved"], again["again"]["record"], listing(home) == snap],
              [[], None, True])
        check("4. a folder that is not an assistant home is refused", again["refused"], True)

        n = subprocess.run(["node", "-e", NODE, PAGE], capture_output=True, text=True, timeout=60, encoding="utf-8")
        try:
            pg = json.loads(n.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            check("the page's code ran under node", n.stderr[-1500:], "")
            return finish()
        q = "This deletes your personal rules and lists. The core rules (how the system works, the built-in ones and yours), the rule book and your cards stay. Continue?"
        check("5. Start fresh first only asks; the question is the exact words with Yes and No; nothing is sent",
              ["data-s=\"fresh-ask\"" in pg["first"], q in pg["first"], q in pg["asked"], "data-s=\"fresh-go\"" in pg["asked"],
               "data-s=\"fresh-no\"" in pg["asked"], pg["postsAsked"]], [True, False, True, True, True, 0])
        check("5. No closes the question and sends nothing", [q in pg["no"], pg["postsNo"]], [False, 0])
        check("5. Yes sends one press carrying the confirm; its result shows; it sits in the Rule book part (both states)",
              [pg["posts"], "Started fresh:" in pg["after"], pg["inRuleBook"]],
              [[{"key": "start-fresh", "id": "start-fresh", "action": "answer", "text": json.dumps({"start_fresh": "confirmed"}, separators=(",", ":"))}],
               True, 2])

        names = {}
        for f in glob.glob(os.path.join(LIVE, "**", "*.py"), recursive=True) + glob.glob(os.path.join(PAGE_DIR, "*.py")):
            t = text(f)
            if "start_fresh" in t or "start-fresh" in t:
                names[os.path.relpath(f, LIVE)] = sorted({w for w in ("start_fresh(", "import start_fresh", "start-fresh") if w in t})
        chat_src = text(os.path.join(LIVE, "chat.py"))
        buttons = chat_src[chat_src.index("PAGE_BUTTONS = {"):chat_src.index("PAGE_WORDS = {")]
        check("6. only answers.py reaches start_fresh.py (no pass, setup, update, chat or desk file names it); chat cannot press it",
              [names, "start-fresh" in buttons], [{"answers.py": ["import start_fresh", "start-fresh"],
                                                  "start_fresh.py": ["start_fresh("]}, False])
    finally:
        _cleanup.remove(tmp)
    return finish()


def finish():
    bad = [r for r in results if not r[1]]
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name)
        if not ok:
            print("   got:  " + json.dumps(got)[:1500])
            print("   want: " + json.dumps(want)[:1500])
    print(f"\n{len(results) - len(bad)}/{len(results)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
