r"""Acceptance: Handled for you never presents a card nobody acted on as handled. On made-up cards only.

Engine, on a scratch copy laid down from this plugin:
- A card in Ready to send is never joined with another card, either way round (discarding the draft must not close the matter).
- Two ordinary open cards still join; the one taken in closes as "Joined into <the other>".
- A card whose task the assistant's own reading closes says so: status "Closed by your assistant", and its last history line
  gives the reason, or says no reason was given.
- A card he answered keeps its own ending when its task closes.

Page, the page's own code cut out of page.html and run under node:
- Joined cards and cards the assistant closed on its own sit in their own fold, "Done by your assistant, no action taken",
  each saying what happened (joined into which card, and whether that card is open or how it ended; or the assistant's reason),
  with Bring it back. Only cards something was done on are under "Finished".

    python tests\handled_truth_acceptance.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
PAGE = os.path.join(PKG, "engine", "System", "live_page", "page.html")
results = []


def check(name, got, want):
    results.append((name, got == want, got, want))


INSIDE = r'''
import json, os, sys
live = sys.argv[1]
sys.path.insert(0, live)
import common, db, items
out = {}
def mk(key, **kw):
    base = dict(kind="task", area="Work", state="yours", title=key, source_who="Dana", source_when=common.now(), source_messages=[])
    base.update(kw)
    return items.upsert(key, "t", **base)[0]
def row(i):
    return items.rows("id = ?", (i,))[0]

task = mk("live:ht-task", title="Ask the supplier for an old-price quote")
ready = mk("live:ht-ready", kind="approval", state="question", title="A reply to Jo", extra={"ready": {"batch": "b1", "why": "You started a reply."}})
out["ready_join"] = [items.join(task, ready, "t"), items.join(ready, task, "t"), row(task)["state"], row(ready)["state"]]
other = mk("live:ht-other", title="The same matter, written again")
ok = items.join(other, task, "t")
o = row(other)
out["plain_join"] = [ok, o["state"], o["status"] == "Joined into " + task, row(task)["state"]]

def add_task(key):
    db.execute("INSERT INTO tasks (item_key, kind, area, title, detail, status, urgency, first_seen, last_seen, created_at, updated_at)"
               " VALUES (?, 'task', 'Work', ?, 'x', 'needs_me', 'normal', today(), today(), now(), now())", (key, key))
for k in ("ht-lights", "ht-quiet", "ht-answered"):
    add_task(k)
items.sync_from_tasks("t1")
card = {k: items.rows("source_key = ?", ("task:" + k,))[0]["id"] for k in ("ht-lights", "ht-quiet", "ht-answered")}
con = db.connect()
con.execute("UPDATE live_items SET answer='Done', answered_at=now(), status='Done' WHERE id=?", (card["ht-answered"],))
con.close()
db.execute("UPDATE tasks SET status='dismissed', resolved_reason='The lights were fixed by the caretaker', updated_at=now() WHERE item_key='ht-lights'")
db.execute("UPDATE tasks SET status='done', updated_at=now() WHERE item_key IN ('ht-quiet', 'ht-answered')")
items.sync_from_tasks("t2")
r = {k: row(v) for k, v in card.items()}
last = lambda x: (x["assistant_did"] or "").split("\n")[-1]
out["closed_reason"] = [r["ht-lights"]["state"], r["ht-lights"]["status"], "I closed it, no action taken" in last(r["ht-lights"]),
                        last(r["ht-lights"]).endswith(": The lights were fixed by the caretaker")]
out["closed_quiet"] = [r["ht-quiet"]["state"], r["ht-quiet"]["status"], last(r["ht-quiet"]).endswith(", and I gave no reason.")]
out["answered_keeps"] = [r["ht-answered"]["state"], r["ht-answered"]["status"]]
print(json.dumps(out))
'''

WANT_ENGINE = {
    "ready_join": [False, False, "yours", "question"],
    "plain_join": [True, "done", True, "yours"],
    "closed_reason": ["done", "I closed it, no action taken", True, True],
    "closed_quiet": ["done", "I closed it, no action taken", True],
    "answered_keeps": ["done", "Done"],
}

NODE = r'''
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8").replace(/\r\n/g, "\n");
const pick = (name) => { const i = src.indexOf("  function " + name + "("); if (i < 0) throw new Error("no function " + name);
  let d = 0, j = src.indexOf("{", i); for (; j < src.length; j++) { if (src[j] === "{") d++; else if (src[j] === "}" && --d === 0) break; } return src.slice(i, j + 1); };
const between = (a, b) => { const i = src.indexOf(a), j = src.indexOf(b, i); if (i < 0 || j < 0) throw new Error("no region " + a); return src.slice(i, j); };
const code = [
  between("  function $(id) {", "  function cards(list, s)"),
  between("  var COMPOSE = ", "  /* ---------- the direct box"),
  pick("cards"), pick("fold"), pick("handledHtml"), pick("doneDays"), pick("find"), pick("calPanel"), pick("whenWords"), pick("laterUntil"),
].join("\n");
const prelude = `
  var S = {meta: {send: {on: true, accounts: ["me@a.example"]}, settings: {page: {}}}, items: [], ans: {}, err: {}, panel: {}, drafts: {}, open: {}, mine: {}, was: {}, think: {},
           sample: {}, box: {}, view: null, oldDone: {}, oldBack: {}, revDone: {}, db: {}, live: "on", listening: true, baseline: "2026-11-01T00:00:00", mail: {hosted: false}, rmDocs: {}};
  var acting = null, device = "Computer, test", talk = {}, LINE = {now: null, queue: []};
  function render() {} function keepDrafts() {} function keepSet() {} function keepGet() { return null; } function toast() {} function hideToast() {} function drawLine() {}
  function setHtml() {} function infoBtn() {} function mailJson() {} function mailEnc() {} function mailCsrf() {} function hiddenSec() {} function cpMake() {} function cpSet() {} function cpList() {} function cpHead() {} function cpSync() {} function cpAlt() {} function cpRow() {} function cpPins() {} function cpRel() {} function cpItems() {} function cpAvatar() {} var CP_SEND = null, CP_OWN = {}; function save() { return true; } function rmCan() { return true; } function rmDoc() { return true; } function rmOpen() {}
`;
const doc = {getElementById: () => null, querySelector: () => null, body: {appendChild() {}}, createElement: () => ({setAttribute() {}}), addEventListener() {}};
const L = new Function("document", "window", "setTimeout", "setInterval", prelude + code + `
  return {S: S, card: card, sect: sect, closedOnly: closedOnly, closedWhy: closedWhy, handledHtml: handledHtml};
`)(doc, {pageYOffset: 0, scrollTo() {}, location: {search: ""}}, () => 0, () => 0);
const S = L.S, out = {};
const base = (o) => Object.assign({state: "done", kind: "task", area: "Work", created_at: "2026-11-18T09:00:00", updated_at: "2026-11-18T09:00:00", done_at: "2026-11-18T10:00:00",
                                  assistant_did: "", asks: [], status: null, answer: null, answered_at: null, last_press: null}, o);
const C = {
  stillOpen: base({id: "L20", key: "L20", state: "yours", title: "Ask the supplier for an old-price quote", short_header: "Old-price quote from the supplier"}),
  ended: base({id: "L21", key: "L21", kind: "approval", title: "A reply to Jo", short_header: "Reply to Jo", status: "Discarded", answer: "Discarded", answered_at: "2026-11-18T10:00:00",
               assistant_did: "You discarded this email 11/18 5:42 PM. It was not sent."}),
  joinedOpen: base({id: "L22", key: "L22", title: "The quote, written again", status: "Joined into L20", answered_at: "2026-11-18T10:00:00", assistant_did: "Joined into L20 (x) 11/18 5:24 PM: one matter."}),
  joinedEnded: base({id: "L23", key: "L23", title: "Ask for the old-price quote", status: "Joined into L21", answered_at: "2026-11-18T10:00:00", assistant_did: "Joined into L21 (x) 11/18 5:24 PM: one matter."}),
  quiet: base({id: "L24", key: "L24", kind: "waiting", title: "Front lights blinking, working it out with Lee"}),
  reason: base({id: "L25", key: "L25", kind: "waiting", title: "Gate code changed", status: "Closed by your assistant",
                assistant_did: "Closed by your assistant 11/20 2:29 PM: Lee said the new code works"}),
  noReason: base({id: "L26", key: "L26", title: "Order filters", status: "Closed by your assistant", assistant_did: "Closed by your assistant 11/20 2:29 PM, with no reason given."}),
  byHim: base({id: "L27", key: "L27", title: "Pay the water bill", status: "Done", answer: "Done", answered_at: "2026-11-18T10:00:00", last_press: {press: "done"},
               assistant_did: "You marked it done 11/18 10:00 AM."}),
};
S.items = Object.values(C);
out.closedOnly = Object.keys(C).filter((k) => L.closedOnly(C[k]));
out.why = {};
["joinedOpen", "joinedEnded", "quiet", "reason", "noReason"].forEach((k) => { out.why[k] = L.closedWhy(C[k]); });
const html = (k) => L.card(C[k], L.sect(C[k]));
out.cardSays = ["joinedOpen", "joinedEnded", "quiet", "reason"].every((k) => html(k).indexOf(L.closedWhy(C[k]).replace(/"/g, "&quot;")) >= 0 || html(k).indexOf(L.closedWhy(C[k])) >= 0);
out.bringBack = ["joinedOpen", "quiet"].every((k) => /Bring it back/.test(html(k)));
out.noFinishedWord = !/>Finished\.</.test(html("quiet"));
out.byHimLine = html("byHim").indexOf("You marked it done") >= 0;
const by = {answered: [], closed: [C.joinedOpen, C.joinedEnded, C.quiet, C.reason, C.noReason], done: [C.ended, C.byHim]};
const hf = L.handledHtml(by);
out.folds = (hf.match(/<summary>[^<]+<span class="cnt">\d+/g) || []).map((x) => x.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim());
console.log(JSON.stringify(out));
'''


def main():
    r = subprocess.run(["node", "-e", NODE, PAGE], capture_output=True, text=True, timeout=120)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        o = {}
        check("the page script ran under node", (r.stderr or r.stdout)[-1500:], "")
    if o:
        check("page: joined cards and cards the assistant closed on its own are told apart from ones something was done on",
              o["closedOnly"], ["joinedOpen", "joinedEnded", "quiet", "reason", "noReason"])
        check("page: each says what happened", o["why"], {
            "joinedOpen": 'I merged this card into "Old-price quote from the supplier", which is still open. Nothing was done on this one by itself.',
            "joinedEnded": 'I merged this card into "Reply to Jo", which has since ended (Discarded). Nothing was done on this one.',
            "quiet": "I marked this Done; nothing shows it was done.",
            "reason": "I marked this Done: Lee said the new code works",
            "noReason": "I marked this Done and gave no reason."})
        check("page: the card itself carries that line", o["cardSays"], True)
        check("page: each keeps Bring it back", o["bringBack"], True)
        check("page: a card nobody acted on never says Finished.", o["noFinishedWord"], True)
        check("page: a card he finished still shows what he did", o["byHimLine"], True)
        check("page: Handled for you names its fold truthfully", o["folds"],
              ["Done by me, no action taken 5"])

    tmp = tempfile.mkdtemp(prefix="handled-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_handled", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47917",
                            "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=300)
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = {}
            check("the engine checks ran", r.stderr.strip()[-2000:], "")
        names = {"ready_join": "engine: a card in Ready to send is never joined, either way round",
                 "plain_join": "engine: two ordinary cards still join; the one taken in says Joined into the other",
                 "closed_reason": "engine: a card the assistant closed says so, with its reason",
                 "closed_quiet": "engine: ... or says no reason was given",
                 "answered_keeps": "engine: a card he answered keeps its own ending"}
        for k, want in WANT_ENGINE.items():
            check(names[k], got.get(k), want)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
