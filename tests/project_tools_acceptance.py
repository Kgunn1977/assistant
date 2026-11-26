r"""Acceptance: the four project tools in Settings, Tools (engine\System\live\project_tools.py and the page's Tools part): Add roadmap
to a project, Add questions file to a project, Remove roadmap from a project, Remove questions file from a project. Made-up projects
and made-up open sessions in a throwaway folder; a stand-in takes the place of the message run, so nothing real is sent.

1. All four are listed, each with its plain words. The projects offered come from the open sessions and from what the assistant
   knows, each with whether the roadmap and the questions file are on there; a session in a worktree folder is not offered.
2. Add sends exactly ONE message, to the project's main session (the one the roadmap or the questions file recorded, else the most
   recently active one in that folder); the message asks the session to wait for the person's yes in that session, and names the
   one command to run after it. Nothing is run or changed in the project from here.
3. No session in the project, or the message not delivered: nothing is run; the answer says "Not sent" and the page shows the
   exact command to type in the project, with a Copy button that copies it. A project the assistant does not know, or one that
   already has the tool on, is not messaged.
4. Remove, after the page's confirm ("Turn the roadmap off in <project>? Its page stays as a record."), turns the tool off and
   changes nothing else: only its own files are deleted, the other projects are untouched, and no message is sent. Without the confirm the page
   sends nothing.
5. The page: each entry shows its words; pressing one lists the projects with on or off; the right buttons are drawn and send one
   press each; the answer the listener sends back is shown in one line.

    python tests\project_tools_acceptance.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
LIVE = os.path.join(PKG, "engine", "System", "live")
PAGE = os.path.join(PKG, "engine", "System", "live_page", "page.html")
results = []

FAKE = r'''
import json, os, sys
text = sys.stdin.read()
name = text.split("\nNAME\n", 1)[1].split("\nENDNAME", 1)[0]
body = text.split("\nBEGIN\n", 1)[1].rsplit("\nEND", 1)[0]
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"to": name, "message": body}) + "\n")
print("NOT REACHABLE" if os.environ.get("FAKE_MODE") == "fail" else "DELIVERED")
'''

INSIDE = r'''
import json, os, sys, time
root, base = sys.argv[1], sys.argv[2]
sys.path.insert(0, sys.argv[3])
import common, project_tools, answers
out = {}
P = lambda n: os.path.join(base, n)

def tree():
    seen = {}
    for top in (base, root):
        for d, _dirs, files in os.walk(top):
            for n in files:
                p = os.path.join(d, n)
                seen[os.path.relpath(p, os.path.dirname(base)).replace("\\", "/")] = open(p, "rb").read().hex()
    return seen

def press(op, tool, folder, n, session=None):
    words = {"folder": folder}
    if session:
        words["session"] = session
    rec = {"id": f"pt:{op}-{tool}:17000000{n:05d}", "action": "answer", "text": json.dumps(words), "at": "2026-11-19T12:00:00"}
    return answers.act_on_answer(rec)

def log():
    p = os.environ["FAKE_LOG"]
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []

out["listed"] = [(t["id"], t["name"], bool(t["words"]), t["command"]) for t in project_tools.listed()]
out["projects"] = {p["name"]: [p["roadmap"], p["questions"]] for p in project_tools.projects()}
out["found"] = {n: [(x["name"], x["child"], x["has"]) for x in project_tools.sessions_of(P(n))] for n in ("Alpha", "Bravo", "Charlie", "Delta")}

# add roadmap, Bravo (no recorded session: the most recently active one in the folder)
before = tree()
r = press("add", "roadmap", P("Bravo"), 1, "s3")
out["bravo"] = {"ok": r.get("ok"), "result": r.get("result"), "log": log(), "changed": tree() != before}
# add roadmap, Delta (the questions file recorded its main session; a newer session is open in the folder too)
n0 = len(log())
r = press("add", "roadmap", P("Delta"), 2, "s6")
out["delta"] = {"result": r.get("result"), "new": log()[n0:]}
# add questions, Alpha (the roadmap recorded its main session)
n0 = len(log())
r = press("add", "questions", P("Alpha"), 3, "s1")
out["alpha"] = {"result": r.get("result"), "new": log()[n0:]}
# no session
n0 = len(log())
r = press("add", "questions", P("Charlie"), 4, "s9")
out["charlie"] = {"result": r.get("result"), "new": log()[n0:]}
# already on, and not a known project
n0 = len(log())
out["already"] = [press("add", "roadmap", P("Alpha"), 5, "s1").get("result"), press("add", "roadmap", os.path.join(base, "Nowhere"), 6, "s1").get("result"), len(log()) - n0]
# not delivered
os.environ["FAKE_MODE"] = "fail"
n0 = len(log())
r = press("add", "roadmap", P("Bravo"), 7, "s4")
out["undelivered"] = {"result": r.get("result"), "attempts": len(log()) - n0}
os.environ["FAKE_MODE"] = ""
out["adds_changed_nothing"] = tree() == before

# remove, after the page's confirm (the page's part is checked under node): only that tool in that project goes
n0 = len(log())
before = tree()
r = press("remove", "roadmap", P("Alpha"), 8)
after = tree()
gone = sorted(k for k in before if k not in after)
new = sorted(k for k in after if k not in before)
changed = sorted(k for k in before if k in after and before[k] != after[k])
out["remove_roadmap"] = {"result": r.get("result"), "gone": gone, "new": new, "changed": changed, "sent": len(log()) - n0,
                         "listed": [e["folder"] for e in (common.read_json(os.path.join(root, "Live", "personal", "settings.json"), {}) or {}).get("roadmaps") or []],
                         "now": project_tools.roadmap_on(P("Alpha"))}
before = tree()
r = press("remove", "questions", P("Delta"), 9, "s6")
after = tree()
out["remove_wrong_session"] = [r.get("result"), project_tools.questions_on(P("Delta")), tree() == after]
r = press("remove", "questions", P("Delta"), 12, "uuid-delta-main")
after = tree()
out["remove_questions"] = {"result": r.get("result"), "changed": sorted(k for k in before if before[k] != after.get(k)),
                           "new": sorted(k for k in after if k not in before), "gone": sorted(k for k in before if k not in after),
                           "on": project_tools.questions_on(P("Delta")), "sent": len(log()) - n0}
before = tree()
out["remove_twice"] = [press("remove", "roadmap", P("Alpha"), 10).get("result"), press("remove", "questions", P("Delta"), 11, "uuid-delta-main").get("result"), tree() == before]
print(json.dumps(out))
'''

NODE = r'''
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8").replace(/\r\n/g, "\n");
const pick = (name) => { const i = src.indexOf("  function " + name + "("); if (i < 0) throw new Error("no function " + name);
  let d = 0, j = src.indexOf("{", i); for (; j < src.length; j++) { if (src[j] === "{") d++; else if (src[j] === "}" && --d === 0) break; } return src.slice(i, j + 1); };
const meta = JSON.parse(process.argv[2]);
const S = {meta: meta, ans: {}, mine: {}, listening: true, db: {posts: [], setAnswer: function (k, r) { this.posts.push({key: k, rec: r}); return Promise.resolve(); }}};
function h(s) { return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }
function isoLocal() { return "2026-11-19T12:00:00"; }
const device = "test";
let rendered = 0; function render() { rendered++; }
const copied = [];
const navigator = {clipboard: {writeText: (t) => { copied.push(t); return Promise.resolve(); }}};
const setTimeout = () => 0;
eval(src.slice(src.indexOf("  var PT = {"), src.indexOf("\n", src.indexOf("  var PT = {"))));
const gi = src.indexOf("  var PT_GUIDE = "); eval(src.slice(gi, src.indexOf("};", gi) + 2));
const xi = src.indexOf("  var INFO_X = "); eval(src.slice(xi, src.indexOf("};", xi) + 2));     // the (i) words the page draws itself
function D(x) { return new Date(x); }
function fmtDT(d) { return d.toISOString().slice(0, 16).replace("T", " "); }
const REB = {ask: false}, RLD = {ask: false}, HOME = {}, SLR = {st: null, busy: false, timer: 0, err: ""}; function homeKind() { return "other"; } S.open = S.open || {}; S.ans = S.ans || {};
const MODP = {parts: {}};  // the Settings part as one piece (the page now gathers parts for its Settings navigation)
function sPart(id, title, inside) { return '<details class="fold" id="set-' + id + '"><summary>' + title + '</summary><div class="panel-box host set-in">' + inside + '</div></details>'; }
for (const f of ["infoBtn", "sAll", "cmdList", "cmdItems", "modEach", "modTools", "reloadItem", "rebuildItem", "homeItem", "toolsBlock", "ptAns", "ptCmd", "ptResult", "ptSessions", "ptPick", "ptItem", "ptSend", "ptCopy", "ptCopyOld"]) eval(pick(f));
const handler = src.slice(src.indexOf("    if (a === 'pt-open')"), src.indexOf("    if (a === 'reb-ask')"));
const press = new Function("a", "b", "S", "PT", "ptSend", "ptCopy", "render", handler);
function btn(attrs) { return {disabled: !!attrs.disabled, getAttribute: (k) => attrs[k] === undefined ? null : attrs[k], textContent: "Copy"}; }
function click(a, attrs) { press(a, btn(attrs), S, PT, ptSend, ptCopy, render); }
const out = {};
out.closed = toolsBlock();
click("pt-open", {"data-t": "add-roadmap"});
out.addPick = toolsBlock();
// press Add on the project with nothing on: one press, nothing else
out.noPostOnChoose = (click("pt-proj", {"data-t": "add-roadmap", "data-f": meta.projects[1].folder}), S.db.posts.length);
out.sessions = toolsBlock();
click("pt-go", {"data-t": "add-roadmap", "data-f": meta.projects[1].folder, "data-x": "s3"});
const k = Object.keys(S.ans)[0];
out.addPosts = S.db.posts.map((p) => ({key: p.key.replace(/\d+$/, "N"), text: p.rec.text, action: p.rec.action}));
out.working = toolsBlock();
S.ans[k] = Object.assign({}, S.ans[k], {status: "done", outcome: "Sent to the session \"Beta main\" (the project's main session). Say yes there and it sets up the roadmap in Bravo; nothing runs until you do."});
out.sent = toolsBlock();
// not sent: the command and Copy
S.ans[k] = Object.assign({}, S.ans[k], {status: "done", outcome: "Not sent: no Claude session is open in that project. In that project's Claude session, type /assistant:roadmap-setup"});
out.notSent = toolsBlock();
const cp = btn({"data-c": "/assistant:roadmap-setup"});
press("pt-copy", cp, S, PT, ptSend, ptCopy, render);
out.copied = copied.slice();
// the listener is off: nothing is sent yet, the command is offered
S.listening = false; delete S.ans[k]; PT.key["add-roadmap"] = "pt:add-roadmap:1";
S.ans["pt:add-roadmap:1"] = {status: "saved"};
out.off = toolsBlock();
S.listening = true;
// remove: asks first
click("pt-open", {"data-t": "add-roadmap"});      // close the add list
S.db.posts.length = 0;
click("pt-open", {"data-t": "remove-roadmap"});
click("pt-go", {"data-t": "remove-roadmap", "data-f": meta.projects[0].folder});
out.confirm = toolsBlock();
out.postsBeforeYes = S.db.posts.length;
click("pt-no", {});
out.afterNo = [S.db.posts.length, /Turn the roadmap off/.test(toolsBlock())];
click("pt-go", {"data-t": "remove-roadmap", "data-f": meta.projects[0].folder});
click("pt-yes", {"data-t": "remove-roadmap"});
out.removePosts = S.db.posts.map((p) => ({key: p.key.replace(/\d+$/, "N"), text: p.rec.text}));
// the questions file's confirm words
click("pt-open", {"data-t": "remove-roadmap"});
click("pt-open", {"data-t": "remove-questions"});
click("pt-proj", {"data-t": "remove-questions", "data-f": meta.projects[3].folder});
out.sessionsQ = toolsBlock();
click("pt-go", {"data-t": "remove-questions", "data-f": meta.projects[3].folder, "data-x": "uuid-delta-main"});
out.confirmQ = toolsBlock();
click("pt-yes", {"data-t": "remove-questions"});
out.removeQPosts = S.db.posts.slice(-1).map((p) => p.rec.text);
// a project where the tool is already on is not offered Add (the button is disabled, and pressing it posts nothing)
click("pt-no", {}); click("pt-open", {"data-t": "remove-questions"}); S.db.posts.length = 0;
click("pt-open", {"data-t": "add-roadmap"});
click("pt-go", {"data-t": "add-roadmap", "data-f": meta.projects[0].folder, disabled: true});
out.disabledPosts = S.db.posts.length;
out.inTop = /var top = [^\n]*toolsBlock\(\)/.test(src);
console.log(JSON.stringify(out));
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(obj, str):
            f.write(obj)
        else:
            json.dump(obj, f)


def main():
    tmp = tempfile.mkdtemp(prefix="ptools-")
    base = os.path.join(tmp, "Work")
    root = os.path.join(tmp, "Assistant")
    cfg = os.path.join(tmp, "claude")
    log = os.path.join(tmp, "sent.log")
    try:
        for n in ("Alpha", "Bravo", "Charlie", "Delta", "Echo", "Alpha" + os.sep + ".claude" + os.sep + "worktrees" + os.sep + "side"):
            os.makedirs(os.path.join(base, n), exist_ok=True)
        # Alpha: roadmap on, main session recorded by the roadmap. Delta: questions file on, main session recorded. Echo: roadmap on (a
        # second roadmap that must stay as it is).
        write(os.path.join(base, "Alpha", ".claude", "roadmap", "config.json"), {"director_local_id": "local_alpha-main", "writes": "main"})
        write(os.path.join(base, "Alpha", "Roadmap page", "roadmap.json"), {"name": "Alpha"})
        write(os.path.join(base, "Echo", ".claude", "roadmap", "config.json"), {"director_local_id": "local_echo-main"})
        write(os.path.join(base, "Delta", ".claude", "questions", "config.json"), {"on": True, "main_session_id": "uuid-delta-main"})
        write(os.path.join(base, "Delta", "Questions.md"), "# Questions\n\nNo open questions.\n")
        write(os.path.join(root, "Live", "personal", "settings.json"),
              {"page_port": 47900, "roadmaps": [{"folder": os.path.join(base, "Alpha")}, {"folder": os.path.join(base, "Echo")}]})
        write(os.path.join(root, "Live", "personal", "projects.json"), {"projects": [{"name": "Charlie", "folder": os.path.join(base, "Charlie")}]})
        data = os.path.join(tmp, "data")
        shutil.copytree(os.path.join(PKG, "scripts"), os.path.join(data, "scripts"))
        shutil.copytree(os.path.join(PKG, "hooks"), os.path.join(data, "hooks"))
        write(os.path.join(data, "hand-out", "sessions.json"), [{"sessionId": "local_alpha-other", "title": "Alpha older", "startedBy": "local_alpha-main"}])
        fake = os.path.join(tmp, "fake_send.py")
        write(fake, FAKE)
        env = dict(os.environ, ASSISTANT_LIVE_HOME=os.path.join(root, "Live"), CLAUDE_CONFIG_DIR=cfg, ASSISTANT_PLUGIN_DATA=data,
                   ASSISTANT_PRESS_FAKE=f'"{sys.executable}" "{fake}"', FAKE_LOG=log, FAKE_MODE="", PYTHONIOENCODING="utf-8")
        env.pop("CLAUDECODE", None)
        # open sessions, written by the made-up runner itself so their process is alive: made by a small preface
        sess = os.path.join(cfg, "sessions")
        os.makedirs(sess, exist_ok=True)
        pid = os.getpid()                       # this test's own process stands in for each session's process
        rows = [("Alpha older", "Alpha", "s1", "local_alpha-other", "2026-11-19T09:00:00"),
                ("Alpha main", "Alpha", "s2", "local_alpha-main", "2026-11-19T08:00:00"),
                ("Bravo old", "Bravo", "s3", "local_bravo-1", "2026-11-19T07:00:00"),
                ("Bravo latest", "Bravo", "s4", "local_bravo-2", "2026-11-19T10:00:00"),
                ("Delta main", "Delta", "uuid-delta-main", "local_delta-main", "2026-11-19T06:00:00"),
                ("Delta newer", "Delta", "s6", "local_delta-new", "2026-11-19T11:00:00"),
                ("Side work", "Alpha" + os.sep + ".claude" + os.sep + "worktrees" + os.sep + "side", "s7", "local_side", "2026-11-19T11:30:00")]
        for i, (name, folder, sid, local, at) in enumerate(rows):
            write(os.path.join(sess, f"{pid}-{i}.json"), {"name": name, "cwd": os.path.join(base, folder), "sessionId": sid, "hostSessionId": local,
                                                          "pid": pid, "updatedAt": at})
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, root, base, LIVE], capture_output=True, text=True, env=env, timeout=300)
        try:
            o = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            o = {}
            check("the checks ran", (r.stderr or r.stdout).strip()[-2500:], "")

        names = ["Add roadmap to a project", "Add questions file to a project", "Remove roadmap from a project", "Remove questions file from a project"]
        check("listed: the four, each with plain words and its command", [(x[1], x[2]) for x in o.get("listed") or []], [(n, True) for n in names])
        check("each one's command is the plugin's own", [x[3] for x in o.get("listed") or []],
              ["/assistant:roadmap-setup", "/assistant:questions-setup", "/assistant:roadmap-setup", "/assistant:questions-setup"])
        pr = o.get("projects") or {}
        check("projects offered, with whether the roadmap and the questions file are on (a worktree session's folder is not offered)",
              [pr.get("Alpha"), pr.get("Bravo"), pr.get("Charlie"), pr.get("Delta"), pr.get("Echo"), "side" in pr], [[True, False], [False, False], [False, False], [False, True], [True, False], False])
        f = o.get("found") or {}
        check("the sessions offered for a project: all of its open ones, none chosen; top sessions first, a child (started from another session) after, "
              "and the one that keeps the questions file marked",
              [f.get("Alpha"), f.get("Bravo"), f.get("Charlie"), f.get("Delta")],
              [[["Alpha main", False, False], ["Alpha older", True, False]], [["Bravo latest", False, False], ["Bravo old", False, False]], [],
               [["Delta newer", False, False], ["Delta main", False, True]]])

        b = o.get("bravo") or {}
        check("Add roadmap, Bravo: exactly one message, to the session chosen (Bravo old), not the most recently active one", [x["to"] for x in b.get("log") or []], ["Bravo old"])
        msg = ((b.get("log") or [{}])[0]).get("message", "")
        check("the message waits for the person's yes in that session and names the one command",
              ["Do nothing yet" in msg, "yes in this session" in msg, "run /assistant:roadmap-setup" in msg, msg.count("/assistant:") == 1, "If they say no" in msg],
              [True, True, True, True, True])
        check("the page is told which session it went to, and that the person says yes there",
              [("\"Bravo old\"" in (b.get("result") or "")), ("Say yes there" in (b.get("result") or "")), "nothing runs until you do" in (b.get("result") or "")], [True, True, True])
        check("nothing was run or changed in any project by an add", o.get("adds_changed_nothing"), True)
        d = o.get("delta") or {}
        check("Add roadmap, Delta: one message, to the session chosen (Delta newer)", [x["to"] for x in d.get("new") or []], ["Delta newer"])
        a = o.get("alpha") or {}
        check("Add questions file, Alpha: one message, to the session chosen (Alpha older), naming the questions command",
              [[x["to"] for x in a.get("new") or []], "/assistant:questions-setup" in ((a.get("new") or [{}])[0]).get("message", "")], [["Alpha older"], True])
        c = o.get("charlie") or {}
        check("The chosen session is not open: nothing is sent, the answer says Not sent and names the command to type there",
              [c.get("new"), (c.get("result") or "").startswith("Not sent: the session you chose is no longer open in that project"), (c.get("result") or "").endswith("type /assistant:questions-setup")], [[], True, True])
        al = o.get("already") or []
        check("a project that has it on, and one the assistant does not know, are not messaged", [al[2] if len(al) > 2 else None, "already on in Alpha" in (al[0] if al else ""), "not one I know" in (al[1] if len(al) > 1 else "")], [0, True, True])
        u = o.get("undelivered") or {}
        check("a message that cannot be delivered: one try, Not sent, the command is named", [u.get("attempts"), (u.get("result") or "").startswith("Not sent"), (u.get("result") or "").endswith("type /assistant:roadmap-setup")], [1, True, True])

        rr = o.get("remove_roadmap") or {}
        check("Remove roadmap, Alpha: it is off; the roadmap's own folder is deleted; the page's record stays",
              [rr.get("now"), rr.get("gone"), "Roadmap page/roadmap.json" in (rr.get("gone") or [])],
              [False, ["Work/Alpha/.claude/roadmap/config.json"], False])
        check("Remove roadmap: deleted outright, nothing new is made (no saved copy, no To Delete folder), and the assistant's own list loses only that project",
              [rr.get("new"), rr.get("listed") == [os.path.join(base, "Echo")]], [[], True])
        check("Remove roadmap changes nothing else: only the settings file changed, no other project was touched, no message was sent",
              [rr.get("changed"), rr.get("sent")], [["Assistant/Live/personal/settings.json"], 0])
        rq = o.get("remove_questions") or {}
        ws = o.get("remove_wrong_session") or []
        check("Remove questions file with a session that has none: nothing is changed", [("has no questions file" in (ws[0] if ws else "")), ws[1] if len(ws) > 1 else None, ws[2] if len(ws) > 2 else None], [True, True, True])
        check("Remove questions file, Delta, the session that keeps it: it is off; its file stays as it is; only that project's own setting changed; no message was sent",
              [rq.get("on"), rq.get("changed"), rq.get("new"), rq.get("gone"), rq.get("sent")],
              [False, ["Work/Delta/.claude/questions/config.json"], [], [], 0])
        rt = o.get("remove_twice") or []
        check("Remove again, where it is already off: says so and changes nothing", [("already off" in rt[0]) if rt else None, ("no questions file" in rt[1]) if len(rt) > 1 else None, rt[2] if len(rt) > 2 else None], [True, True, True])

        # the page, under node
        folders = [os.path.join(base, n) for n in ("Alpha", "Bravo", "Charlie", "Delta")]
        meta = {"tools": [], "ptools": [{"id": "add-roadmap", "name": names[0], "words": "w-add-roadmap", "tool": "roadmap", "op": "add", "command": "/assistant:roadmap-setup"},
                          {"id": "add-questions", "name": names[1], "words": "w-add-questions", "tool": "questions", "op": "add", "command": "/assistant:questions-setup"},
                          {"id": "remove-roadmap", "name": names[2], "words": "w-remove-roadmap", "tool": "roadmap", "op": "remove", "command": "/assistant:roadmap-setup"},
                          {"id": "remove-questions", "name": names[3], "words": "w-remove-questions", "tool": "questions", "op": "remove", "command": "/assistant:questions-setup"}],
                "projects": [{"folder": "C:\\Work\\Alpha", "name": "Alpha", "roadmap": True, "questions": False, "sessions": []},
                             {"folder": "C:\\Work\\Bravo", "name": "Bravo", "roadmap": False, "questions": False, "sessions": [
                                 {"id": "s4", "name": "Bravo latest", "at": "2026-11-19T10:00:00", "child": False, "has": False},
                                 {"id": "s3", "name": "Bravo old", "at": "2026-11-19T07:00:00", "child": False, "has": False},
                                 {"id": "s8", "name": "Child one", "at": "2026-11-19T11:00:00", "child": True, "has": False}]},
                             {"folder": "C:\\Work\\Charlie", "name": "Charlie", "roadmap": False, "questions": False},
                             {"folder": "C:\\Work\\Delta", "name": "Delta", "roadmap": False, "questions": True, "sessions": [
                                 {"id": "s6", "name": "Delta newer", "at": "2026-11-19T11:00:00", "child": False, "has": False},
                                 {"id": "uuid-delta-main", "name": "Delta main", "at": "2026-11-19T06:00:00", "child": False, "has": True}]}]}
        r = subprocess.run(["node", "-e", NODE, PAGE, json.dumps(meta)], capture_output=True, text=True, timeout=60)
        try:
            p = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            p = {}
            check("the page's code ran under node", r.stderr[-1200:], "")
        closed = p.get("closed", "")
        check("every Tools entry shows its name and its plain words, and the Tools part is in Settings",
              [all(f"<b>{n}</b>" in closed and f"w-{i}" in closed for n, i in zip(names, ("add-roadmap", "add-questions", "remove-roadmap", "remove-questions"))), p.get("inTop")], [True, True])
        pick = p.get("addPick", "")
        check("pressing Add roadmap lists the projects with on or off, and Already on where the roadmap is on",
              [pick.count("class=\"pt-row\""), "Roadmap: on &middot; Questions file: off" in pick, pick.count("Already on"), pick.count(">Choose</button>")], [4, True, 1, 3])
        ss = p.get("sessions", "")
        check("choosing a project posts nothing and lists its sessions with when last active and whether started from another session, under the guide line, nothing chosen for the person",
              [p.get("noPostOnChoose"), "Pick the project's top session, the one that oversees the work. A roadmap follows the whole project, including the sessions started from it." in ss.replace("&#39;", "'"),
               ss.count(">Add</button>"), "Last active 2026-11-19" in ss or "Last active 10:00" in ss or "Last active" in ss, "started from another session" in ss, ss.index("Bravo latest") < ss.index("Child one")],
              [0, True, 3, True, True, True])
        check("pressing Add on a project posts exactly one press, with that project, and nothing else",
              p.get("addPosts"), [{"key": "pt:add-roadmap:N", "text": json.dumps({"folder": "C:\\Work\\Bravo", "session": "s3"}, separators=(",", ":")), "action": "answer"}])
        check("while it waits the page says it is asking that project's session", "Asking that project&#39;s Claude session" in p.get("working", "") or "Asking that project's Claude session" in p.get("working", ""), True)
        check("the page shows which session it went to, and that the person says yes there", ["Sent to the session &quot;Beta main&quot;" in p.get("sent", ""), "Say yes there" in p.get("sent", "")], [True, True])
        ns = p.get("notSent", "")
        check("not sent: the page says so plainly and shows the exact command with a Copy button",
              ["Not sent: no Claude session is open in that project." in ns, "<code>/assistant:roadmap-setup</code>" in ns, "data-s=\"pt-copy\"" in ns, "type /assistant" not in ns.split("<code>")[0]], [True, True, True, True])
        check("the Copy button copies exactly the command", p.get("copied"), ["/assistant:roadmap-setup"])
        check("if the listener is off, the page says nothing was sent and offers the command", ["nothing has been sent yet" in p.get("off", ""), "pt-copy" in p.get("off", "")], [True, True])
        check("Remove: pressing a project asks first, in the owner's words, and sends nothing yet",
              ["Turn the roadmap off in Alpha? Its page stays as a record." in p.get("confirm", ""), p.get("postsBeforeYes")], [True, 0])
        check("Remove: No sends nothing and closes the question", p.get("afterNo"), [0, False])
        check("Remove: Yes sends exactly one press", p.get("removePosts"), [{"key": "pt:remove-roadmap:N", "text": json.dumps({"folder": "C:\\Work\\Alpha"}, separators=(",", ":"))}])
        qs = p.get("sessionsQ", "")
        check("Remove questions file: the sessions are listed with the one that keeps it marked and the others cannot be removed; the guide line is the questions one",
              ["Pick the session you're talking with. A questions file keeps that one session's questions." in qs.replace("&#39;", "'"), "has the questions file" in qs, qs.count(">None here</button>"), qs.count(">Remove</button>")], [True, True, 1, 1])
        check("the questions file's confirm says the file stays, and Yes sends the project and the chosen session",
              ["Turn the questions file off in Delta? Its file stays as it is." in p.get("confirmQ", ""), p.get("removeQPosts")],
              [True, [json.dumps({"folder": "C:\\Work\\Delta", "session": "uuid-delta-main"}, separators=(",", ":"))]])
        check("a disabled button sends nothing", p.get("disabledPosts"), 0)
        src = open(os.path.join(PKG, "engine", "System", "live_page", "publish.py"), encoding="utf-8").read()
        check("the page's data carries the four tools and the projects", ["meta[\"ptools\"] = project_tools.listed()" in src, "meta[\"projects\"] = project_tools.projects()" in src], [True, True])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
