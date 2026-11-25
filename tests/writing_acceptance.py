r"""Acceptance (quick): phase 3 of the judgment rebuild, "Writing". On a scratch copy laid down from this plugin, with a made-up
owner, made-up people and 20 made-up sent emails and texts; the humanize run, the mail service and the phone are stood in for
(no Claude run, nothing sent).

- His voice from what he sent: email and texts come out as distinct styles, and a person he writes to differently (Jo) has a
  style of their own; Settings shows both, as lines he can change. The pass learns it again at most once a day.
- Drafts use it: an email draft to Jo opens and closes the way he writes to Jo; a text draft is shaped to how he texts.
- Learning from edits: a page Send of a draft he rewrote writes a rule book row (Reply drafts) saying what changed, and Jo's
  style and the email length move; an unchanged send is a full match; a text he rewrote counts too, from the page or his phone.
- The replies score shows in Settings beside the learning levels, and each row reads in plain words in the rule book.

    python tests\writing_acceptance.py
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
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core")); os.chdir(live)
import common, db, items, voice, ready, answers, send, texts, textlink, writing, rule_book, settings_page, settings_data
out = {}
now = dt.datetime.now().replace(microsecond=0)
db.init_schema(); items.ensure()
common.write_json(common.ITEMS_JSON, {"items": []})          # the page's snapshot a pass would have written
p = common.read_json(common.PERSONAL_JSON, {}) or {}
p.update(first_name="Sam", owner="Sam Rivera")
common.write_json(common.PERSONAL_JSON, p)
con = db.connect()
for pid, key, name in ((901, "email:dana@acme.example", "Dana Ross"), (902, "email:lee@build.example", "Lee Moss"),
                       (903, "email:jo@yard.example", "Jo Park"), (904, "phone:5550001111", "Riley Fox"), (905, "phone:5550002222", "Kim Vale")):
    con.execute("INSERT INTO contacts (key, person_id, name) VALUES (?, ?, ?)", (key, pid, name))
n = [30000]
def sent(channel, to, subject, body, days):
    n[0] += 1
    con.execute("INSERT INTO messages (id, channel, account, thread_id, ts, direction, from_key, to_keys, subject, body, ingested_at)"
                " VALUES (?, ?, ?, ?, ?, 'out', ?, ?, ?, ?, ?)",
                (n[0], channel, "sam@one.example" if channel == "email" else "sms", f"t-{to}", now - dt.timedelta(days=days, hours=n[0] % 7),
                 "email:sam@one.example" if channel == "email" else None, to, subject, body, now))
office = ["The parts for the north job are ready at the counter. I will have the invoice to you by Friday afternoon.",
          "The inspection moved to Tuesday at nine. Please make sure the riser room is open and the valves are tagged.",
          "We are short two heads on the order. I asked the supplier to ship them tomorrow and will confirm once they land.",
          "The drawings are attached with the changes we talked about. Let me know if the layout works for your crew."]
for i in range(4):
    sent("email", "dana@acme.example", f"North job {i}", f"Hi Dana,\n\n{office[i]}\n\nThanks,\nSam", 2 + i)
    sent("email", "lee@build.example", f"Site {i}", f"Hi Lee,\n\n{office[(i + 1) % 4]}\n\nThanks,\nSam", 3 + i)
    sent("email", "jo@yard.example", f"Yard {i}", f"Hey Jo,\n\n{['all set', 'see you then', 'grab them whenever', 'works for me'][i]}\n\nCheers,\nSam", 4 + i)
for i, t in enumerate(("on my way, there in 10", "yep that works", "can you grab milk", "running late sorry")):
    sent("sms", "phone:5550001111", None, t, 1 + i)
    sent("sms", "phone:5550002222", None, t.replace("10", "15"), 2 + i)
con.close()
out["made-up sent messages"] = n[0] - 30000

prof = voice.build(now)
st = prof.get("styles") or {}
out["1. email and texts: distinct styles"] = [
    {k: (st.get("email") or {}).get(k) for k in ("level", "greeting", "signoff")},
    {k: (st.get("text") or {}).get(k) for k in ("level", "greeting", "signoff", "lowercase", "end_mark")}]
out["1. Jo has a style of her own"] = [(x["addr"], x["name"], x["level"], x["greeting"], x["signoff"]) for x in prof.get("people") or []]
vo = {d["id"]: d for d in settings_data.defs(settings_page.for_page())["settings"] if d["group"] == "voice"}
out["1. Settings shows them as lines to change"] = [[l.split(":")[0] for l in vo["styles"]["value"]], [l.split(",")[0] for l in vo["people"]["value"]],
                                                    vo["styles"]["control"], vo["people"]["control"]]
out["1. the pass learns it at most once a day"] = [voice.refresh(now), voice.refresh(now + dt.timedelta(hours=25))]

voice._claude = lambda prompt: ("The parts are in at the counter. Pick them up when you can.", "", 0.1, {})
def draft(to, n_, subject):
    iid, said = ready.make({"type": "draft", "kind": "new", "to": [to], "subject": subject, "body": "The parts are in."}, now, n_, "wt")
    item = items.card_for(iid)
    answers._patch_snapshot([item])
    return item
jo = draft("jo@yard.example", 1, "Parts")
out["2. an email draft to Jo is in how he writes to Jo"] = [jo["draft"]["body"].split("\n")[0], jo["draft"]["body"].split("\n")[-2:],
                                                            jo["draft"]["voice"].get("style")]
texts.draft(to="5550003333", text="Can you bring the ladder tomorrow.", why="made-up")
out["2. a text draft is shaped to how he texts"] = [d["text"] for d in texts._drafts()]

s = common.settings(); s["owner_send"] = {"on": True}; common.write_json(common.SETTINGS, s)
send.accounts = lambda: ["sam@one.example"]
send._handoff = lambda m: "stand-in: nothing sent"
def press(item, body):
    d = item["draft"]
    m = {"account": "sam@one.example", "to": d["to"], "cc": [], "bcc": [], "subject": d["subject"], "body": body, "type": "new",
         "source": None, "files": [], "attach": []}
    m["shown"] = {"account": m["account"], "to": m["to"], "cc": [], "bcc": [], "type": "new", "attach": []}
    return answers._owner_send({"id": item["id"], "action": "answer", "device": "Computer, Chrome",
                                "at": common.now().isoformat(timespec="seconds"), "text": json.dumps({"send_email": m})})
before = [l for l in voice.people_lines() if "jo@yard" in l] + [l for l in voice.style_lines() if l.startswith("Email")]
r = press(jo, "Jo - parts are in, grab them whenever.\n\nSam")
row = next((x for x in rule_book.rows(section="replies") if x.get("message") == f"draft:{jo['id']}"), {})
after = [l for l in voice.people_lines() if "jo@yard" in l] + [l for l in voice.style_lines() if l.startswith("Email")]
out["3. the edited send went (stood in) and wrote a row with the change"] = [
    r.get("sent"), row.get("section"), (row.get("draft_edit") or {}).get("outcome"), (row.get("draft_edit") or {}).get("changes", [])[:2],
    row.get("pick_outcome")]
out["3. the profile moved"] = [before != after, "no greeting" in after[0], "no sign-off" in after[0], before[1] != after[1]]
lee = draft("lee@build.example", 2, "Counter")
r2 = press(lee, lee["draft"]["body"])
row2 = next((x for x in rule_book.rows(section="replies") if x.get("message") == f"draft:{lee['id']}"), {})
out["3. an unchanged send is a full match"] = [r2.get("sent"), (row2.get("draft_edit") or {}).get("outcome"), (row2.get("draft_edit") or {}).get("kept"),
                                               row2.get("pick_outcome")]
textlink.signed_in = lambda st=None: True
textlink.kick = lambda: None
q = texts.queue_send("", "ok bring the ladder tmrw", to="5550003333")
out["3. a text sent from the page against my draft counts"] = [q.get("ok"), sum(1 for x in rule_book.rows(section="replies")
                                                                                 if (x.get("draft_edit") or {}).get("channel") == "text")]

sc = writing.score()
lv = {d["id"]: d for d in settings_data.defs(settings_page.for_page())["settings"] if d["group"] == "learning"}
out["4. the replies score in Settings beside the learning levels"] = [sc["drafts"], sc["unchanged"], 0 < (sc["kept"] or 0) < 100,
    lv["learn_replies"]["help"].startswith("Not enough of your answers yet. You kept "), "went out unchanged" in lv["learn_replies"]["help"],
    "You kept" in lv["learn_mailings"]["help"]]
rb = settings_data.rule_book()
words = [x["you"] for sct in rb["sections"] if sct["id"] == "replies" for x in sct["rows"] if x["message"].startswith("draft:")]
out["4. the rule book reads them in plain words"] = sorted(w.split(",")[0].split(".")[0] for w in words)
print(json.dumps(out, default=str))
'''

WANT = {
    "made-up sent messages": 20,
    "1. email and texts: distinct styles": [{"level": "everyday", "greeting": "Hi", "signoff": "Thanks,"},
                                            {"level": "casual", "greeting": "(no greeting)", "signoff": "(no sign-off)",
                                             "lowercase": True, "end_mark": False}],
    "1. Jo has a style of her own": [["jo@yard.example", "Jo Park", "casual", "Hey", "Cheers,"]],
    "1. Settings shows them as lines to change": [["Email", "Texts"], ["Jo Park <jo@yard.example>"], "list", "list"],
    "1. the pass learns it at most once a day": [False, True],
    "2. an email draft to Jo is in how he writes to Jo": ["Hey Jo,", ["Cheers,", "Sam"], "person"],
    "2. a text draft is shaped to how he texts": ["can you bring the ladder tomorrow"],
    "3. the edited send went (stood in) and wrote a row with the change": [
        True, "replies", "rewritten", ['You took out the greeting "Hey".', 'You took out the sign-off "Cheers,".'], "differed"],
    "3. the profile moved": [True, True, True, True],
    "3. an unchanged send is a full match": [True, "unchanged", 1.0, "matched"],
    "3. a text sent from the page against my draft counts": [True, 1],
    "4. the replies score in Settings beside the learning levels": [3, 1, True, True, True, False],
    "4. the rule book reads them in plain words": ["You rewrote my draft before sending it", "You rewrote my draft before sending it",
                                                   "You sent my draft unchanged"],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="writing-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    env.pop("ASSISTANT_REPLAY", None)
    spec = importlib.util.spec_from_file_location("ac_writing", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47941", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=600)
        try:
            o = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            o = {}
            check("the checks ran", (r.stderr or r.stdout)[-2500:], "")
        for name, want in WANT.items():
            check(name, o.get(name), want)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
