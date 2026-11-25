r"""Acceptance: cards fade away (page.html). A card that leaves a list fades out where it stood before it is taken out,
the cards below slide up from where they were instead of jumping, a new card fades in, and the system's reduced-motion
setting skips all of it. The page's own functions are cut out of page.html and run under node with stand-in page
elements; nothing outside this process is touched.

    python tests\card_motion_acceptance.py
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(os.path.dirname(HERE), "engine", "System", "live_page", "page.html")
results = []

NODE = r'''
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8").replace(/\r\n/g, "\n");
const pick = (name) => { const i = src.indexOf("  function " + name + "("); if (i < 0) throw new Error("no function " + name);
  let d = 0, j = src.indexOf("{", i); for (; j < src.length; j++) { if (src[j] === "{") d++; else if (src[j] === "}" && --d === 0) break; } return src.slice(i, j + 1); };
const line = (re) => src.match(re)[0];
const code = ["function addLines() {}", line(/  var CARD_SEL = [^\n]+\n/), pick("motionOn"), pick("cardSnap"), pick("cardMotion"), pick("setHtml"), pick("setHtmlNow")].join("\n");

/* stand-in page: a list element whose cards are drawn from "key:top:height,..." strings */
let timers = [], reduce = false;
const body = {kids: [], appendChild(n) { n.parentNode = body; this.kids.push(n); }, removeChild(n) { this.kids = this.kids.filter((x) => x !== n); n.parentNode = null; }};
function mkNode(key, top, height) {
  const classes = new Set(), log = [];
  const style = new Proxy({}, {set(t, k, v) { log.push([k, v]); t[k] = v; return true; }});
  const n = {key, top, height, attrs: {"data-key": key}, style, log, parentNode: null,
    classList: {add: (c) => classes.add(c), remove: (c) => classes.delete(c), contains: (c) => classes.has(c)}, classes,
    getAttribute(a) { return a in this.attrs ? this.attrs[a] : null; }, setAttribute(a, v) { this.attrs[a] = v; }, removeAttribute(a) { delete this.attrs[a]; },
    getBoundingClientRect() { return {top: this.top, left: 10, width: 300, height: this.height}; },
    cloneNode() { const c = mkNode(this.key, this.top, this.height); c.clone = true; return c; }};
  return n;
}
function mkList() {
  const el = {nodes: [], _html: null,
    querySelectorAll() { return this.nodes; },
    set innerHTML(h) { const old = Object.fromEntries(this.nodes.map((n) => [n.key, n]));
      this.nodes = h ? h.split(",").map((p) => { const [k, t, hh] = p.split(":"); const n = old[k] && old[k].kept ? old[k] : mkNode(k, +t, +hh); n.top = +t; n.parentNode = el; return n; }) : []; },
    get innerHTML() { return ""; }};
  return el;
}
const L = new Function("window", "document", "setTimeout", "busyKeys", code + "; return {setHtml: setHtml, motionOn: motionOn, CARD_SEL: CARD_SEL};")(
  {matchMedia: (q) => ({matches: reduce && /reduce/.test(q)})}, {body: body}, (fn, ms) => { timers.push({fn, ms}); }, () => ({}));
const out = {};
const run = () => { const t = timers; timers = []; t.forEach((x) => x.fn()); };

// 1. first drawing: no motion at all
let el = mkList();
L.setHtml(el, "A:0:100,B:100:100,C:200:100");
out.firstDraw = {ghosts: body.kids.length, fadedIn: el.nodes.filter((n) => n.classes.has("card-new")).length, timers: timers.length};
// 2. B is answered and leaves: it fades out where it stood, and is taken out only after the fade
L.setHtml(el, "A:0:100,C:100:100");
const g = body.kids[0] || null;
out.leaving = g ? {fading: g.classes.has("card-leaving"), fixed: g.style.position === "fixed", at: g.style.top, still: g.style.height, noKey: g.getAttribute("data-key") === null,
                   hidden: g.getAttribute("aria-hidden"), fadeMs: (timers.find((t) => t.ms === 300) || {}).ms || null} : null;
out.leavingBeforeTimer = body.kids.length;
// 3. C, below it, slides up from its old place after the fade, instead of jumping
const c = el.nodes.find((n) => n.key === "C"), a = el.nodes.find((n) => n.key === "A");
out.slide = {firstAt: (c.log.find((x) => x[0] === "transform") || [])[1], then: c.log.filter((x) => x[0] === "transform").map((x) => x[1]).pop(),
             transition: c.log.filter((x) => x[0] === "transition").map((x) => x[1])[1], aStill: a.log.length};
run();
out.leavingAfterTimer = body.kids.length;
// 4. a new card arrives: it fades in
L.setHtml(el, "D:0:100,A:100:100,C:200:100");
const d = el.nodes.find((n) => n.key === "D");
out.enter = {fadesIn: d.classes.has("card-new"), others: el.nodes.filter((n) => n.key !== "D" && n.classes.has("card-new")).length};
run();
out.enterDone = d.classes.has("card-new");
// 5. reduced motion: the same changes, no fade, no slide
reduce = true; timers = []; body.kids = [];
el = mkList(); L.setHtml(el, "A:0:100,B:100:100,C:200:100"); L.setHtml(el, "A:0:100,C:100:100");
const c2 = el.nodes.find((n) => n.key === "C");
out.reduced = {motionOn: L.motionOn(), ghosts: body.kids.length, moved: c2.log.length, timers: timers.length, drawn: el.nodes.map((n) => n.key).join("")};
console.log(JSON.stringify(out));
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    r = subprocess.run(["node", "-e", NODE, PAGE], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        print("FAIL the page script did not run under node: " + (r.stderr or r.stdout)[-800:])
        return 1
    html = open(PAGE, encoding="utf-8").read()
    check("the first drawing of a list has no motion", o["firstDraw"], {"ghosts": 0, "fadedIn": 0, "timers": 0})
    check("a card that leaves fades out where it stood, hidden from screen readers, for 300 ms", o["leaving"],
          {"fading": True, "fixed": True, "at": "100px", "still": "100px", "noKey": True, "hidden": "true", "fadeMs": 300})
    check("it is taken out only after the fade", (o["leavingBeforeTimer"], o["leavingAfterTimer"]), (1, 0))
    check("the card below starts where it was and slides up after the fade, the one above stays put", o["slide"],
          {"firstAt": "translateY(100px)", "then": "", "transition": "transform 250ms ease 300ms", "aStill": 0})
    check("a new card fades in, the others do not, and the fade-in mark is cleared", (o["enter"], o["enterDone"]),
          ({"fadesIn": True, "others": 0}, False))
    check("reduced motion: the cards change with no fade and no slide", o["reduced"],
          {"motionOn": False, "ghosts": 0, "moved": 0, "timers": 0, "drawn": "AC"})
    check("the page's styles fade out, fade in, and turn both off for reduced motion",
          all(w in html for w in (".card-leaving{animation:cardOut .3s", ".card-new{animation:cardIn .2s",
                                  "@media (prefers-reduced-motion:reduce){*{transition:none!important}.card-leaving,.card-new{animation:none!important}}")), True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
