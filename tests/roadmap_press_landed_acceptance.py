r"""Acceptance: a press on a roadmap drawn in the page stops saying "Sent, not yet on the roadmap" once the roadmap holds the
press itself, even when nothing else on the row changed. The page's own code (rmShown, rmSweep in page.html) is run in node
against a roadmap copy shaped like the one of 11/22 17:00: a comment on a check ("Ongoing work") that the project's session
took and marked done without changing the row. A press the roadmap does not hold yet still says so.

    python tests\roadmap_press_landed_acceptance.py
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(os.path.dirname(HERE), "engine", "System", "live_page", "page.html")

NODE = r'''
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8");
const pick = (name) => { const i = src.indexOf("  function " + name + "("); let d = 0, j = src.indexOf("{", i);
  for (; j < src.length; j++) { if (src[j] === "{") d++; else if (src[j] === "}" && --d === 0) break; } return src.slice(i, j + 1); };
let DOC = null; const S = {ans: {}}, toasts = [];
const rmDoc = () => DOC, toast = (t) => toasts.push(t);
eval(src.match(/  var RM_TS = [^\n]+\n/)[0] + pick("rmMs") + pick("rmShown") + pick("rmSweep") +
     "; globalThis.rmSweep = rmSweep; globalThis.rmShown = rmShown;");
const now = Date.now(), key = "rm:k1:" + now + "-1", mkey = "rm:k1:" + now + "-2";
const note = {row: "step-09", text: "Ongoing work", written: "2026-11-23T00:57:41.143Z", status: "open", check: "v4-1", check_text: "See: headers jamb to jamb."};
const mark = {row: "step-09", check: "test-1", text: "Throwaway test card", result: "works", note: "", marked: "2026-11-23T01:00:06.085Z"};
const ans = (k, op, path, data) => ({id: k, at: "2026-11-22T16:57:41", status: "done", text: JSON.stringify({roadmap: {key: "k1", op, path, data}})});
const out = {};
function fresh() { return {key: "k1", ovl: {}, wr: {}, seen: {}}; }
// 1. the note press, the roadmap not yet holding it: still sent, not yet on the roadmap
DOC = {notes: {}, marks: {}};
S.ans = {[key]: ans(key, "set", "notes/step-09--abc", note)};
let inst = fresh(); rmSweep(inst); out.before = Object.keys(inst.ovl);
// 2. the session took the note and marked it done (status open -> done, a done_note added), nothing else on the row changed
DOC = {notes: {"step-09--abc": Object.assign({}, note, {status: "done", done_note: "Understood: the check stays open while the work goes on."})}, marks: {}};
rmSweep(inst); out.after_done = Object.keys(inst.ovl);
// 3. the same, seen fresh after a reload (from the stored press, not the page's memory)
inst = fresh(); rmSweep(inst); out.after_reload = Object.keys(inst.ovl);
// 4. a mark press on a check that already had an older mark: the older one is not this press
DOC = {notes: {}, marks: {"step-09--test-1": Object.assign({}, mark, {result: "fails", marked: "2026-11-20T10:00:00.000Z"})}};
S.ans = {[mkey]: ans(mkey, "set", "marks/step-09--test-1", mark)};
inst = fresh(); rmSweep(inst); out.mark_older = Object.keys(inst.ovl);
// 5. the mark landed, carrying the press's own time
DOC.marks["step-09--test-1"] = Object.assign({}, mark);
rmSweep(inst); out.mark_landed = Object.keys(inst.ovl);
// 6. an answer to a question the session then closed: the answer's own time is there
const qa = {status: "answered", answer: "A. Yes", choice: "A", note: "", answered: "2026-11-23T01:05:00.000Z"};
out.answer_closed = rmShown({questions: {q1: Object.assign({}, qa, {status: "done", done_note: "Done."})}}, "questions/q1", {op: "update", data: qa});
out.answer_other = rmShown({questions: {q1: {status: "open", answer: "", answered: ""}}}, "questions/q1", {op: "update", data: qa});
out.toasts = toasts;
console.log(JSON.stringify(out));
'''


def main():
    r = subprocess.run(["node", "-e", NODE, PAGE], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        print(r.stderr)
        return 1
    got = json.loads(r.stdout)
    checks = [
        ("a comment not yet on the roadmap says sent, not yet", got["before"], ["notes/step-09--abc"]),
        ("the comment taken and marked done, nothing else changed: no longer sent, not yet", got["after_done"], []),
        ("the same after a reload", got["after_reload"], []),
        ("a mark over an older mark of the same check is still sent, not yet", got["mark_older"], ["marks/step-09--test-1"]),
        ("the mark landed: no longer sent, not yet", got["mark_landed"], []),
        ("an answer the session then closed counts as on the roadmap", got["answer_closed"], True),
        ("a question without the answer does not", got["answer_other"], False),
        ("no trouble shown", got["toasts"], []),
    ]
    bad = 0
    for name, g, w in checks:
        ok = g == w
        bad += not ok
        print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else "  got %r want %r" % (g, w)))
    print("%d of %d passed" % (len(checks) - bad, len(checks)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
