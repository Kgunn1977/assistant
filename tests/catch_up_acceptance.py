r"""Acceptance: when the regular check catches up on answers that reached no listener, a typed message for the chat is
answered (a Claude call) with no database connection held, so neither a write from another process nor a page read
waits on it. On a scratch copy laid down from this plugin, Claude is a stand-in that takes 3 seconds; a card answer
waiting in the same catch-up is applied as before. Nothing outside the scratch folder changes.

    python tests\catch_up_acceptance.py
"""
import importlib.util
import json
import os
import shutil
import _cleanup  # noqa: E402  the scratch folder goes when the test ends
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                                      # the plugin: this repository
results = []

INSIDE = r'''
import hashlib, json, os, secrets, subprocess, sys, threading, time, urllib.request
live = sys.argv[1]
sys.path.insert(0, live); sys.path.insert(0, os.path.join(os.path.dirname(live), "live_page"))
import common, db, items, answers, chat
out = {}
iid, _ = items.upsert("catchup:card", "chat", kind="task", area="From you", state="yours", title="A card answered while nobody listened")
now = common.now().isoformat(timespec="seconds")
answers._save({"id": "chat", "action": "answer", "text": "remember the roof is booked for Friday", "at": now})
answers._save({"id": iid, "action": "done", "at": now})

def slow_claude(words, told, sess):                 # the Claude call, standing in: 3 seconds, then a plain reply
    time.sleep(3)
    return ("Noted: the roof is booked for Friday.", "", 3.0, {})
chat._run = slow_claude

import local_site                                   # the page server, for a signed-in browser
srv = local_site.start()
tok = secrets.token_urlsafe(48)
with local_site.changed:
    local_site._save("sessions", {hashlib.sha256(tok.encode()).hexdigest(): {"made": int(time.time()), "seen": int(time.time()),
                     "exp": int(time.time()) + 3600, "len": 3600, "csrf": secrets.token_hex(32)}})
base = f"http://127.0.0.1:{srv.server_address[1]}"
def door(path):
    req = urllib.request.Request(base + path, headers={"Cookie": f"{local_site.cookie_name()}={tok}", "Host": f"127.0.0.1:{srv.server_address[1]}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, json.loads(resp.read())

WRITER = ("import sys, time; sys.path.insert(0, sys.argv[1]); import db; t = time.time(); c = db.connect(); "
          "c.execute('CREATE TABLE IF NOT EXISTS catchup_probe(x INT)'); c.execute('INSERT INTO catchup_probe VALUES (1)'); c.close(); "
          "print(round(time.time() - t, 2))")
got = {}
check = threading.Thread(target=lambda: got.update(r=items.apply_answers("t-catchup")))
t0 = time.time()
check.start()
time.sleep(0.5)                                     # the stand-in Claude is answering now
w = subprocess.run([sys.executable, "-c", WRITER, live], capture_output=True, text=True, timeout=120)
w_done = time.time() - t0
t1 = time.time()
s, page = door("/api/mail?view=inbox")
read_secs = time.time() - t1
running = check.is_alive()
check.join()
out["while Claude answers: another process writes"] = [w.returncode, w_done < 3, running]
out["while Claude answers: a page read answers at once, not busy"] = [s, read_secs < 0.5, bool(page.get("busy"))]
out["the check took the 3 s Claude answer"] = time.time() - t0 >= 3
said = [t.get("text") for t in chat.load()["turns"]]
row = answers._row(db.connect(read_only=True), iid)
out["afterwards: the chat words are answered, the card answer applied, nothing left waiting"] = [
    "remember the roof is booked for Friday" in said, "Noted: the roof is booked for Friday." in said, row["state"], len(answers._pending()),
    got.get("r", (None,))[0]]

# the contacts step of a check asks a chat service for its people (here a stand-in taking 3 s) before it opens the database
sys.path.insert(0, os.path.join(live, "core"))
import connections, refresh_contacts
def slow_people():
    time.sleep(3)
    return {"chat": {"U1": {"name": "Pat Lee", "email": "pat@example.com", "is_bot": False, "deleted": False}}}
refresh_contacts.id_people = slow_people
sys.argv = ["refresh_contacts.py"]
step = threading.Thread(target=refresh_contacts.main)
t0 = time.time()
step.start()
time.sleep(0.5)
w = subprocess.run([sys.executable, "-c", WRITER, live], capture_output=True, text=True, timeout=120)
w_done = time.time() - t0
running = step.is_alive()
step.join()
c = db.connect(read_only=True)
kept = c.execute("SELECT count(*) FROM contacts WHERE key = 'chat:U1'").fetchone()[0]
c.close()
out["while a chat service answers the contacts step: another process writes, and its person is kept"] = [w.returncode, w_done < 3, running, kept]
print(json.dumps(out))
'''

WANT = {
    "while Claude answers: another process writes": [0, True, True],
    "while Claude answers: a page read answers at once, not busy": [200, True, False],
    "the check took the 3 s Claude answer": True,
    "while a chat service answers the contacts step: another process writes, and its person is kept": [0, True, True, 1],
    "afterwards: the chat words are answered, the card answer applied, nothing left waiting": [True, True, "done", 0, 1],
}


def check(name, got, want):
    results.append((name, got == want, got, want))


def main():
    tmp = tempfile.mkdtemp(prefix="catchup-")
    data, root = os.path.join(tmp, "plugin-data"), os.path.join(tmp, "Assistant")
    home, live = os.path.join(root, "Live"), os.path.join(root, "System", "live")
    env = dict(os.environ, ASSISTANT_LIVE_HOME=home)
    spec = importlib.util.spec_from_file_location("assistant_copy_catchup", os.path.join(PKG, "hooks", "assistant_copy.py"))
    copier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copier)
    try:
        copier.sync(data)
        r = subprocess.run([sys.executable, os.path.join(data, "scripts", "assistant.py"), "lay-down", "--port", "47911",
                            "--sending", "no", "--root", root], capture_output=True, text=True)
        check("lay-down", r.returncode, 0)
        r = subprocess.run([sys.executable, os.path.join(live, "pass.py")], capture_output=True, text=True, env=env, timeout=600)
        check("a first pass makes the database", r.returncode, 0)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", INSIDE, live], capture_output=True, text=True, env=env, timeout=600)
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = {}
            check("the checks ran", r.stderr.strip()[-1500:], "")
        for name, want in WANT.items():
            check(name, got.get(name), want)
    finally:
        _cleanup.remove(tmp)
    for name, ok, got, want in results:
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": wanted {want!r}, got {got!r}"))
    print(f"{sum(r[1] for r in results)} of {len(results)} passed")
    return 0 if all(r[1] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
