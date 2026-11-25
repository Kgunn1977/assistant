r"""Acceptance (quick): Send sends exactly the words on screen. The assistant drafts an email, is told to rewrite it shorter, the
owner edits the rewrite a little and presses Send: with a stub sender (nothing leaves), the edited words are what go; and on the
page, a press made while the draft changed under it (the assistant wrote it again) sends nothing and says so. On a scratch home
laid down from this plugin.

    python tests\send_shown_acceptance.py
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
results = []

LONG = ("Hi Dana,\n\nHere are all the prices I have for 40 cases of blue painter's tape, with the terms each vendor "
        "gave and when each quote runs out, so you can pick.\n\n" + "A long paragraph about each vendor. " * 12 + "\n\nThanks,\nPat")
SHORT = "40 cases of blue painter's tape, per case before tax:\n\n- Vendor A: $31.10/case\n- Vendor B: $32.45/case\n\nThanks,\nPat"
EDITED = SHORT.replace("Vendor B: $32.45/case", "Vendor B: $32.45/case, in stock") + " — café"

INSIDE = r'''
import datetime as dt, json, os, sys
sys.path.insert(0, sys.argv[1])
import common, send
A = "pat@work.example"
send.switched_on = lambda: True
send.accounts = lambda: [A]
got = []
def stub(m):
    got.append(m["body"])
    return "stub-sent"
EDITED = json.loads(os.environ["SHOWN_DATA"])
m = {"account": A, "to": ["lee@acme.example"], "cc": [], "bcc": [], "subject": "Painter's tape prices", "body": EDITED,
     "type": "new", "source": None, "files": [], "attach": []}
m["shown"] = {"account": A, "to": m["to"], "cc": [], "bcc": [], "type": "new", "attach": []}
rec = {"id": "L2", "action": "answer", "device": "Computer, Chrome", "at": common.now().isoformat(timespec="seconds"),
       "text": json.dumps({"send_email": m})}
r = send.send_owner_email(rec, None, handoff=stub)
print(json.dumps({"edited": [r["sent"], got[-1] == EDITED if got else None, len(got)]}))
'''

NODE = r'''
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8");
const pick = (name) => { const i = src.indexOf("  function " + name + "("); if (i < 0) throw new Error("no " + name);
  let d = 0, j = src.indexOf("{", i); for (; j < src.length; j++) { if (src[j] === "{") d++; else if (src[j] === "}" && --d === 0) break; } return src.slice(i, j + 1); };
const [LONG, SHORT, EDITED] = JSON.parse(process.env.SHOWN_DATA);
let S = {err: {}}, body = "";
const wPayload = (k, it) => ({body: body, shown: {}});
const wText = (p) => JSON.stringify({send_email: p});
eval(pick("wSeen") + pick("wPressText"));
const out = {};
body = LONG; wSeen("L1", body);                  // the first draft on its card
body = SHORT; wSeen("L2", body);                 // the rewrite on a new card, shown
body = EDITED; wSeen("L2", EDITED);              // a small edit typed into the rewrite
const t = wPressText("L2", {});
out.edited = t && JSON.parse(t).send_email.body === EDITED;
body = SHORT;                                    // the assistant writes the rewrite again just before Send: the edit would be dropped
out.changed = wPressText("L2", {}) === null && /changed just now/.test(S.err.L2 || "");
console.log(JSON.stringify(out));
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="sendshown-")
    data, root = os.path.join(tmp, "data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("ac_shown", os.path.join(PKG, "hooks", "assistant_copy.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    try:
        page = os.path.join(PKG, "engine", "System", "live_page", "page.html")
        r = subprocess.run(["node", "-e", NODE, page], capture_output=True, text=True, encoding="utf-8",
                           env=dict(os.environ, SHOWN_DATA=json.dumps([LONG, SHORT, EDITED])))
        o = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stderr[-800:]}
        check("the page: the edited rewrite is what a Send press carries", o.get("edited"), True)
        check("the page: a Send press made while the draft changed under it sends nothing and says so", o.get("changed"), True)
        m.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47944", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True,
                           env=dict(env, SHOWN_DATA=json.dumps(EDITED)), cwd=live, timeout=300)
        e = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stderr[-1500:]}
        check("the computer: the edited words, exactly, are handed to the sender", e.get("edited"), [True, True, 1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
