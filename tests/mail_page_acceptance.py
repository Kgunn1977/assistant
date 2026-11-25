r"""Acceptance: the page's side of the mail system (page.html): the Mail part, the writer for a draft made from a message,
the Ready to send summary. The page's own script functions are cut out of page.html and run under node with stand-in data
and a stand-in fetch; there is no server, and nothing outside this process is touched.

    python tests\mail_page_acceptance.py
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
PAGE = os.path.join(PKG, "engine", "System", "live_page", "page.html")
results = []

NODE = r'''
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8").replace(/\r\n/g, "\n");
const pick = (name) => { const i = src.indexOf("  function " + name + "("); if (i < 0) throw new Error("no function " + name);
  let d = 0, j = src.indexOf("{", i); for (; j < src.length; j++) { if (src[j] === "{") d++; else if (src[j] === "}" && --d === 0) break; } return src.slice(i, j + 1); };
const between = (a, b) => { const i = src.indexOf(a), j = src.indexOf(b, i); if (i < 0 || j < 0) throw new Error("no region " + a); return src.slice(i, j); };
const line = (re) => src.match(re)[0];
const code = [
  between("  function $(id) {", "  /* ---------- what each item is"),
  between("  function pressOf(a)", "  function pressRec("), pick("pressName"), pick("headerOf"), pick("find"), pick("attKind"), pick("attView"), pick("viewDraw"),
  line(/  var AREAS = [^\n]+\n/), line(/  var DEF_AREA = [^\n]+\n/), line(/  var FEED_KINDS = [^\n]+\n/), pick("rmKeys"), pick("layoutOf"), pick("secTitle"), pick("secDefault"), pick("secName"), pick("hiddenSec"),
  between("  var COMPOSE = ", "  /* ---------- the direct box"),
].join("\n");

const TT = {sent: [], timers: [], urls: [], toasts: [], kept: 0, renders: 0, els: {}, mode: "ok", scrolled: []};
const prelude = `
  var S = {meta: {send: {on: true, accounts: ["me@a.example", "me@b.example"]}, settings: {page: {hidden: []}}}, items: [], ans: {}, err: {}, panel: {}, drafts: {}, open: {},
           wup: {}, wo: {}, rdGone: {}, rdAsk: {}, rdAll: {}, kept: {}, db: {}, live: "on", listening: true, mail: null};
  var acting = null, device = "Computer, test";
  function keepGet() { return null; } function keepSet() {}
  function render() { TT.renders++; renderMail(); }
  function setHtml(el, html) { el._html = html; el.innerHTML = html; }
  function keepDrafts() { TT.kept++; }
  function chgSend(key, text, label, result) { TT.sent.push({key: key, text: text}); S.ans[key] = {status: "saved"}; return true; }
  function toast(w) { TT.toasts.push(w); }
  function infoBtn() { return ""; }
  var VIEWQ = null; function viewPop(v) { TT.pop = v; return !!TT.popOk; }
`;
const mkRes = (o, status) => ({status: status || 200, ok: (status || 200) < 400, json: async () => o});
const LIST = {ok: true, accounts: [{address: "me@a.example", send: true, can: {archive: true, trash: true, label: true, read: true}},
                                   {address: "me@c.example", send: false, can: {archive: false, trash: true, label: true, read: true}}],
  rows: [{id: 7, account: "me@a.example", thread: "t", ts: "2026-11-18T07:39:39", when: "11/18/26 7:39 AM", from: "pat@x.example", from_name: "Pat <b>Lee</b>", to: "me@a.example", subject: "Lunch & <i>plans</i>", snippet: "Are you free", unread: true, inbox: true, labels: [], files: 2},
         {id: 8, account: "me@c.example", thread: "u", ts: "2026-11-17T09:00:00", when: "11/17/26 9:00 AM", from: "sam@x.example", from_name: "", to: "me@c.example", subject: "Old news", snippet: "", unread: false, inbox: true, labels: [], files: 0}],
  more: true, next: "2026-11-17T09:00:00"};
const THREAD = {ok: true, labels: {"me@a.example": ["Work", "Home"]}, messages: [
  {id: 6, account: "me@a.example", ts: "2026-11-17T07:00:00", when: "x", from: "me@a.example", from_name: "", to: ["pat@x.example"], cc: [], subject: "Lunch", text: "Earlier", unread: false, inbox: true, labels: [], files: []},
  {id: 7, account: "me@a.example", ts: "2026-11-18T07:39:39", when: "11/18/26 7:39 AM", from: "pat@x.example", from_name: "Pat", to: ["me@a.example"], cc: ["sam@x.example"], subject: "Lunch", text: "Hello <script>alert(1)</script> & more", unread: true, inbox: true, labels: ["Work"], files: [{name: "menu <1>.pdf", ref: "att:1", size: 2048}, {name: "sheet.xlsx", ref: "att:2", size: 10}]},
  {id: 9, account: "me@c.example", ts: "2026-11-18T08:00:00", when: "y", from: "sam@x.example", from_name: "Sam", to: ["me@c.example"], cc: [], subject: "Other", text: "Other box", unread: false, inbox: true, labels: [], files: []}]};
const fakeFetch = async (url) => {
  TT.urls.push(url);
  if (TT.mode === "hosted") return mkRes({}, 404);
  if (TT.mode === "busy") { TT.mode = "ok"; return mkRes({busy: true}); }
  if (url.indexOf("api/mail/thread") === 0) { if (TT.hold) await TT.hold; return mkRes(THREAD); }
  if (url.indexOf("api/mail/labels") === 0) return mkRes({ok: true, address: "me@a.example", labels: ["Bills", "Home", "Work"]});
  if (url.indexOf("api/mail/sample") === 0) {
    const m = /[?&]id=(\d+)/.exec(url), id = m ? +m[1] : 21;
    const list = [{id: 21, when: "a", subject: "Newest one"}, {id: 22, when: "b", subject: "Middle one"}, {id: 23, when: "c", subject: "Oldest one"}];
    const one = list.filter((r) => r.id === id)[0];
    return mkRes({ok: true, sender: "dana@x.example", list: list, message: {id: id, account: "me@a.example", ts: "2026-11-18T07:00:00", when: "x", from: "dana@x.example",
      from_name: "Dana", to: ["me@a.example"], cc: [], subject: one.subject, text: one.subject + " <b>body</b>", unread: true, inbox: true, labels: ["Work"], files: []}});
  }
  if (url.indexOf("api/mail?") === 0) return mkRes(LIST);
  return mkRes({}, 404);
};
const fakeTimeout = (fn, ms) => { TT.timers.push({fn: fn, ms: ms}); return TT.timers.length; };
const win = {pageYOffset: 120, scrollTo: (x, y) => TT.scrolled.push(y), location: {search: ""}};
const doc = {getElementById: (id) => (id in TT.els ? TT.els[id] : null), addEventListener: () => 0, querySelector: () => null};
const fixed = 1700000000000; Date.now = () => fixed;
const L = new Function("TT", "fetch", "setTimeout", "window", "document", "setInterval", prelude + code + `
  S.mail = mailNew();
  return {S: S, mailNew: mailNew, layoutOf: layoutOf, secName: secName, hiddenSec: hiddenSec, mailLoad: mailLoad, mailOpen: mailOpen, mailBack: mailBack,
          renderMail: renderMail, mailClick: mailClick, sampleLoad: sampleLoad, sampleHtml: sampleHtml, wDraft: wDraft, wPayload: wPayload, wSetType: wSetType, wRemoveFile: wRemoveFile, wChanged: wChanged,
          wClick: wClick, rdCardHtml: rdCardHtml, writerHtml: writerHtml, wProblem: wProblem, DEF_AREA: DEF_AREA, COMPOSE: COMPOSE, rdClick: rdClick, mailMsgHtml: mailMsgHtml, attView: attView, viewDraw: viewDraw};
`)(TT, fakeFetch, fakeTimeout, win, doc, () => 0);
const S = L.S, out = {};
const btn = (attrs) => ({getAttribute: (n) => (n in attrs ? attrs[n] : null)});
const box = () => TT.els.mail.innerHTML;
TT.els = {"sec-mail": {hidden: true}, "mail": {_html: null, innerHTML: "", querySelector: () => null}, "sec-ready": {}};

(async () => {
  // 1. the part is known, placed at the bottom by default, named, and placeable and hideable like the others
  out.dflt = L.layoutOf(null);
  out.name = L.secName("mail");
  out.moved = L.layoutOf({top: ["mail", "chat"], left: ["decide"], right: ["today"], bottom: ["changes"]});
  out.movedOld = L.layoutOf({main: ["decide"], side: ["today"]}).bottom;
  S.meta.settings.page.hidden = ["mail"]; out.hidden = L.hiddenSec("mail", {}); out.hiddenOther = L.hiddenSec("chat", {});
  S.meta.settings.page.hidden = [];
  out.visible = L.hiddenSec("mail", {});

  // 2. the list from a stand-in /api/mail, the thread from a stand-in /api/mail/thread
  L.renderMail();
  out.sectionShown = TT.els["sec-mail"].hidden === false;
  await new Promise((r) => setImmediate(r));
  await new Promise((r) => setImmediate(r));
  L.renderMail();
  out.listUrl = TT.urls[0];
  const html = box();
  out.rowCount = (html.match(/<li class="mail-row/g) || []).length;
  const foldWas = S.mail.fold;
  S.mail.fold = [{address: "me@one.example", folders: []}, {address: "me@two.example", folders: []}];
  L.renderMail();
  const tree = box();
  out.layout = [(tree.match(/class="btn mail-grip/g) || []).length === 4, tree.indexOf('class="mail-div"') >= 0, /style="--mail-w/.test(tree)];
  // a mailbox the list knows but with no folders stored is still in the column, with its Inbox; its title only folds
  S.mail.fold = [{address: "me@a.example", folders: [{id: "I", path: "Inbox", kind: "inbox"}, {id: "X", path: "Inbox/Suppliers", parent: "I"}]}];
  L.renderMail();
  const t2 = box(), urlsWas = TT.urls.length, acctWas = S.mail.account, viewWas = S.mail.view;
  L.mailClick("mail-shut", btn({"data-acct": "me@c.example"}));
  out.treeAll = {both: t2.indexOf('data-acct="me@a.example"><div class="mail-ah">') >= 0 && t2.indexOf('data-acct="me@c.example"><div class="mail-ah">') >= 0,
    inboxRow: t2.indexOf('data-a="mail-folder" data-acct="me@c.example" data-fid="">Inbox') >= 0,
    titleFolds: /<button class="mail-fold head" type="button" data-a="mail-shut" data-acct="me@a.example" aria-expanded="true"/.test(t2) && t2.indexOf("fold-line") < 0,
    titleKeepsList: TT.urls.length === urlsWas && S.mail.account === acctWas && S.mail.view === viewWas};
  S.mail.fold = foldWas;
  L.renderMail();
  out.unreadRows = (html.match(/<li class="mail-row unread"/g) || []).length;
  out.readRowPlain = /<li class="mail-row" data-a="mail-open" data-id="8"/.test(html);
  out.listEscaped = html.indexOf("Pat &lt;b&gt;Lee&lt;/b&gt;") >= 0 && html.indexOf("Lunch &amp; &lt;i&gt;plans&lt;/i&gt;") >= 0 && html.indexOf("<b>Lee") < 0 && html.indexOf("<i>plans") < 0;
  out.clip = html.indexOf("2 attachments") >= 0;
  out.older = html.indexOf('data-a="mail-older"') >= 0;
  out.filters = ["All addresses", "me@a.example", "me@c.example", "Inbox", "Unread", "All mail", "New email", ">Search<"].every((w) => html.indexOf(w) >= 0);
  L.mailClick("mail-older", btn({}));
  await new Promise((r) => setImmediate(r));
  out.olderUrl = TT.urls[TT.urls.length - 1];
  // the clicked email is drawn at once from its row, before the thread answers; the part keeps its height and the page stays put
  let release; TT.hold = new Promise((r) => { release = r; });
  TT.els.mail.offsetHeight = 640; TT.els.mail.style = {};
  TT.els["sec-mail"].getBoundingClientRect = () => ({top: 40}); TT.els["sec-mail"].scrollIntoView = () => TT.scrolled.push("jump");
  const opening = L.mailClick("mail-open", btn({"data-id": "7"}));
  await new Promise((r) => setImmediate(r));
  const pk = box();
  out.peek = {sender: pk.indexOf("Pat &lt;b&gt;Lee&lt;/b&gt;") >= 0, subject: pk.indexOf("Lunch &amp; &lt;i&gt;plans&lt;/i&gt;") >= 0, first: pk.indexOf("Are you free") >= 0,
              opening: pk.indexOf("Opening...") >= 0, back: pk.indexOf('data-a="mail-back"') >= 0, stub: pk.indexOf("Getting the email.") >= 0,
              shown: TT.els["sec-mail"].hidden === false, height: TT.els.mail.style.minHeight, moved: TT.scrolled.length};
  release(); TT.hold = null;
  await new Promise((r) => setImmediate(r));
  await new Promise((r) => setImmediate(r));
  await new Promise((r) => setImmediate(r));
  L.renderMail();
  out.peekAfter = {height: TT.els.mail.style.minHeight, opening: box().indexOf("Opening...") >= 0};
  const th = box();
  out.threadUrl = TT.urls.filter((u) => u.indexOf("api/mail/thread") === 0)[0];
  out.threadBack = th.indexOf('data-a="mail-back"') >= 0;
  out.popOut = th.indexOf('data-a="mail-pop"') >= 0;
  out.scriptText = th.indexOf("<script>") < 0 && th.indexOf("&lt;script&gt;alert(1)&lt;/script&gt; &amp; more") >= 0;
  out.attachLink = th.indexOf('<a href="api/mail/file?ref=att%3A2&amp;msg=7" download="sheet.xlsx"') >= 0 && th.indexOf('data-a="mail-attview" data-ref="att:1"') >= 0 && th.indexOf('data-kind="pdf" data-msg="7">menu &lt;1&gt;.pdf') >= 0;
  // a PDF link opens in the pop-up window (stand-in window.open), else over the page with Download and a way back to the email
  const pb = btn({"data-ref": "att:1", "data-name": "menu.pdf", "data-kind": "pdf", "data-msg": "7"});
  TT.popOk = true; L.attView(pb); out.popAsked = !!TT.pop && TT.pop.kind === "pdf" && TT.pop.ref === "att:1" && TT.pop.msg === 7;
  TT.popOk = false; TT.els.viewer = {innerHTML: "", querySelector: () => null, setAttribute: () => 0}; S.db = {}; S.mail.hosted = false;
  S.view = {key: "", name: "Email", kind: "message", msg: 7, msgs: []}; L.attView(pb);
  const vh = TT.els.viewer.innerHTML;
  out.inline = vh.indexOf('<iframe class="view-pdf"') >= 0 && vh.indexOf('src="api/mail/file?ref=att%3A1&amp;view=1"') >= 0 && vh.indexOf('id="view-dl" href="api/mail/file?ref=att%3A1" download="menu.pdf"') >= 0 && vh.indexOf('data-a="view-back">Back to the email') >= 0;
  S.view = null;
  out.labelChip = th.indexOf('class="chip">Work ') >= 0 && th.indexOf("Remove label") >= 0;
  out.notRead = TT.sent.length === 1 && /"act":"read"/.test(TT.sent[0].text) && TT.sent[0].key.indexOf("mail:7:") === 0;   // opening an unread email marks it read (the setting is on)
  out.hideNote = th.indexOf("me@c.example: its sign-in does not allow archiving yet") >= 0;
  out.hiddenArchiveOtherBox = (th.match(/data-act="archive"/g) || []).length;
  L.mailBack(); out.scrolledBack = TT.scrolled.slice(); L.renderMail();
  out.backToList = box().indexOf('rows mail-list') >= 0;
  // busy: a retry after 3 seconds; the hosted page: the plain line
  TT.mode = "busy"; TT.timers.length = 0; L.mailLoad(false, true);
  await new Promise((r) => setImmediate(r)); await new Promise((r) => setImmediate(r));
  out.busyNote = S.mail.note; out.busyTimer = TT.timers.map((t) => t.ms);
  TT.timers[0].fn(); await new Promise((r) => setImmediate(r)); await new Promise((r) => setImmediate(r));
  out.busyDone = S.mail.rows.length;
  TT.mode = "hosted"; L.mailLoad(false, true); await new Promise((r) => setImmediate(r)); await new Promise((r) => setImmediate(r)); L.renderMail();
  out.hosted = box();
  TT.mode = "ok"; S.mail = L.mailNew(); S.mail.rows = LIST.rows.slice(); S.mail.accounts = LIST.accounts; S.mail.loaded = true; S.mail.started = true;

  // 3. the presses: exact keys and texts
  TT.sent.length = 0;
  S.mail.open = 7; S.mail.thread = {messages: THREAD.messages, labels: THREAD.labels};
  const press = (a, attrs, extra) => { L.mailClick(a, btn(Object.assign({"data-id": "7"}, attrs || {}))); };
  press("mail-draft", {"data-t": "reply"}); press("mail-draft", {"data-t": "reply_all"}); press("mail-draft", {"data-t": "forward"});
  press("mail-act", {"data-act": "archive"});
  press("mail-del-ask"); L.renderMail(); out.askTrash = box().indexOf("Move this email to the trash?") >= 0; out.noTrashYet = TT.sent.length;
  press("mail-del-go");
  TT.els["mlabs-7"] = {innerHTML: ""}; const before_ = TT.urls.length;
  press("mail-label-open");
  await new Promise((r) => setImmediate(r)); await new Promise((r) => setImmediate(r)); await new Promise((r) => setImmediate(r));
  L.renderMail();
  out.labelList = {url: TT.urls.slice(before_), list: TT.els["mlabs-7"].innerHTML, drawn: box().indexOf('<option value="Home">') >= 0 && box().indexOf('<option value="Bills">') >= 0};
  press("mail-label-no"); press("mail-label-open");
  await new Promise((r) => setImmediate(r)); await new Promise((r) => setImmediate(r));
  out.labelAskedOnce = TT.urls.filter((u) => u.indexOf("api/mail/labels") === 0).length;
  TT.els["mlab-7"] = {value: "Work", focus() {}}; press("mail-label-go");
  press("mail-unlabel", {"data-label": "Work"});
  press("mail-act", {"data-act": "unread"}); press("mail-act", {"data-act": "read"});
  L.mailClick("mail-new", btn({}));
  out.sent = TT.sent.map((s) => [s.key, s.text]);
  out.outcomeShown = (() => { S.ans["mail:7:" + 1700000000000] = {status: "done", outcome: "Not done: this mailbox's sign-in does not allow changing mail yet."}; L.renderMail(); return box().indexOf("Not done: this mailbox&#39;s sign-in does not allow changing mail yet.") >= 0; })();

  // 4 to 6. the writer
  const src = {message: 7, account: "me@b.example", from: "pat@x.example", from_name: "Pat", to: ["me@b.example", "lee@x.example", "me@c.example"], cc: ["sam@x.example", "me@a.example"], ts: "2026-11-18T07:39:39", when: "11/18/26 7:39 AM",
               subject: "Lunch", text: "Original <b>text</b> here", files: [{name: "menu.pdf", ref: "msg:7:menu.pdf", size: 1024}]};
  const mk = () => ({key: "R1", id: "R1", title: "Reply", state: "question", ready: {batch: "b1", made_by: "x"},
    draft: {account: "me@a.example", to: ["pat@x.example"], cc: [], bcc: ["hid@x.example"], subject: "Re: Lunch", body: "Hi Pat", type: "reply", files: [{name: "own.pdf", ref: "up:1", size: 2048}], attach: ["own.pdf"], base: "B1", source: src}});
  let it = mk(); S.items = [it]; S.drafts = {}; S.panel = {}; S.ans = {};
  S.mail.accounts = LIST.accounts;
  const view = (p) => ({type: p.type, source: p.source, to: p.to, cc: p.cc, bcc: p.bcc, subject: p.subject, files: p.files.map((f) => f.name), attach: p.attach, account: p.account});
  out.default = view(L.wPayload("R1", it));
  const html0 = L.writerHtml(it);
  out.fromOptions = ["me@a.example", "me@b.example"].every((a) => html0.indexOf('<option value="' + a + '"') >= 0) && html0.indexOf('<option value="me@b.example" selected>') >= 0;
  out.typeChoice = ['<option value="new"', '<option value="reply" selected>', '<option value="reply_all"', '<option value="forward"'].every((w) => html0.indexOf(w) >= 0);
  out.bccField = html0.indexOf('data-w="bcc"') >= 0 && html0.indexOf('value="hid@x.example"') >= 0 && html0.indexOf("There is no blind copy") < 0;
  out.origFolded = html0.indexOf("<details") >= 0 && html0.indexOf("Original message from Pat, 11/18/26 7:39 AM: Lunch") >= 0 && html0.indexOf("Original &lt;b&gt;text&lt;/b&gt; here") >= 0;
  out.toTypes = {};
  for (const t of ["reply_all", "forward", "new", "reply"]) { L.wSetType("R1", it, t); out.toTypes[t] = view(L.wPayload("R1", it)); }
  L.wSetType("R1", it, "forward"); S.drafts["w:R1"].to = "zed@x.example"; L.wSetType("R1", it, "new"); L.wSetType("R1", it, "forward");
  out.fwdTyped = view(L.wPayload("R1", it)).to;
  // removing a file
  L.wSetType("R1", it, "forward");
  const before = view(L.wPayload("R1", it));
  L.wRemoveFile("R1", it, 0);
  const after = view(L.wPayload("R1", it)), pl = L.wPayload("R1", it);
  out.remove = {before: before.files, after: after.files, attach: pl.attach, shownAttach: pl.shown.attach, shownBcc: pl.shown.bcc, shownType: pl.shown.type, text: JSON.parse(JSON.stringify(pl)).files};
  out.problemNone = L.wProblem("R1", it);
  out.text = Object.keys(pl).concat(Object.keys(pl.shown));
  // 5. a stale saved edit, a changed one
  it = mk(); S.items = [it];
  S.drafts = {"w:R1": {account: "me@a.example", to: "old@x.example", cc: "", bcc: "", subject: "s", body: "b", files: [], attach: [], type: "reply", base: "OLD"}};
  out.staleTo = L.wPayload("R1", it).to; out.staleGone = !("w:R1" in S.drafts);
  S.drafts = {"w:R1": {account: "me@a.example", to: "zed@x.example", cc: "", bcc: "hid@x.example", subject: "Re: Lunch", body: "Hi Pat", files: [], attach: [], type: "reply", base: "B1"}};
  out.changedTo = L.wPayload("R1", it).to;
  out.note = L.wChanged("R1", it);
  const card = L.rdCardHtml(it);
  out.cardNote = card.indexOf("Changed on this device: To was pat@x.example, now zed@x.example") >= 0 && card.indexOf("Use the draft's recipients") >= 0;
  S.panel.R1 = "review"; out.reviewNote = L.writerHtml(it).indexOf("Changed on this device: To was pat@x.example, now zed@x.example") >= 0; delete S.panel.R1;
  L.wClick("w-userecips", btn({}), "R1", it);
  out.restored = L.wPayload("R1", it).to; out.noteAfter = L.wChanged("R1", it);
  S.drafts = {"w:R1": {account: "me@a.example", to: "pat@x.example", cc: "", bcc: "hid@x.example", subject: "Re: Lunch", body: "Hi Pat", files: [], attach: [], type: "reply"}};
  out.noBaseNoNote = L.wChanged("R1", it);
  // 6. the Ready card summary
  it = mk(); S.items = [it]; S.drafts = {}; S.panel = {};
  const sum = L.rdCardHtml(it);
  out.summary = {type: sum.indexOf("<b>Type:</b> Reply to Pat, 11/18/26 7:39 AM: Lunch") >= 0, from: sum.indexOf("<b>From:</b> me@b.example") >= 0, to: sum.indexOf("<b>To:</b> pat@x.example") >= 0,
    bcc: sum.indexOf("<b>Blind copy:</b> hid@x.example") >= 0, attached: sum.indexOf("<b>Attached:</b> own.pdf") >= 0, folded: sum.indexOf('<details class="more" data-d="wsrc:R1"><summary>') >= 0,
    orig: sum.indexOf("Original message from Pat, 11/18/26 7:39 AM: Lunch") >= 0 && sum.indexOf("Original &lt;b&gt;text&lt;/b&gt; here") >= 0 && sum.indexOf("<pre") >= 0};
  // send all carries the new fields
  TT.sent.length = 0; S.ans = {}; S.items = [it];
  L.rdClick("rd-all-go", btn({"data-grp": "b1"}));
  out.sendAll = TT.sent.length ? JSON.parse(TT.sent[0].text).send_all.emails[0] : null;
  // 7. a junk card's sample: the sender's newest email in the card, Older and Newer step through, nothing pressed
  S.sample = {}; TT.sent.length = 0; const from = TT.urls.length;
  L.sampleLoad("L5", null);
  await new Promise((r) => setImmediate(r)); await new Promise((r) => setImmediate(r));
  let sh = L.sampleHtml("L5");
  out.sampleFirst = {url: TT.urls[TT.urls.length - 1], newest: sh.indexOf("Newest one &lt;b&gt;body&lt;/b&gt;") >= 0,
    older: sh.indexOf('data-a="sample-step" data-id="22"') >= 0, newer: sh.indexOf("Newer") >= 0, count: sh.indexOf("1 of the 3 newest emails from dana@x.example") >= 0,
    bare: ["mail-act", "mail-draft", "mail-del-ask", "mail-label-open", "mail-unlabel", "Mark read"].every((w) => sh.indexOf(w) < 0)};
  L.sampleLoad("L5", 22);
  await new Promise((r) => setImmediate(r)); await new Promise((r) => setImmediate(r));
  sh = L.sampleHtml("L5");
  out.sampleStep = {url: TT.urls[TT.urls.length - 1], middle: sh.indexOf("Middle one") >= 0, older: sh.indexOf('data-id="23"') >= 0, newer: sh.indexOf('data-id="21"') >= 0,
    count: sh.indexOf("2 of the 3 newest emails") >= 0};
  out.sampleQuiet = {pressed: TT.sent.length, urls: TT.urls.slice(from).every((u) => u.indexOf("api/mail/sample?card=L5") === 0)};
  TT.mode = "hosted"; S.sample = {};
  L.sampleLoad("L5", null);
  await new Promise((r) => setImmediate(r)); await new Promise((r) => setImmediate(r));
  out.sampleHosted = L.sampleHtml("L5").indexOf("A sample can be read on the page served from your computer.") >= 0;
  TT.mode = "ok";
  // pictures from the internet in an email: shown unless Settings says Hide; then held back with Show pictures
  const picMsg = {id: 41, account: "me@a.example", ts: "2026-11-18T07:39:39", when: "x", from: "news@shop.example", from_name: "Shop", to: ["me@a.example"], cc: [],
                subject: "Sale", text: "Sale", html: true, remote: true, unread: false, inbox: true, labels: [], files: []};
  const picsOf = () => { const x = L.mailMsgHtml(picMsg); return [/pictures=1/.test(x), x.indexOf("Pictures from the internet are hidden") >= 0]; };
  const pageWas = S.meta.settings.page;
  S.meta.settings.page = Object.assign({}, pageWas); out.picsDefault = picsOf();
  S.meta.settings.page = Object.assign({}, pageWas, {mail_pictures: "hide"}); out.picsHide = picsOf();
  S.meta.settings.page = pageWas;
  // a popped-out email: Ready to send shows only the drafts started from it, and nothing when there are none
  const win2 = Object.assign({}, win, {location: {search: "?popout=7"}});
  const L2 = new Function("TT", "fetch", "setTimeout", "window", "document", "setInterval", prelude + "function addLines() {}" + code + `
  S.mail = mailNew(); return {S: S, renderReady: renderReady};`)(TT, fakeFetch, fakeTimeout, win2, doc, () => 0);
  const rd = {hidden: false, innerHTML: "", _html: ""}; TT.els["sec-ready"] = rd;
  const mine = Object.assign(mk(), {key: "R7", id: "R7", ready: {batch: "b1", made_by: "mail-draft:7:1"}});
  const other = Object.assign(mk(), {key: "R9", id: "R9", ready: {batch: "b2", made_by: "chat:9"}});
  L2.S.items = [mine, other]; L2.S.mail.out = {"7": "mail-draft:7:1"};
  L2.renderReady();
  out.popReady = [rd.hidden, rd.innerHTML.indexOf('"R7"') >= 0, rd.innerHTML.indexOf('"R9"') >= 0];
  L2.S.mail.out = {}; L2.renderReady(); out.popReadyNone = rd.hidden;
  console.log(JSON.stringify(out));
})().catch((e) => { console.log(JSON.stringify({error: String(e && e.stack || e)})); });
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    r = subprocess.run(["node", "-e", NODE, PAGE], capture_output=True, text=True, timeout=120)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        o = {"error": (r.stderr or r.stdout)[-800:]}
    if "error" in o:
        print("FAIL the page script did not run under node: " + o["error"])
        return 1
    html = open(PAGE, encoding="utf-8").read()

    # 1. the part
    d = o["dflt"]
    check("mail is a known part, default in bottom", d["bottom"], ["mail", "texts", "calendar"])
    check("the other parts are where they were", (d["top"], d["left"][:1], d["right"]), (["chat", "about"], ["feed"], ["today"]))
    check("it is named Email in the Settings part list", o["name"], "Email")
    check("it can be placed in another area", (o["moved"]["top"], "mail" in o["moved"]["bottom"]), (["mail", "chat", "about"], False))
    check("an older arrangement still gets it at the bottom", o["movedOld"], ["mail", "texts", "calendar"])
    check("it can be switched off like the others", (o["hidden"], o["hiddenOther"], o["visible"]), (True, False, False))
    check("its element is in the bottom area", html.index('id="sec-mail"') > html.index('id="area-bottom"'), True)

    # 2. the Mail part
    check("the part is drawn and asks for the list", (o["sectionShown"], o["listUrl"]), (True, "api/mail?view=inbox&account=&q=&limit=50"))
    check("the list has a row per message, the unread one marked", (o["rowCount"], o["unreadRows"], o["readRowPlain"]), (2, 1, True))
    check("the mailbox column: a drag handle on each of four mailboxes and the resizable divider, its width never written into the markup",
          o.get("layout"), [True, True, False])
    check("every mailbox the list knows is in the column (one with no folders stored gets its Inbox), and its title only opens and closes it",
          o.get("treeAll"), {"both": True, "inboxRow": True, "titleFolds": True, "titleKeepsList": True})
    check("an open email can be popped out into its own window", o.get("popOut"), True)
    check("pictures from the internet in an email show by default; with Hide in Settings they are held back with Show pictures",
          [o.get("picsDefault"), o.get("picsHide")], [[True, False], [False, True]])
    check("a popped-out email shows only the drafts started from it in Ready to send, and none when there are none",
          [o.get("popReady"), o.get("popReadyNone")], [[False, True, False], True])
    check("list text is escaped, never HTML", o["listEscaped"], True)
    check("a paperclip count, Older, address and view filters, search and New email", (o["clip"], o["older"], o["filters"]), (True, True, True))
    check("Older asks for the next page before the last time", o["olderUrl"], "api/mail?view=inbox&account=&q=&limit=50&before=2026-11-17T09%3A00%3A00")
    check("a clicked email shows its sender, subject and first words at once, with Opening, while the thread is still on its way",
          o["peek"], {"sender": True, "subject": True, "first": True, "opening": True, "back": True, "stub": False, "shown": True, "height": "640px", "moved": 0})
    check("... and the part lets go of its height once the email is there", o["peekAfter"], {"height": "", "opening": False})
    check("a thread is asked for by message id and has Back", (o["threadUrl"], o["threadBack"]), ("api/mail/thread?id=7", True))
    check("the Label box asks for the mailbox's label names and lists those not already on the email",
          o["labelList"], {"url": ["api/mail/labels?account=me%40a.example"], "list": '<option value="Bills"><option value="Home">', "drawn": True})
    check("... once per mailbox", o["labelAskedOnce"], 1)
    check("a body containing a script tag shows as text", o["scriptText"], True)
    check("a PDF attachment is a view button, any other kind a download link", o["attachLink"], True)
    check("a PDF link asks for the pop-up window", o["popAsked"], True)
    check("the viewer shows the PDF inline with Download and a way back to the email", o["inline"], True)
    check("labels show with a way to remove them", o["labelChip"], True)
    check("opening an unread message presses one Mark read (the setting is on by default)", o["notRead"], True)
    check("a button the mailbox cannot do is hidden and said once", (o["hideNote"], o["hiddenArchiveOtherBox"]), (True, 2))
    check("Back returns to the list at the same scroll", (o["scrolledBack"], o["backToList"]), ([120], True))
    check("busy: says so and tries again half a second later", (o["busyNote"], o["busyTimer"], o["busyDone"]), ("Mail is being updated. Trying again.", [500], 2))
    check("the hosted page gets the plain line", "Email works on the page served from your computer." in o["hosted"], True)

    # 3. presses
    k = "1700000000000"
    sent = o["sent"]
    want = [
        ["mail-draft:7:" + k, '{"mail_draft":{"message":7,"type":"reply"}}'],
        ["mail-draft:7:" + k, '{"mail_draft":{"message":7,"type":"reply_all"}}'],
        ["mail-draft:7:" + k, '{"mail_draft":{"message":7,"type":"forward"}}'],
        ["mail:7:" + k, '{"mail_act":{"message":7,"act":"archive"}}'],
        ["mail:7:" + k, '{"mail_act":{"message":7,"act":"trash"}}'],
        ["mail:7:" + k, '{"mail_act":{"message":7,"act":"label","label":"Work"}}'],
        ["mail:7:" + k, '{"mail_act":{"message":7,"act":"unlabel","label":"Work"}}'],
        ["mail:7:" + k, '{"mail_act":{"message":7,"act":"unread"}}'],
        ["mail:7:" + k, '{"mail_act":{"message":7,"act":"read"}}'],
        ["mail-draft:new:" + k, '{"mail_draft":{"message":null,"type":"new"}}'],
    ]
    check("Reply, Reply all, Forward, Archive, Delete, Label, Remove label, Mark unread, Mark read, New email: exact key and text", sent, want)
    check("Delete asks 'Move this email to the trash?' first and sends nothing until yes", (o["askTrash"], o["noTrashYet"]), (True, 4))
    check("an outcome shows on the message in plain words", o["outcomeShown"], True)

    # 4. the writer
    base = {"type": "reply", "source": 7, "to": ["pat@x.example"], "cc": [], "bcc": ["hid@x.example"], "subject": "Re: Lunch", "files": ["own.pdf"], "attach": ["own.pdf"], "account": "me@b.example"}
    check("From defaults to the account the message came to", o["default"], base)
    check("From lists every send account; Type has the four choices; Blind copy is there; the old no-blind-copy note is gone",
          (o["fromOptions"], o["typeChoice"], o["bccField"]), (True, True, True))
    check("the original is a folded details element", o["origFolded"], True)
    t = o["toTypes"]
    check("Reply all: from and to without my own addresses, cc without mine, Re:, the original's files then the others", t["reply_all"],
          dict(base, type="reply_all", to=["pat@x.example", "lee@x.example"], cc=["sam@x.example"], files=["menu.pdf", "own.pdf"], attach=["menu.pdf", "own.pdf"]))
    check("Forward: nobody typed yet, Fwd:, the original's files first then the others", t["forward"],
          dict(base, type="forward", to=[], cc=[], subject="Fwd: Lunch", files=["menu.pdf", "own.pdf"], attach=["menu.pdf", "own.pdf"]))
    check("New: the plain subject, the original's files dropped", t["new"], dict(base, type="new", source=None, to=[], cc=[], subject="Lunch"))
    check("Back to Reply: only the sender, with the original's files", t["reply"], dict(base, files=["menu.pdf", "own.pdf"], attach=["menu.pdf", "own.pdf"]))
    check("Forward keeps what was already typed in To", o["fwdTyped"], ["zed@x.example"])
    r_ = o["remove"]
    check("removing a file takes it out of files, attach and shown.attach",
          (r_["before"], r_["after"], r_["attach"], r_["shownAttach"], r_["text"]), (["menu.pdf", "own.pdf"], ["own.pdf"], ["own.pdf"], ["own.pdf"], [{"name": "own.pdf", "ref": "up:1"}]))
    check("bcc and type are in the payload and in shown", (r_["shownBcc"], r_["shownType"]), (["hid@x.example"], "forward"))
    check("the payload carries exactly the contract's fields", o["text"], ["account", "to", "cc", "bcc", "subject", "body", "type", "source", "files", "attach", "shown",
                                                                          "account", "to", "cc", "bcc", "type", "attach"])
    check("an email with a blind copy and files has no problem to fix", o["problemNone"], "")
    sa = o["sendAll"] or {}
    check("Send all carries bcc, type, source, files, attach and shown per email", (sa.get("bcc"), sa.get("type"), sa.get("source"), sa.get("files"), sa.get("attach"), sorted((sa.get("shown") or {}).keys())),
          (["hid@x.example"], "reply", 7, [{"name": "own.pdf", "ref": "up:1"}], ["own.pdf"], ["account", "attach", "bcc", "cc", "to", "type"]))

    # 5. a stale saved edit
    check("a saved edit with an older base is dropped", (o["staleTo"], o["staleGone"]), (["pat@x.example"], True))
    check("a saved edit with the same base and another To keeps it, and says so", (o["changedTo"], o["note"]), (["zed@x.example"], "Changed on this device: To was pat@x.example, now zed@x.example."))
    check("the note and the button are on the card", o["cardNote"], True)
    check("the note is in review too", o["reviewNote"], True)
    check("Use the draft's recipients restores them and clears the note", (o["restored"], o["noteAfter"]), (["pat@x.example"], ""))
    check("a saved edit with no base and the same recipients says nothing", o["noBaseNoNote"], "")

    # 6. the Ready card summary
    check("the Ready card shows Type, From, To, Blind copy, attachment names and a folded original", o["summary"],
          {"type": True, "from": True, "to": True, "bcc": True, "attached": True, "folded": True, "orig": True})

    # 7. a junk card's sample
    check("Read a sample opens the sender's newest email in the card, read only, with Older", o["sampleFirst"],
          {"url": "api/mail/sample?card=L5", "newest": True, "older": True, "newer": False, "count": True, "bare": True})
    check("Older steps to that sender's next email, with Older and Newer", o["sampleStep"],
          {"url": "api/mail/sample?card=L5&id=22", "middle": True, "older": True, "newer": True, "count": True})
    check("reading a sample presses nothing and asks only the sample door", o["sampleQuiet"], {"pressed": 0, "urls": True})
    check("the hosted page says a sample is read on the page served from the computer", o["sampleHosted"], True)
    check("a one-sender junk card links its sender's newest email in its Context", "if (it.sample && s !== 'done') o += '<p>' + viewLink('Their newest email'" in html, True)

    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
