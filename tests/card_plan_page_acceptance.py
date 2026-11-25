r"""Acceptance: "Cards made simpler" on the page (page.html). The page's own card code is cut out of page.html and run under node
with made-up cards of every kind the engine makes, built like the real ones, and a stand-in for the page's saving and fetching.
Nothing outside this process is touched.

- Each kind shows exactly its buttons, in order, with no More (the plan's K1-K20 where the engine makes them).
- Each label leads to the same press on every card.
- Other on question 2 of a two-question card marks the box "Your answer to 2:" and its words are question 2's answer.
- Not needed: Just this one, Everything from this sender, and Other (words that become a rule card).
- Context links open the PDF, the picture and the email over the page; Close returns to the card.
- The opened card shows only Context, the draft (when there is one) and Conversation.
- The front: the title with only Due, Important and New; the recommendation; why it is here with no label; Save beside the box always; typed words, once acted on, leave a card that still needs him open.

    python tests\card_plan_page_acceptance.py
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
const between = (a, b) => { const i = src.indexOf(a), j = src.indexOf(b, i); if (i < 0 || j < 0) throw new Error("no region " + a); return src.slice(i, j); };
const line = (re) => src.match(re)[0];
const click = between("  document.addEventListener('click', function (e) {\n    var fl", "  document.addEventListener('input'");
const code = [
  between("  function $(id) {", "  function cards(list, s)"),
  between("  var COMPOSE = ", "  /* ---------- the direct box"),
  pick("find"), pick("saidNow"), pick("itemOf"), pick("thinks"), pick("roSend"), pick("calPanel"), pick("whenWords"), pick("laterUntil"), pick("boxSave"), pick("viewOpen"), pick("viewPop"), pick("popWin"), pick("viewMsg"), pick("viewClose"), pick("viewDraw"), pick("openDraft"),
  line(/  var MAIL_RETRY_MS = [^\n]+\n/),
  "function onClick(e) {" + click.slice(click.indexOf("{") + 1).replace(/\}\);\s*$/, "") + "}",
].join("\n");

const TT = {saved: [], urls: [], els: {}, focus: null, body: []};
const prelude = `
  var S = {meta: {send: {on: true, accounts: ["me@a.example"]}, settings: {page: {}}}, items: [], ans: {}, err: {}, panel: {}, drafts: {}, open: {}, mine: {}, was: {}, think: {},
           sample: {}, box: {}, view: null, oldDone: {}, oldBack: {}, revDone: {}, db: {}, live: "on", listening: true, baseline: "2026-11-01T00:00:00", mail: {hosted: false}, rmDocs: {}};
  var VIEWQ = null;
  var acting = null, device = "Computer, test", talk = {}, LINE = {now: null, queue: []};
  function render() {} function keepDrafts() {} function keepSet() {} function keepGet() { return null; } function toast() {} function hideToast() {} function drawLine() {} function setHtml(el, html) { el.innerHTML = html; }
  function infoBtn() {} function mailJson() {} function mailEnc() {} function mailCsrf() {} function hiddenSec() {}   // named by window.ASSISTANT_PAGE.lib at load
  function cpMake() {} function cpSet() {} function cpList() {} function cpHead() {} function cpSync() {} function cpAlt() {} function cpRow() {} function cpPins() {} function cpRel() {} function cpItems() {} function cpAvatar() {} var CP_SEND = "", CP_OWN = {};
  function startThink(k) { S.think[k] = {t0: 1}; } function stopThink(k) { delete S.think[k]; }
  function save(it, rec) { rec.at = "2026-11-19T10:00:00"; TT.saved.push({key: it.key, rec: rec}); S.ans[it.key] = rec; delete S.panel[it.key]; return true; }
  function sampleLoad(key) { S.sample[key] = {data: {sender: "dana@vendor.example", list: [{id: 31, when: "x", subject: "Sale"}], message: {id: 31, account: "me@a.example", from: "dana@vendor.example", from_name: "Dana", to: ["me@a.example"], cc: [], subject: "Sale", text: "Big sale", labels: [], files: []}}}; }
  function rmCan() { return true; } function rmDoc() { return true; } function rmOpen() { TT.rm = true; }
  function mailJson(url) { TT.urls.push(url); return {then: function (ok) { ok({ok: true, messages: [{id: 21, account: "me@a.example", from: "dana@vendor.example", from_name: "Dana", to: ["me@a.example"], cc: [], subject: "Invoices 1101 and 1102", text: "Please find the invoices attached.", labels: [], files: []}]}); }}; }
`;
/* the page's own fetching and sample reading, stood in for (declared after the page's code, so these are the ones used) */
const postlude = `
  function sampleLoad(key) { S.sample[key] = {data: {sender: "dana@vendor.example", list: [{id: 31, when: "x", subject: "Sale"}], message: {id: 31, account: "me@a.example", from: "dana@vendor.example", from_name: "Dana", to: ["me@a.example"], cc: [], subject: "Sale", text: "Big sale", labels: [], files: []}}}; }
  function mailJson(url) { TT.urls.push(url); return {then: function (ok) { ok({ok: true, messages: [{id: 21, account: "me@a.example", from: "dana@vendor.example", from_name: "Dana", to: ["me@a.example"], cc: [], subject: "Invoices 1101 and 1102", text: "Please find the invoices attached.", labels: [], files: []}]}); }}; }
`;
const doc = {getElementById: (id) => TT.els[id] || null, querySelector: () => ({focus() { TT.focus = "card"; }}), body: {appendChild: (el) => { TT.els[el.id] = el; }},
             createElement: () => ({setAttribute() {}, set innerHTML(v) { this._inner = v; }, get innerHTML() { return this._inner || ""; }}),
             addEventListener() {}};
TT.els["view-close"] = {focus() { TT.focus = "close"; }};
const L = new Function("TT", "document", "window", "setTimeout", "setInterval", prelude + code + `
  return {S: S, card: card, buttons: buttons, inside: inside, sect: sect, onClick: onClick, find: find, stays: stays, thinks: thinks, said: typeof saidNow === 'function' ? saidNow : null};
` + postlude)(TT, doc, {pageYOffset: 0, scrollTo() {}, location: {search: ""}}, () => 0, () => 0);
const S = L.S, out = {};

/* made-up cards, built like the real ones (made-up names and numbers) */
const now = "2026-11-19T08:00:00";
const base = (o) => Object.assign({state: "question", kind: "question", area: "Work", created_at: "2026-11-02T09:00:00", updated_at: "2026-10-30T09:00:00", assistant_did: "", asks: [], status: null}, o);
const sender = {address: "dana@vendor.example", can_junk: true}, reply = {to: ["dana@vendor.example"], subject: "Invoices", account: "me@a.example"};
const K = {
  K1: base({id: "L1", key: "L1", updated_at: "2026-11-16T08:00:00", title: "Acme Supply owes Bayside Fire $6,000 on invoices 1101 and 1102", needs: "answer", recommended: "Send Dana a short reminder about both invoices.",
            rec_front: "Send Dana a short reminder about both invoices.", why: "Two invoices to Acme, $6,000 in all, are unpaid. One was due 10/1, and there has been no reply in over two weeks.",
            due_date: "2026-10-01", importance: 1, sender: sender, reply: reply, teach: ["not_needed_this", "not_needed_sender", "not_needed_kind"],
            asks: ["Remind Dana about the $6,000?"], questions: [{ask: "Remind Dana about the $6,000?", choices: [{label: "Send reminder", text: "Send reminder", recommended: true}, {label: "Call Dana instead", text: "Call Dana instead"}]}],
            detail: "You emailed Dana Invoice 1101.pdf ($3,000) and the site photo on 11/3. No payment or reply has come in since.",
            documents: [{file: "Invoice 1101.pdf", read: true, kind: "pdf", ref: "att:11", text: "Invoice 1101 ..."}, {file: "Site photo.jpg", read: false, kind: "image", ref: "att:12"}],
            messages: [{id: 21, when: "2026-11-03T09:41", who: "You", subject: "Invoices 1101 and 1102", channel: "email"}, {id: 22, when: "2026-11-16T08:00", who: "Dana", subject: "Re: Invoices", channel: "email"}],
            assistant_did: "11/16: looked again; still no reply.\nYou wrote 11/19 8:32 AM: \"When did I send both of these invoices?\"\nBoth went out 11/3 at 9:41 AM."}),
  K2: base({id: "L2", key: "L2", title: "A reply to Pat about the delivery", kind: "approval", needs: "approval", recommended: "Send it.", rec_front: "Send it.", why: "Pat asked for a date.",
            draft: {to: ["pat@x.example"], cc: [], subject: "Re: Delivery", body: "Hi Pat, Friday works.", attach: []}, teach: ["not_needed_this"]}),
  K3: base({id: "L3", key: "L3", title: "Call the inspector", state: "yours", kind: "task", needs: "do", why: "You added it.", reply: reply, teach: ["not_needed_this"]}),
  K4: base({id: "L4", key: "L4", title: "Which job is the new order for?", needs: "answer", why: "An order came in with no job number.", asks: ["Which job is this for?"], questions: [{ask: "Which job is this for?", choices: []}], teach: ["not_needed_this"]}),
  K5: base({id: "L5", key: "L5", title: "A shipment went out", state: "handled", kind: "fyi", needs: "nothing", why: "The supplier says it shipped.", sender: sender, reply: reply, teach: ["not_needed_this", "not_needed_sender", "not_needed_kind"]}),
  K6: base({id: "L6", key: "L6", title: "Waiting on Dana for the signed contract", state: "in_motion", needs: "waiting", waiting_on: "Dana", checkback_date: "2026-11-24", why: "Dana said she would sign this week.", teach: ["not_needed_this"]}),
  K7: base({id: "L7", key: "L7", title: "Dana has not answered about the quote", needs: "answer", recommended: "Send Dana a reminder.", rec_front: "Send Dana a reminder.", why: "No reply in five working days.",
            came_back: {why: "waited", who: "Dana", waited_days: 5, wait_days: 3}, asks: ["Remind Dana, or keep waiting?"], questions: [{ask: "Remind Dana, or keep waiting?", choices: []}],
            sender: sender, reply: reply, teach: ["not_needed_this", "not_needed_sender", "not_needed_kind"]}),
  K8: base({id: "L8", key: "L8", title: "Inspection Tuesday 9 AM", needs: "answer", why: "The inspector set a time.", calendar: {title: "Inspection", date: "2026-11-24", start: "09:00", certain: true}, asks: ["Put it on your calendar?"], questions: [{ask: "Put it on your calendar?", choices: []}], teach: ["not_needed_this"]}),
  K9: base({id: "L9", key: "L9", title: "Is news@deals.example junk?", source_key: "task:system::noise rule proposals 1", needs: "answer", why: "Judged junk three times.", sample: true, asks: ["Junk?"],
            questions: [{ask: "Junk?", choices: ["Junk", "Never junk"]}], teach: []}),
  K10: base({id: "L10", key: "L10", title: "First email from Sam Lee", source_key: "live:newsender-sam", needs: "answer", why: "Someone new wrote to you.", asks: ["Show their mail?"], questions: [{ask: "Show their mail?", choices: ["Show their mail", "Hold it"]}], teach: []}),
  K11: base({id: "L11", key: "L11", title: "New rule: Hide sale emails from vendors.", source_key: "rule:3", kind: "approval", needs: "approval", why: "You pressed Not needed on a card.", rule: {text: "Hide sale emails from vendors.", way: "show_less", from: "Roof sale", reason: "Sale mail needs nothing from me."},
             asks: ["Approve this rule?"], questions: [{ask: "Approve this rule?", choices: []}], teach: []}),
  K12: base({id: "L12", key: "L12", title: "Do this every time without asking?", source_key: "live:standing-5", needs: "answer", why: "You approved the same thing three times.", asks: ["Always do it?"],
             questions: [{ask: "Always do it?", choices: ["Yes, do it and notify me", "Yes, do it quietly"]}], teach: []}),
  K13: base({id: "L13", key: "L13", title: "A new version of the assistant", state: "yours", needs: "do", why: "Version 0.1.4 is ready.", update: {version: "0.1.4", from: "0.1.3", changes: ["Cards made simpler"]}, teach: []}),
  K14: base({id: "L14", key: "L14", title: "2 cards have sat for 14 days", source_key: "live:old-cards", needs: "answer", why: "They have sat a long time.", old_cards: [{id: "L40", header: "Old one", days: 20}, {id: "L41", header: "Older one", days: 30}], teach: []}),
  K15: base({id: "L15", key: "L15", title: "Your weekly review", source_key: "live:review-1", state: "yours", needs: "do", why: "It is review day.", review: {parts: [{key: "p", title: "Cards that have sat", group: "clear", rows: [{id: "L40", header: "Old one", presses: ["old_keep", "later", "done"]}]}]}, teach: []}),
  K16: base({id: "L16", key: "L16", title: "Write this into the project file?", source_key: "live:projwrite-2", needs: "answer", why: "A project asked to record a change.", asks: ["Write it?"],
             questions: [{ask: "Write it?", choices: [{label: "Yes, write it", text: "Yes, write it", recommended: true}]}], teach: []}),
  K17: base({id: "L17", key: "L17", title: "Repaint the shop sign", state: "yours", shelf: "someday", needs: "do", why: "Set aside.", teach: []}),
  K18: base({id: "L18", key: "L18", title: "Paid the permit fee", state: "done", status: "Done", needs: "nothing", why: "Finished.", assistant_did: "You marked it done 11/18.", teach: []}),
  K19: base({id: "L19", key: "L19", title: "A project is waiting on you", state: "yours", needs: "do", why: "The roadmap needs your call.", roadmap: {key: "proj"}, teach: []}),
  K21: base({id: "L21", key: "L21", title: "Broken bowl drawer", needs: "answer", recommended: "Send Dana a reminder.", rec_front: "Send Dana a reminder.", why: "No reply in five working days.",
             came_back: {why: "waited", who: "Dana", waited_days: 5, wait_days: 3}, sender: sender, reply: reply, teach: ["not_needed_this"]}),
  K22: base({id: "L22", key: "L22", title: "A reply to Pat about the delivery date", kind: "approval", needs: "approval", why: "Pat asked for a date.", asks: ["Send this to Pat?"], questions: [{ask: "Send this to Pat?", choices: []}],
             draft: {to: ["pat@x.example"], cc: [], subject: "Re: Delivery", body: "Hi Pat, Friday works.", attach: []}, teach: ["not_needed_this"]}),
  K20: base({id: "L20", key: "L20", title: "Count which?", source_key: "live:tally-1", needs: "answer", why: "Your Tally addition asks.", asks: ["Which?"], questions: [{ask: "Which?", choices: ["Red", "Blue"]}], teach: []}),
};
S.items = Object.keys(K).map((k) => K[k]);
const btns = (html) => { const out = [], re = /<button class="btn[^"]*" data-a="([^"]+)"([^>]*)>([^<]*)<\/button>/g; let m; while ((m = re.exec(html))) out.push({a: m[1], label: m[3].replace(/&amp;/g, "&"), attrs: m[2]}); return out; };
const front = (it) => L.card(it, L.sect(it));
/* the row of one card (questions of a several-question card are drawn above it, each with its own buttons) */
/* a card's buttons in the order drawn: its one question's own buttons (under the question), then the row */
const row = (it) => { const h = front(it), i = h.indexOf('<div class="acts row-main'), q = h.indexOf('<ol class="qs">');
  const qb = q >= 0 && (h.match(/<li><div class="q-ask">/g) || []).length === 1 ? btns(h.slice(q, h.indexOf("</ol>", q))).map((b) => b.label) : [];
  return i < 0 ? qb : qb.concat(btns(h.slice(i, h.indexOf("</div>", i))).map((b) => b.label)); };
out.rows = {}; for (const k of Object.keys(K)) out.rows[k] = row(K[k]);
out.oldRows = btns(front(K.K14)).map((b) => b.label);
out.reviewRows = btns(front(K.K15)).map((b) => b.label);
out.noMore = Object.keys(K).every((k) => front(K[k]).indexOf('data-a="more"') < 0 && front(K[k]).indexOf(">More<") < 0);

/* 2. each label leads to the same press everywhere: one data-a per label (choices from the writer excepted: each is its own answer) */
const seen = {};
const meaning = (b) => { const g = (n) => (new RegExp('data-' + n + '="([^"]*)"').exec(b.attrs) || [])[1];
  if (b.a === "old-go") return g("do"); if (b.a === "rev-go") return {old_keep: "keep", drop: "done"}[g("p")] || g("p"); return b.a; };
for (const k of Object.keys(K)) for (const b of btns(front(K[k]))) { if (b.a === "choice") continue; (seen[b.label] = seen[b.label] || new Set()).add(meaning(b)); }
out.oneMeaning = Object.keys(seen).filter((l) => seen[l].size > 1).map((l) => l + ": " + [...seen[l]].join(", "));
const press = (it, a, attrs) => { TT.saved.length = 0; const b = {getAttribute: (n) => (attrs && n in attrs ? attrs[n] : n === "data-a" ? a : null), textContent: (attrs && attrs.text) || "",
  closest: (sel) => (sel === "[data-a]" ? b : sel === "[data-key]" ? {getAttribute: () => it.key} : null)};
  L.onClick({target: {closest: (sel) => (sel === "[data-a]" ? b : null)}}); return TT.saved.map((x) => x.rec); };
const what = (recs) => recs.map((r) => { try { return JSON.parse(r.text).press.name; } catch (e) { return r.action + (r.question ? ":q" + r.question : ""); } });
out.done = ["K3", "K5", "K6", "K11", "K12", "K16", "K17"].map((k) => what(press(K[k], "done")).join(""));
out.no = ["K11", "K12", "K16"].map((k) => what(press(K[k], "no")).join(""));
/* a choice carries its button id and meaning: the writer's own, or its place and other */
const chAt = (it, label) => btns(front(it)).find((b) => b.a === "choice" && b.label === label).attrs;
const at2 = (attrs) => { const o = {}; attrs.replace(/data-([a-z]+)="([^"]*)"/g, (m, k, v) => { o["data-" + k] = v; }); return o; };
const meant = base({id: "L31", key: "L31", title: "Which colour?", needs: "answer", why: "x", asks: ["Which?"], questions: [{ask: "Which?", choices: [{label: "Red", text: "Red", id: "red", meaning: "agrees"}, "Blue"]}]});
S.items.push(meant);
out.choiceIds = [at2(chAt(meant, "Red")), at2(chAt(meant, "Blue"))].map((a) => [a["data-b"], a["data-m"]]);
out.choicePress = press(meant, "choice", Object.assign(at2(chAt(meant, "Red")), {text: "Red"})).map((r) => ({text: r.text, button: r.button, meaning: r.meaning}));
/* a card the engine gave a switchable button (card.switches): drawn at the end of its row, its press its own name */
const sw = base({id: "L32", key: "L32", title: "A sale on garden hoses", needs: "nothing", state: "handled", why: "x", sender: sender, teach: ["not_needed_this"],
  switches: [{id: "hide_like_this", label: "Hide mailings like this"}, {id: "keep_showing", label: "Keep showing these"}]});
S.items.push(sw);
out.switchRow = row(sw);
out.switchSaid = L.said ? ["hide_like_this", "keep_showing"].map((p) => { const r = {action: "answer", text: JSON.stringify({press: {name: p}})}; return [L.said(sw, r), L.thinks(r)]; }) : null;
out.noSaid = L.said ? L.said(K.K11, {action: "answer", text: JSON.stringify({press: {name: "no"}})}) : null;
out.switchPress = ["hide_like_this", "keep_showing"].map((p) => what(press(sw, "switch", {"data-p": p, text: "x"})).join(""));
out.later = ["K1", "K3", "K13"].map((k) => { press(K[k], "later"); return S.panel[K[k].key]; });

/* 4. Other on question 2 of a two-question card */
const two = base({id: "L30", key: "L30", title: "Acme invoices", needs: "answer", why: "Two things to settle.", asks: ["Remind Dana?", "Charge late fees on 1101?"],
  questions: [{ask: "Remind Dana?", choices: [{label: "Send reminder", text: "Send reminder", recommended: true}, {label: "Keep waiting", text: "Keep waiting"}]},
              {ask: "Charge late fees on 1101?", choices: [{label: "No late fee", text: "No late fee", recommended: true}, {label: "Add late fee", text: "Add late fee"}]}]});
S.items.push(two);
const twoHtml = front(two);
out.twoFront = {numbered: (twoHtml.match(/<li><div class="q-ask">/g) || []).length, rec2: twoHtml.indexOf("Recommended: No late fee") >= 0,
  qButtons: btns(twoHtml.slice(twoHtml.indexOf('<ol class="qs">'), twoHtml.indexOf("</ol>"))).map((b) => b.label + (/data-q="(\d)"/.exec(b.attrs) || [0, ""])[1]),
  row: btns(twoHtml.slice(twoHtml.indexOf("</ol>"))).map((b) => b.label)};
press(two, "other", {"data-q": "2"});
out.otherBox = /Your answer to 2:/.test(front(two)) && TT.focus === null || /Your answer to 2:/.test(front(two));
S.drafts.L30 = "Only if they are 30 days late";
const ans2 = press(two, "box-save");
out.otherAnswer = ans2.map((r) => ({action: r.action, text: r.text, question: r.question}));
out.choiceQ2 = press(two, "choice", {"data-q": "2", "data-text": "No late fee", "data-b": "q2-1", "data-m": "other", text: "No late fee"}).map((r) => ({text: r.text, question: r.question, button: r.button, meaning: r.meaning}));
out.typedStays = (() => { S.ans.L30 = {action: "answer", text: "When did I send these?", at: "x", status: "done"}; const h = front(two); delete S.ans.L30; return h.indexOf("hide-on-answer") >= 0 && h.indexOf('data-state=') < 0; })();
out.reading = (() => { S.think.L1 = {t0: 1}; const h = front(K.K1); delete S.think.L1; return /Reading\.\.\./.test(h); })();

/* 5. Not needed: the three choices */
press(K.K1, "not-needed");
const nnHtml = front(K.K1);
out.nnPanel = btns(nnHtml.slice(nnHtml.indexOf("What did you not need?") - 40)).map((b) => b.label).slice(0, 4);
out.nnThis = press(K.K1, "nn-go", {"data-t": "this"}).map((r) => JSON.parse(r.text).press);
out.nnSender = press(K.K1, "nn-go", {"data-t": "sender"}).map((r) => JSON.parse(r.text).press);
press(K.K1, "nn-other"); out.nnBox = /What did you not need\?/.test(front(K.K1));
S.drafts.L1 = "sale emails from this supplier";
out.nnOther = press(K.K1, "box-save").map((r) => JSON.parse(r.text).press);

/* 6. Context links open the PDF, the picture and the email over the page, and Close returns to the card */
S.open["card:L1"] = true;
const opened = front(K.K1), ctx = opened.slice(opened.indexOf('<section class="sec-in ctx">'), opened.indexOf("</section>"));
const links = btns(ctx).length ? [] : [];
const lre = /<button class="link view-link" data-a="view"([^>]*)>([^<]*)<\/button>/g; let lm; const ctxLinks = [];
while ((lm = lre.exec(ctx))) ctxLinks.push({attrs: lm[1], words: lm[2]});
out.ctxLinks = ctxLinks.map((l) => l.words.replace(/&#39;/g, "'"));
const viewOf = (attrs) => { const g = (n) => { const m = new RegExp('data-' + n + '="([^"]*)"').exec(attrs); return m ? m[1].replace(/&amp;/g, "&") : null; };
  const b = {getAttribute: (n) => g(n.replace(/^data-/, "")), textContent: ""}; L.onClick({target: {closest: (sel) => (sel === "[data-a]" ? {getAttribute: (n) => n === "data-a" ? "view" : b.getAttribute(n), textContent: "", closest: (s2) => s2 === "[data-key]" ? {getAttribute: () => "L1"} : null} : null)}});
  return TT.els.viewer ? TT.els.viewer.innerHTML : ""; };
const pdf = viewOf(ctxLinks.find((l) => /pdf/.test(l.attrs)).attrs);
out.pdf = {frame: /<iframe class="view-pdf"[^>]*src="api\/mail\/file\?ref=att%3A11&amp;view=1"/.test(pdf), close: /data-a="view-close">Close</.test(pdf), focus: TT.focus};
out.opening = /<div class="none view-wait" role="status">Opening...<\/div><iframe class="view-pdf"/.test(pdf);
out.closed = (() => { L.onClick({target: {closest: (sel) => (sel === "[data-a]" ? {getAttribute: (n) => n === "data-a" ? "view-close" : null} : null)}}); return {view: S.view, hidden: TT.els.viewer.hidden, focus: TT.focus}; })();
const pic = viewOf(ctxLinks.find((l) => /image/.test(l.attrs)).attrs);
out.picture = /<img class="view-img" alt="Site photo.jpg" src="api\/mail\/file\?ref=att%3A12&amp;view=1">/.test(pic);
const mail = viewOf(ctxLinks.find((l) => /data-msg="21"/.test(l.attrs)).attrs);
out.email = {url: TT.urls[TT.urls.length - 1], shows: /Please find the invoices attached\./.test(mail) && /class="mail-msg/.test(mail), noButtons: mail.indexOf('data-a="mail-act"') < 0};
L.onClick({target: {closest: (sel) => (sel === "[data-a]" ? {getAttribute: (n) => n === "data-a" ? "view-close" : null} : null)}});

/* 7. the opened card: Context, the draft when there is one, Conversation; nothing else, nothing folded */
const secs = (html) => (html.match(/<h4>([^<]+)<\/h4>/g) || []).map((x) => x.replace(/<\/?h4>/g, ""));
S.open["card:L2"] = true;
out.openedSections = {invoice: secs(opened), draft: secs(front(K.K2)), folded: /<details/.test(opened) || /<details/.test(front(K.K2)),
  gone: ["Everything it asks", "What the assistant recommends", "The facts", "Source message", "Attached papers", "Evidence", "History", "Here because"].filter((w) => opened.indexOf(w) >= 0)};
out.conversation = /<li class="you">You wrote 11\/19 8:32 AM/.test(opened) && /Both went out 11\/3 at 9:41 AM/.test(opened);
/* a date written plainly reads as words; Other on a one-question card names question 1; a message the story speaks of is
   linked there, and the line after the story only names what the story does not; a paper says Opening... until it loads */
const plain = base({id: "L63", key: "L63", title: "Inspection", needs: "answer", rec_front: "Put the visit on your calendar for 2030-01-18, 9:00 to 9:30 AM.",
  why: "Set for 2030-01-18.", questions: [{ask: "Put it on your calendar?", choices: []}]});
S.items.push(plain);
out.bareDay = front(plain).indexOf("2030-01-18") < 0 && /Fri 1\/18/.test(front(plain));
press(K.K4, "other");
out.answer1 = /Your answer to 1:/.test(front(K.K4));
/* an open card is never a dead end: an answer the assistant already read (it came back since with a new question), or one not
   yet read, leaves its buttons and its box showing */
const dead = (read) => { const c = base({id: read ? "L65" : "L66", key: read ? "L65" : "L66", title: "Robin chasing a credit", state: "yours", needs: "do",
  why: "No reply in 2 working days.", answer: "make that a rule", answered_at: "2026-11-18T09:15:37",
  last_press: read ? {press: "words", at: "2026-11-18T09:15:37", happened: "Saved the rule.", ok: true} : null,
  asks: ["Wait longer, write to them, or drop it?"], questions: [{ask: "Wait longer, write to them, or drop it?", choices: []}]});
  S.items.push(c); const fh = front(c);
  return {hidden: /data-state=/.test(fh.slice(0, fh.indexOf(">"))), buttons: /data-a="done"/.test(fh) && /data-a="later"/.test(fh), box: /<textarea/.test(fh),
          answeredLine: /You answered/.test(fh)}; };
out.notDead = {read: dead(true), unread: dead(false)};
const fwd = base({id: "L64", key: "L64", title: "Invoice from Acme", needs: "answer", why: "x",
  detail: "Dana forwarded a message with Invoice 1101.pdf attached.",
  documents: [{file: "Invoice 1101.pdf", read: true, kind: "pdf", ref: "att:11"}], messages: [{id: 21, when: "2026-11-03T09:41", who: "Dana", subject: "Invoice", channel: "email"}]});
S.items.push(fwd); S.open["card:L64"] = true;
const fh = front(fwd);
out.inline = {msg: /forwarded <button class="link view-link" data-a="view" data-msg="21"[^>]*>a message<\/button>/.test(fh),
  paper: /<button class="link view-link" data-a="view" data-ref="att:11"[^>]*>Invoice 1101.pdf<\/button> attached/.test(fh),
  noTail: fh.indexOf("It came in") < 0 && fh.indexOf("The paper:") < 0};
out.ctxSentence = /You emailed Dana <button class="link view-link" data-a="view" data-ref="att:11" data-kind="pdf" data-name="Invoice 1101.pdf">Invoice 1101.pdf<\/button> \(\$3,000\)/.test(opened);

/* the front: Due, Important and New only; the recommendation; why with no label */
delete S.ans.L1;          /* his own presses above are not news to him: the card as it first arrived */
/* every item on a card's rows is a full button, the same style as the others; only the recommended one is highlighted */
const styles = [];
for (const k of Object.keys(K)) for (const b of (front(K[k]).match(/<div class="acts[^"]*">[\s\S]*?<\/div>/g) || []).join("").match(/<button class="btn[^"]*" data-a="[^"]+"/g) || []) styles.push(b);
out.allButtons = styles.filter((b) => / quiet"/.test(b) || !/class="btn( primary)?( )?"/.test(b.replace(/ data-a.*/, ""))).slice(0, 5);
/* a day marker never reaches the page as text: the recommendation, why, a question, its choices, the story */
const marked = base({id: "L60", key: "L60", title: "Visit at {day:2026-11-19|morning}", needs: "answer", rec_front: "Put the visit on your calendar for {day:2026-11-19}, 6:00 to 6:15 AM.",
  why: "The visit is {day:2026-11-20}.", detail: "Booked for {day:2026-11-21}.", questions: [{ask: "Keep {day:2026-11-19}?", choices: [{label: "Yes, {day:2026-11-19}", text: "Yes", recommended: true}]}]});
S.items.push(marked); S.open["card:L60"] = true;
out.noToken = front(marked).indexOf("{day:") < 0 && front(marked).indexOf("{") < 0;
/* an older card with choices and no question text still shows a question, numbered, with the choices under it */
const dry = base({id: "L61", key: "L61", title: "Get a refund for the leaking head on job 12-345 Corner Kitchen", needs: "answer",
  wants: "Ask the supplier first.", recommended: "Ask the supplier first.", rec_front: "Ask the supplier first.", asks: [], questions: [],
  choices: [{label: "Supplier A", text: "Supplier A", recommended: true}, {label: "Supplier B", text: "Supplier B"}, {label: "Not sure, look it up", text: "Not sure, look it up"}]});
S.items.push(dry);
const dh = front(dry);
out.dryQuestion = {shown: /<li><div class="q-ask">Which do you choose\?/.test(dh), under: btns(dh.slice(dh.indexOf('<ol class="qs">'), dh.indexOf("</ol>"))).map((b) => b.label)};
const f1 = front(K.K1);
out.front = {tags: (f1.match(/<span class="tag [^"]*">([^<]+)<\/span>/g) || []).map((t) => t.replace(/<[^>]+>/g, "")),
  rec: /<div class="rec-front">Recommended: Send Dana a short reminder about both invoices\.<\/div>/.test(f1),
  why: /<div class="why">Two invoices to Acme, \$6,000 in all, are unpaid\. One was due 10\/1, and there has been no reply in over two weeks\.<\/div>/.test(f1),
  noLabel: f1.indexOf("Here because") < 0, box: /placeholder="Ask or tell me about this card..."/.test(f1)};
/* under each question, in order: its primary action (marked *) and its choices, for every kind; and a question with a
   recommendation but no choices or calendar details (yes is doing it) */
const underQ2 = (it) => { const h = front(it), q = h.indexOf('<ol class="qs">'); if (q < 0) return [];
  return h.slice(q, h.indexOf("</ol>", q)).split("<li>").slice(1).map((li) => { const out = [li.match(/<div class="q-ask">([^<]*)/)[1].trim()];
    const re = /<button class="btn( primary)?[^"]*" data-a="[^"]+"[^>]*>([^<]*)<\/button>/g; let m; while ((m = re.exec(li))) out.push(m[2].replace(/&amp;/g, "&") + (m[1] ? "*" : "")); return out; }); };
out.underQ = {}; for (const k of Object.keys(K)) out.underQ[k] = underQ2(K[k]);
const visit = base({id: "L62", key: "L62", title: "The inspector visits the shop", needs: "answer", rec_front: "Put the visit on your calendar for today, 6:00 to 6:15 AM.",
  why: "The inspector set a time.", asks: ["Put it on your calendar?"], questions: [{ask: "Put it on your calendar?", choices: []}]});
S.items.push(visit);
out.underQ.yesNo = underQ2(visit);
/* 9. Save sits beside the box always and closes the card in one press; a rule read from his words is proposed under the box with
   Approve, Disapprove, Discuss and Cancel, each its own press; Cancel gives his words back to the box */
delete S.drafts.L3; delete S.box.L3;
out.saveAlways = btns(front(K.K3)).filter((b) => b.a === "box-save").map((b) => b.label);
out.saveLeaves = [L.stays(K.K3, {action: "answer", text: "Called them, all set."}), L.thinks({action: "answer", text: "Called them, all set."})];
const ro = base({id: "L70", key: "L70", title: "Your UPS package shipped", needs: "answer", why: "UPS says it shipped.", status: "Rule proposed", teach: [],
  rule_offer: {text: "Mark every shipping notice Done.", way: "card_rule", say: "It catches shipping notices from any carrier.", words: "From now on mark these done", at: "2026-11-19T09:00:00", talk: [], reason: "Shipping notices need nothing from me."}});
S.items.push(ro);
const roHtml = front(ro), roAt = roHtml.indexOf('class="rule-offer"');
out.offer = {after: roAt > roHtml.indexOf('data-a="box-save"'), rule: roHtml.indexOf("Proposed rule: <b>Mark every shipping notice Done.</b>") > 0,
  said: roHtml.indexOf("It catches shipping notices from any carrier.") > 0, row: btns(roHtml.slice(roAt)).map((b) => b.label)};
out.offerPress = ["ro-approve", "ro-disapprove", "ro-cancel"].map((a) => { const r = press(ro, a)[0]; delete S.ans.L70;
  return [JSON.parse(r.text).press.do, r.keepDraft === undefined ? null : r.keepDraft, L.stays(ro, r), L.thinks(r)]; });
press(ro, "ro-discuss");
out.discussBox = /How should the rule read\?/.test(front(ro));
S.drafts["ro:L70"] = "Only UPS and FedEx ones";
const dr = press(ro, "ro-send")[0];
out.discuss = [JSON.parse(dr.text).press, L.stays(ro, dr), L.thinks(dr)];
out.rewording = /Rewording\.\.\./.test(front(ro)) && btns(front(ro).slice(front(ro).indexOf('class="rule-offer"'))).length === 0;
delete S.ans.L70;
out.noOffer = front(K.K3).indexOf('class="rule-offer"') < 0;
out.reasons = [front(K.K11).indexOf('<div class="why rule-why">Because: Sale mail needs nothing from me.</div>') > 0,
               roHtml.indexOf('Proposed rule: <b>Mark every shipping notice Done.</b></div><div class="ro-why">Because: Shipping notices need nothing from me.</div>') > 0];
const sc = Object.assign({}, K.K18, {id: "L71", key: "L71", rule_scan: {id: "20261119-100000-4", n: 3, said: "Your rule was applied to 3 other cards.", undone: null}});
const scHtml = front(sc);
out.scanNote = [scHtml.indexOf("Your rule was applied to 3 other cards.") > 0, btns(scHtml).filter((b) => b.a === "scan-undo").map((b) => b.label)];
/* P. the pick (picks.py): the card's first button, not drawn twice; one press sends that choice, marked as the pick; what he
   did last time on a card like it sits beside it; a press pick sends its press; a closed card has none */
const pk = base({id: "L33", key: "L33", title: "Pat asks which day for the shed", needs: "answer", why: "x", asks: ["Which day?"],
  questions: [{ask: "Which day?", choices: [{label: "Thursday works", text: "Thursday works", id: "thu", meaning: "agrees"}, {label: "Ask for Friday", text: "Ask for Friday"}]}],
  pick: {do: "choice", text: "Thursday works", label: "Thursday works", by: "writer"}, last_time: {do: "words", words: "Call Pat", label: "Call Pat"}});
S.items.push(pk);
const pkb = btns(front(pk));
out.pickFirst = [pkb[0].a, pkb[0].label, pkb[1].a, pkb[1].label, pkb.filter((b) => b.label === "Thursday works").length];
out.pickPress = press(pk, "pick").map((r) => [r.text, r.pick, r.button, r.meaning]);
out.lastPress = press(pk, "last-time").map((r) => [r.action, r.text, r.pick || null]);
const pd = base({id: "L34", key: "L34", title: "A shipment went out", state: "handled", needs: "nothing", why: "x", pick: {do: "press", press: "done", label: "Done", by: "program"}});
S.items.push(pd);
const pdb = btns(front(pd)).map((b) => b.a);
out.pickDone = [pdb[0], pdb.indexOf("done") >= 0, what(press(pd, "pick")), press(pd, "pick")[0].pick];
const pdr = press(pd, "drop"), pgi = press(pd, "got-it");
out.dropGot = [what(pdr), what(pgi), L.said(pd, pdr[0]), L.said(pd, pgi[0])];
out.pickClosed = btns(front(Object.assign({}, pd, {id: "L35", key: "L35", state: "done", status: "Done"}))).some((b) => b.a === "pick");
console.log(JSON.stringify(out));
'''

WANT_ROWS = {
    "K1": ["Send reminder", "Call Dana instead", "Other", "Reply", "Done", "Drop", "Snooze", "Not needed"],
    "K2": ["Check and send", "Other", "Done", "Drop", "Snooze"],
    "K3": ["Done", "Reply", "Drop", "Snooze", "Other"],
    "K4": ["Other", "Done", "Drop", "Snooze"],
    "K5": ["Got it", "Done", "Reply", "Drop", "Snooze", "Not needed", "Other"],
    "K6": ["Done", "Drop", "Snooze", "Other"],
    "K7": ["Send reminder", "Keep waiting", "Other", "Reply", "Done", "Drop", "Snooze", "Not needed"],
    "K8": ["Add to calendar", "Pick another time", "Other", "Done", "Drop", "Snooze"],
    "K9": ["Junk", "Never junk", "Other", "Done", "Drop", "Snooze"],
    "K10": ["Show their mail", "Hold it", "Other", "Done", "Drop", "Snooze"],
    "K11": ["Save this rule", "Other", "No", "Snooze"],
    "K12": ["Yes, do it and notify me", "Yes, do it quietly", "Other", "No", "Snooze"],
    "K13": ["Update", "Done", "Drop", "Snooze", "Other"],
    "K14": [],
    "K15": ["Done", "Drop", "Snooze", "Other"],
    "K16": ["Yes, write it", "Other", "No", "Snooze"],
    "K17": ["Bring it back", "Done"],
    "K18": ["Bring it back"],
    "K19": ["Done", "Drop", "Snooze", "Other"],
    "K20": ["Red", "Blue", "Other", "Done", "Drop", "Snooze"],
    "K21": ["Send reminder", "Keep waiting", "Other", "Reply", "Done", "Drop", "Snooze", "Not needed"],
    "K22": ["Check and send", "Other", "Done", "Drop", "Snooze"],
}


# under each question: its words, then its buttons in order, the primary one marked *
WANT_UNDER = {
    "K1": [["Remind Dana about the $6,000?", "Send reminder*", "Call Dana instead", "Other"]],
    "K2": [["Send this reply?", "Check and send*", "Other"]],
    "K4": [["Which job is this for?", "Other"]],
    "K7": [["Remind Dana, or keep waiting?", "Send reminder*", "Keep waiting", "Other"]],
    "K8": [["Put it on your calendar?", "Add to calendar*", "Pick another time", "Other"]],
    "K21": [["Send Dana a reminder?", "Send reminder*", "Keep waiting", "Other"]],
    "K22": [["Send this to Pat?", "Check and send*", "Other"]],
    "K9": [["Junk?", "Junk", "Never junk", "Other"]],
    "K10": [["Show their mail?", "Show their mail", "Hold it", "Other"]],
    "K11": [["Approve this rule?", "Save this rule*", "Other"]],
    "K12": [["Always do it?", "Yes, do it and notify me", "Yes, do it quietly", "Other"]],
    "K16": [["Write it?", "Yes, write it*", "Other"]],
    "K20": [["Which?", "Red", "Blue", "Other"]],
    "yesNo": [["Put it on your calendar?", "Go ahead*", "Other"]],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    # the script goes in on stdin: as an argument it passes Windows' 32,767-character command line limit
    r = subprocess.run(["node", "-e", "eval(require('fs').readFileSync(0, 'utf8'))", PAGE], input=NODE, capture_output=True, text=True,
                       encoding="utf-8", timeout=120)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        print("FAIL the page script did not run under node: " + (r.stderr or r.stdout)[-1500:])
        return 1
    for k, want in WANT_ROWS.items():
        check(f"1. {k}: exactly its buttons, in order", o["rows"].get(k), want)
    for k in list(WANT_ROWS) + ["yesNo"]:
        check(f"1. {k}: under each question, its primary action and its choices", o["underQ"].get(k), WANT_UNDER.get(k, []))
    check("1. K14 old cards: each row Keep, Snooze, Done", o["oldRows"], ["Keep", "Snooze", "Done", "Keep", "Snooze", "Done", "Save"])
    check("1. K15 weekly review: its rows on the new labels, then Done, Drop, Snooze and Other", o["reviewRows"], ["Keep", "Snooze", "Done", "Done", "Drop", "Snooze", "Other", "Save"])
    check("1. no More on any card", o["noMore"], True)
    check("2. each label leads to the same press on every card", o["oneMeaning"], [])
    check("2. Done sends Done on every card", o["done"], ["done"] * 7)
    check("2. No sends No on a rule card, a standing approval offer and a project write", o["no"], ["no"] * 3)
    check("2. each choice carries its button id and meaning (the writer's own, or its place and other)", o["choiceIds"], [["red", "agrees"], ["q1-2", "other"]])
    check("2. ... at the press it says only Got it and what follows, and waits for the engine's own line; No on a rule card says No",
          [o.get("switchSaid"), o.get("noSaid")], [[["Got it. I'll offer a rule to hide these.", True], ["Got it. I'll keep showing these.", True]], "Got it. I didn't make the rule."])
    check("2. a switchable button is drawn at the end of the row, and its press is its own name", [o.get("switchRow"), o.get("switchPress")],
          [["Got it", "Done", "Drop", "Snooze", "Not needed", "Other", "Hide mailings like this", "Keep showing these"], ["hide_like_this", "keep_showing"]])
    check("2. ... and its press sends them with the choice's words", o["choicePress"], [{"text": "Red", "button": "red", "meaning": "agrees"}])
    check("2. Snooze opens the same choices on every card", o["later"], ["later"] * 3)
    check("4. a two-question card numbers its questions, each with its recommended answer first, its other choices and Other",
          o["twoFront"], {"numbered": 2, "rec2": True, "qButtons": ["Send reminder1", "Keep waiting1", "Other1", "No late fee2", "Add late fee2", "Other2"],
                          "row": ["Done", "Drop", "Snooze", "Save"]})
    check("4. Other on question 2 marks the box \"Your answer to 2:\"", o["otherBox"], True)
    check("4. ... and the words go as question 2's answer", o["otherAnswer"], [{"action": "answer", "text": "Only if they are 30 days late", "question": 2}])
    check("4. question 2's own button answers question 2", o["choiceQ2"], [{"text": "No late fee", "question": 2, "button": "q2-1", "meaning": "other"}])
    check("3. typed words, once acted on, leave a card that still needs him open where it was, with its buttons", o["typedStays"], True)
    check("3. ... and it says Reading... while the assistant reads them", o["reading"], True)
    check("5. Not needed opens Just this one, Everything from this sender, Other", o["nnPanel"], ["Just this one", "Everything from this sender", "Other", "Cancel"])
    check("5. Just this one", o["nnThis"], [{"name": "not_needed", "scope": "this"}])
    check("5. Everything from this sender is today's Junk", o["nnSender"], [{"name": "junk"}])
    check("5. Other marks the box \"What did you not need?\"", o["nnBox"], True)
    check("5. ... and the words become a rule card to approve", o["nnOther"], [{"name": "not_needed", "scope": "kind", "words": "sale emails from this supplier"}])
    check("6. Context links the paper, the picture and both emails", o["ctxLinks"],
          ["Invoice 1101.pdf", "site photo", "your email of Tue 11/3 9:41 AM", "Dana's email of Mon 11/16 8:00 AM"])
    check("6. the PDF opens as the PDF over the page, with Close", o["pdf"], {"frame": True, "close": True, "focus": "close"})
    check("6. a paper or picture says Opening... until it has loaded", o["opening"], True)
    check("6. a message and a paper the story speaks of are linked in its own words; no list after it", o["inline"],
          {"msg": True, "paper": True, "noTail": True})
    check("a date written plainly on a card reads as words (Sat 11/21), never 2026-11-21", o["bareDay"], True)
    check("Other on a one-question card marks the box \"Your answer to 1:\"", o["answer1"], True)
    check("an open card with an answer already read, or one still waiting, keeps Done, Later and the box; only an unread one says You answered",
          o["notDead"], {"read": {"hidden": False, "buttons": True, "box": True, "answeredLine": False},
                         "unread": {"hidden": False, "buttons": True, "box": True, "answeredLine": True}})
    check("6. Close returns to the card", o["closed"], {"view": None, "hidden": True, "focus": "card"})
    check("6. the picture opens as the picture", o["picture"], True)
    check("6. the email opens as the email, read only", o["email"], {"url": "api/mail/thread?id=21", "shows": True, "noButtons": True})
    check("7. the opened card shows only Context and Conversation, or Context, the draft and Conversation", o["openedSections"],
          {"invoice": ["Context", "Conversation"], "draft": ["Context", "The draft", "Conversation"], "folded": False, "gone": []})
    check("7. Conversation holds his question and the reply, oldest first", o["conversation"], True)
    check("7. Context names the paper in its sentence, as a link", o["ctxSentence"], True)
    check("8. the front: only Due, Important, New; the recommendation; why with no label; the box", o["front"],
          {"tags": ["Was due Thu 10/1", "Important", "New"], "rec": True, "why": True, "noLabel": True, "box": True})
    check("every item on a card's rows is a full button (none drawn as plain text); only the recommended one highlighted", o["allButtons"], [])
    check("no day marker or other { token reaches the page on any part of a card", o["noToken"], True)
    check("an older card with choices but no question text shows its question, with its choices under it",
          o["dryQuestion"], {"shown": True, "under": ["Supplier A", "Supplier B", "Not sure, look it up", "Other"]})
    check("9. Save sits beside the box even when it is empty", o["saveAlways"], ["Save"])
    check("9. one press of Save sends the words and takes the card out of the way", o["saveLeaves"], [False, True])
    check("9. a rule read from his words: under the box, the answer, the rule in one sentence, four buttons", o["offer"],
          {"after": True, "rule": True, "said": True, "row": ["Approve", "Disapprove", "Discuss", "Cancel"]})
    check("9. Approve and Disapprove are runs that take the card out of the way; Cancel stays and gives his words back", o["offerPress"],
          [["approve", None, False, True], ["disapprove", None, False, True], ["cancel", "From now on mark these done", True, False]])
    check("9. Discuss opens a reply box under the proposal", o["discussBox"], True)
    check("9. ... whose words reword the rule on the card, which stays", o["discuss"],
          [{"name": "rule_offer", "do": "discuss", "words": "Only UPS and FedEx ones"}, True, True])
    check("9. while it is reworded the card says so, with no buttons to press twice", o["rewording"], True)
    check("9. a card with no rule proposed shows no rule buttons", o["noOffer"], True)
    check("R the rule card and a rule proposed from words both show the reason under the rule", o["reasons"], [True, True])
    check("9. the card a rule came from says what it did to other cards, with one Undo", o["scanNote"], [True, ["Undo"]])
    check("P. the pick is the card's first button, then what he did last time; the picked choice is not drawn twice",
          o.get("pickFirst"), ["pick", "Thursday works", "last-time", "Last time: Call Pat", 1])
    check("P. one press of the pick sends that choice with its id and meaning, marked as the pick", o.get("pickPress"),
          [["Thursday works", "1", "thu", "agrees"]])
    check("P. Last time sends what he did then, not marked as the pick", o.get("lastPress"), [["answer", "Call Pat", None]])
    check("P. a Done pick: first, no second Done; its press is Done, marked as the pick", o.get("pickDone"),
          ["pick", False, ["done"], "1"])
    check("P. a closed card shows no pick", o.get("pickClosed"), False)
    check("D. Drop and Got it are their own presses, each with its own words", o.get("dropGot"),
          [["drop"], ["got_it"], "Dropped. I won't bring it up again unless something new comes in about it.", "Got it. This card is closed."])
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
