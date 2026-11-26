r"""Acceptance: Settings, Tools. Each listed tool's Start begins its walk-through in the page's chat (its first message, and the
walk-through it follows in the chat's instructions); uninstall, adopt and the roadmap tools are not listed; a setup step the chat
asks for runs on the computer and its answer comes back in the same message; a step only the computer can do comes back as plain
words saying where to finish it, with the link where one finishes it; the page's Tools part shows every tool in plain words with
Start, and Start posts that tool's start to the chat. On a scratch copy laid down from this plugin, with Claude as a stand-in, and
the page's own code under node. Nothing outside the scratch folder changes.

    python tests\tools_acceptance.py
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

INSIDE = r'''
import json, os, sys
live = sys.argv[1]
sys.path.insert(0, live)
import common, answers, chat, tools, updates
out = {}
updates.latest = lambda rp: ("0.1.4", ["Cards made simpler"])         # the newest version, as the weekly look would find it
updates.repo = lambda: "repo"
out["listed"] = [(t["id"], t["name"], bool(t["words"])) for t in tools.listed()]
runs = []
def stand_in(words, told, sess):
    runs.append({"words": words, "told": told})
    return ("Let us start. Which part?", "", 0.1, {})
chat._run = stand_in
marks = {"update": "THE UPDATE HE STARTED (to version 0.1.4)", "change": "A CHANGE TO HOW THE ASSISTANT WORKS IS BEING TALKED THROUGH",
         "undo": "A CHANGE TO HOW THE ASSISTANT WORKS IS BEING TALKED THROUGH", "introduce": "HE STARTED THE TOOL \"Introduce a project\"",
         "setup": "HE STARTED THE TOOL \"Set up again\"", "voice": "HE STARTED THE TOOL \"Writing style builder\""}
out["start"] = {}
n = 0
for t in tools.listed():
    n += 1
    runs.clear()
    r = answers.act_on_answer({"id": f"tool:{t['id']}:17000000000{n}", "action": "answer", "text": "Start: " + t["name"], "at": f"2026-11-19T12:00:0{n}"})
    first = next(x for x in tools.TOOLS if x["id"] == t["id"])["first"]
    turns = chat.load()["turns"]
    you = [x for x in turns if x.get("who") == "you" and x.get("at") == f"2026-11-19T12:00:0{n}"]
    out["start"][t["id"]] = [r.get("ok"), bool(runs) and runs[0]["words"] == first, bool(runs) and marks[t["id"]] in runs[0]["told"],
                             [x.get("text") for x in you] == [first], turns[-1].get("who")]

# a setup step the chat asks for runs here, and its answer comes back in the same message
runs.clear()
replies = iter(['Let me see your projects.\nACTION: {"type": "setup", "run": ["projects"]}', "You have no projects yet. Which folder?"])
chat._run = lambda words, told, sess: (runs.append({"words": words}) or (next(replies), "", 0.1, {}))
r = chat.handle("Which projects do I have?")
out["a setup step runs and its answer comes back"] = [len(runs), runs[1]["words"].startswith("(the setup steps you asked for ran on this computer"),
                                                      "setup projects: {" in runs[1]["words"], r["result"]]
# the interview's own shorter form
runs.clear()
replies = iter(['ACTION: {"setup": ["accounts"]}', "Here are your accounts."])
r = chat.handle("Which accounts do I have?")
out["the interview's {\"setup\": [...]} form runs too"] = [len(runs), "setup accounts: {" in runs[1]["words"]]
# a step only the computer can do: plain words with where to finish it
runs.clear()
replies = iter(['ACTION: {"type": "setup", "run": ["connect", "google_mail"]}', "That part is at your computer."])
r = chat.handle("Connect my other Gmail")
out["a sign-in step comes back as where to finish it"] = "/assistant:change accounts" in runs[1]["words"]
out["desktop-only steps"] = {
    "change: sign in": tools.run_setup(["connect", "google_mail"]),
    "change: from anywhere": tools.run_setup(["reach-on"]),
    "update: put in place": tools.run_setup(["update-apply"]),
    "setup again: switch on": tools.run_setup(["turn-on"]),
    "a first-setup step": tools.run_setup(["install-parts"]),
    "a change's go": tools.run_setup(["change-go", "ch-0001", "x"]),
    "anything else": tools.run_setup(["rm", "-rf"]),
}
print(json.dumps(out))
'''

NODE = r'''
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8").replace(/\r\n/g, "\n");
const pick = (name) => { const i = src.indexOf("  function " + name + "("); if (i < 0) throw new Error("no function " + name);
  let d = 0, j = src.indexOf("{", i); for (; j < src.length; j++) { if (src[j] === "{") d++; else if (src[j] === "}" && --d === 0) break; } return src.slice(i, j + 1); };
const tools = JSON.parse(process.argv[2]);
const posted = [], jumped = [];
const S = {meta: {tools: tools}};
function h(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
function talkPost(text, key, label) { posted.push({text: text, key: key.replace(/\d+$/, "N"), label: label}); }
function jump(k) { jumped.push(k); }
function ptItem() { return ""; }          // the four project tools have their own test (project_tools_acceptance.py)
S.open = {}; S.ans = {}; const REB = {ask: false}, RLD = {ask: false}, HOME = {}, SLR = {st: null, busy: false, timer: 0, err: ""}; function homeKind() { return "other"; }
const MODP = {parts: {}};  // the Settings part as one piece (the page now gathers parts for its Settings navigation)
function sPart(id, title, inside) { return '<details class="fold" id="set-' + id + '"><summary>' + title + '</summary><div class="panel-box host set-in">' + inside + '</div></details>'; }
const xi = src.indexOf("  var INFO_X = "); eval(src.slice(xi, src.indexOf("};", xi) + 2));     // the (i) words the page draws itself
for (const f of ["infoBtn", "sAll", "cmdList", "cmdItems", "modEach", "modTools", "reloadItem", "rebuildItem", "homeItem", "toolsBlock"]) eval(pick(f));
const html = toolsBlock();
const handler = src.slice(src.indexOf("    if (a === 'tool-start') {"), src.indexOf("    if (a === 'reb-ask')"));
const press = new Function("a", "b", "S", "talkPost", "jump", handler);
for (const t of tools) press("tool-start", {getAttribute: () => t.id}, S, talkPost, jump);
console.log(JSON.stringify({html: html, posted: posted, jumped: jumped, inTop: /var top = [^\n]*toolsBlock\(\)/.test(src)}));
'''

WANT_LISTED = [["update", "Update", True], ["undo", "Undo a change", True],
               ["introduce", "Introduce a project", True], ["setup", "Set up again", True], ["voice", "Writing style builder", True]]


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="tools-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_tools", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47917",
                            "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=900)
        try:
            o = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            o = {}
            check("the checks ran", r.stderr.strip()[-2000:], "")
        check("listed: Update, Change, Undo a change, Introduce a project, Set up again, Writing style builder, each with plain words", o.get("listed"), WANT_LISTED)
        check("not listed: uninstall, adopt, the roadmap tools",
              [x for x in (o.get("listed") or []) if x[0] in ("uninstall", "adopt") or x[0].startswith("roadmap")], [])
        for tid, _n, _w in WANT_LISTED:
            check(f"Start on {tid}: its first message goes to the chat, with its walk-through in the chat's instructions, and is answered",
                  (o.get("start") or {}).get(tid), [True, True, True, True, "assistant"])
        check("a setup step the chat asks for runs on the computer and its answer comes back in the same message",
              o.get("a setup step runs and its answer comes back"), [2, True, True, "Let me see your projects. You have no projects yet. Which folder?"])
        check("the interview's own {\"setup\": [...]} form runs too", o.get("the interview's {\"setup\": [...]} form runs too"), [2, True])
        check("a sign-in step asked for in the chat comes back as where to finish it", o.get("a sign-in step comes back as where to finish it"), True)
        d = o.get("desktop-only steps") or {}
        check("Change, sign in: plain words, finished at the computer with /assistant:change accounts",
              ["sign-in window on your computer" in d.get("change: sign in", ""), "/assistant:change accounts" in d.get("change: sign in", "")], [True, True])
        check("Change, from anywhere: the Tailscale link and where to finish it",
              ["https://tailscale.com/download/windows" in d.get("change: from anywhere", ""), "/assistant:change page" in d.get("change: from anywhere", "")], [True, True])
        check("Update, putting it in place: plain words, finished at the computer with /assistant:update",
              ["stops and restarts this page" in d.get("update: put in place", ""), "/assistant:update" in d.get("update: put in place", "")], [True, True])
        check("Set up again, switching on: plain words, finished at the computer", "/assistant:change switch-on" in d.get("setup again: switch on", ""), True)
        check("a first-setup step is not run from the page", "/assistant:setup" in d.get("a first-setup step", ""), True)
        check("a change is only made by his Approve on its card", "Approve on its card" in d.get("a change's go", ""), True)
        check("anything else is not run", d.get("anything else"), "\"rm\" is not a setup step Talk to your assistant can run. Nothing was changed.")
        listed = [{"id": x[0], "name": x[1], "words": "w-" + x[0], "explain": "x-" + x[0]} for x in WANT_LISTED]
        r = subprocess.run(["node", "-e", NODE, PAGE, json.dumps(listed)], capture_output=True, text=True, timeout=60)
        try:
            p = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            p = {}
            check("the page's code ran under node", r.stderr[-800:], "")
        html = p.get("html", "")
        check("the page's Tools part shows every tool's name, its (i) with its explanation, and plain words with Start",
              [all(f"<b>{x['name']}<button class=\"info\"" in html and f"data-x=\"{x['explain']}\"" in html and x["words"] in html for x in listed),
               html.count("data-s=\"tool-start\""), p.get("inTop")], [True, 5, True])
        check("Start posts that tool's start to the chat and goes to the chat",
              [p.get("posted"), p.get("jumped")], [[{"text": "Start: " + x["name"], "key": f"tool:{x['id']}:N", "label": "Start " + x["name"]} for x in listed], ["chat"] * 5])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
