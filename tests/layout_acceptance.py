r"""Acceptance: the page's parts placed in Top, Left, Right and Bottom from Settings. On a scratch copy laid down from this
plugin with one connected roadmap: an arrangement using all four areas, one part switched off and a new order is saved,
reaches the page's data, is kept across a reload and an update, and the page's own script reads it the same way.
Nothing outside the scratch folder changes.

    python tests\layout_acceptance.py
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                                      # the plugin: this repository
results = []

INSIDE = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
import common, settings_page, setup_steps
what = sys.argv[3]
out = {}
if what == "save":
    setup_steps.apply_roadmap(sys.argv[4])
    mods = settings_page.modules()
    rm = [m for m in mods if m.startswith("rm:")]
    out["default"] = settings_page.for_page()["page"]["order"]
    want = {"top": ["chat", rm[0]], "left": ["feed"], "right": ["today", "about"], "bottom": ["texts", "mail"]}
    want_full = dict(want, bottom=want["bottom"] + ["calendar", "contacts"])
    ok, said = settings_page.save({"settings": {"group": "page", "values": {"order": want, "hidden": ["calendar"]}}})
    out["saved"] = [ok, said[:60]]
    bad, said2 = settings_page.save({"settings": {"group": "page", "values": {"order": {"top": ["chat", "chat"]}}}})
    out["refused"] = bad
    out["want"] = want_full
    # an arrangement saved when each kind of card, Ready to send and Changes to your assistant were parts of their own:
    # the first card kind named places Cards, and the other two are left out (they live in Mail and in Settings now)
    out["older"] = settings_page._order({"top": ["ready", "chat"], "left": ["small", "decide"], "right": ["today", "handled", "changes"],
                                         "bottom": ["held"]}, settings_page.modules())
out["now"] = settings_page.for_page()["page"]["order"]
out["hidden"] = settings_page.for_page()["page"]["hidden"]
print(json.dumps(out))
'''

# the page's own reading of an arrangement (layoutOf in page.html), run as the page runs it
NODE = r'''
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8");
const pick = (name) => { const i = src.indexOf("  function " + name + "("); let d = 0, j = src.indexOf("{", i);
  for (; j < src.length; j++) { if (src[j] === "{") d++; else if (src[j] === "}" && --d === 0) break; } return src.slice(i, j + 1); };
const consts = src.match(/  var AREAS = [^\n]+\n/)[0] + src.match(/  var DEF_AREA = [^\n]+\n/)[0] + src.match(/  var FEED_KINDS = [^\n]+\n/)[0];
const S = {meta: {roadmaps: JSON.parse(process.argv[2])}};
eval(consts + "var TITLE_ID = {};" + pick("modParts") + pick("modKeys") + pick("rmKeys") + pick("layoutOf") + "; globalThis.layoutOf = layoutOf;");
console.log(JSON.stringify({saved: layoutOf(JSON.parse(process.argv[3])), none: layoutOf(null),
  older: layoutOf({top: ["ready", "chat"], left: ["small", "decide"], right: ["today", "handled", "changes"], bottom: ["held"]})}));
'''

# the page's own Ready to send part (renderReady in page.html), drawn with and without drafts, switched on and off
READY = r'''
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8");
const pick = (name) => { const i = src.indexOf("  function " + name + "("); let d = 0, j = src.indexOf("{", i);
  for (; j < src.length; j++) { if (src[j] === "{") d++; else if (src[j] === "}" && --d === 0) break; } return src.slice(i, j + 1); };
let EL = {hidden: true}, LIVE = [], OFF = [], BAR = null;
const S = {ans: {}, rdAll: {}};
const $ = (id) => id === "sec-ready" ? EL : id === "mail-drafts" ? BAR : null;
const setHtml = (el, s) => { el.innerHTML = s; };
const setts = () => ({page: {hidden: OFF}});
const rdLive = () => LIVE, rdLeft = () => [], rdCardHtml = (it) => "<article>" + it.title + "</article>";
const h = (s) => String(s), secName = () => "Ready to send", addLines = () => {};
const plural = (n, w) => n + " " + w + (n === 1 ? "" : "s"), sendOff = () => false, rdAllAns = () => null, rdAllBusy = () => false;
const rdSendable = (it) => it.state !== "done";
eval("var POP = null, RDO = {open: false, was: 0}; " + src.match(/  var FEED_KINDS = [^\n]+\n/)[0] + pick("hiddenSec") + pick("rdIs") + pick("rdOwn") + pick("rdBatch") + pick("renderDrafts") + pick("renderReady") +
     "; globalThis.renderReady = renderReady; globalThis.RDO = RDO;");
const draft = {key: "L1", id: "L1", title: "Reply to Pat", state: "question", ready: {batch: "b1", why: "x"}};
const out = {};
for (const [name, live, off] of [["none", [], []], ["one", [draft], []], ["one, an old switch-off", [draft], ["ready"]],
                                 ["all sent", [Object.assign({}, draft, {state: "done"})], []]]) {
  EL = {hidden: true}; LIVE = live; OFF = off; renderReady();
  out[name] = {hidden: EL.hidden, empty: (EL.innerHTML || "").includes("No drafts right now"), title: (EL.innerHTML || "").includes("<h2>Ready to send</h2>"),
               count: ((EL.innerHTML || "").match(/<span class="n">([^<]*)</) || [])[1] || null};
}
// Mail's header: how many are ready to send, and the button that opens and closes them there
BAR = {}; EL = {hidden: true}; LIVE = []; OFF = []; renderReady();
out.bar_none = {bar: BAR.innerHTML, hidden: EL.hidden};
LIVE = [draft]; renderReady();
out.bar_new = {words: /1 email ready to send/.test(BAR.innerHTML), button: (BAR.innerHTML.match(/>(Hide drafts|Drafts)</) || [])[1], hidden: EL.hidden};
RDO.open = false; renderReady();
out.bar_closed = {words: /1 email ready to send/.test(BAR.innerHTML), button: (BAR.innerHTML.match(/>(Hide drafts|Drafts)</) || [])[1], hidden: EL.hidden};
console.log(JSON.stringify(out));
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="layout-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    project = os.path.join(tmp, "Kitchen project")
    os.makedirs(os.path.join(project, ".claude", "roadmap"))
    with open(os.path.join(project, ".claude", "roadmap", "config.json"), "w", encoding="utf-8") as f:
        json.dump({"director_session_id": "m", "writer": {"session_id": "w"}}, f)
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_layout", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    a = os.path.join(data, "scripts", "assistant.py")

    def inside(*args):
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live, os.path.join(root, "System", "live_page"), *args],
                           capture_output=True, text=True, env=env, timeout=120)
        return json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"error": r.stderr[-400:]}

    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, a, "lay-down", "--port", "47900", "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        got = inside("save", project)
        rm = [m for m in got.get("default", {}).get("left", []) if m.startswith("rm:")]
        check("default: Cards then the new roadmap on the left, Today on the right", (got.get("default", {}).get("top"),
              got.get("default", {}).get("left", [])[:1], len(rm), got.get("default", {}).get("right"), got.get("default", {}).get("bottom")),
              (["chat", "about"], ["feed"], 1, ["today"], ["mail", "texts", "calendar", "contacts"]))
        older = {"top": ["chat", "about"], "left": ["feed"] + rm, "right": ["today"], "bottom": ["mail", "texts", "calendar", "contacts"]}
        check("an arrangement saved with the card kinds as parts reads as Cards, without Ready to send or Changes", got.get("older"), older)
        check("an arrangement using all four areas is saved", got.get("saved", [None])[0], True)
        check("a part named twice is refused", got.get("refused"), False)
        check("the page's data carries it, a part off, a new order", (got.get("now"), got.get("hidden")), (got.get("want"), ["calendar"]))
        again = inside("read")
        check("it is kept: read again later", (again.get("now"), again.get("hidden")), (got.get("want"), ["calendar"]))
        # an update in between (the shipped base made older, so the update runs)
        sj = os.path.join(root, "Shipped", "shipped.json")
        d = json.load(open(sj, encoding="utf-8"))
        d["version"] = "0.0.9"
        json.dump(d, open(sj, "w", encoding="utf-8"))
        r = subprocess.run([sys.executable, a, "update-apply", "--root", root], capture_output=True, text=True)
        check("an update goes through", r.returncode, 0)
        after = inside("read")
        check("it is kept across the update", (after.get("now"), after.get("hidden")), (got.get("want"), ["calendar"]))
        # the page reads the arrangement the same way the engine does
        key = rm[0][3:] if rm else "x"
        page = os.path.join(root, "System", "live_page", "page.html")
        r = subprocess.run(["node", "-e", NODE, page, json.dumps([{"key": key, "name": "Kitchen project"}]), json.dumps(got.get("want"))],
                           capture_output=True, text=True)
        js = json.loads(r.stdout or "{}") if r.returncode == 0 else {"error": r.stderr[-300:]}
        check("the page places every part where it was saved", js.get("saved"), got.get("want"))
        check("with nothing saved the page has Cards on the left and Today on the right", js.get("none"), {"top": ["chat", "about"], "left": ["feed", "rm:" + key],
                                                                         "right": ["today"], "bottom": ["mail", "texts", "calendar", "contacts"]})
        check("the page reads an older arrangement the same way", js.get("older"), dict(older, left=["feed", "rm:" + key]))
        r = subprocess.run(["node", "-e", READY, page], capture_output=True, text=True)
        rd = json.loads(r.stdout or "{}") if r.returncode == 0 else {"error": r.stderr[-300:]}
        check("Ready to send with no drafts: drawn, saying so", rd.get("none"), {"hidden": False, "empty": True, "title": True, "count": None})
        check("with a draft: drawn with its count", rd.get("one"), {"hidden": False, "empty": False, "title": True, "count": "1 email"})
        check("Drafts is no longer a part to switch off: an old switch-off is ignored", (rd.get("one, an old switch-off") or {}).get("hidden"), False)
        check("after sending: the all sent view stays", (rd.get("all sent") or {}).get("count"), "all sent")
        check("Mail's header with no drafts: nothing, and Drafts closed", rd.get("bar_none"), {"bar": "", "hidden": True})
        check("a new draft: the header counts it and opens Drafts", rd.get("bar_new"), {"words": True, "button": "Hide drafts", "hidden": False})
        check("Drafts closed with one waiting: the count stays with a Drafts button", rd.get("bar_closed"), {"words": True, "button": "Drafts", "hidden": True})
        html = open(page, encoding="utf-8").read()
        check("Drafts sits at the top of Mail", html.index('id="mail-drafts"') > html.index('id="sec-mail"') and html.index('id="sec-ready"') < html.index('id="sec-texts"'), True)
        check("Cards holds every kind of card, Hidden today last", [html.index(f'id="sec-{k}"') > html.index('id="sec-feed"') and html.index(f'id="sec-{k}"') < html.index('id="area-right"')
                                                                     for k in ("decide", "small", "tracked", "fyi", "someday", "handled", "saidso", "held")] + [html.index('id="sec-held"') > html.index('id="sec-saidso"')], [True] * 9)
        check("the page has the four areas and no drag handles of its own", (all(f'id="area-{x}"' in html for x in ("top", "left", "right", "bottom")),
                                                                          html.split("<script>")[0].count('draggable')), (True, 0))
        subprocess.run([sys.executable, a, "uninstall", "--remove-data", "--root", root], capture_output=True, text=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got_, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got_!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
