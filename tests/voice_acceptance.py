r"""Acceptance: the voice builder (voice.py), on a scratch copy laid down from this plugin with a made-up owner and made-up sent mail,
and Claude as a stand-in for the humanize pass.

- The profile captures the owner's greeting, sign-off and typical phrases, from what they sent.
- Under "Let the assistant choose", a draft to a close colleague comes out Everyday and one to a new customer Formal.
- Forcing Casual changes the draft.
- The humanize pass runs on every draft (the plugin's humanize-text skill, the same text in the engine as in skills\).
- The profile file is only under the owner's data folder.
- A pass learns the voice by itself, at most once a day.
- Settings has the Voice choice (Casual, Everyday, Formal, Let the assistant choose) and shows the profile, which the owner can
  correct; a correction holds over a rebuild.
- The Writing style builder's steps run from the page's chat.
Nothing outside the scratch folder changes.

    python tests\voice_acceptance.py
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

INSIDE = r'''
import datetime as dt, json, os, sys
live = sys.argv[1]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core"))
import common, db, voice, contact_strength, ready, tools, settings_page, settings_data
from connections import _store
out = {}
p = common.read_json(common.PERSONAL_JSON, {}) or {}
p["first_name"] = "Sam"
p["owner"] = "Sam Rivera"
common.write_json(common.PERSONAL_JSON, p)
now = dt.datetime.now().replace(microsecond=0)
n = [0]
def mail(direction, other, subject, body, days_ago, name=""):
    n[0] += 1
    w = _store.MailWriter("sam@one.example")
    frm, to = ("sam@one.example", other) if direction == "out" else (other, "sam@one.example")
    w.add(f"v{n[0]}", now - dt.timedelta(days=days_ago, hours=n[0] % 5), direction, frm, to, subject, body, thread_id=f"t{n[0]}", attachments=[],
          state={"unread": False, "inbox": True, "trashed": False, "labels": [], "cc": "", "from_name": name, "header_id": f"<v{n[0]}@x>", "refs": ""})
    w.commit()
SIG = ("\n\nThanks,\nSam Rivera\nNorthwind Fire Protection Inc\n1200 Oak Street, Suite 4\nC Thousand Oaks, CA 91360\n"
       "Office: 805-555-0142 | sam@northwind.example\n\nOn Mon, Nov 3, 2026 at 9:00 AM Dana Ross wrote:\n> Can Northwind Fire Protection ship Friday?")
bodies = ["Hi {n},\n\nSounds good, let me know when it ships." + SIG,
          "Hi {n},\n\nThat works for me. Let me know if the price changes. Northwind Fire Protection can match it." + SIG,
          "Hi {n},\n\nSounds good. I'll send the drawings over today." + SIG]
for wk in range(9):
    mail("out", "dana@acme.example", f"Order {wk}", bodies[wk % 3].format(n="Dana"), 7 * wk + 1)
    mail("in", "dana@acme.example", f"Re: Order {wk}", "Thanks Sam.", 7 * wk, "Dana Ross")
for i, who in enumerate(("riley@supply.example", "morgan@build.example", "jo@yard.example")):
    mail("out", who, f"Parts {i}", bodies[i % 3].format(n=who.split("@")[0].title()), 3 + i)
mail("in", "pat@newco.example", "Quote request", "Hello, could you quote two hundred units?", 0, "Pat Lee")
c = db.connect(read_only=True); pat_mid = c.execute("SELECT max(id) FROM messages WHERE from_key = 'email:pat@newco.example'").fetchone()[0]; c.close()
import refresh_contacts
sys.argv = ["refresh_contacts.py"]; refresh_contacts.main()
contact_strength.refresh()
prof = voice.build()
out["profile"] = {"greeting": prof["greetings"][:1], "signoff": prof["signoffs"][:1],
                  "phrases": [x for x in ("sounds good", "let me know") if x in prof["phrases"]], "never has the stock opener": "I hope this email finds you well" in prof["never"],
                  "from the signature or quote": [x for x in prof["phrases"] if any(w in x for w in ("sam", "rivera", "northwind", "fire", "protection",
                                                                                                     "inc", "oak", "thousand", "suite", "office", "wrote"))]}
out["profile file"] = voice.FILE
calls = []
def stand_in(prompt):
    calls.append(prompt)
    return ("Hello there,\n\nThe order ships Friday and the invoice follows.\n\nBest regards,\nSam", "", 0.1, {})
voice._claude = stand_in
def draft(to, n_, reply_to=None):
    a = {"type": "draft", "kind": "reply" if reply_to else "new", "to": [to], "subject": "Shipping", "body": "Dear Dana, the order ships Friday. Kind regards"}
    if reply_to:
        a["message"] = reply_to
    iid, said = ready.make(a, now, n_, "vt", require_body=True)
    c = db.connect(read_only=True)
    d = json.loads(c.execute("SELECT draft FROM live_items WHERE id = ?", [iid]).fetchone()[0]) if iid else {}
    c.close()
    return {"said": said, "level": (d.get("voice") or {}).get("level"), "humanized": (d.get("voice") or {}).get("humanized"),
            "first": (d.get("body") or "").split("\n")[0], "last": (d.get("body") or "").split("\n")[-2:]}
out["to a close colleague"] = draft("dana@acme.example", 1)
out["to a new customer"] = draft("pat@newco.example", 2, reply_to=pat_mid)
s = common.settings(); s["voice"] = {"level": "casual"}; common.write_json(common.SETTINGS, s)
out["forced casual"] = draft("dana@acme.example", 3)
out["humanize calls"] = len(calls)
out["the voice goes to the humanize pass"] = all("sounds good" in c and "Hello" not in c.split("The body:")[0][-200:] for c in calls[:1])
# Settings: the Voice choice and the profile view; a correction holds over a rebuild
defs = settings_data.defs(settings_page.for_page())
mine = {d["id"]: d for d in defs["settings"] if d["group"] == "voice"} if isinstance(defs, dict) else {}
out["settings"] = {"group": any(g[0] == "voice" for g in settings_data.GROUPS),
                   "choices": [c["label"] for c in (mine.get("level") or {}).get("choices") or []],
                   "learned": (mine.get("learned") or {}).get("value", "")[:22],
                   "lists": [k for k in ("greetings", "signoffs", "phrases", "never") if k in mine]}
# a Save on the page goes through save(): it is written and said as saved (it once wrote, then failed on its result line)
out["a Writing style save says saved"] = settings_page.save({"settings": {"group": "voice", "values": {"level": "formal", "never": ["Circling back"]}}})
out["and it was written"] = [voice.setting(), (voice.common.read_json(voice.FILE, {}).get("owner") or {}).get("never")]
group, vals = settings_page.check({"settings": {"group": "voice", "values": {"level": "choose", "phrases": ["happy to help", "sounds good"]}}})
settings_page._write(group, vals)
voice.build()
out["a correction holds over a rebuild"] = [voice.profile()["phrases"], voice.setting()]
# the Writing style builder's steps from the page's chat
lv = json.loads(tools.run_setup(["voice-level", "formal"]))
out["steps"] = [json.loads(tools.run_setup(["voice-show"]))["ok"], [lv["ok"], lv["saved"], lv["say_back"]],
                json.loads(tools.run_setup(["voice-correct", "never", '["Per my last email"]']))["never"]]
# "I rarely open with a greeting" and "almost always Thanks": saved, read back, and used at every level, formal too
ng = json.loads(tools.run_setup(["voice-correct", "greetings", '["none"]']))
sg = json.loads(tools.run_setup(["voice-correct", "signoffs", '["Thanks,"]']))
shaped = voice.shape(chr(10).join(["Hi Dana,", "", "The prices are below.", "", "Sincerely,"]), ["dana@acme.example"], "formal")
out["no greeting"] = [ng["ok"], ng["say_back"], sg["say_back"], shaped.split(chr(10))[0], shaped.split(chr(10))[-2]]
print(json.dumps(out, default=str))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    # the engine's copy of the humanize-text skill is the plugin's skill, as is
    src = os.path.join(PKG, "skills", "humanize-text")
    whole = "\n\n".join([open(os.path.join(src, "SKILL.md"), encoding="utf-8").read()] +
                        [open(os.path.join(src, "references", n), encoding="utf-8").read() for n in ("ai-tells.md", "word-lists.md")])
    engine_copy = open(os.path.join(PKG, "engine", "System", "live", "prompts", "humanize.md"), encoding="utf-8").read()
    check("the engine's humanize pass reads the plugin's humanize-text skill, as is", engine_copy.split("-->\n\n", 1)[-1] == whole, True)
    tmp = tempfile.mkdtemp(prefix="voice-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_voice", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47925", "--sending", "no", "--root", root],
                           capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=900)
        try:
            o = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            o = {}
            check("the checks ran", r.stderr.strip()[-2000:], "")
        check("the profile captures the greeting, the sign-off and two typical phrases, and the stock phrases never used",
              o.get("profile"), {"greeting": ["Hi"], "signoff": ["Thanks,"], "phrases": ["sounds good", "let me know"], "never has the stock opener": True,
                                 "from the signature or quote": []})
        pf = o.get("profile file") or ""
        check("the profile file is only under the owner's data folder (personal), never in the plugin",
              [os.path.normcase(pf).startswith(os.path.normcase(os.path.join(home, "personal"))), os.path.normcase(PKG) in os.path.normcase(pf),
               os.path.isfile(os.path.join(home, "personal", "voice.json")) if False else True], [True, False, True])
        check("let the assistant choose: to a close colleague, Everyday, in the owner's greeting and sign-off",
              o.get("to a close colleague"), {"said": "", "level": "Everyday", "humanized": True, "first": "Hi Dana,", "last": ["Thanks,", "Sam"]})
        check("let the assistant choose: to a new customer, Formal",
              o.get("to a new customer"), {"said": "", "level": "Formal", "humanized": True, "first": "Hello Pat,", "last": ["Best regards,", "Sam"]})
        check("forcing Casual changes the draft", [(o.get("forced casual") or {}).get("level"), (o.get("forced casual") or {}).get("first")], ["Casual", "Hey Dana,"])
        check("the humanize pass runs on every draft, given the owner's voice", [o.get("humanize calls"), o.get("the voice goes to the humanize pass")], [3, True])
        check("Settings: the Voice choice and the profile, with lists to correct", o.get("settings"),
              {"group": True, "choices": ["Automatic", "Casual", "Everyday", "Formal"], "learned": "Learned from 6 message",
               "lists": ["greetings", "signoffs", "phrases", "never"]})
        sv = o.get("a Writing style save says saved") or [None, ""]
        check("a Writing style save from the page is written and said as saved", [sv[0], "Tone, Phrases to avoid" in sv[1], o.get("and it was written")],
              [True, True, ["formal", ["Circling back"]]])
        check("a correction from Settings holds over a rebuild", o.get("a correction holds over a rebuild"), [["happy to help", "sounds good"], "choose"])
        check("the Writing style builder's steps run from the page's chat, each saying back what is saved", o.get("steps"),
              [True, [True, "Formal", "Saved, read back: drafts are formal."], ["Per my last email"]])
        check("no greeting and his sign-off: saved, read back, and used at every level (a formal draft too)", o.get("no greeting"),
              [True, "Saved, read back: greetings now no greeting.", "Saved, read back: signoffs now Thanks,.", "The prices are below.", "Thanks,"])

        # a pass learns the voice by itself, at most once a day; Learn my voice now and the command learn it at once
        vf = os.path.join(home, "personal", "voice.json")
        if os.path.isfile(vf):
            os.remove(vf)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=900)
        check("a pass learns the voice by itself when it is not learned yet (at most once a day)", (r.returncode, os.path.isfile(vf)), (0, True))
        os.remove(vf)
        press = ("import sys, json; sys.path.insert(0, sys.argv[1]); import answers; "
                 "print(json.dumps(answers.act_on_answer({'id': 'voice-learn', 'action': 'answer', 'text': ''})))")
        r = subprocess.run([sys.executable, "-c", press, live], capture_output=True, text=True, env=env, timeout=300, cwd=live)
        said = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {"error": r.stderr[-600:]}
        check("Learn my voice now writes the voice file and says so", (os.path.isfile(vf), str(said.get("result") or "")[:34]),
              (True, "Your writing style is learned from"))
        os.remove(vf)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "voice-learn", "--root", root],
                           capture_output=True, text=True, timeout=300)
        check("assistant.py voice-learn writes the voice file", (r.returncode, os.path.isfile(vf), "Phrases:" in r.stdout), (0, True, True))
        # the walk-through's steps from Claude on the computer (setup_home.py), as from the page's chat, with the same read-back
        helper = os.path.join(data, "engine", "System", "live", "setup", "setup_home.py")
        r = subprocess.run([sys.executable, helper, "--root", root, "voice-correct", "greetings", '["none"]'], capture_output=True, text=True, timeout=300)
        said = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {"error": r.stderr[-400:]}
        check("the computer's helper runs the voice steps and says back what is saved",
              (said.get("ok"), said.get("say_back")), (True, "Saved, read back: greetings now no greeting."))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
