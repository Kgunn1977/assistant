r"""Acceptance: the contacts recount and learning the owner's voice never keep the database from the page, on a mailbox the
size of a real one; and an update's check pass leaves both out. On a scratch copy laid down from this plugin, with made-up
mail (thousands of messages, made-up people). Nothing outside the scratch folder changes.

1. With 6,000 messages (a fifth of them sent), while the recount and the voice build run in one process, another process
   reads the database the way the page does, over and over: every read answers in under 0.5 s, and no connection the
   recount or the build opens is held longer than 2 s.
2. The recount still counts right (a made-up frequent contact), and the voice is still learned.
3. A pass started the way an update's check starts it (quick) does neither; a regular pass does both.

    python tests\pass_holds_acceptance.py
"""
import importlib.util
import json
import os
import re
import shutil
import _cleanup  # noqa: E402  the scratch folder goes when the test ends
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
results = []

SEED = r'''
import datetime as dt, random, sys, os
live = sys.argv[1]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core"))
import db
from connections import _store
random.seed(7)
now = dt.datetime.now().replace(microsecond=0)
ME = "me@one.example"
people = [f"person{i}@firm{i % 40}.example" for i in range(400)]
w = _store.MailWriter(ME)
for i in range(6000):
    other = "dana@acme.example" if i % 50 in (0, 1) else random.choice(people)
    out = i % 5 == 0
    days = random.randint(0, 360)
    body = ("Hi there,\n\nThanks for the update on the " + "".join(chr(97 + int(d)) for d in str(i)) + " order. I'll check the numbers and get back to you by Friday.\n\nThanks,\nMe"
            if out else "Hello,\n\nHere is the latest on the job. " + "Details follow. " * 40 +
            ("\n\nTo unsubscribe click here." if i % 7 == 0 else ""))
    w.add(f"s{i}", now - dt.timedelta(days=days, minutes=i % 600), "out" if out else "in", ME if out else other, other if out else ME,
          f"Order {i}", body, thread_id=f"t{i // 2}", attachments=[],
          state={"unread": False, "inbox": True, "trashed": False, "labels": [], "cc": "", "from_name": "", "header_id": f"<s{i}@x>", "refs": ""})
w.commit()
import refresh_contacts
sys.argv = ["refresh_contacts.py"]; refresh_contacts.main()
c = db.connect(read_only=True); print("messages", c.execute("SELECT count(*) FROM messages").fetchone()[0]); c.close()
'''

WORK = r'''
import json, sys, os, time
live = sys.argv[1]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(live, "core"))
import db
holds = []
real = db.connect
class Timed:
    def __init__(self, con, ro): self.con, self.t, self.ro = con, time.time(), ro
    def __getattr__(self, n): return getattr(self.con, n)
    def close(self):
        holds.append([round(time.time() - self.t, 2), self.ro]); self.con.close()
def timed(read_only=False, **kw): return Timed(real(read_only=read_only, **kw), read_only)
db.connect = timed
import contact_strength, voice
t = time.time(); n = contact_strength.refresh(); recount = time.time() - t
t = time.time(); v = voice.build(); build = time.time() - t
c = real(read_only=True)
dana = c.execute("SELECT sent_count, received_count, strength > 0 FROM contacts WHERE key = 'email:dana@acme.example'").fetchone()
c.close()
print(json.dumps({"holds": holds, "recount": round(recount, 1), "build": round(build, 1), "contacts": n, "dana": list(dana or []),
                  "voice_messages": v.get("messages"), "greeting": (v.get("greetings") or [None])[0]}))
'''

READER = r'''
import json, sys, os, time
live = sys.argv[1]
sys.path.insert(0, live)
import db
worst, reads, end = 0.0, 0, time.time() + float(sys.argv[2])
open(sys.argv[3], "w").write("ready")
while time.time() < end and not os.path.exists(sys.argv[4]):
    t = time.time()
    while True:
        con = db.try_connect(read_only=True)
        if con is not None:
            con.execute("SELECT count(*) FROM live_items").fetchone(); con.close(); break
        time.sleep(0.02)
    worst = max(worst, time.time() - t); reads += 1
    time.sleep(0.05)
print(json.dumps({"worst": round(worst, 2), "reads": reads}))
'''

AFTER_PASS = r'''
import json, sys, os
live = sys.argv[1]
sys.path.insert(0, live)
import db, common
c = db.connect(read_only=True)
counted = c.execute("SELECT count(*) FROM contacts WHERE counted_at IS NOT NULL").fetchone()[0]
c.close()
print(json.dumps({"counted": counted, "voice": os.path.isfile(os.path.join(common.PERSONAL, "voice.json"))}))
'''


def check(name, got, want):
    results.append((name, got == want, got, want))


def last_json(r):
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": (r.stderr or r.stdout).strip()[-1500:]}


def main():
    tmp = tempfile.mkdtemp(prefix="holds-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_holds", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47924", "--sending", "no",
                            "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)

        # 3. an update's quick check leaves both out (the voice the first pass learned is set aside first)
        voice_file = os.path.join(home, "personal", "voice.json")
        if os.path.isfile(voice_file):
            os.remove(voice_file)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True,
                           env=dict(env, ASSISTANT_QUICK_PASS="1"), timeout=600)
        check("3 a quick pass ends ok", r.returncode, 0)
        r = subprocess.run([sys.executable, "-c", AFTER_PASS, live], capture_output=True, text=True, env=env, timeout=120)
        check("3 a quick pass neither recounts contacts nor learns the voice", last_json(r), {"counted": 0, "voice": False})

        t0 = time.time()
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", SEED, live], capture_output=True, text=True, env=env, timeout=1800)
        print(f"   (made the 6,000 messages in {time.time() - t0:.0f} s)", flush=True)
        check("6,000 made-up messages in the database", r.stdout.strip().splitlines()[-1:] if r.returncode == 0 else r.stderr[-800:], ["messages 6000"])

        # 1. the page reads while the recount and the build run
        ready, stop = os.path.join(tmp, "reader.ready"), os.path.join(tmp, "work.done")
        reader = subprocess.Popen([sys.executable, "-c", READER, live, "600", ready, stop], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, env=env)
        while not os.path.exists(ready):
            pass
        w = subprocess.run([sys.executable, "-X", "utf8", "-c", WORK, live], capture_output=True, text=True, env=env, timeout=1200)
        open(stop, "w").close()
        out, err = reader.communicate(timeout=120)
        got, rd = last_json(w), (json.loads(out.strip().splitlines()[-1]) if out.strip() else {"error": err[-800:]})
        holds = got.get("holds") or []
        check("1 the page's reads went on all through (the recount and build now take well under a second, so a few reads)", (rd.get("reads") or 0) >= 3, True)
        check("1 every page read answered in under 0.5 s", (rd.get("worst") is not None and rd["worst"] < 0.5, rd.get("worst")), (True, rd.get("worst")))
        check("1 no connection the recount or the build opened was held 2 s or more", [h for h in holds if h[0] >= 2], [])
        check("1 the recount and the build each opened the database briefly (read, then one write for the recount)", len(holds), 3)
        # 2. still right
        check("2 the recount counts the frequent made-up contact both ways", (got.get("dana") or [0, 0, False])[2], True)
        check("2 the voice is learned from the sent mail", ((got.get("voice_messages") or 0) >= 1000, got.get("greeting")), (True, "Hi"))
        print(f"   (recount {got.get('recount')} s, voice build {got.get('build')} s, worst page read {rd.get('worst')} s, holds {holds})")

        # 3 (cont.): a regular pass recounts and learns; only the quick one leaves them out
        g = open(os.path.join(live, "gather.py"), encoding="utf-8").read()
        p = open(os.path.join(live, "pass.py"), encoding="utf-8").read()
        check("3 a regular pass recounts and learns the voice (only an update's quick check leaves them out)",
              ("contact_strength" not in g and re.search(r'not os\.environ\.get\("ASSISTANT_QUICK_PASS"\):\s+t1 = time\.time\(\)\s+contact_strength\.refresh\(\)', p) is not None,
               re.search(r'not os\.environ\.get\("ASSISTANT_QUICK_PASS"\) and voice\.refresh\(\)', p) is not None), (True, True))
    finally:
        _cleanup.remove(tmp)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
