r"""Acceptance: learning levels and scores per section in Settings (the RSI plan, "The four parts" 4 and "Scoring"). In a scratch
home with a made-up score history; nothing outside the scratch folder is touched, nothing goes to Claude.

1. A home with no setting reads level 1 for every section; a value not understood reads 1; a 2 or a 3 reads as saved.
2. Each section's level saves through a Settings save and reads back; the RSI daily cap kept beside it is left as it was.
3. Level 3 saves and reads back like 1 and 2 (guardrail A15 as amended, approved 11/25).
4. Beside each level, its latest score from the grader's score history (live grades only, not a draft's): percent and count;
   "Not enough answers yet" with no score. The score is only in the Settings part's data, nowhere else in the page's settings.
5. The page code (picked out of page.html and run under node) draws a choice per section with Level 3 choosable,
   the score line beside it, sends the levels as numbers, and the part sits beside the Rule book under Automation.

    python tests\rsi_levels_acceptance.py
"""
import json
import os
import subprocess
import sys
import tempfile

import _cleanup  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(os.path.dirname(HERE), "engine", "System", "live")
PAGE = os.path.join(os.path.dirname(HERE), "engine", "System", "live_page", "page.html")
results = []

ENGINE = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
import common, db, settings_page, settings_data, grader
db.init_schema()
out = {}
def learn(d):
    return {x["id"]: [x["value"], x["help"]] for x in d["settings"] if x["group"] == "learning"}
out["empty"] = [settings_page.learning_levels(), settings_page.for_page()["learning"]]
d = settings_data.defs()
out["empty_defs"] = learn(d)
out["group"] = [g for g in d["groups"] if g["id"] == "learning"]
x = [x for x in d["settings"] if x["group"] == "learning"][0]
out["shape"] = [x["label"], x["control"], x["choices"], bool(x["explain"])]
out["labels"] = [x["label"] for x in d["settings"] if x["group"] == "learning"]
s = common.settings(); s["rsi"] = {"daily_runs": 12, "levels": {"mailings": "x", "bills": 3, "page": True, "calendar": 2}}
common.write_json(common.SETTINGS, s)
out["odd"] = settings_page.learning_levels()
def save(vals):
    ok, line = settings_page.save({"settings": {"group": "learning", "values": vals}})
    return [ok, line.split(": ", 1)[-1]]
allf = list(settings_page.LEARN)
out["save_all_2"] = save({f: 2 for f in allf}) + [settings_page.learning_levels(), common.settings()["rsi"].get("daily_runs")]
out["save_some_1"] = save({"learn_bills": 1, "learn_replies": 1}) + [settings_page.learning_levels()]
out["save_3"] = save({"learn_page": 3})[:1] + [settings_page.learning_levels()["page"]]
out["save_3_among"] = save({"learn_mailings": 1, "learn_page": 3})[:1] + [settings_page.learning_levels()]
save({"learn_mailings": 2, "learn_page": 2})       # back as it was, for the checks below
out["read_back"] = [x["value"] for x in settings_data.defs()["settings"] if x["group"] == "learning"]
os.makedirs(grader.STORE, exist_ok=True)
lines = [
    {"date": "2026-11-20", "at": "2026-11-20T09:00:00", "section": "page", "matched": 10, "graded": 20, "rules": "live", "grade": "a.json"},
    {"date": "2026-11-21", "at": "2026-11-21T09:00:00", "section": "page", "matched": 31, "graded": 34, "rules": "live", "grade": "b.json"},
    {"date": "2026-11-22", "at": "2026-11-22T09:00:00", "section": "page", "matched": 5, "graded": 34, "rules": "draft", "grade": "c.json"},
    {"date": "2026-11-22", "at": "2026-11-22T09:00:00", "section": "bills", "matched": 1, "graded": 1, "rules": "live", "grade": "c.json"},
    {"date": "2026-11-22", "at": "2026-11-22T09:00:00", "section": "mailings", "matched": 0, "graded": 0, "rules": "live", "grade": "c.json"},
]
with open(grader.SCORES, "w", encoding="utf-8") as f:
    f.write("".join(json.dumps(l) + "\n" for l in lines))
d = settings_data.defs()
out["scored"] = learn(d)
meta = json.dumps(settings_page.for_page())
rest = json.dumps([x for x in d["settings"] if x["group"] != "learning"] + [d["groups"], d["commands"], d["rule_book"]])
out["only_here"] = ["right, over" in meta, "right, over" in rest, "Not enough of your answers" in meta + rest]
out["defs"] = d
print(json.dumps(out))
'''

NODE = r'''
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8").replace(/\r\n/g, "\n");
const pick = (name) => { const i = src.indexOf("  function " + name + "("); if (i < 0) throw new Error("no function " + name);
  let d = 0, j = src.indexOf("{", i); for (; j < src.length; j++) { if (src[j] === "{") d++; else if (src[j] === "}" && --d === 0) break; } return src.slice(i, j + 1); };
const defs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const S = {meta: {settings_defs: defs, settings: {}}, drafts: {}, ans: {}, open: {}};
const SET = {said: {}, parts: {}};
function h(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
function hc(s) { return h(s); }
function infoBtn(t, x) { return x ? '<button class="info">i</button>' : ""; }
for (const f of ["setts", "sAll", "sOf", "sDef", "sNow", "sChoices", "sFixed", "sDraft", "sVal", "sId", "sLabel", "sPick", "sLines", "sDraw", "sOne", "sValues"]) eval(pick(f));
const out = {};
out.drawn = sOf("learning").map(sOne).join("\n");
S.drafts["set:learning"] = {learn_page: "1", learn_bills: "2", learn_replies: "2"};
out.values = sValues("learning");
out.drawn_draft = sOf("learning").map(sOne).join(" ");
out.tree = (src.match(/\{id: 'do', label: 'Automation'[^\n]*/) || [""])[0];
console.log(JSON.stringify(out));
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="rsilevels-")
    try:
        env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"))
        env.pop("ASSISTANT_REPLAY", None)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", ENGINE, LIVE], capture_output=True, text=True, env=env, timeout=180,
                           encoding="utf-8")
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            check("the engine part ran", r.stderr.strip()[-2500:], "")
            return finish()
        secs = ["mailings", "bills", "page", "calendar", "replies", "followups"]
        fields = ["learn_" + s for s in secs]
        none = "My picks: Not enough of your answers yet. Show or hide: Not enough of your answers yet."
        hide = lambda x: "My picks: Not enough of your answers yet. Show or hide: " + x + "."    # noqa: E731
        check("1. a home with no setting reads level 1 for every section, in the engine and in Settings",
              [got["empty"][0], got["empty"][1], got["empty_defs"]],
              [{s: 1 for s in secs}, {f: 1 for f in fields}, {f: [1, none] for f in fields}])
        check("1. a value not understood reads 1; a 2 or a 3 reads as saved",
              got["odd"], {"mailings": 1, "bills": 3, "page": 1, "calendar": 2, "replies": 1, "followups": 1})
        check("Settings data: the Learning levels part, a choice per section named in plain words, with its (i) words",
              [got["group"], got["labels"], got["shape"]],
              [[{"id": "learning", "label": "Learning levels", "can_save": True}],
               ["Mailings and unsubscribe", "Bills and receipts", "What reaches the page", "Calendar", "Reply drafts", "Follow-ups and clearing"],
               ["Mailings and unsubscribe", "choice", [{"value": 1, "label": "1 - You teach me on the cards"}, {"value": 2, "label": "2 - I propose, you promote or reject"},
                                                       {"value": 3, "label": "3 - Automatic, up to 10 tries"}], True]])
        check("2. every section's level saves and reads back; the RSI daily cap beside it is kept",
              got["save_all_2"][0:1] + [got["save_all_2"][1].startswith("the learning level for mailings and unsubscribe, ")] + got["save_all_2"][2:],
              [True, True, {s: 2 for s in secs}, 12])
        check("2. a second save changes only the sections it names",
              [got["save_some_1"][0], got["save_some_1"][2]],
              [True, {"mailings": 2, "bills": 1, "page": 2, "calendar": 2, "replies": 1, "followups": 2}])
        check("2. read back in Settings data", got["read_back"], [2, 1, 2, 2, 1, 2])
        check("3. Level 3 saves and reads back (alone or beside another section)",
              [got["save_3"], got["save_3_among"]],
              [[True, 3], [True, {"mailings": 1, "bills": 1, "page": 3, "calendar": 2, "replies": 1, "followups": 2}]])
        check("4. the latest live score, percent and count; a draft's grade and older grades are not it; none: Not enough answers yet",
              {k: v[1] for k, v in got["scored"].items()},
              {"learn_mailings": none, "learn_bills": hide("I got 100% right, over 1 answer of yours"),
               "learn_page": hide("I got 91% right, over 34 answers of yours"), "learn_calendar": none, "learn_replies": none, "learn_followups": none})
        check("4. the score is in the Settings part's data only", got["only_here"], [False, False, False])

        path = os.path.join(tmp, "defs.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(got["defs"], f)
        n = subprocess.run(["node", "-e", NODE, PAGE, path], capture_output=True, text=True, timeout=60, encoding="utf-8")
        try:
            pg = json.loads(n.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            check("the page's code ran under node", n.stderr[-1500:], "")
            return finish()
        d = pg["drawn"]
        check("5. the page draws a choice per section, each with its name, its (i) and the three levels",
              [d.count("<select"), [f for f in fields if 'data-set="learning.' + f + '"' in d], d.count('<button class="info">i</button>'),
               d.count(">1 - You teach me on the cards</option>"), d.count(">2 - I propose, you promote or reject</option>"), "What reaches the page</label>" in d],
              [6, fields, 6, 6, 6, True])
        check("5. Level 3 is shown and can be chosen",
              [d.count('>3 - Automatic, up to 10 tries</option>'), d.count(' disabled>'), "Not available yet" in d], [6, 0, False])
        check("5. each level shows as saved, and its score line beside it",
              [d.count('<option value="2" selected'), d.count('<option value="1" selected'),
               hide("I got 91% right, over 34 answers of yours") + '</div>' in d, d.count(none + '</div>'),
               d.count('<div class="wnote"><b>Level 2: when I miss'), d.count('<div class="wnote"><b>Level 1: I learn from everything'),
               d.count('I never promote one on my own')],
              [4, 2, True, 4, 4, 2, 4])
        check("5. the words of the level picked show under it before Save; Reply drafts never send on their own",
              [w.count('Press Save to make it take effect.') for w in [pg["drawn_draft"]]] + ["I never send a reply on my own at any level" in pg["drawn_draft"],
                                                                                        "standing approval to send" not in pg["drawn_draft"]],
              [6, True, True])
        check("5. a Save sends each level as a number, as picked",
              pg["values"], {"learn_mailings": 2, "learn_bills": 2, "learn_page": 1, "learn_calendar": 2, "learn_replies": 2, "learn_followups": 2})
        check("5. the part sits beside the Rule book under Automation", "'rulebook', 'learning']" in pg["tree"], True)
    finally:
        _cleanup.remove(tmp)
    return finish()


def finish():
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if results and all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
