/* How the page reaches its data on the owner's site: same-site requests that carry their sign-in.
   It keeps one line open to the site, which answers the moment anything changes, so new items
   and results show by themselves. If the site will not hold a line open, it asks every 2 seconds. */
window.LIVE_STORE = function () {
  'use strict';
  var csrf = '', etag = '', onLive, onAnswers, onTrouble, busy = false, again = 0, listening;
  function api(path, opts) {
    opts = opts || {};
    opts.credentials = 'same-origin'; opts.cache = 'no-store';
    return fetch('api/' + path, opts);
  }
  function next(ms) {
    clearTimeout(again);
    again = setTimeout(function () { if (!document.hidden) pull(); }, ms);
  }
  function pull() {
    if (busy) return;
    busy = true;
    var began = Date.now(), head = etag ? {'X-Brief-Have': etag, 'X-Brief-Wait': '1'} : {};
    api('data', {headers: head}).then(function (r) {
      if (r.status === 401) { location.reload(); return null; }
      if (r.status === 304) { onLive(null, true, listening); return null; }
      if (!r.ok) throw new Error(String(r.status));
      return r.json();
    }).then(function (j) {
      busy = false;
      if (j) {
        csrf = j.csrf || '';
        etag = j.etag || '';          /* carried in the reply itself: the host strips the usual header */
        listening = j.listening;
        onLive(j.live || {}, true, listening);
        onAnswers(j.answers || {});
      }
      /* A line that was not held: ask again in 2 seconds. Never ask more than about twice a second. */
      next(!j && Date.now() - began < 1500 ? 2000 : Math.max(50, 500 - (Date.now() - began)));
    }, function () {
      busy = false;
      onTrouble('The data cannot be reached right now, so this may be out of date.', false);
      next(4000);
    });
  }
  function post(path, body) {
    return api(path, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Brief-Csrf': csrf}, body: JSON.stringify(body)})
      .then(function (r) {
        if (r.status === 401) { location.reload(); }
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      });
  }
  return Promise.resolve({
    watch: function (live, answers, trouble) {
      var last = {};
      onLive = function (docs, sure, hears) { if (docs) last = docs; live(last, sure, hears); };
      onAnswers = answers; onTrouble = trouble;
      pull();
      setInterval(function () { if (!document.hidden && !busy) pull(); }, 30000);
      document.addEventListener('visibilitychange', function () { if (!document.hidden) pull(); });
    },
    setAnswer: function (key, rec) { return post('answer', {key: key, record: rec}); },
    clearAnswer: function (key) { return post('answer', {key: key, record: null}); },
    signOut: function () { return post('logout', {}).then(function () { location.reload(); }, function () { location.reload(); }); },
    /* the page's own server only: the password never goes anywhere else */
    changePassword: function (current, fresh, again) { return post('password', {current: current, 'new': fresh, again: again}); },
    signOutAll: function () { return post('signout_all', {}).then(function () { location.reload(); }, function () { location.reload(); }); }
  });
};
window.RM_SRC = {"css": "\n/* Layout: a title-block header with counts, a strip with one cell per step, what's next, then one ordered list of steps; phases indented; rows open in place. */\n:host {\n  --bg: #f5f6f4;\n  --panel: #ffffff;\n  --ink: #1d2422;\n  --muted: #5d6764;\n  --rule: #d5dad6;\n  --accent: #c8281e;\n  --fresh: #0f6f8f;      --fresh-bg: #dcf0f6;\n  --s-done: #2f7d4f;      --s-done-bg: #e3f1e8;\n  --s-look: #a86a00;      --s-look-bg: #fbefd6;\n  --s-first: #2f5f8a;     --s-first-bg: #e2ecf5;\n  --s-now: #c8281e;       --s-now-bg: #fbe3e0;\n  --s-plan: #6b5a9a;      --s-plan-bg: #ece8f6;\n  --s-none: #7a8380;      --s-none-bg: #eceeed;\n  --s-fault: #9c2f6b;     --s-fault-bg: #f6e1ec;\n  --s-built: #1f7a78;     --s-built-bg: #dcf0ee;\n  --f-text: \"IBM Plex Sans\", \"Segoe UI\", system-ui, sans-serif;\n  --f-mono: \"IBM Plex Mono\", Consolas, \"Courier New\", monospace;\n}\n@media (prefers-color-scheme: dark) { :host(:not([data-theme=\"light\"])) {\n  --bg: #141917; --panel: #1c2220; --ink: #e6ebe8; --muted: #9aa6a2; --rule: #2f3835; --accent: #ff6b5c;\n  --fresh: #6fd0ee; --fresh-bg: #143340;\n  --s-done: #6fcf95; --s-done-bg: #1d3427;\n  --s-look: #f0b24a; --s-look-bg: #3a2d14;\n  --s-first: #7fb2e3; --s-first-bg: #1c2c3c;\n  --s-now: #ff7b6e; --s-now-bg: #3e1f1b;\n  --s-plan: #b3a3e6; --s-plan-bg: #2a2540;\n  --s-none: #8e9895; --s-none-bg: #252c2a;\n  --s-fault: #e58bbd; --s-fault-bg: #3b1d2e;\n  --s-built: #5fd3cf; --s-built-bg: #16363a;\n  color-scheme: dark;\n} }\n:host([data-theme=\"dark\"]) {\n  --bg: #141917; --panel: #1c2220; --ink: #e6ebe8; --muted: #9aa6a2; --rule: #2f3835; --accent: #ff6b5c;\n  --fresh: #6fd0ee; --fresh-bg: #143340;\n  --s-done: #6fcf95; --s-done-bg: #1d3427;\n  --s-look: #f0b24a; --s-look-bg: #3a2d14;\n  --s-first: #7fb2e3; --s-first-bg: #1c2c3c;\n  --s-now: #ff7b6e; --s-now-bg: #3e1f1b;\n  --s-plan: #b3a3e6; --s-plan-bg: #2a2540;\n  --s-none: #8e9895; --s-none-bg: #252c2a;\n  --s-fault: #e58bbd; --s-fault-bg: #3b1d2e;\n  --s-built: #5fd3cf; --s-built-bg: #16363a;\n  color-scheme: dark;\n}\n* { box-sizing: border-box; }\n[hidden] { display: none !important; }\n:host { background: var(--bg); color: var(--ink); font-family: var(--f-text); font-size: 15px; line-height: 1.45; }\n.wrap { max-width: 860px; margin: 0 auto; padding-block: 20px 48px;\n  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));\n  display: flex; flex-direction: column; gap: 18px; }\n\n/* title block */\n.tb { border: 2px solid var(--ink); background: var(--panel); display: grid; grid-template-columns: 1fr auto; }\n.tb h1 { margin: 0; padding: 14px 16px; font-size: 1.5rem; line-height: 1.15; font-weight: 700; text-wrap: balance; border-right: 1px solid var(--ink); }\n.tb h1 small { display: block; font-size: .8rem; font-weight: 500; color: var(--muted); margin-top: 4px; letter-spacing: .02em; }\n.tb .date { padding: 10px 14px; display: flex; flex-direction: column; justify-content: center; gap: 6px; font-family: var(--f-mono); }\n.tb .date span { font-size: .68rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); display: block; }\n.tb .date b { font-size: 1.05rem; display: block; }\n.tb .counts { grid-column: 1 / -1; border-top: 1px solid var(--ink); display: flex; flex-wrap: wrap; }\n.tb .counts button { appearance: none; border: 0; background: none; color: inherit; font: inherit; text-align: left; cursor: pointer;\n  flex: 1 1 120px; padding: 8px 12px; border-right: 1px solid var(--rule); min-width: 0; }\n.tb .counts button:last-child { border-right: 0; }\n.tb .counts button:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }\n.tb .counts b { font-family: var(--f-mono); font-size: 1.3rem; display: block; font-variant-numeric: tabular-nums; }\n.tb .counts span { font-size: .75rem; color: var(--muted); }\n@media (max-width: 520px) {\n  .tb { grid-template-columns: 1fr; }\n  .tb h1 { border-right: 0; border-bottom: 1px solid var(--ink); }\n  .tb .date { flex-direction: row; gap: 24px; }\n}\n\n/* strip: one cell per step */\n.strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(22px, 1fr)); gap: 3px; }\n.strip button { appearance: none; border: 0; padding: 0; height: 28px; cursor: pointer; font-family: var(--f-mono); font-size: .62rem; color: var(--bg); font-weight: 600; }\n.strip button:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }\n.strip-legend { display: flex; justify-content: space-between; font-size: .72rem; color: var(--muted); margin-top: 4px; font-family: var(--f-mono); }\n\n/* what's next */\n.next { background: var(--panel); border: 1px solid var(--rule); border-top: 3px solid var(--accent); margin: 0; padding: 4px 14px; display: grid; grid-template-columns: 10em minmax(0, 1fr); }\n.next dt, .next dd { padding: 9px 0; border-bottom: 1px solid var(--rule); margin: 0; min-width: 0; }\n.next dt:nth-last-of-type(1), .next dd:last-child { border-bottom: 0; }\n.next dt { font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); font-weight: 600; padding-top: 11px; padding-right: 12px; }\n.next dt:first-of-type { color: var(--accent); }\n.next dd { font-weight: 500; overflow-wrap: anywhere; }\n@media (max-width: 560px) { .next { grid-template-columns: 1fr; } .next dt { border-bottom: 0; padding-bottom: 0; } }\n\n/* filters */\n.filters { display: flex; flex-wrap: wrap; gap: 6px; }\n.filters button { appearance: none; font: inherit; font-size: .8rem; padding: 6px 11px; border-radius: 999px; border: 1px solid var(--rule); background: var(--panel); color: var(--ink); cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }\n.filters button[aria-pressed=\"true\"] { border-color: var(--ink); background: var(--ink); color: var(--bg); }\n.filters button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }\n.dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex: none; }\n\n/* list */\nh2 { font-size: .78rem; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); margin: 10px 0 6px; font-weight: 600; border-bottom: 1px solid var(--rule); padding-bottom: 6px; }\n.list { display: flex; flex-direction: column; gap: 6px; }\n/* the row list is three folding sections: Planning, Working, Done */\n.folds { display: flex; flex-direction: column; gap: 6px; }\ndetails.sfold { min-width: 0; }\ndetails.sfold > summary { display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 6px 4px; font-size: .95rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; border-bottom: 1px solid var(--rule); }\ndetails.sfold > summary::before { content: \"+\"; font-family: var(--f-mono); color: var(--muted); display: inline-block; width: 1em; }\ndetails.sfold[open] > summary::before { content: \"\\2212\"; }\ndetails.sfold > summary .n { color: var(--muted); font-weight: 500; font-variant-numeric: tabular-nums; }\ndetails.sfold > .list { margin: 8px 0 10px; }\nh3.sub { font-size: .72rem; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); font-weight: 600; margin: 10px 0 0; }\n.pof { grid-column: 2 / -1; font-size: .78rem; color: var(--muted); min-width: 0; overflow-wrap: anywhere; }\ndetails.row { background: var(--panel); border: 1px solid var(--rule); border-left: 4px solid var(--c); min-width: 0; }\ndetails.row.phase { margin-left: 28px; }\n.runline { font-size: .9rem; color: var(--muted); padding: 2px 4px; }\ndetails.hgroup { margin: 4px 0 4px 14px; }\ndetails.hgroup > summary { cursor: pointer; font-weight: 600; padding: 6px 0; }\ndetails.hgroup > summary .n { font-weight: 400; opacity: .7; }\ndetails.row.context { opacity: .5; }\n/* a done step folds its done sub-rows: they show, indented under it, only while the step is open */\n.fmark { grid-column: 2 / -1; font-size: .78rem; color: var(--s-done); font-weight: 600; }\nsummary { list-style: none; cursor: pointer; display: grid; grid-template-columns: 3.2em minmax(0, 1fr) auto auto; align-items: center; gap: 10px; padding: 10px 12px; }\nsummary::-webkit-details-marker { display: none; }\nsummary:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }\n.num { font-family: var(--f-mono); font-weight: 600; font-size: .95rem; color: var(--muted); }\n.name { font-weight: 600; min-width: 0; overflow-wrap: anywhere; }\n.name::after { content: \"+\"; font-family: var(--f-mono); color: var(--muted); margin-left: 8px; font-weight: 500; }\ndetails.row[open] > summary .name::after { content: \"\\2212\"; }\n.tag { font-size: .72rem; font-weight: 600; padding: 3px 8px; border-radius: 4px; color: var(--c); background: var(--cb); white-space: nowrap; }\n.when { font-family: var(--f-mono); font-size: .72rem; color: var(--muted); white-space: nowrap; font-variant-numeric: tabular-nums; }\n.when.fresh { color: var(--fresh); background: var(--fresh-bg); padding: 3px 6px; border-radius: 4px; font-weight: 600; }\n@media (max-width: 560px) {\n  summary { grid-template-columns: 2.6em minmax(0, 1fr) auto; }\n  .name { grid-column: 2 / -1; }\n  .tag { grid-column: 2; justify-self: start; white-space: normal; }\n  .when { grid-column: 3; justify-self: end; }\n  details.row.phase { margin-left: 14px; }\n}\n.facts { margin: 0; padding: 12px 14px 14px; display: grid; grid-template-columns: 9.5em minmax(0, 1fr); gap: 8px 14px; border-top: 1px dashed var(--rule); }\n.facts dt { font-size: .74rem; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); font-weight: 600; padding-top: 2px; }\n.facts dd { margin: 0; min-width: 0; overflow-wrap: anywhere; max-width: 68ch; }\n.facts dd.empty { color: var(--muted); font-style: italic; }\n.facts dd.waits { color: var(--accent); font-weight: 500; }\n@media (max-width: 560px) { .facts { grid-template-columns: 1fr; gap: 2px; } .facts dd { margin-bottom: 8px; } }\n.empty-note { color: var(--muted); font-style: italic; padding: 8px 0; }\n.notice { background: var(--panel); border: 1px dashed var(--rule); padding: 14px 16px; color: var(--muted); }\n.notice.bad { border-color: var(--accent); color: var(--accent); }\nfooter { font-size: .78rem; color: var(--muted); }\n/* Settings: this project's settings, each as the main session last recorded it in board/settings */\n#setlist { display: flex; flex-direction: column; gap: 10px; margin: 8px 0 10px; }\n.setrow { background: var(--panel); border: 1px solid var(--rule); padding: 10px 12px; display: flex; flex-direction: column; gap: 6px; min-width: 0; }\n.setrow .means { font-size: .85rem; color: var(--muted); }\n.setrow .cur { font-size: .9rem; }\n.setbtns { display: flex; flex-wrap: wrap; gap: 8px; }\n.setbtns button { appearance: none; font: inherit; font-size: .9rem; min-height: 44px; padding: 6px 14px; border-radius: 6px; border: 1px solid var(--rule); background: var(--panel); color: var(--ink); cursor: pointer; }\n.setbtns button[aria-pressed=\"true\"] { border: 2px solid var(--ink); background: var(--ink); color: var(--bg); font-weight: 600; cursor: default; }\n.setbtns button.asked { border-style: dashed; border-color: var(--s-look); }\n.setbtns button:focus-visible, .setcopy button:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }\n.setsess { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; border-top: 1px dashed var(--rule); padding-top: 6px; }\n.setcopy { display: flex; gap: 8px; align-items: stretch; min-width: 0; }\n.setcopy input { flex: 1; min-width: 0; font-family: var(--f-mono); font-size: .8rem; padding: 6px 8px; border: 1px solid var(--rule); border-radius: 6px; background: var(--bg); color: var(--ink); }\n.setcopy button { appearance: none; font: inherit; font-weight: 600; min-height: 44px; padding: 6px 16px; border: 2px solid var(--ink); background: var(--ink); color: var(--bg); border-radius: 6px; cursor: pointer; }\n\n/* checks the owner marks Works / Doesn't work */\n.checkbar { background: var(--panel); border: 1px solid var(--rule); border-left: 4px solid var(--s-look); padding: 12px 14px; display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 14px; }\n.checkbar b { font-family: var(--f-mono); font-size: 1.6rem; font-variant-numeric: tabular-nums; color: var(--s-look); }\n.checkbar span { font-weight: 600; }\n.checkbar small { color: var(--muted); font-size: .85rem; flex-basis: 100%; }\n.checkbar small.bad { color: var(--s-fault); font-weight: 600; }\n/* Checks still to try: the bar and the filter button pulse slowly amber (red is kept for questions); reduced motion gets a steady amber outline */\n.cpulse .checkbar, .cpulse .filters button[data-key=\"totry\"]:not([aria-pressed=\"true\"]) { box-shadow: 0 0 0 0 transparent; animation: cpulse 2.6s ease-in-out infinite; }\n@keyframes cpulse { 0%, 100% { box-shadow: 0 0 0 0 transparent; background-color: var(--panel); } 50% { box-shadow: 0 0 12px 3px var(--s-look); background-color: var(--s-look-bg); } }\n@media (prefers-reduced-motion: reduce) { .cpulse .checkbar, .cpulse .filters button[data-key=\"totry\"]:not([aria-pressed=\"true\"]) { animation: none; outline: 2px solid var(--s-look); outline-offset: -2px; } }\n.ccount { grid-column: 2 / -1; font-size: .78rem; color: var(--muted); font-variant-numeric: tabular-nums; }\n.ccount .bad { color: var(--s-fault); font-weight: 600; }\n.ccount .all { color: var(--s-done); font-weight: 600; }\n.checks { border-top: 1px dashed var(--rule); padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 10px; }\n.checks h3 { margin: 0; font-size: .8rem; letter-spacing: .06em; text-transform: uppercase; color: var(--s-look); font-weight: 700; }\ndetails.more { border-top: 1px dashed var(--rule); }\ndetails.more > summary { display: block; padding: 12px 14px; min-height: 44px; font-size: .9rem; font-weight: 600; color: var(--muted); }\ndetails.more > summary::before { content: \"+\"; font-family: var(--f-mono); display: inline-block; width: 1.2em; }\ndetails.more[open] > summary::before { content: \"\\2212\"; }\ndetails.more > summary:hover { color: var(--ink); }\ndetails.more > .facts { border-top: 0; padding-top: 0; }\n.check { border: 1px solid var(--rule); border-radius: 6px; padding: 10px 12px; display: flex; flex-direction: column; gap: 10px; min-width: 0; }\n.check.works { border-color: var(--s-done); background: var(--s-done-bg); }\n.check.fails { border-color: var(--s-fault); background: var(--s-fault-bg); }\n.check p { margin: 0; font-size: 1rem; font-weight: 500; overflow-wrap: anywhere; max-width: 68ch; }\n/* The answer buttons on a check look like three rounded buttons drawn as a Venn diagram: Works and Doesn't work side\n   by side, and Comment below them, raised so it lies over the inner lower part of both. Five places to press, each its\n   own button, stacked so each one's rounded edge is exactly the edge of its place: Comment (z 1) under Works and\n   Doesn't work (z 2), and the two overlaps (z 3) on top. The three outlines are drawn whole above everything (z 4) and\n   take no clicks. An overlap is the two colours mixed; pointing at, focusing or pressing a place thickens the outline\n   of every button it belongs to, so an overlap shows both. */\n.choices { --o: clamp(66px, 15%, 120px); --r: 14px; position: relative; display: grid; gap: 0;\n  grid-template-columns: minmax(0, 1fr) var(--o) 6px var(--o) minmax(0, 1fr); grid-template-rows: 18px 46px 46px; }\n.notebox button, .clear { appearance: none; font: inherit; cursor: pointer; border-radius: 6px; }\n.choices button { appearance: none; font: inherit; cursor: pointer; margin: 0; min-width: 0; border: 0; padding: 4px 6px; position: relative;\n  display: flex; align-items: center; justify-content: center; text-align: center;\n  font-size: 1.02rem; font-weight: 600; line-height: 1.15; color: var(--ink); overflow-wrap: normal; }\n.choices .yes:not(.c) { grid-area: 1 / 1 / 3 / 3; z-index: 2; border-radius: var(--r); background: var(--s-done-bg); padding-right: calc(var(--o) + 6px); }\n.choices .no:not(.c) { grid-area: 1 / 4 / 3 / 6; z-index: 2; border-radius: var(--r); background: var(--s-fault-bg); padding-left: calc(var(--o) + 6px); }\n.choices .only { grid-area: 2 / 2 / 4 / 5; z-index: 1; border-radius: var(--r); background: var(--fresh-bg); padding-top: 46px; }\n.choices .yes.c { grid-area: 2 / 2 / 3 / 3; z-index: 3; border-radius: var(--r) 0 var(--r) 0;\n  background: var(--fresh-bg); background: color-mix(in srgb, color-mix(in srgb, var(--s-done) 50%, var(--fresh)) 34%, var(--panel)); }\n.choices .no.c { grid-area: 2 / 4 / 3 / 5; z-index: 3; border-radius: 0 var(--r) 0 var(--r);\n  background: var(--fresh-bg); background: color-mix(in srgb, color-mix(in srgb, var(--s-fault) 50%, var(--fresh)) 34%, var(--panel)); }\n.choices .ring { z-index: 4; pointer-events: none; border: 2px solid; border-radius: var(--r); }\n.choices .ring.w { grid-area: 1 / 1 / 3 / 3; border-color: var(--s-done); }\n.choices .ring.k { grid-area: 2 / 2 / 4 / 5; border-color: var(--fresh); }\n.choices .ring.d { grid-area: 1 / 4 / 3 / 6; border-color: var(--s-fault); }\n.choices .hint { grid-area: 3 / 1 / 4 / 2; align-self: center; justify-self: end; padding-right: 10px; font-size: .8rem; color: var(--muted); text-align: right; }\n/* the answer in force: its button filled; its overlap with Comment a deeper mix */\n.choices .yes[aria-pressed=\"true\"]:not(.c) { background: var(--s-done); color: var(--panel); }\n.choices .no[aria-pressed=\"true\"]:not(.c) { background: var(--s-fault); color: var(--panel); }\n.choices:has(.yes:not(.c)[aria-pressed=\"true\"]) .yes.c { background: color-mix(in srgb, color-mix(in srgb, var(--s-done) 60%, var(--fresh)) 70%, var(--panel)); }\n.choices:has(.no:not(.c)[aria-pressed=\"true\"]) .no.c { background: color-mix(in srgb, color-mix(in srgb, var(--s-fault) 60%, var(--fresh)) 70%, var(--panel)); }\n/* the comment box open for a place: the outline of every button that place belongs to stays heavy */\n.choices:has(.yes.c[aria-pressed=\"true\"]) :is(.ring.w, .ring.k), .choices:has(.no.c[aria-pressed=\"true\"]) :is(.ring.d, .ring.k),\n.choices:has(.only[aria-pressed=\"true\"]) .ring.k { border-width: 4px; }\n/* pointing at or focusing a place: the same, lighter; pressing it: heavier, and every button it belongs to darkens */\n@media (hover: hover) {\n  .choices:has(.yes:not(.c):hover) .ring.w, .choices:has(.yes.c:hover) :is(.ring.w, .ring.k), .choices:has(.only:hover) .ring.k,\n  .choices:has(.no.c:hover) :is(.ring.d, .ring.k), .choices:has(.no:not(.c):hover) .ring.d { border-width: 4px; border-color: var(--ink); }\n  .choices button:hover { filter: brightness(.96); }\n}\n.choices:has(.yes:not(.c):focus-visible) .ring.w, .choices:has(.yes.c:focus-visible) :is(.ring.w, .ring.k), .choices:has(.only:focus-visible) .ring.k,\n.choices:has(.no.c:focus-visible) :is(.ring.d, .ring.k), .choices:has(.no:not(.c):focus-visible) .ring.d { border-width: 4px; border-color: var(--ink); }\n.choices:has(.yes:not(.c):active) .ring.w, .choices:has(.yes.c:active) :is(.ring.w, .ring.k), .choices:has(.only:active) .ring.k,\n.choices:has(.no.c:active) :is(.ring.d, .ring.k), .choices:has(.no:not(.c):active) .ring.d { border-width: 5px; border-color: var(--ink); }\n.choices button:active, .choices:has(.yes.c:active) :is(.yes, .only), .choices:has(.no.c:active) :is(.no, .only) { filter: brightness(.88); }\n@media (max-width: 560px) { .choices button { font-size: .85rem; padding: 2px 3px; } .choices .hint { display: none; } }\n.choices button:focus-visible, .notebox button:focus-visible, .clear:focus-visible, .notebox textarea:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }\n.notebox { display: flex; flex-direction: column; gap: 8px; }\n.notebox label { font-size: .85rem; font-weight: 600; }\n.notebox small { font-size: .85rem; color: var(--muted); }\n.said .clear, .clear.say { align-self: flex-start; padding-left: 0; }\n.notebox textarea { width: 100%; min-height: 84px; font: inherit; font-size: 1rem; padding: 8px 10px; border: 1px solid var(--rule); border-radius: 6px; background: var(--panel); color: var(--ink); resize: vertical; }\n.notebox button { align-self: flex-start; min-height: 48px; min-width: 120px; padding: 8px 18px; font-weight: 600; border: 2px solid var(--ink); background: var(--ink); color: var(--bg); }\n.cfoot { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; min-height: 28px; }\n.state { font-size: .85rem; color: var(--muted); }\n.state.ok { color: var(--s-done); font-weight: 600; }\n.state.err { color: var(--accent); font-weight: 600; }\n.clear { border: 0; background: none; color: var(--muted); text-decoration: underline; padding: 8px 4px; min-height: 40px; font-size: .9rem; }\n/* a table on a row (field \"table\") */\n.scores { border-top: 1px dashed var(--rule); padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 8px; min-width: 0; }\n.scores h3 { margin: 0; font-size: .85rem; font-weight: 600; color: var(--ink); text-wrap: balance; max-width: 68ch; }\n.scores .scroll { overflow-x: auto; max-width: 100%; }\n.scores table { border-collapse: collapse; font-size: .85rem; width: 100%; min-width: 30em; }\n.scores th, .scores td { padding: 5px 8px; border-bottom: 1px solid var(--rule); text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }\n.scores th { font-size: .7rem; letter-spacing: .05em; text-transform: uppercase; color: var(--muted); font-weight: 600; vertical-align: bottom; white-space: normal; }\n.scores th:first-child, .scores td:first-child { text-align: left; white-space: normal; }\n.scores td { font-family: var(--f-mono); }\n.scores td:first-child { font-family: var(--f-text); font-weight: 500; }\n.scores td .note { color: var(--muted); font-weight: 400; font-size: .8rem; }\n.scores td.nil { color: var(--muted); }\n.scores tfoot td { border-bottom: 0; border-top: 2px solid var(--ink); font-weight: 600; }\n/* what the person writes on a row (collection \"notes\") */\n.ncount { grid-column: 2 / -1; font-size: .78rem; color: var(--fresh); font-weight: 600; }\n.notes { border-top: 1px dashed var(--rule); padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 10px; min-width: 0; }\n.notes h3 { margin: 0; font-size: .8rem; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); font-weight: 700; }\n.ncard .v { white-space: pre-wrap; }\n.ncard .v.md { white-space: normal; }\n.ncard .quiet-line, .checks .quiet-line { font-size: .85rem; color: var(--muted); }\n.ncard .clear { padding-left: 0; }\n.notes details.more { border: 1px dashed var(--rule); border-radius: 6px; }\n.notes details.more > .nlist { padding: 0 12px 12px; }\n.nlist { display: flex; flex-direction: column; gap: 10px; min-width: 0; }\n.sline { grid-column: 2 / -1; font-size: .78rem; color: var(--muted); font-variant-numeric: tabular-nums; min-width: 0; overflow-wrap: anywhere; }\n/* questions for the owner (collection \"questions\"), shown in their row's open view */\n.qbar { appearance: none; font: inherit; color: inherit; text-align: left; cursor: pointer; width: 100%; background: var(--panel); border: 1px solid var(--rule); border-left: 4px solid var(--accent); padding: 12px 14px; display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 14px; }\n.qbar:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }\n/* Open questions: the bar and the filter button pulse slowly red; reduced motion gets a steady red outline instead */\n.qpulse .qbar, .qpulse .filters button[data-key=\"questions\"]:not([aria-pressed=\"true\"]) { --pulse: rgba(200, 40, 30, .30); box-shadow: 0 0 0 0 transparent; animation: qpulse 2.6s ease-in-out infinite; }\n@keyframes qpulse { 0%, 100% { box-shadow: 0 0 0 0 transparent; background-color: var(--panel); } 50% { box-shadow: 0 0 12px 3px var(--pulse); background-color: var(--s-now-bg); } }\n@media (prefers-color-scheme: dark) { :host(:not([data-theme=\"light\"])) .qpulse .qbar, :host(:not([data-theme=\"light\"])) .qpulse .filters button[data-key=\"questions\"]:not([aria-pressed=\"true\"]) { --pulse: rgba(255, 107, 92, .45); } }\n:host([data-theme=\"dark\"]) .qpulse .qbar, :host([data-theme=\"dark\"]) .qpulse .filters button[data-key=\"questions\"]:not([aria-pressed=\"true\"]) { --pulse: rgba(255, 107, 92, .45); }\n@media (prefers-reduced-motion: reduce) { .qpulse .qbar, .qpulse .filters button[data-key=\"questions\"]:not([aria-pressed=\"true\"]) { animation: none; outline: 2px solid var(--accent); outline-offset: -2px; } }\n.qbar b { font-family: var(--f-mono); font-size: 1.6rem; font-variant-numeric: tabular-nums; color: var(--accent); }\n.qbar span { font-weight: 600; }\n.qbar small { color: var(--muted); font-size: .85rem; flex-basis: 100%; }\n.qcount { grid-column: 2 / -1; font-size: .78rem; color: var(--accent); font-weight: 600; }\n.questions { border-top: 1px dashed var(--rule); padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 10px; min-width: 0; }\n.questions h3 { margin: 0; font-size: .8rem; letter-spacing: .06em; text-transform: uppercase; color: var(--accent); font-weight: 700; }\n.questions h3.quiet { color: var(--muted); }\n.qorphan { background: var(--panel); border: 1px solid var(--rule); border-left: 4px solid var(--accent); }\n.qcard { border: 1px solid var(--accent); border-radius: 6px; padding: 10px 12px; display: flex; flex-direction: column; gap: 10px; min-width: 0; }\n.qcard.answered { border-color: var(--rule); }\n.qhead { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 10px; }\n.qtopic { font-weight: 600; }\n.qwhen { margin-left: auto; font-family: var(--f-mono); font-size: .72rem; color: var(--muted); font-variant-numeric: tabular-nums; }\n.qtext { font-size: 1rem; max-width: 68ch; overflow-wrap: anywhere; }\n.md p { margin: 0 0 .5em; } .md > :last-child { margin-bottom: 0; }\n.md ul, .md ol { margin: 0 0 .5em; padding-left: 1.4em; }\n.md h3, .md h4, .md h5, .md h6 { margin: .6em 0 .3em; font-size: .95rem; }\n.md code { font-family: var(--f-mono); background: var(--bg); padding: 0 4px; border-radius: 2px; }\n.md a { color: var(--accent); }\n.md .tscroll { overflow-x: auto; max-width: 100%; margin: 0 0 .5em; }\n.md table { border-collapse: collapse; font-size: .85rem; }\n.md th, .md td { padding: 4px 8px; border-bottom: 1px solid var(--rule); text-align: left; vertical-align: top; }\n.md th { font-size: .72rem; letter-spacing: .04em; text-transform: uppercase; color: var(--muted); font-weight: 600; }\n/* Questions in chat: each session's questions file as written (board/questions-file--<session>), read only */\n#qfiles { display: flex; flex-direction: column; gap: 10px; }\n#qfiles h2 { margin: 0; font-size: .95rem; letter-spacing: .06em; text-transform: uppercase; }\n.qfile { background: var(--panel); border: 1px solid var(--rule); border-left: 4px solid var(--accent); padding: 12px 14px; min-width: 0; }\n.qfile-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 10px; margin-bottom: 8px; }\n.qfile-head b { font-weight: 600; }\n.qfile-head span { margin-left: auto; font-family: var(--f-mono); font-size: .72rem; color: var(--muted); }\n.qfile-text { max-width: 76ch; overflow-wrap: anywhere; }\n.qfile-text h3 { display: none; }\n.qfile .means { margin-top: 8px; font-size: .85rem; color: var(--muted); }\n/* a row's written plan (field \"plan\"), folded in its open view */\n.pmark { grid-column: 2 / -1; font-size: .78rem; color: var(--muted); font-weight: 600; }\n.plantext { padding: 0 14px 14px; max-width: 76ch; min-width: 0; overflow-wrap: anywhere; }\n.pics { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1px; background: var(--rule); border: 1px solid var(--rule); }\n.pic { background: var(--panel); margin: 0; display: flex; flex-direction: column; min-width: 0; }\n.pic button { appearance: none; border: 0; padding: 0; cursor: zoom-in; display: block; background: #fff; }\n.pic button:focus-visible { outline: 3px solid var(--accent); outline-offset: -3px; }\n.pic img { display: block; width: 100%; height: auto; max-height: 520px; object-fit: contain; }\n.pic figcaption { font-size: .85rem; color: var(--muted); padding: 6px 10px 8px; }\n.qchoices { display: flex; flex-direction: column; gap: 8px; }\n.qchoice { appearance: none; font: inherit; cursor: pointer; display: flex; gap: 10px; align-items: flex-start; text-align: left; width: 100%; min-height: 48px; padding: 10px 12px; border: 2px solid var(--rule); border-radius: 6px; background: var(--panel); color: var(--ink); }\n.qchoice .cl { font-family: var(--f-mono); font-weight: 600; min-width: 1.2em; }\n.qchoice[aria-pressed=\"true\"] { background: var(--accent); border-color: var(--accent); color: var(--panel); }\n.qform { display: flex; flex-direction: column; gap: 8px; }\n.qform label { font-size: .85rem; font-weight: 600; }\n.qform textarea { width: 100%; min-height: 84px; font: inherit; font-size: 1rem; padding: 8px 10px; border: 1px solid var(--rule); border-radius: 6px; background: var(--panel); color: var(--ink); resize: vertical; }\n.qrow { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }\n.qbtn { appearance: none; font: inherit; font-weight: 600; cursor: pointer; border-radius: 6px; min-height: 48px; min-width: 120px; padding: 8px 18px; border: 2px solid var(--accent); background: var(--accent); color: var(--panel); }\n.qbtn:disabled { opacity: .5; cursor: default; }\n.qbtn.quiet { border-color: var(--rule); background: var(--panel); color: var(--ink); min-width: 0; }\n.qchoice:focus-visible, .qbtn:focus-visible, .qform textarea:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }\n.qans { background: var(--bg); padding: 10px 12px; border-radius: 6px; display: flex; flex-direction: column; gap: 4px; overflow-wrap: anywhere; }\n.qans .k { font-size: .72rem; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); font-weight: 600; }\n.qans .v { white-space: pre-wrap; }\n/* what was asked and answered before on the same question (field \"history\") */\ndetails.more.qhist { border: 1px dashed var(--rule); border-radius: 6px; min-width: 0; }\ndetails.more.qhist > summary { padding: 10px 12px; }\n.qhist-list { display: flex; flex-direction: column; gap: 10px; padding: 0 12px 12px; min-width: 0; }\n.qhist-item { display: flex; flex-direction: column; gap: 4px; min-width: 0; padding-left: 10px; border-left: 3px solid var(--rule); overflow-wrap: anywhere; }\n.qhist-item.you { border-left-color: var(--accent); }\n.qhist-item .k { font-size: .72rem; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); font-weight: 600; }\n.qhist-item .t { font-weight: 600; }\n.qhist-item .v { max-width: 68ch; min-width: 0; overflow-wrap: anywhere; }\n.qhist-item.you .v { white-space: pre-wrap; }\n.lb { position: fixed; inset: 0; z-index: 20; background: rgba(10,14,18,.92); display: flex; flex-direction: column; padding: 12px; }\n.lb-bar { display: flex; justify-content: space-between; align-items: center; color: #e3e9ef; gap: 12px; padding-bottom: 8px; flex-wrap: wrap; }\n.lb-bar button { font: inherit; font-weight: 600; background: #e3e9ef; color: #12171d; border: 0; border-radius: 4px; padding: 8px 14px; min-height: 40px; cursor: pointer; }\n.lb-scroll { flex: 1; overflow: auto; background: #fff; }\n.lb-scroll img { max-width: none; display: block; }\n.lb-scroll.fit img { max-width: 100%; max-height: 100%; margin: auto; }\n@media (prefers-reduced-motion: no-preference) { details.row { transition: border-color .15s; } }\n", "body": "<div class=\"wrap\">\n  <header class=\"tb\">\n    <h1>Project Roadmap<small id=\"psub\">Every step, in order. Tap a row to see where it stands.</small></h1>\n    <div class=\"date\">\n      <div><span>Facts as of</span><b id=\"asof\">loading</b></div>\n      <div><span>Roadmap last changed</span><b id=\"lastchange\">loading</b></div>\n    </div>\n    <div class=\"counts\" id=\"counts\"></div>\n  </header>\n\n  <div class=\"notice\" id=\"notice\">Loading the roadmap's facts\u2026</div>\n\n  <button type=\"button\" class=\"qbar\" id=\"qbar\" hidden><b id=\"qb-left\">0</b><span id=\"qb-label\">questions for you</span><small id=\"qb-sub\">Tap to show the rows that ask them.</small></button>\n\n  <div class=\"checkbar\" id=\"checkbar\" hidden><b id=\"cb-left\">0</b><span id=\"cb-label\">checks still to try</span><small id=\"cb-sub\"></small></div>\n\n  <section aria-label=\"All steps at a glance\" id=\"stripbox\" hidden>\n    <div class=\"strip\" id=\"strip\"></div>\n    <div class=\"strip-legend\"><span id=\"strip-first\"></span><span id=\"strip-last\"></span></div>\n  </section>\n\n  <dl class=\"next\" id=\"next\" aria-label=\"What's next\" hidden></dl>\n\n  <section id=\"qfiles\" aria-label=\"Questions in chat\" hidden></section>\n\n  <nav class=\"filters\" id=\"filters\" aria-label=\"Show by status\" hidden></nav>\n\n  <main id=\"list\"></main>\n\n  <section id=\"setbox\" aria-label=\"Settings\" hidden>\n    <details class=\"sfold\" id=\"setfold\"><summary>Settings</summary><div id=\"setlist\"></div></details>\n  </section>\n\n  <footer>The facts update live as the work moves. Rows marked in blue changed within 2 hours of the newest change. Rows waiting for your look carry checks: open the row, try each one and tap Works or Doesn't work, and Claude is told at once; to say something with your answer, tap where Comment overlaps it, type, and tap Done; the part of Comment that overlaps neither says something about a check without answering it. Questions for you sit on the row they are about: pick a choice or type, then tap Answer, and Claude is told. Questions in chat shows each chat session's own questions file as it stands; answer those in that chat. You can write on any row: open it, type under \"Say something about this\" and tap Done, and Claude is told. Settings, at the bottom, shows this project's settings; a press there asks the project's main session to change one, and the page shows the new choice only once it has.</footer>\n</div>\n\n<div class=\"lb\" id=\"lb\" hidden role=\"dialog\" aria-modal=\"true\" aria-label=\"Picture full size\">\n  <div class=\"lb-bar\"><span id=\"lb-cap\"></span><span><button id=\"lb-fit\" type=\"button\">Actual size</button> <button id=\"lb-close\" type=\"button\">Close</button></span></div>\n  <div class=\"lb-scroll fit\" id=\"lb-scroll\"><img id=\"lb-img\" alt=\"\"></div>\n</div>"};
window.RM_RUN = function (document, localStorage, claude) {
(function () {
  var STATUS = [
    { key: "Being worked on now", short: "Being worked on now", c: "--s-now" },
    { key: "Ready, waiting for your look", short: "Waiting for your look", c: "--s-look" },
    { key: "Ready, known fault", short: "Known fault", c: "--s-fault" },
    { key: "Built, waiting to be merged", short: "Built, waiting to be merged", c: "--s-built" },
    { key: "Done, confirmed", short: "Done, confirmed", c: "--s-done" },
    { key: "First pass, to be redone", short: "First pass, to be redone", c: "--s-first" },
    { key: "Planned, not started", short: "Planned", c: "--s-plan" },
    { key: "Not started", short: "Not started", c: "--s-none" }
  ];
  function statusOf(s) {
    for (var i = 0; i < STATUS.length; i++) if (STATUS[i].key === s) return STATUS[i];
    return { key: s || "not recorded", short: s || "not recorded", c: "--s-none" };
  }
  var FIELDS = [["does", "Does"], ["not_yet", "Does not do yet"], ["uses", "Uses"], ["shown_working", "Shown working on"], ["waits_on_you", "Waits on you"]];
  var RECENT = "recent", NOTWORK = "notworking", TOTRY = "totry", QFOR = "questions", NOTES = "notes", NOCHK = "nochecks";
  var NOCHK_SHORT = "No checks to try: tell Claude";
  // Rows in these two states carry checks the owner marks. The checks' wording lives on the row (written by the
  // Roadmap writer); each mark is its own document in "marks", id "<row id>--<check id>", written only here.
  var CHECK_STATES = ["Ready, waiting for your look", "Ready, known fault"];
  // Wording a project may change: document "board/settings" (subtitle, steps_heading, extras_heading, checks_heading,
  // planning_heading, working_heading, done_heading).
  var settings = {};
  function setting(k, dflt) { var v = settings && settings[k]; return typeof v === "string" && v.trim() ? v : dflt; }

  var $ = function (id) { return document.getElementById(id); };
  var notice = $("notice");
  var items = null, board = null, boardStamp = null, current = "all", rows = [], emptyNote = null;
  // The row list is three folding sections, by the status each row is shown with. `foldPref` is what the person
  // folded or opened, by section, kept in this browser; Done starts folded, the other two open. `foldTemp` is a
  // section opened to show a row that was scrolled to: it stays open until the person folds it or the page reloads.
  var DONE = "Done, confirmed";
  var BUCKETS = [
    { key: "planning", name: "Planning", set: "planning_heading", has: ["Planned, not started", "Not started"] },
    { key: "working", name: "Working", set: "working_heading" },
    { key: "done", name: "Done", set: "done_heading", has: [DONE] }
  ];
  // A running roadmap (board/settings kind "running") shows only live work, in these groups, and folds finished rows
  // into a History section grouped by release or date. Display only: stored rows and ids are not changed.
  var RUN_BUCKETS = [
    { key: "now", name: "Now (being built)", set: "now_heading" },
    { key: "fault", name: "Being fixed", set: "fault_heading" },
    { key: "wait", name: "Waiting on you", set: "wait_heading" },
    { key: "next", name: "Next batch", set: "next_heading" },
    { key: "ideas", name: "Ideas", set: "ideas_heading" },
    { key: "done", name: "History", set: "history_heading" }
  ];
  function isRunning() { return settings && settings.kind === "running"; }
  function runBucket(it) {
    var s = shownStatus(it);
    if (s === DONE) return "done";
    if (s === "Being worked on now" || s === "Built, waiting to be merged") return "now";
    if (s === "Ready, known fault") return "fault";
    if (s === "Ready, waiting for your look" || noChecks(it) || qOpenOn(it._id) > 0) return "wait";
    return it.idea === true || it.idea === "true" || it.idea === "yes" ? "ideas" : "next";
  }
  function bucketOf(it) {
    if (isRunning()) return runBucket(it);
    var s = shownStatus(it);
    return BUCKETS[0].has.indexOf(s) >= 0 ? "planning" : s === DONE ? "done" : "working";
  }
  var folds = [], foldPref = {}, foldTemp = {};
  try { foldPref = JSON.parse(localStorage.getItem("roadmap-folds") || "{}") || {}; } catch (e) { foldPref = {}; }
  function foldOpen(key) { return !!foldTemp[key] || (typeof foldPref[key] === "boolean" ? foldPref[key] : key !== "done"); }
  // A done step folds its done sub-rows into itself: one row that opens to show them. Which done steps this viewer
  // left open is kept in this browser only. `planOpen` is which rows' plans are open, in page memory.
  var openDone = {}, planOpen = {}, foldQuiet = false;
  try { (JSON.parse(localStorage.getItem("roadmap-open-done") || "[]") || []).forEach(function (id) { openDone[id] = true; }); } catch (e) {}
  function saveOpenDone() { try { localStorage.setItem("roadmap-open-done", JSON.stringify(Object.keys(openDone))); } catch (e) {} }
  // a row inside a folded section, or folded inside its done step, is shown before it is scrolled to
  function reveal(node) {
    var row = node && node.closest ? node.closest("details.row") : null;
    if (row) rows.forEach(function (r) { if (r.el === row && r.under) { r.under.el.open = true; row.hidden = false; } });
    var hg = node && node.closest ? node.closest("details.hgroup") : null;
    if (hg) hg.open = true;
    var f = node && node.closest ? node.closest("details.sfold") : null;
    if (f) { foldTemp[f.dataset.key] = true; f.open = true; }
  }
  var db = null, marks = {}, marksLoaded = false, saveState = {}, drafts = {}, queues = {}, showNote = {};
  // Questions for the owner: one document each in "questions" (row, topic, question, pictures, choices, status,
  // answer, choice, asked, answered). The writer posts them; only this page writes an answer.
  // A question may carry `history`: what was asked and answered before on the same question, oldest first.
  // What the person writes on a row: one document each in "notes" (row, text, written, status "open"), written
  // only here. The writer marks one done with a done_note. `nDrafts` is what is typed for a new one, by row;
  // `nEdit` what is typed to change one, by note; both live in page memory only and survive redraws.
  var notes = {}, nDrafts = {}, nEdit = {}, nState = {}, nSaving = {}, nFold = {};
  function notesOn(rowId) {
    return Object.keys(notes).filter(function (k) { return notes[k].row === rowId; })
      .sort(function (a, b) { return String(notes[a].written || "") < String(notes[b].written || "") ? 1 : -1; });
  }
  function nOpenOn(rowId) { return notesOn(rowId).filter(function (k) { return notes[k].status !== "done"; }).length; }
  var questions = {}, qDrafts = {}, qEditing = {}, qState = {}, qSaving = {}, qFoldOpen = {}, qHistOpen = {};
  // Telling Claude about marks: what was last sent for each mark.
  var markTold = {};

  function checksOf(it) {
    if (CHECK_STATES.indexOf(it.status) < 0 || !Array.isArray(it.checks)) return [];
    return it.checks.filter(function (c) { return c && c.id && c.text; });
  }
  // A row in a Ready state that carries no check has nothing for the person to try. It is shown as a fault in how
  // the row is kept, not as waiting on the person: the main session set a status it had no checks for.
  function noChecks(it) { return CHECK_STATES.indexOf(it.status) >= 0 && !checksOf(it).length; }
  function tagOf(it) {
    var st = statusOf(shownStatus(it));
    return noChecks(it) ? { key: st.key + ". " + NOCHK_SHORT + ".", short: NOCHK_SHORT, c: "--s-fault" } : st;
  }
  function markKey(it, c) { return it._id + "--" + c.id; }
  function markOf(it, c) { var m = marks[markKey(it, c)]; return m && (m.result === "works" || m.result === "fails") ? m : null; }
  function tally(it) {
    var cs = checksOf(it), t = { all: cs.length, marked: 0, fails: 0 };
    cs.forEach(function (c) { var m = markOf(it, c); if (m) { t.marked++; if (m.result === "fails") t.fails++; } });
    return t;
  }
  // The status a row is shown with. A row whose checks are all marked shows at once what its marks give, without
  // waiting for the writer: all Works is "Done, confirmed", any Doesn't work is "Ready, known fault". Display only:
  // the page never writes the row.
  function shownStatus(it) {
    var cs = checksOf(it);
    if (!cs.length) return it.status;
    var t = tally(it);
    return t.marked < t.all ? it.status : t.fails ? "Ready, known fault" : "Done, confirmed";
  }
  // When the writer records such a row it deletes the row's marks and changes its status, and the two can arrive a
  // moment apart. Marks taken away by someone else from a row shown ahead of the database are kept on screen for a
  // few seconds (`held`, by row id), so nothing flicks back in between. `realMarks` is what the database holds.
  var realMarks = {}, held = {}, ownClears = {}, HOLD_MS = 4000;
  function mergeMarks() {
    var m = Object.assign({}, realMarks);
    Object.keys(held).forEach(function (r) {
      var h = held[r];
      if (Date.now() >= h.until) { delete held[r]; return; }
      Object.keys(h.marks).forEach(function (k) { if (!m[k]) m[k] = h.marks[k]; });
    });
    marks = m;
  }
  function fmtStamp(iso) {
    var d = new Date(iso); if (isNaN(d)) return "";
    var h = d.getHours(), ap = h < 12 ? "AM" : "PM"; h = h % 12 || 12;
    return (d.getMonth() + 1) + "/" + d.getDate() + "/" + String(d.getFullYear()).slice(2) + " at " + h + ":" + String(d.getMinutes()).padStart(2, "0") + " " + ap;
  }
  try { current = localStorage.getItem("roadmap-filter") || "all"; } catch (e) {}

  function fmtDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
    if (!m) return iso || "not recorded";
    return (+m[2]) + "/" + (+m[3]) + "/" + m[1].slice(2);
  }

  // When each row and "What's next" last changed: the database's own record of when the document was
  // last written; where the database gives none, the row's `changed` field (a date, or a date and time).
  var FRESH_WINDOW_MS = 2 * 60 * 60 * 1000; // rows changed within 2 hours of the newest change are marked blue
  function toMs(v) {
    if (v == null || v === "") return NaN;
    if (typeof v === "number") return v;
    if (v instanceof Date) return v.getTime();
    if (typeof v.toDate === "function") { try { return v.toDate().getTime(); } catch (e) { return NaN; } }
    if (typeof v.seconds === "number") return v.seconds * 1000;
    if (typeof v === "string") return Date.parse(v);
    return NaN;
  }
  function docTime(d) {
    var m = (d && d.metadata) || {};
    var c = [d && d.updatedAt, d && d.updateTime, d && d.updated_at, m.updatedAt, m.updateTime];
    for (var i = 0; i < c.length; i++) { var t = toMs(c[i]); if (isFinite(t)) return t; }
    return NaN;
  }
  function stampOf(dbMs, changed) {
    if (isFinite(dbMs)) return { ms: dbMs, timed: true };
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(changed || "");
    if (m) return { ms: new Date(+m[1], +m[2] - 1, +m[3]).getTime(), timed: false };
    var t = Date.parse(changed || "");
    return isFinite(t) ? { ms: t, timed: true } : null;
  }
  function fmtWhen(s) {
    if (!s) return "";
    var d = new Date(s.ms), out = (d.getMonth() + 1) + "/" + d.getDate() + "/" + String(d.getFullYear()).slice(2);
    if (!s.timed) return out;
    var h = d.getHours(), ap = h < 12 ? "AM" : "PM"; h = h % 12 || 12;
    return out + " " + h + ":" + String(d.getMinutes()).padStart(2, "0") + " " + ap;
  }
  function fmtWhenDate(s) { if (!s) return ""; var d = new Date(s.ms); return (d.getMonth() + 1) + "/" + d.getDate(); }
  function newestOf(list) {
    return list.reduce(function (m, s) { return s && (!m || s.ms > m.ms) ? s : m; }, null);
  }
  function sameDay(a, b) { var x = new Date(a), y = new Date(b); return x.toDateString() === y.toDateString(); }
  function isFresh(it, newest) {
    var s = it._stamp; if (!s || !newest) return false;
    // a row with a date only could have changed any time that day
    return s.timed ? newest.ms - s.ms <= FRESH_WINDOW_MS : sameDay(s.ms, newest.ms);
  }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function rowId(id) { return "row-" + id; }

  function fail(msg) {
    notice.hidden = false;
    notice.className = "notice bad";
    notice.textContent = msg;
  }

  function render() {
    if (!items) return;
    notice.hidden = true;
    var all = items.slice().sort(function (a, b) { return (a.order || 0) - (b.order || 0); });
    $("psub").textContent = setting("subtitle", isRunning() ? "What is live right now. Tap a row to see where it stands." : "Every step, in order. Tap a row to see where it stands.");
    if (!all.length) {
      notice.hidden = false; notice.className = "notice";
      notice.textContent = "Nothing is on the roadmap yet. Tell Claude the plan in your main session and the rows appear here.";
    }
    var newest = newestOf(all.map(function (it) { return it._stamp; }));
    var latest = newestOf([newest, boardStamp]);
    $("lastchange").textContent = latest ? fmtWhen(latest) : "not recorded";
    $("asof").textContent = board && board.facts_as_of ? fmtDate(board.facts_as_of) : "not recorded";

    // counts by status (tap to filter); a running roadmap shows one short line instead
    var running = isRunning();
    var counts = $("counts"); counts.textContent = "";
    if (running) {
      var live = all.filter(function (it) { return runBucket(it) !== "done"; }).length;
      var wn = all.filter(function (it) { return runBucket(it) === "wait"; }).length;
      var hn = all.length - live;
      counts.appendChild(el("span", "runline", live + " live" + (wn ? ", " + wn + " waiting on you" : "") + ", " + hn + " in history"));
    }
    if (!running) STATUS.forEach(function (s) {
      var n = all.filter(function (it) { return shownStatus(it) === s.key && !noChecks(it); }).length;
      if (!n) return;
      var b = el("button"); b.type = "button";
      var nb = el("b", null, String(n)); nb.style.color = "var(" + s.c + ")";
      b.appendChild(nb); b.appendChild(el("span", null, s.short));
      b.addEventListener("click", function () { setFilter(s.key); });
      counts.appendChild(b);
    });
    var nc = running ? 0 : all.filter(noChecks).length;
    if (nc) {
      var cb = el("button"); cb.type = "button";
      var cn = el("b", null, String(nc)); cn.style.color = "var(--s-fault)";
      cb.appendChild(cn); cb.appendChild(el("span", null, NOCHK_SHORT));
      cb.addEventListener("click", function () { setFilter(NOCHK); });
      counts.appendChild(cb);
    }

    // what's next
    var nx = $("next"); nx.textContent = "";
    var lines = (board && board.lines) || [];
    lines.forEach(function (l) { nx.appendChild(el("dt", null, l.label)); nx.appendChild(el("dd", null, l.text)); });
    if (lines.length && boardStamp) { nx.appendChild(el("dt", null, "Last written")); nx.appendChild(el("dd", "written", fmtWhen(boardStamp))); }
    nx.hidden = !lines.length;

    // strip
    var strip = $("strip"); strip.textContent = "";
    var stepRows = all.filter(function (it) { return it.kind === "step"; });
    stepRows.forEach(function (it) {
      var st = tagOf(it);
      var b = el("button", null, it.number); b.type = "button";
      b.style.background = "var(" + st.c + ")";
      b.title = it.name + " (" + it.number + "): " + st.key;
      b.setAttribute("aria-label", it.name + ", step " + it.number + ", " + st.key);
      b.addEventListener("click", function () {
        setFilter("all");
        var r = $(rowId(it._id)); if (!r) return;
        reveal(r); r.open = true;
        r.scrollIntoView({ behavior: "smooth", block: "center" });
        r.querySelector("summary").focus({ preventScroll: true });
      });
      strip.appendChild(b);
    });
    $("stripbox").hidden = running || stepRows.length < 2;
    if (stepRows.length && !running) {
      $("strip-first").textContent = "Step " + stepRows[0].number;
      $("strip-last").textContent = "Step " + stepRows[stepRows.length - 1].number;
    }

    // list, keeping rows the viewer opened and any note box being typed in
    var ae = document.activeElement, focusKey = null, selA = 0, selB = 0;
    if (ae && ae.tagName === "TEXTAREA" && ae.dataset.key) { focusKey = ae.dataset.key; selA = ae.selectionStart; selB = ae.selectionEnd; }
    var openIds = {}, moreIds = {};
    if (!rows.length) Object.keys(openDone).forEach(function (id) { openIds[id] = true; });
    rows.forEach(function (r) { if (r.el.open) openIds[r.it._id] = true; if (r.more && r.more.open) moreIds[r.it._id] = true; });
    rows = []; folds = [];
    var listEl = $("list"); listEl.textContent = "";
    // questions whose row is not on the roadmap still show, at the top, so none is lost
    var known = {}; all.forEach(function (it) { known[it._id] = true; });
    var orphans = Object.keys(questions).filter(function (k) { return !known[questions[k].row || ""]; });
    var ob = makeQuestions(orphans, "");
    if (ob) {
      var osec = el("section"); osec.appendChild(el("h2", null, "Questions not tied to a row"));
      ob.classList.add("qorphan"); osec.appendChild(ob); listEl.appendChild(osec);
    }
    var isStep = function (it) { return it.kind === "step" || it.kind === "phase"; };
    var byId = {}, where = {};
    all.forEach(function (it) { byId[it._id] = it; where[it._id] = bucketOf(it); });
    var wrap = el("div", "folds");
    // a running roadmap numbers its live rows 1, 2, 3 in page order (display only; stored ids and numbers stay)
    if (running) {
      var dn = 0;
      RUN_BUCKETS.forEach(function (b) {
        all.filter(function (it) { return where[it._id] === b.key; }).forEach(function (it) { it._dn = b.key === "done" ? "" : String(++dn); });
      });
    } else all.forEach(function (it) { delete it._dn; });
    (running ? RUN_BUCKETS : BUCKETS).forEach(function (b) {
      var mine = all.filter(function (it) { return where[it._id] === b.key; });
      if (!mine.length) return;                                  // an empty section is not shown
      var fold = el("details", "sfold"), sum = el("summary");
      fold.id = "sec-" + b.key; fold.dataset.key = b.key;
      sum.appendChild(el("span", null, setting(b.set, b.name))); sum.appendChild(document.createTextNode(" "));
      sum.appendChild(el("span", "n", "(" + mine.length + ")"));
      // a tap or a key press on the heading is the person's choice; it is remembered when no filter is on
      sum.addEventListener("click", function () {
        if (current !== "all") return;
        foldPref[b.key] = !fold.open; delete foldTemp[b.key];
        try { localStorage.setItem("roadmap-folds", JSON.stringify(foldPref)); } catch (e) {}
      });
      fold.appendChild(sum);
      if (running) {
        var groups = [], gby = {};
        if (b.key === "done") {
          mine.slice().sort(function (x, y) { return (y._stamp ? y._stamp.ms : 0) - (x._stamp ? x._stamp.ms : 0); }).forEach(function (it) {
            var gk = it.release ? String(it.release) : fmtWhenDate(it._stamp);
            if (!gby[gk]) { gby[gk] = { key: gk, label: gk, list: [], stamp: it._stamp }; groups.push(gby[gk]); }
            gby[gk].list.push(it);
          });
          groups.forEach(function (g) { var dt = fmtWhenDate(g.stamp); if (g.key !== dt && dt) g.label = g.key + ", " + dt; });
        } else groups = [{ key: "", label: "", list: mine }];
        groups.forEach(function (g) {
          var host = fold;
          if (g.label) {
            host = el("details", "hgroup"); host.dataset.key = "h-" + g.key;
            var hs = el("summary"); hs.appendChild(el("span", null, g.label)); hs.appendChild(document.createTextNode(" "));
            hs.appendChild(el("span", "n", "(" + g.list.length + ")")); host.appendChild(hs);
            fold.appendChild(host);
          }
          var rbox = el("div", "list");
          g.list.forEach(function (it) { rbox.appendChild(makeRow(it, newest, openIds[it._id], moreIds[it._id], b.key, null, 0)); });
          host.appendChild(rbox);
        });
        wrap.appendChild(fold);
        folds.push({ el: fold, key: b.key });
        return;
      }
      // steps and their phases first, then the other work; each kind under its own small heading when both are here
      var parts = [{ title: setting("steps_heading", "Steps"), list: mine.filter(isStep) },
                   { title: setting("extras_heading", "Other work"), list: mine.filter(function (it) { return !isStep(it); }) }];
      var both = parts[0].list.length && parts[1].list.length;
      parts.forEach(function (part) {
        if (!part.list.length) return;
        if (both) fold.appendChild(el("h3", "sub", part.title));
        var box = el("div", "list");
        // each sub-row sits right under its step, whatever its order number, when the step is in this section
        var here = {}, list = [];
        part.list.forEach(function (it) { here[it._id] = true; });
        part.list.forEach(function (it) {
          if (it.kind === "phase" && it.parent && here[it.parent] && byId[it.parent].kind === "step") return;
          list.push(it);
          if (it.kind === "step") part.list.forEach(function (c) { if (c.kind === "phase" && c.parent === it._id) list.push(c); });
        });
        list.forEach(function (it) {
          // a phase sits under its step when the step is in this section; elsewhere it names its step
          var parent = it.kind === "phase" ? byId[it.parent] : null;
          var away = parent && where[parent._id] !== b.key ? parent : null;
          // a done step counts the done sub-rows folded inside it
          var nk = b.key === "done" && it.kind === "step" ? list.filter(function (c) { return c.kind === "phase" && c.parent === it._id; }).length : 0;
          box.appendChild(makeRow(it, newest, openIds[it._id], moreIds[it._id], b.key, away, nk));
        });
        fold.appendChild(box);
      });
      wrap.appendChild(fold);
      folds.push({ el: fold, key: b.key });
    });
    listEl.appendChild(wrap);
    var recs = {}; rows.forEach(function (r) { recs[r.it._id] = r; });
    rows.forEach(function (r) { var up = r.it.kind === "phase" ? recs[r.it.parent] : null; r.under = up && up.nk && up.bucket === r.bucket ? up : null; });
    emptyNote = el("div", "empty-note", "Nothing here with this choice."); emptyNote.hidden = true;
    listEl.appendChild(emptyNote);

    // filters
    var filtersEl = $("filters"); filtersEl.textContent = "";
    addFilter("all", "All", null);
    addFilter(QFOR, "Questions for you", "--accent");
    addFilter(NOTES, "Your notes (" + Object.keys(notes).filter(function (k) { return notes[k].status !== "done" && known[notes[k].row]; }).length + ")", "--fresh");
    addFilter(RECENT, "Latest changes", "--fresh");
    addFilter(TOTRY, "Still to check", "--s-look");
    addFilter(NOTWORK, "Not working", "--s-fault");
    STATUS.forEach(function (s) { if (all.some(function (it) { return shownStatus(it) === s.key && !noChecks(it); })) addFilter(s.key, s.short, s.c); });
    if (all.some(noChecks)) addFilter(NOCHK, NOCHK_SHORT, "--s-fault");
    filtersEl.hidden = !all.length;
    var keys = Array.prototype.map.call(filtersEl.children, function (b) { return b.dataset.key; });
    if (keys.indexOf(current) < 0) current = "all";
    if (focusKey) {
      var ta = document.querySelector('textarea[data-key="' + focusKey.replace(/"/g, "") + '"]');
      if (ta) { var r0 = ta.closest("details"); if (r0) r0.open = true; ta.focus({ preventScroll: true }); try { ta.setSelectionRange(selA, selB); } catch (e) {} }
    }
    updateQuestionCount();
    updateChecks(newest);
  }

  // ---- questions for the owner ----
  var LETTERS = "abcdefghijklmnopqrstuvwxyz";
  function qStatus(q) { return q.status === "answered" || q.status === "done" ? q.status : "open"; }
  function qOpenOn(rowId) { return Object.keys(questions).filter(function (k) { return questions[k].row === rowId && qStatus(questions[k]) === "open"; }).length; }
  function qChoices(q) { return Array.isArray(q.choices) ? q.choices.filter(function (c) { return c != null && String(c).trim(); }) : []; }
  function cleanChoice(t) { return String(t == null ? "" : t).replace(/^\s*([a-z]|\d+)\s*[.):-]\s*/i, ""); }
  function qPics(q) {
    return (Array.isArray(q.pictures) ? q.pictures : []).map(function (p) { return typeof p === "string" ? { url: p } : p; })
      .filter(function (p) { return p && typeof p.url === "string" && /^(https:\/\/|\/)/.test(p.url); });
  }
  function qHistory(q) {
    return (Array.isArray(q.history) ? q.history : []).filter(function (e) { return e && typeof e === "object" && e.text != null && String(e.text).trim(); });
  }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
  function mdInline(s) {
    s = esc(s);
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/\[([^\]]+)\]\((https:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>");
    return s;
  }
  function mdBlock(t) {
    var lines = String(t == null ? "" : t).replace(/\r/g, "").split("\n"), out = [], list = null, para = [], tbl = null;
    function fp() { if (para.length) { out.push("<p>" + para.map(mdInline).join("<br>") + "</p>"); para = []; } }
    function fl() { if (list) { out.push("</" + list + ">"); list = null; } }
    function cells(l) { return l.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(function (c) { return mdInline(c.trim()); }); }
    function ft() {
      if (!tbl) return;
      var h = "<div class=\"tscroll\"><table>";
      tbl.forEach(function (r, i) { var tag = i === 0 && tbl.head ? "th" : "td"; h += "<tr>" + r.map(function (c) { return "<" + tag + ">" + c + "</" + tag + ">"; }).join("") + "</tr>"; });
      out.push(h + "</table></div>"); tbl = null;
    }
    lines.forEach(function (l) {
      var m;
      if (/^\s*\|.*\|\s*$/.test(l)) {
        fp(); fl();
        if (/^\s*\|[\s:|-]+\|\s*$/.test(l)) { if (tbl && tbl.length === 1) tbl.head = true; return; }
        if (!tbl) tbl = [];
        tbl.push(cells(l)); return;
      }
      ft();
      if ((m = /^(#{1,4})\s+(.*)$/.exec(l))) { fp(); fl(); var n = m[1].length + 2; out.push("<h" + n + ">" + mdInline(m[2]) + "</h" + n + ">"); }
      else if ((m = /^\s*[-*]\s+(.*)$/.exec(l))) { fp(); if (list !== "ul") { fl(); out.push("<ul>"); list = "ul"; } out.push("<li>" + mdInline(m[1]) + "</li>"); }
      else if ((m = /^\s*(\d+)[.)]\s+(.*)$/.exec(l))) { fp(); if (list !== "ol") { fl(); out.push("<ol start=\"" + m[1] + "\">"); list = "ol"; } out.push("<li>" + mdInline(m[2]) + "</li>"); }
      else if (!l.trim()) { fp(); fl(); }
      else { fl(); para.push(l); }
    });
    fp(); fl(); ft();
    return out.join("");
  }
  function mdEl(cls, text) { var e = el("div", cls); e.innerHTML = mdBlock(text); return e; }

  // the questions box for a row (or, with rowId "", for the given ids not tied to a row)
  function makeQuestions(ids, rowId) {
    if (rowId) ids = Object.keys(questions).filter(function (k) { return questions[k].row === rowId; });
    if (!ids.length) return null;
    function t(k) { var q = questions[k]; return String(q.answered || q.asked || ""); }
    var open = ids.filter(function (k) { return qStatus(questions[k]) === "open"; })
      .sort(function (a, b) { return String(questions[a].asked || "") < String(questions[b].asked || "") ? -1 : 1; });
    var answered = ids.filter(function (k) { return qStatus(questions[k]) === "answered"; }).sort(function (a, b) { return t(a) < t(b) ? 1 : -1; });
    var done = ids.filter(function (k) { return qStatus(questions[k]) === "done"; }).sort(function (a, b) { return t(a) < t(b) ? 1 : -1; });
    var box = el("div", "questions");
    if (open.length) box.appendChild(el("h3", null, open.length === 1 ? "A question for you" : open.length + " questions for you"));
    else if (answered.length) box.appendChild(el("h3", "quiet", "Your answers"));
    open.concat(answered).forEach(function (k) { box.appendChild(qCard(k, questions[k])); });
    if (done.length) {
      var key = rowId || "-orphans-";
      var fold = el("details", "more"); if (qFoldOpen[key]) fold.open = true;
      fold.addEventListener("toggle", function () { qFoldOpen[key] = fold.open; });
      fold.appendChild(el("summary", null, "Earlier questions, already acted on (" + done.length + ")"));
      var inner = el("div", "questions"); inner.style.borderTop = "0";
      done.forEach(function (k) { inner.appendChild(qCard(k, questions[k])); });
      fold.appendChild(inner);
      if (open.length || answered.length) box.appendChild(fold);
      else { var wrap = el("div"); wrap.appendChild(fold); return wrap; }
    }
    return box;
  }

  function qCard(id, q) {
    var st = qStatus(q);
    var c = el("article", "qcard" + (st === "open" ? "" : " answered")); c.id = "q-" + id;
    var h = el("div", "qhead");
    h.appendChild(el("span", "qtopic", q.topic || "Question"));
    var w = st === "open" ? q.asked : (q.answered || q.asked);
    if (w) h.appendChild(el("span", "qwhen", (st === "open" ? "Asked " : "Answered ") + fmtStamp(w)));
    c.appendChild(h);
    c.appendChild(mdEl("qtext md", q.question || ""));
    var hist = qHistory(q);
    if (hist.length) {
      var hf = el("details", "more qhist"); hf.id = "qh-" + id; if (qHistOpen[id]) hf.open = true;
      hf.addEventListener("toggle", function () { qHistOpen[id] = hf.open; });
      hf.appendChild(el("summary", null, "Earlier on this question (" + hist.length + ")"));
      var hl = el("div", "qhist-list");
      hist.forEach(function (e) {
        var mine = e.who === "you", stamp = e.at ? fmtStamp(e.at) : "";
        var item = el("div", "qhist-item" + (mine ? " you" : ""));
        item.appendChild(el("span", "k", (mine ? "You wrote" : e.who === "asked again" ? "Asked again" : "Asked") + (stamp ? " " + stamp : "")));
        if (!mine && e.topic && String(e.topic).trim()) item.appendChild(el("span", "t", String(e.topic)));
        // the person's own words are shown as plain text; question wording is drawn like the question itself
        item.appendChild(mine ? el("div", "v", String(e.text)) : mdEl("v md", String(e.text)));
        hl.appendChild(item);
      });
      hf.appendChild(hl); c.appendChild(hf);
    }
    var pics = qPics(q);
    if (pics.length) {
      var pb = el("div", "pics");
      pics.forEach(function (p, i) {
        var fig = el("figure", "pic"), b = el("button"); b.type = "button";
        b.setAttribute("aria-label", "Show full size: " + (p.caption || "picture " + (i + 1)));
        var img = el("img"); img.src = p.url; img.alt = p.caption || "Picture " + (i + 1); img.loading = "lazy";
        b.appendChild(img); b.addEventListener("click", function () { openLb(p); });
        fig.appendChild(b); if (p.caption) fig.appendChild(el("figcaption", null, p.caption));
        pb.appendChild(fig);
      });
      c.appendChild(pb);
    }
    if (st === "open" || (st === "answered" && qEditing[id])) c.appendChild(qForm(id, q));
    else {
      var a = el("div", "qans");
      a.appendChild(el("span", "k", "Your answer"));
      a.appendChild(el("span", "v", q.answer || "(none)"));
      if (q.done_note) { a.appendChild(el("span", "k", "What changed")); a.appendChild(mdEl("v md", q.done_note)); }
      c.appendChild(a);
      if (st === "answered") {
        var row = el("div", "qrow");
        var ch = el("button", "qbtn quiet", "Change answer"); ch.type = "button"; ch.id = "qe-" + id;
        ch.addEventListener("click", function () { qEditing[id] = true; delete qDrafts[id]; delete qState[id]; render(); });
        row.appendChild(ch); qMsg(row, id); c.appendChild(row);
      }
    }
    return c;
  }

  function qDraft(id, q) {
    if (!qDrafts[id]) {
      var choice = null, text = "", ch = qChoices(q);
      if (qStatus(q) === "answered") {
        var i = q.choice ? LETTERS.indexOf(String(q.choice).toLowerCase()) : -1;
        if (i >= 0 && i < ch.length) { choice = i; text = q.note || ""; } else text = q.answer || "";
      }
      qDrafts[id] = { choice: choice, text: text };
    }
    return qDrafts[id];
  }

  function qMsg(row, id) {
    var m = qState[id]; if (!m) return;
    var s = el("span", "state" + (m.err ? " err" : m.ok ? " ok" : ""), m.text);
    s.setAttribute("role", "status"); row.appendChild(s);
  }

  function qForm(id, q) {
    var f = el("div", "qform"), dr = qDraft(id, q), ch = qChoices(q), btn;
    function ready() { btn.disabled = !!qSaving[id] || (dr.choice == null && !dr.text.trim()); }
    if (ch.length) {
      var box = el("div", "qchoices"); box.setAttribute("role", "group"); box.setAttribute("aria-label", "Choices");
      ch.forEach(function (c, i) {
        var b = el("button", "qchoice"); b.type = "button"; b.id = "qc-" + id + "-" + i;
        b.setAttribute("aria-pressed", dr.choice === i ? "true" : "false");
        b.appendChild(el("span", "cl", LETTERS[i])); b.appendChild(el("span", null, cleanChoice(c)));
        b.addEventListener("click", function () {
          dr.choice = dr.choice === i ? null : i;
          Array.prototype.forEach.call(box.children, function (x, j) { x.setAttribute("aria-pressed", dr.choice === j ? "true" : "false"); });
          ready();
        });
        box.appendChild(b);
      });
      f.appendChild(box);
    }
    var taId = "qt-" + id;
    var lab = el("label", null, ch.length ? "Anything to add, or your own answer" : "Your answer"); lab.htmlFor = taId;
    var ta = el("textarea"); ta.id = taId; ta.dataset.key = "q-" + id; ta.rows = 3; ta.value = dr.text;
    ta.addEventListener("input", function () { dr.text = ta.value; ready(); });
    f.appendChild(lab); f.appendChild(ta);
    var row = el("div", "qrow");
    btn = el("button", "qbtn", qSaving[id] ? "Saving…" : "Answer"); btn.type = "button"; btn.id = "qa-" + id;
    btn.addEventListener("click", function () { qSave(id); });
    ready(); row.appendChild(btn);
    if (qEditing[id]) {
      var keep = el("button", "qbtn quiet", "Keep my old answer"); keep.type = "button";
      keep.addEventListener("click", function () { delete qEditing[id]; delete qDrafts[id]; delete qState[id]; render(); });
      row.appendChild(keep);
    }
    qMsg(row, id); f.appendChild(row);
    return f;
  }

  function qSave(id) {
    var q = questions[id];
    if (!q || qSaving[id]) return;
    if (!db) { qState[id] = { err: true, text: "Not saved: the page is not connected. Open it signed in to Claude." }; render(); return; }
    if (qStatus(q) === "done") { qState[id] = { err: true, text: "Claude already acted on this one, so it can't be changed." }; render(); return; }
    var dr = qDraft(id, q), text = dr.text.trim(), ch = qChoices(q);
    var letter = dr.choice != null ? LETTERS[dr.choice] : "";
    var answer = letter ? letter + ". " + cleanChoice(ch[dr.choice]) + (text ? "\n" + text : "") : text;
    if (!answer) return;
    qSaving[id] = true; qState[id] = { text: "Saving…" }; render();
    db.doc("questions/" + id).update({ status: "answered", answer: answer, choice: letter, note: letter ? text : "", answered: new Date().toISOString() }).then(function () {
      qSaving[id] = false; delete qEditing[id]; delete qDrafts[id];
      qState[id] = { ok: true, text: "✓ Saved. Telling Claude…" }; render();
      tellClaude(id, q, answer);
    }, function (e) {
      qSaving[id] = false;
      var code = e && e.code;
      qState[id] = { err: true, text: code === "invalid_argument" || code === "not_granted" ? "Not saved: only the page's owner and editors can answer."
        : code === "not_found" ? "Not saved: this question was taken down." : "Not saved: no connection right now. Tap Answer again." };
      render();
    });
  }

  // One comment sent to Claude, so a watching Claude session is told at once; where none is listening the comment is
  // left on the page. `lead` opens the line shown to the person ("✓ Saved."), `what` names the thing ("answer", "mark"),
  // `target` gives the element the comment is anchored at, `done(text, notTold)` receives the line to show.
  function sendToClaude(line, target, lead, what, done) {
    if (line.length > 3500) line = line.slice(0, 3500) + "…";
    claude.use("comments").then(function (cm) {
      if (!cm) { done(lead + " Claude could not be told from here; it will see the " + what + " when it next checks.", true); return; }
      return cm.anchorFor(target() || document.querySelector("header.tb")).then(function (anchor) {
        // Where Claude was not told, the comment is left and the person is told the real reason; the same reason is written into the comment's text for Claude.
        function plain(reason, short) {
          return cm.create({ anchor: anchor, text: line + "\n[Not sent to Claude: " + short + "]" }).then(function () {
            done(lead + " " + reason + " A comment was left for Claude to read at your next message.");
          });
        }
        return cm.canSendToClaude().then(function (can) { return { can: can }; }, function (e) { return { err: e }; }).then(function (r) {
          if (r.err) { var c = (r.err && r.err.code) || "unknown"; return plain("claude.ai could not say whether Claude can be told (" + c + ").", "check_failed:" + c); }
          var can = r.can;
          if (can === "no_session") return plain("No Claude session is watching this roadmap right now.", "no_session");
          if (can === "writers_only") return plain("claude.ai does not see you as an editor of this roadmap.", "writers_only");
          if (can === "off") return plain("Sending to Claude is off in this view.", "off");
          if (can !== "available") return plain("claude.ai gave an unknown answer (" + can + ").", "unknown:" + can);
          return cm.sendToClaude({ anchor: anchor, text: line }).then(function () { done(lead + " Claude has been told."); },
            function (e) { if (e && e.code === "claude_unavailable") return plain("claude.ai did not count this as your own click, so Claude was not told.", "not_own_click"); throw e; });
        });
      });
    }).catch(function (e) {
      var code = e && e.code;
      done(code === "consent_required" || code === "forbidden" || code === "not_granted"
        ? lead + " Claude was not told because commenting from this page is not allowed here."
        : lead + " Claude could not be told just now; it will see the " + what + " when it next checks.", true);
    });
  }
  function whereOf(rowId) {
    var it = (items || []).filter(function (x) { return x._id === rowId; })[0];
    return it ? (it.kind === "step" ? it.name + " (" + it.number + ")" : it.name) : "no row";
  }

  // After an answer saves, Claude is told.
  function tellClaude(id, q, answer) {
    var line = "Answered on the roadmap: the question \"" + (q.topic || id) + "\" on " + whereOf(q.row) + " (questions/" + id + "): " + answer;
    sendToClaude(line, function () { return $("q-" + id); }, "✓ Saved.", "answer",
      function (t, err) { qState[id] = { ok: !err, err: !!err, text: t }; render(); });
  }

  // After a mark saves or is cleared, Claude is told the same way. `data` is what was written; null means cleared.
  // The same mark is not sent twice in a row.
  function tellMark(it, c, data) {
    var key = markKey(it, c), note = data ? String(data.note || "").trim() : "";
    var sig = data ? data.result + "|" + note : "cleared", last = markTold[key];
    if (last && last.sig === sig) { if (last.st) { saveState[key] = last.st; showState(key); } return; }
    var mine = markTold[key] = { sig: sig, st: null };
    var said = !data ? "cleared" : data.result === "works" ? "Works" + (note ? ". Note: " + note : "") : "Doesn't work" + (note ? ". Note: " + note : ", no note");
    var line = "Marked on the roadmap: the check \"" + c.text + "\" on " + whereOf(it._id) + " (marks/" + key + "): " + said;
    sendToClaude(line, function () { var e = findEl(key); return e ? e.item : $(rowId(it._id)); }, data ? "✓ Saved." : "✓ Cleared.", "mark",
      function (t, err) {
        mine.st = { s: "ok", msg: t, bad: !!err };
        if (markTold[key] === mine && saveState[key] && saveState[key].s === "ok") { saveState[key] = mine.st; showState(key); }
      });
  }

  var pulseOpen = 0;
  // Pulse while a row question or any session's questions file has an open question
  function applyPulse() {
    var chat = Object.keys(qfiles).some(function (k) { return Number(qfiles[k] && qfiles[k].open) > 0; });
    $("qbar").parentNode.classList.toggle("qpulse", pulseOpen > 0 || chat);
  }
  function updateQuestionCount() {
    var left = Object.keys(questions).filter(function (k) { return qStatus(questions[k]) === "open"; }).length;
    $("qbar").hidden = !left;
    pulseOpen = left;
    applyPulse();
    $("qb-left").textContent = String(left);
    $("qb-label").textContent = left === 1 ? "question for you" : "questions for you";
    Array.prototype.forEach.call($("filters").children, function (b) {
      if (b.dataset.key === QFOR) b.querySelector(".lbl").textContent = "Questions for you (" + left + ")";
    });
  }
  $("qbar").addEventListener("click", function () { setFilter(QFOR); var f = document.querySelector(".qcard"); if (f) { reveal(f); f.scrollIntoView({ behavior: "smooth", block: "center" }); } });

  function openLb(p) {
    $("lb-img").src = p.url; $("lb-img").alt = p.caption || "";
    $("lb-cap").textContent = p.caption || "";
    $("lb-scroll").classList.add("fit"); $("lb-fit").textContent = "Actual size";
    $("lb").hidden = false; $("lb-close").focus();
  }
  $("lb-close").addEventListener("click", function () { $("lb").hidden = true; });
  $("lb-fit").addEventListener("click", function () {
    var s = $("lb-scroll"); s.classList.toggle("fit");
    $("lb-fit").textContent = s.classList.contains("fit") ? "Actual size" : "Fit";
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") $("lb").hidden = true; });

  // ---- checks: the owner's Works / Doesn't work marks ----
  function makeChecks(it) {
    var cs = checksOf(it);
    if (!cs.length) return null;
    var box = el("div", "checks");
    box.appendChild(el("h3", null, setting("checks_heading", "Try these")));
    var els = [];
    cs.forEach(function (c, i) {
      var key = markKey(it, c);
      var item = el("div", "check");
      item.appendChild(el("p", null, c.text));
      if (c.needs_person) item.appendChild(el("span", "quiet-line", "Why only you can check this: " + c.needs_person));
      var ch = el("div", "choices"); ch.setAttribute("role", "group"); ch.setAttribute("aria-label", "Answer this check");
      // Five places to press, in reading order, drawn as three overlapping buttons. The two plain answers send at once.
      // The two places where Comment overlaps an answer open the box for that answer; they show no words of their own
      // and are named for the ear. The part of Comment that overlaps neither opens the box for a comment that answers
      // nothing.
      var yes = el("button", "yes", "Works"); yes.type = "button";
      var yesC = el("button", "yes c"); yesC.type = "button"; yesC.setAttribute("aria-label", "Works, with a comment");
      var noC = el("button", "no c"); noC.type = "button"; noC.setAttribute("aria-label", "Doesn't work, with a comment");
      var no = el("button", "no", "Doesn't work"); no.type = "button";
      var only = el("button", "only", "Comment"); only.type = "button"; only.setAttribute("aria-label", "Comment only, without marking this check");
      yes.title = "Works"; yesC.title = "Works, with a comment"; noC.title = "Doesn't work, with a comment"; no.title = "Doesn't work"; only.title = "Comment only: marks nothing";
      yes.id = "yes-" + key; no.id = "no-" + key; yesC.id = "yesc-" + key; noC.id = "noc-" + key; only.id = "cmt-" + key;
      ch.appendChild(yes); ch.appendChild(yesC); ch.appendChild(noC); ch.appendChild(no); ch.appendChild(only);
      ["w", "k", "d"].forEach(function (s) { var r = el("span", "ring " + s); r.setAttribute("aria-hidden", "true"); ch.appendChild(r); });
      // where the pointer or focus is, in words, in the free space beside Comment (wide screens only)
      var hint = el("span", "hint"); hint.setAttribute("aria-hidden", "true"); ch.appendChild(hint);
      [yes, yesC, noC, no, only].forEach(function (b) {
        function on() { hint.textContent = b.title; }
        function off() { if (hint.textContent === b.title) hint.textContent = ""; }
        b.addEventListener("mouseenter", on); b.addEventListener("focus", on);
        b.addEventListener("mouseleave", off); b.addEventListener("blur", off);
      });
      item.appendChild(ch);
      // The three comment places open this box. Nothing is written or sent until Done is tapped: `showNote[key]`
      // holds what is waiting ("works", "fails", or "note" for a comment that answers nothing) while the box is open,
      // `drafts[key]` what is typed. Both live in page memory only, so they survive redraws.
      var nb = el("div", "notebox"); nb.hidden = true;
      var taId = "note-" + key;
      var lab = el("label", null, "Do you want to say something about it?"); lab.htmlFor = taId;
      var ta = el("textarea"); ta.id = taId; ta.dataset.key = key; ta.rows = 3;
      ta.value = noteFor(key, markOf(it, c));
      ta.placeholder = "Say what you saw, or leave this empty.";
      var done = el("button", null, "Done"); done.type = "button"; done.id = "done-" + key;
      nb.appendChild(lab); nb.appendChild(ta); nb.appendChild(done);
      nb.appendChild(el("small", null, "Nothing is sent until you tap Done.")); item.appendChild(nb);
      // an answer already sent: what was said, and a way to change it
      var said = el("div", "qans said"); said.hidden = true;
      said.appendChild(el("span", "k", "What you said"));
      var saidText = el("span", "v"); said.appendChild(saidText);
      var change = el("button", "clear", "Change what I said"); change.type = "button"; change.id = "change-" + key;
      said.appendChild(change); item.appendChild(said);
      // an answer sent with no words: a way to add some
      var say = el("button", "clear say", "Say something"); say.type = "button"; say.id = "say-" + key; say.hidden = true;
      item.appendChild(say);
      var foot = el("div", "cfoot");
      var state = el("span", "state"); state.setAttribute("role", "status"); state.setAttribute("aria-live", "polite");
      var clear = el("button", "clear", "Clear my mark"); clear.type = "button";
      foot.appendChild(state); foot.appendChild(clear); item.appendChild(foot);

      // open the box for an answer, or switch the answer waiting in an open box; typed words are kept
      function openBox(answer) {
        showNote[key] = answer;
        if (saveState[key] && saveState[key].s === "err") delete saveState[key];
        ta.value = noteFor(key, markOf(it, c));
        updateChecks(); ta.focus();
      }
      function sentAnswer() { var m = markOf(it, c); return m ? m.result : "works"; }
      // a plain answer: any open box and its words are dropped, the mark is written with no note and Claude is told
      function plain(answer) {
        showNote[key] = false; delete drafts[key];
        writeMark(it, c, { result: answer, note: "" }, true);
      }
      yes.addEventListener("click", function () { plain("works"); });
      no.addEventListener("click", function () { plain("fails"); });
      yesC.addEventListener("click", function () { openBox("works"); });
      noC.addEventListener("click", function () { openBox("fails"); });
      only.addEventListener("click", function () { openBox("note"); });
      change.addEventListener("click", function () { openBox(sentAnswer()); });
      say.addEventListener("click", function () { openBox(sentAnswer()); });
      ta.addEventListener("input", function () { drafts[key] = ta.value; });
      done.addEventListener("click", function () {
        var note = drafts[key] != null ? drafts[key] : ta.value;
        if (showNote[key] === "note") {                  // a comment only: a note on the row that names the check; no mark
          if (!String(note).trim()) { saveState[key] = { s: "err", msg: "Nothing to send: type your comment first." }; showState(key); ta.focus(); return; }
          showNote[key] = false; delete drafts[key];
          updateChecks(); checkNote(it, c, String(note).trim());
          return;
        }
        var answer = showNote[key] === "works" ? "works" : "fails";
        drafts[key] = note; showNote[key] = false;
        writeMark(it, c, { result: answer, note: note }, true);
      });
      clear.addEventListener("click", function () {
        var m = markOf(it, c), unsent = showNote[key] && !(m && m.result === showNote[key]);
        showNote[key] = false; delete drafts[key];
        if (unsent) { updateChecks(); return; }   // an answer never sent: close the box, write and send nothing
        writeMark(it, c, null, true);
      });
      box.appendChild(item);
      els.push({ key: key, it: it, c: c, item: item, yes: yes, no: no, nb: nb, ta: ta, state: state, clear: clear, said: said, saidText: saidText, say: say, yesC: yesC, noC: noC, only: only, lab: lab });
    });
    return { box: box, els: els };
  }

  // A comment on a check that answers nothing: one note on the check's row, naming the check, and Claude is told
  // once. The check's own line reports it. No mark is written.
  function checkNote(it, c, text) {
    var key = markKey(it, c), id = it._id;
    function back(msg) { saveState[key] = { s: "err", msg: msg }; drafts[key] = text; showNote[key] = "note"; updateChecks(); }
    if (!db) { back("Not saved: the page is not connected. Open it signed in to Claude."); return; }
    var k = id + "--" + Date.now().toString(36) + Math.floor(Math.random() * 36).toString(36);
    saveState[key] = { s: "saving" }; showState(key);
    db.doc("notes/" + k).set({ row: id, text: text, written: new Date().toISOString(), status: "open", check: c.id, check_text: c.text }).then(function () {
      saveState[key] = { s: "ok", msg: "✓ Comment saved. Telling Claude…" }; showState(key);
      sendToClaude("Written on the roadmap: a comment on the check \"" + c.text + "\" on " + whereOf(id) + " (notes/" + k + "), not an answer to it: " + text,
        function () { return $("note-" + k) || $(rowId(id)); }, "✓ Comment saved.", "note",
        function (t, err) { saveState[key] = { s: "ok", msg: t, bad: !!err }; showState(key); });
    }, function (e) { back(noteErr(e, "Not saved: this row was taken down.")); });
  }

  function noteFor(key, m) {
    if (drafts[key] != null) return drafts[key];
    return m && (!showNote[key] || m.result === showNote[key]) ? m.note || "" : "";
  }

  function writeMark(it, c, data, tell) {
    var key = markKey(it, c);
    if (!data) ownClears[key] = Date.now();
    if (held[it._id]) { delete held[it._id]; mergeMarks(); }
    if (!db) { saveState[key] = { s: "err", msg: "Not saved: the page is not connected. Open it signed in to Claude." }; showState(key); return; }
    saveState[key] = { s: "saving" }; showState(key);
    var sentNote = data ? data.note : null;
    queues[key] = (queues[key] || Promise.resolve()).then(function () {
      var ref = db.doc("marks/" + key);
      function once() {
        return data ? ref.set({ row: it._id, check: c.id, text: c.text, result: data.result, note: data.note || "", marked: new Date().toISOString() }) : ref.delete();
      }
      return once().catch(function (e) {
        if (e && e.code === "unavailable") return new Promise(function (res) { setTimeout(res, 600 + Math.random() * 800); }).then(once);
        throw e;
      });
    }).then(function () {
      if (drafts[key] != null && drafts[key] === sentNote) delete drafts[key];
      saveState[key] = tell ? { s: "ok", msg: (data ? "✓ Saved." : "✓ Cleared.") + " Telling Claude…" } : { s: "ok" }; showState(key);
      if (tell) tellMark(it, c, data);
    }, function (e) {
      var code = e && e.code, msg;
      if (code === "invalid_argument" || code === "not_granted") msg = "Not saved: only the page's owner and editors can mark checks.";
      else if (code === "quota_exceeded") msg = "Not saved: the roadmap's storage is full.";
      else if (code === "revoked") msg = "Not saved: this page lost its connection. Open it again.";
      else msg = "Not saved: no connection right now. Tap again to retry.";
      saveState[key] = { s: "err", msg: msg };
      if (data && data.note) { showNote[key] = data.result; updateChecks(); } else showState(key);   // a failed save puts the box and its words back
    });
  }

  function findEl(key) {
    for (var i = 0; i < rows.length; i++) {
      var cx = rows[i].cx; if (!cx) continue;
      for (var j = 0; j < cx.els.length; j++) if (cx.els[j].key === key) return cx.els[j];
    }
    return null;
  }

  function showState(key) {
    var e = findEl(key); if (!e) return;
    var st = saveState[key], m = markOf(e.it, e.c);
    e.state.className = "state";
    var pend = showNote[key];
    if (pend && !(st && (st.s === "saving" || st.s === "err"))) e.state.textContent = m && m.result === pend ? "Your change is not sent yet" : (pend === "note" ? "Comment" : pend === "works" ? "Works" : "Doesn't work") + ", not sent yet";
    else if (st && st.s === "saving") e.state.textContent = "Saving…";
    else if (st && st.s === "err") { e.state.className = "state err"; e.state.textContent = st.msg; }
    else if (st && st.s === "ok") { e.state.className = "state " + (st.bad ? "err" : "ok"); e.state.textContent = st.msg || (m ? "✓ Saved" : "✓ Cleared"); }
    else e.state.textContent = m && m.marked ? "Marked " + fmtStamp(m.marked) : "Not checked yet";
  }

  function updateChecks(newest) {
    var total = 0, left = 0, bad = 0;
    rows.forEach(function (r) {
      var t = tally(r.it);
      total += t.all; left += t.all - t.marked; bad += t.fails;
      if (r.cc) {
        r.cc.textContent = "";
        if (t.marked === t.all && !t.fails) r.cc.appendChild(el("span", "all", "All " + t.all + " checks work"));
        else {
          r.cc.appendChild(document.createTextNode(t.marked + " of " + t.all + " checked"));
          if (t.fails) { r.cc.appendChild(document.createTextNode(", ")); r.cc.appendChild(el("span", "bad", t.fails + " not working")); }
        }
        // the tag is ahead of the database: say so until the writer has recorded it
        if (t.marked === t.all && shownStatus(r.it) !== r.it.status) r.cc.appendChild(document.createTextNode(". Claude is recording it."));
      }
      if (!r.cx) return;
      r.cx.els.forEach(function (e) {
        var m = markOf(e.it, e.c), res = m ? m.result : "";
        var pend = showNote[e.key] || "", open = !!pend;
        var note = m ? String(m.note || "").trim() : "";
        // the plain places show the answer in force; a comment place shows what is waiting in the open box
        e.item.className = "check" + (res ? " " + res : "");
        e.yes.setAttribute("aria-pressed", res === "works" ? "true" : "false");
        e.no.setAttribute("aria-pressed", res === "fails" ? "true" : "false");
        e.yesC.setAttribute("aria-pressed", pend === "works" ? "true" : "false");
        e.noC.setAttribute("aria-pressed", pend === "fails" ? "true" : "false");
        e.only.setAttribute("aria-pressed", pend === "note" ? "true" : "false");
        e.lab.textContent = pend === "note" ? "Comment only. This check is not marked either way."
          : pend === "fails" ? "Doesn't work, with a comment. What did you see?" : "Works, with a comment. What do you want to say?";
        e.nb.hidden = !open;
        e.said.hidden = open || !note;
        e.saidText.textContent = note;
        e.say.hidden = open || !(m && !note);
        if (document.activeElement !== e.ta) e.ta.value = noteFor(e.key, m);
        e.clear.hidden = !(m || open);
        showState(e.key);
      });
    });
    var bar = $("checkbar");
    bar.hidden = !total || isRunning();
    $("cb-left").textContent = String(left);
    $("cb-label").textContent = left === 1 ? "check still to try" : "checks still to try";
    var sub = $("cb-sub");
    sub.textContent = "of " + total + " in all" + (bad ? ", " + bad + " marked not working" : "") + (marksLoaded ? "" : " (loading your marks)");
    sub.className = bad ? "bad" : "";
    $("qbar").parentNode.classList.toggle("cpulse", left > 0 && !bar.hidden);
    Array.prototype.forEach.call($("filters").children, function (b) {
      var lbl = b.querySelector(".lbl"); if (!lbl) return;
      if (b.dataset.key === TOTRY) lbl.textContent = "Still to check (" + left + ")";
      if (b.dataset.key === NOTWORK) lbl.textContent = "Not working (" + bad + ")";
    });
    setFilter(current, newest);
  }

  // ---- a table on a row: field "table" = {title, columns: [names], rows: [{<column name>: value}], totals, summary} ----
  function isNum(v) { return typeof v === "number" && isFinite(v); }
  function makeTable(it) {
    var t = it.table;
    if (!t || !Array.isArray(t.columns) || !t.columns.length || !Array.isArray(t.rows)) return null;
    var list = t.rows.filter(function (r) { return r && typeof r === "object"; });
    if (!list.length) return null;
    var cols = t.columns.map(String);
    var box = el("div", "scores");
    if (t.title) box.appendChild(el("h3", null, String(t.title)));
    var scroll = el("div", "scroll"), tbl = el("table"), th = el("thead"), hr = el("tr");
    cols.forEach(function (c) { hr.appendChild(el("th", null, c)); });
    th.appendChild(hr); tbl.appendChild(th);
    var tb = el("tbody"), sum = cols.map(function () { return 0; }), any = cols.map(function () { return false; });
    list.forEach(function (r) {
      var tr = el("tr");
      cols.forEach(function (c, i) {
        var v = r[c], none = v == null || v === "";
        tr.appendChild(el("td", none ? "nil" : null, none ? "\u2013" : String(v)));
        if (i && isNum(v)) { sum[i] += v; any[i] = true; }
      });
      tb.appendChild(tr);
    });
    tbl.appendChild(tb);
    if (t.totals && any.some(Boolean)) {
      var tf = el("tfoot"), fr = el("tr");
      cols.forEach(function (c, i) { fr.appendChild(el("td", null, i ? (any[i] ? String(Math.round(sum[i] * 100) / 100) : "") : "Total")); });
      tf.appendChild(fr); tbl.appendChild(tf);
    }
    scroll.appendChild(tbl); box.appendChild(scroll);
    return { box: box, line: t.summary ? String(t.summary) : "" };
  }

  function makeRow(it, newest, wasOpen, moreWasOpen, bucket, away, nk) {
    var st = tagOf(it);
    var d = el("details", "row" + (it.kind === "phase" && !away ? " phase" : ""));
    d.id = rowId(it._id);
    if (wasOpen) d.open = true;
    d.style.setProperty("--c", "var(" + st.c + ")");
    d.style.setProperty("--cb", "var(" + st.c + "-bg)");
    var s = el("summary");
    var runRow = isRunning();
    s.appendChild(el("span", "num", runRow ? (it._dn || "") : (it.number || (it.kind === "phase" ? "•" : ""))));
    s.appendChild(el("span", "name", it.kind === "step" && !runRow ? it.name + " (" + it.number + ")" : it.name));
    s.appendChild(el("span", "tag", st.short));
    var fresh = isFresh(it, newest);
    var w = el("span", "when" + (fresh ? " fresh" : ""), fmtWhen(it._stamp));
    w.title = "Last changed";
    s.appendChild(w);
    if (away) s.appendChild(el("span", "pof", "Part of " + (away.kind === "step" ? away.name + " (" + away.number + ")" : away.name)));
    var cx = makeChecks(it), cc = null;
    if (cx) { cc = el("span", "ccount"); s.appendChild(cc); }
    var sc = makeTable(it);
    if (sc && sc.line) s.appendChild(el("span", "sline", sc.line));
    var nn = nOpenOn(it._id);
    if (nn) s.appendChild(el("span", "ncount", nn === 1 ? "1 note for Claude" : nn + " notes for Claude"));
    var nq = qOpenOn(it._id);
    if (nq) s.appendChild(el("span", "qcount", nq === 1 ? "A question for you" : nq + " questions for you"));
    var hasPlan = typeof it.plan === "string" && it.plan.trim() !== "";
    if (hasPlan) s.appendChild(el("span", "pmark", "Plan written"));
    if (nk) {
      var fm = el("span", "fmark"); s.appendChild(fm);
      var fmText = function () {
        fm.textContent = d.open ? (nk === 1 ? "Its 1 sub-step is shown below" : "Its " + nk + " sub-steps are shown below")
          : nk + (nk === 1 ? " sub-step" : " sub-steps") + " folded inside: open to show";
      };
      fmText();
      // only the viewer's own tap is remembered, not an opening done by a filter
      s.addEventListener("click", function () { if (d.open) delete openDone[it._id]; else openDone[it._id] = true; saveOpenDone(); });
      d.addEventListener("toggle", function () { fmText(); foldQuiet = true; setFilter(current); foldQuiet = false; });
    }
    d.appendChild(s);
    var qb = makeQuestions(null, it._id);
    if (qb) d.appendChild(qb);
    if (hasPlan) {
      var pf = el("details", "more"), ps = el("summary", null, "Show plan");
      pf.id = "plan-" + it._id;
      if (planOpen[it._id]) { pf.open = true; ps.textContent = "Hide plan"; }
      pf.addEventListener("toggle", function () { planOpen[it._id] = pf.open; ps.textContent = pf.open ? "Hide plan" : "Show plan"; });
      pf.appendChild(ps); pf.appendChild(mdEl("plantext md", it.plan));
      d.appendChild(pf);
    }
    if (sc) d.appendChild(sc.box);
    if (cx) d.appendChild(cx.box);
    var dl = el("dl", "facts");
    dl.appendChild(el("dt", null, "Where it stands")); dl.appendChild(el("dd", null, st.key));
    FIELDS.forEach(function (f) {
      var v = it[f[0]];
      dl.appendChild(el("dt", null, f[1]));
      var dd = el("dd");
      if (!v || /^not recorded$/i.test(v)) { dd.textContent = "not recorded"; dd.className = "empty"; }
      else { dd.textContent = v; if (f[0] === "waits_on_you" && !/^nothing/i.test(v)) dd.className = "waits"; }
      dl.appendChild(dd);
    });
    dl.appendChild(el("dt", null, "Last changed")); dl.appendChild(el("dd", null, it._stamp ? fmtWhen(it._stamp) : "not recorded"));
    // Rows with checks: the checks lead; the long facts fold away behind a Details line.
    var more = null;
    if (cx) {
      more = el("details", "more");
      if (moreWasOpen) more.open = true;
      more.appendChild(el("summary", null, "Details: what it does, what it does not do yet, where it was shown working"));
      more.appendChild(dl);
      d.appendChild(more);
    } else d.appendChild(dl);
    d.appendChild(makeNotes(it));
    rows.push({ el: d, it: it, st: st, cx: cx, cc: cc, more: more, bucket: bucket, nk: nk || 0, under: null });
    return d;
  }

  // ---- what the person writes on a row ----
  function fmtNoteWhen(n) { return n.written ? "Written " + fmtStamp(n.written) : ""; }
  function makeNotes(it) {
    var id = it._id, box = el("div", "notes");
    box.appendChild(el("h3", null, "Say something about this"));
    var f = el("div", "qform"), taId = "nt-" + id;
    var lab = el("label", null, "Your words go to Claude when you tap Done."); lab.htmlFor = taId;
    var ta = el("textarea"); ta.id = taId; ta.dataset.key = "n-" + id; ta.rows = 3; ta.value = nDrafts[id] || "";
    var row = el("div", "qrow"), btn = el("button", "qbtn", nSaving[id] ? "Saving…" : "Done"); btn.type = "button"; btn.id = "nd-" + id;
    function ready() { btn.disabled = !!nSaving[id] || !String(nDrafts[id] || "").trim(); }
    ta.addEventListener("input", function () { nDrafts[id] = ta.value; ready(); });
    btn.addEventListener("click", function () { noteWrite(it); });
    ready(); row.appendChild(btn);
    var m = nState[id];
    if (m) { var st = el("span", "state" + (m.err ? " err" : m.ok ? " ok" : ""), m.text); st.setAttribute("role", "status"); row.appendChild(st); }
    f.appendChild(lab); f.appendChild(ta); f.appendChild(row); box.appendChild(f);
    var ids = notesOn(id);
    if (ids.length) {
      var list = el("div", "nlist");
      ids.slice(0, 3).forEach(function (k) { list.appendChild(noteCard(it, k)); });
      box.appendChild(list);
      if (ids.length > 3) {
        var fold = el("details", "more"); fold.id = "nf-" + id; if (nFold[id]) fold.open = true;
        fold.addEventListener("toggle", function () { nFold[id] = fold.open; });
        fold.appendChild(el("summary", null, "Earlier notes (" + (ids.length - 3) + ")"));
        var inner = el("div", "nlist");
        ids.slice(3).forEach(function (k) { inner.appendChild(noteCard(it, k)); });
        fold.appendChild(inner); box.appendChild(fold);
      }
    }
    return box;
  }

  function noteCard(it, k) {
    var n = notes[k], c = el("article", "qans ncard"); c.id = "note-" + k;
    c.appendChild(el("span", "k", fmtNoteWhen(n) || "Written"));
    if (n.check_text) c.appendChild(el("span", "quiet-line", "About the check: " + n.check_text));
    if (n.status !== "done" && nEdit[k] != null) {
      // changing an open note: nothing is written or sent until Done
      var f = el("div", "qform"), ta = el("textarea"); ta.id = "ne-" + k; ta.dataset.key = "ne-" + k; ta.rows = 3; ta.value = nEdit[k];
      ta.setAttribute("aria-label", "Change what I said");
      var row = el("div", "qrow"), ok = el("button", "qbtn", "Done"); ok.type = "button"; ok.id = "ned-" + k;
      var keep = el("button", "qbtn quiet", "Keep what I said"); keep.type = "button";
      function ready() { ok.disabled = !String(nEdit[k] || "").trim(); }
      ta.addEventListener("input", function () { nEdit[k] = ta.value; ready(); });
      ok.addEventListener("click", function () { noteChange(it, k); });
      keep.addEventListener("click", function () { delete nEdit[k]; render(); });
      ready(); row.appendChild(ok); row.appendChild(keep); f.appendChild(ta); f.appendChild(row); c.appendChild(f);
      return c;
    }
    c.appendChild(el("span", "v", n.text || ""));                       // the person's own words, as plain text
    if (n.status === "done") {
      c.appendChild(el("span", "k", "What changed"));
      c.appendChild(mdEl("v md", n.done_note || "Claude acted on this."));
    } else {
      c.appendChild(el("span", "quiet-line", "Claude has not acted on this yet"));
      var acts = el("div", "qrow");
      var ch = el("button", "clear", "Change what I said"); ch.type = "button"; ch.id = "nc-" + k;
      ch.addEventListener("click", function () { nEdit[k] = n.text || ""; delete nState[it._id]; render(); var t = $("ne-" + k); if (t) t.focus(); });
      var back = el("button", "clear", "Take it back"); back.type = "button"; back.id = "nb-" + k;
      back.addEventListener("click", function () { noteTakeBack(it, k); });
      acts.appendChild(ch); acts.appendChild(back); c.appendChild(acts);
    }
    return c;
  }

  function noteErr(e, gone) {
    var code = e && e.code;
    return code === "invalid_argument" || code === "not_granted" ? "Not saved: only the page's owner and editors can write here."
      : code === "not_found" ? gone : code === "quota_exceeded" ? "Not saved: the roadmap's storage is full."
      : "Not saved: no connection right now. Tap again to retry.";
  }
  // tell Claude about a note through the shared sender; the line it gives is shown beside the row's Done button
  function noteTell(it, k, line, lead) {
    nState[it._id] = { ok: true, text: lead + " Telling Claude…" }; render();
    sendToClaude(line, function () { return $("note-" + k) || $(rowId(it._id)); }, lead, "note",
      function (t, err) { nState[it._id] = { ok: !err, err: !!err, text: t }; render(); });
  }
  function noteWrite(it) {
    var id = it._id, text = String(nDrafts[id] || "").trim();
    if (!text || nSaving[id]) return;
    if (!db) { nState[id] = { err: true, text: "Not saved: the page is not connected. Open it signed in to Claude." }; render(); return; }
    var k = id + "--" + Date.now().toString(36) + Math.floor(Math.random() * 36).toString(36);
    nSaving[id] = true; nState[id] = { text: "Saving…" }; render();
    db.doc("notes/" + k).set({ row: id, text: text, written: new Date().toISOString(), status: "open" }).then(function () {
      nSaving[id] = false; delete nDrafts[id];
      noteTell(it, k, "Written on the roadmap: on " + whereOf(id) + " (notes/" + k + "): " + text, "✓ Saved.");
    }, function (e) { nSaving[id] = false; nState[id] = { err: true, text: noteErr(e, "Not saved: this row was taken down.") }; render(); });
  }
  function noteChange(it, k) {
    var n = notes[k], text = String(nEdit[k] || "").trim();
    if (!n || !text) return;
    if (n.status === "done") { delete nEdit[k]; nState[it._id] = { err: true, text: "Claude already acted on this one, so it can't be changed." }; render(); return; }
    if (text === String(n.text || "").trim()) { delete nEdit[k]; render(); return; }            // nothing changed: nothing sent
    if (!db) { nState[it._id] = { err: true, text: "Not saved: the page is not connected. Open it signed in to Claude." }; render(); return; }
    nState[it._id] = { text: "Saving…" }; render();
    db.doc("notes/" + k).update({ text: text, changed: new Date().toISOString() }).then(function () {
      delete nEdit[k];
      noteTell(it, k, "Changed on the roadmap: what was written on " + whereOf(it._id) + " (notes/" + k + ") now reads: " + text, "✓ Saved.");
    }, function (e) { nState[it._id] = { err: true, text: noteErr(e, "Not saved: this note is no longer there.") }; render(); });
  }
  function noteTakeBack(it, k) {
    var n = notes[k]; if (!n) return;
    if (n.status === "done") { nState[it._id] = { err: true, text: "Claude already acted on this one, so it can't be taken back." }; render(); return; }
    if (!db) { nState[it._id] = { err: true, text: "Not taken back: the page is not connected. Open it signed in to Claude." }; render(); return; }
    var words = n.text || "";
    db.doc("notes/" + k).delete().then(function () {
      delete nEdit[k];
      noteTell(it, k, "Taken back on the roadmap: what was written on " + whereOf(it._id) + " (notes/" + k + ") was taken back. It read: " + words, "✓ Taken back.");
    }, function (e) { nState[it._id] = { err: true, text: noteErr(e, "This note is no longer there.").replace("Not saved", "Not taken back") }; render(); });
  }

  function addFilter(key, label, color) {
    var b = el("button"); b.type = "button"; b.dataset.key = key;
    if (color) { var dot = el("span", "dot"); dot.style.background = "var(" + color + ")"; b.appendChild(dot); }
    b.appendChild(el("span", "lbl", label));
    b.addEventListener("click", function () { setFilter(key); });
    $("filters").appendChild(b);
  }

  function setFilter(key, newest) {
    current = key;
    try { localStorage.setItem("roadmap-filter", key); } catch (e) {}
    if (newest === undefined) newest = newestOf(rows.map(function (r) { return r.it._stamp; }));
    Array.prototype.forEach.call($("filters").children, function (b) { b.setAttribute("aria-pressed", b.dataset.key === key ? "true" : "false"); });
    function hit(it) {
      if (key === "all") return true;
      if (key === RECENT) return isFresh(it, newest);
      // a row answered just now stays in view so the answer is seen saved
      if (key === QFOR) return qOpenOn(it._id) > 0 || Object.keys(qState).some(function (k) { return questions[k] && questions[k].row === it._id; });
      if (key === NOTES) return nOpenOn(it._id) > 0;
      if (key === NOTWORK) return tally(it).fails > 0;
      if (key === TOTRY) { var t = tally(it); return t.marked < t.all; }
      if (key === NOCHK) return noChecks(it);
      return shownStatus(it) === key && !noChecks(it);
    }
    rows.forEach(function (r) {
      var match = hit(r.it);
      var childMatch = r.it.kind === "step" && rows.some(function (c) { return c.it.parent === r.it._id && c.bucket === r.bucket && hit(c.it); });
      // a sub-row a filter picks out opens its done step, so the sub-row shows
      if (childMatch && key !== "all" && r.nk && !r.el.open && !foldQuiet) r.el.open = true;
      r.el.hidden = !(match || childMatch);
      r.el.classList.toggle("context", !match && childMatch);
    });
    // a done step's folded sub-rows show only while the step is open
    rows.forEach(function (r) { if (r.under && (r.under.el.hidden || !r.under.el.open)) r.el.hidden = true; });
    // a section shows only while it holds a row to show; with a filter on it is shown open, whatever was stored;
    // a small heading inside it shows only while a row under it does
    folds.forEach(function (f) {
      var has = rows.some(function (r) { return !r.el.hidden && f.el.contains(r.el); });
      f.el.hidden = !has;
      f.el.open = key !== "all" ? has : foldOpen(f.key);
      Array.prototype.forEach.call(f.el.querySelectorAll("details.hgroup"), function (g) {
        g.hidden = !rows.some(function (r) { return !r.el.hidden && g.contains(r.el); });
        if (key !== "all" && !g.hidden) g.open = true;
      });
      Array.prototype.forEach.call(f.el.querySelectorAll("h3.sub"), function (h) {
        var box = h.nextElementSibling;
        h.hidden = !rows.some(function (r) { return !r.el.hidden && box.contains(r.el); });
      });
    });
    if (emptyNote) emptyNote.hidden = !rows.length || rows.some(function (r) { return !r.el.hidden; });
  }

  // Settings: this project's settings as the main session last recorded them in board/settings ("kind", "helpers",
  // "writes", "writes_switch", "sessions"). A press never changes a setting here: it saves one request, board/ask-<id>
  // ({setting, value, session, session_name, asked, status "open"}), and tells Claude; the main session makes the change,
  // writes the new choice into board/settings and marks the request done. Until then the page shows the choice as asked.
  // Who writes the roadmap is never asked for: only the command for the person to run themselves is shown, with Copy.
  var asks = {}, setState = {}, copyMsg = "";
  var SETS = [
    { k: "kind", name: "Roadmap kind", c: [["stepped", "Stepped", "a build with an end: every step in order"], ["running", "Running", "ongoing work: live work in groups, finished work folded into History"]] },
    { k: "writes", name: "Who writes the roadmap", c: [["writer", "A writer session", "a separate Roadmap writer session writes it"], ["main", "The main session", "the project's main session writes it itself"]] },
    { k: "helpers", name: "Model helpers use", c: [["cheapest", "Cheapest that does the job well", "each helper gets the cheapest model that does its job well"], ["strongest", "Always the strongest", "every helper gets the strongest model"]] }
  ];
  var NOT_RECORDED = "Not recorded yet. Claude's main session records it at its next settings change.";
  function curSetting(k) {
    if (k === "kind") return settings && settings.kind === "running" ? "running" : "stepped";
    var v = settings && settings[k]; return typeof v === "string" ? v : "";
  }
  function stateLine(id) {
    var st = setState[id]; if (!st) return null;
    return el("div", "state " + (st.bad ? "err" : "ok"), st.msg);
  }
  function askSetting(id, data, line) {
    if (!db) { setState[id] = { bad: true, msg: "Not sent: the page is not connected. Open it signed in to Claude." }; renderSettings(); return; }
    data.asked = new Date().toISOString(); data.status = "open";
    setState[id] = { msg: "Sending…" }; renderSettings();
    db.doc("board/" + id).set(data).then(function () {
      sendToClaude(line + " (board/" + id + ")", function () { return $("set-" + id); }, "✓ Asked.", "request",
        function (t, err) { setState[id] = { msg: t + " The choice changes here once the main session has made it.", bad: !!err }; renderSettings(); });
    }, function (e) {
      var code = e && e.code;
      setState[id] = { bad: true, msg: code === "invalid_argument" || code === "not_granted" ? "Not sent: only the page's owner and editors can change settings." : "Not sent: no connection right now. Tap it again." };
      renderSettings();
    });
  }
  function copyCommand(text) {
    function done(ok) {
      copyMsg = ok ? "Copied. Paste it into a PowerShell window and press Enter." : "Copy is blocked here: the command is selected, press Ctrl+C.";
      renderSettings();
      if (!ok) { var i = $("set-cmd"); if (i) { i.focus(); i.select(); } }
    }
    try { navigator.clipboard.writeText(text).then(function () { done(true); }, function () { done(false); }); } catch (e) { done(false); }
  }
  function renderSettings() {
    var box = $("setlist"); if (!box) return;
    $("setbox").hidden = !db;
    box.textContent = "";
    SETS.forEach(function (s) {
      var id = "ask-" + s.k, cur = curSetting(s.k), a = asks[id], row = el("div", "setrow");
      row.id = "set-" + id;
      row.appendChild(el("b", null, s.name));
      row.appendChild(el("div", "means", s.c.map(function (c) { return c[1] + ": " + c[2] + "."; }).join(" ")));
      var now = s.c.filter(function (c) { return c[0] === cur; })[0];
      row.appendChild(el("div", "cur", now ? "Now: " + now[1] + "." : NOT_RECORDED));
      if (s.k === "writes") {
        // the person's own switch: shown, never asked for, never run
        var cmd = settings && typeof settings.writes_switch === "string" ? settings.writes_switch : "";
        if (!cmd) row.appendChild(el("div", "means", "The command to change it shows here once Claude's main session records this project's settings."));
        else {
          row.appendChild(el("div", "means", "Only you change this. To change it, run this yourself in a PowerShell window, not in Claude:"));
          var cp = el("div", "setcopy"), inp = el("input"), cb = el("button", null, "Copy");
          inp.id = "set-cmd"; inp.readOnly = true; inp.value = cmd; inp.setAttribute("aria-label", "The command to change who writes the roadmap");
          cb.type = "button"; cb.setAttribute("aria-label", "Copy the command");
          cb.addEventListener("click", function () { copyCommand(cmd); });
          cp.appendChild(inp); cp.appendChild(cb); row.appendChild(cp);
          if (cur === "main") row.appendChild(el("div", "means", "Then, in the project's main session, type /assistant:roadmap-start-writer."));
          if (copyMsg) row.appendChild(el("div", "state ok", copyMsg));
        }
        box.appendChild(row); return;
      }
      var btns = el("div", "setbtns"), open = a && a.status === "open" && a.value !== cur ? a : null;
      s.c.forEach(function (c) {
        var asked = open && open.value === c[0];
        var b = el("button", asked ? "asked" : null, c[1] + (asked ? " (asked)" : ""));
        b.type = "button"; b.setAttribute("aria-pressed", cur === c[0] ? "true" : "false");
        b.addEventListener("click", function () {
          if (cur === c[0] || asked) return;
          askSetting(id, { setting: s.k, value: c[0] }, "Asked on the roadmap: change the setting \"" + s.name + "\" to \"" + c[1] + "\"");
        });
        btns.appendChild(b);
      });
      row.appendChild(btns);
      if (open) row.appendChild(el("div", "state", "Asked for " + s.c.filter(function (c) { return c[0] === open.value; }).map(function (c) { return c[1]; })[0] + ". The main session is making the change; it shows here once made."));
      else if (a && a.status === "done" && a.value !== cur && a.done_note) row.appendChild(el("div", "state err", "Not changed: " + a.done_note));
      var st = stateLine(id); if (st && !(a && a.status === "done")) row.appendChild(st);
      box.appendChild(row);
    });
    // the questions file, for each of the project's sessions
    var q = el("div", "setrow"), list = settings && Array.isArray(settings.sessions) ? settings.sessions : null;
    q.appendChild(el("b", null, "Questions file"));
    q.appendChild(el("div", "means", "Each session can keep its own questions file. Turning one on or off is asked in that session, and it changes once you say yes there."));
    if (!list) q.appendChild(el("div", "cur", NOT_RECORDED));
    else if (!list.length) q.appendChild(el("div", "cur", "No session of this project was open when the settings were last recorded."));
    (list || []).forEach(function (x) {
      if (!x || !x.id) return;
      var id = "ask-questions--" + String(x.id).replace(/[^A-Za-z0-9._-]/g, "").slice(0, 100), a = asks[id], on = x.questions === true;
      var nm = String(x.name || x.id) + (x.role === "main" ? " (main session)" : x.role === "writer" ? " (Roadmap writer)" : "");
      var open = a && a.status === "open" && (a.value === "on") !== on ? a : null;
      var line = el("div", "setsess"), left = el("span", null, nm + ": " + (on ? "on" : "off") + (open ? ", asked to turn it " + open.value : ""));
      line.id = "set-" + id;
      var b = el("button", null, on ? "Turn off" : "Turn on"), btns = el("div", "setbtns");
      b.type = "button"; b.disabled = !!open;
      b.setAttribute("aria-label", (on ? "Turn the questions file off for " : "Turn the questions file on for ") + nm);
      b.addEventListener("click", function () {
        askSetting(id, { setting: "questions", value: on ? "off" : "on", session: String(x.id), session_name: String(x.name || "") },
          "Asked on the roadmap: turn the questions file " + (on ? "off" : "on") + " for the session \"" + (x.name || x.id) + "\"");
      });
      btns.appendChild(b); line.appendChild(left); line.appendChild(btns); q.appendChild(line);
      if (!open && a && a.status === "done" && (a.value === "on") !== on && a.done_note) q.appendChild(el("div", "state err", "Not changed: " + a.done_note));
      var st = stateLine(id); if (st && !(a && a.status === "done")) q.appendChild(st);
    });
    box.appendChild(q);
  }

  // Questions in chat: each session's questions file, copied as written by that session (board/questions-file--<session>,
  // {session, session_name, file, text, open, changed}). Read only: the person answers in that chat.
  var qfiles = {};
  function renderQFiles() {
    var box = $("qfiles"), ids = Object.keys(qfiles).sort(function (a, b) {
      return String(qfiles[a].session_name || a).localeCompare(String(qfiles[b].session_name || b));
    });
    box.textContent = "";
    box.hidden = !ids.length;
    applyPulse();
    if (!ids.length) return;
    box.appendChild(el("h2", null, "Questions in chat"));
    ids.forEach(function (id) {
      var f = qfiles[id], card = el("article", "qfile"), head = el("div", "qfile-head");
      head.appendChild(el("b", null, String(f.session_name || f.file || "A chat session")));
      if (f.changed) head.appendChild(el("span", null, "Changed " + fmtStamp(f.changed)));
      card.appendChild(head);
      card.appendChild(mdEl("qfile-text md", f.text || ""));
      card.appendChild(el("div", "means", "Answer these in that chat."));
      box.appendChild(card);
    });
  }

  // live facts from the page's own database
  var timer = setTimeout(function () {
    if (!items) fail("The roadmap's facts could not be loaded yet. Check the connection and open the page again.");
  }, 10000);

  (async function () {
    try { db = await claude.use("db"); } catch (e) { db = null; }
    if (!db) { clearTimeout(timer); fail("The roadmap's facts could not be loaded. Open the page signed in to Claude."); return; }
    db.collection("steps").onSnapshot(function (snap) {
      items = snap.docs.map(function (d) { var o = Object.assign({}, d.data()); o._id = d.id; o._stamp = stampOf(docTime(d), o.changed); return o; });
      if (!snap.metadata.fromCache) clearTimeout(timer);
      render();
    }, function () { clearTimeout(timer); if (!items) fail("The roadmap's facts could not be loaded."); });
    db.doc("board/next").onSnapshot(function (snap) {
      board = snap.exists ? snap.data() : null;
      boardStamp = board ? stampOf(docTime(snap), board.facts_as_of) : null;
      render();
    }, function () {});
    db.doc("board/settings").onSnapshot(function (snap) {
      settings = snap.exists ? (snap.data() || {}) : {};
      render();
      renderSettings();
    }, function () {});
    db.collection("board").onSnapshot(function (snap) {
      var next = {};
      var files = {};
      snap.docs.forEach(function (d) {
        if (d.id.indexOf("ask-") === 0) next[d.id] = d.data() || {};
        else if (d.id.indexOf("questions-file--") === 0) files[d.id] = d.data() || {};
      });
      asks = next;
      qfiles = files;
      renderSettings();
      renderQFiles();
    }, function () {});
    renderSettings();
    db.collection("marks").onSnapshot(function (snap) {
      var next = {};
      snap.docs.forEach(function (d) { next[d.id] = d.data(); });
      var before = {}, old = realMarks;
      (items || []).forEach(function (it) { before[it._id] = shownStatus(it); });
      realMarks = next;
      if (!snap.metadata.fromCache) marksLoaded = true;
      if (!items) { mergeMarks(); return; }
      items.forEach(function (it) {
        if (held[it._id] || before[it._id] === it.status) return;
        var keep = {}, byOther = false;
        checksOf(it).forEach(function (c) {
          var k = markKey(it, c); if (!old[k]) return;
          keep[k] = old[k];
          if (!next[k] && !(Date.now() - (ownClears[k] || 0) < 10000)) byOther = true;
        });
        if (!byOther) return;
        held[it._id] = { until: Date.now() + HOLD_MS, marks: keep };
        setTimeout(function () { mergeMarks(); render(); }, HOLD_MS + 50);
      });
      mergeMarks();
      // a row whose shown status changed with the marks is drawn again (tag, colour, counts, filters)
      if (items.some(function (it) { return shownStatus(it) !== before[it._id]; })) render(); else updateChecks();
    }, function () {
      var sub = $("cb-sub"); sub.className = "bad"; sub.textContent = "Your marks could not be loaded. Open the page again.";
    });
    db.collection("notes").onSnapshot(function (snap) {
      var next = {};
      snap.docs.forEach(function (d) { next[d.id] = d.data() || {}; });
      // a note Claude has acted on can no longer be changed: drop a change being typed for it
      Object.keys(nEdit).forEach(function (k) { if (!next[k] || next[k].status === "done") delete nEdit[k]; });
      notes = next;
      if (items) render();
    }, function () {});
    db.collection("questions").onSnapshot(function (snap) {
      var next = {};
      snap.docs.forEach(function (d) { var q = d.data() || {}; if (q.source !== "chat") next[d.id] = q; });
      // A question asked again (back to open after an answer, or open with new wording after this page saved an
      // answer) starts clean: no "Saved" line, no edit state, no draft made from the old answer. A draft being
      // typed on a question that was open all along is kept, and so is the "Saved" line of one still answered.
      Object.keys(next).forEach(function (k) {
        var was = questions[k], now = next[k];
        if (!was || qStatus(now) !== "open") return;
        if (qStatus(was) !== "open") { delete qState[k]; delete qEditing[k]; delete qDrafts[k]; }
        else if (qState[k] && !qSaving[k] && (String(was.question || "") !== String(now.question || "") || qHistory(was).length !== qHistory(now).length)) {
          delete qState[k]; delete qEditing[k];
        }
      });
      questions = next;
      if (items) render();
    }, function () {
      var bar = $("qbar"); bar.hidden = false; $("qb-left").textContent = "?";
      $("qb-label").textContent = "questions could not be loaded"; $("qb-sub").textContent = "Open the page again.";
    });
  })();
})();
};
(function () {
  'use strict';
  var KEEP = 'livepage.';
  function keepGet(k) { try { return localStorage.getItem(KEEP + k); } catch (e) { return null; } }
  function keepSet(k, v) { try { localStorage.setItem(KEEP + k, v); } catch (e) {} }
  /* A few plain words about this browser, recorded with every press. */
  var device = (function () {
    var u = navigator.userAgent || '';
    var kind = /iPad|Tablet/.test(u) || (/Android/.test(u) && !/Mobile/.test(u)) ? 'Tablet' : /Mobi|iPhone|Android/.test(u) ? 'Phone' : 'Computer';
    var br = /Edg\//.test(u) ? 'Edge' : /OPR\//.test(u) ? 'Opera' : /Firefox\//.test(u) ? 'Firefox' : /Chrome\//.test(u) ? 'Chrome' : /Safari\//.test(u) ? 'Safari' : 'browser';
    return kind + ', ' + br;
  })();

  var RM = {inst: {}};
  var S = {
    db: null, meta: null, parts: {}, items: [], ans: {}, err: {}, panel: {}, drafts: {}, open: {},
    q: '', by: keepGet('by') || '', age: '', baseline: keepGet('seen') || '',
    live: 'wait', ansLive: false, note: '', mine: {}, was: {}, think: {}, read: {}, reading: null, rmDocs: {}, chg: null, chgAsk: {}, chgSent: {}, rdGone: {}, rdAsk: {}, rdAll: {}, kept: {}, wup: {}, wo: {}, mail: mailNew(), tx: txNew(), sample: {}, box: {}, view: null, useUndone: {}, revDone: {}, standing: null, oldDone: {}, oldBack: {}, held: null
  };

  function $(id) { return document.getElementById(id); }
  function h(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]; }); }
  function D(s) { if (!s) return null; var d = new Date(String(s).length === 10 ? s + 'T00:00:00' : s); return isNaN(d) ? null : d; }
  function T(s) { var d = D(s); return d ? d.getTime() : 0; }
  var WK = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  function fmtD(d) { return d ? WK[d.getDay()] + ' ' + (d.getMonth() + 1) + '/' + d.getDate() : ''; }
  /* Every time on the page is written here: 12 hour form, or 24 hour form when the owner chose it in Settings.
     clk() does the same for a time inside words the assistant wrote (a card's history, a result). */
  function setts() { return (S.meta && S.meta.settings) || null; }
  function clock24() { var st = setts(); return !!(st && st.page && st.page.clock === '24'); }
  function fmtT(d) { if (!d) return ''; var hh = d.getHours(), m = d.getMinutes(); if (clock24()) return (hh < 10 ? '0' : '') + hh + ':' + (m < 10 ? '0' : '') + m; return ((hh + 11) % 12 + 1) + ':' + (m < 10 ? '0' : '') + m + (hh < 12 ? ' AM' : ' PM'); }
  function clk(s) {
    s = String(s == null ? '' : s);
    if (!clock24()) return s;
    return s.replace(/\b(\d{1,2}):(\d\d) ?([AaPp])\.?[Mm]\b\.?/g, function (all, hh, mm, ap) { var n = (+hh % 12) + (/p/i.test(ap) ? 12 : 0); return (n < 10 ? '0' : '') + n + ':' + mm; });
  }
  function hc(s) { return h(clk(dayWords(s))); }
  var DAY_TOKEN = /\{day:(\d{4}-\d\d-\d\d)(?:\|(morning|afternoon|evening|night))?\}/g;
  var BARE_DAY = /\b(\d{4}-\d\d-\d\d)\b(?![T:\d])/g;       /* a date written plainly (2026-11-21) in a card's words */
  function dayWords(s) {
    s = String(s == null ? '' : s);
    if (s.indexOf('{day:') >= 0) s = s.replace(DAY_TOKEN, function (all, ymd, part) {
      var d = D(ymd); if (!d) return all;
      var n = Math.round((d - D(today())) / 86400000);
      if (n === 0) return part === 'night' ? 'tonight' : part ? 'this ' + part : 'today';
      return (n === 1 ? 'tomorrow' : n === -1 ? (part === 'night' ? 'last' : 'yesterday') : fmtD(d)) + (part ? ' ' + part : '');
    });
    return s.replace(BARE_DAY, function (all, ymd) {
      var d = D(ymd); if (!d) return all;
      var n = Math.round((d - D(today())) / 86400000);
      return n === 0 ? 'today' : n === 1 ? 'tomorrow' : n === -1 ? 'yesterday' : fmtD(d);
    });
  }
  function fmtDT(d) { if (!d) return ''; return (sameDay(d, new Date()) ? '' : fmtD(d) + ' ') + fmtT(d); }
  function sameDay(a, b) { return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate(); }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function isoLocal(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds()); }
  function today() { return isoLocal(new Date()).slice(0, 10); }
  function plural(n, w) { return n + ' ' + w + (n === 1 ? '' : 's'); }

  /* ---------- what each item is ---------- */
  /* The self-improvement parts are gone from the page. Such an item is never drawn, whatever the data carries. */
  var OLD_SELF = {'Improvement': 1, 'Built': 1, 'Build failed': 1, 'Putting it back': 1, 'Put back': 1, 'Could not put back': 1, 'Reading your change': 1};
  function oldSelf(it) {
    if (/^(improve|built):/.test(String(it.source_key || '')) || /^Improvement:/.test(String(it.title || ''))) return true;
    return it.area === 'System' && (OLD_SELF[it.status] === 1 || it.status === 'Needs you');
  }
  /* The card's own words (ITEMS.md "Design round 1"). A card from before them still draws:
     its title is the header, its first question is the thing wanted, and it has no why line. */
  function headerOf(it) { return String(it.header || it.title || ''); }
  function asksOf(it) { return (it.asks || []).filter(function (a) { return a && a !== it.title && a !== it.header && !(it.mini && a === it.mini.question); }); }
  function whyOf(it) { return String(it.why || '').replace(/^\s*here because:?\s*/i, '').trim(); }
  function wantOf(it, s) {
    /* a rule whose sentence did not fit the header is shown whole, since it is the thing being approved */
    if (it.rule && it.rule.text && s !== 'done' && headerOf(it).indexOf(it.rule.text) < 0) return 'Approve this rule? ' + it.rule.text;
    if (it.wants) return String(it.wants);
    var cal = it.calendar && typeof it.calendar === 'object' && s !== 'done' ? it.calendar : null;
    if (cal && cal.certain && cal.date && (cal.all_day || cal.start)) return 'Put this on your calendar: ' + (cal.title ? cal.title + ', ' : '') + whenWords(cal) + '?';
    var asks = asksOf(it), did = lastDid(it), guess = it.best_guess || it.recommended;
    if (s === 'fyi') return '';
    if (s === 'done') return closedOnly(it) ? 'Nothing was done. Bring it back if it still needs doing.' : did || 'Finished.';
    if (s === 'someday') return asks[0] || 'Snoozed to Someday. Bring it back when you want it.';
    if (s === 'motion' || s === 'tracked') {      /* waiting on someone: on whom, when it is looked at again, and what is recommended */
      var cbw = String(it.checkback_date || '').slice(0, 10);
      return (it.waiting_on ? 'Waiting on ' + it.waiting_on : 'Someone else has the next move') + (cbw ? '; looked at again ' + fmtD(D(cbw)) : '') + '.' +
        (guess ? ' Recommended: ' + guess : '');
    }
    if (asks.length) return asks[0] + (asks.length > 1 ? ' (and ' + (asks.length - 1) + ' more; open the card)' : '');
    if (it.draft) return 'A draft waits for your yes.';
    if (guess && (s === 'decide' || s === 'small')) return 'Approve this, or change it: ' + guess;
    if (s === 'task') return 'Yours to do. Press Done when it is finished.';
    if (s === 'new') return 'Just arrived and not sorted yet.';
    return 'Answer in your own words.';
  }
  /* A press (ITEMS.md "Design round 1") travels as an answer whose text is JSON: {"press": {"name": ...}}. */
  function pressOf(a) {
    if (!a || !/^\s*\{"press"/.test(String(a.text || ''))) return null;
    try { var p = JSON.parse(a.text).press; return p && typeof p === 'object' ? p : null; } catch (e) { return null; }
  }
  function pressName(a) { var p = pressOf(a); return p ? String(p.name || '') : ''; }
  function pressRec(name, extra, said) {
    var p = {name: name}, k;
    for (k in extra || {}) p[k] = extra[k];
    return {action: 'answer', text: JSON.stringify({press: p}), result: said || ''};
  }
  /* One press that closed several cards at once, kept on the key "press". */
  function groupOf(it) {
    var g = S.ans.press, p = pressOf(g), own = S.ans[it.key];
    if (!p || p.name !== 'got_it_all' || g.status === 'failed') return null;
    if (own && String(own.at || '') > String(g.at || '')) return null;
    if (p.ids ? p.ids.indexOf(it.id) < 0 : it.needs !== 'nothing') return null;
    if (String(it.updated_at || '') > String(g.at || '') && it.state !== 'done' && g.status === 'done') return null;      /* it came back after that press */
    return g;
  }
  /* He pressed Undo and the engine has not caught up: the card is shown back where it was at once. */
  function undone(it) {
    var own = S.ans[it.key], g = S.ans.press, mine = S.mine[it.key], a = pressName(own) === 'undo' || pressName(own) === 'bring_back' ? own : pressName(g) === 'undo' && (S.lastAll || []).indexOf(it.id) >= 0 ? g : null;
    if (mine && mine.rec === null && mine.t >= T(it.updated_at) - 1000) return true;
    return !!a && a.status !== 'failed' && String(a.at || '') >= String(it.updated_at || '').slice(0, 19);
  }
  function sect(it) {
    var mine = S.mine[it.key];
    /* He just pressed Undo: show the item open again at once, without waiting for his computer to reopen it. */
    if (mine && mine.rec === null && mine.open && (it.state === 'handled' || it.state === 'in_motion')) it = {state: mine.open, kind: it.kind, group: it.group, recommended: it.recommended, draft: it.draft, choices: it.choices};
    var back = undone(it), needs = it.needs, was = back && S.was[it.key];
    /* where the card was when he pressed, so Undo shows it there at once */
    if (was) { it = {state: was.state, kind: it.kind, group: it.group, recommended: it.recommended, draft: it.draft, choices: it.choices, shelf: was.shelf, status: was.status}; needs = was.needs; }
    if (it.state === 'done') { if (!(back && it.status === 'Got it')) return 'done'; needs = 'nothing'; }
    if (it.shelf === 'someday' && !back) return 'someday';
    if (needs === 'nothing' || (!needs && (it.state === 'handled' || (it.kind === 'fyi' && it.state !== 'in_motion')))) return 'fyi';
    if (needs === 'waiting') return it.group === 'tracked' ? 'tracked' : 'motion';
    if (needs === 'do') return it.group === 'small' ? 'small' : 'task';
    if (needs === 'answer' || needs === 'approval') return it.group === 'small' ? 'small' : 'decide';
    if (it.state === 'new') return 'new';
    if (it.state === 'question' || it.state === 'yours') {
      if (it.group === 'small') return 'small';
      if (it.kind === 'task' || (it.state === 'yours' && it.kind !== 'question' && it.kind !== 'approval')) return 'task';
      return (it.recommended || it.draft || it.kind === 'approval' || (it.choices || []).length) ? 'decide' : 'words';
    }
    if (it.state === 'in_motion') return it.group === 'tracked' ? 'tracked' : 'motion';
    return 'decide';
  }
  function isOpenSect(s) { return s === 'decide' || s === 'words' || s === 'task' || s === 'small' || s === 'tracked' || s === 'motion' || s === 'new'; }
  /* ---------- order, sorting and grouping (settings page.sort_by, page.group_kinds and page.group_by; due date, by kind and no groups when absent) ---------- */
  function made(it) { return T(it.created_at || it.source_when) || 0; }
  /* when the card is from (ITEMS.md from_at): its first message's arrival, else when it was made; shown top right, and what Newest and Oldest first go by */
  function fromT(it) { return T(it.from_at) || made(it); }
  function whenHtml(it) { var d = D(it.from_at || it.created_at); return d ? '<time class="when-from" datetime="' + h(isoLocal(d)) + '">' + h(fmtD(d) + ', ' + fmtT(d)) + '</time>' : ''; }
  /* The bar at the top of Cards: Sort by (page.sort_by) and Group by kind (page.group_kinds, on unless turned off). A change shows
     at once and is saved like a Settings save; this device keeps it until the page's data says the same (or ten minutes pass). */
  var SORTS = [['due_first', 'Due date'], ['newest_first', 'Newest first'], ['oldest_first', 'Oldest first'], ['waiting_longest', 'Waiting longest'],
               ['important_senders_first', 'Importance'], ['recently_active', 'Recently active']];
  var SORT_SAYS = 'How the cards are ordered. Due date (the default): the soonest due date first, so late cards lead, then important cards, then the oldest. ' +
    'Newest first and Oldest first: by the date at the top right of each card. Waiting longest: the card that has sat longest where it is now comes first. ' +
    'Importance: the most important first, and among equals the newest; it gets better as I learn what matters to you. ' +
    'Recently active: the card with the latest message first. Saved at once, on every device.';
  var GROUP_SAYS = 'On (the default): the cards stay together by kind, in the order Card order in Settings gives (Needs you, Waiting and Someday, FYI, Done), and Sort by orders them within each kind. ' +
    'Off: every card the filter shows in one list, ordered by Sort by alone. Hidden is always last either way. Saved at once, on every device.';
  function sortPick() { try { var p = JSON.parse(keepGet('sortpick') || 'null'); return p && typeof p === 'object' ? p : null; } catch (e) { return null; } }
  function sortSaved() { var st = setts(); return (st && st.page) || {}; }
  function sortVal() {
    var p = sortPick(), v = p && p.sort_by ? p.sort_by : sortSaved().sort_by;
    return SORTS.some(function (x) { return x[0] === v; }) ? v : 'due_first';
  }
  function kindsGrouped() { var p = sortPick(); return p && typeof p.group_kinds === 'boolean' ? p.group_kinds : sortSaved().group_kinds !== false; }
  function sortMode() { return {newest_first: 'newest', oldest_first: 'oldest', waiting_longest: 'waiting', important_senders_first: 'important', recently_active: 'recent'}[sortVal()] || 'due'; }
  function sortNote() { return SORTS.filter(function (x) { return x[0] === sortVal(); })[0][1]; }
  /* the pick is dropped once the data agrees, once its save was refused (said in the line at the bottom), or after ten minutes */
  function sortSettle() {
    var p = sortPick();
    if (!p) return;
    var sv = sortSaved(), a = S.ans && S.ans.settings, bad = !!(a && a.at === p.at && (a.status === 'failed' || /^Not saved/.test(String(a.outcome || ''))));
    if (bad) toast('How the cards are sorted did not save.', '', String(a.outcome || ''));
    if (bad || (sv.sort_by === p.sort_by && (sv.group_kinds !== false) === p.group_kinds) || !(Date.now() - (p.t || 0) < 600000)) keepSet('sortpick', '');
  }
  function sortSave(sortBy, grouped) {
    if (SET.pending) return;
    var at = isoLocal(new Date());
    keepSet('sortpick', JSON.stringify({sort_by: sortBy, group_kinds: grouped, at: at, t: Date.now()}));
    render();
    if (!S.db) return;
    /* both values every time: the settings answer is one slot, so a quick second change carries the first */
    var rec = {id: 'settings', action: 'answer', label: 'Settings', text: JSON.stringify({settings: {group: 'page', values: {sort_by: sortBy, group_kinds: grouped}}}), at: at, device: device, sent: false, status: 'saved', result: 'Saving how cards are sorted'};
    S.db.setAnswer('settings', rec).then(function () {}, function () { toast('How the cards are sorted did not save. Check the connection and try again.', ''); });
  }
  function sortBarHtml() {
    var v = sortVal(), g = kindsGrouped();
    return '<span class="fs-one"><button type="button" class="fs-group" data-s="sort-group" aria-pressed="' + g + '">Group by kind: ' + (g ? 'On' : 'Off') + '</button>' + infoBtn('Group by kind', GROUP_SAYS) + '</span>' +
      '<span class="fs-one"><label for="feed-sort-by">Sort by</label><select id="feed-sort-by">' + SORTS.map(function (x) { return '<option value="' + x[0] + '"' + (x[0] === v ? ' selected' : '') + '>' + h(x[1]) + '</option>'; }).join('') + '</select>' + infoBtn('Sort by', SORT_SAYS) + '</span>';
  }
  /* One key per card for each sort, the same as the engine's (order.key_for, without its asks-first part); smaller comes first.
     Due date: the soonest due date first, then important, then how often he is in touch with the sender, then the oldest.
     Waiting longest: since the card last moved (state_changed_at). Importance: importance, then the newest. Recently active: the latest message. */
  function lastT(it) { var t = T(it.last_at); (it.messages || []).forEach(function (m) { t = Math.max(t, T(m.when)); }); return t || fromT(it); }
  function sortKey(it, mode) {
    if (mode === 'newest') return [-fromT(it)];
    if (mode === 'oldest') return [fromT(it)];
    if (mode === 'waiting') return [T(it.state_changed_at) || fromT(it)];
    if (mode === 'important') return [-(+it.importance || 0), -fromT(it)];
    if (mode === 'recent') return [-lastT(it)];
    var due = it.due_date ? T(String(it.due_date).slice(0, 10)) : 0;
    return [due ? 0 : 1, due, -(+it.importance || 0), -(+((it.contact || {}).level) || 0), T(it.source_when) || T(it.created_at) || T(it.updated_at)];
  }
  function keyCmp(a, b) { for (var i = 0; i < a.length; i++) if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1; return 0; }
  /* Within a kind: the sort alone; an answered card takes its place by its date like any other. The engine's rank is its own
     order for the saved sort, used while this device has no newer pick of its own. */
  function sortList(list) {
    var mode = sortMode(), idx = list.map(function (it, i) { return [it, i, sortKey(it, mode)]; });
    var ranked = !sortPick() && list.length && list.every(function (it) { return typeof it.rank === 'number'; });
    var cmp = ranked ? function (x, y) { return x[0].rank - y[0].rank; } : function (x, y) { return keyCmp(x[2], y[2]); };
    idx.sort(function (a, b) { return cmp(a, b) || a[1] - b[1]; });
    return idx.map(function (x) { return x[0]; });
  }
  /* Group by kind off: every card the filter shows, in one order by the sort alone (style order inside the one list the feed then is) */
  function mixFeed(box) {
    var arts = [].slice.call(box.querySelectorAll('article.card[data-key]')).filter(function (el) { return !el.closest('#sec-held') && !el.closest('#sec-saidso'); });
    if (box.classList.contains('mix')) {
      var mode = sortMode(), keyed = arts.map(function (el, i) { var it = find(el.getAttribute('data-key')); return [el, i, it ? sortKey(it, mode) : null]; });
      keyed.sort(function (a, b) { return (a[2] ? 0 : 1) - (b[2] ? 0 : 1) || (a[2] && b[2] ? keyCmp(a[2], b[2]) : 0) || a[1] - b[1]; });
      keyed.forEach(function (x, n) { var o = String(n + 1); if (x[0].style.order !== o) x[0].style.order = o; });
    } else arts.forEach(function (el) { if (el.style.order) el.style.order = ''; });
  }
  function groupMode() { var st = setts(), v = st && st.page && st.page.group_by; return v === 'sender' || v === 'area' || v === 'conversation' ? v : 'none'; }
  function senderName(it) { return String(it.source_who || '').replace(/^[a-z]+:/i, '').trim() || (it.sender && it.sender.address) || ''; }
  function senderKey(it) { return String((it.sender && it.sender.address) || senderName(it)).toLowerCase(); }
  function groupKeyOf(it, mode) { if (it.group && it.group.key) return String(it.group.key); return mode === 'area' ? String(it.area || '') : mode === 'conversation' && it.thread ? 'c:' + it.thread : senderKey(it); }
  function groupLabelOf(it, mode) {
    if (it.group && it.group.label) return mode === 'sender' ? String(it.group.label).replace(/^[a-z]+:/i, '') : it.group.label;
    if (mode === 'area') return it.area || 'Other';
    if (mode === 'conversation' && it.thread) return it.thread_title || headerOf(it);
    return senderName(it) || 'Other';
  }
  /* The cards of one section, as one list or, when the owner chose to group them, as folds with a count. pairs: [card, how it is drawn] */
  function listHtml(pairs, scope) {
    var mode = groupMode();
    if (mode === 'none') return '<div class="cards">' + pairs.map(function (x) { return card(x[0], x[1]); }).join('') + '</div>';
    var order = [], map = {};
    pairs.forEach(function (x) { var k = groupKeyOf(x[0], mode); if (!map[k]) { map[k] = {label: groupLabelOf(x[0], mode), items: []}; order.push(k); } map[k].items.push(x); });
    return order.map(function (k) {
      var g = map[k], dk = 'g:by:' + mode + ':' + scope + ':' + k;
      return '<details class="grp" data-d="' + h(dk) + '"' + (S.open[dk] === false ? '' : ' open') + '><summary>' + hc(g.label) + ' <span class="cnt">' + g.items.length + '</span></summary><div class="cards">' +
        g.items.map(function (x) { return card(x[0], x[1]); }).join('') + '</div></details>';
    }).join('');
  }
  function ageDays(it) { var t = T(it.created_at || it.source_when); return t ? Math.max(0, Math.floor((Date.now() - t) / 864e5)) : 0; }
  function bucket(it) { var d = ageDays(it); return d < 1 ? 'a0' : d <= 3 ? 'a1' : d <= 7 ? 'a2' : 'a3'; }
  var AGES = [['a0', 'Today'], ['a1', '1 to 3 days'], ['a2', '4 to 7 days'], ['a3', 'Over a week']];
  function isNew(it) {
    if (it.state === 'done' || S.ans[it.key]) return false;                              /* his own answer is not news to him */
    if (it.answered_at && Math.abs(T(it.updated_at) - T(it.answered_at)) < 60000) return false;
    return T(it.updated_at || it.created_at) > T(S.baseline);
  }
  /* Later: when the card is due back. "someday" never comes back by itself. */
  function laterOver(a) {
    var u = String(a.until || '');
    if (u === 'someday') return false;
    if (!u) return String(a.at || '').slice(0, 10) !== today();          /* an older Not now: back the next day */
    return u.length > 10 ? u <= isoLocal(new Date()) : u <= today();
  }
  function isLater(a) { var n = pressName(a); return !!a && (a.action === 'later' || a.action === 'snooze' || n === 'later' || n === 'someday'); }
  function onShelf(a) { return isLater(a) && a.until === 'someday' && a.status !== 'failed'; }
  /* A press that leaves the card where it is: bringing it back, never junk, and a yes on a draft (the writing screen opens on the card). */
  function stays(it, a) {
    var n = pressName(a);
    if (!n && !isSend(a) && a && !a.calendar && (a.action === 'answer' || a.action === 'change') && a.label && a.question) return true;     /* one question's own answer button: the card stays */
    if (n === 'rule_offer') return /^(discuss|cancel)$/.test(String(pressOf(a).do));      /* rewording or cancelling a proposed rule: the card stays */
    if (n === 'wait_longer') return a.status === 'done';             /* acted on: the card is waiting again, in its own place */
    return n === 'bring_back' || n === 'never_junk' || n === 'undo' || n === 'always_show' || n === 'write_them' || n === 'old_card' || n === 'old_keep' || (n === 'approve' && !!it.draft && !!sendCfg());
  }
  function ansOf(it) {
    var a = S.ans[it.key], lp = it.last_press, g;
    /* A press the engine refused is never silent: the card comes back with the reason. */
    if (a && lp && lp.ok === false && lp.at === a.at && a.status !== 'failed') a = {action: a.action, text: a.text, at: a.at, until: a.until, result: a.result, label: a.label, status: 'failed', outcome: lp.happened || ''};
    if (a && a.status !== 'failed' && ((isLater(a) && laterOver(a)) || stays(it, a))) a = null;
    if (a) return a;
    g = groupOf(it);
    if (g && it.state !== 'done') return {action: 'answer', text: '{"press": {"name": "got_it"}}', group: true, at: g.at, status: g.status, outcome: g.outcome, result: 'Done'};
    /* A Later given on another device shows here too: the card itself carries it. */
    if (it.state !== 'done' && it.shelf === 'later' && !undone(it) && (!it.later_until || String(it.later_until) > isoLocal(new Date())))
      return {action: 'later', until: it.later_until || '', status: 'done', outcome: (lp && lp.happened) || 'Done', at: (lp && lp.at) || it.updated_at, result: 'Snoozed' + (it.later_until ? ' until ' + backWords(it.later_until) : '')};
    var cb = String(it.checkback_date || '').slice(0, 10), st = it.status || '';
    if (!it.header && it.state !== 'done' && cb > today() && (st === 'Not now' || /^Snoozed (to|until) /.test(st)))
      return {action: 'later', until: cb, status: 'done', outcome: 'Done', at: it.updated_at, result: 'Snoozed until ' + fmtD(D(cb))};
    if (it.answer && (it.state === 'question' || it.state === 'yours') && !(lp && lp.at && String(lp.at).slice(0, 19) >= String(it.answered_at || '').slice(0, 19)))
      return {action: 'applied', result: 'You answered', text: it.answer, at: it.answered_at};       /* not yet read: once read, the card is open as before */
    return null;
  }
  function backWords(u) { var d = D(u); return !d ? '' : sameDay(d, new Date()) ? 'about ' + fmtT(d) : fmtD(d); }
  /* An answered item leaves its place at once. It comes back, marked, only when acting on it
     failed or the engine left it with the owner after acting. */
  function away(it, a) {
    if (!a || a.action === 'applied' || a.status === 'failed') return false;
    if (a.status === 'done' && (it.state === 'question' || it.state === 'yours') && !isLater(a)) {
      /* The result names how new the item must be. Item data from before the result never brings the card back. */
      return !!a.as_of && String(it.updated_at || '') < String(a.as_of);
    }
    return true;
  }
  function returned(it, a) { return !!a && a.action !== 'applied' && !away(it, a); }
  function hay(it) {
    if (it._hay) return it._hay;
    var p = [it.id, it.title, it.header, it.wants, it.why, it.detail, it.area, (it.tags || []).join(' '), it.ref, it.who, it.about, it.waiting_on, it.source_who, it.source_ref, it.recommended, it.evidence, it.assistant_did, it.source_text, it.status, it.answer, (it.asks || []).join(' ')];
    if (it.draft) p.push(it.draft.subject, it.draft.body, (it.draft.to || []).join(' '));
    (it.search || []).forEach(function (x) { p.push(x); });
    (it.facts || []).forEach(function (f) { p.push(f[1]); });
    if (it.mini) p.push(it.mini.code, it.mini.text, it.mini.question, it.mini.quote);
    it._hay = p.join(' \n ').toLowerCase();
    return it._hay;
  }
  function match(it) {
    if (S.q && hay(it).indexOf(S.q) < 0) return false;
    if (S.by) { var k = S.by.slice(0, 2), v = S.by.slice(2), cut = v.indexOf('|');
      if (k === 'a:') { if (it.area !== v) return false; }
      else if (k === 'f:' && cut > 0) { if ((it.filters || {})[v.slice(0, cut)] !== v.slice(cut + 1)) return false; } }
    if (S.age && bucket(it) !== S.age) return false;
    return true;
  }

  /* ---------- pieces of a card ---------- */
  function titleHtml(it) {
    var t = headerOf(it), i = t.indexOf(': ');
    if (!it.header && t.length > 70 && i > 12 && i < t.length - 12) return hc(t.slice(0, i)) + '<span class="q-sub">' + hc(t.charAt(i + 2).toUpperCase() + t.slice(i + 3)) + '</span>';
    return hc(t);
  }
  function money(v) {
    if (v == null || v === '') return '';
    var n = Number(v);
    return isNaN(n) ? String(v) : '$' + n.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  }
  function choicesOf(it) {
    return (it.choices || []).map(function (c) {
      return typeof c === 'string' ? {label: c, text: c} : {label: c.label || c.text || c.value || '', text: c.text || c.value || c.label || ''};
    }).filter(function (c) { return c.label; });
  }
  /* The card statuses the engine stores, in the owner's words where the stored word is not (the voice guide, 11/25). */
  var CLOSED_ST = {'I closed it, no action taken': 1, 'Closed by your assistant': 1};
  var STATUS_SAY = {'Closed by your assistant': 'I closed it, no action taken', 'Back: no reply': 'Back: still no reply', 'Said no': 'You turned this rule down',
    'Standing approval made': 'You let me do this without asking', 'Not made': 'You said no', 'Holding their mail': 'Hiding their mail'};
  function statusSay(st) { st = String(st || ''); return /^Joined into /.test(st) ? 'Merged into another card' : STATUS_SAY[st] || st; }
  function lastDid(it) { return it.assistant_did ? String(it.assistant_did).split('\n').filter(Boolean).pop() : ''; }
  /* A finished card nobody acted on: joined into another card, or closed by the assistant's own reading with no press,
     answer or outcome of his. It is not shown as handled: it has its own fold under Handled for you, named for what happened. */
  function closedOnly(it) {
    if (it.state !== 'done') return false;
    var st = String(it.status || '');
    if (/^Joined into /.test(st) || CLOSED_ST[st]) return true;
    return !st && !it.answer && !it.answered_at && !it.last_press;
  }
  function closedWhy(it) {
    var st = String(it.status || ''), j = /^Joined into (\S+)/.exec(st);
    if (j) {
      var d = S.items.filter(function (x) { return x.id === j[1]; })[0];
      if (!d) return 'I merged this card into another one that is no longer on your page. Nothing was done on this one.';
      var nm = '"' + String(d.short_header || headerOf(d)) + '"';
      if (d.state !== 'done') return 'I merged this card into ' + nm + ', which is still open. Nothing was done on this one by itself.';
      return 'I merged this card into ' + nm + ', which has since ended' + (d.status ? ' (' + statusSay(d.status) + ')' : '') + '. Nothing was done on this one.';
    }
    var last = lastDid(it);
    if (CLOSED_ST[st] && last) {
      var why = last.replace(/^Closed by your assistant \S+ \S+ [AP]M:?\s*/, '').replace(/^\S+ \S+ [AP]M: I closed it, no action taken:?\s*/, '');
      return /^,? ?(with no reason given|and I gave no reason)\.?$/.test(why) || !why ? 'I marked this Done and gave no reason.' : 'I marked this Done: ' + why;
    }
    return 'I marked this Done; nothing shows it was done.';
  }
  // The card's history stays folded shut, so answering a card never makes it bigger.
  function historyHtml(it) {
    var lines = it.assistant_did ? String(it.assistant_did).split('\n').filter(function (l) { return l.trim(); }) : [];
    if (!lines.length) return '';
    return more(it, 'history', 'History <span class="cnt">' + lines.length + '</span>', lines.map(function (l) { return '<div class="kv">' + hc(l) + '</div>'; }).join(''));
  }
  function more(it, name, label, inside) {
    var k = name + ':' + it.key;
    return '<details class="more" data-d="' + h(k) + '"' + (S.open[k] ? ' open' : '') + '><summary>' + label + '</summary><div class="inside">' + inside + '</div></details>';
  }
  function docsHtml(it) {
    var list = (it.documents || []).filter(function (d) { return d && d.file; });
    if (!list.length) return '';
    var unread = list.filter(function (d) { return !d.read; }).length;
    var inner = '<div class="kv">These are the words I read from each paper, not a picture of the page.</div>';
    if (unread) inner += '<div class="kv"><b>' + (unread === 1 ? 'I haven\'t read one paper yet, so it can\'t' : 'I haven\'t read ' + unread + ' papers yet, so they can\'t') + ' be shown here.</b> Look at ' + (unread === 1 ? 'it' : 'them') + ' in the original message before you answer.</div>';
    list.forEach(function (d, i) {
      if (d.read) inner += more(it, 'doc' + i, h(d.file) + (d.pages > 1 ? ' <span class="cnt">' + h(d.pages) + ' pages</span>' : ''), '<pre class="src-text">' + h(d.text || '') + '</pre>');
      else inner += '<div class="kv"><b>' + h(d.file) + ':</b> not read yet, so it cannot be shown here.</div>';
    });
    return more(it, 'docs', 'Attached papers <span class="cnt">' + list.length + '</span>' + (unread ? ' <span class="cnt">' + unread + ' cannot be shown yet</span>' : ''), inner);
  }
  function tableHtml(t) {
    var cols = t.columns || [];
    return '<div class="lines-wrap"><table class="lines"><thead><tr>' + cols.map(function (c) { return '<th' + (c.num ? ' class="num"' : '') + '>' + h(c.t) + '</th>'; }).join('') + '</tr></thead><tbody>' +
      t.rows.map(function (r) {
        return '<tr>' + cols.map(function (c, i) { return '<td' + (c.num ? ' class="num"' : '') + '>' + (c.code ? '<span class="part">' + h(r[i]) + '</span>' : h(r[i])) + '</td>'; }).join('') + '</tr>';
      }).join('') + '</tbody></table></div>';
  }
  /* The opened card (ITEMS.md "Cards made simpler"): three sections, all shown at once, nothing folded inside them.
     Context: what happened, with each message, paper and picture behind it as a link that opens it over the page.
     The draft, when there is one. Conversation: what was done and said on the card, his questions and its replies, oldest first. */
  function inside(it, s) {
    var o = '<section class="sec-in ctx"><h4>Context</h4>' + contextHtml(it, s) + '</section>';
    if (it.draft) {
      var d = it.draft, dd = '';
      if ((d.to || []).length) dd += '<div class="kv"><b>To:</b> ' + h(d.to.join(', ')) + '</div>';
      if ((d.cc || []).length) dd += '<div class="kv"><b>Copy to:</b> ' + h(d.cc.join(', ')) + '</div>';
      if (d.subject) dd += '<div class="kv"><b>Subject:</b> ' + h(d.subject) + '</div>';
      if ((d.attach || []).length) dd += '<div class="kv"><b>Attached:</b> ' + h(d.attach.join(', ')) + '</div>';
      dd += '<pre class="src-text">' + h(d.body || '') + '</pre>';
      if (s !== 'done' && sendOff()) dd += '<div class="kv">' + h(sendOff()) + '</div>';
      o += '<section class="sec-in draft"><h4>The draft</h4>' + dd + '</section>';
    }
    var lines = it.assistant_did ? String(it.assistant_did).split('\n').filter(function (l) { return l.trim(); }) : [];
    var wr = ansOf(it);      /* the reply that used to sit in a box above the title */
    /* the reply is added only when the history does not hold it already; compared with spaces and line breaks made one, as a
       reply of more than one paragraph is kept in the history with its blank line dropped (it showed twice) */
    var flat = function (x) { return String(x || '').replace(/\s+/g, ' ').trim(); };
    if (wr && returned(it, wr) && !isSend(wr) && wr.outcome && flat(wr.outcome) && flat(lines.join(' ')).indexOf(flat(wr.outcome)) < 0) lines.push('My reply: ' + String(wr.outcome).trim());
    o += '<section class="sec-in conv"><h4>Conversation</h4>' + (lines.length ? '<ol class="conv-list">' + lines.map(function (l) {
      return '<li' + (/^You /.test(l) ? ' class="you"' : '') + '>' + hc(l) + '</li>'; }).join('') + '</ol>' : '<div class="kv">Nothing said or done on this card yet.</div>') + '</section>';
    return o;
  }
  /* A link in Context: a paper or picture opens as itself, a message as the message, over the page; Close returns to the card. */
  function viewLink(words, x) {
    return '<button class="link view-link" data-a="view"' + (x.ref ? ' data-ref="' + h(x.ref) + '"' : '') + (x.kind ? ' data-kind="' + h(x.kind) + '"' : '') +
      (x.msg != null ? ' data-msg="' + h(x.msg) + '"' : '') + (x.name ? ' data-name="' + h(x.name) + '"' : '') + (x.sample ? ' data-sample="1"' : '') + '>' + words + '</button>';
  }
  function msgWords(m) {
    var t = D(m.when);
    return (m.who === 'You' ? 'your ' : (m.who ? m.who + "'s " : 'the ')) + (m.channel === 'email' || !m.channel ? 'email' : 'message') + (t ? ' of ' + fmtD(t) + ' ' + fmtT(t) : '');
  }
  function contextHtml(it, s) {
    var lead = [], cb = cameBack(it), story = it.detail && !(it.mini && String(it.detail).trim() === String(it.mini.question || '').trim()) ? hc(it.detail) : '';
    if (cb && s !== 'done') lead.push(h(cb) + '.');
    if (it.contact && it.contact.words && s !== 'done') lead.push(h(it.contact.words));      /* how often he is in touch with whoever wrote it */
    if ((s === 'motion' || s === 'tracked') && (it.waiting_on || it.checkback_date)) { var cbw = String(it.checkback_date || '').slice(0, 10); lead.push(h((it.waiting_on ? 'Waiting on ' + it.waiting_on : 'Someone else has the next move') + (cbw ? '; looked at again ' + fmtD(D(cbw)) : '') + '.')); }
    var docs = (it.documents || []).filter(function (d) { return d && d.file; }), msgs = it.messages || [], left = [];
    /* each paper the story names becomes a link where it is named; the rest are named after it */
    docs.forEach(function (d) {
      var x = {ref: d.ref, kind: d.kind || 'file', name: d.file}, base = d.file.replace(/\.[a-z0-9]{2,5}$/i, ''), done = false;
      [d.file, base].forEach(function (w) {
        if (done || !story || w.length < 4) return;
        var parts = story.split(/(<[^>]+>)/), ew = h(w), low = ew.toLowerCase();
        for (var i = 0; i < parts.length && !done; i += 2) {
          var at = parts[i].toLowerCase().indexOf(low);
          if (at >= 0) { parts[i] = parts[i].slice(0, at) + viewLink(parts[i].slice(at, at + ew.length), x) + parts[i].slice(at + ew.length); done = true; }
        }
        if (done) story = parts.join('');
      });
      if (!done) left.push(viewLink(h(d.file), x));
    });
    /* each message the story speaks of ("forwarded a message", "your email of 11/3") is linked there, in order; the rest after it */
    var unlinked = msgs.slice();
    if (story && msgs.length) {
      var parts = story.split(/(<[^>]+>)/), inLink = false;
      for (var pi = 0; pi < parts.length && unlinked.length; pi++) {
        if (pi % 2) { if (/^<button/.test(parts[pi])) inLink = true; else if (/^<\/button/.test(parts[pi])) inLink = false; continue; }
        if (inLink) continue;
        parts[pi] = parts[pi].replace(/\b(?:a|an|the|this|that|his|her|their|your|my|its)\s+(?:forwarded\s+|first\s+|last\s+|new\s+|newest\s+|original\s+)?(?:message|email|e-mail|text|note|reply|letter)\b/gi, function (w) {
          if (!unlinked.length) return w;
          var m = unlinked.shift();
          return viewLink(w, {msg: m.id, name: m.subject || msgWords(m)});
        });
      }
      story = parts.join('');
    }
    var o = lead.length ? '<p class="ctx-lead">' + lead.join(' ') + '</p>' : '';
    if (story) o += '<div class="detail story">' + story + '</div>';
    if (it.rule && it.rule.from) o += '<p>This rule came from what you pressed on the card <b>' + hc(it.rule.from) + '</b>.</p>';
    if (it.update && it.update.version) o += updHtml(it);
    if (left.length) o += '<p>' + (left.length === 1 ? 'The paper: ' : 'The papers: ') + left.join(', ') + '.</p>';
    if (unlinked.length) o += '<p>' + (msgs.length === 1 ? 'It came in ' : unlinked.length < msgs.length ? 'It also rests on ' : 'It rests on ') + unlinked.map(function (m) { return viewLink(h(msgWords(m)), {msg: m.id, name: m.subject || msgWords(m)}); }).join(', ') + '.</p>';
    else if (it.source_text && (it.source_ref || it.source_who)) o += '<p>' + viewLink('The message it came from', {msg: -1, name: it.source_ref || it.source_who}) + '.</p>';
    if (it.sample && s !== 'done') o += '<p>' + viewLink('Their newest email', {sample: 1, name: 'Their newest email'}) + ' shows what this sender writes.</p>';
    if (it.roadmap && it.roadmap.key && rmCan() && rmDoc(it.roadmap.key)) o += '<p><button class="link" data-a="rm-card">Open it in the roadmap</button></p>';
    var a = ageDays(it), about = [statusSay(it.status), a < 1 ? 'arrived today' : plural(a, 'day') + ' old'].filter(Boolean);
    if (it.importance && it.important_reason) about.unshift('Important: ' + it.important_reason);
    var line = about.join(', ');
    o += '<p class="kv">' + hc(line.charAt(0).toUpperCase() + line.slice(1)) + '.</p>';
    return o || '<div class="kv">Nothing more is known about this card.</div>';
  }
  /* The marks beside the title: Due, Important and New only. */
  function tagsHtml(it) {
    var o = '';
    if (it.due_date) { var late = it.due_date < today(); o += '<span class="tag ' + (it.due_date <= today() ? 'crit' : 'warn') + '">' + (late ? 'Was due ' : it.due_date === today() ? 'Due today' : 'Due ') + (it.due_date === today() ? '' : h(fmtD(D(it.due_date)))) + '</span>'; }
    if (it.importance) o += '<span class="tag crit">Important</span>';
    if (isNew(it)) o += '<span class="tag new">New</span>';
    return o;
  }
  /* [data-a, label, style, data-text, {attr: value}] */
  function btnHtml(x) {
    var more = '', k;
    for (k in x[4] || {}) more += ' data-' + k + '="' + h(x[4][k]) + '"';
    return '<button class="btn ' + (x[2] || '') + '" data-a="' + x[0] + '" title="' + String(x[1]).replace(/<[^>]*>/g, '').replace(/"/g, '&quot;') + '"' + (x[3] != null ? ' data-text="' + h(x[3]) + '"' : '') + more + '>' + x[1] + '</button>';
  }
  /* Every open question with its own choices and recommended answer (D9). A card from before `questions` gives its choices to the first. */
  function questionsOf(it, s) {
    if (s !== 'decide' && s !== 'words' && s !== 'small' && s !== 'new' && !(it.came_back && s !== 'done' && s !== 'someday' && s !== 'fyi')) return [];
    var qs =Array.isArray(it.questions) && it.questions.length ? it.questions : asksOf(it).map(function (a, i) { return {ask: a, choices: i ? [] : (it.choices || [])}; });
    var asked = /\?\s*$/.test(String(it.wants || '')) ? it.wants : 'Which do you choose?';       /* a question, never the recommendation */
    if (!qs.length && (it.choices || []).length) qs = [{ask: asked, choices: it.choices}];     /* choices kept from before, with no question text */
    if (!qs.length && it.draft && sendCfg() && !(it.update && it.update.version)) qs = [{ask: 'Send this reply?', choices: []}];     /* a draft: its question, Check and send under it */
    if (!qs.length && it.came_back) {      /* an older came-back card with no question text: one is written from its recommendation, never a bare row of choices */
      var cb = typeof it.came_back === 'object' ? it.came_back : {}, who = cb.who || 'them', rf = String(it.rec_front || it.recommended || '').trim();
      qs = [{ask: /\?\s*$/.test(rf) ? rf : cb.why === 'message' ? 'Answer ' + who + '?' : 'Send ' + who + ' a reminder?', choices: []}];
    }
    qs = qs.map(function (q) { return {ask: q.ask || asked, choices: q.choices}; });
    var pk = pickShown(it, s) && it.pick.do === 'choice' ? String(it.pick.text || '').toLowerCase() : null;
    return qs.map(function (q, qi) {
      var ch = (q.choices || []).map(function (c) {
        if (typeof c === 'string') return {label: c, text: c};
        var t = c.text || c.value || c.label || '';
        return {label: String(c.label || t).replace(/ \(recommended\)$/, ''), text: t, recommended: !!c.recommended, id: c.id, meaning: c.meaning};
      }).filter(function (c) { return c.label && !(qi === 0 && pk && String(c.text).toLowerCase() === pk); });     /* the pick is the first button already */
      return {ask: String(q.ask || ''), choices: ch};
    }).filter(function (q) { return q.ask || q.choices.length; });
  }
  /* The buttons of one question: its recommended answer first and highlighted, its other choices, then Other (B1, B2, B2a).
     Each choice carries its button id and its meaning (the engine checks it against its list); a choice that names
     neither gets its place on the question as its id and the meaning other. */
  function choiceBtns(ch, n) {
    var out = [], at = n ? {q: n} : {}, rec = ch.filter(function (c) { return c.recommended; })[0];
    var own = function (c) { var a = {}, k; for (k in at) a[k] = at[k]; a.b = c.id || 'q' + (n || 1) + '-' + (ch.indexOf(c) + 1); a.m = c.meaning || 'other'; return a; };
    if (rec) out.push(['choice', hc(rec.label), 'primary', rec.text, own(rec)]);
    ch.forEach(function (c) { if (c !== rec) { var other = /\(say which\)/i.test(c.label); out.push([other ? 'other' : 'choice', hc(c.label.replace(/\s*\(say which\)/i, '')), '', c.text, other ? at : own(c)]); } });
    out.push(['other', 'Other', '', null, at]);
    return out;
  }
  /* Every question on the front, numbered (D6, D9): its words, its recommended answer, and its own buttons under it. The first
     question of a card whose answer is an action (a calendar entry, a rule, an update, a draft, a reminder) carries that action. */
  function questionsHtml(it, s) {
    var qs = questionsOf(it, s), first = leadOf(it, s, qs);
    if (!qs.length) return '';
    return '<ol class="qs">' + qs.map(function (q, i) {
      var rec = q.choices.filter(function (c) { return c.recommended; })[0];
      var btns = i === 0 && first.length ? first : choiceBtns(q.choices, qs.length > 1 ? i + 1 : 0);
      return '<li><div class="q-ask">' + hc(q.ask) + (rec ? ' <span class="q-rec">Recommended: ' + hc(rec.label) + '</span>' : '') + '</div>' +
        '<div class="acts' + (btns.some(function (x) { return x[0] === 'choice' && x[1].length > 30; }) ? ' tall' : '') + '">' + btns.map(btnHtml).join('') + '</div></li>';
    }).join('') + '</ol>';
  }
  /* A card of several questions: each one already answered is a small closed card of its own, shown with his answer, what
     was done for it and Change (his new answer goes in the card's box, for that question only). The card closes on its own
     once every question is answered. */
  function answeredHtml(it, s) {
    var a = Array.isArray(it.answered) ? it.answered : [];
    if (!a.length || s === 'done' || s === 'someday') return '';
    return '<ul class="qs-done">' + a.map(function (x, i) {
      return '<li><div class="q-ask">Answered: ' + hc(x.ask || '') + '</div><div class="q-said">Your answer: ' + hc(x.answer || '') +
        (x.did ? '. ' + hc(x.did) : '') + '</div><div class="acts">' + btnHtml(['ans-change', 'Change', '', null, {r: i + 1}]) + '</div></li>';
    }).join('') + '</ul>';
  }
  /* The buttons of a card's first question when its answer is an action rather than one of its choices. [] when its choices do. */
  function leadOf(it, s, qs) {
    var lead = [], cal = it.calendar && typeof it.calendar === 'object' && s !== 'done' && s !== 'fyi' && s !== 'someday' ? it.calendar : null;
    if (s === 'done' || s === 'someday') return lead;
    if (it.rsi && it.rsi.id) return [['rsi-go', it.rsi.kind === 'setting' ? 'Apply' : 'Approve', 'primary'], ['rsi-no', 'Reject', '']];     /* a rule change card: its two buttons only */
    if (cal) { lead.push(['cal-add', 'Add to calendar', 'primary']); lead.push(['cal-open', 'Pick another time', '']); }
    else if (it.update && it.update.version) lead.push(['upd-go', 'Update', 'primary']);
    else if (it.rule && (s === 'decide' || s === 'words' || s === 'small')) lead.push(['approve', 'Save this rule', 'primary']);
    else if (it.draft && sendCfg() && (s === 'decide' || s === 'words' || s === 'small' || s === 'task')) lead.push(['send-check', 'Check and send', 'primary']);
    else if (qs.length && qs[0].choices.length) lead = choiceBtns(qs[0].choices, qs.length > 1 ? 1 : 0);
    else if (qs.length && it.rec_front && (it.needs === 'approval' || !it.came_back)) { lead.push(['approve', 'Go ahead', 'primary']); lead.push(['other', 'Other', '']); }     /* a yes-or-no question with a recommendation: yes is doing it */
    if (it.came_back) {
      if (!lead.some(function (x) { return x[0] === 'choice'; })) lead.unshift(['write-them', 'Send reminder', 'primary']);
      if (!lead.some(function (x) { return /^keep waiting$/i.test(x[1]); })) lead.splice(lead[0] && lead[0][0] === 'write-them' ? 1 : lead.filter(function (x) { return x[0] === 'choice'; }).length, 0, ['keep-waiting', 'Keep waiting', '']);
    }
    if (qs.length && !lead.some(function (x) { return x[0] === 'other'; })) lead.push(['other', 'Other', '', null, qs.length > 1 ? {q: 1} : {}]);
    return lead;
  }
  /* One row of buttons, one meaning each, in this order: the recommended action, the other choices, Other, Reply, Later, Done,
     Not needed (B1-B9). A card shows only the ones that apply; a card that asks nothing leads with Done. No More. */
  function buttons(it, s) {
    var lead = [], tail = [], ch = [], qs = questionsOf(it, s), cal = it.calendar && typeof it.calendar === 'object' && s !== 'done' && s !== 'fyi' && s !== 'someday' ? it.calendar : null;
    var p = S.panel[it.key], k = h(it.key), o = '', key = String(it.source_key || '');
    var teach = teachOf(it, s), nn = teach.filter(function (t) { return /^not_needed/.test(t); }), fromSender = !!(it.sender || (it.messages || []).length || it.source_text);
    var openCard = s !== 'done' && s !== 'someday';
    if (s === 'done') lead.push(['back', 'Bring it back', 'primary']);
    else if (s === 'someday') { lead.push(['back', 'Bring it back', 'primary']); lead.push(['done', 'Done', '']); }
    else if (it.rsi && it.rsi.id) { if (!qs.length) lead = leadOf(it, s, qs); }      /* a rule change card: Approve or Apply, and Reject; no Snooze or Done */
    else {
      if (!qs.length) lead = leadOf(it, s, qs);         /* with a question, its buttons are under it (questionsHtml) */
      if (sendCfg() && replyOf(it) && !it.draft && !cal && !it.rule && !(it.update && it.update.version) && !(it.roadmap && it.roadmap.key)) tail.push(['write', 'Reply', '']);
      /* a card that asks yes or no (a proposed rule, a standing approval offer, a project write) has its own No in Done's place, and no Drop */
      var yesNo = !!(it.rule || /^(rule:|live:standing-|live:projwrite-)/.test(key)), done = yesNo ? ['no', 'No', ''] : ['done', 'Done', ''];
      /* on every open card: Done (a task finished), Drop (not to be considered), Snooze, Other; Got it only where nothing is asked */
      if (!lead.length && !qs.length) {
        if (!yesNo && it.needs === 'nothing') lead.push(['got-it', 'Got it', 'primary']); else done[2] = 'primary';
        lead.push(done);
      } else tail.push(done);
      if (!yesNo) tail.push(['drop', 'Drop', '']);
      tail.push(['later', 'Snooze', '']);
      if (nn.length && fromSender) tail.push(['not-needed', 'Not needed', '']);
      if (!qs.length && !lead.some(function (x) { return x[0] === 'other'; })) tail.push(['other', 'Other', '', null, {noq: '1'}]);
      /* the switchable buttons the engine chose for this card (card.switches): each is its own press, its meaning the engine's */
      (Array.isArray(it.switches) ? it.switches : []).forEach(function (w) { if (w && w.id && w.label) tail.push(['switch', h(w.label), '', null, {p: w.id}]); });
    }
    var dup = pickShown(it, s) ? pickAct(it.pick) : '';      /* the pick's own button is first already: not twice */
    var row = lead.concat(tail).filter(function (x) { return !dup || x[0] !== dup; }), tall = row.some(function (x) { return x[0] === 'choice' && x[1].length > 30; });
    o += '<div class="acts row-main' + (tall ? ' tall' : '') + '">' + row.map(btnHtml).join('') + '</div>';
    if (p === 'nn') {
      o += '<div class="panel-box"><label>What did you not need?</label><div class="acts">' +
        (nn.indexOf('not_needed_this') >= 0 ? btnHtml(['nn-go', 'Just this one', '', null, {t: 'this'}]) : '') +
        (nn.indexOf('not_needed_sender') >= 0 ? btnHtml(['nn-go', 'Everything from this sender', '', null, {t: 'sender'}]) : '') +
        (nn.indexOf('not_needed_kind') >= 0 ? btnHtml(['nn-other', 'Other', '']) : '') +
        btnHtml(['cancel', 'Cancel', '']) + '</div></div>';
    } else if (p === 'later') {
      var offers = laterOffers();
      o += '<div class="panel-box"><label>Bring this back</label><div class="acts">' +
        LATER.filter(function (w) { return offers.indexOf(w[0]) >= 0; }).map(function (w) { return '<button class="btn" data-a="later-go" data-when="' + w[0] + '">' + w[1] + '</button>'; }).join('') + '</div>' +
        (offers.indexOf('date') < 0 ? '' : '<label for="s-' + k + '">Or on a date</label><div class="pick-day"><input type="date" id="s-' + k + '" data-snooze="' + k + '" min="' + dayPlus(1) + '" value="' + h(S.drafts['s:' + it.key] || '') + '">' +
        '<button class="btn" data-a="later-go" data-when="date">On this date</button></div>') +
        '<div class="acts"><button class="btn" data-a="cancel">Cancel</button></div></div>';
    } else if (p === 'cal' && cal) {
      o += calPanel(it, cal, true);
    } else if ((p === 'write' || p === 'review') && (it.draft || replyOf(it))) {
      o += writerHtml(it);
    }
    if (openCard) o += boxHtml(it);
    if (S.err[it.key]) o += '<div class="err" role="alert">' + h(S.err[it.key]) + '</div>';
    return o;
  }
  /* My pick (picks.py): what I predict he will do with this card, its first button; one press does it. What he did instead
     on the last card like it sits beside it, so the choices grow from his habits. Not on a closed card or a rule change card. */
  function pickShown(it, s) { return !!(it.pick && it.pick.label && s !== 'done' && s !== 'someday' && !(it.rsi && it.rsi.id)); }
  function pickAct(p) {
    return p && p.do === 'press' ? ({done: 'done', got_it: 'got-it', drop: 'drop', approve: 'approve', wait_longer: 'keep-waiting', no: 'no', not_needed: 'not-needed'})[p.press] || '' : '';
  }
  function pickHtml(it, s) {
    if (!pickShown(it, s)) return '';
    var lt = it.last_time;
    return '<div class="acts pick-row"><span class="pick-tag">My pick</span>' + btnHtml(['pick', hc(it.pick.label), 'primary']) +
      (lt && lt.label ? btnHtml(['last-time', hc('Last time: ' + lt.label), '']) : '') + '</div>';
  }
  /* The answer one press of a pick (or of what he did last time) sends: the same as pressing that choice or button. */
  function pickRec(it, p) {
    if (!p) return null;
    if (p.do === 'choice') {
      var q0 = Array.isArray(it.questions) && it.questions.length ? it.questions[0].choices || [] : it.choices || [], r = {action: 'answer', label: p.text, text: p.text, result: 'Answered'};
      q0.forEach(function (c, i) {
        var t = typeof c === 'string' ? c : c.text || c.value || c.label || '';
        if (String(t).toLowerCase() === String(p.text).toLowerCase() && typeof c === 'object') { r.button = c.id || 'q1-' + (i + 1); r.meaning = c.meaning || 'other'; }
      });
      if (Array.isArray(it.questions) && it.questions.length > 1) r.question = 1;     /* a card of several: the pick answers its first question only */
      return r;
    }
    if (p.do === 'reply') return {action: 'answer', text: 'Draft a reply: ' + p.gist, label: p.label};
    if (p.do === 'words') return {action: 'answer', text: p.words, label: p.label};
    if (p.do === 'none') return pressRec('leave', null, 'Leaving it as it is');
    if (p.press === 'later') { var lr = pressRec('later', {when: 'tomorrow'}, 'Snoozed'); lr.until = laterUntil('tomorrow', ''); lr.label = p.label; lr.result = 'Snoozed until ' + backWords(lr.until); return lr; }
    if (p.press === 'not_needed') return pressRec('not_needed', {scope: 'this'}, 'Not needed');
    if (p.press === 'wait_longer') return pressRec('wait_longer', null, 'Keeping waiting');
    if (p.press === 'approve') { var ar = pressRec('approve', null, 'Going ahead'); if (it.draft && sendCfg()) { openDraft(it); ar.keepPanel = true; } return ar; }
    return pressRec(p.press, null, p.label);
  }
  /* The one box (B3): words to the assistant about this card. Other marks it for one question ("Your answer to 2:");
     Not needed, Other marks it "What did you not need?". The card stays, "Reading...", until the assistant has read them. */
  function boxHtml(it) {
    var k = h(it.key), m = S.box[it.key] || {}, label = m.nn ? 'What did you not need?' : m.r ? 'Your new answer to: ' + m.ask : m.q && /^live:modcheck-/.test(String(it.source_key || '')) ? 'What happened?' : m.q ? 'Your answer to ' + m.q + ':' : m.q === 0 ? 'Your answer to 1:' : 'Ask or tell me about this card';
    var reading = S.think[it.key] || it.status === 'Thinking';
    var marked = m.nn || m.r || m.q != null;
    return '<div class="ask-box' + (marked ? ' marked' : '') + '"><label for="ab-' + k + '"' + (marked ? '' : ' class="sr"') + '>' + h(label) + '</label>' +
      '<textarea autocomplete="off" name="box-1" id="ab-' + k + '" rows="1" data-draft="' + k + '" data-box="' + k + '" placeholder="' + h(marked ? label : 'Ask or tell me about this card...') + '">' + h(S.drafts[it.key] || '') + '</textarea>' +
      '<button class="btn" data-a="box-save">Save</button>' +
      (marked ? '<button class="btn" data-a="box-clear">Cancel</button>' : '') + '</div>' +
      (reading ? '<div class="reading" role="status"><span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>Reading...</div>' : '') + offerHtml(it);
  }
  /* A rule proposed from his words on this card (card_rules.py): the assistant's answer and the rule in one sentence, under
     the box, with Approve, Disapprove, Discuss and Cancel. Discuss opens a reply box under it; each new wording shows the
     same four buttons. Gone at once on Approve, Disapprove or Cancel. */
  function offerHtml(it) {
    var o = it.rule_offer, k = h(it.key), a = S.ans[it.key], p = pressOf(a);
    if (!o || !o.text) return '';
    var mine = p && p.name === 'rule_offer' && a.status !== 'done' && a.status !== 'failed' && String(a.at || '') > String(o.at || '');      /* pressed, not yet acted on */
    if (mine && p.do !== 'discuss') return '';
    var talk = (o.talk || []).slice(-4).map(function (t) { return '<li class="' + (t.who === 'you' ? 'me' : 'it') + '">' + (t.who === 'you' ? 'You: ' : '') + hc(t.text) + '</li>'; }).join('');
    var o2 = '<div class="rule-offer" role="group" aria-label="Proposed rule">' +
      (o.say ? '<div class="ro-said">' + hc(o.say) + '</div>' : '') +
      '<div class="ro-rule">Proposed rule: <b>' + hc(o.text) + '</b></div>' + (o.reason ? '<div class="ro-why">Because: ' + hc(o.reason) + '</div>' : '') + (talk ? '<ol class="ro-talk">' + talk + '</ol>' : '');
    if (mine) return o2 + '<div class="reading" role="status"><span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>Rewording...</div></div>';
    o2 += '<div class="acts">' + [['ro-approve', 'Approve', 'primary'], ['ro-disapprove', 'Disapprove', ''], ['ro-discuss', 'Discuss', ''], ['ro-cancel', 'Cancel', '']].map(btnHtml).join('') + '</div>';
    if (S.panel[it.key] === 'ro-discuss') o2 += '<div class="ask-box marked"><label for="ro-' + k + '">How should the rule read?</label>' +
      '<textarea autocomplete="off" id="ro-' + k + '" rows="1" data-draft="ro:' + k + '" data-ro="' + k + '" placeholder="How should the rule read?">' + h(S.drafts['ro:' + it.key] || '') + '</textarea>' +
      '<button class="btn primary" data-a="ro-send">Send</button></div>';
    return o2 + '</div>';
  }
  /* What an approved rule did to his other open cards, on the card it came from (and on its reply in the talk): one Undo. */
  function scanHtml(sc) {
    if (!sc || !sc.id || !sc.n) return '';
    var sent = S.ans['rule-scan:' + sc.id];
    if (sc.undone) return '<div class="rule-scan">' + hc(sc.said) + ' Undone: they are back as they were.</div>';
    return '<div class="rule-scan" role="status">' + hc(sc.said) + (sent && sent.status !== 'failed' ? ' <span>' + h(sent.status === 'done' ? sent.outcome || 'Put back.' : 'Putting them back...') + '</span>'
      : ' <button class="btn" data-a="scan-undo" type="button" data-id="' + h(sc.id) + '">Undo</button>' + (sent ? ' <span class="bad">' + h(sent.outcome || 'That Undo did not go through.') + '</span>' : '')) + '</div>';
  }
  function scanUndo(id) {
    var k = 'rule-scan:' + id;
    if (!id || (S.ans[k] && S.ans[k].status !== 'failed')) return;          /* one press counts once */
    chgSend(k, JSON.stringify({press: {name: 'scan_undo'}}), 'Undo what a rule did', 'Putting the cards back');
    render(); renderTalk();
  }
  /* Later offers five things, these four and a date, or only the ones the owner kept in Settings. */
  function laterOffers() { var st = setts(), l = st && st.page && st.page.later_offers; return Array.isArray(l) && l.length ? l : ['today', 'tomorrow', 'next_week', 'date', 'someday']; }
  /* The teaching presses a card may offer (ITEMS.md "Teaching presses on a card"): the engine names them, in order. */
  var TEACH = {not_needed_sender: 'This sender', not_needed_kind: 'This kind of message', not_needed_this: 'Only this one', always_sender: 'This sender', always_kind: 'This kind of message'};
  function teachOf(it, s) {
    if (s === 'done' || s === 'someday' || it.old_cards || it.rule || it.review || /^live:standing-/.test(String(it.source_key || ''))) return [];
    return Array.isArray(it.teach) ? it.teach.filter(function (t) { return TEACH[t]; }) : ['not_needed_this'];
  }
  function teachLabel(t) { return t[0].slice(0, 6) === 'always' ? 'Always show these' : 'I did not need this'; }
  function whoOf(it) { return String(it.source_who || '').replace(/^[a-z]+:/, '') || (it.sender && it.sender.address) || 'This sender'; }
  /* The asking card for old cards: one row for each, with Keep, Someday and Drop. A row leaves on its press. */
  function oldRows(it) {
    var gone = S.oldDone[it.key] || {}, back = S.oldBack[it.key] || {}, rows = (it.old_cards || []).slice();
    Object.keys(back).forEach(function (id) {             /* a row he took back shows again at once, until the engine lists it */
      if (Date.now() - back[id].t > 20000) { delete back[id]; return; }
      if (!rows.some(function (r) { return r.id === id; })) rows.push(back[id].row);
    });
    return rows.filter(function (r) { return r && !gone[r.id]; });
  }
  function oldHtml(it) {
    var rows = oldRows(it), k = h(it.key);
    return '<ul class="rows">' + rows.map(function (r) {
      return '<li><span class="t">' + hc(r.header || r.id) + '</span><span class="src">' + (r.days != null ? 'Has sat ' + plural(+r.days, 'day') : '') + '</span>' +
        '<div class="acts">' + [['keep', 'Keep'], ['later', 'Snooze'], ['done', 'Done']].map(function (b) { return '<button class="btn" data-a="old-go" data-card="' + h(r.id) + '" data-do="' + b[0] + '">' + b[1] + '</button>'; }).join('') + '</div>' +
        (S.open['ol:' + it.key + ':' + r.id] ? '<div class="acts">' + LATER.map(function (w) { return '<button class="btn" data-a="old-later" data-card="' + h(r.id) + '" data-when="' + w[0] + '">' + w[1] + '</button>'; }).join('') + '</div>' : '') + '</li>';
    }).join('') + '</ul>' + (S.err[it.key] ? '<div class="err" role="alert">' + h(S.err[it.key]) + '</div>' : '');
  }
  /* The weekly review (ITEMS.md "Design round 3"): parts in three groups. A row is one of the owner's own cards; its buttons are
     the ordinary presses on that card, so each leaves the review at once and has the usual Undo. */
  var REV_GROUPS = {clear: 'Get clear', current: 'Get current', creative: 'Get creative'};
  var REV_LABEL = {done: 'Done', later: 'Snooze', bring_back: 'Bring it back', wait_longer: 'Keep waiting', drop: 'Done', keep: 'Keep', old_keep: 'Keep'};
  function revRowGone(rv, r) {
    var c = r.id ? find(r.id) : null, mark = (S.revDone[rv.key] || {})[r.id];
    if (mark && S.ans[r.id] && S.ans[r.id].at === mark) return true;
    if (!c) return false;
    if (c.state === 'done') return true;
    return (r.presses || []).indexOf('bring_back') >= 0 ? !c.shelf : !!c.shelf;
  }
  function revRow(rv, r) {
    var rid = String(r.id || ''), pick = S.open['rp:' + rv.key + ':' + rid], panel = '';
    var btns = (r.presses || []).map(function (n) { return '<button class="btn" data-a="rev-go" data-row="' + h(rid) + '" data-p="' + h(n) + '">' + h(REV_LABEL[n] || n) + '</button>'; }).join('');
    if (pick === 'later') panel = '<div class="acts">' + LATER.map(function (w) { return '<button class="btn" data-a="rev-later" data-row="' + h(rid) + '" data-when="' + w[0] + '">' + w[1] + '</button>'; }).join('') + '</div>';
    if (pick === 'wait_longer') panel = '<div class="acts">' + [3, 5, 7].map(function (n) { return '<button class="btn" data-a="rev-wait" data-row="' + h(rid) + '" data-days="' + n + '">' + plural(n, 'day') + '</button>'; }).join('') + '</div>';
    return '<li><span class="t">' + hc(r.header || rid) + '</span>' + (r.note ? '<span class="src">' + hc(r.note) + '</span>' : '') + (btns ? '<div class="acts">' + btns + '</div>' : '') + panel + '</li>';
  }
  function reviewHtml(it) {
    var rv = it.review || {}, o = '', lastGroup = '';
    if (rv.line) o += '<div class="detail">' + hc(rv.line) + '</div>';
    (rv.parts || []).forEach(function (pt) {
      var rows = (pt.rows || []).filter(function (r) { return !revRowGone(it, r); }), inner = '';
      if (pt.group && pt.group !== lastGroup) { o += '<div class="set-sub">' + h(REV_GROUPS[pt.group] || pt.group) + '</div>'; lastGroup = pt.group; }
      (pt.lines || []).forEach(function (l) { inner += '<div class="kv">' + hc(l) + '</div>'; });
      if (rows.length) inner += '<ul class="rows">' + rows.map(function (r) { return revRow(it, r); }).join('') + '</ul>';
      else if ((pt.rows || []).length) inner += '<div class="kv">Everything here is gone through.</div>';
      o += more(it, 'rv-' + pt.key, hc(pt.title || pt.key) + (rows.length ? ' <span class="cnt">' + rows.length + '</span>' : ''), inner || '<div class="kv">Nothing here.</div>');
    });
    if (rv.cost) o += '<div class="wnote">' + hc(rv.cost) + '</div>';
    return o;
  }
  function revApply(rv, rc, rowId, rec) {
    delete S.open['rp:' + rv.key + ':' + rowId];
    acting = rv.key;
    if (save(rc, rec) === false) return;
    (S.revDone[rv.key] = S.revDone[rv.key] || {})[rowId] = rec.at;
    render();
  }
  /* What a card that came back waited for, on its header line. */
  function cameBack(it) {
    var c = it.came_back, n;
    if (!c || typeof c !== 'object') return '';
    n = +c.waited_days;
    return c.why === 'message' ? (c.who || 'They') + ' wrote again' + (n >= 0 ? ' after ' + plural(n, 'day') : '') : 'Waited ' + (n >= 0 ? plural(n, 'working day') : '') + (c.who ? ' for ' + c.who : '') + ', no reply';
  }
  var LATER = [['today', 'Later today'], ['tomorrow', 'Tomorrow'], ['next_week', 'Next week'], ['someday', 'Someday']];
  function dayPlus(n) { var d = new Date(); d.setDate(d.getDate() + n); return isoLocal(d).slice(0, 10); }
  function answered(a) {
    if (!a) return '<div class="answered-line"></div>';
    var when = a.at ? ' ' + fmtDT(D(a.at)) : '', st = a.status || '', note;
    if (a.action === 'applied') note = 'I have it.' + h(when);
    else if (st === 'working') note = '<b class="working">Working on it</b>';
    else if (st === 'done') note = '<b class="outcome' + (notSent(a) ? ' bad' : '') + '">' + hc(a.outcome || 'Done') + '</b>';
    else if (st === 'failed') note = '<b class="outcome bad">' + hc(a.outcome || 'I couldn\'t act on this yet.') + '</b>';
    else if (isSend(a)) note = S.listening === false ? 'This page can\'t reach your computer, so this email won\'t go out. Press Send again when it\'s back.' : 'Waiting for your computer to send it.';
    else if (S.listening === false) note = 'Saved' + h(when) + '. This page can\'t reach your computer, so this waits until it\'s back.';
    else note = 'Saved' + h(when) + '.';
    return '<div class="answered-line"><span class="res">' + h(a.result || 'Answered') + '</span>' +
      (saidOf(a) ? '<span class="said">"' + h(saidOf(a)) + '"</span>' : '') +
      '<span class="rec-note">' + note + '</span>' +
      (isSend(a) ? '' : '<button class="link" data-a="undo">Undo</button>') + '</div>';
  }
  function stateAttr(a) { return a && a.action !== 'applied' ? ' data-state="' + h(a.action) + '"' : ''; }     /* an answer the engine holds never hides the buttons and box */
  /* The assistant rewrote the card from the owner's answer: the card itself now says it all. */
  function rewrote(a) { return !!a && !isSend(a) && /I rewrote the card to match\./.test(String(a.outcome || '')); }
  /* The note over a card that came back to the owner; none over a card already rewritten from their answer. */
  function backNote(was) {
    if (!was || rewrote(was)) return '';
    return '<div class="back">' + hc(was.outcome || 'This came back to you.') + (isSend(was) ? ' ' + h(saidOf(was)) + '. Your words are kept; press Edit to try again.'
      : was.text && !pressOf(was) ? ' You had answered "' + h(was.text) + '".' : '') + '</div>';
  }
  /* A closed card: the header, the one thing wanted, why it is here, its buttons. Pressing the header opens the rest. */
  /* An update card: what is new in plain words, shown on the card itself. Update starts the walk-through in Talk to your assistant. */
  function updHtml(it) {
    var u = it.update, ch = (u && u.changes) || [];
    if (!u || !u.version) return '';
    return '<div class="upd"><b>' + (u.from ? 'Version ' + hc(u.from) + ' to ' : 'Version ') + hc(u.version) + ' brings:</b>' +
      (ch.length ? '<ul>' + ch.map(function (c) { return '<li>' + hc(c) + '</li>'; }).join('') + '</ul>' : '') +
      '<span class="chg-hint">Update walks through each change you made yourself, with you, in the box at the top. Nothing is touched until you say go.</span></div>';
  }
  /* A rule change card (rsi_loop.py): the one change, its reason, what it fixes and breaks and both scores, in the engine's own
     words, on the card itself. The only place outside Settings where a score is shown. */
  function rsiHtml(it) {
    var r = it.rsi, ls = (r && r.lines) || [];
    if (!r || !r.id || !ls.length) return '';
    return '<div class="upd"><ul>' + ls.map(function (l) { return '<li>' + hc(l) + '</li>'; }).join('') + '</ul></div>';
  }
  /* A closed card (ITEMS.md "Cards made simpler"): the title with Due, Important and New; the recommendation; why it is here in two
     sentences at most, with no label; every question with its own buttons; one row of buttons; the box. The title opens the rest. */
  function card(it, s) {
    var was = ansOf(it), back = returned(it, was), a = back || onShelf(was) ? null : was, title = titleHtml(it), mn = it.mini || {};
    var why = whyOf(it), isOpen = !!S.open['card:' + it.key];
    if (s === 'small' && mn.code) title = (mn.count != null && mn.count !== '' ? h(mn.count) + ' &times; ' : '') + '<span class="part">' + h(mn.code) + '</span>' + (mn.text ? ' <span class="q-sub">' + h(mn.text) + '</span>' : '') + '<span class="q-sub">' + h(mn.question || headerOf(it)) + '</span>';
    var st = setts(), flt = (st && st.filter) || {}, old = it.old_cards && s !== 'done' && s !== 'someday';
    if (s === 'fyi' && flt.nothing_needed === 'full' && S.open['card:' + it.key] == null) isOpen = true;      /* the owner asked for these in full */
    if (flt.show_why === 'off') why = '';
    var when = whenHtml(it), bn = back && was && isSend(was) ? backNote(was) : '';      /* only a failed send keeps a box above the title; the assistant's reply is in the card's Conversation */
    if (bn) bn = bn.replace('<div class="back">', '<div class="back">' + when);         /* the date stays top right on a card that came back */
    var head = '<div class="q opener" data-a="open" role="button" tabindex="0" aria-expanded="' + isOpen + '">' + (bn ? '' : when) + title + tagsHtml(it) + '</div>' +
      (it.rule && it.rule.reason ? '<div class="why rule-why">Because: ' + hc(it.rule.reason) + '</div>' : '') +
      (it.rec_front && s !== 'done' ? '<div class="rec-front">Recommended: ' + hc(it.rec_front) + '</div>' : '') +
      (why ? '<div class="why">' + hc(why) + '</div>' : '') + (s === 'done' && (closedOnly(it) || lastDid(it)) ? '<div class="why">' + hc(closedOnly(it) ? closedWhy(it) : lastDid(it)) + '</div>' : '') +
      (it.tip && s !== 'done' ? '<div class="why tip">' + hc(it.tip) + '</div>' : '');      /* a one-time tip, the first time this thing appears (onboard.py) */
    var rest = scanHtml(it.rule_scan) + '<div class="hide-on-answer stack">' + (old ? oldHtml(it) + boxHtml(it) : (it.review && s !== 'done' ? reviewHtml(it) : '') + (it.rsi && s !== 'done' ? rsiHtml(it) : '') + pickHtml(it, s) + answeredHtml(it, s) + questionsHtml(it, s) + buttons(it, s)) + '</div>' + answered(a) +
      (isOpen ? '<div class="card-in">' + inside(it, s) + '</div>' : '');
    return '<article class="card host' + (it.importance && !a ? ' urgent' : '') + '" data-key="' + h(it.key) + '"' + stateAttr(a) + '>' + bn + head + rest + '</article>';
  }
  function cards(list, s) { return '<div class="cards">' + list.map(function (it) { return card(it, s); }).join('') + '</div>'; }
  /* Done: what he answered (each card drawn from its own place), what the assistant closed with nothing done (named so), what is finished */
  function handledHtml(by) {
    var hf = '<div class="cards">' + by.answered.map(function (it) { return card(it, sect(it)); }).join('') + '</div>';
    if (!by.answered.length) hf = '';
    hf += fold('closed', 'Done by me, no action taken', by.closed, 'done', !by.answered.length);
    hf += cards(by.done, 'done');
    return hf;
  }
  function fold(name, label, list, s, first) {
    if (!list.length) return '';
    return '<details class="fold' + (first ? ' first' : '') + '" data-d="' + name + '"' + (S.open[name] ? ' open' : '') + '><summary>' + label + ' <span class="cnt">' + list.length + '</span></summary>' + cards(list, s) + '</details>';
  }

  /* ---------- writing an email: edit a draft, or write one from scratch, then Send ----------
     A Send press is saved like any answer, as ITEMS.md "Sending an email the owner wrote" asks:
     on the card's key, or on the key "compose" for a new email. Its text is the email as JSON,
     with `shown` exactly what the check screen showed. The engine's own rule decides; this page
     only makes sure what it asks for is what was on screen. */
  var COMPOSE = {key: 'compose', id: 'compose', title: 'An email you wrote'};
  var TEXT_MAX = 4000;                      /* the site keeps at most this many characters of one answer */
  var MAX_TO = 20;
  var ADDR = /^[^@\s<>,;"']+@[^@\s<>,;"']+\.[A-Za-z]{2,}$/;
  function itemOf(key) { return key === 'compose' ? COMPOSE : find(key); }
  /* Why the send buttons are not there, in the place he would look for them; empty when they are. */
  function sendOff() {
    var s = S.meta && S.meta.send;
    if (!S.meta || sendCfg()) return '';
    return s && s.on ? 'No connected account can send yet. To connect one, type /assistant:change accounts in Claude on your computer.'
      : 'Sending email from this page is switched off. To turn it on, type /assistant:change sending in Claude on your computer.';
  }
  function sendCfg() { var s = S.meta && S.meta.send; return s && s.on && (s.accounts || []).length ? s : null; }
  /* who a reply by email goes to on a card whose newest message is an email (ITEMS.md `reply`), or null */
  function replyOf(it) {
    var r = it && it !== COMPOSE && it.reply;
    if (!r || typeof r !== 'object' || r.can_email === false) return null;
    var to = (r.to || []).filter(function (x) { return ADDR.test(String(x)); });
    var sj = String(r.subject || '').trim();
    return to.length ? {to: to, cc: [], subject: sj && !/^re:/i.test(sj) ? 'Re: ' + sj : sj, body: '', attach: [], account: String(r.account || '')} : null;
  }
  function isSend(a) { return !!a && /^\s*\{"send_email"/.test(String(a.text || '')); }
  /* a yes on a draft that has not been sent */
  function yesNotSent(it) { return !!it.draft && it.state !== 'done' && (it.status === 'Approved' || (pressName(S.ans[it.key]) === 'approve' && S.ans[it.key].status !== 'failed')); }
  function sendOf(a) { try { var m = JSON.parse(a.text).send_email; return m && typeof m === 'object' ? m : {}; } catch (e) { return {}; } }
  function notSent(a) { return isSend(a) && /^Not sent/.test(String(a.outcome || '')); }
  function saidOf(a) {          /* an answer in words; a Send press as who it went to and its subject, never the raw record */
    if (!a) return '';
    if (pressOf(a)) return '';
    if (!isSend(a)) return a.text || '';
    var m = sendOf(a);
    return 'Email to ' + (m.to || []).concat(m.cc || []).join(', ') + (m.subject ? ': ' + m.subject : '');
  }
  function addrs(s) {
    return String(s || '').split(/[,;\n]+/).map(function (x) {
      var t = x.trim(), m = t.match(/<([^<>]+)>/);
      return (m ? m[1] : t).trim();
    }).filter(Boolean);
  }
  function filesOf(it) { return it && it !== COMPOSE ? (it.evidence_files || []).slice() : []; }
  /* The kinds of email, and what a draft made from a message carries (the contract's `draft`: type, source, files, base). */
  var W_TYPES = ['new', 'reply', 'reply_all', 'forward'];
  function wLow(x) { return String(x == null ? '' : x).toLowerCase(); }
  function wSource(it) { return it && it !== COMPOSE && it.draft && it.draft.source && typeof it.draft.source === 'object' ? it.draft.source : null; }
  function wFile(f) { return {name: String(f.name), ref: String(f.ref == null ? '' : f.ref), size: +f.size || 0}; }
  function wDraftFiles(it) { return ((it && it !== COMPOSE && it.draft && it.draft.files) || []).filter(function (f) { return f && f.name; }).map(wFile); }
  function wFilesOf(d, it) { return Array.isArray(d.files) ? d.files : wDraftFiles(it); }
  function wWho(so) { return String(so.from_name || so.from || ''); }
  function wTypeWords(it, type) {
    var so = wSource(it);
    if (!so || type === 'new') return 'New email';
    return ({reply: 'Reply to', reply_all: 'Reply to all of', forward: 'Forward of'}[type] || 'Email about') + ' ' + wWho(so) + ', ' + String(so.when || '') + ': ' + String(so.subject || '');
  }
  function wDraft(k, it) {
    var d = S.drafts['w:' + k], dr = it && it.draft;
    /* the engine rewrote the draft after this edit was made: the card's draft is the newer one, so the old edit goes */
    if (d && dr && dr.base && d.base && d.base !== dr.base) { delete S.drafts['w:' + k]; keepDrafts(); d = null; }
    if (d) return d;
    var src = dr || replyOf(it) || {}, cfg = sendCfg(), accts = cfg ? cfg.accounts : [], ref = String((it && it.source_ref) || '').toLowerCase(), so = wSource(it);
    var came = String(src.account || '').toLowerCase(), same = accts.filter(function (x) { return came && String(x).toLowerCase() === came; })[0];
    var fromSrc = so && so.account ? accts.filter(function (x) { return wLow(x) === wLow(so.account); })[0] : '';
    /* a reply goes out only from the account the message came to; a new email or a draft may take the only account */
    var acct = fromSrc || (replyOf(it) && !(it && it.draft) ? (same || '') : (accts.length === 1 ? accts[0] : (same
      || accts.filter(function (x) { return ref.indexOf(String(x).toLowerCase()) >= 0; })[0] || '')));
    var files = filesOf(it);
    return {account: acct, to: (src.to || []).join(', '), cc: (src.cc || []).join(', '), bcc: (src.bcc || []).join(', '), subject: src.subject || '', body: src.body || '',
            attach: (src.attach || []).filter(function (n) { return files.indexOf(n) >= 0; }), files: wDraftFiles(it),
            type: so && W_TYPES.indexOf(src.type) >= 0 ? src.type : 'new', base: dr && dr.base ? String(dr.base) : '', pressed: ''};
  }
  function wPayload(k, it) {
    var d = wDraft(k, it), files = filesOf(it), fl = wFilesOf(d, it), so = wSource(it), type = W_TYPES.indexOf(d.type) >= 0 && (so || d.type === 'new') ? d.type : 'new';
    var names = fl.map(function (f) { return f.name; });
    files.filter(function (n) { return (d.attach || []).indexOf(n) >= 0 && names.indexOf(n) < 0; }).forEach(function (n) { names.push(n); });
    var p = {account: d.account || '', to: addrs(d.to), cc: addrs(d.cc), bcc: addrs(d.bcc), subject: String(d.subject || '').trim(), body: String(d.body || ''),
             type: type, source: so && type !== 'new' && so.message != null ? so.message : null, files: fl.map(function (f) { return {name: f.name, ref: f.ref}; }), attach: names};
    p.shown = {account: p.account, to: p.to.slice(), cc: p.cc.slice(), bcc: p.bcc.slice(), type: p.type, attach: p.attach.slice()};
    return p;
  }
  /* Every address that is the owner's own: the accounts he sends from and the ones mail is read from. */
  function wOwn() {
    var cfg = sendCfg(), o = [];
    ((cfg && cfg.accounts) || []).concat(((S.mail && S.mail.accounts) || []).map(function (a) { return a && a.address; })).forEach(function (x) { x = wLow(x); if (x && o.indexOf(x) < 0) o.push(x); });
    return o;
  }
  function wNoOwn(list, drop) {
    var own = wOwn().concat((drop || []).map(wLow)), seen = {};
    return (list || []).map(String).filter(function (x) { var l = wLow(x); if (!l || own.indexOf(l) >= 0 || seen[l]) return false; seen[l] = 1; return true; });
  }
  function wAuto(type, so) {
    if (type === 'reply') return {to: [String(so.from || '')].filter(Boolean), cc: []};
    if (type === 'reply_all') { var to = wNoOwn([so.from].concat(so.to || [])); return {to: to, cc: wNoOwn(so.cc || [], to)}; }
    if (type === 'forward') return {to: [], cc: []};
    return null;
  }
  function wSame(a, b) { var x = a.map(wLow).sort().join('|'), y = b.map(wLow).sort().join('|'); return x === y; }
  function wBaseSubject(s) { return String(s || '').replace(/^\s*((re|fwd?)\s*:\s*)+/i, '').trim(); }
  /* Switching the kind of email recomputes who it goes to, the subject and the files from the message it is about; his words stay. */
  function wSetType(k, it, type) {
    var so = wSource(it);
    if (!so || W_TYPES.indexOf(type) < 0) return false;
    var d = wDraft(k, it), prev = W_TYPES.indexOf(d.type) >= 0 ? d.type : 'new';
    if (prev === type) return false;
    var pa = wAuto(prev, so), na = wAuto(type, so), cur = {to: addrs(d.to), cc: addrs(d.cc)};
    var typed = function (f) { return !(pa && wSame(pa[f], cur[f])); };
    if (na && type !== 'forward') { d.to = na.to.join(', '); d.cc = na.cc.join(', '); }
    else if (type === 'forward') { if (!typed('to')) d.to = ''; if (!typed('cc')) d.cc = ''; }
    var base = wBaseSubject(d.subject) || wBaseSubject(so.subject);
    d.subject = type === 'reply' || type === 'reply_all' ? 'Re: ' + base : type === 'forward' ? 'Fwd: ' + base : base;
    var srcRefs = (so.files || []).map(function (f) { return String(f.ref); });
    var mine = wFilesOf(d, it).filter(function (f) { return srcRefs.indexOf(f.ref) < 0; });
    d.files = type !== 'new' ? (so.files || []).filter(function (f) { return f && f.name; }).map(wFile).concat(mine) : mine;
    d.attach = (d.attach || []).filter(function (n) { return d.files.some(function (f) { return f.name === n; }) || filesOf(it).indexOf(n) >= 0; });
    d.type = type;
    S.drafts['w:' + k] = d;
    return true;
  }
  function wAddFiles(k, it, list) {
    var d = wDraft(k, it), cur = wFilesOf(d, it).slice();
    list.forEach(function (f) { if (f && f.name && !cur.some(function (x) { return x.ref === String(f.ref); })) cur.push(wFile(f)); });
    d.files = cur; S.drafts['w:' + k] = d;
  }
  function wRemoveFile(k, it, i) {
    var d = wDraft(k, it), cur = wFilesOf(d, it), gone = cur[i];
    if (!gone) return false;
    d.files = cur.filter(function (f, j) { return j !== i; });
    if (!d.files.some(function (f) { return f.name === gone.name; })) d.attach = (d.attach || []).filter(function (n) { return n !== gone.name; });
    S.drafts['w:' + k] = d;
    return true;
  }
  /* What the owner changed on this device in who it goes to, when the card's draft has not changed since (a newer draft already dropped the edit). */
  function wChanged(k, it) {
    var dr = it && it.draft, out = [];
    wDraft(k, it);
    var d = S.drafts['w:' + k];
    if (!d || !dr) return '';
    [['To', 'to'], ['Copy to', 'cc'], ['Blind copy', 'bcc']].forEach(function (f) {
      var was = (dr[f[1]] || []).map(String), now = addrs(d[f[1]]);
      if (!wSame(was, now)) out.push(f[0] + ' was ' + (was.join(', ') || 'empty') + ', now ' + (now.join(', ') || 'empty'));
    });
    return out.length ? 'Changed on this device: ' + out.join('; ') + '.' : '';
  }
  function wChangedHtml(k, it) {
    var w = wChanged(k, it);
    return w ? '<div class="chg-warn"><b>' + h(w) + '</b><span>Until you change it back, this is who it goes to.</span></div><div class="acts"><button class="btn" type="button" data-a="w-userecips">Use the draft\'s recipients</button></div>' : '';
  }
  function wOrigHtml(it, k) {
    var so = wSource(it), key = 'wsrc:' + k;
    if (!so) return '';
    return '<details class="more" data-d="' + h(key) + '"' + (S.open[key] ? ' open' : '') + '><summary>Original message from ' + h(wWho(so)) + ', ' + hc(so.when || '') + ': ' + h(so.subject || '') + '</summary><div class="inside"><pre class="src-text">' + h(so.text || '') + '</pre></div></details>';
  }
  function mailSize(n) { n = +n || 0; return n >= 1048576 ? (n / 1048576).toFixed(1) + ' MB' : n >= 1024 ? Math.round(n / 1024) + ' KB' : n ? n + ' bytes' : ''; }
  function wText(p) { return JSON.stringify({send_email: p}); }
  /* Send sends exactly the words on screen: the body last shown (on the card, in the writing screen, as typed) is kept here,
     and a press whose body is not that one (the draft changed under it) sends nothing. */
  function wSeen(k, body) { S.seen = S.seen || {}; S.seen[k] = String(body == null ? '' : body); }
  function wPressText(k, it) {    /* the Send press's words, or null when the email changed since it was shown */
    var p = wPayload(k, it), seen = S.seen && Object.prototype.hasOwnProperty.call(S.seen, k) ? S.seen[k] : null;
    if (seen !== null && seen !== p.body) {
      S.err[k] = 'This email changed just now (I wrote it again). Nothing was sent. Look it over and press Send again.';
      return null;
    }
    return wText(p);
  }
  function wRoom(k, it) {
    var left = TEXT_MAX - wText(wPayload(k, it)).length;
    return left >= 0 ? {text: left + ' characters left in this email (one email here holds about 3,500).', over: false}
      : {text: 'This email is ' + (-left) + ' characters too long to send from this page. Shorten it.', over: true};
  }
  function wProblem(k, it) {
    var cfg = sendCfg();
    if (!cfg) return 'Sending from this page is switched off.';
    var p = wPayload(k, it), bad = p.to.concat(p.cc, p.bcc).filter(function (x) { return !ADDR.test(x); });
    if (cfg.accounts.indexOf(p.account) < 0) return 'Choose the account it goes out from.';
    if (!p.to.length) return 'Put at least one address in To.';
    if (bad.length) return 'Not an email address: ' + bad.slice(0, 3).join(', ');
    if (p.to.length + p.cc.length + p.bcc.length > MAX_TO) return 'More than ' + MAX_TO + ' recipients.';
    if (!p.subject) return 'Write a subject.';
    if (!p.body.trim()) return 'Write the message.';
    if (S.wup[k] && S.wup[k].busy) return 'A file is still being added. Wait a moment.';
    if (wRoom(k, it).over) return wRoom(k, it).text;
    return '';
  }
  function wSuggest(k, field) {
    var d = S.drafts['w:' + k] || {}, typed = String(d[field] || ''), cut = Math.max(typed.lastIndexOf(','), typed.lastIndexOf(';'));
    var q = typed.slice(cut + 1).trim().toLowerCase(), out = [];
    var have = addrs(d.to).concat(addrs(d.cc)).map(function (x) { return x.toLowerCase(); });
    if (q.length < 2) return out;
    ((S.meta && S.meta.people) || []).some(function (p) {
      var hy = [p.name, p.company].concat(p.email || []).join(' ').toLowerCase();
      if (hy.indexOf(q) >= 0) (p.email || []).forEach(function (e) { if (out.length < 6 && have.indexOf(String(e).toLowerCase()) < 0) out.push({name: p.name, company: p.company, email: e}); });
      return out.length >= 6;
    });
    return out;
  }
  function wSuggestHtml(k, field) {
    return wSuggest(k, field).map(function (s) {
      return '<button class="chip" type="button" data-a="w-pick" data-f="' + field + '" data-e="' + h(s.email) + '">' + h(s.name) + (s.company ? ', ' + h(s.company) : '') + ' <b>' + h(s.email) + '</b></button>';
    }).join('');
  }
  function wPick(d, field, email) {
    var typed = String(d[field] || ''), cut = Math.max(typed.lastIndexOf(','), typed.lastIndexOf(';'));
    d[field] = (cut >= 0 ? typed.slice(0, cut + 1) + ' ' : '') + email + ', ';
  }
  /* The attachments: what goes with the email, a file from this computer, the original's files, a file from another email. */
  function wFilesHtml(k, it) {
    var d = wDraft(k, it), fl = wFilesOf(d, it), so = wSource(it), kk = h(k), up = S.wup[k] || {}, wo = S.wo[k] || {}, files = filesOf(it), o = '<label>Attachments</label>';
    o += fl.length ? fl.map(function (f, i) {
      return '<div class="kv wfile">' + h(f.name) + (f.size ? ' (' + h(mailSize(f.size)) + ')' : '') + ' <button class="link" type="button" data-a="w-remove" data-i="' + i + '" aria-label="Remove ' + h(f.name) + '">Remove</button></div>';
    }).join('') : '<div class="wnote">Nothing is attached.</div>';
    if (files.length) o += '<label>Attach from the card</label>' + files.map(function (n, i) {
      return '<label class="check" for="wa' + i + '-' + kk + '"><input type="checkbox" id="wa' + i + '-' + kk + '" data-wa="' + h(n) + '"' + ((d.attach || []).indexOf(n) >= 0 ? ' checked' : '') + '> ' + h(n) + '</label>';
    }).join('');
    var have = fl.map(function (f) { return f.ref; }), left = so ? (so.files || []).filter(function (f) { return f && f.name && have.indexOf(String(f.ref)) < 0; }) : [];
    o += '<div class="acts">' + (left.length ? '<button class="btn" type="button" data-a="w-addorig">Add the original\'s attachments</button>' : '') + '</div>';
    o += '<label for="wup-' + kk + '">Add a file from your computer</label><input type="file" id="wup-' + kk + '" data-wfile="1"' + (up.busy ? ' disabled' : '') + '>' +
      (up.busy ? '<div class="wnote" role="status">Adding the file.</div>' : '') + (up.err ? '<div class="err" role="alert">' + h(up.err) + '</div>' : '') +
      '<div class="wnote">One file can be up to 15 MB.</div>';
    var op = 'wo:' + k;
    o += '<details class="more" data-d="' + h(op) + '"' + (S.open[op] ? ' open' : '') + '><summary>Add from another email</summary><div class="inside">' +
      '<div class="mail-bar"><input type="text" id="wos-' + kk + '" data-wo="q" value="' + h(wo.q || '') + '" placeholder="Words from the email, who sent it or its subject" aria-label="Find the other email" autocomplete="off"><button class="btn" type="button" data-a="w-find">Find</button></div>';
    if (wo.busy) o += '<div class="wnote" role="status">Looking.</div>';
    if (wo.err) o += '<div class="err" role="alert">' + h(wo.err) + '</div>';
    if (wo.rows && !wo.pick) o += wo.rows.length ? '<div class="acts tall">' + wo.rows.map(function (r) {
      return '<button class="chip" type="button" data-a="w-pickmsg" data-id="' + h(r.id) + '">' + h(r.from_name || r.from || '') + ': ' + h(r.subject || '') + (r.files ? ' (' + r.files + (r.files === 1 ? ' file' : ' files') + ')' : '') + '</button>';
    }).join('') + '</div>' : '<div class="wnote">No email matched.</div>';
    if (wo.pick) o += '<div class="kv"><b>' + h(wo.pick.subject || 'That email') + '</b></div>' + (wo.pick.files.length ? wo.pick.files.map(function (f, i) {
      return '<label class="check"><input type="checkbox" data-wotick="' + i + '"' + (wo.ticks && wo.ticks[i] ? ' checked' : '') + '> ' + h(f.name) + (f.size ? ' (' + h(mailSize(f.size)) + ')' : '') + '</label>';
    }).join('') + '<div class="acts"><button class="btn primary" type="button" data-a="w-addother">Add the ticked files</button><button class="btn quiet" type="button" data-a="w-pickno">Choose another email</button></div>' : '<div class="wnote">That email has no files.</div><div class="acts"><button class="btn quiet" type="button" data-a="w-pickno">Choose another email</button></div>');
    return o + '</div></details>';
  }
  function writerHtml(it) {
    var k = it.key, kk = h(k), d = wDraft(k, it), cfg = sendCfg(), files = filesOf(it), src = it.draft || {}, so = wSource(it);
    wSeen(k, d.body);
    if (!cfg) return '<div class="panel-box"><div class="wnote">Sending from this page is switched off.</div><div class="acts"><button class="btn quiet" data-a="cancel">Close</button></div></div>';
    if (S.panel[k] === 'review') {
      var p = wPayload(k, it);
      return '<div class="panel-box review"><label>Check it, then send</label>' + wChangedHtml(k, it) +
        '<div class="kv"><b>Type:</b> ' + h(wTypeWords(it, p.type)) + '</div>' +
        '<div class="kv"><b>From:</b> ' + h(p.account) + '</div>' +
        '<div class="kv"><b>To:</b> ' + h(p.to.join(', ')) + '</div>' +
        (p.cc.length ? '<div class="kv"><b>Copy to:</b> ' + h(p.cc.join(', ')) + '</div>' : '') +
        (p.bcc.length ? '<div class="kv"><b>Blind copy:</b> ' + h(p.bcc.join(', ')) + '</div>' : '') +
        '<div class="kv"><b>Attached:</b> ' + (p.attach.length ? h(p.attach.join(', ')) : 'nothing') + '</div>' +
        '<div class="kv"><b>Subject:</b> ' + h(p.subject) + '</div>' +
        '<pre class="src-text">' + h(p.body) + '</pre>' + wOrigHtml(it, k) +
        '<div class="wnote">It goes out as soon as you press Send now, from the account above, to exactly these people. Anyone in Blind copy gets it without the others seeing them.</div>' +
        '<div class="acts"><button class="btn primary" data-a="w-send">Send now</button><button class="btn" data-a="w-edit">Back to editing</button><button class="btn quiet" data-a="cancel">Close</button></div></div>';
    }
    var opts = '<option value=""' + (d.account ? '' : ' selected') + '>Choose the account</option>' + cfg.accounts.map(function (x) {
      return '<option value="' + h(x) + '"' + (x === d.account ? ' selected' : '') + '>' + h(x) + '</option>';
    }).join('');
    var missing = (src.attach || []).filter(function (n) { return files.indexOf(n) < 0 && !wFilesOf(d, it).some(function (f) { return f.name === n; }); });
    var att = wFilesHtml(k, it);
    if (missing.length) att += '<div class="wnote">The draft also named ' + h(missing.join(', ')) + ', which cannot be attached from here.</div>';
    if (it !== COMPOSE && (it.documents || []).length) att += '<div class="wnote">Papers that came with the message cannot be attached from here.</div>';
    var room = wRoom(k, it), tp = W_TYPES.indexOf(d.type) >= 0 ? d.type : 'new';
    var kinds = so ? '<label for="wy-' + kk + '">Type</label><select id="wy-' + kk + '" data-w="type">' + [['new', 'New'], ['reply', 'Reply'], ['reply_all', 'Reply all'], ['forward', 'Forward']].map(function (x) {
      return '<option value="' + x[0] + '"' + (x[0] === tp ? ' selected' : '') + '>' + x[1] + '</option>';
    }).join('') + '</select>' : '';
    return '<div class="panel-box writer">' + kinds +
      '<label for="wf-' + kk + '">From</label><select id="wf-' + kk + '" data-w="account">' + opts + '</select>' +
      '<label for="wt-' + kk + '">To</label><input type="text" inputmode="email" autocomplete="off" id="wt-' + kk + '" data-w="to" value="' + h(d.to) + '" placeholder="Type a name or an address; put commas between several">' +
      '<div class="sugg" id="wst-' + kk + '">' + wSuggestHtml(k, 'to') + '</div>' +
      '<label for="wc-' + kk + '">Copy to</label><input type="text" inputmode="email" autocomplete="off" id="wc-' + kk + '" data-w="cc" value="' + h(d.cc) + '">' +
      '<div class="sugg" id="wsc-' + kk + '">' + wSuggestHtml(k, 'cc') + '</div>' +
      '<label for="wbc-' + kk + '">Blind copy</label><input type="text" inputmode="email" autocomplete="off" id="wbc-' + kk + '" data-w="bcc" value="' + h(d.bcc || '') + '">' +
      '<label for="wj-' + kk + '">Subject</label><input type="text" autocomplete="off" name="box-2" id="wj-' + kk + '" data-w="subject" value="' + h(d.subject) + '">' +
      '<label for="wb-' + kk + '">Message</label><textarea autocomplete="off" name="box-3" id="wb-' + kk + '" data-w="body">' + h(d.body) + '</textarea>' +
      att + wOrigHtml(it, k) +
      '<div class="wnote' + (room.over ? ' over' : '') + '" id="wn-' + kk + '">' + h(room.text) + '</div>' +
      '<div class="acts"><button class="btn primary" data-a="w-review">Check and send</button><button class="btn quiet" data-a="cancel">Close</button>' +
      '<button class="btn quiet" data-a="w-discard">Throw it away</button></div></div>';
  }
  /* Typing in the writer: kept as it is typed; suggestions and the room left are updated in place, without redrawing the card.
     Choosing another kind of email redraws it, since who it goes to, the subject and the files change. */
  function wInput(t) {
    var hk = t.closest('[data-key]'), k = hk && hk.getAttribute('data-key'), it = k && itemOf(k);
    if (!it) return;
    var d = wDraft(k, it), f = t.getAttribute('data-w');
    if (f === 'type') { if (wSetType(k, it, t.value)) { acting = k; render(); } return; }
    if (f) d[f] = t.value;
    if (f === 'body') wSeen(k, t.value);
    if (t.hasAttribute('data-wa')) {
      var n = t.getAttribute('data-wa');
      d.attach = (d.attach || []).filter(function (x) { return x !== n; });
      if (t.checked) d.attach.push(n);
    }
    S.drafts['w:' + k] = d;
    if (f === 'to' || f === 'cc') { var box = $((f === 'to' ? 'wst-' : 'wsc-') + k); if (box) box.innerHTML = wSuggestHtml(k, f); }
    var note = $('wn-' + k);
    if (note) { var r = wRoom(k, it); note.textContent = r.text; note.className = 'wnote' + (r.over ? ' over' : ''); }
  }
  /* Adding a file from this computer: sent to the page's own server, which keeps it until the email goes. */
  var MAIL_CSRF = '';
  function mailCsrf() {
    if (S.db && S.db.csrf) return Promise.resolve(typeof S.db.csrf === 'function' ? S.db.csrf() : S.db.csrf);
    if (MAIL_CSRF) return Promise.resolve(MAIL_CSRF);
    return fetch('api/data', {credentials: 'same-origin', cache: 'no-store'}).then(function (r) { return r.json(); }).then(function (j) { MAIL_CSRF = (j && j.csrf) || ''; return MAIL_CSRF; });
  }
  function wUpload(k, it, file) {
    var up = S.wup[k] = {busy: true, err: ''};
    if (file.size > 15 * 1024 * 1024) { S.wup[k] = {busy: false, err: file.name + ' is over 15 MB, the most one file can be.'}; render(); return Promise.resolve(false); }
    render();
    return mailCsrf().then(function (tok) {
      return fetch('api/mail/upload', {method: 'POST', credentials: 'same-origin', headers: {'X-Brief-Csrf': tok, 'X-File-Name': encodeURIComponent(file.name)}, body: file});
    }).then(function (r) { return r.json(); }).then(function (j) {
      if (j && j.ok && j.file) { wAddFiles(k, it, [j.file]); keepDrafts(); S.wup[k] = {busy: false, err: ''}; }
      else S.wup[k] = {busy: false, err: (j && j.error) || 'That file could not be added.'};
      acting = k; render(); return true;
    }, function () { S.wup[k] = {busy: false, err: 'That file could not be sent. Check the connection and try again.'}; acting = k; render(); return false; });
  }
  /* Adding from another email: find it by words, pick it, tick its files. */
  function woFind(k) {
    var wo = S.wo[k] = S.wo[k] || {}, q = String(wo.q || '').trim();
    if (!q) { wo.err = 'Type some words from the email first.'; render(); return Promise.resolve(false); }
    wo.busy = true; wo.err = ''; wo.pick = null; render();
    return mailJson('api/mail?view=all&q=' + mailEnc(q) + '&limit=10').then(function (j) {
      wo.busy = false;
      if (j.hosted) wo.err = 'Email works on the page served from your computer.';
      else if (j.busy) wo.err = 'Mail is being updated. Press Find again in a moment.';
      else if (j.ok === false) wo.err = j.error || 'The search did not work.';
      else wo.rows = j.rows || [];
      acting = k; render(); return true;
    }, function () { wo.busy = false; wo.err = 'The search did not work. Check the connection and try again.'; acting = k; render(); return false; });
  }
  function woPick(k, id) {
    var wo = S.wo[k] = S.wo[k] || {};
    wo.busy = true; wo.err = ''; render();
    return mailJson('api/mail/thread?id=' + mailEnc(id)).then(function (j) {
      wo.busy = false;
      var msg = ((j && j.messages) || []).filter(function (m) { return String(m.id) === String(id); })[0];
      if (!msg) wo.err = (j && j.error) || 'That email could not be opened.';
      else { wo.pick = {id: id, subject: msg.subject || '', files: (msg.files || []).map(function (f) { return {name: f.name, ref: f.ref, size: f.size}; })}; wo.ticks = {}; }
      acting = k; render(); return true;
    }, function () { wo.busy = false; wo.err = 'That email could not be opened. Check the connection and try again.'; acting = k; render(); return false; });
  }
  function woInput(t) {
    var hk = t.closest('[data-key]'), k = hk && hk.getAttribute('data-key');
    if (!k) return;
    var wo = S.wo[k] = S.wo[k] || {};
    if (t.hasAttribute('data-wo')) wo.q = t.value;
    if (t.hasAttribute('data-wotick')) { wo.ticks = wo.ticks || {}; wo.ticks[t.getAttribute('data-wotick')] = !!t.checked; }
  }
  /* the writer's own buttons; false when the press is not one of these */
  function wClick(a, b, key, it) {
    var d;
    if (a === 'w-remove') { if (wRemoveFile(key, it, +b.getAttribute('data-i'))) { keepDrafts(); render(); } return true; }
    if (a === 'w-addorig') { var so = wSource(it); if (so) { wAddFiles(key, it, so.files || []); keepDrafts(); render(); } return true; }
    if (a === 'w-userecips') {
      var dr = it.draft || {}; d = wDraft(key, it);
      d.to = (dr.to || []).join(', '); d.cc = (dr.cc || []).join(', '); d.bcc = (dr.bcc || []).join(', ');
      S.drafts['w:' + key] = d; keepDrafts(); render(); return true;
    }
    if (a === 'w-find') { var q = $('wos-' + key); if (q) (S.wo[key] = S.wo[key] || {}).q = q.value; woFind(key); return true; }
    if (a === 'w-pickmsg') { woPick(key, b.getAttribute('data-id')); return true; }
    if (a === 'w-pickno') { var wo = S.wo[key] || {}; wo.pick = null; render(); return true; }
    if (a === 'w-addother') {
      var wp = S.wo[key] || {}, ch = [];
      ((wp.pick && wp.pick.files) || []).forEach(function (f, i) { if (wp.ticks && wp.ticks[i]) ch.push(f); });
      if (!ch.length) { wp.err = 'Tick a file first.'; render(); return true; }
      wAddFiles(key, it, ch); keepDrafts(); S.wo[key] = {q: wp.q || ''}; render(); return true;
    }
    return false;
  }
  /* An email that went out needs its words no longer; one that did not keeps them for another try. */
  function settleSends() {
    Object.keys(S.drafts).forEach(function (dk) {
      if (dk.slice(0, 2) !== 'w:') return;
      var d = S.drafts[dk], a = S.ans[dk.slice(2)];
      if (d && d.pressed && a && a.at === d.pressed && a.status === 'done' && /^Sent from/.test(String(a.outcome || ''))) { delete S.drafts[dk]; keepDrafts(); }
    });
  }
  function sendNote(a) {
    if (a.status === 'working') return '<b class="working">Sending</b>';
    if (a.status === 'done' || a.status === 'failed') return '<b class="outcome' + (a.status === 'failed' || notSent(a) ? ' bad' : '') + '">' + h(a.outcome || 'Done') + '</b>';
    return S.listening === false ? 'This page can\'t reach your computer, so it won\'t go out. Press Send again when it\'s back.' : 'Waiting for your computer to send it.';
  }
  function renderWrite() {
    var el = $('writebar'), k = 'compose', a = S.ans[k], o = '';
    if (!sendCfg()) { setHtml(el, sendOff() ? '<div class="kv">' + h(sendOff()) + '</div>' : ''); return; }
    if (S.panel[k] === 'write' || S.panel[k] === 'review') o += writerHtml(COMPOSE);
    if (isSend(a)) o += '<div class="kv rec-note"><b>' + h(saidOf(a)) + ':</b> ' + sendNote(a) + '</div>';
    if (S.err[k]) o += '<div class="err" role="alert">' + h(S.err[k]) + '</div>';
    setHtml(el, o ? '<div class="host" data-key="compose">' + o + '</div>' : '');
  }
  /* the Settings button sits on the title line, left of the date and time (the time is kept current each minute) */
  var TITLE_ID = {about: 'ab-h', held: 'hd-h', decide: 'dec-h', small: 'sm-h', tracked: 'tr-h', fyi: 'fy-h', someday: 'sd-h', today: 'td-h', handled: 'hf-h', saidso: 'ss-h', changes: 'ch-h', mail: 'ml-h', texts: 'tx-h', calendar: 'cl-h', chat: 'tk-h', feed: 'fd-h'};
  function applyTitles() { Object.keys(TITLE_ID).forEach(function (nm) { var e = $(TITLE_ID[nm]); if (e) e.textContent = secName(nm); }); }
  function renderTop() {
    var b = $('set-btn'), w = $('who'), m = S.meta, d = new Date();
    if (b) { b.textContent = S.panel.settings ? 'Close settings' : 'Settings'; b.setAttribute('aria-expanded', String(!!S.panel.settings)); }
    if (w) w.textContent = (m && m.page_subtitle ? m.page_subtitle + ' ' + String.fromCharCode(183) + ' ' : '') + fmtD(d) + '/' + String(d.getFullYear()).slice(2) + ' ' + fmtT(d);
  }


  /* ---------- Ready to send: emails Talk to your assistant wrote, at the top of the page ----------
     Each is a card with a `ready` field (engine ready to send.md). It is drawn here, whole, and never in the lists below; Send now
     is the same Send press the writing screen makes, Discard is the press "discard", and Send all is one answer for the batch. */
  function rdSent(a) { return !!a && isSend(a) && a.status === 'done' && /^Sent from/.test(String(a.outcome || '')); }
  function rdIs(it) { return !!(it && it.ready && typeof it.ready === 'object'); }
  function rdOwn(it) { return rdIs(it) && !!it.ready.own; }
  function rdBatch(it) { return rdIs(it) && !rdOwn(it) ? String(it.ready.batch || it.key) : 'left'; }
  /* the kept draft the engine holds for a card (one per card), if it is still open */
  function rdOwnFor(it) { return S.items.filter(function (x) { return rdOwn(x) && x.ready.about === it.id && x.state !== 'done'; })[0] || null; }
  function rdAllAns(g) {
    var pre = 'ready-all:' + g + ':', last = null;
    Object.keys(S.ans).forEach(function (k) { if (k.indexOf(pre) === 0 && (!last || k > last)) last = k; });
    return last ? S.ans[last] : null;
  }
  function rdAllBusy(g) { var a = rdAllAns(g); return !!a && a.status !== 'done' && a.status !== 'failed'; }
  /* the cards to show: not done, or just sent from here and not yet put away */
  function rdLive() {
    return S.items.filter(function (it) {
      var a = S.ans[it.key];
      if (!rdIs(it) || S.rdGone[it.key]) return false;
      if (a && pressName(a) === 'discard' && a.status !== 'failed') return false;
      return it.state !== 'done' && !rdSent(a);      /* sent: no longer ready to send, so it leaves at once */
    });
  }
  /* A reply he leaves is the engine's draft (answer "ready-keep"; it comes back as his own ready card), not kept on this device:
     once that card is here the words typed on this device are dropped. Only while the engine has not yet made it (or refused it)
     his words are still shown here, so nothing he typed is ever out of sight. */
  function rdLeft() {
    S.items.forEach(function (it) { if (!rdIs(it) && S.drafts['w:' + it.key] && rdOwnFor(it) && S.panel[it.key] !== 'write' && S.panel[it.key] !== 'review') { delete S.drafts['w:' + it.key]; delete S.kept[it.key]; keepDrafts(); } });
    return S.items.filter(function (it) {
      var d = S.drafts['w:' + it.key];
      return !rdIs(it) && it.state !== 'done' && d && S.kept[it.key] && String(d.body || '').trim() && !d.pressed && !rdOwnFor(it) && S.panel[it.key] !== 'write' && S.panel[it.key] !== 'review' && sendCfg() && !S.rdGone[it.key];
    });
  }
  /* closing the writing screen with words in it on a card: one answer, "ready-keep", so the engine keeps it in Ready to send */
  function rdKeep(it) {
    var k = it.key, d = S.drafts['w:' + k], open = S.panel[k] === 'write' || S.panel[k] === 'review';
    if (!open || !d || rdIs(it) || it === COMPOSE || !String(d.body || '').trim() || !sendCfg()) return;
    var pp = wPayload(k, it), sig = JSON.stringify([pp.account, pp.to, pp.cc, pp.subject, pp.body]);
    if (S.kept[k] === sig) return;                                          /* the same words are already kept */
    S.kept[k] = sig;
    chgSend('ready-keep:' + it.id + ':' + Date.now(), JSON.stringify({keep_draft: {account: pp.account, to: pp.to, cc: pp.cc, subject: pp.subject, body: pp.body}}), 'Keep reply', 'Kept in Drafts, in Email');
  }
  function rdCardHtml(it) {
    var k = it.key, kk = h(k), a = S.ans[k], sent = rdSent(a), grpBusy = rdAllBusy(rdBatch(it)), busy = (isSend(a) && !sent && a.status !== 'failed') || (grpBusy && !sent), off = sendOff();
    var p = wPayload(k, it), open = S.panel[k] === 'write' || S.panel[k] === 'review', ry = rdIs(it) ? it.ready : {}, about = ry.about && find(ry.about), why = rdIs(it) && !rdOwn(it) ? (ry.why || it.why) : '';
    var o = '<article class="draft host" data-key="' + kk + '">';
    if (!open) wSeen(k, p.body);
    if (open) o += writerHtml(it);
    else {
      o += wChangedHtml(k, it) + '<div class="kv"><b>Type:</b> ' + h(wTypeWords(it, p.type)) + '</div><div class="kv"><b>From:</b> ' + h(p.account || 'no account chosen') + '</div><div class="kv"><b>To:</b> ' + h(p.to.join(', ')) + '</div>' +
        (p.cc.length ? '<div class="kv"><b>Copy to:</b> ' + h(p.cc.join(', ')) + '</div>' : '') +
        (p.bcc.length ? '<div class="kv"><b>Blind copy:</b> ' + h(p.bcc.join(', ')) + '</div>' : '') +
        (p.attach.length ? '<div class="kv"><b>Attached:</b> ' + h(p.attach.join(', ')) + '</div>' : '') +
        '<div class="kv"><b>Subject:</b> ' + h(p.subject) + '</div><pre class="src-text">' + h(p.body) + '</pre>' + wOrigHtml(it, k) +
        (why ? '<div class="why">Why: ' + hc(why) + '</div>' : '') + (about && !rdOwn(it) ? '<div class="why">Answers: ' + hc(headerOf(about)) + '</div>' : '') + (rdIs(it) && !rdOwn(it) ? '' : '<div class="why">Your reply to: ' + hc(headerOf(rdOwn(it) ? (find(ry.about) || it) : it)) + '. It is not sent.</div>');
      if (busy) o += '<div class="kv rec-note">' + (isSend(a) ? sendNote(a) : '<b class="working">Sending</b>') + '</div>';
      else if (S.rdAsk[k]) o += '<div class="chg-warn"><b>Discard this email?</b><span>It is not sent and is taken off this page.</span></div><div class="acts"><button class="btn primary" type="button" data-a="rd-discard-go">Yes, discard it</button><button class="btn" type="button" data-a="rd-discard-no">Keep it</button></div>';
      else {
        if ((isSend(a) && a.status === 'failed') || notSent(a)) o += '<div class="kv rec-note"><b class="outcome bad">' + h(a.outcome || 'Not sent') + '</b></div>';
        if (off) o += '<div class="kv">' + h(off) + '</div>';
        o += '<div class="acts">' + (off ? '' : '<button class="btn primary" type="button" data-a="rd-send">Send now</button><button class="btn" type="button" data-a="write">Edit</button>') + '<button class="btn quiet" type="button" data-a="rd-discard-ask">Discard</button></div>';
      }
    }
    if (S.err[k]) o += '<div class="err" role="alert">' + h(S.err[k]) + '</div>';
    return o + '</article>';
  }
  function rdSendable(it) { var a = S.ans[it.key]; return it.state !== 'done' && !rdSent(a) && !(isSend(a) && a.status !== 'failed' && !notSent(a)); }
  /* ---------- Cards: one feed of the card kinds, each drawn as before, with a filter bar ----------
     Each kind keeps its own drawing, buttons and fold (the sections it once was); the feed only shows the kinds the filter names,
     in the order Settings (Appearance, Card order) gives, Hidden today always last as the card that opens the held list. */
  var FEED = {f: 'needs'};
  var FEED_F = [['all', 'All', null], ['needs', 'Needs you', ['decide', 'small']], ['tracked', 'Waiting on others', ['tracked']], ['someday', 'Someday', ['someday']],
                ['fyi', 'FYI', ['fyi']], ['done', 'Done', ['handled', 'saidso']], ['held', 'Hidden', ['held']]];
  var FEED_GROUPS = [['needs', ['decide', 'small']], ['waiting', ['tracked', 'someday']], ['fyi', ['fyi']], ['done', ['handled', 'saidso']]];
  function feedOrder() {
    var st = setts(), o = st && st.page && Array.isArray(st.page.feed_order) ? st.page.feed_order : [], gs = [], out = [];
    o.concat(FEED_GROUPS.map(function (g) { return g[0]; })).forEach(function (k) {
      var g = FEED_GROUPS.filter(function (x) { return x[0] === k || x[1].indexOf(k) >= 0; })[0];
      if (g && gs.indexOf(g) < 0) gs.push(g);
    });
    gs.forEach(function (g) { out = out.concat(g[1]); });
    return out.concat(['held']);
  }
  function feedCount(k) {
    if (k === 'held') { var m = /\d+/.exec(($('n-held') || {}).textContent || ''); return m ? +m[0] : 0; }
    var box = $(k); return box ? box.querySelectorAll('article').length : 0;
  }
  function renderFeed() {
    var box = $('feed'), bar = $('feed-bar');
    if (!box || !bar) return;
    var order = feedOrder(), now = [].map.call(box.children, function (el) { return el.id.slice(4); });
    if (now.join() !== order.join()) order.forEach(function (k) { var el = $('sec-' + k); if (el) box.appendChild(el); });
    var f = FEED_F.filter(function (x) { return x[0] === FEED.f; })[0] || FEED_F[1], want = f[2] || FEED_KINDS;
    FEED_KINDS.forEach(function (k) { var el = $('sec-' + k); if (el && want.indexOf(k) < 0) el.hidden = true; else if (el && k === 'held') el.hidden = false; });      /* hidden is always the last card when shown */
    [].forEach.call(box.querySelectorAll('details.grp, details.fold'), function (d) { if (!d.open) d.open = true; });
    box.className = 'feed f-' + f[0] + (kindsGrouped() ? '' : ' mix');
    mixFeed(box);
    var fs = $('feed-sort'), fp = $('feed-pop');
    if (fs) setHtml(fs, sortBarHtml());
    if (fp) setHtml(fp, S.panel.settings ? '' : infoPop());
    var n = {}; FEED_KINDS.forEach(function (k) { n[k] = feedCount(k); });
    var shown = (f[2] || FEED_KINDS).reduce(function (t, k) { return t + (k === 'held' ? 0 : n[k]); }, 0), fn = $('feed-none');
    if (fn) { fn.hidden = shown > 0 || f[0] === 'held'; fn.textContent = 'Nothing here right now.'; }
    setHtml(bar, FEED_F.map(function (x) {
      var c = (x[2] || FEED_KINDS).reduce(function (t, k) { return t + n[k]; }, 0);
      return '<button type="button" data-s="feed-f" data-f="' + x[0] + '" aria-pressed="' + (x[0] === f[0]) + '">' + h(x[1]) + '<span class="c">' + c + '</span></button>';
    }).join(''));
    var need = n.decide + n.small, hn = $('n-feed'); if (hn) hn.textContent = need ? need + ' need you' : '';
  }
  /* ---------- Drafts: Ready to send, inside Email; its header says how many wait and opens them ---------- */
  var RDO = {open: false, was: 0};
  function renderDrafts(open) {
    var bar = $('mail-drafts'), el = $('sec-ready');
    if (!bar || !el || POP != null) return;
    if (open > RDO.was) RDO.open = true;              /* a new draft opens them, so what Talk to your assistant wrote is in view */
    RDO.was = open;
    setHtml(bar, open || RDO.open ? '<b>' + (open ? plural(open, 'email') + ' ready to send' : 'No drafts waiting') + '</b><button class="btn" type="button" data-s="rd-open" aria-expanded="' + RDO.open + '">' + (RDO.open ? 'Hide drafts' : 'Drafts') + '</button>' : '');
    if (!RDO.open) el.hidden = true;
  }
  function renderReady() {
    var el = $('sec-ready'), list = rdLive().concat(rdLeft()), o = '', groups = [], by = {};
    if (!el) return;
    if (POP != null) {              /* a popped-out email: only the drafts started from it, nothing else of Ready to send */
      var mo = (S.mail && S.mail.out) || {}, made = Object.keys(mo).map(function (k) { return mo[k]; });
      list = list.filter(function (it) { return it.ready && made.indexOf(it.ready.made_by) >= 0; });
      if (!list.length) { el.hidden = true; return; }
      el.hidden = false;
    }
    if (!list.length) {                                             /* always drawn, unless he switched it off */
      o = '<div class="rd-h sec-h" data-fold="ready" role="button" tabindex="0" aria-expanded="true"><h2>' + h(secName('ready')) + '</h2></div><div class="none">No drafts right now.</div>';
      el.hidden = hiddenSec('ready', {});
      if (el._html !== o) { el.innerHTML = o; el._html = o; }
      addLines(); renderDrafts(0);
      return;
    }
    list.forEach(function (it) { var g = rdBatch(it); if (!by[g]) { by[g] = []; groups.push(g); } by[g].push(it); });
    var open = list.filter(function (it) { return it.state !== 'done'; }).length;
    o += '<div class="rd-h sec-h" data-fold="ready" role="button" tabindex="0" aria-expanded="true"><h2>' + h(secName('ready')) + '</h2><span class="n">' + (open ? plural(open, 'email') : 'all sent') + '</span><span class="wnote">' + (list.some(function (x) { return rdIs(x) && !rdOwn(x); }) ? 'Written for you in Talk to your assistant. ' : '') + 'Nothing goes out until you press Send.</span></div>';
    groups.forEach(function (g) {
      var cs = by[g], more = cs.length > 1, sendable = cs.filter(rdSendable), ga = rdAllAns(g);
      o += '<div class="rd-group">' + (g === 'left' ? '<div class="rd-req">Replies you started and left</div>' : '');
      if (g !== 'left' && more && sendable.length > 1 && !sendOff() && !rdAllBusy(g)) {
        if (S.rdAll[g]) {
          var bad = sendable.map(function (it) { var pr = wProblem(it.key, it); return pr ? [it, pr] : null; }).filter(Boolean);
          o += '<div class="rd-all" data-grp="' + h(g) + '"><b>Send all ' + sendable.length + '? This is what will go out:</b><ol>' + sendable.map(function (it) { var pp = wPayload(it.key, it); return '<li>From ' + h(pp.account) + ' to ' + h(pp.to.concat(pp.cc, pp.bcc).join(', ')) + (pp.attach.length ? ', with ' + h(pp.attach.join(', ')) : '') + ': ' + h(pp.subject) + '</li>'; }).join('') + '</ol>' +
            (bad.length ? '<div class="err" role="alert">' + bad.map(function (x) { return h(x[0].title || 'An email') + ': ' + h(x[1]); }).join('<br>') + ' Use Edit on it first.</div>' : '') +
            '<div class="acts"><button class="btn primary" type="button" data-a="rd-all-go" data-grp="' + h(g) + '"' + (bad.length ? ' disabled' : '') + '>Yes, send all ' + sendable.length + '</button><button class="btn" type="button" data-a="rd-all-no" data-grp="' + h(g) + '">Back</button></div></div>';
        } else o += '<div class="acts"><button class="btn primary" type="button" data-a="rd-all-ask" data-grp="' + h(g) + '">Send all ' + sendable.length + '</button><span class="wnote">You see what it will send before it goes.</span></div>';
      }
      if (ga) o += '<div class="kv rec-note"><b>Send all:</b> ' + (ga.status === 'working' ? '<b class="working">Sending</b>' : ga.status === 'done' || ga.status === 'failed' ? '<b class="outcome' + (ga.status === 'failed' ? ' bad' : '') + '">' + h(ga.outcome || 'Done') + '</b>' : S.listening === false ? 'This page can\'t reach your computer, so these won\'t go out. Press Send all again when it\'s back.' : 'Waiting for your computer to send them.') + '</div>';
      o += cs.map(rdCardHtml).join('') + '</div>';
    });
    el.hidden = hiddenSec('ready', {ready: open > 0});                 /* switched off: still shown while an email waits to be sent */
    if (el._html !== o) { el.innerHTML = o; el._html = o; }
    addLines();
    renderDrafts(open);
  }
  function rdSendOne(it) {
    var k = it.key, pr = wProblem(k, it);
    if (pr) { S.panel[k] = 'write'; S.err[k] = pr; return false; }
    var dd = wDraft(k, it), txt = wPressText(k, it);
    if (txt === null) return false;
    var sr = {action: 'answer', label: 'Send email', text: txt, result: 'Sending your email'};
    save(it, sr);
    if (sr.at) { dd.pressed = sr.at; S.drafts['w:' + k] = dd; keepDrafts(); }
    return true;
  }
  function rdClick(a, b) {
    var g = b.getAttribute('data-grp');
    if (a === 'rd-all-ask') { S.rdAll[g] = true; render(); return true; }
    if (a === 'rd-all-no') { delete S.rdAll[g]; render(); return true; }
    if (a === 'rd-all-go') {
      if (S.listening === false) { toast('This page can\'t reach your computer right now, so these wouldn\'t go out. Press Send all again when it\'s back.', ''); return true; }
      if (rdAllBusy(g)) return true;                                           /* one press counts once */
      var cs = rdLive().filter(function (it) { return rdBatch(it) === g && rdSendable(it); }), emails = [];
      delete S.rdAll[g];
      cs.forEach(function (it) { var pp = wPayload(it.key, it); emails.push({item: it.id, account: pp.account, to: pp.to, cc: pp.cc, bcc: pp.bcc, subject: pp.subject, body: pp.body, type: pp.type, source: pp.source, files: pp.files, attach: pp.attach, shown: pp.shown}); });
      if (!emails.length) { render(); return true; }
      chgSend('ready-all:' + g + ':' + Date.now(), JSON.stringify({send_all: {batch: g, emails: emails}}), 'Send all', 'Sending ' + emails.length + ' emails');
      render(); toast('Sending ' + plural(emails.length, 'email') + '.', ''); return true;
    }
    return false;
  }

  /* ---------- Mail: the owner's mail, read and handled here ----------
     Works on the page served from his computer only (the doors /api/mail, /api/mail/thread, /api/mail/file); the hosted page
     gets a 404 and says so. Reading goes straight to those doors; every change (archive, delete, label, read, a new draft)
     is one saved answer, like Send, and shows its plain-words outcome on the message. Mail text is only ever shown escaped.
     Nothing is marked read just by opening a message. */
  var mailFresh = 0;              // after a change of his, the reads ask the computer for the newest mail (mailReload sets it)
  var MAIL_RETRY_MS = 500;        // a busy read of the mail is asked again this soon
  function mailNew() {
    return {view: 'inbox', account: '', q: '', qd: '', deep: false, rows: [], accounts: [], more: false, next: '', loaded: false, loading: false, loadingMore: false,
            err: '', note: '', hosted: false, seq: 0, started: false, open: null, thread: null, tloading: false, terr: '', tseq: 0, scroll: 0,
            out: {}, done: {}, askDel: {}, lab: {}, draftKey: '', opened: {}, peek: null, hold: '', labels: {}, lget: {}, folder: '', fold: [], counts: {}, sel: {}, askBulk: false, mv: {}, snz: {}, pics: {}, fh: {}};
  }
  function mailEnc(s) { return encodeURIComponent(String(s == null ? '' : s)); }
  function mailId(x) { return /^\d+$/.test(String(x)) ? +x : String(x); }
  function mailWho(r) { return String(r.from_name || r.from || 'Unknown sender'); }
  function mailJson(url) {
    return fetch(url, {credentials: 'same-origin', cache: 'no-store'}).then(function (r) {
      if (r.status === 404) return {hosted: true};
      if (!r.ok) throw new Error(String(r.status));
      return r.json();
    });
  }
  /* the list: the first 50 (more = the next 50 older ones); quiet = no redraw first */
  function mailLoad(more, quiet) {
    var m = S.mail, n = ++m.seq;
    if (more) m.loadingMore = true; else m.loading = true;
    m.err = '';
    var url = 'api/mail?view=' + mailEnc(m.view) + (m.view === 'folder' ? '&folder=' + mailEnc(m.folder) : '') + '&account=' + mailEnc(m.account) + '&q=' + mailEnc(m.q) + '&limit=50' + (more && m.next ? '&before=' + mailEnc(m.next) : '') + (m.deep && m.q ? '&deep=1' : '') + (mailFresh ? '&fresh=1' : '');
    if (!quiet) render();
    return mailJson(url).then(function (j) {
      if (n !== m.seq) return;
      if (j.hosted) { m.hosted = true; m.loading = m.loadingMore = false; }
      else if (j.busy) { m.note = 'Mail is being updated. Trying again.'; setTimeout(function () { if (n === m.seq) mailLoad(more, true); }, MAIL_RETRY_MS); }
      else if (j.ok === false) { m.loading = m.loadingMore = false; m.err = j.error || 'Your mail could not be listed just now.'; }
      else {
        m.loading = m.loadingMore = false; m.note = '';
        m.rows = more ? m.rows.concat(j.rows || []) : (j.rows || []);
        if (j.stale && mailFresh && mailFresh < 15) { mailFresh++; setTimeout(function () { if (n === m.seq) mailReload(true); }, 4000); } else mailFresh = 0;   /* the change is not in the list yet: asked again */
        m.accounts = j.accounts || m.accounts; m.more = !!j.more; m.next = j.next || ''; m.loaded = true; m.counts = j.counts || m.counts;
        if (!more) m.sel = {};
        if (!m.foldGot) { m.foldGot = true; mailFolders(); }
      }
      render();
    }, function () { if (n !== m.seq) return; m.loading = m.loadingMore = false; m.err = 'Your mail could not be reached. Check the connection and try again.'; render(); });
  }
  /* each mailbox's folders or labels as a tree, with the service's unread counts (asked again after a change) */
  function mailFolders() {
    return mailJson('api/mail/folders' + (mailFresh ? '?fresh=1' : '')).then(function (j) {
      if (!j || j.hosted) return;
      if (j.busy) { setTimeout(mailFolders, MAIL_RETRY_MS); return; }
      if (j.ok !== false) { S.mail.fold = j.accounts || []; render(); }
    }, function () {});
  }
  function mailThread(id, quiet) {
    var m = S.mail, n = ++m.tseq;
    if (!quiet) { m.thread = null; m.tloading = true; }
    m.terr = '';
    return mailJson('api/mail/thread?id=' + mailEnc(id) + (mailFresh ? '&fresh=1' : '')).then(function (j) {
      if (n !== m.tseq) return;
      if (j.hosted) { m.hosted = true; m.tloading = false; }
      else if (j.busy) { setTimeout(function () { if (n === m.tseq) mailThread(id, true); }, MAIL_RETRY_MS); return; }
      else if (j.ok === false) { m.tloading = false; m.hold = ''; m.terr = j.error || 'That email could not be opened.'; }
      else { m.tloading = false; m.hold = ''; m.note = ''; m.thread = {messages: j.messages || []}; mailUnsubFetch((j.messages || []).slice(-1).map(function (x) { return x.id; })); }
      render();
    }, function () { if (n !== m.tseq) return; m.tloading = false; m.hold = ''; m.terr = 'That email could not be opened. Check the connection and try again.'; render(); });
  }
  /* Opening an email: the clicked row is drawn at once from the list already on the page (From, date, subject, the first
     words) with Opening beneath it, the part keeps its height while the email is fetched, and the page only moves when the
     part's top is above the screen. */
  function mailOpen(id) {
    var m = S.mail, box = $('mail'), sec = $('sec-mail');
    m.scroll = window.pageYOffset || 0; m.open = id; m.lab = {};
    m.peek = m.rows.filter(function (r) { return r.id === id; })[0] || null;
    m.hold = box && box.offsetHeight ? box.offsetHeight + 'px' : '';
    var p = mailThread(id, false);
    if (m.peek && m.peek.unread && mailOpenRead() && mailCan(m.peek.account).read !== false && m.view !== 'drafts') {
      var ak = 'mail:' + id + ':' + Date.now();      /* opening marks it read, written back to the service; no words shown on the email */
      if (chgSend(ak, JSON.stringify({mail_act: {message: id, act: 'read', all: true}}), 'Email', 'Working on it')) m.out['auto:' + id] = ak;
    }
    render();
    if (sec && sec.getBoundingClientRect && sec.getBoundingClientRect().top < 0 && sec.scrollIntoView) sec.scrollIntoView({block: 'start', behavior: 'smooth'});
    return p;
  }
  /* The Label box's list of names: asked for once per mailbox when the box first opens (the computer keeps the names for
     10 minutes); the box is usable at once, since a name can always be typed. */
  function mailLabels(acct) {
    var m = S.mail;
    if (!acct || m.labels[acct] || m.lget[acct]) return null;
    m.lget[acct] = true;
    return mailJson('api/mail/labels?account=' + mailEnc(acct)).then(function (j) {
      delete m.lget[acct];
      if (!j || j.ok === false || j.busy || j.hosted) return;
      m.labels[acct] = j.labels || [];
      Object.keys(m.lab).forEach(function (mid) {
        var msg = ((m.thread && m.thread.messages) || []).filter(function (x) { return String(x.id) === String(mid); })[0], dl = $('mlabs-' + mid);
        if (msg && msg.account === acct && dl) dl.innerHTML = mailLabelOpts(msg);
      });
    }, function () { delete m.lget[acct]; });
  }
  function mailLabelOpts(msg) {
    var mine = msg.labels || [];
    return (S.mail.labels[msg.account] || []).filter(function (l) { return mine.indexOf(l) < 0; }).map(function (l) { return '<option value="' + h(l) + '">'; }).join('');
  }
  function mailBack() {
    var m = S.mail, at = m.scroll;
    m.open = null; m.thread = null; m.peek = null; m.hold = ''; m.tseq++; m.tloading = false; m.terr = ''; m.note = '';
    render();
    if (window.scrollTo) window.scrollTo(0, at);
  }
  function mailOpenRead() { return keepGet('mailopenread') !== '0'; }
  function mailReload(again) {
    var m = S.mail;
    if (again !== true) mailFresh = 1;
    mailFolders();
    if (m.open != null) mailThread(m.open, true);
    mailLoad(false, true);
  }
  function mailSearch(deep) {
    var m = S.mail, bx = $('mail-q');
    if (bx) m.qd = bx.value;
    m.q = String(m.qd || '').trim(); m.deep = !!deep && !!m.q;
    return mailLoad(false);
  }
  /* one change to one email: its key and text are exactly what the engine reads */
  function mailPress(id, act, label, extra) {
    var m = S.mail, key = 'mail:' + id + ':' + Date.now(), a = {message: id, act: act};
    if (label != null && (act === 'label' || act === 'unlabel')) a.label = label;
    if (extra) Object.keys(extra).forEach(function (k) { a[k] = extra[k]; });
    if (!chgSend(key, JSON.stringify({mail_act: a}), 'Email', 'Working on it')) return false;
    if (/^(archive|trash|junk)$/.test(act)) mailX().undoFor[key] = {id: id, act: act, all: !!(extra && extra.all)};
    m.out[id] = key; delete m.askDel[id]; delete m.lab[id]; delete m.mv[id]; delete m.snz[id];
    render();
    return true;
  }
  function mailDraftPress(id, type) {
    var m = S.mail, key = 'mail-draft:' + (id == null ? 'new' : id) + ':' + Date.now();
    if (!chgSend(key, JSON.stringify({mail_draft: {message: id == null ? null : id, type: type}}), 'Start a draft', 'In Drafts, in Email')) return false;
    m.out[id == null ? 'new' : id] = key; m.draftKey = key;
    render();
    return true;
  }
  /* What came back for the presses: reload after a change that was done; open the writer on a new draft and scroll to it. */
  function mailSettle() {
    var m = S.mail, undo = [];
    Object.keys(m.out).forEach(function (id) {
      var key = m.out[id], a = S.ans[key];
      if (!a || m.done[key] || (a.status !== 'done' && a.status !== 'failed')) return;
      m.done[key] = true;
      var good = a.status === 'done' && !/^Not done/.test(String(a.outcome || ''));
      if (key.indexOf('mail:') === 0 && good) setTimeout(mailReload, 0);
      if (key.indexOf('mail:') === 0 && good && mailX().undoFor[key]) undo.push(m.undoFor[key]);
      if (key.indexOf('mail-unsub:') === 0 && good) { var uid = mailId(key.split(':')[1]); delete mailX().unsub[uid]; mailUnsubFetch([uid], true); }
    });
    if (undo.length) mailUndoToast(undo);
    if (m.draftKey && !m.opened[m.draftKey]) {
      var card = S.items.filter(function (it) { return rdIs(it) && it.ready.made_by === m.draftKey; })[0];
      if (card) {
        m.opened[m.draftKey] = true;
        S.drafts['w:' + card.key] = wDraft(card.key, card); S.panel[card.key] = 'write'; delete S.err[card.key]; keepDrafts();
        setTimeout(function () { var rf = $('sec-ready'); if (rf && rf.scrollIntoView) rf.scrollIntoView({block: 'start'}); }, 0);
      }
    }
  }
  function mailOutHtml(id) {
    var key = S.mail.out[id], a = key && S.ans[key];
    if (!a) return '';
    var fin = a.status === 'done' || a.status === 'failed', bad = a.status === 'failed' || /^Not done/.test(String(a.outcome || ''));
    var words = fin ? (a.outcome || (bad ? 'Not done.' : 'Done.')) : S.listening === false ? 'Saved. It is done when your computer is back.' : 'Working on it.';
    return '<div class="kv mail-out" role="status"><b' + (bad ? ' class="bad"' : '') + '>' + hc(words) + '</b></div>';
  }
  function mailCan(address) {
    var a = ((S.mail && S.mail.accounts) || []).filter(function (x) { return x && x.address === address; })[0];
    return (a && a.can) || {};
  }
  function mailTopHtml() {
    var m = S.mail, acc = m.accounts || [];
    return '<div class="mail-top"><div class="mail-bar">' +
      '<select id="mail-acct" aria-label="Which address"><option value="">All addresses</option>' + acc.map(function (a) { return '<option value="' + h(a.address) + '"' + (a.address === m.account ? ' selected' : '') + '>' + h(a.address) + mailCount('inbox', a.address) + '</option>'; }).join('') + '</select>' +
      '<select id="mail-view" aria-label="Which mail">' + (m.view === 'folder' ? '<option value="folder" selected>A folder</option>' : '') + MAIL_VIEWS.map(function (v) { return '<option value="' + v[0] + '"' + (v[0] === m.view ? ' selected' : '') + '>' + v[1] + mailCount(v[0]) + '</option>'; }).join('') + '</select>' +
      '<input type="search" id="mail-q" value="' + h(m.qd) + '" placeholder="Search: words, from:, to:, has:attachment, before:, after:, in:" aria-label="Search your mail" autocomplete="off">' +
      '<button class="btn" type="button" data-a="mail-search">Search</button>' +
      (m.q && !m.deep ? '<button class="btn" type="button" data-a="mail-deep">Also search the mail services</button>' : '') +
      '<button class="btn primary" type="button" data-a="mail-new">New email</button><button class="btn quiet" type="button" data-a="mail-refresh">Refresh</button></div>' +
      (m.deep && m.q ? '<div class="wnote">The mail services were searched too.</div>' : '') + mailOutHtml('new') + '</div>';
  }
  /* ---------- the Mail part's folders, selecting several, star, move and snooze ---------- */
  var MAIL_VIEWS = [['inbox', 'Inbox'], ['unread', 'Unread'], ['starred', 'Starred'], ['snoozed', 'Snoozed'], ['sent', 'Sent'], ['drafts', 'Drafts'], ['junk', 'Junk'], ['all', 'All mail']];
  var MAIL_RANK = {inbox: 0, drafts: 1, sent: 2, archive: 3, spam: 4, trash: 5, outbox: 6};
  function mailCount(key, acct) {
    var c = S.mail.counts || {}, n = 0;
    Object.keys(c).forEach(function (a) { if (acct ? a === acct : !S.mail.account || a === S.mail.account) n += (c[a] && c[a][key]) || 0; });
    return n ? ' (' + n + ')' : '';
  }
  /* a snooze time: later today (3 hours on), tomorrow 8 am, next Monday 8 am, or 8 am on a chosen date; '' when it has passed */
  function mailSnoozeAt(kind, dateStr) {
    var d = new Date(), dm = String(dateStr || '').match(/^(\d{4})-(\d\d)-(\d\d)$/);
    if (kind === 'today') d = new Date(d.getTime() + 3 * 3600000);
    else if (kind === 'tomorrow') { d.setDate(d.getDate() + 1); d.setHours(8, 0, 0, 0); }
    else if (kind === 'week') { d.setDate(d.getDate() + ((8 - d.getDay()) % 7 || 7)); d.setHours(8, 0, 0, 0); }
    else if (dm) d = new Date(+dm[1], +dm[2] - 1, +dm[3], 8, 0, 0);
    else return '';
    if (d.getTime() <= Date.now()) return '';
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':00';
  }
  function mailSnoozeHtml(scope) {
    var id = h(scope);
    return '<div class="mail-bar"><span class="kv">Snooze until</span>' + [['today', 'Later today'], ['tomorrow', 'Tomorrow'], ['week', 'Next week']].map(function (x) {
      return '<button class="btn" type="button" data-a="mail-snooze" data-id="' + id + '" data-when="' + x[0] + '">' + x[1] + '</button>';
    }).join('') + '<input type="date" id="msd-' + id + '" aria-label="Pick a date"><button class="btn" type="button" data-a="mail-snooze" data-id="' + id + '" data-when="date">That date</button>' +
      '<button class="btn quiet" type="button" data-a="mail-snooze-no" data-id="' + id + '">Cancel</button></div>';
  }
  function mailMoveHtml(scope, accts) {
    var o = '';
    (S.mail.fold || []).forEach(function (a) {
      if (accts.indexOf(a.address) < 0) return;
      (a.folders || []).filter(function (f) { return f.kind !== 'outbox' && f.kind !== 'drafts'; }).forEach(function (f) { o += '<option value="' + h(f.id) + '">' + h(f.path) + '</option>'; });
    });
    return '<div class="mail-bar"><select id="mmove-' + h(scope) + '" aria-label="Move to"><option value="">Move to...</option>' + o + '</select>' +
      '<button class="btn primary" type="button" data-a="mail-move-go" data-id="' + h(scope) + '">Move</button><button class="btn quiet" type="button" data-a="mail-move-no" data-id="' + h(scope) + '">Cancel</button></div>';
  }
  function mailSelIds() { var m = S.mail; return Object.keys(m.sel).filter(function (k) { return m.sel[k]; }); }
  /* ---------- Undo for Archive, Delete and Junk, and Unsubscribe (engine: mail_handle.py) ---------- */
  function mailX() { var m = S.mail; if (!m.unsub) { m.unsub = {}; m.undoFor = {}; m.undos = {}; m.askUnsub = {}; } return m; }
  var MAIL_DONE = {archive: 'Archived', trash: 'Moved to the trash', junk: 'Moved to junk'};
  function mailUndoToast(batch) {
    var m = mailX(), key = 'mailundo:' + Date.now();
    m.undos[key] = batch;
    toast(MAIL_DONE[batch[0].act] + (batch.length > 1 ? ' (' + plural(batch.length, 'conversation') + ')' : '') + '.', key, '', {a: 'mail-undo'});
  }
  function mailUndo(key) {
    var m = mailX(), batch = m.undos[key] || [];
    delete m.undos[key]; hideToast();
    batch.forEach(function (u) { mailPress(u.id, 'restore', null, {label: u.act, all: u.all}); });
    if (batch.length) toast('Putting it back.', '');
  }
  /* which of these emails offer Unsubscribe: asked of the engine once each (it asks the mail service once and keeps the answer) */
  /* the computer answers at once: what it holds, or "pending" while it asks the mail service in the background; asked again in 1.5 s (at most 12 times) */
  function mailUnsubFetch(ids, fresh, tries) {
    var m = mailX(), want = (ids || []).filter(function (i) { return i != null && (tries ? m.unsub[i] && m.unsub[i].loading : !m.unsub[i]); }).slice(0, 25);
    if (!want.length) return;
    want.forEach(function (i) { m.unsub[i] = {loading: true}; });
    mailJson('api/mail/unsub?' + (want.length > 1 ? 'ids=' + want.join(',') : 'id=' + mailEnc(want[0])) + (fresh ? '&fresh=1' : '')).then(function (j) {
      var got = want.length > 1 ? (j.info || {}) : (function (o) { o[want[0]] = j; return o; })({}), again = [];
      if (j.busy) { again = want; }
      else want.forEach(function (i) { var r = got[String(i)]; if (r && r.pending) again.push(i); else m.unsub[i] = r && r.ok ? r : {has: false, err: true}; });
      if (again.length && (tries || 0) < 12) setTimeout(function () { mailUnsubFetch(again, false, (tries || 0) + 1); }, 1500);
      else again.forEach(function (i) { m.unsub[i] = {has: false, err: true}; });
      render();
    }, function () { want.forEach(function (i) { delete m.unsub[i]; }); });
  }
  function mailUnsubSel() { var m = mailX(); return mailSelIds().filter(function (k) { var u = m.unsub[mailId(k)]; return u && u.has && !u.done; }); }
  function mailUnsubPress(id, via) {
    var m = mailX(), key = 'mail-unsub:' + id + ':' + Date.now();
    if (!chgSend(key, JSON.stringify({mail_unsub: {message: id, via: via}}), 'Email', 'Working on it')) return false;
    m.out[id] = key; delete m.askUnsub[id];
    render();
    return true;
  }
  /* each selected sender that offers the one-click way is unsubscribed; one that only gives a page or an email is left to the owner, on its own email */
  function mailBulkUnsub() {
    var m = mailX(), n = 0, left = 0;
    mailUnsubSel().forEach(function (k, i) {
      var id = mailId(k), u = m.unsub[id], key = 'mail-unsub:' + id + ':' + (Date.now() + i);
      if (!u.one_click) { left++; return; }
      if (chgSend(key, JSON.stringify({mail_unsub: {message: id, via: 'auto'}}), 'Email', 'Working on it')) { m.out['bulk:' + id] = key; n++; }
    });
    m.sel = {};
    toast((n ? 'Unsubscribing from ' + plural(n, 'sender') + '.' : 'None of those can be unsubscribed from in one press.') + (left ? ' ' + plural(left, 'other') + ' give only a page or an email address: open each one to finish it.' : ''), '');
    render();
  }
  function mailUnsubHtml(msg) {
    var m = mailX(), u = m.unsub[msg.id], id = h(msg.id);
    if (!u || !u.has) return '';
    if (u.done) return '<span class="kv">Unsubscribed</span>';
    if (u.one_click) return '<button class="btn" type="button" data-a="mail-unsub" data-via="auto" data-id="' + id + '">Unsubscribe</button>';
    if (u.https) return '<a class="btn" href="' + h(u.https) + '" target="_blank" rel="noopener noreferrer">Unsubscribe (opens their page)</a>';
    if (u.mailto) return m.askUnsub[msg.id]
      ? '<span class="chg-warn"><b>Send an email to ' + h(u.mailto.to) + ' to unsubscribe?</b></span><button class="btn primary" type="button" data-a="mail-unsub" data-via="mailto" data-id="' + id + '">Yes, send it</button><button class="btn" type="button" data-a="mail-unsub-no" data-id="' + id + '">Not now</button>'
      : '<button class="btn" type="button" data-a="mail-unsub-ask" data-id="' + id + '">Unsubscribe (sends an email)</button>';
    return '';
  }
  function mailBulkHtml() {
    var m = S.mail, ids = mailSelIds();
    if (!ids.length || m.view === 'drafts') return '';
    var accts = [];
    m.rows.forEach(function (r) { if (m.sel[r.id] && accts.indexOf(r.account) < 0) accts.push(r.account); });
    var ok = function (x) { return accts.every(function (a) { return mailCan(a)[x] !== false; }); }, b = function (act, w) { return '<button class="btn" type="button" data-a="mail-bulk" data-act="' + act + '">' + w + '</button>'; };
    var o = '<div class="mail-bulk" role="group" aria-label="Selected mail"><b>' + ids.length + ' selected</b><div class="acts">' +
      '<button class="btn" type="button" data-a="mail-card" data-id="bulk" title="Make a card from the selected emails">Card</button>' +
      (ok('archive') ? b('archive', 'Archive') : '') + (ok('trash') ? '<button class="btn" type="button" data-a="mail-bulk-del-ask">Delete</button>' + b('junk', 'Junk') : '') +
      (mailUnsubSel().length ? '<button class="btn" type="button" data-a="mail-bulk-unsub">Unsubscribe</button>' : '') +
      (ok('read') ? b('read', 'Mark read') + b('unread', 'Mark unread') + '<button class="btn" type="button" data-a="mail-snooze-open" data-id="bulk">Snooze</button>' : '') +
      (m.view === 'snoozed' ? b('unsnooze', 'Bring back now') : '') + (ok('label') ? b('star', 'Star') + b('unstar', 'Unstar') : '') +
      (ok('label') && accts.length === 1 ? '<button class="btn" type="button" data-a="mail-move-open" data-id="bulk">Move</button>' : '') +
      '<button class="btn quiet" type="button" data-a="mail-sel-none">Clear</button></div>';
    if (m.askBulk) o += '<div class="chg-warn"><b>Move ' + plural(ids.length, 'conversation') + ' to the trash?</b><span>They can be taken out of the trash from your mail service.</span></div><div class="acts"><button class="btn primary" type="button" data-a="mail-bulk-del-go">Yes, move them</button><button class="btn" type="button" data-a="mail-bulk-del-no">Keep them</button></div>';
    if (m.mv.bulk) o += mailMoveHtml('bulk', accts);
    if (m.snz.bulk) o += mailSnoozeHtml('bulk');
    return o + '</div>';
  }
  /* one change to every selected row (a row stands for its whole conversation: the engine reaches each email it applies to) */
  function mailBulk(act, extra) {
    var m = S.mail, ids = mailSelIds(), n = 0;
    ids.forEach(function (k, i) {
      var id = mailId(k), a = {message: id, act: act, all: true}, key = 'mail:' + id + ':' + (Date.now() + i);
      Object.keys(extra || {}).forEach(function (x) { a[x] = extra[x]; });
      if (chgSend(key, JSON.stringify({mail_act: a}), 'Email', 'Working on it')) {
        if (/^(archive|trash|junk)$/.test(act)) mailX().undoFor[key] = {id: id, act: act, all: true};
        m.out['bulk:' + id] = key; n++;
      }
    });
    m.sel = {}; m.askBulk = false; m.mv = {}; m.snz = {};
    if (n) toast('Working on ' + plural(n, 'conversation') + '.', '');
    render();
  }
  /* Card: the picked emails become a card at once (engine: mail_card.py), grouped by topic as new mail is; it teaches
     nothing. An email already on a card opens that card instead of making a second one. */
  function mailCardOf(id) {
    var on = function (it) { return (it.messages || []).some(function (x) { return String(x.id) === String(id); }); };
    return S.items.filter(function (it) { return it.state !== 'done' && on(it); })[0] || S.items.filter(on)[0] || null;
  }
  function mailCardShow(key, words) {
    if (POP == null && find(key)) jump(key);
    if (words) toast(words, '');
  }
  function mailCard(ids, all) {
    var m = mailX(), had = [], want = [];
    ids.forEach(function (id) { var c = mailCardOf(id); if (c) { if (had.indexOf(c.key) < 0) had.push(c.key); } else want.push(id); });
    if (!want.length) { if (had.length) mailCardShow(had[0], ids.length === 1 ? 'That email is already on a card.' : had.length === 1 ? 'Those emails are already on a card.' : 'Those emails are already on cards. This is the first.'); return false; }
    var key = 'mail-card:' + Date.now();
    if (!chgSend(key, JSON.stringify({mail_card: {messages: want, all: !!all}}), 'Email', 'Making a card')) return false;
    m.cardFor = m.cardFor || {}; m.cardFor[key] = {ids: want, until: 0};
    if (!all) m.out[want[0]] = key;
    toast(want.length === 1 ? 'Making a card from that email.' : 'Making a card from ' + want.length + ' emails.', '');
    render();
    return true;
  }
  /* the press came back: open the card it made or added to, with the engine's words */
  function mailCardSettle() {
    var m = mailX();
    Object.keys(m.cardFor || {}).forEach(function (key) {
      var w = m.cardFor[key], a = S.ans[key];
      if (!a || (a.status !== 'done' && a.status !== 'failed')) return;
      var good = a.status === 'done' && !/^Not done/.test(String(a.outcome || ''));
      if (!good) { delete m.cardFor[key]; toast(a.outcome || 'Not done.', ''); return; }
      if (!w.until) w.until = Date.now() + 20000;
      var c = null;
      w.ids.some(function (id) { c = mailCardOf(id); return !!c; });
      if (c || Date.now() > w.until) { delete m.cardFor[key]; if (c) mailCardShow(c.key, a.outcome || ''); else toast(a.outcome || 'Done.', ''); }
    });
  }
  function mailTreeHtml() {
    var m = S.mail, accts = mailBoxes().filter(function (a) { return !m.account || a.address === m.account; });
    if (!accts.length) return '';
    var c = m.counts || {}, o = '<nav class="mail-tree" aria-label="Folders">';
    accts.forEach(function (a) {
      var fs = (a.folders || []).slice(), by = {}, ia = (c[a.address] || {}).inbox || 0;
      fs.forEach(function (f) { by[f.path] = f; });
      var key = function (f) { var root = by[String(f.path).split('/')[0]] || f; return [MAIL_RANK[root.kind] != null ? MAIL_RANK[root.kind] : 7, String(f.path).toLowerCase()]; };
      fs.sort(function (x, y) { var kx = key(x), ky = key(y); return kx[0] - ky[0] || (kx[1] < ky[1] ? -1 : kx[1] > ky[1] ? 1 : 0); });
      var shut = !!mailFolds()[a.address];
      if (!fs.length) fs = [{id: '', path: 'Inbox', unread: ia}];      /* no folders stored for it yet: its inbox is still one press away */
      o += '<div class="mail-acct' + (shut ? ' shut' : '') + '" data-acct="' + h(a.address) + '"><div class="mail-ah">' +
        '<button class="btn mail-grip' + (MG.kb === a.address ? ' lifted' : '') + '" type="button" data-mgrip="' + h(a.address) + '" aria-pressed="' + (MG.kb === a.address) + '" title="Drag to move" aria-label="Move ' + h(a.address) + ': drag it, or press Space to pick it up, use the Up and Down arrow keys, press Space to put it down"></button>' +
        '<button class="mail-fold head" type="button" data-a="mail-shut" data-acct="' + h(a.address) + '" aria-expanded="' + !shut + '" title="' + (shut ? 'Show' : 'Hide') + ' the folders of ' + h(a.address) + '">' + h(a.address) + (ia ? ' <b>' + ia + '</b>' : '') + '</button></div><ul>';
      fs.forEach(function (f) {
        var path = String(f.path), n = f.unread != null ? f.unread : f.stored_unread, on = m.account === a.address && (f.id ? m.view === 'folder' && m.folder === f.id : m.view === 'inbox');
        o += '<li class="mail-d' + Math.min(path.split('/').length - 1, 5) + '"><button class="mail-fold' + (on ? ' on' : '') + '" type="button" data-a="mail-folder" data-acct="' + h(a.address) + '" data-fid="' + h(f.id) + '">' + h(path.split('/').pop()) + (n ? ' <b>' + n + '</b>' : '') + '</button></li>';
      });
      o += '</ul></div>';
    });
    return o + '</nav>';
  }
  /* every mailbox in the column: each one the list knows, with its folders when any are stored, in the saved order */
  function mailBoxes() {
    var m = S.mail, by = {}, out = [];
    (m.fold || []).forEach(function (a) { by[a.address] = a; });
    (m.accounts || []).forEach(function (a) { if (!by[a.address]) by[a.address] = {address: a.address, folders: []}; out.push(by[a.address]); });
    (m.fold || []).forEach(function (a) { if (out.indexOf(a) < 0) out.push(a); });
    return out;
  }
  /* each mailbox's folded state, kept per mailbox in this browser */
  function mailFolds() { try { return JSON.parse(keepGet('mailfold') || '{}') || {}; } catch (e) { return {}; } }
  function mailFoldSet(addr, shut) { var f = mailFolds(); if (shut) f[addr] = 1; else delete f[addr]; keepSet('mailfold', JSON.stringify(f)); }
  /* Dragging a mailbox in the left column (touch, pen, mouse; or Space, Up and Down on its handle) puts the mailboxes in
     a new order, saved as the page setting mail_order, which every list of mailboxes follows. */
  var MG = {drag: null, kb: null};
  function mailOrderNow() { return S.mail ? mailBoxes().map(function (a) { return a.address; }) : []; }
  function mailOrderApply(list) {
    var m = S.mail, at = {};
    list.forEach(function (a, i) { at[a] = i; });
    var by = function (x, y) { return (at[x.address] != null ? at[x.address] : 99) - (at[y.address] != null ? at[y.address] : 99); };
    m.fold = (m.fold || []).slice().sort(by); m.accounts = (m.accounts || []).slice().sort(by);
  }
  function mailOrderSave() {
    if (!S.db) return;
    var rec = {id: 'settings', action: 'answer', label: 'Settings', text: JSON.stringify({settings: {group: 'page', values: {mail_order: mailOrderNow()}}}), at: isoLocal(new Date()), device: device, sent: false, status: 'saved', result: 'Saving the order of your mailboxes'};
    S.db.setAnswer('settings', rec).then(function () {}, function () { toast('The order of your mailboxes did not save. Check the connection and try again.', ''); });
  }
  function mailMove(addr, to, save) {
    var l = mailOrderNow(), i = l.indexOf(addr);
    if (i < 0 || to < 0 || to >= l.length) return;
    l.splice(i, 1); l.splice(to, 0, addr);
    mailOrderApply(l); render();
    if (save) mailOrderSave();
  }
  document.addEventListener('pointerdown', function (e) {
    var g = e.target.closest && e.target.closest('.mail-grip');
    if (!g || (e.pointerType === 'mouse' && e.button !== 0)) return;
    MG.drag = {a: g.getAttribute('data-mgrip')};
    try { g.setPointerCapture(e.pointerId); } catch (x) {}
    g.closest('.mail-acct').classList.add('lifted');
    e.preventDefault();
  });
  document.addEventListener('pointermove', function (e) {
    if (!MG.drag) return;
    var el = document.elementFromPoint(e.clientX, e.clientY), t = el && el.closest('.mail-acct');
    [].forEach.call(document.querySelectorAll('.mail-over'), function (n) { n.classList.remove('mail-over'); });
    if (t && t.getAttribute('data-acct') !== MG.drag.a) t.classList.add('mail-over');
  });
  function mailDragEnd(e, drop) {
    var d = MG.drag;
    if (!d) return;
    MG.drag = null;
    [].forEach.call(document.querySelectorAll('.mail-over,.mail-acct.lifted'), function (n) { n.classList.remove('mail-over'); n.classList.remove('lifted'); });
    if (!drop) return;
    var el = document.elementFromPoint(e.clientX, e.clientY), t = el && el.closest('.mail-acct');
    if (!t || t.getAttribute('data-acct') === d.a) return;
    var l = mailOrderNow(), over = t.getAttribute('data-acct'), r = t.getBoundingClientRect(), after = e.clientY > r.top + r.height / 2;
    l.splice(l.indexOf(d.a), 1);
    l.splice(l.indexOf(over) + (after ? 1 : 0), 0, d.a);
    mailOrderApply(l); render(); mailOrderSave();
  }
  document.addEventListener('pointercancel', function (e) { mailDragEnd(e, false); });
  document.addEventListener('pointerup', function (e) { mailDragEnd(e, true); });
  document.addEventListener('keydown', function (e) {
    var g = e.target.closest && e.target.closest('.mail-grip');
    if (!g) return;
    var a = g.getAttribute('data-mgrip'), refocus = function () { var n = document.querySelector('.mail-grip[data-mgrip="' + a + '"]'); if (n) n.focus(); };
    if (e.key === ' ' || e.key === 'Enter' || e.key === 'Escape') {
      if (e.key === 'Escape' && MG.kb !== a) return;
      e.preventDefault(); MG.kb = (e.key === 'Escape' || MG.kb === a) ? null : a; render(); refocus(); return;
    }
    if (MG.kb !== a || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown')) return;
    e.preventDefault();
    mailMove(a, mailOrderNow().indexOf(a) + (e.key === 'ArrowUp' ? -1 : 1), true); refocus();
  });
  /* the divider between the mailbox column and the reading area (computer widths only): drag, or Left and Right on it */
  var MW_MIN = 140, MW_MAX = 480;
  function mailWidth() { var w = parseInt(keepGet('mailw'), 10); return w >= MW_MIN && w <= MW_MAX ? w : 200; }
  function mailWidthSet(w, save) {
    w = Math.max(MW_MIN, Math.min(MW_MAX, Math.round(w)));
    var b = document.querySelector('.mail-body'), d = document.querySelector('.mail-div');
    if (b) b.style.setProperty('--mail-w', w + 'px');
    if (d) d.setAttribute('aria-valuenow', String(w));
    if (save) { keepSet('mailw', String(w)); render(); }
  }
  var MD = null;
  document.addEventListener('pointerdown', function (e) {
    var d = e.target.closest && e.target.closest('.mail-div');
    if (!d || (e.pointerType === 'mouse' && e.button !== 0)) return;
    var t = document.querySelector('.mail-tree');
    MD = {x: e.clientX, w: t ? t.getBoundingClientRect().width : mailWidth()};
    try { d.setPointerCapture(e.pointerId); } catch (x) {}
    d.classList.add('drag'); e.preventDefault();
  });
  document.addEventListener('pointermove', function (e) { if (MD) mailWidthSet(MD.w + e.clientX - MD.x, false); });
  function mailDivEnd(e, save) {
    if (!MD) return;
    var w = MD.w + e.clientX - MD.x; MD = null;
    var d = document.querySelector('.mail-div'); if (d) d.classList.remove('drag');
    if (save) mailWidthSet(w, true);
  }
  document.addEventListener('pointerup', function (e) { mailDivEnd(e, true); });
  document.addEventListener('pointercancel', function (e) { mailDivEnd(e, false); });
  document.addEventListener('keydown', function (e) {
    if (!(e.target.closest && e.target.closest('.mail-div')) || (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight')) return;
    e.preventDefault(); mailWidthSet(mailWidth() + (e.key === 'ArrowLeft' ? -20 : 20), true);
    var d = document.querySelector('.mail-div'); if (d) d.focus();
  });
  /* Pop out: one email in a window of its own (this page with only that email and its actions), so several can be open */
  var POP = (function () { var q = /[?&]popout=([^&]+)/.exec(window.location.search || ''); return q ? decodeURIComponent(q[1]) : null; })();
  function mailPop(id) {
    var w = window.open(window.location.pathname + '?popout=' + mailEnc(id), 'mail-' + String(id).replace(/[^\w-]/g, '_'), 'popup=yes,width=820,height=720');
    if (!w) toast('Your browser blocked the new window. Allow pop-ups for this page and try again.', '');
  }
  function mailClip(n) {
    return n ? '<span class="mail-clip" aria-label="' + plural(n, 'attachment') + '" title="' + plural(n, 'attachment') + '"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.5l-8.6 8.6a5.5 5.5 0 0 1-7.8-7.8l9-9a3.7 3.7 0 0 1 5.2 5.2l-9 9a1.8 1.8 0 0 1-2.6-2.6l8.3-8.3"/></svg>' + n + '</span>' : '';
  }
  function mailRowHtml(r) {
    var t = D(r.ts), when = t ? fmtDT(t) : String(r.when || '');
    var m = S.mail, ro = m.view === 'drafts';
    return '<li class="mail-row' + (r.unread ? ' unread' : '') + '" data-a="mail-open" data-id="' + h(r.id) + '" role="button" tabindex="0">' +
      (ro ? '' : '<input type="checkbox" class="mail-sel" data-a="mail-sel" data-id="' + h(r.id) + '"' + (m.sel[r.id] ? ' checked' : '') + ' aria-label="Select this email">' +
        '<button class="mail-star' + (r.starred ? ' on' : '') + '" type="button" data-a="mail-star" data-id="' + h(r.id) + '" aria-pressed="' + (r.starred ? 'true' : 'false') + '" aria-label="' + (r.starred ? 'Remove the star' : 'Star this email') + '">' + (r.starred ? '&#9733;' : '&#9734;') + '</button>') +
      '<span class="mail-main"><span class="mail-line"><span class="t">' + h(mailWho(r)) + '</span><span class="mail-subj">' + h(r.subject || '(no subject)') + '</span>' + ((r.count || 1) > 1 ? '<span class="mail-n" title="' + plural(r.count, 'email') + ' in this conversation">' + r.count + '</span>' : '') + mailClip(+r.files || 0) + '</span>' +
      (r.snippet ? '<span class="src">' + h(r.snippet) + '</span>' : '') +
      '<span class="src">' + h(when) + (r.account ? ' to ' + h(r.account) : '') + (r.unread ? ' (unread)' : '') + (ro ? ' (a draft, read only here)' : '') + (r.snoozed ? ' (snoozed until ' + h(fmtDT(D(r.snoozed))) + ')' : '') + '</span></span></li>';
  }
  function mailListHtml() {
    var m = S.mail, o = '';
    if (m.note) o += '<div class="wnote" role="status">' + h(m.note) + '</div>';
    if (m.err) o += '<div class="err" role="alert">' + h(m.err) + '</div>';
    if (m.rows.length && m.view !== 'drafts') o += '<label class="check mail-all"><input type="checkbox" data-a="mail-sel-all"' + (m.rows.every(function (r) { return m.sel[r.id]; }) ? ' checked' : '') + '> Select all shown</label>';
    if (m.rows.length) o += '<ul class="rows mail-list">' + m.rows.map(mailRowHtml).join('') + '</ul>';
    else if (m.loading && !m.note) o += '<div class="none" role="status">Getting your mail.</div>';
    else if (m.loaded && !m.err) o += '<div class="none">' + (m.q ? 'No mail matches that.' : m.view === 'unread' ? 'No unread mail.' : m.view === 'snoozed' ? 'Nothing is snoozed.' : 'No mail here.') + '</div>';
    if (m.rows.length && m.loading) o += '<div class="wnote" role="status">Updating.</div>';
    if (m.more) o += '<div class="acts"><button class="btn" type="button" data-a="mail-older"' + (m.loadingMore ? ' disabled' : '') + '>' + (m.loadingMore ? 'Getting older mail' : 'Older') + '</button></div>';
    return o;
  }
  /* A sample of a junk question card's sender: the newest email in full, Older and Newer step through the rest.
     Read from the mail on his computer only (the door /api/mail/sample): nothing is marked read, nothing reaches the service. */
  function sampleLoad(key, id) {
    var sm = S.sample[key] = S.sample[key] || {}, n = sm.seq = (sm.seq || 0) + 1;
    sm.loading = true; sm.err = '';
    render();
    return mailJson('api/mail/sample?card=' + mailEnc(key) + (id != null ? '&id=' + mailEnc(id) : '')).then(function (j) {
      if (S.sample[key] !== sm || n !== sm.seq) return;
      if (j.hosted) { sm.loading = false; sm.err = 'A sample can be read on the page served from your computer.'; }
      else if (j.busy) { setTimeout(function () { if (S.sample[key] === sm && n === sm.seq) sampleLoad(key, id); }, MAIL_RETRY_MS); return; }
      else if (j.ok === false) { sm.loading = false; sm.err = j.error || 'The sample could not be read just now.'; }
      else { sm.loading = false; sm.data = j; }
      render();
    }, function () { if (S.sample[key] !== sm || n !== sm.seq) return; sm.loading = false; sm.err = 'The sample could not be reached. Check the connection and try again.'; render(); });
  }
  function sampleHtml(key) {
    var sm = S.sample[key], d = sm.data, o = '<div class="panel-box mail-sample">';
    if (sm.err) return o + '<div class="err" role="alert">' + h(sm.err) + '</div></div>';
    if (!d) return o + '<div class="none" role="status">Getting the newest email from this sender.</div></div>';
    if (!d.message) return o + '<div class="none">No email from ' + h(d.sender || 'this sender') + ' is held on your computer.</div></div>';
    var list = d.list || [], i = 0;
    list.forEach(function (r, x) { if (r.id === d.message.id) i = x; });
    o += '<div class="acts">' +
      (i + 1 < list.length ? '<button class="btn" type="button" data-a="sample-step" data-id="' + h(list[i + 1].id) + '">&larr; Older</button>' : '') +
      (i > 0 ? '<button class="btn" type="button" data-a="sample-step" data-id="' + h(list[i - 1].id) + '">Newer &rarr;</button>' : '') +
      '<span class="kv">' + h((i + 1) + ' of the ' + plural(list.length, 'newest email') + ' from ' + (d.sender || 'this sender')) + (sm.loading ? ' (getting it)' : '') + '</span></div>';
    return o + mailMsgHtml(d.message, true) + '</div>';
  }
  /* A paper (PDF) or picture shows inside the viewer, with Download there; any other kind still downloads. */
  function attKind(n) {
    var x = (/\.([A-Za-z0-9]+)$/.exec(String(n || '')) || [])[1]; x = (x || '').toLowerCase();
    return x === 'pdf' ? 'pdf' : /^(png|jpe?g|gif)$/.test(x) ? 'image' : '';
  }
  function attView(b) {
    var v = {key: S.view ? S.view.key : '', name: b.getAttribute('data-name') || '', kind: b.getAttribute('data-kind') || '', ref: b.getAttribute('data-ref'), msg: +b.getAttribute('data-msg') || 0};
    if (!VIEWQ && viewPop(v)) return;
    if (S.view) v.back = S.view;
    S.view = v; viewDraw();
  }
  function mailMsgHtml(msg, bare) {
    var id = h(msg.id), can = mailCan(msg.account), ok = function (x) { return can[x] !== false; }, t = D(msg.ts), mine = msg.labels || [], m = S.mail, o = '';
    o += '<article class="mail-msg' + (msg.unread ? ' unread' : '') + '" data-mid="' + id + '">' +
      '<div class="kv"><b>From:</b> ' + h(mailWho(msg)) + (msg.from_name && msg.from ? ' &lt;' + h(msg.from) + '&gt;' : '') + '</div>' +
      '<div class="kv"><b>To:</b> ' + h((msg.to || []).join(', ')) + '</div>' + ((msg.cc || []).length ? '<div class="kv"><b>Copy to:</b> ' + h(msg.cc.join(', ')) + '</div>' : '') +
      '<div class="kv"><b>Date:</b> ' + h(t ? fmtD(t) + ' ' + fmtT(t) : msg.when || '') + (msg.unread ? ' (unread)' : '') + '</div>' +
      (msg.account ? '<div class="kv"><b>Mailbox:</b> ' + h(msg.account) + '</div>' : '');
    if (mine.length) o += '<div class="kv"><b>Labels:</b> ' + mine.map(function (l) {
      return '<span class="chip">' + h(l) + (ok('label') && !bare ? ' <button class="link" type="button" data-a="mail-unlabel" data-id="' + id + '" data-label="' + h(l) + '" aria-label="Remove the label ' + h(l) + '">Remove label</button>' : '') + '</span>';
    }).join(' ') + '</div>';
    if (msg.html) {      /* the email as it was sent, in a frame that may run nothing; pictures from the internet unless Settings says Hide (then on his press) */
      var pics = mailPicsShown() || !!m.pics[msg.id];
      if (msg.remote && !pics) o += '<div class="mail-pics" role="status">Pictures from the internet are hidden. <button class="link" type="button" data-a="mail-pics" data-id="' + id + '">Show pictures</button></div>';
      o += '<iframe class="mail-html" data-fk="' + id + (pics ? 'p' : '') + '" title="The email as it was sent" sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox" referrerpolicy="no-referrer" src="api/mail/body?id=' + mailEnc(msg.id) + (pics ? '&amp;pictures=1' : '') + '"></iframe>';
    } else o += '<pre class="src-text">' + h(msg.text || '') + '</pre>';
    if ((msg.files || []).length) o += '<div class="kv mail-files"><b>Attachments:</b> ' + msg.files.map(function (f) {
      var fk = attKind(f.name), lab = h(f.name) + (f.size ? ' (' + h(mailSize(f.size)) + ')' : '');
      if (fk && f.ref) return '<button class="link" type="button" data-a="mail-attview" data-ref="' + h(f.ref) + '" data-name="' + h(f.name) + '" data-kind="' + fk + '" data-msg="' + id + '">' + lab + '</button>';
      return '<a href="api/mail/file?ref=' + mailEnc(f.ref) + '&amp;msg=' + mailEnc(msg.id) + '" download="' + h(f.name) + '" rel="noopener">' + h(f.name) + (f.size ? ' (' + h(mailSize(f.size)) + ')' : '') + '</a>';
    }).join(', ') + '</div>';
    if (bare) return o + '</article>';
    o += '<div class="acts">' +
      '<button class="btn" type="button" data-a="mail-draft" data-t="reply" data-id="' + id + '">Reply</button>' +
      '<button class="btn" type="button" data-a="mail-draft" data-t="reply_all" data-id="' + id + '">Reply all</button>' +
      '<button class="btn" type="button" data-a="mail-draft" data-t="forward" data-id="' + id + '">Forward</button>' +
      '<button class="btn" type="button" data-a="mail-card" data-id="' + id + '" title="Make a card from this email">Card</button>' +
      (ok('archive') && msg.inbox !== false ? '<button class="btn" type="button" data-a="mail-act" data-act="archive" data-id="' + id + '">Archive</button>' : '') +
      (ok('trash') ? '<button class="btn" type="button" data-a="mail-del-ask" data-id="' + id + '">Delete</button>' + (m.view === 'junk' ? '' : '<button class="btn" type="button" data-a="mail-act" data-act="junk" data-id="' + id + '">Junk</button>') : '') +
      mailUnsubHtml(msg) +
      (ok('label') ? '<button class="btn" type="button" data-a="mail-label-open" data-id="' + id + '">Label</button>' : '') +
      (ok('label') ? '<button class="btn" type="button" data-a="mail-act" data-act="' + (msg.starred ? 'unstar' : 'star') + '" data-id="' + id + '">' + (msg.starred ? 'Remove star' : 'Star') + '</button><button class="btn" type="button" data-a="mail-move-open" data-id="' + id + '">Move</button>' : '') +
      (ok('read') ? (msg.snoozed ? '<button class="btn" type="button" data-a="mail-unsnooze" data-id="' + id + '">Bring back now</button>' : '<button class="btn" type="button" data-a="mail-snooze-open" data-id="' + id + '">Snooze</button>') : '') +
      (ok('read') ? '<button class="btn" type="button" data-a="mail-act" data-act="' + (msg.unread ? 'read' : 'unread') + '" data-id="' + id + '">' + (msg.unread ? 'Mark read' : 'Mark unread') + '</button>' : '') + '</div>';
    if (m.askDel[msg.id]) o += '<div class="chg-warn"><b>Move this email to the trash?</b><span>It can be taken out of the trash from your mail service.</span></div><div class="acts"><button class="btn primary" type="button" data-a="mail-del-go" data-id="' + id + '">Yes, move it</button><button class="btn" type="button" data-a="mail-del-no" data-id="' + id + '">Keep it</button></div>';
    if (m.mv[msg.id]) o += mailMoveHtml(msg.id, [msg.account]);
    if (m.snz[msg.id]) o += mailSnoozeHtml(msg.id);
    if (m.lab[msg.id]) o += '<div class="mail-bar"><input type="text" id="mlab-' + id + '" list="mlabs-' + id + '" placeholder="Choose a label or type a new one" aria-label="Label" autocomplete="off"><datalist id="mlabs-' + id + '">' +
      mailLabelOpts(msg) + '</datalist>' +
      '<button class="btn primary" type="button" data-a="mail-label-go" data-id="' + id + '">Add label</button><button class="btn quiet" type="button" data-a="mail-label-no" data-id="' + id + '">Cancel</button></div>';
    return o + mailOutHtml(msg.id) + '</article>';
  }
  function mailPicsShown() { var st = setts(); return !(st && st.page && st.page.mail_pictures === 'hide'); }
  function mailThreadHtml() {
    var m = S.mail, th = m.thread, o = POP != null ? '<div class="acts"><button class="btn" type="button" data-a="mail-close">Close this window</button></div>' : '<div class="acts"><button class="btn" type="button" data-a="mail-back">Back to the list</button><button class="btn mail-pop" type="button" data-a="mail-pop" data-id="' + h(m.open) + '">Pop out</button></div>';
    if (m.note) o += '<div class="wnote" role="status">' + h(m.note) + '</div>';
    if (m.terr) o += '<div class="err" role="alert">' + h(m.terr) + '</div>';
    if (m.tloading && !th && m.peek) {
      var pk = m.peek, pt = D(pk.ts);
      return o + '<article class="mail-msg mail-peek' + (pk.unread ? ' unread' : '') + '"><div class="kv"><b>From:</b> ' + h(mailWho(pk)) + '</div>' +
        '<div class="kv"><b>Date:</b> ' + h(pt ? fmtD(pt) + ' ' + fmtT(pt) : pk.when || '') + '</div><div class="kv"><b>Subject:</b> ' + h(pk.subject || '(no subject)') + '</div>' +
        (pk.snippet ? '<div class="src">' + h(pk.snippet) + '</div>' : '') + '<div class="none" role="status">Opening...</div></article>';
    }
    if (m.tloading && !th) return o + '<div class="none" role="status">Getting the email.</div>';
    if (!th) return o;
    var told = {}, seen = [];
    th.messages.forEach(function (msg) {
      var can = mailCan(msg.account), no = [['archive', 'archiving'], ['trash', 'deleting'], ['label', 'labels'], ['read', 'marking read or unread']].filter(function (x) { return can[x[0]] === false; }).map(function (x) { return x[1]; });
      if (no.length && !told[msg.account]) { told[msg.account] = 1; seen.push(msg.account + ': its sign-in does not allow ' + no.join(', ') + ' yet, so those buttons are not shown.'); }
    });
    if (seen.length) o += '<div class="wnote">' + seen.map(h).join(' ') + '</div>';
    return o + th.messages.map(function (msg) { return mailMsgHtml(msg, m.view === 'drafts'); }).join('');
  }
  function renderMail() {
    var el = $('sec-mail'), box = $('mail'), m = S.mail;
    if (!el || !box) return;
    el.hidden = POP == null && hiddenSec('mail', {});
    mailSettle(); mailCardSettle();
    if (el.hidden) return;
    var o;
    if (!S.db) o = S.live === 'off' ? '<div class="none">Email works on the page served from your computer.</div>' : '';
    else {
      if (!m.started) { m.started = true; mailLoad(false, true); }
      o = m.hosted ? '<div class="none">Email works on the page served from your computer.</div>' : m.open != null ? mailThreadHtml() : mailTopHtml() + '<div class="mail-body">' + mailTreeHtml() + '<div class="mail-div" role="separator" aria-orientation="vertical" tabindex="0" aria-label="Resize the mailbox column: drag it, or press Left and Right" aria-valuemin="' + MW_MIN + '" aria-valuemax="' + MW_MAX + '" aria-valuenow="' + mailWidth() + '"></div><div class="mail-col">' + mailBulkHtml() + mailListHtml() + '</div></div>';
    }
    setHtml(box, o);
    var mb = box.querySelector('.mail-body');      /* the column width set here: the site's rules ignore a style written into the markup */
    if (mb) mb.style.setProperty('--mail-w', mailWidth() + 'px');
    if (box.style) box.style.minHeight = m.open != null ? m.hold : '';
    if (box.querySelectorAll) [].forEach.call(box.querySelectorAll('iframe.mail-html'), function (f) {
      var k = f.getAttribute('data-fk');
      if (m.fh[k] && !f.style.height) f.style.height = m.fh[k] + 'px';       /* a redraw keeps the email's height until it has loaded */
    });
  }
  /* An email shown as sent is as tall as its content: measured when its frame has loaded, and again when its width changes. */
  function mailFit(f) {
    try {
      var d = f.contentDocument, b = d && d.body;
      if (!b) return;
      var fit = function () { var px = b.scrollHeight; if (px) { f.style.height = px + 'px'; S.mail.fh[f.getAttribute('data-fk')] = px; } };
      fit();
      if (window.ResizeObserver) new ResizeObserver(fit).observe(b);
    } catch (e) {}
  }
  if (document.addEventListener) document.addEventListener('load', function (e) { var f = e.target; if (f && f.tagName === 'IFRAME' && f.classList.contains('mail-html')) mailFit(f); }, true);
  function mailClick(a, b) {
    var m = S.mail, raw = b.getAttribute('data-id'), id = raw == null ? null : mailId(raw);
    if (a === 'mail-open') { mailOpen(id); return true; }
    if (a === 'mail-back') { mailBack(); return true; }
    if (a === 'mail-pop') { mailPop(id); return true; }
    if (a === 'mail-close') { window.close(); return true; }
    if (a === 'mail-shut') { var fa = b.getAttribute('data-acct'); mailFoldSet(fa, !mailFolds()[fa]); render(); return true; }     /* the title only opens and closes its folders */
    if (a === 'mail-attview') { attView(b); return true; }
    if (a === 'mail-pics') { m.pics[id] = 1; render(); return true; }
    if (a === 'mail-older') { mailLoad(true); return true; }
    if (a === 'mail-search') { mailSearch(false); return true; }
    if (a === 'mail-deep') { mailSearch(true); return true; }
    if (a === 'mail-refresh') { mailReload(); return true; }
    if (a === 'mail-new') { mailDraftPress(null, 'new'); return true; }
    if (a === 'mail-draft') { mailDraftPress(id, b.getAttribute('data-t')); return true; }
    if (a === 'mail-act') { mailPress(id, b.getAttribute('data-act')); return true; }
    if (a === 'mail-card') { if (id === 'bulk') { mailCard(mailSelIds().map(mailId), true); m.sel = {}; render(); } else mailCard([id], false); return true; }
    if (a === 'mail-undo') { mailUndo(b.getAttribute('data-key')); return true; }
    if (a === 'mail-unsub') { mailUnsubPress(id, b.getAttribute('data-via') || 'auto'); return true; }
    if (a === 'mail-unsub-ask') { mailX().askUnsub[id] = true; render(); return true; }
    if (a === 'mail-unsub-no') { delete mailX().askUnsub[id]; render(); return true; }
    if (a === 'mail-bulk-unsub') { mailBulkUnsub(); return true; }
    if (a === 'mail-del-ask') { m.askDel[id] = true; render(); return true; }
    if (a === 'mail-del-no') { delete m.askDel[id]; render(); return true; }
    if (a === 'mail-del-go') { mailPress(id, 'trash'); return true; }
    if (a === 'mail-label-open') {
      var lm = ((m.thread && m.thread.messages) || []).filter(function (x) { return x.id === id; })[0];
      m.lab[id] = true; render(); var lf = $('mlab-' + id); if (lf) lf.focus();
      if (lm) mailLabels(lm.account);
      return true;
    }
    if (a === 'mail-label-no') { delete m.lab[id]; render(); return true; }
    if (a === 'mail-label-go') {
      var inp = $('mlab-' + id), name = inp ? String(inp.value || '').trim() : '';
      if (!name) { toast('Choose a label or type a name first.', ''); return true; }
      mailPress(id, 'label', name); return true;
    }
    if (a === 'mail-sel') { m.sel[id] = b.checked; render(); mailUnsubFetch(mailSelIds().map(mailId)); return true; }
    if (a === 'mail-sel-all') { m.sel = {}; if (b.checked) m.rows.forEach(function (r) { m.sel[r.id] = true; }); render(); mailUnsubFetch(mailSelIds().map(mailId)); return true; }
    if (a === 'mail-sel-none') { m.sel = {}; m.askBulk = false; m.mv = {}; m.snz = {}; render(); return true; }
    if (a === 'mail-star') {
      var sr = m.rows.filter(function (x) { return x.id === id; })[0];
      if (sr) mailPress(id, sr.starred ? 'unstar' : 'star');
      return true;
    }
    if (a === 'mail-bulk') { mailBulk(b.getAttribute('data-act')); return true; }
    if (a === 'mail-bulk-del-ask') { m.askBulk = true; render(); return true; }
    if (a === 'mail-bulk-del-no') { m.askBulk = false; render(); return true; }
    if (a === 'mail-bulk-del-go') { mailBulk('trash'); return true; }
    if (a === 'mail-move-open') { m.mv[id] = true; render(); return true; }
    if (a === 'mail-move-no') { delete m.mv[id]; render(); return true; }
    if (a === 'mail-move-go') {
      var mv = $('mmove-' + id), dest = mv ? mv.value : '';
      if (!dest) { toast('Choose a folder first.', ''); return true; }
      if (id === 'bulk') mailBulk('move', {folder: dest}); else mailPress(id, 'move', null, {folder: dest});
      return true;
    }
    if (a === 'mail-snooze-open') { m.snz[id] = true; render(); return true; }
    if (a === 'mail-snooze-no') { delete m.snz[id]; render(); return true; }
    if (a === 'mail-snooze') {
      var dd = $('msd-' + id), at = mailSnoozeAt(b.getAttribute('data-when'), dd ? dd.value : '');
      if (!at) { toast('Choose a time that has not passed.', ''); return true; }
      if (id === 'bulk') mailBulk('snooze', {until: at}); else mailPress(id, 'snooze', null, {until: at, all: true});
      return true;
    }
    if (a === 'mail-unsnooze') { mailPress(id, 'unsnooze', null, {all: true}); return true; }
    if (a === 'mail-folder') {
      mailFoldSet(b.getAttribute('data-acct'), false);
      m.account = b.getAttribute('data-acct'); m.folder = b.getAttribute('data-fid') || ''; m.view = m.folder ? 'folder' : 'inbox';
      m.deep = false; m.sel = {}; mailLoad(false); return true;
    }
    if (a === 'mail-unlabel') { mailPress(id, 'unlabel', b.getAttribute('data-label')); return true; }
    return false;
  }
  /* the address and view boxes: choosing one lists again */
  function mailPick(t) {
    var m = S.mail;
    if (t.id === 'mail-acct') { m.account = t.value; if (m.view === 'folder') m.view = 'inbox'; } else m.view = t.value;
    if (m.view !== 'folder') m.folder = '';
    m.deep = false; m.sel = {};
    mailLoad(false);
  }

  /* ---- chat look: round avatars, relative times, bundles of messages, date lines ---- */
  var CP_USER = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 12a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9zm0 2c-3.6 0-8 1.8-8 5v2h16v-2c0-3.2-4.4-5-8-5z"/></svg>';
  var CP_SEND = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 20.5v-6.8l9-1.7-9-1.7V3.5L22 12z"/></svg>';
  var CP_PIN = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="currentColor"><path d="M16 3v2l-1 1v5l2.5 3v2H12.8v5h-1.6v-5H6.5v-2L9 11V6L8 5V3z"/></svg>';
  function cpHue(name) { var n = 0, t = String(name || ''), i; for (i = 0; i < t.length; i++) n = (n * 31 + t.charCodeAt(i)) % 8; return n; }
  function cpInitials(name) {
    var t = String(name || '').trim();
    if (/^#/.test(t)) return '#';
    if (!t || /^[\d\s()+.\-]+$/.test(t)) return '';
    var w = t.split(/[\s,._-]+/).filter(function (x) { return /[A-Za-z0-9]/.test(x); });
    if (!w.length) return '';
    return (w[0].charAt(0) + (w.length > 1 ? w[w.length - 1].charAt(0) : '')).toUpperCase();
  }
  /* one face: initials in a colour that belongs to the name; a number gets a plain person; a group is up to three faces stacked */
  function cpAvatar(name, group, small) {
    var one = function (n, cls) { var ini = cpInitials(n); return '<span class="cp-av' + (cls || '') + ' av' + cpHue(n) + '">' + (ini ? h(ini) : CP_USER) + '</span>'; };
    if (group) {
      var ms = String(name || '').split(/,\s*/).filter(Boolean).slice(0, 3);
      if (ms.length > 1) return '<span class="cp-avg">' + ms.map(function (n) { return one(n, ''); }).join('') + '</span>';
    }
    return one(name, small ? ' s' : '');
  }
  /* 7:44 AM today, a short weekday within the last week, then Nov 13 (with the year when it is another year) */
  function cpRel(d) {
    if (!d) return '';
    var n = new Date(), sod = new Date(n.getFullYear(), n.getMonth(), n.getDate()).getTime();
    if (d.getTime() >= sod) return fmtT(d);
    if (d.getTime() >= sod - 6 * 86400000) return ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][d.getDay()];
    return ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][d.getMonth()] + ' ' + d.getDate() + (d.getFullYear() === n.getFullYear() ? '' : ', ' + d.getFullYear());
  }
  /* "Friday, Oct 9 · 7:23 AM" */
  function cpDay(d) {
    var n = new Date();
    return ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][d.getDay()] + ', ' + ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][d.getMonth()] + ' ' + d.getDate() +
      (d.getFullYear() === n.getFullYear() ? '' : ', ' + d.getFullYear()) + ' · ' + fmtT(d);
  }
  /* list: [{k, d: Date or null, who, mine, src, n}] oldest first. A bundle is the same sender within five minutes; a gap of an hour gets a date line. */
  function cpItems(list, build) {
    var out = [];
    list.forEach(function (m, i) {
      var q = list[i - 1];
      m.gap = !q || !m.d || !q.d || m.d - q.d >= 3600000;
      m.sep = !q || q.who !== m.who || m.gap || !m.d || !q.d || m.d - q.d > 300000;
    });
    list.forEach(function (m, i) {
      var nx = list[i + 1];
      m.first = m.sep; m.last = !nx || nx.sep;
    });
    list.forEach(function (m) {
      if (m.gap && m.d) out.push({k: 'd' + m.k, cls: 'cp-day', html: h(cpDay(m.d))});
      out.push({k: m.k, cls: 'cp-m ' + (m.mine ? 'out' : 'in') + (m.first ? ' first' : '') + (m.last ? ' last' : '') + (m.cls ? ' ' + m.cls : ''), html: build(m), n: m.n !== false});
    });
    return out;
  }
  function cpPins(kind) { try { return (JSON.parse(keepGet('pins') || '{}') || {})[kind] || []; } catch (e) { return []; } }
  function cpPinToggle(kind, id) {
    var all; try { all = JSON.parse(keepGet('pins') || '{}') || {}; } catch (e) { all = {}; }
    var l = all[kind] || [], i = l.indexOf(id);
    if (i >= 0) l.splice(i, 1); else l.push(id);
    all[kind] = l; keepSet('pins', JSON.stringify(all));
  }
  function cpRow(o) {
    return '<div class="cp-row' + (o.on ? ' on' : '') + (o.unread ? ' unread' : '') + '" data-a="' + o.act + '" data-id="' + h(o.id) + '" role="button" tabindex="0"' + (o.on ? ' aria-current="true"' : '') + '>' +
      cpAvatar(o.name, o.group) + '<span class="cp-rmain"><span class="cp-rname">' + h(o.name) + '</span>' + (o.snip != null ? '<span class="cp-rsnip">' + h(o.snip) + '</span>' : '') + '</span>' +
      '<span class="cp-rside"><span>' + h(o.time || '') + '</span>' + (o.unread ? '<span class="cp-dot" aria-label="Unread">' + (o.unread > 1 ? o.unread : '') + '</span>' : '') +
      '<button class="cp-pin' + (o.pinned ? ' on' : '') + '" type="button" data-a="cp-pin" data-kind="' + o.kind + '" data-id="' + h(o.id) + '" aria-pressed="' + !!o.pinned + '" aria-label="' + (o.pinned ? 'Unpin ' : 'Pin ') + h(o.name) + '">' + CP_PIN + '</button></span></div>';
  }
  function cpGrow(t) { t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight + 2, 150) + 'px'; }
  /* ---- end chat look ---- */

  /* ---------- Chat panels: the shape of the Texts part (and of a mod's part like it) ----------
     One fixed-height panel each: the list of conversations on the left, the open conversation on the right, each scrolling by
     itself, so the page never changes height and never jumps. The frame is built once; only its parts (bar, list, head,
     messages, writing box) are brought up to date, and only when they changed. Messages are kept one by one under a key: one that
     did not change is not touched, older ones go in above without moving what is being read, new ones go below and, when he is
     reading higher up, wait behind a "new messages" tag. Opening a conversation highlights it at once; the one on show stays,
     with a small loading line, until the new one is ready, and then they swap. */
  var CP = {};
  function cpMake(id, box) {
    var p = CP[id];
    if (p && p.root.parentNode === box) return p;
    box.innerHTML = '<div class="cp" data-cp="' + id + '"><div class="cp-bar"></div><div class="cp-body"><div class="cp-list"><div class="cp-lscroll"></div></div>' +
      '<div class="cp-conv"><div class="cp-head"><button class="btn cp-back" type="button" data-a="cp-back">Back</button><span class="cp-hav"></span><span class="cp-ht"><b class="cp-name"></b><span class="cp-sub"></span></span><span class="cp-load" role="status"></span></div>' +
      '<div class="cp-mwrap"><div class="cp-msgs"><div class="cp-empty"></div><ol class="cp-ol"></ol></div><div class="cp-alt" hidden><div class="cp-alth"></div><ol class="cp-ol"></ol></div>' +
      '<div class="cp-spin" role="status" aria-label="Loading older messages" hidden></div><button class="btn primary cp-new" type="button" data-a="cp-new" hidden></button></div><div class="cp-comp"></div></div></div></div>';
    box._html = null;
    var root = box.firstChild, q = function (c) { return root.querySelector(c); };
    p = CP[id] = {id: id, box: box, root: root, newN: 0, more: false, onOlder: null, altKey: '',
      bar: q('.cp-bar'), lscroll: q('.cp-lscroll'), name: q('.cp-name'), sub: q('.cp-sub'), hav: q('.cp-hav'), spin: q('.cp-spin'), load: q('.cp-load'), msgs: q('.cp-msgs'), empty: q('.cp-empty'), ol: q('.cp-msgs > .cp-ol'),
      alt: q('.cp-alt'), alth: q('.cp-alth'), altol: q('.cp-alt > .cp-ol'), tag: q('.cp-new'), comp: q('.cp-comp')};
    p.msgs.addEventListener('scroll', function () { cpScrolled(p); }, {passive: true});
    return p;
  }
  function cpAtBottom(sc) { return sc.scrollHeight - sc.scrollTop - sc.clientHeight < 48; }
  function cpScrolled(p) {
    var sc = p.msgs;
    if (cpAtBottom(sc)) { p.newN = 0; cpTag(p); }
    if (sc.scrollTop < 120 && p.more && p.onOlder) p.onOlder();
  }
  function cpTag(p) {
    p.tag.hidden = !p.newN;
    p.tag.textContent = p.newN === 1 ? '1 new message' : p.newN + ' new messages';
  }
  /* a part of the panel, set again only when its signature changed; the box he is typing in keeps its place */
  function cpSet(el, sig, html) {
    if (el._sig === sig) return false;
    var ae = document.activeElement, keep = ae && el.contains(ae) && ae.id ? {id: ae.id, a: ae.selectionStart, b: ae.selectionEnd} : null;
    el.innerHTML = html; el._sig = sig;
    [].forEach.call(el.querySelectorAll('.cp-pill textarea'), cpGrow);
    if (keep) { var n2 = $(keep.id); if (n2) { n2.focus({preventScroll: true}); try { n2.setSelectionRange(keep.a, keep.b); } catch (e) { /* not every box has a caret */ } } }
    return true;
  }
  function cpList(p, html) {
    var ls = p.lscroll;
    if (ls._h === html) return;
    var top = ls.scrollTop;
    ls.innerHTML = html; ls._h = html; ls.scrollTop = top;
  }
  /* items: [{k: key, html, cls, n: counts as a message for the tag}], oldest first. o.reset: a different conversation, start over;
     o.bottom: go to the newest; otherwise the view holds still unless he is already at the bottom. */
  function cpSync(p, ol, sc, items, o) {
    o = o || {};
    var kids = ol.children, i, li, have = {}, pageY = window.pageYOffset, atB = cpAtBottom(sc), anchor = null,
        prevLast = kids.length ? kids[kids.length - 1].getAttribute('data-k') : null, act = document.activeElement;
    if (o.reset) { ol.innerHTML = ''; prevLast = null; }
    else for (i = 0; i < kids.length; i++) if (kids[i].className !== 'cp-day' && kids[i].offsetTop + kids[i].offsetHeight > sc.scrollTop) { anchor = {k: kids[i].getAttribute('data-k'), off: kids[i].offsetTop - sc.scrollTop}; break; }       /* a date line can come and go above, so a message is the anchor */
    for (i = 0; i < kids.length; i++) have[kids[i].getAttribute('data-k')] = kids[i];
    items.forEach(function (it, n) {
      li = have[it.k];
      if (li) {
        delete have[it.k];
        if (li._h !== it.html && !(act && li.contains(act))) { li.innerHTML = it.html; li._h = it.html; }
      } else { li = document.createElement('li'); li.setAttribute('data-k', it.k); li.innerHTML = it.html; li._h = it.html; }
      if (li.className !== (it.cls || '')) li.className = it.cls || '';
      if (ol.children[n] !== li) ol.insertBefore(li, ol.children[n] || null);
    });
    Object.keys(have).forEach(function (k) { if (have[k].parentNode === ol) ol.removeChild(have[k]); });
    if (o.bottom || o.reset || atB) sc.scrollTop = sc.scrollHeight;
    else if (anchor) {
      var el = null;
      for (i = 0; i < ol.children.length; i++) if (ol.children[i].getAttribute('data-k') === anchor.k) { el = ol.children[i]; break; }
      if (el) sc.scrollTop = el.offsetTop - anchor.off;
    }
    if (o.count && !o.bottom && !o.reset && !atB && prevLast != null) {
      var at = -1;
      items.forEach(function (it, n) { if (it.k === prevLast) at = n; });
      if (at >= 0) p.newN += items.slice(at + 1).filter(function (it) { return it.n; }).length;
    }
    if (o.count) { if (cpAtBottom(sc)) p.newN = 0; cpTag(p); }
    if (window.pageYOffset !== pageY) window.scrollTo(window.pageXOffset, pageY);
    /* a short first page still has older ones above it: ask for them */
    if (o.count && p.more && p.onOlder && sc.scrollHeight <= sc.clientHeight + 40) setTimeout(p.onOlder, 0);
  }
  /* the layer over the messages (a thread, a search): the conversation under it keeps its place */
  function cpAlt(p, a) {
    if (!a) { if (!p.alt.hidden) { p.alt.hidden = true; p.altol.innerHTML = ''; p.altKey = ''; p.alth._sig = null; } return; }
    p.alt.hidden = false;
    cpSet(p.alth, a.key + a.head, a.head);
    var fresh = p.altKey !== a.key;
    p.altKey = a.key;
    cpSync(p, p.altol, p.alt, a.items, {reset: fresh, bottom: fresh && a.bottom});
    if (fresh && !a.bottom) p.alt.scrollTop = 0;
  }
  function cpHead(p, name, group, glyph) {
    var n = String(name || ''), ms = group ? n.split(/,\s*/).filter(Boolean) : [];
    p.name.textContent = n; p.name.title = n;
    p.sub.textContent = ms.length > 1 ? ms.length + ' people' : '';
    var av = n ? cpAvatar(n, group) : '';
    if (p.hav._h !== av) { p.hav.innerHTML = av; p.hav._h = av; }
  }
  /* whose chat panel it is: its state and how it is drawn again (Texts here; a mod's part registers its own) */
  var CP_OWN = {texts: {state: function () { return S.tx; }, render: function () { renderTexts(); }}};
  function cpClick(a, b) {
    var root = b.closest ? b.closest('.cp') : null, id = root && root.getAttribute('data-cp'), p = CP[id], own = CP_OWN[id];
    if (!p || !own) return false;
    if (a === 'cp-pin') { cpPinToggle(b.getAttribute('data-kind'), b.getAttribute('data-id')); own.render(); return true; }
    if (a === 'cp-back') { own.state().view = 'list'; own.render(); return true; }
    if (a === 'cp-new') { p.newN = 0; cpTag(p); p.msgs.scrollTop = p.msgs.scrollHeight; return true; }
    return false;
  }

  /* ---------- Parts of the page the owner's own mods bring (mods.py page_parts) ----------
     A mod with a part names its script (and stylesheet); the page loads it once and the script registers the part with
     ASSISTANT_PAGE.part({id, title, prefix, render, click, input, change, keydown, tools}). The part is a section like Texts: it has its
     place in the arrangement (at the bottom, before Hidden, until he moves it), the menu and Settings; the page lends it
     its helpers (ASSISTANT_PAGE.lib). One that fails is said in the browser's console; the page goes on. */
  var MODP = {parts: {}, loaded: {}};
  function modParts() { return (S.meta && S.meta.mod_parts) || []; }
  function modKeys() { return modParts().map(function (p) { return p.id; }).filter(function (k) { return !TITLE_ID[k] || /^mp-/.test(TITLE_ID[k]); }); }
  function modLoad() {
    modParts().forEach(function (p) {
      var k = p.mod + ':' + p.mark;
      if (MODP.loaded[k] || (TITLE_ID[p.id] && !/^mp-/.test(TITLE_ID[p.id]))) return;      /* never over one of the page's own parts */
      MODP.loaded[k] = 1;
      if (!$('sec-' + p.id)) {
        var sec = document.createElement('section'); sec.id = 'sec-' + p.id; sec.setAttribute('aria-labelledby', 'mp-' + p.id + '-h');
        sec.innerHTML = '<div class="sec-h" data-fold="' + h(p.id) + '" role="button" tabindex="0" aria-expanded="true"><h2 id="mp-' + h(p.id) + '-h">' + h(p.title) + '</h2><span class="n" id="n-' + h(p.id) + '"></span></div><div id="' + h(p.id) + '"></div>';
        ($('area-bottom') || document.body).appendChild(sec);
        TITLE_ID[p.id] = 'mp-' + p.id + '-h';
      }
      var base = 's/mod/' + encodeURIComponent(p.mod) + '/', v = '?v=' + encodeURIComponent(p.mark);
      if (p.style) { var l = document.createElement('link'); l.rel = 'stylesheet'; l.href = base + encodeURIComponent(p.style) + v; document.head.appendChild(l); }
      var sc = document.createElement('script'); sc.src = base + encodeURIComponent(p.script) + v; document.head.appendChild(sc);
    });
  }
  function modEach(fn) { Object.keys(MODP.parts).forEach(function (id) { try { fn(MODP.parts[id]); } catch (e) { if (window.console) console.error(e); } }); }
  function modFor(a) { var hit = null; modEach(function (p) { if (!hit && p.prefix && String(a).indexOf(p.prefix) === 0) hit = p; }); return hit; }
  function modTitle(nm) { var p = modParts().filter(function (x) { return x.id === nm; })[0]; return p ? p.title : ''; }
  function modTools() { var o = ''; modEach(function (p) { if (p.tools) o += p.tools() || ''; }); return o; }
  window.ASSISTANT_PAGE = {
    part: function (p) { if (p && p.id && modKeys().indexOf(p.id) >= 0) { MODP.parts[p.id] = p; render(); } },
    lib: {h: h, hc: hc, $: $, setHtml: setHtml, render: function () { render(); }, toast: toast, info: infoBtn, fmtDT: fmtDT, fmtT: fmtT, fmtD: fmtD, D: D,
          json: mailJson, enc: mailEnc, csrf: mailCsrf, hiddenSec: hiddenSec, state: function () { return S; },
          cpMake: cpMake, cpSet: cpSet, cpList: cpList, cpHead: cpHead, cpSync: cpSync, cpAlt: cpAlt, cpRow: cpRow, cpPins: cpPins, cpRel: cpRel,
          cpItems: cpItems, cpAvatar: cpAvatar, cpSend: function () { return CP_SEND; }, cpOwn: function (id, o) { CP_OWN[id] = o; }}
  };

  /* ---------- Texts: the owner's texts, read and answered here ----------
     Works on the page served from his computer (the doors /api/texts, /api/texts/thread); every change is a press at the page's
     own door: Send queues the text there and the texts link on his computer (textlink.py) takes it from that queue
     and sends it; the page shows Waiting, Sending, Sent or Failed. Only his own Send press queues a text; what the assistant
     drafts waits in the box below the thread for him to edit and send. Text is only ever shown escaped. */
  function txNew() {
    return {q: '', qd: '', rows: [], more: false, next: '', loaded: false, loading: false, loadingMore: false, err: '', note: '', hosted: false,
            seq: 0, started: false, open: null, shown: '', shownName: '', pendName: '', opening: '', loadSay: '', view: 'list', name: '', thread: null, terr: '', tseq: 0, oseq: 0,
            olderBusy: false, stick: false, text: {}, busy: {}, said: {}, drafts: [], problem: '', fresh: null, newTo: '', tick: 0,
            link: {}, linkOpen: false, linkBusy: false, linkErr: '', linkWatch: 0};
  }
  function txJson(url, body) {
    var go = function (tok) {
      var o = {credentials: 'same-origin', cache: 'no-store'};
      if (body) { o.method = 'POST'; o.headers = {'Content-Type': 'application/json', 'X-Brief-Csrf': tok}; o.body = JSON.stringify(body); }
      return fetch(url, o).then(function (r) {
        if (r.status === 404) return {hosted: true};
        if (!r.ok && r.status !== 403) throw new Error(String(r.status));
        return r.json();
      });
    };
    return body ? mailCsrf().then(go) : go('');
  }
  function txLoad(more, quiet) {
    var t = S.tx, n = ++t.seq;
    if (more) t.loadingMore = true; else t.loading = true;
    t.err = '';
    if (!quiet) render();
    return txJson('api/texts?q=' + mailEnc(t.q) + '&limit=50' + (more && t.next ? '&before=' + mailEnc(t.next) : '')).then(function (j) {
      if (n !== t.seq) return;
      t.loading = t.loadingMore = false;
      if (j.hosted) t.hosted = true;
      else if (j.busy) { t.note = 'Texts are being updated. Trying again.'; setTimeout(function () { if (n === t.seq) txLoad(more, true); }, MAIL_RETRY_MS); }
      else if (j.ok === false) t.err = j.error || 'Your texts could not be listed just now.';
      else { t.note = ''; t.rows = more ? t.rows.concat(j.rows || []) : (j.rows || []); t.more = !!j.more; t.next = j.next || ''; t.loaded = true; t.drafts = j.drafts || []; t.problem = j.problem || ''; txLinkSet(j.link); }
      render();
    }, function () { if (n !== t.seq) return; t.loading = t.loadingMore = false; t.err = 'Your texts could not be reached. Check the connection and try again.'; render(); });
  }
  /* One conversation: o.swap is an open (the one on show stays until this arrives), otherwise the newest page is merged in. */
  function txThread(id, o) {
    o = o || {};
    var t = S.tx, n = o.swap ? ++t.oseq : t.oseq, k = ++t.tseq;
    return txJson('api/texts/thread?id=' + mailEnc(id) + '&limit=50').then(function (j) {
      if (n !== t.oseq || (!o.swap && k !== t.tseq)) return;
      if (j.busy) { setTimeout(function () { if (n === t.oseq) txThread(id, o); }, MAIL_RETRY_MS); return; }
      if (o.swap) { t.opening = ''; t.loadSay = ''; }
      if (j.hosted) t.hosted = true;
      else if (j.ok === false) { if (o.swap) { t.terr = j.error || 'That conversation could not be opened.'; t.open = t.shown || null; } }
      else if (o.swap) {
        t.terr = ''; t.shown = id; t.shownName = j.name || t.pendName; t.thread = j; t.problem = j.problem || ''; t.stick = true; t.fresh = null;
        if (t.text[id] == null && (j.drafts || []).length) t.text[id] = j.drafts[0].text;     /* the assistant's draft fills the box until he changes it */
        t.rows.forEach(function (r) { if (r.id === id) r.unread = 0; });
      } else if (t.shown === id && t.thread) {
        var cur = t.thread, nw = j.messages || [], ix = -1, i;
        if (nw.length) for (i = 0; i < cur.messages.length; i++) if (cur.messages[i].id === nw[0].id) { ix = i; break; }
        if (ix >= 0) { j.messages = cur.messages.slice(0, ix).concat(nw); j.more = cur.more; }
        else if (!nw.length) { j.messages = cur.messages; j.more = cur.more; }
        t.thread = j; t.problem = j.problem || '';
      }
      renderTexts();
    }, function () {
      if (n !== t.oseq) return;
      if (o.swap) { t.opening = ''; t.loadSay = ''; t.terr = 'That conversation could not be opened. Check the connection and try again.'; t.open = t.shown || null; renderTexts(); }
    });
  }
  /* Opening: highlighted at once; the conversation on show stays, with a loading line, until this one has arrived. */
  function txOpen(id) {
    var t = S.tx, r = t.rows.filter(function (x) { return x.id === id; })[0];
    t.open = id; t.fresh = null; t.said = {}; t.terr = ''; t.opening = id; t.pendName = r ? r.name : ''; t.view = 'conv';
    t.loadSay = 'Opening ' + (t.pendName || 'the conversation') + '...'; renderTexts();
    return txThread(id, {swap: true});
  }
  /* Older texts, in pages, as he scrolls up: a longer window of the same conversation, put in above without moving the view. */
  function txOlder() {
    var t = S.tx, th = t.thread, id = t.shown, n = t.oseq;
    if (!th || !th.more || t.olderBusy || t.opening) return;
    t.olderBusy = true; t.loadSay = 'Loading older texts...'; renderTexts();
    txJson('api/texts/thread?id=' + mailEnc(id) + '&limit=' + (th.messages.length + 50)).then(function (j) {
      t.olderBusy = false; t.loadSay = '';
      if (n === t.oseq && t.shown === id && j.ok) t.thread = j;
      renderTexts();
    }, function () { t.olderBusy = false; t.loadSay = ''; renderTexts(); });
  }
  function txSearch() { var t = S.tx, bx = $('tx-q'); if (bx) t.qd = bx.value; t.q = String(t.qd || '').trim(); return txLoad(false); }
  /* Send: the owner's own press. The text, and who it goes to, go to the page's door; the box clears only when it was queued. */
  function txSend(conv) {
    var t = S.tx, key = conv || '', body, box = $('tx-text');
    var text = box ? box.value : (t.text[key] || '');
    if (!String(text).trim()) { toast('Write the text first.', ''); return; }
    if (t.busy[key]) return;
    body = {conv: conv || '', text: text};
    if (!conv) { var to = $('tx-to'); body.to = to ? to.value : t.newTo; }
    t.busy[key] = true; t.said[key] = ''; render();
    txJson('api/texts/send', body).then(function (j) {
      t.busy[key] = false;
      if (j.ok) { delete t.text[key]; var bx = $('tx-text'); if (bx && (bx.getAttribute('data-tx') || '') === key) bx.value = ''; t.stick = true; if (!conv) { t.fresh = null; t.newTo = ''; if (j.conv) txOpen(j.conv); } else txThread(conv); txLoad(false, true); }
      else t.said[key] = j.error || 'That did not go through.';
      render();
    }, function () { t.busy[key] = false; t.said[key] = 'This page couldn\'t send that to me. Check the connection and press Send again.'; render(); });
  }
  function txAct(path, body, then) {
    return txJson(path, body).then(function (j) { if (!j.ok && j.error) toast(j.error, ''); if (then) then(); }, function () { toast('That did not work. Check the connection and try again.', ''); });
  }
  var TX_SAY = {queued: 'Waiting to go', sending: 'Sending through Google Messages', sent: 'Sent', failed: 'Did not go'};
  /* Signing in to Google Messages (the texts link on his computer): steps for a Firefox private window, the request copied as cURL
     pasted here (only this computer's own page takes it), then the emoji to tap on his phone. The state comes from api/texts/link. */
  var TX_SIGNIN = 'accounts.google.com/AccountChooser?continue=https://messages.google.com/web/config';
  function txLinkSet(l) {
    var t = S.tx;
    if (!l || typeof l !== 'object') return;
    t.link = l;
    if (t.backWatch) {                  /* after Take it back now: until texts are connected again, or Google kept it with the browser */
      if (l.state === 'connected') { t.backWatch = 0; t.backErr = ''; toast('Texts are connected again.', ''); }
      else if (Date.now() - t.backWatch > 60000) { t.backWatch = 0; if (l.state === 'browser_open') t.backErr = 'Google kept Messages with the browser. Close Google Messages in your browser and press Take it back now again.'; }
    }
    if (!t.linkWatch) return;           /* from the emoji until texts are connected, or the pairing failed */
    if (l.state === 'connected') { t.linkWatch = 0; t.linkOpen = false; toast('Texts are connected to Google Messages.', ''); }
    else if (l.state !== 'pairing' && l.pair_error) { t.linkWatch = 0; t.linkOpen = true; t.linkErr = l.pair_error; }
    else if (Date.now() - t.linkWatch > 300000) t.linkWatch = 0;
  }
  function txLinkHtml() {
    var t = S.tx, L = t.link || {}, st = L.state || '', o = '';
    if (st === 'pairing' && L.emoji) {
      return '<div class="tx-link" role="status"><h3>Tap this emoji on your phone</h3><p>Google Messages on your phone now shows a few emoji. Tap the one that matches:</p>' +
        '<div class="tx-emoji">' + h(L.emoji) + '</div><p>Keep this page open; it says so here when texts are connected.</p>' +
        '<div class="acts"><button class="btn quiet" type="button" data-a="tx-link-cancel">Stop signing in</button></div></div>';
    }
    if (t.linkWatch && st !== 'pairing') return '<div class="wnote" role="status">Paired with your phone. Connecting to Google Messages; this says so here when texts are connected.</div>';
    if (t.linkOpen) {
      return '<div class="tx-link"><h3>Sign in to Google Messages</h3><ol>' +
        '<li>Open Firefox and press Ctrl+Shift+P. A private window opens.</li>' +
        '<li>In that window, type this address and press Enter: <code>' + h(TX_SIGNIN) + '</code></li>' +
        '<li>Sign in with the Google account that Google Messages on your phone uses. A page of text opens; that is right. Go to no other page in that window.</li>' +
        '<li>Press F12. In the panel that opens, click Network, then load the page again with the F5 key.</li>' +
        '<li>In the list, right-click the line named config. Choose Copy Value, then Copy as cURL (POSIX).</li>' +
        '<li>Click in the box below, press Ctrl+V, then press Hand over the sign-in.</li>' +
        '<li>Close the private window with its X. Do not sign out of Google there: signing out would end this sign-in too.</li>' +
        '<li>An emoji shows here. Tap the same one in Google Messages on your phone.</li></ol>' +
        '<label for="tx-cookies">What you copied</label><textarea id="tx-cookies" autocomplete="off" spellcheck="false" placeholder="Paste here"></textarea>' +
        (t.linkErr ? '<div class="err" role="alert">' + h(t.linkErr) + '</div>' : '') +
        '<div class="acts"><button class="btn primary" type="button" data-a="tx-link-go"' + (t.linkBusy ? ' disabled' : '') + '>' + (t.linkBusy ? 'Signing in' : 'Hand over the sign-in') + '</button>' +
        '<button class="btn quiet" type="button" data-a="tx-link-close">Cancel</button></div></div>';
    }
    if (st === 'signed_out_by_google' || st === 'unpaired' || (st === 'signed_out' && L.signed_in_once)) {
      o += '<div class="acts"><button class="btn primary" type="button" data-a="tx-link-open">Sign in to Google Messages</button></div>';
    } else if (st === 'signed_out') {
      o += '<div class="wnote">Texts can come straight from Google Messages on your phone, with no browser tab open. <button class="link" type="button" data-a="tx-link-open">Sign in to Google Messages</button></div>';
    }
    return o;
  }
  function txLinkPoll() {
    var t = S.tx;
    return txJson('api/texts/link').then(function (j) {
      if (j && j.ok) { txLinkSet(j.link); t.problem = j.problem || ''; S.gmNow = String(j.problem || ''); render(); }
    }, function () {});
  }
  setInterval(function () { var L = S.tx.link || {}; if (S.db && !document.hidden && (L.state === 'pairing' || S.tx.linkWatch || S.tx.backWatch)) txLinkPoll(); }, 3000);
  function txLinkGo() {
    var t = S.tx, box = $('tx-cookies'), v = box ? box.value : '';
    if (!v.trim()) { t.linkErr = 'Paste what you copied first.'; render(); return; }
    t.linkBusy = true; t.linkErr = ''; render();
    txJson('api/texts/link/signin', {cookies: v}).then(function (j) {
      t.linkBusy = false;
      if (j && j.ok) { t.linkOpen = false; t.linkWatch = Date.now(); t.link = {state: 'pairing', emoji: j.emoji || ''}; }
      else if (j && j.hosted) t.linkErr = 'The sign-in could not be reached at this address of your page. Open your page at your computer\'s own address and try again there.';
      else t.linkErr = (j && j.error) || 'That did not go through. Try again.';
      render();
    }, function () { t.linkBusy = false; t.linkErr = 'This page couldn\'t reach me. Check the connection and try again.'; render(); });
  }
  function txBuild(e) {
    var x = e.src, th = S.tx.thread, grp = !!(th && th.group), o = '';
    if (!x.out) o += '<span class="cp-avc">' + (e.last ? cpAvatar(x.who || S.tx.shownName, false, true) : '') + '</span>';
    var md = x.media || [], pics = md.map(function (f) {          /* the text's pictures, from its own door; another file is offered to save */
      var u = 'api/texts/file?id=' + encodeURIComponent(f.id);
      return f.pic ? '<a class="tx-pic" href="' + u + '" target="_blank" rel="noopener"><img src="' + u + '" alt="Picture" loading="lazy"></a>'
                   : '<a class="link" href="' + u + '" download="' + h(f.name || 'file') + '">Save ' + h(f.name || 'the file') + '</a>';
    }).join('');
    var words = md.length && x.text === '[media message, no text]' ? '' : h(x.text);
    o += '<span class="cp-col">' + (!x.out && grp && e.first && x.who ? '<span class="cp-who">' + h(x.who) + '</span>' : '') + '<span class="cp-bub">' + pics + words + '</span>' + (e.last ? '<span class="cp-ts">' + h(fmtT(e.d)) + '</span>' : '') + '</span>';
    return o;
  }
  function txSendBuild(e) {
    var s = e.src, o = '<span class="cp-col"><span class="cp-bub">' + h(s.text) + '</span><span class="cp-ts" role="status">' + h(TX_SAY[s.status] || s.status) + (s.status === 'failed' && s.error ? ': ' + h(s.error) : '') + '</span>';
    if (s.status === 'queued') o += '<span class="cp-acts"><button class="link" type="button" data-a="tx-cancel" data-id="' + h(s.id) + '">Take it back</button></span>';
    if (s.status === 'failed') o += '<span class="cp-acts"><button class="link" type="button" data-a="tx-retry" data-id="' + h(s.id) + '">Put it back in the box</button></span>';
    return o + '</span>';
  }
  function txRowHtml(r) {
    return cpRow({act: 'tx-open', id: r.id, kind: 'texts', name: r.name, group: !!r.group, snip: (r.from_me ? 'You: ' : '') + r.last, time: cpRel(D(r.when)), unread: r.unread, on: r.id === S.tx.open, pinned: cpPins('texts').indexOf(r.id) >= 0});
  }
  function txComposer(conv, can, why) {
    var t = S.tx, key = conv || '', dr = (t.drafts || []).filter(function (d) { return conv ? d.conv === conv : !d.conv; })[0], busy = !!t.busy[key];
    if (!can) return '<div class="wnote">' + h(why) + '</div>';
    return '<div class="tx-comp">' + (dr && t.text[key] === dr.text ? '<div class="wnote">Drafted for you' + (dr.why ? ': ' + h(dr.why) : '') + '. Edit it, then press Send; nothing goes until you do. <button class="link" type="button" data-a="tx-discard" data-id="' + h(dr.id) + '">Discard the draft</button></div>' : '') +
      (conv ? '' : '<label for="tx-to">To (a name from your texts, or a phone number)</label><input type="text" id="tx-to" value="' + h(t.newTo) + '" autocomplete="off">') +

      '<div class="cp-pill"><textarea autocomplete="off" name="box-4" id="tx-text" rows="1" maxlength="3000" data-tx="' + h(key) + '" placeholder="Text message" aria-label="' + (conv ? 'Your text' : 'The text') + '">' + h(t.text[key] != null ? t.text[key] : '') + '</textarea>' +
      '<button class="cp-send" type="button" data-a="tx-send" data-id="' + h(key) + '" aria-label="' + (busy ? 'Sending' : 'Send') + '"' + (busy ? ' disabled' : '') + '>' + CP_SEND + '</button></div>' +
      (t.said[key] ? '<div class="err" role="alert">' + h(t.said[key]) + '</div>' : '') + (conv ? '' : '<div class="acts"><button class="btn quiet" type="button" data-a="tx-newno">Cancel</button></div>') + '</div>';
  }
  function txListHtml() {
    var t = S.tx, o = '', pins = cpPins('texts');
    if (t.rows.length) {
      var rows = t.rows.filter(function (r) { return pins.indexOf(r.id) >= 0; }).concat(t.rows.filter(function (r) { return pins.indexOf(r.id) < 0; }));
      o += rows.map(txRowHtml).join('');
    }
    else if (t.loading && !t.note) o += '<div class="none" role="status">Getting your texts.</div>';
    else if (t.loaded && !t.err) o += '<div class="none">' + (t.q ? 'No text matches that.' : 'No texts yet.') + '</div>';
    if (t.more) o += '<div class="acts"><button class="btn" type="button" data-a="tx-older"' + (t.loadingMore ? ' disabled' : '') + '>' + (t.loadingMore ? 'Getting older texts' : 'Older') + '</button></div>';
    return o;
  }
  function txBarHtml() {
    var t = S.tx, o = '<div class="mail-bar"><input type="search" id="tx-q" value="' + h(t.qd) + '" placeholder="Search your texts: words or a name" aria-label="Search your texts" autocomplete="off">' +
      '<button class="btn" type="button" data-a="tx-search">Search</button><button class="btn primary" type="button" data-a="tx-new">New text</button><button class="btn quiet" type="button" data-a="tx-refresh">Refresh</button></div>';
    if (t.problem) o += '<div class="wnote">' + h(t.problem) + ((t.link || {}).state === 'browser_open' ?
      ' <button class="btn" type="button" data-a="tx-link-back"' + (t.backBusy ? ' disabled' : '') + '>' + (t.backBusy ? 'Taking it back' : 'Take it back now') + '</button>' : '') +
      (t.backErr ? '<span class="err" role="alert"> ' + h(t.backErr) + '</span>' : '') + '</div>';
    o += txLinkHtml();
    var ds = (t.drafts || []).filter(function (d) { return !d.conv; });
    if (ds.length && !t.fresh) o += ds.map(function (d) { return '<div class="wnote">Drafted for you to ' + h(d.to || d.name || 'someone') + ': ' + h(d.text.slice(0, 120)) + ' <button class="link" type="button" data-a="tx-usedraft" data-id="' + h(d.id) + '">Open it</button></div>'; }).join('');
    if (t.note) o += '<div class="wnote" role="status">' + h(t.note) + '</div>';
    if (t.err) o += '<div class="err" role="alert">' + h(t.err) + '</div>';
    if (t.terr) o += '<div class="err" role="alert">' + h(t.terr) + '</div>';
    return o;
  }
  function txItems() {
    var th = S.tx.thread;
    if (!th || th.id !== S.tx.shown) return [];
    var list = th.messages.map(function (m) { return {k: 'm' + m.id, d: D(m.ts), who: m.out ? 'me' : (m.who || 'them'), mine: !!m.out, src: m}; });
    var out = cpItems(list, txBuild);
    (th.sends || []).forEach(function (x) {
      out.push({k: 's' + x.id, cls: 'cp-m out first last pend ' + x.status, html: txSendBuild({src: x}), n: false});
    });
    return out;
  }
  function renderTexts() {
    var el = $('sec-texts'), box = $('texts'), t = S.tx;
    if (!el || !box) return;
    el.hidden = hiddenSec('texts', {});
    if (el.hidden) return;
    var msg = null;
    if (!S.db) msg = S.live === 'off' ? '<div class="none">Texts work on the page served from your computer.</div>' : '';
    else {
      if (!t.started) { t.started = true; txLoad(false, true); }
      if (t.hosted) msg = '<div class="none">Texts work on the page served from your computer.</div>';
    }
    if (msg !== null) { setHtml(box, msg); return; }
    var p = cpMake('texts', box), th = t.thread && t.thread.id === t.shown ? t.thread : null, pageY = window.pageYOffset, key, sig;
    p.root.classList.toggle('cp-open', t.view === 'conv');
    p.root.classList.toggle('cp-wait', !!t.opening);
    cpSet(p.bar, JSON.stringify([t.problem, t.link, !!t.linkWatch, t.linkOpen, t.linkBusy, t.linkErr, !!t.backBusy, t.backErr || '', t.note, t.err, t.terr, !!t.fresh, (t.drafts || []).filter(function (d) { return !d.conv; }).map(function (d) { return [d.id, d.text]; })]), txBarHtml());
    cpList(p, txListHtml());
    cpHead(p, t.fresh ? 'New text' : t.shown ? t.shownName : (t.opening ? t.pendName : ''), !t.fresh && !!(th && th.group));
    p.spin.hidden = !t.olderBusy;
    p.load.textContent = t.loadSay || '';
    p.empty.textContent = !t.shown ? (t.opening ? '' : 'Choose a conversation.') : '';
    p.more = !!(th && th.more); p.onOlder = txOlder;
    key = t.fresh ? '' : th ? th.id : null;
    if (key === null) { cpSet(p.comp, 'n', ''); }
    else {
      var dr = (t.drafts || []).filter(function (d) { return key ? d.conv === key : !d.conv; })[0];
      sig = JSON.stringify([key, !!t.busy[key], t.said[key] || '', th ? !!th.can_send : true, !!(dr && t.text[key] === dr.text)]);
      cpSet(p.comp, sig, key === '' ? txComposer('', true, '') : txComposer(th.id, th.can_send, th.cant_send));
    }
    cpSync(p, p.ol, p.msgs, txItems(), {reset: t.shown && p._shown !== t.shown, bottom: t.stick, count: true});     /* after the writing box, which sets the window's height */
    p._shown = t.shown; t.stick = false;
    if (window.pageYOffset !== pageY) window.scrollTo(window.pageXOffset, pageY);
  }
  function txClick(a, b) {
    var t = S.tx, id = b.getAttribute('data-id');
    if (a === 'tx-open') { txOpen(id); return true; }
    if (a === 'tx-older') { txLoad(true); return true; }
    if (a === 'tx-search') { txSearch(); return true; }
    if (a === 'tx-refresh') { txLoad(false); if (t.shown) txThread(t.shown); return true; }
    if (a === 'tx-new') { t.fresh = true; t.view = 'conv'; renderTexts(); var to = $('tx-to'); if (to) to.focus({preventScroll: true}); return true; }
    if (a === 'tx-newno') { t.fresh = null; renderTexts(); return true; }
    if (a === 'tx-send') { txSend(id); return true; }
    if (a === 'tx-cancel') { txAct('api/texts/cancel', {id: id}, function () { if (t.shown) txThread(t.shown); }); return true; }
    if (a === 'tx-retry') {
      var s = ((t.thread && t.thread.sends) || []).filter(function (x) { return x.id === id; })[0];
      if (s) { t.text[t.shown] = s.text; txAct('api/texts/cancel', {id: id}, function () { if (t.shown) txThread(t.shown); }); }
      return true;
    }
    if (a === 'tx-discard') { delete t.text[t.shown || '']; txAct('api/texts/discard', {id: id}, function () { t.drafts = t.drafts.filter(function (d) { return d.id !== id; }); if (t.thread) t.thread.drafts = []; render(); }); return true; }
    if (a === 'tx-link-open') { t.linkOpen = true; t.linkErr = ''; render(); var c = $('tx-cookies'); if (c) c.focus({preventScroll: true}); return true; }
    if (a === 'tx-link-close') { t.linkOpen = false; t.linkErr = ''; render(); return true; }
    if (a === 'tx-link-go') { txLinkGo(); return true; }
    if (a === 'tx-link-back') {          /* his press: Messages back from the browser now (the 15-minute check would do it later) */
      t.backBusy = true; t.backErr = ''; render();
      txJson('api/texts/link/takeback', {}).then(function (j) {
        t.backBusy = false;
        if (j && j.ok) { t.backWatch = Date.now(); txLinkPoll(); }
        else t.backErr = (j && j.hosted) ? 'Taking it back could not be reached at this address of your page.' : (j && j.error) || 'Google did not hand Messages back just now. Try again.';
        render();
      }, function () { t.backBusy = false; t.backErr = 'This page couldn\'t reach me. Check the connection and try again.'; render(); });
      return true;
    }
    if (a === 'tx-link-cancel') { t.linkWatch = 0; txAct('api/texts/link/cancel', {}, function () { txLinkPoll(); }); t.link = {state: 'signed_out'}; render(); return true; }
    if (a === 'tx-usedraft') {
      var d = (t.drafts || []).filter(function (x) { return x.id === id; })[0];
      if (d) { t.text[''] = d.text; t.newTo = d.to || d.name || ''; t.fresh = true; t.view = 'conv'; renderTexts(); }
      return true;
    }
    return false;
  }
  /* The Google Messages line of the Errors block is asked of this computer every half minute, so it clears as soon as the tab's beats arrive. */
  function gmPoll() {
    if (!S.db || document.hidden) return;
    txJson('api/texts/status').then(function (j) {
      if (j && j.ok) { var was = S.gmNow; S.gmNow = String(j.problem || ''); if (was !== S.gmNow) render(); }
    }, function () {});
  }
  setInterval(gmPoll, 30000); setTimeout(gmPoll, 3000);
  /* kept fresh while the part is shown: a thread with a send waiting every few seconds, otherwise the open conversation about every
     fifteen seconds and the list about every half minute. What he is reading does not move. */
  setInterval(function () {
    var t = S.tx, el = $('sec-texts');
    if (!t.started || document.hidden || !S.db || t.hosted || (el && el.hidden)) return;
    t.tick++;
    var pending = t.thread && (t.thread.sends || []).some(function (s) { return s.status === 'queued' || s.status === 'sending' || s.status === 'sent'; });
    if (t.shown && !t.opening && !t.olderBusy && (pending || t.tick % 3 === 0)) txThread(t.shown);
    if (t.tick % 6 === 0 && !t.q && t.rows.length <= 50) txLoad(false, true);
  }, 5000);

  /* ---------- the direct box: the owner talks to the assistant ---------- */
  var talk = {pending: null, err: '', mode: ''};
  /* Old talk. What was said earlier folds away under "Earlier talk"; "Clear the talk" hides everything said so far on this
     device (kept, not deleted, so Undo brings it back). */
  var TALK_PREV = null;
  function talkCleared() { try { return JSON.parse(keepGet('talkcut') || '[]') || []; } catch (e) { return []; } }
  function turnKey(t) { return t.who + '|' + (t.at || '') + '|' + String(t.text || '').slice(0, 40); }
  function talkClear() {
    var all = ((S.meta && S.meta.chat && S.meta.chat.turns) || []).slice(-12), prev = talkCleared();
    TALK_PREV = prev;
    keepSet('talkcut', JSON.stringify(prev.concat(all.map(turnKey)).slice(-80)));
    renderTalk();
    toast('Cleared the talk on this device. Nothing was deleted.', 'talk', '', {a: 'talk-undo'});
  }
  function talkUndo() { keepSet('talkcut', JSON.stringify(TALK_PREV || [])); hideToast(); renderTalk(); }
  function renderTalk() {
    var turns = ((S.meta && S.meta.chat && S.meta.chat.turns) || []).slice(-12), o = '', p = talk.pending, a = S.ans && S.ans[(p && p.key) || 'chat'];
    if (p) {
      var at = -1;
      turns.forEach(function (t, n) { if (t.who === 'you' && !t.desktop && t.at === p.at) at = n; });
      /* the answer is here: the box's own reply after his words (a Claude app turn landing between them is not it) */
      if (at >= 0 && turns.slice(at + 1).some(function (t) { return t.who === 'assistant' && !t.desktop; })) p = talk.pending = null;
      else if (Date.now() - p.t > 240000) { p = talk.pending = null; talk.err = 'No answer came back. Your words were saved; ask again.'; }
    }
    var cut = talkCleared(), vis = turns.filter(function (t) { return cut.indexOf(turnKey(t)) < 0; });
    var start = !vis.length ? 0 : vis[vis.length - 1].who === 'assistant' && vis.length > 1 && vis[vis.length - 2].who === 'you' ? vis.length - 2 : vis.length - 1;
    var li = function (t) { return '<li class="' + (t.who === 'you' ? 'me' : 'it') + '">' + (t.card && t.card.title ? '<span class="on-card">On the card "' + h(t.card.title) + '": </span>' : '') + (t.desktop ? '<span class="on-card">In the Claude app: </span>' : '') + (t.who === 'you' ? h(t.text) : hc(t.text)) + (t.source ? '<span class="src">Source: ' + h(t.source) + '</span>' : '') + chgUndoHere(t) + scanHtml(t.scan) + '</li>'; };
    var last = vis.slice(start), early = vis.slice(0, start), tools = '', phone = window.innerWidth <= 520;
    /* on a phone the newest exchange folds to one line, "Last talk", and stays shut until a reply is pending or he opens it */
    if (phone && !p && !talk.err && last.length) tools += '<details class="more" data-d="talk-last"' + (S.open['talk-last'] ? ' open' : '') + '><summary>Last talk</summary><div class="inside"><ol class="talk-log">' + last.map(li).join('') + '</ol></div></details>';
    else last.forEach(function (t) { o += li(t); });
    if (early.length) tools += '<details class="more" data-d="talk-earlier"' + (S.open['talk-earlier'] ? ' open' : '') + '><summary>Earlier talk <span class="cnt">' + early.length + '</span></summary><div class="inside"><ol class="talk-log">' + early.map(li).join('') + '</ol></div></details>';
    if (vis.length) tools += '<div class="talk-tools"><button class="link" type="button" data-a="talk-clear">Clear the talk</button><span>Hides what was said so far on this device. Nothing is deleted.</span></div>';
    var more = $('talk-more');
    if (more && more._html !== tools) { more.innerHTML = tools; more._html = tools; }
    if (p) {
      if (!turns.some(function (t) { return t.who === 'you' && t.at === p.at; })) o += '<li class="me">' + h(p.text) + '</li>';
      o += '<li class="it wait">' + (S.listening === false ? 'This page can\'t reach your computer right now. I\'ll answer when it\'s back.'
        : (a && a.at === p.at && a.status === 'working' ? 'Working on it' : 'Sending') + '...') + '</li>';
    }
    if (talk.err) o += '<li class="it wait">' + h(talk.err) + '</li>';
    var el = $('talk-log');
    if (el._html !== o) { el.innerHTML = o; el._html = o; el.scrollTop = el.scrollHeight; }
    $('talk-send').disabled = !!p;
    /* Open in the Claude app: a Claude session in the assistant's folder that shares this talk (claude://code/new, the app's own link) */
    var dl = $('talk-desk'), link = S.meta && S.meta.desk_link;
    if (dl) { dl.parentNode.hidden = !link || window.innerWidth <= 520; if (link && dl.getAttribute('href') !== link) dl.setAttribute('href', link); }
  }
  /* Typed words, and the two go buttons of a change, travel the same way: one answer, on the key "chat" (a change's
     first words on a key of their own, "change:<ms>", so the assistant knows a change is being asked for). */
  function talkPost(text, key, label, box) {
    if (!text || talk.pending) return;
    if (!S.db) { talk.err = 'This page can\'t reach me here. Sign in and open it again.'; renderTalk(); return; }
    var rec = {id: key, action: 'answer', text: text, at: isoLocal(new Date()), device: device, sent: false, status: 'saved', label: label};
    var oc = openCardKey(), oit = oc && find(oc); if (oit && oit.id) rec.open_card = oit.id;      /* "this card" in the box: the card open now */
    talk.pending = {text: text, at: rec.at, t: Date.now(), key: key}; talk.err = '';
    if (box) box.value = '';
    S.ans[key] = rec; S.mine[key] = {rec: rec, t: Date.now(), keep: 900000};
    renderTalk();
    startThink('chat', rec.at, ''); drawLine();
    S.db.setAnswer(key, rec).then(function () {}, function () {
      stopThink('chat'); drawLine();
      delete S.ans[key]; delete S.mine[key];
      talk.pending = null; if (box && !box.value) box.value = text;
      talk.err = 'That did not send. Check the connection and try again.'; renderTalk();
    });
  }
  function sendTalk() {
    var box = $('talk-in'), text = box.value.replace(/^\s+|\s+$/g, ''), change = talk.mode === 'change';
    if (!text || talk.pending) return;
    talk.mode = '';
    talkPost(text, change ? 'change:' + Date.now() : 'chat', change ? 'Change' : 'Direct', box);
    renderChanges();
  }
  $('talk-form').addEventListener('submit', function (e) { e.preventDefault(); sendTalk(); });
  $('talk-in').addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); sendTalk(); } });
  setInterval(function () { if (talk.pending) renderTalk(); }, 5000);
  var rsT = 0;
  window.addEventListener('resize', function () { clearTimeout(rsT); rsT = setTimeout(renderTalk, 250); });

  /* ---------- redrawing without disturbing what he is using ---------- */
  var acting = null;                       /* the card he has just pressed something on: that one is redrawn */
  function busyKeys() {
    var b = {}, a = document.activeElement, hst = a && a.closest && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName) ? a.closest('[data-key]') : null;
    if (hst) b[hst.getAttribute('data-key')] = 1;                                    /* he is typing or picking in it */
    if (acting) delete b[acting];
    return b;
  }
  /* Put new content in a section. Nothing is touched when nothing changed. A card in use is left
     exactly as it is; the cards around it are brought up to date one by one. */
  /* "How your page works": the manual the page server serves at /manual (only when the data says it is there) */
  /* "Add to your phone's home screen": the browser's own install prompt where it offers one, else the steps for that phone */
  var HOME = {prompt: null, shown: false};
  window.addEventListener('beforeinstallprompt', function (ev) { ev.preventDefault(); HOME.prompt = ev; if (S.panel && S.panel.settings) render(); });
  window.addEventListener('appinstalled', function () { HOME.prompt = null; HOME.done = true; render(); });
  function homeKind() {
    var ua = navigator.userAgent || '';
    if ((window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) || navigator.standalone === true) return 'there';
    if (/iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) return 'iphone';
    if (/Android/.test(ua)) return 'android';
    return 'other';
  }
  function homeItem() {
    var k = homeKind(), o = '<li><b>Add to your phone\'s home screen' + infoBtn('Add to your phone\'s home screen', INFO_X.home_screen) + '</b>';
    if (k === 'there' || HOME.done) return o + '<span class="say">This page is already on your home screen.</span></li>';
    if (HOME.prompt) o += '<button class="btn primary" type="button" data-s="home-add">Add it now</button>';
    else o += '<button class="btn" type="button" data-s="home-steps" aria-expanded="' + HOME.shown + '">' + (HOME.shown ? 'Hide the steps' : 'Show me how') + '</button>';
    if (HOME.shown && !HOME.prompt) {
      if (k === 'iphone') o += '<ol><li>Press the Share button (the square with an arrow, at the bottom or top of Safari).</li><li>Press Add to Home Screen.</li><li>Press Add.</li></ol>';
      else if (k === 'android') o += '<ol><li>Press the three dots at the top right of the browser.</li><li>Press Add to Home screen, or Install app.</li><li>Press Add or Install.</li></ol>';
      else o += '<p class="say">Open this page on your phone and press this button there. On a computer, the browser\'s menu may offer Install this page.</p>';
    }
    return o + '</li>';
  }
  /* Rebuild all cards (rebuild.py): saves every open card, then the next pass writes each afresh; Put them back undoes it */
  var REB = {ask: false};
  /* Settings, Mail rules (mail_rules.py): the rules the mail services run on their side, per mailbox, in plain words. A new one
     is checked in words first (Check the rule), then made by his own Save press; Delete asks first. */
  var MR = {data: null, at: 0, loading: false, open: false, form: {}, preview: null, confirm: null, key: '', reload: false, msg: ''};
  var MR_DO = {move: 'move to a folder or label', archive: 'archive it', read: 'mark as read', star: 'star or flag it'};
  function mrLoad() {
    if (MR.loading) return;
    MR.loading = true; MR.at = Date.now();
    mailJson('api/mail/rules').then(function (j) {
      MR.loading = false;
      if (j && j.busy) { setTimeout(function () { mrLoad(); }, 500); return; }
      MR.data = j || {}; render();
    }, function () { MR.loading = false; MR.data = {error: true}; render(); });
  }
  function mrPaths(addr) {
    var acc = ((MR.data && MR.data.accounts) || []).filter(function (x) { return x.address === addr; })[0], p = {};
    ((acc && acc.folders) || []).forEach(function (f) { p[f.id] = f.path; });
    return p;
  }
  function mrWords(r, paths) {
    var w = r.when || {}, t = r.then || {}, when = [], acts = [];
    if (w.from) when.push('from ' + w.from);
    if (w.subject) when.push('subject contains "' + w.subject + '"');
    if (w.to) when.push('sent to ' + w.to);
    if (t.move) acts.push('move to ' + (paths[t.move] || 'a folder'));
    if (t.archive && !t.move) acts.push('archive it');
    if (t.read) acts.push('mark as read');
    if (t.star) acts.push('star it');
    var s = (when.join(' and ') || 'any mail') + ' → ' + (acts.join(' and ') || 'nothing this page shows');
    if (r.enabled === false) s += ' (turned off)';
    return s.charAt(0).toUpperCase() + s.slice(1);
  }
  function mrSaid() {
    var got = MR.key && S.ans[MR.key];
    if (!got) return '';
    var t = got.outcome || got.result || '';
    if (got.status !== 'done' && got.status !== 'failed') return '<p class="say"><b class="working">Working on it</b></p>';
    return '<p class="say"><b class="outcome' + (got.status === 'failed' || /^Not done/.test(t) ? ' bad' : '') + '">' + h(t || (got.status === 'failed' ? 'That did not work.' : 'Done.')) + '</b></p>';
  }
  /* Settings, Mail: how the Mail part behaves on this device (kept in this browser, takes effect at once, no Save needed) */
  function mailDeviceBlock() {
    return sPart('maildevice', 'Email', '<div class="set-name"><label class="check"><input type="checkbox" id="mail-openread"' + (mailOpenRead() ? ' checked' : '') + '> Opening marks read</label>' + infoBtn('Opening marks read', INFO_X.open_marks_read) + '</div>');
  }
  function mailRulesBlock() {
    var got = MR.key && S.ans[MR.key];
    if (MR.reload && MR.data && got && (got.status === 'done' || got.status === 'failed')) { MR.reload = false; MR.data = null; }
    if (!MR.loading && (!MR.data || Date.now() - MR.at > 60000)) mrLoad();
    if (!MR.data) return sPart('mailrules', 'Mail rules', '<p class="say">Loading the rules your mail services run.</p>', INFO_X.mail_rules);
    var d = MR.data, accts = d.accounts || [];
    if (d.hosted || !accts.length) return '';
    if (d.error) return sPart('mailrules', 'Mail rules', '<p class="say">Your mail rules could not be read just now.</p>', INFO_X.mail_rules);
    var writable = accts.filter(function (x) { return x.can_write; }), o = '<p class="say">Outlook rules and Gmail filters run by your mail services. They sort mail as it arrives, even when this computer is off. Nothing changes until you press Save or Yes.</p>';
    accts.forEach(function (x) {
      var kind = x.type === 'google_mail' ? 'Gmail' : 'Outlook';
      o += '<div class="mr-acct"><b>' + h(x.address) + '</b> <span class="say">' + kind + '</span>';
      if (x.error) o += '<p class="say"><b class="outcome bad">' + h(x.error) + '</b></p>';
      else {
        if (x.note) o += '<p class="say">' + h(x.note) + '</p>';
        if (!x.rules.length) o += '<p class="say">No rules yet.</p>';
        o += '<ul class="tools">' + x.rules.map(function (r) {
          var ask = MR.confirm && MR.confirm.id === r.id && MR.confirm.account === x.address, li = '<li><span>' + h(r.words) + '</span>';
          if (r.read_only) li += '<span class="say">Read only here: change it in ' + kind + '.</span>';
          else if (ask) li += '<span class="acts">Delete this rule? It stops working on the service. <button class="btn primary" type="button" data-s="mr-del-go" data-acct="' + h(x.address) + '" data-id="' + h(r.id) + '">Yes, delete it</button> <button class="btn" type="button" data-s="mr-del-no">No</button></span>';
          else if (r.can_delete) li += '<button class="btn" type="button" data-s="mr-del-ask" data-acct="' + h(x.address) + '" data-id="' + h(r.id) + '">Delete</button>';
          return li + '</li>';
        }).join('') + '</ul>';
      }
      o += '</div>';
    });
    if (!writable.length) return sPart('mailrules', 'Mail rules', o, INFO_X.mail_rules);
    if (!MR.open) return sPart('mailrules', 'Mail rules', o + '<p><button class="btn" type="button" data-s="mr-add" aria-expanded="false">Add a rule</button></p>' + mrSaid(), INFO_X.mail_rules);
    var F = MR.form || {}, folderOpts = '';
    writable.forEach(function (x) {
      x.folders.forEach(function (f) {
        var val = x.address + '|' + f.id;
        folderOpts += '<option value="' + h(val) + '"' + (F.folderValue === val ? ' selected' : '') + '>' + h((writable.length > 1 ? x.address + ': ' : '') + f.path) + '</option>';
      });
    });
    o += '<div class="mr-form"><label for="mr-account">Mailbox</label><select id="mr-account">' + writable.map(function (x) {
      return '<option value="' + h(x.address) + '"' + (F.account === x.address ? ' selected' : '') + '>' + h(x.address) + '</option>';
    }).join('') + '</select>' +
      '<label for="mr-from">When mail is from (for Outlook, a full address)</label><input id="mr-from" type="text" autocomplete="off" value="' + h(F.from || '') + '">' +
      '<label for="mr-subject">Or the subject contains</label><input id="mr-subject" type="text" autocomplete="off" value="' + h(F.subject || '') + '">' +
      '<label for="mr-to">Or it is sent to</label><input id="mr-to" type="text" autocomplete="off" value="' + h(F.to || '') + '">' +
      '<label for="mr-do">Then</label><select id="mr-do">' + Object.keys(MR_DO).map(function (k) {
        return '<option value="' + k + '"' + ((F.do || 'move') === k ? ' selected' : '') + '>' + MR_DO[k] + '</option>';
      }).join('') + '</select>' +
      '<p class="say">In Outlook, star means mark as important.</p>' +
      '<label for="mr-folder">Folder or label, for moving mail</label><select id="mr-folder">' + folderOpts + '</select>' +
      '<div class="acts"><button class="btn primary" type="button" data-s="mr-check">Check the rule</button> <button class="btn" type="button" data-s="mr-close">Close</button></div></div>';
    if (MR.msg) o += '<p class="say"><b class="outcome bad">' + h(MR.msg) + '</b></p>';
    if (MR.preview) {
      var p = MR.preview;
      o += '<p class="say">This rule will be: <b>' + h(mrWords({when: p.when, then: p.then, enabled: true}, mrPaths(p.account))) + '</b></p>' +
        '<div class="acts"><button class="btn primary" type="button" data-s="mr-save">Save this rule</button> <button class="btn" type="button" data-s="mr-edit">Change it</button></div>';
    }
    return sPart('mailrules', 'Mail rules', o + mrSaid(), INFO_X.mail_rules);
  }
  function mrClick(a, b) {
    if (a === 'mr-add') { MR.open = true; MR.preview = null; MR.msg = ''; render(); return; }
    if (a === 'mr-close') { MR.open = false; MR.preview = null; MR.msg = ''; render(); return; }
    if (a === 'mr-edit') { MR.preview = null; render(); return; }
    if (a === 'mr-check') {
      var v = function (id) { var el = document.getElementById(id); return el ? String(el.value || '').trim() : ''; };
      var f = {account: v('mr-account'), from: v('mr-from'), subject: v('mr-subject'), to: v('mr-to'), do: v('mr-do') || 'move', folderValue: v('mr-folder')};
      var bar = f.folderValue.indexOf('|'), folderAddr = bar < 0 ? '' : f.folderValue.slice(0, bar), folderId = bar < 0 ? '' : f.folderValue.slice(bar + 1);
      MR.form = f; MR.msg = ''; MR.preview = null;
      if (!f.from && !f.subject && !f.to) MR.msg = 'Give a sender, words in the subject or a recipient, so the rule knows which mail to sort.';
      else if (f.do === 'move' && (!folderId || folderAddr !== f.account)) MR.msg = 'Pick a folder or label in ' + f.account + ' to move mail to.';
      else MR.preview = {account: f.account, do: f.do, folder: f.do === 'move' ? folderId : '', when: {from: f.from, subject: f.subject, to: f.to},
        then: {move: f.do === 'move' ? folderId : null, archive: f.do === 'archive', read: f.do === 'read', star: f.do === 'star'}};
      render(); return;
    }
    if (a === 'mr-save') {
      var p = MR.preview;
      if (!p) return;
      MR.key = 'mail-rule:' + Date.now(); MR.reload = true; MR.preview = null; MR.open = false; MR.form = {};
      chgSend(MR.key, JSON.stringify({mail_rule: {op: 'create', account: p.account, when: p.when, do: p.do, folder: p.folder}}), 'Mail rules', 'Saving the rule');
      render(); return;
    }
    if (a === 'mr-del-ask') { MR.confirm = {account: b.getAttribute('data-acct'), id: b.getAttribute('data-id')}; render(); return; }
    if (a === 'mr-del-no') { MR.confirm = null; render(); return; }
    if (a === 'mr-del-go') {
      MR.key = 'mail-rule:' + Date.now(); MR.reload = true; MR.confirm = null;
      chgSend(MR.key, JSON.stringify({mail_rule: {op: 'delete', account: b.getAttribute('data-acct'), rule: b.getAttribute('data-id')}}), 'Mail rules', 'Deleting the rule');
      render();
    }
  }
  /* Settings, Rule book (rule_book.py): each press on a card that came from a message, beside what the assistant did with it,
     by section, each section folded. Keep marks a row reviewed, Edit sets the right answer (show it or keep it off the page,
     with a note) as his own answer, Retire stops it counting; each is one press sent at once, and its outcome is held here
     until the next update brings the rule book as it now reads. */
  var RB = {did: {}, edit: '', right: 'show', note: ''};
  function rbState(mid) {
    var x = RB.did[mid], got = x && S.ans[x.key];
    if (!x) return null;
    if (!got) return {x: x, st: 'done'};
    var t = got.outcome || got.result || '';
    if (got.status === 'failed' || /^Not done/.test(t)) return {x: x, st: 'bad', text: t || 'That did not work.'};
    return {x: x, st: got.status === 'done' ? 'done' : 'working'};
  }
  function rbItem(r) {
    var m = r.message, z = rbState(m), o = '<li><span class="t">' + h(r.sender || 'Unknown sender') + (r.what ? ': ' + h(r.what) : '') + '</span>' +
      '<span class="src">' + h(fmtD(D(r.at))) + '</span><span class="src">What I did: ' + h(r.did) + '</span>' +
      '<span class="src">' + h(r.you) + (r.note ? ' Note: ' + h(r.note) : '') + '</span>' +
      (r.reviewed && !r.edited ? '<span class="src">Reviewed ' + h(fmtD(D(r.reviewed))) + '.</span>' : '');
    if (z && z.st === 'working') return o + '<span class="said">Saving</span></li>';
    if (z && z.st === 'done' && z.x.op === 'keep' && !r.reviewed) o += '<span class="said">Kept and marked reviewed.</span>';
    if (z && z.st === 'done' && z.x.op === 'edit') o += '<span class="said">Saved as your answer: ' + (z.x.right === 'hide' ? 'hide it' : 'show it') + '.</span>';
    if (z && z.st === 'bad') o += '<span class="said bad">' + h(z.text) + '</span>';
    if (RB.edit === m) return o + '<div class="set-line wraps"><select aria-label="The right answer" data-rbf="right"><option value="show"' + (RB.right === 'hide' ? '' : ' selected') + '>Show it</option>' +
      '<option value="hide"' + (RB.right === 'hide' ? ' selected' : '') + '>Hide it</option></select>' +
      '<input type="text" autocomplete="off" class="nm" aria-label="A note, if you like" data-rbf="note" value="' + h(RB.note) + '" placeholder="A note, if you like" maxlength="300"></div>' +
      '<div class="acts"><button class="btn primary" type="button" data-s="rb-save" data-m="' + h(m) + '">Save</button><button class="btn" type="button" data-s="rb-cancel">Cancel</button></div></li>';
    return o + '<div class="acts"><button class="btn" type="button" data-s="rb-keep" data-m="' + h(m) + '">Keep</button>' +
      '<button class="btn" type="button" data-s="rb-edit" data-m="' + h(m) + '" data-r="' + h(r.right || 'show') + '" data-n="' + h(r.note || '') + '">Edit</button>' +
      '<button class="btn" type="button" data-s="rb-retire" data-m="' + h(m) + '">Don\'t learn from this</button></div></li>';
  }
  function rbBlock() {
    var d = sAll().rule_book, o = '';
    if (!d) return '';
    (d.sections || []).forEach(function (sec) {
      var rows = (sec.rows || []).filter(function (r) { var z = rbState(r.message); return !(z && z.st === 'done' && z.x.op === 'retire'); }), k = 'rb-' + sec.id;
      if (rows.length) o += '<details class="more" data-d="' + h(k) + '"' + (S.open[k] ? ' open' : '') + '><summary>' + h(sec.label) + ' <span class="cnt">' + rows.length + '</span></summary>' +
        '<div class="inside"><ul class="rows">' + rows.map(rbItem).join('') + '</ul></div></details>';
    });
    if (!o) return sPart('rulebook', 'Rule book', '<p class="say">Nothing yet. The rule book fills as you use your cards.</p>' + freshLine(), d.explain);
    return sPart('rulebook', 'Rule book', '<p class="say">Your answers on cards, beside what I did. Open a group to review it.</p>' + o +
      (d.more ? '<p class="say">' + (d.more === 1 ? '1 older entry' : d.more + ' older entries') + ' not shown here.</p>' : '') + freshLine(), d.explain);
  }
  /* Settings, Contacts (contacts_book.py): everyone he wrote to or heard from, one-time senders included, and his address books;
     each folded, with last in touch and how often, open matters both ways, history, his notes (Save sends them at once) and
     what the assistant learned. A search narrows the list; the newest contacts show first. */
  var CT = {q: '', notes: {}, did: {}, rows: [], total: 0, loaded: false, loading: false, err: '', seq: 0, hosted: false};
  /* the people come a page at a time from this computer when Contacts is drawn (api/contacts), never in one block */
  function ctLoad(more) {
    if (CT.loading) return;
    var n = ++CT.seq, off = more ? CT.rows.length : 0;
    CT.loading = true; CT.err = '';
    mailJson('api/contacts?q=' + encodeURIComponent(CT.q || '') + '&offset=' + off + '&limit=50').then(function (j) {
      if (n !== CT.seq) return;
      CT.loading = false;
      if (j.hosted) { CT.hosted = true; CT.loaded = true; }
      else if (j.busy) { setTimeout(function () { if (n === CT.seq) ctLoad(more); }, 3000); }
      else { CT.rows = more ? CT.rows.concat(j.people || []) : (j.people || []); CT.total = j.total || 0; CT.loaded = true; }
      render();
    }, function () { if (n !== CT.seq) return; CT.loading = false; CT.err = 'Your contacts could not be reached just now.'; render(); });
  }
  function ctItem(p) {
    var k = 'ct-' + p.person, om = p.open_matters || {}, hi = p.history || {}, a = CT.did[p.person] && S.ans[CT.did[p.person]];
    var list = function (rows, f) { return rows && rows.length ? '<ul class="rows">' + rows.map(function (r) { return '<li><span class="src">' + f(r) + '</span></li>'; }).join('') + '</ul>' : '<p class="say">None.</p>'; };
    var o = '<p class="say">' + h((p.addresses || []).join(', ')) + '</p>' +
      '<p class="say">From: ' + h((p.where || []).join(', ')) + (p.one_time ? '. One-time sender.' : '') + '</p>' +
      '<p class="say">Last in touch: ' + (p.last_in_touch ? h(fmtD(D(p.last_in_touch))) : 'not yet') + '. ' + h(p.how_often || '') + '</p>' +
      '<p class="say"><b>Open, waiting on you</b></p>' + list(om.yours, function (r) { return h(r.title); }) +
      '<p class="say"><b>Open, waiting on them</b></p>' + list(om.theirs, function (r) { return h(r.title); }) +
      '<p class="say"><b>Messages</b></p>' + list(hi.messages, function (r) { return h(fmtD(D(r.at))) + ', ' + h(r.way) + ' (' + h(r.channel) + '): ' + h(r.what); }) +
      '<p class="say"><b>Cards</b></p>' + list(hi.cards, function (r) { return h(r.title) + ' (' + h(r.state) + ')'; }) +
      '<p class="say"><b>Your decisions</b></p>' + list(hi.decisions, function (r) { return h(fmtD(D(r.at))) + ': ' + h(r.press) + (r.happened ? '. ' + h(r.happened) : ''); }) +
      '<p class="say"><b>What I learned</b> ' + h(p.learned || 'Nothing yet.') + '</p>' +
      '<div class="set-line wraps"><textarea class="nm" rows="3" maxlength="2000" aria-label="Your notes on ' + h(p.name) + '" placeholder="Your notes" data-ctn="' + h(p.person) + '">' +
      h(CT.notes[p.person] != null ? CT.notes[p.person] : p.notes || '') + '</textarea></div>' +
      '<div class="acts"><button class="btn" type="button" data-s="ct-save" data-p="' + h(p.person) + '">Save notes</button>' +
      (a ? '<span class="said">' + h(a.result || (a.status === 'failed' ? 'That did not save.' : 'Saving')) + '</span>' : '') + '</div>';
    return '<details class="more" data-d="' + h(k) + '"' + (S.open[k] ? ' open' : '') + '><summary>' + h(p.name) +
      ' <span class="cnt">' + (p.last_in_touch ? h(fmtD(D(p.last_in_touch))) : '') + '</span></summary><div class="inside">' + (S.open[k] ? o : '') + '</div></details>';
  }
  function ctBlock() {
    var d = sAll().contacts;
    if (!d) return '';
    if (!CT.loaded && !CT.loading && !CT.err && (SET.nav || [])[0] === 'people') setTimeout(function () { ctLoad(false); }, 0);
    var body = CT.hosted ? '<p class="say">Contacts open on your page at your own computer.</p>' :
      CT.err ? '<p class="say">' + h(CT.err) + '</p>' : !CT.loaded ? '<p class="say">Loading your contacts.</p>' :
      CT.rows.map(ctItem).join('') + (CT.rows.length < CT.total ? '<div class="acts"><button class="btn" type="button" data-s="ct-more"' + (CT.loading ? ' disabled' : '') + '>Show more (' + (CT.total - CT.rows.length) + ' left)</button></div>' : '');
    return sPart('contacts', 'Contacts', '<p class="say">' + plural(d.count || 0, 'contact') + '. Open one to see its history and your notes.</p>' +
      '<div class="set-line"><input type="search" class="nm" autocomplete="off" aria-label="Find a contact" placeholder="Find a contact" data-ctq="1" value="' + h(CT.q) + '"></div>' +
      body, d.explain);
  }
  function ctClick(a, b) {
    if (a === 'ct-more') { ctLoad(true); render(); return; }
    if (a !== 'ct-save') return;
    var pid = b.getAttribute('data-p'), key = 'contact-note:' + Date.now(), words = CT.notes[pid] != null ? CT.notes[pid] : '';
    if (!chgSend(key, JSON.stringify({contact_note: {person: pid, notes: String(words).slice(0, 2000)}}), 'Contacts', 'Saving your notes')) return;
    CT.did[pid] = key;
    render();
  }
  /* Start fresh (start_fresh.py): asks first; only Yes sends the press, carrying the confirm the engine checks for. Nothing is
     deleted by this page; the computer deletes his own rules and lists and says what it did. */
  var FRESH = {ask: false};
  function freshLine() {
    var a = S.ans && S.ans['start-fresh'], o = '<p class="say"><b>Start fresh</b> Deletes your own rules and lists, so I learn them again from your cards.</p>';
    if (FRESH.ask) o += '<p class="say">This deletes your own rules and lists. The built-in rules, the rule book and your cards stay. Continue?</p>' +
      '<div class="acts"><button class="btn primary" type="button" data-s="fresh-go">Yes, start fresh</button><button class="btn" type="button" data-s="fresh-no">No</button></div>';
    else o += '<div class="acts"><button class="btn" type="button" data-s="fresh-ask">Start fresh</button></div>';
    if (a && a.result) o += '<p class="say">' + h(a.result) + '</p>';
    else if (a && a.status === 'saved') o += '<p class="say">Sent to your computer.</p>';
    return o;
  }
  function rbClick(a, b) {
    var m = b.getAttribute('data-m');
    if (a === 'rb-edit') { RB.edit = m; RB.right = b.getAttribute('data-r') === 'hide' ? 'hide' : 'show'; RB.note = b.getAttribute('data-n') || ''; render(); return; }
    if (a === 'rb-cancel') { RB.edit = ''; render(); return; }
    if (a !== 'rb-keep' && a !== 'rb-retire' && a !== 'rb-save') return;
    var op = a === 'rb-save' ? 'edit' : a.slice(3), body = {op: op, message: m}, key = 'rule-book:' + Date.now();
    if (op === 'edit') { body.right = RB.right === 'hide' ? 'hide' : 'show'; body.note = String(RB.note || '').replace(/\s+/g, ' ').trim().slice(0, 300); }
    if (!chgSend(key, JSON.stringify({rule_book: body}), 'Rule book', op === 'keep' ? 'Keeping it' : op === 'retire' ? 'Leaving it out of what I learn from' : 'Saving your answer')) return;
    RB.did[m] = {op: op, key: key, right: body.right};
    if (op === 'edit') RB.edit = '';
    render();
  }
  /* Settings, Tools: each tool in plain words, with Start. Start opens its walk-through in Talk to your assistant at the top of the page, the way
     Update starts there from its card; the list comes from the engine (tools.py), so a new tool is one more entry there. */
  function toolsBlock() {
    var list = (S.meta && S.meta.tools) || [], plist = (S.meta && S.meta.ptools) || [];
    return sPart('tools', 'Tools', '<p class="say">Most run in Talk to your assistant at the top of the page, one question at a time. Nothing changes until you say so.</p>' +
      '<ul class="tools">' + list.map(function (t) {
        return '<li><b>' + h(t.name) + infoBtn(t.name, t.explain) + '</b><span class="say">' + h(t.words) + '</span><button class="btn" type="button" data-s="tool-start" data-t="' + h(t.id) + '" aria-label="Start ' + h(t.name) + '">Start</button></li>';
      }).join('') + plist.map(ptItem).join('') + cmdItems() + modTools() + reloadItem() + rebuildItem() + homeItem() + '</ul>');
  }
  /* Reload all email history (mail.py reload_history): asks once, then each pass reads every mailbox's whole history a portion
     at a time; how far each mailbox has got shows here. */
  var RLD = {ask: false};
  function reloadItem() {
    var a = S.ans && S.ans['mail-reload'], st = (S.meta && S.meta.mail_reload) || [];
    var o = '<li><b>Reload all email history' + infoBtn('Reload all email history', INFO_X.reload_mail) + '</b><span class="say">Rereads the whole history of every Gmail and Microsoft mailbox, a portion at each check. Stored email is kept, never deleted.</span>';
    if (RLD.ask) o += '<span class="say">Reload the whole history of every mailbox now?</span><button class="btn primary" type="button" data-s="rld-go">Yes, reload it</button> <button class="btn" type="button" data-s="rld-no">No</button>';
    else o += '<button class="btn" type="button" data-s="rld-ask">Start</button>';
    if (a && a.result) o += '<span class="say">' + h(a.result) + '</span>';
    else if (a && a.status === 'saved') o += '<span class="say">Sent to your computer.</span>';
    st.forEach(function (x) { o += '<span class="say">' + h(x.account) + ': ' + h(x.line) + '</span>'; });
    return o + '</li>';
  }
  /* The four project tools (project_tools.py): Add or Remove the roadmap or the questions file in one of the owner's projects.
     Pressing one lists the projects, each with whether the tool is on there. Add asks that project's own Claude session, which
     sets it up once he says yes there; if no session can be asked, the command to type in the project is shown, with Copy.
     Remove asks him here first, then turns it off from here (a roadmap's own files are deleted; a questions file is kept). */
  var PT = {pick: '', proj: '', confirm: null, key: {}, err: ''};
  function ptAns(t) { var k = PT.key[t.id]; return k ? S.ans[k] : null; }
  function ptCmd(t) {
    return '<div class="pt-cmd"><span>Type this in that project\'s Claude session:</span><code>' + h(t.command) + '</code>' +
      '<button class="btn" type="button" data-s="pt-copy" data-c="' + h(t.command) + '" aria-label="Copy ' + h(t.command) + '">Copy</button></div>';
  }
  function ptResult(t) {
    var a = ptAns(t), said = a && (a.outcome || a.result);
    if (!a) return PT.err && PT.pick === t.id ? '<p class="say" role="alert"><b class="outcome bad">' + h(PT.err) + '</b></p>' : '';
    if (a.status === 'failed') return '<p class="say"><b class="outcome bad">' + h(said || 'That did not work.') + '</b></p>';
    if (a.status === 'done') {
      var miss = /^Not sent/.test(String(said || ''));
      return '<p class="say"><b class="outcome' + (miss || /^Not done/.test(String(said || '')) ? ' bad' : '') + '">' + h(String(said || 'Done').replace(/,? ?(In that project's Claude session, )?type \/assistant:[a-z-]+$/, '')) + '</b></p>' + (miss ? ptCmd(t) : '');
    }
    return '<p class="say"><b class="working">' + (t.op === 'add' ? 'Asking that project\'s Claude session' : 'Turning it off') + '</b></p>' +
      (S.listening === false ? '<p class="say">This page can\'t reach your computer, so nothing has been sent yet.</p>' + (t.op === 'add' ? ptCmd(t) : '') : '');
  }
  var PT_GUIDE = {roadmap: 'Pick the project\'s top session, the one that oversees the work. A roadmap follows the whole project, including the sessions started from it.',
                  questions: 'Pick the session you\'re talking with. A questions file keeps that one session\'s questions.'};
  function ptSessions(t, pr) {
    var list = pr.sessions || [], o = '<p class="say"><b>' + h(pr.name) + '</b> <button class="btn quiet" type="button" data-s="pt-back">Choose another project</button></p>' +
      '<p class="say">' + h(PT_GUIDE[t.tool]) + '</p>';
    if (!list.length) return o + '<p class="say">No session is open in this project.</p>' + (t.op === 'add' ? ptCmd(t) : '');
    list.forEach(function (x) {
      var dead = t.op === 'add' ? (t.tool === 'questions' && x.has) : !x.has, d = D(x.at);
      o += '<div class="pt-row"><span><b>' + h(x.name) + '</b><br><span class="where">' + (d ? 'Last active ' + h(fmtDT(d)) : 'Last active unknown') +
        (x.child ? ' &middot; started from another session' : ' &middot; top session') + (x.has ? ' &middot; has the questions file' : '') + '</span></span>' +
        '<button class="btn' + (dead ? ' quiet' : '') + '" type="button"' + (dead ? ' disabled' : '') + ' data-s="pt-go" data-t="' + h(t.id) + '" data-f="' + h(pr.folder) + '" data-x="' + h(x.id) + '" aria-label="' +
        (t.op === 'add' ? 'Add to ' : 'Remove from ') + h(x.name) + '">' + (dead ? (t.op === 'add' ? 'Already has it' : 'None here') : t.op === 'add' ? 'Add' : 'Remove') + '</button></div>';
    });
    return o;
  }
  function ptPick(t) {
    var projs = (S.meta && S.meta.projects) || [], o = '', ask = t.tool === 'roadmap' && t.op === 'remove' ? '' : 'x';
    if (!projs.length) return '<p class="say">I don\'t know any of your projects yet.</p>' + (t.op === 'add' ? ptCmd(t) : '');
    var chosen = ask && PT.proj ? projs.filter(function (p) { return p.folder === PT.proj; })[0] : null;
    if (chosen) o += ptSessions(t, chosen);
    else {
      o += '<p class="say"><b>' + (t.op === 'add' ? 'Which project?' : 'Which project, to turn it off?') + '</b></p>';
      projs.forEach(function (p) {
        var on = !!p[t.tool], dead = t.tool === 'roadmap' ? (t.op === 'add' ? on : !on) : (t.op === 'remove' && !on);
        var label = dead ? 'Already ' + (t.op === 'add' ? 'on' : 'off') : ask ? 'Choose' : 'Remove', what = t.tool === 'roadmap' ? 'roadmap' : 'questions file';
        o += '<div class="pt-row"><span><b>' + h(p.name) + '</b><br><span class="where">' + h(p.folder) + '</span><br><span class="say">Roadmap: ' + (p.roadmap ? 'on' : 'off') + ' &middot; Questions file: ' + (p.questions ? 'on' : 'off') + '</span></span>' +
          '<button class="btn' + (dead ? ' quiet' : '') + '" type="button"' + (dead ? ' disabled' : '') + ' data-s="' + (ask ? 'pt-proj' : 'pt-go') + '" data-t="' + h(t.id) + '" data-f="' + h(p.folder) + '" aria-label="' +
          (ask ? 'Choose a session in ' : 'Remove ' + what + ' from ') + h(p.name) + '">' + label + '</button></div>';
      });
    }
    if (PT.confirm && t.op === 'remove') {
      var pr = projs.filter(function (p) { return p.folder === PT.confirm.f; })[0], nm = pr ? pr.name : PT.confirm.f;
      o += '<p class="say" role="alert"><b>' + (t.tool === 'roadmap' ? 'Turn the roadmap off in ' + h(nm) + '? Its page stays as a record.' : 'Turn the questions file off in ' + h(nm) + '? Its file stays as it is.') + '</b></p>' +
        '<div><button class="btn primary" type="button" data-s="pt-yes" data-t="' + h(t.id) + '">Yes, turn it off</button> <button class="btn" type="button" data-s="pt-no">No</button></div>';
    }
    return o + ptResult(t);
  }
  function ptItem(t) {
    var open = PT.pick === t.id;
    return '<li><b>' + h(t.name) + infoBtn(t.name, t.explain) + '</b><span class="say">' + h(t.words) + '</span><button class="btn" type="button" data-s="pt-open" data-t="' + h(t.id) + '" aria-expanded="' + open + '" aria-label="' + (open ? 'Close ' : 'Choose a project for ') + h(t.name) + '">' + (open ? 'Close' : 'Choose project') + '</button>' +
      (open ? '<div class="pt-pick">' + ptPick(t) + '</div>' : (ptAns(t) ? '<div class="pt-pick">' + ptResult(t) + '</div>' : '')) + '</li>';
  }
  function ptSend(t, folder, session) {
    var key = 'pt:' + t.op + '-' + t.tool + ':' + Date.now();
    if (!S.db) { PT.err = 'This page can\'t reach me here. Sign in and open it again.'; render(); return; }
    var words = {folder: folder}; if (session) words.session = session;
    var rec = {id: key, action: 'answer', label: t.name, text: JSON.stringify(words), at: isoLocal(new Date()), device: device, sent: false, status: 'saved'};
    S.ans[key] = rec; S.mine[key] = {rec: rec, t: Date.now(), keep: 900000}; PT.key[t.id] = key; PT.confirm = null; PT.err = '';
    S.db.setAnswer(key, rec).then(function () {}, function () {
      delete S.ans[key]; delete S.mine[key]; delete PT.key[t.id]; PT.err = 'That did not send. Check the connection and try again.'; render();
    });
    render();
  }
  function ptCopy(text, btn) {
    var done = function () { if (btn) { btn.textContent = 'Copied'; setTimeout(function () { btn.textContent = 'Copy'; }, 1800); } };
    try { if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(text).then(done, function () { ptCopyOld(text, done); }); return; } } catch (e) {}
    ptCopyOld(text, done);
  }
  function ptCopyOld(text, done) {
    var ta = document.createElement('textarea'); ta.value = text; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); done(); } catch (e) {} document.body.removeChild(ta);
  }
  function rebuildItem() {
    var a = S.ans && S.ans.rebuild, o = '<li><b>Rebuild all cards' + infoBtn('Rebuild all cards', INFO_X.rebuild_cards) + '</b>' +
      '<span class="say">I rewrite every open card with your current rules the next time I check for messages. Your answers and snooze dates stay, and I save every card first.</span>';
    if (REB.ask) o += '<span class="say">Rebuild all your open cards now?</span><button class="btn primary" type="button" data-s="reb-go">Yes, rebuild them</button> <button class="btn" type="button" data-s="reb-no">No</button>';
    else o += '<button class="btn" type="button" data-s="reb-ask">Rebuild all cards</button> <button class="btn quiet" type="button" data-s="reb-back">Put them back</button>';
    var rb = S.meta && S.meta.rebuild;
    if (rb && rb.running) o += '<span class="say"><b class="working">Rebuilding your cards now.</b> They refresh on this page when it is done.</span>';
    else if (a && a.result) o += '<span class="say">' + h(a.result) + '</span>';
    else if (a && a.status === 'saved') o += '<span class="say">Sent to your computer.</span>';
    if (rb && !rb.running && rb.done_at) o += '<span class="say">Last rebuilt ' + h(fmtDT(D(rb.done_at))) + (rb.rebuilt != null ? ': ' + rb.rebuilt + ' card' + (rb.rebuilt === 1 ? '' : 's') + ' written afresh.' : '.') + '</span>';
    return o + '</li>';
  }
  function rebuildSend(what) {
    if (!S.db) return;
    var rec = {id: 'rebuild', action: 'answer', label: 'Rebuild all cards', text: JSON.stringify({rebuild: what}), at: isoLocal(new Date()), device: device, sent: false, status: 'saved', result: ''};
    S.db.setAnswer('rebuild', rec).then(function () { render(); }, function () { render(); });
  }
  function manualLink() {
    var m = S.meta && S.meta.manual;
    return m && m.url === '/manual' ? '<a class="btn" href="/manual" target="_blank" rel="noopener">Assistant Manual</a>' + infoBtn('Assistant Manual', INFO_X.manual) : '';
  }
  /* Cards fade away. A card that leaves a list while it is on screen (answered, or gone any other way) fades out where it
     stood (about 300 ms); the cards below it then slide up into its place (about 250 ms) instead of jumping; a card that
     arrives fades in. Similar cards no longer seem to replace each other in the same spot. The system's reduced-motion
     setting turns all of it off. */
  var CARD_SEL = '.card[data-key], li.host[data-key], article.draft[data-key]', FADE_MS = 300, SLIDE_MS = 250, ENTER_MS = 200;
  function motionOn() {
    try { return !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return true; }
  }
  function cardSnap(el) {
    var out = {};
    [].forEach.call(el.querySelectorAll(CARD_SEL), function (n) {
      var k = n.getAttribute('data-key'), r = n.getBoundingClientRect();
      if (!(k in out) && r.height) out[k] = {top: r.top, left: r.left, width: r.width, height: r.height, node: n};
    });
    return out;
  }
  function cardMotion(el, before, drawn) {
    var after = {}, fading = false;
    [].forEach.call(el.querySelectorAll(CARD_SEL), function (n) { var k = n.getAttribute('data-key'); if (!(k in after)) after[k] = n; });
    Object.keys(before).forEach(function (k) {
      if (k in after) return;
      var b = before[k], g = b.node.cloneNode(true), st = g.style;        /* a still copy where it stood, fading out */
      g.removeAttribute('data-key'); g.setAttribute('aria-hidden', 'true'); g.classList.add('card-leaving');
      st.position = 'fixed'; st.top = b.top + 'px'; st.left = b.left + 'px'; st.width = b.width + 'px'; st.height = b.height + 'px';
      st.margin = '0'; st.pointerEvents = 'none'; st.zIndex = '5';
      document.body.appendChild(g);
      setTimeout(function () { if (g.parentNode) g.parentNode.removeChild(g); }, FADE_MS);
      fading = true;
    });
    Object.keys(after).forEach(function (k) {
      var n = after[k], b = before[k];
      if (!b) {
        if (drawn) { n.classList.add('card-new'); setTimeout(function () { n.classList.remove('card-new'); }, ENTER_MS); }
        return;
      }
      var dy = b.top - n.getBoundingClientRect().top;
      if (Math.abs(dy) < 1) return;
      n.style.transition = 'none'; n.style.transform = 'translateY(' + dy + 'px)';        /* first where it was */
      n.getBoundingClientRect();
      n.style.transition = 'transform ' + SLIDE_MS + 'ms ease' + (fading ? ' ' + FADE_MS + 'ms' : '');
      n.style.transform = '';                                                            /* then up into its place */
      setTimeout(function () { n.style.transition = ''; }, SLIDE_MS + (fading ? FADE_MS : 0));
    });
  }
  function setHtml(el, html) {
    if (el._html === html) return;
    var before = motionOn() ? cardSnap(el) : null, drawn = !!el._drawn;
    el._drawn = true;
    setHtmlNow(el, html);
    addLines();
    if (before) cardMotion(el, before, drawn);
  }
  function setHtmlNow(el, html) {
    var busy = busyKeys(), live = [].slice.call(el.querySelectorAll('[data-key]'));
    if (!live.some(function (n) { return busy[n.getAttribute('data-key')]; })) { el.innerHTML = html; el._html = html; return; }
    var tmp = document.createElement('div'), fresh = {}, seen = {};
    tmp.innerHTML = html;
    [].forEach.call(tmp.querySelectorAll('[data-key]'), function (n) { var k = n.getAttribute('data-key'); (fresh[k] = fresh[k] || []).push(n); });
    live.forEach(function (n) {
      var k = n.getAttribute('data-key');
      if (busy[k] || !n.parentNode || !el.contains(n)) return;
      var i = seen[k] || 0, f = fresh[k] && fresh[k][i];
      seen[k] = i + 1;
      if (!f) n.parentNode.removeChild(n); else if (f.outerHTML !== n.outerHTML.replace(/<button type="button" class="fold-line[^>]*><\/button>/g, '')) n.parentNode.replaceChild(f, n);
    });
    el._html = null;                       /* partly current: the next quiet redraw sets it whole */
  }
  /* Unsent words and open boxes are kept on this device, so a reload or a lost connection does not lose them. */
  function keepDrafts() { keepSet('drafts', JSON.stringify({d: S.drafts, p: S.panel})); }
  (function () {
    try { var k = JSON.parse(keepGet('drafts') || '{}'); if (k.d) S.drafts = k.d; if (k.p) S.panel = k.p; } catch (e) {}
  })();

  /* ---------- folding: every section opens and shuts at its heading ---------- */
  /* What is folded is kept on this device, so it holds through a redraw, a reload and a newer version of
     the page. Only a choice he made is kept: a section never seen before has no entry and starts open. A
     folded section stays in the page, out of sight, so words typed in one of its cards are not lost. */
  var FOLDS = {};
  (function () {
    try { FOLDS = JSON.parse(keepGet('folds') || '{}') || {}; } catch (e) { FOLDS = {}; }
    for (var k in FOLDS) if (k.slice(0, 4) !== 'sec:' && k.slice(0, 4) !== 'set:') S.open[k] = FOLDS[k];      /* Settings parts always start shut */
  })();
  var SHUT_FIRST = {about: 1, fyi: 1, someday: 1, saidso: 1, held: 1};
  function shut(name) { var v = FOLDS['sec:' + name]; return v == null ? !!SHUT_FIRST[name] : v === false; }
  function keepFold(k, open) { if (FOLDS[k] === open) return; FOLDS[k] = open; keepSet('folds', JSON.stringify(FOLDS)); }
  /* the side line that shuts an open part: a real button, so touch and keyboard reach it too */
  function addLines() {
    [].forEach.call(document.querySelectorAll('section > .sec-h[data-fold], details[data-d], article.card[data-key]'), function (el) {
      var host = el.matches('.sec-h') ? el.parentNode : el, hd, inside = false;
      if (host.querySelector(':scope > .fold-line')) return;
      if (el.matches('.sec-h')) hd = el.querySelector('h2');
      else if (el.matches('.card')) { hd = el.querySelector(':scope > .opener'); inside = true; if (!hd || hd.getAttribute('aria-expanded') !== 'true') return; }
      else { hd = el.querySelector(':scope > summary'); inside = el.matches('.fold'); }
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'fold-line' + (inside ? ' in' : ''); b.setAttribute('aria-expanded', 'true');
      b.setAttribute('aria-label', 'Close ' + (hd ? hd.textContent.replace(/\s+/g, ' ').trim().slice(0, 80) : 'this part'));
      host.appendChild(b);
    });
    autoFold();
    if (STK) stackSoon();
  }
  function secEmpty(sec) {
    return ![].some.call(sec.children, function (c) { return !c.matches('.sec-h,.fold-line') && (c.matches('.card,.chg') || !!c.querySelector('.card,.chg,.mail-row,li:not(.quiet),details,table,.rm-host:not([hidden])')); });
  }
  /* a part ticked "Only show when it has something in it" is out of the page altogether (heading too) while it is empty */
  function autoFold() {
    var st = setts(), oi = st && st.page && Array.isArray(st.page.open_if_filled) ? st.page.open_if_filled : ['about'];
    [].forEach.call(document.querySelectorAll('section > .sec-h[data-fold]'), function (hd) {
      var nm = hd.getAttribute('data-fold'), sec = hd.parentNode, s = shut(nm);
      sec.classList.toggle('folded', s);
      hd.setAttribute('aria-expanded', String(!s));
      sec.classList.toggle('empty-hide', oi.indexOf(nm) >= 0 && secEmpty(sec));
    });
  }
  function showFolds() { addLines(); }
  /* folding a part from further down the page snaps up to its heading, just under the top bar; a heading already in view stays put */
  function flipFold(name) {
    var closing = !shut(name);
    keepFold('sec:' + name, shut(name)); render();
    if (!closing) return;
    var hd = null;
    [].forEach.call(document.querySelectorAll('section > .sec-h[data-fold]'), function (x) { if (x.getAttribute('data-fold') === name) hd = x; });
    var pin = $('pinbar'), st = $('stack');
    if (!hd || !hd.offsetParent) return;
    var want = (pin ? pin.offsetHeight : 0) + (st && !st.hidden ? st.offsetHeight : 0) + 6, top = hd.getBoundingClientRect().top;
    if (top < want - 8) window.scrollBy({top: top - want, behavior: 'smooth'});
  }
  /* one card open at a time (his plan of 11/23): opening a card closes every other, so "this card" in the box is always the open one */
  function openOnly(k) { Object.keys(S.open).forEach(function (x) { if (x.slice(0, 5) === 'card:' && x !== 'card:' + k) delete S.open[x]; }); S.open['card:' + k] = true; }
  function openCardKey() { var ks = Object.keys(S.open).filter(function (x) { return x.slice(0, 5) === 'card:' && S.open[x] === true; }); return ks.length === 1 ? ks[0].slice(5) : ''; }
  function flipCard(el) { var hst = el.closest('[data-key]'), k = hst && hst.getAttribute('data-key'); if (!k) return; if (el.getAttribute('aria-expanded') !== 'true') openOnly(k); else S.open['card:' + k] = false; acting = k; render(); var again = document.querySelector('[data-key="' + k + '"] .opener'); if (again && document.activeElement !== again && el.matches(':focus-visible')) again.focus(); }
  function howMany(n) { return n + (n === 1 ? ' card' : ' cards'); }
  /* A named group of cards inside a section: its own heading folds it and shows how many it holds. */
  function group(name, label, list, s) {
    var k = 'g:' + name;
    return '<details class="grp" data-d="' + k + '"' + (S.open[k] === false ? '' : ' open') + '><summary>' + label + ' <span class="cnt">' + list.length + '</span></summary>' + cards(list, s) + '</details>';
  }
  showFolds();

  /* ---------- calendar: the day and time he picks ---------- */
  function whenWords(c) {
    var d = D(c.date), o = d ? fmtD(d) + '/' + String(d.getFullYear()).slice(2) : 'No day yet';
    if (c.all_day) return o + ', all day';
    if (c.start) o += ', ' + fmtT(D(c.date + 'T' + c.start)) + (c.end ? ' to ' + fmtT(D(c.date + 'T' + c.end)) : '');
    return o;
  }
  function calDraft(it) {
    var c = it.calendar || {}, d = S.drafts['cal:' + it.key];
    return d || {date: c.date || '', start: c.start || '', end: c.end || '', all_day: !!c.all_day};
  }
  function calPanel(it, c, sure) {
    var k = h(it.key), d = calDraft(it), guessed = !sure && (c.date || c.start);
    return '<div class="panel-box cal">' + (c.title ? '<div class="kv"><b>' + h(c.title) + '</b>' + (c.location ? ', ' + h(c.location) : '') + '</div>' : '') +
      '<label for="cd-' + k + '">Day</label><input type="date" id="cd-' + k + '" data-cal="date" value="' + h(d.date) + '">' +
      '<label class="check" for="ca-' + k + '"><input type="checkbox" id="ca-' + k + '" data-cal="all_day"' + (d.all_day ? ' checked' : '') + '> All day</label>' +
      (d.all_day ? '' : '<div class="times"><span><label for="cs-' + k + '">Starts</label><input type="time" id="cs-' + k + '" data-cal="start" value="' + h(d.start) + '"></span>' +
        '<span><label for="ce-' + k + '">Ends</label><input type="time" id="ce-' + k + '" data-cal="end" value="' + h(d.end) + '"></span></div>') +
      (guessed ? '<div class="guess">The day or time filled in is my best guess. Check it.</div>' : '') +
      '<div class="acts"><button class="btn primary" data-a="cal-save">Add to calendar</button>' + (sure ? '<button class="btn quiet" data-a="cancel">Cancel</button>' : '') + '</div></div>';
  }


  /* ---------- settings: how the page looks, and the panel where the owner changes what they may ----------
     The panel is drawn from definitions sent with the page's data (ITEMS.md "Settings sent as data"): each
     setting comes with its label, help words, kind of control, choices, present value and group, so a setting
     the engine adds later shows here with no change to this page. A Save
     press is saved like any answer, on the key "settings", for one group at a time; the engine checks every
     field and its plain result shows under the Save button. Nothing saves without Save. What is typed is
     kept on this device until it is saved, so a redraw, a refresh or a reload never loses it. A password is
     the one thing kept only while the page is open, and it goes to this page's own server, nowhere else. */
  var SEC_OF = {decide: 'decide', words: 'decide', task: 'decide', 'new': 'decide', small: 'small', tracked: 'tracked', motion: 'tracked', fyi: 'fyi', someday: 'someday', done: 'handled'};
  /* The page's modules and the four areas they go in (Settings, "How the page looks"; settings_page.AREAS). Top and
     bottom run the full width, left is the wide column, right the narrow one; on a phone they stack in that order.
     Each connected roadmap is its own module, rm:<key>. With no saved arrangement the page is as it always was. */
  var AREAS = ['top', 'left', 'right', 'bottom'];
  var AREA_NAME = {top: 'Top (full width)', left: 'Left (the wide column)', right: 'Right (the narrow column)', bottom: 'Bottom (full width)'};
  var DEF_AREA = {top: ['chat', 'about'], left: ['feed', 'roadmaps'], right: ['today'], bottom: ['mail', 'texts', 'calendar']};
  /* the card kinds the Cards feed holds (once each a section of its own); a saved arrangement that names one places Cards there */
  var FEED_KINDS = ['decide', 'small', 'tracked', 'fyi', 'someday', 'handled', 'saidso', 'held'], NOT_PARTS = ['ready', 'changes'];
  function rmKeys() { return ((S.meta && S.meta.roadmaps) || []).map(function (r) { return 'rm:' + r.key; }); }
  function layoutOf(o) {
    o = o || {};
    if (o.main || o.side) o = {top: ['ready', 'chat', 'about'], left: o.main || [], right: o.side || [], bottom: []};
    var known = [].concat(DEF_AREA.top, DEF_AREA.left, DEF_AREA.right, DEF_AREA.bottom).filter(function (x) { return x !== 'roadmaps'; }).concat(modKeys(), rmKeys());
    var out = {}, placed = {};
    function put(a, x) {
      (x === 'roadmaps' ? rmKeys() : [x]).forEach(function (m) { if (known.indexOf(m) >= 0 && !placed[m]) { out[a].push(m); placed[m] = 1; } });
    }
    AREAS.forEach(function (a) { out[a] = []; (o[a] || []).forEach(function (x) { x = String(x); if (FEED_KINDS.indexOf(x) >= 0) x = 'feed'; if (NOT_PARTS.indexOf(x) < 0) put(a, x); }); });
    /* a part the saved arrangement does not name goes where the default puts it: before the next default part placed there */
    AREAS.forEach(function (a) { DEF_AREA[a].forEach(function (x, i) {
      var later = DEF_AREA[a].slice(i + 1).map(function (y) { return out[a].indexOf(y); }).filter(function (n) { return n >= 0; })[0];
      if (later === undefined || x === 'roadmaps' || placed[x] || known.indexOf(x) < 0) { put(a, x); return; }
      out[a].splice(later, 0, x); placed[x] = 1;
    }); });
    modKeys().forEach(function (m) {        /* a part a mod brings, not placed yet: at the bottom, before Hidden */
      if (placed[m]) return;
      var hi = out.bottom.indexOf('held'); out.bottom.splice(hi < 0 ? out.bottom.length : hi, 0, m); placed[m] = 1;
    });
    return out;
  }
  function gatherEvery() { var st = setts(), n = st && st.watch && st.watch.every_minutes; return n === 30 || n === 60 ? n : 15; }
  function gatherPaused() { var st = setts(); return !!(st && st.watch && st.watch.paused); }
  function doneDays() { var st = setts(), n = st && st.page && st.page.done_days; return n > 0 ? n : 7; }
  function secTitle(nm) { var st = setts(), t = st && st.page && st.page.titles; return t && typeof t[nm] === 'string' ? t[nm].trim() : ''; }
  function secName(nm) { return secTitle(nm) || secDefault(nm); }
  function secDefault(nm) {
    var L = (S.meta && S.meta.labels) || {};
    if (modTitle(nm)) return modTitle(nm);
    if (/^rm:/.test(nm)) { var r = ((S.meta && S.meta.roadmaps) || []).filter(function (x) { return 'rm:' + x.key === nm; })[0]; return 'Roadmap: ' + (r ? r.name : 'not connected now'); }
    return {feed: 'Cards', decide: 'Needs you', small: 'Needs you, quick answers', tracked: 'Waiting on others', fyi: 'FYI', someday: 'Someday', roadmaps: 'Roadmaps', ready: 'Drafts', mail: 'Email', texts: 'Texts', calendar: 'Calendar', about: L.about || 'Errors', held: 'Hidden', today: 'Today', handled: 'Done', saidso: 'Done under your approvals', changes: 'Change history', chat: 'Talk to your assistant'}[nm] || nm;
  }
  /* A section the owner hid stays hidden unless it holds something marked important. */
  function hiddenSec(nm, impIn) {      /* a card kind is shown by the feed's filter, never switched off as a part */
    if (FEED_KINDS.indexOf(nm) >= 0 || NOT_PARTS.indexOf(nm) >= 0) return false;
    var st = setts(), hid = (st && st.page && st.page.hidden) || []; return hid.indexOf(nm) >= 0 && !impIn[nm];
  }
  function secEl(m) { return $(/^rm:/.test(m) ? 'sec-rm-' + m.slice(3) : 'sec-' + m); }
  function placeSections() {
    var st = setts(), lay = layoutOf(st && st.page && st.page.order), a = document.activeElement;
    AREAS.forEach(function (ar) {
      var box = $('area-' + ar), els = lay[ar].map(secEl).filter(Boolean);
      if (!box) return;
      var now = [].filter.call(box.children, function (ch) { return /^sec-/.test(ch.id || ''); });
      if (now.length === els.length && now.every(function (ch, i) { return ch === els[i]; })) return;
      els.forEach(function (e) { box.appendChild(e); });
    });
    var chat = $('sec-chat');
    if (chat) chat.hidden = hiddenSec('chat', {});
    if (a && a !== document.activeElement && a.focus) a.focus();
  }
  /* Light or dark and the text size follow the owner's saved choice on every device; the last one seen is
     kept here so the page opens in it before its data arrives. With no choice the page is as it always was. */
  /* The page's style (Settings, How the page looks), Glass dark when none or an old one is saved: html[data-look] and its
     own lettering, fetched only for the style in use. The styles themselves are the "Looks" block of the style sheet. */
  var LOOK_FONTS = {
    workshop: 'family=Barlow:wght@400;500;600;700&family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500',
    broadsheet: 'family=Playfair+Display:wght@700;800;900&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&family=IBM+Plex+Mono:wght@400;500',
    dense: 'family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500',
    glass: 'family=Inter:wght@400;500;600;700&family=Roboto+Mono:wght@400;500',
    expressive: 'family=Roboto+Flex:opsz,wght@8..144,400;8..144,500;8..144,600;8..144,800&family=Roboto+Mono:wght@400;500',
    tiles: 'family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500',
    paper: 'family=Nunito+Sans:opsz,wght@6..12,400;6..12,600;6..12,700;6..12,800&family=Roboto+Mono:wght@400;500',
    retro: 'family=Roboto+Mono:wght@400',
    soft: 'family=Rubik:wght@400;500;600;700&family=Roboto+Mono:wght@400;500',
    panel: 'family=Inter+Tight:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600',
    starship: 'family=Antonio:wght@400;600;700&family=Inter:wght@400;500&family=Roboto+Mono:wght@400',
    terminal: 'family=Barlow+Semi+Condensed:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500',
    greenscreen: 'family=Share+Tech+Mono&family=VT323',
    grid: 'family=Exo+2:wght@400;500;600;700&family=Share+Tech+Mono',
    frost: 'family=Barlow+Semi+Condensed:wght@400;500;600;700&family=Share+Tech+Mono',
    monolith: 'family=Michroma&family=Inter:wght@400;500&family=Roboto+Mono:wght@400',
    haze: 'family=Jost:wght@300;400;500;600&family=Share+Tech+Mono'
  };
  function applyLook() {
    var st = setts(), p = st && st.page, th = p ? p.theme : keepGet('theme'), sz = p ? p.text_size : keepGet('size'), root = document.documentElement;
    if (th === 'light' || th === 'dark') root.setAttribute('data-theme', th); else root.removeAttribute('data-theme');
    if (sz === 'small' || sz === 'large') root.setAttribute('data-size', sz); else root.removeAttribute('data-size');
    var lk = p ? p.look : keepGet('look');
    if (!LOOK_FONTS[lk]) { lk = 'glass'; th = 'dark'; }
    {
      root.setAttribute('data-look', lk);
      if (!document.querySelector('link[data-look-fonts="' + lk + '"]')) {
        var fl = document.createElement('link'); fl.rel = 'stylesheet'; fl.setAttribute('data-look-fonts', lk);
        fl.href = 'https://fonts.googleapis.com/css2?' + LOOK_FONTS[lk] + '&display=swap'; document.head.appendChild(fl);
      }
    }
    rmTheme();
    if (p && (keepGet('look') || '') !== (lk || '')) keepSet('look', lk || '');
    if (p && (keepGet('theme') || '') !== (th || '')) keepSet('theme', th || '');
    if (p && (keepGet('size') || '') !== (sz || '')) keepSet('size', sz || '');
  }
  /* The preview beside Theme, Style and Text size: a frame of its own document on the page's own style sheets, carrying the
     choices made but not yet saved on its html as applyLook puts them on the page's, so the page itself changes only on Save. */
  var APV_IDS = {theme: 1, look: 1, text_size: 1}, APV = {h: 0};
  function apvNow() {
    var p = (setts() || {}).page || {}, lk = sVal('page', 'look', p.look);
    return {th: sVal('page', 'theme', p.theme), lk: LOOK_FONTS[lk] ? lk : 'glass', sz: sVal('page', 'text_size', p.text_size)};
  }
  function apvBox() { var s = apvNow(); return '<div class="apv" id="apv" data-apv="' + h(s.th + '|' + s.lk + '|' + s.sz) + '"></div>'; }
  function apvDoc(s) {
    var css = [].map.call(document.querySelectorAll('link[rel="stylesheet"],style'), function (n) {
      return n.tagName === 'STYLE' ? '<style>' + n.textContent + '</style>' : '<link rel="stylesheet" href="' + h(n.href) + '">'; }).join('');
    return '<!doctype html><html class="apv-doc" data-look="' + s.lk + '"' + (s.th === 'light' || s.th === 'dark' ? ' data-theme="' + s.th + '"' : '') +
      (s.sz === 'small' || s.sz === 'large' ? ' data-size="' + s.sz + '"' : '') + '><head><meta charset="utf-8">' + css +
      '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?' + LOOK_FONTS[s.lk] + '&display=swap"></head><body>' +
      '<header class="mast"><h1>Your desk</h1><span class="mast-r"><button class="btn" type="button" tabindex="-1">Settings</button></span></header>' +
      '<div class="sec-h"><h2>Cards</h2><span class="n">2</span></div><div class="feed">' +
      '<section id="sec-decide"><div class="cards"><article class="card urgent"><div class="q">Approve the quote?</div>' +
      '<div class="acts"><button class="btn primary" type="button" tabindex="-1">Approve</button></div></article></div></section>' +
      '<section id="sec-fyi"><div class="cards"><article class="card"><div class="q">The order shipped</div>' +
      '<div class="acts"><button class="btn" type="button" tabindex="-1">Open</button></div></article></div></section></div>' +
      '<p class="apv-say">Body text looks like this.</p></body></html>';
  }
  function apvMount(el) {
    var box = el.querySelector('#apv');
    if (!box || box.firstChild) return;
    var fr = document.createElement('iframe');
    fr.title = 'Preview of the page with these choices'; fr.tabIndex = -1; fr.setAttribute('aria-hidden', 'true');
    if (APV.h) fr.style.height = APV.h + 'px';
    fr.onload = function () {
      var d = fr.contentDocument;
      function fit() { if (d && d.body && fr.isConnected) { APV.h = Math.ceil(d.body.getBoundingClientRect().height); fr.style.height = APV.h + 'px'; } }
      fit(); if (d && d.body && d.defaultView.ResizeObserver) new d.defaultView.ResizeObserver(fit).observe(d.body);   /* new width, lettering */
    };
    fr.srcdoc = apvDoc(apvNow());
    box.appendChild(fr);
  }
  var SET = {queue: [], leave: false, top: null, pending: null, said: {}, fromRules: {}, pw: {current: '', new1: '', again: ''}, pwSaid: null, pwBusy: false,
             nav: [], parts: {}, cmd: '', info: null};
  function sDraft(g) { return S.drafts['set:' + g] || {}; }
  function sVal(g, f, now) { var d = sDraft(g); return d[f] !== undefined ? d[f] : now; }
  function sDirty(g) { return Object.keys(sDraft(g)).length > 0; }
  function sId(g, f) { return 'set-' + g + '-' + f; }
  function sLabel(g, f, words) { return '<label for="' + sId(g, f) + '">' + words + '</label>'; }
  function sText(g, f, words, now, more) {
    return sLabel(g, f, words) + '<input type="text" id="' + sId(g, f) + '" data-set="' + g + '.' + f + '" value="' + h(sVal(g, f, now)) + '" autocomplete="off"' + (more || '') + '>';
  }
  function sArea(g, f, words, now, note) {
    return sLabel(g, f, words) + '<textarea autocomplete="off" name="box-10" id="' + sId(g, f) + '" data-set="' + g + '.' + f + '">' + h(sVal(g, f, now)) + '</textarea>' + (note ? '<div class="wnote">' + note + '</div>' : '');
  }
  function sPick(g, f, words, now, opts, note) {
    var v = String(sVal(g, f, now));
    return sLabel(g, f, words) + '<select class="short" id="' + sId(g, f) + '" data-set="' + g + '.' + f + '">' + opts.map(function (o) {
      return '<option value="' + h(o[0]) + '"' + (String(o[0]) === v ? ' selected' : '') + (o[2] ? ' disabled' : '') + '>' + h(o[1]) + '</option>'; }).join('') + '</select>' + (note ? '<div class="wnote">' + note + '</div>' : '');
  }
  function sLines(v) { return String(v || '').split(/\n/).map(function (x) { return x.trim(); }).filter(Boolean); }
  function sFoot(g, label) {
    var said = SET.said[g], wait = SET.pending && SET.pending.g === g, o = '';
    if (sDirty(g)) o += '<div class="acts"><button class="btn quiet" type="button" data-s="reset" data-g="' + g + '">Put back what was saved</button></div>';
    if (wait) o += '<div class="set-said wait" role="status">' + (S.listening === false ? 'Saved on the page. This page can\'t reach your computer, so it takes effect when it\'s back.' : 'Saving') + '</div>';
    else if (said && !SET.fromRules[g]) o += sSaid(said);
    else if (sDirty(g)) o += '<div class="wnote">Changed here, not saved yet.</div>';
    return o;
  }
  function sSaid(said) { return '<div class="set-said' + (said.bad ? ' bad' : said.warn ? ' wait' : '') + '" role="status">' + hc(said.text) + '</div>'; }
  /* A list of rules: sentences the owner adds, edits, pauses and removes, in one list for each way a rule can work. */
  function sRulesNow(x) {
    var d = sDraft(x.group)[x.id];
    return (d || sNow(x) || []).map(function (r) { return {id: r.id == null ? null : r.id, text: String(r.text || ''), reason: String(r.reason || ''), way: r.way == null ? null : r.way, on: r.on !== false, made: r.made, from: r.from}; });
  }
  function sRulesSeen(x, d) { if (!d[x.id + '__seen']) d[x.id + '__seen'] = (sNow(x) || []).map(function (r) { return r.id; }).filter(function (i) { return i != null; }); }
  function sRules(x, lab, note) {
    var g = x.group, f = x.id, list = sRulesNow(x), ways = sChoices({choices: x.ways}), path = h(g + '.' + f), o = '<label>' + lab + '</label>' + note, said = SET.said[g];
    if (!ways.length) ways = [[null, '']];
    ways.forEach(function (w, wi) {
      var n = 0, dk = 'radd:' + g + '.' + f + '|' + (w[0] == null ? '' : w[0]), aid = sId(g, f) + '-add' + wi;
      if (w[1]) o += '<div class="set-sub">' + h(w[1]) + '</div>';
      list.forEach(function (r, i) {
        if (w[0] !== null && r.way !== w[0]) return;
        n++;
        var made = D(r.made);
        o += '<div class="rule"><textarea autocomplete="off" name="box-11" id="' + sId(g, f) + '-' + i + '" aria-label="The rule, in one sentence" data-rule="' + path + '" data-i="' + i + '">' + h(r.text) + '</textarea>' +
          '<input type="text" autocomplete="off" name="box-13" class="nm" id="' + sId(g, f) + '-why' + i + '" aria-label="Why this rule" data-rule="' + path + '" data-i="' + i + '" data-k="reason" value="' + h(r.reason) + '" placeholder="Why this rule (optional)" maxlength="300">' +
          '<div class="set-line"><select aria-label="On or paused" id="' + sId(g, f) + '-on' + i + '" data-rule="' + path + '" data-i="' + i + '" data-k="on"><option value="1"' + (r.on ? ' selected' : '') + '>On</option><option value="0"' + (r.on ? '' : ' selected') + '>Paused</option></select>' +
          '<span class="nm wnote">' + (r.id == null ? 'New, not saved yet' : made ? 'Made ' + h(fmtD(made)) + (r.from ? (/^You /.test(r.from) ? '. ' + h(r.from) : ', from "' + h(r.from) + '"') : '') : '') + '</span>' +
          '<button class="btn" type="button" data-s="rule-del" data-rule="' + path + '" data-i="' + i + '">Remove</button></div></div>';
      });
      if (!n) o += '<div class="wnote">No rule here yet.</div>';
      o += '<div class="set-line wraps"><input type="text" autocomplete="off" name="box-12" class="nm" id="' + aid + '" aria-label="A new rule" data-radd="' + h(dk) + '" value="' + h(S.drafts[dk] || '') + '" placeholder="A new rule, in one plain sentence" maxlength="300">' +
        '<button class="btn" type="button" data-s="rule-add" data-rule="' + path + '" data-way="' + h(w[0] == null ? '' : w[0]) + '">Add a rule</button></div>';
    });
    if (SET.pending && SET.pending.g === g && SET.fromRules[g]) o += '<div class="set-said wait" role="status">Saving</div>';
    else if (said && SET.fromRules[g]) o += sSaid(said);
    return o + '<hr class="set-hr">';
  }
  /* typing in a rule or in the box for a new one: kept as typed, never redrawn under the cursor */
  function sRuleInput(t) {
    if (t.hasAttribute('data-radd')) { S.drafts[t.getAttribute('data-radd')] = t.value; return false; }
    var path = t.getAttribute('data-rule') || '', dot = path.indexOf('.'), g = path.slice(0, dot), f = path.slice(dot + 1), x = sDef(g, f);
    if (!x) return false;
    var list = sRulesNow(x), i = +t.getAttribute('data-i'), d = S.drafts['set:' + g] || {};
    if (!list[i]) return false;
    var rk = t.getAttribute('data-k');
    if (rk === 'on') list[i].on = t.value === '1'; else if (rk === 'reason') list[i].reason = t.value; else list[i].text = t.value;
    sRulesSeen(x, d);
    d[f] = list; S.drafts['set:' + g] = d; delete SET.said[g];
    return t.tagName === 'SELECT';
  }
  /* Standing approvals (ITEMS.md "Design round 3"). The ladder is a setting: every entry, its level, On or Paused, how often it
     acted, Remove; one Save is the owner's approval. Each use is in the record "Done on your say-so", with Undo on the card. */
  function sLadderNow(x) {
    var d = sDraft(x.group)[x.id];
    return (d || sNow(x) || []).map(function (r) { return {id: r.id == null ? null : r.id, kind: r.kind, label: r.label || r.kind, area: r.area, level: r.level, on: r.on !== false, used: r.used, made: r.made, from: r.from}; });
  }
  function ladKinds(x) { return (x.kinds || []).map(function (k) { return typeof k === 'object' ? [k.kind || k.value, k.label || k.kind || k.value] : [k, k]; }); }
  function ladAdd(x, path) {
    var add = S.drafts['ladd:' + path] || {}, kinds = ladKinds(x), areas = (x.areas || []).map(String), levels = sChoices({choices: x.levels});
    return {kind: add.kind || (kinds[0] || [''])[0], area: add.area || areas[0] || '', level: add.level || (levels.filter(function (l) { return l[0] !== 'ask'; })[0] || levels[0] || ['tell'])[0]};
  }
  function sLadder(x, lab, note) {
    var g = x.group, f = x.id, list = sLadderNow(x), levels = sChoices({choices: x.levels}), path = h(g + '.' + f), o = '<label>' + lab + '</label>' + note;
    var kinds = ladKinds(x), areas = (x.areas || []).map(String), ad = ladAdd(x, g + '.' + f);
    if (!list.length) o += '<div class="wnote">None yet. After you approve the same kind of thing several times, I ask if I may do it without asking, and your yes adds it here.</div>';
    list.forEach(function (r, i) {
      var made = D(r.made);
      o += '<div class="rule"><div class="detail">' + hc(r.label) + ' <span class="wnote">' + (r.area ? 'in ' + h(r.area) : 'in every area') + '</span></div>' +
        '<div class="set-line wraps"><select aria-label="How it is done" data-lad="' + path + '" data-i="' + i + '" data-k="level">' + levels.map(function (l) { return '<option value="' + h(l[0]) + '"' + (String(l[0]) === String(r.level) ? ' selected' : '') + '>' + h(l[1]) + '</option>'; }).join('') + '</select>' +
        '<select aria-label="On or paused" data-lad="' + path + '" data-i="' + i + '" data-k="on"><option value="1"' + (r.on ? ' selected' : '') + '>On</option><option value="0"' + (r.on ? '' : ' selected') + '>Paused</option></select>' +
        '<button class="btn" type="button" data-s="lad-del" data-rule="' + path + '" data-i="' + i + '">Remove</button></div>' +
        '<div class="wnote">' + (r.id == null ? 'New, not saved yet.' : (made ? 'Made ' + h(fmtD(made)) + (r.from ? ', ' + hc(r.from) : '') + '. ' : '') + 'Used ' + plural(+r.used || 0, 'time') + '. Each use is listed in Cards, under Done.') + '</div></div>';
    });
    if (kinds.length) {
      var sel = function (name, key, opts, cur) { return '<select aria-label="' + name + '" data-ladd="' + path + '" data-k="' + key + '">' + opts.map(function (v) { return '<option value="' + h(v[0]) + '"' + (String(v[0]) === String(cur) ? ' selected' : '') + '>' + h(v[1]) + '</option>'; }).join('') + '</select>'; };
      o += '<div class="set-sub">Add one</div><div class="set-line wraps">' + sel('Kind', 'kind', kinds, ad.kind) + (areas.length ? sel('Area', 'area', areas.map(function (a) { return [a, a]; }), ad.area) : '') + sel('Level', 'level', levels, ad.level) +
        '<button class="btn" type="button" data-s="lad-add" data-rule="' + path + '">Add</button></div>';
    }
    return o + '<hr class="set-hr">';
  }
  function sLadInput(t) {
    if (t.hasAttribute('data-ladd')) { var ak = 'ladd:' + t.getAttribute('data-ladd'), ar = S.drafts[ak] || {}; ar[t.getAttribute('data-k')] = t.value; S.drafts[ak] = ar; return false; }
    var path = t.getAttribute('data-lad') || '', dot = path.indexOf('.'), g = path.slice(0, dot), f = path.slice(dot + 1), x = sDef(g, f);
    if (!x) return false;
    var list = sLadderNow(x), i = +t.getAttribute('data-i'), d = S.drafts['set:' + g] || {};
    if (!list[i]) return false;
    if (t.getAttribute('data-k') === 'on') list[i].on = t.value === '1'; else list[i].level = t.value;
    d[f] = list; S.drafts['set:' + g] = d; delete SET.said[g];
    return false;
  }
  function saidUndo(id) {
    var r = ((S.standing && S.standing.log) || []).filter(function (x) { return String(x.id) === String(id); })[0], it = r && find(r.card);
    if (!it) { toast('That card is no longer on the page, so it cannot be taken back here.', ''); return; }
    S.useUndone[id] = true;
    save(it, pressRec('undo', null, 'Taken back'), true);
    render();
    toast('Taken back. I won\'t do it for you again.', '');
  }
  function renderSaidSo() {
    var sec = $('sec-saidso'), log = (S.standing && S.standing.log) || [], o = '';
    if (!sec) return;
    sec.hidden = !log.length || hiddenSec('saidso', {});
    $('n-saidso').textContent = log.length ? String(log.length) : '';
    var row = function (r) {
      var back = r.undone || S.useUndone[r.id], canUndo = !back && !!find(r.card);
      return '<li><span class="t">' + hc(r.header || r.card) + '</span>' +
        '<span class="src">' + h(fmtDT(D(r.at))) + ', ' + hc(r.label) + (r.area ? ' in ' + h(r.area) : '') + ', ' + (r.level === 'quiet' ? 'done quietly' : 'done and notified') + '</span>' +
        (back ? '<span class="said">Taken back.</span>' : canUndo ? '<div class="acts"><button class="btn" data-a="said-undo" data-use="' + h(r.id) + '">Undo</button></div>' : '<span class="src">The card is no longer on the page.</span>') + '</li>';
    };
    if (log.length) {
      o = '<ul class="rows">' + log.slice(0, 10).map(row).join('') + '</ul>';
      if (log.length > 10) o += '<details class="more" data-d="saidso-earlier"' + (S.open['saidso-earlier'] ? ' open' : '') + '><summary>Earlier uses <span class="cnt">' + (log.length - 10) + '</span></summary><div class="inside"><ul class="rows">' + log.slice(10).map(row).join('') + '</ul></div></details>';
    }
    setHtml($('saidso'), o);
  }

  /* ---------- changes to the program: asked for in Talk to your assistant, listed, undone ----------
     The engine sends one document, "changes" ({active, list}; Package\Test photos\program changes\). Nothing here edits
     the program: the page asks (chat), says where a change stands, and presses Undo. A page with no such document looks as before. */
  var CHG_DONE = {done: 'Made, and seen working on your page', working: 'Being made', failed: 'Not made', undone: 'Undone', undoing: 'Being undone'};
  function chgPart(c) { return c.part_name ? c.part_name : c.part === 'personal' ? 'your personal part' : c.part === 'addon' || c.part === 'add-on' ? 'a taught add-on' : c.part === 'general' ? 'the general part' : (c.part || ''); }
  function chgList() { return (S.chg && S.chg.list) || []; }
  function chgState(c) { return S.chgSent[c.id] && (c.status === 'done') ? 'undoing' : c.status; }
  function chgSeenList() { try { return JSON.parse(keepGet('chgseen') || '[]') || []; } catch (e) { return []; } }
  function chgSend(key, text, label, result) {
    var rec = {action: 'answer', label: label, result: result, text: text};
    if (!S.db) { toast('This page can\'t reach me here. Sign in and open it again.', ''); return false; }
    rec.id = key; rec.at = stamp(key); rec.device = device; rec.sent = false; rec.status = 'saved';
    S.ans[key] = rec; S.mine[key] = {rec: rec, t: Date.now(), keep: 900000};
    S.db.setAnswer(key, rec).then(function () {}, function () { delete S.ans[key]; delete S.mine[key]; delete S.chgSent[(JSON.parse(text).press || {}).change]; toast('That did not send. Check the connection and try again.', ''); render(); });
    return true;
  }
  /* a change's result in Talk to your assistant carries its Undo, as the list of changes does */
  function chgUndoHere(t) {
    var id = t && t.change, row = id && chgList().filter(function (x) { return x.id === id; })[0];
    if (!row || row.status !== 'done' || S.chgSent[id]) return '';
    if (S.chgAsk[id]) return '<span class="acts"><b>Undo this change?</b> <button class="btn primary" type="button" data-a="chg-undo-go" data-id="' + h(id) + '">Yes, undo it</button><button class="btn" type="button" data-a="chg-undo-no" data-id="' + h(id) + '">Keep it</button></span>';
    return '<span class="acts"><button class="btn" type="button" data-a="chg-undo-ask" data-id="' + h(id) + '">Undo</button></span>';
  }
  function chgSteps(a) {
    var o = '';
    (a.steps || []).forEach(function (st) {
      var cls = st.state === 'done' ? 'ok' : st.state === 'failed' ? 'crit' : st.state === 'doing' ? 'warn' : '';
      o += '<li class="' + (st.state === 'todo' ? 'todo' : '') + '"><span class="dot ' + cls + '"></span><span>' + hc(st.name) + (st.state === 'doing' ? ' (now)' : '') + (st.state === 'failed' && st.why ? ': ' + hc(st.why) : '') + '</span></li>';
    });
    return o ? '<ul class="chg-steps">' + o + '</ul>' : '';
  }
  function renderChanges() {
    var c = S.chg, el = $('chg-now'), st = $('chg-start'), sec = $('sec-changes'), list = chgList(), a = c && c.active, o = '', gone = chgSeenList(), shown = 0;
    Object.keys(S.chgSent).forEach(function (cid) { var ua = S.ans[S.chgSent[cid]]; if (ua && ua.status === 'failed') { toast('The change was not undone. ' + (ua.outcome || ''), ''); delete S.chgSent[cid]; } });
    if (!c) { el.hidden = true; st.hidden = true; sec.hidden = true; if (talk.mode) { talk.mode = ''; } return; }
    /* no way in of its own: a change is asked in the box like anything else, and goes on a card in Cards (Approve, Disapprove, Discuss, Cancel) */
    st.hidden = true; talk.mode = '';
    $('talk-in').placeholder = 'Ask or tell me anything';
    /* a change being made, or an update talked through; a change waiting for his answer is a card, not this */
    if (a && (a.kind === 'update' || a.status !== 'asking')) {
      var working = a.status === 'working', upd = a.kind === 'update', fin = a.status === 'finish_at_computer';
      o += '<div class="chg-top"><h3>' + (fin ? 'Almost done: finish at your computer' : working ? (upd ? 'Updating' : 'Making a change') : upd ? 'The update to version ' + hc(a.version || '') + ' is being talked through' : 'A change is being talked through') + (upd ? '' : ': ' + hc(a.words || '')) + '</h3></div>';
      if (upd && (a.sorted || []).length) {
        var BK = {untouched: 'Untouched, kept as it is', adjust: 'Needs adjusting', builtin: 'Now built in', clash: 'Clashes with the new version'};
        o += '<ul class="chg-sort">' + a.sorted.map(function (x) { return '<li><span class="b">' + (BK[x.bucket] || hc(x.bucket || '')) + (x.decision ? ' (settled: ' + hc(x.decision) + ')' : x.bucket === 'untouched' ? '' : ' (waiting for you)') + '</span><span>' + hc(x.words || '') + '</span></li>'; }).join('') + '</ul>';
      }
      if (fin) {
        o += '<div class="detail">' + hc(a.finish || 'Your page and files are updated. The last step, restarting me, has to be finished at your computer. Go to your computer to finish it.') + '</div>';
      } else if (working) {
        o += chgSteps(a) + '<div class="chg-hint">If any step fails, everything is put back by itself and you are told which step and why. It is done only when it is seen working on this page.</div>';
      } else if (a.awaiting_go) {
        o += (a.summary ? '<div class="detail">' + hc(a.summary) + '</div>' : '') + '<div class="chg-hint">Nothing has been changed yet.</div>' +
          '<div class="acts"><button class="btn primary" type="button" data-a="chg-go"' + (talk.pending ? ' disabled' : '') + '>' + (upd ? 'Yes, apply the update' : 'Yes, make this change') + '</button><button class="btn" type="button" data-a="chg-wait"' + (talk.pending ? ' disabled' : '') + '>Not yet</button>' +
          (upd ? '' : '<button class="btn" type="button" data-a="chg-drop">Cancel this change</button>') + '</div>';
      } else {
        o += '<div class="chg-hint">Answer in the box above. Nothing has been changed yet' + (a.step ? '; now: ' + hc(a.step) : '') + '.' +
          (upd ? '' : ' The button "Yes, make this change" shows here once we\'ve agreed exactly what changes.') + '</div>' +
          (upd ? '' : '<div class="acts"><button class="btn" type="button" data-a="chg-drop">Cancel this change</button></div>');
      }
      el.className = fin ? 'chg good' : 'chg'; el.hidden = false; shown = 1;
    } else {
      /* a recent result he has not put away */
      var last = list.filter(function (x) { return gone.indexOf(x.id + ':' + x.status) < 0 && (x.status === 'failed' || x.status === 'done' || x.status === 'undone') && Date.now() - (T(x.finished_at || x.at) || 0) < 7200000; })[0];
      if (last) {
        var bad = last.status === 'failed';
        o += '<div class="chg-top"><h3>' + (bad ? 'The change was not made' : last.status === 'undone' ? 'The change was undone' : 'The change is made') + ': ' + hc(last.words) + '</h3></div>';
        if (bad) o += '<div class="detail">The step "' + hc(last.failed_step || 'unknown') + '" failed' + (last.why ? ': ' + hc(last.why) : '') + '. Everything was put back as it was.</div>' + (last.steps ? chgSteps(last) : '');
        else if (last.status === 'done') o += '<div class="detail">' + hc(last.what || '') + ' It was seen working on your page.</div>';
        else o += '<div class="detail">' + (last.part === 'rsi' ? 'Your rules are back as they were before I changed them on my own.' : 'Your files are back as they were before this change.') + ((last.cannot_take_back || []).length ? ' Not taken back: ' + (last.cannot_take_back || []).map(hc).join('; ').replace(/([^.!?])$/, '$1.') : '') + '</div>';
        o += '<div class="acts"><button class="btn" type="button" data-a="chg-seen" data-id="' + h(last.id) + '" data-st="' + h(last.status) + '">Put this away</button></div>';
        el.className = 'chg ' + (bad ? 'bad' : last.status === 'done' ? 'good' : ''); el.hidden = false; shown = 1;
      }
    }
    if (!shown) el.hidden = true; else if (el._html !== o) { el.innerHTML = o; el._html = o; }
    /* every change ever made */
    sec.hidden = (!list.length) || hiddenSec('changes', {});
    $('n-changes').textContent = list.length ? String(list.length) : '';
    var row = function (x) {
      var s2 = chgState(x), by = (x.built_on_by || []).filter(function (b) { return b.status !== 'undone'; }), r = '<li><span class="t">' + hc(x.words) + '</span>';
      r += '<span class="src">' + (x.what ? hc(x.what) + ' ' : '') + h(fmtDT(D(x.at))) + (chgPart(x) ? ', in ' + hc(chgPart(x)) : '') + '</span>';
      if (s2 === 'failed') r += '<span class="said bad">Not made. The step "' + hc(x.failed_step || 'unknown') + '" failed' + (x.why ? ': ' + hc(x.why) : '') + '. Everything was put back.</span>';
      else if (s2 === 'undone') r += '<span class="said">Undone' + (x.undone_at ? ' ' + h(fmtD(D(x.undone_at))) : '') + '.</span>';
      else if (s2 === 'undoing') r += '<span class="said">Being undone. ' + (x.part === 'rsi' ? 'Your rules are being put back.' : 'Your files are being put back.') + '</span>';
      else if (s2 === 'working') r += '<span class="said">Being made' + (x.step ? ': ' + hc(x.step) : '') + '.</span>';
      else if (S.chgAsk[x.id]) {
        /* a rule change the assistant made on its own at learning level 3: the Undo puts his rules back, not files */
        r += '<div class="chg-warn"><b>Undo this change?</b><span>' + (x.part === 'rsi' ? 'Your rules go back as they were before I changed them on my own. I take out the change I made.' : 'Your files go back as they were before it.') + '</span>' +
          (by.length ? '<span><b>Later changes were built on this one:</b> ' + by.map(function (b) { return hc(b.words); }).join('; ') + '. They may stop working. You can undo them first.</span>' : '') +
          ((x.cannot_take_back || []).length ? '<span><b>Cannot be taken back:</b> ' + x.cannot_take_back.map(hc).join('; ').replace(/([^.!?])$/, '$1.') + '</span>' : '') + '</div>' +
          '<div class="acts"><button class="btn primary" type="button" data-a="chg-undo-go" data-id="' + h(x.id) + '">Yes, undo it</button><button class="btn" type="button" data-a="chg-undo-no" data-id="' + h(x.id) + '">Keep it</button></div>';
      } else r += '<div class="acts"><button class="btn" type="button" data-a="chg-undo-ask" data-id="' + h(x.id) + '">Undo</button></div>';
      return r + '</li>';
    };
    var out = list.length ? '<ul class="rows chgl">' + list.slice(0, 10).map(row).join('') + '</ul>' : '';
    if (list.length > 10) out += '<details class="more" data-d="chg-earlier"' + (S.open['chg-earlier'] ? ' open' : '') + '><summary>Earlier changes <span class="cnt">' + (list.length - 10) + '</span></summary><div class="inside"><ul class="rows chgl">' + list.slice(10).map(row).join('') + '</ul></div></details>';
    var was = $('changes').innerHTML;
    setHtml($('changes'), out);
    if (S.panel.settings && $('changes').innerHTML !== was) renderSettings();   /* Settings, under Tools, shows this list: keep it current */
  }
  function chgClick(a, b) {
    var id = b.getAttribute('data-id');
    if (a === 'chg-start') { talk.mode = 'change'; renderChanges(); $('talk-in').focus(); return true; }
    if (a === 'chg-cancel') { talk.mode = ''; renderChanges(); return true; }
    if (a === 'chg-go') {          /* the go: the program makes the change, hidden, and says how it went in Talk to your assistant */
      var act = S.chg && S.chg.active;
      if (!act || !act.id || S.chgSent['go:' + act.id]) return true;          /* one press counts once */
      if (act.kind === 'update') { talkPost('Yes, go ahead and make this change now.', 'chat', 'Change go'); return true; }
      var gk = 'change-go:' + act.id + ':' + Date.now();
      S.chgSent['go:' + act.id] = gk;
      chgSend(gk, JSON.stringify({press: {name: 'change_go', change: act.id}}), 'Make this change', 'Starting the change');
      renderChanges();
      return true;
    }
    if (a === 'chg-wait') { talkPost('Not yet. I want to say something first.', 'chat', 'Change wait'); return true; }
    if (a === 'chg-drop') {        /* Cancel: the change is set aside before its go; nothing was edited */
      var da = S.chg && S.chg.active;
      if (!da || !da.id || S.chgSent['drop:' + da.id]) return true;
      var dk = 'change-drop:' + da.id + ':' + Date.now();
      S.chgSent['drop:' + da.id] = dk;
      chgSend(dk, JSON.stringify({press: {name: 'change_drop', change: da.id}}), 'Cancel this change', 'Cancelling the change');
      renderChanges();
      return true;
    }
    if (a === 'chg-seen') { var g = chgSeenList(); g.push(id + ':' + b.getAttribute('data-st')); keepSet('chgseen', JSON.stringify(g.slice(-60))); renderChanges(); return true; }
    if (a === 'chg-undo-ask') { S.chgAsk[id] = true; renderChanges(); renderTalk(); return true; }
    if (a === 'chg-undo-no') { delete S.chgAsk[id]; renderChanges(); renderTalk(); return true; }
    if (a === 'chg-undo-go') {
      if (S.chgSent[id]) return true;                                         /* one press counts once */
      var uk = 'change-undo:' + id + ':' + Date.now();
      S.chgSent[id] = uk; delete S.chgAsk[id];
      chgSend(uk, JSON.stringify({press: {name: 'undo_change', change: id}}), 'Undo change', 'Undo asked');
      renderChanges(); renderTalk();
      return true;
    }
    return false;
  }
  /* one part of Settings, folded like the rest: its heading is underlined when shut, a side line shuts it when open */
  /* every part of Settings starts shut each time Settings opens; which were open last time is not kept */
  function setsShut() { Object.keys(S.open).forEach(function (k) { if (k.slice(0, 4) === 'set:') delete S.open[k]; }); SET.nav = []; SET.cmd = ''; SET.info = null; }
  /* Settings is a short list of groups, by what he does; a group opens to its parts and a part to its settings, with a breadcrumb
     (Settings > group > part) whose every step goes back. Each part is gathered here as it is drawn, then shown by where he is. */
  function sPart(id, title, inside, info) { SET.parts[id] = {title: title, inner: inside, info: info ? infoBtn(title, info) : ''}; return ''; }
  function sGroup(g, title, inside) { SET.parts[g] = {title: title, inner: inside}; return ''; }
  var SET_TREE = [
    {id: 'me', label: 'General', say: 'Profile, appearance, calendar and sign-in.', parts: ['you', 'page', 'calendar', 'signin']},
    {id: 'people', label: 'Contacts', say: 'Everyone you write with, your address books, and what the assistant learned about them.', parts: ['contacts']},
    {id: 'in', label: 'Inbox', say: 'Sources, filters, notifications and mail.', parts: ['watch', 'filter', 'alerts', 'maildevice', 'mailrules']},
    {id: 'do', label: 'Automation', say: 'Approvals, writing style, the weekly review, the rule book and learning levels.', parts: ['acting', 'voice', 'review', 'rulebook', 'learning']},
    {id: 'cost', label: 'AI and usage', say: 'AI model and daily limit.', parts: ['thinking']},
    {id: 'tools', label: 'Tools', say: 'Guided setups, project tools, commands and change history.', parts: ['tools', 'changes']}
  ];
  function sTree() {          /* the groups as they stand now; a part the list does not name (a mod's own) goes under More */
    var known = {}, more = [];
    SET_TREE.forEach(function (gr) { gr.parts.forEach(function (p) { known[p] = 1; }); });
    Object.keys(SET.parts).forEach(function (p) { if (!known[p]) more.push(p); });
    var t = SET_TREE.map(function (gr) { return {id: gr.id, label: gr.label, say: gr.say, parts: gr.parts.filter(function (p) { return SET.parts[p]; })}; });
    if (more.length) t.push({id: 'more', label: 'More', say: 'Settings for your own additions.', parts: more});
    return t.filter(function (gr) { return gr.parts.length; });
  }
  function setGo(p) {         /* straight to one part (a refused save opens where it was refused) */
    var t = sTree(), gr = t.filter(function (x) { return x.parts.indexOf(p) >= 0; })[0];
    SET.nav = gr ? [gr.id, p] : [];
  }
  function sNav() {
    var t = sTree(), nav = SET.nav || [], gr = t.filter(function (x) { return x.id === nav[0]; })[0];
    var part = gr ? (gr.parts.length === 1 ? gr.parts[0] : gr.parts.indexOf(nav[1]) >= 0 ? nav[1] : '') : '';
    var step = function (label, to, here) {
      return here ? '<span aria-current="page">' + label + '</span>' : '<button class="link" type="button" data-s="set-nav" data-to="' + h(to) + '">' + label + '</button>';
    };
    var sep = ' <span aria-hidden="true">&rsaquo;</span> ', o = '<nav class="set-crumbs" aria-label="Where you are in Settings">' + step('Settings', '', !gr);
    if (!gr) return o + '</nav><ul class="set-groups">' + t.map(function (x) {
      return '<li><button class="set-go" type="button" data-s="set-nav" data-to="' + h(x.id) + '"><b>' + h(x.label) + '</b><span class="say">' + h(x.say) +
        (x.parts.some(sDirty) ? ' Not saved yet.' : '') + '</span></button></li>';
    }).join('') + '</ul>';
    o += sep + step(h(gr.label), gr.id, !part || gr.parts.length === 1);
    if (part && gr.parts.length > 1) o += sep + step(SET.parts[part].title, '', true);
    if (part && SET.parts[part].info) o += SET.parts[part].info;
    o += '</nav>';
    if (!part) return o + '<ul class="set-groups">' + gr.parts.map(function (p) {
      return '<li><button class="set-go" type="button" data-s="set-nav" data-to="' + h(gr.id + '/' + p) + '"><b>' + SET.parts[p].title + '</b>' +
        (sDirty(p) ? '<span class="say">Not saved yet.</span>' : '') + '</button></li>';
    }).join('') + '</ul>';
    return o + '<div class="panel-box host set-in" id="set-' + h(part) + '" data-key="set:' + h(part) + '">' + SET.parts[part].inner + '</div>';
  }
  /* Calendar: the events the assistant already gathers, shown with EventCalendar (vkurko/calendar 5.21.1, MIT, as its makers ship it,
     its two files served by this computer). Read only: pressing an event shows its details. Mounted once; the page's redraws leave it. */
  var CAL = {ec: null, busy: false, err: '', hosted: false, at: 0, names: [], ev: {}, show: '', list: [], writable: [], form: null, saving: false, formErr: '',
             off: (function () { try { return JSON.parse(keepGet('caloff') || '{}') || {}; } catch (e) { return {}; } })()};   /* calendars he hid, on this device */
  function calShown() { return CAL.list.filter(function (x) { return !CAL.off[(CAL.ev[x.id] || {}).calendar]; }); }
  function calEvent(e) { CAL.ev[e.id] = e; return {id: e.id, title: e.title, start: e.start, end: e.end, allDay: e.all_day, backgroundColor: calColor(e.calendar)}; }
  function calShut() {        /* the form closes even with a box in it still holding the focus */
    var a = document.activeElement, pop = $('cal-pop');
    if (a && pop && pop.contains(a) && a.blur) a.blur();
    CAL.form = null; CAL.formErr = '';
  }
  function calHM(d) { return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2); }
  /* the New event form, from the button: the next whole hour today */
  function calForm(d) {
    if (!CAL.writable.length) { toast('None of your calendars can take a new event from here.', ''); return; }
    var e = new Date(d.getTime() + 3600000);
    CAL.form = {title: '', calendar: CAL.writable.filter(function (n) { return !CAL.off[n]; })[0] || CAL.writable[0], day: isoLocal(d).slice(0, 10), all_day: false, start: calHM(d),
                end: e.getDate() === d.getDate() ? calHM(e) : '23:59', place: '', notes: ''};
    CAL.formErr = ''; renderCal();
    var t = $('cal-f-title'); if (t) t.focus();
  }
  function calSave() {
    if (CAL.saving || !CAL.form) return;
    CAL.saving = true; CAL.formErr = ''; renderCal();
    mailCsrf().then(function (tok) {
      return fetch('api/calendar/add', {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-Brief-Csrf': tok}, body: JSON.stringify(CAL.form)});
    }).then(function (r) { return r.status === 404 ? {ok: false, error: 'Adding events works on the page served from your computer.'} : r.json(); }).then(function (j) {
      CAL.saving = false;
      if (!j || !j.ok) { CAL.formErr = (j && j.error) || 'That did not go through. Nothing was added.'; renderCal(); return; }
      CAL.list = CAL.list.filter(function (x) { return x.id !== j.event.id; }).concat([calEvent(j.event)]);
      if (CAL.names.indexOf(j.event.calendar) < 0) CAL.names.push(j.event.calendar);
      calShut(); if (CAL.ec) CAL.ec.setOption('events', calShown());
      toast('Added to ' + j.event.calendar + '.', ''); renderCal();
    }, function () { CAL.saving = false; CAL.formErr = 'This page couldn\'t reach me. Check the connection and try again.'; renderCal(); });
  }
  function calClick(a, b) {
    if (a === 'cal-key') {
      var n = b.getAttribute('data-c');
      if (CAL.off[n]) delete CAL.off[n]; else CAL.off[n] = 1;
      keepSet('caloff', JSON.stringify(CAL.off));
      if (CAL.ec) CAL.ec.setOption('events', calShown());
      renderCal(); return true;
    }
    if (a === 'cal-new') { var d = new Date(); d.setMinutes(0, 0, 0); d.setHours(d.getHours() + 1); calForm(d); return true; }
    if (a === 'cal-save') { calSave(); return true; }
    if (a === 'cal-cancel') { calShut(); renderCal(); return true; }
    return false;
  }
  var CAL_COLORS = ['#4f86f7', '#2fa874', '#d9971c', '#d9534f', '#8e63e8', '#1aa3a3', '#d65f9e', '#7d8799'];
  function calColor(name) { return CAL_COLORS[Math.max(0, CAL.names.indexOf(name)) % CAL_COLORS.length]; }
  function calLib() {
    if (window.EventCalendar) return Promise.resolve();
    if (!CAL.lib) {
      var css = document.createElement('link'); css.rel = 'stylesheet'; css.href = 's/ec/event-calendar.min.css'; document.head.appendChild(css);
      CAL.lib = new Promise(function (ok, bad) { var sc = document.createElement('script'); sc.src = 's/ec/event-calendar.min.js'; sc.onload = ok; sc.onerror = function (e) { CAL.lib = null; sc.remove(); bad(e); }; document.head.appendChild(sc); });
    }
    return CAL.lib;
  }
  function calLoad() {
    CAL.busy = true;
    Promise.all([calLib(), mailJson('api/calendar/events')]).then(function (r) {
      var j = r[1]; CAL.busy = false; CAL.at = Date.now();
      if (j && j.hosted) { CAL.hosted = true; renderCal(); return; }
      if (!j || !j.ok) { CAL.err = (j && j.error) || 'Your calendar could not be read just now.'; renderCal(); return; }
      CAL.err = ''; CAL.names = j.calendars || []; CAL.writable = j.writable || []; CAL.ev = {};
      CAL.list = (j.events || []).map(calEvent);
      if (CAL.ec) CAL.ec.setOption('events', calShown());
      else CAL.ec = EventCalendar.create($('cal-ec'), {
        view: window.innerWidth < 700 ? 'listWeek' : 'timeGridWeek', events: calShown(), nowIndicator: true, dayMaxEvents: true, scrollTime: '07:00:00',
        headerToolbar: {start: 'prev,next today', center: 'title', end: 'timeGridDay,timeGridWeek,dayGridMonth,listWeek'},
        buttonText: {today: 'Today', timeGridDay: 'Day', timeGridWeek: 'Week', dayGridMonth: 'Month', listWeek: 'List'},
        eventClick: function (info) { CAL.show = String(info.event.id); renderCal(); }
      });
      renderCal();
    }, function () { CAL.busy = false; CAL.at = Date.now(); CAL.err = 'Your calendar couldn\'t be reached. This page tries again in a minute.'; renderCal(); });
  }
  function calWhen(e) {
    var a = D(e.start), b = D(e.end);
    if (!a) return e.start;
    if (e.all_day) { var last = b ? new Date(b.getTime() - 86400000) : a; return fmtD(a) + (last > a ? ' to ' + fmtD(last) : '') + ', all day'; }
    return fmtD(a) + ', ' + fmtT(a) + (b ? ' to ' + (b.toDateString() === a.toDateString() ? '' : fmtD(b) + ', ') + fmtT(b) : '');
  }
  function renderCal() {
    var el = $('sec-calendar'), box = $('calendar');
    if (!el || !box) return;
    el.hidden = hiddenSec('calendar', {});
    if (el.hidden) return;
    if (!$('cal-ec')) box.innerHTML = '<div id="cal-say"></div><div id="cal-ec"></div><div id="cal-pop"></div>';
    var say = !S.db || CAL.hosted ? (S.live === 'off' || CAL.hosted ? 'The calendar works on the page served from your computer.' : '') : CAL.err ||
      (!CAL.ec ? 'Opening your calendar.' : CAL.names.length ? '' : 'I don\'t have any events yet. Calendars connected with /assistant:change accounts show here.');
    var keys = CAL.ec && (CAL.names.length || CAL.writable.length) ? '<div class="cal-keys">' + CAL.names.map(function (n) {      /* a calendar's box: press it to hide or show its events */
      var off = !!CAL.off[n];
      return '<button class="cal-key' + (off ? ' off' : '') + '" type="button" data-s="cal-key" data-c="' + h(n) + '" aria-pressed="' + !off + '" title="' + (off ? 'Show ' : 'Hide ') + h(n) + '"><i data-col="' + calColor(n) + '"></i>' + h(n) + '</button>';
    }).join('') + (CAL.writable.length ? '<button class="btn" type="button" data-s="cal-new">New event</button>' : '') + '</div>' : '';
    setHtml($('cal-say'), (say ? '<div class="none">' + h(say) + '</div>' : '') + keys);
    Array.prototype.forEach.call(document.querySelectorAll('.cal-keys i[data-col]'), function (k) { k.style.background = k.getAttribute('data-col'); });
    var e = CAL.ev[CAL.show], f = CAL.form;
    if (f) {
      var fl = function (k, lab, html) { return '<label for="cal-f-' + k + '">' + lab + '</label>' + html; };
      var inp = function (k, type, more) { return '<input type="' + type + '" id="cal-f-' + k + '" data-calf="' + k + '" value="' + h(f[k]) + '"' + (more || '') + '>'; };
      setHtml($('cal-pop'), '<div class="cmd-pop" data-s="cal-cancel"><div class="cmd-box cal-box" role="dialog" aria-modal="true" aria-labelledby="cal-f-h"><h3 id="cal-f-h">New event</h3><div class="cal-form" data-key="cal-form:' + (f.all_day ? 'a' : 't') + '">' +
        fl('title', 'Title', inp('title', 'text', ' autocomplete="off" maxlength="300"')) +
        fl('calendar', 'Calendar', '<select id="cal-f-calendar" data-calf="calendar">' + CAL.writable.map(function (n) { return '<option' + (n === f.calendar ? ' selected' : '') + '>' + h(n) + '</option>'; }).join('') + '</select>') +
        fl('day', 'Day', inp('day', 'date')) +
        '<label class="check" for="cal-f-all_day"><input type="checkbox" id="cal-f-all_day" data-calf="all_day"' + (f.all_day ? ' checked' : '') + '> All day</label>' +
        (f.all_day ? '' : '<div class="two">' + fl('start', 'Starts', inp('start', 'time')) + fl('end', 'Ends', inp('end', 'time')) + '</div>') +
        fl('place', 'Place', inp('place', 'text', ' autocomplete="off" maxlength="300"')) +
        fl('notes', 'Notes', '<textarea id="cal-f-notes" data-calf="notes" rows="3" maxlength="4000" autocomplete="off">' + h(f.notes) + '</textarea>') + '</div>' +
        (CAL.formErr ? '<div class="err" role="alert">' + h(CAL.formErr) + '</div>' : '') +
        '<div class="acts"><button class="btn primary" type="button" data-s="cal-save"' + (CAL.saving ? ' disabled' : '') + '>' + (CAL.saving ? 'Saving' : 'Save') + '</button>' +
        '<button class="btn" type="button" data-s="cal-cancel">Cancel</button></div></div></div>');
    } else setHtml($('cal-pop'), e ? '<div class="cmd-pop" data-s="cal-close"><div class="cmd-box cal-box" role="dialog" aria-modal="true" aria-labelledby="cal-pop-t"><h3 id="cal-pop-t">' + h(e.title) + '</h3><dl>' +
      '<dt>When</dt><dd>' + h(calWhen(e)) + '</dd>' + (e.location ? '<dt>Where</dt><dd>' + h(e.location) + '</dd>' : '') +
      '<dt>Calendar</dt><dd>' + h(e.calendar) + '</dd>' + (e.description ? '<dt>About</dt><dd>' + h(e.description) + '</dd>' : '') +
      '</dl><div class="acts"><button class="btn" type="button" data-s="cal-close">Close</button></div></div></div>' : '');
    /* again every ten minutes while it is shown; after a failure, once a minute (never at every redraw) */
    if (S.db && !CAL.hosted && !CAL.busy && (!CAL.at || Date.now() - CAL.at > (CAL.err ? 60000 : 600000))) calLoad();
  }
  /* What is changed only with a command in Claude on the computer: a Tools entry each, whose button shows the command to copy */
  function cmdList() { return sAll().commands || []; }
  function cmdItems() {
    return cmdList().map(function (c) {
      return '<li><b>' + h(c.name) + infoBtn(c.name, c.explain) + '</b><span class="say">' + h(c.words) + '</span>' + (c.now ? '<span class="say">' + h(c.now) + '</span>' : '') +
        '<button class="btn" type="button" data-s="cmd-show" data-c="' + h(c.id) + '" aria-haspopup="dialog">Show the command</button></li>';
    }).join('');
  }
  function cmdPop() {
    var c = cmdList().filter(function (x) { return x.id === SET.cmd; })[0];
    if (!c) return '';
    return '<div class="cmd-pop" data-s="cmd-close"><div class="cmd-box" role="dialog" aria-modal="true" aria-labelledby="cmd-pop-t"><h3 id="cmd-pop-t">' + h(c.name) + '</h3>' +
      '<div class="pt-cmd"><code>' + h(c.command) + '</code><button class="btn primary" type="button" data-s="cmd-copy" data-c="' + h(c.command) + '">Copy</button></div>' +
      '<p class="say">' + h(c.where) + '</p><div class="acts"><button class="btn" type="button" data-s="cmd-close">Close</button></div></div></div>';
  }
  /* The (i) beside a setting's name: it opens what that setting is for, in the command pop-up's box. The words come with the
     setting (settings_data.py, tools.py, project_tools.py, a mod's own); those the page draws itself are here. None, no (i). */
  var INFO_X = {open_marks_read: "Marks an unread email as read in your mailbox when you open it. It is on by default and applies to this device only, so each phone or computer has its own choice. Changes at once and needs no Save.",
    mail_rules: "Lists the rules your Gmail and Outlook mailboxes run on their own side, in plain words, and lets you add one or delete one. You pick the sender, subject words or recipient and then whether to move the mail to a folder or label, archive it, mark it read, or star it (important in Outlook). You see the rule in words first and it is made only when you press Save this rule, and it keeps working even when your computer is off.",
    change_password: "Sets a new password for this page's address, with the current one asked for and the new one at least 10 characters. It signs out other browsers there, and if your page is also at another address you change it there too.",
    sign_out_everywhere: "Ends every sign-in at this address on every device, including this one. You then sign in again with your password.",
    learn_now: "Learns your writing style from the emails, texts and other messages you sent and saves it, keeping your own edits to the lists. It only runs when you press it, and drafts use the saved style from then on.",
    reload_mail: "Rereads the whole history of every Gmail and Microsoft mailbox, a portion at each check, and shows how far each mailbox has got. Stored email is kept and never deleted. You are asked to confirm before it starts.",
    rebuild_cards: "I rewrite every open card with your current rules the next time I check for messages. Your answers and snooze dates stay, and I save every card first so Put them back returns them exactly as they were. I ask you to confirm before I start.",
    home_screen: "Puts this page on your phone's home screen like an app. Add it now uses the browser's own prompt where it offers one, otherwise Show me how gives the steps for your phone.",
    manual: "Opens the manual that explains how your page works. It appears only when your page server has the manual."};
  function infoBtn(title, text) {
    return text ? '<button class="info" type="button" data-s="info-show" data-t="' + h(title) + '" data-x="' + h(text) + '" aria-haspopup="dialog" aria-label="What ' + h(title) + ' is for">i</button>' : '';
  }
  function infoPop() {
    var x = SET.info;
    if (!x) return '';
    return '<div class="cmd-pop" data-s="info-close"><div class="cmd-box" role="dialog" aria-modal="true" aria-labelledby="info-pop-t"><h3 id="info-pop-t">' + h(x.t) + '</h3>' +
      '<p class="say">' + h(x.x) + '</p><div class="acts"><button class="btn" type="button" data-s="info-close">Close</button></div></div></div>';
  }
  /* ---- the definitions ---- */
  function sAll() {
    var d = S.meta && S.meta.settings_defs;
    return d && (d.settings || []).length ? d : {groups: [], settings: []};
  }
  function sOf(g) { return (sAll().settings || []).filter(function (x) { return x && x.group === g; }); }
  function sDef(g, f) { return sOf(g).filter(function (x) { return x.id === f; })[0] || null; }
  function sNow(x) { if (x.value !== undefined) return x.value; var st = setts(); return st && st[x.group] ? st[x.group][x.id] : ''; }
  function sChoices(x) { return (x.choices || []).map(function (c) { return c && typeof c === 'object' ? [c.value, c.label != null ? c.label : c.value, !!c.disabled] : [c, c]; }); }
  function sRankNow(x) { var d = sDraft(x.group)[x.id], now = sNow(x); return (Array.isArray(d) ? d : Array.isArray(now) ? now : []).slice(); }
  function sFixed(x) { return x.can_change === false || x.control === 'words'; }
  /* a value shown in words, for a setting the page may not change */
  function sShow(x, v) {
    var hit = sChoices(x).filter(function (c) { return String(c[0]) === String(v); })[0];
    if (hit) return String(hit[1]);
    if (v === true) return 'On';
    if (v === false) return 'Off';
    if (v && typeof v === 'object') return Array.isArray(v) ? (v.length ? v.join(', ') : 'None') : JSON.stringify(v);
    return v == null || v === '' ? 'Not set' : String(v);
  }
  /* The arrangement control holds two things: where each module goes (top, left, right, bottom, in order) and, when the
     engine sends it, which are switched off. Modules are dragged between the areas here, or moved with the buttons; the
     page itself has nothing to drag. */
  function sOrder() {
    var ox = sDef('page', 'order'), hx = sDef('page', 'hidden'), d = sDraft('page'), o = layoutOf(d.order || (ox && sNow(ox)) || {});
    var hid = ox && Array.isArray(ox.hidden) ? ox.hidden : hx ? sNow(hx) : null;
    o.hidden = (d.hidden || hid || []).slice();
    o.ticks = !!hid && !(hx && sFixed(hx));
    o.titles = Object.assign({}, d.titles || (ox && ox.titles) || {});
    o.open = (d.open_if_filled || (ox && Array.isArray(ox.open_if_filled) ? ox.open_if_filled : null) || ['about']).slice();
    return o;
  }
  function sSections() {
    var o = sOrder(), out = '<div class="wnote">Arrange the page like this: top across, then left and right side by side, then bottom across (on a phone they follow one another). Drag a part by its dotted handle, with a finger or the mouse. With the keyboard, press Space on the handle, use the arrow keys, and press Space again to put it down. A name you type is the heading on the page; leave it empty for the usual one. A part ticked "Only show when it has something in it" is out of the page, heading and all, while it is empty.</div><div class="lay-grid">';
    AREAS.forEach(function (ar) {
      out += '<div class="lay-cell lay-' + ar + '"><div class="set-sub">' + AREA_NAME[ar] + '</div><div class="lay-area" data-area="' + ar + '">';
      if (!o[ar].length) out += '<div class="wnote lay-empty">Nothing here. Drag a part here to put it here.</div>';
      o[ar].forEach(function (nm) {
        var id = 'set-show-' + nm.replace(/[^a-z0-9]/gi, '-'), nmH = h(secDefault(nm)), lifted = LAY.kb === nm;
        out += '<div class="set-line lay-mod' + (lifted ? ' lifted' : '') + '" data-mod="' + h(nm) + '">' +
          '<button class="btn lay-grip" type="button" data-grip="' + h(nm) + '" aria-pressed="' + lifted + '" title="Drag to move" aria-label="Move ' + nmH + ': drag it, or press Space to pick it up, use the arrow keys, press Space to put it down"></button>' +
          (o.ticks ? '<label class="check nm" for="' + id + '"><input type="checkbox" id="' + id + '" data-set="page.hidden" data-name="' + h(nm) + '"' + (o.hidden.indexOf(nm) < 0 ? ' checked' : '') + '> ' + nmH + '</label>' : '<span class="nm">' + nmH + '</span>') +
          ('<input type="text" autocomplete="off" name="section-name" class="lay-title" maxlength="60" data-set="page.titles" data-name="' + h(nm) + '" value="' + h(o.titles[nm] || '') + '" placeholder="' + nmH + '" aria-label="Name of ' + nmH + ' on the page">') +
          ('<label class="check lay-open"><input type="checkbox" data-set="page.open_if_filled" data-name="' + h(nm) + '"' + (o.open.indexOf(nm) >= 0 ? ' checked' : '') + '> Only show when it has something in it</label>') +
          '</div>';
      });
      out += '</div></div>';
    });
    return out + '</div>' + (o.ticks ? '<div class="wnote">Untick a part to switch it off. A part that holds something marked important always shows, so nothing important is missed. Some parts show only when they hold something.</div>' : '');
  }
  function layMove(nm, area, before, keep) {
    var o = sOrder();
    AREAS.forEach(function (a) { o[a] = o[a].filter(function (x) { return x !== nm; }); });
    var at = before ? o[area].indexOf(before) : -1;
    if (at < 0) o[area].push(nm); else o[area].splice(at, 0, nm);
    var d = S.drafts['set:page'] || {};
    d.order = {top: o.top, left: o.left, right: o.right, bottom: o.bottom}; S.drafts['set:page'] = d; delete SET.said.page; keepDrafts(); acting = 'set:page'; render();
    if (keep) { var gg = document.querySelector('.lay-grip[data-grip="' + nm + '"]'); if (gg) gg.focus(); }
  }
  var LAY = {drag: null, kb: null};
  function layClear() { [].forEach.call(document.querySelectorAll('.lay-over,.lifted'), function (n) { n.classList.remove('lay-over'); if (!LAY.kb) n.classList.remove('lifted'); }); }
  /* touch, pen and mouse all drag through pointer events on the Move button */
  document.addEventListener('pointerdown', function (e) {
    var g = e.target.closest && e.target.closest('.lay-grip');
    if (!g || (e.pointerType === 'mouse' && e.button !== 0)) return;
    LAY.drag = {nm: g.getAttribute('data-grip')};
    try { g.setPointerCapture(e.pointerId); } catch (x) {}
    g.closest('.lay-mod').classList.add('lifted');
    e.preventDefault();
  });
  document.addEventListener('pointermove', function (e) {
    if (!LAY.drag) return;
    var el = document.elementFromPoint(e.clientX, e.clientY), a = el && el.closest('.lay-area');
    [].forEach.call(document.querySelectorAll('.lay-over'), function (n) { n.classList.remove('lay-over'); });
    if (a) a.classList.add('lay-over');
  });
  document.addEventListener('pointercancel', function () { LAY.drag = null; layClear(); });
  document.addEventListener('pointerup', function (e) {
    var d = LAY.drag;
    if (!d) return;
    LAY.drag = null; layClear();
    var el = document.elementFromPoint(e.clientX, e.clientY), ar = el && el.closest('.lay-area');
    if (!ar) return;
    var over = el.closest('.lay-mod'), before = null;
    if (over && over.getAttribute('data-mod') !== d.nm) {
      var r = over.getBoundingClientRect();
      before = e.clientY > r.top + r.height / 2 ? (over.nextElementSibling && over.nextElementSibling.getAttribute('data-mod') !== d.nm ? over.nextElementSibling.getAttribute('data-mod') : (over.nextElementSibling ? (over.nextElementSibling.nextElementSibling && over.nextElementSibling.nextElementSibling.getAttribute('data-mod')) : null)) : over.getAttribute('data-mod');
    }
    layMove(d.nm, ar.getAttribute('data-area'), before || null);
  });
  /* the keyboard: Space picks a part up, the arrows move it (Up and Down along its area and into the next one,
     Left and Right between the two middle areas), Space or Escape puts it down */
  document.addEventListener('keydown', function (e) {
    var g = e.target.closest && e.target.closest('.lay-grip');
    if (!g) return;
    var nm = g.getAttribute('data-grip');
    if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); LAY.kb = LAY.kb === nm ? null : nm; g.setAttribute('aria-pressed', String(LAY.kb === nm)); g.closest('.lay-mod').classList.toggle('lifted', LAY.kb === nm); return; }
    if (LAY.kb !== nm) return;
    if (e.key === 'Escape') { e.preventDefault(); LAY.kb = null; g.setAttribute('aria-pressed', 'false'); g.closest('.lay-mod').classList.remove('lifted'); return; }
    var k = e.key;
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].indexOf(k) < 0) return;
    e.preventDefault();
    var o = sOrder(), ar = AREAS.filter(function (a) { return o[a].indexOf(nm) >= 0; })[0], list = o[ar], i = list.indexOf(nm);
    if (k === 'ArrowUp') {
      if (i > 0) layMove(nm, ar, list[i - 1], true);
      else if (ar === 'left' || ar === 'right') layMove(nm, 'top', null, true);
      else if (ar === 'bottom') layMove(nm, 'left', null, true);
    } else if (k === 'ArrowDown') {
      if (i < list.length - 1) layMove(nm, ar, list[i + 2] || null, true);
      else if (ar === 'top') layMove(nm, 'left', o.left[0] || null, true);
      else if (ar === 'left' || ar === 'right') layMove(nm, 'bottom', o.bottom[0] || null, true);
    } else if (k === 'ArrowLeft' && ar === 'right') layMove(nm, 'left', o.left[i] || null, true);
    else if (k === 'ArrowRight' && ar === 'left') layMove(nm, 'right', o.right[i] || null, true);
  });
  /* ---- one setting, drawn by its kind of control ---- */
  function sOne(x) {
    var r = sDraw(x), ic = infoBtn(x.label || x.id, x.explain), fixed = sFixed(x), end = fixed ? '</b>' : '</label>', at = r.indexOf(end), from = fixed ? at : r.indexOf('<label');
    if (!ic || at < 0 || from < 0) return r;
    at += end.length;           /* the name and its (i) on one line: a setting's rows are a grid, one row each */
    return fixed ? r.slice(0, at) + ic + r.slice(at) : r.slice(0, from) + '<div class="set-name">' + r.slice(from, at) + ic + '</div>' + r.slice(at);
  }
  function sDraw(x) {
    var g = x.group, f = x.id, now = sNow(x), lab = h(x.label || f), help = x.help ? hc(x.help) : '', note = help ? '<div class="wnote">' + help + '</div>' : '';
    if (sFixed(x)) {
      if (now == null || now === '') return '';                       /* nothing to show yet */
      return '<div class="set-fact"><span><b>' + lab + ':</b> ' + (f === 'topic' ? '</span><div class="chan">' + h(now) + '</div><span>' : hc(sShow(x, now))) + '</span>' + (help ? '<span class="wnote">' + help + '</span>' : '') + '</div>';
    }
    if (x.control === 'long_text') return sArea(g, f, lab, now == null ? '' : now, help);
    if (x.control === 'list') return sArea(g, f, lab, (Array.isArray(now) ? now : now ? [now] : []).join('\n'), help);
    if (x.control === 'toggle') {
      var two = sChoices(x), names = two.length === 2 ? two.map(function (c) { return [c[0] ? '1' : '0', c[1]]; }) : [['0', 'Off'], ['1', 'On']];
      return sPick(g, f, lab, now ? '1' : '0', names, help);
    }
    if (x.control === 'choice' && x.says) {     /* a learning level: what the level picked does on its own, said before Save */
      var sv = x.says[String(sVal(g, f, now))];
      return sPick(g, f, lab, now, sChoices(x), (sv ? '<b>' + hc(sv) + '</b>' + (Object.keys(sDraft(g)).length ? ' Press Save to make it take effect.' : '') + (help ? '<br>' : '') : '') + help);
    }
    if (x.control === 'choice') return sPick(g, f, lab, now, sChoices(x), help);
    if (x.control === 'number') return sLabel(g, f, lab) + '<input type="number" inputmode="numeric"' + (x.min != null ? ' min="' + h(x.min) + '"' : '') + (x.max != null ? ' max="' + h(x.max) + '"' : '') + ' step="1" id="' + sId(g, f) + '" data-set="' + h(g + '.' + f) + '" value="' + h(sVal(g, f, x.placeholder && !now ? '' : now)) + '"' + (x.placeholder ? ' placeholder="' + h(x.placeholder) + '"' : '') + '>' + note;
    if (x.control === 'time') return sLabel(g, f, lab) + '<input type="time" id="' + sId(g, f) + '" data-set="' + h(g + '.' + f) + '" value="' + h(sVal(g, f, now || '')) + '">' + note;
    if (x.control === 'checks') {
      var on = (sDraft(g)[f] || now || []).map(String), cs = sChoices(x);
      return '<label>' + lab + '</label>' + cs.map(function (c, i) {
        var id = sId(g, f) + '-' + i;
        var sw = g === 'calendar' && CAL.names.indexOf(c[0]) >= 0 ? '<i class="cal-sw" data-col="' + calColor(c[0]) + '"></i>' : '';      /* its colour, where the page knows it */
        return '<label class="check" for="' + id + '"><input type="checkbox" id="' + id + '" data-set="' + h(g + '.' + f) + '" data-name="' + h(c[0]) + '"' + (on.indexOf(String(c[0])) >= 0 ? ' checked' : '') + '> ' + sw + h(c[1]) + '</label>';
      }).join('') + note;
    }
    if (x.control === 'order') return '<label>' + lab + '</label>' + sSections() + note;
    if (x.control === 'rules') return sRules(x, lab, note);
    if (x.control === 'rank') {           /* an order: each choice with Up and Down */
      var rk = sRankNow(x), nm2 = {}; sChoices(x).forEach(function (c) { nm2[c[0]] = c[1]; });
      return '<label>' + lab + '</label><ol class="set-rank">' + rk.map(function (v, i) {
        return '<li><span>' + h(nm2[v] || v) + '</span><button class="link" type="button" data-s="rank" data-set="' + h(g + '.' + f) + '" data-i="' + i + '" data-d="-1"' + (i ? '' : ' disabled') + ' aria-label="Move ' + h(nm2[v] || v) + ' up">Up</button>' +
          '<button class="link" type="button" data-s="rank" data-set="' + h(g + '.' + f) + '" data-i="' + i + '" data-d="1"' + (i < rk.length - 1 ? '' : ' disabled') + ' aria-label="Move ' + h(nm2[v] || v) + ' down">Down</button></li>';
      }).join('') + '</ol>' + note;
    }
    if (x.control === 'ladder') return sLadder(x, lab, note);
    return sText(g, f, lab, now == null ? '' : now) + note;
  }
  function renderSettings() {
    var el = $('settings'), st = setts();
    if (!el) return;
    document.documentElement.classList.toggle('set-open', !!S.panel.settings);
    if (!S.panel.settings) { el.hidden = true; return; }
    el.hidden = false;
    SET.parts = {};
    var top = '<div class="set-top"><h2>Settings' + (st && st.version ? ' <small class="set-ver">Version ' + h(st.version) + '</small>' : '') + '</h2><div class="set-acts"><button class="btn primary" type="button" data-s="save-all"' + (SET.pending ? ' disabled' : '') + '>Save</button><button class="btn" type="button" data-s="discard-all">Back</button>' + manualLink() + '</div></div>' + (SET.top ? sSaid(SET.top) : '') + toolsBlock() + mailDeviceBlock() + mailRulesBlock() + rbBlock() + ctBlock() + sPart('changes', 'Change history', ($('changes') && $('changes').innerHTML) || '<p class="say">No changes to your assistant yet.</p>');
    if (!st) { setHtml(el, top + '<div class="none">' + (S.meta ? 'Settings reach this page with my next update, within a few minutes.' : 'Settings show here once my data has reached this page.') + '</div>' + sNav() + infoPop()); return; }
    var a = S.ans && S.ans.settings, p = SET.pending;
    if (p && a && a.at === p.at && (a.status === 'done' || a.status === 'failed')) {
      var bad = a.status === 'failed' || /^Not saved/.test(String(a.outcome || ''));
      SET.said[p.g] = {text: a.outcome || (bad ? 'Not saved.' : 'Saved.'), bad: bad, warn: /pull against each other/.test(String(a.outcome || ''))};
      if (!bad) { delete S.drafts['set:' + p.g]; keepDrafts(); }
      var pg = p.g; SET.pending = p = null;
      if (bad) { SET.queue = []; SET.leave = false; setGo(pg); SET.top = {text: SET.said[pg].text, bad: true}; }   /* a refused save stays here and says why, by Save too */
      else setTimeout(sNext, 0);
    } else if (p && Date.now() - p.t > 45000) {
      SET.said[p.g] = {text: S.listening === false ? 'Saved on the page. This page can\'t reach your computer, so it takes effect when it\'s back.' : 'Saved. Your computer hasn\'t answered yet; it takes effect the next time I check for messages.', bad: false};
      delete S.drafts['set:' + p.g]; keepDrafts();
      SET.pending = p = null; setTimeout(sNext, 0);
    }
    var defs = sAll(), groups = (defs.groups || []).slice(), o = top;
    if (!(defs.settings || []).length) { setHtml(el, top + '<div class="none">Settings reach this page with my next update, within a few minutes.</div>' + sNav() + infoPop()); return; }
    /* a setting whose group the list does not name still shows, under its own name */
    (defs.settings || []).forEach(function (x) { if (x && x.group && !groups.some(function (gr) { return gr.id === x.group; })) groups.push({id: x.group, label: x.group, can_save: true}); });
    var canPw = !!(S.db && S.db.changePassword), pws = SET.pwSaid, canOut = !!(S.db && S.db.signOutAll);
    if ((canPw || canOut) && !groups.some(function (gr) { return gr.id === 'signin'; })) groups.push({id: 'signin', label: 'Sign-in', can_save: false});
    groups.forEach(function (gr) {
      var g = gr.id, list = sOf(g), inner = '', combined = list.some(function (x) { return x.control === 'order'; }), look = '';
      list.forEach(function (x) {
        if (combined && x.id === 'hidden' && x.control === 'checks') return;            /* drawn as the ticks of the order list */
        if (g === 'page' && APV_IDS[x.id] && !sFixed(x)) { if (!look) inner += '\u0001'; look += sOne(x); return; }   /* with the preview beside them */
        inner += sOne(x);
      });
      if (look) inner = inner.replace('\u0001', '<div class="apv-row"><div class="apv-ctl">' + look + '</div>' + apvBox() + '</div>');
      if (g === 'signin') inner = (canPw ? '<div class="set-sub">Change this page\'s password' + infoBtn('Change this page\'s password', INFO_X.change_password) + '</div>' +
        '<label for="set-pw-current">Current password</label><input type="password" id="set-pw-current" data-pw="current" autocomplete="current-password" value="' + h(SET.pw.current) + '">' +
        '<label for="set-pw-new1">New password (10 characters or more)</label><input type="password" id="set-pw-new1" data-pw="new1" autocomplete="new-password" value="' + h(SET.pw.new1) + '">' +
        '<label for="set-pw-again">Confirm new password</label><input type="password" id="set-pw-again" data-pw="again" autocomplete="new-password" value="' + h(SET.pw.again) + '">' +
        '<div class="acts"><button class="btn primary" type="button" data-s="pw"' + (SET.pwBusy ? ' disabled' : '') + '>Change password</button></div>' +
        (pws ? '<div class="set-said' + (pws.bad ? ' bad' : '') + '" role="status">' + h(pws.text) + '</div>' : '') +
        '<div class="wnote">Changes the password for this address only and signs out other browsers here. If the page is also at another address, change it there too.</div><hr class="set-hr">'
        : '<div class="wnote">The password cannot be changed from here.</div>') + inner;
      if (g === 'voice') {           /* the style is learned only when he asks: this button, or the Writing style builder in Tools */
        var va = S.ans && S.ans['voice-learn'];
        inner += '<div class="acts"><button class="btn" type="button" data-s="voice-learn"' + (va && va.status === 'saved' && !va.result ? ' disabled' : '') + '>Learn style now</button>' + infoBtn('Learn style now', INFO_X.learn_now) + '</div>' +
          (va && va.result ? '<div class="set-said" role="status">' + h(va.result) + '</div>' : va && va.status === 'saved' ? '<div class="set-said" role="status">Learning your style...</div>' : '');
      }
      if (gr.can_save !== false && list.some(function (x) { return !sFixed(x); })) inner += sFoot(g);
      if (g === 'signin' && canOut) inner += '<hr class="set-hr"><div class="set-sub">Sign out everywhere' + infoBtn('Sign out everywhere', INFO_X.sign_out_everywhere) + '</div><div class="wnote">Ends every sign-in at this address, on every device including this one. You sign in again with your password.</div>' +
        '<div class="acts"><button class="btn" type="button" data-s="out-all">Sign out everywhere</button></div>';
      if (inner) o += sGroup(g, h(gr.label || g), inner);
    });
    setHtml(el, o + sNav() + cmdPop() + infoPop());
    Array.prototype.forEach.call(el.querySelectorAll('i.cal-sw[data-col]'), function (k) { k.style.background = k.getAttribute('data-col'); });
    apvMount(el);
  }
  function sInput(t) {
    if (t.hasAttribute('data-pw')) { SET.pw[t.getAttribute('data-pw')] = t.value; return false; }
    var path = t.getAttribute('data-set') || '', dot = path.indexOf('.'), g = path.slice(0, dot), f = path.slice(dot + 1), d = S.drafts['set:' + g] || {}, st = setts(), x = sDef(g, f);
    if (!g || !f || !st) return false;
    if (g === 'page' && f === 'hidden' && sDef('page', 'order')) {
      var hid = sOrder().hidden.filter(function (v) { return v !== t.getAttribute('data-name'); });
      if (!t.checked) hid.push(t.getAttribute('data-name'));
      d.hidden = hid;
    } else if (g === 'page' && f === 'titles') {
      var tt = sOrder().titles; tt[t.getAttribute('data-name')] = t.value; d.titles = tt;
    } else if (g === 'page' && f === 'open_if_filled') {
      var oi = sOrder().open.filter(function (v) { return v !== t.getAttribute('data-name'); });
      if (t.checked) oi.push(t.getAttribute('data-name'));
      d.open_if_filled = oi;
    } else if (x && x.control === 'checks') {
      var nm = t.getAttribute('data-name'), on = (d[f] || sNow(x) || []).map(String).filter(function (v) { return v !== nm; });
      if (t.checked) on.push(nm);
      d[f] = on;
    } else d[f] = t.value;
    S.drafts['set:' + g] = d;
    delete SET.said[g];
    return t.tagName === 'SELECT' || t.type === 'checkbox';       /* a pick redraws its group; typing never does */
  }
  /* What a Save sends for one group: every setting in it the page may change, each in the form its control holds. */
  function sValues(g) {
    var d = sDraft(g), v = {}, bad = '', list = sOf(g), combined = list.some(function (x) { return x.control === 'order'; });
    list.forEach(function (x) {
      if (bad || sFixed(x)) return;
      var f = x.id, now = sNow(x), typed = d[f] !== undefined, raw = typed ? d[f] : now, n, hit;
      if (combined && f === 'hidden' && x.control === 'checks') return;
      if (x.control === 'list') v[f] = typed ? sLines(raw) : (Array.isArray(now) ? now : []);
      else if (x.control === 'toggle') v[f] = typed ? String(raw) === '1' : !!now;
      else if (x.control === 'choice') { hit = sChoices(x).filter(function (c) { return String(c[0]) === String(raw); })[0]; v[f] = hit ? hit[0] : raw; }
      else if (x.control === 'number') {
        n = String(raw == null ? '' : raw).trim();
        if (n !== '' && !/^\d{1,9}$/.test(n)) { bad = (x.label || f) + ': type a whole number' + (x.placeholder ? ', or leave it empty.' : '.'); return; }
        if (x.max != null && +n > x.max) { bad = (x.label || f) + ' can be ' + x.max + ' at most.'; return; }
        if (x.min != null && n !== '' && +n < x.min) { bad = (x.label || f) + ' must be ' + x.min + ' or more.'; return; }
        v[f] = n === '' ? 0 : +n;
      }
      else if (x.control === 'checks') { if (sChoices(x).length || typed) v[f] = typed ? raw : (now || []); }
      else if (x.control === 'rules') {
        var rl = sRulesNow(x), short = rl.filter(function (r) { var n = r.text.replace(/\s+/g, ' ').trim().length; return n < 8 || n > 300; })[0];
        if (short) { bad = 'A rule is one plain sentence, 8 to 300 characters. This one is not: "' + short.text + '"'; return; }
        var long = rl.filter(function (r) { return r.reason.replace(/\s+/g, ' ').trim().length > 300; })[0];
        if (long) { bad = 'A rule\'s reason is at most 300 characters. This one is longer: "' + long.reason + '"'; return; }
        v[f + '_seen'] = d[f + '__seen'] || (sNow(x) || []).map(function (r) { return r.id; }).filter(function (i) { return i != null; });
        v[f] = rl.map(function (r) { var e = {id: r.id, text: r.text.replace(/\s+/g, ' ').trim(), reason: r.reason.replace(/\s+/g, ' ').trim(), on: !!r.on}; if (r.way != null) e.way = r.way; return e; });
      }
      else if (x.control === 'ladder') {
        v[f] = sLadderNow(x).map(function (r) { return {id: r.id, kind: r.kind, area: r.area, level: r.level, on: !!r.on}; });
      }
      else if (x.control === 'order') { var o = sOrder(); v[f] = {top: o.top, left: o.left, right: o.right, bottom: o.bottom}; if (o.ticks) v.hidden = o.hidden; if (x.titles !== undefined) { v.titles = {}; Object.keys(o.titles).forEach(function (k) { var w = String(o.titles[k] || '').replace(/\s+/g, ' ').trim(); if (w) v.titles[k] = w; }); v.open_if_filled = o.open; } }
      else if (x.control === 'time') v[f] = String(raw || '');
      else if (x.control === 'rank') v[f] = sRankNow(x);
      else v[f] = String(raw == null ? '' : raw).trim();
    });
    if (bad) return bad;
    if (!Object.keys(v).length) return 'That is not something this page can save.';
    if (g === 'you' && v.first_name === '') return 'Type your first name.';
    if (g === 'alerts' && 'quiet_from' in v && 'quiet_to' in v) {
      if (!!v.quiet_from !== !!v.quiet_to) return 'Quiet hours need both times, or clear both.';
      if (v.quiet_from && v.quiet_from === v.quiet_to) return 'Quiet hours need two different times.';
    }
    return v;
  }
  function sSave(g) {
    if (SET.pending) return;
    if (!S.db) { SET.said[g] = {text: 'This page cannot save here. Sign in and open it again.', bad: true}; return; }
    var v = sValues(g);
    if (typeof v === 'string') { SET.said[g] = {text: v, bad: true}; return; }
    var rec = {id: 'settings', action: 'answer', label: 'Settings', text: JSON.stringify({settings: {group: g, values: v}}), at: isoLocal(new Date()), device: device, sent: false, status: 'saved', result: 'Saving your settings'};
    SET.pending = {g: g, at: rec.at, t: Date.now()};
    delete SET.said[g];
    S.mine.settings = {rec: rec, t: Date.now()};
    S.db.setAnswer('settings', rec).then(function () {}, function () {
      SET.pending = null; SET.queue = []; SET.leave = false; delete S.mine.settings;
      SET.said[g] = {text: 'That did not save. Check the connection and press Save again.', bad: true}; render();
    });
  }
  /* Save at the top: every part with unsaved changes is checked first (a refusal stays here, on that part, and nothing is sent);
     then the parts are saved one after another, and the page goes back to the cards once the last one is saved. */
  function sGoBack() {
    if (S.panel.settings) delete S.panel.settings;
    keepDrafts(); acting = 'compose'; render();
    window.scrollTo(0, SET.backTo || 0);
  }
  function sNext() {
    if (SET.pending || !SET.leave) return;
    var g = SET.queue.shift();
    if (g == null) { SET.leave = false; SET.top = null; sGoBack(); return; }
    sSave(g);
    if (!SET.pending) { SET.queue = []; SET.leave = false; setGo(g); }
    render();
  }
  function sSaveAll() {
    if (SET.pending) return;
    SET.top = null;
    var gs = [], bad = false;
    ((sAll().groups) || []).forEach(function (gr) { if (sDirty(gr.id)) gs.push(gr.id); });
    Object.keys(S.drafts).forEach(function (k) { if (k.slice(0, 4) === 'set:' && gs.indexOf(k.slice(4)) < 0 && sDirty(k.slice(4))) gs.push(k.slice(4)); });
    if (!S.db && gs.length) { SET.top = {text: 'This page cannot save here. Sign in and open it again.', bad: true}; render(); return; }
    gs.forEach(function (g) {
      var v = sValues(g);
      if (typeof v === 'string') { SET.said[g] = {text: v, bad: true}; if (!bad) setGo(g); bad = true; }
    });
    if (bad) { render(); return; }
    SET.queue = gs; SET.leave = true; sNext();
  }
  function sDiscardAll() {
    Object.keys(S.drafts).forEach(function (k) { if (k.slice(0, 4) === 'set:') delete S.drafts[k]; });
    SET.said = {}; SET.queue = []; SET.leave = false; SET.top = null; SET.fromRules = {};
    SET.pw = {current: '', new1: '', again: ''}; SET.pwSaid = null;
    sGoBack();
  }
  function sPassword() {
    var p = SET.pw;
    if (!p.current) { SET.pwSaid = {text: 'Type the password you use now.', bad: true}; return; }
    if (p.new1.length < 10) { SET.pwSaid = {text: 'Use 10 characters or more for the new password.', bad: true}; return; }
    if (p.new1 !== p.again) { SET.pwSaid = {text: 'The two new passwords do not match.', bad: true}; return; }
    SET.pwBusy = true; SET.pwSaid = {text: 'Changing it', bad: false};
    S.db.changePassword(p.current, p.new1, p.again).then(function (j) {
      SET.pwBusy = false;
      if (j && j.ok) { SET.pw = {current: '', new1: '', again: ''}; SET.pwSaid = {text: 'The password of the page at this address is changed. It takes effect now: use it the next time you sign in. Every other browser was signed out.', bad: false}; }
      else SET.pwSaid = {text: 'Not changed. ' + ((j && j.error) || 'The page could not change it just now.'), bad: true};
      acting = 'set:signin'; render();
    }, function () { SET.pwBusy = false; SET.pwSaid = {text: 'Not changed. The page at this address could not change it just now.', bad: true}; acting = 'set:signin'; render(); });
  }
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && SET.cmd) { SET.cmd = ''; render(); }
    if (e.key === 'Escape' && SET.info) { SET.info = null; render(); }
    if (e.key === 'Escape' && CAL.show) { CAL.show = ''; renderCal(); }
    if (e.key === 'Escape' && CAL.form) { calShut(); renderCal(); }
  });
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('[data-s]');
    if (!b) return;
    var a = b.getAttribute('data-s'), g = b.getAttribute('data-g');
    var mps = modFor(a); if (mps && mps.click && mps.click(a, b, e)) return;
    if (a === 'home-add' && HOME.prompt) {
      var pr = HOME.prompt; HOME.prompt = null;
      pr.prompt();
      if (pr.userChoice) pr.userChoice.then(function (c) { if (c && c.outcome === 'accepted') HOME.done = true; render(); });
      return;
    }
    if (a === 'home-steps') { HOME.shown = !HOME.shown; render(); return; }
    if (a === 'rank') {
      var rp = b.getAttribute('data-set') || '', rdot = rp.indexOf('.'), rg = rp.slice(0, rdot), rf = rp.slice(rdot + 1), rx = sDef(rg, rf);
      if (!rx) return;
      var rl = sRankNow(rx), ri = +b.getAttribute('data-i'), rj = ri + (+b.getAttribute('data-d'));
      if (rj < 0 || rj >= rl.length) return;
      var tmp = rl[ri]; rl[ri] = rl[rj]; rl[rj] = tmp;
      var rd = S.drafts['set:' + rg] || {}; rd[rf] = rl; S.drafts['set:' + rg] = rd; delete SET.said[rg]; keepDrafts(); render(); return;
    }
    if (a === 'sort-group') { sortSave(sortVal(), !kindsGrouped()); return; }
    if (a === 'feed-f') {
      FEED.f = b.getAttribute('data-f');
      if (FEED.f === 'held') keepFold('sec:held', true);          /* the list opens, not just its heading */
      render();
      if (b.classList.contains('held-see') && $('sec-feed')) $('sec-feed').scrollIntoView({block: 'start'});
      return;
    }
    if (a === 'rd-open') { RDO.open = !RDO.open; render(); if (RDO.open && $('sec-ready')) $('sec-ready').scrollIntoView({block: 'nearest'}); return; }
    if (a === 'set-nav') { var to = b.getAttribute('data-to') || ''; SET.nav = to ? to.split('/') : []; render(); window.scrollTo(0, 0); return; }
    if (a === 'cmd-show') { SET.cmd = b.getAttribute('data-c') || ''; render(); var cb = document.querySelector('.cmd-box [data-s="cmd-copy"]'); if (cb) cb.focus(); return; }
    if (a === 'cmd-close') { if (b.classList.contains('cmd-pop') && e.target !== b) return; SET.cmd = ''; render(); return; }
    if (a === 'info-show') { SET.info = {t: b.getAttribute('data-t') || '', x: b.getAttribute('data-x') || ''}; render(); var ib = document.querySelector('.cmd-box [data-s="info-close"]'); if (ib) ib.focus(); return; }
    if (a === 'info-close') { if (b.classList.contains('cmd-pop') && e.target !== b) return; SET.info = null; render(); return; }
    if (a === 'cmd-copy') { ptCopy(b.getAttribute('data-c'), b); return; }
    if (a === 'cal-close') { if (b.classList.contains('cmd-pop') && e.target !== b) return; CAL.show = ''; renderCal(); return; }
    if (a === 'cal-cancel' && b.classList.contains('cmd-pop') && e.target !== b) return;
    if (a.indexOf('cal-') === 0 && calClick(a, b)) return;
    if (a === 'tool-start') {
      var tid = b.getAttribute('data-t'), tl = ((S.meta && S.meta.tools) || []).filter(function (x) { return x.id === tid; })[0];
      if (!tl) return;
      talkPost('Start: ' + tl.name, 'tool:' + tid + ':' + Date.now(), 'Start ' + tl.name, null);
      jump('chat');
      return;
    }
    if (a === 'pt-open') { var ot = b.getAttribute('data-t'); PT.pick = PT.pick === ot ? '' : ot; PT.proj = ''; PT.confirm = null; PT.err = ''; render(); return; }
    if (a === 'pt-proj') { PT.proj = b.getAttribute('data-f'); PT.confirm = null; render(); return; }
    if (a === 'pt-back') { PT.proj = ''; PT.confirm = null; render(); return; }
    if (a === 'pt-go' || a === 'pt-yes') {
      var pt = ((S.meta && S.meta.ptools) || []).filter(function (x) { return x.id === b.getAttribute('data-t'); })[0];
      if (!pt || b.disabled) return;
      var pf = a === 'pt-go' ? b.getAttribute('data-f') : PT.confirm && PT.confirm.f, px = a === 'pt-go' ? b.getAttribute('data-x') : PT.confirm && PT.confirm.x;
      if (pt.op === 'remove' && a === 'pt-go') { PT.confirm = {f: pf, x: px}; render(); return; }      /* he is asked first; nothing is sent yet */
      if (pf) ptSend(pt, pf, px);
      return;
    }
    if (a === 'pt-no') { PT.confirm = null; render(); return; }
    if (a === 'pt-copy') { ptCopy(b.getAttribute('data-c'), b); return; }
    if (a === 'voice-learn') {
      if (!S.db) return;
      var vr = {id: 'voice-learn', action: 'answer', label: 'Learn style now', text: '', at: isoLocal(new Date()), device: device, sent: false, status: 'saved', result: ''};
      S.db.setAnswer('voice-learn', vr).then(function () { render(); }, function () { render(); });
      render(); return;
    }
    if (a.indexOf('mr-') === 0) { mrClick(a, b); return; }
    if (a.indexOf('rb-') === 0) { rbClick(a, b); return; }
    if (a.indexOf('ct-') === 0) { ctClick(a, b); return; }
    if (a === 'reb-ask') { REB.ask = true; render(); return; }
    if (a === 'rld-ask') { RLD.ask = true; render(); return; }
    if (a === 'rld-no') { RLD.ask = false; render(); return; }
    if (a === 'rld-go') {
      RLD.ask = false;
      if (S.db) S.db.setAnswer('mail-reload', {id: 'mail-reload', action: 'answer', label: 'Reload all email history', text: 'start', at: isoLocal(new Date()), device: device, sent: false, status: 'saved', result: ''}).then(function () { render(); }, function () { render(); });
      render(); return;
    }
    if (a === 'fresh-ask') { FRESH.ask = true; render(); return; }
    if (a === 'fresh-no') { FRESH.ask = false; render(); return; }
    if (a === 'fresh-go') {
      FRESH.ask = false;
      if (S.db) S.db.setAnswer('start-fresh', {id: 'start-fresh', action: 'answer', label: 'Start fresh', text: JSON.stringify({start_fresh: 'confirmed'}), at: isoLocal(new Date()), device: device, sent: false, status: 'saved', result: ''}).then(function () { render(); }, function () { render(); });
      render(); return;
    }
    if (a === 'reb-no') { REB.ask = false; render(); return; }
    if (a === 'reb-go') { REB.ask = false; rebuildSend('start'); render(); return; }
    if (a === 'reb-back') { rebuildSend('put_back'); render(); return; }
    if (a === 'open') {
      /* Settings covers the cards and closes back to the place he was at; the cards stay in the page, so nothing typed in one is lost */
      if (S.panel.settings) delete S.panel.settings; else { S.panel.settings = 'open'; SET.backTo = window.pageYOffset; setsShut(); }
      keepDrafts(); acting = 'compose'; render();
      window.scrollTo(0, S.panel.settings ? 0 : (SET.backTo || 0));
      return;
    }
    if (a === 'rule-add' || a === 'rule-del') {
      var rp = b.getAttribute('data-rule') || '', rdot = rp.indexOf('.'), rg = rp.slice(0, rdot), rf = rp.slice(rdot + 1), rx = sDef(rg, rf);
      if (!rx) return;
      var rl = sRulesNow(rx), rd = S.drafts['set:' + rg] || {};
      if (a === 'rule-del') {
        if (b.getAttribute('data-sure') !== '1') { b.setAttribute('data-sure', '1'); b.textContent = 'Press again to remove'; return; }
        rl.splice(+b.getAttribute('data-i'), 1);
        delete SET.said[rg];
      } else {
        var way = b.getAttribute('data-way') || '', dk = 'radd:' + rp + '|' + way, words = String(S.drafts[dk] || '').replace(/\s+/g, ' ').trim();
        if (words.length < 8 || words.length > 300) { SET.said[rg] = {text: 'A rule is one plain sentence, 8 to 300 characters.', bad: true}; SET.fromRules[rg] = true; acting = 'set:' + rg; render(); return; }
        rl.push({id: null, text: words, reason: '', way: way || null, on: true});
        delete S.drafts[dk]; delete SET.said[rg];
      }
      sRulesSeen(rx, rd);
      rd[rf] = rl; S.drafts['set:' + rg] = rd; keepDrafts(); acting = 'set:' + rg; render(); return;
    }
    if (a === 'save-all') { sSaveAll(); return; }
    if (a === 'discard-all') { sDiscardAll(); return; }
    if (a === 'save') { SET.fromRules[g] = b.getAttribute('data-from') === 'rules'; acting = 'set:' + g; sSave(g); render(); return; }
    if (a === 'reset') { delete S.drafts['set:' + g]; delete SET.said[g]; keepDrafts(); acting = 'set:' + g; render(); return; }
    if (a === 'pw') { acting = 'set:signin'; sPassword(); render(); return; }
    if (a === 'lad-add' || a === 'lad-del') {
      var lp = b.getAttribute('data-rule') || '', ldot = lp.indexOf('.'), lg = lp.slice(0, ldot), lf = lp.slice(ldot + 1), lx = sDef(lg, lf);
      if (!lx) return;
      var ll = sLadderNow(lx), ld = S.drafts['set:' + lg] || {};
      if (a === 'lad-del') {
        if (b.getAttribute('data-sure') !== '1') { b.setAttribute('data-sure', '1'); b.textContent = 'Press again to remove'; return; }
        ll.splice(+b.getAttribute('data-i'), 1);
      } else {
        var an = ladAdd(lx, lp), kl = ladKinds(lx).filter(function (k) { return String(k[0]) === String(an.kind); })[0];
        ll = ll.filter(function (r) { return !(r.kind === an.kind && String(r.area || '') === String(an.area || '')); });
        ll.push({id: null, kind: an.kind, label: kl ? kl[1] : an.kind, area: an.area, level: an.level, on: true});
        delete S.drafts['ladd:' + lp];
      }
      delete SET.said[lg]; ld[lf] = ll; S.drafts['set:' + lg] = ld; keepDrafts(); acting = 'set:' + lg; render();
      return;
    }
    if (a === 'out-all') {
      if (b.getAttribute('data-sure') !== '1') { b.setAttribute('data-sure', '1'); b.textContent = 'Press again to sign out everywhere'; return; }
      S.db.signOutAll();
      return;
    }
  });
  setInterval(function () { if (SET.pending) render(); }, 5000);
  applyLook();

  /* ---------- the whole page ---------- */
  /* ---------- a newer version of this page ---------- */
  var lastAct = Date.now(), verT = 0;
  ['keydown', 'pointerdown', 'input'].forEach(function (e) { document.addEventListener(e, function () { lastAct = Date.now(); }, true); });
  /* Never reload under his hands: not while a box has the cursor, and not within a few seconds of a key or a tap. */
  function busyHere() {
    var a = document.activeElement;
    return (a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) || Date.now() - lastAct < 6000;
  }
  function renderStrips() {
    var m = S.meta || {}, nv = $('new-version');
    if (nv && m.page_files) {
      if (!S.pageFiles) S.pageFiles = m.page_files;
      else if (m.page_files !== S.pageFiles && nv.hidden) {
        nv.innerHTML = 'A newer version of this page is ready. It loads by itself as soon as you are not typing. <button class="btn" type="button" id="load-new">Load it now</button>';
        nv.hidden = false;
        $('load-new').addEventListener('click', function () { location.reload(); });
        if (!verT) verT = setInterval(function () { if (!busyHere()) location.reload(); }, 2000);
      }
    }
  }
  /* ---------- the assistant's own section: shown only when it has a problem to report ---------- */
  function aboutLines() {
    var m = S.meta, out = [], ab = m && m.about, seen = {};
    if (!m) return out;
    function add(dot, text) { text = String(text || '').trim(); if (text && !seen[text]) { seen[text] = 1; out.push([dot, text]); } }
    var g = D((ab && ab.last_gathered) || m.gathered), mins = g ? (Date.now() - g.getTime()) / 6e4 : 1e9, every = gatherEvery(), st = setts();
    var paused = ab && ab.paused != null ? !!ab.paused : gatherPaused(), since = st && st.watch && st.watch.paused_since;
    var limit = ab && ab.limit_reached != null ? !!ab.limit_reached : !!(st && st.thinking && st.thinking.limit_reached);
    if (paused) add('warn', 'I stopped checking for new messages' + (since ? ' ' + fmtD(D(since)) + ' ' + fmtT(D(since)) : '') + '. Nothing new comes in until you turn Check for new messages back on in Settings, under Sources. Your answers on cards still work.');
    else if (mins > (every === 15 ? 40 : every * 2 + 10)) add('crit', 'I\'m behind on checking for new messages. ' + (g ? 'I last checked ' + fmtD(g) + ' ' + fmtT(g) + '.' : 'This page doesn\'t know when I last checked.'));
    if (limit) add('warn', 'I\'ve reached today\'s limit on AI use' + (st && st.thinking && st.thinking.daily_limit ? ' (' + st.thinking.runs_today + ' of ' + st.thinking.daily_limit + ')' : '') + '. I read nothing new until midnight, so cards wait. An answer you type is saved, and I read it first tomorrow. The limit is in Settings, under AI and usage.');
    ((ab && ab.problems) || m.problems || []).forEach(function (p) {
      var tx = clk(p && typeof p === 'object' ? p.text : p);
      if (S.gmNow != null && /^Google Messages/.test(tx)) return;        /* that line is only as new as the last check; the live one below replaces it */
      add('warn', tx);
    });
    if (S.gmNow) add('warn', S.gmNow);
    if (S.listening === false) add('crit', 'This page can\'t reach your computer. What you press is saved until it\'s back.');
    if (S.note) add('warn', S.note);
    return out;
  }
  function renderAbout() {
    var sec = $('sec-about'), lines = aboutLines();
    if (!sec) return 0;
    sec.hidden = hiddenSec('about', {about: lines.some(function (l) { return l[0] === 'crit'; })});
    $('n-about').textContent = lines.length ? lines.length : '';
    setHtml($('about'), lines.length ? '<ul class="about-list">' + lines.map(function (l) { return '<li><span class="dot ' + l[0] + '"></span><span>' + h(l[1]) + '</span></li>'; }).join('') + '</ul>' : '<div class="none">No errors.</div>');
    return lines.length;
  }

  function render() {
    if (S.view) viewDraw();
    sortSettle();
    applyLook();
    showFolds();
    renderTalk();
    settleSends();
    renderWrite();
    renderStrips();
    var act = document.activeElement, actId = act && act.id, selS = null, selE = null;
    if (act && act.tagName === 'TEXTAREA') { selS = act.selectionStart; selE = act.selectionEnd; }
    var all = S.items, by = {decide: [], words: [], task: [], small: [], tracked: [], motion: [], fyi: [], someday: [], done: [], closed: [], 'new': [], answered: []};
    var shown = 0, total = 0, ages = {a0: 0, a1: 0, a2: 0, a3: 0}, newN = 0, imp = 0, due = 0, openN = {}, impIn = {};
    all.forEach(function (it) {
      /* An item he answered here stays in one place from the press until the answer is cleared, whatever state the engine
         moves it to meanwhile: put off with Later, under Waiting on others until it comes back; anything else, under Done. */
      var s = sect(it), a = ansOf(it), back = returned(it, a), isR = rdIs(it) && it.state !== 'done';
      if (s !== 'done' && onShelf(a)) s = 'someday';                    /* he just put it on the Someday shelf */
      if (it.old_cards && s !== 'done' && !oldRows(it).length && Object.keys(S.oldDone[it.key] || {}).length) return;      /* every row answered: the asking card is finished */
      var gone = s !== 'done' && s !== 'someday' && away(it, a), open = isOpenSect(s) && (!a || back);
      if (s === 'done' && a && ((a.action === 'done' && a.label === 'Put away') || isLater(a))) return;      /* put away: off the page at once */
      total++;
      if (isNew(it)) newN++;
      if (open) { ages[bucket(it)]++; if (!isR) openN[s] = (openN[s] || 0) + 1; if (it.importance) imp++; if (it.due_date && it.due_date <= today()) due++; }
      if (it.importance && (open || s === 'fyi')) impIn[SEC_OF[s] || 'decide'] = 1;
      if (isR) return;                                                 /* in "Ready to send" */
      if (match(it)) { if (gone && isLater(a)) by.someday.push(it); else if (gone) by.answered.push(it); else if (s === 'done' && closedOnly(it)) by.closed.push(it); else by[s].push(it); shown++; }
    });
    ['small', 'tracked', 'motion', 'fyi', 'someday', 'answered', 'closed', 'done'].forEach(function (k) { by[k] = sortList(by[k]); });
    /* "Yours to decide" is ONE list in the engine's rank order; the line names the first card of that list, so both always agree */
    var byS = {}, secOf = function (it) { return byS[it.key] || 'decide'; };
    ['decide', 'words', 'task', 'new'].forEach(function (k) { by[k].forEach(function (it) { byS[it.key] = k; }); });
    by.need = sortList(by.decide.concat(by.words, by.task, by['new']));
    $('nt-decide').textContent = sortNote();
    $('nt-tracked').textContent = sortNote();
    function n(k) { return openN[k] || 0; }

    var m = S.meta, g = m && D(m.gathered), filt = S.q || S.by || S.age;
    var L = (m && m.labels) || {};
    $('title').textContent = (m && m.page_title) || 'Your desk';
    applyTitles();
    $('sec-small').hidden = !by.small.length || hiddenSec('small', impIn);
    ['decide', 'tracked', 'today', 'handled'].forEach(function (nm) { $('sec-' + nm).hidden = hiddenSec(nm, impIn); });
    $('sec-fyi').hidden = !by.fyi.length || hiddenSec('fyi', impIn);
    $('sec-someday').hidden = !by.someday.length || hiddenSec('someday', impIn);
    S.impIn = impIn;
    placeSections();
    renderTop();

    $('f-clear').hidden = !filt;
    $('f-shown').textContent = filt ? 'Showing ' + shown + ' of ' + total : '';

    var emptyWord = filt ? 'Nothing here matches what you are showing.' : null;
    var dec = '';
    if (by.need.length) dec = listHtml(by.need.map(function (it) { return [it, secOf(it)]; }), 'decide');
    setHtml($('decide'), dec || '<div class="none">' + (emptyWord || (m ? 'Nothing waits on you right now.' : 'Decisions that are yours will show here.')) + '</div>');
    /* A folded heading says how many cards are behind it, counted from the cards themselves. */
    $('n-decide').textContent = !m ? '' : shut('decide') ? howMany(by.decide.length + by.words.length + by.task.length + by['new'].length) : (n('decide') + n('words') + n('task')) + ' open';

    setHtml($('small'), by.small.length ? listHtml(by.small.map(function (it) { return [it, 'small']; }), 'small')
      : '<div class="none">' + (emptyWord || (m ? (L.small_none || 'No quick question is open right now.') : (L.small_none_idle || 'Quick questions will show here.'))) + '</div>');
    $('n-small').textContent = !m ? '' : shut('small') ? howMany(by.small.length) : n('small') + ' open';

    var om = '';
    if (groupMode() !== 'none') om = by.tracked.length + by.motion.length ? listHtml(by.tracked.map(function (it) { return [it, 'tracked']; }).concat(by.motion.map(function (it) { return [it, 'motion']; })), 'tracked') : '';
    else {
      if (by.tracked.length) om += cards(by.tracked, 'tracked');
      if (by.motion.length) om += by.tracked.length ? group('motion', h(L.motion_other || 'Waiting on someone else'), by.motion, 'motion') : cards(by.motion, 'motion');
    }
    setHtml($('tracked'), om || '<div class="none">' + (emptyWord || (m ? (L.tracked_none || 'Nothing is waiting right now.') : (L.tracked_none_idle || 'Things someone else is working on will show here.'))) + '</div>');
    $('n-tracked').textContent = !m ? '' : shut('tracked') ? howMany(by.tracked.length + by.motion.length) : String(by.tracked.length + by.motion.length);

    /* things that need nothing: short cards, one Got it each, and one press for all of them */
    var open1 = by.fyi.filter(function (it) { return !ansOf(it) || returned(it, ansOf(it)); }), gp = S.ans.press;
    S.fyiShown = open1.map(function (it) { return it.id; });
    setHtml($('fyi'), !by.fyi.length ? '' : '<div class="sec-top"><button class="btn" data-a="gotit-all"' + (open1.length ? '' : ' disabled') + '>Done, all</button>' +
      (S.err.press ? '<span class="err" role="alert">' + h(S.err.press) + '</span>' : gp && gp.status === 'failed' && pressName(gp) === 'got_it_all' ? '<span class="err" role="alert">' + hc(gp.outcome || 'Those cards could not be marked Done just now.') + '</span>' : '') + '</div>' + listHtml(by.fyi.map(function (it) { return [it, 'fyi']; }), 'fyi'));
    $('n-fyi').textContent = by.fyi.length ? String(by.fyi.length) : '';
    setHtml($('someday'), by.someday.length ? listHtml(by.someday.map(function (it) { return [it, 'someday']; }), 'someday') : '');
    $('n-someday').textContent = by.someday.length ? String(by.someday.length) : '';

    var hf = handledHtml(by);
    setHtml($('handled'), hf || '<div class="none">' + (emptyWord || (m ? 'Nothing is done yet.' : 'What you answered and what is done will show here.')) + '</div>');
    $('n-handled').textContent = !m ? '' : shut('handled') ? howMany(by.answered.length + by.closed.length + by.done.length) : String(by.answered.length);

    renderToday(); renderRoadmaps(); renderHeld(); renderSaidSo(); renderChanges(); renderReady(); renderMail(); renderTexts(); renderCal(); renderFeed(); modLoad(); modEach(function (p) { if (p.render) p.render(); }); renderFoot(); fillBy(); renderSettings();
    checkThink();
    rmSync();
    acting = null;
    if (actId) { var el = $(actId); if (el && el !== document.activeElement) { el.focus(); if (selS != null) { try { el.setSelectionRange(selS, selE); } catch (e) {} } } }
  }
  function renderToday() {
    var m = S.meta, days = m && m.today && m.today.days, o = '';
    var onCal = 0, t0 = today();
    (days || []).forEach(function (d) { if (d.date >= t0) onCal += (d.events || []).length; });
    $('td-note').textContent = fmtD(new Date()) + (days && shut('today') ? ', ' + onCal + ' on the calendar' : '');
    if (!days) { $('agenda').innerHTML = '<li class="quiet">' + (m ? 'The calendar has not reached this page yet.' : 'Your calendar will show here.') + '</li>'; return; }
    var t = today(), seen = 0;
    days.forEach(function (d) {
      if (d.date < t) return;
      if (d.date !== t) o += '<li class="day">' + h(fmtD(D(d.date))) + '</li>';
      if (!(d.events || []).length) o += '<li class="quiet">Nothing on the calendar.</li>';
      (d.events || []).forEach(function (e) {
        seen++;
        var tt = e.start && !e.all_day ? fmtT(D(d.date + 'T' + e.start)) + (e.end ? ' to ' + fmtT(D(d.date + 'T' + e.end)) : '') : 'All day';
        o += '<li><span class="t">' + h(tt) + '</span><span>' + h(e.title) + (e.location ? '<span class="where">' + h(e.location) + '</span>' : '') + '</span></li>';
      });
    });
    $('agenda').innerHTML = o || '<li class="quiet">Nothing on the calendar.</li>';
  }
  /* The optional roadmap piece: one fold per project it is applied to. The page's data carries nothing
     about roadmaps until the owner applies the piece, and then this part stays hidden. Reading only. */
  var RM_DOT = {'Being worked on now': 'warn', 'Built, waiting to be merged': 'warn', 'Ready, waiting for your look': 'crit', 'Ready, known fault': 'crit', 'Done, confirmed': 'ok'};
  /* A roadmap may word its statuses its own way: one not in the list is coloured by what it plainly says. */
  function rmDot(s) {
    if (RM_DOT[s]) return RM_DOT[s];
    s = String(s || '').toLowerCase();
    if (/^done/.test(s)) return 'ok';
    if (/fault|waiting for .*look/.test(s)) return 'crit';
    if (/^being |waiting to be merged/.test(s)) return 'warn';
    return '';
  }
  /* the short summary, shown until the whole roadmap reaches the page (or in a browser too old to draw it) */
  function roadmapHtml(r, i) {
    var k = 'rm:' + r.key, rows = r.rows || [], o = '', tally = '', last = D(r.changed);
    if (!r.note) {
      tally = '<span class="chip">' + (r.checks_waiting ? '<span class="dot crit"></span>' : '') + 'Checks to try <b>' + (r.checks_waiting || 0) + '</b></span>' +
        '<span class="chip">' + (r.questions_open ? '<span class="dot crit"></span>' : '') + 'Questions open <b>' + (r.questions_open || 0) + '</b></span>' +
        (last ? '<span class="chip">Changed <b>' + h(fmtDT(last)) + '</b></span>' : '');
    }
    o += '<details class="fold rm' + (i ? '' : ' first') + '" data-d="' + h(k) + '"' + (S.open[k] === false ? '' : ' open') + '><summary><span class="rm-name">' + h(r.name) + '</span><span class="rm-tally">' + tally + '</span></summary><div class="rm-in">';
    if (!r.note) o += '<div class="wnote">The whole roadmap has not reached this page yet. This is its short summary.</div>';
    if (r.note) o += '<div class="detail">' + h(r.note) + '</div>';
    if ((r.next || []).length) o += '<dl class="rec">' + r.next.map(function (n) { return '<dt>' + h(n.label) + '</dt><dd>' + h(n.text) + '</dd>'; }).join('') + '</dl>';
    if (rows.length) {
      var inOrder = function (x) { return x.kind === 'step' || x.kind === 'phase'; };
      var main = rows.filter(inOrder), extra = rows.filter(function (x) { return !inOrder(x); });
      var tr = function (x) {
        return '<tr' + (x.sub ? ' class="sub"' : '') + '><td>' + (x.n ? '<span class="part">' + h(x.n) + '</span>' : '') + h(x.name) + '</td><td><span class="st"><span class="dot ' + rmDot(x.status) + '"></span>' + h(x.status) + '</span></td></tr>';
      };
      o += '<div class="lines-wrap"><table class="rm-rows"><thead><tr><th>Row</th><th>Status</th></tr></thead><tbody>' + main.map(tr).join('') +
        (extra.length ? '<tr class="grp"><td colspan="2">Other work</td></tr>' + extra.map(tr).join('') : '') + '</tbody></table></div>';
      if (r.rows_total > rows.length) o += '<div class="kv">Showing the first ' + rows.length + ' of ' + r.rows_total + ' rows.</div>';
    } else if (!r.note) o += '<div class="detail">Nothing is on this roadmap yet.</div>';
    var foot = [];
    if (last) foot.push('Last changed <span class="mono">' + h(fmtD(last) + ' ' + fmtT(last)) + '</span>.');
    if (r.link && /^https:\/\/claude\.ai\//.test(r.link)) foot.push('<a class="link" href="' + h(r.link) + '" target="_blank" rel="noopener noreferrer">Open the full roadmap</a> to mark checks and answer questions.');
    if (foot.length) o += '<div class="kv">' + foot.join(' ') + '</div>';
    return o + '</div></details>';
  }
  function renderRoadmaps() {
    var list = (S.meta && S.meta.roadmaps) || [], left = $('area-left'), keep = {};
    list.forEach(function (r) {
      var id = 'sec-rm-' + r.key, sec = $(id);
      keep[id] = 1;
      if (!sec) {
        sec = document.createElement('section');
        sec.id = id;
        sec.setAttribute('aria-label', 'Roadmap: ' + r.name);
        sec.innerHTML = '<div class="sec-h" data-fold="' + h('rm:' + r.key) + '" role="button" tabindex="0" aria-expanded="true"><h2></h2><span class="note">Roadmap</span></div><div class="rm-body"></div><div class="rm-slot"><div class="rm-sent" role="status"></div></div>';
        if (left) left.appendChild(sec);
      }
      sec.querySelector('h2').textContent = secTitle('rm:' + r.key) || r.name;
      sec.hidden = hiddenSec('rm:' + r.key, S.impIn || {});
      /* the whole roadmap is drawn in the section itself, kept apart from the summary so a redraw never takes it out */
      var whole = !!rmDoc(r.key) && rmCan(), slot = sec.querySelector('.rm-slot'), inst = whole ? rmMount(r.key) : RM.inst[r.key];
      if (inst && inst.host.parentNode !== slot) slot.appendChild(inst.host);
      if (inst) inst.host.hidden = !whole;
      setHtml(sec.querySelector('.rm-body'), whole ? '' : roadmapHtml(r, 0));
    });
    [].slice.call(document.querySelectorAll('section[id^="sec-rm-"]')).forEach(function (sec) { if (!keep[sec.id]) sec.parentNode.removeChild(sec); });
    placeSections();
  }
  /* ---------- the roadmap ----------
     The roadmap plugin's own page code (taken whole into this page's files by build_site.py, as window.RM_SRC and
     window.RM_RUN) runs here in a shadow root of its own, so its look and its presses are the plugin's, and neither
     page's styles can touch the other. It is given a stand-in document that points into that root, and a stand-in
     database that reads this page's feed (the document roadmap-<key>, ITEMS.md) and carries every write back as an
     answer. A write shows at once, as in the desktop app, and is kept until the engine has it. */
  function rmDoc(key) { return (S.rmDocs && S.rmDocs[key]) || null; }
  function rmCan() { return !!(window.RM_SRC && window.RM_RUN && window.CSSStyleSheet && Element.prototype.attachShadow && 'adoptedStyleSheets' in Document.prototype); }
  function rmCopy(x) { return JSON.parse(JSON.stringify(x)); }
  function rmErr(code) { var e = new Error(code); e.code = code; return e; }
  /* what the database holds for one collection now: the feed's copy with the owner's own unconfirmed writes on top */
  function rmColl(inst, name) {
    var d = rmDoc(inst.key) || {}, base = d[name] || {}, out = {}, id;
    for (id in base) out[id] = base[id];
    Object.keys(inst.ovl).forEach(function (path) {
      var cut = path.indexOf('/'), c = path.slice(0, cut), i = path.slice(cut + 1), o = inst.ovl[path], m = {}, k;
      if (c !== name) return;
      if (o.op === 'delete') delete out[i];
      else if (o.op === 'set') out[i] = o.data;
      else { for (k in (out[i] || {})) m[k] = out[i][k]; for (k in o.data) m[k] = o.data[k]; out[i] = m; }
    });
    return out;
  }
  function rmMs(key) { var m = /:(\d+)-\d+$/.exec(key); return m ? +m[1] : 0; }
  var RM_TS = {marked: 1, written: 1, answered: 1, changed: 1, asked: 1, at: 1};
  /* does the roadmap's own copy now hold this press? The press itself counts, whatever Claude did with it after: the mark,
     note or answer carrying the press's own time, or its words. Its status is Claude's to move (open to done), so it is
     not compared; nothing else on the row has to change. */
  function rmShown(d, path, o) {
    var cut = path.indexOf('/'), base = ((d || {})[path.slice(0, cut)] || {})[path.slice(cut + 1)], k;
    if (o.op === 'delete') return !base;
    if (!base) return false;
    for (k in (o.data || {})) if (RM_TS[k] && o.data[k] && o.data[k] === base[k]) return true;
    for (k in (o.data || {})) if (!RM_TS[k] && k !== 'status' && JSON.stringify(o.data[k]) !== JSON.stringify(base[k])) return false;
    return true;
  }
  function rmDeliver(inst, l, force) {
    var all = rmColl(inst, l.coll), snap, sig, one;
    if (l.kind === 'col') {
      snap = {docs: Object.keys(all).map(function (id) { var v = rmCopy(all[id]); return {id: id, data: function () { return v; }, metadata: {fromCache: false}}; }), metadata: {fromCache: false}};
      sig = JSON.stringify(all);
    } else {
      one = all[l.id]; sig = JSON.stringify(one || null);
      snap = {exists: !!one, id: l.id, data: function () { return one ? rmCopy(one) : undefined; }, metadata: {fromCache: false}};
    }
    if (!force && l.sig === sig) return;
    l.sig = sig;
    try { l.cb(snap); } catch (e) { /* the roadmap's own code reports its own trouble */ }
  }
  function rmPush(inst, force) {
    var n;
    if (rmDoc(inst.key)) inst.ls.slice().forEach(function (l) { rmDeliver(inst, l, force); });
    rmMark(inst);
    n = Object.keys(inst.ovl).length;
    var sent = $('sec-rm-' + inst.key), line = sent && sent.querySelector('.rm-sent');
    if (line) line.textContent = n ? (n === 1 ? '1 answer sent, not yet on the roadmap' : n + ' answers sent, not yet on the roadmap') : '';
  }
  function rmWrite(inst, op, path, data) {
    var cut = path.indexOf('/'), coll = path.slice(0, cut), id = path.slice(cut + 1), prev = inst.ovl[path], ov, k, m = {};
    if (!S.db) return Promise.reject(rmErr('unavailable'));
    if (op === 'update' && !rmColl(inst, coll)[id]) return Promise.reject(rmErr('not_found'));
    var key = 'rm:' + inst.key + ':' + Date.now() + '-' + (++inst.n);
    var rec = {action: 'answer', label: 'Roadmap', result: 'Saving', text: JSON.stringify({roadmap: {key: inst.key, op: op, path: path, data: data === undefined ? null : data}})};
    rec.id = key; rec.at = stamp(key); rec.device = device; rec.sent = false; rec.status = 'saved';
    ov = {op: op, data: data, key: key, at: rec.at, t: Date.now()};
    if (prev && prev.op !== 'delete' && op === 'update') { for (k in prev.data) m[k] = prev.data[k]; for (k in data) m[k] = data[k]; ov.op = prev.op; ov.data = m; }
    inst.ovl[path] = ov;
    S.ans[key] = rec; S.mine[key] = {rec: rec, t: Date.now(), keep: 900000}; inst.seen[key] = 1;
    rmPush(inst);
    /* like the real database, the write settles only once it is confirmed: the roadmap keeps what was typed until then */
    return new Promise(function (resolve, reject) {
      inst.wr[key] = {resolve: resolve, reject: reject, t: Date.now()};
      S.db.setAnswer(key, rec).then(function () {}, function () {
        delete inst.wr[key]; delete inst.ovl[path]; delete S.mine[key]; delete S.ans[key]; rmPush(inst);
        reject(rmErr('unavailable'));
      });
    });
  }
  function rmDb(inst) {
    function listen(l, cb, err) {
      l.cb = cb; l.err = err; inst.ls.push(l);
      setTimeout(function () { rmDeliver(inst, l, true); }, 0);
      return function () { inst.ls = inst.ls.filter(function (x) { return x !== l; }); };
    }
    return {
      collection: function (name) { return {onSnapshot: function (cb, err) { return listen({kind: 'col', coll: name}, cb, err); }}; },
      doc: function (path) {
        var cut = path.indexOf('/'), coll = path.slice(0, cut), id = path.slice(cut + 1);
        return {
          onSnapshot: function (cb, err) { return listen({kind: 'doc', coll: coll, id: id}, cb, err); },
          get: function () { var one = rmColl(inst, coll)[id]; return Promise.resolve({exists: !!one, id: id, data: function () { return one ? rmCopy(one) : undefined; }}); },
          set: function (data) { return rmWrite(inst, 'set', path, data); },
          update: function (data) { return rmWrite(inst, 'update', path, data); },
          'delete': function () { return rmWrite(inst, 'delete', path); }
        };
      }
    };
  }
  function rmComments(inst) {
    return {
      anchorFor: function () { return Promise.resolve({}); },
      canSendToClaude: function () { return Promise.resolve(S.listening === false ? 'off' : 'available'); },
      /* the press itself is what reaches the project's Claude session (through the listener); a second message would send it twice */
      sendToClaude: function () { return Promise.resolve(); },
      create: function () { return Promise.resolve(); }
    };
  }
  /* each pass: writes the engine has taken or refused, comments answered, and the feed's newest copy handed on */
  function rmSweep(inst) {
    var d = rmDoc(inst.key) || {}, changed = false, pre = 'rm:' + inst.key + ':';
    /* a press sent earlier (before a reload, or from another device) that the roadmap does not show yet is still "sent, not yet on the roadmap" */
    if (rmDoc(inst.key)) Object.keys(S.ans).filter(function (k) { return k.indexOf(pre) === 0 && !inst.seen[k]; }).sort(function (x, y) { return rmMs(x) - rmMs(y); }).forEach(function (k) {
      var a = S.ans[k], j = null, w, cut, c, i, o, prev, m, q;
      inst.seen[k] = 1;
      if (!a || a.status === 'failed' || Date.now() - rmMs(k) > 259200000) return;
      try { j = JSON.parse(a.text); } catch (e) { return; }
      w = j && j.roadmap; if (!w || (w.op !== 'set' && w.op !== 'update' && w.op !== 'delete') || !w.path) return;
      o = {op: w.op, data: w.data, key: k, at: a.at, t: rmMs(k)};
      if (rmShown(d, w.path, o)) return;
      prev = inst.ovl[w.path];
      if (prev && prev.op !== 'delete' && w.op === 'update') { m = {}; for (q in prev.data) m[q] = prev.data[q]; for (q in w.data) m[q] = w.data[q]; o.op = prev.op; o.data = m; }
      inst.ovl[w.path] = o; changed = true;
    });
    Object.keys(inst.ovl).forEach(function (path) {
      var o = inst.ovl[path], a = S.ans[o.key], drop = false;
      if (a && a.status === 'failed') { drop = true; toast(/^not saved/i.test(a.outcome || '') ? a.outcome : 'Not saved on the roadmap. ' + (a.outcome || 'It could not be written just now.'), ''); }
      else if (rmShown(d, path, o)) drop = true;                                     /* the roadmap's own data shows it written */
      else if (Date.now() - o.t > 259200000) drop = true;
      if (drop) { delete inst.ovl[path]; changed = true; }
    });
    Object.keys(inst.wr).forEach(function (key) {
      var w = inst.wr[key], a = S.ans[key];
      if (a && a.status === 'done') { delete inst.wr[key]; w.resolve(); }
      else if (a && a.status === 'failed') { delete inst.wr[key]; w.reject(rmErr('failed')); }
      else if (Date.now() - w.t > 120000) { delete inst.wr[key]; w.reject(rmErr('unconfirmed')); }
    });
    return changed;
  }
  /* each press not yet on the roadmap says so where it was made; the line at the top counts them */
  function rmMark(inst) {
    var root = inst.root, els = {}, d = rmDoc(inst.key) || {};
    if (!root) return;
    [].forEach.call(root.querySelectorAll('[data-rm-sent]'), function (e) { e.removeAttribute('data-rm-sent'); });
    Object.keys(inst.ovl).forEach(function (path) {
      var cut = path.indexOf('/'), c = path.slice(0, cut), id = path.slice(cut + 1), o = inst.ovl[path], el = null, row;
      if (c === 'marks') { var b = root.getElementById('yes-' + id); el = b && b.closest('.check'); }
      else if (c === 'questions') el = root.getElementById('q-' + id);
      else if (c === 'notes') { row = (o.data && o.data.row) || ((d.notes || {})[id] || {}).row; el = row && root.getElementById('row-' + row); el = el && el.querySelector('summary'); }
      if (el) els[path] = el;
    });
    Object.keys(els).forEach(function (p) { els[p].setAttribute('data-rm-sent', 'Sent, not yet on the roadmap'); });
  }
  function rmSync() {
    Object.keys(RM.inst).forEach(function (k) {
      var inst = RM.inst[k], doc = rmDoc(k), ch = rmSweep(inst);
      if (!doc) return;
      if (ch || inst.last !== doc) { inst.last = doc; rmPush(inst); } else rmMark(inst);
    });
  }
  function rmTheme() {
    var t = document.documentElement.getAttribute('data-theme'), l = document.documentElement.getAttribute('data-look');
    Object.keys(RM.inst).forEach(function (k) {
      var hst = RM.inst[k].host; if (t) hst.setAttribute('data-theme', t); else hst.removeAttribute('data-theme');
      if (l) hst.setAttribute('data-look', l); else hst.removeAttribute('data-look');
    });
  }
  /* A chosen style reaches the roadmap through the colors and lettering the page names once for all (--look-*, in the Looks
     block); the roadmap keeps its own step colors. */
  var RM_LOOK = null;
  function rmLookSheet() {
    if (!RM_LOOK) {
      RM_LOOK = new CSSStyleSheet();
      RM_LOOK.replaceSync(':host([data-look]){--bg:var(--look-bg);--panel:var(--look-panel);--ink:var(--look-ink);--muted:var(--look-muted);' +
        '--rule:var(--look-rule);--f-text:var(--look-text);--f-mono:var(--look-mono)}');
    }
    return RM_LOOK;
  }
  function rmMount(key) {
    if (RM.inst[key]) return RM.inst[key];
    var inst = {key: key, n: 0, ovl: {}, seen: {}, wr: {}, ls: [], last: null}, hst = document.createElement('div'), root, sheet, box;
    RM.inst[key] = inst;
    if (!document.querySelector('link[data-rm-fonts]')) {
      var lk = document.createElement('link'); lk.rel = 'stylesheet'; lk.setAttribute('data-rm-fonts', '1');
      lk.href = 'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap';
      document.head.appendChild(lk);
    }
    hst.className = 'rm-host';
    root = hst.attachShadow({mode: 'open'});
    sheet = new CSSStyleSheet(); sheet.replaceSync(window.RM_SRC.css + ' [data-rm-sent]::after{content:attr(data-rm-sent);display:block;font-size:.8rem;font-style:italic;color:var(--muted);padding:2px 0}'); root.adoptedStyleSheets = [sheet, rmLookSheet()];
    box = document.createElement('div'); box.innerHTML = window.RM_SRC.body;
    while (box.firstChild) root.appendChild(box.firstChild);
    inst.host = hst; inst.root = root; rmTheme();
    new MutationObserver(function () { rmMark(inst); }).observe(root, {childList: true, subtree: true});
    var vdoc = {
      getElementById: function (id) { return root.getElementById(id); },
      createElement: function (t) { return document.createElement(t); },
      createTextNode: function (t) { return document.createTextNode(t); },
      get activeElement() { return root.activeElement; },
      querySelector: function (q) { return root.querySelector(q); },
      addEventListener: function (t, f, o) { root.addEventListener(t, f, o); }
    };
    var store = {getItem: function (k) { return keepGet('rm.' + key + '.' + k); }, setItem: function (k, v) { keepSet('rm.' + key + '.' + k, v); }};
    var claudeStandIn = {use: function (name) { return Promise.resolve(name === 'db' ? rmDb(inst) : name === 'comments' ? rmComments(inst) : null); }};
    try { window.RM_RUN(vdoc, store, claudeStandIn); } catch (e) { root.appendChild(document.createTextNode('The roadmap could not be started on this page.')); }
    return inst;
  }
  /* a card's "Open it in the roadmap": to the roadmap's own section, unfolded, at the question, check or row */
  function rmOpen(key, target) {
    var sec = $('sec-rm-' + key), inst;
    if (!rmDoc(key)) { toast('That roadmap has not reached this page yet.', ''); return; }
    if (!rmCan()) { toast('This browser is too old to show the roadmap here. Open the roadmap in Claude instead.', ''); return; }
    if (!sec || sec.hidden) { toast('That roadmap is switched off on this page.', ''); return; }
    if (S.panel.settings) delete S.panel.settings;
    if (sec.classList.contains('folded')) keepFold('sec:rm:' + key, true);
    render();
    inst = RM.inst[key];
    sec.scrollIntoView({block: 'start'});
    if (inst && target) setTimeout(function () { rmJump(inst, target); }, 250);
  }
  /* to the question, check or row a card is about: its parts opened, the place in view */
  function rmJump(inst, t) {
    var root = inst.root, el = null;
    if (t.question) { el = root.getElementById('q-' + t.question); if (!el) { var bar = root.getElementById('qbar'); if (bar && !bar.hidden) bar.click(); el = root.getElementById('q-' + t.question); } }
    if (!el && t.row && t.check) el = root.getElementById('yes-' + t.row + '--' + t.check);
    if (!el && t.row) el = root.getElementById('row-' + t.row);
    if (!el) return;
    for (var n = el; n && n !== root; n = n.parentNode) { if (n.tagName === 'DETAILS') n.open = true; if (n.hidden) n.hidden = false; }
    el.scrollIntoView({block: 'center'});
  }
  /* The foot is one quiet line. Anything the assistant has to report is in its own section, never here. */
  function renderFoot() {
    var m = S.meta, n = renderAbout();
    if (!m) { setHtml($('foot'), '<span class="health">' + h(S.note || 'Connecting to my data.') + '</span>'); return; }
    var g = D((m.about && m.about.last_gathered) || m.gathered);
    setHtml($('foot'), '<span class="health"><span>' + (n ? 'I have ' + n + ' for you to read, under ' + ((S.meta && S.meta.labels && S.meta.labels.about) || 'Errors') + ' near the top of this page.'
      : 'All is well.' + (g ? ' Last checked for messages <span class="mono">' + h(fmtDT(g)) + '</span>.' : '')) + '</span></span>');
  }
  var byKey = '';
  function fillBy() {
    var sets = {}, areas = {};
    S.items.forEach(function (it) {
      var f = it.filters || {};
      Object.keys(f).forEach(function (g) { if (f[g]) { sets[g] = sets[g] || {}; sets[g][f[g]] = 1; } });
      if (it.area) areas[it.area] = 1;
    });
    var k = JSON.stringify([sets, areas]) + S.by;
    if (k === byKey || document.activeElement === $('f-by')) return;       /* never rebuild a list he has open */
    byKey = k;
    var LB = (S.meta && S.meta.labels) || {};
    var o = '<option value="">' + h(LB.filter_all || 'Everything') + '</option>';
    Object.keys(sets).sort().map(function (g) { return ['f:' + g + '|', g, sets[g]]; }).concat([['a:', 'Areas', areas]]).forEach(function (g) {
      var names = Object.keys(g[2]).sort();
      if (names.length) o += '<optgroup label="' + h(g[1]) + '">' + names.map(function (nm) { var v = g[0] + nm; return '<option value="' + h(v) + '"' + (v === S.by ? ' selected' : '') + '>' + h(nm) + '</option>'; }).join('') + '</optgroup>';
    });
    $('f-by').innerHTML = o;
  }

  /* ---------- answers ---------- */
  var RESULT = {approve: 'Approved', change: 'Change asked', answer: 'Answered', later: 'Snoozed', done: 'Marked done', reopen: 'Reopening'};
  function find(key) { for (var i = 0; i < S.items.length; i++) if (S.items[i].key === key) return S.items[i]; return null; }
  /* What this device has just done wins over a slightly older copy from the site for a few
     seconds, so a card never flickers back while the answer is on its way. */
  function mergeMine(ans) {
    var now = Date.now();
    Object.keys(S.mine).forEach(function (k) {
      var m = S.mine[k], sv = ans[k];
      if (now - m.t > (m.keep || 8000)) { delete S.mine[k]; return; }
      if (m.rec) { if (!sv || String(sv.at || '') < String(m.rec.at || '')) ans[k] = m.rec; }
      else if (sv && String(sv.at || '') <= String(m.at || '')) delete ans[k];
    });
    return ans;
  }
  /* The line at the bottom of the screen. Every press says at once what happened, with Undo for 15 seconds.
     A press that sets the assistant thinking (words typed on a card, the box at the top, "This kind of
     message") adds a second line that moves and stays until the result is here; the result then shows
     in the engine's own words, with a way to the card. Several results show one after another. */
  var UNDO_MS = 15000, LINE = {now: null, queue: [], t: 0};
  (function () {
    try { var k = JSON.parse(keepGet('think') || '{}') || {}; delete k.chat; S.think = k; } catch (e) { S.think = {}; }
  })();
  function keepThink() { keepSet('think', JSON.stringify(S.think)); }
  function toast(words, undoKey, about, undoMore) {
    if (S.listening === false) words += ' This page can\'t reach your computer, so this waits until it\'s back.';
    LINE.now = {key: undoKey || '', until: Date.now() + UNDO_MS, html: '<span><b>' + h(words) + '</b>' + (about ? ' ' + h(about) : '') + '</span>' +
      (undoKey ? '<button class="link" data-a="' + (undoMore && undoMore.a ? undoMore.a : undoMore ? 'old-undo' : undoKey === 'press' ? 'undo-all' : 'undo') + '" data-key="' + h(undoKey) + '"' +
        (undoMore && undoMore.a ? (undoMore.part != null ? ' data-part="' + h(undoMore.part) + '" data-row="' + h(undoMore.row) + '"' : '') : undoMore ? ' data-card="' + h(undoMore) + '"' : '') + '>Undo</button>' : '')};
    drawLine();
  }
  function hideToast() { LINE.now = null; drawLine(); }
  function drawLine() {
    var t = $('toast'), now = Date.now(), keys = Object.keys(S.think), html = '';
    if (!t) { t = document.createElement('div'); t.id = 'toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    if (LINE.now && LINE.now.until <= now) LINE.now = null;
    if (!LINE.now && LINE.queue.length) { LINE.now = LINE.queue.shift(); LINE.now.until = now + UNDO_MS; }
    if (LINE.now) html += '<div class="tl">' + LINE.now.html + '</div>';
    if (keys.length) {
      var newest = keys.slice().sort(function (a, b) { return S.think[b].t0 - S.think[a].t0; })[0], canUndo = newest !== 'chat';
      html += '<div class="tl"><span><span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>' +
        (keys.length === 1 ? 'I\'m thinking about what you wrote.' : 'I\'m thinking about ' + keys.length + ' things you wrote.') +
        (LINE.queue.length ? ' ' + plural(LINE.queue.length, 'more result') + ' to show.' : '') + '</span>' +
        (canUndo ? '<button class="link" data-a="think-undo" data-key="' + h(newest) + '">' + (keys.length === 1 ? 'Undo' : 'Undo the last one') + '</button>' : '') + '</div>';
    } else if (LINE.queue.length) html += '<div class="tl"><span>' + plural(LINE.queue.length, 'more result') + ' to show.</span></div>';
    if (t._html !== html) { t.innerHTML = html; t._html = html; }
    t.hidden = !html;
    clearTimeout(LINE.t);
    if (LINE.now) LINE.t = setTimeout(drawLine, Math.max(50, LINE.now.until - now + 30));
  }
  /* A press that starts a Claude run: its key is kept until the result for that very press is here. */
  function startThink(key, at, title) { S.think[key] = {at: at, t0: Date.now(), title: title || ''}; keepThink(); }
  function stopThink(key) { if (S.think[key]) { delete S.think[key]; keepThink(); } }
  function thinks(rec) {
    var p = pressOf(rec);
    if (p) return ((p.name === 'not_needed' || p.name === 'always_show') && p.scope === 'kind') || (p.name === 'rule_offer' && p.do !== 'cancel')
      || p.name === 'hide_like_this' || p.name === 'keep_showing';      /* a switch: what it led to is the engine's own line, once it lands */
    return !isSend(rec) && !rec.label && !rec.calendar && (rec.action === 'answer' || rec.action === 'change') && !!rec.text;
  }
  function checkThink() {
    var changed = false;
    Object.keys(S.think).forEach(function (k) {
      var th = S.think[k], a = S.ans[k], it = k === 'chat' ? null : find(k), words = null, bad = false, late = Date.now() - th.t0 > 6 * 60000;
      if (k === 'chat') {
        if (!talk.pending || talk.pending.at !== th.at) { bad = !!talk.err; words = talk.err || 'I answered you in Talk to your assistant, at the top of the page.'; }
      } else if (!S.ansLive && !late) return;
      else if (!a || a.at !== th.at) { if (Date.now() - th.t0 > 9000) { delete S.think[k]; changed = true; } return; }      /* taken back, or answered again */
      else if ((a.status === 'done' || a.status === 'failed') && !(a.status === 'done' && it && it.status === 'Thinking')) {
        bad = a.status === 'failed' || !!(it && it.last_press && it.last_press.at === a.at && it.last_press.ok === false);
        words = a.outcome || (it && it.last_press && it.last_press.at === a.at && it.last_press.happened) || (bad ? 'I couldn\'t act on this.' : 'I\'m done with it.');
      }
      if (words === null && late) { bad = true; words = 'No result has come back yet. Your words are saved, and I\'ll read them.'; }
      if (words === null) return;
      delete S.think[k]; changed = true;
      var res = {key: k, html: '<span><b' + (bad ? ' class="bad"' : '') + '>' + hc(words) + '</b>' + (th.title && String(words).length < 100 ? ' ' + h(th.title) : '') + '</span>' +
        '<button class="link" data-a="jump" data-key="' + h(k) + '">' + (k === 'chat' ? 'Show it' : 'Show the card') + '</button>'};
      /* it takes the place of the line about the same press; any other line with Undo keeps its time first */
      if (LINE.now && LINE.now.key !== k && LINE.now.until > Date.now() && /data-a=/.test(LINE.now.html)) LINE.queue.push(res);
      else { LINE.now = res; LINE.now.until = Date.now() + UNDO_MS; }
    });
    if (changed) keepThink();
    drawLine();
  }
  setInterval(function () { if (Object.keys(S.think).length || LINE.queue.length) checkThink(); }, 2000);
  /* To where the card now sits: its section unfolded, the card opened and in view. */
  function jump(k) {
    LINE.now = null;
    if (k === 'chat') { if (S.panel.settings) delete S.panel.settings; S.open['talk-last'] = true; render(); drawLine(); $('talk-in').scrollIntoView({block: 'center'}); return; }
    var it = find(k), look = function () { return document.querySelector('.card[data-key="' + k + '"]'); };
    if (!it) { toast('That card is no longer on the page.', ''); return; }
    if (S.panel.settings) delete S.panel.settings;
    if (!match(it)) { S.q = ''; S.by = ''; S.age = ''; $('f-q').value = ''; keepSet('by', ''); byKey = ''; }
    openOnly(k); acting = k; FEED.f = 'all';
    render();
    var el = look(), n = 0;
    if (!el) { toast('That card is no longer on the page.', ''); return; }
    var sec = el.closest('section');
    if (sec && sec.classList.contains('folded')) { keepFold('sec:' + sec.id.slice(4), true); n++; }
    for (var d = el.closest('details'); d; d = d.parentNode && d.parentNode.closest ? d.parentNode.closest('details') : null) {
      if (!d.open) { var dk = d.getAttribute('data-d'); S.open[dk] = true; if (/(^| )(fold|grp)( |$)/.test(d.className)) keepFold(dk, true); n++; }
    }
    if (n) { acting = k; render(); el = look(); }
    drawLine();
    if (!el) return;
    el.scrollIntoView({block: 'center'});
    el.classList.add('flash');
    setTimeout(function () { var e2 = look(); if (e2) e2.classList.remove('flash'); el.classList.remove('flash'); }, 2500);
  }
  /* The line for a press, in the same words the engine uses for what happened. */
  function saidNow(it, rec) {
    var p = pressOf(rec), n = p ? p.name : '';
    if (isSend(rec)) return 'Sending. The result shows where you pressed Send.';
    if (n === 'done') return 'Marked done.';
    if (n === 'got_it') return 'Got it. This card is closed.';
    if (n === 'later' || n === 'someday') return rec.until === 'someday' ? 'Snoozed to Someday, under Someday, until you bring it back.' : 'Snoozed until ' + laterWords(p.when, rec.until) + '. It comes back by itself.';
    if (n === 'bring_back') return 'Back on your page.';
    if (n === 'junk') return ((it.sender && it.sender.address) || 'This sender') + ' is on your junk list. This card is Done.';
    if (n === 'not_needed') return p.scope === 'sender' ? whoOf(it) + ' is on your ignore list. This card is Done.' : p.scope === 'kind' ? 'Done. I\'m writing a rule for your yes.' : 'Done.';
    if (n === 'always_show') return p.scope === 'sender' ? whoOf(it) + ' always gets through now.' : 'I\'m writing a rule for your yes.';
    if (n === 'no') return /^live:standing-/.test(String(it.source_key || '')) ? 'Got it. I\'ll keep asking each time.'
      : /^live:projwrite-/.test(String(it.source_key || '')) ? 'Nothing was written.' : 'Got it. I didn\'t make the rule.';
    if (n === 'drop') return 'Dropped. I won\'t bring it up again unless something new comes in about it.';
    if (n === 'keep_showing') return 'Got it. I\'ll keep showing these.';
    if (n === 'hide_like_this') return 'Got it. I\'ll offer a rule to hide these.';
    if (n === 'wait_longer') return 'Waiting ' + plural(+p.days, 'more working day') + '.';
    if (n === 'write_them') return 'Nothing is sent until you press Send.';
    if (n === 'approve' && it.rule) return 'Done. I saved the rule. It starts the next time I check for messages.';
    if (n === 'old_keep') return 'Kept. I won\'t ask about it again until it has sat that long once more.';
    if (n === 'never_junk') return ((it.sender && it.sender.address) || 'This sender') + ' is on your never junk list. Its mail is always read.';
    if (n === 'approve') return it.draft && sendCfg() ? 'Your yes is recorded. Nothing is sent until you press Send.' : it.draft ? 'Your yes is recorded. Nothing is sent: sending from this page is switched off.' : 'Your yes is recorded.';
    if (rec.action === 'done') return rec.label === 'Put away' ? 'Done.' : 'Marked done.';
    if (rec.action === 'reopen') return 'Reopened.';
    if (rec.calendar) return 'Adding to your calendar: ' + rec.text + '.';
    if (it.rule && !p) return 'I have your words. The rule comes back rewritten.';
    if (p) return p.words && String(p.words).trim() ? 'Answered: ' + String(p.words).replace(/\s+/g, ' ').trim().replace(/[.!?]+$/, '') + '.' : rec.result ? String(rec.result).replace(/[.!?]*$/, '') + '.' : 'Done.';      /* a press never shows its record */
    return 'Answered: ' + String(rec.label && rec.label !== rec.text ? rec.label : rec.text || 'saved').replace(/\s+/g, ' ').trim().replace(/[.!?]+$/, '') + '.';
  }
  /* When a Later comes back, worked out the way the engine does it: 3 hours on, or 6 in the morning of the day. */
  function laterUntil(when, date) {
    var d = new Date();
    if (when === 'someday') return 'someday';
    if (when === 'today') return isoLocal(new Date(d.getTime() + 3 * 36e5));
    if (when === 'tomorrow') return dayPlus(1) + 'T06:00:00';
    if (when === 'next_week') return dayPlus(((8 - d.getDay()) % 7) || 7) + 'T06:00:00';
    return date + 'T06:00:00';
  }
  function laterWords(when, until) {
    var d = D(until);
    return when === 'today' ? 'later today, about ' + fmtT(d) : when === 'tomorrow' ? 'tomorrow, ' + fmtD(d) : fmtD(d);
  }
  var lastAt = {};
  function stamp(key) {
    var t = isoLocal(new Date()), prev = lastAt[key] || '', had = S.ans[key] && String(S.ans[key].at || '');
    if (had && had > prev) prev = had;
    if (prev && t <= prev && D(prev)) t = isoLocal(new Date(D(prev).getTime() + 1000));
    lastAt[key] = t;
    return t;
  }
  function save(it, rec, quiet) {
    if (!S.db) { S.err[it.key] = 'This page cannot save what you press here. Sign in and open it again.'; render(); return false; }
    var mine = S.mine[it.key];
    if (mine && mine.rec && Date.now() - mine.t < 5000 && mine.rec.text === rec.text && mine.rec.action === rec.action) return false;      /* one press counts once */
    rec.id = it.id; rec.at = stamp(it.key); rec.device = device; rec.sent = false;
    rec.item_title = it.title || ''; rec.item_updated = it.updated_at || '';
    rec.result = rec.result || RESULT[rec.action] || 'Answered';
    rec.status = 'saved';
    var before = S.ans[it.key];
    var hadPanel = S.panel[it.key];
    if (pressName(rec) !== 'undo' && it.state !== 'done') S.was[it.key] = {state: it.state, needs: it.needs, shelf: pressName(rec) === 'bring_back' ? null : it.shelf, status: it.status};
    var back = rec.keepDraft; delete rec.keepDraft;          /* Cancel on a proposed rule: his words go back in the box */
    if (back != null) S.drafts[it.key] = back;
    S.ans[it.key] = rec; delete S.err[it.key]; if (!rec.keepPanel) delete S.panel[it.key]; delete rec.keepPanel; delete S.open['rest:' + it.key]; keepDrafts();
    S.mine[it.key] = {rec: rec, t: Date.now()};
    acting = it.key;
    render();
    var thinking = thinks(rec);
    if (thinking) startThink(it.key, rec.at, headerOf(it)); else stopThink(it.key);
    /* while the assistant thinks, Undo sits on the thinking line, which stays as long as the thinking does */
    if (!quiet) { toast(saidNow(it, rec), isSend(rec) || (stays(it, rec) && pressName(rec) !== 'old_keep') || thinking ? '' : it.key, headerOf(it)); if (thinking && LINE.now) LINE.now.key = it.key; }
    else drawLine();
    S.db.setAnswer(it.key, rec).then(function () { if (back == null) delete S.drafts[it.key]; delete S.drafts['s:' + it.key]; delete S.drafts['cal:' + it.key]; delete S.drafts['ro:' + it.key]; keepDrafts(); }, function () {
      delete S.mine[it.key]; stopThink(it.key);
      if (hadPanel) S.panel[it.key] = hadPanel;
      acting = it.key;
      hideToast();
      if (before) S.ans[it.key] = before; else delete S.ans[it.key];
      S.err[it.key] = 'What you pressed wasn\'t saved, so the card is back. Check the connection and press it again.'; render();
    });
    return true;
  }
  function undo(it) {
    var before = S.ans[it.key];
    stopThink(it.key);
    hideToast();
    if (!before) {
      /* closed with the others, put off on another device, or answered and already acted on: the engine takes the newest press back */
      if (groupOf(it) || it.shelf || it.answer || ansOf(it)) save(it, pressRec('undo', null, 'Taken back'), true);
      return;
    }
    delete S.ans[it.key];
    S.mine[it.key] = {rec: null, at: before.at, t: Date.now(), keep: 20000, open: /^(approve|change|answer)$/.test(before.action) && !pressOf(before) ? (it.kind === 'task' ? 'yours' : 'question') : null};
    acting = it.key;
    render();
    S.db.clearAnswer(it.key).catch(function () { delete S.mine[it.key]; S.ans[it.key] = before; S.err[it.key] = 'Undo was not saved. Check the connection and press it again.'; render(); });
  }
  /* One press for several cards, kept on the key "press": Got it for every card shown that needs nothing, and its Undo. */
  function pressAll(rec, said, undoable) {
    if (!S.db) { S.err.press = 'This page cannot save what you press here. Sign in and open it again.'; render(); return; }
    rec.id = 'press'; rec.at = stamp('press'); rec.device = device; rec.sent = false; rec.status = 'saved';
    var before = S.ans.press;
    S.ans.press = rec; delete S.err.press;
    S.mine.press = {rec: rec, t: Date.now()};
    render();
    toast(said, undoable ? 'press' : '');
    S.db.setAnswer('press', rec).then(function () {}, function () {
      delete S.mine.press; hideToast();
      if (before) S.ans.press = before; else delete S.ans.press;
      S.err.press = 'What you pressed wasn\'t saved, so the cards are back. Check the connection and press it again.'; render();
    });
  }
  /* Undo of one row of the asking card: the card it was about takes its newest press back. */
  function oldUndo(key, card) {
    var done = S.oldDone[key] && S.oldDone[key][card], target = find(card) || {key: card, id: card, title: (done && done.row && done.row.header) || ''};
    hideToast();
    if (!done) return;
    delete S.oldDone[key][card];
    (S.oldBack[key] = S.oldBack[key] || {})[card] = {row: done.row, t: Date.now()};
    render();
    if (!S.db) return;
    var rec = pressRec('undo', null, 'Taken back');
    rec.id = card; rec.at = stamp(target.key); rec.device = device; rec.sent = false; rec.status = 'saved'; rec.item_title = target.title || '';
    S.ans[target.key] = rec; S.mine[target.key] = {rec: rec, t: Date.now()};
    S.db.setAnswer(target.key, rec).then(function () {}, function () {
      delete S.mine[target.key]; delete S.ans[target.key]; delete S.oldBack[key][card]; S.oldDone[key][card] = done;
      S.err[key] = 'Undo was not saved. Check the connection and press it again.'; render();
    });
  }
  /* ---------- what was hidden: one folded line, and behind it the list ---------- */
  function heldPress(hk) {
    if (!hk) return;
    if (!S.db) { S.err['held:' + hk] = 'This page cannot save what you press here. Sign in and open it again.'; render(); return; }
    var rec = pressRec('should_have_seen', null, 'Asked to see it');
    rec.id = hk; rec.at = stamp(hk); rec.device = device; rec.sent = false; rec.status = 'saved';
    S.ans[hk] = rec; delete S.err['held:' + hk];
    S.mine[hk] = {rec: rec, t: Date.now()};
    render();
    toast(S.listening === false ? 'Saved.' : 'Bringing it to your page.', '');
    S.db.setAnswer(hk, rec).then(function () {}, function () {
      delete S.mine[hk]; delete S.ans[hk]; hideToast();
      S.err['held:' + hk] = 'What you pressed wasn\'t saved. Check the connection and press it again.'; render();
    });
  }
  /* Reading a hidden message (ITEMS.md "Reading a held-back message"): the row's fold asks the engine for the
     message, one part at a time, and shows its own words as plain text. Reading changes nothing about the row. */
  function readAsk(hk, part) {
    var st = S.read[hk] = S.read[hk] || {parts: []};
    if (st.loading) return;
    if (!S.db) { st.err = 'This page cannot ask for the message here. Sign in and open it again.'; render(); return; }
    var rec = pressRec('read', {part: part}, 'Reading');
    rec.id = hk; rec.at = stamp(hk); rec.device = device; rec.sent = false; rec.status = 'saved';
    st.at = rec.at; st.loading = true; st.t0 = Date.now(); st.err = '';
    render();
    S.db.setAnswer(hk, rec).then(function () {}, function () { st.loading = false; st.err = 'The message could not be asked for. Check the connection and try again.'; render(); });
  }
  function readTake() {
    var rd = S.reading, st = rd && S.read[rd.key];
    if (st && st.loading && st.at === rd.at) {
      st.loading = false;
      if (rd.ok === false) st.err = String(rd.text || 'The message could not be read just now.');
      else {
        st.parts[(+rd.part || 1) - 1] = String(rd.text || '').replace(/\s*\[There is more\. Open the next part\.\]\s*$/, '');
        st.more = !!rd.more; st.total = +rd.parts || 1; st.got = +rd.part || 1;
        st.meta = {from: rd.from, to: rd.to, when: rd.when, subject: rd.subject, papers: rd.papers || []};
      }
    }
    Object.keys(S.read).forEach(function (hk) {
      var x = S.read[hk], a = S.ans[hk];
      if (!x.loading) return;
      if (a && a.at === x.at && a.status === 'failed') { x.loading = false; x.err = String(a.outcome || 'The message could not be read just now.'); }
      else if (Date.now() - x.t0 > 25000) { x.loading = false; x.err = S.listening === false ? 'This page can\'t reach your computer, so the message can\'t be fetched right now.' : 'No answer came back. Try again.'; }
    });
  }
  setInterval(function () { for (var k in S.read) if (S.read[k].loading) { render(); return; } }, 3000);
  function readHtml(r) {
    var k = 'read:' + r.key, st = S.read[r.key] || {parts: []}, m = st.meta, hk = h(r.key), o = '';
    if (m) {
      var list = function (v) { return Array.isArray(v) ? v.join(', ') : String(v || ''); };
      if (m.from) o += '<div class="kv"><b>From:</b> ' + h(list(m.from)) + '</div>';
      if (list(m.to)) o += '<div class="kv"><b>To:</b> ' + h(list(m.to)) + '</div>';
      if (m.when) o += '<div class="kv"><b>When:</b> ' + h(fmtD(D(m.when)) + ' ' + fmtT(D(m.when))) + '</div>';
      if (m.subject) o += '<div class="kv"><b>Subject:</b> ' + h(m.subject) + '</div>';
      if ((m.papers || []).length) o += '<div class="kv"><b>Attached papers:</b> ' + h(m.papers.join(', ')) + '</div>';
      o += '<pre class="src-text">' + h(st.parts.join('\n')) + '</pre>';
      if (st.more && !st.loading && !st.err) o += '<div class="acts"><button class="btn" data-a="read-more" data-hk="' + hk + '">Show the rest</button><span class="wnote">Part ' + st.got + ' of ' + st.total + ' is shown.</span></div>';
    }
    if (st.loading) o += '<div class="kv" role="status"><span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>' + (m ? 'Getting the rest of the message.' : 'Getting the message.') + '</div>';
    if (st.err) o += '<span class="said bad" role="alert">' + hc(st.err) + '</span><div class="acts"><button class="btn" data-a="read-again" data-hk="' + hk + '">Try again</button></div>';
    if (!o) o = '<div class="kv">Open this to read the message.</div>';
    return '<details class="more" data-d="' + h(k) + '"' + (S.open[k] ? ' open' : '') + '><summary class="btn">Read it</summary><div class="inside">' + o + '</div></details>';
  }
  function heldRow(r) {
    var a = S.ans[r.key], n = pressName(a) === 'should_have_seen' ? a : null, at = D(r.at), tail;
    if (n && n.status === 'failed') tail = '<span class="said bad">' + hc(n.outcome || 'That could not be done just now.') + '</span>';
    else if (n && n.status === 'done') tail = '<span class="said">' + hc(n.outcome || 'It is on your page now.') + '</span>';
    else if (n) tail = '<span class="said">' + (S.listening === false ? 'Saved. It comes to your page when your computer is back.' : 'Bringing it to your page') + '</span>';
    else if (r.shown) tail = '<span class="said">You asked to see this. It is on your page.</span>';
    var go = !tail || (n && n.status === 'failed');
    /* a regular card: the Hidden tag, the title, one line with the time and why, then its buttons */
    return '<article class="card held-row"><div class="q">' + h(r.who || r.address || 'Unknown sender') + ': ' + h(r.what || 'no subject') + '</div>' +
      '<div class="why">' + h(fmtDT(at)) + (r.address && r.address !== r.who ? ', ' + h(r.address) : '') + '. Hidden because: ' + hc(r.why || 'no reason was recorded') + '</div>' +
      (tail || '') + '<div class="acts">' + readHtml(r) + (go ? '<button class="btn" data-a="held-go" data-hk="' + h(r.key) + '">I should have seen this</button>' : '') + '</div>' +
      (S.err['held:' + r.key] ? '<div class="err" role="alert">' + h(S.err['held:' + r.key]) + '</div>' : '') + '</article>';
  }
  function renderHeld() {
    var el = $('held'), m = S.meta, hd = S.held, days = (hd && hd.days) || [], t = today();
    if (!el) return;
    readTake();
    if (!m || (m.held_today == null && !hd)) { setHtml(el, ''); $('n-held').textContent = ''; return; }
    var now = days.filter(function (d) { return d.date === t; })[0] || {rows: [], count: 0}, earlier = days.filter(function (d) { return d.date !== t && (d.rows || []).length; });
    var n = m.held_today != null ? +m.held_today : (hd.today != null ? +hd.today : now.count || 0), old = 0;
    earlier.forEach(function (d) { old += d.count || d.rows.length; });
    var nothing = 'Nothing was hidden today.' + (old ? ' See earlier days.' : '');
    $('n-held').textContent = n ? n : '';
    /* in the feed it is one card, the last, that opens the list; the list itself shows under the Hidden filter */
    var one = FEED.f !== 'held', sec = $('sec-held');
    if (sec) sec.classList.toggle('held-one', one);
    if (one) {
      setHtml(el, '<article class="card held-card"><span>' + (n ? 'Hidden today: <b>' + n + '</b>.' : 'Nothing was hidden today.') + '</span>' +
        (n || old ? ' <button class="btn held-see" type="button" data-s="feed-f" data-f="held">' + (n ? 'See them' : 'See earlier days') + '</button>' : '') +
        (m.tips && m.tips.hidden ? '<div class="why tip">' + hc(m.tips.hidden) + '</div>' : '') + '</article>');
      return;
    }
    if (!n && !old) { setHtml(el, '<div class="none">' + nothing + '</div>'); return; }
    var inner = (now.rows || []).length ? '<div class="cards">' + now.rows.map(heldRow).join('') + '</div>' + (now.count > now.rows.length ? '<div class="kv">Showing the newest ' + now.rows.length + ' of ' + now.count + '.</div>' : '')
      : '<div class="kv">' + (n ? 'The list has not reached this page yet.' : 'Nothing was hidden today.') + '</div>';
    if (earlier.length) inner += '<details class="more" data-d="held-earlier"' + (S.open['held-earlier'] ? ' open' : '') + '><summary>Earlier days <span class="cnt">' + old + '</span></summary><div class="inside">' +
      earlier.map(function (d) { return '<div class="held-day">' + h(fmtD(D(d.date))) + ', ' + (d.count || d.rows.length) + ' hidden</div><div class="cards">' + d.rows.map(heldRow).join('') + '</div>'; }).join('') + '</div></details>';
    setHtml(el, '<div class="held-in">' + inner + '</div>');
  }
  function gotItAll() {
    var ids = (S.fyiShown || []).slice(), n = ids.length, extra = {ids: ids};
    if (!n) return;
    S.items.forEach(function (it) { if (ids.indexOf(it.id) >= 0) S.was[it.key] = {state: it.state, needs: it.needs, shelf: it.shelf, status: it.status}; });
    S.lastAll = ids;
    if (JSON.stringify(ids).length > 3500 && !(S.q || S.by || S.age)) extra = null;       /* too many to list: every card that needs nothing */
    else if (JSON.stringify(ids).length > 3500) { ids = ids.slice(0, 300); n = ids.length; extra = {ids: ids}; }
    pressAll(pressRec('got_it_all', extra, 'Done: ' + n + ' cards'), 'Done: ' + plural(n, 'card') + ' that needed nothing.', true);
  }
  /* Approve on a card that holds a draft: the writing screen, filled in, with Send one press away. Nothing is sent by this. */
  /* The box's words: an answer to one question, what he did not need (a rule card to approve), or words to the assistant. */
  /* Discuss on a proposed rule: his words on how it should read; the reworded rule comes back with the same four buttons. */
  function roSend(it) {
    var w = (S.drafts['ro:' + it.key] || '').trim();
    if (!w) { S.err[it.key] = 'Type how the rule should read first.'; render(); return; }
    var rec = pressRec('rule_offer', {do: 'discuss', words: w}, 'Rewording the rule'); rec.keepPanel = false;
    save(it, rec);
  }
  function boxSave(it) {
    var key = it.key, txt = (S.drafts[key] || '').trim(), m = S.box[key] || {};
    if (!txt) { S.err[key] = m.nn ? 'Say what you did not need first.' : 'Type your words first.'; render(); return; }
    var rec = m.nn ? pressRec('not_needed', {scope: 'kind', words: txt}, 'Not needed') : {action: 'answer', text: txt};
    if (!m.nn && m.q) rec.question = m.q;
    if (!m.nn && m.r) rec.redo = m.r;          /* a new answer to one already answered question (Change) */
    delete S.box[key];
    save(it, rec);
  }
  /* A paper, picture or message opened over the page, with Close back to the card (D8). */
  function viewOpen(it, b) {
    var ref = b.getAttribute('data-ref'), msg = b.getAttribute('data-msg'), v = {key: it.key, name: b.getAttribute('data-name') || b.textContent, kind: b.getAttribute('data-kind') || '', ref: ref, from: b};
    if (b.getAttribute('data-sample')) v.kind = 'sample';
    else if (msg != null && msg !== '') { v.kind = 'message'; v.msg = +msg; if (v.msg > 0 && S.db && !S.mail.hosted) viewMsg(v); }
    if (viewPop(v)) return;
    if (v.kind === 'sample') sampleLoad(it.key, null);
    S.view = v; viewDraw();
    var c = $('view-close'); if (c) c.focus();
  }
  /* A paper, picture or email opens in a window of its own (one named window, brought to the front); the page and card stay put.
     Where the browser blocks the window, or the thing is not fetched from his computer, it opens over the page as before. */
  var VIEWQ = (function () {
    var q = window.location.search || '', g = function (n) { var m = new RegExp('[?&]' + n + '=([^&]*)').exec(q); return m ? decodeURIComponent(m[1].replace(/\+/g, ' ')) : ''; };
    if (!/[?&]view=1(&|$)/.test(q)) return null;
    var v = {key: g('key'), name: g('name'), kind: g('kind'), ref: g('ref') || null};
    v.msg = +g('msg') || 0;
    if ((v.kind === 'pdf' || v.kind === 'image') && v.msg > 0) v.back = {key: v.key, name: '', kind: 'message', msg: v.msg};     /* the email this paper came with */
    return v;
  })();
  function viewPop(v) {
    if (VIEWQ || !S.db || S.mail.hosted || S.live === 'off' || (v.kind === 'message' ? !(v.msg > 0) : v.kind !== 'sample' && !v.ref)) return false;
    var q = '?view=1&key=' + encodeURIComponent(v.key) + '&name=' + encodeURIComponent(v.name || '') + '&kind=' + encodeURIComponent(v.kind || '') +
      (v.ref ? '&ref=' + encodeURIComponent(v.ref) : '') + (v.msg > 0 ? '&msg=' + encodeURIComponent(v.msg) : '');
    return popWin(window.location.pathname + q, false);
  }
  /* The one pop-up window ('assistant-viewer'): this page's viewer, or an outside page (then cut off from this page). False when blocked. */
  function popWin(url, outside) {
    var phone = false; try { phone = window.matchMedia('(max-width:700px)').matches || window.matchMedia('(pointer:coarse)').matches; } catch (e) {}
    var w = null;
    try {
      var sz = 900, wd = Math.min(sz, screen.availWidth || sz), ht = Math.min(sz, screen.availHeight || sz);
      var lf = Math.max(0, Math.round(((screen.availWidth || wd) - wd) / 2)), tp = Math.max(0, Math.round(((screen.availHeight || ht) - ht) / 2));
      var to = outside ? '' : url;
      w = phone ? window.open(to, 'assistant-viewer') : window.open(to, 'assistant-viewer', 'popup=yes,width=' + wd + ',height=' + ht + ',left=' + lf + ',top=' + tp);
      if (w && outside) { try { w.opener = null; } catch (e) {} w.location.href = url; }
    } catch (e) { w = null; }
    if (!w) return false;
    try { w.focus(); } catch (e) {}
    return true;
  }
  /* Every link that leaves the page (their unsubscribe page, the roadmap, the manual) opens in that same window; blocked, it opens as a tab as before. */
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[target="_blank"]');
    if (!a || VIEWQ || e.defaultPrevented || e.button || e.ctrlKey || e.metaKey || e.shiftKey) return;
    var u = a.getAttribute('href') || '';
    if (!/^(https?:\/\/|\/manual)/.test(u)) return;
    if (popWin(a.href, true)) e.preventDefault();
  });
  function viewMsg(v) {
    v.loading = true;
    mailJson('api/mail/thread?id=' + mailEnc(v.msg)).then(function (j) {
      v.loading = false;
      if (j.busy) { setTimeout(function () { if (S.view === v) viewMsg(v); }, MAIL_RETRY_MS); return; }
      v.msgs = j.hosted ? null : (j.messages || []).filter(function (x) { return x.id === v.msg; });
      if (!v.msgs || !v.msgs.length) v.err = j.hosted ? 'An email opens on the page served from your computer.' : (j.error || 'That email could not be opened.');
      if (S.view === v) viewDraw();
    }, function () { v.loading = false; v.err = 'That email could not be reached. Check the connection and try again.'; if (S.view === v) viewDraw(); });
  }
  function viewClose() {
    if (VIEWQ) { try { window.close(); } catch (e) {} if (!window.closed) { document.title = 'You can close this window'; } return; }
    var v = S.view; S.view = null; viewDraw();
    if (v && v.kind === 'sample') delete S.sample[v.key];
    var back = v && document.querySelector('[data-key="' + v.key + '"] .opener'); if (back) back.focus();
  }
  function viewDraw() {
    var el = $('viewer'), v = S.view, o = '';
    if (!el) { el = document.createElement('div'); el.id = 'viewer'; el.setAttribute('role', 'dialog'); el.setAttribute('aria-modal', 'true'); document.body.appendChild(el); }
    el.hidden = !v;
    if (!v) { el.innerHTML = ''; el._html = ''; return; }
    var it = find(v.key) || {}, local = !!S.db && !S.mail.hosted && S.live !== 'off';
    o += '<div class="view-bar"><b class="view-name">' + h(v.name || '') + '</b><span class="view-acts">' + ((v.kind === 'pdf' || v.kind === 'image') && v.ref && local ? '<a class="btn" id="view-dl" href="api/mail/file?ref=' + mailEnc(v.ref) + '" download="' + h(v.name) + '" rel="noopener">Download</a>' : '') + (v.back ? '<button class="btn" type="button" data-a="view-back">Back to the email</button>' : '') + '<button class="btn" id="view-close" data-a="view-close">Close</button></span></div><div class="view-body host" data-key="' + h(v.key) + '">';
    if (v.kind === 'pdf' && v.ref && local) o += '<div class="none view-wait" role="status">Opening...</div><iframe class="view-pdf" title="' + h(v.name) + '" src="api/mail/file?ref=' + mailEnc(v.ref) + '&amp;view=1"></iframe>';
    else if (v.kind === 'image' && v.ref && local) o += '<div class="none view-wait" role="status">Opening...</div><img class="view-img" alt="' + h(v.name) + '" src="api/mail/file?ref=' + mailEnc(v.ref) + '&amp;view=1">';
    else if (v.kind === 'message' && v.msg > 0 && local) o += v.err ? '<div class="err">' + h(v.err) + '</div>' : v.msgs ? v.msgs.map(function (m) { return mailMsgHtml(m, true); }).join('') : '<div class="none" role="status">Opening...</div>';
    else if (v.kind === 'message') o += '<article class="mail-msg"><div class="kv">' + hc(it.source_ref || it.source_who || '') + '</div><pre class="src-text">' + h(it.source_text || 'The message is on the page served from your computer.') + '</pre></article>';
    else if (v.kind === 'sample') o += S.sample[v.key] ? sampleHtml(v.key) : '<div class="none" role="status">Opening...</div>';
    else if (v.ref && local) o += '<div class="kv">This file opens in its own program. <a href="api/mail/file?ref=' + mailEnc(v.ref) + '" download="' + h(v.name) + '">Save ' + h(v.name) + '</a></div>';
    else {
      var d = (it.documents || []).filter(function (x) { return x.ref === v.ref || x.file === v.name; })[0];
      o += d && d.read ? '<div class="kv">The paper itself opens on the page served from your computer. Its words, as read:</div><pre class="src-text">' + h(d.text || '') + '</pre>'
        : '<div class="kv">The paper itself opens on the page served from your computer.</div>';
    }
    o += '</div>';
    if (el._html !== o) {           /* a paper already open is not loaded again on each redraw */
      el.innerHTML = o; el._html = o;
      var wait = el.querySelector && el.querySelector('.view-wait'), shown = el.querySelector && el.querySelector('.view-pdf, .view-img');
      if (wait && shown && shown.addEventListener) {        /* Opening... until the paper or picture has loaded */
        shown.addEventListener('load', function () { if (wait.parentNode) wait.parentNode.removeChild(wait); });
        shown.addEventListener('error', function () { wait.textContent = 'That paper could not be opened.'; });
      }
    }
  }
  function openDraft(it) {
    var key = it.key;
    if (!S.drafts['w:' + key]) S.drafts['w:' + key] = wDraft(key, it);
    var pr = wProblem(key, it);
    S.panel[key] = pr ? 'write' : 'review';
    if (pr) S.err[key] = pr + ' Then press Check and send.'; else delete S.err[key];
    keepDrafts();
  }
  document.addEventListener('click', function (e) {
    var fl = e.target.closest('.fold-line');
    if (fl) {
      var fs = fl.parentNode;
      if (fs.tagName === 'DETAILS') fs.open = false;
      else if (fs.tagName === 'ARTICLE') { var fo = fs.querySelector(':scope > .opener'); if (fo) flipCard(fo); }
      else { var fn = fs.querySelector(':scope > .sec-h[data-fold]'); if (fn) flipFold(fn.getAttribute('data-fold')); }
      return;
    }
    var fh =e.target.closest('.sec-h[data-fold]');
    if (fh && !e.target.closest('button, a, input, select, textarea')) { flipFold(fh.getAttribute('data-fold')); return; }
    var b = e.target.closest('[data-a]');
    if (!b) return;
    var a = b.getAttribute('data-a');
    if (a === 'open') { if (!e.target.closest('a')) flipCard(b); return; }
    if (a === 'gotit-all') { gotItAll(); return; }
    if (a === 'read-more' || a === 'read-again') {
      var rk = b.getAttribute('data-hk'), rs = S.read[rk] || {};
      readAsk(rk, a === 'read-more' ? (rs.got || 1) + 1 : rs.meta && rs.more ? (rs.got || 1) + 1 : 1); return;
    }
    if (a === 'talk-clear') { talkClear(); return; }
    if (a === 'talk-undo') { talkUndo(); return; }
    if (a.indexOf('mail-') === 0 && mailClick(a, b)) return;
    if (a.indexOf('cp-') === 0 && cpClick(a, b)) return;
    var mpa = modFor(a); if (mpa && mpa.click && mpa.click(a, b, e)) return;
    if (a.indexOf('tx-') === 0 && txClick(a, b)) return;
    if (a.indexOf('chg-') === 0 && chgClick(a, b)) return;
    if (a.indexOf('rd-all') === 0 && rdClick(a, b)) return;
    if (a === 'said-undo') { saidUndo(b.getAttribute('data-use')); return; }
    if (a === 'held-go') { heldPress(b.getAttribute('data-hk')); return; }
    if (a === 'old-undo') { oldUndo(b.getAttribute('data-key'), b.getAttribute('data-card')); return; }
    if (a === 'jump') { jump(b.getAttribute('data-key')); return; }
    if (a === 'view-close') { viewClose(); return; }
    if (a === 'view-back') { var bv = S.view && S.view.back; if (bv) { S.view = bv; if (bv.kind === 'message' && bv.msg > 0 && !bv.msgs) viewMsg(bv); viewDraw(); } return; }
    if (a === 'scan-undo') { scanUndo(b.getAttribute('data-id')); return; }
    if (a === 'think-undo') { var ti = find(b.getAttribute('data-key')); if (ti) undo(ti); else { stopThink(b.getAttribute('data-key')); drawLine(); } return; }
    if (a === 'undo-all') { hideToast(); pressAll(pressRec('undo', null, 'Taken back'), 'Taken back.', false); return; }
    if (a === 'seen') { S.baseline = (S.meta && S.meta.built) || isoLocal(new Date()); keepSet('seen', S.baseline); render(); return; }
    if (a === 'age') { var v = b.getAttribute('data-age'); S.age = S.age === v ? '' : v; render(); return; }
    if (a === 'clear') { S.q = ''; S.by = ''; S.age = ''; $('f-q').value = ''; keepSet('by', ''); byKey = ''; render(); return; }
    var hostEl = b.closest('[data-key]'); if (!hostEl) return;
    var key = hostEl.getAttribute('data-key'), it = itemOf(key); if (!it) return;
    acting = key;
    if (a.indexOf('w-') === 0 && wClick(a, b, key, it)) return;
    if (a === 'write') {
      if (!sendCfg()) return;
      if (rdOwnFor(it)) { a = 'rd-continue'; }
    }
    if (a === 'write') {
      S.drafts['w:' + key] = wDraft(key, it); S.panel[key] = 'write'; delete S.err[key]; keepDrafts(); render();
      var wf = $('wt-' + key); if (wf) wf.focus();
      return;
    }
    if (a === 'w-pick') {
      var dp = wDraft(key, it), pf = b.getAttribute('data-f') === 'cc' ? 'cc' : 'to';
      wPick(dp, pf, b.getAttribute('data-e') || ''); S.drafts['w:' + key] = dp; keepDrafts(); render();
      var pe = $((pf === 'cc' ? 'wc-' : 'wt-') + key);
      if (pe) { pe.focus(); try { pe.setSelectionRange(pe.value.length, pe.value.length); } catch (e2) {} }
      return;
    }
    if (a === 'w-review') {
      var pr = wProblem(key, it);
      if (pr) { S.err[key] = pr; render(); return; }
      S.panel[key] = 'review'; delete S.err[key]; keepDrafts(); render(); return;
    }
    if (a === 'review') { openDraft(it); render(); return; }
    if (a === 'w-edit') { S.panel[key] = 'write'; delete S.err[key]; keepDrafts(); render(); return; }
    if (a === 'w-discard' && rdIs(it)) { delete S.panel[key]; S.rdAsk[key] = true; render(); return; }
    if (a === 'w-discard') { delete S.drafts['w:' + key]; delete S.panel[key]; delete S.err[key]; keepDrafts(); render(); return; }
    if (a === 'w-send') {
      var ps = wProblem(key, it);
      if (ps) { S.panel[key] = 'write'; S.err[key] = ps; render(); return; }
      if (S.listening === false) { S.err[key] = 'This page can\'t reach your computer right now, so this wouldn\'t go out. Your email is kept. Press Send now again when it\'s back.'; render(); return; }
      var dd = wDraft(key, it), txt = wPressText(key, it);
      if (txt === null) { render(); return; }
      var sr = {action: 'answer', label: 'Send email', text: txt, result: 'Sending your email'};
      save(it, sr);
      if (sr.at) { dd.pressed = sr.at; S.drafts['w:' + key] = dd; keepDrafts(); }
      return;
    }
    if (a === 'rd-continue') {
      var ok = rdOwnFor(it); if (!ok) return;
      S.drafts['w:' + ok.key] = wDraft(ok.key, ok); S.panel[ok.key] = 'write'; delete S.err[ok.key]; keepDrafts(); render();
      var rf = $('sec-ready'); if (rf && rf.scrollIntoView) rf.scrollIntoView({block: 'start'});
      return;
    }
    if (a === 'rd-send') { if (S.listening === false) { S.err[key] = 'This page can\'t reach your computer right now, so this wouldn\'t go out. Press Send now again when it\'s back.'; render(); return; } delete S.err[key]; rdSendOne(it); render(); return; }
    if (a === 'rd-discard-ask') { S.rdAsk[key] = true; render(); return; }
    if (a === 'rd-discard-no') { delete S.rdAsk[key]; render(); return; }
    if (a === 'rd-discard-go') { delete S.rdAsk[key]; if (rdIs(it)) save(it, pressRec('discard', null, 'Discarded')); delete S.drafts['w:' + key]; delete S.panel[key]; keepDrafts(); render(); return; }
    if (a === 'undo') { undo(it); return; }
    if (a === 'cancel') { rdKeep(it); delete S.panel[key]; delete S.err[key]; keepDrafts(); render(); return; }
    if (a === 'cal-open') { S.panel[key] = 'cal'; delete S.err[key]; keepDrafts(); render(); return; }
    if (a === 'cal-ok' || a === 'cal-save') {      /* Add to calendar as shown, or the day he picked */
      var c = it.calendar || {}, d = a === 'cal-ok' ? {date: c.date, start: c.start || '', end: c.end || '', all_day: !!c.all_day} : calDraft(it);
      if (!d.date) { S.err[key] = 'Pick the day.'; render(); return; }
      if (!d.all_day && !d.start) { S.err[key] = 'Pick the start time, or tick All day.'; render(); return; }
      if (!d.all_day && d.end && d.end <= d.start) { S.err[key] = 'The end must be after the start.'; render(); return; }
      var pick = {title: c.title || it.title || '', date: d.date, start: d.all_day ? null : d.start, end: d.all_day ? null : (d.end || null), all_day: !!d.all_day, accepted_as_shown: a === 'cal-ok', location: c.location || null};
      save(it, {action: 'answer', label: 'Add to calendar', text: 'Add to calendar: ' + whenWords(pick), result: 'Add to calendar', calendar: pick}); return;
    }
    if (a === 'sample') { if (S.sample[key]) { delete S.sample[key]; render(); } else sampleLoad(key, null); return; }
    if (a === 'sample-step') { sampleLoad(key, +b.getAttribute('data-id')); return; }
    if (a === 'view') { viewOpen(it, b); return; }
    if (a === 'not-needed') { S.panel[key] = S.panel[key] === 'nn' ? null : 'nn'; delete S.err[key]; render(); return; }
    if (a === 'nn-go') {
      var nt = b.getAttribute('data-t');
      save(it, nt === 'sender' ? pressRec('junk', null, 'Not needed: everything from this sender') : pressRec('not_needed', {scope: 'this'}, 'Not needed')); return;
    }
    if (a === 'nn-other' || a === 'other') {
      delete S.panel[key];
      if (a === 'other' && b.getAttribute('data-noq')) delete S.box[key];      /* Other on a card that asks nothing: his own words in the box */
      else S.box[key] = a === 'nn-other' ? {nn: true} : {q: +(b.getAttribute('data-q') || 0)};
      render();
      var bx = $('ab-' + key); if (bx) bx.focus();
      return;
    }
    if (a === 'ans-change') {        /* Change on an answered question: his new answer goes in the box, for that question only */
      var rn = +(b.getAttribute('data-r') || 0), rq = (it.answered || [])[rn - 1];
      if (!rq) return;
      delete S.panel[key]; S.box[key] = {r: rn, ask: rq.ask || ''}; render();
      var rbx = $('ab-' + key); if (rbx) rbx.focus();
      return;
    }
    if (a === 'box-clear') { delete S.box[key]; render(); return; }
    if (a === 'box-save') { boxSave(it); return; }
    if (a === 'ro-approve' || a === 'ro-disapprove') { save(it, pressRec('rule_offer', {do: a.slice(3)}, a === 'ro-approve' ? 'Rule approved' : 'This time only')); return; }
    if (a === 'ro-cancel') { var rc0 = pressRec('rule_offer', {do: 'cancel'}, 'Cancelled'); rc0.keepDraft = (it.rule_offer || {}).words || ''; save(it, rc0); render(); var rb = $('ab-' + key); if (rb) rb.focus(); return; }
    if (a === 'ro-discuss') { S.panel[key] = S.panel[key] === 'ro-discuss' ? null : 'ro-discuss'; delete S.err[key]; render(); var rd0 = $('ro-' + key); if (rd0) rd0.focus(); return; }
    if (a === 'ro-send') { roSend(it); return; }
    if (a === 'pick' || a === 'last-time') {       /* the pick is marked so the engine knows he took it */
      var pkr = pickRec(it, a === 'pick' ? it.pick : it.last_time);
      if (!pkr) return;
      if (a === 'pick') pkr.pick = '1';
      save(it, pkr); return;
    }
    if (a === 'keep-waiting') { save(it, pressRec('wait_longer', null, 'Keeping waiting')); return; }
    if (a === 'switch') { var sw = b.getAttribute('data-p'); if (sw) save(it, pressRec(sw, null, b.textContent || '')); return; }
    if (a === 'cal-add') {
      var cc = it.calendar || {};
      if (!(cc.certain && cc.date && (cc.all_day || cc.start))) { S.panel[key] = 'cal'; delete S.err[key]; keepDrafts(); render(); return; }
      a = 'cal-ok';
    }
    if (a === 'send-check') { if (!yesNotSent(it)) { var sc2 = pressRec('approve', null, 'Checking the email'); openDraft(it); sc2.keepPanel = true; save(it, sc2); } else { openDraft(it); render(); } return; }
    if (a === 'wait-go') { save(it, pressRec('wait_longer', {days: +b.getAttribute('data-days')}, 'Waiting longer')); return; }
    if (a === 'drop') { save(it, pressRec('drop', null, 'Dropped')); return; }
    if (a === 'got-it') { save(it, pressRec('got_it', null, 'Got it')); return; }
    if (a === 'no') { save(it, pressRec('no', null, 'No')); return; }
    if (a === 'write-them') {
      /* the writing screen opens with an empty message; the press only records that he chose to write */
      if (!sendCfg() || !replyOf(it)) { S.err[key] = sendOff() || 'This card has no email address to write to. Answer in your own words under More.'; render(); return; }
      var wd = wDraft(key, it); if (!S.drafts['w:' + key]) wd.body = '';
      S.drafts['w:' + key] = wd; S.panel[key] = 'write';
      var wr = pressRec('write_them', null, 'Writing to them'); wr.keepPanel = true;
      save(it, wr);
      var wb = $('wb-' + key); if (wb) wb.focus();
      return;
    }
    if (a === 'upd-go') { save(it, pressRec('update_start', {version: it.update && it.update.version}, 'Update started')); return; }
    if (a === 'upd-no') { save(it, pressRec('update_not_now', {version: it.update && it.update.version}, 'Not now')); return; }
    if (a === 'rsi-go' && it.rsi) { save(it, pressRec(it.rsi.kind === 'setting' ? 'rsi_apply' : 'rsi_promote', {proposal: it.rsi.id}, it.rsi.kind === 'setting' ? 'Applying' : 'Approving')); return; }
    if (a === 'rsi-no' && it.rsi) {     /* Reject: words typed in the card's box first are its reason */
      var rw = (S.drafts[key] || '').trim(), rx = {proposal: it.rsi.id};
      if (rw) rx.words = rw;
      save(it, pressRec('rsi_reject', rx, 'Rejected'));
      return;
    }
    if (a === 'rm-card') { rmOpen(it.roadmap.key, it.roadmap); return; }
    if (a === 'rev-go' || a === 'rev-later' || a === 'rev-wait') {
      var rrow = b.getAttribute('data-row'), pn = b.getAttribute('data-p'), rc = find(rrow);
      if (!rc) { S.err[key] = 'That card is no longer on the page.'; render(); return; }
      if (a === 'rev-go' && (pn === 'later' || pn === 'wait_longer')) { var pk = 'rp:' + key + ':' + rrow; S.open[pk] = S.open[pk] === pn ? false : pn; render(); return; }
      var rrec;
      if (a === 'rev-later') {
        var rw = b.getAttribute('data-when'); rrec = pressRec('later', {when: rw}, rw === 'someday' ? 'Someday' : 'Snoozed');
        rrec.until = laterUntil(rw, ''); rrec.label = b.textContent; if (rw !== 'someday') rrec.result = 'Snoozed until ' + backWords(rrec.until);
      } else if (a === 'rev-wait') rrec = pressRec('wait_longer', {days: +b.getAttribute('data-days')}, 'Waiting longer');
      else if (pn === 'keep' || pn === 'old_keep') rrec = pressRec('old_keep', null, 'Kept');
      else if (pn === 'drop') rrec = pressRec('done', null, 'Done');
      else rrec = pressRec(pn, null, REV_LABEL[pn] || pn);
      revApply(it, rc, rrow, rrec);
      return;
    }
    if (a === 'old-go' && b.getAttribute('data-do') === 'later') { var olk = 'ol:' + key + ':' + b.getAttribute('data-card'); S.open[olk] = !S.open[olk]; render(); return; }
    if (a === 'old-go' || a === 'old-later') {
      var oc = b.getAttribute('data-card'), od = a === 'old-later' ? 'later' : b.getAttribute('data-do'), row = (it.old_cards || []).filter(function (r) { return r.id === oc; })[0] || {id: oc};
      var ow = b.getAttribute('data-when'), oextra = {card: oc, 'do': od};
      if (od === 'later') { oextra.when = ow; oextra.until = laterUntil(ow, ''); delete S.open['ol:' + key + ':' + oc]; }
      var orec = pressRec('old_card', oextra, od === 'keep' ? 'Kept' : od === 'later' ? 'Snoozed' : 'Done');
      if (save(it, orec, true) === false) return;
      (S.oldDone[key] = S.oldDone[key] || {})[oc] = {row: row, 'do': od};
      if (S.oldBack[key]) delete S.oldBack[key][oc];
      render();
      toast(od === 'keep' ? 'Kept. I won\'t ask about it again until it has sat that long once more.' : od === 'later' ? 'Snoozed. It comes back then.' : 'Done.', key, row.header, oc);
      return;
    }
    if (a === 'later') {
      S.panel[key] = S.panel[key] === a ? null : a; delete S.err[key]; delete S.open['rest:' + key];
      if (a === 'later' && S.panel[key] && !S.drafts['s:' + key]) {       /* the day the owner chose in Settings is filled in first */
        var sd = setts() && setts().page && setts().page.snooze_days;
        if (sd > 0) S.drafts['s:' + key] = dayPlus(sd);
      }
      keepDrafts(); render();
      return;
    }
    if (a === 'later-go') {
      var when = b.getAttribute('data-when'), day = S.drafts['s:' + key] || '';
      if (when === 'date' && (!day || day <= today())) { S.err[key] = 'Pick a date after today.'; render(); return; }
      var lr = pressRec('later', when === 'date' ? {when: 'date', until: day} : {when: when}, when === 'someday' ? 'Someday' : 'Snoozed');
      lr.until = laterUntil(when, day); lr.label = b.textContent;
      if (when !== 'someday') lr.result = 'Snoozed until ' + backWords(lr.until);
      save(it, lr); return;
    }
    if (a === 'back') { if (sect(it) === 'done') save(it, {action: 'reopen', label: 'Bring it back'}); else save(it, pressRec('bring_back', null, 'Back on your page')); return; }
    if (a === 'junk') { save(it, pressRec('junk', null, 'Junk')); return; }
    if (a === 'never-junk') { save(it, pressRec('never_junk', null, 'Never junk')); return; }
    if (a === 'choice') {
      var cq = +(b.getAttribute('data-q') || 0), crec = {action: 'answer', label: b.textContent, text: b.getAttribute('data-text') || b.textContent, result: 'Answered'};
      if (cq) { crec.question = cq; crec.result = 'Answered question ' + cq; }
      if (b.getAttribute('data-b')) { crec.button = b.getAttribute('data-b'); crec.meaning = b.getAttribute('data-m') || 'other'; }      /* recorded with the press */
      save(it, crec); return;
    }
    if (a === 'approve') {
      var ar = pressRec('approve', null, it.rule ? 'Rule saved' : 'Going ahead');
      if (it.draft && sendCfg()) { openDraft(it); ar.keepPanel = true; }      /* the writing screen opens on the card; only his own Send sends */
      save(it, ar); return;
    }
    if (a === 'done') {
      var st = sect(it);
      if (st === 'done') save(it, {action: 'done', label: 'Put away'});       /* a finished card put away */
      else save(it, pressRec('done', null, 'Done'));
      return;
    }
    if (a === 'reopen') { save(it, {action: 'reopen', label: 'Reopen'}); return; }
    if (a === 'save-text') { boxSave(it); return; }
  });
  document.addEventListener('input', function (e) {
    var t = e.target;
    if (t.id === 'f-q') { S.q = t.value.trim().toLowerCase(); render(); return; }
    if (t.hasAttribute('data-draft')) S.drafts[t.getAttribute('data-draft')] = t.value;
    if (t.hasAttribute('data-snooze')) S.drafts['s:' + t.getAttribute('data-snooze')] = t.value;
    if (t.id === 'mail-q') { S.mail.qd = t.value; return; }
    if (t.tagName === 'TEXTAREA' && t.closest && t.closest('.cp-pill')) cpGrow(t);
    var mpi = false; modEach(function (p) { if (!mpi && p.input && p.input(t)) mpi = true; }); if (mpi) return;
    if (t.hasAttribute('data-calf') && CAL.form) { var cf = t.getAttribute('data-calf'); CAL.form[cf] = t.type === 'checkbox' ? t.checked : t.value; if (t.type === 'checkbox') { t.blur(); renderCal(); } return; }
    if (t.id === 'tx-q') { S.tx.qd = t.value; return; }
    if (t.id === 'tx-text') { S.tx.text[t.getAttribute('data-tx') || ''] = t.value; return; }
    if (t.id === 'tx-to') { S.tx.newTo = t.value; return; }
    if (t.hasAttribute('data-wo') || t.hasAttribute('data-wotick')) { woInput(t); return; }
    if (t.hasAttribute('data-w') || t.hasAttribute('data-wa')) wInput(t);
    if (t.hasAttribute('data-lad') || t.hasAttribute('data-ladd')) { sLadInput(t); keepDrafts(); return; }
    if (t.hasAttribute('data-ctn')) { CT.notes[t.getAttribute('data-ctn')] = t.value; return; }     /* Contacts: notes kept as typed */
    if (t.hasAttribute('data-ctq')) { CT.q = t.value; clearTimeout(CT.typing); CT.typing = setTimeout(function () { ctLoad(false); }, 300); return; }
    if (t.hasAttribute('data-rbf')) { RB[t.getAttribute('data-rbf') === 'right' ? 'right' : 'note'] = t.value; return; }     /* Rule book, Edit: kept as typed */
    if (t.hasAttribute('data-rule') || t.hasAttribute('data-radd')) {
      if (sRuleInput(t)) { var rh = t.closest('[data-key]'); acting = rh && rh.getAttribute('data-key'); keepDrafts(); render(); return; }
    }
    if (t.hasAttribute('data-set') || t.hasAttribute('data-pw')) {
      if (sInput(t)) { var sh = t.closest('[data-key]'); acting = sh && sh.getAttribute('data-key'); keepDrafts(); render(); return; }
    }
    if (t.hasAttribute('data-cal')) {
      var hk = t.closest('[data-key]'), ck = hk && hk.getAttribute('data-key'), ci = ck && find(ck);
      if (ci) {
        var cd = calDraft(ci);
        cd[t.getAttribute('data-cal')] = t.type === 'checkbox' ? t.checked : t.value;
        S.drafts['cal:' + ck] = cd;
        if (t.type === 'checkbox') { acting = ck; render(); }
      }
    }
    keepDrafts();
  });
  /* An empty Starts or Ends box opens on the hour, not the exact minute now: the start on the
     current hour, the end an hour after a start already picked (or on the current hour). */
  document.addEventListener('focusin', function (e) {
    var t = e.target;
    if (!t || t.type !== 'time' || t.value || !t.hasAttribute || !t.hasAttribute('data-cal')) return;
    var hk = t.closest('[data-key]'), ck = hk && hk.getAttribute('data-key'), ci = ck && find(ck);
    if (!ci) return;
    var cd = calDraft(ci), f = t.getAttribute('data-cal'), st = f === 'end' && String(cd.start || '').match(/^(\d\d):/), hr = st ? +st[1] + 1 : new Date().getHours();
    if (hr > 23) return;
    t.value = pad(hr) + ':00';
    cd[f] = t.value; S.drafts['cal:' + ck] = cd; keepDrafts();
  });
  document.addEventListener('change', function (e) {
    var mpc = false; modEach(function (p) { if (!mpc && p.change && p.change(e)) mpc = true; }); if (mpc) return;
    if (e.target.id === 'feed-sort-by') sortSave(e.target.value, kindsGrouped());
    else if (e.target.id === 'f-by') { S.by = e.target.value; keepSet('by', S.by); byKey = ''; render(); }
    else if (e.target.id === 'mail-acct' || e.target.id === 'mail-view') mailPick(e.target);
    else if (e.target.id === 'mail-openread') { keepSet('mailopenread', e.target.checked ? '1' : '0'); render(); }
    else if (e.target.hasAttribute && e.target.hasAttribute('data-wfile')) {
      var wf = e.target.files && e.target.files[0], wh = e.target.closest('[data-key]'), wk = wh && wh.getAttribute('data-key'), wi = wk && itemOf(wk);
      if (wf && wi) wUpload(wk, wi, wf);
    }
    else if (e.target.hasAttribute && (e.target.hasAttribute('data-w') || e.target.hasAttribute('data-wa'))) { wInput(e.target); keepDrafts(); }
    else if (e.target.hasAttribute && e.target.hasAttribute('data-set')) render();      /* he left a settings box: its group now says it is not saved yet */
  });
  document.addEventListener('toggle', function (e) {
    var k = e.target.getAttribute && e.target.getAttribute('data-d');
    if (!k) return;
    S.open[k] = e.target.open;
    if (e.target.open) addLines();
    if (k.slice(0, 5) === 'read:' && e.target.open) { var rst = S.read[k.slice(5)]; if (!rst || (!rst.meta && !rst.loading && !rst.err)) readAsk(k.slice(5), 1); }
    /* a part of the page (not the "more" inside one card) is remembered once it differs from how it starts:
       the two finished lists start shut, everything else starts open */
    var starts = !(k === 'done' || k === 'held' || k.slice(0, 4) === 'set:');
    if (/(^| )(fold|grp)( |$)/.test(e.target.className) && (FOLDS[k] != null || e.target.open !== starts)) keepFold(k, e.target.open);
  }, true);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && S.view) { e.preventDefault(); viewClose(); return; }
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && e.target.hasAttribute && e.target.hasAttribute('data-box')) {
      e.preventDefault(); var bi = itemOf(e.target.getAttribute('data-box')); if (bi) boxSave(bi); return;
    }
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && e.target.hasAttribute && e.target.hasAttribute('data-ro')) {
      e.preventDefault(); var ri = itemOf(e.target.getAttribute('data-ro')); if (ri) roSend(ri); return;
    }
    if ((e.key !== 'Enter' && e.key !== ' ') || !e.target.matches) return;
    if (e.key === 'Enter' && e.target.id === 'mail-q') { e.preventDefault(); mailSearch(false); return; }
    var mpk = false; modEach(function (p) { if (!mpk && p.keydown && p.keydown(e)) mpk = true; }); if (mpk) return;
    if (e.key === 'Enter' && e.target.id === 'tx-q') { e.preventDefault(); txSearch(); return; }
    if (e.key === 'Enter' && e.target.hasAttribute('data-wo')) { e.preventDefault(); var wq = e.target.closest('[data-key]'); if (wq) { (S.wo[wq.getAttribute('data-key')] = S.wo[wq.getAttribute('data-key')] || {}).q = e.target.value; woFind(wq.getAttribute('data-key')); } return; }
    if (e.target.matches('.tx-row')) { e.preventDefault(); txOpen(e.target.getAttribute('data-id')); return; }
    if (e.target.matches('.mail-row')) { e.preventDefault(); mailOpen(mailId(e.target.getAttribute('data-id'))); return; }
    if (e.target.matches('.opener')) { e.preventDefault(); flipCard(e.target); return; }
    if (!e.target.matches('.sec-h[data-fold]')) return;
    e.preventDefault();
    flipFold(e.target.getAttribute('data-fold'));
  });

  /* ---------- the section index: one row of jump links under the pinned title and search ---------- */
  /* Every part on show has a link with its count, in page order (Top, Left, Right, Bottom); the part you are reading is marked.
     On a narrow screen the row scrolls sideways and keeps the marked link in view. */
  var STK = {sig: '', raf: 0, cur: ''};
  function stackItems() {
    var out = [], order = {top: 0, left: 1, right: 2, bottom: 3};
    [].forEach.call(document.querySelectorAll('.wrap section[id^="sec-"]'), function (sec) {
      if (!sec.getClientRects().length || (sec.parentNode && sec.parentNode.closest && sec.parentNode.closest('section[id^="sec-"]'))) return;
      var hd = sec.querySelector(':scope > .sec-h'), h2 = hd && hd.querySelector('h2');
      if (!hd || !h2) return;
      var area = sec.closest('.area, .col'), id = area ? area.id : '', n = hd.querySelector('.n'), m = n && /\d+/.exec(n.textContent || '');
      out.push({sec: sec, hd: hd, name: h2.textContent.replace(/\s+/g, ' ').trim(), n: m ? m[0] : '', lane: id === 'area-top' ? 'top' : id === 'area-left' ? 'left' : id === 'area-right' ? 'right' : 'bottom'});
    });
    return out.map(function (it, k) { return [it, k]; }).sort(function (x, y) { return (order[x[0].lane] - order[y[0].lane]) || (x[1] - y[1]); }).map(function (x) { return x[0]; });
  }
  function updateStack() {
    STK.raf = 0;
    var pin = $('pinbar'), st = $('stack');
    if (!pin || !st || S.panel.settings) return;
    var pinH = pin.offsetHeight, items = stackItems(), cur = '', best = -1e9;
    st.style.top = pinH + 'px';
    var line = pinH + (st.hidden ? 0 : st.offsetHeight) + 12;
    items.forEach(function (it) {          /* the first part (in page order) that spans the line under the bar; else the last heading above it */
      var r = it.sec.getBoundingClientRect(), t = it.hd.getBoundingClientRect().top;
      if (!cur && r.top <= line && r.bottom > line) cur = it.sec.id;
      if (t <= line && t > best) { best = t; STK.last = it.sec.id; }
    });
    if (!cur && best > -1e9) cur = STK.last;
    if (!cur && items.length) cur = items[0].sec.id;
    var html = items.length < 2 ? '' : '<nav class="st-row-list" aria-label="Parts of the page">' + items.map(function (it) {
      var on = it.sec.id === cur, shut = it.sec.classList.contains('folded');
      return '<div class="st-row' + (on ? ' on' : '') + (shut ? ' shut' : '') + '" role="button" tabindex="0" data-st="' + h(it.sec.id) + '" aria-label="Go to ' + h(it.name) + '"' + (on ? ' aria-current="true"' : '') + '>' +
        h(it.name) + (it.n ? '<span class="st-n">' + h(it.n) + '</span>' : '') + '</div>';
    }).join('') + '</nav>';
    if (html !== STK.sig) {
      var sx = st.firstChild ? st.firstChild.scrollLeft : 0;
      STK.sig = html; st.innerHTML = html;
      if (st.firstChild) st.firstChild.scrollLeft = sx;
    }
    st.hidden = !html;
    if (cur !== STK.cur && st.firstChild) {
      STK.cur = cur;
      var on = st.querySelector('.st-row.on'), row = st.firstChild;
      if (on && (on.offsetLeft < row.scrollLeft || on.offsetLeft + on.offsetWidth > row.scrollLeft + row.clientWidth)) row.scrollLeft = on.offsetLeft - 16;
    }
    var stickH = pinH + (html ? st.offsetHeight : 0);
    document.documentElement.style.setProperty('--stick-h', stickH + 'px');
    document.documentElement.style.scrollPaddingTop = (stickH + 8) + 'px';
    /* blank room after the last part, so the page can always scroll until any heading is tight under the index: no more than that */
    var tail = $('tail');
    if (tail) {
      var room = tail.offsetHeight, docH = document.documentElement.scrollHeight - room, need = 0;
      items.forEach(function (it) { var y = it.hd.getBoundingClientRect().top + window.pageYOffset - stickH - 6; if (y > need) need = y; });
      var want = Math.max(0, Math.ceil(need - (docH - window.innerHeight)));
      if (want !== room) tail.style.height = want + 'px';
    }
  }
  function stackSoon() { if (!STK.raf) STK.raf = requestAnimationFrame(updateStack); }
  window.addEventListener('scroll', stackSoon, {passive: true});
  window.addEventListener('resize', stackSoon);
  function stackGo(id) {
    var sec = $(id);
    if (!sec) return;
    if (sec.classList.contains('folded')) { var fh = sec.querySelector(':scope > .sec-h[data-fold]'); if (fh) flipFold(fh.getAttribute('data-fold')); }
    var n = 0;
    (function aim() {
      var pin = $('pinbar'), st = $('stack'), hd = sec.querySelector(':scope > .sec-h'), r = hd.getBoundingClientRect(), want = pin.offsetHeight + (st.hidden ? 0 : st.offsetHeight) + 6;
      window.scrollBy(0, r.top - want);
      updateStack();
      if (++n < 4) requestAnimationFrame(aim);
    })();
  }
  document.addEventListener('click', function (e) {
    var r = e.target.closest && e.target.closest('.st-row');
    if (!r) return;
    stackGo(r.getAttribute('data-st'));
  });
  document.addEventListener('keydown', function (e) {
    var r = e.target.closest && e.target.closest('.st-row');
    if (!r || (e.key !== 'Enter' && e.key !== ' ')) return;
    e.preventDefault(); r.click();
  });

  /* ---------- "since you last looked", kept on this device ---------- */
  var hiddenAt = 0;
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) { hiddenAt = Date.now(); if (S.meta && S.meta.built) keepSet('seen', S.meta.built); }
    else if (hiddenAt && Date.now() - hiddenAt > 6e4) { S.baseline = keepGet('seen') || S.baseline; render(); }
  });
  window.addEventListener('pagehide', function () { if (S.meta && S.meta.built) keepSet('seen', S.meta.built); });

  /* ---------- data ---------- */
  function assemble() {
    var m = S.meta; if (!m) return;
    var out = [];
    for (var i = 0; i < (m.parts || 0); i++) {
      var p = S.parts['part-' + i];
      if (!p || p.stamp !== m.stamp) return; /* a pass is landing; keep what is shown until it is whole */
      out = out.concat(p.items || []);
    }
    S.items = out.filter(function (it) { return it && !oldSelf(it); });
  }
  /* A store gives the page its data and keeps answers. On Claude it is the page's own
     online store; on the owner's site it is set up before this script as window.LIVE_STORE. */
  function claudeStore() {
    if (!(window.claude && window.claude.use)) return Promise.resolve(null);
    return window.claude.use('db').then(function (db) {
      if (!db) return null;
      return {
        watch: function (onLive, onAnswers, onTrouble) {
          db.collection('live').onSnapshot(function (snap) {
            var docs = {};
            snap.docs.forEach(function (d) { var v = d.data(); if (v) docs[d.id] = v; });
            onLive(docs, !snap.metadata.fromCache);
          }, function () { onTrouble('The connection to the data was lost. Reload the page.', true); });
          db.collection('answers').onSnapshot(function (snap) {
            var ans = {};
            snap.docs.forEach(function (d) { var v = d.data(); if (v) ans[d.id] = v; });
            onAnswers(ans);
          }, function () { onTrouble('Answers cannot be read right now. Reload the page.', false); });
        },
        setAnswer: function (key, rec) { return db.doc('answers/' + key).set(rec); },
        clearAnswer: function (key) { return db.doc('answers/' + key).delete(); }
      };
    }, function () { return null; });
  }
  function start(store) {
    S.db = store;
    if (!store) { S.live = 'off'; S.note = 'This page cannot reach its data here. Sign in and open it again.'; render(); return; }
    var timer = setTimeout(function () { S.note = S.meta ? 'The data cannot be reached right now, so this may be out of date.' : 'The data cannot be reached yet. This page keeps trying.'; render(); }, 10000);
    store.watch(function (docs, sure, hears) {
      var meta = docs.current || null, parts = {};
      if (hears === true || hears === false) S.listening = hears;
      Object.keys(docs).forEach(function (k) { if (k !== 'current') parts[k] = docs[k]; });
      S.parts = parts;
      S.held = docs.held || null;
      S.reading = docs.reading || null;
      S.standing = docs.standing || null;
      S.chg = docs.changes || null;
      S.rmDocs = {};
      Object.keys(docs).forEach(function (dk) { if (dk.slice(0, 8) === 'roadmap-') S.rmDocs[dk.slice(8)] = docs[dk]; });
      if (meta) { S.meta = meta; assemble(); }
      if (sure) { clearTimeout(timer); S.note = ''; S.live = 'on'; }
      render();
    }, function (ans) {
      var copy = {};
      Object.keys(ans || {}).forEach(function (k) { copy[k] = ans[k]; });
      S.ans = mergeMine(copy); S.ansLive = true; render();
    },
    function (words, dead) { if (dead) { clearTimeout(timer); S.live = 'off'; } S.note = words; render(); });
    if (store.signOut) { $('signout').hidden = false; $('signout').addEventListener('click', function () { store.signOut(); }); }
  }
  if (VIEWQ) { document.documentElement.className += ' popout viewpop'; S.view = VIEWQ; if (VIEWQ.kind === 'message' && VIEWQ.msg > 0) viewMsg(VIEWQ); else if (VIEWQ.kind === 'sample') sampleLoad(VIEWQ.key, null); }
  else if (POP != null) { document.documentElement.className += ' popout'; S.mail.open = mailId(POP); S.mail.started = true; mailLoad(false, true); mailThread(S.mail.open, false); }
  render();
  setInterval(renderFoot, 60000);
  setInterval(renderTop, 60000);
  (window.LIVE_STORE ? window.LIVE_STORE() : claudeStore()).then(start, function () { start(null); });
})();
