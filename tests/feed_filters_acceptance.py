r"""Acceptance (quick): the Cards filter buttons. The page's own renderFeed is cut out of page.html and run under node with
stand-in sections holding made-up cards. Nothing outside this process is touched.

- The buttons are All, Needs you, Waiting on others, Waiting, Someday, FYI, Done, Hidden, each with its own count.
- Waiting on others counts only the tracked cards and Someday only the someday cards.
- Pressing Waiting on others shows only the tracked section; pressing Someday only the someday section.
- A card in each section is tagged with the button's name.

    python tests\feed_filters_acceptance.py
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(os.path.dirname(HERE), "engine", "System", "live_page", "page.html")
results = []

NODE = r'''
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8").replace(/\r\n/g, "\n");
const pick = (name) => { const i = src.indexOf("  function " + name + "("); if (i < 0) throw new Error("no function " + name);
  let d = 0, j = src.indexOf("{", i); for (; j < src.length; j++) { if (src[j] === "{") d++; else if (src[j] === "}" && --d === 0) break; } return src.slice(i, j + 1); };
const line = (re) => src.match(re)[0];
const mk = (id, n) => ({id, hidden: false, className: "", children: [], textContent: "", querySelectorAll: (q) => q === "article" ? new Array(n).fill(0) : []});
const els = {};
const counts = {decide: 2, small: 1, tracked: 3, waiting: 0, fyi: 4, someday: 5, handled: 6, saidso: 0, held: 0};
Object.keys(counts).forEach((k) => { els[k] = mk(k, counts[k]); els["sec-" + k] = mk("sec-" + k, 0); });
els["n-held"] = {textContent: "0"};
els.feed = {children: Object.keys(counts).map((k) => els["sec-" + k]), className: "", appendChild() {}, querySelectorAll: () => []};
els["feed-bar"] = {innerHTML: ""};
els["feed-none"] = {hidden: true, textContent: ""};
const code = [line(/  var FEED_KINDS = [^\n]+\n/), "var FEED = {f: 'needs'};", line(/  var FEED_F = [^\n]+\n[^\n]+\n/), line(/  var FEED_GROUPS = [^\n]+\n/),
  pick("feedOrder"), pick("feedCount"), pick("renderFeed")].join("\n");
const pre = `function $(id) { return els[id] || null; } function setHtml(el, h) { el.innerHTML = h; } function h(s) { return s; }
  function setts() { return null; } function kindsGrouped() { return true; } function mixFeed() {} function sortBarHtml() { return ""; } function infoPop() { return ""; }
  var S = {panel: {}};`;
const run = new Function("els", pre + code + `
  function bar() { return (els["feed-bar"].innerHTML.split("</button>").filter(function (b) { return b; }) || []).map(function (b) { return b.replace('<span class="c">', "|").replace(/<[^>]+>/g, ""); }); }
  var out = {}; function unhide() { Object.keys(els).forEach(function (k) { if (/^sec-/.test(k)) els[k].hidden = false; }); }
  renderFeed(); out.bar = bar();
  FEED.f = "tracked"; unhide(); renderFeed(); out.tracked = Object.keys(els).filter(function (k) { return /^sec-/.test(k) && !els[k].hidden; });
  FEED.f = "someday"; unhide(); renderFeed(); out.someday = Object.keys(els).filter(function (k) { return /^sec-/.test(k) && !els[k].hidden; });
  return out;`);
console.log(JSON.stringify(run(els)));
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    r = subprocess.run(["node", "-e", NODE, PAGE], capture_output=True, text=True, timeout=120)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        print("FAIL the page script did not run under node: " + (r.stderr or r.stdout)[-1500:])
        return 1
    check("the buttons, in order, with their counts: Waiting on others, Waiting and Someday",
          o["bar"], ["All|21", "Needs you|3", "Waiting on others|3", "Waiting|0", "Someday|5", "FYI|4", "Done|6", "Hidden|0"])
    check("Waiting on others shows only the tracked cards", o["tracked"], ["sec-tracked"])
    check("Someday shows only the someday cards", o["someday"], ["sec-someday"])
    html = open(PAGE, encoding="utf-8").read()
    check("the card tags read Waiting on others and Someday",
          (re.search(r'#sec-tracked article\.card::before\{content:"Waiting on others"\}', html) is not None,
           re.search(r'#sec-someday article\.card::before\{content:"Someday"\}', html) is not None), (True, True))
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
