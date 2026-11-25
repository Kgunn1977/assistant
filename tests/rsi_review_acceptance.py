r"""Acceptance: reviewing the rule book in Settings (the RSI plan, "The rule book's rows": Review in Settings: Keep, Edit,
Retire). In a scratch home with made-up rows and made-up senders; nothing outside the scratch folder is touched, nothing goes
to Claude.

1. With no rows, Settings data carries an empty rule book and the page shows "Nothing yet. The rule book fills as you use your
   cards."
2. Settings data carries the active rows grouped by section, in the sections' fixed order, newest first, each in plain words;
   a row still waiting for its call and a retired row are not listed.
3. The page code (picked out of page.html and run under node, as the Tools part is tested) draws the part folded by section
   with Keep, Edit and Retire on each row; pressing them sends one press each; the part is under Automation in Settings.
4. Those presses, handed to the engine as the listener hands them (answers.act_on_answer): Keep marks the row reviewed and
   leaves its answer; Edit records the owner's own answer (show or hide, a note) with the meaning it carries against the
   assistant's call; Retire takes the row out. The store only grows: every earlier line stays as it was.

    python tests\rsi_review_acceptance.py
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

SETUP = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
import common, db, settings_data, rule_book
db.init_schema()
out = {"empty": settings_data.defs()["rule_book"]}
def row(mid, at, section, call, layer, verdict, source, press, meaning, sender, what, **more):
    r = {"id": "r" + mid + at[-5:-3], "at": at, "message": mid, "section": section, "card": "L1", "card_kind": "fyi",
         "card_area": "Personal", "call": call, "layer": layer, "verdict": verdict, "source": source, "rules": [],
         "seen": {"sender": sender, "what": what, "channel": "email"}, "press": press, "meaning": meaning, "button": "-",
         "choice": "-", "status": "active"}
    r.update(more)
    return r
rule_book._append([
    row("21", "2026-11-20T09:00:00", "mailings", "hide", "setting", "noise", "rule:559", "should_have_seen", "contradicts-hide",
        "Corner Hardware", "Weekend sale on paint"),
    row("22", "2026-11-21T10:00:00", "page", "show", "judge", "task", "Pat asks about the fence", "not_needed", "not-needed",
        "Pat Example", "Fence posts"),
    row("23", "2026-11-22T11:00:00", "page", "show", "judge", "fyi", "A note about the garden club", "got_it", "neutral",
        "Garden Club", "Spring seed swap"),
    row("24", "2026-11-19T08:00:00", "bills", "show", "judge", "task", "A water bill is due", "done", "neutral",
        "Water Utility Example", "Your bill is ready"),
    row("25", "2026-11-23T12:00:00", "page", None, None, None, None, "got_it", "neutral", "Lee Example", "Shed", pending=True),
    row("26", "2026-11-18T07:00:00", "calendar", "show", "judge", "task", "An invite", "approve", "agrees", "Sam Example", "Lunch"),
])
rule_book.retire("26")
out["full"] = settings_data.defs()["rule_book"]
print(json.dumps(out))
'''

ACT = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
import common, db, answers, rule_book, settings_data
posts = json.loads(sys.argv[2])
before = open(rule_book.STORE, encoding="utf-8").read()
out = {"said": []}
for i, p in enumerate(posts):
    rec = dict(p["rec"], id=p["key"], at="2026-11-25T09:0%d:00" % i, acted_at="2026-11-25T09:0%d:01" % i)
    out["said"].append(answers.act_on_answer(rec)["result"])
n = sum(1 for _ in open(rule_book.STORE, encoding="utf-8"))
out["bad"] = [answers.act_on_answer({"id": "rule-book:9", "action": "answer", "at": "2026-11-25T10:00:00",
                                     "text": json.dumps({"rule_book": {"op": "delete", "message": "22"}})})["result"],
              answers.act_on_answer({"id": "rule-book:10", "action": "answer", "at": "2026-11-25T10:01:00",
                                     "text": json.dumps({"rule_book": {"op": "keep", "message": "99"}})})["result"]]
after = open(rule_book.STORE, encoding="utf-8").read()
out["grows"] = [after.startswith(before), len(after.splitlines()) - len(before.splitlines()), n == sum(1 for _ in open(rule_book.STORE, encoding="utf-8"))]
rows = {r["message"]: r for r in rule_book.rows()}
pick = lambda r, ks: {k: r.get(k) for k in ks}
out["keep"] = dict(pick(rows["22"], ("press", "meaning", "at", "review")), reviewed=bool(rows["22"].get("reviewed_at")))
out["edit"] = pick(rows["23"], ("press", "meaning", "right", "note", "by", "call", "review"))
out["edit2"] = pick(rows["21"], ("press", "meaning", "right", "note", "call"))
out["retired"] = ["24" in rows, rule_book.rows(active_only=False)[0]["status"]]
d = settings_data.defs()["rule_book"]
out["sections"] = [[s["id"], [[r["message"], r["you"], bool(r["reviewed"])] for r in s["rows"]]] for s in d["sections"]]
print(json.dumps(out))
'''

NODE = r'''
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8").replace(/\r\n/g, "\n");
const pick = (name) => { const i = src.indexOf("  function " + name + "("); if (i < 0) throw new Error("no function " + name);
  let d = 0, j = src.indexOf("{", i); for (; j < src.length; j++) { if (src[j] === "{") d++; else if (src[j] === "}" && --d === 0) break; } return src.slice(i, j + 1); };
const data = JSON.parse(process.argv[2]);
const S = {meta: {settings_defs: {groups: [], settings: [{id: "x"}], rule_book: data.empty}}, ans: {}, mine: {}, open: {}, chgSent: {},
  db: {posts: [], setAnswer: function (k, r) { this.posts.push({key: k, rec: r}); return Promise.resolve(); }}};
function h(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
function D(x) { return x ? new Date(x) : null; }
function fmtD(d) { return d ? (d.getMonth() + 1) + "/" + d.getDate() : ""; }
function plural(n, w) { return n + " " + w + (n === 1 ? "" : "s"); }
function stamp() { return "2026-11-25T09:00:00"; }
function toast() {}
const device = "test";
let rendered = 0; function render() { rendered++; }
function infoBtn(t, x) { return x ? '<button class="info">i</button>' : ""; }
function sPart(id, title, inside, info) { return '<section id="set-' + id + '"><h3>' + title + "</h3>" + (info ? infoBtn(title, info) : "") + inside + "</section>"; }
eval(src.slice(src.indexOf("  var RB = {"), src.indexOf("\n", src.indexOf("  var RB = {"))));
eval(src.slice(src.indexOf("  var FRESH = {"), src.indexOf("\n", src.indexOf("  var FRESH = {"))));
for (const f of ["sAll", "chgSend", "rbState", "rbItem", "rbBlock", "rbClick", "freshLine"]) eval(pick(f));
function btn(attrs) { return {getAttribute: (k) => attrs[k] === undefined ? null : attrs[k]}; }
const out = {};
out.empty = rbBlock();
S.meta.settings_defs.rule_book = data.full;
out.full = rbBlock();
rbClick("rb-keep", btn({"data-m": "22"}));
out.saving = rbBlock();
const k1 = S.db.posts[0].key; S.ans[k1] = Object.assign({}, S.ans[k1], {status: "done", outcome: "Kept. It is marked reviewed."});
out.kept = rbBlock();
rbClick("rb-edit", btn({"data-m": "23", "data-r": "show", "data-n": ""}));
out.form = rbBlock();
RB.right = "hide"; RB.note = "  Only   matters in spring ";
rbClick("rb-save", btn({"data-m": "23"}));
rbClick("rb-edit", btn({"data-m": "21", "data-r": "hide", "data-n": ""}));
RB.right = "show"; RB.note = "";
rbClick("rb-save", btn({"data-m": "21"}));
rbClick("rb-retire", btn({"data-m": "24"}));
S.db.posts.slice(1).forEach(function (p) { S.ans[p.key] = Object.assign({}, S.ans[p.key], {status: "done", outcome: "Done."}); });
out.after = rbBlock();
out.posts = S.db.posts.map((p) => ({key: p.key, rec: {action: p.rec.action, label: p.rec.label, text: p.rec.text}}));
out.inTree = /\{id: 'do', label: 'Automation'[^\n]*parts: \[[^\]]*'rulebook'/.test(src);
out.inTop = /var top = [^\n]*rbBlock\(\)/.test(src);
out.clickWired = src.indexOf("if (a.indexOf('rb-') === 0) { rbClick(a, b); return; }") >= 0;
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


def main():
    tmp = tempfile.mkdtemp(prefix="rsireview-")
    try:
        env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(tmp, "Live"))
        env.pop("ASSISTANT_REPLAY", None)
        got, r = run(SETUP, env)
        if r.returncode or not got:
            check("the engine setup ran", r.stderr.strip()[-2500:], "")
            return finish()
        check("1. with no rows: an empty rule book in Settings data", [got["empty"]["sections"], got["empty"]["count"], got["empty"]["label"],
                                                                         bool(got["empty"]["explain"])], [[], 0, "Rule book", True])
        full = got["full"]
        check("2. Settings data: active rows grouped by section, in the sections' order, newest first; waiting and retired rows not listed",
              [[s["id"], s["label"], [r["message"] for r in s["rows"]]] for s in full["sections"]] + [full["count"], full["more"]],
              [["mailings", "Mailings and unsubscribe", ["21"]], ["bills", "Bills and receipts", ["24"]],
               ["page", "What reaches the page", ["23", "22"]], 4, 0])
        r21 = full["sections"][0]["rows"][0]
        r22 = full["sections"][2]["rows"][1]
        check("2. each row in plain words: date, sender and subject, what the assistant did, what the user did",
              [[r21["at"], r21["sender"], r21["what"], r21["did"], r21["you"]], [r22["did"], r22["you"], r22["right"], r22["reviewed"]]],
              [["2026-11-20T09:00:00", "Corner Hardware", "Weekend sale on paint",
                "Hid it. It is a mailing with an unsubscribe link, and its subject holds none of your keep words.",
                "You pressed \"I should have seen this\"."], ["Showed it on your page.", "You pressed \"Not needed\".", "show", None]])

        n = subprocess.run(["node", "-e", NODE, PAGE, json.dumps(got)], capture_output=True, text=True, timeout=60, encoding="utf-8")
        try:
            pg = json.loads(n.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            check("the page's code ran under node", n.stderr[-1500:], "")
            return finish()
        check("1. the page's empty state", "<p class=\"say\">Nothing yet. The rule book fills as you use your cards.</p>" in pg["empty"]
              and "data-s=\"rb-" not in pg["empty"], True)
        f = pg["full"]
        check("3. the page draws each section folded, in order, with its count, and Keep, Edit and Retire on every row",
              [f.count("<details class=\"more\" data-d=\"rb-"), f.count(" open>"),
               [s for s in ("Mailings and unsubscribe <span class=\"cnt\">1", "Bills and receipts <span class=\"cnt\">1",
                            "What reaches the page <span class=\"cnt\">2") if s in f],
               f.index("Mailings and") < f.index("Bills and") < f.index("What reaches"),
               f.count("data-s=\"rb-keep\""), f.count("data-s=\"rb-edit\""), f.count("data-s=\"rb-retire\""),
               "Corner Hardware: Weekend sale on paint" in f, "What I did: Showed it on your page." in f],
              [3, 0, ["Mailings and unsubscribe <span class=\"cnt\">1", "Bills and receipts <span class=\"cnt\">1",
                      "What reaches the page <span class=\"cnt\">2"], True, 4, 4, 4, True, True])
        check("3. Keep: Saving while it is sent, then Kept and marked reviewed",
              ["<span class=\"said\">Saving</span>" in pg["saving"], pg["saving"].count("data-s=\"rb-keep\""),
               "Kept and marked reviewed." in pg["kept"]], [True, 3, True])
        check("3. Edit opens the right answer (show or keep it off the page) and a note, with Save and Cancel",
              ["aria-label=\"The right answer\"" in pg["form"], "data-rbf=\"note\"" in pg["form"], "data-s=\"rb-save\" data-m=\"23\"" in pg["form"]],
              [True, True, True])
        a = pg["after"]
        check("3. after Retire the row and its now-empty section are gone; the edits say what was saved",
              ["Bills and receipts" in a, "Saved as your answer: hide it." in a, "Saved as your answer: show it." in a], [False, True, True])
        check("3. one press each, sent as a rule book press",
              [[p["key"].split(":")[0], p["rec"]["action"], p["rec"]["label"], json.loads(p["rec"]["text"])] for p in pg["posts"]],
              [["rule-book", "answer", "Rule book", {"rule_book": {"op": "keep", "message": "22"}}],
               ["rule-book", "answer", "Rule book", {"rule_book": {"op": "edit", "message": "23", "right": "hide", "note": "Only matters in spring"}}],
               ["rule-book", "answer", "Rule book", {"rule_book": {"op": "edit", "message": "21", "right": "show", "note": ""}}],
               ["rule-book", "answer", "Rule book", {"rule_book": {"op": "retire", "message": "24"}}]])
        check("3. the part is under Automation in Settings, drawn with the other parts, and its buttons are wired",
              [pg["inTree"], pg["inTop"], pg["clickWired"]], [True, True, True])

        posts = [dict(p, key=p["key"].split(":")[0] + ":" + str(i + 1)) for i, p in enumerate(pg["posts"])]
        got, r = run(ACT, env, json.dumps(posts))
        if r.returncode or not got:
            check("the engine acted on the presses", r.stderr.strip()[-2500:], "")
            return finish()
        check("4. each press acted on, in plain words", got["said"],
              ["Kept. It's marked reviewed.", "Saved as your answer.", "Saved as your answer.", "Done. I won't learn from this one."])
        check("4. Keep: marked reviewed, its press, meaning and date as they were",
              got["keep"], {"press": "not_needed", "meaning": "not-needed", "at": "2026-11-21T10:00:00", "review": "keep", "reviewed": True})
        check("4. Edit to keep it off the page: his own answer, counted against the call that showed it",
              got["edit"], {"press": "rule_book_edit", "meaning": "contradicts-show", "right": "hide", "note": "Only matters in spring",
                            "by": "owner", "call": "show", "review": "edit"})
        check("4. Edit to show it: counted against the call that hid it",
              got["edit2"], {"press": "rule_book_edit", "meaning": "contradicts-hide", "right": "show", "note": "", "call": "hide"})
        check("4. Retire: out of the active rule book, kept in the file as retired", got["retired"], [False, "retired"])
        check("4. a press that is not Keep, Edit or Retire, or for a row not there, does nothing",
              got["bad"], ["Not done: that wasn't a rule book button.", "Not done: that entry is no longer in the rule book."])
        check("4. the store only grows: every earlier line as it was, one line per press, none for a refused one",
              got["grows"], [True, 4, True])
        check("4. read back in Settings: the edits as his answers, the kept row reviewed, the retired row gone",
              got["sections"],
              [["mailings", [["21", "You set the right answer here: show it.", True]]],
               ["page", [["23", "You set the right answer here: hide it.", True], ["22", "You pressed \"Not needed\".", True]]]])
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
